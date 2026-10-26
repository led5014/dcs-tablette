"""API FastAPI de la tablette + service de sa page.

Tout passe par le profil de l'appareil piloté (appareils/) : il est choisi
d'après le nom que DCS annonce, et le dernier connu reste actif quand DCS se
tait — la page ne se vide pas entre deux missions.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

from fastapi import Cookie, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response

from . import appareils, planche
from .appareils import Profil
from .config import Config
from .dcs import PontDCS
from .kneeboard import lire_page, lister_carnets, trouver
from .miroir import AffichageKneeboard
from .video import KNEEBOARD, PasDImage, Video

WEB_DIR = Path(__file__).resolve().parent / "web"

# Chaque appui est écrit dans la fenêtre du serveur : c'est le seul endroit,
# côté PC, où l'on voit que la tablette a bien parlé.
journal = logging.getLogger("tablette")

# Même raison que pour DCS Debrief : servie en local, la page n'a rien à
# gagner au cache, et un app.js périmé face à un index.html à jour casse.
_SANS_CACHE = {"Cache-Control": "no-cache, must-revalidate"}

PAGE_SUIVANTE, PAGE_PRECEDENTE = 3001, 3002     # communes à tous les kneeboards

# Cookie de la page : l'appareil choisi à la main dans son menu (absent :
# automatique). Un cookie plutôt qu'un réglage du serveur : chaque tablette ou
# téléphone garde le sien, et deux appareils ouverts ne se le disputent pas.
CHOIX = "tablette_appareil"


def create_app(cfg: Optional[Config] = None, pont: Optional[PontDCS] = None,
               video: Optional[Video] = None,
               affichage: Optional[AffichageKneeboard] = None,
               dossier_dcs: Optional[Callable[[], Optional[Path]]] = None) -> FastAPI:
    """`affichage` : partagé avec le miroir du kneeboard sur le PC.
    `dossier_dcs` : où DCS est installé (pages des modules et des cartes)."""
    cfg = cfg or Config()
    pont = pont or PontDCS(cfg.port_ordres, cfg.port_etat)
    video = video or Video(cfg.saved_games)
    affichage = affichage or AffichageKneeboard()
    if dossier_dcs is None:
        from .capture import dossier_dcs    # Windows seulement : chargé à la demande
    app = FastAPI(title="DCS Tablette")
    memoire = {"profil": appareils.PAR_DEFAUT, "nom": appareils.PAR_DEFAUT.noms_dcs[0],
               "dcs": None}

    def dcs() -> Optional[Path]:
        """Dossier de DCS, d'après le jeu qui tourne ; le dernier connu sinon."""
        memoire["dcs"] = dossier_dcs() or memoire["dcs"]
        return memoire["dcs"]

    def actif(choix: Optional[str] = None) -> Tuple[Profil, str]:
        """Profil de l'appareil annoncé ; le dernier connu si DCS se tait.
        `choix` : celui que la tablette a choisi à la main, qui l'emporte —
        pour préparer la page avant même de lancer la mission."""
        dcs = pont.etat()
        if dcs["connecte"] and dcs["appareil"]:
            memoire["profil"] = appareils.profil_pour(dcs["appareil"])
            memoire["nom"] = dcs["appareil"]
        force = appareils.profil_par_id(choix) if choix else None
        if force is not None:
            return force, force.noms_dcs[0]
        return memoire["profil"], memoire["nom"]

    def pilote_ailleurs(profil: Profil) -> Optional[str]:
        """L'appareil que DCS pilote, quand ce n'est pas `profil` ; None sinon."""
        dcs = pont.etat()
        if dcs["connecte"] and dcs["appareil"]:
            reel = appareils.profil_pour(dcs["appareil"])
            if reel.id != profil.id:
                return reel.libelle if reel is not appareils.GENERIQUE else dcs["appareil"]
        return None

    def garde_fou(profil: Profil) -> None:
        """Rien ne part vers DCS pour un appareil choisi à la main qui n'est pas
        celui qu'il pilote : le même numéro y désigne autre chose (l'OSB 1 du
        MFD droit du F-16 est l'A/P de l'UFC du Hornet), et la liste blanche du
        script Lua, qui suit l'appareil piloté, le laisserait passer."""
        ailleurs = pilote_ailleurs(profil)
        if ailleurs:
            raise HTTPException(status_code=409, detail=(
                f"Tablette réglée sur {profil.libelle}, DCS pilote {ailleurs} : "
                "boutons coupés"))

    def avec_panneau(nom: str, choix: Optional[str]) -> Profil:
        profil, _ = actif(choix)
        if nom not in profil.panneaux:
            raise HTTPException(status_code=404, detail=f"pas de {nom} sur {profil.libelle}")
        return profil

    @app.get("/api/etat")
    def etat(kneeboard: Optional[str] = None,
             choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Dict:
        """État de DCS et profil actif. `kneeboard` (pc ou tablette) : où la
        tablette veut le kneeboard de DCS ; elle le redit à chaque appel. Sur
        la tablette, on dit en plus s'il est ouvert dans DCS, pour qu'elle
        bascule dessus d'elle-même. `choisi` : profil pris dans le menu de la
        tablette ; `ailleurs` : l'appareil que DCS pilote s'il diffère."""
        if kneeboard:
            affichage.choisir(kneeboard)
        profil, nom = actif(choix)
        dcs_etat = pont.etat()
        sur = affichage.effectif()
        ouvert = (video.kneeboard_ouvert()
                  if sur == AffichageKneeboard.TABLETTE and dcs_etat["connecte"] else None)
        return {"dcs": dcs_etat, "profil": profil.id, "libelle": profil.libelle,
                "appareil": nom, "choisi": appareils.profil_par_id(choix or "") is not None,
                "ailleurs": pilote_ailleurs(profil),
                "kneeboard": {"sur": sur, "ouvert": ouvert}}

    @app.get("/api/profils")
    def profils() -> List[Dict]:
        """Les appareils du menu de la tablette."""
        return [{"id": p.id, "libelle": p.libelle} for p in appareils.PROFILS]

    @app.get("/api/profil")
    def description_profil(choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Dict:
        return actif(choix)[0].description()

    @app.post("/api/bouton")
    def bouton(corps: Optional[Dict] = None,
               choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Dict:
        """Un appui ou un relâchement sur le cadre d'un écran. La page envoie
        les deux : le bouton reste enfoncé dans le cockpit tant que le doigt
        est posé. `siege` choisit l'appareil des modules à deux places."""
        corps = corps or {}
        profil, _ = actif(choix)
        ecran = profil.ecran(str(corps.get("ecran")))
        if ecran is None:
            raise HTTPException(status_code=404, detail="écran inconnu")
        bouton_ = ecran.bouton(str(corps.get("bouton")))
        appareil = ecran.appareil(str(corps.get("siege") or ""))
        if bouton_ is None or appareil is None:
            raise HTTPException(status_code=422, detail="bouton inconnu sur cet écran")
        garde_fou(profil)
        enfonce = bool(corps.get("enfonce"))
        envoye = pont.appuyer(appareil, bouton_.commande, enfonce)
        if not envoye:
            suite = " — envoi impossible"
        elif not pont.etat()["connecte"]:
            suite = " — DCS ne répond pas, ordre perdu"
        else:
            suite = ""
        journal.info("%s %s %s%s", ecran.libelle, bouton_.id,
                     "enfoncé" if enfonce else "relâché", suite)
        return {"envoye": envoye}

    @app.get("/api/video/{ecran_id}")
    def image_ecran(ecran_id: str, choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Response:
        """Dernière image de l'écran. La page en redemande une dès qu'elle a
        affiché la précédente : le débit suit ce que l'iPad absorbe, sans
        file d'images en retard."""
        if ecran_id == "kneeboard":
            nom = KNEEBOARD
        else:
            ecran = actif(choix)[0].ecran(ecran_id)
            if ecran is None:
                raise HTTPException(status_code=404, detail="écran inconnu")
            nom = ecran.viewport
        try:
            contenu = video.image(nom)
        except PasDImage as e:
            raise HTTPException(status_code=503, detail=str(e))
        return Response(contenu, media_type="image/jpeg",
                        headers={"Cache-Control": "no-store"})

    @app.get("/api/planche")
    def lecture_planche(choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Dict:
        """UFC, IFEI, instruments et voyants tels que DCS les montre ; None
        pour ce que DCS n'a pas envoyé depuis quelques secondes."""
        avec_panneau("ufc", choix)
        texte_ufc, texte_ifei = pont.texte(planche.IND_UFC), pont.texte(planche.IND_IFEI)
        args = pont.arguments()
        return {
            "ufc": planche.ufc(planche.lire_indication(texte_ufc)) if texte_ufc else None,
            "ifei": planche.ifei(planche.lire_indication(texte_ifei)) if texte_ifei else None,
            "instruments": planche.instruments(args),
            "voyants": planche.voyants(args),
        }

    @app.get("/api/planche/cadrans")
    def cadrans() -> Dict:
        return planche.cadrans()

    @app.post("/api/ufc")
    def touche_ufc(corps: Optional[Dict] = None,
                   choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Dict:
        """Une touche de l'UFC (appui puis relâchement, comme les écrans), ou
        un cran de molette de canal COMM : {"touche": "COMM1", "sens": ±1}."""
        garde_fou(avec_panneau("ufc", choix))
        corps = corps or {}
        touche = str(corps.get("touche"))
        if touche in planche.MOLETTES_UFC:
            sens = corps.get("sens")
            if sens not in (1, -1):
                raise HTTPException(status_code=422, detail="sens : 1 ou -1")
            envoye = pont.tourner(planche.UFC, planche.MOLETTES_UFC[touche],
                                  sens * planche.CRAN_MOLETTE)
            journal.info("UFC %s %s", touche, "+" if sens == 1 else "−")
            return {"envoye": envoye}
        if touche not in planche.TOUCHES_UFC:
            raise HTTPException(status_code=404, detail="touche inconnue")
        enfonce = bool(corps.get("enfonce"))
        envoye = pont.appuyer(planche.UFC, planche.TOUCHES_UFC[touche], enfonce)
        if enfonce:
            journal.info("UFC %s", touche)
        return {"envoye": envoye}

    @app.post("/api/kneeboard/dcs/page")
    def page_kneeboard_dcs(corps: Optional[Dict] = None,
                           choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Dict:
        """Tourne la page du kneeboard dans DCS, comme les touches [ et ]."""
        sens = (corps or {}).get("sens")
        if sens not in (1, -1):
            raise HTTPException(status_code=422, detail="sens : 1 ou -1")
        profil, _ = actif(choix)
        if profil.kneeboard is None:
            raise HTTPException(status_code=409, detail=f"{profil.libelle} : pages à tourner "
                                                        "dans DCS ([ et ])")
        garde_fou(profil)
        commande = PAGE_SUIVANTE if sens == 1 else PAGE_PRECEDENTE
        envoye = pont.appuyer(profil.kneeboard, commande, True)
        journal.info("Kneeboard page %s%s", "suivante" if sens == 1 else "précédente",
                     "" if envoye else " — envoi impossible")
        return {"envoye": envoye}

    @app.get("/api/kneeboard")
    def kneeboard(choix: Optional[str] = Cookie(None, alias=CHOIX)) -> List[Dict]:
        carnets = lister_carnets(cfg.saved_games, actif(choix)[1], dcs())
        return [{"id": c.id, "titre": c.titre, "pages": len(c.pages),
                 "url": f"/api/kneeboard/{quote(c.id, safe='')}"} for c in carnets]

    @app.get("/api/kneeboard/{carnet_id}/{rang}")
    def page_kneeboard(carnet_id: str, rang: int,
                       choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Response:
        carnet = trouver(lister_carnets(cfg.saved_games, actif(choix)[1], dcs()), carnet_id)
        if carnet is None or not 0 <= rang < len(carnet.pages):
            raise HTTPException(status_code=404, detail="page introuvable")
        try:
            contenu, media = lire_page(carnet.pages[rang])
        except OSError:
            raise HTTPException(status_code=404, detail="page disparue")
        return Response(contenu, media_type=media, headers=_SANS_CACHE)

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html", headers=_SANS_CACHE)

    @app.get("/app.js")
    def app_js():
        return FileResponse(WEB_DIR / "app.js", media_type="application/javascript",
                            headers=_SANS_CACHE)

    @app.get("/style.css")
    def style_css():
        return FileResponse(WEB_DIR / "style.css", media_type="text/css",
                            headers=_SANS_CACHE)

    # Ajoutée à l'écran d'accueil (Android, iPad, iPhone) : nom, icône, et
    # ouverture en plein écran, sans la barre du navigateur.
    @app.get("/manifest.webmanifest")
    def manifeste():
        return JSONResponse({
            "name": "DCS Tablette", "short_name": "DCS Tablette", "start_url": "/",
            "display": "fullscreen", "orientation": "any",
            "background_color": "#0b0d0e", "theme_color": "#0b0d0e",
            "icons": [{"src": f"/icone-{c}.png", "sizes": f"{c}x{c}", "type": "image/png"}
                      for c in (192, 512)],
        }, media_type="application/manifest+json")

    @app.get("/icone-{cote}.png")
    def icone(cote: int):
        if cote not in (180, 192, 512):
            raise HTTPException(404, "pas d'icône à cette taille")
        return FileResponse(WEB_DIR / f"icone-{cote}.png", media_type="image/png")

    return app
