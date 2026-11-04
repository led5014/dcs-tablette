"""Le DED du F-16C (Data Entry Display) : ses 5 lignes de 24 caractères,
refaites sur la tablette à partir de son texte.

DCS donne le DED par `list_indication(6)` en morceaux nommés (« STPT Num »,
« ACAL_ALEV »…), sans leur place à l'écran. Cette place, page par page, a
été relevée dans le module par les auteurs de DCS-BIOS (github.com/
DCS-Skunkworks/dcs-bios, Scripts/DCS-BIOS/lib/modules/displays/
F_16C_DED.lua : ~1 100 morceaux sur ~150 pages). Sans le module, on ne
peut pas la refaire.

Cette table est sous GPL-3.0, la tablette sous MIT : elle n'est pas livrée
avec. Le serveur la télécharge au premier DED demandé (choix du 04/11/2026),
à une version fixée et vérifiée par son empreinte SHA-256, et la garde dans
%LOCALAPPDATA%\\DCS-Tablette. Elle est lue comme une donnée — le
constructeur de table Lua est analysé ici, jamais exécuté. Faute de table
(hors ligne), le clavier de l'ICP marche quand même ; le DED dit pourquoi
il reste vide.

DCS ne dit pas quelle page du DED est affichée : on la déduit des morceaux
présents (`Gabarit.page`).
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, FrozenSet, Iterable, Iterator, List, Optional, Tuple

from . import VERSION
from .langues import Texte

IND_DED = 6                  # list_indication du DED (DCS-BIOS : parse_indication(6))
LARGEUR, HAUTEUR = 24, 5

VERSION_BIOS = "v0.11.8"
_COMMIT = "b5d0aa45a980909a6823562012f344cf7cfdd2a7"     # celui de cette version
URL = (f"https://raw.githubusercontent.com/DCS-Skunkworks/dcs-bios/{_COMMIT}/"
       "Scripts/DCS-BIOS/lib/modules/displays/F_16C_DED.lua")
EMPREINTE = "078df33559427191a40098fcb3d93af6a327e544a5ffd07c204e09147f128be5"
DELAI_S = 30
# Hors ligne, on ne retente pas à chaque image : une fois par minute.
REESSAI_S = 60.0

journal = logging.getLogger("tablette")


# --------------------------------------------------------------- table Lua

_JETON = re.compile(r"""\s+|--[^\n]*                  # blancs, commentaires
                      |"((?:[^"\\\n]|\\.)*)"          # chaîne
                      |(-?\d+(?:\.\d+)?)              # nombre
                      |([A-Za-z_]\w*)                 # nom
                      |([{}\[\]=,;])                  # ponctuation""", re.X)
_LITTERAUX = {"true": True, "false": False, "nil": None}


def table_lua(texte: str):
    """Le premier constructeur de table de `texte` ({ … }), en dict ou en
    list : chaînes, nombres, booléens et tables imbriquées, ce dont la table
    de DCS-BIOS est faite. ValueError pour toute autre chose."""
    # La première accolade hors commentaire (« --- @type { [string]: … } »).
    debut = next((m.start() for m in re.finditer(r"\{", texte)
                  if "--" not in texte[texte.rfind("\n", 0, m.start()) + 1:m.start()]), None)
    if debut is None:
        raise ValueError("pas de table Lua")
    jetons = _jetons(texte, debut)
    try:
        return _valeur(jetons, next(jetons))
    except StopIteration:
        raise ValueError("table Lua inachevée") from None


def _jetons(texte: str, pos: int) -> Iterator[Tuple[str, object]]:
    while pos < len(texte):
        m = _JETON.match(texte, pos)
        if m is None:
            raise ValueError(f"table Lua illisible à la position {pos}")
        pos = m.end()
        chaine, nombre, nom, signe = m.groups()
        if chaine is not None:
            yield "chaine", re.sub(r"\\(.)", lambda e: {"n": "\n", "t": "\t"}.get(
                e.group(1), e.group(1)), chaine)
        elif nombre:
            yield "nombre", float(nombre) if "." in nombre else int(nombre)
        elif nom:
            yield "nom", nom
        elif signe:
            yield "signe", signe


def _valeur(jetons: Iterator, jeton: Tuple[str, object]):
    genre, v = jeton
    if jeton == ("signe", "{"):
        return _table(jetons)
    if genre in ("chaine", "nombre"):
        return v
    if genre == "nom" and v in _LITTERAUX:
        return _LITTERAUX[v]
    raise ValueError(f"valeur Lua inattendue : {v!r}")


