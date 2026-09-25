#!/usr/bin/env python3
"""
test_tayyor_yuk.py — kech75 darvozasi (2026-09-25, 91 / 92 / 93 / 94-band): "Tayyor" (READY) va yuk xati.

NIMA UCHUN (asl kod `ea461bc` (zip 70) da O'LCHANGAN — `work/probe89.py`, `work/probe91.py`, SQLite = PG)
------------------------------------------------------------------------------------------------------
Oylik hisobot, usta KPI va boshqa moliya hisoblari FAQAT READY ("Tayyor") buyurtmani sanaydi. Holat esa
yuk xatlari bilan hodim bilmagan holda o'zgarardi:
  * to'liq YETKAZILGAN (DELIVERED) buyurtmaning yuki o'chirilsa — READY: hech kim "Tayyor" bosmagan buyurtma
    hisobotga kirardi (M1 / P2 / Q4);
  * "Tayyor" buyurtmaning yuk xati o'chirilsa — holat READY qolib, mahsulot / MRP bandi omborga qaytardi,
    daromad hisobotda qolardi (M2 / P1 / Q3); keyin buyurtma o'chirilsa xomashyo ham qaytardi;
  * "Tayyor" buyurtmaga keyin to'liq yuk yozilsa — DELIVERED bo'lib hisobotdan JIM chiqib ketardi (Q5 / Q7);
  * to'liq YETKAZILGAN buyurtma sahifada "✓ Tayyor" ko'rinar, "Tayyor" tugmasi yashirinardi — uni hisobotga
    kiritishning yo'li yo'q edi (jonli: 171 / 172);
  * o'chirish tasdig'i server shartidan farq qilardi (93 / 94-band).

FOYDALANUVCHI QARORLARI (kech74): 91-band "B" — to'liq topshirilgan buyurtma hisobotga / usta KPI ga FAQAT
hodim "Tayyor" bosganda; 92-band "B" — "Tayyor" buyurtmaning yuk xatini o'chirish TAQIQLANSIN.

BO'LIMLAR
  A  "Tayyor" DELIVERED dan (loy farqi bir marta, penoplast / TM qayta yechilmaydi, avto yuk yo'q,
     completed_at = bosilgan payt, hisobotga kiradi; MRP)
  B  READY yuk xatini o'chirish — 400, hech narsa o'zgarmaydi (to'lovli yuk: 409 dan OLDIN; MRP; qisman yakun;
     crud to'g'ridan)
  C  DELIVERED yuk xati o'chirilsa — in_progress (hisobotga kirmaydi); keyin "Tayyor" ishlaydi; MRP
  D  yuk xati READY ni pasaytirmaydi (hammasi "Ortiqcha" -> Tayyor -> qaytarish o'chirildi -> yuk; eski yuksiz
     READY; "Tayyor" avto yuki — pin olinadi)
  E  o'chirish rejasi (`GET /api/orders/{id}` "ochirish") == `DELETE /api/orders/{id}` amali — 7 holat
  F  UI (faqat SQLite; uvicorn + jsdom, HAQIQIY /orders): nishon va tugmalar, READY yukida o'chirish yo'q,
     `deleteDelivery` server sababi, `deleteSelected` tasdiq matni
  P  parallel (faqat PG): "Tayyor" || yuk xatini o'chirish (DELIVERED) — yuk o'chmaydi
  H  statik tartib

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi (F — faqat SQLite, P — faqat PG).
    python3 tools/test_tayyor_yuk.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tayyor_yuk.py
"""
import os
import sys
import json
import time
import socket
import inspect
import tempfile
import threading
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tayyor_yuk_test"
_T = tempfile.mkdtemp(prefix="tayyor_yuk_")
_DB = os.path.join(_T, "tayyor_yuk_test.db")

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
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime                      # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, FinishedProduct, OrderItem, Order, OrderStatus, Delivery, Payment,
    Recipe, RecipeIngredient, Master,
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


def xabar(r):
    d = js(r)
    if isinstance(d, dict):
        det = d.get("detail", d)
        if isinstance(det, dict):
            return str(det.get("message") or det)
        return str(det)
    return str(getattr(r, "text", ""))[:300]


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


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TY_admin", "Parol123!", UserRole.ADMIN, "TY Admin", company_id=1)
PRJ = Project(company_id=1, client_name="TY Mijoz", project_name="TY loyiha", total_budget=0, total_paid=0)
TOSH = Inventory(company_id=1, item_name="TY Tosh", unit="kg", stock_quantity=1_000_000, price_per_unit=1_000,
                 category="Kimyo")
PENO = Inventory(company_id=1, item_name="TY Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TY Kley", unit="kg", stock_quantity=10_000, price_per_unit=2_000,
                 category="Kimyo")
_db.add_all([PRJ, TOSH, PENO, KLEY])
_db.flush()
REC = Recipe(company_id=1, name="TY retsept", batch_size_kg=100.0)
_db.add(REC)
_db.flush()
_db.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
USTA = Master(company_id=1, name="TY Usta", phone="+998900007575")
_db.add(USTA)
_db.commit()
ID = {"PRJ": PRJ.id, "TOSH": TOSH.id, "PENO": PENO.id, "KLEY": KLEY.id, "REC": REC.id, "USTA": USTA.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "TY_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "TY Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Asosiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 3}]})) or {}).get("id")
print("PT", PT, "BOM", BOM)

_n = [0]


def nom(p="TY_D"):
    _n[0] += 1
    return f"{p}{_n[0]}"


