#!/usr/bin/env python3
"""
test_mrp_yuk_qaytish.py — kech70 / kech71 darvozasi (2026-09-25): MRP detali yuk xati — olish,
qaytarish va "ishlab chiqarilganidan ko'p berib bo'lmaydi".

NIMA UCHUN (asl kod `57e57ca` da SQLite + HAQIQIY PG 16 da O'LCHANGAN — `work/probe76.py`, `probe71r.py`)
------------------------------------------------------------------------------------------------------
  * 76-band: bitta detalga IKKI ishlab chiqarish buyurtmasi (TM A 5 x 3 000, B 5 x 5 000; jami 40 000).
    Yuk 8 (A 5 + B 3) o'chirilganda BUTUN 8 birinchi topilgan TM ga qaytardi: A 8 (ishlab chiqarilgani 5!),
    B 2, tan narx 34 000 (-6 000). PG da so'rovda ORDER BY yo'qligi sababli 36 000 ham chiqdi.
  * K70-1: faqat 5 ishlab chiqarilgan detalga yuk 8 -> 200 (3 hech qayerdan yechilmadi); yuk o'chirilganda
    TM 8 / 24 000 — 3 birlik va 9 000 so'm "havodan" paydo bo'ldi. Hech narsa ishlab chiqarilmagan detalga
    yuk 4 -> 200. FOYDALANUVCHI QARORI (kech70): "Taqiqlansin".
  * K71-1: qisman topshirilgan detal (yuk 3 / TM 5), qolgan band "ozod qilish" bilan ochildi, keyin yuk
    xati o'chirildi -> topshirilgan 3 m2 (9 000 so'm) HECH QAYERGA qaytmadi.

YECHIM (texnik — Claude): TM lar id TARTIBIDA (`FOR UPDATE` + `populate_existing`); faqat TAYYOR TM dan
olinadi; qaysi TM dan qancha olingani `DeliveryItem.mrp_olingan` ga yoziladi va o'chirishda AYNAN shu TM
larga (id bo'yicha — band ozod qilingan bo'lsa erkin qoldiqqa) qaytadi; eski yozuv (NULL) — teskari id
tartibida, ishlab chiqarilganidan oshmaydi; tayyordan ko'p yuk xati va "Tayyor" — 400.

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi (+ parallel prob P).
    python3 tools/test_mrp_yuk_qaytish.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_yuk_qaytish.py
"""
import os
import sys
import json
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_yuk_qaytish_test"
_DB = os.path.join(tempfile.gettempdir(), "mrp_yuk_qaytish_test.db")

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
    import crud, auth, services, database          # noqa: E402

from sqlalchemy import text, inspect as sa_inspect  # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, FinishedProduct, OrderItem, StockSource, ProductionStatus,
)
from production_models import Company              # noqa: E402
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
    """Bitta qiymat qaytaradigan xom SQL; xato (masalan eski kodda ustun yo'q) -> ('XATO', matn)."""
    try:
        with engine.connect() as c:
            r = c.execute(text(q), p)
            v = r.scalar() if r.returns_rows else None
            c.commit()
            return v
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {str(e)[:160]}")


def analyze():
    if PG_URL:
        sql("ANALYZE finished_products")


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "MY_admin", "Parol123!", UserRole.ADMIN, "MY Admin", company_id=1)
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="MY Korxona B"))
    _db.commit()
PRJ = Project(company_id=1, client_name="MY Mijoz", project_name="MY loyiha", total_budget=0, total_paid=0)
TOSH = Inventory(company_id=1, item_name="MY Tosh", unit="kg", stock_quantity=1_000_000, price_per_unit=1_000,
                 category="Kimyo")
