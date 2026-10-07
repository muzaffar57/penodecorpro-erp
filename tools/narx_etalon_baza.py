#!/usr/bin/env python3
"""
narx_etalon_baza.py — narx etalon testlari uchun BAZA (fikstura).

NIMA UCHUN AYRIM FAYL
---------------------
`test_narx_etalon.py` ning o'zi faqat TEKSHIRUVlardan iborat bo'lishi kerak.
Baza qurish (korxona, penoplast, retsept, loyiha) — alohida, shunda
kelajakda boshqa test ham shu bazadan foydalana oladi.

RAQAMLAR QAYERDAN
-----------------
Xomashyo narxlari `etalon_raqamlar.md` dagi HAQIQIY `main` qiymatlaridan
olingan (2026-09-20). Shunda test "o'ylab topilgan" sonlar ustida emas,
korxonaning haqiqiy narx darajasida ishlaydi.

`volume_per_unit` (1 blok necha m³) `main` da o'lchanmagan, shuning uchun
bu yerda ATAYLAB QAT'IY qiymat qo'yilgan (14P = 0.9 m³, 10P = 1.2 m³) —
test takrorlanadigan bo'lishi uchun. Bu son haqiqiy bo'lishi SHART EMAS:
test formulani tekshiradi, omborni emas.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "narx_etalon_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_DB}")

import main  # noqa: E402,F401  (jadvallarni yaratadi)
from sqlalchemy import event  # noqa: E402
from database import SessionLocal, engine  # noqa: E402


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


engine.dispose()

from production_models import Company  # noqa: E402
from models import (  # noqa: E402
    Inventory, Recipe, RecipeIngredient, Project, Order, OrderItem,
    OrderItemSubDetail, FinishedProduct, OrderType, ProjectStatus, StockSource,
)

CID = 1

# ── HAQIQIY narxlar (etalon_raqamlar.md, 2026-09-20) ─────────────
NARX = {
    "Akril Toshkent": 19595.3,
    "Kroshka extra": 645.0,
    "Kroshka mel": 565.0,
    "Oddiy mel": 522.0,
    "Penogasitel": 58000.0,
    "Zagustitel": 38000.0,
    "Penoplast 10P": 624000.0,
    "Penoplast 14P": 802126.32,
}

# 1 blok hajmi — test uchun qat'iy belgilangan (yuqoridagi izohga qarang)
BLOK_HAJM = {"Penoplast 14P": 0.9, "Penoplast 10P": 1.2}

# "Oq marmar" retsepti — 210 kg partiya, 6 ta haqiqiy ingredient
OQ_MARMAR_BATCH = 210.0
OQ_MARMAR = [
    ("Akril Toshkent", 18.0),
    ("Kroshka extra", 110.0),
    ("Kroshka mel", 40.0),
    ("Oddiy mel", 10.0),
    ("Penogasitel", 0.25),
    ("Zagustitel", 0.7),
]

GIPS_NARX = 3000.0  # 1 kg gips — test qiymati


def _inv(db, name, unit, price, vol=1.0, peno=False, default=False, stock=1e6):
    it = Inventory(
        company_id=CID, item_name=name, unit=unit, stock_quantity=stock,
        price_per_unit=price, volume_per_unit=vol,
        is_penoplast=peno, is_default_penoplast=default,
        category="Penoplast" if peno else "Boshqa",
    )
    db.add(it)
    db.flush()
    return it


def qur():
    """Bazani quradi va kerakli obyektlarni lug'atda qaytaradi."""
    db = SessionLocal()

    if not db.query(Company).filter(Company.id == CID).first():
        db.add(Company(id=CID, name="ETALON_KORXONA"))
        db.flush()

    inv = {}
    inv["14P"] = _inv(db, "Penoplast 14P", "dona", NARX["Penoplast 14P"],
                      BLOK_HAJM["Penoplast 14P"], peno=True, default=True)
    inv["10P"] = _inv(db, "Penoplast 10P", "dona", NARX["Penoplast 10P"],
                      BLOK_HAJM["Penoplast 10P"], peno=True)
    inv["gips"] = _inv(db, "Gips", "kg", GIPS_NARX)
    for nom, _kg in OQ_MARMAR:
        inv[nom] = _inv(db, nom, "kg", NARX[nom])

    retsept = Recipe(company_id=CID, name="Oq marmar", batch_size_kg=OQ_MARMAR_BATCH)
    db.add(retsept)
    db.flush()
    for nom, kg in OQ_MARMAR:
        db.add(RecipeIngredient(recipe_id=retsept.id, inventory_id=inv[nom].id,
                                quantity_kg=kg))
    db.flush()

    loyiha = Project(company_id=CID, project_number="PRJ-ETALON",
                     client_name="Etalon mijoz", project_name="Etalon loyiha",
                     status=ProjectStatus.DRAFT)
    db.add(loyiha)
    db.flush()
    db.commit()

    return {"db": db, "inv": inv, "retsept": retsept, "loyiha": loyiha}


_RAQAM = [0]


