#!/usr/bin/env node
/**
 * test_yetkazish_ui.js — 17g (2026-09-22): yetkazish va brak yozish UI si.
 *
 *   templates/orders.html  — `yetkazishYubor`, `saveDelivery` ("Yetkazish"
 *                            oynasi), `submitFullDlvModal` ("Bir yo'la to'liq
 *                            topshirish"), `yetkazishXatoQismlari`
 *   templates/returns.html — `saveBrakBatch`, `brakServerSababi`, `closeBrakModal`
 *   templates/base.html    — `escapeHtml` (sahifalar undan meros oladi)
 *
 * NIMA UCHUN KERAK
 * ----------------
 * 1) `POST /api/deliveries` endi shu yukka bog'liq to'lovni qo'lda to'lov
 *    bilan AYNAN bir xil tekshiradi: qarzdan ko'p bo'lsa 409
 *    (`detail.type = "overpayment_warning"`) va HECH NARSA yozilmaydi.
 *    `yetkazishYubor` server savolini tasdiqlatadi: "Ha" → `confirm_overpay:
 *    true` bilan QAYTA, "Bekor" → `null` (yetkazish saqlanmagan). 17f da UI
 *    bu savolni "❌ ..." xato sifatida ko'rsatardi — mijoz qasddan ko'p
 *    (avans) to'lasa, yetkazishni UMUMAN kiritib bo'lmasdi.
 * 2) `saveBrakBatch` ilgari server rad etgan qatorni JIM tashlab, oynani
 *    yopib sahifani yangilardi — foydalanuvchi brak yozilmaganini bilmasdi.
 *    Endi har rad etilgan qatorning server SABABI ko'rsatiladi.
 * 3) kech26 da O'LCHANGAN va tuzatilgan (shu test ularni ushlaydi):
 *    a) `saveDelivery` server rad javobini `innerHTML` ga yozadi, `shortages`
 *       ichida esa detal NOMI bor. Nom HTML belgilari bilan AYNAN saqlanadi
 *       (`<img src=x onerror=...>` — bazaga tushadi) → endi `escapeHtml`.
 *    b) Sessiya tugaganda (401) `detail` MATN — ilgari "Xato" deb ko'rinardi.
 *    c) Server bir xil qisman yetkazishni ketma-ket ikki marta qabul qiladi
 *       (3 + 3 metr, to'lov ham ikki marta) — "Saqlash" tugmasini tez ikki
 *       bosish shunday natija berardi. Endi so'rov ketayotganda ikkinchi
 *       bosish e'tiborsiz (`_dlvYuborilmoqda`, ikkala yo'l uchun umumiy).
 *    d) Brak yozishda tarmoq qator o'rtasida uzilsa — oldin saqlanganlar
 *       hisobga olinmasdi (oyna yopilganda ro'yxat yangilanmasdi,
 *       foydalanuvchi qayta kiritib brakni ikki marta yozishi mumkin edi).
 * 4) Serverga ketadigan TANA o'zgarmagan bo'lishi SHART — qat'iy qoida uni
 *    aynan shu shaklda qabul qiladi (`tools/test_qaytarish_query.py` D va R
 *    bo'limlari xuddi shu tanalarni haqiqiy serverga yuboradi).
 *
 * QANDAY ISHLAYDI
 * ---------------
 * Funksiyalar HTML dan JONLI o'qiladi (`async` bilan), soxta muhitda
 * (document, fetch, showMsg, showConfirmModal, location, setTimeout, ...)
 * ishga tushiriladi. `sanitizeToLatin` — o'zgartirmaydigan soxta (bu test
 * tana SHAKLINI tekshiradi, kirill → lotin emas). Topilmagan funksiya yoki
 * ishga tushishdagi istisno — yiqilgan tekshiruv (asl faylga qarshi ham
 * QULAMAYDI).
 *
 * ISHLATISH
 * ---------
 *     node tools/test_yetkazish_ui.js
 *     node tools/test_yetkazish_ui.js boshqa/orders.html boshqa/returns.html [boshqa/base.html]
 *                                                              (mutatsiya uchun)
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
const ORDERS = oqi(process.argv[2] || path.join(ROOT, 'templates', 'orders.html'));
const RETURNS = oqi(process.argv[3] || path.join(ROOT, 'templates', 'returns.html'));
const BASE = oqi(process.argv[4] || path.join(ROOT, 'templates', 'base.html'));

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

// Funksiyani HTML dan nomi bo'yicha ajratib olish (`async` bilan).
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

// Soxta javob: `status`, `data` (JSON) yoki `jsonEmas: true`.
function javob(status, data, jsonEmas) {
  const r = {
    ok: status >= 200 && status < 300,
    status,
    json: async () => { if (jsonEmas) throw new Error('JSON emas'); return JSON.parse(JSON.stringify(data)); },
  };
  r.clone = () => javob(status, data, jsonEmas);
  return r;
}

// Test o'zi bo'shatguncha javob bermaydigan so'rov ("ikki marta bosish" uchun).
function kechik(j) {
  return { kechik: true, j, bosh: null };
}

// `innerHTML` dagi matn foydalanuvchiga qanday ko'rinadi.
function korinadi(html) {
  return String(html)
    .replace(/<br>/g, '\n')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&');
}

function element(qiymat) {
  return { value: qiymat, checked: false, textContent: '', innerHTML: '', style: { display: 'none' },
           dataset: {}, disabled: false };
}

/**
 * Umumiy muhit. `javoblar` — ketma-ket qaytariladigan javoblar ('otadi' —
 * tarmoq xatosi, `kechik(...)` — test bo'shatguncha kutadi), `tasdiq` —
 * tasdiq oynasi javobi. `qsa` / `qs` — `querySelectorAll` / `querySelector`.
 */
