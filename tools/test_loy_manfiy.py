#!/usr/bin/env python3
"""
test_loy_manfiy.py — 19-band: loy xomashyosi yetishmasa qoldiq MANFIYGA
tushadi, kirimda qoplanadi; qo'lda chiqim manfiy qoldiqdagi qarzni
o'chira olmaydi.

NIMA UCHUN KERAK (2026-09-21)
-----------------------------
FOYDALANUVCHI QARORI (so'zma-so'z): "ishlab chiqarish to'xtamaydi,
manfiyga tushib qoladi, omborga kirim qilinganda ayirilib tashlanadi,
shunday ishlasin".

Asl kod (O'LCHANGAN):
  * `services.deduct_loy_ingredients` — qoldiq 0 da to'xtatilardi
    (`new_qty = 0.0`), yetishmagan miqdor HECH QAYERDA qolmasdi: keyingi
    kirim uni qoplamasdi, ombor haqiqatdagidan KO'P ko'rinardi.
  * `crud.update_stock` (qo'lda chiqim, `POST /api/inventory/{id}/stock`) —
    chiqim qoldiqdan ko'p bo'lsa JIMGINA 0 ga qirqardi, jurnalga esa
    so'ralgan to'liq miqdor yozilardi (100 da 1000 chiqim → 0, "out 1000").
    Manfiy qoldiqda bu qarzni o'chirib yuborardi (-30 da 5 chiqim → 0).
    Tana tekshirilmasdi: NaN → 500, `true` → +1, 1e20 SAQLANARDI, uzun
    izoh (jurnal ustuni 200) PostgreSQL da 500.

QAMROV
------
A. Ildiz: `deduct_loy_ingredients` — manfiyga tushadi, jurnal matni,
   yetishmovchilik miqdori, harakat yozuvi, qoldiq aniq 0 da ogohlantirish yo'q
B. HTTP: produce / add / production-brak (loyli) — manfiyga tushadi, aniq
C. Kirim (`/purchase`) — manfiyni qoplaydi (to'liq / qisman), narx yangi
D. Buyurtma yaratishda loy yetishmovchiligi ogohlantirishi (409) manfiyda ham
E. Manfiy qoldiq bilan sahifa/API lar 200, qoldiq va KPI to'g'ri
F. `/stock` marshruti: chiqim chegarasi, manfiyda chiqim rad, kirim qoplaydi,
   yomon tanalar → 400 (ombor va jurnal O'ZGARMAGAN), begona/yo'q id → 404
G. Ildiz `update_stock` — to'g'ridan-to'g'ri ValueError, begona korxona → None
H. Statik: eski qirqish qatorlari qaytmagan

ISHLATISH
---------
    python tools/test_loy_manfiy.py
    TENANT_FILTER=1 python tools/test_loy_manfiy.py

Asl kodga qarshi ham QULAMAYDI (mutatsiya uchun): yangi imzo/yordamchilar
`try/except`, HTTP istisnolar 500 ga aylantiriladi.

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "loy_manfiy_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, services                    # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from sqlalchemy import event                       # noqa: E402
import tenant_context as _tc                       # noqa: E402


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


engine.dispose()

from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Inventory, Recipe, RecipeIngredient, InventoryMovement,
    FinishedProduct,
)
from fastapi.testclient import TestClient          # noqa: E402

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
    auth.create_user(db, "LM_admin", "Parol123!", UserRole.ADMIN, "LM Admin",
                     company_id=1)

# Retsept: 100 kg partiyaga 50 kg sement + 50 kg mel (1 kg loy = 0.5 + 0.5)
SEMENT = Inventory(company_id=1, item_name="LM_SEMENT", unit="kg",
                   stock_quantity=10.0, price_per_unit=1000, min_stock=5)
MEL = Inventory(company_id=1, item_name="LM_MEL", unit="kg",
                stock_quantity=1000.0, price_per_unit=500, min_stock=0)
PENO = Inventory(company_id=1, item_name="LM Penoplast", unit="blok",
                 stock_quantity=100.0, price_per_unit=200000,
                 volume_per_unit=1.0, is_penoplast=True,
                 is_default_penoplast=True)
BEGONA = Inventory(company_id=2, item_name="LM_BEGONA", unit="kg",
                   stock_quantity=50.0, price_per_unit=100)
db.add_all([SEMENT, MEL, PENO, BEGONA])
db.commit()
REC = Recipe(company_id=1, name="LM_RETSEPT", batch_size_kg=100.0)
db.add(REC)
db.commit()
db.add_all([
    RecipeIngredient(recipe_id=REC.id, inventory_id=SEMENT.id, quantity_kg=50.0),
    RecipeIngredient(recipe_id=REC.id, inventory_id=MEL.id, quantity_kg=50.0),
])
db.commit()
S_ID, M_ID, P_ID, B_ID, R_ID = SEMENT.id, MEL.id, PENO.id, BEGONA.id, REC.id


def qoldiq(inv_id):
    db.expire_all()
    r = db.query(Inventory).filter(Inventory.id == inv_id).first()
    return float(r.stock_quantity or 0) if r else None


def narx(inv_id):
    db.expire_all()
    r = db.query(Inventory).filter(Inventory.id == inv_id).first()
    return float(r.price_per_unit or 0) if r else None


def qoy(inv_id, qty, price=None):
    """Sinov holatini o'rnatish — to'g'ridan-to'g'ri (hisob emas)."""
    db.expire_all()
    r = db.query(Inventory).filter(Inventory.id == inv_id).first()
    r.stock_quantity = qty
    if price is not None:
        r.price_per_unit = price
    db.commit()


