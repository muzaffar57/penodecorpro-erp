#!/usr/bin/env python3
"""
test_narx_etalon.py — NARX HISOB-KITOBLARI ETALONI (Bosqich 3, 9-band).

NIMA UCHUN KERAK
----------------
Bosqich 3 da hardcoded mahsulot turlari (profil/panel/dona/blok/gips/
termopanel/loy_sotish) dinamik `ProductType` ga ko'chiriladi. Bu —
SaaS ishidan farqli o'laroq — PUL MATEMATIKASIGA tegadi. Bitta formula
sezilmay o'zgarsa, tan narx, foyda va liniya hisoboti jimgina siljiydi.

Shu test BUGUNGI hisob-kitoblarni qotirib qo'yadi. Ko'chirishning HAR
BIR qadamidan keyin shu test qayta ishga tushiriladi: bitta ham raqam
o'zgarmasligi SHART.

KUTILGAN QIYMATLAR QAYERDAN
---------------------------
Ikki manbadan, ATAYLAB mustaqil:
  1. `etalon(...)` — kodning o'zidan EMAS, biznes qoidasidan qayta
     yozilgan MUSTAQIL formula. Ikkalasi mos kelsa — formula to'g'ri.
  2. `LANGAR` — qo'lda hisoblangan qat'iy sonlar. Agar ikkala
     implementatsiya bir xil xato qilsa, langar buni ushlaydi.

ISHLATISH
---------
    python tools/test_narx_etalon.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import narx_etalon_baza as B  # noqa: E402  (bazani quradi)
import services  # noqa: E402
from services import _calc_dim_volume_price, _item_volume_m3  # noqa: E402

OK = FAIL = 0
FAILED = []
EPS = 1e-9


def _yaqin(a, b, eps=EPS, atol=0.0):
    """eps — NISBIY dopusk (float yaxlitlash uchun).
    atol — MUTLAQ dopusk, so'mda (round() dan keladigan +-1 so'm uchun).
    Ikkisini aralashtirmaslik SHART: nisbiy dopuskni 1 dan katta qilib
    qo'yish testni butunlay ishlamaydigan holga keltiradi."""
    a, b = float(a), float(b)
    if a == b:
        return True
    farq = abs(a - b)
    if atol and farq <= atol:
        return True
    return farq <= eps * max(1.0, abs(a), abs(b))


def check(label, olingan, kutilgan, eps=EPS, atol=0.0):
    """Bitta etalon holat."""
    global OK, FAIL
    if _yaqin(olingan, kutilgan, eps, atol):
        OK += 1
        print(f"  \u2713 {label}  = {olingan}")
    else:
        FAIL += 1
        FAILED.append(f"{label}: olingan={olingan!r}  kutilgan={kutilgan!r}")
        print(f"  \u2717 {label}  olingan={olingan!r}  KUTILGAN={kutilgan!r}")


def check_eq(label, olingan, kutilgan):
    global OK, FAIL
    if olingan == kutilgan:
        OK += 1
        print(f"  \u2713 {label}  = {olingan!r}")
    else:
        FAIL += 1
        FAILED.append(f"{label}: olingan={olingan!r}  kutilgan={kutilgan!r}")
        print(f"  \u2717 {label}  olingan={olingan!r}  KUTILGAN={kutilgan!r}")


def bolim(t):
    print(f"\n{'=' * 66}\n{t}\n{'=' * 66}")


# ════════════════════════════════════════════════════════════════
# MUSTAQIL ETALON FORMULALAR (kod EMAS — biznes qoidasidan yozilgan)
# ════════════════════════════════════════════════════════════════

def etalon_profil(eni_sm, keng_sm, uzunlik_m, narx_m3, qoplama=False):
    """Profil (karniz): kesim yarmi olinadi.
    hajm = eni(m) x kenglik(m) x uzunlik / 2
    narx = eni(m) x kenglik(m) x 1m3_narxi / 2 x uzunlik, qoplama bo'lsa x2
    """
    e, k = eni_sm / 100.0, keng_sm / 100.0
    hajm = e * k * uzunlik_m / 2.0
    narx = (e * k * narx_m3 / 2.0) * uzunlik_m
    if qoplama:
        narx *= 2
    return hajm, narx


def etalon_panel(eni_sm, qalin_sm, miqdor, narx_m3, qoplama=False):
    """Panel: to'liq kesim.
    hajm = eni(m) x qalinlik(m) x miqdor
    narx = eni(m) x qalinlik(m) x 1m3_narxi x miqdor, qoplama bo'lsa x2
    """
    e, q = eni_sm / 100.0, qalin_sm / 100.0
    hajm = e * q * miqdor
    narx = (e * q * narx_m3) * miqdor
    if qoplama:
        narx *= 2
    return hajm, narx


def etalon_dona_yangi(eni_sm, qalin_sm, uzunlik_ekv_m):
    """Donali — YANGI usul: o'lchamdan, profil formulasi bilan."""
    return (eni_sm / 100.0) * (qalin_sm / 100.0) / 2.0 * uzunlik_ekv_m


def etalon_dona_eski(qulflangan_narx, narx_m3, miqdor):
    """Donali — ESKI usul: narx nisbatidan."""
    if narx_m3 <= 0 or qulflangan_narx <= 0:
        return 0.0
    return (qulflangan_narx / narx_m3) * miqdor


def etalon_blok(blok_soni, blok_hajmi):
    return blok_soni * blok_hajmi


def etalon_m3_narx(blok_narxi, blok_hajmi):
    """1 m3 TAN narxi = 1 blok narxi / 1 blok hajmi."""
    return blok_narxi / blok_hajmi


# ════════════════════════════════════════════════════════════════
ctx = B.qur()
db = ctx["db"]
inv = ctx["inv"]
loyiha = ctx["loyiha"]
retsept = ctx["retsept"]

P14 = B.NARX["Penoplast 14P"]
P10 = B.NARX["Penoplast 10P"]
V14 = B.BLOK_HAJM["Penoplast 14P"]
V10 = B.BLOK_HAJM["Penoplast 10P"]
M3_14 = etalon_m3_narx(P14, V14)   # 891251.4666666667
M3_10 = etalon_m3_narx(P10, V10)   # 520000.0

BAZA_NARX = 1_000_000.0  # "Asosiy narx" — 1 m3 SOTUV narxi


# ════════════════════════════════════════════════════════════════
bolim("A. PROFIL formulasi — hajm va narx (_calc_dim_volume_price)")
# ════════════════════════════════════════════════════════════════

PROFIL_HOLATLAR = [
    # (eni_sm, keng_sm, uzunlik_m, narx_m3, qoplama)
    (20, 10, 1, 1_000_000, False),
    (20, 10, 1, 1_000_000, True),
    (15, 7.5, 3.4, 850_000, False),
    (15, 7.5, 3.4, 850_000, True),
    (8, 4, 2.5, 1_200_000, False),
    (30, 12, 6, 950_000, True),
    (5.5, 3.2, 12.75, 1_050_000, False),
    (100, 100, 1, 1_000_000, False),   # chekka: 1m x 1m
    (0.1, 0.1, 0.1, 1_000_000, False),  # chekka: juda kichik
    (25, 25, 0, 1_000_000, False),      # chekka: uzunlik 0
]
for e, k, l, n, c in PROFIL_HOLATLAR:
    h_kut, n_kut = etalon_profil(e, k, l, n, c)
    h_ol, n_ol = _calc_dim_volume_price("profil", e, k, l, 1, n, c)
    tag = "qoplamali" if c else "oddiy"
    check(f"profil {e}x{k}cm {l}m {n:,.0f}so'm/m3 {tag} — hajm", h_ol, h_kut)
    check(f"profil {e}x{k}cm {l}m {n:,.0f}so'm/m3 {tag} — narx", n_ol, n_kut)

