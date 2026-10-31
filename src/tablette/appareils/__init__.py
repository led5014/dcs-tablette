"""Profils d'appareil : ce que la tablette sait faire dans chaque module.

Un profil dit quels écrans DCS exporte en image (et sous quel nom de zone),
quels boutons les entourent avec leurs numéros, et ce qui s'y ajoute (UFC,
IFEI, instruments du Hornet). Le serveur choisit le profil d'après le nom
que le script Lua lit dans DCS (LoGetSelfData().Name) : la page se
reconstruit d'elle-même quand on change d'avion.

Les numéros viennent toujours des scripts du module installé (devices.lua,
command_defs.lua, clickabledata.lua) ; tests/test_tablette.py les relit
quand le module est présent.

Le script Lua porte la même liste blanche, générée depuis ces profils
(`lua_appareils`, écrite par scripts/generer_lua_appareils.py) : un ordre qui
n'y figure pas n'atteint jamais le cockpit, et ce qui vaut pour un avion ne
vaut pas pour un autre — le même numéro y désigne autre chose.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from ..instruments import OTAN, Instruments

COTES = ("gauche", "haut", "droite", "bas")


@dataclass(frozen=True)
class Bouton:
    id: str                  # libellé court, unique dans l'écran : "18", "T1", "VID"
    commande: int
    cote: str                # un des COTES, ou "rangee" : sous le cadre
    rang: int                # de gauche à droite, ou de haut en bas


@dataclass(frozen=True)
class Ecran:
    """Un écran exporté en image par DCS, et les boutons de son cadre."""
    id: str
    libelle: str
    viewport: str            # nom de la zone d'export (MonitorSetup)
    appareils: Dict[str, int]  # siège ("" si une seule place) → appareil DCS
    boutons: Tuple[Bouton, ...] = ()
    par_cote: int = 5
    # Rayon des coins du verre, en fraction du côté : la tablette arrondit
    # l'image pareil, pour que les coins où DCS laisse voir le cockpit tombent
    # sur le cadre. Mesuré sur les DDI du Hornet (0,17) ; ailleurs, coins
    # presque droits — l'écran de l'Apache est quasi carré, et arrondir sans
    # l'avoir mesuré rognerait des symboles.
    arrondi: float = 0.02
    # Où le module écrit le libellé de chaque bouton, en fraction de l'image
    # exportée : de gauche à droite pour les rangées du haut et du bas, de
    # haut en bas pour les côtés, un par rang. La tablette centre chaque
    # bouton sur le sien (retour de vol : sur l'Apache, ceux des bouts
    # tombaient à côté). None : boutons également répartis, faute de source
    # (module absent du poste de développement).
    reperes_x: Optional[Tuple[float, ...]] = None
    reperes_y: Optional[Tuple[float, ...]] = None
    # Écran en portrait (JF-17 : 5 boutons en haut et en bas, 8 sur les
    # côtés) : nombre de boutons des côtés, et largeur / hauteur du verre.
    # None : autant que `par_cote`, écran carré.
    par_cote_y: Optional[int] = None
    aspect: Optional[float] = None

    def appareil(self, siege: str) -> Optional[int]:
        if siege in self.appareils:
            return self.appareils[siege]
        return next(iter(self.appareils.values()), None)

    def bouton(self, id_: str) -> Optional[Bouton]:
        return next((b for b in self.boutons if b.id == id_), None)


@dataclass(frozen=True)
class Profil:
    id: str
    libelle: str
    noms_dcs: Tuple[str, ...]          # valeurs possibles de LoGetSelfData().Name
    ecrans: Tuple[Ecran, ...] = ()
    sieges: Tuple[str, ...] = ()       # vide : une seule place
    kneeboard: Optional[int] = None    # appareil des commandes de page, s'il est sûr
    panneaux: Tuple[str, ...] = ()     # panneaux redessinés : "ufc", "ifei", "secours"
    # Autres boutons enfoncés puis relâchés (UFC…), par appareil.
    touches: Dict[int, FrozenSet[int]] = field(default_factory=dict)
    # Molettes à crans : appareil → commande → valeur d'un cran.
    molettes: Dict[int, Dict[int, float]] = field(default_factory=dict)
    textes: Tuple[int, ...] = ()       # indicateurs envoyés en texte (list_indication)
    arguments: Tuple[int, ...] = ()    # aiguilles et voyants (get_argument_value)
    # Instruments analogiques redessinés (instruments.py), pour tout appareil :
    # unités de son cockpit et échelles des cadrans.
    instruments: Instruments = OTAN
    # Cockpit qu'une option de DCS passe en nœuds et pieds (MiG-29, L-39) :
    # ce qui le dit dans Config/options.lua (expression régulière), et ses
    # instruments alors.
    imperial: Optional[Tuple[str, Instruments]] = None

    def ecran(self, id_: str) -> Optional[Ecran]:
        return next((e for e in self.ecrans if e.id == id_), None)

    def instruments_selon(self, options: str) -> Instruments:
        """Les instruments d'après les options de DCS (texte d'options.lua)."""
        if self.imperial and re.search(self.imperial[0], options):
            return self.imperial[1]
        return self.instruments

    def description(self) -> Dict:
        """Ce que la page doit construire pour cet appareil."""
        return {
            "id": self.id,
            "libelle": self.libelle,
            "sieges": list(self.sieges),
            "kneeboard": self.kneeboard is not None,
            "panneaux": list(self.panneaux),
            "ecrans": [{"id": e.id, "libelle": e.libelle, "par_cote": e.par_cote,
                        "par_cote_y": e.par_cote_y, "aspect": e.aspect,
                        "arrondi": e.arrondi,
                        "reperes_x": list(e.reperes_x) if e.reperes_x else None,
                        "reperes_y": list(e.reperes_y) if e.reperes_y else None,
                        "boutons": [{"id": b.id, "cote": b.cote, "rang": b.rang}
                                    for b in e.boutons]}
                       for e in self.ecrans],
        }


def reperes(premier: float, dernier: float, n: int, demi_image: float,
            vers_le_bas: bool = False) -> Tuple[float, ...]:
    """`n` libellés également espacés de `premier` à `dernier`, en unités du
    module (0 au centre de l'image, y vers le haut ; `demi_image` unités du
    centre au bord), en fraction de l'image depuis la gauche — ou depuis le
    haut, `vers_le_bas`."""
    pas = (dernier - premier) / (n - 1)
    signe = -1 if vers_le_bas else 1
    return tuple(round(0.5 + signe * (premier + i * pas) / (2 * demi_image), 4)
                 for i in range(n))


def couronne_horaire(par_cote: int, premier_cote: str,
                     boutons: Sequence[Tuple[str, int]]) -> Tuple[Bouton, ...]:
    """Place des boutons numérotés dans le sens horaire autour d'un cadre.

    Le sens horaire parcourt le côté gauche de bas en haut, le haut de gauche à
    droite, la droite de haut en bas, le bas de droite à gauche ; on commence
    au premier bouton de `premier_cote` dans ce sens. C'est la numérotation
    des DDI du Hornet (depuis le bas du côté gauche) comme des MFCD de l'A-10C
    (depuis la gauche du haut).
    """
    debut = COTES.index(premier_cote)
    places = []
    for k in range(4):
        cote = COTES[(debut + k) % 4]
        rangs = range(par_cote) if cote in ("haut", "droite") else range(par_cote - 1, -1, -1)
        places += [(cote, r) for r in rangs]
    return tuple(Bouton(id_, commande, cote, rang)
                 for (id_, commande), (cote, rang) in zip(boutons, places))


# --------------------------------------------------------------- registre

from . import (a10c, ah64d, f16c, fa18c, modernes, oh58d, sans_ecran,  # noqa: E402
               warbirds)  # (s'appuient sur ce qui précède)

PROFILS: Tuple[Profil, ...] = (
    fa18c.PROFIL, f16c.PROFIL, ah64d.PROFIL, oh58d.PROFIL, a10c.PROFIL,
    modernes.AV8B, modernes.F15E, modernes.JF17, modernes.KA50, modernes.CH47F,
) + sans_ecran.PROFILS + warbirds.PROFILS

# Tout autre appareil : pas d'écran connu, pas de commande. La capture du
# kneeboard marche partout (c'est celui de DCS), pas ses pages : l'appareil
# qui les tourne n'est sûr que pour les modules relevés.
GENERIQUE = Profil(id="generique", libelle="Autre appareil", noms_dcs=())

PAR_DEFAUT = fa18c.PROFIL           # avant que DCS ait annoncé quoi que ce soit


def profil_pour(nom_dcs: Optional[str]) -> Profil:
    for profil in PROFILS:
        if nom_dcs in profil.noms_dcs:
            return profil
    return GENERIQUE


def profil_par_id(id_: str) -> Optional[Profil]:
    return next((p for p in PROFILS if p.id == id_), None)


def viewports() -> List[str]:
    """Toutes les zones d'export utilisées par un profil, sans doublon."""
    vus: List[str] = []
    for profil in PROFILS:
        for ecran in profil.ecrans:
            if ecran.viewport not in vus:
                vus.append(ecran.viewport)
    return vus


