#!/usr/bin/env python3
"""
test_tm_tannarx.py — 5-bo'lim 47-band darvozasi (kech59, 2026-09-24): TAYYOR MAHSULOT 1 birlik tannarxi.

NIMA UCHUN (asl kod `35ec712` da SQLite da O'LCHANGAN — `work/probe59_47.py`)
-------------------------------------------------------------------------
Tayyor mahsulot (TM) 100 m, 1 m = penoplast 0.01 m3 (5 000) + loy 0.5 kg (2 600) = 7 600 so'm; keyin
xomashyo narxi x2:
  * K59-1: "Tayyor mahsulotdan" olingan 10 m detalli buyurtma foydasi `cost_price / produced_quantity`
    bilan — tan narx 76 000 o'rniga 68 400, boshqa buyurtma o'sha TM dan olgach 53 200 ga SILJIRDI.
  * K59-2: shu detaldan 5 m omborga qaytsa — qaytgan TM tannarxi 76 000 (JORIY narx), to'g'risi 38 000.
  * K59-4: TM dan 10 m sotuv tannarxi 152 000 (JORIY), ishlab chiqarilgani 76 000; TM qoldig'i 608 000
    o'rniga 532 000 (keyingi olishlar ham joriy narxda).
  Sabab: `crud._fp_stable_unit_cost` `unit_cost_stable` bo'lmasa penoplast / loyning JORIY narxidan
  hisoblaydi; oddiy (MRP emas) ishlab chiqarishda `unit_cost_stable` yozilmasdi.

YECHIM (texnik — Claude; 32-band qarori "ishlatilgan paytdagi narxda muzlatilsin" bilan bir xil):
  * ishlab chiqarish — `unit_cost_stable = total_cost / qty`; qo'shimcha ishlab chiqarish — og'irlikli
    o'rtacha; qaytgan mahsulot — muzlagan qaytarish tannarxi (qo'shilsa og'irlikli, qaytarish o'chirilsa
    teskarisi);
  * buyurtma foydasi — muzlagan birlik tannarx (`_fp_stable_unit_cost`), bo'lmasa eski formula;
  * `main._migrate_tm_birlik_tannarx` — bo'sh (NULL) qatorlar BUGUNGI qiymatda (33 / 37-band "A" qoidasi).
  Qoldiq chegara (hujjat 56-band): TM ga keyin YANGI partiya qo'shilsa o'rtacha o'zgaradi va avval
  olingan detal foydasi / qaytarishi yangi o'rtachada baholanadi — bu test uni tekshirmaydi.

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_tm_tannarx.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tm_tannarx.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tm_tannarx_test"
_DB = os.path.join(tempfile.gettempdir(), "tm_tannarx_test.db")

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
from models import (                               # noqa: E402
    UserRole, Project, Inventory, Recipe, RecipeIngredient, ReturnItem, FinishedProduct,
    FinishedProductSale, StockSource, ProductionStatus,
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


def tartibda(src, *qismlar):
    """Qismlar src ichida AYNAN shu tartibda uchraydimi (find — topilmasa False)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TT_admin", "Parol123!", UserRole.ADMIN, "TT Admin", company_id=1)
PRJS = [Project(company_id=1, client_name=f"TT Mijoz {i}", project_name=f"TT loyiha {i}", total_budget=0,
                total_paid=0) for i in range(4)]
PENO = Inventory(company_id=1, item_name="TT Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TT Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000,
                 category="Kimyo")
AKR = Inventory(company_id=1, item_name="TT Akril", unit="kg", stock_quantity=100_000, price_per_unit=10_000,
                category="Kimyo")
