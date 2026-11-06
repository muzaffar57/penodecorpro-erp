#!/usr/bin/env python3
"""
test_joriy266.py — kech202 (zip 266): review265 PAST-1 — o'z `company_id` ustuni YO'Q modellar (Payment, OrderAttachment, DeliveryItem,
EmployeeAdvance … — 17 ta) ORM qo'riqchisida so'rovning JORIY korxonasi bilan solishtiriladi; `DeliveryItem` korxonasi `Delivery → Order`
zanjiri bilan aniqlanadi.

NIMA UCHUN KERAK (zip 265 gacha — O'LCHANDI review265 `probes/probe_guard_gap.py` da, asl kodda shu testning A bandlari yiqiladi):
  B korxonasining so'rovi (sessiyada joriy korxona = 2) ichida A korxonasi buyurtmasiga `Payment` / `OrderAttachment` yozilsa — qo'riqchi
  otaning korxonasini oddiygina yozuvning korxonasi deb olardi va YOZARDI (yo'q buyurtma esa — 404): ham korxonalararo yozuv, ham mavjudlik
  farqi. `DeliveryItem` da ota (`Delivery`) o'zi `company_id` siz bo'lgani uchun korxona umuman aniqlanmasdi va `order_item_id` havolasi
  TEKSHIRILMASDI (begona detal — yoziladi, yo'q detal — PG da 500). HTTP marshrutlar otani oldindan korxona bo'yicha qidirgani uchun bu
  hozir tashqaridan yopiq edi — bu test ORM qatlamidagi ikkinchi to'siqni tekshiradi.
BO'LIMLAR: A — B kontekstida begona ota / havola — rad (yo'q id bilan BIR XIL sinf); B — o'z korxonasi, kontekstsiz (cron / tizim),
           `system_context` — ishlaydi; C — o'zgartirilgan yozuv (otani begona korxonaga ko'chirish); D — HTTP: to'lov va yetkazish
           marshrutlari o'z korxonasida ishlaydi, begona buyurtmaga — 404.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (3ff5445 — zip 265) qarshi YIQILADI, QULAMAYDI.
ISHLATISH: python3 tools/test_joriy266.py
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "joriy266_test"
_T = tempfile.mkdtemp(prefix="joriy266_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'joriy266_test.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "ADMIN_PASSWORD", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas                                 # noqa: E402
import tenant_context                              # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (UserRole, Order, OrderItem, Payment, Delivery, DeliveryItem, OrderAttachment, OrderType,   # noqa: E402
                    TenantMismatchError)
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


PAROL = "Kuchli-Sinov-Parol-266"
YOQ = 987654

with TestClient(main.app, base_url="https://testserver") as _c0:
    _c0.get("/login")

s = SessionLocal()
with tenant_context.system_context(s), contextlib.redirect_stdout(_quiet):
    if not s.query(Company).filter(Company.id == 2).first():
        s.add(Company(id=2, name="Joriy B korxona", code="JORIY-B266"))
        s.commit()
    auth.create_user(s, "jr_b_admin", PAROL, UserRole.ADMIN, "B Admin", company_id=2)
    IDS = {}
    for cid, k in ((1, "A"), (2, "B")):
        pid = crud.create_project(s, schemas.ProjectCreate(project_name=f"JR266 {k} loyiha", client_name=f"JR266 {k} mijoz",
                                                           client_phone=f"+99890{cid}266266"), company_id=cid).id
        o = Order(project_id=pid, company_id=cid, order_type=OrderType.PRODUCT, order_number=f"JR266-{k}")
        s.add(o)
        s.flush()
        it = OrderItem(order_id=o.id, company_id=cid, name=f"JR266 {k} detal", category="panel", quantity=5, unit_price=1000,
                       total_price=5000)
        s.add(it)
        s.flush()
        dl = Delivery(order_id=o.id, delivery_number=f"JR266-{k}/Y-1")
        s.add(dl)
        s.flush()
        IDS[k] = (o.id, it.id, dl.id, pid)
    s.commit()
s.close()
OA, IA, DA, PA = IDS["A"]
OB, IB, DB, PB = IDS["B"]


def orm(fn, korxona=2, tizim=False):
    d = SessionLocal()
    try:
        if korxona is not None:
            tenant_context.set_current_company(d, korxona)
        if tizim:
            with tenant_context.system_context(d):
                fn(d)
                d.commit()
        else:
            fn(d)
            d.commit()
        return "OK"
    except TenantMismatchError as e:
        d.rollback()
        return "RAD:" + str(e)
    except Exception as e:                 # noqa: BLE001
        d.rollback()
        return f"BOSHQA:{type(e).__name__}"
    finally:
        d.close()


def sanoq(model, **f):
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            q = d.query(model)
            for k, v in f.items():
                q = q.filter(getattr(model, k) == v)
            return q.count()
    finally:
        d.close()


# ═══════════════════════════════════════════════════════════════════════════════════════════════
section("A — B korxonasi so'rovida begona ota / havola")
_n0 = sanoq(Payment, order_id=OA)
_r = orm(lambda d: d.add(Payment(order_id=OA, amount=1)))
check("A1 Payment(begona A buyurtmasi) B so'rovida — rad (TenantMismatchError)", _r.startswith("RAD:"), _r)
check("A2 A buyurtmasiga to'lov yozilmadi", sanoq(Payment, order_id=OA) == _n0)
_ry = orm(lambda d: d.add(Payment(order_id=YOQ, amount=1)))
check("A3 Payment(yo'q buyurtma) — xuddi shu sinf bilan rad (bir xil javob)", _ry.startswith("RAD:"), _ry)
_r = orm(lambda d: d.add(OrderAttachment(order_id=OA, file_url="/static/uploads/x.png", file_name="x.png")))
check("A4 OrderAttachment(begona buyurtma) — rad", _r.startswith("RAD:"), _r)
_r = orm(lambda d: d.add(DeliveryItem(delivery_id=DB, order_item_id=IA, quantity=1)))
check("A5 DeliveryItem(o'z yetkazishi, begona detal) — rad (korxona Delivery → Order zanjiridan)", _r.startswith("RAD:"), _r)
_r = orm(lambda d: d.add(DeliveryItem(delivery_id=DB, order_item_id=YOQ, quantity=1)))
check("A6 DeliveryItem(o'z yetkazishi, yo'q detal) — rad (avval PG da 500)", _r.startswith("RAD:"), _r)
_r = orm(lambda d: d.add(DeliveryItem(delivery_id=DA, order_item_id=IA, quantity=1)))
check("A7 DeliveryItem(begona yetkazish, begona detal) B so'rovida — rad", _r.startswith("RAD:"), _r)

# ═══════════════════════════════════════════════════════════════════════════════════════════════
section("B — o'z korxonasi, kontekstsiz, tizim konteksti")
check("B1 Payment(o'z buyurtmasi) B so'rovida — yoziladi", orm(lambda d: d.add(Payment(order_id=OB, amount=1))) == "OK")
check("B2 DeliveryItem(o'z yetkazishi, o'z detali) — yoziladi",
      orm(lambda d: d.add(DeliveryItem(delivery_id=DB, order_item_id=IB, quantity=1))) == "OK")
check("B3 OrderAttachment(o'z buyurtmasi) — yoziladi",
      orm(lambda d: d.add(OrderAttachment(order_id=OB, file_url="/static/uploads/y.png", file_name="y.png"))) == "OK")
check("B4 joriy korxonasiz sessiya (cron / fon vazifasi) — A buyurtmasiga to'lov yoziladi (eski xulq, otaning korxonasi)",
      orm(lambda d: d.add(Payment(order_id=OA, amount=2)), korxona=None) == "OK")
check("B5 `system_context` ichida (joriy korxona vaqtincha olinadi) — yoziladi",
      orm(lambda d: d.add(Payment(order_id=OA, amount=3)), korxona=2, tizim=True) == "OK")
check("B6 o'z company_id si bor model (OrderItem) — joriy korxona bilan solishtirilmaydi (platforma egasi aniq company_id bilan)",
      orm(lambda d: d.add(OrderItem(order_id=OA, company_id=1, name="JR266 platforma", category="panel", quantity=1)),
          korxona=2) == "OK")

# ═══════════════════════════════════════════════════════════════════════════════════════════════
section("C — o'zgartirilgan yozuv")


def _kochir(order_id):
    def f(d):
        p = d.query(Payment).filter(Payment.order_id == OB).order_by(Payment.id).first()
        p.order_id = order_id
    return f


_r = orm(_kochir(OA))
check("C1 o'z to'lovini begona buyurtmaga ko'chirish — rad", _r.startswith("RAD:"), _r)
check("C2 to'lov o'z buyurtmasida qoldi", sanoq(Payment, order_id=OB) >= 1)


def _summa(d):
    p = d.query(Payment).filter(Payment.order_id == OB).order_by(Payment.id).first()
    p.amount = 7


check("C3 o'z to'lovining boshqa maydonini o'zgartirish — yoziladi", orm(_summa) == "OK")

# ═══════════════════════════════════════════════════════════════════════════════════════════════
section("D — HTTP (oddiy ish buzilmagan, begona — 404)")
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False, client=("203.0.113.66", 50000))
_rl = CB.post("/login", data={"username": "jr_b_admin", "password": PAROL}, follow_redirects=False)
check("D0 B admini kirdi", _rl.status_code in (302, 303), _rl.status_code)
r = CB.post("/api/payments", json={"order_id": OB, "amount": 1000, "confirm_overpay": True})
check("D1 o'z buyurtmasiga to'lov (HTTP) — 200", r.status_code == 200, (r.status_code, r.text[:300]))
r2 = CB.post("/api/payments", json={"order_id": OA, "amount": 1000})
r3 = CB.post("/api/payments", json={"order_id": YOQ, "amount": 1000})
check("D2 begona ↔ yo'q buyurtmaga to'lov — bir xil status (404) va tana", r2.status_code == r3.status_code == 404
      and js(r2) == js(r3), (r2.status_code, r2.text[:200], r3.status_code, r3.text[:200]))

print(f"\nNATIJA: {OK} / {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(1 if FAIL else 0)
