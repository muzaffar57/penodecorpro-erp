#!/usr/bin/env python3
"""
test_buyurtma_ui173.py — kech144 (zip 173): «Buyurtmalar» va «Qarzdorlar» sahifalari — HAQIQIY Chromium, HAQIQIY lokal server
(uvicorn, test bazasi). Tarmoq xatolari Playwright `route` bilan ataylab beriladi (500 / 502 / javobni kechiktirish).

NIMA UCHUN KERAK (O'LCHANGAN — `work/k173/probe_buyurtma.py`, asl kod = zip 172; natija `work/natija/k173/probe_asl.json`)
  V1   B buyurtma ma'lumoti yuklanmasa to'lov panelida A ning qarzi (1 000 000) qolardi — «To'liq qarz» / «qolganini kechirish» shu
       qarzdan hisoblanardi.
  V1b  A ning javobi kech kelsa, B tanlangan bo'lsa ham A ning detallari va qarzi B sarlavhasi ostida chizilardi.
  V2   Tahrirda loy rejasi (`/planned-loy`) yuklanmasa maydon bo'sh qolib, saqlash `loy_kg=0` yuborardi (30 kg omborga qaytardi).
  V2b  C (loy 30) tahriri yopilib D (loy 0) tahrirlansa — maydonda 30 qolib, saqlashda D ga 30 kg yozilardi.
  V3   O'chirishda ma'lumot so'rovi yiqilsa tasdiq faqat «6 o'chirilsinmi?» derdi — to'lov ham o'chishi ogohlantirilmasdi.
  V4   Yangi buyurtma: server saqlab, javob 502 bo'lsa «❌ Buyurtma saqlanmadi», qayta bosish ikkinchi buyurtma yaratardi.
  V5   «Bir yo'la to'liq topshirish»: qarz yuklanmasa «✓ Qarzi yo'q (to'liq to'langan)» (yolg'on 0).
  V6   Tahrir yopilib «+ Yangi buyurtma» bosilsa — forma tahrirlangan buyurtma ma'lumoti bilan ochilardi.
  QAROR «So'rasin» (13.10): «Bir yo'la to'liq topshirish» to'lov usuli va transportni kim to'laganini so'raydi (ilgari doim naqd /
       kompaniya); oyna faqat muvaffaqiyatda yopiladi.
  QAROR «Faqat ko'rsatilgani» (13.10): «Qarzdorlar» da qarz shu orada o'zgargan bo'lsa — hech narsa saqlanmaydi, sabab ko'rsatiladi.
  P1-3 MRP mahsuloti — Menejer tahriri turni / qoplamani / o'lchamni o'chirmaydi; P2-3 / P2-4 / P2-14 / P2-17 — qolgan audit bandlari.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 172) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_buyurtma_ui173.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "buyurtma_ui173_test"
_T = tempfile.mkdtemp(prefix="bui173_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'buyurtma_ui173.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Recipe, RecipeIngredient, Project, Order, Payment, Delivery   # noqa: E402
from production_models import ProductType          # noqa: E402
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
    auth.create_user(s, "u173_admin", PAROL, UserRole.ADMIN, "U173 Admin", company_id=1)
    auth.create_user(s, "u173_men", PAROL, UserRole.MANAGER, "U173 Menejer", company_id=1)
PENO = Inventory(company_id=1, item_name="U173 Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="U173 Kley", unit="kg", stock_quantity=10000, price_per_unit=2000, category="Kimyo")
s.add_all([PENO, KLEY])
s.flush()
REC = Recipe(company_id=1, name="U173 retsept", batch_size_kg=100.0)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
PRJ = Project(company_id=1, client_name="U173 Mijoz", project_name="U173 loyiha", total_budget=0, total_paid=0)
PT = ProductType(company_id=1, name="U173 Travertin", unit="m²", input_template="area_2d", pricing_formula="per_area",
                 supports_coating=True, coating_price_multiplier=2, is_active=True)
PT2 = ProductType(company_id=1, name="U173 Eski tur", unit="dona", input_template="dimensional_3d", pricing_formula="per_volume",
                  supports_coating=True, coating_price_multiplier=2, is_active=True)
s.add_all([PRJ, PT, PT2])
s.commit()
ID = {"PENO": PENO.id, "KLEY": KLEY.id, "REC": REC.id, "P": PRJ.id, "PT": PT.id, "PT2": PT2.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert C.post("/login", data={"username": "u173_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)


def bu(nom, narx, n, **k):
    it = {"name": nom, "category": "panel", "width": 50, "thickness": 5, "quantity": n, "unit_price": narx, "is_coated": False}
    t = {"project_id": ID["P"], "order_type": "product", "items": [it]}
    t.update(k)
    r = C.post("/api/orders?confirm_shortage=true", json=t)
    assert r.status_code == 200, r.text
    return r.json()["id"]


ID["A"] = bu("U173 A detal", 100000, 10)
ID["B"] = bu("U173 B detal", 1000000, 5)
_itc = {"name": "U173 C qoplamali", "category": "panel", "width": 50, "thickness": 5, "quantity": 10, "unit_price": 30000,
        "is_coated": True, "penoplast_id": ID["PENO"]}
for _n in ("C", "C2"):
    _r = C.post("/api/orders?confirm_shortage=true", json={"project_id": ID["P"], "order_type": "product",
                                                         "items": [dict(_itc, name=f"U173 {_n} qoplamali")],
                                                         "recipe_id": ID["REC"], "loy_kg": 30.0})
    assert _r.status_code == 200, _r.text
    ID[_n] = _r.json()["id"]
ID["D"] = bu("U173 D detal", 20000, 3)
ID["E"] = bu("U173 E detal", 50000, 4)
assert C.post("/api/payments", json={"order_id": ID["E"], "amount": 70000, "payment_type": "partial",
                                      "payment_method": "naqd"}).status_code == 200
ID["F"] = bu("U173 F detal", 10000, 5)          # «Bir yo'la to'liq topshirish» — qaror
ID["G"] = bu("U173 G detal", 380000, 1)         # Qarzdorlar — qarz o'zgargan
ID["H"] = bu("U173 H detal", 10000, 2)          # «Tayyor» oynasi
_rm = C.post("/api/orders?confirm_shortage=true", json={"project_id": ID["P"], "order_type": "product", "items": [
    {"name": "U173 MRP Travertin", "category": "mrp_product", "width": 2, "length": 3, "quantity": 6, "unit_price": 50000,
     "is_coated": True, "product_type_id": ID["PT"]}]})
assert _rm.status_code == 200, _rm.text
ID["M"] = _rm.json()["id"]
_rm2 = C.post("/api/orders?confirm_shortage=true", json={"project_id": ID["P"], "order_type": "product", "items": [
    {"name": "U173 MRP eski", "category": "mrp_product", "width": 1, "thickness": 2, "length": 3, "quantity": 4, "unit_price": 7000,
     "is_coated": True, "product_type_id": ID["PT2"]}]})
assert _rm2.status_code == 200, _rm2.text
ID["M2"] = _rm2.json()["id"]
s = SessionLocal()
s.query(ProductType).filter(ProductType.id == ID["PT2"]).update({"is_active": False})   # tur keyin «o'chirilgan» (faol emas)
s.commit()
s.close()


def api(path):
    r = C.get(path)
    return r.status_code, js(r)


def tolovlar(oid):
    d = SessionLocal()
    try:
        return [(float(p.amount), getattr(p.payment_method, "value", p.payment_method))
                for p in d.query(Payment).filter(Payment.order_id == oid).order_by(Payment.id)]
    finally:
        d.close()


def buyurtmalar_soni():
    d = SessionLocal()
    try:
        return d.query(Order).filter(Order.company_id == 1).count()
    finally:
        d.close()


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
JS_XATO, SOROV = [], []


def kontekst(user="u173_admin"):
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""), q.post_data))
          if "/api/" in q.url and q.method in ("POST", "PUT", "DELETE") else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


# Xabarlar va tasdiq oynalari: `window.__msg` / `window.__tasdiq`; tasdiq javobi — `window.__ha` (standart: true)
ILGAK = """() => { window.__msg = []; window.__tasdiq = []; window.__ha = true;
  window.showMsg = (t, ty) => { window.__msg.push([String(t), ty]); };
  window.showConfirmModal = async (m) => { window.__tasdiq.push(String(m)); return window.__ha; };
  window.customConfirm = async (a, b) => { window.__tasdiq.push(String(a) + (typeof b === 'string' ? ' | ' + b : '')); return window.__ha; }; }"""
HOLAT = """() => { const d = document.getElementById('pay-debt');
  return {sel: typeof selectedOrderId !== 'undefined' ? selectedOrderId : null, num: (document.getElementById('s-num') || {}).textContent,
          qarz_matn: d && d.textContent, qarz: d && d.dataset.qarz, joriy: (typeof _joriyQarz === 'function') ? _joriyQarz() : 'yoq',
          detallar: ((document.getElementById('od-items-container') || {}).innerText || '').slice(0, 160)}; }"""
XATO_500 = {"status": 500, "content_type": "application/json", "body": '{"detail":"Serverda kutilmagan xato yuz berdi"}'}


def ochiq(pg, oid):
    pg.goto(f"{B}/orders?order={oid}", wait_until="networkidle")
    pg.wait_for_timeout(500)
    pg.evaluate(ILGAK)


def msg(pg):
    return pg.evaluate("() => window.__msg || []")


def sorovlar(pg, nima):
    return [x for x in SOROV if nima in x[1]]


def saqla_kut(pg, js):
    """`updateOrder` muvaffaqiyatda sahifani 3 s dan keyin qayta yuklaydi — keyingi `goto` u bilan to'qnashmasin (sekin
    mashinada ERR_ABORTED): qayta yuklanish tugashini kutadi (bo'lmasa — 12 s dan keyin davom)."""
    try:
        with pg.expect_navigation(timeout=12000):
            pg.evaluate(js)
    except Exception:                      # noqa: BLE001 — saqlanmadi (qayta yuklanish yo'q) — tekshiruv o'zi ko'rsatadi
        pass
    try:
        pg.wait_for_load_state("networkidle")
    except Exception:                      # noqa: BLE001
        pass


if br:
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V1 / V1b — to'lov paneli boshqa buyurtma qarzini ko'rsatmaydi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["A"])
        h0 = pg.evaluate(HOLAT)
        check("V1a fikstura: A tanlangan, qarz 1 000 000 (data-qarz)", h0["qarz"] == "1000000" and h0["joriy"] == 1000000, h0)
        _h = lambda r: r.fulfill(**XATO_500)                                                  # noqa: E731
        pg.route(f"**/api/orders/{ID['B']}", _h)
        pg.evaluate(f"() => selectOrder({ID['B']}, document.getElementById('oi-{ID['B']}'))")
        pg.wait_for_timeout(1500)
        h1 = pg.evaluate(HOLAT)
        check("V1 B yuklanmadi → to'lov paneli «—», qarz NOMA'LUM (null) — A ning 1 000 000 qolmaydi (asl: 1 000 000)",
              str(h1["sel"]) == str(ID["B"]) and h1["qarz_matn"] == "—" and h1["qarz"] == "" and h1["joriy"] is None, h1)
        check("V1c detallar o'rnida sabab («Detallar yuklanmadi — server javob bermadi»), A detali YO'Q",
              "Detallar yuklanmadi" in h1["detallar"] and "U173 A" not in h1["detallar"], h1)
        pg.evaluate("() => { openPaymentForm(); fillFullDebt(); }")
        _f = pg.evaluate("() => document.getElementById('pf-amount').value")
        check("V1d «To'liq qarz» → maydon bo'sh, xabar «Qarz hali yuklanmagan»", _f == ""
              and any("hali yuklanmagan" in m[0] for m in msg(pg)), (_f, msg(pg)))
        n0 = len(sorovlar(pg, "/api/payments"))
        pg.evaluate("() => { document.getElementById('pf-amount').value = '100 000'; const w = document.getElementById('pf-writeoff');"
                    " if (w) w.checked = true; return savePayment(); }")
        pg.wait_for_timeout(600)
        check("V1e to'lov + «chegirma» → so'rov YO'Q, sabab «qarzi hali yuklanmagan» (asl: A qarzidan 900 000 kechirilardi)",
              len(sorovlar(pg, "/api/payments")) == n0 and any("qarzi hali yuklanmagan" in m[0] for m in msg(pg)), msg(pg))
        pg.unroute(f"**/api/orders/{ID['B']}", _h)
        # V1f — B javobi hali kelmagan (yuklanmoqda): panelda A ning qarzi ko'rinmaydi, «To'liq qarz» uni yozmaydi
        ochiq(pg, ID["A"])
        kut = []
        _hk = lambda r: kut.append(r)                                                           # noqa: E731
        pg.route(f"**/api/orders/{ID['B']}", _hk)
        pg.evaluate(f"() => {{ selectOrder({ID['B']}, document.getElementById('oi-{ID['B']}')); }}")
        pg.wait_for_timeout(400)
        h1f = pg.evaluate(HOLAT)
        pg.evaluate("() => { openPaymentForm(); fillFullDebt(); }")
        _f1 = pg.evaluate("() => document.getElementById('pf-amount').value")
        check("V1f B yuklanayotganda — panel «—», qarz NOMA'LUM, «To'liq qarz» A ning 1 000 000 ini yozmaydi",
              h1f["qarz_matn"] == "—" and h1f["joriy"] is None and _f1 == "", (h1f, _f1))
        pg.unroute(f"**/api/orders/{ID['B']}", _hk)
        for r in kut:
            try:
                r.continue_()
            except Exception:              # noqa: BLE001
                pass
        pg.wait_for_timeout(1200)
        # V1b — A javobi kechikadi, B tanlanadi
        ochiq(pg, ID["D"])
        ush = []
        _hA = lambda r: ush.append(r)                                                          # noqa: E731
        pg.route(f"**/api/orders/{ID['A']}", _hA)
        pg.evaluate(f"() => selectOrder({ID['A']}, document.getElementById('oi-{ID['A']}'))")
        pg.wait_for_timeout(300)
        pg.evaluate(f"() => selectOrder({ID['B']}, document.getElementById('oi-{ID['B']}'))")
        pg.wait_for_timeout(1500)                       # B chizildi; A ning javoblari HALI ushlab turilibdi
        for r in ush:
            try:
                r.continue_()                           # A ning javoblari endi — B tanlanganidan KEYIN keladi
            except Exception:              # noqa: BLE001
                pass
        pg.wait_for_timeout(1500)
        pg.unroute(f"**/api/orders/{ID['A']}", _hA)
        h2 = pg.evaluate(HOLAT)
        check("V1b A javobi B tanlangandan KEYIN keldi → panel va detallar B niki (5 000 000, «U173 B»; asl: A ning 1 000 000)",
              len(ush) >= 1 and str(h2["sel"]) == str(ID["B"]) and h2["qarz"] == "5000000" and "U173 B" in h2["detallar"]
              and "U173 A" not in h2["detallar"], (len(ush), h2))
    except Exception as _e:                # noqa: BLE001
        check("V1! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V2 / V2b / V6 / P2-17 — tahrir: loy rejasi, yangi forma, «1 m³ asosiy narxi»")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["C"])
        _h2 = lambda r: r.fulfill(**XATO_500)                                                 # noqa: E731
        pg.route(f"**/api/orders/{ID['C']}/planned-loy", _h2)
        SOROV.clear()
        pg.evaluate("() => editSelected()")
        pg.wait_for_timeout(2000)
        _f = pg.evaluate("() => ({ko: getComputedStyle(document.getElementById('newOrderForm')).display, edit: editMode,"
                         " tugma: (document.querySelector('#newOrderForm .btn-dark') || {}).textContent})")
        check("V2 loy rejasi yuklanmadi → tahrir OCHILMADI (forma yopiq, tahrir rejimi yo'q), sabab ko'rsatildi",
              _f["ko"] == "none" and _f["edit"] is False and any("Tahrirlash ochilmadi: loy rejasi yuklanmadi" in m[0] for m in msg(pg)),
              (_f, msg(pg)))
        check("V2b saqlash tugmasi tahrirga ulanmagan («Buyurtmani saqlash»), PUT YO'Q, loy rejasi 30 (asl: 0 ga tushardi)",
              "Buyurtmani saqlash" in (_f["tugma"] or "") and not sorovlar(pg, f"/api/orders/{ID['C']}")
              and api(f"/api/orders/{ID['C']}/planned-loy")[1].get("planned_loy") == 30, (_f, SOROV))
        pg.unroute(f"**/api/orders/{ID['C']}/planned-loy", _h2)
        # V2b — C2 (30) tahriri yopiladi, D (0) tahrirlanadi
        ochiq(pg, ID["C2"])
        pg.evaluate("() => editSelected()")
        pg.wait_for_timeout(2000)
        _c2 = pg.evaluate("() => document.getElementById('loy_kg').value")
        pg.evaluate("() => hideNewForm()")
        pg.evaluate(f"() => selectOrder({ID['D']}, document.getElementById('oi-{ID['D']}'))")
        pg.wait_for_timeout(1200)
        pg.evaluate("() => editSelected()")
        pg.wait_for_timeout(2000)
        _d = pg.evaluate("() => document.getElementById('loy_kg').value")
        check("V2c C2 tahririda loy 30; yopilib D (reja 0) tahrirlansa maydon BO'SH (asl: 30 qolardi)", _c2 == "30" and _d == "", (_c2, _d))
        SOROV.clear()
        saqla_kut(pg, f"() => updateOrder({ID['D']})")
        _put = [x for x in sorovlar(pg, f"/api/orders/{ID['D']}") if x[0] == "PUT"]
        check("V2d D saqlandi — `loy_kg=0`, D ning loy rejasi 0 (asl: 30 kg D ga yozilardi)",
              len(_put) == 1 and "loy_kg=0" in _put[0][1] and api(f"/api/orders/{ID['D']}/planned-loy")[1].get("planned_loy") == 0,
              (_put, api(f"/api/orders/{ID['D']}/planned-loy")))
        # V2e — yangi formada loy yozilgan (tahrir emas), so'ng reja 0 bo'lgan buyurtma tahrirlanadi — maydon BO'SH (eski qiymat qolmaydi)
        ochiq(pg, ID["D"])
        pg.evaluate("() => { showNewForm(); document.getElementById('loy_kg').value = '25'; }")
        pg.evaluate(f"() => selectOrder({ID['D']}, document.getElementById('oi-{ID['D']}'))")
        pg.wait_for_timeout(1000)
        pg.evaluate("() => editSelected()")
        pg.wait_for_timeout(2000)
        _e = pg.evaluate("() => document.getElementById('loy_kg').value")
        check("V2e yangi formada yozilgan 25 kg — reja 0 bo'lgan buyurtma tahririda maydon BO'SH (asl: 25 qolib, saqlashda yozilardi)",
              _e == "", _e)
        pg.evaluate("() => hideNewForm()")
        # V6 — tahrirdan keyin yangi forma bo'sh
        ochiq(pg, ID["C2"])
        pg.evaluate("() => editSelected()")
        pg.wait_for_timeout(2000)
        pg.evaluate("() => hideNewForm()")
        pg.evaluate("() => showNewForm()")
        pg.wait_for_timeout(800)
        _v6 = pg.evaluate("""() => ({nomlar: [...document.querySelectorAll('#items .detal .i-name')].map(e => e.value),
            loy: document.getElementById('loy_kg').value, kel: document.getElementById('final_price').value,
            loyiha: document.getElementById('project_id').value, retsept: (document.getElementById('recipe_id') || {}).value,
            kalit: window._yaratishKaliti || ''})""")
        check("V6 tahrir yopilib «+ Yangi buyurtma» — forma BO'SH (detal nomi, loy, kelishilgan, loyiha, retsept; asl: C2 ma'lumoti)",
              all(n == "" for n in _v6["nomlar"]) and _v6["loy"] == "" and _v6["kel"] == "" and _v6["loyiha"] == ""
              and not _v6["retsept"], _v6)
        k1 = _v6["kalit"]
        pg.evaluate("() => hideNewForm()")
        pg.evaluate("() => showNewForm()")
        k2 = pg.evaluate("() => window._yaratishKaliti || ''")
        check("V6b har yangi forma — yangi forma kaliti (8–64 belgi, harf / raqam)",
              bool(re.fullmatch(r"[A-Za-z0-9_-]{8,64}", k1 or "")) and bool(re.fullmatch(r"[A-Za-z0-9_-]{8,64}", k2 or "")) and k1 != k2,
              (k1, k2))
        # P2-17 — «1 m³ asosiy narxi» yozilgan forma, keyin asosiy narxsiz buyurtma tahriri
        # foydalanuvchi yangi formada narx yozdi, keyin ro'yxatdan buyurtmani tanlab «Tahrirlash» ni bosdi
        ochiq(pg, ID["A"])
        pg.evaluate("() => { showNewForm(); document.getElementById('base_price').value = '777 000'; }")
        pg.evaluate(f"() => selectOrder({ID['A']}, document.getElementById('oi-{ID['A']}'))")
        pg.wait_for_timeout(1000)
        pg.evaluate("() => editSelected()")
        pg.wait_for_timeout(2000)
        _bp = pg.evaluate("() => document.getElementById('base_price').value")
        check("P2-17 asosiy narxsiz buyurtma tahriri — «1 m³ asosiy narxi» BO'SH (asl: oldingi forma 777 000 qolardi)", _bp == "", _bp)
    except Exception as _e:                # noqa: BLE001
        check("V2! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V3 / V5 / P2-4 — ma'lumot yuklanmasa: o'chirish, «Bir yo'la to'liq topshirish», «Tayyor»")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["E"])
        _h3 = lambda r: r.fulfill(**XATO_500) if r.request.method == "GET" else r.continue_()   # noqa: E731
        pg.route(f"**/api/orders/{ID['E']}", _h3)
        SOROV.clear()
        pg.evaluate("() => { window.__ha = false; }")          # asl kod tasdiq so'raydi — «Bekor» (buyurtma o'chmasin)
        pg.evaluate("() => deleteSelected()")
        pg.wait_for_timeout(1500)
        check("V3 o'chirish: ma'lumot yuklanmadi → tasdiq YO'Q, DELETE YO'Q, sabab (asl: «6 o'chirilsinmi?» — to'lov ogohlantirishsiz)",
              pg.evaluate("() => window.__tasdiq") == [] and not [x for x in SOROV if x[0] == "DELETE"]
              and any("ma'lumoti yuklanmadi" in m[0] for m in msg(pg)), (pg.evaluate("() => window.__tasdiq"), msg(pg)))
        pg.unroute(f"**/api/orders/{ID['E']}", _h3)
        ochiq(pg, ID["E"])
        pg.evaluate("() => { window.__ha = false; }")
        pg.evaluate("() => deleteSelected()")
        pg.wait_for_timeout(1500)
        _t = pg.evaluate("() => window.__tasdiq")
        check("V3b nazorat: ma'lumot bor — tasdiqda to'lov ogohlantirishi (70 000 … AVTOMATIK o'chadi)",
              len(_t) == 1 and "AVTOMATIK" in _t[0] and "70 000" in _t[0].replace("\xa0", " "), _t)   # kech150 (zip 190, MOSLANDI)
    except Exception as _e:                # noqa: BLE001
        check("V3! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    ctx, pg = kontekst()
    try:
        # V5
        ochiq(pg, ID["B"])
        _h5 = lambda r: r.fulfill(**XATO_500)                                                 # noqa: E731
        pg.route(f"**/api/orders/{ID['B']}", _h5)
        pg.evaluate("() => quickFullDelivery()")
        pg.wait_for_timeout(1500)
        _v5 = pg.evaluate("() => ({ko: getComputedStyle(document.getElementById('fullDlvModalOverlay')).display,"
                          " matn: document.getElementById('fullDlvModalBody').innerText})")
        check("V5 «Bir yo'la to'liq topshirish»: qarz yuklanmadi → «Mijoz qarzi yuklanmadi — …», «Qarzi yo'q» YO'Q",
              _v5["ko"] == "flex" and "Mijoz qarzi yuklanmadi" in _v5["matn"] and "Qarzi yo'q" not in _v5["matn"], _v5)
        pg.unroute(f"**/api/orders/{ID['B']}", _h5)
        pg.evaluate("() => closeFullDlvModal()")
    except Exception as _e:                # noqa: BLE001
        check("V5! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    ctx, pg = kontekst()
    try:
        # P2-4 — «Tayyor» oynasi
        ochiq(pg, ID["H"])
        _h6 = lambda r: r.fulfill(**XATO_500)                                                 # noqa: E731
        pg.route(f"**/api/orders/{ID['H']}/planned-loy", _h6)
        pg.evaluate("() => markReadySelected()")
        pg.wait_for_timeout(1500)
        _rm = pg.evaluate("""() => ({ko: getComputedStyle(document.getElementById('readyModalOverlay')).display,
            xato: (document.getElementById('readyModalXato') || {}).innerText || '', ok: document.getElementById('readyModalOk').disabled,
            tana: document.getElementById('readyModalBody').innerText})""")
        check("P2-4 «Tayyor»: loy rejasi yuklanmadi → oynada sabab, «Tasdiqlash» YOPIQ, «Bo'sh qoldirsangiz …» (yolg'on) YO'Q",
              _rm["ko"] == "flex" and "yuklanmadi" in _rm["xato"] and _rm["ok"] is True and "Bo'sh qoldirsangiz" not in _rm["tana"], _rm)
        pg.unroute(f"**/api/orders/{ID['H']}/planned-loy", _h6)
        pg.evaluate("() => closeReadyModal()")
        pg.evaluate("() => markReadySelected()")
        pg.wait_for_timeout(1200)
        _rm2 = pg.evaluate("() => ({ok: document.getElementById('readyModalOk').disabled,"
                           " xato: getComputedStyle(document.getElementById('readyModalXato')).display})")
        check("P2-4b qayta ochilganda (yuklandi) — «Tasdiqlash» ochiq, xato qutisi yashirin", _rm2["ok"] is False and _rm2["xato"] == "none", _rm2)
        pg.evaluate("() => closeReadyModal()")
    except Exception as _e:                # noqa: BLE001
        check("P2-4! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V4 — yangi buyurtma: javob yo'qolsa (502) «natija noma'lum», qayta bosish takror YARATMAYDI")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["A"])
        pg.evaluate("() => showNewForm()")
        kalit = pg.evaluate("() => window._yaratishKaliti")
        n0 = buyurtmalar_soni()

        def _h4(r):
            if r.request.method != "POST":
                return r.continue_()
            r.fetch()                                       # server SAQLAYDI
            r.fulfill(status=502, content_type="text/html", body="<html><body>502 Bad Gateway</body></html>")
        pg.route(re.compile(r".*/api/orders(\?.*)?$"), _h4)
        TANA = {"project_id": ID["P"], "order_type": "product", "yaratish_kaliti": kalit,
                "items": [{"name": "U173 V4 detal", "category": "panel", "width": 50, "thickness": 5, "quantity": 2, "unit_price": 1000,
                           "is_coated": False}]}
        pg.evaluate("(t) => { window.__msg = []; return submitOrderRequest(t, false, 0, 'naqd', true); }", TANA)
        pg.wait_for_timeout(1000)
        n1 = buyurtmalar_soni()
        _m1 = msg(pg)
        check("V4 502 (server saqlagan) → «❌ Natija noma'lum — …», «saqlanmadi» EMAS (asl: «❌ Buyurtma saqlanmadi»)",
              n1 == n0 + 1 and any(m[0].startswith("❌ Natija noma'lum") for m in _m1) and not any("saqlanmadi" in m[0] for m in _m1),
              (n0, n1, _m1))
        pg.unroute(re.compile(r".*/api/orders(\?.*)?$"), _h4)
        _d = SessionLocal()
        _v4 = (_d.query(Order.id).filter(Order.yaratish_kaliti == kalit).scalar()
               if hasattr(Order, "yaratish_kaliti") else None)   # asl kodda ustun yo'q — yiqiladi (qulamaydi)
        _d.close()
        pg.evaluate("(t) => { window.__msg = []; submitOrderRequest(t, false, 0, 'naqd', true); }", TANA)
        pg.wait_for_timeout(400)
        _m2 = msg(pg)
        pg.wait_for_timeout(1500)
        pg.wait_for_load_state("networkidle")
        pg.wait_for_timeout(500)
        n2 = buyurtmalar_soni()
        _tan = pg.evaluate("() => typeof selectedOrderId !== 'undefined' ? selectedOrderId : null")
        check("V4b qayta bosish (o'sha forma kaliti) → YANGI buyurtma YO'Q, «avval saqlangan ekan — ochilmoqda», o'sha buyurtma ochildi "
              "(asl: 9 s dan keyin — ikkinchi buyurtma)",
              n2 == n1 and _v4 and str(_tan) == str(_v4) and any("avval saqlangan ekan" in m[0] for m in _m2), (n1, n2, _v4, _tan, _m2))
        # V4c — «💾 Buyurtmani saqlash» (`saveOrder`) forma kalitini yuboradi (server so'rovni rad etadi — buyurtma yaratilmaydi)
        pg.goto(f"{B}/orders", wait_until="networkidle")
        pg.wait_for_timeout(400)
        pg.evaluate(ILGAK)
        pg.evaluate("() => showNewForm()")
        TUT = []

        def _h4c(r):
            if r.request.method == "POST":
                TUT.append(r.request.post_data)
                return r.fulfill(status=400, content_type="application/json", body='{"detail":"Sinov: saqlanmaydi"}')
            return r.continue_()
        pg.route(re.compile(r".*/api/orders(\?.*)?$"), _h4c)
        pg.evaluate(f"""() => {{ const p = document.getElementById('project_id'); p.value = '{ID["P"]}'; p.dispatchEvent(new Event('change'));
            const d = document.getElementById('deadline_input'); if (d) d.value = '2026-12-01';
            const r = document.querySelector('#items .detal'); const t = r.querySelector('.type-opt[data-value="dona"]'); if (t) t.click();
            r.querySelector('.i-name').value = 'U173 kalit detal'; r.querySelector('.i-q').value = '2';
            const up = r.querySelector('.i-unitprice'); if (up) {{ up.value = '1 000'; up.dispatchEvent(new Event('input')); }} }}""")
        pg.evaluate("() => saveOrder(false)")
        pg.wait_for_timeout(1200)
        _k3 = pg.evaluate("() => window._yaratishKaliti || ''")
        _tb = json.loads(TUT[0]) if TUT and TUT[0] else {}
        check("V4c «💾 Buyurtmani saqlash» forma kalitini yuboradi (`yaratish_kaliti` = shu formaniki)",
              bool(_k3) and _tb.get("yaratish_kaliti") == _k3, (TUT[:1], _k3, msg(pg)))
        pg.unroute(re.compile(r".*/api/orders(\?.*)?$"), _h4c)
    except Exception as _e:                # noqa: BLE001
        check("V4! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("QAROR «So'rasin» — «Bir yo'la to'liq topshirish»: to'lov usuli va transportni kim to'lagani")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["F"])
        pg.evaluate("() => quickFullDelivery()")
        pg.wait_for_timeout(1200)
        _o = pg.evaluate("""() => ({usul: [...document.querySelectorAll('#fd-payment-method option')].map(o => o.value),
            tolovchi: [...document.querySelectorAll('#fd-transport-payer option')].map(o => o.value)})""")
        check("Q1 oynada to'lov usuli (naqd / plastik / o'tkazma) va transport to'lovchisi (— / mijoz / kompaniya / 50-50)",
              _o["usul"] == ["naqd", "plastik", "o'tkazma"] and _o["tolovchi"] == ["none", "client", "company", "split"], _o)
        pg.fill("#fd-payment", "20 000")
        pg.fill("#fd-transport", "30 000")
        SOROV.clear()
        pg.click("#fullDlvModalOverlay .btn-green")
        pg.wait_for_timeout(800)
        _e1 = pg.evaluate("() => ({ko: getComputedStyle(document.getElementById('fullDlvModalOverlay')).display,"
                          " xato: document.getElementById('fd-error').innerText, tolov: document.getElementById('fd-payment').value})")
        check("Q2 transport bor, kim to'lagani tanlanmagan → oyna OCHIQ, sabab oynada, kiritilgan to'lov saqlanib turibdi, so'rov YO'Q",
              _e1["ko"] == "flex" and "Transportni kim to'laganini tanlang" in _e1["xato"] and _e1["tolov"] == "20 000"
              and not sorovlar(pg, "/api/deliveries"), (_e1, SOROV))
        pg.select_option("#fd-transport-payer", "client")
        pg.select_option("#fd-payment-method", "plastik")
        with pg.expect_popup(timeout=8000) as _pp:
            pg.click("#fullDlvModalOverlay .btn-green")
        try:
            _pp.value.close()
        except Exception:                  # noqa: BLE001
            pass
        pg.wait_for_timeout(800)
        _post = sorovlar(pg, "/api/deliveries")
        _tana = json.loads(_post[0][2]) if _post and _post[0][2] else {}
        check("Q3 tanlangan qiymatlar yuborildi: transport_payer 'client', payment_method 'plastik' (asl: doim 'company' / 'naqd')",
              _tana.get("transport_payer") == "client" and _tana.get("payment_method") == "plastik"
              and _tana.get("transport_cost") == 30000 and _tana.get("payment_amount") == 20000, _tana)
        d = SessionLocal()
        _dl = d.query(Delivery).filter(Delivery.order_id == ID["F"]).all()
        _dlv = [(x.transport_payer, float(x.transport_cost or 0)) for x in _dl]
        d.close()
        check("Q4 bazada: yuk xati transport to'lovchisi «mijoz», to'lov 20 000 — PLASTIK",
              _dlv == [("client", 30000.0)] and tolovlar(ID["F"]) == [(20000.0, "plastik")], (_dlv, tolovlar(ID["F"])))
        _ko = pg.evaluate("() => getComputedStyle(document.getElementById('fullDlvModalOverlay')).display")
        check("Q5 muvaffaqiyatdan keyin oyna yopildi, yashil xabar", _ko == "none"
              and any("to'liq topshirildi" in m[0] for m in msg(pg)), (_ko, msg(pg)))
    except Exception as _e:                # noqa: BLE001
        check("Q! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("QAROR «Faqat ko'rsatilgani» — Qarzdorlar: qarz shu orada o'zgargan bo'lsa hech narsa saqlanmaydi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/debts", wait_until="networkidle")
        pg.wait_for_timeout(500)
        pg.evaluate(ILGAK)
        _bor = pg.evaluate(f"() => !!document.querySelector('#tab-customers .dbt-item[data-id=\"{ID['G']}\"]')")
        check("D0 G buyurtma (380 000) qarzdorlar ro'yxatida", _bor, _bor)
        pg.evaluate(f"() => selectOrderDebt(document.querySelector('#tab-customers .dbt-item[data-id=\"{ID['G']}\"]'), false)")
        pg.fill("#pay-amount", "10 000")
        pg.check("#pay-writeoff")
        _iz = pg.evaluate("() => document.getElementById('pay-writeoff-izoh').innerText")
        # shu orada (boshqa joyda) 50 000 to'lov yozildi — qarz 330 000 bo'ldi
        assert C.post("/api/payments", json={"order_id": ID["G"], "amount": 50000, "payment_type": "partial",
                                              "payment_method": "naqd"}).status_code == 200
        SOROV.clear()
        pg.click("#tab-customers button[onclick='savePayment()']")
        pg.wait_for_timeout(1500)
        _m = pg.evaluate("() => document.getElementById('pay-msg').innerText")
        _post = sorovlar(pg, "/api/payments")
        check("D1 oynada «Kechiriladi: 370 000», so'rovda kechirish=370000; server 409 → «Qarz o'zgargan … Sahifani yangilang»",
              "370 000" in _iz.replace(" ", " ").replace(" ", " ") and len(_post) == 1 and "kechirish=370000" in _post[0][1]
              and "Qarz o'zgargan" in _m and "Sahifani yangilang" in _m, (_iz, _post, _m))
        check("D2 bazada: faqat oraliq 50 000 to'lov (10 000 ham, kechirish ham YO'Q; asl: 320 000 jim kechirilardi)",
              tolovlar(ID["G"]) == [(50000.0, "naqd")] and abs(api(f"/api/orders/{ID['G']}")[1].get("agreed_amount", 0) - 380000) < 0.01,
              (tolovlar(ID["G"]), api(f"/api/orders/{ID['G']}")[1].get("agreed_amount")))
        pg.goto(B + "/debts", wait_until="networkidle")
        pg.wait_for_timeout(500)
        pg.evaluate(ILGAK)
        pg.evaluate(f"() => selectOrderDebt(document.querySelector('#tab-customers .dbt-item[data-id=\"{ID['G']}\"]'), false)")
        pg.fill("#pay-amount", "10 000")
        pg.check("#pay-writeoff")
        pg.click("#tab-customers button[onclick='savePayment()']")
        pg.wait_for_timeout(1500)
        _m2 = pg.evaluate("() => document.getElementById('pay-msg').innerText")
        check("D3 sahifa yangilangach (qarz 330 000) → 10 000 qabul, 320 000 kechirildi, qarz 0",
              "320 000" in _m2.replace(" ", " ").replace(" ", " ") and api(f"/api/orders/{ID['G']}")[1].get("debt_amount") == 0,
              (_m2, api(f"/api/orders/{ID['G']}")[1].get("debt_amount")))
    except Exception as _e:                # noqa: BLE001
        check("D! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("P1-3 / P2-3 — MRP mahsuloti: Menejer tahriri, o'chirilgan tur, ro'yxat yuklanmasa")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst("u173_men")
    try:
        ochiq(pg, ID["M"])
        pg.evaluate("() => editSelected()")
        pg.wait_for_timeout(2500)
        _r = pg.evaluate("""() => { const r = document.querySelector('#items .detal');
            return r ? {tur: r.dataset.mrpProductTypeId, shakl: r.dataset.mrpInputTemplate, q: r.dataset.mrpSupportsCoating,
                        h: r.querySelector('.i-h').value, l: r.querySelector('.i-l').value} : null; }""")
        check("M1 Menejer: MRP buyurtma tahriri — tur, shakl (2D), qoplama, o'lchamlar tiklandi (asl: 403 → hammasi bo'sh)",
              _r and _r["tur"] == str(ID["PT"]) and _r["shakl"] == "area_2d" and _r["q"] == "1" and _r["h"] == "2" and _r["l"] == "3", _r)
        SOROV.clear()
        saqla_kut(pg, f"() => updateOrder({ID['M']})")
        _put = [x for x in sorovlar(pg, f"/api/orders/{ID['M']}") if x[0] == "PUT"]
        _it = (json.loads(_put[0][2]).get("items") or [{}])[0] if _put and _put[0][2] else {}
        check("M2 saqlash: product_type_id, qoplama, eni / uzunligi SAQLANDI (asl: null / false / null)",
              _it.get("product_type_id") == ID["PT"] and _it.get("is_coated") is True and _it.get("width") == 2 and _it.get("length") == 3,
              (_put[:1], _it))
    except Exception as _e:                # noqa: BLE001
        check("M! ssenariy (Menejer)", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["M2"])
        pg.evaluate("() => editSelected()")
        pg.wait_for_timeout(2500)
        SOROV.clear()
        saqla_kut(pg, f"() => updateOrder({ID['M2']})")
        _put = [x for x in sorovlar(pg, f"/api/orders/{ID['M2']}") if x[0] == "PUT"]
        _it = (json.loads(_put[0][2]).get("items") or [{}])[0] if _put and _put[0][2] else {}
        check("M3 tur keyin faolsizlantirilgan (ro'yxatda yo'q) — saqlashda turi, qoplamasi, 3D o'lchamlari SAQLANADI",
              _it.get("product_type_id") == ID["PT2"] and _it.get("is_coated") is True and _it.get("width") == 1
              and _it.get("thickness") == 2 and _it.get("length") == 3, (_put[:1], _it))
        # P2-3 — ro'yxat yuklanmasa yolg'on «yaratilmagan» emas, sabab; keyingi urinish ishlaydi (bo'sh ro'yxat keshlanmaydi)
        pg.evaluate("() => hideNewForm()")
        ochiq(pg, ID["A"])
        pg.evaluate("() => { _mrpProductTypesCache = null; showNewForm(); }")
        _h7 = lambda r: r.fulfill(**XATO_500)                                                 # noqa: E731
        pg.route("**/api/production/product-types", _h7)
        pg.evaluate("() => openMrpProductPicker(document.querySelector('#items .detal .type-opt') || document.querySelector('#items .detal button'))")
        pg.wait_for_timeout(1000)
        _m = msg(pg)
        check("P2-3 ro'yxat yuklanmadi → «MRP mahsulot turlari yuklanmadi — …» (asl: «Hali … mahsulot turi yaratilmagan»)",
              any("MRP mahsulot turlari yuklanmadi" in m[0] for m in _m) and not any("yaratilmagan" in m[0] for m in _m), _m)
        pg.unroute("**/api/production/product-types", _h7)
        pg.evaluate("() => openMrpProductPicker(document.querySelector('#items .detal .type-opt') || document.querySelector('#items .detal button'))")
        pg.wait_for_timeout(1000)
        _ol = pg.evaluate("() => !!document.getElementById('mrpPickerList') && document.getElementById('mrpPickerList').innerText")
        check("P2-3b keyingi urinish — ro'yxat ochildi (xato keshlanmagan)", bool(_ol) and "U173 Travertin" in _ol, _ol)
        pg.evaluate("() => { const b = document.getElementById('mrpPickerCancel'); if (b) b.click(); }")
        # P2-14 — miqdor bo'sh
        pg.evaluate("() => { hideNewForm(); showNewForm(); }")
        pg.wait_for_timeout(500)
        pg.evaluate(f"""() => {{ const p = document.getElementById('project_id'); p.value = '{ID["P"]}'; p.dispatchEvent(new Event('change'));
            const r = document.querySelector('#items .detal'); const t = r.querySelector('.type-opt[data-value="dona"]'); if (t) t.click();
            r.querySelector('.i-name').value = 'U173 miqdorsiz'; r.querySelector('.i-q').value = ''; }}""")
        SOROV.clear()
        pg.evaluate("() => saveOrder(false)")
        pg.wait_for_timeout(800)
        _val = pg.evaluate("() => [...document.querySelectorAll('#validationList .val-item')].map(x => x.innerText.trim())")
        check("P2-14 miqdor bo'sh → saqlanmaydi, «… «Miqdor» kiritilmagan (0 dan katta bo'lsin)» (asl: JIM 1 bo'lib saqlanardi)",
              any("kiritilmagan (0 dan katta bo'lsin)" in v for v in _val) and not sorovlar(pg, "/api/orders"), (_val, SOROV))
    except Exception as _e:                # noqa: BLE001
        check("M! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    check("X1 sahifalarda JS xatosi yo'q", not JS_XATO, JS_XATO)
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
