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

`--langue en` (ou fr) : la fenêtre en anglais (ou en français) plutôt que
dans la langue de Windows, et pour les fois suivantes ; `--langue auto`
revient à celle de Windows. Accepté partout : `Installer.bat --langue en`.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from . import VERSION, langues
from .config import adresses_locales
from .langues import Texte


class SansConnexionCoupee(logging.Filter):
    """Écarte la trace qu'asyncio écrit sous Windows quand Safari coupe une
    connexion (iPad en veille, onglet fermé). Rien n'est cassé, mais une pile
    d'appels en rouge à chaque mise en veille noierait les vrais messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.exc_info and isinstance(record.exc_info[1], ConnectionResetError))


def servir(local: bool, miroir: bool, mise_a_jour: bool = True, captures: bool = True) -> int:
    import uvicorn

    from .app import create_app
    from .captures import Captures, vue_a_rogner
    from .config import Config, dossier_saved_games
    from .dcs import PontDCS
    from .diagnostic import Diagnostic
    from .installation import (demander, exe_installe, installer, lancer, premiere_fois,
                               tenir_a_jour)
    from .miroir import AffichageKneeboard, Miroir
    from .video import Video

    logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("tablette").setLevel(logging.INFO)
    logging.getLogger("asyncio").addFilter(SansConnexionCoupee())
    cfg = Config()
    fige = getattr(sys, "frozen", False)
    print(f"DCS Tablette {VERSION}\n")
    # Lancé depuis le dossier extrait du zip alors qu'il est installé :
    # c'est l'installé qui démarre, celui que les mises à jour tiennent à jour.
    installe = exe_installe() if fige else None
    if installe:
        print(Texte("DCS Tablette est installé dans {dossier} : c'est lui qui démarre.",
                    dossier=installe.parent))
        lancer(installe, sys.argv[1:])
        return 0
    # Une version plus récente ? Installée avant tout le reste, sans rien
    # demander : elle corrige peut-être ce qui suit. Elle remplace l'exe :
    # on se ferme, le script de mise à jour relance la nouvelle.
    publiee = None
    if mise_a_jour and fige:
        from .mise_a_jour import appliquer, derniere_version
        publiee = derniere_version()
        if appliquer(print, publiee):
            return 0
    # Lancé sans être passé par Installer.bat : on installe d'abord.
    if premiere_fois(cfg.saved_games):
        print(Texte("Première utilisation : installation.") + "\n")
        installer(cfg.saved_games)
        print()
        cfg.saved_games = dossier_saved_games()      # DCS ou DCS.openbeta, au choix du pilote
        installe = exe_installe() if fige else None
        if installe:
            # Copié à sa place : c'est lui qui sert. Cette fenêtre-ci attend
            # qu'on ait lu ce que l'installation a dit, comme Installer.bat.
            lancer(installe, sys.argv[1:])
            demander(Texte("DCS Tablette démarre dans sa propre fenêtre. Appuie sur Entrée "
                           "pour fermer celle-ci. "))
            return 0
    if fige:
        for ligne in tenir_a_jour(Path(sys.executable)):
            print(ligne)
    pont = PontDCS(cfg.port_ordres, cfg.port_etat)
    pont.demarrer()
    video = Video(cfg.saved_games, appareil=pont.dernier_appareil)
    affichage = AffichageKneeboard()      # kneeboard de DCS sur le PC ou la tablette
    diagnostic = Diagnostic(cfg.saved_games, pont, video, cfg.port_web, publiee=publiee)
    diagnostic.demarrer()
    if miroir:
        Miroir(video, cfg.saved_games, affichage).start()
    if captures:
        Captures(cfg.saved_games).start()
    if vue_a_rogner(cfg.saved_games):
        # La fenêtre de DCS couvre aussi l'écran virtuel : partagée telle
        # quelle, elle montre les deux. Les captures, elles, sont recadrées.
        print(Texte("Stream (Discord, OBS) : partager l'écran principal, pas la fenêtre de "
                    "DCS, qui comprend l'écran virtuel.")
              + (" " + Texte("Les captures sont recadrées d'elles-mêmes.") if captures else "")
              + "\n")
    if local:
        print(Texte("Essai local : {adresse}", adresse=f"http://127.0.0.1:{cfg.port_web}"))
    else:
        print(Texte("Ouvrir sur l'iPad :"))
        for adresse in adresses_locales() or [Texte("<adresse de ce PC>")]:
            print(f"  http://{adresse}:{cfg.port_web}")
    print(Texte("Diagnostic : ci-dessus, puis ce qui change ; sur la tablette, toucher la "
                "pastille en haut à gauche.") + "\n")
    try:
        uvicorn.run(create_app(cfg, pont, video, affichage, diagnostic=diagnostic,
                               controle_hote=True),
                    host="127.0.0.1" if local else "0.0.0.0",
                    port=cfg.port_web, log_level="warning")
    finally:
        diagnostic.arreter()
        pont.arreter()
    return 0


def regler_langue(arguments: List[str]) -> List[str]:
    """`--langue fr|en|auto`, où qu'il soit (Installer.bat le passe après
    `installer`) : la langue de la fenêtre, avant tout affichage et avant
    d'importer le reste. Retenue pour les fois suivantes, sauf par le pilote
    de l'écran virtuel, lancé en administrateur avec la langue de la fenêtre
    qui l'a lancé. Rend les autres arguments."""
    lecteur = argparse.ArgumentParser(add_help=False)
    lecteur.add_argument("--langue", choices=("fr", "en", "auto"))
    choix, reste = lecteur.parse_known_args(arguments)
    if choix.langue and "pilote-ecran-virtuel" not in reste:
        try:
            langues.retenir(choix.langue)
        except OSError:
            pass                        # pour cette fois seulement
    langues.regler_pc(choix.langue if choix.langue in langues.LANGUES else langues.du_pc())
    return reste


