"""Appareils sans écran exportable : la tablette leur sert le kneeboard et
les instruments de base redessinés (instruments.py).

Leurs cockpits sont à cadrans, ou leurs écrans n'ont pas de zone d'export
connue : rien à exporter en image. Le kneeboard de DCS s'y capture comme
ailleurs, et ses pages se tournent depuis l'iPad avec l'appareil KNEEBOARD
du module, là où il a été relu :

- MiG-29A Fulcrum (module complet, Mods/aircraft/MiG-29-Fulcrum) :
  devices.lua, KNEEBOARD = 59 ; nom dans DCS « MiG-29 Fulcrum », relevé dans
  les vols enregistrés par DCS Debrief ;
- cockpits FC3 (Su-25T, Su-33…) : pas de table `devices`, le kneeboard
  reçoit l'identifiant 100 (declare_kneeboard_device.lua), celui que
  common_keyboard_binding.lua utilise pour leurs touches [ et ].

Les autres modules ne sont pas installés sur le poste où ces profils ont été
écrits : noms relevés dans DCS-BIOS (AircraftList.lua) et recoupés avec les
définitions de CoreMods ; pas de commande de page (le kneeboard reste
affiché, pages aux touches [ et ]). Unités d'après DCS-BIOS et
DCS-ExportScripts ; celles du Mirage F1 et du C-101 sont déduites.
"""
from dataclasses import replace

from ..instruments import HELICO_KT, HELICO_METRIQUE, METRIQUE, OTAN
from . import Profil

# Option du module, « Avionics Units » : Metric (Native) ou Imperial (1).
MIG29 = Profil(id="mig29", libelle="MiG-29A Fulcrum", noms_dcs=("MiG-29 Fulcrum",),
               kneeboard=59, instruments=replace(METRIQUE, moteurs=2),
               imperial=(r'\["MiG29AvionicsUnits"\]\s*=\s*1\b', replace(OTAN, moteurs=2)))

# Hélicoptères à cadrans.
MI24P = Profil(id="mi24p", libelle="Mi-24P Hind", noms_dcs=("Mi-24P",),
               instruments=replace(HELICO_METRIQUE, moteurs=2))

MI8 = Profil(id="mi8", libelle="Mi-8MTV2", noms_dcs=("Mi-8MT",),
             instruments=replace(HELICO_METRIQUE, moteurs=2))

# Vario de la Gazelle gradué jusqu'à 800 m/min, soit 13 m/s.
SA342 = Profil(id="sa342", libelle="SA342 Gazelle",
               noms_dcs=("SA342M", "SA342L", "SA342Mistral", "SA342Minigun"),
               instruments=replace(HELICO_METRIQUE, vario_max=15.0))

UH1H = Profil(id="uh1h", libelle="UH-1H Huey", noms_dcs=("UH-1H",),
              instruments=replace(HELICO_KT, vitesse_max=150.0))

# Chasseurs de l'OTAN : nœuds et pieds.
F14 = Profil(id="f14", libelle="F-14 Tomcat",
             noms_dcs=("F-14A-95-GR", "F-14A-135-GR-Early", "F-14A-135-GR", "F-14B", "F-14BU"),
             instruments=replace(OTAN, moteurs=2))

F4E = Profil(id="f4e", libelle="F-4E Phantom II", noms_dcs=("F-4E-45MC",),
             instruments=replace(OTAN, moteurs=2))

M2000C = Profil(id="m2000c", libelle="Mirage 2000C", noms_dcs=("M-2000C",))

MIRAGE_F1 = Profil(id="mirage_f1", libelle="Mirage F1",
                   noms_dcs=("Mirage-F1CE", "Mirage-F1EE", "Mirage-F1BE"))

F5E = Profil(id="f5e", libelle="F-5E Tiger II", noms_dcs=("F-5E-3", "F-5E-3_FC"),
             instruments=replace(OTAN, moteurs=2))

# Avions d'école.
C101 = Profil(id="c101", libelle="C-101 Aviojet", noms_dcs=("C-101EB", "C-101CC"),
              instruments=replace(OTAN, vitesse_max=500.0))

MB339 = Profil(id="mb339", libelle="MB-339", noms_dcs=("MB-339A", "MB-339APAN"),
               instruments=replace(OTAN, vitesse_max=500.0))

# L-39 : « Avionics Language » sur English passe ses instruments en nœuds et
# pieds (option générale de DCS, onglet Gameplay).
L39 = Profil(id="l39", libelle="L-39 Albatros", noms_dcs=("L-39C", "L-39ZA"),
             instruments=replace(METRIQUE, vitesse_max=1000.0, vario_max=50.0),
             imperial=(r'\["avionicsLanguage"\]\s*=\s*"english"',
                       replace(OTAN, vitesse_max=550.0)))

# Chasseurs soviétiques et suédois : km/h et mètres.
MIG21 = Profil(id="mig21", libelle="MiG-21bis", noms_dcs=("MiG-21Bis",), instruments=METRIQUE)

MIG19 = Profil(id="mig19", libelle="MiG-19P", noms_dcs=("MiG-19P",),
               instruments=replace(METRIQUE, moteurs=2))

AJS37 = Profil(id="ajs37", libelle="AJS-37 Viggen", noms_dcs=("AJS37",), instruments=METRIQUE)

# Les cockpits FC3 en deux familles d'instruments : ceux de l'OTAN en nœuds
# et pieds (le MiG-29G de la Luftwaffe compris), les autres en km/h et
# mètres. Tous biréacteurs.
FC3 = Profil(
    id="fc3",
    libelle="Appareil FC3",
    noms_dcs=("Su-25T", "Su-33", "Su-27", "J-11A", "Su-25", "MiG-29A", "MiG-29S"),
    kneeboard=100,
    instruments=replace(METRIQUE, moteurs=2),
)

FC3_OTAN = Profil(
    id="fc3_otan",
    libelle="Appareil FC3 (OTAN)",
    noms_dcs=("F-15C", "A-10A", "MiG-29G"),
    kneeboard=100,
    instruments=replace(OTAN, moteurs=2),
)

PROFILS = (MIG29, MI24P, MI8, SA342, UH1H, F14, F4E, M2000C, MIRAGE_F1, F5E, C101, MB339, L39,
           MIG21, MIG19, AJS37, FC3, FC3_OTAN)
