# DCS Tablette — les écrans du cockpit sur l'iPad

Un iPad (ou tout navigateur du réseau local) devient une planche de bord : les
écrans du cockpit en image, avec leurs boutons sous le doigt, la planche avant
du Hornet redessinée, et le kneeboard. La page s'adapte d'elle-même à
l'appareil piloté dans DCS.

## Appareils pris en charge

| Appareil | Écrans en image + boutons | En plus | Pages du kneeboard depuis l'iPad |
|---|---|---|---|
| F/A-18C Hornet | DDI G, DDI D, AMPCD (20 PB) | UFC tactile, IFEI, instruments de secours, voyants | oui |
| F-16C Viper | MFD G, MFD D (20 OSB) | ICP tactile, DED | non (touches [ et ]) |
| AH-64D Apache | MPD G, MPD D (T/R/B/L + FCR, WPN, TSD, VID, COM, A/C, *), TEDAC (image) | siège Pilote / CPG à choisir | oui |
| OH-58D Kiowa | MFD G (copilote), MFD D (pilote) : L1–L5, R1–R5, B1–B4, INIT | — | oui |
| A-10C / A-10C II | MFCD G, MFCD D (20 OSB) | — | oui |
| AV-8B Harrier | MPCD G, MPCD D (20 boutons) | — | oui |
| F-15E Strike Eagle | MPD G, MPD D, MPCD (place avant, 20 PB) | — | oui |
| JF-17 Thunder | MFCD G, centre, D en portrait (U1–5, L1–8, R1–8, D1–5) | — | oui |
| Ka-50 Black Shark II / III | Shkval (image), ABRIS (5 boutons dessous) | — | oui |
| CH-47F Chinook | — (écrans pas encore relevés) | instruments, kneeboard | oui |
| C-130J-30 Super Hercules | HDD G, centre, D (image, pas de boutons : pages choisies sur les AMU) | instruments, kneeboard | oui |
| MiG-29A Fulcrum | HDD, recopie du HUD (interrupteur SOURCE TACT / DUBL) | instruments, disposition « HDD + instr. », kneeboard | oui |
| TF-51D, Fw 190 D-9, appareils FC3 | — (cockpits à cadrans) | instruments, kneeboard | oui |
| Autres warbirds, Corée, jets et hélicoptères à cadrans (`warbirds.py`, `sans_ecran.py`) | — | instruments, kneeboard | non (touches [ et ]) |
| Tout autre appareil | — | instruments (OTAN), kneeboard (affichage) | non |

D'où viennent les numéros, et ce qui reste à confirmer :

- Hornet, Apache, A-10C, MiG-29A, TF-51D, Fw 190 D-9 : relus dans les scripts
  des modules installés ; `tests/test_tablette.py` les recoupe à chaque
  lancement.
- MiG-29A, HDD (31/10/2026, demande : « afficher le HUD, déjà dans un petit
  écran sur le MiG, pour chercher les cibles ») : de tous les modules
  installés, le seul indicateur exportable (`find_viewport`) hors des MFD.
  `Displays/HDD/indicator/BAKE/HDD_init.lua` cherche une zone « HDD », sinon
  RIGHT_MFCD : celle de « Tablette DCS », donc rien à régler. Dans une zone
  carrée, le module recentre l'HDD sur une bande à ses proportions : bandes
  noires possibles, à voir au premier vol. L'interrupteur SOURCE
  (`hdd_commands.SOURCE_KNOB` = 3002, appareil 50, argument 869) est un
  `Bouton(bascule=869)` : le serveur lit sa position et pose l'autre ; le
  script Lua l'accepte dans `positions` (0 ou 1, jamais relâché), pas dans
  `boutons` (relâchés après 5 s). Quelle position est DUBL n'est pas écrit
  dans les scripts, d'où la bascule plutôt que deux boutons.
