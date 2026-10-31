"""Se fait passer pour DCS auprès de la tablette, pour l'essayer sans voler.

Joue le rôle de `DCS-Tablette-Export.lua` : annonce un appareil chaque
seconde (le Hornet par défaut), envoie ses données de vol (un virage à
droite en montée, qui fait vivre les instruments) et affiche chaque ordre
reçu de la tablette.

    .venv\\Scripts\\python.exe scripts\\simuler_dcs_tablette.py
    .venv\\Scripts\\python.exe scripts\\simuler_dcs_tablette.py AH-64D_BLK_II

À ne pas lancer en même temps que DCS : les deux voudraient le même port.
"""
import math
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tablette.appareils import profil_pour  # noqa: E402
from tablette.config import PORT_ETAT, PORT_ORDRES  # noqa: E402


def decrire(profil, appareil: int, commande: int) -> str:
    """« DDI gauche 18 », « kneeboard », ou les numéros bruts."""
    for ecran in profil.ecrans:
        if appareil in ecran.appareils.values():
            for bouton in ecran.boutons:
                if bouton.commande == commande:
                    return f"{ecran.libelle} {bouton.id}"
    if appareil == profil.kneeboard:
        return "kneeboard page"
    return f"appareil {appareil} commande {commande}"


def vol(t: float) -> str:
    """Le message « vol » d'un appareil en virage à droite à 3°/s, en montée,
    dans les unités de DCS (m/s, mètres, radians)."""
    cap = math.radians((3.0 * t) % 360.0)
    valeurs = {
        "vi": 120 + 15 * math.sin(t / 7), "vv": 130, "alt": 1500 + 4 * t, "sol": 1200 + 4 * t,
        "vz": 4 + 2 * math.sin(t / 3), "tang": math.radians(5 + 2 * math.sin(t / 5)),
        "roul": math.radians(25 + 5 * math.sin(t / 4)), "cap": cap, "inc": math.radians(4),
        "mach": 0.4, "bille": 0.15 * math.sin(t / 2), "g": 1.1 + 0.2 * math.sin(t / 3),
        "rpm1": 88, "rpm2": 87, "t1": 620, "t2": 615, "carb": 3200 - t,
        "train": 0, "volets": 0, "aerofreins": 0,
    }
    return "vol " + " ".join(f"{cle}={v:.4f}" for cle, v in valeurs.items())


def main() -> None:
    # Sortie redirigée dans un fichier : Windows l'écrirait en cp1252, sans « → ».
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    nom = sys.argv[1] if len(sys.argv) > 1 else "FA-18C_hornet"
    profil = profil_pour(nom)
    ecoute = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ecoute.bind(("127.0.0.1", PORT_ORDRES))
    ecoute.settimeout(0.05)
    envoi = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"DCS simulé : {nom} ({profil.libelle}), ordres attendus sur le port {PORT_ORDRES}")
    prochaine_annonce = 0.0
    debut = time.monotonic()
    while True:
        if time.monotonic() >= prochaine_annonce:
            envoi.sendto(f"etat {nom}".encode(), ("127.0.0.1", PORT_ETAT))
            prochaine_annonce = time.monotonic() + 1.0
        envoi.sendto(vol(time.monotonic() - debut).encode(), ("127.0.0.1", PORT_ETAT))
        try:
            donnees, _ = ecoute.recvfrom(64)
        except socket.timeout:
            continue
        appareil, commande, valeur = donnees.decode("ascii").split()
        print(f"{decrire(profil, int(appareil), int(commande))} → {valeur}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
