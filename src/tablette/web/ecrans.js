'use strict';

// DCS Tablette — la page Écrans du PC (reglage_ecrans.py).
//
// Les écrans de Windows, la fenêtre de DCS et les zones des écrans du
// cockpit, à l'échelle, comme dans Paramètres → Écran. Chaque élément se
// glisse à la souris ou se règle au pixel ; « Ce qui va changer » se relit à
// chaque retouche (/api/ecrans/apercu), et rien n'est écrit avant
// « Enregistrer ». « Montrer sur mes écrans » pose les zones sur les vrais
// écrans (calage.py) et les fait suivre en direct.
//
// Une seule origine de coordonnées : le bureau de Windows, dont l'écran
// principal est en (0, 0) — c'est aussi celle de la fenêtre de DCS.

const $ = (sel) => document.querySelector(sel);
const SVG = 'http://www.w3.org/2000/svg';
const EXPORTS = ['LEFT_MFCD', 'RIGHT_MFCD', 'CENTER_MFCD', 'TEDAC'];
const COULEURS = { LEFT_MFCD: '#4fc3f7', RIGHT_MFCD: '#ffb74d', CENTER_MFCD: '#81c784',
  TEDAC: '#ce93d8' };
const ACCROCHE_PX = 10;          // aimantation aux bords, en pixels de la page
const ZONE_MIN = 50;

const LANGUE_PAGE = typeof LANGUE === 'string' ? LANGUE : 'fr';
const TRADUCTIONS = typeof TEXTES === 'object' && TEXTES ? TEXTES : {};

function tr(francais, valeurs = {}) {
  const texte = Object.prototype.hasOwnProperty.call(TRADUCTIONS, francais)
    ? TRADUCTIONS[francais] : francais;
  return texte.replace(/\{(\w+)\}/g, (tout, nom) => (nom in valeurs ? String(valeurs[nom]) : tout));
}

function traduirePage() {
  document.documentElement.lang = LANGUE_PAGE;
  for (const el of document.querySelectorAll('[data-t]')) {
    el.textContent = tr(el.textContent.trim().replace(/\s+/g, ' '));
  }
  for (const el of document.querySelectorAll('[data-t-aria]')) {
    el.setAttribute('aria-label', tr(el.getAttribute('aria-label')));
  }
}

function element(balise, classe, texte) {
  const el = document.createElement(balise);
  if (classe) el.className = classe;
  if (texte !== undefined) el.textContent = texte;
  return el;
}

function svg(balise, attributs = {}, parent = null) {
  const el = document.createElementNS(SVG, balise);
  for (const [k, v] of Object.entries(attributs)) el.setAttribute(k, v);
  if (parent) parent.append(el);
  return el;
}

const copie = (o) => JSON.parse(JSON.stringify(o));
const rect = (r) => ({ x: Math.round(r.x), y: Math.round(r.y), largeur: Math.round(r.largeur),
  hauteur: Math.round(r.hauteur) });
const commun = (a, b) => Math.max(0, Math.min(a.x + a.largeur, b.x + b.largeur) - Math.max(a.x, b.x))
  * Math.max(0, Math.min(a.y + a.hauteur, b.y + b.hauteur) - Math.max(a.y, b.y));

// --------------------------------------------------------------- l'état

let etat = null;            // /api/ecrans, tel que relu
let prop = null;            // la proposition en cours : écrans, fenêtre, zones
let jeu = '';               // '' : zones de tous les appareils ; sinon un nom DCS
let choisi = null;          // { type: 'ecran' | 'zone' | 'fenetre', id }
let apercu = null;          // dernier /api/ecrans/apercu
let montre = false;
let garderForme = true;

async function appeler(adresse, corps) {
  const r = await fetch(adresse, corps === undefined ? { cache: 'no-store' } : {
    method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corps) });
  const donnees = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(donnees.detail || `HTTP ${r.status}`);
  return donnees;
}

async function relire() {
  try {
    etat = await appeler('/api/ecrans');
  } catch (e) {
    $('#erreurs').textContent = '';
    $('#erreurs').append(element('li', '', e.message));
    return;
  }
  prop = {
    ecrans: Object.fromEntries(etat.ecrans.filter((e) => e.actif).map((e) => [e.id, rect(e)])),
    fenetre: etat.fenetre ? { ...etat.fenetre } : principalRect()
      && { largeur: principalRect().largeur, hauteur: principalRect().hauteur },
    zones: copie(etat.zones),
    par_appareil: copie(etat.par_appareil),
  };
  if (!Object.keys(prop.zones).length) prop.zones = zonesParDefaut();
  const mode = $('#mode');
  mode.className = 'mode ' + (etat.a_la_main ? 'main' : 'auto');
  mode.textContent = etat.a_la_main ? tr('À votre main') : tr('Automatique');
  $('#nb-virtuels').value = etat.virtuels;
  $('#nb-virtuels').max = etat.virtuels_max;
  construireJeux();
  construireProfils();
  choisi = null;
  toutRedessiner();
}

