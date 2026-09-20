#!/usr/bin/env python3
"""
test_kategoriyalar.py — buyurtma oynasida qaysi turkum ko'rinadi.

NIMA UCHUN
----------
Bosqich 3, 11-band eski qattiq kodlangan turkumlarni bittalab MRP ga
ko'chiradi. Ko'chirilgan turkum buyurtma oynasidan YO'QOLISHI, lekin
kodi va eski yozuvlari BUZILMASLIGI kerak.

Uchta daraja bor:
  ASOSIY    — profil / panel / dona. Har doim ko'rinadi, o'chirib
              bo'lmaydi. Bular ATAYLAB qattiq kodda qoladi.
  IXTIYORIY — termopanel / gips / loy_sotish. Sozlanmagan korxonada
              yoqiq (eski xatti-harakat buzilmasin).
  ESKIRGAN  — blok. Faqat ATAYLAB yoqilganda ko'rinadi. O'rniga MRP.

ISHLATISH
---------
    python tools/test_kategoriyalar.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "kategoriya_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import main  # noqa: E402
import crud  # noqa: E402
from database import SessionLocal  # noqa: E402
from production_models import Company  # noqa: E402

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
db.commit()


# ════════════════════════════════════════════════════════════════
bolim("A. Ro'yxatlar to'g'ri ajratilganmi")
# ════════════════════════════════════════════════════════════════
asosiy = set(main._ASOSIY_KATEGORIYALAR)
ixtiyoriy = {k for k, _ in main.IXTIYORIY_KATEGORIYALAR}
eskirgan = set(main._ESKIRGAN_KATEGORIYALAR)

check("asosiy = profil, panel, dona", asosiy == {"profil", "panel", "dona"})
check("blok endi asosiy EMAS", "blok" not in asosiy)
check("blok ixtiyoriylar ichida", "blok" in ixtiyoriy)
check("blok eskirgan deb belgilangan", eskirgan == {"blok"})
check("eskirganlar ixtiyoriylarning ichida", eskirgan <= ixtiyoriy)
check("asosiy va ixtiyoriy kesishmaydi", not (asosiy & ixtiyoriy))


# ════════════════════════════════════════════════════════════════
bolim("B. Hech qachon sozlanmagan korxona")
# ════════════════════════════════════════════════════════════════
for k in ("profil", "panel", "dona"):
    check(f"{k} — ko'rinadi (asosiy)", main.cat_on(k, 1) is True)
for k in ("termopanel", "gips", "loy_sotish"):
    check(f"{k} — ko'rinadi (eski xatti-harakat saqlandi)",
          main.cat_on(k, 1) is True)
check("blok — KO'RINMAYDI (eskirgan)", main.cat_on("blok", 1) is False)


# ════════════════════════════════════════════════════════════════
bolim("C. Korxona blokni ATAYLAB yoqsa")
# ════════════════════════════════════════════════════════════════
crud.set_setting(db, "enabled_categories", "blok,gips", company_id=1)
main._clear_category_cache(1)
check("blok — endi ko'rinadi", main.cat_on("blok", 1) is True)
check("gips — ko'rinadi", main.cat_on("gips", 1) is True)
check("termopanel — endi ko'rinmaydi (ro'yxatda yo'q)",
      main.cat_on("termopanel", 1) is False)
check("loy_sotish — ko'rinmaydi", main.cat_on("loy_sotish", 1) is False)
check("profil — baribir ko'rinadi (asosiy, o'chirib bo'lmaydi)",
      main.cat_on("profil", 1) is True)


# ════════════════════════════════════════════════════════════════
bolim("D. Sozlama korxonaga xos (tenant)")
# ════════════════════════════════════════════════════════════════
main._clear_category_cache(2)
check("B korxonada blok — hamon ko'rinmaydi",
      main.cat_on("blok", 2) is False)
check("B korxonada termopanel — ko'rinadi (u sozlamagan)",
      main.cat_on("termopanel", 2) is True)


# ════════════════════════════════════════════════════════════════
bolim("E. Bo'sh ro'yxat — hamma ixtiyoriysi o'chadi")
# ════════════════════════════════════════════════════════════════
crud.set_setting(db, "enabled_categories", "", company_id=1)
main._clear_category_cache(1)
for k in ("blok", "gips", "termopanel", "loy_sotish"):
    check(f"{k} — o'chdi", main.cat_on(k, 1) is False)
for k in ("profil", "panel", "dona"):
    check(f"{k} — baribir yoqiq", main.cat_on(k, 1) is True)


# ════════════════════════════════════════════════════════════════
bolim("F. Shablonlar shartni haqiqatan qo'llaydimi")
# ════════════════════════════════════════════════════════════════
for fayl, nechta in (("orders.html", 2), ("finished.html", 2)):
    yol = os.path.join(ROOT, "templates", fayl)
    matn = open(yol, encoding="utf-8").read()
    shartli = matn.count("cat_on('blok'")
    check(f"{fayl} — blok tanlovlari shartga o'ralgan ({shartli} ta)",
          shartli >= nechta)
    # Shartsiz qolgan blok tugmasi bo'lmasligi kerak
    import re as _re
    ochiq = [ln for ln in matn.splitlines()
             if 'data-value="blok"' in ln and "cat_on('blok'" not in ln
             and ".type-opt.active" not in ln and "fp-cat-opt" not in ln]
    check(f"{fayl} — shartsiz blok tugmasi qolmadi", not ochiq)

# Jinja shablonlari hamon o'qiladimi
from jinja2 import Environment, FileSystemLoader  # noqa: E402
env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "templates")))
env.globals["cat_on"] = main.cat_on
for f in ("orders.html", "finished.html", "production.html"):
    try:
        env.get_template(f)
        check(f"{f} — Jinja sintaksisi to'g'ri", True)
    except Exception as e:
        check(f"{f} — Jinja sintaksisi to'g'ri ({e})", False)


# ════════════════════════════════════════════════════════════════
bolim("G. Eski blok yozuvi hamon to'g'ri hisoblanadi")
# ════════════════════════════════════════════════════════════════
# Turkum yashirilgani — KOD o'chirilgani DEGANI EMAS. Ilgari yozilgan
# blok detali avvalgidek hajm/birlik/miqdor berishi SHART.
import services  # noqa: E402
from models import (  # noqa: E402
    Inventory, Project, Order, OrderItem, OrderType, ProjectStatus,
)

peno = Inventory(company_id=1, item_name="Penoplast sinov", unit="dona",
                 stock_quantity=100, price_per_unit=800000,
                 volume_per_unit=1.4, is_penoplast=True,
                 is_default_penoplast=True)
db.add(peno)
db.flush()
loyiha = Project(company_id=1, project_number="PRJ-K", client_name="S",
                 project_name="S", status=ProjectStatus.DRAFT)
db.add(loyiha)
db.flush()
o = Order(company_id=1, order_number="K-001", project_id=loyiha.id,
          order_type=OrderType.PRODUCT, total_amount=600000,
          agreed_amount=600000)
db.add(o)
db.flush()
it = OrderItem(company_id=1, order_id=o.id, name="Eski blok detali",
               category="blok", length=2.5, quantity=30, unit_price=20000,
               total_price=600000, is_coated=False, penoplast_id=peno.id)
db.add(it)
db.commit()

check("eski blok — hajm = 2.5 blok x 1.4 m3",
      abs(services._item_volume_m3(db, it) - 3.5) < 1e-9)
check("eski blok — miqdor CHIQQAN metr (30)",
      it.order_qty_normalized == 30.0)
check("eski blok — birligi metr", it.delivery_unit == "metr")
r = services.calculate_order_profit(db, o.id, company_id=1)
check("eski blok — tan narxi hisoblanadi",
      abs(r["tan_narxi"] - 3.5 * (800000 / 1.4)) < 0.01)


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 60}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
