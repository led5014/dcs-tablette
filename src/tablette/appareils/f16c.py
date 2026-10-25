"""F-16C Viper : les deux MFD et leurs 20 OSB.

Module non installé sur le poste où ce profil a été écrit : les numéros
viennent de DCS-BIOS (github.com/DCS-Skunkworks/dcs-bios,
Scripts/DCS-BIOS/lib/modules/aircraft_modules/F-16C_50.lua), qui les relève
dans les scripts du module :
- MFD gauche = appareil 24, MFD droit = 25 ; « MFD Left Button n » = 3000 + n ;
- OSB numérotés dans le sens horaire depuis la gauche du haut, comme sur
  l'avion (1–5 en haut, 6–10 à droite, 11–15 en bas, 16–20 à gauche).

Zones d'export : LEFT_MFCD et RIGHT_MFCD, la convention des MFD dans DCS.

Le numéro de l'appareil KNEEBOARD n'est pas dans DCS-BIOS : sans lui, la
tablette ne tourne pas les pages (une commande au mauvais appareil pourrait
actionner autre chose) ; le kneeboard reste affiché, pages aux touches [ et ].
"""
from . import Ecran, Profil, couronne_horaire

_OSB = tuple((str(n), 3000 + n) for n in range(1, 21))
_CADRE = couronne_horaire(5, "haut", _OSB)

PROFIL = Profil(
    id="f16c",
    libelle="F-16C Viper",
    noms_dcs=("F-16C_50",),
    ecrans=(
        Ecran("mfd_gauche", "MFD gauche", "LEFT_MFCD", {"": 24}, _CADRE),
        Ecran("mfd_droit", "MFD droit", "RIGHT_MFCD", {"": 25}, _CADRE),
    ),
)
