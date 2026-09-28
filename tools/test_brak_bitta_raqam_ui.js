#!/usr/bin/env node
/**
 * test_brak_bitta_raqam_ui.js — kech107, 49-band ("Bitta raqam", egasi qarori) UI darvozasi.
 *
 *   templates/returns.html   — "Brak tahlili" kartasi izohi (`brakTahlilHtml`): taqsimot — haqiqiy xomashyo narxi,
 *                              Moliya bilan bir hisob; bog'lanmagan eski harakatlar va omborda tayyor turgan
 *                              mahsulot yo'qotishi — alohida (ko'rsatiladi faqat bo'lsa);
 *   templates/finance.html   — xarajatlar ro'yxati (`buildExpDetail`): "Tayyor mahsulot yo'qotishi (omborda)" — Brakdan
 *                              ALOHIDA qator; faqat brak / yo'qotish / transport / ishlab chiqarish bo'lgan oyda ham
 *                              ro'yxat va sof foyda ko'rinadi (asl: "Xarajat kiritilmagan", sof foyda bloki YASHIRIN);
 *   templates/dashboard.html, finished.html — yorliq va xabar matnlari (statik).
 *
 * QANDAY ISHLAYDI: funksiyalar HTML dan JONLI o'qiladi (Jinja teglari olib tashlanadi), soxta muhitda ishga
 * tushiriladi. Topilmagan funksiya yoki istisno — yiqilgan tekshiruv (asl faylga qarshi ham QULAMAYDI).
 *
 * ISHLATISH:  node tools/test_brak_bitta_raqam_ui.js
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
const RETURNS = oqi('returns.html');
const FINANCE = oqi('finance.html');
const DASHBOARD = oqi('dashboard.html');
const FINISHED = oqi('finished.html');
const BASE = oqi('base.html');

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
// Funksiyani nomi bo'yicha ajratib olish (parametrlardagi qavslar — avval `)` gacha).
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
function konst(src, nom) {
  const i = src.indexOf('const ' + nom + ' =');
  if (i < 0) return null;
  const j = src.indexOf(';', i);
  return j < 0 ? null : src.slice(i, j + 1);
}
function jinjasiz(kod) {
  return kod === null ? null : kod.replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, 'null');
}
// ru-RU minglik ajratgichi (NBSP / U+202F) — oddiy bo'shliqqa.
const bosh = (x) => String(x || '').replace(/[  ]/g, ' ');

function kontekst(qosh) {
  const ctx = Object.assign({ console, JSON, String, Number, Math, Array, Object, Error, RegExp, Date, isNaN, parseFloat },
                            qosh || {});
  vm.createContext(ctx);
  return ctx;
}

// ══════════════════════════════════════════════════════════════
// T — returns.html: tahlil izohi
// ══════════════════════════════════════════════════════════════
function tahlilNamuna(qosh) {
  return Object.assign({
    yil: 2026, oy: 9, meyor_foiz: 5.0, brak_xarajat: 74560, ishlab_chiqarish_xarajat: 2000000,
    brak_foizi: 3.73, meyordan_oshdi: false, ogohlantirish: null, yozuvlar_soni: 3, yozuvlar_qiymati: 74560,
    boglanmagan_qiymat: 0, tayyor_yoqotish_qiymati: 0,
    bosqichlar: [{ kod: 'kesish', nomi: 'Kesish', soni: 3, qiymat: 74560, ulush: 100 }],
    sabablar: [], javobgarlar: [], top_detallar: [], yoqotishlar: [],
    trend: [{ yil: 2026, oy: 9, brak_xarajat: 74560, ishlab_chiqarish_xarajat: 2000000, brak_foizi: 3.73, meyordan_oshdi: false }],
  }, qosh || {});
}
function tahlilChiz(d) {
  const qismlar = [olib(BASE, 'escapeHtml'), konst(RETURNS, 'BRAK_OY_NOMLARI'), olib(RETURNS, 'brakTahlilOyMatn'),
                   olib(RETURNS, 'brakFoizMatn'), olib(RETURNS, 'brakTahlilHtml')];
  const tk = ['tkMs', 'tkDate', 'tkSana', 'tkVaqt', 'tkSanaVaqt', 'tkToliq', 'tkISO', 'tkHozir', 'tkKunFarqi']
    .map(n => olib(BASE, n)).filter(Boolean);
  if (!qismlar.every(Boolean)) return { xato: 'funksiyalar topilmadi', html: '' };
  const ctx = kontekst();
  try {
    vm.runInContext(jinjasiz(tk.concat(qismlar).join('\n')), ctx);
    ctx.__d = JSON.parse(JSON.stringify(d));
    return { xato: null, html: bosh(vm.runInContext('brakTahlilHtml(__d)', ctx)) };
  } catch (e) {
    return { xato: String(e.message || e), html: '' };
  }
}
function izoh(html) {
  const m = /<div class="brak-izoh"[^>]*>([\s\S]*?)<\/div>/.exec(html) || /Quyidagi taqsimot[^<]*/.exec(html);
  return m ? (m[1] || m[0]) : '';
}

