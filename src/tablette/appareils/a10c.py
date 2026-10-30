"""A-10C et A-10C II : les deux MFCD et leurs 20 OSB.

Mods/aircraft/A-10C_2/Cockpit/Scripts (A-10C identique) :
- devices.lua : MFCD_LEFT = 2, MFCD_RIGHT = 3 ; pas de KNEEBOARD déclaré :
  declare_kneeboard_device.lua lui donne alors l'identifiant 100, celui que
  common_keyboard_binding.lua utilise aussi ;
- command_defs.lua : device_commands.Button_n = 3000 + n ;
- clickabledata.lua : « OSB n » = Button_n, numérotés dans le sens horaire
  depuis la gauche du haut (1–5 en haut, 6–10 à droite, 11–15 en bas,
  16–20 à gauche) ;
- zones d'export : LEFT_MFCD, RIGHT_MFCD.

Les bascules ADJ, DSP, BRT, CON et SYM ne sont pas reprises.
"""
from . import Ecran, Profil, couronne_horaire, reperes

_OSB = tuple((str(n), 3000 + n) for n in range(1, 21))
_CADRE = couronne_horaire(5, "haut", _OSB)

# Où sont les libellés : MFCD/indicator/MFCD_useful_definitions.lua
# (OSB_positions) et MFCD_sizes.lua : un carré de 569 pixels (origine en bas
# à gauche, recentrée), qui couvre 97 % de l'image (size_k). Haut et bas : x
# de 110 à 569 - 110 ; côtés : y de 569 - 100 (OSB 6, OSB 20) par pas de
# -82,5 — plus haut que le milieu.
_DEMI = 569 / 2 / 0.97
REPERES_X = reperes(110 - 569 / 2, 569 / 2 - 110, 5, _DEMI)
REPERES_Y = reperes(569 / 2 - 100, 569 / 2 - 100 - 4 * 82.5, 5, _DEMI, vers_le_bas=True)

PROFIL = Profil(
    id="a10c",
    libelle="A-10C Warthog",
    noms_dcs=("A-10C_2", "A-10C"),
    ecrans=(
        Ecran("mfcd_gauche", "MFCD gauche", "LEFT_MFCD", {"": 2}, _CADRE,
              reperes_x=REPERES_X, reperes_y=REPERES_Y),
        Ecran("mfcd_droit", "MFCD droit", "RIGHT_MFCD", {"": 3}, _CADRE,
              reperes_x=REPERES_X, reperes_y=REPERES_Y),
    ),
    kneeboard=100,
)
