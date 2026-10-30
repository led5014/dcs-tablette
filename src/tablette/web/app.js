'use strict';

// DCS Tablette — les écrans du cockpit sous le doigt, et le kneeboard à côté.
//
// Tout se construit d'après le profil de l'appareil piloté (/api/profil) :
// les cadres et leurs boutons, les panneaux redessinés (UFC, IFEI, secours du
// Hornet), les dispositions proposées. Changer d'avion dans DCS reconstruit
// la page.
//
// Un bouton reste enfoncé dans le cockpit tant que le doigt est posé : la
// page envoie l'appui au contact, le relâchement au décollement.

const $ = (sel) => document.querySelector(sel);
const attendre = (ms) => new Promise((fin) => setTimeout(fin, ms));

const PERIODE_ETAT_MS = 750;        // aussi le délai de la bascule sur le kneeboard
const PERIODE_IMAGE_MS = 33;        // au plus 30 images par seconde et par écran
const PERIODE_PLANCHE_MS = 100;     // UFC, IFEI, aiguilles : 10 fois par seconde
const ATTENTE_SANS_IMAGE_MS = 1500;
const RATES_AVANT_MESSAGE = 3;
const BORD = 0.62;                  // épaisseur de la couronne de boutons, en cases

// Largeur, en pixels CSS, sous laquelle un panneau devient pénible au doigt
// ou à l'œil (boutons d'un cadre sous ~28 px de haut, touches de l'UFC sous
// ~40 px, voyants illisibles). Une disposition à plusieurs panneaux n'est
// proposée que si chacun l'atteint sur l'écran où la page est ouverte.
const CONFORT = { cadre: 280, ufc: 290, ifei: 200, secours: 520, secoursEtroit: 330 };

function element(balise, classe, texte) {
  const el = document.createElement(balise);
  if (classe) el.className = classe;
  if (texte !== undefined) el.textContent = texte;
  return el;
}

// --------------------------------------------------------------- mémoire
// Disposition, siège et page retrouvés à la réouverture, par appareil. Le
// stockage peut être refusé (navigation privée) : la page s'en passe.

function lire(cle, defaut) {
  try {
    const v = localStorage.getItem('tablette.' + cle);
    return v === null ? defaut : v;
  } catch { return defaut; }
}

function retenir(cle, valeur) {
  try { localStorage.setItem('tablette.' + cle, String(valeur)); } catch { /* sans mémoire */ }
}

// --------------------------------------------------------------- envoi
// Les ordres partent l'un après l'autre. Envoyés en parallèle, un appui bref
// pourrait voir son relâchement arriver AVANT l'appui : le bouton resterait
// alors tenu dans le cockpit jusqu'au garde-fou du script Lua.

let file = Promise.resolve();

async function poster(url, corps) {
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corps),
    });
    // Refusé par le serveur (appareil choisi à la main ≠ appareil piloté…) :
    // sa raison, à montrer telle quelle.
    if (!r.ok) {
      try { return (await r.json()).detail || false; } catch { return false; }
    }
    return (await r.json()).envoye === true;
  } catch { return false; }
}

function enFile(url, corps) {
  const envoi = file.then(() => poster(url, corps));
  file = envoi;
  return envoi;
}

// Relâcheurs des boutons tenus en ce moment : si la page passe en arrière-plan
// (verrouillage de l'iPad, changement d'app), on relâche tout avant de partir.
const tenus = new Set();
const toutRelacher = () => [...tenus].forEach((relacher) => relacher());

function brancherAppui(el, envoyer) {
  let enfonce = false;
  const relacher = () => {
    if (!enfonce) return;
    enfonce = false;
    tenus.delete(relacher);
    el.classList.remove('enfonce');
    envoyer(false);
  };
  el.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    if (enfonce) return;
    enfonce = true;
    tenus.add(relacher);
    el.classList.add('enfonce');
    try { el.setPointerCapture(e.pointerId); } catch { /* pointeur déjà parti */ }
    envoyer(true);
  });
  el.addEventListener('pointerup', relacher);
  el.addEventListener('pointercancel', relacher);
  el.addEventListener('lostpointercapture', relacher);
  el.addEventListener('contextmenu', (e) => e.preventDefault());
}

// Un geste unique (cran de molette) : un seul envoi, et l'enfoncement visible
// le temps du doigt.
function brancherGeste(el, envoyer) {
  el.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    el.classList.add('enfonce');
    envoyer();
  });
  for (const fin of ['pointerup', 'pointercancel', 'pointerleave']) {
    el.addEventListener(fin, () => el.classList.remove('enfonce'));
  }
  el.addEventListener('contextmenu', (e) => e.preventDefault());
}

// Page cachée (iPad verrouillé, autre app) : rien ne doit rester enfoncé. De
// retour : elle a pu tourner entre-temps, on redispose.
document.addEventListener('visibilitychange', () => {
  if (document.hidden) toutRelacher();
  else redisposer();
  accorderKneeboardDcs();
});

// --------------------------------------------------------------- état

let profil = null;
let generation = 0;            // change à chaque reconstruction : les boucles d'avant s'arrêtent
let dispositions = [];
let disposition = null;
let siege = '';
let enKneeboard = false;
let cadrans = null;
const panneaux = new Map();    // id → élément, qui porte ses formes possibles (.formes)
const affiches = new Set();    // panneaux sur la scène en ce moment
const reserve = element('div');
reserve.id = 'reserve';
document.body.append(reserve);

// --------------------------------------------------------------- dispositions
// Une disposition est une liste ordonnée de panneaux. Où les mettre se décide
// à l'affichage, d'après la place réelle : un iPad en paysage aligne deux
// écrans, le même en portrait les empile, un téléphone en paysage les serre,
// un grand écran en montre plus. Aucune taille d'appareil n'est écrite ici.

const abrege = (libelle) => libelle.replace(' gauche', ' G').replace(' droit', ' D');

function calculerDispositions(p) {
  const ids = p.ecrans.map((e) => e.id);
  const liste = [];
  const g = p.ecrans.find((e) => e.id.endsWith('gauche'));
  const d = p.ecrans.find((e) => e.id.endsWith('droit'));
  if (g && d) liste.push({ id: 'deux', libelle: `2 ${g.libelle.split(' ')[0]}`, ids: [g.id, d.id] });
  // `toujours` : proposée même à l'étroit (petit téléphone), plutôt que de
  // priver de l'écran ou du panneau ; les autres sont des regroupements.
  for (const e of p.ecrans) {
    liste.push({ id: e.id, libelle: abrege(e.libelle), ids: [e.id], toujours: true });
  }
  if (p.panneaux.includes('ufc')) {
    liste.push({ id: 'ufc', libelle: 'UFC', ids: ['ufc', 'ifei'], toujours: true });
  }
  if (p.panneaux.includes('secours')) {
    liste.push({ id: 'secours', libelle: 'Secours', ids: ['secours'], toujours: true });
  }
  if (ids.length >= 3) liste.push({ id: 'tous', libelle: `${ids.length} écrans`, ids });
  if (ids.length >= 2 && p.panneaux.length) {
    liste.push({ id: 'planche', libelle: 'Planche', ids: [...ids, ...p.panneaux] });
  }
  return liste;
}