def harakatlar(inv_id):
    db.expire_all()
    return db.query(InventoryMovement).filter(
        InventoryMovement.inventory_id == inv_id).count()


def oxirgi_harakat(inv_id):
    db.expire_all()
    return db.query(InventoryMovement).filter(
        InventoryMovement.inventory_id == inv_id).order_by(
        InventoryMovement.id.desc()).first()


def login(user):
    c = TestClient(main.app, base_url="https://testserver",
                   raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": "Parol123!"},
               follow_redirects=False)
    assert r.status_code == 302, f"{user} login bo'lmadi: {r.status_code}"
    return c


C = login("LM_admin")


def req(method, url, **kw):
    """Server istisnosi skriptni qulatmasin (asl kodga qarshi mutatsiya):
    `raise_server_exceptions=False` → 500 javob."""
    try:
        return getattr(C, method)(url, **kw)
    except Exception as e:          # pragma: no cover — himoya qatlami
        class _R:
            status_code = 599
            text = f"ISTISNO: {type(e).__name__}: {e}"

            def json(self):
                return {}
        return _R()


print("=" * 66)
print("19-BAND DARVOZASI — loy manfiy qoldiq + qo'lda chiqim")
print("TENANT_FILTER = " + ("1 (YOQILGAN)" if _tc.ENABLED else "0 (o'chiq)"))
print("=" * 66)


class _Buyurtma:
    """deduct_loy_ingredients uchun soxta buyurtma (id yo'q — jurnal
    `order_id` bo'sh bo'ladi, FK buzilmaydi)."""
    def __init__(self):
        self.id = None
        self.company_id = 1
        self.order_number = "LM-SINOV"
        self.recipe_id = R_ID


# ══════════════════════════════════════════════════════════════
section("A. Ildiz: deduct_loy_ingredients — qoldiq manfiyga tushadi")
# ══════════════════════════════════════════════════════════════
qoy(S_ID, 10.0)
qoy(M_ID, 1000.0)
h0 = harakatlar(S_ID)
with contextlib.redirect_stdout(_quiet):
    log = services.deduct_loy_ingredients(db, _Buyurtma(), 40.0, use_stock=False,
                                          recipe_id=R_ID, company_id=1)
