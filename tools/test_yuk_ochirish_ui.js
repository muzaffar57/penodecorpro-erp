#!/usr/bin/env node
/**
 * test_yuk_ochirish_ui.js — kech38 (2026-09-23), 5-bo'lim 12-band:
 * to'lov bog'langan yuk xatini o'chirish UI si.
 *
 *   templates/orders.html — `deleteDelivery`, `showConfirmModal` (ixtiyoriy
 *                           uchinchi tugma `altText`), `yetkazishXatoQismlari`,
 *                           `#genericConfirmAlt` tugmasi
 *   templates/base.html   — `escapeHtml`
 *
 * NIMA UCHUN KERAK (asl kod `c7a11f3` da O'LCHANGAN, jonli sinov saytida ham)
 * --------------------------------------------------------------------------
 * `DELETE /api/deliveries/{id}` to'lov bog'langan yukda HAQIQIY PostgreSQL da
 * 500 berardi, `deleteDelivery` esa `!res.ok` da HECH QANDAY xabar
 * ko'rsatmasdi (jonli: tasdiq oynasi chiqdi, keyin — hech narsa).
 * FOYDALANUVCHI QARORI (kech38): "Har safar so'rasin". Endi server 409
 * (`detail.type = "delivery_has_payment"`) qaytaradi va UI uch tugmali oyna
 * ko'rsatadi: "To'lovni ham o'chirish" → `?tolov=ochir`, "To'lovni saqlab
 * qolish" → `?tolov=qoldir`, "Bekor qilish" → hech narsa yuborilmaydi.
 * Har rad javobida server SABABI ko'rsatiladi; ikkinchi so'rov ham rad
 * etilsa — faqat xabar (qayta so'rash sikli yo'q).
 *
 * `showConfirmModal` uchinchi tugmasi faqat `altText` berilganda ko'rinadi —
 * qolgan hamma chaqiruvlar (tugmasiz) avvalgidek true / false qaytaradi.
 *
 * ISHLATISH:  node tools/test_yuk_ochirish_ui.js [boshqa/orders.html] [boshqa/base.html]
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
const ORDERS = oqi(process.argv[2] || path.join(ROOT, 'templates', 'orders.html'));
const BASE = oqi(process.argv[3] || path.join(ROOT, 'templates', 'base.html'));

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

function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
  if (!m) return null;
  const i = m.index;
  // Parametrlar ro'yxatini o'tkazib yuborish (`options = {}` kabi standart
  // qiymatdagi qavs tana boshi deb olinmasin).
  let p = 1, k0 = i + m[0].length;
  for (; k0 < src.length && p > 0; k0++) {
    if (src[k0] === '(') p++;
    else if (src[k0] === ')') p--;
  }
  let d = 0;
  const j = src.indexOf('{', k0);
  if (j < 0) return null;
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(i, k + 1); }
  }
  return null;
}

function javob(status, data, jsonEmas) {
  const r = {
    ok: status >= 200 && status < 300,
    status,
    json: async () => { if (jsonEmas) throw new Error('JSON emas'); return JSON.parse(JSON.stringify(data)); },
  };
  r.clone = () => javob(status, data, jsonEmas);
  return r;
}

const YUK_XABAR = "Bu yuk xatiga (ORD-051-3/Y-2) 500,000 so'm to'lov bog'langan.\n\nTo'lov ham o'chirilsinmi yoki saqlab qolinsinmi?";
const J409 = () => javob(409, { detail: { type: 'delivery_has_payment', message: YUK_XABAR,
                                          delivery_number: 'ORD-051-3/Y-2',
                                          payments: [{ id: 143, amount: 500000 }], total: 500000 } });

/** `tasdiqlar` — showConfirmModal ga ketma-ket javoblar (true / false / 'alt'). */
function muhit(o) {
  const javoblar = o.javoblar || [];
  const tasdiqJavob = (o.tasdiqlar || []).slice();
  const sorovlar = [], xabarlar = [], tasdiqlar = [], hodisalar = [];
  let ji = 0;
  const ctx = {
    console, JSON, String, Number, Math, Promise, Array, Object, Error,
    selectedOrderId: 42,
    fetch: async (url, opts) => {
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET' });
      const j = ji < javoblar.length ? javoblar[ji++] : javob(599, { detail: "kutilmagan so'rov" });
      if (j === 'otadi') throw new Error('tarmoq');
      return j;
    },
    showMsg: (t, tur) => { xabarlar.push({ t: String(t), tur }); },
    showConfirmModal: async (m, op) => {
      tasdiqlar.push({ m: String(m), o: op || {} });
      return tasdiqJavob.length ? tasdiqJavob.shift() : false;
    },
    loadDeliveries: (id) => { hodisalar.push('loadDeliveries:' + id); },
    loadPayments: (id) => { hodisalar.push('loadPayments:' + id); },
  };
  vm.createContext(ctx);
  return { ctx, sorovlar, xabarlar, tasdiqlar, hodisalar };
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

const F_DEL = olib(ORDERS, 'deleteDelivery');
const F_XQ = olib(ORDERS, 'yetkazishXatoQismlari');
const F_SCM = olib(ORDERS, 'showConfirmModal');
const F_ESC = olib(BASE, 'escapeHtml');
const KOD = [F_XQ, F_DEL].filter(Boolean).join('\n');

async function del(o) {
  const m = muhit(o);
  const r = await ishga(m, KOD, 'deleteDelivery(7)');
  return Object.assign(m, r);
}

async function asosiy() {
  bolim('0. Funksiyalar topildi');
  tekshir('orders.html: deleteDelivery / yetkazishXatoQismlari / showConfirmModal', !!(F_DEL && F_XQ && F_SCM));
  tekshir('base.html: escapeHtml', !!F_ESC);

  bolim('D. deleteDelivery');
  let m = await del({ tasdiqlar: [false] });
  tekshir('D1 birinchi tasdiq "Bekor" → so\'rov YO\'Q, xabar YO\'Q',
    !m.xato && m.sorovlar.length === 0 && m.xabarlar.length === 0, qisqa([m.xato, m.sorovlar]));

  m = await del({ tasdiqlar: [true], javoblar: [javob(200, { status: 'ok', tolov_ochirildi: 0, tolov_saqlandi: 0 })] });
  tekshir('D2 to\'lovsiz yuk 200 → bitta DELETE /api/deliveries/7 (parametrsiz)',
    !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/deliveries/7'
    && m.sorovlar[0].method === 'DELETE', qisqa([m.xato, m.sorovlar]));
  tekshir('D2 ro\'yxat yangilandi, to\'lovlar ro\'yxatiga TEGILMADI, xabar "✓ O\'chirildi"',
    m.hodisalar.join() === 'loadDeliveries:42' && m.xabarlar.length === 1
    && m.xabarlar[0].t === "✓ O'chirildi" && m.xabarlar[0].tur === 'success', qisqa([m.hodisalar, m.xabarlar]));

  m = await del({ tasdiqlar: [true, true], javoblar: [J409(), javob(200, { status: 'ok', tolov_ochirildi: 1 })] });
  tekshir('D3 409 → ikkinchi oyna: server xabari AYNAN, 3 tugma (ok / alt / bekor)',
    !m.xato && m.tasdiqlar.length === 2 && m.tasdiqlar[1].m === YUK_XABAR
    && m.tasdiqlar[1].o.okText === "To'lovni ham o'chirish" && m.tasdiqlar[1].o.altText === "To'lovni saqlab qolish"
    && m.tasdiqlar[1].o.danger === true, qisqa([m.xato, m.tasdiqlar]));
  tekshir('D3 "To\'lovni ham o\'chirish" → DELETE /api/deliveries/7?tolov=ochir',
    m.sorovlar.length === 2 && m.sorovlar[1].url === '/api/deliveries/7?tolov=ochir'
    && m.sorovlar[1].method === 'DELETE', qisqa(m.sorovlar));
  tekshir('D3 yuklar VA to\'lovlar ro\'yxati yangilandi, xabar "to\'lov o\'chirildi"',
    m.hodisalar.join() === 'loadDeliveries:42,loadPayments:42' && m.xabarlar.length === 1
    && m.xabarlar[0].tur === 'success' && m.xabarlar[0].t.includes("to'lov o'chirildi"), qisqa([m.hodisalar, m.xabarlar]));

  m = await del({ tasdiqlar: [true, 'alt'], javoblar: [J409(), javob(200, { status: 'ok', tolov_saqlandi: 1 })] });
  tekshir('D4 "To\'lovni saqlab qolish" → ?tolov=qoldir, xabar "saqlab qolindi"',
    !m.xato && m.sorovlar.length === 2 && m.sorovlar[1].url === '/api/deliveries/7?tolov=qoldir'
    && m.hodisalar.join() === 'loadDeliveries:42,loadPayments:42'
    && m.xabarlar.length === 1 && m.xabarlar[0].t.includes('saqlab qolindi'), qisqa([m.sorovlar, m.xabarlar]));

  for (const [nom, bekor] of [['false (Bekor)', false], ['undefined', undefined], ["'boshqa'", 'boshqa']]) {
    m = await del({ tasdiqlar: [true, bekor], javoblar: [J409()] });
    tekshir(`D5 ikkinchi oyna ${nom} → ikkinchi so'rov YO'Q, "bekor qilindi — hech narsa o'zgarmadi"`,
      !m.xato && m.sorovlar.length === 1 && m.hodisalar.length === 0 && m.xabarlar.length === 1
      && m.xabarlar[0].t.includes('bekor qilindi') && m.xabarlar[0].t.includes("o'zgarmadi"), qisqa([m.sorovlar, m.xabarlar]));
  }

  const radlar = [
    ['500 (asl kodda — jim edi)', javob(500, { detail: 'Serverda kutilmagan xato yuz berdi' }), '❌ Serverda kutilmagan xato yuz berdi'],
    ['404 matnli detail', javob(404, { detail: 'Yetkazish topilmadi' }), '❌ Yetkazish topilmadi'],
    ['400 obyekt detail', javob(400, { detail: { success: false, message: "'tolov' noto'g'ri qiymat" } }), "❌ 'tolov' noto'g'ri qiymat"],
    ['409 boshqa tur', javob(409, { detail: 'Boshqa ziddiyat' }), '❌ Boshqa ziddiyat'],
    ['502 JSON emas', javob(502, null, true), '❌ Xato'],
  ];
  for (const [nom, j, kutilgan] of radlar) {
    m = await del({ tasdiqlar: [true], javoblar: [j] });
    tekshir(`D6 ${nom} → xabar AYNAN server sababi, bitta so'rov, ro'yxat yangilanmadi`,
      !m.xato && m.sorovlar.length === 1 && m.tasdiqlar.length === 1 && m.hodisalar.length === 0
      && m.xabarlar.length === 1 && m.xabarlar[0].t === kutilgan && m.xabarlar[0].tur === 'error',
      qisqa([m.xato, m.xabarlar]));
  }

  m = await del({ tasdiqlar: [true], javoblar: ['otadi'] });
  tekshir('D7 tarmoq uzildi → "❌ Tarmoq xatosi"',
    !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].t === '❌ Tarmoq xatosi', qisqa(m.xabarlar));

  m = await del({ tasdiqlar: [true, true], javoblar: [J409(), javob(500, { detail: 'Serverda kutilmagan xato yuz berdi' })] });
  tekshir('D8 tanlovdan keyingi so\'rov 500 → xato xabari, jami 2 so\'rov, ro\'yxat yangilanmadi',
    !m.xato && m.sorovlar.length === 2 && m.hodisalar.length === 0 && m.xabarlar.length === 1
    && m.xabarlar[0].t === '❌ Serverda kutilmagan xato yuz berdi', qisqa([m.sorovlar, m.xabarlar]));

  m = await del({ tasdiqlar: [true, 'alt', true], javoblar: [J409(), J409(), javob(200, {})] });
  tekshir('D9 tanlovdan keyin YANA 409 → faqat xabar, qayta so\'ramaydi (2 so\'rov, 2 oyna)',
    !m.xato && m.sorovlar.length === 2 && m.tasdiqlar.length === 2 && m.xabarlar.length === 1
    && m.xabarlar[0].tur === 'error' && m.xabarlar[0].t.startsWith('❌ '), qisqa([m.sorovlar, m.xabarlar]));

  m = await del({ tasdiqlar: [true, true], javoblar: [J409(), 'otadi'] });
  tekshir('D10 tanlovdan keyin tarmoq uzildi → "❌ Tarmoq xatosi"',
    !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].t === '❌ Tarmoq xatosi', qisqa(m.xabarlar));

  bolim('M. showConfirmModal — ixtiyoriy uchinchi tugma');
  function el() { return { textContent: '', innerHTML: '', style: { display: 'none', background: '' }, onclick: null }; }
  function modalMuhit(altBor) {
    const qator = { style: { flexDirection: '' } };
    const e = {
      genericConfirmOverlay: el(), genericConfirmIcon: el(), genericConfirmTitle: el(), genericConfirmMsg: el(),
      genericConfirmOk: el(), genericConfirmCancel: el(),
    };
    if (altBor) e.genericConfirmAlt = el();
    e.genericConfirmOk.parentElement = qator;
    const ctx = { console, String, Promise, JSON,
      document: { getElementById: (id) => (Object.prototype.hasOwnProperty.call(e, id) ? e[id] : null) } };
    vm.createContext(ctx);
    let xato = null;
    try { vm.runInContext([F_ESC, F_SCM].filter(Boolean).join('\n'), ctx); } catch (er) { xato = String(er.message || er); }
    return { ctx, e, qator, xato };
  }
  async function bos(mm, chaqiruv, tugma) {
    try {
      const p = vm.runInContext(chaqiruv, mm.ctx);
      const oldin = { alt: mm.e.genericConfirmAlt ? { d: mm.e.genericConfirmAlt.style.display, t: mm.e.genericConfirmAlt.textContent,
                                                        on: typeof mm.e.genericConfirmAlt.onclick } : null,
                      yon: mm.qator.style.flexDirection, overlay: mm.e.genericConfirmOverlay.style.display,
                      msg: mm.e.genericConfirmMsg.innerHTML };
      const b = mm.e[tugma];
      if (b && typeof b.onclick === 'function') b.onclick();
      const natija = await Promise.race([p, new Promise((r) => setTimeout(() => r('KUTILMOQDA'), 200))]);
      return { oldin, natija, xato: null };
    } catch (er) { return { xato: String(er.message || er) }; }
  }

  let mm = modalMuhit(true);
  let b = await bos(mm, "showConfirmModal('<b>x</b>\\nY', {danger:true})", 'genericConfirmOk');
  tekshir('M1 altText siz: uchinchi tugma YASHIRIN, onclick yo\'q, qator yo\'nalishi o\'zgarmagan',
    !mm.xato && !b.xato && b.oldin.alt && b.oldin.alt.d === 'none' && b.oldin.alt.on !== 'function' && b.oldin.yon === '',
    qisqa([mm.xato, b]));
  tekshir('M1 "Ha" → true; xabar escape qilingan (<b> matn), \\n → <br>',
    b.natija === true && b.oldin.msg === '&lt;b&gt;x&lt;/b&gt;<br>Y', qisqa(b));
  b = await bos(mm, "showConfirmModal('Savol')", 'genericConfirmCancel');
  tekshir('M2 altText siz "Bekor" → false', b.natija === false, qisqa(b));

  b = await bos(mm, "showConfirmModal('Savol', {okText:'A', altText:'Saqlab qolish'})", 'genericConfirmAlt');
  tekshir('M3 altText bilan: tugma KO\'RINADI, matni AYNAN, qator ustunga (asosiy tepada)',
    !b.xato && b.oldin.alt.d === 'block' && b.oldin.alt.t === 'Saqlab qolish' && b.oldin.alt.on === 'function'
    && b.oldin.yon === 'column-reverse', qisqa(b));
  tekshir('M3 uchinchi tugma → natija \'alt\'', b.natija === 'alt', qisqa(b));
  tekshir('M3 yopilgach: oyna yashirin, alt yashirin va onclick yo\'q, qator asliga',
    mm.e.genericConfirmOverlay.style.display === 'none' && mm.e.genericConfirmAlt.style.display === 'none'
    && mm.e.genericConfirmAlt.onclick === null && mm.qator.style.flexDirection === '', qisqa(mm.e.genericConfirmAlt));
  b = await bos(mm, "showConfirmModal('Savol', {altText:'Saqlab qolish'})", 'genericConfirmOk');
  tekshir('M4 altText bilan "Ha" → true (alt emas)', b.natija === true, qisqa(b));
  b = await bos(mm, "showConfirmModal('Keyingi oddiy savol')", 'genericConfirmAlt');
  tekshir('M5 oldingi alt holati OQMAYDI: oddiy chaqiruvda alt yashirin va bosilganda javob YO\'Q',
    b.oldin.alt.d === 'none' && b.natija === 'KUTILMOQDA', qisqa(b));
  mm.e.genericConfirmCancel.onclick && mm.e.genericConfirmCancel.onclick();

  mm = modalMuhit(false);
  b = await bos(mm, "showConfirmModal('Savol', {altText:'X'})", 'genericConfirmOk');
  tekshir('M6 #genericConfirmAlt bo\'lmagan sahifa ham QULAMAYDI (himoya), "Ha" → true',
    !mm.xato && !b.xato && b.natija === true, qisqa([mm.xato, b]));

  bolim('S. Statik');
  const altSoni = (ORDERS.match(/id="genericConfirmAlt"/g) || []).length;
  tekshir('S1 orders.html: #genericConfirmAlt AYNAN 1 ta, boshlang\'ich holati yashirin',
    altSoni === 1 && /id="genericConfirmAlt" style="display:none;/.test(ORDERS), altSoni);
  tekshir('S2 deleteDelivery: oynaga server xabari (String(det.message)) — HTML qilib qurilmaydi',
    !!F_DEL && F_DEL.includes('showConfirmModal(String(det.message') && !F_DEL.includes('innerHTML'));
}

asosiy().catch((e) => { tekshir('kutilmagan istisno', false, String((e && e.stack) || e)); })
  .finally(() => {
    console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
    if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
    process.exitCode = FAIL === 0 ? 0 : 1;
  });
