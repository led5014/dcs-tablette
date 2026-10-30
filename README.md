# DCS Tablette

Les écrans du cockpit de DCS World sur une tablette, avec leurs boutons sous
le doigt. La page s'adapte toute seule à l'appareil piloté et à l'écran qui
l'affiche : iPad, tablette Android, téléphone, navigateur d'un autre PC.

- **Écrans en direct** : DDI, MFD, MPD… recopiés depuis DCS, sans scintillement.
- **Boutons tactiles** : chaque appui est joué dans le cockpit, tant que le
  doigt est posé.
- **Luminosité écran par écran** : une molette dans le coin bas gauche de
  chaque cadre, pour un TGP trop sombre ou un écran trop pâle ; retenue par
  appareil.
- **Planche avant du Hornet** redessinée : UFC tactile, IFEI, instruments de
  secours, voyants.
- **Kneeboard** : les pages de l'avion piloté lues directement dans les
  fichiers, nettes à toute taille — mission en cours (solo ou multijoueur),
  pages du module, les vôtres, planches de la carte — et celui de DCS en
  direct. Au choix, la touche kneeboard de DCS l'affiche sur le PC comme
  d'habitude, ou sur la tablette, qui bascule alors d'elle-même dessus — et
  dans ce mode, l'ouvrir sur la tablette l'ouvre dans DCS, sans clavier.
- **Toutes les tailles d'écran** : la page ne propose que les dispositions
  qui restent confortables au doigt sur l'écran utilisé — un ou deux écrans
  sur un téléphone, trois sur une tablette en paysage, toute la planche sur
  un grand écran — et se réarrange quand on la fait pivoter.

Pas de Python à installer, rien sur internet en vol : le serveur tourne sur
le PC, l'iPad s'y connecte par le Wi-Fi de la maison.

## Télécharger

Dernière version : **[Releases](../../releases/latest)** → `DCS-Tablette-x.y.z.zip`.

Le zip contient `DCS-Tablette.exe`, `Installer.bat`, `Desinstaller.bat` et un
`LISEZ-MOI.txt` qui reprend ce qui suit.

**Mettre à jour : rien à réinstaller.** À partir de la 1.5.0, DCS Tablette
regarde à son lancement s'il existe une version plus récente et propose de
se mettre à jour : téléchargement vérifié (SHA-256), remplacement de ses
fichiers, relance — vos réglages restent. DCS peut rester ouvert ; sans
réponse au bout de 15 s, il démarre sans mettre à jour. Seule demande faite
à internet, au lancement ; `--sans-mise-a-jour` la supprime. Depuis
une version plus ancienne, extraire une dernière fois le zip à la place de
l'ancien dossier.

## Appareils

| Appareil | Écrans + boutons | En plus |
|---|---|---|
| F/A-18C Hornet | DDI G, DDI D, AMPCD | UFC tactile, IFEI, secours, voyants |
| F-16C Viper | MFD G, MFD D | — |
| AH-64D Apache | MPD G, MPD D (+ FCR, WPN, TSD…), TEDAC en image | siège Pilote / CPG |
| OH-58D Kiowa | MFD G, MFD D | — |
| A-10C / A-10C II | MFCD G, MFCD D | — |
| Mi-24P, SA342, MiG-29A, TF-51D, FC3 | — (cockpits à cadrans) | kneeboard |