def detal_idlar(oid):
    s = SessionLocal()
    try:
        return [x[0] for x in s.query(OrderItem.id).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        s.close()


def _yarat(tana):
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    if not oid:
        return None, None
    ids = detal_idlar(oid)
    return oid, (ids[0] if ids else None)


def peno_buyurtma(draft=False):
    """Oddiy profil 10 metr (penoplast 0.1 blok), 500 000 so'm."""
    tana = {"project_id": ID["PRJ"], "order_type": "product", "is_draft": draft,
            "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 10,
                       "quantity": 10, "unit_price": 50_000, "is_coated": False, "penoplast_id": ID["PENO"]}]}
    return _yarat(tana)


def qoplamali_buyurtma(loy=10.0):
    """Qoplamali profil 10 metr + retsept (loy 10 kg) + usta."""
    tana = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": loy, "recipe_id": ID["REC"],
            "master_id": ID["USTA"],
            "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 10,
                       "quantity": 10, "unit_price": 50_000, "is_coated": True, "penoplast_id": ID["PENO"],
                       "recipe_id": ID["REC"]}]}
    return _yarat(tana)


def mrp_buyurtma(soni=5):
    tana = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": 0,
            "items": [{"name": nom(), "category": "mrp_product", "quantity": soni, "unit_price": 100_000,
                       "is_coated": False, "penoplast_id": None, "product_type_id": PT}]}
    return _yarat(tana)


def ishlab(oid, iid, miqdor):
    r = req(C, "post", "/api/production/orders", json={
        "product_type_id": PT, "bom_id": BOM, "quantity": miqdor, "source_type": "customer_order",
        "source_order_id": oid, "source_order_item_id": iid})
    po = ((js(r) or {}).get("production_order") or {}).get("id") if isinstance(js(r), dict) else None
    if not po:
        return None
    for q in ("start", "complete"):
        if req(C, "post", f"/api/production/orders/{po}/{q}").status_code != 200:
            return None
    s = SessionLocal()
    try:
        tm = s.query(FinishedProduct.id).filter(FinishedProduct.reserved_for_order_item_id == iid) \
            .order_by(FinishedProduct.id.desc()).first()
        return tm[0] if tm else None
    finally:
        s.close()


def yuk(oid, iid, miqdor, tolov=None):
    tana = {"order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom("yuk"),
            "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"}
    if tolov:
        tana["payment_amount"] = tolov
    r = req(C, "post", "/api/deliveries", json=tana)
    d = js(r) or {}
    return r.status_code, (d.get("delivery_id") if isinstance(d, dict) else None)


def yuk_ochir(did, tolov=None):
    return req(C, "delete", f"/api/deliveries/{did}" + (f"?tolov={tolov}" if tolov else ""))


def tayyor(oid, loy=None):
    return req(C, "post", f"/api/orders/{oid}/ready", params=({"loy_kg": str(loy)} if loy is not None else None))


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if not o:
            return None
        yuklar = sorted(x[0] for x in s.query(Delivery.id).filter(Delivery.order_id == oid).all())
        tol = sorted((round(float(p.amount or 0), 2), p.delivery_id)
                     for p in s.query(Payment).filter(Payment.order_id == oid).all())
        return {"status": o.status.value if o.status else None, "yuklar": yuklar, "tolovlar": tol,
                "completed_at": o.completed_at, "pin": bool(o.is_pinned), "del": bool(o.is_deleted)}
    finally:
        s.close()


def hisobot():
    s = SessionLocal()
    try:
        n = datetime.utcnow()
        with contextlib.redirect_stdout(_quiet):
            r = services.get_monthly_report(s, n.year, n.month, company_id=1)
        return (int(r.get("buyurtmalar_soni") or 0), round(float(r.get("daromad_buyurtmalardan") or 0), 2),
                round(float(r.get("ishlab_chiqarish_xarajat") or 0), 2))
    finally:
        s.close()


def qoldiq(inv_id):
    s = SessionLocal()
    try:
        return round(float(s.get(Inventory, inv_id).stock_quantity or 0), 6)
    finally:
        s.close()


def tm_holat(fid):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid) if fid else None
        if not f:
            return None
        return (round(float(f.quantity or 0), 6), round(float(f.reserved_quantity or 0), 6),
                round(float(f.cost_price or 0), 2))
    finally:
        s.close()


def orm_yoz(oid, **kv):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        for k, v in kv.items():
            setattr(o, k, v)
        s.commit()
    finally:
        s.close()


def reja(oid):
    d = js(req(C, "get", f"/api/orders/{oid}")) or {}
    return d.get("ochirish") if isinstance(d, dict) else None


# ══════════════════════════════════════════════════════════════
section("A. \"Tayyor\" to'liq YETKAZILGAN (delivered) buyurtmadan — 91-band (b)")
# ══════════════════════════════════════════════════════════════
H0 = hisobot()
oa, ia = qoplamali_buyurtma(10.0)
check("A0 qoplamali buyurtma yaratildi", oa and ia, oa)
r = yuk(oa, ia, 10)
ha = holat(oa)
check("A1 to'liq yuk -> 200, holat delivered", r[0] == 200 and ha and ha["status"] == "delivered", (r, ha))
check("A1b delivered hisobotda YO'Q (hali \"Tayyor\" bosilmagan — QAROR B)", hisobot() == H0, (H0, hisobot()))
# yuk xati completed_at yozadi — \"Tayyor\" uni BOSILGAN payt bilan almashtirishi kerak (eski oyga suramiz)
orm_yoz(oa, completed_at=datetime(2026, 1, 15, 10, 0, 0))
p0, k0 = qoldiq(ID["PENO"]), qoldiq(ID["KLEY"])
t_bos = datetime.utcnow()
r = tayyor(oa, 12)
d = js(r) or {}
ha2 = holat(oa)
check("A2 \"Tayyor\" (loy 12, reja 10) -> 200", r.status_code == 200, (r.status_code, r.text[:200]))
check("A3 avtomatik yuk YO'Q, yuk xati o'sha (1 ta)", not d.get("auto_delivery") and ha2 and ha2["yuklar"] == ha["yuklar"],
      (d.get("auto_delivery"), ha2))
