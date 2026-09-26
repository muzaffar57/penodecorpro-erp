#!/usr/bin/env python3
"""
test_tm_sotuv_narx.py — kech91 darvozasi (2026-09-26, 7-band): tayyor mahsulot sotuvida (bitta —
`POST /api/finished/sell`, savatcha — `POST /api/finished/sell-batch`) bazaga yoziladigan narx va jami bir-biriga
mos: narx bazadagidek 2 xonaga (PostgreSQL HALF_UP), jami SHU narxdan (`crud._xarid_narx_jami` — 17g xarid qarori
bilan bir xil); kelishilgan summa ham 2 xonaga, qatorlar yig'indisi AYNAN shu summa.

O'LCHANGAN (asl kod = zip 84, `work/probe7.py`, SQLite + HAQIQIY PG 16): narx va jami ALOHIDA yaxlitlanardi —
`333 × 10.335` → bazada narx 10.34, jami 3441.56 (333 × 10.34 = 3443.22, 1.66 so'm farq); `7 × 0.125` → PG narx
0.13, jami 0.88 (7 × 0.13 = 0.91); `3 × 1234.567` → 3703.70 (3703.71); javob `total_amount` 3441.5550000000003;
savatcha kelishilgan 800.005 → qatorlar yig'indisi 800.00. UI (formatPriceInput) butun son yuboradi — bu yo'l
o'zgarmaydi (D bo'limi — nazorat).

Bo'limlar: A — bitta sotuv (6 holat, baza / javob); B — savatcha chegirmasiz; C — savatcha chegirmali
(yig'indi = kelishilgan, asl jami = miqdor × narx); D — butun narx (UI yo'li) — natija asl kod bilan bir xil;
E — tan narxdan past tekshiruvi yoziladigan narx bilan; F — sig'im chegarasi (juda katta — 400, hech narsa
yozilmaydi); G — Moliya / ro'yxat / PDF shu qiymatlarni o'qiydi; H — statik.

Ishlatish:
    python3 tools/test_tm_sotuv_narx.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tm_sotuv_narx.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tm_sotuv_narx_test"
_T = tempfile.mkdtemp(prefix="tm_sotuv_narx_")
_DB = os.path.join(_T, "tm_sotuv_narx_test.db")

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
from datetime import datetime                      # noqa: E402
from decimal import Decimal, ROUND_HALF_UP         # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, FinishedProduct, FinishedProductSale, ProductionStatus,
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


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


def D(v):
    return Decimal(repr(float(v)))


def hu2(v):
    """HALF_UP 2 xona — PostgreSQL Numeric(12,2) qoidasi."""
    return D(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def teng(a, b):
    try:
        return abs(D(a) - D(b)) < Decimal("0.0000001")
    except Exception:                      # noqa: BLE001
        return False


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — har holatga ALOHIDA tayyor mahsulot (qoldiq katta, tan narx 0);
# E uchun tan narxi 999.9995 (cost_price 999 999.50 / 1 000).
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TS_A", "Parol123!", UserRole.ADMIN, "TS A", company_id=1)
FP = {}
for _n in ("S1", "S2", "S3", "S4", "S5", "S6", "B1a", "B1b", "C1a", "C1b", "C1c", "D1", "D2", "D3", "F1", "G1"):
    _fp = FinishedProduct(company_id=1, name=f"TS_{_n}", quantity=100000, unit="metr", cost_price=0,
                          production_status=ProductionStatus.READY, unit_price=1000)
    _db.add(_fp)
    _db.flush()
    FP[_n] = _fp.id
for _n in ("E1", "E2", "E3"):
    _fp = FinishedProduct(company_id=1, name=f"TS_{_n}", quantity=1000, unit="metr", cost_price=999999.5,
                          production_status=ProductionStatus.READY, unit_price=1000)
    _db.add(_fp)
    _db.flush()
    FP[_n] = _fp.id
_db.commit()
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "TS_A", "password": "Parol123!"}, follow_redirects=False)


def sotuv_oqi(sid=None, gid=None):
    s = SessionLocal()
    try:
        q = s.query(FinishedProductSale)
        q = q.filter(FinishedProductSale.id == sid) if sid else q.filter(FinishedProductSale.sale_group_id == gid)
        return [{"q": float(x.quantity), "narx": D(x.unit_price), "jami": D(x.total_amount),
                 "asl": (D(x.original_total) if x.original_total is not None else None),
                 "tan": D(x.cost_amount or 0), "fp": x.finished_product_id}
                for x in q.order_by(FinishedProductSale.id).all()]
    finally:
        s.close()


def qoldiq(fp_id):
    s = SessionLocal()
    try:
        return float(s.get(FinishedProduct, fp_id).quantity)
    finally:
        s.close()


def sotuvlar_soni():
    s = SessionLocal()
    try:
        return s.query(FinishedProductSale).count()
    finally:
        s.close()


def sot(kalit, q, p, **qosh):
    body = {"finished_product_id": FP[kalit], "quantity": q, "unit_price": p, "payment_method": "naqd"}
    body.update(qosh)
    r = req(C, "post", "/api/finished/sell", json=body)
    d = js(r) or {}
    rows = sotuv_oqi(sid=d.get("sale_id")) if d.get("sale_id") else []
    return r.status_code, d, (rows[0] if rows else None)


def savat(items, agreed=None, **qosh):
    body = {"items": [{"finished_product_id": FP[k], "quantity": q, "unit_price": p} for k, q, p in items],
            "payment_method": "naqd"}
    if agreed is not None:
        body["agreed_amount"] = agreed
    body.update(qosh)
    r = req(C, "post", "/api/finished/sell-batch", json=body)
    d = js(r) or {}
    rows = sotuv_oqi(gid=d.get("sale_group_id")) if d.get("sale_group_id") else []
    return r.status_code, d, rows


section("A — bitta sotuv: narx 2 xonaga, jami SHU narxdan (baza va javob)")
check("A0 login 302", _lr.status_code == 302, _lr.status_code)
HOLAT_A = (("S1", 3, 1234.567, "1234.57", "3703.71"), ("S2", 333, 10.335, "10.34", "3443.22"),
           ("S3", 7, 0.125, "0.13", "0.91"), ("S4", 2.5, 333.333, "333.33", "833.33"),
           ("S5", 0.333, 1001, "1001.00", "333.33"), ("S6", 1.005, 1000, "1000.00", "1005.00"))
_a_jami = Decimal("0")
for _k, _q, _p, _narx, _jami in HOLAT_A:
    _st, _d, _row = sot(_k, _q, _p)
    check(f"A {_k} {_q} × {_p}: 200", _st == 200, (_st, _d))
    check(f"A {_k} bazada narx {_narx}", _row is not None and _row["narx"] == Decimal(_narx), _row)
    check(f"A {_k} bazada jami {_jami} = HALF_UP(miqdor × baza narxi)",
          _row is not None and _row["jami"] == Decimal(_jami) == hu2(D(_q) * _row["narx"]), _row)
    check(f"A {_k} javob total_amount = baza jami ({_jami})", teng(_d.get("total_amount"), Decimal(_jami)), _d)
    check(f"A {_k} javob profit = jami − tan narx", _row is not None and teng(_d.get("profit"), _row["jami"] - _row["tan"]),
          (_d, _row))
    check(f"A {_k} qoldiq miqdorga kamaydi", teng(qoldiq(FP[_k]), 100000 - _q), qoldiq(FP[_k]))
    if _row is not None:
        _a_jami += _row["jami"]

section("B — savatcha chegirmasiz: har qator narx / jami mos, javob jami = qatorlar yig'indisi")
_st, _d, _rows = savat([("B1a", 3, 1234.567), ("B1b", 333, 10.335)])
check("B1 200 va 2 qator", _st == 200 and len(_rows) == 2, (_st, _d))
check("B2 1-qator: 1234.57 / 3703.71 (asl ham 3703.71)",
      len(_rows) == 2 and (_rows[0]["narx"], _rows[0]["jami"], _rows[0]["asl"]) == (Decimal("1234.57"), Decimal("3703.71"), Decimal("3703.71")),
      _rows)
check("B3 2-qator: 10.34 / 3443.22 (asl ham 3443.22)",
      len(_rows) == 2 and (_rows[1]["narx"], _rows[1]["jami"], _rows[1]["asl"]) == (Decimal("10.34"), Decimal("3443.22"), Decimal("3443.22")),
      _rows)
check("B4 javob total / original = round(7146.93) = 7147, chegirma 0",
      _d.get("total_amount") == 7147 and _d.get("original_total") == 7147 and _d.get("discount_percent") == 0, _d)
check("B5 har qatorda jami = HALF_UP(miqdor × narx)", all(r["jami"] == hu2(D(r["q"]) * r["narx"]) for r in _rows), _rows)

section("C — savatcha chegirmali: yig'indi AYNAN kelishilgan (2 xonaga), asl = miqdor × narx")
_st, _d, _rows = savat([("C1a", 7, 0.125), ("C1b", 2.5, 333.333), ("C1c", 3, 1234.567)], agreed=4000.005)
_asl = [hu2(D(q) * hu2(p)) for q, p in ((7, 0.125), (2.5, 333.333), (3, 1234.567))]
check("C1 200 va 3 qator", _st == 200 and len(_rows) == 3, (_st, _d))
check("C2 qatorlar yig'indisi = 4000.01 (kelishilgan 4000.005 HALF_UP)",
      sum((r["jami"] for r in _rows), Decimal("0")) == Decimal("4000.01"), [str(r["jami"]) for r in _rows])
check("C3 har qator asl jami = HALF_UP(miqdor × baza narxi)", [r["asl"] for r in _rows] == _asl and
      all(r["asl"] == hu2(D(r["q"]) * r["narx"]) for r in _rows), (_rows, _asl))
check("C4 narxlar 0.13 / 333.33 / 1234.57", [r["narx"] for r in _rows] == [Decimal("0.13"), Decimal("333.33"), Decimal("1234.57")],
      _rows)
_orig = sum(_asl, Decimal("0"))
check("C5 oldingi qatorlar ulushi round(asl × kelishilgan / asl jami, 2); oxirgisi qoldiq",
      len(_rows) == 3 and all(_rows[i]["jami"] == D(round(float(_asl[i]) * 4000.01 / float(_orig), 2)) for i in (0, 1))
      and _rows[2]["jami"] == hu2(Decimal("4000.01") - _rows[0]["jami"] - _rows[1]["jami"]), (_rows, _orig))
check("C6 javob: original = round(asl jami), total 4000, chegirma foizi asl jamidan",
      _d.get("original_total") == round(float(_orig)) and _d.get("total_amount") == 4000
      and teng(_d.get("discount_percent"), round((1 - 4000.01 / float(_orig)) * 100, 2)), (_d, _orig))

section("D — butun narx (UI yo'li): natija o'zgarmaydi")
_st, _d, _row = sot("D1", 3, 1500)
check("D1 3 × 1500 → 1500.00 / 4500.00, javob 4500", _st == 200 and _row is not None and (_row["narx"], _row["jami"]) ==
      (Decimal("1500.00"), Decimal("4500.00")) and teng(_d.get("total_amount"), 4500), (_st, _d, _row))
_st, _d, _row = sot("D2", 0.333, 1001)
check("D2 0.333 × 1001 → 1001.00 / 333.33", _st == 200 and _row is not None and (_row["narx"], _row["jami"]) ==
      (Decimal("1001.00"), Decimal("333.33")), (_st, _row))
_st, _d, _rows = savat([("D3", 2, 25000)], agreed=45000)
check("D3 savatcha 2 × 25 000, kelishilgan 45 000 → narx 25 000, asl 50 000, jami 45 000",
      _st == 200 and len(_rows) == 1 and (_rows[0]["narx"], _rows[0]["asl"], _rows[0]["jami"]) ==
      (Decimal("25000.00"), Decimal("50000.00"), Decimal("45000.00")) and _d.get("discount_percent") == 10.0, (_st, _d, _rows))

section("E — tan narxdan past tekshiruvi yoziladigan narx bilan (tan narx 999.9995)")
_st, _d, _row = sot("E1", 1, 999.996)
check("E1 narx 999.996 → bazada 1000.00 (tan narxdan past EMAS) — tasdiqsiz 200",
      _st == 200 and _row is not None and _row["narx"] == Decimal("1000.00"), (_st, _d))
_n1 = sotuvlar_soni()
_st, _d, _row = sot("E2", 1, 999.99)
check("E2 narx 999.99 (haqiqatan past) → 400 below_cost_warning, yozuv yo'q",
      _st == 400 and isinstance(_d.get("detail"), dict) and _d["detail"].get("type") == "below_cost_warning"
      and sotuvlar_soni() == _n1, (_st, _d))
_st, _d, _rows = savat([("E3", 1, 999.996)])
check("E3 savatcha: 999.996 → 1000.00 — tasdiqsiz 200", _st == 200 and len(_rows) == 1 and _rows[0]["narx"] == Decimal("1000.00"),
      (_st, _d))
_st, _d, _rows = savat([("E3", 1, 999.99)])
check("E4 savatcha: 999.99 → 400 below_cost_warning",
      _st == 400 and isinstance(_d.get("detail"), dict) and _d["detail"].get("type") == "below_cost_warning", (_st, _d))
_st, _d, _row = sot("E2", 1, 999.99, confirm_below_cost=True)
check("E5 tasdiq bilan 999.99 → 200, narx 999.99", _st == 200 and _row is not None and _row["narx"] == Decimal("999.99"), (_st, _d))

section("F — sig'im chegarasi")
_n0 = sotuvlar_soni()
_q0 = qoldiq(FP["F1"])
_st, _d, _row = sot("F1", 2, float(crud._ORDER_ITEM_MAX_MONEY))
check("F1 juda katta jami → 400, sotuv yozilmadi, qoldiq o'zgarmadi",
      _st == 400 and sotuvlar_soni() == _n0 and teng(qoldiq(FP["F1"]), _q0), (_st, _d))
_st, _d, _rows = savat([("F1", 2, float(crud._ORDER_ITEM_MAX_MONEY))])
check("F2 savatcha: juda katta → 400, yozuv yo'q", _st == 400 and sotuvlar_soni() == _n0, (_st, _d))

section("G — Moliya, sotuvlar ro'yxati va PDF shu qiymatlarni o'qiydi")
_st, _d, _row = sot("G1", 333, 10.335)
_gid = _d.get("sale_id")
_now = datetime.utcnow()
_rep = js(req(C, "get", "/api/finance/report", params={"year": _now.year, "month": _now.month})) or {}
_s = SessionLocal()
try:
    _baza_jami = sum((D(x.total_amount) for x in _s.query(FinishedProductSale).all()), Decimal("0"))
finally:
    _s.close()
check("G1 oylik hisobot fp_sales_daromad = round(bazadagi jami yig'indisi)",
      _rep.get("fp_sales_daromad") == round(float(_baza_jami)), (_rep.get("fp_sales_daromad"), _baza_jami))
_sl = js(req(C, "get", "/api/finished/sales")) or []
_gq = [x for x in _sl if x.get("id") == _gid]
check("G2 /api/finished/sales: 10.34 × 333 = 3443.22", len(_gq) == 1 and teng(_gq[0]["unit_price"], 10.34)
      and teng(_gq[0]["total_amount"], 3443.22), _gq)
_pdf = req(C, "get", f"/api/finished/sales/{_gid}/pdf")
check("G3 sotuv PDF 200", _pdf.status_code == 200 and _pdf.content[:4] == b"%PDF", _pdf.status_code)
_st, _d, _rows = savat([("G1", 2, 1234.567)], agreed=2000.005)
_pdfb = req(C, "get", f"/api/finished/sales/batch/{_d.get('sale_group_id')}/pdf")
check("G4 savatcha PDF 200", _st == 200 and _pdfb.status_code == 200 and _pdfb.content[:4] == b"%PDF", (_st, _pdfb.status_code))

section("H — statik")
_s1 = manba(crud, "sell_finished_product")
_sb = manba(crud, "sell_finished_products_batch")
check("H1 bitta sotuv: _xarid_narx_jami(data.quantity, data.unit_price)",
      "_sotuv_narx, total_amount = _xarid_narx_jami(data.quantity, data.unit_price)" in _s1)
check("H2 bitta sotuv: yoziladigan narx va tekshiruv shu narx bilan",
      "        unit_price=_sotuv_narx,\n" in _s1 and "float(_sotuv_narx) < unit_cost" in _s1)
check("H3 bitta sotuv: eski ifoda (miqdor × kiritilgan narx) yo'q", "total_amount = data.quantity * data.unit_price" not in _s1)
check("H4 savatcha: _xarid_narx_jami(item.quantity, item.unit_price)",
      "_narx2, orig_total = _xarid_narx_jami(item.quantity, item.unit_price)" in _sb)
check("H5 savatcha: qatorga _narx2, tekshiruv _narx2 bilan",
      '"unit_price": _narx2,' in _sb and "float(_narx2) < unit_cost" in _sb)
check("H6 savatcha: kelishilgan summa _pul2 bilan", "agreed_grand_total = _pul2(agreed)" in _sb)
check("H7 savatcha: eski ifoda yo'q", "orig_total = item.quantity * item.unit_price" not in _sb)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
