"""Point d'entrée de DCS-Tablette-Ecrans.exe (cible PyInstaller), sans fenêtre.

Lancé à chaque ouverture de Windows par le raccourci du dossier Démarrage :
il démarre `DCS-Tablette.exe ecrans` sans console — ni fenêtre, ni terminal
qui s'ouvre — et s'en va. Tout le travail est dans l'exécutable principal,
qui seul embarque le programme : celui-ci reste minuscule.
"""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    exe = Path(sys.executable).with_name("DCS-Tablette.exe")
    try:
        subprocess.Popen([str(exe), "ecrans"], cwd=str(exe.parent), close_fds=True,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    except OSError:
        sys.exit(1)
