#!/usr/bin/env node
/**
 * test_xarid_ochirish.js — Ta'minotchilar sahifasidagi xaridni o'chirish
 * (`deletePurchase`, templates/suppliers.html).
 *
 * NIMA UCHUN KERAK (20-band, 2026-09-21)
 * --------------------------------------
 * Tasdiqlash oynasi "ombordagi joriy miqdor/narx AVTOMATIK o'zgarmaydi" deb
 * ogohlantirardi — bu NOTO'G'RI edi: server (`DELETE /api/inventory/
 * purchases/{id}`) xarid miqdorini OMBORDAN AYIRADI (Omborxona sahifasidagi
 * oyna to'g'ri yozardi). Endi (foydalanuvchi qarori "1") qoldiq manfiyga
 * ham tushishi mumkin — oyna shuni aytishi kerak. Xato bo'lsa oyna faqat
 * "❌ Xato" derdi — endi server sababi ko'rsatiladi.
 *
 * QANDAY ISHLAYDI
 * ---------------
 * `deletePurchase` suppliers.html dan JONLI o'qiladi, soxta muhitda
 * (customConfirm, fetch, showMsg, openHistory, loadSuppliers) ishga
 * tushiriladi. Topilmagan funksiya — yiqilgan tekshiruv (asl faylga qarshi
 * ham QULAMAYDI).
 *
 * ISHLATISH
 * ---------
 *     node tools/test_xarid_ochirish.js
 *     node tools/test_xarid_ochirish.js boshqa/yo'l/suppliers.html   (mutatsiya uchun)
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
  if (shart) { OK++; console.log(`  \u2713 ${label}`); }
  else {
    FAIL++; FAILED.push(label + (izoh ? ` (${izoh})` : ''));
    console.log(`  \u2717 ${label}${izoh ? '   — ' + izoh : ''}`);
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

// javob: {ok, status, json} yoki 'otadi' (tarmoq xatosi); tasdiq: true/false
function muhitYarat(javob, tasdiq) {
  const sorovlar = [];
  const xabarlar = [];
  const tasdiqMatnlari = [];
  const chaqiruvlar = { openHistory: [], loadSuppliers: 0 };
  const ctx = {
    console, JSON, String, Number, Math, Promise,
    customConfirm: async (matn, opts) => { tasdiqMatnlari.push({ matn: String(matn), opts }); return tasdiq; },
    showMsg: (t, tur) => { xabarlar.push({ t: String(t), tur }); },
    openHistory: (id, keep) => { chaqiruvlar.openHistory.push([id, keep]); },
    loadSuppliers: () => { chaqiruvlar.loadSuppliers++; },
    currentSupplierId: 7,
    fetch: async (url, opts) => {
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET' });
      if (javob === 'otadi') throw new Error('tarmoq');
      return javob;
    },
  };
  vm.createContext(ctx);
  return { ctx, sorovlar, xabarlar, tasdiqMatnlari, chaqiruvlar };
}

async function ishlat(javob, tasdiq = true) {
  const m = muhitYarat(javob, tasdiq);
  const f = olib('deletePurchase');
  if (!f) return { xato: 'topilmadi' };
  // 21-band (2026-09-21): server sababini o'qish mantiqi `deletePurchase`
  // ichidan `serverSababi` umumiy yordamchisiga ko'chirildi (sahifadagi
  // 5 ta tugma endi bir xil ishlaydi). Xulq AYNAN bir xil — shuning
  // uchun bu faylning tekshiruvlari O'ZGARMADI, faqat yordamchi ham
  // muhitga yuklanadi. Topilmasa — yiqilgan tekshiruv (mutatsiya himoyasi).
  const yordamchi = olib('serverSababi');
  if (!yordamchi) return { xato: 'serverSababi topilmadi' };
  try {
    vm.runInContext(yordamchi, m.ctx);
    vm.runInContext(f, m.ctx);
  } catch (e) { return { xato: 'sintaksis: ' + e.message }; }
  try { await vm.runInContext('deletePurchase(55)', m.ctx); }
  catch (e) { return { xato: 'ishlashda: ' + e.message, m }; }
  return { xato: null, m };
}

const j200 = { ok: true, status: 200, json: async () => ({ status: 'ok' }) };
const j404matn = { ok: false, status: 404, json: async () => ({ detail: 'Xarid topilmadi' }) };
const j400obyekt = { ok: false, status: 400, json: async () => ({ detail: { message: 'Obyekt sababi' } }) };
const j500jsonemas = { ok: false, status: 500, json: async () => { throw new Error('JSON emas'); } };
const j422royxat = { ok: false, status: 422, json: async () => ({ detail: [{ msg: 'Field required' }] }) };
const j400bosh = { ok: false, status: 400, json: async () => ({ detail: '' }) };

async function main() {
  console.log(`Fayl: ${HTML_YOLI}`);

  bolim("A. Tasdiqlash oynasi haqiqatni aytadi");
  tekshir('A1 deletePurchase suppliers.html da bor', !!olib('deletePurchase'));
  let r = await ishlat(j200);
  tekshir('A2 ishga tushdi', !r.xato, r.xato);
  const matn = r.m && r.m.tasdiqMatnlari[0] ? r.m.tasdiqMatnlari[0].matn : '';
  tekshir("A3 \"AVTOMATIK o'zgarmaydi\" (yolg'on) YO'Q", !/AVTOMATIK o'zgarmaydi/.test(matn), matn);
  tekshir('A4 "OMBORDAN AYIRILADI" bor', /OMBORDAN AYIRILADI/.test(matn), matn);
  tekshir('A5 manfiy qoldiq va qoplanish haqida aytilgan',
          /manfiy/.test(matn) && /kirimda qoplanadi/.test(matn), matn);
  tekshir('A6 oyna xavfli (danger) belgisi bilan',
          r.m && r.m.tasdiqMatnlari[0] && r.m.tasdiqMatnlari[0].opts && r.m.tasdiqMatnlari[0].opts.danger === true);

  bolim("B. Muvaffaqiyat (200)");
  if (!r.xato) {
    tekshir('B1 bitta DELETE /api/inventory/purchases/55',
            r.m.sorovlar.length === 1 && r.m.sorovlar[0].url === '/api/inventory/purchases/55'
            && r.m.sorovlar[0].method === 'DELETE', JSON.stringify(r.m.sorovlar));
    tekshir("B2 muvaffaqiyat xabari", r.m.xabarlar.length === 1 && r.m.xabarlar[0].tur === 'success',
            JSON.stringify(r.m.xabarlar));
    tekshir('B3 tarix (7, true) va ro\'yxat yangilandi',
            JSON.stringify(r.m.chaqiruvlar.openHistory) === '[[7,true]]' && r.m.chaqiruvlar.loadSuppliers === 1,
            JSON.stringify(r.m.chaqiruvlar));
  } else { for (const n of ['B1', 'B2', 'B3']) tekshir(n + ' (ishlamadi)', false, r.xato); }

  bolim("C. Rad etish — so'rov yo'q");
  r = await ishlat(j200, false);
  tekshir('C1 tasdiqlanmasa so\'rov YUBORILMAYDI', !r.xato && r.m.sorovlar.length === 0,
          r.xato || JSON.stringify(r.m.sorovlar));

  bolim("D. Xato — server sababi ko'rsatiladi");
  const holatlar = [
    ['D1 404 matn sababi', j404matn, '❌ Xarid topilmadi'],
    ['D2 400 detail.message', j400obyekt, '❌ Obyekt sababi'],
    ['D3 500 JSON emas → umumiy', j500jsonemas, '❌ Xato'],
    ['D4 422 ro\'yxat → umumiy', j422royxat, '❌ Xato'],
    ['D5 bo\'sh detail → umumiy', j400bosh, '❌ Xato'],
    ['D6 tarmoq xatosi', 'otadi', '❌ Server xatosi'],
  ];
  for (const [nom, jv, kutil] of holatlar) {
    r = await ishlat(jv);
    const x = r.m && r.m.xabarlar[0];
    tekshir(`${nom} → "${kutil}"`, !r.xato && r.m.xabarlar.length === 1 && x.t === kutil && x.tur === 'error',
            r.xato || JSON.stringify(r.m.xabarlar));
    if (!r.xato) {
      tekshir(`${nom}: ro'yxat yangilanmadi`,
              r.m.chaqiruvlar.openHistory.length === 0 && r.m.chaqiruvlar.loadSuppliers === 0,
              JSON.stringify(r.m.chaqiruvlar));
    } else tekshir(`${nom}: ro'yxat yangilanmadi (ishlamadi)`, false);
  }

  console.log(`\n${'='.repeat(66)}`);
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  console.log('='.repeat(66));
  if (FAILED.length) { console.log('Yiqilganlar:'); FAILED.forEach(x => console.log('  - ' + x)); }
  process.exit(FAIL === 0 ? 0 : 1);
}

main().catch(e => { console.log('KUTILMAGAN: ' + e.message); process.exit(1); });
