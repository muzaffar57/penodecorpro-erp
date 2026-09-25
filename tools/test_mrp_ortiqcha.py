#!/usr/bin/env python3
"""
test_mrp_ortiqcha.py — kech73 darvozasi (2026-09-25, 86-band / K72-1): MRP detalidan ORTIQCHA qaytarish.

NIMA UCHUN (asl kod `7e99f72` (zip 69) da O'LCHANGAN — `work/probe73.py`, SQLite = HAQIQIY PG)
-----------------------------------------------------------------------------------------------
MRP detali (ishlab chiqarish buyurtmasi SHU detalga band qilgan tayyor mahsulot — TM) dan brakdan boshqa
qaytarishning mijozga TOPSHIRILMAGAN (ortiqcha) qismi omborga qo'yilganda `add_returned_to_stock` band TM ga
tegmay YANGI TM yaratardi:
  * hech narsa ishlab chiqarilmagan detal 10 -> "Ortiqcha" 3 -> omborda 3 m² (tan narx 0) "havodan";
  * PO 10 tayyor (band 10) -> "Ortiqcha" 3 -> omborda 13 m² / 39 000 (to'g'risi 10 / 30 000); qolgan 7
    topshirilgach band TM 3 / 3 topshirilgan detalga yopishib qoladi (+ erkin 3);
  * aralash (yuk 5, qaytarish 7) -> 12 m² (to'g'risi 10); PO jarayonda -> ishlab chiqarilmagan 3 m² omborda;
  * buyurtma o'chirilganda band ozod bo'ladi -> ortiqcha IKKI marta (13 m²).

YECHIM (texnik — Claude): `crud._mrp_ortiqcha_reja` — ortiqcha qism SHU detalga band TAYYOR TM bandidan erkin
qoldiqqa o'tadi (eng yangi TM dan; `ReturnItem.mrp_ozod` ga yoziladi); tayyor ortiqcha (tayyor band − mijozga
topshirilishi kerak qoladigan) yetmasa — 400, hech narsa yozilmaydi. Qaytarish o'chirilsa band AYNAN shu TM larga
qaytadi (bo'sh qoldiq yetmasa — 400; band ozod qilingan bo'lsa mahsulot erkin qoladi).

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_mrp_ortiqcha.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_ortiqcha.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_ortiqcha_test"
_DB = os.path.join(tempfile.gettempdir(), "mrp_ortiqcha_test.db")

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
    import crud                                    # noqa: E402
    import database                                # noqa: E402

from sqlalchemy import text                        # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, FinishedProduct, OrderItem, ReturnItem,
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
    auth.create_user(_db, "MO_admin", "Parol123!", UserRole.ADMIN, "MO Admin", company_id=1)
PRJ = Project(company_id=1, client_name="MO Mijoz", project_name="MO loyiha", total_budget=0, total_paid=0)
TOSH = Inventory(company_id=1, item_name="MO Tosh", unit="kg", stock_quantity=1_000_000, price_per_unit=1_000,
                 category="Kimyo")
_db.add_all([PRJ, TOSH])
_db.commit()
ID = {"PRJ": PRJ.id, "TOSH": TOSH.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "MO_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "MO Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Arzon", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 3}]})) or {}).get("id")
BOM2 = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Qimmat", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 5}]})) or {}).get("id")
print("PT", PT, "BOM", BOM, "BOM2", BOM2)

_n = [0]


def nom():
    _n[0] += 1
    return f"MO_D{_n[0]}"


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


def po_draft(oid, iid, miqdor, manba_turi="customer_order", bom=None):
    tana = {"product_type_id": PT, "bom_id": bom or BOM, "quantity": miqdor, "source_type": manba_turi}
    if manba_turi == "customer_order":
        tana.update({"source_order_id": oid, "source_order_item_id": iid})
    r = req(C, "post", "/api/production/orders", json=tana)
    return (js(r) or {}).get("production_order", {}).get("id") if isinstance(js(r), dict) else None


def po_yarat(oid, iid, miqdor, manba_turi="customer_order", bom=None, yakunla=True):
    """Yaratib, boshlab, (yakunla=True bo'lsa) yakunlaydi -> po id (xato -> None)."""
    po = po_draft(oid, iid, miqdor, manba_turi, bom)
    if not po:
        print("   PO yaratilmadi")
        return None
    for q in (("start", "complete") if yakunla else ("start",)):
        r1 = req(C, "post", f"/api/production/orders/{po}/{q}")
        if r1.status_code != 200:
            print(f"   PO {q}:", r1.status_code, (r1.text or "")[:300])
            return None
    return po


def yuk(oid, iid, miqdor):
    r = req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom(),
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    return r.status_code


def qaytar(oid, iid, miqdor, sabab="Ortiqcha", to_stock=True):
    """POST /api/returns -> (status, id, xabar)."""
    r = req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": iid, "item_name": "x",
                                             "quantity": miqdor, "unit": "m²", "reason": sabab,
                                             "refund_amount": 0, "to_stock": to_stock})
    d = js(r) or {}
    return r.status_code, d.get("id"), str(d.get("detail") or d.get("message") or "")


