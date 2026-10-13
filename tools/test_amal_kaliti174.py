#!/usr/bin/env python3
"""
test_amal_kaliti174.py — kech144 (zip 174): AMAL KALITI (`X-Amal-Kaliti`) — yozuvchi amal takror yuborilsa QAYTA bajarilmaydi.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k173_tayyorgarlik/agentlar/tayyor/probe_takror.py`, asl kod = zip 173)
  Tayyor mahsulot sotuvi, guruh sotuvi, brak (yo'qotish), ishlab chiqarish braki, ishlab chiqarish, miqdor qo'shish, xarajat
  (Moliya / «Xarajat qo'shish» / Qarzdorlar «majburiyat to'lovi»), qaytarish, doimiy majburiyat kategoriyasi — server takror
  himoyasi YO'Q edi: bir xil so'rov ikki marta (ikki marta bosish, javob yo'qolib qayta bosish) → 2 sotuv (ombor 10 → 6), 2 brak
  (Moliya «yo'qotish» ikki marta), 2 xarajat. Endi sahifa har oyna ochilishida tasodifiy kalit yuboradi; shu korxonada shu amal uchun
  shu kalit bilan bajarilgan amal bo'lsa — QAYTA bajarilmaydi, birinchi javob qaytadi (`takror: true`, `X-Takror: 1`).
BO'LIMLAR: S sotuv; G guruh sotuv; B brak va ishlab chiqarish braki; I ishlab chiqarish va miqdor qo'shish; X xarajat va doimiy
  majburiyat; Q qaytarish; K kalit qoidalari (noto'g'ri — 400, rad etilgan amal kalitni band qilmaydi, boshqa korxona — alohida, kalitsiz —
  avvalgidek); D «Omborchi» detallari (EGASI QARORI 13.10 «Detal va miqdor» — `/api/tanlov/buyurtmalar|loyihalar/{id}/detallar`:
  «Qaytarishlar: Yaratish» bilan, narxsiz; qaytarish summasini server hisoblaydi); T eski kalitlar tozalanadi (har 500-kalitda, 30
  kundan eskilari); P parallel (PG — 3 ta bir vaqtdagi so'rov → BITTA amal); Z zavod tiklash / zaxira ro'yxatida jadval.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 173) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_amal_kaliti174.py
"""
import os
import io
import sys
import tempfile
import threading
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "amal_kaliti174_test"
_T = tempfile.mkdtemp(prefix="ak174_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'amal_kaliti174.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, Recipe, RecipeIngredient, Project, FinishedProduct, FinishedProductSale,   # noqa: E402
                    FinishedProductLoss, ExpenseTransaction, StockSource, ProductionStatus, ReturnItem, RecurringObligation)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:600]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="AK174 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "ak_admin", PAROL, UserRole.ADMIN, "AK Admin", company_id=1)
    auth.create_user(s, "ak_B_admin", PAROL, UserRole.ADMIN, "AK B Admin", company_id=2)
    auth.create_user(s, "ak_omb", PAROL, UserRole.WAREHOUSE, "AK Omborchi", company_id=1)      # tayyor «Omborchi» roli
PENO = Inventory(company_id=1, item_name="AK Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="AK Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000, category="Kimyo")
PRJ = Project(company_id=1, client_name="AK Mijoz", project_name="AK loyiha", total_budget=0, total_paid=0)
s.add_all([PENO, KLEY, PRJ])
s.flush()
REC = Recipe(company_id=1, name="AK retsept", batch_size_kg=100.0)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))


def tm(cid, nom, miqdor=10.0):
    fp = FinishedProduct(company_id=cid, name=nom, category="profil", quantity=miqdor, produced_quantity=miqdor, unit="metr",
                         unit_price=50000, cost_price=100000, source=StockSource.PRODUCED,
                         production_status=ProductionStatus.READY, is_coated=False)
    s.add(fp)
    s.flush()
    return fp.id


FP1, FP2, FP3, FP4 = tm(1, "AK profil 1"), tm(1, "AK profil 2"), tm(1, "AK profil 3"), tm(1, "AK profil 4")
FPB = tm(2, "AK B profil")
s.commit()
ID = {"PENO": PENO.id, "KLEY": KLEY.id, "PRJ": PRJ.id, "REC": REC.id}
s.close()


def kirish(user):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (user, r.status_code)
    return c