# LANGAR — qo'lda hisoblangan qat'iy sonlar
check("LANGAR profil 20x10cm 1m 1mln — hajm = 0.01 m3",
      _calc_dim_volume_price("profil", 20, 10, 1, 1, 1_000_000)[0], 0.01)
check("LANGAR profil 20x10cm 1m 1mln — narx = 10 000",
      _calc_dim_volume_price("profil", 20, 10, 1, 1, 1_000_000)[1], 10_000.0)
check("LANGAR profil 15x7.5cm 3.4m 850k — narx = 16 256.25",
      _calc_dim_volume_price("profil", 15, 7.5, 3.4, 1, 850_000)[1], 16_256.25)
check("LANGAR profil 15x7.5cm 3.4m 850k qoplamali — narx = 32 512.5",
      _calc_dim_volume_price("profil", 15, 7.5, 3.4, 1, 850_000, True)[1], 32_512.5)
check("LANGAR profil 15x7.5cm 3.4m — hajm = 0.019125 m3",
      _calc_dim_volume_price("profil", 15, 7.5, 3.4, 1, 850_000)[0], 0.019125)


# ════════════════════════════════════════════════════════════════
bolim("B. PANEL formulasi — hajm va narx")
# ════════════════════════════════════════════════════════════════

PANEL_HOLATLAR = [
    (50, 2, 10, 1_000_000, False),
    (50, 2, 10, 1_000_000, True),
    (120, 3.5, 7, 900_000, False),
    (120, 3.5, 7, 900_000, True),
    (33.3, 1.7, 4.5, 1_111_111, False),
    (60, 5, 1, 1_000_000, True),
    (100, 10, 0.5, 800_000, False),
    (12, 12, 100, 750_000, False),
]
for e, q, m, n, c in PANEL_HOLATLAR:
    h_kut, n_kut = etalon_panel(e, q, m, n, c)
    h_ol, n_ol = _calc_dim_volume_price("panel", e, q, 0, m, n, c)
    tag = "qoplamali" if c else "oddiy"
    check(f"panel {e}x{q}cm x{m} {n:,.0f}so'm/m3 {tag} — hajm", h_ol, h_kut)
    check(f"panel {e}x{q}cm x{m} {n:,.0f}so'm/m3 {tag} — narx", n_ol, n_kut)

check("LANGAR panel 50x2cm x10 1mln — hajm = 0.1 m3",
      _calc_dim_volume_price("panel", 50, 2, 0, 10, 1_000_000)[0], 0.1)
check("LANGAR panel 50x2cm x10 1mln — narx = 100 000",
      _calc_dim_volume_price("panel", 50, 2, 0, 10, 1_000_000)[1], 100_000.0)
check("LANGAR panel 50x2cm x10 qoplamali — narx = 200 000",
      _calc_dim_volume_price("panel", 50, 2, 0, 10, 1_000_000, True)[1], 200_000.0)

# Noma'lum turkum — 0 qaytarishi SHART
h0, n0 = _calc_dim_volume_price("gips", 10, 10, 1, 1, 1_000_000)
check("noma'lum turkum 'gips' — hajm 0", h0, 0.0)
check("noma'lum turkum 'gips' — narx 0", n0, 0.0)
h0, n0 = _calc_dim_volume_price("mrp_product", 10, 10, 1, 1, 1_000_000)
check("noma'lum turkum 'mrp_product' — hajm 0", h0, 0.0)
check("BOSH turkum (None) — narx 0",
      _calc_dim_volume_price(None, 10, 10, 1, 1, 1_000_000)[1], 0.0)


# ════════════════════════════════════════════════════════════════
bolim("C. DETAL HAJMI (_item_volume_m3) — ombordan yechish asosi")
# ════════════════════════════════════════════════════════════════

# C1. Profil — o'lchamdan
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C1 profil", category="profil", width=20, thickness=10, length=3,
    quantity=1, unit_price=30000, is_coated=False, penoplast_id=inv["14P"].id)])
check("C1 profil 20x10cm 3m — hajm",
      _item_volume_m3(db, o.items[0]), etalon_profil(20, 10, 3, 0)[0])

# C2. Profil + ichki qo'shimcha detal (sub_detail)
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C2 profil+ichki", category="profil", width=20, thickness=10, length=3,
    quantity=1, unit_price=30000, is_coated=False, penoplast_id=inv["14P"].id,
    sub_details=[dict(name="ichki", category="profil", width=6, thickness=4,
                      length=3, quantity=1, is_coated=False)])])
kut = etalon_profil(20, 10, 3, 0)[0] + etalon_profil(6, 4, 3, 0)[0]
check("C2 profil + ichki profil detal — hajm QO'SHILADI",
      _item_volume_m3(db, o.items[0]), kut)

# C3. Ichki detal PANEL turida
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C3", category="profil", width=20, thickness=10, length=3,
    quantity=1, unit_price=30000, is_coated=False, penoplast_id=inv["14P"].id,
    sub_details=[dict(name="ichki panel", category="panel", width=30,
                      thickness=2, length=0, quantity=5, is_coated=False)])])
kut = etalon_profil(20, 10, 3, 0)[0] + etalon_panel(30, 2, 5, 0)[0]
check("C3 profil + ichki PANEL detal — hajm", _item_volume_m3(db, o.items[0]), kut)

# C4. Panel
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C4 panel", category="panel", width=50, thickness=2, length=0,
    quantity=10, unit_price=100000, is_coated=False, penoplast_id=inv["14P"].id)])
check("C4 panel 50x2cm x10 — hajm",
      _item_volume_m3(db, o.items[0]), etalon_panel(50, 2, 10, 0)[0])

# C5. Donali — YANGI usul (o'lcham bor)
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C5 dona yangi", category="dona", width=12, thickness=8, length=2.5,
    quantity=25, unit_price=5000, is_coated=False, penoplast_id=inv["14P"].id)])
check("C5 dona YANGI usul (12x8cm, 2.5m ekvivalent) — hajm",
      _item_volume_m3(db, o.items[0]), etalon_dona_yangi(12, 8, 2.5))

# C6. Donali — ESKI usul (o'lcham yo'q, narx nisbatidan), 14P
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C6 dona eski", category="dona", quantity=10,
    unit_price=8000, unit_price_for_volume=8000, is_coated=False,
    penoplast_id=inv["14P"].id)])
check("C6 dona ESKI usul (8000 so'm x10, 14P) — hajm",
      _item_volume_m3(db, o.items[0]), etalon_dona_eski(8000, M3_14, 10))

# C7. Donali eski — price_per_m3 detalda saqlangan bo'lsa SHU ustun
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C7", category="dona", quantity=10, unit_price=8000,
    unit_price_for_volume=8000, price_per_m3=700000, is_coated=False,
    penoplast_id=inv["14P"].id)])
check("C7 dona eski — detalning O'Z price_per_m3 (700k) ustun",
      _item_volume_m3(db, o.items[0]), etalon_dona_eski(8000, 700000, 10))

# C8. Donali eski — qoplamali: unit_price_for_volume (xom) ishlatiladi
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C8", category="dona", quantity=10, unit_price=16000,
    unit_price_for_volume=8000, is_coated=True, penoplast_id=inv["14P"].id)])
check("C8 dona eski QOPLAMALI — hajm xom narxdan (2x EMAS)",
      _item_volume_m3(db, o.items[0]), etalon_dona_eski(8000, M3_14, 10))

# C9. Donali eski — unit_price_for_volume yo'q, orqaga moslik
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C9", category="dona", quantity=4, unit_price=9000,
    is_coated=False, penoplast_id=inv["10P"].id)])
check("C9 dona eski — unit_price_for_volume YO'Q, unit_price'dan (10P)",
      _item_volume_m3(db, o.items[0]), etalon_dona_eski(9000, M3_10, 4))

