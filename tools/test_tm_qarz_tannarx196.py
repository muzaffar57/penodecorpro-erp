#!/usr/bin/env python3
"""
test_tm_qarz_tannarx196.py — kech153 (zip 196 «Tayyor mahsulot minusi»; EGASI QARORI 21.10 00:1x «Haqiqiy tannarx», QAYTA SO'RALMAYDI):
minus KEYINROQ boshqa narxdagi haqiqiy mahsulot bilan yopilsa — qarzga olgan buyurtma tannarxi yopgan mahsulot narxida; «Tayyor» bo'lib
bo'lgan buyurtma o'zgarmaydi; buyurtma o'chirilsa — omborga to'g'ri summa; nom / izoh guruhni o'zgartirsa — minus darhol yopiladi.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k196/probe196.py`, zip 195 kodi, SQLite = PG):
  D1 qarz 1 000 lik partiyada, keyin yangi partiya (1 200) «Sotuvga tayyor» — buyurtma tannarxi 15 000 qoldi (haqiqiy 16 000), ombor +
  buyurtmalar kirgan tannarxdan 1 000 kam, o'chirilgach omborda 1 000 kam; D1b arzon (800) — +1 000 «havodan»; D1c AYNAN yopish — −1 000;
  D2 «Yana ishlab chiqarish» — −1 000; D3 boshqa buyurtma qaytishi (2 000 lik) — −5 000; D4 brak bekori — −2 500 (va partiya tannarxi ÷
  miqdori ≠ birligi); G1 / G2 nom / izoh tahriri — minus keyingi amalgacha turdi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1`.
Asl kodga (zip 195) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_tm_qarz_tannarx196.py
"""
import os
import io
import sys
import tempfile
import contextlib
from types import SimpleNamespace

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tm_qarz196_test"
_T = tempfile.mkdtemp(prefix="tm196_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tm196.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Inventory, FinishedProduct, OrderItem, StockSource, ProductionStatus,   # noqa: E402
                    ActivityLog)
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def teng(a, b, eps=0.02):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


main._send_telegram = lambda *a, **k: True

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "tm196_admin", PAROL, UserRole.ADMIN, "TM196 Admin", company_id=1)
PRJ = Project(company_id=1, client_name="TM196 Mijoz", project_name="TM196 loyiha", total_budget=0, total_paid=0)
# penoplast: 1 blok = 1 m³ = 120 000 so'm; profil 1 m = 0,01 m³ → «Yana ishlab chiqarish» 1 m = 1 200 so'm
PENO = Inventory(company_id=1, item_name="TM196 PENO", unit="blok", stock_quantity=100000, min_stock=0, is_penoplast=True,
                 volume_per_unit=1, price_per_unit=120000, category="Penoplast")
