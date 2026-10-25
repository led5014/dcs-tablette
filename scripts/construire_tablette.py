"""Construit le zip à télécharger : DCS-Tablette.exe, ses bibliothèques, l'installeur.

    .venv\\Scripts\\python.exe scripts\\construire_tablette.py

Rend dist/DCS-Tablette-<version>.zip, qui contient un dossier DCS-Tablette/ :
    DCS-Tablette.exe     le serveur (double-clic), et `installer` / `desinstaller`
    Installer.bat        scripts dans DCS + écrans
    Desinstaller.bat
    LISEZ-MOI.txt
    _internal/           Python et les bibliothèques
Rien à installer chez celui qui le télécharge, pas même Python.
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

from tablette import VERSION  # noqa: E402

NOM = "DCS-Tablette"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    subprocess.run([sys.executable, "-m", "PyInstaller", str(RACINE / "dcs_tablette.spec"),
                    "--noconfirm", "--distpath", str(RACINE / "dist"),
                    "--workpath", str(RACINE / "build" / "tablette")], check=True)
    dossier = RACINE / "dist" / NOM
    for fichier in (RACINE / "distribution" / "tablette" / "zip").iterdir():
        shutil.copyfile(fichier, dossier / fichier.name)
    archive = RACINE / "dist" / f"{NOM}-{VERSION}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for fichier in sorted(dossier.rglob("*")):
            if fichier.is_file():
                z.write(fichier, Path(NOM) / fichier.relative_to(dossier))
    print(f"\nPrêt : {archive} ({archive.stat().st_size / 1e6:.1f} Mo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