function principal() { return etat.ecrans.find((e) => e.principal && e.actif); }
function principalRect() { const p = etat && principal(); return p ? rect(p) : null; }

// Sans « Tablette DCS » encore écrite : un carré de quatre sur le premier
// écran virtuel, ou sous l'écran principal.
function zonesParDefaut() {
  const v = etat.ecrans.find((e) => e.virtuel && e.actif);
  const p = principalRect() || { x: 0, y: 0, largeur: 1920, hauteur: 1080 };
  const support = v ? rect(v) : { x: 0, y: p.hauteur, largeur: p.largeur, hauteur: 1000 };
  const c = Math.max(ZONE_MIN, Math.floor(Math.min(support.largeur, support.hauteur) / 2));
  return {
    LEFT_MFCD: { x: support.x, y: support.y, largeur: c, hauteur: c },
    RIGHT_MFCD: { x: support.x + c, y: support.y, largeur: c, hauteur: c },
    CENTER_MFCD: { x: support.x, y: support.y + c, largeur: c, hauteur: c },
    TEDAC: { x: support.x + c, y: support.y + c, largeur: c, hauteur: c },
  };
}

// --------------------------------------------------------------- jeux de zones
// « Tous les appareils », plus un jeu à part par appareil dont les écrans ne
// sont pas carrés (Kiowa en 4:3, JF-17 en portrait) : DCS le lui donne en
// entrant dans l'appareil (reconfigure_for_unit).

function construireJeux() {
  const select = $('#jeu');
  select.textContent = '';
  const tous = element('option', '', tr('Tous les appareils'));
  tous.value = '';
  select.append(tous);
  for (const nom of Object.keys(etat.formes)) {
    const opt = element('option', '', nom);
    opt.value = nom;
    select.append(opt);
  }
  if (![...select.options].some((o) => o.value === jeu)) jeu = '';
  select.value = jeu;
  majAideJeu();
}

function majAideJeu() {
  const aide = $('#jeu-aide');
  aide.textContent = '';
  if (!jeu) {
    aide.textContent = tr('Les zones de tout appareil sans zones à part.');
  } else {
    const a_part = Boolean(prop.par_appareil[jeu]);
    const case_ = element('input');
    case_.type = 'checkbox';
    case_.checked = a_part;
    case_.id = 'a-part';
    case_.addEventListener('change', () => basculerAPart(case_.checked));
    const etiquette = element('label', '', ' ' + tr('Zones à part pour {appareil}', { appareil: jeu }));
    etiquette.htmlFor = 'a-part';
    aide.append(case_, etiquette);
  }
  // Les zones absentes du jeu : à ajouter.
  const zones = zonesDuJeu();
  if (zones) {
    const manquent = EXPORTS.filter((z) => !zones[z]);
    if (manquent.length) {
      const ligne = element('div', 'ligne');
      ligne.append(element('span', 'discret', tr('Ajouter :')));
      for (const z of manquent) {
        const b = element('button', '', libelleZone(z));
        b.type = 'button';
        b.addEventListener('click', () => ajouterZone(z));
        ligne.append(b);
      }
      aide.append(ligne);
    }
  }
}

function zonesDuJeu() {
  if (!jeu) return prop.zones;
  return prop.par_appareil[jeu] || null;
}

function zonesAffichees() {
  return zonesDuJeu() || prop.zones;
}

// Les zones à part d'un appareil, tirées des zones communes : chaque écran
// le plus grand possible à sa forme dans la zone commune, au milieu (comme
// ecrans_dcs._grille), pour ne jamais déborder de ce qui était sur un écran.
function zonesAPartDepuisCommunes(nom) {
  const forme = etat.formes[nom] || {};
  const siennes = {};
  for (const [z, r] of Object.entries(prop.zones)) {
    if (!(z in forme)) continue;
    const largeur = Math.min(r.largeur, Math.floor(r.hauteur * forme[z]));
    const hauteur = Math.min(r.hauteur, Math.round(largeur / forme[z]));
    siennes[z] = { x: r.x + Math.floor((r.largeur - largeur) / 2),
      y: r.y + Math.floor((r.hauteur - hauteur) / 2), largeur, hauteur };
  }
  return siennes;
}