matn = "\n".join(log)
check("A1 sement 10 − 20 = −10 (0 da to'xtamadi)", yaqin(qoldiq(S_ID), -10.0),
      f"qoldiq={qoldiq(S_ID)}")
check("A2 mel 1000 − 20 = 980 (yetarli material o'zgarishsiz mantiq)",
      yaqin(qoldiq(M_ID), 980.0), f"qoldiq={qoldiq(M_ID)}")
check("A3 jurnalda 'qoldiq manfiy: -10.00 kg'", "qoldiq manfiy: -10.00 kg" in matn, matn)
check("A4 jurnalda 'keyingi kirimda qoplanadi'", "keyingi kirimda qoplanadi" in matn, matn)
check("A5 yetishmovchilik miqdori 10.00 (shu ayirishning yo'q qismi)",
      "EDI — 10.00 kg yetishmovchilik" in matn, matn)
check("A6 eski matn ('manfiyga o'tkazilmadi') YO'Q", "manfiyga o'tkazilmadi" not in matn, matn)
check("A7 mel uchun ogohlantirish YO'Q", "LM_MEL: omborda" not in matn, matn)
hm = oxirgi_harakat(S_ID)
check("A8 harakat yozuvi +1, 'out', to'liq sarf 20 kg",
      harakatlar(S_ID) == h0 + 1 and hm is not None and hm.movement_type == "out"
      and yaqin(hm.quantity, 20.0),
      f"soni={harakatlar(S_ID) - h0}, yozuv={(hm.movement_type, hm.quantity) if hm else None}")

# Qoldiq allaqachon manfiy: −10 dan yana 5 kg → −15, yetishmovchilik 5 (10 emas)
with contextlib.redirect_stdout(_quiet):
    log = services.deduct_loy_ingredients(db, _Buyurtma(), 10.0, use_stock=False,
                                          recipe_id=R_ID, company_id=1)
matn = "\n".join(log)
check("A9 manfiydan yana: −10 − 5 = −15", yaqin(qoldiq(S_ID), -15.0), f"qoldiq={qoldiq(S_ID)}")
check("A10 yetishmovchilik = shu ayirish (5.00), qoldiq −15.00",
      "EDI — 5.00 kg yetishmovchilik" in matn and "qoldiq manfiy: -15.00 kg" in matn, matn)

# Aynan 0 ga tushadi — ogohlantirish yo'q
qoy(S_ID, 5.0)
with contextlib.redirect_stdout(_quiet):
    log = services.deduct_loy_ingredients(db, _Buyurtma(), 10.0, use_stock=False,
                                          recipe_id=R_ID, company_id=1)
matn = "\n".join(log)
check("A11 5 − 5 = 0, ogohlantirish YO'Q", yaqin(qoldiq(S_ID), 0.0) and "YETARLI EMAS" not in matn,
      f"qoldiq={qoldiq(S_ID)} log={matn}")

# ══════════════════════════════════════════════════════════════
section("B. HTTP: loyli ishlab chiqarish amallari manfiyga tushadi")
# ══════════════════════════════════════════════════════════════
qoy(S_ID, 2.0)
qoy(M_ID, 1000.0)
qoy(P_ID, 100.0)
r = req("post", "/api/finished/produce", json={
    "name": "LM Karniz B1", "category": "profil", "is_coated": True,
    "penoplast_id": P_ID, "price_per_m3": None, "unit_price": 100000,
    "loy_kg": 20, "recipe_id": R_ID, "notes": None,
    "width": 10, "thickness": 10, "length": 10, "quantity": 1})
check("B1 produce loy 20 kg (sement 2, kerak 10) → 200", r.status_code == 200,
      f"{r.status_code} {r.text[:200]}")
