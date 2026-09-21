#!/usr/bin/env python3
"""
test_kirim_qiymat.py — 17b: ombor kirimi, kirim HUJJATI va retseptlar
tanalarining QAT'IY tekshiruvi.

NIMA UCHUN KERAK (2026-09-21)
-----------------------------
Uchala marshrut pydantic sxemasiga tayanardi, u esa qiymat SIFATINI
tekshirmasdi. Hammasi IZOLYATSIYALANGAN holda O'LCHANGAN
(`work/probe17b_iso.py` — har prob TOZA bazada; 17.1 saboqi: bitta
material ustida ketma-ket prob yolg'on natija beradi, chunki birinchi
`Infinity` keyingi hammasini 500 qiladi).

SAHIFANI BUZADIGAN (bitta so'rov → sahifa abadiy 500, qiymat SAQLANADI):
  * `purchase` `volume_per_unit: Infinity` → `/api/penoplasts`
  * `receipt` qator narxi `Infinity`      → `/api/inventory/purchases`
  * `receipt` `transport_cost: Infinity`  → `/api/finance/history`

JIM QABUL QILINGAN (200 va SAQLANGAN):
  * miqdor/narx `1e20`; `quantity: true` → 1; narx `"5000"` (matn) → 5000
  * `quantity 1e9 × price 1e6` = 1e15 → `total_amount` Numeric(12,2) sig'imi
  * `transport_payer: "xato"` (transport xarajati jim yozilmay qolardi)
  * `payment_due_date: "abc"` / `"2026-13-45"`
  * mavjud bo'lmagan `supplier_id` (PostgreSQL da FK → 500)
  * `receipt`: `production_type: "xato"` (hisobotdan jim tushardi),
    `document_number` 500 belgi (ustun 50 — PostgreSQL da 500),
    `paid_now: 1e20` (ta'minotchiga 1e20 lik to'lov YOZILARDI),
    201 qator, qo'shimcha xarajatlar `1e20` (tan narx 3.9×10¹⁸)
  * `recipes`: nom `"   "` (BO'SH nomli retsept), `batch_size_kg: Infinity`,
    `quantity_kg: 1e20`, tarkibsiz retsept, bir material IKKI marta
    (ombordan ikki baravar yechilardi), va eng jiddiysi —
    `PUT` da `ingredients: []` retsept TARKIBINI BUTUNLAY O'CHIRARDI
  * hamma joyda noma'lum maydonlar e'tiborsiz qolardi

QAMROV
------
A. `POST /api/inventory/{id}/purchase` — yomon tanalar → 400 va HECH NARSA
   yozilmaydi (qoldiq, narx, hajm, xarid soni, to'lov soni)
B. purchase — NAZORAT: `suppliers.html` AYNAN yuboradigan tana → 200 va yozildi
C. `POST /api/inventory/receipt` — yomon tanalar → 400 va hech narsa yozilmaydi
D. receipt — NAZORAT: `supplier_receive.html` AYNAN tanasi; `paid_now`
   hujjat summasigacha qirqiladi; bir material ikki qatorda — RUXSAT
E. `POST` / `PUT /api/recipes` — yomon tanalar → 400; nazorat → 200
F. Ildiz (`crud._clean_val`) — uch model, pydantic chetlab o'tilgan holda
G. Statik — qoidalar sxemaga mos, UI yuboradigan kalitlar qoidalarda bor

ISHLATISH
---------
    python tools/test_kirim_qiymat.py
    TENANT_FILTER=1 python tools/test_kirim_qiymat.py

Asl kodga qarshi ham QULAMAYDI (mutatsiya uchun): HTTP istisnolari 599 ga
aylantiriladi, ildiz chaqiruvlari `try/except`.

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "kirim_qiymat_test.db")
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
import tenant_context as _tc                       # noqa: E402

engine.dispose()

from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Inventory, InventoryPurchase, InventoryReceipt, Recipe,
    RecipeIngredient, Supplier, SupplierPayment,
)
import schemas                                     # noqa: E402
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
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="Test Korxona B"))
    db.commit()

with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "KQ_admin", "Parol123!", UserRole.ADMIN, "KQ Admin",
                     company_id=1)

MAT = Inventory(company_id=1, item_name="KQ_SEMENT", unit="kg",
                stock_quantity=100.0, price_per_unit=1000, min_stock=0)
MAT2 = Inventory(company_id=1, item_name="KQ_MEL", unit="kg",
                 stock_quantity=50.0, price_per_unit=500, min_stock=0)
PENO = Inventory(company_id=1, item_name="KQ Penoplast", unit="blok",
                 stock_quantity=10.0, price_per_unit=200000, min_stock=0,
                 is_penoplast=True, volume_per_unit=1.4)
BEGONA = Inventory(company_id=2, item_name="KQ_BEGONA", unit="kg",
                   stock_quantity=5.0, price_per_unit=100, min_stock=0)
db.add_all([MAT, MAT2, PENO, BEGONA])
db.commit()
SUP = Supplier(company_id=1, name="KQ_TAMIN", phone="+998900000051")
SUPB = Supplier(company_id=2, name="KQ_BEGONA_TAMIN", phone="+998900000052")
db.add_all([SUP, SUPB])
db.commit()
REC = Recipe(company_id=1, name="KQ_RETSEPT", batch_size_kg=100.0)
db.add(REC)
db.commit()
db.add(RecipeIngredient(recipe_id=REC.id, inventory_id=MAT.id, quantity_kg=50.0))
db.commit()

M_ID, M2_ID, P_ID, B_ID = MAT.id, MAT2.id, PENO.id, BEGONA.id
S_ID, SB_ID, R_ID = SUP.id, SUPB.id, REC.id


def holat():
    """Yozilishi mumkin bo'lgan HAMMA narsa — bitta suratda."""
    db.expire_all()
    inv = {}
    for i in db.query(Inventory).all():
        inv[i.id] = (float(i.stock_quantity or 0), float(i.price_per_unit or 0),
                     None if i.volume_per_unit is None else float(i.volume_per_unit))
    return (inv,
            db.query(InventoryPurchase).count(),
            db.query(InventoryReceipt).count(),
            db.query(SupplierPayment).count(),
            db.query(Recipe).count(),
            db.query(RecipeIngredient).count())


