"""La planche avant du Hornet, redessinée sur la tablette à partir des données.

Ces éléments-là ne s'exportent pas en image (DCS n'a de zone d'export que
pour les deux DDI et l'AMPCD). Le script Lua en envoie donc le CONTENU :

- le texte de l'UFC et de l'IFEI, tel que `list_indication` le rend ;
- la position des aiguilles et l'état des voyants, `get_argument_value`.

Tous les numéros viennent des scripts du module (Mods/aircraft/FA-18C/
Cockpit/Scripts) : device_init.lua pour l'ordre des indicateurs,
command_defs.lua et clickabledata.lua pour l'UFC, mainpanel_init.lua pour
les aiguilles, MainPanel/lamps.lua pour les voyants. tests/test_tablette.py
les relit dans l'installation quand elle est présente.

Laissés de côté, trop incertains : le RWR (DCS donne ses symboles, pas leur
position) et le HUD.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from typing import Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------- écrans texte

IND_IFEI = 5          # rang dans la liste `indicators` de device_init.lua
IND_UFC = 6


def lire_indication(texte: str) -> Dict[str, str]:
    """Champs d'un `list_indication` : nom de l'élément → texte affiché.

    Le format : des blocs séparés par une ligne de tirets, le nom sur la
    première ligne, la valeur sur les suivantes ; « children are { » et « } »
    ne sont que de la structure. Un nom répété reçoit « __id:N » : on l'ôte.
    """
    champs: Dict[str, str] = {}
    for bloc in re.split(r"^-{8,}\s*$", texte, flags=re.M):
        lignes = [l for l in bloc.strip("\r\n").splitlines()
                  if l.strip() not in ("children are {", "}")]
        if not lignes:
            continue
        nom = re.sub(r"__id:\d+$", "", lignes[0].strip())
        if nom:
            champs[nom] = "\n".join(lignes[1:]).rstrip()
    return champs


def ufc(champs: Dict[str, str]) -> Dict:
    """Ce que montre l'UFC : bloc-notes, cinq options, deux canaux COMM."""
    return {
        "bloc": [champs.get("UFC_ScratchPadString1Display", ""),
                 champs.get("UFC_ScratchPadString2Display", ""),
                 champs.get("UFC_ScratchPadNumberDisplay", "")],
        "options": [{"repere": champs.get(f"UFC_OptionCueing{i}", ""),
                     "texte": champs.get(f"UFC_OptionDisplay{i}", "")} for i in range(1, 6)],
        "comm1": champs.get("UFC_Comm1Display", ""),
        "comm2": champs.get("UFC_Comm2Display", ""),
    }


# Champs de l'IFEI repris tels quels ; les libellés (« RPM », « TEMP »…) sont
# dessinés par la page.
CHAMPS_IFEI = {
    "rpm_g": "txt_RPM_L", "rpm_d": "txt_RPM_R",
    "temp_g": "txt_TEMP_L", "temp_d": "txt_TEMP_R",
    "ff_g": "txt_FF_L", "ff_d": "txt_FF_R",
    "huile_g": "txt_OilPress_L", "huile_d": "txt_OilPress_R",
    "carburant_haut": "txt_FUEL_UP", "carburant_bas": "txt_FUEL_DOWN",
    "bingo": "txt_BINGO", "codes": "txt_Codes", "sp": "txt_SP",
    "horloge_h": "txt_CLOCK_H", "horloge_m": "txt_CLOCK_M", "horloge_s": "txt_CLOCK_S",
    "chrono_h": "txt_TIMER_H", "chrono_m": "txt_TIMER_M", "chrono_s": "txt_TIMER_S",
}


def ifei(champs: Dict[str, str]) -> Dict[str, str]:
    return {cle: champs.get(nom, "") for cle, nom in CHAMPS_IFEI.items()}


# --------------------------------------------------------------- touches UFC

UFC = 25              # devices.lua
# command_defs.lua, UFC_commands (start_command + rang) ; boutons qu'on
# enfonce et relâche, comme ceux des DDI.
TOUCHES_UFC: Dict[str, int] = {
    "AP": 3001, "IFF": 3002, "TCN": 3003, "ILS": 3004, "DL": 3005, "BCN": 3006,
    "ONOFF": 3007, "COMM1_TIRER": 3008, "COMM2_TIRER": 3009,
    "OPT1": 3010, "OPT2": 3011, "OPT3": 3012, "OPT4": 3013, "OPT5": 3014,
    "IP": 3015, "EMCON": 3017,
    "0": 3018, "1": 3019, "2": 3020, "3": 3021, "4": 3022,
    "5": 3023, "6": 3024, "7": 3025, "8": 3026, "9": 3027,
    "CLR": 3028, "ENT": 3029,
}
# Molettes de canal : un cran = ±0,2 sur la commande de rotation
# (clickabledata.lua, default_button_axis_tumb, gain 0.2, relatif).
MOLETTES_UFC: Dict[str, int] = {"COMM1": 3033, "COMM2": 3034}
CRAN_MOLETTE = 0.2