check("A4 holat ready", ha2 and ha2["status"] == "ready", ha2)
check("A5 completed_at = bosilgan payt (eski 15.01 o'rniga)",
      ha2 and ha2["completed_at"] and ha2["completed_at"] >= t_bos.replace(microsecond=0), ha2 and ha2["completed_at"])
check("A6 loy farqi BIR marta: kley -2 kg (reja 10 allaqachon yechilgan)", taxminan(qoldiq(ID["KLEY"]), k0 - 2),
      (k0, qoldiq(ID["KLEY"])))
check("A7 penoplast QAYTA yechilmadi", taxminan(qoldiq(ID["PENO"]), p0), (p0, qoldiq(ID["PENO"])))
check("A8 usta KPI hisoblandi (javobda)", ((d.get("master_kpi") or {}).get("total_kpi") or 0) > 0, d.get("master_kpi"))
h1 = hisobot()
check("A9 hisobotga KIRDI: +1 buyurtma, +500 000 daromad", h1[0] == H0[0] + 1 and taxminan(h1[1], H0[1] + 500_000, 0.01),
      (H0, h1))
r = tayyor(oa)
check("A10 ikkinchi \"Tayyor\" -> 400 (allaqachon), hech narsa o'zgarmadi",
      r.status_code == 400 and "allaqachon" in xabar(r) and hisobot() == h1 and holat(oa) == ha2, (r.status_code, xabar(r)))

om, im = mrp_buyurtma(5)
tm_a = ishlab(om, im, 5) if om else None
check("A11 MRP buyurtma + PO 5 tayyor", om and tm_a and tm_holat(tm_a) == (5.0, 5.0, 15000.0), tm_holat(tm_a))
r = yuk(om, im, 5)
check("A12 MRP to'liq yuk -> delivered, TM 0 / 0", r[0] == 200 and (holat(om) or {}).get("status") == "delivered"
      and tm_holat(tm_a) == (0.0, 0.0, 0.0), (r, holat(om), tm_holat(tm_a)))
hm0, ts0 = hisobot(), qoldiq(ID["TOSH"])
r = tayyor(om)
check("A13 MRP \"Tayyor\" delivered dan -> 200, avto yuk yo'q",
      r.status_code == 200 and not (js(r) or {}).get("auto_delivery") and len((holat(om) or {}).get("yuklar") or []) == 1,
      (r.status_code, r.text[:200]))
check("A14 MRP: TM ikkinchi marta yechilmadi, xomashyo tegilmadi",
      tm_holat(tm_a) == (0.0, 0.0, 0.0) and taxminan(qoldiq(ID["TOSH"]), ts0), (tm_holat(tm_a), ts0, qoldiq(ID["TOSH"])))
hm1 = hisobot()
check("A15 MRP hisobotga kirdi: +1, +500 000, tan +15 000",
      hm1[0] == hm0[0] + 1 and taxminan(hm1[1], hm0[1] + 500_000, 0.01) and taxminan(hm1[2], hm0[2] + 15_000, 0.01),
      (hm0, hm1))

# ══════════════════════════════════════════════════════════════
section("B. \"Tayyor\" buyurtmaning yuk xatini o'chirish TAQIQ — 92-band (QAROR B)")
# ══════════════════════════════════════════════════════════════
ob, ib = peno_buyurtma()
r = tayyor(ob)
did_b = ((js(r) or {}).get("auto_delivery") or {}).get("delivery_id") if isinstance(js(r), dict) else None
check("B0 \"Tayyor\" -> avtomatik yuk", r.status_code == 200 and did_b, (r.status_code, r.text[:200]))
hb, pb, repb = holat(ob), qoldiq(ID["PENO"]), hisobot()
r = yuk_ochir(did_b)
m = xabar(r)
check("B1 READY yuk xatini o'chirish -> 400", r.status_code == 400, (r.status_code, m))
check("B2 xabar aniq: \"Tayyor\", yuk raqami, o'chirib bo'lmaydi",
      "Tayyor" in m and "o'chirib bo'lmaydi" in m and "/Y-1" in m, m)
check("B3 hech narsa o'zgarmadi (yuk, holat, penoplast, hisobot)",
      holat(ob) == hb and taxminan(qoldiq(ID["PENO"]), pb) and hisobot() == repb, (hb, holat(ob), repb, hisobot()))

oc, ic = peno_buyurtma()
r = yuk(oc, ic, 10, tolov=100_000)
did_c = r[1]
check("B4 to'lovli to'liq yuk -> delivered", r[0] == 200 and (holat(oc) or {}).get("status") == "delivered", (r, holat(oc)))
check("B5 \"Tayyor\" -> 200 (avto yuk yo'q)", tayyor(oc).status_code == 200 and (holat(oc) or {}).get("status") == "ready",
      holat(oc))
hc = holat(oc)
for _tl in (None, "ochir", "qoldir"):
    r = yuk_ochir(did_c, _tl)
    check(f"B6 to'lovli READY yuk (?tolov={_tl}) -> 400 (409 EMAS — taqiq to'lovdan OLDIN), to'lov joyida",
          r.status_code == 400 and "o'chirib bo'lmaydi" in xabar(r) and holat(oc) == hc, (r.status_code, xabar(r), holat(oc)))

om2, im2 = mrp_buyurtma(5)
tm_b = ishlab(om2, im2, 5) if om2 else None
r = tayyor(om2)
did_m = ((js(r) or {}).get("auto_delivery") or {}).get("delivery_id") if isinstance(js(r), dict) else None
check("B7 MRP \"Tayyor\" -> avto yuk, TM 0", r.status_code == 200 and did_m and tm_holat(tm_b) == (0.0, 0.0, 0.0),
      (r.status_code, tm_holat(tm_b)))