_db.add_all([PRJ, TOSH])
_db.commit()
ID = {"PRJ": PRJ.id, "TOSH": TOSH.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "MY_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "MY Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
BOM_A = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Arzon", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 3}]})) or {}).get("id")
BOM_B = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Qimmat", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 5}]})) or {}).get("id")
print("PT", PT, "BOM_A", BOM_A, "BOM_B", BOM_B)

_n = [0]


def nom():
    _n[0] += 1
    return f"MY_D{_n[0]}"


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


def po_yarat(oid, iid, miqdor, bom, tugat=True, manba_turi="customer_order"):
    tana = {"product_type_id": PT, "bom_id": bom, "quantity": miqdor, "source_type": manba_turi}
    if manba_turi == "customer_order":
        tana.update({"source_order_id": oid, "source_order_item_id": iid})
    r = req(C, "post", "/api/production/orders", json=tana)
    po = ((js(r) or {}).get("production_order") or {}).get("id")
    if not po:
        print("   PO yaratilmadi:", r.status_code, (r.text or "")[:300])
        return None
    qadamlar = ("start", "complete") if tugat else ("start",)
    for q in qadamlar:
        r1 = req(C, "post", f"/api/production/orders/{po}/{q}")
        if r1.status_code != 200:
            print(f"   PO {q}:", r1.status_code, (r1.text or "")[:300])
            return None
    return po


def po_tugat(po):
    return req(C, "post", f"/api/production/orders/{po}/complete").status_code


def tmlar(iid):
    """Shu detalga bog'langan TM lar (id tartibida)."""
    s = SessionLocal()
    try:
        return [tm_dict(f) for f in s.query(FinishedProduct).filter(
            FinishedProduct.reserved_for_order_item_id == iid).order_by(FinishedProduct.id).all()]
    finally:
        s.close()


def tm_dict(f):
    return {"id": f.id, "q": round(float(f.quantity or 0), 6), "rez": round(float(f.reserved_quantity or 0), 6),
            "cost": round(float(f.cost_price or 0), 4), "link": f.reserved_for_order_item_id,
            "cid": f.company_id}


def tm(fid):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid)
        return tm_dict(f) if f else None
    finally:
        s.close()


def teng(t, q, rez, cost):
    return bool(t) and taxminan(t["q"], q, 1e-6) and taxminan(t["rez"], rez, 1e-6) and taxminan(t["cost"], cost)


def yuk(oid, iid, miqdor):
    r = req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom(),
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    d = js(r) or {}
    det = d.get("detail") if isinstance(d.get("detail"), dict) else {}
    return {"st": r.status_code, "did": d.get("delivery_id"),
            "msg": str(det.get("message") or d.get("message") or d.get("detail") or ""),
            "shortages": [str(x) for x in (det.get("shortages") or [])]}


def yuk_ochir(did):
    return req(C, "delete", f"/api/deliveries/{did}").status_code


def olingan(did):
    """delivery_items.mrp_olingan -> list (yoki None / ('XATO', ...))."""
    v = sql("SELECT mrp_olingan FROM delivery_items WHERE delivery_id = :d", d=did)
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:                  # noqa: BLE001
            return ("BUZUQ", v)
    return v


def yuklar_soni(oid):
    return sql("SELECT COUNT(*) FROM deliveries WHERE order_id = :o", o=oid)


def topshirilgan(iid):
    s = SessionLocal()
    try:
        oi = s.get(OrderItem, iid)
        return round(float(oi.delivered_qty or 0), 6) if oi else None
    finally:
        s.close()


def buyurtma_holati(oid):
    return str((js(req(C, "get", f"/api/orders/{oid}")) or {}).get("status") or "")


# ══════════════════════════════════════════════════════════════
section("A. Ikki TM (A 5 x 3 000, B 5 x 5 000) — yuk va o'chirish (76-band)")
# ══════════════════════════════════════════════════════════════
o1, i1 = buyurtma(10)
po_yarat(o1, i1, 5, BOM_A)
po_yarat(o1, i1, 5, BOM_B)
analyze()
_t = tmlar(i1)
check("A0 fikstura: detalga 2 TM — A 5 / 15 000, B 5 / 25 000",
      len(_t) == 2 and teng(_t[0], 5, 5, 15000) and teng(_t[1], 5, 5, 25000), _t)
FA, FB = (_t[0]["id"], _t[1]["id"]) if len(_t) == 2 else (None, None)
_y = yuk(o1, i1, 8)
analyze()
check("A1 yuk 8 -> 200", _y["st"] == 200 and _y["did"], _y)
check("A2 olish id tartibida: A 0 / 0 / 0, B 2 / 2 / 10 000",
      teng(tm(FA), 0, 0, 0) and teng(tm(FB), 2, 2, 10000), [tm(FA), tm(FB)])
check("A3 yuk qatorida mrp_olingan = [[A, 5], [B, 3]]",
      olingan(_y["did"]) == [[FA, 5], [FB, 3]], olingan(_y["did"]))
_st = yuk_ochir(_y["did"])
analyze()
check("A4 yuk o'chirildi -> 200", _st == 200, _st)
check("A5 har TM AYNAN asliga: A 5 / 5 / 15 000 (8 EMAS), B 5 / 5 / 25 000",
      teng(tm(FA), 5, 5, 15000) and teng(tm(FB), 5, 5, 25000), [tm(FA), tm(FB)])
check("A6 detal topshirilgan 0", taxminan(topshirilgan(i1), 0, 1e-9), topshirilgan(i1))

