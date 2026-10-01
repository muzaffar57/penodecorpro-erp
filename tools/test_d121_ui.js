#!/usr/bin/env node
/**
 * test_d121_ui.js — kech118 D BOSQICHI 1-qism (zip 121): sahifalardagi XATTI-HARAKAT (egasi QARORLARI kech118 11:40).
 *
 *   templates/finished.html  — G5-11 «Kam» chegarasi (`fpKamChegara`, `fpGuruhKammi`, `rowHtml`, `guruhHtml`,
 *                              `fpKamChegaraYoz`); G5-12 guruh «Sotish» (`fpGuruhSotish`), savatcha (`openBatchSellModal`,
 *                              `updateBatchRemain`, `submitBatchSell`, `onBatchCheckChange`)
 *   templates/returns.html   — G5-20 «Yangi qaytarish» → «Brak»: sabab majburiy (`saveReturn`, `updateReasonHint`,
 *                              `showAddModal`)
 *   templates/hodim_panel.html — G6-21 «Oyligim» (`oylikHtml`, `loadOylik`), rad etilgan so'rov sababi (`loadMyRequests`)
 *   templates/dashboard.html — G6-21 rad etishda sabab (`rejectAdvReq`)
 *   templates/finance.html   — G3-14 boshlang'ich balans ogohlantirishi (`loadCashBalance`)
 *
 * NIMA UCHUN KERAK
 *   Server qoidalari (tools/test_d121.py) — sahifa ularga mos so'rov yuborishi, foydalanuvchiga tushunarli ko'rsatishi va
 *   eski noqulayliklar (savatcha HAMMA qoldiq bilan to'lishi, «Kam» o'ylab topilishi) qaytmasligi kerak.
 * QANDAY ISHLAYDI: funksiyalar HTML dan JONLI o'qiladi (Jinja teglari — birinchi tarmoq), soxta DOM / fetch muhitida ishga
 *   tushiriladi. Topilmagan funksiya yoki istisno — yiqilgan tekshiruv (asl faylga qarshi ham QULAMAYDI).
 * ISHLATISH: node tools/test_d121_ui.js
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
const FINISHED = oqi('finished.html');
const BASE = oqi('base.html');
const RETURNS = oqi('returns.html');
const HODIM = oqi('hodim_panel.html');
const DASHBOARD = oqi('dashboard.html');
const FINANCE = oqi('finance.html');

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
  return s.length > 400 ? s.slice(0, 400) + '…' : s;
}
// Bo'shliqlarni bittaga (ru-RU ming ajratgichi — U+00A0 / U+202F)
function bosh(s) { return String(s).replace(/[  ]/g, ' '); }

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
// Jinja: `{% if %}A{% else %}B{% endif %}` → A (birinchi tarmoq — to'liq ruxsatli foydalanuvchi); qolgan teglar olib tashlanadi
function jinja(kod) {
  if (kod === null) return null;
  return kod.replace(/\{%\s*if[^%]*%\}([\s\S]*?)(?:\{%\s*else\s*%\}[\s\S]*?)?\{%\s*endif\s*%\}/g, '$1')
    .replace(/\{%[\s\S]*?%\}/g, '');
}
function funks(src, nomlar) {
  const yoq = [];
  const kod = nomlar.map((n) => { const f = olib(src, n); if (!f) yoq.push(n); return jinja(f) || ''; }).join('\n');
  return { kod, yoq };
}

function element(qiymat) {
  const el = {
    value: qiymat === undefined ? '' : qiymat, checked: false, textContent: '', innerHTML: '', hidden: false,
    style: { display: 'none' }, dataset: {}, disabled: false, max: '', children: [],
    classList: { toggle: () => {}, add: () => {}, remove: () => {}, contains: () => false },
    focus() { el._fokus = (el._fokus || 0) + 1; }, remove() { el._olib = true; },
    setAttribute() {}, querySelector: () => null, querySelectorAll: () => [],
  };
  return el;
}

function muhit(elementlar, globallar, qs, qsa) {
  const sorovlar = [], xabarlar = [], chaqiruvlar = [];
  const javoblar = [];
  const ctx = Object.assign({
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, isFinite, Array, Object, Error, RegExp,
    Date, Map, Set, Intl,
    document: {
      getElementById: (id) => (Object.prototype.hasOwnProperty.call(elementlar, id) ? elementlar[id] : null),
      querySelectorAll: (sel) => ((qsa && qsa[sel]) || []),
      querySelector: (sel) => ((qs && Object.prototype.hasOwnProperty.call(qs, sel)) ? qs[sel] : null),
    },
    fetch: async (url, opts) => {
      let tana = null;
      try { tana = opts && opts.body ? JSON.parse(opts.body) : null; } catch (e) { tana = 'JSON EMAS'; }
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET', tana, xom: opts && opts.body });
      const j = javoblar.length ? javoblar.shift() : { status: 200, data: { success: true } };
      return { ok: j.status >= 200 && j.status < 300, status: j.status, json: async () => JSON.parse(JSON.stringify(j.data)) };
    },
    showMsg: (t, tur) => { xabarlar.push({ t: String(t), tur }); },
    alert: (t) => { xabarlar.push({ t: String(t), tur: 'alert' }); },
    location: { reload: () => { chaqiruvlar.push('reload'); } },
    setTimeout: () => 0,
    window: { open: (u) => chaqiruvlar.push('open:' + u) },
  }, globallar || {});
  vm.createContext(ctx);
  return { ctx, sorovlar, xabarlar, chaqiruvlar, javoblar };
}

async function ishga(m, kod, chaqiruv) {
  try {
    vm.runInContext(kod, m.ctx);
    const natija = await vm.runInContext(chaqiruv, m.ctx);
    return { xato: null, natija };
  } catch (e) {
    return { xato: String((e && e.message) || e), natija: undefined };
  }
}

const BASE_YORDAM = funks(BASE, ['escapeHtml', 'sonKor', 'jsAttrEscape', 'matnRangi', 'tkMs', 'tkDate', 'tkSana']);
const FIN_YORDAM = funks(FINISHED, ['unitLabel', 'fpMiqdor', 'fpWidth2', 'fpMrpmi', 'fpSku', 'fmt', 'fpJarayondami',
  'fpKamChegara', 'fpPartiyaNomi', 'fpSavatNomi', 'fpGuruhKaliti', 'fpGuruhXulosa', 'fpGuruhla', 'fpGuruhKammi',
  'rowHtml', 'guruhHtml']);

// ══════════════════════════════════════════════════════════════
async function kamBolimi() {
  bolim('finished.html — G5-11 «Kam» chegarasi');
  tekshir('K0 funksiyalar topildi (fpKamChegara, fpPartiyaNomi, fpSavatNomi, rowHtml, guruhHtml ...)',
          !FIN_YORDAM.yoq.length && !BASE_YORDAM.yoq.length, qisqa(FIN_YORDAM.yoq.concat(BASE_YORDAM.yoq)));
  const m = muhit({}, { TM_TAHRIR: true, fpOchiq: new Set() });
  const kod = BASE_YORDAM.kod + '\n' + FIN_YORDAM.kod;
  let r = await ishga(m, kod, `[fpKamChegara({source:'produced', kam_chegara:null}), fpKamChegara({source:'produced'}),
    fpKamChegara({source:'produced', kam_chegara:0}), fpKamChegara({source:'produced', kam_chegara:12.5}),
    fpKamChegara({source:'returned', kam_chegara:5}), fpKamChegara(null)]`);
  tekshir("K1 fpKamChegara: null / yo'q / 0 → null (yozilmagan); 12.5 → 12.5; qaytgan mahsulot → null",
          !r.xato && JSON.stringify(r.natija) === JSON.stringify([null, null, null, 12.5, null, null]), r.xato || qisqa(r.natija));
  r = await ishga(m, '', `[fpGuruhKammi({bosh:{source:'produced', kam_chegara:10}, miqdor:5}),
    fpGuruhKammi({bosh:{source:'produced', kam_chegara:10}, miqdor:0}),
    fpGuruhKammi({bosh:{source:'produced', kam_chegara:10}, miqdor:15}),
    fpGuruhKammi({bosh:{source:'produced', kam_chegara:null}, miqdor:1})]`);
  tekshir("K2 fpGuruhKammi: chegara 10 — 5 «Kam»; 0 (tugagan) va 15 — yo'q; chegara yozilmagan — HECH QACHON «Kam»",
          !r.xato && JSON.stringify(r.natija) === '[true,false,false,false]', r.xato || qisqa(r.natija));
  const fp = (qosh) => JSON.stringify(Object.assign({ id: 7, name: 'Karniz', source: 'produced', category: 'profil', quantity: 4,
    unit: 'metr', unit_price: 1000, cost_price: 4000, total_value: 4000, ombor_qiymati: 4000, is_coated: true,
    production_status: 'ready', kam_chegara: null, created_at: '2026-10-01T05:00:00' }, qosh || {}));
  r = await ishga(m, '', `rowHtml(${fp()}, false)`);
  const h1 = String(r.natija || '');
  tekshir("K3 chegara yozilmagan qator: «Kam» ham, «Yetarli» ham, chiziq ham YO'Q (ilgari 4 metr «Kam» deb chiqardi)",
          !r.xato && !h1.includes('>Kam<') && !h1.includes('>Yetarli<') && !h1.includes('fp-mini-bar') && h1.includes('fp-qty'),
          r.xato || qisqa(h1.slice(h1.indexOf('fp-stock-col'), h1.indexOf('fp-stock-col') + 400)));
  r = await ishga(m, '', `rowHtml(${fp({ kam_chegara: 20 })}, false)`);
  const h2 = String(r.natija || '');
  tekshir("K4 chegara 20, qoldiq 4 → «Kam», chiziq, «chegara: 20 m» yozuvi",
          !r.xato && h2.includes('>Kam<') && h2.includes('fp-mini-bar') && /chegara: 20 m</.test(h2), r.xato || qisqa(h2));
  r = await ishga(m, '', `rowHtml(${fp({ kam_chegara: 3 })}, false)`);
  tekshir("K5 chegara 3, qoldiq 4 → «Yetarli»", !r.xato && String(r.natija).includes('>Yetarli<'), r.xato);
  r = await ishga(m, '', `rowHtml(${fp({ kam_chegara: 20 })}, true)`);
  const h3 = String(r.natija || '');
  tekshir("K6 partiya (guruh ichida) — holat guruh qatorida: partiyada «Kam» / chegara / qo'ng'iroq tugmasi YO'Q",
          !r.xato && !h3.includes('>Kam<') && !h3.includes('chegara:') && !h3.includes('fpKamChegaraYoz'), r.xato || qisqa(h3));
  r = await ishga(m, '', `rowHtml(${fp({ quantity: 0 })}, true)`);
  tekshir("K7 qoldiq 0 — «Tugagan» (chegarasiz ham)", !r.xato && String(r.natija).includes('>Tugagan<'), r.xato);
  r = await ishga(m, '', `rowHtml(${fp()}, false)`);
  tekshir("K8 «Tahrirlash» ruxsati bor — yakka qator menyusida «Kam» chegarasi tugmasi (fpKamChegaraYoz(7))",
          !r.xato && String(r.natija).includes('fpKamChegaraYoz(7)'), r.xato);
  const m2 = muhit({}, { TM_TAHRIR: false, fpOchiq: new Set() });
  r = await ishga(m2, kod, `rowHtml(${fp()}, false) + guruhHtml(fpGuruhla([${fp({ id: 1 })}, ${fp({ id: 2, quantity: 3 })}])[0])`);
  tekshir("K9 ruxsatsiz (TM_TAHRIR false) — qator va guruhda chegara tugmasi YO'Q",
          !r.xato && !String(r.natija).includes('fpKamChegaraYoz'), r.xato || qisqa(r.natija));
  r = await ishga(m, '', `guruhHtml(fpGuruhla([${fp({ id: 1, kam_chegara: 10 })}, ${fp({ id: 2, quantity: 3, kam_chegara: 10 })}])[0])`);
  const g1 = String(r.natija || '');
  tekshir("K10 guruh (2 partiya: 4 + 3 = 7, chegara 10) → «Kam», «chegara: 10 m», guruh qatorida «Sotish» va chegara tugmasi",
          !r.xato && g1.includes('>Kam<') && /chegara: 10 m</.test(g1) && g1.includes('fpGuruhSotish(this)')
          && g1.includes('fpKamChegaraYoz(1)'), r.xato || qisqa(g1));
  r = await ishga(m, '', `guruhHtml(fpGuruhla([${fp({ id: 1 })}, ${fp({ id: 2, quantity: 3 })}])[0])`);
  const g2 = String(r.natija || '');
  tekshir("K11 chegarasiz guruh — «Kam» / «Yetarli» YO'Q, «Sotish» bor",
          !r.xato && !g2.includes('>Kam<') && !g2.includes('>Yetarli<') && g2.includes('fpGuruhSotish(this)'), r.xato || qisqa(g2));
  r = await ishga(m, '', `guruhHtml(fpGuruhla([${fp({ id: 1, quantity: 0 })}, ${fp({ id: 2, quantity: 0 })}])[0])`);
  tekshir("K12 hammasi tugagan guruh — «Sotish» tugmasi YO'Q", !r.xato && !String(r.natija).includes('fpGuruhSotish'), r.xato);
  r = await ishga(m, '', `rowHtml(${fp({ id: 31, category: 'dynamic_bom', ishlab_chiqarish_id: 12 })}, true)
    + '|' + fpSavatNomi(${fp({ id: 31, category: 'dynamic_bom', ishlab_chiqarish_id: 12 })})
    + '|' + fpSavatNomi(${fp({ id: 31 })})`);
  const s1 = String(r.natija || '');
  tekshir("K13 partiya nomi bitta yordamchidan: qatorda «Partiya №12», savatcha belgisida «Karniz — Partiya №12 (01.10.2026)»; "
          + "MRP bo'lmagani — «Partiya FP-0031»",
          !r.xato && s1.includes('>Partiya №12<') && s1.includes('data-name="Karniz — Partiya №12 (01.10.2026)"')
          && s1.split('|')[1] === 'Karniz — Partiya №12 (01.10.2026)' && s1.split('|')[2] === 'Karniz — Partiya FP-0031 (01.10.2026)',
          r.xato || qisqa(s1.split('|').slice(1)));

  // fpKamChegaraYoz — kiritish oynasi → PUT
  for (const [nomi, javob, kut] of [['12,5', '12,5', { chegara: 12.5 }], ["bo'sh", '  ', { chegara: null }],
    ['butun', '30', { chegara: 30 }]]) {
    const mk = muhit({}, { fpItems: [{ id: 5, source: 'produced', unit: 'metr', name: 'X', kam_chegara: 4 }],
      kiritishOyna: async () => javob, loadFp: () => {}, serverXatoSababi: async () => 'x' });
    const k = funks(FINISHED, ['parseNum', 'unitLabel', 'fpMiqdor', 'fpKamChegara', 'fpKamChegaraYoz']);
    r = await ishga(mk, k.kod, 'fpKamChegaraYoz(5)');
    tekshir(`K14 chegara yozish (${nomi}) → PUT /api/finished/5/kam-chegara, tana ${JSON.stringify(kut)}`,
            !r.xato && mk.sorovlar.length === 1 && mk.sorovlar[0].method === 'PUT'
            && mk.sorovlar[0].url === '/api/finished/5/kam-chegara' && mk.sorovlar[0].xom === JSON.stringify(kut),
            r.xato || qisqa(mk.sorovlar));
  }
  for (const [nomi, javob] of [['manfiy', '-3'], ['matn', 'abc'], ['bekor', null]]) {
    const mk = muhit({}, { fpItems: [{ id: 5, source: 'produced', unit: 'metr', name: 'X', kam_chegara: null }],
      kiritishOyna: async () => javob, loadFp: () => {}, serverXatoSababi: async () => 'x' });
    const k = funks(FINISHED, ['parseNum', 'unitLabel', 'fpMiqdor', 'fpKamChegara', 'fpKamChegaraYoz']);
    r = await ishga(mk, k.kod, 'fpKamChegaraYoz(5)');
    tekshir(`K15 ${nomi} → so'rov YUBORILMAYDI${javob === null ? '' : ", xato xabari"}`,
            !r.xato && mk.sorovlar.length === 0 && (javob === null || mk.xabarlar.some((x) => x.tur === 'error')),
            r.xato || qisqa([mk.sorovlar, mk.xabarlar]));
  }
}

// ══════════════════════════════════════════════════════════════
async function sotishBolimi() {
  bolim('finished.html — G5-12 guruh «Sotish» va savatcha');
  const chk = (id, qty) => { const e = element(); e.dataset = { id: String(id), qty: String(qty) }; return e; };
  const guruhDom = (cheklar) => ({ closest: () => ({ querySelectorAll: (sel) => (sel === '.fp-guruh-ichi .fp-batch-check' ? cheklar : []) }) });
  const k = funks(FINISHED, ['fpGuruhSotish']);
  tekshir('S0 fpGuruhSotish topildi', !k.yoq.length, qisqa(k.yoq));
  let c = [chk(1, 5), chk(2, 0), chk(3, 2.5)];
  let m = muhit({}, { fpItems: [], onBatchCheckChange() { m.chaqiruvlar.push('belgi'); }, openBatchSellModal() { m.chaqiruvlar.push('savat'); },
    openSellModal() { m.chaqiruvlar.push('yakka'); } });
  m.ctx.GD = guruhDom(c);
  let r = await ishga(m, k.kod, 'fpGuruhSotish(GD)');
  tekshir("S1 guruh «Sotish»: qoldig'i bor partiyalar belgilanadi (0 lik — yo'q), keyin savatcha ochiladi",
          !r.xato && c[0].checked && !c[1].checked && c[2].checked && m.chaqiruvlar.join(',') === 'belgi,savat',
          r.xato || qisqa([c.map((x) => x.checked), m.chaqiruvlar]));
  c = [chk(1, 0), chk(4, 7)];
  m = muhit({}, { fpItems: [{ id: 4, name: 'Travertin', quantity: 7, unit: 'kvadrat', unit_price: 0 }],
    onBatchCheckChange() { m.chaqiruvlar.push('belgi'); }, openBatchSellModal() { m.chaqiruvlar.push('savat'); },
    openSellModal(id, nom, q, u, p) { m.chaqiruvlar.push(`yakka:${id}:${nom}:${q}:${u}:${p}`); } });
  m.ctx.GD = guruhDom(c);
  r = await ishga(m, k.kod, 'fpGuruhSotish(GD)');
  tekshir("S2 sotsa bo'ladigan bitta partiya — oddiy «Sotish» oynasi (savatcha emas)",
          !r.xato && m.chaqiruvlar.join(',') === 'yakka:4:Travertin:7:kvadrat:0' && !c[1].checked, r.xato || qisqa(m.chaqiruvlar));
  c = [chk(1, 0)];
  m = muhit({}, { fpItems: [], onBatchCheckChange() { m.chaqiruvlar.push('belgi'); }, openBatchSellModal() { m.chaqiruvlar.push('savat'); },
    openSellModal() { m.chaqiruvlar.push('yakka'); } });
  m.ctx.GD = guruhDom(c);
  r = await ishga(m, k.kod, 'fpGuruhSotish(GD)');
  tekshir("S3 qoldiq yo'q — hech narsa ochilmaydi, xato xabari",
          !r.xato && !m.chaqiruvlar.length && m.xabarlar.some((x) => x.tur === 'error'), r.xato || qisqa([m.chaqiruvlar, m.xabarlar]));

  // openBatchSellModal — miqdor BO'SH, «Qoladi»
  const el = {};
  for (const id of ['batch-modal-sub', 'batch-buyer', 'batch-master', 'batch-paymethod', 'batch-agreed', 'batch-discount-info',
    'batch-items-list', 'batchSellModal']) el[id] = element('x');
  m = muhit(el, { _batchItems: { 3: { name: 'Karniz — Partiya №3 (01.10.2026)', maxQty: 12.5, unit: 'metr', price: 1000 },
    8: { name: 'Karniz — Partiya №8', maxQty: 4, unit: 'metr', price: 0 } }, updateBatchTotal() {} });
  const kb = funks(FINISHED, ['unitLabel', 'fpMiqdor', 'narxMatni', 'narxKorinishi', 'openBatchSellModal']);
  r = await ishga(m, BASE_YORDAM.kod + '\n' + kb.kod, 'openBatchSellModal()');
  const lst = String(el['batch-items-list'].innerHTML);
  tekshir("S4 savatcha: har qatorda «Kerakli miqdor» BO'SH (value=\"\"), yorliq «Qoladi» (hozircha butun qoldiq), «Mavjud miqdor» YO'Q",
          !r.xato && (lst.match(/class="batch-qty" value=""/g) || []).length === 2 && (lst.match(/>Qoladi</g) || []).length === 2
          && !lst.includes('Mavjud miqdor') && lst.includes('>12,5 m<') && el.batchSellModal.style.display === 'flex',
          r.xato || qisqa(lst));
  tekshir("S5 savatcha sarlavhasi — bo'sh qolgani sotilmasligi aytiladi; partiya nomi qatorda",
          String(el['batch-modal-sub'].textContent).includes("bo'sh qolgani sotilmaydi") && lst.includes('Karniz — Partiya №3 (01.10.2026)'),
          qisqa(el['batch-modal-sub'].textContent));

  // updateBatchRemain
  const qolEl = element('');
  const inp = element('5');
  inp.dataset = { max: '12.5', unit: 'm' };
  inp.closest = () => ({ querySelector: () => qolEl });
  m = muhit({}, {});
  m.ctx.INP = inp;
  const ku = funks(FINISHED, ['fpMiqdor', 'updateBatchRemain']);
  r = await ishga(m, ku.kod, 'updateBatchRemain(INP); const a = QOL.textContent; INP.value = "20"; updateBatchRemain(INP); [a, QOL.textContent, QOL.style.color]'.replace(/QOL/g, 'INP.closest().querySelector()'));
  tekshir("S6 «Qoladi»: 12,5 − 5 = 7,5 m; ortiqcha yozilsa — «faqat 12,5 m bor» (qizil)",
          !r.xato && r.natija && r.natija[0] === '7,5 m' && r.natija[1] === 'faqat 12,5 m bor' && r.natija[2] === '#DC2626',
          r.xato || qisqa(r.natija));

  // submitBatchSell
  const qator = (id, qty, max, narx) => {
    const q = element(qty); q.dataset = { max: String(max), unit: 'm' };
    const p = element(narx);
    return { dataset: { id: String(id) }, querySelector: (s) => (s === '.batch-qty' ? q : (s === '.batch-price' ? p : null)) };
  };
  const ks = funks(FINISHED, ['parseNum', 'fpMiqdor', 'batchOriginalTotal', 'submitBatchSell']);
  async function sotSina(qatorlar) {
    const e2 = { 'batch-master': element('none'), 'batch-agreed': element(''), 'batch-buyer': element(''), 'batch-paymethod': element('naqd') };
    const mm = muhit(e2, { _batchItems: { 1: { name: 'A' }, 2: { name: 'B' } }, closeBatchSellModal() {}, clearBatchSelection() {},
      customConfirm: async () => false, xatoSababi: () => 'x', fmt: String }, {}, { '.batch-item-row': qatorlar });
    const rr = await ishga(mm, ks.kod, 'submitBatchSell()');
    return Object.assign(mm, { xato: rr.xato });
  }
  m = await sotSina([qator(1, '', 10, '1 000'), qator(2, '2', 5, '1 500')]);
  tekshir("S7 bo'sh qator SOTILMAYDI — faqat miqdor yozilgani yuboriladi",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/finished/sell-batch'
          && JSON.stringify(m.sorovlar[0].tana.items) === JSON.stringify([{ finished_product_id: 2, quantity: 2, unit_price: 1500 }]),
          m.xato || qisqa(m.sorovlar));
  m = await sotSina([qator(1, '', 10, '1 000'), qator(2, '0', 5, '1 500')]);
  tekshir("S8 hech qaysi qatorga miqdor yozilmagan — so'rov YO'Q, «Kamida bitta qatorga …»",
          !m.xato && !m.sorovlar.length && m.xabarlar.some((x) => x.t.includes('Kamida bitta qatorga')), m.xato || qisqa(m.xabarlar));
  m = await sotSina([qator(1, '11', 10, '1 000')]);
  tekshir("S9 qoldiqdan ko'p — so'rov YO'Q, «A: omborda faqat 10 m bor»",
          !m.xato && !m.sorovlar.length && m.xabarlar.some((x) => x.t === 'A: omborda faqat 10 m bor'), m.xato || qisqa(m.xabarlar));
  m = await sotSina([qator(1, '1', 10, '')]);
  tekshir("S10 miqdor bor, narx yo'q — so'rov YO'Q, «A: 1 birlik narxini yozing»",
          !m.xato && !m.sorovlar.length && m.xabarlar.some((x) => x.t === 'A: 1 birlik narxini yozing'), m.xato || qisqa(m.xabarlar));
  tekshir("S11 tugma «✓ Sotish» (ilgari «✓ Hammasini sotish»)",
          FINISHED.includes('onclick="submitBatchSell()"') && FINISHED.includes('>✓ Sotish</button>') && !FINISHED.includes('Hammasini sotish'));

  // onBatchCheckChange — telefonda panel oxirgi qatorni yopmasin
  const bar = element(''); const cnt = element(''); const lst2 = element('');
  lst2.style = {};
  const c1 = element(); c1.checked = true; c1.dataset = { id: '1', name: 'A', qty: '5', unit: 'm', price: '0' };
  m = muhit({ batchSellBar: bar, batchSellCount: cnt, fpList: lst2 }, { _batchItems: {} }, {}, { '.fp-batch-check': [c1] });
  const ko = funks(FINISHED, ['onBatchCheckChange']);
  r = await ishga(m, ko.kod, 'onBatchCheckChange(); const a = [FPL.style.paddingBottom, BAR.style.display]; CHK.checked = false; onBatchCheckChange(); a.concat([FPL.style.paddingBottom, BAR.style.display])'
    .replace(/FPL/g, "document.getElementById('fpList')").replace(/BAR/g, "document.getElementById('batchSellBar')")
    .replace(/CHK/g, "document.querySelectorAll('.fp-batch-check')[0]"));
  tekshir("S12 belgilanganda ro'yxat ostiga joy (96px) — suzuvchi panel qatorni yopmaydi; bekor qilinganda qaytadi",
          !r.xato && JSON.stringify(r.natija) === JSON.stringify(['96px', 'flex', '', 'none']), r.xato || qisqa(r.natija));
}

// ══════════════════════════════════════════════════════════════
async function qaytarishBolimi() {
  bolim('returns.html — G5-20 «Yangi qaytarish» → «Brak»: sabab majburiy');
  const k = funks(RETURNS, ['saveReturn']);
  tekshir('R0 saveReturn topildi', !k.yoq.length);
  async function sina(sabab, cause, stage, worker) {
    const el = { 'f-order': element('7'), 'f-item': element('11'), 'f-qty': element('2'), 'add-error': element(''),
      'return-save-btn': element('Saqlash'), 'f-value': element('0'), 'f-notes': element('izoh') };
    if (cause !== undefined) el['f-brak-cause'] = element(cause);
    if (stage !== undefined) el['f-brak-stage'] = element(stage);
    if (worker !== undefined) el['f-brak-worker'] = element(worker);
    el['add-error'].style = {};
    el['return-save-btn'].style = {};
    const m = muhit(el, { currentOrderItems: [{ id: 11, name: 'D', order_qty_normalized: 10, delivery_unit: 'metr' }],
      isSavingReturn: false }, { 'input[name="f-reason"]:checked': { value: sabab } });
    const r = await ishga(m, k.kod, 'saveReturn()');
    return Object.assign(m, { xato: r.xato, el });
  }
  let m = await sina('Brak', '', 'kesish', '4');
  tekshir("R1 «Brak», sabab tanlanmagan — so'rov YO'Q, «❌ Brak sababini tanlang (ro'yxatdan)», maydonga fokus",
          !m.xato && !m.sorovlar.length && m.el['add-error'].textContent === "❌ Brak sababini tanlang (ro'yxatdan)"
          && m.el['f-brak-cause']._fokus === 1, m.xato || qisqa([m.sorovlar, m.el['add-error'].textContent]));
  m = await sina('Brak', undefined, undefined, undefined);
  tekshir("R2 «Brak», sabab maydoni sahifada yo'q — so'rov YUBORILMAYDI (sababsiz brak yo'q)",
          !m.xato && !m.sorovlar.length, m.xato || qisqa(m.sorovlar));
  m = await sina('Brak', 'uskuna', 'kesish', '4');
  const t = (m.sorovlar[0] || {}).tana || {};
  tekshir("R3 «Brak» + sabab 'uskuna', bosqich 'kesish', javobgar '4' → tanada brak_sabab, brak_bosqich, brak_javobgar_id 4 (son)",
          !m.xato && m.sorovlar.length === 1 && t.reason === 'Brak' && t.brak_sabab === 'uskuna' && t.brak_bosqich === 'kesish'
          && t.brak_javobgar_id === 4, m.xato || qisqa(t));
  m = await sina('Brak', 'olcham', '', '');
  const t2 = (m.sorovlar[0] || {}).tana || {};
  tekshir("R4 bosqich / javobgar tanlanmagan — kalitlari YO'Q (ixtiyoriy), sabab bor",
          !m.xato && t2.brak_sabab === 'olcham' && !('brak_bosqich' in t2) && !('brak_javobgar_id' in t2), m.xato || qisqa(t2));
  m = await sina('Ortiqcha', 'uskuna', 'kesish', '4');
  const t3 = (m.sorovlar[0] || {}).tana || {};
  tekshir("R5 «Butun» (Ortiqcha) — brak maydonlari (yashirin qolgan tanlov bo'lsa ham) YUBORILMAYDI",
          !m.xato && m.sorovlar.length === 1 && t3.reason === 'Ortiqcha' && !Object.keys(t3).some((x) => x.startsWith('brak_')),
          m.xato || qisqa(t3));
  // updateReasonHint — brak maydonlari faqat «Brak» da ko'rinadi
  const ku = funks(RETURNS, ['updateReasonHint']);
  for (const [sabab, kut] of [['Brak', 'block'], ['Ortiqcha', 'none']]) {
    const wrap = element(''); wrap.style = { display: 'x' };
    const mm = muhit({ 'reason-hint': element(''), 'f-item': element(''), 'coating-applied-wrap': element(''), 'f-brak-wrap': wrap },
      { currentOrderItems: [] }, { 'input[name="f-reason"]:checked': { value: sabab } });
    const r = await ishga(mm, ku.kod, 'updateReasonHint()');
    tekshir(`R6 «${sabab}» → brak maydonlari ${kut}`, !r.xato && wrap.style.display === kut, r.xato || wrap.style.display);
  }
  // showAddModal — brak maydonlari tozalanadi
  const ks = funks(RETURNS, ['showAddModal']);
  const e = {};
  for (const id of ['addModal', 'f-order', 'f-item', 'f-qty', 'f-unit-price', 'f-value', 'f-notes', 'f-unit-label', 'add-error']) e[id] = element('eski');
  for (const id of ['f-brak-cause', 'f-brak-stage', 'f-brak-worker']) { e[id] = element('eski'); e[id].style = { borderColor: '#DC2626' }; }
  const radio = { checked: false };
  const mm = muhit(e, { updateReasonHint() {} }, { 'input[name="f-reason"][value="Ortiqcha"]': radio });
  const r = await ishga(mm, ks.kod, 'showAddModal()');
  tekshir("R7 «Yangi qaytarish» qayta ochilganda sabab / bosqich / javobgar bo'sh, qizil chegara olib tashlanadi",
          !r.xato && ['f-brak-cause', 'f-brak-stage', 'f-brak-worker'].every((x) => e[x].value === '' && e[x].style.borderColor === '')
          && radio.checked === true, r.xato || qisqa(['f-brak-cause', 'f-brak-stage', 'f-brak-worker'].map((x) => e[x].value)));
}

// ══════════════════════════════════════════════════════════════
async function hodimBolimi() {
  bolim('hodim_panel.html — G6-21 «Oyligim» va rad etish sababi');
  const eh = funks(HODIM, ['escapeHtml', 'tkMs', 'tkDate', 'tkSana', 'oylikHtml', 'loadOylik', 'loadMyRequests']);
  tekshir('H0 oylikHtml / loadOylik / loadMyRequests topildi', !eh.yoq.length, qisqa(eh.yoq));
  let m = muhit({}, {});
  let r = await ishga(m, eh.kod, `oylikHtml({nomi: 'Oktabr 2026', joriy: true, hisoblangan: 3110000, olingan: 350002, qolgan: 2759998,
      bonus: 150000, bonus_sababi: '<b>Yaxshi</b>', kamaytirish: 40000, kamaytirish_sababi: '2 kun', tolovlar: [
      {sana: '2026-09-30T20:30:00', summa: 100002}]})`);
  const h = bosh(r.natija || '');
  tekshir("H1 oy bloki: nomi + «(joriy oy — hozirgacha)», Hisoblangan 3 110 000, bonus +150 000 (sababi ESCAPE), kamaytirildi −40 000, "
          + "Olingan 350 002, Qolgan 2 759 998, to'lov sanasi Toshkent (01.10.2026)",
          !r.xato && h.includes('Oktabr 2026') && h.includes('(joriy oy — hozirgacha)') && h.includes("3 110 000 so'm")
          && h.includes("+150 000 so'm") && h.includes('&lt;b&gt;Yaxshi&lt;/b&gt;') && !h.includes('<b>Yaxshi')
          && h.includes("−40 000 so'm") && h.includes("350 002 so'm") && h.includes('>Qolgan<') && h.includes("2 759 998 so'm")
          && h.includes("01.10.2026 — 100 002 so'm"), r.xato || qisqa(h));
  r = await ishga(m, '', `oylikHtml({nomi: 'Sentabr 2026', joriy: false, hisoblangan: 0, olingan: 70000, qolgan: -70000, bonus: 0,
      kamaytirish: 0, tolovlar: []})`);
  const h2 = bosh(r.natija || '');
  tekshir("H2 ortiqcha olingan (qolgan < 0) — «Ortiqcha olingan 70 000» (minussiz), bonus / kamaytirish qatorlari yo'q, «joriy» yo'q",
          !r.xato && h2.includes('>Ortiqcha olingan<') && h2.includes("70 000 so'm") && !h2.includes('-70') && !h2.includes('bonus')
          && !h2.includes('kamaytirildi') && !h2.includes('joriy'), r.xato || qisqa(h2));
  const ol = element('');
  m = muhit({ 'oylik-list': ol }, {});
  m.javoblar.push({ status: 200, data: { oylar: [{ nomi: 'Oktabr 2026', joriy: true, hisoblangan: 1, olingan: 0, qolgan: 1, tolovlar: [] },
    { nomi: 'Sentabr 2026', joriy: false, hisoblangan: 2, olingan: 2, qolgan: 0, tolovlar: [] }] } });
  r = await ishga(m, eh.kod, 'loadOylik()');
  tekshir("H3 loadOylik → /api/hodim/oylik, ikkala oy bloki (joriy birinchi)",
          !r.xato && m.sorovlar[0] && m.sorovlar[0].url === '/api/hodim/oylik' && (String(ol.innerHTML).match(/class="oy-blok"/g) || []).length === 2
          && String(ol.innerHTML).indexOf('Oktabr') < String(ol.innerHTML).indexOf('Sentabr'), r.xato || qisqa(ol.innerHTML));
  m = muhit({ 'oylik-list': ol }, {});
  m.javoblar.push({ status: 500, data: {} });
  r = await ishga(m, eh.kod, 'loadOylik()');
  tekshir("H4 server xatosi — «Yuklashda xato» (bo'sh / yolg'on raqam emas)", !r.xato && String(ol.innerHTML).includes('Yuklashda xato'),
          r.xato || qisqa(ol.innerHTML));
  const rl = element('');
  m = muhit({ 'req-list': rl }, {});
  m.javoblar.push({ status: 200, data: [
    { id: 1, amount: 100000, requested_date: '2026-10-01', status: 'rejected', notes: null, rad_sababi: '<i>Berilmagan</i>' },
    { id: 2, amount: 50000, requested_date: '2026-10-01', status: 'rejected', notes: null, rad_sababi: null },
    { id: 3, amount: 70000, requested_date: '2026-10-01', status: 'confirmed', notes: null, rad_sababi: null }] });
  r = await ishga(m, eh.kod, 'loadMyRequests()');
  const q = String(rl.innerHTML);
  tekshir("H5 rad etilgan so'rovda «Sabab: …» (ESCAPE); eski (sababsiz) rad etilganda va tasdiqlanganda — sabab qatori yo'q",
          !r.xato && (q.match(/class="req-sabab"/g) || []).length === 1 && q.includes('Sabab: &lt;i&gt;Berilmagan&lt;/i&gt;')
          && !q.includes('<i>Berilmagan'), r.xato || qisqa(q));
}

// ══════════════════════════════════════════════════════════════
async function adminBolimi() {
  bolim("dashboard.html — rad etishda sabab; finance.html — boshlang'ich balans");
  const k = funks(DASHBOARD, ['rejectAdvReq']);
  tekshir('D0 rejectAdvReq topildi', !k.yoq.length);
  async function sina(javoblar, server) {
    const q = javoblar.slice();
    const izohlar = [];
    const m = muhit({}, { kiritishOyna: async (sar, o) => { izohlar.push(o && o.izoh); return q.length ? q.shift() : null; },
      removeAdvRow(id) { m.chaqiruvlar.push('olib:' + id); }, serverXatoSababi: async () => 'Server sababi',
      customConfirm: async () => true });
    if (server) m.javoblar.push(server);
    const r = await ishga(m, k.kod, 'rejectAdvReq(9)');
    return Object.assign(m, { xato: r.xato, izohlar });
  }
  let m = await sina(['', '   ', '  Bu kuni berilmagan  ']);
  tekshir("D1 bo'sh sabab — oyna QAYTA so'raydi (ogohlantirish bilan); yozilgach POST {sabab} (bo'shliqsiz), qator olib tashlanadi",
          !m.xato && m.izohlar.length === 3 && String(m.izohlar[1]).includes('Sabab yozilmadi') && m.sorovlar.length === 1
          && m.sorovlar[0].url === '/api/admin/advance-requests/9/reject' && m.sorovlar[0].method === 'POST'
          && m.sorovlar[0].xom === JSON.stringify({ sabab: 'Bu kuni berilmagan' }) && m.chaqiruvlar.includes('olib:9'),
          m.xato || qisqa([m.izohlar, m.sorovlar]));
  m = await sina([null]);
  tekshir("D2 «Bekor» — so'rov YO'Q, qator joyida", !m.xato && !m.sorovlar.length && !m.chaqiruvlar.length, m.xato || qisqa(m.sorovlar));
  m = await sina(['sabab'], { status: 400, data: { detail: 'x' } });
  tekshir("D3 server rad etsa — sababi ko'rsatiladi, qator joyida",
          !m.xato && m.xabarlar.some((x) => x.t.includes('Server sababi')) && !m.chaqiruvlar.length, m.xato || qisqa(m.xabarlar));

  const kc = funks(FINANCE, ['loadCashBalance']);
  tekshir('Q0 loadCashBalance topildi', !kc.yoq.length);
  for (const [nomi, qiy, kut] of [["kiritilmagan", false, false], ['kiritilgan', true, true], ['eski server (kalit yo\'q)', undefined, true]]) {
    const ogoh = element(''); ogoh.hidden = !kut;
    const val = element(''); val.style = {};
    const m2 = muhit({ 'cash-balance-val': val, 'cash-boshlangich-yoq': ogoh }, { fmtCash: (n) => String(n) });
    const d = { balance: -5 };
    if (qiy !== undefined) d.boshlangich_kiritilgan = qiy;
    m2.javoblar.push({ status: 200, data: d });
    const r = await ishga(m2, kc.kod, 'loadCashBalance()');
    tekshir(`Q1 boshlang'ich balans ${nomi} → ogohlantirish ${kut ? 'YASHIRIN' : "KO'RINADI"}`, !r.xato && ogoh.hidden === kut,
            r.xato || ogoh.hidden);
  }
}

(async () => {
  try {
    await kamBolimi();
    await sotishBolimi();
    await qaytarishBolimi();
    await hodimBolimi();
    await adminBolimi();
  } catch (e) {
    tekshir('kutilmagan istisno', false, String((e && e.stack) || e).slice(0, 400));
  }
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})();
