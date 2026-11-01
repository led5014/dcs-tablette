r"""Installation dans DCS : les scripts Lua, la ligne d'Export.lua, les écrans.

Sert à l'exécutable (`DCS-Tablette.exe installer`, `desinstaller`) comme aux
scripts du dépôt (`scripts/installer_dcs.py`, `scripts/configurer_ecrans_dcs.py`).
Les fonctions rendent les lignes à afficher au lieu de les imprimer : les
tests les lisent, la console les recopie.

Ce qui est touché, et rien d'autre :
- l'écran virtuel (ecran_virtuel.py) : installé s'il manque et si le pilote
  est d'accord, placé à droite du principal ;
- Saved Games/DCS/Scripts : les deux scripts de la tablette, et une ligne
  ajoutée à la fin d'Export.lua (copie de l'ancien à côté) ;
- Saved Games/DCS/Config/MonitorSetup/tablette.lua, la configuration
  « Tablette DCS » ;
- Saved Games/DCS/Config/options.lua, DCS fermé seulement : configuration
  d'écrans, résolution, fenêtré (copie de l'original à côté) ;
- depuis l'exécutable seulement : le programme copié dans
  %LOCALAPPDATA%\Programs\DCS-Tablette, les raccourcis « DCS Tablette » du
  bureau et du menu Démarrer, « DCS Tablette (écrans) » dans le dossier
  Démarrage (les écrans remis en place à chaque ouverture de Windows), et
  son entrée dans Paramètres → Applications installées, d'où il se
  désinstalle.
Jamais le dossier d'installation de DCS : le contrôle d'intégrité du
multijoueur ne voit rien.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import VERSION
from .capture import moniteurs
from .config import BUREAU, dossier_windows
from .ecrans_dcs import (NOM_AFFICHE, NOM_FICHIER, PasDExport, disposition, disposition_essai,
                         fichier_actif, generer, lire_zones, options_affichage,
                         plein_ecran, regler_options, retablir_options)
from .langues import Texte, fichier_langue, message

SCRIPTS = ("DCS-Tablette-Export.lua", "DCS-Tablette-Appareils.lua")
RACCOURCI = "DCS Tablette.lnk"
ENTETE = "-- DCS Tablette -- ecrans et boutons du cockpit sur l'iPad"
LIGNE = ("pcall(function() local dt_lfs=require('lfs'); "
         "dofile(dt_lfs.writedir()..[[Scripts\\DCS-Tablette-Export.lua]]) end)")
ANCIENS = ("tablette_hornet.lua", "tablette_hornet.lua.precedent")
VDD = "https://github.com/VirtualDrivers/Virtual-Display-Driver"
PROGRAMME = "DCS-Tablette"
EXE = f"{PROGRAMME}.exe"
# Sans fenêtre, lancé à l'ouverture de Windows : il démarre `EXE ecrans`
# sans console (scripts/dcs_tablette_ecrans.py).
EXE_ECRANS = f"{PROGRAMME}-Ecrans.exe"
RACCOURCI_ECRANS = "DCS Tablette (écrans).lnk"
# Ce que le zip pose dans le dossier du programme : copié à l'installation,
# et seul effacé à la désinstallation — rien d'autre de ce dossier.
LIVRES = (EXE, EXE_ECRANS, "_internal", "Installer.bat", "Desinstaller.bat", "LISEZ-MOI.txt",
          "README.txt")
CLE_WINDOWS = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{PROGRAMME}"
MENU_DEMARRER = uuid.UUID("A77F5D77-2E2B-44C3-A6A2-ABA601054A51")      # FOLDERID_Programs
DEMARRAGE = uuid.UUID("B97D20BB-F46A-4C97-BA10-5E3608430854")          # FOLDERID_Startup
DEPOT = "https://github.com/led5014/dcs-tablette"

Moniteur = Tuple[int, int, int, int, bool]      # x, y, largeur, hauteur, principal


def dossier_lua() -> Path:
    """dcs_export/ du dépôt, ou sa copie embarquée dans l'exécutable."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "dcs_export"
    return Path(__file__).resolve().parents[2] / "dcs_export"


def dcs_ouvert() -> bool:
    """DCS.exe tourne-t-il, fenêtre visible ou pas (chargement, menu) ?"""
    sortie = subprocess.run(["tasklist", "/FI", "IMAGENAME eq DCS.exe", "/NH"],
                            capture_output=True, text=True, errors="replace").stdout
    return "DCS.exe" in sortie


def est_installe(saved_games: Path) -> bool:
    """Export.lua charge-t-il le script de la tablette ?"""
    try:
        texte = (saved_games / "Scripts" / "Export.lua").read_bytes()
    except OSError:
        return False
    return SCRIPTS[0].encode() in texte


def scripts_a_jour(saved_games: Path, source: Optional[Path] = None) -> bool:
    """DCS charge-t-il les scripts de CETTE version ? Après une mise à jour,
    les anciens restent dans Saved Games tant qu'on ne les recopie pas."""
    source = source or dossier_lua()
    try:
        return est_installe(saved_games) and all(
            (saved_games / "Scripts" / nom).read_bytes() == (source / nom).read_bytes()
            for nom in SCRIPTS)
    except OSError:
        return False


def premiere_fois(saved_games: Path) -> bool:
    """Rien d'installé : ni la ligne d'Export.lua, ni « Tablette DCS »."""
    return (not est_installe(saved_games)
            and not (saved_games / "Config" / "MonitorSetup" / NOM_FICHIER).exists())


