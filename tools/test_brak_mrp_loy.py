#!/usr/bin/env python3
"""
test_brak_mrp_loy.py — 13-band 5-qadam + 41-band + 42-band darvozasi (kech54, 2026-09-24).

NIMA UCHUN (hammasi asl kod `aecce02` da SQLite va HAQIQIY PG 16 da O'LCHANGAN —
`work/probe54.py`, `work/probe55.py`):
  * 42-band: qoplamali detal \"loygacha\" brak bo'lsa ombordan faqat penoplast yechilardi, brak
    SUMMASI esa loy bilan yozilardi (profil 1 m: xarajat 5 000, summa 10 200) — Qaytarishlar
    sahifasidagi \"Brak qiymati\" Moliyadagi brak xarajatidan katta. FOYDALANUVCHI QARORI (kech54):
    eski yozuvlar O'ZGARMAYDI, faqat yangilari to'g'ri.
  * 41-band: buyurtma loyi (bitta umumiy son) brakda detallarga BIRLIK SONI bo'yicha bo'linardi —
    metr va dona bir xil; tayyor mahsulotdan olingan va MRP detallari ham maxrajga kirardi.
    FOYDALANUVCHI QARORI (kech54): \"Qoplama narxi ulushiga qarab (qimmat detal ko'proq)\".
  * 13-band 5-qadam: MRP detali braki — summa 0, xomashyo yechilmasdi; qoplamali MRP detalida
    BUYURTMA loyi retseptidan yechilardi; \"Ishlab chiqarishda chiqdi\" MRP mahsulotiga — 400.
    YECHIM (texnik — Claude): sarf shu mahsulotni ishlab chiqargan buyurtmaning retsept SURATIDAN.
QAT'IY SHART (kech5 9-bo'lim): brak YOZISH oqimi o'zgarmaydi — oddiy (bitta turli) buyurtmada
natija AYNAN avvalgidek (A7).

ASL KOD: yiqilishi SHART, qulamasligi SHART (yangi nomlar `getattr`, HTTP istisno → 599).
REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
"""
import os
import sys
import json
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "brak_mrp_loy_test"
_DB = os.path.join(tempfile.gettempdir(), "brak_mrp_loy_test.db")

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
from production_models import Company, ProductionOrder   # noqa: E402
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


def taxminan(a, b, eps=1e-6):
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
section("A. 41-band — buyurtma loyi QOPLAMA NARXI ulushi bo'yicha")
# ══════════════════════════════════════════════════════════════
# A1: profil 10 m (50 000) + panel 10 m (10 × 20 000) + dona 100 (100 × 5 000), loy 30 kg
# qoplama narxi ulushlari 50 000 : 200 000 : 500 000 → loy 2 / 8 / 20 kg → birlikka 0.2 / 0.8 / 0.2
o = yarat([profil(10), panel(10), dona(100)], 30)
dt = detallar(o)
kutilgan = [0.2, 0.8, 0.2]
for (iid, nm), k, nomi in zip(dt, kutilgan, ["profil", "panel", "dona"]):
    s, rid, r = brak(o, iid, nm, 1, True)
    check(f"A1 {nomi} 1 birlik braki — loy {k} kg (qoplama narxi ulushi)", s == 200 and taxminan(loy_kg(rid), k),
          f"{s} {loy_kg(rid)} {r.text[:150]}")
    check(f"A1 {nomi} — summa = haqiqiy xarajat (bitta manba)", taxminan(summa(rid), round(xarajat(rid) or -1), 1.0),
          f"{summa(rid)} {xarajat(rid)}")
# A1b: to'liqlik — hamma detal to'liq brak bo'lsa, jami loy AYNAN buyurtma loyi (30 kg)
o = yarat([profil(10), panel(10), dona(100)], 30)
dt = detallar(o)
jami = 0.0
for (iid, nm), miq in zip(dt, [10, 10, 100]):
    s, rid, _ = brak(o, iid, nm, miq, True)
    jami += loy_kg(rid)
