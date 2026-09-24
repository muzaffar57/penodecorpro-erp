#!/usr/bin/env python3
"""
test_ortiqcha_qaytarish.py — 5-bo'lim 57-band darvozasi (kech60, 2026-09-24): ORTIQCHA mahsulot omborga.

FOYDALANUVCHI QARORI (kech60, tugma): "Ha — kerak bo'lmay qolgan ortiqcha mahsulotni omborga qo'yamiz" —
mijozga HALI TOPSHIRILMAGAN mahsulotni "Butun" (Ortiqcha) deb omborga qaytarish hayotda bor.

NIMA UCHUN (asl kod `55b6f69` da O'LCHANGAN — `work/probe60_k3.py`)
--------------------------------------------------------------------
Profil 10 m (penoplast 0.10 blok), "Butun" 5 m omborga (tayyor mahsulot 5 m / 25 000):
  * S1 buyurtma o'chirildi — penoplast 10 m uchun TO'LIQ qaytdi VA 5 m tayyor mahsulot qoldi (ikki marta);
  * S3 detal o'chirildi — xuddi shunday; S4 tahrir 10 -> 3 m — penoplast 7 m qaytdi + 5 m qoldi;
  * S5 3 m topshirilgan, 5 m qaytarilgan, o'chirildi — qolgan 7 m to'liq qaytdi.
  Sabab: 3-band yig'indisi qaytarishni BUYURTMA miqdoriga (topshirilganga emas) cheklaydi, lekin topshirilmagan
  qismdan omborga qo'yilgan miqdor buyurtmaning "qolgan" qismidan AYIRILMASDI.

YECHIM (texnik — Claude): `ReturnItem.ortiqcha_miqdor` — qaytarishning topshirilmagan qismi (avval topshirilgandan,
qolgani ortiqcha); `OrderItem.remaining_qty` = buyurtma − topshirilgan − ortiqcha (yetkazish cheklovi, "Tayyor",
o'chirish / tiklash, qisman yakunlash — hammasi shu orqali); detal o'chirish rad (400), tahrir pastki chegarasi
topshirilgan + ortiqcha; o'chirilgan buyurtmada ortiqcha qaytarishni yozish / o'chirish rad (tiklash simmetriyasi);
`main._migrate_ortiqcha_qaytarish` eski yozuvlarni vaqt tartibida to'ldiradi. Pul ("Pul qaytdi") O'ZGARMAYDI.

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_ortiqcha_qaytarish.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_ortiqcha_qaytarish.py
"""
import os
import sys
import inspect
import tempfile
import itertools
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "ortiqcha_qaytarish_test"
_DB = os.path.join(tempfile.gettempdir(), "ortiqcha_qaytarish_test.db")

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
    import crud, auth                              # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, ReturnItem, FinishedProduct, Order, OrderItem, Delivery, DeliveryItem,
    Recipe, RecipeIngredient,
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
        with contextlib.redirect_stdout(_quiet):
            return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def taxminan(a, b, eps=0.0005):
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


def manba(mod, nom):
    try:
        return inspect.getsource(getattr(mod, nom))
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "OQ_admin", "Parol123!", UserRole.ADMIN, "OQ Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="OQ Penoplast", unit="blok", stock_quantity=100,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="OQ Kley", unit="kg", stock_quantity=1_000, price_per_unit=2_000,
                 category="Kimyo")
_db.add_all([PENO, KLEY])
_db.commit()
RCP = Recipe(company_id=1, name="OQ R", batch_size_kg=100.0)
_db.add(RCP)
_db.commit()
_db.add(RecipeIngredient(recipe_id=RCP.id, inventory_id=KLEY.id, quantity_kg=100.0))   # 1 kg loy = 1 kg kley
_db.commit()
PNO, KNO, RNO = PENO.id, KLEY.id, RCP.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
req(C, "post", "/login", data={"username": "OQ_admin", "password": "Parol123!"}, follow_redirects=False)

_sanoq = itertools.count(1)


def nom(asos):
    return f"OQ {asos} {next(_sanoq)}"


