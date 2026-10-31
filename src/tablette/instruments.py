"""Les instruments analogiques de tout appareil, redessinés sur la tablette.

Pour les warbirds sans écran, les hélicoptères, et en fait tout ce qui vole
dans DCS : un coup d'œil à l'iPad posé sur la cuisse, et la tête reste
dehors. Le script Lua envoie pour tout appareil, avec ou sans profil, les
données de vol de DCS (« vol », dcs.py) : vitesse indiquée, altitude,
assiette, cap, vitesse verticale, facteur de charge, bille, moteur, train.

Ce ne sont pas les instruments du module (leurs aiguilles, leurs pannes, leur
calage) : ce sont les grandeurs de vol de DCS, montrées dans les unités du
cockpit de l'appareil (`Instruments` de chaque profil) — mph et pieds pour un
P-51, km/h et mètres pour un Bf 109, nœuds et pieds pour un jet de l'OTAN.

Toute la géométrie (angles des aiguilles, graduations) se calcule ici : la
page n'a qu'à dessiner, et les tests vérifient les aiguilles.
"""
from __future__ import annotations

import math
import time
from dataclasses import astuple, dataclass
from typing import Callable, Dict, List, Optional

# Facteurs depuis les unités de DCS (Scripts/Export.lua : m/s, mètres, kg).
VITESSES = {"kt": 3600 / 1852, "mph": 3600 / 1609.344, "km/h": 3.6}
ALTITUDES = {"ft": 1 / 0.3048, "m": 1.0}
VARIOS = {"ft/min": 60 / 0.3048, "m/s": 1.0}
MASSES = {"lb": 1 / 0.45359237, "kg": 1.0}

BALAYAGE_BADIN = 320.0      # degrés de 0 à la vitesse maximale du cadran
BALAYAGE_G = 270.0          # cadran de facteur de charge, de g_min à g_max
DEBUT_G = -135.0
BALAYAGE_REGIME = 270.0     # compte-tours de 0 à 110 %
DEBUT_REGIME = -135.0
REGIME_MAX = 110.0
COURSE_VARIO = 170.0        # de 0 (à 9 h) à ± vario_max
VIRAGE_STANDARD = 3.0       # °/s : un virage au taux standard (2 minutes)
ANGLE_TAUX_STANDARD = 20.0  # l'aiguille de virage à ce taux, en degrés
LISSAGE_VIRAGE = 0.25       # part de la nouvelle mesure dans le taux affiché


@dataclass(frozen=True)
class Instruments:
    """Comment montrer les instruments d'un appareil : unités du cockpit et
    échelles des cadrans. Par défaut, un jet de l'OTAN."""
    vitesse: str = "kt"
    altitude: str = "ft"
    vario: str = "ft/min"
    carburant: str = "lb"
    vitesse_max: float = 800.0     # graduation la plus haute du badin
    vario_max: float = 6000.0      # dans l'unité du vario
    g_min: float = -3.0
    g_max: float = 9.0
    moteurs: int = 1
    helicoptere: bool = False      # hauteur sol en avant, plutôt que Mach


# Les familles, pour les profils : mêmes unités que le cockpit.
OTAN = Instruments()
WARBIRD_US = Instruments(vitesse="mph", vitesse_max=500.0, vario_max=4000.0, g_min=-4.0,
                         g_max=8.0)
WARBIRD_METRIQUE = Instruments(vitesse="km/h", altitude="m", vario="m/s", carburant="kg",
                               vitesse_max=800.0, vario_max=30.0, g_min=-4.0, g_max=8.0)
METRIQUE = Instruments(vitesse="km/h", altitude="m", vario="m/s", carburant="kg",
                       vitesse_max=1400.0, vario_max=100.0)
HELICO_KT = Instruments(vitesse_max=200.0, vario_max=4000.0, g_min=-1.0, g_max=4.0,
                        helicoptere=True)
HELICO_METRIQUE = Instruments(vitesse="km/h", altitude="m", vario="m/s", carburant="kg",
                              vitesse_max=350.0, vario_max=30.0, g_min=-1.0, g_max=4.0,
                              helicoptere=True)


# --------------------------------------------------------------- cadrans

def _pas(maximum: float) -> float:
    """Pas des chiffres d'un cadran : 8 à 10 chiffres, en valeurs rondes."""
    for pas in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000):
        if maximum / pas <= 10:
            return pas
    return maximum / 10


def angle_badin(vitesse: float, inst: Instruments) -> float:
    return max(0.0, min(vitesse, inst.vitesse_max)) / inst.vitesse_max * BALAYAGE_BADIN