def installer_scripts(saved_games: Path, source: Optional[Path] = None) -> List[str]:
    """Copie les scripts et ajoute leur ligne à Export.lua, une seule fois.

    Les lignes de Tacview, SRS et des autres outils restent telles quelles :
    le script de la tablette se chaîne derrière eux. À relancer après chaque
    mise à jour ; DCS prend les scripts au lancement de la mission suivante.
    """
    source = source or dossier_lua()
    dossier = saved_games / "Scripts"
    dossier.mkdir(parents=True, exist_ok=True)
    lignes = []
    for nom in SCRIPTS:
        shutil.copyfile(source / nom, dossier / nom)
        lignes.append(Texte("Copié : {chemin}", chemin=dossier / nom))
    export = dossier / "Export.lua"
    if est_installe(saved_games):
        return lignes + [Texte("Export.lua charge déjà la tablette.")]
    brut = export.read_bytes() if export.exists() else b""
    if export.exists():
        copie = export.with_name(f"Export.lua.avant-tablette-{date.today():%Y%m%d}")
        shutil.copyfile(export, copie)
        lignes.append(Texte("Copie de l'ancien Export.lua : {nom}", nom=copie.name))
    with open(export, "ab") as f:
        if brut and not brut.endswith(b"\n"):
            f.write(b"\n")
        f.write(f"{ENTETE}\n{LIGNE}\n".encode("ascii"))
    return lignes + [Texte("Export.lua : ligne de la tablette ajoutée.")]


def desinstaller_scripts(saved_games: Path) -> List[str]:
    """Retire la ligne d'Export.lua (copie à côté) et les deux scripts."""
    dossier = saved_games / "Scripts"
    export = dossier / "Export.lua"
    lignes = []
    if export.exists():
        # En octets : un Export.lua écrit par un autre outil n'est pas
        # forcément en UTF-8, et on ne réécrit que ce qu'on retire.
        avant = export.read_bytes().splitlines(keepends=True)
        apres = [l for l in avant
                 if SCRIPTS[0].encode() not in l and not l.startswith(ENTETE.encode())]
        if len(apres) != len(avant):
            copie = export.with_name(f"Export.lua.avant-desinstallation-{date.today():%Y%m%d}")
            shutil.copyfile(export, copie)
            export.write_bytes(b"".join(apres))
            lignes.append(Texte("Export.lua : ligne de la tablette retirée (copie : {nom}).",
                                nom=copie.name))
    for nom in SCRIPTS:
        chemin = dossier / nom
        if chemin.exists():
            chemin.unlink()
            lignes.append(Texte("Supprimé : {chemin}", chemin=chemin))
    return lignes


# ------------------------------------------------------------ où, selon les écrans
#
# La fenêtre de DCS part du coin haut gauche du bureau ENTIER et s'étend
# vers la droite et vers le bas. Elle ne part du principal que si aucun écran
# n'est à sa gauche ni au-dessus de lui (photo d'un pilote, 01/11/2026 : un
# écran à gauche du principal, et la vue de DCS partie sur lui) : un tel
# écran est à ranger ailleurs (`rangement`). Les écrans exportés vont sur un
# écran collé à DROITE du principal (bords du haut alignés) ou DESSOUS (bords
# de gauche alignés), et la fenêtre de DCS couvre le principal et cet
# écran-là. Elle ne doit couvrir AUCUN autre écran : il resterait noir
# pendant le vol. Un écran réel à droite du principal fait donc passer
# l'écran virtuel dessous.

COTES = ("droite", "dessous")


def _virtuel(m: Sequence) -> Optional[bool]:
    """Un écran est décrit par (x, y, largeur, hauteur, principal[, virtuel]) ;
    sans 6e valeur, on ne sait pas (relevé d'EnumDisplayMonitors)."""
    return m[5] if len(m) > 5 else None