check("A1b to'liq brak — detallar loyi yig'indisi AYNAN buyurtma loyi (30 kg)", taxminan(jami, 30.0, 1e-6), jami)

# A2: bir xil turdagi, narxi farqli — qimmat profil ko'proq (1 : 3)
o = yarat([profil(10, narx=100_000), profil(10, narx=300_000)], 40)
dt = detallar(o)
s1, r1, _ = brak(o, dt[0][0], dt[0][1], 1, True)
s2, r2, _ = brak(o, dt[1][0], dt[1][1], 1, True)
check("A2 arzon profil — 1 m braki 1.0 kg (40 × 1/4 ÷ 10)", taxminan(loy_kg(r1), 1.0), loy_kg(r1))
check("A2 qimmat profil — 1 m braki 3.0 kg (40 × 3/4 ÷ 10)", taxminan(loy_kg(r2), 3.0), loy_kg(r2))

# A3: tayyor mahsulotdan olingan detal maxrajga KIRMAYDI (loyi ishlab chiqarishda sarflangan)
o = yarat([profil(10), profil(10, finished_product_id=ID["FPS"])], 10)
dt = detallar(o)
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, True)
check("A3 yangi profil + tayyor mahsulotdan profil, loy 10 — 1 m braki 1.0 kg (asl: 0.5)",
      s == 200 and taxminan(loy_kg(rid), 1.0), f"{s} {loy_kg(rid)}")
s, rid, r = brak(o, dt[1][0], dt[1][1], 1, True)
check("A3 tayyor mahsulotdan detal braki — buyurtma loyidan HECH narsa yechilmaydi", s == 200 and loy_kg(rid) == 0,
      f"{s} {loy_kg(rid)}")

# A3b: MRP detali (qoplamali, ishlab chiqarilgan) maxrajga KIRMAYDI
o = yarat([profil(10), mrp(10, qop=True)], 10)
dt = detallar(o)
ishlab(o, dt[1][0], 10, qop=True)
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, True)
check("A3b profil + qoplamali MRP, loy 10 — profil 1 m braki 1.0 kg (asl: 0.5)",
      s == 200 and taxminan(loy_kg(rid), 1.0), f"{s} {loy_kg(rid)}")
s, rid, r = brak(o, dt[1][0], dt[1][1], 1, True)
check("A3b qoplamali MRP braki — buyurtma loyi retseptidan (Kley/Akril) YECHILMAYDI",
      s == 200 and loy_kg(rid) == 0 and taxminan(harakatlar(rid).get(ID["BOYOQ"], 0), 0.5),
      f"{s} {harakatlar(rid)}")

# A4: narxsiz buyurtma — zaxira: eski usul (birlik soni)
o = yarat([profil(10, narx=0), dona(10, narx=0)], 20)
dt = detallar(o)
s1, r1, _ = brak(o, dt[0][0], dt[0][1], 1, True)
s2, r2, _ = brak(o, dt[1][0], dt[1][1], 1, True)
check("A4 narxsiz — profil 1 m 1.0 kg, dona 1 ta 1.0 kg (20 ÷ 20 birlik, eski usul)",
      taxminan(loy_kg(r1), 1.0) and taxminan(loy_kg(r2), 1.0), f"{loy_kg(r1)} {loy_kg(r2)}")

# A5: ichki qo'shimcha detal — o'z qoplama belgisi va narxi bilan
_b5 = getattr(services, "_qoplama_narxi", None)


class _S:
    def __init__(self, narx, qop):
        self.total_price = narx
        self.is_coated = qop


class _I:
    def __init__(self, narx, qop, subs):
        self.total_price = narx
        self.is_coated = qop
        self.sub_details = subs
        self.category = "profil"
        self.finished_product_id = None


check("A5 qoplamali ota (80 000, ichida qoplamasiz 20 000) — qoplama narxi 30 000 (faqat ota qismi yarmi)",
      _b5 is not None and taxminan(_b5(_I(80_000, True, [_S(20_000, False)])), 30_000), _b5)
