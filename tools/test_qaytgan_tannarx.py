#!/usr/bin/env python3
"""
test_qaytgan_tannarx.py — 5-bo'lim 34-band darvozasi (kech55, 2026-09-24).

NIMA UCHUN (asl kod `0161cad` da SQLite da O'LCHANGAN — `work/probe56.py`)
-------------------------------------------------------------------------
  * Buyurtmadan omborga qaytgan detal (`crud.add_returned_to_stock`) tayyor mahsulot
    tannarxini `services.get_order_item_unit_cost` bilan — JORIY narxda — olardi,
    buyurtma tan narxi esa (32-band, foydalanuvchi qarori "ishlatilgan paytdagi narxda
    muzlatilsin") ISHLATILGAN paytdagi narxda. Profil 5 000 so'm/m ga qilingan, narx
    x3 bo'lgach 2 m qaytdi → tannarx 30 000 (to'g'risi 10 000); qoplamali (loy 5 kg)
    — 45 600 (to'g'risi 15 200). Sotuv tannarxi = saqlangan cost_price → 1 000 ga
    sotilganda foyda −14 000 (to'g'risi −4 000) — sof foyda sun'iy kamayardi.
  * MRP mahsuloti qaytishi (kech54 C9) — suratdagi sarf JORIY narxda.

YECHIM (texnik — Claude): `get_order_item_unit_cost(..., muzlatilgan=True)` — xomashyo
`_buyurtma_sarf_narxlari` (buyurtma tan narxi bilan bir manba), loy — shu narxlar bilan
(`get_loy_cost_per_kg(narxlar=)`), MRP — surat `unit_price_at_time`; faqat
`add_returned_to_stock` chaqiradi. Brak summasi va `/api/orders` oldindan ko'rish —
JORIY narx (13-band 2-qadam), O'ZGARMAGAN. Jurnali yo'q eski buyurtma — joriy narx.

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_qaytgan_tannarx.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_qaytgan_tannarx.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qaytgan_tannarx_test"
_DB = os.path.join(tempfile.gettempdir(), "qaytgan_tannarx_test.db")

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
    import crud, auth, services                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from production_models import Company             # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, OrderItem, Inventory, InventoryMovement, Recipe,
    RecipeIngredient, ReturnItem, FinishedProduct, FinishedProductLoss, StockSource, ProductionStatus,
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


def taxminan(a, b, eps=0.01):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="ML Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "ML_admin", "Parol123!", UserRole.ADMIN, "ML Admin", company_id=1)
    auth.create_user(_db, "ML_admin_b", "Parol123!", UserRole.ADMIN, "ML Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="ML Mijoz", project_name="ML loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="ML Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="ML Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000, category="Kimyo")
AKR = Inventory(company_id=1, item_name="ML Akril", unit="kg", stock_quantity=100_000, price_per_unit=10_000, category="Kimyo")
TOSH = Inventory(company_id=1, item_name="ML Tosh", unit="kg", stock_quantity=100_000, price_per_unit=1_000, category="Xom")
BOYOQ = Inventory(company_id=1, item_name="ML Boyoq", unit="kg", stock_quantity=100_000, price_per_unit=20_000, category="Xom")
QOP = Inventory(company_id=1, item_name="ML Qop", unit="dona", stock_quantity=100_000, price_per_unit=700, category="Qadoq")
KAM = Inventory(company_id=1, item_name="ML Kam", unit="kg", stock_quantity=1.0, price_per_unit=5_000, category="Xom")
_db.add_all([PRJ, PENO, KLEY, AKR, TOSH, BOYOQ, QOP, KAM])
_db.commit()
R1 = Recipe(company_id=1, name="ML R1", batch_size_kg=100.0)
_db.add(R1)
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0)])
_db.commit()
ID = {k: v.id for k, v in dict(PRJ=PRJ, PENO=PENO, KLEY=KLEY, AKR=AKR, TOSH=TOSH, BOYOQ=BOYOQ,
                                QOP=QOP, KAM=KAM, R1=R1).items()}
with contextlib.redirect_stdout(_quiet):
    _loy = services.get_or_create_loy_stock(_db, _db.get(Recipe, ID["R1"]))
_loy.stock_quantity = 0.0
_db.commit()
ID["LOY"] = _loy.id
FPS = FinishedProduct(company_id=1, name="ML TM profil", category="profil", is_coated=True, quantity=100,
                      produced_quantity=100, unit="metr", unit_price=0, cost_price=1_000_000,
                      source=StockSource.PRODUCED, penoplast_id=ID["PENO"], recipe_id=ID["R1"],
                      unit_volume_m3=0.01, unit_loy_kg=0.5, production_status=ProductionStatus.READY,
                      width=20, thickness=10)
_db.add(FPS)
_db.commit()
ID["FPS"] = FPS.id
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("ML_admin")
CB, _s2 = _kir("ML_admin_b")
if _s1 != 302 or _s2 != 302:
    print(f"LOGIN BO'LMADI: {_s1} / {_s2}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

# MRP: mahsulot turi + 2 variant (V1: Tosh 3 + Qop 1 qadoq + Boyoq 0.5 qoplama; V2: Tosh 5)
_r = req(C, "post", "/api/production/product-types", json={
    "name": "ML Travertin", "unit": "m²", "input_template": "quantity_only", "pricing_formula": "unit_based",
    "supports_coating": True, "coating_price_multiplier": 2})
PT = (js(_r) or {}).get("id")
_r = req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "V1", "batch_quantity": 1, "items": [
        {"inventory_id": ID["TOSH"], "quantity": 3},
        {"inventory_id": ID["QOP"], "quantity": 1, "component_type": "packaging"},
        {"inventory_id": ID["BOYOQ"], "quantity": 0.5, "is_optional": True, "is_coating": True}]})
_bj = js(_r) or {}
BOM1 = _bj.get("id")
BOYOQ_BI = [x["id"] for x in _bj.get("items", []) if x.get("inventory_id") == ID["BOYOQ"]]
_r = req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "V2", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 5}]})
BOM2 = (js(_r) or {}).get("id")
_r = req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "V3kam", "batch_quantity": 1,
    "items": [{"inventory_id": ID["KAM"], "quantity": 0.1}]})
BOM3 = (js(_r) or {}).get("id")

_n = [0]


def nom():
    _n[0] += 1
    return f"ML_D{_n[0]}"


def profil(uzunlik, narx=50_000, qop=True, **k):
    t = {"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": uzunlik, "quantity": 1,
         "unit_price": narx, "is_coated": qop, "penoplast_id": ID["PENO"]}
    if qop:
        t["recipe_id"] = ID["R1"]
    t.update(k)
    return t


def panel(metr, narx=20_000, qop=True):
    t = {"name": nom(), "category": "panel", "width": 30, "thickness": 5, "length": 0, "quantity": metr,
         "unit_price": narx, "is_coated": qop, "penoplast_id": ID["PENO"]}
    if qop:
        t["recipe_id"] = ID["R1"]
    return t


def dona(soni, narx=5_000, qop=True):
    t = {"name": nom(), "category": "dona", "width": 20, "thickness": 10, "length": 5, "quantity": soni,
         "unit_price": narx, "is_coated": qop, "penoplast_id": ID["PENO"]}
    if qop:
        t["recipe_id"] = ID["R1"]
    return t


def mrp(soni, qop=False):
    return {"name": nom(), "category": "mrp_product", "quantity": soni, "unit_price": 100_000, "is_coated": qop,
            "penoplast_id": None, "product_type_id": PT}


def yarat(items, loy_kg=0, klient=None):
    tana = {"project_id": ID["PRJ"], "order_type": "product", "items": items, "recipe_id": ID["R1"],
            "loy_kg": loy_kg}
    r = req(klient or C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    d = js(r)
    oid = d.get("id") if isinstance(d, dict) else None
    if not oid:
        raise RuntimeError(f"buyurtma yaratilmadi: {r.status_code} {r.text[:300]}")
    return oid


def detallar(oid):
    d = SessionLocal()
    try:
        return [(i.id, i.name) for i in d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        d.close()


def ishlab(oid, iid, miqdor, bom=None, qop=False, tugat=True):
    r = req(C, "post", "/api/production/orders", json={
        "product_type_id": PT, "bom_id": bom or BOM1, "quantity": miqdor, "source_type": "customer_order",
        "source_order_id": oid, "source_order_item_id": iid,
        "selected_optional_bom_item_ids": BOYOQ_BI if qop else []})
    po = ((js(r) or {}).get("production_order") or {}).get("id")
    if not po:
        raise RuntimeError(f"PO yaratilmadi: {r.status_code} {r.text[:300]}")
    r1 = req(C, "post", f"/api/production/orders/{po}/start")
    if r1.status_code != 200:
        raise RuntimeError(f"PO boshlanmadi: {r1.status_code} {r1.text[:300]}")
    if tugat:
        r2 = req(C, "post", f"/api/production/orders/{po}/complete")
        if r2.status_code != 200:
            raise RuntimeError(f"PO tugamadi: {r2.status_code} {r2.text[:300]}")
    return po


def brak(oid, iid, nomi, miqdor, qop, klient=None, **k):
    t = {"order_id": oid, "order_item_id": iid, "item_name": nomi, "quantity": miqdor, "unit": "metr",
         "reason": "Brak", "refund_amount": 0, "to_stock": False, "coating_applied": bool(qop)}
    t.update(k)
    r = req(klient or C, "post", "/api/returns", json=t)
    d = js(r)
    return r.status_code, (d.get("id") if isinstance(d, dict) else None), r


def harakatlar(rid):
    if rid is None:
        return {}
    d = SessionLocal()
    try:
        s = {}
        for h in d.query(InventoryMovement).filter(InventoryMovement.return_item_id == rid).all():
            s[h.inventory_id] = s.get(h.inventory_id, 0.0) + float(h.quantity or 0)
        return s
    finally:
        d.close()


def harakat_qatorlari(rid):
    if rid is None:
        return []
    d = SessionLocal()
    try:
        return [(h.inventory_id, h.movement_type, h.unit_cost, getattr(h, "is_brak", None), h.order_id)
                for h in d.query(InventoryMovement).filter(InventoryMovement.return_item_id == rid).all()]
    finally:
        d.close()


def loy_kg(rid):
    h = harakatlar(rid)
    return round(h.get(ID["KLEY"], 0.0) + h.get(ID["AKR"], 0.0) + h.get(ID["LOY"], 0.0), 9)


def xarajat(rid):
    if rid is None:
        return None
    d = SessionLocal()
    try:
        return round(sum(float(h.quantity or 0) * float(h.unit_cost or 0) for h in
                         d.query(InventoryMovement).filter(InventoryMovement.return_item_id == rid).all()), 4)
    finally:
        d.close()


def summa(rid):
    if rid is None:
        return None
    d = SessionLocal()
    try:
        q = d.get(ReturnItem, rid)
        return float(q.refund_amount) if q else None
    finally:
        d.close()


def stoklar():
    d = SessionLocal()
    try:
        return tuple(round(float(d.get(Inventory, ID[k]).stock_quantity or 0), 9)
                     for k in ("PENO", "KLEY", "AKR", "TOSH", "BOYOQ", "QOP", "KAM", "LOY"))
    finally:
        d.close()


def holat():
    d = SessionLocal()
    try:
        return (d.query(ReturnItem).count(), d.query(FinishedProductLoss).count(),
                d.query(InventoryMovement).count()) + stoklar()
    finally:
        d.close()


def brak_xulosa():
    return (js(req(C, "get", "/api/reports/brak-materials")) or {}).get("total_value")


def sof_foyda():
    from datetime import datetime as _dt
    _h = _dt.utcnow()
    return (js(req(C, "get", "/api/finance/report", params={"year": _h.year, "month": _h.month})) or {}).get("sof_foyda")



# ══════════════════════════════════════════════════════════════
# 34-band yordamchilari
# ══════════════════════════════════════════════════════════════
def _asl_narxlar():
    d = SessionLocal()
    try:
        return {k: float(d.get(Inventory, ID[k]).price_per_unit) for k in ("PENO", "KLEY", "AKR", "TOSH", "BOYOQ")}
    finally:
        d.close()


ASL = _asl_narxlar()


def narx(k):
    """Xomashyo narxlarini asl narxning k barobariga qo'yadi."""
    d = SessionLocal()
    try:
        for kk, v in ASL.items():
            d.get(Inventory, ID[kk]).price_per_unit = v * k
        d.commit()
    finally:
        d.close()