def _chevauche(a: Sequence[int], b: Sequence[int]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def supports(ecrans: Sequence[Sequence], physique: bool = True) -> List[Tuple[
        Sequence, str, Tuple[int, int, int, int], Tuple[int, int]]]:
    """Les écrans qui peuvent recevoir les écrans du cockpit, du meilleur au
    moins bon : (écran, côté, sa zone dans la fenêtre de DCS, taille de la
    fenêtre). Virtuels d'abord, puis à droite avant dessous. `physique`
    faux : un écran réel n'est jamais pris — on ne le prend que si le
    pilote a dit que personne ne le regarde (prise HDMI factice)."""
    principal = next((m for m in ecrans if m[4]), None)
    if principal is None:
        return []
    px, py, pl, ph = principal[:4]
    trouves = []
    for m in ecrans:
        if m[4] or (_virtuel(m) is False and not physique):
            continue
        zone = (m[0] - px, m[1] - py, m[2], m[3])
        if zone[:2] == (pl, 0):
            cote = "droite"
        elif zone[:2] == (0, ph):
            cote = "dessous"
        else:
            continue
        fenetre = (max(pl, zone[0] + zone[2]), max(ph, zone[1] + zone[3]))
        if any(o is not m and not o[4]
               and _chevauche((o[0] - px, o[1] - py, o[2], o[3]), (0, 0) + fenetre)
               for o in ecrans):
            continue
        trouves.append((m, cote, zone, fenetre))
    trouves.sort(key=lambda t: (_virtuel(t[0]) is not True, COTES.index(t[1])))
    return trouves


def genants(ecrans: Sequence[Sequence]) -> List[Sequence]:
    """Les écrans réels à gauche ou au-dessus du principal : DCS ouvrirait sa
    fenêtre à partir d'eux. Un écran virtuel mal placé n'en est pas :
    `ecran_virtuel.remettre` s'en charge."""
    principal = next((m for m in ecrans if m[4]), None)
    if principal is None:
        return []
    return sorted((m for m in ecrans if not m[4] and _virtuel(m) is not True
                   and (m[0] < principal[0] or m[1] < principal[1])), key=lambda m: m[:2])


def rangement(ecrans: Sequence[Sequence]) -> List[Tuple[Sequence, int, int]]:
    """Où ranger les écrans `genants` : (écran, x, y) sur le bureau.

    Hors de la fenêtre de DCS, en rang de gauche à droite : sous elle si
    l'écran des écrans du cockpit est à droite du principal (ou s'il n'y en
    a pas, mode essai), à droite d'elle s'il est dessous. La souris y va
    alors par le bas, ou par la droite, sans traverser l'écran virtuel.
    Seule leur place change, jamais leur définition."""
    principal = next((m for m in ecrans if m[4]), None)
    a_ranger = genants(ecrans)
    if principal is None or not a_ranger:
        return []
    px, py, pl, ph = principal[:4]
    restent = [m for m in ecrans if not any(m is g for g in a_ranger)]
    droite = next((m for m in restent if tuple(m[:2]) == (px + pl, py)), None)
    dessous = next((m for m in restent if tuple(m[:2]) == (px, py + ph)), None)
    if droite is None and dessous is not None:
        x, y = px + max(pl, dessous[2]), py
    else:
        y = py + max(ph, droite[3] if droite is not None else 0)
        x = px
    occupes = [tuple(m[:4]) for m in restent]
    places = []
    for m in a_ranger:
        while True:
            gene = next((o for o in occupes if _chevauche((x, y, m[2], m[3]), o)), None)
            if gene is None:
                break
            x = gene[0] + gene[2]
        places.append((m, x, y))
        occupes.append((x, y, m[2], m[3]))
        x += m[2]
    return places


def support_ecrans(ecrans: Sequence[Sequence], essai: bool, physique: bool = True
                   ) -> Optional[Tuple[Tuple[int, int, int, int], Tuple[int, int]]]:
    """Où vont les écrans exportés (zone dans la fenêtre de DCS) et la taille
    de cette fenêtre, c'est-à-dire la résolution à régler dans DCS ; None
    sans écran à sa place."""
    principal = next((m for m in ecrans if m[4]), None)
    if principal is None:
        return None
    pl, ph = principal[2:4]
    if essai:
        return (0, 0, pl, ph), (pl, ph)
    trouves = supports(ecrans, physique)
    return (trouves[0][2], trouves[0][3]) if trouves else None


# ------------------------------------------------------------ le choix du pilote
#
# Fait à l'installation, relu par la console de diagnostic pour savoir quoi
# remettre : « second_ecran » (le cas courant), « essai » (écrans du cockpit
# en bas de la vue), ou « existante » (la configuration d'écrans du pilote,
# qui exporte déjà les écrans : on la laisse et on capture là où elle les
# met). `physique` : un écran réel a été accepté comme support.

def fichier_choix() -> Path:
    racine = os.environ.get("LOCALAPPDATA")
    return (Path(racine) if racine else Path.home()) / "DCS-Tablette" / "installation.json"


def lire_choix(chemin: Optional[Path] = None) -> Dict:
    try:
        choix = json.loads((chemin or fichier_choix()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return choix if isinstance(choix, dict) else {}


def ecrire_choix(choix: Dict, chemin: Optional[Path] = None) -> None:
    chemin = chemin or fichier_choix()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(choix, ensure_ascii=False, indent=1), encoding="utf-8")


def configuration_existante(saved_games: Path) -> Optional[Tuple[str, Dict]]:
    """La configuration d'écrans du pilote, quand ce n'est pas « Tablette
    DCS » et qu'elle exporte déjà des écrans du cockpit (vrais MFD, Helios,
    écran tactile…) : son nom et ses zones. La tablette peut les prendre là."""
    try:
        choix, largeur, hauteur = options_affichage(saved_games)
        if choix.lower() in (Path(NOM_FICHIER).stem, NOM_AFFICHE.lower()):
            return None
        zones = lire_zones(fichier_actif(saved_games).read_text(
            encoding="utf-8", errors="replace"), largeur, hauteur)
    except (OSError, PasDExport):
        return None
    return (choix, zones) if zones else None


def dcs_regle(saved_games: Path, resolution: Tuple[int, int]) -> bool:
    """DCS est-il sur « Tablette DCS », à cette résolution, en fenêtré ?"""
    try:
        choix, largeur, hauteur = options_affichage(saved_games)
    except PasDExport:
        return False
    return (choix.lower() in (Path(NOM_FICHIER).stem, NOM_AFFICHE.lower())
            and (largeur, hauteur) == tuple(resolution) and not plein_ecran(saved_games))


def mode_essai(saved_games: Path) -> Optional[bool]:
    """La configuration « Tablette DCS » est-elle celle d'essai (écrans en
    bas de la vue) ? None si elle n'est pas écrite."""
    try:
        texte = (saved_games / "Config" / "MonitorSetup" / NOM_FICHIER).read_text(
            encoding="utf-8", errors="replace")
    except OSError:
        return None
    return re.search(r"^Description\s*=\s*'Essai", texte, re.M) is not None


def configurer_ecrans(saved_games: Path, essai: bool = False,
                      ecrans: Optional[Sequence[Sequence]] = None,
                      ouvert: Callable[[], bool] = dcs_ouvert,
                      physique: bool = True) -> Tuple[bool, List[str]]:
    """Écrit « Tablette DCS » et, DCS fermé, la sélectionne dans options.lua.

    Second écran (le bon usage) : la vue reste sur l'écran principal, les
    écrans exportés occupent l'écran virtuel collé à droite ou dessous (voir
    `supports`), ou une prise HDMI factice si `physique`. DCS s'étend sur les
    deux, sans couvrir aucun autre écran. Essai : un seul écran, les écrans
    exportés dessinés en bas, par-dessus la vue.

    DCS ouvert, options.lua n'est pas touché : DCS le réécrit en quittant et
    effacerait la modification. On dit quoi régler à la place.
    """
    ecrans = moniteurs() if ecrans is None else ecrans
    principal = next((m for m in ecrans if m[4]), None)
    if not principal:
        return False, [Texte("Écran principal introuvable.")]
    pl, ph = principal[2:4]
    if essai:
        # La taille de l'ÉCRAN, pas celle réglée dans DCS : après un réglage
        # raté, la résolution de DCS ne dit plus où est le bas de la vue.
        zones = disposition_essai(pl, ph)
        description = "Essai : ecrans exportes en bas de l'ecran unique"
        resolution = (pl, ph)
    else:
        trouves = supports(ecrans, physique)
        if not trouves:
            return False, [
                Texte("Pas d'écran libre collé à droite ou sous l'écran principal."),
                Texte("Il en faut un que personne ne regarde, pour que DCS y dessine les écrans"),
                Texte("exportés au lieu de les poser sur la vue :"),
                Texte("  - écran virtuel : Virtual Display Driver, gratuit — {adresse}",
                      adresse=VDD),
                Texte("  - ou une prise HDMI factice."),
                Texte("Installer.bat installe et place l'écran virtuel lui-même. À la main :"),
                Texte("Paramètres → Système → Écran, « Étendre ces affichages », le glisser à"),
                Texte("droite du principal (bords du haut alignés) ou dessous (bords de gauche"),
                Texte("alignés), là où aucun autre écran ne se trouve, puis relancer "
                      "l'installation.")]
        _, cote, zone, resolution = trouves[0]
        zones = disposition(zone, resolution)
        description = "Vue sur l'ecran principal, ecrans exportes sur le second" + (
            ", dessous" if cote == "dessous" else "")

    dossier = saved_games / "Config" / "MonitorSetup"
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / NOM_FICHIER
    texte = generer((0, 0, pl, ph), zones, description)
    # Identique : on n'y touche pas. Réécrit pendant que DCS tourne, il
    # paraîtrait changé depuis son lancement, et la tablette refuserait de
    # capturer jusqu'au redémarrage de DCS (video.py) : c'est le cas d'une
    # mise à jour, Installer.bat relancé DCS ouvert.
    inchange = (fichier.exists()
                and fichier.read_text(encoding="ascii", errors="replace") == texte)
    if inchange:
        lignes = [Texte("Inchangé : {chemin}", chemin=fichier)]
    else:
        if fichier.exists():
            fichier.replace(fichier.with_suffix(".lua.precedent"))
        fichier.write_text(texte, encoding="ascii")
        lignes = [Texte("Écrit : {chemin}", chemin=fichier)]
    for ancien in ANCIENS:                       # l'ancienne « Tablette Hornet »
        (dossier / ancien).unlink(missing_ok=True)
    lignes += [f"  {nom:12} x={x} y={y} {l}×{h}" for nom, (x, y, l, h) in zones.items()]

    # Mise à jour : déjà choisie dans DCS, à la bonne résolution, en fenêtré,
    # rien à régler ni à relancer.
    if inchange and dcs_regle(saved_games, resolution):
        return True, lignes + [Texte("DCS déjà réglé : « {nom} », {largeur}×{hauteur}.",
                                     nom=NOM_AFFICHE, largeur=resolution[0],
                                     hauteur=resolution[1])]

    if not ouvert():
        try:
            copie = regler_options(saved_games, *resolution)
        except (OSError, PasDExport) as e:
            lignes.append(Texte("Réglages de DCS non modifiés ({erreur}). À régler à la main :",
                                erreur=message(e)))
        else:
            return True, lignes + [Texte(
                "DCS réglé : « {nom} », {largeur}×{hauteur}, fenêtré (réglages d'origine "
                "gardés dans {copie}).", nom=NOM_AFFICHE, largeur=resolution[0],
                hauteur=resolution[1], copie=copie.name)]
    else:
        lignes.append(Texte("DCS est ouvert : il réécrira ses réglages en quittant. "
                            "À régler dans DCS :"))
    return True, lignes + [
        Texte("  Options → Système → Moniteurs : « {nom} »", nom=NOM_AFFICHE),
        Texte("  Résolution : {largeur}×{hauteur}, « Plein écran » décoché",
              largeur=resolution[0], hauteur=resolution[1]),
        Texte("puis relancer DCS.")]


def retirer_ecrans(saved_games: Path, ouvert: Callable[[], bool] = dcs_ouvert) -> List[str]:
    """Remet l'affichage d'avant la tablette, puis retire « Tablette DCS »."""
    fichier = saved_games / "Config" / "MonitorSetup" / NOM_FICHIER
    try:
        choix, _, _ = options_affichage(saved_games)
    except PasDExport:
        choix = ""
    lignes = []
    if choix.lower() in (Path(NOM_FICHIER).stem, NOM_AFFICHE.lower()):
        if ouvert():
            return [Texte("DCS est ouvert : ferme-le puis relance la désinstallation, ou choisis"),
                    Texte("toi-même dans Options → Système → Moniteurs ta configuration d'avant"),
                    Texte("et ta résolution.")]
        try:
            copie = retablir_options(saved_games)
        except (OSError, PasDExport) as e:
            return [Texte("Réglages de DCS non remis ({erreur}). Dans Options → Système, choisis",
                          erreur=message(e)),
                    Texte("« 1 Screen » dans Moniteurs et ta résolution, puis relance la"),
                    Texte("désinstallation pour retirer « {nom} ».", nom=NOM_AFFICHE)]
        lignes.append(Texte("Affichage de DCS remis comme avant la tablette (d'après {copie}).",
                            copie=copie.name))
        # Gardée, elle servirait à une prochaine installation : on reviendrait
        # un jour à une résolution vieille de plusieurs écrans.
        copie.unlink(missing_ok=True)
    for chemin in (fichier, fichier.with_suffix(".lua.precedent")):
        if chemin.exists():
            chemin.unlink()
            lignes.append(Texte("Supprimé : {chemin}", chemin=chemin))
    return lignes


def dossier_bureau() -> Path:
    return dossier_windows(BUREAU) or Path.home() / "Desktop"


def creer_raccourci(cible: Path, dossier: Optional[Path] = None, nom: str = RACCOURCI,
                    description: Optional[str] = None) -> Path:
    """Raccourci « DCS Tablette » vers l'exécutable, sur le bureau : un
    double-clic pour lancer la tablette, avec son icône.

    Windows ne crée un .lnk que par COM : PowerShell s'en charge. Les chemins
    passent par l'environnement, rien à échapper dans la commande.
    """
    lien = (dossier or dossier_bureau()) / nom
    commande = ("$r = (New-Object -ComObject WScript.Shell).CreateShortcut($env:DT_LIEN); "
                "$r.TargetPath = $env:DT_CIBLE; $r.WorkingDirectory = $env:DT_DOSSIER; "
                "$r.IconLocation = $env:DT_CIBLE + ',0'; "
                "$r.Description = $env:DT_DESCRIPTION; $r.Save()")
    environnement = dict(os.environ, DT_LIEN=str(lien), DT_CIBLE=str(cible),
                         DT_DOSSIER=str(cible.parent),
                         DT_DESCRIPTION=str(description or Texte(
                             "Les écrans du cockpit de DCS sur la tablette")))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", commande],
                   env=environnement, capture_output=True, check=True, timeout=60)
    if not lien.exists():
        raise OSError(Texte("PowerShell n'a rien écrit"))
    return lien


# ------------------------------------------------------------ le programme
#
# Installé pour l'utilisateur seul, comme VS Code ou Discord : sans droits
# d'administrateur, et la mise à jour peut y écrire. Le zip s'extrait donc
# n'importe où (Téléchargements convient) : l'installation copie le programme
# à sa place, et le dossier extrait peut ensuite partir. Jusqu'à la 1.8.0, le
# programme restait là où on avait extrait le zip, « là où il restera ».

# Lancé par cmd une fois DCS Tablette fermé (un exécutable qui tourne ne
# peut pas s'effacer). PING pour attendre : sans console, timeout.exe refuse.
EFFACER = r"""@echo off
set "SYS=%SystemRoot%\System32"
:attente
"%SYS%\tasklist.exe" /FI "PID eq %DT_PID%" /NH | "%SYS%\find.exe" "%DT_PID%" >nul
if errorlevel 1 goto efface
"%SYS%\PING.EXE" -n 2 127.0.0.1 >nul
goto attente
:efface
rem Le temps que Desinstaller.bat, qui a lance l'exe, finisse de se lire.
"%SYS%\PING.EXE" -n 3 127.0.0.1 >nul
""" + "".join(
    f'rmdir /s /q "%DT_DOSSIER%\\{nom}" 2>nul\n' if "." not in nom
    else f'del /f /q "%DT_DOSSIER%\\{nom}" 2>nul\n' for nom in LIVRES) + r"""rmdir "%DT_DOSSIER%" 2>nul
(goto) 2>nul & del /f /q "%~f0"
"""


def dossier_programme() -> Path:
    racine = os.environ.get("LOCALAPPDATA")
    return ((Path(racine) if racine else Path.home() / "AppData" / "Local")
            / "Programs" / PROGRAMME)


def dossier_menu() -> Path:
    racine = os.environ.get("APPDATA")
    return dossier_windows(MENU_DEMARRER) or (
        (Path(racine) if racine else Path.home() / "AppData" / "Roaming")
        / "Microsoft" / "Windows" / "Start Menu" / "Programs")


def dossier_demarrage() -> Path:
    racine = os.environ.get("APPDATA")
    return dossier_windows(DEMARRAGE) or (
        (Path(racine) if racine else Path.home() / "AppData" / "Roaming")
        / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup")


def journal_ecrans() -> Path:
    """Ce que la remise en place à l'ouverture de Windows a vu et fait : elle
    n'a pas de fenêtre pour le dire."""
    return fichier_choix().parent / "ecrans.log"


def ecrans_au_demarrage(dossier: Path) -> Path:
    """Le raccourci du dossier Démarrage : à chaque ouverture de Windows,
    DCS-Tablette-Ecrans.exe remet l'écran virtuel et les réglages de DCS en
    place, sans fenêtre, avant que DCS soit lancé. Au redémarrage, une mise à
    jour du pilote de l'écran virtuel ou de Windows peut le changer de
    définition ou de place, et DCS s'étendrait sur un écran du pilote.
    Désactivable dans Gestionnaire des tâches → Applications de démarrage."""
    return creer_raccourci(dossier / EXE_ECRANS, dossier_demarrage(), RACCOURCI_ECRANS,
                           Texte("Remet l'écran virtuel et les réglages de DCS en place pour "
                                 "DCS Tablette"))


def meme_fichier(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def copier_programme(source: Path, cible: Path) -> bool:
    """Copie dans `cible` ce que le zip a posé dans `source`. False s'il y est déjà."""
    if meme_fichier(source, cible):
        return False
    cible.mkdir(parents=True, exist_ok=True)
    for nom in LIVRES:
        de = source / nom
        if de.is_dir():
            shutil.copytree(de, cible / nom, dirs_exist_ok=True)
        elif de.is_file():
            shutil.copy2(de, cible / nom)
    return True


def exe_installe(courant: Optional[Path] = None,
                 dossier: Optional[Path] = None) -> Optional[Path]:
    """Le DCS-Tablette.exe installé, s'il existe et n'est pas celui qui
    tourne : lancé depuis le dossier extrait du zip, c'est lui qu'on démarre
    — c'est aussi lui que les mises à jour tiennent à jour."""
    exe = (dossier or dossier_programme()) / EXE
    courant = courant or Path(sys.executable)
    return exe if exe.is_file() and not meme_fichier(exe, courant) else None


def lancer(exe: Path, arguments: Sequence[str] = ()) -> None:
    """DCS Tablette dans sa propre fenêtre."""
    subprocess.Popen([str(exe), *arguments], cwd=str(exe.parent), close_fds=True,
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))


def valeurs_windows(dossier: Path, version: str = VERSION) -> Dict[str, object]:
    """L'entrée de Paramètres → Applications installées."""
    exe = dossier / EXE
    return {"DisplayName": "DCS Tablette", "DisplayVersion": version,
            "Publisher": "led5014", "DisplayIcon": f"{exe},0",
            "InstallLocation": str(dossier), "URLInfoAbout": DEPOT,
            "UninstallString": f'"{exe}" desinstaller --attendre',
            "NoModify": 1, "NoRepair": 1}


def enregistrer(dossier: Path) -> None:
    """Inscrit, ou remet à jour, l'entrée de DCS Tablette dans Applications
    installées. Sous HKEY_CURRENT_USER : pas besoin d'administrateur."""
    import winreg
    taille = sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file()) // 1024
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, CLE_WINDOWS, 0,
                            winreg.KEY_SET_VALUE) as cle:
        for nom, valeur in dict(valeurs_windows(dossier), EstimatedSize=taille).items():
            winreg.SetValueEx(cle, nom, 0, winreg.REG_DWORD if isinstance(valeur, int)
                              else winreg.REG_SZ, valeur)