_db.add_all(PRJS + [PENO, KLEY, AKR])
_db.commit()
R1 = Recipe(company_id=1, name="TT R1", batch_size_kg=100.0)
_db.add(R1)
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0)])
_db.commit()
ID = dict(PENO=PENO.id, KLEY=KLEY.id, AKR=AKR.id, R1=R1.id)
PRJ = [p.id for p in PRJS]
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("TT_admin")
if _s1 != 302:
    print(f"LOGIN BO'LMADI: {_s1}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom():
    _n[0] += 1
    return f"TT_D{_n[0]}"


def narx(k):
    d = SessionLocal()
    try:
        d.get(Inventory, ID["PENO"]).price_per_unit = 500_000 * k
        d.get(Inventory, ID["KLEY"]).price_per_unit = 2_000 * k
        d.get(Inventory, ID["AKR"]).price_per_unit = 10_000 * k
        d.commit()
    finally:
        d.close()


def tm(fid):
    """(quantity, cost_price, unit_cost_stable yoki None, _fp_stable_unit_cost)"""
    d = SessionLocal()
    try:
        f = d.get(FinishedProduct, fid)
        if f is None:
            return (None, None, None, None)
        ucs = float(f.unit_cost_stable) if f.unit_cost_stable is not None else None
        return (float(f.quantity or 0), float(f.cost_price or 0), ucs, crud._fp_stable_unit_cost(d, f))
    finally:
        d.close()


def buyurtma(fid, uzunlik, prj):
    t = {"project_id": prj, "order_type": "product", "recipe_id": ID["R1"], "loy_kg": 0,
         "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": uzunlik,
                    "quantity": 1, "unit_price": 20_000, "is_coated": True, "penoplast_id": ID["PENO"],
                    "finished_product_id": fid}]}
    r = req(C, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
    d = js(r) or {}
    it = (d.get("items") or [{}])[0] if isinstance(d, dict) else {}
    return r.status_code, d.get("id") if isinstance(d, dict) else None, it.get("id"), it.get("name")


def tan(oid):
    d = js(req(C, "get", f"/api/orders/{oid}/profit")) or {}
    return d.get("tan_narxi")


def qaytar(oid, iid, nomi, miqdor):
    r = req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": iid, "item_name": nomi,
                                             "quantity": miqdor, "unit": "metr", "reason": "Ortiqcha",
                                             "refund_amount": 0, "to_stock": True})
    d = js(r) or {}
    rid = d.get("id") if (r.status_code == 200 and isinstance(d, dict)) else None
    fp = sc = None
    if rid:
        s = SessionLocal()
        try:
            ri = s.get(ReturnItem, rid)
            fp, sc = ri.finished_product_id, (float(ri.stock_cost) if ri.stock_cost is not None else None)
        finally:
            s.close()
    return r.status_code, rid, fp, sc


# ══════════════════════════════════════════════════════════════
section("A. Ishlab chiqarish (narx x1) — tannarx muzlaydi")
# ══════════════════════════════════════════════════════════════
r = req(C, "post", "/api/finished/produce", json={"name": "TT TM profil", "category": "profil", "width": 20,
                                                   "thickness": 10, "length": 100, "is_coated": True,
                                                   "penoplast_id": ID["PENO"], "unit_price": 0, "loy_kg": 50,
                                                   "recipe_id": ID["R1"]})
d = js(r) or {}
FP = d.get("product_id")
check("A0 ishlab chiqarish 200, tannarx 760 000 (penoplast 500 000 + loy 260 000)",
      r.status_code == 200 and taxminan(d.get("total_cost"), 760_000), f"{r.status_code} {r.text[:300]}")
check("A1 unit_cost_stable = 7 600 (760 000 / 100 m) — ishlab chiqarilgan paytdagi narx",
      taxminan(tm(FP)[2], 7_600), tm(FP))
r = req(C, "post", f"/api/finished/{FP}/complete")
check("A2 'Tayyor' 200", r.status_code == 200, r.text[:200])

# ══════════════════════════════════════════════════════════════
section("B. Buyurtma TM dan 10 m oladi (x1)")
# ══════════════════════════════════════════════════════════════
s, O1, I1, N1 = buyurtma(FP, 10, PRJ[0])
check("B0 buyurtma 200", s == 200 and O1, s)
check("B1 TM 90 m / 684 000", taxminan(tm(FP)[0], 90) and taxminan(tm(FP)[1], 684_000), tm(FP))
check("B2 buyurtma tan narxi 76 000 (10 x 7 600; asl: 68 400 — cost_price / produced)", taxminan(tan(O1), 76_000),
      tan(O1))