// La place pour les panneaux : la zone sous la barre, moins ses marges (qui
// incluent encoches et barre d'accueil). Mesurée sur la scène ou, kneeboard
// ouvert, sur le kneeboard, qui occupe la même zone.
function espace() {
  const zone = (enKneeboard ? $('#kneeboard') : $('#scene')).getBoundingClientRect();
  const s = getComputedStyle($('#scene'));
  const marge = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--marge')) || 8;
  return {
    largeur: zone.width - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight),
    hauteur: zone.height - parseFloat(s.paddingTop) - parseFloat(s.paddingBottom),
    marge,
  };
}

// Toutes les façons de couper la liste en rangées (dans l'ordre), avec toutes
// les formes de chaque panneau. Chaque panneau est noté par sa largeur
// rapportée à sa largeur de confort. On préfère un agencement où tous sont
// confortables (note ≥ 1) ; entre ceux-là, celui où ils sont le plus grands
// dans l'ensemble (moyenne géométrique des notes) ; et s'il n'y en a aucun,
// celui où le moins bien servi l'est le mieux. Au plus 7 panneaux, soit 64
// découpages : instantané.
function meilleurAgencement(a, b) {
  if (!b) return true;
  const egal = (x, y) => Math.abs(x - y) <= 0.001 * Math.max(Math.abs(x), Math.abs(y), 1);
  if ((a.score >= 1) !== (b.score >= 1)) return a.score >= 1;
  const [va, vb] = a.score >= 1 ? [a.ensemble, b.ensemble] : [a.score, b.score];
  if (!egal(va, vb)) return va > vb;
  // À égalité, la première rangée la plus remplie : deux DDI en haut et
  // l'AMPCD dessous, comme dans le cockpit, plutôt que l'inverse.
  return a.rangees[0].length > b.rangees[0].length;
}

function agencer(ids, { largeur, hauteur, marge }) {
  const formes = ids.map((id) => panneaux.get(id).formes);
  const choix = formes.reduce((acc, f) => acc.flatMap((c) => f.map((x) => c.concat([x]))), [[]]);
  const n = ids.length;
  let meilleur = null;
  for (const c of choix) {
    for (let masque = 0; masque < 2 ** (n - 1); masque += 1) {
      const rangees = [[0]];
      for (let i = 1; i < n; i += 1) {
        if (masque & (1 << (i - 1))) rangees.push([i]);
        else rangees[rangees.length - 1].push(i);
      }
      // Hauteur de chaque rangée à pleine largeur, puis tout réduit d'un même
      // facteur si l'ensemble dépasse en hauteur.
      const naturelles = rangees.map((r) => (largeur - marge * (r.length - 1))
        / r.reduce((s, i) => s + c[i].ratio, 0));
      const libre = hauteur - marge * (rangees.length - 1);
      const k = Math.min(1, libre / naturelles.reduce((a, b) => a + b, 0));
      const h = naturelles.map((x) => Math.floor(x * k));
      let score = Infinity;
      let ensemble = 0;
      rangees.forEach((r, j) => r.forEach((i) => {
        const note = (h[j] * c[i].ratio) / c[i].confort;
        score = Math.min(score, note);
        ensemble += Math.log(Math.max(note, 1e-6));
      }));
      const candidat = {
        score,
        ensemble,
        rangees: rangees.map((r, j) => r.map((i) => ({
          id: ids[i], forme: c[i], hauteur: h[j], largeur: Math.floor(h[j] * c[i].ratio),
        }))),
      };
      if (meilleurAgencement(candidat, meilleur)) meilleur = candidat;
    }
  }
  return meilleur;
}

// Les dispositions qui tiennent sur cet écran, chacune avec son agencement.
function dispositionsPossibles() {
  const place = espace();
  if (place.largeur <= 0 || place.hauteur <= 0) return [];
  return dispositions
    .filter((d) => d.ids.every((id) => panneaux.has(id)))
    .map((d) => ({ d, agencement: agencer(d.ids, place) }))
    .filter(({ d, agencement }) => d.toujours || agencement.score >= 1);
}

function ecranAffiche(id) {
  if (document.hidden) return false;
  if (id === 'kneeboard') return enKneeboard && carnet !== null && carnet.direct === true;
  return !enKneeboard && affiches.has(id);
}

function appliquer() {
  document.body.classList.toggle('en-kneeboard', enKneeboard);
  $('#scene').hidden = enKneeboard;
  $('#kneeboard').hidden = !enKneeboard;
  accorderKneeboardDcs();
  const sansEcrans = dispositions.length === 0;
  $('#bascule').hidden = sansEcrans;
  $('#bascule').textContent = enKneeboard ? 'Écrans' : 'Kneeboard';

  const possibles = dispositionsPossibles();
  const courante = possibles.find((x) => x.d.id === disposition) || possibles[0] || null;
  const nav = $('#modes');
  nav.textContent = '';
  nav.hidden = sansEcrans;
  for (const { d } of possibles) {
    const b = element('button', !enKneeboard && courante && d.id === courante.d.id ? 'actif' : '', d.libelle);
    b.addEventListener('click', () => {
      disposition = d.id;
      retenir(`disposition.${profil.id}`, d.id);
      if (enKneeboard) toutRelacher();
      enKneeboard = false;
      appliquer();
    });
    nav.append(b);
  }
  // Barre trop étroite pour toutes les dispositions (téléphone) : celle en
  // cours reste en vue. À la main : scrollIntoView ferait défiler la page.
  const actif = nav.querySelector('.actif');
  if (actif && nav.scrollWidth > nav.clientWidth) {
    nav.scrollLeft = actif.offsetLeft - (nav.clientWidth - actif.offsetWidth) / 2;
  }

  const scene = $('#scene');
  for (const el of panneaux.values()) reserve.append(el);
  scene.textContent = '';
  affiches.clear();
  if (enKneeboard) return;
  if (!courante) {
    if (sansEcrans) {
      scene.append(element('p', 'vide-appareil', `${profil ? profil.libelle : 'Cet appareil'} : `
        + 'pas d\'écran à reprendre. Le kneeboard reste disponible.'));
    }
    return;
  }
  for (const rangee of courante.agencement.rangees) {
    const r = element('div', 'rangee');
    for (const place of rangee) {
      const el = panneaux.get(place.id);
      el.style.width = `${place.largeur}px`;
      el.style.height = `${place.hauteur}px`;
      el.style.setProperty('--taille', `${place.largeur}px`);
      for (const f of el.formes) if (f.classe) el.classList.toggle(f.classe, f === place.forme);
      affiches.add(place.id);
      r.append(el);
    }
    scene.append(r);
  }
}

function construireSieges() {
  const nav = $('#sieges');
  nav.textContent = '';
  nav.hidden = !profil.sieges.length;
  const libelles = { pilote: 'Pilote', cpg: 'CPG' };
  for (const s of profil.sieges) {
    const b = element('button', s === siege ? 'actif' : '', libelles[s] || s);
    b.addEventListener('click', () => {
      toutRelacher();
      siege = s;
      retenir(`siege.${profil.id}`, s);
      construireSieges();
    });
    nav.append(b);
  }
}

// Rotation, fenêtre redimensionnée, barre du navigateur qui se replie : on
// redispose une fois la rafale d'évènements passée. Un délai plutôt que
// requestAnimationFrame, suspendu tant que la page n'est pas affichée : elle
// doit reprendre à la bonne taille, même tournée pendant qu'elle était cachée.
let redispositionPrevue = 0;
function redisposer() {
  if (!profil) return;
  clearTimeout(redispositionPrevue);
  redispositionPrevue = setTimeout(appliquer, 60);
}
window.addEventListener('resize', redisposer);
window.addEventListener('orientationchange', redisposer);
if (window.ResizeObserver) new ResizeObserver(redisposer).observe(document.body);

