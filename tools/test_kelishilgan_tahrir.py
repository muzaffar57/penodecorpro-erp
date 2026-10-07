#!/usr/bin/env python3
"""
test_kelishilgan_tahrir.py — kech43 darvozasi: 28-band (K42-2). Kelishilgan summani QAYTA
hisoblaydigan joylar pul qaytarish kamaytirishini (`refund_agreed_delta`) yo'qotmasin.

NIMA UCHUN KERAK (asl kod `de24401` da O'LCHANGAN — SQLite va HAQIQIY PostgreSQL 16 AYNAN,
`work/probe43.py`; buyurtma 100 metr × 5 000 = 500 000)
--------------------------------------------------------------------------------
  * Tahrir formasi JORIY (qaytarishdan keyingi) summani ko'rsatib yuborardi: 30 m qaytib
    pul qaytarilgan buyurtma (350 000) o'zgarishsiz saqlansa — “30 % chegirma”, keyingi
    qaytarish narxi 5 000 → 3 500; 10 % chegirmada 37 %, 45 000 o'rniga 31 500.
  * Summasiz tahrir (API) / to'liq qaytgan (0 — maydon bo'sh) — kamaytirish YO'QOLARDI:
    qarz qayta paydo bo'lardi (to'liq to'langan, 150 000 naqd qaytarilgan buyurtmada 150 000
    “qarz”), qaytarishni o'chirish esa summani JAMIDAN oshirardi (500 000 → 1 000 000).
  * Detallar o'zgarsa (chegirma foizi bilan) — 405 000 o'rniga 540 000, o'chirishda 675 000.
  * Qisman topshirilgan buyurtmani “Tayyor” — 150 000 o'rniga 250 000.
  * Qo'lda kelishilgan summa (to'lov paneli) — qaytarish “chegirma” foiziga qo'shilardi.
  * Qo'shimcha: summasiz tahrir, jami o'zgarmasa, CHEGIRMANI ham yo'qotardi (450 000 → 500 000).

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_kelishilgan_tahrir.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_kelishilgan_tahrir.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "kelishilgan_tahrir_test"
_DB = os.path.join(tempfile.gettempdir(), "kelishilgan_tahrir_test.db")

if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
               isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, ReturnItem, Inventory, Payment,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def xabar(r):
    d = js(r)
    if isinstance(d, dict):
        det = d.get("detail")
        if isinstance(det, dict):
            return str(det.get("message") or "")
        return str(det or "")
    return ""


def taxminan(a, b, eps=0.011):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def xavfsiz(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return f"ISTISNO {type(e).__name__}: {e}"


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "KT_admin", "Parol123!", UserRole.ADMIN, "KT Admin", company_id=1)
PRJ = []
for _i in range(40):
    PRJ.append(Project(company_id=1, client_name=f"KT Mijoz {_i}", project_name=f"KT loyiha {_i}",
                       total_budget=0, total_paid=0))
PENO = Inventory(company_id=1, item_name="KT Penoplast", unit="blok", stock_quantity=1000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_db.add_all(PRJ + [PENO])
_db.commit()
PRJ_ID = [p.id for p in PRJ]
PENO_ID = PENO.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r = req(C, "post", "/login", data={"username": "KT_admin", "password": "Parol123!"}, follow_redirects=False)
if _r.status_code != 302:
    print(f"LOGIN BO'LMADI: {_r.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def buyurtma(kelishilgan=None, tolangan=None, narx=50_000, dona=10):
    """API orqali YANGI buyurtma (har biri o'z loyihasida — 8 s takror-himoyasiga tushmasin):
    10 dona × 100 sm = 100 metr, jami 500 000 (5 000 / metr). `kelishilgan` — UI kabi
    `PUT /agreed-amount` (chegirma foizi ham yoziladi). `tolangan` — `POST /api/payments`."""
    _n[0] += 1
    nom = f"KT_D{_n[0]}"
    r = req(C, "post", "/api/orders", json={
        "project_id": PRJ_ID[_n[0] % len(PRJ_ID)], "order_type": "product", "items": [
            {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 100,
             "quantity": dona, "unit_price": narx, "is_coated": False, "penoplast_id": PENO_ID}]})
    d = SessionLocal()
    try:
        oi = d.query(OrderItem).filter(OrderItem.name == nom).order_by(OrderItem.id.desc()).first()
        if oi is None:
            raise RuntimeError(f"buyurtma yaratilmadi: {r.status_code} {r.text[:200]}")
        oid, iid = oi.order_id, oi.id
    finally:
        d.close()
    if kelishilgan is not None:
        req(C, "put", f"/api/orders/{oid}/agreed-amount", json={"agreed_amount": kelishilgan})
    if tolangan:
        req(C, "post", "/api/payments", json={"order_id": oid, "amount": tolangan, "payment_method": "naqd"})
    return oid, iid, nom


def qaytar(oid, iid, nom, miqdor, sabab="Ortiqcha", summa=0, to_stock=False):
    r = req(C, "post", "/api/returns", json={
        "order_id": oid, "order_item_id": iid, "item_name": nom, "quantity": miqdor, "unit": "metr",
        "reason": sabab, "refund_amount": summa, "to_stock": to_stock, "notes": None,
        "coating_applied": False})
    rid = (js(r) or {}).get("id") if (r.status_code == 200 and isinstance(js(r), dict)) else None
    return r, rid


def ri(rid):
    d = SessionLocal()
    try:
        x = d.get(ReturnItem, rid) if rid else None
        if x is None:
            return None
        return {"refund": float(x.refund_amount or 0), "is_refunded": bool(x.is_refunded),
                "delta": (float(x.refund_agreed_delta) if getattr(x, "refund_agreed_delta", None) is not None else None)}
    finally:
        d.close()


def holat(oid):
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        p = d.get(Project, o.project_id)
        ps = [(x.id, float(x.amount), getattr(x, "return_item_id", None))
              for x in d.query(Payment).filter(Payment.order_id == oid).order_by(Payment.id).all()]
        return {"agreed": float(o.agreed_amount) if o.agreed_amount is not None else None,
                "status": str(getattr(o.payment_status, "value", o.payment_status)),
                "tolovlar": ps, "manfiy": [t for t in ps if t[1] < 0],
                "paid": round(sum(t[1] for t in ps), 2), "loyiha": float(p.total_paid or 0),
                "debt": float(o.debt_amount), "archived": bool(o.is_archived)}
    finally:
        d.close()


def api_order(oid):
    return js(req(C, "get", f"/api/orders/{oid}")) or {}


def api_item(oid, iid):
    return next((x for x in (api_order(oid).get("items") or []) if x.get("id") == iid), {})


def pul_qaytdi(rid):
    return req(C, "post", f"/api/returns/{rid}/refund")


def js_round(x):
    """JS `Math.round` (musbat sonlar) — UI summasi."""
    import math
    return float(math.floor(x + 0.5))

def tahrir(oid, nom, agreed=None, dona=10, narx=50_000):
    """UI `updateOrder` tanasi (bitta detal) — `PUT /api/orders/{id}`."""
    d = SessionLocal()
    try:
        prj = d.get(Order, oid).project_id
    finally:
        d.close()
    body = {"project_id": prj, "order_type": "product", "recipe_id": None, "master_id": None,
            "deadline": None, "base_price": None, "loy_kg": None, "items": [
                {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 100,
                 "quantity": dona, "unit_price": narx, "is_coated": False, "penoplast_id": PENO_ID,
                 "price_per_m3": None, "finished_product_id": None, "sub_details": []}]}
    if agreed is not None:
        body["agreed_amount"] = agreed
    return req(C, "put", f"/api/orders/{oid}", json=body)


def ui_qiymat(oid):
    """UI tahrir formasi `final_price` ga yozadigan qiymat (`orders.html` tahrir yuklanishi):
    `kelishilgan_asl ?? agreed_amount`; 0 / bo'sh bo'lsa maydon bo'sh → `undefined`."""
    o = api_order(oid)
    v = o.get("kelishilgan_asl")
    if v is None:
        v = o.get("agreed_amount")
    return v if v else None


def qaytib_pul(oid, iid, nom, miqdor):
    r, rid = qaytar(oid, iid, nom, miqdor, sabab="Ortiqcha")
    rp = pul_qaytdi(rid) if rid else None
    return rid, getattr(rp, "status_code", None)


def bolim_a():
    section("A. /api/orders/{id}: kelishilgan_asl va pul_qaytarish_kamaytirgan")
    oid, iid, nom = buyurtma()
    o = api_order(oid)
    check("A1 pul qaytarishsiz: kamaytirish 0, ASL = kelishilgan (500 000)",
          taxminan(o.get("pul_qaytarish_kamaytirgan"), 0) and taxminan(o.get("kelishilgan_asl"), 500_000), o)
    rid, st = qaytib_pul(oid, iid, nom, 30)
    o = api_order(oid)
    check("A2 30 m pul qaytdi: kelishilgan 350 000, kamaytirish 150 000, ASL 500 000",
          st == 200 and taxminan(o.get("agreed_amount"), 350_000) and taxminan(o.get("pul_qaytarish_kamaytirgan"), 150_000)
          and taxminan(o.get("kelishilgan_asl"), 500_000), (st, o.get("agreed_amount"), o.get("pul_qaytarish_kamaytirgan"), o.get("kelishilgan_asl")))
    r2, rid2 = qaytar(oid, iid, nom, 10)
    o = api_order(oid)
    check("A3 pul qaytarilMAGAN qaytarish kamaytirishga kirmaydi (150 000 qoladi)",
          r2.status_code == 200 and taxminan(o.get("pul_qaytarish_kamaytirgan"), 150_000), (r2.status_code, o.get("pul_qaytarish_kamaytirgan")))
    oid2, iid2, nom2 = buyurtma(kelishilgan=450_000)
    qaytib_pul(oid2, iid2, nom2, 30)
    o2 = api_order(oid2)
    check("A4 10 % chegirma, 30 m: kelishilgan 315 000, kamaytirish 135 000, ASL 450 000",
          taxminan(o2.get("agreed_amount"), 315_000) and taxminan(o2.get("pul_qaytarish_kamaytirgan"), 135_000)
          and taxminan(o2.get("kelishilgan_asl"), 450_000), o2.get("kelishilgan_asl"))


def bolim_b():
    section("B. UI tahriri (o'zgarishsiz saqlash) — summa, chegirma va qaytarish narxi saqlanadi")
    oid, iid, nom = buyurtma()
    qaytib_pul(oid, iid, nom, 30)
    v = ui_qiymat(oid)
    r = tahrir(oid, nom, agreed=v)
    o = api_order(oid)
    check("B1 chegirmasiz: 200, kelishilgan 350 000, chegirma 0 %", r.status_code == 200 and taxminan(o.get("agreed_amount"), 350_000)
          and taxminan(o.get("discount_percent"), 0), (r.status_code, v, o.get("agreed_amount"), o.get("discount_percent")))
    check("B2 qaytarish narxi 5 000 (\u201cchegirma\u201d bo'lib 3 500 ga tushmaydi)",
          taxminan(api_item(oid, iid).get("refund_price_per_unit"), 5000), api_item(oid, iid).get("refund_price_per_unit"))
    r3, rid3 = qaytar(oid, iid, nom, 10)
    check("B3 keyingi 10 m qaytarish avto-summasi 50 000", r3.status_code == 200 and taxminan((ri(rid3) or {}).get("refund"), 50_000),
          (r3.status_code, ri(rid3)))
    oid2, iid2, nom2 = buyurtma(kelishilgan=450_000)
    qaytib_pul(oid2, iid2, nom2, 30)
    r = tahrir(oid2, nom2, agreed=ui_qiymat(oid2))
    o = api_order(oid2)
    check("B4 10 % chegirma: kelishilgan 315 000, chegirma 10 % (37 % emas)",
          r.status_code == 200 and taxminan(o.get("agreed_amount"), 315_000) and taxminan(o.get("discount_percent"), 10),
          (o.get("agreed_amount"), o.get("discount_percent")))
    r4, rid4 = qaytar(oid2, iid2, nom2, 10)
    check("B5 10 % chegirmada keyingi 10 m — 45 000 (31 500 emas)", taxminan((ri(rid4) or {}).get("refund"), 45_000), ri(rid4))
    oid3, iid3, nom3 = buyurtma(tolangan=500_000)
    rid5, _ = qaytib_pul(oid3, iid3, nom3, 30)
    h0 = holat(oid3)
    r = tahrir(oid3, nom3, agreed=ui_qiymat(oid3))
    h = holat(oid3)
    check("B6 to'liq to'langan, 150 000 naqd qaytgan — tahrirdan keyin qarz 0, holat paid, to'lovlar o'zgarmagan",
          r.status_code == 200 and taxminan(h["debt"], 0) and h["status"] == "paid" and h["tolovlar"] == h0["tolovlar"]
          and taxminan(h["agreed"], 350_000), (h0, h))


def bolim_c():
    section("C. Summasiz tahrir (API / bo'sh maydon) — kamaytirish va chegirma yo'qolmaydi")
    oid, iid, nom = buyurtma()
    rid, _ = qaytib_pul(oid, iid, nom, 30)
    r = tahrir(oid, nom)
    check("C1 summasiz tahrir: kelishilgan 350 000 (500 000 emas)", r.status_code == 200 and taxminan(holat(oid)["agreed"], 350_000), holat(oid))
    rd = req(C, "delete", f"/api/returns/{rid}")
    check("C2 qaytarishni o'chirish: 500 000 (jamidan oshmaydi — 650 000 emas)",
          rd.status_code == 200 and taxminan(holat(oid)["agreed"], 500_000), (rd.status_code, holat(oid)))
    oid2, iid2, nom2 = buyurtma()
    rid2, _ = qaytib_pul(oid2, iid2, nom2, 100)
    v = ui_qiymat(oid2)
    r = tahrir(oid2, nom2, agreed=v)
    h = holat(oid2)
    check("C3 to'liq qaytgan (kelishilgan 0): UI maydoni ASL 500 000, tahrirdan keyin kelishilgan 0, qarz 0",
          v == 500_000 and r.status_code == 200 and taxminan(h["agreed"], 0) and taxminan(h["debt"], 0), (v, h))
    r = tahrir(oid2, nom2)
    check("C4 to'liq qaytgan, summasiz tahrir: kelishilgan 0 qoladi", r.status_code == 200 and taxminan(holat(oid2)["agreed"], 0), holat(oid2))
    rd = req(C, "delete", f"/api/returns/{rid2}")
    check("C5 o'chirish: 500 000 (1 000 000 emas)", rd.status_code == 200 and taxminan(holat(oid2)["agreed"], 500_000), holat(oid2))
    oid3, iid3, nom3 = buyurtma(kelishilgan=450_000)
    r = tahrir(oid3, nom3)
    o = api_order(oid3)
    check("C6 pul qaytarishsiz, 10 % chegirma, summasiz tahrir (jami o'zgarmagan): 450 000 va 10 % saqlanadi",
          r.status_code == 200 and taxminan(o.get("agreed_amount"), 450_000) and taxminan(o.get("discount_percent"), 10),
          (o.get("agreed_amount"), o.get("discount_percent")))
    oid4, iid4, nom4 = buyurtma(kelishilgan=520_000)
    r = tahrir(oid4, nom4)
    check("C7 ustama (520 000 > jami) summasiz tahrirda saqlanadi", r.status_code == 200 and taxminan(holat(oid4)["agreed"], 520_000), holat(oid4))


def bolim_d():
    section("D. Detallar o'zgaradi (chegirma foizi bilan)")
    oid, iid, nom = buyurtma(kelishilgan=450_000)
    rid, _ = qaytib_pul(oid, iid, nom, 30)
    ui = js_round(600_000 * (1 - float(api_order(oid).get("discount_percent") or 0) / 100))
    r = tahrir(oid, nom, agreed=ui, dona=12)
    o = api_order(oid)
    check("D1 12 dona (jami 600 000), UI 540 000: kelishilgan 405 000, chegirma 10 %",
          ui == 540_000 and r.status_code == 200 and taxminan(o.get("agreed_amount"), 405_000) and taxminan(o.get("discount_percent"), 10),
          (ui, o.get("agreed_amount"), o.get("discount_percent")))
    rd = req(C, "delete", f"/api/returns/{rid}")
    check("D2 qaytarishni o'chirish: 540 000 (675 000 emas)", rd.status_code == 200 and taxminan(holat(oid)["agreed"], 540_000), holat(oid))
    oid2, iid2, nom2 = buyurtma(kelishilgan=450_000)
    qaytib_pul(oid2, iid2, nom2, 30)
    r = tahrir(oid2, nom2, dona=12)
    check("D3 summasiz, 12 dona: 405 000", r.status_code == 200 and taxminan(holat(oid2)["agreed"], 405_000), holat(oid2))
    oid3, iid3, nom3 = buyurtma()
    qaytib_pul(oid3, iid3, nom3, 90)
    r = tahrir(oid3, nom3, agreed=300_000, dona=6)
    h = holat(oid3)
    check("D4 ASL summa kamaytirishdan kichik (300 000 − 450 000): kelishilgan 0 (manfiy emas)",
          r.status_code == 200 and taxminan(h["agreed"], 0), h)


def bolim_e():
    section("E. Qisman topshirilgan buyurtma \u201cTayyor\u201d")
    oid, iid, nom = buyurtma()
    rd = req(C, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": iid, "quantity": 50}],
                                                 "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    rid, st = qaytib_pul(oid, iid, nom, 20)
    rr = req(C, "post", f"/api/orders/{oid}/ready")
    h = holat(oid)
    check("E1 50 m berildi, 20 m qaytib pul qaytdi, \u201cTayyor\u201d: kelishilgan 150 000 (250 000 emas)",
          rd.status_code == 200 and st == 200 and rr.status_code == 200 and taxminan(h["agreed"], 150_000),
          (rd.status_code, st, rr.status_code, h))
    rx = req(C, "delete", f"/api/returns/{rid}")
    check("E2 qaytarishni o'chirish: 250 000 (jami 250 000 dan oshmaydi)", rx.status_code == 200 and taxminan(holat(oid)["agreed"], 250_000), holat(oid))
    oid2, iid2, nom2 = buyurtma()
    rd2 = req(C, "post", "/api/deliveries", json={"order_id": oid2, "items": [{"order_item_id": iid2, "quantity": 20}],
                                                  "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    rid2, st2 = qaytib_pul(oid2, iid2, nom2, 60)
    rr2 = req(C, "post", f"/api/orders/{oid2}/ready")
    h2 = holat(oid2)
    check("E3 20 m berildi, 60 m qaytib pul qaytdi (300 000), \u201cTayyor\u201d: 100 000 − 300 000 → kelishilgan 0 (manfiy emas)",
          rd2.status_code == 200 and st2 == 200 and rr2.status_code == 200 and h2["agreed"] is not None and taxminan(h2["agreed"], 0),
          (rd2.status_code, st2, rr2.status_code, h2))


def bolim_f():
    section("F. Qo'lda kelishilgan summa (to'lov paneli) — chegirma foizi ASL summadan")
    oid, iid, nom = buyurtma()
    qaytib_pul(oid, iid, nom, 30)
    r = req(C, "put", f"/api/orders/{oid}/agreed-amount", json={"agreed_amount": 300_000})
    o = api_order(oid)
    check("F1 350 000 → 300 000: kelishilgan 300 000, chegirma 10 % (40 % emas), ASL 450 000",
          r.status_code == 200 and taxminan(o.get("agreed_amount"), 300_000) and taxminan(o.get("discount_percent"), 10)
          and taxminan(o.get("kelishilgan_asl"), 450_000), (r.status_code, o.get("agreed_amount"), o.get("discount_percent")))
    check("F2 qaytarish narxi 4 500 (chegirma 10 %)", taxminan(api_item(oid, iid).get("refund_price_per_unit"), 4500),
          api_item(oid, iid).get("refund_price_per_unit"))
    oid2, iid2, nom2 = buyurtma()
    r = req(C, "put", f"/api/orders/{oid2}/agreed-amount", json={"agreed_amount": 400_000})
    check("F3 pul qaytarishsiz: 400 000 → chegirma 20 % (avvalgidek)", taxminan(api_order(oid2).get("discount_percent"), 20),
          api_order(oid2).get("discount_percent"))


def bolim_s():
    section("S. Statik — chaqiruv joylari va UI")
    manba = {f: open(os.path.join(ROOT, f), encoding="utf-8").read() for f in ("crud.py", "main.py", "templates/orders.html")}
    c = manba["crud.py"]

    def tana(nom):
        b = c.find(f"def {nom}(")
        return c[b:c.find("\ndef ", b + 10)] if b >= 0 else ""
    check("S1 crud.pul_qaytarish_kamaytirgan bor (korxona filtri, refunded_at)",
          "ReturnItem.company_id == order.company_id" in tana("pul_qaytarish_kamaytirgan")
          and "refunded_at.isnot(None)" in tana("pul_qaytarish_kamaytirgan"))
    for i, nom in enumerate(("update_order_full", "finalize_partial_order_quantities", "update_order_agreed_amount",
                             "qaytarish_narx_koeffitsienti"), 2):
        check(f"S{i} {nom} kamaytirishni hisobga oladi", "pul_qaytarish_kamaytirgan(db, order)" in tana(nom))
    h = manba["templates/orders.html"]
    check("S6 orders.html tahrir yuklanishi ASL summani yozadi",
          "order.kelishilgan_asl ?? order.agreed_amount" in h and "if (fpEl && order.agreed_amount) fpEl.value" not in h)
    m = manba["main.py"]
    b = m.find('@app.get("/api/orders/{order_id}")')
    t = m[b:m.find("@app.", b + 10)]
    check("S7 /api/orders/{id} javobida kelishilgan_asl va pul_qaytarish_kamaytirgan",
          '"kelishilgan_asl"' in t and '"pul_qaytarish_kamaytirgan"' in t)


for _b in (bolim_a, bolim_b, bolim_c, bolim_d, bolim_e, bolim_f, bolim_s):
    try:
        _b()
    except Exception:                       # noqa: BLE001
        import traceback
        check(f"{_b.__name__} QULADI", False, traceback.format_exc()[-600:])

try:
    engine.dispose()
except Exception:                           # noqa: BLE001
    pass
print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(0 if FAIL == 0 else 1)
