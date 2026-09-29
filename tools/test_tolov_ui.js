#!/usr/bin/env node
/**
 * test_tolov_ui.js — mijoz to'lovini saqlash (`savePayment`) ikki sahifada:
 * templates/orders.html (to'lov oynasi) va templates/debts.html (qarzni yopish).
 *
 * NIMA UCHUN KERAK (17f, 2026-09-22)
 * ----------------------------------
 * 1) `POST /api/payments` endi xom JSON ni qat'iy tekshiradi va xatoda 400 +
 *    ANIQ sabab (`detail` matn) qaytaradi. Ilgari ikkala sahifa ham faqat
 *    umumiy matn ko'rsatardi ("❌ To'lovni saqlashda xato" / "Xato yuz
 *    berdi") — foydalanuvchi NIMA noto'g'riligini bilmasdi.
 * 2) Qarzdan ko'p summa kiritilsa server 409 (`detail.type =
 *    "overpayment_warning"`, `detail.message` — savol) qaytaradi. `debts.html`
 *    uni ham "Xato yuz berdi" deb ko'rsatardi — mijoz qasddan ko'p (avans)
 *    to'lasa, uni bu sahifadan UMUMAN kiritib bo'lmasdi. `orders.html` faqat
 *    sahifada ko'ringan qarzga tayangan (eskirgan bo'lishi mumkin; "chegirmaga
 *    yozish" belgilansa umuman so'ramaydi). Endi ikkalasi ham server savolini
 *    tasdiqlatib, `confirm_overpay: true` bilan QAYTA yuboradi.
 * 3) Serverga ketadigan TANA o'zgarmagan bo'lishi SHART — qat'iy qoida uni
 *    aynan shu shaklda qabul qiladi (`tools/test_pul_query.py` D bo'limi).
 *
 * QANDAY ISHLAYDI
 * ---------------
 * Funksiyalar HTML dan JONLI o'qiladi (`async` bilan), soxta muhitda
 * (document, fetch, showMsg, showConfirmModal / customConfirm, location,
 * setTimeout) ishga tushiriladi. Topilmagan funksiya yoki ishga tushishdagi
 * istisno — yiqilgan tekshiruv (asl faylga qarshi ham QULAMAYDI).
 *
 * ISHLATISH
 * ---------
 *     node tools/test_tolov_ui.js
 *     node tools/test_tolov_ui.js boshqa/orders.html boshqa/debts.html   (mutatsiya uchun)
 *
 * kech115 (A bosqich, G3-01 / G3-02): `debts.html` endi summani o'zi yozmaydi va HAR saqlashdan oldin tasdiq so'raydi
 * (mijoz, buyurtma, summa; «qolganini chegirma qilish» belgisi bo'lsa — KECHIRILADIGAN summa alohida qatorda), natija
 * xabarida kechirilgan summa; `orders.html` — belgi bilan to'lovdan keyin qarz qolsa kechiriladigan summa tasdiqda.
 * Harness: chiqarib olish ro'yxatiga `narxKorinishi` / `narxMatni` / `payKechiriladi`, muhitga `selectedDebt`;
 * tasdiq javobi ro'yxat bo'lishi mumkin (ketma-ket). Eski tekshiruvlar qoidasi o'sha — birinchi tasdiq (saqlashdan
 * oldingi) hisobga olinib moslandi.
 *
 * Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const ORDERS = fs.readFileSync(process.argv[2] || path.join(ROOT, 'templates', 'orders.html'), 'utf8');
const DEBTS = fs.readFileSync(process.argv[3] || path.join(ROOT, 'templates', 'debts.html'), 'utf8');

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

// Funksiyani HTML dan nomi bo'yicha ajratib olish (`async` bilan).
function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
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

function element(qiymat) {
  return { value: qiymat, checked: false, textContent: '', style: {}, innerHTML: '' };
}

/**
 * Umumiy muhit. `javoblar` — ketma-ket qaytariladigan javoblar ('otadi' —
 * tarmoq xatosi), `tasdiq` — tasdiq oynasi javobi.
 */
