#!/usr/bin/env python3
"""
test_oynalar184.py — kech146 (zip 184): OYNALAR (modal) TELEFON KENGLIGIDA — 320 × 640, 375 × 667, 390 × 844, HAQIQIY Chromium
(Playwright, `is_mobile`, `has_touch`, `device_scale_factor=2`), HAQIQIY lokal server.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k183_tayyorgarlik/agentlar/oynalar/HISOBOT.md`: 68 oyna, 95 holat × 3 kenglik):
  P2-1 Buyurtmalar umumiy tasdiq oynasi («Narx kiritilmagan» 12 detal — 1292 px, buyurtmani o'chirish rejasi — 777 px) — tugmalar ekrandan
       tashqarida, hech narsa surilmasdi; P2-2 «Avans berish» — shu oydagi avanslar bilan o'sadi (320 px da 1 ta avansdan); P2-3 «Penoplast
       detal ishlab chiqarish» — «Bo'yi», «Eni», «1 m³ narxi» yozuv joyi 0 px; P2-4 xomashyo yetishmovchiligi (5 qator) — kesilgan;
       P2-5 «Panel kirishi» (320 px); P2-6 «Qisman topshirish» — nom 16 px, «−» tugmasi ostida; P2-7 «Foyda tahlili» — xarajat nomi 0 px,
       summa bilan ustma-ust; P2-8 retsept oynasi tanlagich ochilganda yonga surilgan; P2-9 `customConfirm` uzun savol — kesilgan.
  P3-1 … P3-10 — «Material qo'shish» oynadan chiqqan, «Sovg'a nomi» maydoni, savatcha narxi «25 00», «Hisob-kitob varaqasi» sarlavhasi,
       «Xaridlar tarixi» / «Ombor harakatlari» / ta'minotchi tarixi ustunlari, hodim avans oynalari, MRP tanlagichi nomlari, bosish
       nishonlari < 36 px.
O'lchov (har holat, har kenglik — `OLCH_JS`, agent o'lchovi bilan AYNAN): hujjat / oyna yon tomonga toshishi, ekrandan / qutidan chiqqan
element, kesilgan matn, o'z qutisidan toshgan matn va flex / grid qatori, tor maydon (yozuv joyi < 40 px yoki qiymat sig'magan), HAR
boshqaruvga suriladigan konteynerlarni surib yetib borish (< 0,6 ko'rinsa — yetib bo'lmaydi), qutining kesilgan qismi, bosish nishoni
< 36 px, maydon yozuvi < 16 px. Baho (`baho`) — P2 yoki P3 bo'lsa tekshiruv YIQILADI. Qo'shimcha: o'zgargan oynalarning odatiy (qisqa)
holatlari — regressiya. `baho` dan TASHQARI (`QUTI_JS`, oyna ochilgan zahoti, hech narsa surilmasdan): har holatda quti mazmuni PASTGA
toshmaydi (quti sig'adi yoki o'zi suriladi); savol oynalarida (`customConfirm`, Buyurtmalar umumiy tasdig'i) tugmalar TO'LIQ ko'rinadi —
ekranda va quti ichida («matn suriladi, tugmalar doim ko'rinadi»); «Foyda tahlili» qatorida raqam, belgi va nom BIR qatorda (nom
≥ 100 px), summa nom ustiga tushmaydi (`QATOR_JS`).
Ma'lumot — ilovaning O'Z API si orqali: `tools/test_c_telefon.py` ning ZANJIR_JS i (fayl BAJARILMAYDI — matni o'qiladi) + uzun nomli /
katta summali qo'shimcha (12 detalli 1,23 mlrd so'mlik buyurtma, katta kirim, avanslar …). Hodim oynalari (Dashboard) — soxta API javobi.
REJIM: SQLite (sahifa ko'rinishi baza turiga bog'liq emas — `PG_URL` e'tiborsiz); `TENANT_FILTER=1` ham.
Asl kodga (zip 183) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_oynalar184.py
"""
import os
import re
import io
import sys
import ast
import glob
import json
import time
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
_T = tempfile.mkdtemp(prefix="oyna184_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'oyna184.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402

REJIM = "[TF1] " if os.environ.get("TENANT_FILTER") == "1" else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


ADMIN, PAROL = "o184_admin", "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, ADMIN, PAROL, UserRole.ADMIN, "Andijon Fasad Dekor Bosh Administratori", company_id=1)
    s.commit()
s.close()


def _src_const(yol, nom):
    """tools/test_c_telefon.py dagi JS satrini (ZANJIR_JS) faylni BAJARMASDAN o'qiydi — o'sha ma'lumot zanjiri qayta ishlatiladi."""
    tree = ast.parse(open(os.path.join(ROOT, yol), encoding="utf-8").read())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == nom for t in n.targets):
            return ast.literal_eval(n.value)
    raise KeyError(nom)


ZANJIR_JS = _src_const("tools/test_c_telefon.py", "ZANJIR_JS")
CHART_ORINBOSAR = _src_const("tools/test_c_telefon.py", "CHART_ORINBOSAR")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Ma'lumot (qo'shimcha) va o'lchov — oynalar agenti o'lchovidan (`work/k183_tayyorgarlik/agentlar/oynalar/olchov_oyna.py`) AYNAN
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
M = "Andijon Fasad Dekor Elementlari"

UZUN = "Andijon Fasad Dekor — Karniz profili KR-120 (oq, tashqi ishlar uchun) — 2-qavat"

