"""L'écran virtuel où DCS dessine les écrans exportés : le trouver, l'installer,
le mettre à sa place.

DCS s'étend vers la droite de l'écran principal. Les écrans exportés vont
donc sur un second écran que personne ne regarde, collé à droite du
principal, aligné en haut, à la même définition et à la même fréquence. Le
placer au pixel près dans Paramètres → Écran, c'est là que les pilotes
bloquaient : ce module le fait à leur place.

- TROUVER : un écran virtuel parmi ceux de Windows (Virtual Display Driver ou
  un autre pilote d'écran virtuel). Un écran physique n'est jamais pris pour
  lui, ni déplacé.
- INSTALLER, s'il n'y en a pas et si le pilote est d'accord : Virtual Display
  Driver, open source, téléchargé sur GitHub à une version fixée et vérifié
  par son empreinte SHA-256, posé par NefCon comme le fait le script
  d'installation silencieuse du projet (Community Scripts/silent-install.ps1)
  — sans ajouter ses certificats aux éditeurs de confiance : Windows demande
  donc lui-même s'il faut installer le pilote. Seule étape qui demande les
  droits d'administrateur, dans un processus à part.
- PLACER : mode « Étendre », à droite du principal, aligné en haut, à la
  définition et à la fréquence du principal quand l'écran virtuel les propose.

Chaque étape se fait aussi à la main (LISEZ-MOI, « À la main ») : les
messages disent laquelle a échoué et quoi faire.
"""
from __future__ import annotations

import ctypes
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

Mode = Tuple[int, int, int]           # largeur, hauteur, fréquence

VDD = "https://github.com/VirtualDrivers/Virtual-Display-Driver"
# Versions fixées, vérifiées à l'empreinte : un fichier changé sur GitHub
# n'est pas installé. Les mêmes que silent-install.ps1 du projet.
PILOTE = (f"{VDD}/releases/download/25.7.23/VirtualDisplayDriver-x86.Driver.Only.zip",
          "e24210692b442b39af763536330ce78b423f19342b7a7792c26de3944e418b3a")
NEFCON = ("https://github.com/nefarius/nefcon/releases/download/v1.14.0/nefcon_v1.14.0.zip",
          "a15557da24a9efca203158de3b43b0eaf982db231f0194031f1ed428bc13e669")
ID_MATERIEL = r"Root\MttVDD"
# Où le pilote lit vdd_settings.xml, sauf autre chemin dans le registre
# (Driver.cpp du projet : confpath, valeur VDDPATH).
DOSSIER_VDD = Path(r"C:\VirtualDisplayDriver")
CLE_VDD = r"SOFTWARE\MikeTheTech\VirtualDisplayDriver"
# Nom du pilote, identifiant matériel ou du moniteur (EDID « MTT1337 »).
MOTS_VIRTUELS = ("mttvdd", "mtt1337", "iddsample", "virtual", "virtuel")
ATTENTE_ECRAN_S = 30
PROBLEME_DESACTIVE = 22                # CM_PROB_DISABLED
REDEMARRAGE = 3010                     # ERROR_SUCCESS_REBOOT_REQUIRED
REFUS_UAC = 1223                       # ERROR_CANCELLED

MANUEL = [
    "À la main (détail dans LISEZ-MOI.txt, « À la main ») :",
    f"  1. Installer Virtual Display Driver : {VDD}/releases",
    "     (« VDD Control », puis Install).",
    "  2. Paramètres → Système → Écran : « Étendre ces affichages », écran virtuel",
    "     à la définition et à la fréquence du principal, glissé à DROITE du",
    "     principal, bords du HAUT alignés.",
    "  3. Relancer Installer.bat : il vérifie et finit le reste.",
]


