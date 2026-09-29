#!/usr/bin/env node
/**
 * test_yuqori_panel_ui.js — kech111 (K112-1): yuqori paneldagi ochiluvchi panellar — obuna ogohlantirishi (`#obunaPanel`)
 * va bildirishnomalar (`#notifPanel`) — ochilganda EKRAN ICHIDA joylanadi (templates/base.html, HAQIQIY markup va HAQIQIY
 * skript jsdom da; tugma o'rni va oyna kengligi soxta — jsdom maket hisoblamaydi).
 *
 * NIMA UCHUN KERAK: jonli sinovda (sinov, 29.09.2026, Claude ilovasidagi brauzer 756 px) obuna ogohlantirishi bosilganda
 * panel ekrandan chapga chiqib ketdi — matnning boshi ko'rinmadi. HAQIQIY brauzerda o'lchandi (`work/k112/probe112panel.py`):
 * panel tugmaning o'ng chetiga bog'langan (`right: 0`), tor ekranda tugmalar qatori chapga o'tadi — 390 px da panelning chap
 * cheti −232 px (obuna) / −178 px (bildirishnomalar — ESKI xato, telefonda hamma foydalanuvchida). Qoida: panel kengligi
 * ≤ ekran − 24 px, chap cheti ≥ 12 px, o'ng cheti ekrandan chiqmaydi; joy bo'lsa — avvalgidek tugmaning o'ng chetiga
 * tekislanadi (keng ekranda ko'rinish o'zgarmaydi); oyna o'lchami o'zgarsa — qayta joylanadi; obuna paneli tashqariga
 * bosilganda yopiladi (bildirishnomalar kabi).
 *
 * BO'LIMLAR: P — joylash (tor / juda tor / keng / o'ng chekka / o'lcham o'zgarishi); Y — ochish / yopish (qayta bosish,
 * tashqariga bosish, ichkariga bosish, aria-expanded); N — bildirishnomalar paneli; B — ogohlantirishsiz sahifa (xato yo'q);
 * S — statik. Asl kodda (`bfcfd83`) joylash yo'q — P / N yiqiladi (QULAMAYDI). ISHLATISH: node tools/test_yuqori_panel_ui.js
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
let BASE = '';
try { BASE = fs.readFileSync(path.join(ROOT, 'templates', 'base.html'), 'utf8'); } catch (e) { BASE = ''; }

let OK = 0, FAIL = 0;
const FAILED = [];
function qisqa(x) {
  let s;
  try { s = typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { s = String(x); }
  s = String(s);
  return s.length > 400 ? s.slice(0, 400) + '…' : s;
}
function tekshir(label, shart, izoh) {
  let s = false;
  try { s = !!(typeof shart === 'function' ? shart() : shart); } catch (e) { s = false; }
  if (s) { OK++; console.log(`  ✓ ${label}`); }
  else {
    FAIL++; FAILED.push(label);
    let iz = izoh;
    try { if (typeof izoh === 'function') iz = izoh(); } catch (e) { iz = String(e); }
    console.log(`  ✗ ${label}${iz !== undefined ? '   — ' + qisqa(iz) : ''}`);
  }
}
function bolim(t) { console.log(`\n--- ${t} ---`); }
function jinjasiz(kod) {
  return String(kod || '').replace(/\{#[\s\S]*?#\}/g, '').replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');
}

// Yuqori panel markup'i (header) va undan keyingi skript (IIFE: mavzu, bildirishnomalar, obuna paneli)
const H0 = BASE.indexOf('<header class="erp-topbar">');
const H1 = BASE.indexOf('</header>', H0);
const HEADER = H0 >= 0 && H1 > H0 ? jinjasiz(BASE.slice(H0, H1 + '</header>'.length)) : '';
const S0 = H1 > 0 ? BASE.indexOf('<script>', H1) : -1;
const S1 = S0 > 0 ? BASE.indexOf('</script>', S0) : -1;
const SKRIPT = S0 > 0 && S1 > S0 ? jinjasiz(BASE.slice(S0 + '<script>'.length, S1)) : '';

let JSDOM = null, VirtualConsole = null;
try { ({ JSDOM, VirtualConsole } = require('jsdom')); } catch (e) { JSDOM = null; }

/** jsdom muhiti: oyna kengligi `kenglik`; tugmalar o'rni — `joy` ({obunaBanner: {right, bottom}, notifBell: {...}}). */
function muhit(kenglik, joy, opt) {
  opt = opt || {};
  const xatolar = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => { xatolar.push(String(e && e.message || e)); });
  let header = HEADER;
  if (opt.ogohlantirishsiz) {
    const a = header.indexOf('<div id="obunaWrap"');
    const b = header.indexOf('<div id="notifWrap"');
    if (a >= 0 && b > a) header = header.slice(0, a) + header.slice(b);
  }
  const html = `<!doctype html><html><head></head><body><div id="tashqi" style="height:400px">kontent</div>${header}
<script>
window.fetch = function () { return Promise.resolve({ ok: true, json: function () { return Promise.resolve([]); } }); };
</script></body></html>`;
  const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc });
  const w = dom.window;
  Object.defineProperty(w, 'innerWidth', { configurable: true, writable: true, value: kenglik });
  const JOY = Object.assign({ obunaBanner: { right: 300, bottom: 94 }, notifBell: { right: 350, bottom: 94 } }, joy || {});
  w.__joy = JOY;
  ['obunaBanner', 'notifBell'].forEach(function (id) {
    const el = w.document.getElementById(id);
    if (!el) return;
    el.getBoundingClientRect = function () {
      const j = w.__joy[id];
      return { left: j.right - 36, right: j.right, top: j.bottom - 36, bottom: j.bottom, width: 36, height: 36, x: j.right - 36, y: j.bottom - 36 };
    };
  });
  try {
    const s = w.document.createElement('script');
    s.textContent = SKRIPT;
    w.document.body.appendChild(s);
  } catch (e) { xatolar.push(String(e)); }
  return { w, xatolar };
}
function px(v) { return v === '' || v === undefined || v === null ? NaN : parseFloat(v); }
function joyi(p) { return { position: p.style.position, left: px(p.style.left), width: px(p.style.width), top: px(p.style.top), display: p.style.display }; }
function bosish(w, el) { el.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true })); }

