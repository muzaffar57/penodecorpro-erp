#!/usr/bin/env node
/**
 * test_qoralama_tugma_ui.js — kech109, K109-1: buyurtma TAHRIRIDA «📝 Vaqtincha saqlash» tugmasi yashirilishi
 * (templates/orders.html).
 *
 * NIMA UCHUN KERAK (JONLI O'LCHANGAN — sinov sayti, zip 103 kodi; `main` da ham shu kod, 2026-06 dan beri):
 *   `editSelected` va `showNewForm` tugmani `document.querySelector('#newOrderForm .btn-outline')` bilan qidirardi.
 *   Formadagi BIRINCHI `.btn-outline` — sarlavhadagi «✕ Yopish»; matni 'Vaqtincha' ni o'z ichiga olmagani uchun
 *   hech narsa yashirilmasdi — ORD-038-1 tahririda «📝 Vaqtincha saqlash» ko'rinib turardi. Bosilsa `saveOrder(true)`
 *   himoyasi tahrirni `updateOrder` ga yo'naltiradi: «vaqtincha» emas, HAQIQIY saqlash — chalg'ituvchi.
 *
 * BO'LIMLAR
 *   F — HAQIQIY forma markupi (`<div id="newOrderForm"` … — shablondan, Jinja teglarisiz) + HAQIQIY `showNewForm` va
 *       `editSelected` ning tahrir-tugmalar qismi ("const saveBtn = …" dan `calcDiscount();` gacha — matndan kesiladi):
 *       yangi forma → tahrir → yana yangi forma; tugmalar ko'rinishi va matni.
 *   S — statik: draft tugmasi id bilan topiladi; `.btn-outline` birinchisi bo'yicha qidiruv qolmagan.
 *
 * Funksiyalar / qismlar HTML dan JONLI o'qiladi; topilmasa yoki istisno bo'lsa — yiqilgan tekshiruv (asl faylga qarshi
 * QULAMAYDI). ISHLATISH: node tools/test_qoralama_tugma_ui.js   (chiqish kodi 0 — hammasi o'tdi)
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
let SRC = '';
try { SRC = fs.readFileSync(path.join(ROOT, 'templates', 'orders.html'), 'utf8'); } catch (e) { SRC = ''; }

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
  try { s = !!shart; } catch (e) { s = false; }
  if (s) { OK++; console.log(`  ✓ ${label}`); }
  else { FAIL++; FAILED.push(label); console.log(`  ✗ ${label}${izoh !== undefined ? '   — ' + qisqa(izoh) : ''}`); }
}
function bolim(t) { console.log(`\n--- ${t} ---`); }
function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
  if (!m) return null;
  let i = m.index + m[0].length, d = 1;
  for (; i < src.length && d > 0; i++) { if (src[i] === '(') d++; else if (src[i] === ')') d--; }
  const j = src.indexOf('{', i);
  if (j < 0) return null;
  d = 0;
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(m.index, k + 1); }
  }
  return null;
}
function kes(src, bosh, oxir, dan) {
  const i = src.indexOf(bosh, dan || 0);
  if (i < 0) return null;
  const j = src.indexOf(oxir, i + bosh.length);
  return j < 0 ? null : src.slice(i, j);
}
function jinjasiz(kod) {
  return kod === null ? null : kod.replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');
}
// `<div id="…"` dan uning yopiluvchi </div> igacha (ichma-ich div sanab).
function divMarkup(src, id) {
  const i = src.indexOf(`<div id="${id}"`);
  if (i < 0) return null;
  const re = /<div\b|<\/div>/g;
  re.lastIndex = i;
  let d = 0, m;
  while ((m = re.exec(src))) {
    if (m[0] === '</div>') { d--; if (d === 0) return src.slice(i, m.index + 6); }
    else d++;
  }
  return null;
}

let JSDOM = null, VirtualConsole = null;
try { ({ JSDOM, VirtualConsole } = require('jsdom')); } catch (e) { JSDOM = null; }

const FORMA = jinjasiz(divMarkup(SRC, 'newOrderForm'));
const EDIT = olib(SRC, 'editSelected') || '';
const SHOWNEW = olib(SRC, 'showNewForm');
const TIKLA = olib(SRC, '_tahrirBanneriTikla');
// tahrir shoxining oxiri: `else { … }` yopilishi (`\n    }\n\n    calcDiscount();`) — qavs kirmaydi
const QISM_TUGMA = kes(EDIT, "const saveBtn = document.querySelector('#newOrderForm .btn-dark');", '\n    }\n\n    calcDiscount();');

function muhit() {
  const html = `<!doctype html><body>${FORMA || ''}
    <div id="orderDetail"></div><div id="emptyMid"></div><div id="sumCard"></div></body>`;
  const xatolar = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => { xatolar.push(String(e && e.message || e)); });
  const dom = new JSDOM(html, { runScripts: 'dangerously', virtualConsole: vc });
  const w = dom.window;
  const kod = [
    'var editMode = false, currentEditOrderId = null, editDiscountPct = 0, editUserTouched = false, editInitialLoadDone = false;',
    'var selectedOrderId = null; function filterProjectSelect(){} function addItem(){} function saveOrder(){} function updateOrder(){}',
    TIKLA || 'function _tahrirBanneriTikla(){}', SHOWNEW || '',
    'function __tahrirTugmalar(editId) {', QISM_TUGMA || 'throw new Error("QISM_TUGMA topilmadi");', '}',
  ].join('\n');
  const s = w.document.createElement('script');
  s.textContent = kod;
  w.document.body.appendChild(s);
  return { w, xatolar };
}
function tugmalar(w) {
  const f = w.document.getElementById('newOrderForm');
  const hammasi = f ? [...f.querySelectorAll('button')] : [];
  const top = (matn) => hammasi.find(b => (b.textContent || '').includes(matn)) || null;
  const kor = (b) => !!b && b.style.display !== 'none';
  const qoralama = top('Vaqtincha saqlash'), yopish = top('Yopish');
  const saqlash = hammasi.find(b => /Buyurtmani saqlash|O'zgarishlarni saqlash/.test(b.textContent || '')) || null;
  return {
    qoralama_bor: !!qoralama, qoralama_korinadi: kor(qoralama),
    yopish_bor: !!yopish, yopish_korinadi: kor(yopish),
    saqlash_matn: saqlash ? saqlash.textContent.trim() : null,
  };
}

bolim('F. HAQIQIY forma: yangi → tahrir → yangi');
tekshir('F0 manbalar: forma markupi, showNewForm, editSelected tahrir-tugmalar qismi, jsdom',
  !!FORMA && !!SHOWNEW && !!QISM_TUGMA && !!JSDOM,
  { forma: !!FORMA, shownew: !!SHOWNEW, qism: !!QISM_TUGMA, jsdom: !!JSDOM });
let M = null;
try { M = JSDOM && FORMA ? muhit() : null; } catch (e) { M = null; }
if (M) {
  const w = M.w;
  let x1 = null, x2 = null, x3 = null;
  try { w.showNewForm(); } catch (e) { x1 = String(e && e.message || e); }
  const h1 = tugmalar(w);
  tekshir('F1 yangi forma: «Vaqtincha saqlash» ko\'rinadi, «Yopish» ko\'rinadi, xato yo\'q',
    x1 === null && h1.qoralama_bor && h1.qoralama_korinadi && h1.yopish_korinadi, { x1, h1 });
  try { w.__tahrirTugmalar(177); } catch (e) { x2 = String(e && e.message || e); }
  const h2 = tugmalar(w);
  tekshir('F2 tahrir: «📝 Vaqtincha saqlash» YASHIRILGAN (asl: ko\'rinib qolardi — «Yopish» topilardi)',
    x2 === null && h2.qoralama_bor && !h2.qoralama_korinadi, { x2, h2 });
  tekshir('F3 tahrir: «✕ Yopish» ko\'rinadi (yashirilmaydi), asosiy tugma «💾 O\'zgarishlarni saqlash»',
    h2.yopish_korinadi && h2.saqlash_matn === "💾 O'zgarishlarni saqlash", h2);
  try { w.showNewForm(); } catch (e) { x3 = String(e && e.message || e); }
  const h3 = tugmalar(w);
  tekshir('F4 yana yangi forma: «Vaqtincha saqlash» QAYTA ko\'rinadi, «💾 Buyurtmani saqlash»',
    x3 === null && h3.qoralama_korinadi && h3.saqlash_matn === '💾 Buyurtmani saqlash', { x3, h3 });
  tekshir('F5 skript xatolari yo\'q', M.xatolar.length === 0, M.xatolar);
} else {
  tekshir('F1–F5 muhit tuzilmadi', false, 'jsdom yoki forma markupi yo\'q');
}

bolim('S. Statik');
const tugmaTeg = (/<button[^>]*onclick="saveOrder\(true\)"[^>]*>/.exec(SRC) || [''])[0];
tekshir('S1 «Vaqtincha saqlash» tugmasida id="draftSaveBtn"', /\bid="draftSaveBtn"/.test(tugmaTeg), tugmaTeg);
tekshir('S2 kodda `.btn-outline` BIRINCHISI bo\'yicha draft qidiruvi qolmagan',
  !SRC.includes("document.querySelector('#newOrderForm .btn-outline')"));
tekshir('S3 showNewForm va editSelected — getElementById(\'draftSaveBtn\')',
  !!SHOWNEW && SHOWNEW.includes("getElementById('draftSaveBtn')") && EDIT.includes("getElementById('draftSaveBtn')"));
const birinchiOut = FORMA ? ((/<button[^>]*class="[^"]*btn-outline[^"]*"[^>]*>([^<]*)</.exec(FORMA) || ['', ''])[1] || '') : '';
tekshir('S4 (sabab hujjati) formadagi birinchi `.btn-outline` — «✕ Yopish», draft tugmasi EMAS',
  birinchiOut.includes('Yopish') && !birinchiOut.includes('Vaqtincha'), birinchiOut);

console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
if (FAIL) console.log('Yiqilganlar:\n  - ' + FAILED.join('\n  - '));
process.exit(FAIL ? 1 : 0);
