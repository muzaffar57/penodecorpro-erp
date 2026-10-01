#!/usr/bin/env python3
"""
test_c_telefon.py — kech119, C BOSQICH (telefon): dastur 390 va 360 px kenglikdagi telefonda — HAQIQIY brauzerda (Chromium,
Playwright; sensorli ekran — `hover: none`) O'LCHANADI.

NIMA UCHUN KERAK (audit kech114 — 13 telefon topilmasi; kech119 da `work/k125/telefon.py` bilan asl kodda O'LCHANGAN):
  G2-02  yangi buyurtma: «Eni» / «Kengligi» / «Uzunlik» maydonlari 26 px, 360 px da «Uzunlik» ekrandan chiqardi;
  G2-21  buyurtma tanlanganda amallar (Tayyor, Tahrirlash …) sahifada ~2 000 px pastda, sahifa 530 px kenglikda;
  G3-08  qarzdor tanlanganda «To'lov qabul qilish» 1 390 px da — ekranda yo'q;
  G2-18  Loyihalar sahifasi 776 px kenglikda (tablar ustunni kengaytirardi), «Qolgan to'lov» ekrandan tashqarida;
  G1-20 / G6-15  Dashboard / KPI pul kartalari siqilgan, KPI sahifasi 456 px; «Ehson foizi» «Saqlash» 360 px da chiqardi;
  G3-19  Moliya: qarz qutilari bir qatorda, tranzaksiyalar jadvali 720 px; «Daromad taqsimoti» summalari ekrandan chiqardi;
  G4-11  Omborda narx va chegara ko'rinmasdi; G4-24 retsept tarkibidagi nomlar 46 px («Namuna K…»);
  G5-15  Tayyor mahsulotlar — birinchi mahsulot birinchi ekranda yo'q (5 ta raqam kartasi ~500 px);
  G5-16  rasm qo'shish belgisi (kamera) faqat sichqoncha ustiga kelganda ko'rinardi — telefonda umuman yo'q;
  qo'shimcha (o'lchovda topilgan): yopiq menyuning soyasi har sahifada chap chetda qora chiziq; Bosh sahifa sarlavhasi
  «Assalomu alaykum, Namuna De…» deb kesilardi; Dashboard majburiyat nomi «Namuna Ijara (har oy 5-kunigacha)» 99 px.
QOIDA: telefonda (≤ 600 / 768 / 900 px) hech bir sahifa ekrandan kengaymaydi — yon tomonga faqat ATAYLAB suriladigan
  tasmalar (Dashboard karuseli `#topGrid`, Tayyor mahsulotlar raqam kartalari `.fp-stat-tasma`) va o'z qutisi ichidagi keng
  jadvallar suriladi; tanlangan buyurtma / qarzdorning amallari va to'lov formasi ekranda ko'rinadi; nomlar kesilmaydi.
BO'LIMLAR: S — statik (uslub fayli, shablonlar, kesh versiyasi); M — ma'lumot (brauzerda dasturning o'z API si orqali to'liq
  ish zanjiri: ombor, kirim, retsept, usta, hodim, loyiha, buyurtmalar, to'lov, yetkazish, qaytarish, MRP, tayyor mahsulot,
  moliya, majburiyat); G — har sahifa 390 / 360 px da ekrandan chiqmaydi, JS xatosi yo'q; T — topilmalar bo'yicha ssenariylar.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 125) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` va Chromium (`PLAYWRIGHT_BROWSERS_PATH` / `/opt/pw-browsers`). Shriftlar va Chart.js tashqi
  manbadan yuklanmaydi (shrift — tizimniki, Chart.js — o'rinbosar: grafik kartalari o'lchami shablonda qat'iy).
ISHLATISH: python3 tools/test_c_telefon.py
"""
import os
import re
import sys
import glob
import base64
import time
import socket
import tempfile
import threading
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "c_telefon_test"
_T = tempfile.mkdtemp(prefix="ctel_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'c_telefon_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


CSS = oqi("static/style.css")
TPL = {os.path.basename(f): open(f, encoding="utf-8").read() for f in sorted(glob.glob(os.path.join(ROOT, "templates", "*.html")))}
MAIN = oqi("main.py")


def media_bloklari(matn, shart_re):
    """`@media (...)` bloklarining ichi (shart regex ga mos keladiganlari) — qavslar muvozanati bilan."""
    natija = []
    for m in re.finditer(r"@media\s*([^{]+)\{", matn):
        if not re.search(shart_re, m.group(1)):
            continue
        i, chuqur = m.end(), 1
        while i < len(matn) and chuqur:
            if matn[i] == "{":
                chuqur += 1
            elif matn[i] == "}":
                chuqur -= 1
            i += 1
        natija.append(matn[m.end(): i - 1])
    return "\n".join(natija)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik — uslub fayli, shablonlar, kesh versiyasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_mob = media_bloklari(CSS, r"max-width:\s*(600|640|768|900)px")
_sb = [x for x in re.findall(r"\.sidebar\s*\{([^}]*)\}", _mob) if "translateX(-100%)" in x]
_sbo = re.search(r"\.sidebar\.sidebar-open\s*\{([^}]*)\}", _mob)
check("S1 yopiq (ekrandan tashqaridagi) menyu soyasiz (`box-shadow: none`), soya — faqat `.sidebar.sidebar-open` da (ilgari "
      "chap chetda ~20 px qora chiziq har sahifada)",
      len(_sb) == 1 and re.search(r"box-shadow:\s*none", _sb[0]) and not re.search(r"box-shadow:\s*\d", _sb[0])
      and _sbo and re.search(r"box-shadow:\s*4px", _sbo.group(1)),
      [[x[-200:] for x in _sb], _sbo.group(1) if _sbo else None])
_sv = re.search(r'templates\.env\.globals\["static_version"\]\s*=\s*"([^"]+)"', MAIN)
check("S2 kesh versiyasi yangilangan (style.css o'zgardi — telefonda eski uslub keshdan olinmasin): «20261001-2» emas",
      _sv and _sv.group(1) != "20261001-2" and _sv.group(1) >= "20261001-3", _sv.group(1) if _sv else None)
_m600 = media_bloklari(CSS, r"max-width:\s*600px")
check("S3 telefonda jadval — kartalar (`table.telefon-karta`): sarlavha yashirin, qator — karta, katak «nomi — qiymati» "
      "(`data-label`)",
      re.search(r"table\.telefon-karta\s*>\s*thead\s*\{\s*display:\s*none", _m600)
      and "content: attr(data-label)" in _m600 and re.search(r"\.kpi-grid\s*\{[^}]*repeat\(2,\s*minmax\(0,\s*1fr\)\)\s*!important", _m600),
      _m600[:300])
_jadvallar = sorted(f for f, t in TPL.items() if "telefon-karta" in t)


def tr_kataklari(matn, belgi):
    """`belgi` turgan `<tr …>…</tr>` bo'lagidagi `<td` teglari (data-label bilan / siz)."""
    i = matn.find(belgi)
    if i < 0:
        return None
    bosh, oxir = matn.rfind("<tr", 0, i), matn.find("</tr>", i)
    bolak = matn[bosh: oxir] if bosh >= 0 and oxir > 0 else ""
    tdlar = re.findall(r"<td\b[^>]*>", bolak)
    return len(tdlar), [x[:50] for x in tdlar if "data-label" not in x]


_users = tr_kataklari(TPL.get("users.html", ""), 'data-label="Login"')
_fin = tr_kataklari(TPL.get("finance.html", ""), 'data-label="Sana"')
check("S4 `telefon-karta` jadvallari (Moliya — tranzaksiyalar, Foydalanuvchilar): har katakda `data-label` (telefonda katak "
      "nomi — «Sana», «Summa», «Login», «Rol» …)",
      set(_jadvallar) >= {"finance.html", "users.html"} and _users and _users[0] >= 7 and not _users[1]
      and _fin and _fin[0] >= 7 and not _fin[1], [_jadvallar, _users, _fin])
check("S5 rasm qo'shish belgisi (kamera) sichqonchasiz qurilmada / tor ekranda doim ko'rinadi (`hover: none`)",
      re.search(r"@media\s*\(hover:\s*none\)[^{]*\{[^}]*\.cam-overlay[^}]*opacity:\s*1\s*!important", CSS), None)
check("S6 Tayyor mahsulotlar raqam kartalari telefonda bitta tasma (`.fp-stat-tasma` — yon tomonga suriladi)",
      'class="stat-grid fp-stat-tasma' in TPL.get("finished.html", "")
      and re.search(r"\.fp-stat-tasma\s*\{[^}]*overflow-x:\s*auto", TPL.get("finished.html", "")), None)
check("S7 Buyurtmalar: telefonda bitta ustun tartibi (ro'yxat → xulosa va AMALLAR → tafsilot) va tanlanganda xulosaga surish",
      ".ord-layout > .right-panel{order:2}" in TPL.get("orders.html", "") and "function tanlanganXulosagaSur()" in TPL.get("orders.html", "")
      and "function qarzTafsilotigaSur(" in TPL.get("debts.html", ""), None)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Ma'lumot zanjiri (brauzerda, dasturning O'Z API si orqali — `work/k112z/zanjir_c.js` va `mrp_namuna.js` dan; o'lchov
# `work/k125/telefon.py` bilan AYNAN ma'lumot)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ZANJIR_JS = r"""async (K) => {
  const m = K.m;
  const L = [];
  const I = {};
  const so = async (usul, url, tana, forma) => {
    const o = {method: usul, cache: 'no-store', credentials: 'same-origin'};
    if (forma) {
      const fd = new FormData();
      Object.entries(forma).forEach(([k, v]) => fd.append(k, v));
      o.body = fd;
    } else if (tana !== undefined) {
      o.headers = {'Content-Type': 'application/json'};
      o.body = JSON.stringify(tana);
    }
    let r;
    try { r = await fetch(url, o); } catch (e) { return {st: 599, t: String(e), j: null}; }
    const t = await r.text();
    let j = null;
    try { j = JSON.parse(t); } catch (e) { j = null; }
    return {st: r.status, t, j};
  };
  const q = async (nom, usul, url, tana, forma) => { const r = await so(usul, url, tana, forma); L.push([nom, r.st, String(r.t || '').slice(0, 200)]); return r; };
  const ok = r => r && r.st >= 200 && r.st < 300;
  const skip = nom => { L.push([nom, 'SKIP', 'oldingi qadam yiqilgan']); return null; };
  const qs = o => Object.entries(o).map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(v)).join('&');
  const idOf = r => {
    if (!(ok(r) && r.j)) return null;
    const j = r.j;
    for (const k of ['id', 'delivery_id', 'product_id', 'receipt_id', 'sale_id', 'loss_id']) if (j[k] != null) return j[k];
    for (const k of ['production_order', 'item', 'order']) if (j[k] && j[k].id != null) return j[k].id;
    return null;
  };
  // 1. Ombor: materiallar (+ rasm), ta'minotchi, kirim
  const mat = async (kalit, tana) => { const r = await q('material_' + kalit, 'POST', '/api/inventory', tana); I[kalit] = idOf(r); return r; };
  await mat('peno', {item_name: m + ' Penoplast 15', category: 'Penoplast', unit: 'blok', stock_quantity: 0, min_stock: 0,
                     is_penoplast: true, is_default_penoplast: true, volume_per_unit: 1.0});
  // uzun nom — telefonda nom qisqartirilmay o'ralishi tekshiriladi (retsept tarkibi, ombor, kirim)
  await mat('kley', {item_name: m + ' Kley akril (oq, ichki va tashqi ishlar uchun)', category: "Kimyoviy qo'shimchalar", unit: 'kg', stock_quantity: 0, min_stock: 50,
                     is_penoplast: false, is_default_penoplast: false, volume_per_unit: 1.0});
  await mat('qum', {item_name: m + ' Qum', category: 'Qattiq qotishmalar', unit: 'kg', stock_quantity: 0, min_stock: 100,
                    is_penoplast: false, is_default_penoplast: false, volume_per_unit: 1.0});
  await mat('setka', {item_name: m + ' Setka', category: 'Boshqa', unit: 'dona', stock_quantity: 0, min_stock: 0,
                      is_penoplast: false, is_default_penoplast: false, volume_per_unit: 1.0});
  if (I.kley) {
    const b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
    const bin = atob(b64); const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    const fd = new FormData(); fd.append('file', new Blob([u8], {type: 'image/png'}), m + '_rasm.png');
    let st = 599, t = '';
    try { const r = await fetch('/api/inventory/' + I.kley + '/image', {method: 'POST', body: fd, credentials: 'same-origin'}); st = r.status; t = await r.text(); } catch (e) { t = String(e); }
    L.push(['material_rasm', st, t.slice(0, 120)]);
  }
  const sup = await q('taminotchi', 'POST', '/api/suppliers', {name: m + ' Taminotchi', phone: '+998900001120', notes: m + ' taminotchi izohi'});
  I.sup = idOf(sup);
  if (I.sup && I.peno && I.kley && I.qum && I.setka) {
    await q('kirim', 'POST', '/api/inventory/receipt', {
      items: [{inventory_id: I.peno, quantity: 10, price_per_unit: 600000, volume_per_unit: 1.0, notes: m + ' peno qatori'},
              {inventory_id: I.kley, quantity: 200, price_per_unit: 3000},
              {inventory_id: I.qum, quantity: 500, price_per_unit: 800},
              {inventory_id: I.setka, quantity: 50, price_per_unit: 2500}],
      supplier_id: I.sup, document_number: m + '-KIRIM-1', paid_now: 3000000, transport_cost: 150000, tushirish_cost: 50000,
      yuklash_cost: 0, boshqa_cost: 0, add_to_cost: true, notes: m + ' kirim hujjati', production_type: 'umumiy'});
  } else { skip('kirim'); }
  // 2. Qoplama retsepti, usta, hodim, loyiha
  if (I.kley && I.qum) {
    const rc = await q('retsept', 'POST', '/api/recipes', {name: m + ' Qoplama', batch_size_kg: 100, notes: m + ' retsept izohi',
      ingredients: [{inventory_id: I.kley, quantity_kg: 30}, {inventory_id: I.qum, quantity_kg: 70}]});
    I.retsept = idOf(rc);
  } else { skip('retsept'); }
  I.usta = idOf(await q('usta', 'POST', '/api/masters', {name: m + ' Usta', phone: '+998900001121', cashback_percent: 5, kpi_percent: 0,
                                                         region: 'Andijon', notes: m + ' usta izohi'}));
  I.hodim = idOf(await q('hodim', 'POST', '/api/employees', {name: m + ' Hodim', position: 'Kesuvchi', pay_type: 'fixed', fixed_amount: 3000000,
                                                            production_type: 'umumiy', notes: m + ' hodim izohi'}));
  I.loyiha = idOf(await q('loyiha', 'POST', '/api/projects', {project_name: m + ' Loyiha', client_name: m + ' Mijoz', client_phone: '+998900001122',
                                                            client_address: 'Andijon, ' + m, description: m + ' tavsif', notes: m + ' loyiha izohi'}));
  // 3. MRP: mahsulot turi, retsept (BOM), omborga ishlab chiqarish
  I.tur = idOf(await q('mrp_tur', 'POST', '/api/production/product-types', {name: m + ' Travertin', unit: 'm2', input_template: 'quantity_only',
                                                                          pricing_formula: 'unit_based', supports_coating: false, notes: m + ' tur izohi'}));
  if (I.tur && I.qum && I.kley && I.setka) {
    I.bom = idOf(await q('mrp_bom', 'POST', '/api/production/boms', {product_type_id: I.tur, variant_name: m + ' Standart', batch_quantity: 1,
      notes: m + ' bom izohi',
      items: [{inventory_id: I.qum, component_type: 'raw_material', quantity: 5, scrap_factor_percent: 0, is_optional: false, is_coating: false},
              {inventory_id: I.kley, component_type: 'raw_material', quantity: 1, scrap_factor_percent: 10, is_optional: false, is_coating: false},
              {inventory_id: I.setka, component_type: 'packaging', quantity: 1, scrap_factor_percent: 0, is_optional: false, is_coating: false}]}));
  } else { skip('mrp_bom'); }
  const poIsh = async (nom, tana) => {
    const id = idOf(await q(nom + '_yaratish', 'POST', '/api/production/orders', tana));
    if (!id) { skip(nom + '_ishlash'); return null; }
    const s = await q(nom + '_boshlash', 'POST', '/api/production/orders/' + id + '/start');
    if (ok(s)) await q(nom + '_yakunlash', 'POST', '/api/production/orders/' + id + '/complete');
    return id;
  };
  if (I.tur && I.bom) {
    I.po_ombor = await poIsh('mrp_ombor', {product_type_id: I.tur, bom_id: I.bom, quantity: 4, source_type: 'warehouse_stock', notes: m + ' PO ombor'});
  } else { skip('mrp_ombor'); }
  // 4. Buyurtmalar: zaklat, yetkazish, to'lov, «Tayyor», qaytarish (qarz qoladi — Qarzdorlar)
  const buyurtma = async (nom, tana) => {
    let r = await q(nom, 'POST', '/api/orders', tana);
    if (r.st === 409 && r.j && r.j.detail && r.j.detail.type === 'stock_shortage_warning') r = await q(nom + '_tasdiq', 'POST', '/api/orders?confirm_shortage=true', tana);
    return r;
  };
  const holatQ = async (oid) => { const r = await so('GET', '/api/orders/' + oid + '/delivery-status'); return (r.j && r.j.items) || []; };
  const yetkaz = async (nom, oid, detallar, qosh) => {
    const h = await holatQ(oid);
    const items = h.filter(x => detallar.includes(x.id) && x.remaining > 0.0001).map(x => ({order_item_id: x.id, quantity: x.remaining}));
    if (!items.length) { L.push([nom, 'SKIP', "qolgan miqdor yo'q"]); return null; }
    return await q(nom, 'POST', '/api/deliveries', Object.assign({order_id: oid, items}, qosh));
  };
  const birlik = async (oid, iid) => { const h = await holatQ(oid); const x = h.find(y => y.id === iid); return x ? x.unit : 'dona'; };
  if (I.loyiha && I.peno && I.retsept) {
    const o1 = await buyurtma('buyurtma1', {project_id: I.loyiha, order_type: 'product', recipe_id: I.retsept, master_id: I.usta || null,
      deadline: K.muddat, is_draft: false, base_price: 600000, loy_kg: 20,
      items: [{name: m + ' Karniz', category: 'profil', width: 20, thickness: 15, length: 30, quantity: 1, unit_price: 540000, is_coated: true,
               penoplast_id: I.peno, price_per_m3: null, finished_product_id: null, sub_details: []},
              {name: m + ' Panel', category: 'panel', width: 60, thickness: 5, length: 0, quantity: 20, unit_price: 18000, is_coated: false,
               penoplast_id: I.peno, price_per_m3: null, finished_product_id: null}]});
    I.o1 = idOf(o1);
    if (I.o1) {
      const it = (o1.j.items || []).slice().sort((a, b) => a.id - b.id);
      const karniz = it[0] && it[0].id, panel = it[1] && it[1].id;
      await q('zaklat', 'POST', '/api/payments', {order_id: I.o1, amount: 200000, payment_type: 'zaklat', payment_method: 'naqd', notes: 'Buyurtma yaratilganda'});
      await yetkaz('yetkazish1', I.o1, [karniz], {received_by: m + ' Qabul', notes: m + ' yuk 1', transport_carrier: m + ' Tashuvchi',
        transport_cost: 60000, transport_payer: 'company', payment_amount: 300000, payment_method: 'naqd'});
      await q('tolov', 'POST', '/api/payments', {order_id: I.o1, amount: 100000, payment_type: 'partial', payment_method: 'plastik', notes: m + ' tolov'});
      await yetkaz('yetkazish2', I.o1, [panel], {received_by: m + ' Qabul 2', notes: m + ' yuk 2', transport_carrier: '',
        transport_cost: 0, transport_payer: 'none', payment_method: 'naqd'});
      await q('tayyor1', 'POST', '/api/orders/' + I.o1 + '/ready');
      const qt = await q('qaytarish', 'POST', '/api/returns', {order_id: I.o1, order_item_id: panel, item_name: m + ' Panel', quantity: 2,
        unit: await birlik(I.o1, panel), reason: "Notog'ri o'lcham", refund_amount: 0, to_stock: true, notes: m + ' qaytarish', coating_applied: false});
      const qid = idOf(qt);
      if (qid) await q('qaytarish_pul', 'POST', '/api/returns/' + qid + '/refund');
      await q('buyurtma1_pin', 'POST', '/api/orders/' + I.o1 + '/pin');
    } else { skip('buyurtma1_davomi'); }
  } else { skip('buyurtma1'); }
  if (I.loyiha && I.peno && I.retsept && I.tur) {
    const o2 = await buyurtma('buyurtma2', {project_id: I.loyiha, order_type: 'product', recipe_id: null, master_id: I.usta || null,
      deadline: K.muddat, is_draft: false, base_price: 600000, loy_kg: null,
      items: [{name: m + ' Dona', category: 'dona', width: null, thickness: null, length: null, quantity: 50, unit_price: 5000,
               unit_price_for_volume: 5000, is_coated: false, penoplast_id: I.peno, price_per_m3: null, finished_product_id: null, notes: null},
              {name: m + ' Loy', category: 'loy_sotish', width: null, thickness: null, length: null, quantity: 10, unit_price: 8000, is_coated: false,
               penoplast_id: null, price_per_m3: null, finished_product_id: null, recipe_id: I.retsept},
              {name: m + ' Travertin', category: 'mrp_product', width: null, thickness: null, length: null, quantity: 5, unit_price: 90000,
               is_coated: false, penoplast_id: null, price_per_m3: null, finished_product_id: null, product_type_id: I.tur}]});
    I.o2 = idOf(o2);
    if (I.o2) {
      const it = (o2.j.items || []).slice().sort((a, b) => a.id - b.id);
      const dona = it[0] && it[0].id, loy = it[1] && it[1].id, trav = it[2] && it[2].id;
      await q('zaklat2', 'POST', '/api/payments', {order_id: I.o2, amount: 150000, payment_type: 'zaklat', payment_method: "o'tkazma", notes: m + ' zaklat 2'});
      await q('brak', 'POST', '/api/returns', {order_id: I.o2, order_item_id: dona, item_name: m + ' Dona', quantity: 3,
        unit: await birlik(I.o2, dona), reason: 'Brak', refund_amount: 0, to_stock: false, notes: m + ' brak', coating_applied: false,
        brak_bosqich: 'kesish', brak_sabab: 'ishchi', ...(I.hodim ? {brak_javobgar_id: I.hodim} : {})});
      if (I.bom && trav) {
        await poIsh('mrp_buyurtma', {product_type_id: I.tur, bom_id: I.bom, quantity: 5, source_type: 'customer_order',
          source_order_id: I.o2, source_order_item_id: trav, notes: m + ' PO buyurtma'});
      } else { skip('mrp_buyurtma'); }
      await yetkaz('yetkazish3', I.o2, [dona, loy, trav], {received_by: m + ' Qabul 3', notes: m + ' yuk 3',
        transport_carrier: m + ' Tashuvchi 2', transport_cost: 40000, transport_payer: 'client', payment_amount: 250000, payment_method: 'naqd'});
      await q('tayyor2', 'POST', '/api/orders/' + I.o2 + '/ready');
    } else { skip('buyurtma2_davomi'); }
  } else { skip('buyurtma2'); }
  // 5. Tayyor mahsulot
  if (I.peno) {
    await q('tm_yaratish', 'POST', '/api/finished/produce', {name: m + ' Tayyor karniz', category: 'profil', is_coated: false,
      penoplast_id: I.peno, price_per_m3: null, unit_price: 25000, recipe_id: null, notes: m + ' tm izohi', width: 10, thickness: 10, length: 10, quantity: 5});
    const royxat = await so('GET', '/api/finished');
    const tm = (Array.isArray(royxat.j) ? royxat.j : []).find(x => x.name === m + ' Tayyor karniz');
    if (tm) await q('tm_tayyor', 'POST', '/api/finished/' + tm.id + '/complete');
    else skip('tm_tayyor');
  } else { skip('tm_yaratish'); }
  // 6. Moliya, ta'minotchiga to'lov, majburiyat («har oy 5-kunigacha»)
  await q('xarajat', 'POST', '/api/finance/transactions', {date: K.sana + 'T00:00:00', category: 'Boshqa', amount: 150000, notes: m + ' xarajat',
                                                          production_type: 'umumiy'});
  await q('transport', 'POST', '/api/transport-expenses', {amount: 70000, materials_note: m + ' yuk', notes: m + ' transport', production_type: 'umumiy'});
  if (I.sup) await q('taminotchi_tolov', 'POST', '/api/suppliers/' + I.sup + '/payment', {supplier_id: I.sup, amount: 1000000, notes: m + ' taminotchiga'});
  await q('majburiyat', 'POST', '/api/obligations/recurring?' + qs({category: 'ctel_ijara', label: m + ' Ijara', monthly_target: '500000',
                                                                    icon: '\u{1F3E0}', due_day: '5'}));
  // 7. MRP namunalari (bir necha tur va partiya — Tayyor mahsulotlar ro'yxati, Ishlab chiqarish)
  const post = (u, b) => so('POST', u, b);
  const mat2 = async (n, u, s, p, k) => idOf(await q('mrp_material', 'POST', '/api/inventory', Object.assign({item_name: n, unit: u, stock_quantity: s, price_per_unit: p}, k || {})));
  const M = {qum: await mat2('Qum (mayda)', 'kg', 5000, 820), kley: await mat2('Kley (akril)', 'kg', 500, 3150),
             setka: await mat2("Setka (to'r)", 'm²', 1000, 2600), sement: await mat2('Sement M400', 'qop', 100, 60000, {base_unit: 'kg', conversion_factor: 50})};
  const tur = async (n, u, sh, f) => idOf(await q('mrp_tur2', 'POST', '/api/production/product-types', {name: n, unit: u, input_template: sh, pricing_formula: f, supports_coating: false}));
  const T = {trav: await tur('Travertin', 'm²', 'quantity_only', 'unit_based'), ustun: await tur('Ustun', 'dona', 'dimensional_3d', 'volume_based')};
  const ret = async (pt, n, items) => idOf(await q('mrp_bom2', 'POST', '/api/production/boms', {product_type_id: pt, variant_name: n, batch_quantity: 1, items}));
  if (M.qum && M.kley && M.setka && M.sement && T.trav && T.ustun) {
    const BM = {trav: await ret(T.trav, 'Standart', [{inventory_id: M.qum, quantity: 5}, {inventory_id: M.kley, quantity: 1, scrap_factor_percent: 10},
                   {inventory_id: M.setka, quantity: 1, scrap_factor_percent: 5}]),
                ustun: await ret(T.ustun, 'Ø 30 sm', [{inventory_id: M.qum, quantity: 20}, {inventory_id: M.kley, quantity: 6}, {inventory_id: M.sement, quantity: 10}])};
    for (const [t, b, n] of [['trav', 'trav', 40], ['ustun', 'ustun', 8], ['trav', 'trav', 30]]) {
      if (BM[b]) await poIsh('mrp_namuna_' + t, {product_type_id: T[t], bom_id: BM[b], quantity: n, source_type: 'warehouse_stock'});
    }
  } else { skip('mrp_namuna'); }
  const yiqilgan = L.filter(x => !(typeof x[1] === 'number' && x[1] >= 200 && x[1] < 300));
  return {L, I, yiqilgan};
}"""

# Chart.js o'rinbosari (tashqi tarmoq yo'q; grafik kartalarining o'lchami shablonda qat'iy — joylashuvga ta'sir qilmaydi)
CHART_ORINBOSAR = r"""(function () {
  // haqiqiy Chart.js kabi (`responsive`): canvas o'z qutisining kengligida (balandligi — qutiniki yoki kenglikning yarmi)
  function Chart(ctx, cfg) { this.ctx = ctx; this.config = cfg || {}; this.data = (cfg && cfg.data) || {datasets: []};
    this.options = (cfg && cfg.options) || {}; this.canvas = ctx && ctx.canvas ? ctx.canvas : ctx;
    const c = this.canvas;
    if (c && c.style && c.parentElement) { const p = c.parentElement; const w = p.clientWidth; const h = p.clientHeight || Math.round(w / 2);
      c.style.display = 'block'; c.style.boxSizing = 'border-box'; c.style.width = w + 'px'; c.style.height = h + 'px'; } }
  Chart.prototype.destroy = function () {};
  Chart.prototype.update = function () {};
  Chart.prototype.resize = function () {};
  Chart.prototype.render = function () {};
  Chart.defaults = {color: '#666', borderColor: '#ddd', font: {}, plugins: {legend: {labels: {}}, tooltip: {}}, scale: {grid: {}, ticks: {}}};
  Chart.register = function () {};
  window.Chart = Chart;
})();"""

# Ekrandan chiqqan (o'ngda / chapda) ko'rinadigan elementlar: ataylab suriladigan tasmalar (karusel) va O'Z qutisi ichida
# yon tomonga suriladigan tor (ekran kengligining < 85 %) jadval o'ramlari hisobga olinmaydi; sahifa darajasidagi o'ram
# (≥ 85 %) gorizontal toshsa — `sahifa_yon`.
OLCH_JS = r"""() => {
  const vw = innerWidth; const CS = e => getComputedStyle(e);
  const RUXSAT = '#topGrid, .fp-stat-tasma';
  const vis = e => { const r = e.getBoundingClientRect(); const s = CS(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'; };
  const sel = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/)[0] : '');
  const tor_surish = e => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const o = CS(p).overflowX;
    if ((o === 'auto' || o === 'scroll') && p.clientWidth < vw * 0.85) return true; } return false; };
  const hammasi = [...document.querySelectorAll('body *')].filter(e => vis(e) && CS(e).position !== 'fixed' && !e.closest('.sidebar, .erp-sidebar')
    && !e.closest(RUXSAT) && !e.closest('.modal-overlay'));
  const chiq = hammasi.filter(e => { const r = e.getBoundingClientRect(); return (r.right > vw + 1 || r.left < -1) && !tor_surish(e); });
  const ichki = chiq.filter(e => !chiq.some(x => x !== e && e.contains(x)))
    .map(e => sel(e) + ' [' + Math.round(e.getBoundingClientRect().left) + '..' + Math.round(e.getBoundingClientRect().right) + '] '
         + ((e.innerText || e.value || '') + '').trim().replace(/\s+/g, ' ').slice(0, 24));
  const orama = [...document.querySelectorAll('body *')].filter(e => { const s = CS(e); return (s.overflowX === 'auto' || s.overflowX === 'scroll')
    && e.clientWidth >= vw * 0.85 && e.scrollWidth > e.clientWidth + 2 && vis(e) && !e.matches(RUXSAT) && !e.closest('.sidebar, .erp-sidebar'); })
    .map(e => sel(e) + ' ' + e.clientWidth + '/' + e.scrollWidth);
  return {chiqqan: ichki.slice(0, 8), sahifa_yon: orama.slice(0, 6), hujjat: document.documentElement.scrollWidth, vw};
}"""

# Ochiq oyna (selektor — `.modal-overlay` yoki sahifaning o'z oynasi) ichida ekrandan chiqqan element (o'z qutisida suriladigan
# tor jadvaldan tashqari)
OYNA_JS = r"""(sel) => {
  const vw = innerWidth; const CS = e => getComputedStyle(e);
  const tor_surish = e => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const o = CS(p).overflowX;
    if ((o === 'auto' || o === 'scroll') && p.clientWidth < vw * 0.85) return true; } return false; };
  const oy = [...document.querySelectorAll(sel)].filter(e => { const s = CS(e); const r = e.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0' && r.width > 0 && r.height > 0; });
  const chiq = oy.flatMap(o => [...o.querySelectorAll('*')]).filter(e => { const r = e.getBoundingClientRect(); const s = CS(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && (r.right > vw + 1 || r.left < -1) && !tor_surish(e); });
  return {oyna: oy.map(e => e.id || e.className), chiqqan: chiq.filter(e => !chiq.some(x => x !== e && e.contains(x)))
    .map(e => e.tagName.toLowerCase() + '.' + String(e.className || '').split(' ')[0] + ' [' + Math.round(e.getBoundingClientRect().left) + '..'
         + Math.round(e.getBoundingClientRect().right) + '] ' + ((e.innerText || e.value || '') + '').trim().replace(/\s+/g, ' ').slice(0, 24)).slice(0, 8)};
}"""

# Konteyner bolalari telefonda USTMA-UST (har biri butun kenglikda): {w, bolaklar: [[chap, tepa, kenglik], ...]}
USTMA_JS = r"""(s) => { const g = document.querySelector(s); if (!g || g.offsetParent === null) return null;
                    const b = [...g.children].filter(e => e.offsetParent !== null).map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width)]; });
                    return {w: g.clientWidth, bolaklar: b}; }"""

KESILMAGAN_JS = r"""(s) => [...document.querySelectorAll(s)].filter(e => e.offsetParent !== null).map(e => ({
  t: (e.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40), w: e.clientWidth, sw: e.scrollWidth, h: e.clientHeight, sh: e.scrollHeight,
  kesik: e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 2}))"""

SAHIFALAR = ["/", "/dashboard", "/projects", "/orders", "/inventory", "/suppliers", "/suppliers/receive", "/recipes", "/production",
             "/finished", "/returns", "/debts", "/finance", "/kunlik-xarajat", "/kpi", "/ustalar", "/reports", "/users"]

ADMIN, PAROL = "ctel_admin", "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, ADMIN, PAROL, UserRole.ADMIN, "Namuna Dekor", company_id=1)
s.close()

section("M. Ma'lumot — brauzerda dasturning o'z API si orqali to'liq ish zanjiri")
try:
    from playwright.sync_api import sync_playwright
    PW_BOR = True
except Exception as _e:                    # noqa: BLE001
    PW_BOR = False
    _pw_xato = f"{type(_e).__name__}: {_e}"
check("M0 Python `playwright` bor (HAQIQIY brauzer o'lchovi shart — C bosqichi taxmin bilan emas, o'lchov bilan)", PW_BOR,
      None if PW_BOR else _pw_xato)

import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


NAT = {}
if PW_BOR:
    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    check("M1 lokal server ishga tushdi", server.started)
    B = f"http://127.0.0.1:{port}"
    tk = datetime.utcnow() + timedelta(hours=5)
    K = {"m": "Namuna", "sana": tk.strftime("%Y-%m-%d"), "yil": tk.year, "oy": tk.month,
         "muddat": (tk + timedelta(days=9)).strftime("%Y-%m-%d")}

    def yonalish(route):
        u = route.request.url
        if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
            return route.fulfill(status=200, content_type="application/javascript", body=CHART_ORINBOSAR)
        if u.startswith("https://fonts.googleapis.com/"):
            return route.fulfill(status=200, content_type="text/css", body="")
        return route.fulfill(status=204, body="")

    def balandlik(w):
        return 900 if w >= 1000 else (844 if w >= 380 else 740)

    with sync_playwright() as pw:
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                  "chrome-linux", "chrome"))):
            _exe = _yol
        try:
            br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()
        except Exception as _e:            # noqa: BLE001
            br = None
            check("M2 Chromium ishga tushdi", False, f"{type(_e).__name__}: {_e}")

        def kontekst(w):
            _tel = w < 1000      # telefon — sensorli ekran (`hover: none`); kompyuter — sichqoncha
            ctx = br.new_context(viewport={"width": w, "height": balandlik(w)}, device_scale_factor=1, is_mobile=_tel, has_touch=_tel,
                                 timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                                 r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
            pg = ctx.new_page()
            pg.goto(B + "/login")
            pg.fill("input[name=username]", ADMIN)
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            return ctx, pg

        if br:
            ctx, pg = kontekst(390)
            check("M2 kirish (lokal sinov foydalanuvchisi) — bosh sahifa", "/login" not in pg.url, pg.url)
            try:
                Z = pg.evaluate(ZANJIR_JS, K)
            except Exception as _e:        # noqa: BLE001
                Z = {"yiqilgan": [["istisno", 0, str(_e)[:300]]], "L": [], "I": {}}
            ctx.close()
            check("M3 ish zanjiri: hamma qadam 2xx (ombor, kirim, retsept, usta, hodim, loyiha, 2 buyurtma, to'lov, yetkazish, "
                  "qaytarish, brak, MRP, tayyor mahsulot, moliya, majburiyat)",
                  not Z.get("yiqilgan") and len(Z.get("L") or []) >= 50, [Z.get("yiqilgan"), len(Z.get("L") or [])])

            def och(pg, url, kut=700):
                pg.goto(B + url, wait_until="networkidle")
                pg.wait_for_timeout(kut)

            def js(pg, kod, arg=None):
                try:
                    return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
                except Exception as ex:    # noqa: BLE001
                    return {"js_xato": str(ex)[:300]}

            for w in (390, 360):
                R = NAT.setdefault(w, {})
                ctx, pg = kontekst(w)
                xs = []
                pg.on("pageerror", lambda e: xs.append(str(e)[:200]))
                # ── G: har sahifa ──
                for url in SAHIFALAR:
                    del xs[:]
                    och(pg, url)
                    R["G " + url] = {"o": js(pg, OLCH_JS), "xato": list(xs)}
                # ── T: ssenariylar ──
                del xs[:]
                och(pg, "/orders")
                js(pg, "() => { showNewForm(); addItem(); }")
                pg.wait_for_timeout(600)
                R["yangi"] = js(pg, """() => { const d = document.querySelector('.detal'); if (!d) return null; const vw = innerWidth;
                    const ich = [...d.querySelectorAll('input, select')].filter(e => e.offsetParent !== null && !['file', 'checkbox', 'radio', 'hidden'].includes(e.type));
                    return {soni: ich.length, chiqqan: ich.filter(e => e.getBoundingClientRect().right > vw + 1).map(e => e.className + ':' + Math.round(e.getBoundingClientRect().right)),
                            tor: ich.filter(e => e.getBoundingClientRect().width < 60).map(e => e.className + ':' + Math.round(e.getBoundingClientRect().width)),
                            ohl: ['i-h', 'i-w', 'i-l'].map(k => { const e = d.querySelector('.' + k); return e && e.offsetParent !== null ? Math.round(e.getBoundingClientRect().width) : null; })}; }""")
                R["yangi_o"] = js(pg, OLCH_JS)
                R["yangi_xato"] = list(xs)

                def buyurtma_tanla():
                    och(pg, "/orders")
                    js(pg, "() => { const g = document.querySelector('.proj-group:not(.open) .proj-head'); g && g.click(); }")
                    pg.wait_for_timeout(400)
                    try:
                        pg.click('.ord-list [id^="oi-"]', timeout=3000)
                    except Exception:      # noqa: BLE001
                        js(pg, "() => { const e = document.querySelector('.ord-list [id^=\"oi-\"]'); e && e.click(); }")
                    pg.wait_for_timeout(1200)
                del xs[:]
                buyurtma_tanla()
                R["tanlash"] = js(pg, """() => { const vh = innerHeight; const amal = [...document.querySelectorAll('#btn-ready, #btn-edit, #btn-duplicate')]
                      .filter(e => e.offsetParent !== null);
                    return {vh, amallar: amal.map(e => [e.id, Math.round(e.getBoundingClientRect().top), Math.round(e.getBoundingClientRect().bottom)]),
                            xulosa: (() => { const k = document.getElementById('sumCard'); return k && k.offsetParent !== null ? Math.round(k.getBoundingClientRect().top) : null; })()}; }""")
                R["tanlash_o"] = js(pg, OLCH_JS)
                R["tanlash_xato"] = list(xs)
                del xs[:]
                och(pg, "/debts")
                try:
                    pg.click('[onclick^="selectOrderDebt"]', timeout=3000)
                except Exception:          # noqa: BLE001
                    pass
                pg.wait_for_timeout(1000)
                R["qarz"] = js(pg, """() => { const vh = innerHeight; const e = document.getElementById('pay-amount');
                    const r = e && e.offsetParent !== null ? e.getBoundingClientRect() : null;
                    return {vh, maydon: r ? [Math.round(r.top), Math.round(r.bottom), Math.round(r.right)] : null}; }""")
                R["qarz_o"] = js(pg, OLCH_JS)
                # «Kompaniya o'zi qarzdor» (hodimlar, ta'minotchilar va boshqa majburiyatlar) — telefonda ustma-ust
                js(pg, "() => { try { switchTab('company'); } catch (e) {} }")
                pg.wait_for_timeout(500)
                R["qarz_kompaniya"] = js(pg, USTMA_JS, "#tab-company .dbt-ikki-ustun")
                R["qarz_kompaniya_o"] = js(pg, OLCH_JS)
                del xs[:]
                och(pg, "/projects")
                try:
                    pg.click('[onclick^="selectProj"]', timeout=3000)
                except Exception:          # noqa: BLE001
                    pass
                pg.wait_for_timeout(900)
                R["loyiha"] = js(pg, """() => { const vw = innerWidth; const m = [...document.querySelectorAll('#moneyRow > div')].filter(e => e.offsetParent !== null);
                    return {soni: m.length, chiqqan: m.filter(e => e.getBoundingClientRect().right > vw + 1 || [...e.querySelectorAll('*')].some(x => x.getBoundingClientRect().right > vw + 1))
                              .map(e => (e.innerText || '').replace(/\\s+/g, ' ').slice(0, 30))}; }""")
                R["loyiha_mijoz"] = js(pg, KESILMAGAN_JS, ".proj-client, .proj-name")
                R["loyiha_o"] = js(pg, OLCH_JS)
                R["loyiha_kamera"] = js(pg, "() => [...document.querySelectorAll('.proj-thumb-cam')].map(e => getComputedStyle(e).opacity)")
                js(pg, "() => { try { switchTab('timeline'); } catch (e) {} }")
                pg.wait_for_timeout(700)
                R["loyiha_tl_o"] = js(pg, OLCH_JS)
                del xs[:]
                och(pg, "/recipes")
                try:
                    pg.click('[onclick^="openEditModal"]', timeout=3000)
                except Exception:          # noqa: BLE001
                    pass
                pg.wait_for_timeout(900)
                R["retsept"] = js(pg, KESILMAGAN_JS, ".recp-ing-name")
                R["retsept_oyna"] = js(pg, OYNA_JS, "#editModal")
                del xs[:]
                och(pg, "/production")
                js(pg, """() => { const b = [...document.querySelectorAll('button')].find(x => /\\+ Tarkib/.test(x.innerText) && x.offsetParent !== null); b && b.click(); }""")
                pg.wait_for_timeout(900)
                R["tarkib"] = js(pg, """() => { const r = [...document.querySelectorAll('#bom-modal .bi-asosiy')].find(x => x.offsetParent !== null);
                    if (!r) return null; const q = s => { const e = r.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect();
                      return {d: getComputedStyle(e).display, t: (e.innerText || '').trim(), top: Math.round(b.top), bottom: Math.round(b.bottom), w: Math.round(b.width)}; };
                    return {lmiq: q('.bi-yorliq-miq'), lisr: q('.bi-yorliq-isr'), miq: q('.bi-guruh.miq'), isr: q('.bi-guruh.isr')}; }""")
                R["tarkib_oyna"] = js(pg, OYNA_JS, ".modal-overlay")
                R["tarkib_xato"] = list(xs)
                # G5-16: «Yangi qaytarish» oynasida rasm maydoni; tanlangan rasm saqlangan qaytarishga yuklanadi (faqat 390 px —
                # bir marta yozuv yaratiladi); oyna qayta ochilganda oldingi tanlov tozalanadi
                if w == 390:
                    del xs[:]
                    och(pg, "/returns")
                    js(pg, "() => { showAddModal(); }")
                    pg.wait_for_timeout(300)
                    R["qaytarish_maydon"] = js(pg, """() => { const e = document.getElementById('f-rasm'); if (!e) return null; const b = e.getBoundingClientRect();
                        const l = document.querySelector('label[for="f-rasm"]');
                        return {w: Math.round(b.width), right: Math.round(b.right), vw: innerWidth, accept: e.accept, yorliq: l ? l.textContent.trim() : null}; }""")
                    _png = os.path.join(_T, "qaytarish.png")
                    with open(_png, "wb") as _f:
                        _f.write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
                    try:
                        pg.set_input_files("#f-rasm", _png)
                        js(pg, "() => { closeModal(); showAddModal(); }")
                        pg.wait_for_timeout(200)
                        R["qaytarish_tozalandi"] = js(pg, "() => document.getElementById('f-rasm').files.length")
                        pg.set_input_files("#f-rasm", _png)
                        _oid = js(pg, """() => { const s = document.getElementById('f-order'); const o = [...s.options].find(x => x.value); return o ? o.value : null; }""")
                        pg.select_option("#f-order", _oid)
                        pg.wait_for_function("() => !document.getElementById('f-item').disabled && document.getElementById('f-item').options.length > 1", timeout=10000)
                        _iid = js(pg, """() => { const s = document.getElementById('f-item'); const o = [...s.options].find(x => x.value); return o ? o.value : null; }""")
                        pg.select_option("#f-item", _iid)
                        pg.fill("#f-qty", "0.5")
                        _oldin = js(pg, "async () => { const r = await fetch('/api/returns'); const j = await r.json(); return (Array.isArray(j) ? j : (j.items || [])).map(x => x.id); }")
                        with pg.expect_navigation(timeout=15000):
                            pg.click("#return-save-btn")
                        pg.wait_for_load_state("networkidle")
                        R["qaytarish_rasm"] = js(pg, """async (eski) => { const r = await fetch('/api/returns'); const j = await r.json(); const a = Array.isArray(j) ? j : (j.items || []);
                            const y = a.filter(x => !eski.includes(x.id)); return y.map(x => ({id: x.id, image_url: x.image_url || null})); }""", _oldin or [])
                    except Exception as _e:    # noqa: BLE001
                        R["qaytarish_rasm"] = {"istisno": f"{type(_e).__name__}: {str(_e)[:300]}"}
                    R["qaytarish_xato"] = list(xs)
                och(pg, "/finished")
                R["tayyor"] = js(pg, """() => { const e = [...document.querySelectorAll('.fp-row')].find(x => x.offsetParent !== null);
                    return {vh: innerHeight, birinchi: e ? Math.round(e.getBoundingClientRect().top) : null,
                            kamera: [...document.querySelectorAll('.cam-overlay')].filter(x => x.closest('.fp-row')).map(x => getComputedStyle(x).opacity)}; }""")
                och(pg, "/inventory")
                R["ombor"] = js(pg, """() => { const vw = innerWidth; const r = [...document.querySelectorAll('.mat-row')].find(x => x.offsetParent !== null);
                    if (!r) return null;
                    const ustun = s => { const e = r.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect();
                      return {display: getComputedStyle(e).display, yorliq: getComputedStyle(e, '::before').content, w: Math.round(b.width),
                              ichida: b.width > 0 && b.right <= vw + 1 && b.left >= -1, matn: (e.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 30)}; };
                    return {chegara: ustun('.mat-col-min'), narx: ustun('.mat-col-updated'),
                            kamera: [...document.querySelectorAll('.mat-thumb-cam')].map(x => getComputedStyle(x).opacity)}; }""")
                och(pg, "/finance")
                R["moliya"] = js(pg, """() => { const vw = innerWidth; const l = document.getElementById('revDonutLegend');
                    if (!l || l.offsetParent === null) return null; const q = [...l.children];
                    return {qator: q.length, chiqqan: [...l.querySelectorAll('*')].filter(e => e.getBoundingClientRect().right > vw + 1).map(e => (e.innerText || '').slice(0, 20))}; }""")
                R["moliya_jadval"] = js(pg, """() => { const t = document.querySelector('table.telefon-karta'); if (!t) return null;
                    const tr = t.querySelector('tbody tr'); return {thead: getComputedStyle(t.querySelector('thead')).display, tr: tr ? getComputedStyle(tr).display : null}; }""")
                och(pg, "/kpi")
                R["kpi"] = js(pg, """() => { const vw = innerWidth; const i = document.getElementById('ehson-percent-input'); if (!i) return null;
                    const q = i.closest('.card-body'); return [...q.querySelectorAll('input, button')].map(e => [e.tagName, Math.round(e.getBoundingClientRect().left), Math.round(e.getBoundingClientRect().right), vw]); }""")
                och(pg, "/reports", 1500)
                R["reyting"] = js(pg, KESILMAGAN_JS, ".bi-top-name")
                R["jadval_amal"] = js(pg, """() => { const q = document.querySelector('.bi-jadval-amallar'); if (!q || q.offsetParent === null) return null;
                    const s = q.querySelector('#tableSearch'); const vw = innerWidth;
                    return {w: q.clientWidth, qidiruv: s ? Math.round(s.getBoundingClientRect().width) : null,
                            tugmalar: [...q.querySelectorAll('button, a')].filter(e => e.offsetParent !== null).map(e => [Math.round(e.getBoundingClientRect().left), Math.round(e.getBoundingClientRect().right), vw])}; }""")
                och(pg, "/")
                R["sarlavha"] = js(pg, KESILMAGAN_JS, ".tb-left .page-title")
                R["menyu"] = js(pg, """() => { const s = document.querySelector('.sidebar'); if (!s) return null; const yopiq = getComputedStyle(s).boxShadow;
                    try { toggleSidebar(); } catch (e) {} return new Promise(res => setTimeout(() => { const ochiq = getComputedStyle(s).boxShadow;
                    const ochildi = s.classList.contains('sidebar-open'); try { toggleSidebar(); } catch (e) {}
                    res({yopiq, ochiq, ochildi, yopildi: !s.classList.contains('sidebar-open')}); }, 400)); }""")
                och(pg, "/dashboard", 1200)
                R["majburiyat"] = js(pg, KESILMAGAN_JS, ".majburiyat-nom, #obligList div > span:first-of-type")
                R["dash_ikki"] = js(pg, USTMA_JS, ".dash-grid2")
                ctx.close()
            # kompyuter (1280 px): Hisobotlar reytinglari — uzun material nomi o'z ustunini kengaytirmaydi (4 ustun teng)
            ctx, pg = kontekst(1280)
            och(pg, "/reports", 1500)
            NAT["kompyuter"] = {"reyting": js(pg, """() => { const g = document.querySelector('.bi-top-grid'); if (!g) return null;
                const k = [...g.children].filter(e => e.offsetParent !== null).map(e => Math.round(e.getBoundingClientRect().width));
                const n = [...g.querySelectorAll('.bi-top-name')].map(e => (e.textContent || '').trim()).filter(x => x.length >= 40);
                return {kenglik: k, uzun_nom: n.slice(0, 2), sahifa: document.documentElement.scrollWidth, vw: innerWidth}; }""")}
            ctx.close()
            br.close()
    server.should_exit = True
    th.join(timeout=10)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. Har sahifa 390 / 360 px da: ekrandan chiqqan element yo'q, sahifa yon tomonga surilmaydi, JS xatosi yo'q")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
for w in (390, 360):
    R = NAT.get(w) or {}
    _yomon, _xato = {}, {}
    for url in SAHIFALAR:
        g = R.get("G " + url) or {}
        o = g.get("o") or {}
        if not isinstance(o, dict) or "chiqqan" not in o or o.get("chiqqan") or o.get("sahifa_yon") or (o.get("hujjat") or 0) > w + 1:
            _yomon[url] = o
        if g.get("xato"):
            _xato[url] = g["xato"][:2]
    check(f"G1 {w} px: {len(SAHIFALAR)} sahifaning hech birida ekrandan chiqqan element yo'q (ataylab suriladigan karusel / tasma "
          f"va o'z qutisidagi keng jadval — hisobga olinmaydi), hujjat kengligi ≤ ekran", R and not _yomon, _yomon)
    check(f"G2 {w} px: sahifalarda JS xatosi yo'q", R and not _xato, _xato)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Topilmalar bo'yicha ssenariylar (390 va 360 px)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
for w in (390, 360):
    R = NAT.get(w) or {}
    y = R.get("yangi") or {}
    check(f"T1 {w} px (G2-02) yangi buyurtma: detal maydonlari ≥ 60 px («Eni», «Kengligi», «Uzunlik» — ilgari 26 px), hech biri "
          f"ekrandan chiqmaydi; forma sahifani kengaytirmaydi",
          isinstance(y, dict) and y.get("soni", 0) >= 5 and not y.get("tor") and not y.get("chiqqan")
          and all(v and v >= 60 for v in (y.get("ohl") or [None])) and not (R.get("yangi_o") or {}).get("chiqqan")
          and not R.get("yangi_xato"), [y, R.get("yangi_o"), R.get("yangi_xato")])
    t = R.get("tanlash") or {}
    _am = t.get("amallar") or []
    check(f"T2 {w} px (G2-21) buyurtma tanlanganda xulosa va amallar (Tayyor / Tahrirlash / Nusxa) EKRANDA (ilgari ~2 000 px "
          f"pastda); sahifa yon tomonga surilmaydi",
          _am and all(0 <= a[1] and a[2] <= t.get("vh", 0) for a in _am) and not (R.get("tanlash_o") or {}).get("chiqqan")
          and not (R.get("tanlash_o") or {}).get("sahifa_yon") and not R.get("tanlash_xato"),
          [t, R.get("tanlash_o"), R.get("tanlash_xato")])
    qz = R.get("qarz") or {}
    check(f"T3 {w} px (G3-08) qarzdor tanlanganda «To'lov qabul qilish» summasi maydoni ekranda (ilgari 1 390 px da)",
          qz.get("maydon") and 0 <= qz["maydon"][0] and qz["maydon"][1] <= qz.get("vh", 0) and qz["maydon"][2] <= w + 1
          and not (R.get("qarz_o") or {}).get("chiqqan"), [qz, R.get("qarz_o")])
    qk = R.get("qarz_kompaniya") or {}
    _bq = qk.get("bolaklar") or []
    check(f"T16 {w} px (G3-08) Qarzdorlar «Kompaniya o'zi qarzdor»: hodimlar va ta'minotchilar bloklari USTMA-UST, har biri butun "
          f"kenglikda (ilgari ikki ustun, har biri ~170 px); ekrandan chiqqan element yo'q",
          len(_bq) >= 2 and all(b[2] >= qk.get("w", 0) * 0.9 for b in _bq) and _bq[1][1] > _bq[0][1]
          and not (R.get("qarz_kompaniya_o") or {}).get("chiqqan"), [qk, R.get("qarz_kompaniya_o")])
    lo = R.get("loyiha") or {}
    _mj = R.get("loyiha_mijoz") or []
    check(f"T4 {w} px (G2-18) loyiha tanlanganda «Loyiha qiymati / To'langan / Qolgan to'lov» ekranda (ilgari «Qolgan to'lov» "
          f"chiqib qirqilardi); mijoz nomi va telefoni kesilmaydi; «Timeline» ham sig'adi",
          lo.get("soni") == 3 and not lo.get("chiqqan") and _mj and not any(x.get("kesik") for x in _mj)
          and not (R.get("loyiha_o") or {}).get("chiqqan") and not (R.get("loyiha_o") or {}).get("sahifa_yon")
          and not (R.get("loyiha_tl_o") or {}).get("chiqqan"),
          [lo, [x for x in _mj if x.get("kesik")][:3], R.get("loyiha_o"), R.get("loyiha_tl_o")])
    rt = R.get("retsept") or []
    ro = R.get("retsept_oyna") or {}
    check(f"T5 {w} px (G4-24) retsept tahririda tarkibdagi material nomlari to'liq (ilgari 46 px — «Namuna K…»); oynada ekrandan "
          f"chiqqan element yo'q",
          isinstance(rt, list) and len(rt) >= 2 and not any(x.get("kesik") for x in rt) and ro.get("oyna") and not ro.get("chiqqan"),
          [rt, ro])
    tk_ = R.get("tarkib") or {}
    _lm, _li, _mq, _is = (tk_.get(k) or {} for k in ("lmiq", "lisr", "miq", "isr"))
    check(f"T14 {w} px (G5-25) MRP «Mahsulot tarkibi» qatorida maydon nomlari ko'rinadi: «Miqdor» va «Isrof» o'z maydoni USTIDA "
          f"(ilgari ikkita nomsiz maydon — isrof miqdor bilan adashtirilardi); oynada ekrandan chiqqan element yo'q",
          _lm.get("d") not in (None, "none") and _li.get("d") not in (None, "none") and _lm.get("t") == "Miqdor" and _li.get("t") == "Isrof"
          and _lm.get("w", 0) > 0 and _mq and _is and _lm.get("bottom", 9e9) <= _mq.get("top", -1) + 2 and _li.get("bottom", 9e9) <= _is.get("top", -1) + 2
          and (R.get("tarkib_oyna") or {}).get("oyna") and not (R.get("tarkib_oyna") or {}).get("chiqqan") and not R.get("tarkib_xato"),
          [tk_, R.get("tarkib_oyna"), R.get("tarkib_xato")])
    ty = R.get("tayyor") or {}
    check(f"T6 {w} px (G5-15) Tayyor mahsulotlar: birinchi mahsulot BIRINCHI ekranda (360 × 740 da ilgari 790 px — ekrandan "
          f"tashqarida)", ty.get("birinchi") is not None and ty["birinchi"] + 40 <= ty.get("vh", 0), ty)
    check(f"T7 {w} px (G5-16) sensorli ekranda rasm qo'shish belgisi (kamera) KO'RINADI — Tayyor mahsulotlar va Loyihalar "
          f"(ilgari faqat sichqoncha ustiga kelganda)",
          ty.get("kamera") and all(v == "1" for v in ty["kamera"]) and R.get("loyiha_kamera")
          and all(v == "1" for v in R["loyiha_kamera"]), [ty.get("kamera"), R.get("loyiha_kamera")])
    if w == 390:
        qm, qr = R.get("qaytarish_maydon") or {}, R.get("qaytarish_rasm")
        check("T15 (G5-16) «Yangi qaytarish» oynasida «Rasm (ixtiyoriy)» maydoni (ekran ichida); oyna qayta ochilganda oldingi tanlov "
              "tozalanadi; tanlangan rasm SAQLANGAN qaytarishga yuklanadi (ilgari faqat saqlagandan keyin, telefonda ko'rinmaydigan "
              "belgi orqali)",
              qm.get("yorliq") == "Rasm (ixtiyoriy)" and qm.get("accept") == "image/*" and 0 < qm.get("right", 9e9) <= qm.get("vw", 0) + 1
              and R.get("qaytarish_tozalandi") == 0 and isinstance(qr, list) and len(qr) == 1 and qr[0].get("image_url")
              and not R.get("qaytarish_xato"),
              [qm, R.get("qaytarish_tozalandi"), qr, R.get("qaytarish_xato")])
    om = R.get("ombor") or {}
    _ch, _nx = om.get("chegara") or {}, om.get("narx") or {}
    check(f"T8 {w} px (G4-11) Omborda material qatorida «Chegara:» (min. qoldiq) va «Narx:» ustunlari KO'RINADI, yorlig'i bilan, "
          f"ekran ichida (ilgari 1 100 px dan tor ekranda yashirin); kamera belgisi ko'rinadi",
          _ch.get("display") not in (None, "none") and _nx.get("display") not in (None, "none") and _ch.get("ichida") and _nx.get("ichida")
          and _ch.get("yorliq") == '"Chegara:"' and _nx.get("yorliq") == '"Narx:"' and _nx.get("matn")
          and om.get("kamera") and all(v == "1" for v in om["kamera"]), om)
    ml = R.get("moliya") or {}
    mj = R.get("moliya_jadval") or {}
    check(f"T9 {w} px (G3-19) Moliya: «Daromad taqsimoti» izohi (summa, foiz) ekran ichida (ilgari «73,1%» 391..445 px); "
          f"tranzaksiyalar jadvali — kartalar (sarlavha yashirin, qator — blok)",
          ml.get("qator", 0) >= 2 and not ml.get("chiqqan") and mj.get("thead") == "none" and mj.get("tr") in ("block", None),
          [ml, mj])
    kp = R.get("kpi") or []
    check(f"T10 {w} px (G6-15) KPI: «Ehson foizi» maydoni va «Saqlash» ekran ichida (360 px da ilgari 379 px gacha)",
          isinstance(kp, list) and len(kp) >= 2 and all(x[1] >= -1 and x[2] <= x[3] + 1 for x in kp), kp)
    sr = R.get("sarlavha") or []
    check(f"T11 {w} px Bosh sahifa sarlavhasi «Assalomu alaykum, Namuna Dekor» kesilmaydi (ilgari «…Namuna De…»)",
          sr and not any(x.get("kesik") for x in sr) and "Namuna Dekor" in sr[0].get("t", ""), sr)
    ry = R.get("reyting") or []
    check(f"T17 {w} px Hisobotlar reytinglarida nomlar to'liq (2 qatorgacha; uzun material nomi ilgari ustunni kengaytirib, "
          f"summani ekrandan chiqarardi)", isinstance(ry, list) and any(len(x.get("t", "")) >= 40 for x in ry)
          and not any(x.get("kesik") for x in ry), [x for x in ry if x.get("kesik") or len(x.get("t", "")) >= 40][:4] if isinstance(ry, list) else ry)
    ja = R.get("jadval_amal") or {}
    check(f"T18 {w} px Hisobotlar jadval paneli: «Qidirish» butun kenglikda (≥ 90 %), «Excel» / «Chop etish» keyingi qatorda — ekran "
          f"ichida (ilgari bir qatorda, sahifa 424 px)",
          ja.get("qidiruv") and ja["qidiruv"] >= ja.get("w", 0) * 0.9 and len(ja.get("tugmalar") or []) >= 1
          and all(x[0] >= -1 and x[1] <= x[2] + 1 for x in ja["tugmalar"]), ja)
    mn = R.get("menyu") or {}
    check(f"T12 {w} px yopiq menyuning soyasi yo'q (chap chetda qora chiziq chiqmaydi), ochilganda — bor",
          mn.get("yopiq") == "none" and mn.get("ochiq") not in (None, "none") and mn.get("ochildi") and mn.get("yopildi"), mn)
    di = R.get("dash_ikki") or {}
    _bd = di.get("bolaklar") or []
    check(f"T19 {w} px (G1-20) Dashboard «Tayyor mahsulotlar» va «Brak» bloklari USTMA-UST, har biri butun kenglikda (ilgari ikki "
          f"ustun, ~170 px)", len(_bd) >= 2 and all(b[2] >= di.get("w", 0) * 0.9 for b in _bd) and _bd[1][1] > _bd[0][1], di)
    mb = [x for x in (R.get("majburiyat") or []) if x.get("t")]
    check(f"T13 {w} px (G1-20) Dashboard majburiyat nomlari to'liq («Namuna Ijara (har oy 5-kunigacha)», ta'minotchi, hodim — "
          f"ilgari 60–99 px)", mb and any("Ijara" in x["t"] for x in mb) and not any(x.get("kesik") for x in mb), mb)

kr = (NAT.get("kompyuter") or {}).get("reyting") or {}
_kk = kr.get("kenglik") or []
check("T20 1280 px (kompyuter) Hisobotlar reytinglari: uzun material nomi bo'lsa ham 4 ustun TENG kenglikda (nom «…» bilan "
      "qisqaradi, to'liq nomi — `title`), sahifa ekrandan kengaymaydi",
      len(_kk) == 4 and max(_kk) - min(_kk) <= 2 and kr.get("uzun_nom") and kr.get("sahifa", 9e9) <= kr.get("vw", 0) + 1, kr)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  - " + f)
sys.exit(0 if FAIL == 0 else 1)
