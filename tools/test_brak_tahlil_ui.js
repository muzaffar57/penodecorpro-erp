#!/usr/bin/env node
/**
 * test_brak_tahlil_ui.js — 13-band 7-qadam (kech56, 2026-09-24): brak SABABI, JAVOBGAR hodim va
 * BRAK TAHLILI UI si.
 *
 *   templates/returns.html   — brak oynasi: `#brak-cause`, `#brak-worker`, `saveBrakBatch`,
 *                              `showBrakModal`; ro'yxat yorliqlari; admin "Brak tahlili" kartasi:
 *                              `brakTahlilHtml`, `loadBrakTahlil`, `loadBrakTahlilBadge`
 *   templates/finished.html  — "Kamaytirish" oynasi: `#loss-cause`, `#loss-worker`,
 *                              `lossBosqichTana`, `submitLoss`, `openLossModal`
 *   templates/dashboard.html — brak kartasi: `loadBrakFoiz` (ulush va me'yor ogohlantirishi)
 *
 * NIMA UCHUN KERAK
 * ----------------
 * Sabab va javobgar IXTIYORIY qo'shimcha (kech5 9-bo'lim QAT'IY SHARTI: brak yozish oqimi
 * O'ZGARMAYDI): tanlanmasa tana AYNAN avvalgidek; tanlansa faqat `brak_sabab` / `brak_javobgar_id`
 * (butun son) qo'shiladi; oyna qayta ochilganda oldingi tanlov qolmaydi; element bo'lmasa yiqilmaydi.
 * Tahlil kartasi server javobini chizadi — hodim ismi, mahsulot nomi, server matni HTML sifatida
 * chizilmasligi (escape), me'yordan oshganda ogohlantirish ko'rinishi, ulush yo'q bo'lsa "—".
 *
 * QANDAY ISHLAYDI: funksiyalar HTML dan JONLI o'qiladi (Jinja teglari olib tashlanadi), soxta
 * muhitda ishga tushiriladi. Topilmagan funksiya yoki istisno — yiqilgan tekshiruv (asl faylga
 * qarshi ham QULAMAYDI).
 *
 * ISHLATISH
 *     node tools/test_brak_tahlil_ui.js
 *     node tools/test_brak_tahlil_ui.js returns.html finished.html dashboard.html base.html   (mutatsiya)
 *
 * Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
function oqi(p) {
  try { return fs.readFileSync(p, 'utf8'); } catch (e) { return ''; }
}
const RETURNS = oqi(process.argv[2] || path.join(ROOT, 'templates', 'returns.html'));
const FINISHED = oqi(process.argv[3] || path.join(ROOT, 'templates', 'finished.html'));
const DASHBOARD = oqi(process.argv[4] || path.join(ROOT, 'templates', 'dashboard.html'));
const BASE = oqi(process.argv[5] || path.join(ROOT, 'templates', 'base.html'));

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
function qisqa(x) {
  let s;
  try { s = typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { s = String(x); }
  s = String(s);
  return s.length > 300 ? s.slice(0, 300) + '…' : s;
}

// Funksiyani HTML dan nomi bo'yicha ajratib olish (`async` bilan). Parametrlar ro'yxatidagi
// standart qiymat qavslari tana boshi deb olinmasin (kech38 saboqi) — avval `)` gacha o'tiladi.
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

// `const NOM = [...];` e'lonini ajratib olish (bir qatordan ko'p bo'lishi mumkin).
function konst(src, nom) {
  const i = src.indexOf('const ' + nom + ' =');
  if (i < 0) return null;
  const j = src.indexOf(';', i);
  return j < 0 ? null : src.slice(i, j + 1);
}

function jinjasiz(kod) {
  return kod === null ? null : kod.replace(/\{%[\s\S]*?%\}/g, '');
}

function javob(status, data) {
  return { ok: status >= 200 && status < 300, status, json: async () => JSON.parse(JSON.stringify(data)) };
}

function element(qiymat) {
  return { value: qiymat, checked: false, textContent: '', innerHTML: '', style: { display: 'none' },
           dataset: {}, disabled: false, max: '', classList: { toggle: () => {} } };
}

function muhit(elementlar, qs, qsa, globallar) {
  const sorovlar = [], xabarlar = [];
  let reload = 0;
  const ctx = Object.assign({
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, Array, Object, Error, RegExp,
    document: {
      getElementById: (id) => (Object.prototype.hasOwnProperty.call(elementlar, id) ? elementlar[id] : null),
      querySelectorAll: (sel) => ((qsa && qsa[sel]) || []),
      querySelector: (sel) => ((qs && Object.prototype.hasOwnProperty.call(qs, sel)) ? qs[sel] : null),
    },
    fetch: async (url, opts) => {
      let tana = null;
      try { tana = opts && opts.body ? JSON.parse(opts.body) : null; } catch (e) { tana = 'JSON EMAS'; }
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET', tana, xom: opts && opts.body });
      return javob(200, { success: true, id: sorovlar.length, cost_amount: 1000 });
    },
    showMsg: (t, tur) => { xabarlar.push({ t: String(t), tur }); },
    location: { reload: () => { reload++; } },
    setTimeout: () => 0,
    fmt: (n) => String(n),
    closeLossModal: () => {},
    closeBrakModal: () => {},
    brakServerSababi: async () => 'sabab',
    setLossMode: () => {},
  }, globallar || {});
  vm.createContext(ctx);
  return { ctx, sorovlar, xabarlar, reloadSoni: () => reload };
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

// ══════════════════════════════════════════════════════════════
// R — returns.html: brak oynasi
// ══════════════════════════════════════════════════════════════
const BRAK_ITEMS = [
  { order_id: 301, item_id: 4001, name: 'BRK_A', delivery_unit: 'metr', order_qty_normalized: 10 },
  { order_id: 301, item_id: 4002, name: 'BRK_B', delivery_unit: 'dona', order_qty_normalized: 5 },
];

function asosTana(it, qty) {
  return { order_id: it.order_id, order_item_id: it.item_id, item_name: it.name, quantity: qty,
           unit: it.delivery_unit, reason: 'Brak', refund_amount: 0, to_stock: false, notes: 'izoh',
           coating_applied: true };
}

// qiymatlar: undefined — element YO'Q; aks holda select qiymati
async function brakSina(bosqich, sabab, javobgar) {
  const inp = ['2', '1.5'].map((v, i) => { const e = element(v); e.dataset = { idx: String(i) }; e.style = {}; return e; });
  const el = { 'brak-error': element(''), 'brak-notes': element('  izoh  '), 'brak-save-btn': element(''),
               'brakModal': element('') };
  if (bosqich !== undefined) el['brak-stage'] = element(bosqich);
  if (sabab !== undefined) el['brak-cause'] = element(sabab);
  if (javobgar !== undefined) el['brak-worker'] = element(javobgar);
  const m = muhit(el, { 'input[name="brak-coating-applied"]:checked': { value: 'yes' } }, { '.brak-qty-inp': inp },
                  { brakItems: JSON.parse(JSON.stringify(BRAK_ITEMS)), isSavingBrak: false, brakSaqlanganBor: false });
  const kod = olib(RETURNS, 'saveBrakBatch');
  const r = kod ? await ishga(m, kod, 'saveBrakBatch()') : { xato: 'saveBrakBatch topilmadi' };
  return Object.assign(m, { xato: r.xato });
}

async function brakBolimi() {
  bolim('returns.html — brak oynasi (#brak-cause, #brak-worker, saveBrakBatch, showBrakModal)');
  const asos = [asosTana(BRAK_ITEMS[0], 2), asosTana(BRAK_ITEMS[1], 1.5)];
  const teng = (m, qosh) => !m.xato && m.sorovlar.length === 2
    && m.sorovlar.every((s, i) => s.url === '/api/returns' && s.xom === JSON.stringify(Object.assign({}, asos[i], qosh)));

  let m = await brakSina('kesish', 'ishchi', '7');
  tekshir("R1 bosqich + sabab 'ishchi' + javobgar '7' → tana = asl + brak_bosqich + brak_sabab + brak_javobgar_id (SON)",
          teng(m, { brak_bosqich: 'kesish', brak_sabab: 'ishchi', brak_javobgar_id: 7 }),
          m.xato || qisqa(m.sorovlar.map((s) => s.xom)));
  for (const k of ['xomashyo', 'uskuna', 'olcham', 'boshqa']) {
    m = await brakSina('', k, '');
    tekshir(`R2 faqat sabab '${k}' → asl + brak_sabab`, teng(m, { brak_sabab: k }), m.xato || qisqa(m.sorovlar.map((s) => s.xom)));
  }
  m = await brakSina('', '', '12');
  tekshir("R3 faqat javobgar '12' → asl + brak_javobgar_id 12 (butun son)", teng(m, { brak_javobgar_id: 12 }),
          m.xato || qisqa(m.sorovlar.map((s) => s.xom)));
  for (const [nomi, j] of [["bo'sh", ''], ['son emas', 'abc'], ['0', '0'], ['manfiy', '-3']]) {
    m = await brakSina('', '', j);
    tekshir(`R4 javobgar ${nomi} → kalit YO'Q, tana AYNAN avvalgidek`, teng(m, {}), m.xato || qisqa(m.sorovlar.map((s) => s.xom)));
  }
  m = await brakSina(undefined, undefined, undefined);
  tekshir("R4b #brak-stage / #brak-cause / #brak-worker sahifada YO'Q → yiqilmaydi, tana AYNAN avvalgidek",
          teng(m, {}), m.xato || qisqa(m.sorovlar.map((s) => s.xom)));

  const el = { brakModal: element(''), 'brak-project': element('7'), 'brak-notes': element('eski'),
               'brak-error': element(''), brakList: element(''), 'brak-stage': element('quritish'),
               'brak-cause': element('uskuna'), 'brak-worker': element('9') };
  let mm = muhit(el, {}, {}, { brakItems: [1], brakSaqlanganBor: true });
  const sk = olib(RETURNS, 'showBrakModal');
  let r = sk ? await ishga(mm, sk, 'showBrakModal()') : { xato: 'showBrakModal topilmadi' };
  tekshir("R5 showBrakModal: oldingi sabab va javobgar tozalanadi (''), oyna ochiladi",
          !r.xato && el['brak-cause'].value === '' && el['brak-worker'].value === '' && el['brak-stage'].value === ''
          && el.brakModal.style.display === 'flex',
          r.xato || qisqa({ sabab: el['brak-cause'].value, javobgar: el['brak-worker'].value }));
  const el2 = Object.assign({}, el); delete el2['brak-cause']; delete el2['brak-worker'];
  mm = muhit(el2, {}, {}, { brakItems: [1], brakSaqlanganBor: true });
  r = sk ? await ishga(mm, sk, 'showBrakModal()') : { xato: 'showBrakModal topilmadi' };
  tekshir("R5b showBrakModal: yangi tanlovlar YO'Q bo'lsa ham yiqilmaydi", !r.xato, r.xato);

  const oyna = RETURNS.slice(RETURNS.indexOf('id="brakModal"'), RETURNS.indexOf('brak-save-btn'));
  const sel = /<select id="brak-cause">([\s\S]*?)<\/select>/.exec(oyna);
  tekshir("R6 #brak-cause brak oynasi ichida: bo'sh variant birinchi, qolgani brak_sabablari dan (qattiq yozilmagan)",
          !!sel && /^\s*<option value="">— Tanlanmagan —<\/option>/.test(sel[1])
          && sel[1].includes('{% for k, v in (brak_sabablari or {}).items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}')
          && (sel[1].match(/<option/g) || []).length === 2,
          sel ? qisqa(sel[1]) : 'topilmadi');
  const sw = /<select id="brak-worker">([\s\S]*?)<\/select>/.exec(oyna);
  tekshir("R7 #brak-worker brak oynasi ichida: bo'sh variant birinchi, qolgani brak_hodimlari dan (id qiymat, ism matn)",
          !!sw && /^\s*<option value="">— Tanlanmagan —<\/option>/.test(sw[1])
          && sw[1].includes('{% for h in (brak_hodimlari or []) %}<option value="{{ h.id }}">{{ h.name }}')
          && (sw[1].match(/<option/g) || []).length === 2,
          sw ? qisqa(sw[1]) : 'topilmadi');
  const qator = RETURNS.slice(RETURNS.indexOf('{% if is_defect %}<span class="badge badge-danger">'),
                              RETURNS.indexOf('<span class="badge badge-ready">'));
  tekshir("R8 ro'yxat qatori: brak tarmog'ida sabab yorlig'i (lug'atdan) va javobgar ismi (hodim_nomlari dan)",
          qator.includes('<div class="brak-sabab"') && qator.includes('(brak_sabablari or {}).get(r.brak_sabab, r.brak_sabab)')
          && qator.includes('<div class="brak-javobgar"') && qator.includes('(hodim_nomlari or {}).get(r.brak_javobgar_id'),
          qisqa(qator));
}

// ══════════════════════════════════════════════════════════════
// F — finished.html: "Kamaytirish" oynasi
// ══════════════════════════════════════════════════════════════
async function lossSina(rejim, bosqich, sabab, javobgar) {
  const el = { 'loss-qty': element('4'), 'loss-reason': element('  tashishda sindi  ') };
  if (bosqich !== undefined) el['loss-stage'] = element(bosqich);
  if (sabab !== undefined) el['loss-cause'] = element(sabab);
  if (javobgar !== undefined) el['loss-worker'] = element(javobgar);
  const m = muhit(el, {}, {}, { _lossData: { id: 55, name: 'X', quantity: 10, unit: 'metr', category: 'profil' },
                                _lossMode: rejim });
  const kod = [olib(FINISHED, 'lossBosqichTana'), jinjasiz(olib(FINISHED, 'submitLoss'))];
  if (kod.some((x) => !x)) return Object.assign(m, { xato: 'funksiya topilmadi: ' + kod.map(Boolean) });
  const r = await ishga(m, kod.join('\n'), 'submitLoss()');
  return Object.assign(m, { xato: r.xato });
}

async function lossBolimi() {
  bolim('finished.html — "Kamaytirish" oynasi (#loss-cause, #loss-worker, lossBosqichTana, submitLoss)');
  const fn = olib(FINISHED, 'lossBosqichTana');
  for (const [nomi, b, s, j, kut] of [
    ['hammasi', 'kesish', 'xomashyo', '5', { brak_bosqich: 'kesish', brak_sabab: 'xomashyo', brak_javobgar_id: 5 }],
    ['faqat sabab', '', 'olcham', '', { brak_sabab: 'olcham' }],
    ['faqat javobgar', '', '', '14', { brak_javobgar_id: 14 }],
    ["javobgar son emas", '', '', 'x', {}],
    ["hech biri", '', '', '', {}],
    ["elementlar YO'Q", undefined, undefined, undefined, {}],
  ]) {
    const el = {};
    if (b !== undefined) el['loss-stage'] = element(b);
    if (s !== undefined) el['loss-cause'] = element(s);
    if (j !== undefined) el['loss-worker'] = element(j);
    const m = muhit(el, {}, {}, {});
    const r = fn ? await ishga(m, fn, 'lossBosqichTana()') : { xato: 'topilmadi' };
    tekshir(`F1 lossBosqichTana (${nomi}) → ${JSON.stringify(kut)}`,
            !r.xato && JSON.stringify(r.natija) === JSON.stringify(kut), r.xato || qisqa(r.natija));
  }
  const aslStock = { finished_product_id: 55, quantity: 4, reason: 'tashishda sindi' };
  const aslProd = { finished_product_id: 55, brak_qty: 4, notes: 'tashishda sindi' };
  let m = await lossSina('stock', 'saqlash_tashish', 'boshqa', '3');
  tekshir("F2 kamaytirish + bosqich + sabab + javobgar → /api/finished/loss, tana = asl + uchala kalit",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/finished/loss'
          && m.sorovlar[0].xom === JSON.stringify(Object.assign({}, aslStock,
            { brak_bosqich: 'saqlash_tashish', brak_sabab: 'boshqa', brak_javobgar_id: 3 })),
          m.xato || qisqa(m.sorovlar));
  m = await lossSina('production', '', 'uskuna', '');
  tekshir("F3 ishlab chiqarish braki + faqat sabab → /api/finished/production-brak, tana = asl + brak_sabab",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/finished/production-brak'
          && m.sorovlar[0].xom === JSON.stringify(Object.assign({}, aslProd, { brak_sabab: 'uskuna' })),
          m.xato || qisqa(m.sorovlar));
  m = await lossSina('stock', '', '', '');
  tekshir("F3b hech narsa tanlanmagan → tana AYNAN avvalgidek",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].xom === JSON.stringify(aslStock), m.xato || qisqa(m.sorovlar));

  const el = { 'loss-modal-sub': element(''), 'loss-stock-info': element(''), 'loss-qty': element('3'),
               'loss-reason': element('eski'), 'loss-mode-toggle': element(''), lossModal: element(''),
               'loss-stage': element('quritish'), 'loss-cause': element('ishchi'), 'loss-worker': element('8') };
  const mm = muhit(el, {}, {}, { PROD_BRAK_CATEGORIES: ['profil'], _lossData: null });
  const ok = olib(FINISHED, 'openLossModal');
  const r = ok ? await ishga(mm, ok, "openLossModal(55, 'X', 10, 'metr', 'profil')") : { xato: 'topilmadi' };
  tekshir("F4 openLossModal: oldingi sabab va javobgar tozalanadi (''), oyna ochiladi",
          !r.xato && el['loss-cause'].value === '' && el['loss-worker'].value === '' && el.lossModal.style.display === 'flex',
          r.xato || qisqa({ sabab: el['loss-cause'].value, javobgar: el['loss-worker'].value }));
  const oyna = FINISHED.slice(FINISHED.indexOf('id="lossModal"'), FINISHED.indexOf('id="loss-submit-btn"'));
  const sc = /<select id="loss-cause"[^>]*>([\s\S]*?)<\/select>/.exec(oyna);
  const sw = /<select id="loss-worker"[^>]*>([\s\S]*?)<\/select>/.exec(oyna);
  tekshir("F5 #loss-cause va #loss-worker \"Kamaytirish\" oynasi ichida, variantlar lug'at / hodimlardan",
          !!sc && !!sw && /^\s*<option value="">— Tanlanmagan —<\/option>/.test(sc[1])
          && sc[1].includes('{% for k, v in (brak_sabablari or {}).items() %}')
          && sw[1].includes('{% for h in (brak_hodimlari or []) %}<option value="{{ h.id }}">{{ h.name }}'),
          qisqa([sc && sc[1], sw && sw[1]]));
}

// ══════════════════════════════════════════════════════════════
// T — returns.html: "Brak tahlili" kartasi
// ══════════════════════════════════════════════════════════════
const XSS = '<img src=x onerror=__xss=1>"\'&';
function tahlilNamuna(qosh) {
  return Object.assign({
    yil: 2026, oy: 9, meyor_foiz: 5.0, brak_xarajat: 828986, ishlab_chiqarish_xarajat: 21111804,
    brak_foizi: 3.93, meyordan_oshdi: false, ogohlantirish: null, yozuvlar_soni: 3, yozuvlar_qiymati: 150000,
    bosqichlar: [{ kod: 'kesish', nomi: 'Kesish (penoplast kesish)', soni: 2, qiymat: 100000, ulush: 66.7 },
                 { kod: null, nomi: 'Belgilanmagan', soni: 1, qiymat: 50000, ulush: 33.3 }],
    sabablar: [{ kod: 'ishchi', nomi: 'Ishchi xatosi', soni: 3, qiymat: 150000, ulush: 100 }],
    javobgarlar: [{ kod: 7, nomi: 'Hodim ' + XSS, soni: 1, qiymat: 50000, ulush: 33.3 }],
    top_detallar: [{ nomi: 'Detal ' + XSS, birlik: 'metr' + XSS, soni: 2, miqdor: 12.5, qiymat: 100000, ulush: 66.7 }],
    yoqotishlar: [{ id: 1, sana: '2026-09-20T10:00:00', nomi: 'Mahsulot ' + XSS, miqdor: 1, birlik: 'm2', qiymat: 81447.37,
                    turi: 'Ishlab chiqarish braki', bosqich: 'Qoplash (loy tortish)', sabab: 'Uskuna / stanok nosozligi',
                    javobgar: 'Ism ' + XSS, izoh: '', yozgan: 'Admin ' + XSS }],
    trend: [{ yil: 2026, oy: 8, brak_xarajat: 0, ishlab_chiqarish_xarajat: 0, brak_foizi: null, meyordan_oshdi: false },
            { yil: 2026, oy: 9, brak_xarajat: 828986, ishlab_chiqarish_xarajat: 21111804, brak_foizi: 3.93, meyordan_oshdi: false }],
  }, qosh || {});
}

function tahlilKodi() {
  const qismlar = [olib(BASE, 'escapeHtml'), konst(RETURNS, 'BRAK_OY_NOMLARI'), olib(RETURNS, 'brakTahlilOyMatn'),
                   olib(RETURNS, 'brakFoizMatn'), olib(RETURNS, 'brakTahlilHtml')];
  return qismlar.every(Boolean) ? qismlar.join('\n') : null;
}

async function tahlilChiz(d) {
  const m = muhit({}, {}, {}, {});
  const kod = tahlilKodi();
  if (!kod) return { xato: 'funksiyalar topilmadi', natija: '' };
  vm.runInContext('var __d = ' + JSON.stringify(d) + ';', m.ctx);
  const r = await ishga(m, kod, 'brakTahlilHtml(__d)');
  return { xato: r.xato, natija: String(r.natija || ''), ctx: m.ctx };
}

async function tahlilBolimi() {
  bolim('returns.html — "Brak tahlili" kartasi (brakTahlilHtml, loadBrakTahlil, loadBrakTahlilBadge)');
  let r = await tahlilChiz(tahlilNamuna());
  const h = r.natija;
  tekshir("T1 chiziladi: ulush 3.93 %, me'yor 5 %, Moliya va ishlab chiqarish summalari",
          !r.xato && h.includes('class="brak-foiz"') && h.includes('3.93 %') && h.includes("Me'yor: 5 %")
          && h.includes('Sentyabr 2026'), r.xato || qisqa(h));
  tekshir("T2 me'yordan oshmagan → ogohlantirish bloki YO'Q, ulush yashil",
          !r.xato && !h.includes('brak-ogohlantirish') && h.includes('#16A34A'), r.xato || qisqa(h));
  tekshir("T3 hodim / detal / birlik / mahsulot / yozgan — HTML sifatida chizilmaydi (escape), __xss yo'q",
          !r.xato && !h.includes('<img') && (h.match(/&lt;img src=x onerror=__xss=1&gt;&quot;&#39;&amp;/g) || []).length === 6
          && r.ctx && r.ctx.__xss === undefined, r.xato || qisqa(h));
  tekshir("T4 oylar jadvali — har oy bitta qator; ulushi yo'q oy '—'",
          !r.xato && (h.match(/class="brak-trend-qator"/g) || []).length === 2 && h.includes('Avgust 2026'), r.xato || qisqa(h));
  tekshir("T5 yo'qotishlar jadvali — qator, turi, bosqich, sabab, qiymat",
          !r.xato && (h.match(/class="brak-yoqotish-qator"/g) || []).length === 1 && h.includes('Ishlab chiqarish braki')
          && h.includes('Uskuna / stanok nosozligi') && h.includes('2026-09-20'), r.xato || qisqa(h));
  r = await tahlilChiz(tahlilNamuna({ brak_foizi: 5.01, meyordan_oshdi: true,
                                      ogohlantirish: "Brak me'yordan oshdi: 5.01 % (me'yor 5 %) <b>x</b>",
                                      trend: [{ yil: 2026, oy: 9, brak_xarajat: 5010, ishlab_chiqarish_xarajat: 100000,
                                                brak_foizi: 5.01, meyordan_oshdi: true }] }));
  tekshir("T6 me'yordan oshdi → ogohlantirish bloki (matn escape), ulush qizil, oylar qatorida ⚠️",
          !r.xato && r.natija.includes('class="brak-ogohlantirish"') && r.natija.includes('&lt;b&gt;x&lt;/b&gt;')
          && !r.natija.includes('<b>x</b>') && r.natija.includes('#DC2626') && r.natija.includes('⚠️ 5.01 %'),
          r.xato || qisqa(r.natija));
  r = await tahlilChiz(tahlilNamuna({ brak_foizi: null, ishlab_chiqarish_xarajat: 0, bosqichlar: [], sabablar: [],
                                      javobgarlar: [], top_detallar: [], yoqotishlar: [], trend: [] }));
  tekshir("T7 ulush yo'q (ishlab chiqarish 0) → '—' va tushuntirish; bo'sh jadvallar — 6 ta \"Ma'lumot yo'q\"",
          !r.xato && r.natija.includes('>—<') && r.natija.includes("hisoblab bo'lmaydi")
          && (r.natija.match(/Ma'lumot yo'q/g) || []).length === 6, r.xato || qisqa(r.natija));

  // loadBrakTahlil — URL, rad va tarmoq xatolari
  const lt = olib(RETURNS, 'loadBrakTahlil');
  const yuklash = async (oyQiymati, fetchFn) => {
    const el = { brakTahlilContent: element('') };
    if (oyQiymati !== undefined) el['brak-tahlil-oy'] = element(oyQiymati);
    const urllar = [];
    const m = muhit(el, {}, {}, {
      fetch: async (u) => { urllar.push(String(u)); return fetchFn(); },
      brakTahlilHtml: () => 'CHIZILDI', escapeHtml: (s) => String(s).replace(/</g, '&lt;'),
    });
    const r = lt ? await ishga(m, lt, 'loadBrakTahlil()') : { xato: 'topilmadi' };
    return { xato: r.xato, urllar, html: el.brakTahlilContent.innerHTML };
  };
  let y = await yuklash('2026-09', () => javob(200, {}));
  tekshir("T8 oy tanlangan → /api/reports/brak-tahlil?oylar=6&year=2026&month=9, natija chiziladi",
          !y.xato && y.urllar.length === 1 && y.urllar[0] === '/api/reports/brak-tahlil?oylar=6&year=2026&month=9'
          && y.html === 'CHIZILDI', y.xato || qisqa(y));
  y = await yuklash('', () => javob(200, {}));
  tekshir("T8b oy tanlanmagan → faqat oylar=6 (server joriy oyni oladi)",
          !y.xato && y.urllar[0] === '/api/reports/brak-tahlil?oylar=6', y.xato || qisqa(y));
  y = await yuklash('2026-09', () => javob(403, { detail: '<i>Ruxsat yo\'q</i>' }));
  tekshir("T9 rad (403) → server sababi escape bilan, natija chizilmaydi",
          !y.xato && y.html.includes('&lt;i>Ruxsat') && !y.html.includes('CHIZILDI'), y.xato || qisqa(y));
  y = await yuklash('2026-09', () => { throw new Error('uzildi'); });
  tekshir("T9b tarmoq xatosi → 'Tarmoq xatosi', yiqilmaydi", !y.xato && y.html.includes('Tarmoq xatosi'), y.xato || qisqa(y));

  // loadBrakTahlilBadge — sarlavhadagi belgi
  const lb = olib(RETURNS, 'loadBrakTahlilBadge');
  const belgi = async (d, oyQiymati) => {
    const el = { brakTahlilBadge: element(''), 'brak-tahlil-oy': element(oyQiymati || '') };
    el.brakTahlilBadge.style = {};
    const m = muhit(el, {}, {}, { fetch: async () => javob(200, d) });
    const kod = [olib(RETURNS, 'brakTahlilOyMatn'), olib(RETURNS, 'brakFoizMatn'), lb];
    const r = kod.every(Boolean) ? await ishga(m, kod.join('\n'), 'loadBrakTahlilBadge()') : { xato: 'topilmadi' };
    return { xato: r.xato, el };
  };
  let b = await belgi({ yil: 2026, oy: 9, brak_foizi: 6.2, meyor_foiz: 5, meyordan_oshdi: true });
  tekshir("T10 belgi: me'yordan oshgan → '⚠️ bu oy 6.2 % (me'yor 5 %)' qizil; oy maydoni to'ldiriladi",
          !b.xato && b.el.brakTahlilBadge.textContent === "⚠️ bu oy 6.2 % (me'yor 5 %)"
          && b.el.brakTahlilBadge.style.color === '#DC2626' && b.el['brak-tahlil-oy'].value === '2026-09',
          b.xato || qisqa({ t: b.el.brakTahlilBadge.textContent, oy: b.el['brak-tahlil-oy'].value }));
  b = await belgi({ yil: 2026, oy: 9, brak_foizi: 3.93, meyor_foiz: 5, meyordan_oshdi: false }, '2026-05');
  tekshir("T10b me'yorda → yashil, ⚠️ yo'q; tanlangan oy O'ZGARTIRILMAYDI",
          !b.xato && b.el.brakTahlilBadge.textContent === "bu oy 3.93 % (me'yor 5 %)"
          && b.el.brakTahlilBadge.style.color === '#16A34A' && b.el['brak-tahlil-oy'].value === '2026-05',
          b.xato || qisqa(b.el.brakTahlilBadge.textContent));
  b = await belgi({ yil: 2026, oy: 9, brak_foizi: null, meyor_foiz: 5, meyordan_oshdi: false });
  tekshir("T10c ulush yo'q → belgi bo'sh", !b.xato && b.el.brakTahlilBadge.textContent === '', b.xato);
  tekshir("T11 belgi faqat admin uchun chaqiriladi (IS_ADMIN)",
          RETURNS.includes('if (IS_ADMIN) loadBrakTahlilBadge();'));
}

// ══════════════════════════════════════════════════════════════
// D — dashboard.html: loadBrakFoiz
// ══════════════════════════════════════════════════════════════
async function dashBolimi() {
  bolim('dashboard.html — brak ulushi va me\'yor ogohlantirishi (loadBrakFoiz)');
  const fn = olib(DASHBOARD, 'loadBrakFoiz');
  const sina = async (status, d) => {
    const el = { 'brk-foiz': element(''), 'brk-meyor': element(''), 'brk-ogohlantirish': element('') };
    el['brk-foiz'].style = {};
    const urllar = [];
    const m = muhit(el, {}, {}, { fetch: async (u) => { urllar.push(String(u)); return javob(status, d); } });
    const r = fn ? await ishga(m, fn, 'loadBrakFoiz()') : { xato: 'topilmadi' };
    return { xato: r.xato, el, urllar };
  };
  let s = await sina(200, { brak_foizi: 6.5, meyor_foiz: 5, meyordan_oshdi: true, ogohlantirish: "Brak me'yordan oshdi: 6.5 % (me'yor 5 %)" });
  tekshir("D1 me'yordan oshdi → ulush '6.5 %' qizil, me'yor '5 %', ogohlantirish ko'rinadi (textContent)",
          !s.xato && s.urllar[0] === '/api/reports/brak-tahlil?oylar=1' && s.el['brk-foiz'].textContent === '6.5 %'
          && s.el['brk-foiz'].style.color === '#DC2626' && s.el['brk-meyor'].textContent === '5 %'
          && s.el['brk-ogohlantirish'].style.display === 'block'
          && s.el['brk-ogohlantirish'].textContent === "⚠️ Brak me'yordan oshdi: 6.5 % (me'yor 5 %)"
          && s.el['brk-ogohlantirish'].innerHTML === '',
          s.xato || qisqa({ f: s.el['brk-foiz'].textContent, o: s.el['brk-ogohlantirish'].textContent }));
  s = await sina(200, { brak_foizi: 3.93, meyor_foiz: 5, meyordan_oshdi: false, ogohlantirish: null });
  tekshir("D2 me'yorda → yashil, ogohlantirish yashirin",
          !s.xato && s.el['brk-foiz'].textContent === '3.93 %' && s.el['brk-foiz'].style.color === '#16A34A'
          && s.el['brk-ogohlantirish'].style.display === 'none', s.xato || qisqa(s.el['brk-foiz']));
  s = await sina(200, { brak_foizi: null, meyor_foiz: 5, meyordan_oshdi: false, ogohlantirish: null });
  tekshir("D3 ulush yo'q → '—'", !s.xato && s.el['brk-foiz'].textContent === '—', s.xato || qisqa(s.el['brk-foiz']));
  s = await sina(403, { detail: 'Ruxsat yo\'q' });
  tekshir("D4 rad (403) → hech narsa o'zgarmaydi, yiqilmaydi",
          !s.xato && s.el['brk-foiz'].textContent === '' && s.el['brk-ogohlantirish'].style.display === 'none', s.xato);
  tekshir("D5 sahifa yuklanganda chaqiriladi, kartada qatorlar bor",
          DASHBOARD.includes('loadBrakFoiz();') && DASHBOARD.includes('id="brk-foiz"') && DASHBOARD.includes('id="brk-ogohlantirish"'));
}

(async () => {
  try {
    await brakBolimi();
    await lossBolimi();
    await tahlilBolimi();
    await dashBolimi();
  } catch (e) {
    tekshir('kutilmagan istisno', false, String((e && e.stack) || e).slice(0, 300));
  }
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})();
