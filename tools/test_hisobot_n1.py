#!/usr/bin/env python3
"""test_hisobot_n1.py — kech97 (2026-09-27), 111-band (oylik hisobotda hodim / usta boshiga so'rovlar) + 116-band 2-qadam
(majburiyatlar holati).

NIMA UCHUN KERAK
----------------
O'LCHANGAN (kech97 `work/probe116.py` KENG bosqichi, asl = zip 90, SQLite = PG; +10 usta / hodim / majburiyat):
  * oylik hisobot — hodim boshiga 4 so'rov (to'lov tarixi, `get_employee`, oylik tuzatish, avans yig'indisi), usta boshiga
    2 (oy buyurtmalari, TM sotuvlari): `/api/finance/report` +60, tarix (12 oy) +280, brak tahlili +160, …;
  * `get_company_obligations_status` — majburiyat × 3 oy ALOHIDA xarajat so'rovi (+30), 3 oylik hisobot har biri O'Z
    keshi bilan (Qarzdorlar sahifasi, Moliya qarz xulosasi, PDF).
YECHIM (texnik): hodim / usta ma'lumotlari bir necha IN / GROUP BY so'rovi bilan — tanlash qoidasi AYNAN (to'lov tarixi —
`crud._kompensatsiya_tanla` yagona yordamchi, tarix yo'q — joriy qiymatlar; tuzatish — birinchi yozuv; avans — bazadagi
SUM); majburiyat xarajatlari oy boshiga bitta so'rov; majburiyatlar holati hisobot keshi ichida (3 oy — bitta kesh).
ISBOT (work/dump116.py, 427 chaqiruv, ESKI ↔ YANGI kod bir bazada): SQLite AYNAN; PG — mazmun farqi 0.

BO'LIMLAR
---------
  A MIQYOS: +5 hodim / usta / majburiyat — hisobot, usta KPI, majburiyatlar, 5 marshrut so'rovlari O'ZGARMAYDI
    (nazorat: har qator uchun alohida o'qish o'sadi);
  B to'g'rilik: hodimlar (tarix tanlash, joriy qiymat, tuzatish, avans, summa) — mustaqil (asl yakka funksiyalar) bilan;
    ustalar (oy foydasi) — mustaqil; majburiyatlar (to'langan / qarz / oxirgi to'lov / holat) — mustaqil;
    kesh bilan / keshsiz (HISOBOT_KESHI_YOQIQ=False) AYNAN; begona korxona;
  C majburiyatlar: 3 oylik hisobot BITTA kesh bilan; X 5xx yo'q; S statik.

ISHLATISH
---------
    python3 tools/test_hisobot_n1.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_hisobot_n1.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import json
import inspect
import tempfile
import contextlib
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hisobot_n1_test"
_T = tempfile.mkdtemp(prefix="hn1_")
_DB = os.path.join(_T, "hisobot_n1_test.db")

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
from sqlalchemy import event                       # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (UserRole, Inventory, Project, Order, Master, Employee, PayType,        # noqa: E402
                    EmployeeCompensationHistory, EmployeeMonthlyAdjustment, EmployeeAdvance,
                    RecurringObligation, ExpenseTransaction, FinishedProduct, FinishedProductSale,
                    StockSource, ProductionStatus, OrderStatus)
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


def jsonla(x):
    return json.dumps(json.loads(json.dumps(x, default=str, sort_keys=True)), sort_keys=True)


HOZIR = datetime.utcnow()
# kech105 (9 + 50-band, "Toshkent vaqti bo'yicha"): hisobot davri — Toshkent devor soati (UTC + 5), server kabi; saqlanadigan vaqt — UTC `HOZIR`
_HOZIR_T = HOZIR + timedelta(hours=5)
Y, M = _HOZIR_T.year, _HOZIR_T.month


def oy_oldin(y, m, k):
    for _ in range(k):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return y, m


OY1, OY2 = oy_oldin(Y, M, 1), oy_oldin(Y, M, 2)
KEYIN = (Y + (M == 12), 1 if M == 12 else M + 1)
_OY1_KUN = datetime(OY1[0], OY1[1], 14, 9, 0, 0)
_OY2_KUN = datetime(OY2[0], OY2[1], 20, 11, 0, 0)

# ── Fikstura ────────────────────────────────────────────────────────────────────────────────────────────────
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="HN1 Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "HN1_a", "Parol123!", UserRole.ADMIN, "HN1 A", company_id=1)
    auth.create_user(_db, "HN1_b", "Parol123!", UserRole.ADMIN, "HN1 B", company_id=2)
_pa = Inventory(company_id=1, item_name="HN1 Penoplast A", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
_pb = Inventory(company_id=2, item_name="HN1 Penoplast B", unit="blok", stock_quantity=100_000, price_per_unit=400_000,
                volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
_db.add_all([_pa, _pb])
_db.commit()
PA, PB = _pa.id, _pb.id
_prj = {}
for cid in (1, 2):
    p = Project(company_id=cid, client_name=f"HN1 {cid}", project_name=f"HN1 {cid}", total_budget=0, total_paid=0)
    _db.add(p)
    _db.commit()
    _prj[cid] = p.id
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c


CA, CB = _kir("HN1_a"), _kir("HN1_b")
QADAM = []
ID = {"hodim": [], "usta": [], "ob": []}
_N = {"n": 0}


def _buyurtma(klient, cid, peno, master_id, i, tayyor=True):
    _N["n"] += 1
    t = {"project_id": _prj[cid], "order_type": "product", "loy_kg": 0, "master_id": master_id, "items": [
        {"name": f"HN1 panel {_N['n']}", "category": "panel", "width": 30, "thickness": 5, "quantity": 3 + i,
         "unit_price": 61_000.5 + 10 * i, "is_coated": False, "penoplast_id": peno}]}
    r = req(klient, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
    QADAM.append(("buyurtma", r.status_code))
    oid = (js(r) or {}).get("id") if r.status_code == 200 else None
    if oid and tayyor:
        r2 = req(klient, "post", f"/api/orders/{oid}/ready")
        QADAM.append(("tayyor", r2.status_code))
    return oid


def hodim_qosh(n, teg, cid=1):
    """n ta hodim (turli to'lov turlari), to'lov tarixi, tuzatish, avans."""
    s = SessionLocal()
    ids = []
    for i in range(n):
        tur = [PayType.FIXED, PayType.PERCENT_SALES, PayType.FIXED_PLUS_COATING, PayType.PERCENT_PROFIT][i % 4]
        e = Employee(company_id=cid, name=f"HN1 {teg}{i}", position="Ishchi", pay_type=tur, fixed_amount=1_000_000 + i,
                     percent_value=1.5 + i, per_unit_rate=500, per_unit_type="metr", extra_monthly=(50_000 if i % 3 == 0 else 0),
                     is_active=True, hire_date=HOZIR - timedelta(days=120))
        s.add(e)
        s.flush()
        ids.append(e.id)
        if i % 2 == 0:      # tarix: 2 oy oldin (amal qiladi), keyingi oy (hali amal qilmaydi)
            s.add(EmployeeCompensationHistory(employee_id=e.id, effective_year=OY2[0], effective_month=OY2[1], pay_type=tur,
                                              fixed_amount=900_000 + i, percent_value=2.0 + i, per_unit_rate=400,
                                              per_unit_type="metr", extra_monthly=0))
            s.add(EmployeeCompensationHistory(employee_id=e.id, effective_year=KEYIN[0], effective_month=KEYIN[1],
                                              pay_type=PayType.FIXED, fixed_amount=5_000_000, percent_value=0,
                                              per_unit_rate=0, per_unit_type="metr", extra_monthly=0))
        if i % 3 == 1:
            s.add(EmployeeMonthlyAdjustment(employee_id=e.id, year=Y, month=M, reduction_amount=100_000.5 + i,
                                            reason="HN1 kelmadi", bonus_amount=(25_000 if i % 2 else 0), bonus_reason="HN1"))
        s.add(EmployeeAdvance(employee_id=e.id, amount=200_000.25 + i, date=HOZIR, notes="HN1"))
        if i % 2:
            s.add(EmployeeAdvance(employee_id=e.id, amount=50_000, date=HOZIR - timedelta(minutes=5), notes="HN1 2"))
        s.add(EmployeeAdvance(employee_id=e.id, amount=999_999, date=_OY1_KUN, notes="HN1 o'tgan oy"))
    s.commit()
    s.close()
    ID["hodim"].extend(ids)
    return ids


def usta_qosh(n, teg, cid=1):
    """n ta usta (KPI > 0): har biriga shu oy "Tayyor" buyurtma va TM sotuvi."""
    s = SessionLocal()
    ids = []
    for i in range(n):
        m = Master(company_id=cid, name=f"HN1 {teg}{i}", phone=f"+9989{cid}{len(ID['usta']) + i:07d}", cashback_percent=0,
                   kpi_percent=3.0 + i, is_active=True)
        s.add(m)
        s.flush()
        ids.append(m.id)
        fp = FinishedProduct(company_id=cid, name=f"HN1 TM {teg}{i}", category="dona", quantity=5, produced_quantity=5,
                             unit="dona", unit_price=1_000, cost_price=2_500, unit_cost_stable=500.0,
                             source=StockSource.PRODUCED, production_status=ProductionStatus.READY,
                             finished_production_at=HOZIR)
        s.add(fp)
        s.flush()
        s.add(FinishedProductSale(company_id=cid, finished_product_id=fp.id, product_name=fp.name, quantity=1, unit="dona",
                                  unit_price=1_200.5, total_amount=1_200.5 + i, cost_amount=500, sold_at=HOZIR,
                                  payment_method="naqd", master_id=m.id))
    s.commit()
    s.close()
    for i, mid in enumerate(ids):
        _buyurtma(CA if cid == 1 else CB, cid, PA if cid == 1 else PB, mid, i)
    ID["usta"].extend(ids)
    return ids


def ob_qosh(n, teg, cid=1):
    """n ta doimiy majburiyat: joriy oy qisman to'langan, o'tgan oy to'liq, 2 oy oldin to'lanmagan."""
    s = SessionLocal()
    for i in range(n):
        kat = f"hn1_{teg}{i}"
        s.add(RecurringObligation(company_id=cid, category=kat, label=f"HN1 {teg}{i}", icon="📦",
                                  monthly_target=100_000 + i, due_day=5 + i, is_active=True,
                                  created_at=HOZIR.replace(day=1) - timedelta(days=100)))
        s.add(ExpenseTransaction(company_id=cid, date=HOZIR, category=kat, amount=40_000.5 + i, source="manual"))
        s.add(ExpenseTransaction(company_id=cid, date=HOZIR - timedelta(minutes=3), category=kat, amount=10_000, source="manual"))
        s.add(ExpenseTransaction(company_id=cid, date=_OY1_KUN, category=kat, amount=100_000 + i, source="manual"))
        ID["ob"].append(kat)
    s.commit()
    s.close()


hodim_qosh(4, "h")
usta_qosh(3, "u")
ob_qosh(3, "o")
# maxsus: yaratilishidan OLDINGI oy tekshirilmaydigan majburiyat; to'liq to'langan; faol emas; B korxona
_s = SessionLocal()
_s.add(RecurringObligation(company_id=1, category="hn1_yangi", label="HN1 yangi", icon="📦", monthly_target=70_000,
                           due_day=3, is_active=True, created_at=_HOZIR_T.replace(day=1) + timedelta(hours=1) - timedelta(hours=5)))
_s.add(RecurringObligation(company_id=1, category="hn1_tolik", label="HN1 to'liq", icon="📦", monthly_target=30_000,
                           due_day=3, is_active=True, created_at=HOZIR.replace(day=1) - timedelta(days=100)))
for _oy in (HOZIR, _OY1_KUN, _OY2_KUN):
    _s.add(ExpenseTransaction(company_id=1, date=_oy, category="hn1_tolik", amount=30_000, source="manual"))
_s.add(RecurringObligation(company_id=1, category="hn1_nofaol", label="HN1 nofaol", icon="📦", monthly_target=10_000,
                           due_day=3, is_active=False, created_at=HOZIR.replace(day=1) - timedelta(days=100)))
_s.add(RecurringObligation(company_id=2, category="hn1_o0", label="HN1 B (A bilan bir xil kod)", icon="📦",
                           monthly_target=66_000, due_day=9, is_active=True,
                           created_at=HOZIR.replace(day=1) - timedelta(days=100)))
_s.add(ExpenseTransaction(company_id=2, date=HOZIR, category="hn1_o0", amount=5_000, source="manual"))
_s.commit()
# bir hodimga IKKI tuzatish yozuvi (bir oy) — birinchisi (kichik id) olinadi (asl `.first()`)
_e_ikki = ID["hodim"][0]
_s.add(EmployeeMonthlyAdjustment(employee_id=_e_ikki, year=Y, month=M, reduction_amount=11_111, reason="birinchi",
                                 bonus_amount=0))
_s.commit()
_s.add(EmployeeMonthlyAdjustment(employee_id=_e_ikki, year=Y, month=M, reduction_amount=22_222, reason="ikkinchi",
                                 bonus_amount=0))
_s.commit()
# tarix: bir oyda IKKI yozuv (teng oy) — kattaroq id olinadi
_e_teng = ID["hodim"][2]
_s.add(EmployeeCompensationHistory(employee_id=_e_teng, effective_year=OY1[0], effective_month=OY1[1],
                                   pay_type=PayType.FIXED, fixed_amount=700_000, percent_value=0, per_unit_rate=0,
                                   per_unit_type="metr", extra_monthly=0))
_s.commit()
_s.add(EmployeeCompensationHistory(employee_id=_e_teng, effective_year=OY1[0], effective_month=OY1[1],
                                   pay_type=PayType.FIXED, fixed_amount=777_000, percent_value=0, per_unit_rate=0,
                                   per_unit_type="metr", extra_monthly=0))
_s.commit()
_s.close()
# o'tgan oy tuzatishi (joriy oyga tushmasligi kerak), jarayondagi (Tayyor EMAS) usta buyurtmasi, o'tgan oy TM sotuvi
_s = SessionLocal()
_s.add(EmployeeMonthlyAdjustment(employee_id=ID["hodim"][3], year=OY1[0], month=OY1[1], reduction_amount=33_333,
                                 reason="o'tgan oy", bonus_amount=0))
_fpo = FinishedProduct(company_id=1, name="HN1 TM o'tgan", category="dona", quantity=5, produced_quantity=5, unit="dona",
                       unit_price=1_000, cost_price=2_500, unit_cost_stable=500.0, source=StockSource.PRODUCED,
                       production_status=ProductionStatus.READY, finished_production_at=_OY1_KUN)
_s.add(_fpo)
_s.flush()
_s.add(FinishedProductSale(company_id=1, finished_product_id=_fpo.id, product_name=_fpo.name, quantity=1, unit="dona",
                           unit_price=90_000, total_amount=90_000, cost_amount=500, sold_at=_OY1_KUN, payment_method="naqd",
                           master_id=ID["usta"][0]))
_s.commit()
_s.close()
O_JARAYON = _buyurtma(CA, 1, PA, ID["usta"][0], 7, tayyor=False)
# "Topshirilgan" (DELIVERED) — completed_at shu oyda, lekin holat READY EMAS: usta KPI ga KIRMAYDI (asl shart)
O_TOPSH = _buyurtma(CA, 1, PA, ID["usta"][1], 8)
_s = SessionLocal()
_s.execute(Order.__table__.update().where(Order.__table__.c.id == O_TOPSH).values(status=OrderStatus.DELIVERED))
# joriy oyda amal qiladigan to'lov tarixi (effective = shu oy) — tarixsiz hodimga (joriy qiymat EMAS, shu yozuv olinadi)
_e_joriy = ID["hodim"][3]
_s.add(EmployeeCompensationHistory(employee_id=_e_joriy, effective_year=Y, effective_month=M, pay_type=PayType.FIXED,
                                   fixed_amount=1_234_567, percent_value=0, per_unit_rate=0, per_unit_type="metr",
                                   extra_monthly=0))
_s.commit()
_s.close()
_bh = hodim_qosh(2, "bh", cid=2)
_bu = usta_qosh(1, "bu", cid=2)
# BUZILGAN (Core): B korxona "Tayyor" buyurtmasi A ustasiga biriktirilgan — A ning usta KPI siga KIRMAYDI (korxona sharti)
_s = SessionLocal()
_ob_b = _s.query(Order).filter(Order.company_id == 2, Order.status == OrderStatus.READY).order_by(Order.id).first()
if _ob_b:
    _s.execute(Order.__table__.update().where(Order.__table__.c.id == _ob_b.id).values(master_id=ID["usta"][2]))
    _s.commit()
_s.close()

section("F fikstura")
check(f"F1 fikstura qadamlari 200 ({len(QADAM)} ta)", all(k == 200 for _, k in QADAM), [q for q in QADAM if q[1] != 200][:5])

MARSHRUT = [
    ("report", "/api/finance/report", {"year": Y, "month": M}),
    ("oblst", "/api/obligations/status", {"year": Y, "month": M}),
    ("debts", "/debts", None),
    ("debtsum", "/api/finance/debt-summary", {"year": Y, "month": M}),
    ("health", "/api/reports/business-health", None),
    ("history", "/api/finance/history", None),
]
FUNK = [
    ("report", lambda s: services.get_monthly_report(s, Y, M, company_id=1)),
    ("report1", lambda s: services.get_monthly_report(s, OY1[0], OY1[1], company_id=1)),
    ("usta", lambda s: services.calculate_monthly_master_kpi(s, Y, M, company_id=1)),
    ("obl", lambda s: services.get_company_obligations_status(s, Y, M, company_id=1)),
    ("oblNone", lambda s: services.get_company_obligations_status(s, Y, M, company_id=None)),
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


def nazorat():
    """Asl (qator boshiga) o'qish: har hodim uchun yakka funksiyalar + tuzatish so'rovi, har usta uchun oy buyurtmalari."""
    s = SessionLocal()
    try:
        with sanoq() as sq:
            for e in s.query(Employee).filter(Employee.company_id == 1).all():
                crud.get_employee_compensation_for_month(s, e.id, Y, M)
                services.get_employee_advances_total(s, e.id, Y, M)
                s.query(EmployeeMonthlyAdjustment).filter(EmployeeMonthlyAdjustment.employee_id == e.id,
                                                          EmployeeMonthlyAdjustment.year == Y,
                                                          EmployeeMonthlyAdjustment.month == M).first()
        return sq["n"]
    finally:
        s.close()


# ── A. Miqyos ───────────────────────────────────────────────────────────────────────────────────────────────
section("A miqyos: +5 hodim / usta / majburiyat — so'rovlar o'zgarmaydi")
olchov()        # qizdirish
N0, J0 = olchov()
Z0 = nazorat()
hodim_qosh(5, "m")
usta_qosh(5, "m")
ob_qosh(5, "m")
N1, J1 = olchov()
Z1 = nazorat()
check("A0 fikstura qadamlari 200 (+5 usta buyurtmasi)", all(k == 200 for _, k in QADAM), [q for q in QADAM if q[1] != 200][:5])
for i, k in enumerate(N0, 1):
    check(f"A{i} {k}: {N0[k]} -> {N1[k]} so'rov (o'zgarmaydi)", N0[k] == N1[k] and not str(N0[k]).startswith("XATO"),
          (N0[k], N1[k]))
check(f"A20 nazorat — qator boshiga o'qish o'sadi: {Z0} -> {Z1} (>= +15)", Z1 - Z0 >= 15, (Z0, Z1))
check("A21 marshrutlar 200", all(v == 200 for v in J1.values()), J1)

# ── B. To'g'rilik ───────────────────────────────────────────────────────────────────────────────────────────
section("B to'g'rilik — hodimlar (asl yakka funksiyalar bilan)")
_s = SessionLocal()
_rep = services.get_monthly_report(_s, Y, M, company_id=1)
_emp = services.calculate_monthly_employee_pay(
    _s, Y, M, float(_rep.get("daromad", 0) or 0), 1_000_000.0, 10.0, 5.0, 1.0, 7.0, company_id=1)
_br = {b["employee_id"]: b for b in _emp["breakdown"]}
_ok_tur = _ok_av = _ok_adj = _ok_sum = True
_det = []
_kutilgan_royxat = []
for e in _s.query(Employee).filter(Employee.company_id == 1, Employee.is_active == True).all():   # noqa: E712
    comp = crud.get_employee_compensation_for_month(_s, e.id, Y, M)
    adj = _s.query(EmployeeMonthlyAdjustment).filter(EmployeeMonthlyAdjustment.employee_id == e.id,
                                                     EmployeeMonthlyAdjustment.year == Y,
                                                     EmployeeMonthlyAdjustment.month == M).order_by(
        EmployeeMonthlyAdjustment.id).first()
    avans = services.get_employee_advances_total(_s, e.id, Y, M)
    tur = comp["pay_type"]
    if tur == PayType.FIXED:
        amount = float(comp["fixed_amount"] or 0)
    elif tur == PayType.PERCENT_SALES:
        amount = float(_rep.get("daromad", 0) or 0) * float(comp["percent_value"] or 0) / 100
    elif tur == PayType.PERCENT_PROFIT:
        amount = 1_000_000.0 * float(comp["percent_value"] or 0) / 100
    elif tur == PayType.FIXED_PLUS_COATING:
        amount = float(comp["fixed_amount"] or 0) + 7.0 * float(comp["per_unit_rate"] or 1000)
    else:
        amount = 10.0 * float(comp["per_unit_rate"] or 0)
    if comp["extra_monthly"]:
        amount += float(comp["extra_monthly"])
    red = float(adj.reduction_amount or 0) if adj else 0
    bon = float(adj.bonus_amount or 0) if adj else 0
    if red > 0:
        amount = max(0, amount - red)
    if bon > 0:
        amount += bon
    if amount > 0 or red > 0 or bon > 0:
        _kutilgan_royxat.append(e.id)
        b = _br.get(e.id)
        if not b or b["pay_type"] != tur.value:
            _ok_tur = False
            _det.append(("tur", e.id, b and b["pay_type"], tur.value))
        if not b or b["avans"] != round(avans):
            _ok_av = False
            _det.append(("avans", e.id, b and b["avans"], avans))
        if not b or b["adjustment"] != (round(red) if red else 0) or b["bonus"] != (round(bon) if bon else 0):
            _ok_adj = False
            _det.append(("tuzatish", e.id, b and (b["adjustment"], b["bonus"]), (red, bon)))
        if not b or b["amount"] != round(amount) or b["qolgan"] != round(amount - avans):
            _ok_sum = False
            _det.append(("summa", e.id, b and (b["amount"], b["qolgan"]), (amount, amount - avans)))
check("B1 hodimlar ro'yxati = mustaqil (summa > 0 yoki tuzatish bor; B korxona yo'q)",
      sorted(_br) == sorted(_kutilgan_royxat) and not (set(_br) & set(_bh)), (sorted(_br), sorted(_kutilgan_royxat)))
check("B2 to'lov turi = `get_employee_compensation_for_month` (tarix / joriy)", _ok_tur, _det[:4])
check("B3 avans = `get_employee_advances_total` (shu oy, SUM)", _ok_av, _det[:4])
check("B4 tuzatish / bonus — birinchi yozuv (kichik id)", _ok_adj, _det[:4])
check("B5 summa va qolgan — mustaqil formula", _ok_sum, _det[:4])
_e0 = _br.get(ID["hodim"][0])
check("B6 bir oyda ikki tuzatish — BIRINCHISI (100 000.5 — 'kelmadi' EMAS, 11 111 — 'birinchi')",
      _e0 is not None and _e0["adjustment"] == 11_111 and _e0["adjustment_reason"] == "birinchi", _e0)
_c_teng = crud.get_employee_compensation_for_month(_s, _e_teng, Y, M)
check("B7 tarix: teng oyda ikki yozuv — kattaroq id (777 000); keyingi oy yozuvi (5 000 000) hali amal qilmaydi",
      float(_c_teng["fixed_amount"]) == 777_000 and _br.get(_e_teng, {}).get("amount") is not None, _c_teng)
check("B7b tarix: shu oyda amal qiladigan yozuv (effective = joriy oy) olinadi — 1 234 567 (mustaqil qiymat)",
      _br.get(_e_joriy, {}).get("amount") == 1_234_567 and _br.get(_e_joriy, {}).get("pay_type") == "fixed",
      _br.get(_e_joriy))
_e1 = ID["hodim"][1]
_c1 = crud.get_employee_compensation_for_month(_s, _e1, Y, M)
check("B8 tarixsiz hodim — joriy qiymatlar (Employee jadvali)", float(_c1["percent_value"]) == 2.5, _c1)
check("B9 hodimlar jami = breakdown summalari (round)", _emp["total"] == round(sum(
    b["amount"] for b in _emp["breakdown"])) or abs(_emp["total"] - sum(b["amount"] for b in _emp["breakdown"])) <= len(
    _emp["breakdown"]), _emp["total"])

section("B ustalar (oy foydasi — mustaqil)")
_uk = services.calculate_monthly_master_kpi(_s, Y, M, company_id=1)
_kut = []
for m in _s.query(Master).filter(Master.company_id == 1, Master.is_active == True, Master.kpi_percent > 0).all():   # noqa: E712
    foyda = 0.0
    for o in _s.query(Order).filter(Order.master_id == m.id, Order.status == OrderStatus.READY,
                                    Order.company_id == 1).all():
        if o.completed_at and ((o.completed_at + timedelta(hours=5)).year,
                               (o.completed_at + timedelta(hours=5)).month) == (Y, M):      # kech105: Toshkent oyi
            foyda += float(services.calculate_order_profit(_s, o.id).get("foyda", 0))
    for sv in _s.query(FinishedProductSale).filter(FinishedProductSale.master_id == m.id).all():
        if sv.sold_at and ((sv.sold_at + timedelta(hours=5)).year,
                           (sv.sold_at + timedelta(hours=5)).month) == (Y, M):      # kech105: Toshkent oyi
            foyda += float(sv.total_amount or 0) - float(sv.cost_amount or 0)
    if foyda > 0:
        _kut.append({"master_name": m.name, "kpi_percent": m.kpi_percent, "monthly_profit": round(foyda),
                     "kpi_amount": round(foyda * m.kpi_percent / 100)})
check("B10 usta KPI breakdown = mustaqil (ustalar, oy foydasi, KPI)", jsonla(_uk["breakdown"]) == jsonla(_kut),
      (_uk["breakdown"][:3], _kut[:3]))
check("B11 usta KPI — B korxona ustasi yo'q", not any(b["master_name"].startswith("HN1 bu") for b in _uk["breakdown"]))

section("B majburiyatlar (mustaqil)")
_ob = services.get_company_obligations_status(_s, Y, M, company_id=1)
_kut_ob = []
for obl in _s.query(RecurringObligation).filter(RecurringObligation.company_id == 1, RecurringObligation.is_active == True).all():   # noqa: E712
    t = float(obl.monthly_target or 0)
    if t <= 0:
        continue
    for (yy, mm) in ((Y, M), OY1, OY2):
        import calendar as _cal
        # kech105: oy oxiri — Toshkent kalendari (UTC ko'rinishida − 5 soat), server kabi
        if obl.created_at and obl.created_at > datetime(yy, mm, _cal.monthrange(yy, mm)[1], 23, 59, 59) - timedelta(hours=5):
            continue
        txs = [x for x in _s.query(ExpenseTransaction).filter(ExpenseTransaction.company_id == 1,
                                                                ExpenseTransaction.category == obl.category).all()
               if ((x.date + timedelta(hours=5)).year, (x.date + timedelta(hours=5)).month) == (yy, mm)]
        paid = sum(float(x.amount or 0) for x in txs)
        debt = max(0, t - paid)
        if debt <= 0.5:
            continue
        _kut_ob.append((obl.category, yy, mm, round(t), round(paid), round(debt),
                        max(x.date for x in txs).isoformat() if txs else None))
_bor = sorted((r["category"], r["year"], r["month"], r["target"], r["paid"], r["debt"], r["last_payment"])
              for r in _ob["recurring"])
check("B12 majburiyatlar (kategoriya, oy, maqsad, to'langan, qarz, oxirgi to'lov) = mustaqil",
      _bor == sorted(_kut_ob), (_bor[:4], sorted(_kut_ob)[:4]))
check("B13 majburiyatlar: yaratilishidan oldingi oy / to'liq to'langan / nofaol / B korxona — yo'q",
      not any(r["category"] in ("hn1_tolik", "hn1_nofaol") for r in _ob["recurring"])
      and [(r["year"], r["month"]) for r in _ob["recurring"] if r["category"] == "hn1_yangi"] == [(Y, M)]
      and all(r["target"] != 66_000 for r in _ob["recurring"] if r["category"] == "hn1_o0"), _ob["recurring"][:6])
check("B14 majburiyatlar ro'yxati (year, month) tartibida, jami = qarzlar yig'indisi",
      [(r["year"], r["month"]) for r in _ob["recurring"]] == sorted((r["year"], r["month"]) for r in _ob["recurring"])
      and _ob["total_recurring_debt"] == round(sum(r["debt"] for r in _ob["recurring"])))
_s.close()

section("B kesh bilan / keshsiz AYNAN")
KESH_F = [
    ("report", lambda s: services.get_monthly_report(s, Y, M, company_id=1)),
    ("report1", lambda s: services.get_monthly_report(s, OY1[0], OY1[1], company_id=1)),
    ("reportNone", lambda s: services.get_monthly_report(s, Y, M, company_id=None)),
    ("usta", lambda s: services.calculate_monthly_master_kpi(s, Y, M, company_id=1)),
    ("ustaNone", lambda s: services.calculate_monthly_master_kpi(s, Y, M, company_id=None)),
    ("obl", lambda s: services.get_company_obligations_status(s, Y, M, company_id=1)),
    ("obl1", lambda s: services.get_company_obligations_status(s, OY1[0], OY1[1], company_id=1)),
    ("oblB", lambda s: services.get_company_obligations_status(s, Y, M, company_id=2)),
    ("oblNone", lambda s: services.get_company_obligations_status(s, Y, M, company_id=None)),
    ("fulldebt", lambda s: services.get_full_debt_summary(s, Y, M, company_id=1)),
    ("history3", lambda s: services.get_finance_history(s, 3, company_id=1)),
]


def _chaq(fn):
    s = SessionLocal()
    try:
        return jsonla(fn(s))
    except Exception as e:             # noqa: BLE001
        return f"XATO {type(e).__name__}: {e}"
    finally:
        s.rollback()
        s.close()


for i, (k, fn) in enumerate(KESH_F, 20):
    a = _chaq(fn)
    services.HISOBOT_KESHI_YOQIQ = False
    try:
        b = _chaq(fn)
    finally:
        services.HISOBOT_KESHI_YOQIQ = True
    check(f"B{i} {k}: kesh bilan / keshsiz AYNAN", a == b and not a.startswith("XATO"), (a[:200], b[:200]))

# ── C. majburiyatlar — bitta kesh ───────────────────────────────────────────────────────────────────────────
section("C majburiyatlar holati: 3 oylik hisobot BITTA kesh bilan")
_kesh_lar = []
_asl_rep = services.get_monthly_report


def _kuzat(db, *a, **k):
    _kesh_lar.append(id(services._hk(db)) if services._hk(db) is not None else None)
    return _asl_rep(db, *a, **k)


services.get_monthly_report = _kuzat
try:
    _s = SessionLocal()
    _r = services.get_company_obligations_status(_s, Y, M, company_id=1)
    _s.close()
finally:
    services.get_monthly_report = _asl_rep
check("C1 3 oylik hisobot chaqirildi va HAMMASI bitta (faol) kesh ichida",
      len(_kesh_lar) == 3 and None not in _kesh_lar and len(set(_kesh_lar)) == 1, _kesh_lar)
_s = SessionLocal()
with sanoq() as _sq:
    services.get_company_obligations_status(_s, Y, M, company_id=1)
_s.close()
_yakka = 0
for (yy, mm) in ((Y, M), OY1, OY2):
    _s = SessionLocal()
    with sanoq() as _sq2:
        services.get_monthly_report(_s, yy, mm, company_id=1)
    _yakka += _sq2["n"]
    _s.close()
check(f"C2 majburiyatlar holati ({_sq['n']}) < 3 ta alohida oylik hisobot ({_yakka}) — umumiy kesh", _sq["n"] < _yakka,
      (_sq["n"], _yakka))

# ── D. begona korxona (API) ─────────────────────────────────────────────────────────────────────────────────
section("D begona korxona")
_ob_b = js(req(CB, "get", "/api/obligations/status", params={"year": Y, "month": M})) or {}
check("D1 B majburiyatlari — faqat B (A ning bir xil kodli majburiyati to'lovi aralashmaydi)",
      [(r["category"], r["paid"]) for r in _ob_b.get("recurring", []) if r["year"] == Y and r["month"] == M]
      == [("hn1_o0", 5_000)], _ob_b.get("recurring"))
_rb = js(req(CB, "get", "/api/finance/report", params={"year": Y, "month": M})) or {}
_hb = [b.get("employee_id") for b in (_rb.get("hodimlar_moslashuvchan_breakdown") or [])]
check("D2 B oylik hisoboti hodimlari — faqat B", sorted(_hb) == sorted(_bh), (_hb, _bh))

# ── X. 5xx ──────────────────────────────────────────────────────────────────────────────────────────────────
section("X 5xx")
_5 = [h for h in HOLATLAR if h[1] >= 500]
check("X1 hech bir so'rov 5xx emas", not _5, _5[:5])

# ── S. statik ───────────────────────────────────────────────────────────────────────────────────────────────
section("S statik")


def _src(f):
    try:
        return inspect.getsource(f)
    except Exception:                  # noqa: BLE001
        return ""


_ep = _src(services.calculate_monthly_employee_pay)
check("S1 hodimlar: yakka o'qishlar YO'Q (tarix / avans / tuzatish hodim boshiga)",
      "get_employee_compensation_for_month(" not in _ep and "get_employee_advances_total(" not in _ep
      and "EmployeeMonthlyAdjustment.employee_id == e.id" not in _ep)
check("S2 hodimlar: oldindan o'qish (IN) va yagona tanlash qoidasi",
      "EmployeeCompensationHistory.employee_id.in_(" in _ep and "EmployeeMonthlyAdjustment.employee_id.in_(" in _ep
      and "EmployeeAdvance.employee_id.in_(" in _ep and "_crud._kompensatsiya_tanla(" in _ep
      and "_kompensatsiya_tanla(rows, year, month)" in _src(crud.get_employee_compensation_for_month))
_mk = _src(services.calculate_monthly_master_kpi)
check("S3 ustalar: oy buyurtmalari va TM sotuvlari bitta IN so'rovi bilan",
      "Order.master_id.in_(" in _mk and "_FPS_kpi.master_id.in_(" in _mk and "Order.master_id == m.id" not in _mk
      and "_FPS_kpi.master_id == m.id" not in _mk)
_ob_src = _src(services.get_company_obligations_status)
check("S4 majburiyatlar: xarajatlar oy boshiga bitta so'rov (kategoriyalar ro'yxati)",
      "ExpenseTransaction.category.in_(" in _ob_src and "ExpenseTransaction.category == obl.category" not in _ob_src)
check("S6 hodimlar: IN so'rovlari korxona berilsa ota (hodim) orqali cheklangan (3 ta)",
      all(f"join(Employee, Employee.id == {x}.employee_id)" in _ep
          for x in ("EmployeeCompensationHistory", "EmployeeMonthlyAdjustment", "EmployeeAdvance")))
check("S7 usta KPI hisobot keshi bilan o'ralgan (alohida chaqiruvda ham oldindan o'qish)",
      getattr(services.calculate_monthly_master_kpi, "__wrapped__", None) is not None)
check("S5 majburiyatlar holati hisobot keshi bilan o'ralgan",
      getattr(services.get_company_obligations_status, "__wrapped__", None) is not None
      and "get_company_obligations_status = _hisobot_keshi_bilan(get_company_obligations_status)" in open(
          os.path.join(ROOT, "services.py"), encoding="utf-8").read())

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
