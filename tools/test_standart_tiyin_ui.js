#!/usr/bin/env node
/**
 * test_standart_tiyin_ui.js — kech96 (2026-09-27), 125-band + K96-1 (brauzer qismi).
 *
 * NIMA UCHUN KERAK
 * ----------------
 * 125: hisoblangan STANDART qiymatlar butun so'mga yaxlitlanardi, ta'minotchi "To'liq to'lash" tugmalari noto'g'ri
 * summani yozardi. HAQIQIY brauzerda O'LCHANGAN (Playwright + uvicorn, `work/probe125.py`, asl = zip 89, SQLite = PG):
 *   • orders blok: qoplamali "1 blok narxi" 1 500 000,75 → qoplama Yo'q (750 000) → Bor (1 500 001);
 *     qoplamasiz 1 000 000,50 → koeffitsient 2.5 → 2 500 001; MRP (koeffitsient 2.5) 1 000 000,50 → 400 000 → 1 000 001;
 *   • finished TM formasi Donalik: Eni 10, Qalinlik 10, 1 metrdan 3 dona, "1 m³ narxi" 910 000 → "1 dona narxi" 1 517
 *     (saqlandi ham), buyurtma sahifasi AYNAN shu o'lchamda 1 516.67; kiritilmagan sotuv narxi — Math.round;
 *   • suppliers "To'liq to'lash": faqat JORIY qator va butun so'm — savatdagi qatorlar tushib qolardi (2 × 500,50 +
 *     3 × 1 000 → to'lov 3 000, oyna "✓ To'liq to'landi", qarz 1 001 QOLDI); 7 × 1 000,07 = 7 000.49 → 7 000, 0.49
 *     yashirin qarz;
 *   • supplier_receive: "Qarzga qoladi" va "To'liq to'lash" qo'shimcha xarajatlarni (transport …) ham qo'shardi —
 *     ular ta'minotchi qarziga KIRMAYDI (korxona xarajati): 100 000 + transport 20 000 → to'lov 120 000 (20 000
 *     yashirin ortiqcha to'lov, kassa −140 000); 7 000.49 → 7 000.
 * K96-1: finished TM formasida Blok qoplamasi almashtirilganda "1 blok narxi" QAYTA hisoblanmasdi (orders.html da
 * hisoblanadi) — qoplamasiz mahsulot qoplamali narxda saqlanardi.
 *
 * BO'LIMLAR
 * ---------
 *   S — statik: yordamchilar 4 sahifada AYNAN matn, eski yaxlitlash naqshlari yo'q.
 *   O — orders.html HAQIQIY funksiyalari: onBlokPriceInput / recalcBlokPrice, onMrpPriceInput / recalcMrpPrice.
 *   F — finished.html: recalcBlokPrice, setPCoating (K96-1), pCalc (Donalik), saveProduce (yuboriladigan narx).
 *   P — suppliers.html: apFillFullPaid, apCalc, apAddToBasket, saveAddPurchase (to'lov taqsimoti — tiyinda aniq).
 *   R — supplier_receive.html: updateSummary, apPayFull, submitReceive (tana va xabar).
 *
 * Funksiyalar HTML dan JONLI o'qiladi; topilmagan funksiya / istisno — yiqilgan tekshiruv (asl — tuzatishdan
 * oldingi — shablonlarga qarshi QULAMAYDI).
 *
 * ISHLATISH
 * ---------
 *     node tools/test_standart_tiyin_ui.js
 *     node tools/test_standart_tiyin_ui.js boshqa/templates     (mutatsiya uchun)
 *
 * Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const TDIR = process.argv[2] || path.join(ROOT, 'templates');
function oqi(nom) {
  try { return fs.readFileSync(path.join(TDIR, nom + '.html'), 'utf8'); } catch (e) { return ''; }
}
// Jinja teglari (`{% if … %}` / `{% endif %}`) — vm uchun olib tashlanadi (ichidagi JS qoladi).
function jinjasiz(s) { return String(s).replace(/\{%[^%]*%\}/g, ''); }
const SRC = { orders: oqi('orders'), finished: oqi('finished'), suppliers: oqi('suppliers'),
              receive: oqi('supplier_receive') };

let OK = 0, FAIL = 0;
const FAILED = [];
function tekshir(label, shart, izoh) {
  if (shart) { OK++; console.log(`  ✓ ${label}`); }
  else {
    FAIL++; FAILED.push(label + (izoh ? ` (${izoh})` : ''));
    console.log(`  ✗ ${label}${izoh ? '   — ' + izoh : ''}`);
  }
}
function bolim(t) { console.log(`\n${'='.repeat(66)}\n${t}\n${'='.repeat(66)}`); }
function jsn(x) { try { return JSON.stringify(x); } catch (e) { return String(x); } }

// Funksiyani HTML dan nomi bo'yicha ajratib olish (`async` bilan), qavs hisobi bilan.
function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom.replace(/\$/g, '\\$') + '\\s*\\(');
  const m = re.exec(src);
  if (!m) return null;
  const i = m.index;
  const j = src.indexOf('{', i + m[0].length);
  let d = 0;
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(i, k + 1); }
  }
  return null;
}
function yukla(ctx, src, nomlar, sahifa) {
  const yoq = [];
  const toza = jinjasiz(src);
  for (const n of nomlar) {
    const f = olib(toza, n);
    if (!f) { yoq.push(n); continue; }
    try { vm.runInContext(f, ctx, { filename: `${sahifa}:${n}` }); } catch (e) { yoq.push(n + '!' + e.message); }
  }
  return yoq;
}
const NARX118 = ['parseNum', 'narxMatni', 'narxniOqi', 'narxKorinishi', 'formatPriceInput'];
const YORDAM = ['_onlikQism', '_tiyinHalfUp', 'buyurtmaJami', 'tiyinga', 'pulYigindi'];

// ── Soxta DOM ──
function el(qiymat, qo) {
  return Object.assign({ value: qiymat === undefined ? '' : String(qiymat), textContent: '', innerHTML: '',
                         style: {}, dataset: {}, checked: false, disabled: false, title: '',
                         classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
                         focus() {}, scrollIntoView() {}, closest() { return null; },
                         querySelector() { return null; }, querySelectorAll() { return []; } }, qo || {});
}
function hujjat(elementlar) {
  return {
    getElementById: (id) => (Object.prototype.hasOwnProperty.call(elementlar, id) ? elementlar[id] : null),
    querySelector: () => null, querySelectorAll: () => [], activeElement: null,
    createElement: () => el(''),
  };
}
function javob(status, tana) {
  return { ok: status >= 200 && status < 300, status, json: async () => tana, text: async () => jsn(tana) };
}
function kontekst(qo) {
  const ctx = Object.assign({ console, Math, Number, String, JSON, isFinite, parseFloat, parseInt, Object, Array,
                              BigInt, Promise, setTimeout: () => 0,
                              escapeHtml: (x) => String(x == null ? '' : x) }, qo || {});
  ctx.window = ctx;
  vm.createContext(ctx);
  return ctx;
}
function qator(elementlar, dataset) {
  return { dataset: dataset || {}, querySelector: (s) => (Object.prototype.hasOwnProperty.call(elementlar, s) ? elementlar[s] : null),
           querySelectorAll: () => [], closest: () => null };
}

(async () => {
  // ════════════════════════════════════════════════════════════════════════════
  bolim('S. Statik — yordamchilar 4 sahifada AYNAN, eski yaxlitlash naqshlari yo\'q');
  for (const n of YORDAM) {
    const asl = olib(SRC.orders, n);
    tekshir(`S1 orders.html: ${n} bor`, !!asl);
    for (const [sahifa, src] of [['finished', SRC.finished], ['suppliers', SRC.suppliers], ['supplier_receive', SRC.receive]]) {
      const f = olib(src, n);
      tekshir(`S1 ${sahifa}: ${n} — orders.html dagi bilan AYNAN matn`, !!asl && f === asl, f ? 'farq' : "yo'q");
    }
  }
  const ESKI = [
    ['orders: blok standarti Math.round', SRC.orders, 'formatNum(Math.round(isCoated ? base * mult : base))'],
    ['finished: blok standarti Math.round', SRC.finished, 'fmt(Math.round(isCoated ? base * mult : base))'],
    ['finished: "1 dona narxi" Math.round', SRC.finished, 'upEl.value = Math.round(unitPrice)'],
    ['finished: sotuv narxi Math.round', SRC.finished, 'Math.round(c.perUnitPrice'],
    ['suppliers: "To\'liq to\'lash" Math.round', SRC.suppliers, 'Math.round(qty * price)'],
    ['suppliers: xom qator jamisi (qty*price)', SRC.suppliers, 'total: qty*price'],
    ['supplier_receive: xom qator jamisi (qty*price)', SRC.receive, 'total:qty*price'],
    ['supplier_receive: "To\'liq to\'lash" fmt(grand)', SRC.receive, "value = fmt(grand)"],
  ];
  for (const [nom, src, naqsh] of ESKI) tekshir(`S2 ${nom} — yo'q`, src.indexOf(naqsh) < 0, naqsh);
  const payFull = olib(SRC.receive, 'apPayFull') || '';
  tekshir('S3 supplier_receive apPayFull qo\'shimcha xarajatlarni QO\'SHMAYDI', !!payFull && payFull.indexOf('apGetExtraCosts') < 0
          && payFull.indexOf('transport') < 0, payFull.slice(0, 120));
  const setPC = olib(SRC.finished, 'setPCoating') || '';
  tekshir('S4 finished setPCoating Blokda recalcBlokPrice ni chaqiradi (K96-1)',
          setPC.indexOf("'blok'") >= 0 && setPC.indexOf('recalcBlokPrice()') >= 0, setPC.slice(0, 160));

  // ════════════════════════════════════════════════════════════════════════════
  bolim('O. orders.html — blok / MRP standarti');
  try {
    let hisob = 0;
    const ctx = kontekst({ calculateItem: () => { hisob++; } });
    const yoq = yukla(ctx, SRC.orders, NARX118.concat(YORDAM, ['formatNum', 'recalcBlokPrice', 'onBlokPriceInput',
      'recalcMrpPrice', 'onMrpPriceInput']), 'orders');
    const bp = el(''), c = el('true'), mult = el('2');
    const r = qator({ '.i-blokprice': bp, '.i-c': c, '.i-blokmult': mult }, {});
    bp.value = '1 500 000,75';
    ctx.onBlokPriceInput(r);
    tekshir('O1 blok: qoplamali 1 500 000,75 yozildi → asos 750 000.375', Number(r.dataset.blokBase) === 750000.375,
            jsn({ base: r.dataset.blokBase, yoq }));
    c.value = 'false'; ctx.recalcBlokPrice(r);
    tekshir('O2 blok: qoplama Yo\'q → "750 000.38" (asl: "750 000")', bp.value === '750 000.38', bp.value);
    c.value = 'true'; ctx.recalcBlokPrice(r);
    tekshir('O3 blok: qoplama Bor qayta → "1 500 000.75" — yozilgan qiymat qaytdi (asl: "1 500 001")',
            bp.value === '1 500 000.75', bp.value);
    c.value = 'false'; bp.value = '1 000 000,50'; ctx.onBlokPriceInput(r);
    mult.value = '2.5'; c.value = 'true'; ctx.recalcBlokPrice(r);
    tekshir('O4 blok: 1 000 000,50 × 2.5 → "2 500 001.25" (asl: "2 500 001")', bp.value === '2 500 001.25', bp.value);
    c.value = 'false'; bp.value = '1 000 000,25'; ctx.onBlokPriceInput(r);
    c.value = 'true'; ctx.recalcBlokPrice(r);
    tekshir('O5 blok: aniq yarim tiyin 1 000 000.25 × 2.5 = 2 500 000.625 → "2 500 000.63" (HALF_UP)',
            bp.value === '2 500 000.63', bp.value);
    mult.value = '3'; bp.value = '1 000,01'; ctx.onBlokPriceInput(r);
    c.value = 'false'; ctx.recalcBlokPrice(r);
    const yoqQiymat = bp.value;
    c.value = 'true'; ctx.recalcBlokPrice(r);
    tekshir('O6 blok: float shovqini (1 000,01 / 3 × 3) → Yo\'q "333.34", Bor "1 000.01"',
            yoqQiymat === '333.34' && bp.value === '1 000.01', jsn([yoqQiymat, bp.value]));
    mult.value = '2'; c.value = 'false'; bp.value = '1 000 000'; ctx.onBlokPriceInput(r);
    c.value = 'true'; ctx.recalcBlokPrice(r);
    tekshir('O7 blok: butun narx 1 000 000 × 2 → "2 000 000" (kasrsiz)', bp.value === '2 000 000', bp.value);
    tekshir('O8 blok: har qayta hisobdan keyin calculateItem chaqirildi', hisob >= 8, String(hisob));

    const up = el(''), c2 = el('true');
    const m = qator({ '.i-unitprice': up, '.i-c': c2 }, { mrpCoatingMult: '2.5' });
    up.value = '1 000 000,50'; ctx.onMrpPriceInput(m);
    c2.value = 'false'; ctx.recalcMrpPrice(m);
    const mYoq = up.value;
    c2.value = 'true'; ctx.recalcMrpPrice(m);
    tekshir('O9 MRP (×2.5): 1 000 000,50 → Yo\'q "400 000.2" (asl "400 000"), Bor "1 000 000.5" (asl "1 000 001")',
            mYoq === '400 000.2' && up.value === '1 000 000.5', jsn([mYoq, up.value]));
    m.dataset.mrpCoatingMult = '1.5'; c2.value = 'false'; up.value = '333 333,33'; ctx.onMrpPriceInput(m);
    c2.value = 'true'; ctx.recalcMrpPrice(m);
    tekshir('O10 MRP (×1.5): 333 333.33 → "499 999.995" → "500 000" (HALF_UP, float shovqinisiz)',
            up.value === '500 000', up.value);
  } catch (x) { tekshir('O blok / MRP funksiyalari ishga tushdi', false, x.message); }

  // ════════════════════════════════════════════════════════════════════════════
  bolim('F. finished.html — TM formasi');
  function finKontekst(e, qo) {
    const ctx = kontekst(Object.assign({ document: hujjat(e), syncPCoatingUI: () => {}, PENOS: [], loyCostPerKg: 0,
                                         loyRecipeName: '', customConfirm: async () => true, closeProduceModal: () => {},
                                         loadFp: () => {}, showMsg: () => {} }, qo || {}));
    const yoq = yukla(ctx, SRC.finished, NARX118.concat(YORDAM, ['fmt', 'recalcBlokPrice', 'onBlokPriceInput', 'setPCoating',
      'pCalc', 'saveProduce']), 'finished');
    return { ctx, yoq };
  }
  try {
    const e = { 'p-blokprice': el(''), 'p-coated': el('true'), 'p-blokmult': el('2'), 'p-type': el('blok') };
    const { ctx, yoq } = finKontekst(e);
    let pc = 0;
    ctx.pCalc = () => { pc++; };
    e['p-blokprice'].value = '1 500 000,75'; ctx.onBlokPriceInput();
    ctx.setPCoating(el(''), false);
    const yoqQ = e['p-blokprice'].value;
    tekshir('F1 K96-1: Blok, qoplama Yo\'q (setPCoating) → narx qayta hisoblandi "750 000.38" (asl: o\'zgarmas "1 500 000,75")',
            yoqQ === '750 000.38', jsn({ yoqQ, yoq }));
    ctx.setPCoating(el(''), true);
    tekshir('F2 K96-1: Blok, qoplama Bor → "1 500 000.75"', e['p-blokprice'].value === '1 500 000.75', e['p-blokprice'].value);
    tekshir('F3 setPCoating → pCalc chaqirildi (har safar)', pc >= 2, String(pc));
    e['p-type'].value = 'profil'; e['p-blokprice'].value = 'X';
    const pc0 = pc;
    ctx.setPCoating(el(''), false);
    tekshir('F4 Profilda setPCoating blok narxiga TEGMAYDI, pCalc chaqiriladi', e['p-blokprice'].value === 'X' && pc === pc0 + 1,
            jsn([e['p-blokprice'].value, pc - pc0]));
    e['p-type'].value = 'blok'; e['p-coated'].value = 'false'; e['p-blokmult'].value = '2.5';
    e['p-blokprice'].value = '1 000 000,50'; ctx.onBlokPriceInput();
    e['p-coated'].value = 'true'; ctx.recalcBlokPrice();
    tekshir('F5 recalcBlokPrice: 1 000 000,50 × 2.5 → "2 500 001.25" (asl: "2 500 001")',
            e['p-blokprice'].value === '2 500 001.25', e['p-blokprice'].value);
  } catch (x) { tekshir('F blok funksiyalari ishga tushdi', false, x.message); }

  function donaEl(qoplama) {
    return { 'p-type': el('dona'), 'p-h': el('10'), 'p-w': el(''), 'p-t': el('10'), 'p-l': el('0'), 'p-q': el('6'),
             'p-coated': el(qoplama ? 'true' : 'false'), 'p-m3': el('910 000'), 'p-calc': el(''), 'p-up': el(''),
             'p-donayield': el('3'), 'p-peno': el('9'), 'p-loy': el(''), 'p-price': el(''), 'p-blokprice': el(''),
             'p-error': el(''), 'p-name': el('T1 Donalik'), 'p-recipe': el(''), 'p-notes': el('') };
  }
  try {
    const e = donaEl(false);
    const { ctx, yoq } = finKontekst(e, { PENOS: [{ id: 9, name: 'P', vol: 1, price: 500000 }] });
    vm.runInContext('_pDonaVolLocked = false; _pDonaVolPerUnit = 0;', ctx);
    ctx.pCalc();
    const c = ctx._pCalc || {};
    tekshir('F6 Donalik (10 × 10, 1 m dan 3, 910 000): "1 dona narxi" "1516.67" (asl: "1517")', e['p-up'].value === '1516.67',
            jsn({ up: e['p-up'].value, yoq }));
    tekshir('F7 hisob: 1 birlik narxi 1 516.67, jami 1 516.67 × 6 = 9 100.02 (orders.html bilan AYNAN)',
            c.perUnitPrice === 1516.67 && c.price === 9100.02, jsn({ pu: c.perUnitPrice, p: c.price }));
    tekshir('F8 xulosa oynasi "1 dona narxi: 1 516.67"', String(e['p-calc'].innerHTML).indexOf('1 516.67 so\'m') >= 0,
            String(e['p-calc'].innerHTML).slice(0, 200));
    const e2 = donaEl(true);
    const k2 = finKontekst(e2, { PENOS: [{ id: 9, name: 'P', vol: 1, price: 500000 }] });
    vm.runInContext('_pDonaVolLocked = false; _pDonaVolPerUnit = 0;', k2.ctx);
    k2.ctx.pCalc();
    const c2 = k2.ctx._pCalc || {};
    tekshir('F9 qoplamali: 1 516.666… × 2 = 3 033.333… → "3033.33", jami 3 033.33 × 6 = 18 199.98',
            e2['p-up'].value === '3033.33' && c2.price === 18199.98, jsn({ up: e2['p-up'].value, p: c2.price }));
    const e3 = donaEl(false);
    e3['p-q'].value = '11';
    const k3 = finKontekst(e3, { PENOS: [{ id: 9, name: 'P', vol: 1, price: 500000 }] });
    vm.runInContext('_pDonaVolLocked = false; _pDonaVolPerUnit = 0;', k3.ctx);
    k3.ctx.pCalc();
    tekshir('F12 jami float shovqinisiz: 1 516.67 × 11 = 16 683.37 (xom ko\'paytma 16 683.370000000003)',
            (k3.ctx._pCalc || {}).price === 16683.37, jsn((k3.ctx._pCalc || {}).price));
  } catch (x) { tekshir('F pCalc (Donalik) ishga tushdi', false, x.message); }
  try {
    const e = donaEl(false);
    let tana = null;
    const { ctx, yoq } = finKontekst(e, { fetch: async (u, o) => { tana = JSON.parse(o.body); return javob(200, { name: 'x', quantity: 6, unit: 'dona' }); } });
    vm.runInContext('_pDonaVolLocked = false; _pDonaVolPerUnit = 0;', ctx);
    ctx._pCalc = { volume: 0.01, price: 9100.000000000002, perUnitPrice: 1516.666666666667, count: 6, unit: 'dona' };
    e['p-up'].value = '1516.67';
    await ctx.saveProduce();
    tekshir('F10 saveProduce: sotuv narxi kiritilmagan → hisoblangani 2 xona 1 516.67 (asl: 1 517)',
            !!tana && tana.unit_price === 1516.67, jsn({ u: tana && tana.unit_price, yoq }));
    e['p-price'].value = '1 600,5';
    tana = null;
    await ctx.saveProduce();
    tekshir('F11 saveProduce: sotuv narxi kiritilgan → AYNAN 1 600.5', !!tana && tana.unit_price === 1600.5, jsn(tana && tana.unit_price));
  } catch (x) { tekshir('F saveProduce ishga tushdi', false, x.message); }

  // ════════════════════════════════════════════════════════════════════════════
  bolim('P. suppliers.html — "To\'liq to\'lash" va to\'lov taqsimoti');
  function supKontekst(qo) {
    const e = { 'ap-qty': el(''), 'ap-price': el(''), 'ap-paid-now': el(''), 'ap-total': el(''), 'ap-debt-hint': el(''),
                'ap-basket': el(''), 'ap-basket-list': el(''), 'ap-basket-total': el(''), 'ap-save-btn': el(''),
                'ap-item': el(''), 'ap-transport-payer': el('none'), 'ap-transport-cost': el(''), 'ap-volume': el(''),
                'addPurchaseForm': el('') };
    const tanalar = [];
    const ctx = kontekst(Object.assign({ document: hujjat(e), showMsg: () => {}, openHistory: () => {}, loadSuppliers: () => {},
      fetch: async (u, o) => {
        const t = JSON.parse(o.body); tanalar.push(t);
        const jami = buyurtmaJamiPy(t.quantity, t.price_per_unit);
        const pn = Math.min(t.paid_now, jami);
        return javob(200, { paid_now: pn, debt_remains: Math.round((jami - pn) * 100) / 100 });
      } }, qo || {}));
    vm.runInContext('var apBasket = []; var invItems = [{id: 11, item_name: "A", unit: "kg", is_penoplast: false},'
      + ' {id: 12, item_name: "B", unit: "kg", is_penoplast: false}, {id: 13, item_name: "C", unit: "kg", is_penoplast: false}];'
      + ' var currentSupplierId = 5; var apCreatingNewItem = false; var _tanlangan = 11;'
      + ' async function apResolveItemId() { return _tanlangan; }', ctx);
    const yoq = yukla(ctx, SRC.suppliers, NARX118.concat(YORDAM, ['fmt', 'apJoriyJami', 'apFillFullPaid', 'apCalc',
      'apAddToBasket', 'renderApBasket', 'round2', 'saveAddPurchase', 'apYangiPenoplastmi']), 'suppliers');
    return { ctx, e, tanalar, yoq };
  }
  // Server `_xarid_narx_jami` ning mustaqil (satr asosidagi) nusxasi — test ichida
  function buyurtmaJamiPy(q, n) {
    const t2 = (s) => { // satrdan tiyinga HALF_UP
      const neg = s.startsWith('-'); if (neg) s = s.slice(1);
      let [a, b = ''] = s.split('.'); b = (b + '000').slice(0, 3);
      let t = BigInt(a + b.slice(0, 2)); if (Number(b[2]) >= 5) t += 1n; return neg ? -t : t;
    };
    const narxT = t2(String(n));
    const ql = String(q).split('.'); const qd = (ql[1] || '').length;
    const qm = BigInt(ql[0] + (ql[1] || ''));
    const x = qm * narxT; // tiyin × 10^qd
    const bo = 10n ** BigInt(qd);
    let jt = x / bo; if ((x % bo) * 2n >= bo) jt += 1n;
    return Number(jt) / 100;
  }
  try {
    const { ctx, e, yoq } = supKontekst();
    e['ap-qty'].value = '7'; e['ap-price'].value = '1 000,07';
    ctx.apFillFullPaid();
    tekshir('P1 bitta qator 7 × 1 000,07: "To\'liq to\'lash" → "7000.49" (asl: "7000")', e['ap-paid-now'].value === '7000.49',
            jsn({ v: e['ap-paid-now'].value, yoq }));
    tekshir('P2 oyna: "✓ To\'liq to\'landi", Jami "7 000.49"', e['ap-debt-hint'].innerHTML.indexOf("To'liq to'landi") >= 0
            && e['ap-total'].textContent.indexOf('7 000.49') >= 0, jsn([e['ap-debt-hint'].innerHTML, e['ap-total'].textContent]));
  } catch (x) { tekshir('P1 apFillFullPaid ishga tushdi', false, x.message); }
  try {
    const { ctx, e, tanalar } = supKontekst();
    e['ap-qty'].value = '2'; e['ap-price'].value = '500,50';
    vm.runInContext('_tanlangan = 11;', ctx);
    await ctx.apAddToBasket();
    tekshir('P3 savatga qo\'shildi: jami 1 001 (server qoidasi)', ctx.apBasket.length === 1 && ctx.apBasket[0].total === 1001,
            jsn(ctx.apBasket));
    vm.runInContext('_tanlangan = 12;', ctx);
    e['ap-qty'].value = '3'; e['ap-price'].value = '1 000';
    ctx.apFillFullPaid();
    tekshir('P4 savat 1 001 + joriy 3 000: "To\'liq to\'lash" → "4001" (asl: "3000" — savat tushib qolardi)',
            e['ap-paid-now'].value === '4001', e['ap-paid-now'].value);
    e['ap-paid-now'].value = '4000'; ctx.apCalc();
    tekshir('P5 to\'lov 4 000 (savat + joriy 4 001): oyna "Qarz qoladi: 1" (asl: "✓ To\'liq to\'landi")',
            e['ap-debt-hint'].innerHTML.indexOf('Qarz qoladi') >= 0 && e['ap-debt-hint'].innerHTML.indexOf('>1 so') >= 0,
            e['ap-debt-hint'].innerHTML);
    e['ap-paid-now'].value = '4001';
    await ctx.saveAddPurchase();
    const pn = tanalar.map(t => t.paid_now);
    tekshir('P6 saqlash: har qatorga o\'z jamisi (1 001, 3 000) — qarz 0', jsn(pn) === jsn([1001, 3000]), jsn(pn));
  } catch (x) { tekshir('P3–P6 savat oqimi ishga tushdi', false, x.message); }
  try {
    // 1.5 × 0,03: server qoidasi 0.03 × 1.5 = 0.045 → 0.05 (HALF_UP); xom float 0.045 × 100 = 4.4999… → 0.04
    const { ctx, e, tanalar } = supKontekst();
    e['ap-qty'].value = '1.5'; e['ap-price'].value = '0,03';
    vm.runInContext('_tanlangan = 11;', ctx);
    await ctx.apAddToBasket();
    tekshir('P13 savat qatori 1.5 × 0,03 → jami 0.05 (server qoidasi; xom ko\'paytma 0.04 bo\'lardi)',
            ctx.apBasket.length === 1 && ctx.apBasket[0].total === 0.05, jsn(ctx.apBasket));
    vm.runInContext('_tanlangan = 12;', ctx);
    e['ap-qty'].value = '1.5'; e['ap-price'].value = '0,03';
    ctx.apFillFullPaid();
    tekshir('P14 savat 0.05 + joriy 1.5 × 0,03 (0.05): "To\'liq to\'lash" → "0.1"', e['ap-paid-now'].value === '0.1', e['ap-paid-now'].value);
    tekshir('P16 joriy qator "Jami: 0.05" (server qoidasi; xom 0.045 → "0.04" ko\'rinardi)', e['ap-total'].textContent === "Jami: 0.05 so'm",
            e['ap-total'].textContent);
    await ctx.saveAddPurchase();
    tekshir('P15 saqlash: har qatorga 0.05 (joriy qator ham server qoidasi bilan)', jsn(tanalar.map(t => t.paid_now)) === jsn([0.05, 0.05]),
            jsn(tanalar.map(t => t.paid_now)));
  } catch (x) { tekshir('P13–P15 kasrli miqdor ishga tushdi', false, x.message); }
  try {
    const { ctx, e } = supKontekst();
    vm.runInContext('apBasket = [{ itemId: 11, itemName: "A", unit: "kg", qty: 1, price: 0.1, total: 0.1 }];', ctx);
    e['ap-qty'].value = '1'; e['ap-price'].value = '0,2';
    ctx.apFillFullPaid();
    tekshir('P17 savat 0.1 + joriy 0.2: "To\'liq to\'lash" → "0.3" (float yig\'indi "0.30000000000000004" EMAS)',
            e['ap-paid-now'].value === '0.3', e['ap-paid-now'].value);
  } catch (x) { tekshir('P17 ishga tushdi', false, x.message); }
  async function taqsim(qatorlar, tolov) {
    const { ctx, e, tanalar } = supKontekst();
    vm.runInContext('apBasket = ' + jsn(qatorlar.map((q, i) => ({ itemId: 11 + i, itemName: 'X', unit: 'kg', qty: q[0], price: q[1],
      total: buyurtmaJamiPy(q[0], q[1]) }))) + ';', ctx);
    e['ap-qty'].value = ''; e['ap-price'].value = ''; e['ap-paid-now'].value = String(tolov);
    await ctx.saveAddPurchase();
    return tanalar.map(t => t.paid_now);
  }
  function tiyin(a) { return a.reduce((s, x) => s + Math.round(x * 100), 0); }
  try {
    const t1 = await taqsim([[1, 333.33], [1, 333.33], [1, 333.34]], 500);
    tekshir('P7 taqsimot 500 → 3 qator (333.33 / 333.33 / 333.34): yig\'indi AYNAN 500.00, har biri ≤ jami',
            tiyin(t1) === 50000 && t1[0] <= 333.33 && t1[1] <= 333.33 && t1[2] <= 333.34, jsn(t1));
    const t2 = await taqsim([[3, 0.07], [7, 0.13], [1, 99.99]], 50.01);
    tekshir('P8 taqsimot 50.01 → kichik qatorlar: yig\'indi AYNAN 50.01', tiyin(t2) === 5001, jsn(t2));
    const t3 = await taqsim([[1, 9999999999.99], [1, 1]], 5000000000.37);
    tekshir('P9 katta summa (BigInt): 5 000 000 000.37 → yig\'indi AYNAN, qatordan oshmaydi',
            tiyin(t3) === 500000000037 && t3[1] <= 1, jsn(t3));
    const t4 = await taqsim([[7, 1000.07]], 7000.5);
    tekshir('P10 bardosh ichidagi ortiqcha (7 000.50 > 7 000.49): yuborilgan 7 000.49 (jamidan oshmaydi)',
            jsn(t4) === jsn([7000.49]), jsn(t4));
    const t5 = await taqsim([[2, 500.5], [3, 1000]], 4001);
    tekshir('P11 to\'liq to\'lov: har qatorga AYNAN o\'z jamisi', jsn(t5) === jsn([1001, 3000]), jsn(t5));
    let hammasi = true, misol = null;
    for (let s = 1; s <= 60; s++) {
      const q = [[1 + (s % 4), 10 + s * 7.31], [2, 0.01 * s], [1 + (s % 3), 999.99 - s]];
      const qJ = q.map(x => buyurtmaJamiPy(x[0], Math.round(x[1] * 100) / 100));
      const jT = qJ.reduce((a, x) => a + Math.round(x * 100), 0);
      const tolov = Math.floor(jT * ((s * 37) % 100) / 100) / 100;
      const t = await taqsim(q.map(x => [x[0], Math.round(x[1] * 100) / 100]), tolov);
      const okT = tiyin(t) === Math.round(tolov * 100) && t.every((v, i) => Math.round(v * 100) <= Math.round(qJ[i] * 100));
      if (!okT) { hammasi = false; misol = { q, tolov, t }; break; }
    }
    tekshir('P12 60 tasodifiy holat: yig\'indi = to\'lov (tiyinda), hech bir qator o\'z jamisidan oshmaydi', hammasi, jsn(misol));
  } catch (x) { tekshir('P7–P12 taqsimot ishga tushdi', false, x.message); }

  // ════════════════════════════════════════════════════════════════════════════
  bolim('R. supplier_receive.html — qarz va "To\'liq to\'lash" (qo\'shimcha xarajatlarsiz)');
  function rcvKontekst(qatorlar, qo) {
    const e = { 'ap-qty': el(''), 'ap-price': el(''), 'ap-paid-now': el(''), 'ap-volume': el(''), 'ap-item': el(''),
                'ap-total': el(''), 'ap-volume-wrap': el(''), 'ap-cost-transport': el(''), 'ap-cost-tushirish': el(''),
                'ap-cost-yuklash': el(''), 'ap-cost-boshqa': el(''), 'ap-add-to-cost': el(''), 'ap-due-date': el(''),
                'ap-notes': el(''), 'r-docnum': el(''), 'ap-opening-stock': el(''), 'ap-prod-type': el('umumiy'),
                'ap-prod-type-toggle': el(''), 'receive-submit-btn': el(''), 'sum-products': el(''), 'sum-transport': el(''),
                'sum-grand': el(''), 'sum-paid': el(''), 'sum-debt': el(''), 'rcv-basket-body': el(''),
                'rcv-pos-count': el(''), 'rcv-pos-total': el(''),
                // kech115 (G4-02 / G4-03): kirim sanasi (bugun) va xulosadagi ogohlantirishlar
                'r-date': el('2026-09-30'), 'sum-opening-warn': el(''), 'sum-date-warn': el('') };
    const xabar = [], tanalar = [];
    const ctx = kontekst(Object.assign({ document: hujjat(e), showMsg: (m) => { xabar.push(String(m)); }, saveDraft: () => {},
      clearDraft: () => {}, loadHistoryForSupplier: () => {},
      // kech115: bugun (sana tekshiruvi), tasdiq, saqlangach ro'yxatni qayta yuklash (K115-1)
      tkISO: () => '2026-09-30', customConfirm: async () => true, loadInvItemsForAp: () => {},
      fetch: async (u, o) => { tanalar.push(JSON.parse(o.body)); return javob(200, { success: true }); } }, qo || {}));
    vm.runInContext('var apBasket = ' + jsn(qatorlar) + '; var invItems = []; var currentSupplierId = 7;'
      + ' var prodTypeChosen = true; var apCreatingNewItem = false; var isSubmittingReceive = false;'
      + ' async function apResolveItemId() { return null; }', ctx);
    // kech115 (G4-01 / G4-03): submitReceive yozib qo'yilgan qatorni `apQatorniSavatga` orqali qo'shadi (takror — rad),
    // xulosa sanani `sanaKorinishi` bilan ko'rsatadi — ular ham yuklanadi
    const yoq = yukla(ctx, SRC.receive, NARX118.concat(YORDAM, ['fmt', 'apGetExtraCosts', 'updateSummary', 'apPayFull',
      'renderBasket', 'submitReceive', 'apQatorniSavatga', 'apTakrorQator', 'sanaKorinishi']), 'supplier_receive');
    return { ctx, e, xabar, tanalar, yoq };
  }
  const Q100 = [{ itemId: 21, itemName: 'A', unit: 'kg', qty: 100, price: 1000, total: 100000, isPenoplast: false, volumePerUnit: null }];
  const Q7 = [{ itemId: 22, itemName: 'B', unit: 'kg', qty: 7, price: 1000.07, total: 7000.49, isPenoplast: false, volumePerUnit: null }];
  try {
    const { ctx, e, yoq } = rcvKontekst(Q100);
    e['ap-cost-transport'].value = '20 000';
    ctx.updateSummary();
    tekshir('R1 100 000 + transport 20 000, to\'lovsiz: "Qarzga qoladi" 100 000 (asl: 120 000), "Umumiy summa" 120 000',
            e['sum-debt'].textContent === "100 000 so'm" && e['sum-grand'].textContent === "120 000 so'm",
            jsn({ d: e['sum-debt'].textContent, g: e['sum-grand'].textContent, yoq }));
    ctx.apPayFull();
    tekshir('R2 "To\'liq to\'lash" → "100 000" (asl: "120 000" — transport ta\'minotchiga to\'lanardi)',
            e['ap-paid-now'].value === '100 000', e['ap-paid-now'].value);
    tekshir('R3 to\'liq to\'lovdan keyin "Qarzga qoladi" 0', e['sum-debt'].textContent === "0 so'm", e['sum-debt'].textContent);
  } catch (x) { tekshir('R1–R3 updateSummary / apPayFull ishga tushdi', false, x.message); }
  try {
    const { ctx, e, xabar, tanalar } = rcvKontekst(Q7);
    ctx.apPayFull();
    tekshir('R4 7 × 1 000,07: "To\'liq to\'lash" → "7 000.49" (asl: "7 000")', e['ap-paid-now'].value === '7 000.49',
            e['ap-paid-now'].value);
    await ctx.submitReceive();
    tekshir('R5 yuborilgan paid_now 7 000.49', tanalar.length === 1 && tanalar[0].paid_now === 7000.49, jsn(tanalar.map(t => t.paid_now)));
    tekshir('R6 xabar: "To\'landi: 7 000.49", qarz YO\'Q', xabar.some(m => m.indexOf("To'landi: 7 000.49") >= 0 && m.indexOf('Qarz') < 0),
            jsn(xabar));
  } catch (x) { tekshir('R4–R6 submitReceive (tiyin) ishga tushdi', false, x.message); }
  try {
    const { ctx, e, xabar, tanalar } = rcvKontekst(Q100);
    e['ap-cost-transport'].value = '20 000'; e['ap-paid-now'].value = '50 000';
    await ctx.submitReceive();
    tekshir('R7 50 000 to\'lov, transport 20 000: yuborilgan paid_now 50 000, transport_cost 20 000',
            tanalar.length === 1 && tanalar[0].paid_now === 50000 && tanalar[0].transport_cost === 20000, jsn(tanalar));
    tekshir('R8 xabar: "Qarz: 50 000" (asl: 70 000 — transport qarzga qo\'shilardi)',
            xabar.some(m => m.indexOf('Qarz: 50 000') >= 0), jsn(xabar));
  } catch (x) { tekshir('R7–R8 submitReceive (qisman) ishga tushdi', false, x.message); }
  try {
    const { ctx, e, tanalar, xabar } = rcvKontekst([]);
    vm.runInContext('invItems = [{id: 31, item_name: "D", unit: "kg", is_penoplast: false}];'
      + ' apResolveItemId = async function () { return 31; };', ctx);
    const yoq = yukla(ctx, SRC.receive, ['apAddToBasket'], 'supplier_receive');
    e['ap-qty'].value = '1.5'; e['ap-price'].value = '0,03';
    await ctx.apAddToBasket();
    tekshir('R9 savat qatori 1.5 × 0,03 → jami 0.05 (server qoidasi)', ctx.apBasket.length === 1 && ctx.apBasket[0].total === 0.05,
            jsn({ b: ctx.apBasket, yoq }));
    // kech115 (G4-01): savatdagi qator bilan AYNAN bir xil yozib qo'yilgan qator — endi RAD (ilgari ikkinchi marta yuborilardi)
    e['ap-qty'].value = '1.5'; e['ap-price'].value = '0,03';
    e['ap-paid-now'].value = '0.1';
    await ctx.submitReceive();
    tekshir('R11 (kech115) savatdagi qator yana yozilgan (1.5 × 0,03) — yuborilmaydi, «allaqachon bor»',
            tanalar.length === 0 && xabar.some(m => m.indexOf('allaqachon bor') >= 0), jsn({ tanalar, xabar }));
    // yozib qo'yilgan BOSHQA qator (2.5 × 0,03 = 0.075 → 0.08) — server qoidasi bilan qo'shilib yuboriladi
    e['ap-qty'].value = '2.5'; e['ap-price'].value = '0,03';
    e['ap-paid-now'].value = '0.13';
    await ctx.submitReceive();
    tekshir('R10 yuborishdagi joriy qator ham server qoidasi (2.5 × 0,03 → 0.08; to\'lov 0.13, xabar "To\'landi: 0.13", qarz yo\'q)',
            tanalar.length === 1 && tanalar[0].items.length === 2 && tanalar[0].paid_now === 0.13
            && xabar.some(m => m.indexOf("To'landi: 0.13 so'm") >= 0 && m.indexOf('Qarz') < 0), jsn({ tanalar, xabar }));
  } catch (x) { tekshir('R9–R10 kasrli miqdor ishga tushdi', false, x.message); }

  console.log('\n' + '='.repeat(66));
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  console.log('='.repeat(66));
  if (FAILED.length) { console.log('YIQILGANLAR:'); for (const f of FAILED) console.log('  - ' + f); console.log('='.repeat(66)); }
  process.exit(FAIL ? 1 : 0);
})();