def peno():
    s = SessionLocal()
    try:
        return float(s.get(Inventory, PNO).stock_quantity)
    finally:
        s.close()


def kley():
    s = SessionLocal()
    try:
        return float(s.get(Inventory, KNO).stock_quantity)
    finally:
        s.close()


def loyiha():
    s = SessionLocal()
    try:
        n = next(_sanoq)
        p = Project(company_id=1, client_name=f"OQ Mijoz {n}", project_name=f"OQ loyiha {n}",
                    total_budget=0, total_paid=0)
        s.add(p)
        s.commit()
        return p.id
    finally:
        s.close()


def detal(n, metr):
    return {"name": n, "category": "profil", "width": 20, "thickness": 10, "length": metr, "quantity": 1,
            "unit_price": 20000, "is_coated": False, "penoplast_id": PNO}


def yarat(detallar, loy_kg=0):
    """Buyurtma (jarayonda). Qaytaradi (order_id, {nom: item_id}, project_id) yoki (None, {}, pid)."""
    pid = loyiha()
    tana = {"project_id": pid, "order_type": "product", "loy_kg": loy_kg, "items": detallar}
    if loy_kg:
        tana["recipe_id"] = RNO
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    j = js(r) or {}
    if r.status_code != 200 or "id" not in j:
        return None, {}, pid
    return j["id"], {x["name"]: x["id"] for x in j.get("items", [])}, pid


def qaytar(oid, iid, n, miqdor, sabab="Ortiqcha"):
    return req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": iid, "item_name": n,
                                                 "quantity": miqdor, "unit": "metr", "reason": sabab,
                                                 "refund_amount": 0, "to_stock": True})


def yetkaz(oid, iid, miqdor):
    return req(C, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": iid,
                                                                                "quantity": miqdor}],
                                                    "notes": f"OQ {next(_sanoq)}"})


def detal_holat(iid):
    """(miqdor, topshirilgan, ortiqcha, qolgan) yoki None."""
    s = SessionLocal()
    try:
        it = s.get(OrderItem, iid)
        if it is None:
            return None
        return (float(it.order_qty_normalized), float(it.delivered_qty), float(getattr(it, "ortiqcha_qty", 0)),
                float(it.remaining_qty))
    finally:
        s.close()


def buyurtma(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if o is None:
            return None
        return {"status": o.status.value, "is_deleted": bool(o.is_deleted), "stock_returned": bool(o.stock_returned),
                "total": float(o.total_amount or 0), "agreed": float(o.agreed_amount or 0) if o.agreed_amount is not None else None}
    finally:
        s.close()


def qaytarish(rid):
    s = SessionLocal()
    try:
        r = s.get(ReturnItem, rid)
        if r is None:
            return None
        return {"q": float(r.quantity), "ortiqcha": (None if getattr(r, "ortiqcha_miqdor", None) is None
                                                     else float(r.ortiqcha_miqdor)),
                "fp": r.finished_product_id, "item": r.order_item_id}
    finally:
        s.close()


def tm(fid):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid) if fid else None
        return None if f is None else (float(f.quantity), round(float(f.cost_price or 0), 2))
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════
section("A. Topshirilmagan buyurtma: 5 m ortiqcha omborga -> buyurtma o'chirildi (S1)")
# ══════════════════════════════════════════════════════════════
na = nom("A")
p0 = peno()
oid_a, ia, _ = yarat([detal(na, 10)])
p1 = peno()
check("A0 buyurtma yaratildi, penoplast 0.10 blok yechildi", oid_a and taxminan(p0 - p1, 0.10), (oid_a, p0, p1))
r = qaytar(oid_a, ia.get(na), na, 5)
ra = js(r) or {}
check("A1 5 m \"Butun\" qaytarish -> 200", r.status_code == 200, r.text[:200])
rid_a = ra.get("id")
fid_a = ra.get("finished_product_id")
check("A2 yozuvda ortiqcha_miqdor = 5 (hech narsa topshirilmagan)", (qaytarish(rid_a) or {}).get("ortiqcha") == 5.0,
      qaytarish(rid_a))
