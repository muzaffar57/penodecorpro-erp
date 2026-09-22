#!/usr/bin/env python3
"""
test_loy_query.py — 17d-band: so'rov qatoridagi LOY miqdori, doimiy
majburiyat va eskirgan marshrutlar.

NIMA UCHUN KERAK (2026-09-21)
-----------------------------
Hammasi O'LCHANGAN (`work/probe17d.py`, har prob alohida toza bazada;
uzun kod — jonli sinov saytida), asl kod = kech19.

1) Buyurtma loy miqdori URL da keladigan 7 marshrut (`PUT /loy`,
   `/coating-notify`, `/ready`, `mark-all-ready`, `DELETE`, `PUT` va `POST`
   buyurtma) FastAPI `float` bilan `inf`/`nan`/`-5`/`1e20`/`1_0` ni
   o'tkazardi: loy xomashyosi qoldig'i −∞ SAQLANARDI va buyurtma kartasi,
   "Qarzdorlar", biznes-salomatlik 500; manfiy loy omborga olinganidan KO'P
   qaytarardi (5 kg olingan → 7.5 qaytdi); `PUT` buyurtma `nan` bilan
   detallarni saqlab bo'lib 500 berardi (yarim yozuv).
2) Tanadagi `loy_kg`: `Infinity` → −∞, `true` → 1 kg, `"5"` → 5 kg.
3) Yaratishda loy yetishmovchiligi tekshiruvi faqat so'rov qatorini
   ko'rardi, UI esa tanaga yuboradi — ogohlantirish UI da hech qachon
   chiqmasdi. Endi bitta samarali reja (tana, bo'lmasa so'rov qatori).
4) Qoralama buyurtma `POST /ready` bilan "Tayyor" bo'lardi (xomashyosiz);
   `mark-all-ready` BARCHA qoralamalarni "Tayyor" qilardi → 410.
5) `coating-notify-new` tanasi `pass` edi (har narsaga 200 null) → 410.
6) Doimiy majburiyat: `inf` summa "Qarzdorlar" ni buzardi, kun 0/−3/99999,
   `debts.html` uzun nomdan 30 belgidan uzun kod yasab 500 olardi (JONLI).
7) `/api/finance/expense` (hech bir sahifa chaqirmaydi): 13-oy, `Infinity`
   → `/api/finance/history` 500 → 410.
8) UMUMIY: sxema rad etgan `Infinity` 422 o'rniga 500 berardi (javobda
   `inf` JSON ga yozilmasdi) — `main.xavfsiz_validatsiya_handler`.

QAMROV
------
A. `PUT /api/orders/{id}/loy` — yomon qiymatlar 400, HOLAT o'zgarmagan;
   to'g'ri qiymatlar aniq ombor farqi bilan
B. `POST /coating-notify` — 400 / 0 hech narsa / musbat reja
C. `POST /ready` — 400, bo'sh = reja bo'yicha, haqiqiy loy, QORALAMA rad
D. `DELETE /api/orders/{id}` — 400 da buyurtma va ombor joyida; to'g'ri
   qiymatda aniq qaytarish
E. `PUT /api/orders/{id}` — 400 da DETALLAR ham o'zgarmagan
F. `POST /api/orders` — so'rov qatori va tana; samarali reja; ogohlantirish
G. 410 marshrutlar — hech narsa yozilmaydi (qoralama qoralama qoladi)
H. Doimiy majburiyat — yomon qiymatlar 400, to'g'ri 200, yangilash
I. Korxona: begona buyurtma yomon qiymat bilan ham 404 (oracle yo'q)
J. Ildiz: `crud.update_order_loy`, `services.complete_order`,
   `services.set_recurring_obligation`, `crud.create_order`, yordamchilar
K. Statik: marshrut turlari, 410 tanalari, sxema, UI (`debts.html` kod
   yasash — node bilan bajariladi, `orders.html` sabab)
L. Sxema xatosi (422): tanada `Infinity`/`NaN` bo'lsa ham javob 422 (asl
   kodda FastAPI 422 javobining o'zi JSON ga yozilmay 500 berardi — har
   qanday marshrutda, masalan `agreed_amount`, xarajat `amount: -Infinity`).
   ⚠ Xarajat `amount: +Infinity` bu yerda EMAS — 17e-bandda tuzatildi
   (`tools/test_xarajat_query.py`). 17f da transport xarajati ham xom JSON
   ni o'zi tekshirib 400 beradigan bo'ldi (`tools/test_pul_query.py`), shuning
   uchun 422 vositasi endi `PUT /api/masters/{id}/kpi` (`MasterKpiUpdate`,
   `ge=0, le=100` — `-Infinity`, `NaN`, `+Infinity` ni pydantic rad etadi,
   tana handlerdan OLDIN tekshiriladi; mavjud bo'lmagan usta id bilan — agar
   so'rov handlerga yetsa 404 chiqib tekshiruv yiqiladi).

ISHLATISH
---------
    python tools/test_loy_query.py
    TENANT_FILTER=1 python tools/test_loy_query.py

Asl kodga qarshi ham QULAMAYDI (mutatsiya uchun): yangi yordamchilarga
murojaat `getattr` bilan, ildiz chaqiruvlari `try/except` bilan, HTTP
istisnolar 599 ga aylantiriladi.

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import json
import shutil
import tempfile
import inspect
import subprocess
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "loy_query_test.db")
_SNAP = _DB + ".nusxa"
for _f in (_DB, _SNAP):
    if os.path.exists(_f):
        os.remove(_f)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, schemas, services           # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Inventory, Recipe, RecipeIngredient,
    RecurringObligation, MonthlyExpense, ExpenseTransaction,
)
from fastapi.testclient import TestClient          # noqa: E402

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
        print(f"  ✗ {label}   {str(detail)[:300]}")


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
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="Test Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "LQ_admin", "Parol123!", UserRole.ADMIN, "LQ Admin",
                     company_id=1)
    auth.create_user(_db, "LQ_admin_b", "Parol123!", UserRole.ADMIN, "LQ Admin B",
                     company_id=2)

SEM = Inventory(company_id=1, item_name="LQ_SEMENT", unit="kg", stock_quantity=1000,
                price_per_unit=1000, min_stock=0)
_db.add(SEM)
_db.commit()
REC = Recipe(company_id=1, name="LQ_RETSEPT", batch_size_kg=100)
_db.add(REC)
_db.commit()
# 100 kg loy uchun 50 kg sement → 1 kg loy = 0.5 kg sement
_db.add(RecipeIngredient(recipe_id=REC.id, inventory_id=SEM.id, quantity_kg=50))
PRJ = Project(company_id=1, client_name="LQ Mijoz", project_name="LQ loyiha",
              total_budget=0, total_paid=0)
_db.add(PRJ)
_db.commit()
SEM_ID, R_ID, P_ID = SEM.id, REC.id, PRJ.id


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
        return getattr(client, method)(url, **kw)
    except Exception as e:          # pragma: no cover — himoya qatlami
        return _R599(e)


def tana(nom, loy=10, draft=False):
    return {"project_id": P_ID, "order_type": "product", "recipe_id": R_ID,
            "is_draft": draft, "loy_kg": loy,
            "items": [{"name": nom, "category": "panel", "width": 100,
                       "thickness": 10, "length": 100, "quantity": 10,
                       "unit_price": 100000, "is_coated": True}]}


C0 = login("LQ_admin")
with contextlib.redirect_stdout(_quiet):
    _r1 = C0.post("/api/orders?confirm_shortage=true", json=tana("LQ_ASOSIY"))
    _r2 = C0.post("/api/orders?confirm_shortage=true", json=tana("LQ_QORALAMA", draft=True))
assert _r1.status_code == 200, _r1.text
assert _r2.status_code == 200, _r2.text
O_ID, OD_ID = _r1.json()["id"], _r2.json()["id"]
_db.close()

# IZOLYATSIYA (17.1 saboqi): fikstura bazasining nusxasi — har bir prob
# oldidan tiklanadi. Aks holda bitta o'tib ketgan `inf` keyingi hamma
# problarni 500 qilib, YOLG'ON natija beradi.
engine.dispose()
shutil.copy(_DB, _SNAP)


def tikla():
    engine.dispose()
    shutil.copy(_SNAP, _DB)


def holat():
    """Tekshiriladigan to'liq holat: ombor, buyurtmalar (detallari bilan),
    majburiyatlar, oylik xarajat va tranzaksiyalar."""
    d = SessionLocal()
    try:
        s = d.get(Inventory, SEM_ID)
        buy = []
        for o in d.query(Order).order_by(Order.id).all():
            items = [(i.name, i.quantity) for i in
                     d.query(OrderItem).filter(OrderItem.order_id == o.id).order_by(OrderItem.id)]
            buy.append((o.id, o.status.value if o.status else None, o.planned_loy_kg,
                        o.actual_loy_kg, bool(o.is_deleted), o.notes, tuple(items)))
        return {
            "sem": s.stock_quantity if s else None,
            "buy": buy,
            "obl": [(x.category, x.label, str(x.monthly_target), x.due_day, x.icon)
                    for x in d.query(RecurringObligation).order_by(RecurringObligation.id)],
            "me": [(x.year, x.month, str(x.arenda)) for x in d.query(MonthlyExpense).all()],
            "et": [(str(x.date), x.category, str(x.amount)) for x in
                   d.query(ExpenseTransaction).order_by(ExpenseTransaction.id)],
        }
    finally:
        d.close()


def buyurtma(oid):
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        if not o:
            return None
        return SimpleNamespace(status=o.status.value if o.status else None,
                               planned=o.planned_loy_kg, actual=o.actual_loy_kg,
                               deleted=bool(o.is_deleted))
    finally:
        d.close()


def sement():
    d = SessionLocal()
    try:
        return float(d.get(Inventory, SEM_ID).stock_quantity)
    finally:
        d.close()


SAHIFALAR = ["/api/orders", f"/api/orders/{O_ID}", f"/api/orders/{O_ID}/planned-loy",
             "/api/loy-stock", "/api/obligations/recurring", "/debts",
             "/api/reports/business-health", "/api/finance/history", "/orders"]


def sahifalar_ok(c):
    yomon = []
    for u in SAHIFALAR:
        r = req(c, "get", u)
        if r.status_code >= 500:
            yomon.append(f"{u}:{r.status_code}")
    return yomon


def rad(label, method, url, kutilgan=(400,), client_user="LQ_admin", **kw):
    """Yomon so'rov: kutilgan status VA holat bayt-bayt o'zgarmagan VA
    sahifalar buzilmagan. Har prob toza nusxadan."""
    tikla()
    c = login(client_user)
    h0 = holat()
    r = req(c, method, url, **kw)
    h1 = holat()
    check(f"{label} → {'/'.join(map(str, kutilgan))}", r.status_code in kutilgan,
          f"{r.status_code} {getattr(r, 'text', '')[:150]}")
    farq = {k: (h0[k], h1[k]) for k in h0 if h0[k] != h1[k]}
    check(f"{label}: holat o'zgarmagan", not farq, farq)
    return r


YOMON_MAJBURIY = ["inf", "-inf", "Infinity", "nan", "NaN", "-5", "-0.5", "1e20", "1e13",
                  "true", "1_0", "abc", "0x10", "12abc", ""]
YOMON_IXTIYORIY = [v for v in YOMON_MAJBURIY if v != ""]


# ══════════════════════════════════════════════════════════════
section("A. PUT /api/orders/{id}/loy — loy rejasi")
# ══════════════════════════════════════════════════════════════
for v in YOMON_MAJBURIY:
    rad(f"A PUT /loy loy_kg={v!r}", "put", f"/api/orders/{O_ID}/loy?loy_kg={v}")
rad("A PUT /loy loy_kg umuman yo'q", "put", f"/api/orders/{O_ID}/loy",
    kutilgan=(400, 422))

for v, kutil_sem in [("0", 1000.0), ("5", 997.5), ("12.5", 993.75), ("1e3", 500.0)]:
    tikla()
    c = login("LQ_admin")
    r = req(c, "put", f"/api/orders/{O_ID}/loy?loy_kg={v}")
    b = buyurtma(O_ID)
    check(f"A PUT /loy loy_kg={v} → 200, reja {float(v)}, sement {kutil_sem}",
          r.status_code == 200 and b is not None and yaqin(b.planned, float(v))
          and yaqin(sement(), kutil_sem),
          f"{r.status_code} {getattr(r, 'text', '')[:120]} reja={b and b.planned} sem={sement()}")
check("A sahifalar to'g'ri qiymatdan keyin 200", not sahifalar_ok(login("LQ_admin")),
      sahifalar_ok(login("LQ_admin")))

# Qoralama: ombor TEGILMAYDI (avvalgi xatti-harakat saqlanadi)
tikla()
r = req(login("LQ_admin"), "put", f"/api/orders/{OD_ID}/loy?loy_kg=40")
check("A qoralamada reja o'zgaradi, ombor tegilmaydi",
      r.status_code == 200 and yaqin(buyurtma(OD_ID).planned, 40) and yaqin(sement(), 995.0),
      f"{r.status_code} sem={sement()}")

# ══════════════════════════════════════════════════════════════
section("B. POST /api/orders/{id}/coating-notify")
# ══════════════════════════════════════════════════════════════
for v in YOMON_MAJBURIY:
    rad(f"B coating-notify loy_kg={v!r}", "post",
        f"/api/orders/{O_ID}/coating-notify?loy_kg={v}")
tikla()
c = login("LQ_admin")
h0 = holat()
r = req(c, "post", f"/api/orders/{O_ID}/coating-notify?loy_kg=0")
check("B loy_kg=0 → 200 va hech narsa o'zgarmaydi (avvalgidek)",
      r.status_code == 200 and holat() == h0, f"{r.status_code}")
tikla()
c = login("LQ_admin")
r = req(c, "post", f"/api/orders/{O_ID}/coating-notify?loy_kg=7.5")
check("B loy_kg=7.5 → 200, reja 7.5, ombor TEGILMAYDI (faqat xabar)",
      r.status_code == 200 and yaqin(buyurtma(O_ID).planned, 7.5) and yaqin(sement(), 995.0),
      f"{r.status_code} reja={buyurtma(O_ID).planned} sem={sement()}")
check("B sahifalar 200", not sahifalar_ok(c), sahifalar_ok(c))

# ══════════════════════════════════════════════════════════════
section("C. POST /api/orders/{id}/ready — haqiqiy loy va qoralama")
# ══════════════════════════════════════════════════════════════
for v in YOMON_IXTIYORIY:
    r = rad(f"C ready loy_kg={v!r}", "post", f"/api/orders/{O_ID}/ready?loy_kg={v}")
    if v == "-5":
        try:
            det = r.json().get("detail")
        except Exception:
            det = None
        check("C 400 detail — obyekt, `message` matni bor (UI shuni ko'rsatadi)",
              isinstance(det, dict) and isinstance(det.get("message"), str)
              and "loy_kg" in det.get("message", ""), det)

tikla()
c = login("LQ_admin")
r = req(c, "post", f"/api/orders/{O_ID}/ready?loy_kg=")
b = buyurtma(O_ID)
check("C bo'sh loy_kg= → 200, reja bo'yicha (haqiqiy yozilmaydi), ombor o'zgarmaydi",
      r.status_code == 200 and b.status == "ready" and b.actual is None
      and yaqin(sement(), 995.0), f"{r.status_code} {b} sem={sement()}")
tikla()
c = login("LQ_admin")
r = req(c, "post", f"/api/orders/{O_ID}/ready")
check("C loy_kg umuman yo'q → 200, reja bo'yicha",
      r.status_code == 200 and buyurtma(O_ID).status == "ready", f"{r.status_code}")
tikla()
c = login("LQ_admin")
r = req(c, "post", f"/api/orders/{O_ID}/ready?loy_kg=14")
b = buyurtma(O_ID)
check("C loy_kg=14 (reja 10) → 200, haqiqiy 14, qo'shimcha 4 kg → sement −2",
      r.status_code == 200 and yaqin(b.actual, 14) and yaqin(sement(), 993.0),
      f"{r.status_code} {b} sem={sement()}")
check("C sahifalar 200", not sahifalar_ok(c), sahifalar_ok(c))
tikla()
c = login("LQ_admin")
r = req(c, "post", f"/api/orders/{O_ID}/ready?loy_kg=0")
check("C loy_kg=0 → 200 (\"kiritilmagan\" — avvalgidek, reja bo'yicha)",
      r.status_code == 200 and buyurtma(O_ID).status == "ready", f"{r.status_code}")

for q in ["", "?loy_kg=5"]:
    r = rad(f"C QORALAMA ready{q}", "post", f"/api/orders/{OD_ID}/ready{q}")
    try:
        msg = (r.json().get("detail") or {}).get("message", "")
    except Exception:
        msg = ""
    check(f"C QORALAMA ready{q}: sabab \"jarayonga oling\"", "jarayonga" in msg, msg)

# ══════════════════════════════════════════════════════════════
section("D. DELETE /api/orders/{id} — actual_loy_kg")
# ══════════════════════════════════════════════════════════════
for v in YOMON_IXTIYORIY:
    rad(f"D DELETE actual_loy_kg={v!r}", "delete",
        f"/api/orders/{O_ID}?actual_loy_kg={v}")
for q, kutil in [("", 1000.0), ("?actual_loy_kg=", 1000.0), ("?actual_loy_kg=4", 998.0),
                 ("?actual_loy_kg=0", 1000.0), ("?actual_loy_kg=16", 992.0)]:
    tikla()
    c = login("LQ_admin")
    r = req(c, "delete", f"/api/orders/{O_ID}{q}")
    check(f"D DELETE{q or ' (parametrsiz)'} → 200, buyurtma o'chdi, sement {kutil}",
          r.status_code == 200 and buyurtma(O_ID) is None and yaqin(sement(), kutil),
          f"{r.status_code} {getattr(r, 'text', '')[:100]} sem={sement()}")

# ══════════════════════════════════════════════════════════════
section("E. PUT /api/orders/{id} — tahrir (detallar yarim saqlanmasin)")
# ══════════════════════════════════════════════════════════════
for v in YOMON_IXTIYORIY:
    rad(f"E PUT order loy_kg={v!r}", "put",
        f"/api/orders/{O_ID}?loy_kg={v}&confirm_shortage=true",
        json=tana("LQ_TAHRIR_" + v.replace(".", "_")))
tikla()
c = login("LQ_admin")
r = req(c, "put", f"/api/orders/{O_ID}?loy_kg=6&confirm_shortage=true", json=tana("LQ_TAHRIR_OK"))
check("E loy_kg=6 → 200, reja 6, sement +2 (qaytdi)",
      r.status_code == 200 and yaqin(buyurtma(O_ID).planned, 6) and yaqin(sement(), 997.0),
      f"{r.status_code} {getattr(r, 'text', '')[:120]} sem={sement()}")
tikla()
c = login("LQ_admin")
h0 = holat()
r = req(c, "put", f"/api/orders/{O_ID}?confirm_shortage=true", json=tana("LQ_TAHRIR_LOYSIZ"))
check("E loy_kg so'rovda yo'q → 200, reja O'ZGARMAYDI (10)",
      r.status_code == 200 and yaqin(buyurtma(O_ID).planned, 10), f"{r.status_code}")
r = rad("E tanadagi loy_kg Infinity", "put", f"/api/orders/{O_ID}?confirm_shortage=true",
        kutilgan=(400, 422),
        content=json.dumps(tana("LQ_E_INF")).replace('"loy_kg": 10', '"loy_kg": Infinity'),
        headers={"Content-Type": "application/json"})

# ══════════════════════════════════════════════════════════════
section("F. POST /api/orders — so'rov qatori va tana")
# ══════════════════════════════════════════════════════════════
for v in YOMON_IXTIYORIY:
    rad(f"F POST order ?loy_kg={v!r}", "post",
        f"/api/orders?loy_kg={v}&confirm_shortage=true",
        json=tana("LQ_FQ_" + v.replace(".", "_")))
for raw in ["Infinity", "-Infinity", "NaN", "-5", "1e20", "1e13", "true", "false",
            '"5"', '"abc"', "[]", "{}"]:
    rad(f"F POST order TANA loy_kg={raw}", "post", "/api/orders?confirm_shortage=true",
        kutilgan=(400, 422),
        content=json.dumps(tana("LQ_FB_" + raw.strip('"[]{}'))).replace(
            '"loy_kg": 10', f'"loy_kg": {raw}'),
        headers={"Content-Type": "application/json"})


def yangi_buyurtma_id(r):
    try:
        return r.json().get("id")
    except Exception:
        return None


for label, url, body, kutil_reja, kutil_sem in [
        ("tana 8", "/api/orders?confirm_shortage=true", tana("LQ_F1", loy=8), 8.0, 991.0),
        ("tana 0", "/api/orders?confirm_shortage=true", tana("LQ_F2", loy=0), 0.0, 995.0),
        ("tana null", "/api/orders?confirm_shortage=true", tana("LQ_F3", loy=None), 0.0, 995.0),
        ("tana 12.5 (butun ham float)", "/api/orders?confirm_shortage=true",
         tana("LQ_F4", loy=12.5), 12.5, 988.75),
        ("faqat so'rov qatori 6 (tana null)", "/api/orders?loy_kg=6&confirm_shortage=true",
         tana("LQ_F5", loy=None), 6.0, 992.0),
        ("ikkalasi: tana 4 USTUN, so'rov 30", "/api/orders?loy_kg=30&confirm_shortage=true",
         tana("LQ_F6", loy=4), 4.0, 993.0)]:
    tikla()
    c = login("LQ_admin")
    r = req(c, "post", url, json=body)
    oid = yangi_buyurtma_id(r)
    b = buyurtma(oid) if oid else None
    check(f"F {label} → 200, reja {kutil_reja}, sement {kutil_sem}",
          r.status_code == 200 and b is not None and yaqin(b.planned or 0, kutil_reja)
          and yaqin(sement(), kutil_sem),
          f"{r.status_code} {getattr(r, 'text', '')[:120]} reja={b and b.planned} sem={sement()}")

# Loy yetishmovchiligi ogohlantirishi — TANADAGI reja bo'yicha (UI yo'li)
tikla()
c = login("LQ_admin")
h0 = holat()
r = req(c, "post", "/api/orders", json=tana("LQ_F_KAM", loy=5000))
try:
    det = r.json().get("detail") or {}
except Exception:
    det = {}
check("F tanada loy 5000 kg (2500 kg sement kerak, 995 bor) → 409 ogohlantirish",
      r.status_code == 409 and isinstance(det, dict)
      and det.get("type") == "stock_shortage_warning"
      and any("LQ_SEMENT" in s for s in det.get("shortages", [])),
      f"{r.status_code} {det}")
check("F 409 da hech narsa yozilmagan", holat() == h0)
r = req(c, "post", "/api/orders?confirm_shortage=true", json=tana("LQ_F_KAM2", loy=5000))
check("F tasdiqlansa (19-band qarori) → 200, qoldiq manfiyga tushadi",
      r.status_code == 200 and yaqin(sement(), 995.0 - 2500.0), f"{r.status_code} sem={sement()}")

# ══════════════════════════════════════════════════════════════
section("G. 410 — eskirgan / o'chirilgan marshrutlar")
# ══════════════════════════════════════════════════════════════
rad("G coating-notify-new (to'g'ri qiymat bilan ham)", "post",
    f"/api/orders/coating-notify-new?order_id={O_ID}&loy_kg=5", kutilgan=(410,))
rad("G coating-notify-new inf", "post",
    f"/api/orders/coating-notify-new?order_id={O_ID}&loy_kg=inf", kutilgan=(410,))
rad("G coating-notify-new parametrsiz", "post", "/api/orders/coating-notify-new",
    kutilgan=(410,))
rad("G mark-all-ready parametrsiz — qoralama qoralama QOLADI", "post",
    "/api/orders/mark-all-ready", kutilgan=(410,))
rad("G mark-all-ready loy_kg=5", "post", "/api/orders/mark-all-ready?loy_kg=5",
    kutilgan=(410,))
rad("G mark-all-ready loy_kg=inf", "post", "/api/orders/mark-all-ready?loy_kg=inf",
    kutilgan=(410,))
rad("G finance/expense to'g'ri tana bilan", "post", "/api/finance/expense?year=2026&month=9",
    kutilgan=(410,), json={"arenda": 1000})
rad("G finance/expense 13-oy", "post", "/api/finance/expense?year=2026&month=13",
    kutilgan=(410,), json={"arenda": 1000})
rad("G finance/expense Infinity", "post", "/api/finance/expense?year=2026&month=9",
    kutilgan=(410,), content='{"arenda": Infinity}',
    headers={"Content-Type": "application/json"})
r = rad("G finance/expense tanasiz", "post", "/api/finance/expense", kutilgan=(410,))
try:
    check("G 410 detail — matn (sabab)", isinstance(r.json().get("detail"), str), r.text)
except Exception as e:
    check("G 410 detail — matn (sabab)", False, e)
c_anon = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
r = req(c_anon, "post", "/api/finance/expense", follow_redirects=False)
check("G finance/expense avtorizatsiyasiz → 410 EMAS (avval kirish talab qilinadi)",
      r.status_code != 410 and r.status_code < 500, r.status_code)

# ══════════════════════════════════════════════════════════════
section("H. POST /api/obligations/recurring — doimiy majburiyat")
# ══════════════════════════════════════════════════════════════
OBL = "/api/obligations/recurring"
for v in YOMON_MAJBURIY + ["0", "0.0"]:
    rad(f"H monthly_target={v!r}", "post",
        f"{OBL}?category=lq&label=LQ&monthly_target={v}&due_day=5")
rad("H monthly_target yo'q", "post", f"{OBL}?category=lq&label=LQ&due_day=5")
rad("H monthly_target 1e10 (Numeric(12,2) sig'imidan katta)", "post",
    f"{OBL}?category=lq&label=LQ&monthly_target=1e10&due_day=5")
for v in ["0", "-3", "32", "99999", "1_0", "abc", "true", "5.5", "1e1", "%2B", "-"]:
    rad(f"H due_day={v!r}", "post", f"{OBL}?category=lq&label=LQ&monthly_target=1000&due_day={v}")
for q, nom in [("category=" + "k" * 31, "kod 31 belgi"), ("category=", "kod bo'sh"),
               ("category=%20%20", "kod faqat bo'shliq"), ("", "kod yo'q"),
               ("category=lq&label=" + "n" * 61, "nom 61 belgi"),
               ("category=lq&label=%20%20", "nom faqat bo'shliq"),
               ("category=lq&label=", "nom bo'sh")]:
    lab = "" if "label=" in q else "&label=LQ"
    rad(f"H {nom}", "post", f"{OBL}?{q}{lab}&monthly_target=1000&due_day=5")
rad("H belgi 11 belgi", "post",
    f"{OBL}?category=lq&label=LQ&monthly_target=1000&due_day=5&icon=" + "x" * 11)

tikla()
c = login("LQ_admin")
r = req(c, "post", f"{OBL}?category=" + "k" * 30 + "&label=" + "n" * 60
        + "&monthly_target=250000&due_day=31&icon=" + "x" * 10)
h = holat()
check("H chegara qiymatlari (kod 30, nom 60, belgi 10, kun 31) → 200 va saqlandi",
      r.status_code == 200 and h["obl"] == [("k" * 30, "n" * 60, "250000.00", 31, "x" * 10)],
      f"{r.status_code} {h['obl']}")
r = req(c, "post", f"{OBL}?category=lq2&label=%20Kommunal%20&monthly_target=1&due_day=1")
check("H nom atrofidagi bo'shliq olib tashlanadi, summa 1 → 200",
      r.status_code == 200 and ("lq2", "Kommunal", "1.00", 1, "📦") in holat()["obl"],
      holat()["obl"])
r = req(c, "post", f"{OBL}?category=lq3&label=LQ3&monthly_target=5000")
check("H due_day yo'q → 5 (UI standarti), icon yo'q → 📦",
      r.status_code == 200 and ("lq3", "LQ3", "5000.00", 5, "📦") in holat()["obl"],
      holat()["obl"])
r = req(c, "post", f"{OBL}?category=lq3&label=LQ3&monthly_target=5000&due_day=&icon=")
check("H due_day= va icon= (bo'sh) → 5 va 📦",
      r.status_code == 200 and ("lq3", "LQ3", "5000.00", 5, "📦") in holat()["obl"],
      holat()["obl"])
r = req(c, "post", f"{OBL}?category=lq3&label=LQ3%20yangi&monthly_target=7000&due_day=9")
check("H mavjud kod — YANGILANADI (yangi qator emas)",
      r.status_code == 200 and ("lq3", "LQ3 yangi", "7000.00", 9, "📦") in holat()["obl"]
      and sum(1 for x in holat()["obl"] if x[0] == "lq3") == 1, holat()["obl"])
h0 = holat()
r = req(c, "post", f"{OBL}?category=lq3&label=LQ3&monthly_target=inf&due_day=9")
check("H mavjud yozuvni YOMON qiymat bilan yangilash → 400, yozuv O'ZGARMAGAN",
      r.status_code == 400 and holat() == h0, f"{r.status_code}")
check("H sahifalar (\"Qarzdorlar\", ro'yxat) 200", not sahifalar_ok(c), sahifalar_ok(c))
r = req(c, "post", f"{OBL}?category=lq&label=LQ&monthly_target=-5&due_day=5")
try:
    det = r.json().get("detail")
except Exception:
    det = None
check("H 400 detail — MATN, maydon nomi bilan (debts.html serverSababi ko'rsatadi)",
      isinstance(det, str) and "monthly_target" in det, det)

# ══════════════════════════════════════════════════════════════
section("I. Korxona: begona buyurtma — 404 BIRINCHI (oracle yo'q)")
# ══════════════════════════════════════════════════════════════
for label, method, url in [
        ("PUT /loy", "put", f"/api/orders/{O_ID}/loy?loy_kg=inf"),
        ("coating-notify", "post", f"/api/orders/{O_ID}/coating-notify?loy_kg=inf"),
        ("ready", "post", f"/api/orders/{O_ID}/ready?loy_kg=inf"),
        ("DELETE", "delete", f"/api/orders/{O_ID}?actual_loy_kg=inf"),
        ("ready QORALAMA", "post", f"/api/orders/{OD_ID}/ready")]:
    rad(f"I B korxona: {label} (yomon qiymat)", method, url, kutilgan=(404,),
        client_user="LQ_admin_b")
rad("I B korxona: PUT order (yomon loy)", "put", f"/api/orders/{O_ID}?loy_kg=inf",
    kutilgan=(404,), client_user="LQ_admin_b", json=tana("LQ_I_B"))
rad("I B korxona: POST order A loyihasiga (yomon loy)", "post", "/api/orders?loy_kg=inf",
    kutilgan=(404,), client_user="LQ_admin_b", json=tana("LQ_I_B2"))
tikla()
cb = login("LQ_admin_b")
r = req(cb, "post", f"{OBL}?category=lq&label=LQ_B&monthly_target=1000&due_day=5")
ca = login("LQ_admin")
r2 = req(ca, "get", OBL)
try:
    a_list = r2.json()
except Exception:
    a_list = None
check("I B ning majburiyati A ro'yxatida ko'rinmaydi (B ga 200)",
      r.status_code == 200 and isinstance(a_list, list)
      and not any(x.get("label") == "LQ_B" for x in a_list), f"{r.status_code} {a_list}")

# ══════════════════════════════════════════════════════════════
section("J. Ildiz — pydantic / marshrutni chetlab")
# ══════════════════════════════════════════════════════════════
_qloy = getattr(crud, "_query_loy", None)
_jloy = getattr(crud, "_json_loy", None)
_cmaj = getattr(crud, "_clean_majburiyat", None)


def xato_beradimi(fn, *a, **kw):
    """ValueError → True; qaytsa → False; yordamchi yo'q → None."""
    if fn is None:
        return None
    try:
        fn(*a, **kw)
        return False
    except ValueError:
        return True
    except Exception:
        return "boshqa"


