#!/usr/bin/env python3
"""
test_xarajat_query.py — 17e-band: kunlik xarajat tranzaksiyasi va buyurtmaning
kelishilgan summasi.

NIMA UCHUN KERAK (2026-09-22)
-----------------------------
Hammasi O'LCHANGAN (`work/probe17e.py`, har prob alohida toza bazada; asl
kod = 17d; `agreed_amount: Infinity` — JONLI sinov saytida ham, 500 va
`/logs` yozuvi):

1) `POST`/`PUT /api/finance/transactions` sxemasida summa uchun faqat
   `ge=0` bor edi: `Infinity` → javob 500, LEKIN yozuv SAQLANARDI va
   shundan keyin `/api/finance/history` hamda xarajatlar ro'yxati BUTUNLAY
   500. `1e20` (PostgreSQL da Numeric(12,2) → 500), `true` → 1 so'm,
   `"5000"` → 5000, 0 so'm — qabul.
2) Kategoriya bo'sh / faqat bo'shliq / 31–300 belgi (PostgreSQL da
   String(30) → 500), noto'g'ri `production_type` ("xyz" — oylik hisobotdan
   JIMGINA tushib qolardi; 21 belgi — PostgreSQL 500), sana 0001-yil,
   1999-yil, `12345` (→ 1970-yil) — qabul. Noma'lum kalitlar jim e'tiborsiz.
3) `PUT /api/orders/{id}/agreed-amount` (`OrderAgreedUpdate`, `ge=0`):
   `Infinity` → 500 (SQLite da SAQLANARDI), `1e20` saqlanardi, `true` →
   1 so'm (chegirma 99.9 %), `"800"` → 800, 0 → chegirma 100 % LEKIN
   `_update_order_payment_status` 0 ni "berilmagan" deb qarzni JAMI
   summadan hisoblardi (ikki xil talqin; UI ham 0 ni rad etadi).
4) UI: `debts.html` majburiyat to'lovi va `orders.html` kelishilgan summa
   xatoda faqat "Xato" derdi — endi server sababi.

QAMROV
------
A. `POST` yomon tanalar — 400, HOLAT o'zgarmagan, Moliya sahifalari 200
B. `POST` to'g'ri tanalar (uch sahifaning AYNAN o'z shakli) — aniq qiymatlar
C. `PUT` yomon — 400, yozuv o'zgarmagan; to'g'ri — aniq; sana berilmasa
   eskisi qoladi
D. `PUT` begona / yo'q yozuv — yomon tana bilan ham 404 (oracle yo'q)
E. `agreed-amount` — yomon 400 (`detail` obyekt), buyurtma o'zgarmagan;
   to'g'ri — aniq chegirma va to'lov holati; begona — 404
F. KUMULYATIV: barcha yomon so'rovlardan keyin (tiklamasdan) Moliya tarixi,
   ro'yxat, hisobot 200 va yozuvlar soni o'zgarmagan
G. Ildiz: `crud.create_expense_transaction`, `update_expense_transaction`,
   `update_order_agreed_amount` — `ValueError`, bazaga tegmaydi
H. Statik: marshrut turlari, egalik tekshiruvi TANADAN OLDIN, qoidalar
   jadvali, sxemalar, UI sabablari
I. 422 (tana lug'at emas / buzilgan JSON) — 422 qoladi, 500 emas

ISHLATISH
---------
    python tools/test_xarajat_query.py
    TENANT_FILTER=1 python tools/test_xarajat_query.py

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
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "xarajat_query_test.db")
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
    import crud, auth, schemas                     # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderType, OrderStatus, ExpenseTransaction,
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


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="Test Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "XQ_admin", "Parol123!", UserRole.ADMIN, "XQ Admin",
                     company_id=1)
    auth.create_user(_db, "XQ_admin_b", "Parol123!", UserRole.ADMIN, "XQ Admin B",
                     company_id=2)

PRJ = Project(company_id=1, client_name="XQ Mijoz", project_name="XQ loyiha",
              total_budget=0, total_paid=0)
PRJ_B = Project(company_id=2, client_name="XQ Mijoz B", project_name="XQ loyiha B",
                total_budget=0, total_paid=0)
_db.add_all([PRJ, PRJ_B])
_db.commit()
ORD = Order(company_id=1, project_id=PRJ.id, order_number="XQ-ORD-1",
            order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS,
            total_amount=1000, agreed_amount=1000, discount_percent=0.0)
ORD_B = Order(company_id=2, project_id=PRJ_B.id, order_number="XQ-ORD-B",
              order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS,
              total_amount=2000, agreed_amount=2000, discount_percent=0.0)
_db.add_all([ORD, ORD_B])
_db.commit()
TX = ExpenseTransaction(company_id=1, category="boshqa", amount=500,
                        date=__import__("datetime").datetime(2026, 9, 10),
                        notes="asl", production_type="penoplast", source="manual")
TX_B = ExpenseTransaction(company_id=2, category="arenda", amount=700,
                          date=__import__("datetime").datetime(2026, 9, 11),
                          notes="begona", source="manual")
_db.add_all([TX, TX_B])
_db.commit()
O_ID, OB_ID, TX_ID, TXB_ID = ORD.id, ORD_B.id, TX.id, TX_B.id
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
        return getattr(client, method)(url, **kw)
    except Exception as e:          # pragma: no cover — himoya qatlami
        return _R599(e)


C = login("XQ_admin")
CB = login("XQ_admin_b")

# IZOLYATSIYA (17.1 saboqi): har prob oldidan fikstura bazasi tiklanadi —
# bitta o'tib ketgan `Infinity` keyingi problarni 500 qilib yolg'on natija
# bermasin.
engine.dispose()
shutil.copy(_DB, _SNAP)


def tikla():
    engine.dispose()
    shutil.copy(_SNAP, _DB)


def holat():
    """Tekshiriladigan to'liq holat: barcha xarajat yozuvlari va buyurtmalar."""
    d = SessionLocal()
    try:
        return {
            "et": [(x.id, x.company_id, str(x.date), x.category, str(x.amount), x.notes,
                    x.production_type, x.source)
                   for x in d.query(ExpenseTransaction).order_by(ExpenseTransaction.id)],
            "or": [(o.id, str(o.agreed_amount), o.discount_percent,
                    o.payment_status.value if o.payment_status else None, bool(o.is_archived))
                   for o in d.query(Order).order_by(Order.id)],
        }
    finally:
        d.close()


