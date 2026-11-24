"""La page Écrans du PC : régler soi-même ses écrans et les zones des écrans
du cockpit, en voyant avant ce qui va changer.

Retours d'un pilote (Discord, 05 au 20/11/2026) : la partie tablette « est
pas mal du tout ; ce qu'il manque, c'est l'étape juste avant » — trop
d'automatismes, une disposition qu'on ne peut pas choisir, et aucune
fenêtre qui dise ce que les exports vont devenir. D'où cette page, partie
de la vue de Windows :

- les écrans tels que Windows les place, chacun avec x, y, largeur,
  hauteur, à retoucher (la définition des écrans virtuels seulement : 760 ×
  760 pour un petit écran carré, que le pilote de l'écran virtuel apprend
  au passage) ; leur nombre ;
- la fenêtre de DCS (la résolution d'options.lua), qui part du coin haut
  gauche de l'écran principal ;
- les zones des écrans du cockpit, à glisser ou à régler au pixel, pour
  tous les appareils ou pour ceux dont les écrans ne sont pas carrés ;
- avant d'enregistrer, ce qui va changer, en clair, et les problèmes du
  schéma (apercu.py) ;
- « Montrer sur mes écrans » (calage.py) : les zones posées sur les vrais
  écrans, pour les caler sur un cadre de MFD physique.

Enregistrer passe DCS Tablette « à ma main » : le diagnostic ne déplace
plus ni ne réécrit rien (diagnostic.py). « Automatique » rend la main à
DCS Tablette, qui remet sa disposition. Des écrans de Windows déplacés
reviennent d'eux-mêmes si on ne confirme pas dans les DELAI_S secondes,
comme dans Paramètres → Écran : une disposition qui cacherait la page ne
reste pas.

DCS ouvert, rien n'est enregistré : il réécrit options.lua en quittant, et
relit ses écrans au démarrage seulement.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import apercu, appareils
from .calage import reperes_d_ecran
from .ecrans_dcs import (EXPORTS, NOM_AFFICHE, NOM_FICHIER, PasDExport, generer, lire_zones,
                         options_affichage, regler_options)
from .installation import dcs_ouvert, ecrire_choix, lire_choix
from .langues import Texte

Rect = Tuple[int, int, int, int]

DELAI_S = 20
VIRTUELS_MAX = 4
TAILLE_VIRTUEL = ((320, 7680), (240, 4320))
TAILLE_FENETRE = ((640, 16384), (480, 16384))
ZONE_MIN = 50
# Les définitions proposées pour un écran virtuel, en plus des siennes : de
# petits écrans carrés ou 4:3 pour un MFD seul (demande : 760 × 760, 800 × 800).
DEFINITIONS = ((760, 760), (800, 800), (1024, 768), (1024, 1024), (1280, 1024),
               (1920, 1080), (2560, 1440))
LIBELLES_ZONES = {"LEFT_MFCD": Texte("Écran gauche"), "RIGHT_MFCD": Texte("Écran droit"),
                  "CENTER_MFCD": Texte("Écran central"), "TEDAC": Texte("TEDAC")}


class Refus(Exception):
    """Ce qui empêche d'enregistrer, dit au pilote."""


def _entier(valeur, defaut: Optional[int] = None) -> int:
    if isinstance(valeur, bool):
        raise Refus(Texte("valeur illisible : {valeur}", valeur=valeur))
    try:
        return int(round(float(valeur)))
    except (TypeError, ValueError):
        if defaut is not None:
            return defaut
        raise Refus(Texte("valeur illisible : {valeur}", valeur=valeur))


def _rect(d: Dict) -> Rect:
    return (_entier(d.get("x")), _entier(d.get("y")), _entier(d.get("largeur")),
            _entier(d.get("hauteur")))


def _dico(r: Sequence[int]) -> Dict[str, int]:
    return {"x": r[0], "y": r[1], "largeur": r[2], "hauteur": r[3]}