function muhit(o) {
  const elementlar = o.elementlar || {};
  const javoblar = o.javoblar || [];
  const sorovlar = [], xabarlar = [], tasdiqlar = [], alertlar = [], hodisalar = [], taymerlar = [];
  const kechikkanlar = [];
  let reload = 0, ji = 0;
  const ctx = Object.assign({
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, Array, Object, Error,
    document: {
      getElementById: (id) => (Object.prototype.hasOwnProperty.call(elementlar, id) ? elementlar[id] : null),
      querySelectorAll: (sel) => ((o.qsa && o.qsa[sel]) || []),
      querySelector: (sel) => ((o.qs && Object.prototype.hasOwnProperty.call(o.qs, sel)) ? o.qs[sel] : null),
    },
    fetch: async (url, opts) => {
      let tana = null;
      try { tana = opts && opts.body ? JSON.parse(opts.body) : null; } catch (e) { tana = 'JSON EMAS'; }
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET', tana,
                      headers: (opts && opts.headers) || null });
      hodisalar.push('fetch');
      const j = ji < javoblar.length ? javoblar[ji++] : javob(599, { detail: "kutilmagan so'rov" });
      if (j === 'otadi') throw new Error('tarmoq');
      if (j && j.kechik) {
        kechikkanlar.push(j);
        return new Promise((res) => { j.bosh = () => res(j.j); });
      }
      return j;
    },
    showMsg: (t, tur) => { xabarlar.push({ t: String(t), tur }); },
    showConfirmModal: async (m, op) => { tasdiqlar.push({ m: String(m), o: op }); return o.tasdiq; },
    customConfirm: async (m, op) => { tasdiqlar.push({ m: String(m), o: op }); return o.tasdiq; },
    alert: (m) => { alertlar.push(String(m)); },
    location: { reload: () => { reload++; hodisalar.push('reload'); } },
    setTimeout: (fn, ms) => { taymerlar.push({ fn, ms }); return taymerlar.length; },
    closeDeliveryModal: () => { hodisalar.push('closeDeliveryModal'); },
    closeFullDlvModal: () => { hodisalar.push('closeFullDlvModal'); },
    loadDeliveries: (id) => { hodisalar.push('loadDeliveries:' + id); },
    openPdfSafe: (url) => { hodisalar.push('openPdfSafe:' + url); },
    sanitizeToLatin: (t) => t,
    formatNum: (n) => String(n),
    fmt: (n) => String(n),
  }, o.globallar || {});
  vm.createContext(ctx);
  return {
    ctx, sorovlar, xabarlar, tasdiqlar, alertlar, hodisalar, taymerlar, kechikkanlar,
    reloadSoni: () => reload,
    soni: (h) => hodisalar.filter((x) => x === h).length,
  };
}

// Kodni yuklab, `chaqiruv` ni bajaradi → { xato, natija }.
async function ishga(m, kod, chaqiruv) {
  try {
    vm.runInContext(kod, m.ctx);
    const natija = await vm.runInContext(chaqiruv, m.ctx);
    return { xato: null, natija };
  } catch (e) {
    return { xato: String((e && e.message) || e), natija: undefined };
  }
}

function yukla(m, kod) {
  try { vm.runInContext(kod, m.ctx); return null; } catch (e) { return String((e && e.message) || e); }
}

async function chaqir(m, chaqiruv) {
  try { return { xato: null, natija: await vm.runInContext(chaqiruv, m.ctx) }; }
  catch (e) { return { xato: String((e && e.message) || e), natija: undefined }; }
}

// ══════════════════════════════════════════════════════════════
// orders.html
// ══════════════════════════════════════════════════════════════
const O_NOMLAR = ['parseNum', 'yetkazishXatoQismlari', 'yetkazishYubor', 'saveDelivery', 'submitFullDlvModal'];
const O_FN = O_NOMLAR.map((n) => olib(ORDERS, n));
const ESC = olib(BASE, 'escapeHtml');
const O_KOD = [ESC].concat(O_FN).filter(Boolean).join('\n');

const OVER_XABAR = "Kiritilgan summa (1,500,000 so'm) qarzdan (1,000,000 so'm) 500,000 so'mga ko'p. Shunday ham davom etasizmi?";
const OVER = { detail: { type: 'overpayment_warning', message: OVER_XABAR,
                         amount: 1500000, debt: 1000000, excess: 500000 } };
const OK_QISMAN = { success: true, message: 'Yetkazish saqlandi!', delivery_id: 91,
                    delivery_number: 'ORD-7-1/Y-2', delivery_percent: 40, is_fully_delivered: false };
const OK_TOLIQ = { success: true, message: 'Yetkazish saqlandi!', delivery_id: 92,
                   delivery_number: 'ORD-7-1/Y-3', delivery_percent: 100, is_fully_delivered: true };

// ── yetkazishYubor ──────────────────────────────────────────
const Y_DATA = { order_id: 55, items: [{ order_item_id: 701, quantity: 3 }], received_by: null, notes: null,
                 payment_amount: 1500000, payment_method: 'naqd', transport_carrier: null,
                 transport_cost: 0, transport_payer: 'none' };

async function ySina(javoblar, tasdiq, data) {
  const m = muhit({ javoblar, tasdiq, globallar: { __data: JSON.parse(JSON.stringify(data || Y_DATA)) } });
  const r = await ishga(m, O_KOD, 'yetkazishYubor(__data)');
  return Object.assign(m, r);
}

