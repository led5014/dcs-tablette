"""Ce que la tablette règle sur chaque écran, au-delà de ce que DCS propose.

Retour de vol : le TGP du F-16 trop sombre, puis « augmenter le grain des
écrans, un filtre par-dessus qui gère aussi la lum ». Réglés écran par écran
sur la tablette, appliqués par le PC sur l'image copiée, AVANT la compression
JPEG — éclaircie ou affinée après, l'image n'aurait plus les détails que la
compression a mangés :

- luminosité : une courbe gamma, qui éclaircit les gris sans brûler les
  symboles blancs ;
- contraste : écarte (ou rapproche) les tons du gris moyen ;
- netteté (le « grain ») : un masque flou, qui accentue les traits fins ;
- définition : l'image agrandie par le PC (Lanczos) puis affinée, plutôt
  que laissée à l'iPad, qui l'agrandit en flou ; ou réduite, pour un Wi-Fi
  faible. Elle ne crée pas de détail : celui de DCS dépend de la taille de
  la zone d'export, sur l'écran virtuel ;
- filtre : niveaux automatiques (le plus sombre au noir, le plus clair au
  blanc, image par image : ce qu'il faut à un TGP ou un FLIR), noir et blanc,
  inversé (noir chaud / blanc chaud), ou teinté vert, ambre, rouge de nuit.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Tuple

from PIL import Image, ImageFilter, ImageOps

LUMINOSITE = (-4, 8)
CONTRASTE = (-3, 5)
NETTETE = (0, 5)
PAS_GAMMA = 1.25            # un cran de luminosité : gamma × 1,25 (+4 ≈ gamma 2,4)
PAS_CONTRASTE = 1.2         # un cran de contraste : écart au gris moyen × 1,2
# Les écrans du Hornet sont des traits fins et verts sur du noir. Le JPEG
# ordinaire divise par quatre la résolution des couleurs (4:2:0) : le vert
# bave, pâlit, et l'écran paraît éteint. On garde toutes les couleurs.
SOUS_ECHANTILLONNAGE = 0    # 4:4:4
COTE_MAX = 1100             # à la définition normale, l'iPad ne verrait pas mieux
# Définition : (nom, agrandissement, qualité JPEG). Plus fine, l'image est
# plus lourde à passer par le Wi-Fi : ×2, quatre fois plus de pixels.
DEFINITIONS: Tuple[Tuple[str, float, int], ...] = (
    ("Économe", 0.75, 75),
    ("Normale", 1.0, 85),
    ("Fine", 1.5, 90),
    ("Très fine", 2.0, 92),
)
DEFINITION_NORMALE = 1
COUPURE_AUTO = 0.5          # % des pixels ignorés à chaque bout par les niveaux auto
TEINTES: Dict[str, Tuple[int, int, int]] = {
    "vert": (110, 255, 140),        # phosphore
    "ambre": (255, 190, 70),
    "rouge": (255, 60, 40),         # garde la vision de nuit
}
FILTRES = ("", "auto", "nb", "inverse") + tuple(TEINTES)


@dataclass(frozen=True)
class Reglages:
    """Les réglages d'un écran ; par défaut, l'image telle que DCS la dessine."""
    luminosite: int = 0
    contraste: int = 0
    nettete: int = 0
    definition: int = DEFINITION_NORMALE
    filtre: str = ""


def _borne(v, plage: Tuple[int, int]) -> int:
    return max(plage[0], min(plage[1], int(v)))


def reglages(luminosite=0, contraste=0, nettete=0, definition=DEFINITION_NORMALE,
             filtre: str = "") -> Reglages:
    """Réglages bornés ; ValueError pour un filtre inconnu."""
    if filtre not in FILTRES:
        raise ValueError(f"filtre inconnu : {filtre!r} (connus : {', '.join(FILTRES[1:])})")
    return Reglages(_borne(luminosite, LUMINOSITE), _borne(contraste, CONTRASTE),
                    _borne(nettete, NETTETE), _borne(definition, (0, len(DEFINITIONS) - 1)),
                    filtre)


@lru_cache(maxsize=None)
def table_tons(luminosite: int, contraste: int = 0) -> Tuple[int, ...]:
    """Table de correspondance (`Image.point`, une bande) : gamma puis contraste."""
    gamma = PAS_GAMMA ** luminosite
    facteur = PAS_CONTRASTE ** contraste
    table = []
    for i in range(256):
        v = 255 * (i / 255) ** (1 / gamma)
        v = (v - 127.5) * facteur + 127.5
        table.append(max(0, min(255, round(v))))
    return tuple(table)


def traiter(image: Image.Image, r: Reglages) -> Image.Image:
    """L'image réglée, avant compression. `image` n'est jamais modifiée : elle
    sert aussi aux autres tablettes et aux autres réglages."""
    if r.filtre == "auto":
        image = ImageOps.autocontrast(image, cutoff=COUPURE_AUTO, preserve_tone=True)
    if r.filtre == "nb" or r.filtre in TEINTES:
        image = image.convert("L")
    elif r.filtre == "inverse":
        image = ImageOps.invert(image.convert("RGB"))
    if r.luminosite or r.contraste:
        image = image.point(list(table_tons(r.luminosite, r.contraste))
                            * len(image.getbands()))
    if r.filtre in TEINTES:
        image = ImageOps.colorize(image, (0, 0, 0), TEINTES[r.filtre])
    # Affinée sur les pixels de DCS, avant l'agrandissement : quatre fois
    # moins de calcul qu'après (×2 : 17 ms au lieu de 63 sur 720 px), et le
    # Lanczos garde les bords nets.
    if r.nettete:
        image = image.filter(ImageFilter.UnsharpMask(radius=0.8, percent=45 * r.nettete,
                                                     threshold=2))
    _, echelle, _ = DEFINITIONS[r.definition]
    cote = max(image.size)
    voulu = min(round(cote * echelle), round(COTE_MAX * max(1.0, echelle)))
    if voulu != cote:
        l, h = image.size
        image = image.resize((max(1, round(l * voulu / cote)), max(1, round(h * voulu / cote))),
                             Image.LANCZOS)
    return image


def jpeg(image: Image.Image, r: Reglages = Reglages()) -> bytes:
    tampon = io.BytesIO()
    traiter(image, r).save(tampon, "JPEG", quality=DEFINITIONS[r.definition][2],
                           subsampling=SOUS_ECHANTILLONNAGE)
    return tampon.getvalue()