check("A5 qoplamasiz ota, ichida qoplamali 20 000 — qoplama narxi 10 000",
      _b5 is not None and taxminan(_b5(_I(80_000, False, [_S(20_000, True)])), 10_000), _b5)
check("A5 qoplamasiz, ichki ham qoplamasiz — 0", _b5 is not None and _b5(_I(80_000, False, [_S(20_000, False)])) == 0, _b5)

# A6: aralash buyurtma — oldindan ko'rish (returns.html) ham shu ulushdan
o = yarat([profil(10), dona(100)], 30)
dt = detallar(o)
d = js(req(C, "get", f"/api/orders/{o}")) or {}
_its = {i.get("id"): i for i in d.get("items", [])}
# qoplama narxlari 50 000 : 500 000 → profil loyi 30/11 kg, 10 m → 0.2727… kg/m × loy narxi
_loy_narx = services.get_loy_cost_per_kg(SessionLocal(), ID["R1"], company_id=1).get("cost_per_kg")
_kut = round(0.01 * 500_000 + (30.0 * 50_000 / 550_000 / 10) * _loy_narx)
check("A6 /api/orders detal oldindan ko'rish narxi (loy bilan) — qoplama narxi ulushidan",
      taxminan(_its.get(dt[0][0], {}).get("cost_price_per_unit"), _kut, 1.0),
      f"{_its.get(dt[0][0], {}).get('cost_price_per_unit')} kutilgan {_kut}")

# A7: QAT'IY SHART — bitta qoplamali detal (oddiy buyurtma) — AYNAN avvalgidek
o = yarat([profil(10)], 10)
dt = detallar(o)
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, True)
check("A7 bitta qoplamali profil, loy 10 — 1 m braki 1.0 kg, summa 10 200 (avvalgidek)",
      s == 200 and taxminan(loy_kg(rid), 1.0) and summa(rid) == 10_200, f"{s} {loy_kg(rid)} {summa(rid)}")

# ══════════════════════════════════════════════════════════════
section("B. 42-band — loygacha brak summasi loysiz")
# ══════════════════════════════════════════════════════════════
o = yarat([profil(10)], 10)
dt = detallar(o)
x0 = brak_xulosa()
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, False)
check("B1 qoplamali profil 1 m LOYGACHA — summa 5 000 (faqat penoplast; asl: 10 200)",
      s == 200 and summa(rid) == 5_000, f"{s} {summa(rid)}")
check("B1 loygacha — loy yechilmaydi, xarajat 5 000", loy_kg(rid) == 0 and taxminan(xarajat(rid), 5_000), xarajat(rid))
check("B1 brak xulosasi AYNAN summa qadar o'zgardi (Qaytarishlar = Moliya)",
      x0 is not None and taxminan(brak_xulosa() - x0, summa(rid) or -1, 1.0), f"{x0} {brak_xulosa()}")
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, True)
check("B2 loydan KEYIN — summa 10 200 (penoplast + loy), xarajat bilan teng",
      s == 200 and summa(rid) == 10_200 and taxminan(xarajat(rid), 10_200), f"{summa(rid)} {xarajat(rid)}")
o = yarat([profil(10, qop=False)], 0)
dt = detallar(o)
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, True)
check("B3 qoplamasiz profil (\"loy tortilgan\" belgilansa ham) — summa 5 000", s == 200 and summa(rid) == 5_000, summa(rid))
# B4: eski yozuvlar O'ZGARMAYDI — ilova qayta ishga tushganda ham (migratsiya yo'q)
_d = SessionLocal()
_eski = ReturnItem(company_id=1, order_id=o, order_item_id=dt[0][0], item_name=dt[0][1], quantity=1, unit="metr",
                   reason=crud.ReturnReason.DEFECT, refund_amount=10_200, is_refunded=False, coating_applied=False)