def login(user):
    c = TestClient(main.app, base_url="https://testserver",
                   raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": "Parol123!"},
               follow_redirects=False)
    assert r.status_code == 302, f"{user} login bo'lmadi: {r.status_code}"
    return c


C = login("KQ_admin")


def req(method, url, **kw):
    try:
        return C.request(method.upper(), url, **kw)
    except Exception as e:          # pragma: no cover — himoya qatlami
        class _R:
            status_code = 599
            text = f"ISTISNO: {type(e).__name__}: {e}"

            def json(self):
                return {}
        return _R()


def yomon(label, method, url, tana=None, xom=None, kutilgan=(400,)):
    """Yomon tana → kutilgan holat VA hech narsa o'zgarmagan."""
    oldin = holat()
    if xom is not None:
        r = req(method, url, content=xom,
                headers={"Content-Type": "application/json"})
    else:
        r = req(method, url, json=tana)
    keyin = holat()
    check(f"{label} → {'/'.join(map(str, kutilgan))} va hech narsa yozilmadi",
          r.status_code in kutilgan and oldin == keyin,
          f"{r.status_code} " + ("| HOLAT O'ZGARDI" if oldin != keyin else "")
          + f" {r.text[:110]}")


print("=" * 66)
print("17b DARVOZASI — kirim / kirim hujjati / retsept qiymatlari")
print("TENANT_FILTER = " + ("1 (YOQILGAN)" if _tc.ENABLED else "0 (o'chiq)"))
print("=" * 66)

# ══════════════════════════════════════════════════════════════
section("A. POST /api/inventory/{id}/purchase — yomon tanalar")
# ══════════════════════════════════════════════════════════════
U = f"/api/inventory/{M_ID}/purchase"
UP = f"/api/inventory/{P_ID}/purchase"

yomon("A miqdor 1e20", "post", U, {"quantity": 1e20, "price_per_unit": 1})
yomon("A narx 1e20", "post", U, {"quantity": 1, "price_per_unit": 1e20})
yomon("A miqdor × narx sig'imdan oshdi (1e9 × 1e6)", "post", U,
      {"quantity": 1e9, "price_per_unit": 1e6})
# ⚠ Quyidagi ikki prob ATAYLAB shunday tanlangan: KO'PAYTMA sig'imdan
# OSHMAYDI (1e9), shuning uchun ularni faqat maydonning O'Z chegarasi
# ushlaydi. Aks holda "miqdor × narx" tekshiruvi ikkalasini ham yashirib,
# alohida chegaralar o'chirilsa ham test o'tib ketardi (mutatsiyada
# o'lchandi: M1/M2 — 0 yiqilish).
yomon("A miqdor 1e20 (ko'paytma kichik)", "post", U,
      {"quantity": 1e20, "price_per_unit": 1e-11})
yomon("A narx 1e20 (ko'paytma kichik)", "post", U,
      {"quantity": 1e-11, "price_per_unit": 1e20})
yomon("A miqdor 0", "post", U, {"quantity": 0, "price_per_unit": 1000})
yomon("A miqdor manfiy", "post", U, {"quantity": -5, "price_per_unit": 1000})
yomon("A narx 0", "post", U, {"quantity": 1, "price_per_unit": 0})
yomon("A quantity true", "post", U, {"quantity": True, "price_per_unit": 1000})
yomon("A narx matn '5000'", "post", U, {"quantity": 1, "price_per_unit": "5000"})
yomon("A miqdor yo'q", "post", U, {"price_per_unit": 1000})
yomon("A narx yo'q", "post", U, {"quantity": 1})
yomon("A Infinity miqdor (xom)", "post", U,
      xom='{"quantity": Infinity, "price_per_unit": 1000}')
yomon("A -Infinity miqdor (xom)", "post", U,
      xom='{"quantity": -Infinity, "price_per_unit": 1000}')
