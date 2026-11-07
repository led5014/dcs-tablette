"""Configuration de la tablette : où sont les fichiers de DCS, quels ports.

Les ports UDP doivent rester ceux de `dcs_export/DCS-Tablette-Export.lua` :
le script Lua n'a pas de fichier de réglages, ses valeurs y sont écrites en
dur. En changer un ici sans l'autre coupe le lien sans message.
"""
from __future__ import annotations

import ctypes
import json
import os
import socket
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

PORT_WEB = 8320          # 8317 : DCS Debrief ; 8318 : son instance de travail
PORT_ORDRES = 7790       # le script Lua écoute ici
PORT_ETAT = 7791         # le serveur écoute ici

SAVED_GAMES = uuid.UUID("4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4")   # FOLDERID_SavedGames
BUREAU = uuid.UUID("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")        # FOLDERID_Desktop
# Les dossiers de DCS dans Parties enregistrées, à égalité celui de gauche.
NOMS_DCS = ("DCS", "DCS.openbeta")


def adresses_locales():
    """Adresses IPv4 de ce PC sur le réseau local, à taper sur l'iPad."""
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return sorted({i[4][0] for i in infos if not i[4][0].startswith("127.")})


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


def fichier_choix() -> Path:
    """Ce que le pilote a choisi à l'installation (installation.ecrire_choix)."""
    racine = os.environ.get("LOCALAPPDATA")
    return (Path(racine) if racine else Path.home()) / "DCS-Tablette" / "installation.json"


def dossier_retenu(chemin: Optional[Path] = None) -> Optional[Path]:
    """Le dossier de DCS que le pilote a choisi à l'installation, s'il existe
    encore (installation.choisir_dossier)."""
    try:
        dossier = Path(json.loads((chemin or fichier_choix()).read_text(
            encoding="utf-8"))["saved_games"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return dossier if dossier.is_dir() else None


def dossiers_dcs(racine: Optional[Path] = None) -> List[Path]:
    """Les dossiers de DCS qui existent dans Parties enregistrées."""
    racine = racine or dossier_windows(SAVED_GAMES) or Path.home() / "Saved Games"
    return [racine / nom for nom in NOMS_DCS if (racine / nom).is_dir()]


def dernier_lancement(dossier: Path) -> Optional[float]:
    """Quand DCS s'est servi de ce dossier pour la dernière fois : il
    recommence Logs/dcs.log à chaque lancement et y écrit jusqu'à la fin."""
    try:
        return (dossier / "Logs" / "dcs.log").stat().st_mtime
    except OSError:
        return None


def plus_recent(dossiers: Sequence[Path]) -> Optional[Path]:
    """Celui dont DCS s'est servi en dernier ; à égalité, ou sans dcs.log,
    le premier de la liste."""
    return max(dossiers, key=lambda d: dernier_lancement(d) or 0.0, default=None)


def dossier_saved_games(racine: Optional[Path] = None,
                        chemin_choix: Optional[Path] = None) -> Path:
    """Le dossier dont DCS se sert : Saved Games/DCS, ou DCS.openbeta.

    Les deux existent souvent. Une installation venue de l'ancienne bêta
    garde DCS.openbeta (dcs_variant.txt, dans le dossier de DCS), et
    Saved Games/DCS a pu être créé par une autre installation ou un autre
    outil. Retour d'un pilote, le 05/11/2026 : son DCS se servait de
    DCS.openbeta, la tablette s'était installée dans DCS.

    Le dossier choisi à l'installation s'il existe encore, sinon celui dont
    DCS s'est servi en dernier, sinon Saved Games/DCS.
    """
    retenu = dossier_retenu(chemin_choix)
    if retenu is not None:
        return retenu
    racine = racine or dossier_windows(SAVED_GAMES) or Path.home() / "Saved Games"
    return plus_recent(dossiers_dcs(racine)) or racine / "DCS"


@dataclass
class Config:
    saved_games: Path = field(default_factory=dossier_saved_games)
    port_web: int = PORT_WEB
    port_ordres: int = PORT_ORDRES
    port_etat: int = PORT_ETAT
