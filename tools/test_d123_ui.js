#!/usr/bin/env node
/**
 * test_d123_ui.js — kech118 D BOSQICHI 3-qism (zip 123): BITTA «Brak yozish» oynasi (egasi QARORI G5-04, QAYTA SO'RALMAYDI).
 *
 *   templates/_brak_oyna.html — returns.html («Brak yozish») va finished.html («−») ulaydigan YAGONA oyna: avval «Brak qayerda
 *     chiqdi?» — (A) buyurtma detalida → POST /api/returns (reason «Brak»), (B) omborda turgan tayyor mahsulotda → POST
 *     /api/finished/loss, (C) ishlab chiqarishda → POST /api/finished/production-brak; sabab (MAJBURIY), bosqich, javobgar, izoh —
 *     hamma yo'lda bir xil maydonlar (`brak-cause`, `brak-stage`, `brak-worker`, `brak-notes`).
 *   templates/returns.html — «Yangi qaytarish» FAQAT butun mahsulot (`saveReturn` — reason «Ortiqcha», brak kalitlari yo'q).
 *
 * NIMA UCHUN KERAK
 *   Ilgari brak uch xil oynada yozilardi (Qaytarishlar «Brak yozish», «Yangi qaytarish» → «Brak», Tayyor mahsulotlar «−» — ikki
 *   rejim); qaysi birini ishlatish noaniq edi (audit G5-04). Endi bitta oyna: yo'l tanlanmasa saqlanmaydi, har yo'l o'z marshrutiga
 *   to'g'ri tana yuboradi, sabab tanlanmasa hech qaysi yo'l so'rov yubormaydi.
 * QANDAY ISHLAYDI: funksiyalar HTML dan JONLI o'qiladi (Jinja — birinchi tarmoq), soxta DOM / fetch muhitida ishga tushiriladi.
 *   Topilmagan funksiya yoki istisno — yiqilgan tekshiruv (asl faylga qarshi ham QULAMAYDI).
 * ISHLATISH: node tools/test_d123_ui.js
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
const OYNA = oqi('_brak_oyna.html');
const BASE = oqi('base.html');
const RETURNS = oqi('returns.html');

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
// Jinja: `{% if %}A{% else %}B{% endif %}` → A (birinchi tarmoq); qolgan teglar olib tashlanadi
function jinja(kod) {
  if (kod === null) return null;
  return kod.replace(/\{%\s*if[^%]*%\}([\s\S]*?)(?:\{%\s*else\s*%\}[\s\S]*?)?\{%\s*endif\s*%\}/g, '$1')
    .replace(/\{%[\s\S]*?%\}/g, '');
}
// _brak_oyna.html ichidagi <script> — butunligicha (oyna holati o'zgaruvchilari bilan)
function oynaSkript() {
  const m = /<script>([\s\S]*?)<\/script>/.exec(OYNA);
  return m ? jinja(m[1]) : null;
}

function klassRoyxat() {
  const s = new Set();
  return { _s: s, toggle(k, v) { if (v === undefined ? !s.has(k) : v) s.add(k); else s.delete(k); },
    add(k) { s.add(k); }, remove(k) { s.delete(k); }, contains(k) { return s.has(k); } };
}
function element(id, qiymat) {
  const el = { id, value: qiymat === undefined ? '' : qiymat, checked: false, textContent: '', innerHTML: '', max: '',
    style: { display: 'none' }, dataset: {}, disabled: false, classList: klassRoyxat(), _fokus: 0 };
  el.focus = () => { el._fokus++; };
  return el;
}
const IDLAR = ['brakModal', 'brak-project', 'brakList', 'brak-notes', 'brak-stage', 'brak-worker', 'loss-qty', 'brak-cause',
  'brak-fp', 'brak-fp-tanlash', 'brak-fp-nomi', 'brak-manba-buyurtma', 'brak-manba-ombor', 'brak-manba-ishlab',
  'brak-panel-project', 'brak-tm-panel', 'brak-umumiy', 'brak-sarlavha-sub', 'brak-error', 'brak-save-btn', 'loss-info-stock',
  'loss-info-production', 'loss-qty-label', 'loss-stock-info'];

// Muhit: `yoq` — sahifada YO'Q elementlar (masalan finished sahifasida A yo'li); `javoblar` — fetch javoblari navbati
function muhit(opts) {
  const o = opts || {};
  const el = {};
  for (const id of IDLAR) if (!(o.yoq || []).includes(id)) el[id] = element(id);
  const radiolar = ['buyurtma', 'ombor', 'ishlab'].filter((m) => el['brak-manba-' + m])
    .map((m) => Object.assign(element('r-' + m, m), { name: 'brak-manba' }));
  const qtyInp = (o.qtylar || []).map((q, i) => Object.assign(element('q' + i, String(q)), { dataset: { idx: String(i) } }));
  const sorovlar = [], xabarlar = [], yuklash = [];
  const javoblar = (o.javoblar || []).slice();
  const ctx = {
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, isFinite, Array, Object, Error, RegExp, Set, Map,
    document: {
      getElementById: (id) => (Object.prototype.hasOwnProperty.call(el, id) ? el[id] : null),
      querySelectorAll: (sel) => {
        if (sel === 'input[name="brak-manba"]') return radiolar;
        if (sel === '.brk-manba') return ['buyurtma', 'ombor', 'ishlab'].map((m) => el['brak-manba-' + m]).filter(Boolean);
        if (sel === '.brak-qty-inp') return qtyInp;
        return [];
      },
      querySelector: (sel) => (sel === 'input[name="brak-coating-applied"]:checked' ? { value: o.qoplama || 'no' } : null),
    },
    fetch: async (url, f) => {
      let tana = null;
      try { tana = f && f.body ? JSON.parse(f.body) : null; } catch (e) { tana = 'JSON EMAS'; }
      sorovlar.push({ url: String(url), method: (f && f.method) || 'GET', tana });
      const j = javoblar.length ? javoblar.shift() : { status: 200, data: { success: true, cost_amount: 1000 } };
      return { ok: j.status >= 200 && j.status < 300, status: j.status, json: async () => JSON.parse(JSON.stringify(j.data)) };
    },
    showMsg: (t, tur) => { xabarlar.push({ t: String(t), tur }); },
    xatoSababi: (r, s) => String((r && (r.message || (r.detail && (r.detail.message || r.detail)))) || s || 'Xato'),
    location: { reload: () => { yuklash.push(1); } },
    setTimeout: () => 0,
  };
  vm.createContext(ctx);
  const yordam = ['escapeHtml', 'sonKor', 'birlikKor'].map((n) => olib(BASE, n)).filter(Boolean).join('\n');
  vm.runInContext(yordam, ctx);
  return { ctx, el, radiolar, qtyInp, sorovlar, xabarlar, yuklash };
}
async function ishga(m, ifoda) {
  try {
    return { xato: null, natija: await vm.runInContext(ifoda, m.ctx) };
  } catch (e) {
    return { xato: String((e && e.message) || e), natija: undefined };
  }
}
function oyna(opts) {
  const m = muhit(opts);
  const kod = oynaSkript();
  if (!kod) return Object.assign(m, { kodXato: "skript topilmadi" });
  try { vm.runInContext(kod, m.ctx); } catch (e) { return Object.assign(m, { kodXato: String(e && e.message || e) }); }
  return m;
}
function korinadi(el) { return !!el && el.style.display !== 'none'; }
function rgb(h) {
  h = String(h).replace('#', '');
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}
function lum(h) {
  const [r, g, b] = rgb(h).map((v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function kontrast(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }

const TM = [
  { id: 1, name: 'Karniz K1', quantity: 5, unit: 'm', category: 'profil', source: 'produced', production_status: 'ready' },
  { id: 2, name: 'Jarayondagi', quantity: 4, unit: 'm', category: 'profil', source: 'produced', production_status: 'in_progress' },
  { id: 3, name: 'Tugagan', quantity: 0, unit: 'm', category: 'panel', source: 'produced', production_status: 'ready' },
  { id: 4, name: 'Qaytgan MRP', quantity: 2, unit: 'dona', category: 'mrp_product', source: 'returned', production_status: null },
  { id: 5, name: 'Travertin <b>', quantity: 12.5, unit: 'm2', category: 'dynamic_bom', source: 'produced', production_status: 'ready' },
];

// ══════════════════════════════════════════════════════════════
async function asosBolimi() {
  bolim('_brak_oyna.html — bitta oyna: ochilish va «Brak qayerda chiqdi?»');
  tekshir('O0 oyna skripti topildi va xatosiz yuklanadi', !!oynaSkript() && !oyna().kodXato, oyna().kodXato);
  let m = oyna();
  let r = await ishga(m, 'showBrakModal()');
  tekshir("O1 ochiladi: yo'l TANLANMAGAN, loyiha / tayyor mahsulot / umumiy maydonlar yashirin",
          !r.xato && m.el.brakModal.style.display === 'flex' && !korinadi(m.el['brak-panel-project'])
          && !korinadi(m.el['brak-tm-panel']) && !korinadi(m.el['brak-umumiy']) && m.radiolar.every((x) => !x.checked),
          r.xato || qisqa(['brak-panel-project', 'brak-tm-panel', 'brak-umumiy'].map((k) => m.el[k].style.display)));
  r = await ishga(m, 'brakSaqlash()');
  tekshir("O2 yo'l tanlanmasa — so'rov YO'Q, «❌ Brak qayerda chiqqanini tanlang»",
          !r.xato && !m.sorovlar.length && m.el['brak-error'].textContent === '❌ Brak qayerda chiqqanini tanlang'
          && m.el['brak-error'].style.display === 'block', r.xato || qisqa([m.sorovlar, m.el['brak-error'].textContent]));
  r = await ishga(m, "brakManbaTanla('buyurtma')");
  tekshir("O3 «Buyurtma detalida» → loyiha paneli va umumiy maydonlar ko'rinadi, tayyor mahsulot paneli yashirin, karta belgilangan",
          !r.xato && korinadi(m.el['brak-panel-project']) && !korinadi(m.el['brak-tm-panel']) && korinadi(m.el['brak-umumiy'])
          && m.radiolar[0].checked && m.el['brak-manba-buyurtma'].classList.contains('tanlangan')
          && !m.el['brak-manba-ombor'].classList.contains('tanlangan') && m.el['brak-error'].style.display === 'none',
          r.xato);
  const rang = {};
  for (const mb of ['buyurtma', 'ombor', 'ishlab']) {
    m = oyna({ javoblar: [{ status: 200, data: TM }] });
    await ishga(m, 'showBrakModal()');
    await ishga(m, `brakManbaTanla('${mb}')`);
    rang[mb] = [m.el['brak-save-btn'].textContent, m.el['brak-save-btn'].style.background];
  }
  tekshir("O4 saqlash tugmasi yo'lga mos: «🔴 Brak sifatida saqlash» / «⚠️ Kamaytirish (brak)» / «🏭 Xomashyoni ayirish (brak)»; "
          + "oq yozuv har rangda ≥ 4.5:1",
          rang.buyurtma[0] === '🔴 Brak sifatida saqlash' && rang.ombor[0] === '⚠️ Kamaytirish (brak)'
          && rang.ishlab[0] === '🏭 Xomashyoni ayirish (brak)'
          && Object.values(rang).every(([, c]) => /^#[0-9A-F]{6}$/i.test(c) && kontrast('#FFFFFF', c) >= 4.5), qisqa(rang));
  m = oyna();
  await ishga(m, 'showBrakModal()');
  r = await ishga(m, "brakManbaTanla('yoq'); brakManbaTanla('ombor'.replace('ombor', 'nomalum'))");
  tekshir("O5 noma'lum yo'l — e'tiborsiz (hech narsa ko'rinmaydi)", !r.xato && !korinadi(m.el['brak-umumiy']) && !m.sorovlar.length, r.xato);
}

async function buyurtmaBolimi() {
  bolim("(A) buyurtma detali → POST /api/returns (reason «Brak»)");
  const detal = [{ order_id: 7, item_id: 11, name: 'Karniz', order_qty_normalized: 10, delivery_unit: 'metr', is_coated: true },
    { order_id: 8, item_id: 12, name: 'Panel', order_qty_normalized: 4, delivery_unit: 'm2' }];
  async function sina(qtylar, sabab, bosqich, javobgar, qoplama) {
    const m = oyna({ qtylar, qoplama });
    await ishga(m, "showBrakModal('buyurtma')");
    m.ctx.brakItems = detal;
    vm.runInContext('brakItems = this.brakItems', m.ctx);
    m.el['brak-cause'].value = sabab || '';
    m.el['brak-stage'].value = bosqich || '';
    m.el['brak-worker'].value = javobgar || '';
    m.el['brak-notes'].value = ' izoh ';
    const r = await ishga(m, 'brakSaqlash()');
    return Object.assign(m, { xato: r.xato });
  }
  let m = await sina([2, ''], '', 'kesish', '3');
  tekshir("A1 sabab tanlanmagan — so'rov YO'Q, «❌ Brak sababini tanlang (ro'yxatdan)», maydonga fokus",
          !m.xato && !m.sorovlar.length && m.el['brak-error'].textContent === "❌ Brak sababini tanlang (ro'yxatdan)"
          && m.el['brak-cause']._fokus === 1, m.xato || qisqa([m.sorovlar, m.el['brak-error'].textContent]));
  m = await sina(['', ''], 'uskuna');
  tekshir("A2 miqdor kiritilmagan — so'rov YO'Q, «Kamida bitta detal uchun miqdor kiriting»",
          !m.xato && !m.sorovlar.length && m.el['brak-error'].textContent.includes('Kamida bitta detal'), m.xato);
  m = await sina([11, ''], 'uskuna');
  tekshir("A3 buyurtmadagidan ko'p — so'rov YO'Q, qizil maydon", !m.xato && !m.sorovlar.length
          && m.qtyInp[0].style.borderColor === '#DC2626', m.xato || qisqa(m.sorovlar));
  m = await sina([2, 1.5], 'uskuna', 'kesish', '3', 'yes');
  const t = m.sorovlar.map((s) => s.tana);
  tekshir("A4 ikki detal → ikkita POST /api/returns: reason «Brak», refund 0, to_stock false, izoh, qoplama, sabab / bosqich / "
          + "javobgar (son)",
          !m.xato && m.sorovlar.length === 2 && m.sorovlar.every((s) => s.url === '/api/returns' && s.method === 'POST')
          && t[0].order_id === 7 && t[0].order_item_id === 11 && t[0].quantity === 2 && t[1].quantity === 1.5
          && t.every((x) => x.reason === 'Brak' && x.refund_amount === 0 && x.to_stock === false && x.notes === 'izoh'
                     && x.coating_applied === true && x.brak_sabab === 'uskuna' && x.brak_bosqich === 'kesish'
                     && x.brak_javobgar_id === 3) && m.yuklash.length >= 1, m.xato || qisqa(t));
  m = await sina([2, ''], 'olcham');
  const t2 = (m.sorovlar[0] || {}).tana || {};
  tekshir("A5 bosqich / javobgar tanlanmagan — kalitlari YO'Q", !m.xato && t2.brak_sabab === 'olcham'
          && !('brak_bosqich' in t2) && !('brak_javobgar_id' in t2), m.xato || qisqa(t2));
}

async function tmBolimi() {
  bolim("(B) omborda turgan / (C) ishlab chiqarishda — tayyor mahsulot tanlanadi (Qaytarishlar sahifasi)");
  let m = oyna({ javoblar: [{ status: 200, data: TM }] });
  await ishga(m, 'showBrakModal()');
  let r = await ishga(m, "brakManbaTanla('ombor')");
  const sor0 = m.sorovlar.slice();
  const opts = m.el['brak-fp'].innerHTML;
  tekshir("T1 «Omborda turgan» → /api/finished BIR marta yuklanadi; ro'yxatda faqat TAYYOR va qoldig'i bor (jarayondagi, tugagan YO'Q), "
          + "nom escape qilingan",
          !r.xato && sor0.length === 1 && sor0[0].url === '/api/finished' && opts.includes('value="1"')
          && opts.includes('value="4"') && opts.includes('value="5"') && !opts.includes('value="2"') && !opts.includes('value="3"')
          && opts.includes('Travertin &lt;b&gt;') && !opts.includes('<b>'), r.xato || qisqa(opts));
  tekshir("T2 izoh «Omborda turgan» rejimi; tayyor mahsulot paneli va umumiy maydonlar ko'rinadi, loyiha paneli yashirin",
          korinadi(m.el['loss-info-stock']) && !korinadi(m.el['loss-info-production']) && korinadi(m.el['brak-tm-panel'])
          && !korinadi(m.el['brak-panel-project']) && m.el['loss-qty-label'].textContent === "Necha birlik brak bo'ldi?",
          qisqa([m.el['loss-info-stock'].style, m.el['loss-qty-label'].textContent]));
  m.el['brak-fp'].value = '1';
  await ishga(m, 'brakFpTanla()');
  m.el['loss-qty'].value = '6';
  m.el['brak-cause'].value = 'ishchi';
  r = await ishga(m, 'brakSaqlash()');
  tekshir("T3 ombordagidan ko'p (6 > 5) — so'rov YO'Q, «Omborda faqat 5 m bor»",
          !r.xato && m.sorovlar.length === 1 && m.xabarlar.some((x) => x.t === 'Omborda faqat 5 m bor' && x.tur === 'error'),
          r.xato || qisqa(m.xabarlar));
  m.el['loss-qty'].value = '2';
  m.el['brak-stage'].value = 'saqlash_tashish';
  m.el['brak-notes'].value = 'tashishda sindi';
  r = await ishga(m, 'brakSaqlash()');
  const t = (m.sorovlar[1] || {}).tana || {};
  tekshir("T4 → POST /api/finished/loss {finished_product_id 1, quantity 2, reason: izoh, brak_sabab, brak_bosqich}",
          !r.xato && m.sorovlar.length === 2 && m.sorovlar[1].url === '/api/finished/loss' && t.finished_product_id === 1
          && t.quantity === 2 && t.reason === 'tashishda sindi' && t.brak_sabab === 'ishchi' && t.brak_bosqich === 'saqlash_tashish'
          && !('brak_javobgar_id' in t), r.xato || qisqa(t));
  // (C)
  m = oyna({ javoblar: [{ status: 200, data: TM }] });
  await ishga(m, "showBrakModal('ishlab')");
  const optsC = m.el['brak-fp'].innerHTML;
  tekshir("T5 «Ishlab chiqarishda» → ro'yxatda faqat ishlab chiqariladigan turlar (profil, panel, dona, blok, MRP), qaytgan MRP YO'Q; "
          + "izoh «mahsulot soni o'zgarmaydi»",
          optsC.includes('value="1"') && optsC.includes('value="5"') && !optsC.includes('value="4"')
          && korinadi(m.el['loss-info-production']) && !korinadi(m.el['loss-info-stock']), qisqa(optsC));
  m.el['brak-fp'].value = '5';
  await ishga(m, 'brakFpTanla()');
  m.el['loss-qty'].value = '20';
  m.el['brak-cause'].value = 'uskuna';
  m.el['brak-worker'].value = '9';
  r = await ishga(m, 'brakSaqlash()');
  const t2 = (m.sorovlar[1] || {}).tana || {};
  tekshir("T6 → POST /api/finished/production-brak {finished_product_id 5, brak_qty 20 (qoldiqdan ko'p ham mumkin), notes, "
          + "brak_sabab, brak_javobgar_id}",
          !r.xato && m.sorovlar[1] && m.sorovlar[1].url === '/api/finished/production-brak' && t2.finished_product_id === 5
          && t2.brak_qty === 20 && t2.notes === null && t2.brak_sabab === 'uskuna' && t2.brak_javobgar_id === 9,
          r.xato || qisqa(m.sorovlar));
  // sabab majburiy (B / C)
  m = oyna({ javoblar: [{ status: 200, data: TM }] });
  await ishga(m, "showBrakModal('ombor')");
  m.el['brak-fp'].value = '1';
  await ishga(m, 'brakFpTanla()');
  m.el['loss-qty'].value = '1';
  r = await ishga(m, 'brakSaqlash()');
  tekshir("T7 sabab tanlanmagan — so'rov YO'Q, «Brak sababini tanlang (ro'yxatdan)», maydonga fokus",
          !r.xato && m.sorovlar.length === 1 && m.xabarlar.some((x) => x.t === "Brak sababini tanlang (ro'yxatdan)")
          && m.el['brak-cause']._fokus === 1, r.xato || qisqa(m.xabarlar));
  // mahsulot tanlanmagan
  m = oyna({ javoblar: [{ status: 200, data: TM }] });
  await ishga(m, "showBrakModal('ombor')");
  m.el['loss-qty'].value = '1';
  m.el['brak-cause'].value = 'boshqa';
  r = await ishga(m, 'brakSaqlash()');
  tekshir("T8 mahsulot tanlanmagan — so'rov YO'Q, «Tayyor mahsulotni tanlang»",
          !r.xato && m.sorovlar.length === 1 && m.xabarlar.some((x) => x.t === 'Tayyor mahsulotni tanlang'), r.xato || qisqa(m.xabarlar));
  // ruxsat yo'q
  m = oyna({ javoblar: [{ status: 403, data: { detail: 'x' } }] });
  await ishga(m, "showBrakModal('ombor')");
  tekshir("T9 /api/finished 403 — ro'yxatda «Tayyor mahsulotlarni ko'rishga ruxsat yo'q»",
          m.el['brak-fp'].innerHTML.replace(/&#39;/g, "'").includes("Tayyor mahsulotlarni ko'rishga ruxsat yo'q"), qisqa(m.el['brak-fp'].innerHTML));
}

async function minusBolimi() {
  bolim("Tayyor mahsulotlar «−» → SHU oyna (mahsulot tanlangan; A yo'li yo'q)");
  let m = oyna({ yoq: ['brak-project', 'brakList', 'brak-panel-project', 'brak-manba-buyurtma'] });
  let r = await ishga(m, "openLossModal(7, 'Karniz K7', 3, 'm', 'Profil')");
  tekshir("M1 ochiladi: «Omborda turgan» tanlangan, «Ishlab chiqarishda» bor (profil), mahsulot qotirilgan (tanlash yashirin, nomi "
          + "ko'rinadi), /api/finished so'ralmaydi, «Omborda: 3 m»",
          !r.xato && m.el.brakModal.style.display === 'flex' && m.radiolar.find((x) => x.value === 'ombor').checked
          && korinadi(m.el['brak-manba-ishlab']) && !korinadi(m.el['brak-fp-tanlash']) && korinadi(m.el['brak-fp-nomi'])
          && m.el['brak-fp-nomi'].textContent === 'Karniz K7' && !m.sorovlar.length
          && m.el['loss-stock-info'].textContent === 'Omborda: 3 m', r.xato || qisqa(m.el['loss-stock-info']));
  m.el['loss-qty'].value = '1';
  m.el['brak-cause'].value = 'xomashyo';
  r = await ishga(m, "setLossMode('production'); brakSaqlash()");
  const t = (m.sorovlar[0] || {}).tana || {};
  tekshir("M2 setLossMode('production') → «Ishlab chiqarishda»; saqlash → POST /api/finished/production-brak (mahsulot 7)",
          !r.xato && m.radiolar.find((x) => x.value === 'ishlab').checked && m.sorovlar.length === 1
          && m.sorovlar[0].url === '/api/finished/production-brak' && t.finished_product_id === 7 && t.brak_qty === 1
          && t.brak_sabab === 'xomashyo', r.xato || qisqa(m.sorovlar));
  m = oyna({ yoq: ['brak-project', 'brakList', 'brak-panel-project', 'brak-manba-buyurtma'] });
  r = await ishga(m, "openLossModal(8, 'Qaytgan', 2, 'dona', 'mrp_product')");
  tekshir("M3 ishlab chiqarilmaydigan tur (qaytgan MRP) — «Ishlab chiqarishda» yo'li yashirin",
          !r.xato && !korinadi(m.el['brak-manba-ishlab']) && korinadi(m.el['brak-manba-ombor']), r.xato);
  m.el['loss-qty'].value = '2';
  m.el['brak-cause'].value = 'boshqa';
  r = await ishga(m, 'brakSaqlash()');
  tekshir("M4 → POST /api/finished/loss (mahsulot 8, 2 dona); muvaffaqiyat — oyna yopiladi, xabar",
          !r.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/finished/loss' && m.sorovlar[0].tana.quantity === 2
          && m.el.brakModal.style.display === 'none' && m.xabarlar.some((x) => x.tur === 'success'), r.xato || qisqa(m.xabarlar));
  m = oyna({ yoq: ['brak-project', 'brakList', 'brak-panel-project', 'brak-manba-buyurtma'] });
  r = await ishga(m, "openLossModal(8, 'X', 2, 'dona', 'mrp_product'); brakManbaTanla('buyurtma'); closeLossModal()");
  tekshir("M5 A yo'li sahifada yo'q — tanlab bo'lmaydi; closeLossModal oynani yopadi",
          !r.xato && m.radiolar.find((x) => x.value === 'ombor').checked && m.el.brakModal.style.display === 'none', r.xato);
  m = oyna({ yoq: ['brak-project', 'brakList', 'brak-panel-project', 'brak-manba-buyurtma'],
    javoblar: [{ status: 400, data: { success: false, message: 'Omborda yetarli emas' } }] });
  await ishga(m, "openLossModal(9, 'Y', 3, 'm', 'panel')");
  m.el['loss-qty'].value = '1';
  m.el['brak-cause'].value = 'boshqa';
  r = await ishga(m, 'brakSaqlash()');
  tekshir("M6 server rad etsa — SABABI ko'rsatiladi, oyna ochiq qoladi",
          !r.xato && m.xabarlar.some((x) => x.t === 'Omborda yetarli emas' && x.tur === 'error') && m.el.brakModal.style.display === 'flex',
          r.xato || qisqa(m.xabarlar));
}

async function qaytarishBolimi() {
  bolim("returns.html «Yangi qaytarish» — FAQAT butun mahsulot");
  // kech120 (zip 133 — G5-05, MOSLANDI): «Qiymati» endi umumiy pul qoidasi bilan o'qiladi (`parseNum`) — funksiya ham olinadi
  const kod = ['saveReturn', 'updateReasonHint', 'parseNum'].map((n) => olib(RETURNS, n));
  tekshir('Q0 saveReturn, updateReasonHint topildi', kod.every(Boolean));
  if (!kod.every(Boolean)) return;
  const el = {};
  for (const [id, v] of [['f-order', '7'], ['f-item', '11'], ['f-qty', '2'], ['add-error', ''], ['return-save-btn', 'Saqlash'],
    ['f-value', '5000'], ['f-notes', 'izoh'], ['reason-hint', ''], ['f-brak-cause', 'uskuna'], ['f-brak-stage', 'kesish']]) el[id] = element(id, v);
  const sorovlar = [];
  const ctx = {
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, Array, Object,
    document: {
      getElementById: (id) => el[id] || null,
      querySelector: (sel) => (sel === 'input[name="f-reason"]:checked' ? { value: 'Ortiqcha' } : (sel.includes('f-coating-applied') ? { value: 'yes' } : null)),
    },
    fetch: async (u, f) => { sorovlar.push({ url: u, tana: JSON.parse(f.body) }); return { ok: true, status: 200, json: async () => ({}) }; },
    location: { reload() {} }, currentOrderItems: [{ id: 11, name: 'D', order_qty_normalized: 10, delivery_unit: 'metr' }],
    isSavingReturn: false,
  };
  vm.createContext(ctx);
  let xato = null;
  try { vm.runInContext(kod.join('\n'), ctx); await vm.runInContext('saveReturn()', ctx); vm.runInContext('updateReasonHint()', ctx); } catch (e) { xato = String(e.message || e); }
  const t = (sorovlar[0] || {}).tana || {};
  tekshir("Q1 tana: reason «Ortiqcha», to_stock true, coating_applied false; brak_* kalitlari YO'Q (sahifada eski maydon bo'lsa ham)",
          !xato && sorovlar.length === 1 && t.reason === 'Ortiqcha' && t.to_stock === true && t.coating_applied === false
          && !Object.keys(t).some((k) => k.startsWith('brak_')), xato || qisqa(t));
  tekshir("Q2 maslahat: butun mahsulot omborga qaytadi; brak — «Brak yozish»",
          el['reason-hint'].textContent.includes('Butun mahsulot') && el['reason-hint'].textContent.includes('«Brak yozish»'),
          el['reason-hint'].textContent);
}

(async function () {
  try {
    await asosBolimi();
    await buyurtmaBolimi();
    await tmBolimi();
    await minusBolimi();
    await qaytarishBolimi();
  } catch (e) {
    tekshir('kutilmagan istisno', false, String((e && e.stack) || e).slice(0, 400));
  }
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})();