Tout autre appareil a au moins le kneeboard. Les numéros des boutons du F-16C,
de l'OH-58D, du Mi-24P et de la Gazelle viennent de
[DCS-BIOS](https://github.com/DCS-Skunkworks/dcs-bios) et restent à confirmer
en vol : un retour est bienvenu.

Sur le Hornet, l'Apache et l'A-10C, chaque bouton est en face du libellé que
le module écrit sur l'écran (positions lues dans les scripts du module). Sur
le F-16C et l'OH-58D, les boutons sont également répartis le long du cadre :
une capture d'écran de leurs MFD permettra de les caler aussi.

## Installation

1. Extraire le zip là où il restera (par exemple dans Documents), puis
   double-cliquer **`Installer.bat`**.
2. Si Windows affiche « Windows a protégé votre ordinateur » : *Informations
   complémentaires* → *Exécuter quand même*. L'exécutable n'est pas signé ; il
   est construit à partir de ce dépôt (`scripts/construire_tablette.py`).
3. Répondre aux questions de la fenêtre. Elle affiche d'abord vos écrans et
   vos réglages de DCS, puis fait le reste en tenant compte de ce que vous
   avez déjà. Si votre configuration d'écrans de DCS exporte déjà les écrans
   du cockpit (vrais MFD, Helios…), elle propose de la garder : la tablette
   les prend là où ils sont.

   1. **Écran virtuel.** DCS dessine les écrans exportés sur un écran : sans
      second écran, ils recouvrent la vue. S'il n'y a pas d'écran virtuel,
      l'installation propose d'installer
      [Virtual Display Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver)
      (gratuit, open source ; internet nécessaire pour cette étape). Windows
      demande l'autorisation administrateur, puis de confirmer le pilote.
      Elle le place ensuite **à droite** du principal, ou **dessous** si un de
      vos écrans occupe déjà la droite (la fenêtre de DCS ne doit couvrir
      aucun de vos écrans), à la même définition et à la même fréquence :
      rien à régler dans Paramètres → Écran. Un de vos écrans n'est utilisé
      que si vous dites que c'est une prise HDMI factice ; sans aucune place
      libre, elle propose le mode essai.
   2. **Scripts** de la tablette dans `Saved Games\DCS\Scripts`.
   3. **Écrans de DCS** : configuration « Tablette DCS », résolution des deux
      écrans, fenêtré. Si DCS est ouvert, la fenêtre attend qu'on le ferme.

   Puis elle pose un raccourci **DCS Tablette** sur le bureau.

Si une étape n'aboutit pas, la fenêtre dit laquelle et quoi faire. Chaque
étape se fait aussi à la main : section « À la main » du `LISEZ-MOI.txt`
([source](distribution/tablette/zip/LISEZ-MOI.txt)). En bref : installer
Virtual Display Driver avec *VDD Control* ; dans Paramètres → Système → Écran,
« Étendre ces affichages », écran virtuel à la définition et à la fréquence
du principal, glissé à sa droite, bords du haut alignés ; relancer
`Installer.bat`.

### En vol

1. Double-cliquer **DCS Tablette** sur le bureau : la fenêtre affiche
   l'adresse à ouvrir sur la tablette (`http://192.168.x.x:8320`). Au premier
   lancement, autoriser le programme sur le réseau **privé**.
2. Sur la tablette ou le téléphone, ouvrir l'adresse :
   - iPad, iPhone : Safari, puis *Partager* → *Sur l'écran d'accueil* ;
   - Android : Chrome, puis ⋮ → *Ajouter à l'écran d'accueil*, ou le bouton
     ⛶ pour le plein écran.
3. Lancer DCS et une mission.

Navigateurs : la page évite les fonctions récentes, pour tourner aussi sur
les iPad restés sous un ancien iOS et sur les Android d'entrée de gamme.
Minimum : **iOS / iPadOS 13** (iPad Air 2, iPad mini 4, iPad 5e génération et
suivants) — avant, les boutons ne réagissent pas au doigt.
Essayée dans Chrome aux tailles des téléphones, tablettes et écrans de PC
courants ; un retour sur votre appareil est bienvenu.

## Ce que l'installation modifie

Dans DCS, uniquement `Saved Games\DCS`, jamais le dossier d'installation de
DCS (le contrôle d'intégrité du multijoueur n'est pas concerné) :

| Fichier | Changement | Copie gardée |
|---|---|---|
| Windows : écran virtuel | installé s'il manque et si on accepte (Virtual Display Driver 25.7.23, empreinte vérifiée, réglages dans `C:\VirtualDisplayDriver`) ; placé à droite du principal, ou dessous | — |
| `%LOCALAPPDATA%\DCS-Tablette\installation.json` | ce que vous avez choisi à l'installation (votre configuration gardée, écran HDMI factice…), relu par le diagnostic | — |
| `Scripts\DCS-Tablette-Export.lua`, `Scripts\DCS-Tablette-Appareils.lua` | ajoutés | — |
| `Scripts\Export.lua` | une ligne ajoutée à la fin ; Tacview, SRS… intacts | `Export.lua.avant-tablette-<date>` |
| `Config\MonitorSetup\tablette.lua` | configuration d'écrans « Tablette DCS » | — |
| `Config\options.lua` | configuration d'écrans, résolution, fenêtré | `options.lua.avant-tablette` |
| Bureau | raccourci « DCS Tablette » | — |

Le script Lua n'accepte que les commandes des boutons affichés (une liste
blanche par appareil) et relâche tout bouton tenu plus de 5 secondes.