def qaytar_ochir(rid):
    r = req(C, "delete", f"/api/returns/{rid}")
    d = js(r) or {}
    return r.status_code, str(d.get("detail") or d.get("message") or "")


def tmlar(iid):
    """Shu detalga BOG'LANGAN TM lar (id tartibida): [(id, qoldiq, band, tan narx), ...]."""
    s = SessionLocal()
    try:
        return [(f.id, round(float(f.quantity or 0), 6), round(float(f.reserved_quantity or 0), 6),
                 round(float(f.cost_price or 0), 2))
                for f in s.query(FinishedProduct).filter(FinishedProduct.reserved_for_order_item_id == iid)
                .order_by(FinishedProduct.id).all()]
    finally:
        s.close()


def tm(fid):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid)
        if f is None:
            return None
        return (round(float(f.quantity or 0), 6), round(float(f.reserved_quantity or 0), 6),
                round(float(f.cost_price or 0), 2), f.reserved_for_order_item_id)
    finally:
        s.close()


def jami_tm(dan_keyin):
    """id > dan_keyin bo'lgan HAMMA TM (yangi / qaytgan ham) -> (soni, qoldiq, tan narx)."""
    s = SessionLocal()
    try:
        L = s.query(FinishedProduct).filter(FinishedProduct.company_id == 1, FinishedProduct.id > dan_keyin).all()
        return (len([f for f in L if float(f.quantity or 0) > 1e-9]), round(sum(float(f.quantity or 0) for f in L), 6),
                round(sum(float(f.cost_price or 0) for f in L), 2))
    finally:
        s.close()


def max_tm():
    return int(sql("SELECT COALESCE(MAX(id), 0) FROM finished_products") or 0)


def qaytarish(rid):
    """ReturnItem -> dict (mrp_ozod — getattr: asl kodda ustun YO'Q, QULAMAYDI)."""
    s = SessionLocal()
    try:
        r = s.get(ReturnItem, rid) if rid else None
        if r is None:
            return None
        return {"ozod": getattr(r, "mrp_ozod", None), "stock_qty": r.stock_qty, "fp": r.finished_product_id,
                "ortiqcha": r.ortiqcha_miqdor}
    finally:
        s.close()


def qaytarishlar_soni(iid):
    return sql("SELECT COUNT(*) FROM return_items WHERE order_item_id = :i", i=iid)


def qolgan(iid):
    s = SessionLocal()
    try:
        return round(float(s.get(OrderItem, iid).remaining_qty or 0), 6)
    finally:
        s.close()


def kerak(iid):
    f = getattr(production_service, "mrp_detal_kerak", None)
    if f is None:
        return None
    s = SessionLocal()
    try:
        return f(s, s.get(OrderItem, iid)).get("kerak")
    except Exception as e:                 # noqa: BLE001
        return f"XATO {type(e).__name__}: {e}"
    finally:
        s.close()


def ozod_json(v):
    try:
        import json as _j
        return [[int(a), round(float(b), 6)] for a, b in _j.loads(v)]
    except Exception:                      # noqa: BLE001
        return None


# Umumiy omborga TM (band emas) — "ombordan olingan detal" fiksturasi uchun
po_yarat(None, None, 20, manba_turi="warehouse_stock")
FW = sql("SELECT MAX(id) FROM finished_products WHERE reserved_for_order_item_id IS NULL AND company_id = 1")

