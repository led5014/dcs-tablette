# DCS Tablette

Les écrans du cockpit de DCS World sur une tablette, avec leurs boutons sous
le doigt. La page s'adapte toute seule à l'appareil piloté et à l'écran qui
l'affiche : iPad, tablette Android, téléphone, navigateur d'un autre PC.

- **Écrans en direct** : DDI, MFD, MPD… recopiés depuis DCS, sans scintillement.
- **Boutons tactiles** : chaque appui est joué dans le cockpit, tant que le
  doigt est posé.
- **Planche avant du Hornet** redessinée : UFC tactile, IFEI, instruments de
  secours, voyants.
- **Kneeboard** : les pages de l'avion piloté lues directement dans les
  fichiers, nettes à toute taille — mission en cours (solo ou multijoueur),
  pages du module, les vôtres, planches de la carte — et celui de DCS en
  direct. Au choix, la touche kneeboard de DCS l'affiche sur le PC comme
  d'habitude, ou sur la tablette, qui bascule alors d'elle-même dessus.
- **Toutes les tailles d'écran** : la page ne propose que les dispositions
  qui restent confortables au doigt sur l'écran utilisé — un ou deux écrans
  sur un téléphone, trois sur une tablette en paysage, toute la planche sur
  un grand écran — et se réarrange quand on la fait pivoter.

Pas de Python à installer, rien sur internet : le serveur tourne sur le PC,
l'iPad s'y connecte par le Wi-Fi de la maison.

## Télécharger

Dernière version : **[Releases](../../releases/latest)** → `DCS-Tablette-x.y.z.zip`.

Le zip contient `DCS-Tablette.exe`, `Installer.bat`, `Desinstaller.bat` et un
`LISEZ-MOI.txt` qui reprend ce qui suit.

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

## Installation

### 1. Un second écran que personne ne regarde

DCS dessine les écrans exportés sur un écran : sans second écran, ils
recouvrent la vue. La solution gratuite est un écran virtuel :

1. Installer [Virtual Display Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver)
   avec *VDD Control*.
2. Windows → Paramètres → Système → Écran : régler l'écran virtuel à la taille
   de l'écran principal (par exemple 2560 × 1440), à la même fréquence, et le
   placer **à droite** du principal, **aligné en haut**.

Une prise HDMI factice fait la même chose.

### 2. Installer

1. Fermer DCS.
2. Extraire le zip là où il restera (par exemple dans Documents), puis
   double-cliquer **`Installer.bat`**. Il pose aussi un raccourci
   **DCS Tablette** sur le bureau.
3. Si Windows affiche « Windows a protégé votre ordinateur » : *Informations
   complémentaires* → *Exécuter quand même*. L'exécutable n'est pas signé ; il
   est construit à partir de ce dépôt (`scripts/construire_tablette.py`).

### 3. En vol

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
Essayée dans Chrome aux tailles des téléphones, tablettes et écrans de PC
courants ; un retour sur votre appareil est bienvenu.

## Ce que l'installation modifie

Uniquement dans `Saved Games\DCS`, jamais dans le dossier d'installation de
DCS (le contrôle d'intégrité du multijoueur n'est pas concerné) :

| Fichier | Changement | Copie gardée |
|---|---|---|
| `Scripts\DCS-Tablette-Export.lua`, `Scripts\DCS-Tablette-Appareils.lua` | ajoutés | — |
| `Scripts\Export.lua` | une ligne ajoutée à la fin ; Tacview, SRS… intacts | `Export.lua.avant-tablette-<date>` |
| `Config\MonitorSetup\tablette.lua` | configuration d'écrans « Tablette DCS » | — |
| `Config\options.lua` | configuration d'écrans, résolution, fenêtré | `options.lua.avant-tablette` |
| Bureau | raccourci « DCS Tablette » | — |

Le script Lua n'accepte que les commandes des boutons affichés (une liste
blanche par appareil) et relâche tout bouton tenu plus de 5 secondes.

**Désinstaller** : DCS fermé, `Desinstaller.bat` retire tout et remet
l'affichage d'avant. Supprimer ensuite le dossier.

## Appareil détecté ou choisi

En haut à gauche, le menu **Appareil** : en *Auto*, la page suit l'appareil
que DCS annonce (la pastille est verte quand DCS parle à la tablette). On
peut aussi y choisir son appareil à la main, pour préparer la page avant de
lancer la mission. Si l'appareil choisi n'est pas celui que DCS pilote, la
pastille passe à l'orange et les boutons sont coupés : d'un module à
l'autre, le même numéro désigne un tout autre bouton.

## Problèmes courants

- **« DCS : pas de signal » alors que les écrans s'affichent** : les images
  viennent de l'écran, mais les boutons et le nom de l'appareil passent par
  le script de la tablette dans DCS. Ouvrir `Saved Games\DCS\Logs\dcs.log`
  et chercher `DCS-TABLETTE` : le script y dit s'il est prêt, quel appareil
  il voit, ou pourquoi il ne peut pas démarrer. Aucune ligne : relancer
  `Installer.bat`, puis la mission.

- **La page ne s'ouvre pas sur l'iPad** : le Wi-Fi du PC est peut-être en
  réseau *Public* dans Windows ; le passer en *Privé*.
- **Écrans noirs** : relancer DCS après l'installation (il ne lit la
  configuration d'écrans qu'au démarrage) et vérifier dans Options → Système
  → Moniteurs que « Tablette DCS » est choisi.
- **Le kneeboard de DCS tombe sur l'écran virtuel** : c'est voulu. Dans
  l'onglet Kneeboard de la tablette, « Kneeboard DCS sur » choisit où il
  apparaît quand vous l'ouvrez : *PC* (une fenêtre le recopie en bas à
  droite de l'écran principal) ou *Tablette* (elle bascule dessus, rien sur
  le PC). Si la tablette se déconnecte, il revient sur le PC au bout de 10 s.

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
