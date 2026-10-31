"""API FastAPI de la tablette + service de sa page.

Tout passe par le profil de l'appareil piloté (appareils/) : il est choisi
d'après le nom que DCS annonce, et le dernier connu reste actif quand DCS se
tait — la page ne se vide pas entre deux missions.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

from fastapi import Body, Cookie, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from . import VERSION, appareils, filtres, instruments, planche
from .appareils import Profil
from .config import Config
from .dcs import PontDCS
from .kneeboard import lire_page, lister_carnets, trouver
from .miroir import AffichageKneeboard
from .video import KNEEBOARD, ROGNAGE, PasDImage, Video

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


def hote_permis(hote: str) -> bool:
    """La tablette ouvre la page par l'adresse IP du PC (ou son nom). Un site
    piégé qui ferait pointer SON nom vers le PC (« DNS rebinding ») pour
    appuyer sur les boutons ou déplacer les écrans arrive avec ce nom-là dans
    l'en-tête Host : refusé."""
    nom = hote[1:hote.find("]")] if hote.startswith("[") else hote.rsplit(":", 1)[0]
    try:
        ipaddress.ip_address(nom)
        return True
    except ValueError:
        pc = socket.gethostname().lower()
        return nom.lower() in ("localhost", pc, f"{pc}.local")


def vu_par_la_tablette(description: Dict) -> Dict:
    """Les repères des libellés, en fraction de l'image que la tablette
    montre : celle de DCS rognée de ROGNAGE sur chaque bord (video.py)."""
    for ecran in description["ecrans"]:
        for cle in ("reperes_x", "reperes_y"):
            if ecran.get(cle):
                ecran[cle] = [round((f - ROGNAGE) / (1 - 2 * ROGNAGE), 4) for f in ecran[cle]]
    return description


