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

import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from PIL import Image

from . import filtres
from .copie import Copie, Rect, dans, zone_temoin
from .ecrans_dcs import (PasDExport, fichier_actif, options_affichage, zone_kneeboard,
                         zones_actives)
from .filtres import Reglages

KNEEBOARD = "KNEEBOARD"
TEMOIN = "TEMOIN"

FRAICHEUR_S = 1 / 30             # une copie sert tous les écrans demandés
DEMANDE_RECENTE_S = 1.0          # un écran réclamé depuis moins longtemps est copié
VALIDITE_ZONES_S = 2.0           # options.lua n'est relu qu'une fois toutes les 2 s
SEUIL_NOIR = 8                   # luminosité max sous laquelle une image est noire
GARDE_JPEG_S = 2.0               # une image réglée qui n'a pas resservi depuis est oubliée
# DCS dessine les écrans du Hornet arrondis (rayon ≈ 1/6 du côté, mesuré) et
# laisse un liseré du cockpit sur les bords : on le rogne. Rogner davantage
# couperait les libellés des boutons, collés au bord ; les coins arrondis
# sont masqués par la page, qui arrondit l'écran comme le vrai.
ROGNAGE = 0.012


class PasDImage(Exception):
    """Pas d'image à servir, avec la raison à montrer sur la tablette."""


class KneeboardFerme(PasDImage):
    """DCS tourne et se capture, mais le kneeboard n'y est pas ouvert."""


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
        self._jpeg: Dict[Tuple[str, Reglages], Tuple[float, bytes]] = {}
        # Taille de la dernière image de chaque écran, telle que DCS la dessine.
        self.tailles: Dict[str, Tuple[int, int]] = {}
        # Pour le diagnostic : la dernière image demandée par la tablette,
        # (instant, None si servie, sinon la raison donnée à la tablette).
        self.dernier: Optional[Tuple[float, Optional[str]]] = None

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
                         "Quitte DCS : DCS Tablette remet ses réglages, puis relance DCS.")

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
                raise KneeboardFerme("Kneeboard fermé dans DCS : ouvre-le avec RShift+K "
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

    def kneeboard_ouvert(self) -> Optional[bool]:
        """Le kneeboard est-il ouvert dans DCS ? None quand on ne peut pas le
        savoir (DCS absent, configuration d'écrans qui ne convient pas)."""
        try:
            self.kneeboard()
            return True
        except KneeboardFerme:
            return False
        except PasDImage:
            return None

    def image(self, nom: str, reglages: Reglages = Reglages()) -> bytes:
        """JPEG de l'écran `nom` (LEFT_MFCD…, ou KNEEBOARD), avec les réglages
        de la tablette (filtres.py ; par défaut, tel que DCS le dessine)."""
        with self._verrou:
            try:
                instant, image = self._brute(nom)
            except KneeboardFerme:
                raise
            except PasDImage as e:
                self.dernier = (self._horloge(), str(e))
                raise
            self.dernier = (self._horloge(), None)
            self.tailles[nom] = image.size
            # Deux tablettes peuvent régler le même écran différemment.
            deja = self._jpeg.get((nom, reglages))
            if deja and deja[0] == instant:
                return deja[1]
        # Hors du verrou : un écran agrandi et affiné ne fait pas attendre les
        # autres. L'image copiée n'est jamais modifiée, seulement lue.
        donnees = filtres.jpeg(image, reglages)
        with self._verrou:
            self._jpeg[(nom, reglages)] = (instant, donnees)
            # Un réglage essayé puis quitté ne garde pas son image.
            for cle in [c for c, (t, _) in self._jpeg.items() if instant - t > GARDE_JPEG_S]:
                del self._jpeg[cle]
        return donnees
