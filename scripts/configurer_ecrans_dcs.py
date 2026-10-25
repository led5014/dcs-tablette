"""Écrit la configuration d'écrans « Tablette DCS » et la sélectionne dans DCS.

    .venv\\Scripts\\python.exe scripts\\configurer_ecrans_dcs.py --second-ecran
    .venv\\Scripts\\python.exe scripts\\configurer_ecrans_dcs.py            (essai)

Second écran (le bon usage) : la vue reste sur l'écran principal, les écrans
exportés occupent le second — écran virtuel (Virtual Display Driver) ou prise
HDMI factice —, qui doit être à DROITE du principal et aligné en haut.

Essai : un seul écran. Les écrans exportés sont dessinés en bas, par-dessus la
vue. De quoi voir l'image arriver sur l'iPad sans rien installer.

DCS fermé, le script règle aussi options.lua (configuration, résolution,
fenêtré), après en avoir gardé une copie. La logique est dans
src/tablette/installation.py, partagée avec l'exécutable.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tablette.config import dossier_saved_games  # noqa: E402
from tablette.installation import configurer_ecrans  # noqa: E402

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    options = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    options.add_argument("--second-ecran", action="store_true",
                         help="les écrans sur un second écran à droite du principal")
    complet, lignes = configurer_ecrans(dossier_saved_games(),
                                        essai=not options.parse_args().second_ecran)
    print("\n".join(lignes))
    sys.exit(0 if complet else 1)
