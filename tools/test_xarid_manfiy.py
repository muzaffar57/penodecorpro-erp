#!/usr/bin/env python3
"""
test_xarid_manfiy.py — 20-band: xarid o'chirilganda qoldiq ARIFMETIK
kamayadi (manfiyga tushishi mumkin), penoplast qirqishlari olib tashlandi,
ombor jurnali to'liq, bildirishnomalarda o'chirilgan materiallar yo'q.

NIMA UCHUN KERAK (2026-09-21)
-----------------------------
FOYDALANUVCHI QARORI: "1" — xarid o'chirilganda qoldiq manfiyga tushadi,
HAMMA material uchun (penoplast ham); keyingi kirimda qoplanadi.

Asl kod (kech16, O'LCHANGAN — jonli + lokal):
  * `crud.delete_purchase` — qoldiqni 0 da qirqardi: −2 da 3 kg lik xarid
    o'chirilsa 0 bo'lardi (to'g'risi −5), jurnalga esa "out 3" yozilardi
    (ombor va jurnal bir-biriga zid).
  * `services.deduct_raw_material_for_brak` va `services.adjust_inventory_diff`
    penoplastni `max(0, ...)` bilan ayirardi — `deduct_inventory_for_order`
    ATAYLAB qoldirgan manfiy "qarz"ni jimgina 0 ga ko'tarib o'chirardi.
  * `crud.add_to_production` ("+") penoplast sarfini jurnalga YOZMASDI;
    `crud.delete_finished_product` penoplast qaytishini jurnalga YOZMASDI,
    loy qaytishini esa har doim "Buyurtma TERMOPANEL + bekor qilindi" deb
    yozardi.
  * `services.get_notifications` o'chirilgan (`is_deleted`) materiallarni ham
    "qolmadi" / "N kundan keyin tugaydi" deb ko'rsatardi (jonli: 9 tadan 8 tasi).

QAMROV
------
A. `DELETE /api/inventory/purchases/{id}` — arifmetik, jurnal = haqiqiy
   o'zgarish, manfiy ogohlantirish matni, kirim qoplaydi, suzuvchi nuqta,
   penoplast, begona/yo'q id → 404
B. Ildiz: brak va buyurtma tahriri penoplastni manfiyga tushiradi (qarz o'chmaydi)
C. HTTP produce / add / o'chirish — penoplast jurnali to'liq va muvozanatda,
   loy qaytish sababi mahsulot nomi bilan, uzun nomda sabab ≤ 200
D. Bildirishnomalar — o'chirilganlar yo'q, faollar bor, begona yo'q
E. `crud._jurnal_sabab`
F. Statik: eski qirqish qatorlari qaytmagan

ISHLATISH
---------
    python tools/test_xarid_manfiy.py
    TENANT_FILTER=1 python tools/test_xarid_manfiy.py

Asl kodga qarshi ham QULAMAYDI (mutatsiya uchun): yangi yordamchilar
`try/except`, HTTP istisnolar 500 ga aylantiriladi.

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import tempfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "xarid_manfiy_test.db")
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
from sqlalchemy import event, func                 # noqa: E402
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
    FinishedProduct, InventoryPurchase,
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
    auth.create_user(db, "XM_admin", "Parol123!", UserRole.ADMIN, "XM Admin",
                     company_id=1)

LOY = Inventory(company_id=1, item_name="XM_SEMENT", unit="kg",
                stock_quantity=10.0, price_per_unit=1000, min_stock=0)
MEL = Inventory(company_id=1, item_name="XM_MEL", unit="kg",
                stock_quantity=1000.0, price_per_unit=500, min_stock=0)
PENO = Inventory(company_id=1, item_name="XM Penoplast", unit="blok",
                 stock_quantity=100.0, price_per_unit=200000,
                 volume_per_unit=1.0, is_penoplast=True,
                 is_default_penoplast=True)
PENO2 = Inventory(company_id=1, item_name="XM Penoplast2", unit="blok",
                  stock_quantity=10.0, price_per_unit=200000,
                  volume_per_unit=1.0, is_penoplast=True)
BEGONA = Inventory(company_id=2, item_name="XM_BEGONA", unit="kg",
                   stock_quantity=50.0, price_per_unit=100)
db.add_all([LOY, MEL, PENO, PENO2, BEGONA])
db.commit()
REC = Recipe(company_id=1, name="XM_RETSEPT", batch_size_kg=100.0)
db.add(REC)
db.commit()
db.add_all([
    RecipeIngredient(recipe_id=REC.id, inventory_id=LOY.id, quantity_kg=50.0),
    RecipeIngredient(recipe_id=REC.id, inventory_id=MEL.id, quantity_kg=50.0),
])
db.commit()
L_ID, M_ID, P_ID, P2_ID, B_ID, R_ID = (LOY.id, MEL.id, PENO.id, PENO2.id,
                                       BEGONA.id, REC.id)


def qoldiq(inv_id):
    db.expire_all()
    r = db.query(Inventory).filter(Inventory.id == inv_id).first()
    return float(r.stock_quantity or 0) if r else None


def narx(inv_id):
    db.expire_all()
    r = db.query(Inventory).filter(Inventory.id == inv_id).first()
    return float(r.price_per_unit or 0) if r else None


def qoy(inv_id, qty):
    """Sinov holatini o'rnatish — to'g'ridan-to'g'ri (hisob emas)."""
    db.expire_all()
    r = db.query(Inventory).filter(Inventory.id == inv_id).first()
    r.stock_quantity = qty
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


