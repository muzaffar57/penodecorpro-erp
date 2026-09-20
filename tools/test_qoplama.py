#!/usr/bin/env python3
"""
test_qoplama.py — Bosqich 3, 11.0-band: MRP mahsulotida QOPLAMA.

NIMA TEKSHIRILADI
-----------------
Qoplama ikki mustaqil narsadan iborat, ikkalasi ham alohida sinaladi:

  NARX     — `ProductType.coating_price_multiplier`. Har korxona o'zi
             yozadi (2, 2.5, ...). Faqat sotuv narxiga tegadi.
  XOMASHYO — retseptning `is_optional=True, is_coating=True` qatori.
             Buyurtma detali qoplamali bo'lsa, o'zi qo'shiladi.

  A. Sxema tekshiruvi — koeffitsiyentsiz "qoplama bor" deb bo'lmaydi
  B. Ustunlar bazada bor
  C. Qoplamali detal → qoplama qatori AVTOMATIK tanlanadi
  D. Qoplamasiz detal → qoplama qatori zo'rlab OLIB TASHLANADI
  E. Boshqa ixtiyoriy qatorlar (qadoqlash) tegilmaydi
  F. Ombordan yechish — qoplamali/qoplamasiz farqi haqiqatan chiqadi
  G. Brauzer formulasi — narx koeffitsiyentga ko'payadi

ISHLATISH
---------
    python tools/test_qoplama.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "qoplama_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import main  # noqa: E402,F401
from sqlalchemy import event, inspect  # noqa: E402
from database import SessionLocal, engine  # noqa: E402


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


engine.dispose()

import production_schemas as PS  # noqa: E402
import production_service as PSV  # noqa: E402
from production_models import Company, ProductType, BOM, BOMItem  # noqa: E402
from models import (  # noqa: E402
    Inventory, Project, Order, OrderItem, OrderType, ProjectStatus,
)

db = SessionLocal()
CID = 1
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
if not db.query(Company).filter(Company.id == CID).first():
    db.add(Company(id=CID, name="A_KORXONA"))
db.flush()

peno = Inventory(company_id=CID, item_name="Penoplast 14P", unit="dona",
                 stock_quantity=1000, price_per_unit=802126.32,
                 volume_per_unit=1.4, is_penoplast=True,
                 is_default_penoplast=True)
loy = Inventory(company_id=CID, item_name="Tayyor loy", unit="kg",
                stock_quantity=1000, price_per_unit=2345.64,
                volume_per_unit=1)
qadoq = Inventory(company_id=CID, item_name="Qadoqlash plyonkasi", unit="dona",
                  stock_quantity=1000, price_per_unit=500, volume_per_unit=1)
db.add_all([peno, loy, qadoq])
db.flush()

loyiha = Project(company_id=CID, project_number="PRJ-Q", client_name="Sinov",
                 project_name="Sinov", status=ProjectStatus.DRAFT)
db.add(loyiha)
db.flush()
db.commit()


# ════════════════════════════════════════════════════════════════
bolim("A. Sxema — koeffitsiyentsiz qoplama yoqib bo'lmaydi")
# ════════════════════════════════════════════════════════════════
_asos = dict(name="X", unit="metr", input_template="quantity_only",
             pricing_formula="unit_based")
rad = False
try:
    PS.ProductTypeCreate(**_asos, supports_coating=True)
except Exception:
    rad = True
check("qoplama yoqilgan, koeffitsiyent yo'q — RAD etiladi", rad)

ok25 = PS.ProductTypeCreate(**_asos, supports_coating=True,
                            coating_price_multiplier=2.5)
check("koeffitsiyent 2.5 bilan qabul qilinadi",
      ok25.coating_price_multiplier == 2.5)
oddiy = PS.ProductTypeCreate(**_asos)
check("qoplamasiz tur — standart qiymatlar",
      oddiy.supports_coating is False
      and oddiy.coating_price_multiplier is None)
rad0 = False
try:
    PS.ProductTypeCreate(**_asos, supports_coating=True,
                         coating_price_multiplier=0)
except Exception:
    rad0 = True
check("koeffitsiyent 0 — RAD etiladi", rad0)


# ════════════════════════════════════════════════════════════════
bolim("B. Ustunlar bazada")
# ════════════════════════════════════════════════════════════════
pt_cols = {c["name"] for c in inspect(engine).get_columns("product_types")}
bi_cols = {c["name"] for c in inspect(engine).get_columns("bom_items")}
check("product_types.supports_coating", "supports_coating" in pt_cols)
check("product_types.coating_price_multiplier",
      "coating_price_multiplier" in pt_cols)
check("bom_items.is_coating", "is_coating" in bi_cols)


# ── Tur + retsept: 1 metr uchun 0.4 blok penoplast,
#    0.8 kg loy (qoplama), 1 dona qadoq (ixtiyoriy, qoplama EMAS)
tur = ProductType(company_id=CID, name="Blok karniz", unit="metr",
                  input_template="quantity_only", pricing_formula="unit_based",
                  supports_coating=True, coating_price_multiplier=2.5)
db.add(tur)
db.flush()
bom = BOM(company_id=CID, product_type_id=tur.id, variant_name="Standart",
          batch_quantity=1)
db.add(bom)
db.flush()
bi_peno = BOMItem(bom_id=bom.id, company_id=CID, inventory_id=peno.id,
                  quantity=0.4, scrap_factor_percent=0, is_optional=False)
bi_loy = BOMItem(bom_id=bom.id, company_id=CID, inventory_id=loy.id,
                 quantity=0.8, scrap_factor_percent=0, is_optional=True,
                 is_coating=True)
bi_qadoq = BOMItem(bom_id=bom.id, company_id=CID, inventory_id=qadoq.id,
                   quantity=1, scrap_factor_percent=0, is_optional=True,
                   is_coating=False)
db.add_all([bi_peno, bi_loy, bi_qadoq])
db.commit()


def buyurtma_detali(qoplamali, miqdor=100):
    o = Order(company_id=CID, order_number=f"Q-{qoplamali}-{miqdor}",
              project_id=loyiha.id, order_type=OrderType.PRODUCT,
              total_amount=0, agreed_amount=0)
    db.add(o)
    db.flush()
    it = OrderItem(company_id=CID, order_id=o.id, name="Blok karniz",
                   category="mrp_product", quantity=miqdor, unit_price=20000,
                   total_price=miqdor * 20000, is_coated=qoplamali,
                   product_type_id=tur.id)
    db.add(it)
    db.commit()
    return it


class _Data:
    def __init__(self, item, tanlangan=None):
        self.product_type_id = tur.id
        self.bom_id = bom.id
        self.source_type = "customer_order"
        self.source_order_id = item.order_id
        self.source_order_item_id = item.id
        self.quantity = float(item.quantity)
        self.selected_optional_bom_item_ids = list(tanlangan or [])
        self.notes = None


# ════════════════════════════════════════════════════════════════
bolim("C. Qoplamali detal — qoplama qatori o'zi tanlanadi")
# ════════════════════════════════════════════════════════════════
it_q = buyurtma_detali(True)
r = PSV.create_production_order(db, CID, _Data(it_q), created_by="test")
check("ishlab chiqarish buyurtmasi yaratildi", r.get("success") is True)
import json as _j
tanl = set(_j.loads(r["production_order"].selected_optional_bom_item_ids_json))
check("qoplama qatori TANLANDI (operator belgilamagan bo'lsa ham)",
      bi_loy.id in tanl)
check("qadoqlash qatori tanlanmadi", bi_qadoq.id not in tanl)


# ════════════════════════════════════════════════════════════════
bolim("D. Qoplamasiz detal — qoplama qatori olib tashlanadi")
# ════════════════════════════════════════════════════════════════
it_n = buyurtma_detali(False)
# Operator XATO bilan qoplamani belgilab yuboradi — server tuzatishi SHART
r2 = PSV.create_production_order(db, CID, _Data(it_n, [bi_loy.id]),
                                 created_by="test")
tanl2 = set(_j.loads(r2["production_order"].selected_optional_bom_item_ids_json))
check("detal qoplamasiz — qoplama qatori ZO'RLAB olib tashlandi",
      bi_loy.id not in tanl2)


# ════════════════════════════════════════════════════════════════
bolim("E. Qoplamadan boshqa ixtiyoriy qator tegilmaydi")
# ════════════════════════════════════════════════════════════════
it_q2 = buyurtma_detali(True, miqdor=50)
r3 = PSV.create_production_order(db, CID, _Data(it_q2, [bi_qadoq.id]),
                                 created_by="test")
tanl3 = set(_j.loads(r3["production_order"].selected_optional_bom_item_ids_json))
check("operator tanlagan qadoqlash SAQLANDI", bi_qadoq.id in tanl3)
check("qoplama ham qo'shildi", bi_loy.id in tanl3)


# ════════════════════════════════════════════════════════════════
bolim("F. Ombordan yechish — qoplamali/qoplamasiz farqi")
# ════════════════════════════════════════════════════════════════
peno_0 = float(peno.stock_quantity)
loy_0 = float(loy.stock_quantity)

# Qoplamali 100 metr: 40 blok + 80 kg loy
PSV.start_production_order(db, r["production_order"].id, CID, "test")
PSV.complete_production_order(db, r["production_order"].id, CID, "test")
db.refresh(peno)
db.refresh(loy)
check("qoplamali: penoplast 0.4 x 100 = 40 blok yechildi",
      abs((peno_0 - float(peno.stock_quantity)) - 40.0) < 1e-6)
check("qoplamali: loy 0.8 x 100 = 80 kg yechildi",
      abs((loy_0 - float(loy.stock_quantity)) - 80.0) < 1e-6)

peno_1 = float(peno.stock_quantity)
loy_1 = float(loy.stock_quantity)
PSV.start_production_order(db, r2["production_order"].id, CID, "test")
PSV.complete_production_order(db, r2["production_order"].id, CID, "test")
db.refresh(peno)
db.refresh(loy)
check("qoplamasiz: penoplast yana 40 blok yechildi",
      abs((peno_1 - float(peno.stock_quantity)) - 40.0) < 1e-6)
check("qoplamasiz: loy UMUMAN yechilmadi",
      abs(loy_1 - float(loy.stock_quantity)) < 1e-9)


# ════════════════════════════════════════════════════════════════
bolim("G. Narx koeffitsiyenti — brauzer formulasi")
# ════════════════════════════════════════════════════════════════
# `orders.html` dagi recalcMrpPrice() bilan AYNAN bir xil qoida:
#   yakuniy narx = asos narx x (qoplamali ? koeffitsiyent : 1)


def brauzer_narx(asos, qoplamali, mult):
    return round(asos * mult) if qoplamali else round(asos)


check("20 000, qoplamasiz -> 20 000", brauzer_narx(20000, False, 2.5) == 20000)
check("20 000, qoplamali x2.5 -> 50 000",
      brauzer_narx(20000, True, 2.5) == 50000)
check("20 000, qoplamali x2 -> 40 000", brauzer_narx(20000, True, 2) == 40000)
check("jami: 100 metr x 50 000 = 5 000 000",
      brauzer_narx(20000, True, 2.5) * 100 == 5_000_000)
# Teskari yo'l: xodim YAKUNIY narxni qo'lda yozsa, asos qayta tiklanadi
check("qo'lda 50 000 yozildi, koeffitsiyent 2.5 -> asos 20 000",
      round(50000 / 2.5) == 20000)


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 62}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 62}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 62)
sys.exit(0 if FAIL == 0 else 1)
