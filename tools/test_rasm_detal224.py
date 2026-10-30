#!/usr/bin/env python3
"""
test_rasm_detal224.py — kech160 (zip 224 «Tahrirda rasm o'z detaliga» + ichki detal qatori ko'rinishi; egasi 29.10 «ha»; review220 №7, review214).

NIMA UCHUN KERAK (O'LCHANGAN — `work/k224/probe224.py`, `probe224b.py`, haqiqiy Chromium, zip 223 kodi)
  Buyurtma TAHRIRIDA tanlangan rasm boshqa detalga tushardi: `uploadPendingItemImages` forma qatorlarini (tahrirda saqlangan tartibga
  TESKARI) id o'sish tartibidagi detallar bilan juftlardi — «Rasm A» rasmi to'ldiruvchi detalga, uch xil rasm — A ↔ C almashdi, yangi qator +
  «Rasm B» — ikkalasi boshqa detalga, nomi o'zgartirilgan detal bilan — «Rasm B» rasmi boshqasiga. Ichki qo'shimcha detal qatorida «Qalinligi
  (sm)» yozuvi va Kirill «Бор (×2)» tugmasi ko'p kengliklarda ikki qatorga bo'linardi (yozish joylari har xil balandlikda).
QOIDA: server `PUT /api/orders/{id}` javobida `item_ids` (yuborilgan tartibda saqlangan detal raqami) — sahifa rasmni AYNAN shunga yuklaydi;
  zaxira (`item_ids` yo'q / yangi buyurtma) — `rasmQatorDetallari224`: (1) qator raqami (`data-item-id`) + nomi va turi o'sha; (2) qolganlari forma
  tartibida — olinmagan, nomi va turi o'sha, eng kichik raqamli; (3) qolganlari — raqam tartibida (avvalgi qoida). 409 «Davom etish» — rasmlar ham.
BO'LIMLAR
  S — manba. M — zaxira moslash qoidasi (sahifada, sun'iy qatorlar / detallar: teskari tartib, yangi qator, nomi o'zgargan, nomdoshlar, Kirill /
      bo'shliq / harf, tur, detal topilmadi). T — HAQIQIY tahrir (Chromium + server; rasm fayli md5 bo'yicha qaysi detalda): «Rasm A», uch rasm,
      yangi qator, nomi o'zgargan, nomdosh «Karniz», tur o'zgargan + shu nomli yangi qator, 409 «Davom etish»; javobdagi `item_ids` (API).
  Y — yangi buyurtma oqimi (sahifada qatorlar, javob detallari — yaratilish tartibida, nomdoshlar bilan): yuboriladigan manzillar.
  K — ichki detal qatori: 11 kenglik (1440 … 320 px; zip 214 / 218 chegaralari) × Lotin / Kirill — yozuv / qoplama tugmasi bir qatorda, quti toshmaydi, sahifa
      gorizontal toshmaydi.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. (Faqat sahifa o'zgargan — PG bo'limi yo'q.)
Asl kodga (zip 223) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_rasm_detal224.py
"""
import os
import io
import re
import sys
import time
import socket
import hashlib
import datetime
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k224_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k224.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "PG_URL"):
    os.environ.pop(_k, None)

YORLIQ = "[TF1] " if TF else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master, Order, Recipe, RecipeIngredient   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k224", PAROL, UserRole.ADMIN, "K224", company_id=1)
P35 = Inventory(company_id=1, item_name="K224 Penoplast 35", unit="blok", stock_quantity=10_000, price_per_unit=500_000, volume_per_unit=1.0,
                is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P25 = Inventory(company_id=1, item_name="K224 Penoplast 25", unit="blok", stock_quantity=10_000, price_per_unit=400_000, volume_per_unit=1.0,
                is_penoplast=True, category="Penoplast")
PRJ = Project(company_id=1, client_name="K224 mijoz", project_name="K224 loyiha", client_phone="+998901110224", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K224 Usta", phone="+998900000224", kpi_percent=10)
KLEY = Inventory(company_id=1, item_name="K224 Kley", unit="kg", stock_quantity=100_000, price_per_unit=3_000, category="Kimyo")
s.add_all([P35, P25, PRJ, US, KLEY])
s.flush()
REC = Recipe(company_id=1, name="K224 Oq marmar", batch_size_kg=100.0)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
s.commit()
ID = {"P35": P35.id, "P25": P25.id, "PRJ": PRJ.id, "US": US.id, "REC": REC.id}
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "k224", "password": PAROL}, follow_redirects=False)
A.put("/api/settings/categories", data={"codes": "profil,panel,dona,blok,loy_sotish,mrp_product", "v": "2"})
BUGUN = services._tashkent_date()


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def profil(nom, L, peno, narx_m=60_000, w=20, t=10):
    return {"name": nom, "category": "profil", "width": w, "thickness": t, "length": L, "quantity": 1, "unit_price": narx_m * L,
            "is_coated": False, "penoplast_id": peno, "price_per_m3": None, "finished_product_id": None}