def oxirgi_id():
    db.expire_all()
    return db.query(func.max(InventoryMovement.id)).scalar() or 0


def jurnal_balans(inv_id, dan_id):
    """`dan_id` dan keyingi harakatlar yig'indisi: in − out."""
    db.expire_all()
    rows = db.query(InventoryMovement).filter(
        InventoryMovement.inventory_id == inv_id,
        InventoryMovement.id > dan_id).all()
    return sum((float(m.quantity) if m.movement_type == "in" else -float(m.quantity))
               for m in rows), rows


def oxirgi_xarid(inv_id):
    db.expire_all()
    return db.query(InventoryPurchase).filter(
        InventoryPurchase.inventory_id == inv_id).order_by(
        InventoryPurchase.id.desc()).first()


def login(user):
    c = TestClient(main.app, base_url="https://testserver",
                   raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": "Parol123!"},
               follow_redirects=False)
    assert r.status_code == 302, f"{user} login bo'lmadi: {r.status_code}"
    return c


C = login("XM_admin")


def req(method, url, **kw):
    """Server istisnosi skriptni qulatmasin (asl kodga qarshi mutatsiya)."""
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
print("20-BAND DARVOZASI — xarid o'chirish manfiy + penoplast + jurnal + bildirishnoma")
print("TENANT_FILTER = " + ("1 (YOQILGAN)" if _tc.ENABLED else "0 (o'chiq)"))
print("=" * 66)

# ══════════════════════════════════════════════════════════════
section("A. Xarid o'chirish — qoldiq arifmetik kamayadi")
# ══════════════════════════════════════════════════════════════
qoy(L_ID, 10.0)
r = req("post", f"/api/inventory/{L_ID}/purchase",
        json={"quantity": 5, "price_per_unit": 1000, "paid_now": 0})
check("A1 kirim 5 → 200, qoldiq 15", r.status_code == 200 and yaqin(qoldiq(L_ID), 15.0),
      f"{r.status_code} qoldiq={qoldiq(L_ID)}")