def tayyor(oid, loy=None):
    p = {"loy_kg": str(loy)} if loy is not None else {}
    return req(C, "post", f"/api/orders/{oid}/ready", params=p)


def qaytar(oid, iid, nomi, miqdor, unit="metr"):
    r = req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": iid, "item_name": nomi,
                                             "quantity": miqdor, "unit": unit, "reason": "Ortiqcha",
                                             "refund_amount": 0, "to_stock": True})
    d = js(r)
    return r.status_code, (d.get("id") if (r.status_code == 200 and isinstance(d, dict)) else None), r


def fp_of(rid):
    """(cost_price, quantity, volume_m3, id) — qaytarish yozuvi bog'langan tayyor mahsulot."""
    if not rid:
        return None
    d = SessionLocal()
    try:
        q = d.get(ReturnItem, rid)
        f = d.get(FinishedProduct, q.finished_product_id) if q and q.finished_product_id else None
        return (round(float(f.cost_price or 0), 2), float(f.quantity or 0), round(float(f.volume_m3 or 0), 6), f.id) if f else None
    finally:
        d.close()


def _fp(rid, i=0):
    x = fp_of(rid)
    return x[i] if x else None


def jurnalsiz(oid):
    """Eski buyurtmani taqlid qiladi: shu buyurtmaning ombor harakatlari o'chiriladi."""
    d = SessionLocal()
    try:
        d.query(InventoryMovement).filter(InventoryMovement.order_id == oid).delete(synchronize_session=False)
        d.commit()
    finally:
        d.close()