// --------------------------------------------------------------- images

// Safari d'avant iOS 15 n'a pas createImageBitmap : une <img> hors de la page
// décode aussi bien ; sa mémoire est rendue une fois l'image peinte (close).
async function decoder(blob) {
  if (window.createImageBitmap) return createImageBitmap(blob);
  const url = URL.createObjectURL(blob);
  const img = new Image();
  img.src = url;
  try {
    await (img.decode ? img.decode() : new Promise((ok, ko) => {
      img.onload = ok;
      img.onerror = ko;
    }));
  } catch (e) {
    URL.revokeObjectURL(url);
    throw e;
  }
  img.close = () => URL.revokeObjectURL(url);
  return img;
}

async function demanderImage(id) {
  let r;
  const lum = luminosites.get(id) || 0;
  try {
    r = await fetch(`/api/video/${id}${lum ? `?lum=${lum}` : ''}`, { cache: 'no-store' });
  } catch { return { raison: 'Serveur injoignable' }; }
  if (!r.ok) {
    let raison = null;
    try { raison = (await r.json()).detail; } catch { /* corps illisible */ }
    return { raison: raison || "Pas d'image" };
  }
  try {
    return { image: await decoder(await r.blob()) };
  } catch { return { raison: 'Image illisible' }; }
}

// Une image n'est demandée qu'une fois la précédente affichée : le débit suit
// ce que l'iPad et le Wi-Fi absorbent, sans jamais accumuler de retard. Un
// écran caché (autre disposition, kneeboard, iPad en veille) ne demande rien.
//
// Contre le clignotement : l'image est décodée hors de l'écran puis peinte
// d'un coup sur la toile, jamais de cadre vide entre deux images ; et un raté
// isolé (DCS qui charge, Wi-Fi qui hoquette) laisse la dernière image en
// place au lieu de basculer image ↔ message à chaque fois.
async function boucleImage(id, conteneur, toile, msg, gen) {
  const ctx = toile.getContext('2d');
  let rates = 0;
  while (gen === null || gen === generation) {
    if (!ecranAffiche(id)) { await attendre(300); continue; }
    const debut = performance.now();
    const { image, raison } = await demanderImage(id);
    if (image) {
      if (toile.width !== image.width || toile.height !== image.height) {
        toile.width = image.width;
        toile.height = image.height;
      }
      ctx.drawImage(image, 0, 0);
      image.close();
      rates = 0;
      conteneur.classList.add('avec-image');
      const reste = PERIODE_IMAGE_MS - (performance.now() - debut);
      if (reste > 0) await attendre(reste);
      continue;
    }
    rates += 1;
    msg.textContent = raison;
    const durable = rates >= RATES_AVANT_MESSAGE;
    if (durable) conteneur.classList.remove('avec-image');
    await attendre(durable ? ATTENTE_SANS_IMAGE_MS : 200);
  }
}

// --------------------------------------------------------------- luminosité
// Réglée écran par écran, par appareil, et retenue sur chaque tablette : le
// TGP du F-16 est sombre, un DDI en plein soleil trop pâle. Le PC éclaircit
// l'image avant de la compresser (crans de -2 à +5, 0 : comme dans DCS).

const LUMINOSITE_MIN = -2;
const LUMINOSITE_MAX = 5;
const PAS_MOLETTE_PX = 26;          // glissement du doigt pour un cran
const ANGLE_CRAN = 30;              // la molette tourne de 30° par cran
const luminosites = new Map();

function cleLuminosite(id) { return `luminosite.${profil ? profil.id : ''}.${id}`; }

// Un mot en bas de l'écran (refus d'un appui, cran de luminosité), effacé
// après DUREE_RETOUR_MS : rien ne doit rester sur l'image.
const DUREE_RETOUR_MS = 1800;
function dire(retour, texte, erreur) {
  retour.textContent = texte;
  retour.classList.toggle('erreur', erreur);
  clearTimeout(retour.effacement);
  retour.effacement = setTimeout(() => { retour.textContent = ''; }, DUREE_RETOUR_MS);
}

// Une molette ronde dans le coin bas gauche du cadre, là où un vrai MFD a sa
// commande BRT. On la tourne du doigt : glisser vers le haut ou la droite
// éclaircit, cran par cran ; la molette de la souris et les flèches aussi.
function moletteLuminosite(cadre, id, ligneDuBas, retour) {
  luminosites.set(id, Number(lire(cleLuminosite(id), 0)) || 0);
  const m = element('div', 'molette-lum');
  m.append(element('span', 'repere'));
  m.style.gridColumn = '1';
  m.style.gridRow = String(ligneDuBas);
  m.tabIndex = 0;
  m.setAttribute('role', 'slider');
  m.setAttribute('aria-label', 'Luminosité');
  m.setAttribute('aria-valuemin', String(LUMINOSITE_MIN));
  m.setAttribute('aria-valuemax', String(LUMINOSITE_MAX));

  const dessiner = (afficher) => {
    const v = luminosites.get(id) || 0;
    m.style.setProperty('--angle', `${v * ANGLE_CRAN}deg`);
    m.setAttribute('aria-valuenow', String(v));
    if (afficher) dire(retour, `Luminosité ${v > 0 ? '+' : ''}${v}`, false);
  };
  const fixer = (niveau) => {
    niveau = Math.max(LUMINOSITE_MIN, Math.min(LUMINOSITE_MAX, niveau));
    if (niveau !== (luminosites.get(id) || 0)) {
      luminosites.set(id, niveau);
      retenir(cleLuminosite(id), niveau);
    }
    dessiner(true);
  };

  let depart = null;
  m.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    if (m.setPointerCapture) m.setPointerCapture(e.pointerId);
    depart = { x: e.clientX, y: e.clientY, niveau: luminosites.get(id) || 0 };
    m.classList.add('tourne');
    dessiner(true);
  });
  m.addEventListener('pointermove', (e) => {
    if (!depart) return;
    const glisse = (e.clientX - depart.x) - (e.clientY - depart.y);
    fixer(depart.niveau + Math.round(glisse / PAS_MOLETTE_PX));
  });
  for (const fin of ['pointerup', 'pointercancel']) {
    m.addEventListener(fin, () => { depart = null; m.classList.remove('tourne'); });
  }
  m.addEventListener('wheel', (e) => {
    e.preventDefault();
    fixer((luminosites.get(id) || 0) + (e.deltaY < 0 ? 1 : -1));
  }, { passive: false });
  m.addEventListener('keydown', (e) => {
    const sens = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1 }[e.key];
    if (sens) { e.preventDefault(); fixer((luminosites.get(id) || 0) + sens); }
  });
  m.addEventListener('contextmenu', (e) => e.preventDefault());
  dessiner(false);
  cadre.append(m);
}

// --------------------------------------------------------------- cadres

