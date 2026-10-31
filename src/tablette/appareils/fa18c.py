"""F/A-18C Hornet : deux DDI, l'AMPCD, et la planche avant redessinée.

Mods/aircraft/FA-18C/Cockpit/Scripts :
- devices.lua : MDI_LEFT = 35, MDI_RIGHT = 36, AMPCD = 37, KNEEBOARD = 68 ;
- command_defs.lua : PB 1 à 20 = 3011 à 3030, les mêmes pour les trois
  écrans, « numbered clockwise from the lowest button at the left side » ;
- zones d'export : LEFT_MFCD, RIGHT_MFCD, CENTER_MFCD (…_viewport_cfg.lua).

L'UFC, l'IFEI, les instruments de secours et les voyants : voir planche.py.
"""
from dataclasses import replace

from .. import planche
from ..instruments import OTAN
from . import Ecran, Profil, couronne_horaire, reperes

DOSSIER_KNEEBOARD = "FA-18C_hornet"

_PB = tuple((str(pb), 3010 + pb) for pb in range(1, 21))
_CADRE = couronne_horaire(5, "gauche", _PB)

# Où sont les libellés : Multipurpose_Display_Group/Common/indicator/
# MPD_PB_defs.lua, en unités d'un écran de 1024 (MDG_units.lua,
# UnitsPerSide), centre 0, y vers le haut. Haut et bas : x de -336 (PB 6,
# PB 20) par pas de 169 ; côtés : y de 307 (PB 5, PB 11) par pas de -167.
# Les mêmes pour les DDI et l'AMPCD.
REPERES_X = reperes(-336, -336 + 4 * 169, 5, 512)
REPERES_Y = reperes(307, 307 - 4 * 167, 5, 512, vers_le_bas=True)

PROFIL = Profil(
    id="fa18c",
    libelle="F/A-18C Hornet",
    noms_dcs=("FA-18C_hornet",),
    ecrans=(
        # Verre arrondi, mesuré sur l'export : rayon ≈ 1/6 du côté.
        Ecran("ddi_gauche", "DDI gauche", "LEFT_MFCD", {"": 35}, _CADRE, arrondi=0.17,
              reperes_x=REPERES_X, reperes_y=REPERES_Y),
        Ecran("ddi_droit", "DDI droit", "RIGHT_MFCD", {"": 36}, _CADRE, arrondi=0.17,
              reperes_x=REPERES_X, reperes_y=REPERES_Y),
        Ecran("ampcd", "AMPCD", "CENTER_MFCD", {"": 37}, _CADRE, arrondi=0.17,
              reperes_x=REPERES_X, reperes_y=REPERES_Y),
    ),
    kneeboard=68,
    panneaux=("ufc", "ifei", "secours"),
    touches={planche.UFC: frozenset(planche.TOUCHES_UFC.values())},
    molettes={planche.UFC: {c: planche.CRAN_MOLETTE for c in planche.MOLETTES_UFC.values()}},
    textes=(planche.IND_IFEI, planche.IND_UFC),
    arguments=tuple(planche.ARGUMENTS),
    instruments=replace(OTAN, moteurs=2),
)