yomon("A NaN narx (xom)", "post", U, xom='{"quantity": 1, "price_per_unit": NaN}')
yomon("A transport_payer 'xato'", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "transport_payer": "xato",
       "transport_cost": 500})
yomon("A transport_cost manfiy", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "transport_cost": -1})
yomon("A payment_due_date 'abc'", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "payment_due_date": "abc"})
yomon("A payment_due_date '2026-13-45'", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "payment_due_date": "2026-13-45"})
yomon("A paid_now manfiy", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "paid_now": -1})
yomon("A notes 20000 belgi", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "notes": "x" * 20000})
yomon("A notes son", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "notes": 5})
yomon("A noma'lum maydon company_id", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "company_id": 2})
yomon("A supplier_id bool", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "supplier_id": True})
yomon("A is_opening_stock matn", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "is_opening_stock": "ha"})
yomon("A PENOPLAST volume_per_unit 1e20", "post", UP,
      {"quantity": 1, "price_per_unit": 1000, "volume_per_unit": 1e20})
yomon("A PENOPLAST volume_per_unit 0", "post", UP,
      {"quantity": 1, "price_per_unit": 1000, "volume_per_unit": 0})
yomon("A PENOPLAST volume_per_unit Infinity (xom)", "post", UP,
      xom='{"quantity": 1, "price_per_unit": 1000, "volume_per_unit": Infinity}')
yomon("A supplier_id mavjud emas", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "supplier_id": 99999999},
      kutilgan=(404,))
yomon("A supplier_id BEGONA korxonaniki", "post", U,
      {"quantity": 1, "price_per_unit": 1000, "supplier_id": SB_ID},
      kutilgan=(404,))
yomon("A BEGONA material + yomon tana (oracle yo'q)", "post",
      f"/api/inventory/{B_ID}/purchase", {"quantity": 1e20, "price_per_unit": 1},
      kutilgan=(404,))
yomon("A yo'q material", "post", "/api/inventory/99999999/purchase",
      {"quantity": 1, "price_per_unit": 1000}, kutilgan=(404,))
yomon("A ro'yxat tana (xom)", "post", U, xom='[{"quantity": 1}]',
      kutilgan=(400, 422))

# ══════════════════════════════════════════════════════════════
section("B. purchase NAZORATI — suppliers.html AYNAN tanasi")
# ══════════════════════════════════════════════════════════════
oldin = holat()
r = req("post", U, json={
    "quantity": 5, "price_per_unit": 2000, "paid_now": 5000,
    "supplier_id": S_ID, "notes": "Yetkazib beruvchi sahifasidan qo'shildi",
    "transport_payer": "self", "transport_cost": 1000, "volume_per_unit": None})
keyin = holat()
check("B1 UI tanasi (transport 'self', volume null) → 200",
      r.status_code == 200, f"{r.status_code} {r.text[:150]}")
check("B2 qoldiq 100 → 105 va xarid yozuvi qo'shildi",
      yaqin(keyin[0][M_ID][0], 105.0) and keyin[1] == oldin[1] + 1,
      f"qoldiq={keyin[0][M_ID][0]} xaridlar={keyin[1]}-{oldin[1]}")
r = req("post", UP, json={
    "quantity": 2, "price_per_unit": 300000, "paid_now": 0,
    "supplier_id": S_ID, "notes": None, "transport_payer": "none",
    "transport_cost": 0, "volume_per_unit": 1.5})
check("B3 PENOPLAST kirimi volume_per_unit 1.5 bilan → 200",
      r.status_code == 200, f"{r.status_code} {r.text[:120]}")
db.expire_all()
_p = db.query(Inventory).filter(Inventory.id == P_ID).first()
check("B4 penoplast hajmi o'rtachaga o'zgardi (1.4 va 1.5 orasida)",
      _p is not None and 1.4 <= float(_p.volume_per_unit) <= 1.5,
      f"hajm={None if not _p else _p.volume_per_unit}")
r = req("post", U, json={"quantity": 1, "price_per_unit": 1000,
                         "payment_due_date": "2026-12-31", "supplier_id": S_ID})
check("B5 to'g'ri sana (2026-12-31) → 200", r.status_code == 200,
      f"{r.status_code} {r.text[:120]}")
r = req("post", U, json={"quantity": 1, "price_per_unit": 1000,
                         "is_opening_stock": True})
check("B6 boshlang'ich ombor (is_opening_stock) → 200", r.status_code == 200,
      f"{r.status_code} {r.text[:120]}")
db.expire_all()
_tol0 = db.query(SupplierPayment).count()
r = req("post", U, json={"quantity": 1, "price_per_unit": 1000,
                         "paid_now": 1e6, "supplier_id": S_ID})
db.expire_all()
_j = r.json() if r.status_code == 200 else {}
check("B7 paid_now jamidan katta → 200 va jamigacha QIRQILDI (1000), qarz 0",
      r.status_code == 200 and yaqin(_j.get("paid_now"), 1000.0)
      and yaqin(_j.get("debt_remains"), 0.0),
      f"{r.status_code} paid_now={_j.get('paid_now')} qarz={_j.get('debt_remains')}")