// Les pistes de la grille le long d'un côté du cadre. Sans repères : n cases
// égales. Avec : une case par bouton, centrée sur l'endroit où le module
// écrit son libellé (fraction de l'image, `reperes_x` / `reperes_y` du
// profil), et des vides entre elles — retour de vol : sur l'Apache, les
// libellés n'occupent pas toute la largeur, les boutons des bouts tombaient
// à côté. Le total reste n fr : le cadre garde sa taille. Rend le gabarit, la
// piste du bouton de chaque rang, et celle du bord d'en face.
const MARGE_ECRAN = 0.012;          // = margin de .ecran (style.css) : le verre dans sa case
function pistes(n, reperes) {
  if (!reperes || reperes.length !== n) {
    return { gabarit: `${BORD}fr repeat(${n}, 1fr) ${BORD}fr`, rang: (r) => 2 + r, fin: n + 2 };
  }
  const p = reperes.map((f) => MARGE_ECRAN + (1 - 2 * MARGE_ECRAN) * f);
  let c = 1 / n;                    // largeur d'une case, en fraction de l'écran
  for (let i = 1; i < n; i++) c = Math.min(c, p[i] - p[i - 1]);
  c = Math.min(c, 2 * p[0], 2 * (1 - p[n - 1]));
  const fr = (x) => `${Math.max(0, x * n).toFixed(4)}fr`;
  const t = [fr(p[0] - c / 2)];
  for (let i = 0; i < n; i++) {
    t.push(fr(c), fr((i < n - 1 ? p[i + 1] - c / 2 : 1) - p[i] - c / 2));
  }
  return { gabarit: `${BORD}fr ${t.join(' ')} ${BORD}fr`, rang: (r) => 3 + 2 * r, fin: 2 * n + 3 };
}

function construireCadre(e) {
  const n = e.par_cote;
  const rangee = e.boutons.filter((b) => b.cote === 'rangee');
  const col = pistes(n, e.reperes_x);
  const lig = pistes(n, e.reperes_y);
  const cadre = element('div', 'panneau cadre' + (e.reperes_x || e.reperes_y ? ' sur-reperes' : ''));
  cadre.style.gridTemplateColumns = col.gabarit;
  cadre.style.gridTemplateRows = lig.gabarit + (rangee.length ? ` ${BORD}fr` : '');
  const lignes = n + 2 * BORD + (rangee.length ? BORD : 0);
  cadre.formes = [{ ratio: (n + 2 * BORD) / lignes, classe: '', confort: CONFORT.cadre }];

  const ecran = element('div', 'ecran');
  ecran.style.gridColumn = `2 / ${col.fin}`;
  ecran.style.gridRow = `2 / ${lig.fin}`;
  if (typeof e.arrondi === 'number') ecran.style.setProperty('--arrondi', `${e.arrondi * 100}%`);
  const toile = element('canvas', 'video');
  const msg = element('div', 'ecran-msg', "En attente de l'image…");
  const retour = element('div', 'ecran-retour');
  ecran.append(toile, element('div', 'ecran-nom', e.libelle.toUpperCase()), msg, retour);
  cadre.append(ecran);

  // Rangée de touches fixes sous le cadre, réparties sur toute sa largeur.
  const touchesFixes = element('div', 'touches-fixes');
  if (rangee.length) {
    touchesFixes.style.gridColumn = `1 / ${col.fin + 1}`;
    touchesFixes.style.gridRow = String(lig.fin + 1);
    cadre.append(touchesFixes);
  }
  for (const b of e.boutons) {
    const el = element('button', `pb cote-${b.cote}`, b.id);
    el.setAttribute('aria-label', `${e.libelle}, ${b.id}`);
    if (b.cote === 'rangee') {
      touchesFixes.append(el);
    } else {
      // La couronne de la grille porte les boutons, le centre l'écran.
      const place = {
        gauche: [1, lig.rang(b.rang)], droite: [col.fin, lig.rang(b.rang)],
        haut: [col.rang(b.rang), 1], bas: [col.rang(b.rang), lig.fin],
      }[b.cote];
      el.style.gridColumn = String(place[0]);
      el.style.gridRow = String(place[1]);
      cadre.append(el);
    }
    // Rien d'écrit quand l'appui passe : le texte masquait le bas de l'écran
    // (retour de vol). Seul un refus est dit, le temps de le lire.
    brancherAppui(el, (enfonce) => enFile('/api/bouton',
      { ecran: e.id, bouton: b.id, enfonce, siege }).then((ok) => {
      if (ok !== true) dire(retour, `${b.id} : ${typeof ok === 'string' ? ok : 'non transmis'}`, true);
    }));
  }
  moletteLuminosite(cadre, e.id, lig.fin, retour);
  boucleImage(e.id, ecran, toile, msg, generation);
  return cadre;
}

// --------------------------------------------------------------- UFC

function toucheUfc(touche, libelle, classe = 'touche') {
  const el = element('button', classe, libelle);
  brancherAppui(el, (enfonce) => enFile('/api/ufc', { touche, enfonce }));
  return el;
}

function molette(touche, sens) {
  const el = element('button', 'touche', sens > 0 ? '+' : '−');
  el.setAttribute('aria-label', `${touche} ${sens > 0 ? 'cran suivant' : 'cran précédent'}`);
  brancherGeste(el, () => enFile('/api/ufc', { touche, sens }));
  return el;
}

function construireUfc() {
  const p = element('div', 'panneau ufc');
  p.formes = [{ ratio: 1.08, classe: '', confort: CONFORT.ufc }];
  const bloc = element('div', 'lcd ufc-bloc');
  const champs = [element('span'), element('span'), element('span')];
  bloc.append(...champs);

  const clavier = element('div', 'ufc-clavier');
  for (const t of ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'CLR', '0', 'ENT']) {
    clavier.append(toucheUfc(t, t));
  }
  const options = element('div', 'ufc-options');
  const fenetres = [];
  for (let i = 1; i <= 5; i += 1) {
    const el = toucheUfc(`OPT${i}`, '', 'touche option');
    const repere = element('span', 'repere');
    const texte = element('span', 'texte');
    el.append(repere, texte);
    fenetres.push({ repere, texte });
    options.append(el);
  }
  const milieu = element('div', 'ufc-milieu');
  milieu.append(clavier, options);

  const fonctions = element('div', 'ufc-fonctions');
  for (const [t, l] of [['AP', 'A/P'], ['IFF', 'IFF'], ['TCN', 'TCN'], ['ILS', 'ILS'],
    ['DL', 'D/L'], ['BCN', 'BCN'], ['ONOFF', 'ON/OFF']]) fonctions.append(toucheUfc(t, l));

  // Canaux COMM : le chiffre se tire (appui) ; − et + tournent la molette.
  const bas = element('div', 'ufc-bas');
  const canal1 = toucheUfc('COMM1_TIRER', '', 'touche canal');
  const canal2 = toucheUfc('COMM2_TIRER', '', 'touche canal');
  bas.append(molette('COMM1', -1), canal1, molette('COMM1', 1),
    toucheUfc('IP', 'I/P'), toucheUfc('EMCON', 'EMCON'),
    molette('COMM2', -1), canal2, molette('COMM2', 1));

  p.append(bloc, milieu, fonctions, bas);
  p.maj = (ufc) => {
    p.classList.toggle('sans-donnees', !ufc);
    if (!ufc) return;
    ufc.bloc.forEach((t, i) => { champs[i].textContent = t; });
    ufc.options.forEach((o, i) => {
      fenetres[i].repere.textContent = o.repere;
      fenetres[i].texte.textContent = o.texte;
    });
    canal1.textContent = ufc.comm1;
    canal2.textContent = ufc.comm2;
  };
  return p;
}