# ══════════════════════════════════════════════════════════════
section("A. Rad — ishlab chiqarilmagan ortiqcha omborga qo'yilmaydi (hech narsa yozilmaydi)")
# ══════════════════════════════════════════════════════════════
_m = max_tm()
o, i = buyurtma(10)
_st, _rid, _msg = qaytar(o, i, 3)
check("A1 hech narsa ishlab chiqarilmagan, Ortiqcha 3 -> 400", _st == 400, [_st, _msg[:200]])
check("A1b xabar: faqat ISHLAB CHIQARILGAN, tayyor ortiqcha 0, detal miqdorini kamaytirish",
      "ISHLAB CHIQARILGAN" in _msg and "tayyor ortiqcha 0" in _msg and "miqdorini kamaytiring" in _msg, _msg[:300])
check("A1c yozuv yo'q, yangi TM yo'q, qolgan 10", qaytarishlar_soni(i) == 0 and jami_tm(_m)[1] == 0
      and taxminan(qolgan(i), 10), [qaytarishlar_soni(i), jami_tm(_m), qolgan(i)])

o, i = buyurtma(10)
po_yarat(o, i, 10, yakunla=False)
_m = max_tm() - 1
_st, _rid, _msg = qaytar(o, i, 3)
check("A2 PO jarayonda (TM tayyor emas), Ortiqcha 3 -> 400", _st == 400, [_st, _msg[:200]])
check("A2b xabar: 10 hali ishlab chiqarilmoqda", "10 m² hali ishlab chiqarilmoqda" in _msg, _msg[:400])
check("A2c band 10 o'zgarmadi, TM bitta, yozuv yo'q", [t[1:3] for t in tmlar(i)] == [(10.0, 10.0)]
      and jami_tm(_m)[0] == 1 and qaytarishlar_soni(i) == 0, [tmlar(i), jami_tm(_m), qaytarishlar_soni(i)])

o, i = buyurtma(10)
po_yarat(o, i, 5)
_st, _rid, _msg = qaytar(o, i, 3)
check("A3 5 ishlab chiqarilgan (mijozga 7 kerak), Ortiqcha 3 -> 400 (tayyor ortiqcha 0)", _st == 400
      and "tayyor ortiqcha 0" in _msg and "band tayyor mahsulot 5" in _msg, [_st, _msg[:300]])
check("A3b band 5 o'zgarmadi, yozuv yo'q", [t[1:3] for t in tmlar(i)] == [(5.0, 5.0)] and qaytarishlar_soni(i) == 0,
      [tmlar(i), qaytarishlar_soni(i)])

o, i = buyurtma(10)
po_yarat(o, i, 8)
_st, _rid, _msg = qaytar(o, i, 2)
check("A4 chegara: 8 ishlab chiqarilgan, Ortiqcha 2 -> 400 (tayyor ortiqcha 0 — mijozga 8 kerak)", _st == 400,
      [_st, _msg[:200]])
_st, _rid, _msg = qaytar(o, i, 1.5)
check("A4b 8 ishlab chiqarilgan, Ortiqcha 1.5 -> 400 (8 − 8.5 < 0)", _st == 400, [_st, _msg[:200]])
po_yarat(o, i, 2)
_st, _rid, _msg = qaytar(o, i, 2.001)
check("A4c 10 ishlab chiqarilgan, Ortiqcha 2.001 -> 200 (tayyor ortiqcha 2.001)", _st == 200, [_st, _msg[:200]])
check("A4d band 10 -> 7.999, TM lar 2 ta, yangi TM yo'q", round(sum(t[2] for t in tmlar(i)), 6) == 7.999
      and len(tmlar(i)) == 2, tmlar(i))

# A5: band TM qoldig'i banddan KAM (masalan kamaytirilgan) — mavjud mahsulot = min(qoldiq, band)
o, i = buyurtma(10)
po_yarat(o, i, 10)
FK = tmlar(i)[0][0] if tmlar(i) else None
sql("UPDATE finished_products SET quantity = 8, cost_price = 24000 WHERE id = :f", f=FK)
_st, _rid, _msg = qaytar(o, i, 1)
check("A5 TM 8 / band 10 (2 kamaytirilgan), Ortiqcha 1 -> 400: tayyor band 8 < mijozga 9", _st == 400
      and "band tayyor mahsulot 8" in _msg, [_st, _msg[:300]])
