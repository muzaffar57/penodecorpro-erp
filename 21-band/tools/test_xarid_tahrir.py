#!/usr/bin/env python3
"""
test_xarid_tahrir.py — 21-band: xarid TAHRIRI ombor bilan mos, va
ta'minotchini o'chirish FK cheklovida yiqilmaydi.

NIMA UCHUN KERAK (2026-09-21)
-----------------------------
Ikkala nuqson ham O'LCHANGAN (jonli 1.4k tozalashi + lokal
`work/probe20d.py`), asl kod = kech17 (20-band bilan).

1) `crud.update_purchase` ATAYLAB omborga tegmasdi ("faqat tarixiy yozuv va
   qarz hisobi"), `crud.delete_purchase` esa o'chirishda yozuvning JORIY
   `quantity` sini ombordan ayiradi. Ikki amal bir-biriga ZID edi:

       kirim 3 kg  → qoldiq 3
       tahrir 3→10 → qoldiq 3   (ombor tegilmaydi)
       o'chirish   → qoldiq −7  ← yo'qdan 7 kg "qarz" paydo bo'ldi
                                   (to'g'risi 0 — omborga faqat 3 kg qo'shilgan)

       kirim 10 kg → qoldiq 10
       tahrir 10→2 → qoldiq 10
       o'chirish   → qoldiq 8   ← yo'qdan 8 kg paydo bo'ldi (to'g'risi 0)

   Bu 19/20-band qoidasiga ("ombor va jurnal bir-biriga ZID BO'LMASIN")
   to'g'ridan-to'g'ri qarshi. TUZATMA: tahrirda miqdor FARQI omborga ham
   qo'llanadi (jurnal yozuvi bilan) — shunda "xarid yozuvidagi miqdor" =
   "shu xarid omborga qo'shgan miqdor" invarianti HAR DOIM to'g'ri.

2) `crud.delete_supplier` ta'minotchini BUTUNLAY o'chiradi, lekin oldin
   faqat `InventoryPurchase.supplier_id` ni NULL qilardi va
   `SupplierPayment` larni o'chirardi. `suppliers.id` ga ishora qiluvchi
   YANA IKKI ustun bor va ularga tegilmasdi:
       InventoryMovement.supplier_id   (har kirimda yoziladi)
       InventoryReceipt.supplier_id
   Natijada BIR MARTA ham xarid qilingan ta'minotchini o'chirib bo'lmasdi:
   PostgreSQL `inventory_movements_supplier_id_fkey` ni buzib COMMIT da
   yiqilardi → foydalanuvchi "Serverda kutilmagan xato yuz berdi" (500)
   ko'rardi (jonli o'lchandi, `/logs` 28-xato). Xaridsiz ta'minotchi
   o'chgani uchun ilgari sezilmagan. SQLite da FK standart holatda O'CHIQ —
   shuning uchun lokal testlarda ham ko'rinmagan; bu fayl
   `PRAGMA foreign_keys=ON` bilan ishlaydi va shu yo'lni qulflaydi.

QAMROV
------
A. Tahrir → ombor farqi (ko'paytirish, kamaytirish, o'zgarmagan, faqat narx)
B. Tahrir + o'chirish sikli — ombor AYNAN boshlang'ich holatga qaytadi,
   jurnal balansi = qoldiq o'zgarishi (ikkala yo'nalishda)
C. Manfiy qoldiq — ruxsat, ogohlantirish matni, keyingi kirim qoplaydi
D. Qat'iy tekshiruv (HTTP + ildiz): cheksizlik, bool, 0, manfiy, sig'im,
   matn, `notes` turi — 400 va HECH NARSA yozilmaydi (ombor ham, yozuv ham)
E. Begona korxona xaridi / yo'q id → 404, ombor o'zgarmaydi
F. Ta'minotchini o'chirish — xaridli, harakatli, hujjatli; qarzli (400 →
   force=true), begona → 404; FK yozuvlari NULL, xaridlar tarixi qoladi
G. `_xarid_son` ildizi
H. Statik — eski yolg'on matnlar va tegilmagan ustunlar qaytmagan

ISHLATISH
---------
    python tools/test_xarid_tahrir.py
    TENANT_FILTER=1 python tools/test_xarid_tahrir.py

Asl kodga qarshi ham QULAMAYDI (mutatsiya uchun): yangi yordamchilar
`try/except`, HTTP istisnolar 599 ga aylantiriladi.

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "xarid_tahrir_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth                              # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from sqlalchemy import event                       # noqa: E402
import tenant_context as _tc                       # noqa: E402


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _rec):
    """FK cheklovlari YOQILADI — 21-band ning ikkinchi nuqsoni aynan shu
    qatlamda ko'rinadi (PostgreSQL da doim yoqilgan, SQLite da yo'q)."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