o2, i2 = buyurtma(10)
po_yarat(o2, i2, 5, BOM_A)
po_yarat(o2, i2, 5, BOM_B)
analyze()
_t = tmlar(i2)
GA, GB = (_t[0]["id"], _t[1]["id"]) if len(_t) == 2 else (None, None)
_y1 = yuk(o2, i2, 3)
analyze()
_y2 = yuk(o2, i2, 5)
analyze()
check("A7 yuk 3 va 5 -> 200 / 200; A 0, B 2", _y1["st"] == 200 and _y2["st"] == 200
      and teng(tm(GA), 0, 0, 0) and teng(tm(GB), 2, 2, 10000), [_y1, _y2, tm(GA), tm(GB)])
check("A8 mrp_olingan: 1-yuk [[A, 3]], 2-yuk [[A, 2], [B, 3]]",
      olingan(_y1["did"]) == [[GA, 3]] and olingan(_y2["did"]) == [[GA, 2], [GB, 3]],
      [olingan(_y1["did"]), olingan(_y2["did"])])
yuk_ochir(_y2["did"])
analyze()
check("A9 2-yuk o'chirildi -> A 2 / 2 / 6 000, B 5 / 5 / 25 000 (jami 31 000)",
      teng(tm(GA), 2, 2, 6000) and teng(tm(GB), 5, 5, 25000), [tm(GA), tm(GB)])
yuk_ochir(_y1["did"])
analyze()
check("A10 1-yuk ham o'chirildi -> A 5 / 15 000, B 5 / 25 000 (jami 40 000)",
      teng(tm(GA), 5, 5, 15000) and teng(tm(GB), 5, 5, 25000), [tm(GA), tm(GB)])
check("A11 detal topshirilgan 0, yuklar 0", taxminan(topshirilgan(i2), 0, 1e-9) and yuklar_soni(o2) == 0,
      [topshirilgan(i2), yuklar_soni(o2)])

# ══════════════════════════════════════════════════════════════
section("B. Ishlab chiqarilganidan KO'P yuk — 400 (K70-1, QAROR \"Taqiqlansin\")")
# ══════════════════════════════════════════════════════════════
o3, i3 = buyurtma(10)
po_yarat(o3, i3, 5, BOM_A)
analyze()
_t = tmlar(i3)
F3 = _t[0]["id"] if _t else None
_y = yuk(o3, i3, 8)
check("B1 tayyor 5, yuk 8 -> 400 \"Ishlab chiqarilganidan ko'p berib bo'lmaydi!\"",
      _y["st"] == 400 and _y["msg"] == "Ishlab chiqarilganidan ko'p berib bo'lmaydi!", _y)
check("B2 shortages matnida 'berilmoqchi' va 'tayyor (ishlab chiqarilgan) 5' — sabab va yechim",
      len(_y["shortages"]) == 1 and "8 m² berilmoqchi" in _y["shortages"][0]
      and "tayyor (ishlab chiqarilgan) 5 m²" in _y["shortages"][0]
      and "avval ishlab chiqarishni yakunlang" in _y["shortages"][0], _y["shortages"])
check("B3 hech narsa yozilmadi: yuk 0, TM 5 / 5 / 15 000, topshirilgan 0",
      yuklar_soni(o3) == 0 and teng(tm(F3), 5, 5, 15000) and taxminan(topshirilgan(i3), 0, 1e-9),
      [yuklar_soni(o3), tm(F3), topshirilgan(i3)])
_y = yuk(o3, i3, 5)
check("B4 chegara: yuk 5 (= tayyor) -> 200, TM 0 / 0 / 0, mrp_olingan [[TM, 5]]",
      _y["st"] == 200 and teng(tm(F3), 0, 0, 0) and olingan(_y["did"]) == [[F3, 5]], [_y, tm(F3)])
_y5 = yuk(o3, i3, 1)
check("B5 hammasi topshirilgach yana 1 -> 400 (tayyor 0), TM o'zgarmadi",
      _y5["st"] == 400 and _y5["shortages"] and "tayyor (ishlab chiqarilgan) 0" in _y5["shortages"][0]
      and teng(tm(F3), 0, 0, 0), [_y5, tm(F3)])
yuk_ochir(_y["did"])
check("B6 5 lik yuk o'chirildi -> TM 5 / 5 / 15 000", teng(tm(F3), 5, 5, 15000), tm(F3))

o4, i4 = buyurtma(10)
_y = yuk(o4, i4, 4)
check("B7 hech narsa ishlab chiqarilmagan, yuk 4 -> 400 (tayyor 0), yuk yozilmadi",
      _y["st"] == 400 and _y["shortages"] and "tayyor (ishlab chiqarilgan) 0" in _y["shortages"][0]
      and yuklar_soni(o4) == 0, [_y, yuklar_soni(o4)])

