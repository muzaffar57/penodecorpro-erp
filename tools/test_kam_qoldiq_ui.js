#!/usr/bin/env node
/**
 * test_kam_qoldiq_ui.js — kech108, K108-2 (19-band, EGASI QARORI "Ha, ko'rinsin"): «kam qolgan xomashyo» brauzer qismi.
 *
 *   templates/home.html      `kamQoldiqHtml(items)` — bosh sahifa bloki. Minimal qoldig'i belgilanmagan (0) TUGAGAN
 *                            material endi keladi; asl kod chiziqni `qoldiq / min` bilan hisoblardi (0 ga bo'lish →
 *                            "NaN%" / "-Infinity%"), sonni xom ko'rsatardi (−0.06190476190476213).
 *   templates/dashboard.html `buildWarnList` — yorliq "Tugagan" (qoldiq ≤ 0) / "Kam qoldi", son — 2 kasrgacha.
 *   templates/reports.html   `stockDot` — 0 / 0 (tugagan, min belgilanmagan) sariq (asl: yashil "yetarli");
 *                            Tayyor loy — hech qachon sariq emas (kech37 21-band qarori), manfiy — qizil.
 *
 * Funksiyalar HTML dan JONLI o'qiladi (Jinja teglari olib tashlanadi); topilmasa / istisno — yiqilgan tekshiruv
 * (asl faylga qarshi QULAMAYDI). ISHLATISH: node tools/test_kam_qoldiq_ui.js
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
function oqi(nom) { try { return fs.readFileSync(path.join(ROOT, 'templates', nom), 'utf8'); } catch (e) { return ''; } }
const HOME = oqi('home.html');
const DASH = oqi('dashboard.html');
const REP = oqi('reports.html');
const BASE = oqi('base.html');

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
function jinjasiz(kod) {
  return kod === null ? null : kod.replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, 'null');
}
function ishga(qismlar, ifoda, qosh) {
  if (!qismlar.every(Boolean)) return { xato: 'funksiyalar topilmadi', v: null };
  const ctx = Object.assign({ console, JSON, String, Number, Math, Array, Object, isNaN, parseFloat }, qosh || {});
  vm.createContext(ctx);
  try {
    vm.runInContext(jinjasiz(qismlar.join('\n')), ctx);
    return { xato: null, v: vm.runInContext(ifoda, ctx) };
  } catch (e) { return { xato: String(e && e.message || e), v: null }; }
}
// kech118 (B — U-03 / U-05, MOSLANDI): sahifa funksiyalari base.html `sonKor` / `matnRangi` … ni ham chaqiradi — birga yuklanadi
const ESC = ['escapeHtml', 'sonKor', 'foizKor', 'birlikKor', 'matnRangi'].map(n => olib(BASE, n)).filter(Boolean).join('\n');
const A = { item_name: 'Penoplast 10P', stock_quantity: -0.06190476190476213, min_stock: 0, unit: 'dona' };
const B0 = { item_name: 'Mel', stock_quantity: 0, min_stock: 0, unit: 'kg' };
const D = { item_name: 'Akril', stock_quantity: 5, min_stock: 10, unit: 'kg' };
const X = { item_name: '<img src=x onerror=alert(1)>', stock_quantity: 1, min_stock: 4, unit: 'kg' };

bolim('H — home.html kamQoldiqHtml');
const KQ = olib(HOME, 'kamQoldiqHtml');
let r = ishga([ESC, KQ], `kamQoldiqHtml(${JSON.stringify([A, D])})`);
const h = r.v || '';
tekshir('H1 kamQoldiqHtml mavjud va ishlaydi', !!KQ && r.xato === null && h.length > 0, r.xato);
const qatorlar = h.split('class="stock-row"').slice(1);
tekshir('H2 tugagan, min 0 (Penoplast 10P −0.0619 / 0): chiziq 0 %, NaN / Infinity YO\'Q, qizil, "— tugagan"',
        qatorlar[0] && /width:0%/.test(qatorlar[0]) && !/NaN|Infinity/.test(h) && /#EF4444/.test(qatorlar[0])
        && /— tugagan/.test(qatorlar[0]), qatorlar[0]);
tekshir('H3 son 2 kasrgacha: "-0.06 dona" (asl: -0.06190476190476213)', qatorlar[0] && />-0\.06 dona/.test(qatorlar[0])
        && !/0619047/.test(h), qatorlar[0]);
tekshir('H4 oddiy kam (5 / 10): chiziq 50 %, sariq, "tugagan" YO\'Q', qatorlar[1] && /width:50%/.test(qatorlar[1])
        && /#F59E0B/.test(qatorlar[1]) && !/tugagan/.test(qatorlar[1]), qatorlar[1]);
r = ishga([ESC, KQ], `kamQoldiqHtml(${JSON.stringify([B0])})`);
tekshir('H5 0 / 0: chiziq 0 %, "— tugagan", NaN YO\'Q', r.xato === null && /width:0%/.test(r.v || '') && /— tugagan/.test(r.v || '')
        && !/NaN/.test(r.v || ''), r.v || r.xato);
r = ishga([ESC, KQ], 'kamQoldiqHtml([]) + "|" + kamQoldiqHtml(null)');
tekshir('H6 bo\'sh ro\'yxat / null — "Barcha xomashyo yetarli"', r.xato === null && (r.v || '').split('|').every((x) => /Barcha xomashyo yetarli/.test(x)), r.v || r.xato);
r = ishga([ESC, KQ], `kamQoldiqHtml(${JSON.stringify([X])})`);
tekshir('H7 nom ekranlanadi (<img> teg YO\'Q)', r.xato === null && !/<img/.test(r.v || '') && /&lt;img/.test(r.v || ''), r.v || r.xato);
tekshir('H8 home.html render qismi kamQoldiqHtml(s.low_stock_items) ni ishlatadi; `/ item.min_stock)` bo\'lish QOLMAGAN',
        /kamQoldiqHtml\(s\.low_stock_items\)/.test(HOME) && !/item\.stock_quantity \/ item\.min_stock/.test(HOME));

bolim('D — dashboard.html: kam qoldiq bloki YO\'Q (zip 124)');
// kech118 (zip 124 — egasi QARORI G1-09 «Vazifalar ajratilsin», MOSLANDI): Dashboard «Ombor ogohlantirishlari» (`buildWarnList`)
// olib tashlandi — kam qolgan xomashyo BITTA joyda: Bosh sahifa «Kam qolgan xomashyo» (`kamQoldiqHtml`, yuqoridagi H bo'limi).
tekshir("D1 Dashboard da `buildWarnList` / #warnList YO'Q (takror edi — kam qoldiq Bosh sahifada)",
        !olib(DASH, 'buildWarnList') && !DASH.includes('id="warnList"') && /kamQoldiqHtml\(s\.low_stock_items\)/.test(HOME));

bolim('R — reports.html stockDot');
const SD = olib(REP, 'stockDot');
function nuqta(i) {
  const res = ishga([SD], `stockDot(${JSON.stringify(i)})`);
  const m = /background:(#[0-9A-Fa-f]{6})/.exec(res.v || '');
  return m ? m[1].toUpperCase() : (res.xato || '?');
}
tekshir('R1 0 / 0 (tugagan, min belgilanmagan) — sariq #F59E0B (asl: yashil)', nuqta({ item_name: 'Mel', stock_quantity: 0, min_stock: 0 }) === '#F59E0B',
        nuqta({ item_name: 'Mel', stock_quantity: 0, min_stock: 0 }));
tekshir('R2 manfiy (−0.06 / 0) — qizil #EF4444', nuqta(A) === '#EF4444', nuqta(A));
tekshir('R3 5 / 0 — yashil; 5 / 10 — sariq; 15 / 10 — yashil',
        nuqta({ item_name: 'a', stock_quantity: 5, min_stock: 0 }) === '#22C55E' && nuqta(D) === '#F59E0B'
        && nuqta({ item_name: 'a', stock_quantity: 15, min_stock: 10 }) === '#22C55E');
tekshir('R4 Tayyor loy (0 / 0 va 3 / 10) — yashil (kech37 21-band: ortgan loy uchun chegara yo\'q)',
        nuqta({ item_name: 'Tayyor loy (Oq marmar)', stock_quantity: 0, min_stock: 0 }) === '#22C55E'
        && nuqta({ item_name: 'Tayyor loy (Oq marmar)', stock_quantity: 3, min_stock: 10 }) === '#22C55E');

console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
if (FAIL) console.log('Yiqilganlar:\n  - ' + FAILED.join('\n  - '));
process.exit(FAIL ? 1 : 0);