function basculerAPart(a_part) {
  if (a_part) prop.par_appareil[jeu] = zonesAPartDepuisCommunes(jeu);
  else delete prop.par_appareil[jeu];
  choisi = null;
  toutRedessiner();
}

function recalerAPart(noms) {
  for (const nom of noms) prop.par_appareil[nom] = zonesAPartDepuisCommunes(nom);
  toutRedessiner();
}

function ajouterZone(z) {
  const zones = zonesDuJeu();
  if (!zones) return;
  const v = etat.ecrans.find((e) => e.virtuel && e.actif) || principal();
  const c = Math.max(ZONE_MIN, Math.floor(Math.min(v.largeur, v.hauteur) / 2));
  zones[z] = { x: v.x, y: v.y, largeur: c, hauteur: c };
  choisi = { type: 'zone', id: z };
  toutRedessiner();
}

// --------------------------------------------------------------- libellés
// Les noms des zones (« DDI gauche ») et les repères des boutons sont ceux
// de l'appareil choisi ; sans appareil, les noms génériques.

function construireProfils() {
  const select = $('#profil');
  const avant = select.value;
  select.textContent = '';
  const aucun = element('option', '', tr('(aucun appareil)'));
  aucun.value = '';
  select.append(aucun);
  for (const p of etat.profils) {
    const opt = element('option', '', p.libelle);
    opt.value = p.id;
    select.append(opt);
  }
  select.value = avant || lireMemoire('profil', '');
  if (select.selectedIndex < 0) select.value = '';
}

function profil() { return etat.profils.find((p) => p.id === $('#profil').value) || null; }

function zoneDuProfil(z) {
  const p = profil();
  return p ? p.zones.find((d) => d.zone === z) || null : null;
}

function libelleZone(z) {
  const d = zoneDuProfil(z);
  return d ? d.libelle : (etat.libelles[z] || z);
}

function lireMemoire(cle, defaut) {
  try { return localStorage.getItem('tablette.ecrans.' + cle) ?? defaut; } catch { return defaut; }
}

function retenirMemoire(cle, valeur) {
  try { localStorage.setItem('tablette.ecrans.' + cle, valeur); } catch { /* sans mémoire */ }
}

// --------------------------------------------------------------- le schéma

let echelle = 1;            // unités du schéma par pixel de la page

function cadreDuSchema() {
  const rects = [...Object.values(prop.ecrans), ...Object.values(zonesAffichees())];
  if (prop.fenetre) rects.push({ x: 0, y: 0, ...prop.fenetre });
  const x0 = Math.min(...rects.map((r) => r.x));
  const y0 = Math.min(...rects.map((r) => r.y));
  const x1 = Math.max(...rects.map((r) => r.x + r.largeur));
  const y1 = Math.max(...rects.map((r) => r.y + r.hauteur));
  const marge = Math.max(x1 - x0, y1 - y0) * 0.04;
  return { x: x0 - marge, y: y0 - marge, largeur: x1 - x0 + 2 * marge, hauteur: y1 - y0 + 2 * marge };
}

function problemesDe(type, id) {
  if (!apercu || !apercu.apercu) return [];
  const a = apercu.apercu;
  if (type === 'zone') {
    const zones = jeu && zonesDuJeu() ? (a.par_appareil || {})[jeu] || [] : a.zones;
    return (zones.find((z) => z.nom === id) || { problemes: [] }).problemes;
  }
  if (type === 'ecran') {
    const r = prop.ecrans[id];
    const e = a.ecrans.find((d) => d.x === r.x && d.y === r.y && d.largeur === r.largeur
      && d.hauteur === r.hauteur);
    return e ? e.problemes : [];
  }
  return [];
}