# ══════════════════════════════════════════════════════════════
section("C. Narx x2 — TM tannarxi va buyurtma foydasi O'ZGARMAYDI")
# ══════════════════════════════════════════════════════════════
narx(2)
check("C1 _fp_stable_unit_cost hali 7 600 (asl: 15 200 — joriy narx)", taxminan(tm(FP)[3], 7_600), tm(FP))
check("C2 buyurtma tan narxi hali 76 000", taxminan(tan(O1), 76_000), tan(O1))

# ══════════════════════════════════════════════════════════════
section("D. Narx x2 da 5 m omborga qaytadi (K59-2)")
# ══════════════════════════════════════════════════════════════
s, R_D, RFP, SC = qaytar(O1, I1, N1, 5)
check("D0 qaytarish 200, yangi qaytgan TM", s == 200 and RFP and RFP != FP, (s, RFP))
check("D1 qaytarish tannarxi 38 000 (5 x 7 600; asl: 76 000 — joriy)", taxminan(SC, 38_000), SC)
check("D2 qaytgan TM: 5 m / 38 000, birlik 7 600 muzlagan", taxminan(tm(RFP)[0], 5) and taxminan(tm(RFP)[1], 38_000)
      and taxminan(tm(RFP)[2], 7_600), tm(RFP))
check("D3 manba TM o'zgarmadi (90 / 684 000)", taxminan(tm(FP)[0], 90) and taxminan(tm(FP)[1], 684_000), tm(FP))

# ══════════════════════════════════════════════════════════════
section("E. Narx x2 da ikkinchi buyurtma 10 m oladi (K59-1 siljishi)")
# ══════════════════════════════════════════════════════════════
s, O2, I2, N2 = buyurtma(FP, 10, PRJ[1])
check("E0 buyurtma 200", s == 200 and O2, s)
check("E1 manba TM 80 / 608 000 (asl: 532 000)", taxminan(tm(FP)[0], 80) and taxminan(tm(FP)[1], 608_000), tm(FP))
check("E2 BIRINCHI buyurtma foydasi SILJIMADI — 76 000 (asl: 53 200)", taxminan(tan(O1), 76_000), tan(O1))
check("E3 ikkinchi buyurtma tan narxi 76 000 (asl: 53 200)", taxminan(tan(O2), 76_000), tan(O2))

# ══════════════════════════════════════════════════════════════
section("F. Ikkinchi buyurtma o'chiriladi (x2)")
# ══════════════════════════════════════════════════════════════
r = req(C, "delete", f"/api/orders/{O2}")
check("F1 o'chirish 200, TM 90 / 684 000", r.status_code == 200 and taxminan(tm(FP)[0], 90)
      and taxminan(tm(FP)[1], 684_000), (r.status_code, tm(FP)))

# ══════════════════════════════════════════════════════════════
section("G. Narx x2 da TM dan 10 m sotuv (K59-4)")
# ══════════════════════════════════════════════════════════════
r = req(C, "post", "/api/finished/sell", json={"finished_product_id": FP, "quantity": 10, "unit_price": 30_000,
                                                "buyer_name": "TT xaridor", "confirm_below_cost": True})
d = js(r) or {}
_s = SessionLocal()
try:
    _sot = _s.query(FinishedProductSale).order_by(FinishedProductSale.id.desc()).first()
    _sot_cost = float(_sot.cost_amount) if _sot is not None and _sot.cost_amount is not None else None
finally:
    _s.close()
check("G1 sotuv tannarxi 76 000 (asl: 152 000 — joriy)", r.status_code == 200 and taxminan(_sot_cost, 76_000),
      (r.status_code, _sot_cost, r.text[:200]))
check("G2 sotuv foydasi 224 000 (300 000 - 76 000)", taxminan(d.get("profit"), 224_000), d)
check("G3 TM 80 / 608 000", taxminan(tm(FP)[0], 80) and taxminan(tm(FP)[1], 608_000), tm(FP))