check("B8 to'liq to'langan xarid — alohida to'lov yozuvi YOZILMAYDI "
      "(qarz yo'q, dizayn)",
      db.query(SupplierPayment).count() == _tol0,
      f"{db.query(SupplierPayment).count()} != {_tol0}")

# ══════════════════════════════════════════════════════════════
section("C. POST /api/inventory/receipt — yomon tanalar")
# ══════════════════════════════════════════════════════════════
RU = "/api/inventory/receipt"


def qator(inv_id=None, **kw):
    q = {"inventory_id": inv_id or M_ID, "quantity": 1, "price_per_unit": 100}
    q.update(kw)
    return q


yomon("C items bo'sh", "post", RU, {"items": []})
yomon("C items yo'q", "post", RU, {"supplier_id": S_ID})
yomon("C items ro'yxat emas", "post", RU, {"items": {"inventory_id": M_ID}})
yomon("C qator miqdori 1e20", "post", RU, {"items": [qator(quantity=1e20)]})
yomon("C qator narxi 1e20", "post", RU, {"items": [qator(price_per_unit=1e20)]})
yomon("C qator miqdor × narx sig'imdan oshdi", "post", RU,
      {"items": [qator(quantity=1e9, price_per_unit=1e6)]})
yomon("C qator narxi 1e20 (ko'paytma kichik)", "post", RU,
      {"items": [qator(quantity=1e-11, price_per_unit=1e20)]})
yomon("C qator miqdori 1e20 (ko'paytma kichik)", "post", RU,
      {"items": [qator(quantity=1e20, price_per_unit=1e-11)]})
yomon("C qator miqdori 0", "post", RU, {"items": [qator(quantity=0)]})
yomon("C qator narxi manfiy", "post", RU, {"items": [qator(price_per_unit=-1)]})
yomon("C qator Infinity narx (xom)", "post", RU,
      xom='{"items": [{"inventory_id": %d, "quantity": 1, "price_per_unit": Infinity}]}' % M_ID)
yomon("C qator NaN miqdor (xom)", "post", RU,
      xom='{"items": [{"inventory_id": %d, "quantity": NaN, "price_per_unit": 100}]}' % M_ID)
yomon("C qatorda noma'lum maydon", "post", RU,
      {"items": [qator(company_id=2)]})
yomon("C qatorda inventory_id yo'q", "post", RU,
      {"items": [{"quantity": 1, "price_per_unit": 100}]})
yomon("C transport_cost Infinity (xom)", "post", RU,
      xom='{"items": [{"inventory_id": %d, "quantity": 1, "price_per_unit": 100}],'
          ' "transport_cost": Infinity}' % M_ID)
yomon("C transport_cost 1e20", "post", RU,
      {"items": [qator()], "transport_cost": 1e20})
yomon("C tushirish_cost manfiy", "post", RU,
      {"items": [qator()], "tushirish_cost": -5})
yomon("C yuklash_cost 1e20", "post", RU,
      {"items": [qator()], "yuklash_cost": 1e20})
yomon("C boshqa_cost matn", "post", RU,
      {"items": [qator()], "boshqa_cost": "500"})
yomon("C paid_now 1e20", "post", RU, {"items": [qator()], "paid_now": 1e20})
yomon("C paid_now manfiy", "post", RU, {"items": [qator()], "paid_now": -1})
yomon("C production_type 'xato'", "post", RU,
      {"items": [qator()], "production_type": "xato"})
yomon("C document_number 500 belgi", "post", RU,
      {"items": [qator()], "document_number": "D" * 500})
yomon("C add_to_cost matn", "post", RU, {"items": [qator()], "add_to_cost": "ha"})
yomon("C noma'lum maydon", "post", RU, {"items": [qator()], "company_id": 2})
yomon("C 201 qator", "post", RU, {"items": [qator()] * 201})
yomon("C inventory_id mavjud emas", "post", RU,
      {"items": [qator(inv_id=99999999)]}, kutilgan=(404,))
yomon("C inventory_id BEGONA korxonaniki", "post", RU,
      {"items": [qator(inv_id=B_ID)]}, kutilgan=(404,))
yomon("C supplier_id BEGONA korxonaniki", "post", RU,
      {"items": [qator()], "supplier_id": SB_ID}, kutilgan=(404,))
yomon("C PENOPLAST qatori volume 1e20", "post", RU,
      {"items": [qator(inv_id=P_ID, volume_per_unit=1e20)]})
yomon("C PENOPLAST qatori volume Infinity (xom)", "post", RU,
      xom='{"items": [{"inventory_id": %d, "quantity": 1, "price_per_unit": 100,'
          ' "volume_per_unit": Infinity}]}' % P_ID)

