#!/usr/bin/env python3
"""
test_mrp_loy_ulush.py — 5-bo'lim 44-band + K62-1 darvozasi (kech62, 2026-09-24):
MRP detali buyurtma LOYINI sarflamaydi — YAGONA qoida.

NIMA UCHUN (asl kod `25bcd8d` da SQLite va HAQIQIY PG 16 da O'LCHANGAN — `work/probe62.py`, AYNAN)
------------------------------------------------------------------------------------------------
MRP detalining qoplamasi o'z BOM ining qoplama qatoridan ishlab chiqarishda AVTOMATIK yechiladi
(11.0-band, `production_service`), 41-band (`services._buyurtma_loyi_detalimi`) ham MRP detalini buyurtma
loyi maxrajidan chiqaradi. Lekin:
  * 44-band: `services.loy_relevant_remaining_fraction` (buyurtmani o'chirish / tiklashda buyurtma loyining
    QOLGAN ulushi) MRP detalini ham sanardi. Qoplamali profil 10 m (topshirilmagan) + qoplamali MRP 10
    (to'liq topshirilgan), loy 30 kg: o'chirishda 15 kg qaytdi (to'g'risi 30), tiklashda 15 kg yechildi.
    Aksi (profil topshirilgan, MRP yo'q): 15 kg qaytdi (to'g'risi 0).
  * K62-1: faqat qoplamali MRP detali bor buyurtmada `orders.html` loy kg ni MAJBURIY qilardi
    (`anyCoated` MRP qatorini ham sanardi) — buyurtma loyi yaratishda yechildi (5 kg), ishlab chiqarish
    BOM qoplamasini YANA yechdi (Bo'yoq 5 kg): qoplama xomashyosi IKKI marta. "Tayyor" oynasi
    (`hasCoatable`) ham MRP detali uchun haqiqiy loyni so'rardi.

YECHIM (texnik — Claude): predikat YAGONA — qoplamali VA `_buyurtma_loyi_detalimi` (MRP, "Loy sotish",
Tayyor mahsulotdan olingan — YO'Q): `loy_relevant_remaining_fraction`, `orders.html` `anyCoated` va
`hasCoatable`; loy maydoni izohi aniqlashtirildi. Penoplast detallari uchun hamma natija AYNAN.

ASL KOD: yiqilishi SHART, qulamasligi SHART (yangi nomlar `getattr`, HTTP istisno → 599).
REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_mrp_loy_ulush.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_loy_ulush.py
"""
import os
import sys
import inspect
import tempfile
import subprocess

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_loy_ulush_test"
_DB = os.path.join(tempfile.gettempdir(), "mrp_loy_ulush_test.db")

if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
               isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth, services                          # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Inventory, Recipe, RecipeIngredient,
)
from fastapi.testclient import TestClient          # noqa: E402

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
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {str(detail)[:400]}")


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