QOSHIMCHA_JS = r"""async (a) => {
  const I = a.I, M = a.M, U = a.U; const L = [];
  const so = async (u, usul, tana) => { const o = {method: usul || 'GET', credentials: 'same-origin'};
    if (tana !== undefined) { o.headers = {'Content-Type': 'application/json'}; o.body = JSON.stringify(tana); }
    const r = await fetch(u, o); const t = await r.text(); let j = null; try { j = JSON.parse(t); } catch (e) {} L.push([u, r.status, t.slice(0, 160)]); return {st: r.status, j}; };
  const R = {};
  // katta buyurtma: 12 detal, uzun nomlar, jami ~1.23 mlrd so'm, qisman topshirilgan, katta to'lov
  const items = [];
  for (let i = 0; i < 12; i++) items.push({name: U + ' №' + (i + 1), category: 'profil', width: 20, thickness: 15, length: 30, quantity: 20,
      unit_price: 5143866, is_coated: i % 2 === 0, penoplast_id: I.peno, price_per_m3: null, finished_product_id: null, sub_details: []});
  const tana = {project_id: I.loyiha, order_type: 'product', recipe_id: I.retsept, master_id: I.usta || null, deadline: a.muddat,
    is_draft: false, base_price: 600000, loy_kg: 20, items};
  let r = await so('/api/orders', 'POST', tana);
  if (r.st === 409) r = await so('/api/orders?confirm_shortage=true', 'POST', tana);
  R.katta = r.j && r.j.id;
  if (R.katta) {
    await so('/api/payments', 'POST', {order_id: R.katta, amount: 987654321, payment_type: 'zaklat', payment_method: 'naqd', notes: M + ' katta zaklat'});
    const h = await so('/api/orders/' + R.katta + '/delivery-status');
    const it = h.j && h.j.items && h.j.items[0];
    if (it) await so('/api/deliveries', 'POST', {order_id: R.katta, items: [{order_item_id: it.id, quantity: 5}], received_by: M + ' Qabul qiluvchi',
                                                notes: M + ' qisman yuk', transport_carrier: M + ' Tashuvchi', transport_cost: 1250000, transport_payer: 'company'});
  }
  // qoralama va jarayondagi ishlab chiqarish (Boshlash / Yakunlash oynalari)
  if (I.tur && I.bom) {
    const d = await so('/api/production/orders', 'POST', {product_type_id: I.tur, bom_id: I.bom, quantity: 2, source_type: 'warehouse_stock', notes: M + ' qoralama'});
    R.po_qoralama = d.j && (d.j.id || (d.j.production_order && d.j.production_order.id));
    const j = await so('/api/production/orders', 'POST', {product_type_id: I.tur, bom_id: I.bom, quantity: 3, source_type: 'warehouse_stock', notes: M + ' jarayonda'});
    R.po_jarayon = j.j && (j.j.id || (j.j.production_order && j.j.production_order.id));
    if (R.po_jarayon) await so('/api/production/orders/' + R.po_jarayon + '/start', 'POST');
  }
  // uzun nomli ta'minotchi + katta kirim
  const sp = await so('/api/suppliers', 'POST', {name: M + ' Qurilish Materiallari Savdo MChJ', phone: '+998901234567', notes: M + ' — asosiy yetkazib beruvchi'});
  R.sup2 = sp.j && sp.j.id;
  if (R.sup2 && I.kley && I.qum) await so('/api/inventory/receipt', 'POST', {items: [{inventory_id: I.kley, quantity: 100, price_per_unit: 12345678},
      {inventory_id: I.qum, quantity: 1000, price_per_unit: 9876}], supplier_id: R.sup2, document_number: M + '-KIRIM-2026-0000123',
      paid_now: 1000000000, transport_cost: 2500000, tushirish_cost: 500000, yuklash_cost: 0, boshqa_cost: 0, add_to_cost: true,
      notes: M + ' katta kirim hujjati', production_type: 'umumiy'});
  // katta moliya yozuvi
  await so('/api/finance/transactions', 'POST', {date: a.sana + 'T00:00:00', category: 'Boshqa', amount: 1234567890, notes: M + ' — yillik ijara va kommunal xizmatlar uchun to\'lov',
                                                 production_type: 'umumiy'});
  // uzun nomli hodim (katta oylik) va ishdan ketgan hodim (Savat — «Tiklash» oynasi)
  const h2 = await so('/api/employees', 'POST', {name: M + ' Abdulazizov Muhammadjon', position: 'Bosh texnolog — kesish sexi', pay_type: 'fixed',
                                                 fixed_amount: 123456789, production_type: 'umumiy', notes: M + ' hodim', ishga_kirgan_sana: '2026-01-05'});
  R.hodim2 = h2.j && h2.j.id;
  const h3 = await so('/api/employees', 'POST', {name: M + ' Ketgan Hodim Raximjonov', position: 'Kesuvchi', pay_type: 'fixed', fixed_amount: 4000000,
                                                 production_type: 'umumiy', ishga_kirgan_sana: '2026-01-05'});
  R.hodim3 = h3.j && h3.j.id;
  if (R.hodim3) await so('/api/employees/' + R.hodim3 + '?ketgan_sana=2026-09-30', 'DELETE');
  // bu oy avanslari (Avans oynasida ro'yxat — 4 yozuv)
  for (const [hid, sm] of [[I.hodim, 500000], [R.hodim2, 12345678]]) {
    if (!hid) continue;
    for (let i = 1; i <= 4; i++) await so('/api/employees/' + hid + '/advance?amount=' + sm + '&confirm_excess=true&notes=' + encodeURIComponent(i + '-avans — ' + M + ' (naqd, kassadan)'), 'POST');
  }
  // ikkinchi usta (uzun nom) va foydalanuvchi
  await so('/api/masters', 'POST', {name: M + ' Usta Karimov Abdurahmon', phone: '+998907654321', cashback_percent: 5, kpi_percent: 0, region: 'Andijon viloyati, Asaka tumani'});
  await so('/api/users', 'POST', {username: 'o183_operator', password: 'Parol123!', role: 'manager', full_name: M + ' Operator Xasanova'});
  return {R, L: L.filter(x => !(x[1] >= 200 && x[1] < 300))};
}"""

