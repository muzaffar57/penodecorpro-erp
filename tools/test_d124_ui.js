#!/usr/bin/env node
/**
 * test_d124_ui.js — kech118 D BOSQICHI 4-qism (zip 124): SAHIFALAR VAZIFASI — sahifa JS xatti-harakati (egasi QARORI «Vazifalar
 * ajratilsin» G1-09, G2-17; 01.10 «Tezkor kirish — 3–4 asosiy amal»; QAYTA SO'RALMAYDI).
 *
 *   templates/orders.html   — `buyurtmaniParamdanOch` («/orders?order=ID»: guruh ochiladi, qator tanlanadi; ro'yxatda yo'q —
 *                             «Barchasi» bilan qayta; topilmasa — xabar), `checkForDraftOnLoad` («?yangi=1» — yangi forma)
 *   templates/projects.html — `renderOrders` (qator → /orders?order=ID, summa KELISHILGAN, «+ Yangi buyurtma» — har loyihada,
 *                             ruxsatga qarab; 403 — tushunarli)
 *   templates/dashboard.html — `buildStatusChart` (doira afsonasi: holat va soni; bo'sh — «Buyurtma yo'q»)
 *   templates/home.html     — `loadTasks` («Bugungi vazifalar» — Dashboard dan ko'chdi)
 *   templates/returns.html  — «?brak=1» → bitta brak oynasi ochiladi
 *
 * NIMA UCHUN KERAK: loyihadagi buyurtma qatori Buyurtmalar sahifasini hech narsa tanlanmagan holda ochardi (buyurtmani qayta
 *   qidirish kerak edi), summa chegirmasiz edi; Bosh sahifa / Dashboard bloklari takrorlanardi.
 * QANDAY ISHLAYDI: funksiyalar HTML dan JONLI o'qiladi (Jinja — birinchi tarmoq), soxta DOM muhitida ishga tushiriladi.
 * ISHLATISH: node tools/test_d124_ui.js
 * Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
function oqi(nom) {
  try { return fs.readFileSync(path.join(ROOT, 'templates', nom), 'utf8'); } catch (e) { return ''; }
}
const ORDERS = oqi('orders.html');
const PROJECTS = oqi('projects.html');
const DASHBOARD = oqi('dashboard.html');
const HOME = oqi('home.html');
const RETURNS = oqi('returns.html');
const BASE = oqi('base.html');

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
  return s.length > 500 ? s.slice(0, 500) + '…' : s;
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
function jinja(kod) {
  if (kod === null) return null;
  return kod.replace(/\{%\s*if[^%]*%\}([\s\S]*?)(?:\{%\s*else\s*%\}[\s\S]*?)?\{%\s*endif\s*%\}/g, '$1')
    .replace(/\{%[\s\S]*?%\}/g, '');
}
function element(v) {
  const el = { value: v === undefined ? '' : v, innerHTML: '', textContent: '', style: {}, dataset: {}, _scroll: 0 };
  el.scrollIntoView = () => { el._scroll++; };
  return el;
}
function ctxYasa(qosh) {
  const ctx = Object.assign({ console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, Array, Object, RegExp,
    URLSearchParams, Intl }, qosh || {});
  vm.createContext(ctx);
  return ctx;
}
const ESC = olib(BASE, 'escapeHtml');

// ══════════════════════════════════════════════════════════════
async function buyurtmaBolimi() {
  bolim("orders.html — «/orders?order=ID» va «?yangi=1»");
  const kod = olib(ORDERS, 'buyurtmaniParamdanOch');
  tekshir('B0 buyurtmaniParamdanOch topildi', !!kod);
  if (!kod) return;
  function sina(qidiruv, qatorBor) {
    const ch = { open: [], select: [], replace: [], msg: [], hist: [] };
    const el = element(''); el.dataset = { projectId: '17' };
    const ctx = ctxYasa({
      document: { querySelector: (sel) => (qatorBor && sel === '.ord-list #oi-' + qatorBor ? el : null) },
      window: { location: { pathname: '/orders', replace: (u) => ch.replace.push(u) } },
      history: { replaceState: (a, b, u) => ch.hist.push(u) },
      openProject: (p) => ch.open.push(p), selectOrder: (id, e) => ch.select.push([id, e === el]),
      showMsg: (t, tur) => ch.msg.push([t, tur]),
    });
    vm.runInContext(kod, ctx);
    const r = vm.runInContext(`buyurtmaniParamdanOch(new URLSearchParams(${JSON.stringify(qidiruv)}))`, ctx);
    return { r, ch, el };
  }
  let t = sina('?order=5', '5');
  tekshir("B1 qator bor → guruh ochiladi (loyiha 17), AYNAN shu buyurtma tanlanadi (5, shu qator), ko'rinishga suriladi, URL tozalanadi",
          t.r === true && qisqa(t.ch.open) === '["17"]' && qisqa(t.ch.select) === '[[5,true]]' && t.el._scroll === 1
          && qisqa(t.ch.hist) === '["/orders"]' && !t.ch.replace.length, qisqa([t.r, t.ch]));
  t = sina('?order=5', null);
  tekshir("B2 ro'yxatda yo'q (90 kundan eski) → «/orders?show_all=true&order=5» bilan qayta ochiladi",
          t.r === true && qisqa(t.ch.replace) === '["/orders?show_all=true&order=5"]' && !t.ch.select.length, qisqa(t.ch));
  t = sina('?show_all=true&order=5', null);
  tekshir("B3 «Barchasi» da ham yo'q → «Buyurtma topilmadi …» xabari, qayta yo'naltirish YO'Q (cheksiz aylanish yo'q)",
          t.r === true && !t.ch.replace.length && t.ch.msg.length === 1 && t.ch.msg[0][1] === 'error'
          && qisqa(t.ch.hist) === '["/orders?show_all=true"]', qisqa(t.ch));
  t = sina('?order=5x', '5x');
  tekshir("B4 noto'g'ri ID («5x») — hech narsa tanlanmaydi, yo'naltirilmaydi", t.r === true && !t.ch.select.length
          && !t.ch.replace.length, qisqa(t.ch));
  t = sina('', null);
  tekshir("B5 parametr yo'q → false (odatdagidek davom etadi)", t.r === false && !t.ch.hist.length, qisqa(t));
  // ?yangi=1
  const ck = olib(ORDERS, 'checkForDraftOnLoad');
  tekshir('B6 checkForDraftOnLoad topildi', !!ck);
  if (ck) {
    const ch = { forma: 0, tiklash: 0, hist: [] };
    const ctx = ctxYasa({
      window: { location: { search: '?yangi=1', pathname: '/orders' } }, history: { replaceState: (a, b, u) => ch.hist.push(u) },
      buyurtmaniParamdanOch: () => false, showNewForm: () => { ch.forma++; }, document: { getElementById: () => null },
      localStorage: { getItem: () => { ch.tiklash++; return null; } }, ORDER_DRAFT_LS_KEY: 'x', restoreDraftLS: () => {}, clearDraftLS: () => {},
    });
    vm.runInContext(ck, ctx);
    let x = null;
    try { vm.runInContext('checkForDraftOnLoad()', ctx); } catch (e) { x = String(e.message || e); }
    tekshir("B7 «?yangi=1» → yangi buyurtma formasi BIR marta, qoralama tiklanmaydi, URL tozalanadi",
            !x && ch.forma === 1 && ch.tiklash === 0 && qisqa(ch.hist) === '["/orders"]', x || qisqa(ch));
  }
}

async function loyihaBolimi() {
  bolim("projects.html — loyihaning buyurtmalari (renderOrders)");
  const kod = ['fmt', 'loyihaBuyurtmaSummasi', 'renderOrders'].map((n) => olib(PROJECTS, n));
  const tk = olib(BASE, 'tkSana');
  tekshir('L0 fmt, loyihaBuyurtmaSummasi, renderOrders topildi', kod.every(Boolean));
  if (!kod.every(Boolean)) return;
  async function sina(yaratadi, javob) {
    const tab = element('');
    const ctx = ctxYasa({
      document: { getElementById: (id) => (id === 'tabContent' ? tab : null) },
      fetch: async () => ({ ok: javob.status === 200, status: javob.status, json: async () => javob.data }),
      selectedProjId: 3, BUYURTMA_YARATADI: yaratadi, tkSana: (v) => String(v).slice(0, 10),
    });
    vm.runInContext(ESC + '\n' + kod.join('\n'), ctx);
    await vm.runInContext('renderOrders({})', ctx);
    return tab.innerHTML;
  }
  const B = [{ id: 5, order_number: 'ORD-5', status: 'new', agreed_amount: 864000, total_amount: 900000, created_at: '2026-09-01' },
    { id: 6, order_number: 'ORD-<6>', status: 'ready', agreed_amount: null, total_amount: 500000, created_at: '2026-09-02' }];
  let h = await sina(true, { status: 200, data: B });
  const bosh = h.replace(/\s+/g, ' ');
  tekshir("L1 qator → /orders?order=5 va /orders?order=6 (AYNAN shu buyurtma)",
          h.includes("window.location.href='/orders?order=5'") && h.includes("window.location.href='/orders?order=6'")
          && !h.includes("href='/orders'\""), qisqa(bosh));
  tekshir("L2 summa — KELISHILGAN (864 000, chegirmasiz 900 000 EMAS); kelishilgan yo'q bo'lsa — jami (500 000)",
          /864\s000 so'm/.test(bosh) && !/900\s000 so'm/.test(bosh) && /500\s000 so'm/.test(bosh), qisqa(bosh));
  tekshir("L3 buyurtmasi BOR loyihada ham «+ Yangi buyurtma» (yaratish ruxsati bilan), raqam escape qilingan",
          h.includes('+ Yangi buyurtma') && h.includes("/orders?new_for_project=3") && h.includes('ORD-&lt;6&gt;'), qisqa(bosh));
  h = await sina(false, { status: 200, data: B });
  tekshir("L4 yaratish ruxsati yo'q — «+ Yangi buyurtma» YO'Q", !h.includes('+ Yangi buyurtma') && h.includes('/orders?order=5'));
  h = await sina(true, { status: 200, data: [] });
  tekshir("L5 bo'sh loyiha — «Buyurtma yo'q» va «+ Yangi buyurtma»", h.includes("Buyurtma yo'q") && h.includes('+ Yangi buyurtma'));
  h = await sina(true, { status: 403, data: { detail: 'x' } });
  tekshir("L6 403 — «Buyurtmalarni ko'rishga ruxsat yo'q» (ilgari «Buyurtma yo'q» deb noto'g'ri yozilardi)",
          h.replace(/&#39;/g, "'").includes("Buyurtmalarni ko'rishga ruxsat yo'q") && !h.includes("Buyurtma yo'q<"), qisqa(h));
}

async function dashboardBolimi() {
  bolim("dashboard.html — «Buyurtmalar holati» doirasi afsona bilan (buildStatusChart)");
  const kod = olib(DASHBOARD, 'buildStatusChart');
  const st = /const COLORS=\{[^\n]*\};\nconst ST_COLORS=\{[^\n]*\};\nconst ST_LABELS=\{[^\n]*\};/.exec(DASHBOARD);
  tekshir('S0 buildStatusChart va holat ro\'yxatlari topildi', !!kod && !!st);
  if (!kod || !st) return;
  function sina(statuses) {
    const leg = element('');
    const ctx = ctxYasa({
      document: { getElementById: (id) => (id === 'statusLegend' ? leg : { getContext: () => ({}) }) },
      Chart: function () { this.destroy = () => {}; }, sC: null,
    });
    vm.runInContext(ESC + '\n' + st[0] + '\nvar sC = null;\n' + kod, ctx);
    vm.runInContext(`buildStatusChart(${JSON.stringify(statuses)})`, ctx);
    return leg.innerHTML.replace(/\s+/g, ' ');
  }
  let h = sina({ new: 2, in_progress: 5, ready: 20, delivered: 0 });
  tekshir("S1 afsona: «Yangi 2 ta», «Jarayonda 5 ta», «Tayyor 20 ta»; 0 tasi ko'rsatilmaydi",
          /Yangi<\/span> <b>2 ta<\/b>/.test(h) && /Jarayonda<\/span> <b>5 ta<\/b>/.test(h) && /Tayyor<\/span> <b>20 ta<\/b>/.test(h)
          && !h.includes('Yetkazildi'), qisqa(h));
  h = sina({ new: 0 });
  tekshir("S2 buyurtma yo'q — «Buyurtma yo'q»", h.includes("Buyurtma yo'q"), qisqa(h));
}

async function boshBolimi() {
  bolim("home.html — «Bugungi vazifalar» (loadTasks)");
  const m = /async function loadTasks\(\) \{[\s\S]*?\n\}/.exec(HOME);
  tekshir('V0 loadTasks topildi', !!m);
  if (!m) return;
  async function sina(javob) {
    const el = element('');
    const ctx = ctxYasa({
      document: { getElementById: (id) => (id === 'tasksList' ? el : null) },
      fetch: async () => { if (javob === 'xato') throw new Error('tarmoq'); return { json: async () => javob }; },
    });
    vm.runInContext(ESC + '\n' + m[0], ctx);
    await vm.runInContext('loadTasks()', ctx);
    return el.innerHTML;
  }
  let h = await sina([{ icon: '⏰', text: '3 ta buyurtma muddati o\'tgan <b>' }]);
  tekshir("V1 vazifa matni ko'rinadi (escape qilingan)", h.includes("3 ta buyurtma muddati o&#39;tgan &lt;b&gt;") || h.includes("3 ta buyurtma muddati o'tgan &lt;b&gt;"), qisqa(h));
  h = await sina([]);
  tekshir("V2 vazifa yo'q — «Bugun uchun alohida vazifa yo'q»", h.includes("Bugun uchun alohida vazifa yo'q"), qisqa(h));
  h = await sina('xato');
  tekshir("V3 tarmoq xatosi — «Yuklab bo'lmadi» (abadiy «Yuklanmoqda…» emas)", h.includes("Yuklab bo'lmadi"), qisqa(h));
}

async function qaytarishBolimi() {
  bolim("returns.html — «/returns?brak=1» (Bosh sahifa «Brak yozish» amali)");
  const m = /\(function \(\) \{\n  try \{\n    const p = new URLSearchParams\(window\.location\.search\);\n    if \(p\.get\('brak'\) !== '1'\) return;[\s\S]*?\}\)\(\);/.exec(RETURNS);
  tekshir('K0 «?brak=1» bloki topildi', !!m);
  if (!m) return;
  for (const [qidiruv, holat, kut] of [['?brak=1', 'complete', 1], ['?brak=1', 'loading', 1], ['', 'complete', 0], ['?brak=0', 'complete', 0]]) {
    const ch = { ochildi: 0, hist: [] };
    const tinglovchi = [];
    const ctx = ctxYasa({
      window: { location: { search: qidiruv, pathname: '/returns' } }, history: { replaceState: (a, b, u) => ch.hist.push(u) },
      document: { readyState: holat, getElementById: (id) => (id === 'brakModal' ? {} : null),
                  addEventListener: (n, f) => tinglovchi.push(f) },
      showBrakModal: () => { ch.ochildi++; },
    });
    vm.runInContext(m[0], ctx);
    tinglovchi.forEach((f) => f());
    tekshir(`K1 «${qidiruv || '(yo\'q)'}», hujjat ${holat} → oyna ${kut} marta ochiladi`, ch.ochildi === kut, qisqa(ch));
  }
}

(async function () {
  try {
    await buyurtmaBolimi();
    await loyihaBolimi();
    await dashboardBolimi();
    await boshBolimi();
    await qaytarishBolimi();
  } catch (e) {
    tekshir('kutilmagan istisno', false, String((e && e.stack) || e).slice(0, 400));
  }
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})();