check("A3 detal: qolgan 5 (10 − 0 − 5)", detal_holat(ia.get(na)) == (10.0, 0.0, 5.0, 5.0), detal_holat(ia.get(na)))
check("A4 tayyor mahsulot 5 m / 25 000", tm(fid_a) == (5.0, 25000.0), tm(fid_a))
r = req(C, "delete", f"/api/orders/{oid_a}")
check("A5 buyurtma o'chirildi -> 200", r.status_code == 200, r.text[:200])
check("A6 penoplast FAQAT qolgan 5 m uchun qaytdi (+0.05, 10 m uchun EMAS)", taxminan(peno() - p1, 0.05),
      (p1, peno()))
check("A7 tayyor mahsulot 5 m / 25 000 QOLDI (mahsulot omborda)", tm(fid_a) == (5.0, 25000.0), tm(fid_a))
check("A8 sabab matnida ortiqcha qism aytiladi", "ortiqcha" in str((js(r) or {}).get("reason") or ""), r.text[:300])

# ══════════════════════════════════════════════════════════════
section("B. Yetkazish cheklovi: ortiqcha qism yana topshirilmaydi")
# ══════════════════════════════════════════════════════════════
nb = nom("B")
oid_b, ib, _ = yarat([detal(nb, 10)])
iid_b = ib.get(nb)
r = qaytar(oid_b, iid_b, nb, 5)
check("B0 5 m ortiqcha -> 200", r.status_code == 200, r.text[:200])
r = yetkaz(oid_b, iid_b, 6)
check("B1 6 m yetkazish -> rad (qolgan 5)", r.status_code in (400, 409, 422), (r.status_code, r.text[:200]))
check("B2 rad etilganda topshirilgan 0", detal_holat(iid_b) == (10.0, 0.0, 5.0, 5.0), detal_holat(iid_b))
r = yetkaz(oid_b, iid_b, 5)
check("B3 5 m yetkazish -> 200", r.status_code == 200, r.text[:200])
check("B4 detal: qolgan 0", detal_holat(iid_b) == (10.0, 5.0, 5.0, 0.0), detal_holat(iid_b))
r = req(C, "get", f"/api/orders/{oid_b}/delivery-status")
_it = ((js(r) or {}).get("items") or [{}])[0]
check("B5 yetkazish holati: remaining 0, ortiqcha 5, is_done", _it.get("remaining") == 0 and _it.get("ortiqcha") == 5
      and _it.get("is_done") is True, _it)
_b = buyurtma(oid_b)
check("B6 buyurtma to'liq topshirilgan hisoblanadi (status delivered)", (_b or {}).get("status") == "delivered", _b)

# ══════════════════════════════════════════════════════════════
section("C. \"Tayyor\" (avtomatik to'liq topshirish) ortiqcha qismni topshirmaydi")
# ══════════════════════════════════════════════════════════════
nc = nom("C")
oid_c, ic, _ = yarat([detal(nc, 10)])
iid_c = ic.get(nc)
qaytar(oid_c, iid_c, nc, 4)
pc = peno()
r = req(C, "post", f"/api/orders/{oid_c}/ready")
check("C1 Tayyor -> 200", r.status_code == 200, r.text[:200])
check("C2 avtomatik topshirilgani 6 m (4 m omborda)", detal_holat(iid_c) == (10.0, 6.0, 4.0, 0.0), detal_holat(iid_c))
check("C3 penoplast o'zgarmadi", taxminan(peno(), pc), (pc, peno()))

# ══════════════════════════════════════════════════════════════
section("D. Detal o'chirish: ortiqcha qo'yilgan detal rad (400), qaytarish o'chirilgach — ruxsat")
# ══════════════════════════════════════════════════════════════
nd1, nd2 = nom("D1"), nom("D2")
oid_d, idd, _ = yarat([detal(nd1, 10), detal(nd2, 4)])
iid_d = idd.get(nd1)
r = qaytar(oid_d, iid_d, nd1, 5)
rid_d = (js(r) or {}).get("id")
check("D0 boshqa detal (D2) qolgani o'zgarmadi — ortiqcha faqat o'z detaliga", detal_holat(idd.get(nd2)) ==
      (4.0, 0.0, 0.0, 4.0), detal_holat(idd.get(nd2)))