bolim("T — returns.html «Brak tahlili» izohi");
let r = tahlilChiz(tahlilNamuna());
let iz = izoh(r.html);
tekshir("T1 taqsimot — haqiqiy xomashyo narxi, Moliyadagi «Brak» qatori bilan bir hisob (3 ta, 74 560 so'm)",
        !r.xato && iz.includes('haqiqiy xomashyo narxi') && iz.includes('«Brak» qatori bilan bir hisob') && iz.includes('3 ta, 74 560'),
        r.xato || iz);
tekshir("T2 bog'lanmagan 0 va tayyor turgan yo'qotish 0 — ikkala qo'shimcha jumla YO'Q; eski \"farq bo'lishi mumkin\" jumlasi YO'Q",
        !r.xato && !iz.includes("bog'lanmagan") && !iz.includes('tayyor turgan') && !iz.includes("farq bo'lishi mumkin"), r.xato || iz);
r = tahlilChiz(tahlilNamuna({ brak_xarajat: 77560, boglanmagan_qiymat: 3000, tayyor_yoqotish_qiymati: 50000 }));
iz = izoh(r.html);
tekshir("T3 bog'lanmagan eski harakatlar (3 000) va omborda tayyor turgan yo'qotish (50 000, ulushga kirmaydi) — ko'rsatiladi",
        !r.xato && iz.includes("Yozuvga bog'lanmagan (eski) brak harakatlari: 3 000 so'm")
        && iz.includes("Omborda tayyor turgan mahsulot yo'qotishlari: 50 000 so'm") && iz.includes('brak ulushiga kirmaydi'),
        r.xato || iz);
r = tahlilChiz(tahlilNamuna({ boglanmagan_qiymat: 0.4 }));
iz = izoh(r.html);
tekshir("T4 bog'lanmagan < 1 so'm (yaxlitlash qoldig'i) — ko'rsatilmaydi", !r.xato && !iz.includes("bog'lanmagan"), r.xato || iz);
r = tahlilChiz(tahlilNamuna({ boglanmagan_qiymat: -2500 }));
iz = izoh(r.html);
tekshir("T5 manfiy farq ham ko'rsatiladi (yashirilmaydi)", !r.xato && iz.includes("bog'lanmagan (eski) brak harakatlari: -2 500"),
        r.xato || iz);

// ══════════════════════════════════════════════════════════════
// M — finance.html: xarajatlar ro'yxati
// ══════════════════════════════════════════════════════════════
function moliyaChiz(d) {
  const kod = [olib(BASE, 'escapeHtml'), olib(FINANCE, 'fmt'), olib(FINANCE, 'fmtFull'), olib(FINANCE, 'buildExpDetail')];
  if (!kod.every(Boolean)) return { xato: 'funksiyalar topilmadi', html: '', el: {} };
  const el = {};
  const ol = (id) => { if (!el[id]) el[id] = { innerHTML: '', textContent: '', style: {} }; return el[id]; };
  const ctx = kontekst({ document: { getElementById: ol }, buildRevDonut: () => {} });
  try {
    vm.runInContext(jinjasiz(kod.join('\n')), ctx);
    ctx.__d = JSON.parse(JSON.stringify(d));
    vm.runInContext('buildExpDetail(__d)', ctx);
    return { xato: null, html: bosh(ol('expDetail').innerHTML), el };
  } catch (e) {
    return { xato: String(e.message || e), html: '', el };
  }
}
function hisobot(qosh) {
  return Object.assign({
    xarajatlar: { arenda: 0, elektr: 0, tushlik: 0, soliqlar: 0 }, qoshimcha_xarajatlar: {},
    usta_kpi_breakdown: [], hodimlar_moslashuvchan_breakdown: [], qaytarish_soni: 0, fp_sales_daromad: 0,
    ishlab_chiqarish_xarajat: 0, ehson_xarajat: 0, brak_xarajat: 74560, fp_loss_xarajat: 50000, transport_xarajat: 0,
    jami_xarajat: 124560, daromad: 0, sof_foyda: -124560, foyda_foiz: 0,
  }, qosh || {});
}

