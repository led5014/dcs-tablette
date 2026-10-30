"""DCS Tablette — les écrans du cockpit sur un iPad, et les doigts dessus.

Troisième programme du dépôt, indépendant des deux autres : il tourne
PENDANT le vol, comme Copilote, mais ne s'occupe ni de la tête ni de la voix.
Il sert une page web à la tablette et relaie chaque appui vers DCS par le
script `dcs_export/DCS-Tablette-Export.lua`.

Il n'importe ni `dcs_debrief` ni `copilote`, et aucun des deux ne l'importe.
"""

VERSION = "1.4.0"
