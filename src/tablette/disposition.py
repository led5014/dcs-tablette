"""Où, selon les écrans de Windows : la règle des places, sans rien toucher.

La fenêtre de DCS part du coin haut gauche du principal et s'étend vers la
droite et vers le bas, sauf si un écran à sa gauche est décalé en hauteur :
elle part alors de lui. Essayé avec un pilote le 02/11/2026 : son écran de
gauche un peu plus bas que le principal, la vue de DCS partie dessus ;
débranché, ou remonté bords du haut alignés, DCS revenu sur le principal.
Un tel écran est à aligner (`rangement`), comme un écran au-dessus du
principal. Les écrans exportés vont sur un écran collé à DROITE du
principal (bords du haut alignés) ou DESSOUS (bords de gauche alignés), et
la fenêtre de DCS couvre le principal et cet écran-là. Elle ne doit couvrir
AUCUN autre écran : il resterait noir pendant le vol. Un écran réel à
droite du principal fait donc passer l'écran virtuel dessous.

Module sans Windows : installation, diagnostic, aperçu et écran virtuel
s'en servent tous, les tests aussi.
"""
from __future__ import annotations

from typing import Iterable, List, NamedTuple, Optional, Sequence, Tuple

Rect = Tuple[int, int, int, int]       # x, y, largeur, hauteur

COTES = ("droite", "dessous")


class Moniteur(NamedTuple):
    """Un écran du bureau. `virtuel` : None quand on ne sait pas (relevé
    d'EnumDisplayMonitors, capture.moniteurs). Un tuple : `m[:4]` est sa
    place, `m[4]` dit s'il est le principal."""
    x: int
    y: int
    largeur: int
    hauteur: int
    principal: bool
    virtuel: Optional[bool] = None

    @property
    def rect(self) -> Rect:
        return (self.x, self.y, self.largeur, self.hauteur)


def en_moniteurs(ecrans: Iterable[Sequence]) -> List[Moniteur]:
    """Les écrans en `Moniteur`, qu'ils le soient déjà ou qu'ils viennent en
    tuples (x, y, largeur, hauteur, principal[, virtuel]). Ceux qui le sont
    restent les mêmes objets."""
    return [m if isinstance(m, Moniteur) else Moniteur(*m) for m in ecrans]


def principal_de(ecrans: Iterable[Moniteur]) -> Optional[Moniteur]:
    return next((m for m in ecrans if m.principal), None)


def chevauche(a: Rect, b: Rect) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def supports(ecrans: Sequence[Sequence], physique: bool = True
             ) -> List[Tuple[Moniteur, str, Rect, Tuple[int, int]]]:
    """Les écrans qui peuvent recevoir les écrans du cockpit, du meilleur au
    moins bon : (écran, côté, sa zone dans la fenêtre de DCS, taille de la
    fenêtre). Virtuels d'abord, puis à droite avant dessous. `physique`
    faux : un écran réel n'est jamais pris — on ne le prend que si le
    pilote a dit que personne ne le regarde (prise HDMI factice)."""
    ecrans = en_moniteurs(ecrans)
    principal = principal_de(ecrans)
    if principal is None:
        return []
    px, py, pl, ph = principal.rect
    trouves = []
    for m in ecrans:
        if m.principal or (m.virtuel is False and not physique):
            continue
        zone = (m.x - px, m.y - py, m.largeur, m.hauteur)
        if zone[:2] == (pl, 0):
            cote = "droite"
        elif zone[:2] == (0, ph):
            cote = "dessous"
        else:
            continue
        fenetre = (max(pl, zone[0] + zone[2]), max(ph, zone[1] + zone[3]))
        if any(o is not m and not o.principal
               and chevauche((o.x - px, o.y - py, o.largeur, o.hauteur), (0, 0) + fenetre)
               for o in ecrans):
            continue
        trouves.append((m, cote, zone, fenetre))
    trouves.sort(key=lambda t: (t[0].virtuel is not True, COTES.index(t[1])))
    return trouves


def genants(ecrans: Sequence[Sequence]) -> List[Moniteur]:
    """Les écrans réels décalés en hauteur par rapport au principal : à sa
    gauche sans que les bords du haut soient alignés, ou plus haut que lui.
    DCS ouvrirait sa fenêtre à partir d'eux. Un écran virtuel mal placé n'en
    est pas : `ecran_virtuel.remettre` s'en charge."""
    ecrans = en_moniteurs(ecrans)
    principal = principal_de(ecrans)
    if principal is None:
        return []
    px, py = principal.x, principal.y
    return sorted((m for m in ecrans if not m.principal and m.virtuel is not True
                   and (m.y < py or (m.x < px and m.y != py))), key=lambda m: (m.x, m.y))


def rangement(ecrans: Sequence[Sequence]) -> List[Tuple[Moniteur, int, int]]:
    """Où mettre les écrans `genants` : (écran, x, y) sur le bureau.

    Bord du haut aligné sur celui du principal, du même côté qu'avant : à
    sa gauche, collés à lui ou aux écrans déjà alignés, dans le même ordre ;
    à droite de la fenêtre de DCS pour ceux qui y étaient. Un écran au-dessus
    du principal passe à sa gauche. Seule leur place change, jamais leur
    définition."""
    ecrans = en_moniteurs(ecrans)
    principal = principal_de(ecrans)
    a_ranger = genants(ecrans)
    if principal is None or not a_ranger:
        return []
    px, py, pl = principal.x, principal.y, principal.largeur
    occupes = [m.rect for m in ecrans if not any(m is g for g in a_ranger)]

    def poser(m: Moniteur, x: int) -> None:
        places.append((m, x, py))
        occupes.append((x, py, m.largeur, m.hauteur))

    def gene(x: int, m: Moniteur) -> Optional[Rect]:
        return next((o for o in occupes if chevauche((x, py, m.largeur, m.hauteur), o)), None)

    places: List[Tuple[Moniteur, int, int]] = []
    x = px                # vers la gauche : les écrans de gauche du plus proche au plus loin,
    for m in sorted((m for m in a_ranger if m.x < px + pl),     # puis ceux du dessus
                    key=lambda m: (m.x >= px, -m.x)):
        x -= m.largeur
        while (o := gene(x, m)) is not None:
            x = o[0] - m.largeur
        poser(m, x)
    x = px + pl                                 # vers la droite, après la fenêtre de DCS
    for m in sorted((m for m in a_ranger if m.x >= px + pl), key=lambda m: m.x):
        while (o := gene(x, m)) is not None:
            x = o[0] + o[2]
        poser(m, x)
        x += m.largeur
    return places


def support_ecrans(ecrans: Sequence[Sequence], essai: bool, physique: bool = True
                   ) -> Optional[Tuple[Rect, Tuple[int, int]]]:
    """Où vont les écrans exportés (zone dans la fenêtre de DCS) et la taille
    de cette fenêtre, c'est-à-dire la résolution à régler dans DCS ; None
    sans écran à sa place."""
    principal = principal_de(en_moniteurs(ecrans))
    if principal is None:
        return None
    pl, ph = principal.largeur, principal.hauteur
    if essai:
        return (0, 0, pl, ph), (pl, ph)
    trouves = supports(ecrans, physique)
    return (trouves[0][2], trouves[0][3]) if trouves else None