async function yetkazishYuborBolimi() {
  bolim("orders.html — yetkazishYubor (409 ortiqcha to'lov tasdig'i)");
  tekshir('Y yetkazishYubor topildi', !!O_FN[2]);
  tekshir('Y base.html escapeHtml topildi', !!ESC);

  let j200 = javob(200, OK_QISMAN);
  let m = await ySina([j200], true);
  tekshir("Y 200 → bitta so'rov POST /api/deliveries, JSON sarlavha, tana AYNAN, javob o'zi qaytadi",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/deliveries'
          && m.sorovlar[0].method === 'POST'
          && m.sorovlar[0].headers && m.sorovlar[0].headers['Content-Type'] === 'application/json'
          && JSON.stringify(m.sorovlar[0].tana) === JSON.stringify(Y_DATA)
          && m.natija === j200 && m.tasdiqlar.length === 0,
          m.xato || qisqa(m.sorovlar));

  j200 = javob(200, OK_QISMAN);
  m = await ySina([javob(409, OVER), j200], true);
  tekshir("Y 409 overpayment_warning → tasdiq AYNAN '⚠️ ' + server savoli (danger, 'Ha, davom etaman')",
          !m.xato && m.tasdiqlar.length === 1 && m.tasdiqlar[0].m === '⚠️ ' + OVER_XABAR
          && m.tasdiqlar[0].o && m.tasdiqlar[0].o.danger === true
          && m.tasdiqlar[0].o.okText === 'Ha, davom etaman',
          m.xato || qisqa(m.tasdiqlar));
  tekshir("Y 409 → \"Ha\" → IKKINCHI so'rov: o'sha URL, tana AYNAN + confirm_overpay true",
          m.sorovlar.length === 2 && m.sorovlar[1].url === '/api/deliveries' && m.sorovlar[1].method === 'POST'
          && JSON.stringify(m.sorovlar[0].tana) === JSON.stringify(Y_DATA)
          && JSON.stringify(m.sorovlar[1].tana) === JSON.stringify(Object.assign({}, Y_DATA, { confirm_overpay: true })),
          qisqa(m.sorovlar));
  tekshir('Y 409 → "Ha" → IKKINCHI javob qaytadi', m.natija === j200, qisqa(m.natija && m.natija.status));

  m = await ySina([javob(409, OVER)], false);
  tekshir("Y 409 → \"Bekor\" → null, bitta so'rov (hech narsa yozilmagan)",
          !m.xato && m.natija === null && m.sorovlar.length === 1 && m.tasdiqlar.length === 1,
          m.xato || qisqa([m.natija, m.sorovlar.length]));

  let j409 = javob(409, { detail: { message: "Boshqa to'qnashuv" } });
  m = await ySina([j409], true);
  tekshir("Y boshqa 409 (turi yo'q) → javob o'zgarishsiz, tasdiq so'ralmaydi",
          !m.xato && m.natija === j409 && m.tasdiqlar.length === 0 && m.sorovlar.length === 1,
          m.xato || qisqa([m.tasdiqlar, m.sorovlar.length]));

  j409 = javob(409, null, true);
  m = await ySina([j409], true);
  tekshir("Y 409 JSON emas → javob o'zgarishsiz, tasdiq yo'q, istisno yo'q",
          !m.xato && m.natija === j409 && m.tasdiqlar.length === 0 && m.sorovlar.length === 1,
          m.xato || qisqa([m.tasdiqlar, m.sorovlar.length]));

  j409 = javob(409, OVER);
  m = await ySina([j409], true, Object.assign({}, Y_DATA, { confirm_overpay: true }));
  tekshir("Y confirm_overpay allaqachon true → 409 da qayta so'ramaydi (sikl yo'q)",
          !m.xato && m.natija === j409 && m.tasdiqlar.length === 0 && m.sorovlar.length === 1,
          m.xato || qisqa([m.tasdiqlar, m.sorovlar.length]));

  const j409b = javob(409, OVER);
  m = await ySina([javob(409, OVER), j409b, javob(200, OK_QISMAN)], true);
  tekshir("Y \"Ha\" dan keyin yana 409 → uchinchi so'rov YO'Q, bitta tasdiq, ikkinchi javob qaytadi",
          !m.xato && m.sorovlar.length === 2 && m.tasdiqlar.length === 1 && m.natija === j409b,
          m.xato || qisqa([m.sorovlar.length, m.tasdiqlar.length]));

  const j400 = javob(400, { detail: { success: false, message: 'Qoralama buyurtmani yetkazib bo\'lmaydi' } });
  m = await ySina([j400], true);
  tekshir("Y 400 → javob o'zgarishsiz, tasdiq yo'q",
          !m.xato && m.natija === j400 && m.tasdiqlar.length === 0, m.xato || qisqa(m.tasdiqlar));

  m = await ySina(['otadi'], true);
  tekshir('Y tarmoq xatosi → istisno chaqiruvchiga o\'tadi (u "Server xatosi" ko\'rsatadi)',
          m.xato !== null && m.sorovlar.length === 1, qisqa([m.xato, m.sorovlar.length]));
}

// ── saveDelivery ────────────────────────────────────────────
function sElementlar(o) {
  return {
    'dlv-error': element(''),
    'dlv-received-by': element(o.olgan || ''),
    'dlv-notes': element(o.izoh || ''),
    'dlv-payment-amount': element(o.tolov || ''),
    'dlv-payment-method': element(o.usul === undefined ? 'naqd' : o.usul),
    'dlv-transport-carrier': element(o.tashuvchi || ''),
    'dlv-transport-cost': element(o.transport || ''),
    'dlv-transport-payer': element(o.tolovchi === undefined ? 'none' : o.tolovchi),
  };
}
function sInputlar(qiymatlar) {
  // [ [order_item_id, qiymat, max], ... ]
  return qiymatlar.map(([id, v, max]) => {
    const e = element(v);
    e.id = 'dlv-' + id;
    e.dataset = { max: String(max) };
    e.style = {};
    return e;
  });
}

function sMuhit(o, javoblar, tasdiq = true) {
  const el = sElementlar(o);
  const inp = sInputlar(o.inputlar || [[701, '2.5', 10]]);
  const m = muhit({ elementlar: el, javoblar, tasdiq, qsa: { '.dlv-inp': inp },
                    globallar: { selectedOrderId: o.buyurtma === undefined ? 55 : o.buyurtma,
                                 _dlvYuborilmoqda: false } });
  return Object.assign(m, { err: el['dlv-error'], inp, kodXato: yukla(m, O_KOD) });
}

async function sSina(o, javoblar, tasdiq = true) {
  const m = sMuhit(o, javoblar, tasdiq);
  const r = await chaqir(m, 'saveDelivery()');
  return Object.assign(m, { xato: m.kodXato || r.xato });
}

const S_MIN = { order_id: 55, items: [{ order_item_id: 701, quantity: 2.5 }], received_by: null, notes: null,
                payment_amount: null, payment_method: 'naqd', transport_carrier: null, transport_cost: 0,
                transport_payer: 'none' };