engine.dispose()

from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Inventory, InventoryMovement, InventoryPurchase,
    InventoryReceipt, Supplier, SupplierPayment,
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
    auth.create_user(db, "XT_admin", "Parol123!", UserRole.ADMIN, "XT Admin",
                     company_id=1)
    auth.create_user(db, "XT_admin_b", "Parol123!", UserRole.ADMIN, "XT Admin B",
                     company_id=2)

MAT = Inventory(company_id=1, item_name="XT_SEMENT", unit="kg",
                stock_quantity=0.0, price_per_unit=0, min_stock=0)
MAT2 = Inventory(company_id=1, item_name="XT_MEL", unit="kg",
                 stock_quantity=0.0, price_per_unit=0, min_stock=0)
PENO = Inventory(company_id=1, item_name="XT Penoplast", unit="blok",
                 stock_quantity=0.0, price_per_unit=0,
                 volume_per_unit=2.0, is_penoplast=True)
BEGONA = Inventory(company_id=2, item_name="XT_BEGONA", unit="kg",
                   stock_quantity=50.0, price_per_unit=100, min_stock=0)
db.add_all([MAT, MAT2, PENO, BEGONA])
db.commit()

SUP = Supplier(company_id=1, name="XT_TAMIN", phone="+998900000021")
SUP2 = Supplier(company_id=1, name="XT_TAMIN2", phone="+998900000022")
SUP3 = Supplier(company_id=1, name="XT_TAMIN3_QARZ", phone="+998900000023")
SUP4 = Supplier(company_id=1, name="XT_TAMIN4_TOZA", phone="+998900000024")
SUPB = Supplier(company_id=2, name="XT_BEGONA_TAMIN", phone="+998900000025")
db.add_all([SUP, SUP2, SUP3, SUP4, SUPB])
db.commit()

M_ID, M2_ID, P_ID, B_ID = MAT.id, MAT2.id, PENO.id, BEGONA.id
S_ID, S2_ID, S3_ID, S4_ID, SB_ID = SUP.id, SUP2.id, SUP3.id, SUP4.id, SUPB.id


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


def jurnal_balans(inv_id, dan_id):
    """`dan_id` dan keyingi harakatlar yig'indisi: in − out."""
    db.expire_all()
    rows = db.query(InventoryMovement).filter(
        InventoryMovement.inventory_id == inv_id,
        InventoryMovement.id > dan_id).all()
    return sum((float(m.quantity) if m.movement_type == "in" else -float(m.quantity))
               for m in rows)


def oxirgi_movement_id():
    db.expire_all()
    r = db.query(InventoryMovement).order_by(InventoryMovement.id.desc()).first()
    return r.id if r else 0


def xarid(pid):
    db.expire_all()
    return db.query(InventoryPurchase).filter(InventoryPurchase.id == pid).first()


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


C = login("XT_admin")
CB = login("XT_admin_b")


def _req(client, method, url, **kw):
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


def req(method, url, **kw):
    return _req(C, method, url, **kw)


def reqb(method, url, **kw):
    return _req(CB, method, url, **kw)


def kirim(inv_id, qty, price=1000, supplier_id=None, **extra):
    """Yangi xarid — yozuv id sini qaytaradi (0 — muvaffaqiyatsiz)."""
    tana = {"quantity": qty, "price_per_unit": price, "paid_now": 0,
            "transport_payer": "none", "transport_cost": 0}
    if supplier_id is not None:
        tana["supplier_id"] = supplier_id
    tana.update(extra)
    r = req("post", f"/api/inventory/{inv_id}/purchase", json=tana)
    if r.status_code != 200:
        return 0
    x = oxirgi_xarid(inv_id)
    return x.id if x else 0


def tahrir(pid, **tana):
    return req("put", f"/api/inventory/purchases/{pid}", json=tana)


print("=" * 66)
print("21-BAND DARVOZASI — xarid tahriri ombor bilan mos + ta'minotchi o'chirish (FK)")
print("TENANT_FILTER = " + ("1 (YOQILGAN)" if _tc.ENABLED else "0 (o'chiq)"))
print("=" * 66)

# ══════════════════════════════════════════════════════════════
section("A. Tahrir → ombor farqi qo'llanadi")
# ══════════════════════════════════════════════════════════════
qoy(M_ID, 0.0)
XA = kirim(M_ID, 3, 1000, S_ID)
check("A1 kirim 3 → qoldiq 3", XA and yaqin(qoldiq(M_ID), 3.0),
      f"xarid={XA} qoldiq={qoldiq(M_ID)}")

