#!/usr/bin/env python3
"""
test_hodim_tarix_korxona.py — kech109 darvozasi: 10b E-2 / E-3 — chaqirilmaydigan korxonasiz o'qish funksiyalari.

NIMA UCHUN KERAK (O'LCHANGAN — kech107 toifalash + kech109 `grep`; asl kod `bd0b48c`)
--------------------------------------------------------------------------------
E-2 `crud.get_employee_compensation_for_month(db, employee_id, year, month)` — korxona parametri ham, tekshiruvi ham
    yo'q; dasturda chaqirilmaydi (faqat testlar "oracle" sifatida). Kelajakdagi marshrut uni `auth.employee_of_company`
    siz chaqirsa — A korxona B hodimining to'lov tarixini (tur, summa, foiz) ko'rardi (asl: B hodimi A nomidan — B ning
    haqiqiy summasi qaytadi).
E-3 `crud.get_return_item(db, return_id)` — loyihaning hech bir joyida chaqirilmaydi, ID bo'yicha korxonasiz qaytaradi.

YECHIM (texnik — Claude): E-2 — `company_id` MAJBURIY kalit so'zli parametr (berilmasa TypeError, None — ValueError),
tarix va zaxira (joriy qiymat) faqat shu korxona hodimidan; E-3 — o'lik funksiya olib tashlandi.

REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi.
"""
import os
import re
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hodim_tarix_korxona_test"
_DB = os.path.join(tempfile.gettempdir(), "hodim_tarix_korxona_test.db")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
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
    import crud                                    # noqa: E402
APP = main.app                                     # ilova ishga tushdi (jadvallar, asosiy korxona)
from database import SessionLocal                  # noqa: E402
from models import Employee, EmployeeCompensationHistory, PayType  # noqa: E402
from production_models import Company              # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


YIL, OY = 2026, 9
db = SessionLocal()
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="HTK B korxona"))
    db.commit()
EA = Employee(company_id=1, name="HTK A hodim", position="Ishchi", pay_type=PayType.FIXED, fixed_amount=1_111_111,
              percent_value=0, is_active=True)
EB = Employee(company_id=2, name="HTK B hodim", position="Ishchi", pay_type=PayType.FIXED, fixed_amount=2_222_222,
              percent_value=0, is_active=True)
EB2 = Employee(company_id=2, name="HTK B tarixsiz", position="Ishchi", pay_type=PayType.FIXED, fixed_amount=3_333_333,
               percent_value=0, is_active=True)
db.add_all([EA, EB, EB2])
db.flush()
db.add_all([
    EmployeeCompensationHistory(employee_id=EA.id, effective_year=2026, effective_month=8, pay_type=PayType.FIXED,
                                fixed_amount=1_500_000, percent_value=0, per_unit_rate=0, per_unit_type="metr",
                                extra_monthly=0),
    EmployeeCompensationHistory(employee_id=EB.id, effective_year=2026, effective_month=8, pay_type=PayType.FIXED,
                                fixed_amount=2_500_000, percent_value=0, per_unit_rate=0, per_unit_type="metr",
                                extra_monthly=0),
])
db.commit()
ID = {"EA": EA.id, "EB": EB.id, "EB2": EB2.id}
db.close()


def chaqir(*a, **k):
    s = SessionLocal()
    try:
        return crud.get_employee_compensation_for_month(s, *a, **k)
    except Exception as e:                 # noqa: BLE001
        return ("XATO", type(e).__name__, str(e)[:160])
    finally:
        s.close()


def summa(r):
    try:
        return float(r["fixed_amount"])
    except Exception:                      # noqa: BLE001
        return r


section("1. E-2 — to'lov tarixi faqat o'z korxonasidan")
check("1.1 A hodimi, korxona 1 — tarixdagi 1 500 000", summa(chaqir(ID["EA"], YIL, OY, company_id=1)) == 1_500_000,
      chaqir(ID["EA"], YIL, OY, company_id=1))
check("1.2 B hodimi, korxona 2 — tarixdagi 2 500 000", summa(chaqir(ID["EB"], YIL, OY, company_id=2)) == 2_500_000,
      chaqir(ID["EB"], YIL, OY, company_id=2))
check("1.3 B hodimi, BEGONA korxona 1 — None (asl: parametr yo'q — B ning 2 500 000 qaytardi)",
      chaqir(ID["EB"], YIL, OY, company_id=1) is None, chaqir(ID["EB"], YIL, OY, company_id=1))
check("1.4 tarixsiz B hodimi, korxona 2 — zaxira: joriy 3 333 333", summa(chaqir(ID["EB2"], YIL, OY, company_id=2))
      == 3_333_333, chaqir(ID["EB2"], YIL, OY, company_id=2))
check("1.5 tarixsiz B hodimi, BEGONA korxona 1 — None (zaxira ham korxona bo'yicha)",
      chaqir(ID["EB2"], YIL, OY, company_id=1) is None, chaqir(ID["EB2"], YIL, OY, company_id=1))
_x = chaqir(ID["EB"], YIL, OY)
check("1.6 korxonasiz chaqiruv — TypeError (asl: B ning summasi jimgina qaytardi)",
      isinstance(_x, tuple) and _x[1] == "TypeError", _x)
_x = chaqir(ID["EB"], YIL, OY, company_id=None)
check("1.7 company_id=None — ValueError (begona / hamma korxona taxmin qilinmaydi)",
      isinstance(_x, tuple) and _x[1] == "ValueError", _x)

section("2. E-3 — o'lik funksiya")
check("2.1 `crud.get_return_item` yo'q", not hasattr(crud, "get_return_item"))
_hav = []
for _dir, _dirs, _files in os.walk(ROOT):
    if "/." in _dir or "__pycache__" in _dir or os.sep + "tools" in _dir[len(ROOT):]:
        continue
    for _f in _files:
        if _f.endswith(".py"):
            _t = open(os.path.join(_dir, _f), encoding="utf-8", errors="replace").read()
            if re.search(r"\bget_return_item\(", _t):
                _hav.append(os.path.join(_dir, _f)[len(ROOT) + 1:])
check("2.2 dastur kodida `get_return_item(` chaqiruvi / ta'rifi yo'q", not _hav, _hav)

section("3. Statik")
_src = inspect.getsource(crud.get_employee_compensation_for_month)
_sig = inspect.signature(crud.get_employee_compensation_for_month)
_p = _sig.parameters.get("company_id")
check("3.1 `company_id` — majburiy kalit so'zli parametr (standart qiymatsiz)",
      _p is not None and _p.kind == inspect.Parameter.KEYWORD_ONLY and _p.default is inspect.Parameter.empty, str(_sig))
check("3.2 tarix so'rovi va zaxira — `Employee.company_id == company_id`",
      _src.count("Employee.company_id == company_id") == 2, _src[-600:])
check("3.3 yagona tanlov qoidasi saqlangan (`_kompensatsiya_tanla(rows, year, month)`)",
      "_kompensatsiya_tanla(rows, year, month)" in _src)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