# ══════════════════════════════════════════════════════════════
section("D. receipt NAZORATI — supplier_receive.html AYNAN tanasi")
# ══════════════════════════════════════════════════════════════
oldin = holat()
r = req("post", RU, json={
    "items": [{"inventory_id": M_ID, "quantity": 4, "price_per_unit": 1500,
               "volume_per_unit": None, "is_opening_stock": False},
              {"inventory_id": M2_ID, "quantity": 2, "price_per_unit": 700,
               "volume_per_unit": None, "is_opening_stock": False}],
    "supplier_id": S_ID, "document_number": "KQ-001", "paid_now": 3000,
    "transport_cost": 200, "tushirish_cost": 100, "yuklash_cost": 0,
    "boshqa_cost": 0, "add_to_cost": True,
    "notes": "Kirim sahifasidan qo'shildi", "production_type": None})
keyin = holat()
check("D1 UI tanasi (2 qator, xarajatlar, production_type null) → 200",
      r.status_code == 200, f"{r.status_code} {r.text[:160]}")
check("D2 ikkala material ham ko'paydi va hujjat yozildi",
      keyin[0][M_ID][0] > oldin[0][M_ID][0]
      and keyin[0][M2_ID][0] > oldin[0][M2_ID][0]
      and keyin[2] == oldin[2] + 1,
      f"hujjat={keyin[2]}-{oldin[2]}")
r = req("post", RU, json={
    "items": [{"inventory_id": P_ID, "quantity": 1, "price_per_unit": 250000,
               "volume_per_unit": 1.45, "is_opening_stock": False}],
    "supplier_id": S_ID, "document_number": None, "paid_now": 0,
    "transport_cost": 0, "tushirish_cost": 0, "yuklash_cost": 0,
    "boshqa_cost": 0, "add_to_cost": False, "notes": None,
    "production_type": "penoplast"})
check("D3 penoplast qatori + production_type 'penoplast' → 200",
      r.status_code == 200, f"{r.status_code} {r.text[:130]}")
r = req("post", RU, json={
    "items": [qator()], "production_type": "gips"})
check("D4 production_type 'gips' → 200", r.status_code == 200,
      f"{r.status_code} {r.text[:120]}")
r = req("post", RU, json={"items": [qator()], "production_type": "umumiy"})
check("D5 production_type 'umumiy' → 200", r.status_code == 200,
      f"{r.status_code} {r.text[:120]}")

oldin = holat()
r = req("post", RU, json={
    "items": [{"inventory_id": M_ID, "quantity": 2, "price_per_unit": 1000,
               "volume_per_unit": None, "is_opening_stock": False},
              {"inventory_id": M_ID, "quantity": 3, "price_per_unit": 1200,
               "volume_per_unit": None, "is_opening_stock": False}],
    "supplier_id": S_ID, "paid_now": 0})
keyin = holat()
check("D6 bir material IKKI qatorda (ikki narx) → 200, qoldiq +5 (ATAYLAB ruxsat)",
      r.status_code == 200 and yaqin(keyin[0][M_ID][0], oldin[0][M_ID][0] + 5),
      f"{r.status_code} qoldiq {oldin[0][M_ID][0]} → {keyin[0][M_ID][0]}")

db.expire_all()
_tol_oldin = db.query(SupplierPayment).count()
r = req("post", RU, json={
    "items": [{"inventory_id": M_ID, "quantity": 1, "price_per_unit": 500}],
    "supplier_id": S_ID, "paid_now": 900000, "transport_cost": 100})
db.expire_all()
_oxirgi = db.query(SupplierPayment).order_by(SupplierPayment.id.desc()).first()
check("D7 paid_now hujjat summasidan katta → to'lov 600 ga QIRQILDI",
      r.status_code == 200
      and db.query(SupplierPayment).count() == _tol_oldin + 1
      and _oxirgi is not None and yaqin(_oxirgi.amount, 600.0),
      f"{r.status_code} to'lov={None if not _oxirgi else float(_oxirgi.amount)}")

for u in ["/", "/inventory", "/finance", "/suppliers", "/suppliers/receive",
          "/api/inventory", "/api/penoplasts", "/api/finance/history",
          "/api/suppliers", "/api/recipes", "/api/inventory/purchases"]:
    check(f"D8 sahifa {u} → 200", req("get", u).status_code == 200)

# ══════════════════════════════════════════════════════════════
section("E. POST / PUT /api/recipes")
# ══════════════════════════════════════════════════════════════


def ing(inv_id=None, qty=10):
    return {"inventory_id": inv_id or M_ID, "quantity_kg": qty}


yomon("E nom faqat bo'shliq", "post", "/api/recipes",
      {"name": "   ", "ingredients": [ing()]})
yomon("E nom bo'sh matn", "post", "/api/recipes",
      {"name": "", "ingredients": [ing()]})
yomon("E nom yo'q", "post", "/api/recipes", {"ingredients": [ing()]})
yomon("E nom 101 belgi", "post", "/api/recipes",
      {"name": "N" * 101, "ingredients": [ing()]})
yomon("E nom son", "post", "/api/recipes", {"name": 5, "ingredients": [ing()]})
yomon("E batch_size_kg Infinity (xom)", "post", "/api/recipes",
      xom='{"name": "KQ_inf", "batch_size_kg": Infinity, "ingredients": '
          '[{"inventory_id": %d, "quantity_kg": 1}]}' % M_ID)
