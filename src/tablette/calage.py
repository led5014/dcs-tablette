"""« Montrer sur mes écrans » : chaque zone exportée posée sur les vrais
écrans, au pixel près, là où DCS la dessinera.

Demande d'un pilote (Discord, 20/11/2026) : « un système de preview grandeur
nature, pour aligner les MFD sur les boutons » — un cadre de MFD physique
(Cougar) posé sur un petit écran, l'export doit tomber pile dedans. Ici,
pas besoin de lancer DCS pour le voir : un cadre par zone, toujours au
premier plan, avec

- son nom et sa place (x, y, largeur × hauteur) ;
- une grille au dixième, une croix au centre ;
- les repères des boutons : là où le module écrit leurs libellés
  (appareils.Ecran.reperes_x / reperes_y, relus dans ses scripts), ou
  également répartis faute de source. Ce sont eux qui doivent tomber en
  face des boutons du cadre physique.

La page Écrans redit les cadres à chaque retouche (flèches, chiffres) : ils
suivent en direct. Sans nouvelles pendant DUREE_S, ils disparaissent seuls ;
ils ne prennent ni la souris ni le clavier.

Tk est livré avec Python : aucune dépendance nouvelle (comme miroir.py).
"""
from __future__ import annotations

import ctypes
import logging
import queue
import threading
import time
from typing import Dict, List, Optional, Sequence

from .langues import Texte

DUREE_S = 120
PERIODE_MS = 50
COULEURS = {"LEFT_MFCD": "#4fc3f7", "RIGHT_MFCD": "#ffb74d", "CENTER_MFCD": "#81c784",
            "TEDAC": "#ce93d8"}

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
LWA_ALPHA = 0x2

journal = logging.getLogger("tablette")


def reperes_d_ecran(ecran) -> Dict[str, List[float]]:
    """Où tombent les boutons d'un écran du profil (appareils.Ecran), en
    fraction de l'image exportée, côté par côté : là où le module écrit
    leurs libellés, sinon également répartis. Un côté sans bouton n'en a
    aucun."""
    par_cote: Dict[str, int] = {}
    for b in ecran.boutons:
        par_cote[b.cote] = max(par_cote.get(b.cote, 0), b.rang + 1)
    resultat: Dict[str, List[float]] = {}
    for cote, n in par_cote.items():
        if cote not in ("haut", "bas", "gauche", "droite"):
            continue
        connus = ecran.reperes_x if cote in ("haut", "bas") else ecran.reperes_y
        if connus and len(connus) == n:
            resultat[cote] = [round(f, 4) for f in connus]
        else:
            resultat[cote] = [round((i + 1) / (n + 1), 4) for i in range(n)]
    return resultat


def geometrie(cadre: Dict) -> str:
    """La géométrie Tk d'un cadre : largeur×hauteur+x+y, x et y négatifs
    compris (écran à gauche ou au-dessus du principal : « +-1920 »)."""
    return f"{cadre['largeur']}x{cadre['hauteur']}+{cadre['x']}+{cadre['y']}"


