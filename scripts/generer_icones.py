"""Dessine l'icône de DCS Tablette : un écran de cockpit, ses boutons, un horizon.

    .venv\\Scripts\\python.exe scripts\\generer_icones.py

Écrit :
- src/tablette/web/icone-180.png    écran d'accueil de l'iPad / iPhone (carré plein :
                                    iOS arrondit lui-même les coins)
- src/tablette/web/icone-192.png,   écran d'accueil d'Android, manifeste
  icone-512.png
- distribution/tablette/dcs_tablette.ico   l'exécutable et son raccourci

À relancer seulement pour changer le dessin ; les fichiers sont versionnés.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

RACINE = Path(__file__).resolve().parent.parent
WEB = RACINE / "src" / "tablette" / "web"
ICO = RACINE / "distribution" / "tablette" / "dcs_tablette.ico"

FOND = (11, 13, 14)
CADRE = (58, 63, 66)
CADRE_BORD = (27, 30, 31)
BOUTON = (98, 105, 110)
ECRAN = (4, 7, 6)
VERT = (61, 220, 106)
C = 1024                      # dessin en grand, réduit ensuite : bords lisses


def dessiner(coins_arrondis: bool) -> Image.Image:
    image = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    if coins_arrondis:
        d.rounded_rectangle((0, 0, C - 1, C - 1), radius=210, fill=FOND)
    else:
        d.rectangle((0, 0, C - 1, C - 1), fill=FOND)
    # Le cadre et sa couronne de boutons, quatre par côté.
    d.rounded_rectangle((120, 120, 904, 904), radius=70, fill=CADRE, outline=CADRE_BORD, width=10)
    for i in range(4):
        p = 300 + i * 141
        for x0, y0, x1, y1 in ((p - 42, 148, p + 42, 212), (p - 42, 812, p + 42, 876),
                               (148, p - 42, 212, p + 42), (812, p - 42, 876, p + 42)):
            d.rounded_rectangle((x0, y0, x1, y1), radius=12, fill=BOUTON)
    # L'écran : un horizon et le symbole de l'avion.
    d.rounded_rectangle((250, 250, 774, 774), radius=46, fill=ECRAN)
    d.line((300, 610, 724, 610), fill=VERT, width=22)
    d.line((442, 690, 582, 690), fill=VERT, width=14)
    d.ellipse((472, 470, 552, 550), outline=VERT, width=20)
    d.line((372, 510, 472, 510), fill=VERT, width=20)
    d.line((552, 510, 652, 510), fill=VERT, width=20)
    d.line((512, 470, 512, 420), fill=VERT, width=20)
    return image


def main() -> int:
    arrondie, pleine = dessiner(True), dessiner(False)
    pleine.convert("RGB").resize((180, 180), Image.LANCZOS).save(WEB / "icone-180.png")
    for cote in (192, 512):
        arrondie.resize((cote, cote), Image.LANCZOS).save(WEB / f"icone-{cote}.png")
    ICO.parent.mkdir(parents=True, exist_ok=True)
    arrondie.resize((256, 256), Image.LANCZOS).save(
        ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Écrit : {WEB / 'icone-*.png'}, {ICO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
