#!/usr/bin/env python3
"""
test_brak_narx.py — 13-band (brak tizimi) 2-qadam darvozasi (kech46, 2026-09-24).

NIMA UCHUN KERAK (O'LCHANGAN — `work/probe46.py`, asl kod `19ca309`)
--------------------------------------------------------------------
  * Brak xarajati (`crud.get_brak_material_summary` — Moliya / sof foyda,
    `services.get_monthly_report` `brak_xarajat`, `calculate_split_profit_report`)
    brak uchun ombordan chiqqan HAR harakatni materialning JORIY narxi
    (`inventory.price_per_unit`) bilan baholardi.
  * Natija: 2 kg kley 1 000 so'mdan brak bo'ldi → xarajat 2 000; keyin kley
    narxi 3 000 ga o'zgardi → O'TGAN brak xarajati 6 000 bo'lib qoldi (o'tgan
    oyning sof foydasi ham o'zgaradi). Tizimning qolgan qismi (tan narx, retsept
    surati, to'lovlar) muzlatilgan — brak yagona muzlatilmagan joy edi.

YECHIM (texnik — Claude): `InventoryMovement.unit_cost` (Float, NULL). Har
CHIQIM ("out") harakati yozilganda materialning o'sha paytdagi 1 birlik narxi
yoziladi: `crud.log_movement` (tayyor loy, loy ingredientlari, ishlab
chiqarish braki va boshqalar) va `services.deduct_raw_material_for_brak`
dagi to'g'ridan penoplast harakati. Hisobot `unit_cost` ni o'qiydi; u yo'q
(yangilanishdan OLDINGI harakat) bo'lsa — joriy narx, avvalgidek (eski narx
noma'lum, taxmin qilinmaydi). Kirim ("in") harakatida NULL. Migratsiya
`main._migrate_harakat_narx` (idempotent). Brak YOZISH uslubi O'ZGARMAGAN.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_brak_narx.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_brak_narx.py
"""
import os
import sys
import ast
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "brak_narx_test"
_DB = os.path.join(tempfile.gettempdir(), "brak_narx_test.db")

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

