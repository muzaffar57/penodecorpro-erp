#!/usr/bin/env node
/**
 * tools/test_tolov_panel_ui.js — kech44, 30-band.
 *
 * `templates/orders.html` `loadPayments` (buyurtmaning to'lov paneli, "Hisob-kitob").
 *
 * Nuqson (kech43 da kodda ko'rildi): panel "Chegirma" ni `jami − kelishilgan` deb
 * ko'rsatardi. 28-band (kech43) dan beri kelishilgan summa = ASL kelishilgan − pul
 * qaytarish kamaytirishi, ya'ni mijozga qaytarilgan mahsulot uchun kamaygan summa ham
 * "chegirma" bo'lib ko'rinardi (masalan chegirmasiz 5 400 000 li buyurtmada 1 m2 pul
 * qaytgach — "Chegirma: −180 000 (0.0%)"). Summalar to'g'ri edi, faqat yorliq noto'g'ri.
 *
 * Tuzatish: chegirma `jami − kelishilgan_asl` dan, pul qaytarish kamaytirishi
 * (`pul_qaytarish_kamaytirgan`) alohida "↩️ Qaytarish" qatorida (`#pay-refund-row`).
 * Server bu maydonlarni bermasa (eski kod) — avvalgi xulq (`jami − kelishilgan`).
 *
 * Ishga tushirish:  node tools/test_tolov_panel_ui.js [orders.html]
 * Sezgirlik: tuzatishdan OLDINGI orders.html ni argument qilib bering — yiqilishi SHART,
 * skript qulamasligi shart.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const ORDERS = fs.readFileSync(process.argv[2] || path.join(ROOT, 'templates', 'orders.html'), 'utf8');

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

// Funksiyani HTML dan nomi bo'yicha ajratib olish (`async` bilan). Parametrlar ro'yxatidagi
// standart qiymat qavslari (`options = {}`) tana boshi deb olinmasligi uchun avval
// parametrlar qavsi yopilishi topiladi (kech38 saboqi).
function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
  if (!m) return null;
  const i = m.index;
  let p = 1, k = i + m[0].length;
  for (; k < src.length && p > 0; k++) {
    if (src[k] === '(') p++;
    else if (src[k] === ')') p--;
  }
  const j = src.indexOf('{', k);
  if (j < 0) return null;
  let d = 0;
  for (let q = j; q < src.length; q++) {
    if (src[q] === '{') d++;
    else if (src[q] === '}') { d--; if (d === 0) return src.slice(i, q + 1); }
  }
  return null;
}

// `const NOM = ...;` qatorini ajratib olish (bir qatorli konstanta).
function konst(src, nom) {
  const re = new RegExp('const\\s+' + nom + '\\s*=[^\\n]*;');
  const m = re.exec(src);
  return m ? m[0] : null;
}

function element(id) {
  return { id, value: '', checked: false, textContent: '', style: {}, innerHTML: '' };
}

const ELEMENT_IDLAR = [
  'pay-total', 'pay-agreed', 'pay-paid', 'pay-debt', 's-deadline', 's-status',
  'pay-discount-row', 'pay-discount', 'pay-refund-row', 'pay-refund',
  'pay-status-badge', 'btn-add-payment', 'paymentList',
];

function formatNum(n) {
  // Sahifadagi formatNum o'rniga oddiy, aniq ko'rinish: butun son bo'lsa guruhlarsiz.
  const x = Number(n);
  return Number.isInteger(x) ? String(x) : String(Math.round(x * 100) / 100);
}

const FN = olib(ORDERS, 'loadPayments');
const K1 = konst(ORDERS, 'PAY_TYPE_LABEL');
const K2 = konst(ORDERS, 'PAY_METHOD_ICON');

async function panel(order) {
  const el = {};
  ELEMENT_IDLAR.forEach((id) => { el[id] = element(id); });
  const xatolar = [];
  const ctx = {
    console: { log: () => {}, error: (...a) => { xatolar.push(a.map(String).join(' ')); } },
    JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, Array, Object, Date,
    document: {
      getElementById: (id) => (Object.prototype.hasOwnProperty.call(el, id) ? el[id] : null),
    },
    fetch: async () => ({ ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(order)) }),
    formatNum,
    escapeHtml: (s) => String(s),
    deletePayment: () => {},
  };
  vm.createContext(ctx);
  let xato = null;
  try {
    if (!FN) throw new Error('loadPayments topilmadi');
    vm.runInContext([K1 || '', K2 || '', FN].join('\n'), ctx);
    await vm.runInContext('loadPayments(198)', ctx);
  } catch (e) {
    xato = String(e && e.message || e);
  }
  return { el, xato, xatolar };
}

function kor(e) { return e && e.style ? e.style.display : undefined; }

function baza(o) {
  return Object.assign({
    id: 198, status: 'in_progress', payment_status: 'unpaid', deadline: null,
    delivery_percent: 0, notes: '', payments: [], paid_amount: 0,
  }, o);
}

async function asosiy() {
  bolim('0. Tayyorlov');
  tekshir('loadPayments sahifadan ajratildi', !!FN);
  tekshir('PAY_TYPE_LABEL / PAY_METHOD_ICON topildi', !!K1 && !!K2);

  bolim('1. Chegirmasiz, pul qaytarish yo\'q (5 400 000)');
  {
    const r = await panel(baza({
      total_amount: 5400000, agreed_amount: 5400000, debt_amount: 5400000,
      discount_percent: 0, kelishilgan_asl: 5400000, pul_qaytarish_kamaytirgan: 0,
    }));
    tekshir('1a funksiya xatosiz ishladi', !r.xato && !r.xatolar.length, r.xato || r.xatolar.join(' | '));
    tekshir('1b Kelishilgan 5400000', r.el['pay-agreed'].textContent === "5400000 so'm", r.el['pay-agreed'].textContent);
    tekshir('1c Chegirma qatori yashirin', kor(r.el['pay-discount-row']) === 'none', kor(r.el['pay-discount-row']));
    tekshir('1d Qaytarish qatori yashirin', kor(r.el['pay-refund-row']) === 'none', kor(r.el['pay-refund-row']));
  }

  bolim('2. Chegirmasiz, 1 m2 pul qaytdi (jonli 198 holati: 5 400 000 → 5 220 000)');
  {
    const r = await panel(baza({
      total_amount: 5400000, agreed_amount: 5220000, debt_amount: 5220000,
      discount_percent: 0, kelishilgan_asl: 5400000, pul_qaytarish_kamaytirgan: 180000,
    }));
    tekshir('2a funksiya xatosiz ishladi', !r.xato && !r.xatolar.length, r.xato || r.xatolar.join(' | '));
    tekshir('2b Kelishilgan 5220000 (joriy)', r.el['pay-agreed'].textContent === "5220000 so'm", r.el['pay-agreed'].textContent);
    tekshir('2c Chegirma qatori YASHIRIN (pul qaytarish chegirma emas)',
      kor(r.el['pay-discount-row']) === 'none',
      `display=${kor(r.el['pay-discount-row'])} matn=${r.el['pay-discount'].textContent}`);
    tekshir('2d Qaytarish qatori ko\'rinadi', kor(r.el['pay-refund-row']) === 'flex', kor(r.el['pay-refund-row']));
    tekshir('2e Qaytarish matni −180000 so\'m', r.el['pay-refund'].textContent === "−180000 so'm", r.el['pay-refund'].textContent);
  }

  bolim('3. 10 % chegirma + pul qaytarish (500 000 → ASL 450 000 → 415 000)');
  {
    const r = await panel(baza({
      total_amount: 500000, agreed_amount: 415000, debt_amount: 415000,
      discount_percent: 10, kelishilgan_asl: 450000, pul_qaytarish_kamaytirgan: 35000,
    }));
    tekshir('3a funksiya xatosiz ishladi', !r.xato && !r.xatolar.length, r.xato || r.xatolar.join(' | '));
    tekshir('3b Chegirma ko\'rinadi', kor(r.el['pay-discount-row']) === 'flex', kor(r.el['pay-discount-row']));
    tekshir('3c Chegirma = −50000 so\'m (10.0%) — ASL summadan',
      r.el['pay-discount'].textContent === "−50000 so'm (10.0%)", r.el['pay-discount'].textContent);
    tekshir('3d Qaytarish = −35000 so\'m', r.el['pay-refund'].textContent === "−35000 so'm", r.el['pay-refund'].textContent);
    tekshir('3e Qaytarish qatori ko\'rinadi', kor(r.el['pay-refund-row']) === 'flex', kor(r.el['pay-refund-row']));
  }

  bolim('4. To\'liq qaytgan (kelishilgan 0, K42-1) — 0 haqiqiy qiymat');
  {
    const r = await panel(baza({
      total_amount: 500000, agreed_amount: 0, debt_amount: 0, payment_status: 'paid',
      discount_percent: 0, kelishilgan_asl: 500000, pul_qaytarish_kamaytirgan: 500000,
    }));
    tekshir('4a funksiya xatosiz ishladi', !r.xato && !r.xatolar.length, r.xato || r.xatolar.join(' | '));
    tekshir('4b Kelishilgan 0 so\'m', r.el['pay-agreed'].textContent === "0 so'm", r.el['pay-agreed'].textContent);
    tekshir('4c Chegirma qatori yashirin', kor(r.el['pay-discount-row']) === 'none',
      `display=${kor(r.el['pay-discount-row'])} matn=${r.el['pay-discount'].textContent}`);
    tekshir('4d Qaytarish = −500000 so\'m', r.el['pay-refund'].textContent === "−500000 so'm", r.el['pay-refund'].textContent);
  }

  bolim('5. Eski server (kelishilgan_asl / pul_qaytarish_kamaytirgan YO\'Q) — avvalgi xulq');
  {
    const r = await panel(baza({
      total_amount: 500000, agreed_amount: 450000, debt_amount: 450000, discount_percent: 10,
    }));
    tekshir('5a funksiya xatosiz ishladi', !r.xato && !r.xatolar.length, r.xato || r.xatolar.join(' | '));
    tekshir('5b Chegirma = −50000 so\'m (10.0%)', r.el['pay-discount'].textContent === "−50000 so'm (10.0%)", r.el['pay-discount'].textContent);
    tekshir('5c Chegirma qatori ko\'rinadi', kor(r.el['pay-discount-row']) === 'flex', kor(r.el['pay-discount-row']));
    tekshir('5d Qaytarish qatori yashirin', kor(r.el['pay-refund-row']) === 'none', kor(r.el['pay-refund-row']));
  }

  bolim('6. Ustama (ASL > jami) — chegirma ko\'rsatilmaydi (avvalgidek)');
  {
    const r = await panel(baza({
      total_amount: 500000, agreed_amount: 550000, debt_amount: 550000,
      discount_percent: -10, kelishilgan_asl: 550000, pul_qaytarish_kamaytirgan: 0,
    }));
    tekshir('6a Chegirma qatori yashirin', kor(r.el['pay-discount-row']) === 'none', kor(r.el['pay-discount-row']));
    tekshir('6b Qaytarish qatori yashirin', kor(r.el['pay-refund-row']) === 'none', kor(r.el['pay-refund-row']));
  }

  bolim('7. Suzuvchi nuqta shovqini — "−0 so\'m" chegirma chiqmasin');
  {
    const r = await panel(baza({
      total_amount: 0.1 + 0.2, agreed_amount: 0.3, debt_amount: 0.3,
      discount_percent: 0, kelishilgan_asl: 0.3, pul_qaytarish_kamaytirgan: 0,
    }));
    tekshir('7a jami − ASL = (0.1 + 0.2) − 0.3 > 0 — shovqin haqiqatan bor', (0.1 + 0.2) - 0.3 > 0);
    tekshir('7b Chegirma qatori yashirin', kor(r.el['pay-discount-row']) === 'none',
      `display=${kor(r.el['pay-discount-row'])} matn=${r.el['pay-discount'].textContent}`);
    const r2 = await panel(baza({
      total_amount: 5400000, agreed_amount: 5219999.999999999, debt_amount: 5220000,
      discount_percent: 0, kelishilgan_asl: 5400000.000000001, pul_qaytarish_kamaytirgan: 180000,
    }));
    tekshir('7c ASL biroz katta (shovqin) — chegirma yashirin', kor(r2.el['pay-discount-row']) === 'none', kor(r2.el['pay-discount-row']));
  }

  bolim('8. Noto\'g\'ri / manfiy kamaytirish qiymati — qator chiqmaydi');
  {
    const r = await panel(baza({
      total_amount: 500000, agreed_amount: 500000, debt_amount: 500000,
      discount_percent: 0, kelishilgan_asl: 500000, pul_qaytarish_kamaytirgan: -5,
    }));
    tekshir('8a manfiy — qaytarish qatori yashirin', kor(r.el['pay-refund-row']) === 'none', kor(r.el['pay-refund-row']));
    const r2 = await panel(baza({
      total_amount: 500000, agreed_amount: 500000, debt_amount: 500000,
      discount_percent: 0, kelishilgan_asl: 500000, pul_qaytarish_kamaytirgan: null,
    }));
    tekshir('8b null — xatosiz, qator yashirin', !r2.xato && kor(r2.el['pay-refund-row']) === 'none', r2.xato || kor(r2.el['pay-refund-row']));
  }

  bolim('S. Statik — sahifa belgilashi');
  {
    const q = /<div[^>]*id="pay-refund-row"[^>]*>/.exec(ORDERS);
    const q0 = /<div([^>]*)id="pay-refund-row"/.exec(ORDERS);
    tekshir('S1 #pay-refund-row mavjud', !!q0);
    tekshir('S2 boshlang\'ich holati yashirin (display:none)', !!q0 && /display:none/.test(q0[1]), q0 ? q0[1] : 'yo\'q');
    tekshir('S3 #pay-refund mavjud', ORDERS.includes('id="pay-refund"'));
    tekshir('S4 qaytarish matni textContent orqali (innerHTML emas)',
      !!FN && FN.includes("getElementById('pay-refund').textContent") && !FN.includes("getElementById('pay-refund').innerHTML"));
    tekshir('S5 bir marta', (ORDERS.match(/id="pay-refund-row"/g) || []).length === 1 && !!q);
  }

  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAIL) { console.log('Yiqilganlar:'); FAILED.forEach((f) => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
}

asosiy().catch((e) => {
  console.log('KUTILMAGAN XATO: ' + (e && e.stack || e));
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL + 1}   jami = ${OK + FAIL + 1}`);
  process.exit(1);
});