async function saveDeliveryBolimi() {
  bolim('orders.html — saveDelivery ("Yetkazish" oynasi)');
  tekshir('S parseNum / yetkazishXatoQismlari / yetkazishYubor / saveDelivery / submitFullDlvModal topildi',
          O_FN.every(Boolean), O_NOMLAR.filter((n, i) => !O_FN[i]).join(' '));

  let m = await sSina({ buyurtma: null }, [javob(200, OK_QISMAN)]);
  tekshir("S buyurtma tanlanmagan → so'rov yo'q", !m.xato && m.sorovlar.length === 0,
          m.xato || qisqa(m.sorovlar));

  m = await sSina({}, [javob(200, OK_QISMAN)]);
  tekshir("S minimal: bitta so'rov, tana AYNAN (bo'sh maydonlar null, parseNum('') = 0)",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/deliveries'
          && JSON.stringify(m.sorovlar[0].tana) === JSON.stringify(S_MIN),
          m.xato || qisqa(m.sorovlar));

  m = await sSina({ olgan: '  Vali  ', izoh: ' QY izoh ', tolov: '100 000', usul: 'plastik', tashuvchi: 'Ali',
                    transport: '50 000', tolovchi: 'split', inputlar: [[701, '3', 10], [702, '', 5], [703, '1.5', 4]] },
                  [javob(200, OK_QISMAN)]);
  tekshir("S to'liq: bo'sh miqdorli qator tashlanadi, matn trim, summa parseNum — tana AYNAN",
          !m.xato && m.sorovlar.length === 1 && JSON.stringify(m.sorovlar[0].tana) === JSON.stringify({
            order_id: 55, items: [{ order_item_id: 701, quantity: 3 }, { order_item_id: 703, quantity: 1.5 }],
            received_by: 'Vali', notes: 'QY izoh', payment_amount: 100000, payment_method: 'plastik',
            transport_carrier: 'Ali', transport_cost: 50000, transport_payer: 'split' }),
          m.xato || qisqa(m.sorovlar));

  m = await sSina({}, [javob(200, OK_QISMAN)]);
  tekshir('S 200 (qisman) → oyna yopiladi, nakladnoy ochiladi, ro\'yxat yangilanadi, yashil xabar',
          !m.xato && m.soni('closeDeliveryModal') === 1 && m.soni('openPdfSafe:/api/deliveries/91/pdf') === 1
          && m.soni('loadDeliveries:55') === 1 && m.xabarlar.length === 1 && m.xabarlar[0].tur === 'success'
          && m.xabarlar[0].t === '✓ ORD-7-1/Y-2 saqlandi · Bajarilish: 40%' && m.taymerlar.length === 0,
          m.xato || qisqa([m.hodisalar, m.xabarlar]));

  m = await sSina({}, [javob(200, OK_TOLIQ)]);
  const reloadTaymer = m.taymerlar.find((t) => t.ms === 2500);
  if (reloadTaymer) { try { reloadTaymer.fn(); } catch (e) { /* tekshiruvda ko'rinadi */ } }
  tekshir("S 200 (to'liq) → \"to'liq topshirildi\" xabari, 2.5 s dan keyin sahifa yangilanadi",
          !m.xato && m.soni('closeDeliveryModal') === 1 && m.xabarlar.length === 1
          && m.xabarlar[0].t === "✅ Buyurtma to'liq topshirildi! Nakladnoy tayyor."
          && !!reloadTaymer && m.reloadSoni() === 1,
          m.xato || qisqa([m.xabarlar, m.taymerlar.map((t) => t.ms)]));

  m = await sSina({ tolov: '1 500 000' }, [javob(409, OVER)], false);
  tekshir("S 409 → tasdiq → \"Bekor\": oyna OCHIQ qoladi, xabar yo'q, xato maydoni yashirin",
          !m.xato && m.sorovlar.length === 1 && m.tasdiqlar.length === 1
          && m.tasdiqlar[0].m === '⚠️ ' + OVER_XABAR && m.soni('closeDeliveryModal') === 0
          && m.xabarlar.length === 0 && m.err.style.display === 'none' && m.err.innerHTML === ''
          && m.err.textContent === '',
          m.xato || qisqa([m.sorovlar.length, m.tasdiqlar, m.hodisalar, m.xabarlar, m.err]));

  m = await sSina({ tolov: '1 500 000' }, [javob(409, OVER), javob(200, OK_QISMAN)], true);
  tekshir('S 409 → "Ha" → confirm_overpay true bilan qayta → 200: oyna yopiladi, yashil xabar',
          !m.xato && m.sorovlar.length === 2 && m.sorovlar[1].tana && m.sorovlar[1].tana.confirm_overpay === true
          && m.sorovlar[1].tana.payment_amount === 1500000 && m.soni('closeDeliveryModal') === 1
          && m.xabarlar.length === 1 && m.xabarlar[0].tur === 'success',
          m.xato || qisqa([m.sorovlar, m.hodisalar, m.xabarlar]));

  const KAM = ["Qoldiqdan ko'p berib bo'lmaydi!",
               ["QY_D1_0: 6 metr berilmoqchi, lekin qoldi 4 metr", 'QY_D1_1: 2 dona berilmoqchi, lekin qoldi 0 dona']];
  m = await sSina({}, [javob(400, { detail: { success: false, message: KAM[0], shortages: KAM[1] } })]);
  tekshir('S 400 (message + shortages) → dlv-error da sabab va har yetishmovchilik, oyna ochiq',
          !m.xato && m.err.style.display === 'block'
          && korinadi(m.err.innerHTML) === '❌ ' + KAM[0] + '\n' + KAM[1].join('\n')
          && m.soni('closeDeliveryModal') === 0,
          m.xato || qisqa([m.err.innerHTML, m.hodisalar]));

  const XSS = '<img src=x onerror=alert(1)>';
  m = await sSina({}, [javob(400, { detail: { success: false, message: KAM[0],
                                              shortages: [XSS + ': 6 metr berilmoqchi, lekin qoldi 4 metr'] } })]);
  tekshir("S 400: detal NOMIDAGI HTML innerHTML ga XOM yozilmaydi (escapeHtml) — matn o'zi ko'rinadi",
          !m.xato && m.err.innerHTML.indexOf('<img') < 0 && m.err.innerHTML.indexOf('&lt;img') >= 0
          && korinadi(m.err.innerHTML).indexOf(XSS) >= 0,
          m.xato || qisqa(m.err.innerHTML));

  m = await sSina({}, [javob(400, { detail: { success: false, message: "Xabar <b>qalin</b> & 'qo'shtirnoq'" } })]);
  tekshir('S 400: server XABARIDAGI HTML belgilari ham escapeHtml dan o\'tadi',
          !m.xato && m.err.innerHTML.indexOf('<b>') < 0
          && korinadi(m.err.innerHTML) === "❌ Xabar <b>qalin</b> & 'qo'shtirnoq'",
          m.xato || qisqa(m.err.innerHTML));

  m = await sSina({}, [javob(401, { detail: 'Tizimga kiring' })]);
  tekshir("S 401 (`detail` MATN, sessiya tugagan) → matnning o'zi ko'rsatiladi (\"Xato\" emas)",
          !m.xato && m.err.style.display === 'block' && korinadi(m.err.innerHTML) === '❌ Tizimga kiring',
          m.xato || qisqa(m.err.innerHTML));

  m = await sSina({}, [javob(400, { detail: { success: false } })]);
  tekshir("S 400 (`message` yo'q) → \"❌ Xato\"",
          !m.xato && korinadi(m.err.innerHTML) === '❌ Xato', m.xato || qisqa(m.err.innerHTML));

  m = await sSina({}, [javob(422, { detail: [{ loc: ['body'], msg: 'x' }] })]);
  tekshir("S 422 (ro'yxat) → \"❌ Xato\", istisno yo'q",
          !m.xato && korinadi(m.err.innerHTML) === '❌ Xato', m.xato || qisqa(m.err.innerHTML));

  m = await sSina({}, [javob(500, null, true)]);
  tekshir("S 500 JSON emas → \"❌ Server xatosi\", oyna ochiq",
          !m.xato && m.err.style.display === 'block' && m.err.textContent === '❌ Server xatosi'
          && m.soni('closeDeliveryModal') === 0, m.xato || qisqa([m.err, m.hodisalar]));

  m = await sSina({}, ['otadi']);
  tekshir('S tarmoq xatosi → "❌ Server xatosi"',
          !m.xato && m.err.textContent === '❌ Server xatosi', m.xato || qisqa(m.err));

  m = await sSina({ inputlar: [[701, '11', 10]] }, [javob(200, OK_QISMAN)]);
  tekshir("S qoldiqdan ko'p → so'rov yo'q, xabar, maydon qizil",
          !m.xato && m.sorovlar.length === 0 && m.err.textContent === "❌ Qoldiqdan ko'p miqdor kiritilgan!"
          && m.inp[0].style.borderColor === '#DC2626', m.xato || qisqa([m.sorovlar, m.err]));

  m = await sSina({ inputlar: [[701, '', 10], [702, '0', 5]] }, [javob(200, OK_QISMAN)]);
  tekshir("S miqdor kiritilmagan → so'rov yo'q, xabar",
          !m.xato && m.sorovlar.length === 0 && m.err.textContent === '❌ Kamida bitta mahsulot miqdorini kiriting',
          m.xato || qisqa([m.sorovlar, m.err]));

  // "Saqlash" tugmasini ikki marta bosish: birinchi so'rov hali javob bermagan.
  m = sMuhit({}, [kechik(javob(200, OK_QISMAN)), javob(200, OK_QISMAN), javob(200, OK_QISMAN)]);
  let p1 = null;
  try { p1 = vm.runInContext('saveDelivery()', m.ctx); } catch (e) { p1 = null; }
  const r2 = await chaqir(m, 'saveDelivery()');
  const ikkinchida = m.sorovlar.length;
  m.kechikkanlar.forEach((k) => { if (k.bosh) k.bosh(); });
  let r1x = null;
  try { await p1; } catch (e) { r1x = String(e && e.message || e); }
  tekshir("S ikki marta bosish (birinchi so'rov ketmoqda) → IKKINCHI so'rov YO'Q",
          !m.kodXato && !r2.xato && !r1x && ikkinchida === 1 && m.soni('closeDeliveryModal') === 1,
          m.kodXato || r2.xato || r1x || qisqa([ikkinchida, m.hodisalar]));
  const r3 = await chaqir(m, 'saveDelivery()');
  tekshir("S birinchi so'rov tugagach → qulf bo'shaydi, keyingi bosish yuboriladi",
          !r3.xato && m.sorovlar.length === ikkinchida + 1, r3.xato || qisqa(m.sorovlar.length));

  m = sMuhit({ tolov: '1 500 000' }, [javob(409, OVER), javob(200, OK_QISMAN)], false);
  let a = await chaqir(m, 'saveDelivery()');
  let b = await chaqir(m, 'saveDelivery()');
  tekshir('S "Bekor" dan keyin qulf bo\'shaydi → qayta bosish yuboriladi',
          !m.kodXato && !a.xato && !b.xato && m.sorovlar.length === 2, m.kodXato || a.xato || b.xato
          || qisqa(m.sorovlar.length));

  m = sMuhit({}, ['otadi', javob(200, OK_QISMAN)]);
  a = await chaqir(m, 'saveDelivery()');
  b = await chaqir(m, 'saveDelivery()');
  tekshir("S tarmoq xatosidan keyin qulf bo'shaydi → qayta bosish yuboriladi va saqlanadi",
          !m.kodXato && !a.xato && !b.xato && m.sorovlar.length === 2 && m.soni('closeDeliveryModal') === 1,
          m.kodXato || a.xato || b.xato || qisqa([m.sorovlar.length, m.hodisalar]));

  m = sMuhit({}, [javob(400, { detail: { success: false, message: 'x' } }), javob(200, OK_QISMAN)]);
  a = await chaqir(m, 'saveDelivery()');
  b = await chaqir(m, 'saveDelivery()');
  tekshir("S 400 dan keyin qulf bo'shaydi → tuzatib qayta yuborish mumkin",
          !m.kodXato && !a.xato && !b.xato && m.sorovlar.length === 2 && m.soni('closeDeliveryModal') === 1,
          m.kodXato || a.xato || b.xato || qisqa([m.sorovlar.length, m.hodisalar]));
}