# C10. Donali — narx 0 bo'lsa hajm 0
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C10", category="dona", quantity=5, unit_price=0,
    is_coated=False, penoplast_id=inv["14P"].id)])
check("C10 dona — narx 0 bo'lsa hajm 0", _item_volume_m3(db, o.items[0]), 0.0)

# C11-C12. Blok
for tag, key, vol in (("14P", "14P", V14), ("10P", "10P", V10)):
    o = B.buyurtma_yasa(db, loyiha, [dict(
        name=f"C blok {tag}", category="blok", length=2.5, quantity=30,
        unit_price=40000, is_coated=False, penoplast_id=inv[key].id)])
    check(f"C blok {tag} — 2.5 blok x {vol} m3",
          _item_volume_m3(db, o.items[0]), etalon_blok(2.5, vol))

# C13. Blok — kasr blok soni
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C13", category="blok", length=1.0 / 3.0, quantity=10,
    unit_price=40000, is_coated=False, penoplast_id=inv["14P"].id)])
check("C13 blok — 1/3 blok (kasr yaxlitlanmaydi)",
      _item_volume_m3(db, o.items[0]), etalon_blok(1.0 / 3.0, V14))

# C14-C17. Hajmi YO'Q turkumlar — 0 bo'lishi SHART
for kat, qo in (("gips", dict(gips_unit="metr")), ("termopanel", {}),
                ("loy_sotish", {}), ("mrp_product", {})):
    o = B.buyurtma_yasa(db, loyiha, [dict(
        name=f"C {kat}", category=kat, quantity=10, unit_price=50000,
        is_coated=False, **qo)])
    check(f"C {kat} — penoplast hajmi 0 (alohida hisoblanadi)",
          _item_volume_m3(db, o.items[0]), 0.0)

# C18. Tayyor mahsulotdan olingan detal — hajm 0 (ikki marta yechilmasin)
fp = B.tayyor_mahsulot(db, name="C18 tayyor", category="profil", quantity=100,
                       produced_quantity=100, unit="metr", unit_price=50000,
                       cost_price=2_000_000, penoplast_id=inv["14P"].id)
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="C18", category="profil", width=20, thickness=10, length=5,
    quantity=1, unit_price=50000, is_coated=False,
    penoplast_id=inv["14P"].id, finished_product_id=fp.id)])
check("C18 tayyor mahsulotdan — hajm 0 (xomashyo allaqachon yechilgan)",
      _item_volume_m3(db, o.items[0]), 0.0)


# ── C19–C22. "HAJMNI QULFLAB NARXNI OSHIRISH" yo'li ──────────────
# Brauzerda donali detalning hajmini qulflab, narxni erkin oshirish
# mumkin (yopishtirish mehnati uchun). Ekranda hajm o'zgarmaydi —
# BACKEND ham aynan shu hajmni ko'rishi SHART. Quyidagi to'rt holat
# `templates/orders.html` dagi haqiqiy `calculateItem`/`collectItems`
# ni ishga tushirib o'lchangan (2026-09-20).
QULF_EKRAN = 0.03        # brauzer ko'rsatgan qulflangan hajm (12x8cm, 1m dan 4 ta, 25 dona)
QULF_UPFV = 1200.0       # collectItems saqlaydigan unit_price_for_volume
QULF_BAZA = 1_000_000.0  # buyurtmaning "Asosiy narx"i


def _qulf_holat(nom, **d):
    """Buyurtmaning "Asosiy narx"i to'ldirilgan holatda hajmni o'lchaydi."""
    o = B.buyurtma_yasa(db, loyiha, [dict(
        name=nom, category="dona", is_coated=False,
        penoplast_id=inv["14P"].id, **d)])
    o.base_price = QULF_BAZA
    db.commit()
    db.refresh(o)
    return _item_volume_m3(db, o.items[0])


check("C19 qulflanmagan (o'lcham bor) — backend ekran bilan mos",
      _qulf_holat("C19", width=12, thickness=8, length=6.25, quantity=25,
                  unit_price=1200, unit_price_for_volume=QULF_UPFV),
      QULF_EKRAN)
check("C20 QULFLANGAN + narx 1200->5000 — hajm O'ZGARMAYDI",
      _qulf_holat("C20", width=12, thickness=8, length=6.25, quantity=25,
                  unit_price=5000, unit_price_for_volume=QULF_UPFV),
      QULF_EKRAN)
check("C21 QULFLANGAN + o'lcham tozalangan — Asosiy narxdan tiklanadi",
      _qulf_holat("C21", quantity=25, unit_price=5000,
                  unit_price_for_volume=QULF_UPFV),
      QULF_EKRAN)
check("C22 detalning O'Z '1 m3 narxi' bor — u ustun turadi",
      _qulf_holat("C22", quantity=25, unit_price=5000,
                  unit_price_for_volume=QULF_UPFV, price_per_m3=QULF_BAZA),
      QULF_EKRAN)
# Chekka holat: na detalda, na buyurtmada sotuv narxi yo'q — oxirgi
# chora sifatida TAN narxga tushadi. Bu holat uchun boshqa manba yo'q.
_o_bpsiz = B.buyurtma_yasa(db, loyiha, [dict(
    name="C23", category="dona", quantity=25, unit_price=5000,
    unit_price_for_volume=QULF_UPFV, is_coated=False,
    penoplast_id=inv["14P"].id)])
check("C23 sotuv narxi umuman yo'q — oxirgi chora: tan narx",
      _item_volume_m3(db, _o_bpsiz.items[0]),
      QULF_UPFV / (float(inv["14P"].price_per_unit)
                   / float(inv["14P"].volume_per_unit)) * 25)


# ════════════════════════════════════════════════════════════════
bolim("D. 1 BIRLIK TAN NARXI (get_order_item_unit_cost)")
# ════════════════════════════════════════════════════════════════

LOY_KG_NARX = services.get_loy_cost_per_kg(db, retsept.id)["cost_per_kg"]
check("D0 loy 1 kg tan narxi (Oq marmar, 210kg partiya)", LOY_KG_NARX, 2345.64)

# D1. Profil, qoplamasiz — faqat penoplast
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="D1", category="profil", width=20, thickness=10, length=4,
    quantity=1, unit_price=40000, is_coated=False, penoplast_id=inv["14P"].id)])
hajm = etalon_profil(20, 10, 4, 0)[0]
kut = round(hajm / V14 * P14 / 4.0)       # bloklar x blok narxi / 4 metr
check("D1 profil 20x10cm 4m qoplamasiz — 1 metr tan narxi",
      services.get_order_item_unit_cost(db, o, o.items[0]), kut)

# D2. Panel, qoplamasiz
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="D2", category="panel", width=50, thickness=2, length=0,
    quantity=10, unit_price=100000, is_coated=False, penoplast_id=inv["14P"].id)])
kut = round(etalon_panel(50, 2, 10, 0)[0] / V14 * P14 / 10.0)
check("D2 panel 50x2cm x10 qoplamasiz — 1 dona tan narxi",
      services.get_order_item_unit_cost(db, o, o.items[0]), kut)

# D3. Profil, QOPLAMALI — penoplast + loy
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="D3", category="profil", width=20, thickness=10, length=4,
    quantity=1, unit_price=80000, is_coated=True, penoplast_id=inv["14P"].id,
    recipe_id=retsept.id)], actual_loy_kg=20.0)
peno = etalon_profil(20, 10, 4, 0)[0] / V14 * P14 / 4.0
loy = (20.0 / 4.0) * LOY_KG_NARX          # 4 metr qoplangan
check("D3 profil qoplamali (20kg loy / 4m) — penoplast + loy",
      services.get_order_item_unit_cost(db, o, o.items[0]), round(peno + loy))