_N = [0]


def yarat(items):
    _N[0] += 1
    tana = {"project_id": ID["PRJ"], "order_type": "product", "recipe_id": ID["REC"], "master_id": ID["US"],
            "deadline": (BUGUN + datetime.timedelta(days=5)).isoformat(), "is_draft": False, "base_price": 0, "loy_kg": None,
            "items": list(items) + [profil(f"K224 to'ldiruvchi {_N[0]}", _N[0], ID["P25"])]}
    return js(A.post("/api/orders?confirm_shortage=true", json=tana)).get("id")


from PIL import Image                               # noqa: E402


def png(nom, rgb):
    p = os.path.join(_T, nom + ".png")
    Image.new("RGB", (8, 8), rgb).save(p)
    return p


PA, PB, PC, PD = png("a", (200, 10, 10)), png("b", (10, 200, 10)), png("c", (10, 10, 200)), png("d", (200, 200, 10))
MD5 = {hashlib.md5(open(p, "rb").read()).hexdigest(): k for k, p in (("A", PA), ("B", PB), ("C", PC), ("D", PD))}
YUKLANGAN = []


def rasmlar(oid):
    """{detal nomi: 'A' / 'B' / 'C' / 'D' / None} — rasm fayli md5 bo'yicha."""
    s2 = SessionLocal()
    try:
        out = {}
        for it in sorted(s2.get(Order, oid).items, key=lambda x: x.id):
            k = None
            if it.image_url:
                yol = os.path.join(ROOT, it.image_url.lstrip("/"))
                YUKLANGAN.append(yol)
                try:
                    k = MD5.get(hashlib.md5(open(yol, "rb").read()).hexdigest(), "?")
                except OSError:
                    k = "fayl yo'q"
            out[it.name] = k
        return out
    finally:
        s2.close()


O1 = yarat([profil("Rasm A", 10, ID["P35"]), profil("Rasm B", 8, ID["P35"])])
O2 = yarat([profil("Rasm A", 10, ID["P35"]), profil("Rasm B", 8, ID["P35"])])
O3 = yarat([profil("Rasm A", 10, ID["P35"]), profil("Rasm B", 8, ID["P35"])])
O4 = yarat([profil("Rasm A", 10, ID["P35"]), profil("Rasm B", 8, ID["P35"])])
O5 = yarat([profil("Karniz", 10, ID["P35"]), profil("Karniz", 6, ID["P35"])])
O6 = yarat([profil("Tur X", 10, ID["P35"])])
s = SessionLocal()
PKAM = Inventory(company_id=1, item_name="K224 Penoplast kam", unit="blok", stock_quantity=0.05, price_per_unit=450_000, volume_per_unit=1.0,
                 is_penoplast=True, category="Penoplast")
s.add(PKAM)
s.commit()
ID["PKAM"] = PKAM.id
s.close()
O7 = yarat([profil("Kam A", 1, ID["PKAM"]), profil("Kam B", 1, ID["PKAM"])])
O8 = yarat([profil("Ikki", 10, ID["P35"]), profil("Ikki", 6, ID["P25"])])


def detal_rasm(oid):
    """[(nom, tur, uzunlik, rasm)] — raqam tartibida."""
    s2 = SessionLocal()
    try:
        out = []
        for it in sorted(s2.get(Order, oid).items, key=lambda x: x.id):
            k = None
            if it.image_url:
                yol = os.path.join(ROOT, it.image_url.lstrip("/"))
                YUKLANGAN.append(yol)
                try:
                    k = MD5.get(hashlib.md5(open(yol, "rb").read()).hexdigest(), "?")
                except OSError:
                    k = "fayl yo'q"
            out.append((it.name, (it.category or "").lower(), round(float(it.length or 0), 3), k))
        return out
    finally:
        s2.close()


