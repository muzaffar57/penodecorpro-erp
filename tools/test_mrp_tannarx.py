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
  H. Yuk xati — tayyor mahsulot ombordan CHIQADI
  I. Yuk xatini o'chirish — QAYTADI (aynan simmetrik)
  J. Qisman topshirish — faqat topshirilgan qismi

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
from production_models import (  # noqa: E402
    Company, ProductType, BOM, ProductionOrder,
)
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


def ishlab_chiqarish(order_item, qty, cost, holat="completed", cid=1):
    """Yakunlangan ishlab chiqarish buyurtmasi — xarajatning BARQAROR manbai."""
    b = BOM(company_id=cid, product_type_id=(tur.id if cid == 1 else tur_b.id),
            variant_name=f"V{_n[0]}-{qty}", batch_quantity=1)
    db.add(b)
    db.flush()
    po = ProductionOrder(
        company_id=cid, product_type_id=(tur.id if cid == 1 else tur_b.id),
        bom_id=b.id, source_type="customer_order",
        source_order_item_id=(order_item.id if order_item else None),
        quantity=qty, status=holat, total_cost=cost, total_material_cost=cost)
    db.add(po)
    db.commit()
    return po


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
ishlab_chiqarish(it1, 100, 8_144_736.86)
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
# 100 m² buyurtma, lekin hozircha faqat 60 m² ishlab chiqarilgan
ishlab_chiqarish(it2, 60, 600_000)
r = services.calculate_order_profit(db, o2.id, company_id=1)
check("B faqat ishlab chiqarilgan qismning xarajati", r["tan_narxi"], 600_000)


# ════════════════════════════════════════════════════════════════
bolim("C. Bitta detalga ikkita ishlab chiqarish")
# ════════════════════════════════════════════════════════════════
o3, it3 = buyurtma(100, 180000)
ishlab_chiqarish(it3, 60, 600_000)
ishlab_chiqarish(it3, 40, 500_000)
r = services.calculate_order_profit(db, o3.id, company_id=1)
check("C ikkala partiya ham qo'shildi", r["tan_narxi"], 1_100_000)


# ════════════════════════════════════════════════════════════════
bolim("D. Omborga ishlab chiqarilgan (bog'lanmagan) — qo'shilmaydi")
# ════════════════════════════════════════════════════════════════
o4, it4 = buyurtma(100, 180000)
ishlab_chiqarish(None, 100, 9_999_999)        # omborga, buyurtmasiz
ishlab_chiqarish(it4, 100, 7_777_777, holat="cancelled")   # BEKOR qilingan
r = services.calculate_order_profit(db, o4.id, company_id=1)
check("D bog'lanmagan va BEKOR qilingani qo'shilmadi", r["tan_narxi"], 0)


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
fp6 = mahsulot(10, 700_000)
ishlab_chiqarish(it6, 10, 900_000)
it6.finished_product_id = fp6.id
db.commit()
r = services.calculate_order_profit(db, o6.id, company_id=1)
check("F to'g'ridan-to'g'ri bog'lam ustun (MRP qo'shilmaydi)",
      r["tan_narxi"], 700_000)


# ════════════════════════════════════════════════════════════════
bolim("G. Tenant — boshqa korxonaning mahsuloti")
# ════════════════════════════════════════════════════════════════
o7, it7 = buyurtma(100, 180000)
# B korxonaning ishlab chiqarishi, A korxonaning detaliga ko'rsatilgan —
# bunday "buzuq ma'lumot" ham olinmasligi kerak.
ishlab_chiqarish(it7, 100, 5_000_000, cid=2)
r = services.calculate_order_profit(db, o7.id, company_id=1)
check("G boshqa korxonaning ishlab chiqarishi OLINMADI", r["tan_narxi"], 0)


# ════════════════════════════════════════════════════════════════
bolim("H+I+J. Yuk xati — ombordan chiqish va qaytish")
# ════════════════════════════════════════════════════════════════
import crud  # noqa: E402
import schemas  # noqa: E402

o8, it8 = buyurtma(100, 180000)
po8 = ishlab_chiqarish(it8, 100, 8_144_736.86)
# Ishlab chiqarish natijasi: 100 m², band, barqaror narx 81 447.3686
fp8 = FinishedProduct(
    company_id=1, name="Travertin 25x50", category="dynamic_bom",
    quantity=100, produced_quantity=100, unit="m2", unit_price=0,
    cost_price=8_144_736.86, source=StockSource.PRODUCED,
    product_type_id=tur.id, reserved_for_order_item_id=it8.id,
    reserved_quantity=100, unit_cost_stable=8_144_736.86 / 100)
db.add(fp8)
db.commit()
check("H boshlang'ich ombor", float(fp8.quantity), 100)

# ── Qisman: 60 m² topshiriladi ──
r8 = crud.create_delivery(db, schemas.DeliveryCreate(
    order_id=o8.id, received_by="Mijoz",
    items=[schemas.DeliveryItemCreate(order_item_id=it8.id, quantity=60)]),
    delivered_by="test", company_id=1)
db.refresh(fp8)
check("J qisman topshirildi — omborda 40 qoldi", float(fp8.quantity), 40)
check("J band miqdor ham 40", float(fp8.reserved_quantity), 40)
check("J tan narx barqaror narxdan kamaydi",
      float(fp8.cost_price), 8_144_736.86 - 81_447.3686 * 60, atol=0.02)

# Buyurtma tan narxi O'ZGARMASLIGI shart — topshirish xarajatni kamaytirmaydi
r = services.calculate_order_profit(db, o8.id, company_id=1)
check("J buyurtma tan narxi O'ZGARMADI", r["tan_narxi"], 8_144_736.86)

# ── Qolgan 40 m² ──
crud.create_delivery(db, schemas.DeliveryCreate(
    order_id=o8.id, received_by="Mijoz",
    items=[schemas.DeliveryItemCreate(order_item_id=it8.id, quantity=40)]),
    delivered_by="test", company_id=1)
db.refresh(fp8)
check("H to'liq topshirildi — ombor 0", float(fp8.quantity), 0)
check("H tan narx 0", float(fp8.cost_price or 0), 0, atol=0.02)
check("H bandlik miqdori 0 ga tushdi", float(fp8.reserved_quantity or 0), 0)
check("H tarixiy bog'lam SAQLANDI (qaytarish uchun kerak)",
      1 if fp8.reserved_for_order_item_id == it8.id else 0, 1)

r = services.calculate_order_profit(db, o8.id, company_id=1)
check("H buyurtma tan narxi HAMON o'zgarmagan", r["tan_narxi"], 8_144_736.86)

# ── Yuk xatini o'chirish ──
_dels = [d.id for d in o8.deliveries]
crud.delete_delivery(db, _dels[-1])
db.refresh(fp8)
check("I yuk xati o'chdi — 40 qaytdi", float(fp8.quantity), 40)
check("I tan narx ham qaytdi",
      float(fp8.cost_price), 81_447.3686 * 40, atol=0.02)
check("I bandlik tiklandi", float(fp8.reserved_quantity), 40)


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 62}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 62}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 62)
sys.exit(0 if FAIL == 0 else 1)