# ══════════════════════════════════════════════════════════════
section("C. Ishlab chiqarish BOSHLANGAN, tugamagan (TM jarayonda) -> 400; tugagach -> 200")
# ══════════════════════════════════════════════════════════════
o5, i5 = buyurtma(10)
PO5 = po_yarat(o5, i5, 5, BOM_A, tugat=False)
analyze()
_t = tmlar(i5)
F5 = _t[0]["id"] if _t else None
check("C0 fikstura: TM jarayonda (q 5, band 5)", _t and teng(_t[0], 5, 5, 0), _t)
_y = yuk(o5, i5, 3)
check("C1 jarayondagi TM dan yuk 3 -> 400 (tayyor 0), TM o'zgarmadi, yuk 0",
      _y["st"] == 400 and _y["shortages"] and "tayyor (ishlab chiqarilgan) 0" in _y["shortages"][0]
      and teng(tm(F5), 5, 5, 0) and yuklar_soni(o5) == 0, [_y, tm(F5), yuklar_soni(o5)])
_st = po_tugat(PO5) if PO5 else None
analyze()
_y = yuk(o5, i5, 3)
check("C2 ishlab chiqarish yakunlandi -> yuk 3 -> 200, TM 2 / 2 / 6 000",
      _st == 200 and _y["st"] == 200 and teng(tm(F5), 2, 2, 6000), [_st, _y, tm(F5)])

o5b, i5b = buyurtma(10)
po_yarat(o5b, i5b, 5, BOM_A, tugat=False)
po_yarat(o5b, i5b, 5, BOM_B)
analyze()
_t = tmlar(i5b)
J1, J2 = (_t[0]["id"], _t[1]["id"]) if len(_t) == 2 else (None, None)
_y = yuk(o5b, i5b, 3)
analyze()
check("C3 kichik id TM jarayonda, katta id tayyor: yuk 3 -> 200, faqat TAYYOR dan (B 2), jarayondagi 5 / 5 / 0",
      _y["st"] == 200 and teng(tm(J1), 5, 5, 0) and teng(tm(J2), 2, 2, 10000)
      and olingan(_y["did"]) == [[J2, 3]], [_y, tm(J1), tm(J2), olingan(_y["did"])])

# ══════════════════════════════════════════════════════════════
section("D. ESKI yozuv (mrp_olingan NULL) — teskari id, ishlab chiqarilganidan OSHMAYDI")
# ══════════════════════════════════════════════════════════════
o6, i6 = buyurtma(10)
po_yarat(o6, i6, 5, BOM_A)
po_yarat(o6, i6, 5, BOM_B)
analyze()
_t = tmlar(i6)
HA, HB = (_t[0]["id"], _t[1]["id"]) if len(_t) == 2 else (None, None)
_y = yuk(o6, i6, 8)
_nul = sql("UPDATE delivery_items SET mrp_olingan = NULL WHERE delivery_id = :d", d=_y["did"])
check("D0 fikstura: yuk 8 (A 5 + B 3) yozildi, mrp_olingan NULL qilindi (eski yozuv)",
      _y["st"] == 200 and _nul is None and olingan(_y["did"]) is None, [_y, _nul, olingan(_y["did"])])
yuk_ochir(_y["did"])
analyze()
check("D1 o'chirish: teskari id — B ga 3 (5 gacha), A ga 5 -> A 5 / 15 000, B 5 / 25 000",
      teng(tm(HA), 5, 5, 15000) and teng(tm(HB), 5, 5, 25000), [tm(HA), tm(HB)])

o7, i7 = buyurtma(10)
po_yarat(o7, i7, 5, BOM_A)
analyze()
_t = tmlar(i7)
F7 = _t[0]["id"] if _t else None
_y = yuk(o7, i7, 5)
_q8 = sql("UPDATE delivery_items SET quantity = 8 WHERE delivery_id = :d", d=_y["did"])
_nul = sql("UPDATE delivery_items SET mrp_olingan = NULL WHERE delivery_id = :d", d=_y["did"])
check("D2 fikstura: eski kod yozgan \"8 yuk / 5 ishlab chiqarilgan\" yozuvi (TM 0)",
      _y["st"] == 200 and _q8 is None and teng(tm(F7), 0, 0, 0) and taxminan(topshirilgan(i7), 8, 1e-9),
      [_y, _q8, _nul, tm(F7), topshirilgan(i7)])
_st = yuk_ochir(_y["did"])
check("D3 o'chirish -> 200, faqat 5 qaytdi: TM 5 / 5 / 15 000 (8 / 24 000 EMAS)",
      _st == 200 and teng(tm(F7), 5, 5, 15000), [_st, tm(F7)])