// --------------------------------------------------------------- IFEI

function construireIfei() {
  const p = element('div', 'panneau ifei lcd');
  p.formes = [{ ratio: 0.92, classe: '', confort: CONFORT.ifei }];
  const valeurs = {};
  const champ = (cle, classe) => {
    valeurs[cle] = element('span', classe);
    return valeurs[cle];
  };
  for (const [libelle, g, d] of [['RPM', 'rpm_g', 'rpm_d'], ['TEMP', 'temp_g', 'temp_d'],
    ['FF', 'ff_g', 'ff_d'], ['OIL', 'huile_g', 'huile_d']]) {
    p.append(champ(g, 'valeur'), element('span', 'libelle', libelle), champ(d, 'valeur'));
  }
  p.append(element('span', 'large'));
  p.append(champ('carburant_haut', 'large'), champ('carburant_bas', 'large'));
  const ligne1 = element('div', 'petite');
  ligne1.append(element('span', 'libelle', 'BINGO'), champ('bingo'), champ('codes'));
  const ligne2 = element('div', 'petite');
  ligne2.append(champ('horloge'), champ('chrono'));
  p.append(ligne1, ligne2);
  p.maj = (ifei) => {
    p.classList.toggle('sans-donnees', !ifei);
    if (!ifei) return;
    for (const [cle, el] of Object.entries(valeurs)) {
      if (cle in ifei) el.textContent = ifei[cle];
    }
    const heure = (h, m, s) => [h, m, s].filter((x) => x).join(':');
    valeurs.horloge.textContent = heure(ifei.horloge_h, ifei.horloge_m, ifei.horloge_s);
    valeurs.chrono.textContent = heure(ifei.chrono_h, ifei.chrono_m, ifei.chrono_s);
  };
  return p;
}

// --------------------------------------------------------------- secours

const SVG = 'http://www.w3.org/2000/svg';

function svg(balise, attributs = {}, parent = null) {
  const el = document.createElementNS(SVG, balise);
  for (const [k, v] of Object.entries(attributs)) el.setAttribute(k, v);
  if (parent) parent.append(el);
  return el;
}

const angleDe = (type, position) => cadrans.angles[type][0] + position * cadrans.angles[type][1];

// Un cadran rond : graduations placées par le serveur avec les mêmes tables
// que les aiguilles, une ou deux aiguilles, et une valeur lisible au centre.
function cadran(def, aiguilles = ['#e8ecee']) {
  const s = svg('svg', { viewBox: '-100 -100 200 200' });
  svg('circle', { r: 96, fill: '#0c0e0f', stroke: '#3a4043', 'stroke-width': 3 }, s);
  for (const g of def.graduations) {
    const a = (g.angle - 90) * Math.PI / 180;
    svg('line', { x1: 80 * Math.cos(a), y1: 80 * Math.sin(a), x2: 92 * Math.cos(a),
      y2: 92 * Math.sin(a), stroke: '#c9d1d3', 'stroke-width': 3 }, s);
    const t = svg('text', { x: 66 * Math.cos(a), y: 66 * Math.sin(a) + 6, fill: '#c9d1d3',
      'font-size': 16, 'text-anchor': 'middle', 'font-family': 'sans-serif' }, s);
    t.textContent = g.texte;
  }
  const valeur = svg('text', { y: 44, fill: '#7cff9a', 'font-size': 18, 'text-anchor': 'middle',
    'font-family': 'monospace' }, s);
  const traits = aiguilles.map((couleur) => {
    const g = svg('g', {}, s);
    svg('path', { d: 'M -4 12 L 0 -84 L 4 12 Z', fill: couleur }, g);
    return g;
  });
  svg('circle', { r: 7, fill: '#3a4043' }, s);
  return {
    el: s,
    tourner: (i, angle) => traits[i].setAttribute('transform', `rotate(${angle})`),
    texte: (t) => { valeur.textContent = t; },
  };
}

function horizon() {
  const s = svg('svg', { viewBox: '-100 -100 200 200' });
  const id = `sai${Math.random().toString(36).slice(2)}`;
  const clip = svg('clipPath', { id }, svg('defs', {}, s));
  svg('circle', { r: 92 }, clip);
  const vue = svg('g', { 'clip-path': `url(#${id})` }, s);
  const sphere = svg('g', {}, vue);
  svg('rect', { x: -300, y: -300, width: 600, height: 300, fill: '#3c6fa8' }, sphere);
  svg('rect', { x: -300, y: 0, width: 600, height: 300, fill: '#6b4a2b' }, sphere);
  svg('line', { x1: -300, x2: 300, y1: 0, y2: 0, stroke: '#fff', 'stroke-width': 2 }, sphere);
  for (const p of [-20, -10, 10, 20]) {
    svg('line', { x1: -18, x2: 18, y1: -p * 2, y2: -p * 2, stroke: '#fff', 'stroke-width': 2 }, sphere);
  }
  svg('path', { d: 'M -50 0 H -14 L 0 12 L 14 0 H 50', fill: 'none', stroke: '#f0b43c',
    'stroke-width': 5 }, s);
  svg('circle', { r: 96, fill: 'none', stroke: '#3a4043', 'stroke-width': 6 }, s);
  return {
    el: s,
    // Assiette : 2 unités par degré ; inclinaison : la sphère tourne à l'envers.
    poser: (assiette, inclinaison) => sphere.setAttribute('transform',
      `rotate(${-inclinaison}) translate(0 ${assiette * 2})`),
  };
}

const VOYANTS_ROUGES = new Set(['FIRE G', 'FIRE D', 'APU FIRE', 'NO GO', 'ALT BASSE', 'SHOOT']);
const VOYANTS_VERTS = new Set(['NOSE', 'LEFT', 'RIGHT', 'GO', 'READY', 'A/A', 'A/G', 'HALF',
  'FULL', 'AOA CENTRE', 'APU READY', 'LOCK']);