fid_d = (js(r) or {}).get("finished_product_id")
pd = peno()
r = req(C, "delete", f"/api/order-items/{iid_d}")
check("D1 detal o'chirish -> 400", r.status_code == 400, (r.status_code, r.text[:200]))
check("D2 xabar: omborga qaytarilgan, qaytarishni o'chiring", "omborga qaytarilgan" in r.text and
      "qaytarishni" in r.text, r.text[:300])
check("D3 rad etilganda penoplast, detal, tayyor mahsulot o'zgarmadi",
      taxminan(peno(), pd) and detal_holat(iid_d) == (10.0, 0.0, 5.0, 5.0) and tm(fid_d) == (5.0, 25000.0),
      (pd, peno(), detal_holat(iid_d), tm(fid_d)))
r = req(C, "delete", f"/api/returns/{rid_d}")
check("D4 qaytarish o'chirildi -> 200 (tayyor mahsulot olinadi)", r.status_code == 200 and tm(fid_d) is None
      or (r.status_code == 200 and (tm(fid_d) or (0,))[0] == 0), (r.status_code, r.text[:200], tm(fid_d)))
check("D5 detal: ortiqcha yo'q, qolgan 10", detal_holat(iid_d) == (10.0, 0.0, 0.0, 10.0), detal_holat(iid_d))
r = req(C, "delete", f"/api/order-items/{iid_d}")
check("D6 endi detal o'chirildi -> 200, penoplast 0.10 qaytdi", r.status_code == 200 and taxminan(peno() - pd, 0.10),
      (r.status_code, r.text[:200], pd, peno()))

# ══════════════════════════════════════════════════════════════
section("E. Tahrir: pastki chegara topshirilgan + ortiqcha")
# ══════════════════════════════════════════════════════════════
ne = nom("E")
oid_e, ie, pid_e = yarat([detal(ne, 10)])
iid_e = ie.get(ne)
qaytar(oid_e, iid_e, ne, 5)
pe = peno()
r = req(C, "put", f"/api/orders/{oid_e}", json={"project_id": pid_e, "order_type": "product", "loy_kg": 0,
                                                 "items": [detal(ne, 3)]}, params={"confirm_shortage": "true"})
check("E1 buyurtma tahriri 10 -> 3 m -> 400", r.status_code == 400, (r.status_code, r.text[:200]))
check("E2 xabar: omborga ortiqcha qaytarilgan, kamida 5", "omborga ortiqcha" in r.text and "kamida 5" in r.text,
      r.text[:300])
check("E3 rad etilganda penoplast va detal o'zgarmadi", taxminan(peno(), pe) and
      detal_holat(iid_e) == (10.0, 0.0, 5.0, 5.0), (pe, peno(), detal_holat(iid_e)))
r = req(C, "put", f"/api/orders/{oid_e}", json={"project_id": pid_e, "order_type": "product", "loy_kg": 0,
                                                 "items": [detal(ne, 7)]}, params={"confirm_shortage": "true"})
check("E4 tahrir 10 -> 7 m -> 200", r.status_code == 200, (r.status_code, r.text[:200]))
check("E5 penoplast 3 m uchun qaytdi (+0.03)", taxminan(peno() - pe, 0.03), (pe, peno()))
check("E6 detal: 7 m, ortiqcha 5, qolgan 2", detal_holat(iid_e) == (7.0, 0.0, 5.0, 2.0), detal_holat(iid_e))
r = req(C, "put", f"/api/order-items/{iid_e}", json={"length": 4})
check("E7 bitta detal tahriri 4 m (< 5) -> 400", r.status_code == 400 and "ortiqcha" in r.text,
      (r.status_code, r.text[:200]))
