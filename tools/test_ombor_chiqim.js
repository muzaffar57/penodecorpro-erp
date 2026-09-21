#!/usr/bin/env node
/**
 * test_ombor_chiqim.js — Ombor sahifasidagi "Chiqim" oynasi (`saveChiqim`).
 *
 * NIMA UCHUN KERAK (19-band, 2026-09-21)
 * --------------------------------------
 * Server `POST /api/inventory/{id}/stock` endi chiqim qoldiqdan ko'p bo'lsa
 * (yoki loy qoldig'i manfiy bo'lsa) 400 va ANIQ sabab qaytaradi
 * ("omborda 5 kg bor — 8 kg chiqim qilib bo'lmaydi"). Ilgari oyna 400 da
 * faqat "Xato yuz berdi" derdi — foydalanuvchi nima uchun rad etilganini
 * bilmasdi (ilgari esa server qoldiqni jimgina 0 ga qirqardi).
 *
 * QANDAY ISHLAYDI
 * ---------------
 * `saveChiqim` `templates/inventory.html` dan JONLI o'qiladi, soxta DOM va
 * soxta `fetch` ichida ishga tushiriladi; serverga ketadigan TANA va
 * foydalanuvchiga ko'rsatilgan xabar o'lchanadi. Topilmagan funksiya —
 * yiqilgan tekshiruv (asl faylga qarshi ham QULAMAYDI).
 *
 * ISHLATISH
 * ---------
 *     node tools/test_ombor_chiqim.js
 *     node tools/test_ombor_chiqim.js boshqa/yo'l/inventory.html   (mutatsiya uchun)
 *
 * Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const HTML_YOLI = process.argv[2] || path.join(ROOT, 'templates', 'inventory.html');
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

function soxtaElement(id) {
  return { id, value: '', textContent: '', disabled: false, style: {} };
}

// javob: {ok, status, json} — json funksiya (yoki xato otadi)
function muhitYarat(javob) {
  const elementlar = {};
  const sorovlar = [];
  const toastlar = [];
  const ctx = {
    console, JSON, String, Number, Math, parseFloat, parseInt, Promise,
    location: { reload() { ctx.__reload = (ctx.__reload || 0) + 1; } },
    invToast: (t) => { toastlar.push(String(t)); },
    document: {
      getElementById(id) {
        if (!elementlar[id]) elementlar[id] = soxtaElement(id);
        return elementlar[id];
      },
    },
    fetch: async (url, opts) => {
      sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET',
                      body: opts && opts.body });
      return javob;
    },
    chiqimItemId: 42,
    isSavingChiqim: false,
  };
  vm.createContext(ctx);
  return { ctx, elementlar, sorovlar, toastlar };
}

function yukla(muhit) {
  const f = olib('saveChiqim');
  if (!f) return 'topilmadi';
  try { vm.runInContext(f, muhit.ctx); } catch (e) { return 'sintaksis: ' + e.message; }
  return null;
}

async function ishlat(javob, qty, izoh) {
  const m = muhitYarat(javob);
  const xato = yukla(m);
  if (xato) return { xato };
  m.elementlar['chiqim-qty'] = soxtaElement('chiqim-qty');
  m.elementlar['chiqim-qty'].value = qty;
  m.elementlar['chiqim-notes'] = soxtaElement('chiqim-notes');
  m.elementlar['chiqim-notes'].value = izoh || '';
  try { await vm.runInContext('saveChiqim()', m.ctx); }
  catch (e) { return { xato: 'ishlashda: ' + e.message, m }; }
  return { xato: null, m };
}

const javob400matn = {
  ok: false, status: 400,
  json: async () => ({ detail: "LM_SEMENT: omborda 5 kg bor — 8 kg chiqim qilib bo'lmaydi" }),
};
const javob400obyekt = {
  ok: false, status: 400,
  json: async () => ({ detail: { success: false, message: 'Obyekt sababi' } }),
};
const javob500jsonemas = {
  ok: false, status: 500,
  json: async () => { throw new Error('JSON emas'); },
};
const javob422royxat = {
  ok: false, status: 422,
  json: async () => ({ detail: [{ msg: 'Field required' }] }),
};
const javob200 = { ok: true, status: 200, json: async () => ({ id: 42 }) };

async function main() {
  console.log(`Fayl: ${HTML_YOLI}`);

  bolim('A. saveChiqim topildi va serverga to\'g\'ri tana ketadi');
  const tf = olib('saveChiqim');
  tekshir('A1 saveChiqim HTML da bor', !!tf);
  let r = await ishlat(javob200, '8', 'Inventarizatsiya');
  tekshir('A2 ishga tushdi', !r.xato, r.xato);
  if (!r.xato) {
    const s = r.m.sorovlar;
    tekshir('A3 bitta so\'rov', s.length === 1, `soni=${s.length}`);
    tekshir('A4 manzil /api/inventory/42/stock, POST',
            s[0] && s[0].url === '/api/inventory/42/stock' && s[0].method === 'POST',
            JSON.stringify(s[0]));
    let tana = null;
    try { tana = JSON.parse(s[0].body); } catch (e) { tana = null; }
    tekshir('A5 tana AYNAN {quantity_change:-8, reason:"Inventarizatsiya"}',
            JSON.stringify(tana) === JSON.stringify({ quantity_change: -8, reason: 'Inventarizatsiya' }),
            JSON.stringify(tana));
    tekshir('A6 200 → sahifa yangilandi', r.m.ctx.__reload === 1);
    tekshir('A7 200 → xato xabari yo\'q', r.m.toastlar.length === 0, JSON.stringify(r.m.toastlar));
  }
  r = await ishlat(javob200, '3', '');
  if (!r.xato) {
    let tana = null;
    try { tana = JSON.parse(r.m.sorovlar[0].body); } catch (e) { tana = null; }
    tekshir('A8 izoh bo\'sh → reason null (server ruxsat ro\'yxatiga mos)',
            tana && tana.reason === null && tana.quantity_change === -3, JSON.stringify(tana));
  } else tekshir('A8 ishga tushdi', false, r.xato);

  bolim('B. Server rad etsa — foydalanuvchi SABABNI ko\'radi');
  r = await ishlat(javob400matn, '8');
  tekshir('B1 400 (matn detail) → sabab ko\'rsatildi',
          !r.xato && r.m.toastlar.length === 1 && r.m.toastlar[0].indexOf('omborda 5 kg bor') >= 0,
          r.xato || JSON.stringify(r.m.toastlar));
  tekshir('B2 400 → sahifa yangilanmadi', !r.xato && !r.m.ctx.__reload);
  tekshir('B3 400 → tugma qayta faol, bayroq tushdi',
          !r.xato && r.m.elementlar['chiqim-save-btn'] && r.m.elementlar['chiqim-save-btn'].disabled === false
          && r.m.ctx.isSavingChiqim === false,
          r.xato || JSON.stringify(r.m.elementlar['chiqim-save-btn']));
  r = await ishlat(javob400obyekt, '8');
  tekshir('B4 400 (detail.message obyekt) → sabab ko\'rsatildi',
          !r.xato && r.m.toastlar.length === 1 && r.m.toastlar[0].indexOf('Obyekt sababi') >= 0,
          r.xato || JSON.stringify(r.m.toastlar));
  r = await ishlat(javob500jsonemas, '8');
  tekshir('B5 JSON emas javob → "Xato yuz berdi" (qulamaydi)',
          !r.xato && r.m.toastlar.length === 1 && r.m.toastlar[0].indexOf('Xato yuz berdi') >= 0,
          r.xato || JSON.stringify(r.m.toastlar));
  r = await ishlat(javob422royxat, '8');
  tekshir('B6 422 (detail ro\'yxat) → "Xato yuz berdi", [object Object] emas',
          !r.xato && r.m.toastlar.length === 1 && r.m.toastlar[0].indexOf('Xato yuz berdi') >= 0
          && r.m.toastlar[0].indexOf('[object') < 0,
          r.xato || JSON.stringify(r.m.toastlar));

  bolim('C. Mavjud tekshiruvlar joyida');
  for (const q of ['', '0', '-5', 'abc']) {
    r = await ishlat(javob200, q);
    tekshir(`C "${q}" → so'rov yuborilmadi`, !r.xato && r.m.sorovlar.length === 0,
            r.xato || `so'rovlar=${r.m.sorovlar.length}`);
  }

  console.log(`\n${'='.repeat(66)}`);
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  console.log('='.repeat(66));
  if (FAILED.length) { console.log('Yiqilganlar:'); FAILED.forEach(f => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
}

main().catch(e => { console.log('KUTILMAGAN: ' + e.stack); process.exit(1); });