def qaytadi(fn, *a, **kw):
    if fn is None:
        return "YO'Q"
    try:
        return fn(*a, **kw)
    except Exception as e:
        return f"XATO:{type(e).__name__}"


for v in ["inf", "nan", "-5", "1e20", "1_0", "abc", "true", float("inf"),
          float("nan"), -1.0, True, 1e13]:
    check(f"J _query_loy({v!r}) → ValueError",
          xato_beradimi(_qloy, "loy_kg", v, bosh_mumkin=True) is True)
check("J _query_loy('') ixtiyoriy → None", qaytadi(_qloy, "loy_kg", "", bosh_mumkin=True) is None)
check("J _query_loy('') majburiy → ValueError",
      xato_beradimi(_qloy, "loy_kg", "", bosh_mumkin=False) is True)
check("J _query_loy(' 12.5 ') → 12.5", qaytadi(_qloy, "loy_kg", " 12.5 ", bosh_mumkin=False) == 12.5)
check("J _query_loy(7) (son) → 7.0", qaytadi(_qloy, "loy_kg", 7, bosh_mumkin=False) == 7.0)
for v in ["5", True, float("inf"), float("nan"), -0.1, 1e13, [], {}]:
    check(f"J _json_loy({v!r}) → ValueError", xato_beradimi(_jloy, "loy_kg", v) is True)
