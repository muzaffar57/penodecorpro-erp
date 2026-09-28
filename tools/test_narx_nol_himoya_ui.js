#!/usr/bin/env node
/**
 * test_narx_nol_himoya_ui.js — kech108, 71-band qoldig'i: buyurtma tahririda detal narxi JIM 0 ga tushmasin
 * (templates/orders.html — `editSelected` / `collectItems` / `_narxiNolgaTushgan` / `updateOrder`).
 *
 * NIMA UCHUN KERAK (O'LCHANGAN kech107 `work/probe107u71.py`, HAQIQIY brauzer): `base_price` siz (API / eski) yaratilgan
 * buyurtma tahrir oynasida HECH NARSA o'zgartirmasdan saqlansa — PUT `unit_price` 0, jami 200 000 → 0, ogohlantirishsiz.
 * kech108: saqlangan narxi > 0 detal 0 ga tushsa — umumiy tasdiqdan OLDIN ogohlantirish (nom, eski → 0); «Bekor» — PUT YO'Q
 * (`work/probe108n.py` — haqiqiy brauzerda: asl 200 000 → 0, dev — ogohlantirish, «Bekor», baza AYNAN).
 *
 *   N — `_narxiNolgaTushgan`: saqlangan > 0 va yangi 0 / NaN / manfiy emas-musbat — faqat shular; `_qator` siz — yo'q.
 *   C — `collectItems` o'ramasi: har detalga `_qator` (SANALMAYDIGAN — JSON.stringify ga tushmaydi, Object.keys da yo'q).
 *   U — `updateOrder` (HAQIQIY funksiya, soxta muhit): 0-narxli detal — ogohlantirish matni, «Bekor» → fetch YO'Q;
 *       «Ha» → PUT (tanada `_qator` yo'q); narxlar joyida — ogohlantirish yo'q, PUT bor.
 *   S — statik: editSelected (nusxa emas) `row.dataset.saqlanganNarx` yozadi; ogohlantirish umumiy tasdiqdan OLDIN.
 *
 * Funksiyalar HTML dan JONLI o'qiladi; topilmasa / istisno — yiqilgan tekshiruv (asl faylga qarshi QULAMAYDI).
 * ISHLATISH: node tools/test_narx_nol_himoya_ui.js
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

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
function jinjasiz(kod) {
  return kod === null ? null : kod.replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, 'null');
}
const NOL = olib(SRC, '_narxiNolgaTushgan');
const COLLECT = olib(SRC, 'collectItems');
const UPDATE = olib(SRC, 'updateOrder');
const EDIT = olib(SRC, 'editSelected') || '';
const FORMATNUM = olib(SRC, 'formatNum');

function kontekst(qosh) {
  const ctx = Object.assign({ console, JSON, String, Number, Math, Array, Object, isNaN, parseFloat, parseInt, Error }, qosh || {});
  vm.createContext(ctx);
  return ctx;
}
function qator(narx) { return { dataset: narx === undefined ? {} : { saqlanganNarx: String(narx) } }; }
function detal(nom, narx, q) { const d = { name: nom, unit_price: narx }; if (q) Object.defineProperty(d, '_qator', { value: q, enumerable: false }); return d; }

bolim('N — _narxiNolgaTushgan');
tekshir('N0 _narxiNolgaTushgan mavjud', !!NOL);
if (NOL) {
  const ctx = kontekst();
  let v = null, xato = null;
  try {
    vm.runInContext(jinjasiz(NOL), ctx);
    ctx.__its = [detal('A', 0, qator(200000)), detal('B', 48000, qator(48000)), detal('C', NaN, qator(1000)),
                 detal('D', 0, qator(0)), detal('E', 0, qator(undefined)), detal('F', 0), detal('G', '0', qator('50000.5')),
                 detal('H', 1, qator(9))];
    v = JSON.parse(JSON.stringify(vm.runInContext('_narxiNolgaTushgan(__its)', ctx)));
  } catch (e) { xato = String(e.message || e); }
  const nomlar = (v || []).map((x) => x.nom).join(',');
  tekshir('N1 faqat saqlangan > 0 va yangi 0 / NaN: A, C, G (B narx joyida, D / E saqlangan 0 / yo\'q, F qatorsiz, H 1 > 0)',
          xato === null && nomlar === 'A,C,G', xato || v);
  tekshir('N2 eski narx qatordan: A 200000, G 50000.5; yangi 0', xato === null && Array.isArray(v) && v.length === 3
          && v[0].eski === 200000 && v[2].eski === 50000.5 && v.every((x) => x.yangi === 0), v);
  let bosh = null;
  try { bosh = vm.runInContext('_narxiNolgaTushgan(null).length + _narxiNolgaTushgan([]).length', ctx); } catch (e) { bosh = String(e); }
  tekshir('N3 null / [] — bo\'sh ro\'yxat (istisno yo\'q)', bosh === 0, bosh);
}

bolim('C — collectItems: _qator sanalmaydigan');
function soxtaQator(nom, tur, narx, saqlangan) {
  const qiymat = { '.i-name': nom, '.i-type': tur, '.i-h': '20', '.i-w': '10', '.i-t': '10', '.i-l': '4', '.i-q': '1', '.i-c': 'false',
                   '.i-peno': '1', '.i-m3price': '', '.i-unitprice': String(narx), '.i-donayield': '', '.i-blokprice': '' };
  return {
    dataset: Object.assign({ birlik: String(narx) }, saqlangan === undefined ? {} : { saqlanganNarx: String(saqlangan) }),
    querySelector: (s) => (s in qiymat ? { value: qiymat[s] } : null),
    querySelectorAll: () => [],
  };
}
if (COLLECT) {
  const rows = [soxtaQator('P1', 'panel', 0, 200000), soxtaQator('P2', 'panel', 48000, 48000)];
  const ctx = kontekst({
    document: { querySelectorAll: (s) => (s === '.detal' ? rows : []), getElementById: () => ({ value: '' }) },
    sanitizeToLatin: (x) => x, parseNum: (x) => parseFloat(String(x || '').replace(/\s/g, '')) || 0,
  });
  let its = null, xato = null;
  try { vm.runInContext(jinjasiz(COLLECT), ctx); its = vm.runInContext('collectItems()', ctx); } catch (e) { xato = String(e.message || e); }
  tekshir('C1 collectItems ishlaydi (2 detal)', xato === null && its && its.length === 2, xato || its);
  tekshir('C2 har detalda `_qator` — o\'z qatori (P1 → 1-qator, P2 → 2-qator)', its && its[0]._qator === rows[0] && its[1]._qator === rows[1]);
  const j = its ? JSON.stringify(its) : '';
  tekshir('C3 `_qator` SANALMAYDI: JSON da yo\'q, Object.keys da yo\'q', its && !/_qator/.test(j) && !Object.keys(its[0]).includes('_qator'), j);
  if (NOL && its) {
    const c2 = kontekst();
    vm.runInContext(jinjasiz(NOL), c2);
    c2.__its = its;
    let v = null;
    try { v = JSON.parse(JSON.stringify(vm.runInContext('_narxiNolgaTushgan(__its)', c2))); } catch (e) { v = String(e); }
    tekshir('C4 collectItems → _narxiNolgaTushgan: faqat P1 (200 000 → 0)', Array.isArray(v) && v.length === 1 && v[0].nom === 'P1'
            && v[0].eski === 200000, v);
  }
}

bolim('U — updateOrder (HAQIQIY funksiya, soxta muhit)');
async function yangila(itemsFn, javob) {
  const tasdiq = [], fetchlar = [], xabar = [];
  const el = (v) => ({ value: v, scrollIntoView() {} });
  const ctx = kontekst({
    document: {
      getElementById: (id) => ({ project_id: el('7'), recipe_id: el(''), master_id: el(''), final_price: el('200000'),
        deadline_input: el(''), base_price: el(''), loy_kg: el('0') }[id] || null),
      querySelectorAll: () => [],
    },
    collectItems: itemsFn, retseptMajburiyXatosi54: () => null, showValidationModal: () => {},
    showConfirmModal: async (m) => { tasdiq.push(String(m)); return javob(String(m)); },
    showMsg: (m) => xabar.push(String(m)), parseNum: (x) => parseFloat(String(x || '').replace(/\s/g, '')) || 0,
    fetch: async (u, o) => { fetchlar.push([u, o && o.method, o && o.body]); return { ok: true, json: async () => ({}) }; },
    location: { reload() {} }, setTimeout: () => 0, clearDraftLS: () => {}, loadOrders: async () => {}, hideNewForm: () => {},
    localStorage: { removeItem() {} }, window: {},
    // kech110 (K110-1): sahifaning yuqori darajadagi holati (`let editUserTouched = false;`) — `updateOrder` summani faqat
    // qo'lda yozilganda yuboradi; bu test summa yuborilishiga emas, 0-narx ogohlantirishiga qaraydi
    editUserTouched: false,
  });
  const qism = [NOL, UPDATE, FORMATNUM].filter(Boolean).map(jinjasiz);
  if (!UPDATE) return { xato: 'updateOrder topilmadi', tasdiq, fetchlar };
  try {
    vm.runInContext(qism.join('\n'), ctx);
    ctx.__its = itemsFn;
    await vm.runInContext('updateOrder(15)', ctx);
    return { xato: null, tasdiq, fetchlar, xabar };
  } catch (e) { return { xato: String(e.message || e), tasdiq, fetchlar, xabar }; }
}
(async () => {
  const nolli = () => [detal('D3', 0, qator(200000)), detal('D4', 5000, qator(5000))];
  let r = await yangila(nolli, (m) => !/0 ga tushadi/.test(m));
  tekshir('U1 0-narxli detal: ogohlantirish (nom D3, "200 000 → 0 so\'m") umumiy tasdiqdan OLDIN',
          r.xato === null && r.tasdiq.length >= 1 && /0 ga tushadi/.test(r.tasdiq[0]) && /D3/.test(r.tasdiq[0])
          && /200[\s  ]?000 → 0 so'm/.test(r.tasdiq[0]) && !/D4/.test(r.tasdiq[0]), r);
  tekshir('U2 «Bekor» → PUT YO\'Q (fetch chaqirilmadi), umumiy tasdiq so\'ralmadi', r.xato === null && r.fetchlar.length === 0
          && r.tasdiq.length === 1, r);
  r = await yangila(nolli, () => true);
  const put = r.fetchlar.find((f) => f[1] === 'PUT');
  tekshir('U3 «Ha, 0 bilan saqlash» → umumiy tasdiq va PUT; tanada `_qator` YO\'Q', r.xato === null && r.tasdiq.length === 2 && !!put
          && !/_qator/.test(put[2] || ''), r);
  r = await yangila(() => [detal('D4', 5000, qator(5000)), detal('D5', 0, qator(0))], () => true);
  tekshir('U4 narxlar joyida (saqlangan 0 ham) — ogohlantirish YO\'Q, bitta umumiy tasdiq, PUT bor',
          r.xato === null && r.tasdiq.length === 1 && !/0 ga tushadi/.test(r.tasdiq[0]) && r.fetchlar.some((f) => f[1] === 'PUT'), r);

  bolim('S — statik');
  const kodsiz = EDIT.split('\n').filter((q) => !q.trim().startsWith('//')).join('\n');
  tekshir('S1 editSelected: nusxa bo\'lmasa `row.dataset.saqlanganNarx` yoziladi (item.unit_price)',
          /if \(!isDup\) row\.dataset\.saqlanganNarx = String\(parseFloat\(item\.unit_price/.test(kodsiz));
  const u = UPDATE || '';
  tekshir('S2 updateOrder: ogohlantirish (_narxiNolgaTushgan) umumiy "O\'zgarishlar saqlansinmi?" tasdig\'idan OLDIN',
          u.indexOf('_narxiNolgaTushgan(items)') > 0 && u.indexOf('_narxiNolgaTushgan(items)') < u.indexOf("O'zgarishlar saqlansinmi?"));

  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAIL) console.log('Yiqilganlar:\n  - ' + FAILED.join('\n  - '));
  process.exit(FAIL ? 1 : 0);
})();
