#!/usr/bin/env python3
"""
test_tana_qatiy.py — kech93 darvozasi (2026-09-27, 8-band + K93-1 + K93-2): tanasi ilgari QAT'IY
tekshirilmagan marshrutlar — foydalanuvchi, parol, usta KPI, sovg'a davri, material narxi / min qoldig'i,
ishlab chiqarish (mahsulot turi, retsept, ishlab chiqarish buyurtmasi).

O'LCHANGAN (asl kod = zip 86, `work/probe8.py`, `work/probe8b.py`, `work/probe8c.py`; SQLite va HAQIQIY
PostgreSQL 16):
  * `POST /api/users`: kalit yo'q / `true` / son / NaN → 500; login 51 / ism 101 belgi → PG 500; bo'sh yoki faqat
    bo'shliq / tab login → BO'SH loginli foydalanuvchi; parol 1 belgi → qabul; 72 baytdan uzun parolning oxiri JIM
    tashlanardi (bcrypt: 72 × "A" + "X" bilan yaratilgan foydalanuvchi 72 × "A" + "Y" bilan KIRDI); noma'lum kalit jim;
  * `POST /api/users/{id}/password`: `new_password` `true` / son / ro'yxat / `null` → 500; o'z parolida
    `current_password` son / ro'yxat / `true` → 500; noma'lum kalit jim; 72 baytdan uzun — jim kesish;
  * `PUT /api/masters/{id}/kpi`: `true` → 1.0, "7" → 7.0, noma'lum kalit jim (pydantic "lax");
  * sovg'a: ochish / bosqich — noma'lum kalit jim; usta qo'shish `true` / "1" / 1.0 / 2**31 → PG 500 (SQLite da
    `true` = 1-usta); yopish `{"force": "false"}` / `{"force": 1}` → MAJBURIY yopish (sovg'aga yetgan usta sovg'asiz);
  * material `/price`, `/min-stock`: noma'lum kalit jim, hajm / min qoldiq 1e300 saqlanardi;
  * ishlab chiqarish: noma'lum kalit jim, tanlov maydonlariga ixtiyoriy matn, `true` → 1, "yes" → True, `Infinity`
    retsept partiyasi bazaga, narx 1e20 / `Infinity` / 9 999 999 999.995 → PG 500, bo'shliqli nom → '', qoplama
    koeffitsiyenti / qat'iy narx 0.001 → 0.00, id 2**31 / yo'q material / yo'q buyurtma → PG 500 (SQLite bog'lamsiz
    qator), bo'sh retsept → 0 tannarxli mahsulot;
  * K93-1: "omborga" ishlab chiqarish buyurtmasi BEGONA korxona detaliga bog'lanardi — boshlashda A korxona
    mahsuloti B korxona detaliga BAND qilinardi (B detalining "kerak" miqdori 10 → 8);
  * K93-2: katta miqdorli ishlab chiqarish "Boshlash" dan o'tib, "Yakunlash" da PG 500 (`numeric field overflow`).

Bo'limlar: A — foydalanuvchi; B — parol; C — KPI; D — sovg'a; E — material narxi / min qoldiq; F — mahsulot turi;
G — retsept; J — ishlab chiqarish buyurtmasi + K93-1; K — K93-2 (tannarx sig'imi); S — sxemalar (ikkinchi to'siq)
va crud ildizi; U — UI (HAQIQIY shablon funksiyalari node da, yuborgan tanalari serverga); X — 500 yo'q; H — statik.

Ishlatish:
    python3 tools/test_tana_qatiy.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tana_qatiy.py
"""
import os
import sys
import json
import inspect
import tempfile
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tana_qatiy_test"
_T = tempfile.mkdtemp(prefix="tana_qatiy_")
_DB = os.path.join(_T, "tana_qatiy_test.db")

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

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas as SC                           # noqa: E402
    import production_schemas as PS                # noqa: E402
    import production_service as PSV               # noqa: E402
    import production_routes as PR                 # noqa: E402

from sqlalchemy import func                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, User, Master, Inventory, InventoryMovement, Project, Order, OrderItem, OrderType, OrderStatus,
    GiftPeriod, GiftPeriodTier, GiftPeriodParticipant, FinishedProduct,
)
from production_models import (                    # noqa: E402
    Company, ProductType, BOM, BOMItem, ProductionOrder,
    InputTemplate, PricingFormula, BOMComponentType, ProductionSourceType,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HOLATLAR = []            # X bo'limi: har HTTP javob holati (500 bo'lmasin)


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
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    HOLATLAR.append((metod.upper() + " " + url.split("?")[0], r.status_code))
    return r


def xom(c, metod, url, matn):
    """Xom JSON matni (NaN / Infinity / null uchun)."""
    return req(c, metod, url, content=matn, headers={"Content-Type": "application/json"})


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def detail(r):
    d = js(r)
    return d.get("detail") if isinstance(d, dict) else None


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


def sanoq(model, *shart):
    s = SessionLocal()
    try:
        q = s.query(func.count(model.id))
        for sh in shart:
            q = q.filter(sh)
        return q.scalar()
    finally:
        s.close()


def rad400(label, r, h0, h1, matnmi=True):
    """400, `detail` MATN (UI to'g'ridan-to'g'ri ko'rsatadi) va holat o'zgarmagan."""
    d = detail(r)
    check(label, r.status_code == 400 and (isinstance(d, str) or not matnmi) and h0 == h1,
          f"{r.status_code} {str(d)[:160]} | {h0} -> {h1}")


# ════════════════════════════════════════════════════════════════
# FIKSTURA
# ════════════════════════════════════════════════════════════════
PAROL = "Parol123!"
db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "TQ_admin", PAROL, UserRole.ADMIN, "TQ Admin", company_id=1)
BCID = int(db.query(func.max(Company.id)).scalar() or 0) + 1
db.add(Company(id=BCID, name="TQ Begona"))
db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "TQ_badmin", PAROL, UserRole.ADMIN, "TQ B Admin", company_id=BCID)
    auth.create_user(db, "TQ_boshqa", PAROL, UserRole.MANAGER, "Boshqa", company_id=1)
    auth.create_user(db, "TQ_b_user", PAROL, UserRole.MANAGER, "B user", company_id=BCID)
M1 = Master(company_id=1, name="TQ Usta1", phone="+998900000101", is_active=True, kpi_percent=5)
M2 = Master(company_id=1, name="TQ Usta2", phone="+998900000102", is_active=True, kpi_percent=5)
INV = Inventory(company_id=1, item_name="TQ Akril", unit="kg", stock_quantity=1000, price_per_unit=100)
INV2 = Inventory(company_id=1, item_name="TQ Loy", unit="kg", stock_quantity=1000, price_per_unit=50)
INVB = Inventory(company_id=BCID, item_name="TQ B material", unit="kg", stock_quantity=5, price_per_unit=7)
db.add_all([M1, M2, INV, INV2, INVB])
db.commit()
PRA = Project(company_id=1, client_name="A mijoz", project_name="A loyiha")
PRB = Project(company_id=BCID, client_name="B mijoz", project_name="B loyiha")
db.add_all([PRA, PRB])
db.commit()
PRAID = PRA.id
ORA = Order(company_id=1, project_id=PRA.id, order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS,
            order_number="TQ-A1", total_amount=1000, agreed_amount=1000)
ORA2 = Order(company_id=1, project_id=PRA.id, order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS,
             order_number="TQ-A2", total_amount=1000, agreed_amount=1000)
ORB = Order(company_id=BCID, project_id=PRB.id, order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS,
            order_number="TQ-B1", total_amount=1000, agreed_amount=1000)
db.add_all([ORA, ORA2, ORB])
db.commit()
MID, M2ID, INVID, INV2ID, INVBID = M1.id, M2.id, INV.id, INV2.id, INVB.id
ORAID, ORA2ID, ORBID = ORA.id, ORA2.id, ORB.id
ADMIN_ID = db.query(User).filter(User.username == "TQ_admin").first().id
BOSHQA_ID = db.query(User).filter(User.username == "TQ_boshqa").first().id
B_USER_ID = db.query(User).filter(User.username == "TQ_b_user").first().id
db.close()


def klient(u, p=PAROL):
    k = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = k.post("/login", data={"username": u, "password": p}, follow_redirects=False)
    return k, r.status_code


C, _st = klient("TQ_admin")
CB, _stb = klient("TQ_badmin")
check("fikstura: A va B adminlari tizimga kirdi", _st == 302 and _stb == 302, f"{_st} {_stb}")

# Nazorat mahsulot turi va retsept (API orqali — production.html shaklida)
_r = req(C, "post", "/api/production/product-types",
         json={"name": "TQ tur", "unit": "kg", "input_template": "quantity_only", "pricing_formula": "unit_based",
               "fixed_unit_price": None, "supports_coating": False, "coating_price_multiplier": None, "notes": None})
PTID = (js(_r) or {}).get("id")
_r = req(C, "post", "/api/production/boms",
         json={"product_type_id": PTID, "variant_name": "Standart", "batch_quantity": 1, "notes": None,
               "items": [{"inventory_id": INVID, "component_type": "raw_material", "quantity": 1, "scrap_factor_percent": 0,
                          "is_optional": False, "is_coating": False, "fixed_cost_per_unit": None, "percentage_cost": None},
                         {"inventory_id": INV2ID, "component_type": "raw_material", "quantity": 0.5, "scrap_factor_percent": 0,
                          "is_optional": True, "is_coating": True, "fixed_cost_per_unit": None, "percentage_cost": None}]})
BOMID = (js(_r) or {}).get("id")
check("fikstura: nazorat mahsulot turi va retsept yaratildi (200)", bool(PTID) and bool(BOMID), _r.text[:200])
db = SessionLocal()
_opt = db.query(BOMItem).filter(BOMItem.bom_id == BOMID, BOMItem.is_optional == True).first() if BOMID else None  # noqa: E712
OPTID = _opt.id if _opt else None
db.execute(OrderItem.__table__.insert().values(company_id=1, order_id=ORAID, name="TQ A MRP detal", quantity=10,
                                               product_type_id=PTID, unit_price=100, total_price=1000))
db.execute(OrderItem.__table__.insert().values(company_id=1, order_id=ORA2ID, name="TQ A2 MRP detal", quantity=10,
                                               product_type_id=PTID, unit_price=100, total_price=1000))
db.execute(OrderItem.__table__.insert().values(company_id=BCID, order_id=ORBID, name="TQ B detal", quantity=10,
                                               product_type_id=None, unit_price=100, total_price=1000))
db.commit()
OIA = db.query(OrderItem).filter(OrderItem.name == "TQ A MRP detal").first().id
OIA2 = db.query(OrderItem).filter(OrderItem.name == "TQ A2 MRP detal").first().id
OIB = db.query(OrderItem).filter(OrderItem.name == "TQ B detal").first().id
db.close()


