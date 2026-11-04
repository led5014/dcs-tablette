"""F-16C Viper : les deux MFD et leurs 20 OSB, l'ICP et le DED.

Module non installé sur le poste où ce profil a été écrit : les numéros
viennent de DCS-BIOS (github.com/DCS-Skunkworks/dcs-bios,
Scripts/DCS-BIOS/lib/modules/aircraft_modules/F-16C_50.lua), qui les relève
dans les scripts du module :
- MFD gauche = appareil 24, MFD droit = 25 ; « MFD Left Button n » = 3000 + n ;
- OSB numérotés dans le sens horaire depuis la gauche du haut, comme sur
  l'avion (1–5 en haut, 6–10 à droite, 11–15 en bas, 16–20 à gauche) ;
- ICP (Integrated Control Panel), l'équivalent de l'UFC du Hornet : appareil
  17 (UFC dans devices.lua), commandes 3002 à 3035, recoupées avec
  l'énumération `ufcCommands` de Helios (Aircraft F-16C Plugin/Interfaces/
  Tools/commands.cs).

Zones d'export : LEFT_MFCD et RIGHT_MFCD, la convention des MFD dans DCS.

Le DED (Data Entry Display), au-dessus de l'ICP, n'a pas de zone d'export :
la tablette le refait d'après son texte (ded.py).

Le numéro de l'appareil KNEEBOARD n'est pas dans DCS-BIOS : sans lui, la
tablette ne tourne pas les pages (une commande au mauvais appareil pourrait
actionner autre chose) ; le kneeboard reste affiché, pages aux touches [ et ].
"""
from typing import Dict, Tuple

from . import Ecran, Profil, couronne_horaire
from .. import ded
from ..langues import Texte

_OSB = tuple((str(n), 3000 + n) for n in range(1, 21))
_CADRE = couronne_horaire(5, "haut", _OSB)

ICP = 17
# Boutons, enfoncés puis relâchés comme les OSB : chiffres (0 = 3002 …
# 9 = 3011), COM1, COM2, IFF, LIST, ENTR, RCL, A-A, A-G.
TOUCHES_ICP: Dict[str, int] = {
    **{str(n): 3002 + n for n in range(10)},
    "COM1": 3012, "COM2": 3013, "IFF": 3014, "LIST": 3015,
    "ENTR": 3016, "RCL": 3017, "AA": 3018, "AG": 3019,
}
# Commutateurs à ressort : chaque côté est une commande, poussée à -1 ou à
# +1, qui revient au centre (0) au relâchement — defineSpringloaded_3PosTumb
# de DCS-BIOS. Le « dobber » (Data Control Switch : RTN, SEQ, UP, DN) et la
# bascule ▲▼ du DED (incrément, décrément).
RESSORTS_ICP: Dict[str, Tuple[int, int]] = {
    "RTN": (3032, -1), "SEQ": (3033, 1), "UP": (3034, 1), "DN": (3035, -1),
    "INC": (3030, 1), "DEC": (3031, -1),
}

PROFIL = Profil(
    id="f16c",
    libelle="F-16C Viper",
    noms_dcs=("F-16C_50",),
    ecrans=(
        Ecran("mfd_gauche", Texte("MFD gauche"), "LEFT_MFCD", {"": 24}, _CADRE),
        Ecran("mfd_droit", Texte("MFD droit"), "RIGHT_MFCD", {"": 25}, _CADRE),
    ),
    panneaux=("icp",),
    touches={ICP: frozenset(TOUCHES_ICP.values())},
    ressorts={ICP: {c: sens for c, sens in RESSORTS_ICP.values()}},
    textes=(ded.IND_DED,),
)