@dataclass(frozen=True)
class Ecran:
    nom: str                  # \\.\DISPLAY2
    carte: str                # nom du pilote : « Virtual Display Driver »
    ident: str                # identifiants matériels de la carte et du moniteur
    x: int
    y: int
    largeur: int
    hauteur: int
    frequence: int
    principal: bool = False
    actif: bool = True        # sur le bureau : ni dupliqué, ni déconnecté
    modes: Tuple[Mode, ...] = ()

    @property
    def virtuel(self) -> bool:
        texte = f"{self.carte} {self.ident}".lower()
        return any(mot in texte for mot in MOTS_VIRTUELS)

    def __str__(self) -> str:
        return f"« {self.carte} » ({self.largeur}×{self.hauteur}, {self.frequence} Hz)"


@dataclass(frozen=True)
class Placement:
    """Où et comment mettre l'écran virtuel."""
    ecran: Ecran
    x: int
    y: int
    largeur: int
    hauteur: int
    frequence: int

    @property
    def a_faire(self) -> bool:
        e = self.ecran
        return (not e.actif or (e.x, e.y, e.largeur, e.hauteur, e.frequence)
                != (self.x, self.y, self.largeur, self.hauteur, self.frequence))


# --------------------------------------------------------------- décisions

def choisir_mode(modes: Sequence[Mode], largeur: int, hauteur: int,
                 frequence: int) -> Optional[Mode]:
    """Le mode de l'écran virtuel le plus proche de celui du principal.

    La définition d'abord : DCS ne fait qu'une fenêtre, de la hauteur du plus
    haut des deux, et le kneeboard se colle en bas à droite — sur un écran
    virtuel moins haut, il tomberait hors de tout écran. Plus haut, le bas ne
    serait jamais dessiné. Puis la même fréquence, sinon la plus proche
    au-dessus, pour ne pas ralentir l'image de DCS sur l'écran virtuel.
    """
    if not modes:
        return None
    return min(modes, key=lambda m: ((m[0], m[1]) != (largeur, hauteur), m[1] != hauteur,
                                     m[1] > hauteur, abs(m[1] - hauteur),
                                     abs(m[0] - largeur), m[2] < frequence,
                                     abs(m[2] - frequence)))


