#!/usr/bin/env python3
"""test_kirim_tolov_chegara.py — kech96 (2026-09-27), 125-band (server + brauzer↔server paritet qismi).

NIMA UCHUN KERAK
----------------
Kirim hujjati (`POST /api/inventory/receipt`) ta'minotchiga "hozir to'langan" summani hujjat summasi bilan
cheklardi: `min(paid_now, round(xom mahsulotlar + qo'shimcha xarajatlar))`. HAQIQIY brauzerda O'LCHANGAN
(kech96 `work/probe125.py`, asl = zip 89, SQLite = PG):
  • qo'shimcha xarajatlar (transport, tushirish, yuklash, boshqa) ta'minotchi qarziga KIRMAYDI — ular korxona
    xarajati sifatida Moliyaga yoziladi va kassadan chiqadi. Sahifadagi "To'liq to'lash" ularni ham qo'shgani
    uchun 100 000 + transport 20 000 → ta'minotchiga 120 000 to'lov: qarz "0" ko'rinardi (20 000 yashirin
    ortiqcha to'lov — keyingi 50 000 lik nasiya 30 000 bo'lib ko'rindi), kassa −140 000 (transport IKKI marta);
  • chegara xom ko'paytmadan BUTUN so'mga yaxlitlanardi — bazadagi jami esa `_xarid_narx_jami` (narx 2 xona,
    jami shu narxdan): 7 × 1 000.07 = 7 000.49 → chegara 7 000 (0.49 yashirin qarz), 333 × 10.335 → bazada
    3 443.22, chegara 3 442 (1.22 qarz).
Endi chegara — ta'minotchi qarziga yoziladigan AYNAN summa: nasiya bo'ladigan qatorlar (ta'minotchi bor,
boshlang'ich ombor emas) jamisi, har biri `crud._xarid_narx_jami` bilan.
Brauzer tomoni (`tiyinga`, `pulYigindi` — 4 sahifada) Python o'nlik qoidasi bilan AYNAN (P bo'limi, node).

BO'LIMLAR
---------
  A qo'shimcha xarajat ta'minotchiga to'lanmaydi (chegara = mahsulotlar); keyingi nasiya to'liq ko'rinadi;
  B tiyinli jami (7 × 1 000.07) — to'liq to'lov qarzsiz, katta summa jamigacha qirqiladi;
  C 3 xonali narx (API) — chegara bazadagi jami (3 443.22);
  D boshlang'ich ombor — to'lov yozilmaydi; aralash hujjat — faqat nasiya qatorlari;
  E ta'minotchisiz hujjat — to'lov yo'q (o'zgarmagan), xarajatlar yoziladi;
  F bitta xarid marshruti (o'zgarmagan) — tiyinli to'liq to'lov nasiya emas;
  K kassa: qo'shimcha xarajat BIR marta; P brauzer ↔ server paritet (node); X 5xx yo'q; S statik.

ISHLATISH
---------
    python3 tools/test_kirim_tolov_chegara.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_kirim_tolov_chegara.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import json
import random
import tempfile
import subprocess
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "kirim_tolov_chegara_test"
_T = tempfile.mkdtemp(prefix="ktc_")
_DB = os.path.join(_T, "kirim_tolov_chegara_test.db")

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

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
import services                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, Supplier, InventoryPurchase, SupplierPayment,   # noqa: E402
                    ExpenseTransaction)
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
        return {}


def teng(a, b, tol=0.001):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:                      # noqa: BLE001
        return False


# ── MUSTAQIL etalon (kod emas — qoida): narx 2 xonaga HALF_UP, jami SHU narxdan ──
def d2(x):
    return Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def jami(miqdor, narx):
    return float((Decimal(repr(float(miqdor))) * d2(narx)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "ktc_admin", "Parol123!", UserRole.ADMIN, "KTC Admin", company_id=1)
MAT = [Inventory(company_id=1, item_name=f"KTC Material {i}", unit="kg", stock_quantity=0, price_per_unit=0,
                 is_penoplast=False, category="Kimyoviy qo'shimchalar") for i in range(10)]
SUP = [Supplier(company_id=1, name=f"KTC Taminotchi {i}") for i in range(10)]
s.add_all(MAT + SUP)
s.commit()
M = [m.id for m in MAT]
SID = [x.id for x in SUP]
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = C.post("/login", data={"username": "ktc_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _lr.status_code in (200, 302, 303), _lr.status_code)


def taminotchi(sid):
    """Bazadagi xom holat: nasiya xaridlar jami, to'lovlar, xom qarz (manfiy — yashirin ortiqcha to'lov)."""
    s = SessionLocal()
    try:
        pur = s.query(InventoryPurchase).filter(InventoryPurchase.supplier_id == sid).order_by(InventoryPurchase.id).all()
        pay = s.query(SupplierPayment).filter(SupplierPayment.supplier_id == sid).order_by(SupplierPayment.id).all()
        kredit = sum((Decimal(str(p.total_amount)) for p in pur if p.is_credit), Decimal("0"))
        tolov = sum((Decimal(str(p.amount)) for p in pay), Decimal("0"))
        return {"kredit": float(kredit), "tolovlar": [float(p.amount) for p in pay], "tolov": float(tolov),
                "qarz": float(kredit - tolov), "xaridlar": [(float(p.total_amount), bool(p.is_credit)) for p in pur]}
    finally:
        s.close()


def kassa():
    s = SessionLocal()
    try:
        return services.get_cash_balance(s, company_id=1)
    finally:
        s.close()


def xarajat_soni():
    s = SessionLocal()
    try:
        return s.query(ExpenseTransaction).count()
    finally:
        s.close()


def kirim(qatorlar, **kw):
    tana = {"items": [{"inventory_id": m, "quantity": q, "price_per_unit": n, "volume_per_unit": None,
                       "is_opening_stock": bool(o)} for m, q, n, o in qatorlar],
            "notes": "KTC", "production_type": None}
    tana.update(kw)
    return req(C, "post", "/api/inventory/receipt", json=tana)


# ══════════════════════════════════════════════════════════════
section("A. Qo'shimcha xarajat ta'minotchiga to'lanmaydi — chegara = mahsulotlar jami")
# ══════════════════════════════════════════════════════════════
k0 = kassa()
x0 = xarajat_soni()
r = kirim([(M[0], 100, 1000, False)], supplier_id=SID[0], paid_now=125000, transport_cost=20000,
          tushirish_cost=5000)
h = taminotchi(SID[0])
check("A1 hujjat (100 × 1 000 + transport 20 000 + tushirish 5 000, to'lov 125 000) → 200", r.status_code == 200,
      f"{r.status_code} {r.text[:200]}")
check("A2 ta'minotchiga to'lov 100 000 (mahsulotlar) — 125 000 EMAS", h["tolovlar"] == [100000.0], h)
check("A3 xom qarz 0 (yashirin ortiqcha to'lov yo'q)", teng(h["qarz"], 0), h)
check("A4 qo'shimcha xarajatlar Moliyaga yozildi (2 ta)", xarajat_soni() == x0 + 2, xarajat_soni() - x0)
k1 = kassa()
check("A5 kassa −125 000 (mahsulot 100 000 + xarajatlar 25 000 — BIR marta)", k1["balance"] - k0["balance"] == -125000,
      k1["balance"] - k0["balance"])
r = req(C, "post", f"/api/inventory/{M[1]}/purchase", json={"quantity": 50, "price_per_unit": 1000, "paid_now": 0,
                                                            "supplier_id": SID[0]})
h = taminotchi(SID[0])
check("A6 keyingi nasiya 50 000 → qarz AYNAN 50 000 (asl: 25 000 — ortiqcha to'lovdan jim ayirilardi)",
      r.status_code == 200 and teng(h["qarz"], 50000), (r.status_code, h))
s = SessionLocal()
_kor = crud.get_supplier_debt(s, SID[0], company_id=1)
s.close()
check("A7 ta'minotchi qarzi ko'rinishi 50 000", _kor.get("debt") == 50000, _kor)
r = kirim([(M[2], 10, 500, False)], supplier_id=SID[1], paid_now=5000 + 3000, transport_cost=3000)
h = taminotchi(SID[1])
check("A8 to'lov = mahsulotlar + transport (API) → mahsulotlargacha qirqildi (5 000)",
      r.status_code == 200 and h["tolovlar"] == [5000.0] and teng(h["qarz"], 0), (r.status_code, h))
r = kirim([(M[2], 10, 500, False)], supplier_id=SID[2], paid_now=2000, transport_cost=3000)
h = taminotchi(SID[2])
check("A9 qisman to'lov 2 000 → AYNAN 2 000, qarz 3 000 (transport qarzga qo'shilmaydi)",
      r.status_code == 200 and h["tolovlar"] == [2000.0] and teng(h["qarz"], 3000), (r.status_code, h))

# ══════════════════════════════════════════════════════════════
section("B. Tiyinli jami — to'liq to'lov qarzsiz")
# ══════════════════════════════════════════════════════════════
r = kirim([(M[3], 7, 1000.07, False)], supplier_id=SID[3], paid_now=7000.49)
h = taminotchi(SID[3])
check("B1 7 × 1 000.07 (bazada 7 000.49), to'lov 7 000.49 → to'lov AYNAN 7 000.49, qarz 0",
      r.status_code == 200 and h["tolovlar"] == [7000.49] and teng(h["qarz"], 0) and h["kredit"] == 7000.49,
      (r.status_code, h))
r = kirim([(M[3], 7, 1000.07, False)], supplier_id=SID[4], paid_now=1e9)
h = taminotchi(SID[4])
check("B2 to'lov 1 000 000 000 → jamigacha (7 000.49) qirqildi (asl: 7 000 — 0.49 yashirin qarz)",
      r.status_code == 200 and h["tolovlar"] == [7000.49] and teng(h["qarz"], 0), (r.status_code, h))
r = kirim([(M[3], 3, 1234.56, False), (M[4], 7, 0.13, False), (M[5], 1, 99.99, False)], supplier_id=SID[5],
          paid_now=10 ** 7)
h = taminotchi(SID[5])
_kut = float(sum((Decimal(repr(jami(q, n))) for q, n in ((3, 1234.56), (7, 0.13), (1, 99.99))), Decimal("0")))
check(f"B3 3 qatorli hujjat: chegara qatorlar jamisi yig'indisi ({_kut}) — o'nlik arifmetikada",
      r.status_code == 200 and h["tolovlar"] == [_kut] and teng(h["qarz"], 0), (r.status_code, h, _kut))

# ══════════════════════════════════════════════════════════════
section("C. 3 xonali narx (API) — chegara bazadagi jami")
# ══════════════════════════════════════════════════════════════
r = kirim([(M[6], 333, 10.335, False)], supplier_id=SID[6], paid_now=5000)
h = taminotchi(SID[6])
check("C1 333 × 10.335 → bazada 3 443.22, to'lov 3 443.22 (asl: 3 442 — 1.22 qarz)",
      r.status_code == 200 and h["kredit"] == 3443.22 and h["tolovlar"] == [3443.22] and teng(h["qarz"], 0),
      (r.status_code, h))

# ══════════════════════════════════════════════════════════════
section("D. Boshlang'ich ombor — to'lov yozilmaydi; aralash — faqat nasiya qatorlari")
# ══════════════════════════════════════════════════════════════
r = kirim([(M[7], 5, 1000, True)], supplier_id=SID[7], paid_now=5000)
h = taminotchi(SID[7])
check("D1 faqat boshlang'ich ombor, to'lov 5 000 → to'lov YOZILMADI (qarz ham yo'q)",
      r.status_code == 200 and h["tolovlar"] == [] and h["kredit"] == 0, (r.status_code, h))
r = kirim([(M[7], 1, 1000, False), (M[8], 5, 1000, True)], supplier_id=SID[8], paid_now=6000)
h = taminotchi(SID[8])
check("D2 aralash (nasiya 1 000 + boshlang'ich 5 000), to'lov 6 000 → 1 000 (nasiya qismigacha)",
      r.status_code == 200 and h["tolovlar"] == [1000.0] and teng(h["qarz"], 0), (r.status_code, h))

# ══════════════════════════════════════════════════════════════
section("E. Ta'minotchisiz hujjat — to'lov yo'q (o'zgarmagan)")
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
_tol0 = s.query(SupplierPayment).count()
s.close()
x0 = xarajat_soni()
r = kirim([(M[9], 2, 1500, False)], paid_now=3000, transport_cost=700)
s = SessionLocal()
_tol1 = s.query(SupplierPayment).count()
s.close()
check("E1 ta'minotchisiz → 200, to'lov yozilmadi, transport Moliyada",
      r.status_code == 200 and _tol1 == _tol0 and xarajat_soni() == x0 + 1, (r.status_code, _tol1 - _tol0))

# ══════════════════════════════════════════════════════════════
section("F. Bitta xarid marshruti (o'zgarmagan) — tiyinli to'liq to'lov nasiya emas")
# ══════════════════════════════════════════════════════════════
r = req(C, "post", f"/api/inventory/{M[0]}/purchase", json={"quantity": 7, "price_per_unit": 1000.07,
                                                            "paid_now": 7000.49, "supplier_id": SID[9]})
h = taminotchi(SID[9])
check("F1 7 × 1 000.07, to'lov 7 000.49 → nasiya EMAS, qarz 0",
      r.status_code == 200 and h["xaridlar"] == [(7000.49, False)] and teng(h["qarz"], 0), (r.status_code, h))
r = req(C, "post", f"/api/inventory/{M[0]}/purchase", json={"quantity": 7, "price_per_unit": 1000.07,
                                                            "paid_now": 7000, "supplier_id": SID[9]})
h = taminotchi(SID[9])
check("F2 to'lov 7 000 (butun so'm) → nasiya, qarz 0.49 (marshrut qoidasi — UI endi AYNAN jamini yuboradi)",
      r.status_code == 200 and teng(h["qarz"], 0.49), (r.status_code, h))

# ══════════════════════════════════════════════════════════════
section("P. Brauzer (tiyinga / pulYigindi — 4 sahifa) ↔ Python o'nlik qoidasi — node")
# ══════════════════════════════════════════════════════════════


def js_funksiya(src, nom):
    i = src.find("function " + nom + "(")
    if i < 0:
        return None
    j = src.find("{", i)
    d = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            d += 1
        elif src[k] == "}":
            d -= 1
            if d == 0:
                return src[i:k + 1]
    return None


_rnd = random.Random(96125)
HOLAT_T = [0, 0.005, 0.015, 0.125, 0.335, 750000.375, 1516.6666666666667, 499999.995, 2500000.625, 1000000.5000000001,
           333.3366666666667, 1e-7, 9999999999.99, 0.1 + 0.2, 1234.565, 10.335, 1.005, 2.675]
for _ in range(3000):
    tur = _rnd.random()
    if tur < 0.4:
        HOLAT_T.append(round(_rnd.uniform(0, 5_000_000), _rnd.choice([0, 1, 2, 3, 4])))
    elif tur < 0.7:
        HOLAT_T.append(int(_rnd.uniform(0, 1_000_000)) + _rnd.choice([0.005, 0.015, 0.125, 0.335, 0.565, 0.995, 0.4999]))
    else:
        HOLAT_T.append(_rnd.uniform(0, 2_000_000) / _rnd.choice([1, 1.75, 3, 7, 13]) * _rnd.choice([1, 2, 2.5, 1.5]))
HOLAT_Y = []
for _ in range(500):
    n = _rnd.randint(1, 8)
    HOLAT_Y.append([round(_rnd.uniform(-1000, 5_000_000), 2) if _rnd.random() < 0.2 else round(_rnd.uniform(0, 5_000_000), 2)
                    for _ in range(n)])
_py_t = [float(d2(x)) for x in HOLAT_T]
_py_y = [float(sum((Decimal(repr(float(v))) for v in qs), Decimal("0"))) for qs in HOLAT_Y]
for _sahifa in ("orders", "finished", "suppliers", "supplier_receive"):
    _src = open(os.path.join(ROOT, "templates", _sahifa + ".html"), encoding="utf-8").read()
    _fn = [js_funksiya(_src, n) for n in ("_onlikQism", "_tiyinHalfUp", "buyurtmaJami", "tiyinga", "pulYigindi")]
    check(f"P {_sahifa}.html da 5 yordamchi bor", all(_fn), [bool(x) for x in _fn])
    if not all(_fn):
        continue
    _kod = "\n".join(_fn) + """
