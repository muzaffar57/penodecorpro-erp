#!/usr/bin/env node
/**
 * test_sxema_n4_ui.js — kech144 (zip 172): N4 — «Tizim jurnallari → 🩺 Tizim salomatligi» dagi «🧱 Baza tuzilishi» bloki va
 * tekshiruv yuklanmasa sababi.
 *
 *   templates/logs.html — `runHealthCheck` (javob holati — `yukOl`; xatoda sabab — `yukXatoMatn`), `sxemaHtml` (server
 *                         `database.sxema_farqlari`: farqlar, ishga tushishda kengaytirilgan ustunlar, kengaytirib bo'lmaganlar)
 *
 * NIMA UCHUN KERAK: production 12.10 11:47 xatosi (jurnal ustuni VARCHAR(255)) sinovlarda hech qachon ko'rinmagan — baza tuzilishi
 *   kod bilan farq qilishini faqat production ning o'zi ko'rsata oladi. Platforma egasi «Tekshirish» ni bosganda baza mosmi,
 *   ishga tushishda nima kengaytirilgani (qachon, nimadan nimaga) va qo'lda ko'rish kerak farqlar ko'rinishi kerak. Ilgari
 *   `fetch` javobi tekshirilmasdi: 500 / 403 ham `json()` qilinib, bo'sh natija yoki «Xato yuz berdi» chiqardi (sababsiz).
 * QANDAY ISHLAYDI: funksiyalar HTML dan JONLI o'qiladi (Jinja teglari olib tashlanadi), soxta DOM / fetch muhitida ishga
 *   tushiriladi. Topilmagan funksiya yoki istisno — yiqilgan tekshiruv (asl faylga qarshi ham QULAMAYDI).
 * ISHLATISH: node tools/test_sxema_n4_ui.js        Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
function oqi(nom) {
  try { return fs.readFileSync(path.join(ROOT, 'templates', nom), 'utf8'); } catch (e) { return ''; }
}
const LOGS = oqi('logs.html');
const BASE = oqi('base.html');

let OK = 0, FAIL = 0;
const FAILED = [];
function qisqa(x) {
  let s;
  try { s = typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { s = String(x); }
  s = String(s);
  return s.length > 500 ? s.slice(0, 500) + '…' : s;
}
function tekshir(label, shart, izoh) {
  let s = false;
  try { s = typeof shart === 'function' ? !!shart() : !!shart; } catch (e) { s = false; izoh = String(e); }
  if (s) { OK++; console.log(`  ✓ ${label}`); }
  else {
    FAIL++; FAILED.push(label);
    console.log(`  ✗ ${label}${izoh !== undefined ? '   — ' + qisqa(izoh) : ''}`);
  }
}
function bolim(t) { console.log(`\n--- ${t} ---`); }

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
function jinjasiz(s) {
  // `{% if %}A{% else %}B{% endif %}` → A (platforma egasi); qolgan teglar olib tashlanadi
  return String(s).replace(/\{%\s*if[^%]*%\}([\s\S]*?)(\{%\s*else\s*%\}[\s\S]*?)?\{%\s*endif\s*%\}/g, '$1')
    .replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');
}
// kech160 (zip 225, MOSLANDI): bloklar shtorkada — `shtorkaHtml` (base.html; eski shablonda yo'q — o'tkaziladi)
const YORDAMCHI_NOMLAR = ['shtorkaHtml', 'escapeHtml', 'tkMs', 'tkDate', 'tkSana', 'tkVaqt', 'tkSanaVaqt', 'tkToliq', 'xatoSababi', 'yukXato', 'yukOl',
  'yukSabab', 'yukXatoMatn', 'yukSessiyaKor'];
const YORDAMCHI = YORDAMCHI_NOMLAR.map(n => olib(BASE, n)).filter(Boolean).join('\n');
const SAHIFA = ['runHealthCheck', 'sxemaHtml'].map(n => olib(LOGS, n)).filter(Boolean).map(jinjasiz).join('\n');

function element(id) {
  return {
    id, value: '', textContent: '', innerHTML: '', style: {}, dataset: {}, disabled: false, hidden: true,
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    appendChild() {}, querySelector() { return null; }, querySelectorAll() { return []; }, addEventListener() {}, focus() {},
  };
}
function muhit(javob) {
  const ELS = {};
  const XATOLAR = [];
  const ctx = {
    Math, JSON, Promise, Object, Array, String, Number, parseInt, parseFloat, isNaN, RegExp, Date, Error, Intl,
    console: { log() {}, warn() {}, error(...a) { XATOLAR.push(a.map(String).join(' ')); } },
    setTimeout: (f) => { try { f(); } catch (e) { /* jim */ } return 0; }, clearTimeout() {},
    location: { href: '', reload() {} },
    document: {
      getElementById(id) { if (!(id in ELS)) ELS[id] = element(id); return ELS[id]; },
      querySelector() { return null; }, querySelectorAll() { return []; }, createElement() { return element('?'); },
      body: element('body'), addEventListener() {},
    },
    fetch: async (url) => {
      if (typeof javob === 'function') return javob(String(url));
      return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(javob)), text: async () => JSON.stringify(javob) };
    },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(YORDAMCHI + '\n' + SAHIFA, ctx);
  return { ctx, el: (id) => ctx.document.getElementById(id), XATOLAR };
}
async function yurgiz(m) {
  const p = vm.runInContext('(async () => { await runHealthCheck(); })()', m.ctx);
  return await Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('vaqt tugadi')), 3000))]);
}
async function sinov(nom, fn) {
  try { await fn(); } catch (e) { tekshir(`${nom} — istisnosiz`, false, String(e && e.stack || e)); }
}
function bosh(s) { return String(s).replace(/[  ]/g, ' ').replace(/&#39;/g, "'"); }   // escapeHtml «'» → &#39;

const ASOS = {
  checked_at: '2026-10-13T06:20:00', total_checks: 13, issues_found: 0, issues: [], check_errors: [], is_platform_admin: true,
  financial: { issues_found: 0, issues: [] },
};
const KENG = [
  { jadval: 'activity_logs', ustun: 'new_value', vaqt: '2026-10-13T06:10:58+00:00', oldin: 'VARCHAR(255)', keyin: 'TEXT' },
  { jadval: 'orders', ustun: 'ochirish_yopish_json', vaqt: '2026-10-13T06:10:58+00:00', oldin: 'VARCHAR(255)', keyin: 'TEXT' },
];

(async () => {
  bolim('S. Statik');
  tekshir('S1 logs.html: `runHealthCheck` va `sxemaHtml` topildi', !!olib(LOGS, 'runHealthCheck') && !!olib(LOGS, 'sxemaHtml'));
  tekshir("S2 so'rov `yukOl('/api/system/health-check')` orqali (javob holati tekshiriladi; asl: `fetch` + `json()` holatsiz)",
    /yukOl\(\s*'\/api\/system\/health-check'\s*\)/.test(olib(LOGS, 'runHealthCheck') || ''));
  tekshir('S3 blok faqat texnik qism ko\'rinadigan (platforma egasi) javobda: `!d.technical_hidden && d.sxema`',
    /!d\.technical_hidden && d\.sxema\) html \+= sxemaHtml\(d\.sxema\)/.test(olib(LOGS, 'runHealthCheck') || ''));

  bolim('U. «🧱 Baza tuzilishi» bloki');
  await sinov('U1', async () => {
    const m = muhit(Object.assign({}, ASOS, { sxema: { tekshirildi: true, jadvallar: 59, ustunlar: 727, farqlar: [], kengaytirilgan: KENG,
      ishga_tushish: { vaqt: '2026-10-13T06:10:58+00:00', xatolar: [] } } }));
    await yurgiz(m);
    const h = bosh(m.el('health-results').innerHTML);
    tekshir('U1 mos baza: «Baza tuzilishi kod bilan mos», «59 ta jadval, 727 ta ustun tekshirildi»', h.includes('🧱 Baza tuzilishi')
      && h.includes('Baza tuzilishi kod bilan mos') && h.includes('59 ta jadval, 727 ta ustun tekshirildi'), h.slice(0, 600));
    tekshir("U1b ishga tushishda kengaytirilgan 2 ta ustun — «activity_logs.new_value: VARCHAR(255) → TEXT» va Toshkent vaqti "
      + '(13.10.2026, 11:10:58)', h.includes('Ishga tushishda kengaytirilgan ustunlar (2 ta)') && h.includes('activity_logs</code>') === false
      && h.includes('activity_logs.new_value') && h.includes('VARCHAR(255) → TEXT') && h.includes('orders.ochirish_yopish_json')
      && h.includes('13.10.2026, 11:10:58'), h.slice(h.indexOf('🔧'), h.indexOf('🔧') + 700));
    tekshir("U1c tugma qayta yoqildi, matni «Tekshirish»", m.el('health-check-btn').disabled === false
      && m.el('health-check-btn').textContent === 'Tekshirish');
    tekshir('U1d moliyaviy qism ham chizildi (blok boshqa qismlarni buzmaydi)', h.includes("Hisob-kitoblar to'g'ri!")
      && h.includes('Hammasi joyida!'), h.slice(0, 300));
  });
  await sinov('U2', async () => {
    const m = muhit(Object.assign({}, ASOS, { sxema: { tekshirildi: true, jadvallar: 59, ustunlar: 727, kengaytirilgan: [],
      ishga_tushish: { xatolar: [] }, farqlar: [
        { jadval: 'finished_products', ustun: 'production_status', kodda: 'ENUM productionstatus', bazada: 'VARCHAR(11)', tur: 'qolda',
          izoh: "tur boshqa — avtomatik o'zgartirilmaydi (qiymatlar o'zgarishi mumkin)" },
        { jadval: 'orders', ustun: 'loy_manba_json', kodda: 'TEXT', bazada: 'VARCHAR(255)', tur: 'kengaytirish',
          izoh: "kengaytiriladi (qiymatlar o'zgarmaydi)" },
        { jadval: '<img src=x onerror=alert(1)>', ustun: 'u<b>', kodda: '<i>', bazada: 'x"y', tur: 'qolda', izoh: '<script>' },
      ] } }));
    await yurgiz(m);
    const h = bosh(m.el('health-results').innerHTML);
    tekshir('U2 farqlar: «3 ta farq topildi (727 ta ustundan)», har biri «Kodda / Bazada»', h.includes('3 ta farq topildi (727 ta ustundan)')
      && h.includes('Kodda: <b>ENUM productionstatus</b> · Bazada: <b>VARCHAR(11)</b>') && h.includes('finished_products.production_status'),
      h.slice(0, 900));
    tekshir("U2b «qo'lda» va «kengaytirish» farqlari ajratilgan (qo'lda — «avtomatik o'zgartirilmaydi», kengaytirish — «server qayta ishga "
      + "tushganda avtomatik kengaytiriladi»)", h.includes("Qo'lda ko'rish kerak — avtomatik o'zgartirilmaydi")
      && h.includes('Server qayta ishga tushganda avtomatik kengaytiriladi'), h.slice(0, 1500));
    tekshir('U2c server matni HTML sifatida ishlatilmaydi (escape)', !h.includes('<img src=x') && h.includes('&lt;img src=x onerror=alert(1)&gt;')
      && !h.includes('<script>') && h.includes('&lt;script&gt;') && !h.includes('<b>u') , h.slice(h.indexOf('&lt;img') - 100, h.indexOf('&lt;img') + 400));
    tekshir("U2d «Baza tuzilishi kod bilan mos» chiqmaydi (farq bor)", !h.includes('Baza tuzilishi kod bilan mos'));
  });
  await sinov('U3', async () => {
    const m = muhit(Object.assign({}, ASOS, { sxema: { dialect: 'sqlite', tekshirildi: false,
      izoh: 'SQLite ustun uzunligi va turini tekshirmaydi — sxema tekshiruvi faqat PostgreSQL da' } }));
    await yurgiz(m);
    const h = bosh(m.el('health-results').innerHTML);
    tekshir('U3 tekshirilmagan (SQLite) — sababi ko\'rinadi, «mos» deyilmaydi', h.includes('SQLite ustun uzunligi va turini tekshirmaydi')
      && !h.includes('kod bilan mos'), h.slice(0, 600));
  });
  await sinov('U4', async () => {
    const m = muhit(Object.assign({}, ASOS, { sxema: { tekshirildi: true, jadvallar: 59, ustunlar: 727, farqlar: [
      { jadval: 'return_items', ustun: 'mrp_ozod', kodda: 'TEXT', bazada: 'VARCHAR(255)', tur: 'kengaytirish', izoh: 'kengaytiriladi' }],
      kengaytirilgan: [], ishga_tushish: { xatolar: [{ jadval: 'return_items', ustun: 'mrp_ozod',
        xato: 'cannot alter type of a column used by a view or rule' }] } } }));
    await yurgiz(m);
    const h = bosh(m.el('health-results').innerHTML);
    tekshir("U4 ishga tushishda kengaytirib bo'lmagan ustun — sababi bilan («keyingi ishga tushishda qayta urinadi»)",
      h.includes("Ishga tushishda kengaytirib bo'lmadi") && h.includes('return_items.mrp_ozod') && h.includes('used by a view or rule'),
      h.slice(0, 1200));
  });
  await sinov('U5', async () => {
    const m = muhit(Object.assign({}, ASOS, { technical_hidden: true, is_platform_admin: false, sxema: { tekshirildi: true, farqlar: [] } }));
    await yurgiz(m);
    const h = bosh(m.el('health-results').innerHTML);
    tekshir('U5 korxona admini (texnik qism yashirin) — blok yo\'q', !h.includes('Baza tuzilishi') && h.includes('Moliyaviy izchillik'),
      h.slice(0, 400));
  });
  await sinov('U6', async () => {
    const m = muhit(Object.assign({}, ASOS));
    await yurgiz(m);
    const h = bosh(m.el('health-results').innerHTML);
    tekshir('U6 eski server (javobda `sxema` yo\'q) — blok yo\'q, qolgani avvalgidek', !h.includes('Baza tuzilishi') && h.includes('Hammasi joyida!'),
      h.slice(0, 400));
  });

  bolim('Y. Tekshiruv yuklanmasa — sabab (asl: «Xato yuz berdi» yoki xato javob «natija» sifatida)');
  const HOLLAR = [
    ['Y1 server 500 (HTML)', () => ({ ok: false, status: 500, json: async () => { throw new Error('json emas'); }, text: async () => '<html>' }),
      'Tekshiruv natijasi yuklanmadi — server javob bermadi'],
    ['Y2 403', () => ({ ok: false, status: 403, json: async () => ({ detail: 'Ruxsat yo\'q' }), text: async () => '' }),
      "Tekshiruv natijasi yuklanmadi — ko'rish ruxsati yo'q"],
    ['Y3 tarmoq', () => { throw new TypeError('Failed to fetch'); }, "Tekshiruv natijasi yuklanmadi — internet aloqasi yo'q"],
    ['Y4 401', () => ({ ok: false, status: 401, json: async () => ({ detail: 'Kirish kerak' }), text: async () => '' }),
      'Tekshiruv natijasi yuklanmadi — kirish muddati tugagan'],
    // JSON tanali 500 — holat tekshirilmasa xato javob «natija» bo'lib chiziladi («Tekshirilgan sana: · undefined ta joy»)
    ['Y5 server 500 (JSON)', () => ({ ok: false, status: 500, json: async () => ({ detail: 'Serverda kutilmagan xato yuz berdi' }),
      text: async () => '' }), 'Tekshiruv natijasi yuklanmadi — server javob bermadi'],
  ];
  for (const [nom, javob, kutilgan] of HOLLAR) {
    await sinov(nom, async () => {
      const m = muhit(javob);
      await yurgiz(m);
      const h = bosh(m.el('health-results').innerHTML);
      tekshir(`${nom} — «${kutilgan}», tugma qayta yoqildi`, h.includes(kutilgan) && !h.includes('Hammasi joyida')
        && !h.includes('Tekshirilgan sana')
        && m.el('health-check-btn').disabled === false && m.el('health-check-btn').textContent === 'Tekshirish', h.slice(0, 300));
    });
  }

  console.log(`\nNATIJA: o'tdi = ${OK}, yiqildi = ${FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach(f => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})();
