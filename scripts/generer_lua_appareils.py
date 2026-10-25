"""Écrit dcs_export/DCS-Tablette-Appareils.lua depuis les profils d'appareil.

    .venv\\Scripts\\python.exe scripts\\generer_lua_appareils.py

À relancer après toute modification de src/tablette/appareils : le script
Lua n'accepte que ce que cette liste blanche autorise, et tests/
test_tablette.py vérifie que le fichier versionné est à jour.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

from tablette.appareils import lua_appareils  # noqa: E402

CIBLE = RACINE / "dcs_export" / "DCS-Tablette-Appareils.lua"

if __name__ == "__main__":
    CIBLE.write_text(lua_appareils(), encoding="ascii", newline="\n")
    print(f"Écrit : {CIBLE}")