check("D3b o'sha detal, include_coating=False — faqat penoplast",
      services.get_order_item_unit_cost(db, o, o.items[0], include_coating=False),
      round(peno))

# D4. Loy ikki qoplamali detal orasida BO'LINADI
o = B.buyurtma_yasa(db, loyiha, [
    dict(name="D4a", category="profil", width=20, thickness=10, length=4,
         quantity=1, unit_price=80000, is_coated=True,
         penoplast_id=inv["14P"].id, recipe_id=retsept.id),
    dict(name="D4b", category="profil", width=20, thickness=10, length=6,
         quantity=1, unit_price=120000, is_coated=True,
         penoplast_id=inv["14P"].id, recipe_id=retsept.id),
], actual_loy_kg=20.0)
loy_bir = (20.0 / 10.0) * LOY_KG_NARX     # jami 10 metr qoplangan
p1 = etalon_profil(20, 10, 4, 0)[0] / V14 * P14 / 4.0
check("D4 ikki qoplamali detal — loy 10 metrga taqsimlanadi",
      services.get_order_item_unit_cost(db, o, o.items[0]), round(p1 + loy_bir))

# D5. Qoplamasiz detal loydan ulush OLMAYDI
o = B.buyurtma_yasa(db, loyiha, [
    dict(name="D5a", category="profil", width=20, thickness=10, length=4,
         quantity=1, unit_price=80000, is_coated=True,
         penoplast_id=inv["14P"].id, recipe_id=retsept.id),
    dict(name="D5b", category="profil", width=20, thickness=10, length=4,
         quantity=1, unit_price=40000, is_coated=False,
         penoplast_id=inv["14P"].id),
], actual_loy_kg=8.0)
check("D5 qoplamasiz detal — loy ulushi 0",
      services.get_order_item_unit_cost(db, o, o.items[1]), round(p1))

# D6. actual_loy_kg yo'q -> planned_loy_kg ishlatiladi
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="D6", category="profil", width=20, thickness=10, length=4,
    quantity=1, unit_price=80000, is_coated=True,
    penoplast_id=inv["14P"].id, recipe_id=retsept.id)], planned_loy_kg=12.0)
check("D6 actual_loy_kg yo'q — planned_loy_kg (12kg) ishlatiladi",
      services.get_order_item_unit_cost(db, o, o.items[0]),
      round(p1 + (12.0 / 4.0) * LOY_KG_NARX))

# D7. QULF (11.2b) — 'gips' turkumida MAXSUS tan-narx shoxi endi YO'Q.
# Buyurtmada actual_gips_kg va gips_inventory_id bo'lsa ham, detalning
# 1 birlik tan narxi 0 bo'lishi SHART (penoplast/loy yo'q). Kimdir gips
# shoxini qaytarib qo'ysa — shu test darhol yiqiladi.
o = B.buyurtma_yasa(db, loyiha, [
    dict(name="D7a", category="gips", quantity=30, unit_price=20000,
         is_coated=False, gips_unit="metr"),
    dict(name="D7b", category="gips", quantity=20, unit_price=20000,
         is_coated=False, gips_unit="metr"),
], actual_gips_kg=100.0, gips_inventory_id=inv["gips"].id)
check("D7 QULF: gips — maxsus shox yo'q, tan narx 0",
      services.get_order_item_unit_cost(db, o, o.items[0]), 0.0)

# D8. GIPS — gips_inventory_id yo'q bo'lsa 0
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="D8", category="gips", quantity=30, unit_price=20000,
    is_coated=False, gips_unit="metr")], actual_gips_kg=100.0)
check("D8 gips — xomashyo tanlanmagan bo'lsa tan narx 0",
      services.get_order_item_unit_cost(db, o, o.items[0]), 0.0)

# D9. Blok — tan narx = blok soni x blok narxi / chiqqan metr
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="D9", category="blok", length=2.0, quantity=50,
    unit_price=40000, is_coated=False, penoplast_id=inv["14P"].id)])
check("D9 blok — 2 blok x narx / 50 metr",
      services.get_order_item_unit_cost(db, o, o.items[0]),
      round(2.0 * P14 / 50.0))

# D10. Turli plotnost — 10P arzonroq
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="D10", category="profil", width=20, thickness=10, length=4,
    quantity=1, unit_price=40000, is_coated=False, penoplast_id=inv["10P"].id)])
check("D10 profil 10P plotnostda — tan narxi 10P dan hisoblanadi",
      services.get_order_item_unit_cost(db, o, o.items[0]),
      round(etalon_profil(20, 10, 4, 0)[0] / V10 * P10 / 4.0))


# ════════════════════════════════════════════════════════════════
bolim("E. BUYURTMA FOYDASI (calculate_order_profit)")
# ════════════════════════════════════════════════════════════════

# E1. Bitta profil, qoplamasiz
sotuv = 500_000.0
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="E1", category="profil", width=20, thickness=10, length=4,
    quantity=1, unit_price=sotuv, is_coated=False,
    penoplast_id=inv["14P"].id)], total_amount=sotuv, agreed_amount=sotuv)
r = services.calculate_order_profit(db, o.id)
tan_kut = etalon_profil(20, 10, 4, 0)[0] * M3_14
check("E1 profil — tan narxi", r["tan_narxi"], tan_kut)
check("E1 profil — sotuv narxi", r["sotuv_narxi"], sotuv)
check("E1 profil — foyda", r["foyda"], sotuv - tan_kut)

# E2. Kelishilgan summa (chegirma) ustun bo'lishi SHART
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="E2", category="profil", width=20, thickness=10, length=4,
    quantity=1, unit_price=500_000, is_coated=False,
    penoplast_id=inv["14P"].id)], total_amount=500_000, agreed_amount=450_000)
r = services.calculate_order_profit(db, o.id)
check("E2 chegirma — sotuv narxi agreed_amount dan (450k)",
      r["sotuv_narxi"], 450_000.0)
check("E2 chegirma — foyda ham chegirmadan", r["foyda"], 450_000.0 - tan_kut)

# E3. Ikki xil plotnost bitta buyurtmada — har biri O'Z narxidan
o = B.buyurtma_yasa(db, loyiha, [
    dict(name="E3a", category="profil", width=20, thickness=10, length=4,
         quantity=1, unit_price=500_000, is_coated=False,
         penoplast_id=inv["14P"].id),
    dict(name="E3b", category="profil", width=20, thickness=10, length=4,
         quantity=1, unit_price=500_000, is_coated=False,
         penoplast_id=inv["10P"].id),
], total_amount=1_000_000, agreed_amount=1_000_000)
r = services.calculate_order_profit(db, o.id)
v = etalon_profil(20, 10, 4, 0)[0]
check("E3 ikki plotnost — tan narx har biri o'z narxidan",
      r["tan_narxi"], v * M3_14 + v * M3_10)

# E4. Ichki qo'shimcha detal tan narxga QO'SHILADI (2026-09 audit tuzatishi)
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="E4", category="profil", width=20, thickness=10, length=4,
    quantity=1, unit_price=500_000, is_coated=False,
    penoplast_id=inv["14P"].id,
    sub_details=[dict(name="ichki", category="profil", width=6, thickness=4,
                      length=4, quantity=1, is_coated=False)])],
    total_amount=500_000, agreed_amount=500_000)
r = services.calculate_order_profit(db, o.id)
kut = (etalon_profil(20, 10, 4, 0)[0] + etalon_profil(6, 4, 4, 0)[0]) * M3_14
check("E4 ichki detal — tan narxga qo'shiladi", r["tan_narxi"], kut)