_d.add(_eski)
_d.commit()
_eski_id = _eski.id
_d.close()
with contextlib.redirect_stdout(_quiet):
    for _f in ("sync_missing_columns",):
        try:
            getattr(__import__("database"), _f)()
        except Exception:
            pass
    for _nm in dir(main):
        if _nm.startswith("_migrate_"):
            try:
                getattr(main, _nm)()
            except Exception:
                pass
check("B4 eski (loyli) yozuv summasi — migratsiyalardan keyin ham 10 200 (foydalanuvchi qarori)", summa(_eski_id) == 10_200,
      summa(_eski_id))

# ══════════════════════════════════════════════════════════════
section("C. 5-qadam — buyurtmadagi MRP detali braki (retsept surati)")
# ══════════════════════════════════════════════════════════════
o = yarat([mrp(10, qop=True)])
dt = detallar(o)
PO_A = ishlab(o, dt[0][0], 10, qop=True)
_st0 = stoklar()
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, False)
h = harakatlar(rid)
check("C1 loygacha — faqat xomashyo: Tosh 3 kg (qoplama Boyoq va qadoq Qop YO'Q)",
      s == 200 and set(h) == {ID["TOSH"]} and taxminan(h[ID["TOSH"]], 3.0), f"{s} {h} {r.text[:150]}")
check("C1 summa 3 000 (3 kg × 1 000, brak paytidagi narx)", summa(rid) == 3_000, summa(rid))
_hq = harakat_qatorlari(rid)
check("C1 harakat: chiqim, brak belgisi, narx muzlatilgan, buyurtmaga bog'langan",
      _hq and all(t == "out" and b is True and taxminan(uc, 1_000) and oid == o for _, t, uc, b, oid in _hq), _hq)
check("C1 ombor: Tosh −3, qolganlar o'zgarmadi",
      taxminan(stoklar()[3], _st0[3] - 3) and stoklar()[4:6] == _st0[4:6] and stoklar()[:3] == _st0[:3], (stoklar(), _st0))
s, rid2, r = brak(o, dt[0][0], dt[0][1], 2, True)
h = harakatlar(rid2)
check("C2 loydan KEYIN 2 birlik — Tosh 6 + Boyoq 1 kg, qadoq yo'q",
      s == 200 and set(h) == {ID["TOSH"], ID["BOYOQ"]} and taxminan(h[ID["TOSH"]], 6) and taxminan(h[ID["BOYOQ"]], 1),
      f"{s} {h}")
check("C2 summa 26 000 = xarajat (MRP tan narxi 13 000 / birlik bilan bir xil)",
      summa(rid2) == 26_000 and taxminan(xarajat(rid2), 26_000), f"{summa(rid2)} {xarajat(rid2)}")
# C3: brakni o'chirish — xomashyo AYNAN qaytadi (13-band 6-qadam), narx o'zgarsa ham hisobot o'zgarmaydi
x0 = brak_xulosa()
_d = SessionLocal()
_d.get(Inventory, ID["TOSH"]).price_per_unit = 3_000
_d.commit()
_d.close()
check("C3 Tosh narxi 3x — brak xulosasi O'ZGARMAYDI (narx muzlatilgan)", brak_xulosa() == x0, f"{x0} {brak_xulosa()}")
_d = SessionLocal()
_d.get(Inventory, ID["TOSH"]).price_per_unit = 1_000
_d.commit()
_d.close()
_st1 = stoklar()
r = req(C, "delete", f"/api/returns/{rid2}")
check("C3 brakni o'chirish — 200, Tosh +6, Boyoq +1 (omborga qaytdi)",
      r.status_code == 200 and taxminan(stoklar()[3], _st1[3] + 6) and taxminan(stoklar()[4], _st1[4] + 1),
      f"{r.status_code} {r.text[:150]}")