def _chevauche(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def planifier(ecrans: Sequence[Ecran]) -> Tuple[Optional[Placement], List[str]]:
    """Où mettre l'écran virtuel, ou pourquoi on ne le peut pas.

    Seul l'écran virtuel bouge. Un écran physique qui occupe sa place n'est
    pas déplacé : on dit lequel, le pilote choisit où le mettre.
    """
    principal = next((e for e in ecrans if e.principal), None)
    if principal is None:
        return None, ["Écran principal introuvable."]
    if principal.virtuel:
        return None, [f"L'écran principal est l'écran virtuel {principal}.",
                      "Paramètres → Système → Écran : choisir l'écran qu'on regarde, puis",
                      "cocher « En faire mon écran principal », et relancer Installer.bat."]
    virtuels = [e for e in ecrans if e.virtuel and not e.principal]
    if not virtuels:
        return None, ["Aucun écran virtuel."]
    x, y = principal.x + principal.largeur, principal.y
    # Plusieurs écrans virtuels : celui qui est déjà à sa place, sinon le premier.
    cible = next((e for e in virtuels if e.actif and (e.x, e.y) == (x, y)),
                 next((e for e in virtuels if e.actif), virtuels[0]))
    largeur, hauteur, frequence = (
        choisir_mode(cible.modes, principal.largeur, principal.hauteur, principal.frequence)
        or (cible.largeur or principal.largeur, cible.hauteur or principal.hauteur,
            cible.frequence))
    place = (x, y, largeur, hauteur)
    genants = [e for e in ecrans if e is not cible and e.actif and not e.principal
               and _chevauche((e.x, e.y, e.largeur, e.hauteur), place)]
    if genants:
        return None, [f"L'écran {genants[0]} occupe la place à droite de l'écran principal.",
                      "Paramètres → Système → Écran : le glisser à gauche ou sous le principal,",
                      "puis relancer Installer.bat, qui mettra l'écran virtuel à droite."]
    return Placement(cible, x, y, largeur, hauteur, frequence), []


def reglages_vdd(texte: str, largeur: int, hauteur: int, frequence: int) -> str:
    """vdd_settings.xml avec la définition et la fréquence du principal.

    Le pilote ne propose que les modes de ce fichier : le 3440 × 1440 d'un
    écran large, ou 240 Hz, n'y sont pas d'origine. On ajoute ce qui manque,
    sans rien retirer : un fichier déjà réglé par le pilote reste le sien.
    """
    analyseur = ElementTree.XMLParser(target=ElementTree.TreeBuilder(insert_comments=True))
    racine = ElementTree.fromstring(texte, parser=analyseur)

    def section(nom: str) -> ElementTree.Element:
        trouve = racine.find(nom)
        return trouve if trouve is not None else ElementTree.SubElement(racine, nom)

    if frequence > 1:
        globale = section("global")
        if not any(_entier(g.text) == frequence for g in globale.findall("g_refresh_rate")):
            ElementTree.SubElement(globale, "g_refresh_rate").text = str(frequence)
    resolutions = section("resolutions")
    if not any((_entier(r.findtext("width")), _entier(r.findtext("height"))) == (largeur, hauteur)
               for r in resolutions.findall("resolution")):
        nouvelle = ElementTree.SubElement(resolutions, "resolution")
        for cle, valeur in (("width", largeur), ("height", hauteur),
                            ("refresh_rate", frequence if frequence > 1 else 60)):
            ElementTree.SubElement(nouvelle, cle).text = str(valeur)
    ElementTree.indent(racine, space="    ")
    return ("<?xml version='1.0' encoding='utf-8'?>\n"
            + ElementTree.tostring(racine, encoding="unicode") + "\n")


def _entier(texte: Optional[str]) -> Optional[int]:
    try:
        return int(float((texte or "").strip()))
    except ValueError:
        return None


# --------------------------------------------------------------- Windows

class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32),
                ("DeviceString", wintypes.WCHAR * 128), ("StateFlags", wintypes.DWORD),
                ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128)]


class DEVMODEW(ctypes.Structure):
    # La variante « écran » de l'union : la position à la place des champs
    # d'imprimante, même taille.
    _fields_ = [("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
                ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
                ("dmPositionX", wintypes.LONG), ("dmPositionY", wintypes.LONG),
                ("dmDisplayOrientation", wintypes.DWORD),
                ("dmDisplayFixedOutput", wintypes.DWORD),
                ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
                ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
                ("dmCollate", ctypes.c_short), ("dmFormName", wintypes.WCHAR * 32),
                ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD),
                ("dmPelsWidth", wintypes.DWORD), ("dmPelsHeight", wintypes.DWORD),
                ("dmDisplayFlags", wintypes.DWORD), ("dmDisplayFrequency", wintypes.DWORD),
                ("dmICMMethod", wintypes.DWORD), ("dmICMIntent", wintypes.DWORD),
                ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD),
                ("dmReserved1", wintypes.DWORD), ("dmReserved2", wintypes.DWORD),
                ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD)]


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG),
                ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
                ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int),
                ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE),
                ("hProcess", wintypes.HANDLE)]


ATTACHE_AU_BUREAU = 0x1
PRINCIPAL = 0x4
MIROIR = 0x8
ENUM_CURRENT_SETTINGS = 0xFFFFFFFF
ENUM_REGISTRY_SETTINGS = 0xFFFFFFFE
DM_POSITION = 0x20
DM_PELSWIDTH = 0x80000
DM_PELSHEIGHT = 0x100000
DM_DISPLAYFREQUENCY = 0x400000
CDS_UPDATEREGISTRY = 0x1
CDS_NORESET = 0x10000000
SDC_TOPOLOGY_EXTEND = 0x4
SDC_APPLY = 0x80
SEE_MASK_NOCLOSEPROCESS = 0x40
INFINI = 0xFFFFFFFF