const kirish = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify({t: kirish.t.map(tiyinga), y: kirish.y.map(pulYigindi)}));
"""
    _jf = os.path.join(_T, f"paritet_{_sahifa}.js")
    open(_jf, "w", encoding="utf-8").write(_kod)
    _nat = None
    try:
        _p = subprocess.run(["node", _jf], input=json.dumps({"t": HOLAT_T, "y": HOLAT_Y}), capture_output=True,
                            text=True, timeout=120)
        _nat = json.loads(_p.stdout) if _p.returncode == 0 else None
        if _nat is None:
            print("   node:", _p.stderr[:400])
    except Exception as e:                 # noqa: BLE001
        print("   node ishlamadi:", e)
    check(f"P {_sahifa}: node ishladi", _nat is not None)
    if _nat is not None:
        _ft = [(HOLAT_T[i], _py_t[i], _nat["t"][i]) for i in range(len(HOLAT_T)) if _py_t[i] != _nat["t"][i]]
        _fy = [(HOLAT_Y[i], _py_y[i], _nat["y"][i]) for i in range(len(HOLAT_Y)) if abs(_py_y[i] - _nat["y"][i]) > 1e-9]
        check(f"P {_sahifa}: tiyinga ↔ Decimal HALF_UP AYNAN ({len(HOLAT_T)} holat)", not _ft, _ft[:3])
        check(f"P {_sahifa}: pulYigindi ↔ o'nlik yig'indi AYNAN ({len(HOLAT_Y)} holat)", not _fy, _fy[:3])

# ══════════════════════════════════════════════════════════════
section("X. 5xx yo'q")
# ══════════════════════════════════════════════════════════════
_5xx = [h for h in HOLATLAR if h[1] >= 500]
check("X hech bir so'rov 5xx qaytarmadi", not _5xx, _5xx[:5])

# ══════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════
with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
    MAIN = f.read()
_i = MAIN.find("def api_create_inventory_receipt(")
_marshrut = MAIN[_i:MAIN.find("\n@app.", _i)] if _i >= 0 else ""
check("S1 kirim chegarasi `_xarid_narx_jami` bilan (bazadagi jami)",
      "crud._xarid_narx_jami(it.quantity, it.price_per_unit)[1] for it in data.items" in _marshrut)
check("S2 faqat nasiya qatorlari (ta'minotchi bor, boshlang'ich ombor emas)",
      "if data.supplier_id and not it.is_opening_stock" in _marshrut)
# (izohda eski kod tilga olinadi — tekshiruv aniq KOD qatorlariga qaratilgan)
check("S3 eski chegara kodi (`min(..., round(_jami))`, xarajatlarni qo'shish) yo'q",
      "min(float(data.paid_now), round(_jami))" not in _marshrut
      and "_jami += (float(data.transport_cost)" not in _marshrut
      and "_paid_now = min(float(data.paid_now), float(_jami))" in _marshrut)

print()
print("=" * 60)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