def _chevauche(a: Rect, b: Rect) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _touche(a: Rect, b: Rect) -> bool:
    """Deux écrans collés par un bord (Windows n'en accepte pas d'isolé)."""
    cote = (a[0] + a[2] == b[0] or b[0] + b[2] == a[0]) and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]
    dessus = (a[1] + a[3] == b[1] or b[1] + b[3] == a[1]) and a[0] < b[0] + b[2] and b[0] < a[0] + a[2]
    return cote or dessus


def profils_avec_ecrans(langue: str) -> List[Dict]:
    """Les appareils dont des écrans sont exportés : libellé de chaque zone
    et repères de ses boutons, pour le schéma et le calage."""
    resultat = []
    for profil in appareils.PROFILS:
        if not profil.ecrans:
            continue
        vus = {}
        for e in profil.ecrans:
            vus.setdefault(e.viewport, {"zone": e.viewport, "libelle": e.libelle,
                                        "aspect": e.aspect, "reperes": reperes_d_ecran(e)})
        resultat.append({"id": profil.id, "libelle": profil.libelle,
                         "noms_dcs": list(profil.noms_dcs), "zones": list(vus.values())})
    return sorted(resultat, key=lambda p: str(p["libelle"]).casefold())


class ReglageEcrans:
    """L'état de la page, et ce qu'elle fait. Tout ce qui touche Windows ou
    DCS se remplace (tests) : `lister` (ecran_virtuel.lister), `disposer`
    (ecran_virtuel.disposer), `ouvert` (DCS tourne ?), `commande` (canal du
    pilote de l'écran virtuel), `modes` (ecran_virtuel.proposer_modes),
    `remettre` (ecran_virtuel.remettre), `configurer`
    (installation.configurer_ecrans), `choix` / `ecrire` (installation.json),
    `attendre`, `minuteur` (le retour en arrière)."""

    def __init__(self, saved_games: Path,
                 lister: Optional[Callable[[], list]] = None,
                 disposer: Optional[Callable[[Sequence], Optional[str]]] = None,
                 ouvert: Callable[[], bool] = dcs_ouvert,
                 commande: Optional[Callable[[str], None]] = None,
                 modes: Optional[Callable[..., bool]] = None,
                 remettre: Optional[Callable[..., Tuple[str, str, List[str]]]] = None,
                 configurer: Optional[Callable[..., Tuple[bool, List[str]]]] = None,
                 nombre_virtuels: Optional[Callable[[], int]] = None,
                 choix: Callable[[], Dict] = lire_choix,
                 ecrire: Callable[[Dict], None] = ecrire_choix,
                 attendre: Callable[[float], None] = time.sleep,
                 minuteur: Callable[[float, Callable[[], None]], object] = None):
        if lister is None or disposer is None:
            from . import ecran_virtuel           # Windows seulement
            lister = lister or ecran_virtuel.lister
            disposer = disposer or ecran_virtuel.disposer
            commande = commande or ecran_virtuel.commande_vdd
            modes = modes or ecran_virtuel.proposer_modes
            remettre = remettre or ecran_virtuel.remettre
        self.saved_games = saved_games
        self._lister, self._disposer, self._ouvert = lister, disposer, ouvert
        self._commande, self._modes, self._remettre = commande, modes, remettre
        self._configurer = configurer
        self._nombre_virtuels = nombre_virtuels
        self._choix, self._ecrire, self._attendre = choix, ecrire, attendre
        self._minuteur = minuteur or self._minuteur_threading
        self._verrou = threading.Lock()
        self._avant: Optional[List] = None        # écrans à remettre faute de confirmation
        self._delai = None

    # ------------------------------------------------------------ lire

    def _texte_tablette(self) -> str:
        try:
            return (self.saved_games / "Config" / "MonitorSetup" / NOM_FICHIER).read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def _virtuels(self, ecrans: Sequence) -> int:
        if self._nombre_virtuels is not None:
            return self._nombre_virtuels()
        try:
            from .ecran_virtuel import dossier_vdd, nombre_de_virtuels
            return nombre_de_virtuels((dossier_vdd() / "vdd_settings.xml").read_text(
                encoding="utf-8"))
        except (OSError, ImportError):
            return sum(e.virtuel for e in ecrans)

    def etat(self, langue: str = "fr") -> Dict:
        """Ce que la page dessine : les écrans, la fenêtre de DCS, les zones
        de « Tablette DCS » (pour tous les appareils, et pour ceux dont les
        écrans ne sont pas carrés), le mode, et les problèmes du schéma."""
        ecrans = self._lister()
        try:
            configuration, largeur, hauteur = options_affichage(self.saved_games)
            fenetre: Optional[Tuple[int, int]] = (largeur, hauteur)
        except PasDExport:
            configuration, fenetre = None, None
        texte = self._texte_tablette()
        l, h = fenetre or (0, 0)
        zones = lire_zones(texte, l, h) if texte else {}
        par_appareil = {}
        for nom in appareils.formes():
            siennes = lire_zones(texte, l, h, nom) if texte else {}
            if siennes and siennes != zones:
                par_appareil[nom] = {z: _dico(r) for z, r in siennes.items()}
        choix = self._choix()
        disposition = apercu.calculer(ecrans, fenetre, zones,
                                      {z: str(t) for z, t in LIBELLES_ZONES.items()})
        return {
            "ecrans": [{"id": e.nom, "nom": apercu._nom(e), "x": e.x, "y": e.y,
                        "largeur": e.largeur, "hauteur": e.hauteur, "frequence": e.frequence,
                        "principal": e.principal, "virtuel": e.virtuel, "actif": e.actif,
                        "modes": sorted({(m[0], m[1]) for m in e.modes} | (
                            set(DEFINITIONS) if e.virtuel else set()))}
                       for e in ecrans],
            "fenetre": {"largeur": fenetre[0], "hauteur": fenetre[1]} if fenetre else None,
            "configuration": configuration,
            "tablette": bool(configuration) and configuration.lower() in (
                Path(NOM_FICHIER).stem, NOM_AFFICHE.lower()),
            "zones": {z: _dico(r) for z, r in zones.items()},
            "par_appareil": par_appareil,
            "formes": {nom: forme for nom, forme in appareils.formes().items()},
            "libelles": dict(LIBELLES_ZONES),
            "profils": profils_avec_ecrans(langue),
            "a_la_main": bool(choix.get("a_la_main")),
            "dcs_ouvert": bool(self._ouvert()),
            "virtuels": self._virtuels(ecrans),
            "virtuels_max": VIRTUELS_MAX,
            "apercu": disposition,
            "en_attente": self.en_attente(),
        }

    # ------------------------------------------------------------ comprendre

    def _lire_proposition(self, proposition: Dict, ecrans: Sequence
                          ) -> Tuple[List[Tuple[object, Rect]], Tuple[int, int],
                                     Dict[str, Rect], Dict[str, Dict[str, Rect]], List[Texte]]:
        """La proposition de la page, vérifiée : chaque écran à sa place
        voulue, la fenêtre de DCS, les zones. Lève Refus pour ce qui ne peut
        pas marcher ; rend en plus ce qui mérite d'être dit."""
        par_id = {e.nom: e for e in ecrans if e.actif}
        voulus: List[Tuple[object, Rect]] = []
        remarques: List[Texte] = []
        for d in proposition.get("ecrans") or []:
            e = par_id.get(str(d.get("id")))
            if e is None:
                raise Refus(Texte("Écran inconnu ou débranché : {id} (relire la page).",
                                  id=d.get("id")))
            x, y = _entier(d.get("x")), _entier(d.get("y"))
            if e.virtuel:
                l, h = _entier(d.get("largeur"), e.largeur), _entier(d.get("hauteur"), e.hauteur)
                (lmin, lmax), (hmin, hmax) = TAILLE_VIRTUEL
                if not (lmin <= l <= lmax and hmin <= h <= hmax):
                    raise Refus(Texte("Écran virtuel de {largeur}×{hauteur} : entre {lmin}×{hmin} "
                                      "et {lmax}×{hmax}.", largeur=l, hauteur=h, lmin=lmin,
                                      hmin=hmin, lmax=lmax, hmax=hmax))
            else:
                l, h = e.largeur, e.hauteur
            if e.principal and (x, y) != (0, 0):
                raise Refus(Texte("L'écran principal reste en (0, 0) pour Windows : déplacer "
                                  "plutôt les autres autour de lui."))
            voulus.append((e, (x, y, l, h)))
        vus = {e.nom for e, _ in voulus}
        voulus += [(e, (e.x, e.y, e.largeur, e.hauteur)) for e in par_id.values()
                   if e.nom not in vus]
        for i, (a, ra) in enumerate(voulus):
            for b, rb in voulus[i + 1:]:
                if _chevauche(ra, rb):
                    raise Refus(Texte("Les écrans {a} et {b} se chevauchent.",
                                      a=apercu._nom(a), b=apercu._nom(b)))
        if len(voulus) > 1:
            for e, r in voulus:
                if not any(_touche(r, autre) for f, autre in voulus if f is not e):
                    remarques.append(Texte("{ecran} ne touche aucun autre écran : Windows le "
                                           "recollera au plus près.", ecran=apercu._nom(e)))
        fenetre = proposition.get("fenetre") or {}
        largeur, hauteur = _entier(fenetre.get("largeur")), _entier(fenetre.get("hauteur"))
        (lmin, lmax), (hmin, hmax) = TAILLE_FENETRE
        if not (lmin <= largeur <= lmax and hmin <= hauteur <= hmax):
            raise Refus(Texte("Fenêtre de DCS de {largeur}×{hauteur} : entre {lmin}×{hmin} et "
                              "{lmax}×{hmax}.", largeur=largeur, hauteur=hauteur, lmin=lmin,
                              hmin=hmin, lmax=lmax, hmax=hmax))

        def zones_de(d) -> Dict[str, Rect]:
            resultat = {}
            for nom, r in (d or {}).items():
                if nom not in EXPORTS or r is None:
                    continue
                rect = _rect(r)
                if rect[2] < ZONE_MIN or rect[3] < ZONE_MIN:
                    raise Refus(Texte("Zone {zone} trop petite ({largeur}×{hauteur}).", zone=nom,
                                      largeur=rect[2], hauteur=rect[3]))
                resultat[nom] = rect
            return resultat
        zones = zones_de(proposition.get("zones"))
        par_appareil = {str(nom): zones_de(z) for nom, z in
                        (proposition.get("par_appareil") or {}).items()
                        if str(nom) in appareils.formes()}
        return voulus, (largeur, hauteur), zones, par_appareil, remarques

    def apercu(self, proposition: Dict) -> Dict:
        """Ce que l'enregistrement changerait, en clair, et le schéma de la
        disposition proposée avec ses problèmes. Rien n'est modifié."""
        ecrans = self._lister()
        try:
            voulus, fenetre, zones, par_appareil, remarques = self._lire_proposition(
                proposition, ecrans)
        except Refus as e:
            return {"changements": [], "erreurs": [e.args[0]], "apercu": None}
        changements = self._changements(ecrans, voulus, fenetre, zones, par_appareil)
        places = [self._ecran_deplace(e, r) for e, r in voulus]
        libelles = {z: str(t) for z, t in LIBELLES_ZONES.items()}
        disposition = apercu.calculer(places, fenetre, zones, libelles)
        # Les zones à part (Kiowa, JF-17) restent où elles étaient quand on
        # déplace les autres : leurs problèmes sont dits aussi, par appareil.
        disposition["par_appareil"] = {
            nom: [{"nom": z["nom"], "problemes": z["problemes"]}
                  for z in apercu.calculer(places, fenetre, siennes, libelles)["zones"]]
            for nom, siennes in par_appareil.items()}
        erreurs = []
        if self._ouvert():
            erreurs.append(Texte("DCS est ouvert : le fermer pour enregistrer (il réécrit ses "
                                 "réglages en quittant, et ne relit ses écrans qu'au démarrage)."))
        return {"changements": changements + remarques, "erreurs": erreurs,
                "apercu": disposition}

    @staticmethod
    def _ecran_deplace(e, r: Rect):
        from dataclasses import replace
        return replace(e, x=r[0], y=r[1], largeur=r[2], hauteur=r[3])

    def _changements(self, ecrans: Sequence, voulus, fenetre: Tuple[int, int],
                     zones: Dict[str, Rect], par_appareil: Dict[str, Dict[str, Rect]]
                     ) -> List[Texte]:
        lignes: List[Texte] = []
        for e, (x, y, l, h) in voulus:
            if (l, h) != (e.largeur, e.hauteur):
                lignes.append(Texte("Écran virtuel {ecran} : {avant} → {largeur}×{hauteur}",
                                    ecran=apercu._nom(e), avant=f"{e.largeur}×{e.hauteur}",
                                    largeur=l, hauteur=h))
                if (l, h) not in {(m[0], m[1]) for m in e.modes}:
                    lignes.append(Texte("  définition nouvelle pour le pilote de l'écran virtuel : "
                                        "il est rechargé, les écrans clignotent quelques "
                                        "secondes."))
            if (x, y) != (e.x, e.y):
                lignes.append(Texte("Écran {ecran} : de ({x0}, {y0}) à ({x}, {y})",
                                    ecran=apercu._nom(e), x0=e.x, y0=e.y, x=x, y=y))
        if any((r[0], r[1], r[2], r[3]) != (e.x, e.y, e.largeur, e.hauteur) for e, r in voulus):
            lignes.append(Texte("Écrans de Windows remis comme avant dans {secondes} s si vous ne "
                                "confirmez pas.", secondes=DELAI_S))
        try:
            choix, al, ah = options_affichage(self.saved_games)
        except PasDExport:
            choix, al, ah = "", 0, 0
        if (al, ah) != fenetre or choix.lower() not in (Path(NOM_FICHIER).stem,
                                                        NOM_AFFICHE.lower()):
            lignes.append(Texte("DCS : configuration « {nom} », fenêtre {largeur}×{hauteur}, "
                                "fenêtré (avant : « {choix} », {avant})", nom=NOM_AFFICHE,
                                largeur=fenetre[0], hauteur=fenetre[1], choix=choix or "?",
                                avant=f"{al}×{ah}"))
        texte = self._texte_tablette()
        anciennes = lire_zones(texte, al, ah) if texte and al else {}
        for nom in EXPORTS:
            avant, apres = anciennes.get(nom), zones.get(nom)
            if apres and apres != avant:
                lignes.append(Texte("{zone} : x={x} y={y} {largeur}×{hauteur}",
                                    zone=LIBELLES_ZONES[nom], x=apres[0], y=apres[1],
                                    largeur=apres[2], hauteur=apres[3]))
            elif avant and not apres:
                lignes.append(Texte("{zone} : plus exporté (l'écran reste dans le cockpit)",
                                    zone=LIBELLES_ZONES[nom]))
        for nom, siennes in par_appareil.items():
            anciennes_app = lire_zones(texte, al, ah, nom) if texte and al else {}
            if siennes != anciennes_app:
                lignes.append(Texte("Zones à part pour {appareil} : {nombre}", appareil=nom,
                                    nombre=len(siennes)))
        if not self._choix().get("a_la_main"):
            lignes.append(Texte("Écrans à votre main : DCS Tablette ne les déplacera ni ne les "
                                "réécrira plus (« Automatique » pour revenir à sa disposition)."))
        return lignes

    # ------------------------------------------------------------ appliquer

    def appliquer(self, proposition: Dict) -> Dict:
        """Enregistre la proposition : écrans de Windows (retour en arrière
        sans confirmation), « Tablette DCS » et options.lua, mode « à ma
        main ». Rend ce qui a été fait, et s'il faut confirmer."""
        with self._verrou:
            if self._ouvert():
                raise Refus(Texte("DCS est ouvert : le fermer pour enregistrer (il réécrit ses "
                                  "réglages en quittant, et ne relit ses écrans qu'au "
                                  "démarrage)."))
            ecrans = self._lister()
            voulus, fenetre, zones, par_appareil, _ = self._lire_proposition(proposition, ecrans)
            lignes: List[Texte] = []
            places = self._places(voulus)
            if places:
                lignes += self._poser(places, voulus)
            self._ecrire_dcs(ecrans, fenetre, zones, par_appareil)
            lignes.append(Texte("« {nom} » écrite, DCS réglé en {largeur}×{hauteur}, fenêtré.",
                                nom=NOM_AFFICHE, largeur=fenetre[0], hauteur=fenetre[1]))
            choix = self._choix()
            self._ecrire(dict(choix, a_la_main=True))
            return {"lignes": lignes, "a_confirmer": DELAI_S if self._avant else 0}

    def _places(self, voulus) -> List:
        from .ecran_virtuel import Place
        return [p for p in (Place(e, r[0], r[1], r[2] if e.virtuel else None,
                                  r[3] if e.virtuel else None, e.frequence)
                            for e, r in voulus) if p.change]

    def _poser(self, places: List, voulus) -> List[Texte]:
        """Les écrans à leur place : d'abord, si l'écran virtuel ne connaît
        pas une définition, le pilote l'apprend et se recharge ; puis tout est
        posé d'un coup, et relu."""
        from .ecran_virtuel import Place
        lignes: List[Texte] = []
        nouvelles = sorted({(p.largeur, p.hauteur) for p in places
                            if p.ecran.virtuel and p.largeur
                            and (p.largeur, p.hauteur) not in {(m[0], m[1]) for m in p.ecran.modes}})
        if nouvelles:
            frequence = max((p.ecran.frequence for p in places if p.ecran.virtuel), default=60)
            try:
                recharge = self._modes(nouvelles, frequence, commande=self._commande)
            except OSError as e:
                raise Refus(Texte("Définition {definitions} pas ajoutée à l'écran virtuel ({erreur}).",
                                  definitions=[f"{l}×{h}" for l, h in nouvelles], erreur=e))
            if recharge:
                lignes.append(Texte("Écran virtuel : {definitions} ajoutée(s), pilote rechargé.",
                                    definitions=[f"{l}×{h}" for l, h in nouvelles]))
                attendus = sum(e.virtuel for e, _ in voulus)
                for _ in range(20):
                    self._attendre(1)
                    if sum(e.virtuel and e.actif for e in self._lister()) >= attendus:
                        break
                # Le pilote rechargé, Windows a pu renommer ses écrans : relus.
                nouveaux = {e.nom: e for e in self._lister()}
                virtuels = [e for e in nouveaux.values() if e.virtuel and e.actif]
                refaites = []
                for p in places:
                    e = nouveaux.get(p.ecran.nom)
                    if e is None and p.ecran.virtuel and virtuels:
                        e = virtuels.pop(0)
                    if e is not None:
                        refaites.append(Place(e, p.x, p.y, p.largeur, p.hauteur, p.frequence))
                places = refaites
        self._avant = [Place(p.ecran, p.ecran.x, p.ecran.y, p.ecran.largeur, p.ecran.hauteur,
                             p.ecran.frequence) for p in places]
        erreur = self._disposer(places)
        if erreur:
            self._remettre_avant()
            raise Refus(Texte("Écrans non déplacés : {erreur}.", erreur=erreur))
        self._attendre(1)
        apres = {e.nom: e for e in self._lister()}
        for p in places:
            e = apres.get(p.ecran.nom)
            if e is None:
                continue
            voulu = (p.x, p.y) + ((p.largeur, p.hauteur) if p.largeur else (e.largeur, e.hauteur))
            if (e.x, e.y, e.largeur, e.hauteur) != voulu:
                lignes.append(Texte("Windows a mis {ecran} en ({x}, {y}), {largeur}×{hauteur}.",
                                    ecran=apercu._nom(e), x=e.x, y=e.y, largeur=e.largeur,
                                    hauteur=e.hauteur))
        lignes.append(Texte("Écrans de Windows posés : confirmer dans les {secondes} s, sinon "
                            "ils reviennent comme avant.", secondes=DELAI_S))
        self._delai = self._minuteur(DELAI_S, self._expire)
        return lignes

    def _ecrire_dcs(self, ecrans: Sequence, fenetre: Tuple[int, int], zones: Dict[str, Rect],
                    par_appareil: Dict[str, Dict[str, Rect]]) -> None:
        principal = next((e for e in ecrans if e.principal), None)
        if principal is None:
            raise Refus(Texte("Écran principal introuvable."))
        dossier = self.saved_games / "Config" / "MonitorSetup"
        dossier.mkdir(parents=True, exist_ok=True)
        fichier = dossier / NOM_FICHIER
        texte = generer((0, 0, principal.largeur, principal.hauteur), zones,
                        "Reglee a la main (page Ecrans de DCS Tablette)",
                        {nom: z for nom, z in par_appareil.items()} or None)
        if fichier.exists():
            fichier.replace(fichier.with_suffix(".lua.precedent"))
        fichier.write_text(texte, encoding="ascii")
        try:
            regler_options(self.saved_games, *fenetre)
        except (OSError, PasDExport) as e:
            raise Refus(Texte("« {nom} » écrite, mais réglages de DCS non modifiés ({erreur}).",
                              nom=NOM_AFFICHE, erreur=e))

    # ------------------------------------------------------------ confirmer

    @staticmethod
    def _minuteur_threading(secondes: float, action: Callable[[], None]):
        t = threading.Timer(secondes, action)
        t.daemon = True
        t.start()
        return t

    def en_attente(self) -> bool:
        return self._avant is not None

    def garder(self) -> None:
        """Les écrans posés conviennent : plus de retour en arrière."""
        with self._verrou:
            self._annuler_minuteur()
            self._avant = None

    def annuler(self) -> Optional[str]:
        """« Revenir » : les écrans reprennent leur place d'avant tout de
        suite (les réglages de DCS restent)."""
        with self._verrou:
            self._annuler_minuteur()
            return self._remettre_avant()

    def _expire(self) -> None:
        with self._verrou:
            self._remettre_avant()

    def _annuler_minuteur(self) -> None:
        if self._delai is not None and hasattr(self._delai, "cancel"):
            self._delai.cancel()
        self._delai = None

    def _remettre_avant(self) -> Optional[str]:
        avant, self._avant = self._avant, None
        if not avant:
            return None
        return self._disposer(avant)

    # ------------------------------------------------------------ le reste

    def nombre_virtuels(self, nombre: int) -> List[Texte]:
        """Change le nombre d'écrans virtuels (pilote rechargé) : deux petits
        écrans de part et d'autre d'un écran réel, par exemple."""
        nombre = _entier(nombre)
        if not 1 <= nombre <= VIRTUELS_MAX:
            raise Refus(Texte("De 1 à {max} écrans virtuels.", max=VIRTUELS_MAX))
        if self._ouvert():
            raise Refus(Texte("DCS est ouvert : le fermer avant de changer les écrans virtuels."))
        try:
            self._commande(f"SETDISPLAYCOUNT {nombre}")
        except OSError as e:
            raise Refus(Texte("Le pilote de l'écran virtuel ne répond pas ({erreur}) : "
                              "installé par Installer.bat ?", erreur=e))
        for _ in range(20):
            self._attendre(1)
            if sum(e.virtuel and e.actif for e in self._lister()) == nombre:
                break
        return [Texte("{nombre} écran(s) virtuel(s) : les placer, puis Enregistrer.",
                      nombre=nombre)]

    def automatique(self) -> List[Texte]:
        """Rend la main à DCS Tablette : il remet l'écran virtuel à sa place
        et réécrit « Tablette DCS » pour ces écrans (comme Installer.bat)."""
        with self._verrou:
            if self._ouvert():
                raise Refus(Texte("DCS est ouvert : le fermer pour revenir à la disposition "
                                  "automatique."))
            choix = self._choix()
            self._ecrire({k: v for k, v in choix.items() if k != "a_la_main"})
            etat, detail, solution = self._remettre(True, bool(choix.get("physique")))
            lignes: List[Texte] = [Texte("Écran virtuel : {detail}", detail=detail)] + list(
                solution)
            configurer = self._configurer
            if configurer is None:
                from .installation import configurer_ecrans as configurer
            moniteurs = [(e.x, e.y, e.largeur, e.hauteur, e.principal, e.virtuel)
                         for e in self._lister() if e.actif]
            _, faites = configurer(self.saved_games, choix.get("mode") == "essai", moniteurs,
                                   self._ouvert, physique=bool(choix.get("physique")))
            return lignes + faites
