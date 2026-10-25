"""Les images des écrans exportés et du kneeboard, à la demande de la tablette.

Pas de capture en continu : on ne copie que ce que la page affiche en ce
moment (un écran réclamé depuis moins d'une seconde). Une tablette rangée ou
réglée sur deux DDI ne fait pas copier l'AMPCD pour rien. Une même copie sert
à tous les écrans demandés dans la foulée.

Quand il n'y a pas d'image à donner, on dit pourquoi (DCS absent, écrans non
exportés, fenêtre trop petite, plein écran exclusif, kneeboard fermé) plutôt
que de servir un carré noir muet.
"""
from __future__ import annotations

import io
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from PIL import Image

from .copie import Copie, Rect, dans, zone_temoin
from .ecrans_dcs import (PasDExport, fichier_actif, options_affichage, zone_kneeboard,
                         zones_actives)

KNEEBOARD = "KNEEBOARD"
TEMOIN = "TEMOIN"

# Les écrans du Hornet sont des traits fins et verts sur du noir. Le JPEG
# ordinaire divise par quatre la résolution des couleurs (4:2:0) : le vert
# bave, pâlit, et l'écran paraît éteint. On garde toutes les couleurs.
QUALITE_JPEG = 85
SOUS_ECHANTILLONNAGE = 0         # 4:4:4
COTE_MAX = 1100                  # au-delà, l'iPad ne verrait pas la différence
FRAICHEUR_S = 1 / 30             # une copie sert tous les écrans demandés
DEMANDE_RECENTE_S = 1.0          # un écran réclamé depuis moins longtemps est copié
VALIDITE_ZONES_S = 2.0           # options.lua n'est relu qu'une fois toutes les 2 s
SEUIL_NOIR = 8                   # luminosité max sous laquelle une image est noire
# DCS dessine les écrans du Hornet arrondis (rayon ≈ 1/6 du côté, mesuré) et
# laisse un liseré du cockpit sur les bords : on le rogne. Rogner davantage
# couperait les libellés des boutons, collés au bord ; les coins arrondis
# sont masqués par la page, qui arrondit l'écran comme le vrai.
ROGNAGE = 0.012


class PasDImage(Exception):
    """Pas d'image à servir, avec la raison à montrer sur la tablette."""


def _noire(image: Image.Image) -> bool:
    return all(maxi < SEUIL_NOIR for _, maxi in image.getextrema())


def _rognee(zone: Rect) -> Rect:
    x, y, l, h = zone
    mx, my = round(l * ROGNAGE), round(h * ROGNAGE)
    return (x + mx, y + my, l - 2 * mx, h - 2 * my)


