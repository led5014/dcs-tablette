"""OH-58D Kiowa Warrior : les MFD du copilote (gauche) et du pilote (droite).

Module absent du poste de développement (seule son IA est dans CoreMods) :
les numéros viennent de DCS-BIOS (github.com/DCS-Skunkworks/dcs-bios,
Scripts/DCS-BIOS/lib/modules/aircraft_modules/OH-58D.lua) :
- MFD du pilote = appareil 11 (RMFD), du copilote = 23 (LMFD),
  KNEEBOARD = 51 ;
- « Line Address Key » L1–L5 = 3001–3005, B1–B4 = 3008–3011,
  R1–R5 = 3013–3017, INIT = 3019 ; pas de touche en haut.

Zones d'export natives LEFT_MFCD et RIGHT_MFCD (Cockpit/MFDs/Indicator/
initLMFD.lua et initRMFD.lua, relevé publié sur le forum DCS) ; nom DCS
« OH58D » (CoreMods/aircraft/OH-58D/OH58D.lua).

Les MFD sont en 4:3 : 500 × 375 dans le modèle Helios « OH58D », et
752 × 576 ou 900 × 645 chez les pilotes du forum qui les exportent. Dans
une zone carrée, DCS les étire en hauteur et en coupe le haut (bandeau TQ,
RPM… au-dessus du cap) et un peu les bords — vu sur la tablette en 1.11.1,
et signalé sur le forum avec des MFD WinWing. Le fichier « Tablette DCS »
leur donne donc des zones 4:3, dans sa fonction reconfigure_for_unit
(ecrans_dcs.py).

Repères mesurés sur une photo de la tablette en 1.11.1, pages INITIAL
PAGE 1 et HVR (retour de vol : boutons pas en face des libellés) :
- en bas, les onglets B1–B4 sont deux à gauche, deux à droite (HVR, HSD …
  MMS, COMM) ; la tablette les répartissait également, B3 sous le vide ;
- sur les côtés, les libellés L1–L5 et R1–R5 ne descendent pas aussi près
  des bords que des boutons également répartis.
Zone encore carrée sur cette photo, image étirée et rognée : repères
corrigés de ce rognage, à affiner sur une photo en 4:3.
"""
from ..instruments import HELICO_KT
from . import Bouton, Ecran, Profil
from ..langues import Texte


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
# Quatre boutons en bas, cinq sur les côtés, verre 4:3.
_MFD = dict(par_cote=4, par_cote_y=5, aspect=4 / 3,
            reperes_x=(0.11, 0.255, 0.71, 0.86),
            reperes_y=(0.17, 0.345, 0.515, 0.685, 0.86))

PROFIL = Profil(
    id="oh58d",
    libelle="OH-58D Kiowa",
    noms_dcs=("OH58D",),
    ecrans=(
        Ecran("mfd_gauche", Texte("MFD gauche"), "LEFT_MFCD", {"": 23}, _CADRE, **_MFD),
        Ecran("mfd_droit", Texte("MFD droit"), "RIGHT_MFCD", {"": 11}, _CADRE, **_MFD),
    ),
    kneeboard=51,
    instruments=HELICO_KT,
)
