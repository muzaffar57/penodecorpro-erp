#!/usr/bin/env python3
"""
test_mrp_qoplama_belgi.py — kech112 darvozasi: K112-5 — MRP ishlab chiqargan tayyor mahsulot DOIM «qoplamali» bo'lardi.

NIMA UCHUN KERAK (kech112 jonli C zanjirida topildi — «K112Z Travertin» (qoplamasiz tur) tayyor mahsuloti
`is_coated: true`; asl kod `5519200` da O'LCHANDI — `work/k113/probe_mrp_qoplama.py`, SQLite = PG):
`production_service.start_production_order` tayyor mahsulotni `is_coated` siz yaratardi — model standarti True.
Oylik hisobot (`services.get_monthly_report`) qoplamachi bonusiga va donabay hodim haqiga ("faqat HAQIQATAN
qoplamali") har MRP birligini (qoplamasiz travertin m², kafel kley kg ham) 1 000 so'mdan qo'shardi: 5 ta
ishlab chiqarishdan (20 birlik, 8 tasi haqiqatan qoplamali) bonus 20 000 o'rniga 8 000 bo'lishi kerak edi.

YECHIM (texnik — Claude): tayyor mahsulot `is_coated` = shu ishlab chiqarish suratida qoplama qatori HAQIQATAN
kiritilganmi (`included` va `is_coating` — brak sarfi `services._mrp_birlik_sarfi` bilan bir qoida). Buyurtma
detali qoplamali bo'lsa qoplama qatori o'zi tanlanadi (11.0-band), omborga — operator tanlovi.

BO'LIMLAR: Q — belgi (5 holat), H — oylik hisobot, S — statik.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
    python3 tools/test_mrp_qoplama_belgi.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_qoplama_belgi.py
Asl kodga qarshi QULAMAYDI (HTTP istisno → 599, yangi nomlar `getattr`). Chiqish kodi 0 — hammasi o'tdi.
"""
import os
import sys
import inspect
import tempfile
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_qoplama_belgi_test"
_T = tempfile.mkdtemp()
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'mrp_qoplama_belgi_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
    import production_service                      # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import UserRole, FinishedProduct       # noqa: E402
from production_models import ProductionOrder      # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        detail = f"{detail} [{type(e).__name__}: {e}]"
        cond = False
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:500]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Fikstura
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "MQB_A", "Parol123!", UserRole.ADMIN, "MRP Qoplama Admin", company_id=1)
_db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "MQB_A", "password": "Parol123!"}, follow_redirects=False)
check("F0 admin tizimga kirdi", _lr.status_code == 302, _lr.status_code)
XATO5 = []


def so(metod, url, **k):
    r = req(C, metod, url, **k)
    if r.status_code >= 500:
        XATO5.append((metod, url, r.status_code, getattr(r, "text", "")[:200]))
    return r


ID = {}
ID["qum"] = (js(so("post", "/api/inventory", json={"item_name": "MQB Qum", "unit": "kg", "stock_quantity": 1000,
                                                     "price_per_unit": 800})) or {}).get("id")
ID["kraska"] = (js(so("post", "/api/inventory", json={"item_name": "MQB Kraska", "unit": "kg", "stock_quantity": 1000,
                                                        "price_per_unit": 5000})) or {}).get("id")
ID["t1"] = (js(so("post", "/api/production/product-types", json={
    "name": "MQB Travertin", "unit": "m2", "input_template": "quantity_only", "pricing_formula": "unit_based",
    "supports_coating": False})) or {}).get("id")
ID["b1"] = (js(so("post", "/api/production/boms", json={
    "product_type_id": ID["t1"], "variant_name": "Standart", "batch_quantity": 1,
    "items": [{"inventory_id": ID["qum"], "quantity": 5}]})) or {}).get("id")
ID["t2"] = (js(so("post", "/api/production/product-types", json={
    "name": "MQB Dekor", "unit": "dona", "input_template": "quantity_only", "pricing_formula": "unit_based",
    "supports_coating": True, "coating_price_multiplier": 2})) or {}).get("id")
_b2 = js(so("post", "/api/production/boms", json={
    "product_type_id": ID["t2"], "variant_name": "Standart", "batch_quantity": 1,
    "items": [{"inventory_id": ID["qum"], "quantity": 2},
              {"inventory_id": ID["kraska"], "quantity": 0.5, "is_optional": True, "is_coating": True}]})) or {}
ID["b2"] = _b2.get("id")
ID["qopl"] = next((x.get("id") for x in (_b2.get("items") or []) if x.get("is_coating")), None)
ID["loyiha"] = (js(so("post", "/api/projects", json={"project_name": "MQB Loyiha", "client_name": "MQB Mijoz"})) or {}).get("id")
_o = js(so("post", "/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": ID["loyiha"], "order_type": "product", "deadline": "2026-10-10", "is_draft": False,
    "items": [{"name": "MQB Dekor Q", "category": "mrp_product", "quantity": 3, "unit_price": 50000, "is_coated": True,
               "product_type_id": ID["t2"]},
              {"name": "MQB Dekor", "category": "mrp_product", "quantity": 2, "unit_price": 25000, "is_coated": False,
               "product_type_id": ID["t2"]}]})) or {}
