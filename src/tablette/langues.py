"""Les langues : le français, qui fait référence, et l'anglais.

Le texte s'écrit en français dans le code, comme toujours. `Texte` le
traduit à la demande d'après le catalogue de la langue voulue (anglais.py),
dont les clés sont les phrases françaises elles-mêmes : un texte absent du
catalogue reste en français plutôt que de disparaître, et
tests/test_tablette.py vérifie qu'il n'en manque aucun. Une autre langue,
un jour : un autre catalogue, rien à changer dans le code.

Deux langues vivent côte à côte dans le même programme :
- celle du PC, pour la fenêtre de DCS Tablette, l'installation et la mise à
  jour : celle de Windows, sauf choix contraire retenu (`--langue`) ;
- celle de chaque tablette, pour sa page et ce que le serveur lui envoie :
  celle de son navigateur, sauf choix contraire fait sur la page (cookie).
Un même point du diagnostic s'affiche donc en français dans la fenêtre du PC
et en anglais sur la tablette : il garde son texte français et ses valeurs,
et ne se traduit qu'au dernier moment (`dans`).

Français si la langue demandée est le français, anglais pour toute autre :
un pilote allemand ou espagnol lit plus volontiers l'anglais. Faute de rien
savoir, le français.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Set

from . import anglais

FRANCAIS, ANGLAIS = "fr", "en"
LANGUES = (FRANCAIS, ANGLAIS)
CATALOGUES: Dict[str, Dict[str, str]] = {
    FRANCAIS: {},
    ANGLAIS: {**anglais.SERVEUR, **anglais.PAGE},
}
# Les textes de la page seulement : servis à la tablette (/textes.js).
CATALOGUES_PAGE: Dict[str, Dict[str, str]] = {FRANCAIS: {}, ANGLAIS: anglais.PAGE}

# Cookie de la page : la langue choisie à la main sur cette tablette (absent :
# celle du navigateur). Comme celui de l'appareil, chaque tablette a le sien.
COOKIE = "tablette_langue"

_pc = FRANCAIS
# Textes demandés dans une langue qui ne les a pas : les tests y regardent.
manquants: Set[str] = set()


def pc() -> str:
    """La langue de la fenêtre de DCS Tablette sur le PC."""
    return _pc


def regler_pc(langue: str) -> None:
    """Fixée au lancement (__main__), avant de rien afficher. Jusque-là, et
    dans les tests, le français."""
    global _pc
    _pc = langue if langue in LANGUES else FRANCAIS


def traduire(francais: str, langue: str) -> str:
    """Un libellé venu des données (appareil, écran, carnet) dans `langue` ;
    tel quel s'il n'a pas de traduction : « F/A-18C Hornet » reste lui-même."""
    return CATALOGUES.get(langue, {}).get(francais, francais)


def _rendre(francais: str, valeurs: Dict[str, Any], langue: str) -> str:
    modele = CATALOGUES.get(langue, {}).get(francais)
    if modele is None:
        if langue != FRANCAIS:
            manquants.add(francais)
        modele = francais
    if not valeurs:
        return modele
    # Une liste de valeurs se montre séparée par des virgules, chacune
    # traduite : les réseaux du PC, les écrans exportés.
    return modele.format(**{cle: ", ".join(str(dans(x, langue)) for x in v)
                            if isinstance(v, (list, tuple)) else dans(v, langue)
                            for cle, v in valeurs.items()})


class Texte(str):
    """Un texte à montrer : la phrase française, ses valeurs (`{nom}` dans la
    phrase), et sa traduction dans n'importe quelle langue (`dans`).

    Comme chaîne, il vaut sa traduction dans la langue du PC : la console
    l'affiche tel quel, et le code qui le compare ou le découpe n'y voit
    qu'une chaîne. Assemblé par une f-string ou un +, il redevient une simple
    chaîne dans la langue du PC : ce qui part vers la tablette s'assemble
    donc par des `Texte` dont les valeurs sont d'autres `Texte`.
    """

    francais: str
    valeurs: Dict[str, Any]

    def __new__(cls, francais: str, **valeurs: Any) -> "Texte":
        objet = super().__new__(cls, _rendre(francais, valeurs, _pc))
        objet.francais, objet.valeurs = francais, valeurs
        return objet

    def dans(self, langue: str) -> str:
        return _rendre(self.francais, self.valeurs, langue)

    # Immuable : copié tel quel (dataclasses.asdict copie les points du
    # diagnostic), sans repasser par le constructeur.
    def __copy__(self) -> "Texte":
        return self

    def __deepcopy__(self, memo) -> "Texte":
        return self


def dans(objet: Any, langue: str) -> Any:
    """`objet` pour une tablette : chaque `Texte` qu'il contient traduit dans
    `langue`, à toute profondeur (points du diagnostic, listes, dicts)."""
    if isinstance(objet, Texte):
        return objet.dans(langue)
    if isinstance(objet, dict):
        return {cle: dans(v, langue) for cle, v in objet.items()}
    if isinstance(objet, (list, tuple)):
        return type(objet)(dans(v, langue) for v in objet)
    return objet


def message(erreur: BaseException) -> Any:
    """Le message d'une exception tel qu'elle l'a reçu : un `Texte` reste un
    `Texte`, quand str(erreur) n'en garderait que la langue du PC."""
    if len(erreur.args) == 1 and isinstance(erreur.args[0], str):
        return erreur.args[0]
    return str(erreur)


