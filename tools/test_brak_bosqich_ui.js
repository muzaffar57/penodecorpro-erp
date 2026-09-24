#!/usr/bin/env node
/**
 * test_brak_bosqich_ui.js — 13-band 1-qadam (kech53, 2026-09-24): brak BOSQICHI tanlovi UI si.
 *
 *   templates/returns.html  — brak oynasi: `#brak-stage`, `saveBrakBatch`, `showBrakModal`
 *   templates/finished.html — "Kamaytirish" oynasi: `#loss-stage`, `lossBosqichTana`,
 *                             `submitLoss` (ikkala rejim), `openLossModal`
 *
 * NIMA UCHUN KERAK
 * ----------------
 * Bosqich IXTIYORIY qo'shimcha (kech5 9-bo'lim QAT'IY SHARTI: brak yozish oqimi O'ZGARMAYDI).
 * Shuning uchun: (1) tanlanmasa serverga ketadigan TANA AYNAN avvalgidek bo'lishi (kalit umuman
 * qo'shilmaydi — eski UI testlari va server qoidalari shu tanani kutadi); (2) tanlansa — faqat
 * `brak_bosqich` kaliti qo'shiladi, qolgan hamma maydon AYNAN; (3) oyna qayta ochilganda oldingi
 * tanlov QOLIB KETMASLIGI (aks holda keyingi brak jimgina eski bosqich bilan yozilardi); (4) element
 * sahifada bo'lmasa (eski shablon, boshqa sahifa) funksiyalar yiqilmasligi SHART.
 *
 * QANDAY ISHLAYDI: funksiyalar HTML dan JONLI o'qiladi (Jinja teglari olib tashlanadi), soxta
 * muhitda ishga tushiriladi. Topilmagan funksiya yoki istisno — yiqilgan tekshiruv (asl faylga
 * qarshi ham QULAMAYDI).
 *
 * ISHLATISH
 *     node tools/test_brak_bosqich_ui.js
 *     node tools/test_brak_bosqich_ui.js boshqa/returns.html boshqa/finished.html   (mutatsiya uchun)
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

// Jinja teglarini olib tashlash (`{% if %}` / `{% else %}` tarmoqlari ikkalasi ham qoladi — sintaksis
// uchun zararsiz, test serverga ketadigan TANAni tekshiradi).
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
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, Array, Object, Error,
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
// returns.html — brak oynasi
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

async function brakSina(bosqich) {
  // bosqich: undefined — element YO'Q; aks holda select qiymati
  const inp = ['2', '1.5'].map((v, i) => { const e = element(v); e.dataset = { idx: String(i) }; e.style = {}; return e; });
  const el = { 'brak-error': element(''), 'brak-notes': element('  izoh  '), 'brak-save-btn': element(''),
               'brakModal': element('') };
  if (bosqich !== undefined) el['brak-stage'] = element(bosqich);
  const m = muhit(el, { 'input[name="brak-coating-applied"]:checked': { value: 'yes' } }, { '.brak-qty-inp': inp },
                  { brakItems: JSON.parse(JSON.stringify(BRAK_ITEMS)), isSavingBrak: false, brakSaqlanganBor: false });
  const kod = olib(RETURNS, 'saveBrakBatch');
  const r = kod ? await ishga(m, kod, 'saveBrakBatch()') : { xato: 'saveBrakBatch topilmadi' };
  return Object.assign(m, { xato: r.xato });
}

async function brakBolimi() {
  bolim('returns.html — brak oynasi (#brak-stage, saveBrakBatch, showBrakModal)');
  const asos = [asosTana(BRAK_ITEMS[0], 2), asosTana(BRAK_ITEMS[1], 1.5)];

  let m = await brakSina('qoplash');
  tekshir("R1 bosqich 'qoplash' → har qatorga POST, tana = asl tana + brak_bosqich (oxirida), qolgani AYNAN",
          !m.xato && m.sorovlar.length === 2
          && m.sorovlar.every((s, i) => s.url === '/api/returns'
            && s.xom === JSON.stringify(Object.assign({}, asos[i], { brak_bosqich: 'qoplash' }))),
          m.xato || qisqa(m.sorovlar.map((s) => s.xom)));
  for (const k of ['kesish', 'quritish', 'saqlash_tashish']) {
    m = await brakSina(k);
    tekshir(`R1b '${k}' → tanada brak_bosqich '${k}'`,
            !m.xato && m.sorovlar.length === 2 && m.sorovlar.every((s) => s.tana && s.tana.brak_bosqich === k),
            m.xato || qisqa(m.sorovlar.map((s) => s.tana)));
  }
  m = await brakSina('');
  tekshir("R2 tanlanmagan ('') → tana AYNAN avvalgidek (brak_bosqich kaliti YO'Q)",
          !m.xato && m.sorovlar.length === 2 && m.sorovlar.every((s, i) => s.xom === JSON.stringify(asos[i])),
          m.xato || qisqa(m.sorovlar.map((s) => s.xom)));
  m = await brakSina(undefined);
  tekshir("R3 #brak-stage sahifada YO'Q → yiqilmaydi, tana AYNAN avvalgidek",
          !m.xato && m.sorovlar.length === 2 && m.sorovlar.every((s, i) => s.xom === JSON.stringify(asos[i])),
          m.xato || qisqa(m.sorovlar.map((s) => s.xom)));

  // showBrakModal — oldingi tanlov tozalanadi
  const el = { brakModal: element(''), 'brak-project': element('7'), 'brak-notes': element('eski'),
               'brak-error': element(''), brakList: element(''), 'brak-stage': element('quritish') };
  let mm = muhit(el, {}, {}, { brakItems: [1], brakSaqlanganBor: true });
  const sk = olib(RETURNS, 'showBrakModal');
  let r = sk ? await ishga(mm, sk, 'showBrakModal()') : { xato: 'showBrakModal topilmadi' };
  tekshir("R4 showBrakModal: oldingi bosqich tozalanadi (''), oyna ochiladi",
          !r.xato && el['brak-stage'].value === '' && el.brakModal.style.display === 'flex' && el['brak-notes'].value === '',
          r.xato || qisqa({ bosqich: el['brak-stage'].value, oyna: el.brakModal.style.display }));
  const el2 = Object.assign({}, el); delete el2['brak-stage'];
  mm = muhit(el2, {}, {}, { brakItems: [1], brakSaqlanganBor: true });
  r = sk ? await ishga(mm, sk, 'showBrakModal()') : { xato: 'showBrakModal topilmadi' };
  tekshir("R5 showBrakModal: #brak-stage YO'Q bo'lsa ham yiqilmaydi", !r.xato, r.xato);

  // Shablon: tanlov brak oynasi ichida, bo'sh variant birinchi, variantlar lug'atdan
  const oyna = RETURNS.slice(RETURNS.indexOf('id="brakModal"'), RETURNS.indexOf('brak-save-btn'));
  const sel = /<select id="brak-stage">([\s\S]*?)<\/select>/.exec(oyna);
  tekshir("R6 #brak-stage brak oynasi ichida: bo'sh '— Tanlanmagan —' birinchi, qolgani brak_bosqichlari dan (qattiq yozilmagan)",
          !!sel && /^\s*<option value="">— Tanlanmagan —<\/option>/.test(sel[1])
          && sel[1].includes('{% for k, v in (brak_bosqichlari or {}).items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}')
          && (sel[1].match(/<option/g) || []).length === 2,
          sel ? qisqa(sel[1]) : 'topilmadi');
}

// ══════════════════════════════════════════════════════════════
// finished.html — "Kamaytirish" oynasi
// ══════════════════════════════════════════════════════════════
async function lossSina(rejim, bosqich) {
  const el = { 'loss-qty': element('4'), 'loss-reason': element('  tashishda sindi  ') };
  if (bosqich !== undefined) el['loss-stage'] = element(bosqich);
  const m = muhit(el, {}, {}, { _lossData: { id: 55, name: 'X', quantity: 10, unit: 'metr', category: 'profil' },
                                _lossMode: rejim });
  const kod = [olib(FINISHED, 'lossBosqichTana'), jinjasiz(olib(FINISHED, 'submitLoss'))];
  if (kod.some((x) => !x)) return Object.assign(m, { xato: 'funksiya topilmadi: ' + kod.map(Boolean) });
  const r = await ishga(m, kod.join('\n'), 'submitLoss()');
  return Object.assign(m, { xato: r.xato });
}

async function lossBolimi() {
  bolim('finished.html — "Kamaytirish" oynasi (#loss-stage, lossBosqichTana, submitLoss)');
  const fn = olib(FINISHED, 'lossBosqichTana');
  tekshir('F0 lossBosqichTana topildi', !!fn);
  for (const [nomi, qiy, kut] of [['qiymat', 'kesish', { brak_bosqich: 'kesish' }], ["bo'sh", '', {}],
                                   ["element YO'Q", undefined, {}]]) {
    const el = {};
    if (qiy !== undefined) el['loss-stage'] = element(qiy);
    const m = muhit(el, {}, {}, {});
    const r = fn ? await ishga(m, fn, 'lossBosqichTana()') : { xato: 'topilmadi' };
    tekshir(`F1 lossBosqichTana (${nomi}) → ${JSON.stringify(kut)}`,
            !r.xato && JSON.stringify(r.natija) === JSON.stringify(kut), r.xato || qisqa(r.natija));
  }

  const aslStock = { finished_product_id: 55, quantity: 4, reason: 'tashishda sindi' };
  const aslProd = { finished_product_id: 55, brak_qty: 4, notes: 'tashishda sindi' };
  let m = await lossSina('stock', 'saqlash_tashish');
  tekshir("F2 kamaytirish + 'saqlash_tashish' → /api/finished/loss, tana = asl + brak_bosqich",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/finished/loss'
          && m.sorovlar[0].xom === JSON.stringify(Object.assign({}, aslStock, { brak_bosqich: 'saqlash_tashish' })),
          m.xato || qisqa(m.sorovlar));
  m = await lossSina('stock', '');
  tekshir("F3 kamaytirish, tanlanmagan → tana AYNAN avvalgidek",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].xom === JSON.stringify(aslStock), m.xato || qisqa(m.sorovlar));
  m = await lossSina('production', 'qoplash');
  tekshir("F4 ishlab chiqarish braki + 'qoplash' → /api/finished/production-brak, tana = asl + brak_bosqich",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/finished/production-brak'
          && m.sorovlar[0].xom === JSON.stringify(Object.assign({}, aslProd, { brak_bosqich: 'qoplash' })),
          m.xato || qisqa(m.sorovlar));
  m = await lossSina('production', undefined);
  tekshir("F5 ishlab chiqarish braki, #loss-stage YO'Q → yiqilmaydi, tana AYNAN avvalgidek",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].xom === JSON.stringify(aslProd), m.xato || qisqa(m.sorovlar));

  // openLossModal — oldingi tanlov tozalanadi
  const el = { 'loss-modal-sub': element(''), 'loss-stock-info': element(''), 'loss-qty': element('3'),
               'loss-reason': element('eski'), 'loss-mode-toggle': element(''), lossModal: element(''),
               'loss-stage': element('quritish') };
  const mm = muhit(el, {}, {}, { PROD_BRAK_CATEGORIES: ['profil'], _lossData: null });
  const ok = olib(FINISHED, 'openLossModal');
  const r = ok ? await ishga(mm, ok, "openLossModal(55, 'X', 10, 'metr', 'profil')") : { xato: 'topilmadi' };
  tekshir("F6 openLossModal: oldingi bosqich tozalanadi (''), oyna ochiladi",
          !r.xato && el['loss-stage'].value === '' && el.lossModal.style.display === 'flex',
          r.xato || qisqa({ bosqich: el['loss-stage'].value }));

  const oyna = FINISHED.slice(FINISHED.indexOf('id="lossModal"'), FINISHED.indexOf('id="loss-submit-btn"'));
  const sel = /<select id="loss-stage"[^>]*>([\s\S]*?)<\/select>/.exec(oyna);
  tekshir("F7 #loss-stage \"Kamaytirish\" oynasi ichida: bo'sh variant birinchi, qolgani brak_bosqichlari dan",
          !!sel && /^\s*<option value="">— Tanlanmagan —<\/option>/.test(sel[1])
          && sel[1].includes('{% for k, v in (brak_bosqichlari or {}).items() %}<option value="{{ k }}">{{ v }}</option>{% endfor %}')
          && (sel[1].match(/<option/g) || []).length === 2,
          sel ? qisqa(sel[1]) : 'topilmadi');
}

(async () => {
  try {
    await brakBolimi();
    await lossBolimi();
  } catch (e) {
    tekshir('kutilmagan istisno', false, String((e && e.stack) || e).slice(0, 300));
  }
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})();
