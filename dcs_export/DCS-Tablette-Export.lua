--[[
  DCS Tablette — joue dans le cockpit les appuis faits sur la tablette.

  Le serveur de la tablette (src/tablette) envoie un datagramme UDP par
  appui et par relâchement : "<appareil> <commande> <valeur>", par exemple
  "35 3011 1" pour enfoncer le bouton 1 du DDI gauche du Hornet, puis
  "35 3011 0" pour le relâcher. Ce script les lit au début de chaque image et
  appelle `performClickableAction` : exactement ce que fait un clic de souris
  sur le bouton, donc valable en multijoueur comme en solo.

  En retour, il annonce une fois par seconde quel appareil est piloté : le
  serveur choisit le profil correspondant, et la tablette se reconstruit.
  Pour les appareils dont le profil le prévoit, il envoie aussi ce que la
  tablette redessine elle-même, faute de zone d'export pour ces éléments :
  - "ind <n>\n<texte>" : le texte d'un indicateur (list_indication), à
    chaque changement — l'UFC et l'IFEI du Hornet ;
  - "arg <n>=<v> …" : la position d'aiguilles et l'état de voyants
    (get_argument_value du tableau de bord).

  RÈGLE DE SÛRETÉ ABSOLUE : comme DCS-Debrief-Export.lua, ce script est
  chaîné avec ceux de Tacview et de SRS dans le même Export.lua. Tout appel
  au jeu est protégé par pcall, et la moindre anomalie désactive proprement
  ce script sans toucher aux autres.

  Garde-fous, parce qu'un ordre reçu du réseau agit sur le cockpit :
  - on n'écoute que 127.0.0.1 : seul le serveur de ce PC peut nous parler ;
  - on n'accepte que ce que la liste blanche de l'appareil PILOTÉ autorise
    (DCS-Tablette-Appareils.lua, générée depuis les profils du serveur) : le
    même numéro désigne tout autre chose dans un autre module, et un
    appareil sans profil ne reçoit rien.
--]]

local DCSTablette = {}

local PORT_ORDRES = 7790      -- écouté ici : le serveur y envoie les appuis
local PORT_ETAT = 7791        -- écouté par le serveur : on y annonce l'appareil
local PERIODE_ETAT_S = 1.0
local PERIODE_TEXTE_S = 0.1       -- l'UFC suit la frappe sans retard sensible
local PERIODE_AIGUILLES_S = 0.05  -- 20 fois par seconde : aiguilles fluides
-- Les textes ne partent qu'à chaque changement ; on les renvoie quand même
-- de temps en temps, pour un serveur qui vient de (re)démarrer.
local PERIODE_RAPPEL_TEXTE_S = 2.0

-- Un bouton enfoncé dont le relâchement n'arrive jamais (iPad mis en veille,
-- Wi-Fi coupé au milieu d'un appui) resterait tenu dans le cockpit. Passé ce
-- délai, on le relâche nous-mêmes : aucun bouton repris par la tablette ne se
-- garde enfoncé aussi longtemps.
local LIMITE_APPUI_S = 5.0

-- Démarrage manqué (port pris, LuaSocket pas encore là, LuaExportStart
-- jamais reçu) : on réessaie pendant le vol plutôt que d'abandonner la
-- mission entière. Vu en vrai : un vol entier sans un mot, et rien pour
-- savoir pourquoi — d'où aussi le journal (dcs.log, « DCS-TABLETTE »).
local REESSAI_S = 5.0

local socket = nil
local ecoute = nil
local envoi = nil
local prochainEssai = 0
local dits = {}               -- messages de panne déjà écrits dans dcs.log
local appareil = nil
local profil = nil
local prochainEtat = 0
local prochainTexte = 0
local prochainRappel = 0
local prochainesAiguilles = 0
local derniersTextes = {}
local enfonces = {}           -- "35:3011" -> { appareil, commande, depuis }

-- LuaSocket est livré avec DCS, mais l'environnement d'export ne l'a pas
-- toujours dans ses chemins de recherche : même démarche que le script de
-- débrief, qui la tient elle-même de SRS et de Tacview. Sans lui, rien
-- n'est possible ici et le script se met en retrait.
local function obtenirSocket()
  local function tenter()
    local ok, s = pcall(require, "socket")
    if ok and type(s) == "table" and type(s.udp) == "function" then
      return s
    end
    return nil
  end
  local s = tenter()
  if not s then
    pcall(function()
      local lfs = require("lfs")
      local racine = lfs.currentdir()
      package.path = package.path .. ";" .. racine .. "/LuaSocket/?.lua"
      package.cpath = package.cpath .. ";" .. racine .. "/LuaSocket/?.dll;"
        .. racine .. "/bin/?.dll"
    end)
    s = tenter()
  end
  return s
end
socket = obtenirSocket()

