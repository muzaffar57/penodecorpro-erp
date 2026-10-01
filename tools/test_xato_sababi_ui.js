#!/usr/bin/env node
/**
 * test_xato_sababi_ui.js — kech107 darvozasi (5-bo'lim 10-band, "UI 400 sabablari kpi / inventory / finished").
 *
 *   templates/base.html      — `xatoSababi(javob, standart)`, `serverXatoSababi(res, standart)` (YANGI, yagona qoida)
 *   templates/kpi.html       — usta KPI %, nofaol / faol qilish, avans berish / o'chirish, hodimni o'chirish,
 *                              oylik kamaytirish / bonus, sovg'a davrini yopish
 *   templates/inventory.html — rasm, asosiy plotnost, hisobotlar (Telegram), narx, minimal chegara, turkum, xarid va
 *                              material o'chirish
 *   templates/finished.html  — rasm, qo'shish, kamaytirish / ishlab chiqarish braki, sotish, guruh sotish, narx, o'chirish,
 *                              band qilishni bekor qilish, «Sotuvga tayyor»
 *
 * NIMA UCHUN (asl kod staging `061e082` da O'LCHANGAN — xarita `natija/k107/fetch_xarita_asl.txt`, dinamik — shu test
 * ASL fayllarga qarshi): server rad etganda (400 / 404 / 409 / 422) sababni `detail` da beradi — matn, obyekt
 * (`{message}`) yoki pydantic ro'yxati. Sahifalar ko'p joyda sababni tashlab "Xato yuz berdi" chiqarardi, `r.detail?.message`
 * MATN sababni yo'qotardi, obyekt "[object Object]" bo'lib chiqardi, ba'zi joylarda (avans / hodim o'chirish, TM narxi)
 * rad umuman ko'rsatilmasdi. QOIDA: rad javobidagi sabab faqat base.html yordamchilari bilan o'qiladi.
 *
 * Funksiyalar HTML dan JONLI o'qiladi, soxta muhitda ishga tushiriladi (fetch — rad javobi). Topilmagan funksiya yoki
 * istisno — yiqilgan tekshiruv (asl fayllarga qarshi ham QULAMAYDI).
 *
 *     node tools/test_xato_sababi_ui.js [templates_papkasi]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const TPL = process.argv[2] || path.join(ROOT, 'templates');
function oqi(nom) {
  try { return fs.readFileSync(path.join(TPL, nom), 'utf8'); } catch (e) { return ''; }
}
// Jinja teglari (`{% if … %}` / `{{ … }}`) JS emas — funksiyalar soxta muhitda yurishi uchun olib tashlanadi (ikkala shox
// qoladi — rad shoxiga ta'siri yo'q); statik tekshiruvlar XOM matnda.
function jinjasiz(s) { return s.replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, 'null'); }
const BASE = oqi('base.html'), KPI = oqi('kpi.html'), INV = oqi('inventory.html'), FIN = oqi('finished.html');
const KPI_J = jinjasiz(KPI), INV_J = jinjasiz(INV), FIN_J = jinjasiz(FIN);

let OK = 0, FAIL = 0;
const FAILED = [];
function tekshir(label, shart, izoh) {
  let s = false;
  try { s = !!shart; } catch (e) { s = false; }
  if (s) { OK++; console.log(`  ✓ ${label}`); }
  else {
    FAIL++; FAILED.push(label);
    console.log(`  ✗ ${label}${izoh !== undefined ? '   — ' + qisqa(izoh) : ''}`);
  }
}
function bolim(t) { console.log(`\n--- ${t} ---`); }
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
  const i = m.index;
  let d = 0;
  const j = src.indexOf('{', i + m[0].length);
  if (j < 0) return null;
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(i, k + 1); }
  }
  return null;
}
function el(extra) {
  return Object.assign({ value: '', textContent: '', innerHTML: '', style: {}, dataset: {}, disabled: false,
                         appendChild: () => {}, querySelector: () => null, querySelectorAll: () => [],
                         closest: () => null, classList: { add() {}, remove() {}, toggle() {} } }, extra || {});
}
function javob(status, data) {
  return { ok: status >= 200 && status < 300, status,
           json: async () => (data === undefined ? (() => { throw new Error('JSON emas'); })() : JSON.parse(JSON.stringify(data))),
           clone() { return this; } };
}

// kech118 (B — U-05, MOSLANDI): sahifa funksiyalari base.html `sonKor` / `matnRangi` … ni ham chaqiradi
const BASE_FN = ['escapeHtml', 'xatoSababi', 'serverXatoSababi', 'sonKor', 'foizKor', 'birlikKor', 'matnRangi'];
function kod(src, nomlar) {
  const qism = [];
  const yoq = [];
  for (const n of nomlar) { const f = olib(src, n); if (f) qism.push(f); else yoq.push(n); }
  return { kod: qism.join('\n'), yoq };
}

// Bitta funksiyani soxta muhitda — `fetch` rad javobi bilan — ishga tushiradi; ekranga chiqqan HAMMA matnni qaytaradi.
async function sinov(o) {
  const elementlar = o.elementlar || {};
  const xabarlar = [];
  const sorovlar = [];
  const ctx = {
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, isFinite, Array, Object, Error, Set, Map,
    encodeURIComponent, Date, RegExp,
    document: {
      getElementById: (id) => {
        if (!Object.prototype.hasOwnProperty.call(elementlar, id)) elementlar[id] = el();
        return elementlar[id];
      },
      createElement: () => el(), querySelectorAll: (s) => (o.qsa && o.qsa[s]) || [], querySelector: () => null,
      addEventListener: () => {}, removeEventListener: () => {},
    },
    window: {}, location: { reload() {}, href: '' }, setTimeout: (f) => 0, clearTimeout() {},
    FormData: class { append() {} },
    fetch: async (url, opts) => {
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET' });
      return o.javobFn(String(url), opts);
    },
    alert: (t) => xabarlar.push(String(t)),
    invToast: (t) => xabarlar.push(String(t)),
    showMsg: (t) => xabarlar.push(String(t)),
    customConfirm: async () => true,
    customPrompt: async () => (o.prompt !== undefined ? o.prompt : '1500'),
    prompt: () => (o.prompt !== undefined ? o.prompt : '1500'),
    // kech118 (B — U-07, MOSLANDI): sahifa xom prompt() / alert() o'rniga dastur oynalarini chaqiradi (base.html
    // `kiritishOyna` — Promise, standart qiymat `o.qiymat`; `xabarOyna`) — soxta muhitda shu testning prompt / alert soxtalariga ulanadi.
    kiritishOyna: async () => (o.prompt !== undefined ? o.prompt : '1500'),
    xabarOyna: async (t) => { xabarlar.push(String(t)); },
    promptAmountReason: async () => ({ amount: 1000, reason: 'KB' }),
    confirmDeleteFp: async () => 'keep',
  };
  for (const n of ['loadMasterKpi', 'loadAllMastersFull', 'renderInactiveMasters', 'loadAdvanceHistory', 'loadEmployees',
                   'loadEmpMonthlyReport', 'loadGiftPeriod', 'openPurchaseHistory', 'loadFp', 'closeLossModal',
                   'closeSellModal', 'closeBatchSellModal', 'clearBatchSelection', 'openPdfSafe', 'closeProduceModal']) {
    ctx[n] = () => {};
  }
  ctx.lossBosqichTana = () => ({});
  ctx.batchOriginalTotal = () => 1000;
  ctx.tiyinga = (n) => Math.round(n * 100) / 100;
  ctx.window.open = () => {};
  Object.assign(ctx, o.globallar || {});
  vm.createContext(ctx);
  const b = kod(BASE, BASE_FN);
  const p = kod(o.src, o.yordamchi || []);
  const f = kod(o.src, [o.fn]);
  if (f.yoq.length) return { xato: `funksiya topilmadi: ${o.fn}`, xabarlar, sorovlar, elementlar };
  try {
    vm.runInContext(b.kod + '\n' + p.kod + '\n' + (o.oldin || '') + '\n' + f.kod, ctx);
    await vm.runInContext(o.chaqiruv, ctx);
    return { xato: null, xabarlar, sorovlar, elementlar };
  } catch (e) {
    return { xato: String((e && e.message) || e), xabarlar, sorovlar, elementlar };
  }
}

const SABAB = 'SERVER-SABABI-107';
function rad(detail, status) {
  return async (url, opts) => ((opts && opts.method && opts.method !== 'GET') ? javob(status || 400, {detail})
                                                                            : javob(200, {}));
}
function korindimi(n, matn) {
  const hamma = n.xabarlar.join(' | ') + ' | ' +
    Object.values(n.elementlar || {}).map(e => `${e.textContent || ''} ${e.innerHTML || ''}`).join(' | ');
  return hamma.includes(matn);
}

(async () => {
  // ════════════════════════════════════════════════════════════
  bolim('H — base.html yordamchilari');
  const h = kod(BASE, BASE_FN);
  tekshir('H0 base.html da `xatoSababi` va `serverXatoSababi` bor', !h.yoq.length, h.yoq);
  const hc = { console, JSON, String, Array, Object, Promise };
  vm.createContext(hc);
  let H = {};
  try {
    vm.runInContext(h.kod, hc);
    H = {
      mat: vm.runInContext(`xatoSababi({detail: 'Omborda yetarli emas'})`, hc),
      obj: vm.runInContext(`xatoSababi({detail: {type: 'below_cost_warning', message: 'Tannarxdan past'}})`, hc),
      err: vm.runInContext(`xatoSababi({detail: {success: false, error: 'Ishlatilgan material'}})`, hc),
      ros: vm.runInContext(`xatoSababi({detail: [{loc: ['body', 'amount'], msg: 'Field required'}, {loc: ['query', 'x'], msg: 'bad'}]})`, hc),
      bosh: vm.runInContext(`xatoSababi({detail: '  '}, 'Standart')`, hc),
      yoq: vm.runInContext(`xatoSababi(null)`, hc),
      nom: vm.runInContext(`xatoSababi({detail: {pending_master_names: ['A']}}, 'Xato')`, hc),
    };
  } catch (e) { H.xato = String(e); }
  tekshir("H1 matn sabab — o'zi", H.mat === 'Omborda yetarli emas', H);
  tekshir('H2 obyekt `{message}` — message', H.obj === 'Tannarxdan past', H);
  tekshir('H3 obyekt `{error}` — error', H.err === 'Ishlatilgan material', H);
  tekshir("H4 pydantic ro'yxati — \"maydon: xabar; …\" (body / query olib tashlanadi)", H.ros === 'amount: Field required; x: bad', H);
  tekshir("H5 bo'sh / yo'q / sababsiz obyekt — standart matn", H.bosh === 'Standart' && H.yoq === 'Xato yuz berdi' && H.nom === 'Xato', H);
  let HS = {};
  try {
    HS.json = await vm.runInContext(`serverXatoSababi({json: async () => ({detail: 'A sabab'})})`, hc);
    HS.jsonemas = await vm.runInContext(`serverXatoSababi({json: async () => { throw new Error('x'); }}, 'Standart 2')`, hc);
  } catch (e) { HS.xato = String(e); }
  tekshir("H6 `serverXatoSababi`: javob tanasidan; JSON bo'lmasa — standart", HS.json === 'A sabab' && HS.jsonemas === 'Standart 2', HS);

  // ════════════════════════════════════════════════════════════
  // Har sahifa funksiyasi: MATN sabab (eng ko'p uchraydigan — `HTTPException(400, detail="…")`) ekranga chiqishi SHART.
  const KPI_YORD = ['parseNum', 'narxMatni', 'narxniOqi', 'narxKorinishi', 'fmt'];
  const INV_YORD = ['parseNum', 'narxMatni', 'narxniOqi', 'narxKorinishi', 'fmt'];
  const FIN_YORD = ['parseNum', 'narxMatni', 'narxniOqi', 'narxKorinishi', 'fmt'];
  const HOLATLAR = [
    ['K1 kpi saveMasterKpi (usta KPI %)', KPI, 'saveMasterKpi', 'saveMasterKpi(5)', {elementlar: {'mk-5': el({value: '150'})},
      oldin: 'var inFlightMasterKpi = new Set();'}],
    ['K2 kpi deactivateMaster (nofaol qilish)', KPI, 'deactivateMaster', "deactivateMaster(5, 'U')", {}],
    ['K3 kpi reactivateMaster (faollashtirish)', KPI, 'reactivateMaster', 'reactivateMaster(5, null)', {}],
    ['K4 kpi saveAdvance (avans berish)', KPI, 'saveAdvance', 'saveAdvance()', {elementlar: {'adv-amount': el({value: '100000'}),
      'adv-date': el({value: '2026-09-28'})}, oldin: 'var advanceEmpId = 3;'}],
    ["K5 kpi deleteAdvance (avansni o'chirish — asl: rad JIM)", KPI, 'deleteAdvance', 'deleteAdvance(7)', {oldin: 'var advanceEmpId = 3;'}],
    ["K6 kpi deleteEmployee (hodimni o'chirish — asl: rad JIM)", KPI, 'deleteEmployee', 'deleteEmployee(7)', {}],
    ['K7 kpi editEmpAdjustment (oylik kamaytirish)', KPI, 'editEmpAdjustment', "editEmpAdjustment(3, 'H', 2026, 9, 0, '')",
      {oldin: 'var inFlightEmpAdjustment = new Set();'}],
    ['K8 kpi editEmpBonus (bonus)', KPI, 'editEmpBonus', "editEmpBonus(3, 'H', 2026, 9, 0, '')",
      {oldin: 'var inFlightEmpAdjustment = new Set();'}],
    ["K9 kpi submitCloseGiftPeriod (majburiy yopish rad etildi — matn sabab)", KPI, 'submitCloseGiftPeriod', 'submitCloseGiftPeriod(true)',
      {oldin: 'var isClosingGiftPeriod = false;'}],
    ['I1 inventory uploadInventoryImage (rasm)', INV, 'uploadInventoryImage', 'uploadInventoryImage(3, {files: [{}]})',
      {oldin: 'var inFlightInvActions = new Set();'}],
    ['I2 inventory setDefaultPenoplast', INV, 'setDefaultPenoplast', 'setDefaultPenoplast(3)', {oldin: 'var inFlightInvActions = new Set();'}],
    ["I3 inventory sendFullStockReport (to'liq qoldiq hisoboti)", INV, 'sendFullStockReport', 'sendFullStockReport()',
      {oldin: 'var isSendingStockReport = false;'}],
    ['I4 inventory sendLowStockAlert (kam qoldiq)', INV, 'sendLowStockAlert', 'sendLowStockAlert()', {oldin: 'var isSendingLowStockAlert = false;'}],
    ['I5 inventory editPrice (narx)', INV, 'editPrice', 'editPrice(3, 1000)', {oldin: 'var inFlightInvActions = new Set();'}],
    ['I6 inventory editMinStock (minimal chegara)', INV, 'editMinStock', "editMinStock(3, 5, 'kg')", {prompt: '10',
      oldin: 'var inFlightInvActions = new Set();'}],
    ['I7 inventory editCategory (turkum — PUT)', INV, 'editCategory', "editCategory({dataset: {id: '3', category: 'Boshqa'}})",
      {prompt: 'Kimyoviy', oldin: 'var inFlightInvActions = new Set();'}],
    ["I8 inventory deletePurchase (xarid o'chirish)", INV, 'deletePurchase', "deletePurchase(3, 'X', 5)", {}],
    ["I9 inventory deleteItem (material o'chirish)", INV, 'deleteItem', 'deleteItem(3)', {}],
    ['F1 finished uploadFpImage (rasm)', FIN, 'uploadFpImage', 'uploadFpImage(3, {files: [{}]})', {}],
    ["F2 finished addProduction (qo'shish)", FIN, 'addProduction', "addProduction(3, 2, {name: 'TM', unit: 'dona', quantity: 5, unit_volume_m3: 0.01, unit_loy_kg: 0})", {}],
    // kech118 (D-1, G5-20): brak sababi majburiy — oynada sabab tanlangan (aks holda so'rov yuborilmaydi)
    ['F3 finished submitLoss (kamaytirish)', FIN, 'submitLoss', 'submitLoss()', {elementlar: {'loss-qty': el({value: '1'}), 'loss-cause': el({value: 'boshqa'})},
      oldin: "var _lossData = {id: 3, quantity: 10, unit: 'dona'}; var _lossMode = 'stock';"}],
    ['F4 finished submitLoss (ishlab chiqarish braki)', FIN, 'submitLoss', 'submitLoss()', {elementlar: {'loss-qty': el({value: '1'}), 'loss-cause': el({value: 'boshqa'})},
      oldin: "var _lossData = {id: 3, quantity: 10, unit: 'dona'}; var _lossMode = 'brak';"}],
    ['F5 finished submitSell (sotish)', FIN, 'submitSell', 'submitSell(false)', {elementlar: {'sell-qty': el({value: '1'}),
      'sell-price': el({value: '1000'}), 'sell-master': el({value: 'none'})},
      oldin: "var _sellData = {id: 3, quantity: 10, unit: 'dona', name: 'TM'};"}],
    // kech118 (D-1, G5-12): savatcha qatori miqdori qoldiq (`data-max`) bilan solishtiriladi, xabarda nomi (`_batchItems`)
    ['F6 finished submitBatchSell (guruh sotish)', FIN, 'submitBatchSell', 'submitBatchSell(false)', {elementlar: {'batch-master': el({value: 'none'})},
      qsa: {'.batch-item-row': [el({dataset: {id: '3'}, querySelector: (s) => el({value: s === '.batch-qty' ? '1' : '1000', dataset: {max: '5', unit: 'dona'}})})]},
      oldin: "var _batchItems = {3: {name: 'TM'}};"}],
    ['F7 finished editPrice (TM narxi — asl: rad JIM)', FIN, 'editPrice', 'editPrice(3)', {oldin: "var fpItems = [{id: 3, name: 'TM', unit: 'dona', unit_price: 1000}];"}],
    ["F8 finished delFp (o'chirish)", FIN, 'delFp', "delFp(3, 'x')", {oldin: "var fpItems = [{id: 3, name: 'TM', unit: 'dona'}];"}],
    ['F9 finished releaseFpReservation (band bekor)', FIN, 'releaseFpReservation', "releaseFpReservation(3, 'TM')", {}],
    ['F10 finished markReady («Sotuvga tayyor»)', FIN, 'markReady', 'markReady(3)', {oldin: "var fpItems = [{id: 3, name: 'TM', unit: 'dona', quantity: 2}];"}],
    ['F11 finished saveProduce (ishlab chiqarish — blok)', FIN, 'saveProduce', 'saveProduce()', {elementlar: {'p-name': el({value: 'TM blok'}),
      'p-type': el({value: 'blok'}), 'p-price': el({value: '1000'}), 'p-coated': el({value: 'false'}), 'p-peno': el({value: '3'}),
      'p-q': el({value: '2'})}, globallar: {window: {_pCalc: {count: 1, perUnitPrice: 1000}, _blokKerak: 1, open() {}}}}],
  ];
  bolim("K / I / F — MATN sabab ekranga chiqadi (asl: \"Xato yuz berdi\" / \"Xato\" / hech narsa)");
  for (const [nom, src, fn, chaqiruv, o] of HOLATLAR) {
    const n = await sinov(Object.assign({src: src === KPI ? KPI_J : (src === INV ? INV_J : FIN_J), fn, chaqiruv, javobFn: rad(SABAB),
                                         yordamchi: src === KPI ? KPI_YORD : (src === INV ? INV_YORD : FIN_YORD)}, o));
    tekshir(nom, !n.xato && n.sorovlar.some(x => x.method !== 'GET') && korindimi(n, SABAB),
            {xato: n.xato, xabar: n.xabarlar, sorov: n.sorovlar.map(x => x.method + ' ' + x.url)});
  }
  bolim("O — obyekt `{message}` va pydantic ro'yxati ham ([object Object] emas) — HAMMA joyda");
  // kech107 (mutatsiya kmut107u): ilgari faqat 5 funksiya — rasm / asosiy plotnost / o'chirish / ishlab chiqarish kabi joylarning
  // eski kodi MATN sababni ko'rsatardi-yu obyektda "[object Object]" berardi, ro'yxatda "Xato" — endi HAR joy tekshiriladi.
  for (const [nom, src, fn, chaqiruv, o] of HOLATLAR) {
    const sj = src === KPI ? KPI_J : (src === INV ? INV_J : FIN_J);
    const yj = src === KPI ? KPI_YORD : (src === INV ? INV_YORD : FIN_YORD);
    // Har yurgizish — O'Z elementlari bilan (bir holatning ikki yurgizishi bitta `p-error` ni bo'lishmasin).
    const yangiO = () => Object.assign({}, o, {elementlar: Object.fromEntries(Object.entries(o.elementlar || {})
      .map(([k, v]) => [k, el(Object.assign({}, v))]))});
    const n1 = await sinov(Object.assign({src: sj, fn, chaqiruv, javobFn: rad({message: 'OBYEKT-SABAB'}, 409), yordamchi: yj}, yangiO()));
    const n2 = await sinov(Object.assign({src: sj, fn, chaqiruv, javobFn: rad([{loc: ['body', 'quantity'], msg: 'Field required'}], 422),
                                          yordamchi: yj}, yangiO()));
    const hamma = n1.xabarlar.concat(n2.xabarlar).join(' | ');
    tekshir(nom.split(' ')[0] + ' ' + fn + ": obyekt → message, ro'yxat → \"quantity: Field required\", \"[object Object]\" yo'q",
            !n1.xato && !n2.xato && korindimi(n1, 'OBYEKT-SABAB') && korindimi(n2, 'quantity: Field required') && !hamma.includes('[object Object]'),
            {x1: n1.xato, x2: n2.xato, xabar: hamma});
  }

  bolim("G — sovg'a davrini yopish: kutilayotgan ustalar tasdiqlangach IKKINCHI so'rov rad etilsa (matn / ro'yxat)");
  // Birinchi POST — 409 (sovg'aga yetgan, "Berildi" belgilanmagan ustalar), ikkinchi (majburiy) POST — rad.
  const ketma = (...javoblar) => { let i = 0; return async (url, opts) => ((opts && opts.method && opts.method !== 'GET')
    ? javoblar[Math.min(i++, javoblar.length - 1)] : javob(200, {})); };
  const KUT = javob(409, {detail: {pending_master_names: ['Ali usta'], message: 'Kutilayotgan ustalar bor'}});
  for (const [nom, ikkinchi, kutilgan] of [
    ['G1 matn sabab', javob(400, {detail: SABAB}), SABAB],
    ["G2 pydantic ro'yxati", javob(422, {detail: [{loc: ['body', 'force'], msg: 'Input should be a valid boolean'}]}),
     'force: Input should be a valid boolean'],
    ['G3 obyekt `{message}`', javob(400, {detail: {message: 'OBYEKT-SABAB'}}), 'OBYEKT-SABAB'],
  ]) {
    const n = await sinov({src: KPI_J, fn: 'submitCloseGiftPeriod', chaqiruv: 'submitCloseGiftPeriod(false)', javobFn: ketma(KUT, ikkinchi),
                           yordamchi: KPI_YORD, oldin: 'var isClosingGiftPeriod = false;'});
    tekshir(nom + " — ikkinchi (majburiy) yopish rad etildi: sabab ko'rinadi",
            !n.xato && n.sorovlar.filter(x => x.method === 'POST').length === 2 && korindimi(n, kutilgan),
            {xato: n.xato, xabar: n.xabarlar, sorov: n.sorovlar.map(x => x.method + ' ' + x.url)});
  }

  // ════════════════════════════════════════════════════════════
  bolim('S — statik');
  const ESKI = [
    ['finished.html', FIN, "r.detail?.message || 'Xato yuz berdi'"], ['finished.html', FIN, "((r.detail || {}).message || 'Xato')"],
    ['finished.html', FIN, "(r.detail || 'Xato')"], ['finished.html', FIN, "showMsg('Rasm yuklanmadi', 'error')"],
    ['inventory.html', INV, "invToast('Xato yuz berdi')"], ['inventory.html', INV, "invToast('❌ Xato yuz berdi')"],
    ['inventory.html', INV, "invToast(d.detail || 'Xato yuz berdi')"], ['kpi.html', KPI, "alert('Xato yuz berdi')"],
    ['kpi.html', KPI, "(e.detail && e.detail.message ? e.detail.message : 'Xato')"],
  ];
  const qolgan = ESKI.filter(([f, src, naqsh]) => src.includes(naqsh)).map(([f, , n]) => `${f}: ${n}`);
  tekshir("S1 eski \"sababni yo'qotadigan\" naqshlar qolmadi (9 ta)", !qolgan.length, qolgan);
  const YORDAMCHILI = [
    [KPI, ['saveMasterKpi', 'deactivateMaster', 'reactivateMaster', 'saveAdvance', 'deleteAdvance', 'deleteEmployee', 'editEmpAdjustment',
           'editEmpBonus', 'submitCloseGiftPeriod']],
    [INV, ['uploadInventoryImage', 'setDefaultPenoplast', 'sendFullStockReport', 'sendLowStockAlert', 'editPrice', 'editMinStock',
           'editCategory', 'deletePurchase', 'deleteItem']],
    [FIN, ['uploadFpImage', 'addProduction', 'submitLoss', 'submitBatchSell', 'submitSell', 'editPrice', 'delFp', 'saveProduce',
           'releaseFpReservation', 'markReady']],
  ];
  const yordamsiz = [];
  for (const [src, nomlar] of YORDAMCHILI) {
    for (const n of nomlar) { const f = olib(src, n) || ''; if (!/\b(server)?[xX]atoSababi\(/.test(f)) yordamsiz.push(n); }
  }
  tekshir("S2 28 ta funksiyaning rad shoxi yagona yordamchi bilan (`xatoSababi` / `serverXatoSababi`)", !yordamsiz.length, yordamsiz);
  tekshir("S3 base.html: yordamchilar bitta ta'rif (takror yo'q)",
          (BASE.match(/function xatoSababi\(/g) || []).length === 1 && (BASE.match(/function serverXatoSababi\(/g) || []).length === 1, '');
  tekshir("S4 base.html: `tkKunFarqi` blokidan KEYIN (tk* bloki — base.html ↔ hodim_panel.html AYNAN nusxasi — o'zgarmaydi)",
          BASE.indexOf('function xatoSababi(') > BASE.indexOf('function tkKunFarqi('), '');

  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach(f => console.log('   - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})().catch(e => { console.log('ICHKI XATO: ' + e); console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL + 1}   jami = ${OK + FAIL + 1}`); process.exit(1); });