ID["o"] = _o.get("id")
_it = sorted(_o.get("items") or [], key=lambda x: x.get("id", 0))
ID["d_q"], ID["d_oddiy"] = (_it[0]["id"], _it[1]["id"]) if len(_it) == 2 else (None, None)
check("F1 fikstura (2 tur, 2 retsept, qoplama qatori, buyurtma — 2 MRP detal)", all(ID.values()), ID)


def ishlab(tana):
    r = so("post", "/api/production/orders", json=tana)
    pid = ((js(r) or {}).get("production_order") or {}).get("id")
    if not pid:
        return None, r.text[:200]
    for q in ("start", "complete"):
        rr = so("post", f"/api/production/orders/{pid}/{q}")
        if rr.status_code != 200:
            return None, rr.text[:200]
    s = SessionLocal()
    try:
        p = s.get(ProductionOrder, pid)
        fp = s.get(FinishedProduct, p.finished_product_id) if p and p.finished_product_id else None
        return ({"is_coated": (bool(fp.is_coated) if fp is not None else None),
                 "qty": float(fp.produced_quantity or 0) if fp is not None else None}, "")
    finally:
        s.close()


section("Q. Tayyor mahsulot `is_coated` — qoplama HAQIQATAN kiritilganmi")
Q1, _x = ishlab({"product_type_id": ID["t1"], "bom_id": ID["b1"], "quantity": 4, "source_type": "warehouse_stock"})
check("Q1 qoplamasiz tur, omborga 4 m² → `is_coated` = False", Q1 and Q1["is_coated"] is False, (Q1, _x))
Q2, _x = ishlab({"product_type_id": ID["t2"], "bom_id": ID["b2"], "quantity": 3, "source_type": "customer_order",
                 "source_order_id": ID["o"], "source_order_item_id": ID["d_q"]})
check("Q2 qoplamali detal uchun (qoplama qatori o'zi tanlanadi), 3 → `is_coated` = True", Q2 and Q2["is_coated"] is True, (Q2, _x))
Q3, _x = ishlab({"product_type_id": ID["t2"], "bom_id": ID["b2"], "quantity": 2, "source_type": "customer_order",
                 "source_order_id": ID["o"], "source_order_item_id": ID["d_oddiy"]})
check("Q3 qoplamasiz detal uchun (qoplama qatori olib tashlanadi), 2 → `is_coated` = False", Q3 and Q3["is_coated"] is False, (Q3, _x))
Q4, _x = ishlab({"product_type_id": ID["t2"], "bom_id": ID["b2"], "quantity": 5, "source_type": "warehouse_stock",
                 "selected_optional_bom_item_ids": [ID["qopl"]]})
check("Q4 omborga, qoplama qatori TANLANGAN, 5 → `is_coated` = True", Q4 and Q4["is_coated"] is True, (Q4, _x))
Q5, _x = ishlab({"product_type_id": ID["t2"], "bom_id": ID["b2"], "quantity": 6, "source_type": "warehouse_stock"})
check("Q5 omborga, qoplama qatori tanlanmagan, 6 → `is_coated` = False", Q5 and Q5["is_coated"] is False, (Q5, _x))

section("H. Oylik hisobot — qoplamachi bonusi faqat haqiqatan qoplamali MRP birliklari")
_tk = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
_s = SessionLocal()
try:
    rep = services.get_monthly_report(_s, _tk.year, _tk.month, company_id=1)
finally:
    _s.close()
check("H1 `qoplamachi_bonus_avtomatik` = (3 + 5) × 1 000 = 8 000 (asl kodda 20 000 — hamma 20 birlik)",
      abs(float(rep.get("qoplamachi_bonus_avtomatik", -1)) - 8000) < 0.01, rep.get("qoplamachi_bonus_avtomatik"))
check("H2 `jami_dona` = 8", rep.get("jami_dona") == 8, rep.get("jami_dona"))
check("H3 `/api/finished` — qoplamasiz tur mahsuloti «qoplamali» EMAS",
      all(not x.get("is_coated") for x in (js(so("get", "/api/finished")) or []) if x.get("name") == "MQB Travertin"),
      [(x.get("name"), x.get("is_coated")) for x in (js(so("get", "/api/finished")) or [])])
check("H4 hech bir so'rov 500 bermadi", not XATO5, XATO5)

section("S. Statik")
_sp = manba(production_service, "start_production_order")
check("S1 `start_production_order` — tayyor mahsulot `is_coated` surat qatorlaridan (included + is_coating)",
      tartibda(_sp, "fp = FinishedProduct(", 'is_coated=any(bool(_l.get("included")) and bool(_l.get("is_coating")) for _l in snapshot)',
               "db.add(fp)"))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