-- La liste blanche par appareil, posée à côté de ce script. Sans elle, le
-- script annonce l'appareil mais n'agit sur rien.
pcall(function()
  local lfs = require("lfs")
  dofile(lfs.writedir() .. "Scripts/DCS-Tablette-Appareils.lua")
end)
local APPAREILS = type(TABLETTE_APPAREILS) == "table" and TABLETTE_APPAREILS or {}

-- ---------------------------------------------------------------------------
-- Utilitaires
-- ---------------------------------------------------------------------------

--- Appel protégé : retourne nil plutôt que d'interrompre l'export.
local function sur(f, ...)
  local ok, res = pcall(f, ...)
  if ok then return res end
  return nil
end

--- Une ligne dans dcs.log, sous « DCS-TABLETTE » : ce que fait le script,
--- et surtout pourquoi il ne fait rien quand c'est le cas.
local function journal(message, erreur)
  pcall(function()
    log.write("DCS-TABLETTE", erreur and log.ERROR or log.INFO, message)
  end)
end

--- Une panne n'est écrite qu'une fois par mission : on réessaie toutes les
--- 5 s, le journal n'a pas à le répéter.
local function panne(message)
  if dits[message] then return end
  dits[message] = true
  journal(message, true)
end

local function horloge()
  if socket then return socket.gettime() end
  return os.clock()
end

local function fermer()
  if ecoute then pcall(function() ecoute:close() end) end
  if envoi then pcall(function() envoi:close() end) end
  ecoute, envoi = nil, nil
end

--- Appuie ou relâche un bouton, comme un clic de souris dans le cockpit.
local function jouer(dispositif, commande, valeur)
  local device = sur(GetDevice, dispositif)
  if not device then return end
  pcall(function() device:performClickableAction(commande, valeur) end)
end

local function envoyer(message)
  pcall(function() envoi:sendto(message, "127.0.0.1", PORT_ETAT) end)
end

--- Dit au serveur quel appareil est piloté ("-" : aucun), et retient son
--- profil : changer d'avion change la liste blanche.
local function annoncer()
  local self_ = sur(LoGetSelfData)
  local nom = self_ and self_.Name or nil
  if nom ~= appareil then
    appareil = nom
    profil = nom and APPAREILS[nom] or nil
    derniersTextes = {}
    if nom then
      journal("appareil pilote : " .. nom
        .. (profil and "" or " (sans profil : kneeboard seulement)"))
    else
      journal("aucun appareil pilote (hors cockpit, ou export de l'appareil "
        .. "interdit par le serveur)")
    end
  end
  envoyer("etat " .. tostring(appareil or "-"))
end

--- Texte des indicateurs du profil, seulement s'il a changé.
local function envoyerTextes()
  for _, id in ipairs(profil.textes or {}) do
    local texte = sur(list_indication, id)
    if texte and texte ~= derniersTextes[id] then
      derniersTextes[id] = texte
      envoyer("ind " .. id .. "\n" .. texte)
    end
  end
end

--- Position des aiguilles et état des voyants du profil, en une ligne.
local function envoyerAiguilles()
  local liste = profil.arguments or {}
  if #liste == 0 then return end
  local panneau = sur(GetDevice, 0)
  if not panneau then return end
  local morceaux = {}
  for _, n in ipairs(liste) do
    local ok, v = pcall(function() return panneau:get_argument_value(n) end)
    if ok and type(v) == "number" then
      morceaux[#morceaux + 1] = string.format("%d=%.4f", n, v)
    end
  end
  envoyer("arg " .. table.concat(morceaux, " "))
end

--- Un ordre reçu : vérifié entièrement contre le profil avant de toucher au
--- cockpit.
-- Afficher ou cacher le kneeboard de DCS, pour le montrer sur la tablette
-- sans toucher au clavier : la commande du coup d'œil (touche K,
-- iCommandPlaneShowKneeboard), +1 l'affiche, -1 le cache — et non la bascule
-- de RShift+K, qui inverserait à l'aveugle. Commune à tous les appareils ;
-- seules ces deux valeurs passent.
local KNEEBOARD_AFFICHER = 1587

local function traiter(message, maintenant)
  local sens = tostring(message):match("^kneeboard (%-?1)%s*$")
  if sens then
    pcall(LoSetCommand, KNEEBOARD_AFFICHER, tonumber(sens))
    return
  end
  local d, c, v = tostring(message):match("^(%d+) (%d+) (%-?[%d%.]+)%s*$")
  d, c, v = tonumber(d), tonumber(c), tonumber(v)
  if not d or not c or not v or not profil then return end
  local pages = profil.pages and profil.pages[d]
  if pages and pages[c] then
    -- Pages du kneeboard : un appui seul, ce n'est pas un bouton qu'on tient.
    if v == 1 then jouer(d, c, 1) end
    return
  end
  local molettes = profil.molettes and profil.molettes[d]
  if molettes and molettes[c] then
    -- Un cran, dans un sens ou dans l'autre : rien d'autre n'est accepté.
    if math.abs(math.abs(v) - molettes[c]) < 1e-6 then jouer(d, c, v) end
    return
  end
  local boutons = profil.boutons and profil.boutons[d]
  if not (boutons and boutons[c]) or (v ~= 0 and v ~= 1) then return end
  local cle = d .. ":" .. c
  if v == 1 then
    enfonces[cle] = { d, c, maintenant }
  else
    enfonces[cle] = nil
  end
  jouer(d, c, v)
