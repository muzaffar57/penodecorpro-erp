#!/usr/bin/env python3
"""
test_nom_noyobligi.py — mahsulot turi va retsept varianti nomlari.

NIMA UCHUN
----------
2026-09-20 da aniqlandi: `ProductType.name` va `BOM.variant_name` da
hech qanday takrorlanmaslik sharti yo'q edi. Bitta korxona aynan bir
xil nomli ikkita tur (yoki bitta mahsulotga ikkita "Standart" retsept)
yaratishi mumkin edi — ishlab chiqarish oynasidagi ro'yxatda ular bir
xil ko'rinardi va operator qaysi biri qaysiligini ajrata olmasdi.

Xavfli emas edi (hisob buzilmaydi), lekin o'zi sozlaydigan tizimda
tez chalkashtiradi.

  A. Tur nomi — takrorlanmaydi (katta/kichik harf va bo'sh joy ham)
  B. Nofaol turning nomini QAYTA ishlatish mumkin
  C. Boshqa korxona bemalol o'sha nomni ishlatadi (tenant)
  D. Retsept varianti — bitta mahsulot ichida takrorlanmaydi
  E. Boshqa mahsulotda o'sha variant nomi bemalol
  F. Tahrirlashda ham tekshiriladi, o'zini o'zi bloklamaydi

ISHLATISH
---------
    python tools/test_nom_noyobligi.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "nom_noyobligi_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from database import SessionLocal  # noqa: E402
from production_models import Company, ProductType, BOM  # noqa: E402
from models import Inventory  # noqa: E402
import auth  # noqa: E402

db = SessionLocal()
OK = FAIL = 0
FAILED = []


def check(label, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}  {extra}")


def bolim(t):
    print(f"\n{'=' * 60}\n{t}\n{'=' * 60}")


for cid, nom in ((1, "A"), (2, "B")):
    if not db.query(Company).filter(Company.id == cid).first():
        db.add(Company(id=cid, name=nom))
db.flush()
mat = Inventory(company_id=1, item_name="Sinov material", unit="kg",
                stock_quantity=100, price_per_unit=1000, volume_per_unit=1)
db.add(mat)
db.commit()
MAT_ID = mat.id


# ── Har bir korxona uchun soxta foydalanuvchi ──────────────────
class _User:
    def __init__(self, cid):
        self.id = cid
        self.company_id = cid
        self.username = f"u{cid}"
        self.full_name = f"User {cid}"
        self.role = "admin"
        self.is_active = True


_joriy = {"u": _User(1)}
main.app.dependency_overrides[auth.admin_or_warehouse] = lambda: _joriy["u"]
main.app.dependency_overrides[auth.admin_only] = lambda: _joriy["u"]
main.app.dependency_overrides[auth.admin_or_manager] = lambda: _joriy["u"]
c = TestClient(main.app)

TUR = dict(unit="metr", input_template="quantity_only", pricing_formula="unit_based")


def tur_yarat(nom, cid=1):
    _joriy["u"] = _User(cid)
    return c.post("/api/production/product-types", json={"name": nom, **TUR})


def retsept_yarat(pt_id, variant, cid=1):
    _joriy["u"] = _User(cid)
    return c.post("/api/production/boms", json={
        "product_type_id": pt_id, "variant_name": variant, "batch_quantity": 1,
        "items": [{"inventory_id": MAT_ID, "quantity": 1, "scrap_factor_percent": 0,
                   "is_optional": False, "is_coating": False,
                   "component_type": "raw_material"}]})


# ════════════════════════════════════════════════════════════════
bolim("A. Tur nomi takrorlanmaydi")
# ════════════════════════════════════════════════════════════════
r1 = tur_yarat("Termopanel qolip 25x50")
check("birinchi tur yaratildi", r1.status_code == 200, str(r1.status_code))
PT1 = r1.json()["id"]

r2 = tur_yarat("Termopanel qolip 25x50")
check("AYNAN bir xil nom — rad etildi", r2.status_code == 400, str(r2.status_code))
check("xabar tushunarli", "allaqachon bor" in r2.text, r2.text[:80])

r3 = tur_yarat("termopanel QOLIP 25x50")
check("katta/kichik harf farqi ham — rad etildi", r3.status_code == 400)

r4 = tur_yarat("  Termopanel qolip 25x50  ")
check("oldi-keti bo'sh joy ham — rad etildi", r4.status_code == 400)

r5 = tur_yarat("Termopanel qolip 30x60")
check("BOSHQA nom — qabul qilindi", r5.status_code == 200)
PT2 = r5.json()["id"]
check("nom tozalab saqlanadi (bo'sh joysiz)",
      r5.json()["name"] == "Termopanel qolip 30x60")


# ════════════════════════════════════════════════════════════════
bolim("B. Nofaol turning nomi qayta ishlatiladi")
# ════════════════════════════════════════════════════════════════
_joriy["u"] = _User(1)
c.delete(f"/api/production/product-types/{PT1}")
r6 = tur_yarat("Termopanel qolip 25x50")
check("nofaol qilingandan keyin o'sha nom bo'sh bo'ladi",
      r6.status_code == 200, str(r6.status_code))
PT1 = r6.json()["id"] if r6.status_code == 200 else PT1


# ════════════════════════════════════════════════════════════════
bolim("C. Boshqa korxonaga xalaqit bermaydi")
# ════════════════════════════════════════════════════════════════
r7 = tur_yarat("Termopanel qolip 25x50", cid=2)
check("B korxona o'sha nomni bemalol ishlatadi", r7.status_code == 200,
      str(r7.status_code))


# ════════════════════════════════════════════════════════════════
bolim("D. Retsept varianti — bitta mahsulot ichida")
# ════════════════════════════════════════════════════════════════
b1 = retsept_yarat(PT1, "Standart")
check("birinchi retsept yaratildi", b1.status_code == 200, b1.text[:90])
BOM1 = b1.json()["id"]

b2 = retsept_yarat(PT1, "Standart")
check("bir xil variant nomi — rad etildi", b2.status_code == 400, str(b2.status_code))
check("xabar tushunarli", "allaqachon bor" in b2.text, b2.text[:80])

b3 = retsept_yarat(PT1, "standart")
check("katta/kichik harf farqi ham — rad etildi", b3.status_code == 400)

b4 = retsept_yarat(PT1, "Kleysiz")
check("BOSHQA variant — qabul qilindi", b4.status_code == 200)
BOM2 = b4.json()["id"]


# ════════════════════════════════════════════════════════════════
bolim("E. Boshqa mahsulotda o'sha variant nomi mumkin")
# ════════════════════════════════════════════════════════════════
b5 = retsept_yarat(PT2, "Standart")
check("30x60 mahsulotida ham 'Standart' bo'la oladi", b5.status_code == 200,
      str(b5.status_code))


# ════════════════════════════════════════════════════════════════
bolim("F. Tahrirlash")
# ════════════════════════════════════════════════════════════════
_joriy["u"] = _User(1)
u1 = c.put(f"/api/production/boms/{BOM2}", json={
    "product_type_id": PT1, "variant_name": "Standart", "batch_quantity": 1,
    "items": [{"inventory_id": MAT_ID, "quantity": 1, "scrap_factor_percent": 0,
               "is_optional": False, "is_coating": False,
               "component_type": "raw_material"}]})
check("mavjud boshqa variant nomiga o'zgartirish — rad etildi",
      u1.status_code == 400, str(u1.status_code))

u2 = c.put(f"/api/production/boms/{BOM2}", json={
    "product_type_id": PT1, "variant_name": "Kleysiz", "batch_quantity": 2,
    "items": [{"inventory_id": MAT_ID, "quantity": 1, "scrap_factor_percent": 0,
               "is_optional": False, "is_coating": False,
               "component_type": "raw_material"}]})
check("O'Z nomi bilan saqlash — ishlaydi (o'zini bloklamaydi)",
      u2.status_code == 200, u2.text[:90])


# ════════════════════════════════════════════════════════════════
bolim("G. Bir xil material retseptda IKKI MARTA bo'la oladi")
# ════════════════════════════════════════════════════════════════
# Bu — ataylab ruxsat: "2 ta podveska majburiy + 2 ta ixtiyoriy"
# naqshi aynan shunga tayanadi (2 yoki 4 dona chiqadi).
_joriy["u"] = _User(1)
b6 = c.post("/api/production/boms", json={
    "product_type_id": PT2, "variant_name": "Podveska sinovi", "batch_quantity": 1,
    "items": [
        {"inventory_id": MAT_ID, "quantity": 2, "scrap_factor_percent": 0,
         "is_optional": False, "is_coating": False, "component_type": "raw_material"},
        {"inventory_id": MAT_ID, "quantity": 2, "scrap_factor_percent": 0,
         "is_optional": True, "is_coating": False, "component_type": "raw_material"},
    ]})
check("bir material: 2 majburiy + 2 ixtiyoriy — qabul qilindi",
      b6.status_code == 200, b6.text[:90])
if b6.status_code == 200:
    check("ikkala qator ham saqlandi", len(b6.json()["items"]) == 2)


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 60}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