def detal_narx(oid, iid):
    d = js(req(C, "get", f"/api/orders/{oid}")) or {}
    for i in d.get("items", []) if isinstance(d, dict) else []:
        if i.get("id") == iid:
            return i.get("cost_price_per_unit")
    return None


# ══════════════════════════════════════════════════════════════
section("Q. 34-band — qaytgan mahsulot tannarxi ISHLATILGAN paytdagi narxda")
# ══════════════════════════════════════════════════════════════
narx(1)
# Q1: qoplamasiz profil 10 m (0.1 m³ × 500 000 = 50 000 → 5 000 so'm/m), narx x3 dan keyin 2 m qaytdi
o1 = yarat([profil(10, qop=False)])
r = tayyor(o1)
check("Q0 buyurtma tayyor (xomashyo x1 narxda yechildi)", r.status_code == 200, r.text[:200])
i1, n1 = detallar(o1)[0]
narx(3)
s, q1, r = qaytar(o1, i1, n1, 2)
check("Q1 qoplamasiz profil: narx x3 dan keyin 2 m qaytdi — tannarx 10 000 (ishlatilgan narx; asl: 30 000)",
      s == 200 and taxminan(_fp(q1), 10_000), f"{s} {fp_of(q1)} {r.text[:150]}")
check("Q1 hajm 0.02 m³ (narxga bog'liq emas — avvalgidek)", taxminan(_fp(q1, 2), 0.02, 1e-6), fp_of(q1))
_f1 = _fp(q1, 3)
r = req(C, "post", "/api/finished/sell", json={"finished_product_id": _f1, "quantity": 1, "unit_price": 1000,
                                               "confirm_below_cost": True})
