#!/usr/bin/env node
/**
 * test_loyiha_forma.js — Loyiha formalaridagi "Mijoz Telegram ID" va izoh.
 *
 * NIMA UCHUN KERAK (16-band, 2026-09-21)
 * --------------------------------------
 * Mijozning Telegram ID si alohida ustunda emas, `projects.notes` ichida
 * "tg_id=..." ko'rinishida saqlanadi. Server (main.py — yuk xati PDF va
 * "Buyurtma tayyor" xabari) ID ni `notes.split('tg_id=')[1].split(',')[0]`
 * bilan o'qiydi. Ya'ni bu xususiyatning YARMI brauzerda (`projects.html`)
 * yashaydi va hech bir Python testi unga tegmaydi.
 *
 * O'lchangan nuqsonlar (asl kod, jonli sinov saytida ham):
 *   1) Yaratish formasida JSON obyektida `notes` kaliti IKKI MARTA yozilgan
 *      edi — JavaScript da ikkinchisi yutadi, Telegram ID JIMGINA yo'qolardi
 *      (123456789 kiritildi → serverga `notes: null` ketdi).
 *   2) ID kiritilsa izoh butunlay tashlab yuborilardi; tahrir oynasi esa
 *      ID bor loyihaning izohini bo'sh ko'rsatardi.
 *   3) Raqam bo'lmagan ID ("@user") saqlanar, server uni jim e'tiborsiz
 *      qoldirardi.
 *
 * QANDAY ISHLAYDI
 * ---------------
 * Funksiyalar `templates/projects.html` dan JONLI o'qiladi (nusxa
 * ko'chirilmaydi), soxta DOM va soxta `fetch` ichida ishga tushiriladi,
 * serverga KETADIGAN tana o'lchanadi va server o'qish qoidasining aynan
 * taqlidi bilan tekshiriladi. Server qoidasi o'zgarsa — statik tekshiruv
 * yiqiladi (taqlid eskirib qolmasligi uchun).
 *
 * Asl (tuzatilmagan) faylga qarshi ham QULAMAYDI: topilmagan funksiya —
 * yiqilgan tekshiruv sifatida hisoblanadi.
 *
 * ISHLATISH
 * ---------
 *     node tools/test_loyiha_forma.js
 *     node tools/test_loyiha_forma.js boshqa/yo'l/projects.html   (mutatsiya uchun)
 *
 * Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const HTML_YOLI = process.argv[2] || path.join(ROOT, 'templates', 'projects.html');
const MAIN_YOLI = path.join(ROOT, 'main.py');
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
function teng(label, olingan, kutilgan) {
  const a = JSON.stringify(olingan), b = JSON.stringify(kutilgan);
  tekshir(label, a === b, a === b ? '' : `olingan=${a} kutilgan=${b}`);
}
function bolim(t) { console.log(`\n${'='.repeat(66)}\n${t}\n${'='.repeat(66)}`); }

// ── Funksiyani HTML dan nomi bo'yicha ajratib olish (`async` bilan) ──
// Qavs hisobi satr/shablon ichidagi qavslarni ham sanaydi, lekin bu
// funksiyalarda muvozanatli — natija `vm` da sintaksis bilan tekshiriladi.
function olib(nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(SRC);
  if (!m) return null;
  const i = m.index;
  let d = 0;
  const j = SRC.indexOf('{', i + m[0].length);
  // Parametr ro'yxatidagi qavslardan keyingi birinchi `{` — tana boshi.
  for (let k = j; k < SRC.length; k++) {
    if (SRC[k] === '{') d++;
    else if (SRC[k] === '}') { d--; if (d === 0) return SRC.slice(i, k + 1); }
  }
  return null;
}
function olibConst(nom) {
  const re = new RegExp('const\\s+' + nom + '\\s*=\\s*[^;]+;');
  const m = re.exec(SRC);
  return m ? m[0] : null;
}

// ── Soxta DOM ──
function soxtaElement(id) {
  return {
    id, value: '', textContent: '', disabled: false,
    style: {}, dataset: {}, classList: { add() {}, remove() {} },
  };
}

function muhitYarat() {
  const elementlar = {};
  const soxtaSorovlar = [];
  const toastlar = [];
  const ctx = {
    console,
    JSON, String, Number, Math, parseFloat, parseInt, RegExp, Promise,
    setTimeout: () => 0,     // location.reload ni kechiktiradigan taymer — o'chiq
    location: { reload() { ctx.__reload = (ctx.__reload || 0) + 1; } },
    projToast: (t) => { toastlar.push(String(t)); },
    document: {
      getElementById(id) {
        if (!elementlar[id]) elementlar[id] = soxtaElement(id);
        return elementlar[id];
      },
      querySelector(sel) { return ctx.__kartaSelektor ? ctx.__kartaSelektor(sel) : null; },
    },
    fetch: async (url, opts) => {
      soxtaSorovlar.push({ url: String(url), method: (opts && opts.method) || 'GET',
                           body: opts && opts.body });
      return { ok: true, status: 200, json: async () => ({ id: 1 }) };
    },
    escapeHtml: (s) => String(s),
    selectedProjId: 7,
    isSavingNewProject: false,
    isSavingEditProject: false,
  };
  vm.createContext(ctx);
  return { ctx, elementlar, soxtaSorovlar, toastlar };
}

function yukla(muhit, nomlar) {
  const topilmadi = [];
  let kod = '';
  const c = olibConst('LOYIHA_TG_ID_RE');
  if (c) kod += c.replace(/^const\s+/, 'var ') + '\n';
  for (const n of nomlar) {
    const f = olib(n);
    if (!f) { topilmadi.push(n); continue; }
    kod += f + '\n';
  }
  // `let isSaving...` o'rniga kontekstdagi o'zgaruvchilar ishlatiladi.
  try { vm.runInContext(kod, muhit.ctx); }
  catch (e) { return { xato: 'sintaksis: ' + e.message, topilmadi }; }
  return { xato: null, topilmadi };
}

// ── Server o'qish qoidasining AYNAN taqlidi (main.py, 2 joy) ──
//   c_tg_id = project.notes.split('tg_id=')[1].split(',')[0].strip()
//   if c_tg_id and c_tg_id.lstrip('-').isdigit(): ...
function serverOqiydi(notes) {
  if (!notes || notes.indexOf('tg_id=') < 0) return null;
  const qism = notes.split('tg_id=')[1].split(',')[0].trim();
  const raqam = qism.replace(/^-+/, '');
  if (qism && raqam.length > 0 && /^\d+$/.test(raqam)) return qism;
  return null;
}

async function main() {
  console.log(`Fayl: ${HTML_YOLI}`);

  // ================================================================
  bolim('A. Statik: server qoidasi taqlidga mos (taqlid eskirmasin)');
  // ================================================================
  const mainSrc = fs.readFileSync(MAIN_YOLI, 'utf8');
  const qoida = ".split('tg_id=')[1].split(',')[0].strip()";
  const soni = mainSrc.split(qoida).length - 1;
  tekshir(`A1 main.py da "${qoida}" 2 joyda`, soni === 2, `topildi: ${soni}`);
  tekshir("A2 main.py da ID tekshiruvi `lstrip('-').isdigit()`",
          (mainSrc.match(/tg_id\.lstrip\('-'\)\.isdigit\(\)/g) || []).length >= 2);

  // ================================================================
  bolim('B. Statik: saveProject tanasida `notes` kaliti BITTA');
  // ================================================================
  const sp = olib('saveProject');
  tekshir('B1 saveProject topildi', !!sp);
  if (sp) {
    const kalitlar = (sp.match(/(^|[{,\s])notes\s*:/g) || []).length;
    tekshir('B2 saveProject da `notes:` kaliti aynan 1 marta', kalitlar === 1,
            `topildi: ${kalitlar}`);
  }
  const se = olib('saveEditProject');
  tekshir('B3 saveEditProject topildi', !!se);
  if (se) {
    const kalitlar = (se.match(/(^|[{,\s])notes\s*:/g) || []).length;
    tekshir('B4 saveEditProject da `notes:` kaliti aynan 1 marta', kalitlar === 1,
            `topildi: ${kalitlar}`);
  }

  // ================================================================
  bolim('C. loyihaIzohYasa — ID va izohdan `notes`');
  // ================================================================
  {
    const m = muhitYarat();
    const r = yukla(m, ['loyihaIzohYasa']);
    tekshir('C0 loyihaIzohYasa yuklandi', !r.xato && r.topilmadi.length === 0,
            r.xato || ('topilmadi: ' + r.topilmadi.join(',')));
    const Y = (tg, iz) => {
      try { return vm.runInContext(`loyihaIzohYasa(${JSON.stringify(tg)}, ${JSON.stringify(iz)})`, m.ctx); }
      catch (e) { return { istisno: e.message }; }
    };
    const holatlar = [
      ['C1 ikkalasi bo\'sh → null', '', '', { notes: null }],
      ['C2 faqat izoh', '', 'Fasad 2-qavat', { notes: 'Fasad 2-qavat' }],
      ['C3 faqat ID', '123456789', '', { notes: 'tg_id=123456789' }],
      ['C4 ID + izoh (izoh SAQLANADI)', '123456789', 'Fasad 2-qavat',
        { notes: 'tg_id=123456789, Fasad 2-qavat' }],
      ['C5 bo\'shliqlar kesiladi', '  123456789 ', '  salom  ', { notes: 'tg_id=123456789, salom' }],
      ['C6 guruh ID (manfiy)', '-1001234567890', '', { notes: 'tg_id=-1001234567890' }],
      ['C7 izoh faqat bo\'shliq → null', '', '    ', { notes: null }],
      ['C8 ID bor, izoh bo\'shliq', '5', '   ', { notes: 'tg_id=5' }],
      ['C9 izohda vergul bor', '5', 'a, b, c', { notes: 'tg_id=5, a, b, c' }],
      ['C10 null qiymatlar', null, null, { notes: null }],
    ];
    for (const [l, tg, iz, kut] of holatlar) teng(l, Y(tg, iz), kut);
    const xatolar = [['C11 "@user" → xato', '@user'], ['C12 "12a" → xato', '12a'],
                     ['C13 "12 34" → xato', '12 34'], ['C14 "--5" → xato', '--5'],
                     ['C15 "-" → xato', '-'], ['C16 "+998901234567" → xato', '+998901234567']];
    for (const [l, tg] of xatolar) {
      const n = Y(tg, 'izoh');
      tekshir(l, !!(n && n.xato) && !('notes' in (n || {})), JSON.stringify(n));
    }
    // Server taqlidi: yasalgan `notes` dan server AYNAN shu ID ni o'qiydi
    const juftlar = [['123456789', ''], ['123456789', 'Fasad, 2-qavat'], ['-100555', 'x'],
                     ['  42 ', ' izoh ']];
    for (const [tg, iz] of juftlar) {
      const n = Y(tg, iz);
      teng(`C17 server "${tg.trim()}" + "${iz.trim()}" dan ID ni o'qiydi`,
           serverOqiydi(n && n.notes), tg.trim());
    }
    teng('C18 ID siz izohdan server hech narsa o\'qimaydi', serverOqiydi((Y('', 'oddiy izoh') || {}).notes), null);
  }

  // ================================================================
  bolim('D. loyihaIzohAjrat — tahrir oynasi uchun ajratish');
  // ================================================================
  {
    const m = muhitYarat();
    const r = yukla(m, ['loyihaIzohYasa', 'loyihaIzohAjrat']);
    tekshir('D0 loyihaIzohAjrat yuklandi', !r.xato && r.topilmadi.length === 0,
            r.xato || ('topilmadi: ' + r.topilmadi.join(',')));
    const A = (n) => {
      try { return vm.runInContext(`loyihaIzohAjrat(${JSON.stringify(n)})`, m.ctx); }
      catch (e) { return { istisno: e.message }; }
    };
    const holatlar = [
      ['D1 faqat ID (eski format)', 'tg_id=123456789', { tg: '123456789', izoh: '' }],
      ['D2 ID + izoh', 'tg_id=123456789, Fasad 2-qavat', { tg: '123456789', izoh: 'Fasad 2-qavat' }],
      ['D3 faqat izoh', 'Fasad 2-qavat', { tg: '', izoh: 'Fasad 2-qavat' }],
      ["D4 \"Yo'q\" → bo'sh", "Yo'q", { tg: '', izoh: '' }],
      ['D5 bo\'sh', '', { tg: '', izoh: '' }],
      ['D6 null', null, { tg: '', izoh: '' }],
      ['D7 ID o\'rtada', 'a, tg_id=5, b', { tg: '5', izoh: 'a, b' }],
      ['D8 ID oxirida', 'salom tg_id=-77', { tg: '-77', izoh: 'salom' }],
      ['D9 izohda vergullar', 'tg_id=5, a, b, c', { tg: '5', izoh: 'a, b, c' }],
    ];
    for (const [l, n, kut] of holatlar) teng(l, A(n), kut);
    // Aylanma: ajrat(yasa(tg, izoh)) === {tg, izoh}
    const aylanma = [['123456789', 'Fasad 2-qavat'], ['123456789', ''], ['', 'faqat izoh'],
                     ['-100555', 'a, b'], ['', '']];
    for (const [tg, iz] of aylanma) {
      let n = null;
      try { n = vm.runInContext(`loyihaIzohYasa(${JSON.stringify(tg)}, ${JSON.stringify(iz)}).notes`, m.ctx); }
      catch (e) { n = 'ISTISNO ' + e.message; }
      teng(`D10 aylanma "${tg}" / "${iz}"`, A(n), { tg, izoh: iz });
    }
  }

  // ================================================================
  bolim('E. saveProject — yaratish formasi serverga NIMA yuboradi');
  // ================================================================
  async function yaratish(qiymatlar) {
    const m = muhitYarat();
    const r = yukla(m, ['loyihaIzohYasa', 'saveProject']);
    if (r.xato || r.topilmadi.length) return { yuklanmadi: r.xato || r.topilmadi.join(',') };
    const asos = { 'f-client': 'Karimov Botir', 'f-pname': 'Hovli fasadi', 'f-phone': '',
                   'f-address': '', 'f-tg-id': '', 'f-budget': '1000', 'f-deadline': '2026-10-15',
                   'f-notes': '' };
    const q = Object.assign({}, asos, qiymatlar);
    for (const k of Object.keys(q)) m.ctx.document.getElementById(k).value = q[k];
    try { await vm.runInContext('saveProject()', m.ctx); }
    catch (e) { return { istisno: e.message }; }
    const post = m.soxtaSorovlar.filter(s => s.method === 'POST' && s.url === '/api/projects');
    return { m, post, tana: post.length ? JSON.parse(post[0].body) : null, toast: m.toastlar };
  }
  {
    const r1 = await yaratish({ 'f-tg-id': '123456789' });
    tekshir('E0 saveProject ishladi', !r1.yuklanmadi && !r1.istisno,
            r1.yuklanmadi || r1.istisno);
    teng('E1 faqat ID → notes "tg_id=123456789" (ASL KODDA null edi)',
         r1.tana && r1.tana.notes, 'tg_id=123456789');
    teng('E2 server shu tanadan ID ni o\'qiydi', serverOqiydi(r1.tana && r1.tana.notes), '123456789');
    teng('E3 bitta POST', r1.post ? r1.post.length : -1, 1);

    const r2 = await yaratish({ 'f-tg-id': '123456789', 'f-notes': 'Fasad 2-qavat' });
    teng('E4 ID + izoh → ikkalasi saqlanadi', r2.tana && r2.tana.notes, 'tg_id=123456789, Fasad 2-qavat');

    const r3 = await yaratish({ 'f-notes': 'Fasad 2-qavat' });
    teng('E5 faqat izoh', r3.tana && r3.tana.notes, 'Fasad 2-qavat');

    const r4 = await yaratish({});
    teng('E6 ikkalasi bo\'sh → null', r4.tana ? r4.tana.notes : 'TANA YO\'Q', null);

    const r5 = await yaratish({ 'f-tg-id': '@user' });
    teng('E7 "@user" → so\'rov YUBORILMAYDI', r5.post ? r5.post.length : -1, 0);
    tekshir('E8 "@user" → foydalanuvchiga sabab ko\'rsatiladi',
            !!(r5.toast && r5.toast.some(t => /Telegram ID/.test(t))), JSON.stringify(r5.toast));
    tekshir('E9 "@user" dan keyin himoya bayrog\'i QOTIB QOLMAGAN',
            !!(r5.m && r5.m.ctx.isSavingNewProject === false));
    if (r5.m) {   // xuddi shu sahifada ID tuzatilib qayta bosiladi
      r5.m.ctx.document.getElementById('f-tg-id').value = '555';
      try { await vm.runInContext('saveProject()', r5.m.ctx); } catch (e) {}
      const p = r5.m.soxtaSorovlar.filter(s => s.method === 'POST');
      teng('E10 ID tuzatilgach qayta bosish → POST ketadi', p.length ? JSON.parse(p[0].body).notes : null,
           'tg_id=555');
    } else tekshir('E10 ID tuzatilgach qayta bosish → POST ketadi', false, 'muhit yo\'q');

    const r6 = await yaratish({ 'f-tg-id': '  777  ', 'f-notes': '  izoh  ', 'f-address': '  Andijon  ',
                                'f-phone': ' +998901234567 ' });
    teng('E11 bo\'shliqlar kesiladi (ID, izoh)', r6.tana && r6.tana.notes, 'tg_id=777, izoh');
    teng('E12 manzil kesiladi', r6.tana && r6.tana.client_address, 'Andijon');
    teng('E13 telefon kesiladi', r6.tana && r6.tana.client_phone, '+998901234567');
    // 15-band nazorati — boshqa maydonlar buzilmagan
    teng('E14 qolgan maydonlar AYNAN', r1.tana && {
      client_name: r1.tana.client_name, project_name: r1.tana.project_name,
      total_budget: r1.tana.total_budget, deadline: r1.tana.deadline,
      client_phone: r1.tana.client_phone, client_address: r1.tana.client_address },
      { client_name: 'Karimov Botir', project_name: 'Hovli fasadi', total_budget: 1000,
        deadline: '2026-10-15', client_phone: null, client_address: null });
    teng('E15 tanada ortiqcha kalit yo\'q (server "Noma\'lum maydon" bermasin)',
         r1.tana && Object.keys(r1.tana).sort(),
         ['client_address', 'client_name', 'client_phone', 'deadline', 'notes', 'project_name',
          'total_budget']);
    const r7 = await yaratish({ 'f-client': '', 'f-tg-id': '5' });
    teng('E16 mijoz bo\'sh → so\'rov yo\'q (eski tekshiruv joyida)', r7.post ? r7.post.length : -1, 0);
    const r8 = await yaratish({ 'f-phone': 'Abc', 'f-tg-id': '5' });
    teng('E17 telefon xato → so\'rov yo\'q (eski tekshiruv joyida)', r8.post ? r8.post.length : -1, 0);
  }

  // ================================================================
  bolim('F. Tahrir: openEditModal → saveEditProject');
  // ================================================================
  async function tahrir(kartaNotes, ozgartir) {
    const m = muhitYarat();
    const r = yukla(m, ['loyihaIzohYasa', 'loyihaIzohAjrat', 'openEditModal', 'saveEditProject']);
    if (r.xato || r.topilmadi.length) return { yuklanmadi: r.xato || r.topilmadi.join(',') };
    const karta = { dataset: { client: 'Karimov Botir', phone: '—', name: 'Hovli fasadi', address: '—',
                               budget: '1000', status: 'ACTIVE', notes: kartaNotes } };
    m.ctx.__kartaSelektor = () => karta;
    try { vm.runInContext('openEditModal()', m.ctx); }
    catch (e) { return { istisno: 'openEditModal: ' + e.message }; }
    const oldin = { tg: m.elementlar['e-tg-id'] && m.elementlar['e-tg-id'].value,
                    izoh: m.elementlar['e-notes'] && m.elementlar['e-notes'].value };
    if (ozgartir) for (const k of Object.keys(ozgartir)) m.ctx.document.getElementById(k).value = ozgartir[k];
    try { await vm.runInContext('saveEditProject()', m.ctx); }
    catch (e) { return { istisno: 'saveEditProject: ' + e.message, oldin }; }
    const put = m.soxtaSorovlar.filter(s => s.method === 'PUT');
    return { m, oldin, put, tana: put.length ? JSON.parse(put[0].body) : null, toast: m.toastlar };
  }
  {
    const t1 = await tahrir('tg_id=123456789, Fasad 2-qavat', null);
    tekshir('F0 tahrir ishladi', !t1.yuklanmadi && !t1.istisno, t1.yuklanmadi || t1.istisno);
    teng('F1 oyna: ID ajratildi', t1.oldin && t1.oldin.tg, '123456789');
    teng('F2 oyna: izoh KO\'RSATILDI (ASL KODDA bo\'sh edi)', t1.oldin && t1.oldin.izoh, 'Fasad 2-qavat');
    teng('F3 o\'zgartirmay saqlash → notes AYNAN qaytdi', t1.tana && t1.tana.notes,
         'tg_id=123456789, Fasad 2-qavat');
    teng('F4 PUT manzili', t1.put && t1.put[0] && t1.put[0].url, '/api/projects/7');

    const t2 = await tahrir('tg_id=123456789', null);
    teng('F5 eski format (faqat ID) → o\'zgarmay qaytadi', t2.tana && t2.tana.notes, 'tg_id=123456789');

    const t3 = await tahrir('Oddiy izoh', { 'e-tg-id': '987654321' });
    teng('F6 izohli loyihaga ID qo\'shish → izoh YO\'QOLMAYDI', t3.tana && t3.tana.notes,
         'tg_id=987654321, Oddiy izoh');

    const t4 = await tahrir('tg_id=123456789, Fasad', { 'e-tg-id': '' });
    teng('F7 ID o\'chirilsa → faqat izoh qoladi', t4.tana && t4.tana.notes, 'Fasad');

    const t5 = await tahrir("Yo'q", null);
    teng("F8 \"Yo'q\" → oynada bo'sh, saqlanganda null", [t5.oldin && t5.oldin.izoh, t5.tana && t5.tana.notes],
         ['', null]);

    const t6 = await tahrir('Izoh', { 'e-tg-id': 'abc' });
    teng('F9 "abc" → PUT yuborilmaydi', t6.put ? t6.put.length : -1, 0);
    tekshir('F10 "abc" → sabab ko\'rsatiladi', !!(t6.toast && t6.toast.some(x => /Telegram ID/.test(x))),
            JSON.stringify(t6.toast));
    tekshir('F11 "abc" dan keyin himoya bayrog\'i QOTIB QOLMAGAN',
            !!(t6.m && t6.m.ctx.isSavingEditProject === false));
    if (t6.m) {
      t6.m.ctx.document.getElementById('e-tg-id').value = '42';
      try { await vm.runInContext('saveEditProject()', t6.m.ctx); } catch (e) {}
      const p = t6.m.soxtaSorovlar.filter(s => s.method === 'PUT');
      teng('F12 tuzatilgach qayta bosish → PUT ketadi', p.length ? JSON.parse(p[0].body).notes : null,
           'tg_id=42, Izoh');
    } else tekshir('F12 tuzatilgach qayta bosish → PUT ketadi', false, 'muhit yo\'q');
    teng('F13 server tahrirdan keyin ham ID ni o\'qiydi', serverOqiydi(t3.tana && t3.tana.notes), '987654321');
    teng('F14 tahrir tanasining kalitlari o\'zgarmagan (14-band qoidasi)',
         t1.tana && Object.keys(t1.tana).sort(),
         ['client_address', 'client_name', 'client_phone', 'notes', 'project_name', 'status',
          'total_budget']);
  }

  // ================================================================
  console.log(`\n${'='.repeat(66)}`);
  console.log(`NATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  console.log('='.repeat(66));
  if (FAIL) { console.log('\nYiqilganlar:'); FAILED.forEach(f => console.log('  - ' + f)); }
  process.exit(FAIL ? 1 : 0);
}

main().catch(e => { console.log('KUTILMAGAN XATO: ' + e.stack); process.exit(1); });