check("J _json_loy(None) → None", qaytadi(_jloy, "loy_kg", None) is None)
check("J _json_loy(3) → 3.0", qaytadi(_jloy, "loy_kg", 3) == 3.0)
check("J _clean_majburiyat to'g'ri → kanonik",
      qaytadi(_cmaj, " kod ", " Nom ", "1000", icon="", due_day="") ==
      {"category": "kod", "label": "Nom", "icon": "📦", "monthly_target": 1000.0, "due_day": 5})
for nom, a, kw in [("summa 0", ("k", "n", "0"), {}), ("summa inf", ("k", "n", "inf"), {}),
                   ("kun 32", ("k", "n", "5"), {"due_day": 32}),
                   ("kun True", ("k", "n", "5"), {"due_day": True}),
                   ("kod None", (None, "n", "5"), {}), ("nom 5 (son)", ("k", 5, "5"), {}),
                   ("belgi 5 (son)", ("k", "n", "5"), {"icon": 5})]:
    check(f"J _clean_majburiyat {nom} → ValueError", xato_beradimi(_cmaj, *a, **kw) is True)

# crud.update_order_loy — ombor TEGILMAYDI
for v in [float("inf"), float("nan"), -5.0, 1e20, "abc"]:
    tikla()
    d = SessionLocal()
    h0 = holat()
    try:
        with contextlib.redirect_stdout(_quiet):
            res = crud.update_order_loy(d, O_ID, v)
        natija = isinstance(res, dict) and res.get("success") is False
    except Exception as e:
        natija = f"ISTISNO {type(e).__name__}"
    finally:
        d.close()
    check(f"J crud.update_order_loy({v!r}) → success False, holat o'zgarmagan",
          natija is True and holat() == h0, natija)