check("Q1b qaytgan mahsulot 1 m 1 000 ga sotildi — foyda −4 000 (asl: −14 000)",
      r.status_code == 200 and taxminan((js(r) or {}).get("profit"), -4_000), r.text[:200])
check("Q1b qolgan 1 m tannarxi 5 000", taxminan(_fp(q1), 5_000) and taxminan(_fp(q1, 1), 1), fp_of(q1))
narx(1)

# Q2: qoplamali profil 10 m, loy 5 kg (5 200 so'm/kg) → 5 000 + 0.5 × 5 200 = 7 600 so'm/m
o2 = yarat([profil(10)], 5)
r = tayyor(o2, loy=5)
check("Q2 qoplamali buyurtma tayyor (loy 5 kg)", r.status_code == 200, r.text[:200])
i2, n2 = detallar(o2)[0]
narx(3)
s, q2, r = qaytar(o2, i2, n2, 2)
check("Q2 qoplamali profil: narx x3 dan keyin 2 m — tannarx 15 200 (penoplast + loy ishlatilgan narxda; asl: 45 600)",
      s == 200 and taxminan(_fp(q2), 15_200), f"{s} {fp_of(q2)} {r.text[:150]}")
narx(1)

# Q3: narx o'zgarmagan — AYNAN avvalgidek (asl bilan bir xil)
o3 = yarat([profil(10, qop=False)])
tayyor(o3)
i3, n3 = detallar(o3)[0]
s, q3, r = qaytar(o3, i3, n3, 2)
check("Q3 narx o'zgarmagan — qoplamasiz 2 m tannarx 10 000 (avvalgidek)", s == 200 and taxminan(_fp(q3), 10_000),
      f"{s} {fp_of(q3)}")
