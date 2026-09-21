#!/usr/bin/env python3
"""
test_qoplama_vaqti.py — 22-band: qoplamachi bonusi (va ishlab chiqarish
miqdoriga bog'liq hodim to'lovi) FAQAT mahsulot "Sotuvga tayyor" (READY)
bo'lganda, va u TAYYOR BO'LGAN oyda hisoblanadi.

NIMA UCHUN KERAK (2026-09-21)
-----------------------------
FOYDALANUVCHI QARORI: "2" — bonus mahsulot "Tayyor" bo'lganda hisoblansin
(ish haqiqatan bitganda), ishlab chiqarishga qo'yilganda emas.

Asl kod (kech17 + 21-band, O'LCHANGAN — `work/probe22.py`):
`services.get_monthly_report` ichidagi `direct_produced` so'rovi
mahsulot HOLATINI umuman ko'rmasdi va oyni `created_at` (ishlab
chiqarishga QO'YILGAN sana) bo'yicha ajratardi. Ikki xato:

  (a) JARAYONDAGI (IN_PROGRESS), ya'ni hali qoplanmagan qoplamali
      mahsulot darhol bonusga kirardi: 10 metr → +10 000 so'm. "Tayyor"
      bosilganda bonus BOSHQA o'zgarmasdi — ya'ni haq ish BITGANI uchun
      emas, ish BOSHLANGANI uchun to'lanardi.
  (b) Avgustda boshlanib sentyabrda tayyor bo'lgan mahsulot AVGUST oyiga
      tushardi (o'lchandi: avgust bonusi 7 000, sentyabr 0) — yopilgan
      oyning hisoboti keyin o'zgarib ketardi.

TUZATMA: so'rovga `production_status == READY` qo'shildi va oy
`coalesce(finished_production_at, created_at)` bo'yicha ajratiladi
(eski yozuvlarda ustun bo'sh — o'shalar uchun `created_at`, tarix
buzilmasin). Bu buyurtmalar bilan SIMMETRIK: buyurtma detallari ham
faqat buyurtma READY bo'lgan va `completed_at` shu oyga tushgan holatda
hisoblanadi.

QAMROV
------
A. Jarayondagi qoplamali mahsulot — bonus 0; "Tayyor" bosilgach qo'shiladi
B. Oy chegarasi — tayyor bo'lgan oyga tushadi, yaratilgan oyga EMAS
C. Eski yozuv (`finished_production_at` bo'sh) — `created_at` ga qaytadi
D. Qoplamasiz / gips — hech qachon bonusga kirmaydi (holatdan qat'iy nazar)
E. Jarayondagi mahsulot o'chirilsa — bonus umuman tebranmaydi
F. Hodim to'lovi (`fixed_plus_coating`) — aynan shu qoidaga ergashadi
G. Korxona filtri — begona korxona mahsuloti bonusga kirmaydi
H. Statik — so'rovda holat va sana filtri bor

ISHLATISH
---------
    python tools/test_qoplama_vaqti.py
    TENANT_FILTER=1 python tools/test_qoplama_vaqti.py

Asl kodga qarshi ham QULAMAYDI (mutatsiya uchun): hisobot chaqiruvlari
`try/except` bilan o'ralgan.

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "qoplama_vaqti_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth, services                          # noqa: E402

from database import SessionLocal, engine          # noqa: E402
import tenant_context as _tc                       # noqa: E402

engine.dispose()

from datetime import datetime                      # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Inventory, FinishedProduct, ProductionStatus, StockSource,
    Employee, PayType,
)
from fastapi.testclient import TestClient          # noqa: E402

db = SessionLocal()
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {detail}")


def section(t):
    print(f"\n--- {t} ---")


def yaqin(a, b, eps=1e-6):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="Test Korxona B"))
    db.commit()

with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "QV_admin", "Parol123!", UserRole.ADMIN, "QV Admin",
                     company_id=1)

PENO = Inventory(company_id=1, item_name="QV Penoplast", unit="blok",
                 stock_quantity=100000.0, price_per_unit=200000,
                 volume_per_unit=1.0, is_penoplast=True,
                 is_default_penoplast=True)
db.add(PENO)
db.commit()
P_ID = PENO.id

NOW = datetime.utcnow()
YIL, OY = NOW.year, NOW.month
OLD_YIL, OLD_OY = (YIL - 1, 12) if OY == 1 else (YIL, OY - 1)

client = TestClient(main.app, base_url="https://testserver",
                    raise_server_exceptions=False)
_r = client.post("/login", data={"username": "QV_admin", "password": "Parol123!"},
                 follow_redirects=False)
assert _r.status_code == 302, f"login bo'lmadi: {_r.status_code}"


def req(method, url, **kw):
    """Server istisnosi skriptni qulatmasin (asl kodga qarshi mutatsiya)."""
    try:
        return getattr(client, method)(url, **kw)
    except Exception as e:          # pragma: no cover — himoya qatlami
        class _R:
            status_code = 599
            text = f"ISTISNO: {type(e).__name__}: {e}"

            def json(self):
                return {}
        return _R()


def hisobot(yil=None, oy=None, cid=1):
    """Hisobot — istisno bo'lsa ham skript qulamaydi (mutatsiya himoyasi)."""
    db.expire_all()
    try:
        return services.get_monthly_report(db, yil or YIL, oy or OY,
                                           company_id=cid)
    except Exception as e:          # pragma: no cover
        return {"__xato": f"{type(e).__name__}: {e}",
                "qoplamachi_bonus_avtomatik": None, "jami_metr": None,
                "jami_dona": None, "hodimlar_moslashuvchan_xarajat": None,
                "hodimlar_moslashuvchan_breakdown": []}