OLCH_JS = r"""(a) => {
  const vw = innerWidth, vh = innerHeight; const CS = e => getComputedStyle(e); const R = e => e.getBoundingClientRect();
  const vis = e => { const r = R(e); const s = CS(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05; };
  const nom = e => { let s = e.tagName.toLowerCase() + (e.id ? '#' + e.id : '');
    if (typeof e.className === 'string' && e.className.trim()) s += '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.');
    const t = ((e.tagName === 'SELECT' ? '' : (e.innerText || e.value || e.getAttribute('aria-label') || e.getAttribute('placeholder') || '')) + '').trim().replace(/\s+/g, ' ').slice(0, 42);
    return t ? s + ' «' + t + '»' : s; };
  const rr = r => [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)];
  const ochiqlar = () => [...document.querySelectorAll('body *')].filter(e => { const s = CS(e); if (s.position !== 'fixed' || !vis(e)) return false;
      const r = R(e); return r.width >= vw - 2 && r.height >= vh - 2 && parseInt(s.zIndex || 0) >= 900; }).map(e => e.id || nom(e).slice(0, 40));
  const roots = [...document.querySelectorAll(a.root)].filter(vis);
  if (!roots.length) return {ochilmadi: true, ochiq: ochiqlar(), vw, vh};
  const root = roots[roots.length - 1];
  let box = a.box ? root.querySelector(a.box) : null;
  if (!box) {
    const r0 = R(root);
    if (CS(root).position === 'fixed' && r0.width >= vw - 2 && r0.height >= vh - 2) {
      const ch = [...root.children].filter(e => vis(e) && !['STYLE', 'SCRIPT'].includes(e.tagName));
      ch.sort((x, y) => R(y).width * R(y).height - R(x).width * R(x).height);
      box = ch[0] || root;
    } else box = root;
  }
  const br = R(box), bs = CS(box), rs = CS(root);
  const SCR = /(auto|scroll|overlay)/;
  const ichida = [...root.querySelectorAll('*')].filter(e => vis(e) && !['STYLE', 'SCRIPT', 'OPTION'].includes(e.tagName));
  const xSur = [root, ...ichida].filter(e => SCR.test(CS(e).overflowX) && e.scrollWidth > e.clientWidth + 1);
  const xSurIchida = e => xSur.some(p => p !== e && p.contains(e));
  const chiq = ichida.filter(e => { const r = R(e); return (r.right > vw + 1 || r.left < -1) && !xSurIchida(e); });
  const chiqqan = chiq.filter(e => !chiq.some(x => x !== e && e.contains(x))).map(e => ({el: nom(e), rect: rr(R(e))}));
  const qut = ichida.filter(e => { if (e === box || !box.contains(e)) return false; const r = R(e);
      return (r.right > br.right + 1 || r.left < br.left - 1) && !xSurIchida(e); });
  const qutidan = qut.filter(e => !qut.some(x => x !== e && e.contains(x))).map(e => ({el: nom(e), rect: rr(R(e))}));
  const xsur = xSur.map(e => { const er = R(e); const ong = er.left + e.clientLeft + e.clientWidth;
      const sab = [...e.querySelectorAll('*')].filter(x => vis(x) && R(x).right > ong + 1);
      return {el: nom(e).slice(0, 80), cw: e.clientWidth, sw: e.scrollWidth, quti: e === box || e === root,
              sabab: sab.filter(x => !sab.some(y => y !== x && x.contains(y))).slice(0, 4).map(x => ({el: nom(x).slice(0, 70), rect: rr(R(x)), w: Math.round(R(x).width)}))}; });
  // tor maydon: matn / son maydoni yoki tanlagichning yozuv joyi < 40 px (4-5 raqam ham ko'rinmaydi) YOKI kiritilgan qiymat sig'magan
  const cvt = document.createElement('canvas').getContext('2d');
  const tor = ichida.filter(e => (e.tagName === 'SELECT' || (e.tagName === 'INPUT' && !['checkbox', 'radio', 'button', 'submit', 'file', 'range', 'color', 'hidden', 'date', 'month', 'time', 'datetime-local'].includes((e.type || '').toLowerCase()))))
    .map(e => { const s = CS(e); cvt.font = s.fontWeight + ' ' + s.fontSize + ' ' + s.fontFamily;
      const q = e.tagName === 'SELECT' ? '' : (e.value || ''); const joy = Math.round(e.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight));
      return {el: nom(e).slice(0, 60), id: e.id || '', joy, w: Math.round(R(e).width), qiymat: (e.tagName === 'SELECT' ? (e.options[e.selectedIndex] || {}).text || '' : q || e.placeholder || '').slice(0, 40),
              qiymat_w: (q && /^[-+]?[\d\s\u00a0.,]+$/.test(q)) ? Math.round(cvt.measureText(q).width) : 0}; })
    .filter(x => x.joy < 40 || x.qiymat_w > x.joy + 1);
  const kesik = ichida.filter(e => { const s = CS(e); if (['INPUT', 'SELECT', 'TEXTAREA', 'svg', 'IMG', 'CANVAS'].includes(e.tagName)) return false;
      return (s.overflowX === 'hidden' || s.overflowX === 'clip') && e.scrollWidth > e.clientWidth + 1 && (e.innerText || '').trim(); })
    .map(e => ({el: nom(e), cw: e.clientWidth, sw: e.scrollWidth, ellipsis: CS(e).textOverflow === 'ellipsis'}));
  // o'z qutisidan toshgan matn (overflow: visible — qo'shni element USTIGA chiqadi): to'g'ridan-to'g'ri matnli blok, scrollWidth > clientWidth
  const toshgan = ichida.filter(e => { const s = CS(e); if (s.display === 'inline' || s.display === 'contents' || ['INPUT', 'SELECT', 'TEXTAREA', 'svg', 'IMG', 'CANVAS'].includes(e.tagName)) return false;
      if (s.overflowX !== 'visible') return false;
      return [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && e.scrollWidth > e.clientWidth + 2; })
    .map(e => ({el: nom(e).slice(0, 70), cw: e.clientWidth, sw: e.scrollWidth, rect: rr(R(e))}));
  // flex / grid qatori sig'madi: bolasi qator (konteyner) ichki chegarasidan o'ngga chiqqan (overflow: visible — qo'shni ustiga tushadi)
  ichida.filter(e => { const s = CS(e); return /flex|grid/.test(s.display) && s.overflowX === 'visible' && !xSurIchida(e); }).forEach(e => {
    const r = R(e), s = CS(e); const ong = r.right - parseFloat(s.borderRightWidth) - parseFloat(s.paddingRight);
    const b = [...e.children].filter(x => vis(x) && CS(x).position !== 'absolute' && CS(x).position !== 'fixed' && R(x).right > ong + 2);
    if (b.length && !toshgan.some(t => t.el === nom(e).slice(0, 70)))
      toshgan.push({el: nom(e).slice(0, 70), cw: Math.round(ong - r.left), sw: Math.round(Math.max(...b.map(x => R(x).right)) - r.left), rect: rr(r), qator: true,
                    bola: b.slice(0, 2).map(x => nom(x).slice(0, 50))}); });
  const cv = document.createElement('canvas').getContext('2d');
  const selKesik = ichida.filter(e => e.tagName === 'SELECT').map(e => { const s = CS(e); cv.font = s.fontWeight + ' ' + s.fontSize + ' ' + s.fontFamily;
      const o = e.options[e.selectedIndex]; const t = o ? o.text : ''; const w = cv.measureText(t).width;
      const joy = e.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
      return {el: (e.id ? '#' + e.id : nom(e)), matn: t.slice(0, 70), matn_w: Math.round(w), joy: Math.round(joy)}; }).filter(x => x.matn_w > x.joy + 1);
  // ── yetib borish ──
  const yetadi = e => {
    const sc = [];
    for (let p = e.parentElement; p; p = p.parentElement) { const s = CS(p);
      if ((SCR.test(s.overflowY) && p.scrollHeight > p.clientHeight + 1) || (SCR.test(s.overflowX) && p.scrollWidth > p.clientWidth + 1)) sc.push(p);
      if (p === root) break; }
    const eski = sc.map(p => [p.scrollTop, p.scrollLeft]);
    const r0 = R(e); const avval = r0.top >= -1 && r0.bottom <= vh + 1 && r0.left >= -1 && r0.right <= vw + 1;
    for (const p of sc) {
      const pr = R(p), s = CS(p);
      const t = Math.max(pr.top + p.clientTop, 0), b = Math.min(pr.top + p.clientTop + p.clientHeight, vh);
      const l = Math.max(pr.left + p.clientLeft, 0), g = Math.min(pr.left + p.clientLeft + p.clientWidth, vw);
      let er = R(e);
      if (SCR.test(s.overflowY)) { if (er.bottom > b) p.scrollTop += Math.min(er.bottom - b, er.top - t); else if (er.top < t) p.scrollTop -= (t - er.top); }
      er = R(e);
      if (SCR.test(s.overflowX)) { if (er.right > g) p.scrollLeft += Math.min(er.right - g, er.left - l); else if (er.left < l) p.scrollLeft -= (l - er.left); }
    }
    const r = R(e); let v = {l: Math.max(r.left, 0), t: Math.max(r.top, 0), r: Math.min(r.right, vw), b: Math.min(r.bottom, vh)};
    for (let p = e.parentElement; p; p = p.parentElement) { const s = CS(p);
      if (s.overflowX !== 'visible' || s.overflowY !== 'visible') { const pr = R(p); const cl = pr.left + p.clientLeft, ct = pr.top + p.clientTop;
        v = {l: Math.max(v.l, cl), t: Math.max(v.t, ct), r: Math.min(v.r, cl + p.clientWidth), b: Math.min(v.b, ct + p.clientHeight)}; }
      if (p === root) break; }
    const ul = Math.max(0, v.r - v.l) * Math.max(0, v.b - v.t) / Math.max(1, r.width * r.height);
    const nat = {ulush: Math.round(ul * 100) / 100, avval, rect: rr(r), surildi: sc.map(p => nom(p).slice(0, 50))};
    sc.forEach((p, i) => { p.scrollTop = eski[i][0]; p.scrollLeft = eski[i][1]; });
    return nat;
  };
  const BOS = 'button, a[href], input:not([type=hidden]), select, textarea, [role=button]';
  const boshq = ichida.filter(e => e.matches(BOS) && e !== root && e !== box);
  const nat = boshq.map(e => Object.assign({el: nom(e), tag: e.tagName, tur: (e.type || '').toLowerCase(), h: Math.round(R(e).height), w: Math.round(R(e).width),
                                            fs: parseFloat(CS(e).fontSize)}, yetadi(e)));
  const yetmas = nat.filter(x => x.ulush < 0.6);
  const surish_kerak = nat.filter(x => !x.avval && x.ulush >= 0.6).map(x => x.el);
  const kichik = nat.filter(x => (x.tag === 'BUTTON' || x.tag === 'A' || (x.tag === 'INPUT' && ['button', 'submit'].includes(x.tur))) && x.h < 36)
    .map(x => ({el: x.el, h: x.h, w: x.w}));
  const shrift = nat.filter(x => (x.tag === 'SELECT' || x.tag === 'TEXTAREA' || (x.tag === 'INPUT' && !['checkbox', 'radio', 'button', 'submit', 'file', 'range', 'color'].includes(x.tur))) && x.fs < 16)
    .map(x => ({el: x.el, fs: x.fs}));
  // oyna qutisining yetib bo'lmaydigan (kesilgan) qismi: suriladigan o'ram eng tepaga / eng pastga surilganda ham ekrandan tashqarida
  const kesilgan = (() => { const sc = []; for (let p = box; p; p = p.parentElement) { const s = CS(p);
      if (SCR.test(s.overflowY) && p.scrollHeight > p.clientHeight + 1 && p !== box) sc.push(p); if (p === root) break; }
    const eski = sc.map(p => p.scrollTop); sc.forEach(p => { p.scrollTop = 0; }); const ust = Math.max(0, -R(box).top);
    sc.forEach(p => { p.scrollTop = 1e9; }); const ost = Math.max(0, R(box).bottom - vh); sc.forEach((p, i) => { p.scrollTop = eski[i]; });
    return {ust: Math.round(ust), ost: Math.round(ost), suriladi: sc.map(p => nom(p).slice(0, 40))}; })();
  const sarlavha = (() => { const t = box.querySelector('h1, h2, h3, [class*=title], [id*=itle], [id*=arlavha]'); return t ? (t.innerText || '').trim().slice(0, 60) : ''; })();
  return {vw, vh, hujjat_sw: document.documentElement.scrollWidth, body_sw: document.body.scrollWidth, sarlavha,
          root: {el: nom(root).slice(0, 60), ovY: rs.overflowY, sh: root.scrollHeight, ch: root.clientHeight},
          box: {el: nom(box).slice(0, 80), rect: rr(br), w: Math.round(br.width), h: Math.round(br.height), sw: box.scrollWidth, cw: box.clientWidth, sh: box.scrollHeight,
                ch: box.clientHeight, maxH: bs.maxHeight, ovY: bs.overflowY, ovX: bs.overflowX, scrollLeft: Math.round(box.scrollLeft)},
          kesilgan, toshgan: toshgan.slice(0, 12), chiqqan: chiqqan.slice(0, 10), qutidan: qutidan.slice(0, 10), xsur, kesik: kesik.slice(0, 10), selKesik, yetmas, surish_kerak: surish_kerak.slice(0, 12),
          kichik, shrift, tor, boshqaruv: nat.length, ochiq: ochiqlar()};
}"""

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Oynalar: zip 184 tuzatgan nuqson holatlari + o'zgargan oynalarning odatiy holatlari (url, oyna selektori, ochish — sahifaning o'z funksiyasi)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
SLEEP = "const uxla = ms => new Promise(r => setTimeout(r, ms));"