s.add_all([PRJ, PENO])
s.commit()
PRJ_ID, PENO_ID = PRJ.id, PENO.id
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert A.post("/login", data={"username": "tm196_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)
_n = {"d": 0}


def yangi_tm(miqdor, nom, birlik, holat=ProductionStatus.READY, izoh=None, manba=StockSource.PRODUCED, narx=0.0):
    def f(s):
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=False, width=20, thickness=10,
                             quantity=miqdor, produced_quantity=max(miqdor, 0), unit="metr", unit_price=narx,
                             cost_price=max(miqdor, 0) * birlik, unit_cost_stable=birlik, source=manba,
                             penoplast_id=PENO_ID, unit_volume_m3=0.01, volume_m3=0.01 * max(miqdor, 0), production_status=holat,
                             reserved_quantity=0, notes=izoh)
        s.add(fp)
        s.flush()
        return fp.id
    return db_ishi(f)


def detal(uz, fid, nom=None):
    _n["d"] += 1                           # 8 s «takroriy yuborish» imzosi (nom, tur, soni) — har detal nomi noyob
    return {"name": nom or f"TM196 detal {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": uz,
            "quantity": 1, "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID, "finished_product_id": fid}


def oddiy_detal():
    _n["d"] += 1
    return {"name": f"TM196 oddiy {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": 2, "quantity": 1,
            "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID}


def buyurtma(*d):
    r = A.post("/api/orders?confirm_shortage=true", json={"project_id": PRJ_ID, "order_type": "product", "loy_kg": 0, "items": list(d)})
    return r, js(r).get("id")


def tm(fid):
    def f(s):
        x = s.get(FinishedProduct, fid)
        return None if x is None else (round(float(x.quantity), 4), round(float(x.cost_price or 0), 2),
                                       round(float(x.unit_cost_stable or 0), 2))
    return db_ishi(f)


def detallar(oid):
    """[(id, tm, miqdor, birlik, qarz)] — id tartibida."""
    def f(s):
        return [(x.id, x.finished_product_id, float(x.length if (x.category or '') == 'profil' else x.quantity or 0),
                 round(float(x.fp_unit_cost or 0), 4), round(float(getattr(x, 'fp_qarz', None) or 0), 4))
                for x in s.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id)]
    return db_ishi(f)


def tm_detal(oid, fid):
    return [d for d in detallar(oid) if d[1] == fid]


def btannarx(oid):
    """Buyurtmaning tayyor mahsulot tannarxi: Σ detal birligi × miqdor (`calculate_order_profit` bilan bir qoida)."""
    return round(sum(d[2] * d[3] for d in detallar(oid) if d[3]), 2)


def foyda_tannarxi(oid):
    import services
    p = db_ishi(lambda s: services.calculate_order_profit(s, oid, company_id=1))
    return round(float(p.get("tan_narxi") or 0), 2)


def qiymat(*ids):
    return round(sum((tm(i) or (0, 0, 0))[1] for i in ids), 2)


def tahrir(oid, items):
    o = js(A.get(f"/api/orders/{oid}"))
    t = {"project_id": PRJ_ID, "order_type": "product", "loy_kg": 0, "items": items, "notes": o.get("notes")}
    return A.put(f"/api/orders/{oid}?confirm_shortage=true", json=t)


def mavjud_detal(oid, idx, **ozgar):
    """Buyurtma detalini tahrir uchun (id va nomi bilan) — `ozgar` maydonlari almashtiriladi."""
    it = (js(A.get(f"/api/orders/{oid}")).get("items") or [])[idx]
    d = {"id": it.get("id"), "name": it.get("name"), "category": "profil", "width": 20, "thickness": 10, "length": it.get("length"),
         "quantity": 1, "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID,
         "finished_product_id": it.get("finished_product_id")}
    d.update(ozgar)
    return d


def tugat(nom, miqdor, birlik):
    """Yangi (jarayondagi) partiya — «Sotuvga tayyor» (minusni yopadi)."""
    n = yangi_tm(miqdor, nom, birlik, holat=ProductionStatus.IN_PROGRESS)
    return n, A.post(f"/api/finished/{n}/complete")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Ustun va deploydagi minus qarzini bir marta yozish (migratsiya)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("K1 `order_items.fp_qarz` ustuni (modelda)", hasattr(OrderItem, "fp_qarz"))
L1 = yangi_tm(10, "TM196 K Karniz", 1000)
_, OK1 = buyurtma(detal(6, L1))
_, OK2 = buyurtma(detal(9, L1))                    # L1 −5
_mig = getattr(main, "_migrate_tm_qarz196", None)


def _eski_holat(s):
    """Deploydan oldingi holat: qarz yozuvi yo'q, partiya birligi muzlamagan (eski partiya)."""
    if hasattr(OrderItem, "fp_qarz"):
        s.query(OrderItem).update({"fp_qarz": None}, synchronize_session=False)
    s.get(FinishedProduct, L1).unit_cost_stable = None


db_ishi(_eski_holat)
if _mig:
    with contextlib.redirect_stdout(io.StringIO()):
        _mig()
check("K2 migratsiya: minus (−5) qarzi OXIRGI olgan faol detalga (OK2 — 5), OK1 — 0; partiya birligi qarz yozilgan birlikda muzladi (1 000)",
      _mig and tm_detal(OK2, L1)[0][4] == 5.0 and tm_detal(OK1, L1)[0][4] == 0.0 and tm(L1) == (-5.0, 0.0, 1000.0),
      (tm_detal(OK1, L1), tm_detal(OK2, L1), tm(L1)))
db_ishi(lambda s: s.query(OrderItem).filter(OrderItem.id == tm_detal(OK2, L1)[0][0]).update({"fp_qarz": 4.0}) if _mig else None)
if _mig:
    with contextlib.redirect_stdout(io.StringIO()):
        _mig()
check("K3 ikkinchi ishga tushish — hech narsa o'zgarmaydi (qarz yozuvi bor — bir martalik)", _mig and tm_detal(OK2, L1)[0][4] == 4.0,
      tm_detal(OK2, L1))
db_ishi(lambda s: s.query(OrderItem).filter(OrderItem.id == tm_detal(OK2, L1)[0][0]).update({"fp_qarz": 5.0}) if _mig else None)
# eskirgan qarz yozuvi (qarz boshqa yo'l bilan yopilgan) — yangi minus boshlanganda tozalanadi, keyingi yopilish uni hisoblamaydi
LX = yangi_tm(10, "TM196 K4 Karniz", 1000)
_, OKs = buyurtma(detal(4, LX))                   # 4 m (LX 6) — qarz yo'q
if hasattr(OrderItem, "fp_qarz"):
    db_ishi(lambda s: s.query(OrderItem).filter(OrderItem.order_id == OKs).update({"fp_qarz": 3.0}))   # eskirgan yozuv
_, OKn = buyurtma(detal(8, LX))                   # LX −2 — yangi qarz 2
NX, _ = (lambda n: (n, A.post(f"/api/finished/{n}/complete")))(yangi_tm(2, "TM196 K4 Karniz", 1500, holat=ProductionStatus.IN_PROGRESS))
check("K4 eskirgan qarz yozuvi (3 m, partiya minusda emas edi) yangi minusda tozalandi: yopilish (2 m × 1 500) faqat yangi qarzdorga — "
      "8 000 + 2 × 500 = 9 000; eski buyurtma 4 000, qarzi 0",
      teng(btannarx(OKn), 9000) and teng(btannarx(OKs), 4000) and tm_detal(OKs, LX)[0][4] == 0.0 and tm(LX)[0] == 0.0,
      (tm(LX), detallar(OKs), detallar(OKn)))

LZ = yangi_tm(10, "TM196 K5 Karniz", 1000)
_, OKz = buyurtma(detal(12, LZ))                  # qarz 2 (LZ −2)
if hasattr(OrderItem, "fp_qarz"):
    db_ishi(lambda s: s.query(OrderItem).filter(OrderItem.order_id == OKz).update({"fp_qarz": 5.0}))   # eskirgan (qarzdan katta) yozuv
A.delete(f"/api/orders/{OKz}")
check("K5 detal qarz yozuvi partiya qarzidan katta (5 > 2, eskirgan): o'chirilganda qarz qismi faqat 2 m — LZ 10 m / 10 000 (tannarxsiz "
      "musbat qoldiq paydo bo'lmadi)", tm(LZ)[:2] == (10.0, 10000.0), tm(LZ))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Minus KEYINROQ yopiladi — buyurtma tannarxi yopgan mahsulot narxida (egasi qarori «Haqiqiy tannarx»)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
T1 = yangi_tm(10, "TM196 D1 Karniz", 1000)
r, O1 = buyurtma(detal(15, T1))
check("D0 10 m (1 000) dan 15 m — T −5, detal qarzi 5 (qarzga olingan), birlik 1 000",
      r.status_code == 200 and tm(T1) == (-5.0, 0.0, 1000.0) and tm_detal(O1, T1)[0][3:] == (1000.0, 5.0), (r.status_code, tm(T1), detallar(O1)))
N1, rc = tugat("TM196 D1 Karniz", 20, 1200)
check("D1 yangi partiya (20 m × 1 200) «Sotuvga tayyor» — T 0, N 15 / 18 000; buyurtma tannarxi 10 × 1 000 + 5 × 1 200 = 16 000 "
      "(ilgari 15 000), qarz 0; foyda hisobi ham 16 000",
      rc.status_code == 200 and tm(T1)[:2] == (0.0, 0.0) and tm(N1)[:2] == (15.0, 18000.0) and teng(btannarx(O1), 16000)
      and tm_detal(O1, T1)[0][4] == 0.0 and teng(foyda_tannarxi(O1), 16000), (rc.status_code, tm(T1), tm(N1), detallar(O1), foyda_tannarxi(O1)))
check("D2 saqlanish: ombor (T + N) + buyurtma = kirgan 10 × 1 000 + 20 × 1 200 = 34 000 AYNAN",
      teng(qiymat(T1, N1) + btannarx(O1), 34000), (qiymat(T1, N1), btannarx(O1)))
A.delete(f"/api/orders/{O1}")
check("D3 buyurtma o'chirildi — 15 m T ga 16 000 bilan qaytdi (birlik 1 066,67), guruh 30 m / 34 000 AYNAN (ilgari 33 000)",
      tm(T1)[:2] == (15.0, 16000.0) and teng(tm(T1)[2], 16000 / 15) and teng(qiymat(T1, N1), 34000), (tm(T1), tm(N1)))

T1b = yangi_tm(10, "TM196 D1b Karniz", 1000)
_, O1b = buyurtma(detal(15, T1b))
N1b, _ = tugat("TM196 D1b Karniz", 20, 800)
check("D4 yopgan partiya ARZON (800): buyurtma 14 000 (ilgari 15 000 — 1 000 «havodan»), saqlanish 26 000 AYNAN",
      teng(btannarx(O1b), 14000) and teng(qiymat(T1b, N1b) + btannarx(O1b), 26000), (tm(T1b), tm(N1b), detallar(O1b)))
T1c = yangi_tm(10, "TM196 D1c Karniz", 1000)
_, O1c = buyurtma(detal(15, T1c))
N1c, _ = tugat("TM196 D1c Karniz", 5, 1200)
check("D5 AYNAN yopish (5 m partiya — «ishlab chiqarish kerak: 5»): T 0, N 0 / 0, buyurtma 16 000 — farq hech qayerda yo'qolmadi",
      tm(T1c)[:2] == (0.0, 0.0) and tm(N1c)[:2] == (0.0, 0.0) and teng(btannarx(O1c), 16000), (tm(T1c), tm(N1c), detallar(O1c)))

T2 = yangi_tm(10, "TM196 D2 Karniz", 1000)
_, O2 = buyurtma(detal(15, T2))
ra = A.post(f"/api/finished/{T2}/add", json={"quantity": 20})
check("D6 «Yana ishlab chiqarish» shu partiyaga (+20 m, 1 m = 1 200): T 15 / 18 000, buyurtma 16 000 (ilgari 15 000)",
      ra.status_code == 200 and tm(T2)[:2] == (15.0, 18000.0) and teng(btannarx(O2), 16000), (ra.status_code, js(ra), tm(T2), detallar(O2)))
A.delete(f"/api/orders/{O2}")
check("D7 o'chirilgach T 30 m / 34 000 AYNAN (ilgari 33 000)", tm(T2)[:2] == (30.0, 34000.0), tm(T2))

T3 = yangi_tm(10, "TM196 D3 Karniz", 2000)
_, O3b = buyurtma(detal(10, T3))                  # B: 10 m × 2 000 (T 0)
db_ishi(lambda s: setattr(s.get(FinishedProduct, T3), "unit_cost_stable", 1000))   # partiya birligi keyin 1 000 (holat)
_, O3a = buyurtma(detal(5, T3))                   # A: 5 m qarzga × 1 000 (T −5)
A.delete(f"/api/orders/{O3b}")                    # B o'chdi — 10 m × 2 000: 5 m A qarzini yopdi, 5 m omborga
check("D8 boshqa buyurtma o'chirilib (10 m × 2 000) qarzni yopdi: A tannarxi 5 × 2 000 = 10 000 (ilgari 5 000), T 5 m / 10 000",
      teng(btannarx(O3a), 10000) and tm(T3)[:2] == (5.0, 10000.0) and tm_detal(O3a, T3)[0][4] == 0.0, (tm(T3), detallar(O3a)))

T4 = yangi_tm(10, "TM196 D4 Karniz", 1500)
rl = A.post("/api/finished/loss", json={"finished_product_id": T4, "quantity": 10, "reason": "x", "brak_sabab": "boshqa"})
_lid = js(rl).get("loss_id")
db_ishi(lambda s: setattr(s.get(FinishedProduct, T4), "unit_cost_stable", 1000))
_, O4 = buyurtma(detal(5, T4))                    # A: 5 m qarzga × 1 000 (T −5)
rb = A.delete(f"/api/finished/loss/{_lid}")
check("D9 brak bekori (10 m × 1 500) qarzni yopdi: A 7 500 (ilgari 5 000); T 5 m / 7 500, birlik 1 500 (tannarx ÷ miqdor = birlik)",
      rl.status_code == 200 and rb.status_code == 200 and teng(btannarx(O4), 7500) and tm(T4) == (5.0, 7500.0, 1500.0),
      (rl.status_code, rb.status_code, tm(T4), detallar(O4)))

# guruhdoshdan KEYINROQ ko'chish — boshqa buyurtma tahriri bo'sh qoldiq ochadi
T8, S8 = yangi_tm(10, "TM196 D8 Karniz", 1000), yangi_tm(5, "TM196 D8 Karniz", 1300)
_, O8b = buyurtma(detal(5, S8))                   # B: S8 dan 5 m × 1 300 (S8 0)
_, O8a = buyurtma(detal(15, T8))                  # A: T8 −5 (guruhda bo'sh yo'q)
r8 = tahrir(O8b, [mavjud_detal(O8b, 0, length=2)])   # B 5 → 2: 3 m S8 ga, muvozanat T8 ga
check("D10 boshqa buyurtma 5 → 2 m tahrirlandi — 3 m (1 300) guruhdoshdan A qarziga ko'chdi: A 15 000 + 3 × 300 = 15 900, qarz 2, T −2",
      r8.status_code == 200 and teng(btannarx(O8a), 15900) and tm_detal(O8a, T8)[0][4] == 2.0 and tm(T8)[0] == -2.0 and tm(S8)[0] == 0.0,
      (r8.status_code, js(r8) if r8.status_code != 200 else "", tm(T8), tm(S8), detallar(O8a)))

# qaytgan mahsulot MAVJUD (qaytgan) partiyaga — minusdagi qaytgan partiya
R5 = yangi_tm(10, "TM196 D5 Qaytgan", 1000, manba=StockSource.RETURNED)
_, O5a = buyurtma(detal(15, R5))                  # A: qaytgan partiyadan 15 m — R5 −5
P5 = yangi_tm(10, "TM196 D5 Ishlab", 1300)
_, O5b = buyurtma(detal(4, P5, nom="TM196 D5 Qaytgan"))   # B detali qaytgan partiya nomi bilan (birlik 1 300)


def _qaytar5(s):
    it = s.query(OrderItem).filter(OrderItem.order_id == O5b).first()
    _ordered = float(it.order_qty_normalized or 0)
    s.get(FinishedProduct, R5).unit_price = (float(it.total_price or 0) / _ordered) if _ordered > 0 else 0.0
    s.flush()
    crud.add_returned_to_stock(s, it, 4.0, "boshqa", order_id=O5b, commit=False)


db_ishi(_qaytar5)
check("D11 qaytgan mahsulot (4 m × 1 300) minusdagi qaytgan partiyaga: A qarzidan 4 m yopildi — A 15 000 + 4 × 300 = 16 200, qarz 1",
      teng(btannarx(O5a), 16200) and tm_detal(O5a, R5)[0][4] == 1.0 and tm(R5)[0] == -1.0 and tm(R5)[1] == 0.0,
      (tm(R5), detallar(O5a)))

# brak taqdiri «tuzatildi — o'sha joyiga» (omborda turgan mahsulot) minusni yopadi
T6 = yangi_tm(10, "TM196 D6 Karniz", 1500)
rl6 = A.post("/api/finished/loss", json={"finished_product_id": T6, "quantity": 10, "reason": "x", "brak_sabab": "boshqa"})
_lid6 = js(rl6).get("loss_id")
db_ishi(lambda s: setattr(s.get(FinishedProduct, T6), "unit_cost_stable", 1000))
_, O6 = buyurtma(detal(5, T6))                    # A: 5 m qarzga × 1 000 (T −5)
rt6 = A.post(f"/api/finished/loss/{_lid6}/taqdir", json={"taqdir": "tuzatildi"})
check("D12 brak taqdiri «Tuzatildi» (10 m × 1 500 — o'sha mahsulotga): A 7 500, T 5 m / 7 500, birlik 1 500",
      rt6.status_code == 200 and teng(btannarx(O6), 7500) and tm(T6) == (5.0, 7500.0, 1500.0),
      (rl6.status_code, rt6.status_code, rt6.text[:300], tm(T6), detallar(O6)))

# MRP yuk xati bekori — minusdagi partiyaga qaytgan qism (zip 176 F1 qoidasi bu yo'lda yo'q edi)
T7 = yangi_tm(10, "TM196 D7 Karniz", 1000)
_, O7 = buyurtma(detal(15, T7))                   # T7 −5, A qarzi 5
db_ishi(lambda s: crud._mrp_deliver_stock(s, SimpleNamespace(id=-1, company_id=1), 3.0, company_id=1, sign=-1.0, olingan=[[T7, 3.0]]))
check("D13 MRP yuk xati bekori (3 m) minusdagi partiyaga: T −2, tannarx 0 (ilgari 3 000 — minusdagi qatorda tannarx), A qarzi 2",
      tm(T7)[:2] == (-2.0, 0.0) and tm_detal(O7, T7)[0][4] == 2.0, (tm(T7), detallar(O7)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Qaror chegaralari — «Tayyor» buyurtma o'zgarmaydi; bir nechta qarzdor; qisman yopilgandan keyin qaytish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TR = yangi_tm(20, "TM196 R Karniz", 1000)
_, ORb = buyurtma(detal(10, TR))                  # B: 10 m (TR 10)
_, ORa = buyurtma(detal(15, TR))                  # A: 15 m (TR −5, A qarzi 5)
rr = A.post(f"/api/orders/{ORa}/ready")
NR, _ = tugat("TM196 R Karniz", 20, 1200)
check("R1 qarzga olgan buyurtma «Tayyor» bo'lib bo'lgach minus yopildi — uning tannarxi O'ZGARMADI (15 000; egasi qarori), qarzi 0",
      rr.status_code == 200 and teng(btannarx(ORa), 15000) and tm_detal(ORa, TR)[0][4] == 0.0 and tm(TR)[0] == 0.0 and teng(btannarx(ORb), 10000),
      (rr.status_code, rr.text[:200] if rr.status_code != 200 else "", tm(TR), detallar(ORa), detallar(ORb)))

TF = yangi_tm(10, "TM196 F Karniz", 1000)
_, OFa = buyurtma(detal(13, TF))                  # A qarzi 3 (TF −3)
_, OFc = buyurtma(detal(4, TF))                   # C qarzi 4 (TF −7)
NF, _ = tugat("TM196 F Karniz", 5, 1200)
check("R2 ikki qarzdor: 5 m (1 200) — avval ESKI qarz (A 3 m), so'ng C (2 m): A 13 000 + 3 × 200, C 4 000 + 2 × 200 = 4 400, C qarzi 2",
      teng(btannarx(OFa), 13600) and teng(btannarx(OFc), 4400) and tm_detal(OFa, TF)[0][4] == 0.0 and tm_detal(OFc, TF)[0][4] == 2.0
      and tm(TF)[0] == -2.0, (tm(TF), detallar(OFa), detallar(OFc)))
A.delete(f"/api/orders/{OFc}")
check("R3 qisman yopilgan C o'chirildi: avval qarz 2 m (tannarxsiz), so'ng 2 m haqiqiy (1 200 lik) — TF 2 m / 2 400; saqlanish "
      "10 × 1 000 + 5 × 1 200 = 16 000 AYNAN",
      tm(TF)[:2] == (2.0, 2400.0) and teng(qiymat(TF, NF) + btannarx(OFa), 16000), (tm(TF), tm(NF), detallar(OFa)))
TR4 = yangi_tm(10, "TM196 R4 Karniz", 1000)
_, OR4 = buyurtma(detal(15, TR4))                 # A qarzi 5
ry4 = A.post("/api/deliveries", json={"order_id": OR4, "items": [{"order_item_id": tm_detal(OR4, TR4)[0][0], "quantity": 1}]})
A.delete(f"/api/orders/{OR4}")                    # yuk xati bor — yumshoq o'chirish: 14 m qaytdi (5 m qarz + 9 m), TR4 9
_, OR4b = buyurtma(detal(8, TR4))                 # TR4 1
rt4 = A.post(f"/api/orders/{OR4}/restore")        # qolgan 14 m qayta olinadi: 1 m bor, 13 m qarzga
NR4, _ = tugat("TM196 R4 Karniz", 13, 1200)
check("R4 o'chirilgan buyurtma TIKLANDI (1 m bor, 13 m qarzga — qarz yozildi), keyin 13 m × 1 200 yopdi: A 15 000 + 13 × 200 = 17 600",
      rt4.status_code == 200 and teng(btannarx(OR4), 17600) and tm_detal(OR4, TR4)[0][4] == 0.0 and tm(TR4)[0] == 0.0,
      (rt4.status_code, rt4.text[:200], tm(TR4), detallar(OR4)))
TR5 = yangi_tm(10, "TM196 R5 Karniz", 1000)
_, OR5 = buyurtma(detal(15, TR5))                 # A qarzi 5
NR5, _ = tugat("TM196 R5 Karniz", 2, 1200)        # 2 m yopildi: A (15 000 + 400) / 15, qarz 3
ry5 = A.post("/api/deliveries", json={"order_id": OR5, "items": [{"order_item_id": tm_detal(OR5, TR5)[0][0], "quantity": 12}]})
rr5 = A.post(f"/api/orders/{OR5}/ready")          # qisman «Tayyor»: qolgan 3 m (qarz) qaytadi, buyurtma 12 m ga tushadi
check("R5 qisman tuzatilgan qarzdor buyurtma 12 m topshirilib «Tayyor» (qisman): 3 m qarz qaytdi; tannarx 12 × 1 033,33 = 12 400 = "
      "10 × 1 000 + 2 × 1 200 (haqiqiy); TR5 0",
      ry5.status_code == 200 and rr5.status_code == 200 and teng(btannarx(OR5), 12400, 0.05) and tm(TR5)[:2] == (0.0, 0.0),
      (ry5.status_code, rr5.status_code, rr5.text[:200], tm(TR5), detallar(OR5)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Tahrir — qarzdor detal kamaytirilsa / ko'paytirilsa / boshqa mahsulotga o'tsa / o'chirilsa")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TE = yangi_tm(10, "TM196 E Karniz", 1000)
_, OE = buyurtma(detal(15, TE))                   # qarz 5
re1 = tahrir(OE, [mavjud_detal(OE, 0, length=12)])
check("E1 qarzdor detal 15 → 12 m: avval QARZ qismi qaytadi (tannarxsiz) — TE −2 / 0, qarz 2, birlik 1 000",
      re1.status_code == 200 and tm(TE)[:2] == (-2.0, 0.0) and tm_detal(OE, TE)[0][3:] == (1000.0, 2.0), (re1.status_code, tm(TE), detallar(OE)))
re2 = tahrir(OE, [mavjud_detal(OE, 0, length=16)])
check("E2 12 → 16 m: yana 4 m qarzga — TE −6, qarz 6", re2.status_code == 200 and tm(TE)[0] == -6.0 and tm_detal(OE, TE)[0][4] == 6.0,
      (re2.status_code, tm(TE), detallar(OE)))
UE = yangi_tm(20, "TM196 E boshqa", 1300)
re3 = tahrir(OE, [mavjud_detal(OE, 0, finished_product_id=UE, length=16)])
check("E3 detal boshqa mahsulotga (UE, 1 300) o'tdi: TE ga 16 m qaytdi — 6 m qarz (tannarxsiz) + 10 m (1 000) → TE 10 / 10 000; UE 4, "
      "detal 1 300, qarz 0",
      re3.status_code == 200 and tm(TE)[:2] == (10.0, 10000.0) and tm(UE)[0] == 4.0 and tm_detal(OE, UE)[0][3:] == (1300.0, 0.0),
      (re3.status_code, tm(TE), tm(UE), detallar(OE)))

TE4 = yangi_tm(10, "TM196 E4 Karniz", 1000)
_, OE4 = buyurtma(detal(15, TE4), oddiy_detal())   # qarz 5
_i4 = tm_detal(OE4, TE4)[0][0]
rd4 = A.delete(f"/api/order-items/{_i4}")
check("E4 qarzdor detal o'chirildi (`DELETE /api/order-items`): 5 m qarz + 10 m haqiqiy — TE4 10 / 10 000",
      rd4.status_code == 200 and tm(TE4)[:2] == (10.0, 10000.0), (rd4.status_code, tm(TE4)))
TE5 = yangi_tm(10, "TM196 E5 Karniz", 1000)
_, OE5 = buyurtma(detal(15, TE5), oddiy_detal())   # qarz 5
NE5, _ = tugat("TM196 E5 Karniz", 2, 1200)         # 2 m yopildi: detal (15 000 + 400) / 15, qarz 3
_od5 = (js(A.get(f"/api/orders/{OE5}")).get("items") or [])
_qolgan5 = [mavjud_detal(OE5, i) for i, x in enumerate(_od5) if x.get("finished_product_id") != TE5]
re5 = tahrir(OE5, _qolgan5)
check("E5 to'liq tahrirda qisman tuzatilgan qarzdor detal olib tashlandi: 3 m qarz (tannarxsiz) + 12 m haqiqiy (12 400) — TE5 12 m / 12 400",
      re5.status_code == 200 and tm(TE5)[0] == 12.0 and teng(tm(TE5)[1], 12400), (re5.status_code, re5.text[:200], tm(TE5)))
TE7 = yangi_tm(10, "TM196 E7 Karniz", 2000)
_, OE7b = buyurtma(detal(10, TE7))                # B: 10 m × 2 000 (TE7 0)
db_ishi(lambda s: setattr(s.get(FinishedProduct, TE7), "unit_cost_stable", 1000))
_, OE7a = buyurtma(detal(5, TE7))                 # A qarzi 5 × 1 000 (TE7 −5)
re7 = tahrir(OE7b, [mavjud_detal(OE7b, 0, length=4)])   # B 10 → 4: 6 m (2 000) — 5 m A qarzini yopadi, 1 m omborga
check("E7 boshqa (qarzsiz) buyurtma tahriri minusdagi partiyaga 6 m (2 000) qaytardi: A 5 000 + 5 × 1 000 = 10 000, qarz 0; TE7 1 m / 2 000",
      re7.status_code == 200 and teng(btannarx(OE7a), 10000) and tm_detal(OE7a, TE7)[0][4] == 0.0 and tm(TE7)[:2] == (1.0, 2000.0),
      (re7.status_code, tm(TE7), detallar(OE7a)))

TE6 = yangi_tm(10, "TM196 E6 Karniz", 1000)
_, OE6 = buyurtma(detal(15, TE6))                 # qarz 5
NE6, _ = tugat("TM196 E6 Karniz", 2, 1200)        # 2 m yopildi: detal (15 000 + 400) / 15, qarz 3
_b6 = tm_detal(OE6, TE6)[0]
re6 = tahrir(OE6, [mavjud_detal(OE6, 0, length=11)])   # 4 m qaytdi: 3 m qarz + 1 m haqiqiy (1 033,33)
check("E6 qisman tuzatilgan detal (birlik 1 026,67, qarz 3) 15 → 11 m: 3 m qarz + 1 m haqiqiy (12 400 ÷ 12 = 1 033,33) — TE6 1 m / "
      "1 033,33; detal birligi 1 033,33, qarz 0; saqlanish 12 400 AYNAN",
      teng(_b6[3], 15400 / 15, 0.001) and _b6[4] == 3.0 and re6.status_code == 200 and tm(TE6)[0] == 1.0 and teng(tm(TE6)[1], 12400 / 12)
      and teng(tm_detal(OE6, TE6)[0][3], 12400 / 12, 0.001) and tm_detal(OE6, TE6)[0][4] == 0.0
      and teng(qiymat(TE6, NE6) + btannarx(OE6), 12400), (_b6, re6.status_code, tm(TE6), tm(NE6), detallar(OE6)))

TE8 = yangi_tm(10, "TM196 E8 Karniz", 1000)
_, OE8c = buyurtma(detal(12, TE8))                # C: qarzi 2 (TE8 −2)
A.post(f"/api/finished/{TE8}/add", json={"quantity": 3})   # +3 m (1 200): C qarzi yopildi, TE8 1 m
_, OE8a = buyurtma(detal(5, TE8))                 # A: 1 m bor + 4 m qarzga (TE8 −4)
tahrir(OE8c, [mavjud_detal(OE8c, 0, length=15)])  # C 12 → 15: yana 3 m qarzga (TE8 −7) — C yozuvi A nikidan ESKI
re8 = tahrir(OE8a, [mavjud_detal(OE8a, 0, length=2)])   # A 5 → 2: 3 m — A ning O'Z qarzi (boshqalarnikini yopmaydi)
check("E8 qarzdor A kamaydi (5 → 2): qaytgan 3 m — A ning o'z qarzi (A qarzi 1), eskiroq qarzdor C ga tegilmadi (qarzi 3); TE8 −4",
      re8.status_code == 200 and tm_detal(OE8a, TE8)[0][4] == 1.0 and tm_detal(OE8c, TE8)[0][4] == 3.0 and tm(TE8)[0] == -4.0,
      (re8.status_code, tm(TE8), detallar(OE8a), detallar(OE8c)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Mustaqil tekshiruv topilmalari (`work/k196/review196/HISOBOT.md` 1, 2, 3, 5) — saqlanish AYNAN")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TT1 = yangi_tm(10, "TM196 T1 Karniz", 1000)
_, OT1a = buyurtma(detal(1, TT1))                 # A 1 m
_, OT1c = buyurtma(detal(13, TT1))                # C 9 + 4 qarz (TT1 −4)
NT1, _ = tugat("TM196 T1 Karniz", 2, 3000)        # C qarzidan 2 m (3 000) yopildi
tahrir(OT1a, [mavjud_detal(OT1a, 0, length=4)])   # A 1 → 4: 3 m qarzga (TT1 −5)
A.delete(f"/api/orders/{OT1c}")                   # C o'chdi: 2 m qarz (tannarxsiz) + 11 m haqiqiy (1 363,64) — A qarzi 3 m yopiladi
check("T1 qarzdor buyurtma (C) o'chirilib, haqiqiy qismi boshqa qarzdor (A) qarzini yopdi: A 1 000 + 3 × 1 363,64 = 5 090,91 (ilgari "
      "C ning o'z yozuvi turganida A yozuvi kesilardi — 4 363,64); saqlanish 16 000 AYNAN",
      teng(btannarx(OT1a), 1000 + 3 * 15000 / 11) and teng(qiymat(TT1, NT1) + btannarx(OT1a), 16000),
      (tm(TT1), tm(NT1), detallar(OT1a)))
TY = yangi_tm(2, "TM196 T2 Y", 1500)              # Y — id KICHIK
TX = yangi_tm(10, "TM196 T2 X", 1000)
_, OT2 = buyurtma(detal(14, TX))                  # D: X dan 10 + 4 qarz (X −4)
rt2 = tahrir(OT2, [mavjud_detal(OT2, 0, finished_product_id=TY, length=5)])   # D → Y (5 m): Y −3, qarz 3
check("T2 qarzdor detal id si KICHIK partiyaga o'tdi: X 10 / 10 000, Y −3, D qarzi 3 (ilgari 0 — yozuv yo'qolardi)",
      rt2.status_code == 200 and tm(TX)[:2] == (10.0, 10000.0) and tm(TY)[0] == -3.0 and tm_detal(OT2, TY)[0][4] == 3.0,
      (rt2.status_code, tm(TX), tm(TY), detallar(OT2)))
NT2, _ = tugat("TM196 T2 Y", 3, 2500)
check("T2b Y qarzi 3 m × 2 500 yopildi: D 2 × 1 500 + 3 × 2 500 = 10 500; saqlanish 20 500 AYNAN",
      teng(btannarx(OT2), 10500) and teng(qiymat(TX, TY, NT2) + btannarx(OT2), 20500), (tm(TY), tm(NT2), detallar(OT2)))
TT3 = yangi_tm(10, "TM196 T3 Karniz", 1000)
_, OT3 = buyurtma(detal(10, TT3))                 # I3: 10 m (TT3 0)
A.post(f"/api/finished/{TT3}/add", json={"quantity": 5})   # +5 m (1 200)
tahrir(OT3, [mavjud_detal(OT3, 0), detal(8, TT3)])          # I2: 5 m (1 200) + 3 m qarzga (TT3 −3)
rt3 = tahrir(OT3, [mavjud_detal(OT3, 0, length=4), mavjud_detal(OT3, 1, length=12)])   # I3 10 → 4 (6 m), I2 8 → 12 — bitta tahrirda
NT3, _ = tugat("TM196 T3 Karniz", 1, 1000)
check("T3 bitta tahrirda bir detal kamaydi (6 m qaytdi) va qarzdor detal O'SDI: I2 tannarxi 5 × 1 200 + 7 × 1 000 = 13 000 (ilgari "
      "13 200 — tuzatma yangi miqdorga bo'linardi); saqlanish 17 000 AYNAN",
      rt3.status_code == 200 and teng(tm_detal(OT3, TT3)[1][2] * tm_detal(OT3, TT3)[1][3], 13000)
      and teng(qiymat(TT3, NT3) + btannarx(OT3), 17000), (rt3.status_code, tm(TT3), detallar(OT3)))
TT5 = yangi_tm(10, "TM196 T5 Karniz", 1000)
_, OT5 = buyurtma(detal(15, TT5))                 # qarz 5 (TT5 −5)
ST5 = yangi_tm(2, "TM196 T5 Karniz", 1500)        # bo'sh guruhdosh muvozanatsiz paydo bo'ldi (eski holat)
rt5 = tahrir(OT5, [mavjud_detal(OT5, 0, length=12)])
check("T5 muvozanatsiz guruhda tahrir (15 → 12): avval guruhdosh 2 m (1 500) qarzni yopdi — buyurtma 10 × 1 000 + 2 × 1 500 = 13 000 "
      "(ilgari 12 000 — tahrir eski birlikni qayta yozardi)",
      rt5.status_code == 200 and teng(btannarx(OT5), 13000) and teng(qiymat(TT5, ST5) + btannarx(OT5), 13000),
      (rt5.status_code, tm(TT5), tm(ST5), detallar(OT5)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. Nom / izoh tahriri — partiya boshqa guruhga o'tsa minus darhol yopiladi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
G1 = yangi_tm(10, "TM196 G Karniz", 1000)
_, OG1 = buyurtma(detal(15, G1))                  # G1 −5
S1 = yangi_tm(8, "TM196 G boshqa", 1300)
_j0 = db_ishi(lambda s: s.query(ActivityLog).filter(ActivityLog.action == "tm_minus_yopildi", ActivityLog.entity_id == G1).count())
rg1 = A.put(f"/api/finished/{S1}", json={"name": "TM196 G Karniz"})
check("G1 bo'sh partiya (8 m × 1 300) NOMI minus guruhiga o'zgartirildi — darhol: G1 0, S1 3 / 3 900; buyurtma 15 000 + 5 × 300 = 16 500; "
      "jurnalda «minus yopildi»",
      rg1.status_code == 200 and tm(G1)[0] == 0.0 and tm(S1)[:2] == (3.0, 3900.0) and teng(btannarx(OG1), 16500)
      and db_ishi(lambda s: s.query(ActivityLog).filter(ActivityLog.action == "tm_minus_yopildi", ActivityLog.entity_id == G1).count()) > _j0,
      (rg1.status_code, tm(G1), tm(S1), detallar(OG1)))
G2 = yangi_tm(10, "TM196 H Karniz", 1000, izoh="width2=30")
_, OG2 = buyurtma(detal(15, G2))                  # G2 −5 (width2=30 guruhi)
S2 = yangi_tm(8, "TM196 H Karniz", 1000)          # width2 yo'q — boshqa guruh
rg2 = A.put(f"/api/finished/{G2}", json={"notes": "sinov izohi"})
check("G2 minusdagi partiyaning IZOHI (width2 olib tashlandi) — S2 guruhiga o'tdi: darhol G2 0, S2 3",
      rg2.status_code == 200 and tm(G2)[0] == 0.0 and tm(S2)[0] == 3.0, (rg2.status_code, tm(G2), tm(S2)))
G3 = yangi_tm(10, "TM196 J Karniz", 1000)
_, OG3 = buyurtma(detal(15, G3))                  # G3 −5
S3 = yangi_tm(8, "TM196 J boshqa", 1000)
rg3 = A.put(f"/api/finished/{S3}", json={"unit_price": 25000})
rg4 = A.put(f"/api/finished/{G3}", json={"name": "tm196  j  KARNIZ"})   # faqat harf / bo'shliq — guruh o'zgarmaydi
check("G3 narx tahriri va nomning harf / bo'shliq farqi — guruh o'zgarmaydi: hech narsa ko'chmadi (G3 −5, S3 8)",
      rg3.status_code == 200 and rg4.status_code == 200 and tm(G3)[0] == -5.0 and tm(S3)[0] == 8.0, (rg3.status_code, rg4.status_code, tm(G3), tm(S3)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Brak bekori — tiklangan qism brak narxida, partiya birligi og'irlikli (minussiz)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TB = yangi_tm(10, "TM196 B Karniz", 1000)
rlb = A.post("/api/finished/loss", json={"finished_product_id": TB, "quantity": 2, "reason": "x", "brak_sabab": "boshqa"})
_lb = js(rlb).get("loss_id")
A.post(f"/api/finished/{TB}/add", json={"quantity": 10})           # 8 × 1 000 + 10 × 1 200 = 20 000 / 18 m
rbb = A.delete(f"/api/finished/loss/{_lb}")
check("B1 brak (2 m × 1 000) bekor qilindi — TB 20 m / 22 000, birlik 1 100 (tannarx ÷ miqdor; ilgari 1 111,11)",
      rbb.status_code == 200 and tm(TB)[:2] == (20.0, 22000.0) and teng(tm(TB)[2], 1100), (rbb.status_code, tm(TB)))
_, OBb = buyurtma(detal(20, TB))
check("B2 hammasi buyurtmaga olindi — TB 0 / 0 (qoldiq tannarx qolmadi), buyurtma 22 000",
      tm(TB)[:2] == (0.0, 0.0) and teng(btannarx(OBb), 22000), (tm(TB), detallar(OBb)))

print(f"\n{'=' * 70}\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
