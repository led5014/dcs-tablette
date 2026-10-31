"""Warbirds et avions de Corée : pas d'écran, des cadrans.

La tablette leur sert les instruments de base redessinés (instruments.py),
dans les unités de leur cockpit, et le kneeboard de DCS.

Noms dans DCS (LoGetSelfData().Name) relevés dans la liste des appareils de
DCS-BIOS (AircraftList.lua) et recoupés avec les définitions de CoreMods du
jeu installé ; attention à la casse et aux espaces (« F-86F Sabre »,
« FW-190A8 »). Unités d'après les manuels ED quand ils ont pu être lus
(P-51D, Fw 190 D-9, Mosquito), DCS-BIOS et DCS-ExportScripts sinon ; celles
du F4U (nœuds), de l'I-16 et du Yak-52 sont les moins sûres.

Commande des pages du kneeboard : seulement là où devices.lua a été relu
(TF-51D, Fw 190 D-9). Ailleurs le kneeboard s'affiche, ses pages se tournent
aux touches [ et ] : un mauvais numéro d'appareil appuierait autre chose.
"""
from dataclasses import replace

from ..instruments import METRIQUE, OTAN, WARBIRD_METRIQUE, WARBIRD_US
from . import Profil

# Badin américain de 0 à 700 mph, vario à ±6000 ft/min (manuel du P-51D) ;
# le P-47 a le même vario, d'après la course de son aiguille.
US_6000 = replace(WARBIRD_US, vitesse_max=700.0, vario_max=6000.0)

P51D = Profil(id="p51d", libelle="P-51D Mustang", noms_dcs=("P-51D", "P-51D-30-NA"),
              instruments=US_6000)

# devices.lua, KNEEBOARD = 29.
TF51D = Profil(id="tf51d", libelle="TF-51D Mustang", noms_dcs=("TF-51D",), kneeboard=29,
               instruments=US_6000)

P47 = Profil(id="p47", libelle="P-47D Thunderbolt",
             noms_dcs=("P-47D-30", "P-47D-30bl1", "P-47D-40"), instruments=US_6000)

# Le Corsair, de l'aéronavale : badin en nœuds, contrairement au P-47 et au P-51.
F4U = Profil(id="f4u", libelle="F4U-1D Corsair", noms_dcs=("F4U-1D", "F4U-1D_CW"),
             instruments=replace(WARBIRD_US, vitesse="kt", vitesse_max=450.0))

# Britanniques : mph et pieds, vario à ±4000 ft/min.
SPITFIRE = Profil(id="spitfire", libelle="Spitfire LF Mk IX",
                  noms_dcs=("SpitfireLFMkIX", "SpitfireLFMkIXCW"), instruments=WARBIRD_US)

MOSQUITO = Profil(id="mosquito", libelle="Mosquito FB Mk VI", noms_dcs=("MosquitoFBMkVI",),
                  instruments=replace(WARBIRD_US, moteurs=2))

# Allemands : km/h, mètres, vario à ±30 m/s.
BF109 = Profil(id="bf109", libelle="Bf 109 K-4", noms_dcs=("Bf-109K-4",),
               instruments=replace(WARBIRD_METRIQUE, vitesse_max=750.0))

# Badin du Fw 190 jusqu'à 900 km/h. devices.lua du D-9, KNEEBOARD = 18 ; celui
# de l'A-8 n'a pas été relu, d'où deux profils.
FW190D9 = Profil(id="fw190d9", libelle="Fw 190 D-9", noms_dcs=("FW-190D9",), kneeboard=18,
                 instruments=replace(WARBIRD_METRIQUE, vitesse_max=900.0))

FW190A8 = Profil(id="fw190a8", libelle="Fw 190 A-8", noms_dcs=("FW-190A8",),
                 instruments=replace(WARBIRD_METRIQUE, vitesse_max=900.0))

# Soviétiques.
I16 = Profil(id="i16", libelle="I-16", noms_dcs=("I-16",),
             instruments=replace(WARBIRD_METRIQUE, vitesse_max=600.0))

YAK52 = Profil(id="yak52", libelle="Yak-52", noms_dcs=("Yak-52",),
               instruments=replace(WARBIRD_METRIQUE, vitesse_max=450.0))

# Corée : le module complet et sa version simplifiée « FC ».
F86 = Profil(id="f86", libelle="F-86F Sabre", noms_dcs=("F-86F Sabre", "F-86F_FC"),
             instruments=replace(OTAN, vitesse_max=700.0))

MIG15 = Profil(id="mig15", libelle="MiG-15bis", noms_dcs=("MiG-15bis", "MiG-15bis_FC"),
               instruments=replace(METRIQUE, vitesse_max=1200.0, vario_max=75.0))

PROFILS = (P51D, TF51D, P47, F4U, SPITFIRE, MOSQUITO, BF109, FW190D9, FW190A8, I16, YAK52,
           F86, MIG15)