# services.complete_order — loy va qoralama
for oid, v, nom in [(O_ID, float("inf"), "inf"), (O_ID, float("nan"), "nan"),
                    (O_ID, -5.0, "-5"), (O_ID, "abc", "'abc'"), (O_ID, 1e20, "1e20"),
                    (OD_ID, None, "QORALAMA"), (OD_ID, 5.0, "QORALAMA 5")]:
    tikla()
    d = SessionLocal()
    h0 = holat()
    try:
        with contextlib.redirect_stdout(_quiet):
            res = services.complete_order(d, oid, v)
        natija = isinstance(res, dict) and res.get("success") is False
    except Exception as e:
        natija = f"ISTISNO {type(e).__name__}"
    finally:
        d.close()
    check(f"J services.complete_order({nom}) → success False, holat o'zgarmagan",
          natija is True and holat() == h0, natija)
tikla()
d = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        res = services.complete_order(d, O_ID, 12.0)
    ok = isinstance(res, dict) and res.get("success") is True
except Exception as e:
    ok = f"ISTISNO {e}"
finally:
    d.close()
check("J services.complete_order(12.0) NAZORAT → success True, qo'shimcha 2 kg → sement −1",
      ok is True and yaqin(sement(), 994.0), f"{ok} sem={sement()}")