// ── submitFullDlvModal ──────────────────────────────────────
function fMuhit(o, javoblar, tasdiq = true) {
  const el = { 'fd-payment': element(o.tolov || ''), 'fd-transport': element(o.transport || '') };
  const pending = o.pending === undefined
    ? [{ id: 701, name: 'QY_D1_0', remaining: 4.5, unit: 'metr', is_done: false },
       { id: 702, name: 'QY_D1_1', remaining: 3.33, unit: 'dona', is_done: false }]
    : o.pending;
  const m = muhit({ elementlar: el, javoblar, tasdiq,
                    globallar: { selectedOrderId: 55, _fullDlvPending: pending, _dlvYuborilmoqda: false } });
  return Object.assign(m, { kodXato: yukla(m, O_KOD) });
}

async function fSina(o, javoblar, tasdiq = true) {
  const m = fMuhit(o, javoblar, tasdiq);
  const r = await chaqir(m, 'submitFullDlvModal()');
  return Object.assign(m, { xato: m.kodXato || r.xato });
}

const F_TANA = { order_id: 55, items: [{ order_item_id: 701, quantity: 4.5 }, { order_item_id: 702, quantity: 3.33 }],
                 received_by: null, notes: null, transport_carrier: null, transport_cost: 0, transport_payer: 'none',
                 payment_amount: null, payment_method: 'naqd' };

