"""Lancement : python -m tablette  (ou DCS-Tablette.exe)

    python -m tablette                  le serveur ; l'adresse à ouvrir sur l'iPad s'affiche
    python -m tablette installer        scripts dans DCS + configuration d'écrans
    python -m tablette desinstaller     l'inverse

Le serveur écoute sur toutes les interfaces : c'est la tablette, sur le
Wi-Fi de la maison, qui doit l'atteindre. Au premier lancement, Windows
demande d'autoriser le programme sur le réseau ; il faut accepter pour le
réseau privé, sinon l'iPad ne verra jamais la page.

`--local` n'écoute que ce PC : pour essayer la page dans un navigateur du PC
sans exposer le serveur, ni déclencher la question du pare-feu.
"""
import argparse
import logging
import socket
import sys
from typing import List, Optional

from . import VERSION


def adresses_locales():
    """Adresses IPv4 de ce PC sur le réseau local, à taper sur l'iPad."""
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return sorted({i[4][0] for i in infos if not i[4][0].startswith("127.")})


class SansConnexionCoupee(logging.Filter):
    """Écarte la trace qu'asyncio écrit sous Windows quand Safari coupe une
    connexion (iPad en veille, onglet fermé). Rien n'est cassé, mais une pile
    d'appels en rouge à chaque mise en veille noierait les vrais messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.exc_info and isinstance(record.exc_info[1], ConnectionResetError))


def servir(local: bool, miroir: bool) -> int:
    import uvicorn

    from .app import create_app
    from .config import Config
    from .dcs import PontDCS
    from .installation import est_installe
    from .miroir import Miroir
    from .video import Video

    logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("tablette").setLevel(logging.INFO)
    logging.getLogger("asyncio").addFilter(SansConnexionCoupee())
    cfg = Config()
    print(f"DCS Tablette {VERSION}")
    if not est_installe(cfg.saved_games):
        print("Attention : DCS ne charge pas encore le script de la tablette. Lancer "
              "Installer.bat\n(ou « python -m tablette installer »), puis relancer la mission.\n")
    pont = PontDCS(cfg.port_ordres, cfg.port_etat)
    pont.demarrer()
    video = Video(cfg.saved_games)
    if miroir:
        Miroir(video, cfg.saved_games).start()
    if local:
        print(f"Essai local : http://127.0.0.1:{cfg.port_web}")
    else:
        print("Ouvrir sur l'iPad :")
        for adresse in adresses_locales() or ["<adresse de ce PC>"]:
            print(f"  http://{adresse}:{cfg.port_web}")
    try:
        uvicorn.run(create_app(cfg, pont, video), host="127.0.0.1" if local else "0.0.0.0",
                    port=cfg.port_web, log_level="warning")
    finally:
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
    commandes = options.add_subparsers(dest="commande", metavar="{installer,desinstaller}")
    installer = commandes.add_parser("installer", help="scripts dans DCS + écrans")
    installer.add_argument("--essai", action="store_true",
                           help="sans second écran : les écrans en bas de la vue")
    commandes.add_parser("desinstaller", help="retirer la tablette de DCS")
    choix = options.parse_args(arguments)

    if choix.commande:
        from . import installation
        from .config import dossier_saved_games
        if choix.commande == "installer":
            return installation.installer(dossier_saved_games(), choix.essai)
        return installation.desinstaller(dossier_saved_games())
    return servir(choix.local, not choix.sans_miroir)


if __name__ == "__main__":
    sys.exit(main())
