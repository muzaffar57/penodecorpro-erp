#!/usr/bin/env python3
"""
test_loy_tenant.py — loy (qoplama) retsepti bo'yicha korxonalararo darvoza.

NIMA UCHUN KERAK
----------------
2026-09-21 da O'LCHANGAN sizish: retsept qidiruvi kamida 5 joyda
`db.query(Recipe).first()` bilan tugardi — butun bazadagi birinchi
retsept, ya'ni BOSHQA korxonaniki. Ingredientlar retseptning ichidan
(`recipe.ingredients` → `ing.inventory_id`) olingani uchun, begona
retsept = begona OMBOR. Retsepti hali yo'q YANGI korxona (B) loy
ishlatganda A korxonaning omboridan xomashyo ayirilardi.

Bu `test_idor.py` dan boshqa shakl: u yerda B A ning yozuviga ID bilan
uriladi. Bu yerda B faqat O'Z yozuvi ustida ishlaydi — sizish esa
ichkarida, retsept tanlashda yuz beradi. Shuning uchun IDOR problari
buni ko'rmaydi.

Himoya bitta joyda: `services.resolve_recipe()`. Korxona aniqlanmasa,
"birinchi retsept" zaxira yo'li umuman ishlamaydi.

QAMROV
------
1. HTTP (haqiqiy login, haqiqiy cookie) — B ning 7 ta amali A ning
   omborini o'zgartirmasligi (butun A ombori holati solishtiriladi,
   faqat bitta qator emas).
2. A→A — tuzatma A ning O'Z ishini buzmaganini isbotlash: retseptsiz
   mahsulotda A hamon O'Z retseptiga qaytadi va AYNAN kutilgan miqdorni
   ayiradi.
3. Ildiz qo'riqchisi — `resolve_recipe` / `get_loy_cost_per_kg` ga
   to'g'ridan-to'g'ri murojaat.

`TENANT_FILTER=0` da ham o'tishi SHART: `main` da filtr hali yo'q,
himoya filtrga tayanmasligi kerak.

ISHLATISH
---------
    python tools/test_loy_tenant.py
    TENANT_FILTER=1 python tools/test_loy_tenant.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "loy_tenant_test.db")
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
    UserRole, Inventory, Recipe, RecipeIngredient, FinishedProduct,
    StockSource,
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


def make_fp(cid, name, peno_id):
    """Retseptsiz (recipe_id=None), qoplamali, ishlab chiqarilgan profil.
    1 metrga: 0.1 m³ penoplast, 1 kg loy."""
    fp = FinishedProduct(
        company_id=cid, name=name, category="profil", unit="metr",
        quantity=10.0, produced_quantity=10.0, source=StockSource.PRODUCED,
        penoplast_id=peno_id, volume_m3=1.0, unit_volume_m3=0.1,
        actual_loy_kg=10.0, unit_loy_kg=1.0, recipe_id=None,
        unit_price=50000, cost_price=100000,
    )
    db.add(fp)
    db.commit()
    return fp


with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "AAA_user", "Parol123!", UserRole.ADMIN, "AAA",
                     company_id=1)
    auth.create_user(db, "BBB_user", "Parol123!", UserRole.ADMIN, "BBB",
                     company_id=2)

# A: retsept (100 kg partiyaga 50 kg sement) + penoplast
A_SEMENT = Inventory(company_id=1, item_name="AAA_SEMENT", unit="kg",
                     stock_quantity=1000.0, price_per_unit=5000)
A_PENO = Inventory(company_id=1, item_name="AAA_PENOPLAST", unit="blok",
                   stock_quantity=100.0, price_per_unit=200000,
                   volume_per_unit=1.0)
db.add_all([A_SEMENT, A_PENO])
db.commit()
A_REC = Recipe(company_id=1, name="AAA_RETSEPT", batch_size_kg=100.0)
db.add(A_REC)
db.commit()
db.add(RecipeIngredient(recipe_id=A_REC.id, inventory_id=A_SEMENT.id,
                        quantity_kg=50.0))
db.commit()
A_FP = make_fp(1, "AAA_PROFIL", A_PENO.id)

# B: penoplast bor, RETSEPT YO'Q (yangi mijozning birinchi kuni)
B_PENO = Inventory(company_id=2, item_name="BBB_PENOPLAST", unit="blok",
                   stock_quantity=100.0, price_per_unit=200000,
                   volume_per_unit=1.0)
db.add(B_PENO)
db.commit()
B_FPS = [make_fp(2, f"BBB_PROFIL{k}", B_PENO.id) for k in range(3)]
with contextlib.redirect_stdout(_quiet):
    B_PROJ = crud.create_project(db, schemas.ProjectCreate(
        project_name="BBB_L", client_name="BBB_Mijoz"), company_id=2)

assert db.query(Recipe).filter(Recipe.company_id == 2).count() == 0


def a_state():
    """A korxonaning BUTUN ombori: {id: (nom, qoldiq)} + pozitsiyalar soni.
    Bitta qatorni emas, hammasini solishtiramiz — "Tayyor loy (...)" kabi
    yashirincha yaratiladigan pozitsiyalar ham ushlanishi uchun."""
    db.expire_all()
    rows = db.query(Inventory).filter(Inventory.company_id == 1).all()
    return {r.id: (r.item_name, round(float(r.stock_quantity or 0), 6))
            for r in rows}


def login(user):
    c = TestClient(main.app, base_url="https://testserver")
    r = c.post("/login", data={"username": user, "password": "Parol123!"},
               follow_redirects=False)
    assert r.status_code == 302, f"{user} login bo'lmadi: {r.status_code}"
    assert "session_token" in c.cookies
    return c


B = login("BBB_user")
A = login("AAA_user")

print("=" * 66)
print("LOY/RETSEPT DARVOZASI — B o'z amali bilan A omboriga tegadimi")
print("TENANT_FILTER = " + ("1 (YOQILGAN)" if _tc.ENABLED else "0 (o'chiq)"))
print("=" * 66)


def probe(label, fn):
    """B ning amali: A ombori holati OLDIN == KEYIN bo'lishi shart.
    Amal o'zi muvaffaqiyatli bo'lishi ham tekshiriladi — aks holda
    "hech narsa o'zgarmadi" shunchaki so'rov yetib bormagani bo'lishi
    mumkin (test_idor dagi 422 saboqi)."""
    before = a_state()
    r = fn()
    after = a_state()
    changed = {k: (before.get(k), after.get(k))
               for k in set(before) | set(after) if before.get(k) != after.get(k)}
    check(f"{label} — so'rov bajarildi (2xx)", 200 <= r.status_code < 300,
          f"HTTP {r.status_code}: {r.text[:160]}")
    check(f"{label} — A ombori O'ZGARMADI", not changed, f"o'zgardi: {changed}")
    return r


# ══════════════════════════════════════════════════════════════
section("1. HTTP: B ning o'z amallari (retsepti yo'q)")
# ══════════════════════════════════════════════════════════════
probe("POST /api/finished/{id}/add (+10 metr)",
      lambda: B.post(f"/api/finished/{B_FPS[0].id}/add",
                     json={"quantity": 10}))

probe("POST /api/finished/production-brak (5 birlik)",
      lambda: B.post("/api/finished/production-brak",
                     json={"finished_product_id": B_FPS[1].id,
                           "brak_qty": 5}))

probe("POST /api/finished/produce (loy 20 kg, retseptsiz)",
      lambda: B.post("/api/finished/produce",
                     json={"name": "BBB_YANGI", "category": "profil",
                           "width": 10, "thickness": 10, "length": 10,
                           "penoplast_id": B_PENO.id, "loy_kg": 20,
                           "unit_price": 1000}))

probe("POST /api/orders (umumiy qoplama loy_kg=30)",
      lambda: B.post("/api/orders?loy_kg=30&confirm_shortage=true",
                     json={"project_id": B_PROJ.id, "order_type": "product",
                           "loy_kg": 30,
                           "items": [{"name": "BBB_Detal", "category": "panel",
                                      "quantity": 1, "unit_price": 100000,
                                      "is_coated": True}]}))

# A ning retsept ID sini B o'zi aniq ko'rsatsa — rad etilishi yoki
# e'tiborsiz qoldirilishi kerak, lekin A omboriga tegmasligi SHART.
_before = a_state()
r = B.post("/api/finished/produce",
           json={"name": "BBB_BEGONA", "category": "profil",
                 "width": 10, "thickness": 10, "length": 10,
                 "penoplast_id": B_PENO.id, "loy_kg": 20,
                 "recipe_id": A_REC.id, "unit_price": 1000})
check("produce + A ning recipe_id si — A ombori O'ZGARMADI",
      a_state() == _before, f"HTTP {r.status_code}")
check("produce + A ning recipe_id si — javobda A retsepti yo'q",
      "AAA" not in r.text, r.text[:200])

r = B.get(f"/api/finished/{B_FPS[2].id}/profit")
check("GET /api/finished/{id}/profit — 200", r.status_code == 200,
      f"HTTP {r.status_code}")
check("GET /api/finished/{id}/profit — A retsepti nomi yo'q",
      "AAA" not in r.text, r.text[:200])

r = B.get("/api/loy-cost")
check("GET /api/loy-cost — A retsepti yo'q",
      r.status_code in (200, 404) and "AAA" not in r.text,
      f"HTTP {r.status_code}: {r.text[:160]}")

# ══════════════════════════════════════════════════════════════
section("2. A→A: tuzatma A ning O'Z ishini buzmadi")
# ══════════════════════════════════════════════════════════════
# +10 metr × 1 kg/metr = 10 kg loy; partiya 100 kg ga 50 kg sement
# → 10 × 50/100 = 5 kg sement AYNAN ayirilishi kerak.
db.expire_all()
s0 = float(db.get(Inventory, A_SEMENT.id).stock_quantity)
r = A.post(f"/api/finished/{A_FP.id}/add", json={"quantity": 10})
db.expire_all()
s1 = float(db.get(Inventory, A_SEMENT.id).stock_quantity)
check("A /add — 2xx", 200 <= r.status_code < 300, f"HTTP {r.status_code}")
check("A retseptsiz mahsulotda O'Z retseptiga qaytadi: -5.000 kg sement",
      abs((s0 - s1) - 5.0) < 1e-6, f"{s0} → {s1} (farq {s0 - s1})")

r = A.get(f"/api/finished/{A_FP.id}/profit")
check("A foyda hisobotida O'Z retsepti ko'rinadi",
      r.status_code == 200 and "AAA_RETSEPT" in r.text, r.text[:200])

# ══════════════════════════════════════════════════════════════
section("3. Ildiz qo'riqchisi: services.resolve_recipe")
# ══════════════════════════════════════════════════════════════
check("resolve_recipe(A_rec, company_id=2) → None",
      services.resolve_recipe(db, recipe_id=A_REC.id, company_id=2) is None)
check("resolve_recipe(company_id=2) → None (B da retsept yo'q)",
      services.resolve_recipe(db, company_id=2) is None)
check("resolve_recipe(korxona NOMA'LUM, id yo'q) → None — zaxira YO'Q",
      services.resolve_recipe(db) is None)
check("resolve_recipe(company_id=1) → A retsepti (zaxira ishlaydi)",
      getattr(services.resolve_recipe(db, company_id=1), "id", None) == A_REC.id)
check("get_loy_cost_per_kg(None) korxonasiz — A retseptini bermaydi",
      services.get_loy_cost_per_kg(db, None).get("recipe") is None)


class _Fake:
    company_id = 2
    items = []


check("resolve_recipe(order.company_id=2) — buyurtmadan korxona olinadi",
      services.resolve_recipe(db, order=_Fake()) is None)

print("\n" + "=" * 66)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print(f"tenant_context statistikasi: {_tc.get_stats()}")
print("=" * 66)
if FAILED:
    for f in FAILED:
        print("  \u2717 " + f)
sys.exit(1 if FAIL else 0)