def user_bor(nom):
    s = SessionLocal()
    try:
        u = s.query(User).filter(User.username == nom).first()
        return None if u is None else (u.username, u.full_name, getattr(u.role, "value", u.role))
    finally:
        s.close()


def xesh(uid):
    s = SessionLocal()
    try:
        u = s.get(User, uid)
        return u.password_hash if u else None
    finally:
        s.close()


def userlar():
    return sanoq(User)


# ════════════════════════════════════════════════════════════════
section("A. Foydalanuvchi yaratish — POST /api/users")
# ════════════════════════════════════════════════════════════════
r = req(C, "post", "/api/users", json={"username": "tq_u1", "password": PAROL, "role": "manager", "full_name": "Ali Vali"})
check("A1 NAZORAT (users.html tanasi) → 200, saqlangan", r.status_code == 200 and user_bor("tq_u1") == ("tq_u1", "Ali Vali", "manager"),
      f"{r.status_code} {r.text[:120]} {user_bor('tq_u1')}")
_rad = [
    ("A2 username kalit yo'q", {"password": PAROL}),
    ("A2 password kalit yo'q", {"username": "tq_a2b"}),
    ("A2 noma'lum kalit (is_platform_admin, company_id)", {"username": "tq_a2c", "password": PAROL, "is_platform_admin": True,
                                                          "company_id": BCID}),
    ("A2 username true", {"username": True, "password": PAROL}),
    ("A2 username son 12345", {"username": 12345, "password": PAROL}),
    ("A2 username '' (bo'sh)", {"username": "", "password": PAROL}),
    ("A2 username faqat tab / newline", {"username": "\t\n ", "password": PAROL}),
    ("A2 username 51 belgi", {"username": "u" * 51, "password": PAROL}),
    ("A2 full_name 101 belgi", {"username": "tq_a2d", "password": PAROL, "full_name": "f" * 101}),
    ("A2 full_name son", {"username": "tq_a2e", "password": PAROL, "full_name": 5}),
    ("A2 parol 5 belgi", {"username": "tq_a2f", "password": "12345"}),
    ("A2 parol 1 belgi", {"username": "tq_a2g", "password": "1"}),
    ("A2 parol true", {"username": "tq_a2h", "password": True}),
    ("A2 parol faqat bo'shliq (6)", {"username": "tq_a2i", "password": "      "}),
    ("A2 parol 73 belgi (lotin, 73 bayt)", {"username": "tq_a2j", "password": "A" * 72 + "X"}),
    ("A2 parol 37 kirill harf (74 bayt)", {"username": "tq_a2k", "password": "Ж" * 37}),
    ("A2 rol true", {"username": "tq_a2l", "password": PAROL, "role": True}),
    ("A2 rol 'MANAGER' (enum nomi)", {"username": "tq_a2m", "password": PAROL, "role": "MANAGER"}),
    ("A2 rol null", {"username": "tq_a2n", "password": PAROL, "role": None}),
    ("A2 rol 'superadmin'", {"username": "tq_a2o", "password": PAROL, "role": "superadmin"}),
]
for lbl, tana in _rad:
    h0 = userlar()
    r = req(C, "post", "/api/users", json=tana)
    rad400(f"{lbl} → 400 (matn), foydalanuvchi yaratilmadi", r, h0, userlar())
