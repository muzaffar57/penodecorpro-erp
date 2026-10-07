#!/usr/bin/env python3
"""
test_mrp_tayyorlik.py — kech80 darvozasi (2026-09-26, 88-band): buyurtmadagi «MRP: tayyor» belgisi va «Tayyor»
tugmasi / yuk xati — BIR XIL shart.

NIMA UCHUN (asl kod `be2fbd8` (zip 75) da O'LCHANGAN — `work/probe88.py`)
--------------------------------------------------------------------------
Belgi (`production_service.get_order_mrp_readiness`) faqat BAND qilinganini tekshirardi, band esa ishlab
chiqarish BOSHLANGANDA qo'yiladi:
  * PO 5 boshlangan, yakunlanmagan -> «✅ MRP: tayyor», «Tayyor» tugmasi 400 «… kerak 5, tayyor 0»;
  * 3 tayyor + 2 jarayonda -> «✅ MRP: tayyor», tugma 400 «… tayyor 3».
«Tayyor» (`services.complete_order`) va yuk xati (`crud.create_delivery` `mrp_kam`) esa faqat TAYYOR TM ni
sanaydi (`crud._mrp_tayyor_qoldiq`).

YECHIM (texnik — Claude): `crud.mrp_tayyor_yetadimi(qolgan, tayyor)` — yagona shart; `crud.mrp_topshirish_holati`
(qolgan / tayyor / jarayonda / yetadi) — belgi shundan; «Tayyor» tugmasi shu shart bilan. Belgi qatorida
`tayyor_quantity`, `ishlab_chiqarilmoqda`; buyurtmada `holat` (tayyor / ishlab_chiqarilmoqda / kutilmoqda);
UI (`orders.html` `mrpTayyorlikBelgisi`) — uchinchi holat «🏭 MRP: ishlab chiqarilmoqda».
`remaining_quantity` (hali ishlab chiqarib band qilish kerak), ro'yxat va PO yaratish — O'ZGARMADI.

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_mrp_tayyorlik.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_tayyorlik.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_tayyorlik_test"
_DB = os.path.join(tempfile.gettempdir(), "mrp_tayyorlik_test.db")

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
    auth.create_user(_db, "MT_admin", "Parol123!", UserRole.ADMIN, "MT Admin", company_id=1)
PRJ = Project(company_id=1, client_name="MT Mijoz", project_name="MT loyiha", total_budget=0, total_paid=0)
TOSH = Inventory(company_id=1, item_name="MT Tosh", unit="kg", stock_quantity=1_000_000, price_per_unit=1_000,
                 category="Kimyo")
_db.add_all([PRJ, TOSH])
_db.commit()
ID = {"PRJ": PRJ.id, "TOSH": TOSH.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "MT_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "MT Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Oddiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 3}]})) or {}).get("id")
print("PT", PT, "BOM", BOM)

_n = [0]


def nom():
    _n[0] += 1
    return f"MT_D{_n[0]}"


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
        s.add(ReturnItem(company_id=1, order_id=oid, order_item_id=iid, item_name="MT ortiqcha", quantity=miqdor,
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

import json                                        # noqa: E402
import re                                          # noqa: E402
import subprocess                                  # noqa: E402
import crud                                        # noqa: E402
import services                                    # noqa: E402
from sqlalchemy import select                      # noqa: E402


def tayyorlik_to_liq(oid):
    """GET /api/orders/{id} -> mrp_readiness (butun lug'at, yo'q bo'lsa {})."""
    return (js(req(C, "get", f"/api/orders/{oid}")) or {}).get("mrp_readiness") or {}


def qator(mr, iid):
    return next((x for x in (mr.get("items") or []) if x.get("order_item_id") == iid), None) or {}


def holat(oid):
    return (js(req(C, "get", f"/api/orders/{oid}")) or {}).get("status")


def tayyor_bos(oid):
    """POST /api/orders/{id}/ready -> (status, xabar)."""
    r = req(C, "post", f"/api/orders/{oid}/ready", json={})
    d = js(r) or {}
    det = d.get("detail")
    return r.status_code, str(d.get("message") or (det.get("message") if isinstance(det, dict) else det) or "")


def yuk_x(oid, iid, miqdor):
    """POST /api/deliveries -> (status, xabar + shortages)."""
    r = req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom(),
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    d = js(r) or {}
    det = d.get("detail")
    if isinstance(det, dict):
        m = str(det.get("message") or "") + " " + " | ".join(str(x) for x in (det.get("shortages") or []))
    else:
        m = str(d.get("message") or det or "")
    return r.status_code, m


def buyurtma_n(sonlar, nomlar=None):
    """Bir nechta MRP detalli buyurtma. -> (order_id, [order_item_id ...] id tartibida)."""
    its = []
    for k, s in enumerate(sonlar):
        its.append({"name": (nomlar[k] if nomlar else nom()), "category": "mrp_product", "quantity": s,
                    "unit_price": 100_000, "is_coated": False, "penoplast_id": None, "product_type_id": PT})
    tana = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": 0, "items": its}
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id")
    if not oid:
        print("   buyurtma yaratilmadi:", r.status_code, (r.text or "")[:300])
        return None, []
    s = SessionLocal()
    try:
        iids = [x for (x,) in s.query(OrderItem.id).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        s.close()
    return oid, iids


def po_tugat(po):
    return req(C, "post", f"/api/production/orders/{po}/complete").status_code


def izchil(mr, st):
    """Belgi va «Tayyor» tugmasi bir xil javob beradimi: fully_ready True <=> 200."""
    return (mr.get("fully_ready") is True) == (st == 200)


MR = {}   # UI bo'limi uchun HAQIQIY API javoblari

# ══════════════════════════════════════════════════════════════
section("A. Belgi (GET /api/orders/{id} -> mrp_readiness) va «Tayyor» tugmasi — BIR XIL shart")
# ══════════════════════════════════════════════════════════════
# A1: ishlab chiqarish BOSHLANGAN, yakunlanmagan (probe88 R1)
oa, ia = buyurtma(5)
da = po_draft(oa, ia, 5)
sa = po_start(da["po"])
mr = tayyorlik_to_liq(oa)
q = qator(mr, ia)
MR["A1"] = mr
check("A1 fikstura: PO 5 boshlandi (in_progress), band 5",
      da["st"] == 200 and sa["st"] == 200 and po_holati(da["po"]) == "in_progress" and taxminan(band_jami(ia), 5),
      [da, sa, po_holati(da["po"]), band_jami(ia)])
check("A1a jarayondagi ishlab chiqarish -> belgi TAYYOR EMAS (eski kod: fully_ready true)",
      mr.get("fully_ready") is False and q.get("is_ready") is False, mr)
check("A1b qator: remaining 0 (yangi ishlab chiqarish kerak EMAS), tayyor 0, ishlab_chiqarilmoqda 5",
      taxminan(q.get("remaining_quantity"), 0) and taxminan(q.get("tayyor_quantity"), 0)
      and taxminan(q.get("ishlab_chiqarilmoqda"), 5), q)
check("A1c holat 'ishlab_chiqarilmoqda'", mr.get("holat") == "ishlab_chiqarilmoqda", mr.get("holat"))
_st, _m = tayyor_bos(oa)
check("A1d «Tayyor» 400 'kerak 5, tayyor 0' va belgi bilan IZCHIL; holat in_progress qoldi",
      _st == 400 and "kerak 5, tayyor 0" in _m and izchil(mr, _st) and holat(oa) == "in_progress", [_st, _m])
check("A1e ro'yxatda (Mijoz buyurtmasi asosida) YO'Q — jarayondagi band yangi ishlab chiqarishni talab qilmaydi",
      royxat(ia) is None, royxat(ia))
# A2: yakunlangach
_c = po_tugat(da["po"])
mr = tayyorlik_to_liq(oa)
q = qator(mr, ia)
MR["A2"] = mr
check("A2a PO yakunlandi -> belgi tayyor, holat 'tayyor', tayyor 5, ishlab_chiqarilmoqda 0",
      _c == 200 and mr.get("fully_ready") is True and q.get("is_ready") is True and mr.get("holat") == "tayyor"
      and taxminan(q.get("tayyor_quantity"), 5) and taxminan(q.get("ishlab_chiqarilmoqda"), 0), [_c, mr])
_st, _m = tayyor_bos(oa)
check("A2b «Tayyor» 200, belgi bilan IZCHIL, buyurtma ready", _st == 200 and izchil(mr, _st) and holat(oa) == "ready",
      [_st, _m, holat(oa)])

# A3: 3 tayyor + 2 jarayonda (probe88 R3)
ob, ib = buyurtma(5)
_a = po_draft(ob, ib, 3)
po_start(_a["po"])
po_tugat(_a["po"])
_b = po_draft(ob, ib, 2)
po_start(_b["po"])
mr = tayyorlik_to_liq(ob)
q = qator(mr, ib)
MR["A3"] = mr
check("A3a 3 tayyor + 2 jarayonda -> belgi TAYYOR EMAS, holat ishlab_chiqarilmoqda (eski: tayyor)",
      mr.get("fully_ready") is False and q.get("is_ready") is False and mr.get("holat") == "ishlab_chiqarilmoqda", mr)
check("A3b qator: remaining 0, tayyor 3, ishlab_chiqarilmoqda 2",
      taxminan(q.get("remaining_quantity"), 0) and taxminan(q.get("tayyor_quantity"), 3)
      and taxminan(q.get("ishlab_chiqarilmoqda"), 2), q)
_st, _m = tayyor_bos(ob)
check("A3c «Tayyor» 400 'kerak 5, tayyor 3' — IZCHIL", _st == 400 and "kerak 5, tayyor 3" in _m and izchil(mr, _st),
      [_st, _m])
po_tugat(_b["po"])
mr = tayyorlik_to_liq(ob)
_st, _m = tayyor_bos(ob)
check("A3d ikkinchi PO yakunlangach -> tayyor, «Tayyor» 200 (IZCHIL)",
      mr.get("fully_ready") is True and mr.get("holat") == "tayyor" and _st == 200 and izchil(mr, _st), [mr, _st, _m])

# A4: faqat DRAFT PO (band yo'q)
oc, ic = buyurtma(4)
po_draft(oc, ic, 4)
mr = tayyorlik_to_liq(oc)
q = qator(mr, ic)
MR["A4"] = mr
check("A4 DRAFT PO -> kutilmoqda, remaining 4, tayyor 0, ishlab_chiqarilmoqda 0 (nazorat)",
      mr.get("fully_ready") is False and mr.get("holat") == "kutilmoqda" and taxminan(q.get("remaining_quantity"), 4)
      and taxminan(q.get("tayyor_quantity"), 0) and taxminan(q.get("ishlab_chiqarilmoqda"), 0), mr)
_st, _m = tayyor_bos(oc)
check("A4b «Tayyor» 400 — IZCHIL", _st == 400 and izchil(mr, _st), [_st, _m])

# A5: 3 tayyor, kerak 5 (boshqa hech narsa)
od, idd = buyurtma(5)
po_yarat(od, idd, 3)
mr = tayyorlik_to_liq(od)
q = qator(mr, idd)
check("A5 3 tayyor / kerak 5 -> kutilmoqda, remaining 2, tayyor 3, ishlab_chiqarilmoqda 0",
      mr.get("fully_ready") is False and mr.get("holat") == "kutilmoqda" and taxminan(q.get("remaining_quantity"), 2)
      and taxminan(q.get("tayyor_quantity"), 3) and taxminan(q.get("ishlab_chiqarilmoqda"), 0), mr)

# A6: 3 tayyor + 1 jarayonda, kerak 5 -> hali 1 ishlab chiqarish kerak
oe, ie = buyurtma(5)
po_yarat(oe, ie, 3)
_e = po_draft(oe, ie, 1)
po_start(_e["po"])
mr = tayyorlik_to_liq(oe)
q = qator(mr, ie)
MR["A6"] = mr
check("A6 3 tayyor + 1 jarayonda / kerak 5 -> KUTILMOQDA (yana 1 kerak), ishlab_chiqarilmoqda 1",
      mr.get("fully_ready") is False and mr.get("holat") == "kutilmoqda" and taxminan(q.get("remaining_quantity"), 1)
      and taxminan(q.get("tayyor_quantity"), 3) and taxminan(q.get("ishlab_chiqarilmoqda"), 1), mr)
_st, _m = tayyor_bos(oe)
check("A6b «Tayyor» 400 — IZCHIL", _st == 400 and izchil(mr, _st), [_st, _m])

# A7: ikki detal — X tayyor, Y jarayonda
of, _l = buyurtma_n([4, 6])
ifx, ify = (_l + [None, None])[:2]
po_yarat(of, ifx, 4)
_f = po_draft(of, ify, 6)
po_start(_f["po"])
mr = tayyorlik_to_liq(of)
MR["A7"] = mr
check("A7a X tayyor + Y jarayonda -> buyurtma ishlab_chiqarilmoqda; X is_ready, Y emas",
      mr.get("fully_ready") is False and mr.get("holat") == "ishlab_chiqarilmoqda"
      and qator(mr, ifx).get("is_ready") is True and qator(mr, ify).get("is_ready") is False, mr)
_st, _m = tayyor_bos(of)
check("A7b «Tayyor» 400 (faqat Y sanaladi: 'kerak 6, tayyor 0') — IZCHIL",
      _st == 400 and "kerak 6, tayyor 0" in _m and "kerak 4" not in _m and izchil(mr, _st), [_st, _m])

# A8: ikki detal — X jarayonda, Y hali ishlab chiqarilmagan
og, _l = buyurtma_n([2, 3])
igx, igy = (_l + [None, None])[:2]
_g = po_draft(og, igx, 2)
po_start(_g["po"])
mr = tayyorlik_to_liq(og)
MR["A8"] = mr
check("A8 X jarayonda + Y ishlab chiqarilmagan -> KUTILMOQDA (ishlab_chiqarilmoqda EMAS)",
      mr.get("fully_ready") is False and mr.get("holat") == "kutilmoqda"
      and taxminan(qator(mr, igy).get("remaining_quantity"), 3)
      and taxminan(qator(mr, igx).get("ishlab_chiqarilmoqda"), 2), mr)

# A9: ombordan olingan detal (finished_product_id) — ishlab chiqarish kutilmaydi
oh, ih = buyurtma(2, {"finished_product_id": FW})
mr = tayyorlik_to_liq(oh)
q = qator(mr, ih)
check("A9 ombordan olingan detal -> tayyor (nazorat)",
      oh and FW and mr.get("fully_ready") is True and q.get("is_ready") is True and mr.get("holat") == "tayyor", mr)
_st, _m = tayyor_bos(oh)
check("A9b «Tayyor» 200 — IZCHIL", _st == 200 and izchil(mr, _st), [_st, _m])

# A10: ortiqcha omborga (qolgan 7 < band 10) — tayyor
oi7, ii7 = buyurtma(10)
po_yarat(oi7, ii7, 10)
ortiqcha_yoz(oi7, ii7, 3)
mr = tayyorlik_to_liq(oi7)
q = qator(mr, ii7)
check("A10 ortiqcha 3 (qolgan 7, tayyor 10) -> tayyor (nazorat, C8 holati)",
      mr.get("fully_ready") is True and q.get("is_ready") is True and taxminan(q.get("tayyor_quantity"), 10), mr)

# A11: jarayondagi band ozod qilindi -> kutilmoqda
oj, ij = buyurtma(5)
_j = po_draft(oj, ij, 5)
po_start(_j["po"])
_s = SessionLocal()
try:
    _fpj = _s.query(FinishedProduct.id).filter(FinishedProduct.reserved_for_order_item_id == ij).scalar()
finally:
    _s.close()
_rl = req(C, "post", f"/api/finished/{_fpj}/release-reservation")
mr = tayyorlik_to_liq(oj)
q = qator(mr, ij)
check("A11 jarayondagi band ozod qilindi -> kutilmoqda, remaining 5, ishlab_chiqarilmoqda 0",
      _rl.status_code == 200 and mr.get("holat") == "kutilmoqda" and taxminan(q.get("remaining_quantity"), 5)
      and taxminan(q.get("ishlab_chiqarilmoqda"), 0), [_rl.status_code, mr])

# ══════════════════════════════════════════════════════════════
section("B. Qisman topshirilgan buyurtma — belgi va YUK XATI bir xil shart")
# ══════════════════════════════════════════════════════════════
ok_, ik_ = buyurtma(10)
po_yarat(ok_, ik_, 5)
_y1 = yuk_x(ok_, ik_, 5)
_k2 = po_draft(ok_, ik_, 5)
po_start(_k2["po"])
mr = tayyorlik_to_liq(ok_)
q = qator(mr, ik_)
MR["B1"] = mr
check("B1 5 topshirilgan + qolgan 5 jarayonda -> ishlab_chiqarilmoqda, remaining 0, tayyor 0",
      _y1[0] == 200 and mr.get("fully_ready") is False and mr.get("holat") == "ishlab_chiqarilmoqda"
      and taxminan(q.get("remaining_quantity"), 0) and taxminan(q.get("tayyor_quantity"), 0)
      and taxminan(q.get("delivered_quantity"), 5), [_y1, mr])
_y2 = yuk_x(ok_, ik_, 5)
check("B2 yuk 5 -> 400 'tayyor (ishlab chiqarilgan) 0' — belgi bilan IZCHIL",
      _y2[0] == 400 and "tayyor (ishlab chiqarilgan) 0" in _y2[1] and (q.get("is_ready") is True) == (_y2[0] == 200),
      _y2)
po_tugat(_k2["po"])
mr = tayyorlik_to_liq(ok_)
q = qator(mr, ik_)
_y3 = yuk_x(ok_, ik_, 5)
check("B3 PO yakunlangach -> belgi tayyor, yuk 5 -> 200 (IZCHIL)",
      mr.get("fully_ready") is True and q.get("is_ready") is True and _y3[0] == 200, [mr, _y3])
mr = tayyorlik_to_liq(ok_)
check("B4 to'liq topshirilgach -> tayyor (nazorat, A2 holati eski testda)",
      mr.get("fully_ready") is True and mr.get("holat") == "tayyor", mr)

# ══════════════════════════════════════════════════════════════
section("C. Yordamchilar to'g'ridan (crud.mrp_tayyor_yetadimi, crud.mrp_topshirish_holati)")
# ══════════════════════════════════════════════════════════════
_yet = getattr(crud, "mrp_tayyor_yetadimi", None)


def yet(a, b):
    if _yet is None:
        return "YO'Q"
    try:
        return _yet(a, b)
    except Exception as e:                 # noqa: BLE001
        return f"{type(e).__name__}: {e}"


check("C1 yetadimi(5, 0) False; (5, 5) True; (5, 6) True", yet(5, 0) is False and yet(5, 5) is True and yet(5, 6) is True,
      [yet(5, 0), yet(5, 5), yet(5, 6)])
check("C2 chegara (yuk xati bilan bir xil 0.001): (5, 4.9995) True; (5, 4.998) False",
      yet(5, 4.9995) is True and yet(5, 4.998) is False, [yet(5, 4.9995), yet(5, 4.998)])
check("C3 qolgan ~0: (0, 0) True; (0.0005, 0) True", yet(0, 0) is True and yet(0.0005, 0) is True,
      [yet(0, 0), yet(0.0005, 0)])
_hol = getattr(crud, "mrp_topshirish_holati", None)


def hol(iid):
    if _hol is None:
        return None
    s = SessionLocal()
    try:
        return _hol(s, s.get(OrderItem, iid))
    except Exception as e:                 # noqa: BLE001
        return {"XATO": f"{type(e).__name__}: {e}"}
    finally:
        s.close()


_h = hol(ie)
check("C4 A6 detali: qolgan 5, tayyor 3, jarayonda 1, yetadi False",
      isinstance(_h, dict) and taxminan(_h.get("qolgan"), 5) and taxminan(_h.get("tayyor"), 3)
      and taxminan(_h.get("jarayonda"), 1) and _h.get("yetadi") is False, _h)
_h = hol(ih)
check("C5 ombordan olingan detal: qolgan 0, yetadi True", isinstance(_h, dict) and taxminan(_h.get("qolgan"), 0)
      and _h.get("yetadi") is True, _h)
_h = hol(ifx)
check("C6 A7 X (tayyor 4): yetadi True, jarayonda 0", isinstance(_h, dict) and _h.get("yetadi") is True
      and taxminan(_h.get("tayyor"), 4) and taxminan(_h.get("jarayonda"), 0), _h)
check("C7 son turi float (JSON da 0.0, 0 emas)", isinstance(_h, dict) and isinstance(_h.get("tayyor"), float)
      and isinstance(_h.get("jarayonda"), float), _h)

# ══════════════════════════════════════════════════════════════
section("G. Boshqa korxonaning TM i (Core insert — ORM qo'riqchisi rad etadi) tayyor deb SANALMAYDI")
# ══════════════════════════════════════════════════════════════
ogk, igk = buyurtma(5)
_gx = None
try:
    with engine.begin() as _cn:
        from production_models import Company
        _crow = dict(_cn.execute(select(Company.__table__).where(Company.__table__.c.id == 1)).mappings().first())
        _c2 = _cn.execute(select(Company.__table__.c.id).where(Company.__table__.c.id == 2)).scalar()
        if not _c2:
            _crow["id"] = 2
            _crow["name"] = "MT B korxona"
            if "code" in _crow:
                _crow["code"] = "MTB"
            _cn.execute(Company.__table__.insert().values(**_crow))
        _frow = dict(_cn.execute(select(FinishedProduct.__table__).where(
            FinishedProduct.__table__.c.id == FW)).mappings().first())
        _frow.pop("id", None)
        _frow.update({"company_id": 2, "quantity": 5, "reserved_quantity": 5, "reserved_for_order_item_id": igk})
        _cn.execute(FinishedProduct.__table__.insert().values(**_frow))
except Exception as _e:                    # noqa: BLE001
    _gx = f"{type(_e).__name__}: {str(_e)[:300]}"
mr = tayyorlik_to_liq(ogk)
q = qator(mr, igk)
MR["G1"] = mr
check("G0 fikstura: B korxonasining TM i A detaliga band (5) — Core insert", _gx is None and taxminan(band_jami(igk), 5),
      [_gx, band_jami(igk)])
check("G1 belgi TAYYOR EMAS (B ning TM i A ga tayyor sanalmaydi), tayyor 0",
      mr.get("fully_ready") is False and q.get("is_ready") is False and taxminan(q.get("tayyor_quantity"), 0), mr)
check("G2 holat 'kutilmoqda' — jarayonda ham 0 (ishlab_chiqarilmoqda EMAS)",
      mr.get("holat") == "kutilmoqda" and taxminan(q.get("ishlab_chiqarilmoqda"), 0), mr)
_st, _m = tayyor_bos(ogk)
check("G3 «Tayyor» 400 'kerak 5, tayyor 0' — IZCHIL", _st == 400 and "kerak 5, tayyor 0" in _m and izchil(mr, _st),
      [_st, _m])

# ══════════════════════════════════════════════════════════════
section("U. UI: mrpTayyorlikBelgisi (HAQIQIY orders.html funksiyasi, HAQIQIY API javoblari bilan, node)")
# ══════════════════════════════════════════════════════════════


def js_funksiya(matn, nom_):
    """Yuqori darajadagi `function nom_(` matni — birinchi qator boshidagi `}` gacha (regex literal /
    satr ichidagi qavslarga qaramaydi — kech31 saboqi); topilmasa ''."""
    i = matn.find("function " + nom_ + "(")
    if i < 0:
        return ""
    k = matn.find("\n}", i)
    return matn[i:k + 2] if k >= 0 else ""


_ord = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_base = open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8").read()
_f_esc = js_funksiya(_base, "escapeHtml")
_f_son = js_funksiya(_ord, "mrpSon")
_f_bel = js_funksiya(_ord, "mrpTayyorlikBelgisi")
ESKI_MR = {"applicable": True, "fully_ready": False,
           "items": [{"order_item_id": 1, "item_name": "<b>\"X'&", "needed_quantity": 5, "reserved_quantity": 5,
                      "delivered_quantity": 0, "remaining_quantity": 0, "tayyor_quantity": 0,
                      "ishlab_chiqarilmoqda": 5, "is_ready": False}], "holat": "ishlab_chiqarilmoqda"}
_kirish = dict(MR)
_kirish["YOMON_NOM"] = ESKI_MR
_kirish["YOMON_NOM2"] = dict(ESKI_MR, holat="kutilmoqda",
                             items=[dict(ESKI_MR["items"][0], remaining_quantity=2, ishlab_chiqarilmoqda=0)])
_kirish["QOLLANMAYDI"] = {"applicable": False}
_kirish["NULL"] = None
_skript = (_f_esc + "\n" + _f_son + "\n" + _f_bel + "\n"
           + "const K = " + json.dumps(_kirish, ensure_ascii=False) + ";\n"
           + "const R = {};\nfor (const k of Object.keys(K)) { try { R[k] = mrpTayyorlikBelgisi(K[k]); }"
           + " catch (e) { R[k] = 'XATO: ' + e; } }\nprocess.stdout.write(JSON.stringify(R));\n")
UI = {}
if _f_esc and _f_bel:
    _p = os.path.join(tempfile.gettempdir(), "mt_belgi.js")
    open(_p, "w", encoding="utf-8").write(_skript)
    try:
        _o = subprocess.run(["node", _p], capture_output=True, text=True, timeout=60)
        UI = json.loads(_o.stdout or "{}")
    except Exception as _e:                # noqa: BLE001
        UI = {"XATO": f"{type(_e).__name__}: {_e}"}
check("U0 funksiya shablonda bor va node da ishladi", bool(_f_bel) and isinstance(UI, dict) and "A1" in UI,
      [len(_f_bel), str(UI)[:200]])


def ui(k):
    return str(UI.get(k, ""))


def title(h):
    m = re.search(r'title="([^"]*)"', h)
    return m.group(1) if m else ""


check("U1 A1 (jarayonda) -> '🏭 MRP: ishlab chiqarilmoqda', '✅' YO'Q",
      "🏭 MRP: ishlab chiqarilmoqda" in ui("A1") and "✅" not in ui("A1"), ui("A1"))
check("U2 A1 izohi: 'ishlab chiqarilmoqda 5', 'tayyor 0', 'avval ishlab chiqarishni yakunlang'",
      "ishlab chiqarilmoqda 5" in title(ui("A1")) and "tayyor 0" in title(ui("A1"))
      and "avval ishlab chiqarishni yakunlang" in title(ui("A1")), title(ui("A1")))
check("U3 A2 (yakunlangan) -> '✅ MRP: tayyor'", "✅ MRP: tayyor" in ui("A2") and "🏭" not in ui("A2"), ui("A2"))
check("U4 A3 izohi: 'tayyor 3', 'ishlab chiqarilmoqda 2'",
      "🏭 MRP: ishlab chiqarilmoqda" in ui("A3") and "tayyor 3" in title(ui("A3"))
      and "ishlab chiqarilmoqda 2" in title(ui("A3")), ui("A3"))
check("U5 A4 (draft) -> '⏳ MRP: kutilmoqda', izohda 'yana 4'",
      "⏳ MRP: kutilmoqda" in ui("A4") and "yana 4" in title(ui("A4")), ui("A4"))
check("U6 A6 -> kutilmoqda, izohda 'yana 1' VA 'ishlab chiqarilmoqda 1'",
      "⏳ MRP: kutilmoqda" in ui("A6") and "yana 1" in title(ui("A6"))
      and "ishlab chiqarilmoqda 1" in title(ui("A6")), ui("A6"))
check("U7 A7 (ikki detal) -> ishlab chiqarilmoqda; izohda faqat tayyor bo'lmagan detal",
      "🏭 MRP: ishlab chiqarilmoqda" in ui("A7") and "ishlab chiqarilmoqda 6" in title(ui("A7"))
      and title(ui("A7")).count(": ") == 1, ui("A7"))
check("U8 A8 -> kutilmoqda", "⏳ MRP: kutilmoqda" in ui("A8") and "🏭" not in ui("A8"), ui("A8"))
check("U9 B1 (qisman topshirilgan, qolgani jarayonda) -> ishlab chiqarilmoqda", "🏭" in ui("B1"), ui("B1"))
check("U10 G1 (begona TM) -> kutilmoqda", "⏳ MRP: kutilmoqda" in ui("G1"), ui("G1"))
_yh = ui("YOMON_NOM")
check("U11 detal nomi izohda ESCAPE (bir marta): &lt;b&gt;&quot;X&#39;&amp; — xom '<b>' / qo'sh escape YO'Q",
      "&lt;b&gt;&quot;X&#39;&amp;" in _yh and "<b>" not in _yh and "&amp;lt;" not in _yh, _yh)
_yh2 = ui("YOMON_NOM2")
check("U11b 'kutilmoqda' izohida ham ESCAPE (bir marta), 'yana 2'",
      "⏳ MRP: kutilmoqda" in _yh2 and "&lt;b&gt;&quot;X&#39;&amp;" in _yh2 and "<b>" not in _yh2
      and "&amp;lt;" not in _yh2 and "yana 2" in _yh2, _yh2)
check("U12 applicable false / null -> bo'sh", ui("QOLLANMAYDI") == "" and ui("NULL") == "",
      [ui("QOLLANMAYDI"), ui("NULL")])
_son = ""
if _f_son:
    try:
        _son = subprocess.run(["node", "-e", _f_son + "\nprocess.stdout.write(mrpSon(0.1 + 0.2) + '|' + mrpSon(2) + '|' + mrpSon(null))"],
                              capture_output=True, text=True, timeout=30).stdout
    except Exception as _e:                # noqa: BLE001
        _son = f"{type(_e).__name__}: {_e}"
check("U13 son yaxlitlash: mrpSon(0.1+0.2) = '0.3', mrpSon(2) = '2', mrpSon(null) = '0'", _son == "0.3|2|0", _son)

# ══════════════════════════════════════════════════════════════
section("H. Statik tartib (yagona shart, eski langarlar saqlangan)")
# ══════════════════════════════════════════════════════════════
_hs = manba(crud, "mrp_topshirish_holati")
check("H1 yordamchi: MRP-yetkazish tekshiruvi -> remaining_qty -> _mrp_tayyor_qoldiq -> _fp_tayyormi -> yetadimi",
      tartibda(_hs, "if not _mrp_yetkazish_detalimi(order_item):", "float(order_item.remaining_qty or 0)",
               "_mrp_tayyor_qoldiq(db, order_item, company_id, lock)", "if not _fp_tayyormi(fp)",
               '"yetadi": mrp_tayyor_yetadimi(qolgan, tayyor)'), _hs[:200])
_ys = manba(crud, "mrp_tayyor_yetadimi")
check("H2 shart: qolgan > 0.001 VA qolgan > tayyor + 0.001 (yuk xati chegarasi bilan bir xil)",
      "return not (qolgan > 0.001 and qolgan > tayyor + 0.001)" in _ys, _ys[-200:])
_co = manba(services, "complete_order")
check("H3 «Tayyor»: _mrp_tayyor_qoldiq (eski langar) -> mrp_tayyor_yetadimi -> _mrp_kam; eski ifoda YO'Q",
      tartibda(_co, "if not order.deliveries:", "_mrp_tayyor_qoldiq(db, _it, order.company_id, lock=False)",
               "if not _crud_qulf.mrp_tayyor_yetadimi(_kerak, _tayyor):", "_mrp_kam.append(", "if _mrp_kam:")
      and "if _kerak > _tayyor + 0.001:" not in _co, _co[:200])
_tr = manba(production_service, "get_order_mrp_readiness")
check("H4 belgi: mrp_detal_kerak -> mrp_topshirish_holati -> is_ready = kerak<=0 VA yetadi -> holat",
      tartibda(_tr, "k = mrp_detal_kerak(db, item)", "_th = crud.mrp_topshirish_holati(db, item)",
               '"is_ready": remaining <= 0.0001 and _th["yetadi"]', '"holat": holat'), _tr[-300:])
_lo = js_funksiya(_ord, "loadOrderItems")
check("H5 UI: loadOrderItems belgini /api/orders javobidan (order.mrp_readiness) chizadi; eski if/else YO'Q",
      tartibda(_lo, "fetch(`/api/orders/${id}`)", "const order = await res.json();",
               "mrpEl.innerHTML = mrpTayyorlikBelgisi(order.mrp_readiness);")
      and "ombordan band qilingan" not in _ord, _lo[:200])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
