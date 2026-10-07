#!/usr/bin/env node
/**
 * test_platforma_ui.js — kech111: PLATFORMA PANELI sahifasi (templates/platforma.html) — HAQIQIY markup va HAQIQIY
 * sahifa JavaScript'i jsdom da, `fetch` soxta (server javoblari fiksturadan).
 *
 * NIMA UCHUN KERAK: egasi QARORI kech110 "B — Kartochkalar" — har mijoz korxona kartochkasi (holat belgisi, obuna
 * chizig'i, faollik), saralash (Hammasi / Faol / Muddati yaqin / Bloklangan / Sinov davri), qidiruv, «Bloklash» oynasi
 * (sabab + izoh), «Muddatni uzaytirish» (+N oy / aniq sana; yangi sana SERVERDAN — `korish=1`), «Ochish», «Uzaytirib
 * ochish», «Parolni tiklash», yangi korxona, xatolar ro'yxati. Korxona nomi / izoh / xato matni — foydalanuvchi
 * (mijoz) kiritgan matn: HTML bo'lib chizilmasligi SHART (boshqa korxona nomi orqali platforma egasining sahifasida
 * skript ishlashi — eng xavfli joy).
 *
 * BO'LIMLAR: K — kartochkalar va raqamlar; F — saralash / qidiruv; B — bloklash oynasi; U — uzaytirish oynasi;
 * O — ochish / parol / yangi korxona; X — xatolar; H — HTML in'ektsiya; S — statik.
 * Asl kodda sahifa yo'q — hamma tekshiruv yiqiladi (QULAMAYDI). ISHLATISH: node tools/test_platforma_ui.js
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
function oqi(f) { try { return fs.readFileSync(path.join(ROOT, 'templates', f), 'utf8'); } catch (e) { return ''; } }
const SRC = oqi('platforma.html');
const BASE = oqi('base.html');

let OK = 0, FAIL = 0;
const FAILED = [];
function qisqa(x) {
  let s;
  try { s = typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { s = String(x); }
  s = String(s);
  return s.length > 400 ? s.slice(0, 400) + '…' : s;
}
function tekshir(label, shart, izoh) {
  let s = false;
  try { s = !!(typeof shart === 'function' ? shart() : shart); } catch (e) { s = false; }
  if (s) { OK++; console.log(`  ✓ ${label}`); }
  else { FAIL++; FAILED.push(label); console.log(`  ✗ ${label}${izoh !== undefined ? '   — ' + qisqa(izoh) : ''}`); }
}
function bolim(t) { console.log(`\n--- ${t} ---`); }
function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
  if (!m) return null;
  let i = m.index + m[0].length, d = 1;
  for (; i < src.length && d > 0; i++) { if (src[i] === '(') d++; else if (src[i] === ')') d--; }
  const j = src.indexOf('{', i);
  if (j < 0) return null;
  d = 0;
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(m.index, k + 1); }
  }
  return null;
}
function jinjasiz(kod) {
  return kod === null ? null : kod.replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, '');
}
function blok(src, nom) {
  const i = src.indexOf(`{% block ${nom} %}`);
  if (i < 0) return '';
  const j = src.indexOf('{% endblock %}', i);
  return j < 0 ? '' : src.slice(i + `{% block ${nom} %}`.length, j);
}

let JSDOM = null, VirtualConsole = null;
try { ({ JSDOM, VirtualConsole } = require('jsdom')); } catch (e) { JSDOM = null; }

const MARKUP = jinjasiz(blok(SRC, 'content'));
const SKRIPT = (blok(SRC, 'scripts').match(/<script>([\s\S]*)<\/script>/) || [])[1] || '';
const YORDAM = ['escapeHtml', 'tkMs', 'tkDate', 'tkSana', 'tkVaqt', 'tkSanaVaqt', 'tkISO', 'tkKunFarqi', 'xatoSababi',
  'serverXatoSababi'].map(n => olib(BASE, n) || '').join('\n');

// ── Fikstura ──
const HOZIR = new Date(Date.now()).toISOString().slice(0, 19);     // server shakli: UTC, zona belgisiz
const YOMON = '<img src=x onerror="window.__xss=1">Delta';
function holat(o) {
  return Object.assign({bosqich: 'faol', bloklangan: false, avtomatik: false, sabab: null, qolgan_kun: 20,
    yopilish_kuni: null, yopilishga: null, sinov: false, obuna_boshi: '2026-09-20', obuna_tugash: '2026-10-30',
    davr_kun: 30, imtiyoz_gacha: null, bloklangan_at: null, bloklagan: null}, o);
}
function royxat() {
  return [
    {id: 1, name: 'PenodecorPro', code: 'PDP', created_at: '2026-06-01T10:00:00', users: 3, buyurtma_shu_oy: 12,
     buyurtma_jami: 90, oxirgi_kirish: HOZIR, platforma_egasi: true, blok_izoh: null,
     holat: holat({bosqich: 'muddatsiz', qolgan_kun: null, obuna_tugash: null, obuna_boshi: null, davr_kun: null})},
    {id: 2, name: 'Alfa Dekor', code: 'ALFA', created_at: '2026-08-13T20:30:00', users: 3, buyurtma_shu_oy: 9,
     buyurtma_jami: 20, oxirgi_kirish: HOZIR, platforma_egasi: false, blok_izoh: null,
     holat: holat({davr_kun: 40})},   // 20.09 → 30.10 = 40 kun (30 emas — chiziq davrga bo'linadi)
    {id: 3, name: 'Beta Fasad', code: 'BETA', created_at: '2026-09-02T08:00:00', users: 2, buyurtma_shu_oy: 4,
     buyurtma_jami: 4, oxirgi_kirish: '2026-09-01T10:00:00', platforma_egasi: false, blok_izoh: null,
     holat: holat({bosqich: 'yaqin', qolgan_kun: 3, sinov: true, obuna_tugash: '2026-10-13', davr_kun: 30})},
    {id: 4, name: 'Gamma Dekor', code: 'GAMMA', created_at: '2026-09-21T08:00:00', users: 1, buyurtma_shu_oy: 0,
     buyurtma_jami: 0, oxirgi_kirish: null, platforma_egasi: false, blok_izoh: null,
     holat: holat({bosqich: 'otgan', qolgan_kun: -1, obuna_tugash: '2026-10-09', yopilish_kuni: '2026-10-13', yopilishga: 3})},
    {id: 5, name: YOMON, code: 'DE"LTA<', created_at: '2026-06-30T08:00:00', users: 2, buyurtma_shu_oy: 0,
     buyurtma_jami: 31, oxirgi_kirish: '2026-09-08T10:00:00', platforma_egasi: false, blok_izoh: '<b>izoh</b>&',
     holat: holat({bosqich: 'bloklangan', bloklangan: true, avtomatik: true, sabab: "Obuna muddati o'tdi (avtomatik)",
       qolgan_kun: -9, obuna_tugash: '2026-10-01', bloklangan_at: '2026-10-05T04:00:00', bloklagan: 'Tizim (avtomatik)'})},
  ];
}
const SUMMARY = {raqamlar: {jami: 4, faol: 1, muddati_yaqin: 2, bloklangan: 1, sinov: 1, bugun_kirish: 7, bugun_xato: 2,
  bugun: '2026-10-10'}, aloqa_telefoni: '+998 90 555 44 33', sabablar: ["To'lov qilinmagan", "Mijoz o'zi so'radi", 'Boshqa'],
  oylar: [1, 3, 6, 12], sinov_kun: 30, imtiyoz_kun: 3};
const XATOLAR = [{id: 9, company_id: 5, korxona: YOMON, vaqt: '10.10.2026 09:00', method: 'GET', endpoint: '/api/<x>',
  kim: '<i>kim</i>', xabar: '<script>window.__xss2=1</script>xato', trace: 'Traceback <b>'}];

function jsonS(x) { return JSON.stringify(x).replace(/</g, '\\u003c'); }   // <script> ichida "</script>" bo'lmasin
function muhit(opt) {
  opt = opt || {};
  const xatolar = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => { xatolar.push(String(e && e.message || e)); });
  const html = `<!doctype html><html><head></head><body>${MARKUP}
<script>
window.__sorov = []; window.__msg = []; window.__tasdiq = [];
window.__javob = ${jsonS(opt.javob || {})};
window.__royxat = ${jsonS(royxat())};
function showMsg(m, t) { window.__msg.push([String(m), t]); }
function customConfirm(a, b) { window.__tasdiq.push([String(a), String(b)]); return Promise.resolve(true); }
function __fd(b) { const o = {}; if (b && typeof b.forEach === 'function') b.forEach((v, k) => { o[k] = String(v); }); return o; }
window.fetch = function (url, o) {
  const m = (o && o.method) || 'GET';
  window.__sorov.push({url: String(url), method: m, body: __fd(o && o.body)});
  const k = m + ' ' + String(url).split('?')[0];
  let st = 200, d;
  if (window.__javob[k]) { st = window.__javob[k][0]; d = window.__javob[k][1]; }
  else if (k === 'GET /api/platform/companies') d = window.__royxat;
  else if (k === 'GET /api/platform/summary') d = ${jsonS(SUMMARY)};
  else if (k === 'GET /api/platform/errors') d = ${jsonS(XATOLAR)};
  else if (/\\/extend$/.test(k)) d = (__fd(o && o.body).korish === '1')
      ? {status: 'korish', obuna_tugash: (__fd(o && o.body).sana || '2026-11-30')}
      : {status: 'ok', obuna_tugash: '2026-11-30', ochildi: false, holat: {bloklangan: false}};
  else if (/\\/unblock$/.test(k)) d = {status: 'ok', imtiyoz_gacha: '2026-10-13'};
  else if (/\\/block$/.test(k)) d = {status: 'ok'};
  else if (/reset-admin-password$/.test(k)) d = {status: 'ok', username: 'alfa_<admin>', password: 'Ab<3>cd'};
  else if (k === 'POST /api/platform/companies') d = {status: 'ok', company: {id: 9, name: 'Yangi <b>', code: 'YANGI',
      obuna_tugash: '2026-11-09', obuna_turi: 'sinov'}, admin: {username: 'yangi_admin', password: 'Pp12<'}};
  else if (k === 'POST /api/platform/contact-phone') d = {status: 'ok', aloqa_telefoni: __fd(o && o.body).telefon};
  else d = {};
  return Promise.resolve({ok: st >= 200 && st < 300, status: st, json: () => Promise.resolve(d)});
};
</script>
<script>${YORDAM}</script>
<script>${SKRIPT}</script></body></html>`;
  const dom = new JSDOM(html, {runScripts: 'dangerously', virtualConsole: vc, url: 'https://sinov.test/platforma'});
  return {w: dom.window, xatolar};
}
const kut = (ms) => new Promise(r => setTimeout(r, ms || 30));
function karta(w, id) { return w.document.querySelector(`#plKartalar [data-korxona="${id}"]`); }
function tugma(el, matn) { return el ? [...el.querySelectorAll('button')].find(b => b.textContent.trim() === matn) || null : null; }
function matnlar(w, sel) { return [...w.document.querySelectorAll(sel)].map(e => e.textContent.trim()); }

(async function () {
  if (!JSDOM) { tekshir('jsdom o\'rnatilgan (NODE_PATH)', false); return yakun(); }
  tekshir('S0 platforma.html bor, markup va skript o\'qildi', SRC && MARKUP.includes('plKartalar') && SKRIPT.length > 1000,
    [SRC.length, SKRIPT.length]);

  bolim('K. Kartochkalar va raqamlar');
  let {w, xatolar} = muhit();
  await kut(80);
  const kartalar = [...w.document.querySelectorAll('#plKartalar .pl-card')];
  tekshir('K1 4 ta mijoz kartochkasi (platforma egasi korxonasi yo\'q)', kartalar.length === 4 && !karta(w, 1),
    kartalar.map(k => k.dataset.korxona));
  tekshir('K2 egasi korxonasi izohda nomi bilan', w.document.getElementById('plEgaIzoh').textContent.includes('PenodecorPro'));
  tekshir('K3 raqamlar: mijoz 4, bugun kirishlar 7, bugun xatolar 2', () => {
    const t = w.document.getElementById('plRaqamlar').textContent;
    return t.includes('Mijoz korxonalar4') && t.includes('Bugun kirishlar7') && t.includes('Bugun xatolar2');
  }, w.document.getElementById('plRaqamlar').textContent);
  const a = karta(w, 2), b = karta(w, 3), g = karta(w, 4), d = karta(w, 5);
  tekshir('K4 Alfa: «Faol», «Obuna 30.10.2026 gacha», «20 kun qoldi», chiziq 50 % (20 / 40 kunlik davr)', () =>
    a.textContent.includes('Faol') && a.textContent.includes('Obuna 30.10.2026 gacha') && a.textContent.includes('20 kun qoldi')
    && a.querySelector('.pl-bar > div').style.width === '50%', a && a.textContent);
  tekshir('K4b yaratilgan sana — Toshkent kuni (UTC 2026-08-13T20:30 → «14.08.2026 dan»)', () =>
    a.textContent.includes('14.08.2026 dan') && !a.textContent.includes('2026-08-13'), a && a.querySelector('.pl-kod').textContent);
  tekshir('K5 Beta: «Muddati yaqin» + «Sinov», «Sinov davri 13.10.2026 gacha», sariq ramka, «Muddatni uzaytirish» qora',
    () => b.classList.contains('yaqin') && b.textContent.includes('Sinov davri 13.10.2026 gacha') && b.textContent.includes('Sinov')
      && tugma(b, 'Muddatni uzaytirish').classList.contains('qora'), b && b.textContent);
  tekshir('K6 Gamma: «Muddati o\'tdi», «Tugadi — 3 kundan keyin yopiladi», «Hali kirmagan»', () =>
    g.textContent.includes("Muddati o'tdi") && g.textContent.includes('Tugadi — 3 kundan keyin yopiladi')
    && g.textContent.includes('Hali kirmagan'), g && g.textContent);
  tekshir('K7 bloklangan: sabab, izoh, «Buyurtma (jami) 31», tugmalar Ochish / Uzaytirib ochish / Parolni tiklash', () =>
    d.classList.contains('bloklangan') && d.textContent.includes("Obuna muddati o'tdi (avtomatik)") && d.textContent.includes('31')
    && d.textContent.includes('Buyurtma (jami)') && tugma(d, 'Ochish') && tugma(d, 'Uzaytirib ochish') && tugma(d, 'Parolni tiklash')
    && !tugma(d, 'Bloklash'), d && d.textContent);
  tekshir('K8 oxirgi kirish bugun — «Bugun, HH:MM»', () => /Bugun, \d\d:\d\d/.test(a.textContent), a && a.textContent);
  tekshir('K9 aloqa telefoni maydoni serverdan to\'ldirildi', w.document.getElementById('plTelefon').value === '+998 90 555 44 33');
  tekshir('K10 sahifa xatosiz (jsdomError yo\'q)', xatolar.length === 0, xatolar);

  bolim('F. Saralash va qidiruv');
  tekshir('F1 chiplar: Hammasi · 4, Faol · 1, Muddati yaqin · 2, Bloklangan · 1, Sinov davri · 1',
    JSON.stringify(matnlar(w, '#plChiplar .pl-chip')) === JSON.stringify(['Hammasi · 4', 'Faol · 1', 'Muddati yaqin · 2',
      'Bloklangan · 1', 'Sinov davri · 1']), matnlar(w, '#plChiplar .pl-chip'));
  w.document.querySelector('[data-filtr="bloklangan"]').click();
  tekshir('F2 «Bloklangan» — faqat 5, chip aktiv (aria-pressed)', () => {
    const k = [...w.document.querySelectorAll('#plKartalar .pl-card')].map(x => x.dataset.korxona);
    return JSON.stringify(k) === '["5"]' && w.document.querySelector('[data-filtr="bloklangan"]').getAttribute('aria-pressed') === 'true';
  });
  w.document.querySelector('[data-filtr="yaqin"]').click();
  tekshir('F3 «Muddati yaqin» — Beta va Gamma (yaqin + imtiyoz)', JSON.stringify([...w.document.querySelectorAll('#plKartalar .pl-card')]
    .map(x => x.dataset.korxona)) === '["3","4"]');
  w.document.querySelector('[data-filtr="sinov"]').click();
  tekshir('F4 «Sinov davri» — faqat Beta', JSON.stringify([...w.document.querySelectorAll('#plKartalar .pl-card')]
    .map(x => x.dataset.korxona)) === '["3"]');
  w.document.querySelector('[data-filtr="hammasi"]').click();
  const q = w.document.getElementById('plQidiruv');
  q.value = 'gam'; q.dispatchEvent(new w.Event('input', {bubbles: true}));
  tekshir('F5 qidiruv «gam» — Gamma', JSON.stringify([...w.document.querySelectorAll('#plKartalar .pl-card')]
    .map(x => x.dataset.korxona)) === '["4"]');
  q.value = 'alfa'; q.dispatchEvent(new w.Event('input', {bubbles: true}));
  tekshir('F6 qidiruv kod bo\'yicha ham («alfa» → ALFA)', JSON.stringify([...w.document.querySelectorAll('#plKartalar .pl-card')]
    .map(x => x.dataset.korxona)) === '["2"]');
  q.value = 'yoq-korxona'; q.dispatchEvent(new w.Event('input', {bubbles: true}));
  tekshir('F7 mos korxona yo\'q — izoh', w.document.getElementById('plKartalar').textContent.includes("Tanlovga mos korxona yo'q"));
  q.value = ''; q.dispatchEvent(new w.Event('input', {bubbles: true}));

  bolim('B. Bloklash oynasi');
  tugma(karta(w, 2), 'Bloklash').click();
  const m = w.document.getElementById('plModal');
  tekshir('B1 oyna ochildi: sarlavha, 3 band, sabablar serverdan', () => m.classList.contains('ochiq')
    && w.document.getElementById('plModalSarlavha').textContent === 'Alfa Dekor korxonasini bloklash'
    && JSON.stringify([...w.document.querySelectorAll('#blSabab option')].map(o => o.textContent)) === JSON.stringify(SUMMARY.sabablar)
    && w.document.getElementById('plOyna').textContent.includes("ma'lumotlar o'chmaydi"));
  w.document.getElementById('blSabab').value = "Mijoz o'zi so'radi";
  w.document.getElementById('blIzoh').value = ' Iyul <b>to\'lovi</b> ';
  let n0 = w.__sorov.length;
  w.document.querySelector('#plOyna [data-modal="blokla"]').click();
  await kut(60);
  const bs = w.__sorov.slice(n0).find(x => x.method === 'POST');
  tekshir('B2 POST /api/platform/companies/2/block — sabab va izoh (bo\'shliqsiz)', bs && bs.url === '/api/platform/companies/2/block'
    && bs.body.sabab === "Mijoz o'zi so'radi" && bs.body.izoh === "Iyul <b>to'lovi</b>", bs);
  tekshir('B3 muvaffaqiyat: oyna yopildi, xabar, ro\'yxat qayta yuklandi', () => !m.classList.contains('ochiq')
    && w.__msg.some(x => x[0] === 'Korxona bloklandi') && w.__sorov.slice(n0).some(x => x.url === '/api/platform/companies'));
  ({w} = muhit({javob: {'POST /api/platform/companies/2/block': [400, {detail: 'Korxona allaqachon bloklangan'}]}}));
  await kut(80);
  tugma(karta(w, 2), 'Bloklash').click();
  w.document.querySelector('#plOyna [data-modal="blokla"]').click();
  await kut(60);
  tekshir('B4 server rad etsa (400) — sabab oynada, oyna OCHIQ qoladi', w.document.getElementById('plModal').classList.contains('ochiq')
    && w.document.getElementById('blXato').textContent === 'Korxona allaqachon bloklangan');
  w.document.querySelector('#plOyna [data-modal="yop"]').click();
  tekshir('B5 «Bekor» — oyna yopiladi, so\'rov yo\'q', !w.document.getElementById('plModal').classList.contains('ochiq'));

  bolim('U. Uzaytirish oynasi (yangi sana — SERVERDAN)');
  ({w} = muhit());
  await kut(80);
  n0 = w.__sorov.length;
  tugma(karta(w, 3), 'Muddatni uzaytirish').click();
  await kut(60);
  let ks = w.__sorov.slice(n0).filter(x => x.method === 'POST');
  tekshir('U1 ochilishda oldindan ko\'rish: POST …/3/extend korish=1, oy=1', ks.length === 1 && ks[0].url === '/api/platform/companies/3/extend'
    && ks[0].body.korish === '1' && ks[0].body.oy === '1', ks);
  tekshir('U2 «Yangi muddat: 30.11.2026 gacha» va «Hozir: Sinov davri 13.10.2026 gacha»', () =>
    w.document.getElementById('uzKorish').textContent === 'Yangi muddat: 30.11.2026 gacha'
    && w.document.getElementById('plOyna').textContent.includes('Hozir: Sinov davri 13.10.2026 gacha'));
  tekshir('U3 variantlar serverdan: +1 / +3 / +6 / +12 oy va «Aniq sana»', JSON.stringify([...w.document.querySelectorAll('input[name="uzOy"]')]
    .map(x => x.value)) === '["1","3","6","12","sana"]');
  const sanaR = w.document.querySelector('input[name="uzOy"][value="sana"]');
  sanaR.checked = true; sanaR.dispatchEvent(new w.Event('change', {bubbles: true}));
  const si = w.document.getElementById('uzSana'); si.value = '2027-01-31';
  si.dispatchEvent(new w.Event('change', {bubbles: true}));
  await kut(60);
  ks = w.__sorov.slice(n0).filter(x => x.method === 'POST');
  tekshir('U4 «Aniq sana» — maydon ko\'rinadi, oldindan ko\'rish sana bilan (oy YO\'Q)', () =>
    w.document.getElementById('uzSanaJoy').style.display === '' && ks[ks.length - 1].body.sana === '2027-01-31'
    && !('oy' in ks[ks.length - 1].body) && w.document.getElementById('uzKorish').textContent === 'Yangi muddat: 31.01.2027 gacha', ks);
  n0 = w.__sorov.length;
  w.document.querySelector('#plOyna [data-modal="uzaytir"]').click();
  await kut(60);
  ks = w.__sorov.slice(n0).filter(x => x.method === 'POST');
  tekshir('U5 «Uzaytirish» — POST extend sana bilan, korish YO\'Q; unblock chaqirilmaydi; oyna yopildi', ks.length === 1
    && ks[0].body.sana === '2027-01-31' && !('korish' in ks[0].body) && !w.document.getElementById('plModal').classList.contains('ochiq')
    && w.__msg.some(x => x[0] === 'Obuna 30.11.2026 gacha uzaytirildi'), ks);
  // Uzaytirib ochish: server avtomatik blokni o'zi ochadi (holat.bloklangan=false) — unblock SO'RALMAYDI
  n0 = w.__sorov.length;
  tugma(karta(w, 5), 'Uzaytirib ochish').click();
  await kut(60);
  w.document.querySelector('#plOyna [data-modal="uzaytir"]').click();
  await kut(80);
  ks = w.__sorov.slice(n0).filter(x => x.method === 'POST' && !x.body.korish);
  tekshir('U6 «Uzaytirib ochish» (avtomatik blok — server ochdi) — faqat extend', ks.length === 1 && /\/5\/extend$/.test(ks[0].url), ks);
  // qo'lda blok: extend javobida hali bloklangan → unblock ham
  ({w} = muhit({javob: {'POST /api/platform/companies/5/extend': [200, {status: 'ok', obuna_tugash: '2026-12-01', ochildi: false,
    holat: {bloklangan: true}}]}}));
  await kut(80);
  n0 = w.__sorov.length;
  tugma(karta(w, 5), 'Uzaytirib ochish').click();
  await kut(60);
  w.document.querySelector('#plOyna [data-modal="uzaytir"]').click();
  await kut(80);
  ks = w.__sorov.slice(n0).filter(x => x.method === 'POST' && !x.body.korish);
  tekshir('U7 qo\'lda bloklangan — extend, KEYIN unblock', ks.length === 2 && /\/extend$/.test(ks[0].url) && /\/5\/unblock$/.test(ks[1].url), ks);
  ({w} = muhit({javob: {'POST /api/platform/companies/2/extend': [400, {detail: 'Sana bugundan oldin bo\'lmasin'}]}}));
  await kut(80);
  tugma(karta(w, 2), 'Muddatni uzaytirish').click();
  await kut(60);
  tekshir('U8 oldindan ko\'rish rad etilsa — sabab ko\'rinadi', w.document.getElementById('uzKorish').textContent === "Sana bugundan oldin bo'lmasin");

  bolim('O. Ochish, parol, yangi korxona, aloqa telefoni');
  ({w} = muhit());
  await kut(80);
  n0 = w.__sorov.length;
  tugma(karta(w, 5), 'Ochish').click();
  await kut(60);
  ks = w.__sorov.slice(n0).filter(x => x.method === 'POST');
  tekshir('O1 «Ochish» — tasdiq (avtomatik — imtiyoz eslatmasi), POST unblock, xabar imtiyoz sanasi bilan', () =>
    w.__tasdiq.length === 1 && w.__tasdiq[0][1].includes('3 kunlik imtiyoz') && ks.length === 1 && /\/5\/unblock$/.test(ks[0].url)
    && w.__msg.some(x => x[0] === 'Ochildi — imtiyoz 13.10.2026 gacha'), [w.__tasdiq, ks, w.__msg]);
  tugma(karta(w, 2), 'Parolni tiklash').click();
  await kut(60);
  tekshir('O2 parol tiklash — natija qutisi (login / parol matn sifatida)', () => {
    const t = w.document.getElementById('plNatija');
    return t.textContent.includes('alfa_<admin>') && t.textContent.includes('Ab<3>cd') && !t.querySelector('admin');
  }, w.document.getElementById('plNatija').innerHTML);
  w.document.getElementById('plYangiBtn').click();
  tekshir('O3 «+ Yangi korxona» formani ochadi; sinov davri matni serverdan', w.document.getElementById('plYangi').style.display === ''
    && w.document.getElementById('plSinovMatn').textContent === '30 kunlik sinov davri');
  w.document.getElementById('ncNom').value = 'Yangi <b>';
  w.document.getElementById('ncLogin').value = 'yangi_admin';
  n0 = w.__sorov.length;
  w.document.getElementById('ncYarat').click();
  await kut(60);
  ks = w.__sorov.slice(n0).filter(x => x.method === 'POST');
  tekshir('O4 yaratish — POST name / admin_username, natijada sinov muddati, forma tozalandi va yopildi', () =>
    ks[0].body.name === 'Yangi <b>' && ks[0].body.admin_username === 'yangi_admin'
    && w.document.getElementById('plNatija').textContent.includes('Sinov davri: 09.11.2026 gacha')
    && w.document.getElementById('ncNom').value === '' && w.document.getElementById('plYangi').style.display === 'none', ks);
  w.document.getElementById('plTelefon').value = ' +998 91 000 00 00 ';
  w.document.getElementById('plTelefonSaqla').click();
  await kut(60);
  ks = w.__sorov.filter(x => x.url === '/api/platform/contact-phone');
  tekshir('O5 aloqa telefoni — POST (bo\'shliqsiz), «✓ Saqlandi»', ks.length === 1 && ks[0].body.telefon === '+998 91 000 00 00'
    && w.document.getElementById('plTelefonNatija').textContent === '✓ Saqlandi', ks);

  bolim('X. Xatolar ro\'yxati');
  tekshir('X1 xatolar chizildi (korxona, manzil, kim) — matn sifatida', () => {
    const r = w.document.querySelector('#xtRoyxat .pl-xato');
    return r && r.textContent.includes('<script>window.__xss2=1</script>xato') && r.textContent.includes('/api/<x>')
      && r.textContent.includes('<i>kim</i>');
  });
  const xr = w.document.querySelector('#xtRoyxat .pl-xato');
  xr.click();
  tekshir('X2 bosilganda traceback ochiladi', xr.classList.contains('ochiq'));
  const sel = w.document.getElementById('xtKorxona');
  sel.value = '5'; n0 = w.__sorov.length;
  sel.dispatchEvent(new w.Event('change', {bubbles: true}));
  await kut(60);
  tekshir('X3 korxona tanlansa — GET /api/platform/errors?korxona=5', w.__sorov.slice(n0).some(x => x.url === '/api/platform/errors?korxona=5'),
    w.__sorov.slice(n0));
  tekshir('X4 korxona ro\'yxati tanlovda (Hammasi, Platforma + 5 korxona)', sel.options.length === 7, sel.options.length);

  bolim('H. HTML in\'ektsiya — mijoz kiritgan matn (nom, kod, izoh, xato) HTML bo\'lib chizilmaydi');
  tekshir('H1 korxona nomi — <img> elementi YARATILMADI, skript ishlamadi', !w.document.querySelector('#plKartalar img')
    && !w.__xss && !w.__xss2 && karta(w, 5).textContent.includes(YOMON));
  tekshir('H2 kod va izoh — matn sifatida', karta(w, 5).textContent.includes('DE"LTA<') && karta(w, 5).textContent.includes('Izoh: <b>izoh</b>&')
    && !karta(w, 5).querySelector('.pl-blok b + b'));
  tekshir('H3 tanlovdagi korxona nomi — matn', [...w.document.getElementById('xtKorxona').options].some(o => o.textContent === YOMON));
  tugma(karta(w, 5), 'Uzaytirib ochish').click();
  await kut(60);
  tekshir('H4 oyna sarlavhasidagi nom — matn (img yo\'q)', !w.document.querySelector('#plOyna img')
    && w.document.getElementById('plModalSarlavha').textContent.startsWith(YOMON));

  bolim('S. Statik');
  tekshir('S1 inline onclick YO\'Q (data-* + delegatsiya)', !SRC.includes('onclick='));
  tekshir('S2 `new Date(` / toISOString / getMonth YO\'Q (Toshkent yordamchilari; sana formulasi serverda)',
    !SKRIPT.includes('new Date(') && !SKRIPT.includes('toISOString') && !SKRIPT.includes('getMonth') && !SKRIPT.includes('setMonth'));
  tekshir('S3 innerHTML ga qo\'yiladigan qatorlarda foydalanuvchi maydonlari escapeHtml orqali', () =>
    ['r.name', 'r.code', 'r.blok_izoh', 'h.sabab', 'x.xabar', 'x.endpoint', 'x.kim', 'x.trace', 'x.korxona']
      .every(f => SKRIPT.includes('escapeHtml(' + f)));
  return yakun();
})().catch(e => { tekshir('istisnosiz yakunlandi', false, String(e && e.stack || e)); yakun(); });

function yakun() {
  console.log(`\nNATIJA: o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach(f => console.log('  - ' + f)); }
  process.exitCode = FAIL ? 1 : 0;
}