def cadres_valides(cadres: Sequence[Dict]) -> List[Dict]:
    """Les cadres demandés par la page, bornés : des entiers, une taille
    raisonnable, au plus huit. Le reste est écarté."""
    propres = []
    for c in list(cadres)[:8]:
        try:
            x, y = int(c["x"]), int(c["y"])
            largeur, hauteur = int(c["largeur"]), int(c["hauteur"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (20 <= largeur <= 8192 and 20 <= hauteur <= 8192
                and -16384 <= x <= 16384 and -16384 <= y <= 16384):
            continue
        reperes = c.get("reperes") if isinstance(c.get("reperes"), dict) else {}
        propres.append({
            "x": x, "y": y, "largeur": largeur, "hauteur": hauteur,
            "titre": str(c.get("titre", ""))[:60],
            "couleur": COULEURS.get(str(c.get("zone")), "#e0e0e0"),
            "reperes": {cote: [float(f) for f in reperes.get(cote, [])[:12]
                               if isinstance(f, (int, float)) and 0 <= f <= 1]
                        for cote in ("haut", "bas", "gauche", "droite")},
        })
    return propres


class Calage(threading.Thread):
    """Les cadres sur les vrais écrans, dans leur propre fil Tk."""

    def __init__(self):
        super().__init__(name="tablette-calage", daemon=True)
        self._ordres: "queue.Queue[Optional[List[Dict]]]" = queue.Queue()
        self._demarre = False
        self._verrou = threading.Lock()

    def montrer(self, cadres: Sequence[Dict]) -> int:
        """Pose (ou déplace) les cadres ; rend combien sont montrés."""
        propres = cadres_valides(cadres)
        with self._verrou:
            if not self._demarre:
                self._demarre = True
                self.start()
        self._ordres.put(propres)
        return len(propres)

    def cacher(self) -> None:
        if self._demarre:
            self._ordres.put([])

    def run(self) -> None:
        try:
            from . import capture  # noqa: F401 — pixels physiques (SetProcessDpiAwarenessContext)
        except Exception:                          # noqa: BLE001 — hors Windows
            pass
        import tkinter as tk

        racine = tk.Tk()
        racine.withdraw()
        fenetres: List = []
        etat = {"depuis": time.monotonic()}

        def traversable(fenetre) -> None:
            try:
                user32 = ctypes.windll.user32
                hwnd = int(fenetre.wm_frame(), 16)
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED
                                      | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
                                      | WS_EX_NOACTIVATE)
                user32.SetLayeredWindowAttributes(hwnd, 0, 235, LWA_ALPHA)
            except (AttributeError, OSError, ValueError):
                pass

        def dessiner(toile, c: Dict) -> None:
            l, h, couleur = c["largeur"], c["hauteur"], c["couleur"]
            toile.delete("all")
            for i in range(1, 10):
                toile.create_line(l * i / 10, 0, l * i / 10, h, fill="#2a3238")
                toile.create_line(0, h * i / 10, l, h * i / 10, fill="#2a3238")
            toile.create_line(l / 2 - 20, h / 2, l / 2 + 21, h / 2, fill=couleur)
            toile.create_line(l / 2, h / 2 - 20, l / 2, h / 2 + 21, fill=couleur)
            toile.create_rectangle(1, 1, l - 2, h - 2, outline=couleur, width=3)
            long = max(8, round(min(l, h) * 0.05))
            for cote, fractions in c["reperes"].items():
                for f in fractions:
                    if cote == "haut":
                        toile.create_line(l * f, 0, l * f, long, fill=couleur, width=3)
                    elif cote == "bas":
                        toile.create_line(l * f, h, l * f, h - long, fill=couleur, width=3)
                    elif cote == "gauche":
                        toile.create_line(0, h * f, long, h * f, fill=couleur, width=3)
                    else:
                        toile.create_line(l, h * f, l - long, h * f, fill=couleur, width=3)
            taille = max(9, min(18, round(min(l, h) / 22)))
            toile.create_text(l / 2, h / 2 - 2 * taille, fill=couleur, text=c["titre"],
                              font=("Segoe UI", taille, "bold"))
            toile.create_text(l / 2, h / 2 + 2 * taille, fill="#e8ecee",
                              text=f"x={c['x']}  y={c['y']}  {l}×{h}",
                              font=("Consolas", max(8, taille - 2)))

        def poser(cadres: List[Dict]) -> None:
            while len(fenetres) > len(cadres):
                fenetres.pop().destroy()
            while len(fenetres) < len(cadres):
                f = tk.Toplevel(racine)
                f.overrideredirect(True)
                f.attributes("-topmost", True)
                f.configure(bg="black")
                toile = tk.Canvas(f, bg="#0b0d0e", bd=0, highlightthickness=0)
                toile.pack(fill="both", expand=True)
                f.toile = toile
                fenetres.append(f)
                f.update_idletasks()
                traversable(f)
            for f, c in zip(fenetres, cadres):
                f.geometry(geometrie(c))
                f.toile.configure(width=c["largeur"], height=c["hauteur"])
                # Dans ce fil, Tk n'applique pas de lui-même la géométrie
                # demandée (vu sur le poste de développement : cadres restés
                # en (0, 0), puis sourds aux déplacements) : appliquée ici.
                f.update_idletasks()
                dessiner(f.toile, c)
                f.lift()

        def tic() -> None:
            try:
                dernier = None
                while True:
                    try:
                        dernier = self._ordres.get_nowait()
                    except queue.Empty:
                        break
                if dernier is not None:
                    etat["depuis"] = time.monotonic()
                    poser(dernier)
                elif fenetres and time.monotonic() - etat["depuis"] > DUREE_S:
                    poser([])
            except Exception:                     # noqa: BLE001 — jamais bloquant
                if not etat.get("erreur_dite"):
                    journal.exception(Texte("Calage des écrans : cadres non posés"))
                    etat["erreur_dite"] = True
            racine.after(PERIODE_MS, tic)

        racine.after(PERIODE_MS, tic)
        racine.mainloop()