def yozuv(tx_id):
    d = SessionLocal()
    try:
        x = d.get(ExpenseTransaction, tx_id)
        if not x:
            return None
        return SimpleNamespace(date=x.date, category=x.category, amount=float(x.amount),
                               notes=x.notes, production_type=x.production_type,
                               company_id=x.company_id, source=x.source)
    finally:
        d.close()


def buyurtma(oid):
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        return SimpleNamespace(agreed=float(o.agreed_amount), discount=o.discount_percent,
                               pstatus=o.payment_status.value if o.payment_status else None)
    finally:
        d.close()


def eng_songgi_yozuv():
    d = SessionLocal()
    try:
        x = d.query(ExpenseTransaction).order_by(ExpenseTransaction.id.desc()).first()
        return x.id if x else None
    finally:
        d.close()


SAHIFALAR = ["/api/finance/history", "/api/finance/transactions",
             "/api/finance/transactions?year=2026&month=9",
             "/api/finance/report?year=2026&month=9", "/finance", "/debts",
             "/api/orders", f"/api/orders/{O_ID}"]


def sahifalar_xato(c):
    """200 bermagan sahifalar ro'yxati (bo'sh — hammasi joyida)."""
    xato = []
    for u in SAHIFALAR:
        r = req(c, "get", u)
        if r.status_code != 200:
            xato.append((u, r.status_code))
    return xato


def xom(client, method, url, raw):
    return req(client, method, url, content=raw,
               headers={"Content-Type": "application/json"})


def tana(**k):
    b = {"category": "boshqa", "amount": 1000}
    b.update(k)
    return json.dumps(b)


def detail_matn(r):
    try:
        d = r.json().get("detail")
    except Exception:
        return None
    return d if isinstance(d, str) else None


def detail_xabar(r):
    try:
        d = r.json().get("detail")
    except Exception:
        return None
    if isinstance(d, dict) and isinstance(d.get("message"), str) and d.get("success") is False:
        return d["message"]
    return None


# Yomon xarajat tanalari: (nom, xom JSON, sababda bo'lishi kerak bo'lgan kalit)
YOMON_TX = [
    ("amount Infinity", '{"category": "boshqa", "amount": Infinity}', "amount"),
    ("amount -Infinity", '{"category": "boshqa", "amount": -Infinity}', "amount"),
    ("amount NaN", '{"category": "boshqa", "amount": NaN}', "amount"),
    ("amount 1e20", tana(amount=1e20), "amount"),
    ("amount 1e10 (sig'imdan katta)", tana(amount=1e10), "amount"),
    ("amount true", tana(amount=True), "amount"),
    ("amount false", tana(amount=False), "amount"),
    ("amount \"5000\"", tana(amount="5000"), "amount"),
    ("amount 0", tana(amount=0), "amount"),
    ("amount -5", tana(amount=-5), "amount"),
    ("amount null", tana(amount=None), "amount"),
    ("amount ro'yxat", tana(amount=[1000]), "amount"),
    ("amount berilmagan", json.dumps({"category": "boshqa"}), "amount"),
    ("category 300", tana(category="x" * 300), "category"),
    ("category 31", tana(category="x" * 31), "category"),
    ("category ''", tana(category=""), "category"),
    ("category bo'shliq", tana(category="   "), "category"),
    ("category null", tana(category=None), "category"),
    ("category 123", tana(category=123), "category"),
    ("category berilmagan", json.dumps({"amount": 1000}), "category"),
    ("notes 10001", tana(notes="n" * 10001), "notes"),
    ("notes 123", tana(notes=123), "notes"),
    ("production_type xyz", tana(production_type="xyz"), "production_type"),
    ("production_type Penoplast (katta harf)", tana(production_type="Penoplast"),
     "production_type"),
    ("production_type 21 belgi", tana(production_type="p" * 21), "production_type"),
    ("production_type 5", tana(production_type=5), "production_type"),
    ("date abc", tana(date="abc"), "date"),
    ("date 0001-yil", tana(date="0001-01-01T00:00:00"), "date"),
    ("date 1999-yil", tana(date="1999-12-31T00:00:00"), "date"),
    ("date 2101-yil", tana(date="2101-01-01"), "date"),
    ("date 12345 (son)", tana(date=12345), "date"),
    ("date 2026-13-45", tana(date="2026-13-45"), "date"),
    ("noma'lum source", tana(source="monthly_form"), "source"),
    ("noma'lum company_id", tana(company_id=2), "company_id"),
    ("noma'lum created_by", tana(created_by="boshqa odam"), "created_by"),
]

