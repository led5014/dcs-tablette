"""Le kneeboard de DCS recopié sur l'écran du PC.

Avec un écran virtuel à droite, DCS ouvre le kneeboard au coin bas droit de
TOUTE son image : sur l'écran virtuel, que personne ne regarde. Le déplacer
dans DCS ne tient pas d'une session à l'autre, et changer sa place par
défaut demande de modifier un fichier de DCS, ce qui fait échouer le
contrôle d'intégrité des serveurs multijoueur.

Cette fenêtre recopie donc la page, en direct, au coin bas droit de l'écran
principal — là où DCS l'aurait mise sur un écran unique :

- elle n'apparaît que quand le kneeboard est ouvert dans DCS (RShift+K, K),
  et que la tablette ne l'a pas pris pour elle (AffichageKneeboard) ;
- toujours au premier plan, sans cadre, absente de la barre des tâches ;
- la souris la traverse : elle ne prend jamais un clic destiné à DCS.

Elle ne s'affiche que si le kneeboard tombe hors de l'écran principal :
sur un écran unique, DCS le montre déjà lui-même.

Tk est livré avec Python : aucune dépendance nouvelle.
"""
from __future__ import annotations

import ctypes
import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

from .copie import Rect
from .ecrans_dcs import PasDExport, options_affichage, zone_kneeboard

PERIODE_MS = 100
VALIDITE_PLACE_S = 2.0
SILENCE_TABLETTE_S = 10.0

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
LWA_ALPHA = 0x2

journal = logging.getLogger("tablette")


def hors_ecran_principal(zone_ecran: Rect, principal: Rect) -> bool:
    """La zone (coordonnées écran) est-elle entièrement hors de l'écran principal ?"""
    x, y, l, h = zone_ecran
    px, py, pl, ph = principal
    return x >= px + pl or x + l <= px or y >= py + ph or y + h <= py


def place_miroir(principal: Rect, taille: Tuple[int, int]) -> Rect:
    """Coin bas droit de la zone donnée (l'écran principal moins la barre des
    tâches), à la taille de la page."""
    px, py, pl, ph = principal
    l, h = taille
    return (px + pl - l, py + ph - h, l, h)


class AffichageKneeboard:
    """Où le kneeboard de DCS s'affiche quand on l'ouvre (RShift+K, K) :
    sur le PC, par ce miroir, comme DCS d'habitude ; ou sur la tablette, qui
    bascule alors d'elle-même dessus, et rien sur le PC.

    Choisi sur la tablette, qui le redit à chaque demande d'état. Sans
    nouvelles d'elle depuis 10 s (iPad en veille, Wi-Fi coupé), retour au
    PC : le kneeboard ne doit jamais disparaître des deux côtés à la fois.
    """
    PC, TABLETTE = "pc", "tablette"

    def __init__(self, horloge: Callable[[], float] = time.monotonic):
        self._horloge = horloge
        self._choix = self.PC
        self._vu = -1e9

    def choisir(self, sur: str) -> None:
        if sur in (self.PC, self.TABLETTE):
            self._choix = sur
            self._vu = self._horloge()

    def effectif(self) -> str:
        if self._choix == self.TABLETTE and self._horloge() - self._vu < SILENCE_TABLETTE_S:
            return self.TABLETTE
        return self.PC


class Miroir(threading.Thread):
    def __init__(self, video, saved_games: Path,
                 affichage: Optional[AffichageKneeboard] = None):
        super().__init__(name="tablette-miroir", daemon=True)
        self.video = video
        self.saved_games = saved_games
        self.affichage = affichage
        self._place: Tuple[float, Optional[Rect]] = (-1e9, None)

    def _sur_pc(self) -> bool:
        return self.affichage is None or self.affichage.effectif() == AffichageKneeboard.PC

    def run(self) -> None:
        # Un miroir en panne ne doit pas emporter le serveur de la tablette.
        try:
            self._boucle()
        except Exception:                         # noqa: BLE001
            journal.exception("Miroir du kneeboard arrêté")

    def _ecran_principal_si_necessaire(self) -> Optional[Rect]:
        """La partie utile de l'écran principal (sans la barre des tâches, qui
        passerait par-dessus) si le kneeboard de DCS tombe ailleurs, sinon
        None. Recalculé toutes les 2 s : résolution ou écrans peuvent changer."""
        instant, principal = self._place
        if time.monotonic() - instant < VALIDITE_PLACE_S:
            return principal
        from .capture import moniteurs, origine_dcs, zone_utile_principale
        principal = None
        try:
            _, largeur, hauteur = options_affichage(self.saved_games)
            origine = origine_dcs()
            ecran = next((m[:4] for m in moniteurs() if m[4]), None)
            if origine and ecran:
                x, y, l, h = zone_kneeboard(largeur, hauteur)
                if hors_ecran_principal((origine[0] + x, origine[1] + y, l, h), ecran):
                    principal = zone_utile_principale() or ecran
        except PasDExport:
            pass
        self._place = (time.monotonic(), principal)
        return principal

    def _boucle(self) -> None:
        import tkinter as tk
        from PIL import ImageTk

        from .video import PasDImage

        racine = tk.Tk()
        racine.withdraw()
        racine.overrideredirect(True)
        racine.attributes("-topmost", True)
        racine.configure(bg="black")
        etiquette = tk.Label(racine, bd=0, highlightthickness=0, bg="black")
        etiquette.pack()
        etat = {"visible": False, "empreinte": None, "photo": None, "geometrie": None}

        def traversable() -> None:
            user32 = ctypes.windll.user32
            hwnd = int(racine.wm_frame(), 16)
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED
                                  | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
                                  | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
            user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)

        def cacher() -> None:
            if etat["visible"]:
                racine.withdraw()
                etat["visible"] = False

        def tic() -> None:
            try:
                principal = self._ecran_principal_si_necessaire()
                image = None
                if principal is not None and self._sur_pc():
                    try:
                        image = self.video.kneeboard()
                    except PasDImage:
                        image = None
                if image is None:
                    cacher()
                else:
                    # On ne refait l'image Tk que si la page a changé : le
                    # kneeboard reste immobile l'essentiel du temps.
                    empreinte = image.resize((36, 54)).tobytes()
                    if empreinte != etat["empreinte"]:
                        etat["photo"] = ImageTk.PhotoImage(image)
                        etiquette.configure(image=etat["photo"])
                        etat["empreinte"] = empreinte
                    x, y, l, h = place_miroir(principal, image.size)
                    geometrie = f"{l}x{h}+{x}+{y}"
                    if geometrie != etat["geometrie"]:
                        racine.geometry(geometrie)
                        etat["geometrie"] = geometrie
                    if not etat["visible"]:
                        racine.deiconify()
                        traversable()
                        etat["visible"] = True
            except Exception:                     # noqa: BLE001
                # Une seule trace : répétée dix fois par seconde, elle
                # noierait la fenêtre du serveur.
                if not etat.get("erreur_dite"):
                    journal.exception("Miroir du kneeboard : image ignorée")
                    etat["erreur_dite"] = True
                cacher()
            racine.after(PERIODE_MS, tic)

        racine.after(500, tic)
        racine.mainloop()
