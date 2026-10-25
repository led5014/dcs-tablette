"""Installe les scripts Lua de la tablette dans DCS.

    .venv\\Scripts\\python.exe scripts\\installer_dcs.py

Copie DCS-Tablette-Export.lua et sa liste blanche par appareil
(DCS-Tablette-Appareils.lua) dans Saved Games/DCS/Scripts, puis ajoute à
Export.lua la ligne qui les charge — une seule fois, après une copie de
l'Export.lua d'origine. La logique est dans src/tablette/installation.py,
partagée avec l'exécutable (`DCS-Tablette.exe installer`, qui règle aussi les
écrans).

À relancer après chaque mise à jour du dépôt ; DCS prend les scripts au
lancement de la mission suivante.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tablette.config import dossier_saved_games  # noqa: E402
from tablette.installation import installer_scripts  # noqa: E402

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for ligne in installer_scripts(dossier_saved_games()):
        print(ligne)