# C4: ishlab chiqarish boshlanmagan — rad, hech narsa yozilmaydi
o = yarat([mrp(10)])
dt = detallar(o)
h0 = holat()
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, False)
check("C4 ishlab chiqarilmagan MRP detali braki — 400 (asl: 200, summa 0)", s == 400, f"{s} {r.text[:150]}")
check("C4 xabar — ishlab chiqarish boshlanmagan", "boshlanmagan" in str((js(r) or {}).get("detail", "")), r.text[:200])
check("C4 hech narsa yozilmadi (yozuvlar, harakatlar, qoldiqlar)", holat() == h0, (holat(), h0))
# C5: faqat BEKOR qilingan ishlab chiqarish — rad; JARAYONDAGI — surat ishlatiladi
_r = req(C, "post", "/api/production/orders", json={
    "product_type_id": PT, "bom_id": BOM1, "quantity": 5, "source_type": "customer_order",
    "source_order_id": o, "source_order_item_id": dt[0][0]})
_po = ((js(_r) or {}).get("production_order") or {}).get("id")
req(C, "post", f"/api/production/orders/{_po}/start")
req(C, "post", f"/api/production/orders/{_po}/cancel")
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, False)
check("C5 faqat bekor qilingan ishlab chiqarish — 400", s == 400, f"{s} {r.text[:150]}")
PO_J = ishlab(o, dt[0][0], 10, tugat=False)
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, False)
check("C5 JARAYONDAGI (boshlangan) ishlab chiqarish surati — 200, Tosh 3", s == 200 and taxminan(harakatlar(rid).get(ID["TOSH"]), 3),
      f"{s} {harakatlar(rid)}")
# C6: ikki ishlab chiqarish (V1 4 birlik Tosh 3, V2 6 birlik Tosh 5) — miqdor bo'yicha o'rtacha 4.2
o = yarat([mrp(10)])
dt = detallar(o)
ishlab(o, dt[0][0], 4, bom=BOM1)
ishlab(o, dt[0][0], 6, bom=BOM2)
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, False)
check("C6 ikki variant — 1 birlik Tosh (4×3 + 6×5) ÷ 10 = 4.2 kg", s == 200 and taxminan(harakatlar(rid).get(ID["TOSH"]), 4.2),
      f"{s} {harakatlar(rid)}")
# C7: eski surat (kech54 dan oldingi — `is_coating` kalitisiz) — qoplama tanlangan qatordan aniqlanadi
o = yarat([mrp(10, qop=True)])
dt = detallar(o)
_po7 = ishlab(o, dt[0][0], 10, qop=True)
_d = SessionLocal()
_p = _d.get(ProductionOrder, _po7)
_sur = json.loads(_p.recipe_snapshot_json)
check("C7 yangi surat qatorlarida `is_coating` va `bom_item_id` bor",
      all("is_coating" in q and "bom_item_id" in q for q in _sur) and any(q.get("is_coating") for q in _sur), _sur)
for q in _sur:
    q.pop("is_coating", None)
    q.pop("bom_item_id", None)
_p.recipe_snapshot_json = json.dumps(_sur)
_d.commit()
_d.close()
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, False)
check("C7 eski surat, loygacha — Boyoq (qoplama) YO'Q", s == 200 and set(harakatlar(rid)) == {ID["TOSH"]}, harakatlar(rid))
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, True)
check("C7 eski surat, loydan keyin — Boyoq 0.5 bor", s == 200 and taxminan(harakatlar(rid).get(ID["BOYOQ"]), 0.5), harakatlar(rid))
# C8: begona korxona — B o'z buyurtmasi + A detali → rad (avvalgidek), A ombori tegilmaydi
_st = stoklar()
s, rid, r = brak(o, dt[0][0], dt[0][1], 1, False, klient=CB)
check("C8 B sessiyasi A ning MRP detaliga brak — 4xx, A ombori o'zgarmadi", 400 <= s < 500 and stoklar() == _st, f"{s}")
_sarf = getattr(services, "_mrp_birlik_sarfi", None)
_d = SessionLocal()
try:
    _oi = _d.get(OrderItem, dt[0][0])
    check("C8 surat korxona bo'yicha filtrlanadi (B korxona uchun — None)",
          _sarf is not None and _sarf(_d, 2, order_item=_oi) is None and _sarf(_d, 1, order_item=_oi), _sarf)