# ══════════════════════════════════════════════════════════════
section("A. POST /api/finance/transactions — yomon tanalar 400, hech narsa yozilmaydi")
# ══════════════════════════════════════════════════════════════
for nom, raw, kalit in YOMON_TX:
    tikla()
    h0 = holat()
    r = xom(C, "post", "/api/finance/transactions", raw)
    sabab = detail_matn(r)
    check(f"A {nom} → 400", r.status_code == 400, (r.status_code, r.text[:160]))
    check(f"A {nom} — sabab matn va kalitni nomlaydi", sabab is not None and kalit in sabab, sabab)
    check(f"A {nom} — holat o'zgarmagan", holat() == h0)
    xato = sahifalar_xato(C)
    check(f"A {nom} — Moliya sahifalari 200", not xato, xato)

# ══════════════════════════════════════════════════════════════
section("B. POST — to'g'ri tanalar (sahifalarning AYNAN o'z shakli)")
# ══════════════════════════════════════════════════════════════
import datetime as _dt                             # noqa: E402

TOGRI_TX = [
    # finance.html saveTx
    ("finance.html (penoplast)", json.dumps({"date": "2026-09-22T00:00:00", "category": "elektr",
                                              "amount": 125000, "notes": None,
                                              "production_type": "penoplast"}),
     dict(date=_dt.datetime(2026, 9, 22), category="elektr", amount=125000.0, notes=None,
          production_type="penoplast")),
    ("finance.html (umumiy → null)", json.dumps({"date": "2026-09-05T00:00:00", "category": "arenda",
                                                  "amount": 2000000, "notes": "sentyabr",
                                                  "production_type": None}),
     dict(date=_dt.datetime(2026, 9, 5), category="arenda", amount=2000000.0, notes="sentyabr",
          production_type=None)),
    # kunlik_xarajat.html
    ("kunlik_xarajat.html", json.dumps({"date": "2026-09-21T00:00:00", "category": "tushlik",
                                        "amount": 45000, "notes": None}),
     dict(date=_dt.datetime(2026, 9, 21), category="tushlik", amount=45000.0, notes=None,
          production_type=None)),
    # debts.html quickPayObligation — kategoriya = majburiyat kodi (30 belgi), kasr summa
    ("debts.html (30 belgili kod, kasr summa)",
     json.dumps({"date": "2026-09-28T00:00:00", "category": "kommunal_tolovlar_va_bosh_8083",
                 "amount": 750000.5, "notes": "To'lov (Qarzdorlar sahifasidan)"}),
     dict(date=_dt.datetime(2026, 9, 28), category="kommunal_tolovlar_va_bosh_8083",
          amount=750000.5, notes="To'lov (Qarzdorlar sahifasidan)", production_type=None)),
    ("faqat majburiylar (sana — hozir)", json.dumps({"category": "boshqa", "amount": 1}),
     dict(category="boshqa", amount=1.0, notes=None, production_type=None)),
    ("sana YYYY-MM-DD, production_type '' → null",
     json.dumps({"date": "2026-01-02", "category": "soliqlar", "amount": 9999999999.99,
                 "production_type": ""}),
     dict(date=_dt.datetime(2026, 1, 2), category="soliqlar", amount=9999999999.99,
          production_type=None)),
    ("gips yo'nalishi, 10000 belgili izoh",
     json.dumps({"category": "reklama", "amount": 0.01, "production_type": "gips",
                 "notes": "i" * 10000}),
     dict(category="reklama", amount=0.01, production_type="gips", notes="i" * 10000)),
]
for nom, raw, kutilgan in TOGRI_TX:
    tikla()
    n0 = len(holat()["et"])
    r = xom(C, "post", "/api/finance/transactions", raw)
    check(f"B {nom} → 200", r.status_code == 200, (r.status_code, r.text[:160]))
    n1 = len(holat()["et"])
    check(f"B {nom} — aynan bitta yozuv qo'shildi", n1 == n0 + 1, (n0, n1))
    y = yozuv(eng_songgi_yozuv())
    for k, v in kutilgan.items():
        fakt = getattr(y, k, "YO'Q") if y else "YO'Q"
        ok = yaqin(fakt, v) if k == "amount" else fakt == v
        check(f"B {nom} — {k} aniq", ok, (fakt, v))
    check(f"B {nom} — korxona = foydalanuvchiniki (1), manba manual",
          y is not None and y.company_id == 1 and y.source == "manual",
          y and (y.company_id, y.source))
    xato = sahifalar_xato(C)
    check(f"B {nom} — Moliya sahifalari 200", not xato, xato)