xa = oxirgi_xarid(L_ID)
XA_ID = xa.id if xa else 0
qoy(L_ID, 2.0)           # 13 kg ishlab chiqarishda ishlatildi
h0 = harakatlar(L_ID)
r = req("delete", f"/api/inventory/purchases/{XA_ID}")
check("A2 ishlatilgan xarid o'chirildi → 200", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
check("A3 qoldiq 2 − 5 = −3 (0 da qirqilmadi)", yaqin(qoldiq(L_ID), -3.0), f"qoldiq={qoldiq(L_ID)}")
hm = oxirgi_harakat(L_ID)
check("A4 jurnal +1, 'out 5' — haqiqiy o'zgarishga TENG",
      harakatlar(L_ID) == h0 + 1 and hm is not None and hm.movement_type == "out"
      and yaqin(hm.quantity, 5.0),
      f"soni={harakatlar(L_ID) - h0} yozuv={(hm.movement_type, hm.quantity) if hm else None}")
sabab = (hm.reason or "") if hm else ""
check("A5 sabab: 'qoldiq manfiy: -3' va 'keyingi kirimda qoplanadi'",
      "qoldiq manfiy: -3" in sabab and "keyingi kirimda qoplanadi" in sabab, sabab)
check("A6 eski matn ('0 dan pastga tushirilmadi') YO'Q", "0 dan pastga" not in sabab, sabab)
check("A7 sabab ≤ 200 belgi", len(sabab) <= 200, str(len(sabab)))
check("A8 xarid yozuvi o'chdi",
      db.query(InventoryPurchase).filter(InventoryPurchase.id == XA_ID).first() is None)

r = req("post", f"/api/inventory/{L_ID}/purchase",
        json={"quantity": 8, "price_per_unit": 1200, "paid_now": 0})
check("A9 −3 ga +8 kirim → 5 (qarz qoplandi), narx 1200",
      r.status_code == 200 and yaqin(qoldiq(L_ID), 5.0) and yaqin(narx(L_ID), 1200.0),
      f"{r.status_code} qoldiq={qoldiq(L_ID)} narx={narx(L_ID)}")

r = req("post", f"/api/inventory/{L_ID}/purchase",
        json={"quantity": 4, "price_per_unit": 1200, "paid_now": 0})
xa = oxirgi_xarid(L_ID)
r = req("delete", f"/api/inventory/purchases/{xa.id if xa else 0}")
hm = oxirgi_harakat(L_ID)
check("A10 oddiy holat: 5 + 4 − 4 = 5, ogohlantirish YO'Q",
      r.status_code == 200 and yaqin(qoldiq(L_ID), 5.0) and hm is not None
      and "manfiy" not in (hm.reason or ""),
      f"{r.status_code} qoldiq={qoldiq(L_ID)} sabab={hm.reason if hm else None}")

# Aynan 0 ga (suzuvchi nuqta): 0.3 − 0.30000000000000004 → 0, ogohlantirish yo'q
qoy(L_ID, 0.3)
db.expunge_all()     # SQLite o'chirilgan id ni qayta beradi — eski obyekt sessiyada qolmasin
_xp = InventoryPurchase(inventory_id=L_ID, item_name="XM_SEMENT",
                        quantity=0.1 + 0.2, unit="kg", price_per_unit=1000,
                        total_amount=300)
db.add(_xp)
db.commit()
r = req("delete", f"/api/inventory/purchases/{_xp.id}")
hm = oxirgi_harakat(L_ID)
check("A11 0.3 − (0.1+0.2) → aynan 0 (manfiy −5e-17 emas)",
      r.status_code == 200 and qoldiq(L_ID) == 0.0, f"{r.status_code} qoldiq={qoldiq(L_ID)!r}")
check("A12 suzuvchi nuqtada ogohlantirish YO'Q",
      hm is not None and "manfiy" not in (hm.reason or ""), hm.reason if hm else None)

# Penoplast (qaror: HAMMA material)
qoy(P2_ID, 10.0)
r = req("post", f"/api/inventory/{P2_ID}/purchase",
        json={"quantity": 3, "price_per_unit": 200000, "paid_now": 0})
xp = oxirgi_xarid(P2_ID)
qoy(P2_ID, 1.0)
r = req("delete", f"/api/inventory/purchases/{xp.id if xp else 0}")
check("A13 penoplast: 1 − 3 = −2 (penoplast ham manfiyga)",
      r.status_code == 200 and yaqin(qoldiq(P2_ID), -2.0), f"{r.status_code} qoldiq={qoldiq(P2_ID)}")
hm = oxirgi_harakat(P2_ID)
check("A14 penoplast jurnali 'out 3', sabab 'qoldiq manfiy: -2 blok'",
      hm is not None and hm.movement_type == "out" and yaqin(hm.quantity, 3.0)
      and "qoldiq manfiy: -2 blok" in (hm.reason or ""),
      f"{(hm.movement_type, hm.quantity, hm.reason) if hm else None}")

# Begona va yo'q
db.expunge_all()
_bx = InventoryPurchase(inventory_id=B_ID, item_name="XM_BEGONA", quantity=5.0,
                        unit="kg", price_per_unit=100, total_amount=500)
db.add(_bx)
db.commit()
BX_ID = _bx.id
hb = harakatlar(B_ID)
r = req("delete", f"/api/inventory/purchases/{BX_ID}")
db.expire_all()
check("A15 begona korxona xaridi → 404, begona qoldiq/jurnal/xarid O'ZGARMADI",
      r.status_code == 404 and yaqin(qoldiq(B_ID), 50.0) and harakatlar(B_ID) == hb
      and db.query(InventoryPurchase).filter(InventoryPurchase.id == BX_ID).first() is not None,
      f"{r.status_code} qoldiq={qoldiq(B_ID)}")
r = req("delete", "/api/inventory/purchases/99999999")
check("A16 yo'q xarid → 404", r.status_code == 404, str(r.status_code))

# ══════════════════════════════════════════════════════════════
section("B. Ildiz: penoplast brak va buyurtma tahriri — qarz o'chmaydi")
# ══════════════════════════════════════════════════════════════


class _Detal:
    """deduct_raw_material_for_brak uchun soxta panel detali: 10 dona
    100 sm × 10 sm → 1.0 m³ (1 blok), 1 dona = 0.1 blok."""
    def __init__(self):
        self.category = "panel"
        self.width = 100
        self.thickness = 10
        self.length = 100
        self.quantity = 10
        self.unit_price = 1000
        self.unit_price_for_volume = None
        self.price_per_m3 = None
        self.finished_product_id = None
        self.penoplast_id = P_ID
        self.order_qty_normalized = 10.0
        self.name = "XM panel"
        self.is_coated = False
        self.company_id = 1


def brak(qty):
    with contextlib.redirect_stdout(_quiet):
        try:
            services.deduct_raw_material_for_brak(db, _Detal(), None, qty, False)
            db.commit()
        except Exception as e:
            db.rollback()
            return f"ISTISNO {type(e).__name__}: {e}"
    return None


qoy(P_ID, 0.1)
h0 = harakatlar(P_ID)
x = brak(2)
check("B1 brak 2 dona (0.2 blok), qoldiq 0.1 → −0.1 (0 emas)",
      x is None and yaqin(qoldiq(P_ID), -0.1), f"{x} qoldiq={qoldiq(P_ID)}")
hm = oxirgi_harakat(P_ID)
check("B2 jurnal 'out 0.2' — haqiqiy o'zgarishga TENG",
      harakatlar(P_ID) == h0 + 1 and hm is not None and yaqin(hm.quantity, 0.2),
      f"{(hm.movement_type, hm.quantity) if hm else None}")
qoy(P_ID, -1.0)
x = brak(1)
check("B3 qoldiq allaqachon −1: brak 0.1 blok → −1.1 (qarz 0 ga ko'tarilmadi)",
      x is None and yaqin(qoldiq(P_ID), -1.1), f"{x} qoldiq={qoldiq(P_ID)}")

PANEL = {"category": "panel", "width": 100, "thickness": 10, "length": 100,
         "quantity": 10, "unit_price": 1000, "is_coated": False,
         "penoplast_id": None, "name": "XM tahrir"}
PANEL["penoplast_id"] = P_ID


def tahrir(eski, yangi):
    with contextlib.redirect_stdout(_quiet):
        try:
            services.adjust_inventory_diff(db, eski, yangi, company_id=1)
            db.commit()
        except Exception as e:
            db.rollback()
            return f"ISTISNO {type(e).__name__}: {e}"
    return None


qoy(P_ID, 0.5)
x = tahrir([], [dict(PANEL)])
check("B4 tahrir +1 blok, qoldiq 0.5 → −0.5", x is None and yaqin(qoldiq(P_ID), -0.5),
      f"{x} qoldiq={qoldiq(P_ID)}")
qoy(P_ID, -2.0)
x = tahrir([], [dict(PANEL)])
check("B5 qoldiq −2, tahrir +1 blok → −3 (qarz o'chmadi)", x is None and yaqin(qoldiq(P_ID), -3.0),
      f"{x} qoldiq={qoldiq(P_ID)}")
x = tahrir([dict(PANEL)], [])
check("B6 teskari tahrir (detal o'chirildi) → −3 + 1 = −2", x is None and yaqin(qoldiq(P_ID), -2.0),
      f"{x} qoldiq={qoldiq(P_ID)}")
qoy(P_ID, 5.0)
x = tahrir([], [dict(PANEL)])
check("B7 nazorat: yetarli qoldiqda 5 − 1 = 4", x is None and yaqin(qoldiq(P_ID), 4.0),
      f"{x} qoldiq={qoldiq(P_ID)}")

# ══════════════════════════════════════════════════════════════
section("C. Tayyor mahsulot: penoplast jurnali to'liq, loy sababi to'g'ri")
# ══════════════════════════════════════════════════════════════
# Blok hajmi 2.0 — "blok" ≠ "m³" (1.0 da m³ ni blok o'rniga yozish xatosi
# ko'rinmay qolardi)
db.query(Inventory).filter(Inventory.id == P2_ID).update({"volume_per_unit": 2.0})
db.commit()
qoy(P2_ID, 100.0)
qoy(L_ID, 1000.0)
qoy(M_ID, 1000.0)
p0 = qoldiq(P2_ID)
l0 = qoldiq(L_ID)
dan = oxirgi_id()
NOM = "XM Karniz C1"
r = req("post", "/api/finished/produce", json={
    "name": NOM, "category": "profil", "is_coated": True,
    "penoplast_id": P2_ID, "price_per_m3": None, "unit_price": 100000,
    "loy_kg": 20, "recipe_id": R_ID, "notes": None,
    "width": 10, "thickness": 10, "length": 10, "quantity": 1})
check("C1 produce → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
db.expire_all()
FP = db.query(FinishedProduct).filter(FinishedProduct.name == NOM).first()
FP2_ID = FP.id if FP else 0
p1 = qoldiq(P2_ID)
hp = harakatlar(P2_ID)
r = req("post", f"/api/finished/{FP2_ID}/add", json={"quantity": 5})
check("C2 add +5 → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
p2 = qoldiq(P2_ID)
hm = oxirgi_harakat(P2_ID)
check("C3 add: penoplast kamaydi VA jurnalga 'out' yozildi (miqdor = kamayish)",
      p2 < p1 and harakatlar(P2_ID) == hp + 1 and hm is not None
      and hm.movement_type == "out" and yaqin(hm.quantity, p1 - p2),
      f"{p1}→{p2} soni={harakatlar(P2_ID) - hp} yozuv={(hm.movement_type, hm.quantity) if hm else None}")
check("C4 add sababida mahsulot nomi", hm is not None and NOM in (hm.reason or ""),
      hm.reason if hm else None)
bal, _ = jurnal_balans(P2_ID, dan)
check("C5 produce+add: penoplast jurnal balansi = qoldiq o'zgarishi",
      yaqin(bal, p2 - p0), f"jurnal={bal} qoldiq={p2 - p0}")

dan2 = oxirgi_id()
r = req("delete", f"/api/finished/{FP2_ID}")
check("C6 jarayondagi mahsulot o'chirildi → 200", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
check("C7 penoplast AYNAN qaytdi", yaqin(qoldiq(P2_ID), p0), f"{qoldiq(P2_ID)} vs {p0}")
check("C8 loy AYNAN qaytdi", yaqin(qoldiq(L_ID), l0), f"{qoldiq(L_ID)} vs {l0}")
bal2, rows = jurnal_balans(P2_ID, dan2)
check("C9 o'chirishda penoplast 'in' jurnalga yozildi (miqdor = qaytgan)",
      len(rows) == 1 and rows[0].movement_type == "in" and yaqin(bal2, p0 - p2),
      f"yozuvlar={[(m.movement_type, m.quantity) for m in rows]} kutilgan={p0 - p2}")
check("C10 penoplast qaytish sababida mahsulot nomi",
      len(rows) == 1 and NOM in (rows[0].reason or ""), [m.reason for m in rows])
bal_all, _ = jurnal_balans(P2_ID, dan)
check("C11 butun sikl: penoplast jurnal balansi 0 (qoldiq ham qaytdi)", yaqin(bal_all, 0.0), str(bal_all))
_, lrows = jurnal_balans(L_ID, dan2)
lsabab = [m.reason or "" for m in lrows]
check("C12 loy qaytish sababida mahsulot nomi va 'o'chirildi'",
      len(lrows) == 1 and NOM in lsabab[0] and "o'chirildi" in lsabab[0], lsabab)
check("C13 loy sababida 'TERMOPANEL' YO'Q", len(lrows) == 1 and "TERMOPANEL" not in lsabab[0], lsabab)

# Uzun nom (150 belgi) — jurnal sabablari ustunga (200) sig'adi
UZUN = "U" * 150
dan3 = oxirgi_id()
r = req("post", "/api/finished/produce", json={
    "name": UZUN, "category": "profil", "is_coated": True,
    "penoplast_id": P2_ID, "price_per_m3": None, "unit_price": 100000,
    "loy_kg": 20, "recipe_id": R_ID, "notes": None,
    "width": 10, "thickness": 10, "length": 10, "quantity": 1})
db.expire_all()
FPU = db.query(FinishedProduct).filter(FinishedProduct.name == UZUN).first()
if FPU:
    req("post", f"/api/finished/{FPU.id}/add", json={"quantity": 2})
    r2 = req("delete", f"/api/finished/{FPU.id}")
else:
    r2 = None
db.expire_all()
uz = [len(m.reason or "") for m in db.query(InventoryMovement).filter(
    InventoryMovement.id > dan3).all()]
check("C14 150 belgilik nom: produce/add/o'chirish → 200",
      r.status_code == 200 and FPU is not None and r2 is not None and r2.status_code == 200,
      f"{r.status_code} {getattr(r2, 'status_code', None)}")
check("C15 barcha yangi jurnal sabablari ≤ 200 belgi (PostgreSQL String(200))",
      len(uz) >= 4 and max(uz) <= 200, f"uzunliklar={uz}")

# Penoplast manfiy bo'lsa — yangi produce rad (yo'q materialdan mahsulot yozilmaydi)
qoy(P_ID, -1.0)
r = req("post", "/api/finished/produce", json={
    "name": "XM manfiy produce", "category": "profil", "is_coated": False,
    "penoplast_id": P_ID, "unit_price": 1000, "loy_kg": 0,
    "width": 10, "thickness": 10, "length": 1, "quantity": 1})
check("C16 penoplast −1 da produce → 400, qoldiq o'zgarmadi",
      r.status_code == 400 and yaqin(qoldiq(P_ID), -1.0), f"{r.status_code} qoldiq={qoldiq(P_ID)}")
qoy(P_ID, 100.0)

# ══════════════════════════════════════════════════════════════
section("D. Bildirishnomalar — o'chirilgan materiallar ko'rinmaydi")
# ══════════════════════════════════════════════════════════════


def material(nom, qty, deleted=False, cid=1, sarf=0.0):
    it = Inventory(company_id=cid, item_name=nom, unit="kg", stock_quantity=qty,
                   price_per_unit=100, min_stock=0, is_deleted=deleted)
    db.add(it)
    db.commit()
    if sarf:
        db.add(InventoryMovement(company_id=cid, inventory_id=it.id, item_name=nom,
                                 movement_type="out", quantity=sarf, unit="kg",
                                 reason="XM sarf", created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
        db.commit()
    return it.id


D_DEL0 = material("XMN_ochirilgan_nol", 0.0, deleted=True)
D_DEL5 = material("XMN_ochirilgan_sarfli", 5.0, deleted=True, sarf=140.0)
D_ACT0 = material("XMN_faol_nol", 0.0)
D_NEG = material("XMN_faol_manfiy", -3.0)
D_ACT5 = material("XMN_faol_sarfli", 5.0, sarf=140.0)
D_BEG = material("XMN_begona_nol", 0.0, cid=2)


def matnlar_http():
    r = req("get", "/api/notifications")
    try:
        return r.status_code, [n.get("text", "") for n in r.json()]
    except Exception:
        return r.status_code, []


st, mt = matnlar_http()
hamma = " | ".join(mt)
check("D1 /api/notifications → 200", st == 200, str(st))
check("D2 faol 0 qoldiq → 'qolmadi' BOR", "XMN_faol_nol qolmadi" in mt, hamma)
check("D3 faol manfiy qoldiq → 'qolmadi' BOR", "XMN_faol_manfiy qolmadi" in mt, hamma)
check("D4 faol sarfli → 'kundan keyin tugaydi' BOR (bashorat yo'li ishlaydi)",
      any(t.startswith("XMN_faol_sarfli") and "tugaydi" in t for t in mt), hamma)
check("D5 o'chirilgan 0 qoldiq — YO'Q", not any("XMN_ochirilgan_nol" in t for t in mt), hamma)
check("D6 o'chirilgan sarfli (bashorat) — YO'Q", not any("XMN_ochirilgan_sarfli" in t for t in mt), hamma)
check("D7 begona korxona materiali — YO'Q", not any("XMN_begona" in t for t in mt), hamma)
with contextlib.redirect_stdout(_quiet):
    ild = [n.get("text", "") for n in services.get_notifications(db, company_id=1)]
check("D8 ildiz get_notifications(1) HTTP bilan bir xil to'plam", sorted(ild) == sorted(mt),
      f"ildiz={ild}")
# Nazorat: shu materiallarni tiklasak — PAYDO bo'ladi (sinov holati haqiqatan
# ogohlantirish beradigan holat ekanini isbotlaydi)
for _i in (D_DEL0, D_DEL5):
    db.query(Inventory).filter(Inventory.id == _i).update({"is_deleted": False})
db.commit()
st, mt2 = matnlar_http()
check("D9 nazorat: tiklangan 0 qoldiq → 'qolmadi' paydo bo'ldi",
      "XMN_ochirilgan_nol qolmadi" in mt2, " | ".join(mt2))
check("D10 nazorat: tiklangan sarfli → bashorat paydo bo'ldi",
      any(t.startswith("XMN_ochirilgan_sarfli") and "tugaydi" in t for t in mt2), " | ".join(mt2))
for _i in (D_DEL0, D_DEL5):
    db.query(Inventory).filter(Inventory.id == _i).update({"is_deleted": True})
db.commit()

# ══════════════════════════════════════════════════════════════
section("E. crud._jurnal_sabab")
# ══════════════════════════════════════════════════════════════
_js = getattr(crud, "_jurnal_sabab", None)
check("E1 crud._jurnal_sabab mavjud", callable(_js))
if callable(_js):
    a = _js("a" * 300)
    check("E2 300 belgi → 200 belgi, '…' bilan tugaydi", len(a) == 200 and a.endswith("…"), str(len(a)))
    check("E3 200 belgi — o'zgarmaydi", _js("b" * 200) == "b" * 200)
    check("E4 qisqa matn — o'zgarmaydi", _js("Xarid #5") == "Xarid #5")
    check("E5 None → ''", _js(None) == "")
else:
    for n in ("E2", "E3", "E4", "E5"):
        check(f"{n} (yordamchi yo'q)", False)

# ══════════════════════════════════════════════════════════════
section("F. Statik — eski qirqish qatorlari qaytmagan")
# ══════════════════════════════════════════════════════════════
with open(os.path.join(ROOT, "crud.py"), encoding="utf-8") as f:
    CRUD = f.read()
with open(os.path.join(ROOT, "services.py"), encoding="utf-8") as f:
    SERV = f.read()
with open(os.path.join(ROOT, "templates", "suppliers.html"), encoding="utf-8") as f:
    SUPP = f.read()
check("F1 crud: 'max(0, float(p.stock_quantity) - blocks)' YO'Q",
      "max(0, float(p.stock_quantity) - blocks)" not in CRUD)
check("F2 services: penoplast 'max(0, ...)' qirqishlari YO'Q",
      "max(0, old_qty - blocks)" not in SERV
      and "max(0, float(p.stock_quantity) - blocks)" not in SERV)
check("F3 crud: 'zaxira 0 dan pastga tushirilmadi' YO'Q",
      "0 dan pastga tushirilmadi" not in CRUD)
check("F4 suppliers.html: \"AVTOMATIK o'zgarmaydi\" yolg'on ogohlantirishi YO'Q",
      "AVTOMATIK o'zgarmaydi" not in SUPP)
check("F5 services.get_notifications — ikkala so'rovda is_deleted filtri",
      SERV.count("Inventory.is_deleted.isnot(True)") >= 2)

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