LONG_NAMES = [f"{UZUN} №{i}" for i in range(1, 13)]

NIZO = [{"id": 800 + i, "employee_name": f"{M} Hodim Karimova №{i}", "position": "Bo'yoqchi", "date": "2026-10-10", "given_by": "Andijon Fasad Dekor Bosh Administratori",
         "amount": 123456789, "notes": "Oktabr oyi uchun avans — naqd, kassadan berilgan (hujjat №A-2026-10-000123)", "javob_vaqti": "2026-10-14T19:40:00"}
        for i in range(1, 4)]

AVANS = [{"id": 700 + i, "employee_name": f"{M} Hodim Yo'ldoshev №{i}", "requested_date": "2026-10-14", "amount": 1234567890,
          "notes": "Uy-joy ta'miri uchun avans so'rayman — keyingi ikki oy oyligidan ushlab qolinsin, iltimos"} for i in range(1, 6)]

KAT = []


def oyna(k, url, root, och, kut=900, box=None, izoh="", kim="admin", mock=None, oldin=None, keyin=None, qosh=None):
    KAT.append(dict(k=k, url=url, root=root, och=och, kut=kut, box=box, izoh=izoh, kim=kim, mock=mock, oldin=oldin, keyin=keyin, qosh=qosh))


def ustun(sel):
    return ("() => [...document.querySelectorAll(" + json.dumps(sel) + ")].filter(e => e.offsetParent !== null).slice(0, 3).map(e => ({w: Math.round(e.getBoundingClientRect().width), "
            "h: Math.round(e.getBoundingClientRect().height), l: Math.round(e.getBoundingClientRect().left), r: Math.round(e.getBoundingClientRect().right), sw: e.scrollWidth, matn: (e.innerText || '').replace(/\\s+/g, ' ').slice(0, 50)}))")


