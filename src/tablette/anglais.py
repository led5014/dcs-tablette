"""Les textes en anglais, rangés sous leur texte français (la référence).

Une entrée par phrase française du code, telle qu'elle y est écrite, avec
ses `{valeurs}` : la traduction les reprend à sa place. Une phrase changée
dans le code doit l'être ici aussi : tests/test_tablette.py le vérifie.

Vocabulaire tenu partout : les menus de DCS et de Windows sous leur nom
anglais (Options → System → Monitors, Settings → System → Display),
« configuration d'écrans » = monitor setup, « écran virtuel » = virtual
display, « pastille » = status dot. Guillemets droits "…" pour « … ».
"""

# Ce que le serveur dit : diagnostic, erreurs, libellés, console du PC.
SERVEUR = {
    # ------------------------------------------------------------ __main__.py
    "DCS Tablette est installé dans {dossier} : c'est lui qui démarre.":
        "DCS Tablette is installed in {dossier}: starting that one.",
    "Première utilisation : installation.": "First run: installing.",
    "DCS Tablette démarre dans sa propre fenêtre. Appuie sur Entrée pour fermer celle-ci. ":
        "DCS Tablette is starting in its own window. Press Enter to close this one. ",
    "Stream (Discord, OBS) : partager l'écran principal, pas la fenêtre de DCS, qui comprend "
    "l'écran virtuel.":
        "Streaming (Discord, OBS): share the main display, not the DCS window, which includes "
        "the virtual display.",
    "Les captures sont recadrées d'elles-mêmes.": "Screenshots are cropped automatically.",
    "Essai local : {adresse}": "Local test: {adresse}",
    "Ouvrir sur l'iPad :": "Open on the iPad:",
    "<adresse de ce PC>": "<this PC's address>",
    "Diagnostic : ci-dessus, puis ce qui change ; sur la tablette, toucher la pastille en "
    "haut à gauche.":
        "Diagnostics: above, then whatever changes; on the tablet, tap the status dot at the "
        "top left.",
    "n'écouter que ce PC (essais sans iPad)": "listen on this PC only (tests without an iPad)",
    "ne pas recopier le kneeboard sur l'écran du PC": "don't mirror the kneeboard on the PC display",
    "ne pas demander à GitHub s'il existe une version plus récente":
        "don't ask GitHub whether a newer version exists",
    "ne pas recadrer les captures de DCS sur l'écran principal":
        "don't crop DCS screenshots to the main display",
    "langue de la fenêtre, retenue : fr, en, ou auto (celle de Windows)":
        "language of this window, remembered: fr, en, or auto (follow Windows)",
    "écran virtuel, scripts dans DCS, écrans de DCS": "virtual display, scripts in DCS, DCS displays",
    "sans second écran : les écrans en bas de la vue":
        "without a second display: cockpit displays at the bottom of the view",
    "retirer la tablette de DCS": "remove the tablet from DCS",
    "attendre Entrée avant de fermer la fenêtre": "wait for Enter before closing the window",
    # scripts/dcs_tablette_entry.py
    "Appuie sur Entrée pour fermer cette fenêtre.": "Press Enter to close this window.",

    # ------------------------------------------------------------ app.py
    "Hôte refusé : ouvrir la page par l'adresse IP du PC.":
        "Host refused: open the page using the PC's IP address.",
    "Tablette réglée sur {choisi}, DCS pilote {pilote} : boutons coupés":
        "Tablet set to {choisi}, DCS is flying {pilote}: buttons disabled",
    "pas de {panneau} sur {appareil}": "no {panneau} on {appareil}",
    "écran inconnu": "unknown display",
    "bouton inconnu sur cet écran": "unknown button on this display",
    "position inconnue : DCS ne l'a pas encore envoyée": "unknown position: DCS hasn't sent it yet",
    "basculé ({position})": "switched ({position})",
    "enfoncé": "pressed",
    "relâché": "released",
    "envoi impossible": "could not send",
    "DCS ne répond pas, ordre perdu": "DCS not responding, command lost",
    "touche inconnue": "unknown key",
    "sens : 1 ou -1": "sens: 1 or -1",
    "{appareil} : pages à tourner dans DCS ([ et ])": "{appareil}: turn the pages in DCS ([ and ])",
    "Kneeboard : page suivante": "Kneeboard: next page",
    "Kneeboard : page précédente": "Kneeboard: previous page",
    "ouvert : true ou false": "ouvert: true or false",
    "Kneeboard affiché dans DCS": "Kneeboard shown in DCS",
    "Kneeboard caché dans DCS": "Kneeboard hidden in DCS",
    "page introuvable": "page not found",
    "page disparue": "page gone",

    # ------------------------------------------------------------ appareils/
    "Autre appareil": "Other aircraft",
    "Appareil FC3": "FC3 aircraft",
    "Appareil FC3 (OTAN)": "FC3 aircraft (NATO)",
    "DDI gauche": "Left DDI",
    "DDI droit": "Right DDI",
    "MFCD gauche": "Left MFCD",
    "MFCD droit": "Right MFCD",
    "MFCD centre": "Center MFCD",
    "MFD gauche": "Left MFD",
    "MFD droit": "Right MFD",
    "MPCD gauche": "Left MPCD",
    "MPCD droit": "Right MPCD",
    "MPD gauche": "Left MPD",
    "MPD droit": "Right MPD",

    # ------------------------------------------------------------ instruments.py
    "HAUTEUR": "HEIGHT AGL",
    "MACH": "MACH",
    "INCIDENCE": "AOA",
    "TEMP. MOTEUR": "ENGINE TEMP",
    "CARBURANT": "FUEL",
    "TRAIN": "GEAR",
    "SORTI": "DOWN",
    "RENTRÉ": "UP",
    "EN MOUVEMENT": "IN TRANSIT",
    "VOLETS": "FLAPS",
    "AÉROFREINS": "SPEED BRAKE",

    # ------------------------------------------------------------ kneeboard.py
    "Kneeboard de l'avion": "Aircraft kneeboard",
    "Cartes : {carte}": "Charts: {carte}",

    # ------------------------------------------------------------ captures.py, miroir.py
    "Capture recadrée sur l'écran principal : {nom}": "Screenshot cropped to the main display: {nom}",
    "Recadrage des captures : passage ignoré": "Screenshot cropping: pass skipped",
    "Miroir du kneeboard arrêté": "Kneeboard mirror stopped",
    "Miroir du kneeboard : image ignorée": "Kneeboard mirror: frame skipped",

    # ------------------------------------------------------------ video.py
    "La configuration d'écrans a changé depuis le lancement de DCS, qui ne la relit qu'au "
    "démarrage : relance DCS.":
        "The monitor setup changed since DCS started, and DCS only reads it at startup: "
        "restart DCS.",
    "DCS n'est pas lancé, ou sa fenêtre est réduite.":
        "DCS isn't running, or its window is minimized.",
    "DCS est réglé en {largeur} × {hauteur} mais sa fenêtre ne fait que {fenetre_l} × "
    "{fenetre_h} : vérifie la résolution dans Options → Système, puis relance DCS.":
        "DCS is set to {largeur} × {hauteur} but its window is only {fenetre_l} × {fenetre_h}: "
        "check the resolution in Options → System, then restart DCS.",
    "{nom} sort de la fenêtre de DCS ({largeur} × {hauteur}) : la configuration d'écrans ne "
    "correspond pas à la résolution. Quitte DCS : DCS Tablette remet ses réglages, puis "
    "relance DCS.":
        "{nom} is outside the DCS window ({largeur} × {hauteur}): the monitor setup doesn't "
        "match the resolution. Quit DCS: DCS Tablette restores its settings, then restart DCS.",
    "La configuration d'écrans de DCS n'exporte pas {nom}.":
        "The DCS monitor setup doesn't export {nom}.",
    "Kneeboard fermé dans DCS : ouvre-le avec RShift+K (ou garde K enfoncé pour un coup "
    "d'œil).":
        "Kneeboard closed in DCS: open it with RShift+K (or hold K down for a quick look).",
    "Image noire : décoche « Plein écran » dans Options → Système de DCS (le mode fenêtré se "
    "capture).":
        "Black image: uncheck \"Full Screen\" in DCS Options → System (windowed mode can be "
        "captured).",

    # ------------------------------------------------------------ ecrans_dcs.py
    "Réglages de DCS introuvables (Config/options.lua).":
        "DCS settings not found (Config/options.lua).",
    "Réglages d'affichage de DCS illisibles.": "DCS display settings unreadable.",
    "options.lua : réglage « {cle} » introuvable.": "options.lua: setting \"{cle}\" not found.",
    "pas de copie des réglages d'avant la tablette.":
        "no copy of the settings from before the tablet.",
    "DCS utilise la configuration d'écrans « {choix} », qui n'exporte pas les écrans. Choisis "
    "« {nom} » dans Options → Système → Moniteurs, puis relance DCS.":
        "DCS uses the \"{choix}\" monitor setup, which doesn't export the displays. Choose "
        "\"{nom}\" in Options → System → Monitors, then restart DCS.",

    # ------------------------------------------------------------ diagnostic.py
    "OK": "OK",
    "RÉPARÉ": "FIXED",
    "ATTENTE": "WAITING",
    "À FAIRE": "TO DO",
    "MANQUE": "MISSING",
    "{titre} : {detail}": "{titre}: {detail}",
    "« {nom} »": "\"{nom}\"",
    "Vérification :": "Checks:",
    "vérification impossible ({type} : {erreur})": "check failed ({type}: {erreur})",
    "Diagnostic : vérification impossible ({type} : {erreur}).":
        "Diagnostics: check failed ({type}: {erreur}).",
    "non vérifié": "not checked",
    "non vérifié ({type} : {erreur})": "not checked ({type}: {erreur})",
    "Dossier de DCS": "DCS folder",
    "pas de réglages de DCS dans {dossier}": "no DCS settings in {dossier}",
    "Lancer DCS une fois, jusqu'au menu, le quitter, puis relancer DCS Tablette : il finit "
    "l'installation tout seul.":
        "Start DCS once, up to the main menu, quit it, then restart DCS Tablette: it finishes "
        "the installation by itself.",
    "Installation": "Installation",
    "DCS Tablette n'est pas installé dans DCS (ou vient d'être désinstallé)":
        "DCS Tablette isn't installed in DCS (or was just uninstalled)",
    "Lancer Installer.bat pour l'installer.": "Run Installer.bat to install it.",
    "Scripts dans DCS": "Scripts in DCS",
    "à jour, chargés par Export.lua": "up to date, loaded by Export.lua",
    "copie impossible ({erreur})": "copy failed ({erreur})",
    "Relancer Installer.bat.": "Run Installer.bat again.",
    "À la main : copier DCS-Tablette-Export.lua et DCS-Tablette-Appareils.lua dans Saved "
    "Games\\DCS\\Scripts, et ajouter à la fin d'Export.lua :":
        "By hand: copy DCS-Tablette-Export.lua and DCS-Tablette-Appareils.lua to Saved "
        "Games\\DCS\\Scripts, and add at the end of Export.lua:",
    "copiés dans Saved Games\\DCS\\Scripts : relancer la mission pour qu'ils servent":
        "copied to Saved Games\\DCS\\Scripts: restart the mission to use them",
    "copiés dans Saved Games\\DCS\\Scripts : ils serviront dès la prochaine mission":
        "copied to Saved Games\\DCS\\Scripts: they'll be used from the next mission",
    "Écran virtuel": "Virtual display",
    "mode essai : écrans du cockpit en bas de la vue":
        "test mode: cockpit displays at the bottom of the view",
    "pas utilisé : DCS exporte avec « {nom} »": "not used: DCS exports with \"{nom}\"",
    "Écrans de DCS": "DCS displays",
    "« {nom} » (la vôtre) : {nombre} écrans exportés": "\"{nom}\" (yours): {nombre} displays exported",
    "DCS n'est plus sur votre configuration « {nom} »":
        "DCS is no longer on your \"{nom}\" monitor setup",
    "Dans DCS : Options → Système → Moniteurs « {nom} », puis relancer DCS.":
        "In DCS: Options → System → Monitors \"{nom}\", then restart DCS.",
    "Ou relancer Installer.bat pour passer à « {nom} ».":
        "Or run Installer.bat again to switch to \"{nom}\".",
    "en attente de l'écran virtuel": "waiting for the virtual display",
    "en attente de l'écran virtuel, et la fenêtre de DCS ({largeur}×{hauteur}) recouvre "
    "{recouverts}":
        "waiting for the virtual display, and the DCS window ({largeur}×{hauteur}) covers "
        "{recouverts}",
    "Quitter DCS : DCS Tablette remet l'écran virtuel à sa place et règle DCS, puis relancer "
    "DCS.":
        "Quit DCS: DCS Tablette puts the virtual display back and sets up DCS, then restart "
        "DCS.",
    "Remettre d'abord l'écran virtuel (point « Écran virtuel ») : DCS Tablette règle "
    "ensuite DCS tout seul.":
        "First put the virtual display back (\"Virtual display\" item): DCS Tablette then sets "
        "up DCS by itself.",
    "en bas de la vue": "at the bottom of the view",
    "sur le second écran": "on the second display",
    "« {nom} » : {nombre} écrans {ou}": "\"{nom}\": {nombre} displays {ou}",
    "« {nom} » ne tombe plus sur les écrans : les écrans du cockpit sortent {ecran}":
        "\"{nom}\" no longer fits the displays: the cockpit displays fall outside {ecran}",
    "« {nom} » ne tombe plus sur les écrans : les écrans du cockpit sortent {ecran}, et la "
    "fenêtre de DCS ({largeur}×{hauteur}) recouvre {recouverts}":
        "\"{nom}\" no longer fits the displays: the cockpit displays fall outside {ecran}, "
        "and the DCS window ({largeur}×{hauteur}) covers {recouverts}",
    "de l'écran principal ({largeur}×{hauteur})": "the main display ({largeur}×{hauteur})",
    "de l'écran virtuel ({largeur}×{hauteur})": "the virtual display ({largeur}×{hauteur})",
    "du second écran ({largeur}×{hauteur})": "the second display ({largeur}×{hauteur})",
    "votre écran {largeur}×{hauteur}": "your {largeur}×{hauteur} display",
    "Quitter DCS : DCS Tablette la récrit tout seul, puis relancer DCS.":
        "Quit DCS: DCS Tablette rewrites it by itself, then restart DCS.",
    "« {nom} » écrite à la taille des écrans, écrans du cockpit {ou}":
        "\"{nom}\" written to fit the displays, cockpit displays {ou}",
    "Réglages de DCS": "DCS settings",
    "« {nom} », {largeur}×{hauteur}, {mode}": "\"{nom}\", {largeur}×{hauteur}, {mode}",
    "fenêtré": "windowed",
    "plein écran": "full screen",
    "plein écran : la tablette n'y voit rien": "full screen: the tablet can't see anything",
    "Dans DCS : Options → Système, décocher « Plein écran », puis relancer DCS.":
        "In DCS: Options → System, uncheck \"Full Screen\", then restart DCS.",
    "réglages illisibles ({erreur})": "settings unreadable ({erreur})",
    "Dans DCS : Options → Système → Moniteurs « {nom} », Résolution {largeur}×{hauteur}, "
    "« Plein écran » décoché, puis relancer DCS.":
        "In DCS: Options → System → Monitors \"{nom}\", Resolution {largeur}×{hauteur}, "
        "\"Full Screen\" unchecked, then restart DCS.",
    "Ou dans DCS : Options → Système → Moniteurs « {nom} », Résolution {largeur}×{hauteur}, "
    "« Plein écran » décoché, puis relancer DCS.":
        "Or in DCS: Options → System → Monitors \"{nom}\", Resolution {largeur}×{hauteur}, "
        "\"Full Screen\" unchecked, then restart DCS.",
    "remis sur {voulu} (il était sur {avant})": "set back to {voulu} (it was {avant})",
    "DCS est sur {avant}": "DCS is set to {avant}",
    "Quitter DCS : DCS Tablette remet ses réglages tout seul, puis relancer DCS.":
        "Quit DCS: DCS Tablette restores its settings by itself, then restart DCS.",
    "DCS": "DCS",
    "pas lancé": "not running",
    "lancé avant le dernier réglage des écrans": "started before the last display setup",
    "Quitter DCS et le relancer : il ne relit les écrans qu'au démarrage.":
        "Quit DCS and start it again: it only reads the monitor setup at startup.",
    "lancé": "running",
    "en cours de lancement": "starting",
    "Script de la tablette dans DCS": "Tablet script in DCS",
    "port UDP {port} déjà pris : DCS Tablette n'entend pas DCS":
        "UDP port {port} already in use: DCS Tablette can't hear DCS",
    "Une autre fenêtre DCS Tablette est sans doute ouverte : la fermer, puis relancer "
    "celle-ci.":
        "Another DCS Tablette window is probably open: close it, then restart this one.",
    "DCS parle à la tablette : {appareil}": "DCS is talking to the tablet: {appareil}",
    "pas dans un appareil": "not in an aircraft",
    "démarre avec la mission": "starts with the mission",
    "pas encore de mission : le script démarre avec elle":
        "no mission yet: the script starts with it",
    "rien sous DCS-TABLETTE dans dcs.log": "nothing under DCS-TABLETTE in dcs.log",
    "panne dans dcs.log : « {ligne} »": "error in dcs.log: \"{ligne}\"",
    "dernier mot dans dcs.log : « {ligne} »": "last line in dcs.log: \"{ligne}\"",
    "DCS lancé, pas de signal ; {vu}": "DCS running, no signal; {vu}",
    "Normal au menu de DCS : le script démarre avec la mission.":
        "Normal in the DCS main menu: the script starts with the mission.",
    "En mission et toujours rien : relancer la mission (les scripts ont pu changer depuis "
    "son lancement).":
        "In a mission and still nothing: restart the mission (the scripts may have changed "
        "since it started).",
    "Rien sous DCS-TABLETTE dans Saved Games\\DCS\\Logs\\dcs.log : Export.lua ne charge pas "
    "le script ; relancer Installer.bat, puis la mission.":
        "Nothing under DCS-TABLETTE in Saved Games\\DCS\\Logs\\dcs.log: Export.lua doesn't "
        "load the script; run Installer.bat again, then restart the mission.",
    "Images des écrans": "Display images",
    "aucune tablette n'en demande en ce moment": "no tablet is asking for them right now",
    "envoyées à la tablette": "sent to the tablet",
    "DCS pas lancé": "DCS not running",
    "Réseau du PC": "PC network",
    "le PC n'est relié à aucun réseau": "the PC isn't connected to any network",
    "Le brancher au Wi-Fi ou au câble de la maison : la tablette doit être sur le même "
    "réseau.":
        "Connect it to the home Wi-Fi or cable: the tablet must be on the same network.",
    "« {reseau} » est en réseau Public : Windows y bloque la tablette":
        "\"{reseau}\" is a Public network: Windows blocks the tablet on it",
    "Paramètres → Réseau et Internet → Wi-Fi (ou Ethernet) → « {reseau} » → Type de profil "
    "réseau : Privé.":
        "Settings → Network & internet → Wi-Fi (or Ethernet) → \"{reseau}\" → Network profile "
        "type: Private.",
    "{reseaux} en privé": "{reseaux} set to Private",
    "Tablette": "Tablet",
    "connectée ({adresse})": "connected ({adresse})",
    "plus de nouvelles depuis {secondes} s ({adresse}) : en veille ?":
        "no news for {secondes} s ({adresse}): asleep?",
    "aucune connectée pour l'instant": "none connected yet",
    "Sur la tablette, même Wi-Fi : ouvrir http://{adresse}:{port}":
        "On the tablet, same Wi-Fi: open http://{adresse}:{port}",
    "La page ne s'ouvre pas : réseau du PC en Privé (voir plus haut), et DCS Tablette "
    "autorisé dans le pare-feu : Sécurité Windows → Pare-feu et protection du réseau → "
    "Autoriser une application via le pare-feu → DCS-Tablette, case Privé cochée.":
        "Page won't open: PC network set to Private (see above), and DCS Tablette allowed "
        "through the firewall: Windows Security → Firewall & network protection → Allow an "
        "app through firewall → DCS-Tablette, Private box checked.",
    "Version": "Version",
    "{version} (pas de nouvelle vérifiée au lancement)": "{version} (no update check at startup)",
    "{nouvelle} disponible, vous avez la {version}": "{nouvelle} available, you have {version}",
    "Fermer DCS Tablette et le relancer : il se met à jour tout seul, réglages gardés. S'il "
    "n'y arrive pas, sa fenêtre dit pourquoi.":
        "Close DCS Tablette and start it again: it updates itself, settings kept. If it "
        "can't, its window says why.",
    "{version}, à jour": "{version}, up to date",

    # ------------------------------------------------------------ ecran_virtuel.py
    "À la main (détail dans LISEZ-MOI.txt, « À la main ») :":
        "By hand (details in README.txt, \"Manual setup\"):",
    "  1. Installer Virtual Display Driver : {adresse}":
        "  1. Install Virtual Display Driver: {adresse}",
    "     (« VDD Control », puis Install).": "     (\"VDD Control\", then Install).",
    "  2. Paramètres → Système → Écran : « Étendre ces affichages », écran virtuel":
        "  2. Settings → System → Display: \"Extend these displays\", virtual display",
    "     à la définition et à la fréquence du principal, glissé à DROITE du":
        "     at the main display's resolution and refresh rate, dragged to the RIGHT",
    "     principal, bords du HAUT alignés — ou DESSOUS, bords de GAUCHE alignés,":
        "     of the main one, TOP edges aligned — or BELOW it, LEFT edges aligned,",
    "     si un de vos écrans occupe déjà la droite.":
        "     if one of your displays already sits on the right.",
    "  3. Relancer Installer.bat : il vérifie et finit le reste.":
        "  3. Run Installer.bat again: it checks and finishes the rest.",
    "« {carte} » ({largeur}×{hauteur}, {frequence} Hz)":
        "\"{carte}\" ({largeur}×{hauteur}, {frequence} Hz)",
    "à droite du principal, aligné en haut": "right of the main display, top-aligned",
    "sous le principal, aligné à gauche": "below the main display, left-aligned",
    "{largeur}×{hauteur}, {frequence} Hz, {ou}": "{largeur}×{hauteur}, {frequence} Hz, {ou}",
    "Écran principal introuvable.": "Main display not found.",
    "L'écran principal est l'écran virtuel {ecran}.": "The main display is the virtual display {ecran}.",
    "Paramètres → Système → Écran : choisir l'écran qu'on regarde, puis":
        "Settings → System → Display: select the display you look at, then",
    "cocher « En faire mon écran principal », et relancer Installer.bat.":
        "check \"Make this my main display\", and run Installer.bat again.",
    "Aucun écran virtuel.": "No virtual display.",
    "Les écrans {ecrans} occupent la droite et le":
        "Displays {ecrans} take up the space to the right of and",
    "dessous de l'écran principal : la fenêtre de DCS les couvrirait, ils resteraient noirs.":
        "below the main display: the DCS window would cover them and they would stay black.",
    "Paramètres → Système → Écran : en glisser un à gauche ou au-dessus du principal,":
        "Settings → System → Display: drag one to the left of or above the main display,",
    "puis relancer Installer.bat. Ou, pour essayer sans : Installer.bat --essai.":
        "then run Installer.bat again. Or, to try without one: Installer.bat --essai.",
    "principal": "main",
    "virtuel": "virtual",
    "dupliqué ou déconnecté": "duplicated or disconnected",
    "à droite du principal": "right of the main display",
    "à droite du principal, décalé": "right of the main display, offset",
    "à gauche du principal": "left of the main display",
    "sous le principal": "below the main display",
    "sous le principal, décalé": "below the main display, offset",
    "au-dessus du principal": "above the main display",
    "Windows refuse ce réglage (code {code})": "Windows refuses this setting (code {code})",
    "Windows n'a pas appliqué le réglage (code {code})":
        "Windows did not apply the setting (code {code})",
    "{fichier} n'est pas le fichier attendu (empreinte différente) : rien n'est installé.":
        "{fichier} is not the expected file (different checksum): nothing installed.",
    "Virtual Display Driver est installé mais désactivé : réactivation.":
        "Virtual Display Driver is installed but disabled: enabling it.",
    "Réactivation refusée : {erreur}": "Enabling refused: {erreur}",
    "Virtual Display Driver est déjà installé et en marche.":
        "Virtual Display Driver is already installed and running.",
    "Téléchargement : {adresse}": "Downloading: {adresse}",
    "Téléchargement impossible : {erreur}": "Download failed: {erreur}",
    "Réglages de l'écran virtuel : {fichier} ({largeur}×{hauteur}, {frequence} Hz)":
        "Virtual display settings: {fichier} ({largeur}×{hauteur}, {frequence} Hz)",
    "Installation du pilote (Windows peut demander de confirmer l'éditeur)…":
        "Installing the driver (Windows may ask you to confirm the publisher)…",
    "NefCon n'a pas pu s'exécuter : {erreur}": "NefCon could not run: {erreur}",
    "Pilote installé ; Windows demande un redémarrage.":
        "Driver installed; Windows asks for a restart.",
    "Le pilote n'a pas été installé (NefCon : code {code}).":
        "The driver was not installed (NefCon: code {code}).",
    "Pilote installé.": "Driver installed.",
    "Autorisation administrateur refusée : rien n'a été installé.":
        "Administrator permission refused: nothing was installed.",
    "Lancement en administrateur impossible (erreur {erreur}).":
        "Could not start as administrator (error {erreur}).",
    "{ecran}, {ou}": "{ecran}, {ou}",
    "pas d'écran virtuel : {ecran}, choisi à l'installation":
        "no virtual display: {ecran}, chosen at install",
    "aucun : les écrans du cockpit iraient sur la vue":
        "none: the cockpit displays would land on the view",
    "Lancer Installer.bat : il propose de l'installer (répondre O) et le place.":
        "Run Installer.bat: it offers to install it (answer Y) and places it.",
    "{ecran} n'est pas à sa place": "{ecran} is out of place",
    "« Vérifier » pour réessayer de le remettre, ou relancer Installer.bat.":
        "\"Check\" to try putting it back again, or run Installer.bat again.",
    "À la main : Paramètres → Système → Écran, « Étendre ces affichages », {voulu}.":
        "By hand: Settings → System → Display, \"Extend these displays\", {voulu}.",
    "L'écran {ecran} est à droite du principal.": "Display {ecran} is right of the main one.",
    "L'écran {ecran} est sous le principal.": "Display {ecran} is below the main one.",
    "Si personne ne le regarde (prise HDMI factice), les écrans du cockpit":
        "If nobody looks at it (dummy HDMI plug), the cockpit displays",
    "peuvent aller dessus ; DCS le couvrira pendant le vol.":
        "can go there; DCS will cover it during the flight.",
    "Est-ce un écran que personne ne regarde ? [o/N] ": "Is it a display nobody looks at? [y/N] ",
    "Écran {ecran} gardé pour les écrans du cockpit.":
        "Display {ecran} kept for the cockpit displays.",
    "Cet écran reste à vous : un écran virtuel sera ajouté à côté.":
        "This display stays yours: a virtual display will be added alongside.",
    "Aucun écran virtuel. Il en faut un, que personne ne regarde, pour que":
        "No virtual display. One is needed, that nobody looks at, so that",
    "DCS y dessine les écrans exportés au lieu de les poser sur la vue.":
        "DCS draws the exported displays there instead of over the view.",
    "DCS Tablette peut installer Virtual Display Driver (gratuit, open source) :":
        "DCS Tablette can install Virtual Display Driver (free, open source):",
    "Windows demandera l'autorisation administrateur, puis peut-être de":
        "Windows will ask for administrator permission, then maybe to",
    "confirmer l'installation du pilote : accepter les deux.":
        "confirm the driver installation: accept both.",
    "Installer l'écran virtuel maintenant ? [O/n] ": "Install the virtual display now? [Y/n] ",
    "Écran virtuel non installé.": "Virtual display not installed.",
    "Le pilote est installé, mais aucun écran virtuel n'apparaît.":
        "The driver is installed, but no virtual display shows up.",
    "Redémarrer le PC, puis relancer Installer.bat.": "Restart the PC, then run Installer.bat again.",
    "L'écran virtuel est dupliqué ou déconnecté : passage en mode « Étendre ».":
        "The virtual display is duplicated or disconnected: switching to \"Extend\" mode.",
    "Écran virtuel {ecran} déjà en place, {ou}.": "Virtual display {ecran} already in place, {ou}.",
    "Windows n'a pas gardé la position demandée": "Windows did not keep the requested position",
    "Écran virtuel {ecran} non placé : {erreur}.": "Virtual display {ecran} not placed: {erreur}.",
    "À régler dans Paramètres → Système → Écran : {voulu}.":
        "To set in Settings → System → Display: {voulu}.",
    "Écran virtuel « {carte} » placé : {voulu}.": "Virtual display \"{carte}\" placed: {voulu}.",
    "(Un écran occupe déjà la droite du principal : l'écran virtuel va dessous.)":
        "(A display already sits right of the main one: the virtual display goes below.)",

    # ------------------------------------------------------------ installation.py
    "Copié : {chemin}": "Copied: {chemin}",
    "Export.lua charge déjà la tablette.": "Export.lua already loads the tablet.",
    "Copie de l'ancien Export.lua : {nom}": "Copy of the old Export.lua: {nom}",
    "Export.lua : ligne de la tablette ajoutée.": "Export.lua: tablet line added.",
    "Export.lua : ligne de la tablette retirée (copie : {nom}).":
        "Export.lua: tablet line removed (copy: {nom}).",
    "Supprimé : {chemin}": "Deleted: {chemin}",
    "Pas d'écran libre collé à droite ou sous l'écran principal.":
        "No free display right next to or below the main display.",
    "Il en faut un que personne ne regarde, pour que DCS y dessine les écrans":
        "One is needed that nobody looks at, so that DCS draws the exported",
    "exportés au lieu de les poser sur la vue :": "displays there instead of over the view:",
    "  - écran virtuel : Virtual Display Driver, gratuit — {adresse}":
        "  - virtual display: Virtual Display Driver, free — {adresse}",
    "  - ou une prise HDMI factice.": "  - or a dummy HDMI plug.",
    "Installer.bat installe et place l'écran virtuel lui-même. À la main :":
        "Installer.bat installs and places the virtual display itself. By hand:",
    "Paramètres → Système → Écran, « Étendre ces affichages », le glisser à":
        "Settings → System → Display, \"Extend these displays\", drag it to the",
    "droite du principal (bords du haut alignés) ou dessous (bords de gauche":
        "right of the main one (top edges aligned) or below it (left edges",
    "alignés), là où aucun autre écran ne se trouve, puis relancer l'installation.":
        "aligned), where no other display sits, then run the installation again.",
    "Inchangé : {chemin}": "Unchanged: {chemin}",
    "Écrit : {chemin}": "Written: {chemin}",
    "DCS déjà réglé : « {nom} », {largeur}×{hauteur}.":
        "DCS already set: \"{nom}\", {largeur}×{hauteur}.",
    "Réglages de DCS non modifiés ({erreur}). À régler à la main :":
        "DCS settings not changed ({erreur}). To set by hand:",
    "DCS réglé : « {nom} », {largeur}×{hauteur}, fenêtré (réglages d'origine gardés dans "
    "{copie}).":
        "DCS set: \"{nom}\", {largeur}×{hauteur}, windowed (original settings kept in {copie}).",
    "DCS est ouvert : il réécrira ses réglages en quittant. À régler dans DCS :":
        "DCS is open: it will rewrite its settings when it quits. To set in DCS:",
    "  Options → Système → Moniteurs : « {nom} »": "  Options → System → Monitors: \"{nom}\"",
    "  Résolution : {largeur}×{hauteur}, « Plein écran » décoché":
        "  Resolution: {largeur}×{hauteur}, \"Full Screen\" unchecked",
    "puis relancer DCS.": "then restart DCS.",
    "DCS est ouvert : ferme-le puis relance la désinstallation, ou choisis":
        "DCS is open: close it and run the uninstall again, or choose",
    "toi-même dans Options → Système → Moniteurs ta configuration d'avant":
        "yourself, in Options → System → Monitors, your previous monitor setup",
    "et ta résolution.": "and your resolution.",
    "Réglages de DCS non remis ({erreur}). Dans Options → Système, choisis":
        "DCS settings not restored ({erreur}). In Options → System, choose",
    "« 1 Screen » dans Moniteurs et ta résolution, puis relance la":
        "\"1 Screen\" in Monitors and your resolution, then run the",
    "désinstallation pour retirer « {nom} ».": "uninstall again to remove \"{nom}\".",
    "Affichage de DCS remis comme avant la tablette (d'après {copie}).":
        "DCS display restored as before the tablet (from {copie}).",
    "Les écrans du cockpit de DCS sur la tablette": "DCS cockpit displays on the tablet",
    "PowerShell n'a rien écrit": "PowerShell wrote nothing",
    "Entrée dans Applications installées non mise à jour ({erreur}).":
        "Installed apps entry not updated ({erreur}).",
    "Raccourci « DCS Tablette » ajouté au menu Démarrer.":
        "\"DCS Tablette\" shortcut added to the Start menu.",
    "DCS Tablette est ouvert. Ferme sa fenêtre, puis appuie sur Entrée (ou tape p pour "
    "passer) : ":
        "DCS Tablette is open. Close its window, then press Enter (or type p to pass): ",
    "Programme installé dans {dossier}.": "Program installed in {dossier}.",
    "Le dossier extrait du zip ne sert plus : il peut être supprimé.":
        "The folder extracted from the zip is no longer needed: it can be deleted.",
    "Programme non copié dans {dossier} ({erreur}) : il reste ici, {source}.":
        "Program not copied to {dossier} ({erreur}): it stays here, {source}.",
    "Raccourci sur le bureau non créé ({erreur}).": "Desktop shortcut not created ({erreur}).",
    "Raccourci dans le menu Démarrer non créé ({erreur}).":
        "Start menu shortcut not created ({erreur}).",
    "Entrée dans Applications installées non créée ({erreur}).":
        "Installed apps entry not created ({erreur}).",
    "Dossier de DCS introuvable ({dossier}).": "DCS folder not found ({dossier}).",
    "Lance DCS une fois pour qu'il le crée, puis recommence.":
        "Start DCS once so it creates it, then try again.",
    "Dossier de DCS : {dossier}": "DCS folder: {dossier}",
    "Vos écrans :": "Your displays:",
    "(illisibles)": "(unreadable)",
    "DCS : configuration « {nom} », {largeur}×{hauteur}, {mode}":
        "DCS: \"{nom}\" monitor setup, {largeur}×{hauteur}, {mode}",
    "DCS : {erreur}": "DCS: {erreur}",
    "DCS exporte déjà {nombre} écrans du cockpit avec votre configuration « {nom} » : "
    "{zones}.":
        "DCS already exports {nombre} cockpit displays with your \"{nom}\" monitor setup: "
        "{zones}.",
    "La tablette peut les prendre là où ils sont, sans toucher à vos écrans ni à DCS.":
        "The tablet can take them where they are, without touching your displays or DCS.",
    "Garder votre configuration ? [O/n] ": "Keep your monitor setup? [Y/n] ",
    "{etape}/{etapes}  Écran virtuel": "{etape}/{etapes}  Virtual display",
    "  Sans écran pour eux, la tablette marche quand même en mode essai : les":
        "  Without a display for them, the tablet still works in test mode: the",
    "  écrans du cockpit sont dessinés en bas de la vue, par-dessus le cockpit.":
        "  cockpit displays are drawn at the bottom of the view, over the cockpit.",
    "  Passer en mode essai ? [o/N] ": "  Switch to test mode? [y/N] ",
    "{etape}/{etapes}  Scripts de la tablette": "{etape}/{etapes}  Tablet scripts",
    "{etape}/{etapes}  Écrans de DCS": "{etape}/{etapes}  DCS displays",
    "  Votre configuration « {nom} » est gardée : rien à changer.":
        "  Your \"{nom}\" monitor setup is kept: nothing to change.",
    "  Mais DCS est en plein écran, que la tablette ne voit pas : dans DCS,":
        "  But DCS is in full screen, which the tablet can't see: in DCS,",
    "  Options → Système, décocher « Plein écran », puis relancer DCS.":
        "  Options → System, uncheck \"Full Screen\", then restart DCS.",
    "  Écran virtuel pas prêt : la configuration d'écrans de DCS attendra.":
        "  Virtual display not ready: the DCS monitor setup will wait.",
    "  Relancer Installer.bat une fois l'écran virtuel en place.":
        "  Run Installer.bat again once the virtual display is in place.",
    "  DCS est ouvert. Ferme-le, puis appuie sur Entrée (ou tape p pour passer) : ":
        "  DCS is open. Close it, then press Enter (or type p to pass): ",
    "« DCS Tablette » (bureau ou menu Démarrer)": "\"DCS Tablette\" (desktop or Start menu)",
    "Installation terminée. DCS Tablette démarre dans sa fenêtre : ouvre sur la tablette "
    "l'adresse qu'il affiche. Les fois suivantes, lance {programme}.":
        "Installation complete. DCS Tablette is starting in its window: open the address it "
        "shows on the tablet. Next time, start {programme}.",
    "Installation terminée. Lance {programme} et ouvre sur la tablette l'adresse qu'il "
    "affiche.":
        "Installation complete. Start {programme} and open the address it shows on the "
        "tablet.",
    "Scripts installés ; les écrans restent à régler (voir ci-dessus, et LISEZ-MOI.txt, « À "
    "la main »).":
        "Scripts installed; the displays still need setting up (see above, and README.txt, "
        "\"Manual setup\").",
    "  DCS Tablette est encore ouvert. Ferme sa fenêtre, puis appuie sur Entrée (ou tape p "
    "pour passer) : ":
        "  DCS Tablette is still open. Close its window, then press Enter (or type p to "
        "pass): ",
    "Retiré de Paramètres → Applications installées.": "Removed from Settings → Installed apps.",
    "Rien à retirer : la tablette n'était pas installée.":
        "Nothing to remove: the tablet wasn't installed.",
    "Le programme s'efface dès que cette fenêtre se ferme.":
        "The program deletes itself as soon as this window closes.",
    "On peut maintenant supprimer le dossier de DCS Tablette.":
        "The DCS Tablette folder can now be deleted.",
    "L'écran virtuel reste installé : il peut servir à autre chose. Pour le retirer :":
        "The virtual display stays installed: it may be useful for something else. To remove it:",
    "Gestionnaire de périphériques → Cartes graphiques → Virtual Display Driver,":
        "Device Manager → Display adapters → Virtual Display Driver,",
    "clic droit → Désinstaller l'appareil.": "right-click → Uninstall device.",
    "Appuie sur Entrée pour fermer cette fenêtre. ": "Press Enter to close this window. ",

    # ------------------------------------------------------------ mise_a_jour.py
    "Nouvelle version : DCS Tablette {nouvelle} (vous avez {version}).":
        "New version: DCS Tablette {nouvelle} (you have {version}).",
    "Mise à jour, réglages gardés. Téléchargement ({taille} Mo)…":
        "Updating, settings kept. Downloading ({taille} MB)…",
    "Mise à jour, réglages gardés. Téléchargement…": "Updating, settings kept. Downloading…",
    "Mise à jour impossible : {erreur}. On continue avec la {version}.":
        "Update failed: {erreur}. Carrying on with {version}.",
    "À la main : {adresse}": "By hand: {adresse}",
    "Fichier vérifié. DCS Tablette se ferme, se met à jour et se relance tout seul.":
        "File verified. DCS Tablette closes, updates and restarts by itself.",
    "le fichier téléchargé n'est pas celui publié (empreinte différente)":
        "the downloaded file is not the published one (different checksum)",
    "{exe} absent du zip": "{exe} missing from the zip",
    # Le script de remplacement (REMPLACER) : ses lignes title et echo, en ASCII.
    "DCS Tablette - mise a jour": "DCS Tablette - update",
    "Mise a jour de DCS Tablette : on attend qu'il soit ferme...":
        "Updating DCS Tablette: waiting for it to close...",
    "Copie des nouveaux fichiers...": "Copying the new files...",
    "La copie a echoue. Extraire a la main le zip telecharge :":
        "The copy failed. Extract the downloaded zip by hand:",
    'dans "%DT_CIBLE%"': 'into "%DT_CIBLE%"',
}

