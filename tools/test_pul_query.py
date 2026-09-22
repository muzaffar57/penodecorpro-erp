#!/usr/bin/env python3
"""
test_pul_query.py — 17f-band: pul maydonlarining ANIQLIGI (1 tiyindan kichik
musbat summa) va SIG'IMI (Numeric(12,2)), kirish transporti, mijoz to'lovi,
sovg'a davri, xarid tahriri va xarid / kirim hujjatining hosila yozuvlari.

NIMA UCHUN KERAK (2026-09-22)
-----------------------------
Hammasi HAQIQIY PostgreSQL 16 da O'LCHANGAN (`work/probe17f_pg.py`,
`work/probe17f_hosila.py`; asl kod = 17e). SQLite `Numeric(12,2)` ni
yaxlitlamaydi va sig'im oshishini sezmaydi — shuning uchun oldingi lokal
testlar bularning birortasini ko'rmagan:

1) MUSBAT bo'lishi shart bo'lgan 12 ta pul yo'lining HAMMASI `0.001` ni 200
   bilan qabul qilardi, baza esa uni 0.00 ga yaxlitlardi: 0 so'mlik xarajat,
   avans, oylik yopish, ta'minotchiga to'lov, mijoz to'lovi, transport,
   majburiyat, sovg'a bosqichi; kelishilgan summa 0 (chegirma 100 %); xarid
   narxi 0.00 lekin jami 0.01 (bir-biriga zid).
2) Xarid TAHRIRI: narx `1e10` va miqdor × narx `1e6 × 1e5` — 500 (narx uchun
   Float chegarasi ishlatilardi, jami summa tekshirilmasdi).
3) `POST /api/transport-expenses`: `Infinity` / `1e20` / 25 belgili tur /
   300 belgili izoh — 500; `true` → 1 so'm, `"5"`, ro'yxatdan tashqari tur —
   qabul.
4) `POST /api/payments`: `Infinity` / `1e20` — 500 (takror-tekshiruv
   so'rovida); `true` → 1 so'mlik to'lov, `"5"`, `order_id: true` →
   1-buyurtma; noto'g'ri tur / usul JIMGINA partial / naqd.
5) `POST /api/gift-period/open`: bosqichlar tekshiruvsiz `float(...)` — matn,
   `[5]`, nom son, `Infinity`, `1e20`, 101 belgili nom — HAMMASI 500;
   `master_ids` dagi `true` → 1-usta.
6) HOSILA yozuvlar: xarid `paid_now: 0.001` — 17e da 0 so'mlik ta'minotchi
   to'lovi; ta'minotchi to'lovi ildizi qat'iy bo'lgach esa xarid SAQLANIB,
   keyin 500 (yarim saqlanish). "O'z hisobimdan" transport `0.001` — 0 so'mlik
   transport. Kirim hujjati transport / tushirish / yuklash / boshqa / to'lov
   `0.001` — 0 so'mlik Moliya xarajati / to'lov.

QAMROV
------
A. Tiyin: 13 yo'l × (0.001, 0.004 → 400, holat o'zgarmagan, sabab "0.01";
   0.005 → 200 va 0.01; 0.02 → 200 va 0.02)
B. Xarid tahriri sig'imi: 1e10, 1e6 × 1e5, faqat narx / faqat miqdor
   berilganda ham (ikkinchisi yozuvdan); chegara 9 999 999 999.95 — 200
C. Transport: yomon tanalar 400 (`detail` MATN), holat o'zgarmagan; to'g'ri
   tanalar — aniq qiymatlar, korxona
D. Mijoz to'lovi: yomon tanalar 400; `orders.html` (to'lov oynasi, zaklat)
   va `debts.html` tanalari AYNAN 200 va aniq qiymatlar; 404 / 409 / 3 baravar
   / takror / chegirmaga yozish — saqlangan; loyiha `total_paid`
E. Sovg'a davri: ochish — yomon 400, `kpi.html` tanalari 200 (saralash,
   `strip`, takror va begona ustalar); bosqich tahriri — yomon 400, to'g'ri 200
X. Hosila: xarid va kirim hujjatidagi 0-yoki-tiyin maydonlar — yarim
   saqlanish yo'q, 0 so'mlik hosila yozuv yo'q
F. Ildiz: `create_transport_expense`, `create_payment`, `open_gift_period`,
   `update_gift_period_tier`, `_clean_val`, `_json_son`, `_xarid_son`,
   `_sovga_ustalari` — bazaga tegmasdan rad
G. Statik: marshrut turlari, tekshiruv TARTIBI (yozishdan OLDIN), qoidalar,
   sxemalar, UI (server sababi, 409 tasdiq)
H. 422 qoladi (tana lug'at emas / buzilgan JSON), 500 emas
K. KUMULYATIV: hamma problardan keyin sahifalar 200; hech bir javob 500 emas
P. PostgreSQL (faqat `PG_URL` muhitda bo'lsa, masalan
   `PG_URL=postgresql://postgres@127.0.0.1:5432`): shu skript o'zini
   `PUL_PG_REJIM=1` bilan YANGI PostgreSQL bazasida qayta ishga tushiradi va
   A, B, C, D, E, X, F, H, K ni o'sha yerda bajaradi (tiklashsiz — har
   tekshiruv o'z oldingi holatiga nisbatan), qo'shimcha: saqlangan qiymat
   AYNAN "0.01" / "9999999999.95" (0.00 EMAS). Natija umumiy songa qo'shiladi.

ISHLATISH
---------
    python tools/test_pul_query.py
    TENANT_FILTER=1 python tools/test_pul_query.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python tools/test_pul_query.py

Asl kodga qarshi ham QULAMAYDI (mutatsiya uchun): yangi yordamchilarga
murojaat `getattr` bilan, ildiz chaqiruvlari `try/except` bilan, HTTP
istisnolar 599 ga aylantiriladi, statik tartib `tartibda()` (`find`) bilan.

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import json
import shutil
import inspect
import tempfile
import subprocess
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_REJIM = os.environ.get("PUL_PG_REJIM") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "pul_query_test"

_DB = os.path.join(tempfile.gettempdir(), "pul_query_test.db")
_SNAP = _DB + ".nusxa"

if PG_REJIM:
    # Har ishga YANGI PostgreSQL bazasi (izolyatsiya qoidasi).
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
               isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    for _f in (_DB, _SNAP):
        if os.path.exists(_f):
            os.remove(_f)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, schemas                     # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderType, OrderStatus, ExpenseTransaction,
    Employee, Inventory, Supplier, InventoryPurchase, InventoryReceipt,
    SupplierPayment, EmployeeAdvance, RecurringObligation, TransportExpense,
    Payment, GiftPeriod, GiftPeriodTier, GiftPeriodParticipant, Master,
)
from fastapi.testclient import TestClient          # noqa: E402

OK = FAIL = 0
FAILED = []
KODLAR = []          # barcha HTTP javob kodlari (K: 500 yo'qligi)
YORLIQ = "[PG] " if PG_REJIM else ""
MONEY = 9_999_999_999.99


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:300]}")


def section(t):
    print(f"\n--- {YORLIQ}{t} ---")


def yaqin(a, b, eps=1e-6):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


def tiyin_ok(v, kutilgan):
    """Saqlangan pul qiymati `kutilgan` (2 xonali) ga teng. SQLite yaxlitlamaydi
    (0.005 saqlanadi — 2 xonaga yaxlitlab solishtiriladi); PostgreSQL da
    AYNAN shu matn bo'lishi SHART (0.00 EMAS)."""
    if v is None:
        return False
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    if f <= 0 or round(f, 2) != round(kutilgan, 2):
        return False
    if PG_REJIM:
        return str(v) == f"{kutilgan:.2f}"
    return True


def tartibda(src, *qismlar):
    """`qismlar` `src` ichida AYNAN shu tartibda uchraydimi. Birortasi yo'q
    bo'lsa — False (asl kodga qarshi `ValueError` bilan QULAMASLIK uchun)."""
    joy = -1
    for q in qismlar:
        i = src.find(q, joy + 1)
        if i < 0:
            return False
        joy = i
    return True


def manba(obj):
    try:
        return inspect.getsource(obj)
    except Exception:
        return ""