def uzunlik_rasm(oid, nom):
    """nomdoshlar: {uzunlik: rasm} (md5 bo'yicha)."""
    s2 = SessionLocal()
    try:
        out = {}
        for it in s2.get(Order, oid).items:
            if it.name != nom:
                continue
            k = None
            if it.image_url:
                yol = os.path.join(ROOT, it.image_url.lstrip("/"))
                YUKLANGAN.append(yol)
                try:
                    k = MD5.get(hashlib.md5(open(yol, "rb").read()).hexdigest(), "?")
                except OSError:
                    k = "fayl yo'q"
            out[round(float(it.length or 0), 3)] = k
        return out
    finally:
        s2.close()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_OH = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_up = _OH[_OH.find("async function uploadPendingItemImages"):]
_up = _up[:_up.find("\n}\n") + 3]
check("S1 `rasmQatorDetallari224` bor; `uploadPendingItemImages` qator ↔ detalni SHU bilan oladi (tartib bo'yicha juftlash — yo'q)",
      "function rasmQatorDetallari224(" in _OH and "rasmQatorDetallari224(rows, savedItems)" in _up and "sortedItems[i]" not in _up, _up[:300])
check("S2 ichki detal qatori: yozuvlar `white-space:nowrap`, o'lcham maydonlari min 112 px, qoplama min 160 px",
      _OH.count('min-width:112px"><label style="font-size:12px;color:var(--m-475569);white-space:nowrap">') == 3
      and 'min-width:112px;display:none"><label style="font-size:12px;color:var(--m-475569);white-space:nowrap">Miqdor' in _OH
      and 'min-width:160px"><label style="font-size:12px;color:var(--m-475569);white-space:nowrap">Qoplama' in _OH
      and _OH.count('class="sd-coat-opt sd-coat-') == 2 and _OH.count('style="white-space:nowrap" onclick="setSubDetailCoating(') == 2)

import uvicorn                                      # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402
so = socket.socket()
so.bind(("127.0.0.1", 0))
port = so.getsockname()[1]
so.close()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
BU = f"http://127.0.0.1:{port}"
XATO = []
STUB = """() => { window.__msg = []; window.showMsg = (t, ty) => { window.__msg.push([String(t), ty]); };
    window.showConfirmModal = async () => true; window.customConfirm = async () => true; window.confirm = () => true;
    window.alert = (t) => window.__msg.push([String(t), 'alert']); window.__reload = 0;
    try { window.location.reload = () => { window.__reload++; }; } catch (e) {} }"""
# M — sun'iy qatorlar: [nom, raqam] ro'yxati, detallar: [{id, name}] → har qatorga detal id (yoki null)
MOSLA = """([qs, ds]) => {
  if (typeof rasmQatorDetallari224 !== 'function') return 'FUNKSIYA YOQ';
  const qatorlar = qs.map(([nom, id, tur]) => { const d = document.createElement('div'); d.className = 'detal';
    d.innerHTML = '<input class="i-name">' + (tur ? `<select class="i-type"><option value="${tur}" selected>${tur}</option></select>` : '');
    d.querySelector('.i-name').value = nom; if (id) d.dataset.itemId = String(id); return d; });
  return rasmQatorDetallari224(qatorlar, ds).map(x => x ? x.id : null);
}"""
# Y — yangi buyurtma: sahifadagi qatorlar (addItem), fayllar, javob detallari — yaratilish (yuborilish) tartibida; fetch ushlanadi
YANGI = """async ([nomlar, fayl_qator]) => {
  showNewForm();
  const items = document.getElementById('items');
  items.querySelectorAll('.detal').forEach(r => r.remove());
  for (const n of nomlar) { addItem(); }
  const rows = [...items.querySelectorAll('.detal')];
  rows.forEach((r, i) => { r.querySelector('.i-name').value = nomlar[i]; });
  const tartib = collectItems().map(x => x.name);
  const saved = tartib.map((n, i) => ({id: 500 + i, name: n}));
  const yuborildi = [];
  const asl = window.fetch;
  window.fetch = async (u, o) => { yuborildi.push(String(u)); return new Response('{}', {status: 200}); };
  const dt = (nom) => { const d = new DataTransfer(); d.items.add(new File([nom], nom + '.png', {type: 'image/png'})); return d.files; };
  fayl_qator.forEach(i => { rows[i].querySelector('.i-pending-image').files = dt('f' + i); });
  let xatolar;
  try { xatolar = await uploadPendingItemImages(saved); } finally { window.fetch = asl; }
  return {tartib, yuborildi, saved, nomlar_dom: rows.map(r => r.querySelector('.i-name').value), xatolar};
}"""
BOLINISH = r"""() => {
  const r = document.querySelector('#items .detal .subdetail-row'); if (!r) return ['ichki yoq'];
  const out = [];
  r.querySelectorAll('label, .sd-coat-opt').forEach(e => {
    if (e.offsetParent === null || !e.textContent.trim()) return;
    const rg = document.createRange(); rg.selectNodeContents(e);
    const qator = new Set([...rg.getClientRects()].filter(x => x.width > 0.5).map(x => Math.round(x.top))).size;
    if (qator > 1) out.push(e.textContent.trim().slice(0, 24) + ' — ' + qator + ' qator');
  });
  [...r.children].forEach(d => { if (d.offsetParent !== null && d.scrollWidth > d.clientWidth + 1) out.push('QUTI toshdi: ' + d.textContent.trim().slice(0, 18)); });
  const sah = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  if (sah > 0) out.push('sahifa gorizontal toshdi ' + sah);
  return out;
}"""
ICHKI = """() => { const r = document.querySelector('#items .detal'); const w = r.querySelector('.i-subdetails-wrap'); if (w) w.style.display = '';
  if (!r.querySelector('.subdetail-row')) addSubDetailRow(r);
  const sd = r.querySelector('.subdetail-row .sd-type'); if (sd) { sd.value = 'panel'; sd.dispatchEvent(new Event('change', {bubbles: true})); }
  if (typeof _applyScriptToNode === 'function') _applyScriptToNode(document.body);
  return !!r.querySelector('.subdetail-row'); }"""


