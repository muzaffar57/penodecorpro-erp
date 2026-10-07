#!/usr/bin/env python3
"""
test_buyurtma_oqimi.py — buyurtmaning to'liq hayot sikli va OMBOR.

NIMA UCHUN YOZILDI
------------------
2026-09-20, 11.2a-band: termopanel kodini olib tashlayotganda uning
ortidagi "Loy sotish" bloki ham tasodifan o'chib ketdi
(`activate_draft_order` ichida). 512 ta mavjud test buni USHLAMADI —
chunki buyurtmaning `qoralama → jarayonga olish → tayyor → o'chirish`
yo'li bo'yicha ombor harakatini tekshiradigan test yo'q edi.

Shu test o'sha bo'shliqni yopadi. Har qadamda ombor AYNAN qancha
o'zgarganini o'lchaydi.

  A. Qoralama — omborga TEGILMAYDI
  B. Jarayonga olish — penoplast yechiladi
  C. Jarayonga olish — "Loy sotish" detali o'z retseptidan yechiladi
  D. "Tayyor" — qoplama loyi retsept bo'yicha yechiladi
  E. O'chirish — yetkazilmagan buyurtmada hammasi qaytadi

ISHLATISH
---------
    python tools/test_buyurtma_oqimi.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "buyurtma_oqimi_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import main  # noqa: E402,F401
from sqlalchemy import event  # noqa: E402
from database import SessionLocal, engine  # noqa: E402


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


engine.dispose()

import crud  # noqa: E402
import services  # noqa: E402
import schemas  # noqa: E402
from production_models import Company  # noqa: E402
from models import Inventory, Recipe, RecipeIngredient, Project, ProjectStatus  # noqa: E402

db = SessionLocal()
CID = 1
OK = FAIL = 0
FAILED = []


def check(label, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label + (" " + extra if extra else ""))
        print(f"  \u2717 {label}  {extra}")


def bolim(t):
    print(f"\n{'=' * 62}\n{t}\n{'=' * 62}")


# ── Baza: penoplast + "Oq marmar" retsepti (haqiqiy nisbatlar) ──
if not db.query(Company).filter(Company.id == CID).first():
    db.add(Company(id=CID, name="A"))
db.flush()

peno = Inventory(company_id=CID, item_name="Penoplast 14P", unit="dona",
                 stock_quantity=100, price_per_unit=802126.32,
                 volume_per_unit=1.4, is_penoplast=True, is_default_penoplast=True)
db.add(peno)
BATCH = 210.0
ING = [("Akril Toshkent", 18.0, 19595.3), ("Kroshka extra", 110.0, 645.0),
       ("Kroshka mel", 40.0, 565.0), ("Oddiy mel", 10.0, 522.0),
       ("Penogasitel", 0.25, 58000.0), ("Zagustitel", 0.7, 38000.0)]
inv = {}
for nom, _kg, narx in ING:
    it = Inventory(company_id=CID, item_name=nom, unit="kg", stock_quantity=1000,
                   price_per_unit=narx, volume_per_unit=1)
    db.add(it)
    db.flush()
    inv[nom] = it
retsept = Recipe(company_id=CID, name="Oq marmar", batch_size_kg=BATCH)
db.add(retsept)
db.flush()
for nom, kg, _n in ING:
    db.add(RecipeIngredient(recipe_id=retsept.id, inventory_id=inv[nom].id, quantity_kg=kg))
loyiha = Project(company_id=CID, project_number="PRJ-O", client_name="S",
                 project_name="S", status=ProjectStatus.DRAFT)
db.add(loyiha)
db.commit()


def qoldiq():
    db.expire_all()
    return {i.item_name: float(i.stock_quantity)
            for i in db.query(Inventory).filter(Inventory.company_id == CID).all()}


def farq(a, b):
    return {k: round(a[k] - b[k], 9) for k in a if abs(a[k] - b[k]) > 1e-9}


def loy_kutilgan(kg):
    return {nom: round(kg * q / BATCH, 9) for nom, q, _ in ING}


# ── Buyurtma: qoplamali profil + "Loy sotish" 20 kg ──────────────
buyurtma = schemas.OrderCreate(
    project_id=loyiha.id, order_type="product", is_draft=True,
    recipe_id=retsept.id,
    items=[
        schemas.OrderItemCreate(
            name="Qoplamali profil", category="profil", width=20, thickness=10,
            length=4, quantity=1, unit_price=800000, is_coated=True,
            penoplast_id=peno.id, recipe_id=retsept.id, price_per_m3=1100000),
        schemas.OrderItemCreate(
            name="Loy sotish", category="loy_sotish", quantity=20,
            unit_price=5000, is_coated=False, recipe_id=retsept.id),
    ])

# ════════════════════════════════════════════════════════════════
bolim("A. Qoralama — omborga tegilmaydi")
# ════════════════════════════════════════════════════════════════
A = qoldiq()
o = crud.create_order(db, buyurtma)
B = qoldiq()
check("qoralama yaratildi", o is not None)
check("ombor UMUMAN o'zgarmadi", farq(A, B) == {}, str(farq(A, B)))


# ════════════════════════════════════════════════════════════════
bolim("B+C. Jarayonga olish — penoplast VA loy sotish")
# ════════════════════════════════════════════════════════════════
B = qoldiq()
crud.activate_draft_order(db, o.id)
C = qoldiq()
d = farq(B, C)

# profil 20x10cm 4m -> 0.04 m3 -> 0.04/1.4 blok
check("penoplast yechildi (0.04 m3 / 1.4)",
      abs(d.get("Penoplast 14P", 0) - 0.04 / 1.4) < 1e-9,
      f"olingan={d.get('Penoplast 14P')}")

# "Loy sotish" 20 kg — retsept bo'yicha
kut = loy_kutilgan(20)
for nom, qiymat in kut.items():
    check(f"loy sotish: {nom} — {qiymat:g} kg",
          abs(d.get(nom, 0) - qiymat) < 1e-9,
          f"olingan={d.get(nom, 0)}")
check("⚠ LOY SOTISH BLOKI ISHLADI (11.2a da tasodifan o'chgan edi)",
      all(abs(d.get(n, 0) - v) < 1e-9 for n, v in kut.items()))


# ════════════════════════════════════════════════════════════════
bolim("D. 'Tayyor' — qoplama loyi")
# ════════════════════════════════════════════════════════════════
C = qoldiq()
r = services.complete_order(db, o.id, 8.0)
D = qoldiq()
d2 = farq(C, D)
check("yakunlandi", r.get("success") is True, str(r.get("message"))[:60])
kut2 = loy_kutilgan(8)
for nom, qiymat in kut2.items():
    check(f"qoplama loyi: {nom} — {qiymat:g} kg",
          abs(d2.get(nom, 0) - qiymat) < 1e-9,
          f"olingan={d2.get(nom, 0)}")
check("qoplamada penoplast QAYTA yechilmadi",
      abs(d2.get("Penoplast 14P", 0)) < 1e-9)


# ════════════════════════════════════════════════════════════════
bolim("E. O'chirish — yetkazilmagan buyurtmada hammasi qaytadi")
# ════════════════════════════════════════════════════════════════
# `main.py` dagi o'chirish endpointi aynan shu ikki funksiyani chaqiradi
# (yetkazilmagan buyurtma uchun), shuning uchun shu yerda ham shunday.
BOSH = qoldiq()
db.refresh(o)
services.return_inventory_for_order(db, o)
services.return_loy_ingredients(db, o, 8.0)
E = qoldiq()
d3 = farq(BOSH, E)
check("penoplast qaytdi",
      abs(d3.get("Penoplast 14P", 0) + 0.04 / 1.4) < 1e-9,
      f"olingan={d3.get('Penoplast 14P')}")
kut3 = loy_kutilgan(8)
for nom, qiymat in kut3.items():
    check(f"loy qaytdi: {nom} — {qiymat:g} kg",
          abs(-d3.get(nom, 0) - qiymat) < 1e-9,
          f"olingan={-d3.get(nom, 0)}")


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 62}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 62}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 62)
sys.exit(0 if FAIL == 0 else 1)
