#!/usr/bin/env node
/**
 * test_qaytarish_ochirish_ui.js — kech40 (2026-09-23), 5-bo'lim 22-band + K40-1:
 * qaytarishni o'chirish va qaytgan tayyor mahsulotni o'chirish UI si.
 *
 *   templates/returns.html  — `deleteReturn`, `qaytarishXatoMatni`, `toggleRefund`
 *   templates/finished.html — `delFp`
 *
 * NIMA UCHUN KERAK (asl kod `42da36b` da O'LCHANGAN)
 * --------------------------------------------------
 * `deleteReturn` tasdiq oynasi "Moliya va Tayyor mahsulotlarga ta'sir qilmaydi,
 * faqat tarixiy yozuv o'chadi" derdi va rad javobida faqat "Xato" ko'rsatardi.
 * FOYDALANUVCHI QARORI (kech40, B): o'chirish HAMMASINI orqaga qaytaradi —
 * endi oyna omborga qo'shilgan miqdor va qaytarilgan pul bekor qilinishini
 * aytadi (qatordagi `data-stock` / `data-refund`), server rad etsa SABABINI
 * ko'rsatadi (mahsulot sotilgan / band, eski pul qaytarish), ikki marta
 * bosish bitta so'rov yuboradi. `toggleRefund` ham server sababini ko'rsatadi.
 * `delFp` rad javobida HECH NARSA ko'rsatmasdi (tugma "ishlamaydigandek") —
 * endi qoldig'i bor qaytgan mahsulot rad etilganda sabab ko'rinadi (K40-1).
 *
 * ISHLATISH:  node tools/test_qaytarish_ochirish_ui.js [boshqa/returns.html] [boshqa/finished.html]
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
const RETURNS = oqi(process.argv[2] || path.join(ROOT, 'templates', 'returns.html'));
const FINISHED = oqi(process.argv[3] || path.join(ROOT, 'templates', 'finished.html'));

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

// ── Sahifa muhiti (har holat uchun yangi) ─────────────────────────
function muhit(opts) {
  const o = Object.assign({ tasdiq: true, javob: null, qatorlar: {}, fetchKut: null }, opts || {});
  const yozuv = { fetch: [], alert: [], reload: 0, confirm: [], showMsg: [], loadFp: 0 };
  const qatorlar = {};
  for (const [id, ds] of Object.entries(o.qatorlar)) qatorlar['row-' + id] = { dataset: ds };
  const sb = {
    console: { log() {}, error() {}, warn() {} },
    document: { getElementById: (id) => qatorlar[id] || null },
    location: { reload: () => { yozuv.reload++; } },
    alert: (m) => { yozuv.alert.push(String(m)); },
    customConfirm: async (...a) => { yozuv.confirm.push(a); return o.tasdiq; },
    confirmDeleteFp: async () => 'delete',
    showMsg: (m, t) => { yozuv.showMsg.push([String(m), t]); },
    loadFp: () => { yozuv.loadFp++; },
    fpItems: [{ id: 7, name: 'QO mahsulot', volume_m3: 0.5, source: 'returned' }],
    fetch: async (url, init) => {
      yozuv.fetch.push([String(url), (init && init.method) || 'GET']);
      if (o.fetchKut) await o.fetchKut;
      const j = typeof o.javob === 'function' ? o.javob(yozuv.fetch.length) : o.javob;
      if (j === 'TARMOQ') throw new TypeError('Failed to fetch');
      return {
        ok: j.status >= 200 && j.status < 300,
        status: j.status,
        json: async () => { if (j.body === undefined) throw new SyntaxError('JSON emas'); return j.body; },
      };
    },
    inFlightRefundToggle: new Set(),
    inFlightDeleteReturn: new Set(),
  };
  vm.createContext(sb);
  const kodlar = [];
  for (const [src, nom] of [[RETURNS, 'qaytarishXatoMatni'], [RETURNS, 'deleteReturn'],
                           [RETURNS, 'toggleRefund'], [FINISHED, 'delFp']]) {
    const k = olib(src, nom);
    if (k) kodlar.push(k + `\nglobalThis.${nom} = ${nom};`);
  }
  try { vm.runInContext(kodlar.join('\n'), sb); } catch (e) { yozuv.xato = String(e); }
  return { sb, yozuv };
}

async function chaqir(sb, nom, ...a) {
  try {
    if (typeof sb[nom] !== 'function') return `FUNKSIYA YO'Q: ${nom}`;
    await sb[nom](...a);
    return 'ok';
  } catch (e) { return `ISTISNO ${e && e.name}: ${e && e.message}`; }
}

async function main() {
  bolim("0. Funksiyalar topildi");
  for (const [src, nom] of [[RETURNS, 'qaytarishXatoMatni'], [RETURNS, 'deleteReturn'],
                           [RETURNS, 'toggleRefund'], [FINISHED, 'delFp']]) {
    tekshir(`0 ${nom} bor`, !!olib(src, nom));
  }

  bolim("R. deleteReturn — tasdiq matni, server sababi, ikki marta bosish");
  {
    const { sb, yozuv } = muhit({ qatorlar: { 5: { refund: 'no', stock: '' } }, javob: { status: 200, body: { status: 'ok' } } });
    const n = await chaqir(sb, 'deleteReturn', 5);
    const m = String((yozuv.confirm[0] || [])[0] || '');
    tekshir("R1 oddiy yozuv: tasdiq so'raldi", yozuv.confirm.length === 1, qisqa([n, yozuv]));
    tekshir("R1 eski noto'g'ri matn YO'Q (\"ta'sir qilmaydi\")", !m.includes("ta'sir qilmaydi"), qisqa(m));
    tekshir("R1 ombor / pul qatorlari yo'q (bog'lam yo'q)", !m.includes('📦') && !m.includes('💰'), qisqa(m));
    tekshir("R1 200 → bitta DELETE /api/returns/5", qisqa(yozuv.fetch) === qisqa([['/api/returns/5', 'DELETE']]), qisqa(yozuv.fetch));
    tekshir("R1 200 → sahifa yangilandi, xabar yo'q", yozuv.reload === 1 && yozuv.alert.length === 0, qisqa(yozuv));
  }
  {
    const { sb, yozuv } = muhit({ qatorlar: { 6: { refund: 'no', stock: '10 metr' } }, javob: { status: 200, body: {} } });
    await chaqir(sb, 'deleteReturn', 6);
    const m = String((yozuv.confirm[0] || [])[0] || '');
    tekshir("R2 omborga qaytgan: \"Omborga qo'shilgan 10 metr … olib tashlanadi\"",
      m.includes("Omborga qo'shilgan 10 metr") && m.includes('olib tashlanadi'), qisqa(m));
    tekshir("R2 pul qatori yo'q", !m.includes('💰'), qisqa(m));
  }
  {
    const { sb, yozuv } = muhit({ qatorlar: { 8: { refund: 'yes', stock: '' } }, javob: { status: 200, body: {} } });
    await chaqir(sb, 'deleteReturn', 8);
    const m = String((yozuv.confirm[0] || [])[0] || '');
    tekshir("R3 pul qaytarilgan: \"qaytarilgan pul ham bekor qilinadi\"",
      m.includes('qaytarilgan pul ham bekor qilinadi') && m.includes('kelishilgan summa'), qisqa(m));
    const o = (yozuv.confirm[0] || [])[1] || {};
    tekshir("R3 xavfli tugma (danger) va \"Ha, o'chirish\"", o.danger === true && o.okText === "Ha, o'chirish", qisqa(o));
  }
  {
    const { sb, yozuv } = muhit({ tasdiq: false, qatorlar: { 5: { refund: 'yes', stock: '3 metr' } }, javob: { status: 200, body: {} } });
    await chaqir(sb, 'deleteReturn', 5);
    tekshir("R4 \"Bekor\" → so'rov YO'Q", yozuv.fetch.length === 0 && yozuv.reload === 0, qisqa(yozuv));
  }
  {
    // kech45 (13-band): brak yozuvi — xomashyo qaytishi haqida ogohlantirish
    const { sb, yozuv } = muhit({ qatorlar: { 9: { refund: 'no', stock: '', reason: 'Brak' } }, javob: { status: 200, body: {} } });
    await chaqir(sb, 'deleteReturn', 9);
    const m = String((yozuv.confirm[0] || [])[0] || '');
    tekshir("R3b brak: \"xomashyo … omborga qaytariladi\" + eski yozuv ogohlantirishi",
      m.includes('🧱') && m.includes('omborga qaytariladi') && m.includes('oldin yozilgan brakda xomashyo qaytmaydi'), qisqa(m));
    const { sb: sb2, yozuv: y2 } = muhit({ qatorlar: { 10: { refund: 'no', stock: '', reason: 'Ortiqcha' } }, javob: { status: 200, body: {} } });
    await chaqir(sb2, 'deleteReturn', 10);
    tekshir("R3c brakdan boshqa: brak qatori YO'Q", !String((y2.confirm[0] || [])[0] || '').includes('🧱'), qisqa(y2.confirm));
  }
  const sabab = "Bu qaytarish bilan \"QO\" omboriga 10 metr qo'shilgan, hozir bo'sh qoldig'i 2 metr — mahsulot sotilgan";
  {
    const { sb, yozuv } = muhit({ qatorlar: { 5: { refund: 'no', stock: '10 metr' } }, javob: { status: 400, body: { detail: sabab } } });
    await chaqir(sb, 'deleteReturn', 5);
    tekshir("R5 400 (matn) → AYNAN server sababi", qisqa(yozuv.alert) === qisqa(['❌ ' + sabab]), qisqa(yozuv.alert));
    tekshir("R5 400 → sahifa YANGILANMADI", yozuv.reload === 0, yozuv.reload);
  }
  {
    const { sb, yozuv } = muhit({ qatorlar: { 5: {} }, javob: { status: 400, body: { detail: { message: 'Obyekt sababi' } } } });
    await chaqir(sb, 'deleteReturn', 5);
    tekshir("R6 400 (obyekt) → detail.message", qisqa(yozuv.alert) === qisqa(['❌ Obyekt sababi']), qisqa(yozuv.alert));
  }
  {
    const { sb, yozuv } = muhit({ qatorlar: { 5: {} }, javob: { status: 500 } });
    await chaqir(sb, 'deleteReturn', 5);
    tekshir("R7 500 (JSON emas) → '❌ Xato'", qisqa(yozuv.alert) === qisqa(['❌ Xato']), qisqa(yozuv.alert));
  }
  {
    const { sb, yozuv } = muhit({ qatorlar: { 5: {} }, javob: { status: 422, body: { detail: [{ msg: 'x' }] } } });
    await chaqir(sb, 'deleteReturn', 5);
    tekshir("R8 422 (massiv detail) → '❌ Xato' (JSON massiv matnga aylanmaydi)", qisqa(yozuv.alert) === qisqa(['❌ Xato']), qisqa(yozuv.alert));
  }
  {
    const { sb, yozuv } = muhit({ qatorlar: { 5: {} }, javob: 'TARMOQ' });
    const n = await chaqir(sb, 'deleteReturn', 5);
    tekshir("R9 tarmoq xatosi → xabar, istisno yo'q, yangilanmadi",
      n === 'ok' && yozuv.alert.length === 1 && yozuv.alert[0].includes('Tarmoq xatosi') && yozuv.reload === 0, qisqa([n, yozuv]));
  }
  {
    let ochil;
    const kut = new Promise((r) => { ochil = r; });
    const { sb, yozuv } = muhit({ qatorlar: { 5: {} }, javob: { status: 400, body: { detail: 'rad' } }, fetchKut: kut });
    const p1 = chaqir(sb, 'deleteReturn', 5);
    const p2 = chaqir(sb, 'deleteReturn', 5);
    await new Promise((r) => setTimeout(r, 20));
    ochil();
    await Promise.all([p1, p2]);
    tekshir("R10 ikki marta bosish → BITTA so'rov", yozuv.fetch.length === 1, qisqa(yozuv.fetch));
    await chaqir(sb, 'deleteReturn', 5);
    tekshir("R11 so'rov tugagach qulf bo'shaydi → yana so'rov", yozuv.fetch.length === 2, qisqa(yozuv.fetch));
  }

  bolim("T. toggleRefund — server sababi");
  {
    const { sb, yozuv } = muhit({ javob: { status: 200, body: {} } });
    await chaqir(sb, 'toggleRefund', 5, true);
    tekshir("T1 allaqachon qaytgan → hech narsa", yozuv.fetch.length === 0 && yozuv.confirm.length === 0, qisqa(yozuv));
  }
  {
    const { sb, yozuv } = muhit({ tasdiq: false, javob: { status: 200, body: {} } });
    await chaqir(sb, 'toggleRefund', 5, false);
    tekshir("T2 \"Bekor\" → so'rov yo'q", yozuv.fetch.length === 0, qisqa(yozuv));
  }
  {
    const { sb, yozuv } = muhit({ javob: { status: 200, body: {} } });
    await chaqir(sb, 'toggleRefund', 5, false);
    tekshir("T3 200 → POST /api/returns/5/refund, yangilandi",
      qisqa(yozuv.fetch) === qisqa([['/api/returns/5/refund', 'POST']]) && yozuv.reload === 1, qisqa(yozuv));
  }
  {
    const { sb, yozuv } = muhit({ javob: { status: 404, body: { detail: 'Qaytarish topilmadi' } } });
    await chaqir(sb, 'toggleRefund', 5, false);
    tekshir("T4 404 → server sababi", qisqa(yozuv.alert) === qisqa(['❌ Qaytarish topilmadi']), qisqa(yozuv.alert));
  }
  // kech44 (29-band): muvaffaqiyat xabari (`j.xabar`, 24-band — "qarzdan chegirildi" / "naqd qaytarildi")
  // foydalanuvchiga sahifa yangilanishidan OLDIN ko'rsatiladi; xabar yo'q / buzuq javobda — jim yangilanadi.
  const XABAR = "Kelishilgan summa 180 000 so'mga kamaydi — qarzdan chegirildi, naqd pul qaytarilmadi (mijoz ortiqcha to'lamagan).";
  {
    const { sb, yozuv } = muhit({ javob: { status: 200, body: { status: 'ok', naqd_qaytarildi: 0, xabar: XABAR } } });
    let alertReloadPaytida = -1;
    sb.location = { reload: () => { yozuv.reload++; alertReloadPaytida = yozuv.alert.length; } };
    const r = await chaqir(sb, 'toggleRefund', 5, false);
    tekshir("T5 200 + xabar → AYNAN bitta alert '✓ ' + xabar",
      r === 'ok' && qisqa(yozuv.alert) === qisqa(['✓ ' + XABAR]), `${r} ${qisqa(yozuv.alert)}`);
    tekshir("T5b alert sahifa yangilanishidan OLDIN (yangilanish paytida alert allaqachon bor)",
      yozuv.reload === 1 && alertReloadPaytida === 1, `reload=${yozuv.reload} alertReloadPaytida=${alertReloadPaytida}`);
  }
  {
    const { sb, yozuv } = muhit({ javob: { status: 200, body: { status: 'ok' } } });
    const r = await chaqir(sb, 'toggleRefund', 5, false);
    tekshir("T6 200, xabar YO'Q → alert yo'q, yangilandi", r === 'ok' && yozuv.alert.length === 0 && yozuv.reload === 1, `${r} ${qisqa(yozuv)}`);
  }
  {
    const { sb, yozuv } = muhit({ javob: { status: 200 } });
    const r = await chaqir(sb, 'toggleRefund', 5, false);
    tekshir("T7 200, JSON EMAS → istisno yo'q, alert yo'q, yangilandi", r === 'ok' && yozuv.alert.length === 0 && yozuv.reload === 1, `${r} ${qisqa(yozuv)}`);
  }
  {
    const { sb, yozuv } = muhit({ javob: { status: 200, body: { xabar: 5 } } });
    const r = await chaqir(sb, 'toggleRefund', 5, false);
    tekshir("T8 xabar satr EMAS (5) → alert yo'q", r === 'ok' && yozuv.alert.length === 0 && yozuv.reload === 1, `${r} ${qisqa(yozuv)}`);
    const m2 = muhit({ javob: { status: 200, body: { xabar: '' } } });
    const r2 = await chaqir(m2.sb, 'toggleRefund', 5, false);
    tekshir("T8b xabar bo'sh satr → alert yo'q ('✓ ' yolg'iz chiqmaydi)", r2 === 'ok' && m2.yozuv.alert.length === 0 && m2.yozuv.reload === 1, `${r2} ${qisqa(m2.yozuv)}`);
    const m3 = muhit({ javob: { status: 200, body: null } });
    const r3 = await chaqir(m3.sb, 'toggleRefund', 5, false);
    tekshir("T8c javob null → istisno yo'q, alert yo'q", r3 === 'ok' && m3.yozuv.alert.length === 0 && m3.yozuv.reload === 1, `${r3} ${qisqa(m3.yozuv)}`);
  }
  {
    const { sb, yozuv } = muhit({ javob: { status: 200, body: { xabar: XABAR } } });
    await chaqir(sb, 'toggleRefund', 5, false);
    const tm = yozuv.confirm.length ? String(yozuv.confirm[0][0]) : '';
    tekshir("T9 tasdiq matni: kelishilgan summadan chegiriladi, naqd faqat ortiqcha qism (24-band)",
      tm.includes('kelishilgan summasidan chegiriladi') && tm.includes("ortiqcha to'lagan"), tm.slice(0, 120));
  }

  bolim("F. delFp (finished.html) — rad javobida server sababi (K40-1)");
  const fsabab = "Bu mahsulotda hali 5 metr qoldiq bor — o'chirib bo'lmaydi.";
  {
    const { sb, yozuv } = muhit({ javob: { status: 400, body: { detail: fsabab } } });
    const n = await chaqir(sb, 'delFp', 7, 'returned');
    tekshir("F1 qaytgan mahsulot: tasdiq → DELETE /api/finished/7",
      yozuv.fetch.length === 1 && yozuv.fetch[0][0].startsWith('/api/finished/7') && yozuv.fetch[0][1] === 'DELETE', qisqa([n, yozuv.fetch]));
    tekshir("F1 400 → showMsg('❌ ' + sabab, 'error')", qisqa(yozuv.showMsg) === qisqa([['❌ ' + fsabab, 'error']]), qisqa(yozuv.showMsg));
    tekshir("F1 400 → ro'yxat qayta yuklanmadi", yozuv.loadFp === 0, yozuv.loadFp);
  }
  {
    const { sb, yozuv } = muhit({ javob: { status: 400, body: { detail: { message: 'Obyekt' } } } });
    await chaqir(sb, 'delFp', 7, 'returned');
    tekshir("F2 400 (obyekt) → detail.message", qisqa(yozuv.showMsg) === qisqa([['❌ Obyekt', 'error']]), qisqa(yozuv.showMsg));
  }
  {
    const { sb, yozuv } = muhit({ javob: { status: 500 } });
    await chaqir(sb, 'delFp', 7, 'returned');
    tekshir("F3 500 (JSON emas) → '❌ Xato'", qisqa(yozuv.showMsg) === qisqa([['❌ Xato', 'error']]), qisqa(yozuv.showMsg));
  }
  {
    const { sb, yozuv } = muhit({ javob: { status: 200, body: { status: 'ok' } } });
    await chaqir(sb, 'delFp', 7, 'returned');
    tekshir("F4 200 → ro'yxat yangilandi, '✓ O'chirildi'", yozuv.loadFp === 1
      && yozuv.showMsg.length === 1 && yozuv.showMsg[0][1] === 'success', qisqa(yozuv));
  }
}

main().catch((e) => {
  FAIL++; FAILED.push('kutilmagan istisno: ' + e);
  console.log('  ✗ kutilmagan istisno: ' + e);
}).finally(() => {
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) {
    console.log('YIQILGANLAR:');
    for (const f of FAILED) console.log('  - ' + f);
  }
  process.exitCode = FAIL === 0 ? 0 : 1;
});