hm2 = hisobot()
r = yuk_ochir(did_m)
check("B8 MRP READY yuk -> 400, TM bandi / qoldig'i QAYTMADI, hisobot o'zgarmadi",
      r.status_code == 400 and tm_holat(tm_b) == (0.0, 0.0, 0.0) and (holat(om2) or {}).get("yuklar") == [did_m]
      and hisobot() == hm2, (r.status_code, tm_holat(tm_b), holat(om2)))

oq, iq = peno_buyurtma()
r = yuk(oq, iq, 5)
did_q = r[1]
r2 = tayyor(oq)
check("B9 qisman (5 / 10) -> \"Tayyor\" (qisman yakun) -> ready", r[0] == 200 and r2.status_code == 200
      and (holat(oq) or {}).get("status") == "ready", (r, r2.status_code, holat(oq)))
hq = holat(oq)
r = yuk_ochir(did_q)
check("B10 qisman yakunlangan READY yuki -> 400, o'zgarmadi", r.status_code == 400 and holat(oq) == hq, (r.status_code, holat(oq)))

_s = SessionLocal()
_xat = None
try:
    crud.delete_delivery(_s, did_b, company_id=1)
except ValueError as e:
    _xat = str(e)
except Exception as e:                     # noqa: BLE001
    _xat = f"BOSHQA {type(e).__name__}: {e}"
finally:
    _s.rollback()
    _s.close()
check("B11 crud.delete_delivery to'g'ridan -> ValueError, yuk joyida",
      _xat is not None and not _xat.startswith("BOSHQA") and "Tayyor" in _xat and (holat(ob) or {}).get("yuklar") == hb["yuklar"],
      (_xat, holat(ob)))

# ══════════════════════════════════════════════════════════════
section("C. To'liq YETKAZILGAN (delivered) yuki o'chirilsa — in_progress (READY EMAS)")
# ══════════════════════════════════════════════════════════════
od, idd = peno_buyurtma()
rep0 = hisobot()
r = yuk(od, idd, 10)
did_d = r[1]
r = yuk_ochir(did_d)
check("C1 delivered yuki o'chirildi -> 200, holat in_progress", r.status_code == 200
      and (holat(od) or {}).get("status") == "in_progress" and (holat(od) or {}).get("yuklar") == [], (r.status_code, holat(od)))
check("C2 hisobotga KIRMADI (ilgari READY bo'lib kirardi)", hisobot() == rep0, (rep0, hisobot()))
r = tayyor(od)
check("C3 keyin \"Tayyor\" -> avto yuk, ready, hisobotga +1", r.status_code == 200
      and (holat(od) or {}).get("status") == "ready" and len((holat(od) or {}).get("yuklar") or []) == 1
      and hisobot()[0] == rep0[0] + 1, (r.status_code, holat(od), hisobot()))

oe, ie = peno_buyurtma()
y1 = yuk(oe, ie, 5)
y2 = yuk(oe, ie, 5)
check("C4 ikki yuk (5 + 5) -> delivered", (holat(oe) or {}).get("status") == "delivered", (y1, y2, holat(oe)))
r = yuk_ochir(y2[1])
check("C5 ikkinchi yuk o'chirildi -> in_progress (qisman)", r.status_code == 200 and (holat(oe) or {}).get("status") == "in_progress",
      (r.status_code, holat(oe)))
r = yuk_ochir(y1[1])
check("C6 in_progress dagi yuk o'chirildi -> in_progress (nazorat)", r.status_code == 200
      and (holat(oe) or {}).get("status") == "in_progress", (r.status_code, holat(oe)))

om3, im3 = mrp_buyurtma(5)
tm_c = ishlab(om3, im3, 5) if om3 else None
repc = hisobot()
r = yuk(om3, im3, 5)
r2 = yuk_ochir(r[1])
check("C7 MRP delivered yuki o'chirildi -> in_progress, TM 5 / band 5 qaytdi, hisobot o'zgarmadi",
      r[0] == 200 and r2.status_code == 200 and (holat(om3) or {}).get("status") == "in_progress"
      and tm_holat(tm_c) == (5.0, 5.0, 15000.0) and hisobot() == repc, (r, r2.status_code, holat(om3), tm_holat(tm_c)))

# ══════════════════════════════════════════════════════════════
section("D. Yuk xati \"Tayyor\" (READY) ni pasaytirmaydi")
# ══════════════════════════════════════════════════════════════
of, if_ = peno_buyurtma()
r = req(C, "post", "/api/returns", json={"order_id": of, "order_item_id": if_, "item_name": "x", "quantity": 10,
                                         "unit": "metr", "reason": "Ortiqcha", "to_stock": True})
rid_f = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
check("D0 hammasi \"Ortiqcha\" omborga -> 200", r.status_code == 200 and rid_f, (r.status_code, r.text[:200]))
r = tayyor(of)
check("D1 \"Tayyor\" -> ready, yuk yo'q", r.status_code == 200 and (holat(of) or {}).get("status") == "ready"
      and (holat(of) or {}).get("yuklar") == [], (r.status_code, holat(of)))
r = req(C, "delete", f"/api/returns/{rid_f}")
check("D2 qaytarish o'chirildi -> 200", r.status_code == 200, (r.status_code, r.text[:200]))
repd, hd = hisobot(), holat(of)
r = yuk(of, if_, 10)
hd2 = holat(of)
check("D3 qolgani yuk bilan topshirildi -> 200, holat READY QOLDI (delivered EMAS)",
      r[0] == 200 and hd2 and hd2["status"] == "ready" and len(hd2["yuklar"]) == 1, (r, hd2))
