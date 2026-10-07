#!/usr/bin/env node
/**
 * test_tahrir_banner_ui.js — kech108, K108-3: topshirila boshlagan buyurtmani tahrirlash oynasi (templates/orders.html).
 *
 * NIMA UCHUN KERAK (O'LCHANGAN — `main` zaxirasining haqiqiy ma'lumoti, lokal nusxa, HAQIQIY brauzer):
 *   `editSelected` topshirish boshlangan buyurtmada tahrir bannerini `editBanner.innerHTML = …` bilan qayta yozardi —
 *   ichidagi `<span id="editOrderNum">` o'chardi, keyingi qator `document.getElementById('editOrderNum').textContent = …`
 *   TypeError berardi. Foydalanuvchi: "Server xatosi: Cannot set properties of null (setting 'textContent')"; sarlavha
 *   "Yangi buyurtma", tugma "💾 Buyurtmani saqlash", "Vaqtincha saqlash" ko'rinib qolardi, `calcDiscount()` /
 *   `editInitialLoadDone = true` bajarilmasdi (chegirma foizi bo'yicha qayta hisob o'chardi). `showNewForm` banner mazmunini
 *   tiklamasdi — sahifa yangilanmasdan keyingi (oddiy) buyurtma tahriri ham buzilardi.
 *
 * BO'LIMLAR
 *   D — jsdom: shablondagi HAQIQIY banner markup va HAQIQIY `editSelected` qismlari (topshirish shoxi, sarlavha / raqam
 *       o'rnatish — matndan kesib olinadi) + `showNewForm` — ketma-ketlik: topshirilgan buyurtma → oddiy buyurtma.
 *   Y — yordamchilar: `_tahrirBanneriTopshirish` (foiz — faqat son, matn in'ektsiyasi yo'q), `_tahrirBanneriTikla`.
 *   S — statik: banner (container) `innerHTML` ga yozilmaydi; `showNewForm` tiklaydi; raqam / sarlavha null-xavfsiz.
 *
 * Funksiyalar / qismlar HTML dan JONLI o'qiladi; topilmasa yoki istisno bo'lsa — yiqilgan tekshiruv (asl faylga qarshi
 * QULAMAYDI). ISHLATISH: node tools/test_tahrir_banner_ui.js   (chiqish kodi 0 — hammasi o'tdi)
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__dirname);
let SRC = '';
try { SRC = fs.readFileSync(path.join(ROOT, 'templates', 'orders.html'), 'utf8'); } catch (e) { SRC = ''; }

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
  try { s = !!shart; } catch (e) { s = false; }
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
// Matndan kesish: `bosh` dan (u ham kiradi) `oxir` gacha (u kirmaydi); topilmasa null.
function kes(src, bosh, oxir, dan) {
  const i = src.indexOf(bosh, dan || 0);
  if (i < 0) return null;
  const j = src.indexOf(oxir, i + bosh.length);
  return j < 0 ? null : src.slice(i, j);
}
function jinjasiz(kod) {
  return kod === null ? null : kod.replace(/\{%[\s\S]*?%\}/g, '').replace(/\{\{[\s\S]*?\}\}/g, 'null');
}

let JSDOM = null, VirtualConsole = null;
try { ({ JSDOM, VirtualConsole } = require('jsdom')); } catch (e) { JSDOM = null; }

const EDIT = olib(SRC, 'editSelected') || '';
const SHOWNEW = olib(SRC, 'showNewForm');
const TOPSH = olib(SRC, '_tahrirBanneriTopshirish');
const TIKLA = olib(SRC, '_tahrirBanneriTikla');
// Shablondagi HAQIQIY banner markup: <div id="editBanner" … dan uning yopiluvchi </div> igacha (ichma-ich div sanab).
function bannerMarkup(src) {
  const i = src.indexOf('<div id="editBanner"');
  if (i < 0) return null;
  const re = /<div\b|<\/div>/g;
  re.lastIndex = i;
  let d = 0, m;
  while ((m = re.exec(src))) {
    if (m[0] === '</div>') { d--; if (d === 0) return src.slice(i, m.index + 6); }
    else d++;
  }
  return null;
}
const BANNER = bannerMarkup(SRC);
// editSelected ichidan: topshirish shoxi (`const dd = _dlvHolat103;` dan "// Kelishilgan summa" gacha) va
// sarlavha / raqam o'rnatish ("// Zaklat maydonini" dan `showMsg(\`✏️` gacha).
const QISM_DLV = kes(EDIT, 'const dd = _dlvHolat103;', '// Kelishilgan summa');
const QISM_SARLAVHA = kes(EDIT, '// Zaklat maydonini yashiramiz', 'showMsg(`✏️');

function muhit() {
  // showNewForm ishlatadigan elementlar + banner (HAQIQIY markup) + forma sarlavhasi / tugmalar.
  const html = `<!doctype html><body>
    <div id="newOrderForm" style="display:none">${BANNER || ''}
      <div class="card"><div class="card-head"><h3 id="formTitle">Yangi buyurtma</h3></div>
        <button class="btn btn-dark">💾 Buyurtmani saqlash</button>
        <button class="btn btn-outline">📝 Vaqtincha saqlash</button>
        <div id="zaklat-field-wrap"></div><div id="discount-auto-hint"></div>
        <input id="deadline_input"><input id="project_id_search"><div id="items"><div>1</div></div>
      </div></div>
    <div id="orderDetail"></div><div id="emptyMid"></div><div id="sumCard"></div>
  </body>`;
  const xatolar = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => { xatolar.push(String(e && e.message || e)); });
  const dom = new JSDOM(html, { runScripts: 'dangerously', virtualConsole: vc });
  const w = dom.window;
  const kod = [
    'var editMode = false, currentEditOrderId = null, editDiscountPct = 0, editUserTouched = false, editInitialLoadDone = false;',
    'var selectedOrderId = null; function filterProjectSelect(){} function addItem(){} function saveOrder(){} function updateOrder(){}',
    TOPSH || '', TIKLA || '', jinjasiz(SHOWNEW) || '',
    // editSelected qismlari — asl joyidagidek, bitta funksiya ichida (o'zgaruvchilar: _dlvHolat103, order)
    'function __tahrirQismi(_dlvHolat103, order) {', QISM_DLV || 'throw new Error("QISM_DLV topilmadi");',
    QISM_SARLAVHA || 'throw new Error("QISM_SARLAVHA topilmadi");', '}',
  ].join('\n');
  const s = w.document.createElement('script');
  s.textContent = kod;
  w.document.body.appendChild(s);
  return { w, xatolar };
}
function tahrir(m, dd, raqam, dlvMap) {
  // editSelected tartibi: showNewForm → (topshirish holati) → … → sarlavha / raqam
  const w = m.w;
  try {
    w.showNewForm();
    w._dlvMap = dlvMap || {};
    w.__tahrirQismi(dd, { order_number: raqam });
    return null;
  } catch (e) { return String(e && e.message || e); }
}
function holat(w) {
  const d = w.document;
  const eb = d.getElementById('editBanner');
  const t = d.getElementById('editBannerTopshirish');
  return {
    raqam: (d.getElementById('editOrderNum') || {}).textContent ?? null,
    raqam_bor: !!d.getElementById('editOrderNum'),
    sarlavha: (d.getElementById('formTitle') || {}).textContent,
    banner_korinadi: eb ? eb.style.display : null,
    fon: eb ? eb.style.background : null,
    topsh_korinadi: t ? t.style.display : null,
    topsh_matn: t ? t.textContent.replace(/\s+/g, ' ').trim() : null,
    banner_matn: eb ? eb.textContent.replace(/\s+/g, ' ').trim() : null,
  };
}

bolim('D — jsdom: HAQIQIY banner va editSelected qismlari');
tekshir('D0 jsdom mavjud, banner markup, showNewForm va editSelected qismlari shablonda topildi',
        !!JSDOM && !!BANNER && !!SHOWNEW && !!QISM_DLV && !!QISM_SARLAVHA,
        { jsdom: !!JSDOM, banner: !!BANNER, show: !!SHOWNEW, dlv: !!QISM_DLV, sarlavha: !!QISM_SARLAVHA });
if (JSDOM && BANNER && SHOWNEW) {
  const m = muhit();
  const x1 = tahrir(m, { delivery_percent: 85.7 }, 'ORD-051-1', { '45 li karniz': { delivered: 3 } });
  const h1 = holat(m.w);
  tekshir('D1 topshirila boshlagan buyurtma tahriri — istisno YO\'Q (asl: "Cannot set properties of null (setting \'textContent\')")',
          x1 === null, x1);
  tekshir('D2 banner raqami saqlanadi: editOrderNum = ORD-051-1, sarlavha «Buyurtmani tahrirlash»',
          h1.raqam_bor && h1.raqam === 'ORD-051-1' && h1.sarlavha === 'Buyurtmani tahrirlash', h1);
  tekshir('D3 topshirish ogohlantirishi ko\'rinadi (85.7 %) va banner sariq', /topshirila boshlagan \(85\.7%\)/.test(h1.banner_matn || '')
          && /rgb\(254, 243, 199\)|#FEF3C7|var\(--f-fef3c7\)/i.test(h1.fon || ''), h1);   // kech118 (zip 122, MOSLANDI): fon ro'yxatdan ham
  const x2 = tahrir(m, null, 'ORD-037-1', {});
  const h2 = holat(m.w);
  tekshir('D4 sahifa yangilanmasdan KEYINGI (topshirilmagan) buyurtma tahriri — istisno YO\'Q, raqam ORD-037-1', x2 === null
          && h2.raqam === 'ORD-037-1' && h2.sarlavha === 'Buyurtmani tahrirlash', { x2, h2 });
  tekshir('D5 keyingi tahrirda topshirish ogohlantirishi va sariq rang QOLMAGAN (showNewForm tikladi)',
          x2 === null && !/topshirila boshlagan/.test(h2.banner_matn || '') && !/254, 243, 199|FEF3C7/i.test(h2.fon || ''), h2);
  tekshir('D6 jsdom skript xatosi yo\'q (yordamchilar / qismlar kompilyatsiya bo\'ldi)', m.xatolar.length === 0, m.xatolar);
}

bolim('Y — yordamchilar');
if (JSDOM && BANNER) {
  const m = muhit();
  const w = m.w;
  let xato = null;
  try { w._tahrirBanneriTopshirish({ delivery_percent: '<img src=x onerror=alert(1)>' }); } catch (e) { xato = String(e.message || e); }
  const t = w.document.getElementById('editBannerTopshirish');
  tekshir('Y1 _tahrirBanneriTopshirish mavjud; foiz — faqat son (matn in\'ektsiyasi → 0 %, <img> YO\'Q)',
          !!TOPSH && xato === null && t && !t.querySelector('img') && /\(0%\)/.test(t.textContent), { xato, html: t ? t.innerHTML : null });
  try { w._tahrirBanneriTikla(); } catch (e) { xato = String(e.message || e); }
  tekshir('Y2 _tahrirBanneriTikla: ogohlantirish bo\'sh va yashirin, rang asl (#F8F2EB / #E8D5C0), editOrderNum joyida',
          !!TIKLA && xato === null && t && t.innerHTML === '' && t.style.display === 'none'
          && /248, 242, 235|F8F2EB/i.test(w.document.getElementById('editBanner').style.background)
          && !!w.document.getElementById('editOrderNum'), { xato });
  tekshir('Y3 banner markup: editOrderNum va editBannerTopshirish — editBanner ICHIDA',
          !!w.document.querySelector('#editBanner #editOrderNum') && !!w.document.querySelector('#editBanner #editBannerTopshirish'));
}

bolim('S — statik');
const QISMSIZ = EDIT.split('\n').filter((q) => !q.trim().startsWith('//')).join('\n');
tekshir('S1 editSelected bannerni (container) innerHTML bilan qayta yozmaydi (eb2.innerHTML / editBanner.innerHTML YO\'Q)',
        EDIT.length > 0 && !/eb2\.innerHTML|getElementById\('editBanner'\)\.innerHTML/.test(QISMSIZ));
tekshir('S2 editSelected: editOrderNum / formTitle null-xavfsiz (to\'g\'ridan `getElementById(\'editOrderNum\').textContent` YO\'Q)',
        EDIT.length > 0 && !/getElementById\('editOrderNum'\)\.textContent/.test(QISMSIZ)
        && !/getElementById\('formTitle'\)\.textContent\s*=\s*'Buyurtmani tahrirlash'/.test(QISMSIZ));
tekshir('S3 showNewForm _tahrirBanneriTikla() ni chaqiradi', !!SHOWNEW && /_tahrirBanneriTikla\(\)/.test(SHOWNEW));
tekshir('S4 editSelected topshirish shoxi _tahrirBanneriTopshirish(dd) orqali', /_tahrirBanneriTopshirish\(dd\)/.test(QISM_DLV || ''));

console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
if (FAIL) console.log('Yiqilganlar:\n  - ' + FAILED.join('\n  - '));
process.exit(FAIL ? 1 : 0);
