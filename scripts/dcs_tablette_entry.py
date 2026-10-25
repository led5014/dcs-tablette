"""Point d'entrée de DCS-Tablette.exe (cible PyInstaller)."""
import sys
import traceback

from tablette.__main__ import main


def principal() -> int:
    try:
        code = main()
    except KeyboardInterrupt:
        return 0
    except SystemExit as e:         # uvicorn sort ainsi quand le port est pris
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if isinstance(e.code, str):
            print(e.code)
    except Exception:
        traceback.print_exc()
        code = 1
    # Lancé d'un double-clic, la console se fermerait avant qu'on lise l'erreur.
    if code and len(sys.argv) == 1:
        input("\nAppuie sur Entrée pour fermer cette fenêtre.")
    return code


if __name__ == "__main__":
    sys.exit(principal())
