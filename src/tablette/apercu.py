"""L'aperçu de la disposition des écrans : où DCS va dessiner chaque écran
exporté, à l'échelle, pour le schéma du panneau Diagnostic de la tablette.

Idée d'un pilote (Discord, fil « Ajouter aperçu exports », 05/11/2026) :
voir avant de voler où tombent les exports. Tout est relu, rien n'est
supposé :
- les écrans de Windows, leur place, leur taille, leur modèle
  (ecran_virtuel.lister) ;
- la fenêtre de DCS : la résolution réglée dans options.lua, à partir du
  coin haut gauche du principal (voir installation.supports) ;
- les zones exportées par la configuration d'écrans choisie dans DCS,
  telles qu'il les donne à l'appareil piloté (ecrans_dcs.lire_zones) ;
- la zone du kneeboard, que DCS colle en bas à droite de sa fenêtre
  (ecrans_dcs.zone_kneeboard), avec son bandeau.
Une autre disposition que celle d'Installer.bat (écran virtuel plus petit,
écrans exportés ailleurs, configuration du pilote) se dessine donc telle
qu'elle est.

Ce qui pose problème est marqué, avec la raison : une zone hors des écrans
ou hors de la fenêtre de DCS (rien n'y est dessiné), une zone sous le
kneeboard (il la cache une fois ouvert), un écran réel couvert par la
fenêtre de DCS (il resterait noir en vol), un écran à gauche décalé en
hauteur (DCS partirait de lui, installation.genants).

Rien n'est modifié : c'est un aperçu.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

from .ecrans_dcs import (BANDEAU_KNEEBOARD, PasDExport, fichier_actif, lire_zones,
                         options_affichage, zone_kneeboard)
from .installation import genants
from .langues import Texte, message

Rect = Tuple[int, int, int, int]       # x, y, largeur, hauteur


def _commun(a: Rect, b: Rect) -> int:
    """La surface que deux rectangles ont en commun."""
    largeur = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    hauteur = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0, largeur) * max(0, hauteur)


def _dedans(zone: Rect, cadre: Rect) -> bool:
    return _commun(zone, cadre) == zone[2] * zone[3]


def _hors_ecrans(zone: Rect, ecrans: Sequence[Rect]) -> Optional[Texte]:
    """Une zone hors de tout écran, en tout ou en partie : DCS n'y dessine
    rien que l'on voie ou que l'on capture. Les écrans du bureau ne se
    chevauchent pas : la zone est couverte si les parts communes font sa
    surface."""
    vue = sum(_commun(zone, e) for e in ecrans)
    if vue == 0:
        return Texte("hors de tout écran")
    if vue < zone[2] * zone[3]:
        return Texte("en partie hors des écrans")
    return None


def _nom(ecran) -> str:
    """Le modèle de l'écran (« LG ULTRAGEAR ») ; le pilote pour l'écran
    virtuel ; sinon son numéro dans Windows."""
    if ecran.modele:
        return ecran.modele
    if ecran.virtuel:
        return ecran.carte
    numero = re.search(r"(\d+)$", ecran.nom)
    return Texte("Écran {numero}", numero=numero.group(1)) if numero else ecran.nom


def _rect(r: Rect) -> Dict[str, int]:
    return {"x": r[0], "y": r[1], "largeur": r[2], "hauteur": r[3]}


def calculer(ecrans: Sequence, resolution: Optional[Tuple[int, int]],
             zones: Dict[str, Rect], libelles: Optional[Dict[str, str]] = None) -> Dict:
    """La disposition, en coordonnées du bureau de Windows.

    `ecrans` : ceux de ecran_virtuel.lister (seuls ceux du bureau comptent).
    `resolution` : la taille de la fenêtre de DCS réglée dans options.lua,
    None si on ne la connaît pas. `zones` : les zones exportées, en
    coordonnées de la fenêtre de DCS. `libelles` : le nom à montrer pour
    chaque zone (« DDI gauche »), sinon le sien (LEFT_MFCD).

    Chaque écran, zone ou kneeboard porte la liste de ses `problemes` (des
    `Texte`), vide quand tout va bien.
    """
    actifs = [e for e in ecrans if e.actif and e.largeur > 0 and e.hauteur > 0]
    principal = next((e for e in actifs if e.principal), None)
    places = [(e.x, e.y, e.largeur, e.hauteur) for e in actifs]
    resultat: Dict = {"ecrans": [], "fenetre": None, "zones": [], "kneeboard": None}

    fenetre = None
    if principal is not None and resolution is not None:
        fenetre = (principal.x, principal.y) + tuple(resolution)
        resultat["fenetre"] = _rect(fenetre)
    ox, oy = (principal.x, principal.y) if principal is not None else (0, 0)

    kneeboard = None
    if resolution is not None:
        kx, ky, kl, kh = zone_kneeboard(*resolution)
        # Avec son bandeau (flèches, marque-pages) : il cache aussi ce qui est dessous.
        kneeboard = (ox + kx - BANDEAU_KNEEBOARD, oy + ky, kl + BANDEAU_KNEEBOARD, kh)
        hors = _hors_ecrans(kneeboard, places)
        resultat["kneeboard"] = {**_rect(kneeboard), "problemes": [hors] if hors else []}

    exportes = []
    for nom, (x, y, l, h) in zones.items():
        zone = (ox + x, oy + y, l, h)
        exportes.append(zone)
        problemes = []
        hors = _hors_ecrans(zone, places)
        if hors:
            problemes.append(hors)
        if fenetre is not None and not _dedans(zone, fenetre):
            problemes.append(Texte("hors de la fenêtre de DCS : elle n'y est pas dessinée"))
        if kneeboard is not None and _commun(zone, kneeboard):
            problemes.append(Texte("sous le kneeboard : cachée quand il est ouvert"))
        resultat["zones"].append({"nom": nom, "libelle": (libelles or {}).get(nom, nom),
                                  **_rect(zone), "problemes": problemes})

    decales = {tuple(m[:4]) for m in genants([(e.x, e.y, e.largeur, e.hauteur, e.principal,
                                               e.virtuel) for e in actifs])}
    for e, place in zip(actifs, places):
        problemes = []
        # Un écran réel sous la fenêtre de DCS, qui n'y reçoit aucun écran
        # exporté : DCS le couvre de noir. Le principal porte la vue ; un
        # écran virtuel, personne ne le regarde ; un écran qui reçoit des
        # zones est voulu là (configuration du pilote, prise HDMI factice).
        if (fenetre is not None and not e.principal and not e.virtuel
                and _commun(place, fenetre) and not any(_commun(z, place) for z in exportes)):
            problemes.append(Texte("sous la fenêtre de DCS : il restera noir en vol"))
        if place in decales:
            problemes.append(Texte("décalé en hauteur : DCS ouvrirait sa fenêtre à partir de "
                                   "lui"))
        resultat["ecrans"].append({"nom": _nom(e), **_rect(place), "frequence": e.frequence,
                                   "principal": e.principal, "virtuel": e.virtuel,
                                   "problemes": problemes})

    tous = ([e["problemes"] for e in resultat["ecrans"]]
            + [z["problemes"] for z in resultat["zones"]]
            + [resultat["kneeboard"]["problemes"] if resultat["kneeboard"] else []])
    resultat["problemes"] = sum(len(p) for p in tous)
    # Le cadre du schéma : tout ce qui est dessiné, zones hors écran comprises.
    rects = places + exportes + [r for r in (fenetre, kneeboard) if r is not None]
    if rects:
        x0, y0 = min(r[0] for r in rects), min(r[1] for r in rects)
        x1 = max(r[0] + r[2] for r in rects)
        y1 = max(r[1] + r[3] for r in rects)
        resultat["cadre"] = _rect((x0, y0, x1 - x0, y1 - y0))
    else:
        resultat["cadre"] = None
    resultat["raison"] = None if principal is not None else Texte("Écran principal introuvable.")
    return resultat


def lire_dcs(saved_games: Path, appareil: Optional[str]
             ) -> Tuple[Optional[str], Optional[Tuple[int, int]], Dict[str, Rect], Optional[str]]:
    """Ce que DCS a choisi : le nom de la configuration d'écrans, la taille
    de sa fenêtre, les zones qu'elle exporte pour `appareil` (nom DCS ;
    None : celles de tout appareil qu'elle ne nomme pas), et pourquoi il
    n'y en a aucune. Relu, jamais écrit."""
    try:
        choix, largeur, hauteur = options_affichage(saved_games)
    except PasDExport as e:
        return None, None, {}, message(e)
    try:
        texte = fichier_actif(saved_games).read_text(encoding="utf-8", errors="replace")
    except PasDExport as e:
        return choix, (largeur, hauteur), {}, message(e)
    except OSError as e:
        return choix, (largeur, hauteur), {}, Texte("configuration d'écrans illisible "
                                                    "({erreur})", erreur=e)
    trouve = re.search(r"name\s*=\s*_\('([^']*)'\)", texte)
    nom = trouve.group(1) if trouve else choix
    zones = lire_zones(texte, largeur, hauteur, appareil)
    raison = None if zones else Texte("« {nom} » n'exporte aucun écran", nom=nom)
    return nom, (largeur, hauteur), zones, raison


def apercu(ecrans: Sequence, saved_games: Path, appareil: Optional[str] = None,
           libelles: Optional[Dict[str, str]] = None) -> Dict:
    """Pour /api/disposition : la disposition, la configuration d'écrans de
    DCS, et pourquoi rien n'est exporté s'il le faut. Ses textes sont des
    `Texte`, à traduire pour la tablette qui demande."""
    configuration, resolution, zones, raison = lire_dcs(saved_games, appareil)
    resultat = calculer(ecrans, resolution, zones, libelles)
    resultat["configuration"] = configuration
    resultat["raison"] = resultat["raison"] or raison
    return resultat