function dessiner() {
  const schema = $('#schema');
  schema.textContent = '';
  const cadre = cadreDuSchema();
  schema.setAttribute('viewBox', `${cadre.x} ${cadre.y} ${cadre.largeur} ${cadre.hauteur}`);
  const largeurPage = schema.clientWidth || 800;
  const hauteurPage = schema.clientHeight || 500;
  echelle = Math.max(cadre.largeur / largeurPage, cadre.hauteur / hauteurPage);
  const taille = (px) => px * echelle;
  const trait = { 'vector-effect': 'non-scaling-stroke' };

  // Les écrans de Windows.
  for (const e of etat.ecrans.filter((d) => d.actif)) {
    const r = prop.ecrans[e.id];
    const mobile = !e.principal;
    const g = svg('g', { class: 'ecran' + (e.principal ? ' principal' : '') + (e.virtuel ? ' virtuel' : '')
      + (mobile ? ' mobile' : '') + (estChoisi('ecran', e.id) ? ' choisi' : '')
      + (problemesDe('ecran', e.id).length ? ' probleme' : '') }, schema);
    svg('rect', { class: 'fond', x: r.x, y: r.y, width: r.largeur, height: r.hauteur,
      'stroke-width': 1.5, ...trait }, g);
    // En bas à gauche : les zones se posent d'ordinaire en haut à gauche.
    const nom = svg('text', { x: r.x + taille(8), y: r.y + r.hauteur - taille(24), fill: '#e8ecee',
      'font-size': taille(14) }, g);
    nom.textContent = (e.principal ? '★ ' : '') + e.nom;
    const detail = svg('text', { x: r.x + taille(8), y: r.y + r.hauteur - taille(8), fill: '#7d878b',
      'font-size': taille(12) }, g);
    detail.textContent = `${r.largeur}×${r.hauteur} · (${r.x}, ${r.y})` + (e.virtuel ? ' · ' + tr('virtuel') : '');
    g.addEventListener('pointerdown', (ev) => saisir(ev, 'ecran', e.id, mobile));
    if (estChoisi('ecran', e.id) && e.virtuel) poignee(schema, 'ecran', e.id, r);
  }

  // La fenêtre de DCS.
  if (prop.fenetre) {
    const g = svg('g', { class: 'fenetre' + (estChoisi('fenetre', 'dcs') ? ' choisi' : '') }, schema);
    svg('rect', { x: 0, y: 0, width: prop.fenetre.largeur, height: prop.fenetre.hauteur,
      fill: 'none', stroke: estChoisi('fenetre', 'dcs') ? '#fff' : '#f0b43c',
      'stroke-width': 2, 'stroke-dasharray': '10 6', ...trait }, g);
    const t = svg('text', { x: prop.fenetre.largeur - taille(8), y: prop.fenetre.hauteur - taille(8),
      'text-anchor': 'end', fill: '#f0b43c', 'font-size': taille(12) }, g);
    t.textContent = tr('Fenêtre de DCS {largeur}×{hauteur}', prop.fenetre);
  }

  // Le kneeboard, tel que le serveur l'a calculé pour cette fenêtre.
  const k = apercu && apercu.apercu && apercu.apercu.kneeboard;
  if (k) {
    svg('rect', { x: k.x, y: k.y, width: k.largeur, height: k.hauteur, fill: 'rgba(239,90,79,.12)',
      stroke: 'rgba(239,90,79,.6)', 'stroke-dasharray': '4 4', 'stroke-width': 1, ...trait }, schema);
    const t = svg('text', { x: k.x + k.largeur / 2, y: k.y + k.hauteur / 2, 'text-anchor': 'middle',
      fill: 'rgba(239,90,79,.8)', 'font-size': taille(12) }, schema);
    t.textContent = tr('kneeboard ouvert');
  }

  // Les zones du jeu affiché.
  const zones = zonesAffichees();
  const modifiable = Boolean(zonesDuJeu());
  for (const z of EXPORTS) {
    const r = zones[z];
    if (!r) continue;
    const couleur = COULEURS[z];
    const g = svg('g', { class: 'zone' + (estChoisi('zone', z) ? ' choisi' : '')
      + (problemesDe('zone', z).length ? ' probleme' : '') }, schema);
    svg('rect', { x: r.x, y: r.y, width: r.largeur, height: r.hauteur, fill: couleur,
      'fill-opacity': modifiable ? 0.28 : 0.12, stroke: couleur, 'stroke-width': 2, ...trait }, g);
    const t = svg('text', { x: r.x + r.largeur / 2, y: r.y + r.hauteur / 2, 'text-anchor': 'middle',
      fill: '#fff', 'font-size': taille(13) }, g);
    t.textContent = libelleZone(z);
    const t2 = svg('text', { x: r.x + r.largeur / 2, y: r.y + r.hauteur / 2 + taille(17),
      'text-anchor': 'middle', fill: '#c9d1d3', 'font-size': taille(11) }, g);
    t2.textContent = `${r.largeur}×${r.hauteur} · (${r.x}, ${r.y})`;
    if (modifiable) {
      g.addEventListener('pointerdown', (ev) => saisir(ev, 'zone', z, true));
      if (estChoisi('zone', z)) poignee(schema, 'zone', z, r);
    }
  }
  schema.onpointerdown = (ev) => {
    if (ev.target === schema) { choisi = null; toutRedessiner(); }
  };
}

function poignee(schema, type, id, r) {
  const c = 12 * echelle;
  const p = svg('rect', { class: 'poignee', x: r.x + r.largeur - c / 2, y: r.y + r.hauteur - c / 2,
    width: c, height: c }, schema);
  p.addEventListener('pointerdown', (ev) => { ev.stopPropagation(); saisir(ev, type, id, true, true); });
}