function muhit(elementlar, javoblar, tasdiq, qoshimcha) {
  const sorovlar = [], xabarlar = [], tasdiqlar = [], alertlar = [];
  let reload = 0, ji = 0;
  const ctx = Object.assign({
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, Array, Object,
    document: {
      getElementById: (id) => (Object.prototype.hasOwnProperty.call(elementlar, id) ? elementlar[id] : null),
    },
    fetch: async (url, opts) => {
      let tana = null;
      try { tana = opts && opts.body ? JSON.parse(opts.body) : null; } catch (e) { tana = 'JSON EMAS'; }
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET', tana });
      const j = ji < javoblar.length ? javoblar[ji++] : javob(599, { detail: 'kutilmagan so\'rov' });
      if (j === 'otadi') throw new Error('tarmoq');
      return j;
    },
    showMsg: (t, tur) => { xabarlar.push({ t: String(t), tur }); },
    // kech115: `tasdiq` ro'yxat bo'lsa — ketma-ket javoblar (birinchi — saqlashdan oldingi tasdiq)
    showConfirmModal: async (m, o) => { tasdiqlar.push({ m: String(m), o }); return Array.isArray(tasdiq) ? !!tasdiq[tasdiqlar.length - 1] : tasdiq; },
    customConfirm: async (m, o) => { tasdiqlar.push({ m: String(m), o }); return Array.isArray(tasdiq) ? !!tasdiq[tasdiqlar.length - 1] : tasdiq; },
    alert: (m) => { alertlar.push(String(m)); },
    location: { reload: () => { reload++; } },
    setTimeout: () => 0,
    closePaymentForm: () => {},
    loadPayments: () => {},
    formatNum: (n) => String(n),
    fmt: (n) => String(n),
  }, qoshimcha || {});
  vm.createContext(ctx);
  return { ctx, sorovlar, xabarlar, tasdiqlar, alertlar, reloadSoni: () => reload };
}

async function ishga(m, kod, chaqiruv) {
  try {
    vm.runInContext(kod, m.ctx);
    await vm.runInContext(chaqiruv, m.ctx);
    return null;
  } catch (e) {
    return String(e && e.message || e);
  }
}

// ══════════════════════════════════════════════════════════════
// orders.html
// ══════════════════════════════════════════════════════════════
// kech95 (124-band): savePayment ortiqcha to'lov tekshiruvi uchun aniq qarzni `_joriyQarz` dan oladi —
// u ham shablondan JONLI o'qiladi.
const O_NOMLAR = ['parseNum', 'savePayment', 'tolovXatoSababi', '_joriyQarz', 'narxKorinishi', 'narxMatni'];
const O_FN = O_NOMLAR.map((n) => olib(ORDERS, n));
const O_KOD = O_FN.filter(Boolean).join('\n');

function oElementlar(o) {
  const e = {
    'pf-amount': element(o.summa || '150 000'),
    'pf-writeoff': element(''),
    'pay-debt': element(''),
    'pf-type': element(o.tur || 'partial'),
    'pf-method': element(o.usul || 'naqd'),
    'pf-notes': element(o.izoh || ''),
  };
  e['pf-writeoff'].checked = !!o.writeOff;
  e['pay-debt'].textContent = o.qarz || '1 000 000 so\'m';
  return e;
}

async function oSina(o, javoblar, tasdiq = true) {
  const m = muhit(oElementlar(o), javoblar, tasdiq, { selectedOrderId: 55 });
  const xato = await ishga(m, O_KOD, 'savePayment()');
  return Object.assign(m, { xato });
}

