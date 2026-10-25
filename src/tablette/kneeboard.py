"""Les pages de kneeboard que la tablette peut afficher.

Trois sources, toutes de simples images déjà sur le disque :

- la mission en cours, retrouvée dans le journal de DCS ;
- « Mes pages » : `Saved Games/DCS/Kneeboard/` (pages communes à tous les
  appareils) et son sous-dossier propre au Hornet ;
- les missions : chaque `.miz` de `Saved Games/DCS/Missions/` qui embarque
  des pages dans `KNEEBOARD/IMAGES/` ou `KNEEBOARD/<appareil>/IMAGES/`.

Les pages que DCS fabrique lui-même (fréquences, points de navigation) ne
sont pas des fichiers : elles arrivent par la capture du kneeboard de DCS
(video.py), présentée en tête de liste par la page.

Aucun chemin ne vient de la tablette : elle désigne un carnet par l'identifiant
qu'on lui a donné et une page par son rang, et l'on ne sert que ce qu'on a
soi-même listé.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Union

EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
MISSIONS_MAX = 30

# Une page de mission : le fichier .miz et le nom de l'image dans l'archive.
Page = Union[Path, Tuple[Path, str]]


@dataclass
class Carnet:
    id: str
    titre: str
    pages: List[Page] = field(default_factory=list)


def _images(dossier: Path) -> List[Path]:
    if not dossier.is_dir():
        return []
    return sorted((p for p in dossier.iterdir()
                   if p.is_file() and p.suffix.lower() in EXTENSIONS),
                  key=lambda p: p.name.lower())


def _pages_de_mission(miz: Path, dossier_appareil: str) -> List[Tuple[Path, str]]:
    prefixes = ("KNEEBOARD/IMAGES/", f"KNEEBOARD/{dossier_appareil}/IMAGES/".upper())
    try:
        with zipfile.ZipFile(miz) as archive:
            noms = archive.namelist()
    except (OSError, zipfile.BadZipFile):
        return []
    retenus = [n for n in noms
               if n.upper().startswith(prefixes)
               and Path(n).suffix.lower() in EXTENSIONS]
    return [(miz, n) for n in sorted(retenus, key=str.lower)]


LECTURE_JOURNAL = 2_000_000      # octets lus à la fin de dcs.log


def mission_en_cours(saved_games: Path) -> Optional[Path]:
    """Le fichier de la mission que DCS a chargée en dernier, d'après dcs.log.

    Vu en vrai : une mission lancée depuis l'éditeur ou une campagne est
    jouée depuis une copie temporaire (AppData/Local/Temp/DCS/tempMission.miz),
    hors du dossier Missions : sans le journal, ses pages resteraient
    invisibles.
    """
    journal = saved_games / "Logs" / "dcs.log"
    try:
        with open(journal, "rb") as f:
            f.seek(max(0, journal.stat().st_size - LECTURE_JOURNAL))
            fin = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    chemins = re.findall(r"loadMission (.+?\.miz)\s*$", fin, re.M)
    if not chemins:
        return None
    chemin = Path(chemins[-1].strip())
    return chemin if chemin.is_file() else None


def lister_carnets(saved_games: Path, dossier_appareil: str) -> List[Carnet]:
    carnets = []
    en_cours = mission_en_cours(saved_games)
    if en_cours is not None:
        pages = _pages_de_mission(en_cours, dossier_appareil)
        if pages:
            carnets.append(Carnet("en-cours", "Mission en cours", list(pages)))
    racine = saved_games / "Kneeboard"
    mes_pages = _images(racine) + _images(racine / dossier_appareil)
    if mes_pages:
        carnets.append(Carnet("mes-pages", "Mes pages", list(mes_pages)))

    dossier_missions = saved_games / "Missions"
    if dossier_missions.is_dir():
        missions = sorted(dossier_missions.glob("*.miz"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        for miz in missions[:MISSIONS_MAX]:
            pages = _pages_de_mission(miz, dossier_appareil)
            if pages:
                carnets.append(Carnet(f"miz:{miz.name}", miz.stem, list(pages)))
    return carnets


def trouver(carnets: List[Carnet], carnet_id: str) -> Optional[Carnet]:
    return next((c for c in carnets if c.id == carnet_id), None)


def lire_page(page: Page) -> Tuple[bytes, str]:
    """Contenu et type MIME d'une page. Lève OSError si elle a disparu."""
    if isinstance(page, Path):
        return page.read_bytes(), EXTENSIONS[page.suffix.lower()]
    miz, nom = page
    try:
        with zipfile.ZipFile(miz) as archive:
            return archive.read(nom), EXTENSIONS[Path(nom).suffix.lower()]
    except (KeyError, zipfile.BadZipFile) as e:
        raise OSError(str(e)) from e
