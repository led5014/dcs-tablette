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
"""
from __future__ import annotations

import ast
import operator
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

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

def disposition_essai(largeur: int, hauteur: int) -> Dict[str, Rect]:
    """Écran unique : les écrans en bas, par-dessus la vue.

    Pour essayer sans second écran. Ils masquent une bande du cockpit : c'est
    le prix de l'essai, pas une disposition pour voler.
    """
    c = min(COTE_ESSAI, hauteur // 3, largeur // 4)
    y = hauteur - c
    return {"LEFT_MFCD": (0, y, c, c),
            "CENTER_MFCD": (largeur // 2 - c, y, c, c),
            "TEDAC": (largeur // 2, y, c, c),
            "RIGHT_MFCD": (largeur - c, y, c, c)}


def zone_kneeboard(largeur: int, hauteur: int) -> Rect:
    """Où DCS dessine la page du kneeboard ouvert, pour une image largeur × hauteur."""
    l = min(hauteur // 2, largeur // 2)
    h = round(l * PROPORTION_KNEEBOARD) + MARGE_BAS_KNEEBOARD
    return (largeur - l, hauteur - h, l, h)


def disposition_second_ecran(largeur: int, hauteur: int,
                             largeur2: int, hauteur2: int) -> Dict[str, Rect]:
    """Second écran (largeur2 × hauteur2) à droite du principal, alignés en haut.

    Un carré de quatre : écrans gauche et droit en haut, central (AMPCD) et
    TEDAC dessous. Le coin bas droit reste libre : c'est là que DCS ouvre le
    kneeboard, et il recouvrirait un écran placé dessous.
    """
    _, _, lk, _ = zone_kneeboard(largeur + largeur2, max(hauteur, hauteur2))
    c = min(hauteur2 // 2, (largeur2 - lk - BANDEAU_KNEEBOARD) // 2)
    return {"LEFT_MFCD": (largeur, 0, c, c),
            "RIGHT_MFCD": (largeur + c, 0, c, c),
            "CENTER_MFCD": (largeur, c, c, c),
            "TEDAC": (largeur + c, c, c, c)}


def _chaine_lua(texte: str) -> str:
    """Chaîne Lua entre apostrophes : celle de « l'écran » la fermerait, et
    DCS refuserait tout le fichier."""
    return "'" + texte.replace("\\", "\\\\").replace("'", "\\'") + "'"


def generer(vue: Rect, zones: Dict[str, Rect], description: str) -> str:
    """Texte du fichier MonitorSetup. En ASCII : DCS le lit tel quel."""
    x, y, l, h = vue
    lignes = [
        "-- Genere par DCS Tablette (scripts/configurer_ecrans_dcs.py).",
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
        if nom not in zones:
            continue
        zx, zy, zl, zh = zones[nom]
        lignes += [f"{nom} =", "{", f"     x = {zx};", f"     y = {zy};",
                   f"     width = {zl};", f"     height = {zh};", "}", ""]
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


def lire_zones(texte: str, largeur: int, hauteur: int) -> Dict[str, Rect]:
    """Zones d'export définies dans un fichier MonitorSetup."""
    zones = {}
    for nom in EXPORTS:
        bloc = re.search(rf"^\s*{nom}\s*=\s*\{{(.*?)\}}", texte, re.M | re.S)
        if not bloc:
            continue
        valeurs = {}
        for cle in ("x", "y", "width", "height"):
            m = re.search(rf"\b{cle}\s*=\s*([^;,\n]+)", bloc.group(1))
            if m:
                try:
                    valeurs[cle] = round(_evaluer(m.group(1), largeur, hauteur))
                except (ValueError, SyntaxError, ZeroDivisionError):
                    pass
        if len(valeurs) == 4 and valeurs["width"] > 0 and valeurs["height"] > 0:
            zones[nom] = (valeurs["x"], valeurs["y"], valeurs["width"], valeurs["height"])
    return zones


def _option(texte: str, cle: str) -> Optional[str]:
    m = re.search(rf'\["{cle}"\]\s*=\s*"?([^",\n]+)"?\s*,', texte)
    return m.group(1).strip() if m else None


def options_affichage(saved_games: Path) -> Tuple[str, int, int]:
    """Configuration d'écrans choisie, largeur et hauteur de DCS."""
    try:
        texte = (saved_games / "Config" / "options.lua").read_text(encoding="utf-8",
                                                                   errors="replace")
    except OSError:
        raise PasDExport("Réglages de DCS introuvables (Config/options.lua).")
    choix, largeur, hauteur = (_option(texte, "multiMonitorSetup"),
                               _option(texte, "width"), _option(texte, "height"))
    if not (choix and largeur and hauteur):
        raise PasDExport("Réglages d'affichage de DCS illisibles.")
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
            raise PasDExport(f"options.lua : réglage « {cle} » introuvable.")
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
        raise PasDExport("pas de copie des réglages d'avant la tablette.")
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
    raise PasDExport(f"DCS utilise la configuration d'écrans « {choix} », qui "
                     f"n'exporte pas les écrans. Choisis « {NOM_AFFICHE} » dans "
                     "Options → Système → Moniteurs, puis relance DCS.")


def zones_actives(saved_games: Path) -> Dict[str, Rect]:
    """Zones d'export du fichier MonitorSetup que DCS utilise."""
    _, largeur, hauteur = options_affichage(saved_games)
    texte = fichier_actif(saved_games).read_text(encoding="utf-8", errors="replace")
    return lire_zones(texte, largeur, hauteur)