def taxminan(a, b, eps=1e-6):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def tartibda(src, *qismlar):
    """Qismlar src ichida AYNAN shu tartibda uchraydimi (find — topilmasa False)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "ML62_admin", "Parol123!", UserRole.ADMIN, "ML62 Admin", company_id=1)
PRJ = Project(company_id=1, client_name="ML62 Mijoz", project_name="ML62 loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="ML62 Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="ML62 Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000, category="Kimyo")
AKR = Inventory(company_id=1, item_name="ML62 Akril", unit="kg", stock_quantity=100_000, price_per_unit=10_000, category="Kimyo")
TOSH = Inventory(company_id=1, item_name="ML62 Tosh", unit="kg", stock_quantity=100_000, price_per_unit=1_000, category="Xom")
BOYOQ = Inventory(company_id=1, item_name="ML62 Boyoq", unit="kg", stock_quantity=100_000, price_per_unit=20_000, category="Xom")
_db.add_all([PRJ, PENO, KLEY, AKR, TOSH, BOYOQ])
_db.commit()
R1 = Recipe(company_id=1, name="ML62 R1", batch_size_kg=100.0)
_db.add(R1)
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0)])
_db.commit()
ID = {k: v.id for k, v in dict(PRJ=PRJ, PENO=PENO, KLEY=KLEY, AKR=AKR, TOSH=TOSH, BOYOQ=BOYOQ, R1=R1).items()}
with contextlib.redirect_stdout(_quiet):
    _loy = services.get_or_create_loy_stock(_db, _db.get(Recipe, ID["R1"]))
_loy.stock_quantity = 0.0
_db.commit()
ID["LOY"] = _loy.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_s = req(C, "post", "/login", data={"username": "ML62_admin", "password": "Parol123!"}, follow_redirects=False)
if _s.status_code != 302:
    print(f"LOGIN BO'LMADI: {_s.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

# MRP: mahsulot turi (qoplama qo'llaydi) + BOM (Tosh 3 + Bo'yoq 0.5 — ixtiyoriy QOPLAMA qatori)
_r = req(C, "post", "/api/production/product-types", json={
    "name": "ML62 Travertin", "unit": "m²", "input_template": "quantity_only", "pricing_formula": "unit_based",
    "supports_coating": True, "coating_price_multiplier": 2})
PT = (js(_r) or {}).get("id")
_r = req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "V1", "batch_quantity": 1, "items": [
        {"inventory_id": ID["TOSH"], "quantity": 3},
        {"inventory_id": ID["BOYOQ"], "quantity": 0.5, "is_optional": True, "is_coating": True}]})
BOM1 = (js(_r) or {}).get("id")
if not PT or not BOM1:
    print(f"MRP TAYYORLANMADI: PT={PT} BOM1={BOM1}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom():
    _n[0] += 1
    return f"ML62_D{_n[0]}"


def profil(uzunlik, narx=50_000, qop=True):
    t = {"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": uzunlik, "quantity": 1,
         "unit_price": narx, "is_coated": qop, "penoplast_id": ID["PENO"]}
    if qop:
        t["recipe_id"] = ID["R1"]
    return t


def panel(metr, narx=20_000, qop=True):
    t = {"name": nom(), "category": "panel", "width": 30, "thickness": 5, "length": 0, "quantity": metr,
         "unit_price": narx, "is_coated": qop, "penoplast_id": ID["PENO"]}
    if qop:
        t["recipe_id"] = ID["R1"]
    return t


def mrp(soni, qop=True, narx=100_000):
    return {"name": nom(), "category": "mrp_product", "quantity": soni, "unit_price": narx, "is_coated": qop,
            "penoplast_id": None, "product_type_id": PT}


def yarat(items, loy_kg=0):
    tana = {"project_id": ID["PRJ"], "order_type": "product", "items": items, "recipe_id": ID["R1"],
            "loy_kg": loy_kg}
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    d = js(r)
    return (d.get("id") if isinstance(d, dict) else None), r


def detallar(oid):
    if not oid:
        return []
    d = SessionLocal()
    try:
        return [i.id for i in d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        d.close()


def ishlab(oid, iid, miqdor):
    r = req(C, "post", "/api/production/orders", json={
        "product_type_id": PT, "bom_id": BOM1, "quantity": miqdor, "source_type": "customer_order",
        "source_order_id": oid, "source_order_item_id": iid, "selected_optional_bom_item_ids": []})
    po = ((js(r) or {}).get("production_order") or {}).get("id")
    if not po:
        return False
    r1 = req(C, "post", f"/api/production/orders/{po}/start")
    r2 = req(C, "post", f"/api/production/orders/{po}/complete")
    return r1.status_code == 200 and r2.status_code == 200


_sanoq = [0]


def yetkaz(oid, iid, miqdor):
    _sanoq[0] += 1
    r = req(C, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}],
                                                  "notes": f"ML62 yuk {_sanoq[0]}"})
    return r.status_code


def stok():
    d = SessionLocal()
    try:
        return {k: float(d.get(Inventory, ID[k]).stock_quantity or 0) for k in ("KLEY", "AKR", "LOY", "BOYOQ", "TOSH")}
    finally:
        d.close()


def loy(s):
    """Buyurtma loyi zaxirasi (kg): retsept ingredientlari (Kley + Akril) + tayyor loy."""
    return s["KLEY"] + s["AKR"] + s["LOY"]


def ulush(oid):
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        if o is None:
            return None
        return float(services.loy_relevant_remaining_fraction(o))
    except Exception:                      # noqa: BLE001
        return None
    finally:
        d.close()


def ochir(oid):
    return req(C, "delete", f"/api/orders/{oid}")


def tikla(oid):
    return req(C, "post", f"/api/orders/{oid}/restore")


# ══════════════════════════════════════════════════════════════
section("A. 44-band: profil topshirilMAGAN + MRP TO'LIQ topshirilgan, loy 30 kg")
# ══════════════════════════════════════════════════════════════
s0 = stok()
oA, _r = yarat([profil(10), mrp(10)], loy_kg=30)
check("A0 buyurtma yaratildi", oA, getattr(_r, "text", "")[:200])
s1 = stok()
check("A1 yaratishda buyurtma loyi 30 kg yechildi (Kley 18 + Akril 12)", taxminan(loy(s0) - loy(s1), 30),
      loy(s0) - loy(s1))
dA = detallar(oA)
iP, iM = (dA + [None, None])[:2]
check("A2 MRP 10 ishlab chiqarildi", iM and ishlab(oA, iM, 10))
s2 = stok()
check("A3 ishlab chiqarish BOM qoplamasini yechdi (Bo'yoq 5 kg, Tosh 30) — o'zgarmagan yo'l",
      taxminan(s1["BOYOQ"] - s2["BOYOQ"], 5) and taxminan(s1["TOSH"] - s2["TOSH"], 30) and taxminan(loy(s1), loy(s2)),
      {k: s1[k] - s2[k] for k in s1})
check("A4 MRP 10 topshirildi", iM and yetkaz(oA, iM, 10) == 200)
check("A5 loy ulushi = 1.0 (buyurtma loyining yagona iste'molchisi — profil — topshirilmagan)",
      taxminan(ulush(oA), 1.0), ulush(oA))
s3 = stok()
_r = ochir(oA)
s4 = stok()
check("A6 o'chirish 200", _r.status_code == 200, getattr(_r, "text", "")[:200])
check("A7 o'chirishda buyurtma loyi TO'LIQ qaytdi — 30 kg (eski kod: 15)", taxminan(loy(s4) - loy(s3), 30),
      loy(s4) - loy(s3))
check("A8 Kley / Akril retsept ulushida qaytdi (18 / 12)",
      taxminan(s4["KLEY"] - s3["KLEY"], 18) and taxminan(s4["AKR"] - s3["AKR"], 12),
      (s4["KLEY"] - s3["KLEY"], s4["AKR"] - s3["AKR"]))
_r = tikla(oA)
s5 = stok()
check("A9 tiklash 200", _r.status_code == 200, getattr(_r, "text", "")[:200])
check("A10 tiklashda AYNAN o'sha 30 kg qayta yechildi (eski kod: 15)", taxminan(loy(s4) - loy(s5), 30),
      loy(s4) - loy(s5))
check("A11 o'chirish + tiklash — zaxira aylanib asliga (loy s3 = s5)", taxminan(loy(s3), loy(s5)), (loy(s3), loy(s5)))

# ══════════════════════════════════════════════════════════════
section("B. 44-band aksi: profil TO'LIQ topshirilgan + MRP topshirilMAGAN, loy 30 kg")
# ══════════════════════════════════════════════════════════════
oB, _r = yarat([profil(10), mrp(10)], loy_kg=30)
dB = detallar(oB)
iPb = dB[0] if dB else None
check("B1 profil 10 topshirildi", iPb and yetkaz(oB, iPb, 10) == 200)
check("B2 loy ulushi = 0.0 (profil loyi sarflangan)", taxminan(ulush(oB), 0.0), ulush(oB))
t3 = stok()
_r = ochir(oB)
t4 = stok()
check("B3 o'chirish 200", _r.status_code == 200, getattr(_r, "text", "")[:200])
check("B4 o'chirishda loy QAYTMADI — 0 kg (eski kod: 15)", taxminan(loy(t4) - loy(t3), 0), loy(t4) - loy(t3))

# ══════════════════════════════════════════════════════════════
section("C. Penoplast detallari — natija AYNAN (regressiya): profil 10 + panel 10, profil topshirilgan")
# ══════════════════════════════════════════════════════════════
oC, _r = yarat([profil(10), panel(10)], loy_kg=30)
dC = detallar(oC)
check("C1 profil 10 topshirildi", dC and yetkaz(oC, dC[0], 10) == 200)
check("C2 loy ulushi = 0.5 (1 − 10 / 20 — avvalgidek)", taxminan(ulush(oC), 0.5), ulush(oC))
u3 = stok()
_r = ochir(oC)
u4 = stok()
check("C3 o'chirishda 15 kg qaytdi (avvalgidek)", _r.status_code == 200 and taxminan(loy(u4) - loy(u3), 15),
      (_r.status_code, loy(u4) - loy(u3)))
_r = tikla(oC)
u5 = stok()
check("C4 tiklashda 15 kg yechildi (avvalgidek)", _r.status_code == 200 and taxminan(loy(u4) - loy(u5), 15),
      (_r.status_code, loy(u4) - loy(u5)))
oC2, _r = yarat([profil(10), panel(10, qop=False)], loy_kg=20)
dC2 = detallar(oC2)
check("C5 qoplamasiz panel topshirilsa (profil yo'q) — ulush 1.0 (qoplamasiz sanalmaydi, avvalgidek)",
      len(dC2) == 2 and yetkaz(oC2, dC2[1], 10) == 200 and taxminan(ulush(oC2), 1.0), ulush(oC2))

# ══════════════════════════════════════════════════════════════
section("D. K62-1: FAQAT qoplamali MRP detali — buyurtma loyi ishlatilmaydi")
# ══════════════════════════════════════════════════════════════
v0 = stok()
oD, _r = yarat([mrp(10)], loy_kg=0)
v1 = stok()
check("D1 faqat qoplamali MRP, loy 0 — backend qabul qiladi", oD, getattr(_r, "text", "")[:200])
check("D2 yaratishda buyurtma loyi YECHILMADI", taxminan(loy(v0), loy(v1)), loy(v0) - loy(v1))
dD = detallar(oD)
check("D3 ishlab chiqarish qoplamasini BOM dan oladi (Bo'yoq 5 kg) — qoplama BIR marta",
      dD and ishlab(oD, dD[0], 10) and taxminan(v1["BOYOQ"] - stok()["BOYOQ"], 5), v1["BOYOQ"] - stok()["BOYOQ"])
# API orqali loy kiritilgan bo'lsa (UI endi talab qilmaydi) — o'chirishda TO'LIQ qaytadi (iste'molchi yo'q)
oD2, _r = yarat([mrp(10)], loy_kg=5)
dD2 = detallar(oD2)
_ok = dD2 and ishlab(oD2, dD2[0], 10) and yetkaz(oD2, dD2[0], 4) == 200
check("D4 MRP 10 dan 4 topshirildi — loy ulushi 1.0 (MRP buyurtma loyini sarflamaydi; eski: 0.6)",
      _ok and taxminan(ulush(oD2), 1.0), ulush(oD2))
w3 = stok()
_r = ochir(oD2)
w4 = stok()
check("D5 o'chirishda kiritilgan 5 kg TO'LIQ qaytdi (eski kod: 3)", _r.status_code == 200 and taxminan(loy(w4) - loy(w3), 5),
      (_r.status_code, loy(w4) - loy(w3)))

# ══════════════════════════════════════════════════════════════
section("E. Predikat — `_buyurtma_loyi_detalimi` bilan YAGONA (to'g'ridan)")
# ══════════════════════════════════════════════════════════════


class _D:
    def __init__(self, cat, qop, q, topsh, fp=None):
        self.category = cat
        self.is_coated = qop
        self.order_qty_normalized = q
        self.delivered_qty = topsh
        self.ortiqcha_qty = 0
        self.finished_product_id = fp


class _O:
    def __init__(self, items):
        self.items = items


_f = getattr(services, "loy_relevant_remaining_fraction", None)


def _u(items):
    try:
        return float(_f(_O(items)))
    except Exception:                      # noqa: BLE001
        return None


check("E1 MRP qoplamali (to'liq topshirilgan) + profil (topshirilmagan) → 1.0",
      taxminan(_u([_D("mrp_product", True, 10, 10), _D("profil", True, 10, 0)]), 1.0),
      _u([_D("mrp_product", True, 10, 10), _D("profil", True, 10, 0)]))
check("E2 MRP katta registrda ('MRP_Product') ham chiqariladi → 1.0",
      taxminan(_u([_D("MRP_Product", True, 10, 10), _D("profil", True, 10, 0)]), 1.0),
      _u([_D("MRP_Product", True, 10, 10), _D("profil", True, 10, 0)]))
check("E3 Loy sotish va Tayyor mahsulotdan olingan — avvalgidek chiqariladi → 0.5",
      taxminan(_u([_D("loy_sotish", True, 50, 50), _D("profil", True, 10, 10, fp=7), _D("profil", True, 10, 5)]), 0.5),
      _u([_D("loy_sotish", True, 50, 50), _D("profil", True, 10, 10, fp=7), _D("profil", True, 10, 5)]))
check("E4 faqat MRP qoplamali (qisman) → 1.0 (iste'molchi yo'q)",
      taxminan(_u([_D("mrp_product", True, 10, 4)]), 1.0), _u([_D("mrp_product", True, 10, 4)]))
_src = ""
try:
    _src = inspect.getsource(_f)
except Exception:                          # noqa: BLE001
    pass
check("E5 funksiya `_buyurtma_loyi_detalimi` ni chaqiradi (qo'lda nusxa emas)",
      tartibda(_src, "if it.is_coated", "and _buyurtma_loyi_detalimi(it)"))
_bd = getattr(services, "_buyurtma_loyi_detalimi", None)
check("E6 `_buyurtma_loyi_detalimi` o'zgarmagan (loy_sotish / mrp_product / finished_product_id)",
      _bd is not None and _bd(_D("mrp_product", True, 1, 0)) is False and _bd(_D("loy_sotish", True, 1, 0)) is False
      and _bd(_D("profil", True, 1, 0, fp=3)) is False and _bd(_D("profil", True, 1, 0)) is True)

# ══════════════════════════════════════════════════════════════
section("F. API — \"Tayyor\" oynasi uchun kalitlar")
# ══════════════════════════════════════════════════════════════
_o = js(req(C, "get", f"/api/orders/{oA}")) or {}
_it = _o.get("items") or []
check("F1 /api/orders/{id} detallarida category, is_coated, finished_product_id bor",
      _it and all(("category" in x and "is_coated" in x and "finished_product_id" in x) for x in _it),
      [sorted(x.keys())[:30] for x in _it[:1]])

# ══════════════════════════════════════════════════════════════
section("G. UI — statik")
# ══════════════════════════════════════════════════════════════
_h = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
check("G1 anyCoated: MRP qatori loy kg ni majburiy qilmaydi (fpId tekshiruvidan keyin, .i-c dan OLDIN)",
      tartibda(_h, "const anyCoated = Array.from(document.querySelectorAll('.detal')).some(row => {",
               "if (row.dataset.fpId) return false;",
               "if (row.querySelector('.i-type')?.value === 'mrp_product') return false;",
               "const cEl = row.querySelector('.i-c');"))
check("G2 hasCoatable: MRP / Loy sotish / Tayyor mahsulotdan — chiqariladi",
      tartibda(_h, "const hasCoatable = (planned > 0) || (orderData && orderData.items && orderData.items.some(it =>",
               "it.is_coated", "&& !['mrp_product', 'loy_sotish'].includes(String(it.category || '').toLowerCase())",
               "&& !it.finished_product_id));")
      and "orderData.items.some(it => it.is_coated));" not in _h)
check("G3 loy maydoni izohi — penoplast detallari uchun, MRP o'z retseptidan",
      "— qoplamali penoplast detallari uchun (MRP mahsuloti qoplamasi o'z retseptidan)</span>" in _h
      and "— barcha detallar uchun</span>" not in _h)

# ══════════════════════════════════════════════════════════════
section("H. UI — dinamik (shablondagi HAQIQIY ifoda, jsdom)")
# ══════════════════════════════════════════════════════════════


def _parcha(src, bosh, oxir):
    i = src.find(bosh)
    if i < 0:
        return ""
    j = src.find(oxir, i)
    return src[i:j + len(oxir)] if j >= 0 else ""


_any = _parcha(_h, "const anyCoated", "\n  });")
_has = _parcha(_h, "const hasCoatable", ";\n")
_jsk = r"""
const { JSDOM } = require('jsdom');
function qator(tur, qop, fp) {
  return `<div class="detal"${fp ? ' data-fp-id="9"' : ''}><input class="i-type" value="${tur}"><input class="i-c" value="${qop}"></div>`;
}
function anyC(qatorlar) {
  const dom = new JSDOM('<body>' + qatorlar.join('') + '</body>');
  const document = dom.window.document;
  __ANY__
  return anyCoated;
}
function hasC(planned, items) {
  const orderData = { items };
  __HAS__
  return hasCoatable;
}
const n = {
  h1: anyC([qator('mrp_product', 'true')]),
  h2: anyC([qator('profil', 'true')]),
  h3: anyC([qator('mrp_product', 'true'), qator('profil', 'true', true)]),
  h4: anyC([qator('mrp_product', 'false'), qator('panel', 'true')]),
  h5: hasC(0, [{ category: 'mrp_product', is_coated: true, finished_product_id: null }]),
  h6: hasC(0, [{ category: 'profil', is_coated: true, finished_product_id: null }]),
  h7: hasC(0, [{ category: 'profil', is_coated: true, finished_product_id: 4 }, { category: 'loy_sotish', is_coated: true }]),
  h8: hasC(12, [{ category: 'mrp_product', is_coated: true }]),
};
console.log(JSON.stringify(n));
""".replace("__ANY__", _any).replace("__HAS__", _has)
_nat = {}
_xato = ""
if _any and _has:
    _tf = os.path.join(tempfile.gettempdir(), "mrp_loy_ulush_ui.js")
    with open(_tf, "w", encoding="utf-8") as _f2:
        _f2.write(_jsk)
    _env = dict(os.environ)
    if not _env.get("NODE_PATH"):
        try:
            _env["NODE_PATH"] = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True,
                                               timeout=60).stdout.strip()
        except Exception:                  # noqa: BLE001
            pass
    try:
        _p = subprocess.run(["node", _tf], capture_output=True, text=True, timeout=120, env=_env)
        import json as _json
        _nat = _json.loads((_p.stdout or "").strip().splitlines()[-1]) if _p.returncode == 0 and _p.stdout.strip() else {}
        _xato = (_p.stderr or "")[:300]
    except Exception as e:                 # noqa: BLE001
        _xato = f"{type(e).__name__}: {e}"
else:
    _xato = "shablondan ifoda topilmadi"
check("H1 faqat qoplamali MRP qatori — loy kg SO'RALMAYDI", _nat.get("h1") is False, (_nat, _xato))
check("H2 qoplamali profil — loy kg so'raladi (avvalgidek)", _nat.get("h2") is True, (_nat, _xato))
check("H3 MRP + Tayyor mahsulotdan qoplamali — so'ralmaydi", _nat.get("h3") is False, (_nat, _xato))
check("H4 qoplamasiz MRP + qoplamali panel — so'raladi", _nat.get("h4") is True, (_nat, _xato))
check("H5 \"Tayyor\" oynasi: faqat qoplamali MRP, reja 0 — loy SO'RALMAYDI", _nat.get("h5") is False, (_nat, _xato))
check("H6 \"Tayyor\" oynasi: qoplamali profil — so'raladi (avvalgidek)", _nat.get("h6") is True, (_nat, _xato))
check("H7 \"Tayyor\" oynasi: faqat Tayyor mahsulotdan / Loy sotish — so'ralmaydi", _nat.get("h7") is False, (_nat, _xato))
check("H8 \"Tayyor\" oynasi: reja > 0 — har doim so'raladi (avvalgidek)", _nat.get("h8") is True, (_nat, _xato))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