tikla()
r = xom(CB, "post", "/api/finance/transactions", tana(category="b_korxona", amount=321))
y = yozuv(eng_songgi_yozuv())
check("B 2-korxona admini — yozuv 2-korxonaga", r.status_code == 200 and y is not None
      and y.company_id == 2 and y.category == "b_korxona", (r.status_code, y))

# ══════════════════════════════════════════════════════════════
section("C. PUT /api/finance/transactions/{id} — yomon 400, to'g'ri aniq")
# ══════════════════════════════════════════════════════════════
for nom, raw, kalit in YOMON_TX:
    tikla()
    h0 = holat()
    r = xom(C, "put", f"/api/finance/transactions/{TX_ID}", raw)
    sabab = detail_matn(r)
    check(f"C {nom} → 400", r.status_code == 400, (r.status_code, r.text[:160]))
    check(f"C {nom} — sabab kalitni nomlaydi", sabab is not None and kalit in sabab, sabab)
    check(f"C {nom} — yozuv o'zgarmagan", holat() == h0)

tikla()
r = xom(C, "put", f"/api/finance/transactions/{TX_ID}",
        json.dumps({"date": "2026-09-15T00:00:00", "category": "kutilmagan", "amount": 125000,
                    "notes": "tuzatildi", "production_type": None}))
y = yozuv(TX_ID)
check("C finance.html tahriri → 200", r.status_code == 200, (r.status_code, r.text[:160]))
check("C tahrir — sana, kategoriya, summa, izoh, yo'nalish aniq",
      y is not None and y.date == _dt.datetime(2026, 9, 15) and y.category == "kutilmagan"
      and yaqin(y.amount, 125000) and y.notes == "tuzatildi" and y.production_type is None, y)
check("C tahrir — korxona va manba o'zgarmagan", y is not None and y.company_id == 1
      and y.source == "manual", y)
xato = sahifalar_xato(C)
check("C tahrirdan keyin sahifalar 200", not xato, xato)

tikla()
r = xom(C, "put", f"/api/finance/transactions/{TX_ID}",
        json.dumps({"category": "boshqa", "amount": 600}))
y = yozuv(TX_ID)
check("C sana berilmasa — ESKI sana qoladi (2026-09-10)", r.status_code == 200 and y is not None
      and y.date == _dt.datetime(2026, 9, 10) and yaqin(y.amount, 600), (r.status_code, y))

tikla()
r = xom(C, "put", f"/api/finance/transactions/{TX_ID}",
        json.dumps({"date": "", "category": "boshqa", "amount": 700}))
y = yozuv(TX_ID)
check("C sana '' — ESKI sana qoladi", r.status_code == 200 and y is not None
      and y.date == _dt.datetime(2026, 9, 10) and yaqin(y.amount, 700), (r.status_code, y))

# ══════════════════════════════════════════════════════════════
section("D. PUT begona / yo'q yozuv — yomon tana bilan ham 404")
# ══════════════════════════════════════════════════════════════
for nom, raw in [("yomon tana", '{"category": "x", "amount": Infinity}'),
                 ("noma'lum kalit", tana(company_id=1)),
                 ("to'g'ri tana", tana(amount=5))]:
    tikla()
    h0 = holat()
    r = xom(C, "put", f"/api/finance/transactions/{TXB_ID}", raw)
    check(f"D begona yozuv, {nom} → 404", r.status_code == 404, (r.status_code, r.text[:120]))
    check(f"D begona yozuv, {nom} — hech narsa o'zgarmagan", holat() == h0)
    r = xom(C, "put", "/api/finance/transactions/999999", raw)
    check(f"D yo'q yozuv, {nom} → 404", r.status_code == 404, (r.status_code, r.text[:120]))
tikla()
r = xom(CB, "put", f"/api/finance/transactions/{TXB_ID}", tana(category="arenda", amount=800))
y = yozuv(TXB_ID)
check("D egasi (2-korxona) o'z yozuvini tahrirlaydi → 200", r.status_code == 200
      and y is not None and yaqin(y.amount, 800), (r.status_code, y))

