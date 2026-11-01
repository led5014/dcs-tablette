"""Les captures d'écran sans l'écran virtuel.

DCS s'étend sur l'écran principal ET sur l'écran virtuel où il dessine les
écrans exportés : 5120 × 1440 pour deux écrans de 2560. Tout ce qui capture
la fenêtre de DCS en prend toute la largeur — F12 de Steam, Impr. écran de
DCS, Win + Alt + Impr. écran (Game Bar) —, et Win + Impr. écran prend tous
les écrans du bureau. Vu le 31/10/2026 : une capture Steam en 5120 × 1440,
la moitié droite noire.

Rien à faire à la source : la fenêtre de DCS est d'un seul tenant, et une
fenêtre plus grande que le bureau, DCS la ramène à l'écran (docs/tablette.md,
« Essayé et écarté »). Ce fil recadre donc, tant que DCS Tablette tourne,
chaque nouvelle capture qui a la taille de toute l'image de DCS sur la vue
principale (Center de la configuration d'écrans) : elle redevient celle
d'un écran unique.

- seulement les fichiers apparus depuis le lancement : les anciennes
  captures ne bougent pas ;
- seulement à la taille exacte de l'image de DCS (largeur et hauteur
  d'options.lua) : la capture d'une zone, d'un autre jeu ou d'un bureau à
  trois écrans reste telle quelle ;
- un JPEG est réenregistré avec ses propres tables de quantification, donc
  à la qualité choisie par Steam ou DCS ; la date du fichier est gardée ;
- la vignette de Steam est refaite, sinon sa bibliothèque montrerait
  encore le bandeau large.

Un stream ne se recadre pas : Discord partage la fenêtre de DCS en entier.
Il faut partager l'écran principal à la place (LISEZ-MOI, « Captures et
stream »).
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from PIL import Image, JpegImagePlugin

from .config import dossier_windows
from .copie import Rect, dans
from .ecrans_dcs import PasDExport, fichier_actif, lire_vue, options_affichage
from .langues import Texte

APPLI_STEAM_DCS = "223750"
CAPTURES_WINDOWS = uuid.UUID("B7BEDE81-DF94-4682-A7D8-57A52620B86F")   # FOLDERID_Screenshots
VIDEOS = uuid.UUID("18989B1D-99B5-455B-841C-AB7C74E4DDFC")             # FOLDERID_Videos
EXTENSIONS = (".jpg", ".jpeg", ".png")
PERIODE_S = 2.0
# Un fichier plus jeune est peut-être encore en cours d'écriture.
REPOS_S = 1.0
# Illisible autant de fois de suite (image tronquée, fichier verrouillé) :
# on le laisse.
ESSAIS = 5

journal = logging.getLogger("tablette")


def vue_a_rogner(saved_games: Path) -> Optional[Tuple[Rect, Tuple[int, int]]]:
    """La vue principale de DCS et la taille de toute son image, quand les
    écrans exportés sont dessinés hors de la vue (sur l'écran virtuel). None
    sinon : mode essai, écran unique, réglages illisibles."""
    try:
        _, largeur, hauteur = options_affichage(saved_games)
        texte = fichier_actif(saved_games).read_text(encoding="utf-8", errors="replace")
    except (OSError, PasDExport):
        return None
    vue = lire_vue(texte, largeur, hauteur)
    if not vue or vue == (0, 0, largeur, hauteur) or not dans(vue, (largeur, hauteur)):
        return None
    return vue, (largeur, hauteur)


def dossier_steam() -> Optional[Path]:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as cle:
            return Path(winreg.QueryValueEx(cle, "SteamPath")[0])
    except (ImportError, OSError):
        return None


def dossiers_captures(saved_games: Path) -> List[Path]:
    """Où arrivent les captures : DCS, Steam (DCS seulement), Windows, Game Bar."""
    dossiers = [saved_games / "Screenshots"]
    steam = dossier_steam()
    if steam:
        dossiers += sorted((steam / "userdata").glob(
            f"*/760/remote/{APPLI_STEAM_DCS}/screenshots"))
    captures, videos = dossier_windows(CAPTURES_WINDOWS), dossier_windows(VIDEOS)
    if captures:
        dossiers.append(captures)
    if videos:
        dossiers.append(videos / "Captures")
    return [d for d in dossiers if d.is_dir()]


def _remplacer(chemin: Path, image: Image.Image, format_: str, **options) -> None:
    """Réécrit `chemin` d'un coup (jamais à moitié écrit), à sa date d'avant."""
    dates = chemin.stat()
    temporaire = chemin.with_name(chemin.name + ".dcs-tablette")
    try:
        image.save(temporaire, format=format_, **options)
        os.replace(temporaire, chemin)
    finally:
        temporaire.unlink(missing_ok=True)
    os.utime(chemin, ns=(dates.st_atime_ns, dates.st_mtime_ns))


def rogner(chemin: Path, vue: Rect, taille: Tuple[int, int]) -> bool:
    """Recadre la capture sur la vue si elle a la taille de toute l'image de
    DCS. True si elle l'a été. OSError si elle est illisible — peut-être
    encore en cours d'écriture."""
    with Image.open(chemin) as image:
        if image.size != tuple(taille):
            return False
        image.load()
        format_ = image.format
        options: Dict = {}
        if format_ == "JPEG":
            options = {"qtables": image.quantization,
                       "subsampling": JpegImagePlugin.get_sampling(image)}
            options.update({cle: image.info[cle] for cle in ("exif", "icc_profile")
                            if image.info.get(cle)})
        x, y, l, h = vue
        recadree = image.crop((x, y, x + l, y + h))
    _remplacer(chemin, recadree, format_, **options)
    vignette = chemin.parent / "thumbnails" / chemin.name
    if vignette.is_file():
        with Image.open(vignette) as ancienne:
            largeur = ancienne.width
        petite = recadree.resize((largeur, max(1, round(largeur * h / l))), Image.LANCZOS)
        _remplacer(vignette, petite.convert("RGB"), "JPEG", quality=90)
    return True


class Captures(threading.Thread):
    """Recadre les nouvelles captures sur la vue principale, toutes les 2 s."""

    def __init__(self, saved_games: Path,
                 dossiers: Optional[Callable[[], List[Path]]] = None,
                 depuis: Optional[float] = None):
        super().__init__(name="tablette-captures", daemon=True)
        self.saved_games = saved_games
        self._dossiers = dossiers or (lambda: dossiers_captures(saved_games))
        self.depuis = time.time() if depuis is None else depuis
        self._faits: Set[Path] = set()
        self._essais: Dict[Path, int] = {}

    def tour(self, maintenant: Optional[float] = None) -> List[Path]:
        """Un passage dans les dossiers : rend les captures recadrées."""
        maintenant = time.time() if maintenant is None else maintenant
        cadre = vue_a_rogner(self.saved_games)
        if cadre is None:
            return []
        recadrees = []
        for dossier in self._dossiers():
            try:
                entrees = list(os.scandir(dossier))
            except OSError:
                continue
            for entree in entrees:
                chemin = Path(entree.path)
                if not entree.name.lower().endswith(EXTENSIONS) or chemin in self._faits:
                    continue
                try:
                    date = entree.stat().st_mtime
                except OSError:
                    continue
                if date < self.depuis or maintenant - date < REPOS_S:
                    continue
                try:
                    if rogner(chemin, *cadre):
                        recadrees.append(chemin)
                        journal.info(Texte("Capture recadrée sur l'écran principal : {nom}",
                                           nom=chemin.name))
                except OSError:
                    self._essais[chemin] = self._essais.get(chemin, 0) + 1
                    if self._essais[chemin] < ESSAIS:
                        continue
                self._faits.add(chemin)
        return recadrees

    def run(self) -> None:
        while True:
            try:
                self.tour()
            except Exception:                     # noqa: BLE001 — jamais le serveur
                journal.exception(Texte("Recadrage des captures : passage ignoré"))
            time.sleep(PERIODE_S)