def buyurtma_yasa(db, loyiha, items, **kw):
    """Bitta buyurtma + detallarini yaratadi. items — lug'atlar ro'yxati."""
    _RAQAM[0] += 1
    o = Order(
        company_id=CID, order_number=f"ETL-{_RAQAM[0]:03d}",
        project_id=loyiha.id, order_type=OrderType.PRODUCT,
        total_amount=kw.get("total_amount", 0),
        agreed_amount=kw.get("agreed_amount", 0),
        actual_loy_kg=kw.get("actual_loy_kg"),
        planned_loy_kg=kw.get("planned_loy_kg"),
        actual_gips_kg=kw.get("actual_gips_kg"),
        gips_inventory_id=kw.get("gips_inventory_id"),
        notes=kw.get("notes"),
    )
    db.add(o)
    db.flush()
    for d in items:
        subs = d.pop("sub_details", None)
        it = OrderItem(company_id=CID, order_id=o.id, **d)
        db.add(it)
        db.flush()
        for s in (subs or []):
            db.add(OrderItemSubDetail(order_item_id=it.id, **s))
        db.flush()
    db.commit()
    db.refresh(o)
    return o


def tayyor_mahsulot(db, **kw):
    fp = FinishedProduct(company_id=CID, source=StockSource.PRODUCED, **kw)
    db.add(fp)
    db.flush()
    db.commit()
    return fp


JONLI_CID = 2   # jonli etalon ALOHIDA korxonada — sun'iy fikstura bilan
                # xomashyo nomlari bir xil, bitta korxonada to'qnashardi


def jonli_qur(yol=None):
    """JONLI etalonni (staging'dagi `main` ma'lumoti) alohida bazaga tiklaydi.

    `narx_etalon_jonli.json` — 2026-09-20 da staging API dan DASTUR ORQALI
    o'lchangan haqiqiy 22 buyurtma, 75 detal, 9 xomashyo va "Oq marmar"
    retsepti. Shu yerda ular ayni id'lari bilan qayta quriladi, shunda
    `calculate_order_profit` o'sha kunги raqamni qaytarishi SHART.
    """
    import json
    import os as _os
    from models import Inventory as _I, Recipe as _R, RecipeIngredient as _RI

    yol = yol or _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                               "narx_etalon_jonli.json")
    with open(yol, encoding="utf-8") as fh:
        d = json.load(fh)

    db = SessionLocal()
    if not db.query(Company).filter(Company.id == JONLI_CID).first():
        db.add(Company(id=JONLI_CID, name="JONLI_ETALON"))
        db.flush()

    for _id, nom, narx, hajm, peno, asosiy, birlik in d["inventory"]:
        if db.query(_I).filter(_I.id == _id).first():
            continue
        db.add(_I(id=_id, company_id=JONLI_CID, item_name=nom, unit=birlik,
                  stock_quantity=1e6, price_per_unit=narx, volume_per_unit=hajm,
                  is_penoplast=peno, is_default_penoplast=asosiy))
    rid, rnom, rbatch = d["recipe"]
    if not db.query(_R).filter(_R.id == rid).first():
        db.add(_R(id=rid, company_id=JONLI_CID, name=rnom, batch_size_kg=rbatch))
        db.flush()
        for _r, _inv, kg in d["recipe_ingredients"]:
            db.add(_RI(recipe_id=_r, inventory_id=_inv, quantity_kg=kg))
    db.flush()

    loyiha = Project(company_id=JONLI_CID, project_number="PRJ-JONLI",
                     client_name="Jonli etalon", project_name="Jonli etalon",
                     status=ProjectStatus.DRAFT)
    db.add(loyiha)
    db.flush()

    detallar = {}
    for it in d["order_items"]:
        detallar.setdefault(it["order_number"], []).append(it)

    buyurtmalar = {}
    for o in d["orders"]:
        row = Order(company_id=JONLI_CID, order_number=o["order_number"],
                    project_id=loyiha.id, order_type=OrderType.PRODUCT,
                    total_amount=o["total_amount"], agreed_amount=o["agreed_amount"],
                    actual_loy_kg=o["actual_loy_kg"], planned_loy_kg=o["planned_loy_kg"])
        db.add(row)
        db.flush()
        for it in detallar.get(o["order_number"], []):
            db.add(OrderItem(
                id=it["id"], company_id=JONLI_CID, order_id=row.id, name=f"detal {it['id']}",
                category=it["category"], width=it["width"], thickness=it["thickness"],
                length=it["length"], quantity=it["quantity"], is_coated=it["is_coated"],
                unit_price=it["unit_price"], total_price=0,
                unit_price_for_volume=it["unit_price_for_volume"],
                price_per_m3=it["price_per_m3"], penoplast_id=it["penoplast_id"],
                recipe_id=it["recipe_id"]))
        db.flush()
        buyurtmalar[o["order_number"]] = row
    db.commit()
    return {"db": db, "company_id": JONLI_CID, "buyurtmalar": buyurtmalar,
            "etalon": d["etalon_foyda"], "malumot": d}
