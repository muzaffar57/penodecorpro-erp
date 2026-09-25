#!/usr/bin/env python3
"""
test_mrp_kerak.py — kech72 darvozasi (2026-09-25, 85-band / K71-2): MRP detali uchun "hali ishlab chiqarish
KERAK" miqdori — YAGONA qoida.

NIMA UCHUN (asl kod `8384fcb` (zip 68) da O'LCHANGAN — `work/probe85.py`, `work/probe85b.py`; jonli ham)
-------------------------------------------------------------------------------------------------------
To'rt joyda (`production_service`: tayyorlik belgisi, "Mijoz buyurtmasi asosida" ro'yxati, ishlab chiqarish
buyurtmasini yaratish va boshlash) kerak = `quantity − SUM(band)` edi — TOPSHIRILGAN miqdor va buyurtma
yaratilganda OMBORDAN olingan detal hisobga olinmasdi:
  * detal 10, 10 ishlab chiqarilgan, 5 topshirilgan -> belgi "tayyor EMAS, yana 5", ro'yxatda "kerak 5";
  * TO'LIQ topshirilgan detal -> ro'yxatda "kerak 10", yangi ishlab chiqarish QABUL qilinib boshlanardi
    (xomashyo ikkinchi marta yechiladi, ortiqcha mahsulot topshirilgan detalga band bo'lib qoladi);
  * detal 10, 5 ishlab chiqarilib topshirilgan -> PO 10 qabul (5 ortiqcha);
  * ombordagi tayyor mahsulotdan olingan detal -> "kerak 3", PO 3 qabul va boshlandi.
  Jonli (sinov sayti, kech72): buyurtma 198 detal 664 (30 / topshirilgan 18 / band 12) — ro'yxatda "kerak 18".

YECHIM (texnik — Claude): `production_service.mrp_detal_kerak(db, order_item)` —
kerak = qolgan (`OrderItem.remaining_qty`: buyurtma − topshirilgan − omborga ortiqcha; ombordan olingan detal
uchun 0) − band. To'rt joy ham shundan; rad xabarida sabab (band / topshirilgan / ombordan).

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi (+ parallel boshlash P).
    python3 tools/test_mrp_kerak.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_kerak.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_kerak_test"
_DB = os.path.join(tempfile.gettempdir(), "mrp_kerak_test.db")

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
    import auth                                    # noqa: E402
    import production_service                      # noqa: E402

from sqlalchemy import text                        # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, FinishedProduct, OrderItem, ReturnItem, ReturnReason,
)
from production_models import ProductionOrder      # noqa: E402
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


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


def sql(q, **p):
    """Bitta qiymat qaytaradigan xom SQL; xato -> ('XATO', matn)."""
    try:
        with engine.connect() as c:
            r = c.execute(text(q), p)
            v = r.scalar() if r.returns_rows else None
            c.commit()
            return v
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {str(e)[:160]}")


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "MK_admin", "Parol123!", UserRole.ADMIN, "MK Admin", company_id=1)
PRJ = Project(company_id=1, client_name="MK Mijoz", project_name="MK loyiha", total_budget=0, total_paid=0)
TOSH = Inventory(company_id=1, item_name="MK Tosh", unit="kg", stock_quantity=1_000_000, price_per_unit=1_000,
                 category="Kimyo")
_db.add_all([PRJ, TOSH])
_db.commit()
ID = {"PRJ": PRJ.id, "TOSH": TOSH.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "MK_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "MK Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Oddiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 3}]})) or {}).get("id")
print("PT", PT, "BOM", BOM)

_n = [0]


def nom():
    _n[0] += 1
    return f"MK_D{_n[0]}"


def buyurtma(soni, qoshimcha=None):
    """MRP detalli buyurtma (jarayonda). -> (order_id, order_item_id); xato -> (None, None)."""
    it = {"name": nom(), "category": "mrp_product", "quantity": soni, "unit_price": 100_000,
          "is_coated": False, "penoplast_id": None, "product_type_id": PT}
    if qoshimcha:
        it.update(qoshimcha)
    tana = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": 0, "items": [it]}
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id")
    if not oid:
        print("   buyurtma yaratilmadi:", r.status_code, (r.text or "")[:300])
        return None, None
    s = SessionLocal()
    try:
        iid = s.query(OrderItem.id).filter(OrderItem.order_id == oid).scalar()
    finally:
        s.close()
    return oid, iid


def po_draft(oid, iid, miqdor, manba_turi="customer_order"):
    """Ishlab chiqarish buyurtmasi (DRAFT). -> {st, po, msg}."""
    tana = {"product_type_id": PT, "bom_id": BOM, "quantity": miqdor, "source_type": manba_turi}
    if manba_turi == "customer_order":
        tana.update({"source_order_id": oid, "source_order_item_id": iid})
    r = req(C, "post", "/api/production/orders", json=tana)
    d = js(r) or {}
    det = d.get("detail")
    msg = d.get("message") or (det.get("message") if isinstance(det, dict) else det) or ""
    return {"st": r.status_code, "po": (d.get("production_order") or {}).get("id"), "msg": str(msg)}


def po_start(po):
    r = req(C, "post", f"/api/production/orders/{po}/start")
    d = js(r) or {}
    det = d.get("detail")
    msg = d.get("message") or (det.get("message") if isinstance(det, dict) else det) or ""
    return {"st": r.status_code, "msg": str(msg)}


def po_yarat(oid, iid, miqdor, manba_turi="customer_order"):
    """Yaratib, boshlab, yakunlaydi -> po id (xato -> None)."""
    d = po_draft(oid, iid, miqdor, manba_turi)
    if not d["po"]:
        print("   PO yaratilmadi:", d)
        return None
    for q in ("start", "complete"):
        r1 = req(C, "post", f"/api/production/orders/{d['po']}/{q}")
        if r1.status_code != 200:
            print(f"   PO {q}:", r1.status_code, (r1.text or "")[:300])
            return None
    return d["po"]


def yuk(oid, iid, miqdor):
    r = req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom(),
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    return r.status_code


def tayyorlik(oid, iid):
    """GET /api/orders/{id} -> mrp_readiness: (fully_ready, shu detal qatori)."""
    mr = (js(req(C, "get", f"/api/orders/{oid}")) or {}).get("mrp_readiness") or {}
    qator = next((x for x in (mr.get("items") or []) if x.get("order_item_id") == iid), None)
    return mr.get("fully_ready"), qator or {}


def royxat(iid):
    """GET /api/production/mrp-order-items -> shu detal qatori (yo'q bo'lsa None)."""
    L = js(req(C, "get", "/api/production/mrp-order-items", params={"product_type_id": PT})) or []
    if not isinstance(L, list):
        return ("XATO", L)
    return next((x for x in L if x.get("order_item_id") == iid), None)


def band_jami(iid):
    s = SessionLocal()
    try:
        return round(sum(float(f.reserved_quantity or 0) for f in s.query(FinishedProduct).filter(
            FinishedProduct.reserved_for_order_item_id == iid).all()), 6)
    finally:
        s.close()


def tm_soni(iid):
    return sql("SELECT COUNT(*) FROM finished_products WHERE reserved_for_order_item_id = :i", i=iid)


def po_holati(po):
    s = SessionLocal()
    try:
        p = s.get(ProductionOrder, po)
        return getattr(getattr(p, "status", None), "value", str(getattr(p, "status", None))) if p else None
    finally:
        s.close()


def tosh_qoldiq():
    s = SessionLocal()
    try:
        return round(float(s.get(Inventory, ID["TOSH"]).stock_quantity or 0), 6)
    finally:
        s.close()


def ortiqcha_yoz(oid, iid, miqdor):
    """Omborga qo'yilgan ORTIQCHA qism (57-band) — ORM bilan to'g'ridan (qaytarish oqimining ombor
    ta'siri bu testga tegishli emas; `OrderItem.remaining_qty` faqat `ortiqcha_miqdor` ni o'qiydi)."""
    s = SessionLocal()
    try:
        s.add(ReturnItem(company_id=1, order_id=oid, order_item_id=iid, item_name="MK ortiqcha", quantity=miqdor,
                         unit="m²", reason=ReturnReason.EXCESS, ortiqcha_miqdor=miqdor, refund_amount=0))
        s.commit()
    finally:
        s.close()


def kerak_dict(iid):
    """Yordamchining o'zi (asl kodda yo'q -> None, QULAMAYDI)."""
    f = getattr(production_service, "mrp_detal_kerak", None)
    if f is None:
        return None
    s = SessionLocal()
    try:
        return f(s, s.get(OrderItem, iid))
    except Exception as e:                 # noqa: BLE001
        return {"XATO": f"{type(e).__name__}: {e}"}
    finally:
        s.close()


# Umumiy omborga TM (band emas) — "ombordan olingan detal" fiksturasi uchun
POW = po_yarat(None, None, 20, manba_turi="warehouse_stock")
_s = SessionLocal()
try:
    FW = _s.query(FinishedProduct.id).filter(FinishedProduct.reserved_for_order_item_id.is_(None),
                                             FinishedProduct.product_type_id == PT,
                                             FinishedProduct.company_id == 1).order_by(FinishedProduct.id.desc()).scalar()
finally:
    _s.close()

# ══════════════════════════════════════════════════════════════
section("A. Tayyorlik belgisi (GET /api/orders/{id} -> mrp_readiness)")
# ══════════════════════════════════════════════════════════════
o1, i1 = buyurtma(10)
po_yarat(o1, i1, 10)
_f, _q = tayyorlik(o1, i1)
check("A0 fikstura (nazorat): detal 10, 10 ishlab chiqarilgan -> tayyor, yana 0",
      _f is True and _q.get("is_ready") is True and taxminan(_q.get("remaining_quantity"), 0), [_f, _q])
_st = yuk(o1, i1, 5)
_f, _q = tayyorlik(o1, i1)
check("A1 yuk 5 (band 5 qoldi) -> HALI tayyor, yana 0; band 5, topshirilgan 5",
      _st == 200 and _f is True and _q.get("is_ready") is True and taxminan(_q.get("remaining_quantity"), 0)
      and taxminan(_q.get("reserved_quantity"), 5) and taxminan(_q.get("delivered_quantity"), 5), [_st, _f, _q])
_st = yuk(o1, i1, 5)
_f, _q = tayyorlik(o1, i1)
check("A2 to'liq topshirildi (10 / 10) -> tayyor, yana 0 (eski kod: 'yana 10')",
      _st == 200 and _f is True and _q.get("is_ready") is True and taxminan(_q.get("remaining_quantity"), 0)
      and taxminan(_q.get("delivered_quantity"), 10), [_st, _f, _q])
o2, i2 = buyurtma(10)
po_yarat(o2, i2, 5)
_st = yuk(o2, i2, 5)
_f, _q = tayyorlik(o2, i2)
check("A3 detal 10, 5 ishlab chiqarilib topshirilgan -> tayyor EMAS, yana 5 (eski kod: 10)",
      _st == 200 and _f is False and _q.get("is_ready") is False and taxminan(_q.get("remaining_quantity"), 5),
      [_st, _f, _q])
o3, i3 = buyurtma(10)
_f, _q = tayyorlik(o3, i3)
check("A4 nazorat: yangi detal 10 -> tayyor EMAS, yana 10",
      _f is False and taxminan(_q.get("remaining_quantity"), 10), [_f, _q])
o4, i4 = buyurtma(3, {"finished_product_id": FW})
_f, _q = tayyorlik(o4, i4)
check("A5 ombordan olingan detal (finished_product_id) -> tayyor, yana 0 (eski kod: 'yana 3')",
      o4 and FW and _f is True and _q.get("is_ready") is True and taxminan(_q.get("remaining_quantity"), 0),
      [o4, FW, _f, _q])

# ══════════════════════════════════════════════════════════════
section("B. \"Mijoz buyurtmasi asosida\" ro'yxati (GET /api/production/mrp-order-items)")
# ══════════════════════════════════════════════════════════════
check("B1 to'liq topshirilgan detal ro'yxatda YO'Q (eski kod: 'kerak 10')", royxat(i1) is None, royxat(i1))
o5, i5 = buyurtma(10)
po_yarat(o5, i5, 10)
_st = yuk(o5, i5, 5)
check("B2 detal 10, 10 ishlab chiqarilgan, 5 topshirilgan (band 5) -> ro'yxatda YO'Q (eski kod: 'kerak 5')",
      _st == 200 and royxat(i5) is None, [_st, royxat(i5)])
_r = royxat(i2) or {}
check("B3 5 ishlab chiqarilib topshirilgan detal 10 -> kerak 5, band 0, topshirilgan 5 (eski kod: 10)",
      taxminan(_r.get("remaining_quantity"), 5) and taxminan(_r.get("already_reserved"), 0)
      and taxminan(_r.get("delivered_quantity"), 5) and taxminan(_r.get("needed_quantity"), 10), _r)
_r = royxat(i3) or {}
check("B4 nazorat: yangi detal 10 -> kerak 10", taxminan(_r.get("remaining_quantity"), 10), _r)
check("B5 ombordan olingan detal ro'yxatda YO'Q (eski kod: 'kerak 3')", royxat(i4) is None, royxat(i4))
o6, i6 = buyurtma(10)
po_yarat(o6, i6, 5)
ortiqcha_yoz(o6, i6, 3)
_r = royxat(i6) or {}
check("B6 detal 10, band 5, omborga ORTIQCHA 3 -> kerak 2 (qolgan 7 - band 5; eski kod: 5)",
      taxminan(_r.get("remaining_quantity"), 2) and taxminan(_r.get("already_reserved"), 5), _r)
_L = js(req(C, "get", "/api/production/mrp-order-items")) or []
check("B7 turi ko'rsatilmagan ro'yxat ham shu qoida: i3 kerak 10 bor, i1 / i5 / i4 yo'q",
      isinstance(_L, list) and any(x.get("order_item_id") == i3 and taxminan(x.get("remaining_quantity"), 10) for x in _L)
      and not any(x.get("order_item_id") in (i1, i5, i4) for x in _L), [len(_L) if isinstance(_L, list) else _L])

# ══════════════════════════════════════════════════════════════
section("C. Ishlab chiqarish buyurtmasini YARATISH (dastlabki tekshiruv)")
# ══════════════════════════════════════════════════════════════
_d = po_draft(o2, i2, 10)
check("C1 kerak 5 detalga PO 10 -> 400, xabar 'endi faqat 5' + '5 topshirilgan' (eski kod: 200)",
      _d["st"] == 400 and not _d["po"] and "endi faqat 5 " in _d["msg"] and "5 topshirilgan" in _d["msg"], _d)
_d = po_draft(o2, i2, 5.001)
check("C2 chegara: kerak 5, PO 5.001 -> 400", _d["st"] == 400 and not _d["po"], _d)
_d = po_draft(o2, i2, 5)
check("C3 chegara: kerak 5, PO 5 -> 200 (DRAFT)", _d["st"] == 200 and _d["po"], _d)
_d = po_draft(o1, i1, 1)
check("C4 to'liq topshirilgan detalga PO 1 -> 400 'endi faqat 0' (eski kod: 200)",
      _d["st"] == 400 and not _d["po"] and "endi faqat 0 " in _d["msg"], _d)
_d = po_draft(o4, i4, 3)
check("C5 ombordan olingan detalga PO 3 -> 400, sabab 'ombordagi tayyor mahsulotdan olingan' (eski kod: 200)",
      _d["st"] == 400 and not _d["po"] and "ombordagi tayyor mahsulotdan olingan" in _d["msg"], _d)
_d = po_draft(o5, i5, 1)
check("C6 detal 10, band 5, topshirilgan 5 -> PO 1 -> 400 (eski kod: 200)", _d["st"] == 400 and not _d["po"], _d)
_d = po_draft(o3, i3, 10)
check("C7 nazorat: yangi detal 10, PO 10 -> 200", _d["st"] == 200 and _d["po"], _d)
o7, i7 = buyurtma(10)
po_yarat(o7, i7, 10)
ortiqcha_yoz(o7, i7, 3)
_d = po_draft(o7, i7, 1)
_f, _q = tayyorlik(o7, i7)
check("C8 ortiqcha band (qolgan 7 < band 10): PO 1 -> 400 'endi faqat 0' (manfiy EMAS); belgi tayyor, yana 0; ro'yxatda yo'q",
      _d["st"] == 400 and "endi faqat 0 " in _d["msg"] and "endi faqat -" not in _d["msg"]
      and _f is True and taxminan(_q.get("remaining_quantity"), 0) and royxat(i7) is None, [_d, _f, _q, royxat(i7)])

# ══════════════════════════════════════════════════════════════
section("D. BOSHLASH (HAQIQIY, qulfli tekshiruv)")
# ══════════════════════════════════════════════════════════════
o8, i8 = buyurtma(10)
_db8 = po_draft(o8, i8, 10)                       # hali hech narsa yo'q — kerak 10, qabul
po_yarat(o8, i8, 5)                               # 5 ishlab chiqarildi (band 5)
_st = yuk(o8, i8, 5)                              # 5 topshirildi (band 0) -> kerak 5
_tosh0 = tosh_qoldiq()
_tm0 = tm_soni(i8)
_s = po_start(_db8["po"]) if _db8["po"] else {"st": None, "msg": ""}
check("D1 draft PO 10 (yuk 5 dan oldin yaratilgan) boshlanganda -> RAD, xabarda '5 topshirilgan' (eski kod: 200)",
      _db8["st"] == 200 and _st == 200 and _s["st"] not in (200, None) and "endi faqat 5 " in _s["msg"]
      and "5 topshirilgan" in _s["msg"], [_db8, _st, _s])
check("D2 rad etilgan boshlash hech narsaga tegmadi: yangi TM yo'q, xomashyo o'zgarmadi, PO DRAFT",
      tm_soni(i8) == _tm0 and taxminan(tosh_qoldiq(), _tosh0) and str(po_holati(_db8["po"])).lower() == "draft",
      [tm_soni(i8), _tm0, tosh_qoldiq(), _tosh0, po_holati(_db8["po"])])
_dc = po_draft(o8, i8, 5)
_sc = po_start(_dc["po"]) if _dc["po"] else {"st": None}
check("D3 nazorat: kerak 5, PO 5 yaratildi va boshlandi -> 200, band 5",
      _dc["st"] == 200 and _sc["st"] == 200 and taxminan(band_jami(i8), 5), [_dc, _sc, band_jami(i8)])
o9, i9 = buyurtma(3)
_d9 = po_draft(o9, i9, 3)
_s = SessionLocal()
try:
    _s.get(OrderItem, i9).finished_product_id = FW  # tahrirda detal ombordagi TM ga bog'landi (taqlid)
    _s.commit()
finally:
    _s.close()
_s9 = po_start(_d9["po"]) if _d9["po"] else {"st": None, "msg": ""}
check("D4 draftdan keyin detal ombordan olinadigan bo'ldi -> boshlash RAD, sabab 'ombordagi' (eski kod: 200)",
      _d9["st"] == 200 and _s9["st"] not in (200, None) and "ombordagi tayyor mahsulotdan olingan" in _s9["msg"]
      and tm_soni(i9) == 0, [_d9, _s9, tm_soni(i9)])

# ══════════════════════════════════════════════════════════════
section("E. Yordamchi to'g'ridan (production_service.mrp_detal_kerak)")
# ══════════════════════════════════════════════════════════════
_k = kerak_dict(i2) or {}
check("E1 i2: band 0, topshirilgan 5, qolgan 5, kerak 5, ombordan emas",
      taxminan(_k.get("band"), 0) and taxminan(_k.get("topshirilgan"), 5) and taxminan(_k.get("qolgan"), 5)
      and taxminan(_k.get("kerak"), 5) and _k.get("ombordan") is False, _k)
_k = kerak_dict(i4) or {}
check("E2 ombordan olingan: qolgan 0, kerak 0, ombordan True",
      taxminan(_k.get("qolgan"), 0) and taxminan(_k.get("kerak"), 0) and _k.get("ombordan") is True, _k)
_k = kerak_dict(i7) or {}
check("E3 ortiqcha band: qolgan 7, band 10, kerak -3 (manfiy — chaqiruvchi max bilan ko'rsatadi)",
      taxminan(_k.get("qolgan"), 7) and taxminan(_k.get("band"), 10) and taxminan(_k.get("kerak"), -3), _k)
_k = kerak_dict(i6) or {}
check("E4 ortiqcha 3, band 5: qolgan 7, kerak 2", taxminan(_k.get("qolgan"), 7) and taxminan(_k.get("kerak"), 2), _k)

# ══════════════════════════════════════════════════════════════
section("P. Parallel BOSHLASH (faqat HAQIQIY PG): kerak 5, bir vaqtda ikki draft PO 5")
# ══════════════════════════════════════════════════════════════
if PG_URL:
    import threading
    o10, i10 = buyurtma(10)
    po_yarat(o10, i10, 5)
    yuk(o10, i10, 5)                              # kerak 5 (band 0)
    _pa = po_draft(o10, i10, 5)
    _pb = po_draft(o10, i10, 5)
    _bar = threading.Barrier(2)
    _nat = {}

    def _ish(n, po):
        s = SessionLocal()
        try:
            _bar.wait(timeout=30)
            r = production_service.start_production_order(s, po, company_id=1, performed_by=f"MK{n}")
            _nat[n] = bool((r or {}).get("success"))
        except Exception as e:             # noqa: BLE001
            s.rollback()
            _nat[n] = f"XATO {type(e).__name__}: {str(e)[:120]}"
        finally:
            s.close()

    _th = [threading.Thread(target=_ish, args=(1, _pa["po"])), threading.Thread(target=_ish, args=(2, _pb["po"]))]
    for _x in _th:
        _x.start()
    for _x in _th:
        _x.join(60)
    check("P0 fikstura: ikki draft PO 5 yaratildi (kerak 5 — har biri alohida sig'adi)",
          _pa["st"] == 200 and _pb["st"] == 200, [_pa, _pb])
    check("P1 aynan bittasi boshlandi (ikkinchisi qulfdan keyin kerak 0 ni ko'rib — rad; eski kod: ikkalasi)",
          sorted(v is True for v in _nat.values()) == [False, True], _nat)
    check("P2 band jami 5 (ortiqcha band yo'q), TM bitta", taxminan(band_jami(i10), 5) and tm_soni(i10) == 2,
          [_nat, band_jami(i10), tm_soni(i10)])
else:
    print("  (SQLite — parallel prob o'tkazib yuborildi)")

# ══════════════════════════════════════════════════════════════
section("H. Statik tartib")
# ══════════════════════════════════════════════════════════════
_mk = manba(production_service, "mrp_detal_kerak")
check("H1 yordamchi: band yig'indisi -> ombordan belgisi -> remaining_qty -> kerak = qolgan - band",
      tartibda(_mk, "FinishedProduct.reserved_for_order_item_id == order_item.id",
               "getattr(order_item, 'finished_product_id', None)",
               "qolgan = 0.0 if ombordan else float(order_item.remaining_qty or 0)",
               '"kerak": qolgan - band'), _mk[:200])
_tr = manba(production_service, "get_order_mrp_readiness")
check("H2 tayyorlik belgisi yordamchidan (eski formula YO'Q)",
      tartibda(_tr, "k = mrp_detal_kerak(db, item)", 'remaining = k["kerak"]', '"is_ready": remaining <= 0.0001')
      and "- float(reserved)" not in _tr, _tr[-300:])
_ro = manba(production_service, "get_mrp_order_items_status")
check("H3 ro'yxat yordamchidan, filtr undan KEYIN (eski formula YO'Q)",
      tartibda(_ro, "k = mrp_detal_kerak(db, item)", 'remaining = k["kerak"]', "if remaining <= 0.0001:", "continue")
      and "- float(reserved)" not in _ro, _ro[-300:])
_cr = manba(production_service, "create_production_order")
check("H4 yaratish: yordamchi -> max(0, kerak) -> tekshiruv (eski formula YO'Q)",
      tartibda(_cr, "_k = mrp_detal_kerak(db, order_item)", 'remaining = max(0.0, _k["kerak"])',
               "if data.quantity > remaining + 0.0001:") and "float(already_reserved)" not in _cr, _cr[:200])
_sp = manba(production_service, "start_production_order")
check("H5 boshlash: detal QULFLANADI -> yordamchi -> tekshiruv -> rollback (eski formula YO'Q)",
      tartibda(_sp, "OrderItem.id == po.source_order_item_id", ").with_for_update().first()",
               "_k = mrp_detal_kerak(db, locked_item)", 'remaining = max(0.0, _k["kerak"])',
               "if po.quantity > remaining + 0.0001:", "db.rollback()") and "float(already_reserved)" not in _sp,
      _sp[:200])
_izoh = manba(production_service, "_mrp_kerak_izoh")
check("H6 rad xabari sababi: band, topshirilgan, ombordan",
      tartibda(_izoh, "band qilingan", "topshirilgan", "ombordagi tayyor mahsulotdan olingan"), _izoh[:200])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