end

-- ---------------------------------------------------------------------------
-- Points d'entrée DCS
-- ---------------------------------------------------------------------------

--- Ouvre ce qui manque encore : l'envoi (annonce de l'appareil, textes,
--- aiguilles) et l'écoute des appuis. Les deux sont indépendants : un port
--- d'écoute pris n'empêche pas d'annoncer l'appareil, et la tablette garde
--- le bon profil même quand ses boutons ne peuvent pas agir.
local function demarrer()
  if not socket then socket = obtenirSocket() end
  if not socket then
    panne("LuaSocket introuvable : la tablette ne recoit rien de DCS")
    return
  end
  if not envoi then
    local ok = pcall(function()
      local s = socket.udp()
      s:settimeout(0)
      envoi = s
    end)
    if not ok then
      panne("envoi UDP impossible : la tablette ne recoit rien de DCS")
    end
  end
  if not ecoute then
    local ok, err = pcall(function()
      local s = socket.udp()
      -- setsockname ne lève pas : il rend nil et un message.
      local lie, e = s:setsockname("127.0.0.1", PORT_ORDRES)
      if not lie then
        pcall(function() s:close() end)
        error(e)
      end
      s:settimeout(0)
      ecoute = s
    end)
    if ok then
      journal("pret : appuis de la tablette ecoutes sur 127.0.0.1:" .. PORT_ORDRES)
    else
      panne("port " .. PORT_ORDRES .. " indisponible (" .. tostring(err) .. ") : "
        .. "boutons de la tablette inactifs, nouvel essai toutes les 5 s")
    end
  end
end

function DCSTablette.start()
  dits = {}
  appareil = nil
  prochainEssai = 0
  demarrer()
end

function DCSTablette.frame()
  local maintenant = horloge()
  if (not envoi or not ecoute) and maintenant >= prochainEssai then
    prochainEssai = maintenant + REESSAI_S
    demarrer()
  end
  if not envoi then return end
  if maintenant >= prochainEtat then
    prochainEtat = maintenant + PERIODE_ETAT_S
    annoncer()
  end
  -- Lecture non bloquante : sans ordre en attente, receive rend nil aussitôt.
  -- La borne évite qu'un flot anormal de datagrammes retienne l'image.
  for _ = 1, (ecoute and 10 or 0) do
    local message = ecoute:receive()
    if not message then break end
    traiter(message, maintenant)
  end
  for cle, e in pairs(enfonces) do
    if maintenant - e[3] > LIMITE_APPUI_S then
      enfonces[cle] = nil
      jouer(e[1], e[2], 0)
    end
  end
  if not profil then return end
  if maintenant >= prochainRappel then
    prochainRappel = maintenant + PERIODE_RAPPEL_TEXTE_S
    derniersTextes = {}
  end
  if maintenant >= prochainTexte then
    prochainTexte = maintenant + PERIODE_TEXTE_S
    envoyerTextes()
  end
  if maintenant >= prochainesAiguilles then
    prochainesAiguilles = maintenant + PERIODE_AIGUILLES_S
    envoyerAiguilles()
  end
end

function DCSTablette.stop()
  for _, e in pairs(enfonces) do
    jouer(e[1], e[2], 0)
  end
  enfonces = {}
  fermer()
end

journal("charge (LuaSocket : " .. (socket and "oui" or "pas encore") .. ")")

-- Chaînage : on conserve les fonctions déjà installées par Tacview, SRS et
-- le script de débrief. Ne JAMAIS écraser sans rappeler l'ancienne, sous
-- peine de casser leur export.
local precedentStart = LuaExportStart
local precedentAvantImage = LuaExportBeforeNextFrame
local precedentStop = LuaExportStop

LuaExportStart = function()
  if precedentStart then pcall(precedentStart) end
  pcall(DCSTablette.start)
end

-- Ici, à chaque image, et non au rendez-vous programmé du script de débrief.
--
-- Le débrief relève un état deux fois par seconde : un rendez-vous lui suffit.
-- Un appui sur la tablette doit, lui, arriver dans le cockpit tout de suite ;
-- attendre le prochain rendez-vous ajouterait jusqu'à une demi-seconde à
-- chaque bouton. Le travail par image reste une lecture non bloquante qui
-- rend la main aussitôt quand rien n'est arrivé.
LuaExportBeforeNextFrame = function()
  if precedentAvantImage then pcall(precedentAvantImage) end
  pcall(DCSTablette.frame)
end

LuaExportStop = function()
  if precedentStop then pcall(precedentStop) end
  pcall(DCSTablette.stop)
end
