"""C-130J-30 Super Hercules : trois HDD en image, et le kneeboard.

Module absent du poste de développement (01/11/2026) : rien n'a été relu
dans ses fichiers. Deux sources :
- une capture d'un pilote en vol, en mode essai de « Tablette DCS » (zones
  en bas de la vue) : le module dessine de lui-même dans LEFT_MFCD (le PFD),
  CENTER_MFCD (SYSTEM STATUS) et RIGHT_MFCD (moteurs et ACAWS), rien dans
  TEDAC. La capture annonçait « BLUE C-130J-30 », le nom du dossier de
  kneeboard du module ;
- DCS-BIOS (Scripts/DCS-BIOS/lib/modules/aircraft_modules/C-130J.lua) : nom
  « C-130J-30 », KNEEBOARD = 95, HDD001–HDD004 = 56–59.

Les quatre HDD n'ont pas de boutons autour : leurs pages se choisissent sur
les AMU (L1–L4, R1–R4), qui ne sont pas exportés. Les zones portent donc le
nom de leur place : lequel des quatre HDD sort dans chacune, et ce que montre
celui qui n'a pas de zone, n'est pas écrit — à voir au premier vol.

Sur la capture, le PFD déborde à gauche et le bas des pages est coupé : les
HDD sont plus hauts que larges, et la zone carrée n'en garde peut-être qu'une
partie. À confirmer sur la tablette.
"""
from dataclasses import replace

from ..instruments import OTAN
from . import Ecran, Profil
from ..langues import Texte

# Pas de bouton, pas de commande : aucun appareil DCS à viser.
PROFIL = Profil(
    id="c130j",
    libelle="C-130J Super Hercules",
    noms_dcs=("C-130J-30",),
    ecrans=(
        Ecran("hdd_gauche", Texte("HDD gauche"), "LEFT_MFCD", {}),
        Ecran("hdd_centre", Texte("HDD centre"), "CENTER_MFCD", {}),
        Ecran("hdd_droit", Texte("HDD droit"), "RIGHT_MFCD", {}),
    ),
    kneeboard=95,
    # Quatre moteurs, mais DCS n'en donne que deux régimes (left, right).
    instruments=replace(OTAN, vitesse_max=400.0, g_min=-1.0, g_max=3.0, moteurs=2),
)
