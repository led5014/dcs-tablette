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
from . import Ecran, Profil, couronne_horaire

_OSB = tuple((str(n), 3000 + n) for n in range(1, 21))
_CADRE = couronne_horaire(5, "haut", _OSB)

PROFIL = Profil(
    id="a10c",
    libelle="A-10C Warthog",
    noms_dcs=("A-10C_2", "A-10C"),
    ecrans=(
        Ecran("mfcd_gauche", "MFCD gauche", "LEFT_MFCD", {"": 2}, _CADRE),
        Ecran("mfcd_droit", "MFCD droit", "RIGHT_MFCD", {"": 3}, _CADRE),
    ),
    kneeboard=100,
)