function estChoisi(type, id) { return choisi && choisi.type === type && choisi.id === id; }

function rectDe(type, id) {
  if (type === 'ecran') return prop.ecrans[id];
  if (type === 'zone') return zonesAffichees()[id];
  return null;
}

// --------------------------------------------------------------- souris

function versSchema(ev) {
  const schema = $('#schema');
  const pt = schema.createSVGPoint();
  pt.x = ev.clientX;
  pt.y = ev.clientY;
  return pt.matrixTransform(schema.getScreenCTM().inverse());
}

function bordsAimants(type, id) {
  const xs = [0];
  const ys = [0];
  const ajouter = (r) => { xs.push(r.x, r.x + r.largeur); ys.push(r.y, r.y + r.hauteur); };
  for (const [autre, r] of Object.entries(prop.ecrans)) if (!(type === 'ecran' && autre === id)) ajouter(r);
  if (type === 'zone') {
    for (const [autre, r] of Object.entries(zonesAffichees())) if (autre !== id) ajouter(r);
  }
  return { xs, ys };
}

function aimanter(valeur, longueur, bords) {
  const seuil = ACCROCHE_PX * echelle;
  let meilleur = null;
  for (const b of bords) {
    for (const [v, decalage] of [[valeur, 0], [valeur + longueur, longueur]]) {
      const d = Math.abs(v - b);
      if (d < seuil && (meilleur === null || d < meilleur.d)) meilleur = { d, valeur: b - decalage };
    }
  }
  return meilleur ? meilleur.valeur : valeur;
}

function saisir(ev, type, id, mobile, redimensionner = false) {
  ev.preventDefault();
  ev.stopPropagation();
  choisi = { type, id };
  if (!mobile) { toutRedessiner(); return; }
  const depart = versSchema(ev);
  const avant = { ...rectDe(type, id) };
  const bords = bordsAimants(type, id);
  const forme = formeImposee(type, id, avant);
  const bouger = (e) => {
    const p = versSchema(e);
    const dx = p.x - depart.x;
    const dy = p.y - depart.y;
    const r = rectDe(type, id);
    if (redimensionner) {
      let l = Math.max(ZONE_MIN, Math.round(avant.largeur + dx));
      let h = Math.max(ZONE_MIN, Math.round(avant.hauteur + dy));
      if (forme) h = Math.round(l / forme);
      r.largeur = l;
      r.hauteur = h;
    } else {
      r.x = Math.round(e.shiftKey ? avant.x + dx : aimanter(avant.x + dx, avant.largeur, bords.xs));
      r.y = Math.round(e.shiftKey ? avant.y + dy : aimanter(avant.y + dy, avant.hauteur, bords.ys));
    }
    dessiner();
    majChoisi();
    montrerSiBesoin();
  };
  const lacher = () => {
    window.removeEventListener('pointermove', bouger);
    window.removeEventListener('pointerup', lacher);
    toutRedessiner();
  };
  window.addEventListener('pointermove', bouger);
  window.addEventListener('pointerup', lacher);
  toutRedessiner(false);
}

// La forme à garder en redimensionnant : celle de l'écran de l'appareil
// pour un jeu à part, sinon la forme actuelle si « Garder la forme ».
function formeImposee(type, id, r) {
  if (type !== 'zone' || !garderForme) return null;
  const forme = jeu && etat.formes[jeu] && etat.formes[jeu][id];
  return forme || r.largeur / r.hauteur;
}

// --------------------------------------------------------------- clavier