def bonus(yil=None, oy=None, cid=1):
    return hisobot(yil, oy, cid).get("qoplamachi_bonus_avtomatik")


def ishlab(nom, coated=True, uzunlik=10.0):
    """`produce` — JARAYONDAGI (IN_PROGRESS) mahsulot yaratadi."""
    r = req("post", "/api/finished/produce", json={
        "name": nom, "category": "profil", "is_coated": coated,
        "penoplast_id": P_ID, "price_per_m3": 100000, "unit_price": 50000,
        "loy_kg": 0, "recipe_id": None, "notes": None,
        "width": 10, "thickness": 10, "length": uzunlik, "quantity": 1})
    if r.status_code != 200:
        return 0
    try:
        return r.json().get("product_id") or 0
    except Exception:               # pragma: no cover
        return 0


def sana_qoy(fp_id, yaratilgan=None, tayyor="YOZILMAYDI"):
    db.expire_all()
    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    if not fp:
        return None
    if yaratilgan is not None:
        fp.created_at = yaratilgan
    if tayyor != "YOZILMAYDI":
        fp.finished_production_at = tayyor
    db.commit()
    return fp


def holat(fp_id):
    db.expire_all()
    fp = db.query(FinishedProduct).filter(FinishedProduct.id == fp_id).first()
    return fp.production_status if fp else None


print("=" * 66)
print("22-BAND DARVOZASI — qoplamachi bonusi FAQAT 'Tayyor' mahsulot uchun")
print("TENANT_FILTER = " + ("1 (YOQILGAN)" if _tc.ENABLED else "0 (o'chiq)"))
print("=" * 66)

# ══════════════════════════════════════════════════════════════
section("A. Jarayondagi mahsulot bonusga KIRMAYDI, 'Tayyor' bo'lgach kiradi")
# ══════════════════════════════════════════════════════════════
b0 = bonus()
check("A0 boshlang'ich bonus 0", yaqin(b0, 0.0), f"bonus={b0}")

F1 = ishlab("QV_qoplamali_1", coated=True, uzunlik=10)
check("A1 qoplamali mahsulot yaratildi (jarayonda)",
      F1 and holat(F1) == ProductionStatus.IN_PROGRESS,
      f"id={F1} holat={holat(F1)}")
b1 = bonus()
check("A2 JARAYONDAGI mahsulot bonusni OSHIRMADI (ilgari +10 000)",
      yaqin(b1, b0), f"bonus={b1} (oldin {b0})")
check("A3 jami_metr ham oshmadi", yaqin(hisobot().get("jami_metr"), 0.0),
      f"jami_metr={hisobot().get('jami_metr')}")