def oublier() -> bool:
    """Retire l'entrée d'Applications installées. True si elle y était."""
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CLE_WINDOWS)
        return True
    except OSError:
        return False


def tenir_a_jour(exe: Path) -> List[str]:
    """À chaque lancement de l'exécutable : l'entrée de Windows à la version
    qui tourne (celle d'une mise à jour comprise), le raccourci du menu
    Démarrer s'il manque (installé avant la 1.9.0), et la remise en place des
    écrans à l'ouverture de Windows (avant la 1.11.0) — une fois : retirée à
    la main, elle ne revient pas. Ne lève jamais."""
    lignes = []
    try:
        enregistrer(exe.parent)
    except (OSError, ImportError) as e:
        lignes.append(Texte("Entrée dans Applications installées non mise à jour ({erreur}).",
                            erreur=e))
    if not (dossier_menu() / RACCOURCI).exists():
        try:
            creer_raccourci(exe, dossier_menu())
            lignes.append(Texte("Raccourci « DCS Tablette » ajouté au menu Démarrer."))
        except (OSError, subprocess.SubprocessError):
            pass
    choix = lire_choix()
    if (exe.parent / EXE_ECRANS).is_file() and not choix.get("demarrage"):
        try:
            if not (dossier_demarrage() / RACCOURCI_ECRANS).exists():
                ecrans_au_demarrage(exe.parent)
                lignes.append(Texte("Écrans remis en place à chaque ouverture de Windows "
                                    "(dossier Démarrage)."))
            ecrire_choix(dict(choix, demarrage=True))
        except (OSError, subprocess.SubprocessError):
            pass                        # au prochain lancement
    return lignes


