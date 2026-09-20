#!/usr/bin/env node
/**
 * test_narx_frontend.js — BRAUZERDAGI narx formulalarining etaloni.
 *
 * NIMA UCHUN KERAK
 * ----------------
 * Sotuv narxini SERVER emas, BRAUZER hisoblaydi. Server esa o'sha
 * hisoblangan narxni oladi. Ya'ni narx formulasining yarmi `.html`
 * fayllarda yashaydi va `test_narx_etalon.py` ularga umuman tegmaydi.
 *
 * O'lchangan holat: profil hajm formulasi Python'da 4, JavaScript'da 4
 * joyda takrorlangan. `orders.html` dagi `calculateItem()` va
 * `finished.html` dagi `pCalc()` — bir-biridan MUSTAQIL nusxalar.
 * Biri o'zgarib ikkinchisi qolsa, buyurtmadagi narx bilan tayyor
 * mahsulotdagi narx jimgina ajralib ketadi.
 *
 * QANDAY ISHLAYDI
 * ---------------
 * Funksiyalar `templates/*.html` dan JONLI o'qiladi (nusxa ko'chirilmaydi —
 * aks holda test eskirib qolardi), soxta DOM ichida ishga tushiriladi va
 * natijasi MUSTAQIL yozilgan etalon formula bilan solishtiriladi.
 *
 * ISHLATISH
 * ---------
 *     node tools/test_narx_frontend.js
 *
 * Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const T = (f) => fs.readFileSync(path.join(ROOT, 'templates', f), 'utf8');

let OK = 0, FAIL = 0;
const FAILED = [];
const EPS = 1e-9;

function check(label, olingan, kutilgan) {
  const a = Number(olingan), b = Number(kutilgan);
  const mos = a === b || Math.abs(a - b) <= EPS * Math.max(1, Math.abs(a), Math.abs(b));
  if (mos) { OK++; console.log(`  \u2713 ${label}  = ${a}`); }
  else {
    FAIL++; FAILED.push(`${label}: olingan=${a} kutilgan=${b}`);
    console.log(`  \u2717 ${label}  olingan=${a}  KUTILGAN=${b}`);
  }
}
function bolim(t) { console.log(`\n${'='.repeat(66)}\n${t}\n${'='.repeat(66)}`); }

// ── Funksiyani HTML dan nomi bo'yicha ajratib olish (qavs hisobi bilan) ──
function olib(src, nom) {
  const i = src.indexOf('function ' + nom + '(');
  if (i < 0) throw new Error(`funksiya topilmadi: ${nom}`);
  let d = 0, j = src.indexOf('{', i);
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(i, k + 1); }
  }
  throw new Error(`qavs yopilmadi: ${nom}`);
}

// ── MUSTAQIL ETALON FORMULALAR (kod emas — biznes qoidasidan) ──
const etalonProfil = (eniSm, kengSm, uzunlik, narxM3, qoplama) => {
  const e = eniSm / 100, k = kengSm / 100;
  let narx = (e * k * narxM3 / 2) * uzunlik;
  if (qoplama) narx *= 2;
  return { hajm: e * k * uzunlik / 2, narx };
};
const etalonPanel = (eniSm, qalinSm, miqdor, narxM3, qoplama) => {
  const e = eniSm / 100, q = qalinSm / 100;
  let narx = (e * q * narxM3) * miqdor;
  if (qoplama) narx *= 2;
  return { hajm: e * q * miqdor, narx };
};

// ── Soxta DOM ──
function soxtaElement(qiymat) {
  return { value: qiymat === undefined ? '' : String(qiymat), style: {},
           textContent: '', title: '', disabled: false };
}
function soxtaQator(maydonlar, dataset) {
  const el = {};
  for (const [k, v] of Object.entries(maydonlar)) el['.' + k] = soxtaElement(v);
  for (const k of ['i-vol', 'i-price', 'i-perm', 'i-vol-relock'])
    if (!el['.' + k]) el['.' + k] = soxtaElement('');
  return {
    dataset: dataset || {},
    querySelector: (s) => el[s] || null,
    querySelectorAll: () => [],
    _el: el,
  };
}

// ════════════════════════════════════════════════════════════════
bolim("A. orders.html :: calculateItem() — buyurtma sahifasidagi narx");
// ════════════════════════════════════════════════════════════════

const ORDERS = T('orders.html');
const ctxA = {
  console,
  PENOPLASTS: [{ id: 1, volPerUnit: 0.9, isDefault: true },
               { id: 2, volPerUnit: 1.2, isDefault: false }],
  document: { getElementById: (id) => soxtaElement(id === 'base_price' ? '1000000' : '') },
  // hisobga ta'sir qilmaydigan yordamchilar — bo'sh qoldiriladi
  updatePenoWarn() {}, checkDeliveredLimit() {}, checkFpLimit() {},
  updateTotal() {}, updateLiveStats() {}, updateDetalSummary() {},
};
vm.createContext(ctxA);
for (const nom of ['parseNum', 'formatNum', 'calcSubDetailRow', 'calculateItem'])
  vm.runInContext(olib(ORDERS, nom), ctxA, { filename: `orders.html:${nom}` });

const BAZA = 1000000;

function ishlat(maydonlar, dataset) {
  const row = soxtaQator(maydonlar, dataset);
  ctxA.calculateItem(row);
  return { narx: parseFloat(row.dataset.price), hajm: parseFloat(row.dataset.volume), row };
}

// A1. Profil — i-h = Eni, i-w = Kenglik
for (const [h, w, l, c] of [[20, 10, 3, false], [15, 7.5, 3.4, true],
                            [8, 4, 2.5, false], [30, 12, 6, true],
                            [5.5, 3.2, 12.75, false]]) {
  const r = ishlat({ 'i-type': 'profil', 'i-h': h, 'i-w': w, 'i-t': 0, 'i-l': l,
                     'i-q': 1, 'i-c': String(c) });
  const k = etalonProfil(h, w, l, BAZA, c);
  check(`A profil ${h}x${w}cm ${l}m ${c ? 'qoplamali' : 'oddiy'} — narx`, r.narx, k.narx);
  check(`A profil ${h}x${w}cm ${l}m ${c ? 'qoplamali' : 'oddiy'} — hajm`, r.hajm, k.hajm);
}

// A2. Panel — i-h = Eni, i-t = Qalinlik
for (const [h, t, q, c] of [[50, 2, 10, false], [120, 3.5, 7, true],
                            [33.3, 1.7, 4.5, false], [60, 5, 1, true]]) {
  const r = ishlat({ 'i-type': 'panel', 'i-h': h, 'i-w': 0, 'i-t': t, 'i-l': 0,
                     'i-q': q, 'i-c': String(c) });
  const k = etalonPanel(h, t, q, BAZA, c);
  check(`A panel ${h}x${t}cm x${q} ${c ? 'qoplamali' : 'oddiy'} — narx`, r.narx, k.narx);
  check(`A panel ${h}x${t}cm x${q} ${c ? 'qoplamali' : 'oddiy'} — hajm`, r.hajm, k.hajm);
}

// A3. Donali — YANGI usul: hajm o'lchamdan, narx SHUNDAN kelib chiqadi
for (const [h, t, chiqim, qty, c] of [[12, 8, 4, 25, false], [10, 10, 2, 7, false],
                                      [12, 8, 4, 25, true], [6.5, 3, 5, 100, false]]) {
  const r = ishlat({ 'i-type': 'dona', 'i-h': h, 'i-t': t, 'i-w': 0, 'i-l': 0,
                     'i-q': qty, 'i-c': String(c), 'i-donayield': chiqim,
                     'i-unitprice': 0 });
  const birHajm = (h / 100) * (t / 100) / 2 / chiqim;
  let birNarx = birHajm * BAZA;
  if (c) birNarx *= 2;
  check(`A dona ${h}x${t}cm 1m dan ${chiqim} ta, ${qty} dona${c ? ' qoplamali' : ''} — hajm`,
        r.hajm, birHajm * qty);
  check(`A dona ${h}x${t}cm 1m dan ${chiqim} ta, ${qty} dona${c ? ' qoplamali' : ''} — narx`,
        r.narx, birNarx * qty);
}

// A4. Donali — QULFLANGAN hajm: narx erkin, hajm o'zgarmaydi, x2 QILINMAYDI
{
  const r = ishlat({ 'i-type': 'dona', 'i-h': 12, 'i-t': 8, 'i-w': 0, 'i-l': 0,
                     'i-q': 10, 'i-c': 'true', 'i-donayield': 4,
                     'i-unitprice': '5000' },
                   { donaVolLocked: 'true', donaVolPerUnit: '0.0012' });
  check('A dona QULFLANGAN — hajm saqlangan qiymatdan', r.hajm, 0.0012 * 10);
  check('A dona QULFLANGAN qoplamali — narx QAYTA x2 qilinmaydi', r.narx, 50000);
}

// A5. Donali — tayyor mahsulotdan: narx yakuniy, x2 yo'q, hajm 0
{
  const r = ishlat({ 'i-type': 'dona', 'i-h': 12, 'i-t': 8, 'i-w': 0, 'i-l': 0,
                     'i-q': 6, 'i-c': 'true', 'i-donayield': 4,
                     'i-unitprice': '7000' }, { fpId: '5' });
  check('A dona tayyor mahsulotdan — narx to\'g\'ridan-to\'g\'ri', r.narx, 42000);
  check('A dona tayyor mahsulotdan — hajm 0', r.hajm, 0);
}

// A6. Blok — 1 metr narxi = blok narxi / chiqim; hajm = blok soni x blok hajmi
for (const [blokNarx, chiqim, kerak] of [[800000, 2.5, 30], [600000, 3, 10],
                                         [1000000, 1.75, 7]]) {
  const r = ishlat({ 'i-type': 'blok', 'i-h': 0, 'i-w': 0, 'i-t': 0,
                     'i-l': chiqim, 'i-q': kerak, 'i-c': 'false',
                     'i-blokprice': String(blokNarx), 'i-peno': '1' });
  check(`A blok ${blokNarx}so'm, 1 blokdan ${chiqim}m, ${kerak}m kerak — narx`,
        r.narx, (blokNarx / chiqim) * kerak);
  check(`A blok ${blokNarx}so'm, 1 blokdan ${chiqim}m, ${kerak}m kerak — hajm`,
        r.hajm, (kerak / chiqim) * 0.9);
}

// A7. Oddiy turkumlar — miqdor x birlik narxi, penoplast hajmi 0
for (const kat of ['termopanel', 'loy_sotish', 'gips', 'mrp_product']) {
  const r = ishlat({ 'i-type': kat, 'i-h': 0, 'i-w': 0, 'i-t': 0, 'i-l': 0,
                     'i-q': 15, 'i-c': 'false', 'i-unitprice': '40000' });
  check(`A ${kat} — narx = 15 x 40 000`, r.narx, 600000);
  check(`A ${kat} — penoplast hajmi 0`, r.hajm, 0);
}

// ════════════════════════════════════════════════════════════════
bolim("B. orders.html :: calcSubDetailRow() — ichki qo'shimcha detal");
// ════════════════════════════════════════════════════════════════

function subIshlat(maydonlar) {
  const el = {};
  for (const [k, v] of Object.entries(maydonlar)) el['.' + k] = soxtaElement(v);
  for (const k of ['sd-info']) if (!el['.' + k]) el['.' + k] = soxtaElement('');
  return ctxA.calcSubDetailRow({ querySelector: (s) => el[s] || null }, BAZA);
}

for (const [h, w, l, c] of [[6, 4, 3, false], [8, 5, 2.5, true]]) {
  const r = subIshlat({ 'sd-type': 'profil', 'sd-name': 'ichki', 'sd-w': h,
                        'sd-t': w, 'sd-l': l, 'sd-q': 1, 'sd-c': String(c) });
  const k = etalonProfil(h, w, l, BAZA, c);
  check(`B ichki profil ${h}x${w}cm ${l}m — hajm`, r.volume, k.hajm);
  check(`B ichki profil ${h}x${w}cm ${l}m — narx`, r.price, k.narx);
}
for (const [h, t, q, c] of [[30, 2, 5, false], [25, 3, 4, true]]) {
  const r = subIshlat({ 'sd-type': 'panel', 'sd-name': 'ichki', 'sd-w': h,
                        'sd-t': t, 'sd-l': 0, 'sd-q': q, 'sd-c': String(c) });
  const k = etalonPanel(h, t, q, BAZA, c);
  check(`B ichki panel ${h}x${t}cm x${q} — hajm`, r.volume, k.hajm);
  check(`B ichki panel ${h}x${t}cm x${q} — narx`, r.price, k.narx);
}

// ════════════════════════════════════════════════════════════════
bolim("C. finished.html :: pCalc() — MUSTAQIL uchinchi nusxa");
// ════════════════════════════════════════════════════════════════

const FINISHED = T('finished.html');
const pMaydon = {};
const ctxC = {
  console,
  PENOS: [{ id: 1, volPerUnit: 0.9, isDefault: true }],
  // Loy tan narxi — bu testda 0, chunki bu yerda QOPLAMA XOMASHYOSI emas,
  // narx FORMULASI tekshiriladi (loy tan narxi Python testida F bo'limida).
  loyCostPerKg: 0,
  escapeHtml: (s) => String(s),
  fmt: (n) => String(n),
  pToggleVolLock() {},
  window: {},
  document: {
    getElementById: (id) => (pMaydon[id] = pMaydon[id] || soxtaElement('')),
  },
};
vm.createContext(ctxC);
for (const nom of ['parseNum', 'pCalc'])
  vm.runInContext(olib(FINISHED, nom), ctxC, { filename: `finished.html:${nom}` });

function pIshlat(qiymatlar) {
  for (const k of Object.keys(pMaydon)) delete pMaydon[k];
  for (const [k, v] of Object.entries(qiymatlar)) pMaydon[k] = soxtaElement(v);
  for (const k of ['p-calc', 'p-price', 'p-up', 'p-loy', 'p-m3', 'p-peno',
                   'p-donayield', 'p-blokprice', 'p-w', 'p-h', 'p-t', 'p-l', 'p-q'])
    if (!pMaydon[k]) pMaydon[k] = soxtaElement('');
  ctxC.pCalc();
  // pCalc natijasini o'zi `window._pCalc` ga yozadi — o'sha olinadi
  // (ekrandagi yaxlitlangan matn emas, aniq qiymat).
  return ctxC.window._pCalc;
}

// C1. pCalc PROFIL — orders.html bilan AYNAN bir xil chiqishi SHART
for (const [h, w, l, c] of [[20, 10, 3, false], [15, 7.5, 3.4, true],
                            [30, 12, 6, true]]) {
  const p = pIshlat({ 'p-type': 'profil', 'p-h': h, 'p-w': w, 'p-t': 0,
                      'p-l': l, 'p-q': 1, 'p-coated': String(c),
                      'p-m3': String(BAZA) });
  const k = etalonProfil(h, w, l, BAZA, c);
  check(`C pCalc profil ${h}x${w}cm ${l}m — 1 metr narxi`,
        p.perUnitPrice, k.narx / l);
  const o = ishlat({ 'i-type': 'profil', 'i-h': h, 'i-w': w, 'i-t': 0, 'i-l': l,
                     'i-q': 1, 'i-c': String(c) });
  check(`C pCalc profil ${h}x${w}cm ${l}m — orders.html bilan BIR XIL`,
        p.price, o.narx);
}

// C2. pCalc PANEL
for (const [h, t, q, c] of [[50, 2, 10, false], [120, 3.5, 7, true]]) {
  const p = pIshlat({ 'p-type': 'panel', 'p-h': h, 'p-w': 0, 'p-t': t,
                      'p-l': 0, 'p-q': q, 'p-coated': String(c),
                      'p-m3': String(BAZA) });
  const o = ishlat({ 'i-type': 'panel', 'i-h': h, 'i-w': 0, 'i-t': t, 'i-l': 0,
                     'i-q': q, 'i-c': String(c) });
  check(`C pCalc panel ${h}x${t}cm x${q} — etalon narx`,
        p.price, etalonPanel(h, t, q, BAZA, c).narx);
  check(`C pCalc panel ${h}x${t}cm x${q} — orders.html bilan BIR XIL`,
        p.price, o.narx);
}

// C3. pCalc BLOK
for (const [blokNarx, chiqim, kerak] of [[800000, 2.5, 30], [600000, 3, 10]]) {
  const p = pIshlat({ 'p-type': 'blok', 'p-h': 0, 'p-w': 0, 'p-t': 0,
                      'p-l': chiqim, 'p-q': kerak, 'p-coated': 'false',
                      'p-blokprice': String(blokNarx), 'p-peno': '1' });
  const o = ishlat({ 'i-type': 'blok', 'i-h': 0, 'i-w': 0, 'i-t': 0,
                     'i-l': chiqim, 'i-q': kerak, 'i-c': 'false',
                     'i-blokprice': String(blokNarx), 'i-peno': '1' });
  check(`C pCalc blok ${blokNarx}so'm / ${chiqim}m x ${kerak}m — etalon narx`,
        p.price, (blokNarx / chiqim) * kerak);
  check(`C pCalc blok ${blokNarx}so'm / ${chiqim}m x ${kerak}m — orders.html bilan BIR XIL`,
        p.price, o.narx);
}

// C4. pCalc DONALI — yangi usul
for (const [h, t, chiqim, qty, c] of [[12, 8, 4, 25, false], [10, 10, 2, 7, true]]) {
  const p = pIshlat({ 'p-type': 'dona', 'p-h': h, 'p-w': 0, 'p-t': t, 'p-l': 0,
                      'p-q': qty, 'p-coated': String(c), 'p-m3': String(BAZA),
                      'p-donayield': chiqim, 'p-up': '0' });
  const o = ishlat({ 'i-type': 'dona', 'i-h': h, 'i-t': t, 'i-w': 0, 'i-l': 0,
                     'i-q': qty, 'i-c': String(c), 'i-donayield': chiqim,
                     'i-unitprice': 0 });
  let birNarx = (h / 100) * (t / 100) / 2 / chiqim * BAZA;
  if (c) birNarx *= 2;
  check(`C pCalc dona ${h}x${t}cm 1m dan ${chiqim} ta — etalon narx`,
        p.price, birNarx * qty);
  check(`C pCalc dona ${h}x${t}cm 1m dan ${chiqim} ta — orders.html bilan BIR XIL`,
        p.price, o.narx);
}

// ════════════════════════════════════════════════════════════════
console.log(`\n${'='.repeat(66)}`);
console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
if (FAILED.length) {
  console.log(`${'='.repeat(66)}\nYIQILGANLAR:`);
  for (const f of FAILED) console.log('  - ' + f);
}
console.log('='.repeat(66));
process.exit(FAIL === 0 ? 0 : 1);