from sqlalchemy import text, inspect as sa_inspect  # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Inventory, InventoryMovement,
    ActivityLog, Recipe, RecipeIngredient,
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
    """Qismlar matnda shu tartibda uchraydimi (`find`, topilmasa False)."""
    p = 0
    for q in qismlar:
        i = src.find(q, p)
        if i < 0:
            return False
        p = i + len(q)
    return True


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="BN Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "BN_admin", "Parol123!", UserRole.ADMIN, "BN Admin", company_id=1)
    auth.create_user(_db, "BN_admin_b", "Parol123!", UserRole.ADMIN, "BN Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="BN Mijoz", project_name="BN loyiha", total_budget=0, total_paid=0)
PRJ_B = Project(company_id=2, client_name="BN Mijoz B", project_name="BN loyiha B", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="BN Penoplast", unit="blok", stock_quantity=1000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
PENO_B = Inventory(company_id=2, item_name="BN Penoplast B", unit="blok", stock_quantity=1000,
                   price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="BN Kley", unit="kg", stock_quantity=1000,
                 price_per_unit=2_000, category="Kimyo")
_db.add_all([PRJ, PRJ_B, PENO, PENO_B, KLEY])
_db.commit()
RET = Recipe(company_id=1, name="BN Retsept", batch_size_kg=100.0)
_db.add(RET)
_db.commit()
_db.add(RecipeIngredient(recipe_id=RET.id, inventory_id=KLEY.id, quantity_kg=100.0))
_db.commit()
PRJ_ID, PRJB_ID, PENO_ID, PENOB_ID, KLEY_ID, RET_ID = (
    PRJ.id, PRJ_B.id, PENO.id, PENO_B.id, KLEY.id, RET.id)
# Tayyor loy zaxirasi — brak loyining bir qismi shundan olinadi (3 kg)
with contextlib.redirect_stdout(_quiet):
    _loy = services.get_or_create_loy_stock(_db, _db.get(Recipe, RET_ID))
_loy.stock_quantity = 3.0
_db.commit()
LOY_ID = _loy.id
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("BN_admin")
CB, _s2 = _kir("BN_admin_b")
if _s1 != 302 or _s2 != 302:
    print(f"LOGIN BO'LMADI: {_s1} / {_s2}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def buyurtma(qoplama=False, b=False):
    """API orqali YANGI buyurtma (profil, 10 dona × 100 sm = 100 metr, penoplastli).
    `qoplama=True` — detal qoplamali, retsept bog'lanadi va haqiqiy loy 100 kg
    (ORM bilan — \"Tayyor\" bosilgandagi qiymat) → (order_id, detal_id)."""
    _n[0] += 1
    nom = f"BN_D{_n[0]}"
    r = req(CB if b else C, "post", "/api/orders", json={
        "project_id": PRJB_ID if b else PRJ_ID, "order_type": "product", "items": [
            {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 100,
             "quantity": 10, "unit_price": 50_000, "is_coated": bool(qoplama),
             "penoplast_id": PENOB_ID if b else PENO_ID}]})
    oid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    d = SessionLocal()
    try:
        q = d.query(OrderItem).filter(OrderItem.name == nom)
        if oid:
            q = q.filter(OrderItem.order_id == oid)
        oi = q.order_by(OrderItem.id.desc()).first()
        if oi is None:
            raise RuntimeError(f"buyurtma yaratilmadi: {r.status_code} {r.text[:200]}")
        if qoplama:
            oi.is_coated = True
            oi.recipe_id = RET_ID
            d.get(Order, oi.order_id).actual_loy_kg = 100.0
            d.commit()
        return oi.order_id, oi.id
    finally:
        d.close()


def detal_nomi(iid):
    d = SessionLocal()
    try:
        return d.get(OrderItem, iid).name
    finally:
        d.close()


def brak(oid, iid, miqdor, qoplama_tortilgan=False, b=False):
    t = {"order_id": oid, "order_item_id": iid, "item_name": detal_nomi(iid),
         "quantity": miqdor, "unit": "metr", "reason": "Brak", "refund_amount": 0,
         "to_stock": False, "coating_applied": bool(qoplama_tortilgan)}
    r = req(CB if b else C, "post", "/api/returns", json=t)
    rid = (js(r) or {}).get("id") if (r.status_code == 200 and isinstance(js(r), dict)) else None
    return r, rid


def ochir(rid, c=None):
    return req(c or C, "delete", f"/api/returns/{rid}")


def ombor(*ids):
    d = SessionLocal()
    try:
        return tuple(round(float(d.get(Inventory, i).stock_quantity or 0), 9) for i in ids)
    finally:
        d.close()


def harakatlar(rid):
    """Shu brak yozuviga bog'langan harakatlar: [(inventory_id, turi, miqdor)]."""
    d = SessionLocal()
    try:
        if not hasattr(InventoryMovement, "return_item_id"):
            return []
        return [(m.inventory_id, m.movement_type, round(float(m.quantity), 9))
                for m in d.query(InventoryMovement).filter(
                    InventoryMovement.return_item_id == rid).order_by(InventoryMovement.id).all()]
    finally:
        d.close()


def brak_harakat_soni():
    d = SessionLocal()
    try:
        return d.query(InventoryMovement).filter(InventoryMovement.reason.like("Brak%")).count()
    finally:
        d.close()


def jami_harakat():
    d = SessionLocal()
    try:
        return d.query(InventoryMovement).count()
    finally:
        d.close()


def brak_qiymati():
    d = SessionLocal()
    try:
        return float(crud.get_brak_material_summary(d, company_id=1).get("total_value") or 0)
    finally:
        d.close()


def audit(rid):
    d = SessionLocal()
    try:
        x = d.query(ActivityLog).filter(ActivityLog.entity_type == "return",
                                        ActivityLog.entity_id == rid,
                                        ActivityLog.action == "deleted").order_by(ActivityLog.id.desc()).first()
        return (x.new_value or "") if x else ""
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════
# Yordamchilar
# ══════════════════════════════════════════════════════════════
from datetime import datetime as _dt        # noqa: E402
_HOZ = _dt.utcnow()
YIL, OY = _HOZ.year, _HOZ.month


def narx_qoy(inv_id, narx):
    d = SessionLocal()
    try:
        d.get(Inventory, inv_id).price_per_unit = narx
        d.commit()
    finally:
        d.close()


def xulosa():
    d = SessionLocal()
    try:
        return crud.get_brak_material_summary(d, company_id=1)
    finally:
        d.close()


def jami_brak():
    return float(xulosa().get("total_value") or 0)


def oylik_brak():
    d = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            return float(services.get_monthly_report(d, YIL, OY, company_id=1).get("brak_xarajat") or 0)
    finally:
        d.close()


def split_brak():
    d = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            r = services.calculate_split_profit_report(d, YIL, OY, company_id=1)
        return (r["penoplast"]["brak_xarajati"], r["penoplast"]["sof_foyda"])
    except Exception as e:                 # noqa: BLE001
        return f"{type(e).__name__}: {e}"
    finally:
        d.close()


def harakat_narxlari(rid):
    """Brak yozuviga bog'langan harakatlar: {inventory_id: unit_cost}."""
    d = SessionLocal()
    try:
        return {m.inventory_id: getattr(m, "unit_cost", "USTUN_YOQ")
                for m in d.query(InventoryMovement).filter(InventoryMovement.return_item_id == rid).all()}
    finally:
        d.close()


def yangi_material(nom, narx, qoldiq=100.0):
    d = SessionLocal()
    try:
        m = Inventory(company_id=1, item_name=nom, unit="kg", stock_quantity=qoldiq,
                      price_per_unit=narx, category="Kimyo")
        d.add(m)
        d.commit()
        return m.id
    finally:
        d.close()


def chiqim(inv_id, nom, miqdor, sabab, order_id=None, tur="out"):
    """`crud.log_movement` orqali harakat (qoldiq ham kamayadi) → harakat id."""
    d = SessionLocal()
    try:
        if inv_id:
            m = d.get(Inventory, inv_id)
            m.stock_quantity = float(m.stock_quantity or 0) + (miqdor if tur == "in" else -miqdor)
        # kech52 (13-band, 3-qadam): ilova brak harakatini BELGI bilan yozadi (`is_brak`) — hisobot
        # sabab matniga qaramaydi. Shu yordamchi brakni simulyatsiya qilganda ("Brak ..." chiqim)
        # belgini ham qo'yadi; belgi ustuni yo'q (eski) kodda — avvalgidek.
        _k = {}
        if tur == "out" and (sabab or "").startswith("Brak") and hasattr(InventoryMovement, "is_brak"):
            _k["is_brak"] = True
        crud.log_movement(d, inv_id, nom, tur, miqdor, "kg", reason=sabab, order_id=order_id, company_id=1, **_k)
        d.commit()
        return d.query(InventoryMovement).order_by(InventoryMovement.id.desc()).first().id
    finally:
        d.close()


def harakat(hid):
    d = SessionLocal()
    try:
        return d.get(InventoryMovement, hid)
    finally:
        d.close()


def narxi(hid):
    return getattr(harakat(hid), "unit_cost", "USTUN_YOQ")


def mat_qiymat(nom):
    for m in xulosa().get("by_material") or []:
        if m.get("item_name") == nom:
            return m
    return {}


def buy_qiymat(oid):
    for o in xulosa().get("by_order") or []:
        if o.get("order_id") == oid:
            return o
    return {}


# ══════════════════════════════════════════════════════════════
# A. log_movement — chiqimda narx muzlatiladi
# ══════════════════════════════════════════════════════════════
section("A. Harakat yozilganda narx muzlatiladi")
try:
    A_ID = yangi_material("BN A kley", 1_000)
    h1 = chiqim(A_ID, "BN A kley", 2, "Brak — sinov A (2 birlik)")
    check("A1 chiqim (\"out\") harakatida unit_cost = o'sha paytdagi narx (1 000)", narxi(h1) == 1_000, narxi(h1))
    h2 = chiqim(A_ID, "BN A kley", 5, "Xarid: sinov A", tur="in")
    check("A2 kirim (\"in\") harakatida unit_cost NULL", narxi(h2) is None, narxi(h2))
    narx_qoy(A_ID, None)
    h3 = chiqim(A_ID, "BN A kley", 1, "Brak — sinov A narxsiz (1 birlik)")
    check("A3 narxi belgilanmagan material — unit_cost 0 (hisobot ham 0 deb hisoblardi)", narxi(h3) == 0, narxi(h3))
    h4 = chiqim(None, "BN A o'chgan", 1, "Brak — materialsiz (1 birlik)")
    check("A4 materialsiz harakat — unit_cost NULL", narxi(h4) is None, narxi(h4))
    # Sessiyada hali yozilmagan narx o'zgarishi ham ko'rinadi (`db.get`)
    narx_qoy(A_ID, 1_000)
    d = SessionLocal()
    try:
        d.get(Inventory, A_ID).price_per_unit = 7_000
        crud.log_movement(d, A_ID, "BN A kley", "out", 1, "kg", reason="Brak — sessiya (1 birlik)", company_id=1)
        d.commit()
        h5 = d.query(InventoryMovement).order_by(InventoryMovement.id.desc()).first().id
    finally:
        d.close()
    check("A5 bir sessiyadagi yozilmagan narx (7 000) harakatga tushadi", narxi(h5) == 7_000, narxi(h5))
    # Tozalash: A bo'limi harakatlari keyingi jamilarni buzmasin
    d = SessionLocal()
    try:
        d.query(InventoryMovement).filter(InventoryMovement.id.in_([h1, h2, h3, h4, h5])).delete(synchronize_session=False)
        d.commit()
    finally:
        d.close()
    # Narxni o'qish yiqilsa ham harakat yozilishi SHART (narxsiz)
    _asl_get = None
    d = SessionLocal()
    try:
        _asl_get = d.get

        _bir_marta = [True]

        def _yiqiluvchi_get(model, *a, **k):
            # Faqat BIRINCHI chaqiruv (log_movement narxi) yiqiladi — keyingi
            # chaqiruvlar (flush dagi korxona qo'riqchisi) odatdagidek.
            if model is Inventory and _bir_marta[0]:
                _bir_marta[0] = False
                raise RuntimeError("sinov: narx o'qilmadi")
            return _asl_get(model, *a, **k)
        d.get = _yiqiluvchi_get
        _oldin = d.query(InventoryMovement).count()
        crud.log_movement(d, A_ID, "BN A kley", "out", 1, "kg", reason="Brak — get yiqildi (1 birlik)", company_id=1)
        d.commit()
        _keyin = d.query(InventoryMovement).count()
        h6 = d.query(InventoryMovement).order_by(InventoryMovement.id.desc()).first()
        check("A6 narxni o'qish yiqilsa ham harakat yoziladi (narxsiz)",
              _keyin == _oldin + 1 and h6.reason == "Brak — get yiqildi (1 birlik)"
              and getattr(h6, "unit_cost", "USTUN_YOQ") is None, (_oldin, _keyin, h6.reason))
        d.query(InventoryMovement).filter(InventoryMovement.id == h6.id).delete(synchronize_session=False)
        d.commit()
    finally:
        d.close()
except Exception as e:                     # noqa: BLE001
    check("A bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# B. Hisobot muzlatilgan narxni o'qiydi
# ══════════════════════════════════════════════════════════════
section("B. Brak xarajati — narx o'zgarsa ham o'tgan brak o'zgarmaydi")
try:
    OID_B, _ = buyurtma()
    B_ID = yangi_material("BN B kley", 1_000)
    j0 = jami_brak()
    chiqim(B_ID, "BN B kley", 2, "Brak — sinov B (2 birlik)", order_id=OID_B)
    check("B1 brak 2 kg × 1 000 → jami +2 000", taxminan(jami_brak() - j0, 2_000), jami_brak() - j0)
    narx_qoy(B_ID, 3_000)
    check("B2 narx 3 000 ga o'zgardi — jami O'ZGARMADI (+2 000)", taxminan(jami_brak() - j0, 2_000), jami_brak() - j0)
    m = mat_qiymat("BN B kley")
    check("B3 by_material: qiymat 2 000, 1 birlik narxi 1 000", m.get("value") == 2_000 and taxminan(m.get("unit_price"), 1_000), m)
    o = buy_qiymat(OID_B)
    check("B4 by_order: shu buyurtma qiymati 2 000", o.get("total_value") == 2_000
          and [i.get("value") for i in o.get("items") or []] == [2_000], o)
    chiqim(B_ID, "BN B kley", 1, "Brak — sinov B2 (1 birlik)", order_id=OID_B)
    check("B5 yangi narxdagi ikkinchi brak 1 kg × 3 000 → jami +5 000", taxminan(jami_brak() - j0, 5_000), jami_brak() - j0)
    m = mat_qiymat("BN B kley")
    check("B6 by_material turli narxlarda: miqdor 3, qiymat 5 000, o'rtacha narx 5 000 / 3",
          m.get("quantity") == 3 and m.get("value") == 5_000 and taxminan(m.get("unit_price"), 5_000 / 3), m)
    check("B7 by_order: 2 000 + 3 000", buy_qiymat(OID_B).get("total_value") == 5_000, buy_qiymat(OID_B))
    narx_qoy(B_ID, 10)
    check("B8 narx yana o'zgardi (10) — jami baribir +5 000", taxminan(jami_brak() - j0, 5_000), jami_brak() - j0)
except Exception as e:                     # noqa: BLE001
    check("B bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# C. Eski harakat (narxsiz) — joriy narx, avvalgidek
# ══════════════════════════════════════════════════════════════
section("C. Yangilanishdan oldingi harakat — joriy narx (taxmin qilinmaydi)")
try:
    C_ID = yangi_material("BN C kley", 1_000)
    hc = chiqim(C_ID, "BN C kley", 2, "Brak — sinov C (2 birlik)")
    with engine.begin() as cn:
        cn.execute(text("UPDATE inventory_movements SET unit_cost = NULL WHERE id = :i"), {"i": hc})
    check("C0 eski holat tayyor (unit_cost NULL)", narxi(hc) is None, narxi(hc))
    check("C1 eski harakat joriy narx bilan: 2 000", mat_qiymat("BN C kley").get("value") == 2_000, mat_qiymat("BN C kley"))
    narx_qoy(C_ID, 4_000)
    check("C2 narx o'zgarsa eski harakat qiymati ham o'zgaradi: 8 000 (avvalgi xulq)",
          mat_qiymat("BN C kley").get("value") == 8_000, mat_qiymat("BN C kley"))
    chiqim(C_ID, "BN C kley", 1, "Brak — sinov C2 (1 birlik)")
    check("C3 aralash: eski 2 × 4 000 + yangi 1 × 4 000 = 12 000", mat_qiymat("BN C kley").get("value") == 12_000,
          mat_qiymat("BN C kley"))
    narx_qoy(C_ID, 5_000)
    check("C4 narx 5 000: eski 10 000 + yangi (muzlatilgan) 4 000 = 14 000",
          mat_qiymat("BN C kley").get("value") == 14_000, mat_qiymat("BN C kley"))
    # Brak paytida narxi belgilanmagan material: muzlatilgan qiymat 0 —
    # keyin narx qo'yilsa ham o'tgan brak 0 bo'lib qoladi (NULL emas, 0).
    C0_ID = yangi_material("BN C narxsiz", None)
    chiqim(C0_ID, "BN C narxsiz", 2, "Brak — sinov C narxsiz (2 birlik)")
    check("C5 narxsiz material braki — qiymat 0", mat_qiymat("BN C narxsiz").get("value") == 0, mat_qiymat("BN C narxsiz"))
    narx_qoy(C0_ID, 5_000)
    check("C6 keyin narx qo'yildi (5 000) — o'tgan brak baribir 0 (muzlatilgan 0 zaxiraga tushmaydi)",
          mat_qiymat("BN C narxsiz").get("value") == 0, mat_qiymat("BN C narxsiz"))
except Exception as e:                     # noqa: BLE001
    check("C bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# D. Haqiqiy yo'l — API orqali detal braki (penoplast + loy)
# ══════════════════════════════════════════════════════════════
section("D. Detal braki (API) — penoplast, tayyor loy, kley muzlatiladi; moliya o'zgarmaydi")
try:
    narx_qoy(LOY_ID, 1_500)
    oid, iid = buyurtma(qoplama=True)
    j0, oy0, sp0 = jami_brak(), oylik_brak(), split_brak()
    r, rid = brak(oid, iid, 10, qoplama_tortilgan=True)
    check("D1 brak yozildi (200)", r.status_code == 200 and rid, f"{r.status_code} {r.text[:200]}")
    hn = harakat_narxlari(rid)
    check("D2 uchala harakatda unit_cost = o'sha paytdagi narx (penoplast 500 000, tayyor loy 1 500, kley 2 000)",
          hn.get(PENO_ID) == 500_000 and hn.get(LOY_ID) == 1_500 and hn.get(KLEY_ID) == 2_000, hn)
    j1, oy1, sp1 = jami_brak(), oylik_brak(), split_brak()
    check("D3 brak xarajati oshdi — oylik hisobotda ham, liniya hisobotida (penoplast) ham xuddi shuncha",
          j1 > j0 and taxminan(oy1 - oy0, j1 - j0, 1.0) and isinstance(sp1, tuple)
          and abs((sp1[0] - sp0[0]) - (j1 - j0)) <= 1, (j0, j1, oy0, oy1, sp0, sp1))
    narx_qoy(PENO_ID, 1_500_000)
    narx_qoy(KLEY_ID, 6_000)
    narx_qoy(LOY_ID, 4_500)
    check("D4 uchala narx 3 baravar oshdi — xulosa jami O'ZGARMADI", taxminan(jami_brak(), j1, 0.5), (j1, jami_brak()))
    check("D5 oylik hisobot brak_xarajat O'ZGARMADI (sof foyda)", taxminan(oylik_brak(), oy1, 0.5), (oy1, oylik_brak()))
    check("D6 liniya hisoboti (penoplast brak_xarajati va sof_foyda) O'ZGARMADI", split_brak() == sp1, (sp0, sp1, split_brak()))
    narx_qoy(PENO_ID, 500_000)
    narx_qoy(KLEY_ID, 2_000)
    narx_qoy(LOY_ID, 1_500)
    # Qoplamasiz brak: yozuv summasi (tan narx) == xarajat (ikkalasi yozish paytidagi narx)
    oid2, iid2 = buyurtma()
    j2 = jami_brak()
    r2, rid2 = brak(oid2, iid2, 5)
    summa = float((js(r2) or {}).get("refund_amount") or 0) if isinstance(js(r2), dict) else 0
    check("D7 qoplamasiz brak — yozuv summasi xarajatga teng", r2.status_code == 200 and summa > 0
          and abs((jami_brak() - j2) - summa) <= 1, (summa, jami_brak() - j2))
    narx_qoy(PENO_ID, 900_000)
    check("D8 penoplast narxi o'zgargach ham yozuv summasi va xarajat teng",
          abs((jami_brak() - j2) - summa) <= 1, (summa, jami_brak() - j2))
    narx_qoy(PENO_ID, 500_000)
    rd = ochir(rid2)
    check("D9 brak o'chirildi — xarajat asliga (6-qadam bilan mos)", rd.status_code == 200 and taxminan(jami_brak(), j2, 0.5),
          (rd.status_code, j2, jami_brak()))
except Exception as e:                     # noqa: BLE001
    check("D bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# M. Migratsiya
# ══════════════════════════════════════════════════════════════
section("M. Migratsiya")
try:
    ust = {c["name"]: c for c in sa_inspect(engine).get_columns("inventory_movements")}
    check("M1 yangi bazada unit_cost ustuni bor", "unit_cost" in ust, sorted(ust))
    mig = getattr(main, "_migrate_harakat_narx", None)
    check("M2 main._migrate_harakat_narx mavjud", callable(mig), "")
    if callable(mig):
        _eski_soni = None
        with engine.begin() as cn:
            _eski_soni = cn.execute(text("SELECT COUNT(*) FROM inventory_movements")).scalar()
            cn.execute(text("ALTER TABLE inventory_movements DROP COLUMN unit_cost"))
        check("M3 eski holat tayyor (ustun olib tashlandi)",
              "unit_cost" not in {c["name"] for c in sa_inspect(engine).get_columns("inventory_movements")}, "")
        with contextlib.redirect_stdout(_quiet):
            mig()
            mig()
        ust2 = {c["name"] for c in sa_inspect(engine).get_columns("inventory_movements")}
        with engine.begin() as cn:
            n = cn.execute(text("SELECT COUNT(*) FROM inventory_movements")).scalar()
            nn = cn.execute(text("SELECT COUNT(*) FROM inventory_movements WHERE unit_cost IS NOT NULL")).scalar()
        check("M4 migratsiya ustunni qaytardi (ikki marta — xatosiz), harakatlar soni o'zgarmadi, eski qiymatlar NULL",
              "unit_cost" in ust2 and n == _eski_soni and nn == 0, (ust2, n, _eski_soni, nn))
        engine.dispose()
        narx_qoy(A_ID, 1_000)
        hm = chiqim(A_ID, "BN A kley", 1, "Brak — migratsiyadan keyin (1 birlik)")
        check("M5 migratsiyadan keyin yangi chiqim narxi yoziladi", narxi(hm) == 1_000, narxi(hm))
except Exception as e:                     # noqa: BLE001
    check("M bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# S. Statik
# ══════════════════════════════════════════════════════════════
section("S. Statik")
try:
    csrc = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
    ssrc = open(os.path.join(ROOT, "services.py"), encoding="utf-8").read()
    msrc = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    osrc = open(os.path.join(ROOT, "models.py"), encoding="utf-8").read()
    for s in (csrc, ssrc, msrc, osrc):
        ast.parse(s)
    im = osrc[osrc.find("class InventoryMovement"):]
    im = im[:im.find("\nclass ", 10)]
    check("S1 model: unit_cost = Column(Float, nullable=True)", "unit_cost = Column(Float, nullable=True)" in im, "")
    lm = csrc[csrc.find("def log_movement"):]
    lm = lm[:lm.find("\ndef ", 10)]
    check("S2 log_movement: faqat \"out\" da, sessiya obyekti (db.get) bilan narx, harakatga yoziladi",
          tartibda(lm, 'if movement_type == "out" and inventory_id:', "try:", "db.get(Inventory, inventory_id)",
                   "float(_inv_narx.price_per_unit or 0)", "unit_cost=_narx"), "")
    dd = ssrc[ssrc.find("def deduct_raw_material_for_brak"):]
    dd = dd[:dd.find("\ndef ", 10)]
    check("S3 services penoplast harakati narxni yozadi", "unit_cost=float(p.price_per_unit or 0)" in dd, "")
    check("S4 InventoryMovement(...) yozuvchilari faqat ikkita (log_movement va services penoplast)",
          csrc.count("InventoryMovement(") == 1 and ssrc.count("InventoryMovement(") == 1
          and msrc.count("InventoryMovement(") == 0,
          (csrc.count("InventoryMovement("), ssrc.count("InventoryMovement("), msrc.count("InventoryMovement(")))
    bs = csrc[csrc.find("def get_brak_material_summary"):]
    bs = bs[:bs.find("\ndef ", 10)]
    check("S5 xulosa: ikkala sikl _harakat_narxi dan, joriy narx faqat zaxira",
          bs.count("price = _harakat_narxi(r, inv)") == 2 and "if harakat.unit_cost is not None:" in bs
          and bs.count("inv.price_per_unit") == 1, (bs.count("price = _harakat_narxi(r, inv)"), bs.count("inv.price_per_unit")))
    check("S6 migratsiya modul darajasida, brak harakati migratsiyasidan keyin chaqiriladi",
          tartibda(msrc, "def _migrate_harakat_narx", "\n_migrate_brak_harakat()\n", "\n_migrate_harakat_narx()\n")
          or tartibda(msrc, "\n_migrate_brak_harakat()\n", "def _migrate_harakat_narx", "\n_migrate_harakat_narx()\n"), "")
except Exception as e:                     # noqa: BLE001
    check("S bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