def installer_programme(demander: Callable[[str], Optional[str]],
                        autres: Callable[[], int]) -> Path:
    """Le programme à sa place, ses deux raccourcis et son entrée dans
    Windows. Rend l'exe installé, ou celui qui tourne si la copie a échoué."""
    source, cible = Path(sys.executable).parent, dossier_programme()
    exe = cible / EXE
    if not meme_fichier(source, cible):
        # Un DCS Tablette ouvert depuis l'installation tient ses fichiers.
        while autres():
            reponse = demander("  " + Texte("DCS Tablette est ouvert. Ferme sa fenêtre, puis "
                                            "appuie sur Entrée (ou tape p pour passer) : "))
            if reponse is None or reponse.strip().lower() == "p":
                break
        try:
            copier_programme(source, cible)
            print("\n" + Texte("Programme installé dans {dossier}.", dossier=cible))
            print(Texte("Le dossier extrait du zip ne sert plus : il peut être supprimé."))
        except OSError as e:
            print("\n" + Texte("Programme non copié dans {dossier} ({erreur}) : il reste ici, "
                               "{source}.", dossier=cible, erreur=e, source=source))
            exe = Path(sys.executable)
    raccourcis = (
        (dossier_bureau(), lambda e: Texte("Raccourci sur le bureau non créé ({erreur}).",
                                           erreur=e)),
        (dossier_menu(), lambda e: Texte("Raccourci dans le menu Démarrer non créé "
                                         "({erreur}).", erreur=e)))
    for dossier, echec in raccourcis:
        try:
            creer_raccourci(exe, dossier)
        except (OSError, subprocess.SubprocessError) as e:
            print(echec(e))
    if (exe.parent / EXE_ECRANS).is_file():
        try:
            ecrans_au_demarrage(exe.parent)
        except (OSError, subprocess.SubprocessError) as e:
            print(Texte("Remise en place des écrans à l'ouverture de Windows non posée "
                        "({erreur}).", erreur=e))
    try:
        enregistrer(exe.parent)
    except OSError as e:
        print(Texte("Entrée dans Applications installées non créée ({erreur}).", erreur=e))
    return exe