bolim("M — finance.html xarajatlar ro'yxati");
let m = moliyaChiz(hisobot());
tekshir("M1 faqat brak va tayyor turgan yo'qotish bo'lgan oy — ro'yxat chiziladi (asl: \"Xarajat kiritilmagan\")",
        !m.xato && !m.html.includes('Xarajat kiritilmagan') && m.html.includes('Jami xarajat:'), m.xato || m.html);
tekshir("M2 «Brak (yaroqsiz xomashyo)» 74 560 va ALOHIDA «Tayyor mahsulot yo'qotishi (omborda)» 50 000",
        !m.xato && m.html.includes('🗑️ Brak (yaroqsiz xomashyo)') && m.html.includes('74 560 so\'m')
        && m.html.includes("📦 Tayyor mahsulot yo'qotishi (omborda)") && m.html.includes("50 000 so'm"), m.xato || m.html);
tekshir("M3 sof foyda bloki ko'rinadi (asl: yashirin)",
        !m.xato && (m.el.profitBlock || {}).style && m.el.profitBlock.style.display === 'block'
        && bosh((m.el.profitBig || {}).textContent).includes('-124 560'), m.xato || m.el.profitBlock);
m = moliyaChiz(hisobot({ fp_loss_xarajat: 0, jami_xarajat: 74560, sof_foyda: -74560 }));
tekshir("M4 tayyor turgan yo'qotish 0 — qatori YO'Q", !m.xato && !m.html.includes("Tayyor mahsulot yo'qotishi"), m.xato || m.html);
m = moliyaChiz(hisobot({ brak_xarajat: 0, fp_loss_xarajat: 0, jami_xarajat: 0, sof_foyda: 0 }));
tekshir("M5 HECH qanday xarajat va daromad yo'q — \"Xarajat kiritilmagan\" (avvalgidek), sof foyda yashirin",
        !m.xato && m.html.includes('Xarajat kiritilmagan') && (m.el.profitBlock || {style: {}}).style.display === 'none',
        m.xato || m.html);
m = moliyaChiz(hisobot({ brak_xarajat: 0, fp_loss_xarajat: 0, jami_xarajat: 0, ishlab_chiqarish_xarajat: 300000,
                         daromad: 500000, sof_foyda: 200000 }));
tekshir("M6 faqat ishlab chiqarish va daromad bo'lgan oy — ro'yxat (ishlab chiqarish qatori) va sof foyda ko'rinadi",
        !m.xato && m.html.includes('🏭 Ishlab chiqarish xarajati') && m.html.includes("300 000 so'm")
        && (m.el.profitBlock || {style: {}}).style.display === 'block', m.xato || m.html);

// ══════════════════════════════════════════════════════════════
bolim('S — statik');
tekshir("S1 bosh sahifa yorlig'i «Brak qiymati (bu oy, xomashyo)» (asl: «Yo'qotish qiymati» — tayyor yo'qotishni ham anglatardi)",
        DASHBOARD.includes('Brak qiymati (bu oy, xomashyo)') && !DASHBOARD.includes("Yo'qotish qiymati (bu oy)"), '');
tekshir("S2 qaytarishlar sahifasi kartasi «Brak qiymati (bu oy)»", RETURNS.includes('<div class="stat-label">Brak qiymati (bu oy)</div>'), '');
tekshir("S3 «Kamaytirish» matnlari: «Tayyor mahsulot yo'qotishi» qatoriga (asl: «Moliyada Brak xarajatiga»)",
        !FINISHED.includes('Moliyada Brak xarajatiga') && (FINISHED.match(/«Tayyor mahsulot yo'qotishi» qatoriga/g) || []).length === 2, '');

console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach(f => console.log('   - ' + f)); }
process.exit(FAIL ? 1 : 0);