async function ordersBolimi() {
  bolim('orders.html — savePayment');
  tekshir('O parseNum / savePayment / tolovXatoSababi topildi', O_FN.every(Boolean),
          O_FN.map((f, i) => (f ? '' : O_NOMLAR[i])).join(' '));

  let m = await oSina({}, [javob(200, { debt_amount: 850000, is_archived: false })]);
  const t = m.sorovlar[0] && m.sorovlar[0].tana;
  tekshir('O muvaffaqiyat: bitta so\'rov, AYNAN tana (qat\'iy qoida qabul qiladigan shakl)',
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/payments'
          && m.sorovlar[0].method === 'POST'
          && JSON.stringify(t) === JSON.stringify({ order_id: 55, amount: 150000, payment_type: 'partial',
                                                   payment_method: 'naqd', notes: null, confirm_overpay: false }),
          m.xato || JSON.stringify(m.sorovlar));
  tekshir('O muvaffaqiyat: yashil xabar qarz bilan',
          m.xabarlar.length === 1 && m.xabarlar[0].tur === 'success' && m.xabarlar[0].t.includes('850000'),
          JSON.stringify(m.xabarlar));

  m = await oSina({}, [javob(400, { detail: "'amount' juda katta" })]);
  tekshir('O 400 (`detail` matn) → xabarda server SABABI',
          !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].tur === 'error'
          && m.xabarlar[0].t === "❌ 'amount' juda katta", m.xato || JSON.stringify(m.xabarlar));

  m = await oSina({}, [javob(404, { detail: 'Buyurtma topilmadi' })]);
  tekshir('O 404 → "Buyurtma topilmadi" ko\'rsatiladi',
          !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].t === '❌ Buyurtma topilmadi',
          m.xato || JSON.stringify(m.xabarlar));

  m = await oSina({}, [javob(400, { detail: { success: false, message: 'Obyekt sabab' } })]);
  tekshir('O 400 (`detail` obyekt) → `detail.message`',
          !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].t === '❌ Obyekt sabab',
          m.xato || JSON.stringify(m.xabarlar));

  m = await oSina({}, [javob(422, { detail: [{ loc: ['body'], msg: 'x' }] })]);
  tekshir('O 422 (ro\'yxat) → umumiy matn ("To\'lovni saqlashda xato")',
          !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].t === "❌ To'lovni saqlashda xato",
          m.xato || JSON.stringify(m.xabarlar));

  m = await oSina({}, [javob(502, null, true)]);
  tekshir('O JSON bo\'lmagan javob → umumiy matn, istisno yo\'q',
          !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].t === "❌ To'lovni saqlashda xato",
          m.xato || JSON.stringify(m.xabarlar));

  const OVER = { detail: { type: 'overpayment_warning', message: 'Kiritilgan summa ko\'p. Shunday ham davom etasizmi?',
                           amount: 150000, debt: 100000, excess: 50000 } };
  // kech115: sahifadagi qarz 100 000 < summa 150 000 — kechiriladigan summa yo'q, oldindan tasdiq so'ralmaydi
  m = await oSina({ writeOff: true, qarz: '100 000 so\'m' }, [javob(409, OVER), javob(200, { debt_amount: 0, is_archived: true })], true);
  tekshir('O 409 overpayment (chegirmaga yozish belgilangan) → server savoli bilan tasdiq',
          !m.xato && m.tasdiqlar.length === 1 && m.tasdiqlar[0].m.includes('Shunday ham davom etasizmi?'),
          m.xato || JSON.stringify(m.tasdiqlar));
  tekshir('O 409 tasdiqlandi → ikkinchi so\'rov AYNAN o\'sha tana + confirm_overpay true, o\'sha URL',
          m.sorovlar.length === 2 && m.sorovlar[1].url === '/api/payments?write_off_remainder=true'
          && m.sorovlar[1].tana && m.sorovlar[1].tana.confirm_overpay === true
          && m.sorovlar[1].tana.amount === 150000 && m.sorovlar[1].tana.order_id === 55,
          JSON.stringify(m.sorovlar));
  tekshir('O 409 → tasdiq → 200: muvaffaqiyat xabari (arxiv)',
          m.xabarlar.length === 1 && m.xabarlar[0].tur === 'success', JSON.stringify(m.xabarlar));

  m = await oSina({ writeOff: true, qarz: '100 000 so\'m' }, [javob(409, OVER)], false);
  tekshir('O 409 va "Bekor" → qayta yuborilmaydi, xato xabari yo\'q',
          !m.xato && m.sorovlar.length === 1 && m.xabarlar.length === 0,
          m.xato || JSON.stringify([m.sorovlar.length, m.xabarlar]));

  // Sahifadagi qarz 100 000, summa 150 000 → oldindan tasdiq (confirm_overpay true);
  // server baribir 409 bersa — ikkinchi marta so'ralmaydi, sabab ko'rsatiladi.
  m = await oSina({ qarz: '100 000 so\'m' }, [javob(409, OVER)], true);
  tekshir('O oldindan tasdiqlangan so\'rovga 409 → sikl yo\'q, bitta so\'rov, sabab ko\'rsatiladi',
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].tana.confirm_overpay === true
          && m.tasdiqlar.length === 1 && m.xabarlar.length === 1
          && m.xabarlar[0].t.includes('Shunday ham davom etasizmi?'),
          m.xato || JSON.stringify([m.sorovlar.length, m.tasdiqlar.length, m.xabarlar]));

  m = await oSina({ tur: 'zaklat', usul: "o'tkazma", izoh: '  izoh  ', summa: '1 500.5' },
                  [javob(200, { debt_amount: 1, is_archived: false })]);
  tekshir('O tur/usul/izoh (trim) va kasr summa tanada AYNAN',
          !m.xato && m.sorovlar[0] && JSON.stringify(m.sorovlar[0].tana) === JSON.stringify(
            { order_id: 55, amount: 1500.5, payment_type: 'zaklat', payment_method: "o'tkazma",
              notes: 'izoh', confirm_overpay: false }), m.xato || JSON.stringify(m.sorovlar));

  m = await oSina({}, ['otadi']);
  tekshir('O tarmoq xatosi → "❌ Server xatosi"',
          !m.xato && m.xabarlar.length === 1 && m.xabarlar[0].t === '❌ Server xatosi',
          m.xato || JSON.stringify(m.xabarlar));

  // kech115 (G3-02): belgi bilan to'lovdan keyin qarz qolsa — kechiriladigan summa saqlashdan OLDIN tasdiqda
  const bosh = (t) => String(t).replace(/[\s\u00a0\u202f]+/g, ' ');
  m = await oSina({ writeOff: true, qarz: '1 000 000 so\'m' }, [javob(200, { debt_amount: 0, is_archived: true,
    write_off: { amount: 850000, message: 'Qolgan 850000 so\'m chegirmaga qo\'shildi' } })], true);
  tekshir('O kech115: belgi + qarz qoladi → tasdiqda «850 000 so\'m KECHIRILADI», danger',
          !m.xato && m.tasdiqlar.length === 1 && bosh(m.tasdiqlar[0].m).includes("850 000 so'm KECHIRILADI")
          && m.tasdiqlar[0].o && m.tasdiqlar[0].o.danger === true && m.sorovlar.length === 1
          && m.sorovlar[0].url === '/api/payments?write_off_remainder=true',
          m.xato || JSON.stringify([m.tasdiqlar, m.sorovlar.length]));
  m = await oSina({ writeOff: true, qarz: '1 000 000 so\'m' }, [javob(200, { debt_amount: 0 })], false);
  tekshir('O kech115: kechirish tasdig\'ida «Bekor» → so\'rov YO\'Q',
          !m.xato && m.tasdiqlar.length === 1 && m.sorovlar.length === 0, m.xato || JSON.stringify(m.sorovlar));
  m = await oSina({ writeOff: true, qarz: '150 000 so\'m' }, [javob(200, { debt_amount: 0, is_archived: true })], true);
  tekshir('O kech115: belgi, lekin to\'lov qarzni to\'liq yopadi → tasdiq so\'ralmaydi',
          !m.xato && m.tasdiqlar.length === 0 && m.sorovlar.length === 1, m.xato || JSON.stringify(m.tasdiqlar));
}

