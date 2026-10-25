"""OH-58D Kiowa Warrior : les MFD du copilote (gauche) et du pilote (droite).

Module non installé sur le poste où ce profil a été écrit : les numéros
viennent de DCS-BIOS (github.com/DCS-Skunkworks/dcs-bios,
Scripts/DCS-BIOS/lib/modules/aircraft_modules/OH-58D.lua) :
- MFD du pilote = appareil 11 (RMFD), du copilote = 23 (LMFD),
  KNEEBOARD = 51 ;
- « Line Address Key » L1–L5 = 3001–3005, B1–B4 = 3008–3011,
  R1–R5 = 3013–3017, INIT = 3019 ; pas de touche en haut.

Zones d'export : LEFT_MFCD et RIGHT_MFCD, d'après une configuration publiée
sur le forum DCS — pas confirmé par ED, à vérifier au premier vol.
"""
from . import Bouton, Ecran, Profil


def _cadre_mfd():
    boutons = []
    for i in range(1, 6):
        boutons.append(Bouton(f"L{i}", 3000 + i, "gauche", i - 1))
        boutons.append(Bouton(f"R{i}", 3012 + i, "droite", i - 1))
    for i in range(1, 5):
        boutons.append(Bouton(f"B{i}", 3007 + i, "bas", i - 1))
    boutons.append(Bouton("INIT", 3019, "rangee", 0))
    return tuple(boutons)


_CADRE = _cadre_mfd()

PROFIL = Profil(
    id="oh58d",
    libelle="OH-58D Kiowa",
    noms_dcs=("OH58D",),
    ecrans=(
        Ecran("mfd_gauche", "MFD gauche", "LEFT_MFCD", {"": 23}, _CADRE),
        Ecran("mfd_droit", "MFD droit", "RIGHT_MFCD", {"": 11}, _CADRE),
    ),
    kneeboard=51,
)
