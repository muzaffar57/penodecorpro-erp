#!/usr/bin/env node
/**
 * test_narx_kiritish_ui.js — 118-band (kech94): pul / son kiritishning YAGONA
 * qoidasi 9 sahifada (debts, finance, finished, hodim_panel, inventory, kpi,
 * orders, supplier_receive, suppliers).
 *
 * NIMA UCHUN KERAK
 * ----------------
 * Har sahifada `parseNum` / `formatPriceInput` ning O'Z ta'rifi bor edi (3 xil
 * `parseNum`, 5 xil `formatPriceInput`) va kasr kiritgan foydalanuvchi JIMGINA
 * noto'g'ri summa yuborardi (O'LCHANGAN — kech93 `work/probe118.py`):
 *   • harflab "10.5" → 105, "1234.56" → 123 456 (nuqta darhol yo'qolardi);
 *   • yopishtirilgan "1.000.000" → 1, "1 228 752,75" → 122 875 275;
 *   • "10,5" → 105 (6 sahifa) yoki 10 (orders / finished);
 *   • "-500" → 500 (6 sahifa — ishora jimgina almashardi);
 *   • prompt oynalari: ombor narxi "12 500" → 12 (parseFloat), sotuv narxi
 *     standarti Math.round (OK bosilsa tiyinli narx yaxlitlanardi).
 * Endi 5 funksiya (parseNum, narxMatni, narxniOqi, narxKorinishi,
 * formatPriceInput) HAMMA sahifada matni AYNAN bir xil va qoida bitta.
 *
 * BO'LIMLAR
 * ---------
 *   A — tuzilish: har sahifada 5 funksiya bittadan, matni AYNAN bir xil, blok
 *       kompilyatsiya bo'ladi; formatPriceInput li HAR maydon `type="text"` va
 *       ishlovchida BIRINCHI; shunday maydonni o'qish FAQAT parseNum orqali;
 *       prompt yo'llarida parseFloat / Math.round yo'q.
 *   B — parseNum (umumiy son: o'lcham, miqdor, formatlangan pul matni).
 *   C — narxMatni / formatPriceInput: yopishtirish, harflab yozish, kursor.
 *   D — narxniOqi / narxKorinishi.
 *   E — sahifalarning HAQIQIY funksiyalari: debts quickPayObligation, finished
 *       editPrice, inventory editPrice / editMinStock, suppliers editPurchase,
 *       kpi yangi davr pog'onasi ishlovchisi.
 *   J — jsdom: shablondagi HAQIQIY <input oninput="formatPriceInput(this)...">
 *       ga harflab yozish (hodisa, fokus, kursor).
 *
 * Funksiyalar HTML dan JONLI o'qiladi; topilmagan funksiya / istisno —
 * yiqilgan tekshiruv (asl — tuzatishdan oldingi — faylga qarshi QULAMAYDI).
 *
 * ISHLATISH
 * ---------
 *     node tools/test_narx_kiritish_ui.js
 *     node tools/test_narx_kiritish_ui.js boshqa/templates     (mutatsiya uchun)
 *
 * Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const TDIR = process.argv[2] || path.join(ROOT, 'templates');
const SAHIFALAR = ['debts', 'finance', 'finished', 'hodim_panel', 'inventory', 'kpi',
                   'orders', 'supplier_receive', 'suppliers'];
const FUNKS = ['parseNum', 'narxMatni', 'narxniOqi', 'narxKorinishi', 'formatPriceInput'];
const NBSP = String.fromCharCode(160);
const NNBSP = String.fromCharCode(0x202f);

const SRC = {};
for (const s of SAHIFALAR) {
  try { SRC[s] = fs.readFileSync(path.join(TDIR, s + '.html'), 'utf8'); }
  catch (e) { SRC[s] = ''; }
}

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
function teng(a, b) { return (Number.isNaN(a) && Number.isNaN(b)) || a === b; }

// Funksiyani HTML dan nomi bo'yicha ajratib olish (`async` bilan).
function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src || '');
  if (!m) return null;
  const i = m.index;
  let d = 0;
  const j = src.indexOf('{', i + m[0].length);
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(i, k + 1); }
  }
  return null;
}
function sana(src, nom) {
  const re = new RegExp('function\\s+' + nom + '\\s*\\(', 'g');
  return ((src || '').match(re) || []).length;
}

// Sahifaning 5 yordamchisi yuklangan soxta muhit.
// kech106: sahifa funksiyalari joriy oy / "bugun" ni base.html dagi Toshkent vaqti yordamchilaridan oladi
const TK_FUNKS = ['tkMs', 'tkDate', 'tkSana', 'tkVaqt', 'tkSanaVaqt', 'tkToliq', 'tkISO', 'tkHozir', 'tkKunFarqi'];
const BASE_SRC = (() => { try { return fs.readFileSync(path.join(TDIR, 'base.html'), 'utf8'); } catch (e) { return ''; } })();
function muhit(sahifa, qoshimcha) {
  const ctx = Object.assign({ console }, qoshimcha || {});
  vm.createContext(ctx);
  const xatolar = [];
  for (const f of FUNKS) {
    const t = olib(SRC[sahifa], f);
    if (!t) continue;
    try { vm.runInContext(t, ctx); } catch (e) { xatolar.push(f + ': ' + e.message); }
  }
  for (const f of TK_FUNKS) {
    const t = olib(BASE_SRC, f);
    if (!t) continue;
    try { vm.runInContext(t, ctx); } catch (e) { xatolar.push(f + ': ' + e.message); }
  }
  ctx.__xatolar = xatolar;
  return ctx;
}
function chaqir(ctx, nom, ...args) {
  if (typeof ctx[nom] !== 'function') return { xato: nom + ' yo\'q' };
  try { return { v: ctx[nom](...args) }; } catch (e) { return { xato: e.message }; }
}

// Soxta <input>: qiymat, kursor, setSelectionRange chaqiruvlari, yozuvlar soni.
function soxtaMaydon(qiymat, kursor) {
  const el = {
    _v: String(qiymat), yozuv: 0, tanlov: [],
    selectionStart: kursor == null ? String(qiymat).length : kursor,
    get value() { return this._v; },
    set value(x) { this._v = String(x); this.yozuv++; this.selectionStart = this._v.length; },
    setSelectionRange(a, b) { this.tanlov.push([a, b]); this.selectionStart = a; },
  };
  return el;
}
// Harflab yozish: har belgi kursor joyiga qo'yiladi, keyin formatPriceInput.
function harflab(ctx, matn) {
  const el = soxtaMaydon('', 0);
  ctx.document = { activeElement: el };
  for (const ch of matn) {
    const p = el.selectionStart;
    el._v = el._v.slice(0, p) + ch + el._v.slice(p);
    el.selectionStart = p + 1;
    ctx.formatPriceInput(el);
  }
  return el;
}

// ════════════════════════════════════════════════════════════════
bolim('A. Tuzilish — 5 funksiya, matni AYNAN bir xil, maydonlar va o\'qish');
// ════════════════════════════════════════════════════════════════
const ETALON = {};
for (const f of FUNKS) ETALON[f] = olib(SRC.debts, f);
for (const s of SAHIFALAR) {
  for (const f of FUNKS) {
    const n = sana(SRC[s], f);
    tekshir(`A1 ${s}: ${f} bittadan`, n === 1, `${n} ta`);
  }
}
for (const s of SAHIFALAR) {
  if (s === 'debts') continue;
  for (const f of FUNKS) {
    const t = olib(SRC[s], f);
    tekshir(`A2 ${s}: ${f} matni debts dagi bilan AYNAN`, !!t && !!ETALON[f] && t === ETALON[f]);
  }
}
// A3: 5 funksiya birga kompilyatsiya bo'ladi va yuklanadi; ular joylashgan <script> bloki
// Jinja boshqaruvisiz ({% %}) bo'lsa — butun blok ham (Jinja li bloklarni d94 dagi
// probe_js_sintaksis.py HAQIQIY sahifada tekshiradi).
for (const s of SAHIFALAR) {
  const funks = FUNKS.map((f) => olib(SRC[s], f));
  let xato = funks.every(Boolean) ? null : "funksiya yo'q";
  if (!xato) {
    try { new vm.Script(funks.join('\n'), { filename: s + '.html#118' }); } catch (e) { xato = e.message; }
  }
  if (!xato && muhit(s).__xatolar.length) xato = muhit(s).__xatolar.join('; ');
  const bloklar = (SRC[s].match(/<script(?![^>]*\bsrc=)[^>]*>[\s\S]*?<\/script>/g) || [])
    .filter((b) => /function\s+narxMatni\s*\(/.test(b));
  if (!xato && bloklar.length !== 1) xato = `${bloklar.length} blok`;
  let butun = false;
  if (!xato && !/\{%/.test(bloklar[0])) {
    butun = true;
    const kod = bloklar[0].replace(/^<script[^>]*>/, '').replace(/<\/script>$/, '').replace(/\{\{[\s\S]*?\}\}/g, '0');
    try { new vm.Script(kod, { filename: s + '.html' }); } catch (e) { xato = e.message; }
  }
  tekshir(`A3 ${s}: 118 funksiyalari${butun ? ' va butun skript bloki' : ''} kompilyatsiya bo'ladi`, !xato, xato);
}
// A4: formatPriceInput li HAR <input> — type text (number EMAS) va ishlovchida BIRINCHI.
const PUL_ID = {};
const PUL_KLASS = {};
for (const s of SAHIFALAR) {
  const teglar = (SRC[s].match(/<input\b[^>]*>/g) || []).filter((t) => /formatPriceInput/.test(t));
  const yomon = [];
  PUL_ID[s] = []; PUL_KLASS[s] = [];
  for (const t of teglar) {
    const tur = (/\btype="([^"]+)"/.exec(t) || [])[1] || 'text';
    const ish = (/\boninput="([^"]*)"/.exec(t) || [])[1] || '';
    if (tur !== 'text') yomon.push(`type=${tur}: ${t.slice(0, 60)}`);
    if (!/^\s*formatPriceInput\(this\)/.test(ish)) yomon.push(`birinchi emas: ${ish.slice(0, 70)}`);
    const id = (/\bid="([^"$]+)"/.exec(t) || [])[1];
    if (id) PUL_ID[s].push(id);
    const kl = (/\bclass="([^"$]+)"/.exec(t) || [])[1];
    if (!id && kl) PUL_KLASS[s].push(kl.split(/\s+/)[0]);
  }
  const kutilgan = s === 'inventory' ? 0 : 1;
  tekshir(`A4 ${s}: ${teglar.length} pul maydoni — type="text", formatPriceInput(this) birinchi`,
          yomon.length === 0 && teglar.length >= kutilgan, yomon.join(' | '));
}
// A5: pul maydonini O'QISH faqat parseNum(...) ichida (qiymat berish — o'qish emas).
for (const s of SAHIFALAR) {
  const src = SRC[s];
  const yomon = [];
  let jami = 0;
  const tekshirOqish = (re, nom) => {
    let m;
    while ((m = re.exec(src))) {
      const keyin = src.slice(m.index + m[0].length, m.index + m[0].length + 4);
      if (/^\s*=[^=]/.test(keyin)) continue;                       // qiymat berish
      jami++;
      const oldin = src.slice(Math.max(0, m.index - 40), m.index);
      // qoralama nusxasi (`base_price: document.getElementById(...)?.value || ''`) — xom matn
      // saqlanadi va O'SHA maydonga qaytariladi (o'qish emas).
      if (/[\w$]+\s*:\s*$/.test(oldin)) continue;
      if (!/parseNum\(\s*(?:[\w$]+\??\.)*$/.test(oldin)) {
        const q = src.slice(Math.max(0, m.index - 30), m.index + m[0].length).replace(/\s+/g, ' ');
        yomon.push(`${nom}: …${q}`);
      }
    }
  };
  for (const id of PUL_ID[s]) {
    const e = id.replace(/[.*+?^${}()|[\]\\-]/g, '\\$&');
    tekshirOqish(new RegExp(`document\\.getElementById\\(['"]${e}['"]\\)\\??\\.value`, 'g'), id);
  }
  for (const kl of PUL_KLASS[s]) {
    const e = kl.replace(/[.*+?^${}()|[\]\\-]/g, '\\$&');
    tekshirOqish(new RegExp(`querySelector\\(['"]\\.${e}['"]\\)\\??\\.value`, 'g'), '.' + kl);
  }
  tekshir(`A5 ${s}: pul maydonini o'qish (${jami}) — faqat parseNum orqali`, yomon.length === 0,
          yomon.slice(0, 3).join(' | '));
}
// A6: prompt yo'llari — parseFloat / Math.round yo'q, pul — narxniOqi.
{
  const inv = SRC.inventory;
  const ep = olib(inv, 'editPrice') || '';
  const em = olib(inv, 'editMinStock') || '';
  tekshir('A6 inventory editPrice: parseFloat yo\'q, narxniOqi bor', !!ep && !/parseFloat\(/.test(ep) && /narxniOqi\(/.test(ep));
  tekshir('A6 inventory editMinStock: parseFloat yo\'q, parseNum bor', !!em && !/parseFloat\(/.test(em) && /parseNum\(/.test(em));
  const sp = olib(SRC.suppliers, 'editPurchase') || '';
  tekshir('A6 suppliers editPurchase: parseFloat yo\'q, narxniOqi + narxKorinishi bor',
          !!sp && !/parseFloat\(/.test(sp) && /narxniOqi\(/.test(sp) && /narxKorinishi\(/.test(sp));
  const fe = olib(SRC.finished, 'editPrice') || '';
  tekshir('A6 finished editPrice: Math.round yo\'q, narxniOqi + narxKorinishi bor',
          !!fe && !/Math\.round\(/.test(fe) && /narxniOqi\(/.test(fe) && /narxKorinishi\(/.test(fe));
  const dq = olib(SRC.debts, 'quickPayObligation') || '';
  tekshir('A6 debts quickPayObligation: Math.round yo\'q, narxniOqi + narxKorinishi bor',
          !!dq && !/Math\.round\(/.test(dq) && /narxniOqi\(/.test(dq) && /narxKorinishi\(/.test(dq));
  const sr = SRC.supplier_receive;
  // kech115 (G4-01): savatga qo'shish ikki joydan BITTA yordamchiga (`apQatorniSavatga`) ko'chdi — hajm o'qish ham bitta
  tekshir('A6 supplier_receive ap-volume: parseFloat yo\'q (parseNum — apQatorniSavatga da, bitta joy)',
          !/parseFloat\(\s*document\.getElementById\(['"]ap-volume['"]\)/.test(sr)
          && (sr.match(/parseNum\(\s*document\.getElementById\(['"]ap-volume['"]\)\.value\)/g) || []).length === 1
          && /function apQatorniSavatga\([\s\S]*?parseNum\(document\.getElementById\('ap-volume'\)\.value\)/.test(sr));
}

// ════════════════════════════════════════════════════════════════
bolim('B. parseNum — umumiy son (o\'lcham, miqdor, formatlangan pul matni)');
// ════════════════════════════════════════════════════════════════
const B_HOLLAR = [
  ['150000', 150000], ['1 234', 1234], [`1${NBSP}228${NBSP}752,75`, 1228752.75],
  [`1${NNBSP}000`, 1000], ['10.5', 10.5], ['10,5', 10.5], ['0.125', 0.125], ['5.5', 5.5],
  ['33.3', 33.3], ['1234.56', 1234.56], ['1 234.56', 1234.56], ['1.000.000', 1000000],
  ['1,000,000', 1000000], ['1,234.56', 1234.56], ['1.234,56', 1234.56], ['-500', -500],
  ['-1 500,5', -1500.5], ['12abc', 12], ["1 500 so'm", 1500], ['', 0], [null, 0],
  [undefined, 0], ['abc', 0], [42.5, 42.5], [NaN, 0], [Infinity, 0], ['1e3', 1000],
  ['.5', 0.5], ['10.', 10], ['12.500', 12.5], ['12 500', 12500], ['1e999', 0],
  ['9'.repeat(400) + ',5', 0], ['-,', 0], [`${NBSP}1e3${NNBSP}`, 1000],
];
for (const s of SAHIFALAR) {
  const ctx = muhit(s);
  for (const [kir, kut] of B_HOLLAR) {
    const r = chaqir(ctx, 'parseNum', kir);
    tekshir(`B ${s}: parseNum(${jsn(kir)}) = ${kut}`, !r.xato && teng(r.v, kut), r.xato || jsn(r.v));
  }
}

// ════════════════════════════════════════════════════════════════
bolim('C. narxMatni / formatPriceInput — yopishtirish, harflab, kursor');
// ════════════════════════════════════════════════════════════════
const C_YOPISH = [
  ['150000', '150 000', 150000], ['10.5', '10.5', 10.5], ['10,5', '10,5', 10.5],
  ['0.5', '0.5', 0.5], ['1234.56', '1 234.56', 1234.56], ['1.000.000', '1 000 000', 1000000],
  ['1,000,000', '1 000 000', 1000000], ['1,234.56', '1 234.56', 1234.56],
  ['1.234,56', '1 234,56', 1234.56], ['12.500', '12 500', 12500], ['12,500', '12 500', 12500],
  [`1${NBSP}228${NBSP}752,75`, '1 228 752,75', 1228752.75], ['0.125', '0.12', 0.12],
  ['1234.567', '1 234.56', 1234.56], ['-500', '0', 0], ['1 500-', '0', 0], ['12abc', '12', 12],
  ['abc', '', 0], ['', '', 0], ['007', '7', 7], ['00.5', '0.5', 0.5], ['.5', '0.5', 0.5],
  ['.', '0.', 0], ['10.', '10.', 10], ['12,50', '12,50', 12.5], ['1e3', '13', 13],
  ['99999999999.99', '99 999 999 999.99', 99999999999.99],
];
const C_HARF = [
  ['150000', '150 000', 150000], ['10.5', '10.5', 10.5], ['10,5', '10,5', 10.5],
  ['0.5', '0.5', 0.5], ['1234.56', '1 234.56', 1234.56], ['1.000.000', '1 000 000', 1000000],
  ['1,000,000.50', '1 000 000.50', 1000000.5], ['1.000.000,5', '1 000 000,5', 1000000.5],
  ['12.500', '12 500', 12500], ['1 228 752,75', '1 228 752,75', 1228752.75],
  ['-', '0', 0], ['0.125', '0.12', 0.12], ['100.25', '100.25', 100.25],
];
for (const s of SAHIFALAR) {
  const ctx = muhit(s);
  for (const [kir, kut, son] of C_YOPISH) {
    const el = soxtaMaydon(kir);
    ctx.document = { activeElement: el };
    let xato = null;
    try { ctx.formatPriceInput(el); } catch (e) { xato = e.message; }
    const pn = chaqir(ctx, 'parseNum', el.value);
    tekshir(`C1 ${s}: yopishtirish ${jsn(kir)} → ${jsn(kut)} (${son})`,
            !xato && el.value === kut && !pn.xato && teng(pn.v, son), xato || `${jsn(el.value)} / ${jsn(pn.v)}`);
  }
  for (const [kir, kut, son] of C_HARF) {
    let el = null, xato = null;
    try { el = harflab(ctx, kir); } catch (e) { xato = e.message; }
    const pn = el ? chaqir(ctx, 'parseNum', el.value) : { xato: 'yo\'q' };
    tekshir(`C2 ${s}: harflab ${jsn(kir)} → ${jsn(kut)} (${son})`,
            !xato && el && el.value === kut && !pn.xato && teng(pn.v, son),
            xato || `${jsn(el && el.value)} / ${jsn(pn.v)}`);
  }
  // C3 — kursor: "1 234" ning "1 2|34" joyiga "9" → "12 9|34" (kursor yozilgan raqamdan keyin).
  {
    const el = soxtaMaydon('1 2934', 4);
    ctx.document = { activeElement: el };
    let xato = null;
    try { ctx.formatPriceInput(el); } catch (e) { xato = e.message; }
    const oxirgi = el.tanlov[el.tanlov.length - 1];
    tekshir(`C3 ${s}: o'rtaga yozish — "12 934", kursor 4 da`,
            !xato && el.value === '12 934' && jsn(oxirgi) === '[4,4]', xato || `${jsn(el.value)} ${jsn(el.tanlov)}`);
  }
  // C4 — fokussiz maydon (dasturiy chaqiruv): qiymat me'yorlanadi, kursor tegilmaydi.
  {
    const el = soxtaMaydon('1234.5');
    ctx.document = { activeElement: null };
    let xato = null;
    try { ctx.formatPriceInput(el); } catch (e) { xato = e.message; }
    tekshir(`C4 ${s}: fokussiz — "1 234.5", setSelectionRange chaqirilmadi`,
            !xato && el.value === '1 234.5' && el.tanlov.length === 0, xato || `${jsn(el.value)} ${jsn(el.tanlov)}`);
  }
  // C5 — o'zgarmagan matn qayta YOZILMAYDI (kursor sakramaydi).
  {
    const el = soxtaMaydon('1 234,5', 3);
    ctx.document = { activeElement: el };
    let xato = null;
    try { ctx.formatPriceInput(el); } catch (e) { xato = e.message; }
    tekshir(`C5 ${s}: me'yoriy matn qayta yozilmaydi`, !xato && el.yozuv === 0 && el.value === '1 234,5',
            xato || `yozuv=${el.yozuv} ${jsn(el.value)}`);
  }
  // C6 — number maydoni (selectionStart istisno otadi) qulatmaydi; null / yo'q maydon ham.
  {
    const el = { _v: '1234', get value() { return this._v; }, set value(x) { this._v = String(x); },
                 get selectionStart() { throw new Error('InvalidStateError'); }, setSelectionRange() { throw new Error('x'); } };
    ctx.document = { activeElement: el };
    let xato = null;
    try { ctx.formatPriceInput(el); ctx.formatPriceInput(null); } catch (e) { xato = e.message; }
    tekshir(`C6 ${s}: selectionStart istisnosi / null maydon — qulamaydi`, !xato && el._v === '1 234', xato || jsn(el._v));
  }
}

// ════════════════════════════════════════════════════════════════
bolim('D. narxniOqi (prompt pul matni) / narxKorinishi (prompt standarti)');
// ════════════════════════════════════════════════════════════════
const D_OQI = [
  ['12 500', 12500], ['12500', 12500], ['1.000.000', 1000000], ['12,5', 12.5], ['12.500', 12500],
  ['1 500,5', 1500.5], ['1.234,56', 1234.56], ['0', 0], ['-5', NaN], ['5-', NaN], ['abc', NaN],
  ['', NaN], [null, NaN], ['.', NaN], ['12 500.00', 12500], [' 7 ', 7],
];
const D_KOR = [
  [12500, '12 500'], [12500.5, '12 500.5'], [1228752.7500000002, '1 228 752.75'], [0, '0'],
  [0.1 + 0.2, '0.3'], [100, '100'], [10.1, '10.1'], ['12500.00', '12 500'], [null, '0'], [-5, '0'],
];
for (const s of SAHIFALAR) {
  const ctx = muhit(s);
  for (const [kir, kut] of D_OQI) {
    const r = chaqir(ctx, 'narxniOqi', kir);
    tekshir(`D1 ${s}: narxniOqi(${jsn(kir)}) = ${kut}`, !r.xato && teng(r.v, kut), r.xato || String(r.v));
  }
  for (const [kir, kut] of D_KOR) {
    const r = chaqir(ctx, 'narxKorinishi', kir);
    const qayta = r.xato ? { xato: 'x' } : chaqir(ctx, 'narxniOqi', r.v);
    const son = Math.round((Number(kir) || 0) * 100) / 100;
    tekshir(`D2 ${s}: narxKorinishi(${jsn(kir)}) = ${jsn(kut)} va qayta o'qilsa AYNAN`,
            !r.xato && r.v === kut && !qayta.xato && (son < 0 ? qayta.v === 0 : qayta.v === son),
            r.xato || `${jsn(r.v)} → ${qayta.v}`);
  }
}

// ════════════════════════════════════════════════════════════════
bolim('E. Sahifalarning HAQIQIY funksiyalari (prompt / tahrir / pog\'ona)');
// ════════════════════════════════════════════════════════════════
function javobOk(data) {
  return { ok: true, status: 200, json: async () => data || { status: 'ok' }, text: async () => '' };
}
async function yurgiz(sahifa, funksiyalar, ctxQ, chaqiruv) {
  const ctx = muhit(sahifa, ctxQ);
  for (const nom of funksiyalar) {
    const t = olib(SRC[sahifa], nom);
    if (!t) return { xato: nom + ' topilmadi', ctx };
    try { vm.runInContext(t, ctx); } catch (e) { return { xato: 'sintaksis ' + nom + ': ' + e.message, ctx }; }
  }
  try { await vm.runInContext(chaqiruv, ctx); } catch (e) { return { xato: 'ishlashda: ' + e.message, ctx }; }
  return { xato: null, ctx };
}
function sorovMuhit(promptlar) {
  const q = { sorovlar: [], promptArg: [], alertlar: [], xabarlar: [], toastlar: [], qayta: 0 };
  let pi = 0;
  q.ctx = {
    prompt: (m, d) => { q.promptArg.push(d); return pi < promptlar.length ? promptlar[pi++] : null; },
    customPrompt: async (t, h, d) => { q.promptArg.push(d); return pi < promptlar.length ? promptlar[pi++] : null; },
    // kech118 (B — U-07, MOSLANDI): sahifa xom prompt() / alert() o'rniga dastur oynalarini chaqiradi (base.html
    // `kiritishOyna` — Promise, standart qiymat `o.qiymat`; `xabarOyna`) — soxta muhitda shu testning prompt / alert soxtalariga ulanadi.
    kiritishOyna: async (t, o) => { q.promptArg.push(o && o.qiymat); return pi < promptlar.length ? promptlar[pi++] : null; },
    xabarOyna: async (m) => { q.alertlar.push(String(m)); },
    customConfirm: async () => true,
    alert: (m) => { q.alertlar.push(String(m)); },
    showMsg: (t, tur) => { q.xabarlar.push([String(t), tur]); },
    invToast: (t) => { q.toastlar.push(String(t)); },
    location: { reload() { q.qayta++; } },
    fetch: async (url, opts) => {
      let tana = null;
      try { tana = opts && opts.body ? JSON.parse(opts.body) : null; } catch (e) { tana = 'JSON EMAS'; }
      q.sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET', tana });
      return javobOk();
    },
    serverSababi: async () => 'Xato',
    loadFp() {}, openHistory() {}, loadSuppliers() {}, currentSupplierId: 7,
    fmt: (n) => String(n),
  };
  return q;
}

(async () => {
  // E1 — debts quickPayObligation (majburiyatni tez to'lash).
  const E1 = [
    ['1.500.000', 1500000], ['1 500,5', 1500.5], ['1 228 752.75', 1228752.75], ['12.500', 12500],
    ['-500', null], ['0', null], ['abc', null],
  ];
  for (const [kir, kut] of E1) {
    const q = sorovMuhit([kir]);
    const r = await yurgiz('debts', ['quickPayObligation'], q.ctx,
                           "quickPayObligation('arenda', 'Arenda', 1228752.75, 2026, 9)");
    const t = q.sorovlar[0];
    const shart = kut === null
      ? (!r.xato && q.sorovlar.length === 0 && q.alertlar.length === 1)
      : (!r.xato && q.sorovlar.length === 1 && t.tana && t.tana.amount === kut);
    tekshir(`E1 debts quickPayObligation ${jsn(kir)} → ${kut === null ? 'RAD (alert, so\'rov yo\'q)' : kut}`,
            shart, r.xato || jsn({ s: q.sorovlar, a: q.alertlar }));
  }
  {
    const q = sorovMuhit([null]);
    const r = await yurgiz('debts', ['quickPayObligation'], q.ctx,
                           "quickPayObligation('arenda', 'Arenda', 1228752.75, 2026, 9)");
    tekshir('E1 debts: prompt standarti "1 228 752.75" (yaxlitlanmagan)', !r.xato && q.promptArg[0] === '1 228 752.75',
            r.xato || jsn(q.promptArg));
  }

  // E2 — finished editPrice (tayyor mahsulot sotuv narxi).
  const E2 = [['12 500,5', 12500.5], ['1.000.000', 1000000], ['12.500', 12500], ['abc', null], ['-5', null], ['0', null]];
  for (const [kir, kut] of E2) {
    const q = sorovMuhit([kir]);
    q.ctx.fpItems = [{ id: 5, name: 'TM', unit: 'm', unit_price: 12500.5 }];
    const r = await yurgiz('finished', ['editPrice'], q.ctx, 'editPrice(5)');
    const t = q.sorovlar[0];
    const shart = kut === null
      ? (!r.xato && q.sorovlar.length === 0 && q.xabarlar.some((x) => x[1] === 'error'))
      : (!r.xato && q.sorovlar.length === 1 && t.method === 'PUT' && t.tana && t.tana.unit_price === kut);
    tekshir(`E2 finished editPrice ${jsn(kir)} → ${kut === null ? 'RAD (xabar, so\'rov yo\'q)' : kut}`,
            shart, r.xato || jsn({ s: q.sorovlar, x: q.xabarlar }));
  }
  {
    const q = sorovMuhit([null]);
    q.ctx.fpItems = [{ id: 5, name: 'TM', unit: 'm', unit_price: 12500.5 }];
    const r = await yurgiz('finished', ['editPrice'], q.ctx, 'editPrice(5)');
    tekshir('E2 finished: prompt standarti "12 500.5" (Math.round EMAS)', !r.xato && q.promptArg[0] === '12 500.5',
            r.xato || jsn(q.promptArg));
  }

  // E3 — inventory editPrice / editMinStock (customPrompt).
  const E3 = [['12 500', 12500], ['1.000.000', 1000000], ['12,5', 12.5], ['0', 0], ['12.500', 12500],
              ['-5', null], ['abc', null]];
  for (const [kir, kut] of E3) {
    const q = sorovMuhit([kir]);
    q.ctx.document = { getElementById: () => ({ textContent: '' }) };
    const r = await yurgiz('inventory', ['editPrice'], q.ctx,
                           'var inFlightInvActions = new Set(); editPrice(11, 12500)');
    const t = q.sorovlar[0];
    const shart = kut === null
      ? (!r.xato && q.sorovlar.length === 0 && q.toastlar.length === 1)
      : (!r.xato && q.sorovlar.length === 1 && t.url === '/api/inventory/11/price' && t.tana && t.tana.price_per_unit === kut);
    tekshir(`E3 inventory editPrice ${jsn(kir)} → ${kut === null ? 'RAD (toast, so\'rov yo\'q)' : kut}`,
            shart, r.xato || jsn({ s: q.sorovlar, t: q.toastlar }));
  }
  const E3b = [['1,5', 1.5], ['10 000', 10000], ['2.5', 2.5], ['abc', null], ['', null]];
  for (const [kir, kut] of E3b) {
    const q = sorovMuhit([kir]);
    q.ctx.document = { getElementById: () => ({ textContent: '' }) };
    const r = await yurgiz('inventory', ['editMinStock'], q.ctx,
                           "var inFlightInvActions = new Set(); editMinStock(11, 5, 'kg')");
    const t = q.sorovlar[0];
    const shart = kut === null
      ? (!r.xato && q.sorovlar.length === 0)
      : (!r.xato && q.sorovlar.length === 1 && t.tana && t.tana.min_stock === kut);
    tekshir(`E3 inventory editMinStock ${jsn(kir)} → ${kut === null ? 'so\'rov yo\'q' : kut}`,
            shart, r.xato || jsn(q.sorovlar));
  }

  // E4 — suppliers editPurchase (miqdor umumiy son, narx — pul qoidasi).
  const E4 = [[['1,5', '12 500'], 1.5, 12500], [['3', '1.000.000'], 3, 1000000],
              [['2', '12,5'], 2, 12.5], [['3', '-5'], null, null], [['1 000', '5'], 1000, 5]];
  for (const [promptlar, kq, kn] of E4) {
    const q = sorovMuhit(promptlar);
    const r = await yurgiz('suppliers', ['editPurchase'], q.ctx,
                           'var inFlightPurchaseEdit = new Set(); editPurchase(55, 3, 1000.5, false)');
    const t = q.sorovlar[0];
    const shart = kq === null
      ? (!r.xato && q.sorovlar.length === 0 && q.xabarlar.some((x) => x[1] === 'error'))
      : (!r.xato && q.sorovlar.length === 1 && t.tana && t.tana.quantity === kq && t.tana.price_per_unit === kn);
    tekshir(`E4 suppliers editPurchase ${jsn(promptlar)} → ${kq === null ? 'RAD' : jsn([kq, kn])}`,
            shart, r.xato || jsn({ s: q.sorovlar, x: q.xabarlar }));
    if (promptlar[0] === '1,5') {
      tekshir('E4 suppliers: narx prompt standarti "1 000.5"', !r.xato && q.promptArg[1] === '1 000.5',
              r.xato || jsn(q.promptArg));
    }
  }

  // E5 — kpi yangi davr pog'onasi: ishlovchi avval formatlaydi, keyin o'qiydi (maydon = summa).
  {
    const m = /oninput="([^"]*_newPeriodTiers\[\$\{i\}\]\.amount[^"]*)"/.exec(SRC.kpi);
    tekshir('E5 kpi: pog\'ona summasi ishlovchisi topildi', !!m);
    for (const [kir, kutMatn, kut] of [['12.500', '12 500', 12500], ['1 000 000', '1 000 000', 1000000],
                                        ['1234,5', '1 234,5', 1234.5], ['10.5', '10.5', 10.5]]) {
      let xato = null, el = null, ctx = null;
      if (m) {
        ctx = muhit('kpi', { _newPeriodTiers: [{ name: '', amount: '' }] });
        el = soxtaMaydon(kir);
        ctx.document = { activeElement: el };
        ctx.__el = el;
        try {
          vm.runInContext('(function(){' + m[1].replace(/\$\{i\}/g, '0') + '}).call(__el)', ctx);
        } catch (e) { xato = e.message; }
      }
      const summa = ctx && ctx._newPeriodTiers ? ctx._newPeriodTiers[0].amount : undefined;
      tekshir(`E5 kpi pog'ona ${jsn(kir)} → maydon ${jsn(kutMatn)}, summa ${kut}`,
              !!m && !xato && el.value === kutMatn && summa === kut, xato || jsn([el && el.value, summa]));
    }
  }

  // ════════════════════════════════════════════════════════════════
  bolim('J. jsdom — shablondagi HAQIQIY maydonga harflab yozish (hodisa, fokus, kursor)');
  // ════════════════════════════════════════════════════════════════
  let JSDOM = null, VirtualConsole = null;
  try { ({ JSDOM, VirtualConsole } = require('jsdom')); } catch (e) { JSDOM = null; }
  tekshir('J0 jsdom mavjud', !!JSDOM);
  const J_MAYDON = { debts: 'pay-amount', finance: 'tx-f-amount', finished: 'sell-price', hodim_panel: 'f-amount',
                     kpi: 'adv-amount', orders: 'pf-amount', supplier_receive: 'ap-price', suppliers: 'ap-price',
                     inventory: null };
  for (const s of SAHIFALAR) {
    if (!JSDOM) { tekshir(`J ${s}: jsdom yo'q`, false); continue; }
    let teg = null;
    if (J_MAYDON[s]) {
      const re = new RegExp(`<input\\b[^>]*\\bid="${J_MAYDON[s]}"[^>]*>`);
      teg = (re.exec(SRC[s]) || [])[0] || null;
    } else {
      teg = '<input type="text" id="sintetik" oninput="formatPriceInput(this)">';
    }
    const ish = teg ? ((/\boninput="([^"]*)"/.exec(teg) || [])[1] || '') : '';
    // ishlovchidagi boshqa chaqiruvlar (updateSellTotal, apCalc, ...) — bo'sh stub.
    const stublar = (ish.match(/([A-Za-z_$][\w$]*)\s*\(/g) || [])
      .map((x) => x.replace(/\s*\($/, '')).filter((n) => n !== 'formatPriceInput');
    const funks = FUNKS.map((f) => olib(SRC[s], f)).filter(Boolean).join('\n');
    let natija = null, xato = null;
    const domXato = [];
    try {
      const vc = new VirtualConsole();
      vc.on('jsdomError', (e) => { domXato.push(String(e && e.message || e)); });
      const dom = new JSDOM(`<!doctype html><body>${teg || ''}<script>${funks}\n` +
        stublar.map((n) => `function ${n}(){}`).join('\n') + '</script></body>',
        { runScripts: 'dangerously', virtualConsole: vc });
      const w = dom.window;
      const el = w.document.querySelector('input');
      const yoz = (matn) => {
        el.focus();
        for (const ch of matn) {
          const p = el.selectionStart;
          el.value = el.value.slice(0, p) + ch + el.value.slice(el.selectionEnd);
          el.setSelectionRange(p + 1, p + 1);
          el.dispatchEvent(new w.Event('input', { bubbles: true }));
        }
      };
      yoz('1234.5');
      const a = [el.value, el.selectionStart];
      el.value = ''; yoz('1.000.000');
      const b = [el.value, el.selectionStart];
      // o'rtaga yozish: "150 000" → kursor "15|0 000" ga, "9" → "1 590 000", kursor "1 59|0 000"
      el.value = '150 000'; el.setSelectionRange(2, 2); yoz('9');
      const c = [el.value, el.selectionStart];
      el.value = ''; yoz('-');
      const d = el.value;
      natija = { a, b, c, d, pn: w.parseNum ? w.parseNum(a[0]) : null };
      w.close();
    } catch (e) { xato = e.message; }
    if (!xato && domXato.length) xato = 'sahifa xatosi: ' + domXato[0].slice(0, 120) + ` (${domXato.length} ta)`;
    tekshir(`J ${s}: ${J_MAYDON[s] || 'sintetik'} — harflab "1234.5" → "1 234.5" (kursor oxirda), parseNum 1234.5`,
            !xato && natija && natija.a[0] === '1 234.5' && natija.a[1] === 7 && natija.pn === 1234.5,
            xato || jsn(natija));
    tekshir(`J ${s}: harflab "1.000.000" → "1 000 000"`, !xato && natija && natija.b[0] === '1 000 000',
            xato || jsn(natija && natija.b));
    tekshir(`J ${s}: o'rtaga "9" → "1 590 000", kursor 4 da`,
            !xato && natija && natija.c[0] === '1 590 000' && natija.c[1] === 4, xato || jsn(natija && natija.c));
    tekshir(`J ${s}: "-" → "0" (manfiy pul YO'Q)`, !xato && natija && natija.d === '0', xato || jsn(natija && natija.d));
  }

  console.log('\n' + '='.repeat(66));
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.slice(0, 80).forEach((f) => console.log('  - ' + f)); }
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  process.exit(FAIL === 0 ? 0 : 1);
})().catch((e) => {
  console.log('KUTILMAGAN ISTISNO: ' + (e && e.stack || e));
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL + 1}   jami = ${OK + FAIL + 1}`);
  process.exit(1);
});
