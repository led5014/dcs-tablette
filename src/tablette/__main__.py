"""Lancement : python -m tablette  (ou DCS-Tablette.exe)

    python -m tablette                  le serveur ; l'adresse à ouvrir sur l'iPad s'affiche
    python -m tablette installer        écran virtuel, scripts dans DCS, configuration d'écrans
    python -m tablette desinstaller     l'inverse (l'écran virtuel reste)

Le serveur écoute sur toutes les interfaces : c'est la tablette, sur le
Wi-Fi de la maison, qui doit l'atteindre. Au premier lancement, Windows
demande d'autoriser le programme sur le réseau ; il faut accepter pour le
réseau privé, sinon l'iPad ne verra jamais la page.

`--local` n'écoute que ce PC : pour essayer la page dans un navigateur du PC
sans exposer le serveur, ni déclencher la question du pare-feu.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from . import VERSION
from .config import adresses_locales


class SansConnexionCoupee(logging.Filter):
    """Écarte la trace qu'asyncio écrit sous Windows quand Safari coupe une
    connexion (iPad en veille, onglet fermé). Rien n'est cassé, mais une pile
    d'appels en rouge à chaque mise en veille noierait les vrais messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.exc_info and isinstance(record.exc_info[1], ConnectionResetError))


def servir(local: bool, miroir: bool, mise_a_jour: bool = True) -> int:
    import uvicorn

    from .app import create_app
    from .config import Config
    from .dcs import PontDCS
    from .diagnostic import Diagnostic
    from .installation import dcs_ouvert, demander, installer, premiere_fois
    from .miroir import AffichageKneeboard, Miroir
    from .video import Video

    logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("tablette").setLevel(logging.INFO)
    logging.getLogger("asyncio").addFilter(SansConnexionCoupee())
    cfg = Config()
    print(f"DCS Tablette {VERSION}\n")
    # Une version plus récente ? Proposée avant tout le reste : elle corrige
    # peut-être ce qui suit. Acceptée, elle remplace l'exe : on se ferme.
    # DCS ouvert, on ne demande rien : la question bloquerait le démarrage
    # en plein vol ; le diagnostic de la tablette le signale.
    publiee = None
    if mise_a_jour and getattr(sys, "frozen", False):
        from .mise_a_jour import derniere_version, proposer
        publiee = derniere_version()
        if not dcs_ouvert() and proposer(print, demander, publiee):
            return 0
    # Lancé sans être passé par Installer.bat : on installe d'abord.
    if premiere_fois(cfg.saved_games):
        print("Première utilisation : installation.\n")
        installer(cfg.saved_games)
        print()
    pont = PontDCS(cfg.port_ordres, cfg.port_etat)
    pont.demarrer()
    video = Video(cfg.saved_games)
    affichage = AffichageKneeboard()      # kneeboard de DCS sur le PC ou la tablette
    diagnostic = Diagnostic(cfg.saved_games, pont, video, cfg.port_web, publiee=publiee)
    diagnostic.demarrer()
    if miroir:
        Miroir(video, cfg.saved_games, affichage).start()
    if local:
        print(f"Essai local : http://127.0.0.1:{cfg.port_web}")
    else:
        print("Ouvrir sur l'iPad :")
        for adresse in adresses_locales() or ["<adresse de ce PC>"]:
            print(f"  http://{adresse}:{cfg.port_web}")
    print("Diagnostic : ci-dessus, puis ce qui change ; sur la tablette, toucher la "
          "pastille en haut à gauche.\n")
    try:
        uvicorn.run(create_app(cfg, pont, video, affichage, diagnostic=diagnostic,
                               controle_hote=True),
                    host="127.0.0.1" if local else "0.0.0.0",
                    port=cfg.port_web, log_level="warning")
    finally:
        diagnostic.arreter()
        pont.arreter()
    return 0


def main(arguments: Optional[List[str]] = None) -> int:
    # Sortie redirigée (fichier, autre console) : les flèches et les « × »
    # ne doivent pas faire tomber le programme.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    options = argparse.ArgumentParser(prog="DCS-Tablette", description=f"DCS Tablette {VERSION}")
    options.add_argument("--local", action="store_true",
                         help="n'écouter que ce PC (essais sans iPad)")
    options.add_argument("--sans-miroir", action="store_true",
                         help="ne pas recopier le kneeboard sur l'écran du PC")
    options.add_argument("--sans-mise-a-jour", action="store_true",
                         help="ne pas demander à GitHub s'il existe une version plus récente")
    commandes = options.add_subparsers(dest="commande", metavar="{installer,desinstaller}")
    installer = commandes.add_parser("installer",
                                     help="écran virtuel, scripts dans DCS, écrans de DCS")
    installer.add_argument("--essai", action="store_true",
                           help="sans second écran : les écrans en bas de la vue")
    commandes.add_parser("desinstaller", help="retirer la tablette de DCS")
    # Lancée par `installer`, en administrateur : le pilote de l'écran virtuel.
    pilote = commandes.add_parser("pilote-ecran-virtuel")
    pilote.add_argument("--mode", required=True, help="largeurxhauteur@fréquence")
    pilote.add_argument("--journal", required=True, type=Path)
    choix = options.parse_args(arguments)

    if choix.commande == "pilote-ecran-virtuel":
        from .ecran_virtuel import installer_pilote
        mode = tuple(int(v) for v in choix.mode.replace("@", "x").split("x"))

        def journal(ligne: str) -> None:
            print(ligne)
            with open(choix.journal, "a", encoding="utf-8") as f:
                f.write(ligne + "\n")
        return installer_pilote(mode, journal)
    if choix.commande:
        from . import installation
        from .config import dossier_saved_games
        if choix.commande == "installer":
            return installation.installer(dossier_saved_games(), choix.essai)
        return installation.desinstaller(dossier_saved_games())
    return servir(choix.local, not choix.sans_miroir, not choix.sans_mise_a_jour)


if __name__ == "__main__":
    sys.exit(main())
