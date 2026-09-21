#!/usr/bin/env node
/**
 * test_xarid_tahrir_ui.js — Ta'minotchilar sahifasidagi xaridni TAHRIRLASH
 * (`editPurchase`) va server sababini ko'rsatish (`serverSababi`),
 * templates/suppliers.html.
 *
 * NIMA UCHUN KERAK (21-band, 2026-09-21)
 * --------------------------------------
 * 1) Tahrir oynasi "Ombordagi joriy miqdor va o'rtacha narxga TA'SIR
 *    QILMAYDI (agar kerak bo'lsa Omborxonada qo'lda tuzating)" derdi.
 *    Server endi miqdor FARQINI omborga qo'llaydi (chunki o'chirishda
 *    yozuvdagi miqdor ayiriladi — ikkisi mos bo'lishi SHART), shuning
 *    uchun oyna ham shuni aytishi kerak: qancha ko'payadi/kamayadi.
 * 2) Bu sahifadagi tugmalar xato bo'lsa faqat "❌ Xato" derdi — ya'ni
 *    "Bu yetkazib beruvchida … qarz bor" kabi ANIQ sabablarni foydalanuvchi
 *    KO'RMASDI. Endi `serverSababi` yordamchisi `detail` (matn) yoki
 *    `detail.message` (obyekt) ni o'qiydi, JSON emas / ro'yxat (422) —
 *    umumiy matn.
 *
 * QANDAY ISHLAYDI
 * ---------------
 * Funksiyalar suppliers.html dan JONLI o'qiladi (`async` bilan birga),
 * soxta muhitda (prompt, customConfirm, fetch, showMsg, openHistory,
 * loadSuppliers) ishga tushiriladi va serverga ketadigan TANA o'lchanadi.
 * Topilmagan funksiya — yiqilgan tekshiruv (asl faylga qarshi ham
 * QULAMAYDI).
 *
 * ISHLATISH
 * ---------
 *     node tools/test_xarid_tahrir_ui.js
 *     node tools/test_xarid_tahrir_ui.js boshqa/yo'l/suppliers.html   (mutatsiya uchun)
 *
 * Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const HTML_YOLI = process.argv[2] || path.join(ROOT, 'templates', 'suppliers.html');
const SRC = fs.readFileSync(HTML_YOLI, 'utf8');

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
function olib(nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(SRC);
  if (!m) return null;
  const i = m.index;
  let d = 0;
  const j = SRC.indexOf('{', i + m[0].length);
  for (let k = j; k < SRC.length; k++) {
    if (SRC[k] === '{') d++;
    else if (SRC[k] === '}') { d--; if (d === 0) return SRC.slice(i, k + 1); }
  }
  return null;
}

/**
 * javob — {ok,status,json} yoki 'otadi' (tarmoq xatosi)
 * promptlar — prompt() ketma-ket qaytaradigan qiymatlar
 * tasdiq — customConfirm javobi
 */
function muhitYarat(javob, promptlar, tasdiq) {
  const sorovlar = [];
  const xabarlar = [];
  const tasdiqMatnlari = [];
  const chaqiruvlar = { openHistory: [], loadSuppliers: 0 };
  let pi = 0;
  const ctx = {
    console, JSON, String, Number, Math, Promise, parseFloat, isNaN, Set,
    prompt: () => (pi < promptlar.length ? promptlar[pi++] : null),
    customConfirm: async (matn, opts) => {
      tasdiqMatnlari.push({ matn: String(matn), opts });
      return tasdiq;
    },
    showMsg: (t, tur) => { xabarlar.push({ t: String(t), tur }); },
    openHistory: (id, keep) => { chaqiruvlar.openHistory.push([id, keep]); },
    loadSuppliers: () => { chaqiruvlar.loadSuppliers++; },
    currentSupplierId: 7,
    fmt: (n) => String(n),
    suppliers: [{ id: 7, name: 'Sinov Ta\'minotchi' }],
    fetch: async (url, opts) => {
      let tana = null;
      try { tana = opts && opts.body ? JSON.parse(opts.body) : null; } catch (e) { tana = 'JSON EMAS'; }
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET', tana });
      if (javob === 'otadi') throw new Error('tarmoq');
      return javob;
    },
  };
  vm.createContext(ctx);
  return { ctx, sorovlar, xabarlar, tasdiqMatnlari, chaqiruvlar };
}