check("D4 hisobotdan CHIQMADI (ilgari -500 000)", hisobot() == repd, (repd, hisobot()))
check("D5 completed_at o'zgarmadi (\"Tayyor\" bosilgan payt)", hd2 and hd2["completed_at"] == hd["completed_at"],
      (hd["completed_at"], hd2 and hd2["completed_at"]))

og, ig = peno_buyurtma()
orm_yoz(og, status=OrderStatus.READY, completed_at=datetime.utcnow())      # eski ma'lumot: yuksiz READY
repg = hisobot()
r = yuk(og, ig, 10)
check("D6 eski yuksiz READY ga to'liq yuk -> READY qoladi, hisobot o'zgarmadi",
      r[0] == 200 and (holat(og) or {}).get("status") == "ready" and hisobot() == repg, (r, holat(og), repg, hisobot()))

oh, ih = peno_buyurtma()
orm_yoz(oh, is_pinned=True)
r = tayyor(oh)
hh = holat(oh)
check("D7 \"Tayyor\" avto yuki: ready, yuk 1, pin olindi, completed_at bor",
      r.status_code == 200 and hh and hh["status"] == "ready" and len(hh["yuklar"]) == 1 and not hh["pin"]
      and hh["completed_at"] is not None, (r.status_code, hh))

# ══════════════════════════════════════════════════════════════
section("E. O'chirish rejasi (GET /api/orders/{id} \"ochirish\") == DELETE amali — 93 / 94-band")
# ══════════════════════════════════════════════════════════════
KALITLAR = ("yuk_bor", "toliq_topshirilgan", "xomashyo_qaytishi_mumkin", "xomashyo_qaytadi", "qisman", "yumshoq",
            "hisobotda_qoladi")


def e_holat(lab, tayyorla, kutilgan):
    """kutilgan = (yumshoq, xomashyo_qaytadi, hisobotda_qoladi, qisman)."""
    s0 = hisobot()[0]
    oid = tayyorla()
    if not oid:
        check(f"{lab} holat tayyorlandi", False, oid)
        return
    rj = reja(oid)
    p1 = qoldiq(ID["PENO"])
    r = req(C, "delete", f"/api/orders/{oid}")
    dj = js(r) or {}
    p2 = qoldiq(ID["PENO"])
    s2 = hisobot()[0]
    check(f"{lab} rejada hamma kalit bor", isinstance(rj, dict) and all(k in rj for k in KALITLAR), rj)
    rj = rj if isinstance(rj, dict) else {}
    haqiqat = (bool(dj.get("soft_deleted")), p2 > p1 + 1e-9, s2 - s0 == 1, rj.get("qisman"))
    check(f"{lab} reja == amal (yumshoq, xomashyo, hisobotda)",
          r.status_code == 200 and (rj.get("yumshoq"), rj.get("xomashyo_qaytadi"), rj.get("hisobotda_qoladi"))
          == haqiqat[:3], (r.status_code, rj, haqiqat, dj))
    check(f"{lab} kutilgan: yumshoq={kutilgan[0]} xomashyo={kutilgan[1]} hisobotda={kutilgan[2]} qisman={kutilgan[3]}",
          (rj.get("yumshoq"), rj.get("xomashyo_qaytadi"), rj.get("hisobotda_qoladi"), rj.get("qisman")) == kutilgan, rj)


def _e1():
    return peno_buyurtma()[0]


def _e2():
    o, i = peno_buyurtma()
    yuk(o, i, 5)
    return o


def _e3():
    o, i = peno_buyurtma()
    yuk(o, i, 10)
    return o


def _e4():
    o, i = peno_buyurtma()
    tayyor(o)
    return o


def _e5():
    o, i = peno_buyurtma()
    orm_yoz(o, status=OrderStatus.READY, completed_at=datetime.utcnow())
    return o


def _e6():
    return peno_buyurtma(draft=True)[0]


def _e7():
    o, i = peno_buyurtma()
    req(C, "post", "/api/returns", json={"order_id": o, "order_item_id": i, "item_name": "x", "quantity": 4,
                                         "unit": "metr", "reason": "Ortiqcha", "to_stock": True})
    return o


def _e8():
    o, i = peno_buyurtma()
    orm_yoz(o, stock_returned=True)       # xomashyo avval qaytarilgan (tiklash izi) — ikkinchi marta qaytmaydi
    return o


e_holat("E1 jarayonda, yuksiz", _e1, (False, True, False, False))
e_holat("E2 qisman topshirilgan (5 / 10)", _e2, (True, True, False, True))
e_holat("E3 to'liq YETKAZILGAN (Tayyor emas)", _e3, (True, False, False, True))
e_holat("E4 Tayyor (yuk bilan)", _e4, (True, False, True, True))
e_holat("E5 eski yuksiz Tayyor", _e5, (True, True, True, False))
e_holat("E6 qoralama", _e6, (False, False, False, False))
e_holat("E7 jarayonda, 4 m ortiqcha omborga", _e7, (False, True, False, True))
e_holat("E8 jarayonda, xomashyo avval qaytarilgan (stock_returned)", _e8, (False, False, False, False))

# ══════════════════════════════════════════════════════════════
section("F. UI — HAQIQIY /orders (uvicorn + jsdom; faqat SQLite)")
# ══════════════════════════════════════════════════════════════
try:
    NODE_PATH = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=60).stdout.strip()
except Exception:                          # noqa: BLE001
    NODE_PATH = ""
ENV = dict(os.environ)
ENV["NODE_PATH"] = NODE_PATH