def angle_vario(vario: float, inst: Instruments) -> float:
    p = max(-1.0, min(1.0, vario / inst.vario_max))
    return 270.0 + p * COURSE_VARIO


def angle_g(g: float, inst: Instruments) -> float:
    p = (max(inst.g_min, min(inst.g_max, g)) - inst.g_min) / (inst.g_max - inst.g_min)
    return DEBUT_G + p * BALAYAGE_G


def angle_regime(pourcent: float) -> float:
    return DEBUT_REGIME + max(0.0, min(pourcent, REGIME_MAX)) / REGIME_MAX * BALAYAGE_REGIME


def _chiffre(v: float) -> str:
    return f"{v:g}"


def cadrans(inst: Instruments) -> Dict:
    """Graduations des cadrans de cet appareil, en degrés (0 = midi, sens
    horaire), placées par les mêmes fonctions que les aiguilles : l'aiguille
    et son chiffre ne peuvent pas se contredire."""
    pas = _pas(inst.vitesse_max)
    badin = [{"texte": _chiffre(v), "angle": round(angle_badin(v, inst), 1)}
             for v in _plage(pas, inst.vitesse_max, pas)]
    # Trois ou quatre chiffres de chaque côté du zéro, zéro compris.
    pas_vario = next((p for p in (1, 2, 5, 10, 20, 25, 50, 500, 1000, 2000, 5000)
                      if inst.vario_max / p <= 4 and inst.vario_max % p == 0),
                     inst.vario_max / 4)
    echelle = 1000 if inst.vario == "ft/min" else 1     # chiffres en milliers de ft/min
    vario = [{"texte": _chiffre(abs(v) / echelle), "angle": round(angle_vario(v, inst), 1)}
             for v in _plage(-inst.vario_max, inst.vario_max, pas_vario)]
    pas_g = 1 if inst.g_max - inst.g_min <= 6 else 2
    debut_g = math.ceil(inst.g_min / pas_g) * pas_g      # chiffres pairs : -2, 0, 2…
    g = [{"texte": _chiffre(v), "angle": round(angle_g(v, inst), 1)}
         for v in _plage(debut_g, math.floor(inst.g_max / pas_g) * pas_g, pas_g)]
    regime = [{"texte": _chiffre(v), "angle": round(angle_regime(v), 1)}
              for v in _plage(0, 100, 20)]
    return {
        "cle": cle(inst),
        "unites": {"vitesse": inst.vitesse, "altitude": inst.altitude,
                   "vario": ("×1000 ft/min" if inst.vario == "ft/min" else inst.vario),
                   "carburant": inst.carburant},
        "moteurs": inst.moteurs,
        "helicoptere": inst.helicoptere,
        "badin": badin,
        "vario": vario,
        "g": g,
        "regime": regime,
        "altimetre": [{"texte": str(i), "angle": i * 36.0} for i in range(10)],
    }


def _plage(debut: float, fin: float, pas: float) -> List[float]:
    """De `debut` à `fin` au plus (750 km/h par 100 : jusqu'à 700)."""
    n = int(math.floor((fin - debut) / pas + 1e-9))
    return [round(debut + i * pas, 6) for i in range(n + 1)]


def cle(inst: Instruments) -> str:
    """Ce qui distingue ces cadrans d'autres : la page redemande les siens
    quand la lecture n'a plus la même (unités changées dans DCS)."""
    return "/".join(str(v) for v in astuple(inst))


# --------------------------------------------------------------- lecture

class TauxDeVirage:
    """Le taux de virage, tiré du cap reçu 20 fois par seconde, lissé :
    LoGetAngularVelocity donne une vitesse angulaire en axes avion, dont le
    signe varie selon les modules ; la dérivée du cap, elle, ne ment pas
    (positive en virage à droite)."""

    def __init__(self, horloge: Callable[[], float] = time.monotonic):
        self._horloge = horloge
        self._dernier: Optional[tuple] = None
        self.taux = 0.0          # °/s

    def mesurer(self, cap: float) -> float:
        maintenant = self._horloge()
        if self._dernier is not None:
            cap0, t0 = self._dernier
            dt = maintenant - t0
            if 0.01 < dt < 1.0:
                ecart = (cap - cap0 + 180.0) % 360.0 - 180.0
                self.taux += LISSAGE_VIRAGE * (ecart / dt - self.taux)
            elif dt >= 1.0:
                self.taux = 0.0
        self._dernier = (cap, maintenant)
        return self.taux


