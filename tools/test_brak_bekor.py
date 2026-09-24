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
  F. 18-band: "ishlab chiqarish braki" yozuvini bekor qilish RAD etiladi
     (ilgari mahsulot miqdori yo'qdan oshar, penoplast qaytmas, xarajat
     moliyada qolar edi — jonli o'lchangan 2026-09-21) — hech narsa o'zgarmaydi
  G. 18-band: belgi matni crud / services / yozuv o'rtasida bir xil
  H. 18-band: HTTP — o'z ishlab chiqarish braki 400 (`detail.message`),
     begona ishlab chiqarish braki 404 (oracle yo'q), oddiy brak 200

ISHLATISH
---------
    python tools/test_brak_bekor.py
    TENANT_FILTER=1 python tools/test_brak_bekor.py
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
    FinishedProduct, FinishedProductLoss, StockSource, ActivityLog, ProductionStatus,
    Inventory, InventoryMovement, UserRole,
)
import auth  # noqa: E402
import services  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

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
                         source=StockSource.PRODUCED,
                         # 17-band: ombordan chiqadigan amal (brak) faqat
                         # TAYYOR mahsulotda — fikstura tayyor mahsulot.
                         production_status=ProductionStatus.READY)
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
# 18-band fiksturasi: penoplastdan qilingan TAYYOR mahsulot (qoplamasiz —
# faqat penoplast ayiriladi), har korxonada alohida
# ════════════════════════════════════════════════════════════════
def yangi_peno(cid, stock=100.0):
    inv = Inventory(company_id=cid, item_name=f"Brak18 Penoplast {cid}", unit="blok",
                    stock_quantity=stock, price_per_unit=500_000,
                    volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def yangi_peno_fp(cid, peno_id, qty=10.0, cost=100_000.0):
    fp = FinishedProduct(company_id=cid, name=f"Brak18 Profil {cid}", category="profil",
                         quantity=qty, produced_quantity=qty, unit="metr",
                         unit_price=50_000, cost_price=cost,
                         source=StockSource.PRODUCED,
                         production_status=ProductionStatus.READY,
                         penoplast_id=peno_id, unit_volume_m3=0.01,
                         unit_loy_kg=0.0, is_coated=False)
    db.add(fp)
    db.commit()
    db.refresh(fp)
    return fp


def holat(fp_id, peno_id, cid):
    """Ishlab chiqarish brakiga tegishli HAMMA narsa: mahsulot miqdori va
    tan narxi, penoplast qoldig'i, ombor harakatlari soni, brak yozuvlari
    soni, oylik hisobotdagi brak xarajati va sof foyda."""
    db.expire_all()
    fp_ = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    inv = db.query(Inventory).filter(Inventory.id == peno_id).first()
    harakat = db.query(InventoryMovement).filter(
        InventoryMovement.inventory_id == peno_id).count()
    yozuv = db.query(FinishedProductLoss).filter(
        FinishedProductLoss.finished_product_id == fp_id).count()
    try:
        from datetime import datetime as _dt
        _n = _dt.now()
        rep = services.get_monthly_report(db, _n.year, _n.month, company_id=cid)
        sof = round(float(rep.get("sof_foyda", 0) or 0), 4)
    except Exception as _e:          # hisobot yiqilsa ham skript QULAMASIN
        sof = f"xato: {type(_e).__name__}"
    return (round(float(fp_.quantity), 6), round(float(fp_.cost_price), 4),
            round(float(inv.stock_quantity), 6), harakat, yozuv, sof)


# ════════════════════════════════════════════════════════════════
bolim("F. 18-band: ishlab chiqarish braki — bekor qilish RAD, hech narsa o'zgarmaydi")
# ════════════════════════════════════════════════════════════════
peno_a = yangi_peno(1)
fp_i = yangi_peno_fp(1, peno_a.id)
PENO_A_ID, FP_I_ID = peno_a.id, fp_i.id
h0 = holat(FP_I_ID, PENO_A_ID, 1)
ri = crud.record_finished_product_production_brak(
    db, FP_I_ID, brak_qty=2, notes="sinov", created_by="t", company_id=1)
check("ishlab chiqarish braki yozildi", ri.get("success") is True)
h1 = holat(FP_I_ID, PENO_A_ID, 1)
check("mahsulot soniga TEGILMADI (10)", h1[0] == 10.0 == h0[0])
check("penoplast 2 × 0.01 = 0.02 blok ayirildi (100 -> 99.98)",
      abs(h1[2] - 99.98) < 1e-9, str(h1))
check("ombor harakati yozildi (+1)", h1[3] == h0[3] + 1, str((h0, h1)))
check("brak yozuvi yozildi (+1)", h1[4] == h0[4] + 1)
check("xarajat oylik hisobotga BIR MARTA tushdi (sof -10 000)",
      isinstance(h1[5], float) and isinstance(h0[5], float)
      and abs((h0[5] - h1[5]) - 10_000.0) < 0.01, str((h0[5], h1[5])))
loss_i = db.query(FinishedProductLoss).filter(
    FinishedProductLoss.id == ri.get("loss_id")).first()
check("yozuv sababi belgi bilan boshlanadi",
      loss_i is not None and (loss_i.reason or "").startswith(
          getattr(crud, "_ISH_BRAK_BELGI", "Ishlab chiqarish jarayonida brak")))

# Jurnal soni rad etilgan urinishlardan OLDIN (id bo'yicha emas: SQLite
# o'chirilgan eng katta id ni qayta beradi — A–C bo'limlari id 1 ni
# o'chirgan, shu id yangi yozuvga berilgan; o'lchandi)
_jc0 = db.query(ActivityLog).filter(
    ActivityLog.entity_type == "finished_product_loss").count()
bi = crud.delete_finished_product_loss(db, ri.get("loss_id"), company_id=1, performed_by="t")
check("bekor qilish RAD etildi", bi.get("success") is False, str(bi))
check("rad sababi — kod 'ishlab_chiqarish_braki'",
      bi.get("kod") == "ishlab_chiqarish_braki", str(bi))
check("xabarda 'Ishlab chiqarish brakini' bor",
      "Ishlab chiqarish brakini" in (bi.get("message") or ""), str(bi))
h2 = holat(FP_I_ID, PENO_A_ID, 1)
check("mahsulot miqdori O'ZGARMADI (yo'qdan oshmadi)", h2[0] == h1[0], str((h1, h2)))
check("tan narxi O'ZGARMADI (shishmadi)", h2[1] == h1[1], str((h1, h2)))
check("penoplast qoldig'i O'ZGARMADI", h2[2] == h1[2], str((h1, h2)))
check("ombor harakatlari O'ZGARMADI", h2[3] == h1[3], str((h1, h2)))
check("brak yozuvi JOYIDA", h2[4] == h1[4], str((h1, h2)))
check("oylik sof foyda O'ZGARMADI", h2[5] == h1[5], str((h1, h2)))
check("holat butunligicha bir xil", h2 == h1, str((h1, h2)))

# Takror urinish ham rad (birinchisi hech narsa o'chirmagan)
bi2 = crud.delete_finished_product_loss(db, ri.get("loss_id"), company_id=1, performed_by="t")
check("takror urinish ham rad", bi2.get("kod") == "ishlab_chiqarish_braki", str(bi2))
check("takrordan keyin ham holat bir xil", holat(FP_I_ID, PENO_A_ID, 1) == h1)

# Rad etilgan urinish "bekor qilindi" deb jurnalga TUSHMASLIGI kerak
_jc1 = db.query(ActivityLog).filter(
    ActivityLog.entity_type == "finished_product_loss").count()
check("rad etilgan 2 urinish jurnalga 'bekor qilindi' deb yozilmadi", _jc1 == _jc0,
      str((_jc0, _jc1)))

# Belgi faqat BOSHIDA hisoblanadi: sababi belgi bilan boshlanmagan (oddiy
# zaxiradan kamaytirish, izohida belgi matni bo'lsa ham) — oddiy bekor qilinadi
fp_o = yangi_peno_fp(1, PENO_A_ID, qty=5, cost=50_000)
ro = crud.record_finished_product_loss(
    db, _Loss(fp_o.id, 1, reason="izoh: Ishlab chiqarish jarayonida brak emas"),
    created_by="t", company_id=1)
bo = crud.delete_finished_product_loss(db, ro["loss_id"], company_id=1, performed_by="t")
db.refresh(fp_o)
check("oddiy brak (belgi o'rtada) — bekor qilindi", bo.get("success") is True, str(bo))
check("oddiy brak — miqdor qaytdi 4 -> 5", float(fp_o.quantity) == 5.0)

# Mahsulot o'chirilgan ishlab chiqarish braki — baribir rad (yozuv qoladi)
fp_d = yangi_peno_fp(1, PENO_A_ID, qty=3, cost=30_000)
rd = crud.record_finished_product_production_brak(
    db, fp_d.id, brak_qty=1, created_by="t", company_id=1)
loss_d = db.query(FinishedProductLoss).filter(
    FinishedProductLoss.id == rd.get("loss_id")).first()
loss_d.finished_product_id = None
db.delete(fp_d)
db.commit()
bd = crud.delete_finished_product_loss(db, rd.get("loss_id"), company_id=1, performed_by="t")
check("mahsulotsiz ishlab chiqarish braki ham rad", bd.get("kod") == "ishlab_chiqarish_braki",
      str(bd))
check("mahsulotsiz ishlab chiqarish braki yozuvi joyida",
      db.query(FinishedProductLoss).filter(
          FinishedProductLoss.id == rd.get("loss_id")).first() is not None)

# Korxona tekshiruvi rad etishdan OLDIN: B ning ishlab chiqarish braki A uchun
# "topilmadi" (kod YO'Q — mavjudligi oshkor bo'lmaydi)
peno_b = yangi_peno(2)
fp_ib = yangi_peno_fp(2, peno_b.id)
PENO_B_ID, FP_IB_ID = peno_b.id, fp_ib.id
rb = crud.record_finished_product_production_brak(
    db, FP_IB_ID, brak_qty=1, created_by="t", company_id=2)
LOSS_IB_ID = rb.get("loss_id")
bb = crud.delete_finished_product_loss(db, LOSS_IB_ID, company_id=1, performed_by="t")
check("A korxona B ning ishlab chiqarish brakini — 'topilmadi'",
      bb.get("success") is False and "topilmadi" in (bb.get("message") or ""), str(bb))
check("… va kod YO'Q (oracle yo'q)", "kod" not in bb, str(bb))
bb2 = crud.delete_finished_product_loss(db, LOSS_IB_ID, company_id=2, performed_by="t")
check("B o'zi ham ishlab chiqarish brakini bekor qila olmaydi",
      bb2.get("kod") == "ishlab_chiqarish_braki", str(bb2))


# ════════════════════════════════════════════════════════════════
bolim("G. 18-band: belgi matni hamma joyda bir xil")
# ════════════════════════════════════════════════════════════════
BELGI = getattr(crud, "_ISH_BRAK_BELGI", None)
check("crud._ISH_BRAK_BELGI mavjud", BELGI == "Ishlab chiqarish jarayonida brak", str(BELGI))
check("crud._ish_brakimi mavjud", callable(getattr(crud, "_ish_brakimi", None)))
_src_services = open(os.path.join(ROOT, "services.py"), encoding="utf-8").read()
# kech57 (40-band): services literal NUSXA saqlamaydi — crud konstantasini oladi
# (ilgari bu tekshiruv 2 ta nusxa AYNAN shu matn ekanini qulflardi).
check("services.py da belgi literal nusxasi YO'Q, crud._ISH_BRAK_BELGI ishlatiladi",
      BELGI is not None and _src_services.count(f'"{BELGI}"') == 0
      and _src_services.count("._ISH_BRAK_BELGI") >= 3,
      str((_src_services.count('"Ishlab chiqarish jarayonida brak"'),
           _src_services.count("._ISH_BRAK_BELGI"))))
_src_crud = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
check("crud.py da belgi matni FAQAT bir marta (konstanta) yozilgan",
      _src_crud.count('"Ishlab chiqarish jarayonida brak"') == 1,
      str(_src_crud.count('"Ishlab chiqarish jarayonida brak"')))
if callable(getattr(crud, "_ish_brakimi", None)):
    check("_ish_brakimi: belgi bilan boshlansa True",
          crud._ish_brakimi(_Loss(1, 1, reason=f"{BELGI} — x")) is True)
    check("_ish_brakimi: o'rtada bo'lsa False",
          crud._ish_brakimi(_Loss(1, 1, reason=f"izoh {BELGI}")) is False)
    check("_ish_brakimi: None sabab — False",
          crud._ish_brakimi(_Loss(1, 1, reason=None)) is False)
else:
    for _l in ("_ish_brakimi: belgi bilan boshlansa True",
               "_ish_brakimi: o'rtada bo'lsa False",
               "_ish_brakimi: None sabab — False"):
        check(_l, False, "funksiya yo'q")


# ════════════════════════════════════════════════════════════════
bolim("H. 18-band: HTTP DELETE /api/finished/loss/{id}")
# ════════════════════════════════════════════════════════════════
import contextlib  # noqa: E402
import io  # noqa: E402
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(db, "bb_admin", "Parol123!", UserRole.ADMIN, "BB", company_id=1)
client = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = client.post("/login", data={"username": "bb_admin", "password": "Parol123!"},
                  follow_redirects=False)
check("login (admin, A korxona)", _lr.status_code == 302, str(_lr.status_code))

# o'z ishlab chiqarish braki → 400, hech narsa o'zgarmaydi
fp_h = yangi_peno_fp(1, PENO_A_ID)
FP_H_ID = fp_h.id
rh = crud.record_finished_product_production_brak(
    db, FP_H_ID, brak_qty=3, created_by="t", company_id=1)
hh1 = holat(FP_H_ID, PENO_A_ID, 1)
_r = client.delete(f"/api/finished/loss/{rh.get('loss_id')}")
check("o'z ishlab chiqarish braki → 400", _r.status_code == 400, f"{_r.status_code} {_r.text[:200]}")
try:
    _d = _r.json().get("detail")
except Exception:
    _d = None
check("400 javobi `detail.message` shaklida (UI o'qiydi)",
      isinstance(_d, dict) and _d.get("success") is False
      and "Ishlab chiqarish brakini" in (_d.get("message") or ""), str(_d))
check("HTTP rad etilgach holat bir xil", holat(FP_H_ID, PENO_A_ID, 1) == hh1,
      str((hh1, holat(FP_H_ID, PENO_A_ID, 1))))

# begona korxonaning ishlab chiqarish braki → 404 (400 EMAS — oracle yo'q)
hb1 = holat(FP_IB_ID, PENO_B_ID, 2)
_r = client.delete(f"/api/finished/loss/{LOSS_IB_ID}")
check("begona ishlab chiqarish braki → 404", _r.status_code == 404, f"{_r.status_code} {_r.text[:200]}")
check("begona korxonada hech narsa o'zgarmadi", holat(FP_IB_ID, PENO_B_ID, 2) == hb1)

# yo'q yozuv → 404
_r = client.delete("/api/finished/loss/99999999")
check("yo'q yozuv → 404", _r.status_code == 404, f"{_r.status_code}")

# oddiy brak → 200 va to'liq tiklanadi, takror → 404
fp_ho = yangi_peno_fp(1, PENO_A_ID, qty=6, cost=60_000)
FP_HO_ID = fp_ho.id
rho = crud.record_finished_product_loss(db, _Loss(FP_HO_ID, 2), created_by="t", company_id=1)
_r = client.delete(f"/api/finished/loss/{rho['loss_id']}")
check("oddiy brak → 200", _r.status_code == 200, f"{_r.status_code} {_r.text[:200]}")
db.expire_all()
_fpho = db.query(FinishedProduct).filter(FinishedProduct.id == FP_HO_ID).first()
check("oddiy brak — miqdor 4 -> 6, tan narx 60 000",
      float(_fpho.quantity) == 6.0 and abs(float(_fpho.cost_price) - 60_000) < 0.01,
      str((_fpho.quantity, _fpho.cost_price)))
_r = client.delete(f"/api/finished/loss/{rho['loss_id']}")
check("oddiy brak takror → 404", _r.status_code == 404, f"{_r.status_code}")


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 60}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