A = kirish("ak_admin")
AB = kirish("ak_B_admin")


def H(k):
    return {"X-Amal-Kaliti": k} if k else {}


def soni(model, **f):
    d = SessionLocal()
    try:
        q = d.query(model)
        for k, v in f.items():
            q = q.filter(getattr(model, k) == v)
        return q.count()
    finally:
        d.close()


def qoldiq(fp_id):
    d = SessionLocal()
    try:
        return float(d.get(FinishedProduct, fp_id).quantity)
    finally:
        d.close()


def sotuv_tana(fp, miqdor=2, narx=60000):
    return {"finished_product_id": fp, "quantity": miqdor, "unit_price": narx, "buyer_name": None, "payment_method": "naqd",
            "master_id": None, "confirm_below_cost": True}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Sotuv — o'sha kalit bilan takror so'rov IKKINCHI sotuv yozmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
k1 = "akSotuv_00000001"
r1 = A.post("/api/finished/sell", json=sotuv_tana(FP1), headers=H(k1))
r2 = A.post("/api/finished/sell", json=sotuv_tana(FP1), headers=H(k1))
check("S1 birinchi — 200, takror belgisisiz; ikkinchi — 200, `takror: true`, `X-Takror: 1`, o'sha sotuv",
      r1.status_code == 200 and not js(r1).get("takror") and r1.headers.get("X-Takror") is None
      and r2.status_code == 200 and js(r2).get("takror") is True and r2.headers.get("X-Takror") == "1"
      and js(r2).get("sale_id") == js(r1).get("sale_id"), (r1.status_code, r1.text[:200], r2.status_code, r2.text[:200]))
check("S2 bazada BITTA sotuv, qoldiq 10 → 8 (asl: 2 sotuv, 10 → 6)",
      soni(FinishedProductSale, finished_product_id=FP1) == 1 and abs(qoldiq(FP1) - 8) < 1e-9,
      (soni(FinishedProductSale, finished_product_id=FP1), qoldiq(FP1)))
r3 = A.post("/api/finished/sell", json=sotuv_tana(FP1), headers=H("akSotuv_00000002"))
check("S3 YANGI kalit (yangi oyna) — yangi sotuv (ataylab ikkinchi sotuv mumkin), qoldiq 6",
      r3.status_code == 200 and not js(r3).get("takror") and soni(FinishedProductSale, finished_product_id=FP1) == 2
      and abs(qoldiq(FP1) - 6) < 1e-9, (r3.status_code, qoldiq(FP1)))
r4 = A.post("/api/finished/sell", json=sotuv_tana(FP1))
r5 = A.post("/api/finished/sell", json=sotuv_tana(FP1))
check("S4 kalitsiz (API / eski sahifa) — avvalgidek: ikki so'rov ikki sotuv", r4.status_code == 200 and r5.status_code == 200
      and soni(FinishedProductSale, finished_product_id=FP1) == 4 and abs(qoldiq(FP1) - 2) < 1e-9, (r4.status_code, r5.status_code))