NODE_SAHIFA = r"""
const { JSDOM, VirtualConsole, ResourceLoader } = require("jsdom");
const [base, cookie, opsJson] = process.argv.slice(2);
class R extends ResourceLoader {
  fetch(url, o) {
    if (url.startsWith(base)) return super.fetch(url, o);
    const p = Promise.resolve(Buffer.from("window.Chart = function(){return {destroy(){},update(){}}};"));
    p.abort = () => {};
    return p;
  }
}
const kut = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const out = { xato: [], natija: [] };
  try {
    const html = await (await fetch(base + "/orders", { headers: { cookie } })).text();
    const vc = new VirtualConsole();
    vc.on("jsdomError", e => { const m = String(e && (e.message || e)).slice(0, 200); if (!/Not implemented|parse CSS/.test(m)) out.xato.push(m); });
    let pending = 0;
    const sorovlar = [];
    const dom = new JSDOM(html, {
      url: base + "/orders", runScripts: "dangerously", pretendToBeVisual: true, resources: new R(), virtualConsole: vc,
      beforeParse(w) {
        w.fetch = async (u, o) => {
          const url = new URL(String(u), base + "/orders").href;
          pending++;
          try {
            o = o || {};
            const h = Object.assign({}, o.headers || {}); h.cookie = cookie;
            const r = await fetch(url, Object.assign({}, o, { headers: h, redirect: "manual" }));
            if (o.method && o.method !== "GET") sorovlar.push([o.method, url.slice(base.length), r.status]);
            return r;
          } finally { pending--; }
        };
        w.alert = () => {}; w.confirm = () => true; w.scrollTo = () => {}; w.open = () => null;
        w.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
        w.HTMLElement.prototype.scrollIntoView = function () {};
      },
    });
    const w = dom.window;
    const tinch = async () => { for (let i = 0; i < 100; i++) { await kut(100); if (pending === 0) { await kut(300); if (pending === 0) return; } } };
    await kut(500); await tinch();
    const ops = JSON.parse(opsJson);
    for (const [amal, a1, a2] of ops) {
      const n = { amal, a1 };
      try {
        if (amal === "holat") {
          const el = w.document.getElementById("oi-" + a1);
          n.el_bor = !!el;
          if (el) {
            w.selectOrder(a1, el);
            await tinch();
            n.btn_ready = w.document.getElementById("btn-ready").style.display;
            n.btn_edit = w.document.getElementById("btn-edit").style.display;
            n.status = w.document.getElementById("od-status").textContent;
            n.ro_yxat = el.textContent.replace(/\s+/g, " ").slice(0, 200);
          }
        } else if (amal === "yuklar") {
          w.eval("selectedOrderId = " + Number(a1));
          await w.loadDeliveries(a1);
          await tinch();
          const hist = w.document.getElementById("dlvHistory");
          n.ochir_tugma = hist ? hist.querySelectorAll('button[onclick^="deleteDelivery("]').length : -1;
          n.qulf = hist ? hist.querySelectorAll(".dlv-qulf").length : -1;
        } else if (amal === "yuk_ochir") {
          w.eval("selectedOrderId = " + Number(a2));
          const tasdiq = [], msg = [];
          w.showConfirmModal = async (m) => { tasdiq.push(String(m)); return true; };
          w.showMsg = (m, t) => { msg.push(String(m) + " |" + t); };
          await w.deleteDelivery(a1);
          await tinch();
          n.tasdiq = tasdiq; n.msg = msg;
        } else if (amal === "ochirish") {
          w.eval("selectedOrderId = " + Number(a1));
          const tasdiq = [];
          w.showConfirmModal = async (m) => { tasdiq.push(String(m)); return false; };
          w.showPromptModal = async () => null;
          await w.deleteSelected();
          await tinch();
          n.tasdiq = tasdiq;
        }
      } catch (e) { n.istisno = String(e && (e.stack || e)).slice(0, 400); }
      out.natija.push(n);
    }
    out.sorovlar = sorovlar;
  } catch (e) { out.istisno = String(e && (e.stack || e)).slice(0, 600); }
  console.log("NATIJA_JSON " + JSON.stringify(out));
  process.exit(0);
})();
"""


def node_js(kod, *args, timeout=200):
    f = os.path.join(_T, "n_%d.js" % int(time.time() * 1e6))
    open(f, "w", encoding="utf-8").write(kod)
    try:
        k = subprocess.run(["node", f] + [str(a) for a in args], capture_output=True, text=True,
                           env=ENV, timeout=timeout)
    except Exception as e:                 # noqa: BLE001
        return {"istisno_py": f"{type(e).__name__}: {e}"}
    for q in k.stdout.splitlines():
        if q.startswith("NATIJA_JSON "):
            try:
                return json.loads(q[len("NATIJA_JSON "):])
            except Exception as e:         # noqa: BLE001
                return {"istisno_py": f"json: {e}"}
    return {"stdout": k.stdout[-600:], "stderr": k.stderr[-600:]}


def bosh_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


