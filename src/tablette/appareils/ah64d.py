"""AH-64D Apache : les deux MPD du siège occupé, et le TEDAC.

Mods/aircraft/AH-64D/Cockpit/Scripts (copie dans le dépôt : AH-64D/) :
- devices.lua : MFD_PLT_LEFT = 42, MFD_PLT_RIGHT = 43, MFD_CPG_LEFT = 44,
  MFD_CPG_RIGHT = 45, TEDAC = 51, KNEEBOARD = 84 ;
- command_defs.lua, mpd_commands depuis start_command : T1–T6 = 3001–3006,
  R1–R6 = 3007–3012, B6–B1 = 3013–3018, L6–L1 = 3019–3024, * = 3025,
  VID = 3026, COM = 3027, A/C = 3028, TSD = 3029, WPN = 3030, FCR = 3031 ;
- zones d'export : LEFT_MFCD et RIGHT_MFCD pour les MPD des deux sièges
  (Displays/MFD/indicator/LCD/MFD_LCD.lua), TEDAC pour le TEDAC.

Position des boutons : les arguments 3D de clickabledata.lua font le tour du
cadre dans le sens horaire (T de gauche à droite, R de haut en bas, puis B6…B1
et L6…L1) : B1 (M, le menu) est donc en bas à gauche, L1 en haut à gauche.

Le siège n'est publié nulle part dans les données d'export : la tablette le
demande au pilote (Pilote / CPG). DCS montre les MPD du siège occupé ; les
boutons, eux, appartiennent à un siège précis.
"""
from dataclasses import replace

from ..instruments import HELICO_KT
from . import Bouton, Ecran, Profil, reperes

DOSSIER_KNEEBOARD = "AH-64D_BLK_II"

# Où sont les libellés : Displays/MFD/indicator/MFD_PB_Defs.lua, en pixels
# d'un écran de 1024 (MFD_Page_Defs.lua, display_size_pix), centre 0, y vers
# le haut. T et B : x de -335 (T1, B1) à 320 ; L et R : y de 330 (L1, R1) à
# -280. Les libellés n'occupent pas toute la largeur : répartis également,
# les boutons des bouts tombaient à côté.
REPERES_X = reperes(-335, 320, 6, 512)
REPERES_Y = reperes(330, -280, 6, 512, vers_le_bas=True)


def _cadre_mpd():
    boutons = []
    for i in range(1, 7):
        boutons.append(Bouton(f"T{i}", 3000 + i, "haut", i - 1))
        boutons.append(Bouton(f"R{i}", 3006 + i, "droite", i - 1))
        boutons.append(Bouton(f"B{i}", 3019 - i, "bas", i - 1))
        boutons.append(Bouton(f"L{i}", 3025 - i, "gauche", i - 1))
    # Touches fixes, rangées sous le cadre.
    for rang, (id_, commande) in enumerate((("FCR", 3031), ("WPN", 3030), ("TSD", 3029),
                                            ("VID", 3026), ("COM", 3027), ("A/C", 3028),
                                            ("*", 3025))):
        boutons.append(Bouton(id_, commande, "rangee", rang))
    return tuple(boutons)


_CADRE = _cadre_mpd()

PROFIL = Profil(
    id="ah64d",
    libelle="AH-64D Apache",
    noms_dcs=("AH-64D_BLK_II",),
    ecrans=(
        Ecran("mpd_gauche", "MPD gauche", "LEFT_MFCD", {"pilote": 42, "cpg": 44},
              _CADRE, par_cote=6, reperes_x=REPERES_X, reperes_y=REPERES_Y),
        Ecran("mpd_droit", "MPD droit", "RIGHT_MFCD", {"pilote": 43, "cpg": 45},
              _CADRE, par_cote=6, reperes_x=REPERES_X, reperes_y=REPERES_Y),
        Ecran("tedac", "TEDAC", "TEDAC", {"cpg": 51}, (), par_cote=6),
    ),
    sieges=("pilote", "cpg"),
    kneeboard=84,
    instruments=replace(HELICO_KT, moteurs=2),
)