# ══════════════════════════════════════════════════════════════
section("E. PUT /api/orders/{id}/agreed-amount")
# ══════════════════════════════════════════════════════════════
YOMON_AG = [
    ("Infinity", '{"agreed_amount": Infinity}'),
    ("-Infinity", '{"agreed_amount": -Infinity}'),
    ("NaN", '{"agreed_amount": NaN}'),
    ("1e20", '{"agreed_amount": 1e20}'),
    ("1e10", '{"agreed_amount": 1e10}'),
    ("0", '{"agreed_amount": 0}'),
    ("-5", '{"agreed_amount": -5}'),
    ("true", '{"agreed_amount": true}'),
    ("\"800\"", '{"agreed_amount": "800"}'),
    ("null", '{"agreed_amount": null}'),
    ("berilmagan", '{}'),
    ("noma'lum kalit", '{"agreed_amount": 800, "total_amount": 5}'),
]
for nom, raw in YOMON_AG:
    tikla()
    h0 = holat()
    r = xom(C, "put", f"/api/orders/{O_ID}/agreed-amount", raw)
    xabar = detail_xabar(r)
    check(f"E {nom} → 400", r.status_code == 400, (r.status_code, r.text[:160]))
    check(f"E {nom} — detail {{success: false, message}}", xabar is not None, r.text[:160])
    check(f"E {nom} — buyurtma o'zgarmagan", holat() == h0)

for nom, qiymat, chegirma, holati in [("800 (chegirma 20 %)", 800, 20.0, "unpaid"),
                                      ("1000 (chegirmasiz)", 1000, 0.0, "unpaid"),
                                      ("1500 (jamidan ko'p)", 1500, 0.0, "unpaid"),
                                      ("0.01 (eng kichik)", 0.01, 100.0, "unpaid"),
                                      ("999.5 (kasr)", 999.5, 0.05, "unpaid")]:
    tikla()
    r = xom(C, "put", f"/api/orders/{O_ID}/agreed-amount", json.dumps({"agreed_amount": qiymat}))
    b = buyurtma(O_ID)
    check(f"E {nom} → 200", r.status_code == 200, (r.status_code, r.text[:160]))
    check(f"E {nom} — summa, chegirma, holat aniq", yaqin(b.agreed, qiymat)
          and yaqin(b.discount, chegirma) and b.pstatus == holati, b)
    try:
        j = r.json()
    except Exception:
        j = {}
    check(f"E {nom} — javob maydonlari", yaqin(j.get("agreed_amount"), qiymat)
          and yaqin(j.get("discount_percent"), chegirma) and j.get("status") == "ok", j)

for nom, raw in [("yomon tana", '{"agreed_amount": Infinity}'),
                 ("to'g'ri tana", '{"agreed_amount": 5}')]:
    tikla()
    h0 = holat()
    r = xom(C, "put", f"/api/orders/{OB_ID}/agreed-amount", raw)
    check(f"E begona buyurtma, {nom} → 404", r.status_code == 404, (r.status_code, r.text[:120]))
    check(f"E begona buyurtma, {nom} — o'zgarmagan", holat() == h0)
    r = xom(C, "put", "/api/orders/999999/agreed-amount", raw)
    check(f"E yo'q buyurtma, {nom} → 404", r.status_code == 404, (r.status_code, r.text[:120]))

# ══════════════════════════════════════════════════════════════
section("F. KUMULYATIV — barcha yomon so'rovlar ketma-ket (tiklamasdan)")
# ══════════════════════════════════════════════════════════════
tikla()
h0 = holat()
for nom, raw, kalit in YOMON_TX:
    xom(C, "post", "/api/finance/transactions", raw)
    xom(C, "put", f"/api/finance/transactions/{TX_ID}", raw)
for nom, raw in YOMON_AG:
    xom(C, "put", f"/api/orders/{O_ID}/agreed-amount", raw)
check("F yozuvlar va buyurtmalar AYNAN avvalgidek", holat() == h0)
xato = sahifalar_xato(C)
check("F Moliya tarixi, ro'yxat, hisobot, sahifalar 200", not xato, xato)
r = req(C, "get", "/api/finance/history")
try:
    _fh = r.json()
    _fh_ok = isinstance(_fh, list)
except Exception:
    _fh_ok = False
check("F /api/finance/history — JSON massiv", r.status_code == 200 and _fh_ok, r.status_code)

# ══════════════════════════════════════════════════════════════
section("G. Ildiz — crud funksiyalari bazaga tegmasdan rad etadi")
# ══════════════════════════════════════════════════════════════
YOMON_ILDIZ = [
    ("amount inf", {"category": "boshqa", "amount": float("inf")}),
    ("amount nan", {"category": "boshqa", "amount": float("nan")}),
    ("amount 1e20", {"category": "boshqa", "amount": 1e20}),
    ("amount True", {"category": "boshqa", "amount": True}),
    ("amount '5000'", {"category": "boshqa", "amount": "5000"}),
    ("amount 0", {"category": "boshqa", "amount": 0}),
    ("category 31", {"category": "x" * 31, "amount": 5}),
    ("category ''", {"category": "", "amount": 5}),
    ("production_type xyz", {"category": "boshqa", "amount": 5, "production_type": "xyz"}),
    ("date 1999", {"category": "boshqa", "amount": 5, "date": _dt.datetime(1999, 1, 1)}),
    ("noma'lum kalit", {"category": "boshqa", "amount": 5, "source": "x"}),
]
for nom, data in YOMON_ILDIZ:
    tikla()
    h0 = holat()
    d = SessionLocal()
    xato_turi = None
    try:
        crud.create_expense_transaction(d, dict(data), performed_by="t", source="manual",
                                        company_id=1)
    except ValueError:
        xato_turi = "ValueError"
    except Exception as e:
        xato_turi = type(e).__name__
        d.rollback()
    finally:
        d.close()
    check(f"G create {nom} — ValueError", xato_turi == "ValueError", xato_turi)
    check(f"G create {nom} — baza o'zgarmagan", holat() == h0)

    tikla()
    d = SessionLocal()
    xato_turi = None
    try:
        crud.update_expense_transaction(d, TX_ID, dict(data), company_id=1)
    except ValueError:
        xato_turi = "ValueError"
    except Exception as e:
        xato_turi = type(e).__name__
        d.rollback()
    finally:
        d.close()
    check(f"G update {nom} — ValueError", xato_turi == "ValueError", xato_turi)
    check(f"G update {nom} — yozuv o'zgarmagan", holat() == h0)

