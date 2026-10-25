"""Une copie de la fenêtre de DCS, réduite à ce que la tablette demande.

Coordonnées en pixels de la zone cliente de DCS, comme dans un fichier
MonitorSetup. Module sans Windows : la capture le remplit, les tests aussi.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from PIL import Image

Rect = Tuple[int, int, int, int]       # x, y, largeur, hauteur
COTE_TEMOIN = 64


@dataclass
class Copie:
    taille: Tuple[int, int]            # zone cliente de DCS au moment de la copie
    ecrans: Dict[str, Image.Image]     # seulement les zones contenues dans la fenêtre


def dans(zone: Rect, taille: Tuple[int, int]) -> bool:
    x, y, l, h = zone
    return x >= 0 and y >= 0 and x + l <= taille[0] and y + h <= taille[1]


def zone_temoin(taille: Tuple[int, int]) -> Rect:
    """Un carré au milieu de la vue principale. S'il est noir aussi, ce n'est
    pas un écran éteint, c'est la copie qui ne voit rien.

    Pas au centre de la fenêtre : quand DCS s'étend sur deux écrans, le
    centre tombe sur la frontière, souvent hors de la vue.
    """
    c = COTE_TEMOIN
    return (min(taille) // 2 - c // 2, taille[1] // 2 - c // 2, c, c)


def decouper(fenetre: Image.Image, zones: Dict[str, Rect]) -> Copie:
    """Copie tirée d'une image de la fenêtre entière."""
    ecrans = {nom: fenetre.crop((x, y, x + l, y + h))
              for nom, (x, y, l, h) in zones.items() if dans((x, y, l, h), fenetre.size)}
    return Copie(fenetre.size, ecrans)