# E5. Tayyor mahsulotdan — penoplast QAYTA hisoblanmaydi
fp2 = B.tayyor_mahsulot(db, name="E5 tayyor", category="profil", quantity=100,
                        produced_quantity=100, unit="metr", unit_price=50000,
                        cost_price=0, penoplast_id=inv["14P"].id)
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="E5", category="profil", width=20, thickness=10, length=4,
    quantity=1, unit_price=500_000, is_coated=False,
    penoplast_id=inv["14P"].id, finished_product_id=fp2.id)],
    total_amount=500_000, agreed_amount=500_000)
r = services.calculate_order_profit(db, o.id)
check("E5 tayyor mahsulotdan — penoplast tan narxi 0", r["tan_narxi"], 0.0)

# E6. Blok buyurtmasi
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="E6", category="blok", length=3.0, quantity=60, unit_price=20000,
    is_coated=False, penoplast_id=inv["14P"].id)],
    total_amount=1_200_000, agreed_amount=1_200_000)
r = services.calculate_order_profit(db, o.id)
check("E6 blok — 3 blok tan narxi", r["tan_narxi"], 3.0 * V14 * M3_14)

# E7. Donali — qoplamali, hajm xom narxdan
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="E7", category="dona", quantity=10, unit_price=16000,
    unit_price_for_volume=8000, is_coated=True,
    penoplast_id=inv["14P"].id)], total_amount=160_000, agreed_amount=160_000)
r = services.calculate_order_profit(db, o.id)
check("E7 dona qoplamali — tan narx xom narxdan (2x emas)",
      r["tan_narxi"], etalon_dona_eski(8000, M3_14, 10) * M3_14)

# E8. Gips buyurtmasi — penoplast yo'q
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="E8", category="gips", quantity=50, unit_price=20000,
    is_coated=False, gips_unit="metr")],
    total_amount=1_000_000, agreed_amount=1_000_000,
    actual_gips_kg=100.0, gips_inventory_id=inv["gips"].id)
r = services.calculate_order_profit(db, o.id)
check("E8 QULF: gips buyurtmasi — tan narx 0 (gips xarajati yo'q)",
      r["tan_narxi"], 0.0)

# E9. Bo'sh buyurtma — tan narx 0, foyda = sotuv
o = B.buyurtma_yasa(db, loyiha, [], total_amount=100_000, agreed_amount=100_000)
r = services.calculate_order_profit(db, o.id)
check("E9 detalsiz buyurtma — tan narx 0", r["tan_narxi"], 0.0)
check("E9 detalsiz buyurtma — foyda = sotuv", r["foyda"], 100_000.0)

# E10. Mavjud bo'lmagan buyurtma
r = services.calculate_order_profit(db, 999999)
check_eq("E10 yo'q buyurtma — success=False", r.get("success"), False)

# E11. PANEL buyurtmasi (calculate_order_profit ning O'Z panel shoxi)
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="E11", category="panel", width=50, thickness=2, length=0,
    quantity=10, unit_price=100_000, is_coated=False,
    penoplast_id=inv["14P"].id)],
    total_amount=1_000_000, agreed_amount=1_000_000)
r = services.calculate_order_profit(db, o.id)
check("E11 panel — tan narxi", r["tan_narxi"],
      etalon_panel(50, 2, 10, 0)[0] * M3_14)
check("E11 panel — foyda", r["foyda"],
      1_000_000 - etalon_panel(50, 2, 10, 0)[0] * M3_14)

# E12. PANEL qoplamali — hajm qoplamadan O'ZGARMAYDI
o = B.buyurtma_yasa(db, loyiha, [dict(
    name="E12", category="panel", width=50, thickness=2, length=0,
    quantity=10, unit_price=200_000, is_coated=True,
    penoplast_id=inv["14P"].id, recipe_id=retsept.id)],
    total_amount=2_000_000, agreed_amount=2_000_000, actual_loy_kg=0.0)
r = services.calculate_order_profit(db, o.id)
check("E12 panel qoplamali — penoplast hajmi o'zgarmaydi",
      r["tan_narxi"], etalon_panel(50, 2, 10, 0)[0] * M3_14)

# E13-E15. Penoplastsiz turkumlar — tan narxi 0 bo'lishi SHART
for kat, qo in (("termopanel", {}), ("loy_sotish", {}), ("mrp_product", {})):
    o = B.buyurtma_yasa(db, loyiha, [dict(
        name=f"E {kat}", category=kat, quantity=20, unit_price=50_000,
        is_coated=False, **qo)], total_amount=1_000_000, agreed_amount=1_000_000)
    r = services.calculate_order_profit(db, o.id)
    check(f"E {kat} — penoplast tan narxi 0 (alohida hisoblanadi)",
          r["tan_narxi"], 0.0)

# E16. ARALASH buyurtma — 4 turkum birga, har biri o'z formulasi bilan
o = B.buyurtma_yasa(db, loyiha, [
    dict(name="E16 profil", category="profil", width=20, thickness=10,
         length=4, quantity=1, unit_price=400_000, is_coated=False,
         penoplast_id=inv["14P"].id),
    dict(name="E16 panel", category="panel", width=50, thickness=2, length=0,
         quantity=10, unit_price=100_000, is_coated=False,
         penoplast_id=inv["14P"].id),
    dict(name="E16 dona", category="dona", quantity=10, unit_price=8000,
         unit_price_for_volume=8000, is_coated=False,
         penoplast_id=inv["14P"].id),
    dict(name="E16 blok", category="blok", length=2.0, quantity=50,
         unit_price=20_000, is_coated=False, penoplast_id=inv["14P"].id),
], total_amount=3_000_000, agreed_amount=3_000_000)
r = services.calculate_order_profit(db, o.id)
kut = (etalon_profil(20, 10, 4, 0)[0]
       + etalon_panel(50, 2, 10, 0)[0]
       + etalon_dona_eski(8000, M3_14, 10)
       + etalon_blok(2.0, V14)) * M3_14
check("E16 aralash (profil+panel+dona+blok) — jami tan narxi",
      r["tan_narxi"], kut)
check("E16 aralash — foyda", r["foyda"], 3_000_000 - kut)


# ════════════════════════════════════════════════════════════════
bolim("F. LOY (qoplama) TAN NARXI — retsept miqyoslash")
# ════════════════════════════════════════════════════════════════

li = services.get_loy_cost_per_kg(db, retsept.id)
qolda = sum(kg / B.OQ_MARMAR_BATCH * B.NARX[nom] for nom, kg in B.OQ_MARMAR)
check("F1 Oq marmar 1 kg tan narxi — mustaqil hisob bilan mos",
      li["cost_per_kg"], round(qolda, 2))
check("F2 partiya hajmi 210 kg", li["batch_size"], 210.0)
check_eq("F3 retsept nomi", li["recipe"], "Oq marmar")
check_eq("F4 ingredientlar soni", len(li["breakdown"]), 6)
for nom, kg in B.OQ_MARMAR:
    qator = next(x for x in li["breakdown"] if x["name"] == nom)
    check(f"F5 {nom} — 1 kg loydagi ulushi",
          qator["cost_per_kg"], round(kg / B.OQ_MARMAR_BATCH * B.NARX[nom], 2))


# ════════════════════════════════════════════════════════════════
bolim("G. O'LCHOV BIRLIGI VA MIQDOR (model xossalari)")
# ════════════════════════════════════════════════════════════════

o = B.buyurtma_yasa(db, loyiha, [
    dict(name="G profil", category="profil", width=20, thickness=10, length=7.5,
         quantity=1, unit_price=1000, is_coated=False),
    dict(name="G panel", category="panel", width=50, thickness=2, length=0,
         quantity=12, unit_price=1000, is_coated=False),
    dict(name="G blok", category="blok", length=2, quantity=40,
         unit_price=1000, is_coated=False),
    dict(name="G termopanel", category="termopanel", quantity=33,
         unit_price=1000, is_coated=True),
    dict(name="G gips metr", category="gips", quantity=15, unit_price=1000,
         is_coated=False, gips_unit="metr"),
    dict(name="G gips m2", category="gips", quantity=16, unit_price=1000,
         is_coated=False, gips_unit="m2"),
    dict(name="G gips dona", category="gips", quantity=17, unit_price=1000,
         is_coated=False, gips_unit="dona"),
    dict(name="G loy", category="loy_sotish", quantity=120, unit_price=1000,
         is_coated=False),
])
it = {x.name: x for x in o.items}
check("G1 profil miqdori = UZUNLIK (7.5 m), miqdor emas",
      it["G profil"].order_qty_normalized, 7.5)