class Video:
    def __init__(self, saved_games: Path,
                 capturer: Optional[Callable[[Dict[str, Rect]], Optional[Copie]]] = None,
                 lancement: Optional[Callable[[], Optional[float]]] = None,
                 horloge: Callable[[], float] = time.monotonic):
        if capturer is None or lancement is None:
            from . import capture           # Windows seulement : chargé à la demande
            capturer = capturer or capture.capturer_dcs
            lancement = lancement or capture.lancement_dcs
        self.saved_games = saved_games
        self._capturer = capturer
        self._lancement = lancement
        self._horloge = horloge
        self._verrou = threading.Lock()
        self._zones: Optional[Tuple[float, Dict[str, Rect], Optional[str]]] = None
        self._resolution: Optional[Tuple[int, int]] = None
        self._copie: Optional[Tuple[float, Optional[Copie]]] = None
        self._demandes: Dict[str, float] = {}
        self._jpeg: Dict[str, Tuple[float, bytes]] = {}

    # ----------------------------------------------------------- zones

    def _zones_actives(self, maintenant: float) -> Dict[str, Rect]:
        """Zones des écrans exportés, plus celle du kneeboard ; lève la raison
        si la configuration d'écrans de DCS n'en exporte aucun."""
        if self._zones is None or maintenant - self._zones[0] > VALIDITE_ZONES_S:
            try:
                zones = zones_actives(self.saved_games)
                self._resolution = options_affichage(self.saved_games)[1:]
                zones[KNEEBOARD] = zone_kneeboard(*self._resolution)
                # Vu en vrai : la configuration réécrite pendant que DCS
                # tournait, il dessinait encore à l'ancienne place et la
                # tablette capturait à côté. On le dit au lieu de capturer.
                lance = self._lancement()
                if lance is not None and fichier_actif(self.saved_games).stat().st_mtime > lance:
                    raise PasDExport("La configuration d'écrans a changé depuis le "
                                     "lancement de DCS, qui ne la relit qu'au "
                                     "démarrage : relance DCS.")
                self._zones = (maintenant, zones, None)
            except PasDExport as e:
                self._zones = (maintenant, {}, str(e))
        _, zones, raison = self._zones
        if raison:
            raise PasDImage(raison)
        return zones

    def _copie_pour(self, nom: str, maintenant: float,
                    zones: Dict[str, Rect]) -> Tuple[float, Copie]:
        """Copie récente contenant `nom` ; sinon une nouvelle, de tous les
        écrans affichés en ce moment."""
        self._demandes[nom] = maintenant
        if self._copie is not None:
            instant, copie = self._copie
            if (maintenant - instant < FRAICHEUR_S and copie is not None
                    and (nom in copie.ecrans or not dans(zones[nom], copie.taille))):
                return instant, copie
        voulues = {n: (_rognee(z) if n != KNEEBOARD else z) for n, z in zones.items()
                   if maintenant - self._demandes.get(n, -1e9) < DEMANDE_RECENTE_S}
        self._copie = (maintenant, self._capturer(voulues))
        instant, copie = self._copie
        if copie is None:
            raise PasDImage("DCS n'est pas lancé, ou sa fenêtre est réduite.")
        return instant, copie

    def _hors_fenetre(self, nom: str, taille: Tuple[int, int]) -> PasDImage:
        fl, fh = taille
        rl, rh = self._resolution or taille
        if (rl, rh) != (fl, fh):
            # Vu en vrai : DCS réglé plus grand que l'espace des écrans garde
            # une fenêtre plus petite, et ce qui dépasse n'est dessiné nulle part.
            return PasDImage(f"DCS est réglé en {rl} × {rh} mais sa fenêtre ne fait "
                             f"que {fl} × {fh} : vérifie la résolution dans Options → "
                             "Système, puis relance DCS.")
        return PasDImage(f"{nom} sort de la fenêtre de DCS ({fl} × {fh}) : la "
                         "configuration d'écrans ne correspond pas à la résolution. "
                         "Relance scripts/configurer_ecrans_dcs.py.")

    # ----------------------------------------------------------- images

    def _brute(self, nom: str) -> Tuple[float, Image.Image]:
        maintenant = self._horloge()
        zones = self._zones_actives(maintenant)
        if nom not in zones:
            raise PasDImage(f"La configuration d'écrans de DCS n'exporte pas {nom}.")
        instant, copie = self._copie_pour(nom, maintenant, zones)
        if nom not in copie.ecrans:
            raise self._hors_fenetre(nom, copie.taille)
        image = copie.ecrans[nom]
        if nom == KNEEBOARD:
            # Fermé, DCS ne le dessine pas. On juge sur le bas de la page :
            # vu en vrai, un écran exporté qui déborde sur la zone (ancienne
            # disposition encore chargée par DCS) suffisait à le croire ouvert.
            l, h = image.size
            if _noire(image.crop((0, int(h * 0.75), l, int(h * 0.95)))):
                raise PasDImage("Kneeboard fermé dans DCS : ouvre-le avec RShift+K "
                                "(ou garde K enfoncé pour un coup d'œil).")
            return instant, image
        if not _noire(image):
            return instant, image
        # Un écran éteint est noir, et c'est normal (démarrage à froid). Mais si
        # le milieu de la vue l'est aussi, la copie ne voit rien : DCS en plein
        # écran exclusif. Le témoin n'est copié que dans ce cas.
        temoin = self._capturer({TEMOIN: zone_temoin(copie.taille)})
        if temoin is not None and TEMOIN in temoin.ecrans and _noire(temoin.ecrans[TEMOIN]):
            raise PasDImage("Image noire : décoche « Plein écran » dans "
                            "Options → Système de DCS (le mode fenêtré se capture).")
        return instant, image

    def kneeboard(self) -> Image.Image:
        """Page du kneeboard telle que DCS la dessine ; lève la raison sinon."""
        with self._verrou:
            return self._brute(KNEEBOARD)[1]

    def image(self, nom: str) -> bytes:
        """JPEG de l'écran `nom` (LEFT_MFCD…, ou KNEEBOARD)."""
        with self._verrou:
            instant, image = self._brute(nom)
            deja = self._jpeg.get(nom)
            if deja and deja[0] == instant:
                return deja[1]
            if max(image.size) > COTE_MAX:
                image = image.copy()
                image.thumbnail((COTE_MAX, COTE_MAX))
            tampon = io.BytesIO()
            image.save(tampon, "JPEG", quality=QUALITE_JPEG,
                       subsampling=SOUS_ECHANTILLONNAGE)
            donnees = tampon.getvalue()
            self._jpeg[nom] = (instant, donnees)
            return donnees
