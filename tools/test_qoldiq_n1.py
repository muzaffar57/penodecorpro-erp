#!/usr/bin/env python3
"""test_qoldiq_n1.py — kech98 (2026-09-27), 129-band (116-band QOLDIG'I: qator boshiga so'rov qolgan 5 joy) + ta'minotchi
qarzi yig'indisi va yaxlitlash qoidasi.

NIMA UCHUN KERAK
----------------
O'LCHANGAN (kech97 `work/probe116.py` KENG bosqichi, kech98 `work/probe129a.py`; asl = zip 91, SQLite = PG):
  (a) ta'minotchilar — ta'minotchi boshiga 3 so'rov (`get_supplier_debt`: nasiya xaridlar + to'lovlar; barcha xaridlar):
      `/api/suppliers`, `/api/suppliers/debt-total` 12 -> 42 (+10 ta'minotchi), `/debts`, qarzlar xulosasi, PDF;
      qarz FLOAT yig'indi + Python `round()` (bankir):
        * 29 972.26 + 19 244.86 + 144.38 = 49 361.50 — SQLite 49 361, PG da birinchi xaridning faqat IZOHI tahrirlansa
          (qator jismoniy oxirga ko'chadi) 49 362 — pul o'zgarmasdan (float tartib);
        * 100.50 -> 100, 101.50 -> 102, 102.50 -> 102; qoldiq 2.50 — "2 so'm";
        * 7 × 1 000.07 = 7 000.49 qarzga AYNAN 7 000.49 to'lansa — 409 "qarzdan (7,000 so'm) 0 so'mga ko'p";
  (b) `services.get_chart_data` — usta boshiga 2 so'rov (SUM, soni) + TM sotuvi boshiga mahsulot;
  (c) `crud.get_masters_kpi_report` — usta boshiga "oxirgi buyurtma" so'rovi;
  (d) `services.get_today_stats` — bugungi TM sotuvi boshiga mahsulot;
  (e) `services.get_notifications` — material boshiga 14 kunlik chiqim SUM.
YECHIM (texnik): (a) `crud._taminotchi_toplami` — bir necha IN so'rovi, pul yig'indisi `Decimal` da ANIQ;
`_taminotchi_qarz_korinishi` — butun so'mga 0.5 YUQORIGA (`_som_butun_int` — JS `Math.round`, bazadagi HALF_UP bilan bir
xil), qarz qoldig'i yarim so'mdan oshmasa 0 (`QARZ_BARDOSH` — mijoz qarzi bilan bir qoida); ortiqcha to'lov — TIYIN
aniqligida, faqat yarim so'mdan KO'P bo'lsa 409; (b)–(e) GROUP BY / `selectinload` — natija AYNAN.
ISBOT (`work/dump129.py`, 599 chaqiruv, ETALON = asl kod + FAQAT yangi yaxlitlash qoidasi ↔ YANGI): SQLite / PG / TF=1 —
AYNAN; asl ↔ yangi farqi FAQAT ta'minotchi qarzi ko'rinishida (.50 holatlar).

BO'LIMLAR
---------
  A MIQYOS: +5 ta'minotchi / usta / bugungi TM sotuvi / material — 9 marshrut va 6 funksiya so'rovlari O'ZGARMAYDI
    (nazorat: asl — qator boshiga — o'qish o'sadi);
  B ta'minotchilar: har ta'minotchi mustaqil hisob bilan (Decimal, HALF_UP, bardosh), maxsus holatlar (tartib, .50,
    qoldiq, ortiqcha to'langan, xaridsiz, naqd, NULL sana, nofaol, B korxona), tartib, jami, muddatlar, tarix;
  C ortiqcha to'lov qoidasi (tiyin + bardosh) va o'chirish;
  D grafik / bugun / usta KPI / bildirishnomalar — ASL algoritm (qator boshiga) bilan AYNAN;
  E begona korxona; X 5xx yo'q; S statik.

ISHLATISH
---------
    python3 tools/test_qoldiq_n1.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_qoldiq_n1.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import json
import inspect
import tempfile
import contextlib
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qoldiq_n1_test"
_T = tempfile.mkdtemp(prefix="qn1_")
_DB = os.path.join(_T, "qoldiq_n1_test.db")

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

import io                                          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
import services                                    # noqa: E402
import sqlalchemy.orm as _orm                      # noqa: E402
from sqlalchemy.orm import strategy_options as _so  # noqa: E402
from sqlalchemy import event, func, text           # noqa: E402
from database import SessionLocal, engine, tashkent_today_start_utc   # noqa: E402
from production_models import Company              # noqa: E402
from models import (UserRole, Inventory, InventoryMovement, InventoryPurchase, Supplier, SupplierPayment,   # noqa: E402
                    Project, Order, Master, FinishedProduct, FinishedProductSale, StockSource, ProductionStatus,
                    OrderStatus)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HOLATLAR = []


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
        print(f"  ✗ {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.content = self.text.encode()

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    HOLATLAR.append((metod.upper() + " " + url.split("?")[0], r.status_code))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


SANOQ = {"n": 0, "on": False}


@event.listens_for(engine, "before_cursor_execute")
def _sana(conn, cursor, statement, parameters, context, executemany):
    if SANOQ["on"]:
        SANOQ["n"] += 1


@contextlib.contextmanager
def sanoq():
    SANOQ["n"] = 0
    SANOQ["on"] = True
    try:
        yield SANOQ
    finally:
        SANOQ["on"] = False


@contextlib.contextmanager
def asl_yol():
    """ASL (kech98 gacha) yuklash: kod ishlatadigan `selectinload` — `lazyload` (zanjirdagi ham)."""
    eski_f, eski_m = _orm.selectinload, _so._AbstractLoad.selectinload
    _orm.selectinload = _orm.lazyload
    _so._AbstractLoad.selectinload = _so._AbstractLoad.lazyload
    try:
        yield
    finally:
        _orm.selectinload = eski_f
        _so._AbstractLoad.selectinload = eski_m


def jsonla(x):
    def _v(y):
        if isinstance(y, dict):
            return {k: _v(v) for k, v in y.items() if k != "created_at"}
        if isinstance(y, list):
            return [_v(v) for v in y]
        return y
    return json.dumps(_v(json.loads(json.dumps(x, default=str, sort_keys=True))), sort_keys=True)


# ── MUSTAQIL qoida (kod emas): tiyin, butun so'm 0.5 YUQORIGA, qarz bardoshi 0.5 ─────────────────────────────
def d2(x):
    return Decimal(repr(float(x or 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def hu(x):
    return int(Decimal(x).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


HOZIR = datetime.utcnow()
Y, M = HOZIR.year, HOZIR.month

# ── Fikstura ────────────────────────────────────────────────────────────────────────────────────────────────
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="QN1 Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "QN1_a", "Parol123!", UserRole.ADMIN, "QN1 A", company_id=1)
    auth.create_user(_db, "QN1_b", "Parol123!", UserRole.ADMIN, "QN1 B", company_id=2)
_pa = Inventory(company_id=1, item_name="QN1 Penoplast A", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
_pb = Inventory(company_id=2, item_name="QN1 Penoplast B", unit="blok", stock_quantity=100_000, price_per_unit=400_000,
                volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
_ma = Inventory(company_id=1, item_name="QN1 Xarid A", unit="kg", stock_quantity=1_000_000, price_per_unit=1_000,
                category="Kimyo")
_mb = Inventory(company_id=2, item_name="QN1 Xarid B", unit="kg", stock_quantity=1_000_000, price_per_unit=1_000,
                category="Kimyo")
_db.add_all([_pa, _pb, _ma, _mb])
_db.commit()
PA, PB, MA, MB = _pa.id, _pb.id, _ma.id, _mb.id
_prj = {}
for _cid in (1, 2):
    _p = Project(company_id=_cid, client_name=f"QN1 {_cid}", project_name=f"QN1 {_cid}", total_budget=0, total_paid=0)
    _db.add(_p)
    _db.commit()
    _prj[_cid] = _p.id
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c


CA, CB = _kir("QN1_a"), _kir("QN1_b")
QADAM = []
ID = {}
_N = {"n": 0, "tel": 0}


def taminotchi(teg, cid=1, faol=True):
    s = SessionLocal()
    _N["tel"] += 1
    x = Supplier(company_id=cid, name=f"QN1 {teg}", phone=f"+99897{_N['tel']:07d}", is_active=faol)
    s.add(x)
    s.commit()
    i = x.id
    s.close()
    ID["S_" + teg] = i
    return i


def xarid(sid, summa, kredit=True, vaqt=None, muddat=None, cid=1):
    s = SessionLocal()
    p = InventoryPurchase(inventory_id=MA if cid == 1 else MB, item_name="QN1 Xarid", quantity=1, unit="kg",
                          price_per_unit=summa, total_amount=summa, purchased_at=vaqt or HOZIR, supplier_id=sid,
                          is_credit=kredit, category="Kimyo", payment_due_date=muddat, notes=f"QN1 {summa}")
    s.add(p)
    s.commit()
    i = p.id
    s.close()
    return i


def tolov_orm(sid, summa):
    s = SessionLocal()
    s.add(SupplierPayment(supplier_id=sid, amount=summa, paid_at=HOZIR - timedelta(hours=1), notes="QN1"))
    s.commit()
    s.close()


def taminotchi_qosh(n, teg, cid=1):
    """n ta ta'minotchi: shu oy nasiya (juftlarida to'lov muddati), 40 kunlik nasiya, naqd xarid, to'lov."""
    for i in range(n):
        sid = taminotchi(f"{teg}{i}", cid)
        xarid(sid, 1_000.25 + i, muddat=(HOZIR + timedelta(days=3 + i, minutes=len(ID)) if i % 2 == 0 else None), cid=cid)
        xarid(sid, 500.5, vaqt=HOZIR - timedelta(days=40), cid=cid)
        xarid(sid, 300, kredit=False, cid=cid)
        tolov_orm(sid, 400.25 + i)


