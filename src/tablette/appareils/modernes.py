"""Appareils modernes à écrans exportables : AV-8B, F-15E, JF-17, Ka-50, et
le CH-47F (instruments et kneeboard, ses écrans ne sont pas encore sûrs).

Modules absents du poste de développement (31/10/2026) : rien n'a été relu
dans leurs fichiers. Les numéros viennent de deux sources indépendantes qui
concordent — DCS-BIOS (Scripts/DCS-BIOS/lib/modules/aircraft_modules/*.lua)
et les extractions DCSAutoMate des devices.lua, clickabledata.lua et
command_defs.lua du jeu ; les noms des zones d'export, des fichiers
d'indicateurs relevés par Helios et du sujet « How to set up your exports to
be aircraft specific » du forum ED. La PLACE des boutons autour de l'écran
est la moins sûre (jauges Helios, nommage) : à confirmer au premier vol, et
caler sur une capture comme le Hornet (`reperes_x`, `reperes_y`).
"""
from dataclasses import replace

from ..instruments import HELICO_KT, HELICO_METRIQUE, OTAN
from . import Bouton, Ecran, Profil, couronne_horaire

# AV-8B N/A : MPCD_LEFT = 26, MPCD_RIGHT = 27 ; boutons 1–20 = 3199 + n à
# gauche, 3223 + n à droite ; numérotés comme les DDI du Hornet (1 en bas du
# côté gauche, sens horaire) — jauge MFD-AV8B.cs de Helios. Zones d'export
# natives LEFT_MFCD, RIGHT_MFCD (MPCDL_init.lua, MPCDR_init.lua).
AV8B = Profil(
    id="av8b",
    libelle="AV-8B Harrier",
    noms_dcs=("AV8BNA",),
    ecrans=(
        Ecran("mpcd_gauche", "MPCD gauche", "LEFT_MFCD", {"": 26},
              couronne_horaire(5, "gauche", tuple((str(n), 3199 + n) for n in range(1, 21)))),
        Ecran("mpcd_droit", "MPCD droit", "RIGHT_MFCD", {"": 27},
              couronne_horaire(5, "gauche", tuple((str(n), 3223 + n) for n in range(1, 21)))),
    ),
    kneeboard=100,          # pas de KNEEBOARD dans devices.lua : 100 (declare_kneeboard_device.lua)
    instruments=replace(OTAN, vitesse_max=600.0),
)


def _cadre_f15e():
    """PB 1–20 = 3060 + n, les mêmes pour tous les écrans (mfdg_commands) ;
    sens antihoraire depuis le haut du côté gauche : gauche 1–5 de haut en
    bas, bas 6–10 de gauche à droite, droite 11–15 de bas en haut, haut
    16–20 de droite à gauche (jauge MPD.cs de Helios, parseur de DCS-BIOS)."""
    boutons = []
    for i in range(5):
        boutons.append(Bouton(str(1 + i), 3061 + i, "gauche", i))
        boutons.append(Bouton(str(6 + i), 3066 + i, "bas", i))
        boutons.append(Bouton(str(15 - i), 3075 - i, "droite", i))
        boutons.append(Bouton(str(20 - i), 3080 - i, "haut", i))
    return tuple(boutons)


# F-15E : place avant seulement — MPD_FLEFT = 34, MPCD_FCENTER = 35,
# MPD_FRIGHT = 36, zones LEFT_MFCD, CENTER_MFCD, RIGHT_MFCD (Bake_FCL, FCC,
# FCR). La place arrière partage LEFT/RIGHT_MFCD sans qu'on sache ce qui s'y
# dessine : pas de siège WSO tant que ce n'est pas vérifié.
F15E = Profil(
    id="f15e",
    libelle="F-15E Strike Eagle",
    noms_dcs=("F-15ESE",),
    ecrans=(
        Ecran("mpd_gauche", "MPD gauche", "LEFT_MFCD", {"": 34}, _cadre_f15e()),
        Ecran("mpd_droit", "MPD droit", "RIGHT_MFCD", {"": 36}, _cadre_f15e()),
        Ecran("mpcd", "MPCD", "CENTER_MFCD", {"": 35}, _cadre_f15e()),
    ),
    kneeboard=100,          # 68 y est l'IFF, pas le kneeboard
    instruments=replace(OTAN, moteurs=2),
)


