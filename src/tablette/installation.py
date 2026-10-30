"""Installation dans DCS : les scripts Lua, la ligne d'Export.lua, les écrans.

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
- le raccourci « DCS Tablette » sur le bureau, depuis l'exécutable seulement.
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
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .capture import moniteurs
from .config import BUREAU, dossier_windows
from .ecrans_dcs import (NOM_AFFICHE, NOM_FICHIER, PasDExport, disposition, disposition_essai,
                         fichier_actif, generer, lire_zones, options_affichage,
                         plein_ecran, regler_options, retablir_options)

SCRIPTS = ("DCS-Tablette-Export.lua", "DCS-Tablette-Appareils.lua")
RACCOURCI = "DCS Tablette.lnk"
ENTETE = "-- DCS Tablette -- ecrans et boutons du cockpit sur l'iPad"
LIGNE = ("pcall(function() local dt_lfs=require('lfs'); "
         "dofile(dt_lfs.writedir()..[[Scripts\\DCS-Tablette-Export.lua]]) end)")
ANCIENS = ("tablette_hornet.lua", "tablette_hornet.lua.precedent")
VDD = "https://github.com/VirtualDrivers/Virtual-Display-Driver"

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
        lignes.append(f"Copié : {dossier / nom}")
    export = dossier / "Export.lua"
    if est_installe(saved_games):
        return lignes + ["Export.lua charge déjà la tablette."]
    brut = export.read_bytes() if export.exists() else b""
    if export.exists():
        copie = export.with_name(f"Export.lua.avant-tablette-{date.today():%Y%m%d}")
        shutil.copyfile(export, copie)
        lignes.append(f"Copie de l'ancien Export.lua : {copie.name}")
    with open(export, "ab") as f:
        if brut and not brut.endswith(b"\n"):
            f.write(b"\n")
        f.write(f"{ENTETE}\n{LIGNE}\n".encode("ascii"))
    return lignes + ["Export.lua : ligne de la tablette ajoutée."]


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
            lignes.append(f"Export.lua : ligne de la tablette retirée (copie : {copie.name}).")
    for nom in SCRIPTS:
        chemin = dossier / nom
        if chemin.exists():
            chemin.unlink()
            lignes.append(f"Supprimé : {chemin}")
    return lignes


# ------------------------------------------------------------ où, selon les écrans
#
# La fenêtre de DCS part du coin haut gauche de l'écran principal et s'étend
# vers la droite et vers le bas : DCS ne dessine ni à gauche ni au-dessus du
# principal. Les écrans exportés vont donc sur un écran collé à DROITE du
# principal (bords du haut alignés) ou DESSOUS (bords de gauche alignés), et
# la fenêtre de DCS couvre le principal et cet écran-là. Elle ne doit couvrir
# AUCUN autre écran : il resterait noir pendant le vol. Un écran réel à
# droite du principal fait donc passer l'écran virtuel dessous.

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
        return False, ["Écran principal introuvable."]
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
                "Pas d'écran libre collé à droite ou sous l'écran principal.",
                "Il en faut un que personne ne regarde, pour que DCS y dessine les écrans",
                "exportés au lieu de les poser sur la vue :",
                f"  - écran virtuel : Virtual Display Driver, gratuit — {VDD}",
                "  - ou une prise HDMI factice.",
                "Installer.bat installe et place l'écran virtuel lui-même. À la main :",
                "Paramètres → Système → Écran, « Étendre ces affichages », le glisser à",
                "droite du principal (bords du haut alignés) ou dessous (bords de gauche",
                "alignés), là où aucun autre écran ne se trouve, puis relancer l'installation."]
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
        lignes = [f"Inchangé : {fichier}"]
    else:
        if fichier.exists():
            fichier.replace(fichier.with_suffix(".lua.precedent"))
        fichier.write_text(texte, encoding="ascii")
        lignes = [f"Écrit : {fichier}"]
    for ancien in ANCIENS:                       # l'ancienne « Tablette Hornet »
        (dossier / ancien).unlink(missing_ok=True)
    lignes += [f"  {nom:12} x={x} y={y} {l}×{h}" for nom, (x, y, l, h) in zones.items()]

    # Mise à jour : déjà choisie dans DCS, à la bonne résolution, en fenêtré,
    # rien à régler ni à relancer.
    if inchange and dcs_regle(saved_games, resolution):
        return True, lignes + [f"DCS déjà réglé : « {NOM_AFFICHE} », "
                               f"{resolution[0]}×{resolution[1]}."]

    if not ouvert():
        try:
            copie = regler_options(saved_games, *resolution)
        except (OSError, PasDExport) as e:
            lignes.append(f"Réglages de DCS non modifiés ({e}). À régler à la main :")
        else:
            return True, lignes + [
                f"DCS réglé : « {NOM_AFFICHE} », {resolution[0]}×{resolution[1]}, fenêtré "
                f"(réglages d'origine gardés dans {copie.name})."]
    else:
        lignes.append("DCS est ouvert : il réécrira ses réglages en quittant. À régler dans DCS :")
    return True, lignes + [
        "  Options → Système → Moniteurs : « " + NOM_AFFICHE + " »",
        f"  Résolution : {resolution[0]}×{resolution[1]}, « Plein écran » décoché",
        "puis relancer DCS."]


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
            return ["DCS est ouvert : ferme-le puis relance la désinstallation, ou choisis",
                    "toi-même dans Options → Système → Moniteurs ta configuration d'avant",
                    "et ta résolution."]
        try:
            copie = retablir_options(saved_games)
        except (OSError, PasDExport) as e:
            return [f"Réglages de DCS non remis ({e}). Dans Options → Système, choisis",
                    "« 1 Screen » dans Moniteurs et ta résolution, puis relance la",
                    "désinstallation pour retirer « Tablette DCS »."]
        lignes.append(f"Affichage de DCS remis comme avant la tablette (d'après {copie.name}).")
        # Gardée, elle servirait à une prochaine installation : on reviendrait
        # un jour à une résolution vieille de plusieurs écrans.
        copie.unlink(missing_ok=True)
    for chemin in (fichier, fichier.with_suffix(".lua.precedent")):
        if chemin.exists():
            chemin.unlink()
            lignes.append(f"Supprimé : {chemin}")
    return lignes


def dossier_bureau() -> Path:
    return dossier_windows(BUREAU) or Path.home() / "Desktop"


def creer_raccourci(cible: Path, dossier: Optional[Path] = None) -> Path:
    """Raccourci « DCS Tablette » vers l'exécutable, sur le bureau : un
    double-clic pour lancer la tablette, avec son icône.

    Windows ne crée un .lnk que par COM : PowerShell s'en charge. Les chemins
    passent par l'environnement, rien à échapper dans la commande.
    """
    lien = (dossier or dossier_bureau()) / RACCOURCI
    commande = ("$r = (New-Object -ComObject WScript.Shell).CreateShortcut($env:DT_LIEN); "
                "$r.TargetPath = $env:DT_CIBLE; $r.WorkingDirectory = $env:DT_DOSSIER; "
                "$r.IconLocation = $env:DT_CIBLE + ',0'; "
                "$r.Description = 'Les ecrans du cockpit de DCS sur la tablette'; $r.Save()")
    environnement = dict(os.environ, DT_LIEN=str(lien), DT_CIBLE=str(cible),
                         DT_DOSSIER=str(cible.parent))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", commande],
                   env=environnement, capture_output=True, check=True, timeout=60)
    if not lien.exists():
        raise OSError("PowerShell n'a rien écrit")
    return lien


def demander(question: str) -> Optional[str]:
    """La réponse tapée dans la console, None si personne ne peut répondre."""
    try:
        return input(question)
    except (EOFError, OSError):
        return None


def installer(saved_games: Path, essai: bool = False,
              demander: Callable[[str], Optional[str]] = demander,
              ouvert: Callable[[], bool] = dcs_ouvert,
              lister_ecrans: Optional[Callable[[], list]] = None,
              chemin_choix: Optional[Path] = None) -> int:
    """`DCS-Tablette.exe installer` : écran virtuel, scripts, écrans de DCS,
    raccourci. Fait tout ce qu'il peut, et dit à la main ce qu'il n'a pas pu.

    Part de ce que le pilote a déjà : ses écrans (un écran réel n'est jamais
    pris sans son accord, l'écran virtuel va à droite ou dessous selon la
    place), et sa configuration d'écrans de DCS (si elle exporte déjà les
    écrans du cockpit, on propose de la garder). Le choix est retenu pour la
    console de diagnostic (`ecrire_choix`).
    """
    from . import ecran_virtuel
    if not saved_games.is_dir():
        print(f"Dossier de DCS introuvable ({saved_games}).")
        print("Lance DCS une fois pour qu'il le crée, puis recommence.")
        return 1
    lister_ecrans = lister_ecrans or ecran_virtuel.lister
    print(f"Dossier de DCS : {saved_games}")

    # Ce que le pilote a déjà, avant de toucher à quoi que ce soit.
    try:
        ecrans = lister_ecrans()
    except OSError:
        ecrans = []
    print("\nVos écrans :")
    for ligne in ecran_virtuel.decrire(ecrans) or ["(illisibles)"]:
        print("  " + ligne)
    try:
        nom, largeur, hauteur = options_affichage(saved_games)
        print(f"DCS : configuration « {nom} », {largeur}×{hauteur}, "
              + ("plein écran" if plein_ecran(saved_games) else "fenêtré"))
    except PasDExport as e:
        print(f"DCS : {e}")

    choix: Dict = {"mode": "essai" if essai else "second_ecran", "physique": False}
    existante = None if essai else configuration_existante(saved_games)
    if existante:
        nom, zones = existante
        print(f"\nDCS exporte déjà {len(zones)} écrans du cockpit avec votre configuration "
              f"« {nom} » : {', '.join(sorted(zones))}.")
        print("La tablette peut les prendre là où ils sont, sans toucher à vos écrans ni à DCS.")
        if ecran_virtuel.accepte(demander("Garder votre configuration ? [O/n] ")):
            choix = {"mode": "existante", "configuration": nom}

    etapes = 3 if choix["mode"] == "second_ecran" else 2
    pret = True
    if choix["mode"] == "second_ecran":
        print(f"\n1/{etapes}  Écran virtuel")
        resultat = ecran_virtuel.preparer(lambda ligne: print("  " + ligne),
                                          lambda question: demander("  " + question))
        if resultat is None:
            print("  Sans écran pour eux, la tablette marche quand même en mode essai : les")
            print("  écrans du cockpit sont dessinés en bas de la vue, par-dessus le cockpit.")
            if ecran_virtuel.oui(demander("  Passer en mode essai ? [o/N] ")):
                choix["mode"] = "essai"
            else:
                pret = False
        else:
            choix["physique"] = resultat == "physique"
    ecrire_choix(choix, chemin_choix)
    print(f"\n{etapes - 1}/{etapes}  Scripts de la tablette")
    for ligne in installer_scripts(saved_games):
        print("  " + ligne)
    print(f"\n{etapes}/{etapes}  Écrans de DCS")
    if choix["mode"] == "existante":
        print(f"  Votre configuration « {choix['configuration']} » est gardée : rien à changer.")
        complet = True
        if plein_ecran(saved_games):
            print("  Mais DCS est en plein écran, que la tablette ne voit pas : dans DCS,")
            print("  Options → Système, décocher « Plein écran », puis relancer DCS.")
    elif not pret:
        print("  Écran virtuel pas prêt : la configuration d'écrans de DCS attendra.")
        print("  Relancer Installer.bat une fois l'écran virtuel en place.")
        complet = False
    else:
        # DCS réécrit options.lua en quittant : réglé DCS ouvert, le choix
        # « Tablette DCS » serait perdu. On attend qu'il soit fermé.
        while ouvert():
            reponse = demander("  DCS est ouvert. Ferme-le, puis appuie sur Entrée "
                               "(ou tape p pour passer) : ")
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
    lancer = "DCS-Tablette.exe"
    # Depuis le code source, pas de raccourci : il pointerait vers Python.
    if getattr(sys, "frozen", False):
        try:
            creer_raccourci(Path(sys.executable))
            lancer = "« DCS Tablette » (raccourci posé sur le bureau)"
        except (OSError, subprocess.SubprocessError) as e:
            print(f"\nRaccourci sur le bureau non créé ({e}).")
    if complet:
        print(f"\nInstallation terminée. Lance {lancer} et ouvre sur la tablette "
              "l'adresse qu'il affiche.")
    else:
        print("\nScripts installés ; les écrans restent à régler (voir ci-dessus, et "
              "LISEZ-MOI.txt, « À la main »).")
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
                 autres: Callable[[], int] = autres_instances) -> int:
    """`DCS-Tablette.exe desinstaller` : l'inverse d'`installer`."""
    while autres():
        reponse = demander("  DCS Tablette est encore ouvert. Ferme sa fenêtre, puis appuie "
                           "sur Entrée (ou tape p pour passer) : ")
        if reponse is None or reponse.strip().lower() == "p":
            break
    lignes = desinstaller_scripts(saved_games) + retirer_ecrans(saved_games)
    lien = dossier_bureau() / RACCOURCI
    for chemin in (lien, fichier_choix()):
        if chemin.exists():
            chemin.unlink()
            lignes.append(f"Supprimé : {chemin}")
    for ligne in lignes or ["Rien à retirer : la tablette n'était pas installée."]:
        print("  " + ligne)
    print("\nOn peut maintenant supprimer le dossier de DCS Tablette.")
    print("L'écran virtuel reste installé : il peut servir à autre chose. Pour le retirer :")
    print("Gestionnaire de périphériques → Cartes graphiques → Virtual Display Driver,")
    print("clic droit → Désinstaller l'appareil.")
    return 0