if not PG_URL:
    # UI holatlari (hammasi yangi, to'lovsiz)
    fu_del, fu_del_i = peno_buyurtma()
    fu_del_y = yuk(fu_del, fu_del_i, 10)[1]
    fu_rdy, _i = peno_buyurtma()
    fu_rdy_y = ((js(tayyor(fu_rdy)) or {}).get("auto_delivery") or {}).get("delivery_id")
    fu_prog, _i = peno_buyurtma()
    fu_qis, fu_qis_i = peno_buyurtma()
    yuk(fu_qis, fu_qis_i, 5)
    fu_eski, _i = peno_buyurtma()
    orm_yoz(fu_eski, status=OrderStatus.READY, completed_at=datetime.utcnow())
    fu_qt, fu_qt_i = peno_buyurtma()
    yuk(fu_qt, fu_qt_i, 5, tolov=50_000)
    check("F0 UI holatlari tayyorlandi", all([fu_del, fu_del_y, fu_rdy, fu_rdy_y, fu_prog, fu_qis, fu_eski, fu_qt])
          and len((holat(fu_qt) or {}).get("tolovlar") or []) == 1
          and (holat(fu_del) or {}).get("status") == "delivered" and (holat(fu_rdy) or {}).get("status") == "ready",
          (holat(fu_del), holat(fu_rdy)))

    BASE = COOKIE = SERVER_XATO = None
    try:
        import uvicorn                             # noqa: E402
        import httpx                               # noqa: E402
        _port = bosh_port()
        _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=_port, log_level="critical",
                                             lifespan="off"))
        threading.Thread(target=_srv.run, daemon=True).start()
        for _ in range(150):
            if _srv.started:
                break
            time.sleep(0.1)
        BASE = f"http://127.0.0.1:{_port}"
        _l2 = httpx.post(BASE + "/login", data={"username": "TY_admin", "password": "Parol123!"}, follow_redirects=False)
        COOKIE = "; ".join(h.split(";")[0] for h in _l2.headers.get_list("set-cookie"))
    except Exception as e:                 # noqa: BLE001
        SERVER_XATO = f"{type(e).__name__}: {e}"
    _jsdom_bor = subprocess.run(["node", "-e", "require('jsdom')"], capture_output=True, env=ENV).returncode == 0
    check("F0a jsdom topildi (topilmasa F yiqiladi — jim o'tmaydi)", _jsdom_bor, NODE_PATH)
    check("F0b sinov serveri ko'tarildi, login cookie bor", SERVER_XATO is None and bool(COOKIE), SERVER_XATO)

    OPS = [["holat", fu_del], ["holat", fu_rdy], ["holat", fu_prog],
           ["yuklar", fu_rdy], ["yuklar", fu_del],
           ["yuk_ochir", fu_rdy_y, fu_rdy],
           ["ochirish", fu_del], ["ochirish", fu_rdy], ["ochirish", fu_qis], ["ochirish", fu_prog], ["ochirish", fu_eski],
           ["ochirish", fu_qt]]
    U = node_js(NODE_SAHIFA, BASE, COOKIE, json.dumps(OPS)) if not SERVER_XATO else {"istisno_py": SERVER_XATO}
    NT = U.get("natija") or []
    check("F0c sahifa yuklandi, JS xatosiz, hamma amal bajarildi",
          not U.get("istisno") and not U.get("istisno_py") and not U.get("xato") and len(NT) == len(OPS)
          and not any(x.get("istisno") for x in NT), {k: U.get(k) for k in ("istisno", "istisno_py", "xato", "stderr")})

    def nt(i):
        return NT[i] if i < len(NT) else {}

    a = nt(0)
    check("F1 delivered: \"Tayyor\" tugmasi KO'RINADI, tahrir yashirin",
          a.get("el_bor") and a.get("btn_ready") == "block" and a.get("btn_edit") == "none", a)
    check("F2 delivered: nishon \"Yetkazildi\" + \"belgilanmagan\", \"✓ Tayyor\" EMAS",
          "Yetkazildi" in str(a.get("status")) and "belgilanmagan" in str(a.get("status"))
          and "✓ Tayyor" not in str(a.get("status")), a)
    check("F3 delivered: ro'yxat nishoni \"Yetkazildi\"", "Yetkazildi" in str(a.get("ro_yxat")), a.get("ro_yxat"))
    b = nt(1)
    check("F4 ready: \"✓ Tayyor\", \"Tayyor\" va tahrir tugmalari yashirin",
          "✓ Tayyor" in str(b.get("status")) and b.get("btn_ready") == "none" and b.get("btn_edit") == "none", b)
    c = nt(2)
    check("F5 jarayonda (nazorat): \"Jarayonda\", ikkala tugma ko'rinadi",
          "Jarayonda" in str(c.get("status")) and c.get("btn_ready") == "block" and c.get("btn_edit") == "block", c)
    d = nt(3)
    check("F6 ready yuk xatlari: o'chirish tugmasi YO'Q, 🔒 bor", d.get("ochir_tugma") == 0 and d.get("qulf") == 1, d)
    e = nt(4)
    check("F7 delivered yuk xatlari: o'chirish tugmasi bor (nazorat)", e.get("ochir_tugma") == 1 and e.get("qulf") == 0, e)
    f = nt(5)
    check("F8 deleteDelivery (ready): server sababi xabarda, yuk joyida",
          any("o'chirib bo'lmaydi" in x and "|error" in x for x in (f.get("msg") or []))
          and (holat(fu_rdy) or {}).get("yuklar") == [fu_rdy_y], (f, holat(fu_rdy)))

    def matn(i):
        t = (nt(i).get("tasdiq") or [""])
        return t[0] if t else ""

    t_del, t_rdy, t_qis, t_prg, t_eski = matn(6), matn(7), matn(8), matn(9), matn(10)
    check("F9 tasdiq (delivered): YETKAZILGAN, xomashyo QAYTARILMAYDI, hisobotga KIRMAYDI, \"saqlanib qoladi\" YO'Q",
          "YETKAZILGAN" in t_del and "QAYTARILMAYDI" in t_del and "KIRMAYDI" in t_del and "saqlanib qoladi" not in t_del, t_del)
    check("F10 tasdiq (ready, yuk bilan): TAYYOR, QAYTARILMAYDI, hisobotlarda saqlanib qoladi",
          "TAYYOR" in t_rdy and "QAYTARILMAYDI" in t_rdy and "saqlanib qoladi" in t_rdy and "KIRMAYDI" not in t_rdy, t_rdy)
    check("F11 tasdiq (qisman): qisman, faqat QOLGAN qism, hisobotga KIRMAYDI",
          "qisman topshirilgan" in t_qis and "Faqat QOLGAN" in t_qis and "KIRMAYDI" in t_qis
          and "saqlanib qoladi" not in t_qis, t_qis)
    check("F12 tasdiq (jarayonda): xomashyo qaytariladi, butunlay o'chiriladi",
          "omborga qaytariladi" in t_prg and "Butunlay" in t_prg and "QAYTARILMAYDI" not in t_prg, t_prg)
    check("F13 tasdiq (eski yuksiz ready): TAYYOR, xomashyo QAYTARILADI (server kabi), hisobotda qoladi",
          "TAYYOR" in t_eski and "omborga qaytariladi" in t_eski and "QAYTARILMAYDI" not in t_eski
          and "saqlanib qoladi" in t_eski, t_eski)
    t_qt = matn(11)
    check("F15 tasdiq (qisman + to'lov): to'lov SAQLANADI deyiladi (server yumshoq o'chiradi), \"AVTOMATIK o'chadi\" EMAS",
          "qisman topshirilgan" in t_qt and "avtomatik o'chmaydi" in t_qt and "AVTOMATIK o'chadi" not in t_qt, t_qt)
    check("F14 tasdiq rad etildi — buyurtma o'chirish so'rovi YUBORILMADI",
          not any(s[0] == "DELETE" and s[1].startswith("/api/orders/") for s in (U.get("sorovlar") or [])), U.get("sorovlar"))

