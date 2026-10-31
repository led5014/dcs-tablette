"""Le lien avec DCS : deux sens, en UDP, sur la boucle locale.

- Aller : un datagramme par appui ou relâchement vers le script Lua,
  "<appareil> <commande> <valeur>" ; et "kneeboard 1" / "kneeboard -1"
  pour afficher ou cacher le kneeboard de DCS. Rien n'attend de réponse :
  un ordre perdu est un bouton qui ne s'enfonce pas, et le pilote réappuie.
- Retour : le script annonce chaque seconde l'appareil piloté. Faute
  d'annonce depuis `SILENCE_S`, DCS est considéré absent — on ne prétend
  pas savoir ce qui se passe dans un cockpit qu'on n'entend plus. Dans un
  Hornet, il envoie aussi le texte de l'UFC et de l'IFEI (« ind ») et la
  position des aiguilles et des voyants (« arg ») : périmés au même délai.
  Et pour tout appareil, 20 fois par seconde, les données de vol (« vol ») :
  vitesse, altitude, assiette, cap, moteur… pour les instruments analogiques.
"""
from __future__ import annotations

import math
import socket
import threading
import time
from typing import Dict, Optional, Tuple

from .instruments import TauxDeVirage

SILENCE_S = 3.0
TAILLE_MAX = 65536             # un texte d'IFEI tient en quelques Ko


class PontDCS:
    def __init__(self, port_ordres: int, port_etat: int, hote: str = "127.0.0.1"):
        self.hote = hote
        self.port_ordres = port_ordres
        self.port_etat = port_etat
        self._envoi = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._ecoute: Optional[socket.socket] = None
        self._fil: Optional[threading.Thread] = None
        self._arret = threading.Event()
        self._verrou = threading.Lock()
        self._dernier: Optional[tuple] = None      # (appareil ou None, instant)
        self._textes: Dict[int, Tuple[str, float]] = {}
        self._arguments: Tuple[Dict[int, float], float] = ({}, 0.0)
        self._vol: Tuple[Dict[str, float], bool, float] = ({}, False, -1e9)
        self._virage = TauxDeVirage()

    def demarrer(self) -> None:
        """Ouvre l'écoute des annonces. Un port déjà pris n'empêche pas de
        servir la page : l'état restera simplement « pas de signal »."""
        try:
            ecoute = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ecoute.bind((self.hote, self.port_etat))
            ecoute.settimeout(0.5)
        except OSError:
            return
        self._ecoute = ecoute
        # Port 0 dans les tests : on retient celui que l'OS a choisi.
        self.port_etat = ecoute.getsockname()[1]
        self._fil = threading.Thread(target=self._ecouter, name="tablette-etat",
                                     daemon=True)
        self._fil.start()

    @property
    def a_l_ecoute(self) -> bool:
        """Faux quand le port était pris au démarrage : DCS parle dans le vide."""
        return self._ecoute is not None

    def arreter(self) -> None:
        self._arret.set()
        if self._fil:
            self._fil.join(timeout=2)
        for s in (self._ecoute, self._envoi):
            if s:
                try:
                    s.close()
                except OSError:
                    pass

    def _ecouter(self) -> None:
        while not self._arret.is_set():
            try:
                donnees, _ = self._ecoute.recvfrom(TAILLE_MAX)
            except socket.timeout:
                continue
            except OSError:
                return
            self._recevoir(donnees.decode("utf-8", "replace"))

    def _recevoir(self, texte: str) -> None:
        maintenant = time.monotonic()
        if texte.startswith("etat "):
            nom = texte[5:].strip()
            with self._verrou:
                self._dernier = (None if nom in ("", "-") else nom, maintenant)
        elif texte.startswith("ind "):
            entete, _, contenu = texte.partition("\n")
            try:
                numero = int(entete[4:])
            except ValueError:
                return
            with self._verrou:
                self._textes[numero] = (contenu, maintenant)
        elif texte.startswith("arg "):
            valeurs = {}
            for morceau in texte[4:].split():
                n, _, v = morceau.partition("=")
                try:
                    valeurs[int(n)] = float(v)
                except ValueError:
                    continue
            with self._verrou:
                self._arguments = (valeurs, maintenant)
        elif texte.startswith("vol "):
            # Données de vol de tout appareil (instruments.py) ; « vol - » :
            # le serveur multijoueur interdit d'exporter son propre appareil.
            donnees: Dict[str, float] = {}
            if texte[4:].strip() != "-":
                for morceau in texte[4:].split():
                    cle, _, v = morceau.partition("=")
                    try:
                        donnees[cle] = float(v)
                    except ValueError:
                        continue
            if "cap" in donnees:
                # Taux de virage tiré du cap, à chaque message : le calculer à
                # chaque demande de la page le fausserait (deux tablettes, ou
                # une demande sans nouveau message entre-temps).
                donnees["taux"] = self._virage.mesurer(math.degrees(donnees["cap"]) % 360.0)
            with self._verrou:
                self._vol = (donnees, texte[4:].strip() == "-", maintenant)

    def texte(self, numero: int) -> Optional[str]:
        """Dernier texte reçu de l'indicateur `numero`, s'il est frais."""
        with self._verrou:
            recu = self._textes.get(numero)
        if recu is None or time.monotonic() - recu[1] > SILENCE_S:
            return None
        return recu[0]

    def vol(self) -> Tuple[Optional[Dict[str, float]], bool]:
        """Dernières données de vol (None si rien de frais), et si le serveur
        multijoueur interdit de les exporter."""
        with self._verrou:
            donnees, interdit, instant = self._vol
        if time.monotonic() - instant > SILENCE_S:
            return None, False
        return (None if interdit else dict(donnees)), interdit

    def arguments(self) -> Dict[int, float]:
        """Dernières positions d'aiguilles et de voyants, si fraîches."""
        with self._verrou:
            valeurs, instant = self._arguments
        if time.monotonic() - instant > SILENCE_S:
            return {}
        return dict(valeurs)

    def appuyer(self, appareil: int, commande: int, enfonce: bool) -> bool:
        """Envoie l'ordre ; faux seulement si l'envoi lui-même a échoué."""
        return self._envoyer(f"{appareil} {commande} {1 if enfonce else 0}")

    def kneeboard(self, ouvert: bool) -> bool:
        """Affiche ou cache le kneeboard de DCS (le coup d'œil, touche K)."""
        return self._envoyer(f"kneeboard {1 if ouvert else -1}")

    def tourner(self, appareil: int, commande: int, cran: float) -> bool:
        """Un cran de molette, dans le sens du signe de `cran`."""
        return self._envoyer(f"{appareil} {commande} {cran:g}")

    def _envoyer(self, message: str) -> bool:
        try:
            self._envoi.sendto(message.encode("ascii"), (self.hote, self.port_ordres))
        except OSError:
            return False
        return True

    def etat(self) -> Dict:
        with self._verrou:
            dernier = self._dernier
        if dernier is None:
            return {"connecte": False, "appareil": None}
        nom, instant = dernier
        if time.monotonic() - instant > SILENCE_S:
            return {"connecte": False, "appareil": None}
        return {"connecte": True, "appareil": nom}
