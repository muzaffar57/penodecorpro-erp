#!/usr/bin/env node
/**
 * test_d122_ui.js — kech118 D BOSQICHI 2-qism (zip 122): TUNGI REJIM — sahifa JS i chizadigan ranglar (audit U-02; egasi
 * QARORI «To'liq tuzatilsin — har sahifa ranglari umumiy ranglar ro'yxatiga», QAYTA SO'RALMAYDI).
 *
 *   templates/base.html    — `matnRangi` (holat yozuvi rangi: tungi rejimda yorug' tus), grafik o'rami (Chart.js: tungi
 *                            rejimda standart yozuv / chiziq ranglari va sozlamadagi yorug' ranglar almashadi),
 *                            `toggleTheme` (rejim almashganda sahifa QAYTA YUKLANADI — JS chizgan ranglar yangi rejimda)
 *   templates/recipes.html — retsept tarkibi qatori (`ingredientRowHtml`): fon / belgi — ro'yxatdan, yozuv — `matnRangi`
 *
 * NIMA UCHUN KERAK
 *   CSS ranglari ro'yxatga o'tkazildi (tools/test_d122.py), lekin bir qism ranglarni sahifa JS i HISOBLAB yozadi (holat
 *   belgilari, grafiklar). Ular rejimni bilmasa — qorong'i kartada to'q yozuv / oq to'r chiziqlari qolardi (o'lchandi).
 * QANDAY ISHLAYDI: funksiyalar HTML dan JONLI o'qiladi, soxta DOM muhitida (data-theme bilan / siz) ishga tushiriladi.
 *   Topilmagan funksiya yoki istisno — yiqilgan tekshiruv (asl faylga qarshi ham QULAMAYDI).
 * ISHLATISH: node tools/test_d122_ui.js
 * Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
function oqi(nom) {
  try { return fs.readFileSync(path.join(ROOT, nom), 'utf8'); } catch (e) { return ''; }
}
const BASE = oqi('templates/base.html');
const RECIPES = oqi('templates/recipes.html');
const RANGLAR = oqi('static/ranglar.css');
const STYLE = oqi('static/style.css');

let OK = 0, FAIL = 0;
const FAILED = [];
function tekshir(label, shart, izoh) {
  if (shart) { OK++; console.log(`  ✓ ${label}`); }
  else {
    FAIL++; FAILED.push(label);
    console.log(`  ✗ ${label}${izoh ? '   — ' + izoh : ''}`);
  }
}
function bolim(t) { console.log(`\n${'='.repeat(66)}\n${t}\n${'='.repeat(66)}`); }
function qisqa(x) {
  let s;
  try { s = typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { s = String(x); }
  s = String(s);
  return s.length > 400 ? s.slice(0, 400) + '…' : s;
}

function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
  if (!m) return null;
  let i = m.index + m[0].length, d = 1;
  for (; i < src.length && d > 0; i++) {
    if (src[i] === '(') d++;
    else if (src[i] === ')') d--;
  }
  const j = src.indexOf('{', i);
  if (j < 0) return null;
  d = 0;
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(m.index, k + 1); }
  }
  return null;
}
// `window.toggleTheme = function() { … };` — tayinlangan funksiya
function tayin(src, nom) {
  const i = src.indexOf(nom + ' = function');
  if (i < 0) return null;
  const j = src.indexOf('{', i);
  let d = 0;
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(i, k + 1) + ';'; }
  }
  return null;
}

// ── WCAG kontrast ──
function rgb(h) {
  h = String(h).replace('#', '');
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}
function lum(h) {
  const [r, g, b] = rgb(h).map((v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function kontrast(a, b) {
  const x = lum(a), y = lum(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
function blok(css, bosh) {
  const i = css.indexOf(bosh);
  if (i < 0) return {};
  const j = css.indexOf('}', i);
  const r = {};
  for (const m of css.slice(i, j).matchAll(/--([\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})\s*;/g)) r[m[1]] = m[2].toUpperCase();
  return r;
}
const D_STYLE = blok(STYLE, 'html[data-theme="dark"] {');
const KARTA = D_STYLE.white || '#1E212A';
const TUNGI = blok(RANGLAR, 'html[data-theme="dark"] {');

function hujjat(tungi) {
  const attr = {};
  if (tungi) attr['data-theme'] = 'dark';
  return {
    documentElement: {
      getAttribute: (k) => (Object.prototype.hasOwnProperty.call(attr, k) ? attr[k] : null),
      setAttribute: (k, v) => { attr[k] = String(v); },
      removeAttribute: (k) => { delete attr[k]; },
    },
    getElementById: () => null,
    _attr: attr,
  };
}
function muhit(tungi, qosh) {
  const ctx = Object.assign({
    console, JSON, String, Number, Math, Object, Array, Error, RegExp, Set, Map, Promise,
    document: hujjat(tungi),
  }, qosh || {});
  ctx.window = ctx;
  vm.createContext(ctx);
  return ctx;
}
function ishga(ctx, kod, ifoda) {
  try {
    vm.runInContext(kod, ctx);
    return { xato: null, natija: vm.runInContext(ifoda, ctx) };
  } catch (e) {
    return { xato: String((e && e.message) || e), natija: undefined };
  }
}

// ══════════════════════════════════════════════════════════════
function matnBolimi() {
  bolim('base.html — matnRangi (holat yozuvi rangi)');
  const kod = olib(BASE, 'matnRangi');
  tekshir('M0 matnRangi topildi', !!kod);
  if (!kod) return;
  // holat ranglari (yorqin — chiziq / nuqta uchun) — sahifalar shularni beradi
  const holatlar = ['#22c55e', '#16a34a', '#f59e0b', '#d97706', '#ef4444', '#0ea5e9', '#94a3b8', '#9ca3af', '#b9783f',
    '#a86b36', '#b7770d', '#ca8a04', '#eab308', '#0891b2', '#06b6d4', '#db2777', '#ec4899', '#f97316', '#ea580c', '#3b82f6',
    '#64748b', '#bdc3c7', '#95a5a6', '#7f8c8d', '#10b981', '#0d9488', '#8b5cf6', '#6b7280', '#7C3AED', '#2563EB', '#1D4ED8',
    '#8E44AD', '#1e40af', '#9333ea'];
  const Y = muhit(false), T = muhit(true);
  let ry = ishga(Y, kod, `${JSON.stringify(holatlar)}.map(c => [matnRangi(c), matnRangi(c, 1)])`);
  let rt = ishga(T, kod, `${JSON.stringify(holatlar)}.map(c => [matnRangi(c), matnRangi(c, 1)])`);
  tekshir('M1 ikkala rejimda istisnosiz', !ry.xato && !rt.xato, qisqa([ry.xato, rt.xato]));
  if (ry.xato || rt.xato) return;
  // yorug' rejim — avvalgi (zip 121) natija: oq kartada ≥ 4.5 (o'zgarmagan)
  const yomonY = [];
  holatlar.forEach((c, i) => ry.natija[i].forEach((v) => { if (kontrast(v, '#FFFFFF') < 4.5) yomonY.push([c, v]); }));
  tekshir("M2 yorug' rejim O'ZGARMAGAN: #22C55E → #15803D, fonda #166534; har holat yozuvi oq kartada ≥ 4.5:1",
          ry.natija[0][0] === '#15803D' && ry.natija[0][1] === '#166534' && !yomonY.length, qisqa(yomonY));
  const yomonT = [];
  holatlar.forEach((c, i) => rt.natija[i].forEach((v) => {
    if (!/^#[0-9A-Fa-f]{6}$/.test(v) || kontrast(v, KARTA) < 4.5) yomonT.push([c, v, /^#/.test(v) ? kontrast(v, KARTA).toFixed(2) : '']);
  }));
  tekshir(`M3 tungi rejim: HAR holat yozuvi (oddiy va och fonli) qorong'i kartada (${KARTA}) ≥ 4.5:1 — yorug' tus`,
          !yomonT.length, qisqa(yomonT));
  tekshir('M4 tungi rejim: #22C55E → #4ADE80 (yashil — yorug\'), #EF4444 → #F87171, #B9783F → #D09A63 (oltin)',
          rt.natija[0][0] === '#4ADE80' && rt.natija[4][0] === '#F87171' && rt.natija[8][0] === '#D09A63',
          qisqa([rt.natija[0], rt.natija[4], rt.natija[8]]));
  // och-tusli fonlar (tungi rejimda qorong'i tus) ustida ham o'qiladi
  const ochFon = Object.entries(TUNGI).filter(([k]) => /^f-(fef2f2|fffbeb|f0fdf4|eff6ff|fdf2f8|fef3c7|dcfce7|fee2e2|f8f2eb)$/.test(k));
  const yomonF = [];
  holatlar.forEach((c, i) => ochFon.forEach(([k, f]) => { const v = rt.natija[i][1]; if (kontrast(v, f) < 4.5) yomonF.push([c, v, k]); }));
  tekshir("M5 tungi rejim: och fonli holat yozuvi (matnRangi(c, 1)) belgilar fonida (--f-fef2f2, --f-f0fdf4 … tungi) ≥ 4.5:1",
          ochFon.length >= 8 && !yomonF.length, qisqa([ochFon.length, yomonF.slice(0, 8)]));
  const r = ishga(T, kod, "[matnRangi('#123456'), matnRangi(''), matnRangi(null)]");
  tekshir("M6 tungi rejim: noma'lum rang o'zgarmaydi, bo'sh qiymat — xatosiz", !r.xato && r.natija[0] === '#123456',
          qisqa(r));
}

function grafikBolimi() {
  bolim('base.html — grafik o\'rami (Chart.js)');
  const m = /<script>\s*\/\/[^\n]*\n[\s\S]*?(\(function\(\) \{\s*let _realChart;[\s\S]*?\}\)\(\);)\s*<\/script>/.exec(BASE);
  tekshir("G0 grafik o'rami topildi", !!m);
  if (!m) return;
  const yasash = `
    function Soxta(ctx, config) { this.config = config; }
    Soxta.prototype.update = function () {};
    Soxta.defaults = { color: '#666', borderColor: 'rgba(0,0,0,0.1)' };
    window.Chart = Soxta;
    function sozlama() {
      return {
        type: 'bar',
        data: { labels: ['Yan'], datasets: [{ data: [1], backgroundColor: ['#fff', '#22C55E', '#F8F2EB'], borderColor: '#FFF' },
                                         { data: [2], backgroundColor: '#B9783F' }] },
        options: { plugins: { legend: { labels: { color: '#4B5563' } } },
                   scales: { x: { ticks: { color: '#9CA3AF' } }, y: { grid: { color: '#F0ECE6' }, ticks: { color: '#6B7280' } },
                             y2: { grid: { color: '#F0F1F3' } } } },
      };
    }
    const g = new Chart({}, sozlama());
    ({ c: g.config, d: { color: Chart.defaults.color, borderColor: Chart.defaults.borderColor } });`;
  const T = muhit(true), Y = muhit(false);
  const rt = ishga(T, m[1], yasash), ry = ishga(Y, m[1], yasash);
  tekshir('G1 ikkala rejimda grafik yaratildi (istisnosiz)', !rt.xato && !ry.xato, qisqa([rt.xato, ry.xato]));
  if (rt.xato || ry.xato) return;
  const ct = rt.natija.c, cy = ry.natija.c;
  tekshir("G2 tungi: standart yozuv rangi #A3A6B0, chiziq — rgba(255,255,255,0.10) (qorong'i kartaga mos)",
          rt.natija.d.color === '#A3A6B0' && rt.natija.d.borderColor === 'rgba(255,255,255,0.10)', qisqa(rt.natija.d));
  tekshir("G3 tungi: to'r chiziqlari (#F0ECE6, #F0F1F3) → #2E3240, o'q / afsona yozuvlari (#9CA3AF, #6B7280, #4B5563) → " +
          "yorug' tus, oq bo'lak chegarasi / ustun (#fff, #FFF) → karta rangi, och ustun (#F8F2EB) → #5A4630",
          ct.options.scales.y.grid.color === '#2E3240' && ct.options.scales.y2.grid.color === '#2E3240'
          && ct.options.scales.x.ticks.color === '#A3A6B0' && ct.options.scales.y.ticks.color === '#A3A6B0'
          && ct.options.plugins.legend.labels.color === '#C9CBD2'
          && ct.data.datasets[0].backgroundColor[0] === '#1E212A' && ct.data.datasets[0].borderColor === '#1E212A'
          && ct.data.datasets[0].backgroundColor[2] === '#5A4630',
          qisqa(ct));
  tekshir("G4 tungi: to'yingan ranglar (#22C55E, #B9783F) O'ZGARMAYDI (ma'no beradi)",
          ct.data.datasets[0].backgroundColor[1] === '#22C55E' && ct.data.datasets[1].backgroundColor === '#B9783F', qisqa(ct.data));
  tekshir("G5 yorug' rejim O'ZGARMAGAN: sozlama aynan, standart ranglar tegilmagan",
          cy.options.scales.y.grid.color === '#F0ECE6' && cy.options.plugins.legend.labels.color === '#4B5563'
          && cy.data.datasets[0].backgroundColor[0] === '#fff' && cy.data.datasets[0].backgroundColor[2] === '#F8F2EB'
          && ry.natija.d.color === '#666' && ry.natija.d.borderColor === 'rgba(0,0,0,0.1)', qisqa([cy, ry.natija.d]));
}

function rejimBolimi() {
  bolim('base.html — rejim tugmasi (toggleTheme)');
  const kod = tayin(BASE, 'window.toggleTheme');
  const ikon = olib(BASE, 'applyThemeIcon');
  tekshir('R0 toggleTheme va applyThemeIcon topildi', !!kod && !!ikon);
  if (!kod || !ikon) return;
  for (const tungi of [false, true]) {
    const saqlangan = {}, yuklash = [];
    const ctx = muhit(tungi, {
      localStorage: { setItem: (k, v) => { saqlangan[k] = v; }, getItem: (k) => saqlangan[k] || null },
      location: { reload: () => yuklash.push(1) },
    });
    const r = ishga(ctx, ikon + '\n' + kod, 'toggleTheme(); document.documentElement.getAttribute("data-theme")');
    const kutil = tungi ? null : 'dark';
    tekshir(`R${tungi ? 2 : 1} ${tungi ? 'tungi → yorug\'' : 'yorug\' → tungi'}: rejim almashdi, eslab qolindi ` +
            `(«${tungi ? 'light' : 'dark'}»), sahifa BIR marta qayta yuklandi (JS chizgan ranglar yangi rejimda)`,
            !r.xato && r.natija === kutil && saqlangan.theme === (tungi ? 'light' : 'dark') && yuklash.length === 1,
            qisqa([r, saqlangan, yuklash]));
  }
}

function retseptBolimi() {
  bolim('recipes.html — retsept tarkibi qatori (ingredientRowHtml)');
  const kod = ['escapeHtml', 'matnRangi', 'recpCatStyle', 'ingredientRowHtml'].map((n) => olib(n === 'escapeHtml' || n === 'matnRangi' ? BASE : RECIPES, n));
  const jad = /const RECP_CAT_STYLE = \{[\s\S]*?\n\};/.exec(RECIPES);
  tekshir('E0 funksiyalar va RECP_CAT_STYLE topildi', kod.every(Boolean) && !!jad);
  if (!kod.every(Boolean) || !jad) return;
  for (const tungi of [false, true]) {
    const ctx = muhit(tungi);
    const r = ishga(ctx, jad[0] + '\n' + kod.join('\n'),
      `["Gips", "Penoplast", "Bazalt", "Kimyoviy qo'shimchalar", "Qattiq qotishmalar", null].map(c => ingredientRowHtml('n', 0, {id: 1, item_name: 'X', category: c}, 2))`);
    if (r.xato) { tekshir(`E${tungi ? 2 : 1} qator chizildi`, false, r.xato); continue; }
    const yomon = [];
    r.natija.forEach((h) => {
      const ikon = /recp-ing-icon" style="background:(var\(--f-[0-9a-f]{6}\));color:(var\(--m-[0-9a-f]{6}\))"/.exec(h);
      const pill = /recp-cat-pill" style="background:(var\(--f-[0-9a-f]{6}\));color:(#[0-9A-Fa-f]{6})"/.exec(h);
      if (!ikon || !pill) { yomon.push(h.slice(0, 200)); return; }
      if (tungi && kontrast(pill[2], TUNGI[pill[1].slice(6, -1)] || '#FFFFFF') < 4.5) yomon.push([pill[1], pill[2]]);
      if (!tungi && kontrast(pill[2], '#' + pill[1].slice(8, -1)) < 4.5) yomon.push([pill[1], pill[2]]);
    });
    tekshir(`E${tungi ? 2 : 1} ${tungi ? 'tungi' : 'yorug\''}: belgi foni / rangi — ro'yxatdan (var(--f-…) / var(--m-…)), ` +
            `kategoriya yozuvi o'z fonida ≥ 4.5:1 (6 kategoriya)`, !yomon.length, qisqa(yomon));
  }
}

(function () {
  try {
    matnBolimi();
    grafikBolimi();
    rejimBolimi();
    retseptBolimi();
  } catch (e) {
    tekshir('kutilmagan istisno', false, String((e && e.stack) || e).slice(0, 400));
  }
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})();
