#!/usr/bin/env python3
"""test_atomik_tolov.py — kech99 (2026-09-27), probe103 QOLDIG'I (G, H, I).

NIMA UCHUN KERAK
----------------
O'LCHANGAN (kech99 `work/probeGHI.py`, asl = zip 92, SQLite = PG) — nosozlik in'ektsiyasi + qayta urinish:
  G1 `POST /api/payments?write_off_remainder=true` — to'lov saqlangach qoldiqni chegirmaga yozishda xato → 500, to'lov
     QOLARDI (chegirmasiz); 8 s dan keyin qayta → 409 "qarzdan ko'p" (tasdiqlansa — ikkinchi to'lov);
  G2 `POST /api/payments` — to'lov saqlangach javob uchun buyurtmani o'qishda xato → 500, to'lov QOLARDI; 8 s dan keyin
     qayta → 200 — IKKI to'lov (30 000 × 2);
  H1 `DELETE /api/payments/{id}` — audit "deleted" saqlangach xato → 500: to'lov QOLARDI, audit "o'chirildi" derdi;
     qayta urinish — ikkinchi audit;
  I1 `DELETE /api/orders/{id}/permanent` — o'chirish saqlangach audit yozuvida xato → 500, buyurtma IZSIZ o'chardi;
  I3 `DELETE /api/projects/{id}/permanent` — AYNAN I1 naqshi.
YECHIM (texnik — 103-band naqshi): endpoint ning yozadigan qismi `crud.bitta_tranzaksiya` ichida — xato bo'lsa hech narsa
saqlanmaydi, qayta urinish — bir marta. Oddiy oqim (to'lov, chegirma, 8 s takror himoyasi, "qarzdan ko'p" 409,
o'chirish) AYNAN.

"8 s dan keyin" — `crud.PUL_TAKROR_SONIYA = 0` bilan (kutmasdan; himoya qoidasi o'zi B bo'limida sinaladi).

BO'LIMLAR
---------
  A oddiy oqim (asl xulq AYNAN); G / H / I nosozlik + qayta urinish; X 5xx faqat sun'iy xatoda; S statik.

ISHLATISH
---------
    python3 tools/test_atomik_tolov.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_atomik_tolov.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import inspect
import tempfile
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "atomik_tolov_test"
_T = tempfile.mkdtemp(prefix="ato_")
_DB = os.path.join(_T, "atomik_tolov_test.db")

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
    import crud                                    # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import UserRole, Inventory, Project, Order, Payment, ActivityLog   # noqa: E402
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
    print(f"\n── {t} " + "─" * max(0, 90 - len(t)))


s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "ato_a", "Parol123!", UserRole.ADMIN, "ATO A", company_id=1)
_pa = Inventory(company_id=1, item_name="ATO Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500_000,
                volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
s.add(_pa)
_prj = Project(company_id=1, client_name="ATO", project_name="ATO", total_budget=0, total_paid=0)
s.add(_prj)
s.commit()
PID, PA = _prj.id, _pa.id
s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
C.post("/login", data={"username": "ato_a", "password": "Parol123!"}, follow_redirects=False)


def so(usul, url, sun_iy=False, **k):
    try:
        r = getattr(C, usul)(url, **k)
    except Exception as e:                 # noqa: BLE001
        HOLATLAR.append((url, 599, sun_iy))
        return 599, f"{type(e).__name__}: {e}"
    HOLATLAR.append((url, r.status_code, sun_iy))
    try:
        return r.status_code, r.json()
    except Exception:                      # noqa: BLE001
        return r.status_code, r.text


_BN = [0]


def buyurtma(narx, prj=None):
    # har buyurtma NOMI boshqa — bir xil tarkibli buyurtma 8 s ichida takror deb qaytariladi (K84-1 himoyasi)
    _BN[0] += 1
    kod, d = so("post", "/api/orders", json={"project_id": prj or PID, "order_type": "product", "loy_kg": 0, "items": [
        {"name": f"ATO {narx} #{_BN[0]}", "category": "panel", "width": 30, "thickness": 5, "quantity": 1, "unit_price": narx,
         "is_coated": False, "penoplast_id": PA}]}, params={"confirm_shortage": "true"})
    return d.get("id") if (kod == 200 and isinstance(d, dict)) else None


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        p = s.query(Payment).filter(Payment.order_id == oid).order_by(Payment.id).all()
        return {"bor": o is not None, "tolovlar": [float(x.amount) for x in p],
                "kelishilgan": float(o.agreed_amount) if o is not None and o.agreed_amount is not None else None,
                "qarz": round(float(o.debt_amount), 2) if o is not None else None,
                "izoh": (o.notes or "") if o is not None else None}
    finally:
        s.close()


def audit(turi, amal, eid=None):
    s = SessionLocal()
    try:
        q = s.query(ActivityLog).filter(ActivityLog.entity_type == turi, ActivityLog.action == amal)
        if eid is not None:
            q = q.filter(ActivityLog.entity_id == eid)
        return q.count()
    finally:
        s.close()


def loyiha_bor(pid):
    s = SessionLocal()
    try:
        return s.get(Project, pid) is not None
    finally:
        s.close()


class SunIyXato(Exception):
    pass


@contextlib.contextmanager
def buz(obj, nom, shart=lambda *a, **k: True):
    asl = getattr(obj, nom)
    qoldi = [1]

    def _o(*a, **k):
        if qoldi[0] > 0 and shart(*a, **k):
            qoldi[0] -= 1
            raise SunIyXato(f"sun'iy xato: {nom}")
        return asl(*a, **k)
    setattr(obj, nom, _o)
    try:
        yield
    finally:
        setattr(obj, nom, asl)


@contextlib.contextmanager
def himoyasiz():
    """"8 s dan keyin" — takror-imzo oynasi 0 (kutmasdan)."""
    asl = crud.PUL_TAKROR_SONIYA
    crud.PUL_TAKROR_SONIYA = 0
    try:
        yield
    finally:
        crud.PUL_TAKROR_SONIYA = asl


def tolov(oid, summa, **p):
    return so("post", "/api/payments", params=p or None,
              json={"order_id": oid, "amount": summa, "payment_type": "partial", "payment_method": "naqd"})


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A oddiy oqim")
o = buyurtma(100_000)
kod, d = tolov(o, 30_000)
check("A1 to'lov 200, javob maydonlari (to'langan / qarz / holat)", kod == 200 and isinstance(d, dict)
      and abs(d.get("paid_amount", 0) - 30_000) < 0.01 and abs(d.get("debt_amount", 0) - 70_000) < 0.01
      and d.get("duplicate") is False and d.get("write_off") is None, (kod, d))
kod, d = tolov(o, 30_000)
check("A2 8 s ichida AYNAN o'sha to'lov — takror (yangi yozuv yo'q)", kod == 200 and isinstance(d, dict)
      and d.get("duplicate") is True and holat(o)["tolovlar"] == [30_000.0], (kod, d, holat(o)))
kod, d = tolov(o, 69_900, write_off_remainder="true")
_h = holat(o)
check("A3 qoldiqni chegirmaga (100 so'm) — kelishilgan 99 900, qarz 0, izohda [WRITEOFF:100]",
      kod == 200 and isinstance(d, dict) and (d.get("write_off") or {}).get("amount") == 100
      and abs(_h["kelishilgan"] - 99_900) < 0.01 and _h["qarz"] == 0 and "[WRITEOFF:100]" in _h["izoh"], (kod, d, _h))
kod, d = tolov(o, 5_000)
check("A4 qarzsiz buyurtmaga to'lov — 409 'qarzdan ko'p' (yozuv yo'q)", kod == 409 and len(holat(o)["tolovlar"]) == 2,
      (kod, d))
s = SessionLocal()
_pid = s.query(Payment.id).filter(Payment.order_id == o).order_by(Payment.id).first()[0]
s.close()
_a0 = audit("payment", "deleted", _pid)
kod, d = so("delete", f"/api/payments/{_pid}")
check("A5 to'lovni o'chirish 200 — to'lov yo'q, audit 1", kod == 200 and len(holat(o)["tolovlar"]) == 1
      and audit("payment", "deleted", _pid) == _a0 + 1, (kod, holat(o)))
kod, d = so("delete", f"/api/payments/{_pid}")
check("A6 yo'q to'lovni o'chirish — 404, audit o'zgarmaydi", kod == 404 and audit("payment", "deleted", _pid) == _a0 + 1,
      kod)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G to'lov — nosozlik va qayta urinish")
o1 = buyurtma(100_000)
check("G0 fikstura: har buyurtma alohida (takror himoyasi yutmagan)", o1 and o1 != o, (o, o1))
with buz(crud, "_update_order_payment_status", shart=lambda db, order, *a, **k: "[WRITEOFF:" in (order.notes or "")):
    kod, _ = so("post", "/api/payments", sun_iy=True, params={"write_off_remainder": "true"},
                json={"order_id": o1, "amount": 99_900, "payment_type": "partial", "payment_method": "naqd"})
_h1 = holat(o1)
check("G1a chegirmani yozishda xato — 500 va HECH NARSA saqlanmagan (to'lov yo'q, kelishilgan 100 000)",
      kod == 500 and _h1["tolovlar"] == [] and abs(_h1["kelishilgan"] - 100_000) < 0.01 and "[WRITEOFF:" not in _h1["izoh"],
      (kod, _h1))
with himoyasiz():
    kod, d = tolov(o1, 99_900, write_off_remainder="true")
_h1 = holat(o1)
check("G1b 8 s dan keyin qayta urinish — 200, BITTA to'lov, chegirma 100, qarz 0",
      kod == 200 and _h1["tolovlar"] == [99_900.0] and abs(_h1["kelishilgan"] - 99_900) < 0.01 and _h1["qarz"] == 0,
      (kod, d, _h1))
o2 = buyurtma(100_000)
with buz(crud, "get_order"):
    kod, _ = so("post", "/api/payments", sun_iy=True,
                json={"order_id": o2, "amount": 30_000, "payment_type": "partial", "payment_method": "naqd"})
_h2 = holat(o2)
check("G2a to'lovdan keyingi qadamda xato — 500 va to'lov saqlanmagan", kod == 500 and _h2["tolovlar"] == [], (kod, _h2))
with himoyasiz():
    kod, d = tolov(o2, 30_000)
_h2 = holat(o2)
check("G2b 8 s dan keyin qayta urinish — BITTA to'lov (30 000), qarz 70 000",
      kod == 200 and _h2["tolovlar"] == [30_000.0] and _h2["qarz"] == 70_000, (kod, _h2))
o2b = buyurtma(100_000)
with buz(crud, "get_order"):
    so("post", "/api/payments", sun_iy=True,
       json={"order_id": o2b, "amount": 40_000, "payment_type": "partial", "payment_method": "naqd"})
kod, d = tolov(o2b, 40_000)
check("G2c 8 s ICHIDA qayta urinish — yangi to'lov (birinchisi saqlanmagan), duplicate False",
      kod == 200 and isinstance(d, dict) and d.get("duplicate") is False and holat(o2b)["tolovlar"] == [40_000.0],
      (kod, d, holat(o2b)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H to'lovni o'chirish — nosozlik")
o3 = buyurtma(100_000)
kod, d = tolov(o3, 20_000)
_p3 = d.get("payment_id") if isinstance(d, dict) else None
with buz(crud, "_loyiha_tolangan_yangila"):
    kod, _ = so("delete", f"/api/payments/{_p3}", sun_iy=True)
check("H1a o'chirishda xato — 500, to'lov QOLDI va audit 'deleted' YO'Q", kod == 500
      and holat(o3)["tolovlar"] == [20_000.0] and audit("payment", "deleted", _p3) == 0,
      (kod, holat(o3), audit("payment", "deleted", _p3)))
kod, _ = so("delete", f"/api/payments/{_p3}")
check("H1b qayta urinish — 200, to'lov yo'q, audit AYNAN 1", kod == 200 and holat(o3)["tolovlar"] == []
      and audit("payment", "deleted", _p3) == 1, (kod, audit("payment", "deleted", _p3)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("I butunlay o'chirish — nosozlik")
o4 = buyurtma(100_000)
_r1 = so("post", f"/api/orders/{o4}/ready")[0]
_r2 = so("delete", f"/api/orders/{o4}")[0]
with buz(crud, "log_activity", shart=lambda db, action, *a, **k: action == "permanently_deleted"):
    kod, _ = so("delete", f"/api/orders/{o4}/permanent", sun_iy=True)
check("I1a buyurtma: audit yozishda xato — 500, buyurtma O'CHMAGAN (izsiz o'chish yo'q)",
      (_r1, _r2) == (200, 200) and kod == 500 and holat(o4)["bor"] is True
      and audit("order", "permanently_deleted", o4) == 0, (_r1, _r2, kod, holat(o4)["bor"]))
kod, _ = so("delete", f"/api/orders/{o4}/permanent")
check("I1b qayta urinish — 200, buyurtma yo'q, audit 1", kod == 200 and holat(o4)["bor"] is False
      and audit("order", "permanently_deleted", o4) == 1, kod)
s = SessionLocal()
_pr = Project(company_id=1, client_name="ATO bo'sh", project_name="ATO bo'sh", total_budget=0, total_paid=0)
s.add(_pr)
s.commit()
P2 = _pr.id
s.close()
_r3 = so("delete", f"/api/projects/{P2}")[0]
with buz(crud, "log_activity", shart=lambda db, action, *a, **k: action == "permanently_deleted"):
    kod, _ = so("delete", f"/api/projects/{P2}/permanent", sun_iy=True)
check("I3a loyiha: audit yozishda xato — 500, loyiha O'CHMAGAN", _r3 == 200 and kod == 500 and loyiha_bor(P2) is True
      and audit("project", "permanently_deleted", P2) == 0, (_r3, kod, loyiha_bor(P2)))
kod, _ = so("delete", f"/api/projects/{P2}/permanent")
check("I3b qayta urinish — 200, loyiha yo'q, audit 1", kod == 200 and loyiha_bor(P2) is False
      and audit("project", "permanently_deleted", P2) == 1, kod)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("X 5xx")
_xx = [h for h in HOLATLAR if h[1] >= 500 and not h[2]]
check(f"X1 {len(HOLATLAR)} so'rovda 5xx faqat sun'iy xatolarda", not _xx, _xx[:5])

section("S statik")
_sp = inspect.getsource(main.api_create_payment)
check("S1 to'lov: create_payment, get_order, chegirma — bitta tranzaksiya bloki ichida",
      "with crud.bitta_tranzaksiya(db):" in _sp
      and _sp.find("with crud.bitta_tranzaksiya(db):") < _sp.find("payment = crud.create_payment(")
      < _sp.find("order = crud.get_order(") < _sp.find("_tolov_qoldigini_chegirmaga(db, order)")
      < _sp.find("except crud.OverpaymentWarning"))
_wo = getattr(main, "_tolov_qoldigini_chegirmaga", None)
check("S2 chegirma yordamchisi o'zi commit qilmaydi", _wo is not None and "db.commit()" not in inspect.getsource(_wo))
for _nom, _ichki in (("api_delete_payment", "crud.delete_payment("),
                     ("api_permanent_delete_order", "crud.permanent_delete_order("),
                     ("api_permanent_delete_project", "crud.permanent_delete_project(")):
    _src = inspect.getsource(getattr(main, _nom))
    _b = _src.find("with crud.bitta_tranzaksiya(db):")
    check(f"S3 {_nom} — yozuvchi chaqiruv blok ichida", _b >= 0 and _src.find(_ichki) > _b)

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
engine.dispose()
sys.exit(1 if FAIL else 0)