FP = "const i = fpItems.find(x => x.quantity > 0) || fpItems[0];"
TANLA_KATTA = SLEEP + ("const tanla = async (id) => { const g = document.querySelector('.ord-item[data-order-id=\"' + id + '\"]');"
                       " if (g) { const ph = g.closest('.proj-group'); if (ph && !ph.classList.contains('open')) { const h = ph.querySelector('.proj-head'); h && h.click(); await uxla(300); } g.click(); }"
                       " else { await selectOrder(id); } await uxla(1500); }; await tanla(window.__KATTA);")
oyna("base_tasdiq_qisqa", "/users", "#ccModal", "customConfirm(\"Foydalanuvchi o'chirilsinmi?\", {danger: true, okText: \"O'chirish\"});", 400,
     izoh="customConfirm — qisqa")
oyna("base_tasdiq_uzun", "/kpi", "#ccModal",
     "customConfirm(`Quyidagi ustalar sovg'aga yetgan, lekin hali \"Berildi\" belgilanmagan:\\n\\n${" + json.dumps([f"{M} Usta {n}" for n in
       ["Karimov Abdurahmon", "Toshmatov Bekzod", "Yusupov Jasurbek", "Qodirov Sardor", "Ergashev Nodirbek", "Rahimov Ulug'bek", "Sobirov Otabek",
        "Mirzayev Doniyor"]]) + ".join(', ')}\\n\\nShunga qaramay yopib, ularning qoldig'ini ham keshbekka o'tkazishni istaysizmi? (Ular sovg'a olmay qoladi!)`,"
     " {danger: true, okText: 'Shunga qaramay yop'});", 500,
     izoh="customConfirm — sovg'a davrini yopish (kpi.html:2319 matni, 8 usta nomi)")
oyna("hodim_nizo", "/dashboard", "#avansNizoModal", "", 1500, mock={"/api/admin/qurilma-sorovlari": [], "/api/admin/avans-nizolar": NIZO},
     izoh="3 nizo (soxta API javobi)", qosh=ustun("#avansNizoList .nizo-qator > div:first-child > div:first-child"))
oyna("hodim_avans", "/dashboard", "#advReqModal", "", 1500,
     mock={"/api/admin/qurilma-sorovlari": [], "/api/admin/avans-nizolar": [], "/api/admin/pending-advance-requests": AVANS}, izoh="5 so'rov (soxta API javobi)",
     qosh=ustun("#advReqList > div > div:first-child > div:first-child"))
oyna("kpi_hodim_tahrir", "/kpi", "#empModal", "const e = empItems.find(x => x.name.includes('Abdulazizov')) || empItems[0]; editEmployee(e.id);", 900)
oyna("kpi_avans", "/kpi", "#advanceModal", "document.querySelector('.emp-tugmalar .mini-btn').click();", 1000)
oyna("kpi_kirish", "/kpi", "#panelAccessModal", "document.querySelector('.emp-tugmalar .btn-gold-outline').click();", 600)
oyna("kpi_sovga", "/kpi", "#giftPeriodModal", "openGiftPeriodModal();", 800, izoh="sovg'a davri yopiq — yangi davr formasi")
oyna("kpi_sovga_ochiq", "/kpi", "#giftPeriodModal", "openGiftPeriodModal();", 1200, izoh="sovg'a davri ochiq (3 bosqich, 2 usta)",
     oldin="""async (I) => { const so = async (u, t) => (await fetch(u, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(t)})).status;
       return await so('/api/gift-period/open', {tiers: [{gift_name: 'Samsung Galaxy A54 smartfon (128 GB, qora)', threshold_amount: 123456789},
         {gift_name: 'Artel konditsioner 12 000 BTU (inverter)', threshold_amount: 456789012}, {gift_name: 'Chevrolet Cobalt avtomobili (2026, oq)', threshold_amount: 1234567890}], master_ids: null}); }""",
     keyin="""async () => (await fetch('/api/gift-period/close', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({force: true})})).status""")
oyna("tm_yangi", "/finished", "#prodModal", SLEEP + "openProduceModal(); await uxla(400); const f = (id, v) => { const e = document.getElementById(id); if (e) { e.value = v;"
     " e.dispatchEvent(new Event('input')); } }; f('p-h', '120'); f('p-w', '15'); f('p-l', '3.5'); f('p-m3', '1 200 000');", 800,
     izoh="o'lchamlar kiritilgan: 120 × 15 sm, 3,5 m, 1 m³ narxi 1 200 000")
oyna("tm_savat", "/finished", "#batchSellModal", "[...document.querySelectorAll('.fp-batch-check')].filter(x => parseFloat(x.dataset.qty) > 0).forEach(c => c.checked = true);"
     " onBatchCheckChange(); openBatchSellModal();", 700)
oyna("ombor_xaridlar", "/inventory", "#historyModal", "openPurchaseHistory();", 1500, qosh=ustun("#historyModal .mv-order-row > div:first-child"))
oyna("ombor_harakatlar", "/inventory", "#movementsModal", "openMovements();", 1500, qosh=ustun("#movementsModal .mv-order-row > div:first-child"))
oyna("b_yetkazish", "/orders", "#dlvModal", TANLA_KATTA + " openDeliveryModal(); await uxla(900); fillAllRemaining();", 1200,
     izoh="12 detalli katta buyurtma, qisman topshirilgan; «Qoldiqni to'ldirish» bosilgan", qosh=ustun("#dlvForm > div > div:first-child, #dlvForm > div > div:last-child"))
oyna("b_hisob", "/orders", "#sumModal", TANLA_KATTA + " openSummaryModal();", 1200)
oyna("b_ochirish_tasdiq", "/orders", "#genericConfirmOverlay", TANLA_KATTA + " deleteSelected();", 1500,
     izoh="«O'chirish» — server rejasidan uzun matn (qisman topshirilgan, 987 654 321 so'm to'langan buyurtma)")
oyna("b_tasdiq_qisqa", "/orders", "#genericConfirmOverlay", "showConfirmModal(\"Bu to'lovni o'chirishni tasdiqlaysizmi?\", {danger: true, okText: \"O'chirish\"});", 400)
oyna("b_tasdiq_narxsiz", "/orders", "#genericConfirmOverlay", "_narxsizTasdiq(" + json.dumps(LONG_NAMES) + ", false);", 500,
     izoh="«Narx kiritilmagan» — 12 detal nomi (sahifaning o'z `_narxsizTasdiq` i)")
