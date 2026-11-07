"""Construit le site de DCS Tablette (GitHub Pages) dans un dossier à publier.

    python site/construire.py --release release.json --sortie _site

`release.json` : la réponse de l'API GitHub pour la dernière version
(`gh api repos/<dépôt>/releases/latest`). Illisible, vide ou sans zip : le
bouton mène à la page des versions, et la ligne de version le dit.

Les pages portent trois marqueurs : {{URL_ZIP}} (le lien du bouton),
{{INFOS}} (version, taille, date) et {{STYLE}} (site/style.css, recopié
dans chaque page : une seule feuille à tenir, aucune requête de plus). Les
icônes viennent de la page de la tablette (src/tablette/web) : copiées ici,
jamais dupliquées dans le dépôt.
"""
import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SITE = RACINE / "site"
ICONES = RACINE / "src" / "tablette" / "web"
VERSIONS = "https://github.com/led5014/dcs-tablette/releases/latest"
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")


def derniere_version(chemin: Path):
    """(version, url du zip, taille en octets, date) ; None sans zip publié."""
    try:
        publiee = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(publiee, dict):
        return None
    version = str(publiee.get("tag_name") or "").lstrip("v")
    zips = [a for a in publiee.get("assets") or [] if str(a.get("name", "")).endswith(".zip")]
    # Le zip que la mise à jour de DCS Tablette attend, sinon le premier.
    zip_ = next((a for a in zips if a.get("name") == f"DCS-Tablette-{version}.zip"),
                zips[0] if zips else None)
    if not version or zip_ is None:
        return None
    try:
        jour = date.fromisoformat(str(publiee.get("published_at", ""))[:10])
    except ValueError:
        jour = None
    return version, zip_["browser_download_url"], int(zip_.get("size") or 0), jour


def infos(version_, anglais: bool) -> str:
    if version_ is None:
        return ("Latest version on GitHub" if anglais
                else "Dernière version sur GitHub")
    version, _, taille, jour = version_
    morceaux = [f"Version {version}"]
    if taille:
        morceaux.append(f"{taille / 1e6:.0f} {'MB' if anglais else 'Mo'}")
    if jour:
        morceaux.append(f"{MONTHS[jour.month - 1]} {jour.day}, {jour.year}" if anglais
                        else f"{jour.day} {MOIS[jour.month - 1]} {jour.year}")
    return " · ".join(morceaux)


def construire(release: Path, sortie: Path) -> None:
    version_ = derniere_version(release)
    url = version_[1] if version_ else VERSIONS
    style = (SITE / "style.css").read_text(encoding="utf-8").rstrip("\n")
    if sortie.exists():
        shutil.rmtree(sortie)
    for page in sorted(SITE.rglob("*.html")):
        relatif = page.relative_to(SITE)
        anglais = relatif.parts[0] == "en"
        texte = (page.read_text(encoding="utf-8")
                 .replace("{{STYLE}}", style)
                 .replace("{{URL_ZIP}}", url)
                 .replace("{{INFOS}}", infos(version_, anglais)))
        if "{{" in texte:
            raise SystemExit(f"marqueur inconnu dans {relatif}")
        cible = sortie / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(texte, encoding="utf-8")
    for cote in (192, 512):
        shutil.copyfile(ICONES / f"icone-{cote}.png", sortie / f"icone-{cote}.png")
    print(f"{sortie} : {infos(version_, False)} -> {url}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    options = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    options.add_argument("--release", type=Path, required=True)
    options.add_argument("--sortie", type=Path, required=True)
    arguments = options.parse_args()
    construire(arguments.release, arguments.sortie)
