#!/usr/bin/env python3
"""
test_fp_product_type.py — Bosqich 3, 10-band tekshiruvi.

NIMA TEKSHIRILADI
-----------------
`finished_products.product_type_id` — tayyor mahsulot qaysi mahsulot
TURIDAN ekani. 12-band (liniya bo'yicha moliya) shu ustunga tayanadi,
shuning uchun u to'g'ri to'lishi va noto'g'ri to'lmasligi kerak.

  A. MRP ishlab chiqarish — turni tayyor mahsulotga YOZADI
  B. Eski turkumlar (profil/panel/...) — NULL bo'lib qoladi (ataylab)
  C. Buyurtma detalidan qaytarish — turni olib keladi
  D. Birlashtirish — ikki xil tur BITTA yozuvga qo'shilib ketmaydi
  E. Tenant qo'riqchisi — boshqa korxonaning turiga bog'lab bo'lmaydi
  F. Backfill so'rovi — `production_orders` orqali aniq ishlaydi
  G. Zaxira (backup) — yangi ustun eksportga tushadi

ISHLATISH
---------
    python tools/test_fp_product_type.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "fp_product_type_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import main  # noqa: E402,F401
from sqlalchemy import event, text  # noqa: E402
from database import SessionLocal, engine  # noqa: E402


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


engine.dispose()

import crud  # noqa: E402
from production_models import Company, ProductType, BOM, ProductionOrder  # noqa: E402
from models import (  # noqa: E402
    FinishedProduct, StockSource, Project, Order, OrderItem, OrderType,
    ProjectStatus, TenantMismatchError,
)

db = SessionLocal()
OK = FAIL = 0
FAILED = []


def check(label, cond):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}")


def bolim(t):
    print(f"\n{'=' * 62}\n{t}\n{'=' * 62}")


# ── Baza ────────────────────────────────────────────────────────
for cid, nom in ((1, "A_KORXONA"), (2, "B_KORXONA")):
    if not db.query(Company).filter(Company.id == cid).first():
        db.add(Company(id=cid, name=nom))
db.flush()

tur_a = ProductType(company_id=1, name="A turi", unit="kg",
                    input_template="quantity_only", pricing_formula="unit_based")
tur_b = ProductType(company_id=2, name="B turi", unit="kg",
                    input_template="quantity_only", pricing_formula="unit_based")
db.add_all([tur_a, tur_b])
db.flush()

loyiha = Project(company_id=1, project_number="PRJ-FP", client_name="Sinov",
                 project_name="Sinov", status=ProjectStatus.DRAFT)
db.add(loyiha)
db.flush()
db.commit()


# ════════════════════════════════════════════════════════════════
bolim("A. Ustun mavjudligi va standart qiymati")
# ════════════════════════════════════════════════════════════════
ustunlar = {c["name"] for c in __import__("sqlalchemy").inspect(engine)
            .get_columns("finished_products")}
check("finished_products.product_type_id ustuni bor",
      "product_type_id" in ustunlar)

fp_bosh = FinishedProduct(company_id=1, name="Eski usul", category="profil",
                          quantity=10, produced_quantity=10, unit="metr",
                          unit_price=1000, cost_price=0,
                          source=StockSource.PRODUCED)
db.add(fp_bosh)
db.commit()
check("eski turkum (profil) — turi NULL bo'lib qoladi (ATAYLAB)",
      fp_bosh.product_type_id is None)


# ════════════════════════════════════════════════════════════════
bolim("B. MRP ishlab chiqarish turni yozadimi")
# ════════════════════════════════════════════════════════════════
fp_mrp = FinishedProduct(company_id=1, name="A turi", category="dynamic_bom",
                         quantity=20, produced_quantity=20, unit="kg",
                         unit_price=0, cost_price=0,
                         source=StockSource.PRODUCED,
                         product_type_id=tur_a.id)
db.add(fp_mrp)
db.commit()
db.refresh(fp_mrp)
check("MRP mahsuloti — turi saqlandi", fp_mrp.product_type_id == tur_a.id)
check("bog'lam obyekt sifatida ham ochiladi",
      fp_mrp.product_type is not None and fp_mrp.product_type.name == "A turi")


# ════════════════════════════════════════════════════════════════
bolim("C. Buyurtma detalidan qaytarish turni olib keladimi")
# ════════════════════════════════════════════════════════════════
o = Order(company_id=1, order_number="FP-001", project_id=loyiha.id,
          order_type=OrderType.PRODUCT, total_amount=100000,
          agreed_amount=100000)
db.add(o)
db.flush()
it_mrp = OrderItem(company_id=1, order_id=o.id, name="MRP detal",
                   category="mrp_product", quantity=10, unit_price=5000,
                   total_price=50000, is_coated=False,
                   product_type_id=tur_a.id)
it_eski = OrderItem(company_id=1, order_id=o.id, name="Eski detal",
                    category="panel", width=50, thickness=2, quantity=10,
                    unit_price=5000, total_price=50000, is_coated=False)
db.add_all([it_mrp, it_eski])
db.commit()

fp1 = crud.add_returned_to_stock(db, it_mrp, 3, "Ortiqcha")
check("MRP detali qaytarildi — turi ko'chdi",
      fp1.product_type_id == tur_a.id)
fp2 = crud.add_returned_to_stock(db, it_eski, 3, "Ortiqcha")
check("eski detal qaytarildi — turi NULL", fp2.product_type_id is None)


# ════════════════════════════════════════════════════════════════
bolim("D. Birlashtirish — ikki xil tur qo'shilib ketmaydimi")
# ════════════════════════════════════════════════════════════════
oldingi = fp1.id
fp1b = crud.add_returned_to_stock(db, it_mrp, 2, "Ortiqcha")
check("bir xil tur — o'sha yozuvga qo'shildi", fp1b.id == oldingi)
check("miqdori jamlandi", float(fp1b.quantity) == 5.0)

# Nomi/o'lchami/narxi AYNAN bir xil, lekin turi boshqa detal
it_boshqa = OrderItem(company_id=1, order_id=o.id, name="MRP detal",
                      category="panel", quantity=10, unit_price=5000,
                      total_price=50000, is_coated=False)
db.add(it_boshqa)
db.commit()
fp3 = crud.add_returned_to_stock(db, it_boshqa, 4, "Ortiqcha")
check("turi BOSHQA (NULL) — ALOHIDA yozuv yaratildi", fp3.id != oldingi)
check("eski yozuvning miqdori o'zgarmadi", float(fp1b.quantity) == 5.0)


# ════════════════════════════════════════════════════════════════
bolim("E. Tenant qo'riqchisi — boshqa korxonaning turi")
# ════════════════════════════════════════════════════════════════
rad_etildi = False
try:
    yomon = FinishedProduct(company_id=1, name="O'g'irlangan tur",
                            category="dynamic_bom", quantity=1,
                            produced_quantity=1, unit="kg", unit_price=0,
                            cost_price=0, source=StockSource.PRODUCED,
                            product_type_id=tur_b.id)   # B korxonaning turi!
    db.add(yomon)
    db.commit()
except TenantMismatchError:
    db.rollback()
    rad_etildi = True
except Exception:
    db.rollback()
check("A korxona B korxonaning turiga bog'lay OLMAYDI", rad_etildi)

# O'z korxonasining turi — ishlashi SHART
yaxshi = FinishedProduct(company_id=2, name="B mahsuloti",
                         category="dynamic_bom", quantity=1,
                         produced_quantity=1, unit="kg", unit_price=0,
                         cost_price=0, source=StockSource.PRODUCED,
                         product_type_id=tur_b.id)
db.add(yaxshi)
db.commit()
check("B korxona O'Z turiga bog'lay OLADI", yaxshi.product_type_id == tur_b.id)


# ════════════════════════════════════════════════════════════════
bolim("F. Backfill so'rovi — production_orders orqali")
# ════════════════════════════════════════════════════════════════
fp_null = FinishedProduct(company_id=1, name="Turi yo'q", category="dynamic_bom",
                          quantity=7, produced_quantity=7, unit="kg",
                          unit_price=0, cost_price=0,
                          source=StockSource.PRODUCED)
db.add(fp_null)
db.flush()
bom_a = BOM(company_id=1, product_type_id=tur_a.id, variant_name="Standart",
            batch_quantity=1)
db.add(bom_a)
db.flush()
po = ProductionOrder(company_id=1, product_type_id=tur_a.id, bom_id=bom_a.id,
                     quantity=7, status="completed",
                     finished_product_id=fp_null.id, source_type="to_stock")
db.add(po)
db.commit()

nomzod = db.execute(text(
    "SELECT COUNT(*) FROM finished_products f "
    "JOIN production_orders p ON p.finished_product_id = f.id "
    "WHERE f.product_type_id IS NULL AND p.product_type_id IS NOT NULL"
)).scalar()
check("SANASH: to'ldiriladigan 1 ta yozuv topildi", nomzod == 1)

# SQLite `UPDATE ... FROM` ni qo'llab-quvvatlamaydi, shuning uchun bu yerda
# bir xil natija beradigan subquery shakli ishlatiladi. Postgres'dagi
# migratsiya `UPDATE ... FROM` bilan yozilgan — mantiq AYNAN bir xil.
db.execute(text(
    "UPDATE finished_products SET product_type_id = ("
    "  SELECT p.product_type_id FROM production_orders p "
    "  WHERE p.finished_product_id = finished_products.id "
    "    AND p.product_type_id IS NOT NULL LIMIT 1) "
    "WHERE product_type_id IS NULL AND id IN ("
    "  SELECT finished_product_id FROM production_orders "
    "  WHERE finished_product_id IS NOT NULL AND product_type_id IS NOT NULL)"))
db.commit()
db.refresh(fp_null)
check("TO'LDIRISH: turi production_order dan olindi",
      fp_null.product_type_id == tur_a.id)
db.refresh(fp_bosh)
check("eski turkum yozuviga TEGILMADI (hamon NULL)",
      fp_bosh.product_type_id is None)

qoldi = db.execute(text(
    "SELECT COUNT(*) FROM finished_products f "
    "JOIN production_orders p ON p.finished_product_id = f.id "
    "WHERE f.product_type_id IS NULL AND p.product_type_id IS NOT NULL"
)).scalar()
check("takroriy ishga tushirilsa — to'ldiradigan narsa qolmadi", qoldi == 0)

chalkash = db.execute(text(
    "SELECT COUNT(*) FROM finished_products f "
    "JOIN product_types t ON t.id = f.product_type_id "
    "WHERE f.company_id IS NOT t.company_id")).scalar()
check("NAZORAT: boshqa korxonaning turiga ishora qiluvchi yozuv yo'q",
      chalkash == 0)


# ════════════════════════════════════════════════════════════════
bolim("G. Zaxira (backup) yangi ustunni oladimi")
# ════════════════════════════════════════════════════════════════
zax = crud.export_full_backup(db, company_id=1)
fp_jadval = zax["tables"].get("finished_products", [])
check("zaxirada finished_products bor", len(fp_jadval) > 0)
check("zaxira qatorida product_type_id maydoni bor",
      all("product_type_id" in r for r in fp_jadval))
turli = [r for r in fp_jadval if r.get("product_type_id")]
check("turi bor yozuvlar zaxirada ham turi bilan", len(turli) >= 2)
check("faqat A korxona yozuvlari (tenant)",
      all(r.get("company_id") == 1 for r in fp_jadval))


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 62}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 62}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 62)
sys.exit(0 if FAIL == 0 else 1)