check("D4 detal topshirilgan 0", taxminan(topshirilgan(i7), 0, 1e-9), topshirilgan(i7))

o7b, i7b = buyurtma(10)
po_yarat(o7b, i7b, 5, BOM_A)
po_yarat(o7b, i7b, 5, BOM_B)
analyze()
_t = tmlar(i7b)
KA, KB = (_t[0]["id"], _t[1]["id"]) if len(_t) == 2 else (None, None)
_y1 = yuk(o7b, i7b, 3)
_y2 = yuk(o7b, i7b, 5)
for _dx in (_y1["did"], _y2["did"]):
    sql("UPDATE delivery_items SET mrp_olingan = NULL WHERE delivery_id = :d", d=_dx)
analyze()
yuk_ochir(_y2["did"])
analyze()
check("D5 ikki ESKI yuk (3: A; 5: A 2 + B 3), keyingisi o'chirildi -> teskari: B 5, A 2 (jami 31 000)",
      _y1["st"] == 200 and _y2["st"] == 200 and teng(tm(KA), 2, 2, 6000) and teng(tm(KB), 5, 5, 25000),
      [_y1, _y2, tm(KA), tm(KB)])
yuk_ochir(_y1["did"])
analyze()
check("D6 birinchisi ham o'chirildi -> A 5 / 15 000, B 5 / 25 000", teng(tm(KA), 5, 5, 15000) and teng(tm(KB), 5, 5, 25000),
      [tm(KA), tm(KB)])

# ══════════════════════════════════════════════════════════════
section("E. \"Tayyor\" (POST /api/orders/{id}/ready) — MRP kam bo'lsa rad, HECH NARSAGA tegmaydi")
# ══════════════════════════════════════════════════════════════
o8, i8 = buyurtma(10)
po_yarat(o8, i8, 5, BOM_A)
analyze()
_t = tmlar(i8)
F8 = _t[0]["id"] if _t else None
_h0 = buyurtma_holati(o8)
_r = req(C, "post", f"/api/orders/{o8}/ready")
_d = (js(_r) or {}).get("detail")
_m = str(_d.get("message") if isinstance(_d, dict) else _d)
check("E1 kerak 10, tayyor 5 -> 400 \"MRP mahsuloti hali to'liq ishlab chiqarilmagan\" + detal",
      _r.status_code == 400 and "MRP mahsuloti hali to'liq ishlab chiqarilmagan" in _m and "kerak 10, tayyor 5" in _m,
      [_r.status_code, _m])
check("E2 holat O'ZGARMADI, yuk 0, TM 5 / 5 / 15 000",
      buyurtma_holati(o8) == _h0 and _h0 not in ("ready", "delivered") and yuklar_soni(o8) == 0
      and teng(tm(F8), 5, 5, 15000), [_h0, buyurtma_holati(o8), yuklar_soni(o8), tm(F8)])
po_yarat(o8, i8, 5, BOM_B)
analyze()
_t = tmlar(i8)
F8B = _t[1]["id"] if len(_t) == 2 else None
_r = req(C, "post", f"/api/orders/{o8}/ready")
analyze()
_did = sql("SELECT MAX(id) FROM deliveries WHERE order_id = :o", o=o8)
check("E3 to'liq ishlab chiqarilgach \"Tayyor\" -> 200, avtomatik yuk 1, holat tayyor/yetkazilgan",
      _r.status_code == 200 and yuklar_soni(o8) == 1 and buyurtma_holati(o8) in ("ready", "delivered"),
      [_r.status_code, (_r.text or "")[:200], yuklar_soni(o8), buyurtma_holati(o8)])
check("E4 avtomatik yuk: mrp_olingan [[A, 5], [B, 5]], TM lar 0",
      olingan(_did) == [[F8, 5], [F8B, 5]] and teng(tm(F8), 0, 0, 0) and teng(tm(F8B), 0, 0, 0),
      [olingan(_did), tm(F8), tm(F8B)])

# ══════════════════════════════════════════════════════════════
section("F. Ombordan olingan TM li MRP detal (finished_product_id) — cheklov ta'sir QILMAYDI")
# ══════════════════════════════════════════════════════════════
POW = po_yarat(None, None, 6, BOM_A, manba_turi="warehouse_stock")
_s = SessionLocal()
try:
    _fw = _s.query(FinishedProduct).filter(FinishedProduct.reserved_for_order_item_id.is_(None),
                                           FinishedProduct.product_type_id == PT,
                                           FinishedProduct.company_id == 1).order_by(FinishedProduct.id.desc()).first()
    FW = _fw.id if _fw else None
finally:
    _s.close()