def effacer_programme_apres(dossier: Path) -> None:
    """Efface les fichiers du programme (LIVRES, rien d'autre) une fois DCS
    Tablette fermé, puis le dossier s'il est alors vide."""
    from .mise_a_jour import commande
    script = Path(tempfile.gettempdir()) / "dcs-tablette-desinstallation.bat"
    script.write_text(EFFACER.replace("\n", "\r\n"), encoding="ascii")
    subprocess.Popen(commande(script), close_fds=True,
                     env=dict(os.environ, DT_PID=str(os.getpid()), DT_DOSSIER=str(dossier)),
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def demander(question: str) -> Optional[str]:
    """La réponse tapée dans la console, None si personne ne peut répondre."""
    try:
        return input(question)
    except (EOFError, OSError):
        return None


A_LA_MAIN_RANGER = (
    Texte("  À la main : Paramètres → Système → Écran, glisser cet écran sous le principal"),
    Texte("  (ou à droite de l'écran virtuel) : aucun écran à gauche ni au-dessus du principal."))


def ecran_de_dcs(ecrans: Sequence, demander: Callable[[str], Optional[str]]) -> bool:
    """DCS s'affiche sur l'écran principal de Windows. Plusieurs écrans réels :
    on le dit et on demande si c'est le bon ; sinon, la marche à suivre, et
    l'installation s'arrête là — tout le reste en dépend. Sans réponse
    possible (pas de console), on continue."""
    from .ecran_virtuel import accepte
    reels = [e for e in ecrans if e.actif and not e.virtuel]
    principal = next((e for e in reels if e.principal), None)
    if principal is None or len(reels) < 2:
        return True
    print("\n" + Texte("DCS s'affichera sur l'écran principal de Windows ({largeur}×{hauteur}, "
                       "{frequence} Hz) :", largeur=principal.largeur,
                       hauteur=principal.hauteur, frequence=principal.frequence))
    print(Texte("celui où « En faire mon écran principal » est coché dans Paramètres → Écran."))
    reponse = demander(Texte("C'est bien l'écran où vous voulez DCS ? [O/n] "))
    if reponse is None or accepte(reponse):
        return True
    print(Texte("Paramètres → Système → Écran : cliquer l'écran voulu pour DCS, cocher"))
    print(Texte("« En faire mon écran principal », puis relancer Installer.bat."))
    return False


def ranger_avec_accord(lister_ecrans: Callable[[], list],
                       demander: Callable[[str], Optional[str]]) -> bool:
    """Un écran réel à gauche ou au-dessus du principal : DCS partirait de lui.
    On propose de le ranger hors de la fenêtre de DCS (`rangement`). Rend
    True si le pilote a dit oui : retenu, le diagnostic et l'ouverture de
    Windows le rangeront de nouveau si Windows le remet à cette place."""
    from . import ecran_virtuel
    try:
        actifs = [e for e in lister_ecrans() if e.actif]
    except OSError:
        return False
    places = rangement([(e.x, e.y, e.largeur, e.hauteur, e.principal, e.virtuel)
                        for e in actifs])
    if not places:
        return False
    principal = next(e for e in actifs if e.principal)
    noms = [Texte("votre écran {largeur}×{hauteur}", largeur=m[2], hauteur=m[3])
            for m, _, _ in places]
    print("\n" + Texte("À gauche ou au-dessus de l'écran principal : {ecrans}.", ecrans=noms))
    print(Texte("DCS ouvre sa fenêtre au coin haut gauche du bureau entier : sa vue partirait"))
    print(Texte("de là, et les écrans du cockpit ne tomberaient plus à leur place."))
    if places[0][2] >= principal.y + principal.hauteur:
        print(Texte("DCS Tablette peut ranger {ecrans} sous la fenêtre de DCS (la souris y "
                    "passera par le bas).", ecrans=noms))
    else:
        print(Texte("DCS Tablette peut ranger {ecrans} à droite de la fenêtre de DCS (la "
                    "souris y passera par la droite).", ecrans=noms))
    if not ecran_virtuel.accepte(demander(Texte("  Ranger maintenant ? [O/n] "))):
        for ligne in A_LA_MAIN_RANGER:
            print(ligne)
        return False
    erreur = ecran_virtuel.ranger(lister_ecrans)
    if erreur:
        print(Texte("  Écrans non rangés : {erreur}.", erreur=erreur))
        for ligne in A_LA_MAIN_RANGER:
            print(ligne)
    else:
        print(Texte("  Rangé : {ecrans}.", ecrans=noms))
    return True


def installer(saved_games: Path, essai: bool = False,
              demander: Callable[[str], Optional[str]] = demander,
              ouvert: Callable[[], bool] = dcs_ouvert,
              lister_ecrans: Optional[Callable[[], list]] = None,
              chemin_choix: Optional[Path] = None,
              demarrer: bool = False) -> int:
    """`DCS-Tablette.exe installer` : écran virtuel, scripts, écrans de DCS,
    programme à sa place et raccourcis, puis, si `demarrer` et que tout est
    prêt, DCS Tablette lui-même. Fait tout ce qu'il peut, et dit à la main
    ce qu'il n'a pas pu.

    Part de ce que le pilote a déjà : ses écrans (un écran réel n'est jamais
    pris sans son accord, l'écran virtuel va à droite ou dessous selon la
    place), et sa configuration d'écrans de DCS (si elle exporte déjà les
    écrans du cockpit, on propose de la garder). Le choix est retenu pour la
    console de diagnostic (`ecrire_choix`).
    """
    from . import ecran_virtuel
    if not saved_games.is_dir():
        print(Texte("Dossier de DCS introuvable ({dossier}).", dossier=saved_games))
        print(Texte("Lance DCS une fois pour qu'il le crée, puis recommence."))
        return 1
    lister_ecrans = lister_ecrans or ecran_virtuel.lister
    print(Texte("Dossier de DCS : {dossier}", dossier=saved_games))

    # Ce que le pilote a déjà, avant de toucher à quoi que ce soit.
    try:
        ecrans = lister_ecrans()
    except OSError:
        ecrans = []
    print("\n" + Texte("Vos écrans :"))
    for ligne in ecran_virtuel.decrire(ecrans) or [Texte("(illisibles)")]:
        print("  " + ligne)
    try:
        nom, largeur, hauteur = options_affichage(saved_games)
        print(Texte("DCS : configuration « {nom} », {largeur}×{hauteur}, {mode}", nom=nom,
                    largeur=largeur, hauteur=hauteur,
                    mode=Texte("plein écran") if plein_ecran(saved_games) else Texte("fenêtré")))
    except PasDExport as e:
        print(Texte("DCS : {erreur}", erreur=message(e)))
    if not ecran_de_dcs(ecrans, demander):
        return 1

    choix: Dict = {"mode": "essai" if essai else "second_ecran", "physique": False}
    existante = None if essai else configuration_existante(saved_games)
    if existante:
        nom, zones = existante
        print("\n" + Texte("DCS exporte déjà {nombre} écrans du cockpit avec votre "
                           "configuration « {nom} » : {zones}.", nombre=len(zones), nom=nom,
                           zones=sorted(zones)))
        print(Texte("La tablette peut les prendre là où ils sont, sans toucher à vos écrans "
                    "ni à DCS."))
        if ecran_virtuel.accepte(demander(Texte("Garder votre configuration ? [O/n] "))):
            choix = {"mode": "existante", "configuration": nom}

    etapes = 3 if choix["mode"] == "second_ecran" else 2
    pret = True
    if choix["mode"] == "second_ecran":
        print("\n" + Texte("{etape}/{etapes}  Écran virtuel", etape=1, etapes=etapes))
        resultat = ecran_virtuel.preparer(lambda ligne: print("  " + ligne),
                                          lambda question: demander("  " + question))
        if resultat is None:
            print(Texte("  Sans écran pour eux, la tablette marche quand même en mode essai : les"))
            print(Texte("  écrans du cockpit sont dessinés en bas de la vue, par-dessus le "
                        "cockpit."))
            if ecran_virtuel.oui(demander(Texte("  Passer en mode essai ? [o/N] "))):
                choix["mode"] = "essai"
            else:
                pret = False
        else:
            choix["physique"] = resultat == "physique"
    if choix["mode"] != "existante" and pret and ranger_avec_accord(lister_ecrans, demander):
        choix["ranger"] = True
    ecrire_choix(choix, chemin_choix)
    print("\n" + Texte("{etape}/{etapes}  Scripts de la tablette", etape=etapes - 1,
                       etapes=etapes))
    for ligne in installer_scripts(saved_games):
        print("  " + ligne)
    print("\n" + Texte("{etape}/{etapes}  Écrans de DCS", etape=etapes, etapes=etapes))
    if choix["mode"] == "existante":
        print(Texte("  Votre configuration « {nom} » est gardée : rien à changer.",
                    nom=choix["configuration"]))
        complet = True
        if plein_ecran(saved_games):
            print(Texte("  Mais DCS est en plein écran, que la tablette ne voit pas : dans DCS,"))
            print(Texte("  Options → Système, décocher « Plein écran », puis relancer DCS."))
    elif not pret:
        print(Texte("  Écran virtuel pas prêt : la configuration d'écrans de DCS attendra."))
        print(Texte("  Relancer Installer.bat une fois l'écran virtuel en place."))
        complet = False
    else:
        # DCS réécrit options.lua en quittant : réglé DCS ouvert, le choix
        # « Tablette DCS » serait perdu. On attend qu'il soit fermé.
        while ouvert():
            reponse = demander(Texte("  DCS est ouvert. Ferme-le, puis appuie sur Entrée "
                                     "(ou tape p pour passer) : "))
            if reponse is None or reponse.strip().lower() == "p":
                break
        # Relus : l'écran virtuel vient peut-être d'arriver ou de bouger.
        try:
            actuels = [(e.x, e.y, e.largeur, e.hauteur, e.principal, e.virtuel)
                       for e in lister_ecrans() if e.actif]
        except OSError:
            actuels = None
        complet, lignes = configurer_ecrans(saved_games, choix["mode"] == "essai", actuels,
                                            ouvert, physique=choix["physique"])
        for ligne in lignes:
            print("  " + ligne)
    a_lancer, exe = "DCS-Tablette.exe", None
    # Depuis le code source, ni copie ni raccourci : ils pointeraient vers Python.
    if getattr(sys, "frozen", False):
        exe = installer_programme(demander, autres_instances)
        a_lancer = Texte("« DCS Tablette » (bureau ou menu Démarrer)")
    if complet and demarrer and exe and not autres_instances():
        lancer(exe)
        print("\n" + Texte("Installation terminée. DCS Tablette démarre dans sa fenêtre : "
                           "ouvre sur la tablette l'adresse qu'il affiche. Les fois suivantes, "
                           "lance {programme}.", programme=a_lancer))
    elif complet:
        print("\n" + Texte("Installation terminée. Lance {programme} et ouvre sur la tablette "
                           "l'adresse qu'il affiche.", programme=a_lancer))
    else:
        print("\n" + Texte("Scripts installés ; les écrans restent à régler (voir ci-dessus, "
                           "et LISEZ-MOI.txt, « À la main »)."))
    return 0 if complet else 1


def autres_instances() -> int:
    """Combien d'autres DCS-Tablette.exe tournent : le serveur resté ouvert
    pendant qu'on désinstalle avec le même exécutable."""
    try:
        sortie = subprocess.run(["tasklist", "/FI", "IMAGENAME eq DCS-Tablette.exe",
                                 "/FO", "CSV", "/NH"], capture_output=True, text=True,
                                errors="replace", timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    pids = re.findall(r'^"[^"]*","(\d+)"', sortie, re.M)
    return sum(int(p) != os.getpid() for p in pids)


def desinstaller(saved_games: Path, demander: Callable[[str], Optional[str]] = demander,
                 autres: Callable[[], int] = autres_instances, attendre: bool = False) -> int:
    """`DCS-Tablette.exe desinstaller` : l'inverse d'`installer`, programme
    compris. `attendre` : lancé par Paramètres → Applications installées, la
    fenêtre se fermerait avant qu'on ait pu la lire."""
    while autres():
        reponse = demander(Texte("  DCS Tablette est encore ouvert. Ferme sa fenêtre, puis "
                                 "appuie sur Entrée (ou tape p pour passer) : "))
        if reponse is None or reponse.strip().lower() == "p":
            break
    lignes = desinstaller_scripts(saved_games) + retirer_ecrans(saved_games)
    for chemin in (dossier_bureau() / RACCOURCI, dossier_menu() / RACCOURCI,
                   dossier_demarrage() / RACCOURCI_ECRANS, fichier_choix(), journal_ecrans(),
                   fichier_langue()):
        if chemin.exists():
            chemin.unlink()
            lignes.append(Texte("Supprimé : {chemin}", chemin=chemin))
    fige = getattr(sys, "frozen", False)
    if fige and oublier():
        lignes.append(Texte("Retiré de Paramètres → Applications installées."))
    for ligne in lignes or [Texte("Rien à retirer : la tablette n'était pas installée.")]:
        print("  " + ligne)
    if fige:
        effacer_programme_apres(Path(sys.executable).parent)
        print("\n" + Texte("Le programme s'efface dès que cette fenêtre se ferme."))
    else:
        print("\n" + Texte("On peut maintenant supprimer le dossier de DCS Tablette."))
    print(Texte("L'écran virtuel reste installé : il peut servir à autre chose. Pour le "
                "retirer :"))
    print(Texte("Gestionnaire de périphériques → Cartes graphiques → Virtual Display Driver,"))
    print(Texte("clic droit → Désinstaller l'appareil."))
    if attendre:
        demander("\n" + Texte("Appuie sur Entrée pour fermer cette fenêtre. "))
    return 0