# La page de la tablette (web/app.js, web/index.html), servie par /textes.js.
PAGE = {
    # ------------------------------------------------------------ index.html
    "Appareil": "Aircraft",
    "Disposition": "Layout",
    "Siège": "Seat",
    "Plein écran": "Full screen",
    "Écrans du cockpit": "Cockpit displays",
    "Carnet": "Book",
    "Page précédente": "Previous page",
    "Page suivante": "Next page",
    "Kneeboard ouvert dans DCS : afficher sur": "Kneeboard opened in DCS: show on",
    "Kneeboard DCS sur": "DCS kneeboard on",
    "Tablette": "Tablet",
    "Kneeboard de DCS en direct": "Live DCS kneeboard",
    "En attente du kneeboard de DCS…": "Waiting for the DCS kneeboard…",
    "Page de kneeboard": "Kneeboard page",
    "Aucune page à afficher.": "No page to show.",
    "Dépose des images PNG ou JPG dans": "Drop PNG or JPG images into",
    "(ou son sous-dossier au nom de l'appareil), ou vole une mission qui en embarque.":
        "(or its subfolder named after the aircraft), or fly a mission that carries some.",
    "Diagnostic": "Diagnostics",
    "Vérifier": "Check",
    "Fermer": "Close",
    "Dernières réparations et alertes": "Latest repairs and alerts",

    # ------------------------------------------------------------ dispositions, sièges
    "{ecran} + instr.": "{ecran} + instr.",
    "Secours": "Standby",
    "{nombre} écrans": "{nombre} displays",
    "Planche": "Panel",
    "Instruments": "Instruments",
    "Écrans": "Displays",
    "Kneeboard": "Kneeboard",
    "Cet appareil": "This aircraft",
    "{appareil} : pas d'écran à reprendre. Le kneeboard reste disponible.":
        "{appareil}: no displays to show. The kneeboard is still available.",
    "Pilote": "Pilot",

    # ------------------------------------------------------------ images et réglages des écrans
    "Serveur injoignable": "Server unreachable",
    "Pas d'image": "No image",
    "Image illisible": "Unreadable image",
    "En attente de l'image…": "Waiting for the image…",
    "{bouton} : {raison}": "{bouton}: {raison}",
    "non transmis": "not sent",
    "Luminosité": "Brightness",
    "Contraste": "Contrast",
    "Netteté": "Sharpness",
    "Économe": "Economy",
    "Normale": "Normal",
    "Fine": "Fine",
    "Très fine": "Very fine",
    "Aucun": "None",
    "Niveaux auto": "Auto levels",
    "Noir et blanc": "Black and white",
    "Inversé": "Inverted",
    "Vert": "Green",
    "Ambre": "Amber",
    "Rouge nuit": "Night red",
    "{ecran} : luminosité (toucher pour tous les réglages)":
        "{ecran}: brightness (tap for all settings)",
    "Luminosité {niveau}": "Brightness {niveau}",
    "Réglages de {ecran}": "{ecran} settings",
    "{reglage} : moins": "{reglage}: less",
    "{reglage} : plus": "{reglage}: more",
    "Définition": "Resolution",
    "Filtre": "Filter",
    "DCS dessine cet écran en {taille} px.": "DCS draws this display at {taille} px.",
    "Agrandi et affiné par le PC : plus net, plus lourd pour le Wi-Fi.":
        "Upscaled and sharpened by the PC: crisper, heavier on the Wi-Fi.",
    "Image allégée, pour un Wi-Fi faible.": "Lighter image, for weak Wi-Fi.",
    "Niveaux auto : le plus sombre au noir, le plus clair au blanc, image par image — pour un "
    "TGP ou un FLIR.":
        "Auto levels: darkest to black, brightest to white, frame by frame — for a TGP or "
        "FLIR.",
    "Inversé : noir chaud ↔ blanc chaud.": "Inverted: black hot ↔ white hot.",
    "Par défaut": "Default",
    "Pareil sur les autres écrans": "Same on the other displays",
    "Copié sur {ecrans}": "Copied to {ecrans}",

    # ------------------------------------------------------------ UFC, secours, instruments
    "{molette} : cran suivant": "{molette}: next step",
    "{molette} : cran précédent": "{molette}: previous step",
    "VITESSE {unite}": "AIRSPEED {unite}",
    "ALTITUDE {unite}": "ALTITUDE {unite}",
    "HORIZON": "ATTITUDE",
    "VARIO {unite}": "VSI {unite}",
    "SONDE ft": "RADAR ALT ft",
    "HYD G / D ×1000 psi": "HYD L / R ×1000 psi",
    "FREIN ×1000 psi": "BRAKE ×1000 psi",
    "gauche": "left",
    "droite": "right",
    "VIRAGE": "TURN",
    "CAP": "HEADING",
    "RÉGIME % G / D": "RPM % L / R",
    "RÉGIME %": "RPM %",
    "En attente des données de vol (DCS en mission).":
        "Waiting for flight data (DCS in a mission).",
    "Données de vol coupées par le serveur multijoueur : il interdit l'export de son "
    "appareil.":
        "Flight data blocked by the multiplayer server: it forbids exporting its aircraft.",
    # Les voyants du Hornet (planche.VOYANTS) dont le nom est en français.
    "FIRE G": "L FIRE",
    "FIRE D": "R FIRE",
    "TRAIN": "GEAR",
    "AOA HAUT": "AOA HIGH",
    "AOA CENTRE": "AOA CENTER",
    "AOA BAS": "AOA LOW",
    "ALT BASSE": "LOW ALT",

    # ------------------------------------------------------------ état de DCS, appareil
    "DCS : pas de signal": "DCS: no signal",
    "DCS : pas dans un appareil": "DCS: not in an aircraft",
    "DCS : {appareil}": "DCS: {appareil}",
    "{appareil} (pas de profil, kneeboard seul)": "{appareil} (no profile, kneeboard only)",
    "Tablette réglée sur {choisi}, DCS pilote {pilote} : boutons coupés":
        "Tablet set to {choisi}, DCS is flying {pilote}: buttons disabled",
    "serveur injoignable": "server unreachable",
    "Serveur de la tablette injoignable": "Tablet server unreachable",
    "{appareil} — DCS : {pilote}": "{appareil} — DCS: {pilote}",
    "Kneeboard DCS (en direct)": "DCS kneeboard (live)",

    # ------------------------------------------------------------ diagnostic
    "réparé": "fixed",
    "en attente": "waiting",
    "à régler": "action needed",
    "manque": "missing",
    "Diagnostic : {nombre} point à régler": "Diagnostics: {nombre} item needs action",
    "Diagnostic : {nombre} points à régler": "Diagnostics: {nombre} items need action",
    "vérifié à {heure}": "checked at {heure}",
    "pas encore vérifié": "not checked yet",
    "{titre} : {detail}": "{titre}: {detail}",
    "PC injoignable : la fenêtre DCS Tablette est-elle ouverte, et le PC sur le même Wi-Fi ?":
        "PC unreachable: is the DCS Tablette window open, and is the PC on the same Wi-Fi?",
    "vérification…": "checking…",
}
