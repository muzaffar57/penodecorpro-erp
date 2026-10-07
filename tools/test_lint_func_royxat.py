#!/usr/bin/env python3
"""test_lint_func_royxat.py — kech109, K107-3: `tools/tenant_lint.py` ko'r nuqtalari.

NIMA UCHUN KERAK
----------------
O'LCHANGAN (kech107 toifalash `lint_toifalash.md`, kech109 skan — asl lint `bd0b48c`):
  (a) `db.query(func.coalesce(func.sum(FinishedProduct.reserved_quantity), 0.0))` shaklidagi so'rov lint ga UMUMAN
      ko'rinmasdi — faqat birinchi nom (`func`) model bilan solishtirilardi. 10b E-1 dagi korxonasiz band yig'indisi
      (`production_service.mrp_detal_kerak`) aynan shu ko'r nuqtada edi; ochilgach yana 3 ta chiqdi: 2 tasi korxona
      sharti RO'YXATDA (`services.get_inventory_kpi` — `.filter(*_mv_cid, …)`), 1 tasi ota tekshirilgan
      (`services.get_employee_advances_total` — marshrut `auth.employee_of_company`, baseline B).
  (b) `filters.append(X.company_id == company_id)` … `.filter(*filters)` — korxona sharti ro'yxat ichida; lint uni
      ko'rmay `crud.search_finished_products` (№14) ni baseline ga soxta yozgan edi.
YECHIM (texnik): (a) birinchi nom model bo'lmasa — argument ichidan birinchi TENANT model (nom / taxallus /
`modul.Model`); (b) `.filter(*RO'YXAT …)` — shu funksiyada ro'yxatga korxona sharti qo'shilgan bo'lsa cheklangan.

BO'LIMLAR
---------
  L sun'iy fayl (vaqtinchalik ROOT): func / case / taxallus / ko'p qatorli / filtrli / tenant emas / model yo'q;
    ro'yxat — append / literal / shartli literal / `*RO'YXAT, boshqa` / korxonasiz ro'yxat;
  M haqiqiy `production_service.py` nusxasi — `mrp_detal_kerak` band so'rovidan korxona sharti olib tashlansa lint
    uni TOPADI (asl ko'r nuqta);
  R haqiqiy repo: lint TOZA; baseline da №14 yo'q, `get_employee_advances_total` bor;
  S statik.

ISHLATISH
---------
    python3 tools/test_lint_func_royxat.py        (baza kerak emas — PG_URL e'tiborsiz)
"""
import os
import re
import sys
import io
import json
import inspect
import tempfile
import contextlib
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n── {t} " + "─" * max(0, 90 - len(t)))