check("E8 rad etilganda detal o'zgarmadi", detal_holat(iid_e) == (7.0, 0.0, 5.0, 2.0), detal_holat(iid_e))
r = req(C, "put", f"/api/order-items/{iid_e}", json={"length": 6})
check("E9 bitta detal tahriri 6 m -> 200, qolgan 1", r.status_code == 200 and
      detal_holat(iid_e) == (6.0, 0.0, 5.0, 1.0), (r.status_code, r.text[:200], detal_holat(iid_e)))

# ══════════════════════════════════════════════════════════════
section("F. Qisman topshirilgan: 3 m topshirildi, 5 m qaytarildi (3 topshirilgandan + 2 ortiqcha)")
# ══════════════════════════════════════════════════════════════
nf = nom("F")
oid_f, iff, _ = yarat([detal(nf, 10)])
iid_f = iff.get(nf)
yetkaz(oid_f, iid_f, 3)
r = qaytar(oid_f, iid_f, nf, 5)
rid_f = (js(r) or {}).get("id")
check("F1 yozuv ortiqcha_miqdor = 2", (qaytarish(rid_f) or {}).get("ortiqcha") == 2.0, qaytarish(rid_f))
check("F2 detal: qolgan 5 (10 − 3 − 2)", detal_holat(iid_f) == (10.0, 3.0, 2.0, 5.0), detal_holat(iid_f))
pf = peno()
r = req(C, "delete", f"/api/orders/{oid_f}")
check("F3 o'chirildi (yumshoq) -> 200", r.status_code == 200 and (js(r) or {}).get("soft_deleted") is True,
      r.text[:200])
check("F4 penoplast faqat qolgan 5 m uchun (+0.05)", taxminan(peno() - pf, 0.05), (pf, peno()))
r2 = qaytar(oid_f, iid_f, nf, 1)
check("F5 o'chirilgan buyurtmada yana ortiqcha qaytarish -> 400", r2.status_code == 400, (r2.status_code, r2.text[:200]))
r2 = req(C, "delete", f"/api/returns/{rid_f}")
check("F6 o'chirilgan buyurtmaning ortiqcha qaytarishini o'chirish -> 400", r2.status_code == 400,
      (r2.status_code, r2.text[:200]))
check("F7 rad etilganda penoplast o'zgarmadi", taxminan(peno() - pf, 0.05), (pf, peno()))
r = req(C, "post", f"/api/orders/{oid_f}/restore")
check("F8 tiklash -> 200", r.status_code == 200, r.text[:200])
check("F9 tiklash AYNAN o'shani qayta yechdi (penoplast asliga)", taxminan(peno(), pf), (pf, peno()))
_bf = buyurtma(oid_f)
check("F10 tiklangan: is_deleted False, stock_returned False", _bf and not _bf["is_deleted"] and
      not _bf["stock_returned"], _bf)

