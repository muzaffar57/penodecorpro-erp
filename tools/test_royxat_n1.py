#!/usr/bin/env python3
"""test_royxat_n1.py — kech97 (2026-09-27), 116-band 1-qadam (buyurtma / loyiha N+1) + 114-band (ro'yxat tartibi).

NIMA UCHUN KERAK
----------------
O'LCHANGAN (kech97 `work/probe116.py` — BARCHA 94 GET marshrut, fikstura + 10 loyiha / buyurtma, asl = zip 90,
SQLite = PG): 12 marshrutda SQL so'rovlar soni buyurtma / loyiha boshiga o'sardi — `/api/system/health-check` +50,
`/orders` +40, `/api/orders` +40, `/debts` +20, `/api/dashboard/deliveries` +20, `/api/dashboard/debts` +20,
`/projects` +10, `/api/projects/dashboard-stats` +10, `/api/reports/alerts` +10, `/api/reports/business-health` +10,
`/api/finance/debt-summary` +10, `/api/finance/report-pdf` +10; `/api/dashboard/charts` — "Tayyor" buyurtma boshiga.
Sabab: har buyurtmaning to'lovlari (qarz), detallari, detal yetkazishlari, qaytarishlari, loyiha buyurtmalari —
alohida lazy so'rov; moliyaviy izchillik tekshiruvi esa buyurtma / detal boshiga ALOHIDA `db.query(...)` qilardi.

114-band (kech90 `probe90_tartib`): PostgreSQL da ORDER BY siz ro'yxat tartibi so'rov SHAKLIGA (lazy `= ?` /
selectinload `IN`) va qatorning jismoniy joyiga (UPDATE dan keyin ko'chadi) bog'liq — bir xil ro'yxat ikki yo'lda turli
tartibda chiqardi (kech97 fikstura116, PG: 1-loyiha buyurtmalari lazy [8, 2, 14, 9, 5, 15, …] — id tartibi EMAS).

YECHIM (texnik): munosabatlarga `order_by=id` (Project.orders, Order.items / returns / payments / gips_additives,
OrderItem.deliveries); ro'yxat so'rovlariga `selectinload`; izchillik tekshiruvi — munosabatlar orqali.
ISBOT (work/dump116.py, 427 chaqiruv, ESKI ↔ YANGI kod bir bazada): SQLite AYNAN; PG — faqat 1-loyiha buyurtmalari
ro'yxati TARTIBI (lazy jismoniy → id), mazmun farqi 0; TENANT_FILTER=1 da ham shunday (farq — faqat health-check dagi
jarayon so'rovlar hisoblagichi).

BO'LIMLAR
---------
  A MIQYOS: +5 loyiha / buyurtma — 13 marshrut so'rovlari O'ZGARMAYDI; ASL (lazy) yo'l bilan esa o'sadi (nazorat);
  B natija ASL (hamma munosabat lazy) yo'l bilan AYNAN — 11 funksiya × 3 korxona holati + 12 marshrut javobi;
    mustaqil hisob: qarz statistikasi, `/api/orders` to'lovlari, yetkazish statistikasi, izchillik (ortiqcha to'lov,
    ortiqcha yetkazish, narxsiz detal);
  C 114: UPDATE dan keyin (PG — jismoniy joy o'zgaradi) lazy va selectinload ro'yxatlari id tartibida, lazy SQL da
    ORDER BY; D begona korxona; X 5xx yo'q; S statik.

ISHLATISH
---------
    python3 tools/test_royxat_n1.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_royxat_n1.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import json
import hashlib
import inspect
import tempfile
import contextlib
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "royxat_n1_test"
_T = tempfile.mkdtemp(prefix="rn1_")
_DB = os.path.join(_T, "royxat_n1_test.db")

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
import models                                      # noqa: E402
import schemas                                     # noqa: E402
import sqlalchemy.orm as _orm                      # noqa: E402
from sqlalchemy.orm import strategy_options as _so  # noqa: E402
from sqlalchemy import event, text                 # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (UserRole, Inventory, Project, Order, OrderItem, Payment, Delivery,   # noqa: E402
                    DeliveryItem, ReturnItem, ReturnReason, QARZ_BARDOSH)
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


# ── SQL hisoblagich ─────────────────────────────────────────────────────────────────────────────────────────
SANOQ = {"n": 0, "on": False, "sql": []}


@event.listens_for(engine, "before_cursor_execute")
def _sana(conn, cursor, statement, parameters, context, executemany):
    if SANOQ["on"]:
        SANOQ["n"] += 1
        SANOQ["sql"].append(statement)


@contextlib.contextmanager
def sanoq():
    SANOQ["n"] = 0
    SANOQ["sql"] = []
    SANOQ["on"] = True
    try:
        yield SANOQ
    finally:
        SANOQ["on"] = False


@contextlib.contextmanager
def asl_yol():
    """ASL (kech97 gacha) yuklash: kod ishlatadigan `selectinload` — `lazyload` (zanjirdagi ham). Natija shu yo'l
    bilan AYNAN bo'lishi, so'rovlar esa qator boshiga o'sishi kerak."""
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
            return {k: _v(v) for k, v in y.items() if k != "checked_at"}
        if isinstance(y, list):
            return [_v(v) for v in y]
        return y
    return json.dumps(_v(json.loads(json.dumps(x, default=str, sort_keys=True))), sort_keys=True)