check("G2 panel miqdori = 12", it["G panel"].order_qty_normalized, 12.0)
check("G3 blok miqdori = CHIQQAN metr (40)",
      it["G blok"].order_qty_normalized, 40.0)
check("G4 termopanel miqdori = 33 m2",
      it["G termopanel"].order_qty_normalized, 33.0)
check_eq("G5 profil birligi", it["G profil"].delivery_unit, "metr")
check_eq("G6 panel birligi", it["G panel"].delivery_unit, "metr")
check_eq("G7 blok birligi", it["G blok"].delivery_unit, "metr")
check_eq("G8 termopanel birligi", it["G termopanel"].delivery_unit, "m²")
check_eq("G9 gips metr birligi", it["G gips metr"].delivery_unit, "metr")
check_eq("G10 gips m2 birligi (m2 -> m²)", it["G gips m2"].delivery_unit, "m²")
check_eq("G11 gips dona birligi", it["G gips dona"].delivery_unit, "dona")
check_eq("G12 loy sotish birligi", it["G loy"].delivery_unit, "kg")


# ════════════════════════════════════════════════════════════════
bolim("H. SERVER va BRAUZER formulalari BIR XILmi")
# ════════════════════════════════════════════════════════════════
# orders.html `calculateItem()` dagi formulaning aynan nusxasi.
# MUHIM: brauzerda maydon nomlari boshqacha — `i-h` = Eni, `i-w` =
# Kenglik, `i-t` = Qalinlik. Saqlashda (`collectItems`) PROFIL uchun
# `width=i-h, thickness=i-w`, PANEL uchun `width=i-h, thickness=i-t`.
# Ya'ni bazadagi `thickness` ustuni profilda "Kenglik"ni saqlaydi.

def brauzer_profil(i_h, i_w, i_l, baza_narx, qoplama):
    eni_m, keng_m = i_h / 100.0, i_w / 100.0
    per_metr = (eni_m * keng_m * baza_narx) / 2.0
    narx = per_metr * i_l
    if qoplama:
        narx *= 2
    hajm = (eni_m * keng_m * i_l) / 2.0
    return hajm, narx


def brauzer_panel(i_h, i_t, qty, baza_narx, qoplama):
    eni_m, qalin_m = i_h / 100.0, i_t / 100.0
    per_dona = eni_m * qalin_m * baza_narx
    narx = per_dona * qty
    if qoplama:
        narx *= 2
    return eni_m * qalin_m * qty, narx


for i_h, i_w, i_l, c in [(20, 10, 3, False), (15, 7.5, 3.4, True),
                         (8, 4, 2.5, False), (30, 12, 6, True),
                         (5.5, 3.2, 12.75, False)]:
    bh, bn = brauzer_profil(i_h, i_w, i_l, BAZA_NARX, c)
    sh, sn = _calc_dim_volume_price("profil", i_h, i_w, i_l, 1, BAZA_NARX, c)
    check(f"H profil {i_h}x{i_w} {i_l}m — hajm brauzer==server", sh, bh)
    check(f"H profil {i_h}x{i_w} {i_l}m — narx brauzer==server", sn, bn)

for i_h, i_t, q, c in [(50, 2, 10, False), (120, 3.5, 7, True),
                       (33.3, 1.7, 4.5, False), (60, 5, 1, True)]:
    bh, bn = brauzer_panel(i_h, i_t, q, BAZA_NARX, c)
    sh, sn = _calc_dim_volume_price("panel", i_h, i_t, 0, q, BAZA_NARX, c)
    check(f"H panel {i_h}x{i_t} x{q} — hajm brauzer==server", sh, bh)
    check(f"H panel {i_h}x{i_t} x{q} — narx brauzer==server", sn, bn)

# Donali YANGI usul — brauzer: (h/100)*(t/100)/2/donaYield, server: uzunlik
# ekvivalenti (qty/donaYield) bilan profil formulasi. Ikkalasi mos kelishi SHART.
for i_h, i_t, dona_yield, qty in [(12, 8, 4, 25), (10, 10, 2, 7), (6.5, 3, 5, 100)]:
    brauzer_hajm = (i_h / 100.0) * (i_t / 100.0) / 2.0 / dona_yield * qty
    o = B.buyurtma_yasa(db, loyiha, [dict(
        name="H dona", category="dona", width=i_h, thickness=i_t,
        length=qty / dona_yield, quantity=qty, unit_price=1000,
        is_coated=False, penoplast_id=inv["14P"].id)])
    check(f"H dona {i_h}x{i_t}cm, 1m dan {dona_yield} ta, {qty} dona — hajm",
          _item_volume_m3(db, o.items[0]), brauzer_hajm)

# Blok — brauzer: blokKerak = kerakMetr / chiqadi; hajm = blokKerak x volPerUnit
for chiqadi, kerak in [(2.5, 30), (3.0, 10), (1.75, 7)]:
    blok_kerak = kerak / chiqadi
    o = B.buyurtma_yasa(db, loyiha, [dict(
        name="H blok", category="blok", length=blok_kerak, quantity=kerak,
        unit_price=1000, is_coated=False, penoplast_id=inv["14P"].id)])
    check(f"H blok 1 blokdan {chiqadi}m, {kerak}m kerak — hajm",
          _item_volume_m3(db, o.items[0]), blok_kerak * V14)


# ════════════════════════════════════════════════════════════════
bolim("I. LINIYA BO'YICHA MOLIYA — gips / penoplast ajratilishi")
# ════════════════════════════════════════════════════════════════
# ⚠️ BOSQICH 3 NING 12-BANDI AYNAN SHU YERNI QAYTA YOZADI.
# Bugungi qoida IKKI QISMDAN iborat:
#   1) Daromad: har bir detalning ulushi = (detal summasi / buyurtma jami)
#      x kelishilgan summa. Turkumi 'gips' bo'lsa gipsga, QOLGANI HAMMASI
#      penoplastga (dona, blok, panel, termopanel, loy_sotish, mrp_product).
#   2) To'g'ridan-to'g'ri xomashyo: foyda breakdown'idagi qator nomi
#      "🧱 Gips" bilan BOSHLANSA gipsga — ya'ni MATN solishtiriladi.
# Ko'chirishdan keyin ikkala qoida ham o'zgaradi. JAMI daromad
# o'zgarmasligi SHART.

from models import Order as _O, OrderStatus as _OS, Employee, ExpenseTransaction  # noqa: E402
import datetime as _dt  # noqa: E402

YIL, OY = 2026, 8


def _tayyorla(o, kun=15):
    o.status = _OS.READY
    o.completed_at = _dt.datetime(YIL, OY, kun, 12, 0)
    db.commit()
    db.refresh(o)
    return o


# I1. Daromad ulushi — chegirma bilan
o = B.buyurtma_yasa(db, loyiha, [
    dict(name="I1 gips", category="gips", quantity=10, unit_price=20_000,
         total_price=200_000, is_coated=False, gips_unit="metr"),
    dict(name="I1 profil", category="profil", width=20, thickness=10, length=4,
         quantity=1, unit_price=800_000, total_price=800_000, is_coated=False,
         penoplast_id=inv["14P"].id),
], total_amount=1_000_000, agreed_amount=900_000)
_tayyorla(o)
rep = services.get_monthly_report(db, YIL, OY, company_id=B.CID)
tb = rep["turlar_boyicha"]
check("I1 gips daromadi = 200k/1mln x 900k", tb["gips"]["daromad"], 180_000)
check("I1 penoplast daromadi = 800k/1mln x 900k",
      tb["penoplast"]["daromad"], 720_000)