async function submitFullBolimi() {
  bolim('orders.html — submitFullDlvModal ("Bir yo\'la to\'liq topshirish")');

  let m = await fSina({ pending: null }, [javob(200, OK_TOLIQ)]);
  tekshir("F kutilayotgan detal yo'q (`_fullDlvPending` null) → so'rov yo'q",
          !m.xato && m.sorovlar.length === 0, m.xato || qisqa(m.sorovlar));

  m = await fSina({}, [javob(200, OK_TOLIQ)]);
  tekshir("F tana AYNAN: har kutilayotgan detal `remaining` bilan (3.33 — o'zgarishsiz), to'lov null",
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/deliveries'
          && JSON.stringify(m.sorovlar[0].tana) === JSON.stringify(F_TANA),
          m.xato || qisqa(m.sorovlar));
  tekshir("F oyna so'rovdan OLDIN yopiladi",
          m.hodisalar.indexOf('closeFullDlvModal') === 0 && m.hodisalar.indexOf('fetch') === 1,
          qisqa(m.hodisalar));
  const rt = m.taymerlar.find((t) => t.ms === 2500);
  if (rt) { try { rt.fn(); } catch (e) { /* tekshiruvda ko'rinadi */ } }
  tekshir("F 200 → nakladnoy, ro'yxat, yashil xabar, 2.5 s dan keyin sahifa yangilanadi",
          m.soni('openPdfSafe:/api/deliveries/92/pdf') === 1 && m.soni('loadDeliveries:55') === 1
          && m.xabarlar.length === 1 && m.xabarlar[0].tur === 'success'
          && m.xabarlar[0].t === "✅ Buyurtma to'liq topshirildi! Nakladnoy tayyor."
          && !!rt && m.reloadSoni() === 1,
          qisqa([m.hodisalar, m.xabarlar, m.taymerlar.map((t) => t.ms)]));

  m = await fSina({ tolov: '200 000', transport: '30 000' }, [javob(200, OK_TOLIQ)]);
  tekshir("F to'lov va transport → payment_amount / transport_cost son, to'lovchi 'company'",
          !m.xato && m.sorovlar.length === 1 && JSON.stringify(m.sorovlar[0].tana) === JSON.stringify(
            Object.assign({}, F_TANA, { transport_cost: 30000, transport_payer: 'company', payment_amount: 200000 })),
          m.xato || qisqa(m.sorovlar));

  m = await fSina({ tolov: '1 500 000' }, [javob(409, OVER)], false);
  tekshir("F 409 → \"Bekor\" → \"Yetkazish saqlanmadi — ...\" (xato), bitta so'rov, nakladnoy yo'q",
          !m.xato && m.sorovlar.length === 1 && m.tasdiqlar.length === 1 && m.xabarlar.length === 1
          && m.xabarlar[0].tur === 'error'
          && m.xabarlar[0].t === "Yetkazish saqlanmadi — to'lov summasini tekshirib qayta kiriting"
          && m.hodisalar.filter((h) => h.startsWith('openPdfSafe')).length === 0,
          m.xato || qisqa([m.sorovlar.length, m.xabarlar, m.hodisalar]));

  m = await fSina({ tolov: '1 500 000' }, [javob(409, OVER), javob(200, OK_TOLIQ)], true);
  tekshir('F 409 → "Ha" → confirm_overpay true bilan qayta, tana qolgani AYNAN → yashil xabar',
          !m.xato && m.sorovlar.length === 2
          && JSON.stringify(m.sorovlar[1].tana) === JSON.stringify(Object.assign({}, F_TANA,
            { payment_amount: 1500000, confirm_overpay: true }))
          && m.xabarlar.length === 1 && m.xabarlar[0].tur === 'success',
          m.xato || qisqa([m.sorovlar, m.xabarlar]));

  m = await fSina({}, [javob(400, { detail: { success: false, message: "Qoldiqdan ko'p berib bo'lmaydi!",
                                              shortages: ['A: 1', 'B: 2'] } })]);
  tekshir("F 400 (message + shortages) → showMsg sabab va yetishmovchiliklar bilan",
          !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].tur === 'error'
          && m.xabarlar[0].t === "❌ Qoldiqdan ko'p berib bo'lmaydi!\nA: 1\nB: 2",
          m.xato || qisqa(m.xabarlar));

  m = await fSina({}, [javob(401, { detail: 'Tizimga kiring' })]);
  tekshir("F 401 (`detail` MATN) → matnning o'zi ko'rsatiladi",
          !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].t === '❌ Tizimga kiring',
          m.xato || qisqa(m.xabarlar));

  m = await fSina({}, [javob(500, null, true)]);
  tekshir('F 500 JSON emas → "❌ Server xatosi"',
          !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].t === '❌ Server xatosi', m.xato || qisqa(m.xabarlar));

  m = await fSina({}, ['otadi']);
  tekshir('F tarmoq xatosi → "❌ Server xatosi"',
          !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].t === '❌ Server xatosi', m.xato || qisqa(m.xabarlar));

  m = fMuhit({}, [kechik(javob(200, OK_TOLIQ)), javob(200, OK_TOLIQ), javob(200, OK_TOLIQ)]);
  let p1 = null;
  try { p1 = vm.runInContext('submitFullDlvModal()', m.ctx); } catch (e) { p1 = null; }
  const r2 = await chaqir(m, 'submitFullDlvModal()');
  const ikkinchida = m.sorovlar.length;
  m.kechikkanlar.forEach((k) => { if (k.bosh) k.bosh(); });
  let r1x = null;
  try { await p1; } catch (e) { r1x = String(e && e.message || e); }
  tekshir("F ikki marta chaqirish (birinchi so'rov ketmoqda) → IKKINCHI so'rov YO'Q",
          !m.kodXato && !r2.xato && !r1x && ikkinchida === 1,
          m.kodXato || r2.xato || r1x || qisqa(ikkinchida));
  const r3 = await chaqir(m, 'submitFullDlvModal()');
  tekshir("F birinchi so'rov tugagach → qulf bo'shaydi",
          !r3.xato && m.sorovlar.length === ikkinchida + 1, r3.xato || qisqa(m.sorovlar.length));

  // Ikki yo'l uchun UMUMIY qulf: qisman yetkazish ketayotganda to'liq topshirish ham kutadi.
  m = fMuhit({}, [javob(200, OK_TOLIQ)]);
  m.ctx._dlvYuborilmoqda = true;
  const rq = await chaqir(m, 'submitFullDlvModal()');
  tekshir("F boshqa yetkazish so'rovi ketayotganda (umumiy qulf) → so'rov yo'q",
          !m.kodXato && !rq.xato && m.sorovlar.length === 0, m.kodXato || rq.xato || qisqa(m.sorovlar.length));
}

// ══════════════════════════════════════════════════════════════
// returns.html — saveBrakBatch
// ══════════════════════════════════════════════════════════════
const R_NOMLAR = ['brakServerSababi', 'closeBrakModal', 'saveBrakBatch'];
const R_FN = R_NOMLAR.map((n) => olib(RETURNS, n));
const R_KOD = R_FN.filter(Boolean).join('\n');

