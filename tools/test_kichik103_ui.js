#!/usr/bin/env node
/**
 * test_kichik103_ui.js — kech103 kichik bandlari (UI) darvozasi.
 *
 *   templates/orders.html   — `openDeliveryModal` (58 ortiqcha matni, 83 MRP tayyor, K103-3 birlik yorlig'i),
 *                             `saveDelivery` (83: tayyordan ko'p — yuborilmaydi), `loadDeliveries` (58 ro'yxat),
 *                             `checkDeliveredLimit` (58 / 63: kamida = topshirilgan + ortiqcha), `editSelected`
 *                             (K103-4 — topshirish holati detallar chizilishidan OLDIN o'qiladi, statik)
 *   templates/returns.html  — `deleteReturn` (90: MRP ortiqchasi tasdiqda)
 *   templates/finished.html — `openProfitModal` (62: narx farqi qatori; 66: MRP mahsulotida hajm / penoplast yo'q)
 *   templates/base.html     — `escapeHtml`
 *
 * NIMA UCHUN (asl kod `d081624` da HAQIQIY brauzerda O'LCHANGAN — `work/probe103ui.py`):
 *   T2d / T2j — 10 m dan 4 topshirilib 3 omborga ortiqcha qaytarilgan detal: oyna "Qoldi: 3 · Jami 10" (ortiqcha
 *   aytilmaydi), hammasi chiqqach "✅ To'liq topshirilgan" (7 topshirilgan); T2f — tahrirda 6 m (kamida 7) ogohlantirishsiz
 *   yuborildi (server 400); T3c / T3d — MRP 10 dan 4 tayyor: oyna tayyor miqdorni ko'rsatmaydi, birlik "ta" (m² o'rniga),
 *   6 kiritilsa so'rov serverga ketadi; T4d — MRP ortiqchasi tasdiqda yo'q; T5b — qatorlar 1 200 000, tan narxi 600 000;
 *   T6 — MRP mahsulotida "Hajm 0.0000 m³", "Penoplast 0"; T7 — tahrir oynasi oldingi buyurtmaning cheklovi bilan chizilardi.
 *
 * Funksiyalar HTML dan JONLI o'qiladi, soxta muhitda ishga tushiriladi; topilmagan funksiya yoki istisno — yiqilgan
 * tekshiruv (asl fayllarga qarshi ham QULAMAYDI).
 *
 *     node tools/test_kichik103_ui.js [orders.html returns.html finished.html base.html]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
function oqi(p) {
  try { return fs.readFileSync(p, 'utf8'); } catch (e) { return ''; }
}
const ORDERS = oqi(process.argv[2] || path.join(ROOT, 'templates', 'orders.html'));
const RETURNS = oqi(process.argv[3] || path.join(ROOT, 'templates', 'returns.html'));
const FINISHED = oqi(process.argv[4] || path.join(ROOT, 'templates', 'finished.html'));
const BASE = oqi(process.argv[5] || path.join(ROOT, 'templates', 'base.html'));

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
function matn(html) {
  return String(html || '').replace(/<[^>]*>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
}
function javob(status, data) {
  return { ok: status >= 200 && status < 300, status, json: async () => JSON.parse(JSON.stringify(data)) };
}
function el(extra) {
  return Object.assign({ value: '', textContent: '', innerHTML: '', style: {}, dataset: {}, disabled: false,
                         querySelector: () => null, querySelectorAll: () => [], scrollIntoView: () => {} }, extra || {});
}
function muhit(o) {
  const elementlar = o.elementlar || {};
  const javoblar = o.javoblar || [];
  const sorovlar = [], xabarlar = [], tasdiqlar = [];
  let ji = 0;
  const ctx = Object.assign({
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, Array, Object, Error, Set,
    document: {
      getElementById: (id) => (Object.prototype.hasOwnProperty.call(elementlar, id) ? elementlar[id] : null),
      querySelectorAll: (sel) => ((o.qsa && o.qsa[sel]) || []),
      querySelector: (sel) => ((o.qs && Object.prototype.hasOwnProperty.call(o.qs, sel)) ? o.qs[sel] : null),
    },
    fetch: async (url, opts) => {
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET' });
      if (typeof o.javobFn === 'function') return o.javobFn(String(url), opts);
      return ji < javoblar.length ? javoblar[ji++] : javob(599, {});
    },
    showMsg: (t) => { xabarlar.push(String(t)); },
    customConfirm: async (m) => { tasdiqlar.push(String(m)); return false; },
    showConfirmModal: async (m) => { tasdiqlar.push(String(m)); return false; },
    alert: () => {},
    location: { reload: () => {} },
    setTimeout: () => 0,
    formatNum: (n) => String(n),
    fmt: (n) => String(Math.round(n)),
    parseNum: (v) => parseFloat(String(v).replace(/\s/g, '')) || 0,
    sanitizeToLatin: (t) => t,
    renderDeliveryHistory: () => {},
  }, o.globallar || {});
  vm.createContext(ctx);
  return { ctx, sorovlar, xabarlar, tasdiqlar };
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

(async () => {
  // ═══════════════════════════════════════════════════════════
  bolim("A. 58 / 83 / K103-3 — yetkazish oynasi (openDeliveryModal)");
  // ═══════════════════════════════════════════════════════════
  const ODM = olib(ORDERS, 'openDeliveryModal');
  tekshir("A0 openDeliveryModal topildi", !!ODM);
  function odmMuhit(items) {
    const e = { dlvForm: el(), 'dlv-modal-sub': el(), 'dlv-debt-info': el(), 'dlv-received-by': el(), 'dlv-notes': el(),
                'dlv-payment-amount': el(), 'dlv-payment-method': el(), 'dlv-transport-carrier': el(),
                'dlv-transport-cost': el(), 'dlv-transport-payer': el(), 'dlv-payer-hint': el(), 'dlv-error': el(),
                dlvModal: el() };
    const m = muhit({ elementlar: e, javobFn: async () => javob(200, { debt_amount: 0 }),
                      globallar: { dlvData: { order_number: 'ORD-1', client_name: 'Mijoz', items }, selectedOrderId: 1 } });
    return { m, e };
  }
  {
    const { m, e } = odmMuhit([
      { id: 11, name: 'Karniz', unit: 'metr', ordered: 10, delivered: 4, remaining: 3, ortiqcha: 3, mrp_tayyor: null, is_done: false },
      { id: 12, name: 'Travertin', unit: 'm²', ordered: 10, delivered: 0, remaining: 10, ortiqcha: 0, mrp_tayyor: 4, is_done: false },
      { id: 13, name: 'Panel', unit: 'metr', ordered: 10, delivered: 7, remaining: 0, ortiqcha: 3, mrp_tayyor: null, is_done: true },
      { id: 14, name: 'Dona', unit: 'dona', ordered: 5, delivered: 5, remaining: 0, ortiqcha: 0, mrp_tayyor: null, is_done: true },
      { id: 15, name: 'MRP tayyor', unit: 'm²', ordered: 6, delivered: 0, remaining: 6, ortiqcha: 0, mrp_tayyor: 6, is_done: false },
    ]);
    const r = await ishga(m, ESC + '\n' + ODM, 'openDeliveryModal()');
    const h = e.dlvForm.innerHTML;
    const qatorlar = h.split('class="dlv-inp"');
    tekshir("A1 ishga tushdi", !r.xato, r.xato);
    tekshir("A2 ortiqchali, qolgan bor detal: 'omborga ortiqcha 3 metr' (asl: faqat 'Qoldi: 3 · Jami 10')",
      /Qoldi:\s*<b[^>]*>3 metr<\/b> · Jami 10 metr · 📦 omborga ortiqcha 3 metr/.test(h), matn(h));
    tekshir("A3 hammasi chiqqan ortiqchali detal: 'Yakunlangan: topshirilgan 7 metr · omborga ortiqcha 3' (asl: 'To'liq topshirilgan')",
      matn(h).includes("✅ Yakunlangan: topshirilgan 7 metr · 📦 omborga ortiqcha 3 metr"), matn(h));
    tekshir("A4 ortiqchasiz to'liq topshirilgan detal — '✅ To'liq topshirilgan' AYNAN",
      (h.match(/✅ To'liq topshirilgan/g) || []).length === 1, matn(h));
    tekshir("A5 MRP 4 / 10: '🏭 tayyor: 4 m²' qizil (kam)", /🏭 tayyor: <b style="color:#DC2626">4 m²<\/b>/.test(h), matn(h));
    tekshir("A6 MRP 6 / 6: tayyor yashil", /🏭 tayyor: <b style="color:#16A34A">6 m²<\/b>/.test(h), matn(h));
    tekshir("A7 MRP emas detalda 'tayyor' yo'q", !/Karniz[\s\S]*?tayyor:[\s\S]*?Travertin/.test(h), matn(h));
    tekshir("A8 kiritish maydonida data-tayyor (MRP 4, boshqasi bo'sh)", h.includes('id="dlv-12" data-max="10" data-tayyor="4"')
      && h.includes('id="dlv-11" data-max="3" data-tayyor=""'), h.slice(0, 300));
    tekshir("A9 birlik yorlig'i: metr → m, dona → ta, m² → m² (asl: m² ham 'ta')",
      /dlvStep\(12,1\)">\+<\/button>\s*<span[^>]*>m²<\/span>/.test(h) && /dlvStep\(11,1\)">\+<\/button>\s*<span[^>]*>m<\/span>/.test(h)
      && /dlvStep\(14,1\)">\+<\/button>\s*<span[^>]*>ta<\/span>/.test(h), qatorlar.length);
  }
  {
    const { m, e } = odmMuhit([
      { id: 21, name: '<img src=x onerror=alert(1)>', unit: '<b>', ordered: 10, delivered: 4, remaining: 3, ortiqcha: 3,
        mrp_tayyor: 2, is_done: false }]);
    const r = await ishga(m, ESC + '\n' + ODM, 'openDeliveryModal()');
    const h = e.dlvForm.innerHTML;
    tekshir("A10 nom / birlik HTML belgilari escape (ortiqcha va MRP matnida ham)", !r.xato && !h.includes('<img')
      && !h.includes('<b>') && h.includes('&lt;b&gt;'), h.slice(0, 400));
  }

  // ═══════════════════════════════════════════════════════════
  bolim("B. 83 — saveDelivery: MRP tayyordan ko'p kiritilsa yuborilmaydi");
  // ═══════════════════════════════════════════════════════════
  const SD = olib(ORDERS, 'saveDelivery');
  tekshir("B0 saveDelivery topildi", !!SD);
  const m_yub = { n: 0 };
  function sdMuhit(inplar) {
    m_yub.n = 0;
    const e = { 'dlv-error': el({ style: { display: 'none' } }), 'dlv-received-by': el(), 'dlv-notes': el(),
                'dlv-payment-amount': el(), 'dlv-payment-method': el({ value: 'naqd' }), 'dlv-transport-carrier': el(),
                'dlv-transport-cost': el(), 'dlv-transport-payer': el({ value: 'none' }) };
    return { m: muhit({ elementlar: e, qsa: { '.dlv-inp': inplar }, javobFn: async () => javob(200, { delivery_id: 1 }),
                        globallar: { selectedOrderId: 1, _dlvYuborilmoqda: false, __yuborildi: 0,
                                     yetkazishYubor: async () => { m_yub.n++; return null; } } }), e };
  }
  {
    const inp = el({ id: 'dlv-12', value: '6', dataset: { max: '10', tayyor: '4' } });
    const { m, e } = sdMuhit([inp]);
    const r = await ishga(m, SD, 'saveDelivery()');
    tekshir("B1 MRP 6 > tayyor 4 — so'rov YUBORILMADI, xato matni (asl: serverga ketardi)",
      !r.xato && m_yub.n === 0 && e['dlv-error'].style.display === 'block' && /tayyor miqdordan ko'p/.test(e['dlv-error'].textContent)
      && inp.style.borderColor === '#DC2626', { xato: r.xato, t: e['dlv-error'].textContent });
  }
  {
    const inp = el({ id: 'dlv-12', value: '4', dataset: { max: '10', tayyor: '4' } });
    const { m, e } = sdMuhit([inp]);
    const r = await ishga(m, SD, 'saveDelivery()');
    tekshir("B2 MRP 4 = tayyor — yuborishga o'tadi (yetkazishYubor chaqirildi)",
      !r.xato && m_yub.n === 1 && e['dlv-error'].style.display !== 'block', { xato: r.xato, n: m_yub.n, t: e['dlv-error'].textContent });
  }
  {
    const inp = el({ id: 'dlv-11', value: '3', dataset: { max: '3', tayyor: '' } });
    const { m, e } = sdMuhit([inp]);
    const r = await ishga(m, SD, 'saveDelivery()');
    tekshir("B3 MRP emas (data-tayyor bo'sh) — tayyor tekshiruvi yo'q", !r.xato && m_yub.n === 1,
      { xato: r.xato, n: m_yub.n, t: e['dlv-error'].textContent });
  }
  {
    const inp = el({ id: 'dlv-11', value: '5', dataset: { max: '3', tayyor: '' } });
    const { m, e } = sdMuhit([inp]);
    await ishga(m, SD, 'saveDelivery()');
    tekshir("B4 qoldiqdan ko'p — eski xabar AYNAN", e['dlv-error'].textContent === "❌ Qoldiqdan ko'p miqdor kiritilgan!",
      e['dlv-error'].textContent);
  }

  // ═══════════════════════════════════════════════════════════
  bolim("C. 58 — o'ng ro'yxat (loadDeliveries)");
  // ═══════════════════════════════════════════════════════════
  const LD = olib(ORDERS, 'loadDeliveries');
  tekshir("C0 loadDeliveries topildi", !!LD);
  {
    const e = { 'dlv-pct-text': el(), 'dlv-pct-bar': el(), 'dlv-pct-badge': el(), dlvItemList: el() };
    const m = muhit({ elementlar: e, javoblar: [javob(200, { delivery_percent: 70, is_fully_delivered: false, deliveries: [],
      items: [{ id: 1, name: 'K', unit: 'metr', ordered: 10, delivered: 7, remaining: 0, ortiqcha: 3, percent: 70, is_done: true },
              { id: 2, name: 'P', unit: 'metr', ordered: 5, delivered: 2, remaining: 3, ortiqcha: 0, percent: 40, is_done: false }] })] });
    const r = await ishga(m, ESC + '\nlet dlvData = null;\n' + LD, 'loadDeliveries(1)');
    const t = matn(e.dlvItemList.innerHTML);
    tekshir("C1 ortiqchali detal: '7 / 10 metr · 📦 omborga 3'", !r.xato && t.includes('7 / 10 metr · 📦 omborga 3'), t);
    tekshir("C2 ortiqchasiz: '2 / 5 metr' (qo'shimcha matnsiz)", /2 \/ 5 metr(?! ·)/.test(t), t);
  }

  // ═══════════════════════════════════════════════════════════
  bolim("D. 58 / 63 — tahrir: kamida = topshirilgan + ortiqcha (checkDeliveredLimit)");
  // ═══════════════════════════════════════════════════════════
  const CDL = olib(ORDERS, 'checkDeliveredLimit');
  tekshir("D0 checkDeliveredLimit topildi", !!CDL);
  function qator(type, qiymat, ds) {
    const inp = el({ value: String(qiymat), style: {} });
    const warn = el({ style: { display: 'none' }, textContent: '' });
    const typeEl = el({ value: type });
    const r = el({ dataset: Object.assign({}, ds) });
    r.querySelector = (sel) => (sel === '.i-type' ? typeEl : (sel === '.i-l' || sel === '.i-q') ? inp
      : sel === '.i-peno-warn' ? warn : null);
    return { r, inp, warn };
  }
  for (const [nom, q, ds, xato, kut] of [
    ['D1 6 m (4 topshirilgan + 3 ortiqcha = 7) — xato, matnda ikkalasi', 6, { delivered: '4', ortiqcha: '3', dlvUnit: 'metr' }, '1',
      "❌ 4 metr topshirilgan va 3 metr omborga ortiqcha qaytarilgan — kamida 7"],
    ['D2 7 m — xato yo\'q', 7, { delivered: '4', ortiqcha: '3', dlvUnit: 'metr' }, '', null],
    ['D3 faqat ortiqcha (topshirilgan 0, ortiqcha 3) — 2 m xato', 2, { delivered: '0', ortiqcha: '3', dlvUnit: 'metr' }, '1',
      "❌ 0 metr topshirilgan va 3 metr omborga ortiqcha qaytarilgan — kamida 3"],
    ['D4 ortiqchasiz 3 m (topshirilgan 4) — eski matn AYNAN', 3, { delivered: '4', dlvUnit: 'metr' }, '1',
      "❌ 4 metr topshirilgan — kamida shuncha bo'lishi kerak"],
  ]) {
    const { r, warn } = qator('profil', q, ds);
    const m = muhit({});
    const res = await ishga(m, CDL, '');
    m.ctx.__r = r;
    let x = null;
    try { vm.runInContext('checkDeliveredLimit(__r)', m.ctx); } catch (e) { x = String(e.message || e); }
    tekshir(nom, !res.xato && !x && (r.dataset.dlvError || '') === xato && (kut === null || warn.textContent === kut),
      { dlvError: r.dataset.dlvError, warn: warn.textContent, x });
  }

  // ═══════════════════════════════════════════════════════════
  bolim("E. K103-4 — tahrir oynasi: topshirish holati detallar chizilishidan OLDIN (statik)");
  // ═══════════════════════════════════════════════════════════
  const ES = olib(ORDERS, 'editSelected') || '';
  const iFetch = ES.indexOf("fetch(`/api/orders/${editId}/delivery-status`)");
  const iChiz = ES.indexOf("(window._dlvMap || {})[(item.name || '').trim().toLowerCase()]");
  tekshir("E1 delivery-status o'qilishi detallar chizilishidan OLDIN (asl: KEYIN)", iFetch > 0 && iChiz > 0 && iFetch < iChiz,
    { iFetch, iChiz });
  tekshir("E2 delivery-status editSelected ichida BIR marta o'qiladi",
    (ES.match(/\/api\/orders\/\$\{editId\}\/delivery-status/g) || []).length === 1);
  tekshir("E3 oldingi buyurtma xaritasi tozalanadi (window._dlvMap = {} — o'qishdan oldin)",
    ES.indexOf('window._dlvMap = {};') >= 0 && ES.indexOf('window._dlvMap = {};') < iFetch);
  tekshir("E5 xaritaga ortiqchali detal ham kiradi (topshirilmagan, faqat omborga ortiqcha)",
    ES.includes('if (i.delivered > 0 || i.ortiqcha > 0) window._dlvMap[i.name.trim().toLowerCase()] = i;'));
  tekshir("E6 detal qatori: cheklov ortiqchada ham qo'yiladi, dataset.ortiqcha yoziladi",
    ES.includes('if (dlvInfo && (dlvInfo.delivered > 0 || dlvInfo.ortiqcha > 0)) {')
    && ES.includes('row.dataset.ortiqcha = dlvInfo.ortiqcha || 0;'));
  tekshir("E4 nusxa (isDup) rejimida o'qilmaydi", /if \(!isDup\) \{\s*try \{\s*const dr0 = await fetch\(`\/api\/orders\/\$\{editId\}\/delivery-status`\)/.test(ES));

  // ═══════════════════════════════════════════════════════════
  bolim("F. 90 — Qaytarishlar: o'chirish tasdig'ida MRP ortiqchasi");
  // ═══════════════════════════════════════════════════════════
  const DR = olib(RETURNS, 'deleteReturn');
  tekshir("F0 deleteReturn topildi", !!DR);
  for (const [nom, ds, bor, yoq] of [
    ['F1 MRP ortiqchasi 3 m² — tasdiqda aytiladi', { reason: 'Ortiqcha', refund: 'no', stock: '4 m²', mrp: '3 m²' },
      ["📦 Omborga qo'shilgan 4 m²", "🏭 Ishlab chiqarish bandidan erkin qoldiqqa o'tkazilgan 3 m²"], []],
    ['F2 MRP ortiqchasiz — eski matn (qo\'shimcha qatorsiz)', { reason: 'Ortiqcha', refund: 'no', stock: '2 metr', mrp: '' },
      ["📦 Omborga qo'shilgan 2 metr"], ['🏭']],
  ]) {
    const m = muhit({ elementlar: { 'row-5': el({ dataset: ds }) }, globallar: { inFlightDeleteReturn: new Set() } });
    const r = await ishga(m, 'const inFlightDeleteReturn = new Set();\n' + DR, 'deleteReturn(5)');
    const t = m.tasdiqlar[0] || '';
    tekshir(nom, !r.xato && bor.every((b) => t.includes(b)) && yoq.every((y) => !t.includes(y))
      && m.sorovlar.length === 0, { xato: r.xato, t });
  }

  // ═══════════════════════════════════════════════════════════
  bolim("G. 62 / 66 — foyda oynasi (openProfitModal)");
  // ═══════════════════════════════════════════════════════════
  const OPM = olib(FINISHED, 'openProfitModal');
  const W2 = olib(FINISHED, 'fpWidth2') || 'function fpWidth2(){return null;}';
  tekshir("G0 openProfitModal topildi", !!OPM);
  async function opm(i, profit) {
    const e = { 'pm-sub': el(), profitModal: el(), 'pm-body': el() };
    const m = muhit({ elementlar: e, javobFn: async () => javob(200, profit), globallar: { fpItems: [i] } });
    const r = await ishga(m, ESC + '\n' + W2 + '\n' + OPM, `openProfitModal(${i.id})`);
    return { xato: r.xato, t: matn(e['pm-body'].innerHTML), h: e['pm-body'].innerHTML };
  }
  {
    const r = await opm({ id: 1, name: 'TM', unit: 'metr', quantity: 100, unit_price: 30000, cost_price: 600000, width: 20,
      thickness: 10, is_coated: true, category: 'profil', volume_m3: 1, actual_loy_kg: 50 },
      { success: true, penoplast_cost: 1000000, loy_cost: 200000, loy_cost_per_kg: 4000, loy_kg: 50, volume_m3: 1, recipe: 'R' });
    tekshir("G1 narx o'zgargan TM: 'Narx farqi' qatori −600 000 (qatorlar yig'indisi = tan narxi)", !r.xato
      && r.t.includes("↕ Narx farqi (qatorlar joriy narxda, tan narxi ishlab chiqarilgan paytda) -600000 so'm")
      && r.t.includes("Tan narxi 600000 so'm"), r.t);
    tekshir("G2 penoplast / loy qatorlari o'zgarmagan", r.t.includes("📦 Penoplast 1000000 so'm")
      && r.t.includes("🧱 Loy (50 kg × 4000) 200000 so'm") && r.t.includes('Hajm (qoldiq): 1.0000 m³'), r.t);
  }
  {
    const r = await opm({ id: 2, name: 'TM2', unit: 'metr', quantity: 100, unit_price: 30000, cost_price: 1200000, width: 20,
      thickness: 10, is_coated: true, category: 'profil', volume_m3: 1, actual_loy_kg: 50 },
      { success: true, penoplast_cost: 1000000, loy_cost: 200000, loy_cost_per_kg: 4000, loy_kg: 50, volume_m3: 1, recipe: 'R' });
    tekshir("G3 narx o'zgarmagan (yig'indi = tan narxi) — farq qatori YO'Q", !r.xato && !r.t.includes('Narx farqi'), r.t);
  }
  {
    const r = await opm({ id: 3, name: 'Travertin', unit: 'm²', quantity: 6, unit_price: 0, cost_price: 18000, is_coated: true,
      category: 'dynamic_bom', product_type_id: 7, volume_m3: 0, actual_loy_kg: 0 },
      { success: true, penoplast_cost: 0, loy_cost: 0, loy_cost_per_kg: 0, loy_kg: 0, volume_m3: 0, recipe: null });
    tekshir("G4 MRP: 'Hajm (qoldiq)' va 'Penoplast' YO'Q (asl: 0.0000 m³ / 0 so'm)", !r.xato && !r.t.includes('Hajm (qoldiq)')
      && !r.t.includes('Penoplast') && !r.t.includes('Narx farqi'), r.t);
    tekshir("G5 MRP: 'Xomashyo (retsept bo'yicha …)' = tan narxi", r.t.includes("🏭 Xomashyo (retsept bo'yicha, ishlab chiqarilgan paytda) 18000 so'm")
      && r.t.includes("Tan narxi 18000 so'm"), r.t);
  }
  {
    const r = await opm({ id: 4, name: 'P', unit: 'dona', quantity: 2, unit_price: 0, cost_price: 5000, is_coated: false,
      category: 'dona', product_type_id: 9, volume_m3: 0, actual_loy_kg: 0 },
      { success: true, penoplast_cost: 0, loy_cost: 0, loy_cost_per_kg: 0, loy_kg: 0, volume_m3: 0 });
    tekshir("G6 mahsulot turi (product_type_id) bor — MRP ko'rinishi", !r.xato && r.t.includes('🏭 Xomashyo') && !r.t.includes('Hajm (qoldiq)'), r.t);
  }

  // ═══════════════════════════════════════════════════════════
  bolim("H. 59 — o'chirish tasdig'i: qaytarish yozuvi bor buyurtma yumshoq o'chiriladi (deleteSelected)");
  // ═══════════════════════════════════════════════════════════
  const DS = olib(ORDERS, 'deleteSelected');
  tekshir("H0 deleteSelected topildi", !!DS);
  async function dsMatn(buyurtma) {
    const m = muhit({ javobFn: async () => javob(200, buyurtma), globallar: { selectedOrderId: 5 } });
    const r = await ishga(m, ESC + '\n' + DS, 'deleteSelected()');
    return { xato: r.xato, t: m.tasdiqlar[0] || '', sorovlar: m.sorovlar.map((x) => x.method + ' ' + x.url) };
  }
  {
    const r = await dsMatn({ order_number: 'ORD-59', status: 'in_progress', is_draft: false, paid_amount: 100000,
      delivery_percent: 0, ochirish: { yuk_bor: false, xomashyo_qaytadi: true, qisman: true, yumshoq: true, qaytarish_bor: true,
        yopiladi: false, hisobotda_qoladi: false, loy_sorov: false } });
    tekshir("H1 yetkazilmagan + ortiqcha qaytarish (server yumshoq): '🗂 … tarix sifatida «O'chirilganlar» da saqlanadi' qatori",
      !r.xato && r.t.includes("🗂 Buyurtmada qaytarish (ortiqcha / brak) yozuvi bor — buyurtma, qaytarish va to'lov yozuvlari tarix sifatida «O'chirilganlar» da saqlanadi (tiklash mumkin)."), r);
    tekshir("H2 … to'lov saqlanadi deyiladi, 'Butunlay o'chiriladi' / 'AVTOMATIK o'chadi' YO'Q",
      r.t.includes("💰 100000 so'm to'lov — hisobotlar uchun saqlanib qoladi") && !r.t.includes("Butunlay o'chiriladi")
      && !r.t.includes('AVTOMATIK o\'chadi'), r.t);
    tekshir("H3 tasdiqlanmadi — DELETE yuborilmadi", !r.sorovlar.some((x) => x.startsWith('DELETE')), r.sorovlar);
  }
  {
    const r = await dsMatn({ order_number: 'ORD-60', status: 'in_progress', is_draft: false, paid_amount: 100000,
      delivery_percent: 0, ochirish: { yuk_bor: false, xomashyo_qaytadi: true, qisman: false, yumshoq: false, qaytarish_bor: false,
        yopiladi: false, hisobotda_qoladi: false, loy_sorov: false } });
    tekshir("H4 qaytarishsiz (NAZORAT): 'Butunlay o'chiriladi' + to'lov AVTOMATIK o'chadi, 🗂 qatori YO'Q", !r.xato
      && r.t.includes("Butunlay o'chiriladi") && r.t.includes("AVTOMATIK o'chadi") && !r.t.includes('🗂'), r.t);
  }
  {
    const r = await dsMatn({ order_number: 'ORD-61', status: 'in_progress', is_draft: false, paid_amount: 0,
      delivery_percent: 40, ochirish: { yuk_bor: true, xomashyo_qaytadi: true, qisman: true, yumshoq: true, qaytarish_bor: true,
        yopiladi: false, hisobotda_qoladi: false, loy_sorov: false } });
    tekshir("H5 yuk xati bor (avvaldan yumshoq) — 🗂 qatori YO'Q (matn avvalgidek)", !r.xato && !r.t.includes('🗂')
      && r.t.includes('📦 Mahsulot qisman topshirilgan (40%).'), r.t);
  }

  // ═══════════════════════════════════════════════════════════
  bolim("I. 54 — qoplama retsepti majburiy (retseptMajburiyXatosi54, saveOrder, updateOrder)");
  // ═══════════════════════════════════════════════════════════
  const RMX = olib(ORDERS, 'retseptMajburiyXatosi54');
  tekshir("I0 retseptMajburiyXatosi54 topildi", !!RMX);
  function selEl(qiymat, variantlar) {
    return el({ value: qiymat, options: variantlar.map((v) => ({ value: v })) });
  }
  for (const [nom, sel, ac, loy, kut] of [
    ['I1 qoplamali, retsept tanlanmagan (ro\'yxatda bor) — "tanlang"', selEl('', ['', '1', '2']), true, 10,
      "Qoplama retsepti tanlanmagan — loy qaysi retseptdan tayyorlanishini «Retsept» maydonidan tanlang"],
    ['I2 qoplamali, korxonada retsept yo\'q — "yarating"', selEl('', ['']), true, 10,
      "Qoplama retsepti tanlanmagan — korxonada retsept yo'q: avval «Retseptlar» bo'limida retsept yarating"],
    ['I1b qoplamali, loy hali kiritilmagan (0) — retsept baribir SHART (loy xatosi alohida)', selEl('', ['', '1']), true, 0,
      "Qoplama retsepti tanlanmagan — loy qaysi retseptdan tayyorlanishini «Retsept» maydonidan tanlang"],
    ['I3 retsept tanlangan — xato yo\'q', selEl('2', ['', '1', '2']), true, 10, null],
    ['I4 qoplamasiz, loy 0 — xato yo\'q (retsept kerak emas)', selEl('', ['', '1']), false, 0, null],
    ['I5 qoplamasiz, lekin loy 5 — retsept SHART (server qoidasi bilan)', selEl('', ['', '1']), false, 5,
      "Qoplama retsepti tanlanmagan — loy qaysi retseptdan tayyorlanishini «Retsept» maydonidan tanlang"],
  ]) {
    const m = muhit({ elementlar: { recipe_id: sel } });
    const r = await ishga(m, RMX || '', `JSON.stringify(retseptMajburiyXatosi54(${ac}, ${loy}))`);
    const n = r.natija === undefined ? undefined : JSON.parse(r.natija);
    tekshir(nom, !r.xato && (kut === null ? n === null : (n && n.text === kut && n.targetId === 'recipe_id')), { xato: r.xato, n });
  }
  function formaMuhit(retsept, loy, ixtiyoriy) {
    const o = ixtiyoriy || {};
    const typeEl = el({ value: o.tur || 'profil' });
    const cEl = el({ value: o.qoplama === false ? 'false' : 'true' });
    const row = el({ dataset: o.fp ? { fpId: '7' } : {}, id: 'row-1' });
    row.querySelector = (s) => (s === '.i-type' ? typeEl : s === '.i-c' ? cEl : null);
    const e = { project_id: el({ value: '1' }), deadline_input: el({ value: '2026-10-01' }), loy_kg: el({ value: String(loy) }),
                recipe_id: selEl(retsept, ['', '3']), master_id: el({ value: '' }), final_price: el({ value: '0' }),
                zaklat_amount: el({ value: '0' }), zaklat_method: el({ value: 'naqd' }), base_price: el({ value: '0' }),
                resultBox: el() };
    const holat = { modal: [], yubor: [] };
    const m = muhit({ elementlar: e, qsa: { '.detal': [row] }, javobFn: async () => javob(200, { success: true }),
      globallar: { editMode: false, currentEditOrderId: null, DEFAULT_PENO_ID: null,
                   collectItems: () => [{ name: 'K', category: o.tur || 'profil', quantity: 1, is_coated: o.qoplama !== false }],
                   showValidationModal: (x) => { holat.modal.push(x); },
                   submitOrderRequest: async (d, isDraft) => { holat.yubor.push({ d, isDraft }); } } });
    return { m, holat };
  }
  const SO = olib(ORDERS, 'saveOrder');
  const UO = olib(ORDERS, 'updateOrder');
  tekshir("I6 saveOrder / updateOrder topildi", !!SO && !!UO);
  for (const [nom, retsept, loy, draft, bloklanadi, ixt] of [
    ["I7 yaratish: qoplamali, loy 10, retseptsiz — saqlanmaydi, oynada retsept xatosi (asl: yuborilardi)", '', 10, false, true, {}],
    ["I8 qoralama ham — saqlanmaydi", '', 10, true, true, {}],
    ["I9 retsept tanlangan — yuboriladi (recipe_id 3)", '3', 10, false, false, {}],
    ["I10 tayyor mahsulotdan olingan detal (qoplama loyi yo'q), loy 0 — retseptsiz yuboriladi (NAZORAT)", '', 0, false, false, { fp: true }],
  ]) {
    const { m, holat } = formaMuhit(retsept, loy, ixt);
    const r = await ishga(m, (RMX || '') + '\n' + (SO || ''), `saveOrder(${draft})`);
    const xatoMatn = JSON.stringify(holat.modal);
    tekshir(nom, !r.xato && (bloklanadi
      ? (holat.yubor.length === 0 && xatoMatn.includes('Qoplama retsepti tanlanmagan') && xatoMatn.includes('"targetId":"recipe_id"'))
      : (holat.yubor.length === 1 && holat.modal.length === 0 && (retsept ? holat.yubor[0].d.recipe_id === 3 : true))),
      { xato: r.xato, modal: holat.modal, yubor: holat.yubor.length });
  }
  for (const [nom, retsept, bloklanadi] of [
    ["I11 tahrir: qoplamali, loy 10, retseptsiz — tasdiq oynasigacha ham bormaydi, retsept xatosi (asl: PUT ketardi)", '', true],
    ["I12 tahrir: retsept tanlangan — odatdagi tasdiq oynasi", '3', false],
  ]) {
    const { m, holat } = formaMuhit(retsept, 10, {});
    const r = await ishga(m, (RMX || '') + '\n' + (UO || ''), 'updateOrder(9)');
    const xatoMatn = JSON.stringify(holat.modal);
    tekshir(nom, !r.xato && (bloklanadi
      ? (m.tasdiqlar.length === 0 && xatoMatn.includes('Qoplama retsepti tanlanmagan') && !m.sorovlar.some((x) => x.method === 'PUT'))
      : (m.tasdiqlar.length === 1 && m.tasdiqlar[0].includes("O'zgarishlar saqlansinmi?") && holat.modal.length === 0)),
      { xato: r.xato, modal: holat.modal, tasdiq: m.tasdiqlar, sorov: m.sorovlar });
  }
  tekshir("I13 forma: «Retsept» yorlig'ida 'qoplamali buyurtmada majburiy'",
    /<label>Retsept <span[^>]*>— qoplamali buyurtmada majburiy<\/span><\/label>\s*<select id="recipe_id"/.test(ORDERS));

  // ═══════════════════════════════════════════════════════════
  bolim("S. Statik");
  // ═══════════════════════════════════════════════════════════
  tekshir("S1 orders.html: submitFullDlvModal / saveDelivery da payment_warning tarmog'i yo'q (11)",
    !/if \(r\.payment_warning\)|r\.payment_warning \?/.test(olib(ORDERS, 'submitFullDlvModal') || 'if (r.payment_warning)')
    && !/if \(r\.payment_warning\)|r\.payment_warning \?/.test(SD || 'if (r.payment_warning)'));
  tekshir("S2 finished.html: showProfit yo'q (64)", FINISHED.length > 1000 && !/function\s+showProfit\s*\(/.test(FINISHED));

  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  process.exit(FAIL === 0 ? 0 : 1);
})();