check("F0 fikstura: umumiy omborga TM 6 / 18 000 (band emas)", POW and teng(tm(FW), 6, 0, 18000), [POW, tm(FW)])
o9, i9 = buyurtma(3, {"finished_product_id": FW})
check("F1 buyurtma yaratilganda ombordan 3 olindi (TM 3)", o9 and FW and taxminan(tm(FW)["q"], 3, 1e-6),
      [o9, tm(FW)])
_y = yuk(o9, i9, 3)
check("F2 yuk 3 -> 200 (band TM yo'q, lekin cheklov bu detalga tegmaydi), TM 3 da qoldi",
      _y["st"] == 200 and taxminan(tm(FW)["q"], 3, 1e-6), [_y, tm(FW)])

# ══════════════════════════════════════════════════════════════
section("G. Boshqa korxonaning TM iga tegilmaydi")
# ══════════════════════════════════════════════════════════════
o10, i10 = buyurtma(10)
po_yarat(o10, i10, 5, BOM_A)
_s = SessionLocal()
try:
    _x = FinishedProduct(company_id=1, name="MY begona", category="dynamic_bom", quantity=4, produced_quantity=4,
                         unit="m²", unit_price=0, cost_price=4000, unit_cost_stable=1000,
                         source=StockSource.PRODUCED, production_status=ProductionStatus.READY,
                         reserved_quantity=4, reserved_for_order_item_id=i10, product_type_id=PT)
    _s.add(_x)
    _s.commit()
    FX = _x.id
finally:
    _s.close()
_bk = sql("UPDATE finished_products SET company_id = 2 WHERE id = :f", f=FX)
analyze()
check("G0 fikstura: detalga B korxona TM i (4 / 4 000) bog'langan", _bk is None and tm(FX)["cid"] == 2, [_bk, tm(FX)])
_t = [t for t in tmlar(i10) if t["cid"] == 1]
F10 = _t[0]["id"] if _t else None
_y = yuk(o10, i10, 6)
check("G1 yuk 6 -> 400 (tayyor faqat O'Z korxonasi: 5), begona TM 4 / 4 000 o'zgarmadi",
      _y["st"] == 400 and _y["shortages"] and "tayyor (ishlab chiqarilgan) 5" in _y["shortages"][0]
      and teng(tm(FX), 4, 4, 4000), [_y, tm(FX)])
_y = yuk(o10, i10, 5)
check("G2 yuk 5 -> 200, faqat o'z TM idan (0), begona 4 / 4 000; mrp_olingan faqat o'z TM",
      _y["st"] == 200 and teng(tm(F10), 0, 0, 0) and teng(tm(FX), 4, 4, 4000) and olingan(_y["did"]) == [[F10, 5]],
      [_y, tm(F10), tm(FX), olingan(_y["did"])])
yuk_ochir(_y["did"])
check("G3 o'chirish -> o'z TM 5 / 15 000, begona 4 / 4 000", teng(tm(F10), 5, 5, 15000) and teng(tm(FX), 4, 4, 4000),
      [tm(F10), tm(FX)])

o10b, i10b = buyurtma(10)
po_yarat(o10b, i10b, 5, BOM_A)
_t = tmlar(i10b)
F10b = _t[0]["id"] if _t else None
_y = yuk(o10b, i10b, 2)
_bk = sql("UPDATE finished_products SET company_id = 2 WHERE id = :f", f=F10b)
_st = yuk_ochir(_y["did"])
check("G4 yuk yozgan TM keyin BOSHQA korxonaga o'tgan (buzilgan yozuv): o'chirish 200, begona TM ga TEGILMADI (3)",
      _y["st"] == 200 and _bk is None and _st == 200 and taxminan(tm(F10b)["q"], 3, 1e-6)
      and tm(F10b)["cid"] == 2, [_y, _bk, _st, tm(F10b)])

# ══════════════════════════════════════════════════════════════
section("I. K71-1: band OZOD qilingach yuk xati o'chirilsa — mahsulot o'z TM iga qaytadi")
# ══════════════════════════════════════════════════════════════
o11, i11 = buyurtma(10)
po_yarat(o11, i11, 5, BOM_A)
_t = tmlar(i11)
F11 = _t[0]["id"] if _t else None
_y = yuk(o11, i11, 3)
_oz = req(C, "post", f"/api/finished/{F11}/release-reservation").status_code
check("I0 fikstura: yuk 3 (TM 2 / 2), qolgan band ozod qilindi (UI tugmasi — band > 0)",
      _y["st"] == 200 and _oz == 200 and teng(tm(F11), 2, 0, 6000) and tm(F11)["link"] is None,
      [_y, _oz, tm(F11)])