check("A5b TM 8 / band 10 o'zgarmadi", tmlar(i) == [(FK, 8.0, 10.0, 24000.0)], tmlar(i))

# ══════════════════════════════════════════════════════════════
section("B. Ortiqcha — band TM dan erkin qoldiqqa (yangi TM yaratilmaydi)")
# ══════════════════════════════════════════════════════════════
o, i = buyurtma(10)
po_yarat(o, i, 10)
_m = max_tm() - 1
T = tmlar(i)
F1 = T[0][0] if T else None
_st, R1, _msg = qaytar(o, i, 3)
check("B1 PO 10 tayyor, Ortiqcha 3 -> 200", _st == 200, [_st, _msg[:200]])
check("B1b TM 10 / band 7 / 30 000 — o'sha bitta TM", tmlar(i) == [(F1, 10.0, 7.0, 30000.0)], tmlar(i))
check("B1c omborda jami 10 m² / 30 000 (yangi TM YO'Q)", jami_tm(_m) == (1, 10.0, 30000.0), jami_tm(_m))
_q = qaytarish(R1) or {}
check("B1d yozuvda mrp_ozod [[TM, 3]], stock_qty bo'sh, finished_product_id yo'q, ortiqcha 3",
      ozod_json(_q.get("ozod")) == [[F1, 3.0]] and not _q.get("stock_qty") and _q.get("fp") is None
      and taxminan(_q.get("ortiqcha"), 3), _q)
check("B1e qolgan 7, kerak 0 (band 7)", taxminan(qolgan(i), 7) and kerak(i) in (0, 0.0), [qolgan(i), kerak(i)])
check("B2 qolgan 7 topshirildi -> 200", yuk(o, i, 7) == 200)
check("B2b TM 3 / band 0 / 9 000 (erkin 3 saqlandi)", tmlar(i) == [(F1, 3.0, 0.0, 9000.0)], tmlar(i))
_st, _msg = qaytar_ochir(R1)
check("B3 qaytarish o'chirildi -> 200", _st == 200, [_st, _msg])
check("B3b band tiklandi: TM 3 / band 3; qolgan 3", tmlar(i) == [(F1, 3.0, 3.0, 9000.0)] and taxminan(qolgan(i), 3),
      [tmlar(i), qolgan(i)])

o, i = buyurtma(10)
po_yarat(o, i, 10)
F2 = tmlar(i)[0][0] if tmlar(i) else None
_st, R2, _ = qaytar(o, i, 4)
_st2, _ = qaytar_ochir(R2)
check("B4 Ortiqcha 4 -> o'chirish: TM 10 / band 10 / 30 000 AYNAN asliga", _st == 200 and _st2 == 200
      and tmlar(i) == [(F2, 10.0, 10.0, 30000.0)], [_st, _st2, tmlar(i)])

# B5: ikki TM (arzon 5 × 3 000, qimmat 5 × 5 000) — eng yangi TM dan bo'shatiladi, topshirish erkin qismni yemaydi
o, i = buyurtma(10)
po_yarat(o, i, 5)
po_yarat(o, i, 5, bom=BOM2)
_m = max_tm() - 2
T = tmlar(i)
FA, FB = (T[0][0], T[1][0]) if len(T) == 2 else (None, None)
_st, R5, _ = qaytar(o, i, 3)
check("B5 ikki TM, Ortiqcha 3 -> 200: ENG YANGI (qimmat) TM dan: A 5 / 5, B 5 / 2",
      _st == 200 and tmlar(i) == [(FA, 5.0, 5.0, 15000.0), (FB, 5.0, 2.0, 25000.0)], [_st, tmlar(i)])
check("B5b mrp_ozod [[B, 3]]", ozod_json((qaytarish(R5) or {}).get("ozod")) == [[FB, 3.0]], qaytarish(R5))
check("B5c qolgan 7 topshirildi -> A 0, B 3 / band 0 (erkin 3 SAQLANDI)", yuk(o, i, 7) == 200
      and tmlar(i) == [(FA, 0.0, 0.0, 0.0), (FB, 3.0, 0.0, 15000.0)], tmlar(i))