# --------------------------------------------------------------- Lua

def _ensemble(valeurs: Iterable[int]) -> str:
    return "{ " + ", ".join(f"[{v}] = true" for v in sorted(set(valeurs))) + " }"


def lua_appareils() -> str:
    """Liste blanche du script Lua, par appareil. Générée, jamais écrite à la main."""
    lignes = [
        "-- DCS Tablette : liste blanche par appareil.",
        "-- GENERE par scripts/generer_lua_appareils.py depuis src/tablette/appareils :",
        "-- ne pas modifier a la main, relancer le script.",
        "TABLETTE_APPAREILS = {",
    ]
    for profil in PROFILS:
        boutons: Dict[int, set] = {}
        for ecran in profil.ecrans:
            for appareil in ecran.appareils.values():
                boutons.setdefault(appareil, set()).update(b.commande for b in ecran.boutons)
        for appareil, commandes in profil.touches.items():
            boutons.setdefault(appareil, set()).update(commandes)
        boutons = {a: c for a, c in boutons.items() if c}
        corps = [
            "    boutons = {" + "".join(f"\n      [{a}] = {_ensemble(c)},"
                                        for a, c in sorted(boutons.items())) + "\n    },",
            "    molettes = {" + "".join(
                f"\n      [{a}] = {{ " + ", ".join(f"[{c}] = {v:g}" for c, v in sorted(m.items()))
                + " },"
                for a, m in sorted(profil.molettes.items())) + "\n    },",
            "    pages = {" + (f" [{profil.kneeboard}] = {_ensemble((3001, 3002))} "
                               if profil.kneeboard is not None else " ") + "},",
            "    textes = { " + ", ".join(map(str, profil.textes)) + " },",
            "    arguments = { " + ", ".join(map(str, profil.arguments)) + " },",
        ]
        for nom in profil.noms_dcs:
            lignes.append(f'  ["{nom}"] = {{')
            lignes += corps
            lignes.append("  },")
    lignes.append("}")
    return "\n".join(lignes) + "\n"
