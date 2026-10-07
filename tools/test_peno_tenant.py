#!/usr/bin/env python3
"""
test_peno_tenant.py — "asosiy penoplast" bo'yicha korxonalararo darvoza
va `models._tenant_guard` ning filtr ostida ishlashi.

NIMA UCHUN KERAK (2026-09-21, hammasi asl kodda HTTP orqali O'LCHANGAN)
-----------------------------------------------------------------------
1. O'QISH: `services.get_penoplast_list()` da korxona filtri umuman yo'q
   edi — B `GET /api/penoplasts`, `/orders`, `/finished` da A ning
   penoplastlarini (nomi, qoldig'i, narxi) ko'rardi.
2. YOZISH: `POST /api/inventory/{id}/set-default-penoplast` ommaviy
   UPDATE bilan BUTUN bazadagi asosiy belgilarni o'chirardi — B o'z
   penoplastini asosiy qilsa, A ning asosiy plotnosti yo'qolardi.
   `TENANT_FILTER=1` da HAM (filtr faqat SELECT ga ta'sir qiladi).
3. `get_default_penoplast(db)` 6 joyda korxonasiz chaqirilib, butun
   bazadagi BIRINCHI asosiy penoplastni (odatda A nikini) qaytarardi.
   Natija (filtr o'chiq): B penoplast tanlamagan buyurtma yarata
   OLMASDI — 409.
4. HIMOYA KO'RLIGI: `_tenant_guard` ota/havola yozuvini `session.get()`
   bilan o'qirdi va `TENANT_FILTER=1` da bu o'qish filtrlanardi — begona
   yozuv "yo'q" bo'lib ko'rinib, tekshiruv jimgina o'tkazilardi. B ning
   buyurtma detaliga A ning `penoplast_id` si BAZAGA YOZILARDI (filtr
   o'chiq bo'lsa xuddi shu so'rov 409 edi).

QAMROV
------
1. B ning o'qishlari — A penoplasti ko'rinmaydi
2. B ning yozishlari — A ombori VA asosiy belgilari o'zgarmaydi; B ning
   buyurtmasi O'Z asosiy penoplastidan ayiradi
3. A→A — A ning o'z asosiy penoplasti ishlaydi, aniq miqdor bilan
4. Himoya filtr ostida — begona havola rad etiladi (ENABLED majburan
   yoqib tekshiriladi, shuning uchun filtr o'chiq ishga tushirishda ham
   qulf faol)
5. Ildiz funksiyalar — korxona noma'lum bo'lsa zaxira yo'q

ISHLATISH
---------
    python tools/test_peno_tenant.py
    TENANT_FILTER=1 python tools/test_peno_tenant.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "peno_tenant_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402,F401
    import crud, auth, schemas, services           # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from sqlalchemy import event                       # noqa: E402
import tenant_context as _tc                       # noqa: E402


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


engine.dispose()

from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Inventory, Order, OrderItem, TenantMismatchError,
)
from fastapi.testclient import TestClient          # noqa: E402

db = SessionLocal()
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {detail}")


def section(t):
    print(f"\n--- {t} ---")


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="Test Korxona B"))
    db.commit()

with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "AAA_user", "Parol123!", UserRole.ADMIN, "AAA",
                     company_id=1)
    auth.create_user(db, "BBB_user", "Parol123!", UserRole.ADMIN, "BBB",
                     company_id=2)

# A — birinchi yaratiladi (kichik ID): korxonasiz `.first()` aynan uni
# qaytarardi. A1 asosiy, A2 ikkinchi (boshqa hajm/narx — farq ko'rinsin).
A1 = Inventory(company_id=1, item_name="AAA_PENO_ASOSIY", unit="blok",
               stock_quantity=100.0, price_per_unit=200000,
               volume_per_unit=1.0, is_penoplast=True,
               is_default_penoplast=True)
A2 = Inventory(company_id=1, item_name="AAA_PENO_IKKINCHI", unit="blok",
               stock_quantity=100.0, price_per_unit=900000,
               volume_per_unit=0.5, is_penoplast=True)
db.add_all([A1, A2])
db.commit()
B1 = Inventory(company_id=2, item_name="BBB_PENO", unit="blok",
               stock_quantity=100.0, price_per_unit=100000,
               volume_per_unit=2.0, is_penoplast=True,
               is_default_penoplast=True)
db.add(B1)
db.commit()
with contextlib.redirect_stdout(_quiet):
    A_PROJ = crud.create_project(db, schemas.ProjectCreate(
        project_name="AAA_L", client_name="AAA_Mijoz"), company_id=1)
    B_PROJ = crud.create_project(db, schemas.ProjectCreate(
        project_name="BBB_L", client_name="BBB_Mijoz"), company_id=2)


def a_state():
    """A ning BUTUN ombori: qoldiq VA asosiy belgisi (belgi ham sizish)."""
    db.expire_all()
    rows = db.query(Inventory).filter(Inventory.company_id == 1).all()
    return {r.id: (r.item_name, round(float(r.stock_quantity or 0), 6),
                   bool(r.is_default_penoplast)) for r in rows}


def stock(inv):
    db.expire_all()
    return float(db.get(Inventory, inv.id).stock_quantity)


def login(user):
    c = TestClient(main.app, base_url="https://testserver")
    r = c.post("/login", data={"username": user, "password": "Parol123!"},
               follow_redirects=False)
    assert r.status_code == 302, f"{user} login bo'lmadi: {r.status_code}"
    return c


B = login("BBB_user")
A = login("AAA_user")

print("=" * 66)
print("PENOPLAST DARVOZASI — asosiy penoplast va himoya filtr ostida")
print("TENANT_FILTER = " + ("1 (YOQILGAN)" if _tc.ENABLED else "0 (o'chiq)"))
print("=" * 66)

# 100×10×100 sm × 10 dona = 1.0 m³ — barcha hisoblarda shu hajm.
PANEL = {"category": "panel", "width": 100, "thickness": 10, "length": 100,
         "quantity": 10, "unit_price": 1000, "is_coated": False}


def order_body(proj, name, **extra):
    return {"project_id": proj.id, "order_type": "product",
            "items": [dict(PANEL, name=name, **extra)]}


# ══════════════════════════════════════════════════════════════
section("1. B ning o'qishlari — A penoplasti ko'rinmaydi")
# ══════════════════════════════════════════════════════════════
# Belgi "AAA_PENO" — "AAA" emas: /orders da #B0AAA0 CSS rangi bor.
for url in ("/api/penoplasts", "/orders", "/finished"):
    r = B.get(url)
    check(f"GET {url} — 200", r.status_code == 200, f"HTTP {r.status_code}")
    check(f"GET {url} — A penoplasti yo'q", "AAA_PENO" not in r.text)

r = B.get("/api/penoplasts").json()
check("GET /api/penoplasts — B o'z penoplastini ko'radi",
      [i["name"] for i in r["items"]] == ["BBB_PENO"], str(r["items"])[:160])
check("GET /api/penoplasts — default_id = B ning asosiysi",
      r["default_id"] == B1.id, f"{r['default_id']} != {B1.id}")

# ══════════════════════════════════════════════════════════════
section("2. B ning yozishlari — A ga tegmaydi")
# ══════════════════════════════════════════════════════════════
before = a_state()
r = B.post(f"/api/inventory/{B1.id}/set-default-penoplast")
check("B set-default (o'z penoplasti) — 2xx", 200 <= r.status_code < 300,
      f"HTTP {r.status_code}")
check("B set-default — A ning asosiy belgisi O'ZGARMADI",
      a_state() == before, f"{before} → {a_state()}")
db.expire_all()
check("B set-default — B1 hamon asosiy (belgi yo'qolmadi)",
      db.get(Inventory, B1.id).is_default_penoplast is True)

before, b0 = a_state(), stock(B1)
r = B.post("/api/orders?confirm_shortage=true",
           json=order_body(B_PROJ, "BBB_Panel"))
check("B buyurtma (penoplast tanlanmagan) — 2xx",
      200 <= r.status_code < 300, f"HTTP {r.status_code}: {r.text[:160]}")
check("B buyurtma — A ombori O'ZGARMADI", a_state() == before)
check("B buyurtma — O'Z asosiysidan ayirdi: 1.0 m³ / 2.0 = -0.5 blok",
      abs((b0 - stock(B1)) - 0.5) < 1e-6, f"{b0} → {stock(B1)}")
B_ORDER_ID = r.json().get("id") if r.status_code < 300 else None

before, b0 = a_state(), stock(B1)
r = B.post("/api/orders?confirm_shortage=true",
           json=order_body(B_PROJ, "BBB_Begona", quantity=7,
                           penoplast_id=A2.id))
check("B buyurtma + A ning penoplast_id si — RAD ETILDI (4xx)",
      400 <= r.status_code < 500, f"HTTP {r.status_code}: {r.text[:160]}")
check("B buyurtma + A ning penoplast_id si — A ombori O'ZGARMADI",
      a_state() == before)
db.expire_all()
_foreign = db.query(OrderItem).filter(OrderItem.company_id == 2,
                                      OrderItem.penoplast_id.in_([A1.id, A2.id])).count()
check("B ning birorta detali A penoplastiga bog'lanmagan", _foreign == 0,
      f"{_foreign} ta begona havola saqlangan")

before, b0 = a_state(), stock(B1)
r = B.post("/api/finished/produce",
           json={"name": "BBB_FP", "category": "panel", "width": 100,
                 "thickness": 10, "length": 100, "quantity": 5,
                 "unit_price": 1000})
check("B produce (penoplast tanlanmagan) — 2xx", 200 <= r.status_code < 300,
      f"HTTP {r.status_code}: {r.text[:160]}")
check("B produce — A ombori O'ZGARMADI", a_state() == before)
check("B produce — O'Z asosiysidan ayirdi", stock(B1) < b0,
      f"{b0} → {stock(B1)}")

# Ichki funksiyalar B ning HAQIQIY buyurtmasi bilan (HTTP da yaratilgan)
if B_ORDER_ID:
    db.expire_all()
    bo = db.get(Order, B_ORDER_ID)
    bi = bo.items[0]
    before = a_state()
    with contextlib.redirect_stdout(_quiet):
        services.deduct_raw_material_for_brak(db, bi, bo, 2, False)
        db.commit()
    check("deduct_raw_material_for_brak(B) — A ombori O'ZGARMADI",
          a_state() == before)
    uc = services.get_order_item_unit_cost(db, bo, bi, include_coating=False)
    # 0.1 m³/dona ÷ 2.0 = 0.05 blok × 100000 = 5000 (B narxi). A niki 20000.
    check("get_order_item_unit_cost(B) — B penoplasti narxi: 5000",
          abs(uc - 5000) < 1e-6, f"{uc}")
    before, b0 = a_state(), stock(B1)
    with contextlib.redirect_stdout(_quiet):
        services.return_inventory_for_order(db, bo)
    check("return_inventory_for_order(B) — A ombori O'ZGARMADI",
          a_state() == before)
    check("return_inventory_for_order(B) — B ga +0.5 blok qaytdi",
          abs((stock(B1) - b0) - 0.5) < 1e-6, f"{b0} → {stock(B1)}")
    before = a_state()
    with contextlib.redirect_stdout(_quiet):
        services.adjust_inventory_diff(db, [], [dict(PANEL, name="x")],
                                       order_id=B_ORDER_ID)
    check("adjust_inventory_diff(B buyurtmasi) — A ombori O'ZGARMADI",
          a_state() == before)
else:
    check("B buyurtmasi yaratildi (ichki funksiyalar uchun)", False)

# ══════════════════════════════════════════════════════════════
section("3. A→A: A ning o'z asosiy penoplasti ishlaydi")
# ══════════════════════════════════════════════════════════════
a0 = stock(A1)
r = A.post("/api/orders?confirm_shortage=true",
           json=order_body(A_PROJ, "AAA_Panel"))
check("A buyurtma — 2xx", 200 <= r.status_code < 300, f"HTTP {r.status_code}")
check("A buyurtma — O'Z asosiysidan (A1): 1.0 m³ / 1.0 = -1.0 blok",
      abs((a0 - stock(A1)) - 1.0) < 1e-6, f"{a0} → {stock(A1)}")

r = A.post(f"/api/inventory/{A2.id}/set-default-penoplast")
db.expire_all()
check("A set-default A2 — A2 asosiy, A1 emas, B1 tegilmagan",
      r.status_code == 200 and db.get(Inventory, A2.id).is_default_penoplast
      and not db.get(Inventory, A1.id).is_default_penoplast
      and db.get(Inventory, B1.id).is_default_penoplast,
      f"HTTP {r.status_code}")
a0 = stock(A2)
r = A.post("/api/orders?confirm_shortage=true",
           json=order_body(A_PROJ, "AAA_Panel_2", quantity=5))
check("A buyurtma — YANGI asosiysidan (A2): 0.5 m³ / 0.5 = -1.0 blok",
      abs((a0 - stock(A2)) - 1.0) < 1e-6, f"{a0} → {stock(A2)}")
r = A.get("/api/penoplasts").json()
check("A /api/penoplasts — faqat A, default = A2",
      sorted(i["name"] for i in r["items"]) == ["AAA_PENO_ASOSIY", "AAA_PENO_IKKINCHI"]
      and r["default_id"] == A2.id, str(r)[:200])

# O'chirilgan penoplastni qayta qo'shib asosiy qilish (asl kodda O'LCHANGAN:
# korxonada birorta ham asosiy qolmasdi). B da — A ga tegmasligi ham ko'rinadi.
_old = Inventory(company_id=2, item_name="BBB_PENO_ESKI", unit="blok",
                 stock_quantity=0, price_per_unit=1, volume_per_unit=1,
                 is_penoplast=True, is_default_penoplast=True, is_deleted=True)
db.add(_old)
db.commit()
before = a_state()
with contextlib.redirect_stdout(_quiet):
    _r = crud.add_item(db, schemas.InventoryCreate(
        item_name="BBB_PENO_ESKI", unit="blok", stock_quantity=10,
        price_per_unit=1, volume_per_unit=1, is_penoplast=True,
        is_default_penoplast=True), company_id=2)
db.expire_all()
_bdef = [i.id for i in db.query(Inventory).filter(
    Inventory.company_id == 2, Inventory.is_default_penoplast == True)]
check("qayta tiklangan penoplast asosiy qilindi — B da AYNAN u asosiy",
      _r.id == _old.id and _bdef == [_old.id], f"{_r.id} / {_bdef}")
check("qayta tiklash (B) — A ombori/belgisi O'ZGARMADI", a_state() == before)

# ══════════════════════════════════════════════════════════════
section("4. Himoya filtr ostida — begona havola rad etiladi")
# ══════════════════════════════════════════════════════════════
# Filtrni majburan yoqamiz: bu qulf `TENANT_FILTER=0` ishga tushirishda ham
# faol bo'lsin (ko'rlik aynan filtr yoqilganda paydo bo'ladi).
_prev_enabled = _tc.ENABLED
_tc.ENABLED = True
s = SessionLocal()
try:
    _tc.set_current_company(s, 2)
    bo2 = s.query(Order).filter(Order.company_id == 2).first()
    check("filtr ostida A penoplasti B ga ko'rinmaydi (shart to'g'ri qo'yilgan)",
          s.query(Inventory).filter(Inventory.id == A2.id).first() is None)
    s.add(OrderItem(order_id=bo2.id, company_id=2, name="BBB_guard",
                    category="panel", quantity=1, penoplast_id=A2.id))
    try:
        s.flush()
        rejected = False
    except TenantMismatchError:
        rejected = True
    s.rollback()
    check("filtr YONIQ: B detali + A penoplast_id — TenantMismatchError",
          rejected)
    _tc.set_current_company(s, 2)
    s.add(OrderItem(order_id=bo2.id, company_id=2, name="BBB_guard_ok",
                    category="panel", quantity=1, penoplast_id=B1.id))
    try:
        s.flush()
        ok_own = True
    except TenantMismatchError:
        ok_own = False
    s.rollback()
    check("filtr YONIQ: B detali + O'Z penoplasti — o'tadi", ok_own)
finally:
    s.close()
    _tc.ENABLED = _prev_enabled

# ══════════════════════════════════════════════════════════════
section("5. Ildiz funksiyalar")
# ══════════════════════════════════════════════════════════════
check("get_default_penoplast(korxona NOMA'LUM) → None — zaxira YO'Q",
      services.get_default_penoplast(db) is None)
check("get_penoplast_list(korxona NOMA'LUM) → []",
      services.get_penoplast_list(db) == [])
# 3-bo'limda B ning asosiysi ataylab BBB_PENO_ESKI ga almashtirilgan.
check("get_default_penoplast(company_id=2) → B ning joriy asosiysi",
      getattr(services.get_default_penoplast(db, company_id=2), "id", None) == _old.id)
check("get_default_penoplast(company_id=1) → A ning joriy asosiysi (A2)",
      getattr(services.get_default_penoplast(db, company_id=1), "id", None) == A2.id)
check("_peno_of(A2, company_id=2) → None",
      services._peno_of(db, A2.id, 2) is None)

print("\n" + "=" * 66)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print(f"tenant_context statistikasi: {_tc.get_stats()}")
print("=" * 66)
if FAILED:
    for f in FAILED:
        print("  \u2717 " + f)
sys.exit(1 if FAIL else 0)