# Ildiz: to'g'ri lug'at — datetime sana ham (marshrut tozalagan shakl)
tikla()
d = SessionLocal()
try:
    _t = crud.create_expense_transaction(d, {"category": "elektr", "amount": 5.5,
                                             "date": _dt.datetime(2026, 9, 1)},
                                         performed_by="t", source="manual", company_id=1)
    _ok = (_t.category == "elektr" and yaqin(_t.amount, 5.5)
           and _t.date == _dt.datetime(2026, 9, 1) and _t.company_id == 1)
except Exception as e:
    _ok = f"{type(e).__name__}: {e}"
finally:
    d.close()
check("G create to'g'ri lug'at (datetime sana) — saqlanadi", _ok is True, _ok)

# Ildiz: pydantic obyekt ham qabul (eski chaqiruv shakli)
tikla()
d = SessionLocal()
try:
    _obj = schemas.ExpenseTransactionCreate(category="elektr", amount=7.0)
    _t = crud.create_expense_transaction(d, _obj, performed_by="t", source="manual",
                                         company_id=1)
    _ok = _t.category == "elektr" and yaqin(_t.amount, 7.0)
except Exception as e:
    _ok = f"{type(e).__name__}: {e}"
finally:
    d.close()
check("G create pydantic obyekt — saqlanadi", _ok is True, _ok)

for nom, qiymat in [("inf", float("inf")), ("nan", float("nan")), ("1e20", 1e20),
                    ("0", 0), ("-5", -5), ("True", True), ("'800'", "800"), ("None", None)]:
    tikla()
    h0 = holat()
    d = SessionLocal()
    xato_turi = None
    try:
        crud.update_order_agreed_amount(d, O_ID, qiymat)
    except ValueError:
        xato_turi = "ValueError"
    except Exception as e:
        xato_turi = type(e).__name__
        d.rollback()
    finally:
        d.close()
    check(f"G agreed {nom} — ValueError", xato_turi == "ValueError", xato_turi)
    check(f"G agreed {nom} — buyurtma o'zgarmagan", holat() == h0)

tikla()
d = SessionLocal()
try:
    _o = crud.update_order_agreed_amount(d, O_ID, 750)
    _ok = _o is not None and yaqin(_o.agreed_amount, 750) and yaqin(_o.discount_percent, 25.0)
except Exception as e:
    _ok = f"{type(e).__name__}: {e}"
finally:
    d.close()
check("G agreed 750 — chegirma 25 %", _ok is True, _ok)

_cv = getattr(crud, "_clean_val", None)
for model, data, kutilgan in [
    ("ExpenseTransaction", {"category": " boshqa ", "amount": 5, "production_type": "  penoplast "},
     {"category": " boshqa ", "amount": 5.0, "production_type": "penoplast"}),
    ("ExpenseTransaction", {"category": "a", "amount": 1, "date": "2026-09-22T00:00:00"},
     {"category": "a", "amount": 1.0, "date": _dt.datetime(2026, 9, 22)}),
    ("OrderAgreed", {"agreed_amount": 800}, {"agreed_amount": 800.0}),
]:
    try:
        _r = _cv(model, dict(data)) if _cv else None
    except Exception as e:
        _r = f"{type(e).__name__}: {e}"
    check(f"G _clean_val {model} {sorted(data)} — tozalangan natija", _r == kutilgan, _r)

# ══════════════════════════════════════════════════════════════
section("H. Statik — marshrut turlari, tartib, qoidalar, sxemalar, UI")
# ══════════════════════════════════════════════════════════════
def _marshrut(fn_nomi):
    fn = getattr(main, fn_nomi, None)
    try:
        return inspect.getsource(fn) if fn else ""
    except (OSError, TypeError):
        return ""


def _data_turi(fn_nomi):
    fn = getattr(main, fn_nomi, None)
    if fn is None:
        return None
    try:
        return inspect.signature(fn).parameters["data"].annotation
    except (KeyError, ValueError, TypeError):
        return None