def _buyurtma(klient, cid, peno, master_id, i, tayyor=True):
    _N["n"] += 1
    t = {"project_id": _prj[cid], "order_type": "product", "loy_kg": 0, "master_id": master_id, "items": [
        {"name": f"QN1 panel {_N['n']}", "category": "panel", "width": 30, "thickness": 5, "quantity": 3 + i,
         "unit_price": 51_000.5 + 10 * i, "is_coated": False, "penoplast_id": peno}]}
    r = req(klient, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
    QADAM.append(("buyurtma", r.status_code))
    oid = (js(r) or {}).get("id") if r.status_code == 200 else None
    if oid and tayyor:
        r2 = req(klient, "post", f"/api/orders/{oid}/ready")
        QADAM.append(("tayyor", r2.status_code))
    return oid


def usta(teg, cid=1, faol=True, kpi=3.0):
    s = SessionLocal()
    _N["tel"] += 1
    m = Master(company_id=cid, name=f"QN1 {teg}", phone=f"+99896{_N['tel']:07d}", cashback_percent=0, kpi_percent=kpi,
               is_active=faol)
    s.add(m)
    s.commit()
    i = m.id
    s.close()
    ID["M_" + teg] = i
    return i


def usta_qosh(n, teg, cid=1):
    for i in range(n):
        mid = usta(f"{teg}{i}", cid, kpi=2.0 + i)
        _buyurtma(CA if cid == 1 else CB, cid, PA if cid == 1 else PB, mid, i)


def sotuv(teg, kat, summa, vaqt=None, cid=1, ochirilgan=False):
    s = SessionLocal()
    fid = None
    if not ochirilgan:
        fp = FinishedProduct(company_id=cid, name=f"QN1 TM {teg}", category=kat, quantity=5, produced_quantity=5,
                             unit="dona", unit_price=1_000, cost_price=2_500, unit_cost_stable=500.0,
                             source=StockSource.PRODUCED, production_status=ProductionStatus.READY,
                             finished_production_at=HOZIR)
        s.add(fp)
        s.flush()
        fid = fp.id
    s.add(FinishedProductSale(company_id=cid, finished_product_id=fid, product_name=f"QN1 sotuv {teg}", quantity=1,
                              unit="dona", unit_price=summa, total_amount=summa, cost_amount=100.25,
                              sold_at=vaqt or HOZIR, payment_method="naqd", master_id=None))
    s.commit()
    s.close()


def sotuv_qosh(n, teg, cid=1):
    for i in range(n):
        sotuv(f"{teg}{i}", "Gips" if i % 2 == 0 else "dona", 2_000.5 + i, cid=cid)


def material(teg, qoldiq, chiqimlar, cid=1, ochirilgan=False):
    """chiqimlar: [(miqdor, necha kun oldin)]; har materialga "in" harakat ham (e'tiborsiz)."""
    s = SessionLocal()
    it = Inventory(company_id=cid, item_name=f"QN1 {teg}", unit="kg", stock_quantity=qoldiq, min_stock=0,
                   price_per_unit=1_000, category="Kimyo", is_deleted=ochirilgan)
    s.add(it)
    s.flush()
    for miq, kun in chiqimlar:
        s.add(InventoryMovement(company_id=cid, inventory_id=it.id, item_name=it.item_name, movement_type="out",
                                quantity=miq, unit="kg", reason="QN1 chiqim", created_at=HOZIR - timedelta(days=kun)))
    s.add(InventoryMovement(company_id=cid, inventory_id=it.id, item_name=it.item_name, movement_type="in",
                            quantity=900, unit="kg", reason="QN1 kirim", created_at=HOZIR - timedelta(days=1)))
    s.commit()
    i = it.id
    s.close()
    ID["N_" + teg] = i
    return i


def material_qosh(n, teg, cid=1):
    for i in range(n):
        material(f"{teg}{i}", 10 + i, [(10, 2), (20.5, 4)], cid=cid)


# asos: ta'minotchilar, ustalar, sotuvlar, materiallar
taminotchi_qosh(3, "t")
usta_qosh(3, "u")
sotuv_qosh(3, "s")
material_qosh(3, "n")
# maxsus ta'minotchilar
_t = taminotchi("ORD")
ID["ORD_x"] = [xarid(_t, 29_972.26), xarid(_t, 19_244.86), xarid(_t, 144.38)]
_t = taminotchi("ORD2")
ID["ORD2_x"] = [xarid(_t, 33_910.34), xarid(_t, 18_494.03), xarid(_t, 10_112.13)]
xarid(taminotchi("EVEN"), 102.50)
_t = taminotchi("RES05")
xarid(_t, 1_000.50)
tolov_orm(_t, 1_000)
_t = taminotchi("RES25")
xarid(_t, 1_002.50)
tolov_orm(_t, 1_000)
_t = taminotchi("OVER")
xarid(_t, 1_000)
tolov_orm(_t, 1_500)
taminotchi("NONE")
xarid(taminotchi("CASH"), 5_000, kredit=False)
_t = taminotchi("MIX")
xarid(_t, 700.25, vaqt=HOZIR - timedelta(days=40))
xarid(_t, 300.25)
xarid(_t, 99.99, kredit=False)
tolov_orm(_t, 0.49)
xarid(taminotchi("INACT", faol=False), 8_888.88, muddat=HOZIR + timedelta(days=6, minutes=7))
_t = taminotchi("DUE1")
xarid(_t, 5_000, muddat=HOZIR - timedelta(days=2))
_t = taminotchi("DUE2")
xarid(_t, 5_000, muddat=HOZIR + timedelta(days=2, minutes=1))
tolov_orm(_t, 5_000)
_t = taminotchi("DUE3")
xarid(_t, 1_000.40, muddat=HOZIR + timedelta(days=1, minutes=2))
tolov_orm(_t, 1_000)
_t = taminotchi("DUE4")
xarid(_t, 1_000.60, muddat=HOZIR + timedelta(days=10, minutes=3))
tolov_orm(_t, 1_000)
_t = taminotchi("DUE5")
xarid(_t, 2_000, muddat=HOZIR + timedelta(days=5, minutes=4))
xarid(_t, 3_000, muddat=HOZIR + timedelta(days=1, minutes=5))
_t = taminotchi("B", cid=2)
xarid(_t, 777.77, cid=2)
tolov_orm(_t, 7.77)
xarid(taminotchi("DUEB", cid=2), 4_000, muddat=HOZIR + timedelta(days=3, minutes=6), cid=2)
_t = taminotchi("PAY2")
xarid(_t, 3_000)
tolov_orm(_t, 1_000.25)
tolov_orm(_t, 999.75)
# PG: ORD birinchi xaridi jismoniy OXIRGA (faqat izoh) + statistika — ketma-ket skan tartibi id tartibidan farq qiladi
_s = SessionLocal()
_s.execute(InventoryPurchase.__table__.update().where(InventoryPurchase.__table__.c.id.in_([ID["ORD_x"][0], ID["ORD2_x"][0]])).values(
    notes="QN1 izoh tahrirlandi"))
_s.commit()
if PG_URL:
    _s.execute(text("ANALYZE inventory_purchases"))
    _s.commit()
_fiz = [r[0] for r in _s.execute(text("SELECT id FROM inventory_purchases WHERE supplier_id = :s"), {"s": ID["S_ORD"]})]
_s.close()
# maxsus ustalar: biri "Tayyor" buyurtmalaridan birining sanasi NULL, biri yagona "Tayyor" NULL, biri buyurtmasiz, nofaol
_m1 = usta("MNULL1", kpi=4.0)
_o1a = _buyurtma(CA, 1, PA, _m1, 1)
_o1b = _buyurtma(CA, 1, PA, _m1, 2)
_m2 = usta("MNULL2", kpi=5.0)
_o2 = _buyurtma(CA, 1, PA, _m2, 3)
usta("MNONE", kpi=6.0)
_m4 = usta("MNOFAOL", faol=False, kpi=7.0)
_buyurtma(CA, 1, PA, _m4, 4)
_mb = usta("MB", cid=2, kpi=3.0)
_ob1 = _buyurtma(CB, 2, PB, _mb, 1)
_ob2 = _buyurtma(CB, 2, PB, _mb, 2)
# MNULL1: yana "Tayyor" (2 kun oldin), yumshoq o'chirilgan "Tayyor", jarayondagi; MNULL2: keyinroq DELIVERED;
# BUZILGAN (Core): B korxona buyurtmasi A ustasida (MNULL1) — A grafigi / KPI siga korxona sharti bilan kirmaydi
_o1c = _buyurtma(CA, 1, PA, _m1, 5)
_o1d = _buyurtma(CA, 1, PA, _m1, 6)
_o1e = _buyurtma(CA, 1, PA, _m1, 7, tayyor=False)
_o2b = _buyurtma(CA, 1, PA, _m2, 8)
_s = SessionLocal()
for _oid in (_o1b, _o2):
    if _oid:
        _s.execute(Order.__table__.update().where(Order.__table__.c.id == _oid).values(completed_at=None))
if _o1c:
    _s.execute(Order.__table__.update().where(Order.__table__.c.id == _o1c).values(completed_at=HOZIR - timedelta(days=2)))
if _o1d:
    _s.execute(Order.__table__.update().where(Order.__table__.c.id == _o1d).values(is_deleted=True))
if _o2b:
    _s.execute(Order.__table__.update().where(Order.__table__.c.id == _o2b).values(
        status=OrderStatus.DELIVERED, completed_at=HOZIR + timedelta(hours=1)))
if _ob2:
    _s.execute(Order.__table__.update().where(Order.__table__.c.id == _ob2).values(master_id=_m1))
_s.commit()
_s.close()
# maxsus sotuvlar: mahsuloti o'chirilgan (NULL), o'tgan oy Gips, B korxona
sotuv("OCH", "Gips", 1_234.5, ochirilgan=True)
sotuv("OTGAN", "Gips", 2_900.25, vaqt=HOZIR - timedelta(days=32))
sotuv("B", "Gips", 2_222.22, cid=2)
# maxsus materiallar: > 7 kun, aniq 7 kun (14 / 14), faqat eski chiqim, o'chirilgan, B korxona
material("N2", 100, [(14, 2)])
material("N3", 7, [(3.5, 1), (4.2, 2), (6.3, 3)])
material("N4", 3, [(9, 20)])
material("N5", 2, [(28, 4)], ochirilgan=True)
material("NB", 5, [(30, 2)], cid=2)
_s = SessionLocal()
_s.execute(InventoryMovement.__table__.insert().values(
    company_id=2, inventory_id=ID["N_N2"], item_name="QN1 N2", movement_type="out", quantity=1_000, unit="kg",
    reason="QN1 begona", created_at=HOZIR - timedelta(days=1)))
_s.commit()
_s.close()

section("F fikstura")
check(f"F1 fikstura qadamlari 200 ({len(QADAM)} ta)", all(k == 200 for _, k in QADAM), [q for q in QADAM if q[1] != 200][:5])
if PG_URL:
    check("F2 PG: ORD birinchi xaridi jismoniy oxirda (tartib id dan farq qiladi — test sezgir)",
          _fiz == [ID["ORD_x"][1], ID["ORD_x"][2], ID["ORD_x"][0]], _fiz)

MARSHRUT = [
    ("suppliers", "/api/suppliers", None),
    ("supdebt", "/api/suppliers/debt-total", None),
    ("due", "/api/suppliers/due-dates", None),
    ("debts", "/debts", None),
    ("debtsum", "/api/finance/debt-summary", {"year": Y, "month": M}),
    ("charts", "/api/dashboard/charts", None),
    ("kpirep", "/api/masters/kpi-report", {"include_inactive": "true"}),
    ("today", "/api/dashboard/today", None),
    ("notif", "/api/notifications", None),
]
FUNK = [
    ("suppliers", lambda s: crud.get_suppliers_with_debt(s, company_id=1)),
    ("due", lambda s: crud.get_supplier_payment_due_dates(s, company_id=1)),
    ("charts", lambda s: services.get_chart_data(s, company_id=1)),
    ("kpirep", lambda s: crud.get_masters_kpi_report(s, Y, include_inactive=True, company_id=1)),
    ("today", lambda s: services.get_today_stats(s, company_id=1)),
    ("notif", lambda s: services.get_notifications(s, company_id=1)),
]


def olchov():
    n, jav = {}, {}
    for k, url, par in MARSHRUT:
        with sanoq() as sq:
            r = req(CA, "get", url, params=par)
        n["API " + k] = sq["n"]
        jav["API " + k] = r.status_code
    for k, fn in FUNK:
        s = SessionLocal()
        try:
            with sanoq() as sq:
                fn(s)
            n[k] = sq["n"]
        except Exception as e:          # noqa: BLE001
            n[k] = f"XATO {type(e).__name__}: {e}"
        finally:
            s.rollback()
            s.close()
    return n, jav


# ── ASL algoritmlar (kech98 gacha — qator boshiga so'rov; natija manbai sifatida) ──────────────────────────
def eski_qarz(s, sid):
    pur = s.query(InventoryPurchase).filter(InventoryPurchase.supplier_id == sid, InventoryPurchase.is_credit == True).all()   # noqa: E712
    pay = s.query(SupplierPayment).filter(SupplierPayment.supplier_id == sid).all()
    hamma = s.query(InventoryPurchase).filter(InventoryPurchase.supplier_id == sid).order_by(
        InventoryPurchase.purchased_at.desc()).all()
    return pur, pay, hamma


def eski_usta_kpi(s, cid):
    def _oc(q):
        return q.filter(Order.company_id == cid) if cid is not None else q
    q = s.query(Master).filter(Master.is_active == True)        # noqa: E712
    if cid is not None:
        q = q.filter(Master.company_id == cid)
    out = []
    for m in q.all():
        total = _oc(s.query(func.sum(func.coalesce(Order.agreed_amount, Order.total_amount, 0))).filter(
            Order.master_id == m.id, Order.status == OrderStatus.READY)).scalar() or 0
        cnt = _oc(s.query(Order).filter(Order.master_id == m.id, Order.is_deleted.isnot(True))).count()
        out.append({"name": m.name, "total": float(total), "orders": cnt})
    out.sort(key=lambda x: x["total"], reverse=True)
    return out[:5]


def eski_oxirgi(s, mid):
    o = s.query(Order).filter(Order.master_id == mid, Order.status == OrderStatus.READY).order_by(
        Order.completed_at.desc().nullslast()).first()
    return o.completed_at.isoformat() if o and o.completed_at else None


def eski_bildirish(s, cid):
    """`get_notifications` 🟠 qismi — kech98 gacha (material boshiga SUM)."""
    now = datetime.utcnow()
    items = s.query(Inventory).filter(
        *([Inventory.company_id == cid] if cid is not None else []),
        Inventory.is_deleted.isnot(True), Inventory.stock_quantity > 0,
        ~Inventory.item_name.like(services.TAYYOR_LOY_PREFIKS + '%')).all()
    out = []
    for item in items:
        t = s.query(func.sum(InventoryMovement.quantity)).filter(
            *([InventoryMovement.company_id == cid] if cid is not None else []),
            InventoryMovement.inventory_id == item.id, InventoryMovement.movement_type == "out",
            InventoryMovement.created_at >= now - timedelta(days=14)).scalar()
        t = float(t or 0)
        if t <= 0:
            continue
        kun = float(item.stock_quantity) / (t / 14)
        if kun <= 7:
            out.append(f"{item.item_name} {max(1, round(kun))} kundan keyin tugaydi")
    return out


def nazorat():
    """ASL (qator boshiga) o'qishlar soni: ta'minotchilar (3 / ta), ustalar (2 + 1), materiallar (1), bugungi TM sotuvlari
    (lazy mahsulot) — fikstura qo'shimchalari shu so'rovlar doirasida ekanini ko'rsatadi."""
    s = SessionLocal()
    try:
        with sanoq() as sq:
            for x in s.query(Supplier).filter(Supplier.company_id == 1, Supplier.is_active == True).all():   # noqa: E712
                eski_qarz(s, x.id)
            eski_usta_kpi(s, 1)
            for m in s.query(Master).filter(Master.company_id == 1).all():
                eski_oxirgi(s, m.id)
            eski_bildirish(s, 1)
            with asl_yol():
                services.get_today_stats(s, company_id=1)
        return sq["n"]
    finally:
        s.rollback()
        s.close()


# ── A. Miqyos ───────────────────────────────────────────────────────────────────────────────────────────────
section("A miqyos: +5 ta'minotchi / usta / bugungi TM sotuvi / material — so'rovlar o'zgarmaydi")
olchov()        # qizdirish
N0, J0 = olchov()
Z0 = nazorat()
taminotchi_qosh(5, "m")
usta_qosh(5, "m")
sotuv_qosh(5, "m")
material_qosh(5, "m")
N1, J1 = olchov()
Z1 = nazorat()
check("A0 fikstura qadamlari 200 (+5 usta buyurtmasi)", all(k == 200 for _, k in QADAM), [q for q in QADAM if q[1] != 200][:5])
for i, k in enumerate(N0, 1):
    check(f"A{i} {k}: {N0[k]} -> {N1[k]} so'rov (o'zgarmaydi)", N0[k] == N1[k] and not str(N0[k]).startswith("XATO"),
          (N0[k], N1[k]))
check(f"A20 nazorat — ASL (qator boshiga) o'qish o'sadi: {Z0} -> {Z1} (>= +40)", Z1 - Z0 >= 40, (Z0, Z1))
check("A21 marshrutlar 200", all(v == 200 for v in J1.values()), J1)


# ── B. Ta'minotchilar — mustaqil hisob ─────────────────────────────────────────────────────────────────────
def kutilgan(sid):
    """Bazadagi xom yozuvlardan, qoida bo'yicha (Decimal, 0.5 yuqoriga, bardosh 0.5)."""
    s = SessionLocal()
    try:
        pur = s.query(InventoryPurchase).filter(InventoryPurchase.supplier_id == sid).order_by(InventoryPurchase.id).all()
        pay = s.query(SupplierPayment).filter(SupplierPayment.supplier_id == sid).order_by(SupplierPayment.id).all()
        kredit = sum((d2(p.total_amount) for p in pur if p.is_credit), Decimal("0"))
        tolov = sum((d2(p.amount) for p in pay), Decimal("0"))
        qarz = kredit - tolov
        if qarz <= Decimal("0.5"):
            qarz = Decimal("0")
        vaqtlar = [p.purchased_at for p in pur if p.purchased_at is not None]
        oy = [p for p in pur if p.purchased_at is not None and (p.purchased_at.year, p.purchased_at.month) == (Y, M)]
        return {"total_credit": hu(kredit), "total_paid": hu(tolov), "debt": hu(qarz),
                "purchase_count": sum(1 for p in pur if p.is_credit),
                "last_purchase_at": max(vaqtlar).isoformat() if vaqtlar else None,
                "month_count": len(oy), "month_total": hu(sum((d2(p.total_amount) for p in oy), Decimal("0")))}
    finally:
        s.close()


def royxat(klient):
    r = req(klient, "get", "/api/suppliers")
    j = js(r) if r.status_code == 200 else None
    return r.status_code, {x["id"]: x for x in (j or [])}, [x["id"] for x in (j or [])]


def taminot(teg):
    return _R.get(ID["S_" + teg], {})


section("B ta'minotchilar — mustaqil hisob (Decimal, 0.5 yuqoriga, bardosh)")
_st, _R, _TARTIB = royxat(CA)
check("B0 /api/suppliers 200", _st == 200, _st)
_s = SessionLocal()
_A_FAOL = [x for x in _s.query(Supplier).filter(Supplier.company_id == 1, Supplier.is_active == True)   # noqa: E712
           .order_by(Supplier.name).all()]
_s.close()
_yomon = []
for x in _A_FAOL:
    k = kutilgan(x.id)
    g = {kk: _R.get(x.id, {}).get(kk) for kk in k}
    if g != k:
        _yomon.append((x.name, g, k))
check(f"B1 har faol A ta'minotchisi ({len(_A_FAOL)} ta) — 7 maydon mustaqil hisob bilan AYNAN", not _yomon and _A_FAOL,
      _yomon[:3])
check("B1b ro'yxatda faqat faol A ta'minotchilari (nofaol va B yo'q)", set(_R) == {x.id for x in _A_FAOL},
      (len(_R), len(_A_FAOL)))
_kut_tartib = [x.id for x in sorted(_A_FAOL, key=lambda x: -kutilgan(x.id)["debt"])]      # nom tartibida barqaror
check("B1c tartib: qarz kamayishi bo'yicha, teng qarzda — nom bo'yicha", _TARTIB == _kut_tartib, (_TARTIB[:6], _kut_tartib[:6]))
check("B2 ORD 29 972.26 + 19 244.86 + 144.38 = 49 361.50 → 49 362 (0.5 yuqoriga; PG da izoh tahriridan keyin ham)",
      taminot("ORD").get("debt") == 49_362 and taminot("ORD").get("total_credit") == 49_362, taminot("ORD"))
check("B2b ORD2 33 910.34 + 18 494.03 + 10 112.13 = 62 516.50 → 62 517 (float yig'indi HAR tartibda 62 516.4999…)",
      taminot("ORD2").get("debt") == 62_517 and taminot("ORD2").get("total_credit") == 62_517, taminot("ORD2"))
check("B3 EVEN 102.50 → 103 (asl bankir: 102)", taminot("EVEN").get("debt") == 103 and taminot("EVEN").get("total_credit") == 103,
      taminot("EVEN"))
check("B4 RES05 1 000.50 − 1 000 = 0.50 → qarz 0 (bardosh), kredit 1 001, to'langan 1 000",
      (taminot("RES05").get("debt"), taminot("RES05").get("total_credit"), taminot("RES05").get("total_paid")) == (0, 1001, 1000),
      taminot("RES05"))
check("B5 RES25 qoldiq 2.50 → 3 (asl bankir: 2)", taminot("RES25").get("debt") == 3, taminot("RES25"))
check("B6 OVER ortiqcha to'langan → qarz 0, to'langan 1 500", (taminot("OVER").get("debt"), taminot("OVER").get("total_paid")) == (0, 1500),
      taminot("OVER"))
check("B7 NONE xaridsiz — hammasi 0, oxirgi xarid yo'q",
      {k: taminot("NONE").get(k) for k in ("debt", "total_credit", "total_paid", "purchase_count", "month_count",
                                           "month_total", "last_purchase_at")} ==
      {"debt": 0, "total_credit": 0, "total_paid": 0, "purchase_count": 0, "month_count": 0, "month_total": 0,
       "last_purchase_at": None}, taminot("NONE"))
check("B8 CASH faqat naqd — qarz 0, nasiya soni 0, oy 1 ta / 5 000",
      (taminot("CASH").get("debt"), taminot("CASH").get("purchase_count"), taminot("CASH").get("month_count"),
       taminot("CASH").get("month_total")) == (0, 0, 1, 5000), taminot("CASH"))
check("B9 MIX: kredit 1 000.50 → 1 001, to'langan 0.49 → 0, qarz 1 000.01 → 1 000, oy 2 ta / 400.24 → 400",
      (taminot("MIX").get("total_credit"), taminot("MIX").get("total_paid"), taminot("MIX").get("debt"),
       taminot("MIX").get("month_count"), taminot("MIX").get("month_total")) == (1001, 0, 1000, 2, 400), taminot("MIX"))
_d = js(req(CA, "get", "/api/suppliers/debt-total")) or {}
_kq = [kutilgan(x.id)["debt"] for x in _A_FAOL]
check("B10 debt-total = qarzlar yig'indisi va qarzdorlar soni",
      _d.get("total_debt") == sum(_kq) and _d.get("supplier_count") == sum(1 for q in _kq if q > 0), (_d, sum(_kq)))
_ds = js(req(CA, "get", "/api/finance/debt-summary", params={"year": Y, "month": M})) or {}
check("B11 qarzlar xulosasi: ta'minotchilar qarzi va soni AYNAN",
      _ds.get("supplier_debt") == sum(_kq) and _ds.get("supplier_debt_count") == sum(1 for q in _kq if q > 0), _ds)
# PG: yana bir xarid jismoniy ko'chiriladi — qarz tartibdan mustaqil
_s = SessionLocal()
_s.execute(InventoryPurchase.__table__.update().where(InventoryPurchase.__table__.c.id == ID["ORD_x"][1]).values(
    notes="QN1 izoh 2"))
_s.commit()
if PG_URL:
    _s.execute(text("ANALYZE inventory_purchases"))
    _s.commit()
_s.close()
_st2, _R2, _ = royxat(CA)
check("B12 ORD boshqa xarid izohi tahrirlangach ham 49 362 (tartibdan mustaqil)", _R2.get(ID["S_ORD"], {}).get("debt") == 49_362,
      _R2.get(ID["S_ORD"]))
_yomon = []
_s = SessionLocal()
for x in _A_FAOL[:12]:
    k = kutilgan(x.id)
    for cid in (1, None):
        g = crud.get_supplier_debt(_s, x.id, company_id=cid)
        if g != {kk: k[kk] for kk in ("total_credit", "total_paid", "debt", "purchase_count")}:
            _yomon.append((x.name, cid, g))
    h = js(req(CA, "get", f"/api/suppliers/{x.id}/history")) or {}
    if {kk: h.get(kk) for kk in ("total_credit", "total_paid", "debt", "purchase_count")} != \
            {kk: k[kk] for kk in ("total_credit", "total_paid", "debt", "purchase_count")}:
        _yomon.append((x.name, "tarix", h.get("debt")))
g2 = crud.get_supplier_debt(_s, ID["S_ORD"], company_id=2)
_s.close()
check("B13 get_supplier_debt (korxona bilan / korxonasiz) va tarix sahifasi — ro'yxat bilan bir qoida", not _yomon, _yomon[:3])
check("B14 get_supplier_debt begona korxona bilan — nol", g2 == {"total_credit": 0, "total_paid": 0, "debt": 0, "purchase_count": 0}, g2)


def kutilgan_muddat(cid):
    s = SessionLocal()
    try:
        rows = s.query(InventoryPurchase).join(Supplier, Supplier.id == InventoryPurchase.supplier_id).filter(
            Supplier.company_id == cid, InventoryPurchase.is_credit == True,             # noqa: E712
            InventoryPurchase.payment_due_date.isnot(None)).order_by(InventoryPurchase.payment_due_date.asc()).all()
        eng = {}
        for p in rows:
            if p.supplier_id not in eng or p.payment_due_date < eng[p.supplier_id]:
                eng[p.supplier_id] = p.payment_due_date
        now = datetime.utcnow()
        out = []
        for sid, due in eng.items():
            q = kutilgan(sid)["debt"]
            if q <= 0:
                continue
            kun = (due.date() - now.date()).days
            out.append({"supplier_id": sid, "supplier_name": s.get(Supplier, sid).name, "debt": q,
                        "due_date": due.isoformat(), "days_left": kun,
                        "status": "overdue" if kun < 0 else ("due_soon" if kun <= 3 else "ok")})
        out.sort(key=lambda x: x["days_left"])
        return out
    finally:
        s.close()


_due = js(req(CA, "get", "/api/suppliers/due-dates")) or []
_kdue = kutilgan_muddat(1)
check(f"B15 to'lov muddatlari (A) mustaqil hisob bilan AYNAN ({len(_kdue)} ta)", _due == _kdue and _kdue,
      (_due[:3], _kdue[:3]))
_dn = {x["supplier_name"] for x in _due}
check("B16 muddatlar: DUE2 (to'langan), DUE3 (qoldiq 0.40) YO'Q; DUE4 (0.60 → 1), DUE1 (o'tgan), DUE5, nofaol INACT BOR",
      "QN1 DUE2" not in _dn and "QN1 DUE3" not in _dn and {"QN1 DUE1", "QN1 DUE4", "QN1 DUE5", "QN1 INACT"} <= _dn
      and next((x["debt"] for x in _due if x["supplier_name"] == "QN1 DUE4"), None) == 1, sorted(_dn))
_dueb = js(req(CB, "get", "/api/suppliers/due-dates")) or []
check("B17 muddatlar (B) — faqat B ta'minotchisi", [x["supplier_name"] for x in _dueb] == ["QN1 DUEB"] and _dueb == kutilgan_muddat(2),
      _dueb)
# NULL sana (faqat Core bilan): oxirgi xarid — haqiqiy eng so'nggi sana; faqat NULL — yo'q; 500 YO'Q (asl PG — 500)
_tn = taminotchi("NULLV")
xarid(_tn, 111.11, vaqt=HOZIR - timedelta(days=10))
_pn = xarid(_tn, 222.22)
_ta = taminotchi("NULLALL")
_pa2 = xarid(_ta, 333.33)
_s = SessionLocal()
_s.execute(InventoryPurchase.__table__.update().where(InventoryPurchase.__table__.c.id.in_([_pn, _pa2])).values(
    purchased_at=None))
_s.commit()
_s.close()
_st3, _R3, _ = royxat(CA)
check("B18 NULL sanali xarid bilan /api/suppliers 200 (asl: faqat NULL sanali ta'minotchida 500; PG da `DESC` NULL ni birinchi qo'yadi — birorta NULL bo'lsa ham 500)",
      _st3 == 200, _st3)
check("B19 NULLV: oxirgi xarid — haqiqiy sana (10 kun oldin), qarz ikkala xarid (333.33 → 333)",
      _R3.get(_tn, {}).get("last_purchase_at") == kutilgan(_tn)["last_purchase_at"] and kutilgan(_tn)["last_purchase_at"]
      and _R3.get(_tn, {}).get("debt") == 333, _R3.get(_tn))
check("B20 NULLALL: oxirgi xarid yo'q, oy soni 0, qarz 333", (_R3.get(_ta, {}).get("last_purchase_at"),
                                                             _R3.get(_ta, {}).get("month_count"),
                                                             _R3.get(_ta, {}).get("debt")) == (None, 0, 333), _R3.get(_ta))

# ── C. Ortiqcha to'lov qoidasi va o'chirish ───────────────────────────────────────────────────────────────
section("C ortiqcha to'lov (tiyin + bardosh 0.5) va o'chirish")


def tol(sid, summa, tasdiq=False):
    r = req(CA, "post", f"/api/suppliers/{sid}/payment", json={"amount": summa, "confirm_overpay": tasdiq})
    return r.status_code, js(r) or {}


_c1 = taminotchi("C1")
xarid(_c1, 7_000.49)
_k, _j = tol(_c1, 7_000.49)
check("C1 qarz 7 000.49 ga AYNAN 7 000.49 → 200, qarz 0 (asl: 409 \"0 so'mga ko'p\")", _k == 200 and _j.get("debt") == 0, (_k, _j))
_c2 = taminotchi("C2")
xarid(_c2, 1_000.50)
_ko = kutilgan(_c2)["debt"]
_k, _j = tol(_c2, _ko)
check(f"C2 qarz 1 000.50 (ko'rinishi {_ko}) — ko'rsatilgan summa to'lansa 200, qarz 0", _ko == 1001 and _k == 200 and _j.get("debt") == 0,
      (_ko, _k, _j))
_c3 = taminotchi("C3")
xarid(_c3, 1_000.49)
_k, _j = tol(_c3, 1_001)
_det = _j.get("detail") if isinstance(_j.get("detail"), dict) else {}
check("C3 qarz 1 000.49, to'lov 1 001 (0.51 ortiq) → 409, excess 0.51, debt 1 000.49",
      _k == 409 and _det.get("type") == "overpayment_warning" and abs(float(_det.get("excess", 0)) - 0.51) < 1e-9
      and abs(float(_det.get("debt", 0)) - 1000.49) < 1e-9, (_k, _j))
_k, _j = tol(_c3, 1_001, True)
check("C4 tasdiq bilan → 200, qarz 0, to'langan 1 001", _k == 200 and _j.get("debt") == 0 and _j.get("total_paid") == 1001, (_k, _j))
_c5 = taminotchi("C5")
xarid(_c5, 1_000)
_k, _j = tol(_c5, 1_000.50)
check("C5 qarz 1 000, to'lov 1 000.50 (0.50 — bardosh ichida) → 200", _k == 200 and _j.get("debt") == 0, (_k, _j))
_c6 = taminotchi("C6")
xarid(_c6, 1_000)
_k, _j = tol(_c6, 1_000.51)
check("C6 qarz 1 000, to'lov 1 000.51 → 409 (excess 0.51)", _k == 409 and abs(float((_j.get("detail") or {}).get("excess", 0)) - 0.51) < 1e-9,
      (_k, _j))
_c7 = taminotchi("C7")
_k, _j = tol(_c7, 1)
check("C7 qarzsiz ta'minotchiga 1 so'm → 409 (excess 1, debt 0)",
      _k == 409 and float((_j.get("detail") or {}).get("excess", -1)) == 1.0 and float((_j.get("detail") or {}).get("debt", -1)) == 0.0,
      (_k, _j))
_k, _j = tol(ID["S_OVER"], 1)
check("C10 ortiqcha to'langan (xom qarz −500) ta'minotchiga 1 so'm → 409 (excess 1, debt 0 — manfiy qarz 0 deb olinadi)",
      _k == 409 and float((_j.get("detail") or {}).get("excess", -1)) == 1.0 and float((_j.get("detail") or {}).get("debt", -1)) == 0.0,
      (_k, _j))
_c8 = taminotchi("C8")
xarid(_c8, 1_000)
_k, _j = tol(_c8, 400.25)
check("C8 qisman to'lov 400.25 → 200, qarz 599.75 → 600", _k == 200 and _j.get("debt") == 600, (_k, _j))
for _teg, _narx, _kut_k, _kut_q in (("D1", 1_000.50, 200, None), ("D2", 1_000.60, 400, 1), ("D3", 1_002.50, 400, 3)):
    _d_id = taminotchi(_teg)
    xarid(_d_id, _narx)
    tolov_orm(_d_id, 1_000)
    _r = req(CA, "delete", f"/api/suppliers/{_d_id}")
    _dj = js(_r) or {}
    _dq = (_dj.get("detail") or {}).get("debt") if isinstance(_dj.get("detail"), dict) else None
    check(f"C9 o'chirish: qoldiq {_narx - 1000:.2f} → {_kut_k}" + (f" (qarz {_kut_q})" if _kut_q else ""),
          _r.status_code == _kut_k and (_kut_q is None or _dq == _kut_q), (_r.status_code, _dj))

# ── D. Grafik / bugun / usta KPI / bildirishnomalar — ASL algoritm bilan AYNAN ─────────────────────────────
section("D grafik / bugun / usta KPI / bildirishnomalar — ASL (qator boshiga) algoritm bilan AYNAN")
for cid in (1, 2, None):
    s = SessionLocal()
    try:
        g = services.get_chart_data(s, company_id=cid)
        e = eski_usta_kpi(s, cid)
        s.rollback()
        with asl_yol():
            ga = services.get_chart_data(s, company_id=cid)
        check(f"D1 c{cid} grafik ustalar (top 5) — ASL (usta boshiga SUM / soni) bilan AYNAN", g["master_kpi"] == e,
              (g["master_kpi"], e))
        check(f"D2 c{cid} grafik — ASL (lazy mahsulot) yo'l bilan AYNAN", jsonla(g) == jsonla(ga))
        t = services.get_today_stats(s, company_id=cid)
        s.rollback()
        with asl_yol():
            ta = services.get_today_stats(s, company_id=cid)
        check(f"D3 c{cid} bugungi statistika — ASL yo'l bilan AYNAN", jsonla(t) == jsonla(ta), (t, ta))
        rep = crud.get_masters_kpi_report(s, Y, include_inactive=True, company_id=cid)
        _yo = [(r["name"], r["last_order_date"], eski_oxirgi(s, r["id"])) for r in rep["masters"]
               if r["last_order_date"] != eski_oxirgi(s, r["id"])]
        check(f"D4 c{cid} usta KPI oxirgi sana — ASL (usta boshiga, NULLS LAST) bilan AYNAN ({len(rep['masters'])} usta)",
              not _yo and rep["masters"], _yo[:3])
        nb = [x["text"] for x in services.get_notifications(s, company_id=cid) if x["category"] == "stock_predicted"]
        ne = eski_bildirish(s, cid)
        check(f"D5 c{cid} bildirishnomalar (tugash bashorati) — ASL (material boshiga SUM) bilan AYNAN ({len(ne)} ta)",
              nb == ne, (nb, ne))
    finally:
        s.rollback()
        s.close()
_s = SessionLocal()
_rep = {r["name"]: r for r in crud.get_masters_kpi_report(_s, Y, include_inactive=True, company_id=1)["masters"]}
_m1_sanalar = [o.completed_at for o in _s.query(Order).filter(Order.master_id == _m1, Order.status == OrderStatus.READY).all()]
_o1a_c = max(x for x in _m1_sanalar if x is not None) if any(x is not None for x in _m1_sanalar) else None
_m1_null = sum(1 for x in _m1_sanalar if x is None)
_bd = [x["text"] for x in services.get_notifications(_s, company_id=1)]
_t1 = services.get_today_stats(_s, company_id=1)
_kun0 = tashkent_today_start_utc()
_gips = sum((d2(x.total_amount) for x in _s.query(FinishedProductSale).outerjoin(
    FinishedProduct, FinishedProductSale.finished_product_id == FinishedProduct.id).filter(
    FinishedProductSale.company_id == 1, func.lower(FinishedProduct.category) == "gips",
    FinishedProductSale.sold_at >= _kun0, FinishedProductSale.sold_at < _kun0 + timedelta(days=1)).all()),
    Decimal("0"))
_s.close()
check("D6 MNULL1: NULL sanali 'Tayyor' e'tiborsiz — eng so'nggi HAQIQIY sana (o'chirilgan 'Tayyor' ham, asl kabi)",
      _m1_null == 1 and len(_m1_sanalar) >= 4
      and _rep.get("QN1 MNULL1", {}).get("last_order_date") == (_o1a_c.isoformat() if _o1a_c else "?"),
      (_m1_null, len(_m1_sanalar), _rep.get("QN1 MNULL1", {}).get("last_order_date"), _o1a_c))
check("D7 MNULL2 (yagona 'Tayyor' NULL) va MNONE (buyurtmasiz) — sana yo'q",
      _rep.get("QN1 MNULL2", {}).get("last_order_date") is None and _rep.get("QN1 MNONE", {}).get("last_order_date") is None
      and "QN1 MNULL2" in _rep and "QN1 MNONE" in _rep, (_rep.get("QN1 MNULL2"), _rep.get("QN1 MNONE")))
check("D8 bildirishnoma: N3 (aniq 7 kun) BOR, N2 (> 7; B korxona chiqimi hisoblanmaydi), N4 (eski), N5 (o'chirilgan) YO'Q",
      "QN1 N3 7 kundan keyin tugaydi" in _bd and not any(x.startswith(("QN1 N2 ", "QN1 N4 ", "QN1 N5 ", "QN1 NB "))
                                                            for x in _bd), _bd)
check("D9 bugungi Gips tushumi Gips turkumli TM sotuvlarini o'z ichiga oladi (o'chirilgan mahsulotli sotuv — penoplastda)",
      _gips > 0 and _t1.get("today_gips_revenue") == round(float(_gips)), (_t1, _gips))

# ── E. Begona korxona ───────────────────────────────────────────────────────────────────────────────────────
section("E begona korxona")
_stb, _RB, _ = royxat(CB)
_s = SessionLocal()
_b_ids = {x.id for x in _s.query(Supplier).filter(Supplier.company_id == 2, Supplier.is_active == True).all()}   # noqa: E712
_s.close()
check("E1 B ro'yxati — faqat B ta'minotchilari, qiymatlar mustaqil hisob bilan AYNAN",
      _stb == 200 and set(_RB) == _b_ids and all({k: _RB[i].get(k) for k in kutilgan(i)} == kutilgan(i) for i in _b_ids),
      (sorted(_RB), sorted(_b_ids)))
check("E2 B ta'minotchisi qarzi 777.77 − 7.77 = 770", _RB.get(ID["S_B"], {}).get("debt") == 770, _RB.get(ID["S_B"]))
_rb = js(req(CB, "get", "/api/masters/kpi-report", params={"include_inactive": "true"})) or {}
check("E3 B usta KPI — faqat B ustasi", [m.get("name") for m in _rb.get("masters", [])] == ["QN1 MB"], _rb)
_nb = [x["text"] for x in (js(req(CB, "get", "/api/notifications")) or [])]
check("E4 B bildirishnomalari — B materiali (NB) bor, A materiallari yo'q",
      any(x.startswith("QN1 NB ") for x in _nb) and not any(x.startswith(("QN1 n", "QN1 m", "QN1 N3")) for x in _nb), _nb)
_r = req(CB, "post", f"/api/suppliers/{ID['S_ORD']}/payment", json={"amount": 1, "confirm_overpay": True})
check("E5 B admini A ta'minotchisiga to'lov → 404", _r.status_code == 404, _r.status_code)

# ── X. 5xx ──────────────────────────────────────────────────────────────────────────────────────────────────
section("X 5xx")
_xx = [h for h in HOLATLAR if h[1] >= 500]
check(f"X1 {len(HOLATLAR)} so'rovda 5xx yo'q", not _xx, _xx[:5])

# ── S. Statik ───────────────────────────────────────────────────────────────────────────────────────────────
section("S statik")


def _src(f):
    try:
        return inspect.getsource(getattr(f, "__wrapped__", f))
    except Exception as e:                 # noqa: BLE001
        return f"{type(e).__name__}: {e}"


_sw = _src(crud.get_suppliers_with_debt)
_sd = _src(crud.get_supplier_debt)
_sdd = _src(crud.get_supplier_payment_due_dates)
_sp = _src(crud.create_supplier_payment)
_sc = _src(services.get_chart_data)
_st_ = _src(services.get_today_stats)
_sk = _src(crud.get_masters_kpi_report)
_sn = _src(services.get_notifications)
check("S1 ro'yxat: ta'minotchi boshiga so'rov yo'q, yagona to'plam + ko'rinish",
      "get_supplier_debt(db, s.id)" not in _sw and "db.query(InventoryPurchase)" not in _sw
      and "_taminotchi_toplami(db, [s.id for s in suppliers], company_id=company_id)" in _sw
      and "_taminotchi_qarz_korinishi(_t)" in _sw)
check("S2 get_supplier_debt: o'sha yordamchilar (float yig'indi yo'q)",
      "_taminotchi_toplami(db, [supplier_id], company_id=company_id, faqat_nasiya=True)" in _sd
      and "_taminotchi_qarz_korinishi(_t)" in _sd and "sum(float(" not in _sd)
check("S3 muddatlar: ta'minotchi boshiga qarz / ta'minotchi so'rovi yo'q",
      "get_supplier_debt(db, sid" not in _sdd and "_taminotchi_toplami(db, _sids" in _sdd and "Supplier.id.in_(" in _sdd)
check("S4 ortiqcha to'lov: tiyin + bardosh", "_ortiqcha = pul_tiyin(float(data.amount) - current_debt)" in _sp
      and "if _ortiqcha > QARZ_BARDOSH and not data.confirm_overpay:" in _sp and "current_debt = debt_info[" not in _sp)
check("S5 grafik: usta boshiga so'rov yo'q (2 GROUP BY), TM sotuvi mahsuloti oldindan",
      "Order.master_id == m.id" not in _sc and _sc.count(".group_by(Order.master_id)") == 2
      and ".options(_sil_cd(FinishedProductSale.finished_product))" in _sc)
check("S6 bugun: TM sotuvi mahsuloti oldindan", ".options(_sil_td(FinishedProductSale.finished_product))" in _st_)
check("S7 usta KPI: oxirgi sana bitta GROUP BY", "last_order = db.query(" not in _sk and "_func_kpi.max(Order.completed_at)" in _sk)
check("S8 bildirishnomalar: material boshiga SUM yo'q (GROUP BY)", "InventoryMovement.inventory_id == item.id" not in _sn
      and ".group_by(InventoryMovement.inventory_id)" in _sn)
_sb = _src(crud._som_butun_int) if hasattr(crud, "_som_butun_int") else ""
check("S9 butun so'm — 0.5 YUQORIGA (HALF_UP), natija int", "ROUND_HALF_UP" in _sb and "return int(" in _sb)
_sq = _src(crud._taminotchi_qarz_korinishi) if hasattr(crud, "_taminotchi_qarz_korinishi") else ""
check("S10 qarz bardoshi — QARZ_BARDOSH (mijoz qarzi bilan bir qoida)", "QARZ_BARDOSH" in _sq)
_stt = _src(crud._taminotchi_toplami) if hasattr(crud, "_taminotchi_toplami") else ""
check("S11 to'plam: korxona berilsa ota (ta'minotchi) orqali cheklov — xaridlar va to'lovlar (2 joy)",
      _stt.count("Supplier.company_id == company_id") == 2 and _stt.count(".join(Supplier, Supplier.id == ") == 2)
check("S12 muddatlar: ta'minotchilar IN so'rovi korxona bilan; usta KPI oxirgi sana — ota (usta) orqali korxona",
      "_sq = _sq.filter(Supplier.company_id == company_id)" in _sdd
      and "_oxq = _oxq.join(Master, Master.id == Order.master_id).filter(Master.company_id == company_id)" in _sk)

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
engine.dispose()
sys.exit(1 if FAIL else 0)
