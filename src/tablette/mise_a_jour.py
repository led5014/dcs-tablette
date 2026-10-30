"""Mettre à jour sans tout réinstaller.

Au lancement, DCS Tablette demande à GitHub la dernière version publiée. S'il
y en a une plus récente et que le pilote le veut, il la télécharge, vérifie
son empreinte SHA-256 (celle que GitHub donne pour le fichier, sinon celle
des notes de version), puis remplace ses propres fichiers et se relance.

Rien d'autre ne bouge : l'écran virtuel, les réglages de DCS, le choix fait
à l'installation, le raccourci du bureau. Les scripts dans DCS sont recopiés
par la console de diagnostic au lancement suivant, et la page de la tablette
se recharge d'elle-même quand la version du serveur change.

Un exécutable qui tourne ne peut pas s'écraser : la copie est faite par un
petit script à part (cmd + robocopy, livrés avec Windows), qui attend que
DCS Tablette soit fermé, copie, puis le relance. Les chemins lui passent par
l'environnement : rien à échapper, accents compris.

Seul moment où DCS Tablette parle à internet : cette demande, au lancement,
4 secondes au plus — hors ligne, il démarre comme avant. DCS ouvert, rien
n'est proposé (la question attendrait une réponse au PC, en plein vol) : le
diagnostic de la tablette signale la nouvelle version. `--sans-mise-a-jour`
supprime la demande.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from . import VERSION

DEPOT = "led5014/dcs-tablette"
API = f"https://api.github.com/repos/{DEPOT}/releases/latest"
DELAI_S = 3
NOM = "DCS-Tablette"

# Pas de bloc entre parenthèses : un « ) » dans un chemin (« DCS-Tablette (1) »,
# nom que Windows donne à un zip téléchargé deux fois) le refermerait. Les
# chemins ne paraissent qu'entre guillemets, où ( ) & sont du texte. Les
# commandes de Windows par leur chemin complet : un find.exe d'un autre
# outil dans le PATH ne répond pas pareil.
REMPLACER = r"""@echo off
title DCS Tablette - mise a jour
set "SYS=%SystemRoot%\System32"
echo Mise a jour de DCS Tablette : on attend qu'il soit ferme...
:attente
"%SYS%\tasklist.exe" /FI "PID eq %DT_PID%" /NH | "%SYS%\find.exe" "%DT_PID%" >nul
if errorlevel 1 goto copie
"%SYS%\timeout.exe" /t 1 /nobreak >nul
goto attente
:copie
echo Copie des nouveaux fichiers...
"%SYS%\Robocopy.exe" "%DT_SOURCE%" "%DT_CIBLE%" /E /R:5 /W:1 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto echec
start "" "%DT_CIBLE%\DCS-Tablette.exe"
rmdir /s /q "%DT_TEMP%" 2>nul
exit /b 0
:echec
echo.
echo La copie a echoue. Extraire a la main le zip telecharge :
echo   "%DT_ZIP%"
echo dans "%DT_CIBLE%"
pause
exit /b 1
"""


def numero(version: str) -> Tuple[int, ...]:
    """« v1.10.2 » → (1, 10, 2) : comparable, contrairement au texte. Trois
    nombres seulement : « 1.5.0-rc1 » n'est pas plus récent que « 1.5.0 »."""
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3])


def derniere_version(ouvrir: Callable = urllib.request.urlopen) -> Optional[Dict]:
    """La dernière version publiée : numéro, adresse du zip, empreinte,
    notes. None si GitHub ne répond pas à temps, répond mal, ou si la
    version n'a pas de zip vérifiable. Ne lève jamais : le serveur doit
    démarrer quoi qu'il arrive."""
    resultat: list = []
    # Dans un fil, borné : le délai d'urlopen ne couvre pas la résolution du
    # nom, qui peut traîner bien plus longtemps sur un réseau capricieux.
    fil = threading.Thread(target=lambda: resultat.append(_lire_publication(ouvrir)),
                           daemon=True)
    fil.start()
    fil.join(DELAI_S + 1)
    return resultat[0] if resultat else None


def _lire_publication(ouvrir: Callable) -> Optional[Dict]:
    requete = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": f"{NOM}/{VERSION}"})
    try:
        with ouvrir(requete, timeout=DELAI_S) as reponse:
            publiee = json.loads(reponse.read().decode("utf-8"))
        return _publication(publiee)
    except Exception:                   # noqa: BLE001 — http.client, JSON tordu…
        return None


def _publication(publiee) -> Optional[Dict]:
    if not isinstance(publiee, dict):
        return None
    version = str(publiee.get("tag_name", "")).lstrip("v")
    nom_zip = f"{NOM}-{version}.zip"
    zip_ = next((a for a in publiee.get("assets", []) if a.get("name") == nom_zip), None)
    if not version or zip_ is None:
        return None
    empreinte = str(zip_.get("digest") or "").removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-f]{64}", empreinte):
        # Pas d'empreinte donnée par GitHub : celle des notes de version.
        notes = re.search(rf"{re.escape(nom_zip)}[\s\S]*?\b([0-9a-f]{{64}})\b",
                          publiee.get("body") or "")
        empreinte = notes.group(1) if notes else ""
    if not empreinte:
        return None
    return {"version": version, "url": zip_["browser_download_url"],
            "empreinte": empreinte, "taille": zip_.get("size", 0),
            "notes": publiee.get("body") or ""}


