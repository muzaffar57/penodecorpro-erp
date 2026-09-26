#!/usr/bin/env python3
"""
test_qarz_tiyin.py — kech92 darvozasi (2026-09-26, 119-band / K91-1): mijoz buyurtmasining qarzi va to'lov
holati tiyin aniqligida, 0.5 so'mdan oshmaydigan qoldiq — qarz YO'Q (`models.QARZ_BARDOSH`).

O'LCHANGAN (asl kod = zip 85, `work/probe119.py`, SQLite va HAQIQIY PostgreSQL 16 — AYNAN bir xil):
  * to'langan summa `float` lar yig'indisi edi, kelishilgan summa bilan QAT'IY (`paid < agreed`) solishtirilardi:
    3 × −166 517.15 qaytarishdan keyin to'langan 448.54999999998836 (kelishilgan 448.55) — qarz 1.2e-11, holat
    "qisman"; tiyinli to'lovlar 2 674.60 + 1 236.47 (kelishilgan 3 911.07) — qarz 4.5e-13, "qisman";
  * UI yo'li (qarz butun so'mda ko'rinadi, to'lov butun so'mda kiritiladi): kelishilgan 461 538.40, ko'rinib turgan
    qarz 461 538 to'landi — qarz 0.40000000002, "qisman", arxivga O'TMAYDI, dashboard qarzdorlar ro'yxatida, 30
    kundan keyin "qarzdor" ogohlantirishi; "chegirmaga yozish" 0.5 dan kichik qoldiqni yozmaydi (BERK KO'CHA);
    kelishilgan 461 538.75 da ko'rinib turgan qarz 461 539 to'lansa — "qarzdan (461,539 so'm) 0 so'mga ko'p" (409);
    yetkazish bilan to'lov — xuddi shunday; dashboard jami qarz 461539.95000000007.

Bo'limlar: A — model (`paid_amount`, `debt_amount`, yordamchilar); B — `_update_order_payment_status` jadvali
(chegara 0.5 ikki tomoni); C — HTTP (UI yo'llari, ortiqcha to'lov tasdig'i chegarasi, chegirmaga yozish,
yetkazish to'lovi, tiyinli qaytarish / to'lov); D — dashboard / ogohlantirish / bugungi to'lovlar / sahifalar;
E — nazorat (haqiqiy qarz, haqiqiy ortiqcha to'lov, 3 baravar qoidasi o'zgarmadi); H — statik.

Ishlatish:
    python3 tools/test_qarz_tiyin.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_qarz_tiyin.py
"""
import os
import re
import sys
import math
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qarz_tiyin_test"
_T = tempfile.mkdtemp(prefix="qarz_tiyin_")
_DB = os.path.join(_T, "qarz_tiyin_test.db")

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
from datetime import datetime, timedelta           # noqa: E402
from decimal import Decimal                        # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Inventory, Payment, PaymentStatus, OrderType,
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
        self.content = b""

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