function construireSecours() {
  const p = element('div', 'panneau secours');
  // En largeur (4 instruments par rangée) ou en hauteur (3) : la page prend
  // celle qui laisse les instruments les plus grands sur l'écran du moment.
  p.formes = [{ ratio: 1.45, classe: '', confort: CONFORT.secours },
    { ratio: 0.76, classe: 'etroit', confort: CONFORT.secoursEtroit }];
  const case_ = (titre, contenu) => {
    const c = element('div', 'instrument');
    c.append(contenu, element('span', 'titre', titre));
    p.append(c);
  };
  const badin = cadran(cadrans.badin);
  const alti = cadran(cadrans.altimetre);
  const sai = horizon();
  const vario = cadran(cadrans.vario);
  const sonde = cadran(cadrans.sonde);
  const hyd = cadran(cadrans.pression, ['#7cc7ff', '#ffb36b']);
  const frein = cadran(cadrans.pression);
  case_('VITESSE kt', badin.el);
  case_('ALTITUDE ft', alti.el);
  case_('HORIZON', sai.el);
  case_('VARIO ×1000 ft/min', vario.el);
  case_('SONDE ft', sonde.el);
  case_('HYD G / D ×1000 psi', hyd.el);
  case_('FREIN ×1000 psi', frein.el);
  const calage = element('div', 'instrument lcd');
  calage.style.alignItems = 'center';
  calage.style.justifyContent = 'center';
  p.append(calage);

  const voyants = element('div', 'voyants');
  const lampes = new Map();
  p.append(voyants);

  p.maj = (instr, etats) => {
    p.classList.toggle('sans-donnees', !instr);
    if (instr) {
      badin.tourner(0, angleDe('tour', instr.badin.position));
      badin.texte(Math.round(instr.badin.valeur));
      alti.tourner(0, angleDe('tour', instr.altimetre.position));
      alti.texte(instr.altimetre.valeur);
      sai.poser(instr.sai.assiette, instr.sai.inclinaison);
      vario.tourner(0, angleDe('vario', instr.vario.position));
      vario.texte(Math.round(instr.vario.valeur));
      sonde.tourner(0, angleDe('tour', instr.sonde.position));
      sonde.texte(Math.round(instr.sonde.valeur));
      hyd.tourner(0, angleDe('pression', instr.hydraulique.gauche.position));
      hyd.tourner(1, angleDe('pression', instr.hydraulique.droite.position));
      hyd.texte(`${Math.round(instr.hydraulique.gauche.valeur)} / ${Math.round(instr.hydraulique.droite.valeur)}`);
      frein.tourner(0, angleDe('pression', instr.frein.position));
      frein.texte(Math.round(instr.frein.valeur));
      calage.textContent = `${instr.altimetre.calage.toFixed(2)} inHg`;
    }
    if (!etats) return;
    for (const [nom, allume] of Object.entries(etats)) {
      if (!lampes.has(nom)) {
        const couleur = VOYANTS_ROUGES.has(nom) ? ' rouge' : VOYANTS_VERTS.has(nom) ? ' vert' : '';
        const l = element('div', `voyant${couleur}`, nom);
        lampes.set(nom, l);
        voyants.append(l);
      }
      lampes.get(nom).classList.toggle('allume', allume);
    }
  };
  return p;
}

async function bouclePlanche(gen) {
  while (gen === generation) {
    if (!['ufc', 'ifei', 'secours'].some((id) => ecranAffiche(id))) {
      await attendre(300);
      continue;
    }
    let d = null;
    try {
      const r = await fetch('/api/planche', { cache: 'no-store' });
      if (r.ok) d = await r.json();
    } catch { /* serveur injoignable : panneaux grisés */ }
    if (gen !== generation) return;
    if (panneaux.has('ufc')) panneaux.get('ufc').maj(d && d.ufc);
    if (panneaux.has('ifei')) panneaux.get('ifei').maj(d && d.ifei);
    if (panneaux.has('secours')) panneaux.get('secours').maj(d && d.instruments, d && d.voyants);
    await attendre(PERIODE_PLANCHE_MS);
  }
}

// --------------------------------------------------------------- profil

async function chargerProfil() {
  let p;
  try {
    p = await (await fetch('/api/profil', { cache: 'no-store' })).json();
    if (p.panneaux.includes('secours') && !cadrans) {
      cadrans = await (await fetch('/api/planche/cadrans', { cache: 'no-store' })).json();
    }
  } catch {
    setTimeout(chargerProfil, 2000);
    return;
  }
  generation += 1;
  toutRelacher();
  profil = p;
  dispositions = calculerDispositions(p);
  disposition = lire(`disposition.${p.id}`, dispositions.length ? dispositions[0].id : null);
  siege = p.sieges.length ? lire(`siege.${p.id}`, p.sieges[0]) : '';
  if (!p.sieges.includes(siege)) siege = p.sieges.length ? p.sieges[0] : '';

  panneaux.clear();
  reserve.textContent = '';
  for (const e of p.ecrans) panneaux.set(e.id, construireCadre(e));
  if (p.panneaux.includes('ufc')) panneaux.set('ufc', construireUfc());
  if (p.panneaux.includes('ifei')) panneaux.set('ifei', construireIfei());
  if (p.panneaux.includes('secours')) panneaux.set('secours', construireSecours());
  if (p.panneaux.length) bouclePlanche(generation);

  // Appareil sans écran repris : le kneeboard est tout ce qu'on peut offrir.
  if (!dispositions.length && !enKneeboard) {
    enKneeboard = true;
    chargerCarnets();
  }
  construireSieges();
  appliquer();
}

// --------------------------------------------------------------- état DCS

let versionServeur = null;

async function rafraichirEtat() {
  const el = $('#etat');
  let classe = 'inconnu';
  let detecte;                    // ce que DCS dit, pour l'option « Auto »
  let titre;
  let ailleurs = null;
  try {
    const e = await (await fetch(`/api/etat?kneeboard=${kneeboardSur}`, { cache: 'no-store' })).json();
    // Serveur mis à jour pendant que la page restait ouverte (iPad en veille,
    // icône d'écran d'accueil sans bouton pour recharger) : on se recharge,
    // sinon la vieille page continue de tourner sur le nouveau serveur.
    if (versionServeur === null) {
      versionServeur = e.version;
      document.title = `DCS Tablette ${e.version}`;
    } else if (e.version && e.version !== versionServeur) {
      toutRelacher();
      location.reload();
      return;
    }
    suivreKneeboardDcs(e.kneeboard);
    majBadgeDiagnostic(e.problemes || 0);
    const d = e.dcs;
    ailleurs = e.ailleurs;
    if (!d.connecte) {
      detecte = 'DCS : pas de signal';
    } else if (!d.appareil) {
      detecte = 'DCS : pas dans un appareil';
    } else if (ailleurs) {
      detecte = `DCS : ${ailleurs}`;
    } else if (e.profil === 'generique') {
      classe = 'autre';
      detecte = `${d.appareil} (pas de profil, kneeboard seul)`;
    } else {
      classe = 'ok';
      detecte = e.choisi ? `DCS : ${e.libelle}` : e.libelle;
    }
    titre = detecte;
    if (ailleurs) {
      classe = 'autre';
      titre = `Tablette réglée sur ${e.libelle}, DCS pilote ${ailleurs} : boutons coupés`;
    }
    if (profil && e.profil !== profil.id) chargerProfil();
  } catch {
    classe = 'erreur';
    detecte = 'serveur injoignable';
    titre = 'Serveur de la tablette injoignable';
  }
  el.className = 'etat ' + classe;
  el.title = titre;
  el.setAttribute('aria-label', titre);
  majMenuAppareil(detecte, ailleurs);
}

// --------------------------------------------------------------- appareil
// Le menu Appareil : « Auto » suit ce que DCS annonce ; un appareil choisi à
// la main prépare la page avant la mission, ou rattrape un DCS muet. Le
// choix voyage dans un cookie : chaque tablette garde le sien, et le serveur
// coupe les boutons si l'appareil choisi n'est pas celui que DCS pilote.

const COOKIE_APPAREIL = 'tablette_appareil';

