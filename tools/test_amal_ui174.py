#!/usr/bin/env python3
"""
test_amal_ui174.py — kech144 (zip 174): «Tayyor mahsulotlar», «Qaytarishlar», «Qarzdorlar», «Moliya», «Kunlik xarajat» — HAQIQIY Chromium,
HAQIQIY lokal server (uvicorn, test bazasi). Tarmoq xatolari Playwright `route` bilan ataylab beriladi: so'rov serverda BAJARILADI, javob esa
502 (deploy almashinuvi) bo'lib qaytadi; tarmoq uzilishi (`abort`); javobni kechiktirish.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k173_tayyorgarlik/agentlar/tayyor/probe_takror.py`, `probe_rollar.py`, asl kod = zip 173)
  B#1  Sotuv / guruh sotuv: ikki marta bosish — 2 sotuv; 502 dan keyin «Server xatosi», qayta bosish — IKKINCHI sotuv.
  B#2  Brak (omborda / ishlab chiqarishda): xuddi shunday — 2 brak, Moliyada ikki marta.
  B#3  Ishlab chiqarish, «Yana ishlab chiqarish»: himoya yo'q — 2 partiya, xomashyo ikki marta.
  B#4  Qarzdorlar «majburiyat to'lovi», Moliya / «Kunlik xarajat» yangi xarajat: 502 dan keyin qayta bosish — 2 xarajat.
  B#6  «Omborchi» (tayyor rol): «Yangi qaytarish» / «Brak yozish → Buyurtma detalida» — detallar 403, sahifa «detal yo'q» derdi
       (EGASI QARORI 13.10 «Detal va miqdor»: Omborchi faqat detal nomi va miqdorini ko'radi, summani server hisoblaydi).
  C#13 «Yangi qaytarish»: A buyurtmaning kech javobi B tanlangandan keyin B ostida chizilardi.
  C#18 «+ Kategoriya» ikki marta bosish — 2 kategoriya; C#19 kategoriyani o'chirish rad etilsa — «Xato yuz berdi» (sababsiz).
  C#21 «Sotish» oynasi narxi yaxlitlanardi (12 500,5 → «12 501»).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 173) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_amal_ui174.py
"""
import os
import re
import io
import sys
import glob
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "amal_ui174_test"
_T = tempfile.mkdtemp(prefix="aui174_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'amal_ui174.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, Recipe, RecipeIngredient, Project, FinishedProduct, FinishedProductSale,   # noqa: E402
                    FinishedProductLoss, ExpenseTransaction, StockSource, ProductionStatus, ReturnItem, RecurringObligation)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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
        print(f"  ✗ {label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "u174_admin", PAROL, UserRole.ADMIN, "U174 Admin", company_id=1)
    auth.create_user(s, "u174_omb", PAROL, UserRole.WAREHOUSE, "U174 Omborchi", company_id=1)     # tayyor «Omborchi»
    auth.create_user(s, "u174_mol", PAROL, UserRole.ACCOUNTANT, "U174 Moliyachi", company_id=1)   # tayyor «Moliyachi»
PENO = Inventory(company_id=1, item_name="U174 Penoplast", unit="blok", stock_quantity=10000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="U174 Kley", unit="kg", stock_quantity=100000, price_per_unit=2000, category="Kimyo")
PRJ = Project(company_id=1, client_name="U174 Mijoz", project_name="U174 loyiha", total_budget=0, total_paid=0)
s.add_all([PENO, KLEY, PRJ])
s.flush()
REC = Recipe(company_id=1, name="U174 retsept", batch_size_kg=100.0)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))


def tm(nom, miqdor, narx=50000):
    fp = FinishedProduct(company_id=1, name=nom, category="profil", quantity=miqdor, produced_quantity=miqdor, unit="metr",
                         unit_price=narx, cost_price=10000, source=StockSource.PRODUCED,
                         production_status=ProductionStatus.READY, is_coated=False)
    s.add(fp)
    s.flush()
    return fp.id


ID = {"S": tm("U174 Sotuv profil", 50), "G": tm("U174 Guruh profil", 20), "L": tm("U174 Brak profil", 20),
      "N": tm("U174 Tiyin narx", 5, 12500.5)}
s.commit()
ID.update({"PENO": PENO.id, "KLEY": KLEY.id, "REC": REC.id, "PRJ": PRJ.id})
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert C.post("/login", data={"username": "u174_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)


def ishlab(nom):
    r = C.post("/api/finished/produce", json={"name": nom, "category": "profil", "is_coated": False, "penoplast_id": ID["PENO"],
                                              "price_per_m3": None, "unit_price": 100000, "recipe_id": None, "notes": None,
                                              "width": 10, "thickness": 10, "length": 10, "quantity": 1, "loy_kg": 0})
    assert r.status_code == 200, r.text
    d = js(r)
    return d.get("product_id") or d.get("id") or d.get("finished_product_id")


ID["P"] = ishlab("U174 Ishlab brak profil")     # ishlab chiqarish braki uchun (barqaror nisbat bor)
ID["A"] = ishlab("U174 Qoshish profil")         # «Yana ishlab chiqarish»


def buyurtma(nom, narx, n):
    r = C.post("/api/orders?confirm_shortage=true", json={"project_id": ID["PRJ"], "order_type": "product", "items": [
        {"name": nom, "category": "panel", "width": 50, "thickness": 5, "quantity": n, "unit_price": narx, "is_coated": False}]})
    assert r.status_code == 200, r.text
    oid = js(r)["id"]
    oi = js(r)["items"][0]["id"]
    rd = C.post("/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": oi, "quantity": n}], "received_by": None,
                                         "notes": None, "transport_carrier": None, "transport_cost": 0, "transport_payer": "none",
                                         "payment_amount": None, "payment_method": "naqd"})
    assert rd.status_code == 200, rd.text
    return oid, oi


