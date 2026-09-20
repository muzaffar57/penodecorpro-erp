#!/usr/bin/env python3
"""
test_kategoriyalar.py — buyurtma oynasida qaysi turkum ko'rinadi.

NIMA UCHUN
----------
Bosqich 3, 11-band eski qattiq kodlangan turkumlarni bittalab MRP ga
ko'chiradi. Ko'chirilgan turkum buyurtma oynasidan YO'QOLISHI, lekin
kodi va eski yozuvlari BUZILMASLIGI kerak.

To'rtta daraja bor (2026-09-21 da kodda O'LCHANGAN):
  ASOSIY    — profil / panel / dona. Har doim ko'rinadi, o'chirib
              bo'lmaydi. Bular ATAYLAB qattiq kodda qoladi.
  IXTIYORIY — loy_sotish / blok. Sozlanmagan korxonada yoqiq
              (eski xatti-harakat buzilmasin) — ESKIRGANlardan tashqari.
  ESKIRGAN  — blok. Faqat ATAYLAB yoqilganda ko'rinadi.
              O'rniga MRP dan o'z turingizni yaratasiz.
  OLIB TASHLANGAN — termopanel (11.2a) va gips (11.2b). Kodi ham,
              interfeysi ham butunlay o'chirildi, shuning uchun
              UCHALA ro'yxatda ham YO'Q.

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
check("eskirganlar = blok", eskirgan == {"blok"})
check("termopanel ro'yxatda UMUMAN yo'q (butunlay olib tashlangan)",
      "termopanel" not in ixtiyoriy and "termopanel" not in asosiy)
# 11.2b (2026-09-20): `gips` ham xuddi termopanel kabi BUTUNLAY olib
# tashlandi — endi u ixtiyoriylar ham, eskirganlar ham ro'yxatida yo'q.
check("gips ro'yxatda UMUMAN yo'q (butunlay olib tashlangan)",
      "gips" not in ixtiyoriy and "gips" not in asosiy and "gips" not in eskirgan)
check("eskirganlar ixtiyoriylarning ichida", eskirgan <= ixtiyoriy)
check("asosiy va ixtiyoriy kesishmaydi", not (asosiy & ixtiyoriy))


# ════════════════════════════════════════════════════════════════
bolim("B. Hech qachon sozlanmagan korxona")
# ════════════════════════════════════════════════════════════════
for k in ("profil", "panel", "dona"):
    check(f"{k} — ko'rinadi (asosiy)", main.cat_on(k, 1) is True)
check("loy_sotish — ko'rinadi (hali eskirmagan)",
      main.cat_on("loy_sotish", 1) is True)
check("blok — KO'RINMAYDI (eskirgan)", main.cat_on("blok", 1) is False)
# ⚠ gips ham False beradi, lekin SABABI BOSHQA: u `_ESKIRGAN_...` da emas,
# balki UCHALA ro'yxatning hech birida yo'q (11.2b da butunlay olib
# tashlangan). Ilgari ikkalasi bitta tsiklda "(eskirgan)" yorlig'i bilan
# tekshirilardi — test o'tardi, lekin AYTGAN sababi noto'g'ri edi.
# Shuning uchun har bir mexanizm alohida qulflanadi:
check("blok — ESKIRGAN ro'yxatida (shuning uchun o'chiq)",
      "blok" in main._ESKIRGAN_KATEGORIYALAR)
check("gips — ESKIRGAN ro'yxatida EMAS (butunlay olib tashlangan)",
      "gips" not in main._ESKIRGAN_KATEGORIYALAR)
check("gips — KO'RINMAYDI (hech bir ro'yxatda yo'q)",
      main.cat_on("gips", 1) is False)


# ════════════════════════════════════════════════════════════════
bolim("C. Korxona blokni ATAYLAB yoqsa")
# ════════════════════════════════════════════════════════════════
crud.set_setting(db, "enabled_categories", "blok,gips", company_id=1)
main._clear_category_cache(1)
check("blok — endi ko'rinadi", main.cat_on("blok", 1) is True)

# ⚠⚠ TUZATILDI (2026-09-21). Ilgari `cat_on` sozlama satridagi ISTALGAN
# so'zga True qaytarardi — u so'z hali mavjud turkummi, tekshirmasdi.
# Natijada 11.2b dan OLDIN yozilgan `enabled_categories` satrida "gips"
# qolgan korxonada gips shoxlari QAYTIB KELARDI, ammo admin uni sozlamalar
# sahifasida ko'rmagani uchun O'CHIRA HAM OLMASDI. Endi noma'lum so'z
# e'tiborsiz qoldiriladi va sozlama o'zi-o'zidan tozalanadi.
check("gips — eski sozlama satri uni QAYTARMAYDI",
      main.cat_on("gips", 1) is False)
check("gips — yoqilganlar to'plamiga ham tushmaydi",
      "gips" not in main.enabled_categories_of(1))

# Xuddi shu himoya `termopanel` da ham ishlashini O'LCHAB ko'rsatamiz:
crud.set_setting(db, "enabled_categories", "blok,gips,termopanel", company_id=1)
main._clear_category_cache(1)
check("termopanel — eski satrda bo'lsa HAM qaytmaydi",
      main.cat_on("termopanel", 1) is False)
check("blok — o'sha satrdagi HAQIQIY turkum esa ishlaydi",
      main.cat_on("blok", 1) is True)
crud.set_setting(db, "enabled_categories", "blok,gips", company_id=1)
main._clear_category_cache(1)

_ruxsat = {k for k, _ in main.IXTIYORIY_KATEGORIYALAR}
check("gips — admin sozlama ro'yxatida YO'Q (o'chira olmaydi)",
      "gips" not in _ruxsat)
check("termopanel — admin sozlama ro'yxatida YO'Q", "termopanel" not in _ruxsat)
check("termopanel — ko'rinmaydi (umuman yo'q)",
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
check("B korxonada gips ham ko'rinmaydi", main.cat_on("gips", 2) is False)
check("B korxonada termopanel ham yo'q", main.cat_on("termopanel", 2) is False)
check("B korxonada loy_sotish — ko'rinadi (u sozlamagan)",
      main.cat_on("loy_sotish", 2) is True)


# ════════════════════════════════════════════════════════════════
bolim("E. Bo'sh ro'yxat — hamma ixtiyoriysi o'chadi")
# ════════════════════════════════════════════════════════════════
crud.set_setting(db, "enabled_categories", "", company_id=1)
main._clear_category_cache(1)
for k in ("blok", "gips", "loy_sotish"):
    check(f"{k} — o'chdi", main.cat_on(k, 1) is False)
for k in ("profil", "panel", "dona"):
    check(f"{k} — baribir yoqiq", main.cat_on(k, 1) is True)


# ════════════════════════════════════════════════════════════════
bolim("F. Shablonlar shartni haqiqatan qo'llaydimi")
# ════════════════════════════════════════════════════════════════
import glob as _glob
for turkum in ("blok", "gips"):
    ochiq_jami = []
    for yol in _glob.glob(os.path.join(ROOT, "templates", "*.html")):
        matn = open(yol, encoding="utf-8").read()
        for ln in matn.splitlines():
            if f'data-value="{turkum}"' not in ln and f'value="{turkum}"' not in ln:
                continue
            if f"cat_on('{turkum}'" in ln:
                continue
            if ".type-opt.active" in ln:
                continue   # CSS qoidasi, tugma emas
            if os.path.basename(yol) == "kpi.html":
                # `kpi.html` dagi "blok" / "metr" / "dona" — HODIM TO'LOV
                # BIRLIGI (`Employee.per_unit_type`), buyurtma turkumi EMAS.
                # Usta blok kesgani uchun haq oladi — bu turkum yashirilishi
                # bilan hech qanday aloqasi yo'q va tegilmasligi SHART.
                continue
            ochiq_jami.append(os.path.basename(yol) + ": " + ln.strip()[:70])
    check(f"{turkum} — shartsiz qolgan UI joyi yo'q"
          + (f" ({ochiq_jami[:1]})" if ochiq_jami else ""), not ochiq_jami)

# Yuqoridagi istisno ATAYLAB: kpi.html dagi "blok" hodim to'lov birligi.
# Agar u kelajakda turkum tanloviga aylanib qolsa — shu tekshiruv buni
# ushlaydi (select nomi o'zgarsa yiqiladi).
kpi = open(os.path.join(ROOT, "templates", "kpi.html"), encoding="utf-8").read()
check("kpi.html dagi 'blok' — hodim to'lov birligi selectida",
      'id="e-unittype"' in kpi
      and kpi.index('id="e-unittype"') < kpi.index('<option value="blok">'))

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

# Gips va termopanel yozuvlari ham buzilmasligi SHART
o2 = Order(company_id=1, order_number="K-002", project_id=loyiha.id,
           order_type=OrderType.PRODUCT, total_amount=0, agreed_amount=0)
db.add(o2)
db.flush()
g_it = OrderItem(company_id=1, order_id=o2.id, name="Eski gips",
                 category="gips", quantity=40, unit_price=15000,
                 total_price=600000, is_coated=False, gips_unit="m2")
t_it = OrderItem(company_id=1, order_id=o2.id, name="Eski termopanel",
                 category="termopanel", quantity=25, unit_price=90000,
                 total_price=2250000, is_coated=True)
db.add_all([g_it, t_it])
db.commit()
check("eski gips — miqdor 40", g_it.order_qty_normalized == 40.0)
check("eski gips — birligi m² (gips_unit dan)", g_it.delivery_unit == "m²")
check("eski gips — penoplast hajmi 0",
      services._item_volume_m3(db, g_it) == 0.0)
check("eski termopanel — miqdor 25", t_it.order_qty_normalized == 25.0)
check("eski termopanel — birligi m²", t_it.delivery_unit == "m²")
check("eski termopanel — penoplast hajmi 0",
      services._item_volume_m3(db, t_it) == 0.0)


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 60}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