# ══════════════════════════════════════════════════════════════
section("G. Faqat topshirilgandan qaytarish (ortiqcha 0) — avvalgidek")
# ══════════════════════════════════════════════════════════════
ng = nom("G")
oid_g, ig, _ = yarat([detal(ng, 10)])
iid_g = ig.get(ng)
yetkaz(oid_g, iid_g, 6)
r = qaytar(oid_g, iid_g, ng, 4)
rid_g = (js(r) or {}).get("id")
check("G1 ortiqcha_miqdor = 0", (qaytarish(rid_g) or {}).get("ortiqcha") == 0.0, qaytarish(rid_g))
check("G2 qolgan 4 (10 − 6)", detal_holat(iid_g) == (10.0, 6.0, 0.0, 4.0), detal_holat(iid_g))
pg = peno()
req(C, "delete", f"/api/orders/{oid_g}")
check("G3 o'chirishda qolgan 4 m to'liq qaytdi (+0.04)", taxminan(peno() - pg, 0.04), (pg, peno()))
r = qaytar(oid_g, iid_g, ng, 1)
check("G4 o'chirilgan buyurtmada topshirilgandan qaytarish (ortiqcha 0) — cheklanmaydi", r.status_code == 200,
      (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════
section("H. Qisman yakunlash (\"Tayyor\" qisman topshirilganda): miqdor = topshirilgan + ortiqcha")
# ══════════════════════════════════════════════════════════════
nh = nom("H")
oid_h, ih, _ = yarat([detal(nh, 10)])
iid_h = ih.get(nh)
yetkaz(oid_h, iid_h, 2)
qaytar(oid_h, iid_h, nh, 5)
check("H0 detal: 2 topshirilgan, 3 ortiqcha, qolgan 5", detal_holat(iid_h) == (10.0, 2.0, 3.0, 5.0), detal_holat(iid_h))
ph = peno()
_bh0 = buyurtma(oid_h)
r = req(C, "post", f"/api/orders/{oid_h}/ready")
check("H1 Tayyor -> 200", r.status_code == 200, r.text[:200])
check("H2 penoplast faqat qolgan 5 m uchun qaytdi (+0.05)", taxminan(peno() - ph, 0.05), (ph, peno()))
check("H3 detal miqdori 5 (2 + 3), qolgan 0", detal_holat(iid_h) == (5.0, 2.0, 3.0, 0.0), detal_holat(iid_h))
_bh = buyurtma(oid_h)
check("H4 buyurtma jami summasi AYNAN yarmiga tushdi (5 / 10 — ortiqcha qism buyurtmada qoladi)",
      _bh0 and _bh and _bh0["total"] > 0 and taxminan(_bh["total"], _bh0["total"] * 0.5, 0.011), (_bh0, _bh))

# ══════════════════════════════════════════════════════════════
section("M. Qoplamali (loy 10 kg): o'chirish / tiklashda loy ham faqat qolgan qism uchun")
# ══════════════════════════════════════════════════════════════
def detal_q(n, metr):
    d = detal(n, metr)
    d["is_coated"] = True
    return d


nm1 = nom("M1")
k0 = kley()
oid_m1, im1, _ = yarat([detal_q(nm1, 10)], loy_kg=10)
k1 = kley()
check("M0 qoplamali buyurtma: loy 10 kg (kley −10)", oid_m1 and taxminan(k0 - k1, 10.0), (oid_m1, k0, k1))
qaytar(oid_m1, im1.get(nm1), nm1, 5)
r = req(C, "delete", f"/api/orders/{oid_m1}")
check("M1 topshirilmagan, 5 m ortiqcha -> o'chirishda loy 5 kg qaytdi (10 EMAS)",
      r.status_code == 200 and taxminan(kley() - k1, 5.0), (r.status_code, k1, kley()))
nm2 = nom("M2")
oid_m2, im2, _ = yarat([detal_q(nm2, 10)], loy_kg=10)
iid_m2 = im2.get(nm2)
yetkaz(oid_m2, iid_m2, 1)
qaytar(oid_m2, iid_m2, nm2, 5)                                     # 1 topshirilgandan + 4 ortiqcha
check("M2 detal: 1 topshirilgan, 4 ortiqcha, qolgan 5", detal_holat(iid_m2) == (10.0, 1.0, 4.0, 5.0),
      detal_holat(iid_m2))
k2 = kley()
r = req(C, "delete", f"/api/orders/{oid_m2}")
check("M3 qisman topshirilgan + ortiqcha -> loy 5 kg qaytdi (qolgan ulush 0.5, 0.9 EMAS)",
      r.status_code == 200 and taxminan(kley() - k2, 5.0), (r.status_code, k2, kley()))
r = req(C, "post", f"/api/orders/{oid_m2}/restore")
check("M4 tiklash loyni AYNAN qayta yechdi", r.status_code == 200 and taxminan(kley(), k2), (r.status_code, k2, kley()))

# ══════════════════════════════════════════════════════════════
section("K. Brak — ortiqcha hisoblanmaydi")
# ══════════════════════════════════════════════════════════════
nk = nom("K")
oid_k, ik, _ = yarat([detal(nk, 10)])
iid_k = ik.get(nk)
r = qaytar(oid_k, iid_k, nk, 2, sabab="Brak")
rid_k = (js(r) or {}).get("id")
check("K1 brak -> 200, ortiqcha_miqdor NULL", r.status_code == 200 and (qaytarish(rid_k) or {"ortiqcha": 1})["ortiqcha"]
      is None, (r.status_code, r.text[:200], qaytarish(rid_k)))
check("K2 detal qolgan 10 (brak buyurtmadan chiqarmaydi)", detal_holat(iid_k) == (10.0, 0.0, 0.0, 10.0),
      detal_holat(iid_k))

# ══════════════════════════════════════════════════════════════
section("L. Pul o'zgarmaydi: ortiqcha qaytarish buyurtma summasiga tegmaydi")
# ══════════════════════════════════════════════════════════════
nl = nom("L")
oid_l, il, _ = yarat([detal(nl, 10)])
_l0 = buyurtma(oid_l)
qaytar(oid_l, il.get(nl), nl, 5)
_l1 = buyurtma(oid_l)
check("L1 jami va kelishilgan summa AYNAN", _l0 and _l1 and _l0["total"] == _l1["total"] and _l0["agreed"] == _l1["agreed"],
      (_l0, _l1))

# ══════════════════════════════════════════════════════════════
section("J. Migratsiya: eski (NULL) yozuvlar vaqt tartibida to'ldiriladi")
# ══════════════════════════════════════════════════════════════
nj = nom("J")
oid_j, ij, _ = yarat([detal(nj, 10)])
iid_j = ij.get(nj)
yetkaz(oid_j, iid_j, 2)
rj1 = (js(qaytar(oid_j, iid_j, nj, 3)) or {}).get("id")        # 2 topshirilgandan + 1 ortiqcha
yetkaz(oid_j, iid_j, 4)
rj2 = (js(qaytar(oid_j, iid_j, nj, 3)) or {}).get("id")        # 3 topshirilgandan (4 bor)
rj3 = (js(qaytar(oid_j, iid_j, nj, 2)) or {}).get("id")        # 1 topshirilgandan + 1 ortiqcha
check("J0 yozishda: 1 / 0 / 1 (oxirgisi: 1 topshirilgandan + 1 ortiqcha)",
      [(qaytarish(x) or {}).get("ortiqcha") for x in (rj1, rj2, rj3)] == [1.0, 0.0, 1.0],
      [qaytarish(x) for x in (rj1, rj2, rj3)])
# eski holatni taqlid qilish: ortiqcha_miqdor NULL, vaqtlar aniq tartibda
_s = SessionLocal()
try:
    _t0 = datetime(2026, 9, 1, 10, 0, 0)
    _dl = (_s.query(Delivery).join(DeliveryItem, DeliveryItem.delivery_id == Delivery.id)
           .filter(DeliveryItem.order_item_id == iid_j).order_by(Delivery.id).all())
    for k, d in enumerate(_dl):
        d.delivered_at = _t0 + timedelta(hours=2 * k)            # 10:00, 12:00
    for k, rid in enumerate((rj1, rj2, rj3)):
        rr = _s.get(ReturnItem, rid)
        rr.returned_at = _t0 + timedelta(hours=1 + 2 * k)        # 11:00, 13:00, 15:00
        rr.ortiqcha_miqdor = None
    _s.commit()
finally:
    _s.close()
check("J1 NULL qilingan (eski yozuv taqlidi)", [(qaytarish(x) or {}).get("ortiqcha") for x in (rj1, rj2, rj3)]
      == [None, None, None], [qaytarish(x) for x in (rj1, rj2, rj3)])
_mig = getattr(main, "_migrate_ortiqcha_qaytarish", None)
with contextlib.redirect_stdout(_quiet):
    try:
        _mig()
    except Exception as e:                 # noqa: BLE001
        print("migratsiya xatosi", e)
check("J2 migratsiya: 1 / 0 / 1 (yozishdagi bilan AYNAN)",
      [(qaytarish(x) or {}).get("ortiqcha") for x in (rj1, rj2, rj3)] == [1.0, 0.0, 1.0],
      [qaytarish(x) for x in (rj1, rj2, rj3)])
check("J3 brak yozuvi NULL qoldi", (qaytarish(rid_k) or {"ortiqcha": 1})["ortiqcha"] is None, qaytarish(rid_k))
# teskari tartib: qaytarish yuk xatidan OLDIN — hammasi ortiqcha
_s = SessionLocal()
try:
    for k, rid in enumerate((rj1, rj2, rj3)):
        rr = _s.get(ReturnItem, rid)
        rr.returned_at = _t0 - timedelta(hours=3 - k)            # 07:00, 08:00, 09:00 — yuklardan oldin
        rr.ortiqcha_miqdor = None
    _s.commit()
finally:
    _s.close()
with contextlib.redirect_stdout(_quiet):
    try:
        _mig()
    except Exception as e:                 # noqa: BLE001
        print("migratsiya xatosi", e)
check("J4 qaytarishlar yuklardan oldin — hammasi ortiqcha (3 / 3 / 2)",
      [(qaytarish(x) or {}).get("ortiqcha") for x in (rj1, rj2, rj3)] == [3.0, 3.0, 2.0],
      [qaytarish(x) for x in (rj1, rj2, rj3)])
_s = SessionLocal()
try:
    _s.get(ReturnItem, rj2).ortiqcha_miqdor = 0.5                 # qo'lda qiymat — migratsiya tegmasin
    _s.commit()
finally:
    _s.close()
with contextlib.redirect_stdout(_quiet):
    try:
        _mig()
    except Exception as e:                 # noqa: BLE001
        print("migratsiya xatosi", e)
check("J5 ikkinchi chaqiruv — to'ldirilgan yozuvlarga tegilmaydi (idempotent)",
      [(qaytarish(x) or {}).get("ortiqcha") for x in (rj1, rj2, rj3)] == [3.0, 0.5, 2.0],
      [qaytarish(x) for x in (rj1, rj2, rj3)])

# aralash: ikkitasi to'ldirilgan (0 — topshirilgandan), uchinchisi NULL va ikkala yukdan KEYIN
_s = SessionLocal()
try:
    for rid, v in ((rj1, 0.0), (rj2, 0.0)):
        _s.get(ReturnItem, rid).ortiqcha_miqdor = v
    rr = _s.get(ReturnItem, rj3)
    rr.ortiqcha_miqdor = None
    rr.returned_at = _t0 + timedelta(hours=3)                    # 13:00 — 6 topshirilgan, 6 qaytarilgan
    _s.commit()
finally:
    _s.close()
with contextlib.redirect_stdout(_quiet):
    try:
        _mig()
    except Exception as e:                 # noqa: BLE001
        print("migratsiya xatosi", e)
check("J6 aralash: to'ldirilganlar topshirilgandan olingani hisobga olinadi — uchinchisi 2 (hammasi ortiqcha)",
      [(qaytarish(x) or {}).get("ortiqcha") for x in (rj1, rj2, rj3)] == [0.0, 0.0, 2.0],
      [qaytarish(x) for x in (rj1, rj2, rj3)])

# ══════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════
_mdl = open(os.path.join(ROOT, "models.py"), encoding="utf-8").read()
check("S1 remaining_qty ortiqchani ayiradi",
      "return max(self.order_qty_normalized - self.delivered_qty - self.ortiqcha_qty, 0)" in _mdl)
_d = manba(main, "api_delete_order")
check("S2 o'chirish: qisman sharti xomashyo va loy yo'lida",
      tartibda(_d, "qisman = services.buyurtmadan_qisman_chiqqan(order)", "if qisman:",
               "return_inventory_for_order_partial", "if not qisman:", "return_loy_ingredients(db, order, planned_loy)"))
_r = manba(crud, "restore_order")
check("S3 tiklash: o'chirishdagi bilan bir xil shart (xomashyo va loy)",
      tartibda(_r, "if services.buyurtmadan_qisman_chiqqan(db_order):", "return_inventory_for_order_partial",
               "services.loy_relevant_remaining_fraction(db_order)", "if services.buyurtmadan_qisman_chiqqan(db_order) else 1.0"))
_m = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("S4 migratsiya e'londan keyin modul darajasida chaqiriladi",
      tartibda(_m, "def _migrate_ortiqcha_qaytarish", "\n_migrate_ortiqcha_qaytarish()\n"))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