def plus_recente(publiee: Optional[Dict], actuelle: str = VERSION) -> bool:
    return publiee is not None and numero(publiee["version"]) > numero(actuelle)


def nouveautes(notes: str, lignes: int = 6) -> list:
    """Les premières puces de la section « Nouveau » des notes de version."""
    section = notes.split("## Nouveau", 1)[-1].split("\n## ", 1)[0]
    puces = [re.sub(r"\*\*|`", "", l.strip()[2:]) for l in section.splitlines()
             if l.strip().startswith("- ")]
    return [p if len(p) <= 110 else p[:107] + "…" for p in puces[:lignes]]


def telecharger(publiee: Dict, dossier: Path,
                ouvrir: Callable = urllib.request.urlopen) -> Path:
    """Le zip, vérifié, extrait dans `dossier` ; rend le dossier DCS-Tablette
    qu'il contient. Lève OSError si quoi que ce soit cloche : rien n'est
    alors remplacé."""
    zip_ = dossier / f"{NOM}-{publiee['version']}.zip"
    empreinte = hashlib.sha256()
    with ouvrir(publiee["url"], timeout=60) as reponse, open(zip_, "wb") as f:
        while bloc := reponse.read(1 << 20):
            empreinte.update(bloc)
            f.write(bloc)
    if empreinte.hexdigest() != publiee["empreinte"]:
        raise OSError("le fichier téléchargé n'est pas celui publié (empreinte différente)")
    with zipfile.ZipFile(zip_) as z:
        z.extractall(dossier / "extrait")
    source = dossier / "extrait" / NOM
    if not (source / f"{NOM}.exe").exists():
        raise OSError(f"{NOM}.exe absent du zip")
    return source


def environnement_remplacement(source: Path, cible: Path, dossier: Path,
                               zip_: Path) -> Dict[str, str]:
    return dict(os.environ, DT_PID=str(os.getpid()), DT_SOURCE=str(source),
                DT_CIBLE=str(cible), DT_TEMP=str(dossier), DT_ZIP=str(zip_))


def commande(script: Path) -> str:
    """La ligne qui lance le script. `cmd /c "…"` enlève les guillemets dès
    que le chemin contient & ou ( ) — un nom d'utilisateur « Jean & Marie »
    suffit, %TEMP% est dans son profil — et le coupe en morceaux. Avec /s,
    cmd n'ôte que la paire extérieure : le chemin reste entre guillemets."""
    return f'cmd /s /c ""{script}""'


def lancer_remplacement(source: Path, cible: Path, dossier: Path, zip_: Path) -> None:
    """Le script qui attend la fermeture, copie, relance et fait le ménage
    (le zip et son extraction, dans `dossier`), dans sa propre console."""
    script = Path(tempfile.gettempdir()) / "dcs-tablette-mise-a-jour.bat"
    script.write_text(REMPLACER.replace("\n", "\r\n"), encoding="ascii")
    subprocess.Popen(commande(script),
                     env=environnement_remplacement(source, cible, dossier, zip_),
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                     close_fds=True)


def proposer(afficher: Callable[[str], None], demander: Callable[[str], Optional[str]],
             publiee: Optional[Dict]) -> bool:
    """Au lancement de l'exécutable : une version plus récente (`publiee`,
    lue une seule fois par l'appelant) ? On la propose. Rend True si la mise
    à jour est lancée — DCS Tablette doit alors se fermer pour qu'elle
    remplace ses fichiers."""
    if not getattr(sys, "frozen", False):
        return False                    # depuis le code source : git pull
    if not plus_recente(publiee):
        return False
    afficher(f"Nouvelle version : DCS Tablette {publiee['version']} (vous avez {VERSION}).")
    for puce in nouveautes(publiee["notes"]):
        afficher(f"  - {puce}")
    reponse = demander("Mettre à jour maintenant ? Vos réglages sont gardés. [O/n] ")
    if reponse is None or reponse.strip().lower() not in ("", "o", "oui", "y", "yes"):
        afficher("Pas maintenant : DCS Tablette le reproposera au prochain lancement.\n")
        return False
    taille = publiee.get("taille", 0) / 1e6
    afficher(f"Téléchargement ({taille:.0f} Mo)…" if taille else "Téléchargement…")
    dossier = Path(tempfile.mkdtemp(prefix="dcs-tablette-"))
    try:
        source = telecharger(publiee, dossier)
    except Exception as e:              # noqa: BLE001 — jamais bloquant
        shutil.rmtree(dossier, ignore_errors=True)
        afficher(f"Mise à jour impossible : {e}. On continue avec la {VERSION}.")
        afficher(f"À la main : https://github.com/{DEPOT}/releases/latest\n")
        return False
    lancer_remplacement(source, Path(sys.executable).parent, dossier,
                        dossier / f"{NOM}-{publiee['version']}.zip")
    afficher("Fichier vérifié. DCS Tablette se ferme, se met à jour et se relance tout seul.")
    return True
