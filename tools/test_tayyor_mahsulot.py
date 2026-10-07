#!/usr/bin/env python3
"""
test_tayyor_mahsulot.py — Tayyor mahsulotning UCHTA ombor funksiyasi.

NEGA BU TEST BOR
----------------
2026-09-20 da (11.2b, gipsni olib tashlash ishi) aniqlandi: quyidagi
uchta funksiyani BIRORTA ham test qamramas ekan — holbuki ular
OMBORDAN HAQIQIY XOMASHYO AYIRADI va tan narxni o'zgartiradi:

    crud.add_to_production                        — "+" miqdor qo'shish
    crud.record_finished_product_production_brak  — ishlab chiqarish braki
    crud.get_finished_profit                      — mahsulot foydasi

Bundan tashqari, uchalasida ham M4 (tenant) izohida "xomashyo ham faqat
shu korxonaniki bo'lishi SHART" deb yozilgan yordamchilar bor edi
(`_add_inv`, `_brak_inv`, `_pf_inv`), lekin ular AMALDA faqat gips
qidiruvlarida ishlatilgan — Penoplast qidiruvlari korxona filtrisiz
raw so'rov edi. 11.2b da Penoplast qidiruvlari ham o'sha yordamchilarga
o'tkazildi. F bo'limi aynan shuni qulflaydi.

NIMA TEKSHIRILADI
-----------------
  A. "+" — Penoplast BARQAROR nisbatdan (unit_volume_m3) ayiriladi
  B. "+" — eski yozuv (unit_volume_m3 yo'q) joriy nisbatga qaytadi
  C. Brak — Penoplast QO'SHIMCHA ayiriladi, mahsulot soniga TEGILMAYDI
  D. Brak — xomashyo yetmasa rad etiladi, ombor o'zgarmaydi
  E. Foyda — penoplast_cost saqlangan hajmdan hisoblanadi
  F. TENANT QULFI — xomashyo boshqa korxonaniki bo'lsa, uchala funksiya
     ham unga TEGMAYDI
  G. Gips QULFI — gips maxsus yo'llari butunlay yo'q

ISHLATISH
---------
    python tools/test_tayyor_mahsulot.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "tayyor_mahsulot_test.db")
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
from production_models import Company  # noqa: E402
from models import (  # noqa: E402
    Inventory, FinishedProduct, FinishedProductLoss, StockSource,
    ProductionStatus, Recipe, RecipeIngredient,
)

db = SessionLocal()
A_CID, B_CID = 1, 2
OK = FAIL = 0
FAILED = []

PENO_NARX = 802126.32     # 1 blok
BLOK_HAJM = 1.4           # m³
LOY_NARX = 2000.0         # 1 kg (bitta ingredient, 1 kg partiya)


def check(label, olingan, kutilgan, atol=0.0001):
    global OK, FAIL
    if isinstance(kutilgan, (int, float)) and isinstance(olingan, (int, float)):
        mos = abs(float(olingan) - float(kutilgan)) <= atol
    else:
        mos = olingan == kutilgan
    if mos:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}  olingan={olingan}  KUTILGAN={kutilgan}")


def check_true(label, cond):
    check(label, bool(cond), True)


def bolim(t):
    print(f"\n{'=' * 62}\n{t}\n{'=' * 62}")


def _stock(inv_id):
    db.expire_all()
    return float(db.query(Inventory).filter(Inventory.id == inv_id).first().stock_quantity)


# ── Baza ────────────────────────────────────────────────────────
for cid, nom in ((A_CID, "A_KORXONA"), (B_CID, "B_KORXONA")):
    if not db.query(Company).filter(Company.id == cid).first():
        db.add(Company(id=cid, name=nom))
db.flush()


def _peno(cid, nom):
    it = Inventory(company_id=cid, item_name=nom, unit="dona",
                   stock_quantity=1000.0, price_per_unit=PENO_NARX,
                   volume_per_unit=BLOK_HAJM, is_penoplast=True,
                   is_default_penoplast=(cid == A_CID), category="Penoplast")
    db.add(it)
    db.flush()
    return it


peno_a = _peno(A_CID, "Penoplast 14P (A)")
peno_b = _peno(B_CID, "Penoplast 14P (B)")

# Loy retsepti — 1 kg partiya, bitta ingredient, 1 kg = LOY_NARX
loy_mat = Inventory(company_id=A_CID, item_name="Akril", unit="kg",
                    stock_quantity=1000.0, price_per_unit=LOY_NARX,
                    volume_per_unit=1.0, category="Boshqa")
db.add(loy_mat)
db.flush()
retsept = Recipe(company_id=A_CID, name="Oq marmar", batch_size_kg=1.0)
db.add(retsept)
db.flush()
db.add(RecipeIngredient(recipe_id=retsept.id, inventory_id=loy_mat.id,
                        quantity_kg=1.0))

# B korxonaning O'Z retsepti — tenant qorovuli ota-yozuvni ham tekshiradi
loy_mat_b = Inventory(company_id=B_CID, item_name="Akril (B)", unit="kg",
                      stock_quantity=1000.0, price_per_unit=LOY_NARX,
                      volume_per_unit=1.0, category="Boshqa")
db.add(loy_mat_b)
db.flush()
retsept_b = Recipe(company_id=B_CID, name="Oq marmar (B)", batch_size_kg=1.0)
db.add(retsept_b)
db.flush()
db.add(RecipeIngredient(recipe_id=retsept_b.id, inventory_id=loy_mat_b.id,
                        quantity_kg=1.0))
db.commit()


def yarat(*, cid=A_CID, peno=None, qty=100.0, unit_vol=0.002,
          unit_loy=None, coated=False, nom="Sinov profil"):
    """Penoplast asosli, ISHLAB CHIQARILGAN tayyor mahsulot."""
    p = peno if peno is not None else peno_a
    vol = unit_vol * qty if unit_vol is not None else 0.0
    narx_m3 = PENO_NARX / BLOK_HAJM
    fp = FinishedProduct(
        company_id=cid, name=nom, category="profil", unit="metr",
        quantity=qty, produced_quantity=qty, is_coated=coated,
        source=StockSource.PRODUCED,
        production_status=ProductionStatus.READY,
        penoplast_id=p.id, volume_m3=vol,
        unit_volume_m3=unit_vol, unit_loy_kg=unit_loy,
        actual_loy_kg=(unit_loy * qty) if unit_loy else 0.0,
        recipe_id=(retsept.id if cid == A_CID else retsept_b.id),
        unit_price=100_000, cost_price=vol * narx_m3,
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)
    return fp


NARX_M3 = PENO_NARX / BLOK_HAJM

# ════════════════════════════════════════════════════════════════
bolim("A. \"+\" MIQDOR QO'SHISH — barqaror nisbatdan")
# ════════════════════════════════════════════════════════════════
fp = yarat(qty=100.0, unit_vol=0.002)           # 0.2 m³ jami
oldin = _stock(peno_a.id)
r = crud.add_to_production(db, fp.id, 50.0, performed_by="test",
                           company_id=A_CID)
check_true("A1 '+' muvaffaqiyatli", r.get("success"))
kerak_m3 = 0.002 * 50.0                          # 0.1 m³
kerak_blok = kerak_m3 / BLOK_HAJM
check("A2 Penoplast aynan shuncha blok kamaydi",
      oldin - _stock(peno_a.id), kerak_blok)
db.refresh(fp)
check("A3 qoldiq 100 -> 150", float(fp.quantity), 150.0)
check("A4 produced_quantity ham 150", float(fp.produced_quantity), 150.0)
check("A5 hajm 0.2 -> 0.3 m³", float(fp.volume_m3), 0.3)
check("A6 tan narx qo'shilgan hajm narxiga oshdi",
      float(fp.cost_price), 0.3 * NARX_M3, atol=1.0)

# ── A7/A8. QISMAN SOTILGAN mahsulot — JORIY nisbat emas, BARQAROR nisbat ──
# Mahsulot sotilganda faqat `quantity` kamayadi, `volume_m3` o'zgarmaydi.
# Shuning uchun "joriy nisbat" (volume_m3 / quantity) vaqt o'tishi bilan
# haqiqatdan uzoqlashadi. "+" BARQAROR nisbatdan (unit_volume_m3)
# hisoblanishi SHART — aks holda qoldiq 0'ga yaqinlashganda xomashyo
# bir necha barobar ko'p ayirilardi.
fp_s = yarat(qty=100.0, unit_vol=0.002, nom="Qisman sotilgan")
fp_s.quantity = 20.0                 # 80 metri sotilgan; volume_m3 = 0.2 qoldi
db.commit()
joriy_nisbat = 0.2 / 20.0            # 0.01 — BARQARORIDAN 5 BAROBAR katta
check("A7 joriy nisbat barqarordan farq qiladi (fikstura to'g'ri)",
      joriy_nisbat != 0.002, True)
oldin = _stock(peno_a.id)
r = crud.add_to_production(db, fp_s.id, 10.0, performed_by="test",
                           company_id=A_CID)
check_true("A8 '+' muvaffaqiyatli", r.get("success"))
check("A9 BARQAROR nisbatdan hisoblandi (joriy nisbatdan EMAS)",
      oldin - _stock(peno_a.id), (0.002 * 10.0) / BLOK_HAJM)

# ── B. eski yozuv — unit_volume_m3 yo'q ──
fp2 = yarat(qty=100.0, unit_vol=None)
fp2.volume_m3 = 0.2                              # joriy nisbat 0.002
fp2.unit_volume_m3 = None
fp2.unit_loy_kg = None
db.commit()
oldin = _stock(peno_a.id)
r = crud.add_to_production(db, fp2.id, 10.0, performed_by="test",
                           company_id=A_CID)
check_true("B1 eski yozuvda ham '+' ishlaydi", r.get("success"))
check("B2 joriy nisbatdan (0.2/100) hisoblandi",
      oldin - _stock(peno_a.id), (0.2 / 100.0 * 10.0) / BLOK_HAJM)

# ════════════════════════════════════════════════════════════════
bolim("C/D. ISHLAB CHIQARISH BRAKI")
# ════════════════════════════════════════════════════════════════
fp3 = yarat(qty=100.0, unit_vol=0.002)
oldin = _stock(peno_a.id)
r = crud.record_finished_product_production_brak(
    db, fp3.id, brak_qty=5.0, notes="sinov", created_by="test",
    company_id=A_CID)
check_true("C1 brak muvaffaqiyatli", r.get("success"))
brak_blok = (0.002 * 5.0) / BLOK_HAJM
check("C2 Penoplast QO'SHIMCHA ayirildi", oldin - _stock(peno_a.id), brak_blok)
check("C3 brak xarajati = blok x narx",
      float(r["cost_amount"]), brak_blok * PENO_NARX, atol=1.0)
db.refresh(fp3)
check("C4 mahsulot soniga TEGILMAYDI", float(fp3.quantity), 100.0)
check("C5 FinishedProductLoss yozuvi yaratildi",
      db.query(FinishedProductLoss).filter(
          FinishedProductLoss.finished_product_id == fp3.id).count(), 1)

# D. xomashyo yetmaydi
kam = Inventory(company_id=A_CID, item_name="Kam penoplast", unit="dona",
                stock_quantity=0.001, price_per_unit=PENO_NARX,
                volume_per_unit=BLOK_HAJM, is_penoplast=True,
                category="Penoplast")
db.add(kam)
db.commit()
fp4 = yarat(qty=100.0, unit_vol=0.002, peno=kam)
oldin = _stock(kam.id)
r = crud.record_finished_product_production_brak(
    db, fp4.id, brak_qty=50.0, created_by="test", company_id=A_CID)
check("D1 yetmasa rad etiladi", r.get("success"), False)
check_true("D2 xabarda 'yetishmayapti'", "yetishmayapti" in str(r.get("message", "")))
check("D3 ombor O'ZGARMADI", _stock(kam.id), oldin)

# ════════════════════════════════════════════════════════════════
bolim("E. MAHSULOT FOYDASI (get_finished_profit)")
# ════════════════════════════════════════════════════════════════
fp5 = yarat(qty=100.0, unit_vol=0.002)
pf = crud.get_finished_profit(db, fp5.id, company_id=A_CID)
check_true("E1 success", pf.get("success"))
check("E2 penoplast_cost = saqlangan hajm x 1 m³ narxi",
      pf["penoplast_cost"], round(0.2 * NARX_M3), atol=1.0)
check("E3 daromad = qoldiq x sotuv narxi", pf["revenue"], 100 * 100_000)
check("E4 loy narxi 0 (qoplamasiz)", pf["loy_cost"], 0)

fp6 = yarat(qty=10.0, unit_vol=0.002, unit_loy=0.5, coated=True)
pf6 = crud.get_finished_profit(db, fp6.id, company_id=A_CID)
check("E5 qoplamali — loy_kg saqlangan qiymatdan", pf6["loy_kg"], 5.0)
check("E6 qoplamali — loy narxi = kg x 1 kg narxi",
      pf6["loy_cost"], round(5.0 * LOY_NARX), atol=1.0)

# ════════════════════════════════════════════════════════════════
bolim("F. TENANT QULFI — xomashyo boshqa korxonaniki bo'lsa")
# ════════════════════════════════════════════════════════════════
# A korxonaning mahsuloti, lekin penoplast_id B korxonanikiga ishora
# qiladi. TOPILMA (2026-09-20): `models._tenant_guard` bunday yozuvni
# ORM orqali yaratishga YO'L QO'YMAYDI (TenantMismatchError) — ya'ni
# himoya ikki qavatli. Lekin qorovul kiritilishidan OLDIN yozilgan
# (yoki to'g'ridan-to'g'ri SQL bilan buzilgan) eski qatorlar bo'lishi
# mumkin, shuning uchun bu yerda aynan shunday qator XOM SQL bilan
# yasaladi va uchala funksiya ham B ning omboriga TEGMASLIGI tekshiriladi.
from sqlalchemy import text as _sql  # noqa: E402

try:
    yarat(cid=A_CID, peno=peno_b, qty=1.0, unit_vol=0.002, nom="Taqiq")
    check("F0 tenant qorovuli korxonalararo yozuvni bloklaydi", False, True)
except Exception as _e:
    db.rollback()
    check("F0 tenant qorovuli korxonalararo yozuvni bloklaydi",
          type(_e).__name__, "TenantMismatchError")

fp_x = yarat(cid=A_CID, peno=peno_a, qty=100.0, unit_vol=0.002,
             nom="Chalkash yozuv")
db.execute(_sql("UPDATE finished_products SET penoplast_id=:b WHERE id=:i"),
           {"b": peno_b.id, "i": fp_x.id})      # qorovuldan chetlab — eski qator
db.commit()
db.expire_all()
fp_x = db.query(FinishedProduct).filter(FinishedProduct.id == fp_x.id).first()
check("F0b xom SQL bilan eski chalkash qator yasaldi",
      fp_x.penoplast_id, peno_b.id)
b_oldin = _stock(peno_b.id)

r = crud.add_to_production(db, fp_x.id, 10.0, performed_by="test",
                           company_id=A_CID)
check("F1 '+' — B korxona ombori O'ZGARMADI", _stock(peno_b.id), b_oldin)
db.refresh(fp_x)
check("F2 '+' — xomashyo topilmagani uchun tan narx oshmadi",
      float(fp_x.cost_price), 0.2 * NARX_M3, atol=1.0)

r = crud.record_finished_product_production_brak(
    db, fp_x.id, brak_qty=5.0, created_by="test", company_id=A_CID)
check("F3 brak — B korxona ombori O'ZGARMADI", _stock(peno_b.id), b_oldin)
check("F4 brak — xomashyo topilmadi deb rad etiladi", r.get("success"), False)

pf_x = crud.get_finished_profit(db, fp_x.id, company_id=A_CID)
check("F5 foyda — B ning narxidan hisoblanmaydi", pf_x["penoplast_cost"], 0)

# B korxonaning O'Z mahsuloti esa normal ishlashi kerak
fp_b = yarat(cid=B_CID, peno=peno_b, qty=100.0, unit_vol=0.002, nom="B mahsuloti")
b_oldin = _stock(peno_b.id)
r = crud.add_to_production(db, fp_b.id, 10.0, performed_by="test",
                           company_id=B_CID)
check_true("F6 B o'z mahsulotiga '+' — ishlaydi", r.get("success"))
check("F7 B o'z ombori kamaydi", b_oldin - _stock(peno_b.id),
      (0.002 * 10.0) / BLOK_HAJM)

# ════════════════════════════════════════════════════════════════
bolim("G. GIPS QULFI (11.2b) — maxsus yo'llar butunlay yo'q")
# ════════════════════════════════════════════════════════════════
import inspect as _insp  # noqa: E402

for fn_nom, fn in (("add_to_production", crud.add_to_production),
                   ("record_..._production_brak",
                    crud.record_finished_product_production_brak),
                   ("get_finished_profit", crud.get_finished_profit),
                   ("_fp_stable_unit_cost", crud._fp_stable_unit_cost)):
    src = _insp.getsource(fn).lower()
    check(f"G: {fn_nom} — 'gips' so'zi yo'q", "gips" in src, False)

check("G: brak imzosida gips_kg_brak yo'q",
      "gips_kg_brak" in str(_insp.signature(
          crud.record_finished_product_production_brak)), False)

# Gips turidagi mahsulot endi maxsus yo'lga tushmaydi — brak rad etiladi
fp_g = yarat(qty=10.0, unit_vol=None, nom="Gips yozuvi")
fp_g.category = "gips"
fp_g.unit_volume_m3 = None
fp_g.unit_loy_kg = None
fp_g.volume_m3 = 0.0
fp_g.gips_kg_used = 50.0
db.commit()
r = crud.record_finished_product_production_brak(
    db, fp_g.id, brak_qty=1.0, created_by="test", company_id=A_CID)
check("G: gips mahsuloti — maxsus shox yo'q, umumiy yo'ldan rad etiladi",
      r.get("success"), False)
pf_g = crud.get_finished_profit(db, fp_g.id, company_id=A_CID)
check("G: gips mahsuloti foydasida gips_kg_used maydoni yo'q",
      "gips_kg_used" in pf_g, False)

# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 62}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 62}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print(f"{'=' * 62}")
sys.exit(1 if FAIL else 0)
