#!/usr/bin/env node
/**
 * test_avans_yubor_ui.js — kech140 (zip 168, audit A-P09 — egasi QARORLARI 11.10 «Ogohlantirib so'rasin», «Keyingi oydan ushlansin»).
 *
 *   templates/base.html            — YANGI `avansYubor(url)`: 409 `avans_oylikdan_ortiq` → oyna so'raydi → «Ha» — AYNAN o'sha so'rov
 *                                    `confirm_excess=true` bilan qayta; «Bekor» — qayta so'rov YO'Q; boshqa rad — sabab (`amalSababi`)
 *   templates/kpi.html             — `saveAdvance` (avans berish), `loadCurrentMonthEmpStatus` («🟠 Hodim qarzdor», keyingi / o'tgan oy)
 *   templates/debts.html           — `closeEmployeeDebt` («oylikni yopish»; ilgari rad — «Xato yuz berdi», sababsiz)
 *   templates/_hodim_oynalari.html — `confirmAdvReq` (hodim so'rovini tasdiqlash; 404 — qator olib tashlanadi)
 *   templates/hodim_panel.html     — `oylikHtml` (keyingi oy oyligidan ushlanadigan / o'tgan oydan kelgan qism)
 *
 * NIMA UCHUN: asl kod (zip 167) oylikdan ko'p avansni jimgina yozardi; server endi 409 qaytaradi — sahifa so'ramasa avans umuman
 * yozilmay qoladi (yoki sababsiz «Xato»). KPI kartasi qolgan manfiy bo'lsa «🟢 To'liq to'langan, qolgan 0» derdi.
 * Funksiyalar HTML dan JONLI o'qiladi, soxta muhitda ishga tushiriladi. Topilmagan funksiya — yiqilgan tekshiruv (asl fayllarga qarshi
 * ham QULAMAYDI).
 *
 *     node tools/test_avans_yubor_ui.js [templates_papkasi]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const TPL = process.argv[2] || path.join(ROOT, 'templates');
function oqi(nom) { try { return fs.readFileSync(path.join(TPL, nom), 'utf8'); } catch (e) { return ''; } }
function jinjasiz(s) { return s.replace(/\{#[\s\S]*?#\}/g, '').replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, 'null'); }
const BASE = jinjasiz(oqi('base.html')), KPI = jinjasiz(oqi('kpi.html')), DEBTS = jinjasiz(oqi('debts.html'));
const HO = jinjasiz(oqi('_hodim_oynalari.html')), PANEL = jinjasiz(oqi('hodim_panel.html'));

let OK = 0, FAIL = 0;
const FAILED = [];
function tekshir(label, shart, izoh) {
  let s = false;
  try { s = !!shart; } catch (e) { s = false; }
  if (s) { OK++; console.log(`  ✓ ${label}`); }
  else { FAIL++; FAILED.push(label); console.log(`  ✗ ${label}${izoh !== undefined ? '   — ' + qisqa(izoh) : ''}`); }
}
function bolim(t) { console.log(`\n--- ${t} ---`); }
// Brauzerdagi ko'rinish: ru-RU ming ajratgichi (U+00A0 / U+202F) — oddiy bo'shliq, HTML belgilari (`escapeHtml`) — asl harf
function toza(h) { return String(h || '').replace(/[\u00a0\u202f]/g, ' ').replace(/&#0?39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&'); }
function qisqa(x) { let s; try { s = typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { s = String(x); } s = String(s); return s.length > 500 ? s.slice(0, 500) + '…' : s; }
function olib(src, nom) {
  const m = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(').exec(src);
  if (!m) return null;
  let d = 0;
  const j = src.indexOf('{', m.index + m[0].length);
  if (j < 0) return null;
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(m.index, k + 1); }
  }
  return null;
}
function el(extra) {
  return Object.assign({ value: '', textContent: '', innerHTML: '', style: {}, dataset: {}, disabled: false,
                         appendChild() {}, querySelector: () => null, querySelectorAll: () => [], closest: () => null, remove() {},
                         classList: { add() {}, remove() {}, toggle() {} } }, extra || {});
}
function javob(status, data) {
  return { ok: status >= 200 && status < 300, status,
           json: async () => (data === undefined ? (() => { throw new Error('JSON emas'); })() : JSON.parse(JSON.stringify(data))),
           clone() { return this; } };
}
const ORTIQ = { detail: { type: 'avans_oylikdan_ortiq', message: "Oktabr 2026 uchun oylikdan qolgani 2 000 000 so'm — 8 000 000 so'mga ko'p",
                          excess: 8000000 } };

// Soxta muhit: `fetch` — `javobFn(url, n)` (n — nechanchi so'rov), `customConfirm` — `ha` qiymati (ketma-ket ro'yxat ham bo'ladi)
function muhit(o) {
  const elementlar = o.elementlar || {};
  const xabarlar = [], sorovlar = [], tasdiqlar = [];
  let n = 0;
  const haRoy = Array.isArray(o.ha) ? o.ha.slice() : null;
  const ctx = {
    console, JSON, String, Number, Math, Promise, parseFloat, parseInt, isNaN, isFinite, Array, Object, Error, Set, Map,
    encodeURIComponent, Date, RegExp, Boolean,
    document: { getElementById: (id) => { if (!(id in elementlar)) elementlar[id] = el(); return elementlar[id]; },
                createElement: () => el(), querySelectorAll: () => [], querySelector: () => null, addEventListener() {} },
    window: {}, location: { reload() { xabarlar.push('[reload]'); }, href: '' }, setTimeout: () => 0, clearTimeout() {},
    fetch: async (url, opts) => { sorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET' }); return o.javobFn(String(url), n++); },
    alert: (t) => xabarlar.push(String(t)), xabarOyna: async (t) => { xabarlar.push(String(t)); },
    showMsg: (t) => xabarlar.push(String(t)),
    customConfirm: async (a, b) => { tasdiqlar.push([a, b]); return haRoy ? !!haRoy.shift() : (o.ha === undefined ? true : !!o.ha); },
    yukSessiyaKor() {}, loadAdvanceHistory() {}, loadEmployees() {}, removeAdvRow: (id) => xabarlar.push('[removeAdvRow ' + id + ']'),
    advTugmalar() {}, tkHozir: () => ({ yil: 2026, oy: 10, kun: 11 }),
    // kech155 (zip 210 «Naqd / Bank / Karta», MOSLANDI): «qaysi hisobdan» — base.html tanlovi (soxta DOMda chizilmaydi — standart 'naqd')
    hisobQiymat: () => 'naqd', hisobTanla() {}, hisobTanlovChiz: () => null,
  };
  vm.createContext(ctx);
  return { ctx, elementlar, xabarlar, sorovlar, tasdiqlar };
}
function yukla(m, src, nomlar) {
  const yoq = [];
  for (const [s, ns] of src) for (const nm of ns) { const f = olib(s, nm); if (f) vm.runInContext(f, m.ctx); else yoq.push(nm); }
  for (const nm of nomlar || []) { if (!(nm in m.ctx) && !yoq.includes(nm)) yoq.push(nm); }
  return yoq;
}
// kech155 (zip 210 «Naqd / Bank / Karta», MOSLANDI): formasiz pul amali (oylikni yopish, so'rov tasdig'i) — base.html `hisobSora` (u `customConfirm` ni chaqiradi)
const BASE_FN = ['escapeHtml', 'xatoSababi', 'serverXatoSababi', 'amalSababi', 'avansYubor', 'hisobSora'];

(async () => {
  bolim('A — base.html `avansYubor`');
  {
    const m = muhit({ javobFn: (u, n) => (n === 0 ? javob(409, ORTIQ) : javob(200, { status: 'ok', id: 5, keyingi_oyga: 8000000 })) });
    const yoq = yukla(m, [[BASE, BASE_FN]]);
    tekshir('A0 base.html da `avansYubor` (va `amalSababi`) bor', !yoq.length, yoq);
    if (!yoq.length) {
      const r = await m.ctx.avansYubor('/api/employees/3/advance?amount=10000000&notes=&adv_date=2026-10-11');
      tekshir("A1 409 `avans_oylikdan_ortiq` — oyna server xabari bilan, «Ha» — o'sha so'rov `&confirm_excess=true` bilan",
              r.ok && m.tasdiqlar.length === 1 && String(m.tasdiqlar[0][1]).includes('8 000 000') && m.sorovlar.length === 2
              && m.sorovlar[1].url === '/api/employees/3/advance?amount=10000000&notes=&adv_date=2026-10-11&confirm_excess=true'
              && m.sorovlar[1].method === 'POST', { r, s: m.sorovlar, t: m.tasdiqlar });
      const m2 = muhit({ ha: false, javobFn: () => javob(409, ORTIQ) });
      yukla(m2, [[BASE, BASE_FN]]);
      const r2 = await m2.ctx.avansYubor('/api/admin/advance-requests/7/confirm');
      tekshir("A2 «Bekor» — qayta so'rov YO'Q, natija `bekor`", !r2.ok && r2.bekor === true && m2.sorovlar.length === 1, { r2, s: m2.sorovlar });
      const m3 = muhit({ javobFn: (u, n) => (n === 0 ? javob(409, ORTIQ) : javob(200, { success: true })) });
      yukla(m3, [[BASE, BASE_FN]]);
      await m3.ctx.avansYubor('/api/admin/advance-requests/7/confirm');
      tekshir("A3 «?» siz manzil — `?confirm_excess=true`", m3.sorovlar[1] && m3.sorovlar[1].url === '/api/admin/advance-requests/7/confirm?confirm_excess=true', m3.sorovlar);
      const m4 = muhit({ javobFn: () => javob(409, { detail: "So'rov allaqachon ko'rib chiqilgan" }) });
      yukla(m4, [[BASE, BASE_FN]]);
      const r4 = await m4.ctx.avansYubor('/x?y=1');
      tekshir("A4 boshqa 409 — oyna YO'Q, sabab serverdan", !r4.ok && !m4.tasdiqlar.length && r4.holat === 409 && r4.xato.includes('allaqachon'), r4);
      const m5 = muhit({ javobFn: () => javob(400, { detail: "Summa musbat bo'lishi kerak" }) });
      yukla(m5, [[BASE, BASE_FN]]);
      const r5 = await m5.ctx.avansYubor('/x?y=1');
      tekshir('A5 400 — sabab serverdan', !r5.ok && r5.xato.includes('musbat'), r5);
      const m6 = muhit({ javobFn: () => { throw new TypeError('Failed to fetch'); } });
      yukla(m6, [[BASE, BASE_FN]]);
      const r6 = await m6.ctx.avansYubor('/x?y=1');
      tekshir("A6 tarmoq uzildi — «internet aloqasi yo'q»", !r6.ok && r6.xato.includes('internet'), r6);
    }
  }

  bolim("K — kpi.html: avans berish va «Joriy oy» kartasi");
  {
    const m = muhit({ elementlar: { 'adv-amount': el({ value: '10000000' }), 'adv-date': el({ value: '2026-10-11' }), 'adv-notes': el({ value: '' }),
                                    'adv-save-btn': el({ textContent: 'Saqlash' }) },
                      javobFn: (u, n) => (n === 0 ? javob(409, ORTIQ) : javob(200, { status: 'ok', id: 9 })) });
    m.ctx.advanceEmpId = 3;
    const yoq = yukla(m, [[BASE, BASE_FN], [KPI, ['parseNum', 'narxMatni', 'narxniOqi', 'narxKorinishi', 'fmt', 'saveAdvance']]]);
    tekshir('K0 funksiyalar topildi', !yoq.length, yoq);
    if (!yoq.length) {
      vm.runInContext('var advanceEmpId = 3;', m.ctx);
      await m.ctx.saveAdvance();
      tekshir("K1 oylikdan ko'p avans — so'raldi va `confirm_excess=true` bilan qayta yuborildi, maydon tozalandi",
              m.tasdiqlar.length === 1 && m.sorovlar.length === 2 && m.sorovlar[1].url.endsWith('&confirm_excess=true')
              && m.sorovlar[0].url.includes('&hisob=naqd')     // kech155 (zip 210 «Naqd / Bank / Karta», MOSLANDI): qaysi hisobdan berildi
              && m.elementlar['adv-amount'].value === '', { s: m.sorovlar, x: m.xabarlar });
      const m2 = muhit({ elementlar: { 'adv-amount': el({ value: '100000' }), 'adv-date': el({ value: '2026-10-11' }), 'adv-notes': el({ value: '' }),
                                       'adv-save-btn': el() }, javobFn: () => javob(400, { detail: "'adv_date' YYYY-MM-DD ko'rinishidagi haqiqiy sana bo'lishi kerak" }) });
      yukla(m2, [[BASE, BASE_FN], [KPI, ['parseNum', 'narxMatni', 'narxniOqi', 'narxKorinishi', 'fmt', 'saveAdvance']]]);
      vm.runInContext('var advanceEmpId = 3;', m2.ctx);
      await m2.ctx.saveAdvance();
      tekshir('K2 rad — xabarda server sababi', m2.xabarlar.some(x => x.includes('YYYY-MM-DD')), m2.xabarlar);
    }
    // «Joriy oy» kartasi — `yukBlok` soxtasi muvaffaqiyat shoxini darhol chaqiradi
    const mk = muhit({ elementlar: { 'k-emp-calculated': el(), 'k-emp-unpaid': el(), 'emp-fin-1': el(), 'emp-status-1': el(),
                                     'emp-fin-2': el(), 'emp-status-2': el() }, javobFn: () => javob(200, {}) });
    const yk = yukla(mk, [[BASE, ['escapeHtml']], [KPI, ['fmt', 'loadCurrentMonthEmpStatus']]]);
    tekshir('K3 `loadCurrentMonthEmpStatus` topildi', !yk.length, yk);
    if (!yk.length) {
      mk.ctx.yukBlok = (nom, url, ok) => { ok({ hodimlar_breakdown: [
        { employee_id: 1, amount: 3000000, avans: 5000000, qolgan: -2000000, oldingi_oydan: 5000000, keyingi_oyga: 0, avans_jami: 0 },
        { employee_id: 2, amount: 3000000, avans: 3000000, qolgan: 0, oldingi_oydan: 0, keyingi_oyga: 8000000, avans_jami: 11000000 }] }); };
      mk.ctx.yukXatoKor = () => {}; mk.ctx.yukXato = () => new Error('x'); mk.ctx.yukXatoMatn = () => '';
      await mk.ctx.loadCurrentMonthEmpStatus();
      const s1 = toza(mk.elementlar['emp-status-1'].innerHTML), f1 = toza(mk.elementlar['emp-fin-1'].innerHTML);
      tekshir("K4 qolgan −2 000 000 — «🟠 Hodim qarzdor: 2 000 000 so'm» (ilgari «🟢 To'liq to'langan»), «Hodim qarzi» 2 000 000",
              s1.includes('Hodim qarzdor') && s1.includes('2 000 000') && !s1.includes("To'liq to'langan") && f1.includes('Hodim qarzi')
              && f1.includes('2 000 000'), { s1, f1 });
      tekshir("K5 o'tgan oydan ushlangan qism ko'rinadi", f1.includes("o'tgan oydan") && f1.includes('5 000 000'), f1);
      const f2 = toza(mk.elementlar['emp-fin-2'].innerHTML), s2 = toza(mk.elementlar['emp-status-2'].innerHTML);
      tekshir("K6 keyingi oyga o'tgan 8 000 000 — izoh; holat «To'liq to'langan»", f2.includes('keyingi oy') && f2.includes('8 000 000')
              && s2.includes("To'liq to'langan"), { f2, s2 });
      // kech140 (zip 168, sinov saytida JONLI O'LCHANDI — 756 px panel): kenglik cheklanmagan izoh qatori hodim qatorini 312 → 515 px
      // ga kengaytirib, holat belgisini ekrandan chiqarardi; cheklov bilan 312 / 312
      tekshir("K6b izoh qatori kengligi cheklangan (qator toshmaydi)", /max-width:\s*1[0-9]{2}px/.test(f2.split('keyingi oy')[0].slice(-400)), f2);
    }
  }

  // kech140 (zip 168, sinov saytida JONLI TOPILDI): avans berilgach ro'yxat qayta chizilardi, «To'langan / Qolgan» va holat bo'sh qolardi
  {
    const mr = muhit({ elementlar: { empList: el(), 'k-emp-count': el() }, javobFn: () => javob(200, {}) });
    let holatChaqirildi = 0;
    const yr = yukla(mr, [[BASE, ['escapeHtml']], [KPI, ['fmt', 'loadEmployees']]]);
    tekshir('K7a `loadEmployees` topildi', !yr.length, yr);
    if (!yr.length) {
      for (const pc of KPI.match(/^const PAY_[A-Z_]+ = \{[\s\S]*?\};/gm) || []) vm.runInContext(pc.replace('const ', 'var '), mr.ctx);
      mr.ctx.yukNavbat = () => () => true;
      mr.ctx.yukOl = async (url) => (String(url).startsWith('/api/employees/') ? { advances: [], total: 0 }
        : [{ id: 5, name: 'H', pay_type: 'fixed', fixed_amount: 1000000, is_active: true, avans_holat: {} }]);
      mr.ctx.yukXato = () => new Error('x'); mr.ctx.yukXatoMatn = () => ''; mr.ctx.yukRoyxatXato = () => {};
      mr.ctx.loadCurrentMonthEmpStatus = async () => { holatChaqirildi++; };
      let xato = null;
      mr.ctx.console = { log() {}, warn() {}, error() {}, info() {} };    // qator chizish yordamchilari shart emas (holat chaqiruvi tekshiriladi)
      try { await mr.ctx.loadEmployees(); } catch (e) { xato = String(e && e.stack || e); }
      tekshir("K7 hodimlar ro'yxati qayta chizilgach joriy oy holati («To'langan / Qolgan», belgi) ham qayta yuklanadi",
              !xato && holatChaqirildi === 1, { xato, holatChaqirildi });
    }
  }

  bolim("D — debts.html «oylikni yopish»");
  {
    const m = muhit({ ha: [true, true], javobFn: (u, n) => (n === 0 ? javob(409, ORTIQ) : javob(200, { success: true })) });
    const yoq = yukla(m, [[BASE, BASE_FN], [DEBTS, ['fmt', 'closeEmployeeDebt']]]);
    tekshir('D0 funksiyalar topildi', !yoq.length, yoq);
    if (!yoq.length) {
      await m.ctx.closeEmployeeDebt(3, 'H', 50000000, 2026, 10);
      tekshir("D1 qolgandan ko'p — ikkinchi oyna (oylikdan ko'p) va `confirm_excess=true` bilan qayta, sahifa yangilandi",
              m.tasdiqlar.length === 2 && m.sorovlar.length === 2 && m.sorovlar[1].url.endsWith('&confirm_excess=true')
              && m.sorovlar[0].url.includes('&hisob=naqd')     // kech155 (zip 210 «Naqd / Bank / Karta», MOSLANDI): tasdiq oynasida tanlangan hisob
              && m.xabarlar.includes('[reload]'), { s: m.sorovlar, t: m.tasdiqlar, x: m.xabarlar });
      const m2 = muhit({ javobFn: () => javob(400, { detail: "'month' 1–12 bo'lishi kerak" }) });
      yukla(m2, [[BASE, BASE_FN], [DEBTS, ['fmt', 'closeEmployeeDebt']]]);
      await m2.ctx.closeEmployeeDebt(3, 'H', 100, 2026, 10);
      tekshir("D2 rad — sabab bilan (ilgari «Xato yuz berdi»)", m2.xabarlar.some(x => x.includes("1–12")), m2.xabarlar);
    }
  }

  bolim("H — _hodim_oynalari.html: hodim so'rovini tasdiqlash");
  {
    const m = muhit({ javobFn: (u, n) => (n === 0 ? javob(409, ORTIQ) : javob(200, { success: true, advance_id: 4 })) });
    const yoq = yukla(m, [[BASE, BASE_FN], [HO, ['confirmAdvReq']]]);
    tekshir('H0 funksiya topildi', !yoq.length, yoq);
    if (!yoq.length) {
      await m.ctx.confirmAdvReq(7);
      tekshir("H1 oylikdan ko'p so'rov — so'raldi, `?confirm_excess=true` bilan tasdiqlandi, qator olib tashlandi",
              // kech155 (zip 210 «Naqd / Bank / Karta», MOSLANDI): tasdiq oynasida tanlangan hisob — `?hisob=naqd`, ortiqchasi — `&confirm_excess=true`
              m.sorovlar.length === 2 && m.sorovlar[1].url === '/api/admin/advance-requests/7/confirm?hisob=naqd&confirm_excess=true'
              && m.xabarlar.includes('[removeAdvRow 7]'), { s: m.sorovlar, x: m.xabarlar });
      const m2 = muhit({ javobFn: () => javob(404, { detail: "So'rov topilmadi yoki allaqachon ko'rib chiqilgan" }) });
      yukla(m2, [[BASE, BASE_FN], [HO, ['confirmAdvReq']]]);
      await m2.ctx.confirmAdvReq(8);
      tekshir('H2 404 — sabab ko\'rsatildi va qator olib tashlandi', m2.xabarlar.some(x => x.includes('allaqachon'))
              && m2.xabarlar.includes('[removeAdvRow 8]'), m2.xabarlar);
    }
  }

  bolim("P — hodim_panel.html «Oyligim»");
  {
    const m = muhit({ javobFn: () => javob(200, {}) });
    const yoq = yukla(m, [[PANEL, ['escapeHtml', 'tolovBelgisi', 'tolovQatorHtml', 'oylikHtml']]]);
    tekshir('P0 `oylikHtml` topildi', !yoq.includes('oylikHtml'), yoq);
    if (!yoq.includes('oylikHtml')) {
      const h1 = toza(m.ctx.oylikHtml({ nomi: 'Oktabr 2026', joriy: true, hisoblangan: 3000000, olingan: 3000000, qolgan: 0, bonus: 0,
                                    kamaytirish: 0, keyingi_oyga: 8000000, oldingi_oydan: 0, tolovlar: [] }));
      const h2 = toza(m.ctx.oylikHtml({ nomi: 'Noyabr 2026', joriy: true, hisoblangan: 3000000, olingan: 8000000, qolgan: -5000000, bonus: 0,
                                    kamaytirish: 0, keyingi_oyga: 0, oldingi_oydan: 8000000, tolovlar: [] }));
      tekshir("P1 keyingi oyga o'tgan qism — «keyingi oy oyligidan ushlanadi»", h1.includes('8 000 000') && h1.includes('keyingi oy oyligidan'), h1);
      tekshir("P2 o'tgan oydan kelgan qism va «Ortiqcha olingan»", h2.includes("o'tgan oyda ortiqcha olingan") && h2.includes('Ortiqcha olingan'), h2);
    }
  }

  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) console.log('YIQILGANLAR:\n  ' + FAILED.join('\n  '));
  process.exit(FAIL ? 1 : 0);
})().catch(e => { console.log('QULADI: ' + (e && e.stack || e)); console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL + 1}   jami = ${OK + FAIL + 1}`); process.exit(1); });