_st = yuk_ochir(_y["did"])
check("I1 yuk o'chirildi -> 200, TM 5 / 15 000 (3 m2 va 9 000 so'm QAYTDI)",
      _st == 200 and taxminan(tm(F11)["q"], 5, 1e-6) and taxminan(tm(F11)["cost"], 15000), [_st, tm(F11)])
check("I2 band ozod qilingan edi — qaytgan mahsulot ERKIN (band 0, bog'lam yo'q)",
      taxminan(tm(F11)["rez"], 0, 1e-9) and tm(F11)["link"] is None, tm(F11))

o12, i12 = buyurtma(10)
po_yarat(o12, i12, 5, BOM_A)
_t = tmlar(i12)
F12 = _t[0]["id"] if _t else None
_y = yuk(o12, i12, 5)
_oz = req(C, "post", f"/api/finished/{F12}/release-reservation").status_code
_st = yuk_ochir(_y["did"])
check("I3 to'liq yuk (5), bog'lam ozod (API), yuk o'chirildi -> TM 5 / 0 / 15 000",
      _y["st"] == 200 and _oz == 200 and _st == 200 and teng(tm(F12), 5, 0, 15000), [_y, _oz, _st, tm(F12)])

# ══════════════════════════════════════════════════════════════
section("P. Parallel yuk (faqat HAQIQIY PG): tayyor 5, bir vaqtda 4 va 3")
# ══════════════════════════════════════════════════════════════
if PG_URL:
    import threading
    from schemas import DeliveryCreate, DeliveryItemCreate
    o13, i13 = buyurtma(10)
    po_yarat(o13, i13, 5, BOM_A)
    analyze()
    _t = tmlar(i13)
    F13 = _t[0]["id"] if _t else None
    _bar = threading.Barrier(2)
    _nat = {}

    def _ish(n, miqdor):
        s = SessionLocal()
        try:
            _bar.wait(timeout=30)
            r = crud.create_delivery(s, DeliveryCreate(order_id=o13, items=[DeliveryItemCreate(
                order_item_id=i13, quantity=miqdor)], notes=f"MY parallel {n}"),
                delivered_by=f"MY{n}", company_id=1)
            s.commit()
            _nat[n] = bool((r or {}).get("success"))
        except Exception as e:             # noqa: BLE001
            s.rollback()
            _nat[n] = f"XATO {type(e).__name__}: {str(e)[:120]}"
        finally:
            s.close()

    _th = [threading.Thread(target=_ish, args=(1, 4.0)), threading.Thread(target=_ish, args=(2, 3.0))]
    for _x in _th:
        _x.start()
    for _x in _th:
        _x.join(60)
    _q = tm(F13)
    _top = topshirilgan(i13)
    check("P1 aynan bittasi o'tdi (ikkinchisi tayyordan ko'p — rad)",
          sorted(v is True for v in _nat.values()) == [False, True], _nat)
    check("P2 TM + topshirilgan = 5 (havodan mahsulot yo'q), TM 1 yoki 2",
          _q and taxminan(_q["q"] + (_top or 0), 5, 1e-6) and (taxminan(_q["q"], 1, 1e-6) or taxminan(_q["q"], 2, 1e-6)),
          [_nat, _q, _top])
else:
    print("  (SQLite — parallel prob o'tkazib yuborildi)")

# ══════════════════════════════════════════════════════════════
section("H. Statik tartib")
# ══════════════════════════════════════════════════════════════
_bt = manba(crud, "_mrp_band_tmlar")
check("H1 band TM lar id TARTIBIDA, FOR UPDATE + populate_existing, oldin flush",
      tartibda(_bt, "q = q.order_by(FinishedProduct.id)", "db.flush()",
               "q = q.with_for_update().populate_existing()"), _bt[:200])
_ds = manba(crud, "_mrp_deliver_stock")
check("H2 olishda faqat TAYYOR TM; olingan natija ga yoziladi",
      tartibda(_ds, "if sign > 0:", "if not _fp_tayyormi(fp):", "olindi.append([fp.id, round(olinadi, 6)])",
               'natija["olingan"] = olindi'), _ds[:200])
check("H3 qaytarish: yozilgan id bo'yicha (_mrp_tmlar_idlar), eski yozuvda teskari tartib va chegara",
      tartibda(_ds, "if olingan is not None:", "_mrp_tmlar_idlar(db,", "for fp in reversed(tmlar):",
               "float(fp.produced_quantity or 0) - float(fp.quantity or 0)"), _ds[:200])
check("H4 band faqat hali SHU detalga bog'langan TM ga qaytadi",
      "if fp.reserved_for_order_item_id == order_item.id:" in _ds)
