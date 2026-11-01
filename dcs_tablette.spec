# PyInstaller — « DCS-Tablette.exe » et ses bibliothèques, dans un dossier
#   .venv\Scripts\python.exe scripts\construire_tablette.py   (exe + zip)
# Un dossier plutôt qu'un exe unique : démarrage immédiat, et moins de faux
# positifs des antivirus, qui se méfient des exe qui se décompressent seuls.
# Les scripts Lua voyagent dans l'exe : `installer` les copie dans DCS
# (voir tablette/installation.py, dossier_lua).
from pathlib import Path

PROJECT = Path(SPECPATH)

a = Analysis(
    [str(PROJECT / "scripts" / "dcs_tablette_entry.py")],
    pathex=[str(PROJECT / "src")],
    binaries=[],
    datas=[
        (str(PROJECT / "src" / "tablette" / "web"), "tablette/web"),
        (str(PROJECT / "dcs_export" / "DCS-Tablette-Export.lua"), "dcs_export"),
        (str(PROJECT / "dcs_export" / "DCS-Tablette-Appareils.lua"), "dcs_export"),
    ],
    hiddenimports=[
        # uvicorn charge ses implémentations dynamiquement
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # importés à la demande par le lanceur selon la commande
        "tablette.app",
        "tablette.installation",
        "tablette.ecran_virtuel",
        "tablette.diagnostic",
        "tablette.mise_a_jour",
        "tablette.miroir",
    ],
    excludes=[
        "matplotlib", "numpy", "pytest", "PyInstaller", "IPython", "notebook",
        "scipy", "pandas", "dcs_debrief", "copilote",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DCS-Tablette",
    icon=str(PROJECT / "distribution" / "tablette" / "dcs_tablette.ico"),
    console=True,          # la console affiche l'adresse à taper sur la tablette
    debug=False,
    strip=False,
    upx=False,
)

# « DCS-Tablette-Ecrans.exe » : sans console, lancé à l'ouverture de Windows,
# il démarre « DCS-Tablette.exe ecrans » sans fenêtre (installation.py,
# ecrans_au_demarrage). Sa propre analyse, d'un script qui n'importe que
# subprocess : il reste minuscule, et partage _internal avec le principal.
b = Analysis(
    [str(PROJECT / "scripts" / "dcs_tablette_ecrans.py")],
    excludes=["tablette", "tkinter", "unittest", "pydoc", "email", "http", "xml"],
    noarchive=False,
)

exe_ecrans = EXE(
    PYZ(b.pure),
    b.scripts,
    [],
    exclude_binaries=True,
    name="DCS-Tablette-Ecrans",
    icon=str(PROJECT / "distribution" / "tablette" / "dcs_tablette.ico"),
    console=False,
    debug=False,
    strip=False,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    exe_ecrans,
    b.binaries,
    b.datas,
    name="DCS-Tablette",
    strip=False,
    upx=False,
)