r = req("post", f"/api/finished/{F1}/complete")
check("A4 'Sotuvga tayyor' → 200", r.status_code == 200,
      f"{r.status_code} {r.text[:120]}")
check("A5 holat READY va finished_production_at yozildi",
      holat(F1) == ProductionStatus.READY
      and sana_qoy(F1).finished_production_at is not None,
      f"holat={holat(F1)}")
b2 = bonus()
check("A6 endi bonus AYNAN 10 metr × 1000 = 10 000 ga oshdi",
      yaqin(b2 - b0, 10000.0), f"farq={b2 - b0}")
check("A7 jami_metr 10", yaqin(hisobot().get("jami_metr"), 10.0),
      f"jami_metr={hisobot().get('jami_metr')}")

# Haq "muzlatilgan" miqdor bo'yicha: mahsulot keyin SOTILSA yoki BRAK
# qilinsa `quantity` kamayadi, lekin hodim ishni ALLAQACHON bajargan —
# `produced_quantity` ("Tayyor" bosilgan paytdagi son) ishlatiladi.
# Bu 22-band dan OLDIN ham shunday edi; shu yerda qulflanadi, aks holda
# bu shox darvozada umuman sinalmay qolardi.
r = req("post", "/api/finished/sell", json={
    "finished_product_id": F1, "quantity": 4, "unit_price": 50000,
    "buyer_name": "QV_xaridor", "payment_method": "naqd", "master_id": None,
    "confirm_below_cost": True})
check("A8 mahsulotdan 4 metr sotildi → 200", r.status_code == 200,
      f"{r.status_code} {r.text[:150]}")
db.expire_all()
_f1 = db.query(FinishedProduct).filter(FinishedProduct.id == F1).first()
check("A9 qoldiq 10 → 6, `produced_quantity` esa 10 bo'lib qoldi",
      _f1 is not None and yaqin(_f1.quantity, 6.0)
      and yaqin(_f1.produced_quantity, 10.0),
      f"qoldiq={_f1.quantity if _f1 else None} asl={_f1.produced_quantity if _f1 else None}")
check("A10 SOTILGANDAN keyin ham bonus 10 000 — haq kamaymadi",
      yaqin(bonus() - b0, 10000.0), f"farq={bonus() - b0}")
check("A11 jami_metr hamon 10 (joriy qoldiq 6 emas)",
      yaqin(hisobot().get("jami_metr"), 10.0),
      f"jami_metr={hisobot().get('jami_metr')}")

# ══════════════════════════════════════════════════════════════
section("B. Oy chegarasi — TAYYOR bo'lgan oyga tushadi")
# ══════════════════════════════════════════════════════════════
F2 = ishlab("QV_oldingi_oyda_boshlandi", coated=True, uzunlik=7)
sana_qoy(F2, yaratilgan=datetime(OLD_YIL, OLD_OY, 15))
b_shu_oldin = bonus()
b_old_oldin = bonus(OLD_YIL, OLD_OY)
check("B1 jarayonda: na shu oy, na oldingi oy bonusi oshdi",
      yaqin(b_shu_oldin, b2) and yaqin(b_old_oldin, 0.0),
      f"shu={b_shu_oldin} oldingi={b_old_oldin}")

r = req("post", f"/api/finished/{F2}/complete")
check("B2 'Tayyor' → 200", r.status_code == 200, f"{r.status_code}")
b_shu = bonus()
b_old = bonus(OLD_YIL, OLD_OY)
check("B3 SHU oy bonusi +7 000 (tayyor bo'lgan oy)",
      yaqin(b_shu - b_shu_oldin, 7000.0), f"farq={b_shu - b_shu_oldin}")
check("B4 OLDINGI oy (yaratilgan oy) bonusi 0 — yopilgan oy buzilmadi",
      yaqin(b_old, 0.0), f"oldingi={b_old}")