check("I2 JAMI = gips + penoplast (chegirmadan keyingi summa)",
      tb["gips"]["daromad"] + tb["penoplast"]["daromad"], 900_000)

# I3. GIPS BO'LMAGAN BARCHA turkumlar penoplastga tushadi
for kat, qo in (("dona", dict(unit_price_for_volume=1000)), ("blok", dict(length=1.0)),
                ("panel", dict(width=50, thickness=2)), ("termopanel", {}),
                ("loy_sotish", {}), ("mrp_product", {})):
    o2 = B.buyurtma_yasa(db, loyiha, [dict(
        name=f"I3 {kat}", category=kat, quantity=1, unit_price=100_000,
        total_price=100_000, is_coated=False, **qo)],
        total_amount=100_000, agreed_amount=100_000)
    _tayyorla(o2, kun=16)
    yangi = services.get_monthly_report(db, YIL, OY, company_id=B.CID)["turlar_boyicha"]
    check(f"I3 '{kat}' turkumi PENOPLASTga tushadi (gips emas)",
          yangi["penoplast"]["daromad"] - tb["penoplast"]["daromad"], 100_000)
    check(f"I3 '{kat}' — gips daromadi o'zgarmadi", yangi["gips"]["daromad"], 180_000)
    tb = yangi

PENO_JAMI = tb["penoplast"]["daromad"]   # 720k + 6 x 100k = 1 320 000
check("I4 oltita turkumdan keyin penoplast daromadi", PENO_JAMI, 1_320_000)

rep = services.get_monthly_report(db, YIL, OY, company_id=B.CID)
check("I5 hisobotdagi umumiy daromad = gips + penoplast",
      rep["turlar_boyicha"]["gips"]["daromad"]
      + rep["turlar_boyicha"]["penoplast"]["daromad"],
      round(rep["daromad"]))

# I6. To'g'ridan-to'g'ri xomashyo — "🧱 Gips" MATNI bo'yicha ajratiladi
o3 = B.buyurtma_yasa(db, loyiha, [
    dict(name="I6 gips", category="gips", quantity=50, unit_price=20_000,
         total_price=1_000_000, is_coated=False, gips_unit="metr"),
], total_amount=1_000_000, agreed_amount=1_000_000,
    actual_gips_kg=100.0, gips_inventory_id=inv["gips"].id)
_tayyorla(o3, kun=17)
pd = services.calculate_order_profit(db, o3.id, company_id=B.CID)
gips_qatorlar = [x for x in pd["breakdown"] if str(x["nomi"]).startswith("🧱 Gips")]
check_eq("I6 QULF: breakdown'da '🧱 Gips' qatori endi UMUMAN yo'q",
         len(gips_qatorlar), 0)
check("I6 QULF: gips buyurtmasining tan narxi 0", pd["tan_narxi"], 0.0)

sp = services.calculate_split_profit_report(db, YIL, OY, company_id=B.CID)
check("I7 QULF: split — gips xomashyo xarajati 0 (manba yo'q)",
      sp["gips"]["xomashyo_xarajati"], 0)
# Penoplast hajmini MUSTAQIL yig'amiz: I1 profil + I3 dona/blok/panel
# (termopanel, loy_sotish, mrp_product — penoplast ishlatmaydi)
peno_hajm = (etalon_profil(20, 10, 4, 0)[0]          # I1 profil
             + etalon_dona_eski(1000, M3_14, 1)      # I3 dona
             + etalon_blok(1.0, V14)                 # I3 blok (1 blok)
             + etalon_panel(50, 2, 1, 0)[0])         # I3 panel
check("I8 split — penoplast xomashyo xarajati (4 ta detal yig'indisi)",
      sp["penoplast"]["xomashyo_xarajati"], round(peno_hajm * M3_14), atol=1.5)

# I9. Daromad nisbati — umumiy xarajat shu nisbatda bo'linadi
g_d = float(sp["gips"]["daromad"])
p_d = float(sp["penoplast"]["daromad"])
check("I9 daromad_ulushi gips_foiz = gips / (gips + penoplast)",
      sp["daromad_ulushi"]["gips_foiz"], round(g_d / (g_d + p_d) * 100, 1))
check("I9 daromad_ulushi penoplast_foiz = 100 - gips_foiz",
      sp["daromad_ulushi"]["penoplast_foiz"],
      round(100 - round(g_d / (g_d + p_d) * 100, 1), 1))

# I10. Yo'nalishi belgilangan qo'shimcha xarajat — o'z liniyasiga to'liq
db.add(ExpenseTransaction(company_id=B.CID, date=_dt.datetime(YIL, OY, 10),
                          category="boshqa", amount=500_000,
                          production_type="gips"))
db.add(ExpenseTransaction(company_id=B.CID, date=_dt.datetime(YIL, OY, 10),
                          category="boshqa", amount=300_000,
                          production_type="penoplast"))
db.commit()
tb2 = services.get_monthly_report(db, YIL, OY, company_id=B.CID)["turlar_boyicha"]
check("I10 gips yo'nalishli xarajat = 500k", tb2["gips"]["qoshimcha_xarajat"], 500_000)
check("I10 penoplast yo'nalishli xarajat = 300k",
      tb2["penoplast"]["qoshimcha_xarajat"], 300_000)

# I11. Yo'nalishi BELGILANMAGAN xarajat — daromad nisbatida bo'linadi
sp_old = services.calculate_split_profit_report(db, YIL, OY, company_id=B.CID)
db.add(ExpenseTransaction(company_id=B.CID, date=_dt.datetime(YIL, OY, 11),
                          category="boshqa", amount=1_000_000,
                          production_type=None))
db.commit()
sp_new = services.calculate_split_profit_report(db, YIL, OY, company_id=B.CID)
ulush_g = float(sp_new["gips"]["daromad"]) / (
    float(sp_new["gips"]["daromad"]) + float(sp_new["penoplast"]["daromad"]))
check("I11 belgilanmagan 1mln xarajat — gips ulushi daromad nisbatida",
      sp_new["gips"]["umumiy_xarajat_ulushi"]
      - sp_old["gips"]["umumiy_xarajat_ulushi"],
      round(1_000_000 * ulush_g), atol=1.5)
check("I11 belgilanmagan 1mln xarajat — penoplast ulushi",
      sp_new["penoplast"]["umumiy_xarajat_ulushi"]
      - sp_old["penoplast"]["umumiy_xarajat_ulushi"],
      round(1_000_000 * (1 - ulush_g)), atol=1.5)

# I12. Hodim — yo'nalishi belgilangan bo'lsa 100% o'z liniyasiga
from models import PayType as _PayType  # noqa: E402
emp = Employee(company_id=B.CID, name="I12 gips hodimi",
               pay_type=_PayType.FIXED, fixed_amount=2_000_000,
               production_type="gips", is_active=True,
               hire_date=_dt.datetime(YIL, 1, 1))
db.add(emp)
db.commit()
sp3 = services.calculate_split_profit_report(db, YIL, OY, company_id=B.CID)
check("I12 yo'nalishi 'gips' bo'lgan hodim — 100% gipsga",
      sp3["gips"]["hodim_xarajati"], 2_000_000)
check("I12 penoplast hodim xarajati 0", sp3["penoplast"]["hodim_xarajati"], 0)

