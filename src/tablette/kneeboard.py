"""Les pages de kneeboard que la tablette peut afficher, lues dans les fichiers.

« Kneeboard de l'avion » rassemble les images que DCS met dans le kneeboard
de l'appareil piloté, de la plus propre au vol à la plus générale :

- la mission en cours : `KNEEBOARD/IMAGES/` et `KNEEBOARD/<appareil>/IMAGES/`
  du `.miz` — ou du `.trk` en multijoueur : vu dans dcs.log, DCS charge la
  mission du serveur depuis l'enregistrement de la partie ;
- celles livrées avec le module (`Mods/aircraft/<module>/Cockpit/Scripts/
  KNEEBOARD/pages/`, deux pour l'A-10C) ;
- les tiennes : `Saved Games/DCS/Kneeboard/<appareil>/`, puis `Kneeboard/`.

« Cartes : <carte> » : les planches livrées avec la carte de la mission
(`Mods/terrains/<carte>/Kneeboard/`, 53 aérodromes et légendes pour le
Caucase). Puis les missions du dossier Missions, à feuilleter.

Dossiers et noms suivent `Scripts/Aircrafts/_Common/Cockpit/KNEEBOARD/
indicator/init.lua` de DCS. Les pages que DCS fabrique lui-même (fréquences,
points, carte de la mission) ne sont pas des fichiers : elles arrivent par la
capture du kneeboard de DCS (video.py), en tête de liste sur la tablette.

Aucun chemin ne vient de la tablette : elle désigne un carnet par
l'identifiant qu'on lui a donné et une page par son rang, et l'on ne sert que
ce qu'on a soi-même listé.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from PIL import Image

EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
# Lues par DCS, pas par les navigateurs : converties en PNG au passage.
CONVERTIES = {".dds", ".tga", ".bmp"}
MISSIONS_MAX = 30

# Une page de mission : le fichier .miz ou .trk et le nom de l'image dedans.
Page = Union[Path, Tuple[Path, str]]


@dataclass
class Carnet:
    id: str
    titre: str
    pages: List[Page] = field(default_factory=list)


def _lisible(nom: str) -> bool:
    extension = Path(nom).suffix.lower()
    return extension in EXTENSIONS or extension in CONVERTIES


def _images(dossier: Optional[Path]) -> List[Path]:
    if dossier is None or not dossier.is_dir():
        return []
    return sorted((p for p in dossier.iterdir() if p.is_file() and _lisible(p.name)),
                  key=lambda p: p.name.lower())


def _pages_de_mission(miz: Path, appareil: str) -> List[Tuple[Path, str]]:
    prefixes = ("KNEEBOARD/IMAGES/", f"KNEEBOARD/{appareil}/IMAGES/".upper())
    try:
        with zipfile.ZipFile(miz) as archive:
            noms = archive.namelist()
    except (OSError, zipfile.BadZipFile):
        return []
    retenus = [n for n in noms if n.upper().startswith(prefixes) and _lisible(n)]
    return [(miz, n) for n in sorted(retenus, key=str.lower)]


LECTURE_JOURNAL = 2_000_000      # octets lus à la fin de dcs.log


def mission_en_cours(saved_games: Path) -> Optional[Path]:
    """Le fichier de la mission que DCS a chargée en dernier, d'après dcs.log.

    Vu en vrai : une mission lancée depuis l'éditeur ou une campagne est
    jouée depuis une copie temporaire (AppData/Local/Temp/DCS/tempMission.miz),
    et une mission multijoueur depuis l'enregistrement de la partie
    (Tracks/Multiplayer/<mission>-<date>.trk), hors du dossier Missions :
    sans le journal, leurs pages resteraient invisibles.
    """
    journal = saved_games / "Logs" / "dcs.log"
    try:
        with open(journal, "rb") as f:
            f.seek(max(0, journal.stat().st_size - LECTURE_JOURNAL))
            fin = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    chemins = re.findall(r"loadMission (.+?\.(?:miz|trk))\s*$", fin, re.M | re.I)
    if not chemins:
        return None
    chemin = Path(chemins[-1].strip())
    return chemin if chemin.is_file() else None


@lru_cache(maxsize=8)
def _carte(mission: str, _date: float) -> Optional[str]:
    try:
        with zipfile.ZipFile(mission) as archive:
            texte = archive.read("mission").decode("utf-8", "replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    m = re.search(r'\["theatre"\]\s*=\s*"([^"]+)"', texte)
    return m.group(1) if m else None


def carte_de(mission: Path) -> Optional[str]:
    """La carte de la mission (« Caucasus », « Syria »…), lue une fois par fichier."""
    try:
        return _carte(str(mission), mission.stat().st_mtime)
    except OSError:
        return None


@lru_cache(maxsize=4)
def _modules(dcs: str) -> Dict[str, Path]:
    """Appareil → dossier de son module, d'après les make_flyable('<appareil>', …)
    des entry.lua : le dossier ne porte pas le nom de l'appareil (FA-18C pour
    FA-18C_hornet)."""
    modules = {}
    for entree in sorted((Path(dcs) / "Mods" / "aircraft").glob("*/entry.lua")):
        try:
            texte = entree.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for appareil in re.findall(r"make_flyable\(\s*['\"]([^'\"]+)['\"]", texte):
            modules.setdefault(appareil, entree.parent)
    return modules


@lru_cache(maxsize=4)
def _cartes(dcs: str) -> Dict[str, Path]:
    """Carte → dossier de ses planches, d'après le `local self_ID = "…"` des
    entry.lua des cartes : l'identifiant n'est pas toujours le nom du dossier
    (SinaiMap pour Sinai, MarianaIslandsWWII pour MarianasWWII)."""
    cartes = {}
    for entree in sorted((Path(dcs) / "Mods" / "terrains").glob("*/entry.lua")):
        try:
            texte = entree.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        planches = next((d for d in entree.parent.iterdir()
                         if d.is_dir() and d.name.lower() == "kneeboard"), None)
        for identifiant in re.findall(r'\bself_ID\s*=\s*"([^"]+)"', texte):
            if planches is not None:
                cartes.setdefault(identifiant, planches)
    return cartes


def lister_carnets(saved_games: Path, appareil: str,
                   dcs: Optional[Path] = None) -> List[Carnet]:
    """Les carnets de l'appareil piloté. `dcs` : dossier d'installation de DCS
    (pages du module et de la carte), inconnu tant qu'il n'a pas tourné."""
    carnets = []
    en_cours = mission_en_cours(saved_games)
    module = _modules(str(dcs)).get(appareil) if dcs else None
    racine = saved_games / "Kneeboard"
    avion = ((_pages_de_mission(en_cours, appareil) if en_cours else [])
             + _images(module / "Cockpit" / "Scripts" / "KNEEBOARD" / "pages" if module else None)
             + _images(racine / appareil) + _images(racine))
    if avion:
        carnets.append(Carnet("avion", "Kneeboard de l'avion", list(avion)))

    carte = carte_de(en_cours) if en_cours else None
    planches = _cartes(str(dcs)).get(carte) if dcs and carte else None
    if planches is not None:
        pages = _images(planches / appareil) + _images(planches)
        if pages:
            carnets.append(Carnet(f"carte:{carte}", f"Cartes : {carte}", list(pages)))

    dossier_missions = saved_games / "Missions"
    if dossier_missions.is_dir():
        missions = sorted(dossier_missions.glob("*.miz"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        for miz in missions[:MISSIONS_MAX]:
            if en_cours is not None and miz == en_cours:
                continue                # déjà en tête du kneeboard de l'avion
            pages = _pages_de_mission(miz, appareil)
            if pages:
                carnets.append(Carnet(f"miz:{miz.name}", miz.stem, list(pages)))
    return carnets


def trouver(carnets: List[Carnet], carnet_id: str) -> Optional[Carnet]:
    return next((c for c in carnets if c.id == carnet_id), None)


def lire_page(page: Page) -> Tuple[bytes, str]:
    """Contenu et type MIME d'une page. Lève OSError si elle a disparu ou ne
    se lit pas."""
    if isinstance(page, Path):
        nom, donnees = page.name, page.read_bytes()
    else:
        miz, nom = page
        try:
            with zipfile.ZipFile(miz) as archive:
                donnees = archive.read(nom)
        except (KeyError, zipfile.BadZipFile) as e:
            raise OSError(str(e)) from e
    extension = Path(nom).suffix.lower()
    if extension in EXTENSIONS:
        return donnees, EXTENSIONS[extension]
    try:
        image = Image.open(io.BytesIO(donnees))
        tampon = io.BytesIO()
        image.convert("RGBA" if "A" in image.getbands() else "RGB").save(tampon, "PNG")
    except (OSError, ValueError) as e:
        raise OSError(f"{nom} illisible : {e}") from e
    return tampon.getvalue(), "image/png"
