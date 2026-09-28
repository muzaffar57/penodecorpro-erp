#!/usr/bin/env node
/**
 * test_loyiha_tahrir_ui.js — kech107 darvozasi (10-band "1a"): LOYIHA TAHRIR OYNASI (`templates/projects.html`) —
 * "Muddati" maydoni (`e-deadline`) va tozalangan maydonlar. Server qismi — `tools/test_loyiha_tahrir.py`.
 *
 * NIMA UCHUN (asl kod staging `061e082` da O'LCHANGAN — `work/probe107a.py`): tahrir oynasida muddat maydoni YO'Q edi
 * (server ham `deadline` ni 400 bilan rad etardi) — loyiha muddatini o'zgartirishning yo'li yo'q edi.
 * Funksiyalar HTML dan JONLI o'qiladi (openEditModal, saveEditProject, loyihaIzohYasa, loyihaIzohAjrat + base.html tk*),
 * soxta DOM da ishga tushiriladi; topilmagan funksiya — yiqilgan tekshiruv (asl faylga qarshi ham QULAMAYDI).
 *
 *     node tools/test_loyiha_tahrir_ui.js [templates_papkasi]
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.dirname(__dirname);
const TPL = process.argv[2] || path.join(ROOT, 'templates');
function oqi(nom) { try { return fs.readFileSync(path.join(TPL, nom), 'utf8'); } catch (e) { return ''; } }
const BASE = oqi('base.html'), PRJ = oqi('projects.html');

let OK = 0, FAIL = 0;
const FAILED = [];
function tekshir(label, shart, izoh) {
  let s = false;
  try { s = !!shart; } catch (e) { s = false; }
  if (s) { OK++; console.log(`  ✓ ${label}`); }
  else { FAIL++; FAILED.push(label); console.log(`  ✗ ${label}${izoh !== undefined ? '   — ' + qisqa(izoh) : ''}`); }
}
function bolim(t) { console.log(`\n--- ${t} ---`); }
function qisqa(x) {
  let s; try { s = typeof x === 'string' ? x : JSON.stringify(x); } catch (e) { s = String(x); }
  s = String(s); return s.length > 400 ? s.slice(0, 400) + '…' : s;
}
function olib(src, nom) {
  const re = new RegExp('(async\\s+)?function\\s+' + nom + '\\s*\\(');
  const m = re.exec(src);
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
function el(extra) { return Object.assign({ value: '', textContent: '', style: {}, dataset: {}, disabled: false }, extra || {}); }
const TK = ['tkMs', 'tkDate', 'tkISO'];
const FN = ['loyihaIzohYasa', 'loyihaIzohAjrat', 'openEditModal', 'saveEditProject'];

function muhit(karta) {
  const elementlar = {};
  const sorovlar = [], xabarlar = [];
  const ctx = {
    console, JSON, String, Number, Math, Promise, Date, RegExp, parseFloat, parseInt, isNaN, Object, Array,
    document: {
      getElementById: (id) => { if (!elementlar[id]) elementlar[id] = el(); return elementlar[id]; },
      querySelector: (s) => (s.includes('proj-card') ? karta : null),
    },
    location: { reload() {} },
    fetch: async (url, opts) => { sorovlar.push({url: String(url), method: (opts && opts.method) || 'GET',
                                                 tana: opts && opts.body ? JSON.parse(opts.body) : null});
                                   return { ok: true, status: 200, json: async () => ({}) }; },
    projToast: (t) => xabarlar.push(String(t)),
    selectedProjId: 7,
  };
  vm.createContext(ctx);
  return { ctx, elementlar, sorovlar, xabarlar };
}
function kodlar() {
  const q = [], yoq = [];
  for (const n of TK) { const f = olib(BASE, n); if (f) q.push(f); else yoq.push('base:' + n); }
  for (const n of FN) { const f = olib(PRJ, n); if (f) q.push(f); else yoq.push(n); }
  q.push("var LOYIHA_TG_ID_RE = /^-?\\d+$/; var isSavingEditProject = false;");
  return { kod: q.join('\n'), yoq };
}
const KARTA = (xom) => ({ dataset: { client: 'Karimov', phone: '+998901234567', name: 'Hovli', address: 'Andijon', budget: '5000000',
                                    status: 'ACTIVE', notes: 'tg_id=123, eshik', deadlineRaw: xom } });

(async () => {
  const k = kodlar();
  bolim('L — tahrir oynasi: muddat');
  tekshir('L0 funksiyalar topildi (openEditModal, saveEditProject, loyihaIzoh*, base tk*)', !k.yoq.length, k.yoq);
  for (const [nom, xom, kutilgan] of [
    ["L1 muddat bor (UTC 00:00) — maydonda o'sha sana", '2026-10-20T00:00:00', '2026-10-20'],
    ["L2 Toshkent tuni (UTC 20:30 = Toshkent ertasi 01:30) — Toshkent sanasi", '2026-10-19T20:30:00', '2026-10-20'],
    ["L3 muddat yo'q — maydon bo'sh", '', ''],
  ]) {
    const m = muhit(KARTA(xom));
    let xato = null;
    try { vm.runInContext(k.kod, m.ctx); vm.runInContext('openEditModal()', m.ctx); } catch (e) { xato = String(e.message || e); }
    tekshir(nom, !xato && m.elementlar['e-deadline'] && m.elementlar['e-deadline'].value === kutilgan,
            {xato, qiymat: m.elementlar['e-deadline'] && m.elementlar['e-deadline'].value});
  }
  bolim('S — saqlash tanasi (saveEditProject)');
  for (const [nom, qiymat, kutilgan] of [
    ["S1 yangi muddat — tanada `deadline: \"2026-11-01\"`", '2026-11-01', '2026-11-01'],
    ["S2 maydon tozalangan — tanada `deadline: null` (server olib tashlaydi)", '', null],
  ]) {
    const m = muhit(KARTA('2026-10-20T00:00:00'));
    let xato = null;
    try {
      vm.runInContext(k.kod, m.ctx);
      vm.runInContext('openEditModal()', m.ctx);
      m.elementlar['e-deadline'].value = qiymat;
      m.elementlar['e-phone'].value = '';
      await vm.runInContext('saveEditProject()', m.ctx);
    } catch (e) { xato = String(e.message || e); }
    const t = (m.sorovlar[0] || {}).tana || {};
    tekshir(nom, !xato && m.sorovlar.length === 1 && m.sorovlar[0].method === 'PUT' && m.sorovlar[0].url === '/api/projects/7'
            && Object.prototype.hasOwnProperty.call(t, 'deadline') && t.deadline === kutilgan && t.client_phone === null,
            {xato, sorov: m.sorovlar});
  }
  bolim('X — statik');
  const i = PRJ.indexOf('id="editModal"');
  const modal = i >= 0 ? PRJ.slice(i, PRJ.indexOf('</div>\n</div>', i)) : '';
  tekshir('X1 tahrir oynasida `<input type="date" id="e-deadline">` ("Muddati")', /Muddati<\/label><input type="date" id="e-deadline">/.test(modal), '');
  tekshir('X2 yaratish oynasidagi `f-deadline` o\'z joyida', PRJ.includes('<input type="date" id="f-deadline">'), '');

  console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL}   jami = ${OK + FAIL}`);
  if (FAILED.length) { console.log('YIQILGANLAR:'); FAILED.forEach(f => console.log('   - ' + f)); }
  process.exit(FAIL ? 1 : 0);
})().catch(e => { console.log('ICHKI XATO: ' + e); console.log(`\nNATIJA:  o'tdi = ${OK}   yiqildi = ${FAIL + 1}   jami = ${OK + FAIL + 1}`); process.exit(1); });