// ══════════════════════════════════════════════════════════════
// debts.html
// ══════════════════════════════════════════════════════════════
const D_NOMLAR = ['parseNum', 'serverSababi', 'savePayment', 'payKechiriladi', 'narxKorinishi', 'narxMatni'];
const D_FN = D_NOMLAR.map((n) => olib(DEBTS, n));
const D_KOD = D_FN.filter(Boolean).join('\n');

function dElementlar(o) {
  const e = {
    'pay-amount': element(o.summa === undefined ? '250 000' : o.summa),   // kech115: bo'sh summa ham sinaladi
    'pay-writeoff': element(''),
    'pay-note': element(o.izoh || ''),
    'pay-msg': element(''),
  };
  e['pay-writeoff'].checked = !!o.writeOff;
  // `oldingiXabar` — oldingi urinishning xato xabari hali ko'rinib turibdi.
  e['pay-msg'].style = { display: o.oldingiXabar ? 'block' : 'none' };
  return e;
}

async function dSina(o, javoblar, tasdiq = true) {
  const el = dElementlar(o);
  // kech115: tanlangan qarz (tasdiq va kechiriladigan summa uchun — `selectOrderDebt` qo'yadi)
  const m = muhit(el, javoblar, tasdiq, { selectedOrderId: '55',
    selectedDebt: { debt: o.qarz === undefined ? 1000000 : o.qarz, client: 'Ali Valiyev', orderNumber: 'ORD-007-1' } });
  const xato = await ishga(m, D_KOD, 'savePayment()');
  return Object.assign(m, { xato, msg: el['pay-msg'] });
}