h0 = harakatlar(M_ID)
r = tahrir(XA, quantity=10, price_per_unit=1000)
check("A2 tahrir 3→10 → 200", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
check("A3 qoldiq 3 → 10 (farq +7 omborga qo'llandi)", yaqin(qoldiq(M_ID), 10.0),
      f"qoldiq={qoldiq(M_ID)}")
hm = oxirgi_harakat(M_ID)
check("A4 jurnal +1, 'in 7' — FARQGA teng",
      harakatlar(M_ID) == h0 + 1 and hm is not None and hm.movement_type == "in"
      and yaqin(hm.quantity, 7.0),
      f"soni={harakatlar(M_ID) - h0} yozuv={(hm.movement_type, hm.quantity) if hm else None}")
check("A5 jurnal sababida eski va yangi miqdor bor",
      hm is not None and "Xarid tahrirlandi" in (hm.reason or "")
      and "3 → 10" in (hm.reason or ""), f"sabab={(hm.reason if hm else None)}")
check("A6 yozuvdagi miqdor va summa yangilandi",
      xarid(XA) is not None and yaqin(xarid(XA).quantity, 10.0)
      and yaqin(float(xarid(XA).total_amount), 10000.0),
      f"{(float(xarid(XA).quantity), float(xarid(XA).total_amount)) if xarid(XA) else None}")

h0 = harakatlar(M_ID)
r = tahrir(XA, quantity=4, price_per_unit=1000)
check("A7 tahrir 10→4 → 200 va qoldiq 10 → 4", r.status_code == 200
      and yaqin(qoldiq(M_ID), 4.0), f"{r.status_code} qoldiq={qoldiq(M_ID)}")
hm = oxirgi_harakat(M_ID)
check("A8 jurnal 'out 6'",
      harakatlar(M_ID) == h0 + 1 and hm is not None and hm.movement_type == "out"
      and yaqin(hm.quantity, 6.0),
      f"yozuv={(hm.movement_type, hm.quantity) if hm else None}")

h0 = harakatlar(M_ID)
narx0 = narx(M_ID)
r = tahrir(XA, quantity=4, price_per_unit=1000)
check("A9 miqdor O'ZGARMAGAN tahrir → jurnalga yozuv YO'Q, qoldiq o'sha",
      r.status_code == 200 and harakatlar(M_ID) == h0 and yaqin(qoldiq(M_ID), 4.0),
      f"{r.status_code} soni={harakatlar(M_ID) - h0} qoldiq={qoldiq(M_ID)}")

h0 = harakatlar(M_ID)
r = tahrir(XA, price_per_unit=7000)
check("A10 FAQAT narx tahriri → qoldiq va jurnal tegilmaydi",
      r.status_code == 200 and harakatlar(M_ID) == h0 and yaqin(qoldiq(M_ID), 4.0),
      f"{r.status_code} soni={harakatlar(M_ID) - h0} qoldiq={qoldiq(M_ID)}")
check("A11 narx tahririda yozuv summasi qayta hisoblandi (4 × 7000)",
      xarid(XA) is not None and yaqin(float(xarid(XA).total_amount), 28000.0),
      f"{float(xarid(XA).total_amount) if xarid(XA) else None}")
check("A12 ombordagi O'RTACHA narx tahrirdan o'zgarmaydi",
      yaqin(narx(M_ID), narx0), f"{narx(M_ID)} != {narx0}")

# ══════════════════════════════════════════════════════════════
section("B. Tahrir + o'chirish sikli — ombor AYNAN qaytadi")
# ══════════════════════════════════════════════════════════════
qoy(M_ID, 0.0)
m0 = oxirgi_movement_id()
XA = kirim(M_ID, 3, 1000, S_ID)
tahrir(XA, quantity=10, price_per_unit=1000)
r = req("delete", f"/api/inventory/purchases/{XA}")
check("B1 3 → 10 → o'chirish: qoldiq 0 (ilgari −7 edi)",
      r.status_code == 200 and yaqin(qoldiq(M_ID), 0.0),
      f"{r.status_code} qoldiq={qoldiq(M_ID)}")
check("B2 jurnal balansi = qoldiq o'zgarishi (0)",
      yaqin(jurnal_balans(M_ID, m0), 0.0), f"balans={jurnal_balans(M_ID, m0)}")
check("B3 xarid yozuvi o'chdi", xarid(XA) is None)

qoy(M_ID, 0.0)
m0 = oxirgi_movement_id()
XA = kirim(M_ID, 10, 1000, S_ID)
tahrir(XA, quantity=2, price_per_unit=1000)
r = req("delete", f"/api/inventory/purchases/{XA}")
check("B4 10 → 2 → o'chirish: qoldiq 0 (ilgari +8 edi)",
      r.status_code == 200 and yaqin(qoldiq(M_ID), 0.0),
      f"{r.status_code} qoldiq={qoldiq(M_ID)}")
check("B5 jurnal balansi = 0", yaqin(jurnal_balans(M_ID, m0), 0.0),
      f"balans={jurnal_balans(M_ID, m0)}")

qoy(P_ID, 0.0)
m0 = oxirgi_movement_id()
XA = kirim(P_ID, 4, 100000, S_ID, volume_per_unit=2)
tahrir(XA, quantity=9, price_per_unit=100000)
check("B6 PENOPLAST ham: 4 → 9 → qoldiq 9", yaqin(qoldiq(P_ID), 9.0),
      f"qoldiq={qoldiq(P_ID)}")
r = req("delete", f"/api/inventory/purchases/{XA}")
check("B7 penoplast o'chirish → qoldiq 0, jurnal balansi 0",
      r.status_code == 200 and yaqin(qoldiq(P_ID), 0.0)
      and yaqin(jurnal_balans(P_ID, m0), 0.0),
      f"{r.status_code} qoldiq={qoldiq(P_ID)} balans={jurnal_balans(P_ID, m0)}")

qoy(M_ID, 0.0)
m0 = oxirgi_movement_id()
XA = kirim(M_ID, 0.3, 1000, S_ID)
tahrir(XA, quantity=0.1, price_per_unit=1000)
tahrir(XA, quantity=0.2, price_per_unit=1000)
r = req("delete", f"/api/inventory/purchases/{XA}")
check("B8 suzuvchi nuqta: 0.3 → 0.1 → 0.2 → o'chirish = AYNAN 0",
      r.status_code == 200 and qoldiq(M_ID) == 0.0,
      f"qoldiq={qoldiq(M_ID)!r}")

# ══════════════════════════════════════════════════════════════
section("C. Manfiy qoldiq — ruxsat, ogohlantirish, kirim qoplaydi")
# ══════════════════════════════════════════════════════════════
qoy(M_ID, 0.0)
XA = kirim(M_ID, 10, 1000, S_ID)
qoy(M_ID, 2.0)              # 8 kg ishlab chiqarishda ishlatildi
r = tahrir(XA, quantity=3, price_per_unit=1000)
check("C1 tahrir 10→3 ishlatilgandan keyin → qoldiq 2 − 7 = −5",
      r.status_code == 200 and yaqin(qoldiq(M_ID), -5.0),
      f"{r.status_code} qoldiq={qoldiq(M_ID)}")
hm = oxirgi_harakat(M_ID)
check("C2 sababda manfiy ogohlantirish bor",
      hm is not None and "qoldiq manfiy: -5" in (hm.reason or "")
      and "keyingi kirimda qoplanadi" in (hm.reason or ""),
      f"sabab={(hm.reason if hm else None)}")
check("C3 sabab 200 belgidan oshmaydi",
      hm is not None and len(hm.reason or "") <= 200,
      f"uzunlik={(len(hm.reason or '') if hm else None)}")
r = req("post", f"/api/inventory/{M_ID}/purchase",
        json={"quantity": 8, "price_per_unit": 2000, "paid_now": 0,
              "transport_payer": "none", "transport_cost": 0})
check("C4 keyingi kirim 8 manfiyni qopladi → 3", r.status_code == 200
      and yaqin(qoldiq(M_ID), 3.0), f"{r.status_code} qoldiq={qoldiq(M_ID)}")

qoy(M_ID, 0.0)
XA = kirim(M_ID, 5, 1000, S_ID)
qoy(M_ID, -2.0)             # allaqachon manfiy
r = tahrir(XA, quantity=9, price_per_unit=1000)
check("C5 manfiy qoldiqda tahrir 5→9 → −2 + 4 = 2",
      r.status_code == 200 and yaqin(qoldiq(M_ID), 2.0),
      f"{r.status_code} qoldiq={qoldiq(M_ID)}")
req("delete", f"/api/inventory/purchases/{XA}")

# ══════════════════════════════════════════════════════════════
section("D. Qat'iy tekshiruv — 400 va HECH NARSA yozilmaydi")
# ══════════════════════════════════════════════════════════════
qoy(M2_ID, 0.0)
XA = kirim(M2_ID, 6, 1500, S2_ID)
check("D0 tayyorgarlik: qoldiq 6", yaqin(qoldiq(M2_ID), 6.0), f"qoldiq={qoldiq(M2_ID)}")

def xom(matn):
    """Xom JSON matn — NaN/Infinity ni `json=` orqali yuborib bo'lmaydi."""
    return req("put", f"/api/inventory/purchases/{XA}", content=matn,
               headers={"Content-Type": "application/json"})


# ⚠ Cheksizlik (`Infinity`/`NaN`) bu ro'yxatda EMAS — `json=` orqali
# yuborilmaydi (httpx serializatori istisno beradi). Ular pastda, XOM JSON
# matn bilan sinaladi (`xom(...)`), brauzerdagi holatga mos.
YOMON = [
    ("miqdor true", {"quantity": True, "price_per_unit": 1000}),
    ("narx true", {"quantity": 6, "price_per_unit": True}),
    ("miqdor 0", {"quantity": 0, "price_per_unit": 1000}),
    ("miqdor manfiy", {"quantity": -5, "price_per_unit": 1000}),
    ("narx manfiy", {"quantity": 6, "price_per_unit": -1000}),
    ("miqdor matn", {"quantity": "abc", "price_per_unit": 1000}),
    ("miqdor sig'imdan katta", {"quantity": 1e13, "price_per_unit": 1000}),
    ("narx sig'imdan katta", {"quantity": 6, "price_per_unit": 1e13}),
    ("notes son", {"quantity": 6, "notes": 5}),
    ("notes 1001 belgi", {"quantity": 6, "notes": "x" * 1001}),
    ("is_credit matn", {"quantity": 6, "is_credit": "ha"}),
    ("is_credit 1", {"quantity": 6, "is_credit": 1}),
    ("noma'lum maydon", {"quantity": 6, "supplier_id": 1}),
    ("inventory_id ko'chirish", {"quantity": 6, "inventory_id": 99}),
    ("miqdor null emas, ro'yxat", {"quantity": [1, 2]}),
    ("tana ro'yxat ichidagi obyekt", {"quantity": {"son": 5}}),
]
for nom, tana in YOMON:
    h0 = harakatlar(M2_ID)
    q0 = qoldiq(M2_ID)
    x0 = xarid(XA)
    e0 = (float(x0.quantity), float(x0.price_per_unit), x0.notes, bool(x0.is_credit)) if x0 else None
    r = tahrir(XA, **tana)
    x1 = xarid(XA)
    e1 = (float(x1.quantity), float(x1.price_per_unit), x1.notes, bool(x1.is_credit)) if x1 else None
    check(f"D {nom} → 400 va ombor/yozuv o'zgarmadi",
          r.status_code == 400 and yaqin(qoldiq(M2_ID), q0)
          and harakatlar(M2_ID) == h0 and e0 == e1,
          f"{r.status_code} qoldiq={qoldiq(M2_ID)}/{q0} "
          f"harakat={harakatlar(M2_ID)}/{h0} yozuv={e1}/{e0}")

for nom, matn in [("Infinity", '{"quantity": Infinity}'),
                  ("-Infinity", '{"quantity": -Infinity}'),
                  ("NaN", '{"quantity": NaN}')]:
    h0 = harakatlar(M2_ID)
    q0 = qoldiq(M2_ID)
    r = xom(matn)
    check(f"D xom {nom} → 400/422 va ombor tegilmadi",
          r.status_code in (400, 422) and yaqin(qoldiq(M2_ID), q0)
          and harakatlar(M2_ID) == h0,
          f"{r.status_code} qoldiq={qoldiq(M2_ID)}/{q0} soni={harakatlar(M2_ID) - h0}")

h0 = harakatlar(M2_ID)
r = xom('[{"quantity": 5}]')
check("D ro'yxat tana → 400/422 va yozilmaydi",
      r.status_code in (400, 422) and harakatlar(M2_ID) == h0,
      f"{r.status_code} soni={harakatlar(M2_ID) - h0}")

h0 = harakatlar(M2_ID)
r = xom('{}')
check("D bo'sh tana → 200, hech narsa o'zgarmaydi",
      r.status_code == 200 and harakatlar(M2_ID) == h0,
      f"{r.status_code} soni={harakatlar(M2_ID) - h0}")

r = tahrir(XA, quantity=7, price_per_unit=1500)
check("D nazorat: to'g'ri tahrir → 200 va qoldiq 7",
      r.status_code == 200 and yaqin(qoldiq(M2_ID), 7.0),
      f"{r.status_code} qoldiq={qoldiq(M2_ID)}")

# ══════════════════════════════════════════════════════════════
section("E. Begona / yo'q xarid — 404, ombor tegilmaydi")
# ══════════════════════════════════════════════════════════════
q0, h0 = qoldiq(M2_ID), harakatlar(M2_ID)
r = tahrir(99999999, quantity=5, price_per_unit=1000)
check("E1 yo'q xarid → 404", r.status_code == 404, f"{r.status_code}")
r = req("put", "/api/inventory/purchases/99999999", json={"quantity": 0})
check("E2 yo'q xarid + yomon tana → 404 (oracle yo'q)", r.status_code == 404,
      f"{r.status_code}")
r = reqb("put", f"/api/inventory/purchases/{XA}",
         json={"quantity": 99, "price_per_unit": 1})
check("E3 BEGONA korxona xaridni tahrirlay olmaydi → 404", r.status_code == 404,
      f"{r.status_code}")
check("E4 begona urinishdan keyin ombor va jurnal o'zgarmadi",
      yaqin(qoldiq(M2_ID), q0) and harakatlar(M2_ID) == h0,
      f"qoldiq={qoldiq(M2_ID)}/{q0} harakat={harakatlar(M2_ID)}/{h0}")
r = reqb("delete", f"/api/inventory/purchases/{XA}")
check("E5 BEGONA korxona xaridni o'chira olmaydi → 404 va yozuv joyida",
      r.status_code == 404 and xarid(XA) is not None, f"{r.status_code}")

# ══════════════════════════════════════════════════════════════
section("F. Ta'minotchini o'chirish — FK yiqilmaydi")
# ══════════════════════════════════════════════════════════════
# Oldingi bo'limlardan qolgan (to'lanmagan) xaridlar qarz yaratadi — ularni
# olib tashlaymiz, F bo'limi QARZSIZ ta'minotchini sinaydi (qarzli holat
# alohida, F8–F12 da).
db.expire_all()
for _x in db.query(InventoryPurchase).filter(
        InventoryPurchase.supplier_id == S_ID).all():
    req("delete", f"/api/inventory/purchases/{_x.id}")
qoy(M_ID, 0.0)
XS = kirim(M_ID, 5, 1000, S_ID, paid_now=5000)   # to'liq to'langan — qarz yo'q
db.expire_all()
mv_bor = db.query(InventoryMovement).filter(
    InventoryMovement.supplier_id == S_ID).count()
check("F0 kirim ta'minotchi bog'langan harakat YOZDI (nuqson sharti)",
      mv_bor >= 1, f"soni={mv_bor}")
xarid_soni = db.query(InventoryPurchase).filter(
    InventoryPurchase.supplier_id == S_ID).count()
check("F1 ta'minotchida xarid bor", xarid_soni >= 1, f"soni={xarid_soni}")

# Hujjat (receipt) ham bog'lansin — ikkinchi tegilmagan ustun
RC = InventoryReceipt(company_id=1, supplier_id=S_ID, document_number="XT-1",
                      transport_cost=0)
db.add(RC)
db.commit()
RC_ID = RC.id

r = req("delete", f"/api/suppliers/{S_ID}")
check("F2 xaridli+harakatli+hujjatli ta'minotchi o'chdi → 200 (ilgari 500)",
      r.status_code == 200, f"{r.status_code} {r.text[:200]}")
db.rollback()
db.expire_all()
check("F3 ta'minotchi bazadan yo'qoldi",
      db.query(Supplier).filter(Supplier.id == S_ID).first() is None)
check("F4 InventoryMovement.supplier_id NULL qilindi (o'chirilmadi)",
      db.query(InventoryMovement).filter(
          InventoryMovement.supplier_id == S_ID).count() == 0
      and harakatlar(M_ID) >= 1,
      f"qolgan={db.query(InventoryMovement).filter(InventoryMovement.supplier_id == S_ID).count()}")
check("F5 InventoryReceipt.supplier_id NULL qilindi (hujjat qoldi)",
      db.query(InventoryReceipt).filter(InventoryReceipt.id == RC_ID).first() is not None
      and db.query(InventoryReceipt).filter(
          InventoryReceipt.supplier_id == S_ID).count() == 0)
check("F6 xarid tarixi qoldi, faqat bog'lanish uzildi",
      xarid(XS) is not None and xarid(XS).supplier_id is None,
      f"{(xarid(XS).supplier_id if xarid(XS) else 'yozuv yo_q')}")
check("F7 ombor qoldig'i o'chirishdan o'zgarmadi (5)", yaqin(qoldiq(M_ID), 5.0),
      f"qoldiq={qoldiq(M_ID)}")

# Qarzli ta'minotchi — 400, keyin force=true
qoy(M_ID, 0.0)
r = req("post", f"/api/inventory/{M_ID}/purchase",
        json={"quantity": 4, "price_per_unit": 5000, "paid_now": 0,
              "supplier_id": S3_ID, "transport_payer": "none", "transport_cost": 0})
check("F8 qarzli kirim → 200", r.status_code == 200, f"{r.status_code}")
r = req("delete", f"/api/suppliers/{S3_ID}")
check("F9 qarzli ta'minotchi force'siz → 400 (qarz sababi bilan)",
      r.status_code == 400 and "qarz" in str(r.json()).lower(),
      f"{r.status_code} {r.text[:150]}")
db.rollback()
db.expire_all()
check("F10 rad etilgandan keyin ta'minotchi joyida",
      db.query(Supplier).filter(Supplier.id == S3_ID).first() is not None)
r = req("delete", f"/api/suppliers/{S3_ID}?force=true")
check("F11 force=true bilan o'chdi → 200", r.status_code == 200,
      f"{r.status_code} {r.text[:200]}")
db.rollback()
db.expire_all()
check("F12 force o'chirishda to'lovlar ham tozalandi",
      db.query(SupplierPayment).filter(
          SupplierPayment.supplier_id == S3_ID).count() == 0)

# To'lovli ta'minotchi (SupplierPayment NOT NULL FK) — QISMAN to'lov
# yozuv yaratadi (to'liq to'langan xarid qarz emas, yozuv ham yo'q).
qoy(M2_ID, 0.0)
r = req("post", f"/api/inventory/{M2_ID}/purchase",
        json={"quantity": 2, "price_per_unit": 1000, "paid_now": 1500,
              "supplier_id": S2_ID, "transport_payer": "none", "transport_cost": 0})
db.expire_all()
tolov_soni = db.query(SupplierPayment).filter(
    SupplierPayment.supplier_id == S2_ID).count()
check("F13 qisman to'langan kirim SupplierPayment yozdi", tolov_soni >= 1,
      f"soni={tolov_soni} {r.status_code}")
mv_b = db.query(InventoryMovement).filter(
    InventoryMovement.supplier_id == S2_ID).count()
check("F13b shu ta'minotchida bog'langan harakat ham bor", mv_b >= 1, f"soni={mv_b}")
r = req("delete", f"/api/suppliers/{S2_ID}?force=true")
check("F14 to'lovli + harakatli ta'minotchi force bilan o'chdi → 200",
      r.status_code == 200, f"{r.status_code} {r.text[:200]}")
db.rollback()
db.expire_all()
check("F15 to'lov yozuvlari o'chdi, harakat NULL qilindi (FK buzilmadi)",
      db.query(SupplierPayment).filter(
          SupplierPayment.supplier_id == S2_ID).count() == 0
      and db.query(InventoryMovement).filter(
          InventoryMovement.supplier_id == S2_ID).count() == 0
      and db.query(Supplier).filter(Supplier.id == S2_ID).first() is None)

# Toza (xaridsiz) ta'minotchi — avvalgidek ishlaydi
r = req("delete", f"/api/suppliers/{S4_ID}")
check("F16 xaridsiz ta'minotchi o'chdi → 200", r.status_code == 200,
      f"{r.status_code}")

# Begona korxona
r = req("delete", f"/api/suppliers/{SB_ID}")
check("F17 BEGONA korxona ta'minotchisi → 404", r.status_code == 404,
      f"{r.status_code}")
db.rollback()
db.expire_all()
check("F18 begona ta'minotchi joyida",
      db.query(Supplier).filter(Supplier.id == SB_ID).first() is not None)
r = req("delete", "/api/suppliers/99999999")
check("F19 yo'q ta'minotchi → 404", r.status_code == 404, f"{r.status_code}")

# ══════════════════════════════════════════════════════════════
section("G. Ildiz — _xarid_son")
# ══════════════════════════════════════════════════════════════


def _xs(v):
    try:
        return crud._xarid_son(v, "quantity")
    except ValueError as e:
        return f"XATO: {e}"
    except Exception as e:          # pragma: no cover — mutatsiya himoyasi
        return f"ISTISNO: {type(e).__name__}"


check("G1 oddiy son → o'zi", _xs(5) == 5.0, f"{_xs(5)}")
check("G2 None → xato", str(_xs(None)).startswith("XATO"), f"{_xs(None)}")
check("G3 True → xato (bool son emas)", str(_xs(True)).startswith("XATO"), f"{_xs(True)}")
check("G4 0 → xato", str(_xs(0)).startswith("XATO"), f"{_xs(0)}")
check("G5 manfiy → xato", str(_xs(-1)).startswith("XATO"), f"{_xs(-1)}")
check("G6 cheksiz → xato", str(_xs(float('inf'))).startswith("XATO"), f"{_xs(float('inf'))}")
check("G7 NaN → xato", str(_xs(float('nan'))).startswith("XATO"), f"{_xs(float('nan'))}")
check("G8 matn → xato", str(_xs('5')).startswith("XATO"), f"{_xs('5')}")
check("G9 sig'imdan katta → xato", str(_xs(1e13)).startswith("XATO"), f"{_xs(1e13)}")
check("G10 chegaradagi qiymat → o'tadi",
      _xs(crud._UPD_SON_CHEGARA) == float(crud._UPD_SON_CHEGARA),
      f"{_xs(crud._UPD_SON_CHEGARA)}")
check("G11 xato matnida maydon nomi bor", "quantity" in str(_xs(0)), f"{_xs(0)}")


def _upd_ildiz(pid, data, company_id=1):
    try:
        return crud.update_purchase(db, pid, data, company_id=company_id)
    except ValueError as e:
        return f"XATO: {e}"
    except Exception as e:          # pragma: no cover
        return f"ISTISNO: {type(e).__name__}"


check("G12 ildiz: begona korxona → None",
      _upd_ildiz(XA, {"quantity": 5}, company_id=2) is None,
      f"{_upd_ildiz(XA, {'quantity': 5}, company_id=2)}")
q0 = qoldiq(M2_ID)
res = _upd_ildiz(XA, {"quantity": float('inf')})
check("G13 ildiz: cheksizlik → ValueError va ombor tegilmagan",
      str(res).startswith("XATO") and yaqin(qoldiq(M2_ID), q0),
      f"{res} qoldiq={qoldiq(M2_ID)}/{q0}")

# ══════════════════════════════════════════════════════════════
section("H. Statik — yolg'on matn va tegilmagan ustunlar qaytmagan")
# ══════════════════════════════════════════════════════════════
with open(os.path.join(ROOT, "crud.py"), encoding="utf-8") as f:
    CRUD = f.read()
with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
    MAIN = f.read()
with open(os.path.join(ROOT, "templates", "suppliers.html"), encoding="utf-8") as f:
    SUPP = f.read()

check("H1 suppliers.html: \"TA'SIR QILMAYDI\" yolg'on ogohlantirishi YO'Q",
      "TA'SIR QILMAYDI" not in SUPP)
check("H2 suppliers.html: \"qo'lda tuzating\" maslahati YO'Q",
      "qo'lda tuzating" not in SUPP)
check("H3 suppliers.html: `serverSababi` yordamchisi bor va 5 joyda ishlatiladi",
      "async function serverSababi(" in SUPP and SUPP.count("serverSababi(res)") >= 5,
      f"soni={SUPP.count('serverSababi(res)')}")
check("H4 suppliers.html: qotib qolgan \"Xato\" matni YO'Q (server sababi ko'rsatiladi)",
      "showMsg('❌ Xato', 'error')" not in SUPP)
_NULL_QOLIP = '{"supplier_id": None}'
check("H5 crud: delete_supplier InventoryMovement.supplier_id ni NULL qiladi",
      "InventoryMovement.supplier_id == supplier_id" in CRUD
      and CRUD.count(_NULL_QOLIP) >= 3,
      f"soni={CRUD.count(_NULL_QOLIP)}")
check("H6 crud: delete_supplier InventoryReceipt.supplier_id ni ham NULL qiladi",
      "InventoryReceipt.supplier_id == supplier_id" in CRUD)
check("H7 crud: `_xarid_son` modul darajasida mavjud",
      "def _xarid_son(" in CRUD and callable(getattr(crud, "_xarid_son", None)))
check("H8 crud: update_purchase da eski \"ombor tegilmaydi\" izohi YO'Q",
      "ombordagi joriy miqdor/o'rtacha narxni orqaga qaytarib hisoblamaydi" not in CRUD)
check("H9 main: api_update_purchase ValueError → 400",
      "except ValueError as e:" in MAIN
      and "crud.update_purchase(db, purchase_id" in MAIN)
check("H10 main: eski \"ta'sir qilmaydi\" hujjat matni YO'Q",
      "ombordagi joriy miqdor/narxga ta'sir qilmaydi" not in MAIN)

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