# services.set_recurring_obligation — ValueError, hech narsa yozilmaydi
for nom, a, kw in [("inf", ("lqr", "LQR", float("inf")), {}),
                   ("manfiy", ("lqr", "LQR", -5.0), {}),
                   ("kun 0", ("lqr", "LQR", 1000.0), {"due_day": 0}),
                   ("kod 31", ("k" * 31, "LQR", 1000.0), {}),
                   ("nom 61", ("lqr", "n" * 61, 1000.0), {})]:
    tikla()
    d = SessionLocal()
    h0 = holat()
    try:
        with contextlib.redirect_stdout(_quiet):
            services.set_recurring_obligation(d, *a, company_id=1, **kw)
        natija = False
    except ValueError:
        natija = True
    except Exception as e:
        natija = f"ISTISNO {type(e).__name__}"
    finally:
        d.close()
    check(f"J services.set_recurring_obligation({nom}) → ValueError, yozilmagan",
          natija is True and holat() == h0, natija)

# crud.create_order — sxemani chetlab (model_construct) cheksiz loy
for v in [float("inf"), -3.0, True, "5"]:
    tikla()
    d = SessionLocal()
    h0 = holat()
    try:
        oc = schemas.OrderCreate.model_construct(
            project_id=P_ID, order_type="product", master_id=None, recipe_id=R_ID,
            items=[schemas.OrderItemCreate(name=f"LQ_J_{v}", category="panel", width=100,
                                           thickness=10, length=100, quantity=10,
                                           unit_price=100000, is_coated=True)],
            agreed_amount=None, is_draft=False, deadline=None, notes=None,
            gips_inventory_id=None, planned_gips_kg=None, gips_additives=[],
            base_price=None, loy_kg=v)
        with contextlib.redirect_stdout(_quiet):
            crud.create_order(d, oc, company_id=1)
        natija = False
    except ValueError:
        natija = True
    except Exception as e:
        natija = f"ISTISNO {type(e).__name__}: {e}"
    finally:
        d.rollback()
        d.close()
    check(f"J crud.create_order(loy_kg={v!r}) → ValueError, yozilmagan",
          natija is True and holat() == h0, natija)

