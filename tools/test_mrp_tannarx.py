#!/usr/bin/env python3
"""
test_mrp_tannarx.py — MRP xarajati buyurtma foydasiga yetib boradimi.

NIMA UCHUN YOZILDI
------------------
2026-09-20, staging'dagi jonli sinovda topildi: 100 m² travertin
buyurtmasi MRP orqali ishlab chiqarildi, xomashyoga 8 144 736.86 so'm
ketdi — lekin buyurtma foydasi `tan narx = 0`, `foyda = 18 000 000`
ya'ni 100% marja ko'rsatdi. Sentabr sof foydasi zarardan foydaga
"o'tib" ketdi.

Sabab: MRP tayyor mahsulotni buyurtma detaliga
`FinishedProduct.reserved_for_order_item_id` orqali bog'laydi, lekin
foyda hisobi faqat `order_item.finished_product_id` ga qarardi.
Ikkalasi hech qayerda uchrashmasdi.

  A. MRP band qilgan mahsulotning tan narxi buyurtmaga qo'shiladi
  B. Qisman ishlab chiqarish — faqat band qilingan qismi
  C. Bir detalga ikkita ishlab chiqarish — ikkalasi ham qo'shiladi
  D. Bog'lanmagan (omborga ishlangan) mahsulot — QO'SHILMAYDI
  E. Eski yo'l (finished_product_id) buzilmagan
  F. Ikki marta hisoblanmaydi
  G. Tenant — boshqa korxonaning mahsuloti olinmaydi

ISHLATISH
---------
    python tools/test_mrp_tannarx.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "mrp_tannarx_test.db")
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

import services  # noqa: E402
from production_models import Company, ProductType  # noqa: E402
from models import (  # noqa: E402
    FinishedProduct, StockSource, Project, Order, OrderItem, OrderType,
    ProjectStatus,
)

db = SessionLocal()
OK = FAIL = 0
FAILED = []


def check(label, olingan, kutilgan, atol=0.01):
    global OK, FAIL
    if abs(float(olingan) - float(kutilgan)) <= atol:
        OK += 1
        print(f"  \u2713 {label}  = {olingan}")
    else:
        FAIL += 1
        FAILED.append(f"{label}: {olingan} != {kutilgan}")
        print(f"  \u2717 {label}  olingan={olingan}  KUTILGAN={kutilgan}")


def bolim(t):
    print(f"\n{'=' * 62}\n{t}\n{'=' * 62}")


for cid, nom in ((1, "A"), (2, "B")):
    if not db.query(Company).filter(Company.id == cid).first():
        db.add(Company(id=cid, name=nom))
db.flush()
tur = ProductType(company_id=1, name="Travertin 25x50", unit="m2",
                  input_template="area_2d", pricing_formula="unit_based")
tur_b = ProductType(company_id=2, name="Travertin 25x50", unit="m2",
                    input_template="area_2d", pricing_formula="unit_based")
db.add_all([tur, tur_b])
db.flush()
loyiha = Project(company_id=1, project_number="PRJ-M", client_name="S",
                 project_name="S", status=ProjectStatus.DRAFT)
db.add(loyiha)
db.commit()

_n = [0]


def buyurtma(miqdor=100, narx=180000, cid=1):
    _n[0] += 1
    o = Order(company_id=cid, order_number=f"M-{_n[0]:03d}", project_id=loyiha.id,
              order_type=OrderType.PRODUCT, total_amount=miqdor * narx,
              agreed_amount=miqdor * narx)
    db.add(o)
    db.flush()
    it = OrderItem(company_id=cid, order_id=o.id, name="Travertin",
                   category="mrp_product", quantity=miqdor, unit_price=narx,
                   total_price=miqdor * narx, is_coated=False,
                   product_type_id=tur.id)
    db.add(it)
    db.commit()
    db.refresh(o)
    return o, it


def mahsulot(qty, cost, band_uchun=None, band_qty=None, cid=1):
    fp = FinishedProduct(
        company_id=cid, name="Travertin 25x50", category="dynamic_bom",
        quantity=qty, produced_quantity=qty, unit="m2", unit_price=0,
        cost_price=cost, source=StockSource.PRODUCED,
        product_type_id=(tur.id if cid == 1 else tur_b.id),
        reserved_for_order_item_id=(band_uchun.id if band_uchun else None),
        reserved_quantity=(band_qty if band_qty is not None else (qty if band_uchun else 0)))
    db.add(fp)
    db.commit()
    return fp


# ════════════════════════════════════════════════════════════════
bolim("A. MRP band qilgan mahsulot — tan narxi qo'shiladi")
# ════════════════════════════════════════════════════════════════
o1, it1 = buyurtma(100, 180000)
mahsulot(100, 8_144_736.86, band_uchun=it1)
r = services.calculate_order_profit(db, o1.id, company_id=1)
check("A tan narxi = ishlab chiqarish xarajati", r["tan_narxi"], 8_144_736.86)
check("A sotuv narxi", r["sotuv_narxi"], 18_000_000)
check("A foyda = 18 000 000 - 8 144 736.86", r["foyda"], 9_855_263.14)
_q = [b for b in r["breakdown"] if "Tayyor mahsulot" in str(b["nomi"])]
check("A breakdown'da alohida qator bor", len(_q), 1)


# ════════════════════════════════════════════════════════════════
bolim("B. Qisman ishlab chiqarish — faqat band qilingan qism")
# ════════════════════════════════════════════════════════════════
o2, it2 = buyurtma(100, 180000)
# 100 m² ishlab chiqarildi, lekin shu detalga faqat 60 m² band
mahsulot(100, 1_000_000, band_uchun=it2, band_qty=60)
r = services.calculate_order_profit(db, o2.id, company_id=1)
check("B tan narx = 1 000 000 / 100 x 60", r["tan_narxi"], 600_000)


# ════════════════════════════════════════════════════════════════
bolim("C. Bitta detalga ikkita ishlab chiqarish")
# ════════════════════════════════════════════════════════════════
o3, it3 = buyurtma(100, 180000)
mahsulot(60, 600_000, band_uchun=it3, band_qty=60)
mahsulot(40, 500_000, band_uchun=it3, band_qty=40)
r = services.calculate_order_profit(db, o3.id, company_id=1)
check("C ikkala partiya ham qo'shildi", r["tan_narxi"], 1_100_000)


# ════════════════════════════════════════════════════════════════
bolim("D. Omborga ishlab chiqarilgan (bog'lanmagan) — qo'shilmaydi")
# ════════════════════════════════════════════════════════════════
o4, it4 = buyurtma(100, 180000)
mahsulot(100, 9_999_999, band_uchun=None)   # hech kimga band emas
r = services.calculate_order_profit(db, o4.id, company_id=1)
check("D bog'lanmagan mahsulot tan narxga qo'shilmadi", r["tan_narxi"], 0)


# ════════════════════════════════════════════════════════════════
bolim("E+F. Eski yo'l buzilmagan, ikki marta hisoblanmaydi")
# ════════════════════════════════════════════════════════════════
o5, it5 = buyurtma(10, 50000)
fp5 = mahsulot(10, 400_000, band_uchun=None)
it5.finished_product_id = fp5.id      # ESKI, to'g'ridan-to'g'ri bog'lam
db.commit()
r = services.calculate_order_profit(db, o5.id, company_id=1)
check("E eski bog'lam orqali tan narx", r["tan_narxi"], 400_000)

# Ikkala bog'lam ham bo'lsa — FAQAT bittasi hisoblanadi
o6, it6 = buyurtma(10, 50000)
fp6 = mahsulot(10, 700_000, band_uchun=it6)
it6.finished_product_id = fp6.id
db.commit()
r = services.calculate_order_profit(db, o6.id, company_id=1)
check("F ikkala bog'lam bor — bir marta hisoblandi", r["tan_narxi"], 700_000)


# ════════════════════════════════════════════════════════════════
bolim("G. Tenant — boshqa korxonaning mahsuloti")
# ════════════════════════════════════════════════════════════════
o7, it7 = buyurtma(100, 180000)
# B korxonaning mahsuloti. Bandlik bog'lamini ORM qo'riqchisi rad etadi
# (bu ham to'g'ri himoya), shuning uchun "buzuq ma'lumot" holatini
# taqlid qilish uchun to'g'ridan-to'g'ri SQL bilan qo'yamiz — foyda
# hisobi bunday yozuvni ham OLMASLIGI kerak.
fp7 = mahsulot(100, 5_000_000, cid=2)
from sqlalchemy import text as _t
db.execute(_t("UPDATE finished_products SET reserved_for_order_item_id=:i, "
              "reserved_quantity=100 WHERE id=:f"), {"i": it7.id, "f": fp7.id})
db.commit()
r = services.calculate_order_profit(db, o7.id, company_id=1)
check("G boshqa korxonaning mahsuloti OLINMADI", r["tan_narxi"], 0)


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 62}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 62}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 62)
sys.exit(0 if FAIL == 0 else 1)