ID["OA"], ID["OAI"] = buyurtma("U174 A qaytarish detali", 10000, 5)
ID["OB"], ID["OBI"] = buyurtma("U174 B qaytarish detali", 20000, 4)
ID["KAT"] = js(C.post("/api/obligations/recurring", params={"category": "u174_kat", "label": "U174 ijara", "monthly_target": "300000",
                                                           "icon": "🏠", "due_day": "5"})).get("id")
assert ID["KAT"], "kategoriya"


def soni(model, **f):
    d = SessionLocal()
    try:
        q = d.query(model)
        for k, v in f.items():
            q = q.filter(getattr(model, k) == v)
        return q.count()
    finally:
        d.close()


def qoldiq(fp_id):
    d = SessionLocal()
    try:
        return float(d.get(FinishedProduct, fp_id).quantity)
    finally:
        d.close()


def tm_nomi_soni(nom):
    return soni(FinishedProduct, name=nom)


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
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
B = f"http://127.0.0.1:{port}"
pw_ctx = br = None
if PW_BOR and server.started:
    pw_ctx = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                              "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        br = None
        _pw_x = f"{type(_e).__name__}: {_e}"
check("T0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO, SOROV, JAVOB = [], [], []


def kontekst(user="u174_admin"):
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""), q.post_data, q.headers.get("x-amal-kaliti")))
          if "/api/" in q.url and q.method in ("POST", "PUT", "DELETE") else None)
    pg.on("response", lambda r: JAVOB.append((r.request.method, r.url.replace(B, ""), r.status, r.headers.get("x-takror")))
          if "/api/" in r.url and r.request.method in ("POST", "PUT", "DELETE") else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


# Xabarlar, tasdiq va kiritish oynalari: `window.__msg`; tasdiq javobi — `window.__ha` (standart: true); kiritish — `window.__kirit`
ILGAK = """() => { window.__msg = []; window.__ha = true; window.__kirit = null;
  window.showMsg = (t, ty) => { window.__msg.push([String(t), ty || '']); };
  window.alert = (t) => { window.__msg.push([String(t), 'alert']); };
  window.xabarOyna = async (t) => { window.__msg.push([String(t), 'oyna']); };
  window.customConfirm = async () => window.__ha;
  window.kiritishOyna = async () => window.__kirit;
  window.open = () => null; }"""
SAHIFA_502 = {"status": 502, "content_type": "text/html", "body": "<html><body><h1>502 Bad Gateway</h1></body></html>"}


def ochiq(pg, yol):
    pg.goto(B + yol, wait_until="networkidle")
    pg.wait_for_timeout(400)
    pg.evaluate(ILGAK)


def msg(pg):
    try:
        return pg.evaluate("() => window.__msg || []")
    except Exception:                      # noqa: BLE001 — sahifa qayta yuklangan
        return []


def sorovlar(nima, usul="POST"):
    return [x for x in SOROV if nima in x[1] and x[0] == usul]


def javoblar(nima, usul="POST"):
    return [x for x in JAVOB if nima in x[1] and x[0] == usul]


class Bajar502:
    """So'rov serverga YETADI va bajariladi (`route.fetch`), lekin brauzerga 502 HTML qaytadi (deploy almashinuvi)."""

    def __init__(self):
        self.holat = []

    def __call__(self, route):
        try:
            j = route.fetch()
            self.holat.append(j.status)
        except Exception as e:             # noqa: BLE001
            self.holat.append(f"{type(e).__name__}")
        route.fulfill(**SAHIFA_502)


def baj(pg, ifoda, kutish=600):
    """Sahifa funksiyasini chaqiradi va (va'da bo'lsa) tugashini kutadi; sahifa qayta yuklansa — yuklanishni kutadi."""
    x = None
    try:
        pg.evaluate(ifoda)
    except Exception as e:                 # noqa: BLE001 — muvaffaqiyatda sahifa qayta yuklanadi (kontekst yo'qoladi)
        x = str(e)[:120]
    pg.wait_for_timeout(kutish)
    try:
        pg.wait_for_load_state("networkidle")
    except Exception:                      # noqa: BLE001
        pass
    return x


KALIT_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
NOMALUM = "natijasi noma'lum"
TAKROR = "ikkinchi marta yozilmadi"

if br:
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("S. «Sotish» (B#1, C#21)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/finished")
        sotuv_och = (f"() => {{ openSellModal({ID['S']}, 'U174 Sotuv profil', 50, 'metr', 50000);"
                     " document.getElementById('sell-qty').value = '1'; document.getElementById('sell-master').value = 'none';"
                     " updateSellTotal(); }")
        pg.evaluate(sotuv_och)
        n0 = len(sorovlar("/api/finished/sell"))
        pg.dblclick("#sellModal button.btn-green")
        pg.wait_for_timeout(1500)
        _s1 = sorovlar("/api/finished/sell")[n0:]
        check("S1 «✓ Sotish» ikki marta bosildi → BITTA so'rov, bazada BITTA sotuv, qoldiq 50 → 49 (asl: 2 sotuv)",
              len(_s1) == 1 and soni(FinishedProductSale, finished_product_id=ID["S"]) == 1 and abs(qoldiq(ID["S"]) - 49) < 1e-9,
              (len(_s1), soni(FinishedProductSale, finished_product_id=ID["S"]), qoldiq(ID["S"])))
        check("S1b so'rovda amal kaliti (`X-Amal-Kaliti`, 8–64 belgi)", bool(_s1) and bool(KALIT_RE.match(_s1[0][3] or "")),
              _s1[:1])
        # S2 — server bajardi, javob 502 → «natija noma'lum», oyna ochiq; qayta bosish → takror (ikkinchi sotuv YO'Q)
        ochiq(pg, "/finished")
        pg.evaluate(sotuv_och)
        h = Bajar502()
        pg.route("**/api/finished/sell", h)
        n0 = len(sorovlar("/api/finished/sell"))
        baj(pg, "() => submitSell()")
        m1 = msg(pg)
        oyna = pg.evaluate("() => document.getElementById('sellModal').style.display")
        check("S2 server bajardi, javob 502 → «⚠️ Sotuv natijasi noma'lum … qayta bossangiz — ikki marta yozilmaydi», oyna OCHIQ"
              " (asl: «Server xatosi»)",
              h.holat == [200] and any(NOMALUM in x[0] and "Sotuv" in x[0] and "ikki marta yozilmaydi" in x[0] for x in m1)
              and oyna == "flex" and soni(FinishedProductSale, finished_product_id=ID["S"]) == 2, (h.holat, m1, oyna))
        pg.unroute("**/api/finished/sell", h)
        baj(pg, "() => submitSell()")
        m2 = msg(pg)
        _s2 = sorovlar("/api/finished/sell")[n0:]
        _j2 = javoblar("/api/finished/sell")[-1:]
        check("S3 qayta bosish → server birinchi javobni qaytaradi (`X-Takror: 1`), xabar «✓ Sotildi … ikkinchi marta yozilmadi»;"
              " bazada sotuv O'SHA (2), qoldiq 48 (asl: 3 sotuv, 47)",
              len(_s2) == 2 and _s2[0][3] and _s2[0][3] == _s2[1][3] and _j2 and _j2[0][3] == "1"
              and any(x[0].startswith("✓ Sotildi") and TAKROR in x[0] for x in m2)
              and soni(FinishedProductSale, finished_product_id=ID["S"]) == 2 and abs(qoldiq(ID["S"]) - 48) < 1e-9,
              (_s2, _j2, m2, qoldiq(ID["S"])))
        # S4 — tarmoq uzildi (so'rov serverga yetmadi) → natija noma'lum; qayta bosish → bajariladi (BIR marta)
        ochiq(pg, "/finished")
        pg.evaluate(sotuv_och)
        _ab = lambda r: r.abort()                                                               # noqa: E731
        pg.route("**/api/finished/sell", _ab)
        baj(pg, "() => submitSell()")
        m3 = msg(pg)
        check("S4 internet uzildi → «… natijasi noma'lum: internet aloqasi yo'q …», sotuv YO'Q",
              any(NOMALUM in x[0] and "internet aloqasi yo'q" in x[0] for x in m3)
              and soni(FinishedProductSale, finished_product_id=ID["S"]) == 2, m3)
        pg.unroute("**/api/finished/sell", _ab)
        baj(pg, "() => submitSell()")
        m4 = msg(pg)
        check("S5 qayta bosish → sotildi (takror EMAS), bazada 3, qoldiq 47",
              any(x[0].startswith("✓ Sotildi") and TAKROR not in x[0] for x in m4)
              and soni(FinishedProductSale, finished_product_id=ID["S"]) == 3 and abs(qoldiq(ID["S"]) - 47) < 1e-9, m4)
        # S6 — server rad etdi (400) → sabab; kalit tashlanadi (keyingi urinish — yangi kalit)
        ochiq(pg, "/finished")
        pg.evaluate(sotuv_och)
        _rad = lambda r: r.fulfill(status=400, content_type="application/json",                # noqa: E731
                                   body='{"detail": {"success": false, "message": "SINOV-RAD-174"}}')
        pg.route("**/api/finished/sell", _rad)
        n0 = len(sorovlar("/api/finished/sell"))
        baj(pg, "() => submitSell()")
        m5 = msg(pg)
        pg.unroute("**/api/finished/sell", _rad)
        baj(pg, "() => submitSell()")
        _s6 = sorovlar("/api/finished/sell")[n0:]
        check("S6 server rad etdi → «❌ Sotuv saqlanmadi: SINOV-RAD-174»; keyingi urinish — YANGI kalit (rad etilgan amal kalitni band"
              " qilmaydi) va sotiladi",
              any(x[0] == "❌ Sotuv saqlanmadi: SINOV-RAD-174" for x in m5) and len(_s6) == 2 and _s6[0][3] != _s6[1][3]
              and soni(FinishedProductSale, finished_product_id=ID["S"]) == 4, (m5, _s6))
        # S7 — narx tiyin bilan (C#21)
        ochiq(pg, "/finished")
        _np = pg.evaluate(f"() => {{ openSellModal({ID['N']}, 'U174 Tiyin narx', 5, 'dona', 12500.5);"
                          " const v = document.getElementById('sell-price').value; return [v, parseNum(v)]; }")
        check("S7 «Sotish» oynasida narx 12 500,5 → maydonda tiyin saqlanadi (asl: «12 501» — shu narxda sotilardi)",
              abs(float(_np[1]) - 12500.5) < 1e-9 and "12 501" not in _np[0], _np)
    except Exception as _e:              # noqa: BLE001 — asl kodda (zip 173) element / funksiya yo'q bo'lishi mumkin: test QULAMAYDI
        check("bo'lim kutilmagan istisno bilan to'xtadi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("G. Guruh sotuv (savatcha) — B#1")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/finished")
        guruh_och = (f"() => {{ _batchItems = {{ '{ID['G']}': {{name: 'U174 Guruh profil', maxQty: 20, unit: 'metr', price: 50000}} }};"
                     " openBatchSellModal(); document.querySelector('.batch-item-row .batch-qty').value = '2';"
                     " document.getElementById('batch-master').value = 'none'; updateBatchTotal(); }")
        pg.evaluate(guruh_och)
        h = Bajar502()
        pg.route("**/api/finished/sell-batch", h)
        n0 = len(sorovlar("/api/finished/sell-batch"))
        baj(pg, "() => submitBatchSell()")
        m1 = msg(pg)
        pg.unroute("**/api/finished/sell-batch", h)
        baj(pg, "() => submitBatchSell()")
        m2 = msg(pg)
        _g = sorovlar("/api/finished/sell-batch")[n0:]
        check("G1 502 (server bajardi) → natija noma'lum; qayta bosish → o'sha kalit, takror; bazada BITTA sotuv, qoldiq 20 → 18",
              h.holat == [200] and any(NOMALUM in x[0] for x in m1) and len(_g) == 2 and _g[0][3] and _g[0][3] == _g[1][3]
              and any(TAKROR in x[0] and "sotildi" in x[0] for x in m2)
              and soni(FinishedProductSale, finished_product_id=ID["G"]) == 1 and abs(qoldiq(ID["G"]) - 18) < 1e-9,
              (h.holat, m1, m2, _g, qoldiq(ID["G"])))
        pg.evaluate(guruh_och)
        n0 = len(sorovlar("/api/finished/sell-batch"))
        pg.dblclick("#batchSellModal button.btn-green")
        pg.wait_for_timeout(1500)
        check("G2 «✓ Sotish» ikki marta bosildi → BITTA so'rov, qoldiq 16",
              len(sorovlar("/api/finished/sell-batch")[n0:]) == 1 and abs(qoldiq(ID["G"]) - 16) < 1e-9,
              (sorovlar("/api/finished/sell-batch")[n0:], qoldiq(ID["G"])))
    except Exception as _e:              # noqa: BLE001 — asl kodda (zip 173) element / funksiya yo'q bo'lishi mumkin: test QULAMAYDI
        check("bo'lim kutilmagan istisno bilan to'xtadi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("B. Brak — omborda turgan va ishlab chiqarishda (B#2)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/finished")
        brak_och = (f"() => {{ openLossModal({ID['L']}, 'U174 Brak profil', 20, 'metr', 'profil');"
                    " document.getElementById('loss-qty').value = '1'; document.getElementById('brak-cause').value = 'boshqa'; }")
        pg.evaluate(brak_och)
        n0 = len(sorovlar("/api/finished/loss"))
        pg.dblclick("#brak-save-btn")
        pg.wait_for_timeout(1500)
        check("B1 «⚠️ Kamaytirish (brak)» ikki marta bosildi → BITTA so'rov, BITTA brak, qoldiq 20 → 19",
              len(sorovlar("/api/finished/loss")[n0:]) == 1 and soni(FinishedProductLoss, finished_product_id=ID["L"]) == 1
              and abs(qoldiq(ID["L"]) - 19) < 1e-9, (sorovlar("/api/finished/loss")[n0:], qoldiq(ID["L"])))
        ochiq(pg, "/finished")
        pg.evaluate(brak_och)
        h = Bajar502()
        pg.route("**/api/finished/loss", h)
        n0 = len(sorovlar("/api/finished/loss"))
        baj(pg, "() => submitLoss()")
        m1 = msg(pg)
        oyna = pg.evaluate("() => document.getElementById('brakModal').style.display")
        pg.unroute("**/api/finished/loss", h)
        baj(pg, "() => submitLoss()")
        m2 = msg(pg)
        _b = sorovlar("/api/finished/loss")[n0:]
        check("B2 502 (server bajardi) → «Brak natijasi noma'lum», oyna ochiq; qayta bosish → takror; brak 2 (asl: 3), qoldiq 18",
              h.holat == [200] and any(NOMALUM in x[0] and "Brak" in x[0] for x in m1) and oyna == "flex"
              and len(_b) == 2 and _b[0][3] == _b[1][3] and any(TAKROR in x[0] for x in m2)
              and soni(FinishedProductLoss, finished_product_id=ID["L"]) == 2 and abs(qoldiq(ID["L"]) - 18) < 1e-9,
              (h.holat, m1, oyna, m2, _b, qoldiq(ID["L"])))
        # ishlab chiqarish braki
        ochiq(pg, "/finished")
        pg.evaluate(f"() => {{ openLossModal({ID['P']}, 'U174 Ishlab brak profil', 1, 'metr', 'profil'); setLossMode('production');"
                    " document.getElementById('loss-qty').value = '1'; document.getElementById('brak-cause').value = 'boshqa'; }")
        h = Bajar502()
        pg.route("**/api/finished/production-brak", h)
        n0 = len(sorovlar("/api/finished/production-brak"))
        baj(pg, "() => submitLoss()")
        m1 = msg(pg)
        pg.unroute("**/api/finished/production-brak", h)
        baj(pg, "() => submitLoss()")
        m2 = msg(pg)
        _p = sorovlar("/api/finished/production-brak")[n0:]
        check("B3 ishlab chiqarish braki: 502 (server bajardi) → natija noma'lum; qayta bosish → takror; yozuv BITTA",
              h.holat == [200] and any(NOMALUM in x[0] for x in m1) and len(_p) == 2 and _p[0][3] == _p[1][3]
              and any(TAKROR in x[0] for x in m2) and soni(FinishedProductLoss, finished_product_id=ID["P"]) == 1,
              (h.holat, m1, m2, _p, soni(FinishedProductLoss, finished_product_id=ID["P"])))
    except Exception as _e:              # noqa: BLE001 — asl kodda (zip 173) element / funksiya yo'q bo'lishi mumkin: test QULAMAYDI
        check("bo'lim kutilmagan istisno bilan to'xtadi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("I. Ishlab chiqarish va «Yana ishlab chiqarish» (B#3)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/finished")
        ishlab_och = ("() => { openProduceModal(); document.getElementById('p-name').value = 'U174 UI partiya';"
                      " document.getElementById('p-h').value = '10'; document.getElementById('p-w').value = '10';"
                      " document.getElementById('p-l').value = '2'; document.getElementById('p-coated').value = 'false';"
                      " syncPCoatingUI(false); pCalc(); document.getElementById('p-price').value = '60000'; }")
        pg.evaluate(ishlab_och)
        h = Bajar502()
        pg.route("**/api/finished/produce", h)
        n0 = len(sorovlar("/api/finished/produce"))
        baj(pg, "() => saveProduce()")
        e1 = pg.evaluate("() => document.getElementById('p-error').textContent")
        pg.unroute("**/api/finished/produce", h)
        baj(pg, "() => saveProduce()")
        m2 = msg(pg)
        _i = sorovlar("/api/finished/produce")[n0:]
        check("I1 502 (server bajardi) → oynada «Ishlab chiqarish natijasi noma'lum»; qayta bosish → takror; partiya BITTA (asl: 2,"
              " xomashyo ikki marta)",
              h.holat == [200] and NOMALUM in (e1 or "") and len(_i) == 2 and _i[0][3] == _i[1][3]
              and any(TAKROR in x[0] for x in m2) and tm_nomi_soni("U174 UI partiya") == 1,
              (h.holat, e1, m2, _i, tm_nomi_soni("U174 UI partiya")))
        pg.evaluate(ishlab_och.replace("U174 UI partiya", "U174 UI partiya 2"))
        n0 = len(sorovlar("/api/finished/produce"))
        pg.dblclick("#prodModal button.btn-gold")
        pg.wait_for_timeout(2000)
        check("I2 «🏭 Ishlab chiqarish» ikki marta bosildi → BITTA so'rov, BITTA partiya",
              len(sorovlar("/api/finished/produce")[n0:]) == 1 and tm_nomi_soni("U174 UI partiya 2") == 1,
              (sorovlar("/api/finished/produce")[n0:], tm_nomi_soni("U174 UI partiya 2")))
        # «Yana ishlab chiqarish» (miqdor qo'shish)
        ochiq(pg, "/finished")
        q0 = qoldiq(ID["A"])
        h = Bajar502()
        pg.route(f"**/api/finished/{ID['A']}/add", h)
        n0 = len(sorovlar(f"/api/finished/{ID['A']}/add"))
        _ch = f"() => addProduction({ID['A']}, 2, fpItems.find(i => i.id === {ID['A']}))"
        baj(pg, _ch)
        m1 = msg(pg)
        pg.unroute(f"**/api/finished/{ID['A']}/add", h)
        baj(pg, _ch)
        m2 = msg(pg)
        _a = sorovlar(f"/api/finished/{ID['A']}/add")[n0:]
        check("I3 «Yana ishlab chiqarish»: 502 (server bajardi) → natija noma'lum; qayta → takror; miqdor BIR marta +2",
              h.holat == [200] and any(NOMALUM in x[0] for x in m1) and len(_a) == 2 and _a[0][3] == _a[1][3]
              and any(TAKROR in x[0] for x in m2) and abs(qoldiq(ID["A"]) - (q0 + 2)) < 1e-9, (h.holat, m1, m2, _a, q0, qoldiq(ID["A"])))
    except Exception as _e:              # noqa: BLE001 — asl kodda (zip 173) element / funksiya yo'q bo'lishi mumkin: test QULAMAYDI
        check("bo'lim kutilmagan istisno bilan to'xtadi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("Q. «Omborchi» — «Yangi qaytarish» va «Brak yozish → Buyurtma detalida» (B#6, QAROR «Detal va miqdor»)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst("u174_omb")
    try:
        ochiq(pg, "/returns")
        pg.evaluate("() => showAddModal()")
        pg.evaluate("() => qaytarishBuyurtmalariniYukla()")
        pg.evaluate(f"() => {{ document.getElementById('f-order').value = '{ID['OA']}'; return onOrderChange(); }}")
        pg.wait_for_timeout(400)
        opt = pg.evaluate("() => Array.from(document.getElementById('f-item').options).map(o => [o.value, o.textContent])")
        check("Q1 Omborchi buyurtmani tanladi → detal ro'yxatda (asl: 403, «Bu buyurtmada detal yo'q»), narx maydoni YO'Q",
              any(str(ID["OAI"]) == v and "U174 A qaytarish detali" in t for v, t in opt)
              and pg.evaluate("() => !document.getElementById('f-unit-price')"), opt)
        pg.evaluate(f"() => {{ document.getElementById('f-item').value = '{ID['OAI']}'; onItemChange();"
                    " document.getElementById('f-qty').value = '1'; calcValue(); }")
        h = Bajar502()
        pg.route("**/api/returns", h)
        n0 = len(sorovlar("/api/returns"))
        baj(pg, "() => saveReturn()")
        e1 = pg.evaluate("() => document.getElementById('add-error').textContent")
        pg.unroute("**/api/returns", h)
        baj(pg, "() => saveReturn()", 1200)
        _q = sorovlar("/api/returns")[n0:]
        d = SessionLocal()
        try:
            _rr = [(float(r.quantity), float(r.refund_amount or 0)) for r in d.query(ReturnItem).filter(ReturnItem.order_id == ID["OA"])]
        finally:
            d.close()
        check("Q2 saqlash: 502 (server bajardi) → «Qaytarish natijasi noma'lum»; qayta → takror; qaytarish BITTA, summani server"
              " hisobladi (1 × 10 000)",
              h.holat == [200] and NOMALUM in (e1 or "") and len(_q) == 2 and _q[0][3] == _q[1][3] and len(_rr) == 1
              and abs(_rr[0][1] - 10000) < 0.01 and '"refund_amount":0' in (_q[0][2] or "").replace(" ", ""), (h.holat, e1, _q, _rr))
        # Brak yozish — buyurtma detalida (loyiha → detallar)
        ochiq(pg, "/returns")
        pg.evaluate("() => showBrakModal('buyurtma')")
        pg.evaluate("() => brakLoyihalariniYukla()")
        pg.evaluate(f"() => {{ document.getElementById('brak-project').value = '{ID['PRJ']}'; return onBrakProjectChange(); }}")
        pg.wait_for_timeout(400)
        lst = pg.evaluate("() => document.getElementById('brakList').innerText")
        check("Q3 Omborchi loyihani tanladi → detallar ro'yxatda (asl: 403, «Bu loyihada detal topilmadi»)",
              "U174 B qaytarish detali" in lst and "topilmadi" not in lst, lst[:300])
        n0 = len(sorovlar("/api/returns"))
        pg.evaluate(f"""() => {{ const i = brakItems.findIndex(x => x.item_id === {ID['OBI']});
          document.querySelector('.brak-qty-inp[data-idx="' + i + '"]').value = '1';
          document.getElementById('brak-cause').value = 'boshqa'; }}""")
        baj(pg, "() => saveBrakBatch()", 1200)
        check("Q4 brak saqlandi (bitta so'rov, amal kaliti bilan), yozuv BITTA",
              len(sorovlar("/api/returns")[n0:]) == 1 and bool(KALIT_RE.match(sorovlar("/api/returns")[-1][3] or ""))
              and soni(ReturnItem, order_id=ID["OB"]) == 1, (sorovlar("/api/returns")[n0:], soni(ReturnItem, order_id=ID["OB"])))
    except Exception as _e:              # noqa: BLE001 — asl kodda (zip 173) element / funksiya yo'q bo'lishi mumkin: test QULAMAYDI
        check("bo'lim kutilmagan istisno bilan to'xtadi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("R. «Yangi qaytarish» — eski javob yangi tanlovni bosmaydi (C#13)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/returns")
        pg.evaluate("() => { showAddModal(); return qaytarishBuyurtmalariniYukla(); }")
        kut = []
        _hk = lambda r: kut.append(r)                                                               # noqa: E731
        pg.route(f"**/api/tanlov/buyurtmalar/{ID['OA']}/detallar", _hk)
        pg.evaluate(f"() => {{ document.getElementById('f-order').value = '{ID['OA']}'; onOrderChange(); }}")
        pg.wait_for_timeout(300)
        pg.evaluate(f"() => {{ document.getElementById('f-order').value = '{ID['OB']}'; return onOrderChange(); }}")
        pg.wait_for_timeout(400)
        for r in kut:
            r.continue_()
        pg.wait_for_timeout(800)
        opt = pg.evaluate("() => Array.from(document.getElementById('f-item').options).map(o => o.textContent).join(' | ')")
        check("R1 A so'rovi kech keldi (B tanlangandan keyin) → ro'yxatda B detali, A detali YO'Q (asl: A detallari B ostida)",
              len(kut) == 1 and "U174 B qaytarish detali" in opt and "U174 A qaytarish detali" not in opt, (len(kut), opt))
        pg.unroute(f"**/api/tanlov/buyurtmalar/{ID['OA']}/detallar", _hk)
        _h5 = lambda r: r.fulfill(status=500, content_type="application/json",                     # noqa: E731
                                  body='{"detail":"Serverda kutilmagan xato yuz berdi"}')
        pg.route(f"**/api/tanlov/buyurtmalar/{ID['OA']}/detallar", _h5)
        pg.evaluate(f"() => {{ document.getElementById('f-order').value = '{ID['OA']}'; return onOrderChange(); }}")
        pg.wait_for_timeout(300)
        opt = pg.evaluate("() => Array.from(document.getElementById('f-item').options).map(o => o.textContent).join(' | ')")
        check("R2 detallar yuklanmadi → sabab («Detallar yuklanmadi — server javob bermadi …»), yolg'on «detal yo'q» EMAS",
              "Detallar yuklanmadi" in opt and "detal yo'q" not in opt, opt)
    except Exception as _e:              # noqa: BLE001 — asl kodda (zip 173) element / funksiya yo'q bo'lishi mumkin: test QULAMAYDI
        check("bo'lim kutilmagan istisno bilan to'xtadi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("D. «Qarzdorlar» — kategoriya, majburiyat to'lovi, o'chirish sababi (B#4, C#18, C#19)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/debts")
        k0 = soni(RecurringObligation, company_id=1)
        pg.evaluate("() => { document.getElementById('cat-label').value = 'U174 Kommunal'; document.getElementById('cat-target').value = '500 000';"
                    " document.getElementById('cat-dueday').value = '7'; document.getElementById('cat-icon').value = '💡'; }")
        n0 = len(sorovlar("/api/obligations/recurring"))
        baj(pg, "() => { saveNewCategory(); return saveNewCategory(); }", 1200)
        check("D1 «+ Kategoriya» ikki marta → BITTA so'rov, BITTA kategoriya (asl: 2 — kod har bosishda yangi)",
              len(sorovlar("/api/obligations/recurring")[n0:]) == 1 and soni(RecurringObligation, company_id=1) == k0 + 1,
              (sorovlar("/api/obligations/recurring")[n0:], soni(RecurringObligation, company_id=1), k0))
        ochiq(pg, "/debts")
        x0 = soni(ExpenseTransaction, category="u174_kat")
        pg.evaluate("() => { window.__kirit = '150 000'; }")
        h = Bajar502()
        pg.route("**/api/finance/transactions", h)
        n0 = len(sorovlar("/api/finance/transactions"))
        baj(pg, "() => quickPayObligation('u174_kat', 'U174 ijara', 300000)")
        m1 = msg(pg)
        pg.unroute("**/api/finance/transactions", h)
        baj(pg, "() => quickPayObligation('u174_kat', 'U174 ijara', 300000)", 1200)
        _x = sorovlar("/api/finance/transactions")[n0:]
        check("D2 majburiyat to'lovi: 502 (server bajardi) → «To'lov natijasi noma'lum» (asl: «❌ Xato yuz berdi»); qayta → o'sha"
              " kalit; xarajat BITTA (asl: 2 × 150 000)",
              h.holat == [200] and any(NOMALUM in x[0] and "To'lov" in x[0] for x in m1) and len(_x) == 2 and _x[0][3] == _x[1][3]
              and soni(ExpenseTransaction, category="u174_kat") == x0 + 1, (h.holat, m1, _x, soni(ExpenseTransaction, category="u174_kat")))
    except Exception as _e:              # noqa: BLE001 — asl kodda (zip 173) element / funksiya yo'q bo'lishi mumkin: test QULAMAYDI
        check("bo'lim kutilmagan istisno bilan to'xtadi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    finally:
        ctx.close()
    ctx, pg = kontekst("u174_mol")
    try:
        ochiq(pg, "/debts")
        baj(pg, f"() => deleteCategory({ID['KAT']}, 'U174 ijara')")
        m1 = msg(pg)
        check("D3 Moliyachi kategoriyani o'chirmoqchi (server 403) → «❌ Kategoriya o'chirilmadi: <sabab>» (asl: «Xato yuz berdi»)",
              any(x[0].startswith("❌ Kategoriya o'chirilmadi: ") and len(x[0]) > len("❌ Kategoriya o'chirilmadi: ") + 3
                  and "Xato yuz berdi" not in x[0] for x in m1) and soni(RecurringObligation, id=ID["KAT"]) == 1, m1)
    except Exception as _e:              # noqa: BLE001 — asl kodda (zip 173) element / funksiya yo'q bo'lishi mumkin: test QULAMAYDI
        check("bo'lim kutilmagan istisno bilan to'xtadi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("X. «Moliya» va «Kunlik xarajat» — yangi xarajat (A)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/finance")
        x0 = soni(ExpenseTransaction, category="tushlik")
        tx_och = ("() => { document.getElementById('tx-f-editing-id').value = ''; document.getElementById('tx-f-date').value = tkISO();"
                  " document.getElementById('tx-f-category').value = 'tushlik'; document.getElementById('tx-f-amount').value = '77 000';"
                  " document.getElementById('tx-f-notes').value = 'U174 moliya'; }")
        pg.evaluate(tx_och)
        h = Bajar502()
        pg.route("**/api/finance/transactions", h)
        n0 = len(sorovlar("/api/finance/transactions"))
        baj(pg, "() => saveTx()")
        m1 = msg(pg)
        pg.unroute("**/api/finance/transactions", h)
        baj(pg, "() => saveTx()")
        m2 = msg(pg)
        _x = sorovlar("/api/finance/transactions")[n0:]
        check("X1 Moliya: 502 (server bajardi) → «Xarajat natijasi noma'lum» (asl: sababsiz «❌ Saqlanmadi» — qayta saqlashga undardi);"
              " qayta → takror; xarajat BITTA",
              h.holat == [200] and any(NOMALUM in x[0] for x in m1) and len(_x) == 2 and _x[0][3] == _x[1][3]
              and any(TAKROR in x[0] for x in m2) and soni(ExpenseTransaction, category="tushlik") == x0 + 1,
              (h.holat, m1, m2, _x, soni(ExpenseTransaction, category="tushlik"), x0))
        ochiq(pg, "/kunlik-xarajat")
        x0 = soni(ExpenseTransaction, category="kutilmagan")
        pg.evaluate("() => { document.getElementById('kx-date').value = tkISO(); document.getElementById('kx-category').value = 'kutilmagan';"
                    " document.getElementById('kx-amount').value = '33 000'; document.getElementById('kx-notes').value = 'U174 kunlik'; }")
        h = Bajar502()
        pg.route("**/api/finance/transactions", h)
        n0 = len(sorovlar("/api/finance/transactions"))
        baj(pg, "() => kxSave()")
        e1 = pg.evaluate("() => document.getElementById('kx-error').textContent")
        pg.unroute("**/api/finance/transactions", h)
        baj(pg, "() => kxSave()")
        ok2 = pg.evaluate("() => document.getElementById('kx-success').textContent")
        _x = sorovlar("/api/finance/transactions")[n0:]
        check("X2 Kunlik xarajat: 502 (server bajardi) → «Xarajat natijasi noma'lum» (asl: «❌ Xato yuz berdi»); qayta → «✓ Saqlandi …"
              " ikkinchi marta yozilmadi»; xarajat BITTA",
              h.holat == [200] and NOMALUM in (e1 or "") and len(_x) == 2 and _x[0][3] == _x[1][3]
              and (ok2 or "").startswith("✓ Saqlandi") and TAKROR in (ok2 or "")
              and soni(ExpenseTransaction, category="kutilmagan") == x0 + 1, (h.holat, e1, ok2, _x))
    except Exception as _e:              # noqa: BLE001 — asl kodda (zip 173) element / funksiya yo'q bo'lishi mumkin: test QULAMAYDI
        check("bo'lim kutilmagan istisno bilan to'xtadi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    finally:
        ctx.close()

    check("Z1 sahifalarda JS xatosi yo'q", not JS_XATO, JS_XATO[:5])

if br:
    br.close()
if pw_ctx:
    pw_ctx.stop()
server.should_exit = True
print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
