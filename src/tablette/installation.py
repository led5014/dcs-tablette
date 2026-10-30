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

import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from .capture import moniteurs
from .config import BUREAU, dossier_windows
from .ecrans_dcs import (NOM_AFFICHE, NOM_FICHIER, PasDExport, disposition_essai,
                         disposition_second_ecran, generer, options_affichage,
                         regler_options, retablir_options)

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


def configurer_ecrans(saved_games: Path, essai: bool = False,
                      ecrans: Optional[Sequence[Moniteur]] = None,
                      ouvert: Callable[[], bool] = dcs_ouvert) -> Tuple[bool, List[str]]:
    """Écrit « Tablette DCS » et, DCS fermé, la sélectionne dans options.lua.

    Second écran (le bon usage) : la vue reste sur l'écran principal, les
    écrans exportés occupent celui qui le touche à droite, aligné en haut —
    écran virtuel ou prise HDMI factice. DCS s'étend sur les deux. Essai : un
    seul écran, les écrans exportés dessinés en bas, par-dessus la vue.

    DCS ouvert, options.lua n'est pas touché : DCS le réécrit en quittant et
    effacerait la modification. On dit quoi régler à la place.
    """
    ecrans = moniteurs() if ecrans is None else ecrans
    principal = next((m for m in ecrans if m[4]), None)
    if not principal:
        return False, ["Écran principal introuvable."]
    px, py, pl, ph, _ = principal
    if essai:
        # La taille de l'ÉCRAN, pas celle réglée dans DCS : après un réglage
        # raté, la résolution de DCS ne dit plus où est le bas de la vue.
        zones = disposition_essai(pl, ph)
        description = "Essai : ecrans exportes en bas de l'ecran unique"
        resolution = (pl, ph)
    else:
        second = next((m for m in ecrans if not m[4] and m[0] == px + pl and m[1] == py), None)
        if second is None:
            return False, [
                "Pas de second écran à droite de l'écran principal, aligné en haut.",
                "Il en faut un que personne ne regarde, pour que DCS y dessine les écrans",
                "exportés au lieu de les poser sur la vue :",
                f"  - écran virtuel : Virtual Display Driver, gratuit — {VDD}",
                "  - ou une prise HDMI factice.",
                "Installer.bat installe et place l'écran virtuel lui-même. À la main :",
                "Paramètres → Système → Écran, « Étendre ces affichages », le glisser à",
                "droite du principal, bords du haut alignés, puis relancer l'installation."]
        _, _, sl, sh, _ = second
        zones = disposition_second_ecran(pl, ph, sl, sh)
        description = "Vue sur l'ecran principal, ecrans exportes sur le second"
        resolution = (pl + sl, max(ph, sh))

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

    # Mise à jour : déjà choisie dans DCS, à la bonne résolution, rien à
    # régler ni à relancer.
    try:
        choix, largeur, hauteur = options_affichage(saved_games)
        deja = (choix.lower() in (Path(NOM_FICHIER).stem, NOM_AFFICHE.lower())
                and (largeur, hauteur) == resolution)
    except PasDExport:
        deja = False
    if inchange and deja:
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
              ouvert: Callable[[], bool] = dcs_ouvert) -> int:
    """`DCS-Tablette.exe installer` : écran virtuel, scripts, écrans de DCS,
    raccourci. Fait tout ce qu'il peut, et dit à la main ce qu'il n'a pas pu."""
    if not saved_games.is_dir():
        print(f"Dossier de DCS introuvable ({saved_games}).")
        print("Lance DCS une fois pour qu'il le crée, puis recommence.")
        return 1
    etapes = 2 if essai else 3
    print(f"Dossier de DCS : {saved_games}")
    pret = True
    if not essai:
        from .ecran_virtuel import preparer
        print(f"\n1/{etapes}  Écran virtuel")
        pret = preparer(lambda ligne: print("  " + ligne),
                        lambda question: demander("  " + question))
    print(f"\n{etapes - 1}/{etapes}  Scripts de la tablette")
    for ligne in installer_scripts(saved_games):
        print("  " + ligne)
    print(f"\n{etapes}/{etapes}  Écrans de DCS")
    if not pret:
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
        complet, lignes = configurer_ecrans(saved_games, essai, ouvert=ouvert)
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


def desinstaller(saved_games: Path) -> int:
    """`DCS-Tablette.exe desinstaller` : l'inverse d'`installer`."""
    lignes = desinstaller_scripts(saved_games) + retirer_ecrans(saved_games)
    lien = dossier_bureau() / RACCOURCI
    if lien.exists():
        lien.unlink()
        lignes.append(f"Supprimé : {lien}")
    for ligne in lignes or ["Rien à retirer : la tablette n'était pas installée."]:
        print("  " + ligne)
    print("\nOn peut maintenant supprimer le dossier de DCS Tablette.")
    print("L'écran virtuel reste installé : il peut servir à autre chose. Pour le retirer :")
    print("Gestionnaire de périphériques → Cartes graphiques → Virtual Display Driver,")
    print("clic droit → Désinstaller l'appareil.")
    return 0