finally:
    _d.close()
# C9: qaytgan MRP mahsuloti (\"Ortiqcha\") tayyor mahsulotga xomashyo tan narxi bilan tushadi
o = yarat([mrp(10)])
dt = detallar(o)
ishlab(o, dt[0][0], 10)
r = req(C, "post", "/api/returns", json={"order_id": o, "order_item_id": dt[0][0], "item_name": dt[0][1], "quantity": 2,
                                         "unit": "m²", "reason": "Ortiqcha", "refund_amount": 0, "to_stock": True})
_rid9 = (js(r) or {}).get("id")
_d = SessionLocal()
try:
    _q9 = _d.get(ReturnItem, _rid9) if _rid9 else None
    _fp9 = _d.get(FinishedProduct, _q9.finished_product_id) if _q9 and _q9.finished_product_id else None
    check("C9 qaytgan MRP (2 birlik, loysiz) tan narxi 6 000 (Tosh 3 × 1 000 × 2; asl: 0)",
          _fp9 is not None and taxminan(_fp9.cost_price, 6_000, 0.01), f"{r.status_code} {_fp9 and _fp9.cost_price}")
finally:
    _d.close()

# ══════════════════════════════════════════════════════════════
section("D. 5-qadam — \"Ishlab chiqarishda chiqdi\" (MRP tayyor mahsuloti)")
# ══════════════════════════════════════════════════════════════
o = yarat([mrp(10, qop=True)])
dt = detallar(o)
_poD = ishlab(o, dt[0][0], 10, qop=True)
_d = SessionLocal()
FPD = _d.get(ProductionOrder, _poD).finished_product_id
_q0 = float(_d.get(FinishedProduct, FPD).quantity)
_d.close()
_st = stoklar()
sf0 = sof_foyda()
x0 = brak_xulosa()
r = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": FPD, "brak_qty": 2})
d = js(r) or {}
check("D1 MRP mahsuloti braki — 200 (asl: 400 \"xomashyo nisbati topilmadi\")", r.status_code == 200, r.text[:200])
check("D1 xarajat 26 000 (2 × (Tosh 3 + Boyoq 0.5)), qadoqsiz", taxminan(d.get("cost_amount"), 26_000),
      d.get("cost_amount"))
check("D1 ombor: Tosh −6, Boyoq −1, Qop o'zgarmadi",
      taxminan(stoklar()[3], _st[3] - 6) and taxminan(stoklar()[4], _st[4] - 1) and stoklar()[5] == _st[5], stoklar())
_d = SessionLocal()
try:
    check("D1 mahsulot soniga TEGILMADI", taxminan(_d.get(FinishedProduct, FPD).quantity, _q0), _q0)
    _hs = _d.query(InventoryMovement).filter(InventoryMovement.reason.like("Brak (ishlab chiqarish)%")).all()
    check("D1 harakatlar brak belgili, narx muzlatilgan", len(_hs) == 2 and all(h.is_brak is True and h.unit_cost for h in _hs),
          [(h.item_name, h.is_brak, h.unit_cost) for h in _hs])
finally:
    _d.close()
check("D2 brak xulosasi +26 000, sof foyda −26 000 (BIR marta — yo'qotish yozuvi ikkinchi marta ayirilmaydi)",
      taxminan((brak_xulosa() or 0) - (x0 or 0), 26_000, 1) and sf0 is not None
      and taxminan((sof_foyda() or 0) - sf0, -26_000, 1), f"{x0}->{brak_xulosa()} {sf0}->{sof_foyda()}")