def _espace(n: float) -> str:
    """12 340 : séparateur de milliers lisible sur un petit écran."""
    return f"{n:,.0f}".replace(",", " ")


def lecture(vol: Optional[Dict[str, float]], inst: Instruments) -> Optional[Dict]:
    """Ce que montrent les instruments, aiguilles comprises ; None sans données.
    `vol["taux"]` : taux de virage en °/s, ajouté par dcs.py (TauxDeVirage)."""
    if not vol:
        return None
    d: Dict = {}
    if "vi" in vol:
        v = vol["vi"] * VITESSES[inst.vitesse]
        d["badin"] = {"angle": round(angle_badin(v, inst), 1), "texte": str(round(v))}
    if "alt" in vol:
        a = vol["alt"] * ALTITUDES[inst.altitude]
        # Grande aiguille : un tour pour 1000 (ft ou m) ; petite : 10 000.
        d["altimetre"] = {"angles": [round((a % 1000) / 1000 * 360, 1),
                                     round((a % 10000) / 10000 * 360, 1)],
                          "texte": _espace(a)}
    if "tang" in vol and "roul" in vol:
        d["horizon"] = {"assiette": round(math.degrees(vol["tang"]), 1),
                        "inclinaison": round(math.degrees(vol["roul"]), 1)}
    if "cap" in vol:
        cap = math.degrees(vol["cap"]) % 360.0
        d["cap"] = {"cap": round(cap, 1), "texte": f"{round(cap) % 360:03d}°"}
        taux = vol.get("taux", 0.0)
        d["virage"] = {"angle": round(max(-45.0, min(45.0, taux / VIRAGE_STANDARD
                                                      * ANGLE_TAUX_STANDARD)), 1),
                       "bille": round(max(-1.0, min(1.0, vol.get("bille", 0.0))), 3),
                       "texte": f"{taux:+.1f}°/s"}
    if "vz" in vol:
        z = vol["vz"] * VARIOS[inst.vario]
        d["vario"] = {"angle": round(angle_vario(z, inst), 1),
                      "texte": (_espace(round(z, -1)) if inst.vario == "ft/min"
                                else f"{z:+.1f}")}
    if "g" in vol:
        d["g"] = {"angle": round(angle_g(vol["g"], inst), 1), "texte": f"{vol['g']:.1f}"}
    regimes = [vol[c] for c in ("rpm1", "rpm2")[:max(1, inst.moteurs)] if c in vol]
    if regimes:
        d["regime"] = {"angles": [round(angle_regime(r), 1) for r in regimes],
                       "texte": " / ".join(f"{r:.0f}" for r in regimes)}
    d["bandeau"] = _bandeau(vol, inst)
    return d


def _bandeau(vol: Dict[str, float], inst: Instruments) -> List[Dict[str, str]]:
    """Les valeurs lues en chiffres, sous les cadrans."""
    b: List[Dict[str, str]] = []
    if inst.helicoptere and "sol" in vol:
        b.append({"titre": "HAUTEUR", "texte": f"{_espace(vol['sol'] * ALTITUDES[inst.altitude])} "
                                               f"{inst.altitude}"})
    if "mach" in vol and not inst.helicoptere and inst.vitesse == "kt":
        b.append({"titre": "MACH", "texte": f"{vol['mach']:.2f}"})
    if "inc" in vol:
        b.append({"titre": "INCIDENCE", "texte": f"{math.degrees(vol['inc']):.1f}°"})
    temperatures = [vol[c] for c in ("t1", "t2")[:max(1, inst.moteurs)] if c in vol]
    if temperatures:
        b.append({"titre": "TEMP. MOTEUR", "texte": " / ".join(f"{t:.0f}" for t in temperatures)
                  + " °C"})
    if "carb" in vol:
        b.append({"titre": "CARBURANT", "texte": f"{_espace(vol['carb'] * MASSES[inst.carburant])} "
                                                 f"{inst.carburant}"})
    if "train" in vol:
        t = vol["train"]
        b.append({"titre": "TRAIN", "texte": "SORTI" if t > 0.99 else "RENTRÉ" if t < 0.01
                  else "EN MOUVEMENT", "etat": "vert" if t > 0.99 else "" if t < 0.01 else "ambre"})
    if "volets" in vol:
        b.append({"titre": "VOLETS", "texte": f"{vol['volets'] * 100:.0f} %"})
    if vol.get("aerofreins", 0.0) > 0.01:
        b.append({"titre": "AÉROFREINS", "texte": f"{vol['aerofreins'] * 100:.0f} %",
                  "etat": "ambre"})
    return b