# ══════════════════════════════════════════════════════════════
section("P. Parallel (faqat PG): \"Tayyor\" || yuk xatini o'chirish — delivered buyurtma")
# ══════════════════════════════════════════════════════════════
if PG_URL:
    _pn = 0
    for _urinish in range(3):
        op, ip = peno_buyurtma()
        _yp = yuk(op, ip, 10)
        did_p = _yp[1]
        nat = {}

        def _a(oid=op):
            s = SessionLocal()
            asl = s.commit
            _bir = [True]

            def sekin():
                if _bir[0]:
                    _bir[0] = False
                    time.sleep(0.4)
                asl()
            s.commit = sekin
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    nat["a"] = services.complete_order(s, oid)
            except Exception as e:         # noqa: BLE001
                nat["a"] = f"{type(e).__name__}: {e}"
            finally:
                s.close()

        def _b(did=did_p):
            time.sleep(0.15)
            s = SessionLocal()
            try:
                nat["b"] = crud.delete_delivery(s, did, company_id=1)
            except ValueError as e:
                nat["b"] = f"ValueError: {e}"
                s.rollback()
            except Exception as e:         # noqa: BLE001
                nat["b"] = f"{type(e).__name__}: {e}"
                s.rollback()
            finally:
                s.close()

        ta, tb = threading.Thread(target=_a), threading.Thread(target=_b)
        ta.start()
        tb.start()
        ta.join(30)
        tb.join(30)
        hp = holat(op)
        if (str(nat.get("b", "")).startswith("ValueError") and hp and hp["status"] == "ready"
                and hp["yuklar"] == [did_p]):
            _pn += 1
        else:
            print("   P urinish", _urinish, nat, hp)
    check("P1 3 / 3: \"Tayyor\" yutdi -> yuk o'chirish rad (400), asl yuk joyida, holat ready", _pn == 3, _pn)

# ══════════════════════════════════════════════════════════════
section("H. Statik tartib")
# ══════════════════════════════════════════════════════════════
_dd = manba(crud, "delete_delivery")
check("H1 delete_delivery: qulf -> qayta o'qish -> READY rad -> to'lov so'rovi (YukToloviBor dan OLDIN)",
      tartibda(_dd, "_pul_qulfi(db, 101, order.id)", "db.expire_all()", "order = d.order",
               "if order.status == OrderStatus.READY:", "raise ValueError(", "tolovlar = db.query(Payment)",
               "raise YukToloviBor("), _dd[:200])
check("H2 delete_delivery: delivered -> IN_PROGRESS (READY ga o'tkazish YO'Q)",
      "order.status = OrderStatus.IN_PROGRESS" in _dd and "order.status = OrderStatus.READY" not in _dd)
_cd = manba(crud, "create_delivery")
check("H3 create_delivery: READY holati saqlanadi, pin / completed_at avvalgidek",
      tartibda(_cd, "if fully and order.status not in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):",
               "if order.status != OrderStatus.READY:", "order.status = OrderStatus.DELIVERED",
               "if not order.completed_at:", "order.is_pinned = False"))
_rj = manba(main, "_buyurtma_ochirish_rejasi")
_ad = manba(main, "api_delete_order")
_ifodalar = ("is_fully_delivered = order.status == OrderStatus.DELIVERED or order.is_fully_delivered",
             "can_return = order.status != OrderStatus.DRAFT and not is_fully_delivered",
             "qisman = services.buyurtmadan_qisman_chiqqan(order)",
             "order.status in (OrderStatus.READY, OrderStatus.DELIVERED)")
check("H4 o'chirish rejasi va api_delete_order — AYNAN bir xil shartlar",
      all(x in _rj and x in _ad for x in _ifodalar), [x for x in _ifodalar if x not in _rj or x not in _ad])
check("H5 GET /api/orders/{id} rejani qaytaradi", '"ochirish": _buyurtma_ochirish_rejasi(order)' in manba(main, "api_get_order"))
_html = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
check("H6 orders.html: isReady faqat ready; tahrir delivered da ham yashirin",
      "const isReady = d.status === 'ready';" in _html
      and "const isReady = d.status === 'ready' || d.status === 'delivered';" not in _html
      and "(isReady || isDelivered) ? 'none' : 'block'" in _html)
check("H7 orders.html: tasdiq matni server rejasidan (ochirish / hisobotda_qoladi)",
      tartibda(_html, "async function deleteSelected()", "const oc = o.ochirish || {};", "oc.xomashyo_qaytadi",
               "oc.yumshoq", "oc.hisobotda_qoladi", "showConfirmModal("))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(0 if FAIL == 0 else 1)