check("B2 sement 2 − 10 = −8", yaqin(qoldiq(S_ID), -8.0), f"qoldiq={qoldiq(S_ID)}")
check("B3 mel 1000 − 10 = 990", yaqin(qoldiq(M_ID), 990.0), f"qoldiq={qoldiq(M_ID)}")
db.expire_all()
FP = db.query(FinishedProduct).filter(FinishedProduct.name == "LM Karniz B1").first()
check("B4 mahsulot yaratildi", FP is not None)
FP_ID = FP.id if FP else 0
if FP:
    r = req("post", f"/api/finished/{FP_ID}/add", json={"quantity": 5})
    check("B5 add +5 (loy proporsional) → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    db.expire_all()
    fp2 = db.query(FinishedProduct).filter(FinishedProduct.id == FP_ID).first()
    # add_to_production loy ulushini o'zi hisoblaydi — kutilgan sarfni o'sha
    # mahsulot ma'lumotidan chiqaramiz (unit_loy_kg × 5 × 0.5 sement).
    kutil = -8.0 - float(FP.unit_loy_kg or 0) * 5 * 0.5
    check("B6 sement yana kamaydi, manfiyda qoldi (aniq)", yaqin(qoldiq(S_ID), kutil),
          f"qoldiq={qoldiq(S_ID)} kutilgan={kutil}")
    oldin = qoldiq(S_ID)
    # Ishlab chiqarish braki (jarayondagi mahsulotda ruxsat — 17a chegarasi)
    r = req("post", "/api/finished/production-brak",
            json={"finished_product_id": FP_ID, "brak_qty": 1})
    check("B7 production-brak 1 birlik (qoplamali) → 200", r.status_code == 200,
          f"{r.status_code} {r.text[:200]}")
    kutil2 = oldin - float(fp2.unit_loy_kg or 0) * 1 * 0.5
    check("B8 sement brak ulushiga kamaydi (manfiyda, aniq)", yaqin(qoldiq(S_ID), kutil2),
          f"qoldiq={qoldiq(S_ID)} kutilgan={kutil2}")
else:
    for n in ("B5", "B6", "B7", "B8"):
        check(f"{n} (mahsulot yo'q)", False)

# ══════════════════════════════════════════════════════════════
section("C. Kirim manfiy qoldiqni qoplaydi")
# ══════════════════════════════════════════════════════════════
qoy(S_ID, -30.0, price=1000)
r = req("post", f"/api/inventory/{S_ID}/purchase",
        json={"quantity": 100, "price_per_unit": 1200, "paid_now": 0})
check("C1 −30 ga +100 kirim → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
check("C2 qoldiq 70 (to'liq qoplandi)", yaqin(qoldiq(S_ID), 70.0), f"qoldiq={qoldiq(S_ID)}")
check("C3 narx = yangi xarid narxi 1200 (manfiyning tan narxi yo'q)",
      yaqin(narx(S_ID), 1200.0), f"narx={narx(S_ID)}")
qoy(S_ID, -30.0, price=1000)
r = req("post", f"/api/inventory/{S_ID}/purchase",
        json={"quantity": 20, "price_per_unit": 1500, "paid_now": 0})
check("C4 −30 ga +20 kirim → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
check("C5 qoldiq −10 (qisman qoplandi)", yaqin(qoldiq(S_ID), -10.0), f"qoldiq={qoldiq(S_ID)}")
check("C6 narx = 1500", yaqin(narx(S_ID), 1500.0), f"narx={narx(S_ID)}")
r = req("post", f"/api/inventory/{S_ID}/purchase",
        json={"quantity": 50, "price_per_unit": 1300, "paid_now": 0})
check("C7 −10 ga +50 → 40, narx 1300", r.status_code == 200 and yaqin(qoldiq(S_ID), 40.0)
      and yaqin(narx(S_ID), 1300.0), f"{r.status_code} qoldiq={qoldiq(S_ID)} narx={narx(S_ID)}")

# ══════════════════════════════════════════════════════════════
section("D. Buyurtma: loy yetishmovchiligi ogohlantirishi manfiyda ham")
# ══════════════════════════════════════════════════════════════
qoy(S_ID, -5.0)
with contextlib.redirect_stdout(_quiet):
    lchk = services.check_loy_ingredients_for_order(db, R_ID, 10.0, company_id=1)
check("D1 manfiy qoldiqda yetishmovchilik aniqlanadi",
      lchk.get("enough") is False and any("LM_SEMENT" in s for s in lchk.get("shortages", [])),
      str(lchk))
check("D2 xabarda manfiy qoldiq ko'rinadi ('qoldi -5.00')",
      any("qoldi -5.00" in s for s in lchk.get("shortages", [])), str(lchk))

# ══════════════════════════════════════════════════════════════
section("E. Manfiy qoldiq bilan sahifa/API lar")
# ══════════════════════════════════════════════════════════════
qoy(S_ID, -12.5, price=1000)
for u in ("/", "/inventory", "/finance", "/finished", "/returns",
          "/api/inventory", "/api/inventory/kpi", "/api/inventory/movements",
          "/api/finance/history", "/api/penoplasts", "/api/recipes",
          "/api/loy-stock", "/api/loy-cost"):
    r = req("get", u)
    check(f"E {u} → 200", r.status_code == 200, f"{r.status_code} {r.text[:160]}")
r = req("get", "/api/inventory")
try:
    satr = [x for x in r.json() if x["id"] == S_ID]
except Exception:
    satr = []
check("E-a /api/inventory da qoldiq −12.5", bool(satr) and yaqin(satr[0]["stock_quantity"], -12.5),
      str(satr)[:200])
r = req("get", "/inventory")
check("E-b /inventory sahifasida '-12.5 kg'", "-12.5 kg" in r.text)
with contextlib.redirect_stdout(_quiet):
    kam = crud.get_low_stock_items(db, company_id=1)
check("E-c kam qolganlar ro'yxatida sement bor", any(i.id == S_ID for i in kam))

# ══════════════════════════════════════════════════════════════
section("F. POST /api/inventory/{id}/stock — qo'lda tuzatish")
# ══════════════════════════════════════════════════════════════


def stock_prob(label, body, kutilgan_kod, qoldiq_oldin, raw=None, kutilgan_qoldiq=None,
               sabab=None, harakat_farq=None):
    qoy(S_ID, qoldiq_oldin)
    h_old = harakatlar(S_ID)
    if raw is not None:
        r = req("post", f"/api/inventory/{S_ID}/stock", content=raw,
                headers={"Content-Type": "application/json"})
    else:
        r = req("post", f"/api/inventory/{S_ID}/stock", json=body)
    kq = qoldiq_oldin if kutilgan_qoldiq is None else kutilgan_qoldiq
    hf = (0 if kutilgan_kod != 200 else 1) if harakat_farq is None else harakat_farq
    check(f"{label} → {kutilgan_kod}", r.status_code == kutilgan_kod,
          f"{r.status_code} {r.text[:200]}")
    check(f"{label} — qoldiq {kq:g}", yaqin(qoldiq(S_ID), kq), f"qoldiq={qoldiq(S_ID)}")
    check(f"{label} — harakatlar +{hf}", harakatlar(S_ID) - h_old == hf,
          f"farq={harakatlar(S_ID) - h_old}")
    if sabab is not None:
        check(f"{label} — sabab '{sabab}'", sabab in r.text, r.text[:200])
    return r


stock_prob("F1 chiqim 1000 (qoldiq 100)", {"quantity_change": -1000}, 400, 100.0,
           sabab="omborda 100 kg bor")
stock_prob("F2 chiqim 5 (qoldiq −30, manfiy)", {"quantity_change": -5}, 400, -30.0,
           sabab="qoldiq manfiy")
stock_prob("F3 chiqim 100.0001 (qoldiq 100)", {"quantity_change": -100.0001}, 400, 100.0)
stock_prob("F4 chiqim aynan 100 (qoldiq 100)", {"quantity_change": -100}, 200, 100.0,
           kutilgan_qoldiq=0.0)
r = stock_prob("F5 chiqim 40 (qoldiq 100) izoh bilan",
               {"quantity_change": -40, "reason": "Inventarizatsiya F5"}, 200, 100.0,
               kutilgan_qoldiq=60.0)
hm = oxirgi_harakat(S_ID)
check("F5b harakat: out 40, izoh saqlandi",
      hm is not None and hm.movement_type == "out" and yaqin(hm.quantity, 40.0)
      and hm.reason == "Inventarizatsiya F5",
      str((hm.movement_type, hm.quantity, hm.reason)) if hm else "yo'q")
stock_prob("F6 kirim +20 (qoldiq −30) — qoplaydi", {"quantity_change": 20}, 200, -30.0,
           kutilgan_qoldiq=-10.0)
hm = oxirgi_harakat(S_ID)
check("F6b harakat: in 20", hm is not None and hm.movement_type == "in" and yaqin(hm.quantity, 20.0))
stock_prob("F7 chiqim 0.3 (qoldiq 0.3, suzuvchi nuqta)", {"quantity_change": -0.3}, 200, 0.3,
           kutilgan_qoldiq=0.0)
stock_prob("F7b chiqim 0.30000000000000004 (qoldiq 0.3) — tolerans", {"quantity_change": -0.30000000000000004},
           200, 0.3, kutilgan_qoldiq=0.0)
check("F7c qoldiq aynan 0 (manfiy ulush qolmadi)", qoldiq(S_ID) == 0.0, f"qoldiq={qoldiq(S_ID)!r}")
# Yomon tanalar — 400 (FastAPI tana turi xato bo'lsa 422 — u ham hech narsa yozmaydi)
stock_prob("F8 NaN (xom matn)", None, 400, 100.0, raw=b'{"quantity_change": NaN}')
stock_prob("F9 Infinity (xom matn)", None, 400, 100.0, raw=b'{"quantity_change": Infinity}')
stock_prob("F10 -Infinity (xom matn)", None, 400, 100.0, raw=b'{"quantity_change": -Infinity}')
stock_prob("F11 true", {"quantity_change": True}, 400, 100.0)
stock_prob("F12 \"5\" (matn)", {"quantity_change": "5"}, 400, 100.0)
stock_prob("F13 0", {"quantity_change": 0}, 400, 100.0)
stock_prob("F14 1e20", {"quantity_change": 1e20}, 400, 100.0)
stock_prob("F15 kalit yo'q", {"reason": "x"}, 400, 100.0)
stock_prob("F16 noma'lum kalit", {"quantity_change": 1, "stock_quantity": 5}, 400, 100.0,
           sabab="Noma")
stock_prob("F17 izoh 201 belgi", {"quantity_change": 1, "reason": "x" * 201}, 400, 100.0)
stock_prob("F18 izoh son", {"quantity_change": 1, "reason": 5}, 400, 100.0)
stock_prob("F19 izoh aynan 200 belgi — ruxsat", {"quantity_change": 1, "reason": "y" * 200},
           200, 100.0, kutilgan_qoldiq=101.0)
stock_prob("F20 null", {"quantity_change": None}, 400, 100.0)
r = req("post", f"/api/inventory/{S_ID}/stock", json=[1, 2])
check("F21 ro'yxat tana → 422/400, hech narsa yozilmadi",
      r.status_code in (400, 422), f"{r.status_code}")
# Begona / yo'q id — tana tekshiruvidan OLDIN 404 (oracle yo'q)
b_old = qoldiq(B_ID)
r = req("post", f"/api/inventory/{B_ID}/stock", json={"quantity_change": -5})
check("F22 begona material (yaxshi tana) → 404", r.status_code == 404, f"{r.status_code}")
r = req("post", f"/api/inventory/{B_ID}/stock", json={"quantity_change": True})
check("F23 begona material (yomon tana) → 404", r.status_code == 404, f"{r.status_code}")
check("F24 begona qoldiq o'zgarmadi", yaqin(qoldiq(B_ID), b_old), f"{qoldiq(B_ID)}")
r = req("post", "/api/inventory/99999999/stock", json={"quantity_change": True})
check("F25 yo'q material (yomon tana) → 404", r.status_code == 404, f"{r.status_code}")
stock_prob("F26 UI tanasi AYNAN (reason null)", {"quantity_change": -2, "reason": None},
           200, 10.0, kutilgan_qoldiq=8.0)

# ══════════════════════════════════════════════════════════════
section("G. Ildiz: crud.update_stock to'g'ridan-to'g'ri")
# ══════════════════════════════════════════════════════════════


def ildiz(label, fn, kutilgan_xato, qoldiq_oldin, kutilgan_qoldiq=None):
    qoy(S_ID, qoldiq_oldin)
    xato = None
    natija = None
    try:
        with contextlib.redirect_stdout(_quiet):
            natija = fn()
    except ValueError as e:
        xato = e
    except TypeError as e:          # asl kodda yangi imzo yo'q
        xato = e
    except Exception as e:          # asl kodda boshqa istisno
        xato = e
    db.rollback()
    kq = qoldiq_oldin if kutilgan_qoldiq is None else kutilgan_qoldiq
    if kutilgan_xato:
        check(f"{label} → ValueError", isinstance(xato, ValueError),
              f"xato={type(xato).__name__ if xato else None}")
    else:
        check(f"{label} → xatosiz", xato is None, f"xato={xato!r}")
    check(f"{label} — qoldiq {kq:g}", yaqin(qoldiq(S_ID), kq), f"qoldiq={qoldiq(S_ID)}")
    return natija


ildiz("G1 chiqim qoldiqdan ko'p", lambda: crud.update_stock(db, S_ID, -50.0), True, 10.0)
ildiz("G2 manfiy qoldiqda chiqim", lambda: crud.update_stock(db, S_ID, -1.0), True, -3.0)
ildiz("G3 NaN", lambda: crud.update_stock(db, S_ID, float("nan")), True, 10.0)
ildiz("G4 True", lambda: crud.update_stock(db, S_ID, True), True, 10.0)
ildiz("G5 izoh 201 belgi", lambda: crud.update_stock(db, S_ID, 1.0, notes="z" * 201), True, 10.0)
ildiz("G6 kirim manfiyni qoplaydi", lambda: crud.update_stock(db, S_ID, 5.0), False, -3.0,
      kutilgan_qoldiq=2.0)
n = ildiz("G7 begona korxona (company_id=1, material 2-korxonada) → None",
          lambda: crud.update_stock(db, B_ID, -1.0, company_id=1), False, 10.0,
          kutilgan_qoldiq=10.0)
check("G7b natija None, begona qoldiq o'zgarmadi", n is None and yaqin(qoldiq(B_ID), b_old),
      f"n={n} begona={qoldiq(B_ID)}")

# ══════════════════════════════════════════════════════════════
section("H. Statik: eski qirqish qaytmagan")
# ══════════════════════════════════════════════════════════════
import inspect                                     # noqa: E402
src_d = inspect.getsource(services.deduct_loy_ingredients)
check("H1 deduct_loy_ingredients da 'new_qty = 0.0' YO'Q", "new_qty = 0.0" not in src_d)
check("H2 deduct_loy_ingredients da 'manfiyga o'tkazilmadi' YO'Q",
      "manfiyga o'tkazilmadi" not in src_d)
src_u = inspect.getsource(crud.update_stock)
check("H3 update_stock da 'new_qty = 0  # Manfiy bo'lmasin' YO'Q",
      "new_qty = 0  # Manfiy bo'lmasin" not in src_u)
check("H4 crud._clean_stock_change mavjud", hasattr(crud, "_clean_stock_change"))

# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print("=" * 60)
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  - " + f)
db.close()
sys.exit(0 if FAIL == 0 else 1)