def _attendre(jetons: Iterator, signe: str) -> None:
    if next(jetons) != ("signe", signe):
        raise ValueError(f"« {signe} » attendu dans la table Lua")


def _table(jetons: Iterator):
    cles: Dict = {}
    liste: List = []
    for jeton in jetons:
        if jeton == ("signe", "}"):
            if not cles:
                return liste
            cles.update({i + 1: v for i, v in enumerate(liste)})
            return cles
        if jeton in (("signe", ","), ("signe", ";")):
            continue
        if jeton == ("signe", "["):
            cle = _valeur(jetons, next(jetons))
            _attendre(jetons, "]")
            _attendre(jetons, "=")
            cles[cle] = _valeur(jetons, next(jetons))
        elif jeton[0] == "nom" and jeton[1] not in _LITTERAUX:
            _attendre(jetons, "=")
            cles[jeton[1]] = _valeur(jetons, next(jetons))
        else:
            liste.append(_valeur(jetons, jeton))
    raise ValueError("table Lua inachevée")


# --------------------------------------------------------------- gabarit

@dataclass(frozen=True)
class Place:
    """Où le module écrit un morceau du DED : colonne et ligne comptées
    depuis 1, comme dans la table."""
    x: int
    y: int
    pages: FrozenSet[str]
    a_droite: bool = False    # « RGHT » : x est la dernière colonne du texte
    inverse: bool = False     # vidéo inverse (color = "i")


class Gabarit:
    """La place de chaque morceau du DED, page par page."""

    def __init__(self, places: Dict[str, Tuple[Place, ...]]):
        if not places:
            raise ValueError("table du DED vide")
        self.places = places
        # Nombre de morceaux de chaque page : départage deux pages qui
        # reconnaissent autant de morceaux (la plus petite est mieux remplie).
        self.tailles: Counter = Counter(
            page for liste in places.values() for page in set().union(*(p.pages for p in liste)))

    @classmethod
    def lire(cls, texte: str) -> "Gabarit":
        """D'après le texte de F_16C_DED.lua. ValueError s'il n'en a pas la forme."""
        table = table_lua(texte)
        if not isinstance(table, dict):
            raise ValueError("table du DED illisible")
        places: Dict[str, Tuple[Place, ...]] = {}
        for nom, liste in table.items():
            if not isinstance(liste, list):
                continue
            trouvees = tuple(
                Place(d["x"], d["y"], frozenset(p for p in d.get("pages") or () if isinstance(p, str)),
                      d.get("alignment") == "RGHT", d.get("color") == "i")
                for d in liste
                if isinstance(d, dict) and isinstance(d.get("x"), int) and isinstance(d.get("y"), int))
            if trouvees:
                places[str(nom)] = trouvees
        return cls(places)

    def page(self, noms: Iterable[str]) -> Optional[str]:
        """La page affichée : celle où se trouvent le plus des morceaux
        présents ; à égalité, la plus petite."""
        votes: Counter = Counter()
        for nom in noms:
            votes.update(set().union(*(p.pages for p in self.places.get(nom, ()))))
        if not votes:
            return None
        return max(votes, key=lambda page: (votes[page], -self.tailles[page], page))

    def ecran(self, champs: Dict[str, str]) -> Dict:
        """Ce que montre le DED : la page déduite, et chaque ligne en
        morceaux [texte, inverse] — 24 caractères en tout, espaces compris,
        pour qu'une police à chasse fixe garde les colonnes."""
        page = self.page(champs)
        lettres = [[" "] * LARGEUR for _ in range(HAUTEUR)]
        inverses = [[False] * LARGEUR for _ in range(HAUTEUR)]
        for nom, texte in champs.items():
            candidates = self.places.get(nom, ())
            # Un morceau qui n'a qu'une place s'y écrit, quelle que soit la page.
            place = candidates[0] if len(candidates) == 1 else next(
                (p for p in candidates if page in p.pages), None)
            if place is None or not 1 <= place.y <= HAUTEUR:
                continue
            texte = texte.replace("\n", "")
            debut = place.x - len(texte) + 1 if place.a_droite else place.x
            for i, c in enumerate(texte):
                colonne = debut + i - 1
                if not 0 <= colonne < LARGEUR:
                    continue
                # Un espace n'efface pas ce qu'un autre morceau a écrit ; la
                # vidéo inverse, elle, couvre tout le morceau.
                if c != " ":
                    lettres[place.y - 1][colonne] = c
                if place.inverse:
                    inverses[place.y - 1][colonne] = True
        lignes = []
        for lettres_, inverses_ in zip(lettres, inverses):
            morceaux: List[list] = []
            for c, inv in zip(lettres_, inverses_):
                if morceaux and morceaux[-1][1] == inv:
                    morceaux[-1][0] += c
                else:
                    morceaux.append([c, inv])
            lignes.append(morceaux)
        return {"page": page, "lignes": lignes}