const BRAK_ITEMS = [
  { order_id: 301, item_id: 4001, name: 'BRK_A', delivery_unit: 'metr', order_qty_normalized: 10 },
  { order_id: 301, item_id: 4002, name: 'BRK_B', delivery_unit: 'dona', order_qty_normalized: 5 },
  { order_id: 302, item_id: 4003, name: 'BRK_C', delivery_unit: 'metr', order_qty_normalized: 8 },
];

function bMuhit(o, javoblar) {
  const qiymatlar = o.qiymatlar || ['2', '1.5', ''];
  const inp = qiymatlar.map((v, i) => {
    const e = element(v);
    e.dataset = { idx: String(i) };
    e.style = {};
    return e;
  });
  const btn = element('');
  btn.textContent = 'Saqlash';
  const modal = element('');
  modal.style = { display: 'flex' };
  const el = { 'brak-error': element(''), 'brak-notes': element(o.izoh === undefined ? '  brak izoh  ' : o.izoh),
               'brak-save-btn': btn, 'brakModal': modal };
  const qs = {};
  if (o.qoplama !== null) qs['input[name="brak-coating-applied"]:checked'] = { value: o.qoplama || 'yes' };
  const m = muhit({ elementlar: el, javoblar, qsa: { '.brak-qty-inp': inp }, qs,
                    globallar: { brakItems: JSON.parse(JSON.stringify(BRAK_ITEMS)), isSavingBrak: false,
                                 brakSaqlanganBor: false } });
  return Object.assign(m, { err: el['brak-error'], inp, btn, modal, kodXato: yukla(m, R_KOD) });
}

async function bSina(o, javoblar) {
  const m = bMuhit(o, javoblar);
  const r = await chaqir(m, 'saveBrakBatch()');
  return Object.assign(m, { xato: m.kodXato || r.xato });
}

function brakTana(it, qty, izoh, qoplama) {
  return { order_id: it.order_id, order_item_id: it.item_id, item_name: it.name, quantity: qty,
           unit: it.delivery_unit, reason: 'Brak', refund_amount: 0, to_stock: false, notes: izoh,
           coating_applied: qoplama };
}