def _user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.EnumDisplayDevicesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                           ctypes.POINTER(DISPLAY_DEVICEW), wintypes.DWORD]
    user32.EnumDisplaySettingsExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                              ctypes.POINTER(DEVMODEW), wintypes.DWORD]
    user32.ChangeDisplaySettingsExW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(DEVMODEW),
                                                wintypes.HWND, wintypes.DWORD, ctypes.c_void_p]
    user32.ChangeDisplaySettingsExW.restype = wintypes.LONG
    user32.SetDisplayConfig.argtypes = [wintypes.UINT, ctypes.c_void_p, wintypes.UINT,
                                        ctypes.c_void_p, wintypes.UINT]
    user32.SetDisplayConfig.restype = wintypes.LONG
    return user32


def _peripherique(user32, nom: Optional[str], rang: int) -> Optional[DISPLAY_DEVICEW]:
    d = DISPLAY_DEVICEW()
    d.cb = ctypes.sizeof(d)
    return d if user32.EnumDisplayDevicesW(nom, rang, ctypes.byref(d), 0) else None


def _reglage(user32, nom: str, rang: int) -> Optional[DEVMODEW]:
    m = DEVMODEW()
    m.dmSize = ctypes.sizeof(m)
    return m if user32.EnumDisplaySettingsExW(nom, rang, ctypes.byref(m), 0) else None


def lister() -> List[Ecran]:
    """Les écrans que Windows connaît, sur le bureau ou non, en pixels réels.

    Une sortie de carte graphique sans moniteur n'en est pas un. Une sortie
    d'écran virtuel sans moniteur l'est : c'est l'écran virtuel dupliqué ou
    déconnecté, qu'il faut remettre sur le bureau.
    """
    user32 = _user32()
    ecrans = []
    rang = 0
    while (carte := _peripherique(user32, None, rang)) is not None:
        rang += 1
        if carte.StateFlags & MIROIR:
            continue
        moniteur = _peripherique(user32, carte.DeviceName, 0)
        ident = f"{carte.DeviceID} {moniteur.DeviceID if moniteur else ''}".strip()
        actif = bool(carte.StateFlags & ATTACHE_AU_BUREAU)
        virtuel = any(mot in f"{carte.DeviceString} {ident}".lower() for mot in MOTS_VIRTUELS)
        if moniteur is None and not (virtuel or actif):
            continue
        modes, i = set(), 0
        while (m := _reglage(user32, carte.DeviceName, i)) is not None:
            i += 1
            if m.dmDisplayFrequency > 1:          # 0 et 1 : « fréquence du matériel »
                modes.add((m.dmPelsWidth, m.dmPelsHeight, m.dmDisplayFrequency))
        r = _reglage(user32, carte.DeviceName,
                     ENUM_CURRENT_SETTINGS if actif else ENUM_REGISTRY_SETTINGS)
        position = ((r.dmPositionX, r.dmPositionY, r.dmPelsWidth, r.dmPelsHeight,
                     r.dmDisplayFrequency) if r is not None else (0, 0, 0, 0, 0))
        ecrans.append(Ecran(carte.DeviceName, carte.DeviceString, ident, *position,
                            principal=bool(carte.StateFlags & PRINCIPAL),
                            actif=actif and r is not None, modes=tuple(sorted(modes))))
    return ecrans


def etendre() -> bool:
    """Le mode « Étendre » de Windows (Win+P), comme si on l'avait choisi : un
    écran dupliqué ou déconnecté ne reçoit pas la fenêtre de DCS."""
    return _user32().SetDisplayConfig(0, None, 0, None, SDC_APPLY | SDC_TOPOLOGY_EXTEND) == 0