# Teskari holat: oldingi oyda TAYYOR bo'lgan mahsulot shu oyga tushmaydi
F3 = ishlab("QV_oldingi_oyda_tayyor", coated=True, uzunlik=3)
req("post", f"/api/finished/{F3}/complete")
sana_qoy(F3, yaratilgan=datetime(OLD_YIL, OLD_OY, 2),
         tayyor=datetime(OLD_YIL, OLD_OY, 20))
check("B5 oldingi oyda tayyor bo'lgan mahsulot SHU oy bonusiga tushmadi",
      yaqin(bonus(), b_shu), f"bonus={bonus()} (kutilgan {b_shu})")
check("B6 u OLDINGI oy bonusiga tushdi (+3 000)",
      yaqin(bonus(OLD_YIL, OLD_OY), 3000.0), f"oldingi={bonus(OLD_YIL, OLD_OY)}")

# ══════════════════════════════════════════════════════════════
section("C. Eski yozuv — finished_production_at bo'sh bo'lsa created_at")
# ══════════════════════════════════════════════════════════════
F4 = ishlab("QV_eski_yozuv", coated=True, uzunlik=5)
req("post", f"/api/finished/{F4}/complete")
sana_qoy(F4, yaratilgan=datetime(YIL, OY, 3), tayyor=None)
b_eski = bonus()
check("C1 READY, sana ustuni BO'SH → created_at oyiga tushadi (+5 000)",
      yaqin(b_eski - bonus(OLD_YIL, OLD_OY) * 0 - b_shu, 5000.0),
      f"bonus={b_eski} (oldin {b_shu})")
sana_qoy(F4, yaratilgan=datetime(OLD_YIL, OLD_OY, 3), tayyor=None)
check("C2 eski yozuv sanasi oldingi oyga surilsa — shu oydan chiqadi",
      yaqin(bonus(), b_shu), f"bonus={bonus()} (kutilgan {b_shu})")
check("C3 va oldingi oyga qo'shiladi (3 000 + 5 000)",
      yaqin(bonus(OLD_YIL, OLD_OY), 8000.0), f"oldingi={bonus(OLD_YIL, OLD_OY)}")
sana_qoy(F4, yaratilgan=datetime(YIL, OY, 3),
         tayyor=datetime(YIL, OY, 4))     # holatni tiklaymiz
b_baza = bonus()
check("C4 holat tiklandi (shu oy = 10 000 + 7 000 + 5 000)",
      yaqin(b_baza, 22000.0), f"bonus={b_baza}")

# ══════════════════════════════════════════════════════════════
section("D. Qoplamasiz va gips — hech qachon bonusga kirmaydi")
# ══════════════════════════════════════════════════════════════
F5 = ishlab("QV_qoplamasiz", coated=False, uzunlik=20)
req("post", f"/api/finished/{F5}/complete")
check("D1 QOPLAMASIZ mahsulot tayyor bo'lsa ham bonusga kirmadi",
      yaqin(bonus(), b_baza), f"bonus={bonus()} (kutilgan {b_baza})")

GIPS = FinishedProduct(company_id=1, name="QV_gips", category="gips",
                       unit="dona", quantity=50, produced_quantity=50,
                       source=StockSource.PRODUCED, is_coated=True,
                       production_status=ProductionStatus.READY,
                       finished_production_at=datetime(YIL, OY, 5),
                       created_at=datetime(YIL, OY, 5))
db.add(GIPS)
db.commit()
check("D2 GIPS mahsuloti (READY, qoplamali) bonusga kirmadi",
      yaqin(bonus(), b_baza), f"bonus={bonus()} (kutilgan {b_baza})")
db.delete(GIPS)
db.commit()

# ══════════════════════════════════════════════════════════════
section("E. Jarayondagi mahsulot o'chirilsa — bonus tebranmaydi")
# ══════════════════════════════════════════════════════════════
F6 = ishlab("QV_ochiriladi", coated=True, uzunlik=40)
b_yaratildi = bonus()
check("E1 yaratilgandan keyin bonus o'zgarmadi", yaqin(b_yaratildi, b_baza),
      f"bonus={b_yaratildi}")
r = req("delete", f"/api/finished/{F6}")
check("E2 jarayondagi mahsulot o'chirildi → 200", r.status_code == 200,
      f"{r.status_code}")
