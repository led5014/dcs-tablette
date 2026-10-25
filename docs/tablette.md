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
`DCS-Tablette.exe installer`, qui fait les étapes 2 et 4 ci-dessous ;
`Desinstaller.bat` les défait. Le mode d'emploi est dans le README du dépôt
public (source : `distribution/tablette/depot/README.md`).

Publier une version : `scripts\publier_tablette.py` recopie la tablette, et
elle seule (liste blanche), dans `..\dcs-tablette` ; y lancer
`scripts\construire_tablette.py` pour le zip, puis commit, tag et release.
Monter `VERSION` dans `src/tablette/__init__.py` avant.

Depuis le code :

1. **Python** et ce dépôt : `.venv` avec FastAPI, uvicorn, Pillow (voir
   `requirements.txt`). Rien d'autre à installer côté tablette.
2. **Scripts Lua dans DCS** : `.venv\Scripts\python.exe scripts\installer_dcs.py`.
   Copie `DCS-Tablette-Export.lua` et `DCS-Tablette-Appareils.lua` dans
   `Saved Games\DCS\Scripts` et ajoute la ligne qui les charge à `Export.lua`,
   après une copie de l'original. Tacview, SRS et les autres restent intacts.
3. **Un second écran que personne ne regarde**, pour que DCS y dessine les
   écrans exportés au lieu de les poser sur la vue :
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

- **Dispositions** (barre du haut), selon l'appareil : deux écrans côte à
  côte, un écran seul, UFC + IFEI, Secours. Sur un grand écran (navigateur du
  PC, iPad Pro), « 3 écrans » et « Planche » (tous les écrans et panneaux
  ensemble) apparaissent quand il y a la place.
- **Boutons** : enfoncés dans le cockpit tant que le doigt est posé.
- **Kneeboard** : un bouton bascule vers lui et revient. En tête, le kneeboard
  de DCS en direct (RShift+K pour l'ouvrir) ; puis les pages de la mission en
  cours, de `Saved Games\DCS\Kneeboard` et des missions du dossier Missions.
- **Sur le PC** : quand le kneeboard de DCS tombe sur l'écran virtuel, une
  fenêtre miroir le recopie en bas à droite de l'écran principal, au-dessus de
  la barre des tâches ; la souris la traverse.

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