check("B5d omborda jami 3 m² / 15 000", jami_tm(_m)[1:] == (3.0, 15000.0), jami_tm(_m))

# B6: aralash — yuk 5, qaytarish 7 (5 mijozdan qaytgan + 2 ortiqcha)
o, i = buyurtma(10)
po_yarat(o, i, 10)
_m = max_tm() - 1
F6 = tmlar(i)[0][0] if tmlar(i) else None
yuk(o, i, 5)
_st, R6, _msg = qaytar(o, i, 7, "Mijoz iltimosi")
_q = qaytarish(R6) or {}
check("B6 aralash qaytarish 7 -> 200", _st == 200, [_st, _msg[:200]])
check("B6b band TM 5 / band 3 (2 erkin); mijozdan qaytgan 5 — yangi TM 5 / 15 000",
      tmlar(i) == [(F6, 5.0, 3.0, 15000.0)] and _q.get("fp") and tm(_q.get("fp")) is not None
      and tm(_q.get("fp"))[:3] == (5.0, 0.0, 15000.0), [tmlar(i), _q, tm(_q.get("fp")) if _q.get("fp") else None])
check("B6c yozuv: stock_qty 5, mrp_ozod [[TM, 2]], ortiqcha 2", taxminan(_q.get("stock_qty"), 5)
      and ozod_json(_q.get("ozod")) == [[F6, 2.0]] and taxminan(_q.get("ortiqcha"), 2), _q)
check("B6d omborda jami 10 m² / 30 000", jami_tm(_m)[1:] == (10.0, 30000.0), jami_tm(_m))
_st, _ = qaytar_ochir(R6)
check("B6e o'chirildi: band TM 5 / 5, qaytgan TM 0; jami 5 / 15 000", _st == 200
      and tmlar(i) == [(F6, 5.0, 5.0, 15000.0)] and jami_tm(_m)[1:] == (5.0, 15000.0), [_st, tmlar(i), jami_tm(_m)])

# B7: ketma-ket ikki ortiqcha
o, i = buyurtma(10)
po_yarat(o, i, 10)
_a = qaytar(o, i, 2)[0]
_b = qaytar(o, i, 2)[0]
_c = qaytar(o, i, 6.5)
check("B7 Ortiqcha 2 + 2 -> band 6; so'ng 6.5 -> 400 (jami qaytarish buyurtmadan oshadi yoki tayyor ortiqcha yetmaydi)",
      _a == 200 and _b == 200 and [t[1:3] for t in tmlar(i)] == [(10.0, 6.0)] and _c[0] == 400, [_a, _b, _c, tmlar(i)])

# ══════════════════════════════════════════════════════════════
section("C. O'chirish himoyasi / band ozod / buyurtma o'chirish")
# ══════════════════════════════════════════════════════════════
o, i = buyurtma(10)
po_yarat(o, i, 10)
FC = tmlar(i)[0][0] if tmlar(i) else None
_st, RC, _ = qaytar(o, i, 3)
# erkin 3 dan 2 si sotildi (simulyatsiya): qoldiq 8, band 7 -> bo'sh 1
sql("UPDATE finished_products SET quantity = quantity - 2, cost_price = cost_price - 6000 WHERE id = :f", f=FC)
_st2, _msg2 = qaytar_ochir(RC)
check("C1 erkin qism sotilgan (bo'sh 1 < 3) -> o'chirish 400, sabab aniq", _st == 200 and _st2 == 400
      and "bo'sh qoldig'i 1" in _msg2 and "sotilgan" in _msg2, [_st, _st2, _msg2[:300]])
check("C1b hech narsa o'zgarmadi: yozuv bor, TM 8 / band 7", qaytarish(RC) is not None
      and tmlar(i) == [(FC, 8.0, 7.0, 24000.0)], [qaytarish(RC), tmlar(i)])

o, i = buyurtma(10)
po_yarat(o, i, 10)
FD = tmlar(i)[0][0] if tmlar(i) else None
_st, RD, _ = qaytar(o, i, 3)
_rr = req(C, "post", f"/api/finished/{FD}/release-reservation")
_st2, _msg2 = qaytar_ochir(RD)
check("C2 band admin tomonidan ozod qilingan -> o'chirish 200, band QAYTA yopilmaydi (TM 10 / 0, bog'lamsiz)",
      _rr.status_code == 200 and _st2 == 200 and tm(FD) == (10.0, 0.0, 30000.0, None), [_rr.status_code, _st2, _msg2, tm(FD)])