oyna("b_tekshiruv", "/orders", "#validationModal", SLEEP + "showNewForm(); addItem(); addItem(); addItem(); await uxla(400); saveOrder(false);", 900,
     izoh="bo'sh forma «Buyurtmani saqlash» — tekshiruv ro'yxati")
oyna("b_yetishmovchilik", "/orders", "#validationModal", "showStockShortageModal(" + json.dumps(
    [f"{M} Penoplast 15: kerak 1 234,567 m³, omborda 10,000 m³ — 1 224,567 m³ yetmaydi",
     f"{M} Kley akril (oq, ichki va tashqi ishlar uchun): kerak 12 345,5 kg, omborda 300 kg",
     f"{M} Qum: kerak 98 765 kg, omborda 1 500 kg"]) + ", {}, false, 0, 'naqd');", 500, izoh="xomashyo yetishmasligi (3 qator, server matni shaklida)")
oyna("b_yetishmovchilik5", "/orders", "#validationModal", "showStockShortageModal(" + json.dumps(
    [f"{M} Penoplast 15: kerak 1 234,567 m³, omborda 10,000 m³ — 1 224,567 m³ yetmaydi",
     f"{M} Kley akril (oq, ichki va tashqi ishlar uchun): kerak 12 345,5 kg, omborda 300 kg",
     f"{M} Qum: kerak 98 765 kg, omborda 1 500 kg", f"{M} Setka: kerak 2 400 dona, omborda 41 dona",
     "Sement M400: kerak 350 qop, omborda 100 qop"]) + ", {}, false, 0, 'naqd');", 500, izoh="xomashyo yetishmasligi — 5 qator")
oyna("b_foyda", "/orders", "#profitModal", TANLA_KATTA + " await loadProfit();", 1200, izoh="katta buyurtma (~1,23 mlrd so'm)",
     qosh=ustun("#profitModal div[style*='gap:12px;padding:12px 0'] > div[style*='flex:1'], #profitModal div[style*='gap:12px;padding:12px 0'] > div:last-child"))
oyna("b_mrp_tanlash", "/orders", "#__mrpPicker", SLEEP + "showNewForm(); addItem(); await uxla(300); const d = document.querySelector('.detal');"
     " const t = d.querySelector('.type-opt[data-value=\"mrp_product\"]'); if (t) { t.click(); await uxla(300); }"
     " const b = [...d.querySelectorAll('button')].find(x => /openMrpProductPicker/.test(x.getAttribute('onclick') || ''));"
     " await openMrpProductPicker(b || d); await uxla(300); const o = [...document.body.children].reverse().find(x => getComputedStyle(x).position === 'fixed' && x.querySelector('#mrpPickerList')); if (o) o.id = '__mrpPicker';",
     700, izoh="MRP mahsulotini tanlash (JS bilan yaratiladigan oyna)")
oyna("retsept_yangi", "/recipes", "#addModal", "await openAddModal();", 800)
oyna("retsept_yangi_tanlash", "/recipes", "#addModal", "await openAddModal(); await openIngredientPicker('f');", 1000, izoh="xomashyo tanlagichi ochiq")
oyna("retsept_tahrir", "/recipes", "#editModal", "document.querySelector('[aria-label=\"Tahrirlash\"][onclick^=\"openEditModal\"]').click();", 1000)
oyna("rol_user", "/rollar", "#rlUserModal", "userQoshOch();", 700)
oyna("taminotchi_tarix", "/suppliers", "#historyModal", "const b = [...document.querySelectorAll('.sup-tarix')]; (b.find(x => x.closest('.sup-row') && /MChJ/.test(x.closest('.sup-row').innerText)) || b[0]).click();", 1600,
     qosh=ustun("#historyModal div[style*='justify-content:space-between;align-items:center;padding:7px 0'] > div:first-child"))
oyna("taminotchi_xarid", "/suppliers", "#historyModal", SLEEP + "document.querySelector('.sup-tarix').click(); await uxla(1500); openAddPurchase(); apToggleNewItem();", 900,
     izoh="tarix oynasida «Xarid qo'shish» + yangi material")

NUQSON = {"b_tasdiq_narxsiz": "P2-1", "b_ochirish_tasdiq": "P2-1", "kpi_avans": "P2-2", "tm_yangi": "P2-3", "b_yetishmovchilik5": "P2-4",
          "kpi_kirish": "P2-5", "b_yetkazish": "P2-6", "b_foyda": "P2-7", "retsept_yangi_tanlash": "P2-8", "base_tasdiq_uzun": "P2-9",
          "retsept_yangi": "P3-1", "retsept_tahrir": "P3-1", "kpi_sovga": "P3-2", "tm_savat": "P3-3", "b_hisob": "P3-4",
          "ombor_xaridlar": "P3-5", "ombor_harakatlar": "P3-5", "taminotchi_tarix": "P3-6", "taminotchi_xarid": "P3-6", "hodim_nizo": "P3-7",
          "hodim_avans": "P3-7", "b_mrp_tanlash": "P3-8", "kpi_sovga_ochiq": "P3-9", "kpi_hodim_tahrir": "P3-9", "rol_user": "P3-9"}


# ism ustuni eng kam kengligi (P3-7 — baho o'lchamaydi, alohida o'lchov)
USTUN_MIN = {"hodim_nizo": 180, "hodim_avans": 180, "taminotchi_tarix": 150}
# kech146 (mutatsiya U18 — O'LCHANGAN): ta'minotchi tarixidagi xarid qatori o'ralmasa 320 px da nom ustuni 61 px (236 px balandlikda
# harfma-harf), `baho` OK derdi (`overflow-wrap:anywhere` — hech narsa toshmaydi); to'g'ri holatda 236 px (nom butun qator)
USTUN_NOMI = {"taminotchi_tarix": "xarid nomi ustuni"}

# Quti PASTGA toshishi va savol oynalarida tugmalar (P2-1 / P2-9 qoidasi «matn suriladi, tugmalar doim ko'rinadi») — `baho` buni
# o'lchamaydi: `qutidan` — faqat yon tomon, `yetmas` — 0,6 dan kam ko'rinsa. O'LCHANGAN (kech146, mutatsiya U02): `customConfirm` matn
# bloki surilmasa 320 px da quti mazmuni 641 / 600 px — «Shunga qaramay yop» qutidan 41 px pastga toshib, ekrandan 21 px chiqadi
# (0,75 ko'rinadi — `baho` OK derdi).
# oyna ko'rindimi (OLCH_JS dagi `vis` bilan bir qoida)
OCHIQ_JS = r"""(sel) => [...document.querySelectorAll(sel)].some(e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
  return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05; })"""
