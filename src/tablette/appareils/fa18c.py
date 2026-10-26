"""F/A-18C Hornet : deux DDI, l'AMPCD, et la planche avant redessinée.

Mods/aircraft/FA-18C/Cockpit/Scripts :
- devices.lua : MDI_LEFT = 35, MDI_RIGHT = 36, AMPCD = 37, KNEEBOARD = 68 ;
- command_defs.lua : PB 1 à 20 = 3011 à 3030, les mêmes pour les trois
  écrans, « numbered clockwise from the lowest button at the left side » ;
- zones d'export : LEFT_MFCD, RIGHT_MFCD, CENTER_MFCD (…_viewport_cfg.lua).

L'UFC, l'IFEI, les instruments de secours et les voyants : voir planche.py.
"""
from .. import planche
from . import Ecran, Profil, couronne_horaire

DOSSIER_KNEEBOARD = "FA-18C_hornet"

_PB = tuple((str(pb), 3010 + pb) for pb in range(1, 21))
_CADRE = couronne_horaire(5, "gauche", _PB)

PROFIL = Profil(
    id="fa18c",
    libelle="F/A-18C Hornet",
    noms_dcs=("FA-18C_hornet",),
    ecrans=(
        # Verre arrondi, mesuré sur l'export : rayon ≈ 1/6 du côté.
        Ecran("ddi_gauche", "DDI gauche", "LEFT_MFCD", {"": 35}, _CADRE, arrondi=0.17),
        Ecran("ddi_droit", "DDI droit", "RIGHT_MFCD", {"": 36}, _CADRE, arrondi=0.17),
        Ecran("ampcd", "AMPCD", "CENTER_MFCD", {"": 37}, _CADRE, arrondi=0.17),
    ),
    kneeboard=68,
    panneaux=("ufc", "ifei", "secours"),
    touches={planche.UFC: frozenset(planche.TOUCHES_UFC.values())},
    molettes={planche.UFC: {c: planche.CRAN_MOLETTE for c in planche.MOLETTES_UFC.values()}},
    textes=(planche.IND_IFEI, planche.IND_UFC),
    arguments=tuple(planche.ARGUMENTS),
)
