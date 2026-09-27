#!/usr/bin/env python3
"""test_loyiha_izchillik.py — kech98 (2026-09-27), 130-band.

NIMA UCHUN KERAK
----------------
O'LCHANGAN (kech98 `work/probe130.py`, asl = zip 91, SQLite = PG):
  (a) `/projects` kartasi "N ta buyurtma" (`crud.get_projects_with_stats.orders_count = len(p.orders)`) yumshoq
      o'chirilgan buyurtmani ham sanardi: loyihada jarayondagi + qoralama + yumshoq o'chirilgan "Tayyor" (+ butunlay
      o'chirilgan) — karta "3 ta buyurtma", loyihaning "Buyurtmalar" yorlig'i (`/api/orders?project_id`) va loyiha
      detali (`/api/projects/{id}/detail-stats` total_orders) — 2;
  (b) `crud.check_financial_consistency` 2-tekshiruvi ortiqcha to'langan (foydalanuvchi TASDIQLAGAN) buyurtmani
      "Qarz hisobi mos emas" deb chiqarardi ("Yozilgan qarz: 0 so'm, lekin kutilgan: −5,000 so'm") — `/logs` "Tizim
      tekshiruvi" da "1 ta moliyaviy nomuvofiqlik". `Order.debt_amount` qoidasi (tiyin, qoldiq yarim so'mdan oshmasa 0,
      ortiqcha — 0) bo'yicha qarz 0 — TO'G'RI.
YECHIM (texnik): (a) karta soni — o'chirilmagan buyurtmalar (yorliq va detal bilan bir xil); summa — moliyaviy tarix
(o'chirilganlar ham, avvalgidek); (b) kutilgan qarz — `debt_amount` qoidasi bilan (tekshiruv qarz hisobining O'ZI
buzilganini topadi — B6 sezgirlik isboti).

BO'LIMLAR
---------
  A loyiha kartasi soni ↔ "Buyurtmalar" yorlig'i ↔ detal; summa (moliyaviy tarix); B korxona;
  B izchillik: ortiqcha to'langan / qoldiq 0.40 / 0.60 / to'liq / qisman; health-check; sezgirlik (buzilgan qarz
    hisobi ushlanadi); X 5xx yo'q; S statik.

ISHLATISH
---------
    python3 tools/test_loyiha_izchillik.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_loyiha_izchillik.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import re
import sys
import inspect
import tempfile
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "loyiha_izchillik_test"
_T = tempfile.mkdtemp(prefix="liz_")
_DB = os.path.join(_T, "loyiha_izchillik_test.db")

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
import models                                      # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, Inventory, Project, Order   # noqa: E402
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
        return None


# ── Fikstura ────────────────────────────────────────────────────────────────────────────────────────────────
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="LIZ Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "LIZ_a", "Parol123!", UserRole.ADMIN, "LIZ A", company_id=1)
    auth.create_user(_db, "LIZ_b", "Parol123!", UserRole.ADMIN, "LIZ B", company_id=2)
_pen = {}
for _cid in (1, 2):
    _p = Inventory(company_id=_cid, item_name=f"LIZ Penoplast {_cid}", unit="blok", stock_quantity=100_000,
                   price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True,
                   category="Penoplast")
    _db.add(_p)
    _db.commit()
    _pen[_cid] = _p.id
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c


CA, CB = _kir("LIZ_a"), _kir("LIZ_b")
QADAM = []
_N = {"n": 0}


def loyiha(cid, nom):
    s = SessionLocal()
    p = Project(company_id=cid, client_name=f"LIZ {nom}", project_name=f"LIZ {nom}", total_budget=0, total_paid=0)
    s.add(p)
    s.commit()
    i = p.id
    s.close()
    return i


def buyurtma(klient, cid, pid, narx, **k):
    _N["n"] += 1
    t = {"project_id": pid, "order_type": "product", "loy_kg": 0, "items": [
        {"name": f"LIZ panel {_N['n']}", "category": "panel", "width": 30, "thickness": 5, "quantity": 2,
         "unit_price": narx, "is_coated": False, "penoplast_id": _pen[cid]}]}
    t.update(k)
    r = req(klient, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
    QADAM.append(("buyurtma", r.status_code))
    return (js(r) or {}).get("id") if r.status_code == 200 else None


def tolov(klient, oid, summa, tasdiq=True):
    r = req(klient, "post", "/api/payments", json={"order_id": oid, "amount": summa, "payment_type": "partial",
                                                   "payment_method": "naqd", "confirm_overpay": tasdiq})
    QADAM.append(("to'lov", r.status_code))
    return r.status_code


def karta(klient, pid):
    h = req(klient, "get", "/projects")
    m = re.search(r'data-id="%d".*?(\d+) ta buyurtma' % pid, getattr(h, "text", ""), re.S)
    return int(m.group(1)) if m else None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A loyiha kartasi soni ↔ Buyurtmalar yorlig'i ↔ detal")
P1 = loyiha(1, "P1")
O_JAR = buyurtma(CA, 1, P1, 41_000)
O_SOFT = buyurtma(CA, 1, P1, 42_000)
QADAM.append(("tayyor", req(CA, "post", f"/api/orders/{O_SOFT}/ready").status_code))
QADAM.append(("o'chirish (yumshoq)", req(CA, "delete", f"/api/orders/{O_SOFT}").status_code))
O_QOR = buyurtma(CA, 1, P1, 43_000, is_draft=True)
O_HARD = buyurtma(CA, 1, P1, 44_000)
QADAM.append(("o'chirish (butunlay)", req(CA, "delete", f"/api/orders/{O_HARD}").status_code))
P2 = loyiha(1, "P2 faqat o'chirilgan")
O_P2 = buyurtma(CA, 1, P2, 45_000)
QADAM.append(("tayyor", req(CA, "post", f"/api/orders/{O_P2}/ready").status_code))
QADAM.append(("o'chirish (yumshoq)", req(CA, "delete", f"/api/orders/{O_P2}").status_code))
P3 = loyiha(1, "P3 bo'sh")
PB = loyiha(2, "PB")
O_B = buyurtma(CB, 2, PB, 46_000)
check(f"A0 fikstura qadamlari 200 ({len(QADAM)} ta)", all(k == 200 for _, k in QADAM), [q for q in QADAM if q[1] != 200])
_s = SessionLocal()
_hol = {o.id: bool(o.is_deleted) for o in _s.query(Order).filter(Order.project_id.in_([P1, P2])).all()}
_st = {p.id: p for p in crud.get_projects_with_stats(_s, company_id=1)}
_sum_kut = sum(float(o.total_amount or 0) for o in _s.query(Order).filter(Order.project_id == P1).all())
_s.close()
check("A1 fikstura: P1 da 3 buyurtma qoldi (yumshoq o'chirilgan BITTA), butunlay o'chirilgan yo'q; P2 — faqat o'chirilgan",
      _hol == {O_JAR: False, O_SOFT: True, O_QOR: False, O_P2: True}, _hol)
_yor = [o["id"] for o in (js(req(CA, "get", "/api/orders", params={"project_id": P1})) or [])]
_det = js(req(CA, "get", f"/api/projects/{P1}/detail-stats")) or {}
check("A2 Buyurtmalar yorlig'i: jarayondagi + qoralama (2)", sorted(_yor) == sorted([O_JAR, O_QOR]), _yor)
check("A3 loyiha detali total_orders = 2", _det.get("total_orders") == 2, _det)
check("A4 get_projects_with_stats.orders_count = yorliq soni (2; asl: 3)", getattr(_st.get(P1), "orders_count", None) == len(_yor) == 2,
      getattr(_st.get(P1), "orders_count", None))
check("A5 /projects kartasi \"2 ta buyurtma\" (asl: 3)", karta(CA, P1) == 2, karta(CA, P1))
check("A6 faqat o'chirilgan buyurtmali loyiha — 0 (asl: 1); bo'sh loyiha — 0",
      karta(CA, P2) == 0 and karta(CA, P3) == 0 and getattr(_st.get(P2), "orders_count", None) == 0, (karta(CA, P2), karta(CA, P3)))
check("A7 summa — moliyaviy tarix (o'chirilgan buyurtma ham, avvalgidek)", abs(getattr(_st.get(P1), "orders_sum", -1) - _sum_kut) < 1e-6
      and _sum_kut > 0, (getattr(_st.get(P1), "orders_sum", None), _sum_kut))
check("A8 ro'yxat (p.orders) o'zgarmagan — o'chirilgani ham ichida (summa uchun)",
      sorted(o.id for o in (_st.get(P1).orders or [])) == sorted([O_JAR, O_SOFT, O_QOR]) if _st.get(P1) else False)
check("A9 B korxona: B kartasi 1, A sahifasida B loyihasi yo'q", karta(CB, PB) == 1 and karta(CA, PB) is None, (karta(CB, PB), karta(CA, PB)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B moliyaviy izchillik — qarz qoidasi (debt_amount bilan bir xil)")
P4 = loyiha(1, "P4")
O_ORT = buyurtma(CA, 1, P4, 10_000)
O_T40 = buyurtma(CA, 1, P4, 10_000.2)
O_T60 = buyurtma(CA, 1, P4, 10_000.3)
O_TOL = buyurtma(CA, 1, P4, 10_001)
O_QIS = buyurtma(CA, 1, P4, 10_002)
_k = [tolov(CA, O_ORT, 25_000), tolov(CA, O_T40, 20_000), tolov(CA, O_T60, 20_000), tolov(CA, O_TOL, 20_002),
      tolov(CA, O_QIS, 5_000)]
check("B0 to'lovlar 200 (ortiqcha — tasdiq bilan)", _k == [200] * 5, _k)
_s = SessionLocal()
_q = {o.id: (o.kelishilgan_summa, float(o.paid_amount or 0), o.debt_amount) for o in _s.query(Order).filter(
    Order.id.in_([O_ORT, O_T40, O_T60, O_TOL, O_QIS])).all()}
_fc = crud.check_financial_consistency(_s, company_id=1)
_s.close()
check("B1 qarzlar: ortiqcha 0, qoldiq 0.40 → 0, qoldiq 0.60 → 0.6, to'liq 0, qisman 15 004",
      [_q[i][2] for i in (O_ORT, O_T40, O_T60, O_TOL, O_QIS)] == [0, 0.0, 0.6, 0.0, 15_004.0], _q)
_dm = [x for x in _fc["issues"] if x["type"] == "debt_mismatch"]
check("B2 debt_mismatch YO'Q (asl: ortiqcha to'langan buyurtma \"kutilgan −5,000\" bilan)", not _dm, _dm)
check("B3 izchillik natijasi: hech qanday muammo yo'q", _fc["issues_found"] == 0 and not _fc["issues"], _fc["issues"][:3])
_hc = js(req(CA, "get", "/api/system/health-check")) or {}
check("B4 health-check: moliyaviy nomuvofiqlik 0", (_hc.get("financial") or {}).get("issues_found") == 0, _hc.get("financial"))
_fcb = None
_s = SessionLocal()
try:
    _fcb = crud.check_financial_consistency(_s, company_id=2)
finally:
    _s.close()
check("B5 B korxona izchilligi — A buyurtmalari yo'q", _fcb is not None and _fcb["issues_found"] == 0, _fcb)
# sezgirlik: qarz hisobi (debt_amount) buzilsa — tekshiruv ushlaydi
_asl_prop = models.Order.debt_amount
try:
    models.Order.debt_amount = property(lambda self: float(_asl_prop.fget(self) or 0) + 10)
    _s = SessionLocal()
    try:
        _fcs = crud.check_financial_consistency(_s, company_id=1)
    finally:
        _s.close()
finally:
    models.Order.debt_amount = _asl_prop
_dms = {x["label"] for x in _fcs["issues"] if x["type"] == "debt_mismatch"}
_s = SessionLocal()
_on = {o.id: o.order_number for o in _s.query(Order).filter(Order.company_id == 1, Order.is_deleted.is_(False)).all()}
_s.close()
check(f"B6 sezgirlik: qarz hisobi sun'iy +10 buzilsa — HAR o'chirilmagan buyurtma debt_mismatch ({len(_on)} ta)",
      _dms == {f"Buyurtma {n}" for n in _on.values()} and len(_on) >= 7, (len(_dms), len(_on)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("X 5xx")
_xx = [h for h in HOLATLAR if h[1] >= 500]
check(f"X1 {len(HOLATLAR)} so'rovda 5xx yo'q", not _xx, _xx[:5])

section("S statik")
_sp = inspect.getsource(crud.get_projects_with_stats)
_sf = inspect.getsource(crud.check_financial_consistency)
check("S1 karta soni — o'chirilmaganlar", "orders_count = sum(1 for o in (p.orders or []) if not o.is_deleted)" in _sp
      and "orders_count = len(p.orders)" not in _sp)
check("S2 izchillik 2-tekshiruvi — debt_amount qoidasi (tiyin + bardosh)",
      "expected_debt = pul_tiyin(agreed - paid)" in _sf and "if expected_debt <= QARZ_BARDOSH:" in _sf
      and "paid = pul_tiyin_yigindi(p.amount for p in pays)" in _sf
      and "expected_debt = agreed - paid" not in _sf)

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
engine.dispose()
sys.exit(1 if FAIL else 0)