# D3: yetishmasa — 400, hech narsa yozilmaydi
o = yarat([mrp(10)])
dt = detallar(o)
_d = SessionLocal()
_d.get(Inventory, ID["KAM"]).stock_quantity = 5.0
_d.commit()
_d.close()
_poK = ishlab(o, dt[0][0], 10, bom=BOM3)
_d = SessionLocal()
FPK = _d.get(ProductionOrder, _poK).finished_product_id
_d.close()
h0 = holat()
r = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": FPK, "brak_qty": 50})
check("D3 xomashyo yetishmaydi (kerak 5, bor 4) — 400, hech narsa yozilmadi",
      r.status_code == 400 and "yetishmayapti" in r.text and holat() == h0, f"{r.status_code} {r.text[:200]}")
# D4: suratsiz \"dynamic_bom\" mahsuloti — 400 (taxmin qilinmaydi)
_d = SessionLocal()
_fx = FinishedProduct(company_id=1, name="ML suratsiz", category="dynamic_bom", quantity=5, produced_quantity=5, unit="m²",
                      unit_price=0, cost_price=0, source=StockSource.PRODUCED, production_status=ProductionStatus.READY)
_d.add(_fx)
_d.commit()
_fxid = _fx.id
_d.close()
h0 = holat()
r = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": _fxid, "brak_qty": 1})
check("D4 suratsiz MRP mahsuloti — 400, hech narsa yozilmadi", r.status_code == 400 and holat() == h0, r.text[:200])
# D5: begona korxona
r = req(CB, "post", "/api/finished/production-brak", json={"finished_product_id": FPD, "brak_qty": 1})
check("D5 B sessiyasi A mahsulotiga — 4xx", 400 <= r.status_code < 500, r.status_code)

# ══════════════════════════════════════════════════════════════
section("S. Statik — tartib va yagona manba")
# ══════════════════════════════════════════════════════════════
_cri = inspect.getsource(crud.create_return_item)
_i0 = _cri.find("services._mrp_birlik_sarfi")
check("S1 create_return_item: MRP rad tekshiruvi yozuvdan (`ReturnItem(`) OLDIN",
      _i0 != -1 and _cri.find("item = ReturnItem(") != -1 and _i0 < _cri.find("item = ReturnItem("), _i0)
check("S2 create_return_item: brak summasi `include_coating` bilan (loy tortilganmi)",
      "include_coating=bool(getattr(data, 'coating_applied', False))" in _cri)
_ded = inspect.getsource(services.deduct_raw_material_for_brak)
_uc = inspect.getsource(services.get_order_item_unit_cost)
check("S3 yechim va summa loyi — BITTA manba (`_brak_loyi_birlikka`), eski birlik soni yo'q",
      "_brak_loyi_birlikka(order, order_item)" in _ded and "_brak_loyi_birlikka(order, item)" in _uc
      and "total_coated_units +=" not in _ded and "total_coated_units +=" not in _uc)
check("S4 MRP — yechim va summa bir yordamchidan (`_mrp_birlik_sarfi`)",
      "_mrp_brakini_yech(" in _ded and "_mrp_birlik_sarfi(" in _uc)
_pb = inspect.getsource(crud.record_finished_product_production_brak)
_j0 = _pb.find("'dynamic_bom'")
_j1 = _pb.find('db.info["_brak_harakat"] = True')
check("S5 ishlab chiqarish braki: MRP qatorlari va yetarlilik brak oynasidan (yozuvdan) OLDIN, eski tekshiruv MRP da o'tkaziladi",
      -1 < _j0 < _pb.find("yetishmayapti", _j0) < _j1
      and "if _mrp_qatorlar is None and penoplast_vol_needed <= 0 and loy_kg_needed <= 0" in _pb)
_yor = inspect.getsource(getattr(crud, "_mrp_ishlab_chiqarish_braki_xomashyo", lambda: None))
check("S7 MRP yechish yordamchisi — `log_movement` orqali (brak belgisi va narx oynadan)",
      "log_movement(" in _yor and "db.add(InventoryMovement" not in _yor, _yor[:80])
check("S6 koeffitsiyent — qoplamali narx = qoplamasiz × 2", getattr(services, "QOPLAMA_NARX_KOEF", None) == 2.0)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