# ══════════════════════════════════════════════════════════════
section("H. Narx x2 da +20 m qo'shimcha ishlab chiqarish — og'irlikli o'rtacha")
# ══════════════════════════════════════════════════════════════
r = req(C, "post", f"/api/finished/{FP}/add", json={"quantity": 20})
check("H0 qo'shish 200", r.status_code == 200, r.text[:300])
# yangi 20 m: penoplast 0.2 m3 x 1 000 000 = 200 000 + loy 10 kg x 10 400 = 104 000 -> 304 000
check("H1 birlik (7 600 x 80 + 304 000) / 100 = 9 120 (asl: joriy 15 200)", taxminan(tm(FP)[2], 9_120), tm(FP))
check("H2 TM 100 m / 912 000 (= birlik x qoldiq)", taxminan(tm(FP)[0], 100) and taxminan(tm(FP)[1], 912_000), tm(FP))
narx(3)
check("H3 narx x3 — birlik hali 9 120", taxminan(tm(FP)[3], 9_120), tm(FP))
narx(2)

# ══════════════════════════════════════════════════════════════
section("I. Qaytgan TM ga yana qaytarish qo'shiladi va o'chiriladi")
# ══════════════════════════════════════════════════════════════
s, R_I, RFP2, SC2 = qaytar(O1, I1, N1, 2)
check("I0 ikkinchi qaytarish 200, o'sha qaytgan TM ga qo'shildi", s == 200 and RFP2 == RFP, (s, RFP2, RFP))
check("I1 qaytarish tannarxi 2 x 9 120 = 18 240 (manba TM o'rtachasi)", taxminan(SC2, 18_240), SC2)
check("I2 qaytgan TM birlik (38 000 + 18 240) / 7 = 8 034.2857", taxminan(tm(RFP)[2], 56_240 / 7),
      tm(RFP))
r = req(C, "delete", f"/api/returns/{R_I}")
check("I3 qaytarish o'chirildi 200 — qaytgan TM 5 m / 38 000, birlik 7 600 ga QAYTDI",
      r.status_code == 200 and taxminan(tm(RFP)[0], 5) and taxminan(tm(RFP)[1], 38_000)
      and taxminan(tm(RFP)[2], 7_600), (r.status_code, tm(RFP), r.text[:200]))

# ══════════════════════════════════════════════════════════════
section("K. Qaytgan TM butunlay buyurtmaga olinadi")
# ══════════════════════════════════════════════════════════════
s, O3, I3, N3 = buyurtma(RFP, 5, PRJ[2])
check("K0 buyurtma 200, qaytgan TM 0 m / 0", s == 200 and O3 and taxminan(tm(RFP)[0], 0)
      and taxminan(tm(RFP)[1], 0), (s, tm(RFP)))
check("K1 buyurtma tan narxi 38 000 (asl: 0 — cost_price tugagan)", taxminan(tan(O3), 38_000), tan(O3))
r = req(C, "delete", f"/api/orders/{O3}")
check("K2 o'chirish 200 — qaytgan TM 5 m / 38 000", r.status_code == 200 and taxminan(tm(RFP)[0], 5)
      and taxminan(tm(RFP)[1], 38_000), (r.status_code, tm(RFP)))