TUGMA_DOIM = {"base_tasdiq_qisqa", "base_tasdiq_uzun", "b_tasdiq_qisqa", "b_tasdiq_narxsiz", "b_ochirish_tasdiq"}
QUTI_JS = r"""(a) => {
  const vw = innerWidth, vh = innerHeight; const R = e => e.getBoundingClientRect(); const CS = e => getComputedStyle(e);
  const vis = e => { const r = R(e); const s = CS(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05; };
  const roots = [...document.querySelectorAll(a.root)].filter(vis);
  if (!roots.length) return {ochilmadi: true};
  const root = roots[roots.length - 1];
  let box = a.box ? root.querySelector(a.box) : null;
  if (!box) {
    const r0 = R(root);
    if (CS(root).position === 'fixed' && r0.width >= vw - 2 && r0.height >= vh - 2) {
      const ch = [...root.children].filter(e => vis(e) && !['STYLE', 'SCRIPT'].includes(e.tagName));
      ch.sort((x, y) => R(y).width * R(y).height - R(x).width * R(x).height);
      box = ch[0] || root;
    } else box = root;
  }
  const b = R(box), bs = CS(box);
  const tugmalar = [...box.querySelectorAll('button')].filter(vis).map(e => { const r = R(e);
      return {el: e.id || (e.innerText || '').trim().slice(0, 30), top: Math.round(r.top), bottom: Math.round(r.bottom)}; });
  const tashqarida = tugmalar.filter(t => t.top < Math.max(0, b.top) - 1 || t.bottom > Math.min(vh, b.bottom) + 1);
  return {vh, quti: [Math.round(b.top), Math.round(b.bottom)], sh: box.scrollHeight, ch: box.clientHeight, ovY: bs.overflowY,
          toshadi: !/(auto|scroll|overlay)/.test(bs.overflowY) && box.scrollHeight > box.clientHeight + 1, tugmalar, tashqarida};
}"""

# «Foyda tahlili» qatori (P2-7): raqam, belgi va nom BIR qatorda, nom ≥ 100 px, summa nom ustiga tushmaydi — `baho` buni ko'rmaydi.
# O'LCHANGAN (kech146, mutatsiya U08): qator klassi `pf-qator` To'lov formasining `.pf-qator > div{flex:1 1 140px !important}` (≤ 900 px)
# qoidasini olib, 320 / 375 / 390 px da raqam, belgi, nom va summa — har biri ALOHIDA qatorda (4 qavat) edi; `baho` OK derdi.
QATOR_BIR = {"b_foyda": "#profitModal div[style*='gap:12px;padding:12px 0']"}
QATOR_JS = r"""(sel) => [...document.querySelectorAll(sel)].filter(e => e.offsetParent !== null).slice(0, 3).map(q => { const c = [...q.children];
  const r = e => { const x = e.getBoundingClientRect(); return {l: Math.round(x.left), t: Math.round(x.top), r: Math.round(x.right), b: Math.round(x.bottom), w: Math.round(x.width)}; };
  return {raqam: r(c[0]), belgi: r(c[1]), nom: r(c[2]), summa: r(c[c.length - 1])}; })"""


def qator_bir(x):
    n = x["raqam"]
    return (abs(x["belgi"]["t"] - n["t"]) <= 6 and abs(x["nom"]["t"] - n["t"]) <= 6 and x["nom"]["w"] >= 100
            and (x["summa"]["t"] >= x["nom"]["b"] - 2 or x["summa"]["l"] >= x["nom"]["r"] - 1))


def baho(o, w):
    """(daraja, [sabablar]) — daraja: 'OK' / 'P3' / 'P2' / 'OCHILMADI'."""
    if not isinstance(o, dict) or o.get("ochilmadi") or o.get("js_xato"):
        return "OCHILMADI", [str(o)[:120]]
    p2, p3 = [], []
    k = o.get("kesilgan") or {}
    if k.get("ust", 0) > 2:
        p2.append(f"top {k['ust']} px cut off (unreachable)")
    if k.get("ost", 0) > 2:
        p2.append(f"bottom {k['ost']} px cut off (unreachable)")
    for y in o.get("yetmas") or []:
        p2.append(f"unreachable control {y['el']} visible {y['ulush']:.2f} rect {y['rect']}")
    if (o.get("hujjat_sw") or 0) > int(w):
        p2.append(f"document scrollWidth {o['hujjat_sw']} > {w}")
    for c in o.get("chiqqan") or []:
        p2.append(f"off-screen {c['el']} {c['rect']}")
    for c in o.get("qutidan") or []:
        p3.append(f"spills out of box {c['el']} {c['rect']} (box {o['box']['rect']})")
    for x in o.get("xsur") or []:
        if x.get("quti"):
            p3.append(f"box scrolls sideways {x['el']} {x['cw']}/{x['sw']} — cause: {x.get('sabab')}")
    for x in o.get("tor") or []:
        (p2 if x["joy"] < 24 else p3).append(f"narrow field {x['el']} text area {x['joy']} px (field {x['w']} px) value «{x['qiymat']}»"
                                             + (f" value needs {x['qiymat_w']} px" if x.get("qiymat_w") else ""))
    for x in o.get("toshgan") or []:
        p3.append(f"text overflows its own box (overlaps neighbour) {x['el']} {x['cw']}/{x['sw']} rect {x['rect']}")
    if ((o.get("box") or {}).get("scrollLeft") or 0) > 0:
        p2.append(f"box opened scrolled sideways: scrollLeft {o['box']['scrollLeft']} px — left edge of content hidden")
    for x in o.get("kesik") or []:
        p3.append(f"clipped text {x['el']} {x['cw']}/{x['sw']}{' (ellipsis)' if x.get('ellipsis') else ''}")
    for x in o.get("kichik") or []:
        p3.append(f"tap target {x['h']} px {x['el']}")
    for x in o.get("shrift") or []:
        p3.append(f"input font {x['fs']} px {x['el']}")
    if p2:
        return "P2", p2 + p3
    if p3:
        return "P3", p3
    return "OK", []

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Server va brauzer
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


port = _port()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
th = threading.Thread(target=server.run, daemon=True)
th.start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
B = f"http://127.0.0.1:{port}"
tk = datetime.utcnow() + timedelta(hours=5)
K = {"m": M, "sana": tk.strftime("%Y-%m-%d"), "yil": tk.year, "oy": tk.month, "muddat": (tk + timedelta(days=9)).strftime("%Y-%m-%d")}
OLCHAM = {320: 640, 375: 667, 390: 844}


def yonalish(route):
    u = route.request.url
    if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
        return route.fulfill(status=200, content_type="application/javascript", body=CHART_ORINBOSAR)
    if u.startswith("https://fonts.googleapis.com/"):
        return route.fulfill(status=200, content_type="text/css", body="")
    return route.fulfill(status=204, body="")