_cd = manba(crud, "create_delivery")
check("H5 create_delivery: MRP tayyor tekshiruvi valid_items dan OLDIN, rad yozuvdan OLDIN, olingan yoziladi",
      tartibda(_cd, "if _mrp_yetkazish_detalimi(oi):", "_mrp_tayyor_qoldiq(db, oi, order.company_id)\n",
               "mrp_kam.append(", "valid_items.append((oi, di.quantity))", "if mrp_kam:",
               "db_delivery", "natija=_mn", "_di.mrp_olingan = _json.dumps(_mn[\"olingan\"])"), _cd[:200])
_ti = manba(crud, "_mrp_tmlar_idlar")
check("H9 yozilgan id bo'yicha qidirish ham KORXONA bilan cheklangan, id tartibida, qulf bilan",
      tartibda(_ti, "FinishedProduct.id.in_(idlar)", "q = q.filter(FinishedProduct.company_id == company_id)",
               "db.flush()", "q.order_by(FinishedProduct.id).with_for_update().populate_existing()"), _ti[:200])
_dd = manba(crud, "delete_delivery")
check("H6 delete_delivery: olingan=_mrp_olingan_oqi(di)", "olingan=_mrp_olingan_oqi(di))" in _dd)
_co = manba(services, "complete_order")
check("H7 \"Tayyor\": MRP tekshiruvi holat READY qilinishidan OLDIN",
      tartibda(_co, "if not order.deliveries:", "_mrp_tayyor_qoldiq(db, _it, order.company_id, lock=False)",
               "if _mrp_kam:", "order.status = OrderStatus.READY"), _co[:200])
_yd = manba(crud, "_mrp_yetkazish_detalimi")
check("H8 cheklov faqat MRP detaliga, ombordan olingan TM li detalga EMAS",
      "== 'mrp_product')" in _yd and "not getattr(order_item, 'finished_product_id', None)" in _yd, _yd[:200])

# ══════════════════════════════════════════════════════════════
section("M. Zaxira nusxa va migratsiya (eski bazaga ustun qo'shiladi)")
# ══════════════════════════════════════════════════════════════
# `/api/system/backup` — faqat platforma administratori (403); manba funksiyasi to'g'ridan.
_s = SessionLocal()
try:
    _b = crud.export_full_backup(_s, company_id=1)
except Exception as e:                     # noqa: BLE001
    _b = {"XATO": f"{type(e).__name__}: {e}"}
finally:
    _s.close()


def _jadval(x, nomi):
    if isinstance(x, dict):
        if nomi in x and isinstance(x[nomi], list):
            return x[nomi]
        for v in x.values():
            r = _jadval(v, nomi)
            if r is not None:
                return r
    return None


_di = _jadval(_b, "delivery_items") or []
check("M1 zaxira nusxada delivery_items qatorlarida mrp_olingan kaliti bor (yangisi to'ldirilgan)",
      _di and all("mrp_olingan" in r for r in _di) and any(r.get("mrp_olingan") for r in _di),
      [len(_di), (_di[:1] or [None])[0]])
_jami_q = sql("SELECT COUNT(*) FROM delivery_items")
_drop = sql("ALTER TABLE delivery_items DROP COLUMN mrp_olingan")
try:
    engine.dispose()
    with contextlib.redirect_stdout(_quiet):
        database.sync_missing_columns()
    engine.dispose()
    _cols = [c["name"] for c in sa_inspect(engine).get_columns("delivery_items")]
except Exception as e:                     # noqa: BLE001
    _cols = [f"XATO {e}"]
check("M2 ustun o'chirildi (eski baza) -> sync_missing_columns qayta QO'SHDI",
      _drop is None and "mrp_olingan" in _cols, [_drop, _cols])
check("M3 eski qatorlar NULL (standart qiymat yozilmadi), qatorlar yo'qolmadi",
      sql("SELECT COUNT(*) FROM delivery_items WHERE mrp_olingan IS NOT NULL") == 0
      and sql("SELECT COUNT(*) FROM delivery_items") == _jami_q and (_jami_q or 0) > 0,
      [_jami_q, sql("SELECT COUNT(*) FROM delivery_items WHERE mrp_olingan IS NOT NULL")])
o14, i14 = buyurtma(10)
po_yarat(o14, i14, 5, BOM_A)
_t = tmlar(i14)
F14 = _t[0]["id"] if _t else None
_y = yuk(o14, i14, 2)
check("M4 migratsiyadan keyin yangi yuk -> 200, mrp_olingan yozildi",
      _y["st"] == 200 and olingan(_y["did"]) == [[F14, 2]], [_y, olingan(_y["did"])])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
