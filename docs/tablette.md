# DCS Tablette — les écrans du cockpit sur l'iPad

Un iPad (ou tout navigateur du réseau local) devient une planche de bord : les
écrans du cockpit en image, avec leurs boutons sous le doigt, la planche avant
du Hornet redessinée, et le kneeboard. La page s'adapte d'elle-même à
l'appareil piloté dans DCS.

## Appareils pris en charge

| Appareil | Écrans en image + boutons | En plus | Pages du kneeboard depuis l'iPad |
|---|---|---|---|
| F/A-18C Hornet | DDI G, DDI D, AMPCD (20 PB) | UFC tactile, IFEI, instruments de secours, voyants | oui |
| F-16C Viper | MFD G, MFD D (20 OSB) | — | non (touches [ et ]) |
| AH-64D Apache | MPD G, MPD D (T/R/B/L + FCR, WPN, TSD, VID, COM, A/C, *), TEDAC (image) | siège Pilote / CPG à choisir | oui |
| OH-58D Kiowa | MFD G (copilote), MFD D (pilote) : L1–L5, R1–R5, B1–B4, INIT | — | oui |
| A-10C / A-10C II | MFCD G, MFCD D (20 OSB) | — | oui |
| Mi-24P Hind, SA342 Gazelle | — (cockpits à cadrans) | kneeboard | non |
| MiG-29A, TF-51D, appareils FC3 | — | kneeboard | oui |
| Tout autre appareil | — | kneeboard (affichage) | non |

D'où viennent les numéros, et ce qui reste à confirmer :

- Hornet, Apache, A-10C, MiG-29A, TF-51D : relus dans les scripts des modules
  installés ; `tests/test_tablette.py` les recoupe à chaque lancement.
- F-16C, OH-58D, Mi-24P, SA342 : modules absents du poste de développement,
  numéros tirés de [DCS-BIOS](https://github.com/DCS-Skunkworks/dcs-bios)
  (`aircraft_modules/*.lua`). À confirmer au premier vol de chacun :
  - zones d'export de l'OH-58D (`LEFT_MFCD` / `RIGHT_MFCD` d'après le forum
    DCS, sans confirmation d'ED) ;
  - position B1 (menu) en bas à gauche des MPD de l'Apache, déduite de l'ordre
    des arguments 3D.
- Pas de commande de page de kneeboard tant que l'appareil KNEEBOARD du module
  n'est pas relevé : une commande au mauvais appareil actionnerait autre chose.

Ajouter un appareil : un fichier dans `src/tablette/appareils/`, l'entrée dans
`PROFILS`, puis `scripts\generer_lua_appareils.py` (la liste blanche du script
Lua en dépend) et `scripts\installer_dcs.py`.

## Installation

Pour l'escadron : le zip des Releases du dépôt public
(`DCS-Tablette.exe` + `Installer.bat`), sans Python. `Installer.bat` lance
`DCS-Tablette.exe installer`, qui fait les étapes 2 à 4 ci-dessous et pose
le raccourci « DCS Tablette » sur le bureau ; `Desinstaller.bat` défait 2
et 4 (l'écran virtuel reste). Le mode d'emploi est dans le README et dans
`distribution/tablette/zip/LISEZ-MOI.txt`, qui décrit aussi chaque étape à
la main.

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

Luminosité : molette dans le coin bas gauche de chaque cadre (`app.js`,
`moletteLuminosite`), crans de -2 à +5, courbe gamma appliquée par le PC
avant le JPEG (`video.table_luminosite`), retenue par appareil et par écran
sur chaque tablette.

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
   Écrit « Tablette DCS » (une seule configuration pour tous les appareils) et
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

## Sur l'iPad

- **Dispositions** (barre du haut), selon l'appareil : deux écrans, un écran
  seul, UFC + IFEI, Secours, « 3 écrans », « Planche » (tous les écrans et
  panneaux). La page essaie chaque façon de répartir les panneaux en rangées
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
- **Boutons en face des libellés** (retour de vol, 30/10/2026 : sur
  l'Apache, ceux des bouts tombaient à côté) : `reperes_x` / `reperes_y` de
  chaque `Ecran`, là où le module écrit les libellés, lus dans ses scripts —
  Apache MFD_PB_Defs.lua, Hornet MPD_PB_defs.lua, A-10C OSB_positions ;
  `TestContreLesScriptsDesModules` les relit. Le serveur les ramène à
  l'image rognée (`app.vu_par_la_tablette`), la page fait une case par
  bouton centrée sur son libellé, des vides entre (`app.js`, `pistes`).
  Vérifié sur une image dessinée aux positions des scripts : 1,4 px d'écart
  au plus sur un écran de 373 px. F-16C, OH-58D : modules absents du poste,
  boutons également répartis, à caler sur une capture.
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

## Essai sans DCS

`scripts\simuler_dcs_tablette.py [nom DCS de l'appareil]` se fait passer pour
le jeu et affiche chaque ordre reçu. `launch_tablette.bat --local` n'écoute que
le PC ; `--sans-miroir` désactive la fenêtre miroir.