check("C2b qolgan 10 (ortiqcha buyurtmaga qaytdi)", taxminan(qolgan(i), 10), qolgan(i))

o, i = buyurtma(10)
po_yarat(o, i, 10)
FE = tmlar(i)[0][0] if tmlar(i) else None
_m = max_tm() - 1
yuk(o, i, 2)
_st, RE, _ = qaytar(o, i, 3)
check("C3 yuk 2 + qaytarish 3 (2 qaytgan + 1 ortiqcha) -> jami 10 / 30 000", _st == 200
      and jami_tm(_m)[1:] == (10.0, 30000.0), [_st, jami_tm(_m)])
_rd = req(C, "delete", f"/api/orders/{o}")
check("C3b buyurtma o'chirildi (yumshoq) -> band ozod, jami 10 / 30 000 (ortiqcha IKKI MARTA emas)",
      _rd.status_code == 200 and jami_tm(_m)[1:] == (10.0, 30000.0), [_rd.status_code, jami_tm(_m)])
_st2, _msg2 = qaytar_ochir(RE)
check("C3c o'chirilgan buyurtmaning ortiqcha qaytarishi o'chirilmaydi -> 400", _st2 == 400, [_st2, _msg2[:200]])
_rt = req(C, "post", f"/api/orders/{o}/restore")
_st3, _msg3 = qaytar_ochir(RE)
check("C3d tiklangach o'chirish -> 200; jami 8 / 24 000 (ishlab chiqarilgan 10 − topshirilgan 2)",
      _rt.status_code == 200 and _st3 == 200 and jami_tm(_m)[1:] == (8.0, 24000.0), [_rt.status_code, _st3, _msg3, jami_tm(_m)])

o, i = buyurtma(10)
po_yarat(o, i, 10)
_m = max_tm() - 1
qaytar(o, i, 3)
_rd = req(C, "delete", f"/api/orders/{o}")
check("C4 yetkazishsiz buyurtma o'chirildi (qattiq) -> jami 10 / 30 000 (13 EMAS)",
      _rd.status_code == 200 and jami_tm(_m)[1:] == (10.0, 30000.0), [_rd.status_code, jami_tm(_m)])

# ══════════════════════════════════════════════════════════════
section("D / E. Nazorat — to_stock=false; ombordan olingan TM li detal (avvalgidek)")
# ══════════════════════════════════════════════════════════════
o, i = buyurtma(10)
po_yarat(o, i, 10)
_m = max_tm() - 1
_st, RD1, _ = qaytar(o, i, 3, to_stock=False)
check("D1 to_stock=false Ortiqcha 3 -> 200, band 10 o'zgarmaydi, yangi TM yo'q, mrp_ozod yo'q",
      _st == 200 and [t[1:3] for t in tmlar(i)] == [(10.0, 10.0)] and jami_tm(_m)[0] == 1
      and not (qaytarish(RD1) or {}).get("ozod"), [_st, tmlar(i), jami_tm(_m), qaytarish(RD1)])
o, i = buyurtma(10)
_st, RD2, _msg = qaytar(o, i, 3, to_stock=False)
check("D2 to_stock=false, hech narsa ishlab chiqarilmagan, Ortiqcha 3 -> 200 (omborga hech narsa qo'yilmaydi — rad YO'Q)",
      _st == 200 and taxminan(qolgan(i), 7) and tmlar(i) == [], [_st, _msg[:200], qolgan(i), tmlar(i)])

_m = max_tm()
o, i = buyurtma(5, {"finished_product_id": FW})
_st, RE1, _msg = qaytar(o, i, 2)
_q = qaytarish(RE1) or {}
check("E1 ombordan olingan TM li MRP detal, Ortiqcha 2 -> 200, avvalgidek qaytgan TM (stock_qty 2), mrp_ozod yo'q",
      _st == 200 and taxminan(_q.get("stock_qty"), 2) and _q.get("fp") and not _q.get("ozod"), [_st, _msg[:200], _q])

