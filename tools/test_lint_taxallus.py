#!/usr/bin/env python3
"""test_lint_taxallus.py — kech99 (2026-09-27), 113-band.

NIMA UCHUN KERAK
----------------
O'LCHANGAN (kech99, `ast` bilan): `tools/tenant_lint.py` `db.query(<Nom>` dagi nomni faqat HAQIQIY model nomlari bilan
solishtirardi — taxallus bilan yozilgan so'rov (`from models import InventoryMovement as _IMv` → `db.query(_IMv)`;
`_X = Model`; `db.query(crud.Inventory)`) lint ga UMUMAN ko'rinmasdi: na xato, na baseline yozuvi. Loyihada crud 22,
main 21, services 24 ta tenant model taxallusi bor edi; ochilgach 20 ta filtrsiz so'rov ko'rindi (hammasi tahlil
qilindi — FK uzish / havola tekshiruvi, ota tekshirilgan, tizim — baseline ga yozildi).
YECHIM (texnik): lint fayldagi taxalluslarni `ast` bilan yig'adi (`import … as X`, `X = Model`), `modul.Model`
shaklini taniydi; konstruktor tekshiruvi ham taxallusni ko'radi; noaniq taxallus (bir nom — ikki model) — xato.

BO'LIMLAR
---------
  L sun'iy fayl ustida (vaqtinchalik ROOT): taxallus / `X = Model` / `modul.Model` / haqiqiy nom / ustun so'rovi /
    korxona filtri bor-yo'q / model bo'lmagan taxallus / tenant bo'lmagan model / noaniq taxallus / konstruktor;
  R haqiqiy repo: lint TOZA, baseline da taxallusli 20 yozuv, eskirgan yozuv yo'q;
  S statik.

ISHLATISH
---------
    python3 tools/test_lint_taxallus.py        (baza kerak emas — PG_URL e'tiborsiz)

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
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
    spec = importlib.util.spec_from_file_location("tenant_lint_sinov", os.path.join(ROOT, "tools", "tenant_lint.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TL = yukla()

MODELS = '''
from sqlalchemy import Column, Integer

_TENANT_RULES = {
    "OrderItem": [("order_id", "Order")],
}


class Company(Base):
    id = Column(Integer, primary_key=True)


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
import crud
from models import InventoryMovement as _IMv, Order as _Ord, Setting as _St
from models import (OrderItem as _OIt,
                    Order as _Ord2)
from sqlalchemy import func as _fn


def f_taxallus(db, x):
    return db.query(_IMv).filter(_IMv.id == x).first()


def f_taxallus_filtr(db, x, company_id):
    return db.query(_IMv).filter(_IMv.id == x, _IMv.company_id == company_id).first()


def f_kop_qator(db, x):
    return db.query(_OIt).filter(_OIt.id == x).first()


def f_modul(db, x):
    return db.query(crud.Order).filter(crud.Order.id == x).first()


def f_tayinlash(db, x):
    _Q = Order
    return db.query(_Q).filter(_Q.id == x).first()


def f_haqiqiy(db, x):
    return db.query(Order).filter(Order.id == x).first()


def f_ustun(db, x):
    return db.query(Order.id).filter(Order.id == x).first()


def f_model_emas(db, x):
    return db.query(_fn.count(1)).first()


def f_tenant_emas(db, x):
    return db.query(_St).filter(_St.id == x).first()


def f_konstruktor(db):
    db.add(_Ord(id=5))


def f_konstruktor_ok(db, company_id):
    db.add(_Ord2(id=6, company_id=company_id))
'''

NOANIQ = '''
from models import Order as _X


def a(db):
    return db.query(_X).first()


def b(db):
    from models import InventoryMovement as _X
    return db.query(_X).first()
'''

section("L sun'iy fayl")
_t = tempfile.mkdtemp(prefix="ltx_")
open(os.path.join(_t, "models.py"), "w", encoding="utf-8").write(MODELS)
open(os.path.join(_t, "sinov1.py"), "w", encoding="utf-8").write(SINOV)
open(os.path.join(_t, "sinov2.py"), "w", encoding="utf-8").write(NOANIQ)
_asl_root, _asl_files = TL.ROOT, TL.SCAN_FILES
TL.ROOT, TL.SCAN_FILES = _t, ["sinov1.py"]
try:
    with contextlib.redirect_stdout(io.StringIO()):
        W, RD = TL.scan()
except Exception as e:                     # noqa: BLE001
    W, RD = [f"XATO {type(e).__name__}: {e}"], []
TL.SCAN_FILES = ["sinov2.py"]
try:
    with contextlib.redirect_stdout(io.StringIO()):
        W2, RD2 = TL.scan()
except Exception as e:                     # noqa: BLE001
    W2, RD2 = [f"XATO {type(e).__name__}: {e}"], []
TL.ROOT, TL.SCAN_FILES = _asl_root, _asl_files


def bor(royxat, funksiya, model):
    return [x for x in royxat if f"(funksiya: {funksiya})" in x and f"db.query({model})" in x]


check("L1 taxallus (`_IMv`) filtrsiz — InventoryMovement deb topiladi", len(bor(RD, "f_taxallus", "InventoryMovement")) == 1,
      RD)
check("L2 taxallus korxona filtri bilan — topilmaydi", not bor(RD, "f_taxallus_filtr", "InventoryMovement"), RD)
check("L3 ko'p qatorli import taxallusi (`_OIt`) — OrderItem deb topiladi", len(bor(RD, "f_kop_qator", "OrderItem")) == 1, RD)
check("L4 `modul.Model` (`crud.Order`) — Order deb topiladi", len(bor(RD, "f_modul", "Order")) == 1, RD)
check("L5 `_Q = Order` tayinlash taxallusi — Order deb topiladi", len(bor(RD, "f_tayinlash", "Order")) == 1, RD)
check("L6 haqiqiy nom va ustun so'rovi (`Order.id`) — avvalgidek topiladi (xabar shakli o'zgarmagan)",
      len(bor(RD, "f_haqiqiy", "Order")) == 1 and len(bor(RD, "f_ustun", "Order")) == 1
      and all("taxallus" not in x for x in bor(RD, "f_haqiqiy", "Order")), RD)
check("L7 model bo'lmagan taxallus (`_fn`) va tenant bo'lmagan model (`_St`) — topilmaydi",
      not [x for x in RD if "f_model_emas" in x or "f_tenant_emas" in x], RD)
check("L8 jami o'qish topilmalari AYNAN 6 ta", len(RD) == 6, RD)
check("L9 konstruktor taxallus bilan (`_Ord(...)` company_id siz) — YOZISH xatosi, taxallus nomi bilan",
      [x for x in W if "Order() (taxallus _Ord)" in x and "f_konstruktor)" in x], W)
check("L10 konstruktor taxallus bilan company_id berilgan — xato yo'q", not [x for x in W if "f_konstruktor_ok" in x], W)
check("L11 noaniq taxallus (bir nom — ikki model) — xato sifatida ko'rsatiladi",
      [x for x in W2 if "taxallus '_X'" in x], W2)
check("L12 noaniq taxallus hech qaysi modelga bog'lanmaydi (taxmin qilinmaydi)", not RD2, RD2)

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
_tax_yoz = [x for x in _bl if (any(t in x for t in ("db.query(_", "db.query(crud.")) or "log_db.query(_U_err" in x)
            and "db.query(_func." not in x]
# kech130 (zip 154, MOSLANDI): `main._master_by_chat_id` (`_Mst`) endi korxona to'plami bilan filtrlaydi (`korxonalar` — umumiy bot:
# platforma korxonalari, korxona boti: o'sha korxona) — lint uni filtrlangan deb ko'radi, baseline yozuvi olib tashlandi: 21 → 20.
check("R2 baseline da taxallusli so'rovlar yozilgan (20 ta — hammasi tahlil qilingan; kech109: +1 K109-2 FK uzish; kech130: −1 "
      "`_master_by_chat_id`)",
      len(_tax_yoz) == 20, (len(_tax_yoz), _tax_yoz[:3]))
try:
    with contextlib.redirect_stdout(io.StringIO()):
        _w, _r = TL.scan()
except Exception as e:                     # noqa: BLE001
    _w, _r = [f"XATO {e}"], []
check("R3 haqiqiy repo: YOZISH xatosi yo'q (taxallusli konstruktor ham)", not _w, _w[:3])

section("S statik")
_src = inspect.getsource(TL)
check("S1 `_taxalluslar` — ast bilan (ImportFrom + Assign), noaniq ajratiladi",
      "def _taxalluslar(" in _src and "ast.ImportFrom" in _src and "ast.Assign" in _src and "noaniq" in _src)
check("S2 o'qish: haqiqiy nom → taxallus → modul orqali", "elif _n1 in tax:" in _src and "elif _n2 and _n2 in all_models:" in _src)

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
sys.exit(1 if FAIL else 0)