def kirish(pg):
    pg.goto(BU + "/login")
    pg.fill("input[name=username]", "k224")
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    try:
        pg.evaluate("() => localStorage.removeItem('penodecor_new_order_draft_v1')")
    except Exception:                      # noqa: BLE001
        pass


def tayyor(pg):
    pg.goto(BU + "/orders")
    pg.wait_for_load_state("networkidle")
    pg.evaluate(STUB)


def tahrir(pg, oid):
    pg.evaluate(f"() => {{ selectedOrderId = {oid}; editSelected('edit'); }}")
    pg.wait_for_timeout(2500)


def qator(pg, nom):
    for r in pg.query_selector_all("#items .detal"):
        if r.query_selector(".i-name").input_value() == nom:
            return r
    return None


def saqla(pg, oid):
    pg.evaluate(f"() => {{ updateOrder({oid}); }}")
    for _ in range(40):
        pg.wait_for_timeout(300)
        if pg.evaluate("() => (window.__msg || []).some(m => String(m[0]).startsWith('✓'))"):
            break
    pg.wait_for_timeout(500)


with sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.set_default_timeout(20000)
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
    kirish(pg)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("M — moslash qoidasi (sun'iy qatorlar)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    tayyor(pg)
    _m = lambda qs, ds: pg.evaluate(MOSLA, [qs, ds])                     # noqa: E731
    _d3 = [{"id": 7, "name": "Rasm A"}, {"id": 8, "name": "Rasm B"}, {"id": 9, "name": "To'ldiruvchi"}]
    check("M1 tahrir — qatorlar TESKARI (9, 8, 7): har qator o'z raqamiga",
          _m([["To'ldiruvchi", 9], ["Rasm B", 8], ["Rasm A", 7]], _d3) == [9, 8, 7], _m([["To'ldiruvchi", 9], ["Rasm B", 8], ["Rasm A", 7]], _d3))
    check("M2 yangi qator (raqamsiz) tepada — yangi detalga (13), eskilari o'z raqamiga",
          _m([["Yangi D", None], ["To'ldiruvchi", 9], ["Rasm B", 8], ["Rasm A", 7]], _d3 + [{"id": 13, "name": "Yangi D"}]) == [13, 9, 8, 7])
    check("M3 nomi o'zgargan qator (eski raqam 7, nom «Rasm A2») — yangi yaratilgan detalga (14), qolganlari o'z raqamiga",
          _m([["To'ldiruvchi", 9], ["Rasm B", 8], ["Rasm A2", 7]], [{"id": 8, "name": "Rasm B"}, {"id": 9, "name": "To'ldiruvchi"},
                                                                    {"id": 14, "name": "Rasm A2"}]) == [9, 8, 14])
    check("M4 yangi buyurtma, nomdosh ikki «Karniz» + boshqa (javobda detallar ixtiyoriy tartibda) — forma tartibida yaratilish tartibiga (20, 21, 22)",
          _m([["Karniz", None], ["Ustun", None], ["Karniz", None]], [{"id": 22, "name": "Karniz"}, {"id": 21, "name": "Ustun"},
                                                                     {"id": 20, "name": "Karniz"}]) == [20, 21, 22])
    check("M5 nom kaliti: server tartiblagan nom («PADAKOLNIK» → «Padakolnik»), ikki bo'shliq — o'sha detal (raqam tartibiga TESKARI qatorlar)",
          _m([["Rom  karniz", None], ["PADAKOLNIK", None]], [{"id": 30, "name": "Padakolnik"}, {"id": 31, "name": "Rom karniz"}]) == [31, 30])
    check("M5b nom kaliti — katta / kichik harf: «KARNIZ», «PLITA» ↔ «karniz», «plita» (ikkalasi raqam tartibiga TESKARI)",
          _m([["KARNIZ", None], ["PLITA", None]], [{"id": 50, "name": "plita"}, {"id": 51, "name": "karniz"}]) == [51, 50])
    check("M5c nom kaliti — bo'shliqlar: «Rom  karniz», « Ustun  A » ↔ «Rom karniz», «Ustun A» (raqam tartibiga TESKARI)",
          _m([["Rom  karniz", None], [" Ustun  A ", None]], [{"id": 52, "name": "Ustun A"}, {"id": 53, "name": "Rom karniz"}]) == [53, 52])
    check("M5d nom kaliti — Kirill: «Плита», «Карниз» ↔ «Plita», «Karniz» (raqam tartibiga TESKARI)",
          _m([["Плита", None], ["Карниз", None]], [{"id": 61, "name": "Karniz"}, {"id": 62, "name": "Plita"}]) == [62, 61])
    check("M9 zaxira qoida — TUR ham: raqamli «X» qatori panelga o'zgartirilgan (server uni yangi detal qiladi), yangi «X» profil qatori eski "
          "detalga moslanadi — panel → 13, profil → 10",
          _m([["X", 10, "panel"], ["X", None, "profil"]], [{"id": 10, "name": "X", "category": "profil"},
                                                            {"id": 13, "name": "X", "category": "panel"}]) == [13, 10])
    check("M6 raqam bor, lekin shu raqamli detal boshqa nomda (server nom bo'yicha boshqa qatorga moslagan) — nomi o'shasiga",
          _m([["B", 10], ["A", None]], [{"id": 10, "name": "A"}, {"id": 13, "name": "B"}]) == [13, 10])
    check("M8 tahrir — nomdosh ikki «Karniz» TESKARI (11, 10): raqam bo'yicha (nom bo'yicha bo'lsa almashardi)",
          _m([["Karniz", 11], ["Karniz", 10]], [{"id": 10, "name": "Karniz"}, {"id": 11, "name": "Karniz"}]) == [11, 10])
    check("M7 detal yetmasa — null (rasm yuborilmaydi), ortiqcha detal — e'tiborsiz",
          _m([["X", None], ["Y", None]], [{"id": 40, "name": "Z"}]) == [40, None])

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("T — haqiqiy tahrir (Chromium + server)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    tayyor(pg)
    tahrir(pg, O1)
    qator(pg, "Rasm A").query_selector(".i-pending-image").set_input_files(PA)
    saqla(pg, O1)
    _r1 = rasmlar(O1)
    check("T1 «Rasm A» ga rasm — «Rasm A» da A, boshqalarida rasm yo'q (ilgari to'ldiruvchi detalga tushardi)",
          _r1.get("Rasm A") == "A" and _r1.get("Rasm B") is None and _r1.get("K224 to'ldiruvchi 1") is None, _r1)

    tayyor(pg)
    tahrir(pg, O2)
    qator(pg, "Rasm A").query_selector(".i-pending-image").set_input_files(PA)
    qator(pg, "Rasm B").query_selector(".i-pending-image").set_input_files(PB)
    qator(pg, "K224 to'ldiruvchi 2").query_selector(".i-pending-image").set_input_files(PC)
    saqla(pg, O2)
    _r2 = rasmlar(O2)
    check("T2 uch detalga uch xil rasm — A / B / C o'z joyida (ilgari A ↔ C almashardi)",
          _r2 == {"Rasm A": "A", "Rasm B": "B", "K224 to'ldiruvchi 2": "C"}, _r2)

    tayyor(pg)
    tahrir(pg, O3)
    pg.evaluate("() => addItem()")
    pg.wait_for_timeout(300)
    pg.evaluate("""() => { const r = document.querySelector('#items .detal'); r.querySelector('.i-name').value = 'Yangi D';
        r.querySelector('.i-h').value = 20; r.querySelector('.i-w').value = 10; r.querySelector('.i-l').value = 5;
        const p = r.querySelector('.i-peno'); if (p && p.options[1]) p.value = p.options[1].value; calculateItem(r); updateTotal(); }""")
    qator(pg, "Yangi D").query_selector(".i-pending-image").set_input_files(PD)
    qator(pg, "Rasm B").query_selector(".i-pending-image").set_input_files(PB)
    saqla(pg, O3)
    _r3 = rasmlar(O3)
    check("T3 tahrirda yangi qator «Yangi D» (D) + «Rasm B» (B) — ikkalasi o'z detalida, «Rasm A» va to'ldiruvchida rasm yo'q",
          _r3 == {"Rasm A": None, "Rasm B": "B", "K224 to'ldiruvchi 3": None, "Yangi D": "D"}, _r3)

    tayyor(pg)
    tahrir(pg, O4)
    pg.evaluate("""() => { const r = [...document.querySelectorAll('#items .detal')].find(x => x.querySelector('.i-name').value === 'Rasm A');
        const i = r.querySelector('.i-name'); i.value = 'Rasm A2'; i.dispatchEvent(new Event('input', {bubbles: true})); }""")
    qator(pg, "Rasm A2").query_selector(".i-pending-image").set_input_files(PA)
    qator(pg, "Rasm B").query_selector(".i-pending-image").set_input_files(PB)
    saqla(pg, O4)
    _r4 = rasmlar(O4)
    check("T4 nomi o'zgartirilgan «Rasm A» → «Rasm A2» (yangi detal) A, «Rasm B» — B (ilgari B boshqa detalga)",
          _r4 == {"Rasm B": "B", "K224 to'ldiruvchi 4": None, "Rasm A2": "A"}, _r4)
    tayyor(pg)
    tahrir(pg, O5)
    for _r5 in pg.query_selector_all("#items .detal"):
        if _r5.query_selector(".i-name").input_value() == "Karniz":
            _l5 = float(_r5.query_selector(".i-l").input_value() or 0)
            _r5.query_selector(".i-pending-image").set_input_files(PA if abs(_l5 - 10) < 1e-6 else PB)
    saqla(pg, O5)
    _u5 = uzunlik_rasm(O5, "Karniz")
    check("T6 nomdosh ikki «Karniz» (10 m va 6 m) — 10 m ga A, 6 m ga B (raqam bo'yicha; tartib / nom bo'yicha bo'lsa almashardi)",
          _u5 == {10.0: "A", 6.0: "B"}, _u5)
    # T7 — tur o'zgartirildi (server: o'sha qator — YANGI detal, yangi shu nomli profil qatori — ESKI detalga moslanadi)
    tayyor(pg)
    tahrir(pg, O6)
    pg.evaluate("""() => { const r = [...document.querySelectorAll('#items .detal')].find(x => x.querySelector('.i-name').value === 'Tur X');
        const b = r.querySelector('.type-opt[data-value="panel"]'); if (b) b.click();
        r.querySelector('.i-h').value = 50; r.querySelector('.i-w').value = 5; const q = r.querySelector('.i-q'); if (q) q.value = 2;
        r.dataset.t224 = 'panel'; calculateItem(r); updateTotal(); }""")
    pg.evaluate("() => addItem()")
    pg.wait_for_timeout(300)
    pg.evaluate("""() => { const r = document.querySelector('#items .detal'); r.querySelector('.i-name').value = 'Tur X';
        r.querySelector('.i-h').value = 20; r.querySelector('.i-w').value = 10; r.querySelector('.i-l').value = 5; r.dataset.t224 = 'profil';
        const p = r.querySelector('.i-peno'); if (p && p.options[1]) p.value = p.options[1].value; calculateItem(r); updateTotal(); }""")
    _tur7 = pg.evaluate("() => [...document.querySelectorAll('#items .detal')].map(r => [r.querySelector('.i-name').value, r.querySelector('.i-type').value, r.dataset.itemId || ''])")
    for _r7 in pg.query_selector_all("#items .detal"):
        _t7 = _r7.get_attribute("data-t224")
        if _t7 == "panel":
            _r7.query_selector(".i-pending-image").set_input_files(PA)
        elif _t7 == "profil":
            _r7.query_selector(".i-pending-image").set_input_files(PB)
    saqla(pg, O6)
    _d7 = detal_rasm(O6)
    _p7 = [x for x in _d7 if x[0] == "Tur X" and x[1] == "panel"]
    _f7 = [x for x in _d7 if x[0] == "Tur X" and x[1] == "profil"]
    check("T7 «Tur X» profil → panel (A) + yangi «Tur X» profil qatori (B): panel detalda A, profil detalda B (server nom + tur bilan moslaydi; "
          "faqat nom bo'yicha bo'lsa almashardi — review224 №2)",
          len(_p7) == 1 and len(_f7) == 1 and _p7[0][3] == "A" and _f7[0][3] == "B", (_d7, _tur7))

    # T8 — ombor yetmaydi (409) → «Davom etish» → rasm ham yuklanadi (review224 №1)
    tayyor(pg)
    tahrir(pg, O7)
    pg.evaluate("""() => { const r = [...document.querySelectorAll('#items .detal')].find(x => x.querySelector('.i-name').value === 'Kam A');
        r.querySelector('.i-l').value = 60; calculateItem(r); updateTotal(); }""")
    qator(pg, "Kam A").query_selector(".i-pending-image").set_input_files(PA)
    qator(pg, "Kam B").query_selector(".i-pending-image").set_input_files(PB)
    _put8 = []
    pg.on("response", lambda q: _put8.append(q.status) if q.request.method == "PUT" and re.search(r"/api/orders/\d+", q.url) else None)
    pg.evaluate(f"() => {{ window.__msg = []; updateOrder({O7}); }}")
    for _ in range(50):
        pg.wait_for_timeout(300)
        if pg.evaluate("() => (window.__msg || []).some(m => String(m[0]).startsWith('✓'))"):
            break
    pg.wait_for_timeout(500)
    _d8 = {x[0]: (x[2], x[3]) for x in detal_rasm(O7)}
    check("T8 tahrirda ombor yetmadi (409) → «Davom etish» (200): «Kam A» 60 m — A, «Kam B» — B (ilgari rasm jimgina yuklanmasdi)",
          _put8[:2] == [409, 200] and _d8.get("Kam A") == (60.0, "A") and _d8.get("Kam B") == (1.0, "B"),
          (_put8, _d8, pg.evaluate("() => window.__msg")))
    # T10 — nomdosh ikki «Ikki» o'chirilib, raqamsiz qayta qo'shildi: server xususiyat (plotnost) bo'yicha moslaydi — faqat `item_ids` aniq
    tayyor(pg)
    tahrir(pg, O8)
    pg.evaluate("""() => { [...document.querySelectorAll('#items .detal')].filter(x => x.querySelector('.i-name').value === 'Ikki').forEach(x => x.remove());
        updateTotal(); }""")
    pg.evaluate("() => { addItem(); addItem(); }")
    pg.wait_for_timeout(400)
    pg.evaluate("""([p25, p35]) => { const rs = [...document.querySelectorAll('#items .detal')];
        const qo = (r, peno, l, belgi) => { r.querySelector('.i-name').value = 'Ikki'; r.querySelector('.i-h').value = 20; r.querySelector('.i-w').value = 10;
          r.querySelector('.i-l').value = l; const p = r.querySelector('.i-peno'); if (p) p.value = String(peno); r.dataset.t224 = belgi; calculateItem(r); };
        qo(rs[0], p25, 10, 'x'); qo(rs[1], p35, 6, 'y'); updateTotal(); }""", [ID["P25"], ID["P35"]])
    for _r10 in pg.query_selector_all("#items .detal"):
        _b10 = _r10.get_attribute("data-t224")
        if _b10 == "x":
            _r10.query_selector(".i-pending-image").set_input_files(PA)
        elif _b10 == "y":
            _r10.query_selector(".i-pending-image").set_input_files(PB)
    saqla(pg, O8)
    _d10 = sorted((x[2], x[3]) for x in detal_rasm(O8) if x[0] == "Ikki")
    check("T10 nomdosh ikki «Ikki» o'chirilib raqamsiz qayta qo'shildi (plotnostlari almashgan): 10 m — A, 6 m — B (server xususiyat bo'yicha "
          "moslaydi; sahifa javobdagi `item_ids` ni oladi — review224 №3)", _d10 == [(6.0, "B"), (10.0, "A")], _d10)
    check("T9 javobda `item_ids` — yuborilgan tartibda, hammasi shu buyurtmaning detali (API: o'zgarishsiz saqlash)",
          lambda: (lambda o, r: r.status_code == 200 and isinstance(js(r).get("item_ids"), list)
                   and sorted(js(r)["item_ids"]) == sorted(it["id"] for it in o["items"])
                   and js(r)["item_ids"] == [it["id"] for it in o["items"][::-1]])(
              js(A.get(f"/api/orders/{O1}")),
              A.put(f"/api/orders/{O1}", json={**{k: v for k, v in js(A.get(f"/api/orders/{O1}")).items() if k in ("project_id", "order_type", "master_id", "deadline", "is_draft", "base_price", "recipe_id")},
                                              "items": [{"id": it["id"], "name": it["name"], "category": it["category"], "width": it["width"], "thickness": it["thickness"],
                                                         "length": it["length"], "quantity": it["quantity"], "unit_price": it["unit_price"], "is_coated": it["is_coated"],
                                                         "penoplast_id": it.get("penoplast_id"), "price_per_m3": it.get("price_per_m3"), "finished_product_id": None}
                                                        for it in js(A.get(f"/api/orders/{O1}"))["items"][::-1]]})))
    check("T5 saqlash xabari muvaffaqiyatli («✓ Saqlandi…»), rasm ogohlantirishi yo'q (oxirgi tahrir — 409 «Davom etish»)",
          lambda: any(str(m[0]).startswith("✓ Saqlandi") and "⚠️" not in str(m[0]) and m[1] == "success" for m in pg.evaluate("() => window.__msg")),
          pg.evaluate("() => window.__msg"))

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("Y — yangi buyurtma oqimi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    tayyor(pg)
    _y = pg.evaluate(YANGI, [["Birinchi", "Karniz", "Ikkinchi", "Karniz"], [0, 1, 3]])
    _kut = []
    if isinstance(_y, dict):
        # forma tartibidagi qator → yaratilish tartibidagi detal (nomdoshlar — forma tartibida: server yuborilgan tartibda yaratadi)
        _ishl = {}
        for i, n in enumerate(_y["tartib"]):
            _ishl.setdefault(n, []).append(500 + i)
        _dom_id = [_ishl[n].pop(0) for n in _y["nomlar_dom"]]
        _kut = sorted(f"/api/order-items/{_dom_id[i]}/image" for i in (0, 1, 3))
    check("Y1 yangi buyurtma (4 qator, nomdosh ikki «Karniz»), 3 qatorga rasm — har biri forma tartibidagi o'z detaliga, xato yo'q",
          isinstance(_y, dict) and sorted(_y["yuborildi"]) == _kut and len(_y["yuborildi"]) == 3 and not _y["xatolar"], (_y, _kut))

    check("Y2 sahifa JS xatosi yo'q (M / T / Y)", not XATO, XATO[:3])
    ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("K — ichki qo'shimcha detal qatori ko'rinishi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    _yomon = {}
    for w, h, tel in ((1440, 900, False), (1366, 768, False), (1151, 900, False), (1150, 900, False), (1024, 768, False), (901, 900, False),
                      (900, 900, False), (768, 1024, True), (390, 844, True), (360, 740, True), (320, 640, True)):
        for yozuv in ("lotin", "kirill"):
            c2 = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
            c2.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
            c2.add_init_script(f"try {{ localStorage.setItem('erp_script', '{yozuv}'); }} catch (e) {{}}")
            p2 = c2.new_page()
            p2.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            kirish(p2)
            p2.goto(BU + "/orders")
            p2.wait_for_load_state("networkidle")
            p2.evaluate("() => showNewForm()")
            p2.wait_for_timeout(300)
            _bor = p2.evaluate(ICHKI)
            p2.wait_for_timeout(200)
            _b = p2.evaluate(BOLINISH) if _bor else ["ichki detal qo'shilmadi"]
            if _b:
                _yomon[f"{w}_{yozuv}"] = _b
            c2.close()
    check("K1 1440 / 1366 / 1151 / 1150 / 1024 / 901 / 900 / 768 / 390 / 360 / 320 px × Lotin / Kirill: ichki detal yozuvlari va «Yo'q / Bor (×2)» bir qatorda, quti va sahifa toshmaydi",
          not _yomon, _yomon)
    check("K2 sahifa JS xatosi yo'q (K)", not XATO, XATO[:3])
    br.close()
server.should_exit = True

import glob                                       # noqa: E402
for _y2 in set(YUKLANGAN):      # sinov rasmlari va ularning kichik nusxalari (`_kichik/…/<nom>_*`) — repo `static/uploads` da qolmasin;
    _stem = os.path.splitext(os.path.basename(_y2))[0]          # faqat SHU sinov fayllari (parallel sinovlarniki tegilmaydi)
    for _f in [_y2] + glob.glob(os.path.join(ROOT, "static", "uploads", "_kichik", "*", _stem + "_*")):
        try:
            os.remove(_f)
        except OSError:
            pass

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