# --------------------------------------------------------------- aiguilles

def _interpoler(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    """Interpolation linéaire par morceaux ; xs croissants."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect_right(xs, x) - 1
    t = (x - xs[i]) / (xs[i + 1] - xs[i])
    return ys[i] + t * (ys[i + 1] - ys[i])


def _vers_valeur(arg: float, valeurs: Sequence[float], positions: Sequence[float]) -> float:
    """Position d'aiguille → grandeur : la table du cockpit, lue à l'envers."""
    if positions[0] > positions[-1]:
        valeurs, positions = valeurs[::-1], positions[::-1]
    return _interpoler(arg, list(positions), list(valeurs))


def _vers_position(valeur: float, valeurs: Sequence[float], positions: Sequence[float]) -> float:
    return _interpoler(valeur, list(valeurs), list(positions))


# mainpanel_init.lua : (argument, grandeurs, positions d'aiguille).
BADIN = (217, (0.0, 60.0, 100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0,
               500.0, 550.0, 600.0, 650.0, 700.0, 750.0, 800.0, 850.0),
         (0.0, 0.0445, 0.15, 0.348, 0.586, 0.636, 0.673, 0.715, 0.748, 0.782,
          0.819, 0.849, 0.870, 0.898, 0.922, 0.950, 0.976, 1.0))
VARIO = (225, (-6000.0, -4000.0, -3000.0, -2000.0, -1000.0, -500.0, 0.0, 500.0,
               1000.0, 2000.0, 3000.0, 4000.0, 6000.0),
         (-1.0, -0.83, -0.73, -0.605, -0.40, -0.22, 0.0, 0.22, 0.40, 0.605, 0.73, 0.83, 1.0))
ALTI_CENTAINES = 218          # aiguille : 0..1 = 0..1000 ft
ALTI_MILLIERS = 219           # tambour : 0..1 = 0..10
ALTI_DIZAINES_MILLIERS = 220  # tambour : 0..1 = 0..9
CALAGE = (221, 222, 223)      # tambours du calage : centièmes, dixièmes, 26..31 inHg
SAI_ASSIETTE = (205, (-90.0, 90.0), (-1.0, 1.0))      # degrés
SAI_INCLINAISON = (206, (-180.0, 180.0), (-1.0, 1.0))
SAI_VIRAGE = (208, (-4.5, 4.5), (1.0, -1.0))
SONDE = (286, (-10.0, 0.0, 100.0, 200.0, 300.0, 400.0, 600.0, 800.0, 1000.0, 3000.0,
               5000.0, 5100.0),
         (0.0, 0.048, 0.171, 0.296, 0.416, 0.530, 0.616, 0.706, 0.799, 0.886, 0.974, 0.98))
HYD_GAUCHE = (310, (0.0, 5000.0), (0.0, 1.0))
HYD_DROITE = (311, (0.0, 5000.0), (0.0, 1.0))
FREIN = (242, (0.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0),
         (0.0, 0.036, 0.338, 0.636, 0.924, 1.0))

# MainPanel/lamps.lua : libellé du voyant → argument.
VOYANTS: Dict[str, int] = {
    "MASTER CAUTION": 13, "FIRE G": 10, "FIRE D": 26, "APU FIRE": 29,
    "GO": 15, "NO GO": 16, "L BLEED": 17, "R BLEED": 18, "SPD BRK": 19,
    "STBY": 20, "REC": 22, "XMIT": 24, "ASPJ OH": 25, "RCDR ON": 31, "DISP": 32,
    "SAM": 38, "AI": 39, "AAA": 40, "CW": 41,
    "CK SEAT": 298, "APU ACC": 299, "BATT SW": 300, "FCS HOT": 301, "GEN TIE": 302,
    "FUEL LO": 304, "FCES": 305, "L GEN": 307, "R GEN": 308,
    "NOSE": 166, "LEFT": 165, "RIGHT": 167, "HALF": 163, "FULL": 164, "FLAPS": 162,
    "TRAIN": 227, "HOOK": 294, "LOCK": 1, "SHOOT": 2,
    "A/A": 47, "A/G": 48, "READY": 44, "DISCH": 45, "APU READY": 376,
    "AOA HAUT": 4, "AOA CENTRE": 5, "AOA BAS": 6, "ALT BASSE": 290,
}
SEUIL_VOYANT = 0.3

ARGUMENTS: List[int] = sorted(
    {BADIN[0], VARIO[0], ALTI_CENTAINES, ALTI_MILLIERS, ALTI_DIZAINES_MILLIERS, *CALAGE,
     SAI_ASSIETTE[0], SAI_INCLINAISON[0], SAI_VIRAGE[0], SONDE[0], HYD_GAUCHE[0],
     HYD_DROITE[0], FREIN[0], *VOYANTS.values()})


def instruments(args: Dict[int, float]) -> Optional[Dict]:
    """Grandeurs lues sur les aiguilles, avec la position brute de chacune
    (0..1 ou −1..1) pour que la page la place sur son cadran."""
    if not args:
        return None

    def a(n: int) -> float:
        return float(args.get(n, 0.0))

    def lu(table) -> Dict:
        n, valeurs, positions = table
        return {"valeur": round(_vers_valeur(a(n), valeurs, positions), 1), "position": a(n)}

    # Altitude : tambours pour les dizaines de milliers et les milliers,
    # aiguille pour les centaines (un tour = 1000 ft).
    centaines = a(ALTI_CENTAINES) * 1000.0
    milliers = round(a(ALTI_MILLIERS) * 10.0) % 10
    dizaines = round(a(ALTI_DIZAINES_MILLIERS) * 9.0)
    calage = (round(26.0 + 5.0 * a(CALAGE[2])) + (round(a(CALAGE[1]) * 10.0) % 10) / 10.0
              + (round(a(CALAGE[0]) * 10.0) % 10) / 100.0)
    return {
        "badin": lu(BADIN),
        "vario": lu(VARIO),
        "altimetre": {"valeur": round(dizaines * 10000 + milliers * 1000 + centaines),
                      "position": a(ALTI_CENTAINES), "calage": round(calage, 2)},
        "sai": {"assiette": round(_vers_valeur(a(SAI_ASSIETTE[0]), *SAI_ASSIETTE[1:]), 1),
                "inclinaison": round(_vers_valeur(a(SAI_INCLINAISON[0]),
                                                  *SAI_INCLINAISON[1:]), 1),
                "virage": round(_vers_valeur(a(SAI_VIRAGE[0]), *SAI_VIRAGE[1:]), 2)},
        "sonde": lu(SONDE),
        "hydraulique": {"gauche": lu(HYD_GAUCHE), "droite": lu(HYD_DROITE)},
        "frein": lu(FREIN),
    }


def voyants(args: Dict[int, float]) -> Optional[Dict[str, bool]]:
    if not args:
        return None
    return {nom: float(args.get(n, 0.0)) > SEUIL_VOYANT for nom, n in VOYANTS.items()}


# --------------------------------------------------------------- cadrans

def _graduations(table, valeurs: Sequence[float], angle) -> List[Dict]:
    _, grandeurs, positions = table
    return [{"texte": f"{v:g}", "angle": round(angle(_vers_position(v, grandeurs, positions)), 1)}
            for v in valeurs]


def cadrans() -> Dict:
    """Graduations des cadrans, en degrés (0 = midi, sens horaire), placées
    avec les mêmes tables que les aiguilles : l'aiguille et son chiffre ne
    peuvent pas se contredire. La page n'a qu'à dessiner."""
    tour = lambda p: p * 360.0                     # cadran d'un tour complet
    vario = lambda p: 270.0 + p * 170.0            # zéro à 9 h, ±6000 vers 3 h
    pression = lambda p: -135.0 + p * 270.0        # 0..5000 psi sur trois quarts
    return {
        "badin": {"aiguille": "tour", "graduations": _graduations(
            BADIN, (100, 150, 200, 300, 400, 500, 600, 700, 800), tour)},
        "vario": {"aiguille": "vario", "graduations": [
            {"texte": texte, "angle": round(vario(_vers_position(v, *VARIO[1:])), 1)}
            for texte, v in (("6", -6000), ("4", -4000), ("2", -2000), ("1", -1000),
                             (".5", -500), ("0", 0), (".5", 500), ("1", 1000),
                             ("2", 2000), ("4", 4000), ("6", 6000))]},
        "altimetre": {"aiguille": "tour", "graduations": [
            {"texte": str(i), "angle": i * 36.0} for i in range(10)]},
        "sonde": {"aiguille": "tour", "graduations": _graduations(
            SONDE, (0, 100, 200, 300, 400, 600, 800, 1000, 3000, 5000), tour)},
        "pression": {"aiguille": "pression", "graduations": [
            {"texte": str(i), "angle": round(pression(i / 5.0), 1)} for i in range(6)]},
        # Aiguille : angle = départ + position × course.
        "angles": {"tour": [0.0, 360.0], "vario": [270.0, 170.0], "pression": [-135.0, 270.0]},
    }