for fn_nomi in ("api_create_expense_transaction", "api_update_expense_transaction",
                "api_update_agreed_amount"):
    check(f"H {fn_nomi} — tana xom dict (pydantic JIM o'girmasin)",
          _data_turi(fn_nomi) is dict, _data_turi(fn_nomi))

src_post = _marshrut("api_create_expense_transaction")
src_put = _marshrut("api_update_expense_transaction")
src_ag = _marshrut("api_update_agreed_amount")
check("H POST marshruti — _clean_val(\"ExpenseTransaction\") → create",
      tartibda(src_post, '_clean_val("ExpenseTransaction"', "create_expense_transaction("))
check("H POST marshruti — ValueError → 400",
      tartibda(src_post, "except ValueError", "status_code=400"))
check("H PUT marshruti — EGALIK tanadan OLDIN",
      tartibda(src_put, "expense_of_company(", "404", '_clean_val("ExpenseTransaction"',
               "update_expense_transaction("))
check("H PUT marshruti — ValueError → 400", tartibda(src_put, "except ValueError", "status_code=400"))
check("H agreed marshruti — EGALIK tanadan OLDIN",
      tartibda(src_ag, "order_of_company(", "404", '_clean_val("OrderAgreed"',
               "update_order_agreed_amount("))
check("H agreed marshruti — detail obyekt (success/message)",
      tartibda(src_ag, "except ValueError", "status_code=400", '"success": False', '"message"'))

try:
    src_cr = inspect.getsource(crud.create_expense_transaction)
    src_up = inspect.getsource(crud.update_expense_transaction)
    src_oa = inspect.getsource(crud.update_order_agreed_amount)
except (OSError, TypeError, AttributeError):
    src_cr = src_up = src_oa = ""
check("H ildiz create — tozalash bazaga yozishdan OLDIN",
      tartibda(src_cr, '_clean_val("ExpenseTransaction"', "ExpenseTransaction(", "db.add("))
check("H ildiz update — tozalash so'rovdan OLDIN",
      tartibda(src_up, '_clean_val("ExpenseTransaction"', "db.query(ExpenseTransaction)"))
check("H ildiz agreed — tozalash so'rovdan OLDIN",
      tartibda(src_oa, '_clean_val("OrderAgreed"', "db.query(Order)"))

try:
    _vr = crud._val_rules()
except Exception as e:
    _vr = {"XATO": str(e)}
_et = _vr.get("ExpenseTransaction", {}) if isinstance(_vr, dict) else {}
_oa = _vr.get("OrderAgreed", {}) if isinstance(_vr, dict) else {}
check("H qoidalar — ExpenseTransaction AYNAN 5 kalit",
      sorted(_et) == ["amount", "category", "date", "notes", "production_type"], sorted(_et))
check("H qoidalar — amount musbat, sig'im chegarasi",
      _et.get("amount") == ("son", False, True, getattr(crud, "_ORDER_ITEM_MAX_MONEY", None)),
      _et.get("amount"))
check("H qoidalar — category majburiy, ≤ 30 (ustun String(30))",
      _et.get("category") == ("matn", True, 30), _et.get("category"))
_pt = _et.get("production_type")
check("H qoidalar — production_type ro'yxat: umumiy/penoplast/gips",
      isinstance(_pt, tuple) and len(_pt) == 3 and _pt[0] == "tanlov" and _pt[1] is True
      and sorted(_pt[2]) == ["gips", "penoplast", "umumiy"], _pt)
check("H qoidalar — date ixtiyoriy sana", _et.get("date") == ("sana", True), _et.get("date"))
check("H qoidalar — OrderAgreed faqat agreed_amount, musbat",
      _oa == {"agreed_amount": ("son", False, True,
                                getattr(crud, "_ORDER_ITEM_MAX_MONEY", None))}, _oa)
_vm = getattr(crud, "_VAL_MAJBURIY", {})
check("H majburiy — ExpenseTransaction category, amount",
      _vm.get("ExpenseTransaction") == {"category": 1, "amount": None},
      _vm.get("ExpenseTransaction"))
check("H majburiy — OrderAgreed agreed_amount",
      _vm.get("OrderAgreed") == {"agreed_amount": None}, _vm.get("OrderAgreed"))

try:
    from models import ExpenseTransaction as _ETm
    _cat_len = _ETm.__table__.c.category.type.length
    _pt_len = _ETm.__table__.c.production_type.type.length
except Exception:
    _cat_len = _pt_len = None
check("H model — category String(30) qoidaga mos", _cat_len == 30, _cat_len)
check("H model — production_type String(20) ≥ eng uzun tanlov",
      _pt_len is not None and _pt_len >= max(len(v) for v in ("umumiy", "penoplast", "gips")),
      _pt_len)

from pydantic import ValidationError as _VE        # noqa: E402


def _sxema_rad(cls, **k):
    try:
        cls(**k)
        return False
    except _VE:
        return True
    except Exception:
        return False