h0 = userlar()
r = xom(C, "post", "/api/users", '{"username": NaN, "password": "Parol123!"}')
check("A2 username NaN (xom) → 400 / 422, yaratilmadi", r.status_code in (400, 422) and userlar() == h0, f"{r.status_code} {r.text[:120]}")
d = detail(req(C, "post", "/api/users", json={"username": "tq_a2p", "password": "12345"}))
check("A3 qisqa parol xabari — 'Parol kamida 6 belgi' (almashtirish bilan bir xil)", d == "Parol kamida 6 belgi", d)
d = detail(req(C, "post", "/api/users", json={"username": "tq_a2q", "password": "Ж" * 37}))
check("A3 uzun parol xabari — 72 bayt va kirill 36 belgi aytiladi", isinstance(d, str) and "72" in d and "36" in d, d)
# Chegaralar — qabul
r = req(C, "post", "/api/users", json={"username": "v" * 50, "password": PAROL})
check("A4 username 50 belgi (chegara) → 200", r.status_code == 200 and user_bor("v" * 50) is not None, f"{r.status_code} {r.text[:100]}")
r = req(C, "post", "/api/users", json={"username": "tq_a4b", "password": PAROL, "full_name": "f" * 100})
check("A4 full_name 100 belgi (chegara) → 200", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
P72 = "A" * 72
r = req(C, "post", "/api/users", json={"username": "tq_a4c", "password": P72})
_, _l1 = klient("tq_a4c", P72)
check("A4 parol 72 bayt (lotin) → 200 va aynan shu parol bilan kiradi", r.status_code == 200 and _l1 == 302, f"{r.status_code} {_l1}")
P36 = "Ж" * 36
r = req(C, "post", "/api/users", json={"username": "tq_a4d", "password": P36})
_, _l2 = klient("tq_a4d", P36)
check("A4 parol 36 kirill harf (72 bayt) → 200 va kiradi", r.status_code == 200 and _l2 == 302, f"{r.status_code} {_l2}")
r = req(C, "post", "/api/users", json={"username": "tq_a4e", "password": "123456"})
check("A4 parol 6 belgi (eng kami) → 200", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
r = req(C, "post", "/api/users", json={"username": "  tq_a4f  ", "password": PAROL})
_, _l3 = klient("tq_a4f")
check("A4 login chetidagi bo'shliqlar — avvalgidek kesilib saqlanadi va kiradi", r.status_code == 200 and user_bor("tq_a4f") is not None
      and _l3 == 302, f"{r.status_code} {user_bor('tq_a4f')} {_l3}")
r = req(C, "post", "/api/users", json={"username": "tq a4g", "password": PAROL})
check("A4 login ichida bo'shliq — avvalgidek ruxsat", r.status_code == 200 and user_bor("tq a4g") is not None, f"{r.status_code}")
r = req(C, "post", "/api/users", json={"username": "tq_a4h", "password": PAROL})
check("A4 rol berilmagan → 'manager' (avvalgidek)", r.status_code == 200 and (user_bor("tq_a4h") or ("", "", ""))[2] == "manager",
      f"{r.status_code} {user_bor('tq_a4h')}")
r = req(C, "post", "/api/users", json={"username": "tq_a4i", "password": PAROL, "role": "warehouse", "full_name": None})
check("A4 rol 'warehouse', full_name null → 200 (null avvalgidek saqlanadi)", r.status_code == 200
      and user_bor("tq_a4i") == ("tq_a4i", None, "warehouse"), f"{r.status_code} {user_bor('tq_a4i')}")
h0 = userlar()
r = req(C, "post", "/api/users", json={"username": "tq_u1", "password": PAROL})
check("A5 takror login → 400 'Bu username band' (o'zgarmadi)", r.status_code == 400 and detail(r) == "Bu username band"
      and userlar() == h0, f"{r.status_code} {detail(r)}")
h0 = userlar()
r = req(C, "post", "/api/users", json=[1, 2])
check("A5 tana ro'yxat → 422 (FastAPI), yaratilmadi", r.status_code == 422 and userlar() == h0, f"{r.status_code}")
s = SessionLocal()
_bosh = s.query(func.count(User.id)).filter(func.trim(User.username) == "").scalar()
s.close()
check("A6 bazada bo'sh (yoki faqat bo'shliqli) loginli foydalanuvchi YO'Q", _bosh == 0, _bosh)

# ════════════════════════════════════════════════════════════════
section("B. Parolni almashtirish — POST /api/users/{id}/password")
# ════════════════════════════════════════════════════════════════
r = req(C, "post", f"/api/users/{BOSHQA_ID}/password", json={"new_password": "Yangi123!"})
_, _l = klient("TQ_boshqa", "Yangi123!")
check("B1 NAZORAT (boshqa foydalanuvchi, users.html tanasi) → 200 va yangi parol bilan kiradi", r.status_code == 200 and _l == 302,
      f"{r.status_code} {_l}")
for lbl, tana in [("B2 {} (kalit yo'q)", {}), ("B2 new_password true", {"new_password": True}),
                  ("B2 new_password son", {"new_password": 1234567}), ("B2 new_password ro'yxat", {"new_password": [1, 2, 3, 4, 5, 6, 7]}),
                  ("B2 new_password null", {"new_password": None}), ("B2 new_password 5 belgi", {"new_password": "12345"}),
                  ("B2 new_password faqat bo'shliq", {"new_password": "       "}),
                  ("B2 new_password 73 bayt", {"new_password": "B" * 73}),
                  ("B2 new_password 37 kirill (74 bayt)", {"new_password": "Ж" * 37}),
                  ("B2 noma'lum kalit (role)", {"new_password": "Yangi456!", "role": "admin"})]:
    h0 = xesh(BOSHQA_ID)
    r = req(C, "post", f"/api/users/{BOSHQA_ID}/password", json=tana)
    rad400(f"{lbl} → 400 (matn), parol o'zgarmadi", r, h0, xesh(BOSHQA_ID))
d = detail(req(C, "post", f"/api/users/{BOSHQA_ID}/password", json={}))
check("B3 kalit yo'q — xabar avvalgidek 'Parol kamida 6 belgi'", d == "Parol kamida 6 belgi", d)
for lbl, cp in [("son 123", 123), ("ro'yxat", ["a"]), ("true", True)]:
    h0 = xesh(ADMIN_ID)
    r = req(C, "post", f"/api/users/{ADMIN_ID}/password", json={"new_password": "Yangi789!", "current_password": cp})
    rad400(f"B4 o'z paroli: current_password {lbl} → 400 (500 EMAS), parol o'zgarmadi", r, h0, xesh(ADMIN_ID))
h0 = xesh(ADMIN_ID)
r = req(C, "post", f"/api/users/{ADMIN_ID}/password", json={"new_password": "Yangi789!", "current_password": ""})
check("B4 o'z paroli: current_password '' → 400 'Joriy parolni kiriting' (o'zgarmadi)",
      r.status_code == 400 and detail(r) == "Joriy parolni kiriting" and xesh(ADMIN_ID) == h0, f"{r.status_code} {detail(r)}")
r = req(C, "post", f"/api/users/{ADMIN_ID}/password", json={"new_password": "Yangi789!", "current_password": "notogri!"})
check("B4 o'z paroli: noto'g'ri joriy parol → 400 (o'zgarmadi)", r.status_code == 400 and xesh(ADMIN_ID) == h0, f"{r.status_code}")
h0 = xesh(B_USER_ID)
r = req(C, "post", f"/api/users/{B_USER_ID}/password", json={"new_password": "Buzildi123!"})
check("B5 begona korxona foydalanuvchisi (to'g'ri tana) → 404, parol o'zgarmadi", r.status_code == 404 and xesh(B_USER_ID) == h0,
      f"{r.status_code}")
h0 = xesh(B_USER_ID)
r = req(C, "post", f"/api/users/{B_USER_ID}/password", json={"new_password": True})
check("B5 begona korxona foydalanuvchisi (buzuq tana) → 400 yoki 404, o'zgarmadi", r.status_code in (400, 404) and xesh(B_USER_ID) == h0,
      f"{r.status_code}")

# ════════════════════════════════════════════════════════════════
section("C. Usta KPI — PUT /api/masters/{id}/kpi")
# ════════════════════════════════════════════════════════════════


def kpi(mid=MID):
    s = SessionLocal()
    try:
        return s.get(Master, mid).kpi_percent
    finally:
        s.close()


r = req(C, "put", f"/api/masters/{MID}/kpi", json={"kpi_percent": 7.5})
check("C1 NAZORAT 7.5 → 200 va saqlandi", r.status_code == 200 and kpi() == 7.5, f"{r.status_code} {kpi()}")
r = req(C, "put", f"/api/masters/{MID}/kpi", json={"kpi_percent": 0})
check("C1 NAZORAT 0 (kpi.html bo'sh maydon → 0) → 200", r.status_code == 200 and kpi() == 0, f"{r.status_code} {kpi()}")
r = req(C, "put", f"/api/masters/{MID}/kpi", json={"kpi_percent": 100})
check("C1 NAZORAT 100 (chegara) → 200", r.status_code == 200 and kpi() == 100, f"{r.status_code} {kpi()}")
for lbl, tana, raw in [("true", {"kpi_percent": True}, None), ("\"7\" matn", {"kpi_percent": "7"}, None),
                       ("noma'lum kalit (cashback_percent)", {"kpi_percent": 6, "cashback_percent": 99}, None),
                       ("101", {"kpi_percent": 101}, None), ("-1", {"kpi_percent": -1}, None),
                       ("null", {"kpi_percent": None}, None), ("kalit yo'q", {}, None),
                       ("NaN (xom)", None, '{"kpi_percent": NaN}'), ("Infinity (xom)", None, '{"kpi_percent": Infinity}')]:
    h0 = kpi()
    r = xom(C, "put", f"/api/masters/{MID}/kpi", raw) if raw else req(C, "put", f"/api/masters/{MID}/kpi", json=tana)
    check(f"C2 {lbl} → 422 (sxema), KPI o'zgarmadi", r.status_code == 422 and kpi() == h0, f"{r.status_code} {r.text[:120]} {kpi()}")

# ════════════════════════════════════════════════════════════════
section("D. Sovg'a davri")
# ════════════════════════════════════════════════════════════════


def davrlar():
    return sanoq(GiftPeriod)


def faol_davr():
    s = SessionLocal()
    try:
        p = s.query(GiftPeriod).filter(GiftPeriod.company_id == 1, GiftPeriod.is_active == True).first()  # noqa: E712
        return None if p is None else p.id
    finally:
        s.close()


def ishtirokchilar(pid):
    s = SessionLocal()
    try:
        return sorted(x.master_id for x in s.query(GiftPeriodParticipant).filter(GiftPeriodParticipant.period_id == pid).all())
    finally:
        s.close()


def bosqich(tid):
    s = SessionLocal()
    try:
        t = s.get(GiftPeriodTier, tid)
        return None if t is None else (t.gift_name, round(float(t.threshold_amount), 2))
    finally:
        s.close()


h0 = davrlar()
r = req(C, "post", "/api/gift-period/open", json={"tiers": [{"gift_name": "Sovg'a", "threshold_amount": 1000}], "master_ids": [MID],
                                                  "zzz": 1})
rad400("D1 ochish: noma'lum kalit → 400 (matn), davr ochilmadi", r, h0, davrlar())
r = req(C, "post", "/api/gift-period/open", json={"tiers": [{"gift_name": "Sovg'a", "threshold_amount": 1000}], "master_ids": [MID]})
PID = faol_davr()
check("D1 ochish NAZORAT (kpi.html tanasi, tanlangan usta) → 200", r.status_code == 200 and PID is not None
      and ishtirokchilar(PID) == [MID], f"{r.status_code} {r.text[:120]}")
s = SessionLocal()
TID = s.query(GiftPeriodTier).filter(GiftPeriodTier.period_id == PID).first().id if PID else 0
s.close()
h0 = bosqich(TID)
r = req(C, "put", f"/api/gift-period/tier/{TID}", json={"gift_name": "Sovg'a X", "threshold_amount": 2000, "period_id": 99})
rad400("D2 bosqich: noma'lum kalit → 400 (matn), bosqich o'zgarmadi", r, h0, bosqich(TID))
r = req(C, "put", f"/api/gift-period/tier/{TID}", json={"gift_name": "Sovg'a B", "threshold_amount": 1500})
check("D2 bosqich NAZORAT → 200", r.status_code == 200 and bosqich(TID) == ("Sovg'a B", 1500.0), f"{r.status_code} {bosqich(TID)}")
for lbl, tana in [("true", {"master_id": True}), ("\"id\" matn", {"master_id": str(M2ID)}), ("kasr ko'rinishi (N.0)", {"master_id": float(M2ID)}),
                  ("2**31", {"master_id": 2 ** 31}), ("0", {"master_id": 0}), ("-1", {"master_id": -1}), ("kalit yo'q {}", {}),
                  ("null", {"master_id": None}), ("noma'lum kalit", {"master_id": M2ID, "period_id": 1})]:
    h0 = ishtirokchilar(PID)
    r = req(C, "post", "/api/gift-period/add-master", json=tana)
    rad400(f"D3 usta qo'shish: {lbl} → 400 (matn), ishtirokchilar o'zgarmadi", r, h0, ishtirokchilar(PID))
r = req(C, "post", "/api/gift-period/add-master", json={"master_id": M2ID})
check("D3 usta qo'shish NAZORAT → 200 va qo'shildi", r.status_code == 200 and ishtirokchilar(PID) == sorted([MID, M2ID]),
      f"{r.status_code} {ishtirokchilar(PID)}")
# Sovg'aga YETGAN usta (1-usta "Tayyor" buyurtmasi, 5 000 ≥ 1 500) — majburiy bo'lmagan yopish to'xtashi SHART
s = SessionLocal()
_ps = s.get(GiftPeriod, PID)
_boshl = (getattr(_ps, "started_at", None) or datetime.utcnow()) if _ps else datetime.utcnow()
s.add(Order(company_id=1, project_id=PRAID, order_type=OrderType.PRODUCT, status=OrderStatus.READY, order_number="TQ-SOVGA",
            total_amount=5000, agreed_amount=5000, master_id=MID, completed_at=_boshl + timedelta(microseconds=1)))
s.commit()
s.close()
_ov = xavfsiz(crud.get_gift_period_overview, SessionLocal(), company_id=1)
check("D4 fikstura: 1-usta sovg'aga yetgan (pending)", isinstance(_ov, dict) and "TQ Usta1" in (_ov.get("pending_master_names") or []),
      str(_ov)[:200])
for lbl, tana, raw in [("force \"false\" (matn)", {"force": "false"}, None), ("force 1 (son)", {"force": 1}, None),
                       ("force \"true\"", {"force": "true"}, None), ("noma'lum kalit", {"x": 1}, None),
                       ("noma'lum kalit + force false", {"force": False, "x": 1}, None)]:
    r = req(C, "post", "/api/gift-period/close", json=tana)
    check(f"D4 yopish: {lbl} → 400, davr OCHIQ qoldi (majburiy yopilmadi)", r.status_code == 400 and faol_davr() == PID,
          f"{r.status_code} {r.text[:140]} faol={faol_davr()}")
r = req(C, "post", "/api/gift-period/close", json={"force": False})
_d = detail(r)
check("D5 yopish {force: false} (kpi.html birinchi urinish) → 400, sovg'aga yetganlar ro'yxati, davr ochiq",
      r.status_code == 400 and isinstance(_d, dict) and "TQ Usta1" in (_d.get("pending_master_names") or []) and faol_davr() == PID,
      f"{r.status_code} {str(_d)[:160]}")
r = xom(C, "post", "/api/gift-period/close", "null")
check("D5 yopish tana null → oddiy (majburiy EMAS) yopish: 400, davr ochiq", r.status_code == 400 and faol_davr() == PID,
      f"{r.status_code} {r.text[:120]}")
r = req(C, "post", "/api/gift-period/close", json=[1])
check("D5 yopish tana ro'yxat → 422, davr ochiq", r.status_code == 422 and faol_davr() == PID, f"{r.status_code}")
r = req(C, "post", "/api/gift-period/close", json={"force": True})
check("D6 yopish {force: true} (kpi.html tasdiqdan keyin) → 200, davr yopildi", r.status_code == 200 and faol_davr() is None,
      f"{r.status_code} {r.text[:120]}")

# ════════════════════════════════════════════════════════════════
section("E. Material narxi / min qoldig'i")
# ════════════════════════════════════════════════════════════════


def inv(iid=INVID):
    s = SessionLocal()
    try:
        i = s.get(Inventory, iid)
        return (round(float(i.price_per_unit or 0), 2), i.volume_per_unit, i.min_stock, i.stock_quantity)
    finally:
        s.close()


for lbl, url, tana in [("/price noma'lum kalit (stock_quantity)", "price", {"price_per_unit": 150, "stock_quantity": 99999}),
                       ("/price volume 1e300", "price", {"price_per_unit": 150, "volume_per_unit": 1e300}),
                       ("/price volume 1e12 + 1", "price", {"price_per_unit": 150, "volume_per_unit": 1e12 + 1}),
                       ("/min-stock noma'lum kalit (price_per_unit)", "min-stock", {"min_stock": 5, "price_per_unit": 0}),
                       ("/min-stock 1e300", "min-stock", {"min_stock": 1e300}),
                       ("/min-stock 1e12 + 1", "min-stock", {"min_stock": 1e12 + 1})]:
    h0 = inv()
    r = req(C, "post", f"/api/inventory/{INVID}/{url}", json=tana)
    rad400(f"E1 {lbl} → 400 (matn), material o'zgarmadi", r, h0, inv())
r = req(C, "post", f"/api/inventory/{INVID}/price", json={"price_per_unit": 120})
check("E2 /price NAZORAT (inventory.html tanasi) → 200", r.status_code == 200 and inv()[0] == 120.0, f"{r.status_code} {inv()}")
r = req(C, "post", f"/api/inventory/{INVID}/price", json={"price_per_unit": 100, "volume_per_unit": 1e12})
check("E2 /price hajm 1e12 (chegara) → 200", r.status_code == 200 and inv()[1] == 1e12, f"{r.status_code} {inv()}")
r = req(C, "post", f"/api/inventory/{INVID}/min-stock", json={"min_stock": 7.5})
check("E2 /min-stock NAZORAT → 200", r.status_code == 200 and inv()[2] == 7.5, f"{r.status_code} {inv()}")
r = req(C, "post", f"/api/inventory/{INVID}/min-stock", json={"min_stock": 1e12})
check("E2 /min-stock 1e12 (chegara) → 200", r.status_code == 200 and inv()[2] == 1e12, f"{r.status_code} {inv()}")
req(C, "post", f"/api/inventory/{INVID}/min-stock", json={"min_stock": 0})

# ════════════════════════════════════════════════════════════════
section("F. Mahsulot turi — POST /api/production/product-types")
# ════════════════════════════════════════════════════════════════
PT0 = {"name": "TQ f", "unit": "kg", "input_template": "quantity_only", "pricing_formula": "unit_based"}


def turlar():
    return sanoq(ProductType)


def tur(nom):
    s = SessionLocal()
    try:
        p = s.query(ProductType).filter(ProductType.name == nom).first()
        return None if p is None else (p.name, p.unit, p.input_template, p.pricing_formula, p.supports_coating,
                                       None if p.coating_price_multiplier is None else round(float(p.coating_price_multiplier), 2),
                                       None if p.fixed_unit_price is None else round(float(p.fixed_unit_price), 2), p.company_id)
    finally:
        s.close()


_f_rad = [
    ("noma'lum kalit (company_id, is_active)", dict(PT0, name="TQ f1", company_id=BCID, is_active=False), None),
    ("input_template 'qalbaki'", dict(PT0, name="TQ f2", input_template="qalbaki"), None),
    ("pricing_formula 'qalbaki'", dict(PT0, name="TQ f3", pricing_formula="qalbaki"), None),
    ("input_template yo'q", {"name": "TQ f4", "unit": "kg", "pricing_formula": "unit_based"}, None),
    ("fixed_unit_price 1e20", dict(PT0, name="TQ f5", pricing_formula="fixed_price", fixed_unit_price=1e20), None),
    ("fixed_unit_price 9 999 999 999.995", dict(PT0, name="TQ f6", pricing_formula="fixed_price", fixed_unit_price=9999999999.995), None),
    ("fixed_unit_price 0.001", dict(PT0, name="TQ f7", pricing_formula="fixed_price", fixed_unit_price=0.001), None),
    ("fixed_unit_price -1", dict(PT0, name="TQ f8", pricing_formula="fixed_price", fixed_unit_price=-1), None),
    ("fixed_unit_price \"100\"", dict(PT0, name="TQ f9", pricing_formula="fixed_price", fixed_unit_price="100"), None),
    ("fixed_unit_price Infinity (xom)", None, json.dumps(dict(PT0, name="TQ f10")).replace("}", ', "fixed_unit_price": Infinity}')),
    ("supports_coating \"yes\"", dict(PT0, name="TQ f11", supports_coating="yes", coating_price_multiplier=2), None),
    ("supports_coating 1", dict(PT0, name="TQ f12", supports_coating=1, coating_price_multiplier=2), None),
    ("qoplama + koeffitsiyent yo'q", dict(PT0, name="TQ f13", supports_coating=True), None),
    ("koeffitsiyent 0.001", dict(PT0, name="TQ f14", supports_coating=True, coating_price_multiplier=0.001), None),
    ("koeffitsiyent 0.004", dict(PT0, name="TQ f15", supports_coating=True, coating_price_multiplier=0.004), None),
    ("koeffitsiyent 0", dict(PT0, name="TQ f16", supports_coating=True, coating_price_multiplier=0), None),
    ("koeffitsiyent 100.01", dict(PT0, name="TQ f17", supports_coating=True, coating_price_multiplier=100.01), None),
    ("notes 10 001 belgi", dict(PT0, name="TQ f18", notes="n" * 10001), None),
    ("name true", dict(PT0, name=True), None),
    ("name '   ' (bo'shliq)", dict(PT0, name="   "), None),
    ("name 151 belgi", dict(PT0, name="n" * 151), None),
    ("unit '   '", dict(PT0, name="TQ f19", unit="   "), None),
    ("unit 21 belgi", dict(PT0, name="TQ f20", unit="u" * 21), None),
    ("unit yo'q", {"name": "TQ f21", "input_template": "quantity_only", "pricing_formula": "unit_based"}, None),
]
for lbl, tana, raw in _f_rad:
    h0 = turlar()
    r = xom(C, "post", "/api/production/product-types", raw) if raw else req(C, "post", "/api/production/product-types", json=tana)
    rad400(f"F1 {lbl} → 400 (matn), tur yaratilmadi", r, h0, turlar())
d = detail(req(C, "post", "/api/production/product-types", json=dict(PT0, name="TQ f22", supports_coating=True)))
check("F2 qoplama koeffitsiyentsiz — o'qiladigan xabar (sxema 422 ro'yxati EMAS)",
      isinstance(d, str) and "koeffitsiyent" in d, d)
r = req(C, "post", "/api/production/product-types", json=dict(PT0, name="TQ f23", supports_coating=True, coating_price_multiplier=99.999))
check("F3 koeffitsiyent 99.999 → 200, bazada 100.00", r.status_code == 200 and (tur("TQ f23") or [None] * 6)[5] == 100.0,
      f"{r.status_code} {tur('TQ f23')}")
r = req(C, "post", "/api/production/product-types", json=dict(PT0, name="TQ f24", pricing_formula="fixed_price", fixed_unit_price=0))
check("F3 qat'iy narx 0 → 200 (0 — ruxsat)", r.status_code == 200 and (tur("TQ f24") or [None] * 7)[6] == 0.0, f"{r.status_code} {tur('TQ f24')}")
r = req(C, "post", "/api/production/product-types", json=dict(PT0, name="TQ f25", pricing_formula="fixed_price", fixed_unit_price=0.01))
check("F3 qat'iy narx 0.01 → 200", r.status_code == 200 and (tur("TQ f25") or [None] * 7)[6] == 0.01, f"{r.status_code} {tur('TQ f25')}")
r = req(C, "post", "/api/production/product-types", json=dict(PT0, name="  TQ f26  ", input_template=" area_2d "))
check("F3 nom chetidagi bo'shliq kesiladi, tanlov kanonik (' area_2d ' → 'area_2d')",
      r.status_code == 200 and (tur("TQ f26") or [None] * 3)[2] == "area_2d", f"{r.status_code} {tur('TQ f26')}")
for _it in InputTemplate:
    r = req(C, "post", "/api/production/product-types", json=dict(PT0, name=f"TQ it {_it.value}", input_template=_it.value))
    check(f"F4 input_template '{_it.value}' → 200", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
for _pf in PricingFormula:
    r = req(C, "post", "/api/production/product-types", json=dict(PT0, name=f"TQ pf {_pf.value}", pricing_formula=_pf.value))
    check(f"F4 pricing_formula '{_pf.value}' → 200", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
h0 = turlar()
r = req(C, "post", "/api/production/product-types", json=dict(PT0, name="TQ tur"))
check("F5 takror nom → 400 (avvalgidek)", r.status_code == 400 and turlar() == h0, f"{r.status_code} {detail(r)}")

# ════════════════════════════════════════════════════════════════
section("G. Retsept — POST / PUT /api/production/boms")
# ════════════════════════════════════════════════════════════════
IT0 = {"inventory_id": INVID, "quantity": 1}
BOM0 = {"product_type_id": PTID, "batch_quantity": 1, "items": [dict(IT0)]}


def retseptlar():
    return (sanoq(BOM), sanoq(BOMItem))


def retsept(bid):
    s = SessionLocal()
    try:
        b = s.get(BOM, bid)
        if b is None:
            return None
        its = s.query(BOMItem).filter(BOMItem.bom_id == bid).order_by(BOMItem.id).all()
        return (b.variant_name, b.batch_quantity, b.notes, [(i.inventory_id, i.component_type, i.quantity, i.is_optional) for i in its])
    finally:
        s.close()


_g_rad = [
    ("noma'lum kalit (company_id)", dict(BOM0, variant_name="g1", company_id=BCID), None),
    ("items [] (bo'sh retsept)", dict(BOM0, variant_name="g2", items=[]), None),
    ("items yo'q", {"product_type_id": PTID, "variant_name": "g3", "batch_quantity": 1}, None),
    ("items ro'yxat emas", dict(BOM0, variant_name="g4", items={"inventory_id": INVID}), None),
    ("qator: quantity true", dict(BOM0, variant_name="g5", items=[dict(IT0, quantity=True)]), None),
    ("qator: quantity \"5\"", dict(BOM0, variant_name="g6", items=[dict(IT0, quantity="5")]), None),
    ("qator: quantity 0", dict(BOM0, variant_name="g7", items=[dict(IT0, quantity=0)]), None),
    ("qator: quantity 1e12 + 1", dict(BOM0, variant_name="g8", items=[dict(IT0, quantity=1e12 + 1)]), None),
    ("qator: inventory_id 2**31", dict(BOM0, variant_name="g9", items=[dict(IT0, inventory_id=2 ** 31)]), None),
    ("qator: inventory_id true", dict(BOM0, variant_name="g10", items=[dict(IT0, inventory_id=True)]), None),
    ("qator: YO'Q material (999999)", dict(BOM0, variant_name="g11", items=[dict(IT0, inventory_id=999999)]), None),
    ("qator: BEGONA korxona materiali", dict(BOM0, variant_name="g12", items=[dict(IT0, inventory_id=INVBID)]), None),
    ("qator: component_type 'qalbaki'", dict(BOM0, variant_name="g13", items=[dict(IT0, component_type="qalbaki")]), None),
    ("qator: scrap 101", dict(BOM0, variant_name="g14", items=[dict(IT0, scrap_factor_percent=101)]), None),
    ("qator: scrap null", dict(BOM0, variant_name="g15", items=[dict(IT0, scrap_factor_percent=None)]), None),
    ("qator: fixed_cost 0.001", dict(BOM0, variant_name="g16", items=[dict(IT0, fixed_cost_per_unit=0.001)]), None),
    ("qator: fixed_cost 1e20", dict(BOM0, variant_name="g17", items=[dict(IT0, fixed_cost_per_unit=1e20)]), None),
    ("qator: percentage 1001", dict(BOM0, variant_name="g18", items=[dict(IT0, percentage_cost=1001)]), None),
    ("qator: is_optional \"yes\"", dict(BOM0, variant_name="g19", items=[dict(IT0, is_optional="yes")]), None),
    ("qator: noma'lum kalit", dict(BOM0, variant_name="g20", items=[dict(IT0, bom_id=1)]), None),
    ("batch_quantity true", dict(BOM0, variant_name="g21", batch_quantity=True), None),
    ("batch_quantity 1e12 + 1", dict(BOM0, variant_name="g22", batch_quantity=1e12 + 1), None),
    ("batch_quantity Infinity (xom)", None, json.dumps(dict(BOM0, variant_name="g23")).replace('"batch_quantity": 1', '"batch_quantity": Infinity')),
    ("product_type_id 2**31", dict(BOM0, variant_name="g24", product_type_id=2 ** 31), None),
    ("product_type_id true", dict(BOM0, variant_name="g25", product_type_id=True), None),
    ("variant_name 101 belgi", dict(BOM0, variant_name="v" * 101), None),
    ("notes 10 001", dict(BOM0, variant_name="g26", notes="n" * 10001), None),
    ("qator 501 ta", dict(BOM0, variant_name="g27", items=[dict(IT0)] * 501), None),
]
for lbl, tana, raw in _g_rad:
    h0 = retseptlar()
    r = xom(C, "post", "/api/production/boms", raw) if raw else req(C, "post", "/api/production/boms", json=tana)
    rad400(f"G1 {lbl} → 400 (matn), retsept yaratilmadi", r, h0, retseptlar())
d = detail(req(C, "post", "/api/production/boms", json=dict(BOM0, variant_name="g28", items=[dict(IT0), dict(IT0, inventory_id=INVBID)])))
check("G2 begona material — qaysi qator ekani aytiladi, 'topilmadi' (oracle yo'q)", d == "'items' 2-qator: material topilmadi", d)
h0 = retseptlar()
r = req(C, "post", "/api/production/boms", json=dict(BOM0, variant_name="   "))
check("G3 faqat bo'shliqli nom → 'Standart' deb hisoblanadi (bor — takror 400), '' nomli retsept YO'Q",
      r.status_code == 400 and "Standart" in str(detail(r)) and retseptlar() == h0, f"{r.status_code} {detail(r)}")
r = req(C, "post", "/api/production/boms", json=dict(BOM0, product_type_id=PTID, variant_name="  Yozgi  ",
                                                     items=[dict(IT0), {"inventory_id": INV2ID, "quantity": 2, "component_type": "packaging",
                                                                        "scrap_factor_percent": 5, "is_optional": True, "is_coating": False,
                                                                        "fixed_cost_per_unit": 0, "percentage_cost": 10, "notes": "q"}]))
_g = js(r) or {}
check("G4 NAZORAT: to'liq qatorli retsept → 200, nom kesildi, qatorlar aynan",
      r.status_code == 200 and retsept(_g.get("id")) == ("Yozgi", 1.0, None, [(INVID, "raw_material", 1.0, False), (INV2ID, "packaging", 2.0, True)]),
      f"{r.status_code} {r.text[:160]} {retsept(_g.get('id'))}")
r = req(C, "post", "/api/production/boms", json=dict(BOM0, variant_name="g29", items=[dict(IT0), dict(IT0, quantity=2, is_optional=True)]))
check("G4 bir material ikki qatorda (xomashyo + ixtiyoriy) → 200 (ataylab ruxsat)", r.status_code == 200, f"{r.status_code} {detail(r)}")
YBID = _g.get("id")
h0 = retsept(YBID)
r = req(C, "put", f"/api/production/boms/{YBID}", json=dict(BOM0, variant_name="Yozgi", items=[dict(IT0, inventory_id=INVBID)]))
check("G5 PUT begona material → 400, retsept (qatorlari bilan) O'ZGARMADI", r.status_code == 400 and retsept(YBID) == h0,
      f"{r.status_code} {detail(r)} {retsept(YBID)}")
r = req(C, "put", f"/api/production/boms/{YBID}", json=dict(BOM0, variant_name="Yozgi", items=[]))
check("G5 PUT items [] → 400, o'zgarmadi", r.status_code == 400 and retsept(YBID) == h0, f"{r.status_code} {detail(r)}")
r = req(C, "put", f"/api/production/boms/{YBID}", json=dict(BOM0, variant_name="Yozgi", batch_quantity=2, company_id=BCID))
check("G5 PUT noma'lum kalit → 400, o'zgarmadi", r.status_code == 400 and retsept(YBID) == h0, f"{r.status_code} {detail(r)}")
r = req(C, "put", f"/api/production/boms/{YBID}", json=dict(BOM0, variant_name="Yozgi", batch_quantity=2))
check("G5 PUT NAZORAT → 200", r.status_code == 200 and (retsept(YBID) or [None, None])[1] == 2.0, f"{r.status_code} {retsept(YBID)}")
r = req(CB, "put", f"/api/production/boms/{YBID}", json=dict(BOM0, product_type_id=PTID, variant_name="B", items=[dict(IT0, inventory_id=INVBID)]))
check("G5 B korxona admini A retseptini (to'g'ri tana) → 404", r.status_code == 404, f"{r.status_code}")

# ════════════════════════════════════════════════════════════════
section("J. Ishlab chiqarish buyurtmasi — POST /api/production/orders (+ K93-1)")
# ════════════════════════════════════════════════════════════════
PO0 = {"product_type_id": PTID, "bom_id": BOMID, "quantity": 2, "source_type": "warehouse_stock"}


def buyurtmalar():
    return sanoq(ProductionOrder)


def po(pid):
    s = SessionLocal()
    try:
        p = s.get(ProductionOrder, pid)
        return None if p is None else (p.source_type, p.source_order_id, p.source_order_item_id, p.quantity,
                                       json.loads(p.selected_optional_bom_item_ids_json or "[]"), p.status)
    finally:
        s.close()


def kerak(oiid):
    s = SessionLocal()
    try:
        return PSV.mrp_detal_kerak(s, s.get(OrderItem, oiid))["kerak"]
    finally:
        s.close()


_j_rad = [
    ("noma'lum kalit (status, company_id)", dict(PO0, status="completed", company_id=BCID)),
    ("source_type 'qalbaki'", dict(PO0, source_type="qalbaki")),
    ("quantity true", dict(PO0, quantity=True)),
    ("quantity \"2\"", dict(PO0, quantity="2")),
    ("quantity 0", dict(PO0, quantity=0)),
    ("quantity 1e12 + 1", dict(PO0, quantity=1e12 + 1)),
    ("bom_id 2**31", dict(PO0, bom_id=2 ** 31)),
    ("product_type_id true", dict(PO0, product_type_id=True)),
    ("selected [true]", dict(PO0, selected_optional_bom_item_ids=[True])),
    ("selected [\"1\"]", dict(PO0, selected_optional_bom_item_ids=["1"])),
    ("selected [2**31]", dict(PO0, selected_optional_bom_item_ids=[2 ** 31])),
    ("selected 1 (ro'yxat emas)", dict(PO0, selected_optional_bom_item_ids=1)),
    ("selected 501 ta", dict(PO0, selected_optional_bom_item_ids=list(range(1, 502)))),
    ("omborga + O'Z detali", dict(PO0, source_order_item_id=OIA)),
    ("omborga + BEGONA detal", dict(PO0, source_order_item_id=OIB)),
    ("omborga + BEGONA buyurtma", dict(PO0, source_order_id=ORBID)),
    ("omborga + YO'Q buyurtma (999999)", dict(PO0, source_order_id=999999)),
    ("mijozga + detal 2**31", dict(PO0, source_type="customer_order", source_order_item_id=2 ** 31)),
    ("mijozga + BEGONA detal", dict(PO0, source_type="customer_order", source_order_item_id=OIB)),
    ("mijozga + boshqa buyurtma id si (mos emas)", dict(PO0, source_type="customer_order", source_order_item_id=OIA, source_order_id=ORA2ID)),
    ("notes 10 001", dict(PO0, notes="n" * 10001)),
]
for lbl, tana in _j_rad:
    h0 = buyurtmalar()
    r = req(C, "post", "/api/production/orders", json=tana)
    rad400(f"J1 {lbl} → 400 (matn), buyurtma yaratilmadi", r, h0, buyurtmalar())
h0 = buyurtmalar()
r = xom(C, "post", "/api/production/orders", json.dumps(PO0).replace('"quantity": 2', '"quantity": Infinity'))
rad400("J1 quantity Infinity (xom) → 400, yaratilmadi", r, h0, buyurtmalar())
r = req(C, "post", "/api/production/orders", json=dict(PO0, source_order_item_id=None, selected_optional_bom_item_ids=[OPTID, OPTID], notes=None))
_p = (js(r) or {}).get("production_order") or {}
check("J2 omborga NAZORAT (production.html tanasi) → 200, bog'lanishsiz, takror id bir marta",
      r.status_code == 200 and po(_p.get("id")) == ("warehouse_stock", None, None, 2.0, [OPTID], "draft"),
      f"{r.status_code} {r.text[:160]} {po(_p.get('id'))}")
r = req(C, "post", "/api/production/orders", json=dict(PO0, source_type="customer_order", source_order_item_id=OIA, quantity=3))
_p = (js(r) or {}).get("production_order") or {}
PO_MIJOZ = _p.get("id")
check("J3 mijozga NAZORAT → 200, buyurtma id si detaldan", r.status_code == 200 and (po(PO_MIJOZ) or [None] * 3)[1:3] == (ORAID, OIA),
      f"{r.status_code} {r.text[:160]} {po(PO_MIJOZ)}")
r = req(C, "post", "/api/production/orders", json=dict(PO0, source_type="customer_order", source_order_item_id=OIA2, source_order_id=ORA2ID,
                                                       quantity=1))
_p = (js(r) or {}).get("production_order") or {}
check("J3 mijozga + MOS buyurtma id si → 200", r.status_code == 200 and (po(_p.get("id")) or [None] * 3)[1:3] == (ORA2ID, OIA2),
      f"{r.status_code} {r.text[:160]}")
k0 = kerak(OIA)
r = req(C, "post", f"/api/production/orders/{PO_MIJOZ}/start")
check("J4 mijozga buyurtmani boshlash (nazorat) → 200, detal 'kerak' 3 ga kamaydi",
      r.status_code == 200 and abs(kerak(OIA) - (k0 - 3)) < 1e-9, f"{r.status_code} {r.text[:160]} {k0} -> {kerak(OIA)}")
# K93-1: K93-1 dan OLDIN yaratilgan (bazada bor bo'lishi mumkin) begona detalli buyurtma — Core bilan
_kb0 = kerak(OIB)
s = SessionLocal()
_lg = []
for _st in ("warehouse_stock", "customer_order"):
    _res = s.execute(ProductionOrder.__table__.insert().values(
        company_id=1, product_type_id=PTID, bom_id=BOMID, source_type=_st, source_order_item_id=OIB, quantity=2,
        status="draft", selected_optional_bom_item_ids_json="[]", created_at=datetime.utcnow()))
    _lg.append(_res.inserted_primary_key[0])
s.commit()
s.close()
for _pid, _st in zip(_lg, ("warehouse_stock", "customer_order")):
    f0 = sanoq(FinishedProduct)
    r = req(C, "post", f"/api/production/orders/{_pid}/start")
    s = SessionLocal()
    _band = s.query(func.count(FinishedProduct.id)).filter(FinishedProduct.reserved_for_order_item_id == OIB).scalar()
    s.close()
    check(f"J5 K93-1: eski {_st} buyurtma BEGONA detal bilan — boshlash → 409, TM yaratilmadi, B detaliga band YO'Q, B 'kerak' o'zgarmadi",
          r.status_code == 409 and sanoq(FinishedProduct) == f0 and _band == 0 and kerak(OIB) == _kb0 and (po(_pid) or [None] * 6)[5] == "draft",
          f"{r.status_code} {r.text[:160]} band={_band} kerak {_kb0}->{kerak(OIB)}")

# ════════════════════════════════════════════════════════════════
section("K. K93-2 — tannarx bazaga sig'maydi (boshlash / yakunlash)")
# ════════════════════════════════════════════════════════════════
s = SessionLocal()
_co = s.get(Company, 1)
_co.allow_negative_stock = True
s.commit()
s.close()


def harakatlar():
    return sanoq(InventoryMovement)


r = req(C, "post", "/api/production/orders", json=dict(PO0, quantity=1e12))
_pk = ((js(r) or {}).get("production_order") or {}).get("id")
i0, f0, m0 = inv(), sanoq(FinishedProduct), harakatlar()
r = req(C, "post", f"/api/production/orders/{_pk}/start")
_d = detail(r)
check("K1 1e12 dona × 100 so'm — boshlash → 409 'tannarxi juda katta', qoralama qoldi, TM / harakat yo'q",
      r.status_code == 409 and "tannarxi juda katta" in str(_d) and (po(_pk) or [None] * 6)[5] == "draft"
      and sanoq(FinishedProduct) == f0 and harakatlar() == m0 and inv() == i0, f"{r.status_code} {str(_d)[:160]}")
r = req(C, "post", "/api/production/orders", json=dict(PO0, quantity=1e8))
_pk2 = ((js(r) or {}).get("production_order") or {}).get("id")
r = req(C, "post", f"/api/production/orders/{_pk2}/start")
check("K1 chegara: 1e8 dona × 100 so'm (1e10 > sig'im) → 409", r.status_code == 409, f"{r.status_code} {r.text[:120]}")
r = req(C, "post", "/api/production/orders", json=dict(PO0, quantity=2))
_pk3 = ((js(r) or {}).get("production_order") or {}).get("id")
r = req(C, "post", f"/api/production/orders/{_pk3}/start")
check("K2 oddiy buyurtma boshlandi (nazorat) → 200", r.status_code == 200 and (po(_pk3) or [None] * 6)[5] == "in_progress", f"{r.status_code}")
# yakunlashgacha retseptga ULKAN qat'iy xarajat qo'shildi (yakunlash qo'shimcha xarajatni JORIY retseptdan oladi)
s = SessionLocal()
s.execute(BOMItem.__table__.update().where(BOMItem.bom_id == BOMID, BOMItem.inventory_id == INVID).values(fixed_cost_per_unit=9_000_000_000))
s.commit()
s.close()
i0, m0 = inv(), harakatlar()
r = req(C, "post", f"/api/production/orders/{_pk3}/complete")
check("K3 yakunlash: tannarx 18e9 > sig'im → 409, JARAYONDA qoldi, xomashyo ayirilmadi, harakat yozilmadi",
      r.status_code == 409 and "tannarxi juda katta" in str(detail(r)) and (po(_pk3) or [None] * 6)[5] == "in_progress"
      and inv() == i0 and harakatlar() == m0, f"{r.status_code} {r.text[:160]} {i0} -> {inv()}")
s = SessionLocal()
s.execute(BOMItem.__table__.update().where(BOMItem.bom_id == BOMID, BOMItem.inventory_id == INVID).values(fixed_cost_per_unit=None))
s.commit()
s.close()
r = req(C, "post", f"/api/production/orders/{_pk3}/complete")
s = SessionLocal()
_fp = s.query(FinishedProduct).filter(FinishedProduct.id == s.get(ProductionOrder, _pk3).finished_product_id).first()
_fpc = None if _fp is None else round(float(_fp.cost_price or 0), 2)
s.close()
check("K4 xarajat olib tashlangach yakunlash → 200, tannarx 2 × 1 × 100 = 200", r.status_code == 200 and _fpc == 200.0,
      f"{r.status_code} {r.text[:120]} {_fpc}")
_x = getattr(PSV, "_tannarx_sigimi_xatosi", None)
check("K5 yordamchi: 9 999 999 999.99 — sig'adi, 9 999 999 999.995 — sig'maydi, NaN — sig'maydi",
      callable(_x) and _x(9_999_999_999.99, 1) is None and _x(9_999_999_999.995, 1) is not None and _x(float("nan"), 1) is not None,
      "yordamchi yo'q")
check("K5 yordamchi: 1 birlik tannarxi (Numeric(14,4)) — 1e9 / 0.01 dona sig'maydi, 1e9 / 1 sig'adi",
      callable(_x) and _x(1e9, 0.01) is not None and _x(1e9, 1) is None, "yordamchi yo'q")

# ════════════════════════════════════════════════════════════════
section("S. Sxemalar (ikkinchi to'siq) va crud ildizi")
# ════════════════════════════════════════════════════════════════


def rad_sxema(fn):
    try:
        fn()
        return False
    except Exception:                      # noqa: BLE001
        return True


_pt = dict(name="X", unit="kg", input_template="quantity_only", pricing_formula="unit_based")
check("S1 ProductTypeCreate: noma'lum kalit rad", rad_sxema(lambda: PS.ProductTypeCreate(**_pt, company_id=2)))
check("S1 ProductTypeCreate: input_template 'qalbaki' rad", rad_sxema(lambda: PS.ProductTypeCreate(**dict(_pt, input_template="qalbaki"))))
check("S1 ProductTypeCreate: supports_coating 'yes' rad", rad_sxema(lambda: PS.ProductTypeCreate(**_pt, supports_coating="yes",
                                                                                                coating_price_multiplier=2)))
check("S1 ProductTypeCreate: fixed_unit_price inf rad", rad_sxema(lambda: PS.ProductTypeCreate(**_pt, fixed_unit_price=float("inf"))))
check("S1 ProductTypeCreate: fixed_unit_price 1e20 rad", rad_sxema(lambda: PS.ProductTypeCreate(**_pt, fixed_unit_price=1e20)))
check("S1 ProductTypeCreate: to'g'ri — qabul", not rad_sxema(lambda: PS.ProductTypeCreate(**_pt)))
check("S2 BOMItemCreate: inventory_id true rad", rad_sxema(lambda: PS.BOMItemCreate(inventory_id=True, quantity=1)))
check("S2 BOMItemCreate: inventory_id 2**31 rad", rad_sxema(lambda: PS.BOMItemCreate(inventory_id=2 ** 31, quantity=1)))
check("S2 BOMItemCreate: component_type 'qalbaki' rad", rad_sxema(lambda: PS.BOMItemCreate(inventory_id=1, quantity=1, component_type="qalbaki")))
check("S2 BOMItemCreate: quantity '5' rad", rad_sxema(lambda: PS.BOMItemCreate(inventory_id=1, quantity="5")))
check("S2 BOMCreate: items [] rad", rad_sxema(lambda: PS.BOMCreate(product_type_id=1, batch_quantity=1, items=[])))
check("S2 BOMCreate: batch inf rad", rad_sxema(lambda: PS.BOMCreate(product_type_id=1, batch_quantity=float("inf"),
                                                                    items=[{"inventory_id": 1, "quantity": 1}])))
check("S2 BOMCreate: to'g'ri — qabul", not rad_sxema(lambda: PS.BOMCreate(product_type_id=1, batch_quantity=1,
                                                                          items=[{"inventory_id": 1, "quantity": 1}])))
_po = dict(product_type_id=1, bom_id=1, quantity=1, source_type="warehouse_stock")
check("S3 ProductionOrderCreate: source_type 'qalbaki' rad", rad_sxema(lambda: PS.ProductionOrderCreate(**dict(_po, source_type="qalbaki"))))
check("S3 ProductionOrderCreate: selected [true] rad", rad_sxema(lambda: PS.ProductionOrderCreate(**_po, selected_optional_bom_item_ids=[True])))
check("S3 ProductionOrderCreate: quantity true rad", rad_sxema(lambda: PS.ProductionOrderCreate(**dict(_po, quantity=True))))
check("S3 ProductionOrderCreate: noma'lum kalit rad", rad_sxema(lambda: PS.ProductionOrderCreate(**_po, status="completed")))
check("S3 ProductionOrderCreate: to'g'ri — qabul", not rad_sxema(lambda: PS.ProductionOrderCreate(**_po)))
check("S4 MasterKpiUpdate: true rad", rad_sxema(lambda: SC.MasterKpiUpdate(kpi_percent=True)))
check("S4 MasterKpiUpdate: '7' rad", rad_sxema(lambda: SC.MasterKpiUpdate(kpi_percent="7")))
check("S4 MasterKpiUpdate: noma'lum kalit rad", rad_sxema(lambda: SC.MasterKpiUpdate(kpi_percent=5, cashback_percent=1)))
check("S4 MasterKpiUpdate: 5 — qabul", not rad_sxema(lambda: SC.MasterKpiUpdate(kpi_percent=5)))
s = SessionLocal()
_k0 = s.get(Master, M2ID).kpi_percent
check("S5 crud.update_master_kpi(true) → ValueError, o'zgarmadi", rad_sxema(lambda: crud.update_master_kpi(s, M2ID, True, company_id=1))
      and s.get(Master, M2ID).kpi_percent == _k0)
check("S5 crud.update_master_kpi('7') → ValueError", rad_sxema(lambda: crud.update_master_kpi(s, M2ID, "7", company_id=1)))
check("S5 crud.update_master_kpi(nan) → ValueError", rad_sxema(lambda: crud.update_master_kpi(s, M2ID, float("nan"), company_id=1)))
_m = xavfsiz(crud.update_master_kpi, s, M2ID, 9, company_id=1)
check("S5 crud.update_master_kpi(9) → saqlandi", getattr(_m, "kpi_percent", None) == 9, _m)
s.close()
req(C, "post", "/api/gift-period/open", json={"tiers": [{"gift_name": "S", "threshold_amount": 1000000}], "master_ids": [MID]})
_pid = faol_davr()
s = SessionLocal()
for lbl, v in [("true", True), ("'id' matn", str(M2ID)), ("N.0", float(M2ID)), ("2**31", 2 ** 31)]:
    _res = xavfsiz(crud.add_master_to_active_gift_period, s, v, company_id=1)
    check(f"S6 crud.add_master_to_active_gift_period({lbl}) → success False (istisno yo'q), qo'shilmadi",
          isinstance(_res, dict) and _res.get("success") is False and ishtirokchilar(_pid) == [MID], _res)
for lbl, v in [("\"false\"", "false"), ("1", 1), ("None", None)]:
    _res = xavfsiz(crud.close_gift_period, s, force=v, company_id=1)
    check(f"S7 crud.close_gift_period(force={lbl}) → success False, davr ochiq", isinstance(_res, dict) and _res.get("success") is False
          and faol_davr() == _pid, _res)
s.close()
s = SessionLocal()
_r = xavfsiz(PSV.create_production_order, s, 1, PS.ProductionOrderCreate(**dict(_po, product_type_id=PTID, bom_id=BOMID,
                                                                                 source_order_item_id=OIA)))
check("S8 servis: omborga + detal (sxema orqali) → success False", isinstance(_r, dict) and _r.get("success") is False, _r)
s.close()
_cv = getattr(crud, "_clean_val", None)
check("S9 _clean_val('BOM'): nom None / '' / '   ' → 'Standart'",
      all(xavfsiz(_cv, "BOM", dict(BOM0, variant_name=v)).get("variant_name") == "Standart" if isinstance(xavfsiz(_cv, "BOM", dict(BOM0, variant_name=v)), dict)
          else False for v in (None, "", "   ")))
check("S9 _clean_val('UserCreate'): login kesiladi", (xavfsiz(_cv, "UserCreate", {"username": " a ", "password": PAROL}) or {}).get("username") == "a"
      if isinstance(xavfsiz(_cv, "UserCreate", {"username": " a ", "password": PAROL}), dict) else False)

# ════════════════════════════════════════════════════════════════
section("U. UI — HAQIQIY shablon funksiyalari (node) yuborgan tanalar serverga")
# ════════════════════════════════════════════════════════════════


def js_funksiya(matn, nom_):
    """`async function nom_(` yoki `function nom_(` — qator boshidagi birinchi `}` gacha."""
    for bosh in ("async function " + nom_ + "(", "function " + nom_ + "("):
        i = matn.find(bosh)
        if i >= 0:
            k = matn.find("\n}", i)
            return matn[i:k + 2] if k >= 0 else ""
    return ""


_prod = open(os.path.join(ROOT, "templates", "production.html"), encoding="utf-8").read()
_kpi = open(os.path.join(ROOT, "templates", "kpi.html"), encoding="utf-8").read()
_usr = open(os.path.join(ROOT, "templates", "users.html"), encoding="utf-8").read()
_fnlar = {n: js_funksiya(_prod, n) for n in ("saveProductType", "saveBom", "saveProductionOrder")}
_fnlar.update({n: js_funksiya(_kpi, n) for n in ("saveMasterKpi", "submitOpenGiftPeriod", "saveTierEdit",
                                                 "submitAddMasterToGiftPeriod", "submitCloseGiftPeriod", "parseNum", "fmt")})
_fnlar.update({n: js_funksiya(_usr, n) for n in ("saveUser", "changePass", "changeMyPassword")})
check("U0 hamma UI funksiyalari shablonlarda topildi", all(_fnlar.values()), [k for k, v in _fnlar.items() if not v])
_fnlar["changeMyPassword"] = _fnlar["changeMyPassword"].replace("{{ current_user.id }}", "990001")
ADMIN_YANGI = "AdminYangi1!"
_harness = r"""
const SENT = {}; let CUR = null;
function mkEl(o) { const e = {value: '', checked: false, dataset: {}, style: {}, textContent: '', innerHTML: '', disabled: false,
  children: [], _q: {}, classList: {add(){}, remove(){}, toggle(){}}, querySelector(s) { return this._q[s] || mkEl(); },
  click(){}, closest() { return null; }, focus(){}, remove(){}, appendChild(){} }; return Object.assign(e, o || {}); }
let EL = {}; let QSA = {};
globalThis.document = { getElementById: id => (EL[id] || (EL[id] = mkEl())), querySelectorAll: s => (QSA[s] || []),
  querySelector: s => mkEl(), body: {appendChild(){}}, createElement: () => mkEl() };
globalThis.fetch = async (url, opt) => { SENT[CUR] = {url, method: (opt && opt.method) || 'GET',
  body: (opt && opt.body) ? JSON.parse(opt.body) : null}; return {ok: true, status: 200, json: async () => ({})}; };
globalThis.alert = m => { (SENT['_alert'] = SENT['_alert'] || []).push(CUR + ': ' + String(m)); };
let PROMPTS = []; globalThis.prompt = () => PROMPTS.shift();
globalThis.customConfirm = async () => true;
for (const n of ['showMsg', 'closeModal', 'loadProductTypes', 'switchProdTab', 'loadMasterKpi', 'loadGiftPeriod', 'showAddedToast'])
  globalThis[n] = () => {};
globalThis.location = {reload(){}};
var isOpeningGiftPeriod = false, isSavingTierEdit = false, isClosingGiftPeriod = false, isSavingUser = false;
var inFlightMasterKpi = new Set(); var _newPeriodTiers = [];
function v(id, val) { EL[id] = mkEl({value: String(val)}); }
function c(id, val) { EL[id] = mkEl({checked: !!val}); }
function qator(o) { return mkEl({_q: {'.bi-inventory': mkEl({value: String(o.inv)}), '.bi-component-type': mkEl({value: o.tur}),
  '.bi-quantity': mkEl({value: o.q}), '.bi-scrap': mkEl({value: o.scrap}), '.bi-optional': mkEl({checked: o.opt}),
  '.bi-coating': mkEl({checked: o.coat}), '.bi-fixed-cost': mkEl({value: o.fix}), '.bi-percentage-cost': mkEl({value: o.pct})}}); }
"""
_ssenariy = r"""
async function yur() {
  const K = __KIRISH__;
  EL = {}; QSA = {}; CUR = 'P1';
  v('pt-f-name', 'UI tur 1'); v('pt-f-unit', 'm²'); v('pt-f-input-template', 'area_2d'); v('pt-f-pricing-formula', 'fixed_price');
  v('pt-f-fixed-price', '150000'); c('pt-f-supports-coating', true); v('pt-f-coating-mult', '2.5'); v('pt-f-notes', '');
  await saveProductType();
  EL = {}; QSA = {}; CUR = 'P2';
  v('pt-f-name', ' UI tur 2 '); v('pt-f-unit', 'dona'); v('pt-f-input-template', 'quantity_only'); v('pt-f-pricing-formula', 'unit_based');
  v('pt-f-fixed-price', ''); c('pt-f-supports-coating', false); v('pt-f-coating-mult', ''); v('pt-f-notes', 'izoh');
  await saveProductType();
  EL = {}; QSA = {}; CUR = 'B1';
  v('bom-f-product-type-id', K.pt); v('bom-f-editing-id', ''); v('bom-f-variant', ''); v('bom-f-batch', '10'); v('bom-f-notes', '');
  EL['bom-items-wrap'] = mkEl({children: [qator({inv: K.inv, tur: 'raw_material', q: '2.5', scrap: '', opt: false, coat: false, fix: '', pct: ''}),
                                          qator({inv: K.inv2, tur: 'packaging', q: '1', scrap: '3', opt: true, coat: true, fix: '100', pct: '10'})]});
  await saveBom();
  EL = {}; QSA = {}; CUR = 'B2';
  v('bom-f-product-type-id', K.pt); v('bom-f-editing-id', K.bom); v('bom-f-variant', 'Standart'); v('bom-f-batch', '1'); v('bom-f-notes', 'x');
  EL['bom-items-wrap'] = mkEl({children: [qator({inv: K.inv, tur: 'raw_material', q: '1', scrap: '0', opt: false, coat: false, fix: '', pct: ''}),
                                          qator({inv: K.inv2, tur: 'raw_material', q: '0.5', scrap: '0', opt: true, coat: true, fix: '', pct: ''})]});
  await saveBom();
  EL = {}; QSA = {}; CUR = 'O1';
  v('po-f-product-type', K.pt); v('po-f-bom', K.bom); v('po-f-quantity', '3'); v('po-f-source-type', 'warehouse_stock');
  v('po-f-source-order-item', ''); v('po-f-notes', '');
  QSA['#po-optional-list .po-opt'] = [mkEl({checked: true, dataset: {id: String(K.opt)}})];
  await saveProductionOrder();
  EL = {}; QSA = {}; CUR = 'O2';
  v('po-f-product-type', K.pt); v('po-f-bom', K.bom); v('po-f-quantity', '1'); v('po-f-source-type', 'customer_order');
  v('po-f-source-order-item', K.oi); v('po-f-notes', 'mijoz');
  QSA['#po-optional-list .po-opt'] = [mkEl({checked: false, dataset: {id: String(K.opt)}})];
  await saveProductionOrder();
  EL = {}; QSA = {}; CUR = 'K1'; v('mk-' + K.m1, '7.5'); await saveMasterKpi(K.m1);
  EL = {}; QSA = {}; CUR = 'K2'; v('mk-' + K.m1, ''); await saveMasterKpi(K.m1);
  EL = {}; QSA = {}; CUR = 'G1';
  _newPeriodTiers = [{name: "Sovg'a UI", amount: parseNum('1 000 000')}, {name: '', amount: ''}];
  c('giftPeriodSelectMode', true); QSA['.gift-period-master-cb:checked'] = [mkEl({value: String(K.m1)})];
  await submitOpenGiftPeriod();
  EL = {}; QSA = {}; CUR = 'G2'; v('tierEditName', 'Sovg\'a UI 2'); v('tierEditAmount', '2 000 000'); await saveTierEdit(990002);
  EL = {}; QSA = {}; CUR = 'G3'; v('giftPeriodAddMasterSelect', K.m2); await submitAddMasterToGiftPeriod();
  EL = {}; QSA = {}; CUR = 'G4'; await submitCloseGiftPeriod(false);
  EL = {}; QSA = {}; CUR = 'U1';
  v('f-username', ' ui_user '); v('f-password', 'Parol123!'); v('f-role', 'manager'); v('f-fullname', 'UI Foydalanuvchi');
  await saveUser();
  EL = {}; QSA = {}; CUR = 'U2'; PROMPTS = ['UiYangi123!']; await changePass(990003, 'ui_user', null);
  EL = {}; QSA = {}; CUR = 'U3'; PROMPTS = [K.eski, K.yangi, K.yangi]; await changeMyPassword();
  process.stdout.write(JSON.stringify(SENT));
}
yur().catch(e => process.stdout.write(JSON.stringify({XATO: String(e && e.stack || e)})));
"""
_kir = {"pt": PTID, "bom": BOMID, "inv": INVID, "inv2": INV2ID, "opt": OPTID, "oi": OIA2, "m1": MID, "m2": M2ID,
        "eski": PAROL, "yangi": ADMIN_YANGI}
_skript = _harness + "\n".join(_fnlar.values()) + _ssenariy.replace("__KIRISH__", json.dumps(_kir))
UI = {}
_p = os.path.join(_T, "ui_tana.js")
open(_p, "w", encoding="utf-8").write(_skript)
try:
    _o = subprocess.run(["node", _p], capture_output=True, text=True, timeout=60)
    UI = json.loads(_o.stdout or "{}")
except Exception as e:                     # noqa: BLE001
    UI = {"XATO": f"{type(e).__name__}: {e}"}
_ogoh = [a for a in ((UI or {}).get("_alert") or []) if any(x in a for x in ("❌", "Kamida", "to'g'ri", "Xato", "mos kelmadi"))]
check("U0 node: 15 ssenariy tanasi olindi, UI o'zi rad etmadi (xato alert yo'q)", isinstance(UI, dict) and "XATO" not in UI and not _ogoh
      and all(k in UI for k in ("P1", "P2", "B1", "B2", "O1", "O2", "K1", "K2", "G1", "G2", "G3", "G4", "U1", "U2", "U3")),
      f"kalitlar={sorted(UI.keys()) if isinstance(UI, dict) else UI} alert={(UI or {}).get('_alert')} xato={str((UI or {}).get('XATO'))[:200]}")


def ui_yubor(kod, almash=None):
    x = UI.get(kod) or {}
    url = x.get("url") or "/yoq"
    for a, b in (almash or {}).items():
        url = url.replace(a, str(b))
    return req(C, (x.get("method") or "GET").lower(), url, json=x.get("body"))


for kod, izoh in [("P1", "mahsulot turi (qat'iy narx, qoplama 2.5)"), ("P2", "mahsulot turi (bo'sh maydonlar → null)")]:
    r = ui_yubor(kod)
    check(f"U1 production.html saveProductType {izoh} → 200", r.status_code == 200, f"{r.status_code} {r.text[:160]} | {UI.get(kod)}")
r = ui_yubor("B1")
check("U2 production.html saveBom (yangi, nom bo'sh → 'Standart' → takror 400 EMAS: UI 'Standart' yuboradi, shu tur uchun bor)",
      r.status_code in (200, 400) and (r.status_code == 200 or "Standart" in str(detail(r))), f"{r.status_code} {r.text[:160]}")
_b1 = dict((UI.get("B1") or {}).get("body") or {})
_b1["variant_name"] = "UI yangi"
r = req(C, "post", "/api/production/boms", json=_b1)
check("U2 saveBom tanasi (yangi nom bilan) → 200 (bo'sh isrof → 0, bo'sh xarajat → null)", r.status_code == 200,
      f"{r.status_code} {r.text[:160]} | {_b1}")
r = ui_yubor("B2")
check("U2 production.html saveBom (tahrir, PUT) → 200", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
r = ui_yubor("O1")
check("U3 production.html saveProductionOrder (omborga, ixtiyoriy qator) → 200", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
r = ui_yubor("O2")
check("U3 production.html saveProductionOrder (mijoz buyurtmasi) → 200", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
for kod in ("K1", "K2"):
    r = ui_yubor(kod)
    check(f"U4 kpi.html saveMasterKpi {kod} → 200", r.status_code == 200, f"{r.status_code} {r.text[:160]} | {UI.get(kod)}")
req(C, "post", "/api/gift-period/close", json={"force": True})
r = ui_yubor("G1")
_gp = faol_davr()
check("U5 kpi.html submitOpenGiftPeriod (tanlangan usta) → 200", r.status_code == 200 and _gp is not None and ishtirokchilar(_gp) == [MID],
      f"{r.status_code} {r.text[:160]} | {UI.get('G1')}")
s = SessionLocal()
_tid = s.query(GiftPeriodTier).filter(GiftPeriodTier.period_id == _gp).first().id if _gp else 0
s.close()
r = ui_yubor("G2", {"990002": _tid})
check("U5 kpi.html saveTierEdit → 200", r.status_code == 200 and bosqich(_tid) == ("Sovg'a UI 2", 2000000.0), f"{r.status_code} {r.text[:160]}")
r = ui_yubor("G3")
check("U5 kpi.html submitAddMasterToGiftPeriod → 200", r.status_code == 200 and ishtirokchilar(_gp) == sorted([MID, M2ID]),
      f"{r.status_code} {r.text[:160]}")
r = ui_yubor("G4")
check("U5 kpi.html submitCloseGiftPeriod(false) → 200 yoki 400 (sovg'aga yetganlar), 422 EMAS",
      r.status_code in (200, 400) and not (r.status_code == 400 and isinstance(detail(r), str)), f"{r.status_code} {r.text[:160]}")
r = ui_yubor("U1")
check("U6 users.html saveUser → 200", r.status_code == 200 and user_bor("ui_user") is not None, f"{r.status_code} {r.text[:160]}")
s = SessionLocal()
_uid = (s.query(User).filter(User.username == "ui_user").first() or User(id=0)).id
s.close()
r = ui_yubor("U2", {"990003": _uid})
check("U6 users.html changePass → 200", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
r = ui_yubor("U3", {"990001": ADMIN_ID})
_, _l = klient("TQ_admin", ADMIN_YANGI)
check("U6 users.html changeMyPassword (joriy parol bilan) → 200 va yangi parol bilan kiradi", r.status_code == 200 and _l == 302,
      f"{r.status_code} {r.text[:160]} {_l}")

# ════════════════════════════════════════════════════════════════
section("X. Hech bir javob 500 emas")
# ════════════════════════════════════════════════════════════════
_besh = [x for x in HOLATLAR if x[1] >= 500]
check(f"X1 {len(HOLATLAR)} HTTP javobning hech biri 5xx emas", not _besh, _besh[:10])

# ════════════════════════════════════════════════════════════════
section("H. Statik")
# ════════════════════════════════════════════════════════════════
_psrc = open(os.path.join(ROOT, "production_schemas.py"), encoding="utf-8").read()
for _cls, _enum, _maydon in [(PS.ProductTypeCreate, InputTemplate, "input_template"), (PS.ProductTypeCreate, PricingFormula, "pricing_formula"),
                             (PS.BOMItemCreate, BOMComponentType, "component_type"),
                             (PS.ProductionOrderCreate, ProductionSourceType, "source_type")]:
    try:
        _args = set(getattr(_cls.model_fields[_maydon].annotation, "__args__", ()) or ())
    except Exception:                      # noqa: BLE001
        _args = set()
    check(f"H1 {_cls.__name__}.{_maydon} Literal = {_enum.__name__} qiymatlari (AYNAN)", _args == {m.value for m in _enum},
          f"{_args} vs {[m.value for m in _enum]}")
for _cls in (PS.ProductTypeCreate, PS.BOMItemCreate, PS.BOMCreate, PS.ProductionOrderCreate, SC.MasterKpiUpdate):
    _mc = getattr(_cls, "model_config", {}) or {}
    check(f"H2 {_cls.__name__}: extra=forbid, strict, allow_inf_nan=False",
          _mc.get("extra") == "forbid" and _mc.get("strict") is True and _mc.get("allow_inf_nan") is False, _mc)
_rules = xavfsiz(getattr(crud, "_val_rules", lambda: {}))
_rules = _rules if isinstance(_rules, dict) else {}


def uzunlik(tbl, ust):
    try:
        return tbl.__table__.c[ust].type.length
    except Exception:                      # noqa: BLE001
        return None


for _m, _k, _tbl, _ust in [("UserCreate", "username", User, "username"), ("UserCreate", "full_name", User, "full_name"),
                           ("ProductType", "name", ProductType, "name"), ("ProductType", "unit", ProductType, "unit"),
                           ("BOM", "variant_name", BOM, "variant_name")]:
    _q = (_rules.get(_m) or {}).get(_k)
    check(f"H3 qoida {_m}.{_k} matn chegarasi = ustun sig'imi ({_tbl.__tablename__}.{_ust})",
          bool(_q) and _q[0] == "matn" and _q[2] == uzunlik(_tbl, _ust), f"{_q} vs {uzunlik(_tbl, _ust)}")
check("H4 parol eng ko'pi 72 bayt (bcrypt), eng kami 6", getattr(crud, "_PAROL_MAX_BAYT", None) == 72 and getattr(crud, "_PAROL_MIN", None) == 6)
_fp_cost = FinishedProduct.__table__.c["cost_price"].type
_fp_unit = FinishedProduct.__table__.c["unit_cost_stable"].type
check("H5 K93-2 chegaralari ustun sig'imidan: cost_price Numeric(12,2), unit_cost_stable Numeric(14,4)",
      getattr(PSV, "_TANNARX_MAX", None) == round(10 ** (_fp_cost.precision - _fp_cost.scale) - 10 ** -_fp_cost.scale, _fp_cost.scale)
      and getattr(PSV, "_BIRLIK_TANNARX_MAX", None) == round(10 ** (_fp_unit.precision - _fp_unit.scale) - 10 ** -_fp_unit.scale, _fp_unit.scale),
      f"{getattr(PSV, '_TANNARX_MAX', None)} {getattr(PSV, '_BIRLIK_TANNARX_MAX', None)}")
_msrc = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
for _fn, _qism in [("api_create_user", 'crud._clean_val("UserCreate", data)'), ("api_change_password", 'crud._clean_val("UserPassword", data)'),
                   ("api_open_gift_period", 'crud._faqat_kalitlar(data, {"tiers", "master_ids"})'),
                   ("api_update_gift_period_tier", 'crud._faqat_kalitlar(data, {"gift_name", "threshold_amount"})'),
                   ("api_add_master_to_gift_period", 'crud._clean_val("GiftAddMaster", data)'),
                   ("api_close_gift_period", 'crud._clean_val("GiftClose"'),
                   ("api_update_price", 'crud._faqat_kalitlar(data, {"price_per_unit", "volume_per_unit"})'),
                   ("api_update_min_stock", 'crud._faqat_kalitlar(data, {"min_stock"})')]:
    check(f"H6 main.{_fn}: {_qism[:60]}", _qism in manba(main, _fn), "yo'q")
check("H6 main.api_close_gift_period: eski `bool((data or {}).get(\"force\"))` YO'Q",
      'force = bool((data or {}).get("force"))' not in manba(main, "api_close_gift_period"))
for _fn, _mod in [("create_product_type", "ProductType"), ("create_bom", "BOM"), ("update_bom", "BOM"), ("create_order", "ProductionOrder")]:
    _s = manba(PR, _fn)
    check(f"H7 production_routes.{_fn}: `_tana(\"{_mod}\"` va tana `dict = Body(...)`", f'_tana("{_mod}", data' in _s
          and "data: dict = Body(...)" in _s, _s[:120])
for _fn in ("create_bom", "update_bom"):
    check(f"H7 production_routes.{_fn}: materiallar shu korxonadan (`_retsept_materiallari`)", "_retsept_materiallari(db, data.items" in manba(PR, _fn))
_ssrc = manba(PSV, "start_production_order")
check("H8 start: begona / yo'q detal — boshlanmaydi (else tarmog'i) va tannarx sig'imi erta",
      "Bog'langan buyurtma-detali topilmadi" in _ssrc and "_tannarx_sigimi_xatosi(" in _ssrc)
check("H8 complete: tannarx sig'imi — yozishdan OLDIN", "_tannarx_sigimi_xatosi(total_cost" in manba(PSV, "complete_production_order"))
check("H8 create_production_order: omborga — bog'lanishsiz",
      "Omborga ishlab chiqarishda buyurtma yoki" in manba(PSV, "create_production_order"))

print("\n" + "=" * 66)
print(f"REJIM: {'PostgreSQL' if PG_URL else 'SQLite'}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
sys.exit(1 if FAIL else 0)