r6 = A.post("/api/finished/sell", json=sotuv_tana(FP1, miqdor=50), headers=H("akSotuv_00000003"))
r7 = A.post("/api/finished/sell", json=sotuv_tana(FP1, miqdor=1), headers=H("akSotuv_00000003"))
check("S5 rad etilgan sotuv (qoldiqdan ko'p — 400) kalitni BAND QILMAYDI: o'sha kalit bilan to'g'ri so'rov — bajariladi",
      r6.status_code == 400 and r7.status_code == 200 and not js(r7).get("takror") and abs(qoldiq(FP1) - 1) < 1e-9,
      (r6.status_code, r7.status_code, r7.text[:200], qoldiq(FP1)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. Guruh sotuv (savatcha)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
gt = {"items": [{"finished_product_id": FP2, "quantity": 1, "unit_price": 70000}], "buyer_name": "AK xaridor", "payment_method": "naqd"}
g1 = A.post("/api/finished/sell-batch", json=gt, headers=H("akGuruh_00000001"))
g2 = A.post("/api/finished/sell-batch", json=gt, headers=H("akGuruh_00000001"))
check("G1 guruh sotuv takrori — `takror: true`, bazada BITTA sotuv, qoldiq 10 → 9",
      g1.status_code == 200 and g2.status_code == 200 and js(g2).get("takror") is True
      and soni(FinishedProductSale, finished_product_id=FP2) == 1 and abs(qoldiq(FP2) - 9) < 1e-9,
      (g1.status_code, g2.status_code, g2.text[:200], qoldiq(FP2)))
g3 = A.post("/api/finished/sell", json=sotuv_tana(FP2, miqdor=1), headers=H("akGuruh_00000001"))
check("G2 o'sha kalit BOSHQA amalda (oddiy sotuv) — alohida (kalit amal ichida noyob)",
      g3.status_code == 200 and not js(g3).get("takror") and soni(FinishedProductSale, finished_product_id=FP2) == 2, g3.text[:200])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Brak (yo'qotish) va ishlab chiqarish braki")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
lt = {"finished_product_id": FP3, "quantity": 1, "reason": None, "brak_sabab": "boshqa"}
b1 = A.post("/api/finished/loss", json=lt, headers=H("akBrak_000000001"))
b2 = A.post("/api/finished/loss", json=lt, headers=H("akBrak_000000001"))
check("B1 brak takrori — `takror: true`, BITTA brak yozuvi, qoldiq 10 → 9 (asl: 2 yozuv, Moliya ikki marta)",
      b1.status_code == 200 and b2.status_code == 200 and js(b2).get("takror") is True
      and soni(FinishedProductLoss, finished_product_id=FP3) == 1 and abs(qoldiq(FP3) - 9) < 1e-9,
      (b1.status_code, b1.text[:200], b2.status_code, b2.text[:200], qoldiq(FP3)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("I. Ishlab chiqarish va miqdor qo'shish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
pt = {"name": "AK TM ishlab", "category": "profil", "is_coated": True, "penoplast_id": ID["PENO"], "price_per_m3": None,
      "unit_price": 100000, "recipe_id": ID["REC"], "notes": "ak174", "width": 10, "thickness": 10, "length": 10, "quantity": 5,
      "loy_kg": 5}
n0 = soni(FinishedProduct, company_id=1)
d = SessionLocal()
kley0 = float(d.get(Inventory, ID["KLEY"]).stock_quantity)
d.close()
p1 = A.post("/api/finished/produce", json=pt, headers=H("akIshlab_0000001"))
p2 = A.post("/api/finished/produce", json=pt, headers=H("akIshlab_0000001"))
d = SessionLocal()
kley1 = float(d.get(Inventory, ID["KLEY"]).stock_quantity)
d.close()
check("I1 ishlab chiqarish takrori — `takror: true`, BITTA partiya, loy xomashyosi BIR marta yechildi",
      p1.status_code == 200 and p2.status_code == 200 and js(p2).get("takror") is True and soni(FinishedProduct, company_id=1) == n0 + 1
      and abs((kley0 - kley1) - 5) < 1e-6, (p1.status_code, p1.text[:200], p2.status_code, kley0, kley1))
_yangi = js(p1).get("product_id") or js(p1).get("id") or js(p1).get("finished_product_id")
q0 = qoldiq(_yangi) if _yangi else None
a1 = A.post(f"/api/finished/{_yangi}/add", json={"quantity": 2}, headers=H("akQoshish_000001"))
a2 = A.post(f"/api/finished/{_yangi}/add", json={"quantity": 2}, headers=H("akQoshish_000001"))
check("I2 miqdor qo'shish takrori — `takror: true`, miqdor BIR marta +2",
      a1.status_code == 200 and a2.status_code == 200 and js(a2).get("takror") is True and q0 is not None
      and abs(qoldiq(_yangi) - (q0 + 2)) < 1e-9, (a1.status_code, a1.text[:200], a2.status_code, q0, _yangi and qoldiq(_yangi)))
a3 = A.post(f"/api/finished/{FP4}/add", json={"quantity": 1}, headers=H("akQoshish_000001"))
check("I3 o'sha kalit BOSHQA mahsulotga — alohida amal (bajariladi)",
      a3.status_code in (200, 400) and not js(a3).get("takror"), (a3.status_code, a3.text[:200]))
pb = {"finished_product_id": _yangi, "brak_qty": 1, "notes": None, "brak_sabab": "boshqa"}
b3 = A.post("/api/finished/production-brak", json=pb, headers=H("akIshBrak_000001"))
b4 = A.post("/api/finished/production-brak", json=pb, headers=H("akIshBrak_000001"))
check("I4 ishlab chiqarish braki takrori — `takror: true`, BITTA yozuv (brak xomashyosi bir marta yechildi)",
      b3.status_code == 200 and b4.status_code == 200 and js(b4).get("takror") is True
      and soni(FinishedProductLoss, finished_product_id=_yangi) == 1, (b3.status_code, b3.text[:200], b4.status_code, b4.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("X. Xarajat va doimiy majburiyat kategoriyasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
tt = {"date": "2026-10-13T00:00:00", "category": "ijara_ak174", "amount": 150000, "notes": "To'lov (Qarzdorlar sahifasidan)"}
x1 = A.post("/api/finance/transactions", json=tt, headers=H("akXarajat_000001"))
x2 = A.post("/api/finance/transactions", json=tt, headers=H("akXarajat_000001"))
check("X1 xarajat takrori — `takror: true`, o'sha id, BITTA qator (asl: 2 × 150 000)",
      x1.status_code == 200 and x2.status_code == 200 and js(x2).get("takror") is True and js(x2).get("id") == js(x1).get("id")
      and soni(ExpenseTransaction, category="ijara_ak174") == 1, (x1.status_code, x1.text[:200], x2.status_code, x2.text[:200]))
x3 = A.post("/api/finance/transactions", json=dict(tt, amount=0), headers=H("akXarajat_000002"))
x4 = A.post("/api/finance/transactions", json=tt, headers=H("akXarajat_000002"))
check("X2 rad etilgan xarajat (summa 0 — 400) kalitni band qilmaydi — o'sha kalit bilan to'g'risi yoziladi",
      x3.status_code == 400 and x4.status_code == 200 and not js(x4).get("takror") and soni(ExpenseTransaction, category="ijara_ak174") == 2,
      (x3.status_code, x4.status_code))
mp = {"category": "ak_kat_1", "label": "AK ijara", "monthly_target": "3000000", "icon": "🏠", "due_day": "5"}
m1 = A.post("/api/obligations/recurring", params=mp, headers=H("akKategor_000001"))
m2 = A.post("/api/obligations/recurring", params=dict(mp, category="ak_kat_2"), headers=H("akKategor_000001"))
check("X3 «+ Kategoriya» ikki marta (sahifa har bosishda yangi kod beradi) — o'sha kalit: BITTA kategoriya",
      m1.status_code == 200 and m2.status_code == 200 and js(m2).get("takror") is True
      and soni(RecurringObligation, company_id=1) == 1, (m1.status_code, m1.text[:200], m2.status_code, m2.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Qaytarish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ro = A.post("/api/orders?confirm_shortage=true", json={"project_id": ID["PRJ"], "order_type": "product", "items": [
    {"name": "AK qaytarish detali", "category": "panel", "width": 50, "thickness": 5, "quantity": 5, "unit_price": 10000,
     "is_coated": False}]})
OID = js(ro).get("id")
OI = (js(ro).get("items") or [{}])[0].get("id")
A.post("/api/deliveries", json={"order_id": OID, "items": [{"order_item_id": OI, "quantity": 5}], "received_by": None, "notes": None,
                                "transport_carrier": None, "transport_cost": 0, "transport_payer": "none", "payment_amount": None,
                                "payment_method": "naqd"})
qt = {"order_id": OID, "order_item_id": OI, "item_name": "AK qaytarish detali", "quantity": 1, "unit": "metr", "reason": "Ortiqcha",
      "refund_amount": 0, "to_stock": False, "notes": None, "coating_applied": False}
q1 = A.post("/api/returns", json=qt, headers=H("akQaytar_0000001"))
q2 = A.post("/api/returns", json=qt, headers=H("akQaytar_0000001"))
check("Q1 qaytarish takrori — `takror: true`, o'sha id, BITTA qaytarish yozuvi",
      q1.status_code == 200 and q2.status_code == 200 and js(q2).get("takror") is True and js(q2).get("id") == js(q1).get("id")
      and soni(ReturnItem, order_id=OID) == 1, (ro.status_code, q1.status_code, q1.text[:200], q2.status_code, q2.text[:200]))
check("Q2 birinchi javob shakli avvalgidek (qaytarish maydonlari — id, order_id, quantity, reason)",
      all(k in js(q1) for k in ("id", "order_id", "quantity", "reason")), js(q1))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Kalit qoidalari va korxona chegarasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_yomon = {}
for k in ("qisqa7x", "bo'sh joy bor", "x" * 65, "калит123456"):
    try:
        rr = A.post("/api/finished/sell", json=sotuv_tana(FP4, miqdor=1), headers={"X-Amal-Kaliti": k})
        _yomon[k[:12]] = rr.status_code
    except Exception as e:                 # noqa: BLE001 — sarlavhada ASCII bo'lmagan belgi (mijoz kutubxonasi rad etadi)
        _yomon[k[:12]] = type(e).__name__
check("K1 noto'g'ri kalit (8 dan qisqa, bo'shliq / apostrof, 64 dan uzun) — 400, sotuv YO'Q",
      all(v == 400 or v == "UnicodeEncodeError" for v in _yomon.values()) and soni(FinishedProductSale, finished_product_id=FP4) == 0,
      (_yomon, soni(FinishedProductSale, finished_product_id=FP4)))
kb1 = AB.post("/api/finished/sell", json=sotuv_tana(FPB, miqdor=1), headers=H(k1))
check("K2 boshqa korxonada o'sha kalit — o'z sotuvi (takror EMAS)",
      kb1.status_code == 200 and not js(kb1).get("takror") and soni(FinishedProductSale, finished_product_id=FPB) == 1, kb1.text[:200])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. «Omborchi» — qaytarish / brak oynasi detallari (EGASI QARORI «Detal va miqdor»)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
AO = kirish("ak_omb")
d1 = AO.get(f"/api/tanlov/buyurtmalar/{OID}/detallar")
_i1 = (js(d1).get("items") or [{}])[0]
check("D1 Omborchi buyurtma detallari — 200: nom, miqdor, birlik; NARX YO'Q (asl: `/api/orders/{id}` — 403, «detal yo'q»)",
      d1.status_code == 200 and _i1.get("id") == OI and _i1.get("name") == "AK qaytarish detali" and "order_qty_normalized" in _i1
      and "delivery_unit" in _i1 and not any(k in _i1 for k in ("refund_price_per_unit", "unit_price", "total_price",
                                                                 "price_per_unit_final", "cost_price_per_unit")),
      (d1.status_code, d1.text[:300]))
check("D2 eski marshrutlar Omborchiga avvalgidek yopiq (`/api/orders/{id}` — «Buyurtmalar: Ko'rish», `/api/projects/{id}/items` —"
      " «Loyihalar: Ko'rish») — sahifa ularni endi chaqirmaydi",
      AO.get(f"/api/orders/{OID}").status_code == 403 and AO.get(f"/api/projects/{ID['PRJ']}/items").status_code == 403)
d2 = A.get(f"/api/tanlov/buyurtmalar/{OID}/detallar")
_i2 = (js(d2).get("items") or [{}])[0]
check("D3 Admin (tannarx ruxsati bor) — 1 birlik qaytarish narxi ham (10 000 — kelishilgan)",
      d2.status_code == 200 and abs(float(_i2.get("refund_price_per_unit") or 0) - 10000) < 0.01, d2.text[:300])
d3 = AO.get(f"/api/tanlov/loyihalar/{ID['PRJ']}/detallar")
_i3 = [x for x in (js(d3).get("items") or []) if x.get("item_id") == OI]
check("D4 Omborchi loyiha detallari — 200, buyurtma raqami / detal / miqdor; narxsiz",
      d3.status_code == 200 and len(_i3) == 1 and _i3[0].get("order_id") == OID and _i3[0].get("order_number")
      and not any("price" in k for k in _i3[0]), (d3.status_code, d3.text[:300]))
rq = AO.post("/api/returns", json=dict(qt, quantity=1, refund_amount=0), headers=H("akOmbQaytar_0001"))
check("D5 Omborchi qaytarishi — narx yubormasdan (0): summani server hisoblaydi (1 × 10 000)",
      rq.status_code == 200 and abs(float(js(rq).get("refund_amount") or 0) - 10000) < 0.01, (rq.status_code, rq.text[:300]))
_rd = A.post("/api/orders?confirm_shortage=true", json={"project_id": ID["PRJ"], "order_type": "product", "is_draft": True, "items": [
    {"name": "AK qoralama", "category": "panel", "width": 50, "thickness": 5, "quantity": 1, "unit_price": 1000, "is_coated": False}]})
_DR = js(_rd).get("id")
_rb = AB.post("/api/projects", json={"client_name": "AK B mijoz", "project_name": "AK B loyiha"})
_PB = js(_rb).get("id")
check("D6 qoralama buyurtma / boshqa korxona buyurtmasi / yo'q buyurtma — 404 (tanlov ro'yxati qoidasi)",
      _DR is not None and AO.get(f"/api/tanlov/buyurtmalar/{_DR}/detallar").status_code == 404
      and AB.get(f"/api/tanlov/buyurtmalar/{OID}/detallar").status_code == 404
      and AO.get("/api/tanlov/buyurtmalar/999999/detallar").status_code == 404, (_rd.status_code, _DR))
check("D7 boshqa korxona loyihasi / yo'q loyiha — 404",
      AB.get(f"/api/tanlov/loyihalar/{ID['PRJ']}/detallar").status_code == 404
      and AO.get("/api/tanlov/loyihalar/999999/detallar").status_code == 404
      and _PB is not None and AO.get(f"/api/tanlov/loyihalar/{_PB}/detallar").status_code == 404, (_rb.status_code, _PB))

import models as _models                          # noqa: E402
AmalKaliti = getattr(_models, "AmalKaliti", None)   # asl kodda (zip 173) yo'q — test qulamasdan yiqiladi
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Eski kalitlar tozalanadi — jadval cheksiz o'smaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_t_ok = False
_t_x = ""
if AmalKaliti is not None:
    from datetime import datetime as _dt, timedelta as _td
    from sqlalchemy import text as _sql
    d = SessionLocal()
    try:
        d.add_all([AmalKaliti(company_id=1, amal_turi="sinov_eski", sorov_kaliti="akEski_00000001", javob_json="{}",
                              created_at=_dt.utcnow() - _td(days=40)),
                   AmalKaliti(company_id=2, amal_turi="sinov_eski", sorov_kaliti="akEski_00000002", javob_json="{}",
                              created_at=_dt.utcnow() - _td(days=31)),
                   AmalKaliti(company_id=1, amal_turi="sinov_yangi", sorov_kaliti="akYangi_0000001", javob_json="{}",
                              created_at=_dt.utcnow() - _td(days=2))])
        d.commit()
        # keyingi kalit qatori id si 500 bo'lsin (tozalash shu kalitda ishga tushadi)
        if PG_URL:
            d.execute(_sql("SELECT setval(pg_get_serial_sequence('amal_kalitlari', 'id'), 499)"))
        else:
            d.add(AmalKaliti(id=499, company_id=1, amal_turi="sinov_bosh", sorov_kaliti="akBosh_00000499", javob_json="{}"))
        d.commit()
    except Exception as e:                 # noqa: BLE001
        _t_x = f"{type(e).__name__}: {e}"
    finally:
        d.close()
rt = A.post("/api/finished/sell", json=sotuv_tana(FP3, miqdor=1), headers=H("akTozala_0000001"))
d = SessionLocal()
try:
    _qolgan = sorted(r.sorov_kaliti for r in d.query(AmalKaliti).filter(AmalKaliti.amal_turi.in_(["sinov_eski", "sinov_yangi"]))) if AmalKaliti else []
    _yangi_id = (d.query(AmalKaliti.id).filter(AmalKaliti.sorov_kaliti == "akTozala_0000001").scalar()) if AmalKaliti else None
finally:
    d.close()
check("T1 500-kalit bilan sotuv — o'tdi; SHU korxonaning 30 kundan eski kaliti o'chdi, boshqa korxonaniki tegilmadi (tenant), "
      "yangisi (2 kunlik) qoldi",
      rt.status_code == 200 and _yangi_id == 500 and _qolgan == ["akEski_00000002", "akYangi_0000001"],
      (rt.status_code, _yangi_id, _qolgan, _t_x))
_n_toz = _soni_toz = None
if AmalKaliti is not None and hasattr(crud, "amal_kalitlari_tozala"):
    d2 = SessionLocal()
    try:
        # kun=-1 — hammasi «eski» (vaqt chegarasi ertaga); har korxona alohida
        _n_toz = (crud.amal_kalitlari_tozala(d2, 1, kun=-1), crud.amal_kalitlari_tozala(d2, 2, kun=-1))
    except TypeError as e:                 # asl kod (korxonasiz imzo)
        _n_toz = f"TypeError: {e}"
    finally:
        d2.close()
    _soni_toz = soni(AmalKaliti)
rt2 = A.post("/api/finished/sell", json=sotuv_tana(FP3, miqdor=1), headers=H("akTozala_0000002"))
check("T2 `amal_kalitlari_tozala(korxona, kun=-1)` — o'sha korxonanikini o'chiradi, sonini qaytaradi (1-korxona ≥ 2, 2-korxona ≥ 1); "
      "keyingi kalitli amal ishlaydi (kalit yoziladi)",
      isinstance(_n_toz, tuple) and _n_toz[0] >= 2 and _n_toz[1] >= 1 and _soni_toz == 0 and rt2.status_code == 200
      and soni(AmalKaliti) == 1,
      (_n_toz, _soni_toz, rt2.status_code, AmalKaliti is not None and soni(AmalKaliti)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Jadval — zavod tiklash / zaxira ro'yxatida")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("Z1 `amal_kalitlari` — `crud._reset_table_order` da (zavod tiklash o'chiradi, zaxira o'z ichiga oladi)",
      AmalKaliti is not None and AmalKaliti in crud._reset_table_order(), [m.__name__ for m in crud._reset_table_order()][-5:])
check("Z2 bajarilgan amallar kalitlari yozilgan (korxona 1; T2 dan keyin — bitta)", AmalKaliti is not None and soni(AmalKaliti, company_id=1) == 1,
      AmalKaliti is not None and soni(AmalKaliti, company_id=1))

if PG_URL:
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("P. Parallel (PG) — o'sha kalit bilan 3 ta bir vaqtdagi so'rov")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    # Poyga ANIQ bo'lsin (mut174 M03p saboq: kirish (parol xeshi) har oqimda ~0,2 s — so'rovlar ketma-ket kelib, ikkinchisi birinchining
    # SAQLANGAN kalitini ko'rardi, noyoblik to'qnashuvi yo'li sinalmasdi): avval 3 mijoz kiradi, so'rovlar `Barrier` bilan bir vaqtda
    # ketadi, sotuvning o'zi 0,6 s sekinlashtiriladi (birinchi so'rov kalit qatorini SAQLAMASDAN ushlab turadi) — qolgan ikkitasi
    # noyoblik indeksida kutadi va IntegrityError → birinchi javob (`takror`) yo'lidan o'tadi.
    import time as _time
    d = SessionLocal()
    d.query(FinishedProduct).filter(FinishedProduct.id == FP4).update({"quantity": 10.0})
    d.commit()
    d.close()
    n_s = soni(FinishedProductSale, finished_product_id=FP4)
    natija = []
    _mijozlar = [kirish("ak_admin") for _ in range(3)]
    _tosiq = threading.Barrier(3)
    _asl_sotuv = crud.sell_finished_product

    def _sekin_sotuv(*a, **k):
        _time.sleep(0.6)
        return _asl_sotuv(*a, **k)

    def _ish(c):
        _tosiq.wait(30)
        rr = c.post("/api/finished/sell", json=sotuv_tana(FP4, miqdor=1), headers=H("akParallel_00001"))
        natija.append((rr.status_code, js(rr).get("sale_id"), bool(js(rr).get("takror"))))

    crud.sell_finished_product = _sekin_sotuv
    try:
        _ip = [threading.Thread(target=_ish, args=(c,)) for c in _mijozlar]
        for t in _ip:
            t.start()
        for t in _ip:
            t.join(90)
    finally:
        crud.sell_finished_product = _asl_sotuv
    check("P1 3 parallel so'rov (bir vaqtda, birinchisi kalitni saqlamasdan ushlab turadi) → BITTA sotuv (qolganlari takror, o'sha"
          " sale_id), qoldiq 10 → 9",
          len(natija) == 3 and all(x[0] == 200 for x in natija) and len({x[1] for x in natija}) == 1
          and sum(1 for x in natija if not x[2]) == 1 and soni(FinishedProductSale, finished_product_id=FP4) == n_s + 1
          and abs(qoldiq(FP4) - 9) < 1e-9, (natija, qoldiq(FP4)))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