/** `editPurchase(id, qty, price, isCredit)` ni ishga tushiradi. */
async function tahrirla(javob, promptlar, tasdiq = true,
                        args = '55, 3, 1000, false') {
  const m = muhitYarat(javob, promptlar, tasdiq);
  const yordamchi = olib('serverSababi');
  const f = olib('editPurchase');
  if (!f) return { xato: 'editPurchase topilmadi' };
  if (!yordamchi) return { xato: 'serverSababi topilmadi' };
  // `inFlightPurchaseEdit` — funksiyadan tashqarida e'lon qilingan.
  try {
    vm.runInContext('const inFlightPurchaseEdit = new Set();', m.ctx);
    vm.runInContext(yordamchi, m.ctx);
    vm.runInContext(f, m.ctx);
  } catch (e) { return { xato: 'sintaksis: ' + e.message }; }
  try { await vm.runInContext(`editPurchase(${args})`, m.ctx); }
  catch (e) { return { xato: 'ishlashda: ' + e.message, m }; }
  return { xato: null, m };
}

/** `serverSababi(res, standart)` ni yakka o'zi ishga tushiradi. */
async function sababOl(javob, standart) {
  const m = muhitYarat(javob, [], true);
  const yordamchi = olib('serverSababi');
  if (!yordamchi) return { xato: 'topilmadi' };
  try { vm.runInContext(yordamchi, m.ctx); }
  catch (e) { return { xato: 'sintaksis: ' + e.message }; }
  m.ctx.__javob = javob;
  m.ctx.__standart = standart;
  try {
    const natija = await vm.runInContext(
      'serverSababi(__javob, __standart)', m.ctx);
    return { xato: null, natija };
  } catch (e) { return { xato: 'ishlashda: ' + e.message }; }
}

const j200 = { ok: true, status: 200, json: async () => ({ status: 'ok', total_amount: 10000 }) };
const j400matn = { ok: false, status: 400, json: async () => ({ detail: "'quantity' juda katta" }) };
const j400obyekt = { ok: false, status: 400, json: async () => ({ detail: { message: 'Obyekt sababi' } }) };
const j404 = { ok: false, status: 404, json: async () => ({ detail: 'Xarid topilmadi' }) };
const j500jsonemas = { ok: false, status: 500, json: async () => { throw new Error('JSON emas'); } };
const j422royxat = { ok: false, status: 422, json: async () => ({ detail: [{ msg: 'Field required' }] }) };
const j400bosh = { ok: false, status: 400, json: async () => ({ detail: '' }) };