def appliquer(placement: Placement) -> Optional[str]:
    """Place l'écran virtuel et l'enregistre (il y restera au redémarrage).
    Rend la raison d'un refus de Windows, ou None."""
    user32 = _user32()
    m = DEVMODEW()
    m.dmSize = ctypes.sizeof(m)
    m.dmFields = DM_POSITION | DM_PELSWIDTH | DM_PELSHEIGHT
    m.dmPositionX, m.dmPositionY = placement.x, placement.y
    m.dmPelsWidth, m.dmPelsHeight = placement.largeur, placement.hauteur
    if placement.frequence > 1:
        m.dmFields |= DM_DISPLAYFREQUENCY
        m.dmDisplayFrequency = placement.frequence
    code = user32.ChangeDisplaySettingsExW(placement.ecran.nom, ctypes.byref(m), None,
                                           CDS_UPDATEREGISTRY | CDS_NORESET, None)
    if code != 0:
        return f"Windows refuse ce réglage (code {code})"
    code = user32.ChangeDisplaySettingsExW(None, None, None, 0, None)
    return None if code == 0 else f"Windows n'a pas appliqué le réglage (code {code})"


# ------------------------------------------------- installation du pilote

def dossier_vdd() -> Path:
    """Le dossier où le pilote lit ses réglages."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CLE_VDD) as cle:
            return Path(winreg.QueryValueEx(cle, "VDDPATH")[0])
    except (ImportError, OSError):
        return DOSSIER_VDD


def _telecharger(url: str, empreinte: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as reponse:
        donnees = reponse.read()
    if hashlib.sha256(donnees).hexdigest() != empreinte:
        raise OSError(f"{url.rsplit('/', 1)[-1]} n'est pas le fichier attendu "
                      "(empreinte différente) : rien n'est installé.")
    return donnees


def _powershell(commande: str, **environnement: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", commande],
                          env=dict(os.environ, **environnement), capture_output=True,
                          text=True, errors="replace", timeout=120)


def _peripherique_vdd() -> Optional[Tuple[str, int]]:
    """Virtual Display Driver déjà là (désactivé, en panne) : son identifiant
    d'instance et son code de problème. Pour ne pas en créer un second."""
    sortie = _powershell(
        "Get-PnpDevice -Class Display -ErrorAction SilentlyContinue | "
        "Where-Object { $_.HardwareID -contains $env:DT_ID } | "
        "ForEach-Object { $_.InstanceId + '|' + [int]$_.ConfigManagerErrorCode }",
        DT_ID=ID_MATERIEL).stdout
    for ligne in sortie.splitlines():
        instance, _, code = ligne.strip().rpartition("|")
        if instance and code.isdigit():
            return instance, int(code)
    return None


