#!/usr/bin/env python3
"""
test_tolov_query.py — 17c-band: so'rov qatoridagi pul marshrutlari va
loyiha "To'langan" summasi.

NIMA UCHUN KERAK (2026-09-21)
-----------------------------
Hammasi O'LCHANGAN (`work/probe17c.py`, har prob alohida toza bazada;
jonli sayt), asl kod = kech18.

1) `POST /api/projects/{id}/payment?amount=` — loyihaga pulni TO'LOV
   YOZUVISIZ `Project.total_paid` ga qo'shardi. Bu pul Moliyaga tushmasdi
   va keyingi buyurtma to'lovida IZSIZ O'CHIB KETARDI:
       zaklat 300 000 → total_paid 300 000, Payment 0 ta
       buyurtmaga 200 000 to'lov → total_paid 200 000  (300 000 yo'qoldi)
   FOYDALANUVCHI QARORI "1" (2026-09-21): loyihadagi "💰 To'lov qo'shish"
   OLIB TASHLANADI, to'lov FAQAT buyurtma orqali. Marshrut 410 qaytaradi.

2) `Project.total_paid` ni faqat `create_payment` / `delete_payment`
   yangilardi. Yuk xati to'lovi, pul qaytarish, buyurtmani butunlay
   o'chirish — yangilamasdi. Jonli: PRJ-033 buyurtmasi to'liq to'langan
   (2 560 000), loyiha kartasida "To'langan: 0". Endi HAR BIR yo'l
   `crud._loyiha_tolangan_yangila` ni chaqiradi, eski farqlarni esa
   ishga tushishdagi `main._migrate_loyiha_tolangan_sinxron` tuzatadi.

3) Hodim avansi, oylik tuzatish (bonus / kamaytirish), oylik qarzini
   yopish — pul URL da keladi va FastAPI `float` uni tekshiruvsiz
   o'tkazardi: `inf` avans avanslar ro'yxatini (500), `inf` bonus
   "Qarzdorlar" sahifasini (500) BUZARDI; manfiy bonus mavjud bonusni
   JIMGINA o'chirardi; 13-oy / 99999-yil yozilardi; noto'g'ri avans sanasi
   JIMGINA bugunga aylanardi; oylik yopishda 13-oy → 500.

4) Ta'minotchiga to'lov — pydantic `Field(gt=0)` `Infinity` ni (ortiqcha
   to'lov tasdig'i bilan SAQLANARDI, ta'minotchilar va qarzdorlar
   sahifalarini buzardi), `true` ni (→ 1 so'm), `"5000"` matnini va
   `1e20` ni o'tkazib yuborardi.

QAMROV
------
A. Loyiha to'lovi olib tashlangan: 410, hech narsa yozilmaydi; begona → 404
B. `total_paid` invarianti — oddiy to'lov, o'chirish, yuk xati to'lovi,
   pul qaytarish, buyurtmani butunlay o'chirish, chiqindi qutisidan o'chirish
C. Ishga tushish migratsiyasi — eski farqlar, idempotentlik, korxona chegarasi
D. Hodim avansi (HTTP): UI tanasi, yomon qiymatlar, sana, izoh, begona
E. Oylik tuzatish (HTTP): UI tanalari, yomon qiymat MAVJUD yozuvni
   o'zgartirmaydi, 0 = o'chirish saqlangan, begona
F. Oylik qarzini yopish (HTTP)
G. Ta'minotchiga to'lov (HTTP): UI tanasi, ortiqcha to'lov oqimi, yomon
   tanalar, tanadagi `supplier_id` e'tiborsiz, begona
H. Ildiz (marshrutni chetlab): yordamchilar, crud va services funksiyalari
I. Statik: UI dan tugma olib tashlangan, qoidalar = sxema maydonlari,
   UI kalitlari qoidalarda, marshrutlar matn oladi, yordamchi HAR yo'lda

ISHLATISH
---------
    python tools/test_tolov_query.py
    TENANT_FILTER=1 python tools/test_tolov_query.py

Asl kodga qarshi ham QULAMAYDI (mutatsiya uchun): yangi yordamchilarga
murojaat `getattr` bilan, ildiz chaqiruvlari `try/except` bilan, HTTP
istisnolar 599 ga aylantiriladi.

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import tempfile
import inspect
import re
from datetime import datetime
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "tolov_query_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, schemas, services           # noqa: E402

from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Payment, Employee, EmployeeAdvance,
    EmployeeMonthlyAdjustment, Supplier, SupplierPayment, Inventory,
    InventoryPurchase, ReturnItem, ReturnReason,
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


def yaqin(a, b, eps=0.005):
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
    auth.create_user(db, "TQ_admin", "Parol123!", UserRole.ADMIN, "TQ Admin",
                     company_id=1)
    auth.create_user(db, "TQ_admin_b", "Parol123!", UserRole.ADMIN, "TQ Admin B",
                     company_id=2)

PRJ = Project(company_id=1, client_name="TQ Mijoz", project_name="TQ loyiha",
              total_budget=5_000_000, total_paid=0)
PRJ_B = Project(company_id=2, client_name="TQ Begona", project_name="TQ begona loyiha",
                total_budget=1_000_000, total_paid=0)
PRJ_BOSH = Project(company_id=1, client_name="TQ Bo'sh", project_name="TQ buyurtmasiz",
                   total_budget=0, total_paid=0)
db.add_all([PRJ, PRJ_B, PRJ_BOSH])
db.commit()

EMP = Employee(company_id=1, name="TQ Hodim")
EMP_B = Employee(company_id=2, name="TQ Begona hodim")
SUP = Supplier(company_id=1, name="TQ Ta'minotchi", phone="+998900001701")
SUP2 = Supplier(company_id=1, name="TQ Ta'minotchi 2", phone="+998900001702")
SUP_B = Supplier(company_id=2, name="TQ Begona ta'minotchi", phone="+998900001703")
MAT = Inventory(company_id=1, item_name="TQ_SEMENT", unit="kg", stock_quantity=0,
                price_per_unit=0, min_stock=0)
db.add_all([EMP, EMP_B, SUP, SUP2, SUP_B, MAT])
db.commit()
db.add(InventoryPurchase(inventory_id=MAT.id, item_name="TQ_SEMENT", quantity=10,
                         price_per_unit=50_000, total_amount=500_000,
                         supplier_id=SUP.id, is_credit=True))
db.add(InventoryPurchase(inventory_id=MAT.id, item_name="TQ_SEMENT", quantity=10,
                         price_per_unit=50_000, total_amount=500_000,
                         supplier_id=SUP2.id, is_credit=True))
db.commit()

P_ID, PB_ID, P0_ID = PRJ.id, PRJ_B.id, PRJ_BOSH.id
E_ID, EB_ID = EMP.id, EMP_B.id
S_ID, S2_ID, SB_ID = SUP.id, SUP2.id, SUP_B.id

_n = [0]


def yangi_buyurtma(project_id=None, company_note="TQ"):
    """Loyihada YANGI buyurtma (panel, penoplastsiz — ombor kerak emas)."""
    _n[0] += 1
    with contextlib.redirect_stdout(_quiet):
        o = crud.create_order(db, schemas.OrderCreate(
            project_id=project_id or P_ID, order_type="product",
            items=[schemas.OrderItemCreate(
                name=f"{company_note}_DETAL_{_n[0]}", category="panel", width=100,
                thickness=10, length=100, quantity=10, unit_price=100_000,
                is_coated=False)]), performed_by="TQ")
    oid = o.id
    iid = db.query(OrderItem).filter(OrderItem.order_id == oid).first().id
    return oid, iid


def tolangan(pid):
    db.expire_all()
    p = db.get(Project, pid)
    return float(p.total_paid or 0) if p else None


def tolov_yigindi(pid):
    """HAQIQIY to'lovlar yig'indisi — loyiha buyurtmalaridagi barcha Payment."""
    db.expire_all()
    q = db.query(Payment).join(Order, Order.id == Payment.order_id).filter(
        Order.project_id == pid)
    return round(sum(float(x.amount or 0) for x in q.all()), 2)


def tolov_soni():
    db.expire_all()
    return db.query(Payment).count()


def avanslar(eid):
    db.expire_all()
    return [(round(float(a.amount), 2), a.date.strftime("%Y-%m-%d") if a.date else None,
             a.notes) for a in db.query(EmployeeAdvance).filter(
        EmployeeAdvance.employee_id == eid).order_by(EmployeeAdvance.id).all()]


def tuzatishlar(eid):
    db.expire_all()
    return [(a.year, a.month, round(float(a.reduction_amount or 0), 2),
             round(float(a.bonus_amount or 0), 2), a.reason, a.bonus_reason)
            for a in db.query(EmployeeMonthlyAdjustment).filter(
        EmployeeMonthlyAdjustment.employee_id == eid).order_by(
        EmployeeMonthlyAdjustment.id).all()]


def sup_tolovlar(sid):
    db.expire_all()
    return [(round(float(p.amount), 2), p.notes) for p in db.query(SupplierPayment).filter(
        SupplierPayment.supplier_id == sid).order_by(SupplierPayment.id).all()]


def login(user):
    c = TestClient(main.app, base_url="https://testserver",
                   raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": "Parol123!"},
               follow_redirects=False)
    assert r.status_code == 302, f"{user} login bo'lmadi: {r.status_code}"
    return c


C = login("TQ_admin")
CB = login("TQ_admin_b")


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


def jtana(url, matn, client=None):
    """Xom JSON matni bilan POST (Infinity / NaN ni ham yuborish uchun)."""
    return _req(client or C, "post", url, content=matn,
                headers={"Content-Type": "application/json"})


def detail(r):
    try:
        d = r.json()
        return d.get("detail") if isinstance(d, dict) else d
    except Exception:
        return None


def _yordamchi(nom):
    """Yangi crud yordamchisi — asl kodda yo'q bo'lsa None (skript qulamasin)."""
    return getattr(crud, nom, None)


BUGUN = datetime.utcnow().strftime("%Y-%m-%d")

# ══════════════════════════════════════════════════════════════
section("A. Loyiha to'lovi (zaklat) OLIB TASHLANGAN — 410, hech narsa yozilmaydi")
# ══════════════════════════════════════════════════════════════
t0, n0 = tolangan(P_ID), tolov_soni()
r = req("post", f"/api/projects/{P_ID}/payment?amount=300000")
check(f"A1 POST /api/projects/A/payment?amount=300000 → {r.status_code} (410 shart)",
      r.status_code == 410, r.text[:160])
check("A2 javob sababi aniq: to'lov buyurtma orqali",
      isinstance(detail(r), str) and "buyurtma orqali" in detail(r), str(detail(r))[:160])
check("A3 total_paid o'zgarmadi, Payment yozuvi yaratilmadi",
      tolangan(P_ID) == t0 and tolov_soni() == n0, f"{t0}->{tolangan(P_ID)} | {n0}->{tolov_soni()}")
for _v in ("inf", "-inf", "nan", "-5", "0", "1e20", "abc", "true", ""):
    r = req("post", f"/api/projects/{P_ID}/payment?amount={_v}")
    check(f"A4 amount={_v!r} → {r.status_code} (410 shart), hech narsa o'zgarmadi",
          r.status_code == 410 and tolangan(P_ID) == t0 and tolov_soni() == n0,
          f"{r.text[:100]} | {tolangan(P_ID)}")
r = req("post", f"/api/projects/{P_ID}/payment")
check(f"A5 amount YO'Q → {r.status_code} (410 shart)", r.status_code == 410, r.text[:120])
tb0 = tolangan(PB_ID)
r = req("post", f"/api/projects/{PB_ID}/payment?amount=300000")
check(f"A6 begona loyiha → {r.status_code} (404 shart — mavjudligi bildirilmaydi)",
      r.status_code == 404, r.text[:120])
r = req("post", f"/api/projects/{PB_ID}/payment?amount=inf")
check(f"A7 begona loyiha + yomon summa → {r.status_code} (404 shart — egalik BIRINCHI)",
      r.status_code == 404, r.text[:120])
check("A8 begona loyiha total_paid o'zgarmadi", tolangan(PB_ID) == tb0,
      f"{tb0}->{tolangan(PB_ID)}")
r = req("post", "/api/projects/99999999/payment?amount=1000")
check(f"A9 mavjud bo'lmagan loyiha → {r.status_code} (404 shart)", r.status_code == 404,
      r.text[:120])
check("A10 crud.add_payment (yozuvsiz zaklat) OLIB TASHLANGAN",
      not hasattr(crud, "add_payment"), "crud.add_payment hali bor")

# ══════════════════════════════════════════════════════════════
section("B. total_paid = HAQIQIY to'lovlar yig'indisi — HAR BIR yo'lda")
# ══════════════════════════════════════════════════════════════
O1, I1 = yangi_buyurtma()
O2, I2 = yangi_buyurtma()

r = req("post", "/api/payments", json={"order_id": O1, "amount": 200_000})
check(f"B1 buyurtma to'lovi 200 000 → {r.status_code} (200 shart)", r.status_code == 200,
      r.text[:140])
check("B2 total_paid = 200 000 = to'lovlar yig'indisi",
      yaqin(tolangan(P_ID), 200_000) and yaqin(tolangan(P_ID), tolov_yigindi(P_ID)),
      f"{tolangan(P_ID)} / {tolov_yigindi(P_ID)}")

r = req("post", "/api/payments", json={"order_id": O2, "amount": 100_000})
check(f"B3 ikkinchi buyurtmaga 100 000 → {r.status_code}", r.status_code == 200, r.text[:140])
check("B4 total_paid = 300 000 (ikkala buyurtma)",
      yaqin(tolangan(P_ID), 300_000) and yaqin(tolangan(P_ID), tolov_yigindi(P_ID)),
      f"{tolangan(P_ID)} / {tolov_yigindi(P_ID)}")

db.expire_all()
_p2 = db.query(Payment).filter(Payment.order_id == O2).first()
r = req("delete", f"/api/payments/{_p2.id}")
check(f"B5 to'lov o'chirildi → {r.status_code}", r.status_code == 200, r.text[:140])
check("B6 total_paid = 200 000 (o'chirilgan to'lov chiqdi)",
      yaqin(tolangan(P_ID), 200_000) and yaqin(tolangan(P_ID), tolov_yigindi(P_ID)),
      f"{tolangan(P_ID)} / {tolov_yigindi(P_ID)}")

n0 = tolov_soni()
r = req("post", "/api/deliveries", json={
    "order_id": O1, "items": [{"order_item_id": I1, "quantity": 1}],
    "payment_amount": 50_000, "payment_method": "naqd"})
check(f"B7 yuk xati + to'lov 50 000 → {r.status_code} (200 shart)", r.status_code == 200,
      r.text[:160])
check("B8 yuk xati to'lovi yozuvi yaratildi", tolov_soni() == n0 + 1,
      f"{n0}->{tolov_soni()}")
check("B9 total_paid = 250 000 — yuk xati to'lovi ham kiradi (ILGARI KIRMASDI, jonli PRJ-033)",
      yaqin(tolangan(P_ID), 250_000) and yaqin(tolangan(P_ID), tolov_yigindi(P_ID)),
      f"{tolangan(P_ID)} / {tolov_yigindi(P_ID)}")

# kech42: brakka pul qaytarilmaydi (400) — sabab "Ortiqcha"; 24-band: naqd faqat ORTIQCHA
# to'langan qism — buyurtmaning kelishilgan summasi to'langaniga (250 000) teng qilinadi,
# shunda 30 000 qaytishi AYNAN 30 000 naqd (manfiy to'lov) beradi.
_ret = ReturnItem(company_id=1, order_id=O1, item_name="TQ_DETAL qaytarish", quantity=1,
                  unit="dona", reason=ReturnReason.EXCESS, refund_amount=30_000,
                  is_refunded=False)
db.add(_ret)
_o1_ = db.get(Order, O1)
_o1_.agreed_amount = 250_000
db.commit()
r = req("post", f"/api/returns/{_ret.id}/refund")
check(f"B10 pul qaytarildi (30 000) → {r.status_code} (200 shart)", r.status_code == 200,
      r.text[:140])
check("B11 total_paid = 220 000 — qaytarilgan pul ayiriladi (ILGARI AYIRILMASDI)",
      yaqin(tolangan(P_ID), 220_000) and yaqin(tolangan(P_ID), tolov_yigindi(P_ID)),
      f"{tolangan(P_ID)} / {tolov_yigindi(P_ID)}")

O3, I3 = yangi_buyurtma()
r = req("post", "/api/payments", json={"order_id": O3, "amount": 40_000})
check(f"B12 uchinchi buyurtmaga 40 000 → {r.status_code}", r.status_code == 200, r.text[:140])
check("B13 total_paid = 260 000", yaqin(tolangan(P_ID), 260_000), f"{tolangan(P_ID)}")
r = req("delete", f"/api/orders/{O3}")
db.expire_all()
check(f"B14 topshirilmagan buyurtma o'chirildi → {r.status_code}, bazadan butunlay chiqdi",
      r.status_code == 200 and db.get(Order, O3) is None, r.text[:140])
check("B15 total_paid = 220 000 — o'chgan buyurtma to'lovi chiqdi (ILGARI QOLARDI)",
      yaqin(tolangan(P_ID), 220_000) and yaqin(tolangan(P_ID), tolov_yigindi(P_ID)),
      f"{tolangan(P_ID)} / {tolov_yigindi(P_ID)}")

O4, I4 = yangi_buyurtma()
r = req("post", "/api/deliveries", json={
    "order_id": O4, "items": [{"order_item_id": I4, "quantity": 1}],
    "payment_amount": 10_000, "payment_method": "naqd"})
check(f"B16 to'rtinchi buyurtma: yuk xati + 10 000 → {r.status_code}", r.status_code == 200,
      r.text[:140])
check("B17 total_paid = 230 000", yaqin(tolangan(P_ID), 230_000), f"{tolangan(P_ID)}")
r = req("delete", f"/api/orders/{O4}")
db.expire_all()
_o4 = db.get(Order, O4)
check(f"B18 topshirilgan buyurtma → {r.status_code}, YUMSHOQ o'chdi (chiqindi qutisida)",
      r.status_code == 200 and _o4 is not None and bool(_o4.is_deleted), r.text[:140])
check("B19 yumshoq o'chirishda total_paid o'zgarmaydi (to'lov bazada qoladi) = 230 000",
      yaqin(tolangan(P_ID), 230_000) and yaqin(tolangan(P_ID), tolov_yigindi(P_ID)),
      f"{tolangan(P_ID)} / {tolov_yigindi(P_ID)}")
r = req("delete", f"/api/orders/{O4}/permanent")
db.expire_all()
check(f"B20 chiqindi qutisidan butunlay o'chirildi → {r.status_code}",
      r.status_code == 200 and db.get(Order, O4) is None, r.text[:140])
check("B21 total_paid = 220 000 — butunlay o'chgan buyurtma to'lovi chiqdi (ILGARI QOLARDI)",
      yaqin(tolangan(P_ID), 220_000) and yaqin(tolangan(P_ID), tolov_yigindi(P_ID)),
      f"{tolangan(P_ID)} / {tolov_yigindi(P_ID)}")

check("B22 begona korxona loyihasi total_paid tegilmadi", tolangan(PB_ID) == tb0,
      f"{tb0}->{tolangan(PB_ID)}")
r = req("get", "/projects")
_kutilgan = f'data-paid="{db.get(Project, P_ID).total_paid}"'
check(f"B23 /projects → {r.status_code}, kartada To'langan = haqiqiy to'lovlar ({_kutilgan})",
      r.status_code == 200 and _kutilgan in r.text, r.text[:120] if r.status_code != 200 else "")
check("B24 /projects da loyihaga to'lov tugmasi va oynasi YO'Q",
      r.status_code == 200 and "payModal" not in r.text and "savePayment" not in r.text
      and "/payment?amount" not in r.text, "sahifada eski tugma qolgan")
r = req("get", "/api/projects")
_pa = None
try:
    _pa = [x for x in r.json() if x.get("id") == P_ID][0].get("total_paid")
except Exception:
    pass
check("B25 GET /api/projects → total_paid = 220 000", yaqin(_pa, 220_000), f"{_pa}")

# ══════════════════════════════════════════════════════════════
section("C. Ishga tushish migratsiyasi — eski farqlar tuzatiladi, idempotent")
# ══════════════════════════════════════════════════════════════
_migr = getattr(main, "_migrate_loyiha_tolangan_sinxron", None)
check("C1 main._migrate_loyiha_tolangan_sinxron mavjud", callable(_migr))
db.expire_all()
db.get(Project, P_ID).total_paid = 0              # PRJ-033 holati
db.get(Project, P0_ID).total_paid = 5_000         # eski yozuvsiz \"zaklat\"
db.get(Project, PB_ID).total_paid = 999            # begona korxona — o'z qiymati bilan
db.commit()
_ok_b = tolov_yigindi(PB_ID)
try:
    with contextlib.redirect_stdout(_quiet):
        _n1 = _migr() if callable(_migr) else None
except Exception as e:
    _n1 = f"ISTISNO {type(e).__name__}: {e}"
check(f"C2 migratsiya 3 ta farqli loyihani tuzatdi ({_n1})", _n1 == 3, f"{_n1}")
check("C3 PRJ-033 holati: 0 → haqiqiy to'lovlar (220 000)",
      yaqin(tolangan(P_ID), 220_000), f"{tolangan(P_ID)}")
check("C4 buyurtmasiz loyihadagi yozuvsiz summa → 0", yaqin(tolangan(P0_ID), 0),
      f"{tolangan(P0_ID)}")
check("C5 begona korxona loyihasi O'Z to'lovlariga tenglashdi",
      yaqin(tolangan(PB_ID), _ok_b), f"{tolangan(PB_ID)} / {_ok_b}")
try:
    with contextlib.redirect_stdout(_quiet):
        _n2 = _migr() if callable(_migr) else None
except Exception as e:
    _n2 = f"ISTISNO {type(e).__name__}: {e}"
check(f"C6 ikkinchi ishga tushish — 0 qator ({_n2}), qiymatlar joyida",
      _n2 == 0 and yaqin(tolangan(P_ID), 220_000), f"{_n2} | {tolangan(P_ID)}")
tb0 = tolangan(PB_ID)

# ══════════════════════════════════════════════════════════════
section("D. Hodim avansi — POST /api/employees/{id}/advance")
# ══════════════════════════════════════════════════════════════
# kpi.html 942: `?amount=${amount}&notes=${encodeURIComponent(notes)}&adv_date=${dateVal}`
r = req("post", f"/api/employees/{E_ID}/advance?amount=150000&notes=&adv_date=")
_a = avanslar(E_ID)
check(f"D1 UI tanasi (izoh va sana BO'SH) → {r.status_code} (200 shart)", r.status_code == 200,
      r.text[:140])
check("D2 avans 150 000, sana BUGUN (bo'sh sana saqlangan xulq)",
      len(_a) == 1 and _a[0][0] == 150_000 and _a[0][1] == BUGUN, f"{_a}")
r = req("post", f"/api/employees/{E_ID}/advance?amount=75000.5&notes=Oldindan&adv_date=2026-09-05")
_a = avanslar(E_ID)
check(f"D3 UI tanasi (izoh + sana) → {r.status_code}, 75 000.50, 2026-09-05, izoh saqlandi",
      r.status_code == 200 and len(_a) == 2 and _a[1] == (75_000.5, "2026-09-05", "Oldindan"),
      f"{r.text[:100]} | {_a}")
_a0 = avanslar(E_ID)
for _v in ("inf", "-inf", "nan", "Infinity", "-Infinity", "NaN", "-5", "0", "0.0",
           "1e20", "1e10", "abc", "true", "12abc", "1e", "", "  ", "1_000", "5_0"):
    r = req("post", f"/api/employees/{E_ID}/advance?amount={_v}&notes=&adv_date=")
    check(f"D4 amount={_v!r} → {r.status_code} (400 shart), avans yozilmadi",
          r.status_code == 400 and avanslar(E_ID) == _a0, f"{r.text[:100]}")
r = req("post", f"/api/employees/{E_ID}/advance?notes=x")
check(f"D5 amount YO'Q → {r.status_code} (400 shart)",
      r.status_code == 400 and avanslar(E_ID) == _a0, r.text[:120])
r = req("post", f"/api/employees/{E_ID}/advance?amount=9999999999.99&notes=&adv_date=")
_a = avanslar(E_ID)
check(f"D6 aynan sig'im chegarasi 9 999 999 999.99 → {r.status_code} (200 shart)",
      r.status_code == 200 and len(_a) == len(_a0) + 1, r.text[:120])
_a0 = avanslar(E_ID)
for _d in ("abc", "2026-13-45", "2026-02-30", "1999-12-31", "2101-01-01", "05.09.2026",
           "2026-9-5x", "2026-09-05T10:00:00"):
    r = req("post", f"/api/employees/{E_ID}/advance?amount=1000&notes=&adv_date={_d}")
    check(f"D7 adv_date={_d!r} → {r.status_code} (400 shart — ILGARI JIMGINA BUGUNGA aylanardi)",
          r.status_code == 400 and avanslar(E_ID) == _a0, f"{r.text[:100]}")
r = req("post", f"/api/employees/{E_ID}/advance?amount=1000&notes=" + "x" * 10_001)
check(f"D8 izoh 10 001 belgi → {r.status_code} (400 shart)",
      r.status_code == 400 and avanslar(E_ID) == _a0, r.text[:120])
r = req("post", f"/api/employees/{E_ID}/advance?amount=1000&notes=" + "y" * 10_000)
check(f"D9 izoh aynan 10 000 belgi → {r.status_code} (200 shart)",
      r.status_code == 200 and len(avanslar(E_ID)) == len(_a0) + 1, r.text[:120])
_ab0 = avanslar(EB_ID)
for _v in ("inf", "1000"):
    r = req("post", f"/api/employees/{EB_ID}/advance?amount={_v}")
    check(f"D10 begona hodim (amount={_v}) → {r.status_code} (404 shart — egalik BIRINCHI)",
          r.status_code == 404 and avanslar(EB_ID) == _ab0, r.text[:120])
r = req("get", f"/api/employees/{E_ID}/advances?year=2026&month=9")
check(f"D11 avanslar ro'yxati → {r.status_code} (200 shart)", r.status_code == 200,
      r.text[:120])

# ══════════════════════════════════════════════════════════════
section("E. Oylik tuzatish — POST /api/employees/{id}/monthly-adjustment")
# ══════════════════════════════════════════════════════════════
_U = f"/api/employees/{E_ID}/monthly-adjustment"
# kpi.html 1340: bonus; 1316: kamaytirish
r = req("post", f"{_U}?year=2026&month=9&bonus_amount=50000&bonus_reason=Yaxshi%20ish")
check(f"E1 UI bonus tanasi → {r.status_code} (200 shart)", r.status_code == 200, r.text[:140])
check("E2 bonus 50 000 yozildi", tuzatishlar(E_ID) == [(2026, 9, 0, 50_000, None, "Yaxshi ish")],
      f"{tuzatishlar(E_ID)}")
r = req("post", f"{_U}?year=2026&month=9&reduction_amount=20000&reason=")
check(f"E3 UI kamaytirish tanasi (sabab bo'sh) → {r.status_code}", r.status_code == 200,
      r.text[:140])
_t0 = tuzatishlar(E_ID)
check("E4 kamaytirish 20 000, bonus 50 000 SAQLANDI (faqat berilgani yangilanadi)",
      len(_t0) == 1 and _t0[0][:4] == (2026, 9, 20_000, 50_000), f"{_t0}")
for _q in ("bonus_amount=inf", "bonus_amount=-inf", "bonus_amount=nan", "bonus_amount=Infinity",
           "bonus_amount=-50000", "bonus_amount=1e20", "bonus_amount=1e10", "bonus_amount=abc",
           "bonus_amount=true", "reduction_amount=-1", "reduction_amount=inf",
           "reduction_amount=12abc", "bonus_amount=5_000"):
    r = req("post", f"{_U}?year=2026&month=9&{_q}")
    check(f"E5 {_q} → {r.status_code} (400 shart), MAVJUD yozuv o'zgarmadi",
          r.status_code == 400 and tuzatishlar(E_ID) == _t0, f"{r.text[:100]} | {tuzatishlar(E_ID)}")
for _y, _m in (("2026", "13"), ("2026", "0"), ("2026", "-1"), ("2026", "abc"), ("2026", "9.5"),
               ("1999", "9"), ("2101", "9"), ("99999", "9"), ("1", "9"), ("abc", "9"),
               ("", "9"), ("2026", "")):
    r = req("post", f"{_U}?year={_y}&month={_m}&bonus_amount=1000")
    check(f"E6 year={_y!r} month={_m!r} → {r.status_code} (400 shart), yangi yozuv yo'q",
          r.status_code == 400 and tuzatishlar(E_ID) == _t0, f"{r.text[:100]} | {tuzatishlar(E_ID)}")
r = req("post", f"{_U}?month=9&bonus_amount=1000")
check(f"E7 year YO'Q → {r.status_code} (400 shart)",
      r.status_code == 400 and tuzatishlar(E_ID) == _t0, r.text[:120])
r = req("post", f"{_U}?year=2026&month=9&bonus_amount=1000&bonus_reason=" + "z" * 10_001)
check(f"E8 bonus sababi 10 001 belgi → {r.status_code} (400 shart)",
      r.status_code == 400 and tuzatishlar(E_ID) == _t0, r.text[:120])
r = req("post", f"{_U}?year=2026&month=9&reduction_amount=1000&reason=" + "z" * 10_001)
check(f"E9 kamaytirish sababi 10 001 belgi → {r.status_code} (400 shart)",
      r.status_code == 400 and tuzatishlar(E_ID) == _t0, r.text[:120])
r = req("get", f"{_U}?year=2026&month=9")
_g = r.json() if r.status_code == 200 else {}
check(f"E10 GET → {r.status_code}, 20 000 / 50 000", r.status_code == 200
      and yaqin(_g.get("reduction_amount"), 20_000) and yaqin(_g.get("bonus_amount"), 50_000),
      f"{_g}")
r = req("post", f"{_U}?year=2026&month=12&bonus_amount=1000")
check(f"E11 12-oy (chegara) → {r.status_code} (200 shart)", r.status_code == 200, r.text[:120])
r = req("post", f"{_U}?year=2026&month=12&bonus_amount=0")
check(f"E12 12-oy bonus 0 → {r.status_code}, yozuv o'chdi", r.status_code == 200
      and not [x for x in tuzatishlar(E_ID) if x[1] == 12], f"{tuzatishlar(E_ID)}")
r = req("post", f"{_U}?year=2026&month=9&reduction_amount=0&reason=")
_t = tuzatishlar(E_ID)
check(f"E13 kamaytirish 0 → {r.status_code}, kamaytirish o'chdi, bonus qoldi",
      r.status_code == 200 and len(_t) == 1 and _t[0][2:4] == (0, 50_000), f"{_t}")
r = req("post", f"{_U}?year=2026&month=9&bonus_amount=0&bonus_reason=")
check(f"E14 bonus ham 0 → {r.status_code}, yozuv BUTUNLAY o'chdi (UI \"0 — o'chadi\" saqlangan)",
      r.status_code == 200 and tuzatishlar(E_ID) == [], f"{tuzatishlar(E_ID)}")
_tb0 = tuzatishlar(EB_ID)
for _q in ("bonus_amount=inf", "bonus_amount=1000"):
    r = req("post", f"/api/employees/{EB_ID}/monthly-adjustment?year=2026&month=9&{_q}")
    check(f"E15 begona hodim ({_q}) → {r.status_code} (404 shart)",
          r.status_code == 404 and tuzatishlar(EB_ID) == _tb0, r.text[:120])
r = req("post", f"{_U}?year=2026&month=9&bonus_amount=50000&bonus_reason=Qayta")
r2 = req("get", "/debts")
check(f"E16 bonus bilan /debts → {r2.status_code} (200 shart)",
      r.status_code == 200 and r2.status_code == 200, r2.text[:120])

# ══════════════════════════════════════════════════════════════
section("F. Oylik qarzini yopish — POST /api/obligations/employee/{id}/close")
# ══════════════════════════════════════════════════════════════
_F = f"/api/obligations/employee/{E_ID}/close"
_a0 = avanslar(E_ID)
r = req("post", f"{_F}?year=2026&month=8&amount=120000")        # debts.html 432
_a = avanslar(E_ID)
check(f"F1 UI tanasi → {r.status_code} (200 shart), success",
      r.status_code == 200 and (r.json() or {}).get("success") is True, r.text[:140])
check("F2 avans yozuvi 120 000, avgust oyiga", len(_a) == len(_a0) + 1
      and _a[-1][0] == 120_000 and _a[-1][1].startswith("2026-08"), f"{_a[-1:]}")
_a0 = avanslar(E_ID)
for _y, _m, _v in (("2026", "13", "1000"), ("2026", "0", "1000"), ("1999", "8", "1000"),
                   ("2101", "8", "1000"), ("abc", "8", "1000"), ("2026", "8", "inf"),
                   ("2026", "8", "nan"), ("2026", "8", "-5"), ("2026", "8", "0"),
                   ("2026", "8", "1e20"), ("2026", "8", "abc"), ("2026", "8", "")):
    r = req("post", f"{_F}?year={_y}&month={_m}&amount={_v}")
    check(f"F3 year={_y} month={_m} amount={_v!r} → {r.status_code} (400 shart)",
          r.status_code == 400 and avanslar(E_ID) == _a0, f"{r.text[:100]}")
r = req("post", f"{_F}?year=2026&month=8")
check(f"F4 amount YO'Q → {r.status_code} (400 shart)",
      r.status_code == 400 and avanslar(E_ID) == _a0, r.text[:120])
_ab0 = avanslar(EB_ID)
r = req("post", f"/api/obligations/employee/{EB_ID}/close?year=2026&month=8&amount=inf")
check(f"F5 begona hodim + yomon summa → {r.status_code} (404 shart)",
      r.status_code == 404 and avanslar(EB_ID) == _ab0, r.text[:120])

# ══════════════════════════════════════════════════════════════
section("G. Ta'minotchiga to'lov — POST /api/suppliers/{id}/payment")
# ══════════════════════════════════════════════════════════════
_G = f"/api/suppliers/{S_ID}/payment"
# suppliers.html 906 / supplier_receive.html 518 — AYNAN shu tana
r = req("post", _G, json={"supplier_id": S_ID, "amount": 100_000, "confirm_overpay": False})
check(f"G1 UI tanasi → {r.status_code} (200 shart)", r.status_code == 200, r.text[:160])
check("G2 to'lov 100 000 yozildi, qarz 400 000",
      sup_tolovlar(S_ID) == [(100_000, None)] and yaqin((r.json() or {}).get("debt"), 400_000),
      f"{sup_tolovlar(S_ID)} | {r.text[:120]}")
_s0 = sup_tolovlar(S_ID)
r = req("post", _G, json={"supplier_id": S_ID, "amount": 900_000, "confirm_overpay": False})
_d = detail(r)
check(f"G3 qarzdan ko'p (900 000) → {r.status_code} (409 shart), detail.type saqlangan",
      r.status_code == 409 and isinstance(_d, dict) and _d.get("type") == "overpayment_warning",
      r.text[:160])
check("G4 409 da hech narsa yozilmadi", sup_tolovlar(S_ID) == _s0, f"{sup_tolovlar(S_ID)}")
_bad = [
    '{"supplier_id": %d, "amount": Infinity}',
    '{"supplier_id": %d, "amount": Infinity, "confirm_overpay": true}',
    '{"supplier_id": %d, "amount": -Infinity, "confirm_overpay": true}',
    '{"supplier_id": %d, "amount": NaN, "confirm_overpay": true}',
    '{"supplier_id": %d, "amount": true}',
    '{"supplier_id": %d, "amount": "5000"}',
    '{"supplier_id": %d, "amount": 1e20, "confirm_overpay": true}',
    '{"supplier_id": %d, "amount": 10000000000, "confirm_overpay": true}',
    '{"supplier_id": %d, "amount": 0}',
    '{"supplier_id": %d, "amount": -5}',
    '{"supplier_id": %d}',
    '{"supplier_id": %d, "amount": null}',
    '{"supplier_id": %d, "amount": 1000, "confirm_overpay": "ha"}',
    '{"supplier_id": %d, "amount": 1000, "confirm_overpay": 1}',
    '{"supplier_id": %d, "amount": 1000, "notes": 5}',
    '{"supplier_id": %d, "amount": 1000, "foo": 1}',
    '{"supplier_id": %d, "amount": 1000, "paid_by": "boshqa"}',
]
for _b in _bad:
    _t = _b % S_ID
    r = jtana(_G, _t)
    check(f"G5 {_t[:70]} → {r.status_code} (400 shart), yozilmadi",
          r.status_code == 400 and sup_tolovlar(S_ID) == _s0, f"{r.text[:100]} | {sup_tolovlar(S_ID)}")
for _t in ('{"supplier_id": "abc", "amount": 1000}', '{"supplier_id": true, "amount": 1000}',
           '{"supplier_id": 0, "amount": 1000}'):
    r = jtana(_G, _t)
    check(f"G6 {_t[:60]} → {r.status_code} (400 shart), yozilmadi",
          r.status_code == 400 and sup_tolovlar(S_ID) == _s0, f"{r.text[:100]}")
# Obyekt bo'lmagan tana — FastAPI `dict = Body(...)` ning o'zi 422 bilan rad
# etadi (17b dagi barcha xom-dict marshrutlar bilan bir xil); muhimi —
# hech narsa yozilmaydi va 500 yo'q.
for _t in ('[1, 2]', '"matn"', 'null'):
    r = jtana(_G, _t)
    check(f"G6b obyekt emas: {_t} → {r.status_code} (400/422 shart), yozilmadi",
          r.status_code in (400, 422) and sup_tolovlar(S_ID) == _s0, f"{r.text[:100]}")
r = jtana(_G, '{"supplier_id": %d, "amount": 1000, "notes": "%s"}' % (S_ID, "q" * 10_001))
check(f"G7 izoh 10 001 belgi → {r.status_code} (400 shart)",
      r.status_code == 400 and sup_tolovlar(S_ID) == _s0, r.text[:120])
r = req("post", _G, json={"supplier_id": S_ID, "amount": 900_000, "confirm_overpay": True})
check(f"G8 ortiqcha to'lov TASDIQLANDI → {r.status_code} (200 shart)", r.status_code == 200,
      r.text[:140])
check("G9 900 000 yozildi", sup_tolovlar(S_ID)[-1] == (900_000, None), f"{sup_tolovlar(S_ID)}")
_s2, _sb = sup_tolovlar(S2_ID), sup_tolovlar(SB_ID)
r = req("post", f"/api/suppliers/{S2_ID}/payment",
        json={"supplier_id": SB_ID, "amount": 12_345, "notes": "yo'l id si"})
check(f"G10 tanada BEGONA supplier_id → {r.status_code}; to'lov YO'L dagi ta'minotchiga yozildi",
      r.status_code == 200 and sup_tolovlar(S2_ID) == _s2 + [(12_345, "yo'l id si")]
      and sup_tolovlar(SB_ID) == _sb, f"{r.text[:100]} | {sup_tolovlar(S2_ID)} | {sup_tolovlar(SB_ID)}")
r = req("post", f"/api/suppliers/{S2_ID}/payment", json={"amount": 2_000})
check(f"G11 supplier_id tanada YO'Q → {r.status_code} (200 shart — ixtiyoriy)",
      r.status_code == 200 and sup_tolovlar(S2_ID)[-1] == (2_000, None), r.text[:120])
_sb = sup_tolovlar(SB_ID)
for _t in ('{"amount": Infinity, "confirm_overpay": true}', '{"amount": 1000}'):
    r = jtana(f"/api/suppliers/{SB_ID}/payment", _t)
    check(f"G12 begona ta'minotchi ({_t[:40]}) → {r.status_code} (404 shart — egalik BIRINCHI)",
          r.status_code == 404 and sup_tolovlar(SB_ID) == _sb, r.text[:120])
_bad_pages = []
for _u in ("/suppliers", "/api/suppliers", "/debts", "/api/suppliers/debt-total",
           f"/api/suppliers/{S_ID}/history", "/suppliers/receive"):
    _rr = req("get", _u)
    if _rr.status_code not in (200, 404):
        _bad_pages.append(f"{_u}={_rr.status_code}")
check("G13 ta'minotchi/qarz sahifalari buzilmagan", not _bad_pages, f"{_bad_pages}")

# ══════════════════════════════════════════════════════════════
section("H. Ildiz — marshrutni chetlab (crud / services)")
# ══════════════════════════════════════════════════════════════
_qs = _yordamchi("_query_son")
_qb = _yordamchi("_query_butun")


def _xato(fn, *a, **kw):
    """ValueError ko'tarsa True; yordamchi yo'q yoki boshqacha — False."""
    if fn is None:
        return False
    try:
        fn(*a, **kw)
    except ValueError:
        return True
    except Exception:
        return False
    return False


def _qiymat(fn, *a, **kw):
    if fn is None:
        return "YORDAMCHI YO'Q"
    try:
        return fn(*a, **kw)
    except Exception as e:
        return f"ISTISNO {type(e).__name__}"


# "1_0" — Python `float()` uni 10 deb o'qiydi; KICHIK qiymat, chegara (100)
# uni yashirmaydi (mutatsiya M6: naqsh o'rniga oddiy `float()`).
for _v in ("inf", "Infinity", "nan", "true", "12abc", "1_000", "1_0", " 1_0 ", "0x10", "1e", float("inf"),
           float("nan"), True, "-5", -5.0):
    check(f"H1 _query_son({_v!r}) — rad etiladi",
          _xato(_qs, "x", _v, bosh_mumkin=False, musbat=True, chegara=100.0))
for _v, _k in (("12", 12.0), (" 12.5 ", 12.5), ("1e1", 10.0), (".5", 0.5), (7, 7.0)):
    check(f"H2 _query_son({_v!r}) = {_k}",
          _qiymat(_qs, "x", _v, bosh_mumkin=False, musbat=True, chegara=100.0) == _k)
check("H3 _query_son(bo'sh, bosh_mumkin=True) = None",
      _qiymat(_qs, "x", "", bosh_mumkin=True, musbat=False, chegara=1.0) is None)
check("H4 _query_son(101 > chegara 100) — rad",
      _xato(_qs, "x", "101", bosh_mumkin=False, musbat=True, chegara=100.0))
for _v in ("13", "0", "abc", "9.5", "", True, "+", "1" * 13):
    check(f"H5 _query_butun({_v!r}, 1..12) — rad", _xato(_qb, "month", _v, 1, 12))
for _v, _k in (("12", 12), (" 1 ", 1), (6, 6)):
    check(f"H6 _query_butun({_v!r}) = {_k}", _qiymat(_qb, "month", _v, 1, 12) == _k)

_a0 = avanslar(E_ID)
_ok = False
try:
    crud.create_employee_advance(db, E_ID, float("inf"), "ildiz")
except ValueError:
    _ok = True
except Exception:
    _ok = False
db.rollback()
check("H7 crud.create_employee_advance(inf) — ValueError, yozilmadi",
      _ok and avanslar(E_ID) == _a0, f"{avanslar(E_ID)[-1:]}")
for _v in (-5.0, 0.0, 1e20, True):
    _ok = False
    try:
        crud.create_employee_advance(db, E_ID, _v, "ildiz")
    except ValueError:
        _ok = True
    except Exception:
        _ok = False
    db.rollback()
    check(f"H8 crud.create_employee_advance({_v!r}) — ValueError, yozilmadi",
          _ok and avanslar(E_ID) == _a0)
_ok = False
try:
    crud.create_employee_advance(db, E_ID, 1000.0, "ildiz", adv_date="2026-13-45")
except ValueError:
    _ok = True
except Exception:
    _ok = False
db.rollback()
check("H9 crud.create_employee_advance(sana 2026-13-45) — ValueError",
      _ok and avanslar(E_ID) == _a0)
_ok = False
try:
    _r9 = crud.create_employee_advance(db, E_ID, 1000.0, "ildiz nazorat",
                                       adv_date=datetime(2026, 9, 3))
    _ok = _r9 is not None
except Exception:
    _ok = False
db.rollback()
check("H10 NAZORAT: crud.create_employee_advance(1000, datetime) — yozildi",
      _ok and avanslar(E_ID)[-1] == (1000.0, "2026-09-03", "ildiz nazorat"),
      f"{avanslar(E_ID)[-1:]}")

_t0 = tuzatishlar(E_ID)
for _args, _lbl in (((2026, 9, -5.0, None, None, None), "kamaytirish -5"),
                    ((2026, 9, None, None, float("inf"), None), "bonus inf"),
                    ((2026, 9, None, None, float("nan"), None), "bonus nan"),
                    ((2026, 13, None, None, 1000.0, None), "13-oy"),
                    ((1999, 9, None, None, 1000.0, None), "1999-yil"),
                    ((2026, True, None, None, 1000.0, None), "oy = True")):
    _ok = False
    try:
        crud.set_employee_monthly_adjustment(db, E_ID, *_args)
    except ValueError:
        _ok = True
    except Exception:
        _ok = False
    db.rollback()
    check(f"H11 crud.set_employee_monthly_adjustment({_lbl}) — ValueError, o'zgarmadi",
          _ok and tuzatishlar(E_ID) == _t0, f"{tuzatishlar(E_ID)}")

_s0 = sup_tolovlar(S_ID)
for _amt, _lbl in ((float("inf"), "inf"), (float("nan"), "nan"), (True, "True"),
                   (1e20, "1e20"), (-5.0, "-5")):
    _ok = False
    try:
        crud.create_supplier_payment(
            db, SimpleNamespace(supplier_id=S_ID, amount=_amt, notes=None,
                                confirm_overpay=True), paid_by="ildiz", company_id=1)
    except ValueError:
        _ok = True
    except Exception:
        _ok = False
    db.rollback()
    check(f"H12 crud.create_supplier_payment(amount={_lbl}) — ValueError, yozilmadi",
          _ok and sup_tolovlar(S_ID) == _s0, f"{sup_tolovlar(S_ID)}")
_ok = False
try:
    _p = crud.create_supplier_payment(
        db, schemas.SupplierPaymentCreate(supplier_id=S_ID, amount=3_333, notes="xarid bilan",
                                          confirm_overpay=True),
        paid_by="ildiz", company_id=1)
    _ok = _p is not None
except Exception:
    _ok = False
db.rollback()
check("H13 NAZORAT: pydantic tana (xarid bilan birga to'lov yo'li, main.py) — yozildi",
      _ok and sup_tolovlar(S_ID)[-1] == (3_333, "xarid bilan"), f"{sup_tolovlar(S_ID)[-1:]}")

_a0 = avanslar(E_ID)
for _args, _lbl in (((2026, 9, float("inf")), "summa inf"), ((2026, 9, -1.0), "summa -1"),
                    ((2026, 9, 1e20), "summa 1e20")):
    _ok = False
    try:
        services.close_employee_debt(db, E_ID, *_args, paid_by="ildiz")
    except ValueError:
        _ok = True
    except Exception:
        _ok = False
    db.rollback()
    check(f"H14 services.close_employee_debt({_lbl}) — ValueError, avans yozilmadi",
          _ok and avanslar(E_ID) == _a0, f"{avanslar(E_ID)[-1:]}")

_ly = _yordamchi("_loyiha_tolangan_yangila")
db.expire_all()
_prj = db.get(Project, P_ID)
_prj.total_paid = 1
db.flush()
try:
    if _ly:
        _ly(db, _prj)
    db.commit()
except Exception:
    db.rollback()
check("H15 crud._loyiha_tolangan_yangila — total_paid haqiqiy to'lovlarga qaytdi",
      _ly is not None and yaqin(tolangan(P_ID), tolov_yigindi(P_ID)),
      f"{tolangan(P_ID)} / {tolov_yigindi(P_ID)}")
try:
    if _ly:
        _ly(db, None)
    _none_ok = _ly is not None
except Exception:
    _none_ok = False
db.rollback()
check("H16 crud._loyiha_tolangan_yangila(None) — jim o'tadi (loyihasiz buyurtma)", _none_ok)

# ══════════════════════════════════════════════════════════════
section("I. Statik")
# ══════════════════════════════════════════════════════════════
with open(os.path.join(ROOT, "templates", "projects.html"), encoding="utf-8") as f:
    _proj = f.read()
for _t in ("payModal", "savePayment", "showPayModal", "/payment?amount", "proj-pay-save-btn",
           "isSavingProjPayment"):
    check(f"I1 projects.html da '{_t}' YO'Q", _t not in _proj)

_rules = {}
try:
    _rules = crud._val_rules().get("SupplierPayment", {})
except Exception:
    _rules = {}
_schema = set(schemas.SupplierPaymentCreate.model_fields)
check(f"I2 SupplierPayment qoidalari = sxema maydonlari ({sorted(_schema)})",
      set(_rules) == _schema, f"{sorted(_rules)}")
check("I3 SupplierPayment majburiy: amount",
      getattr(crud, "_VAL_MAJBURIY", {}).get("SupplierPayment", {}).keys() == {"amount"})
for _fn in ("suppliers.html", "supplier_receive.html"):
    with open(os.path.join(ROOT, "templates", _fn), encoding="utf-8") as f:
        _html = f.read()
    _m = re.findall(r"/payment`,\s*\{[\s\S]{0,200}?JSON\.stringify\(\{([^}]*)\}\)", _html)
    _keys = set()
    for _blk in _m:
        for _part in _blk.split(","):
            _k = _part.split(":")[0].strip()
            if _k:
                _keys.add(_k)
    check(f"I4 {_fn} to'lov tanasi kalitlari ({sorted(_keys)}) qoidalarda",
          bool(_keys) and _keys <= set(_rules), f"{sorted(_keys)} / {sorted(_rules)}")


def _param_turi(fn, nom):
    try:
        return str(inspect.signature(fn).parameters[nom].annotation)
    except Exception:
        return "YO'Q"


for _fn, _nomlar in ((main.api_create_employee_advance, ("amount",)),
                     (main.api_set_employee_adjustment,
                      ("year", "month", "reduction_amount", "bonus_amount")),
                     (main.api_close_employee_debt, ("year", "month", "amount"))):
    for _nom in _nomlar:
        _t = _param_turi(_fn, _nom)
        check(f"I5 {_fn.__name__}({_nom}) MATN sifatida olinadi ({_t})",
              "str" in _t and "float" not in _t and "int" not in _t.replace("Optional", ""))
check("I6 api_add_payment 'amount' qabul qilmaydi (yo'l olib tashlangan)",
      "amount" not in inspect.signature(main.api_add_payment).parameters)
check("I7 api_supplier_payment tanasi xom dict (pydantic emas)",
      "dict" in _param_turi(main.api_supplier_payment, "data"))
for _f in ("create_payment", "delete_payment", "mark_refunded", "create_delivery",
           "delete_order", "permanent_delete_order"):
    try:
        _src = inspect.getsource(getattr(crud, _f))
    except Exception:
        _src = ""
    check(f"I8 crud.{_f} total_paid ni yagona yordamchi bilan yangilaydi",
          "_loyiha_tolangan_yangila(" in _src)
try:
    _cr = inspect.getsource(crud)
except Exception:
    _cr = ""
check("I9 crud da total_paid qo'lda yig'ilmaydi (eski `project.total_paid = sum(` yo'q)",
      "project.total_paid = sum(" not in _cr)
with open(os.path.join(ROOT, "templates", "kpi.html"), encoding="utf-8") as f:
    _kpi = f.read()
check("I10 kpi.html avans so'rovi (amount, notes, adv_date) — marshrut parametrlari bilan mos",
      "/advance?amount=${amount}&notes=" in _kpi and "&adv_date=${dateVal}" in _kpi
      and {"amount", "notes", "adv_date"} <= set(
          inspect.signature(main.api_create_employee_advance).parameters))
with open(os.path.join(ROOT, "templates", "debts.html"), encoding="utf-8") as f:
    _debts = f.read()
check("I11 debts.html oylik yopish so'rovi (year, month, amount) — marshrut bilan mos",
      "/close?year=${y}&month=${m}&amount=${amount}" in _debts
      and {"year", "month", "amount"} <= set(
          inspect.signature(main.api_close_employee_debt).parameters))

# Migratsiya modul yuklanganda (ishga tushishda) CHAQIRILADI — funksiyaning
# o'zi C bo'limida sinaladi, bu yerda esa chaqiruv joyi (mutatsiya M22:
# chaqiruv olib tashlansa jonli bazadagi eski farqlar hech qachon tuzalmaydi).
try:
    import ast as _ast
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
        _tree = _ast.parse(f.read())
    _yuqori = False
    for _node in _tree.body:            # faqat MODUL darajasi (def ichi emas)
        for _sub in _ast.walk(_node):
            if isinstance(_node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                break
            if (isinstance(_sub, _ast.Call) and isinstance(_sub.func, _ast.Name)
                    and _sub.func.id == "_migrate_loyiha_tolangan_sinxron"):
                _yuqori = True
except Exception:
    _yuqori = False
check("I12 main.py: _migrate_loyiha_tolangan_sinxron() MODUL darajasida chaqiriladi", _yuqori)

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 62)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print("=" * 62)
if FAILED:
    print("Yiqilganlar:")
    for x in FAILED:
        print("  -", x)
db.close()
sys.exit(1 if FAIL else 0)