# Sxema
for raw, kutil in [('"loy_kg": 10', 10.0), ('"loy_kg": 0', 0.0), ('"loy_kg": 2.5', 2.5),
                   ('"loy_kg": null', None), ('"notes": null', None)]:
    try:
        v = schemas.OrderCreate.model_validate_json('{"project_id": 1, ' + raw + '}').loy_kg
    except Exception as e:
        v = f"XATO {type(e).__name__}"
    check(f"J sxema {{{raw}}} → {kutil}", v == kutil, v)
for raw in ["true", '"5"', "Infinity", "NaN", "-1", "1e13"]:
    try:
        schemas.OrderCreate.model_validate_json('{"project_id": 1, "loy_kg": ' + raw + '}')
        natija = False
    except Exception:
        natija = True
    check(f"J sxema loy_kg={raw} → rad", natija)

# ══════════════════════════════════════════════════════════════
section("K. Statik — marshrutlar, sxema, UI")
# ══════════════════════════════════════════════════════════════
from fastapi.routing import APIRoute  # noqa: E402


def marshrutlar(routes):
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        orr = getattr(r, "original_router", None)
        if orr is not None:
            yield from marshrutlar(orr.routes)


QROUTES = {}
for r in marshrutlar(main.app.routes):
    for m in r.methods - {"HEAD"}:
        QROUTES[(m, r.path)] = r