def installer_pilote(mode: Mode, journal: Callable[[str], None] = print) -> int:
    """Installe Virtual Display Driver, réglé sur le mode du principal.

    Processus administrateur (`DCS-Tablette.exe pilote-ecran-virtuel`, lancé
    par `lancer_installation`) : il ne fait que ça. Rend 0, REDEMARRAGE, ou
    un autre code en cas d'échec, raison au journal.
    """
    try:
        existant = _peripherique_vdd()
    except (OSError, subprocess.SubprocessError):
        existant = None
    if existant and existant[1] == PROBLEME_DESACTIVE:
        journal("Virtual Display Driver est installé mais désactivé : réactivation.")
        r = _powershell("Enable-PnpDevice -InstanceId $env:DT_INSTANCE -Confirm:$false",
                        DT_INSTANCE=existant[0])
        if r.returncode:
            journal(f"Réactivation refusée : {r.stderr.strip()[:300]}")
        return r.returncode
    if existant and existant[1] == 0:
        journal("Virtual Display Driver est déjà installé et en marche.")
        return 0

    dossier = dossier_vdd()
    with tempfile.TemporaryDirectory(prefix="dcs-tablette-") as temporaire:
        temporaire = Path(temporaire)
        try:
            for nom, (url, empreinte) in (("NefCon", NEFCON), ("VDD", PILOTE)):
                journal(f"Téléchargement : {url}")
                with zipfile.ZipFile(io.BytesIO(_telecharger(url, empreinte))) as z:
                    z.extractall(temporaire / nom)
        except OSError as e:
            journal(f"Téléchargement impossible : {e}")
            return 1
        source = temporaire / "VDD" / "VirtualDisplayDriver"
        dossier.mkdir(parents=True, exist_ok=True)
        for nom in ("MttVDD.dll", "MttVDD.inf", "mttvdd.cat"):
            shutil.copyfile(source / nom, dossier / nom)
        reglages = dossier / "vdd_settings.xml"
        modele = reglages if reglages.exists() else source / "vdd_settings.xml"
        reglages.write_text(reglages_vdd(modele.read_text(encoding="utf-8"), *mode),
                            encoding="utf-8")
        journal(f"Réglages de l'écran virtuel : {reglages} ({mode[0]}×{mode[1]}, {mode[2]} Hz)")
        nefcon = str(temporaire / "NefCon" / "x64" / "nefconw.exe")
        inf = str(dossier / "MttVDD.inf")
        # Un appareil déjà là (pilote en panne) reçoit le pilote ; sinon on le
        # crée avec : « install » en créerait un second à côté du premier.
        commande = ([nefcon, "--install-driver", "--inf-path", inf] if existant
                    else [nefcon, "install", inf, ID_MATERIEL])
        journal("Installation du pilote (Windows peut demander de confirmer l'éditeur)…")
        try:
            code = subprocess.run(commande, cwd=dossier, timeout=300).returncode
        except (OSError, subprocess.SubprocessError) as e:
            journal(f"NefCon n'a pas pu s'exécuter : {e}")
            return 1
    if code == REDEMARRAGE:
        journal("Pilote installé ; Windows demande un redémarrage.")
    elif code:
        journal(f"Le pilote n'a pas été installé (NefCon : code {code}).")
    else:
        journal("Pilote installé.")
    return code


def lancer_installation(mode: Mode) -> Tuple[int, List[str]]:
    """Lance `installer_pilote` en administrateur : Windows le demande (UAC).

    Le reste de l'installation ne quitte pas l'utilisateur : en
    administrateur, « Parties enregistrées » et le Bureau pourraient être
    ceux d'un autre compte. Rend le code de sortie et le journal.
    """
    if getattr(sys, "frozen", False):
        debut = []
    else:
        src = str(Path(__file__).resolve().parents[1])
        debut = ["-c", f"import sys; sys.path.insert(0, {src!r}); "
                       "from tablette.__main__ import main; sys.exit(main())"]
    descripteur, journal = tempfile.mkstemp(prefix="dcs-tablette-", suffix=".txt")
    os.close(descripteur)
    try:
        arguments = debut + ["pilote-ecran-virtuel", "--mode", "{}x{}@{}".format(*mode),
                             "--journal", journal]
        info = SHELLEXECUTEINFOW()
        info.cbSize = ctypes.sizeof(info)
        info.fMask = SEE_MASK_NOCLOSEPROCESS
        info.lpVerb = "runas"
        info.lpFile = sys.executable
        info.lpParameters = subprocess.list2cmdline(arguments)
        info.nShow = 1
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        if not shell32.ShellExecuteExW(ctypes.byref(info)):
            erreur = ctypes.get_last_error()
            if erreur == REFUS_UAC:
                return REFUS_UAC, ["Autorisation administrateur refusée : rien n'a été installé."]
            return erreur or 1, [f"Lancement en administrateur impossible (erreur {erreur})."]
        kernel32.WaitForSingleObject(info.hProcess, INFINI)
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        kernel32.CloseHandle(info.hProcess)
        lignes = Path(journal).read_text(encoding="utf-8", errors="replace").splitlines()
        return code.value, lignes
    finally:
        Path(journal).unlink(missing_ok=True)


# --------------------------------------------------------------- l'étape

def _accepte(reponse: Optional[str]) -> bool:
    return reponse is not None and reponse.strip().lower() in ("", "o", "oui", "y", "yes")