def fayl(nom):
    try:
        with open(os.path.join(ROOT, nom), encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def js_funksiya(src, nom):
    """HTML dan `function nom(` tanasini (qavslar bo'yicha) ajratib oladi."""
    for bosh in (f"async function {nom}(", f"function {nom}("):
        i = src.find(bosh)
        if i >= 0:
            j = src.find("{", i)
            d = 0
            for k in range(j, len(src)):
                if src[k] == "{":
                    d += 1
                elif src[k] == "}":
                    d -= 1
                    if d == 0:
                        return src[i:k + 1]
    return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="Test Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "PQ_admin", "Parol123!", UserRole.ADMIN, "PQ Admin", company_id=1)
    auth.create_user(_db, "PQ_admin_b", "Parol123!", UserRole.ADMIN, "PQ Admin B", company_id=2)

PRJ = Project(company_id=1, client_name="PQ Mijoz", project_name="PQ loyiha",
              total_budget=0, total_paid=0)
PRJ_B = Project(company_id=2, client_name="PQ Mijoz B", project_name="PQ loyiha B",
                total_budget=0, total_paid=0)
_db.add_all([PRJ, PRJ_B])
_db.commit()


def _buyurtma(cid, prj, nomer, summa):
    return Order(company_id=cid, project_id=prj.id, order_number=nomer,
                 order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS,
                 total_amount=summa, agreed_amount=summa, discount_percent=0.0)


ORD_A = _buyurtma(1, PRJ, "PQ-A", 1_000_000)        # kelishilgan summa
ORD_T = _buyurtma(1, PRJ, "PQ-T", 10_000_000)       # to'lovlar
ORD_O = _buyurtma(1, PRJ, "PQ-O", 100_000)          # ortiqcha to'lov / 3 baravar
ORD_W = _buyurtma(1, PRJ, "PQ-W", 100_000)          # chegirmaga yozish
ORD_B = _buyurtma(2, PRJ_B, "PQ-B", 2_000_000)      # begona korxona
EMP = Employee(company_id=1, name="PQ Hodim")
MAT = Inventory(company_id=1, item_name="PQ_SEMENT", unit="kg",
                stock_quantity=100.0, price_per_unit=1000, min_stock=0)
SUP = Supplier(company_id=1, name="PQ_TAMIN", phone="+998900009911")
SUP2 = Supplier(company_id=1, name="PQ_TAMIN2", phone="+998900009912")
SUP_B = Supplier(company_id=2, name="PQ_TAMIN_B", phone="+998900009913")
USTA = Master(company_id=1, name="PQ Usta", phone="+998900009914")
USTA_B = Master(company_id=2, name="PQ Usta B", phone="+998900009915")
_db.add_all([ORD_A, ORD_T, ORD_O, ORD_W, ORD_B, EMP, MAT, SUP, SUP2, SUP_B, USTA, USTA_B])
_db.commit()
OA, OT, OO, OW, OB = ORD_A.id, ORD_T.id, ORD_O.id, ORD_W.id, ORD_B.id
E_ID, M_ID, S_ID, S2_ID, SB_ID = EMP.id, MAT.id, SUP.id, SUP2.id, SUP_B.id
U_ID, UB_ID, PRJ_ID = USTA.id, USTA_B.id, PRJ.id
_db.close()


def login(user):
    c = TestClient(main.app, base_url="https://testserver",
                   raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": "Parol123!"},
               follow_redirects=False)
    assert r.status_code == 302, f"{user} login bo'lmadi: {r.status_code}"
    return c


class _R599:
    status_code = 599

    def __init__(self, e):
        self.text = f"ISTISNO: {type(e).__name__}: {e}"

    def json(self):
        return {}


def req(client, method, url, **kw):
    """Server istisnosi skriptni qulatmasin (asl kodga qarshi mutatsiya)."""
    try:
        r = getattr(client, method)(url, **kw)
    except Exception as e:          # pragma: no cover — himoya qatlami
        r = _R599(e)
    KODLAR.append((r.status_code, method, url))
    return r


def xom(client, method, url, raw):
    return req(client, method, url, content=raw,
               headers={"Content-Type": "application/json"})


def detail(r):
    try:
        return r.json().get("detail")
    except Exception:
        return None


def matn(r):
    return getattr(r, "text", "") or ""


C = login("PQ_admin")
CB = login("PQ_admin_b")

# Tahrir uchun xarid — API orqali (maydonlari haqiqiy oqimdagidek)
req(C, "post", f"/api/inventory/{M_ID}/purchase",
    json={"quantity": 5, "price_per_unit": 1000, "supplier_id": S_ID})
_d = SessionLocal()
P_ID = _d.query(InventoryPurchase).order_by(InventoryPurchase.id.desc()).first().id
_d.close()

# IZOLYATSIYA: har prob oldidan fikstura bazasi tiklanadi (faqat SQLite;
# PostgreSQL rejimida har tekshiruv o'z oldingi holatiga nisbatan).
if not PG_REJIM:
    engine.dispose()
    shutil.copy(_DB, _SNAP)


def tikla():
    if PG_REJIM:
        return
    engine.dispose()
    shutil.copy(_SNAP, _DB)


def holat():
    """Tekshiriladigan to'liq holat — 17f tegadigan hamma jadvallar."""
    d = SessionLocal()
    try:
        def q(model, *ustunlar):
            return [tuple(str(getattr(x, u)) for u in ustunlar)
                    for x in d.query(model).order_by(model.id)]
        return {
            "et": q(ExpenseTransaction, "id", "category", "amount", "production_type", "source"),
            "or": q(Order, "id", "agreed_amount", "discount_percent", "payment_status",
                    "is_archived", "notes"),
            "sp": q(SupplierPayment, "id", "supplier_id", "amount"),
            "ea": q(EmployeeAdvance, "id", "employee_id", "amount"),
            "ro": q(RecurringObligation, "id", "category", "monthly_target"),
            "ip": q(InventoryPurchase, "id", "quantity", "price_per_unit", "total_amount"),
            "inv": q(Inventory, "id", "stock_quantity", "price_per_unit"),
            "ir": q(InventoryReceipt, "id"),
            "te": q(TransportExpense, "id", "amount", "materials_note", "production_type",
                    "company_id"),
            "pay": q(Payment, "id", "order_id", "amount", "payment_type", "payment_method",
                     "received_by", "notes"),
            "prj": q(Project, "id", "total_paid"),
            "gp": q(GiftPeriod, "id", "is_active"),
            "gt": q(GiftPeriodTier, "id", "period_id", "gift_name", "threshold_amount"),
            "gpp": q(GiftPeriodParticipant, "id", "period_id", "master_id"),
        }
    finally:
        d.close()


def oxirgi(model, **flt):
    d = SessionLocal()
    try:
        q = d.query(model)
        for k, v in flt.items():
            q = q.filter(getattr(model, k) == v)
        return q.order_by(model.id.desc()).first()
    finally:
        d.close()


def soni(model):
    d = SessionLocal()
    try:
        return d.query(model).count()
    finally:
        d.close()


def sovga_yop():
    d = SessionLocal()
    try:
        for gp in d.query(GiftPeriod).filter(GiftPeriod.is_active == True).all():  # noqa: E712
            gp.is_active = False
        d.commit()
    finally:
        d.close()


SAHIFALAR = ["/api/transport-expenses", "/api/payments", "/api/projects",
             "/api/orders", f"/api/orders/{OT}", "/api/finance/history",
             "/api/finance/transactions", "/api/finance/report?year=2026&month=9",
             "/api/gift-period", "/api/inventory", "/finance", "/debts", "/orders",
             "/kpi"]


def sahifalar_yiqilgan(c, royxat=None):
    yomon = []
    for u in (SAHIFALAR if royxat is None else royxat):
        r = req(c, "get", u)
        if r.status_code != 200:
            yomon.append((u, r.status_code))
    return yomon


# ══════════════════════════════════════════════════════════════
# A. Tiyindan kichik musbat summa — 13 yo'l
# ══════════════════════════════════════════════════════════════
def _tier_tayyor():
    """Faol davr + bitta bosqich (tier tahriri uchun); bosqich id si."""
    sovga_yop()
    req(C, "post", "/api/gift-period/open",
        json={"tiers": [{"gift_name": "PQ tayyor", "threshold_amount": 100}], "master_ids": []})
    t = oxirgi(GiftPeriodTier)
    return t.id if t else 0


def _qiymat(model, ustun, **flt):
    o = oxirgi(model, **flt)
    return getattr(o, ustun) if o is not None else None


YOLLAR = [
    ("xarajat POST amount", None,
     lambda v, i: xom(C, "post", "/api/finance/transactions",
                      json.dumps({"category": "boshqa", "amount": v})),
     lambda: _qiymat(ExpenseTransaction, "amount")),
    ("kelishilgan summa PUT", None,
     lambda v, i: xom(C, "put", f"/api/orders/{OA}/agreed-amount", json.dumps({"agreed_amount": v})),
     lambda: _qiymat(Order, "agreed_amount", id=OA)),
    ("ta'minotchiga to'lov amount", None,
     lambda v, i: xom(C, "post", f"/api/suppliers/{S_ID}/payment",
                      json.dumps({"amount": v, "confirm_overpay": True})),
     lambda: _qiymat(SupplierPayment, "amount")),
    ("hodim avansi ?amount=", None,
     lambda v, i: req(C, "post", f"/api/employees/{E_ID}/advance", params={"amount": repr(v)}),
     lambda: _qiymat(EmployeeAdvance, "amount")),
    ("oylik qarzini yopish ?amount=", None,
     lambda v, i: req(C, "post", f"/api/obligations/employee/{E_ID}/close",
                      params={"year": "2026", "month": "9", "amount": repr(v)}),
     lambda: _qiymat(EmployeeAdvance, "amount")),
    ("doimiy majburiyat ?monthly_target=", None,
     lambda v, i: req(C, "post", "/api/obligations/recurring",
                      params={"category": f"pqtiyin{i}", "label": f"PQ tiyin {i}",
                              "monthly_target": repr(v)}),
     lambda: _qiymat(RecurringObligation, "monthly_target")),
    ("xarid POST price_per_unit", None,
     lambda v, i: xom(C, "post", f"/api/inventory/{M_ID}/purchase",
                      json.dumps({"quantity": 5, "price_per_unit": v, "supplier_id": S_ID})),
     lambda: _qiymat(InventoryPurchase, "price_per_unit")),
    ("kirim hujjati qator price_per_unit", None,
     lambda v, i: xom(C, "post", "/api/inventory/receipt",
                      json.dumps({"supplier_id": S_ID, "items": [
                          {"inventory_id": M_ID, "quantity": 5, "price_per_unit": v}]})),
     lambda: _qiymat(InventoryPurchase, "price_per_unit")),
    ("xarid TAHRIR price_per_unit", None,
     lambda v, i: xom(C, "put", f"/api/inventory/purchases/{P_ID}", json.dumps({"price_per_unit": v})),
     lambda: _qiymat(InventoryPurchase, "price_per_unit", id=P_ID)),
    ("transport POST amount", None,
     lambda v, i: xom(C, "post", "/api/transport-expenses", json.dumps({"amount": v})),
     lambda: _qiymat(TransportExpense, "amount")),
    ("mijoz to'lovi POST amount", None,
     lambda v, i: xom(C, "post", "/api/payments", json.dumps({"order_id": OT, "amount": v})),
     lambda: _qiymat(Payment, "amount")),
    ("sovg'a davri ochish threshold", sovga_yop,
     lambda v, i: xom(C, "post", "/api/gift-period/open",
                      json.dumps({"tiers": [{"gift_name": "PQ", "threshold_amount": v}],
                                  "master_ids": []})),
     lambda: _qiymat(GiftPeriodTier, "threshold_amount")),
    ("sovg'a bosqichi TAHRIR threshold", "tier",
     None,
     None),
]


def a_bolimi():
    section("A. 1 tiyindan kichik musbat summa — 400; 0.005 → 0.01; 0.02 → 0.02")
    i = 0
    for nom, tayyor, yubor, oqi in YOLLAR:
        for v, yaxshi in ((0.001, False), (0.004, False), (0.005, True), (0.02, True)):
            i += 1
            tikla()
            tier_id = None
            if tayyor == "tier":
                tier_id = _tier_tayyor()
            elif tayyor is not None:
                tayyor()
            h0 = holat()
            if tayyor == "tier":
                r = xom(C, "put", f"/api/gift-period/tier/{tier_id}",
                        json.dumps({"gift_name": "PQ tahrir", "threshold_amount": v}))
                saqlangan = _qiymat(GiftPeriodTier, "threshold_amount", id=tier_id)
            else:
                r = yubor(v, i)
                saqlangan = oqi()
            if not yaxshi:
                check(f"A {nom} {v} → 400 (sabab '0.01'), holat o'zgarmagan",
                      r.status_code == 400 and "0.01" in matn(r) and holat() == h0,
                      f"{r.status_code} {matn(r)[:160]}")
            else:
                check(f"A {nom} {v} → 200, saqlangan {0.01 if v < 0.01 else v:.2f}",
                      r.status_code == 200 and tiyin_ok(saqlangan, 0.01 if v < 0.01 else v),
                      f"{r.status_code} saqlangan={saqlangan!r} {matn(r)[:120]}")


# ══════════════════════════════════════════════════════════════
# B. Xarid tahriri — sig'im
# ══════════════════════════════════════════════════════════════
def xarid(pid):
    o = oxirgi(InventoryPurchase, id=pid)
    return SimpleNamespace(qty=float(o.quantity), narx=o.price_per_unit, jami=o.total_amount)


def zaxira():
    o = oxirgi(Inventory, id=M_ID)
    return float(o.stock_quantity)


def b_asl():
    """Tahrir qilinadigan xarid ASL holatda (5 × 1000). SQLite — fikstura
    tiklanadi; PostgreSQL rejimida (tiklash yo'q) — oldingi bo'limlar
    o'zgartirgan xarid API orqali asl qiymatga qaytariladi."""
    tikla()
    if PG_REJIM:
        xom(C, "put", f"/api/inventory/purchases/{P_ID}",
            json.dumps({"quantity": 5, "price_per_unit": 1000}))


def b_bolimi():
    section("B. Xarid TAHRIRI — narx va jami summa sig'imi")
    for nom, tana, sabab in [
            ("narx 1e10", {"price_per_unit": 1e10}, "'price_per_unit' juda katta"),
            ("narx 9999999999.991", {"price_per_unit": 9999999999.991}, "'price_per_unit' juda katta"),
            # Miqdor 1 dan kichik: jami (0.5 × 1.5e10 = 7.5e9) sig'imga sig'adi, narx
            # esa Numeric(12,2) ga sig'maydi (PostgreSQL da 500) — faqat narx chegarasi.
            ("miqdor 0.5 × narx 1.5e10", {"quantity": 0.5, "price_per_unit": 1.5e10},
             "'price_per_unit' juda katta"),
            ("miqdor 1e6 × narx 1e5", {"quantity": 1e6, "price_per_unit": 1e5}, "×"),
            ("faqat narx 2e9 (× joriy miqdor 5)", {"price_per_unit": 2e9}, "×"),
            ("faqat miqdor 1e7 (× joriy narx 1000)", {"quantity": 1e7}, "×")]:
        b_asl()
        h0 = holat()
        r = xom(C, "put", f"/api/inventory/purchases/{P_ID}", json.dumps(tana))
        check(f"B {nom} → 400 ('{sabab}'), xarid va ombor o'zgarmagan",
              r.status_code == 400 and sabab in matn(r) and holat() == h0,
              f"{r.status_code} {matn(r)[:160]}")
    b_asl()
    z0 = zaxira()
    r = xom(C, "put", f"/api/inventory/purchases/{P_ID}",
            json.dumps({"quantity": 5, "price_per_unit": 1999999999.99}))
    x = xarid(P_ID)
    check("B chegara 5 × 1 999 999 999.99 = 9 999 999 999.95 → 200, aniq jami, ombor o'zgarmagan",
          r.status_code == 200 and tiyin_ok(x.jami, 9999999999.95) and zaxira() == z0,
          f"{r.status_code} jami={x.jami!r} {matn(r)[:120]}")
    b_asl()
    r = xom(C, "put", f"/api/inventory/purchases/{P_ID}", json.dumps({"price_per_unit": 1234}))
    x = xarid(P_ID)
    check("B narx 1234 → 200, jami 6170",
          r.status_code == 200 and tiyin_ok(x.narx, 1234) and tiyin_ok(x.jami, 6170),
          f"{r.status_code} {x}")
    b_asl()
    z0 = zaxira()
    r = xom(C, "put", f"/api/inventory/purchases/{P_ID}", json.dumps({"quantity": 7}))
    x = xarid(P_ID)
    check("B miqdor 7 → 200, jami 7000, ombor +2",
          r.status_code == 200 and yaqin(x.qty, 7) and tiyin_ok(x.jami, 7000)
          and yaqin(zaxira(), z0 + 2),
          f"{r.status_code} {x} zaxira {z0}->{zaxira()}")


# ══════════════════════════════════════════════════════════════
# C. Kirish transporti
# ══════════════════════════════════════════════════════════════
def c_bolimi():
    section("C. POST /api/transport-expenses — yomon 400, to'g'ri 200")
    for nom, raw in [
            ("amount Infinity", '{"amount": Infinity}'),
            ("amount -Infinity", '{"amount": -Infinity}'),
            ("amount NaN", '{"amount": NaN}'),
            ("amount 1e20", '{"amount": 1e20}'),
            ("amount 9999999999.991", '{"amount": 9999999999.991}'),
            ("amount true", '{"amount": true}'),
            ("amount \"5\"", '{"amount": "5"}'),
            ("amount 0", '{"amount": 0}'),
            ("amount -5", '{"amount": -5}'),
            ("amount yo'q", '{"notes": "PQ"}'),
            ("amount null", '{"amount": null}'),
            ("production_type xyz", '{"amount": 5, "production_type": "xyz"}'),
            ("production_type 25 belgi", '{"amount": 5, "production_type": "%s"}' % ("p" * 25)),
            ("production_type son", '{"amount": 5, "production_type": 5}'),
            ("materials_note 256 belgi", '{"amount": 5, "materials_note": "%s"}' % ("m" * 256)),
            ("materials_note son", '{"amount": 5, "materials_note": 5}'),
            ("notes 10001 belgi", '{"amount": 5, "notes": "%s"}' % ("n" * 10001)),
            ("noma'lum kalit company_id", '{"amount": 5, "company_id": 2}'),
            ("noma'lum kalit expense_date", '{"amount": 5, "expense_date": "2026-09-01"}')]:
        tikla()
        h0 = holat()
        r = xom(C, "post", "/api/transport-expenses", raw)
        check(f"C {nom} → 400, `detail` matn, holat o'zgarmagan",
              r.status_code == 400 and isinstance(detail(r), str) and holat() == h0,
              f"{r.status_code} {matn(r)[:160]}")

    tikla()
    r = xom(C, "post", "/api/transport-expenses", '{"amount": 5000}')
    t = oxirgi(TransportExpense)
    check("C {amount: 5000} → 200: summa, korxona 1, yaratgan, bo'sh maydonlar",
          r.status_code == 200 and t is not None and tiyin_ok(t.amount, 5000)
          and t.company_id == 1 and t.created_by == "PQ Admin" and t.materials_note is None
          and t.production_type is None and t.notes is None
          and yaqin((r.json() or {}).get("amount"), 5000),
          f"{r.status_code} {matn(r)[:120]}")
    r = xom(C, "post", "/api/transport-expenses", json.dumps(
        {"amount": 12345.5, "materials_note": "Akril, Kroshka", "notes": "PQ izoh",
         "production_type": "penoplast"}))
    t = oxirgi(TransportExpense)
    check("C to'liq tana → 200, AYNAN qiymatlar",
          r.status_code == 200 and tiyin_ok(t.amount, 12345.5) and t.materials_note == "Akril, Kroshka"
          and t.notes == "PQ izoh" and t.production_type == "penoplast",
          f"{r.status_code} {matn(r)[:120]}")
    r = xom(C, "post", "/api/transport-expenses", json.dumps(
        {"amount": 7000, "materials_note": "m" * 255, "notes": "n" * 10000}))
    t = oxirgi(TransportExpense)
    check("C chegara: materials_note 255, notes 10000 belgi → 200",
          r.status_code == 200 and len(t.materials_note or "") == 255 and len(t.notes or "") == 10000,
          f"{r.status_code} {matn(r)[:120]}")
    r = xom(C, "post", "/api/transport-expenses", '{"amount": 8000, "production_type": ""}')
    t = oxirgi(TransportExpense)
    check("C production_type \"\" → 200, bo'sh (null)",
          r.status_code == 200 and t.production_type is None and tiyin_ok(t.amount, 8000),
          f"{r.status_code} {matn(r)[:120]}")
    r = xom(C, "post", "/api/transport-expenses", '{"amount": 9999999999.99}')
    t = oxirgi(TransportExpense)
    check("C chegara summa 9 999 999 999.99 → 200, aniq",
          r.status_code == 200 and tiyin_ok(t.amount, 9999999999.99), f"{r.status_code} {matn(r)[:120]}")
    r = xom(CB, "post", "/api/transport-expenses", '{"amount": 4321}')
    t = oxirgi(TransportExpense)
    check("C 2-korxona admini → 200, yozuv 2-korxonaga",
          r.status_code == 200 and t.company_id == 2 and tiyin_ok(t.amount, 4321),
          f"{r.status_code} {matn(r)[:120]}")
    r = req(C, "get", "/api/transport-expenses")
    try:
        _ids = {x.get("amount") for x in r.json()}
    except Exception:
        _ids = set()
    check("C GET 1-korxona ro'yxatida 2-korxona yozuvi YO'Q",
          r.status_code == 200 and 4321.0 not in _ids, f"{r.status_code} {_ids}")


# ══════════════════════════════════════════════════════════════
# D. Mijoz to'lovi
# ══════════════════════════════════════════════════════════════
def tolov_holati():
    h = holat()
    return {"pay": h["pay"], "or": h["or"], "prj": h["prj"]}


def d_bolimi():
    section("D. POST /api/payments — yomon 400; UI tanalari 200; 404/409 saqlangan")
    tikla()
    for nom, raw in [
            ("amount Infinity", '{"order_id": %d, "amount": Infinity}' % OT),
            ("amount -Infinity", '{"order_id": %d, "amount": -Infinity}' % OT),
            ("amount NaN", '{"order_id": %d, "amount": NaN}' % OT),
            ("amount 1e20", '{"order_id": %d, "amount": 1e20}' % OT),
            ("amount 9999999999.991", '{"order_id": %d, "amount": 9999999999.991}' % OT),
            ("amount true", '{"order_id": %d, "amount": true}' % OT),
            ("amount \"5\"", '{"order_id": %d, "amount": "5"}' % OT),
            ("amount 0", '{"order_id": %d, "amount": 0}' % OT),
            ("amount -5", '{"order_id": %d, "amount": -5}' % OT),
            ("amount yo'q", '{"order_id": %d}' % OT),
            ("amount null", '{"order_id": %d, "amount": null}' % OT),
            ("order_id yo'q", '{"amount": 1001}'),
            ("order_id true", '{"order_id": true, "amount": 1002}'),
            ("order_id \"1\"", '{"order_id": "%d", "amount": 1003}' % OT),
            ("order_id 1.0 (kasr)", '{"order_id": %d.0, "amount": 1004}' % OT),
            ("order_id 0", '{"order_id": 0, "amount": 1005}'),
            ("order_id -1", '{"order_id": -1, "amount": 1006}'),
            ("order_id 2^31", '{"order_id": 2147483648, "amount": 1007}'),
            ("payment_type xyz", '{"order_id": %d, "amount": 1008, "payment_type": "xyz"}' % OT),
            ("payment_type son", '{"order_id": %d, "amount": 1009, "payment_type": 5}' % OT),
            ("payment_method cash", '{"order_id": %d, "amount": 1010, "payment_method": "cash"}' % OT),
            ("payment_method karta", '{"order_id": %d, "amount": 1011, "payment_method": "karta"}' % OT),
            ("payment_method 50 belgi",
             '{"order_id": %d, "amount": 1012, "payment_method": "%s"}' % (OT, "x" * 50)),
            ("received_by 101 belgi",
             '{"order_id": %d, "amount": 1013, "received_by": "%s"}' % (OT, "r" * 101)),
            ("received_by son", '{"order_id": %d, "amount": 1014, "received_by": 5}' % OT),
            ("notes 10001 belgi", '{"order_id": %d, "amount": 1015, "notes": "%s"}' % (OT, "n" * 10001)),
            ("confirm_overpay \"true\"",
             '{"order_id": %d, "amount": 1016, "confirm_overpay": "true"}' % OT),
            ("confirm_overpay 1", '{"order_id": %d, "amount": 1017, "confirm_overpay": 1}' % OT),
            ("noma'lum kalit company_id", '{"order_id": %d, "amount": 1018, "company_id": 2}' % OT),
            ("noma'lum kalit paid_at", '{"order_id": %d, "amount": 1019, "paid_at": "2026-01-01"}' % OT)]:
        h0 = tolov_holati()
        r = xom(C, "post", "/api/payments", raw)
        check(f"D {nom} → 400, `detail` matn, to'lov/buyurtma/loyiha o'zgarmagan",
              r.status_code == 400 and isinstance(detail(r), str) and tolov_holati() == h0,
              f"{r.status_code} {matn(r)[:160]}")

    # ── UI tanalari AYNAN ──
    def songgi_tolov():
        return oxirgi(Payment)

    def tolov_tekshir(nom, url, tana, summa, tur, usul, qabul, izoh):
        n0 = soni(Payment)
        r = xom(C, "post", url, json.dumps(tana))
        p = songgi_tolov()
        try:
            dup = (r.json() or {}).get("duplicate")
        except Exception:
            dup = None
        check(f"D {nom} → 200, AYNAN qiymatlar, bitta yangi yozuv",
              r.status_code == 200 and soni(Payment) == n0 + 1 and p is not None
              and p.order_id == tana["order_id"] and tiyin_ok(p.amount, summa)
              and p.payment_type.value == tur and p.payment_method.value == usul
              and p.received_by == qabul and p.notes == izoh and dup is False,
              f"{r.status_code} {matn(r)[:140]} "
              f"{p and (p.amount, p.payment_type, p.payment_method, p.received_by, p.notes)}")

    tolov_tekshir("orders.html to'lov oynasi (partial, naqd, izohsiz)", "/api/payments",
                  {"order_id": OT, "amount": 150000, "payment_type": "partial",
                   "payment_method": "naqd", "notes": None, "confirm_overpay": False},
                  150000, "partial", "naqd", "PQ Admin", None)
    tolov_tekshir("orders.html to'lov oynasi (final, plastik, izoh, kasr)", "/api/payments",
                  {"order_id": OT, "amount": 160000.5, "payment_type": "final",
                   "payment_method": "plastik", "notes": "PQ izoh", "confirm_overpay": False},
                  160000.5, "final", "plastik", "PQ Admin", "PQ izoh")
    tolov_tekshir("orders.html zaklat (o'tkazma)", "/api/payments",
                  {"order_id": OT, "amount": 170000, "payment_type": "zaklat",
                   "payment_method": "o'tkazma", "notes": "Buyurtma yaratilganda"},
                  170000, "zaklat", "o'tkazma", "PQ Admin", "Buyurtma yaratilganda")
    tolov_tekshir("debts.html qarzni yopish (standart tur/usul)",
                  "/api/payments?write_off_remainder=false",
                  {"order_id": OT, "amount": 180000, "notes": None},
                  180000, "partial", "naqd", "PQ Admin", None)
    tolov_tekshir("debts.html ortiqcha tasdiqlangan (confirm_overpay true)",
                  "/api/payments?write_off_remainder=false",
                  {"order_id": OT, "amount": 185000, "notes": "avans", "confirm_overpay": True},
                  185000, "partial", "naqd", "PQ Admin", "avans")
    tolov_tekshir("received_by berilgan, payment_type \"\" → standart", "/api/payments",
                  {"order_id": OT, "amount": 186000, "payment_type": "", "received_by": "Kassir"},
                  186000, "partial", "naqd", "Kassir", None)

    # Loyiha total_paid = shu loyiha to'lovlari yig'indisi (17c invarianti)
    d = SessionLocal()
    try:
        yig = sum(float(p.amount) for p in d.query(Payment).join(Order, Order.id == Payment.order_id)
                  .filter(Order.project_id == PRJ_ID).all())
        tp = float(d.get(Project, PRJ_ID).total_paid or 0)
    finally:
        d.close()
    check("D loyiha total_paid = to'lovlar yig'indisi", yaqin(tp, yig, 0.011), f"{tp} != {yig}")

    # ── Saqlangan xatti-harakatlar ──
    h0 = tolov_holati()
    r = xom(C, "post", "/api/payments", '{"order_id": 999999, "amount": 1000}')
    check("D mavjud bo'lmagan buyurtma → 404 'Buyurtma topilmadi', o'zgarmagan",
          r.status_code == 404 and detail(r) == "Buyurtma topilmadi" and tolov_holati() == h0,
          f"{r.status_code} {matn(r)[:120]}")
    r = xom(C, "post", "/api/payments", '{"order_id": %d, "amount": 1000}' % OB)
    check("D begona korxona buyurtmasi → 404, o'zgarmagan",
          r.status_code == 404 and tolov_holati() == h0, f"{r.status_code} {matn(r)[:120]}")
    r = xom(CB, "post", "/api/payments", '{"order_id": %d, "amount": 1000}' % OT)
    check("D 2-korxona admini 1-korxona buyurtmasiga → 404, o'zgarmagan",
          r.status_code == 404 and tolov_holati() == h0, f"{r.status_code} {matn(r)[:120]}")
    r = xom(C, "post", "/api/payments", '{"order_id": %d, "amount": 150000}' % OO)
    d409 = detail(r)
    check("D qarzdan ko'p → 409 overpayment_warning (savol matni), o'zgarmagan",
          r.status_code == 409 and isinstance(d409, dict)
          and d409.get("type") == "overpayment_warning" and "davom" in str(d409.get("message"))
          and tolov_holati() == h0, f"{r.status_code} {matn(r)[:160]}")
    r = xom(C, "post", "/api/payments",
            '{"order_id": %d, "amount": 400000, "confirm_overpay": true}' % OO)
    check("D 3 baravardan katta → 400 'juda katta', o'zgarmagan",
          r.status_code == 400 and "juda katta" in matn(r) and tolov_holati() == h0,
          f"{r.status_code} {matn(r)[:160]}")
    r = xom(C, "post", "/api/payments",
            '{"order_id": %d, "amount": 150000, "confirm_overpay": true}' % OO)
    p = oxirgi(Payment)
    check("D tasdiqlangan ortiqcha to'lov → 200, yozildi",
          r.status_code == 200 and p.order_id == OO and tiyin_ok(p.amount, 150000),
          f"{r.status_code} {matn(r)[:160]}")
    tana = {"order_id": OT, "amount": 190000, "payment_type": "partial", "payment_method": "naqd"}
    n0 = soni(Payment)
    r1 = xom(C, "post", "/api/payments", json.dumps(tana))
    r2 = xom(C, "post", "/api/payments", json.dumps(tana))
    try:
        dup2 = (r2.json() or {}).get("duplicate")
    except Exception:
        dup2 = None
    check("D takroriy yuborish (8 s ichida) → ikkinchisi duplicate, faqat 1 yozuv",
          r1.status_code == 200 and r2.status_code == 200 and dup2 is True
          and soni(Payment) == n0 + 1, f"{r1.status_code} {r2.status_code} {matn(r2)[:120]}")
    r = xom(C, "post", "/api/payments?write_off_remainder=true",
            '{"order_id": %d, "amount": 99600}' % OW)
    o = oxirgi(Order, id=OW)
    try:
        wo = (r.json() or {}).get("write_off") or {}
    except Exception:
        wo = {}
    check("D chegirmaga yozish → 200, 400 so'm yozildi, kelishilgan 99 600",
          r.status_code == 200 and wo.get("amount") == 400 and tiyin_ok(o.agreed_amount, 99600),
          f"{r.status_code} {matn(r)[:160]}")


# ══════════════════════════════════════════════════════════════
# E. Sovg'a davri
# ══════════════════════════════════════════════════════════════
def e_bolimi():
    section("E. Sovg'a davri — ochish va bosqich tahriri")
    t1 = '{"gift_name": "X", "threshold_amount": 100}'
    for nom, raw in [
            ("tiers matn", '{"tiers": "abc"}'),
            ("tiers [5]", '{"tiers": [5]}'),
            ("tiers bo'sh ro'yxat", '{"tiers": []}'),
            ("tiers yo'q", '{"master_ids": []}'),
            ("tiers 51 ta", '{"tiers": [%s]}' % ", ".join(
                '{"gift_name": "T%d", "threshold_amount": %d}' % (k, 100 + k) for k in range(51))),
            ("gift_name son", '{"tiers": [{"gift_name": 5, "threshold_amount": 100}]}'),
            ("gift_name bo'sh", '{"tiers": [{"gift_name": "", "threshold_amount": 100}]}'),
            ("gift_name bo'shliq", '{"tiers": [{"gift_name": "   ", "threshold_amount": 100}]}'),
            ("gift_name 101 belgi", '{"tiers": [{"gift_name": "%s", "threshold_amount": 100}]}' % ("g" * 101)),
            ("gift_name yo'q", '{"tiers": [{"threshold_amount": 100}]}'),
            ("threshold yo'q", '{"tiers": [{"gift_name": "X"}]}'),
            ("threshold \"abc\"", '{"tiers": [{"gift_name": "X", "threshold_amount": "abc"}]}'),
            ("threshold \"5000\"", '{"tiers": [{"gift_name": "X", "threshold_amount": "5000"}]}'),
            ("threshold true", '{"tiers": [{"gift_name": "X", "threshold_amount": true}]}'),
            ("threshold Infinity", '{"tiers": [{"gift_name": "X", "threshold_amount": Infinity}]}'),
            ("threshold NaN", '{"tiers": [{"gift_name": "X", "threshold_amount": NaN}]}'),
            ("threshold 1e20", '{"tiers": [{"gift_name": "X", "threshold_amount": 1e20}]}'),
            ("threshold 0", '{"tiers": [{"gift_name": "X", "threshold_amount": 0}]}'),
            ("threshold -5", '{"tiers": [{"gift_name": "X", "threshold_amount": -5}]}'),
            ("bosqichda noma'lum kalit",
             '{"tiers": [{"gift_name": "X", "threshold_amount": 100, "sort_order": 3}]}'),
            ("master_ids matn", '{"tiers": [%s], "master_ids": "abc"}' % t1),
            ("master_ids [true]", '{"tiers": [%s], "master_ids": [true]}' % t1),
            ("master_ids [\"1\"]", '{"tiers": [%s], "master_ids": ["1"]}' % t1),
            ("master_ids [1.5]", '{"tiers": [%s], "master_ids": [1.5]}' % t1),
            ("master_ids [0]", '{"tiers": [%s], "master_ids": [0]}' % t1),
            ("master_ids son", '{"tiers": [%s], "master_ids": 5}' % t1),
            ("master_ids 1001 ta", '{"tiers": [%s], "master_ids": [%s]}' % (
                t1, ", ".join(str(k + 1) for k in range(1001))))]:
        tikla()
        sovga_yop()
        h0 = holat()
        r = xom(C, "post", "/api/gift-period/open", raw)
        check(f"E ochish {nom} → 400, davr/bosqich/ishtirokchi yaratilmagan",
              r.status_code == 400 and holat() == h0, f"{r.status_code} {matn(r)[:160]}")

    # ── kpi.html tanalari ──
    tikla()
    sovga_yop()
    r = xom(C, "post", "/api/gift-period/open", json.dumps(
        {"tiers": [{"gift_name": "Televizor", "threshold_amount": 5000000},
                   {"gift_name": "Telefon", "threshold_amount": 2000000}], "master_ids": []}))
    gp = oxirgi(GiftPeriod)
    d = SessionLocal()
    try:
        tl = [(t.gift_name, float(t.threshold_amount), t.sort_order)
              for t in d.query(GiftPeriodTier).filter(GiftPeriodTier.period_id == (gp.id if gp else 0))
              .order_by(GiftPeriodTier.sort_order)]
        np_ = d.query(GiftPeriodParticipant).filter(
            GiftPeriodParticipant.period_id == (gp.id if gp else 0)).count()
    finally:
        d.close()
    check("E kpi.html (barcha ustalar) → 200, faol davr, bosqichlar summa bo'yicha, ishtirokchi yozuvi yo'q",
          r.status_code == 200 and gp is not None and gp.is_active and gp.company_id == 1
          and tl == [("Telefon", 2000000.0, 0), ("Televizor", 5000000.0, 1)] and np_ == 0,
          f"{r.status_code} {matn(r)[:120]} {tl} {np_}")

    tikla()
    sovga_yop()
    r = xom(C, "post", "/api/gift-period/open", json.dumps(
        {"tiers": [{"gift_name": "  Muzlatgich ", "threshold_amount": 3000000}],
         "master_ids": [U_ID, U_ID, UB_ID]}))
    gp = oxirgi(GiftPeriod)
    d = SessionLocal()
    try:
        tl = [(t.gift_name, float(t.threshold_amount))
              for t in d.query(GiftPeriodTier).filter(GiftPeriodTier.period_id == (gp.id if gp else 0))]
        ish = sorted(p.master_id for p in d.query(GiftPeriodParticipant)
                     .filter(GiftPeriodParticipant.period_id == (gp.id if gp else 0)))
    finally:
        d.close()
    check("E kpi.html (tanlangan ustalar, takror + begona) → 200, nom tozalangan, faqat o'z ustasi 1 marta",
          r.status_code == 200 and tl == [("Muzlatgich", 3000000.0)] and ish == [U_ID],
          f"{r.status_code} {matn(r)[:120]} {tl} {ish}")

    # ── Bosqich tahriri (shu faol davrda) ──
    tier = oxirgi(GiftPeriodTier)
    T_ID = tier.id if tier else 0
    for nom, raw in [
            ("threshold \"abc\"", '{"gift_name": "Y", "threshold_amount": "abc"}'),
            ("threshold true", '{"gift_name": "Y", "threshold_amount": true}'),
            ("threshold Infinity", '{"gift_name": "Y", "threshold_amount": Infinity}'),
            ("threshold 1e20", '{"gift_name": "Y", "threshold_amount": 1e20}'),
            ("threshold 0", '{"gift_name": "Y", "threshold_amount": 0}'),
            ("threshold -5", '{"gift_name": "Y", "threshold_amount": -5}'),
            ("threshold 0.004", '{"gift_name": "Y", "threshold_amount": 0.004}'),
            ("gift_name 101 belgi", '{"gift_name": "%s", "threshold_amount": 100}' % ("g" * 101)),
            ("gift_name son", '{"gift_name": 5, "threshold_amount": 100}'),
            ("gift_name bo'sh", '{"gift_name": "", "threshold_amount": 100}')]:
        h0 = holat()
        r = xom(C, "put", f"/api/gift-period/tier/{T_ID}", raw)
        check(f"E bosqich tahriri {nom} → 400, o'zgarmagan",
              r.status_code == 400 and holat() == h0, f"{r.status_code} {matn(r)[:140]}")
    h0 = holat()
    r = xom(CB, "put", f"/api/gift-period/tier/{T_ID}",
            '{"gift_name": "Begona", "threshold_amount": 100}')
    check("E 2-korxona admini 1-korxona bosqichini → 400, o'zgarmagan",
          r.status_code == 400 and holat() == h0, f"{r.status_code} {matn(r)[:140]}")
    r = xom(C, "put", f"/api/gift-period/tier/{T_ID}",
            json.dumps({"gift_name": "Muzlatgich XL", "threshold_amount": 3500000}))
    t = oxirgi(GiftPeriodTier, id=T_ID)
    check("E kpi.html bosqich tahriri → 200, AYNAN qiymatlar",
          r.status_code == 200 and t.gift_name == "Muzlatgich XL" and tiyin_ok(t.threshold_amount, 3500000),
          f"{r.status_code} {matn(r)[:140]}")


# ══════════════════════════════════════════════════════════════
# X. Hosila yozuvlar — xarid va kirim hujjati
# ══════════════════════════════════════════════════════════════
def x_bolimi():
    section("X. Xarid / kirim hujjati — 0 yoki kamida 1 tiyin (yarim saqlanish yo'q)")
    xurl = f"/api/inventory/{M_ID}/purchase"
    for nom, tana, kalit in [
            ("xarid paid_now 0.001", {"quantity": 5, "price_per_unit": 1100, "supplier_id": S_ID,
                                      "paid_now": 0.001}, "paid_now"),
            ("xarid paid_now 0.004", {"quantity": 5, "price_per_unit": 1101, "supplier_id": S_ID,
                                      "paid_now": 0.004}, "paid_now"),
            ("xarid transport self 0.001", {"quantity": 5, "price_per_unit": 1102,
                                            "transport_payer": "self", "transport_cost": 0.001},
             "transport_cost"),
            ("xarid transport supplier 0.004", {"quantity": 5, "price_per_unit": 1103,
                                                "transport_payer": "supplier", "transport_cost": 0.004},
             "transport_cost")]:
        tikla()
        h0 = holat()
        r = xom(C, "post", xurl, json.dumps(tana))
        check(f"X {nom} → 400 ('{kalit}' 0 yoki 0.01), xarid/ombor/to'lov/transport o'zgarmagan",
              r.status_code == 400 and kalit in matn(r) and "0.01" in matn(r) and holat() == h0,
              f"{r.status_code} {matn(r)[:160]}")
    tikla()
    n0, s0 = soni(InventoryPurchase), soni(SupplierPayment)
    # SUP2: A bo'limidagi S_ID ga 0.01 lik to'lov 8 s ichida bo'lsa, mavjud
    # takror-yuborish himoyasi (ta'minotchi + summa + 8 s) yangisini yaratmaydi.
    r = xom(C, "post", xurl, json.dumps({"quantity": 5, "price_per_unit": 1104, "supplier_id": S2_ID,
                                         "paid_now": 0.005}))
    sp = oxirgi(SupplierPayment)
    check("X xarid paid_now 0.005 → 200, xarid + 0.01 so'mlik to'lov",
          r.status_code == 200 and soni(InventoryPurchase) == n0 + 1 and soni(SupplierPayment) == s0 + 1
          and tiyin_ok(sp.amount, 0.01), f"{r.status_code} {matn(r)[:120]} {sp and sp.amount}")
    tikla()
    n0, s0 = soni(InventoryPurchase), soni(SupplierPayment)
    r = xom(C, "post", xurl, json.dumps({"quantity": 5, "price_per_unit": 1105, "supplier_id": S_ID,
                                         "paid_now": 0}))
    check("X xarid paid_now 0 → 200, to'lov yozilmagan",
          r.status_code == 200 and soni(InventoryPurchase) == n0 + 1 and soni(SupplierPayment) == s0,
          f"{r.status_code} {matn(r)[:120]}")
    tikla()
    t0 = soni(TransportExpense)
    r = xom(C, "post", xurl, json.dumps({"quantity": 5, "price_per_unit": 1106,
                                         "transport_payer": "self", "transport_cost": 5000}))
    t = oxirgi(TransportExpense)
    check("X xarid 'o'z hisobimdan' transport 5000 → 200, transport yozuvi (material nomi, korxona 1)",
          r.status_code == 200 and soni(TransportExpense) == t0 + 1 and tiyin_ok(t.amount, 5000)
          and t.materials_note == "PQ_SEMENT" and t.company_id == 1,
          f"{r.status_code} {matn(r)[:120]}")

    for kalit in ("transport_cost", "tushirish_cost", "yuklash_cost", "boshqa_cost", "paid_now"):
        tikla()
        h0 = holat()
        r = xom(C, "post", "/api/inventory/receipt", json.dumps(
            {"supplier_id": S_ID, "items": [{"inventory_id": M_ID, "quantity": 2, "price_per_unit": 2000}],
             kalit: 0.001}))
        check(f"X kirim {kalit} 0.001 → 400, hujjat/xarid/xarajat/to'lov o'zgarmagan",
              r.status_code == 400 and kalit in matn(r) and "0.01" in matn(r) and holat() == h0,
              f"{r.status_code} {matn(r)[:160]}")
    tikla()
    r = xom(C, "post", "/api/inventory/receipt", json.dumps(
        {"supplier_id": S_ID, "items": [{"inventory_id": M_ID, "quantity": 2, "price_per_unit": 2001}],
         "transport_cost": 0.005, "paid_now": 0.005}))
    et = oxirgi(ExpenseTransaction, category="transport_kirim")
    sp = oxirgi(SupplierPayment)
    check("X kirim transport 0.005 va to'lov 0.005 → 200, ikkalasi 0.01 (0.00 EMAS)",
          r.status_code == 200 and et is not None and tiyin_ok(et.amount, 0.01)
          and sp is not None and tiyin_ok(sp.amount, 0.01),
          f"{r.status_code} {matn(r)[:120]} {et and et.amount} {sp and sp.amount}")
    tikla()
    e0, s0 = soni(ExpenseTransaction), soni(SupplierPayment)
    r = xom(C, "post", "/api/inventory/receipt", json.dumps(
        {"supplier_id": S_ID, "items": [{"inventory_id": M_ID, "quantity": 2, "price_per_unit": 2002}],
         "transport_cost": 0, "tushirish_cost": 0, "yuklash_cost": 0, "boshqa_cost": 0, "paid_now": 0}))
    check("X kirim barcha qo'shimcha 0 → 200, hosila xarajat/to'lov yo'q",
          r.status_code == 200 and soni(ExpenseTransaction) == e0 and soni(SupplierPayment) == s0,
          f"{r.status_code} {matn(r)[:120]}")


# ══════════════════════════════════════════════════════════════
# F. Ildiz (crud) — bazaga tegmasdan rad
# ══════════════════════════════════════════════════════════════
def urin(fn):
    """(natija, istisno_nomi) — asl kodga qarshi qulamaslik uchun."""
    try:
        return fn(), None
    except Exception as e:
        return None, type(e).__name__


def f_bolimi():
    section("F. Ildiz (crud) — ValueError / success False, hech narsa yozilmaydi")
    tikla()
    ns = lambda **kw: SimpleNamespace(**{**{"materials_note": None, "notes": None,  # noqa: E731
                                            "production_type": None}, **kw})
    for nom, arg in [("lug'at amount 0.001", {"amount": 0.001}),
                     ("obyekt amount Infinity", ns(amount=float("inf"))),
                     ("obyekt amount true", ns(amount=True)),
                     ("lug'at production_type xyz", {"amount": 5, "production_type": "xyz"}),
                     ("lug'at materials_note 256", {"amount": 5, "materials_note": "m" * 256})]:
        n0 = soni(TransportExpense)
        d = SessionLocal()
        try:
            _, ist = urin(lambda: crud.create_transport_expense(d, arg, created_by="F", company_id=1))
            d.rollback()
        finally:
            d.close()
        check(f"F create_transport_expense {nom} → ValueError, yozilmagan",
              ist == "ValueError" and soni(TransportExpense) == n0, ist)
    d = SessionLocal()
    try:
        t, ist = urin(lambda: crud.create_transport_expense(
            d, schemas.TransportExpenseCreate(amount=5000, materials_note="Ichki"),
            created_by="F", company_id=1))
        t_ok = t is not None and yaqin(t.amount, 5000) and t.materials_note == "Ichki" and t.company_id == 1
    finally:
        d.close()
    check("F create_transport_expense ichki chaqiruv (sxema obyekti) → yoziladi", t_ok, ist)

    tp = lambda **kw: SimpleNamespace(**{**{"order_id": OT, "payment_type": "partial",  # noqa: E731
                                            "payment_method": "naqd", "received_by": None,
                                            "notes": None, "confirm_overpay": False}, **kw})
    for nom, arg in [("amount 0.001", tp(amount=0.001)),
                     ("amount true", tp(amount=True)),
                     ("order_id true", tp(order_id=True, amount=1234)),
                     ("payment_type xyz", tp(amount=1235, payment_type="xyz")),
                     ("model_construct amount 0.004",
                      schemas.PaymentCreate.model_construct(
                          order_id=OT, amount=0.004, payment_type="partial", payment_method="naqd",
                          received_by=None, notes=None, confirm_overpay=False))]:
        h0 = tolov_holati()
        d = SessionLocal()
        try:
            _, ist = urin(lambda: crud.create_payment(d, arg, company_id=1))
            d.rollback()
        finally:
            d.close()
        check(f"F create_payment {nom} → ValueError, to'lov/buyurtma o'zgarmagan",
              ist == "ValueError" and tolov_holati() == h0, ist)

    for nom, tiers, ustalar in [
            ("threshold 0.001", [{"gift_name": "X", "threshold_amount": 0.001}], None),
            ("threshold \"5000\"", [{"gift_name": "X", "threshold_amount": "5000"}], None),
            ("tiers matn", "abc", None),
            ("master_ids [true]", [{"gift_name": "X", "threshold_amount": 100}], [True])]:
        sovga_yop()
        h0 = holat()
        d = SessionLocal()
        try:
            res, ist = urin(lambda: crud.open_gift_period(d, tiers, master_ids=ustalar, company_id=1))
            d.rollback()
        finally:
            d.close()
        check(f"F open_gift_period {nom} → success False, yozilmagan",
              isinstance(res, dict) and res.get("success") is False and holat() == h0, (res, ist))

    tier_id = _tier_tayyor()
    for nom, nomi, summa in [("threshold 0.004", "Y", 0.004), ("nom 101", "g" * 101, 100)]:
        h0 = holat()
        d = SessionLocal()
        try:
            res, ist = urin(lambda: crud.update_gift_period_tier(d, tier_id, nomi, summa, company_id=1))
            d.rollback()
        finally:
            d.close()
        check(f"F update_gift_period_tier {nom} → success False, o'zgarmagan",
              isinstance(res, dict) and res.get("success") is False and holat() == h0, (res, ist))

    cv = getattr(crud, "_clean_val", None)
    xato = []
    for model, kalit in [("Purchase", "paid_now"), ("Purchase", "transport_cost"),
                         ("Receipt", "paid_now"), ("Receipt", "transport_cost"),
                         ("Receipt", "tushirish_cost"), ("Receipt", "yuklash_cost"),
                         ("Receipt", "boshqa_cost")]:
        asos = ({"quantity": 5, "price_per_unit": 1000} if model == "Purchase" else
                {"items": [{"inventory_id": M_ID, "quantity": 1, "price_per_unit": 10}]})
        _, ist = urin(lambda: cv(model, {**asos, kalit: 0.004}))
        r0, ist0 = urin(lambda: cv(model, {**asos, kalit: 0}))
        r5, ist5 = urin(lambda: cv(model, {**asos, kalit: 0.005}))
        if ist != "ValueError" or ist0 is not None or ist5 is not None:
            xato.append((model, kalit, ist, ist0, ist5))
    check("F _clean_val Purchase/Receipt: 7 maydon 0.004 → ValueError; 0 va 0.005 → qabul",
          cv is not None and not xato, xato)

    js = getattr(crud, "_json_son", None)
    money = getattr(crud, "_ORDER_ITEM_MAX_MONEY", MONEY)
    son = getattr(crud, "_UPD_SON_CHEGARA", 1e12)
    _, i1 = urin(lambda: js("x", 0.004, False, True, money))
    r2, i2 = urin(lambda: js("x", 0.005, False, True, money))
    r3, i3 = urin(lambda: js("x", 0.001, True, False, money))
    r4, i4 = urin(lambda: js("x", 0.001, False, True, son))
    check("F _json_son: pul musbat 0.004 → ValueError; 0.005 → qabul; 0 ruxsat pul 0.001 va Float miqdor 0.001 → tegilmaydi",
          i1 == "ValueError" and i2 is None and yaqin(r2, 0.005) and i3 is None and yaqin(r3, 0.001)
          and i4 is None and yaqin(r4, 0.001), (i1, i2, r2, i3, r3, i4, r4))

    xs = getattr(crud, "_xarid_son", None)
    r1, i1 = urin(lambda: xs(0.001, "quantity"))
    _, i2 = urin(lambda: xs(0.001, "price_per_unit", pul=True))
    _, i3 = urin(lambda: xs(1e10, "price_per_unit", pul=True))
    r4, i4 = urin(lambda: xs(1e10, "quantity"))
    r5, i5 = urin(lambda: xs(9999999999.99, "price_per_unit", pul=True))
    check("F _xarid_son: miqdor 0.001 va 1e10 → qabul; narx 0.001 va 1e10 → ValueError; narx chegarasi → qabul",
          i1 is None and yaqin(r1, 0.001) and i2 == "ValueError" and i3 == "ValueError"
          and i4 is None and i5 is None and yaqin(r5, 9999999999.99), (i1, i2, i3, i4, i5))

    su = getattr(crud, "_sovga_ustalari", None)
    r1, i1 = urin(lambda: su(None))
    r2, i2 = urin(lambda: su([3, 3, 4]))
    _, i3 = urin(lambda: su([True]))
    _, i4 = urin(lambda: su("1"))
    _, i5 = urin(lambda: su(list(range(1, 1002))))
    r6, i6 = urin(lambda: su(list(range(1, 1001))))
    check("F _sovga_ustalari: None → [], takror olib tashlanadi, true/matn/1001 ta → ValueError, 1000 ta → qabul",
          su is not None and r1 == [] and r2 == [3, 4] and i3 == "ValueError" and i4 == "ValueError"
          and i5 == "ValueError" and i6 is None and len(r6 or []) == 1000, (r1, r2, i3, i4, i5, i6))


# ══════════════════════════════════════════════════════════════
# G. Statik (faqat SQLite rejimida — bazaga bog'liq emas)
# ══════════════════════════════════════════════════════════════
def g_bolimi():
    section("G. Statik — tur, tartib, qoidalar, sxemalar, UI")

    def annot(fn, nom):
        try:
            return inspect.signature(fn).parameters[nom].annotation
        except Exception:
            return None

    check("G api_create_transport: `data` — xom lug'at (dict)",
          annot(getattr(main, "api_create_transport", None), "data") is dict)
    check("G api_create_payment: `data` — xom lug'at (dict)",
          annot(getattr(main, "api_create_payment", None), "data") is dict)
    s = manba(getattr(main, "api_create_transport", None))
    check("G transport marshruti: _clean_val → create_transport_expense, ValueError → 400",
          tartibda(s, '_clean_val("TransportExpense"', "crud.create_transport_expense(",
                   "except ValueError", "status_code=400"))
    s = manba(getattr(main, "api_create_payment", None))
    check("G to'lov marshruti: _clean_val → sxema → create_payment; 409 va 404/400 saqlangan",
          tartibda(s, '_clean_val("Payment"', "schemas.PaymentCreate(", "crud.create_payment(",
                   "OverpaymentWarning", "status_code=409", "topilmadi"))
    s = manba(getattr(crud, "create_payment", None))
    check("G create_payment: ildiz tekshiruvi qulf va takror-tekshiruv so'rovidan OLDIN",
          tartibda(s, '_clean_val("Payment"', "_pul_qulfi(", "Payment.amount == _summa"))
    s = manba(getattr(crud, "create_transport_expense", None))
    check("G create_transport_expense: ildiz tekshiruvi obyekt yaratishdan OLDIN",
          tartibda(s, '_clean_val("TransportExpense"', "TransportExpense(", "db.add("))
    s = manba(getattr(crud, "open_gift_period", None))
    check("G open_gift_period: _clean_val va _sovga_ustalari davr yaratishdan OLDIN",
          tartibda(s, '_clean_val("GiftPeriodOpen"', "_sovga_ustalari(", "GiftPeriod(")
          and "amt = float(t.get(" not in s)
    s = manba(getattr(crud, "update_purchase", None))
    check("G update_purchase: jami summa tekshiruvi yozuvni o'zgartirishdan OLDIN",
          tartibda(s, "_ORDER_ITEM_MAX_MONEY", "p.quantity ="))
    s = manba(getattr(main, "api_purchase_stock", None)) or manba(getattr(main, "api_inventory_purchase", None))
    if not s:
        _m = fayl("main.py")
        _i = _m.find('@app.post("/api/inventory/{item_id}/purchase")')
        s = _m[_i:_i + 6000] if _i >= 0 else ""
    check("G xarid marshruti: tana (_tana_400 Purchase) xarid/to'lov/transport yozishdan OLDIN",
          tartibda(s, '_tana_400("Purchase"', "crud.purchase_stock(", "crud.create_transport_expense(",
                   "crud.create_supplier_payment("))
    vr = urin(lambda: crud._val_rules())[0] or {}
    check("G _val_rules: TransportExpense / Payment / GiftTier / GiftPeriodOpen qoidalari",
          all(k in vr for k in ("TransportExpense", "Payment", "GiftTier", "GiftPeriodOpen"))
          and set(vr.get("Payment", {})) == {"order_id", "amount", "payment_type", "payment_method",
                                             "received_by", "notes", "confirm_overpay"}
          and set(vr.get("TransportExpense", {})) == {"amount", "materials_note", "notes",
                                                      "production_type"}, list(vr)[-6:])
    tt = getattr(crud, "_TOLOV_TURI", {})
    tu = getattr(crud, "_TOLOV_USULI_MIJOZ", {})
    from models import PaymentType, PaymentMethod
    check("G to'lov tanlovlari = models.PaymentType / PaymentMethod qiymatlari",
          set(tt) == {e.value for e in PaymentType} and set(tu) == {e.value for e in PaymentMethod},
          (tt, tu))
    vm_ = getattr(crud, "_VAL_MAJBURIY", {})
    check("G _VAL_MAJBURIY: transport amount; to'lov order_id+amount; bosqich nom+summa; davr tiers",
          "amount" in vm_.get("TransportExpense", {}) and {"order_id", "amount"} <= set(vm_.get("Payment", {}))
          and {"gift_name", "threshold_amount"} <= set(vm_.get("GiftTier", {}))
          and "tiers" in vm_.get("GiftPeriodOpen", {}))
    ny = getattr(crud, "_NOL_YOKI_TIYIN", {})
    check("G _NOL_YOKI_TIYIN: xarid 2 maydon, kirim 5 maydon",
          set(ny.get("Purchase", ())) == {"paid_now", "transport_cost"}
          and set(ny.get("Receipt", ())) == {"paid_now", "transport_cost", "tushirish_cost",
                                             "yuklash_cost", "boshqa_cost"}, ny)

    def sx(klass, **kw):
        return urin(lambda: klass(**kw))[1]

    T, P = schemas.TransportExpenseCreate, schemas.PaymentCreate
    check("G TransportExpenseCreate: Infinity / true / \"5\" / 1e20 / uzun matn / noto'g'ri tur — rad",
          all(sx(T, **kw) for kw in ({"amount": float("inf")}, {"amount": True}, {"amount": "5"},
                                      {"amount": 1e20}, {"amount": 5, "materials_note": "m" * 256},
                                      {"amount": 5, "production_type": "xyz"})))
    check("G PaymentCreate: order_id true / amount true / Infinity / noto'g'ri tur, usul / uzun qabul qiluvchi — rad",
          all(sx(P, **kw) for kw in ({"order_id": True, "amount": 5}, {"order_id": 1, "amount": True},
                                      {"order_id": 1, "amount": float("inf")},
                                      {"order_id": 1, "amount": 5, "payment_type": "xyz"},
                                      {"order_id": 1, "amount": 5, "payment_method": "cash"},
                                      {"order_id": 1, "amount": 5, "received_by": "r" * 101})))
    p, ist = urin(lambda: P(order_id=1, amount=5))
    check("G PaymentCreate standartlari: partial / naqd / tasdiqsiz",
          p is not None and p.payment_type == "partial" and p.payment_method == "naqd"
          and p.confirm_overpay is False, ist)

    orders = fayl("templates/orders.html")
    debts = fayl("templates/debts.html")
    sp_o = js_funksiya(orders, "savePayment")
    sp_d = js_funksiya(debts, "savePayment")
    check("G orders.html savePayment: 409 overpayment_warning → tasdiq va confirm_overpay bilan qayta",
          tartibda(sp_o, "res.status === 409", "overpayment_warning", "showConfirmModal(",
                   "data.confirm_overpay = true", "yubor()"))
    check("G orders.html savePayment: xatoda server sababi (eski umumiy matn yolg'iz emas)",
          "tolovXatoSababi(res" in sp_o and bool(js_funksiya(orders, "tolovXatoSababi"))
          and "showMsg('❌ To\\'lovni saqlashda xato', 'error')" not in sp_o)
    check("G debts.html savePayment: 409 → customConfirm, confirm_overpay bilan qayta; xatoda serverSababi",
          tartibda(sp_d, "res.status === 409", "overpayment_warning", "customConfirm(",
                   "confirm_overpay = true", "yubor()")
          and "serverSababi(res" in sp_d and "'Xato yuz berdi';" not in sp_d.replace(
              "serverSababi(res, 'Xato yuz berdi')", ""))
    tdir = os.path.join(ROOT, "templates")
    yozadi = []
    for f in sorted(os.listdir(tdir)):
        if f.endswith(".html") and "/api/transport-expenses" in fayl(os.path.join("templates", f)):
            yozadi.append(f)
    check("G hech bir shablon /api/transport-expenses ga murojaat qilmaydi (faqat API — qoidalar ustunlardan)",
          yozadi == [], yozadi)


# ══════════════════════════════════════════════════════════════
# H. 422 qoladi
# ══════════════════════════════════════════════════════════════
def h_bolimi():
    section("H. Tana lug'at emas / buzilgan JSON — 422 (500 emas)")
    tikla()
    h0 = holat()
    for nom, url, raw in [("transport ro'yxat", "/api/transport-expenses", "[]"),
                          ("transport buzilgan JSON", "/api/transport-expenses", '{"amount":'),
                          ("to'lov ro'yxat", "/api/payments", "[1, 2]"),
                          ("to'lov buzilgan JSON", "/api/payments", '{"order_id":'),
                          ("sovg'a ochish ro'yxat", "/api/gift-period/open", "[]")]:
        r = xom(C, "post", url, raw)
        check(f"H {nom} → 422, holat o'zgarmagan", r.status_code == 422 and holat() == h0,
              f"{r.status_code} {matn(r)[:120]}")


# ══════════════════════════════════════════════════════════════
# K. Kumulyativ
# ══════════════════════════════════════════════════════════════
def k_bolimi():
    section("K. KUMULYATIV — tiklamasdan, hamma problardan keyin")
    check("K sahifalar 200 (1-korxona)", not sahifalar_yiqilgan(C), sahifalar_yiqilgan(C))
    _b = [u for u in SAHIFALAR if u != f"/api/orders/{OT}"]     # 1-korxona buyurtmasi — B uchun 404
    check("K sahifalar 200 (2-korxona)", not sahifalar_yiqilgan(CB, _b), sahifalar_yiqilgan(CB, _b))
    besh = [k for k in KODLAR if k[0] >= 500]
    check("K butun ish davomida birorta ham 5xx javob yo'q", not besh, besh[:8])


# ══════════════════════════════════════════════════════════════
# Ishga tushirish
# ══════════════════════════════════════════════════════════════
a_bolimi()
b_bolimi()
c_bolimi()
d_bolimi()
e_bolimi()
x_bolimi()
f_bolimi()
if not PG_REJIM:
    g_bolimi()
h_bolimi()
k_bolimi()

if not PG_REJIM:
    section("P. PostgreSQL rejimi")
    if not PG_URL:
        print("  (o'tkazib yuborildi — PG_URL muhitda yo'q; masalan "
              "PG_URL=postgresql://postgres@127.0.0.1:5432)")
    else:
        env = dict(os.environ, PUL_PG_REJIM="1")
        try:
            pr = subprocess.run([sys.executable, os.path.abspath(__file__)], env=env,
                                capture_output=True, text=True, timeout=800)
            chiq = pr.stdout + ("\n" + pr.stderr[-2000:] if pr.returncode not in (0, 1) else "")
            rc = pr.returncode
        except Exception as e:
            chiq, rc = f"ISTISNO {type(e).__name__}: {e}", 99
        p_ok = p_fail = None
        for q in chiq.splitlines():
            if q.startswith("NATIJA:"):
                try:
                    p_ok = int(q.split("o'tdi =")[1].split()[0])
                    p_fail = int(q.split("yiqildi =")[1].split()[0])
                except Exception:
                    pass
                print("  [PG] P-" + q)
            elif "✗" in q or q.startswith("---") or q.startswith("  ✓"):
                print(q)
        if p_ok is None:
            check("P PostgreSQL rejimi ishga tushdi va natija berdi", False, chiq[-600:])
        else:
            OK += p_ok
            FAIL += p_fail
            if p_fail:
                FAILED.append(f"[PG] ichki yiqilganlar: {p_fail} ta (yuqorida ✗ bilan)")
            check("P PostgreSQL rejimi yakunlandi (chiqish kodi 0 yoki 1)", rc in (0, 1), rc)

print("\n" + "=" * 66)
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
sys.exit(0 if FAIL == 0 else 1)