def qturi(m, path, nom):
    r = QROUTES.get((m, path))
    if not r:
        return "YO'Q"
    for q in r.dependant.query_params:
        if q.name == nom:
            return str(getattr(q.field_info, "annotation", None))
    return "PARAMETR YO'Q"


for m, path, nom in [("PUT", "/api/orders/{order_id}/loy", "loy_kg"),
                     ("POST", "/api/orders/{order_id}/coating-notify", "loy_kg"),
                     ("POST", "/api/orders/{order_id}/ready", "loy_kg"),
                     ("DELETE", "/api/orders/{order_id}", "actual_loy_kg"),
                     ("PUT", "/api/orders/{order_id}", "loy_kg"),
                     ("POST", "/api/orders", "loy_kg"),
                     ("POST", "/api/obligations/recurring", "monthly_target"),
                     ("POST", "/api/obligations/recurring", "due_day")]:
    t = qturi(m, path, nom)
    check(f"K {m} {path} `{nom}` — MATN (float/int emas)",
          "str" in t and "float" not in t and "int" not in t, t)

# Supurish: yozuvchi marshrutlarda son (float/int) so'rov parametri QOLMADI
qolgan = []
for (m, path), r in QROUTES.items():
    if m in ("GET",):
        continue
    for q in r.dependant.query_params:
        t = str(getattr(q.field_info, "annotation", None))
        if ("float" in t or "int" in t) and not t.endswith("bool'>"):
            qolgan.append(f"{m} {path} {q.name}:{t}")
check("K supurish: yozuvchi marshrutlarda son turidagi so'rov parametri 0 ta", not qolgan, qolgan)

for m, path, fn in [("POST", "/api/orders/coating-notify-new", "api_coating_notify_with_loy"),
                    ("POST", "/api/orders/mark-all-ready", "api_mark_all_ready"),
                    ("POST", "/api/finance/expense", "api_save_expense")]:
    r = QROUTES.get((m, path))
    src = inspect.getsource(r.endpoint) if r else ""
    check(f"K {path} — faqat 410 (so'rov parametrisiz, bazaga tegmaydi)",
          r is not None and "status_code=410" in src and "db:" not in src
          and not r.dependant.query_params and not r.dependant.body_params, src[:120])

try:
    fi = schemas.OrderCreate.model_fields["loy_kg"]
    meta = repr(fi.metadata)
    check("K sxema OrderCreate.loy_kg — strict, allow_inf_nan=False, ge=0",
          "Strict" in meta and "allow_inf_nan=False" in meta and "ge=0" in meta, meta)
except Exception as e:
    check("K sxema OrderCreate.loy_kg — strict, allow_inf_nan=False, ge=0", False, e)

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


src_co = inspect.getsource(crud.create_order)
check("K crud.create_order — `_json_loy` advisory qulf / yozuvdan OLDIN",
      tartibda(src_co, "_json_loy", "db.add("), "")
src_ul = inspect.getsource(crud.update_order_loy)
check("K crud.update_order_loy — tekshiruv `adjust_loy_diff` chaqiruvidan OLDIN",
      tartibda(src_ul, "_query_loy(", "services.adjust_loy_diff("))
src_cp = inspect.getsource(services.complete_order)
check("K services.complete_order — loy tekshiruvi va QORALAMA rad birinchi o'zgarishdan OLDIN",
      tartibda(src_cp, "_query_loy", "OrderStatus.DRAFT", "deduct_loy_ingredients"))
src_ro = inspect.getsource(services.set_recurring_obligation)
check("K services.set_recurring_obligation — `_clean_majburiyat` qidiruvdan OLDIN",
      tartibda(src_ro, "_clean_majburiyat", "db.query("))
src_upd = inspect.getsource(QROUTES[("PUT", "/api/orders/{order_id}")].endpoint)
check("K PUT order — loy tekshiruvi `update_order_full` dan OLDIN (yarim yozuv yo'q)",
      tartibda(src_upd, "_query_loy", "update_order_full"))
src_cr = inspect.getsource(QROUTES[("POST", "/api/orders")].endpoint)
check("K POST order — loy tekshiruvi egalikdan KEYIN, ombor tekshiruvidan OLDIN",
      tartibda(src_cr, "project_of_company", "_query_loy", "check_inventory_for_order")
      and "check_loy_ingredients_for_order" in src_cr)

with open(os.path.join(ROOT, "templates", "debts.html"), encoding="utf-8") as f:
    debts = f.read()
with open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8") as f:
    orders = f.read()
check("K debts.html — nom maydoni maxlength=60", 'id="cat-label"' in debts
      and 'maxlength="60"' in debts.split('id="cat-label"')[1][:120])
_snc = debts.split("async function saveNewCategory(){")[-1].split("\n}\n")[0]
check("K debts.html — saveNewCategory `majburiyatKodi` va `serverSababi` ishlatadi",
      "majburiyatKodi(label" in _snc and "await serverSababi(res" in _snc
      and "alert('Xato yuz berdi')" not in _snc, _snc[:200])