def create_app(cfg: Optional[Config] = None, pont: Optional[PontDCS] = None,
               video: Optional[Video] = None,
               affichage: Optional[AffichageKneeboard] = None,
               dossier_dcs: Optional[Callable[[], Optional[Path]]] = None,
               diagnostic=None, controle_hote: bool = False) -> FastAPI:
    """`affichage` : partagé avec le miroir du kneeboard sur le PC.
    `dossier_dcs` : où DCS est installé (pages des modules et des cartes).
    `diagnostic` : la console de diagnostic (diagnostic.py), lancée à côté.
    `controle_hote` : refuser les noms d'hôte inconnus (voir `hote_permis`) ;
    le serveur le met, les tests parlent à « testserver »."""
    cfg = cfg or Config()
    pont = pont or PontDCS(cfg.port_ordres, cfg.port_etat)
    video = video or Video(cfg.saved_games)
    affichage = affichage or AffichageKneeboard()
    if dossier_dcs is None:
        from .capture import dossier_dcs    # Windows seulement : chargé à la demande
    app = FastAPI(title="DCS Tablette")

    if controle_hote:
        @app.middleware("http")
        async def filtrer_hote(requete: Request, suite):
            if not hote_permis(requete.headers.get("host", "")):
                return PlainTextResponse("Hôte refusé : ouvrir la page par l'adresse IP du PC.",
                                         status_code=400)
            return await suite(requete)
    memoire = {"profil": appareils.PAR_DEFAUT, "nom": appareils.PAR_DEFAUT.noms_dcs[0],
               "dcs": None, "options": (None, "")}

    def options_dcs() -> str:
        """Config/options.lua, relu seulement quand DCS l'a réécrit : les
        unités de certains cockpits y sont réglées (Profil.imperial)."""
        chemin = cfg.saved_games / "Config" / "options.lua"
        try:
            date = chemin.stat().st_mtime
            if memoire["options"][0] != date:
                memoire["options"] = (date, chemin.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            memoire["options"] = (None, "")
        return memoire["options"][1]

    def instruments_actifs(choix: Optional[str]) -> instruments.Instruments:
        return actif(choix)[0].instruments_selon(options_dcs())

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
    def etat(requete: Request, kneeboard: Optional[str] = None,
             choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Dict:
        """État de DCS et profil actif. `kneeboard` (pc ou tablette) : où la
        tablette veut le kneeboard de DCS ; elle le redit à chaque appel. Sur
        la tablette, on dit en plus s'il est ouvert dans DCS, pour qu'elle
        bascule dessus d'elle-même. `choisi` : profil pris dans le menu de la
        tablette ; `ailleurs` : l'appareil que DCS pilote s'il diffère."""
        if kneeboard:
            affichage.choisir(kneeboard)
        if diagnostic is not None and requete.client:
            diagnostic.tablette_vue(requete.client.host)
        profil, nom = actif(choix)
        dcs_etat = pont.etat()
        sur = affichage.effectif()
        ouvert = (video.kneeboard_ouvert()
                  if sur == AffichageKneeboard.TABLETTE and dcs_etat["connecte"] else None)
        return {"version": VERSION,
                "dcs": dcs_etat, "profil": profil.id, "libelle": profil.libelle,
                "appareil": nom, "choisi": appareils.profil_par_id(choix or "") is not None,
                "ailleurs": pilote_ailleurs(profil),
                "kneeboard": {"sur": sur, "ouvert": ouvert},
                "problemes": diagnostic.etat()["problemes"] if diagnostic else 0}

    @app.get("/api/diagnostic")
    def lire_diagnostic() -> Dict:
        """Le dernier résultat de la console de diagnostic, sans revérifier."""
        if diagnostic is None:
            return {"heure": "", "points": [], "problemes": 0, "journal": []}
        return diagnostic.etat()

    @app.post("/api/diagnostic")
    def verifier_diagnostic(corps: Dict = Body(...)) -> Dict:
        """Bouton « Vérifier » : tout revérifier maintenant, et réessayer ce
        qu'on avait renoncé à réparer tout seul. Corps JSON exigé : une page
        d'un autre site ne peut pas en envoyer sans que le navigateur le
        bloque, alors qu'un POST vide passerait — et ceci déplace des écrans."""
        if diagnostic is None:
            return lire_diagnostic()
        diagnostic.verifier(forcer=True)
        return diagnostic.etat()

    @app.get("/api/profils")
    def profils() -> List[Dict]:
        """Les appareils du menu de la tablette, par ordre alphabétique."""
        return [{"id": p.id, "libelle": p.libelle}
                for p in sorted(appareils.PROFILS, key=lambda p: p.libelle.casefold())]

    @app.get("/api/profil")
    def description_profil(choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Dict:
        return vu_par_la_tablette(actif(choix)[0].description())

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
    def image_ecran(ecran_id: str, lum: int = 0, contraste: int = 0, nettete: int = 0,
                    definition: int = filtres.DEFINITION_NORMALE, filtre: str = "",
                    choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Response:
        """Dernière image de l'écran. La page en redemande une dès qu'elle a
        affiché la précédente : le débit suit ce que l'iPad absorbe, sans
        file d'images en retard. Les autres paramètres : réglages de la
        tablette pour cet écran (filtres.py), bornés. L'en-tête
        X-Taille-Source donne la taille de l'image que DCS dessine."""
        try:
            reglages = filtres.reglages(lum, contraste, nettete, definition, filtre)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        if ecran_id == "kneeboard":
            nom = KNEEBOARD
        else:
            ecran = actif(choix)[0].ecran(ecran_id)
            if ecran is None:
                raise HTTPException(status_code=404, detail="écran inconnu")
            nom = ecran.viewport
        try:
            contenu = video.image(nom, reglages)
        except PasDImage as e:
            raise HTTPException(status_code=503, detail=str(e))
        entetes = {"Cache-Control": "no-store"}
        taille = getattr(video, "tailles", {}).get(nom)
        if taille:
            entetes["X-Taille-Source"] = f"{taille[0]}x{taille[1]}"
        return Response(contenu, media_type="image/jpeg", headers=entetes)

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

    @app.get("/api/instruments")
    def lire_instruments(choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Dict:
        """Les instruments analogiques, pour tout appareil (instruments.py).
        `interdit` : le serveur multijoueur coupe l'export de son appareil."""
        vol, interdit = pont.vol()
        inst = instruments_actifs(choix)
        return {"interdit": interdit, "cle": instruments.cle(inst),
                "instruments": instruments.lecture(vol, inst)}

    @app.get("/api/instruments/cadrans")
    def cadrans_instruments(choix: Optional[str] = Cookie(None, alias=CHOIX)) -> Dict:
        return instruments.cadrans(instruments_actifs(choix))

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

    @app.post("/api/kneeboard/dcs/affichage")
    def affichage_kneeboard_dcs(corps: Optional[Dict] = None) -> Dict:
        """Affiche ou cache le kneeboard dans DCS, comme le coup d'œil (K) :
        en mode tablette, le regarder ici en direct l'ouvre dans DCS, sans
        toucher au clavier. Commun à tous les appareils."""
        ouvert = (corps or {}).get("ouvert")
        if not isinstance(ouvert, bool):
            raise HTTPException(status_code=422, detail="ouvert : true ou false")
        envoye = pont.kneeboard(ouvert)
        journal.info("Kneeboard %s dans DCS%s", "affiché" if ouvert else "caché",
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