async function debtsBolimi() {
  bolim('debts.html — savePayment');
  tekshir('D parseNum / serverSababi / savePayment (+ kech115 yordamchilari) topildi', D_FN.every(Boolean),
          D_FN.map((f, i) => (f ? '' : D_NOMLAR[i])).join(' '));

  let m = await dSina({}, [javob(200, { status: 'ok' })]);
  tekshir('D muvaffaqiyat: bitta so\'rov, AYNAN tana, order_id butun son',
          !m.xato && m.sorovlar.length === 1 && m.sorovlar[0].url === '/api/payments?write_off_remainder=false'
          && JSON.stringify(m.sorovlar[0].tana) === JSON.stringify({ order_id: 55, amount: 250000, notes: null }),
          m.xato || JSON.stringify(m.sorovlar));
  tekshir('D muvaffaqiyat: yashil xabar, sahifa yangilanadi',
          m.msg.style.display === 'block' && m.msg.textContent.startsWith('✓')
          && m.msg.textContent.replace(/[\s\u00a0\u202f]/g, '').includes('250000'),
          JSON.stringify([m.msg.style, m.msg.textContent]));

  m = await dSina({}, [javob(400, { detail: "'amount' son bo'lishi kerak" })]);
  tekshir('D 400 (`detail` matn) → xabarda server SABABI',
          !m.xato && m.msg.style.display === 'block' && m.msg.textContent === "❌ 'amount' son bo'lishi kerak",
          m.xato || m.msg.textContent);

  m = await dSina({}, [javob(422, { detail: [{ msg: 'x' }] })]);
  tekshir('D 422 (ro\'yxat) → umumiy "Xato yuz berdi"',
          !m.xato && m.msg.textContent === '❌ Xato yuz berdi', m.xato || m.msg.textContent);

  const OVER = { detail: { type: 'overpayment_warning', message: 'Qarzdan 50 000 so\'mga ko\'p. Shunday ham davom etasizmi?' } };
  m = await dSina({}, [javob(409, OVER), javob(200, { status: 'ok' })], true);
  // kech115: birinchi tasdiq — saqlashdan oldingi (G3-01), ikkinchisi — server savoli
  tekshir('D 409 overpayment → server savoli bilan tasdiq (customConfirm)',
          !m.xato && m.tasdiqlar.length === 2 && m.tasdiqlar[1].m.includes('Shunday ham davom etasizmi?'),
          m.xato || JSON.stringify(m.tasdiqlar));
  tekshir('D 409 tasdiqlandi → ikkinchi so\'rov: o\'sha tana + confirm_overpay true, o\'sha URL',
          m.sorovlar.length === 2 && m.sorovlar[1].url === '/api/payments?write_off_remainder=false'
          && JSON.stringify(m.sorovlar[1].tana) === JSON.stringify({ order_id: 55, amount: 250000, notes: null,
                                                                   confirm_overpay: true }),
          JSON.stringify(m.sorovlar));
  tekshir('D 409 → tasdiq → 200: yashil xabar',
          m.msg.style.display === 'block' && m.msg.textContent.startsWith('✓'), m.msg.textContent);

  m = await dSina({ oldingiXabar: true }, [javob(409, OVER)], [true, false]);
  tekshir('D 409 va "Bekor" → qayta yuborilmaydi, oldingi xabar ham yashiriladi',
          !m.xato && m.sorovlar.length === 1 && m.msg.style.display === 'none',
          m.xato || JSON.stringify([m.sorovlar.length, m.msg.style]));

  m = await dSina({}, [javob(409, { detail: { message: 'Boshqa to\'qnashuv' } })], true);
  tekshir('D boshqa 409 (turi yo\'q) → server tasdig\'i so\'ralmaydi (faqat saqlashdan oldingi), sabab ko\'rsatiladi',
          !m.xato && m.tasdiqlar.length === 1 && m.sorovlar.length === 1
          && m.msg.textContent === '❌ Boshqa to\'qnashuv', m.xato || m.msg.textContent);

  m = await dSina({ writeOff: true, izoh: 'naqd berdi' }, [javob(200, { status: 'ok' })]);
  tekshir('D chegirmaga yozish va izoh → URL true, izoh tanada',
          !m.xato && m.sorovlar[0] && m.sorovlar[0].url === '/api/payments?write_off_remainder=true'
          && m.sorovlar[0].tana.notes === 'naqd berdi', m.xato || JSON.stringify(m.sorovlar));

  // ── kech115 (G3-01 / G3-02) ──
  const bosh = (t) => String(t).replace(/[\s\u00a0\u202f]+/g, ' ');
  m = await dSina({ summa: '' }, [javob(200, { status: 'ok' })], true);
  tekshir('D kech115: summa bo\'sh → so\'rov yo\'q, xabar «Summani kiriting», brauzer alert YO\'Q',
          !m.xato && m.sorovlar.length === 0 && m.msg.style.display === 'block' && m.msg.textContent.includes('Summani kiriting')
          && m.alertlar.length === 0, m.xato || JSON.stringify([m.sorovlar.length, m.msg.textContent, m.alertlar]));
  m = await dSina({ summa: '380 000', qarz: 380000 }, [javob(200, { status: 'ok' })], true);
  tekshir('D kech115: saqlashdan OLDIN tasdiq — mijoz, buyurtma, summa (ilgari bir bosishda yozilardi)',
          !m.xato && m.tasdiqlar.length === 1 && bosh(m.tasdiqlar[0].m).includes("Ali Valiyev · ORD-007-1: 380 000 so'm")
          && !m.tasdiqlar[0].m.includes('KECHIRILADI') && m.sorovlar.length === 1, m.xato || JSON.stringify(m.tasdiqlar));
  m = await dSina({ summa: '380 000', qarz: 380000 }, [javob(200, { status: 'ok' })], false);
  tekshir('D kech115: tasdiqda «Bekor» → so\'rov YO\'Q', !m.xato && m.sorovlar.length === 0 && m.tasdiqlar.length === 1,
          m.xato || JSON.stringify(m.sorovlar));
  m = await dSina({ summa: '10 000', qarz: 380000, writeOff: true }, [javob(200, { status: 'ok', write_off:
    { amount: 370000, message: "Qolgan 370000 so'm chegirmaga qo'shildi" } })], true);
  tekshir('D kech115: belgi + 10 000 / 380 000 → tasdiqda «Qolgan 370 000 so\'m KECHIRILADI», danger',
          !m.xato && m.tasdiqlar.length === 1 && bosh(m.tasdiqlar[0].m).includes("Qolgan 370 000 so'm KECHIRILADI")
          && m.tasdiqlar[0].o && m.tasdiqlar[0].o.danger === true, m.xato || JSON.stringify(m.tasdiqlar));
  tekshir('D kech115: natija xabarida kechirilgan summa (ilgari faqat «10 000 qabul qilindi»)',
          bosh(m.msg.textContent).includes("370 000 so'm chegirma qilib kechirildi"), m.msg.textContent);
  m = await dSina({ summa: '380 000', qarz: 380000, writeOff: true }, [javob(200, { status: 'ok', write_off: null })], true);
  tekshir('D kech115: belgi, lekin to\'lov qarzni yopadi → tasdiqda kechirish YO\'Q',
          !m.xato && m.tasdiqlar.length === 1 && !m.tasdiqlar[0].m.includes('KECHIRILADI'), m.xato || JSON.stringify(m.tasdiqlar));
  m = await dSina({ summa: '379 999.6', qarz: 380000, writeOff: true }, [javob(200, { status: 'ok' })], true);
  tekshir('D kech115: 0.4 so\'m qoldiq — qarz emas (0.5 bardosh), kechirish so\'ralmaydi',
          !m.xato && m.tasdiqlar.length === 1 && !m.tasdiqlar[0].m.includes('KECHIRILADI'), m.xato || JSON.stringify(m.tasdiqlar));
}

(async () => {
  await ordersBolimi();
  await debtsBolimi();
  console.log('\n' + '='.repeat(66));
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  process.exit(FAIL === 0 ? 0 : 1);
})();