check("K orders.html — o'chirish xatosida server sababi",
      "showMsg('❌ Xato yuz berdi', 'error')" not in orders
      and "det.message" in orders)

# `majburiyatKodi` — sahifaning O'Z kodi node da bajariladi
import re  # noqa: E402
m = re.search(r"function majburiyatKodi[\s\S]*?\n}\n", debts)
if m and shutil.which("node"):
    labels = ["Kommunal tolovlar va boshqa xarajat", "Arenda", "   ", "a" * 60,
              "Кўмир ва газ харажатлари учун тўлов", "_____x", "O'z xarajat: soliq / 2026"]
    js = m.group(0) + "\nconsole.log(JSON.stringify(" + json.dumps(labels) + \
        ".map(l => majburiyatKodi(l, 1726912345678))));"
    try:
        out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
        kodlar = json.loads(out.stdout.strip())
    except Exception as e:
        kodlar = [f"XATO {e}"]
    check("K majburiyatKodi — hammasi 1–30 belgi (server chegarasi)",
          all(isinstance(k, str) and 1 <= len(k) <= 30 for k in kodlar), kodlar)
    check("K majburiyatKodi — uzun nom 30 belgiga qisqaradi, oxiri _5678",
          kodlar[0] == "kommunal_tolovlar_va_bosh_5678", kodlar[0])
    check("K majburiyatKodi — bo'sh asos → 'xarajat_5678'", kodlar[2] == "xarajat_5678", kodlar[2])
    check("K majburiyatKodi — qisqartirilgan asos oxirida '_' qolmaydi",
          all("__" not in k for k in kodlar), kodlar)
    tikla()
    c = login("LQ_admin")
    ok_hammasi = True
    for k, lab in zip(kodlar, labels):
        if not lab.strip():
            continue
        r = req(c, "post", OBL, params={"category": k, "label": lab,
                                        "monthly_target": "100000", "due_day": "5"})
        ok_hammasi = ok_hammasi and r.status_code == 200
    check("K UI yasagan kodlar bilan server → 200 (jonli 500 holati yopildi)", ok_hammasi)
else:
    check("K majburiyatKodi topildi va node mavjud", False, "node yo'q yoki funksiya yo'q")

# ══════════════════════════════════════════════════════════════
section("L. Sxema xatosi (422) — cheksiz qiymat bilan ham 500 EMAS")
# ══════════════════════════════════════════════════════════════
tikla()
c = login("LQ_admin")
for label, url, raw in [
        ("buyurtma agreed_amount Infinity", "/api/orders",
         json.dumps(tana("LQ_L1")).replace('"loy_kg": 10', '"loy_kg": 10, "agreed_amount": Infinity')),
        ("buyurtma loy_kg NaN", "/api/orders",
         json.dumps(tana("LQ_L2")).replace('"loy_kg": 10', '"loy_kg": NaN')),
        ("buyurtma loy_kg -Infinity", "/api/orders",
         json.dumps(tana("LQ_L3")).replace('"loy_kg": 10', '"loy_kg": -Infinity')),
        # 17e (2026-09-22): vosita `/api/finance/transactions` dan
        # `/api/transport-expenses` ga ko'chirilgan edi; 17f (2026-09-22) da
        # transport marshruti ham xom JSON ni o'zi tekshirib 400 beradigan
        # bo'ldi (`test_pul_query.py`), shuning uchun vosita endi usta KPI
        # foizi (`MasterKpiUpdate.kpi_percent`, `ge=0, le=100`). Bu yerda FAQAT
        # 422-handler sinaladi: sxema rad etgan `-Infinity` / `NaN` /
        # `+Infinity` javobi JSON ga yozilishi kerak. Usta id MAVJUD EMAS —
        # tana handlerdan OLDIN rad etilmasa 404 chiqadi va tekshiruv yiqiladi.
        ("usta kpi_percent -Infinity (sxema ge=0 rad etadi)", "/api/masters/999999/kpi",
         '{"kpi_percent": -Infinity}'),
        ("usta kpi_percent NaN (sxema rad etadi)", "/api/masters/999999/kpi",
         '{"kpi_percent": NaN}'),
        ("usta kpi_percent +Infinity (sxema le=100 rad etadi)", "/api/masters/999999/kpi",
         '{"kpi_percent": Infinity}')]:
    h0 = holat()
    _metod = "put" if url.startswith("/api/masters/") else "post"
    r = req(c, _metod, url, content=raw, headers={"Content-Type": "application/json"})
    try:
        d = r.json().get("detail")
    except Exception:
        d = None
    check(f"L {label} → 422, `detail` ro'yxat, holat o'zgarmagan",
          r.status_code == 422 and isinstance(d, list) and d and holat() == h0,
          f"{r.status_code} {getattr(r, 'text', '')[:150]}")
    check(f"L {label}: `input` matnga aylangan (JSON da son emas)",
          isinstance(d, list) and all(not isinstance(e.get("input"), float) for e in d
                                      if isinstance(e, dict)), d)
r = req(c, "post", "/api/orders", content='{"project_id": "abc", "items": []}',
        headers={"Content-Type": "application/json"})
try:
    d = r.json().get("detail")
except Exception:
    d = None
check("L oddiy 422 (project_id 'abc') — FastAPI standarti bilan bir xil shakl",
      r.status_code == 422 and isinstance(d, list) and d[0].get("loc") == ["body", "project_id"]
      and d[0].get("input") == "abc" and "type" in d[0] and "msg" in d[0], d)
r = req(c, "post", "/api/orders", content='[1, 2', headers={"Content-Type": "application/json"})
check("L buzilgan JSON → 422 (500 emas)", r.status_code == 422, r.status_code)
_jx = getattr(main, "_json_xavfsiz", None)
check("L _json_xavfsiz — ichma-ich inf/nan matnga, qolgani o'zgarmaydi",
      _jx is not None and _jx({"a": [float("inf"), 1.5, {"b": float("nan")}], "c": "x", "d": None})
      == {"a": ["inf", 1.5, {"b": "nan"}], "c": "x", "d": None})
from fastapi.exceptions import RequestValidationError as _RVE  # noqa: E402
check("L RequestValidationError uchun handler ro'yxatdan o'tgan",
      _RVE in main.app.exception_handlers)
check("L sahifalar 200", not sahifalar_ok(c), sahifalar_ok(c))

print("\n" + "=" * 66)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print("=" * 66)
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