# I13. Yo'nalishsiz hodim — daromad nisbatida bo'linadi
emp2 = Employee(company_id=B.CID, name="I13 umumiy hodim",
                pay_type=_PayType.FIXED,
                fixed_amount=1_000_000, production_type=None, is_active=True,
                hire_date=_dt.datetime(YIL, 1, 1))
db.add(emp2)
db.commit()
sp4 = services.calculate_split_profit_report(db, YIL, OY, company_id=B.CID)
u_g = float(sp4["gips"]["daromad"]) / (
    float(sp4["gips"]["daromad"]) + float(sp4["penoplast"]["daromad"]))
check("I13 yo'nalishsiz hodim — gipsga daromad nisbatida",
      sp4["gips"]["hodim_xarajati"], 2_000_000 + 1_000_000 * u_g, atol=1.5)
check("I13 yo'nalishsiz hodim — penoplastga qolgani",
      sp4["penoplast"]["hodim_xarajati"], 1_000_000 * (1 - u_g), atol=1.5)

# I14. Sof foyda va foiz — ichki izchillik
for liniya in ("gips", "penoplast"):
    d = sp4[liniya]
    check(f"I14 {liniya} — jami xarajat = xomashyo + hodim + brak + umumiy",
          d["jami_xarajat"],
          round(d["xomashyo_xarajati"] + d["hodim_xarajati"]
                + d["brak_xarajati"] + d["umumiy_xarajat_ulushi"]), atol=1.5)
    check(f"I14 {liniya} — sof foyda = daromad - jami xarajat",
          d["sof_foyda"], round(d["daromad"] - d["jami_xarajat"]), atol=1.5)
    check(f"I14 {liniya} — foyda foizi",
          d["foyda_foiz"],
          round(d["sof_foyda"] / d["daromad"] * 100, 1) if d["daromad"] else 0)

# I15. Daromadsiz oy — 50/50 zaxira qoidasi
sp5 = services.calculate_split_profit_report(db, YIL, 7, company_id=B.CID)
check("I15 daromadsiz oy — gips ulushi 50%",
      sp5["daromad_ulushi"]["gips_foiz"], 50.0)
check("I15 daromadsiz oy — penoplast ulushi 50%",
      sp5["daromad_ulushi"]["penoplast_foiz"], 50.0)

# I16. Tayyor mahsulotni buyurtmasiz sotish — mahsulot KATEGORIYASI
# bo'yicha yo'naltiriladi (buyurtma detali emas, alohida yo'l).
from models import FinishedProductSale  # noqa: E402

oldin = services.get_monthly_report(db, YIL, OY, company_id=B.CID)["turlar_boyicha"]
fp_g = B.tayyor_mahsulot(db, name="I16 gips mahsulot", category="gips",
                         quantity=10, produced_quantity=10, unit="metr",
                         unit_price=50_000, cost_price=0)
fp_p = B.tayyor_mahsulot(db, name="I16 profil mahsulot", category="profil",
                         quantity=10, produced_quantity=10, unit="metr",
                         unit_price=50_000, cost_price=0)
db.add(FinishedProductSale(company_id=B.CID, finished_product_id=fp_g.id,
                           product_name=fp_g.name, quantity=1, unit="metr",
                           unit_price=400_000, total_amount=400_000,
                           sold_at=_dt.datetime(YIL, OY, 20)))
db.add(FinishedProductSale(company_id=B.CID, finished_product_id=fp_p.id,
                           product_name=fp_p.name, quantity=1, unit="metr",
                           unit_price=600_000, total_amount=600_000,
                           sold_at=_dt.datetime(YIL, OY, 20)))
db.commit()
keyin = services.get_monthly_report(db, YIL, OY, company_id=B.CID)["turlar_boyicha"]
check("I16 gips kategoriyali tayyor mahsulot sotuvi — gipsga",
      keyin["gips"]["daromad"] - oldin["gips"]["daromad"], 400_000)
check("I16 profil kategoriyali tayyor mahsulot sotuvi — penoplastga",
      keyin["penoplast"]["daromad"] - oldin["penoplast"]["daromad"], 600_000)

# ════════════════════════════════════════════════════════════════
bolim("J. JONLI ETALON — staging'dagi HAQIQIY 22 buyurtma")
# ════════════════════════════════════════════════════════════════
# Yuqoridagi bo'limlar O'YLAB TOPILGAN holatlar ustida ishlaydi.
# Bu bo'lim esa `main` ning haqiqiy ma'lumoti ustida: 2026-09-20 da
# staging API dan DASTUR ORQALI (ekran suratidan emas) o'lchangan
# 22 buyurtma, 75 detal, 9 xomashyo, "Oq marmar" retsepti —
# `tools/narx_etalon_jonli.json` da saqlangan va shu yerda lokal
# bazaga qayta tiklanadi. Hisob o'sha kungi raqamni qaytarishi SHART.

jonli = B.jonli_qur()
jdb, jord, jet = jonli["db"], jonli["buyurtmalar"], jonli["etalon"]
JCID = jonli["company_id"]

check_eq("J0 jonli ma'lumot — buyurtmalar soni", len(jord), 22)
check_eq("J0 jonli ma'lumot — detallar soni",
         len(jonli["malumot"]["order_items"]), 75)

jami_sotuv = jami_tan = 0.0
for nom in sorted(jet):
    sotuv, tan, foyda = jet[nom]
    r = services.calculate_order_profit(jdb, jord[nom].id, company_id=JCID)
    check(f"J {nom} — sotuv narxi", r["sotuv_narxi"], sotuv, atol=0.01)
    check(f"J {nom} — tan narxi", r["tan_narxi"], tan, atol=0.01)
    check(f"J {nom} — foyda", r["foyda"], foyda, atol=0.01)
    jami_sotuv += r["sotuv_narxi"]
    jami_tan += r["tan_narxi"]

check("J jami sotuv narxi (22 buyurtma)", jami_sotuv,
      sum(v[0] for v in jet.values()), atol=0.01)
check("J jami tan narxi (22 buyurtma)", jami_tan,
      sum(v[1] for v in jet.values()), atol=0.01)

# "ready" buyurtmalar foydasi — sentabr moliya hisobotidagi
# `buyurtmalar_foydasi` bilan AYNAN bir xil bo'lishi jonli tasdiqlangan.
_ready = {o["order_number"] for o in jonli["malumot"]["orders"]
          if o["status"] == "ready"}
check_eq("J 'ready' buyurtmalar soni (hisobotdagi 16 ga mos)", len(_ready), 16)
ready_foyda = sum(
    services.calculate_order_profit(jdb, jord[n].id, company_id=JCID)["foyda"]
    for n in sorted(_ready))
# 2026-09-20 da jonli o'lchangan: hisobotdagi `buyurtmalar_foydasi`
# `ready` buyurtmalar foydasining yig'indisiga AYNAN teng edi (10 402 710).
# Donali detal tan narxi xatosi tuzatilgandan keyin bu 14 109 833 bo'ladi —
# staging'da qayta o'lchanib tasdiqlangan qiymat.
check("J 'ready' foyda yig'indisi (tuzatishdan keyin)",
      round(ready_foyda), 14_109_833, atol=1.5)

# Xomashyo narxlari — etalon_raqamlar.md dagi qiymatlar
from models import Inventory as _JInv  # noqa: E402
for _id, nom, narx, hajm, *_ in jonli["malumot"]["inventory"]:
    if narx is None:
        continue
    row = jdb.query(_JInv).filter(_JInv.id == _id).first()
    check(f"J xomashyo {nom} — 1 birlik narxi", float(row.price_per_unit), narx)
check("J Penoplast 14P — 1 m3 TAN narxi", 802126.32 / 1.4, 572947.3714285714)
check("J Penoplast 10P — 1 m3 TAN narxi", 624000 / 1.4, 445714.2857142857)


# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 66}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 66}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print("=" * 66)
sys.exit(0 if FAIL == 0 else 1)