async function main() {
  console.log(`Fayl: ${HTML_YOLI}`);

  bolim('A. Oyna matni — ombor o\'zgarishini AYTADI');
  tekshir('A1 editPurchase suppliers.html da bor', !!olib('editPurchase'));
  tekshir('A2 serverSababi yordamchisi bor', !!olib('serverSababi'));

  // 3 → 10 (ko'payadi)
  let r = await tahrirla(j200, ['10', '1000']);
  tekshir('A3 ishga tushdi', !r.xato, r.xato);
  let matn = r.m && r.m.tasdiqMatnlari[0] ? r.m.tasdiqMatnlari[0].matn : '';
  tekshir("A4 eski yolg'on \"TA'SIR QILMAYDI\" matni YO'Q",
          !/TA'SIR QILMAYDI/.test(matn), matn);
  tekshir("A5 \"qo'lda tuzating\" maslahati YO'Q", !/qo'lda tuzating/.test(matn), matn);
  tekshir("A6 ko'payish aytilgan (7 ga KO'PAYADI)",
          /KO'PAYADI/.test(matn) && /7/.test(matn), matn);
  tekshir("A7 o'rtacha narx o'zgarmasligi aytilgan",
          /narx o'zgarmaydi/.test(matn), matn);
  tekshir('A8 oyna xavfli (danger) belgisi bilan',
          !!(r.m && r.m.tasdiqMatnlari[0] && r.m.tasdiqMatnlari[0].opts
             && r.m.tasdiqMatnlari[0].opts.danger === true));

  // 10 → 4 (kamayadi)
  r = await tahrirla(j200, ['4', '1000'], true, '55, 10, 1000, false');
  matn = r.m && r.m.tasdiqMatnlari[0] ? r.m.tasdiqMatnlari[0].matn : '';
  tekshir('A9 kamayish aytilgan (6 ga KAMAYADI)',
          /KAMAYADI/.test(matn) && /6/.test(matn), matn);
  tekshir('A10 manfiyga tushish va qoplanish haqida aytilgan',
          /manfiy/.test(matn) && /kirimda qoplanadi/.test(matn), matn);

  // Miqdor o'zgarmadi — faqat narx
  r = await tahrirla(j200, ['3', '5000']);
  matn = r.m && r.m.tasdiqMatnlari[0] ? r.m.tasdiqMatnlari[0].matn : '';
  tekshir("A11 miqdor o'zgarmasa — \"omborga ta'sir qilmaydi\" deydi",
          /o'zgarmadi/.test(matn) && !/KAMAYADI/.test(matn) && !/KO'PAYADI/.test(matn), matn);
  tekshir('A12 miqdor o\'zgarmasa oyna xavfli EMAS',
          !!(r.m && r.m.tasdiqMatnlari[0] && r.m.tasdiqMatnlari[0].opts
             && r.m.tasdiqMatnlari[0].opts.danger === false));

  bolim('B. Serverga ketadigan TANA');
  r = await tahrirla(j200, ['12.5', '2500']);
  tekshir('B1 bitta PUT /api/inventory/purchases/55',
          !r.xato && r.m.sorovlar.length === 1
          && r.m.sorovlar[0].url === '/api/inventory/purchases/55'
          && r.m.sorovlar[0].method === 'PUT',
          JSON.stringify(r.m && r.m.sorovlar));
  tekshir('B2 tana AYNAN {quantity, price_per_unit}',
          !r.xato && JSON.stringify(r.m.sorovlar[0].tana)
            === JSON.stringify({ quantity: 12.5, price_per_unit: 2500 }),
          JSON.stringify(r.m && r.m.sorovlar[0] && r.m.sorovlar[0].tana));
  tekshir('B3 muvaffaqiyatda tarix (7, true) va ro\'yxat yangilandi',
          !r.xato && JSON.stringify(r.m.chaqiruvlar.openHistory) === '[[7,true]]'
          && r.m.chaqiruvlar.loadSuppliers === 1,
          JSON.stringify(r.m && r.m.chaqiruvlar));
  tekshir('B4 muvaffaqiyat xabari',
          !r.xato && r.m.xabarlar.length === 1 && r.m.xabarlar[0].tur === 'success',
          JSON.stringify(r.m && r.m.xabarlar));

  bolim('C. Rad etish va yomon qiymat — so\'rov YUBORILMAYDI');
  r = await tahrirla(j200, ['10', '1000'], false);
  tekshir('C1 tasdiq rad etilsa — so\'rov yo\'q',
          !r.xato && r.m.sorovlar.length === 0, JSON.stringify(r.m && r.m.sorovlar));
  r = await tahrirla(j200, [null]);
  tekshir('C2 miqdor prompt bekor qilinsa — so\'rov va oyna yo\'q',
          !r.xato && r.m.sorovlar.length === 0 && r.m.tasdiqMatnlari.length === 0);
  r = await tahrirla(j200, ['10', null]);
  tekshir('C3 narx prompt bekor qilinsa — so\'rov yo\'q',
          !r.xato && r.m.sorovlar.length === 0);
  r = await tahrirla(j200, ['0', '1000']);
  tekshir('C4 miqdor 0 → so\'rov yo\'q, xato xabari',
          !r.xato && r.m.sorovlar.length === 0 && r.m.xabarlar.length === 1
          && r.m.xabarlar[0].tur === 'error', JSON.stringify(r.m && r.m.xabarlar));
  r = await tahrirla(j200, ['-5', '1000']);
  tekshir('C5 miqdor manfiy → so\'rov yo\'q', !r.xato && r.m.sorovlar.length === 0);
  r = await tahrirla(j200, ['abc', '1000']);
  tekshir('C6 miqdor matn → so\'rov yo\'q', !r.xato && r.m.sorovlar.length === 0);
  r = await tahrirla(j200, ['10', '0']);
  tekshir('C7 narx 0 → so\'rov yo\'q', !r.xato && r.m.sorovlar.length === 0);
  r = await tahrirla(j200, ['10', '-1']);
  tekshir('C8 narx manfiy → so\'rov yo\'q', !r.xato && r.m.sorovlar.length === 0);

  bolim('D. Xato javoblari — SERVER sababi ko\'rsatiladi');
  r = await tahrirla(j400matn, ['10', '1000']);
  tekshir('D1 400 matn sababi xabarda',
          !r.xato && r.m.xabarlar.length === 1
          && /juda katta/.test(r.m.xabarlar[0].t) && r.m.xabarlar[0].tur === 'error',
          JSON.stringify(r.m && r.m.xabarlar));
  tekshir('D2 xatoda tarix/ro\'yxat YANGILANMAYDI',
          !r.xato && r.m.chaqiruvlar.openHistory.length === 0
          && r.m.chaqiruvlar.loadSuppliers === 0,
          JSON.stringify(r.m && r.m.chaqiruvlar));
  r = await tahrirla(j400obyekt, ['10', '1000']);
  tekshir('D3 400 obyekt sababi (detail.message) xabarda',
          !r.xato && /Obyekt sababi/.test(r.m.xabarlar[0].t),
          JSON.stringify(r.m && r.m.xabarlar));
  r = await tahrirla(j404, ['10', '1000']);
  tekshir('D4 404 matn sababi xabarda',
          !r.xato && /Xarid topilmadi/.test(r.m.xabarlar[0].t),
          JSON.stringify(r.m && r.m.xabarlar));
  r = await tahrirla(j500jsonemas, ['10', '1000']);
  tekshir('D5 JSON emas → umumiy "Xato" (qulamaydi)',
          !r.xato && r.m.xabarlar.length === 1 && /Xato/.test(r.m.xabarlar[0].t),
          JSON.stringify(r.m && r.m.xabarlar));
  r = await tahrirla(j422royxat, ['10', '1000']);
  tekshir('D6 422 ro\'yxat → umumiy "Xato" ([object Object] EMAS)',
          !r.xato && /Xato/.test(r.m.xabarlar[0].t)
          && !/object Object/.test(r.m.xabarlar[0].t),
          JSON.stringify(r.m && r.m.xabarlar));
  r = await tahrirla(j400bosh, ['10', '1000']);
  tekshir('D7 bo\'sh detail → umumiy "Xato"',
          !r.xato && /Xato/.test(r.m.xabarlar[0].t)
          && !/❌\s*$/.test(r.m.xabarlar[0].t),
          JSON.stringify(r.m && r.m.xabarlar));
  r = await tahrirla('otadi', ['10', '1000']);
  tekshir('D8 tarmoq xatosi → "Server xatosi" va qulamaydi',
          !r.xato && r.m.xabarlar.length === 1
          && /Server xatosi/.test(r.m.xabarlar[0].t),
          JSON.stringify(r.m && r.m.xabarlar));

  bolim('E. serverSababi yordamchisi — yakka');
  let s = await sababOl(j400matn);
  tekshir('E1 detail matn → o\'zi', !s.xato && s.natija === "'quantity' juda katta", JSON.stringify(s));
  s = await sababOl(j400obyekt);
  tekshir('E2 detail.message → o\'zi', !s.xato && s.natija === 'Obyekt sababi', JSON.stringify(s));
  s = await sababOl(j422royxat);
  tekshir('E3 ro\'yxat → standart "Xato"', !s.xato && s.natija === 'Xato', JSON.stringify(s));
  s = await sababOl(j500jsonemas);
  tekshir('E4 JSON emas → standart "Xato"', !s.xato && s.natija === 'Xato', JSON.stringify(s));
  s = await sababOl(j400bosh);
  tekshir('E5 bo\'sh detail → standart "Xato"', !s.xato && s.natija === 'Xato', JSON.stringify(s));
  s = await sababOl(j400bosh, 'Boshqa standart');
  tekshir('E6 berilgan standart ishlatiladi', !s.xato && s.natija === 'Boshqa standart', JSON.stringify(s));

  bolim('F. Statik — sahifadagi boshqa tugmalar ham sababni ko\'rsatadi');
  tekshir("F1 qotib qolgan \"❌ Xato'\" matni YO'Q",
          !SRC.includes("showMsg('❌ Xato', 'error')"));
  tekshir('F2 serverSababi kamida 5 joyda ishlatiladi',
          (SRC.match(/serverSababi\(res\)/g) || []).length >= 5,
          String((SRC.match(/serverSababi\(res\)/g) || []).length));
  tekshir('F3 deleteSupplier ham serverSababi ishlatadi',
          /deleteSupplier[\s\S]{0,1600}serverSababi\(res\)/.test(SRC));

  console.log(`\n${'='.repeat(66)}`);
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  console.log('='.repeat(66));
  if (FAILED.length) {
    console.log('Yiqilganlar:');
    for (const x of FAILED) console.log('  - ' + x);
  }
  process.exit(FAIL === 0 ? 0 : 1);
}

main().catch((e) => {
  console.log('KUTILMAGAN XATO: ' + e.message);
  process.exit(1);
});
