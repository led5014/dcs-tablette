"""Appareils sans écran exportable : la tablette leur sert le kneeboard.

Leurs cockpits sont à cadrans : rien à exporter en image. Le kneeboard de
DCS s'y capture comme ailleurs, et ses pages se tournent depuis l'iPad avec
l'appareil KNEEBOARD de chaque module :

- MiG-29A Fulcrum (module complet, Mods/aircraft/MiG-29-Fulcrum) :
  devices.lua, KNEEBOARD = 59 ; nom dans DCS « MiG-29 Fulcrum », relevé dans
  les vols enregistrés par DCS Debrief ;
- TF-51D : devices.lua, KNEEBOARD = 29 ;
- cockpits FC3 (Su-25T, Su-33…) : pas de table `devices`, le kneeboard
  reçoit l'identifiant 100 (declare_kneeboard_device.lua), celui que
  common_keyboard_binding.lua utilise pour leurs touches [ et ].
"""
from . import Profil

MIG29 = Profil(id="mig29", libelle="MiG-29A Fulcrum", noms_dcs=("MiG-29 Fulcrum",),
               kneeboard=59)

TF51D = Profil(id="tf51d", libelle="TF-51D Mustang", noms_dcs=("TF-51D",), kneeboard=29)

# Hélicoptères à cadrans de l'escadron. Modules non installés sur le poste où
# ces profils ont été écrits : noms relevés dans DCS-BIOS (Mi-24P.lua,
# SA342.lua) ; leur appareil KNEEBOARD n'y figure pas, donc pas de commande
# de page (le kneeboard reste affiché, pages aux touches [ et ]).
MI24P = Profil(id="mi24p", libelle="Mi-24P Hind", noms_dcs=("Mi-24P",))

SA342 = Profil(id="sa342", libelle="SA342 Gazelle",
               noms_dcs=("SA342M", "SA342L", "SA342Mistral", "SA342Minigun"))

FC3 = Profil(
    id="fc3",
    libelle="Appareil FC3",
    noms_dcs=("Su-25T", "Su-33", "Su-27", "J-11A", "F-15C", "A-10A", "Su-25",
              "MiG-29A", "MiG-29S", "MiG-29G"),
    kneeboard=100,
)