def _cadre_jf17(u: int, l: int, r: int, d: int):
    """U1–U5 en haut, D1–D5 en bas (de gauche à droite), L1–L8 et R1–R8 sur
    les côtés (de haut en bas) : le côté est dans le nom, sûr ; l'ordre est
    probable (Hoggit : les pages secondaires utilisent « the lower 3 »)."""
    return tuple(
        [Bouton(f"U{i + 1}", u + i, "haut", i) for i in range(5)]
        + [Bouton(f"D{i + 1}", d + i, "bas", i) for i in range(5)]
        + [Bouton(f"L{i + 1}", l + i, "gauche", i) for i in range(8)]
        + [Bouton(f"R{i + 1}", r + i, "droite", i) for i in range(8)])


# JF-17 : un seul appareil MFCD = 47 pour les trois écrans, chacun ses
# numéros. Écrans en portrait, environ 422 × 563 (modèle Helios « DEKA_JF-17 »).
# DCS cherche JF17_LEFT_MFCD puis LEFT_MFCD (deux arguments) : les zones
# génériques suffisent. Comment DCS dessine un écran en portrait dans la zone
# carrée de « Tablette DCS » n'est pas vérifié : à regarder au premier vol.
_JF17 = dict(par_cote=5, par_cote_y=8, aspect=422 / 563)
JF17 = Profil(
    id="jf17",
    libelle="JF-17 Thunder",
    noms_dcs=("JF-17",),
    ecrans=(
        Ecran("mfcd_gauche", "MFCD gauche", "LEFT_MFCD", {"": 47},
              _cadre_jf17(3238, 3244, 3252, 3262), **_JF17),
        Ecran("mfcd_droit", "MFCD droit", "RIGHT_MFCD", {"": 47},
              _cadre_jf17(3304, 3310, 3318, 3326), **_JF17),
        Ecran("mfcd_centre", "MFCD centre", "CENTER_MFCD", {"": 47},
              _cadre_jf17(3271, 3277, 3285, 3293), **_JF17),
    ),
    kneeboard=100,
    instruments=replace(OTAN, vitesse_max=900.0),
)

# Ka-50 (II et III) : le Shkval (SHKVAL = 8) n'a pas de boutons autour, ses
# réglages sont sur un autre panneau ; l'ABRIS (ABRIS = 9) a ses cinq
# boutons en rangée sous l'écran, 3001–3005. Zones : « Shkval » puis
# LEFT_MFCD, « ABRIS » puis RIGHT_MFCD (SHKVAL/BAKE/init.lua, ABRIS/BAKE/init.lua).
# Kneeboard : appareil 100, pages 3001 / 3002 (raccourcis du module).
KA50 = Profil(
    id="ka50",
    libelle="Ka-50 Black Shark",
    noms_dcs=("Ka-50", "Ka-50_3"),
    ecrans=(
        Ecran("shkval", "Shkval", "LEFT_MFCD", {"": 8}, ()),
        Ecran("abris", "ABRIS", "RIGHT_MFCD", {"": 9},
              tuple(Bouton(str(n), 3000 + n, "rangee", n - 1) for n in range(1, 6))),
    ),
    kneeboard=100,
    instruments=replace(HELICO_METRIQUE, moteurs=2),
)

# CH-47F : KNEEBOARD = 68 (devices.lua). Seul RIGHT_MFCD est sûr comme zone
# d'export native, sans savoir lequel des cinq MFD il montre (le MFD
# extérieur du pilote, d'après les fichiers où les autres sont commentés) :
# pas d'écran tant que ce n'est pas vu en vol.
CH47F = Profil(
    id="ch47f",
    libelle="CH-47F Chinook",
    noms_dcs=("CH-47Fbl1",),
    kneeboard=68,
    instruments=replace(HELICO_KT, moteurs=2),
)