o3b = yarat([profil(10)], 5)
tayyor(o3b, loy=5)
i3b, n3b = detallar(o3b)[0]
s, q3b, r = qaytar(o3b, i3b, n3b, 2)
check("Q3 narx o'zgarmagan — qoplamali 2 m tannarx 15 200 (avvalgidek)", s == 200 and taxminan(_fp(q3b), 15_200),
      f"{s} {fp_of(q3b)}")

# Q4: birlashtirish — Q1 detalidan yana 1 m (narx x3) — o'sha mahsulotga qo'shiladi, ishlatilgan narxda
narx(3)
s, q4, r = qaytar(o1, i1, n1, 1)
check("Q4 ikkinchi qaytarish o'sha mahsulotga birlashdi — 1 m + 1 m, tannarx 5 000 + 5 000 = 10 000 (asl: 15 000 + 15 000)",
      s == 200 and _fp(q4, 3) == _f1 and taxminan(_fp(q4), 10_000) and taxminan(_fp(q4, 1), 2), f"{s} {fp_of(q4)} {_f1}")
# Q5: qaytarishni o'chirish — AYNAN o'sha qo'shilgan qism ayiriladi (22-band)
r = req(C, "delete", f"/api/returns/{q4}")
d = SessionLocal()
try:
    _f = d.get(FinishedProduct, _f1)
    _q5 = (round(float(_f.cost_price or 0), 2), float(_f.quantity or 0)) if _f else None
finally:
    d.close()
check("Q5 ikkinchi qaytarish o'chirildi — mahsulot 1 m, tannarx 5 000 (qo'shilgani aynan ayirildi)",
      r.status_code == 200 and _q5 is not None and taxminan(_q5[0], 5_000) and taxminan(_q5[1], 1), f"{r.status_code} {_q5}")
narx(1)

# Q6: jurnali yo'q ESKI buyurtma — joriy narx (taxmin qilinmaydi, avvalgi xulq)
o6 = yarat([profil(10, qop=False)])
tayyor(o6)
i6, n6 = detallar(o6)[0]
jurnalsiz(o6)
narx(3)
s, q6, r = qaytar(o6, i6, n6, 2)
check("Q6 jurnali yo'q eski buyurtma — joriy narx: 2 m tannarx 30 000 (avvalgidek)", s == 200 and taxminan(_fp(q6), 30_000),
      f"{s} {fp_of(q6)}")

# Q7: brak summasi va oldindan ko'rish — JORIY narx (13-band 2-qadam) — O'ZGARMAGAN
s, rb, r = brak(o3, i3, n3, 1, False)
check("Q7 brak (narx x3) summasi 15 000 — yozilgan paytdagi JORIY narx (o'zgarmagan)", s == 200 and summa(rb) == 15_000,
      f"{s} {summa(rb)} {r.text[:150]}")
