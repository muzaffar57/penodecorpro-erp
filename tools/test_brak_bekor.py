#!/usr/bin/env python3
"""
test_brak_bekor.py — xato yozilgan brakni bekor qilish.

NIMA UCHUN
----------
`record_finished_product_loss()` bor edi, lekin uni ORQAGA QAYTARISH
yo'li hech qayerda yo'q edi. Ya'ni bir marta xato yozilgan brak
Moliyadagi "Brak xarajati"da abadiy qolib ketardi va sof foydani
jimgina pasaytirardi. Bu bo'shliq 2026-09-20 da, staging'dagi sinov
tozalashi sentabr sof foydasini 6 573 773 so'mga siljitib yuborganda
aniqlandi.

  A. Mahsulot hali bor — miqdor va tan narx QAYTARILADI
  B. Mahsulot o'chirilgan — faqat yozuv o'chadi, xato bermaydi
  C. Boshqa korxonaning yozuvini o'chirib bo'lmaydi
  D. Yo'q yozuv — toza xato xabari
  E. Faoliyat jurnaliga tushadi

ISHLATISH
---------
    python tools/test_brak_bekor.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "brak_bekor_test.db")
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
    FinishedProduct, FinishedProductLoss, StockSource, ActivityLog,
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
    print(f"\n{'=' * 60}\n{t}\n{'=' * 60}")


for cid, nom in ((1, "A"), (2, "B")):
    if not db.query(Company).filter(Company.id == cid).first():
        db.add(Company(id=cid, name=nom))
db.flush()
db.commit()


class _Loss:
    def __init__(self, fp_id, qty, reason="sinov"):
        self.finished_product_id = fp_id
        self.quantity = qty
        self.reason = reason


def yangi_fp(cid=1, qty=10, cost=1_000_000):
    fp = FinishedProduct(company_id=cid, name=f"Mahsulot {cid}", category="profil",
                         quantity=qty, produced_quantity=qty, unit="metr",
                         unit_price=200_000, cost_price=cost,
                         source=StockSource.PRODUCED)
    db.add(fp)
    db.commit()
    db.refresh(fp)
    return fp


# ════════════════════════════════════════════════════════════════
bolim("A. Mahsulot bor — to'liq bekor qilinadi")
# ════════════════════════════════════════════════════════════════
fp = yangi_fp()
r = crud.record_finished_product_loss(db, _Loss(fp.id, 4), created_by="t", company_id=1)
db.refresh(fp)
check("brak yozildi", r["success"] is True)
check("miqdor 10 -> 6", float(fp.quantity) == 6.0)
check("tan narx 1 000 000 -> 600 000", float(fp.cost_price) == 600_000.0)
check("brak summasi 400 000", abs(r["cost_amount"] - 400_000) < 0.01)

b = crud.delete_finished_product_loss(db, r["loss_id"], company_id=1, performed_by="t")
db.refresh(fp)
check("bekor qilindi", b["success"] is True)
check("miqdor QAYTDI 6 -> 10", float(fp.quantity) == 10.0)
check("tan narx QAYTDI -> 1 000 000", float(fp.cost_price) == 1_000_000.0)
check("ombor tiklandi deb belgilandi", b["ombor_tiklandi"] is True)
check("brak yozuvi o'chdi",
      db.query(FinishedProductLoss).filter(
          FinishedProductLoss.id == r["loss_id"]).first() is None)


# ════════════════════════════════════════════════════════════════
bolim("B. Mahsulot o'chirilgan — yozuv baribir o'chadi")
# ════════════════════════════════════════════════════════════════
fp2 = yangi_fp(qty=5, cost=500_000)
r2 = crud.record_finished_product_loss(db, _Loss(fp2.id, 5), created_by="t", company_id=1)
loss2 = db.query(FinishedProductLoss).filter(
    FinishedProductLoss.id == r2["loss_id"]).first()
loss2.finished_product_id = None          # mahsulot o'chirilgan holat
db.delete(fp2)
db.commit()
b2 = crud.delete_finished_product_loss(db, r2["loss_id"], company_id=1, performed_by="t")
check("mahsulotsiz ham bekor qilindi", b2["success"] is True)
check("ombor tiklanmadi (mahsulot yo'q)", b2["ombor_tiklandi"] is False)
check("yozuv o'chdi",
      db.query(FinishedProductLoss).filter(
          FinishedProductLoss.id == r2["loss_id"]).first() is None)


# ════════════════════════════════════════════════════════════════
bolim("C. Tenant — boshqa korxonaning yozuvi")
# ════════════════════════════════════════════════════════════════
fp_b = yangi_fp(cid=2, qty=8, cost=800_000)
r3 = crud.record_finished_product_loss(db, _Loss(fp_b.id, 3), created_by="t", company_id=2)
b3 = crud.delete_finished_product_loss(db, r3["loss_id"], company_id=1, performed_by="t")
check("A korxona B ning brakini o'chira OLMAYDI", b3["success"] is False)
check("yozuv joyida",
      db.query(FinishedProductLoss).filter(
          FinishedProductLoss.id == r3["loss_id"]).first() is not None)
b4 = crud.delete_finished_product_loss(db, r3["loss_id"], company_id=2, performed_by="t")
db.refresh(fp_b)
check("B korxona O'Z brakini o'chira oladi", b4["success"] is True)
check("B ning ombori tiklandi 5 -> 8", float(fp_b.quantity) == 8.0)


# ════════════════════════════════════════════════════════════════
bolim("D. Yo'q yozuv")
# ════════════════════════════════════════════════════════════════
b5 = crud.delete_finished_product_loss(db, 999999, company_id=1, performed_by="t")
check("aniq xato xabari", b5["success"] is False and "topilmadi" in b5["message"])


# ════════════════════════════════════════════════════════════════
bolim("E. Faoliyat jurnali")
# ════════════════════════════════════════════════════════════════
jurnal = db.query(ActivityLog).filter(
    ActivityLog.entity_type == "finished_product_loss").all()
check("har bir bekor qilish jurnalga tushdi", len(jurnal) >= 3)
check("izohda mahsulot nomi bor",
      any("Mahsulot" in (x.entity_label or "") for x in jurnal))


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 60}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