yomon("E batch_size_kg 1e20", "post", "/api/recipes",
      {"name": "KQ_k", "batch_size_kg": 1e20, "ingredients": [ing()]})
yomon("E batch_size_kg 0", "post", "/api/recipes",
      {"name": "KQ_n", "batch_size_kg": 0, "ingredients": [ing()]})
yomon("E quantity_kg 1e20", "post", "/api/recipes",
      {"name": "KQ_k2", "ingredients": [ing(qty=1e20)]})
yomon("E quantity_kg Infinity (xom)", "post", "/api/recipes",
      xom='{"name": "KQ_inf2", "ingredients": '
          '[{"inventory_id": %d, "quantity_kg": Infinity}]}' % M_ID)
yomon("E quantity_kg 0", "post", "/api/recipes",
      {"name": "KQ_n2", "ingredients": [ing(qty=0)]})
yomon("E bir material IKKI marta", "post", "/api/recipes",
      {"name": "KQ_takror", "ingredients": [ing(qty=10), ing(qty=20)]})
yomon("E ingredients BO'SH", "post", "/api/recipes",
      {"name": "KQ_bosh", "ingredients": []})
yomon("E ingredients YO'Q", "post", "/api/recipes", {"name": "KQ_yoq"})
yomon("E 101 ingredient", "post", "/api/recipes",
      {"name": "KQ_kop", "ingredients": [ing()] * 101})
yomon("E notes 20000 belgi", "post", "/api/recipes",
      {"name": "KQ_izoh", "notes": "z" * 20000, "ingredients": [ing()]})
yomon("E noma'lum maydon", "post", "/api/recipes",
      {"name": "KQ_nm", "company_id": 2, "ingredients": [ing()]})
yomon("E ingredient yo'q material", "post", "/api/recipes",
      {"name": "KQ_bg", "ingredients": [ing(inv_id=99999999)]}, kutilgan=(404,))
yomon("E ingredient BEGONA material", "post", "/api/recipes",
      {"name": "KQ_bg2", "ingredients": [ing(inv_id=B_ID)]}, kutilgan=(404,))

yomon("E PUT nom bo'shliq", "put", f"/api/recipes/{R_ID}",
      {"name": "   ", "ingredients": [ing()]})
yomon("E PUT batch Infinity (xom)", "put", f"/api/recipes/{R_ID}",
      xom='{"name": "KQ_x", "batch_size_kg": Infinity, "ingredients": '
          '[{"inventory_id": %d, "quantity_kg": 1}]}' % M_ID)
yomon("E PUT ingredients BO'SH (tarkib o'chib ketardi)", "put",
      f"/api/recipes/{R_ID}", {"name": "KQ_x2", "ingredients": []})
yomon("E PUT bir material ikki marta", "put", f"/api/recipes/{R_ID}",
      {"name": "KQ_x3", "ingredients": [ing(qty=1), ing(qty=2)]})
yomon("E PUT noma'lum maydon", "put", f"/api/recipes/{R_ID}",
      {"name": "KQ_x4", "company_id": 2, "ingredients": [ing()]})
yomon("E PUT yo'q retsept + yomon tana (oracle yo'q)", "put",
      "/api/recipes/99999999", {"name": "   ", "ingredients": []},
      kutilgan=(404,))

oldin = holat()
r = req("post", "/api/recipes", json={
    "name": "KQ_yangi", "batch_size_kg": 150,
    "notes": "sinov", "ingredients": [ing(qty=60), ing(inv_id=M2_ID, qty=40)]})
keyin = holat()
check("E NAZORAT: to'g'ri retsept (2 ta material) → 200 va yozildi",
      r.status_code == 200 and keyin[4] == oldin[4] + 1
      and keyin[5] == oldin[5] + 2,
      f"{r.status_code} retsept={keyin[4]}-{oldin[4]} ing={keyin[5]}-{oldin[5]}")
r = req("put", f"/api/recipes/{R_ID}", json={
    "name": "KQ_RETSEPT_yangilandi", "batch_size_kg": 120, "notes": None,
    "ingredients": [ing(qty=30), ing(inv_id=M2_ID, qty=20)]})
db.expire_all()
_rec = db.query(Recipe).filter(Recipe.id == R_ID).first()
check("E NAZORAT: PUT to'g'ri tana → 200 va tarkib 2 ta bo'ldi",
      r.status_code == 200 and _rec is not None
      and _rec.name == "KQ_RETSEPT_yangilandi"
      and db.query(RecipeIngredient).filter(
          RecipeIngredient.recipe_id == R_ID).count() == 2,
      f"{r.status_code} {r.text[:130]}")

# ══════════════════════════════════════════════════════════════
section("F. Ildiz — crud._clean_val (pydantic chetlab o'tilgan)")
# ══════════════════════════════════════════════════════════════


def cv(model, data):
    """Ildiz chaqiruvi — model yo'q bo'lsa ham skript QULAMAYDI
    (asl kodga qarshi mutatsiya uchun: u yerda bu modellar yo'q)."""
    try:
        return crud._clean_val(model, data)
    except ValueError as e:
        return f"XATO: {e}"
    except Exception as e:          # pragma: no cover — mutatsiya himoyasi
        return f"ISTISNO: {type(e).__name__}"


