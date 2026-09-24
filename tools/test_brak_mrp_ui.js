#!/usr/bin/env node
/**
 * test_brak_mrp_ui.js — 13-band 5-qadam (kech54, 2026-09-24): "Ishlab chiqarishda chiqdi"
 * MRP tayyor mahsuloti (`category = 'dynamic_bom'`) uchun ham ochiladi.
 *
 * NIMA UCHUN: server endi MRP mahsulotining ishlab chiqarish brakini retsept SURATIDAN yozadi
 * (`crud.record_finished_product_production_brak`, `tools/test_brak_mrp_loy.py` D bo'limi), lekin
 * `finished.html` dagi `PROD_BRAK_CATEGORIES` ro'yxatida `dynamic_bom` yo'q edi — tugma umuman
 * ko'rinmasdi (O'LCHANGAN: asl shablon). Qaytgan MRP mahsuloti (`mrp_product`) — surati yo'q,
 * tugma ko'rinmaydi (server baribir 400 beradi). Eski turkumlar — AYNAN avvalgidek.
 *
 * ISHLATISH: node tools/test_brak_mrp_ui.js [boshqa/finished.html]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
function oqi(p) { try { return fs.readFileSync(p, 'utf8'); } catch (e) { return ''; } }
const FINISHED = oqi(process.argv[2] || path.join(ROOT, 'templates', 'finished.html'));

let OK = 0, FAIL = 0;
const FAILED = [];
function tekshir(label, shart, izoh) {
  if (shart) { OK++; console.log(`  ✓ ${label}`); }
  else { FAIL++; FAILED.push(label); console.log(`  ✗ ${label}${izoh ? '   — ' + izoh : ''}`); }
}
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
function element(v) {
  return { value: v, textContent: '', style: { display: 'none' }, max: '', classList: { toggle: () => {} } };
}

const m = /const PROD_BRAK_CATEGORIES = (\[[^\]]*\]);/.exec(FINISHED);
let royxat = null;
try { royxat = m ? vm.runInNewContext(m[1]) : null; } catch (e) { royxat = null; }
tekshir("U1 PROD_BRAK_CATEGORIES ichida 'dynamic_bom' (MRP tayyor mahsuloti)",
        Array.isArray(royxat) && royxat.includes('dynamic_bom'), JSON.stringify(royxat));
tekshir("U2 eski turkumlar AYNAN qoldi (profil, panel, dona, blok)",
        Array.isArray(royxat) && ['profil', 'panel', 'dona', 'blok'].every((x) => royxat.includes(x)), JSON.stringify(royxat));
tekshir("U3 qaytgan MRP mahsuloti ('mrp_product') — ro'yxatda YO'Q (surati yo'q)",
        Array.isArray(royxat) && !royxat.includes('mrp_product'), JSON.stringify(royxat));

const kod = olib(FINISHED, 'openLossModal');
function och(kat) {
  const el = { 'loss-modal-sub': element(''), 'loss-stock-info': element(''), 'loss-qty': element(''),
               'loss-reason': element(''), 'loss-mode-toggle': element(''), lossModal: element(''),
               'loss-stage': element('') };
  const ctx = { document: { getElementById: (id) => el[id] || null }, setLossMode: () => {},
                PROD_BRAK_CATEGORIES: royxat || [], _lossData: null };
  vm.createContext(ctx);
  try {
    vm.runInContext(kod, ctx);
    vm.runInContext(`openLossModal(7, 'X', 10, 'm²', ${JSON.stringify(kat)})`, ctx);
    return el['loss-mode-toggle'].style.display;
  } catch (e) { return 'XATO ' + e.message; }
}
tekshir("U4 openLossModal('dynamic_bom') — \"Ishlab chiqarishda chiqdi\" tugmasi ko'rinadi", kod && och('dynamic_bom') === 'flex', kod ? och('dynamic_bom') : 'topilmadi');
tekshir("U5 openLossModal('DYNAMIC_BOM') — katta harf ham (toLowerCase, avvalgidek)", kod && och('DYNAMIC_BOM') === 'flex');
tekshir("U6 openLossModal('mrp_product') — ko'rinmaydi", kod && och('mrp_product') === 'none');
tekshir("U7 openLossModal('profil') — ko'rinadi (avvalgidek)", kod && och('profil') === 'flex');
tekshir("U8 openLossModal('gips') — ko'rinmaydi (avvalgidek)", kod && och('gips') === 'none');

console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach((f) => console.log('  - ' + f)); }
process.exit(FAIL ? 1 : 0);