def yukla():
    spec = importlib.util.spec_from_file_location("tenant_lint_sinov109", os.path.join(ROOT, "tools", "tenant_lint.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TL = yukla()

MODELS = '''
from sqlalchemy import Column, Integer

_TENANT_RULES = {
    "OrderItem": [("order_id", "Order")],
}


class Order(Base):
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, nullable=False)


class OrderItem(Base):
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer)


class InventoryMovement(Base):
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, nullable=False)


class Setting(Base):
    id = Column(Integer, primary_key=True)
'''

SINOV = '''
from sqlalchemy import func, case
from sqlalchemy import func as _fn
from models import InventoryMovement as _IMv
import models


def f_func(db):
    return db.query(func.sum(Order.id)).scalar()


def f_func_filtr(db, company_id):
    return db.query(func.coalesce(func.sum(InventoryMovement.id), 0)).filter(
        InventoryMovement.company_id == company_id).scalar()


def f_func_ichma(db, x):
    return db.query(func.coalesce(func.sum(OrderItem.id), 0.0)).filter(
        OrderItem.order_id == x
    ).scalar()


def f_func_taxallus(db):
    return db.query(_fn.count(_IMv.id)).scalar()


def f_func_modul(db):
    return db.query(func.max(models.Order.id)).scalar()


def f_case(db):
    return db.query(case((Order.id > 0, 1), else_=0)).all()


def f_func_tenant_emas(db):
    return db.query(func.count(Setting.id)).scalar()


def f_func_modelsiz(db):
    return db.query(func.count(1)).scalar()


def f_func_aralash(db):
    return db.query(func.count(Setting.id), func.sum(Order.id)).first()


def f_royxat_append(db, q, company_id=None):
    filters = [Order.id > 0]
    if company_id is not None:
        filters.append(Order.company_id == company_id)
    return db.query(Order).filter(*filters).all()


def f_royxat_literal(db, company_id):
    shart = [Order.id > 0, Order.company_id == company_id]
    return db.query(Order).filter(*shart).all()


def f_royxat_shartli(db, company_id=None):
    _mv = ([InventoryMovement.company_id == company_id] if company_id is not None else [])
    return db.query(func.count(InventoryMovement.id)).filter(
        *_mv,
        InventoryMovement.id > 0
    ).scalar()


def f_royxat_korxonasiz(db, x):
    filters = [Order.id == x]
    filters.append(Order.id > 0)
    return db.query(Order).filter(*filters).all()


def f_royxat_begona(db, company_id):
    boshqa = [Order.company_id == company_id]
    filters = [Order.id > 0]
    return db.query(Order).filter(*filters).all()
'''

section("L sun'iy fayl")
_t = tempfile.mkdtemp(prefix="lfr_")
open(os.path.join(_t, "models.py"), "w", encoding="utf-8").write(MODELS)
open(os.path.join(_t, "sinov1.py"), "w", encoding="utf-8").write(SINOV)
_asl_root, _asl_files = TL.ROOT, TL.SCAN_FILES
TL.ROOT, TL.SCAN_FILES = _t, ["sinov1.py"]
try:
    with contextlib.redirect_stdout(io.StringIO()):
        W, RD = TL.scan()
except Exception as e:                     # noqa: BLE001
    W, RD = [f"XATO {type(e).__name__}: {e}"], []
TL.ROOT, TL.SCAN_FILES = _asl_root, _asl_files


def bor(royxat, funksiya, model):
    return [x for x in royxat if f"(funksiya: {funksiya})" in x and f"db.query({model})" in x]


def funksiyada(royxat, funksiya):
    return [x for x in royxat if f"(funksiya: {funksiya})" in x]


check("L1 `db.query(func.sum(Order.id))` filtrsiz — Order deb topiladi (asl: ko'rinmasdi)",
      len(bor(RD, "f_func", "Order")) == 1, RD)
check("L2 func + korxona filtri — topilmaydi", not funksiyada(RD, "f_func_filtr"), RD)
check("L3 ichma-ich func, ko'p qatorli, ota filtri (order_id) — OrderItem deb topiladi",
      len(bor(RD, "f_func_ichma", "OrderItem")) == 1, RD)
check("L4 taxallusli func (`_fn.count(_IMv.id)`) — InventoryMovement deb topiladi",
      len(bor(RD, "f_func_taxallus", "InventoryMovement")) == 1, RD)
check("L5 `func.max(models.Order.id)` — Order deb topiladi", len(bor(RD, "f_func_modul", "Order")) == 1, RD)
check("L6 `case((Order.id > 0, 1), …)` — Order deb topiladi", len(bor(RD, "f_case", "Order")) == 1, RD)
check("L7 tenant bo'lmagan model (`Setting`) va modelsiz `func.count(1)` — topilmaydi",
      not funksiyada(RD, "f_func_tenant_emas") and not funksiyada(RD, "f_func_modelsiz"), RD)
check("L7b aralash argument (`func.count(Setting.id), func.sum(Order.id)`) — tenant bo'lmagan model o'tkazib, Order topiladi",
      len(bor(RD, "f_func_aralash", "Order")) == 1, RD)
check("L8 `filters.append(Order.company_id == …)` + `.filter(*filters)` — topilmaydi (asl: soxta signal)",
      not funksiyada(RD, "f_royxat_append"), RD)
check("L9 ro'yxat literalida korxona sharti — topilmaydi", not funksiyada(RD, "f_royxat_literal"), RD)
check("L10 shartli ro'yxat (`([X.company_id == …] if … else [])`) + `.filter(*_mv, …)` — topilmaydi",
      not funksiyada(RD, "f_royxat_shartli"), RD)
check("L11 korxona sharti YO'Q ro'yxat — topiladi (ro'yxat qoidasi ko'r-ko'rona o'tkazmaydi)",
      len(bor(RD, "f_royxat_korxonasiz", "Order")) == 1, RD)
check("L12 korxona sharti BOSHQA ro'yxatda (ishlatilmagan) — topiladi",
      len(bor(RD, "f_royxat_begona", "Order")) == 1, RD)
check("L13 jami o'qish topilmalari AYNAN 8 ta, yozish xatosi yo'q", len(RD) == 8 and not W, (len(RD), RD, W))

section("M haqiqiy production_service.py — asl ko'r nuqta")
_t2 = tempfile.mkdtemp(prefix="lfr_m_")
for _f in ("models.py", "production_models.py"):
    _p = os.path.join(ROOT, _f)
    if os.path.exists(_p):
        open(os.path.join(_t2, _f), "w", encoding="utf-8").write(open(_p, encoding="utf-8").read())
_ps = open(os.path.join(ROOT, "production_service.py"), encoding="utf-8").read()
_m = re.search(r"def mrp_detal_kerak\(.*?\n(?=def )", _ps, re.S)
_fn_src = _m.group(0) if _m else ""
_mut = re.sub(r"\n(\s*)[^\n]*\.filter\(FinishedProduct\.company_id == [^\n]*", r"\n\1pass", _fn_src)
open(os.path.join(_t2, "production_service.py"), "w", encoding="utf-8").write(_ps.replace(_fn_src, _mut) if _fn_src else _ps)
TL.ROOT, TL.SCAN_FILES = _t2, ["production_service.py"]
try:
    with contextlib.redirect_stdout(io.StringIO()):
        _w, _r = TL.scan()
except Exception as e:                     # noqa: BLE001
    _w, _r = [f"XATO {e}"], []
TL.ROOT, TL.SCAN_FILES = _asl_root, _asl_files
check("M0 mutatsiya qo'llandi (mrp_detal_kerak dan korxona sharti olib tashlandi)", bool(_fn_src) and _mut != _fn_src,
      _fn_src[-400:])
check("M1 korxonasiz band yig'indisi — lint TOPADI (db.query(FinishedProduct), mrp_detal_kerak)",
      len(bor(_r, "mrp_detal_kerak", "FinishedProduct")) == 1, _r)

section("R haqiqiy repo")
_out = io.StringIO()
try:
    with contextlib.redirect_stdout(_out):
        _rc = TL.main()
except SystemExit as e:                    # noqa: BLE001
    _rc = e.code
except Exception as e:                     # noqa: BLE001
    _rc = f"XATO {type(e).__name__}: {e}"
check("R1 `tenant_lint.py` haqiqiy repo — TOZA (rc 0)", _rc == 0, _out.getvalue()[-600:])
_bl = json.load(open(os.path.join(ROOT, "tools", "tenant_lint_baseline.json"), encoding="utf-8")).get("read", [])
check("R2 baseline da `search_finished_products` (№14 — soxta signal) YO'Q",
      not [x for x in _bl if "(funksiya: search_finished_products)" in x], [x for x in _bl if "search_finished" in x])
check("R3 baseline da `get_employee_advances_total` (func — ota tekshirilgan, B) BOR",
      len([x for x in _bl if "(funksiya: get_employee_advances_total)" in x]) == 1)
check("R4 baseline da `get_inventory_kpi` (korxona sharti ro'yxatda) YO'Q",
      not [x for x in _bl if "(funksiya: get_inventory_kpi)" in x])

section("S statik")
_src = inspect.getsource(TL)
check("S1 `_argument_modeli` — func / case argumentidan tenant model", "def _argument_modeli(" in _src
      and "_argument_modeli(kod_lines, i, m.start()" in _src)
check("S2 ro'yxat filtri qoidasi (`.filter(*RO'YXAT`, append / literal)",
      "append|extend" in _src and "(?:append|extend)" in _src)

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
sys.exit(1 if FAIL else 0)