_ETC = getattr(schemas, "ExpenseTransactionCreate", None)
_OAU = getattr(schemas, "OrderAgreedUpdate", None)
for nom, k in [("inf", {"category": "a", "amount": float("inf")}),
               ("True", {"category": "a", "amount": True}),
               ("'5'", {"category": "a", "amount": "5"}),
               ("0", {"category": "a", "amount": 0}),
               ("1e20", {"category": "a", "amount": 1e20}),
               ("category ''", {"category": "", "amount": 5}),
               ("category 31", {"category": "x" * 31, "amount": 5}),
               ("production_type xyz", {"category": "a", "amount": 5, "production_type": "xyz"})]:
    check(f"H sxema ExpenseTransactionCreate {nom} — rad (ikkinchi to'siq)",
          _ETC is not None and _sxema_rad(_ETC, **k))
check("H sxema ExpenseTransactionCreate to'g'ri — qabul",
      _ETC is not None and not _sxema_rad(_ETC, category="a", amount=5, production_type="gips"))
for nom, v in [("inf", float("inf")), ("0", 0), ("True", True), ("'800'", "800"), ("1e20", 1e20)]:
    check(f"H sxema OrderAgreedUpdate {nom} — rad", _OAU is not None and _sxema_rad(_OAU, agreed_amount=v))
check("H sxema OrderAgreedUpdate 800 — qabul", _OAU is not None and not _sxema_rad(_OAU, agreed_amount=800))


def _fayl(nisbiy):
    try:
        with open(os.path.join(ROOT, nisbiy), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _funksiya(src, nomi):
    """`src` dagi JS funksiya tanasi (keyingi `function` gacha)."""
    i = src.find(nomi)
    if i < 0:
        return ""
    j = src.find("\nfunction ", i + len(nomi))
    k = src.find("\nasync function ", i + len(nomi))
    oxir = min([x for x in (j, k) if x > 0] or [len(src)])
    return src[i:oxir]


_debts = _fayl("templates/debts.html")
_orders = _fayl("templates/orders.html")
_qp = _funksiya(_debts, "async function quickPayObligation")
check("H debts.html majburiyat to'lovi — xatoda server sababi (serverSababi)",
      tartibda(_qp, "/api/finance/transactions", "res.ok", "serverSababi(res"), _qp[:80])
check("H debts.html majburiyat to'lovi — faqat \"Xato yuz berdi\" emas",
      "else alert('Xato yuz berdi')" not in _qp)
_ea = _funksiya(_orders, "async function editAgreedAmount")
check("H orders.html kelishilgan summa — detail.message ko'rsatiladi",
      tartibda(_ea, "/agreed-amount", "res.ok", "detail.message", "showMsg('❌ ' + sabab"),
      _ea[:80])
check("H orders.html kelishilgan summa — faqat '❌ Xato' emas",
      "showMsg('❌ Xato', 'error')" not in _ea)
check("H orders.html — UI ham 0 va manfiyni rad etadi (server bilan mos)",
      "if (!val || val <= 0)" in _ea)
_fin = _fayl("templates/finance.html")
_kx = _fayl("templates/kunlik_xarajat.html")
check("H finance.html saveTx — server matnli sababini ko'rsatadi",
      "alert('Xato: ' + (e.detail || ''))" in _fin)
check("H kunlik_xarajat.html — server matnli sababini ko'rsatadi",
      "err.textContent = '❌ ' + (e.detail || 'Xato yuz berdi')" in _kx)
for nom, src in [("finance.html", _funksiya(_fin, "async function saveTx")),
                 ("kunlik_xarajat.html", _kx), ("debts.html", _qp)]:
    check(f"H {nom} — faqat ruxsat etilgan kalitlarni yuboradi",
          "source" not in src.split("/api/finance/transactions", 1)[-1][:600]
          and "company_id" not in src.split("/api/finance/transactions", 1)[-1][:600])

# ══════════════════════════════════════════════════════════════
section("I. Sxema darajasidagi xatolar — 422 qoladi, 500 emas")
# ══════════════════════════════════════════════════════════════
tikla()
for nom, method, url, raw in [
    ("POST tana massiv", "post", "/api/finance/transactions", "[1, 2]"),
    ("POST tana matn", "post", "/api/finance/transactions", '"salom"'),
    ("POST buzilgan JSON", "post", "/api/finance/transactions", '{"category": '),
    ("PUT tana massiv", "put", f"/api/finance/transactions/{TX_ID}", "[Infinity]"),
    ("agreed tana massiv", "put", f"/api/orders/{O_ID}/agreed-amount", "[Infinity]"),
    ("agreed buzilgan JSON", "put", f"/api/orders/{O_ID}/agreed-amount", '{"agreed_amount": '),
]:
    h0 = holat()
    r = xom(C, method, url, raw)
    check(f"I {nom} → 422", r.status_code == 422, (r.status_code, r.text[:120]))
    check(f"I {nom} — hech narsa o'zgarmagan", holat() == h0)
xato = sahifalar_xato(C)
check("I sahifalar 200", not xato, xato)

print("\n" + "=" * 66)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print("=" * 66)
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
