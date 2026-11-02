"""Où DCS dessine les écrans exportés : on l'écrit, puis on le relit.

DCS place un écran du cockpit hors du cockpit quand le fichier MonitorSetup
choisi dans Options → Système → Moniteurs lui donne une zone : LEFT_MFCD,
RIGHT_MFCD, CENTER_MFCD, TEDAC. Les coordonnées partent du coin haut-gauche
de la fenêtre de DCS.

Ce module :
- ÉCRIT le fichier « Tablette DCS » (deux dispositions : essai sur l'écran
  unique, ou second écran à droite du principal) ;
- RELIT le fichier réellement choisi dans DCS, d'après options.lua, pour
  capturer exactement là où DCS dessine. Un fichier retouché à la main reste
  donc suivi, et un fichier livré avec DCS (1 Screen…) est reconnu comme
  n'exportant rien plutôt que capturé au hasard.

Les zones sont carrées, sauf pour un appareil dont les écrans ne le sont pas
(Kiowa, 4:3) : dans un carré, DCS les étire et en coupe le haut. Le fichier
leur donne leur forme dans `reconfigure_for_unit`, que DCS appelle en
entrant dans chaque appareil (Config/MonitorSetup/3Cameras.lua, livré avec
DCS, l'explique) ; la relecture rejoue cette fonction pour l'appareil piloté.
"""
from __future__ import annotations

import ast
import operator
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .langues import Texte

Rect = Tuple[int, int, int, int]       # x, y, largeur, hauteur

NOM_FICHIER = "tablette.lua"
NOM_AFFICHE = "Tablette DCS"
# Une seule configuration pour tous les appareils : chaque module ne dessine
# que les zones qu'il connaît (le Hornet ignore TEDAC, l'A-10C CENTER_MFCD).
# Ce sont celles de appareils.viewports() ; un test vérifie qu'elles y sont.
EXPORTS = ("LEFT_MFCD", "RIGHT_MFCD", "CENTER_MFCD", "TEDAC")

# Taille des écrans en mode essai : assez grands pour être lisibles sur l'iPad,
# assez petits pour laisser voir le cockpit sur l'écran unique.
COTE_ESSAI = 480

# Le kneeboard de DCS ne passe pas par les zones d'export : DCS le place lui-
# même (ViewportHandling.lua, update_screenspace_diplacement), collé en bas à
# droite de TOUTE l'image qu'il dessine, large de la moitié de sa hauteur.
# Mesuré le 25/10/2026 en 5120 × 1440 : page 720 × 1080 (2:3) plus 4 px de
# marge basse, et un bandeau de 32 px à sa gauche (flèches, marque-pages).
PROPORTION_KNEEBOARD = 1.5
MARGE_BAS_KNEEBOARD = 4
BANDEAU_KNEEBOARD = 32


class PasDExport(Exception):
    """Les écrans ne sont pas exportés, avec la raison à montrer au pilote."""


# --------------------------------------------------------------- écriture

