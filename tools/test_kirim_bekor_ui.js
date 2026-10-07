#!/usr/bin/env node
/**
 * test_kirim_bekor_ui.js — kech107 darvozasi (10-band "Kirim hujjatini bekor qilish"): UI oqimi.
 *
 *   templates/inventory.html — «Xaridlar tarixi» → «📦 Kirim #N» oynasidagi «Kirim hujjatini bekor qilish»:
 *                              `kirimHujjatiniBekorQil` (reja → tasdiq → so'rov), `kirimBekorRejaMatni`, `openPhDrawer`
 *   templates/base.html      — `customConfirm` ga ixtiyoriy UCHINCHI tugma (`altText` → 'alt'), `serverXatoSababi`
 * Server qismi — `tools/test_kirim_bekor.py`. EGASI QARORI (kech107): to'lov bo'lsa "Har safar so'rasin" —
 * «To'lovni ham o'chirish» / «Ta'minotchida avans qolsin» / «Bekor».
 * Funksiyalar HTML dan JONLI o'qiladi, soxta DOM da ishga tushiriladi (asl faylga qarshi ham QULAMAYDI).
 *
 *     node tools/test_kirim_bekor_ui.js [templates_papkasi]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const TPL = process.argv[2] || path.join(ROOT, 'templates');
function oqi(nom) { try { return fs.readFileSync(path.join(TPL, nom), 'utf8'); } catch (e) { return ''; } }
const BASE = oqi('base.html'), INV = oqi('inventory.html');

let OK = 0, FAIL = 0;
const FAILED = [];
function tekshir(label, shart, izoh) {
  let s = false;
  try { s = !!shart; } catch (e) { s = false; }
  if (s) { OK++; console.log(`  ✓ ${label}`); }
  else { FAIL++; FAILED.push(label); console.log(`  ✗ ${label}${izoh !== undefined ? '   — ' + qisqa(izoh) : ''}`); }
}
function bolim(t) { console.log(`\n--- ${t} ---`); }
function qisqa(x) {
  let s; try { s = typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { s = String(x); }
  s = String(s); return s.length > 500 ? s.slice(0, 500) + '…' : s;
}
function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
  if (!m) return null;
  let d = 0;
  const j = src.indexOf('{', m.index + m[0].length);
  if (j < 0) return null;
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(m.index, k + 1); }
  }
  return null;
}
function el(extra) { return Object.assign({ value: '', textContent: '', innerHTML: '', style: {}, dataset: {}, className: '' }, extra || {}); }
function javob(status, data) { return { ok: status >= 200 && status < 300, status, json: async () => JSON.parse(JSON.stringify(data)) }; }

const REJA_TOLOVSIZ = {receipt_id: 12, document_number: 'D-12', materiallar: [
  {purchase_id: 1, inventory_id: 3, nomi: 'Akril', miqdor: 100, birlik: 'kg', joriy_qoldiq: 200, yangi_qoldiq: 100,
   joriy_narx: 2000, yangi_narx: 1000, narx_qaytdi: true},
  {purchase_id: 2, inventory_id: 4, nomi: 'Qum', miqdor: 50, birlik: 'kg', joriy_qoldiq: 20, yangi_qoldiq: -30,
   joriy_narx: 500, yangi_narx: 500, narx_qaytdi: false}],
  xarajatlar: [{id: 5, turi: 'transport_kirim', summa: 20000}], xarajatlar_jami: 20000, tolov: null, manfiy: ['Qum']};
const REJA_TOLOVLI = Object.assign({}, REJA_TOLOVSIZ, {tolov: {summa: 150000, soni: 1}});

function muhit(o) {
  const elementlar = {};
  const sorovlar = [], xabarlar = [], tasdiqlar = [];
  const ctx = {
    console, JSON, String, Number, Math, Promise, Date, RegExp, parseFloat, parseInt, isNaN, Object, Array,
    document: { getElementById: (id) => { if (!elementlar[id]) elementlar[id] = el(); return elementlar[id]; },
                addEventListener() {}, removeEventListener() {} },
    location: { reload() {} }, setTimeout: () => 0,
    fetch: async (url, opts) => { sorovlar.push({url: String(url), method: (opts && opts.method) || 'GET'}); return o.javobFn(String(url), opts); },
    invToast: (t) => xabarlar.push(String(t)),
    customConfirm: async (a, b, c) => { tasdiqlar.push({sarlavha: a, matn: b, opts: c}); return o.tanlov; },
    fmt: (n) => Math.round(n || 0).toLocaleString('ru-RU').replace(/,/g, ' '),
    closePhDrawer() {},
  };
  vm.createContext(ctx);
  const q = [];
  const yoq = [];
  for (const n of ['escapeHtml', 'xatoSababi', 'serverXatoSababi']) { const f = olib(BASE, n); if (f) q.push(f); else yoq.push('base:' + n); }
  for (const n of ['kirimBekorRejaMatni', 'kirimHujjatiniBekorQil']) { const f = olib(INV, n); if (f) q.push(f); else yoq.push(n); }
  q.push('var _kirimBekorYuborilmoqda = false;');
  return { ctx, elementlar, sorovlar, xabarlar, tasdiqlar, kod: q.join('\n'), yoq };
}
async function yurgiz(o) {
  const m = muhit(o);
  let xato = m.yoq.length ? 'topilmadi: ' + m.yoq.join(', ') : null;
  if (!xato) {
    try { vm.runInContext(m.kod, m.ctx); await vm.runInContext("kirimHujjatiniBekorQil('12')", m.ctx); }
    catch (e) { xato = String(e.message || e); }
  }
  return Object.assign(m, { xato });
}
const JAVOB = (reja, bekor) => async (url) => (url.includes('/cancel-plan') ? javob(200, reja)
                                              : (url.includes('/cancel') ? (bekor || javob(200, {bekor_qilindi: true})) : javob(404, {})));

(async () => {
  bolim("K — oqim (reja → tasdiq → so'rov)");
  let m = await yurgiz({javobFn: JAVOB(REJA_TOLOVSIZ), tanlov: true});
  tekshir("K1 to'lovsiz hujjat: reja so'raladi, 2 tugmali tasdiq («Bekor qilish»), POST /cancel tanlovsiz",
          !m.xato && m.sorovlar.map(x => x.method + ' ' + x.url).join(',') ===
          'GET /api/inventory/receipts/12/cancel-plan,POST /api/inventory/receipts/12/cancel'
          && m.tasdiqlar.length === 1 && !(m.tasdiqlar[0].opts || {}).altText && (m.tasdiqlar[0].opts || {}).okText === 'Bekor qilish',
          {xato: m.xato, sorov: m.sorovlar, tasdiq: m.tasdiqlar});
  // `fmt` — ru-RU (minglik ajratgich — NBSP / U+202F) — solishtirish uchun oddiy bo'shliqqa.
  const bosh = (x) => String(x || '').replace(/[\u00a0\u202f]/g, ' ');
  const matn = bosh((m.tasdiqlar[0] || {}).matn);
  tekshir("K2 reja matnida: material, qoldiq 200 → 100, narx 2 000 → 1 000; narx o'zgarmaydigan material; xarajat 20 000; manfiy ogohlantirish",
          matn.includes('Akril') && matn.includes('200 → 100') && matn.includes('2 000 → 1 000') && matn.includes("narx o'zgarmaydi")
          && matn.includes('20 000') && matn.includes('manfiy') && matn.includes('Qum'), matn);
  tekshir("K3 sarlavhada hujjat raqami va hujjat nomeri", ((m.tasdiqlar[0] || {}).sarlavha || '').includes('Kirim #12') &&
          ((m.tasdiqlar[0] || {}).sarlavha || '').includes('D-12'), (m.tasdiqlar[0] || {}).sarlavha);
  for (const [nom, tanlov, url] of [
    ["K4 to'lovli: «To'lovni ham o'chirish» → ?tolov=ochirish", true, 'POST /api/inventory/receipts/12/cancel?tolov=ochirish'],
    ["K5 to'lovli: «Ta'minotchida avans qolsin» → ?tolov=avans", 'alt', 'POST /api/inventory/receipts/12/cancel?tolov=avans'],
    ["K6 to'lovli: «Bekor» — POST YUBORILMAYDI", false, null],
  ]) {
    m = await yurgiz({javobFn: JAVOB(REJA_TOLOVLI), tanlov});
    const t = m.tasdiqlar[0] || {};
    const post = m.sorovlar.filter(x => x.method === 'POST').map(x => x.method + ' ' + x.url);
    tekshir(nom, !m.xato && (t.opts || {}).altText === "Ta'minotchida avans qolsin" && (t.opts || {}).okText === "To'lovni ham o'chirish"
            && bosh(t.matn).includes('150 000') && (url ? (post.length === 1 && post[0] === url) : post.length === 0),
            {xato: m.xato, post, opts: t.opts});
  }
  m = await yurgiz({javobFn: JAVOB(REJA_TOLOVSIZ, javob(400, {detail: 'SABAB-BEKOR'})), tanlov: true});
  tekshir("K7 server rad etsa — sabab ko'rsatiladi (`serverXatoSababi`)", !m.xato && m.xabarlar.some(x => x.includes('SABAB-BEKOR')),
          {xato: m.xato, xabar: m.xabarlar});
  // Obyekt / pydantic ro'yxati ham (eski "d.detail || …" naqshi obyektda "[object Object]" berardi — mutatsiya kmut107u U17).
  const m1 = await yurgiz({javobFn: JAVOB(REJA_TOLOVSIZ, javob(409, {detail: {type: 'x', message: 'OBYEKT-BEKOR'}})), tanlov: true});
  const m2 = await yurgiz({javobFn: JAVOB(REJA_TOLOVSIZ, javob(422, {detail: [{loc: ['query', 'tolov'], msg: 'bad value'}]})), tanlov: true});
  const hamma = m1.xabarlar.concat(m2.xabarlar).join(' | ');
  tekshir("K7b rad sababi obyekt / ro'yxat bo'lsa ham — matn (\"[object Object]\" emas)",
          !m1.xato && !m2.xato && hamma.includes('OBYEKT-BEKOR') && hamma.includes('tolov: bad value') && !hamma.includes('[object Object]'),
          {xato: [m1.xato, m2.xato], xabar: hamma});
  m = await yurgiz({javobFn: async () => javob(404, {detail: 'Kirim hujjati topilmadi'}), tanlov: true});
  tekshir("K8 reja topilmasa — sabab va POST yo'q", !m.xato && m.xabarlar.some(x => x.includes('Kirim hujjati topilmadi'))
          && !m.sorovlar.some(x => x.method === 'POST'), {xato: m.xato, xabar: m.xabarlar});

  bolim("C — base.html `customConfirm`: ixtiyoriy uchinchi tugma");
  const cc = olib(BASE, 'customConfirm');
  function ccMuhit() {
    const els = {};
    ['ccModal', 'ccModalTitle', 'ccModalMessage', 'ccModalOk', 'ccModalCancel', 'ccModalAlt'].forEach(i => { els[i] = el(); });
    const ctx = { Promise, String, document: { getElementById: (i) => els[i] || null, addEventListener() {}, removeEventListener() {} } };
    vm.createContext(ctx);
    return { ctx, els };
  }
  let c1 = null, c2 = null, c3 = null, xato = null;
  try {
    let x = ccMuhit(); vm.runInContext(cc, x.ctx);
    let p = vm.runInContext("customConfirm('S', 'M', {altText: 'Avans', okText: 'Ochir'})", x.ctx);
    const altKorindi = x.els.ccModalAlt.style.display === '' && x.els.ccModalAlt.textContent === 'Avans';
    x.els.ccModalAlt.onclick(); c1 = [await p, altKorindi];
    x = ccMuhit(); vm.runInContext(cc, x.ctx);
    p = vm.runInContext("customConfirm('S', 'M', {altText: 'Avans'})", x.ctx); x.els.ccModalOk.onclick(); c2 = await p;
    x = ccMuhit(); vm.runInContext(cc, x.ctx);
    p = vm.runInContext("customConfirm('Oddiy savol')", x.ctx);
    const yashirin = x.els.ccModalAlt.style.display === 'none';
    x.els.ccModalCancel.onclick(); c3 = [await p, yashirin];
  } catch (e) { xato = String(e.message || e); }
  tekshir("C1 `altText` berilsa — tugma ko'rinadi, bosilsa 'alt'", !xato && c1 && c1[0] === 'alt' && c1[1], {xato, c1});
  tekshir("C2 asosiy tugma — true (o'zgarmagan)", !xato && c2 === true, {xato, c2});
  tekshir("C3 `altText` siz (eski chaqiruvlar) — uchinchi tugma YASHIRIN, «Bekor» — false", !xato && c3 && c3[0] === false && c3[1], {xato, c3});

  bolim('S — statik');
  tekshir("S1 «Kirim #N» oynasida «Kirim hujjatini bekor qilish» tugmasi (`phDrawerBekor`)",
          /id="phDrawerBekor"[\s\S]{0,300}kirimHujjatiniBekorQil\(this\.dataset\.receiptId\)/.test(INV), '');
  tekshir('S2 `openPhDrawer` tugmaga hujjat raqamini qo\'yadi',
          (olib(INV, 'openPhDrawer') || '').includes("document.getElementById('phDrawerBekor').dataset.receiptId = String(receiptId)"), '');
  tekshir("S3 base.html modalida `ccModalAlt` (yashirin)", /<button id="ccModalAlt"[^>]*display:none/.test(BASE), '');

  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach(f => console.log('   - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})().catch(e => { console.log('ICHKI XATO: ' + e); console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL + 1}   jami = ${OK + FAIL + 1}`); process.exit(1); });
