"""Configuration de la tablette : où sont les fichiers de DCS, quels ports.

Les ports UDP doivent rester ceux de `dcs_export/DCS-Tablette-Export.lua` :
le script Lua n'a pas de fichier de réglages, ses valeurs y sont écrites en
dur. En changer un ici sans l'autre coupe le lien sans message.
"""
from __future__ import annotations

import ctypes
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PORT_WEB = 8320          # 8317 : DCS Debrief ; 8318 : son instance de travail
PORT_ORDRES = 7790       # le script Lua écoute ici
PORT_ETAT = 7791         # le serveur écoute ici

SAVED_GAMES = uuid.UUID("4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4")   # FOLDERID_SavedGames
BUREAU = uuid.UUID("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")        # FOLDERID_Desktop


def dossier_windows(dossier: uuid.UUID) -> Optional[Path]:
    """Un dossier connu de Windows (Parties enregistrées, Bureau) là où il est
    vraiment : on a pu le déplacer sur un autre disque ou dans OneDrive."""
    try:
        guid = (ctypes.c_ubyte * 16).from_buffer_copy(dossier.bytes_le)
        chemin = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None,
                                                      ctypes.byref(chemin)) != 0:
            return None
        try:
            return Path(chemin.value) if chemin.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(chemin)
    except (AttributeError, OSError):       # hors Windows
        return None


def dossier_saved_games() -> Path:
    """Saved Games/DCS, ou DCS.openbeta pour une installation bêta seule."""
    racine = dossier_windows(SAVED_GAMES) or Path.home() / "Saved Games"
    for nom in ("DCS", "DCS.openbeta"):
        if (racine / nom).is_dir():
            return racine / nom
    return racine / "DCS"


@dataclass
class Config:
    saved_games: Path = field(default_factory=dossier_saved_games)
    port_web: int = PORT_WEB
    port_ordres: int = PORT_ORDRES
    port_etat: int = PORT_ETAT