section("T. Server, brauzer, ma'lumot")
check("T0 lokal server va Playwright", bool(server.started and PW_BOR), _pw_x)
JS_XATO = []
if server.started and PW_BOR:
    with sync_playwright() as pw:
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*", "chrome-linux",
                                                  "chrome"))):
            _exe = _yol
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def kontekst(w):
            ctx = br.new_context(viewport={"width": w, "height": OLCHAM.get(w, 844)}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                 timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|cdn\.jsdelivr\.net|unpkg\.com)/.*"),
                      yonalish)
            pg = ctx.new_page()
            pg.set_default_timeout(15000)
            pg.goto(B + "/login")
            pg.fill("input[name=username]", ADMIN)
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            return ctx, pg

        def js(p, kod, arg=None):
            try:
                return p.evaluate(kod, arg) if arg is not None else p.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def kut_royxat(p, kod, arg=None):
            """Ro'yxat (qatorlar) o'lchovi — og'ir yuk ostida ma'lumot kechikishi mumkin: bo'sh bo'lsa 10 s gacha qayta o'lchanadi."""
            u = js(p, kod, arg)
            for _ in range(20):
                if isinstance(u, list) and u:
                    break
                p.wait_for_timeout(500)
                u = js(p, kod, arg)
            return u

        ctx, pg = kontekst(390)
        Z = pg.evaluate(ZANJIR_JS, K)
        Q = pg.evaluate(QOSHIMCHA_JS, {"I": Z.get("I") or {}, "M": M, "U": UZUN, "muddat": K["muddat"], "sana": K["sana"]})
        ctx.close()
        I = dict(Z.get("I") or {})
        I.update(Q.get("R") or {})
        check("T1 ma'lumot zanjiri (ilovaning o'z API si) — yiqilgan so'rov yo'q, katta buyurtma bor",
              not Z.get("yiqilgan") and not Q.get("L") and I.get("katta"), (Z.get("yiqilgan"), Q.get("L"), sorted(I)))
        for w in (320, 375, 390):
            section(f"O. Oynalar — {w} × {OLCHAM[w]}")
            ctx, pg = kontekst(w)
            pg.on("pageerror", lambda ex, w=w: JS_XATO.append(f"{w}: {str(ex)[:200]}"))
            for e in KAT:
                if e["mock"]:
                    for u, data in e["mock"].items():
                        pg.route("**" + u, (lambda body: (lambda route: route.fulfill(status=200, content_type="application/json", body=body)))(json.dumps(data)))
                if e["oldin"]:
                    js(pg, e["oldin"], I)
                try:
                    pg.goto(B + e["url"], wait_until="networkidle")
                except Exception:          # noqa: BLE001
                    pass
                pg.wait_for_timeout(500)
                pg.evaluate("(I) => { window.__KATTA = I.katta; window.__I = I; }", I)
                och = js(pg, "async () => { try { " + e["och"] + " return 'ok'; } catch (ex) { return 'XATO: ' + String(ex); } }") if e["och"] else "ok"
                pg.wait_for_timeout(e["kut"])
                # og'ir yuk ostida (parallel testlar) server javobi kechikishi mumkin — oyna ko'rinmagan bo'lsa 10 s gacha kutiladi, keyin
                # ochilish animatsiyasi uchun yana 0,6 s (kech146 00:0x, O'LCHANGAN: TF1 + parallel etalon — «O'chirish» rejasi 1,5 s da
                # kelmay, oyna «ochilmadi» deb yiqildi; yolg'iz yurishda o'tadi)
                if js(pg, OCHIQ_JS, e["root"]) is not True:
                    try:
                        pg.wait_for_function(OCHIQ_JS, arg=e["root"], timeout=10000)
                    except Exception:      # noqa: BLE001
                        pass
                    pg.wait_for_timeout(600)
                # ochilgan zahoti (OLCH_JS surib ko'rishidan OLDIN): quti pastga toshishi, savol oynasida tugmalar
                q = js(pg, QUTI_JS, {"root": e["root"], "box": e["box"]})
                m = js(pg, OLCH_JS, {"root": e["root"], "box": e["box"]})
                d, sab = baho(m, str(w))
                b = (m.get("box") or {}) if isinstance(m, dict) else {}
                check(f"{NUQSON.get(e['k'], 'R')} {e['k']} @{w} — {e['root']}: OK (quti {b.get('w', '?')}×{b.get('h', '?')})"
                      + (f" — {e['izoh']}" if e["izoh"] else ""), och == "ok" and d == "OK", (och, d, sab[:6]))
                q_ok = isinstance(q, dict) and not q.get("ochilmadi") and not q.get("js_xato")
                check(f"{NUQSON.get(e['k'], 'R')} {e['k']} @{w} — quti mazmuni pastga TOSHMAYDI (sig'adi yoki quti o'zi suriladi)",
                      q_ok and not q.get("toshadi"), q)
                if e["k"] in TUGMA_DOIM:
                    check(f"{NUQSON.get(e['k'], 'R')} {e['k']} @{w} — tugmalar ochilgan zahoti TO'LIQ ko'rinadi (surmasdan, quti ichida)",
                          q_ok and len(q.get("tugmalar") or []) >= 2 and not q.get("tashqarida"), q)
                if e["k"] in USTUN_MIN:
                    # P3-7: hodim ismi ustuni (agent o'lchovi: 320 px da 56 / 94 px — so'zlar harfma-harf bo'linardi); P3-6: xarid nomi (U18)
                    u = kut_royxat(pg, e["qosh"])
                    eng = min((x.get("w", 0) for x in u), default=0) if isinstance(u, list) else 0
                    check(f"{NUQSON[e['k']]} {e['k']} @{w} — {USTUN_NOMI.get(e['k'], 'ism ustuni')} ≥ {USTUN_MIN[e['k']]} px (siqilmagan)",
                          isinstance(u, list) and len(u) > 0 and eng >= USTUN_MIN[e["k"]], u)
                if e["k"] in QATOR_BIR:
                    u = kut_royxat(pg, QATOR_JS, QATOR_BIR[e["k"]])
                    check(f"{NUQSON[e['k']]} {e['k']} @{w} — har qatorda raqam, belgi va nom BIR qatorda, nom ≥ 100 px, summa nom ustiga tushmaydi",
                          isinstance(u, list) and len(u) > 0 and all(qator_bir(x) for x in u), u)
                if e["mock"]:
                    for u in e["mock"]:
                        try:
                            pg.unroute("**" + u)
                        except Exception:  # noqa: BLE001
                            pass
                if e["keyin"]:
                    js(pg, e["keyin"])
            ctx.close()
        br.close()
server.should_exit = True
th.join(timeout=10)

section("Z. Sahifa xatolari")
check("Z1 oynalar ochilganda ushlanmagan JS xatosi yo'q", not JS_XATO, JS_XATO[:5])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