**Désinstaller** : DCS et DCS Tablette fermés, `Desinstaller.bat` retire tout et remet
l'affichage d'avant. Supprimer ensuite le dossier. L'écran virtuel reste
(Gestionnaire de périphériques → Cartes graphiques → Virtual Display Driver →
*Désinstaller l'appareil* pour le retirer).

## Appareil détecté ou choisi

En haut à gauche, le menu **Appareil** : en *Auto*, la page suit l'appareil
que DCS annonce (la pastille est verte quand DCS parle à la tablette). On
peut aussi y choisir son appareil à la main, pour préparer la page avant de
lancer la mission. Si l'appareil choisi n'est pas celui que DCS pilote, la
pastille passe à l'orange et les boutons sont coupés : d'un module à
l'autre, le même numéro désigne un tout autre bouton.

## Diagnostic

DCS Tablette vérifie tout ce dont la tablette a besoin, à son lancement puis
toutes les 10 secondes : dossier de DCS, scripts, écran virtuel, écrans et
réglages de DCS, DCS lancé, signal du script (avec la dernière ligne
`DCS-TABLETTE` de dcs.log), images, réseau du PC (Public ou Privé), tablette
connectée.

- **Sur le PC** : la liste « Vérification » dans la fenêtre au lancement,
  puis chaque changement, horodaté.
- **Sur la tablette** : toucher la pastille en haut à gauche, ou le badge
  « ⚠ n » qui apparaît quand quelque chose est à régler. *Vérifier*
  revérifie tout de suite.

Chaque point est *OK*, *réparé*, *en attente* (DCS pas lancé…), *à régler*
ou *manque*, avec la marche à suivre. Ce qui se répare sans risque l'est
tout seul, et c'est dit : scripts d'une ancienne version, écran virtuel
déplacé par une mise à jour de Windows, configuration d'écrans qui ne tombe
plus sur les écrans, DCS repassé en plein écran ou sur une autre
configuration (une fois DCS fermé : il réécrit ses réglages en quittant).
Rien n'est installé sans le demander : l'écran virtuel manquant, c'est
`Installer.bat`.

## Problèmes courants

D'abord, le diagnostic ci-dessus. Les cas les plus fréquents :

- **« DCS : pas de signal » alors que les écrans s'affichent** : les images
  viennent de l'écran, mais les boutons et le nom de l'appareil passent par
  le script de la tablette dans DCS. Le diagnostic montre la dernière ligne
  `DCS-TABLETTE` de `Saved Games\DCS\Logs\dcs.log` : le script y dit s'il
  est prêt, quel appareil il voit, ou pourquoi il ne peut pas démarrer.
  Aucune ligne : relancer `Installer.bat`, puis la mission.

- **La page ne s'ouvre pas sur l'iPad** : le Wi-Fi du PC est peut-être en
  réseau *Public* dans Windows ; le passer en *Privé*.
- **Écrans noirs** : relancer DCS après l'installation (il ne lit la
  configuration d'écrans qu'au démarrage) et vérifier dans Options → Système
  → Moniteurs que « Tablette DCS » est choisi.
- **Les écrans du cockpit couvrent la vue** : l'écran virtuel n'est plus à
  sa place (mise à jour de Windows ou du pilote graphique). DCS Tablette le
  remet tout seul ; quitter DCS et le relancer.
- **Le kneeboard de DCS tombe sur l'écran virtuel** : c'est voulu. Dans
  l'onglet Kneeboard de la tablette, « Kneeboard DCS sur » choisit où il
  apparaît quand vous l'ouvrez : *PC* (une fenêtre le recopie en bas à
  droite de l'écran principal) ou *Tablette* (elle bascule dessus, rien sur
  le PC). Si la tablette se déconnecte, il revient sur le PC au bout de 10 s.
- **La tablette montre une ancienne version après une mise à jour** : à
  partir de la 1.2.1 elle se recharge seule ; avant, fermer l'app (ou
  l'onglet) et la rouvrir.

## Depuis le code source

Python 3.12, Windows.

```bat
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python.exe scripts\installer_dcs.py
.venv\Scripts\python.exe scripts\configurer_ecrans_dcs.py --second-ecran
launch_tablette.bat
```

- Tests : `set PYTHONPATH=src` puis
  `.venv\Scripts\python.exe -m unittest tests.test_tablette`
- Sans DCS : `scripts\simuler_dcs_tablette.py [nom de l'appareil]` se fait
  passer pour le jeu.
- Construire le zip : `.venv\Scripts\python.exe scripts\construire_tablette.py`
- Ajouter un appareil : un fichier dans `src/tablette/appareils/`, puis
  `scripts\generer_lua_appareils.py`.

Fonctionnement détaillé, choix et pistes écartées : [docs/tablette.md](docs/tablette.md).

---

Outil communautaire, sans lien avec Eagle Dynamics. DCS World est une marque
d'Eagle Dynamics SA.