def main(arguments: Optional[List[str]] = None) -> int:
    # Sortie redirigée (fichier, autre console) : les flèches et les « × »
    # ne doivent pas faire tomber le programme.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    arguments = regler_langue(sys.argv[1:] if arguments is None else arguments)
    options = argparse.ArgumentParser(prog="DCS-Tablette", description=f"DCS Tablette {VERSION}")
    options.add_argument("--local", action="store_true",
                         help=Texte("n'écouter que ce PC (essais sans iPad)"))
    options.add_argument("--sans-miroir", action="store_true",
                         help=Texte("ne pas recopier le kneeboard sur l'écran du PC"))
    options.add_argument("--sans-mise-a-jour", action="store_true",
                         help=Texte("ne pas demander à GitHub s'il existe une version plus "
                                    "récente"))
    options.add_argument("--captures-entieres", action="store_true",
                         help=Texte("ne pas recadrer les captures de DCS sur l'écran principal"))
    # Lue avant (regler_langue) : ici pour l'aide seulement.
    options.add_argument("--langue", choices=("fr", "en", "auto"),
                         help=Texte("langue de la fenêtre, retenue : fr, en, ou auto (celle "
                                    "de Windows)"))
    commandes = options.add_subparsers(dest="commande",
                                       metavar="{installer,desinstaller,ecrans}")
    installer = commandes.add_parser("installer",
                                     help=Texte("écran virtuel, scripts dans DCS, écrans de DCS"))
    installer.add_argument("--essai", action="store_true",
                           help=Texte("sans second écran : les écrans en bas de la vue"))
    desinstaller = commandes.add_parser("desinstaller",
                                        help=Texte("retirer la tablette de DCS"))
    desinstaller.add_argument("--attendre", action="store_true",
                              help=Texte("attendre Entrée avant de fermer la fenêtre"))
    commandes.add_parser("ecrans", help=Texte("remettre l'écran virtuel et les réglages de DCS "
                                              "en place (fait à chaque ouverture de Windows)"))
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
            return installation.installer(dossier_saved_games(), choix.essai, demarrer=True)
        if choix.commande == "ecrans":
            from .diagnostic import remettre_au_demarrage
            return remettre_au_demarrage(dossier_saved_games(), installation.journal_ecrans())
        return installation.desinstaller(dossier_saved_games(), attendre=choix.attendre)
    return servir(choix.local, not choix.sans_miroir, not choix.sans_mise_a_jour,
                  not choix.captures_entieres)


if __name__ == "__main__":
    sys.exit(main())
