"""La console de diagnostic : ce qui manque pour que la tablette marche, et
comment le régler.

Une douzaine de points, de l'installation au vol, vérifiés au lancement de DCS Tablette
puis toutes les 10 secondes. Ce qui se répare sans risque l'est aussitôt, et
c'est dit : scripts d'une ancienne version, écran virtuel déplacé (mise à
jour de Windows ou du pilote graphique), configuration d'écrans qui ne tombe
plus sur les écrans, DCS repassé en plein écran ou sur une autre
configuration — ses réglages DCS fermé seulement : il les réécrit en
quittant. Pour le reste, la marche à suivre.

Affichée dans la fenêtre de DCS Tablette (la liste au lancement, puis ce qui
change) et dans le panneau Diagnostic de la tablette (/api/diagnostic).
Une vérification qui plante devient un point « non vérifié » : la console
ne doit jamais empêcher de voler.

Les points sont faits de `Texte` (langues.py) : la fenêtre du PC les montre
dans la langue du PC, chaque tablette dans la sienne (`langues.dans`).
"""
from __future__ import annotations

import re
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import VERSION
from .config import (NOMS_DCS, PORT_WEB, adresses_locales, dernier_lancement, dossiers_dcs,
                     plus_recent)
from .mise_a_jour import numero
from .appareils import formes
from .ecrans_dcs import (NOM_AFFICHE, NOM_FICHIER, PasDExport, a_leur_forme, fichier_actif,
                         lire_zones, options_affichage, plein_ecran, regler_options)
from .installation import (LIGNE, configuration_existante, configurer_ecrans, dcs_ouvert, genants,
                           dcs_regle, installer_scripts, lire_choix, mode_essai, premiere_fois,
                           scripts_a_jour, support_ecrans)
from .langues import FRANCAIS, Texte, dans, message, pc

OK, REPARE, ATTENTE, A_FAIRE, MANQUE = "ok", "repare", "attente", "a_faire", "manque"
ETIQUETTES = {OK: Texte("OK"), REPARE: Texte("RÉPARÉ"), ATTENTE: Texte("ATTENTE"),
              A_FAIRE: Texte("À FAIRE"), MANQUE: Texte("MANQUE")}
PROBLEMES = (A_FAIRE, MANQUE)

PERIODE_S = 10
PERIODE_RESEAU_S = 60
# Un écran virtuel qu'on n'a pas su remettre : chaque essai fait clignoter
# les écrans, on ne réessaie pas tout seul avant ce délai.
PAUSE_APRES_ECHEC_S = 600
TABLETTE_RECENTE_S = 10
# Ouverture de Windows : l'écran virtuel arrive quelques secondes après la
# session. On l'attend, puis on laisse Windows finir de poser les écrans.
ATTENTE_ECRAN_VIRTUEL_S = 90
POSE_DES_ECRANS_S = 5
IMAGE_RECENTE_S = 15
JOURNAL_MAX = 15
FIN_DU_JOURNAL = 512 * 1024


@dataclass(frozen=True)
class Point:
    titre: str
    etat: str
    detail: str
    solution: Tuple[str, ...] = ()


def lignes_console(points: Sequence[Point]) -> List[str]:
    lignes = []
    for p in points:
        lignes.append(f"  {ETIQUETTES[p.etat].dans(pc()):8} "
                      + Texte("{titre} : {detail}", titre=p.titre, detail=p.detail))
        lignes += [f"           → {s}" for s in p.solution]
    return lignes


def _dans(zone: Tuple[int, int, int, int], ecran: Sequence[int]) -> bool:
    x, y, l, h = zone
    ex, ey, el, eh = ecran[:4]
    return ex <= x and ey <= y and x + l <= ex + el and y + h <= ey + eh


