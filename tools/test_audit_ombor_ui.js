#!/usr/bin/env node
/**
 * test_audit_ombor_ui.js — kech142 (zip 170): AUDIT — OMBOR / MRP topilmalarining SAHIFADAGI qismi.
 *
 *   templates/finished.html     — A-O01: «Sotish» oynasi buyurtmaga BAND qismni sotishga ruxsat bermaydi (`openSellModal`,
 *                                 `submitSell`), qatorda to'liq band partiya «Sotish» yopiq, savatcha belgisi sotsa bo'ladigan
 *                                 miqdor bilan (`rowHtml`), guruh «Sotish» — sotsa bo'ladigani bo'lsa (`fpGuruhXulosa`,
 *                                 `guruhHtml`), guruhdan bitta partiya — band bilan (`fpGuruhSotish`)
 *   templates/_brak_oyna.html   — A-O08: «Brak» oynasida band qism ko'rinadi, brak band qismga tegsa oldindan so'raladi, server
 *                                 «band kamaydi» desa — xabarda (`openLossModal`, `brakSaqlash`)
 *   templates/supplier_receive.html, suppliers.html — A-O09: «yangi material» nomi band (409) — mavjud material tanlanadi,
 *                                 yangisi yaratilmaydi; boshqa xato — server SABABI bilan (`apResolveItemId`)
 *   templates/inventory.html    — EGASI QARORI «O'chirishdan oldin 0 bo'lsin»: qoldig'i bor material — so'rovsiz, sabab bilan
 *                                 (`deleteItem`)
 *   templates/production.html   — A-O03: yakunlangan / bekor qilingan ishlab chiqarishda «bekor qilish» tugmasi yo'q (`poOyna`);
 *                                 «Boshlash» / «Yakunlash» rad etilib, shu orada holat o'zgargan bo'lsa — oyna yopiladi; A-O10 a
 *                                 matni (o'chirilgan material tannarxga KIRADI)
 *
 * NIMA UCHUN KERAK: server qoidalari (tools/test_audit_ombor*.py, test_audit_mrp.py) — sahifa ularni oldindan ko'rsatishi, band
 *   mahsulotni sotish / brak qilishda foydalanuvchini adashtirmasligi kerak (asl zip 169 da sotish oynasi «Omborda: 4», max 4 —
 *   hammasi band bo'lsa ham; `work/audit/tasdiq/ombor/p_o01.py --brauzer`).
 * QANDAY ISHLAYDI: funksiyalar HTML dan JONLI o'qiladi (Jinja teglari — birinchi tarmoq), soxta DOM / fetch muhitida ishga
 *   tushiriladi. Topilmagan funksiya yoki istisno — yiqilgan tekshiruv (asl faylga qarshi ham QULAMAYDI).
 * ISHLATISH: node tools/test_audit_ombor_ui.js
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
const OYNA = oqi('_brak_oyna.html');
const RCV = oqi('supplier_receive.html');
const SUP = oqi('suppliers.html');
const INV = oqi('inventory.html');
const PROD = oqi('production.html');

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
  return s.length > 500 ? s.slice(0, 500) + '…' : s;
}
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
function klassRoyxat() {
  const s = new Set();
  return { _s: s, toggle(k, v) { if (v === undefined ? !s.has(k) : v) s.add(k); else s.delete(k); },
    add(k) { s.add(k); }, remove(k) { s.delete(k); }, contains(k) { return s.has(k); } };
}
function element(id, qiymat) {
  const el = { id, value: qiymat === undefined ? '' : qiymat, checked: false, textContent: '', innerHTML: '', max: '',
    style: { display: 'none' }, dataset: {}, disabled: false, classList: klassRoyxat(), _fokus: 0, _bola: [] };
  el.focus = () => { el._fokus++; };
  el.appendChild = (x) => { el._bola.push(x); };
  el.querySelector = () => null;
  el.querySelectorAll = () => [];
  el.setAttribute = () => {};
  return el;
}
function javob(status, data) {
  const j = { ok: status >= 200 && status < 300, status, json: async () => JSON.parse(JSON.stringify(data)) };
  j.clone = () => javob(status, data);
  return j;
}
// Umumiy muhit: `idlar` — sahifadagi elementlar; `globallar` — sahifa yordamchilari soxtasi; `javoblar` — fetch navbati
function muhit(idlar, globallar, javoblar) {
  const el = {};
  for (const id of idlar) el[id] = element(id);
  const sorovlar = [], xabarlar = [], chaqiruvlar = [];
  const navbat = (javoblar || []).slice();
  const ctx = Object.assign({
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, isFinite, Array, Object, Error, RegExp, Set, Map,
    Date, Intl,
    document: {
      getElementById: (id) => (Object.prototype.hasOwnProperty.call(el, id) ? el[id] : null),
      createElement: () => element('yangi'),
      querySelectorAll: () => [],
      querySelector: () => null,
      addEventListener: () => {},
    },
    fetch: async (url, f) => {
      let tana = null;
      try { tana = f && f.body ? JSON.parse(f.body) : null; } catch (e) { tana = 'JSON EMAS'; }
      sorovlar.push({ url: String(url), method: (f && f.method) || 'GET', tana });
      const j = navbat.length ? navbat.shift() : { status: 200, data: { success: true } };
      return javob(j.status, j.data);
    },
    showMsg: (t, tur) => { xabarlar.push({ t: String(t), tur }); },
    location: { reload: () => { chaqiruvlar.push('reload'); } },
    setTimeout: () => 0,
    window: { open: (u) => chaqiruvlar.push('open:' + u) },
  }, globallar || {});
  vm.createContext(ctx);
  return { ctx, el, sorovlar, xabarlar, chaqiruvlar };
}
async function ishga(m, kod, chaqiruv) {
  try {
    if (kod) vm.runInContext(kod, m.ctx);
    const natija = await vm.runInContext(chaqiruv, m.ctx);
    return { xato: null, natija };
  } catch (e) {
    return { xato: String((e && e.message) || e), natija: undefined };
  }
}

const BASE_YORDAM = funks(BASE, ['escapeHtml', 'sonKor', 'jsAttrEscape', 'matnRangi', 'tkMs', 'tkDate', 'tkSana', 'birlikKor']);

// ══════════════════════════════════════════════════════════════
async function sotishBolimi() {
  bolim('finished.html — A-O01: band qism sotilmaydi');
  const fy = funks(FINISHED, ['unitLabel', 'fpMiqdor', 'fmt', 'parseNum', 'openSellModal', 'submitSell', 'updateSellTotal']);
  tekshir('F0 funksiyalar topildi (openSellModal, submitSell ...)', !fy.yoq.length && !BASE_YORDAM.yoq.length,
    qisqa(fy.yoq.concat(BASE_YORDAM.yoq)));
  const IDS = ['sell-modal-sub', 'sell-stock-info', 'sell-qty', 'sell-price', 'sell-buyer', 'sell-master', 'sell-paymethod',
    'sell-total-box', 'sellModal'];
  let m = muhit(IDS, { _sellData: null });
  let r = await ishga(m, BASE_YORDAM.kod + '\n' + fy.kod + '\nvar _sellData = null;', "openSellModal(7, 'X', 10, 'm²', 0, 10)");
  const info1 = bosh(m.el['sell-stock-info'].textContent);
  tekshir("F1 to'liq band (10 / band 10): oynada «band: 10 (buyurtma uchun) · sotsa bo'ladi: 0», miqdor maksimumi 0",
    !r.xato && info1.includes('band: 10') && info1.includes("sotsa bo'ladi: 0") && String(m.el['sell-qty'].max) === '0',
    r.xato || qisqa([info1, m.el['sell-qty'].max]));
  m = muhit(IDS, {});
  r = await ishga(m, BASE_YORDAM.kod + '\n' + fy.kod + '\nvar _sellData = null;', "openSellModal(7, 'FI Vaza', 8, 'dona', 50000)");
  tekshir("F2 bandsiz (eski 5 argument) — matn avvalgidek «Omborda: 8 dona», maksimum 8",
    !r.xato && bosh(m.el['sell-stock-info'].textContent) === 'Omborda: 8 dona' && String(m.el['sell-qty'].max) === '8',
    r.xato || qisqa([m.el['sell-stock-info'].textContent, m.el['sell-qty'].max]));
  m = muhit(IDS, {});
  r = await ishga(m, BASE_YORDAM.kod + '\n' + fy.kod + '\nvar _sellData = null;', "openSellModal(7, 'X', 10, 'm²', 0, 6)");
  tekshir("F2b qisman band (10 / band 6) — maksimum 4, matnda «sotsa bo'ladi: 4»",
    !r.xato && String(m.el['sell-qty'].max) === '4' && bosh(m.el['sell-stock-info'].textContent).includes("sotsa bo'ladi: 4"),
    r.xato || qisqa(m.el['sell-stock-info'].textContent));
  m.el['sell-qty'].value = '5';
  m.el['sell-price'].value = '1000';
  m.el['sell-master'].value = 'none';
  r = await ishga(m, '', 'submitSell()');
  tekshir("F3 sotsa bo'ladigandan ko'p (5 > 4) — so'rov YO'Q, xabarda band va «Bandni bekor qilish»",
    !r.xato && m.sorovlar.length === 0 && m.xabarlar.some((x) => x.tur === 'error' && x.t.includes('band')
      && x.t.includes('Bandni bekor qilish')), r.xato || qisqa(m.xabarlar));
  m.el['sell-qty'].value = '4';
  r = await ishga(m, '', 'submitSell()');
  tekshir("F3b sotsa bo'ladigan 4 — bitta POST /api/finished/sell", !r.xato && m.sorovlar.length === 1
    && m.sorovlar[0].url === '/api/finished/sell' && m.sorovlar[0].tana.quantity === 4, r.xato || qisqa(m.sorovlar));
  m = muhit(IDS, {});
  r = await ishga(m, BASE_YORDAM.kod + '\n' + fy.kod + "\nvar _sellData = {id: 3, quantity: 10, unit: 'm', name: 'Eski'};", '0');
  m.el['sell-qty'].value = '10';
  m.el['sell-price'].value = '1000';
  m.el['sell-master'].value = 'none';
  r = await ishga(m, '', 'submitSell()');
  tekshir("F4 eski `_sellData` (band kaliti yo'q) — avvalgidek butun qoldiq, bitta POST", !r.xato && m.sorovlar.length === 1,
    r.xato || qisqa([m.sorovlar, m.xabarlar]));

  // rowHtml / guruhHtml
  const FIN = funks(FINISHED, ['unitLabel', 'fpMiqdor', 'fpWidth2', 'fpMrpmi', 'fpSku', 'fmt', 'fpJarayondami', 'fpKamChegara',
    'fpPartiyaNomi', 'fpSavatNomi', 'fpGuruhKaliti', 'fpGuruhXulosa', 'fpGuruhla', 'fpGuruhKammi', 'rowHtml', 'guruhHtml']);
  tekshir('F5 rowHtml / guruhHtml / fpGuruhXulosa topildi (yangi umumiy yordamchisiz)', !FIN.yoq.length, qisqa(FIN.yoq));
  const fp = (qosh) => JSON.stringify(Object.assign({ id: 7, name: 'Karniz', source: 'produced', category: 'profil', quantity: 8,
    unit: 'metr', unit_price: 1000, cost_price: 4000, total_value: 4000, ombor_qiymati: 4000, is_coated: true,
    production_status: 'ready', kam_chegara: null, created_at: '2026-10-01T05:00:00', reserved_quantity: 0 }, qosh || {}));
  m = muhit([], { TM_TAHRIR: true, fpOchiq: new Set() });
  r = await ishga(m, BASE_YORDAM.kod + '\n' + FIN.kod, `rowHtml(${fp({ quantity: 10, reserved_quantity: 10 })}, false)`);
  const h1 = String(r.natija || '');
  const sotTugma = (h) => { const i = h.indexOf('fp-amal fp-amal-sotish'); return i < 0 ? '' : h.slice(i, h.indexOf('</button>', i)); };
  const chek = (h) => { const i = h.indexOf('fp-batch-check'); return i < 0 ? '' : h.slice(i, h.indexOf('>', i)); };
  tekshir("F6 to'liq band partiya: «Sotish» tugmasi YOPIQ (sababi title da), savatcha belgisi 0 va yopiq",
    !r.xato && / disabled /.test(sotTugma(h1) + ' ') && sotTugma(h1).includes('Hammasi buyurtmaga band') && chek(h1).includes('data-qty="0"')
    && chek(h1).includes('disabled'), r.xato || qisqa([sotTugma(h1), chek(h1)]));
  r = await ishga(m, '', `rowHtml(${fp({ quantity: 10, reserved_quantity: 6 })}, false)`);
  const h2 = String(r.natija || '');
  tekshir("F7 qisman band (10 / 6): «Sotish» ochiq, oynaga band 6 uzatiladi, savatcha belgisi 4",
    !r.xato && sotTugma(h2).includes("openSellModal(7, 'Karniz', 10, 'metr', 1000, 6)") && !/disabled/.test(sotTugma(h2))
    && chek(h2).includes('data-qty="4"') && !chek(h2).includes('disabled'), r.xato || qisqa([sotTugma(h2), chek(h2)]));
  tekshir("F7b qisman band — «Brak» oynasiga ham band 6 uzatiladi", h2.includes("'profil', 6)"), qisqa(h2.slice(h2.indexOf('openLossModal'), h2.indexOf('openLossModal') + 120)));
  r = await ishga(m, '', `rowHtml(${fp()}, false)`);
  const h3 = String(r.natija || '');
  tekshir("F8 bandsiz qator — avvalgidek: 5 argumentli oyna, savatcha 8, yopiq emas",
    !r.xato && sotTugma(h3).includes("openSellModal(7, 'Karniz', 8, 'metr', 1000)\"") && chek(h3).includes('data-qty="8"')
    && !chek(h3).includes('disabled') && !/disabled/.test(sotTugma(h3)), r.xato || qisqa([sotTugma(h3), chek(h3)]));
  r = await ishga(m, '', `JSON.stringify([fpGuruhla([${fp({ id: 1, quantity: 10, reserved_quantity: 10 })},
    ${fp({ id: 2, quantity: 5, reserved_quantity: 2 })}])[0].sotsa])`);
  tekshir("F9 guruh xulosasida sotsa bo'ladigani = Σ (qoldiq − band) = 3", !r.xato && r.natija === '[3]', r.xato || qisqa(r.natija));
  r = await ishga(m, '', `guruhHtml(fpGuruhla([${fp({ id: 1, quantity: 10, reserved_quantity: 10 })},
    ${fp({ id: 2, quantity: 5, reserved_quantity: 5 })}])[0])`);
  tekshir("F10 guruhda hammasi band — guruh «Sotish» tugmasi YO'Q", !r.xato && !String(r.natija).includes('fpGuruhSotish'),
    r.xato || qisqa(r.natija));
  r = await ishga(m, '', `guruhHtml(fpGuruhla([${fp({ id: 1, quantity: 10, reserved_quantity: 10 })},
    ${fp({ id: 2, quantity: 5, reserved_quantity: 2 })}])[0])`);
  tekshir("F10b guruhda sotsa bo'ladigani bor — guruh «Sotish» bor", !r.xato && String(r.natija).includes('fpGuruhSotish(this)'),
    r.xato || qisqa(r.natija));

  // fpGuruhSotish — bitta partiya: band bilan oynaga
  const kg = funks(FINISHED, ['fpGuruhSotish']);
  const chk = (id, qty) => { const e = element('c' + id); e.dataset = { id: String(id), qty: String(qty) }; return e; };
  const guruhDom = (cheklar) => ({ closest: () => ({ querySelectorAll: (sel) => (sel === '.fp-guruh-ichi .fp-batch-check' ? cheklar : []) }) });
  const arglar = [];
  m = muhit([], { fpItems: [{ id: 2, name: 'Karniz', quantity: 10, unit: 'metr', unit_price: 1000, reserved_quantity: 6 }],
    openSellModal: (...a) => { arglar.push(a); }, onBatchCheckChange() {}, openBatchSellModal() {} });
  vm.runInContext('var GD = null;', m.ctx);
  m.ctx.GD = guruhDom([chk(1, 0), chk(2, 4)]);
  r = await ishga(m, kg.kod, 'fpGuruhSotish(GD)');
  tekshir("F11 guruhdan bitta sotsa bo'ladigan partiya — oynaga band (6) ham uzatiladi",
    !r.xato && arglar.length === 1 && arglar[0][5] === 6 && arglar[0][2] === 10, r.xato || qisqa(arglar));
}

// ══════════════════════════════════════════════════════════════
const BRAK_IDLAR = ['brakModal', 'brak-project', 'brakList', 'brak-notes', 'brak-stage', 'brak-worker', 'loss-qty', 'brak-cause',
  'brak-fp', 'brak-fp-tanlash', 'brak-fp-nomi', 'brak-manba-buyurtma', 'brak-manba-ombor', 'brak-manba-ishlab',
  'brak-panel-project', 'brak-tm-panel', 'brak-umumiy', 'brak-sarlavha-sub', 'brak-error', 'brak-save-btn', 'loss-info-stock',
  'loss-info-production', 'loss-qty-label', 'loss-stock-info'];
const YOQ_A = ['brak-project', 'brakList', 'brak-panel-project', 'brak-manba-buyurtma'];

function brakOyna(javoblar, tasdiq) {
  const idlar = BRAK_IDLAR.filter((x) => !YOQ_A.includes(x));
  const tasdiqlar = [];
  const m = muhit(idlar, {
    customConfirm: async (...a) => { tasdiqlar.push(a); return tasdiq; },
    xatoSababi: (r, s) => String((r && (r.message || (r.detail && (r.detail.message || r.detail)))) || s || 'Xato'),
  }, javoblar);
  const radiolar = ['ombor', 'ishlab'].map((x) => Object.assign(element('r-' + x, x), { name: 'brak-manba' }));
  m.ctx.document.querySelectorAll = (sel) => {
    if (sel === 'input[name="brak-manba"]') return radiolar;
    if (sel === '.brk-manba') return ['ombor', 'ishlab'].map((x) => m.el['brak-manba-' + x]).filter(Boolean);
    return [];
  };
  m.tasdiqlar = tasdiqlar;
  vm.runInContext(BASE_YORDAM.kod, m.ctx);
  const sk = /<script>([\s\S]*?)<\/script>/.exec(OYNA);
  try { vm.runInContext(jinja(sk ? sk[1] : ''), m.ctx); } catch (e) { m.kodXato = String(e && e.message || e); }
  return m;
}

async function brakBolimi() {
  bolim('_brak_oyna.html — A-O08: brak band qismga tegsa oldindan so\'raladi');
  let m = brakOyna([], true);
  tekshir('B0 oyna skripti yuklandi', !m.kodXato, m.kodXato);
  let r = await ishga(m, '', "openLossModal(7, 'Travertin', 10, 'm²', 'dynamic_bom', 4)");
  tekshir("B1 band bilan ochildi — «Omborda: 10 m² · shundan band: 4 (buyurtma uchun)»",
    !r.xato && bosh(m.el['loss-stock-info'].textContent).includes('shundan band: 4'), r.xato || qisqa(m.el['loss-stock-info'].textContent));
  m = brakOyna([], false);
  await ishga(m, '', "openLossModal(7, 'Travertin', 10, 'm²', 'dynamic_bom', 4)");
  m.el['loss-qty'].value = '8';
  m.el['brak-cause'].value = 'boshqa';
  r = await ishga(m, '', 'brakSaqlash()');
  tekshir("B2 brak 8 (bo'sh qism 6) — AVVAL so'raladi (2 band qismdan), «Yo'q» — so'rov yuborilmadi",
    !r.xato && m.tasdiqlar.length === 1 && bosh(m.tasdiqlar[0][1] || '').includes('2') && m.sorovlar.length === 0,
    r.xato || qisqa([m.tasdiqlar, m.sorovlar]));
  m = brakOyna([{ status: 200, data: { success: true, cost_amount: 1000, band_kamaydi: 2 } }], true);
  await ishga(m, '', "openLossModal(7, 'Travertin', 10, 'm²', 'dynamic_bom', 4)");
  m.el['loss-qty'].value = '8';
  m.el['brak-cause'].value = 'boshqa';
  r = await ishga(m, '', 'brakSaqlash()');
  tekshir("B3 «Ha» — POST /api/finished/loss; javobda band kamaygani — xabarda ogohlantirish",
    !r.xato && m.tasdiqlar.length === 1 && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/finished/loss'
    && m.xabarlar.some((x) => x.tur === 'success' && x.t.includes('band') && x.t.includes('2')), r.xato || qisqa([m.sorovlar, m.xabarlar]));
  m = brakOyna([], true);
  await ishga(m, '', "openLossModal(7, 'Travertin', 10, 'm²', 'dynamic_bom', 4)");
  m.el['loss-qty'].value = '6';
  m.el['brak-cause'].value = 'boshqa';
  r = await ishga(m, '', 'brakSaqlash()');
  tekshir("B4 brak bo'sh qism ichida (6) — so'ralmaydi, darhol yuboriladi", !r.xato && m.tasdiqlar.length === 0 && m.sorovlar.length === 1,
    r.xato || qisqa([m.tasdiqlar, m.sorovlar]));
  m = brakOyna([], true);
  await ishga(m, '', "openLossModal(7, 'Karniz', 3, 'm', 'Profil')");
  tekshir("B5 bandsiz (eski 5 argument) — matn avvalgidek «Omborda: 3 m»", m.el['loss-stock-info'].textContent === 'Omborda: 3 m',
    qisqa(m.el['loss-stock-info'].textContent));
}

// ══════════════════════════════════════════════════════════════
async function materialBolimi(nomi, SRC, saqlashTugma) {
  bolim(`${nomi} — A-O09: «yangi material» nomi band — mavjud material tanlanadi`);
  const F = funks(SRC, ['apResolveItemId']);
  tekshir(`M0 ${nomi}: apResolveItemId topildi`, !F.yoq.length, qisqa(F.yoq));
  const IDS = ['ap-item', 'ap-newitem-name', 'ap-newitem-category', 'ap-newitem-unit', 'ap-newitem-volume', 'ap-newitem-default',
    'ap-volume'];
  function tayyor(javoblar, inv) {
    const chaq = [];
    const m = muhit(IDS, {
      apCreatingNewItem: true, invItems: inv || [{ id: 5, item_name: 'Akril', unit: 'kg' }],
      apToggleNewItem: () => chaq.push('toggle'), apOnItemChange: () => chaq.push('change'),
      sanitizeToLatin: (t) => t, parseNum: (v) => parseFloat(String(v).replace(/\s/g, '')) || 0,
      amalSababi: async (res) => { const j = await res.json(); const d = j.detail; return String((d && d.message) || d || 'sabab yo\'q'); },
    }, javoblar);
    m.chaq = chaq;
    m.el['ap-newitem-name'].value = 'Akril';
    m.el['ap-newitem-category'].value = 'Kimyo';
    m.el['ap-newitem-unit'].value = 'litr';
    return m;
  }
  const band = { type: 'material_nomi_band', id: 5, item_name: 'Akril', unit: 'kg',
    message: '«Akril» nomli material omborda allaqachon bor (birligi: kg) — ro\'yxatdan tanlang' };
  let m = tayyor([{ status: 409, data: { detail: band } }]);
  let r = await ishga(m, 'var apCreatingNewItem = true;\n' + F.kod, 'apResolveItemId()');
  tekshir(`M1 ${nomi}: 409 «material_nomi_band» — mavjud material (id 5) tanlandi, yangisi qo'shilmadi, natija null, `
    + `xabarda birlik va «${saqlashTugma}»`,
    !r.xato && r.natija === null && m.el['ap-item'].value === '5' && m.el['ap-item']._bola.length === 0
    && m.chaq.join(',') === 'toggle,change' && m.xabarlar.some((x) => x.t.includes('birligi: kg') && x.t.includes(saqlashTugma)),
    r.xato || qisqa([r.natija, m.el['ap-item'].value, m.chaq, m.xabarlar]));
  m = tayyor([{ status: 409, data: { detail: band } }], [{ id: 9, item_name: 'Boshqa', unit: 'kg' }]);
  r = await ishga(m, 'var apCreatingNewItem = true;\n' + F.kod, 'apResolveItemId()');
  tekshir(`M2 ${nomi}: 409, lekin material sahifa ro'yxatida yo'q — xato xabari SERVER SABABI bilan ([object Object] emas)`,
    !r.xato && r.natija === null && m.xabarlar.some((x) => x.tur === 'error' && x.t.includes("allaqachon bor")
      && !x.t.includes('[object Object]')), r.xato || qisqa(m.xabarlar));
  m = tayyor([{ status: 400, data: { detail: '«g» mayda birligi uchun o\'girish koeffitsienti kerak' } }]);
  r = await ishga(m, 'var apCreatingNewItem = true;\n' + F.kod, 'apResolveItemId()');
  tekshir(`M3 ${nomi}: boshqa xato (400) — «Yangi material yaratib bo'lmadi: <server sababi>»`,
    !r.xato && r.natija === null && m.xabarlar.some((x) => x.tur === 'error' && x.t.includes("Yangi material yaratib bo'lmadi: ")
      && x.t.includes('koeffitsienti')), r.xato || qisqa(m.xabarlar));
}

// ══════════════════════════════════════════════════════════════
async function inventarBolimi() {
  bolim("inventory.html — EGASI QARORI: qoldig'i bor material o'chirilmaydi");
  const F = funks(INV, ['deleteItem']);
  tekshir('I0 deleteItem topildi', !F.yoq.length, qisqa(F.yoq));
  function tayyor(tasdiq) {
    const oynalar = [], tasdiqlar = [], toast = [];
    const m = muhit([], {
      xabarOyna: async (t) => { oynalar.push(String(t)); }, customConfirm: async (...a) => { tasdiqlar.push(a); return tasdiq; },
      invToast: (t) => toast.push(String(t)), amalSababi: async () => 'sabab',
    });
    Object.assign(m, { oynalar, tasdiqlar, toast });
    vm.runInContext(BASE_YORDAM.kod, m.ctx);
    return m;
  }
  let m = tayyor(true);
  let r = await ishga(m, F.kod, "deleteItem(3, {name: 'Kraska', qty: 7, unit: 'kg'})");
  tekshir("I1 qoldiq 7 kg — so'rov ham, tasdiq ham YO'Q; oynada sabab «Chiqim (tuzatish)» bilan",
    !r.xato && m.sorovlar.length === 0 && m.tasdiqlar.length === 0 && m.oynalar.length === 1 && m.oynalar[0].includes('Chiqim (tuzatish)')
    && m.oynalar[0].includes('7'), r.xato || qisqa([m.sorovlar, m.oynalar]));
  m = tayyor(true);
  r = await ishga(m, F.kod, "deleteItem(3, {name: 'Penoplast', qty: -2, unit: 'blok'})");
  tekshir("I2 manfiy qoldiq — sabab «Kirim (tuzatish)» bilan, so'rov yo'q",
    !r.xato && m.sorovlar.length === 0 && m.oynalar.length === 1 && m.oynalar[0].includes('Kirim (tuzatish)'), r.xato || qisqa(m.oynalar));
  m = tayyor(true);
  r = await ishga(m, F.kod, "deleteItem(3, {name: 'Bo\\'sh', qty: 0, unit: 'kg'})");
  tekshir("I3 qoldiq 0 — tasdiq, so'ng DELETE /api/inventory/3", !r.xato && m.tasdiqlar.length === 1 && m.sorovlar.length === 1
    && m.sorovlar[0].method === 'DELETE' && m.sorovlar[0].url === '/api/inventory/3', r.xato || qisqa(m.sorovlar));
}

// ══════════════════════════════════════════════════════════════
async function ishlabBolimi() {
  bolim('production.html — A-O03 / A-O10 a');
  const F = funks(PROD, ['poOyna', 'poBoshlashTasdiq', 'poYakunlashTasdiq']);
  tekshir('P0 poOyna / poBoshlashTasdiq / poYakunlashTasdiq topildi', !F.yoq.length, qisqa(F.yoq));
  const IDS = ['snapshot-modal-title', 'snapshot-warnings', 'snapshot-list', 'snapshot-tugmalar', 'po-oyna-amal'];
  function tayyor(royxat, javoblar, keyingiRoyxat) {
    const chaq = [];
    const m = muhit(IDS, {
      poRoyxat: royxat, poSarlavha: (p) => '№' + p.id, openModalEl: (id) => chaq.push('ochildi:' + id),
      closeModal: (id) => chaq.push('yopildi:' + id), poManbaMatni: () => 'Omborga', vaqtKartalariHtml: () => '',
      rejaJadvaliHtml: () => '', rejaOgohHtml: () => '', pulKorinish: (x) => String(x), birlikMatni: (x) => String(x),
      birlikYoz: (x) => String(x), xatoSababi: (d, s) => String((d && d.detail) || s),
      loadProductionOrders: async () => { if (keyingiRoyxat) m.ctx.poRoyxat = keyingiRoyxat; },
    }, javoblar);
    m.chaq = chaq;
    vm.runInContext(BASE_YORDAM.kod + '\nvar poAmalda = false;', m.ctx);
    return m;
  }
  let m = tayyor([{ id: 4, status: 'completed', birlik: 'dona' }]);
  let r = await ishga(m, F.kod, "poOyna(4, 'batafsil')");
  tekshir("P1 yakunlangan ishlab chiqarish oynasida «Ishlab chiqarishni bekor qilish» tugmasi YO'Q",
    !r.xato && !m.el['snapshot-tugmalar'].innerHTML.includes('po-bekor-tugma'), r.xato || qisqa(m.el['snapshot-tugmalar'].innerHTML));
  m = tayyor([{ id: 4, status: 'draft', birlik: 'dona' }], [{ status: 200, data: { mumkin: true, miqdor: 1, tannarx: 10 } }]);
  r = await ishga(m, F.kod, "poOyna(4, 'boshlash')");
  tekshir("P1b qoralamada tugma bor", !r.xato && m.el['snapshot-tugmalar'].innerHTML.includes('po-bekor-tugma'), r.xato);
  m = tayyor([{ id: 4, status: 'draft', birlik: 'dona' }], [{ status: 409, data: { detail: 'Faqat qoralamani boshlash mumkin' } }],
    [{ id: 4, status: 'in_progress', birlik: 'dona' }]);
  vm.runInContext(F.kod, m.ctx);
  let qayta = 0;
  vm.runInContext('var _asl = poOyna; poOyna = function(){ _qayta(); return _asl.apply(null, arguments); };', Object.assign(m.ctx, { _qayta: () => { qayta++; } }));
  r = await ishga(m, '', 'poBoshlashTasdiq(4)');
  tekshir("P2 «Boshlash» 409, shu orada boshqa joyda boshlangan — oyna YOPILDI (eski holatda qayta ochilmadi)",
    !r.xato && qayta === 0 && m.chaq.includes('yopildi:snapshot-modal'), r.xato || qisqa([qayta, m.chaq]));
  m = tayyor([{ id: 4, status: 'in_progress', birlik: 'dona' }], [{ status: 409, data: { detail: 'yakunlangan' } }],
    [{ id: 4, status: 'completed', birlik: 'dona' }]);
  r = await ishga(m, F.kod, 'poYakunlashTasdiq(4)');
  tekshir("P3 «Yakunlash» 409, shu orada yakunlangan — oyna yopildi", !r.xato && m.chaq.includes('yopildi:snapshot-modal'),
    r.xato || qisqa(m.chaq));
  tekshir("P4 A-O10 a matni: o'chirilgan material «tannarxga boshlangan kundagi narx bilan kiradi» (eski «tannarxga kirmaydi» yo'q)",
    PROD.includes("lekin tannarxga boshlangan kundagi narx bilan kiradi") && !PROD.includes("o'tkazib yuboriladi va tannarxga kirmaydi"));
}

(async () => {
  await sotishBolimi();
  await brakBolimi();
  await materialBolimi('supplier_receive.html', RCV, "+ Material ro'yxatga qo'shish");
  await materialBolimi('suppliers.html', SUP, '✓ Saqlash');
  await inventarBolimi();
  await ishlabBolimi();
  console.log(`\nNATIJA: o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('Yiqilganlar:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})();
