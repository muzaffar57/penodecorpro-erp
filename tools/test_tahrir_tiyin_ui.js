#!/usr/bin/env node
/**
 * test_tahrir_tiyin_ui.js — kech95 (2026-09-27), 124-band + 117-band (brauzer qismi).
 *
 * NIMA UCHUN KERAK
 * ----------------
 * 124: tahrir formalari tiyinli qiymatni YAXLITLAB to'ldirardi (`formatNum` / `fmt` / `fmtFull` —
 * Math.round), "Saqlash" / "OK" bosilsa qiymat JIMGINA yaxlitlanib saqlanardi. HAQIQIY brauzerda
 * O'LCHANGAN (Playwright + uvicorn, `work/probe124.py`, asl = zip 88):
 *   • orders tahriri: kelishilgan 6 228 752.75 → "6 228 753" → saqlashda +0.25 (qarz ham +0.25);
 *     asosiy narx 1 200 000.50 → 1 200 001; panel "1 m³ narxi" 1 000 000.25 → 1 000 000 (jami o'zgardi);
 *   • orders Donalik "1 dona narxi" 3 997.13 → "3 997"; foydalanuvchi "3 997.40" yozsa ham 3 997.13
 *     yuborilardi (butun so'mda taqqoslash — kiritilgan narx E'TIBORSIZ);
 *   • orders "Kelishilgan summa" oynasi standarti Math.round (OK → +0.25);
 *   • orders "To'liq qarz" → 1 228 753 (0.25 ortiqcha); debts pay-amount — shunday;
 *   • finished savatcha "1 birlik narxi" 1 234.56 → 1 235 (sotuv 1 235 × 5);
 *   • finance xarajat 12 345.67 tahriri → 12 346 bo'lib saqlanardi; Ehson summasi `fmtFull`.
 * Endi to'ldirish — `narxKorinishi` (2 xonagacha, aynan), to'lov paneli aniq qarzni `data-qarz` dan oladi.
 * 117 (brauzer): forma "Jami" si server qoidasi bilan (`buyurtmaJami` — narx 2 xonaga HALF_UP, jami SHU
 * narxdan), `collectItems` Profil / Panel uchun XOM birlik narxini (`dataset.birlik`) yuboradi.
 *
 * BO'LIMLAR
 * ---------
 *   S — statik: har to'ldirish joyi `narxKorinishi` bilan, eski `formatNum(...)` / `fmt(...)` yo'q.
 *   O — orders.html HAQIQIY funksiyalari: fillFullDebt, savePayment (ortiqcha to'lov so'rovi),
 *       editAgreedAmount, calculateItem (Donalik tiyinli narx, jami qoidasi), collectItems.
 *   F — finished.html openBatchSellModal; D — debts.html selectOrderDebt;
 *   X — finance.html editTx / fillEhsonAmount; K — kpi.html renderTierChipsHtml.
 *
 * Funksiyalar HTML dan JONLI o'qiladi; topilmagan funksiya / istisno — yiqilgan tekshiruv (asl — tuzatishdan
 * oldingi — shablonlarga qarshi QULAMAYDI).
 *
 * ISHLATISH
 * ---------
 *     node tools/test_tahrir_tiyin_ui.js
 *     node tools/test_tahrir_tiyin_ui.js boshqa/templates     (mutatsiya uchun)
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
const SRC = { orders: oqi('orders'), finished: oqi('finished'), debts: oqi('debts'), finance: oqi('finance'),
              kpi: oqi('kpi') };

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
  for (const n of nomlar) {
    const f = olib(src, n);
    if (!f) { yoq.push(n); continue; }
    try { vm.runInContext(f, ctx, { filename: `${sahifa}:${n}` }); } catch (e) { yoq.push(n + '!' + e.message); }
  }
  return yoq;
}
const YORDAMCHI = ['parseNum', 'narxMatni', 'narxniOqi', 'narxKorinishi', 'formatPriceInput'];

// ── Soxta DOM ──
function el(qiymat, qo) {
  return Object.assign({ value: qiymat === undefined ? '' : String(qiymat), textContent: '', innerHTML: '',
                         style: {}, dataset: {}, checked: false, disabled: false, title: '',
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

// ════════════════════════════════════════════════════════════════════════════
bolim('S. Statik — to\'ldirish joylari narxKorinishi bilan');
const O = SRC.orders;
const S_BOR = [
  ['orders asosiy narx', O, "basePriceEl.value = narxKorinishi(order.base_price)", 'formatNum(order.base_price)'],
  ['orders Donalik saqlangan narx', O, 'upEl.value = narxKorinishi(rawPrice)', 'formatNum(rawPrice)'],
  ['orders Blok narxi (notes)', O, 'bpEl.value = narxKorinishi(blokPrice)', 'formatNum(Math.round(blokPrice))'],
  ['orders Loy sotish narxi', O, "upEl2.value = narxKorinishi(parseFloat(item.unit_price || 0))",
   "upEl2.value = formatNum("],
  ['orders MRP narxi', O, "upEl3.value = narxKorinishi(parseFloat(item.unit_price || 0))", "upEl3.value = formatNum("],
  ['orders TM Donalik narxi (tahrir)', O, 'upTm.value = narxKorinishi(fpNarxTm)', 'formatNum(fpNarxTm)'],
  ['orders TM Donalik narxi (tanlash)', O, 'up.value = narxKorinishi(fpNarx)', 'up.value = formatNum(fpNarx)'],
  ['orders "1 m³ narxi"', O, 'm3El.value = narxKorinishi(item.price_per_m3)', 'formatNum(item.price_per_m3)'],
  ['orders kelishilgan summa', O, 'fpEl.value = narxKorinishi(_aslKel)', 'formatNum(_aslKel)'],
  ['orders Donalik formula narxi', O, 'if (upEl) upEl.value = narxKorinishi(unitPrice);',
   'if (upEl) upEl.value = formatNum(unitPrice);'],
  ['finished savatcha narxi', SRC.finished, 'class="batch-price" value="${narxKorinishi(it.price)}"',
   'class="batch-price" value="${fmt(it.price)}"'],
  ['debts pay-amount', SRC.debts, "getElementById('pay-amount').value = narxKorinishi(debt)",
   "getElementById('pay-amount').value = fmt(debt)"],
  ['finance cashtx-amount', SRC.finance, "getElementById('cashtx-amount').value = narxKorinishi(amount)",
   "getElementById('cashtx-amount').value = fmtFull(amount)"],
  ['finance tx-f-amount', SRC.finance, "getElementById('tx-f-amount').value = narxKorinishi(amount)",
   "getElementById('tx-f-amount').value = fmtFull(amount)"],
  ['kpi tierEditAmount', SRC.kpi, 'id="tierEditAmount" value="${narxKorinishi(t.threshold_amount)}"',
   'id="tierEditAmount" value="${fmt(t.threshold_amount)}"'],
];
for (const [nom, src, bor, yoq] of S_BOR) {
  tekshir(`S ${nom}: narxKorinishi bilan, eski yaxlitlash yo'q`, src.includes(bor) && !src.includes(yoq),
          `bor=${src.includes(bor)} eski=${src.includes(yoq)}`);
}
tekshir('S orders "Kelishilgan summa" oynasi: standart narxKorinishi(cur), o\'qish narxniOqi, type:number yo\'q',
        O.includes('narxKorinishi(cur),') && O.includes('const val = narxniOqi(v);') &&
        !O.includes('String(Math.round(cur))') && !O.includes("title:'Kelishilgan summa', type:'number'"), '');
tekshir('S orders loadPayments aniq qarzni #pay-debt data-qarz ga yozadi',
        (olib(O, 'loadPayments') || '').includes("document.getElementById('pay-debt').dataset.qarz = String(debt);"), '');
tekshir('S orders collectItems Profil / Panel XOM birlik narxini (dataset.birlik) yuboradi',
        O.includes('parseFloat(row.dataset.birlik)') && O.includes('row.dataset.birlik = _birlik117;'), '');

// ════════════════════════════════════════════════════════════════════════════
bolim('O. orders.html — HAQIQIY funksiyalar');
function oMuhit(elementlar, qo) {
  const xabar = [];
  const ctx = Object.assign({
    console, Math, Number, String, JSON, isFinite, parseFloat, parseInt, BigInt, Object, Array,
    document: hujjat(elementlar), xabar,
    showMsg: (t, tur) => xabar.push({ t: String(t), tur }),
    formatNum: (n) => (!n || isNaN(n)) ? '0' : Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' '),
  }, qo || {});
  vm.createContext(ctx);
  const yoq = yukla(ctx, O, YORDAMCHI.concat(['_joriyQarz', 'fillFullDebt']), 'orders');
  return { ctx, yoq, xabar };
}
// O1 fillFullDebt — aniq qarz
try {
  const e = { 'pay-debt': el(''), 'pf-amount': el('') };
  e['pay-debt'].textContent = "1 228 753 so'm";
  e['pay-debt'].dataset.qarz = '1228752.75';
  const m = oMuhit(e);
  m.ctx.fillFullDebt();
  tekshir('O1 "To\'liq qarz": pf-amount "1 228 752.75" (asl: "1 228 753")', e['pf-amount'].value === '1 228 752.75',
          jsn({ v: e['pf-amount'].value, yoq: m.yoq }));
  tekshir('O1 pf-amount qiymati parseNum bilan AYNAN 1 228 752.75',
          typeof m.ctx.parseNum === 'function' && m.ctx.parseNum(e['pf-amount'].value) === 1228752.75, e['pf-amount'].value);
  const e2 = { 'pay-debt': el(''), 'pf-amount': el('') };
  e2['pay-debt'].textContent = "1 228 753 so'm";
  e2['pay-debt'].dataset = {};
  const m2 = oMuhit(e2);
  m2.ctx.fillFullDebt();
  tekshir('O1 data-qarz yo\'q (eski panel) → ko\'rinishdan: "1 228 753"', e2['pf-amount'].value === '1 228 753',
          e2['pf-amount'].value);
  const e3 = { 'pay-debt': el(''), 'pf-amount': el('x') };
  e3['pay-debt'].textContent = "0 so'm";
  e3['pay-debt'].dataset.qarz = '0';
  const m3 = oMuhit(e3);
  m3.ctx.fillFullDebt();
  tekshir('O1 qarz 0 → "Qarz yo\'q", maydon tegilmaydi', e3['pf-amount'].value === 'x' &&
          m3.xabar.some(x => x.t.includes("Qarz yo'q")), jsn(m3.xabar));
} catch (e) { tekshir('O1 fillFullDebt ishga tushdi', false, e.message); }

// O2 savePayment — aniq qarzga teng to'lov ortiqcha deb so'ralmaydi; 0.25 ko'pi so'raladi
async function tolovSina(summa, qarz) {
  const e = { 'pf-amount': el(summa), 'pf-writeoff': el(''), 'pay-debt': el(''), 'pf-type': el('partial'),
              'pf-method': el('naqd'), 'pf-notes': el('') };
  e['pay-debt'].textContent = "1 228 753 so'm";
  e['pay-debt'].dataset.qarz = String(qarz);
  const sorov = [];
  let tasdiqSoni = 0;
  const m = oMuhit(e, {
    selectedOrderId: 55,
    fetch: async (url, o) => { sorov.push({ url, tana: o && o.body ? JSON.parse(o.body) : null });
                               return javob(200, { debt_amount: 0, is_archived: false }); },
    showConfirmModal: async () => { tasdiqSoni++; return true; },
    customConfirm: async () => { tasdiqSoni++; return true; },
    loadPayments: async () => {}, loadOrders: async () => {}, closePaymentForm: () => {}, loadDetail: async () => {},
    setTimeout: () => 0, location: { reload() {} },
  });
  const yoq = yukla(m.ctx, O, ['tolovXatoSababi', 'savePayment'], 'orders');
  await m.ctx.savePayment();
  return { sorov, tasdiqSoni, yoq: m.yoq.concat(yoq) };
}
(async () => {
  try {
    let r = await tolovSina('1 228 752.75', 1228752.75);
    tekshir('O2 qarzga AYNAN teng to\'lov (1 228 752.75) → tasdiq so\'ralmaydi, summa AYNAN yuboriladi',
            r.tasdiqSoni === 0 && r.sorov.length === 1 && r.sorov[0].tana && r.sorov[0].tana.amount === 1228752.75,
            jsn(r));
    r = await tolovSina('1 228 753', 1228752.75);
    tekshir('O2 qarzdan 0.25 ko\'p (1 228 753) → ortiqcha to\'lov tasdig\'i so\'raladi (asl: so\'ralmasdi)',
            r.tasdiqSoni === 1, jsn(r));
  } catch (e) { tekshir('O2 savePayment ishga tushdi', false, e.message); }

  // O3 editAgreedAmount — standart aniq, OK → aniq summa
  async function kelSina(javobMatn) {
    const sorov = [];
    let standart = null, opts = null;
    const m = oMuhit({}, {
      selectedOrderId: 77,
      fetch: async (url, o) => {
        sorov.push({ url, method: (o && o.method) || 'GET', tana: o && o.body ? JSON.parse(o.body) : null });
        if (!o || !o.method) return javob(200, { total_amount: 6228752.75, agreed_amount: 6228752.75, discount_percent: 0 });
        return javob(200, { discount_percent: 0, debt_amount: 0 });
      },
      showPromptModal: async (msg, def, op) => { standart = def; opts = op || {}; return javobMatn === null ? def : javobMatn; },
      loadPayments: () => {},
    });
    const yoq = yukla(m.ctx, O, ['editAgreedAmount'], 'orders');
    await m.ctx.editAgreedAmount();
    return { sorov, standart, opts, xabar: m.xabar, yoq: m.yoq.concat(yoq) };
  }
  try {
    let r = await kelSina(null);
    const put = r.sorov.find(s => s.method === 'PUT');
    tekshir('O3 "Kelishilgan summa" oynasi standarti "6 228 752.75" (asl: "6228753")', r.standart === '6 228 752.75',
            jsn(r.standart));
    tekshir('O3 o\'zgartirmay OK → PUT agreed_amount AYNAN 6 228 752.75 (asl: 6 228 753)',
            !!put && put.tana && put.tana.agreed_amount === 6228752.75, jsn(r.sorov));
    tekshir('O3 oyna maydoni matn (type:number emas — bo\'shliqli summani qabul qiladi)',
            r.opts && r.opts.type !== 'number', jsn(r.opts));
    r = await kelSina('1.000.000');
    const put2 = r.sorov.find(s => s.method === 'PUT');
    tekshir('O3 "1.000.000" → 1 000 000 (prompt standarti narxniOqi)', !!put2 && put2.tana.agreed_amount === 1000000,
            jsn(r.sorov));
    r = await kelSina('12.500');
    const put3 = r.sorov.find(s => s.method === 'PUT');
    tekshir('O3 "12.500" → 12 500 (ming ajratgich — narxniOqi; parseNum 12.5 berardi)',
            !!put3 && put3.tana.agreed_amount === 12500, jsn(r.sorov));
    r = await kelSina('abc');
    tekshir('O3 "abc" → so\'rov yo\'q, xato xabari', !r.sorov.some(s => s.method === 'PUT') &&
            r.xabar.some(x => x.tur === 'error'), jsn(r));
  } catch (e) { tekshir('O3 editAgreedAmount ishga tushdi', false, e.message); }

  // O4 / O5 calculateItem + collectItems
  function qator(maydonlar, dataset) {
    const elm = {};
    for (const [k, v] of Object.entries(maydonlar)) elm['.' + k] = el(v);
    for (const k of ['i-vol', 'i-price', 'i-perm', 'i-vol-relock', 'i-name', 'i-peno', 'i-m3price', 'i-donayield',
                     'i-blokprice', 'i-loysale-recipe', 'i-unitprice', 'i-c', 'i-h', 'i-w', 'i-t', 'i-l', 'i-q'])
      if (!elm['.' + k]) elm['.' + k] = el('');
    return { dataset: dataset || {}, id: 'r1', querySelector: (s) => elm[s] || null, querySelectorAll: () => [],
             closest: () => null, _el: elm };
  }
  function cMuhit(qatorlar) {
    const ctx = {
      console, Math, Number, String, JSON, isFinite, parseFloat, parseInt, BigInt, Object, Array,
      PENOPLASTS: [{ id: 1, volPerUnit: 0.9, isDefault: true }],
      document: { getElementById: (id) => el(id === 'base_price' ? '1000000' : ''),
                  querySelectorAll: (s) => (s === '.detal' ? qatorlar : []) },
      updatePenoWarn() {}, checkDeliveredLimit() {}, checkFpLimit() {}, updateTotal() {}, updateLiveStats() {},
      updateDetalSummary() {}, sanitizeToLatin: (x) => x,
    };
    vm.createContext(ctx);
    const yoq = yukla(ctx, O, YORDAMCHI.concat(['formatNum', '_onlikQism', '_tiyinHalfUp', 'buyurtmaJami',
                                                 'calcSubDetailRow', 'calculateItem', 'collectItems']), 'orders');
    return { ctx, yoq };
  }
  try {
    // O4 Donalik tiyinli narx
    let r = qator({ 'i-type': 'dona', 'i-q': '34', 'i-c': 'false', 'i-unitprice': '3 997.40', 'i-name': 'D' },
                  { unitprice: '3997.13' });
    let m = cMuhit([r]);
    m.ctx.calculateItem(r);
    tekshir('O4 Donalik: saqlangan 3 997.13, maydonga "3 997.40" yozildi → 3 997.40 ishlatiladi (asl: 3 997.13)',
            parseFloat(r.dataset.unitprice) === 3997.4 && parseFloat(r.dataset.price) === 135911.6,
            jsn({ u: r.dataset.unitprice, p: r.dataset.price, yoq: m.yoq }));
    r = qator({ 'i-type': 'dona', 'i-q': '34', 'i-c': 'false', 'i-unitprice': '3 997.13', 'i-name': 'D' },
              { unitprice: '3997.125' });
    m = cMuhit([r]);
    m.ctx.calculateItem(r);
    tekshir('O4 Donalik: maydon aniq narxning 2 xonali ko\'rinishi → aniq narx saqlanadi; jami server qoidasi (135 902.42)',
            parseFloat(r.dataset.unitprice) === 3997.125 && parseFloat(r.dataset.price) === 135902.42,
            jsn({ u: r.dataset.unitprice, p: r.dataset.price }));
    r = qator({ 'i-type': 'dona', 'i-q': '10', 'i-c': 'false', 'i-h': '13', 'i-t': '7', 'i-donayield': '3',
                'i-unitprice': '', 'i-name': 'D' });
    m = cMuhit([r]);
    m.ctx.calculateItem(r);
    const bir = (13 / 100) * (7 / 100) / 2 / 3 * 1000000;
    tekshir(`O4 Donalik o'lchamdan: maydon ${m.ctx.narxKorinishi ? m.ctx.narxKorinishi(bir) : '?'} (2 xona, asl: butun)`,
            !!m.ctx.narxKorinishi && r._el['.i-unitprice'].value === m.ctx.narxKorinishi(bir), r._el['.i-unitprice'].value);
    // O5 jami qoidasi + collectItems
    const panel = qator({ 'i-type': 'panel', 'i-h': '50', 'i-t': '2', 'i-q': '3', 'i-c': 'false', 'i-name': 'Panel',
                          'i-m3price': '1 000 000.25', 'i-peno': '1' });
    const blok = qator({ 'i-type': 'blok', 'i-l': '1.75', 'i-q': '7', 'i-c': 'false', 'i-name': 'Blok',
                         'i-blokprice': '1 000 000', 'i-peno': '1' });
    const loy = qator({ 'i-type': 'loy_sotish', 'i-q': '7', 'i-c': 'false', 'i-name': 'Loy', 'i-unitprice': '1 234.565' });
    m = cMuhit([panel, blok, loy]);
    for (const q of [panel, blok, loy]) m.ctx.calculateItem(q);
    tekshir('O5 panel 0.5 × 0.02 × 1 000 000.25 × 3 m: forma jami 30 000.00 (server qoidasi; xom 30 000.0075)',
            parseFloat(panel.dataset.price) === 30000 && parseFloat(panel.dataset.birlik) === 10000.0025,
            jsn({ p: panel.dataset.price, b: panel.dataset.birlik }));
    tekshir('O5 blok 1 000 000 / 1.75 m × 7 m: forma jami 3 999 999.99 (1 metr narxi 571 428.57 dan)',
            parseFloat(blok.dataset.price) === 3999999.99, blok.dataset.price);
    tekshir('O5 loy 1 234.565 × 7 kg: forma jami 8 641.99 (narx 1 234.57 dan)', parseFloat(loy.dataset.price) === 8641.99,
            loy.dataset.price);
    // Yuboriladigan birlik narxi AYNAN collectItems dagisi (xom jami / miqdor EMAS): float da (6.065 × 13) / 13 =
    // 6.0649999999999995 — HALF_UP 6.06 bo'lardi (to'g'risi 6.07 → 13 × 6.07 = 78.91).
    const loy2 = qator({ 'i-type': 'loy_sotish', 'i-q': '13', 'i-c': 'false', 'i-name': 'Loy2', 'i-unitprice': '6.065' });
    const dona2 = qator({ 'i-type': 'dona', 'i-q': '13', 'i-c': 'false', 'i-unitprice': '6.07', 'i-name': 'Dona2' },
                        { unitprice: '6.065' });
    m.ctx.calculateItem(loy2);
    m.ctx.calculateItem(dona2);
    tekshir('O5 loy 6.065 × 13: jami 78.91 (birlik narxi 6.07 dan; xom jami / miqdor 6.06 berardi)',
            parseFloat(loy2.dataset.price) === 78.91, loy2.dataset.price);
    tekshir('O5 Donalik aniq narx 6.065 × 13: jami 78.91 (dataset.unitprice dan)', parseFloat(dona2.dataset.price) === 78.91,
            dona2.dataset.price);
    const items = m.ctx.collectItems();
    const ip = items.find(i => i.name === 'Panel'), ib = items.find(i => i.name === 'Blok');
    tekshir('O5 collectItems: panel XOM birlik narxi 10 000.0025 × 3 (server o\'zi yaxlitlaydi)',
            ip && ip.unit_price === 10000.0025 && ip.quantity === 3, jsn(ip));
    tekshir('O5 collectItems: blok 1 metr narxi (1e6 / 1.75) × 7', ib && ib.unit_price === 1000000 / 1.75 && ib.quantity === 7,
            jsn(ib));
  } catch (e) { tekshir('O4 / O5 calculateItem / collectItems ishga tushdi', false, e.message); }

  // ══════════════════════════════════════════════════════════════════════════
  bolim('F / D / X / K — boshqa sahifalar');
  try {
    const e = { 'batch-modal-sub': el(''), 'batch-buyer': el(''), 'batch-master': el(''), 'batch-paymethod': el(''),
                'batch-agreed': el(''), 'batch-discount-info': el(''), 'batch-items-list': el(''), batchSellModal: el('') };
    const ctx = { console, Math, Number, String, JSON, isFinite, parseFloat, parseInt, Object, Array,
                  document: hujjat(e), updateBatchTotal() {},
                  escapeHtml: (x) => String(x), fmt: (n) => Math.round(n || 0).toLocaleString('ru-RU').replace(/,/g, ' ') };
    vm.createContext(ctx);
    const yoq = yukla(ctx, SRC.finished, YORDAMCHI.concat(['openBatchSellModal']), 'finished');
    vm.runInContext("var _batchItems = {5: {name: 'TM', maxQty: 5, unit: 'dona', price: 1234.56}};", ctx);
    ctx.openBatchSellModal();
    tekshir('F savatcha "1 birlik narxi" maydoni "1 234.56" (asl: "1 235")',
            e['batch-items-list'].innerHTML.includes('class="batch-price" value="1 234.56"'), jsn({ yoq }));
  } catch (x) { tekshir('F openBatchSellModal ishga tushdi', false, x.message); }
  try {
    const e = { 'cd-name': el(''), 'cd-avatar': el(''), 'cd-body': el(''), payCard: el(''), 'pay-amount': el(''),
                'pay-note': el(''), 'pay-writeoff': el(''), 'pay-msg': el('') };
    const ctx = { console, Math, Number, String, JSON, isFinite, parseFloat, parseInt, Object, Array,
                  document: Object.assign(hujjat(e), { querySelectorAll: () => [] }),
                  escapeHtml: (x) => String(x), fmt: (n) => Math.round(n || 0).toLocaleString('ru-RU').replace(/,/g, ' ') };
    vm.createContext(ctx);
    const yoq = yukla(ctx, SRC.debts, YORDAMCHI.concat(['selectOrderDebt']), 'debts');
    vm.runInContext('var selectedOrderId = null;', ctx);
    const elOrder = { classList: { add() {}, remove() {} },
                      dataset: { id: '9', agreed: '6228752.75', paid: '5000000', debt: '1228752.75', client: 'M',
                                 orderNumber: 'ORD-1', project: 'L', phone: '', deadline: '' } };
    ctx.selectOrderDebt(elOrder);
    tekshir('D debts to\'lov summasi "1 228 752.75" (asl: "1 228 753")', e['pay-amount'].value === '1 228 752.75',
            jsn({ v: e['pay-amount'].value, yoq }));
  } catch (x) { tekshir('D selectOrderDebt ishga tushdi', false, x.message); }
  try {
    const e = { 'tx-f-editing-id': el(''), 'tx-modal-title': el(''), 'tx-f-date': el(''), 'tx-f-category': el(''),
                'tx-f-amount': el(''), 'tx-f-notes': el(''), 'tx-f-prodtype': el(''), txModal: el(''),
                'cashtx-amount': el('') };
    const ctx = { console, Math, Number, String, JSON, isFinite, parseFloat, parseInt, Object, Array,
                  document: hujjat(e), setTimeout: () => 0,
                  fetch: async () => javob(200, { ehson_xarajat: 1234.56 }),
                  fmtFull: (n) => Number(Math.round(n || 0)).toLocaleString('ru-RU') };
    vm.createContext(ctx);
    const yoq = yukla(ctx, SRC.finance, YORDAMCHI.concat(['editTx', 'fillEhsonAmount']), 'finance');
    ctx.editTx(3, '2026-09-20T00:00:00', 'boshqa', 12345.67, 'izoh', '');
    tekshir('X xarajat tahriri: summa "12 345.67" (asl: "12 346")', e['tx-f-amount'].value === '12 345.67',
            jsn({ v: e['tx-f-amount'].value, yoq }));
    ctx.event = { target: el('') };
    await ctx.fillEhsonAmount();
    tekshir('X Ehson summasi "1 234.56" (asl: "1 235")', e['cashtx-amount'].value === '1 234.56', e['cashtx-amount'].value);
  } catch (x) { tekshir('X editTx / fillEhsonAmount ishga tushdi', false, x.message); }
  try {
    const ctx = { console, Math, Number, String, JSON, isFinite, parseFloat, parseInt, Object, Array,
                  escapeHtml: (x) => String(x), fmt: (n) => Math.round(n || 0).toLocaleString('ru-RU').replace(/,/g, ' ') };
    vm.createContext(ctx);
    const yoq = yukla(ctx, SRC.kpi, YORDAMCHI.concat(['renderTierChipsHtml']), 'kpi');
    vm.runInContext("var _currentPeriodTiers = [{id: 7, gift_name: 'Sovg\\'a', threshold_amount: 1500000.5}]; var _editingTierId = 7;", ctx);
    const html = ctx.renderTierChipsHtml();
    tekshir('K sovg\'a pog\'onasi tahriri: chegara "1 500 000.5" (asl: "1 500 001")',
            String(html).includes('id="tierEditAmount" value="1 500 000.5"'), jsn({ yoq }));
  } catch (x) { tekshir('K renderTierChipsHtml ishga tushdi', false, x.message); }

  console.log('\n' + '='.repeat(66));
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  console.log('='.repeat(66));
  if (FAILED.length) { console.log('YIQILGANLAR:'); for (const f of FAILED) console.log('  - ' + f); console.log('='.repeat(66)); }
  process.exit(FAIL ? 1 : 0);
})();