- F-16C, OH-58D, Mi-24P, SA342, AV-8B, F-15E, JF-17, Ka-50, CH-47F : modules
  absents du poste de développement, numéros tirés de
  [DCS-BIOS](https://github.com/DCS-Skunkworks/dcs-bios)
  (`aircraft_modules/*.lua`), recoupés avec les extractions des `devices.lua`
  et `clickabledata.lua` des modules (DCSAutoMate). À confirmer au premier vol
  de chacun :
  - repères des boutons de l'OH-58D (voir plus bas) ;
  - position B1 (menu) en bas à gauche des MPD de l'Apache, déduite de l'ordre
    des arguments 3D ;
  - place des boutons autour des MPD du F-15E (sens antihoraire depuis le
    haut à gauche, jauge Helios) et des MFCD du JF-17 (ordre des L/R et U/D
    déduit des noms), et comment DCS dessine les MFCD en portrait du JF-17
    dans la zone d'export ;
  - kneeboard des modules sans `KNEEBOARD` dans `devices.lua` (AV-8B, F-15E,
    JF-17, Ka-50) : appareil 100, comme les FC3 ;
  - F-15E : seulement la place avant (la place arrière partage les zones
    d'export sans qu'on sache ce qui s'y dessine) ; CH-47F : pas d'écran tant
    qu'on ne sait pas lequel des cinq MFD sort dans `RIGHT_MFCD`.
- F-16C, ICP et DED (04/11/2026, demande : « l'UFC des différents
  appareils, sur le F-16 par exemple »). L'ICP est l'UFC du F-16 : appareil
  17, commandes 3002–3019 (chiffres, COM1, COM2, IFF, LIST, ENTR, RCL, A-A,
  A-G) relevées dans DCS-BIOS et recoupées avec l'énumération `ufcCommands`
  de Helios. Le dobber (RTN, SEQ, UP, DN, 3032–3035) et la bascule ▲▼ du DED
  (3030–3031) sont des commutateurs à ressort : une commande par côté,
  poussée à -1 ou +1, relâchée à 0 (`defineSpringloaded_3PosTumb` de
  DCS-BIOS). `Profil.ressorts` les porte ; le script Lua les accepte à leur
  seule valeur ou à 0, et les relâche au bout de 5 s comme les boutons.
  Le DED n'a pas de zone d'export : son texte arrive par
  `list_indication(6)`, en morceaux nommés sans position. La place de chacun,
  page par page, est la table `F_16C_DED.lua` de DCS-BIOS (~1 000 morceaux,
  ~80 pages), sous GPL-3.0 : incompatible avec la licence MIT du dépôt, elle
  n'y est pas copiée. `ded.TableDED` la télécharge au premier `/api/ded`
  (DCS-BIOS v0.11.8, par son commit, SHA-256 vérifié), la garde dans
  `%LOCALAPPDATA%\DCS-Tablette\F_16C_DED-v0.11.8.lua` et la lit comme une
  donnée (`ded.table_lua`, un analyseur de constructeur de table, rien
  d'exécuté). Hors ligne : nouvel essai par minute, le DED dit pourquoi, le
  clavier marche. La page affichée n'est pas exportée : `Gabarit.page` prend
  celle qui reconnaît le plus de morceaux présents, la plus petite à égalité.
  Vérifié sur la vraie table avec une page STPT fabriquée ; **pas encore vu
  en vol** : à confirmer, la page reconnue sur chaque écran du DED, les
  caractères spéciaux du module (la flèche ↕ de « IncDecSymbol », le degré),
  et les astérisques, que la table met en vidéo inverse. Changer de version
  de DCS-BIOS : `_COMMIT`, `VERSION_BIOS` et `EMPREINTE` ensemble.
- OH-58D, MFD en 4:3 (02/11/2026, photo de la tablette en 1.11.1 : haut des
  pages coupé, image étirée, bords rognés ; B1–B4 pas en face de leurs
  onglets). Zones natives `LEFT_MFCD` / `RIGHT_MFCD`
  (`Cockpit/MFDs/Indicator/initLMFD.lua` et `initRMFD.lua`, relevé du
  forum) ; 4:3 d'après le modèle Helios « OH58D » (500 × 375) et les
  pilotes du forum (752 × 576), qui signalent le même haut coupé dans une
  zone carrée. « Tablette DCS » garde ses carrés pour tous, et donne au
  Kiowa deux zones 4:3 l'une sous l'autre (960 × 720 sur un second écran
  2560 × 1440) dans `reconfigure_for_unit`, que DCS appelle en entrant dans
  chaque appareil (exemple commenté dans `Config/MonitorSetup/3Cameras.lua`
  de DCS). Les écrans à une autre forme viennent de `Ecran.aspect`
  (`appareils.formes`) : le JF-17, en portrait, en profite aussi. La
  relecture (`ecrans_dcs.lire_zones`) rejoue le fichier pour l'appareil
  piloté (`PontDCS.dernier_appareil`), y compris ceux de Helios
  (`if unit_type == … or false then … return end`). Un fichier d'avant,
  tout en carrés, est récrit par le diagnostic, DCS fermé. Cadre : 4 boutons
  en bas, 5 sur les côtés ; repères mesurés sur la photo, corrigés de la
  zone carrée, bons sur la photo en 4:3 (1.12.0). Cette photo-là montrait
  encore la première lettre des libellés de gauche et la moitié de la ligne
  du haut coupées, comme en carré : les 1,2 % rognés sur chaque bord pour le
  liseré du Hornet (`appareils.ROGNAGE`). `Ecran.rognage` = 0 pour le Kiowa,
  dont le module écrit jusqu'au bord.
- C-130J-30 (01/11/2026, d'après la capture d'un pilote en vol, en mode
  essai) : le module dessine de lui-même dans `LEFT_MFCD` (PFD),
  `CENTER_MFCD` (SYSTEM STATUS) et `RIGHT_MFCD` (moteurs et ACAWS), rien dans
  `TEDAC`. Nom, `KNEEBOARD` = 95 et HDD001–004 = 56–59 : DCS-BIOS. Les HDD
  n'ont pas de boutons (pages choisies sur les AMU, non exportés). À
  confirmer : lequel des quatre HDD sort dans chaque zone, et si la zone
  carrée coupe les HDD, plus hauts que larges (PFD débordant à gauche et bas
  des pages coupé sur la capture).
- Noms des appareils dans DCS (`LoGetSelfData().Name`) : liste de DCS-BIOS
  (`AircraftList.lua`) recoupée avec les définitions de CoreMods du jeu ;
  casse et espaces comptent (« F-86F Sabre », « MiG-21Bis », « FW-190A8 »).
- Pas de commande de page de kneeboard tant que l'appareil KNEEBOARD du module
  n'est pas relevé : une commande au mauvais appareil actionnerait autre chose.

Ajouter un appareil : un fichier dans `src/tablette/appareils/`, l'entrée dans
`PROFILS`, puis `scripts\generer_lua_appareils.py` (la liste blanche du script
Lua en dépend) et `scripts\installer_dcs.py`.

## Installation

Pour l'escadron : le zip des Releases du dépôt public
(`DCS-Tablette.exe` + `Installer.bat`), sans Python. `Installer.bat` lance
`DCS-Tablette.exe installer`, qui fait les étapes 2 à 4 ci-dessous ; la
désinstallation (`Desinstaller.bat`, ou Applications installées) défait 2
et 4 (l'écran virtuel reste). Le mode d'emploi est dans le README et dans
`distribution/tablette/zip/LISEZ-MOI.txt`, qui décrit aussi chaque étape à
la main.

Installation et mise à jour les plus simples possible (demande du
31/10/2026, « à chaque fois ») :
- le programme s'installe pour l'utilisateur seul dans
  `%LOCALAPPDATA%\Programs\DCS-Tablette`, comme VS Code ou Discord : sans
  droits d'administrateur, et la mise à jour peut y écrire. Le zip
  s'extrait n'importe où ; `installation.installer_programme` copie ce
  qu'il a posé (`LIVRES`), pose les raccourcis du bureau et du menu
  Démarrer, et l'entrée d'Applications installées (`HKCU\…\Uninstall\
  DCS-Tablette`, `enregistrer`), puis `Installer.bat` démarre le serveur.
  Jusqu'à la 1.8.0, le programme restait là où le zip avait été extrait ;
- lancé depuis un autre dossier alors qu'il est installé (le dossier extrait
  gardé), l'exécutable démarre l'installé (`exe_installe`) : un seul
  exemplaire à tenir à jour. À chaque lancement, `tenir_a_jour` remet la
  version de l'entrée de Windows et pose le raccourci du menu Démarrer s'il
  manque (installations d'avant) ;
- à chaque ouverture de Windows, `DCS-Tablette-Ecrans.exe` (dossier
  Démarrage, `installation.ecrans_au_demarrage`) lance `DCS-Tablette.exe
  ecrans` sans console (`CREATE_NO_WINDOW`) : `diagnostic.remettre_au_
  demarrage` attend l'écran virtuel, fait les réparations du diagnostic
  avant que DCS soit lancé, et écrit ce qu'il a vu dans
  `%LOCALAPPDATA%\DCS-Tablette\ecrans.log`. Né d'une photo de pilote
  (01/11/2026) : écran virtuel repassé en 1920 × 1080 au redémarrage, son
  écran réel à sa place, DCS étalé dessus. Un petit exécutable à part
  (`scripts/dcs_tablette_ecrans.py`, `console=False` dans le .spec), parce
  qu'un raccourci ne sait pas lancer une console cachée et que le terminal
  de Windows 11 ignorerait « réduite ». `tenir_a_jour` le pose une fois aux
  installations d'avant la 1.11.0 (`demarrage` dans installation.json) :
  retiré à la main, il ne revient pas ;
- un écran à gauche du principal mais décalé en hauteur fait partir la
  fenêtre de DCS de lui. Photos du même pilote (« Identifier » : son écran
  2 à gauche du principal, un peu plus bas, la vue de DCS partie sur lui),
  puis essai avec lui le 02/11/2026 : écran débranché, ou remonté bords du
  haut alignés, DCS revient sur le principal ; redescendu, DCS repart.
  (La 1.11.0 croyait que DCS partait du coin haut gauche du bureau entier
  et rangeait l'écran SOUS le principal : abandonné, et rien ne prouve
  qu'un écran dessous ne gêne pas aussi.) `installation.genants` repère
  les écrans réels à gauche décalés en hauteur, ou au-dessus du principal ;
  `rangement` aligne leur bord du haut sur celui du principal, du même
  côté (au-dessus : à gauche), sans chevauchement ni changement d'ordre ;
  `ecran_virtuel.ranger` les y met. Jamais sans accord : l'installation
  demande, et retient `ranger` dans installation.json ; avec lui, le point
  « Écrans de Windows » du diagnostic (et l'ouverture de Windows) les
  réaligne, DCS fermé. Sans, il dit de relancer Installer.bat ;
- avec plusieurs écrans réels (ou l'écran virtuel en principal),
  l'installation demande sur lequel mettre DCS, par son numéro dans « Vos
  écrans », chaque écran nommé par son modèle (`noms_des_ecrans`,
  QueryDisplayConfig : EnumDisplayDevices ne dit que « Generic PnP
  Monitor »). Un autre que le principal en devient le principal
  (`ecran_virtuel.rendre_principal` : lui en (0, 0) avec
  CDS_SET_PRIMARY, les autres décalés d'autant) ; si Windows refuse,
  l'installation s'arrête et dit quoi cocher ;
- la mise à jour se fait sans question (`mise_a_jour.appliquer`) : la
  question O/n de la 1.5.0 à la 1.8.0 (15 s pour répondre) passait le plus
  souvent sans réponse, DCS Tablette lancé puis laissé derrière DCS ;
- la désinstallation, depuis Windows (`desinstaller --attendre`, pour que la
  fenêtre reste lisible) ou `Desinstaller.bat`, efface aussi le programme :
  un script cmd sans fenêtre (`EFFACER`) attend la fermeture de l'exe, puis
  ne retire que les fichiers de `LIVRES` et le dossier s'il est alors vide.

L'étape 3 était celle où les pilotes bloquaient : placer l'écran virtuel au
pixel près, à droite et aligné en haut (30/10/2026). `ecran_virtuel.py` la
fait :
- trouve l'écran virtuel (`EnumDisplayDevices` : « Virtual Display Driver »,
  `Root\MttVDD`, moniteur `MTT1337`) ; un écran physique n'est jamais
  déplacé, une prise HDMI factice déjà à droite est gardée ;
- s'il manque, et si le pilote répond O : télécharge Virtual Display Driver
  25.7.23 et NefCon 1.14.0 (versions et SHA-256 fixés, les mêmes que
  `silent-install.ps1` du projet VDD), écrit `vdd_settings.xml` avec la
  définition et la fréquence du principal, installe par
  `nefconw install MttVDD.inf Root\MttVDD`. Seule partie en administrateur,
  dans un processus à part (`DCS-Tablette.exe pilote-ecran-virtuel`, UAC) ;
  les certificats du pilote ne sont pas ajoutés aux éditeurs de confiance,
  Windows demande donc confirmation. Un appareil désactivé est réactivé
  plutôt que doublé ;
- remet en mode « Étendre » s'il est dupliqué (`SetDisplayConfig`), puis le
  place (`ChangeDisplaySettingsEx`, enregistré) et relit la position.
Essayé en vrai : la détection et le téléchargement vérifié, sur le poste de
développement. L'installation du pilote et le placement ne sont couverts
que par les tests (écrans décrits) : à essayer sur un PC sans écran virtuel.

Après l'installation, `diagnostic.py` (30/10/2026) : la console de
diagnostic, dans la fenêtre du serveur et sur la tablette (pastille ou
badge « ⚠ n », `/api/diagnostic`). Une douzaine de points vérifiés au lancement puis
toutes les 10 s ; répare seule ce qui est sûr (scripts périmés recopiés,
écran virtuel remis par `ecran_virtuel.remettre`, `tablette.lua` réécrite
si ses zones ne tombent plus sur l'écran — retouchée à la main et toujours
juste, elle reste —, `options.lua` remis DCS fermé seulement). Un écran
virtuel qu'on n'a pas su remettre n'est pas réessayé seul avant 10 minutes :
chaque essai fait clignoter les écrans. Rien n'est installé sans accord.
Lancé sans être passé par Installer.bat, l'exécutable installe d'abord
(`premiere_fois`). Vu au premier essai : le Wi-Fi du poste de
développement était en réseau Public.

Toutes les configurations d'écrans (30/10/2026, `installation.supports`,
`ecran_virtuel.planifier`) : la fenêtre de DCS part du coin haut gauche du
principal et s'étend à droite et vers le bas (les fichiers MonitorSetup
livrés « auto_placement » le confirment : `displays[i].x - screen.x`). Les
écrans exportés vont donc sur l'écran collé à droite (bords du haut) ou
dessous (bords de gauche), et la fenêtre ne doit couvrir aucun autre écran,
qui resterait noir en vol. L'écran virtuel va à droite si c'est libre (la
disposition éprouvée en vol), sinon dessous. Le kneeboard suit la formule
de ViewportHandling.lua (`min(h/2, w/2)`, en bas à droite de la fenêtre) :
`ecrans_dcs.disposition` loge les quatre écrans hors de lui, quel que soit
le côté. En disposition « dessous », le kneeboard ouvert déborde en partie
sur l'écran principal — c'est DCS qui le place. **Pas encore essayé en vol :
la fenêtre de DCS étendue vers le bas (2560 × 2880).**
Un écran réel n'est jamais pris d'office (avant : une prise HDMI factice à
droite était supposée) ; une configuration du pilote qui exporte déjà les
écrans est gardée si il le veut ; le choix est retenu dans
`%LOCALAPPDATA%\DCS-Tablette\installation.json` pour le diagnostic.

Réglages des écrans (`filtres.py`, 31/10/2026 ; demande : « augmenter le
grain, un filtre par-dessus qui gère aussi la lum, plus grand panel de
résolution, lum et grain »). Molette dans le coin bas gauche de chaque cadre
(`app.js`, `moletteLuminosite`) : tournée, la luminosité ; touchée, le
panneau de l'écran (`ouvrirReglages`) :

- luminosité -4 à +8 (gamma × 1,25 par cran) et contraste -3 à +5 (écart
  au gris moyen × 1,2 par cran), en une seule table (`table_tons`) ;
- netteté 0 à 5 : masque flou (rayon 0,8, 45 % par cran) sur les pixels de
  DCS, avant l'agrandissement — après, quatre fois plus de calcul ;
- définition : Économe (× 0,75, JPEG 75), Normale (× 1, JPEG 85, comme
  avant), Fine (× 1,5, 90), Très fine (× 2, 92), agrandie au Lanczos. Mesuré
  sur 720 px : 4 ms l'image normale, 46 ms en Très fine avec netteté (170 Ko
  au lieu de 50). Elle ne crée pas de détail : celui-ci dépend de la taille
  de la zone d'export (720 px sur un écran virtuel de 1440 de haut, dit dans
  le panneau d'après l'en-tête `X-Taille-Source`) ;
- filtres : niveaux auto (`ImageOps.autocontrast`, 0,5 % coupés à chaque
  bout, tons préservés : pour un TGP ou un FLIR sombre), noir et blanc,
  inversé (noir chaud / blanc chaud), vert, ambre, rouge de nuit.

Tout s'applique sur le PC AVANT le JPEG (après, les détails mangés par la
compression seraient perdus), hors du verrou de la copie : un écran en Très
fine ne retarde pas les autres. Seuls les réglages qui s'écartent du défaut
partent dans l'adresse ; retenus par appareil et par écran sur chaque
tablette (`reglages.<appareil>.<écran>`, la luminosité des versions
précédentes reprise), « Pareil sur les autres écrans » les recopie.

Publier une version : monter `VERSION` dans `src/tablette/__init__.py`,
lancer `scripts\construire_tablette.py` pour le zip, puis commit, tag et
release GitHub avec le zip. Les notes de version gardent une section
« ## Nouveau » en puces (`mise_a_jour.nouveautes` les montre au pilote) et
l'empreinte SHA-256 du zip (repli si GitHub ne la donne pas).

Depuis le code :

1. **Python** et ce dépôt : `.venv` avec FastAPI, uvicorn, Pillow (voir
   `requirements.txt`). Rien d'autre à installer côté tablette.
2. **Scripts Lua dans DCS** : `.venv\Scripts\python.exe scripts\installer_dcs.py`.
   Copie `DCS-Tablette-Export.lua` et `DCS-Tablette-Appareils.lua` dans
   `Saved Games\DCS\Scripts` et ajoute la ligne qui les charge à `Export.lua`,
   après une copie de l'original. Tacview, SRS et les autres restent intacts.
3. **Un second écran que personne ne regarde**, pour que DCS y dessine les
   écrans exportés au lieu de les poser sur la vue. `python -m tablette
   installer` l'installe et le place (voir plus haut). À la main :
   - [Virtual Display Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver)
     (gratuit) : installer avec *VDD Control*, puis dans Paramètres → Écran,
     régler l'écran virtuel en **2560 × 1440** (ou la taille de l'écran
     principal), à la même fréquence, **à droite** du principal et aligné en
     haut ;
   - ou une prise HDMI factice.
4. **Configuration d'écrans de DCS**, DCS fermé :
   `.venv\Scripts\python.exe scripts\configurer_ecrans_dcs.py --second-ecran`.
   Écrit « Tablette DCS » (une seule configuration pour tous les appareils,
   zones à leur forme pour ceux dont les écrans ne sont pas carrés) et
   la sélectionne dans `options.lua` avec la résolution qui couvre les deux
   écrans, en fenêtré.
5. **Lancer** : double-cliquer `launch_tablette.bat`. La fenêtre affiche
   l'adresse à ouvrir sur l'iPad. Au premier lancement, autoriser Python sur
   le réseau quand Windows le demande.
6. **Sur l'iPad** : ouvrir l'adresse dans Safari, puis Partager → « Sur l'écran
   d'accueil » pour l'avoir en plein écran. Verrouillage automatique sur
   « Jamais » pendant le vol.

Sans second écran, `configurer_ecrans_dcs.py` sans option pose les écrans en
bas de la vue : pour essayer, pas pour voler.

## Instruments de base, pour tout appareil

`instruments.py` (31/10/2026, demande : des warbirds sans écran, garder la
tête dehors). Le script Lua envoie pour TOUT appareil, avec ou sans profil,
20 fois par seconde, un message « vol » : `LoGetIndicatedAirSpeed`,
`LoGetAltitudeAboveSeaLevel`, `LoGetADIPitchBankYaw`, `LoGetMagneticYaw`,
`LoGetVerticalVelocity`, `LoGetAccelerationUnits`, `LoGetSlipBallPosition`,
`LoGetEngineInfo`, `LoGetMechInfo`… en unités de DCS (m/s, m, rad ; voir
Scripts/Export.lua). « vol - » quand `LoIsOwnshipExportAllowed()` est faux
(serveur multijoueur). `dcs.py` en tire le taux de virage (dérivée du cap,
lissée : le signe de `LoGetAngularVelocity` n'est pas sûr d'un module à
l'autre), `instruments.lecture` convertit dans les unités du profil
(`Profil.instruments` : OTAN, WARBIRD_US, WARBIRD_METRIQUE, METRIQUE,
HELICO_KT, HELICO_METRIQUE) et calcule les angles des aiguilles ; la page
dessine (`construireInstruments`, `compas`, `indicateurVirage`). Ce sont les
grandeurs de vol de DCS, pas les aiguilles du module : ni ses pannes, ni
son calage. Le script tourne dans les tests, dans le moteur Lua de DCS
(son `bin/lua.dll`), avec un faux DCS.

Unités par appareil : manuels ED quand ils ont pu être lus (P-51D : badin
0–700 mph, vario ±6000 ft/min ; Fw 190 D-9 : jusqu'à 900 km/h ; Mosquito :
mph, ±4000 ft/min), DCS-BIOS et DCS-ExportScripts sinon. Les moins sûres :
F4U (nœuds), I-16 et Yak-52 (métriques), Mirage F1 et C-101 (nœuds
supposés). Deux cockpits changent d'unités selon les options de DCS
(`Profil.imperial`) : le MiG-29A (`MiG29AvionicsUnits = 1`, « Imperial ») et
le L-39 (`avionicsLanguage = "english"`). Le serveur relit
`Config/options.lua` quand DCS l'a réécrit ; la lecture porte une `cle` des
cadrans, et la page redemande les siens quand elle change.

## Sur l'iPad

- **Dispositions** (barre du haut), selon l'appareil : deux écrans, un écran
  seul, UFC + IFEI, ICP (avec le DED), Secours, « 3 écrans », « Planche »
  (tous les écrans et panneaux). La page essaie chaque façon de répartir les panneaux en rangées
  sur la place réelle (téléphone, tablette, PC, portrait ou paysage) et ne
  propose un regroupement que si chaque panneau y garde sa largeur de
  confort (`CONFORT` dans `web/app.js`) ; un écran seul, l'UFC et le Secours
  restent toujours proposés. Le Secours a deux formes, en largeur et en
  hauteur. Aucune taille d'appareil n'est écrite en dur, et la page ne
  dépend d'aucune fonction récente des navigateurs (tailles posées en
  pixels par le script, pas de « container queries »).
- **Écran d'accueil** : manifeste et icônes (`scripts/generer_icones.py`)
  pour Android et iOS ; bouton ⛶ (plein écran) là où le navigateur le permet.
- **Boutons** : enfoncés dans le cockpit tant que le doigt est posé.
- **Appareil** (menu en haut à gauche) : *Auto* suit l'annonce de DCS ; un
  appareil choisi à la main prépare la page avant la mission. Le choix vit
  dans un cookie de la page (`tablette_appareil`) : chaque tablette a le
  sien. Garde-fou (`garde_fou` dans `app.py`) : choisi ≠ piloté, aucun ordre
  ne part, car la liste blanche du script Lua suit l'appareil PILOTÉ et
  laisserait passer un numéro qui y désigne autre chose (OSB 1 du MFD droit
  du F-16 = A/P de l'UFC du Hornet).
- **Coins des écrans** : `arrondi` de chaque `Ecran` ; 0,17 mesuré sur les
  DDI du Hornet, 0,02 ailleurs tant que rien n'est mesuré (l'écran de
  l'Apache est quasi carré).
- **Image entière dans le verre** : `object-fit: contain` sur la toile. Le
  verre n'a pas tout à fait la forme que calcule `construireCadre` (marges
  et bordures en %, mesuré 1,361 au lieu de 4:3 sur le Kiowa en 1280 × 800) ;
  l'image garde ses proportions, avec au plus un liseré noir d'1 % sur deux
  bords, au lieu d'être étirée. Vérifié en 1280 × 800, 1340 × 620 et
  1024 × 768, deux MFD et un seul : les quatre bords de l'image visibles.
- **Boutons en face des libellés** (retour de vol, 30/10/2026 : sur
  l'Apache, ceux des bouts tombaient à côté) : `reperes_x` / `reperes_y` de
  chaque `Ecran`, là où le module écrit les libellés, lus dans ses scripts —
  Apache MFD_PB_Defs.lua, Hornet MPD_PB_defs.lua, A-10C OSB_positions ;
  `TestContreLesScriptsDesModules` les relit. Le serveur les ramène à
  l'image rognée (`app.vu_par_la_tablette`), la page fait une case par
  bouton centrée sur son libellé, des vides entre (`app.js`, `pistes`).
  Vérifié sur une image dessinée aux positions des scripts : 1,4 px d'écart
  au plus sur un écran de 373 px. OH-58D : calé sur une photo de la
  tablette, à affiner. F-16C : module absent du poste, boutons également
  répartis, à caler sur une capture.
- **Appuis** : rien d'écrit sur l'image quand l'appui passe (retour de vol :
  « T1 enfoncé » masquait le bas de l'écran) ; un refus et le cran de
  luminosité s'affichent 1,8 s.
- **Script Lua** : écrit dans dcs.log sous `DCS-TABLETTE` (chargé, prêt,
  appareil vu, ou la panne) ; démarrage manqué ou port pris : nouvel essai
  toutes les 5 s, et l'appareil est annoncé même sans écoute des appuis.
  Vu en vrai le 26/10 : un vol entier dans l'Apache sans un mot du script,
  cause non retrouvée faute de trace.
- **Kneeboard** : un bouton bascule vers lui et revient. Carnets
  (`kneeboard.py`) :
  - « Kneeboard DCS (en direct) » : la capture du kneeboard de DCS, seule
    source des pages que DCS fabrique (fréquences, points) ;
  - « Kneeboard de l'avion », par défaut : les fichiers que DCS met dans le
    kneeboard de l'appareil piloté — mission en cours (`.miz`, ou `.trk` en
    multijoueur : vu dans dcs.log, DCS y charge la mission du serveur), pages
    du module, `Saved Games\DCS\Kneeboard\<appareil>` puis `Kneeboard\` ;
  - « Cartes : <carte> » : planches de la carte de la mission
    (`Mods/terrains/<carte>/Kneeboard`, 53 pour le Caucase) ;
  - les autres missions du dossier Missions.
  Dossier de DCS lu sur le DCS.exe qui tourne ; module et carte retrouvés par
  leurs `entry.lua` (`make_flyable('<appareil>'`, `local self_ID = "<carte>"`).
  DDS, TGA, BMP convertis en PNG.
- **Kneeboard DCS sur PC ou tablette** (onglet Kneeboard) : où va le
  kneeboard quand on l'ouvre dans DCS (RShift+K, K).
  - PC : une fenêtre miroir le recopie en bas à droite de l'écran principal
    (DCS le dessine sur l'écran virtuel), au-dessus de la barre des tâches ;
    la souris la traverse.
  - Tablette : pas de miroir ; l'ouvrir dans DCS amène la tablette sur le
    kneeboard en direct, le refermer la ramène où elle était. Et l'inverse :
    regarder le kneeboard en direct sur la tablette l'ouvre dans DCS (DCS
    ne le dessine qu'ouvert), passer à autre chose le referme — message
    « kneeboard ±1 », le coup d'œil de la touche K (iCommandPlaneShowKneeboard,
    1587, `LoSetCommand`), seul ordre accepté hors liste blanche.
  La page se recharge seule quand la version du serveur change (`version`
  dans `/api/etat`) : une icône d'écran d'accueil n'a pas de bouton pour
  recharger, et la vieille page tournait sur le nouveau serveur.
  La page redit son choix à chaque demande d'état (`/api/etat?kneeboard=…`) ;
  muette plus de 10 s, le PC reprend le kneeboard (`AffichageKneeboard`).

## Fonctionnement

- Le script Lua annonce l'appareil piloté ; le serveur choisit son profil
  (`src/tablette/appareils/`) et la page se reconstruit. Le dernier profil
  reste actif entre deux missions.
- Les écrans exportés sont copiés dans la fenêtre de DCS : copie de la zone à
  l'écran quand DCS y est visible (rapide, toujours le cas sur l'écran
  virtuel), copie de la fenêtre elle-même sinon. La tablette ne montre jamais
  rien d'autre que DCS.
- Les boutons partent en UDP vers le script Lua, qui n'accepte que la liste
  blanche de l'appareil piloté et relâche de lui-même un bouton tenu plus de
  5 secondes.
- Les captures (`captures.py`, 31/10/2026 ; retour : « quand on fait une
  capture ou un stream sur Discord, ça montre les 2 écrans ») : la fenêtre
  de DCS couvre l'écran principal et l'écran virtuel, et tout ce qui la
  capture en prend toute la largeur (vu : un F12 de Steam en 5120 × 1440).
  Toutes les 2 s, les nouvelles images des dossiers de captures — DCS
  (`Saved Games\DCS\Screenshots`), Steam (`userdata\*\760\remote\223750\
  screenshots`, vignette refaite), Windows (dossier connu Captures d'écran)
  et Game Bar (`Vidéos\Captures`) — qui ont exactement la taille de l'image
  de DCS (`options.lua`) sont recadrées sur la vue `Center` de la
  configuration d'écrans. JPEG réenregistré avec ses tables de
  quantification (même qualité), date du fichier gardée, fichier remplacé
  d'un coup ; une image illisible (en cours d'écriture) est reprise au
  passage suivant. Les anciennes captures et celles d'une zone ne bougent
  pas. Mesuré sur la capture Steam : 67 ms. `--captures-entieres` coupe tout.
  La vignette de Steam est refaite, mais `screenshots.vdf` garde la taille
  d'origine : Steam le tient ouvert et le réécrit.
- Les langues (`langues.py`, 01/11/2026) : français ou anglais. Le texte
  s'écrit toujours en français dans le code ; `Texte("… {valeur} …",
  valeur=…)` le traduit à la demande d'après `anglais.py`, dont les clés sont
  les phrases françaises. Comme chaîne, un `Texte` vaut sa traduction dans la
  langue du PC (celle de Windows, ou `--langue en|fr|auto`, retenue dans
  `%LOCALAPPDATA%\DCS-Tablette\langue.txt`) ; la tablette a la sienne (choix
  FR / EN du panneau Diagnostic, cookie `tablette_langue`, sinon
  `Accept-Language`), et l'API lui traduit chaque `Texte` au dernier moment
  (`langues.dans`). Un point du diagnostic peut ainsi s'afficher en français
  sur le PC et en anglais sur la tablette. La page passe par `tr('…')` ; ses
  textes lui arrivent par `/textes.js`, avec la langue décidée par le
  serveur. Français si la langue demandée est le français, anglais pour toute
  autre, français faute de rien savoir. Une phrase changée dans le code doit
  l'être dans `anglais.py` : `TestLangues` refuse une clé manquante ou en
  trop, et une traduction qui perd une `{valeur}`. Une f-string ou un `+`
  aplatissent un `Texte` dans la langue du PC : ce qui part vers la tablette
  s'assemble par des `Texte` imbriqués. Les décisions prises sur un texte
  (« commence par aucun ») regardent le français, la référence
  (`dans(texte, "fr")`).

## Essayé et écarté

- Dessiner les écrans sous le bord bas d'une fenêtre plus haute que l'écran
  (25/10/2026) : DCS réglé en 2560 × 2240 garde une fenêtre de 2560 × 1440,
  et ce qui dépasse n'est dessiné nulle part.
- Déplacer le kneeboard de DCS sur l'écran principal : la position ne tient
  pas d'une session à l'autre, et changer sa place par défaut demande de
  modifier un fichier de DCS (contrôle d'intégrité en multijoueur). D'où le
  miroir.
- RWR et HUD redessinés : DCS ne donne pas la position des symboles du RWR,
  ni de quoi refaire le HUD. Le RWR reste lisible sur la page EW d'un écran.
- Un stream de la seule vue principale (31/10/2026) : Discord, OBS ou la
  Game Bar partagent la fenêtre de DCS en entier, et DCS n'en fait qu'une,
  écran virtuel compris — rien à recadrer de notre côté. Une fenêtre « vue
  seule » recopiant la vue par une vignette DWM (façon OnTopReplica) se
  partagerait, mais ni Discord ni OBS n'ont été essayés dessus, et partager
  l'écran principal donne la même chose sans rien installer : c'est la
  marche à suivre (README, « Captures et stream »).

## Essai sans DCS

`scripts\simuler_dcs_tablette.py [nom DCS de l'appareil]` se fait passer pour
le jeu et affiche chaque ordre reçu. `launch_tablette.bat --local` n'écoute que
le PC ; `--sans-miroir` désactive la fenêtre miroir.
