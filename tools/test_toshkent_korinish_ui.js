#!/usr/bin/env node
/**
 * test_toshkent_korinish_ui.js — kech106, 9 + 50-band C qismi darvozasi (BRAUZER ko'rinishi). FOYDALANUVCHI QARORI
 * (kech105, 2026-09-28): "Toshkent vaqti bo'yicha" — ekrandagi sana-vaqt, "bugun" standart sanasi va joriy oy / yil
 * brauzer qaysi mintaqada bo'lmasin TOSHKENT (UTC+5, yozgi vaqt yo'q — server `database.TASHKENT_OFFSET`).
 *
 * NIMA UCHUN (asl kod staging `e627685` da O'LCHANGAN — `work/probe106ui.py`, HAQIQIY Chromium; brauzer soati Toshkent
 * 01.10.2026 02:00, yozuvlar Toshkent 01.10.2026 01:30):
 *   * server vaqtni UTC da, zona belgisiz beradi ("2026-09-30T20:30:00") — `new Date(s)` uni brauzerning MAHALLIY vaqti
 *     deb o'qiydi: Toshkent kompyuterida to'lov / yuk xati / xarid / harakat / xarajat / kassa / avans / KPI / loyiha /
 *     TM / tizim tekshiruvi vaqtlari 5 soat orqada ("30.09"; oktyabr filtri ichidagi xarajat "30.09" ko'rinardi);
 *   * `new Date().toISOString().slice(0, 10)` — UTC sanasi: Toshkent 00:00–05:00 da hodim avans so'rovi, kirim hujjati,
 *     kunlik xarajat, yangi xarajat, avans berish standart sanasi KECHAGI kun; majburiyatni tez to'lash OKTYABR to'lovini
 *     30.09 ga (sentyabr hisobotiga) yozardi; xarajatni tahrirlash oynasi tungi xarajat sanasini 30.09 qilib qo'yardi;
 *   * brak xulosasi "shu oy" — mahalliy oy boshi UTC ga o'girilib, Toshkent brauzerida HAR DOIM oldingi oyning oxirgi
 *     kuni; "bugun ishlab chiqarilgan" — 0; UTC / Nyu-York brauzerida joriy oy sentyabr, muddat "5 kun qoldi".
 *
 * BO'LIMLAR
 *   H — `templates/base.html` dagi yagona yordamchilar (tkMs, tkDate, tkSana, tkVaqt, tkSanaVaqt, tkToliq, tkISO, tkHozir,
 *       tkKunFarqi): o'qish (zona belgisiz / Z / ofset / mikrosoniya / bo'shliq / faqat sana / noto'g'ri), Toshkent kun
 *       chegarasi (UTC 18:59:59 → 30.09, 19:00 → 01.10), yil chegarasi, kun farqi
 *   T — shablonlarning HAQIQIY funksiyalari (HTML dan jonli o'qiladi, soxta DOM / fetch / soat bilan): qarzdorlar (tez
 *       to'lov sanasi, to'lovlar tarixi), qaytarishlar ("shu oy"), moliya (yangi / tahrir sanasi, xarajatlar jadvali,
 *       kassa tarixi, kunlik sana, standart oy), KPI (avans sanasi va tarixi, hisobot oyi, yil), buyurtmalar (yuk xatlari,
 *       hisob-kitob belgisi vaqti), TM ("bugun"), tizim tekshiruvi, loyihalar (to'lovlar, voqealar, muddat), hisobotlar
 *       (joriy oy), bosh sahifa (avans so'rovi, majburiyatlar oyi), ta'minotchilar ("Bugun / Kecha"), ombor harakati,
 *       hodim paneli / kirim / kunlik xarajat standart sanasi
 *   S — statik: tk bloki base.html va hodim_panel.html da AYNAN; shablon JS da `new Date(` faqat saralashda (a − b),
 *       `toISOString` / mahalliy `getMonth…` / `toLocaleDateString` / sana `.slice(0, 10)` yo'q; kutilgan tk chaqiruvlari
 *
 * H va T bo'limlari UCH brauzer mintaqasida (Asia/Tashkent, UTC, America/New_York — alohida jarayon, `TZ`) yuradi:
 * natija hammasida AYNAN bir xil bo'lishi SHART. "Hozir" — UTC 30.09.2026 21:00 (Toshkent 01.10.2026 02:00).
 *
 *     node tools/test_toshkent_korinish_ui.js          (REPO=<papka> — boshqa daraxtga qarshi)
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const cp = require('child_process');

const ROOT = process.env.REPO || path.dirname(__dirname);
const MINTAQALAR = ['Asia/Tashkent', 'UTC', 'America/New_York'];
const TK_NOMLAR = ['tkMs', 'tkDate', 'tkSana', 'tkVaqt', 'tkSanaVaqt', 'tkToliq', 'tkISO', 'tkHozir', 'tkKunFarqi'];

function oqi(nom) {
  try { return fs.readFileSync(path.join(ROOT, 'templates', nom), 'utf8'); } catch (e) { return ''; }
}
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
function qisqa(x) {
  let s;
  try { s = typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { s = String(x); }
  s = String(s);
  return s.length > 300 ? s.slice(0, 300) + '…' : s;
}

let OK = 0, FAIL = 0;
const FAILED = [];
function tekshir(label, shart, izoh) {
  let s = false;
  try { s = typeof shart === 'function' ? !!shart() : !!shart; } catch (e) { s = false; izoh = String(e); }
  if (s) { OK++; console.log(`  ✓ ${label}`); }
  else {
    FAIL++; FAILED.push(label);
    console.log(`  ✗ ${label}${izoh !== undefined ? '   — ' + qisqa(izoh) : ''}`);
  }
}
function bolim(t) { console.log(`\n--- ${t} ---`); }

// ═════════════════════════════════════ ICHKI jarayon (bitta mintaqa) ═════════════════════════════════════
async function ichki() {
  const TZ = process.env.TZ || '?';
  const RealDate = Date;
  const HOZIR = RealDate.UTC(2026, 8, 30, 21, 0, 0);            // Toshkent 01.10.2026 02:00
  const LAHZA = '2026-09-30T20:30:00';                          // Toshkent 01.10.2026 01:30
  const T_MS = RealDate.UTC(2026, 9, 1, 1, 30, 0);             // Toshkent devor soati (UTC maydonlarida)
  const S_UZ = new RealDate(T_MS).toLocaleDateString('uz', {timeZone: 'UTC'});
  const V_UZ = new RealDate(T_MS).toLocaleTimeString('uz', {hour: '2-digit', minute: '2-digit', timeZone: 'UTC'});
  const SV_UZ = S_UZ + ' ' + V_UZ;
  const T_UZ = new RealDate(T_MS).toLocaleString('uz', {timeZone: 'UTC'});
  const S_RU = new RealDate(T_MS).toLocaleDateString('ru-RU', {timeZone: 'UTC'});
  const UTC_UZ = new RealDate(RealDate.UTC(2026, 8, 30, 20, 30)).toLocaleDateString('uz', {timeZone: 'UTC'});   // "30/09/2026"

  function soxtaDate(ms) {
    return class D extends RealDate {
      constructor(...a) { if (a.length === 0) super(ms); else super(...a); }
      static now() { return ms; }
    };
  }
  const BASE = oqi('base.html');
  const HOD = oqi('hodim_panel.html');
  const yordamchilar = (src) => TK_NOMLAR.map(n => olib(src, n)).filter(Boolean).join('\n') + '\n' + (olib(src, 'escapeHtml') || '');
  const YORDAMCHI = yordamchilar(BASE);        // base.html ni kengaytiradigan sahifalar
  const HOD_YORDAMCHI = yordamchilar(HOD);     // hodim_panel.html — O'Z nusxasi (base.html ga bog'lanmagan)

  function element(id) {
    const e = {
      id, value: '', textContent: '', innerHTML: '', style: {}, dataset: {}, checked: true, disabled: false, options: [],
      classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
      appendChild() {}, querySelector() { return null; }, querySelectorAll() { return []; }, addEventListener() {},
      focus() {}, setSelectionRange() {}, reset() {},
    };
    return e;
  }
  function muhit(o) {
    o = o || {};
    const ELS = {};
    const SOROV = [];
    const ctx = {
      Date: soxtaDate(o.hozir === undefined ? HOZIR : o.hozir), console: { log() {}, error() {}, warn() {} },
      Math, JSON, Promise, Object, Array, String, Number, parseInt, parseFloat, isNaN, RegExp, Intl, Error,
      setTimeout: (f) => { try { f(); } catch (e) {} return 0; }, clearTimeout() {},
      alert: (m) => { ctx.__alert = String(m); }, confirm: () => true, prompt: () => o.prompt === undefined ? null : o.prompt,
      location: { reload() { ctx.__reload = true; }, href: '' },
      showMsg() {}, customConfirm: async () => true, showConfirmModal: async () => true,
      document: {
        getElementById(id) { if (!(id in ELS)) ELS[id] = element(id); return ELS[id]; },
        querySelector() { return null; }, querySelectorAll() { return []; }, createElement() { return element('?'); },
        body: element('body'), activeElement: null, addEventListener() {},
      },
      fetch: async (url, opt) => {
        SOROV.push({ url: String(url), opt: opt || null });
        let data = null;
        for (const [k, v] of Object.entries(o.javob || {})) { if (String(url).indexOf(k) === 0) { data = v; break; } }
        return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(data)), text: async () => JSON.stringify(data) };
      },
    };
    ctx.window = ctx;
    vm.createContext(ctx);
    vm.runInContext(o.yordamchi === undefined ? YORDAMCHI : o.yordamchi, ctx);
    if (o.qoshimcha) vm.runInContext(o.qoshimcha, ctx);
    return { ctx, ELS, SOROV, el: (id) => ctx.document.getElementById(id) };
  }
  function fnlar(src, nomlar) {
    return nomlar.map(n => olib(src, n)).filter(Boolean).map(s => s.replace(/\{%[\s\S]*?%\}/g, '')).join('\n');
  }
  async function yurgiz(m, kod) {
    const p = vm.runInContext(`(async () => { ${kod} })()`, m.ctx);
    return await Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('vaqt tugadi')), 3000))]);
  }
  function soz(src, nom) {   // `const NOM = …;` (bir qatorli)
    const m = new RegExp('const\\s+' + nom + '\\s*=\\s*([^\\n]*);').exec(src);
    return m ? `var ${nom} = ${m[1]};` : '';
  }

  // ─────────────────────────────── H: yordamchilar ───────────────────────────────
  bolim(`H. Yordamchilar (base.html) — brauzer mintaqasi ${TZ}`);
  const xv = (ctx, kod) => { try { return vm.runInContext(kod, ctx); } catch (e) { return 'XATO: ' + e.message; } };
  const H = muhit();
  const hv = (kod) => xv(H.ctx, kod);
  tekshir('H1 base.html da 9 ta yordamchi bor (tkMs … tkKunFarqi)', TK_NOMLAR.every(n => hv(`typeof ${n}`) === 'function'),
          TK_NOMLAR.filter(n => hv(`typeof ${n}`) !== 'function'));
  tekshir('H2 tkMs: zona belgisiz server vaqti — UTC ("2026-09-30T20:30:00" → UTC 20:30)',
          hv(`tkMs('2026-09-30T20:30:00')`) === RealDate.UTC(2026, 8, 30, 20, 30), hv(`tkMs('2026-09-30T20:30:00')`));
  tekshir('H3 tkMs: mikrosoniya (.123456), bo\'shliq ("2026-09-30 20:30:00"), Z, +05:00 ofset',
          hv(`tkMs('2026-09-30T20:30:00.123456')`) === RealDate.UTC(2026, 8, 30, 20, 30, 0, 123)
          && hv(`tkMs('2026-09-30 20:30:00')`) === RealDate.UTC(2026, 8, 30, 20, 30)
          && hv(`tkMs('2026-09-30T20:30:00Z')`) === RealDate.UTC(2026, 8, 30, 20, 30)
          && hv(`tkMs('2026-10-01T01:30:00+05:00')`) === RealDate.UTC(2026, 8, 30, 20, 30),
          [hv(`tkMs('2026-09-30T20:30:00.123456')`), hv(`tkMs('2026-09-30 20:30:00')`), hv(`tkMs('2026-10-01T01:30:00+05:00')`)]);
  tekshir('H4 tkMs: faqat sana ("2026-10-01") — o\'sha kun 00:00 UTC; null / "" / undefined / "abc" — NaN; Date va son — o\'zi',
          hv(`tkMs('2026-10-01')`) === RealDate.UTC(2026, 9, 1) && hv(`[tkMs(null), tkMs(''), tkMs(undefined), tkMs('abc')].every(isNaN)`) === true
          && hv(`tkMs(new Date(5000))`) === 5000 && hv(`tkMs(7)`) === 7);
  tekshir(`H5 tkISO() (bugun) — "2026-10-01"; tkHozir() — 2026 / 10 / 1 (brauzer soati UTC 30.09 21:00)`,
          hv(`tkISO()`) === '2026-10-01' && hv(`JSON.stringify(tkHozir())`) === '{"yil":2026,"oy":10,"kun":1}',
          [hv(`tkISO()`), hv(`JSON.stringify(tkHozir())`)]);
  tekshir(`H6 tkSana / tkVaqt / tkSanaVaqt / tkToliq — "${S_UZ}", "${V_UZ}", "${SV_UZ}", "${T_UZ}" (Toshkent 01.10 01:30)`,
          hv(`tkSana('${LAHZA}')`) === S_UZ && hv(`tkVaqt('${LAHZA}')`) === V_UZ && hv(`tkSanaVaqt('${LAHZA}')`) === SV_UZ
          && hv(`tkToliq('${LAHZA}')`) === T_UZ,
          [hv(`tkSana('${LAHZA}')`), hv(`tkVaqt('${LAHZA}')`), hv(`tkToliq('${LAHZA}')`)]);
  tekshir(`H7 til / format saqlanadi: tkSana(v, 'ru-RU') — "${S_RU}"; uzun oy nomi`,
          hv(`tkSana('${LAHZA}', 'ru-RU')`) === S_RU
          && hv(`tkSana('2026-10-01', 'uz', {day:'numeric', month:'long', year:'numeric'})`)
             === new RealDate(RealDate.UTC(2026, 9, 1)).toLocaleDateString('uz', {day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'}),
          [hv(`tkSana('${LAHZA}', 'ru-RU')`)]);
  tekshir('H8 Toshkent kun chegarasi: UTC 30.09 18:59:59 → "2026-09-30", 19:00:00 → "2026-10-01"',
          hv(`tkISO('2026-09-30T18:59:59')`) === '2026-09-30' && hv(`tkISO('2026-09-30T19:00:00')`) === '2026-10-01',
          [hv(`tkISO('2026-09-30T18:59:59')`), hv(`tkISO('2026-09-30T19:00:00')`)]);
  tekshir('H9 tkKunFarqi: muddat 05.10 → 4; Toshkent 01.10 00:00 → 0; 30.09 23:59 → −1; noto\'g\'ri — NaN',
          hv(`tkKunFarqi('2026-10-05T00:00:00')`) === 4 && hv(`tkKunFarqi('2026-09-30T19:00:00')`) === 0
          && hv(`tkKunFarqi('2026-09-30T18:59:00')`) === -1 && hv(`isNaN(tkKunFarqi(null))`) === true,
          [hv(`tkKunFarqi('2026-10-05T00:00:00')`), hv(`tkKunFarqi('2026-09-30T19:00:00')`), hv(`tkKunFarqi('2026-09-30T18:59:00')`)]);
  tekshir('H10 qiymat yo\'q — bo\'sh satr (tkSana / tkVaqt / tkSanaVaqt / tkToliq / tkISO)',
          hv(`[tkSana(null), tkVaqt(''), tkSanaVaqt(undefined), tkToliq(null), tkISO(null)].every(x => x === '')`) === true);
  const HT = muhit({ hozir: RealDate.UTC(2026, 8, 30, 19, 30) });             // Toshkent 01.10.2026 00:30
  const HT2 = muhit({ hozir: RealDate.UTC(2026, 8, 30, 18, 59, 59) });        // Toshkent 30.09.2026 23:59:59
  tekshir('H12 "bugun" kun chegarasida: soat Toshkent 01.10 00:30 → tkISO() "2026-10-01", tkHozir oy 10; '
          + '30.09 23:59:59 → "2026-09-30", oy 9',
          xv(HT.ctx, `tkISO() + ' ' + tkHozir().oy`) === '2026-10-01 10' && xv(HT2.ctx, `tkISO() + ' ' + tkHozir().oy`) === '2026-09-30 9',
          [xv(HT.ctx, `tkISO() + ' ' + tkHozir().oy`), xv(HT2.ctx, `tkISO() + ' ' + tkHozir().oy`)]);
  const HY = muhit({ hozir: RealDate.UTC(2026, 11, 31, 19, 30) });            // Toshkent 01.01.2027 00:30
  const HY2 = muhit({ hozir: RealDate.UTC(2026, 11, 31, 18, 30) });           // Toshkent 31.12.2026 23:30
  tekshir('H11 yil chegarasi: Toshkent 01.01.2027 00:30 → 2027 / 1 / "2027-01-01"; 31.12.2026 23:30 → 2026 / 12',
          xv(HY.ctx, `JSON.stringify(tkHozir()) + tkISO()`) === '{"yil":2027,"oy":1,"kun":1}2027-01-01'
          && xv(HY2.ctx, `JSON.stringify(tkHozir())`) === '{"yil":2026,"oy":12,"kun":31}',
          [xv(HY.ctx, `JSON.stringify(tkHozir()) + tkISO()`), xv(HY2.ctx, `JSON.stringify(tkHozir())`)]);

  // ─────────────────────────────── T: shablon funksiyalari ───────────────────────────────
  bolim(`T. Shablonlarning haqiqiy funksiyalari — brauzer mintaqasi ${TZ}`);
  const DEBTS = oqi('debts.html'), RET = oqi('returns.html'), FIN = oqi('finance.html'), KPI = oqi('kpi.html');
  const ORD = oqi('orders.html'), FIN2 = oqi('finished.html'), LOGS = oqi('logs.html'), PRJ = oqi('projects.html');
  const REP = oqi('reports.html'), DASH = oqi('dashboard.html'), SUP = oqi('suppliers.html'), INV = oqi('inventory.html');
  const RCV = oqi('supplier_receive.html'), KX = oqi('kunlik_xarajat.html');
  const PUL = ['parseNum', 'narxMatni', 'narxniOqi', 'narxKorinishi', 'serverSababi', 'fmt', 'fmtFull', 'formatNum',
               'fmtShort', 'mvFmtQty', 'suggestedReserve'];

  async function sinov(label, fn) {
    try { await fn(); } catch (e) { tekshir(label, false, 'XATO: ' + e.message); }
  }

  await sinov('T1', async () => {
    const m = muhit({ prompt: '1000', qoshimcha: fnlar(DEBTS, PUL.concat(['quickPayObligation'])) });
    await yurgiz(m, `await quickPayObligation('arenda', 'Arenda', 1000);`);
    const b = m.SOROV.filter(s => s.opt && s.opt.method === 'POST').map(s => JSON.parse(s.opt.body || '{}'));
    tekshir('T1 qarzdorlar — joriy oy majburiyatini tez to\'lash: sana 2026-10-01T00:00:00 (asl: 2026-09-30 — sentyabrga!)',
            b.length === 1 && b[0].date === '2026-10-01T00:00:00' && b[0].amount === 1000, b);
    const m2 = muhit({ prompt: '500', qoshimcha: fnlar(DEBTS, PUL.concat(['quickPayObligation'])) });
    await yurgiz(m2, `await quickPayObligation('arenda', 'Arenda', 500, 2026, 9);`);
    const b2 = m2.SOROV.filter(s => s.opt && s.opt.method === 'POST').map(s => JSON.parse(s.opt.body || '{}'));
    tekshir('T2 qarzdorlar — O\'TGAN oy (sentyabr) qarzi: sana o\'sha oyning 28-kuni (o\'zgarmagan qoida)',
            b2.length === 1 && b2[0].date === '2026-09-28T00:00:00', b2);
  });
  await sinov('T3', async () => {
    const m = muhit({ qoshimcha: fnlar(DEBTS, PUL.concat(['renderTimeline'])) });
    await yurgiz(m, `renderTimeline([{date: '${LAHZA}', amount: 1000, notes: 'n', created_by: 'x'}]);`);
    const h = m.el('tl-list').innerHTML;
    tekshir(`T3 qarzdorlar — to'lovlar tarixi (shu oy): "${S_UZ}"`, h.includes(S_UZ) && !h.includes(UTC_UZ), h);
    const m2 = muhit({ javob: { '/api/obligations/timeline': [] }, qoshimcha: fnlar(DEBTS, PUL.concat(['openObligTimeline', 'renderTimeline'])) });
    await yurgiz(m2, `await openObligTimeline('arenda', 'Arenda');`);
    tekshir('T4 qarzdorlar — tarix so\'rovi joriy Toshkent oyi uchun (year=2026&month=10)',
            m2.SOROV.some(s => s.url.includes('year=2026&month=10')), m2.SOROV.map(s => s.url));
  });
  await sinov('T5', async () => {
    const m = muhit({ qoshimcha: fnlar(RET, ['brakSummaryThisMonth']) + '\nfunction loadBrakSummary() {}' });
    await yurgiz(m, `brakSummaryThisMonth();`);
    tekshir('T5 qaytarishlar — brak xulosasi "shu oy": 2026-10-01 … 2026-10-01 (asl: Toshkentda 2026-09-30 dan)',
            m.el('brak-sum-start').value === '2026-10-01' && m.el('brak-sum-end').value === '2026-10-01',
            [m.el('brak-sum-start').value, m.el('brak-sum-end').value]);
  });
  await sinov('T6', async () => {
    // kech117 (A2): openTxModal / editTx yashirin yo'nalish variantini `txYonalishVarianti` bilan tayyorlaydi
    const m = muhit({ qoshimcha: fnlar(FIN, PUL.concat(['openTxModal', 'editTx', 'txYonalishVarianti'])) });
    await yurgiz(m, `openTxModal();`);
    const yangi = m.el('tx-f-date').value;
    await yurgiz(m, `editTx(5, '${LAHZA}', 'boshqa', 7000, '', '');`);
    const tahrir = m.el('tx-f-date').value;
    await yurgiz(m, `editTx(6, '2026-09-15T00:00:00', 'boshqa', 7000, '', '');`);
    const sanali = m.el('tx-f-date').value;
    tekshir('T6 moliya — yangi xarajat standart sanasi 2026-10-01 (asl: 2026-09-30)', yangi === '2026-10-01', yangi);
    tekshir('T7 moliya — tungi xarajatni tahrirlash sanasi 2026-10-01 (asl: 2026-09-30 — saqlansa sentyabrga ko\'chardi); '
            + 'faqat sana 2026-09-15 — o\'zgarmaydi', tahrir === '2026-10-01' && sanali === '2026-09-15', [tahrir, sanali]);
  });
  await sinov('T8', async () => {
    const m = muhit({ javob: { '/api/finance/transactions': [{ id: 1, date: LAHZA, category: 'boshqa', amount: 7000, source: 'manual' }] },
                      qoshimcha: fnlar(FIN, PUL.concat(['loadDailyTransactions'])) + '\n' + soz(FIN, 'CAT_LABELS') + '\n'
                                 + soz(FIN, 'SOURCE_LABELS') + '\n' + soz(FIN, 'CAT_ICONS') });
    m.el('tx-date').value = '2026-10-01';
    m.el('tx-whole-month').checked = true;
    await yurgiz(m, `await loadDailyTransactions();`);
    const h = m.el('tx-body').innerHTML;
    tekshir(`T8 moliya — xarajatlar jadvali (oktyabr): tungi xarajat "${S_UZ}" (asl: "${UTC_UZ}")`, h.includes(`<td>${S_UZ}</td>`), h.slice(0, 200));
  });
  await sinov('T9', async () => {
    const m = muhit({ javob: { '/api/finance/cash-transactions': [{ id: 1, created_at: LAHZA, category: 'boshlangich', amount: 5 }] },
                      qoshimcha: fnlar(FIN, PUL.concat(['loadCashTxHistory'])) });
    await yurgiz(m, `await loadCashTxHistory();`);
    const h = m.el('cashTxHistoryList').innerHTML;
    tekshir(`T9 moliya — kassa tarixi (ru-RU format saqlangan): "${S_RU}"`, h.includes(S_RU), h.slice(0, 300));
  });
  await sinov('T10', async () => {
    const m = muhit({ javob: { '/api/finance/daily': { date: '2026-10-01', sales: { total: 0, orders_count: 0, profit: 0, cost: 0 },
                                                          expenses: { total: 0, material: { breakdown: [] }, other: { breakdown: [] }, transport: null } } },
                      qoshimcha: fnlar(FIN, PUL.concat(['loadDailyFinance'])) + '\nfunction animateCounter() {}' });
    await yurgiz(m, `await loadDailyFinance();`);
    const kut = new RealDate(RealDate.UTC(2026, 9, 1)).toLocaleDateString('uz', {day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'});
    tekshir(`T10 moliya — kunlik hisobot sanasi "${kut}" (asl: G'arb mintaqasida — oldingi kun)`, m.el('daily-date').textContent === kut,
            m.el('daily-date').textContent);
  });
  await sinov('T11', async () => {
    const m = muhit();
    // finance.html boshlang'ich qatori: standart oy / yil
    const q = /const now=[^\n]*\n[^\n]*sel-month[^\n]*\n[^\n]*sel-year[^\n]*/.exec(FIN);
    if (q) vm.runInContext(q[0].replace('const now=', 'var now='), m.ctx);
    tekshir('T11 moliya — standart oy / yil: 10 / 2026 (asl: UTC va G\'arb brauzerida 9)',
            q && String(m.el('sel-month').value) === '10' && String(m.el('sel-year').value) === '2026',
            [q && q[0].slice(0, 80), m.el('sel-month').value, m.el('sel-year').value]);
  });
  await sinov('T12', async () => {
    const m = muhit({ javob: { '/api/employees/7/advances': { total: 30000, advances: [{ id: 1, date: LAHZA, amount: 30000, notes: '' }] } },
                      qoshimcha: fnlar(KPI, PUL.concat(['openAdvanceModal', 'loadAdvanceHistory'])) + '\nvar advanceEmpId = null;' });
    await yurgiz(m, `openAdvanceModal(7, 'Hodim'); await loadAdvanceHistory(7);`);
    tekshir('T12 KPI — avans berish standart sanasi 2026-10-01 (asl: 2026-09-30)', m.el('adv-date').value === '2026-10-01', m.el('adv-date').value);
    const h = m.el('adv-history').innerHTML;
    tekshir(`T13 KPI — avanslar tarixi: joriy Toshkent oyi so'raladi va sana "${S_UZ}"`,
            m.SOROV.some(s => s.url === '/api/employees/7/advances?year=2026&month=10') && h.includes(S_UZ),
            [m.SOROV.map(s => s.url), h.slice(0, 160)]);
  });
  await sinov('T14', async () => {
    const m = muhit({ qoshimcha: fnlar(KPI, ['initEmpReportSelectors']) + '\n' + soz(KPI, 'MONTH_NAMES_UZ') });
    await yurgiz(m, `initEmpReportSelectors();`);
    const q = /document\.getElementById\('kpi-year'\)\.value = [^\n]*;/.exec(KPI.split('\n').filter(l => /^document\.getElementById\('kpi-year'\)/.test(l)).join('\n'));
    if (q) vm.runInContext(q[0], m.ctx);
    tekshir('T14 KPI — hodimlar hisoboti oyi / yili 10 / 2026, usta KPI yili 2026',
            String(m.el('emp-report-month').value) === '10' && String(m.el('emp-report-year').value) === '2026'
            && q && String(m.el('kpi-year').value) === '2026',
            [m.el('emp-report-month').value, m.el('emp-report-year').value, m.el('kpi-year').value]);
  });
  await sinov('T15', async () => {
    const dlv = { order_number: 'ORD-1', client_name: 'M', status: 'in_progress',
                  deliveries: [{ id: 3, delivery_number: 'ORD-1/Y-1', short_number: 'Y-1', delivered_at: LAHZA, total_sum: 100,
                                 items: [{ item_name: 'Detal', quantity: 1, unit: 'metr' }] }] };
    const m = muhit({ qoshimcha: fnlar(ORD, PUL.concat(['openSummaryModal', 'renderDeliveryHistory'])) + '\n'
                                 + soz(ORD, 'DLV_HISTORY_LIMIT') + '\nvar dlvHistoryExpanded = false; function updateSumTotal() {}\n'
                                 + `var dlvData = ${JSON.stringify(dlv)};` });
    await yurgiz(m, `openSummaryModal(); renderDeliveryHistory(true);`);
    const s = m.el('sumList').innerHTML, h = m.el('dlvHistory').innerHTML;
    const ts = (/data-ts="(\d+)"/.exec(s) || [])[1];
    tekshir(`T15 buyurtmalar — yuk xatlari tarixi "${SV_UZ}", hisob-kitob ro'yxati "${S_UZ}"`, h.includes(SV_UZ) && s.includes(S_UZ),
            [h.slice(0, 120), s.slice(0, 120)]);
    tekshir('T16 buyurtmalar — hisob-kitob "oxirgi N kun" belgisi — HAQIQIY vaqt (UTC 30.09 20:30), 5 soat xatosiz',
            Number(ts) === RealDate.UTC(2026, 8, 30, 20, 30), ts);
  });
  await sinov('T17', async () => {
    const items = [{ id: 1, source: 'produced', created_at: LAHZA, quantity: 1, reserve: 0 },
                   { id: 2, source: 'produced', created_at: '2026-09-30T18:59:00', quantity: 1, reserve: 0 },
                   { id: 3, source: 'returned', created_at: LAHZA, quantity: 1, reserve: 0 }];
    const m = muhit({ javob: { '/api/finished/stats': { in_progress_count: 0, total_value: 0 } },
                      qoshimcha: fnlar(FIN2, PUL.concat(['loadStats', 'openHistoryModal',
                      // kech114 (7A): statistika guruhlar va birliklar bo'yicha — loadStats yordamchilari
                      'miqdorlarMatni', 'fpMiqdor', 'fpGuruhla', 'fpGuruhXulosa', 'fpGuruhKaliti', 'fpJarayondami',
                      'fpGuruhKammi', 'suggestedReserve', 'fpWidth2', 'unitLabel'])) + `\nvar fpItems = ${JSON.stringify(items)};` });
    await yurgiz(m, `await loadStats(); openHistoryModal(1);`);
    tekshir('T17 TM — "bugun ishlab chiqarilgan": 1 tur (Toshkent 01.10 01:30 — bugun; 30.09 23:59 — kecha; asl: 0)',
            m.el('k-today-produced').textContent === '1 tur', m.el('k-today-produced').textContent);
    tekshir(`T18 TM — tarix "Yaratilgan sana": "${T_UZ}"`, m.el('hist-body').innerHTML.includes(T_UZ), m.el('hist-body').innerHTML.slice(0, 400));
  });
  await sinov('T19', async () => {
    const m = muhit({ javob: { '/api/system/health-check': { checked_at: LAHZA, technical_hidden: true, financial: null } },
                      qoshimcha: fnlar(LOGS, ['runHealthCheck']) });
    await yurgiz(m, `await runHealthCheck();`);
    tekshir(`T19 tizim tekshiruvi — "Tekshirilgan sana: ${T_UZ}"`, m.el('health-results').innerHTML.includes(`Tekshirilgan sana: ${T_UZ}`),
            m.el('health-results').innerHTML.slice(0, 200));
  });
  await sinov('T20', async () => {
    const jv = { '/api/orders?project_id=': [{ id: 9, order_number: 'ORD-9', status: 'ready', created_at: LAHZA, completed_at: LAHZA }],
                 '/api/payments?order_id=': [{ id: 1, amount: 1000, paid_at: LAHZA, payment_method: 'naqd' }] };
    const m = muhit({ javob: jv, qoshimcha: fnlar(PRJ, PUL.concat(['renderPayments', 'renderTimeline', 'loadStatusPanel']))
                                            + '\nvar selectedProjId = 1; var progressMap = {};' });
    await yurgiz(m, `await renderPayments({});`);
    const p = m.el('tabContent').innerHTML;
    await yurgiz(m, `await renderTimeline({startRaw: '2026-09-15', name: 'L'});`);
    const t = m.el('tabContent').innerHTML;
    tekshir(`T20 loyihalar — to'lovlar "${S_UZ}", voqealar "${T_UZ}"`, p.includes(S_UZ) && t.includes(T_UZ), [p.slice(0, 150), t.slice(0, 200)]);
    await yurgiz(m, `await loadStatusPanel({id: 1, budget: 0, paid: 0, orders: 1, status: 'ACTIVE', deadlineRaw: '2026-10-05T00:00:00'});`);
    const q1 = m.el('statusPanel').innerHTML;
    await yurgiz(m, `await loadStatusPanel({id: 1, budget: 0, paid: 0, orders: 1, status: 'ACTIVE', deadlineRaw: '2026-09-30T00:00:00'});`);
    const q2 = m.el('statusPanel').innerHTML;
    tekshir('T21 loyihalar — muddat 05.10: "4 kun qoldi", 30.09: "1 kun kechikdi" (Toshkent kalendari; asl UTC / G\'arbda "5 kun")',
            q1.includes('4 kun qoldi') && q2.includes('1 kun kechikdi'), [(/\d+ kun \w+/.exec(q1) || [])[0], (/\d+ kun \w+/.exec(q2) || [])[0]]);
  });
  await sinov('T22', async () => {
    const m = muhit({ javob: { '/api/finance/history': [], '/api/reports/comparison': {} },
                      qoshimcha: fnlar(REP, PUL.concat(['loadKpi'])) + '\n' + soz(REP, 'MONTH_NAMES') });
    await yurgiz(m, `await loadKpi();`);
    tekshir('T22 hisobotlar — joriy oy "Oktabr 2026" (asl: UTC / G\'arbda sentyabr)',
            m.el('kpiPeriodLabel').textContent.includes('Oktabr 2026'), m.el('kpiPeriodLabel').textContent);
  });
  await sinov('T23', async () => {
    const m = muhit({ javob: { '/api/admin/pending-advance-requests': [{ id: 1, employee_name: 'H', amount: 1, requested_date: '2026-10-01T00:00:00' }],
                               '/api/obligations/status': { recurring: [], employees: [] }, '/api/suppliers': [], '/api/suppliers/due-dates': [] },
                      qoshimcha: fnlar(DASH, ['checkPendingAdvanceRequests', 'loadObligationsWidget']) });
    await yurgiz(m, `await checkPendingAdvanceRequests(); await loadObligationsWidget();`);
    tekshir(`T23 bosh sahifa — avans so'rovi sanasi "${S_UZ}" (faqat sana — kalendar kuni)`, m.el('advReqList').innerHTML.includes(S_UZ),
            m.el('advReqList').innerHTML.slice(0, 200));
    tekshir('T24 bosh sahifa — majburiyatlar joriy Toshkent oyi uchun (year=2026&month=10)',
            m.SOROV.some(s => s.url === '/api/obligations/status?year=2026&month=10'), m.SOROV.map(s => s.url));
  });
  await sinov('T25', async () => {
    const m = muhit({ qoshimcha: fnlar(SUP, ['daysAgoText']) });
    const d = (v) => xv(m.ctx, `daysAgoText(${JSON.stringify(v)})`);
    tekshir('T25 ta\'minotchilar — oxirgi xarid Toshkent 01.10 01:30 → "Bugun"; 30.09 23:59 → "Kecha" (asl: "Bugun"); '
            + '30.09 00:00 → "Kecha"; 20.09 → "11 kun oldin"; yo\'q → "Hali xarid yo\'q"',
            d(LAHZA) === 'Bugun' && d('2026-09-30T18:59:00') === 'Kecha' && d('2026-09-29T19:00:00') === 'Kecha'
            && d('2026-09-20T12:00:00') === '11 kun oldin' && d(null) === "Hali xarid yo'q",
            [d(LAHZA), d('2026-09-30T18:59:00'), d('2026-09-29T19:00:00'), d('2026-09-20T12:00:00')]);
    const eski = d('2026-08-01T20:00:00');           // Toshkent 02.08.2026 01:00
    tekshir('T26 ta\'minotchilar — 30 kundan eski TUNGI xarid — Toshkent sanasi 02.08 (asl: mahalliy 01.08)',
            eski === new RealDate(RealDate.UTC(2026, 7, 2, 1)).toLocaleDateString('uz', {timeZone: 'UTC'}), eski);
  });
  await sinov('T27', async () => {
    const m = muhit({ qoshimcha: fnlar(INV, ['mvRowHtml', 'mvFmtQty']) });
    const h = String(xv(m.ctx, `mvRowHtml({created_at: '${LAHZA}', item_name: 'Akril', movement_type: 'out', quantity: 1, unit: 'kg'})`));
    tekshir(`T27 ombor — harakat qatori "${SV_UZ}"`, h.includes(SV_UZ), h.slice(0, 200));
  });
  const standart = (nom, src, re, yordamchi, hozir) => {
    const m = muhit({ yordamchi, hozir });
    const q = re.exec(src);
    let v = null;
    if (q) { try { vm.runInContext(q[0], m.ctx); v = m.el(nom).value; } catch (e) { v = 'XATO ' + e.message; } }
    return v;
  };
  const FDATE = /document\.getElementById\('f-date'\)\.value = [^;\n]*;/;
  const T_0030 = RealDate.UTC(2026, 8, 30, 19, 30);                           // Toshkent 01.10.2026 00:30
  tekshir('T28 hodim paneli — avans so\'rovi standart sanasi 2026-10-01 (Toshkent 02:00 va 00:30 da; panelning O\'Z '
          + 'yordamchilari; asl: 2026-09-30)',
          standart('f-date', HOD, FDATE, HOD_YORDAMCHI) === '2026-10-01' && standart('f-date', HOD, FDATE, HOD_YORDAMCHI, T_0030) === '2026-10-01',
          [standart('f-date', HOD, FDATE, HOD_YORDAMCHI), standart('f-date', HOD, FDATE, HOD_YORDAMCHI, T_0030)]);
  tekshir('T29 kirim hujjati — standart sana 2026-10-01 (asl: 2026-09-30)',
          standart('r-date', RCV, /document\.getElementById\('r-date'\)\.value = [^;\n]*;/) === '2026-10-01',
          standart('r-date', RCV, /document\.getElementById\('r-date'\)\.value = [^;\n]*;/));
  tekshir('T30 kunlik xarajat — standart sana 2026-10-01 (asl: 2026-09-30)',
          standart('kx-date', KX, /document\.getElementById\('kx-date'\)\.value = [^;\n]*;/) === '2026-10-01',
          standart('kx-date', KX, /document\.getElementById\('kx-date'\)\.value = [^;\n]*;/));
  await sinov('T31', async () => {
    const HB = HOD.indexOf('function tkMs(') >= 0;
    const m = muhit({ yordamchi: HOD_YORDAMCHI, qoshimcha: fnlar(HOD, ['loadMyRequests']) });
    m.ctx.fetch = async () => ({ ok: true, json: async () => [{ amount: 1, requested_date: '2026-10-01T00:00:00', status: 'pending', notes: '' }] });
    await yurgiz(m, `await loadMyRequests();`);
    tekshir(`T31 hodim paneli — so'rovlar ro'yxati sanasi "${S_UZ}" (panelning O'Z yordamchilari bilan)`,
            HB && m.el('req-list').innerHTML.includes(S_UZ), m.el('req-list').innerHTML.slice(0, 200));
  });

  console.log(`\nICHKI: ok=${OK} fail=${FAIL}`);
}