async function brakBolimi() {
  bolim('returns.html — saveBrakBatch (loyihadan brak yozish)');
  tekshir('B brakServerSababi / closeBrakModal / saveBrakBatch topildi', R_FN.every(Boolean),
          R_NOMLAR.filter((n, i) => !R_FN[i]).join(' '));

  let m = await bSina({}, [javob(200, { id: 1 }), javob(200, { id: 2 })]);
  tekshir("B hammasi 200 → har qatorga bitta POST /api/returns, tana AYNAN (Brak, 0 so'm, omborga emas)",
          !m.xato && m.sorovlar.length === 2 && m.sorovlar.every((s) => s.url === '/api/returns' && s.method === 'POST')
          && JSON.stringify(m.sorovlar[0].tana) === JSON.stringify(brakTana(BRAK_ITEMS[0], 2, 'brak izoh', true))
          && JSON.stringify(m.sorovlar[1].tana) === JSON.stringify(brakTana(BRAK_ITEMS[1], 1.5, 'brak izoh', true)),
          m.xato || qisqa(m.sorovlar));
  tekshir('B hammasi 200 → oyna yopiladi, sahifa BIR marta yangilanadi, xato maydoni yashirin',
          m.modal.style.display === 'none' && m.reloadSoni() === 1 && m.err.style.display === 'none',
          qisqa([m.modal.style, m.reloadSoni(), m.err]));

  m = await bSina({ izoh: '', qoplama: null }, [javob(200, { id: 1 }), javob(200, { id: 2 })]);
  tekshir("B izoh bo'sh → notes null; qoplama tanlanmagan → coating_applied false",
          !m.xato && m.sorovlar.length === 2 && m.sorovlar[0].tana.notes === null
          && m.sorovlar[0].tana.coating_applied === false, m.xato || qisqa(m.sorovlar[0]));

  m = await bSina({}, [javob(200, { id: 1 }), javob(400, { detail: "Buyurtmada 5 dona bor, 7 qaytarib bo'lmaydi" })]);
  tekshir('B qisman (200 + 400 matn) → aniq xabar: "❌ 1 ta saqlandi, 1 ta saqlanmadi — nom: sabab"',
          !m.xato && m.err.style.display === 'block'
          && m.err.textContent === "❌ 1 ta saqlandi, 1 ta saqlanmadi — BRK_B: Buyurtmada 5 dona bor, 7 qaytarib bo'lmaydi",
          m.xato || qisqa(m.err.textContent));
  tekshir("B qisman → saqlangan qator miqdori tozalanadi, rad etilgani QOLADI",
          m.inp[0].value === '' && m.inp[1].value === '1.5', qisqa([m.inp[0].value, m.inp[1].value]));
  tekshir("B qisman → oyna OCHIQ, sahifa yangilanmaydi, `brakSaqlanganBor` true",
          m.modal.style.display === 'flex' && m.reloadSoni() === 0 && m.ctx.brakSaqlanganBor === true,
          qisqa([m.modal.style, m.reloadSoni(), m.ctx.brakSaqlanganBor]));
  tekshir("B qisman → tugma qayta faol, matni tiklanadi, `isSavingBrak` false",
          m.btn.disabled === false && m.btn.textContent === 'Saqlash' && m.ctx.isSavingBrak === false,
          qisqa([m.btn.disabled, m.btn.textContent, m.ctx.isSavingBrak]));
  // Qisman saqlangandan keyin oyna yopilsa — ro'yxat yangilanadi.
  const cz = await chaqir(m, 'closeBrakModal()');
  tekshir("B qisman → oyna yopilganda sahifa BIR marta yangilanadi, bayroq tushadi",
          !cz.xato && m.reloadSoni() === 1 && m.ctx.brakSaqlanganBor === false && m.modal.style.display === 'none',
          cz.xato || qisqa([m.reloadSoni(), m.ctx.brakSaqlanganBor]));

  m = await bSina({}, [javob(200, { id: 1 }), javob(400, { detail: 'x' }), javob(200, { id: 3 })]);
  const qayta = await chaqir(m, 'saveBrakBatch()');
  tekshir("B qisman → rad etilganni tuzatib qayta saqlash: FAQAT qolgan qator yuboriladi, oyna yopiladi",
          !m.xato && !qayta.xato && m.sorovlar.length === 3
          && JSON.stringify(m.sorovlar[2].tana) === JSON.stringify(brakTana(BRAK_ITEMS[1], 1.5, 'brak izoh', true))
          && m.modal.style.display === 'none' && m.reloadSoni() >= 1,
          m.xato || qayta.xato || qisqa([m.sorovlar.length, m.modal.style, m.reloadSoni()]));

  m = await bSina({}, [javob(400, { detail: { success: false, message: 'Obyekt sabab' } }),
                       javob(400, { detail: 'Matn sabab' })]);
  tekshir('B hammasi rad (detail obyekt va matn) → "❌ 2 ta saqlanmadi — A: ...; B: ...", bayroq YO\'Q',
          !m.xato && m.err.textContent === '❌ 2 ta saqlanmadi — BRK_A: Obyekt sabab; BRK_B: Matn sabab'
          && m.ctx.brakSaqlanganBor === false && m.inp[0].value === '2' && m.inp[1].value === '1.5'
          && m.reloadSoni() === 0,
          m.xato || qisqa([m.err.textContent, m.ctx.brakSaqlanganBor]));

  m = await bSina({ qiymatlar: ['2', '', ''] }, [javob(422, { detail: [{ msg: 'x' }] })]);
  tekshir('B 422 (ro\'yxat) → "Xato (422)"',
          !m.xato && m.err.textContent === '❌ 1 ta saqlanmadi — BRK_A: Xato (422)', m.xato || qisqa(m.err.textContent));

  m = await bSina({ qiymatlar: ['2', '', ''] }, [javob(500, null, true)]);
  tekshir('B 500 JSON emas → "Xato (500)", istisno yo\'q',
          !m.xato && m.err.textContent === '❌ 1 ta saqlanmadi — BRK_A: Xato (500)', m.xato || qisqa(m.err.textContent));

  m = await bSina({ qiymatlar: ['2', '', ''] }, [javob(400, { detail: '' })]);
  tekshir("B `detail` bo'sh matn → \"Xato (400)\"",
          !m.xato && m.err.textContent === '❌ 1 ta saqlanmadi — BRK_A: Xato (400)', m.xato || qisqa(m.err.textContent));

  m = await bSina({}, [javob(200, { id: 1 }), 'otadi']);
  tekshir("B tarmoq 2-qatorda uzildi → \"Server xatosi — 1 ta saqlandi\", bayroq true (oyna yopilsa yangilanadi)",
          !m.xato && m.err.style.display === 'block'
          && m.err.textContent === '❌ Server xatosi — 1 ta saqlandi, qolganlari saqlanmadi'
          && m.ctx.brakSaqlanganBor === true && m.inp[0].value === '' && m.inp[1].value === '1.5'
          && m.reloadSoni() === 0,
          m.xato || qisqa([m.err.textContent, m.ctx.brakSaqlanganBor, m.inp.map((x) => x.value)]));
  const cz2 = await chaqir(m, 'closeBrakModal()');
  tekshir('B tarmoq uzilgach oyna yopilsa → sahifa yangilanadi (saqlangan brak ko\'rinadi)',
          !cz2.xato && m.reloadSoni() === 1, cz2.xato || qisqa(m.reloadSoni()));

  m = await bSina({}, ['otadi']);
  tekshir('B tarmoq 1-qatordayoq uzildi → "❌ Server xatosi", bayroq YO\'Q',
          !m.xato && m.err.textContent === '❌ Server xatosi' && m.ctx.brakSaqlanganBor === false
          && m.inp[0].value === '2', m.xato || qisqa([m.err.textContent, m.ctx.brakSaqlanganBor]));

  m = await bSina({ qiymatlar: ['11', '1', ''] }, [javob(200, { id: 1 })]);
  tekshir("B buyurtmadagidan ko'p → so'rov yo'q, xabar, maydon qizil",
          !m.xato && m.sorovlar.length === 0
          && m.err.textContent === "❌ Buyurtmadagi miqdordan ko'p kiritilgan — qizil maydonlarni tekshiring"
          && m.inp[0].style.borderColor === '#DC2626', m.xato || qisqa([m.sorovlar.length, m.err.textContent]));

  m = await bSina({ qiymatlar: ['', '0', ''] }, [javob(200, { id: 1 })]);
  tekshir("B miqdor kiritilmagan → so'rov yo'q, xabar",
          !m.xato && m.sorovlar.length === 0 && m.err.textContent === '❌ Kamida bitta detal uchun miqdor kiriting',
          m.xato || qisqa([m.sorovlar.length, m.err.textContent]));

  m = bMuhit({ qiymatlar: ['2', '', ''] }, [kechik(javob(200, { id: 1 })), javob(200, { id: 2 })]);
  let p1 = null;
  try { p1 = vm.runInContext('saveBrakBatch()', m.ctx); } catch (e) { p1 = null; }
  const r2 = await chaqir(m, 'saveBrakBatch()');
  const ikkinchida = m.sorovlar.length;
  m.kechikkanlar.forEach((k) => { if (k.bosh) k.bosh(); });
  let r1x = null;
  try { await p1; } catch (e) { r1x = String(e && e.message || e); }
  tekshir("B ikki marta bosish (birinchisi ketmoqda) → ikkinchi so'rov YO'Q",
          !m.kodXato && !r2.xato && !r1x && ikkinchida === 1 && m.reloadSoni() === 1,
          m.kodXato || r2.xato || r1x || qisqa([ikkinchida, m.reloadSoni()]));

  m = bMuhit({}, []);
  m.ctx.brakSaqlanganBor = false;
  const cz3 = await chaqir(m, 'closeBrakModal()');
  tekshir('B hech narsa saqlanmagan holda oyna yopilsa → sahifa yangilanMAYDI',
          !m.kodXato && !cz3.xato && m.reloadSoni() === 0 && m.modal.style.display === 'none',
          m.kodXato || cz3.xato || qisqa(m.reloadSoni()));
}

(async () => {
  await yetkazishYuborBolimi();
  await saveDeliveryBolimi();
  await submitFullBolimi();
  await brakBolimi();
  console.log('\n' + '='.repeat(66));
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  process.exit(FAIL === 0 ? 0 : 1);
})().catch((e) => {
  // Kutilmagan istisno ham NATIJA qatorini chiqarsin (hammasi.sh uni o'qiydi).
  console.log('KUTILMAGAN ISTISNO: ' + String((e && e.stack) || e));
  FAIL++;
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  process.exit(1);
});