function choixAppareil() {
  const m = document.cookie.match(/(?:^|; )tablette_appareil=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : 'auto';
}

function retenirAppareil(valeur) {
  document.cookie = valeur === 'auto'
    ? `${COOKIE_APPAREIL}=; path=/; max-age=0; SameSite=Lax`
    : `${COOKIE_APPAREIL}=${encodeURIComponent(valeur)}; path=/; max-age=31536000; SameSite=Lax`;
}

async function construireMenuAppareil() {
  const select = $('#appareil');
  let liste = [];
  try {
    liste = await (await fetch('/api/profils', { cache: 'no-store' })).json();
  } catch {
    setTimeout(construireMenuAppareil, 2000);
    return;
  }
  const auto = select.options[0];
  select.textContent = '';
  select.append(auto);
  for (const p of liste) {
    const opt = element('option', '', p.libelle);
    opt.value = p.id;
    opt.dataset.libelle = p.libelle;
    select.append(opt);
  }
  select.value = choixAppareil();
  if (select.selectedIndex < 0) select.value = 'auto';
}

function majMenuAppareil(detecte, ailleurs) {
  const select = $('#appareil');
  select.options[0].textContent = `Auto · ${detecte}`;
  for (const opt of select.options) {
    if (!opt.dataset.libelle) continue;
    opt.textContent = opt.selected && ailleurs
      ? `${opt.dataset.libelle} — DCS : ${ailleurs}` : opt.dataset.libelle;
  }
  select.title = select.selectedOptions.length ? select.selectedOptions[0].textContent : '';
}

$('#appareil').addEventListener('change', (e) => {
  toutRelacher();                 // les boutons sous le doigt vont changer
  retenirAppareil(e.target.value);
  chargerProfil();
  if (enKneeboard) chargerCarnets();
  rafraichirEtat();
});

// --------------------------------------------------------------- kneeboard

// En tête, le kneeboard de DCS lui-même, capturé en direct : les pages que
// DCS fabrique (carte, points, fréquences) n'existent nulle part en fichier.
// Ses flèches tournent les pages DANS DCS, comme les touches [ et ].
// Puis les fichiers, lus tels quels, nets à toute taille : « Kneeboard de
// l'avion » (mission, module, pages perso), les cartes, les autres missions.
const KNEEBOARD_DCS = { id: 'dcs', titre: 'Kneeboard DCS (en direct)', direct: true };

let carnets = [];
let carnet = null;
let page = 0;

// `impose` : carnet choisi par la page elle-même (bascule à l'ouverture dans
// DCS), qui ne remplace pas celui que l'on a choisi à la main.
async function chargerCarnets(impose = null) {
  let fichiers = [];
  try {
    fichiers = await (await fetch('/api/kneeboard', { cache: 'no-store' })).json();
  } catch { fichiers = []; }
  carnets = [KNEEBOARD_DCS, ...fichiers];
  const select = $('#kb-carnet');
  select.textContent = '';
  for (const c of carnets) {
    const opt = element('option', '', c.direct ? c.titre : `${c.titre} (${c.pages})`);
    opt.value = c.id;
    select.append(opt);
  }
  const voulu = impose || lire('carnet', '');
  carnet = carnets.find((c) => c.id === voulu)
    || carnets.find((c) => c.id === 'avion') || carnets[0];
  page = !impose && carnet.id === voulu ? Number(lire('page', '0')) || 0 : 0;
  select.value = carnet.id;
  afficherPage(!impose);
}

function choisirCarnet(id, memoriser) {
  carnet = carnets.find((c) => c.id === id) || carnet;
  page = 0;
  $('#kb-carnet').value = carnet.id;
  afficherPage(memoriser);
}

function afficherPage(memoriser = true) {
  const vue = $('#kb-vue');
  const img = $('#kb-image');
  vue.classList.toggle('direct', carnet.direct === true);
  accorderKneeboardDcs();
  if (memoriser) retenir('carnet', carnet.id);
  if (carnet.direct) {
    img.hidden = true;
    $('#kb-vide').hidden = true;
    $('#kb-num').textContent = 'DCS';
    const tournable = !profil || profil.kneeboard;
    $('#kb-prec').disabled = $('#kb-suiv').disabled = !tournable;
    return;
  }
  const vide = carnet.pages === 0;
  img.hidden = vide;
  $('#kb-vide').hidden = !vide;
  if (vide) {
    $('#kb-num').textContent = '';
    $('#kb-prec').disabled = $('#kb-suiv').disabled = true;
    return;
  }
  page = Math.max(0, Math.min(page, carnet.pages - 1));
  img.src = `${carnet.url}/${page}`;
  $('#kb-num').textContent = `${page + 1} / ${carnet.pages}`;
  $('#kb-prec').disabled = page === 0;
  $('#kb-suiv').disabled = page === carnet.pages - 1;
  if (page + 1 < carnet.pages) new Image().src = `${carnet.url}/${page + 1}`;
  if (memoriser) retenir('page', page);
}

// --------------------------------------------------------------- kneeboard de DCS
// Où va le kneeboard quand on l'ouvre dans DCS (RShift+K, K) : sur le PC,
// par le miroir, comme d'habitude ; ou ici. La page redit ce choix au
// serveur à chaque demande d'état ; muette plus de 10 s, il revient au PC.
// Sur la tablette, l'ouvrir dans DCS amène la page sur le kneeboard en
// direct ; le refermer la ramène là où elle était.

let kneeboardSur = lire('kneeboard.sur', 'pc') === 'tablette' ? 'tablette' : 'pc';
let ouvertDansDcs = false;
let avantOuverture = null;      // { enKneeboard, carnet } quand DCS l'a ouvert
let afficheParLaTablette = false;

// Sur la tablette, regarder le kneeboard de DCS en direct suffit à l'ouvrir
// dans DCS (DCS ne le dessine qu'ouvert) ; passer à autre chose le referme.
// Rien ne s'affiche sur le PC : en mode tablette, le miroir est coupé.
function accorderKneeboardDcs() {
  const voulu = kneeboardSur === 'tablette' && enKneeboard && !document.hidden
    && carnet !== null && carnet.direct === true;
  if (voulu === afficheParLaTablette) return;
  afficheParLaTablette = voulu;
  poster('/api/kneeboard/dcs/affichage', { ouvert: voulu });
}

function construireKneeboardSur() {
  for (const b of document.querySelectorAll('#kb-sur button')) {
    b.classList.toggle('actif', b.dataset.sur === kneeboardSur);
  }
}

async function suivreKneeboardDcs(kb) {
  const ouvert = Boolean(kb && kb.sur === 'tablette' && kb.ouvert === true);
  if (ouvert === ouvertDansDcs) return;
  ouvertDansDcs = ouvert;
  if (ouvert) {
    avantOuverture = { enKneeboard, carnet: carnet ? carnet.id : null };
    if (!enKneeboard) {
      toutRelacher();               // les écrans vont disparaître sous le doigt
      enKneeboard = true;
      appliquer();
      await chargerCarnets(KNEEBOARD_DCS.id);
    } else if (!carnet || !carnet.direct) {
      choisirCarnet(KNEEBOARD_DCS.id, false);
    }
    return;
  }
  const avant = avantOuverture;
  avantOuverture = null;
  // Revenu ailleurs à la main entre-temps : on n'y touche pas.
  if (!avant || !enKneeboard || !carnet || !carnet.direct) return;
  if (!avant.enKneeboard) {
    enKneeboard = false;
    appliquer();
  } else if (avant.carnet) {
    choisirCarnet(avant.carnet, false);
  }
}

function tourner(sens) {
  if (!carnet) return;
  if (carnet.direct) {
    if (profil && profil.kneeboard) poster('/api/kneeboard/dcs/page', { sens });
    return;
  }
  const suivante = page + sens;
  if (suivante < 0 || suivante >= carnet.pages) return;
  page = suivante;
  afficherPage();
}

function brancherKneeboard() {
  $('#kb-carnet').addEventListener('change', (e) => {
    carnet = carnets.find((c) => c.id === e.target.value) || null;
    page = 0;
    afficherPage();
  });
  $('#kb-prec').addEventListener('click', () => tourner(-1));
  $('#kb-suiv').addEventListener('click', () => tourner(1));
  for (const b of document.querySelectorAll('#kb-sur button')) {
    b.addEventListener('click', () => {
      kneeboardSur = b.dataset.sur;
      retenir('kneeboard.sur', kneeboardSur);
      construireKneeboardSur();
      accorderKneeboardDcs();
      rafraichirEtat();             // le PC le sait tout de suite
    });
  }
  construireKneeboardSur();

  // Balayage horizontal pour tourner la page ; un appui sur le tiers gauche
  // ou droit fait de même, pour qui préfère taper que glisser.
  const vue = $('#kb-vue');
  let depart = null;
  vue.addEventListener('pointerdown', (e) => { depart = { x: e.clientX, y: e.clientY }; });
  vue.addEventListener('pointerup', (e) => {
    if (!depart) return;
    const dx = e.clientX - depart.x;
    const dy = e.clientY - depart.y;
    depart = null;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy)) {
      tourner(dx < 0 ? 1 : -1);
    } else if (Math.abs(dx) < 10 && Math.abs(dy) < 10) {
      const largeur = vue.getBoundingClientRect().width;
      if (e.clientX < largeur / 3) tourner(-1);
      else if (e.clientX > (2 * largeur) / 3) tourner(1);
    }
  });
  vue.addEventListener('pointercancel', () => { depart = null; });

  // Un seul geste pour jeter un œil au kneeboard et revenir aux écrans.
  $('#bascule').addEventListener('click', () => {
    // Les écrans vont disparaître : rien ne doit y rester enfoncé.
    if (!enKneeboard) toutRelacher();
    enKneeboard = !enKneeboard;
    if (enKneeboard) chargerCarnets();
    appliquer();
  });
}