def preparer(afficher: Callable[[str], None], demander: Callable[[str], Optional[str]],
             lister: Callable[[], List[Ecran]] = lister, etendre: Callable[[], bool] = etendre,
             appliquer: Callable[[Placement], Optional[str]] = appliquer,
             installer: Callable[[Mode], Tuple[int, List[str]]] = lancer_installation,
             attendre: Callable[[float], None] = time.sleep) -> bool:
    """L'étape « écran virtuel » d'Installer.bat : trouvé, installé s'il le
    faut et si le pilote est d'accord, mis à sa place. Rend True s'il est prêt.

    `demander` rend None quand personne ne peut répondre (pas de console) :
    rien n'est alors installé sans accord.
    """
    ecrans = lister()
    principal = next((e for e in ecrans if e.principal), None)
    if principal is None:
        afficher("Écran principal introuvable.")
        return False
    if not any(e.virtuel and not e.principal for e in ecrans) and not principal.virtuel:
        droite = (principal.x + principal.largeur, principal.y)
        deja = next((e for e in ecrans if e.actif and not e.principal
                     and (e.x, e.y) == droite), None)
        if deja is not None:
            # Une prise HDMI factice, ou un écran choisi exprès : on le garde.
            afficher(f"Second écran {deja} déjà à droite du principal, aligné en haut : gardé.")
            return True
        for ligne in ("Aucun écran virtuel. Il en faut un, que personne ne regarde, pour que",
                      "DCS y dessine les écrans exportés au lieu de les poser sur la vue.",
                      "DCS Tablette peut installer Virtual Display Driver (gratuit, open source) :",
                      f"  {VDD}",
                      "Windows demandera l'autorisation administrateur, puis peut-être de",
                      "confirmer l'installation du pilote : accepter les deux."):
            afficher(ligne)
        if not _accepte(demander("Installer l'écran virtuel maintenant ? [O/n] ")):
            afficher("Écran virtuel non installé.")
            for ligne in MANUEL:
                afficher(ligne)
            return False
        code, lignes = installer((principal.largeur, principal.hauteur, principal.frequence))
        for ligne in lignes:
            afficher("  " + ligne)
        if code not in (0, REDEMARRAGE):
            for ligne in MANUEL:
                afficher(ligne)
            return False
        # Windows met quelques secondes à brancher le nouvel écran.
        for _ in range(ATTENTE_ECRAN_S):
            ecrans = lister()
            if any(e.virtuel and not e.principal for e in ecrans):
                break
            attendre(1)
        else:
            afficher("Le pilote est installé, mais aucun écran virtuel n'apparaît.")
            afficher("Redémarrer le PC, puis relancer Installer.bat.")
            return False

    if not any(e.virtuel and e.actif and not e.principal for e in ecrans):
        afficher("L'écran virtuel est dupliqué ou déconnecté : passage en mode « Étendre ».")
        if etendre():
            attendre(2)
            ecrans = lister()
    placement, lignes = planifier(ecrans)
    if placement is None:
        for ligne in lignes:
            afficher(ligne)
        return False
    p = placement
    voulu = f"{p.largeur}×{p.hauteur}, {p.frequence} Hz, à droite du principal, aligné en haut"
    if not p.a_faire:
        afficher(f"Écran virtuel {p.ecran} déjà en place.")
        return True
    erreur = appliquer(p)
    if erreur is None:
        attendre(1)
        apres = next((e for e in lister() if e.nom == p.ecran.nom), None)
        if apres is None or (apres.x, apres.y, apres.largeur, apres.hauteur) != (
                p.x, p.y, p.largeur, p.hauteur):
            erreur = "Windows n'a pas gardé la position demandée"
    if erreur:
        afficher(f"Écran virtuel {p.ecran} non placé : {erreur}.")
        afficher(f"À régler dans Paramètres → Système → Écran : {voulu}.")
        return False
    afficher(f"Écran virtuel « {p.ecran.carte} » placé : {voulu}.")
    return True