// ═════════════════════════════════════ TASHQI jarayon ═════════════════════════════════════
function statik() {
  bolim('S. Statik — shablonlar');
  const fayllar = fs.readdirSync(path.join(ROOT, 'templates')).filter(f => f.endsWith('.html')).sort();
  const BASE = oqi('base.html'), HOD = oqi('hodim_panel.html');
  function blok(src) {
    const i = src.indexOf('// ══ UMUMIY (kech106');
    const f = olib(src, 'tkKunFarqi');
    if (i < 0 || !f) return null;
    const j = src.indexOf(f) + f.length;
    return src.slice(i, j);
  }
  const bB = blok(BASE), bH = blok(HOD);
  tekshir('S1 tk bloki base.html da bor va hodim_panel.html dagi nusxa bilan AYNAN (belgilar soni ' + (bB ? bB.length : 0) + ')',
          bB && bH && bB === bH, [bB ? bB.length : null, bH ? bH.length : null]);
  function jsQismi(src) {
    // tk blokidan tashqari, faqat <script> ichidagi matn
    const b = blok(src);
    const s = b ? src.replace(b, '') : src;
    const out = [];
    const re = /<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g;
    let m;
    while ((m = re.exec(s))) out.push(m[1]);
    return out.join('\n').split('\n').map(q => q.replace(/\/\/.*$/, '')).join('\n');
  }
  const SARALASH = /new Date\((?:[^()]|\([^()]*\))*\)\s*-\s*new Date\((?:[^()]|\([^()]*\))*\)/g;
  const buzilish = { newDate: [], iso: [], mahalliy: [], locale: [], kesim: [] };
  for (const f of fayllar) {
    const js = jsQismi(oqi(f)).replace(SARALASH, 'SARALASH');
    js.split('\n').forEach((q, i) => {
      if (/new Date\(/.test(q)) buzilish.newDate.push(`${f}: ${q.trim().slice(0, 90)}`);
      if (/\.toISOString\(/.test(q)) buzilish.iso.push(`${f}: ${q.trim().slice(0, 90)}`);
      if (/\.get(FullYear|Month|Date|Day|Hours|Minutes|Seconds|TimezoneOffset)\(/.test(q)) buzilish.mahalliy.push(`${f}: ${q.trim().slice(0, 90)}`);
      if (/\.toLocale(Date|Time)String\(/.test(q)) buzilish.locale.push(`${f}: ${q.trim().slice(0, 90)}`);
      if (/(_at|[dD]ate|deadline|sana|Iso)\b[^;\n]{0,12}\)?\.(slice|substring)\(0,\s*10\)|split\(['"]T['"]\)/.test(q)) buzilish.kesim.push(`${f}: ${q.trim().slice(0, 90)}`);
    });
  }
  tekshir('S2 shablon JS da `new Date(` faqat saralashda (a − b) — server vaqti / "hozir" tk yordamchilari orqali', !buzilish.newDate.length, buzilish.newDate);
  tekshir('S3 `toISOString()` (UTC sanasi) — faqat tk blokida', !buzilish.iso.length, buzilish.iso);
  tekshir('S4 mahalliy `getFullYear / getMonth / getDate / getHours …` — yo\'q (joriy oy / yil — tkHozir)', !buzilish.mahalliy.length, buzilish.mahalliy);
  tekshir('S5 `toLocaleDateString / toLocaleTimeString` — faqat tk blokida', !buzilish.locale.length, buzilish.locale);
  tekshir('S6 server sanasini `.slice(0, 10)` / `split(\'T\')` bilan kesish yo\'q (tkISO)', !buzilish.kesim.length, buzilish.kesim);
  const KUT = {
    'orders.html': ['tkSanaVaqt(dl.delivered_at)', 'tkSana(d.delivered_at)', 'tkMs(d.delivered_at)', 'tkSana(order.deadline)',
                    'tkKunFarqi(order.deadline)', 'tkSanaVaqt(p.paid_at)', 'tkISO(order.deadline)'],
    'inventory.html': ['tkSanaVaqt(p.purchased_at)', 'tkSanaVaqt(e.latest)', 'tkSanaVaqt(g.latestDate)', 'tkSanaVaqt(m.created_at)'],
    'suppliers.html': ['tkSana(p.purchased_at)', 'tkSana(p.paid_at)', 'tkKunFarqi(iso)'],
    'supplier_receive.html': ['tkSana(p.purchased_at)', "getElementById('r-date').value = tkISO()"],
    'projects.html': ['tkKunFarqi(d.deadlineRaw)', 'tkSana(o.created_at)', 'tkSana(p.paid_at)', 'tkSana(m.created_at)', 'tkToliq(e.date)'],
    'kpi.html': ['tkSana(r.completed_at)', 'tkSana(a.date)', "getElementById('adv-date').value = tkISO()"],
    'dashboard.html': ['tkSana(due.due_date)', 'tkSana(r.requested_date)'],
    'hodim_panel.html': ["getElementById('f-date').value = tkISO()", 'tkSana(r.requested_date)'],
    'returns.html': ['tkISO(x.sana)'],
    'finance.html': ["tkSana(r.created_at, 'ru-RU')", 'tkSana(t.date)', 'tkISO(dateIso)'],
    'logs.html': ['tkToliq(d.checked_at)'],
    'finished.html': ['tkToliq(item.created_at)', 'tkISO(i.created_at)'],
  };
  const yoq = [];
  for (const [f, lst] of Object.entries(KUT)) { const s = oqi(f); lst.forEach(x => { if (!s.includes(x)) yoq.push(`${f}: ${x}`); }); }
  tekshir(`S7 kutilgan tk chaqiruvlari joyida (${Object.values(KUT).reduce((a, b) => a + b.length, 0)} ta)`, !yoq.length, yoq);
  const tkIshlatadi = fayllar.filter(f => /\btk(Ms|Date|Sana|Vaqt|SanaVaqt|Toliq|ISO|Hozir|KunFarqi)\(/.test(jsQismi(oqi(f))));
  const asossiz = tkIshlatadi.filter(f => f !== 'base.html' && f !== 'hodim_panel.html' && !/\{%\s*extends\s+["']base\.html["']\s*%\}/.test(oqi(f)));
  const TK_SAHIFALAR = ['dashboard.html', 'debts.html', 'finance.html', 'finished.html', 'hodim_panel.html', 'inventory.html',
                        'kpi.html', 'kunlik_xarajat.html', 'logs.html', 'orders.html', 'projects.html',
                        'reports.html', 'returns.html', 'supplier_receive.html', 'suppliers.html'];
  tekshir(`S8 tk ishlatadigan shablonlar (${TK_SAHIFALAR.length} ta kutilgan) base.html ni kengaytiradi (hodim_panel — o'z nusxasi)`,
          TK_SAHIFALAR.every(f => tkIshlatadi.includes(f)) && !asossiz.length,
          [TK_SAHIFALAR.filter(f => !tkIshlatadi.includes(f)), asossiz]);
  tekshir('S9 nazorat: statik qidiruv sun\'iy buzilishni TOPADI (`new Date(x.paid_at).toLocaleDateString`, `toISOString().slice(0, 10)`)',
          (() => {
            const q = "const d = new Date(p.paid_at).toLocaleDateString('uz'); const b = new Date().toISOString().slice(0, 10);";
            const t = q.replace(SARALASH, 'SARALASH');
            return /new Date\(/.test(t) && /\.toISOString\(/.test(t) && /\.toLocale(Date|Time)String\(/.test(t)
                   && !/new Date\(/.test('x.sort((a,b) => new Date(b.created_at) - new Date(a.created_at))'.replace(SARALASH, 'SARALASH'));
          })());
}

function tashqi() {
  statik();
  for (const tz of MINTAQALAR) {
    bolim(`Mintaqa ${tz} (alohida jarayon)`);
    const r = cp.spawnSync(process.execPath, [__filename, '--ichki'], { env: Object.assign({}, process.env, { TZ: tz, REPO: ROOT }),
                                                                            encoding: 'utf8', timeout: 120000 });
    const out = String(r.stdout || '') + String(r.stderr || '');
    out.split('\n').forEach(q => { if (q.trim()) console.log(`[${tz}] ${q}`); });
    const m = /ICHKI: ok=(\d+) fail=(\d+)/.exec(out);
    if (!m) { FAIL++; FAILED.push(`${tz}: ichki jarayon natija bermadi (rc ${r.status})`); console.log(`  ✗ ${tz}: ichki jarayon natija bermadi (rc ${r.status})`); continue; }
    OK += Number(m[1]); FAIL += Number(m[2]);
    out.split('\n').filter(q => /^\s*✗/.test(q)).forEach(q => FAILED.push(`[${tz}] ${q.trim().slice(2, 120)}`));
  }
  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('Yiqilganlar:'); FAILED.forEach(f => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
}

if (process.argv.includes('--ichki')) {
  ichki().then(() => process.exit(0)).catch(e => { console.log('ICHKI XATO: ' + (e && e.stack || e)); process.exit(2); });
} else {
  tashqi();
}