// --------------------------------------------------------------- diagnostic
// Ce que la fenêtre de DCS Tablette vérifie sur le PC (diagnostic.py), point
// par point : OK, réparé tout seul, en attente (DCS pas lancé…), ou à régler,
// avec la marche à suivre. Ouvert en touchant la pastille, ou le badge
// « ⚠ n » qui apparaît quand il y a quelque chose à régler.

const MARQUES = { ok: '✓', repare: '✓', attente: '…', a_faire: '!', manque: '✕' };
const LIBELLES = { ok: '', repare: 'réparé', attente: 'en attente', a_faire: 'à régler',
                   manque: 'manque' };
const PERIODE_DIAGNOSTIC_MS = 2000;
let diagnosticOuvert = false;

function majBadgeDiagnostic(n) {
  const badge = $('#diag');
  badge.hidden = !n;
  badge.textContent = `⚠ ${n}`;
  badge.setAttribute('aria-label', `Diagnostic : ${n} point${n > 1 ? 's' : ''} à régler`);
}

function afficherDiagnostic(d) {
  $('#diag-heure').textContent = d.heure ? `vérifié à ${d.heure}` : 'pas encore vérifié';
  const liste = $('#diag-points');
  liste.textContent = '';
  for (const p of d.points) {
    const li = element('li', p.etat);
    li.append(element('span', 'marque', MARQUES[p.etat] || '?'));
    const titre = element('div', 'point-titre', p.titre);
    if (LIBELLES[p.etat]) titre.append(element('em', '', LIBELLES[p.etat]));
    li.append(titre, element('div', 'point-detail', p.detail));
    if (p.solution.length) {
      const etapes = element('ol', 'point-solution');
      for (const s of p.solution) etapes.append(element('li', '', s));
      li.append(etapes);
    }
    liste.append(li);
  }
  const journal = $('#diag-journal');
  journal.textContent = '';
  $('#diag-titre-journal').hidden = d.journal.length === 0;
  for (const j of d.journal) {
    const li = element('li', j.etat);
    li.append(element('span', 'heure', j.heure), `${j.titre} : ${j.detail}`);
    journal.append(li);
  }
  majBadgeDiagnostic(d.problemes);
}

async function chargerDiagnostic(verifier = false) {
  try {
    // POST en JSON : le serveur refuse un POST vide, qu'une page d'un autre
    // site pourrait envoyer sans que le navigateur s'y oppose.
    const r = await fetch('/api/diagnostic', verifier
      ? { method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ verifier: true }) }
      : { cache: 'no-store' });
    afficherDiagnostic(await r.json());
  } catch {
    $('#diag-heure').textContent = 'PC injoignable : la fenêtre DCS Tablette est-elle '
      + 'ouverte, et le PC sur le même Wi-Fi ?';
  }
}

function ouvrirDiagnostic(ouvrir) {
  diagnosticOuvert = ouvrir;
  $('#diagnostic').hidden = !ouvrir;
  if (ouvrir) chargerDiagnostic();
}

function brancherDiagnostic() {
  const etat = $('#etat');
  etat.addEventListener('click', () => ouvrirDiagnostic(!diagnosticOuvert));
  etat.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') ouvrirDiagnostic(!diagnosticOuvert);
  });
  $('#diag').addEventListener('click', () => ouvrirDiagnostic(true));
  $('#diag-fermer').addEventListener('click', () => ouvrirDiagnostic(false));
  $('#diag-verifier').addEventListener('click', async () => {
    const bouton = $('#diag-verifier');
    bouton.disabled = true;
    $('#diag-heure').textContent = 'vérification…';
    await chargerDiagnostic(true);
    bouton.disabled = false;
  });
  setInterval(() => { if (diagnosticOuvert && !document.hidden) chargerDiagnostic(); },
              PERIODE_DIAGNOSTIC_MS);
}

// --------------------------------------------------------------- plein écran
// Android, navigateur du PC : un bouton cache la barre du navigateur. Masqué
// quand la page est ouverte depuis l'écran d'accueil (déjà plein écran) et
// sur iPhone, où Safari ne le permet pas.

function brancherPleinEcran() {
  const racine = document.documentElement;
  const demander = racine.requestFullscreen || racine.webkitRequestFullscreen;
  const quitter = document.exitFullscreen || document.webkitExitFullscreen;
  const actuel = () => document.fullscreenElement || document.webkitFullscreenElement;
  const autonome = navigator.standalone === true || (window.matchMedia
    && window.matchMedia('(display-mode: standalone), (display-mode: fullscreen)').matches);
  const permis = document.fullscreenEnabled || document.webkitFullscreenEnabled;
  const bouton = $('#plein');
  bouton.hidden = !demander || !permis || autonome;
  bouton.addEventListener('click', () => {
    try {
      const r = actuel() ? quitter.call(document) : demander.call(racine);
      if (r && r.catch) r.catch(() => {});
    } catch { /* refusé : la page reste dans sa fenêtre */ }
  });
}

// --------------------------------------------------------------- démarrage

brancherPleinEcran();
brancherDiagnostic();
construireMenuAppareil();
brancherKneeboard();
chargerProfil();
boucleImage('kneeboard', $('#kb-vue'), $('#kb-direct'), $('#kb-msg'), null);
rafraichirEtat();
setInterval(rafraichirEtat, PERIODE_ETAT_MS);
