#!/usr/bin/env node
/**
 * test_oy_boshi_ui.js — kech119 (zip 125): Hisobotlar «oy boshi» va buyurtma «Foyda tahlili» — sahifa JS xatti-harakati.
 *
 *   templates/reports.html — `nisbatanMatni`, `davrSarlavhaMatni` (egasi QARORI 01.10 «Shu kunlar bilan»: joriy oy tugamagan —
 *                            «1–10-sentabrga nisbatan», bo'lim sarlavhasida «1–10-oktabr ↔ 1–10-sentabr (oyning shu kunlari)»),
 *                            `buildAiSummary` («Oy xulosasi»), `loadComparison`, `loadForecast` (K119-1: oylik xarajat bir marta —
 *                            izoh), `loadTopRankings` («Eng ko'p sarflangan xomashyo» — miqdor va BIRLIGI, «ming» siz)
 *   templates/orders.html  — `loadProfit` (G2-15: pul — butun so'm, foiz — vergul, qaytgan mahsulot «+… so'm» yashil — «−-…» emas,
 *                            paneldagi «Sotuv narxi» — kelishilgan summa), `selectOrder` / `loadPayments` (statik)
 *
 * O'LCHANGAN (sinov sayti, 01.10.2026): «Daromad o'tgan oyga nisbatan 100% kamaydi» (1 kun ↔ butun sentabr), «Taxminiy sof foyda
 *   −573 500 000 so'm», «Podveska 2 ming» (birliksiz); «Foyda tahlili» da hamma buyurtmada «11 458,947 so'm» (3 xonali tiyin).
 * QANDAY ISHLAYDI: funksiyalar HTML dan JONLI o'qiladi, soxta DOM / fetch muhitida ishga tushiriladi.
 * ISHLATISH: node tools/test_oy_boshi_ui.js      Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
function oqi(nom) {
  try { return fs.readFileSync(path.join(ROOT, 'templates', nom), 'utf8'); } catch (e) { return ''; }
}
const REPORTS = oqi('reports.html');
const ORDERS = oqi('orders.html');
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
  return s.length > 600 ? s.slice(0, 600) + '…' : s;
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
// bo'shliqlar (NBSP, tor NBSP) — oddiy bo'shliqqa, `escapeHtml` dagi apostrof («&#39;») — «'» (solishtirish uchun)
const B = (s) => String(s === undefined || s === null ? '' : s).replace(/[\u00a0\u202f]/g, ' ').replace(/&#39;/g, "'");
function element(v) {
  return { value: v === undefined ? '' : v, innerHTML: '', textContent: '', style: {}, dataset: {}, children: [],
           appendChild(c) { this.children.push(c); return c; }, remove() { this._removed = true; } };
}
function ctxYasa(qosh) {
  const ctx = Object.assign({ console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, isFinite, Array,
    Object, RegExp, Intl, Date, setTimeout }, qosh || {});
  vm.createContext(ctx);
  return ctx;
}
function yukla(ctx, src, nomlar) {
  const yoq = [];
  for (const n of nomlar) {
    const k = olib(src, n);
    if (!k) { yoq.push(n); continue; }
    vm.runInContext(k, ctx);
  }
  return yoq;
}
const BASE_YORDAM = ['escapeHtml', 'sonKor', 'foizKor', 'birlikKor', 'matnRangi'];
function soxtaFetch(javob) {
  return async (url) => {
    const kalit = Object.keys(javob).find(k => String(url).startsWith(k));
    const v = kalit ? javob[kalit] : null;
    return { ok: v !== null, status: v !== null ? 200 : 404, json: async () => v };
  };
}
function sahifaDom(idlar) {
  const els = {};
  for (const id of idlar) els[id] = element('');
  return { els, document: { getElementById: (id) => (id in els ? els[id] : null), documentElement: { getAttribute: () => null } } };
}

// ══════════════════════════════════════════════════════════════
async function hisobotBolimi() {
  bolim("reports.html — solishtirish davri, «Oy xulosasi», taxmin izohi, xomashyo birligi");
  const yoq = olib(REPORTS, 'nisbatanMatni') === null || olib(REPORTS, 'davrSarlavhaMatni') === null;
  tekshir("R0 `nisbatanMatni` va `davrSarlavhaMatni` topildi", !yoq);
  const { els, document } = sahifaDom(['compDavr', 'comp-daromad', 'comp-jami_xarajat', 'comp-sof_foyda', 'comp-foyda_foiz',
    'aiSummary', 'aiSummaryList', 'forecastBody', 'topCustomers', 'topProducts', 'topMaterials', 'topSuppliers']);
  const DAVR = { yil: 2026, oy: 10, oldingi_yil: 2026, oldingi_oy: 9, kun_gacha: 10, toliq_oy: false,
                 joriy_nom: '1–10-oktabr', oldingi_nom: '1–10-sentabr' };
  const DAVR1 = Object.assign({}, DAVR, { kun_gacha: 1, joriy_nom: '1-oktabr', oldingi_nom: '1-sentabr' });
  const TOLIQ = Object.assign({}, DAVR, { kun_gacha: null, toliq_oy: true, joriy_nom: 'oktabr', oldingi_nom: 'sentabr' });
  const COMP = {
    daromad: { current: 500000, previous: 1200000, change_pct: -58.3, holat: 'kamaydi' },
    jami_xarajat: { current: 4000000, previous: 1720000, change_pct: 132.6, holat: 'oshdi' },
    sof_foyda: { current: 1000, previous: 500, change_pct: 100.0, holat: 'oshdi' },
    foyda_foiz: { current: 1, previous: 1, change_pct: 0, holat: 'ozgarmadi' },
    davr: DAVR,
  };
  const ctx = ctxYasa({ document, fetch: soxtaFetch({}), tkHozir: () => ({ yil: 2026, oy: 10, kun: 10 }) });
  const qolgan = yukla(ctx, BASE, BASE_YORDAM)
    .concat(yukla(ctx, REPORTS, ['fmt', 'fmtQty', 'fmtShort', 'nisbatanMatni', 'davrSarlavhaMatni', 'ozgarishKorinishi',
      'topListHtml', 'loadComparison', 'loadForecast', 'loadTopRankings', 'buildAiSummary']));
  vm.runInContext("var qisqaSom = n => (n === null ? '—' : fmtShort(n) + \" so'm\"); var toliqSom = n => (n === null ? '—' : fmt(n) + \" so'm\"); var currentDays = 90;", ctx);
  tekshir('R0b kerakli funksiyalar topildi', !qolgan.length, qisqa(qolgan));
  if (qolgan.length) return;

  const nis = (d) => vm.runInContext(`nisbatanMatni(${JSON.stringify(d)})`, ctx);
  tekshir("R1 joriy oy tugamagan (10-kun) — «1–10-sentabrga nisbatan»; 1-kun — «1-sentabrga nisbatan»",
          nis(DAVR) === '1–10-sentabrga nisbatan' && nis(DAVR1) === '1-sentabrga nisbatan', qisqa([nis(DAVR), nis(DAVR1)]));
  tekshir("R2 to'liq oy yoki eski javob (`davr` yo'q) — «o'tgan oyga nisbatan»",
          nis(TOLIQ) === "o'tgan oyga nisbatan" && nis(null) === "o'tgan oyga nisbatan" && nis(undefined) === "o'tgan oyga nisbatan");
  const sar = (d) => vm.runInContext(`davrSarlavhaMatni(${JSON.stringify(d)})`, ctx);
  tekshir("R3 bo'lim sarlavhasi: «— 1–10-oktabr ↔ 1–10-sentabr (oyning shu kunlari)»; to'liq — «— oktabr ↔ sentabr»; yo'q — ''",
          sar(DAVR) === '— 1–10-oktabr ↔ 1–10-sentabr (oyning shu kunlari)' && sar(TOLIQ) === '— oktabr ↔ sentabr' && sar(null) === '',
          qisqa([sar(DAVR), sar(TOLIQ), sar(null)]));

  // «Oy xulosasi» — 1-oktabr holati (sinov saytida «Daromad o'tgan oyga nisbatan 100% kamaydi» edi)
  ctx.fetch = soxtaFetch({ '/api/reports/comparison': Object.assign({}, COMP, { davr: DAVR1,
    daromad: { current: 0, previous: 0, change_pct: null, holat: 'ozgarmadi' },
    sof_foyda: { current: -18500000, previous: -16000000, change_pct: -15.6, holat: 'kamaydi' } }) });
  await vm.runInContext('buildAiSummary([])', ctx);
  const xulosa = B(els.aiSummaryList.innerHTML);
  tekshir("R4 «Oy xulosasi» (1-oktabr): «Daromad 1-sentabrga nisbatan o'zgarmadi», «o'tgan oyga nisbatan 100% kamaydi» YO'Q",
          xulosa.includes('Daromad 1-sentabrga nisbatan') && xulosa.includes("o'zgarmadi") && !xulosa.includes("o'tgan oyga nisbatan")
          && !xulosa.includes('100%'), qisqa(xulosa));
  ctx.fetch = soxtaFetch({ '/api/reports/comparison': COMP });
  await vm.runInContext('buildAiSummary([])', ctx);
  const xulosa10 = B(els.aiSummaryList.innerHTML);
  tekshir("R5 «Oy xulosasi» (10-oktabr): «Daromad 1–10-sentabrga nisbatan 58,3% kamaydi»",
          xulosa10.includes('Daromad 1–10-sentabrga nisbatan') && xulosa10.includes('58,3% kamaydi'), qisqa(xulosa10));
  ctx.fetch = soxtaFetch({ '/api/reports/comparison': Object.assign({}, COMP, { davr: TOLIQ }) });
  await vm.runInContext('buildAiSummary([])', ctx);
  tekshir("R6 to'liq oy — «Daromad o'tgan oyga nisbatan …» (avvalgi matn)",
          B(els.aiSummaryList.innerHTML).includes("Daromad o'tgan oyga nisbatan"), qisqa(els.aiSummaryList.innerHTML));

  ctx.fetch = soxtaFetch({ '/api/reports/comparison': COMP });
  await vm.runInContext('loadComparison()', ctx);
  tekshir("R7 «O'tgan oy bilan taqqoslash» sarlavhasi yonida davr: «— 1–10-oktabr ↔ 1–10-sentabr (oyning shu kunlari)»",
          els.compDavr.textContent === '— 1–10-oktabr ↔ 1–10-sentabr (oyning shu kunlari)' && B(els['comp-daromad'].innerHTML).includes('58,3%'),
          qisqa([els.compDavr.textContent, els['comp-daromad'].innerHTML]));

  // Taxmin — oylik xarajat izohi (K119-1)
  ctx.fetch = soxtaFetch({ '/api/reports/forecast': { available: true, days_passed: 1, days_in_month: 31, forecast_daromad: 0,
    forecast_foyda: -18500000, current_daromad: 0, current_foyda: -18500000, doimiy_xarajat: 18500000 } });
  await vm.runInContext('loadForecast()', ctx);
  const fc = B(els.forecastBody.innerHTML);
  tekshir("R8 taxmin izohi: «Hodimlar oyligi, arenda, elektr va soliq (18 500 000 so'm) — bir marta hisoblangan»; sof foyda −18 500 000",
          fc.includes("Hodimlar oyligi, arenda, elektr va soliq (18 500 000 so'm) — bir marta hisoblangan")
          && fc.includes("-18 500 000 so'm") && !fc.includes('573'), qisqa(fc));
  ctx.fetch = soxtaFetch({ '/api/reports/forecast': { available: true, days_passed: 5, days_in_month: 31, forecast_daromad: 100,
    forecast_foyda: 50, current_daromad: 10, current_foyda: 5, doimiy_xarajat: 0 } });
  await vm.runInContext('loadForecast()', ctx);
  tekshir("R9 oylik xarajat 0 — izoh chiqmaydi", !B(els.forecastBody.innerHTML).includes('bir marta hisoblangan'));

  // Eng ko'p sarflangan xomashyo — birlik bilan
  ctx.fetch = soxtaFetch({ '/api/reports/top-customers': [], '/api/dashboard/top-finished-products': [],
    '/api/reports/top-suppliers': [],
    '/api/reports/top-materials': [{ item_name: 'Podveska', unit: 'dona', total_qty: 2000, movement_count: 3 },
                                   { item_name: 'Qorishma', unit: 'kg', total_qty: 1980.5, movement_count: 2 },
                                   { item_name: 'Setka', unit: 'm2', total_qty: 12, movement_count: 1 },
                                   { item_name: 'Birliksiz', unit: null, total_qty: 7, movement_count: 1 },
                                   { item_name: '<b>x</b>', unit: '<i>', total_qty: 1, movement_count: 1 }] });
  await vm.runInContext('loadTopRankings()', ctx);
  const tm = B(els.topMaterials.innerHTML);
  tekshir("R10 xomashyo: «2 000 dona», «1 980,5 kg», «12 m²», «7» — birligi bilan, «ming» YO'Q",
          tm.includes('2 000 dona') && tm.includes('1 980,5 kg') && tm.includes('12 m²') && tm.includes('>7<') && !tm.includes('ming'),
          qisqa(tm));
  tekshir("R11 nom va birlik escape qilinadi (HTML kiritilmaydi)", !tm.includes('<b>x</b>') && !tm.includes('<i>') && tm.includes('&lt;b&gt;'),
          qisqa(tm));

  // KPI kartasi — statik (loadKpi ko'p so'rov yuboradi): o'zgarish matni davrdan
  const kpi = olib(REPORTS, 'loadKpi') || '';
  tekshir("R12 KPI kartasi o'zgarishi: `nisbatanMatni(comp.davr)` («o'tgan oyga nisbatan» qattiq yozuvi yo'q)",
          kpi.includes('nisbatanMatni(comp.davr)') && !kpi.includes("\" o'tgan oyga nisbatan\""), '');
  const ai = olib(REPORTS, 'buildAiSummary') || '';
  tekshir("R13 «Oy xulosasi» qatorida «o'tgan oyga nisbatan» qattiq yozilmagan — `nisbatanMatni(comp.davr)`",
          ai.includes('nisbatanMatni(comp.davr)') && !ai.includes("o'tgan oyga nisbatan"), '');
}

// ══════════════════════════════════════════════════════════════
async function foydaBolimi() {
  bolim("orders.html — «Foyda tahlili» (G2-15)");
  const kod = olib(ORDERS, 'loadProfit');
  tekshir('O0 loadProfit topildi', !!kod);
  if (!kod) return;
  const { els, document } = sahifaDom(['profitRow', 'profitRow2', 's-cost', 's-profit', 's-total']);
  let modal = null;
  document.createElement = () => { modal = element(''); modal.id = ''; return modal; };
  document.body = { appendChild: (m) => { els[m.id || 'profitModal'] = m; return m; } };
  const PROFIT = {
    success: true, sotuv_narxi: 864000, tan_narxi: 11458.94742857143, foyda: -647684.6153, foyda_foiz: -14.6,
    breakdown: [
      { nomi: "Penoplast 14P (0,02 m³ × 572 947 so'm/m³)", summa: 11458.94742857143 },
      { nomi: "↩️ Omborga qaytgan mahsulot (tannarxdan ayrildi)", summa: -37010.4 },
      { nomi: "Usta haqi (Ali, 7,5% foydadan)", summa: 1500.5 },
    ],
  };
  const ctx = ctxYasa({ document, fetch: soxtaFetch({ '/api/orders/5/profit': PROFIT }), selectedOrderId: 5 });
  const qolgan = yukla(ctx, BASE, BASE_YORDAM).concat(yukla(ctx, ORDERS, ['formatNum', 'loadProfit']));
  tekshir('O0b kerakli funksiyalar topildi', !qolgan.length, qisqa(qolgan));
  if (qolgan.length) return;
  await vm.runInContext('loadProfit()', ctx);
  const h = B(modal ? modal.innerHTML : '');
  tekshir("O1 qaytgan mahsulot: «+37 010 so'm» yashil (ilgari «−-37 010» — ikki minus)",
          /color:var\(--m-15803d\)[^>]*>\+37 010 so'm</.test(h) && !h.includes('−-') && !h.includes('--37'), qisqa(h.slice(0, 3000)));
  tekshir("O2 xarajat qatorlari: «−11 459 so'm», «−1 501 so'm» (butun so'm, tiyinsiz)",
          h.includes("−11 459 so'm") && h.includes("−1 501 so'm"), '');
  tekshir("O3 kartalar va jami: sotuv «864 000», tan narxi «11 459», foyda «-647 685» — 3 xonali tiyin («647 684,615») YO'Q",
          h.includes('864 000<br>') && h.includes('11 459<br>') && h.includes('-647 685<br>') && h.includes("Jami tan narxi:")
          && !/\d,\d{3}/.test(h.replace(/0,02 m³ × 572 947/, '')), qisqa(h.match(/\d[\d ]*,\d+/g)));
  tekshir("O4 foiz — vergul: «-14,6%» (ikki joyda)", (h.match(/-14,6%/g) || []).length === 2, qisqa(h.match(/-?\d+[.,]\d%/g)));
  tekshir("O5 panel: Sotuv narxi «864 000 so'm» (kelishilgan), Tan narxi «11 459 so'm», Foyda «-647 685 so'm (-14,6%)»",
          B(els['s-total'].textContent) === "864 000 so'm" && B(els['s-cost'].textContent) === "11 459 so'm"
          && B(els['s-profit'].textContent) === "-647 685 so'm (-14,6%)",
          qisqa([els['s-total'].textContent, els['s-cost'].textContent, els['s-profit'].textContent]));
  tekshir("O6 panel qatorlari ko'rsatildi (Tan narxi, Foyda), modal ochildi",
          els.profitRow.style.display === 'flex' && els.profitRow2.style.display === 'flex' && modal && modal.style.display === 'flex',
          qisqa([els.profitRow.style, els.profitRow2.style, modal && modal.style]));

  const sel = olib(ORDERS, 'selectOrder') || '';
  tekshir("O7 buyurtma tanlanganda «Sotuv narxi» qaytarishdan oldingi jami (`d.total`) EMAS — «—», keyin kelishilgan",
          sel.includes("sTotal.textContent = '—'") && !/sTotal\.textContent\s*=\s*Number\(d\.total\)/.test(sel), '');
  const lp = olib(ORDERS, 'loadPayments') || '';
  tekshir("O8 buyurtma hisobi yuklanganda «Sotuv narxi» = kelishilgan (`hk.kelishilgan`)",
          /sTotalK\.textContent = formatNum\(hk \? hk\.kelishilgan : agreed\)/.test(lp), '');
  tekshir("O9 orders.html da `toLocaleString` qolmagan (summalar — formatNum / sonKor)", !/toLocaleString/.test(ORDERS), '');
}

(async () => {
  try { await hisobotBolimi(); } catch (e) { tekshir('HISOBOT bo\'limi qulamadi', false, e && e.stack); }
  try { await foydaBolimi(); } catch (e) { tekshir('FOYDA bo\'limi qulamadi', false, e && e.stack); }
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach(f => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})();
