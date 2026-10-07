#!/usr/bin/env node
/**
 * test_ombor_turkum_ui.js — kech105 (K105-2 / K105-3) UI darvozasi.
 *
 *   templates/suppliers.html        — Ta'minotchi → "Xarid qo'shish" oynasi, "🆕 yangi material" rejimi:
 *                                     `apNewItemCategoryChange` / `apYangiPenoplastmi` (YANGI), `apToggleNewItem`,
 *                                     `apResolveItemId`, `apOnItemChange`, `apAddToBasket`, `saveAddPurchase`
 *   templates/supplier_receive.html — "Kirim" sahifasi: `renderInvDropdown` (turkumsiz material guruhi),
 *                                     `onNewItemCategoryChange`, yangi material turkumlari
 *   templates/base.html             — `escapeHtml`
 *
 * NIMA UCHUN (asl kod staging `77ef78a` da O'LCHANGAN — `work/probe105.py`, API tanasi AYNAN suppliers.html niki):
 *   * suppliers.html yangi materialni `{item_name, category, unit, stock_quantity, min_stock}` bilan yaratardi —
 *     "Penoplast" turkumi tanlansa ham `is_penoplast` YO'Q → oddiy material (buyurtma plotnost tanlovida yo'q),
 *     blok hajmi ("1 blok necha m³?") yangi material rejimida ko'rsatilmasdi;
 *   * yangi penoplast "savatga" qo'shilsa — avval material YARATILIB, keyin "savatga qo'shib bo'lmaydi" derdi;
 *   * savat bor-u, joriy qator penoplast bo'lsa — penoplast hajmsiz saqlanardi (hajm faqat yakka xaridda);
 *   * joriy qator to'ldirilgan-u material aniqlanmasa (tanlanmagan / yangi material xatosi) — savat JIMGINA
 *     saqlanib, joriy qator tashlab ketilardi;
 *   * supplier_receive.html yangi material turkumlarida "Boshqa" yo'q, o'rniga "🧱 Bazalt" (koddan olib tashlangan
 *     yo'nalish); turkumsiz material ro'yxatda "Bazalt" guruhiga tushardi; `updateBazaltWrapVisibility` — o'lik.
 *
 * Funksiyalar HTML dan JONLI o'qiladi, soxta muhitda ishga tushiriladi; topilmagan funksiya yoki istisno — yiqilgan
 * tekshiruv (asl fayllarga qarshi ham QULAMAYDI).
 *
 *     node tools/test_ombor_turkum_ui.js [suppliers.html supplier_receive.html base.html]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
function oqi(p) {
  try { return fs.readFileSync(p, 'utf8'); } catch (e) { return ''; }
}
const SUP = oqi(process.argv[2] || path.join(ROOT, 'templates', 'suppliers.html'));
const REC = oqi(process.argv[3] || path.join(ROOT, 'templates', 'supplier_receive.html'));
const BASE = oqi(process.argv[4] || path.join(ROOT, 'templates', 'base.html'));

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
function javob(status, data) {
  return { ok: status >= 200 && status < 300, status, json: async () => JSON.parse(JSON.stringify(data)) };
}
function el(extra) {
  return Object.assign({ value: '', textContent: '', innerHTML: '', style: {}, dataset: {}, disabled: false,
                         appendChild: () => {}, querySelector: () => null, querySelectorAll: () => [] }, extra || {});
}
function muhit(o) {
  const elementlar = o.elementlar || {};
  const sorovlar = [], xabarlar = [];
  const ctx = Object.assign({
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, Array, Object, Error, Set, BigInt,
    document: {
      getElementById: (id) => (Object.prototype.hasOwnProperty.call(elementlar, id) ? elementlar[id] : null),
      createElement: () => el(),
      querySelectorAll: () => [],
      querySelector: () => null,
    },
    fetch: async (url, opts) => {
      let tana = null;
      try { tana = opts && opts.body ? JSON.parse(opts.body) : null; } catch (e) { tana = opts && opts.body; }
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET', tana });
      if (typeof o.javobFn === 'function') return o.javobFn(String(url), opts, tana);
      return javob(599, {});
    },
    showMsg: (t) => { xabarlar.push(String(t)); },
    parseNum: (v) => parseFloat(String(v).replace(/\s/g, '')) || 0,
    narxKorinishi: (n) => String(n),
    buyurtmaJami: (q, p) => ({ jami: Math.round(q * p * 100) / 100 }),
    pulYigindi: (a) => Math.round(a.reduce((s, x) => s + (Number(x) || 0), 0) * 100) / 100,
    apCalc: () => {},
    renderApBasket: () => {},
    openHistory: () => {},
    loadSuppliers: () => {},
    sanitizeToLatin: (t) => t,
    round2: (n) => Math.round(n * 100) / 100,
  }, o.globallar || {});
  vm.createContext(ctx);
  return { ctx, sorovlar, xabarlar };
}
async function ishga(m, kod, chaqiruv) {
  try {
    vm.runInContext(kod, m.ctx);
    return { xato: null, natija: await vm.runInContext(chaqiruv, m.ctx) };
  } catch (e) {
    return { xato: String((e && e.message) || e), natija: undefined };
  }
}

const ESC = olib(BASE, 'escapeHtml') || 'function escapeHtml(s){return String(s);}';
const F = {};
for (const nom of ['apToggleNewItem', 'apYangiPenoplastmi', 'apNewItemCategoryChange', 'apResolveItemId',
                   'apOnItemChange', 'apAddToBasket', 'saveAddPurchase']) {
  F[nom] = olib(SUP, nom);
}
const KOD = Object.values(F).filter(Boolean).join('\n');

function supElementlar(o) {
  const e = {
    'ap-item': el({ value: o.tanlangan || '', style: { display: 'block' } }),
    'ap-newitem-form': el({ style: { display: 'none' } }),
    'ap-newitem-toggle-text': el(),
    'ap-newitem-name': el({ value: o.nom || '' }),
    'ap-newitem-category': el({ value: o.turkum || "Kimyoviy qo'shimchalar" }),
    'ap-newitem-unit': el({ value: o.birlik || 'dona' }),
    'ap-volume-wrap': el({ style: { display: o.hajmKorinadi ? 'block' : 'none' } }),
    'ap-volume': el({ value: o.hajm || '' }),
    'ap-volume-hint': el(),
    'ap-qty': el({ value: o.miqdor || '' }),
    'ap-price': el({ value: o.narx || '' }),
    'ap-total': el(),
    'ap-paid-now': el({ value: '' }),
    'ap-transport-payer': el({ value: 'none' }),
    'ap-transport-cost': el({ value: '' }),
    'ap-save-btn': el(),
    'addPurchaseForm': el({ style: { display: 'block' } }),
  };
  return e;
}
function supMuhit(o) {
  const e = supElementlar(o);
  let keyingiId = 500;
  const m = muhit({
    elementlar: e,
    globallar: { apCreatingNewItem: !!o.yangi, invItems: (o.invItems || []).slice(), apBasket: (o.savat || []).slice(),
                 currentSupplierId: 7 },
    javobFn: async (url, opts, tana) => {
      if (url === '/api/inventory' && opts && opts.method === 'POST') {
        const id = ++keyingiId;
        return javob(200, { id, item_name: tana.item_name, unit: tana.unit, category: tana.category,
                            is_penoplast: !!tana.is_penoplast, volume_per_unit: tana.volume_per_unit || 1.0 });
      }
      if (/\/api\/inventory\/\d+\/purchase$/.test(url)) return javob(200, { paid_now: 0, debt_remains: 0 });
      return javob(599, {});
    },
  });
  return { m, e };
}
const INV_OLDIN = [
  { id: 11, item_name: 'Akril', unit: 'kg', category: "Kimyoviy qo'shimchalar", is_penoplast: false },
  { id: 12, item_name: 'Penoplast 25', unit: 'dona', category: 'Penoplast', is_penoplast: true, volume_per_unit: 1.2 },
];

(async () => {
  // ═══════════════════════════════════════════════════════════
  bolim('0. Funksiyalar topildi (suppliers.html)');
  // ═══════════════════════════════════════════════════════════
  for (const k of Object.keys(F)) tekshir(`0 ${k} topildi`, !!F[k]);

  // ═══════════════════════════════════════════════════════════
  bolim("A. Yangi material rejimi: 'Penoplast' turkumi — blok hajmi maydoni");
  // ═══════════════════════════════════════════════════════════
  {
    const { m, e } = supMuhit({ yangi: true, turkum: 'Penoplast', hajm: '9' });
    const r = await ishga(m, KOD, 'apNewItemCategoryChange()');
    tekshir("A1 'Penoplast' tanlandi — hajm maydoni KO'RINADI, qiymat tozalanadi, izoh 'majburiy' (asl: funksiya yo'q)",
      !r.xato && e['ap-volume-wrap'].style.display === 'block' && e['ap-volume'].value === ''
      && /majburiy/.test(e['ap-volume-hint'].textContent), { xato: r.xato, d: e['ap-volume-wrap'].style.display });
  }
  {
    const { m, e } = supMuhit({ yangi: true, turkum: "Kimyoviy qo'shimchalar", hajmKorinadi: true, hajm: '1.5' });
    const r = await ishga(m, KOD, 'apNewItemCategoryChange()');
    tekshir("A2 boshqa turkum — hajm maydoni YASHIRIN, qiymat tozalanadi", !r.xato
      && e['ap-volume-wrap'].style.display === 'none' && e['ap-volume'].value === '', r.xato);
  }
  {
    const { m, e } = supMuhit({ yangi: false, turkum: 'Penoplast', tanlangan: '11', invItems: INV_OLDIN });
    const r = await ishga(m, KOD, 'apToggleNewItem()');
    tekshir("A3 yangi material rejimiga o'tish — turkum 'Penoplast' tanlangan bo'lsa hajm maydoni ko'rinadi (asl: yashirin)",
      !r.xato && m.ctx.apCreatingNewItem === true && e['ap-volume-wrap'].style.display === 'block',
      { xato: r.xato, d: e['ap-volume-wrap'].style.display });
  }
  {
    const { m, e } = supMuhit({ yangi: true, turkum: 'Penoplast', tanlangan: '12', invItems: INV_OLDIN,
                                hajmKorinadi: true, hajm: '3' });
    const r = await ishga(m, KOD, 'apToggleNewItem()');
    tekshir("A4 ro'yxatga qaytish — tanlangan mavjud penoplast (12) hajmi qaytadi (1.2)", !r.xato
      && m.ctx.apCreatingNewItem === false && e['ap-volume-wrap'].style.display === 'block'
      && String(e['ap-volume'].value) === '1.2', { xato: r.xato, v: e['ap-volume'].value });
  }
  {
    const { m, e } = supMuhit({ yangi: true, turkum: 'Penoplast', tanlangan: '11', invItems: INV_OLDIN,
                                hajmKorinadi: true, hajm: '3' });
    const r = await ishga(m, KOD, 'apToggleNewItem()');
    tekshir("A5 ro'yxatga qaytish — tanlangan oddiy material (11) — hajm maydoni yashiriladi", !r.xato
      && e['ap-volume-wrap'].style.display === 'none' && e['ap-volume'].value === '', r.xato);
  }

  // ═══════════════════════════════════════════════════════════
  bolim('B. apResolveItemId — yangi material tanasi');
  // ═══════════════════════════════════════════════════════════
  {
    const { m, e } = supMuhit({ yangi: true, nom: 'Plotnost 30', turkum: 'Penoplast', hajm: '' });
    const r = await ishga(m, KOD, 'apResolveItemId()');
    tekshir("B1 'Penoplast', hajm KIRITILMAGAN — material YARATILMAYDI (so'rov yo'q), xabar (asl: yaratilardi)",
      !r.xato && r.natija === null && m.sorovlar.length === 0 && m.xabarlar.some(x => /1 blok necha m³/.test(x)),
      { xato: r.xato, s: m.sorovlar, x: m.xabarlar });
  }
  {
    const { m, e } = supMuhit({ yangi: true, nom: 'Plotnost 30', turkum: 'Penoplast', hajm: '1.25' });
    const r = await ishga(m, KOD, 'apResolveItemId()');
    const t = (m.sorovlar[0] || {}).tana || {};
    tekshir("B2 'Penoplast' + hajm 1.25 — tanada is_penoplast=true va volume_per_unit=1.25 (asl: ikkalasi yo'q)",
      !r.xato && m.sorovlar.length === 1 && t.is_penoplast === true && t.volume_per_unit === 1.25
      && t.category === 'Penoplast' && t.item_name === 'Plotnost 30', { xato: r.xato, t });
    const yangi = (m.ctx.invItems || []).find(i => i.item_name === 'Plotnost 30');
    tekshir("B3 ro'yxatga yangi material penoplast + hajm bilan qo'shildi; tanlandi; hajm maydoni 1.25 bilan ko'rinadi",
      !!yangi && yangi.is_penoplast === true && yangi.volume_per_unit === 1.25 && r.natija === yangi.id
      && String(e['ap-item'].value) === String(yangi.id) && e['ap-volume-wrap'].style.display === 'block'
      && String(e['ap-volume'].value) === '1.25', { yangi, v: e['ap-volume'].value, d: e['ap-volume-wrap'].style.display });
  }
  {
    const { m } = supMuhit({ yangi: true, nom: 'Setka', turkum: 'Boshqa', hajm: '' });
    const r = await ishga(m, KOD, 'apResolveItemId()');
    const t = (m.sorovlar[0] || {}).tana || {};
    tekshir("B4 'Boshqa' — tanada is_penoplast=false, volume_per_unit YO'Q (hajm so'ralmaydi)",
      !r.xato && m.sorovlar.length === 1 && t.is_penoplast === false && !('volume_per_unit' in t)
      && t.category === 'Boshqa', { xato: r.xato, t });
  }
  {
    const { m } = supMuhit({ yangi: true, nom: '', turkum: 'Penoplast', hajm: '1' });
    const r = await ishga(m, KOD, 'apResolveItemId()');
    tekshir("B5 nomsiz — so'rov yo'q, 'nomini kiriting' (o'zgarmagan xulq)", !r.xato && r.natija === null
      && m.sorovlar.length === 0 && m.xabarlar.some(x => /nomini kiriting/.test(x)), { xato: r.xato, x: m.xabarlar });
  }

  // ═══════════════════════════════════════════════════════════
  bolim('C. apAddToBasket — yangi penoplast savatga');
  // ═══════════════════════════════════════════════════════════
  {
    const { m } = supMuhit({ yangi: true, nom: 'Plotnost 30', turkum: 'Penoplast', hajm: '1.2', miqdor: '5', narx: '1000' });
    const r = await ishga(m, KOD, 'apAddToBasket()');
    tekshir("C1 yangi 'Penoplast' savatga — material YARATILMAYDI (so'rov yo'q), 'savatga qo'shib bo'lmaydi' (asl: avval yaratilardi)",
      !r.xato && m.sorovlar.length === 0 && m.xabarlar.some(x => /savatga qo'shib bo'lmaydi/.test(x))
      && (m.ctx.apBasket || []).length === 0, { xato: r.xato, s: m.sorovlar, x: m.xabarlar });
  }
  {
    const { m } = supMuhit({ yangi: true, nom: 'Setka', turkum: 'Boshqa', miqdor: '5', narx: '1000' });
    const r = await ishga(m, KOD, 'apAddToBasket()');
    tekshir("C2 yangi oddiy material savatga — yaratiladi va savatga tushadi (o'zgarmagan xulq)",
      !r.xato && m.sorovlar.length === 1 && (m.ctx.apBasket || []).length === 1, { xato: r.xato, s: m.sorovlar });
  }

  // ═══════════════════════════════════════════════════════════
  bolim('D. saveAddPurchase — penoplast va savat; aniqlanmagan joriy qator');
  // ═══════════════════════════════════════════════════════════
  const SAVAT = [{ itemId: 11, itemName: 'Akril', unit: 'kg', qty: 2, price: 500, total: 1000 }];
  {
    const { m } = supMuhit({ yangi: true, nom: 'Plotnost 30', turkum: 'Penoplast', hajm: '1.2', miqdor: '5', narx: '1000',
                             savat: SAVAT, invItems: INV_OLDIN });
    const r = await ishga(m, KOD, 'saveAddPurchase()');
    tekshir("D1 savat bor + joriy qator YANGI penoplast — HECH NARSA yuborilmaydi (material ham yaratilmaydi), xabar",
      !r.xato && m.sorovlar.length === 0 && m.xabarlar.some(x => /alohida saqlang/.test(x)),
      { xato: r.xato, s: m.sorovlar.map(s => s.url), x: m.xabarlar });
  }
  {
    const { m } = supMuhit({ yangi: false, tanlangan: '12', miqdor: '5', narx: '1000', hajm: '1.2', hajmKorinadi: true,
                             savat: SAVAT, invItems: INV_OLDIN });
    const r = await ishga(m, KOD, 'saveAddPurchase()');
    tekshir("D2 savat bor + joriy qator MAVJUD penoplast — yuborilmaydi (asl: penoplast hajmsiz saqlanardi)",
      !r.xato && m.sorovlar.length === 0 && m.xabarlar.some(x => /alohida saqlang/.test(x)),
      { xato: r.xato, s: m.sorovlar.map(s => [s.url, s.tana && s.tana.volume_per_unit]), x: m.xabarlar });
  }
  {
    const { m } = supMuhit({ yangi: false, tanlangan: '', miqdor: '5', narx: '1000', savat: SAVAT, invItems: INV_OLDIN });
    const r = await ishga(m, KOD, 'saveAddPurchase()');
    tekshir("D3 joriy qator to'ldirilgan, material TANLANMAGAN, savat bor — saqlash TO'XTAYDI, 'Materialni tanlang' "
      + "(asl: savat jimgina saqlanardi, joriy qator tashlab ketilardi)",
      !r.xato && m.sorovlar.length === 0 && m.xabarlar.some(x => /Materialni tanlang/.test(x)),
      { xato: r.xato, s: m.sorovlar.map(s => s.url), x: m.xabarlar });
  }
  {
    const { m } = supMuhit({ yangi: true, nom: 'Plotnost 30', turkum: 'Penoplast', hajm: '', miqdor: '5', narx: '1000',
                             savat: [], invItems: INV_OLDIN });
    const r = await ishga(m, KOD, 'saveAddPurchase()');
    tekshir("D4 yakka yangi penoplast, hajm yo'q — material yaratilmaydi, xarid yuborilmaydi, hajm xabari",
      !r.xato && m.sorovlar.length === 0 && m.xabarlar.some(x => /1 blok necha m³/.test(x))
      && !m.xabarlar.some(x => /Kamida bitta material/.test(x)), { xato: r.xato, s: m.sorovlar, x: m.xabarlar });
  }
  {
    const { m } = supMuhit({ yangi: true, nom: 'Plotnost 30', turkum: 'Penoplast', hajm: '1.25', miqdor: '5', narx: '1000',
                             savat: [], invItems: INV_OLDIN });
    const r = await ishga(m, KOD, 'saveAddPurchase()');
    const xarid = m.sorovlar.find(s => /\/purchase$/.test(s.url)) || {};
    tekshir("D5 yakka yangi penoplast + hajm 1.25 — material (is_penoplast) yaratiladi, xarid volume_per_unit=1.25 bilan",
      !r.xato && m.sorovlar.length === 2 && m.sorovlar[0].tana && m.sorovlar[0].tana.is_penoplast === true
      && xarid.tana && xarid.tana.volume_per_unit === 1.25 && xarid.tana.quantity === 5,
      { xato: r.xato, s: m.sorovlar });
  }
  {
    const { m } = supMuhit({ yangi: false, tanlangan: '11', miqdor: '3', narx: '700', savat: SAVAT, invItems: INV_OLDIN });
    const r = await ishga(m, KOD, 'saveAddPurchase()');
    const xaridlar = m.sorovlar.filter(s => /\/purchase$/.test(s.url));
    tekshir("D6 NAZORAT: savat + oddiy material — ikkala qator yuboriladi (o'zgarmagan xulq)",
      !r.xato && xaridlar.length === 2 && xaridlar.every(s => s.tana.volume_per_unit === null),
      { xato: r.xato, s: m.sorovlar.map(s => s.url) });
  }

  // ═══════════════════════════════════════════════════════════
  bolim('E. supplier_receive.html — turkumlar (K105-2)');
  // ═══════════════════════════════════════════════════════════
  const RID = olib(REC, 'renderInvDropdown');
  tekshir('E0 renderInvDropdown topildi', !!RID);
  {
    const sel = el();
    const m = muhit({ elementlar: { 'ap-item': sel },
                      globallar: { invItems: [{ id: 1, item_name: 'Podveska', unit: 'dona', category: null },
                                              { id: 2, item_name: 'Akril', unit: 'kg', category: "Kimyoviy qo'shimchalar" }],
                                   supplierFilterActive: false, supplierFilterIds: null } });
    const r = await ishga(m, ESC + '\n' + (RID || ''), 'renderInvDropdown()');
    tekshir("E1 turkumsiz material 'Boshqa' guruhida (asl: 'Bazalt' guruhida)", !r.xato
      && /<optgroup label="Boshqa">[^]*Podveska/.test(sel.innerHTML) && !/label="Bazalt"/.test(sel.innerHTML),
      { xato: r.xato, h: sel.innerHTML.slice(0, 300) });
  }
  const selM = /<select id="ap-newitem-category"[^>]*>([\s\S]*?)<\/select>/.exec(REC);
  const variantlar = selM ? (selM[1].match(/value="([^"]*)"/g) || []).map(s => s.slice(7, -1)) : [];
  tekshir("E2 Kirim — yangi material turkumlari: Penoplast, Kimyoviy, Mineral, Boshqa ('🧱 Bazalt' YO'Q)",
    JSON.stringify(variantlar) === JSON.stringify(['Penoplast', "Kimyoviy qo'shimchalar", 'Qattiq qotishmalar', 'Boshqa']),
    variantlar);
  const selS = /<select id="ap-newitem-category"[^>]*>([\s\S]*?)<\/select>/.exec(SUP);
  const variantlarS = selS ? (selS[1].match(/value="([^"]*)"/g) || []).map(s => s.slice(7, -1)) : [];
  tekshir("E3 Ta'minotchilar va Kirim sahifasi — turkumlar ro'yxati BIR XIL", variantlarS.length === 4
    && JSON.stringify(variantlarS) === JSON.stringify(variantlar), [variantlarS, variantlar]);
  const ONC = olib(REC, 'onNewItemCategoryChange');
  {
    const wrap = el({ style: { display: 'none' } });
    const m = muhit({ elementlar: { 'ap-newitem-category': el({ value: 'Penoplast' }), 'ap-newitem-peno-wrap': wrap,
                                     'ap-newitem-name': el({ value: 'X' }) } });
    const r = await ishga(m, ONC || '', 'onNewItemCategoryChange()');
    tekshir("E4 Kirim — 'Penoplast' tanlansa penoplast maydonlari ko'rinadi, o'lik funksiyaga murojaat YO'Q",
      !!ONC && !r.xato && wrap.style.display === 'grid' && !/updateBazaltWrapVisibility/.test(REC),
      { xato: r.xato, d: wrap.style.display });
  }

  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) {
    console.log('YIQILGANLAR:');
    for (const f of FAILED) console.log('   - ' + f);
  }
  process.exit(FAIL ? 1 : 0);
})();