check("Q7 /api/orders oldindan ko'rish cost_price_per_unit 15 000 — joriy narx (o'zgarmagan)",
      taxminan(detal_narx(o3, i3), 15_000), detal_narx(o3, i3))
narx(1)

# Q8–Q10: MRP mahsuloti (V1: Tosh 3 kg × 1 000 = 3 000 so'm/birlik, qadoqsiz)
o8 = yarat([mrp(10)])
i8, n8 = detallar(o8)[0]
ishlab(o8, i8, 10)
# kech73 (86-band): avval 2 birlik TOPSHIRILADI — qaytarish mijozdan QAYTGAN mahsulot (topshirilmagan MRP ortiqchasi
# endi yangi TM yaratmaydi, band TM dan erkin qoldiqqa o'tadi — tools/test_mrp_ortiqcha.py).
req(C, "post", "/api/deliveries", json={"order_id": o8, "items": [{"order_item_id": i8, "quantity": 2}],
                                     "notes": "Q8 yuk", "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
narx(3)
s, q8, r = qaytar(o8, i8, n8, 2, unit="m²")
check("Q8 MRP: ishlab chiqarilgandan keyin narx x3, 2 birlik qaytdi — tannarx 6 000 (surat narxi; asl: 18 000)",
      s == 200 and taxminan(_fp(q8), 6_000), f"{s} {fp_of(q8)} {r.text[:150]}")
s, rb8, r = brak(o8, i8, n8, 1, False)
check("Q9 MRP brak summasi (narx x3) 9 000 — joriy narx (13-band 2-qadam, o'zgarmagan)", s == 200 and summa(rb8) == 9_000,
      f"{s} {summa(rb8)} {r.text[:150]}")
narx(1)
o10 = yarat([mrp(10)])
i10, n10 = detallar(o10)[0]
ishlab(o10, i10, 10)
# kech73 (86-band): avval 2 birlik TOPSHIRILADI — qaytarish mijozdan QAYTGAN mahsulot (topshirilmagan MRP ortiqchasi
# endi yangi TM yaratmaydi, band TM dan erkin qoldiqqa o'tadi — tools/test_mrp_ortiqcha.py).
req(C, "post", "/api/deliveries", json={"order_id": o10, "items": [{"order_item_id": i10, "quantity": 2}],
                                     "notes": "Q10 yuk", "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
s, q10, r = qaytar(o10, i10, n10, 2, unit="m²")
check("Q10 MRP narx o'zgarmagan — 6 000 (kech54 C9 bilan bir xil)", s == 200 and taxminan(_fp(q10), 6_000), f"{s} {fp_of(q10)}")

# Q12: o'lchamsiz dona (hajm zaxira yo'li — penoplast narxidan) — hajm ham, tannarx ham x1 dagidek
o12 = yarat([{"name": nom(), "category": "dona", "width": 0, "thickness": 0, "length": 0, "quantity": 10,
              "unit_price": 5_000, "is_coated": False, "penoplast_id": ID["PENO"]}])
r = tayyor(o12)
i12, n12 = detallar(o12)[0]
_d = SessionLocal()
try:
    _oi12 = _d.get(OrderItem, i12)
    _v12 = services._item_volume_m3(_d, _oi12, None)
    _u12 = services.get_order_item_unit_cost(_d, _oi12.order, _oi12)
finally:
    _d.close()
narx(3)
s, q12, r = qaytar(o12, i12, n12, 2, unit="dona")
check("Q12 o'lchamsiz dona: narx x3 dan keyin 2 dona — hajm x1 dagi hajmning 2/10 qismi (asl: narx x3 dan hisoblanib 3 marta kichik)",
      s == 200 and _v12 > 0 and taxminan(_fp(q12, 2), round(_v12 * 2 / 10, 6), 1e-6), f"{s} {fp_of(q12)} v1={_v12}")
check("Q12 o'lchamsiz dona: tannarx 2 × x1 dagi birlik tannarxi", s == 200 and taxminan(_fp(q12), 2 * _u12),
      f"{fp_of(q12)} u1={_u12}")
narx(1)

# Q11: yordamchilar — to'g'ridan (narxlar lug'ati va surat narxlari)
_d = SessionLocal()
try:
    _lk = services.get_loy_cost_per_kg(_d, ID["R1"], company_id=1)
    _lk2 = services.get_loy_cost_per_kg(_d, ID["R1"], company_id=1, narxlar={ID["KLEY"]: 1_000}) \
        if "narxlar" in inspect.signature(services.get_loy_cost_per_kg).parameters else None
    check("Q11 get_loy_cost_per_kg narxlarsiz — joriy (0.6 × 2 000 + 0.4 × 10 000 = 5 200)",
          taxminan(_lk.get("cost_per_kg"), 5_200), _lk.get("cost_per_kg"))
    check("Q11 get_loy_cost_per_kg(narxlar={Kley: 1 000}) — 0.6 × 1 000 + 0.4 × 10 000 = 4 600 (Akril joriy)",
          _lk2 is not None and taxminan(_lk2.get("cost_per_kg"), 4_600), _lk2 and _lk2.get("cost_per_kg"))
    _sq = getattr(services, "_mrp_sarf_qiymati", None)
    _sq_ok = _sq is not None and "narxlar" in inspect.signature(_sq).parameters
    check("Q11 _mrp_sarf_qiymati(narxlar=) — lug'atdagi material o'sha narxda, qolgani joriy",
          _sq_ok and taxminan(_sq(_d, {ID["TOSH"]: 3, ID["BOYOQ"]: 1}, 1, narxlar={ID["TOSH"]: 500}), 3 * 500 + 20_000),
          _sq_ok)
    _oi8 = _d.get(OrderItem, i8)
    _sn = {}
    _sarf = getattr(services, "_mrp_birlik_sarfi", None)
    try:
        _r11 = _sarf(_d, 1, order_item=_oi8, surat_narxlari=_sn)
    except TypeError as e:
        _r11 = f"TypeError {e}"
    check("Q11 _mrp_birlik_sarfi(surat_narxlari=) — sarf o'zgarmaydi (Tosh 3), narx 1 000 (surat)",
          isinstance(_r11, dict) and taxminan(_r11.get(ID["TOSH"]), 3) and ID["TOSH"] in _sn
          and taxminan(_sn[ID["TOSH"]][1] / _sn[ID["TOSH"]][0], 1_000), f"{_r11} {_sn}")
finally:
    _d.close()

# ══════════════════════════════════════════════════════════════
section("S. Statik — faqat qaytgan mahsulot muzlatilgan narxda")
# ══════════════════════════════════════════════════════════════
_src_ret = inspect.getsource(crud.add_returned_to_stock)
check("S1 add_returned_to_stock — get_order_item_unit_cost(..., muzlatilgan=True)",
      "get_order_item_unit_cost(db, order_item.order, order_item, muzlatilgan=True)" in _src_ret)
check("S2 add_returned_to_stock — hajm ham ishlatilgan narxda (penoplast_narxi=)",
      "_item_volume_m3(db, order_item, None, penoplast_narxi=" in _src_ret)
_src_cr = inspect.getsource(crud.create_return_item)
check("S3 create_return_item (brak summasi) muzlatilgan narxni ISHLATMAYDI (13-band 2-qadam)",
      "get_order_item_unit_cost(" in _src_cr and "muzlatilgan" not in _src_cr)
_src_main = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("S4 main.py oldindan ko'rish muzlatilgan narxni ISHLATMAYDI",
      "get_order_item_unit_cost(db, order, i)" in _src_main and "muzlatilgan" not in _src_main)
_sig = inspect.signature(services.get_order_item_unit_cost).parameters
check("S5 get_order_item_unit_cost(muzlatilgan=False) — standart joriy narx",
      "muzlatilgan" in _sig and _sig["muzlatilgan"].default is False)
_src_uc = inspect.getsource(services.get_order_item_unit_cost)
check("S6 get_order_item_unit_cost — muzlatilgan narx manbai _buyurtma_sarf_narxlari (buyurtma tan narxi bilan bir)",
      "_buyurtma_sarf_narxlari(db, order) if (muzlatilgan and order is not None) else {}" in _src_uc)

print()
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