check("F1 Purchase to'g'ri tana → lug'at",
      isinstance(cv("Purchase", {"quantity": 1, "price_per_unit": 100}), dict))
check("F2 Purchase cheksiz miqdor → xato",
      str(cv("Purchase", {"quantity": float('inf'), "price_per_unit": 1})).startswith("XATO"))
check("F3 Purchase transport_payer 'xato' → xato",
      str(cv("Purchase", {"quantity": 1, "price_per_unit": 1,
                          "transport_payer": "xato"})).startswith("XATO"))
check("F4 Purchase transport_payer 'self' → o'tadi",
      isinstance(cv("Purchase", {"quantity": 1, "price_per_unit": 1,
                                 "transport_payer": "self"}), dict))
check("F5 Purchase miqdor × narx chegarasi → xato",
      str(cv("Purchase", {"quantity": 1e9, "price_per_unit": 1e6})).startswith("XATO"))
check("F6 ReceiptItem volume_per_unit 0 → xato",
      str(cv("ReceiptItem", {"inventory_id": 1, "quantity": 1,
                             "price_per_unit": 1,
                             "volume_per_unit": 0})).startswith("XATO"))
# ⚠ Ildiz darajasidagi probalar — marshrutda pydantic sxemasi IKKINCHI
# to'siq bo'lib turadi (`Field(gt=0)`, `min_length=1`), shuning uchun
# faqat HTTP orqali sinalsa qoidaning o'zi o'chirilgani BILINMAYDI
# (mutatsiyada o'lchandi: M6/M10 — 0 yiqilish).
check("F6b Purchase volume_per_unit 0 → xato (ildizda)",
      str(cv("Purchase", {"quantity": 1, "price_per_unit": 1,
                          "volume_per_unit": 0})).startswith("XATO"),
      str(cv("Purchase", {"quantity": 1, "price_per_unit": 1,
                          "volume_per_unit": 0})))
check("F6c Receipt items BO'SH → xato (ildizda)",
      str(cv("Receipt", {"items": []})).startswith("XATO"),
      str(cv("Receipt", {"items": []})))
check("F6d ReceiptItem narxi chegaradan katta → xato (ildizda)",
      str(cv("ReceiptItem", {"inventory_id": 1, "quantity": 1e-11,
                             "price_per_unit": 1e20})).startswith("XATO"))
check("F7 Receipt production_type None → o'tadi",
      isinstance(cv("Receipt", {"items": [{"inventory_id": 1, "quantity": 1,
                                           "price_per_unit": 1}],
                                "production_type": None}), dict))
check("F8 Receipt document_number 51 belgi → xato",
      str(cv("Receipt", {"items": [{"inventory_id": 1, "quantity": 1,
                                    "price_per_unit": 1}],
                         "document_number": "D" * 51})).startswith("XATO"))
check("F9 Receipt document_number 50 belgi → o'tadi",
      isinstance(cv("Receipt", {"items": [{"inventory_id": 1, "quantity": 1,
                                           "price_per_unit": 1}],
                                "document_number": "D" * 50}), dict))
check("F10 RecipeBody takror material → xato",
      str(cv("RecipeBody", {"name": "x", "ingredients": [
          {"inventory_id": 7, "quantity_kg": 1},
          {"inventory_id": 7, "quantity_kg": 2}]})).startswith("XATO"))
check("F11 RecipeBody har xil material → o'tadi",
      isinstance(cv("RecipeBody", {"name": "x", "ingredients": [
          {"inventory_id": 7, "quantity_kg": 1},
          {"inventory_id": 8, "quantity_kg": 2}]}), dict))
check("F12 Receipt takror material — ATAYLAB o'tadi",
      isinstance(cv("Receipt", {"items": [
          {"inventory_id": 7, "quantity": 1, "price_per_unit": 1},
          {"inventory_id": 7, "quantity": 2, "price_per_unit": 2}]}), dict))
check("F13 xato matnida qator raqami bor",
      "2-qator" in str(cv("Receipt", {"items": [
          {"inventory_id": 7, "quantity": 1, "price_per_unit": 1},
          {"inventory_id": 8, "quantity": -1, "price_per_unit": 1}]})),
      str(cv("Receipt", {"items": [
          {"inventory_id": 7, "quantity": 1, "price_per_unit": 1},
          {"inventory_id": 8, "quantity": -1, "price_per_unit": 1}]})))
def _takror_sinov(qatorlar):
    f = getattr(crud, "_takror_material_yoq", None)
    if f is None:
        return "YO'Q"
    try:
        f(qatorlar, "inventory_id", "x")
        return "o'tdi"
    except ValueError as e:
        return f"XATO: {e}"
    except Exception as e:          # pragma: no cover
        return f"ISTISNO: {type(e).__name__}"


check("F14 _takror_material_yoq — bo'sh ro'yxat xato bermaydi",
      _takror_sinov([]) == "o'tdi", _takror_sinov([]))
