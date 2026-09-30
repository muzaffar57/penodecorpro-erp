#!/usr/bin/env node
/**
 * test_kelishilgan_tahrir_ui.js — kech110, K110-1: buyurtma TAHRIRIDA kelishilgan summa (templates/orders.html).
 *
 * NIMA UCHUN KERAK (asl kod `ba6935c` — HAQIQIY brauzerda O'LCHANGAN, `work/probe110k2.py`, SQLite = PG; jonli
 * sinovda ham — 56 000 → jami 20 000, kelishilgan 56 000):
 *   `reapplyDiscount` faqat saqlangan chegirma FOIZI (`discount_percent` > 0) bo'lsa ishlardi — chegirmasiz buyurtmada
 *   detal olib tashlansa forma eski summani ko'rsatib, `updateOrder` uni yuborardi (server "qo'lda kiritilgan" deb
 *   olardi): 400 000 → jami 300 000, kelishilgan 400 000; ustama (450 000) va to'lovda kechirilgan qarz ham shunday;
 *   nomsiz (saqlanmaydigan) qator chegirma asosiga kirardi (360 000 → 450 000); tiyinli chegirmasiz buyurtma
 *   «📉 Chegirma: 0 so'm (0.0%)» ko'rinardi; yangi formada zaklat = jami bo'lsa «Qarz qoladi: 0 so'm».
 * Endi: `kelishilganQayta` (server `crud.kelishilgan_qayta_hisob` bilan AYNAN — paritet tools/test_kelishilgan_nisbat.py)
 * — chegirmasiz: jamiga teng; chegirma / ustama: nisbat (egasi QARORI — ustama "Foizi saqlansin"); kechirilgan qarz
 * so'mda (QAROR "Kechirilgan so'mda qolsin"); summa faqat QO'LDA yozilganda PUT ga ketadi.
 *
 * BO'LIMLAR
 *   U — HAQIQIY funksiyalar (jsdom): `editSelected` ning tahrir-yuklash qismi (matndan kesiladi — asl va yangi kod
 *       ikkalasi ham yuklanadi), `reapplyDiscount`, `calcDiscount`, `calcDebt`, `getNamedTotal`, `updateOrder` (fetch
 *       tanasi ushlanadi).
 *   S — statik.
 * Funksiyalar HTML dan JONLI o'qiladi; topilmasa / istisno — yiqilgan tekshiruv (asl faylga qarshi QULAMAYDI).
 * ISHLATISH: node tools/test_kelishilgan_tahrir_ui.js [templates_papka]   (chiqish kodi 0 — hammasi o'tdi)
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
const TDIR = process.argv[2] || path.join(ROOT, 'templates');
let SRC = '';
try { SRC = fs.readFileSync(path.join(TDIR, 'orders.html'), 'utf8'); } catch (e) { SRC = ''; }
// kech118 (B — U-05, MOSLANDI): eslatma / chegirma foizi base.html `sonKor` bilan («10%», «+12,5%»; avval «10.00%»)
let BASE_SRC = '';
try { BASE_SRC = fs.readFileSync(path.join(TDIR, 'base.html'), 'utf8'); } catch (e) { BASE_SRC = ''; }

let OK = 0, FAIL = 0;
const FAILED = [];
function qisqa(x) {
  let s;
  try { s = typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { s = String(x); }
  s = String(s);
  return s.length > 500 ? s.slice(0, 500) + '…' : s;
}
function tekshir(label, shart, izoh) {
  let s = false;
  try { s = !!shart; } catch (e) { s = false; }
  if (s) { OK++; console.log(`  ✓ ${label}`); }
  else { FAIL++; FAILED.push(label); console.log(`  ✗ ${label}${izoh !== undefined ? '   — ' + qisqa(izoh) : ''}`); }
}
function bolim(t) { console.log(`\n--- ${t} ---`); }
function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom.replace(/\$/g, '\\$') + '\\s*\\(');
  const m = re.exec(src);
  if (!m) return null;
  let i = m.index + m[0].length, d = 1;
  for (; i < src.length && d > 0; i++) { if (src[i] === '(') d++; else if (src[i] === ')') d--; }
  const j = src.indexOf('{', i);
  if (j < 0) return null;
  d = 0;
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(m.index, k + 1); }
  }
  return null;
}
function kes(src, bosh, oxir) {
  if (!src) return null;
  const i = src.indexOf(bosh);
  if (i < 0) return null;
  const j = src.indexOf(oxir, i + bosh.length);
  return j < 0 ? null : src.slice(i, j);
}

let JSDOM = null, VirtualConsole = null;
try { ({ JSDOM, VirtualConsole } = require('jsdom')); } catch (e) { JSDOM = null; }

const EDIT = olib(SRC, 'editSelected') || '';
// tahrir shoxi: holat (asl: `editDiscountPct = …`; yangi: `editJami0 = …`) + kelishilgan summa + eslatmalar
const QISM_YUKLASH = kes(EDIT, 'editUserTouched = false;', '// Loy rejasi');
// oxiri: `calcDiscount();` + (yangi) yuklash eslatmasini saqlash + `editInitialLoadDone = true;`
const QISM_OXIR = kes(EDIT, '    calcDiscount();\n', '\n  } catch');
const FUNK = ['formatNum', 'parseNum', 'narxMatni', 'narxKorinishi', 'getNamedTotal', 'calcDiscount', 'calcDebt',
  'reapplyDiscount', '_tiyin110', '_tiyinda110', 'kelishilganQayta', 'updateOrder',
  // kech115 (G2-07): `updateOrder` yangi narxsiz qatorni tasdiqlatadi — yordamchilar ham yuklanadi
  '_narxsizDetallar', '_narxsizTasdiq'];
const KOD = {};
for (const f of FUNK) KOD[f] = olib(SRC, f);

function muhit() {
  const html = `<!doctype html><body>
    <input id="project_id" value="7"><input id="recipe_id" value=""><input id="master_id" value="">
    <input id="deadline_input" value=""><input id="base_price" value=""><input id="loy_kg" value="">
    <div id="items"></div>
    <input type="text" id="final_price"><input type="text" id="zaklat_amount">
    <div id="discount-auto-hint" style="display:none"></div>
    <div id="discount_info" style="display:none"></div><div id="debt_info" style="display:none"></div>
    <div id="resultBox"></div><input id="boshqa"></body>`;
  const xatolar = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => { xatolar.push(String(e && e.message || e)); });
  const dom = new JSDOM(html, { runScripts: 'dangerously', virtualConsole: vc, url: 'https://testserver/orders' });
  const w = dom.window;
  const kod = [
    'var editMode = false, currentEditOrderId = null, editUserTouched = false, editInitialLoadDone = false;',
    'var editDiscountPct = 0, editJami0 = 0, editAsl0 = 0, editKech = 0;',
    'var _dlvHolat103 = null; window._dlvMap = {}; function _tahrirBanneriTopshirish(){}',
    'function updateLiveStats(){} function showMsg(){} function showValidationModal(){}',
    'function retseptMajburiyXatosi54(){ return null; } function _narxiNolgaTushgan(){ return []; }',
    'async function showConfirmModal(){ return true; } async function customConfirm(){ return false; }',
    'async function uploadPendingItemImages(){} function escapeHtml(s){ return String(s); }',
    'function collectItems(){ return Array.from(document.querySelectorAll(".detal")).filter(r => r.querySelector(".i-name").value.trim()).map(r => ({name: r.querySelector(".i-name").value, category: "panel", quantity: 1, unit_price: parseFloat(r.dataset.price)})); }',
    'window.__tanalar = []; window.fetch = async (url, o) => { window.__tanalar.push({url: String(url), body: o && o.body ? JSON.parse(o.body) : null}); return { ok: false, status: 400, json: async () => ({ detail: "sinov" }) }; };',
    ...FUNK.map(f => KOD[f] || ''),
    ...['sonKor', 'foizKor'].map(f => olib(BASE_SRC, f) || ''),
    'function __yukla(order) { editMode = true; currentEditOrderId = order.id; var editId = order.id;',
    QISM_YUKLASH || 'throw new Error("QISM_YUKLASH topilmadi");',
    QISM_OXIR || 'throw new Error("QISM_OXIR topilmadi");',
    '}',
  ].join('\n');
  const s = w.document.createElement('script');
  s.textContent = kod;
  w.document.body.appendChild(s);
  return { w, xatolar };
}

function qator(w, nom, narx) {
  const r = w.document.createElement('div');
  r.className = 'detal';
  r.dataset.price = String(narx);
  const i = w.document.createElement('input');
  i.className = 'i-name';
  i.value = nom;
  r.appendChild(i);
  w.document.getElementById('items').appendChild(r);
  return r;
}
function ochir(w, nom) {
  const r = Array.from(w.document.querySelectorAll('.detal')).find(x => x.querySelector('.i-name').value === nom);
  if (r) r.remove();
}
function holat(w) {
  const h = w.document.getElementById('discount-auto-hint');
  const di = w.document.getElementById('discount_info');
  return { fp: w.document.getElementById('final_price').value, hint: h.style.display === 'none' ? '' : h.textContent,
           info: di.style.display === 'none' ? '' : di.textContent };
}
// Buyurtma yuklanadi (A 300 000 + B 100 000 = 400 000 — yoki berilgan qatorlar), `order` — `/api/orders/{id}` shakli
function tahrirda(order, qatorlar) {
  const M = muhit();
  const w = M.w;
  for (const [n, p] of (qatorlar || [['A', 300000], ['B', 100000]])) qator(w, n, p);
  let x = null;
  try { w.__yukla(Object.assign({ id: 5, total_amount: 400000, agreed_amount: 400000, kelishilgan_asl: 400000,
    discount_percent: 0, pul_qaytarish_kamaytirgan: 0, kechirilgan_qarz: 0 }, order)); } catch (e) { x = String(e && e.message || e); }
  return { w, x, M };
}
function qayta(w) {
  try { w.reapplyDiscount(); return null; } catch (e) { return String(e && e.message || e); }
}

bolim('U. HAQIQIY funksiyalar (jsdom)');
tekshir('U0 manbalar: jsdom, editSelected qismlari, funksiyalar (formatNum … updateOrder)',
  !!JSDOM && !!QISM_YUKLASH && !!QISM_OXIR && ['getNamedTotal', 'calcDiscount', 'reapplyDiscount', 'updateOrder'].every(f => !!KOD[f]),
  { jsdom: !!JSDOM, yuklash: !!QISM_YUKLASH, oxir: !!QISM_OXIR, funk: FUNK.filter(f => !KOD[f]) });

if (JSDOM && QISM_YUKLASH && QISM_OXIR) {
  // U1 chegirmasiz: B olib tashlanadi
  {
    const { w, x } = tahrirda({});
    const h0 = holat(w);
    ochir(w, 'B');
    const x2 = qayta(w);
    const h = holat(w);
    tekshir('U1a chegirmasiz (400 000): yuklanganda «✓ Chegirmasiz», eslatma yo\'q', x === null && h0.fp === '400 000'
      && h0.info.includes('Chegirmasiz') && h0.hint === '', { x, h0 });
    tekshir('U1b B olib tashlandi: kelishilgan 300 000 (asl: 400 000 — «📈 Standartdan ortiq: +100 000»), «✓ Chegirmasiz»',
      x2 === null && h.fp === '300 000' && h.info.includes('Chegirmasiz') && h.hint.includes('Chegirmasiz'), { x2, h });
    w.__tanalar.length = 0;
    let x3 = null;
    const p = (async () => { try { await w.updateOrder(5); } catch (e) { x3 = String(e && e.message || e); } })();
    p.then(() => {
      const t = (w.__tanalar[0] || {}).body || {};
      tekshir('U1c saqlash: summa QO\'LDA yozilmagan — PUT tanasida `agreed_amount` YO\'Q (server yagona qoidasi hal qiladi; '
        + 'asl: eski 400 000 yuborilardi)', x3 === null && w.__tanalar.length === 1 && !('agreed_amount' in t)
        && (w.__tanalar[0].url || '').startsWith('/api/orders/5'), { x3, tanalar: w.__tanalar });
      davom2();
    });
  }
} else {
  tekshir('U1–U12 muhit tuzilmadi', false, 'jsdom yoki editSelected qismlari yo\'q');
  yakun();
}

function davom2() {
  // U2 10 % chegirma
  {
    const { w, x } = tahrirda({ agreed_amount: 360000, kelishilgan_asl: 360000, discount_percent: 10 });
    const h0 = holat(w);
    ochir(w, 'B');
    qayta(w);
    const h = holat(w);
    tekshir('U2 10 % chegirma (360 000): yuklanganda «10% chegirma bor»; B olib tashlandi — 270 000, «Chegirma 10% saqlandi»',
      x === null && h0.hint.includes(' 10% chegirma') && h0.hint.includes('chegirma') && h.fp === '270 000'
      && h.hint.includes('Chegirma') && h.hint.includes('Chegirma 10% saqlandi'), { x, h0, h });
  }
  // U3 ustama
  {
    const { w, x } = tahrirda({ agreed_amount: 450000, kelishilgan_asl: 450000 });
    const h0 = holat(w);
    ochir(w, 'B');
    qayta(w);
    const h = holat(w);
    tekshir('U3 ustama 450 000: yuklanganda «+12,5% ustama»; B olib tashlandi — 337 500 (asl: 450 000), «Ustama +12,5%»',
      x === null && h0.hint.includes('+12,5%') && h0.hint.includes('ustama') && h.fp === '337 500'
      && h.hint.includes('Ustama +12,5%'), { x, h0, h });
  }
  // U4 kechirilgan (chegirmasiz)
  {
    const { w, x } = tahrirda({ agreed_amount: 399000, kelishilgan_asl: 399000, kechirilgan_qarz: 1000 });
    const h0 = holat(w);
    ochir(w, 'B');
    qayta(w);
    const h = holat(w);
    tekshir('U4 1 000 kechirilgan (399 000): yuklanganda eslatma; B olib tashlandi — 299 000 (asl: 399 000), eslatmada «1 000»',
      x === null && h0.hint.includes('kechirilgan qarz') && h0.hint.includes('1 000') && h.fp === '299 000'
      && h.hint.includes('Kechirilgan qarz') && h.hint.includes('1 000'), { x, h0, h });
  }
  // U5 kechirilgan + chegirma, A narxi oshadi
  {
    const { w, x } = tahrirda({ agreed_amount: 358000, kelishilgan_asl: 358000, discount_percent: 10, kechirilgan_qarz: 2000 });
    const a = Array.from(w.document.querySelectorAll('.detal'))[0];
    a.dataset.price = '450000';
    qayta(w);
    const h = holat(w);
    tekshir('U5 10 % + 2 000 kechirilgan: A 300 000 → 450 000 (jami 550 000) — 493 000 (asl: 495 000 — kechirilgan yo\'qolardi)',
      x === null && h.fp === '493 000', { x, h });
  }
  // U6 nomsiz qator
  {
    const { w, x } = tahrirda({ agreed_amount: 360000, kelishilgan_asl: 360000, discount_percent: 10 });
    const h0 = holat(w);
    qator(w, '', 100000);
    qayta(w);
    const h = holat(w);
    tekshir('U6 10 % chegirma + nomsiz (saqlanmaydigan) qator 100 000: kelishilgan 360 000 qoladi (asl: 450 000), eslatma o\'zgarmaydi',
      x === null && h.fp === '360 000' && h.hint === h0.hint && h.info.includes('(10%)'), { x, h0, h });
  }
  // U7 tiyinli chegirmasiz — ko'rinish
  {
    const { w, x } = tahrirda({ total_amount: 107000.48, agreed_amount: 107000.48, kelishilgan_asl: 107000.48 },
      [['A', 99999.99], ['B', 7000.49]]);
    const h0 = holat(w);
    ochir(w, 'B');
    qayta(w);
    const h = holat(w);
    tekshir('U7 tiyinli chegirmasiz (99 999.99 + 7 000.49): yuklanganda «✓ Chegirmasiz» (asl: «📉 Chegirma: 0 so\'m (0.0%)»); '
      + 'B olib tashlandi — 99 999.99', x === null && h0.info.includes('Chegirmasiz') && !h0.info.includes('Chegirma:')
      && h.fp === '99 999.99' && h.info.includes('Chegirmasiz'), { x, h0, h });
  }
  // U8 qo'lda ustama, keyin B olib tashlanadi; saqlashda summa yuboriladi
  {
    const { w, x } = tahrirda({});
    const fp = w.document.getElementById('final_price');
    fp.focus();
    fp.value = '420 000';
    let x2 = null;
    try { w.calcDiscount(); } catch (e) { x2 = String(e && e.message || e); }
    w.document.getElementById('boshqa').focus();
    ochir(w, 'B');
    qayta(w);
    const h = holat(w);
    tekshir('U8a qo\'lda 420 000 (+5 %), so\'ng B olib tashlandi — 315 000 (asl: 420 000 qolardi), «Ustama +5%»',
      x === null && x2 === null && h.fp === '315 000' && h.hint.includes('Ustama +5% '), { x, x2, h });
    w.__tanalar.length = 0;
    let x3 = null;
    (async () => { try { await w.updateOrder(5); } catch (e) { x3 = String(e && e.message || e); } })().then(() => {
      const t = (w.__tanalar[0] || {}).body || {};
      tekshir('U8b saqlash: summa QO\'LDA yozilgan — PUT `agreed_amount` = 315 000', x3 === null && t.agreed_amount === 315000,
        { x3, tanalar: w.__tanalar });
      davom3();
    });
  }
}

function davom3() {
  // U9 olib tashlab, qaytarish — eslatma tiklanadi
  {
    const { w, x } = tahrirda({ agreed_amount: 360000, kelishilgan_asl: 360000, discount_percent: 10 });
    const h0 = holat(w);
    ochir(w, 'B');
    qayta(w);
    const h1 = holat(w);
    qator(w, 'B', 100000);
    qayta(w);
    const h2 = holat(w);
    tekshir('U9 B olib tashlanib (270 000), QAYTA qo\'shildi — 360 000 AYNAN, yuklangandagi eslatma tiklanadi',
      x === null && h1.fp === '270 000' && h2.fp === '360 000' && h2.hint === h0.hint && h0.hint !== '', { x, h0, h1, h2 });
  }
  // U9b tiyinli chegirma — jami asos holiga qaytsa ASL AYNAN (butun so'mga yaxlitlanmaydi)
  {
    const { w, x } = tahrirda({ agreed_amount: 360000.37, kelishilgan_asl: 360000.37, discount_percent: 10 });
    ochir(w, 'B');
    qayta(w);
    const h1 = holat(w);
    qator(w, 'B', 100000);
    qayta(w);
    const h2 = holat(w);
    tekshir('U9b tiyinli 360 000.37: B olib tashlandi — 270 000 (butun so\'m), qaytarildi — 360 000.37 AYNAN',
      x === null && h1.fp === '270 000' && h2.fp === '360 000.37', { x, h1, h2 });
  }
  // U10 chegirmasiz — qaytarish: eslatma yo'q holatga
  {
    const { w, x } = tahrirda({});
    ochir(w, 'B');
    qayta(w);
    qator(w, 'B', 100000);
    qayta(w);
    const h = holat(w);
    tekshir('U10 chegirmasiz: olib tashlab qaytarildi — 400 000, «🔄» eslatmasi yashirildi', x === null && h.fp === '400 000'
      && h.hint === '', { x, h });
  }
  // U11 yangi forma — zaklat = jami (float shovqini)
  {
    const M = muhit();
    const w = M.w;
    qator(w, 'A', 100000.1);
    qator(w, 'B', 200000.2);
    w.document.getElementById('zaklat_amount').value = '300 000.3';
    let x = null;
    try { w.calcDebt(); } catch (e) { x = String(e && e.message || e); }
    const d = w.document.getElementById('debt_info');
    const t = d.style.display === 'none' ? '' : d.textContent;
    tekshir('U11 yangi forma: jami 100 000.1 + 200 000.2, zaklat 300 000.3 — «To\'liq to\'landi» (asl: «Qarz qoladi: 0 so\'m»)',
      x === null && t.includes("To'liq to'landi"), { x, t });
  }
  // U12 pul qaytarish kamaytirishi + chegirma — ikkala eslatma
  {
    const { w, x } = tahrirda({ agreed_amount: 310000, kelishilgan_asl: 360000, discount_percent: 10, pul_qaytarish_kamaytirgan: 50000 });
    const h0 = holat(w);
    tekshir('U12 pul qaytarish (50 000) + 10 % chegirma: forma ASL 360 000, ikkala eslatma (chegirma, qaytarish)',
      x === null && h0.fp === '360 000' && h0.hint.includes(' 10% chegirma') && h0.hint.includes('50 000'), { x, h0 });
    ochir(w, 'B');
    qayta(w);
    const h1 = holat(w);
    tekshir('U13 shu buyurtmada B olib tashlandi — ASL 270 000 (nisbat ASL summadan; qaytarish kamaytirishini server ayiradi)',
      h1.fp === '270 000', h1);
  }
  statik();
}

function statik() {
  bolim('S. Statik');
  const upd = KOD.updateOrder || '';
  tekshir('S1 `updateOrder`: `agreed_amount` faqat `editUserTouched` bo\'lsa',
    upd.includes('agreed_amount: (editUserTouched && finalPrice) ? finalPrice : undefined'));
  const rea = KOD.reapplyDiscount || '';
  tekshir('S2 `reapplyDiscount`: nomli detallar (`getNamedTotal`) va `kelishilganQayta`; eski `editDiscountPct` kodda yo\'q',
    rea.includes('getNamedTotal()') && rea.includes('kelishilganQayta(') && !SRC.includes('editDiscountPct'));
  const cd = KOD.calcDiscount || '';
  tekshir('S3 `calcDiscount` / `calcDebt` tiyinlarda taqqoslaydi (`_tiyin110`)',
    cd.includes('_tiyin110(total - finalPrice)') && (KOD.calcDebt || '').includes('_tiyin110(agreed - zaklat)'));
  yakun();
}

function yakun() {
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAIL) console.log('Yiqilganlar:\n  - ' + FAILED.join('\n  - '));
  process.exit(FAIL ? 1 : 0);
}