def _fin_du_journal(saved_games: Path) -> Optional[str]:
    """La fin de dcs.log. DCS recommence ce fichier à chaque lancement :
    c'est la session en cours."""
    try:
        with open(saved_games / "Logs" / "dcs.log", "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - FIN_DU_JOURNAL))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return None


def mission_lancee(saved_games: Path) -> Optional[bool]:
    """Une mission a-t-elle été chargée depuis le lancement de DCS ? Avant, le
    script de la tablette ne peut rien dire : DCS ne lit Export.lua qu'au
    début d'une mission. None si dcs.log est illisible.

    Relevé le 01/11/2026 : « Dispatcher (Main): loadMission <fichier> » à
    chaque mission, en solo comme en multijoueur (une piste .trk)."""
    texte = _fin_du_journal(saved_games)
    if texte is None:
        return None
    return re.search(r"\bDispatcher \(\w+\): loadMission\b", texte) is not None


def derniere_ligne_tablette(saved_games: Path) -> Optional[Tuple[bool, str]]:
    """La dernière chose que le script de la tablette a écrite dans dcs.log,
    et si c'était une panne."""
    texte = _fin_du_journal(saved_games)
    if texte is None:
        return None
    for ligne in reversed(texte.splitlines()):
        if "DCS-TABLETTE" in ligne:
            # « 2026-10-29 21:07:12.345 ERROR   DCS-TABLETTE (Main): port pris… »
            avant, apres = ligne.split("DCS-TABLETTE", 1)
            return "ERROR" in avant, apres.split(":", 1)[-1].strip()
    return None


def profils_reseau() -> Optional[List[Tuple[str, str]]]:
    """Réseaux du PC et leur type pour Windows (Public, Private,
    DomainAuthenticated) ; None si on ne peut pas le savoir."""
    try:
        sortie = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-NetConnectionProfile | ForEach-Object { $_.Name + '|' + $_.NetworkCategory }"],
            capture_output=True, text=True, errors="replace", timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    profils = []
    for ligne in sortie.splitlines():
        nom, _, categorie = ligne.strip().rpartition("|")
        if categorie:
            profils.append((nom, categorie))
    return profils


class Diagnostic:
    """Les vérifications, leur dernier résultat, et ce qui a changé.

    Tout ce qui touche Windows ou DCS se remplace (tests) : `ouvert` (DCS
    tourne ?), `ecrans` (moniteurs, virtuels signalés), `virtuel`
    (ecran_virtuel.remettre), `lancement` (heure de lancement de DCS),
    `reseaux` (profils_reseau), `choix` (ce que le pilote a choisi à
    l'installation, installation.lire_choix), `ranger` (ecran_virtuel.ranger,
    appelé seulement avec l'accord du pilote).
    """

    def __init__(self, saved_games: Path, pont=None, video=None, port_web: int = PORT_WEB,
                 ouvert: Callable[[], bool] = dcs_ouvert,
                 ecrans: Optional[Callable[[], list]] = None,
                 virtuel: Optional[Callable[..., Tuple[str, str, List[str]]]] = None,
                 lancement: Optional[Callable[[], Optional[float]]] = None,
                 reseaux: Callable[[], Optional[List[Tuple[str, str]]]] = profils_reseau,
                 choix: Callable[[], Dict] = lire_choix,
                 publiee: Optional[Dict] = None,
                 horloge: Callable[[], float] = time.monotonic,
                 ranger: Optional[Callable[[], Optional[str]]] = None):
        if ecrans is None or virtuel is None or lancement is None:
            from . import capture, ecran_virtuel    # Windows seulement
            ecrans = ecrans or ecran_virtuel.moniteurs
            virtuel = virtuel or ecran_virtuel.remettre
            lancement = lancement or capture.lancement_dcs
        self.saved_games = saved_games
        self.pont, self.video, self.port_web = pont, video, port_web
        self._ouvert, self._ecrans, self._virtuel = ouvert, ecrans, virtuel
        self._lancement, self._reseaux, self._horloge = lancement, reseaux, horloge
        self._choix = choix
        self._ranger = ranger
        self._echec_rangement = -1e9
        self._publiee = publiee          # dernière version sur GitHub, lue au lancement
        self._verrou = threading.Lock()          # une vérification à la fois
        # Le résultat, lu par la page toutes les 750 ms : jamais bloqué par
        # une vérification en cours (PowerShell, tasklist : une seconde).
        self._verrou_etat = threading.Lock()
        self._points: List[Point] = []
        self._heure = ""
        self._journal: List[Dict] = []
        self._tablette: Optional[Tuple[str, float]] = None
        self._reseau: Optional[Tuple[float, Point]] = None
        self._echec_ecran = -1e9
        self._derniers_nouveaux: List[Dict] = []
        self._reveil = threading.Event()
        self._arret = threading.Event()

    # ------------------------------------------------------------ les points

    def _dossier(self) -> Point:
        titre = Texte("Dossier de DCS")
        if not (self.saved_games / "Config" / "options.lua").exists():
            return Point(titre, MANQUE,
                         Texte("pas de réglages de DCS dans {dossier}", dossier=self.saved_games),
                         (Texte("Lancer DCS une fois, jusqu'au menu, le quitter, puis relancer "
                                "DCS Tablette : il finit l'installation tout seul."),))
        # DCS et DCS.openbeta côte à côte : DCS ne se sert que d'un des deux
        # (config.dossier_saved_games). On dit lequel a été pris, et si DCS
        # s'est lancé depuis avec l'autre.
        autres = ([d for d in dossiers_dcs(self.saved_games.parent) if d != self.saved_games]
                  if self.saved_games.name in NOMS_DCS else [])
        autre = plus_recent(autres)
        if autre is None:
            return Point(titre, OK, str(self.saved_games))
        if (dernier_lancement(autre) or 0) > (dernier_lancement(self.saved_games) or 0):
            return Point(titre, A_FAIRE,
                         Texte("{dossier}, mais DCS s'est lancé plus récemment avec {autre}",
                               dossier=self.saved_games, autre=autre.name),
                         (Texte("Relancer Installer.bat : il demande lequel est le dossier de "
                                "votre DCS et y installe la tablette."),))
        return Point(titre, OK, Texte("{dossier} (celui du dernier lancement de DCS ; {autre} "
                                      "existe aussi)", dossier=self.saved_games, autre=autre.name))

    def _scripts(self, lance: bool) -> Point:
        titre = Texte("Scripts dans DCS")
        scripts = self.saved_games / "Scripts"          # DCS ou DCS.openbeta
        if scripts_a_jour(self.saved_games):
            return Point(titre, OK, Texte("à jour, chargés par Export.lua"))
        try:
            installer_scripts(self.saved_games)
        except OSError as e:
            return Point(titre, MANQUE, Texte("copie impossible ({erreur})", erreur=e), (
                Texte("Relancer Installer.bat."),
                Texte("À la main : copier DCS-Tablette-Export.lua et DCS-Tablette-Appareils.lua "
                      "dans {dossier}, et ajouter à la fin d'Export.lua :", dossier=scripts),
                LIGNE))
        if lance:
            return Point(titre, REPARE, Texte("copiés dans {dossier} : relancer la mission pour "
                                              "qu'ils servent", dossier=scripts))
        return Point(titre, REPARE, Texte("copiés dans {dossier} : ils serviront dès la prochaine "
                                          "mission", dossier=scripts))

    def _ecran_virtuel(self, essai: bool, forcer: bool, physique: bool, lance: bool) -> Point:
        titre = Texte("Écran virtuel")
        if essai:
            return Point(titre, OK, Texte("mode essai : écrans du cockpit en bas de la vue"))
        # DCS ouvert, on ne déplace rien : un écran qui s'endort ou une télé
        # qu'on allume en vol ne doit pas faire perdre la tablette. On le dit.
        reparer = not lance and (forcer or self._horloge() - self._echec_ecran
                                 > PAUSE_APRES_ECHEC_S)
        etat, detail, solution = self._virtuel(reparer, physique)
        # Jugé sur le texte français, la référence, quelle que soit la langue.
        if etat == MANQUE and reparer and not dans(detail, FRANCAIS).startswith("aucun"):
            self._echec_ecran = self._horloge()
        return Point(titre, etat, detail, tuple(solution))

    def _windows(self, ecrans: list, lance: bool, forcer: bool, accord: bool) -> Point:
        """Aucun écran réel décalé en hauteur à gauche du principal, ni
        au-dessus : DCS ouvrirait sa fenêtre à partir de lui
        (installation.genants). Alignés tout seuls DCS fermé si le pilote l'a
        accepté à l'installation — comme l'écran virtuel, pas en boucle après
        un échec —, sinon la marche à suivre."""
        titre = Texte("Écrans de Windows")
        a_ranger = genants(ecrans)
        if not a_ranger:
            return Point(titre, OK, Texte("alignés en haut sur l'écran principal"))
        noms = [Texte("votre écran {largeur}×{hauteur}", largeur=m[2], hauteur=m[3])
                for m in a_ranger]
        a_la_main = Texte("Ou Paramètres → Système → Écran : les glisser à gauche de l'écran "
                          "principal, bords du haut alignés, puis relancer DCS.")
        if accord and not lance and (forcer or self._horloge() - self._echec_rangement
                                     > PAUSE_APRES_ECHEC_S):
            if self._ranger is None:
                from .ecran_virtuel import ranger    # Windows seulement
                self._ranger = ranger
            erreur = self._ranger()
            if erreur is None:
                return Point(titre, REPARE, Texte("alignés en haut sur l'écran principal : "
                                                  "{ecrans}", ecrans=noms))
            self._echec_rangement = self._horloge()
            return Point(titre, MANQUE, Texte("{ecrans} pas alignés : {erreur}", ecrans=noms,
                                              erreur=erreur), (a_la_main,))
        return Point(titre, A_FAIRE, Texte(
            "{ecrans} décalés en hauteur par rapport à l'écran principal : DCS ouvre sa fenêtre "
            "à partir d'eux", ecrans=noms), (
            Texte("Quitter DCS : DCS Tablette les aligne tout seul, puis relancer DCS.")
            if accord else
            Texte("Relancer Installer.bat (DCS fermé) : il propose de les aligner sur l'écran "
                  "principal."), a_la_main))

    def _existante(self, nom: str) -> List[Point]:
        """Le pilote a gardé sa configuration d'écrans, qui exporte déjà les
        écrans du cockpit : on ne la remplace pas, on vérifie qu'elle est là."""
        points = [Point(Texte("Écran virtuel"), OK,
                        Texte("pas utilisé : DCS exporte avec « {nom} »", nom=nom))]
        actuelle = configuration_existante(self.saved_games)
        if actuelle and actuelle[0] == nom:
            points.append(Point(Texte("Écrans de DCS"), OK,
                                Texte("« {nom} » (la vôtre) : {nombre} écrans exportés",
                                      nom=nom, nombre=len(actuelle[1]))))
        else:
            points.append(Point(
                Texte("Écrans de DCS"), A_FAIRE,
                Texte("DCS n'est plus sur votre configuration « {nom} »", nom=nom), (
                    Texte("Dans DCS : Options → Système → Moniteurs « {nom} », puis "
                          "relancer DCS.", nom=nom),
                    Texte("Ou relancer Installer.bat pour passer à « {nom} ».",
                          nom=NOM_AFFICHE))))
        if plein_ecran(self.saved_games):
            points.append(Point(Texte("Réglages de DCS"), A_FAIRE,
                                Texte("plein écran : la tablette n'y voit rien"),
                                (Texte("Dans DCS : Options → Système, décocher « Plein "
                                       "écran », puis relancer DCS."),)))
        else:
            points.append(Point(Texte("Réglages de DCS"), OK, Texte("fenêtré")))
        return points

    def _configuration(self, essai: bool, ecrans: list, lance: bool,
                       physique: bool) -> Tuple[Point, Optional[Tuple[int, int]]]:
        titre = Texte("Écrans de DCS")
        support = support_ecrans(ecrans, essai, physique)
        if support is None:
            return self._en_attente(ecrans, lance), None
        ecran, resolution = support
        ou = Texte("en bas de la vue") if essai else Texte("sur le second écran")
        fichier = self.saved_games / "Config" / "MonitorSetup" / NOM_FICHIER
        try:
            texte = fichier.read_text(encoding="utf-8", errors="replace")
        except OSError:
            texte = ""
        zones = lire_zones(texte, *resolution)
        sur_l_ecran = bool(zones) and all(_dans(z, ecran) for z in zones.values())
        # Écrite par une version d'avant les zones par appareil : les écrans
        # du Kiowa y sont carrés, étirés et coupés par DCS. Récrite comme une
        # configuration qui ne tombe plus sur les écrans.
        formees = a_leur_forme(texte, *resolution, formes())
        # Retouchée à la main et toujours sur l'écran : elle reste telle quelle.
        if sur_l_ecran and formees:
            return Point(titre, OK, Texte("« {nom} » : {nombre} écrans {ou}", nom=NOM_AFFICHE,
                                          nombre=len(zones), ou=ou)), resolution
        if lance:
            # Réécrite DCS ouvert, la tablette refuserait toute capture jusqu'au
            # redémarrage de DCS (video.py) : on attend qu'il soit fermé.
            pourquoi = (self._ne_tombe_plus(ecran, ecrans) if not sur_l_ecran else
                        Texte("« {nom} » date d'avant les écrans qui ne sont pas carrés : "
                              "ceux du Kiowa y sont étirés et coupés", nom=NOM_AFFICHE))
            return Point(titre, A_FAIRE, pourquoi, (
                Texte("Quitter DCS : DCS Tablette la récrit tout seul, puis relancer DCS."),)
            ), None
        complet, lignes = configurer_ecrans(self.saved_games, essai, ecrans, lambda: lance,
                                            physique=physique)
        if not complet:
            return Point(titre, MANQUE, lignes[0], tuple(lignes[1:])), resolution
        return Point(titre, REPARE, Texte("« {nom} » écrite à la taille des écrans, "
                                          "écrans du cockpit {ou}", nom=NOM_AFFICHE, ou=ou)
                     ), resolution

    def _sous_dcs(self, ecrans: list, support: Optional[Tuple[int, int, int, int]] = None
                  ) -> Tuple[int, int, list]:
        """La fenêtre de DCS telle que réglée dans options.lua (elle part du
        coin haut gauche du principal), et les écrans réels qu'elle recouvre,
        hors du principal et du `support` des écrans du cockpit."""
        try:
            _, largeur, hauteur = options_affichage(self.saved_games)
        except PasDExport:
            return 0, 0, []
        principal = next((m for m in ecrans if m[4]), None)
        if principal is None:
            return largeur, hauteur, []
        px, py = principal[:2]
        recouverts = []
        for m in ecrans:
            x, y, l, h = m[0] - px, m[1] - py, m[2], m[3]
            if m[4] or (x, y, l, h) == tuple(support or ()) or (len(m) > 5 and m[5]):
                continue
            if x < largeur and 0 < x + l and y < hauteur and 0 < y + h:
                recouverts.append(Texte("votre écran {largeur}×{hauteur}", largeur=l, hauteur=h))
        return largeur, hauteur, recouverts

    def _en_attente(self, ecrans: list, lance: bool) -> Point:
        """Pas d'écran à sa place pour ceux du cockpit. La fenêtre de DCS,
        réglée pour l'ancienne disposition, recouvre parfois alors un écran du
        pilote (photo d'un pilote, 01/11/2026 : écran virtuel repassé en
        1920 × 1080 à gauche, son écran réel à sa place) : c'est à régler."""
        titre = Texte("Écrans de DCS")
        largeur, hauteur, recouverts = self._sous_dcs(ecrans)
        if not recouverts:
            return Point(titre, ATTENTE, Texte("en attente de l'écran virtuel"))
        return Point(titre, A_FAIRE, Texte(
            "en attente de l'écran virtuel, et la fenêtre de DCS ({largeur}×{hauteur}) "
            "recouvre {recouverts}", largeur=largeur, hauteur=hauteur, recouverts=recouverts), (
            Texte("Quitter DCS : DCS Tablette remet l'écran virtuel à sa place et règle DCS, "
                  "puis relancer DCS.") if lance else
            Texte("Remettre d'abord l'écran virtuel (point « Écran virtuel ») : DCS Tablette "
                  "règle ensuite DCS tout seul."),))

    def _ne_tombe_plus(self, support: Tuple[int, int, int, int], ecrans: list) -> Texte:
        """Pourquoi « Tablette DCS » ne tombe plus sur les écrans : l'écran qui
        reçoit ceux du cockpit a changé (définition, place). La fenêtre de DCS,
        toujours à la taille d'avant, recouvre alors parfois un écran du
        pilote : c'est ce qu'il voit, DCS qui déborde sur cet écran-là."""
        principal = next(m for m in ecrans if m[4])
        px, py = principal[:2]
        _, _, l, h = support
        sur = next((m for m in ecrans if (m[0] - px, m[1] - py) + tuple(m[2:4]) == tuple(support)),
                   principal)
        if sur[4]:
            ecran = Texte("de l'écran principal ({largeur}×{hauteur})", largeur=l, hauteur=h)
        elif len(sur) > 5 and sur[5]:
            ecran = Texte("de l'écran virtuel ({largeur}×{hauteur})", largeur=l, hauteur=h)
        else:
            ecran = Texte("du second écran ({largeur}×{hauteur})", largeur=l, hauteur=h)
        largeur, hauteur, recouverts = self._sous_dcs(ecrans, support)
        if recouverts:
            return Texte("« {nom} » ne tombe plus sur les écrans : les écrans du cockpit "
                         "sortent {ecran}, et la fenêtre de DCS ({largeur}×{hauteur}) "
                         "recouvre {recouverts}", nom=NOM_AFFICHE, ecran=ecran,
                         largeur=largeur, hauteur=hauteur, recouverts=recouverts)
        return Texte("« {nom} » ne tombe plus sur les écrans : les écrans du cockpit "
                     "sortent {ecran}", nom=NOM_AFFICHE, ecran=ecran)

    def _reglages(self, resolution: Tuple[int, int], lance: bool) -> Point:
        titre = Texte("Réglages de DCS")
        l, h = resolution
        voulu = Texte("« {nom} », {largeur}×{hauteur}, {mode}", nom=NOM_AFFICHE, largeur=l,
                      hauteur=h, mode=Texte("fenêtré"))
        if dcs_regle(self.saved_games, resolution):
            return Point(titre, OK, voulu)
        try:
            choix, al, ah = options_affichage(self.saved_games)
            avant = Texte("« {nom} », {largeur}×{hauteur}, {mode}", nom=choix, largeur=al,
                          hauteur=ah, mode=Texte("plein écran") if plein_ecran(self.saved_games)
                          else Texte("fenêtré"))
        except PasDExport as e:
            avant = message(e)
        if not lance:
            try:
                regler_options(self.saved_games, *resolution)
            except (OSError, PasDExport) as e:
                return Point(titre, MANQUE, Texte("réglages illisibles ({erreur})",
                                                  erreur=message(e)), (
                    Texte("Dans DCS : Options → Système → Moniteurs « {nom} », Résolution "
                          "{largeur}×{hauteur}, « Plein écran » décoché, puis relancer DCS.",
                          nom=NOM_AFFICHE, largeur=l, hauteur=h),))
            return Point(titre, REPARE, Texte("remis sur {voulu} (il était sur {avant})",
                                              voulu=voulu, avant=avant))
        return Point(titre, A_FAIRE, Texte("DCS est sur {avant}", avant=avant), (
            Texte("Quitter DCS : DCS Tablette remet ses réglages tout seul, puis relancer DCS."),
            Texte("Ou dans DCS : Options → Système → Moniteurs « {nom} », Résolution "
                  "{largeur}×{hauteur}, « Plein écran » décoché, puis relancer DCS.",
                  nom=NOM_AFFICHE, largeur=l, hauteur=h)))

    def _dcs(self, lance: bool) -> Point:
        if not lance:
            return Point(Texte("DCS"), ATTENTE, Texte("pas lancé"))
        heure = self._lancement()
        try:
            change = heure is not None and fichier_actif(self.saved_games).stat().st_mtime > heure
        except (OSError, PasDExport):
            change = False
        if change:
            return Point(Texte("DCS"), A_FAIRE,
                         Texte("lancé avant le dernier réglage des écrans"),
                         (Texte("Quitter DCS et le relancer : il ne relit les écrans qu'au "
                                "démarrage."),))
        return Point(Texte("DCS"), OK, Texte("lancé") if heure is not None
                     else Texte("en cours de lancement"))

    def _script(self, lance: bool) -> Optional[Point]:
        titre = Texte("Script de la tablette dans DCS")
        if self.pont is None:
            return None
        if not self.pont.a_l_ecoute:
            return Point(titre, MANQUE, Texte("port UDP {port} déjà pris : DCS Tablette "
                                              "n'entend pas DCS", port=self.pont.port_etat), (
                Texte("Une autre fenêtre DCS Tablette est sans doute ouverte : la fermer, puis "
                      "relancer celle-ci."),))
        e = self.pont.etat()
        if e["connecte"]:
            return Point(titre, OK, Texte("DCS parle à la tablette : {appareil}",
                                          appareil=e["appareil"]
                                          or Texte("pas dans un appareil")))
        if not lance:
            return Point(titre, ATTENTE, Texte("démarre avec la mission"))
        ligne = derniere_ligne_tablette(self.saved_games)
        if ligne is None and mission_lancee(self.saved_games) is False:
            # Au menu de DCS : rien à régler, il n'a pas encore lu Export.lua.
            return Point(titre, ATTENTE, Texte("pas encore de mission : le script démarre "
                                               "avec elle"))
        if ligne is None:
            vu = Texte("rien sous DCS-TABLETTE dans dcs.log")
        elif ligne[0]:
            vu = Texte("panne dans dcs.log : « {ligne} »", ligne=ligne[1])
        else:
            vu = Texte("dernier mot dans dcs.log : « {ligne} »", ligne=ligne[1])
        etat = ATTENTE if ligne and not ligne[0] else A_FAIRE
        return Point(titre, etat, Texte("DCS lancé, pas de signal ; {vu}", vu=vu), (
            Texte("Normal au menu de DCS : le script démarre avec la mission."),
            Texte("En mission et toujours rien : relancer la mission (les scripts ont pu "
                  "changer depuis son lancement)."),
            Texte("Rien sous DCS-TABLETTE dans {journal} : Export.lua ne charge pas le script ; "
                  "relancer Installer.bat, puis la mission.",
                  journal=self.saved_games / "Logs" / "dcs.log")))

    def _images(self, lance: bool) -> Optional[Point]:
        titre = Texte("Images des écrans")
        if self.video is None:
            return None
        dernier = getattr(self.video, "dernier", None)
        if dernier is None or self._horloge() - dernier[0] > IMAGE_RECENTE_S:
            return Point(titre, ATTENTE, Texte("aucune tablette n'en demande en ce moment"))
        if dernier[1] is None:
            return Point(titre, OK, Texte("envoyées à la tablette"))
        if not lance:
            return Point(titre, ATTENTE, Texte("DCS pas lancé"))
        return Point(titre, A_FAIRE, dernier[1])

    def _reseau_pc(self) -> Point:
        titre = Texte("Réseau du PC")
        if self._reseau is not None and self._horloge() - self._reseau[0] < PERIODE_RESEAU_S:
            return self._reseau[1]
        profils = self._reseaux()
        if profils is None:
            point = Point(titre, ATTENTE, Texte("non vérifié"))
        elif not profils:
            point = Point(titre, MANQUE, Texte("le PC n'est relié à aucun réseau"), (
                Texte("Le brancher au Wi-Fi ou au câble de la maison : la tablette doit être "
                      "sur le même réseau."),))
        else:
            publics = [nom for nom, categorie in profils if categorie == "Public"]
            if publics:
                point = Point(titre, A_FAIRE, Texte("« {reseau} » est en réseau Public : "
                                                    "Windows y bloque la tablette",
                                                    reseau=publics[0]), (
                    Texte("Paramètres → Réseau et Internet → Wi-Fi (ou Ethernet) → "
                          "« {reseau} » → Type de profil réseau : Privé.", reseau=publics[0]),))
            else:
                point = Point(titre, OK, Texte("{reseaux} en privé", reseaux=[
                    Texte("« {nom} »", nom=n) for n, _ in profils]))
        self._reseau = (self._horloge(), point)
        return point

    def _la_tablette(self) -> Point:
        titre = Texte("Tablette")
        if self._tablette is not None:
            adresse, instant = self._tablette
            depuis = self._horloge() - instant
            if depuis < TABLETTE_RECENTE_S:
                return Point(titre, OK, Texte("connectée ({adresse})", adresse=adresse))
            return Point(titre, ATTENTE, Texte("plus de nouvelles depuis {secondes} s "
                                               "({adresse}) : en veille ?",
                                               secondes=int(depuis), adresse=adresse))
        adresses = adresses_locales() or [Texte("<adresse de ce PC>")]
        return Point(titre, ATTENTE, Texte("aucune connectée pour l'instant"), (
            Texte("Sur la tablette, même Wi-Fi : ouvrir http://{adresse}:{port}",
                  adresse=adresses[0], port=self.port_web),
            Texte("La page ne s'ouvre pas : réseau du PC en Privé (voir plus haut), et DCS "
                  "Tablette autorisé dans le pare-feu : Sécurité Windows → Pare-feu et "
                  "protection du réseau → Autoriser une application via le pare-feu → "
                  "DCS-Tablette, case Privé cochée.")))

    def _version(self) -> Point:
        if self._publiee is None:
            return Point(Texte("Version"), OK, Texte("{version} (pas de nouvelle vérifiée au "
                                                     "lancement)", version=VERSION))
        if numero(self._publiee["version"]) > numero(VERSION):
            return Point(Texte("Version"), ATTENTE,
                         Texte("{nouvelle} disponible, vous avez la {version}",
                               nouvelle=self._publiee["version"], version=VERSION), (
                Texte("Fermer DCS Tablette et le relancer : il se met à jour tout seul, "
                      "réglages gardés. S'il n'y arrive pas, sa fenêtre dit pourquoi."),))
        return Point(Texte("Version"), OK, Texte("{version}, à jour", version=VERSION))

    # ------------------------------------------------------------ l'ensemble

    def _sur(self, titre: str, verification: Callable[[], Optional[Point]]) -> Optional[Point]:
        try:
            return verification()
        except Exception as e:                  # noqa: BLE001 — jamais bloquant
            return Point(titre, ATTENTE, Texte("non vérifié ({type} : {erreur})",
                                               type=type(e).__name__, erreur=message(e)))

    def verifier(self, forcer: bool = False) -> List[Point]:
        """Tous les points, réparations comprises. `forcer` : réessaie aussi ce
        qu'on avait renoncé à réparer tout seul (bouton « Vérifier »)."""
        with self._verrou:
            points = self._calculer(forcer)
            maintenant = time.strftime("%H:%M:%S")
            with self._verrou_etat:
                avant = {p.titre: p for p in self._points}
                nouveaux = []
                for p in points:
                    ancien = avant.get(p.titre)
                    if ancien and (ancien.etat, ancien.detail) == (p.etat, p.detail):
                        continue
                    # Au journal : réparations, problèmes, et problèmes réglés.
                    if p.etat in (REPARE,) + PROBLEMES or (
                            ancien and ancien.etat in PROBLEMES and p.etat == OK):
                        nouveaux.append({"heure": maintenant, **asdict(p)})
                self._points, self._heure = points, maintenant
                self._journal = (self._journal + nouveaux)[-JOURNAL_MAX:]
                self._derniers_nouveaux = nouveaux
            return points

    def _calculer(self, forcer: bool) -> List[Point]:
        try:
            lance = bool(self._ouvert())
        except (OSError, subprocess.SubprocessError):
            lance = False
        points = [self._sur(Texte("Dossier de DCS"), self._dossier)]
        config = None
        if points[0].etat == OK and premiere_fois(self.saved_games):
            # Pas installée, ou désinstallée pendant que DCS Tablette tournait :
            # on ne remet rien d'office, la désinstallation doit tenir.
            points.append(Point(Texte("Installation"), A_FAIRE,
                                Texte("DCS Tablette n'est pas installé dans DCS (ou vient "
                                      "d'être désinstallé)"),
                                (Texte("Lancer Installer.bat pour l'installer."),)))
        elif points[0].etat == OK:
            choix = self._choix()
            # Installé avant que le choix soit retenu (1.4 et avant) : un écran
            # réel déjà en place était pris d'office, il le reste.
            physique = bool(choix.get("physique", not choix))
            mode = choix.get("mode") or ("essai" if mode_essai(self.saved_games)
                                         else "second_ecran")
            essai = mode == "essai"
            points.append(self._sur(Texte("Scripts dans DCS"), lambda: self._scripts(lance)))
            if mode == "existante":
                existante = self._sur(Texte("Écrans de DCS"),
                                      lambda: self._existante(choix.get("configuration", "")))
                points += existante if isinstance(existante, list) else [existante]
            else:
                points.append(self._sur(Texte("Écran virtuel"), lambda: self._ecran_virtuel(
                    essai, forcer, physique, lance)))
                points.append(self._sur(Texte("Écrans de Windows"), lambda: self._windows(
                    self._ecrans(), lance, forcer, bool(choix.get("ranger")))))
                config = self._sur(Texte("Écrans de DCS"), lambda: self._configuration(
                    essai, self._ecrans(), lance, physique))
        if config is not None:
            if isinstance(config, tuple):
                point, resolution = config
                points.append(point)
                if resolution is not None:
                    points.append(self._sur(Texte("Réglages de DCS"),
                                            lambda: self._reglages(resolution, lance)))
            else:
                points.append(config)
        points.append(self._sur(Texte("DCS"), lambda: self._dcs(lance)))
        points.append(self._sur(Texte("Script de la tablette dans DCS"),
                                lambda: self._script(lance)))
        points.append(self._sur(Texte("Images des écrans"), lambda: self._images(lance)))
        points.append(self._sur(Texte("Réseau du PC"), self._reseau_pc))
        points.append(self._sur(Texte("Tablette"), self._la_tablette))
        points.append(self._sur(Texte("Version"), self._version))
        return [p for p in points if p is not None]

    def etat(self) -> Dict:
        """Pour /api/diagnostic : le dernier résultat, sans rien revérifier.
        Ses textes sont des `Texte` : à traduire pour la tablette qui demande."""
        with self._verrou_etat:
            points = [asdict(p) for p in self._points]
            return {"heure": self._heure, "points": points,
                    "problemes": sum(p["etat"] in PROBLEMES for p in points),
                    "journal": list(reversed(self._journal))}

    def tablette_vue(self, adresse: str) -> None:
        """Appelé à chaque demande d'état de la page : une tablette est là."""
        self._tablette = (adresse, self._horloge())

    def relancer(self) -> None:
        self._reveil.set()

    # ------------------------------------------------------------ en fond

    def demarrer(self, afficher: Callable[[str], None] = print) -> None:
        """La liste complète tout de suite, puis toutes les PERIODE_S ce qui
        a changé, horodaté, dans la fenêtre de DCS Tablette."""
        afficher(Texte("Vérification :"))
        try:
            for ligne in lignes_console(self.verifier()):
                afficher(ligne)
        except Exception as e:                  # noqa: BLE001 — le serveur démarre quand même
            afficher("  " + Texte("vérification impossible ({type} : {erreur})",
                                  type=type(e).__name__, erreur=message(e)))
        afficher("")

        def boucle():
            while not self._arret.is_set():
                self._reveil.wait(PERIODE_S)
                self._reveil.clear()
                if self._arret.is_set():
                    return
                try:
                    self.verifier()
                except Exception as e:          # noqa: BLE001 — la boucle continue
                    afficher(Texte("Diagnostic : vérification impossible ({type} : {erreur}).",
                                   type=type(e).__name__, erreur=message(e)))
                    continue
                for evenement in self._derniers_nouveaux:
                    p = Point(evenement["titre"], evenement["etat"], evenement["detail"],
                              tuple(evenement["solution"]))
                    afficher(f"{evenement['heure']}  " + lignes_console([p])[0].lstrip())
                    for ligne in lignes_console([p])[1:]:
                        afficher(ligne)

        threading.Thread(target=boucle, name="tablette-diagnostic", daemon=True).start()

    def arreter(self) -> None:
        self._arret.set()
        self._reveil.set()


# ------------------------------------------------------------ ouverture de Windows

ECRANS = ("Écran virtuel", "Écrans de Windows", "Écrans de DCS", "Réglages de DCS")


def remettre_au_demarrage(saved_games: Path, journal: Path,
                          diagnostic: Optional[Diagnostic] = None,
                          ecrans: Optional[Callable[[], list]] = None,
                          choix: Callable[[], Dict] = lire_choix,
                          attendre: Callable[[float], None] = time.sleep,
                          afficher: Callable[[str], None] = print) -> int:
    """`DCS-Tablette.exe ecrans`, lancé sans fenêtre à chaque ouverture de
    Windows (DCS-Tablette-Ecrans.exe, dossier Démarrage) : les réparations du
    diagnostic, faites avant que DCS soit lancé. Au redémarrage, une mise à
    jour du pilote de l'écran virtuel ou de Windows peut le changer de
    définition ou de place ; DCS, réglé pour l'ancienne disposition,
    s'étendrait alors sur un écran du pilote (photo d'un pilote, 01/11/2026).

    Ce qui a été vu et fait va dans `journal` : pas de fenêtre pour le dire.
    Rend 0 si les écrans sont en place, 1 sinon."""
    voulu = choix()
    physique = bool(voulu.get("physique", not voulu))
    mode = voulu.get("mode") or ("essai" if mode_essai(saved_games) else "second_ecran")
    if mode == "second_ecran" and not physique:
        if ecrans is None:
            from .ecran_virtuel import moniteurs as ecrans
        for _ in range(ATTENTE_ECRAN_VIRTUEL_S // 2):
            if any(len(m) > 5 and m[5] and not m[4] for m in ecrans()):
                break
            attendre(2)
        attendre(POSE_DES_ECRANS_S)
    points = (diagnostic or Diagnostic(saved_games)).verifier(forcer=True)
    lignes = [Texte("DCS Tablette {version} : écrans remis en place à l'ouverture de Windows, "
                    "le {date}", version=VERSION, date=time.strftime("%d/%m/%Y %H:%M:%S"))
              ] + lignes_console(points)
    try:
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text("\n".join(str(l) for l in lignes) + "\n", encoding="utf-8")
    except OSError:
        pass
    for ligne in lignes:
        afficher(ligne)
    return int(any(p.titre in ECRANS and p.etat in PROBLEMES for p in points))