# --------------------------------------------------------------- téléchargement

def fichier_table() -> Path:
    racine = os.environ.get("LOCALAPPDATA")
    return (Path(racine) if racine else Path.home()) / "DCS-Tablette" / f"F_16C_DED-{VERSION_BIOS}.lua"


class TableDED:
    """Le gabarit, lu une fois : depuis le fichier gardé s'il est intact,
    sinon téléchargé dans un fil — la page n'attend pas, elle redemande."""

    def __init__(self, fichier: Optional[Path] = None,
                 ouvrir: Callable = urllib.request.urlopen):
        self.fichier = fichier or fichier_table()
        self._ouvrir = ouvrir
        self._verrou = threading.Lock()
        self._gabarit: Optional[Gabarit] = None
        self._fil: Optional[threading.Thread] = None
        self._prochain_essai = 0.0
        self._erreur: Optional[object] = None    # Texte, ou message d'urllib

    def gabarit(self) -> Optional[Gabarit]:
        """Le gabarit s'il est prêt. Sinon None, et un chargement lancé
        s'il n'y en a pas déjà un, ni un échec trop récent."""
        with self._verrou:
            if self._gabarit is None and (self._fil is None or not self._fil.is_alive()) \
                    and time.monotonic() >= self._prochain_essai:
                self._fil = threading.Thread(target=self._charger, name="table-ded", daemon=True)
                self._fil.start()
            return self._gabarit

    def raison(self) -> Texte:
        """Pourquoi le gabarit n'est pas là, pour le DED de la page."""
        with self._verrou:
            erreur = self._erreur
        if erreur:
            return Texte("DED : table de DCS-BIOS non téléchargée ({raison}). Nouvel essai "
                         "dans une minute ; le clavier marche.", raison=erreur)
        return Texte("DED : téléchargement de sa table (DCS-BIOS)…")

    def _charger(self) -> None:
        try:
            gabarit = Gabarit.lire(self._contenu())
        # Dans un fil : tout ce qui peut sortir d'urllib et de http.client
        # (IncompleteRead n'est pas une OSError) doit finir ici.
        except Exception as e:                  # noqa: BLE001
            journal.warning("Table du DED (DCS-BIOS %s) : %s", VERSION_BIOS, e)
            with self._verrou:
                # Notre Texte tel quel : la tablette le lira dans sa langue.
                self._erreur = (e.args[0] if e.args and isinstance(e.args[0], Texte)
                                else str(e) or type(e).__name__)
                self._prochain_essai = time.monotonic() + REESSAI_S
            return
        with self._verrou:
            self._gabarit, self._erreur = gabarit, None

    def _contenu(self) -> str:
        """Le texte de la table, vérifié : celui du fichier gardé, sinon
        celui de GitHub, gardé à son tour."""
        try:
            donnees = self.fichier.read_bytes()
            if hashlib.sha256(donnees).hexdigest() == EMPREINTE:
                return donnees.decode("utf-8")
        except OSError:
            pass
        requete = urllib.request.Request(URL, headers={"User-Agent": f"DCS-Tablette/{VERSION}"})
        with self._ouvrir(requete, timeout=DELAI_S) as reponse:
            donnees = reponse.read()
        if hashlib.sha256(donnees).hexdigest() != EMPREINTE:
            raise OSError(Texte("ce n'est pas la table attendue (empreinte différente)"))
        self.fichier.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.fichier.with_suffix(".tmp")
        provisoire.write_bytes(donnees)
        os.replace(provisoire, self.fichier)
        journal.info("Table du DED téléchargée (DCS-BIOS %s)", VERSION_BIOS)
        return donnees.decode("utf-8")