def raison(erreur: BaseException, langue: str) -> str:
    """Le message d'une exception levée avec un `Texte`, dans `langue`."""
    return dans(message(erreur), langue)


# --------------------------------------------------------------- laquelle

def de_l_etiquette(etiquette: str) -> Optional[str]:
    """« fr-FR », « fr_CA », « EN » → la langue, si on la parle ; None sinon."""
    langue = etiquette.strip().replace("_", "-").split("-")[0].lower()
    return langue if langue in LANGUES else None


def preferee(etiquettes: Iterable[str]) -> str:
    """La première langue qu'on parle, dans l'ordre de préférence ; l'anglais
    si aucune (allemand, espagnol…) ; le français pour une liste vide."""
    vues = False
    for etiquette in etiquettes:
        vues = True
        langue = de_l_etiquette(etiquette)
        if langue:
            return langue
    return ANGLAIS if vues else FRANCAIS


def du_navigateur(entete: Optional[str]) -> str:
    """D'après l'en-tête Accept-Language : « fr-FR,fr;q=0.9,en;q=0.8 »."""
    choix = []
    for rang, morceau in enumerate((entete or "").split(",")):
        etiquette, *parametres = (p.strip() for p in morceau.split(";"))
        poids = 1.0
        for p in parametres:
            nom, _, valeur = p.partition("=")
            if nom.strip() == "q":
                try:
                    poids = float(valeur)
                except ValueError:
                    poids = 0.0
        if etiquette and etiquette != "*" and poids > 0:
            choix.append((-poids, rang, etiquette))
    return preferee(etiquette for _, _, etiquette in sorted(choix))


def de_la_tablette(cookie: Optional[str], entete: Optional[str]) -> str:
    """La langue d'une tablette : celle choisie sur sa page, sinon celle de
    son navigateur."""
    return cookie if cookie in LANGUES else du_navigateur(entete)


def de_windows() -> Optional[str]:
    """La langue d'affichage de Windows ; None hors de Windows."""
    try:
        identifiant = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    except (AttributeError, OSError):
        return None
    # Langue principale : les 10 bits du bas (0x0C français, 0x09 anglais…).
    return FRANCAIS if identifiant & 0x3FF == 0x0C else ANGLAIS


# --------------------------------------------------------------- le choix du PC
#
# `DCS-Tablette.exe --langue en` : retenu dans %LOCALAPPDATA%\DCS-Tablette,
# à côté du choix fait à l'installation, pour que le raccourci du bureau
# (sans argument) reste en anglais. `--langue auto` : suivre Windows.

def fichier_langue() -> Path:
    racine = os.environ.get("LOCALAPPDATA")
    return (Path(racine) if racine else Path.home()) / "DCS-Tablette" / "langue.txt"


def lire_choix(chemin: Optional[Path] = None) -> Optional[str]:
    try:
        langue = (chemin or fichier_langue()).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return langue if langue in LANGUES else None


def retenir(langue: str, chemin: Optional[Path] = None) -> None:
    """Retient `langue` pour le PC ; « auto » efface le choix."""
    chemin = chemin or fichier_langue()
    if langue not in LANGUES:
        chemin.unlink(missing_ok=True)
        return
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(langue + "\n", encoding="utf-8")


def du_pc(chemin: Optional[Path] = None,
          windows: Callable[[], Optional[str]] = de_windows) -> str:
    """Le choix retenu, sinon la langue de Windows, sinon le français."""
    return lire_choix(chemin) or windows() or FRANCAIS