document.addEventListener('keydown', (ev) => {
  if (!choisi || ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
  const fleches = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
  if (!(ev.key in fleches)) return;
  const r = rectDe(choisi.type, choisi.id);
  if (!r || (choisi.type === 'ecran' && etat.ecrans.find((e) => e.id === choisi.id).principal)) return;
  if (choisi.type === 'zone' && !zonesDuJeu()) return;
  ev.preventDefault();
  const pas = ev.shiftKey ? 10 : 1;
  const [dx, dy] = fleches[ev.key];
  if (ev.ctrlKey) {
    const virtuel = choisi.type === 'zone'
      || etat.ecrans.find((e) => e.id === choisi.id).virtuel;
    if (!virtuel) return;
    const forme = formeImposee(choisi.type, choisi.id, r);
    r.largeur = Math.max(ZONE_MIN, r.largeur + dx * pas);
    r.hauteur = Math.max(ZONE_MIN, r.hauteur + dy * pas);
    if (forme && dx) r.hauteur = Math.round(r.largeur / forme);
    else if (forme && dy) r.largeur = Math.round(r.hauteur * forme);
  } else {
    r.x += dx * pas;
    r.y += dy * pas;
  }
  toutRedessiner();
});

// --------------------------------------------------------------- le choisi

function champ(libelle, valeur, changer, options = {}) {
  const id = 'c-' + Math.random().toString(36).slice(2);
  const l = element('label', '', libelle);
  l.htmlFor = id;
  const input = element('input');
  input.type = 'number';
  input.id = id;
  input.step = '1';
  input.value = valeur;
  if (options.desactive) input.disabled = true;
  input.addEventListener('change', () => {
    const v = Math.round(Number(input.value));
    if (Number.isFinite(v)) changer(v);
    toutRedessiner();
  });
  return [l, input];
}

function majChoisi() {
  const titre = $('#choisi-titre');
  const corps = $('#choisi-corps');
  corps.textContent = '';
  corps.className = '';
  if (!choisi) {
    titre.textContent = tr('Rien de choisi');
    corps.className = 'discret';
    corps.textContent = tr('Cliquer un écran, une zone ou la fenêtre de DCS dans le schéma.');
    return;
  }
  const grille = element('div', 'champs');
  if (choisi.type === 'ecran') {
    const e = etat.ecrans.find((d) => d.id === choisi.id);
    const r = prop.ecrans[e.id];
    titre.textContent = e.nom + (e.principal ? ' — ' + tr('principal') : e.virtuel ? ' — ' + tr('virtuel') : '');
    grille.append(...champ('x', r.x, (v) => { r.x = v; }, { desactive: e.principal }),
      ...champ('y', r.y, (v) => { r.y = v; }, { desactive: e.principal }));
    if (e.virtuel) {
      grille.append(...champ(tr('Largeur'), r.largeur, (v) => { r.largeur = v; }),
        ...champ(tr('Hauteur'), r.hauteur, (v) => { r.hauteur = v; }));
    }
    corps.append(grille);
    if (e.virtuel) {
      const ligne = element('div', 'ligne');
      const select = element('select');
      select.setAttribute('aria-label', tr('Définitions'));
      select.append(element('option', '', tr('Définition…')));
      for (const [l, h] of e.modes) {
        const opt = element('option', '', `${l}×${h}`);
        opt.value = `${l}x${h}`;
        select.append(opt);
      }
      select.addEventListener('change', () => {
        const [l, h] = select.value.split('x').map(Number);
        if (l && h) { r.largeur = l; r.hauteur = h; toutRedessiner(); }
      });
      ligne.append(select);
      corps.append(ligne);
    } else if (e.principal) {
      corps.append(element('p', 'discret', tr('Windows garde l\'écran principal en (0, 0) : déplacer les autres autour de lui.')));
    } else {
      corps.append(element('p', 'discret', tr('Écran réel : sa place seulement, jamais sa définition.')));
    }
  } else if (choisi.type === 'zone') {
    const zones = zonesAffichees();
    const r = zones[choisi.id];
    titre.textContent = `${libelleZone(choisi.id)} (${choisi.id})`;
    const modifiable = Boolean(zonesDuJeu());
    grille.append(...champ('x', r.x, (v) => { r.x = v; }, { desactive: !modifiable }),
      ...champ('y', r.y, (v) => { r.y = v; }, { desactive: !modifiable }),
      ...champ(tr('Largeur'), r.largeur, (v) => {
        const forme = formeImposee('zone', choisi.id, r);
        r.largeur = Math.max(ZONE_MIN, v);
        if (forme) r.hauteur = Math.round(r.largeur / forme);
      }, { desactive: !modifiable }),
      ...champ(tr('Hauteur'), r.hauteur, (v) => {
        const forme = formeImposee('zone', choisi.id, r);
        r.hauteur = Math.max(ZONE_MIN, v);
        if (forme) r.largeur = Math.round(r.hauteur * forme);
      }, { desactive: !modifiable }));
    corps.append(grille);
    if (modifiable) {
      const ligne = element('div', 'ligne');
      const forme = element('input');
      forme.type = 'checkbox';
      forme.id = 'garder-forme';
      forme.checked = garderForme;
      forme.addEventListener('change', () => { garderForme = forme.checked; });
      const lf = element('label', '', ' ' + tr('Garder la forme'));
      lf.htmlFor = 'garder-forme';
      const retirer = element('button', '', tr('Ne plus exporter'));
      retirer.type = 'button';
      retirer.addEventListener('click', () => {
        delete zonesDuJeu()[choisi.id];
        choisi = null;
        toutRedessiner();
      });
      ligne.append(forme, lf, retirer);
      corps.append(ligne);
      corps.append(element('p', 'discret',
        tr('Pas exporté, l\'écran reste dans le cockpit, sans image sur la tablette.')));
    } else {
      corps.append(element('p', 'discret', tr('Zones communes : cocher « Zones à part » pour en donner d\'autres à cet appareil.')));
    }
  } else {
    titre.textContent = tr('Fenêtre de DCS');
    corps.className = 'discret';
    corps.textContent = tr('Elle part du coin haut gauche de l\'écran principal : régler sa taille à droite.');
  }
}

// --------------------------------------------------------------- l'aperçu

let minuterieApercu = null;

function proposition() {
  return {
    ecrans: Object.entries(prop.ecrans).map(([id, r]) => ({ id, ...r })),
    fenetre: prop.fenetre,
    zones: prop.zones,
    par_appareil: prop.par_appareil,
  };
}

function demanderApercu() {
  clearTimeout(minuterieApercu);
  minuterieApercu = setTimeout(async () => {
    try {
      apercu = await appeler('/api/ecrans/apercu', proposition());
    } catch (e) {
      apercu = { changements: [], erreurs: [e.message], apercu: null };
    }
    afficherApercu();
    dessiner();
  }, 250);
}

function remplir(liste, lignes) {
  liste.textContent = '';
  for (const l of lignes) liste.append(element('li', '', l));
}

function afficherApercu() {
  remplir($('#erreurs'), apercu.erreurs || []);
  remplir($('#changements'), (apercu.changements || []).length ? apercu.changements
    : [tr('Rien : tout est comme enregistré.')]);
  const problemes = [];
  const a = apercu.apercu;
  if (a) {
    for (const z of a.zones) for (const p of z.problemes) problemes.push(`${libelleZone(z.nom)} : ${p}`);
    for (const [nom, zones] of Object.entries(a.par_appareil || {})) {
      for (const z of zones) {
        for (const p of z.problemes) problemes.push(`${nom} — ${libelleZone(z.nom)} : ${p}`);
      }
    }
    for (const e of a.ecrans) for (const p of e.problemes) problemes.push(`${e.nom} : ${p}`);
    if (a.kneeboard) for (const p of a.kneeboard.problemes) problemes.push(`${tr('Kneeboard')} : ${p}`);
  }
  $('#titre-problemes').hidden = !problemes.length;
  remplir($('#problemes'), problemes);
  // Des zones à part restées à l'ancienne place : les recaler d'un coup.
  const perdues = a ? Object.entries(a.par_appareil || {})
    .filter(([, zones]) => zones.some((z) => z.problemes.length)).map(([nom]) => nom) : [];
  if (perdues.length) {
    const li = element('li');
    const b = element('button', '', tr('Recaler les zones à part de {appareils} sur les zones communes',
      { appareils: perdues.join(', ') }));
    b.type = 'button';
    b.addEventListener('click', () => recalerAPart(perdues));
    li.append(b);
    $('#problemes').append(li);
  }
  $('#enregistrer').disabled = Boolean((apercu.erreurs || []).length);
}

function toutRedessiner(relireApercu = true) {
  $('#f-largeur').value = prop.fenetre ? prop.fenetre.largeur : '';
  $('#f-hauteur').value = prop.fenetre ? prop.fenetre.hauteur : '';
  majAideJeu();
  dessiner();
  majChoisi();
  if (relireApercu) demanderApercu();
  montrerSiBesoin();
}

// --------------------------------------------------------------- sur les vrais écrans

let minuterieMontrer = null;
let entretien = null;

function cadres() {
  const zones = zonesAffichees();
  return EXPORTS.filter((z) => zones[z]).map((z) => {
    const d = zoneDuProfil(z);
    return { zone: z, titre: libelleZone(z), ...zones[z], reperes: d ? d.reperes : {} };
  });
}

function montrerSiBesoin() {
  if (!montre) return;
  clearTimeout(minuterieMontrer);
  minuterieMontrer = setTimeout(() => {
    appeler('/api/ecrans/montrer', { cadres: cadres() }).catch(() => {});
  }, 60);
}

function basculerMontrer() {
  montre = !montre;
  $('#montrer').classList.toggle('actif', montre);
  $('#montrer').textContent = montre ? tr('Cacher des écrans') : tr('Montrer sur mes écrans');
  clearInterval(entretien);
  if (montre) {
    montrerSiBesoin();
    // Sans nouvelles, les cadres partent d'eux-mêmes (calage.DUREE_S) : on
    // les entretient tant que la page les montre.
    entretien = setInterval(montrerSiBesoin, 60000);
  } else {
    appeler('/api/ecrans/montrer', { cadres: [] }).catch(() => {});
  }
}

window.addEventListener('pagehide', () => {
  if (montre) {
    navigator.sendBeacon('/api/ecrans/montrer',
      new Blob([JSON.stringify({ cadres: [] })], { type: 'application/json' }));
  }
});

// --------------------------------------------------------------- enregistrer

function journal(lignes) {
  remplir($('#journal'), lignes);
}

let compteARebours = null;

function demanderConfirmation(secondes) {
  const barre = $('#confirmer');
  let reste = secondes;
  barre.hidden = false;
  const maj = () => {
    $('#confirmer-texte').textContent = tr('Garder ces écrans ? Retour comme avant dans {secondes} s.',
      { secondes: reste });
  };
  maj();
  clearInterval(compteARebours);
  compteARebours = setInterval(() => {
    reste -= 1;
    if (reste <= 0) {
      clearInterval(compteARebours);
      barre.hidden = true;
      journal([tr('Pas de confirmation : écrans remis comme avant.')]);
      setTimeout(relire, 1500);
      return;
    }
    maj();
  }, 1000);
}

async function confirmer(revenir) {
  clearInterval(compteARebours);
  $('#confirmer').hidden = true;
  try {
    journal((await appeler('/api/ecrans/garder', { revenir })).lignes);
  } catch (e) { journal([e.message]); }
  relire();
}

async function enregistrer() {
  const bouton = $('#enregistrer');
  bouton.disabled = true;
  journal([tr('Enregistrement…')]);
  try {
    const r = await appeler('/api/ecrans/enregistrer', proposition());
    journal(r.lignes);
    if (r.a_confirmer) demanderConfirmation(r.a_confirmer);
    else relire();
  } catch (e) {
    journal([e.message]);
  }
  bouton.disabled = false;
}

async function automatique() {
  if (!window.confirm(tr('Rendre la main à DCS Tablette ? Il remet l\'écran virtuel à sa place et réécrit « Tablette DCS » à sa façon.'))) return;
  journal([tr('Disposition automatique…')]);
  try {
    journal((await appeler('/api/ecrans/automatique', {})).lignes);
  } catch (e) { journal([e.message]); }
  relire();
}

async function changerVirtuels() {
  const nombre = Number($('#nb-virtuels').value);
  journal([tr('Écrans virtuels : pilote rechargé…')]);
  try {
    journal((await appeler('/api/ecrans/virtuels', { nombre })).lignes);
  } catch (e) { journal([e.message]); }
  relire();
}

// La fenêtre de DCS juste assez grande pour l'écran principal et les zones
// posées sur un écran (une zone à part restée hors des écrans ne compte pas).
function couvrir() {
  const p = principalRect();
  const ecrans = Object.values(prop.ecrans);
  const surUnEcran = (z) => ecrans.some((e) => commun(z, e) > 0);
  const rects = [p, ...Object.values(prop.zones).filter(surUnEcran)];
  for (const z of Object.values(prop.par_appareil)) rects.push(...Object.values(z).filter(surUnEcran));
  prop.fenetre = {
    largeur: Math.max(...rects.map((r) => r.x + r.largeur)),
    hauteur: Math.max(...rects.map((r) => r.y + r.hauteur)),
  };
  toutRedessiner();
}

// --------------------------------------------------------------- branchements

traduirePage();
$('#relire').addEventListener('click', relire);
$('#montrer').addEventListener('click', basculerMontrer);
$('#enregistrer').addEventListener('click', enregistrer);
$('#annuler').addEventListener('click', relire);
$('#automatique').addEventListener('click', automatique);
$('#changer-virtuels').addEventListener('click', changerVirtuels);
$('#couvrir').addEventListener('click', couvrir);
$('#garder').addEventListener('click', () => confirmer(false));
$('#revenir').addEventListener('click', () => confirmer(true));
$('#jeu').addEventListener('change', (e) => { jeu = e.target.value; choisi = null; toutRedessiner(false); });
$('#profil').addEventListener('change', (e) => {
  retenirMemoire('profil', e.target.value);
  toutRedessiner(false);
});
for (const [cle, id] of [['largeur', '#f-largeur'], ['hauteur', '#f-hauteur']]) {
  $(id).addEventListener('change', () => {
    const v = Math.round(Number($(id).value));
    if (Number.isFinite(v) && v > 0) {
      prop.fenetre = { ...(prop.fenetre || {}), [cle]: v };
      toutRedessiner();
    }
  });
}
window.addEventListener('resize', () => { if (prop) dessiner(); });
relire();
