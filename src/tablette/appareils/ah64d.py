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
from . import Bouton, Ecran, Profil

DOSSIER_KNEEBOARD = "AH-64D_BLK_II"


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
              _CADRE, par_cote=6),
        Ecran("mpd_droit", "MPD droit", "RIGHT_MFCD", {"pilote": 43, "cpg": 45},
              _CADRE, par_cote=6),
        Ecran("tedac", "TEDAC", "TEDAC", {"cpg": 51}, (), par_cote=6),
    ),
    sieges=("pilote", "cpg"),
    kneeboard=84,
)