def xavfsiz(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return f"ISTISNO {type(e).__name__}: {e}"


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


def xususiyat_manbasi(cls, nom):
    p = getattr(cls, nom, None)
    f = getattr(p, "fget", None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


def js_round(x):
    """JS `Math.round` (musbat) — UI `formatNum` ko'rsatgan qarz."""
    return float(math.floor(float(x) + 0.5))


def tiyin_aniq(v):
    """Qiymat tiyin aniqligidami: repr da 2 tadan ko'p kasr xonasi yo'q."""
    try:
        s = repr(float(v))
    except Exception:                      # noqa: BLE001
        return False
    if "e" in s or "E" in s:
        return float(v) == 0.0
    kasr = s.split(".")[1] if "." in s else ""
    return len(kasr) <= 2


# ══════════════════════════════════════════════════════════════
# A — model
# ══════════════════════════════════════════════════════════════
section("A — model: paid_amount / debt_amount / yordamchilar")


def tr_order(agreed, summalar, total=500_000):
    o = Order(company_id=1, project_id=None, order_type=OrderType.PRODUCT,
              total_amount=Decimal(str(total)),
              agreed_amount=(Decimal(str(agreed)) if agreed is not None else None))
    o.payments = [Payment(amount=Decimal(str(s))) for s in summalar]
    return o


_o = tr_order(448.55, ["500000", "-166517.15", "-166517.15", "-166517.15"])
_p, _q = xavfsiz(lambda: _o.paid_amount), xavfsiz(lambda: _o.debt_amount)
check("A1 3 × −166 517.15 qaytarish: paid_amount = 448.55 (tiyin aniq, float shovqinisiz)",
      repr(_p) == "448.55", repr(_p))
check("A2 ... debt_amount = 0.0 (float, avvalgi 'to'liq to'langan' shakli)", repr(_q) == "0.0", repr(_q))
_o = tr_order(3911.07, ["2674.60", "1236.47"], total=4000)
check("A3 tiyinli to'lovlar 2674.60 + 1236.47: paid 3911.07, qarz 0.0",
      repr(xavfsiz(lambda: _o.paid_amount)) == "3911.07" and repr(xavfsiz(lambda: _o.debt_amount)) == "0.0",
      (repr(xavfsiz(lambda: _o.paid_amount)), repr(xavfsiz(lambda: _o.debt_amount))))
for _nom, _ag, _kut in (("A4 qoldiq 0.40 → qarz 0.0", "461538.40", "0.0"),
                        ("A5 qoldiq 0.50 (chegara) → qarz 0.0", "461538.50", "0.0"),
                        ("A6 qoldiq 0.51 → qarz 0.51", "461538.51", "0.51"),
                        ("A7 qoldiq 0.75 → qarz 0.75", "461538.75", "0.75"),
                        ("A8 qoldiq 1.00 → qarz 1.0", "461539", "1.0")):
    _o = tr_order(_ag, ["461538"])
    _d = xavfsiz(lambda: _o.debt_amount)
    check(_nom, repr(_d) == _kut, repr(_d))
_o = tr_order(1000, ["1100"])
_d = xavfsiz(lambda: _o.debt_amount)
check("A9 ortiqcha to'langan (1000 / 1100) → qarz 0 (int, avvalgi shakl)", repr(_d) == "0", repr(_d))
_o = tr_order(1000, [])
check("A10 to'lovsiz: paid_amount 0 (int, avvalgi shakl), qarz 1000.0",
      repr(xavfsiz(lambda: _o.paid_amount)) == "0" and repr(xavfsiz(lambda: _o.debt_amount)) == "1000.0",
      (repr(xavfsiz(lambda: _o.paid_amount)), repr(xavfsiz(lambda: _o.debt_amount))))
_o = tr_order(1000, ["400"])
check("A11 haqiqiy qisman qarz 600.0 o'zgarmadi", repr(xavfsiz(lambda: _o.debt_amount)) == "600.0",
      repr(xavfsiz(lambda: _o.debt_amount)))
_pt = getattr(models, "pul_tiyin", None)
_py = getattr(models, "pul_tiyin_yigindi", None)
check("A12 models.QARZ_BARDOSH = 0.5", getattr(models, "QARZ_BARDOSH", None) == 0.5, getattr(models, "QARZ_BARDOSH", None))
check("A13 pul_tiyin: 10.335 → 10.34 (HALF_UP), 0.125 → 0.13, −1e-11 → 0.0 (manfiy nol EMAS)",
      _pt is not None and _pt(10.335) == 10.34 and _pt(0.125) == 0.13 and repr(_pt(-1e-11)) == "0.0",
      (_pt and (_pt(10.335), _pt(0.125), repr(_pt(-1e-11)))))
check("A14 pul_tiyin_yigindi: [0.1, 0.2] → 0.3; [] → 0.0; Decimal va None qabul qiladi",
      _py is not None and repr(_py([0.1, 0.2])) == "0.3" and repr(_py([])) == "0.0"
      and _py([Decimal("2674.60"), None, 1236.47]) == 3911.07,
      (_py and (repr(_py([0.1, 0.2])), repr(_py([])))))

# ══════════════════════════════════════════════════════════════
# B — _update_order_payment_status
# ══════════════════════════════════════════════════════════════
section("B — _update_order_payment_status (chegara 0.5 ikki tomoni)")
_JAD = [
    ("B1 448.55 / 3 tiyinli qaytarish → paid, arxiv", 448.55, ["500000", "-166517.15", "-166517.15", "-166517.15"], 500_000, PaymentStatus.PAID, True),
    ("B2 461 538.40 / 461 538 → paid, arxiv", "461538.40", ["461538"], 500_000, PaymentStatus.PAID, True),
    ("B3 461 538.50 / 461 538 (chegara) → paid", "461538.50", ["461538"], 500_000, PaymentStatus.PAID, True),
    ("B4 461 538.51 / 461 538 → partial, arxivda EMAS", "461538.51", ["461538"], 500_000, PaymentStatus.PARTIAL, False),
    ("B5 1000 / to'lovsiz → unpaid", 1000, [], 500_000, PaymentStatus.UNPAID, False),
    ("B6 kelishilgan 0.40 (jami > 0) / to'lovsiz → paid, arxiv (K42-1 — qarz yo'q)", "0.40", [], 500_000, PaymentStatus.PAID, True),
    ("B7 kelishilgan 0.51 / to'lovsiz → unpaid", "0.51", [], 500_000, PaymentStatus.UNPAID, False),
    ("B8 0 so'mlik bo'sh buyurtma → unpaid, arxivda EMAS", 0, [], 0, PaymentStatus.UNPAID, False),
    ("B9 1000 / 1100 → paid", 1000, ["1100"], 500_000, PaymentStatus.PAID, True),
    ("B10 1000 / 999.49 → partial (0.51)", 1000, ["999.49"], 500_000, PaymentStatus.PARTIAL, False),
    ("B11 3911.07 / 2674.60 + 1236.47 → paid", "3911.07", ["2674.60", "1236.47"], 4000, PaymentStatus.PAID, True),
    ("B12 kelishilgan 0 / −100 (manfiy to'lov) → unpaid (avvalgidek)", 0, ["-100"], 500_000, PaymentStatus.UNPAID, False),
]
for _nom, _ag, _ps, _tot, _st, _ar in _JAD:
    _o = tr_order(_ag, _ps, total=_tot)
    _r = xavfsiz(crud._update_order_payment_status, None, _o)
    check(_nom, _o.payment_status == _st and bool(_o.is_archived) is _ar
          and ((_o.closed_at is not None) is _ar),
          (_r, _o.payment_status, _o.is_archived, _o.closed_at))

# ══════════════════════════════════════════════════════════════
# Tayyorgarlik (HTTP)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "QT_admin", "Parol123!", UserRole.ADMIN, "QT Admin", company_id=1)
PRJ = [Project(company_id=1, client_name=f"QT Mijoz {i}", project_name=f"QT loyiha {i}",
               total_budget=0, total_paid=0) for i in range(60)]
PENO = Inventory(company_id=1, item_name="QT Penoplast", unit="blok", stock_quantity=1000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_db.add_all(PRJ + [PENO])
_db.commit()
PRJ_ID = [p.id for p in PRJ]
PENO_ID = PENO.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "QT_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print(f"LOGIN BO'LMADI: {_lr.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def buyurtma(narx=50_000, dona=10, uzunlik=100):
    """10 dona × 100 sm profil, 50 000 → jami 500 000. Har biri o'z loyihasida."""
    _n[0] += 1
    nom = f"QT_D{_n[0]}"
    r = req(C, "post", "/api/orders", json={
        "project_id": PRJ_ID[_n[0] % len(PRJ_ID)], "order_type": "product", "items": [
            {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": uzunlik,
             "quantity": dona, "unit_price": narx, "is_coated": False, "penoplast_id": PENO_ID}]})
    d = SessionLocal()
    try:
        oi = d.query(OrderItem).filter(OrderItem.name == nom).order_by(OrderItem.id.desc()).first()
        if oi is None:
            return None, None, nom, r.status_code
        return oi.order_id, oi.id, nom, r.status_code
    finally:
        d.close()


def kelishilgan(oid, summa):
    return req(C, "put", f"/api/orders/{oid}/agreed-amount", json={"agreed_amount": summa})


def tolov(oid, summa, write_off=False, tasdiq=False):
    url = "/api/payments" + ("?write_off_remainder=true" if write_off else "")
    tana = {"order_id": oid, "amount": summa, "payment_method": "naqd"}
    if tasdiq:
        tana["confirm_overpay"] = True
    return req(C, "post", url, json=tana)


def holat(oid):
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        if o is None:
            return {}
        ps = [float(x.amount) for x in d.query(Payment).filter(Payment.order_id == oid).order_by(Payment.id).all()]
        return {"agreed": float(o.agreed_amount) if o.agreed_amount is not None else None,
                "status": o.payment_status, "archived": bool(o.is_archived), "tolovlar": ps,
                "debt": o.debt_amount, "notes": o.notes or ""}
    finally:
        d.close()


def api_o(oid):
    return js(req(C, "get", f"/api/orders/{oid}")) or {}


# ══════════════════════════════════════════════════════════════
# C — HTTP (UI yo'llari)
# ══════════════════════════════════════════════════════════════
section("C — HTTP: UI yo'llari")
# C1 — kelishilgan .40, ko'rinib turgan qarz to'lanadi
O_C1, _i, _nm, _s = buyurtma()
kelishilgan(O_C1, 461_538.40)
_q = holat(O_C1).get("debt", 0)
_r = tolov(O_C1, js_round(_q))
_h = holat(O_C1)
_d = js(_r) or {}
check("C1 kelishilgan 461 538.40 + to'lov 461 538 (UI): 200, paid, arxiv, qarz 0",
      _r.status_code == 200 and _h.get("status") == PaymentStatus.PAID and _h.get("archived") is True
      and _h.get("debt") == 0, (_r.status_code, _h))
check("C2 ... javob: debt_amount 0, is_archived true (UI 'arxivga o'tdi' xabari)",
      _d.get("debt_amount") == 0 and _d.get("is_archived") is True and _d.get("payment_status") == "paid", _d)
_ao = api_o(O_C1)
check("C3 ... GET /api/orders/{id}: debt_amount 0, paid_amount 461538.0",
      _ao.get("debt_amount") == 0 and _ao.get("paid_amount") == 461538.0, (_ao.get("debt_amount"), _ao.get("paid_amount")))

# C4 — .75: ko'rinib turgan qarz (461 539) — tasdiqsiz o'tadi
O_C4, _i, _nm, _s = buyurtma()
kelishilgan(O_C4, 461_538.75)
_q = holat(O_C4).get("debt", 0)
_r = tolov(O_C4, js_round(_q))
_h = holat(O_C4)
check("C4 kelishilgan 461 538.75 + to'lov 461 539 (UI): 409 YO'Q — 200, paid, arxiv",
      _r.status_code == 200 and _h.get("status") == PaymentStatus.PAID and _h.get("archived") is True,
      (_r.status_code, (js(_r) or {}).get("detail"), _h))

# C5 — ortiqcha 0.60 (> 0.5) — tasdiq SO'RALADI, hech narsa yozilmaydi
O_C5, _i, _nm, _s = buyurtma()
kelishilgan(O_C5, 461_538.40)
_r = tolov(O_C5, 461_539)
_det = (js(_r) or {}).get("detail") or {}
_h = holat(O_C5)
check("C5 qarz 461 538.40, to'lov 461 539 (0.60 ortiqcha) → 409 overpayment_warning, yozuv yo'q",
      _r.status_code == 409 and isinstance(_det, dict) and _det.get("type") == "overpayment_warning"
      and _h.get("tolovlar") == [], (_r.status_code, _det, _h.get("tolovlar")))
check("C6 ... 409 excess tiyin aniq: 0.6", isinstance(_det, dict) and repr(_det.get("excess")) == "0.6",
      repr(_det.get("excess")) if isinstance(_det, dict) else _det)
_r = tolov(O_C5, 461_539, tasdiq=True)
_h = holat(O_C5)
check("C7 ... tasdiq bilan 200, paid", _r.status_code == 200 and _h.get("status") == PaymentStatus.PAID,
      (_r.status_code, _h))

# C8 — .75 qarzga 461 540 (1.25 ortiqcha) → 409, excess 1.25
O_C8, _i, _nm, _s = buyurtma()
kelishilgan(O_C8, 461_538.75)
_r = tolov(O_C8, 461_540)
_det = (js(_r) or {}).get("detail") or {}
check("C8 qarz 461 538.75, to'lov 461 540 → 409, excess 1.25, xabarda '1 so'mga ko'p'",
      _r.status_code == 409 and isinstance(_det, dict) and repr(_det.get("excess")) == "1.25"
      and "1 so'mga ko'p" in str(_det.get("message")), (_r.status_code, _det))

# C9 — "chegirmaga yozish": qoldiq 0.40 — to'lov o'zi yopadi
O_C9, _i, _nm, _s = buyurtma()
kelishilgan(O_C9, 461_538.40)
tolov(O_C9, 400_000)
_r = tolov(O_C9, 61_538, write_off=True)
_h = holat(O_C9)
_d = js(_r) or {}
check("C9 qoldiq 0.40 + 'chegirmaga yozish': 200, paid, arxiv (berk ko'cha yo'q)",
      _r.status_code == 200 and _h.get("status") == PaymentStatus.PAID and _h.get("archived") is True
      and _d.get("is_archived") is True, (_r.status_code, _d, _h))
check("C10 ... kelishilgan o'zgarmadi (461 538.40), WRITEOFF belgisi yo'q (yozadigan qoldiq yo'q)",
      _h.get("agreed") == 461538.4 and "WRITEOFF" not in _h.get("notes", ""), _h)

# C11 — "chegirmaga yozish": qoldiq 538.40 — avvalgidek yoziladi
O_C11, _i, _nm, _s = buyurtma()
kelishilgan(O_C11, 461_538.40)
_r = tolov(O_C11, 461_000, write_off=True)
_h = holat(O_C11)
_wo = (js(_r) or {}).get("write_off") or {}
check("C11 qoldiq 538.40 + 'chegirmaga yozish': kelishilgan 461 000.0, paid, arxiv, [WRITEOFF:538]",
      _r.status_code == 200 and _h.get("agreed") == 461000.0 and _h.get("status") == PaymentStatus.PAID
      and _h.get("archived") is True and "[WRITEOFF:538]" in _h.get("notes", "") and _wo.get("amount") == 538,
      (_r.status_code, _wo, _h))

# C12 / C13 — yetkazish bilan to'lov (UI "Bir yo'la to'liq topshirish")
O_C12, I_C12, _nm, _s = buyurtma()
kelishilgan(O_C12, 461_538.40)
_q = holat(O_C12).get("debt", 0)
_r = req(C, "post", "/api/deliveries", json={"order_id": O_C12, "items": [{"order_item_id": I_C12, "quantity": 100}],
                                               "payment_amount": js_round(_q)})
_h = holat(O_C12)
check("C12 yetkazish + to'lov 461 538 (kelishilgan .40): 200, paid, arxiv",
      _r.status_code == 200 and _h.get("status") == PaymentStatus.PAID and _h.get("archived") is True,
      (_r.status_code, (js(_r) or {}).get("detail"), _h))
O_C13, I_C13, _nm, _s = buyurtma()
kelishilgan(O_C13, 461_538.75)
_q = holat(O_C13).get("debt", 0)
_r = req(C, "post", "/api/deliveries", json={"order_id": O_C13, "items": [{"order_item_id": I_C13, "quantity": 100}],
                                               "payment_amount": js_round(_q)})
_h = holat(O_C13)
check("C13 yetkazish + to'lov 461 539 (kelishilgan .75): 409 YO'Q — 200, paid",
      _r.status_code == 200 and _h.get("status") == PaymentStatus.PAID, (_r.status_code, (js(_r) or {}).get("detail"), _h))

# C14 — tiyinli qaytarish (P3): 3 × 166 517.15 + "Pul qaytdi"
O_C14, I_C14, N_C14, _s = buyurtma()
tolov(O_C14, 500_000)
_rs = []
for _k in range(3):
    _rr = req(C, "post", "/api/returns", json={
        "order_id": O_C14, "order_item_id": I_C14, "item_name": N_C14, "quantity": 33.3, "unit": "metr",
        "reason": "Ortiqcha", "refund_amount": 166_517.15, "to_stock": False, "notes": None, "coating_applied": False})
    _rid = (js(_rr) or {}).get("id") if _rr.status_code == 200 else None
    _rs.append((_rr.status_code, req(C, "post", f"/api/returns/{_rid}/refund").status_code if _rid else None))
_h = holat(O_C14)
check("C14 3 × 166 517.15 qaytarish + pul qaytdi: kelishilgan 448.55, paid, arxiv, qarz 0.0",
      _h.get("agreed") == 448.55 and _h.get("status") == PaymentStatus.PAID and _h.get("archived") is True
      and repr(_h.get("debt")) == "0.0", (_rs, _h))
_ao = api_o(O_C14)
check("C15 ... API paid_amount 448.55 (float shovqinisiz), debt_amount 0",
      repr(_ao.get("paid_amount")) == "448.55" and _ao.get("debt_amount") == 0,
      (repr(_ao.get("paid_amount")), _ao.get("debt_amount")))

# C16 — tiyinli to'lovlar (API)
O_C16, _i, _nm, _s = buyurtma(narx=4_000, dona=1, uzunlik=100)
kelishilgan(O_C16, 3911.07)
tolov(O_C16, 2674.60)
_r = tolov(O_C16, 1236.47)
_h = holat(O_C16)
_d = js(_r) or {}
check("C16 tiyinli to'lovlar 2674.60 + 1236.47 = 3911.07: paid, arxiv; javob paid_amount 3911.07, debt 0",
      _h.get("status") == PaymentStatus.PAID and _h.get("archived") is True
      and repr(_d.get("paid_amount")) == "3911.07" and _d.get("debt_amount") == 0, (_h, _d))

# C17 — javoblarda manfiy nol / shovqin yo'q
_matnlar = [req(C, "get", f"/api/orders/{x}").text for x in (O_C1, O_C4, O_C9, O_C14, O_C16)]
check("C17 GET /api/orders/{id} javoblarida '-0.0' va 'e-1' (shovqin) yo'q",
      all("-0.0" not in t and "e-1" not in t for t in _matnlar),
      [t[:0] for t in _matnlar])

# ══════════════════════════════════════════════════════════════
# E — nazorat (o'zgarmasligi kerak)
# ══════════════════════════════════════════════════════════════
section("E — nazorat: haqiqiy qarz / ortiqcha to'lov / 3 baravar")
O_E1, _i, _nm, _s = buyurtma()
kelishilgan(O_E1, 461_538.40)
_r = tolov(O_E1, 400_000)
_h = holat(O_E1)
check("E1 haqiqiy qisman: 400 000 / 461 538.40 → partial, qarz 61538.4",
      _r.status_code == 200 and _h.get("status") == PaymentStatus.PARTIAL and repr(_h.get("debt")) == "61538.4"
      and _h.get("archived") is False, (_r.status_code, _h))
O_E2, _i, _nm, _s = buyurtma()
_r = tolov(O_E2, 500_001)
check("E2 500 000 qarzga 500 001 → 409 (1 so'm ortiqcha — tasdiq so'raladi)", _r.status_code == 409, _r.status_code)
_r = tolov(O_E2, 1_600_000)
check("E3 3 baravar qoidasi (1 600 000 > 3 × 500 000) → 400", _r.status_code == 400, (_r.status_code, _r.text[:120]))
O_E4, _i, _nm, _s = buyurtma()
_r = tolov(O_E4, 500_000)
_h = holat(O_E4)
check("E4 butun summa AYNAN to'landi → paid, arxiv, qarz 0.0", _r.status_code == 200 and _h.get("status") == PaymentStatus.PAID
      and _h.get("archived") is True and repr(_h.get("debt")) == "0.0", (_r.status_code, _h))
# E5 — kichik haqiqiy qarz 10.42 (D3 da oddiy float yig'indisi 1023087.5700000001 berardi — jami qarz tiyin aniq bo'lishi SHART)
O_E5, _i, _nm, _s = buyurtma()
kelishilgan(O_E5, 1000.42)
_r = tolov(O_E5, 990)
_h = holat(O_E5)
check("E5 kichik haqiqiy qarz: 990 / 1000.42 → partial, qarz 10.42", _r.status_code == 200
      and _h.get("status") == PaymentStatus.PARTIAL and repr(_h.get("debt")) == "10.42", (_r.status_code, _h))

# ══════════════════════════════════════════════════════════════
# D — dashboard / ogohlantirish / bugungi to'lovlar / sahifalar
# ══════════════════════════════════════════════════════════════
section("D — dashboard, ogohlantirish, sahifalar")
_s = SessionLocal()
try:
    for _x in (O_C1, O_C9, O_C14, O_C16, O_E1):
        _o = _s.get(Order, _x)
        if _o is not None:
            _o.created_at = datetime.utcnow() - timedelta(days=45)
    _s.commit()
finally:
    _s.close()
_ds = js(req(C, "get", "/api/dashboard/debts")) or {}
_ids = [x.get("order_id") for x in (_ds.get("debt_orders") or [])]
check("D1 /api/dashboard/debts: to'liq to'langan (C1, C9, C14, C16, C12) ro'yxatda YO'Q",
      not any(x in _ids for x in (O_C1, O_C9, O_C14, O_C16, O_C12)), _ids)
check("D2 ... haqiqiy qarz (E1) ro'yxatda, qarz 61538.4",
      any(x.get("order_id") == O_E1 and repr(x.get("debt_amount")) == "61538.4" for x in (_ds.get("debt_orders") or [])),
      [(x.get("order_id"), x.get("debt_amount")) for x in (_ds.get("debt_orders") or [])])
_s = SessionLocal()
try:
    _faol = [o for o in _s.query(Order).filter(Order.is_archived == False, Order.is_deleted.isnot(True)).all()]  # noqa: E712
    _kut_qarz = sum((Decimal(repr(float(o.kelishilgan_summa))) - sum((Decimal(repr(float(p.amount))) for p in o.payments), Decimal("0"))
                     for o in _faol
                     if Decimal(repr(float(o.kelishilgan_summa))) - sum((Decimal(repr(float(p.amount))) for p in o.payments), Decimal("0")) > Decimal("0.5")),
                    Decimal("0"))
    _bugun = [p for p in _s.query(Payment).all()]
finally:
    _s.close()
check("D3 total_debt = haqiqiy qarzlar yig'indisi (Decimal), tiyin aniq",
      Decimal(repr(float(_ds.get("total_debt", -1)))) == _kut_qarz and tiyin_aniq(_ds.get("total_debt")),
      (repr(_ds.get("total_debt")), _kut_qarz))
check("D4 total_agreed / total_paid / today_payments — tiyin aniq (shovqinsiz)",
      tiyin_aniq(_ds.get("total_agreed")) and tiyin_aniq(_ds.get("total_paid")) and tiyin_aniq(_ds.get("today_payments")),
      (repr(_ds.get("total_agreed")), repr(_ds.get("total_paid")), repr(_ds.get("today_payments"))))
_kut_bugun = sum((Decimal(repr(float(p.amount))) for p in _bugun), Decimal("0"))
check("D5 today_payments = bugungi to'lovlar yig'indisi (Decimal) AYNAN",
      Decimal(repr(float(_ds.get("today_payments", -1)))) == _kut_bugun, (repr(_ds.get("today_payments")), _kut_bugun))
_al = js(req(C, "get", "/api/reports/alerts")) or []
_qal = [a.get("text") for a in _al if "qarzdor" in str(a.get("text"))]
check("D6 /api/reports/alerts: muddati o'tgan qarzdor FAQAT haqiqiy (E1) — '1 ta'",
      _qal == ["1 ta qarzdorning muddati 30 kundan oshgan"], _qal)
_pg = req(C, "get", "/orders")
_m = re.search(r'<div class="ord-item" style="([^"]*)"\s+id="oi-' + str(O_C12) + r'"', _pg.text or "")
check("D7 /orders: to'liq topshirilgan + to'langan (C12, qoldiq 0.40) qatori YASHIL, qizil EMAS",
      _pg.status_code == 200 and _m is not None and "#F0FDF4" in _m.group(1) and "#FEF2F2" not in _m.group(1),
      (_pg.status_code, _m.group(1) if _m else None))
_dp = req(C, "get", "/debts")
check("D8 /debts sahifasi 200 (qarzdorlar)", _dp.status_code == 200, _dp.status_code)

# ══════════════════════════════════════════════════════════════
# H — statik
# ══════════════════════════════════════════════════════════════
section("H — statik")
_hs = manba(crud, "_update_order_payment_status")
check("H1 holat: tiyin + QARZ_BARDOSH bilan, eski QAT'IY solishtiruv yo'q",
      "elif pul_tiyin(agreed - paid) > QARZ_BARDOSH:" in _hs and "elif paid < agreed:" not in _hs
      and "paid = order.paid_amount" in _hs, _hs[:0])
check("H2 holat: K42-1 chegarasi QARZ_BARDOSH", "if agreed <= QARZ_BARDOSH and total > 0 and paid >= -0.005:" in _hs)
_tc = manba(crud, "_tolov_chegarasi")
check("H3 ortiqcha to'lov: tiyin + QARZ_BARDOSH, eski `float(summa) > current_debt` yo'q",
      "_ortiqcha = pul_tiyin(float(summa) - current_debt)" in _tc and "if _ortiqcha > QARZ_BARDOSH and not confirm_overpay:" in _tc
      and "if float(summa) > current_debt" not in _tc)
_gd = manba(crud, "get_debt_stats")
check("H4 get_debt_stats: Order.debt_amount / paid_amount, o'z float hisobi yo'q",
      "debt = o.debt_amount" in _gd and "paid = o.paid_amount" in _gd
      and "sum(float(p.amount or 0) for p in (o.payments" not in _gd and "debt = max(agreed - paid, 0)" not in _gd)
check("H5 Order.paid_amount — pul_tiyin_yigindi; debt_amount — pul_tiyin + QARZ_BARDOSH",
      "pul_tiyin_yigindi(p.amount for p in tolovlar)" in xususiyat_manbasi(Order, "paid_amount")
      and "if qoldiq > QARZ_BARDOSH:" in xususiyat_manbasi(Order, "debt_amount"))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