# ══════════════════════════════════════════════════════════════
section("J. Migratsiya — bo'sh (NULL) birlik tannarx BUGUNGI qiymatda")
# ══════════════════════════════════════════════════════════════
narx(1)
_d = SessionLocal()
_L = dict(
    L1=FinishedProduct(company_id=1, name="TT eski 1", category="profil", is_coated=True, quantity=10,
                       produced_quantity=10, unit="metr", unit_price=0, cost_price=999, source=StockSource.PRODUCED,
                       penoplast_id=ID["PENO"], recipe_id=ID["R1"], unit_volume_m3=0.01, unit_loy_kg=0.5,
                       production_status=ProductionStatus.READY),
    L2=FinishedProduct(company_id=1, name="TT eski 2", category="dona", quantity=4, produced_quantity=8, unit="dona",
                       unit_price=0, cost_price=400, source=StockSource.RETURNED,
                       production_status=ProductionStatus.READY),
    L3=FinishedProduct(company_id=1, name="TT eski 3", category="dona", quantity=0, produced_quantity=5, unit="dona",
                       unit_price=0, cost_price=500, source=StockSource.PRODUCED,
                       production_status=ProductionStatus.READY),
    L4=FinishedProduct(company_id=1, name="TT eski 4", category="dona", quantity=0, produced_quantity=0, unit="dona",
                       unit_price=0, cost_price=0, source=StockSource.PRODUCED,
                       production_status=ProductionStatus.READY),
    L5=FinishedProduct(company_id=1, name="TT eski 5", category="dona", quantity=3, produced_quantity=3, unit="dona",
                       unit_price=0, cost_price=300, source=StockSource.PRODUCED, unit_cost_stable=123,
                       production_status=ProductionStatus.READY),
)
_d.add_all(list(_L.values()))
_d.commit()
LID = {k: v.id for k, v in _L.items()}
_d.close()
_mig = getattr(main, "_migrate_tm_birlik_tannarx", None)
check("J0 main._migrate_tm_birlik_tannarx mavjud", callable(_mig))
if callable(_mig):
    with contextlib.redirect_stdout(_quiet):
        try:
            _mig()
        except Exception as e:            # noqa: BLE001
            print("migratsiya xatosi", e)
check("J1 hajm + loyli eski TM — bugungi narxda 7 600", taxminan(tm(LID["L1"])[2], 7_600), tm(LID["L1"]))
check("J2 hajmsiz eski TM — cost_price / quantity = 100 (produced bo'yicha 50 EMAS)", taxminan(tm(LID["L2"])[2], 100), tm(LID["L2"]))
check("J3 qoldig'i 0 — cost_price / produced_quantity = 100", taxminan(tm(LID["L3"])[2], 100), tm(LID["L3"]))
check("J4 tannarxsiz — NULL qoladi", tm(LID["L4"])[2] is None, tm(LID["L4"]))
check("J5 allaqachon bor qiymat (123) — tegilmadi", taxminan(tm(LID["L5"])[2], 123), tm(LID["L5"]))
check("J6 ishlab chiqarilgan TM (A) ga tegilmadi — 9 120", taxminan(tm(FP)[2], 9_120), tm(FP))
narx(2)
if callable(_mig):
    with contextlib.redirect_stdout(_quiet):
        try:
            _mig()
        except Exception as e:            # noqa: BLE001
            print("migratsiya xatosi", e)
check("J7 ikkinchi chaqiruv (narx x2) — L1 hali 7 600 (idempotent)", taxminan(tm(LID["L1"])[2], 7_600),
      tm(LID["L1"]))
check("J8 muzlagan L1 — narx x2 da ham _fp_stable_unit_cost 7 600", taxminan(tm(LID["L1"])[3], 7_600),
      tm(LID["L1"]))

# ══════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════
try:
    _p = inspect.getsource(crud.produce_finished_product)
except Exception:                          # noqa: BLE001
    _p = ""
check("S1 ishlab chiqarishda unit_cost_stable yoziladi", "unit_cost_stable=(total_cost / qty)" in _p)
try:
    _f = inspect.getsource(services.calculate_order_profit)
except Exception:                          # noqa: BLE001
    _f = ""
check("S2 foyda: muzlagan birlik AVVAL, eski formula (va cost_price tugasa o'tkazish) faqat zaxira",
      tartibda(_f, "_fp_stable_unit_cost(db, fp_c)", "unit_cost = _muz59", "if base_qty <= 0 or not fp_c.cost_price",
               "unit_cost = float(fp_c.cost_price) / base_qty"))
_m = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("S3 migratsiya e'londan keyin modul darajasida chaqiriladi",
      tartibda(_m, "def _migrate_tm_birlik_tannarx", "\n_migrate_tm_birlik_tannarx()\n"))
try:
    _a = inspect.getsource(crud.add_returned_to_stock)
except Exception:                          # noqa: BLE001
    _a = ""
check("S4 qaytgan TM: birlashishda o'rtacha cost_price o'zgarishidan OLDIN",
      tartibda(_a, "existing.unit_cost_stable =", "existing.cost_price = float(existing.cost_price or 0)"))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