function main() {
  if (!JSDOM) { console.log('jsdom yo\'q — test o\'tkazilmadi'); tekshir('jsdom mavjud', false); return; }

  bolim('S — statik');
  tekshir('S1 base.html: yuqori panel (header) va undan keyingi skript topildi', HEADER.length > 0 && SKRIPT.length > 0);
  tekshir('S2 obuna tugmasi nomli funksiyani chaqiradi (inline joylashsiz ochish yo\'q)',
    /id="obunaBanner"[\s\S]{0,200}onclick="obunaPaneliniAlmashtir\(\)"/.test(BASE), BASE.slice(BASE.indexOf('id="obunaBanner"'), BASE.indexOf('id="obunaBanner"') + 200));
  tekshir('S3 joylash funksiyasi bitta — ikkala panel uni chaqiradi',
    (SKRIPT.match(/function panelniJoyla\(/g) || []).length === 1
    && /toggleNotifPanel[\s\S]{0,200}panelniJoyla\(document\.getElementById\('notifBell'\)/.test(SKRIPT)
    && /obunaPaneliniAlmashtir[\s\S]{0,300}panelniJoyla\(t, p\)/.test(SKRIPT));

  bolim('P — joylash');
  // Tor ekran (390 px): tugmalar qatori chapda — obuna tugmasining o'ng cheti 108 px (HAQIQIY brauzerda o'lchangan)
  let m = muhit(390, { obunaBanner: { right: 108, bottom: 94 }, notifBell: { right: 162, bottom: 94 } });
  let w = m.w, p = w.document.getElementById('obunaPanel');
  tekshir('P0 skript xatosiz yuklandi, funksiyalar bor', m.xatolar.length === 0 && typeof w.panelniJoyla === 'function'
    && typeof w.obunaPaneliniAlmashtir === 'function' && typeof w.toggleNotifPanel === 'function', m.xatolar);
  try { w.obunaPaneliniAlmashtir(); } catch (e) { m.xatolar.push(String(e)); }
  let j = joyi(p);
  tekshir('P1 390 px: panel ochildi, chap cheti 12 px (tugmaga tekislansa −232 px bo\'lardi), kengligi 340 px, o\'ng cheti ≤ 378',
    j.display === 'block' && j.position === 'fixed' && j.left === 12 && j.width === 340 && j.left + j.width <= 390 - 12, j);
  tekshir('P2 390 px: panel tugmaning 8 px pastida (top = 102)', j.top === 102, j);
  tekshir('P2b `right` bekor qilingan (chap chekka ishlaydi), max-width cheklovi olib tashlangan',
    p.style.right === 'auto' && p.style.maxWidth === 'none', [p.style.right, p.style.maxWidth]);

  m = muhit(320, { obunaBanner: { right: 90, bottom: 94 } });
  w = m.w; p = w.document.getElementById('obunaPanel');
  try { w.obunaPaneliniAlmashtir(); } catch (e) { m.xatolar.push(String(e)); }
  j = joyi(p);
  tekshir('P3 320 px: kenglik = ekran − 24 = 296 px, chap 12, o\'ng cheti 308 (ekrandan chiqmaydi)',
    j.width === 296 && j.left === 12 && j.left + j.width === 308, j);

  m = muhit(1400, { obunaBanner: { right: 1210, bottom: 47 } });
  w = m.w; p = w.document.getElementById('obunaPanel');
  try { w.obunaPaneliniAlmashtir(); } catch (e) { m.xatolar.push(String(e)); }
  j = joyi(p);
  tekshir('P4 1400 px: avvalgidek tugmaning o\'ng chetiga tekislangan (chap = 1210 − 340 = 870), top = 55',
    j.left === 870 && j.width === 340 && j.top === 55, j);

  m = muhit(1400, { obunaBanner: { right: 1395, bottom: 47 } });
  w = m.w; p = w.document.getElementById('obunaPanel');
  try { w.obunaPaneliniAlmashtir(); } catch (e) { m.xatolar.push(String(e)); }
  j = joyi(p);
  tekshir('P5 tugma o\'ng chekkada (1395): panel o\'ngdan ham chiqmaydi — chap = 1400 − 340 − 12 = 1048',
    j.left === 1048 && j.left + j.width === 1388, j);

  // O'lcham o'zgarishi: keng ekranda ochiq → tor ekranga o'tdi → qayta joylanadi
  m = muhit(1400, { obunaBanner: { right: 1210, bottom: 47 } });
  w = m.w; p = w.document.getElementById('obunaPanel');
  try { w.obunaPaneliniAlmashtir(); } catch (e) { m.xatolar.push(String(e)); }
  w.innerWidth = 390; w.__joy.obunaBanner = { right: 108, bottom: 94 };
  w.dispatchEvent(new w.Event('resize'));
  j = joyi(p);
  tekshir('P6 oyna 1400 → 390 px (panel ochiq): qayta joylandi — chap 12, top 102', j.left === 12 && j.top === 102 && j.width === 340, j);
  try { w.obunaPaneliniAlmashtir(); } catch (e) { m.xatolar.push(String(e)); }
  const oldin = joyi(p);
  w.innerWidth = 1400; w.__joy.obunaBanner = { right: 1210, bottom: 47 };
  w.dispatchEvent(new w.Event('resize'));
  tekshir('P7 yopiq panel o\'lcham o\'zgarganda joylanmaydi (ochilganda joylanadi)',
    JSON.stringify(joyi(p)) === JSON.stringify(oldin) && p.style.display === 'none', [oldin, joyi(p)]);

  bolim('Y — ochish / yopish');
  m = muhit(390, { obunaBanner: { right: 108, bottom: 94 } });
  w = m.w; p = w.document.getElementById('obunaPanel');
  const t = w.document.getElementById('obunaBanner');
  bosish(w, t);
  tekshir('Y1 tugma bosildi — ochildi, aria-expanded = true', p.style.display === 'block' && t.getAttribute('aria-expanded') === 'true',
    [p.style.display, t.getAttribute('aria-expanded')]);
  bosish(w, p);
  tekshir('Y2 panelning o\'ziga bosish — ochiq qoladi (matnni o\'qish / nusxalash)', p.style.display === 'block', p.style.display);
  bosish(w, w.document.getElementById('tashqi'));
  tekshir('Y3 tashqariga bosish — yopildi, aria-expanded = false', p.style.display === 'none' && t.getAttribute('aria-expanded') === 'false',
    [p.style.display, t.getAttribute('aria-expanded')]);
  bosish(w, t); bosish(w, t);
  tekshir('Y4 tugmani ikki marta bosish — ochildi va yopildi', p.style.display === 'none' && t.getAttribute('aria-expanded') === 'false',
    [p.style.display, t.getAttribute('aria-expanded')]);
  if (p.style.display !== 'block') bosish(w, t);
  const ochiqEdi = p.style.display === 'block';
  bosish(w, w.document.getElementById('notifBell'));
  tekshir('Y5 obuna paneli ochiq turib qo\'ng\'iroq bosildi — obuna paneli yopildi, bildirishnomalar ochildi',
    ochiqEdi && p.style.display === 'none' && w.document.getElementById('notifPanel').style.display === 'block',
    [ochiqEdi, p.style.display, w.document.getElementById('notifPanel').style.display]);

  bolim('N — bildirishnomalar paneli (eski xato — telefonda hamma foydalanuvchida)');
  m = muhit(390, { notifBell: { right: 162, bottom: 94 } });
  w = m.w;
  const np = w.document.getElementById('notifPanel');
  bosish(w, w.document.getElementById('notifBell'));
  j = joyi(np);
  tekshir('N1 390 px: bildirishnomalar paneli ekran ichida (chap 12, kengligi 340; tugmaga tekislansa −178 px bo\'lardi)',
    j.display === 'block' && j.left === 12 && j.width === 340 && j.position === 'fixed', j);
  bosish(w, w.document.getElementById('tashqi'));
  tekshir('N2 tashqariga bosish — yopildi (avvalgi xulq saqlangan)', np.style.display === 'none', np.style.display);
  m = muhit(1400, { notifBell: { right: 1264, bottom: 47 } });
  w = m.w;
  bosish(w, w.document.getElementById('notifBell'));
  j = joyi(w.document.getElementById('notifPanel'));
  tekshir('N3 1400 px: avvalgidek qo\'ng\'iroqning o\'ng chetiga tekislangan (chap = 924)', j.left === 924 && j.top === 55, j);

  bolim('B — ogohlantirishsiz sahifa (ko\'p foydalanuvchi — obuna belgisi yo\'q)');
  m = muhit(390, { notifBell: { right: 108, bottom: 94 } }, { ogohlantirishsiz: true });
  w = m.w;
  let xato = null;
  try { w.obunaPaneliniAlmashtir(); bosish(w, w.document.getElementById('tashqi')); w.dispatchEvent(new w.Event('resize')); }
  catch (e) { xato = String(e); }
  tekshir('B1 obuna belgisi yo\'q — funksiya, tashqi bosish va o\'lcham o\'zgarishi xatosiz', xato === null && m.xatolar.length === 0
    && !w.document.getElementById('obunaPanel'), [xato, m.xatolar]);
  bosish(w, w.document.getElementById('notifBell'));
  j = joyi(w.document.getElementById('notifPanel'));
  tekshir('B2 bildirishnomalar — ekran ichida (chap 12)', j.display === 'block' && j.left === 12, j);
}

try { main(); } catch (e) { FAIL++; FAILED.push('QULADI: ' + e); console.log('  ✗ QULADI: ' + (e && e.stack || e)); }
console.log(`\nNATIJA: o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
if (FAILED.length) { console.log('Yiqilganlar:'); FAILED.forEach((f) => console.log('  - ' + f)); }
process.exit(FAIL ? 1 : 0);