check("E3 o'chirilgandan keyin ham bonus o'zgarmadi", yaqin(bonus(), b_baza),
      f"bonus={bonus()}")

# ══════════════════════════════════════════════════════════════
section("F. Hodim to'lovi (fixed_plus_coating) shu qoidaga ergashadi")
# ══════════════════════════════════════════════════════════════
QOP = Employee(company_id=1, name="QV_Qoplamachi",
               pay_type=PayType.FIXED_PLUS_COATING,
               fixed_amount=1_000_000, per_unit_rate=1_000,
               per_unit_type="metr", is_active=True,
               hire_date=datetime(YIL - 1, 1, 1))
db.add(QOP)
db.commit()


def qop_haqi(yil=None, oy=None):
    rep = hisobot(yil, oy)
    det = [b for b in rep.get("hodimlar_moslashuvchan_breakdown", [])
           if b.get("name") == "QV_Qoplamachi"]
    return det[0]["amount"] if det else None


h_baza = qop_haqi()
check("F1 hozirgi haq = oylik + 22 metr × 1000",
      yaqin(h_baza, 1_000_000 + 22_000), f"haq={h_baza}")
F7 = ishlab("QV_hodim_sinovi", coated=True, uzunlik=6)
check("F2 JARAYONDAGI mahsulot hodim haqini oshirmadi",
      yaqin(qop_haqi(), h_baza), f"haq={qop_haqi()} (kutilgan {h_baza})")
req("post", f"/api/finished/{F7}/complete")
check("F3 'Tayyor' bo'lgach haq +6 000",
      yaqin(qop_haqi() - h_baza, 6000.0), f"farq={qop_haqi() - h_baza}")

# ══════════════════════════════════════════════════════════════
section("G. Korxona filtri — begona mahsulot bonusga kirmaydi")
# ══════════════════════════════════════════════════════════════
b_1korxona = bonus()
BEGONA = FinishedProduct(company_id=2, name="QV_begona", category="profil",
                         unit="metr", quantity=999, produced_quantity=999,
                         source=StockSource.PRODUCED, is_coated=True,
                         production_status=ProductionStatus.READY,
                         finished_production_at=datetime(YIL, OY, 6),
                         created_at=datetime(YIL, OY, 6))
db.add(BEGONA)
db.commit()
check("G1 2-korxona mahsuloti 1-korxona bonusiga KIRMADI",
      yaqin(bonus(cid=1), b_1korxona), f"bonus={bonus(cid=1)}")
check("G2 2-korxonaning o'z bonusi hisoblandi (999 × 1000)",
      yaqin(bonus(cid=2), 999000.0), f"bonus2={bonus(cid=2)}")
db.delete(BEGONA)
db.commit()

# ══════════════════════════════════════════════════════════════
section("H. Statik — so'rovda holat va sana filtri bor")
# ══════════════════════════════════════════════════════════════
with open(os.path.join(ROOT, "services.py"), encoding="utf-8") as f:
    SERV = f.read()

check("H1 direct_produced so'rovida production_status == READY filtri bor",
      "FinishedProduct.production_status == ProductionStatus.READY" in SERV)
check("H2 oy chegarasi coalesce(finished_production_at, created_at) bilan",
      "func.coalesce(FinishedProduct.finished_production_at," in SERV)
check("H3 eski, holatni ko'rmaydigan created_at filtri QAYTMAGAN",
      "FinishedProduct.created_at >= _dp_start" not in SERV)
check("H4 `_tayyor_sana` ikkala chegarada ham ishlatiladi",
      SERV.count("_tayyor_sana >= _dp_start") == 1
      and SERV.count("_tayyor_sana < _dp_end") == 1,
      f"{SERV.count('_tayyor_sana >= _dp_start')}/{SERV.count('_tayyor_sana < _dp_end')}")
check("H5 ProductionStatus shu blokda import qilingan",
      "from models import FinishedProduct, StockSource, ProductionStatus" in SERV)

print()
print("=" * 60)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print("=" * 60)
if FAILED:
    print("Yiqilganlar:")
    for x in FAILED:
        print("  - " + x)
db.close()
sys.exit(0 if FAIL == 0 else 1)