# ══════════════════════════════════════════════════════════════
section("G. Korxona chegarasi — yozilgan TM keyin boshqa korxonaga o'tgan")
# ══════════════════════════════════════════════════════════════
_s = SessionLocal()
try:
    from production_models import Company
    if _s.get(Company, 2) is None:
        _s.add(Company(id=2, name="MO Korxona B"))
        _s.commit()
finally:
    _s.close()
o, i = buyurtma(10)
po_yarat(o, i, 10)
FG = tmlar(i)[0][0] if tmlar(i) else None
_st, RG, _ = qaytar(o, i, 3)
sql("UPDATE finished_products SET company_id = 2 WHERE id = :f", f=FG)
_st2, _ = qaytar_ochir(RG)
check("G1 begona korxona TM iga tegilmaydi: o'chirish 200, TM band 7 da qoldi", _st == 200 and _st2 == 200
      and tm(FG) is not None and tm(FG)[:2] == (10.0, 7.0), [_st, _st2, tm(FG)])

# ══════════════════════════════════════════════════════════════
section("M. Ustun — ORM default YO'Q, sync_missing_columns qayta qo'shadi (eski qatorlar NULL)")
# ══════════════════════════════════════════════════════════════
_col = getattr(getattr(ReturnItem, "__table__", None), "c", {}).get("mrp_ozod") if hasattr(ReturnItem, "__table__") else None
check("M1 ReturnItem.mrp_ozod — Text, nullable, default YO'Q", _col is not None and _col.nullable
      and _col.default is None and _col.server_default is None, repr(_col))
_nn = sql("SELECT COUNT(*) FROM return_items WHERE mrp_ozod IS NOT NULL")
if not PG_URL:
    _d = sql("ALTER TABLE return_items DROP COLUMN mrp_ozod")
    try:
        with contextlib.redirect_stdout(_quiet):
            database.sync_missing_columns()
    except Exception as e:                 # noqa: BLE001
        _d = ("XATO", str(e))
    check("M2 SQLite: ustun o'chirilib sync qayta qo'shdi, hamma qator NULL",
          sql("SELECT COUNT(*) FROM return_items WHERE mrp_ozod IS NULL") == sql("SELECT COUNT(*) FROM return_items")
          and not isinstance(_nn, tuple) and _nn >= 1, [_d, _nn])

# ══════════════════════════════════════════════════════════════
section("H. Statik tartib")
# ══════════════════════════════════════════════════════════════
_cr = manba(crud, "create_return_item")
_rj = manba(crud, "_mrp_ortiqcha_reja")
_dl = manba(crud, "delete_return_item")
check("H1 create_return_item: reja YOZISHDAN OLDIN, _mrp_yetkazish_detalimi sharti bilan",
      tartibda(_cr, "_mrp_yetkazish_detalimi(order_item)", "_mrp_ortiqcha_reja(db, order_item, _ortiqcha_yangi",
               "item = ReturnItem("), _cr[:80])
check("H2 omborga faqat topshirilgan qism: add_returned_to_stock(_ombor_miqdor",
      tartibda(_cr, "_ombor_miqdor = max(0.0, float(data.quantity) - float(_ortiqcha_yangi))",
               "item.mrp_ozod = ", "if _ombor_miqdor > 1e-9:", "db, oi, _ombor_miqdor,"), "")
check("H3 reja: qulf bilan, faqat tayyor TM, teskari id",
      tartibda(_rj, "_mrp_band_tmlar(db, order_item, cid, lock=True)", "if _fp_tayyormi(fp)",
               "ReturnItem.company_id == cid", "for fp in reversed(tayyor):"), _rj[:80])
check("H4 delete: band TM lar RETURNED TM dan OLDIN qulflanadi (id tartibi), tekshiruv o'zgarishdan OLDIN",
      tartibda(_dl, "_mrp_tmlar_idlar(db, [r[0] for r in _ozod], _cid)", "fp = get_finished_product(db, item.finished_product_id",
               "_f_oz.reserved_quantity = float(_f_oz.reserved_quantity or 0) + _q_oz"), "")
check("H5 delete: band faqat SHU detalga bog'langan TM ga qaytadi",
      "_f_oz.reserved_for_order_item_id == item.order_item_id" in _dl, "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