def tiyin(x):
    return Decimal(repr(float(x or 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── Fikstura ────────────────────────────────────────────────────────────────────────────────────────────────
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="RN1 Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "RN1_a", "Parol123!", UserRole.ADMIN, "RN1 A", company_id=1)
    auth.create_user(_db, "RN1_b", "Parol123!", UserRole.ADMIN, "RN1 B", company_id=2)
_pa = Inventory(company_id=1, item_name="RN1 Penoplast A", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
_pb = Inventory(company_id=2, item_name="RN1 Penoplast B", unit="blok", stock_quantity=100_000, price_per_unit=400_000,
                volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
_db.add_all([_pa, _pb])
_db.commit()
PA, PB = _pa.id, _pb.id
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c


CA, CB = _kir("RN1_a"), _kir("RN1_b")
QADAM = []
_NOM = {"n": 0}


def _loyiha(cid, nom):
    s = SessionLocal()
    p = Project(company_id=cid, client_name=f"RN1 {nom}", project_name=f"RN1 {nom}", total_budget=0, total_paid=0)
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    return pid


def _buyurtma(klient, pid, peno, i, **k):
    _NOM["n"] += 1
    t = {"project_id": pid, "order_type": "product", "loy_kg": 0, "items": [
        {"name": f"RN1 panel {_NOM['n']}", "category": "panel", "width": 30, "thickness": 5, "quantity": 3 + i,
         "unit_price": 41_000 + 10 * i, "is_coated": False, "penoplast_id": peno},
        {"name": f"RN1 profil {_NOM['n']}", "category": "profil", "width": 10, "thickness": 5, "length": 4 + i,
         "quantity": 1, "unit_price": 22_000.5, "is_coated": False, "penoplast_id": peno}]}
    t.update(k)
    r = req(klient, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
    QADAM.append(("buyurtma", r.status_code))
    return (js(r) or {}).get("id") if r.status_code == 200 else None


def _tolov(klient, oid, summa, **k):
    t = {"order_id": oid, "amount": summa, "payment_type": "partial", "payment_method": "naqd"}
    t.update(k)
    r = req(klient, "post", "/api/payments", json=t)
    QADAM.append(("to'lov", r.status_code))
    return r


def _tayyor(klient, oid):
    r = req(klient, "post", f"/api/orders/{oid}/ready")
    QADAM.append(("tayyor", r.status_code))
    return r


def _yetkaz(oid, qty=(1.5, 0.25)):
    s = SessionLocal()
    its = s.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()
    d = Delivery(order_id=oid, delivery_number=f"RN1-Y{oid}", delivered_at=datetime.utcnow(), delivered_by="RN1")
    s.add(d)
    s.flush()
    for it in its:
        for q in qty:
            s.add(DeliveryItem(delivery_id=d.id, order_item_id=it.id, quantity=q, unit="metr"))
    s.commit()
    s.close()


def _qaytar(oid):
    s = SessionLocal()
    it = s.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).first()
    s.add(ReturnItem(company_id=1, order_id=oid, order_item_id=it.id, item_name=it.name, quantity=1, unit="metr",
                     reason=ReturnReason.EXCESS, ortiqcha_miqdor=0.5, returned_at=datetime.utcnow()))
    s.commit()
    s.close()


def qosh(n, teg):
    """n ta yangi loyiha + buyurtma (A): 2 to'lov, juftlari "Tayyor" + yetkazish, har uchinchisida qaytarish."""
    ids = []
    for i in range(n):
        pid = _loyiha(1, f"{teg}{i}")
        oid = _buyurtma(CA, pid, PA, i)
        ids.append(oid)
        if not oid:
            continue
        _tolov(CA, oid, 10_000.25 + i)
        _tolov(CA, oid, 20_000 + 7 * i)
        if i % 2 == 0:
            _tayyor(CA, oid)
            _yetkaz(oid)
        if i % 3 == 0:
            _qaytar(oid)
    return ids


ASOS = qosh(4, "asos")
# maxsus holatlar: ortiqcha to'langan, qoralama, yumshoq o'chirilgan (to'lovi bilan), eski (40 kun) qarzdor,
# narxsiz detal (qoralama EMAS), ortiqcha yetkazilgan detal; B korxona buyurtmalari
_pm = _loyiha(1, "maxsus")
O_ORT = _buyurtma(CA, _pm, PA, 1)
_s = SessionLocal()
_qarz = float(_s.get(Order, O_ORT).debt_amount or 0) if O_ORT else 0
_s.close()
_tolov(CA, O_ORT, round(_qarz + 1_000, 2), payment_type="final", confirm_overpay=True)
O_QOR = _buyurtma(CA, _pm, PA, 2, is_draft=True)
O_OCH = _buyurtma(CA, _pm, PA, 3)
_tolov(CA, O_OCH, 5_000.5)
O_ESKI = _buyurtma(CA, _pm, PA, 4)
_tolov(CA, O_ESKI, 1_234.56)
O_NOL = _buyurtma(CA, _pm, PA, 5)
O_KOP = _buyurtma(CA, _pm, PA, 6)
_tayyor(CA, O_KOP)
_yetkaz(O_KOP, qty=(50.0,))
_s = SessionLocal()
_s.execute(Order.__table__.update().where(Order.__table__.c.id == O_OCH).values(is_deleted=True))
_s.execute(Order.__table__.update().where(Order.__table__.c.id == O_ESKI).values(
    created_at=datetime.utcnow() - timedelta(days=40)))
_nol_it = _s.query(OrderItem).filter(OrderItem.order_id == O_NOL).order_by(OrderItem.id).first()
_s.execute(OrderItem.__table__.update().where(OrderItem.__table__.c.id == _nol_it.id).values(unit_price=0))
_s.commit()
_s.close()
_pbq = _loyiha(2, "B")
O_B1 = _buyurtma(CB, _pbq, PB, 0)
_tolov(CB, O_B1, 7_777.77)
O_B2 = _buyurtma(CB, _pbq, PB, 1)
_tayyor(CB, O_B2)
_tolov(CB, O_B2, 11_000)

section("F fikstura")
check(f"F1 fikstura qadamlari 200 ({len(QADAM)} ta)", all(k == 200 for _, k in QADAM),
      [q for q in QADAM if q[1] != 200][:5])
check("F2 hamma buyurtma yaratildi", all(ASOS) and all((O_ORT, O_QOR, O_OCH, O_ESKI, O_NOL, O_KOP, O_B1, O_B2)))

Y, M = datetime.utcnow().year, datetime.utcnow().month
MARSHRUT = [
    ("orders", "/orders", None), ("ordersAll", "/orders", {"show_all": "true"}), ("apiorders", "/api/orders", None),
    ("debts", "/debts", None), ("deliv", "/api/dashboard/deliveries", None), ("debtstats", "/api/dashboard/debts", None),
    ("projects", "/projects", None), ("projdash", "/api/projects/dashboard-stats", None),
    ("alerts", "/api/reports/alerts", None), ("health", "/api/reports/business-health", None),
    ("debtsum", "/api/finance/debt-summary", {"year": Y, "month": M}), ("charts", "/api/dashboard/charts", None),
    ("syshealth", "/api/system/health-check", None),
]


def olchov(klient):
    n, jav = {}, {}
    for k, url, par in MARSHRUT:
        with sanoq() as sq:
            r = req(klient, "get", url, params=par)
        n[k] = sq["n"]
        if k == "syshealth":        # jarayon so'rovlar hisoblagichi (tenant_filter.stats) — so'rovlar soniga bog'liq
            d = js(r) or {}
            d.pop("tenant_filter", None)
            jav[k] = (r.status_code, jsonla(d))
        else:
            jav[k] = (r.status_code, hashlib.sha256(r.content).hexdigest())
    return n, jav


# ── A. Miqyos ───────────────────────────────────────────────────────────────────────────────────────────────
section("A miqyos: +5 loyiha / buyurtma — so'rovlar o'zgarmaydi (ASL lazy yo'l bilan o'sadi)")
olchov(CA)          # qizdirish: jarayonning birinchi chaqiruvidagi bir martalik so'rovlar (sozlamalar keshi) hisobga kirmasin
N0, J0 = olchov(CA)
with asl_yol():
    L0, LJ0 = olchov(CA)
YANGI = qosh(5, "miq")
N1, J1 = olchov(CA)
with asl_yol():
    L1, LJ1 = olchov(CA)
for i, (k, url, _) in enumerate(MARSHRUT, 1):
    check(f"A{i} {url} ({k}): {N0[k]} -> {N1[k]} so'rov (o'zgarmaydi)", N1[k] == N0[k], (N0[k], N1[k]))
for i, (k, url, _) in enumerate(MARSHRUT, 1):
    check(f"A{i}n nazorat — ASL yo'lda {url} ({k}) o'sadi: {L0[k]} -> {L1[k]} (>= +3)", L1[k] - L0[k] >= 3,
          (L0[k], L1[k]))
check("A20 javoblar hammasi 200", all(J1[k][0] == 200 for k in J1), {k: J1[k][0] for k in J1})

# ── B. Natija ASL yo'l bilan AYNAN ──────────────────────────────────────────────────────────────────────────
section("B natija ASL (lazy) yo'l bilan AYNAN")
for i, (k, url, _) in enumerate(MARSHRUT, 1):
    check(f"B{i} {url} ({k}) javobi ASL yo'l bilan AYNAN", J1[k] == LJ1[k], (J1[k], LJ1[k]))


def _prj(s, cid):
    return [{"id": p.id, "soni": p.orders_count, "summa": p.orders_sum, "qarz": p.debt, "haq": p.actual_sum,
             "royxat": [o.id for o in (p.orders or [])]} for p in crud.get_projects_with_stats(s, company_id=cid)]


def _main(s, cid):
    return [{"id": o.id, "tolik": o.is_fully_delivered, "qarz": o.debt_amount,
             "detal": [(it.id, it.delivered_qty, it.remaining_qty, it.ortiqcha_qty) for it in (o.items or [])],
             "tolov": [p.id for p in (o.payments or [])], "qaytarish": [r.id for r in (o.returns or [])]}
            for o in crud.get_orders_for_main_page(s, days=90, show_all=True, company_id=cid, royxat_uchun=True)]


FUNK = [
    ("debtstats", lambda s, c: crud.get_debt_stats(s, company_id=c)),
    ("delivstats", lambda s, c: crud.get_delivery_stats(s, company_id=c)),
    ("alerts", lambda s, c: services.get_business_alerts(s, company_id=c)),
    ("health", lambda s, c: services.get_business_health(s, company_id=c)),
    ("fulldebt", lambda s, c: services.get_full_debt_summary(s, Y, M, company_id=c)),
    ("charts", lambda s, c: services.get_chart_data(s, company_id=c)),
    ("fincons", lambda s, c: crud.check_financial_consistency(s, company_id=c)),
    ("prjstats", _prj),
    ("projdash", lambda s, c: crud.get_projects_dashboard_stats(s, company_id=c)),
    ("orders", lambda s, c: [schemas.OrderRead.model_validate(o).model_dump() for o in crud.get_orders(s, company_id=c)]),
    ("mainpage", _main),
]


def chaqir(fn, cid):
    s = SessionLocal()
    try:
        with sanoq() as sq:
            v = fn(s, cid)
        return jsonla(v), sq["n"]
    except Exception as e:             # noqa: BLE001
        return f"XATO {type(e).__name__}: {e}", -1
    finally:
        s.rollback()
        s.close()


j = 20
NATIJA = {}
for nom, fn in FUNK:
    for cid in (1, 2, None):
        yangi, ny = chaqir(fn, cid)
        with asl_yol():
            asl, na = chaqir(fn, cid)
        NATIJA[(nom, cid)] = yangi
        j += 1
        check(f"B{j} {nom} c{cid}: ASL yo'l bilan AYNAN (so'rovlar {na} -> {ny})",
              yangi == asl and not yangi.startswith("XATO"), (yangi[:300], asl[:300]))

# mustaqil hisob
section("B2 mustaqil hisob")
_s = SessionLocal()
_orders_a = _s.query(Order).filter(Order.company_id == 1, Order.is_deleted.isnot(True),
                                   Order.is_archived == False).order_by(Order.id).all()   # noqa: E712
_tol = {}
for p in _s.query(Payment).all():
    _tol.setdefault(p.order_id, []).append(p)


def _qarz(o):
    kel = Decimal(repr(float(o.agreed_amount))) if o.agreed_amount is not None else Decimal(repr(float(o.total_amount or 0)))
    tol = sum((Decimal(repr(float(p.amount or 0))) for p in _tol.get(o.id, [])), Decimal("0"))
    q = (kel - tol).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return q if q > Decimal(repr(QARZ_BARDOSH)) else Decimal("0")


_kutilgan_qarz = {o.id: _qarz(o) for o in _orders_a}
_ds = json.loads(NATIJA[("debtstats", 1)])
check("B40 qarz statistikasi: qarzdorlar = mustaqil hisob (to'lovlar SQL, Decimal)",
      sorted(d["order_id"] for d in _ds["debt_orders"]) == sorted(k for k, v in _kutilgan_qarz.items() if v > 0),
      (_ds["debt_orders_count"], {k: str(v) for k, v in _kutilgan_qarz.items()}))
check("B41 qarz statistikasi: jami qarz = mustaqil hisob",
      tiyin(_ds["total_debt"]) == sum(_kutilgan_qarz.values(), Decimal("0")),
      (_ds["total_debt"], str(sum(_kutilgan_qarz.values(), Decimal("0")))))
_o_ort = _s.get(Order, O_ORT)
check("B42 ortiqcha to'langan buyurtma — qarz 0 (mustaqil hisob ham), qarzdorlar ro'yxatida yo'q",
      _qarz(_o_ort) == 0 and float(_o_ort.debt_amount) == 0 and O_ORT not in [d["order_id"] for d in _ds["debt_orders"]],
      (str(_qarz(_o_ort)), _o_ort.debt_amount, _o_ort.is_archived))
_ao = json.loads(NATIJA[("orders", 1)])
check("B43 /api/orders: har buyurtma to'lovlari = bazadagi to'lovlar (id tartibida)",
      all([p["id"] for p in o["payments"]] == sorted(p.id for p in _tol.get(o["id"], [])) for o in _ao),
      [(o["id"], [p["id"] for p in o["payments"]]) for o in _ao][:6])
check("B44 /api/orders: detallar id tartibida, begona / o'chirilgan buyurtma yo'q",
      all([it["id"] for it in o["items"]] == sorted(it["id"] for it in o["items"]) for o in _ao)
      and O_OCH not in [o["id"] for o in _ao] and O_B1 not in [o["id"] for o in _ao])
_dl = {}
for di in _s.query(DeliveryItem).all():
    _dl[di.order_item_id] = _dl.get(di.order_item_id, 0.0) + float(di.quantity or 0)
_dvs = json.loads(NATIJA[("delivstats", 1)])
_tolik = _qisman = _yoq = 0
for o in _s.query(Order).filter(Order.company_id == 1, Order.is_deleted.isnot(True),
                                Order.status.notin_([models.OrderStatus.DRAFT, models.OrderStatus.CANCELLED])).all():
    jami = yet = 0.0
    for it in o.items:
        b = it.order_qty_normalized
        if b <= 0:
            continue
        jami += b
        yet += min(_dl.get(it.id, 0.0), b)
    f = round(yet / jami * 100, 1) if jami > 0 else 0.0
    if f >= 100:
        _tolik += 1
    elif f > 0:
        _qisman += 1
    else:
        _yoq += 1
check("B45 yetkazish statistikasi = mustaqil hisob (to'liq / qisman / boshlanmagan)",
      (_dvs["fully_delivered"], _dvs["partial_count"], _dvs["not_started"]) == (_tolik, _qisman, _yoq),
      (_dvs, (_tolik, _qisman, _yoq)))
_fc = json.loads(NATIJA[("fincons", 1)])
_tur = {}
for x in _fc["issues"]:
    _tur.setdefault(x["type"], []).append(x["label"])
_on = {o.id: o.order_number for o in _s.query(Order).all()}
check("B46 izchillik: ortiqcha to'langan buyurtma — debt_mismatch (asl qoida: qarz 0 ↔ kutilgan manfiy)",
      any(_on[O_ORT] in l for l in _tur.get("debt_mismatch", [])), _tur)
check("B47 izchillik: ortiqcha yetkazilgan detal — over_delivery", len(_tur.get("over_delivery", [])) >= 1, _tur)
check("B48 izchillik: narxsiz detal (qoralama EMAS) — zero_price_item", any(_on[O_NOL] in l for l in _tur.get("zero_price_item", [])),
      _tur)
check("B49 izchillik: qoralama buyurtma detali zero_price da yo'q, begona korxona yo'q",
      not any(_on[O_QOR] in l for l in _tur.get("zero_price_item", []))
      and not any(_on[O_B1] in l or _on[O_B2] in l for v in _tur.values() for l in v), _tur)


def _eski_izchillik(db, company_id):
    """ASL (zip 90) `check_financial_consistency` 1, 2, 6, 8-tekshiruvlari — buyurtma / detal boshiga ALOHIDA so'rovlar
    (mustaqil nusxa; kmut97a N31 / N32 — mazmun mutatsiyalari "ASL yo'l" bilan ko'rinmasdi)."""
    from models import OrderStatus as _OS
    iss = []
    oq = db.query(Order).filter(Order.is_deleted.is_(False))
    if company_id is not None:
        oq = oq.filter(Order.company_id == company_id)
    orders = oq.all()
    for o in orders:
        items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
        items_sum = sum(float(it.unit_price or 0) * float(it.quantity or 1) for it in items)
        total = float(o.total_amount or 0)
        diff = abs(items_sum - total)
        if diff > 1:
            iss.append({"type": "order_total_mismatch", "label": f"Buyurtma {o.order_number}",
                        "detail": f"Jami summa: {total:,.0f} so'm, lekin detallar yig'indisi: {items_sum:,.0f} so'm",
                        "diff": round(diff, 2)})
    for o in orders:
        pays = db.query(Payment).filter(Payment.order_id == o.id).all()
        paid = sum(float(p.amount or 0) for p in pays)
        debt = float(o.debt_amount or 0)
        expected_debt = o.kelishilgan_summa - paid
        diff = abs(debt - expected_debt)
        if diff > 1:
            iss.append({"type": "debt_mismatch", "label": f"Buyurtma {o.order_number}",
                        "detail": f"Yozilgan qarz: {debt:,.0f} so'm, lekin kutilgan (kelishilgan−to'langan): {expected_debt:,.0f} so'm",
                        "diff": round(diff, 2)})
    iq = db.query(OrderItem)
    if company_id is not None:
        iq = iq.filter(OrderItem.company_id == company_id)
    for it in iq.all():
        cat = (it.category or '').lower()
        ordered = float(it.length or 0) if cat == 'profil' else float(it.quantity or 0)
        delivered = sum(float(di.quantity or 0) for di in
                        db.query(DeliveryItem).filter(DeliveryItem.order_item_id == it.id).all())
        if delivered > ordered + 0.01:
            iss.append({"type": "over_delivery", "label": f"{it.name} (buyurtma #{it.order_id})",
                        "detail": f"Buyurtma qilingan: {ordered:.2f}, lekin topshirilgan: {delivered:.2f}",
                        "diff": round(delivered - ordered, 2)})
    oq8 = db.query(Order).filter(Order.is_deleted.is_(False), Order.status != _OS.DRAFT)
    if company_id is not None:
        oq8 = oq8.filter(Order.company_id == company_id)
    for o in oq8.all():
        for it in db.query(OrderItem).filter(OrderItem.order_id == o.id).all():
            if float(it.unit_price or 0) <= 0:
                iss.append({"type": "zero_price_item", "label": f"{it.name} (buyurtma {o.order_number})",
                            "detail": "Bu detalning narxi \"0\" — unutilib qolgan bo'lishi mumkin", "diff": 0})
    return iss


_TURLAR = ("order_total_mismatch", "debt_mismatch", "over_delivery", "zero_price_item")
for _cid in (1, 2, None):
    _s2 = SessionLocal()
    try:
        _yangi_iz = [x for x in crud.check_financial_consistency(_s2, company_id=_cid)["issues"] if x["type"] in _TURLAR]
    finally:
        _s2.close()
    _s2 = SessionLocal()
    try:
        _eski_iz = _eski_izchillik(_s2, _cid)
    finally:
        _s2.close()
    check(f"B60 izchillik c{_cid}: 4 tekshiruv natijasi ASL algoritm (alohida so'rovlar) bilan AYNAN ({len(_eski_iz)} ta)",
          jsonla(_yangi_iz) == jsonla(_eski_iz), (len(_yangi_iz), len(_eski_iz), _yangi_iz[:2], _eski_iz[:2]))
check("B61 izchillik: debt_mismatch FAQAT ortiqcha to'langan buyurtma", sorted(_tur.get("debt_mismatch", [])) ==
      [f"Buyurtma {_on[O_ORT]}"], _tur.get("debt_mismatch"))
_al = json.loads(NATIJA[("alerts", 1)])
check("B50 ogohlantirish: muddati o'tgan qarzdor (40 kun) — 1 ta",
      any("1 ta qarzdorning muddati" in a["text"] for a in _al), _al)
_s.close()

# ── C. 114 — ro'yxat tartibi ────────────────────────────────────────────────────────────────────────────────
section("C 114: UPDATE dan keyin ro'yxatlar id tartibida (lazy va selectinload)")
_pc = _loyiha(1, "tartib")
C_ORD = [_buyurtma(CA, _pc, PA, i) for i in range(4)]
for _o in C_ORD[:2]:
    _tolov(CA, _o, 3_000.5)
    _tolov(CA, _o, 4_000.25)
    _tayyor(CA, _o)
    _yetkaz(_o)
_s = SessionLocal()
_it0 = _s.query(OrderItem).filter(OrderItem.order_id == C_ORD[0]).order_by(OrderItem.id).first()
_di0 = _s.query(DeliveryItem).filter(DeliveryItem.order_item_id == _it0.id).order_by(DeliveryItem.id).first()
_p0 = _s.query(Payment).filter(Payment.order_id == C_ORD[0]).order_by(Payment.id).first()
for _o in C_ORD[:2]:
    _s.execute(Order.__table__.update().where(Order.__table__.c.id == _o).values(notes="RN1 qayta yozildi"))
_s.execute(OrderItem.__table__.update().where(OrderItem.__table__.c.id == _it0.id).values(notes="RN1 qayta"))
_s.execute(DeliveryItem.__table__.update().where(DeliveryItem.__table__.c.id == _di0.id).values(unit="metr"))
_s.execute(Payment.__table__.update().where(Payment.__table__.c.id == _p0.id).values(notes="RN1 qayta"))
_s.commit()
_xom = [r[0] for r in _s.execute(text("SELECT id FROM orders WHERE project_id = :p"), {"p": _pc}).fetchall()]
_s.close()
print(f"  (ma'lumot) ORDER BY siz xom so'rov tartibi: {_xom} — id tartibi: {_xom == sorted(_xom)}"
      f"{' (PG: jismoniy joy o`zgardi — test kuchli)' if PG_URL and _xom != sorted(_xom) else ''}")

_s = SessionLocal()
_p = _s.get(Project, _pc)
with sanoq() as _sq:
    _lz = [o.id for o in _p.orders]
check("C1 lazy Project.orders — id tartibida", _lz == sorted(_lz) and len(_lz) == 4, _lz)
check("C2 lazy SQL da ORDER BY orders.id", any("ORDER BY orders.id" in q for q in _sq["sql"]), _sq["sql"][-1:])
_o0 = _s.get(Order, C_ORD[0])
_li = [it.id for it in _o0.items]
_lp = [p.id for p in _o0.payments]
_ld = [d.id for d in _o0.items[0].deliveries]
check("C3 lazy Order.items / payments / OrderItem.deliveries — id tartibida",
      _li == sorted(_li) and _lp == sorted(_lp) and len(_li) == 2 and len(_lp) == 2
      and _ld == sorted(d.id for d in _s.query(DeliveryItem).filter(DeliveryItem.order_item_id == _li[0]).all())
      and len(_ld) >= 2,
      (_li, _lp, _ld, [(d.id, d.order_item_id, d.quantity, d.delivery_id) for d in
                       _s.query(DeliveryItem).filter(DeliveryItem.order_item_id.in_(_li)).all()]))
_s.close()
_s = SessionLocal()
_ps = _s.query(Project).filter(Project.id == _pc).options(_orm.selectinload(Project.orders).selectinload(
    Order.items).selectinload(OrderItem.deliveries), _orm.selectinload(Project.orders).selectinload(Order.payments)).one()
_so_ = [o.id for o in _ps.orders]
_oo = next(o for o in _ps.orders if o.id == C_ORD[0])
check("C4 selectinload ro'yxatlari lazy bilan AYNAN (tartib ham)",
      _so_ == _lz and [it.id for it in _oo.items] == _li and [p.id for p in _oo.payments] == _lp
      and [d.id for d in _oo.items[0].deliveries] == _ld, (_so_, _lz))
_s.close()
_s = SessionLocal()
_pr = next(x for x in crud.get_projects_with_stats(_s, company_id=1) if x.id == _pc)
check("C5 get_projects_with_stats: loyiha ro'yxati id tartibida, soni 4", [o.id for o in _pr.orders] == sorted(C_ORD)
      and _pr.orders_count == 4, [o.id for o in _pr.orders])
_s.close()

# ── D. begona korxona ──────────────────────────────────────────────────────────────────────────────────────
section("D begona korxona")
_rb = js(req(CB, "get", "/api/orders")) or []
check("D1 B ning /api/orders — faqat B buyurtmalari", sorted(o["id"] for o in _rb) == sorted([O_B1, O_B2]),
      [o.get("id") for o in _rb])
_hb = req(CB, "get", "/debts").text
_s = SessionLocal()
_a_nomer = [o.order_number for o in _s.query(Order).filter(Order.company_id == 1).all()]
_s.close()
check("D2 B ning Qarzdorlar sahifasida A buyurtmasi yo'q", not any(n and n in _hb for n in _a_nomer))
_ds_b = js(req(CB, "get", "/api/dashboard/debts")) or {}
check("D3 B qarz statistikasi — faqat B", all(d["order_id"] in (O_B1, O_B2) for d in _ds_b.get("debt_orders", [])),
      _ds_b)

# ── X. 5xx ──────────────────────────────────────────────────────────────────────────────────────────────────
section("X 5xx")
_5 = [h for h in HOLATLAR if h[1] >= 500]
check("X1 hech bir so'rov 5xx emas", not _5, _5[:5])

# ── S. statik ───────────────────────────────────────────────────────────────────────────────────────────────
section("S statik")
_rel = {
    "Project.orders": (Project.orders, "Order.id"), "Order.items": (Order.items, "OrderItem.id"),
    "Order.returns": (Order.returns, "ReturnItem.id"), "Order.payments": (Order.payments, "Payment.id"),
    "Order.gips_additives": (Order.gips_additives, "OrderGipsAdditive.id"),
    "OrderItem.deliveries": (OrderItem.deliveries, "DeliveryItem.id"),
}
for i, (nom, (attr, kut)) in enumerate(_rel.items(), 1):
    ob = attr.property.order_by
    check(f"S{i} {nom}: order_by = {kut}",
          bool(ob) and len(ob) == 1 and f"{ob[0].table.name}.{ob[0].name}" == {
              "Order.id": "orders.id", "OrderItem.id": "order_items.id", "ReturnItem.id": "return_items.id",
              "Payment.id": "payments.id", "OrderGipsAdditive.id": "order_gips_additives.id",
              "DeliveryItem.id": "delivery_items.id"}[kut], ob)


def _src(f):
    try:
        return inspect.getsource(f)
    except Exception:                  # noqa: BLE001
        return ""


_fc_src = _src(crud.check_financial_consistency)
check("S10 izchillik: buyurtma / detal boshiga alohida so'rov YO'Q",
      "db.query(OrderItem).filter(OrderItem.order_id == o.id)" not in _fc_src
      and "db.query(Payment).filter(Payment.order_id == o.id)" not in _fc_src
      and "db.query(DeliveryItem)" not in _fc_src
      and "items = list(o.items or [])" in _fc_src and "pays = list(o.payments or [])" in _fc_src
      and "(it.deliveries or [])" in _fc_src)
check("S11 Buyurtmalar sahifasi royxat_uchun=True bilan",
      "royxat_uchun=True)" in _src(main.orders_page) and "if royxat_uchun:" in _src(crud.get_orders_for_main_page))
check("S12 Qaytarishlar sahifasi — ro'yxatlar yuklanmaydi (standart False)", "royxat_uchun" not in _src(main.returns_page)
      and inspect.signature(crud.get_orders_for_main_page).parameters.get("royxat_uchun") is not None
      and inspect.signature(crud.get_orders_for_main_page).parameters["royxat_uchun"].default is False)
_opt = [
    ("S13 get_orders", crud.get_orders, ("Order.items).selectinload(OrderItem.sub_details)", "Order.payments)",
                                         "Order.gips_additives)")),
    ("S14 get_orders_for_main_page", crud.get_orders_for_main_page,
     ("Order.items).selectinload(OrderItem.deliveries)", "Order.returns)", "Order.payments)")),
    ("S15 get_delivery_stats", crud.get_delivery_stats,
     ("Order.items).selectinload(OrderItem.deliveries)", "Order.returns)", "Order.payments)", "Order.project)")),
    ("S16 get_debt_stats", crud.get_debt_stats, ("Order.payments)", "Order.project)")),
    ("S17 get_business_alerts", services.get_business_alerts, ("Order.payments)",)),
    ("S18 get_business_health", services.get_business_health, ("Order.payments)",)),
    ("S19 get_full_debt_summary", services.get_full_debt_summary, ("Order.payments)",)),
    ("S20 get_chart_data", services.get_chart_data, ("Order.items)",)),
    ("S21 get_projects_with_stats", crud.get_projects_with_stats, ("Project.orders)",)),
    ("S22 get_projects_dashboard_stats", crud.get_projects_dashboard_stats, ("Project.orders)",)),
    ("S23 debts_page", main.debts_page, ("Order.payments)", "Order.project)")),
]
for nom, f, qism in _opt:
    s = _src(f)
    check(f"{nom}: oldindan yuklash ({len(qism)} ro'yxat)", all(q in s for q in qism), [q for q in qism if q not in s])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