def _grille(bloc: Rect, forme: Dict[str, float]) -> Dict[str, Rect]:
    """Les écrans de `forme` (zone → largeur / hauteur) rangés en grille dans
    `bloc`, chacun le plus grand possible à sa forme, au milieu de sa case.
    Parmi une colonne, deux… on garde la grille qui donne au plus petit la
    plus grande surface : les deux écrans 4:3 du Kiowa, l'un sous l'autre,
    sont plus grands que dans leurs carrés."""
    bx, by, bl, bh = bloc
    noms = [nom for nom in EXPORTS if nom in forme]

    def taille(cl: int, ch: int, aspect: float) -> Tuple[int, int]:
        l = min(cl, int(ch * aspect))
        return l, min(ch, round(l / aspect))

    meilleure = None
    for colonnes in range(1, len(noms) + 1):
        cl, ch = bl // colonnes, bh // -(-len(noms) // colonnes)
        surface = min(l * h for l, h in (taille(cl, ch, forme[nom]) for nom in noms))
        if meilleure is None or surface > meilleure[0]:
            meilleure = (surface, colonnes, cl, ch)
    _, colonnes, cl, ch = meilleure
    zones = {}
    for i, nom in enumerate(noms):
        l, h = taille(cl, ch, forme[nom])
        zones[nom] = (bx + (i % colonnes) * cl + (cl - l) // 2,
                      by + (i // colonnes) * ch + (ch - h) // 2, l, h)
    return zones


def disposition_essai(largeur: int, hauteur: int,
                      forme: Optional[Dict[str, float]] = None) -> Dict[str, Rect]:
    """Écran unique : les écrans en bas, par-dessus la vue.

    Pour essayer sans second écran. Ils masquent une bande du cockpit : c'est
    le prix de l'essai, pas une disposition pour voler. `forme` : les écrans
    d'un appareil qui ne sont pas carrés (zone → largeur / hauteur), chacun
    dans son carré.
    """
    c = min(COTE_ESSAI, hauteur // 3, largeur // 4)
    y = hauteur - c
    zones = {"LEFT_MFCD": (0, y, c, c),
             "CENTER_MFCD": (largeur // 2 - c, y, c, c),
             "TEDAC": (largeur // 2, y, c, c),
             "RIGHT_MFCD": (largeur - c, y, c, c)}
    if forme:
        return {nom: _grille(zones[nom], {nom: aspect})[nom] for nom, aspect in forme.items()
                if nom in zones}
    return zones


def zone_kneeboard(largeur: int, hauteur: int) -> Rect:
    """Où DCS dessine la page du kneeboard ouvert, pour une image largeur × hauteur."""
    l = min(hauteur // 2, largeur // 2)
    h = round(l * PROPORTION_KNEEBOARD) + MARGE_BAS_KNEEBOARD
    return (largeur - l, hauteur - h, l, h)


def disposition(support: Rect, fenetre: Tuple[int, int],
                forme: Optional[Dict[str, float]] = None) -> Dict[str, Rect]:
    """Les écrans exportés sur l'écran `support` (en coordonnées de la
    fenêtre de DCS, de taille `fenetre`), qu'il soit à droite du principal
    ou dessous.

    Un carré de quatre au coin haut gauche du support : écrans gauche et
    droit en haut, central (AMPCD) et TEDAC dessous, aussi grands que
    possible sans passer sous le kneeboard, que DCS colle en bas à droite de
    TOUTE sa fenêtre (ViewportHandling.lua) et qui les recouvrirait. Vide si
    le support est trop petit. `forme` : les écrans d'un appareil qui ne
    sont pas carrés (zone → largeur / hauteur), rangés dans le même carré.
    """
    sx, sy, sl, sh = support
    kx, ky, _, _ = zone_kneeboard(*fenetre)
    c = min(sl // 2, sh // 2,
            max((kx - BANDEAU_KNEEBOARD - sx) // 2, (ky - sy) // 2))
    if c < 100:
        return {}
    if forme:
        return _grille((sx, sy, 2 * c, 2 * c), forme)
    return {"LEFT_MFCD": (sx, sy, c, c),
            "RIGHT_MFCD": (sx + c, sy, c, c),
            "CENTER_MFCD": (sx, sy + c, c, c),
            "TEDAC": (sx + c, sy + c, c, c)}


def disposition_second_ecran(largeur: int, hauteur: int, largeur2: int, hauteur2: int,
                             forme: Optional[Dict[str, float]] = None) -> Dict[str, Rect]:
    """Second écran (largeur2 × hauteur2) à droite du principal, alignés en haut."""
    return disposition((largeur, 0, largeur2, hauteur2),
                       (largeur + largeur2, max(hauteur, hauteur2)), forme)


def _chaine_lua(texte: str) -> str:
    """Chaîne Lua entre apostrophes : celle de « l'écran » la fermerait, et
    DCS refuserait tout le fichier."""
    return "'" + texte.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _bloc(nom: str, zone: Optional[Rect], retrait: str = "") -> List[str]:
    if zone is None:
        return [f"{retrait}{nom} = nil"]
    zx, zy, zl, zh = zone
    return [f"{retrait}{ligne}" for ligne in (
        f"{nom} =", "{", f"     x = {zx};", f"     y = {zy};",
        f"     width = {zl};", f"     height = {zh};", "}")]


def _par_appareil(zones: Dict[str, Rect], par_appareil: Dict[str, Dict[str, Rect]]) -> List[str]:
    """`reconfigure_for_unit` : les zones des appareils de `par_appareil`
    (nom DCS → zones ; une zone absente n'est pas dessinée), celles de
    `zones` pour tous les autres. Les noms aux mêmes zones partagent leur
    branche."""
    branches: List[Tuple[List[str], Dict[str, Rect]]] = []
    for nom, siennes in par_appareil.items():
        meme = next((b for b in branches if b[1] == siennes), None)
        if meme:
            meme[0].append(nom)
        else:
            branches.append(([nom], siennes))
    lignes = [
        "-- Ecrans qui ne sont pas carres : DCS appelle cette fonction en entrant",
        "-- dans chaque appareil (voir Config/MonitorSetup/3Cameras.lua, livre avec DCS).",
        "function reconfigure_for_unit(unit_type)",
    ]
    for i, (noms, siennes) in enumerate(branches):
        condition = " or ".join(f'unit_type == "{nom}"' for nom in noms)
        lignes.append(f"     {'if' if i == 0 else 'elseif'} {condition} then")
        for nom in EXPORTS:
            if nom in zones or nom in siennes:
                lignes += _bloc(nom, siennes.get(nom), " " * 10)
    lignes.append("     else")
    for nom in EXPORTS:
        if nom in zones:
            lignes += _bloc(nom, zones[nom], " " * 10)
    return lignes + ["     end", "end", ""]


def generer(vue: Rect, zones: Dict[str, Rect], description: str,
            par_appareil: Optional[Dict[str, Dict[str, Rect]]] = None) -> str:
    """Texte du fichier MonitorSetup. En ASCII : DCS le lit tel quel.
    `par_appareil` : nom DCS → zones, pour les appareils dont les écrans ne
    sont pas carrés (voir `_par_appareil`)."""
    x, y, l, h = vue
    lignes = [
        "-- Genere par DCS Tablette (Installer.bat, ou sa console de diagnostic).",
        "-- Le serveur de la tablette relit ce fichier pour capturer les ecrans",
        "-- exportes : on peut le retoucher a la main, il suivra.",
        "_  = function(p) return p; end;",
        f"name = _({_chaine_lua(NOM_AFFICHE)});",
        f"Description = {_chaine_lua(description)}",
        "Viewports =",
        "{",
        "     Center =",
        "     {",
        f"          x = {x};",
        f"          y = {y};",
        f"          width = {l};",
        f"          height = {h};",
        "          viewDx = 0;",
        "          viewDy = 0;",
        f"          aspect = {l / h:.10g};",
        "     }",
        "}",
        "",
    ]
    for nom in EXPORTS:
        if nom in zones:
            lignes += _bloc(nom, zones[nom]) + [""]
    if par_appareil:
        lignes += _par_appareil(zones, par_appareil)
    lignes += ["UIMainView = Viewports.Center", "GU_MAIN_VIEWPORT = Viewports.Center", ""]
    return "\n".join(lignes)


# --------------------------------------------------------------- relecture

_OPERATEURS = {ast.Add: operator.add, ast.Sub: operator.sub,
               ast.Mult: operator.mul, ast.Div: operator.truediv}


def _evaluer(expression: str, largeur: int, hauteur: int) -> float:
    """Arithmétique des fichiers MonitorSetup (`screen.width / 3`…), sans
    jamais exécuter autre chose que des nombres et quatre opérations."""
    texte = (expression.replace("screen.width", str(largeur))
             .replace("screen.height", str(hauteur))
             .replace("screen.aspect", repr(largeur / hauteur)))

    def calculer(noeud):
        if isinstance(noeud, ast.Expression):
            return calculer(noeud.body)
        if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)):
            return noeud.value
        if isinstance(noeud, ast.BinOp) and type(noeud.op) in _OPERATEURS:
            return _OPERATEURS[type(noeud.op)](calculer(noeud.left), calculer(noeud.right))
        if isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, ast.USub):
            return -calculer(noeud.operand)
        raise ValueError(f"expression non comprise : {expression}")

    return calculer(ast.parse(texte.strip(), mode="eval"))


def _rect(corps: str, largeur: int, hauteur: int) -> Optional[Rect]:
    """Le rectangle d'une table { x = …; y = …; width = …; height = … }."""
    valeurs = {}
    for cle in ("x", "y", "width", "height"):
        m = re.search(rf"\b{cle}\s*=\s*([^;,\n}}]+)", corps)
        if m:
            try:
                valeurs[cle] = round(_evaluer(m.group(1), largeur, hauteur))
            except (ValueError, SyntaxError, ZeroDivisionError):
                pass
    if len(valeurs) == 4 and valeurs["width"] > 0 and valeurs["height"] > 0:
        return valeurs["x"], valeurs["y"], valeurs["width"], valeurs["height"]
    return None


def _lire_bloc(texte: str, nom: str, largeur: int, hauteur: int) -> Optional[Rect]:
    bloc = re.search(rf"^\s*{nom}\s*=\s*\{{(.*?)\}}", texte, re.M | re.S)
    return _rect(bloc.group(1), largeur, hauteur) if bloc else None


# Commentaires (longs d'abord), chaînes, mots, opérateurs : de quoi suivre le
# fil d'un fichier MonitorSetup sans jamais l'exécuter.
_JETONS = re.compile(r"--\[(=*)\[.*?\]\1\]|--[^\n]*|\[(=*)\[.*?\]\2\]"
                     r"|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|\w+|==|~=|\S", re.S)


def _rejouer(jetons: List[Tuple[str, int, int]], texte: str, largeur: int, hauteur: int,
             appareil: str, fonction: bool, zones: Dict[str, Optional[Rect]]) -> None:
    """Les affectations des zones d'export, dans `zones`, comme DCS les fait :
    hors de toute fonction (`fonction` faux), ou dans `reconfigure_for_unit`
    appelée pour `appareil`. Comprend if / elseif / else, `return`, et des
    conditions `unit_type == "…"` liées par `or` ; toute autre condition est
    tenue pour fausse, et les boucles ne sont pas parcourues."""
    pile: List[Dict] = [{"actif": not fonction}]
    accolades = 0

    def actif() -> bool:
        # Dans une fonction, seul compte ce qui est ouvert depuis son début.
        debut = max((k for k, b in enumerate(pile) if "param" in b), default=0)
        return all(b["actif"] for b in pile[debut:])

    def condition(i: int) -> Tuple[bool, int]:
        param = next((b["param"] for b in reversed(pile) if b.get("param")), None)
        termes, terme = [], []
        while i < len(jetons) and jetons[i][0] != "then":
            if jetons[i][0] == "or":
                termes.append(terme)
                terme = []
            elif jetons[i][0] not in ("(", ")"):
                terme.append(jetons[i][0])
            i += 1
        termes.append(terme)
        vrai = False
        for t in termes:
            if t == ["true"]:
                vrai = True
            elif len(t) == 3 and t[1] == "==" and param in (t[0], t[2]):
                autre = t[2] if t[0] == param else t[0]
                vrai |= autre[:1] in "\"'" and autre[1:-1] == appareil
        return vrai, i + 1

    i = 0
    while i < len(jetons):
        j = jetons[i][0]
        suivant = jetons[i + 1][0] if i + 1 < len(jetons) else ""
        if j == "function":
            notre = (suivant == "reconfigure_for_unit" and i + 3 < len(jetons)
                     and jetons[i + 2][0] == "(")
            pile.append({"actif": fonction and notre,
                         "param": jetons[i + 3][0] if notre else None})
            while i < len(jetons) and jetons[i][0] != ")":
                i += 1
        elif j == "if":
            vrai, i = condition(i + 1)
            pile.append({"actif": vrai, "pris": vrai})
            continue
        elif j == "elseif" and "pris" in pile[-1]:
            vrai, i = condition(i + 1)
            pile[-1]["actif"] = vrai and not pile[-1]["pris"]
            pile[-1]["pris"] |= vrai
            continue
        elif j == "else" and "pris" in pile[-1]:
            pile[-1]["actif"] = not pile[-1]["pris"]
        elif j in ("do", "repeat"):
            pile.append({"actif": False})
        elif j in ("end", "until") and len(pile) > 1:
            pile.pop()
        elif j == "return" and actif() and len(pile) > 1:
            # La fonction s'arrête : plus rien de ce qui suit ne compte.
            for b in reversed(pile):
                b["actif"] = False
                if "param" in b:
                    break
        elif j == "{":
            accolades += 1
        elif j == "}":
            accolades -= 1
        elif (j in EXPORTS and suivant == "=" and accolades == 0
              and (i == 0 or jetons[i - 1][0] not in (".", "local"))):
            valeur = jetons[i + 2][0] if i + 2 < len(jetons) else ""
            if valeur == "{":
                debut, profondeur, k = jetons[i + 2][2], 0, i + 2
                while k < len(jetons):
                    profondeur += {"{": 1, "}": -1}.get(jetons[k][0], 0)
                    if profondeur == 0:
                        break
                    k += 1
                fin = jetons[k][1] if k < len(jetons) else len(texte)
                if actif():
                    zones[j] = _rect(texte[debut:fin], largeur, hauteur)
                i = k + 1
                continue
            if actif() and (valeur == "nil" or valeur in EXPORTS):
                zones[j] = zones.get(valeur)
        i += 1


def lire_zones(texte: str, largeur: int, hauteur: int,
               appareil: Optional[str] = None) -> Dict[str, Rect]:
    """Zones d'export définies dans un fichier MonitorSetup, pour `appareil`
    (nom DCS) : DCS lit le fichier, puis appelle `reconfigure_for_unit`
    s'il y en a une. Sans appareil, celles de tout appareil qu'elle ne
    nomme pas."""
    jetons = [(m.group(), m.start(), m.end()) for m in _JETONS.finditer(texte)
              if not m.group().startswith("--")]
    zones: Dict[str, Optional[Rect]] = {}
    for fonction in (False, True):
        _rejouer(jetons, texte, largeur, hauteur, appareil or "", fonction, zones)
    return {nom: zones[nom] for nom in EXPORTS if zones.get(nom)}


def a_leur_forme(texte: str, largeur: int, hauteur: int,
                 formes: Dict[str, Dict[str, float]]) -> bool:
    """Chaque appareil de `formes` (nom DCS → zone → largeur / hauteur) a-t-il
    dans ce fichier ses écrans à leur forme ? Non pour un fichier écrit
    avant qu'il y en ait (tout en carrés, 1.11 et avant)."""
    for appareil, forme in formes.items():
        zones = lire_zones(texte, largeur, hauteur, appareil)
        for nom, aspect in forme.items():
            zone = zones.get(nom)
            if zone is None or abs(zone[2] / zone[3] - aspect) > 0.02 * aspect:
                return False
    return True


def lire_vue(texte: str, largeur: int, hauteur: int) -> Optional[Rect]:
    """La vue principale (Center) d'un fichier MonitorSetup."""
    return _lire_bloc(texte, "Center", largeur, hauteur)


def _option(texte: str, cle: str) -> Optional[str]:
    m = re.search(rf'\["{cle}"\]\s*=\s*"?([^",\n]+)"?\s*,', texte)
    return m.group(1).strip() if m else None


def options_affichage(saved_games: Path) -> Tuple[str, int, int]:
    """Configuration d'écrans choisie, largeur et hauteur de DCS."""
    try:
        texte = (saved_games / "Config" / "options.lua").read_text(encoding="utf-8",
                                                                   errors="replace")
    except OSError:
        raise PasDExport(Texte("Réglages de DCS introuvables (Config/options.lua)."))
    choix, largeur, hauteur = (_option(texte, "multiMonitorSetup"),
                               _option(texte, "width"), _option(texte, "height"))
    if not (choix and largeur and hauteur):
        raise PasDExport(Texte("Réglages d'affichage de DCS illisibles."))
    return choix, int(float(largeur)), int(float(hauteur))


def plein_ecran(saved_games: Path) -> bool:
    """DCS est-il en plein écran ? Exclusif, il ne se capture pas (image noire)."""
    try:
        texte = (saved_games / "Config" / "options.lua").read_text(encoding="utf-8",
                                                                   errors="replace")
    except OSError:
        return False
    return (_option(texte, "fullScreen") or "").lower() == "true"


CLES_AFFICHAGE = ("multiMonitorSetup", "width", "height", "aspect", "fullScreen")


def _valeur_brute(texte: str, cle: str) -> Optional[str]:
    """La valeur telle qu'écrite, guillemets compris : de quoi la remettre."""
    m = re.search(rf'\["{cle}"\]\s*=\s*([^,\n]+),', texte)
    return m.group(1).strip() if m else None


def _remplacer(texte: str, valeurs: Dict[str, str]) -> str:
    for cle, valeur in valeurs.items():
        texte, n = re.subn(rf'(\["{cle}"\]\s*=\s*)[^,\n]+(,)', rf"\g<1>{valeur}\g<2>",
                           texte, count=1)
        if n != 1:
            raise PasDExport(Texte("options.lua : réglage « {cle} » introuvable.", cle=cle))
    return texte


def regler_options(saved_games: Path, largeur: int, hauteur: int) -> Path:
    """Choisit « Tablette DCS » et la résolution dans options.lua, en fenêtré.

    À n'appeler que DCS fermé : il réécrit ce fichier en quittant. Garde une
    copie de l'original à côté — la première seulement : une installation
    relancée ne doit pas recouvrir l'original par un fichier déjà réglé. Rend
    le chemin de la copie.
    """
    chemin = saved_games / "Config" / "options.lua"
    texte = chemin.read_text(encoding="utf-8")
    copie = chemin.with_suffix(".lua.avant-tablette")
    if not copie.exists():
        copie.write_text(texte, encoding="utf-8")
    chemin.write_text(_remplacer(texte, {
        "multiMonitorSetup": f'"{Path(NOM_FICHIER).stem}"', "width": str(largeur),
        "height": str(hauteur), "aspect": f"{largeur / hauteur:.14g}",
        "fullScreen": "false"}), encoding="utf-8")
    return copie


def retablir_options(saved_games: Path) -> Path:
    """Remet l'affichage d'avant la tablette (configuration d'écrans,
    résolution, plein écran), d'après la copie gardée par `regler_options`.
    Les autres réglages, changés depuis, restent tels quels. DCS fermé
    seulement. Rend le chemin de la copie."""
    chemin = saved_games / "Config" / "options.lua"
    copie = chemin.with_suffix(".lua.avant-tablette")
    if not copie.exists():
        raise PasDExport(Texte("pas de copie des réglages d'avant la tablette."))
    ancien = copie.read_text(encoding="utf-8", errors="replace")
    valeurs = {cle: _valeur_brute(ancien, cle) for cle in CLES_AFFICHAGE}
    texte = chemin.read_text(encoding="utf-8")
    chemin.write_text(_remplacer(texte, {c: v for c, v in valeurs.items() if v}),
                      encoding="utf-8")
    return copie


def fichier_actif(saved_games: Path) -> Path:
    """Le fichier MonitorSetup que DCS utilise, d'après options.lua."""
    choix, _, _ = options_affichage(saved_games)
    dossier = saved_games / "Config" / "MonitorSetup"
    if dossier.is_dir():
        for f in dossier.glob("*.lua"):
            texte = f.read_text(encoding="utf-8", errors="replace")
            nom = re.search(r"name\s*=\s*_\('([^']*)'\)", texte)
            if choix.lower() in (f.stem.lower(), (nom.group(1).lower() if nom else "")):
                return f
    raise PasDExport(Texte("DCS utilise la configuration d'écrans « {choix} », qui "
                           "n'exporte pas les écrans. Choisis « {nom} » dans "
                           "Options → Système → Moniteurs, puis relance DCS.",
                           choix=choix, nom=NOM_AFFICHE))


def zones_actives(saved_games: Path, appareil: Optional[str] = None) -> Dict[str, Rect]:
    """Zones d'export du fichier MonitorSetup que DCS utilise, telles que
    DCS les donne à `appareil` (nom DCS)."""
    _, largeur, hauteur = options_affichage(saved_games)
    texte = fichier_actif(saved_games).read_text(encoding="utf-8", errors="replace")
    return lire_zones(texte, largeur, hauteur, appareil)