check("F15 _takror_material_yoq — takror id da xato",
      str(_takror_sinov([{"inventory_id": 3}, {"inventory_id": 3}])).startswith("XATO"),
      _takror_sinov([{"inventory_id": 3}, {"inventory_id": 3}]))

# ══════════════════════════════════════════════════════════════
section("G. Statik — qoidalar sxema va UI bilan mos")
# ══════════════════════════════════════════════════════════════
try:
    _QOIDA = crud._val_rules()
except Exception:                   # pragma: no cover — mutatsiya himoyasi
    _QOIDA = {}


def _q(model):
    """Model qoidalari — bo'lmasa bo'sh to'plam (skript qulamasin)."""
    return set((_QOIDA.get(model) or {}).keys())


for model, sxema in [("Purchase", schemas.StockPurchase),
                     ("ReceiptItem", schemas.ReceiptItemCreate),
                     ("Receipt", schemas.InventoryReceiptCreate),
                     ("RecipeIngredient", schemas.RecipeIngredientCreate),
                     ("RecipeBody", schemas.RecipeCreate)]:
    maydonlar = set(sxema.model_fields.keys())
    qoidalar = _q(model)
    check(f"G {model}: qoidalar bor va ⊆ sxema maydonlari",
          bool(qoidalar) and qoidalar <= maydonlar,
          f"ortiqcha: {sorted(qoidalar - maydonlar)}" if qoidalar else "QOIDA YO'Q")
    check(f"G {model}: sxemadagi HAR maydon qoidada bor",
          maydonlar <= qoidalar, f"yetishmaydi: {sorted(maydonlar - qoidalar)}")

# UI AYNAN yuboradigan kalitlar
UI_PURCHASE = {"quantity", "price_per_unit", "paid_now", "supplier_id", "notes",
               "transport_payer", "transport_cost", "volume_per_unit"}
UI_RECEIPT = {"items", "supplier_id", "document_number", "paid_now",
              "transport_cost", "tushirish_cost", "yuklash_cost", "boshqa_cost",
              "add_to_cost", "notes", "production_type"}
UI_RECEIPT_ITEM = {"inventory_id", "quantity", "price_per_unit",
                   "volume_per_unit", "is_opening_stock"}
UI_RECIPE = {"name", "batch_size_kg", "notes", "ingredients"}
check("G1 suppliers.html kalitlari qoidalarda bor",
      UI_PURCHASE <= _q("Purchase"), f"{sorted(UI_PURCHASE - _q('Purchase'))}")
check("G2 supplier_receive.html kalitlari qoidalarda bor",
      UI_RECEIPT <= _q("Receipt"), f"{sorted(UI_RECEIPT - _q('Receipt'))}")
check("G3 supplier_receive.html QATOR kalitlari qoidalarda bor",
      UI_RECEIPT_ITEM <= _q("ReceiptItem"),
      f"{sorted(UI_RECEIPT_ITEM - _q('ReceiptItem'))}")
check("G4 recipes.html kalitlari qoidalarda bor",
      UI_RECIPE <= _q("RecipeBody"), f"{sorted(UI_RECIPE - _q('RecipeBody'))}")

with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
    MAIN = f.read()
with open(os.path.join(ROOT, "crud.py"), encoding="utf-8") as f:
    CRUD = f.read()
with open(os.path.join(ROOT, "templates", "supplier_receive.html"),
          encoding="utf-8") as f:
    RCV = f.read()

check("G5 purchase marshruti xom dict oladi",
      "def api_purchase_stock(item_id: int, data: dict = Body(...)" in MAIN)
check("G6 receipt marshruti xom dict oladi",
      "def api_create_inventory_receipt(data: dict = Body(...)" in MAIN)
check("G7 retsept marshrutlari xom dict oladi",
      "def api_create_recipe(recipe: dict = Body(...)" in MAIN
      and "def api_update_recipe(recipe_id: int, data: dict = Body(...)" in MAIN)
check("G8 `_tana_400` yordamchisi bor va 4 marta ishlatiladi",
      "def _tana_400(" in MAIN and MAIN.count("_tana_400(") >= 5,
      f"soni={MAIN.count('_tana_400(')}")
check("G9 receipt paid_now hujjat summasigacha qirqiladi",
      "_paid_now = min(float(data.paid_now), round(_jami))" in MAIN)
check("G10 `_TRANSPORT_TOLOVCHI` va `_ISHLAB_CHIQARISH_TURI` mavjud",
      "_TRANSPORT_TOLOVCHI = {" in CRUD and "_ISHLAB_CHIQARISH_TURI = {" in CRUD)
_TP = set(getattr(crud, "_TRANSPORT_TOLOVCHI", {}) or {})
_PT = set(getattr(crud, "_ISHLAB_CHIQARISH_TURI", {}) or {})
check("G11 transport_payer qiymatlari UI dagi bilan bir xil",
      _TP == {"none", "self", "supplier"}, f"{sorted(_TP)}")
check("G12 production_type UI dagi tanlovlarni qamrab oladi",
      {"penoplast", "gips"} <= _PT and '<option value="penoplast">' in RCV,
      f"{sorted(_PT)}")

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
