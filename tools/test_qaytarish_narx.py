#!/usr/bin/env python3
"""
test_qaytarish_narx.py — kech42 darvozasi: 4-band, 24-band, brak pul qaytarish va K42-1.

NIMA UCHUN KERAK (asl kod `d947656` da O'LCHANGAN — SQLite va HAQIQIY PostgreSQL 16,
`work/probe42.py`; buyurtma 100 metr × 5 000 = 500 000)
--------------------------------------------------------------------------------
  * 4-band: 10 % chegirmali buyurtma (kelishilgan 450 000) — butun qaytarish 500 000
    (chegirmasiz) yozilardi. FOYDALANUVCHI QARORI (kech41): "Chegirmali narxdan".
  * 24-band: to'lanmagan buyurtmada "Pul qaytdi" −150 000 to'lov yozib, qarzni
    kelishilgan summadan katta ko'rsatardi; 200 000 to'langan + 300 000 qaytgan →
    −300 000 va qarz 300 000 (asli 0). Qaror (kech41, Claude ga topshirilgan): naqd
    faqat mijoz ORTIQCHA to'lagan qism uchun, qolgani qarzdan chegiriladi.
  * Brak — ishlab chiqarish zarari (FOYDALANUVCHI, kech41): mijozga pul HECH QACHON
    qaytarilmaydi; API brak yozuviga 200 bilan −25 000 yozardi.
  * K42-1: `agreed_amount or total_amount` — kelishilgan summa 0 (to'liq qaytgan /
    kechirilgan) "kiritilmagan" deb jami summa olinardi: to'lanmagan, to'liq qaytgan
    buyurtmada qarz 1 000 000; ishga tushish migratsiyasi HAR deployda 0 → jami.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_qaytarish_narx.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_qaytarish_narx.py
"""
import os
import sys
import re
import json
import tempfile
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qaytarish_narx_test"
_DB = os.path.join(tempfile.gettempdir(), "qaytarish_narx_test.db")

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
    import crud, auth, services                    # noqa: E402

from sqlalchemy import text                        # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, ReturnItem, Inventory, Payment, PaymentStatus, OrderType,
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
    auth.create_user(_db, "QN_admin", "Parol123!", UserRole.ADMIN, "QN Admin", company_id=1)
PRJ = []
for _i in range(40):
    PRJ.append(Project(company_id=1, client_name=f"QN Mijoz {_i}", project_name=f"QN loyiha {_i}",
                       total_budget=0, total_paid=0))
PENO = Inventory(company_id=1, item_name="QN Penoplast", unit="blok", stock_quantity=1000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_db.add_all(PRJ + [PENO])
_db.commit()
PRJ_ID = [p.id for p in PRJ]
PENO_ID = PENO.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r = req(C, "post", "/login", data={"username": "QN_admin", "password": "Parol123!"}, follow_redirects=False)
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
    nom = f"QN_D{_n[0]}"
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


# ══════════════════════════════════════════════════════════════
# A. 4-band — qaytarish summasi KELISHILGAN narxdan
# ══════════════════════════════════════════════════════════════
def bolim_a():
    section("A. 4-band — chegirmali buyurtmada qaytarish kelishilgan narxdan")
    oid, iid, nom = buyurtma(kelishilgan=450_000)
    o = api_order(oid)
    it = api_item(oid, iid)
    check("A0 fikstura: kelishilgan 450 000, chegirma 10 %", taxminan(o.get("agreed_amount"), 450_000)
          and taxminan(o.get("discount_percent"), 10), o)
    check("A1 `/api/orders/{id}` refund_price_per_unit = 4 500 (kelishilgan), price_per_unit_final = 5 000 (o'zgarmagan)",
          taxminan(it.get("refund_price_per_unit"), 4_500) and it.get("price_per_unit_final") == 5000, it)
    r, rid = qaytar(oid, iid, nom, 100)
    check("A2 butun qaytarish (summa 0 — server hisoblaydi) → 450 000", r.status_code == 200
          and taxminan((ri(rid) or {}).get("refund"), 450_000), (r.status_code, xabar(r), ri(rid)))

    oid, iid, nom = buyurtma(kelishilgan=450_000)
    u = api_item(oid, iid).get("refund_price_per_unit") or 0
    ui = js_round(30 * u)
    r, rid = qaytar(oid, iid, nom, 30, summa=ui)
    check(f"A3 UI summasi (30 × {u}) = {ui} → 200, AYNAN 135 000", r.status_code == 200 and ui == 135_000
          and taxminan((ri(rid) or {}).get("refund"), 135_000), (r.status_code, xabar(r), ui))
    d = SessionLocal()
    n0 = d.query(ReturnItem).filter(ReturnItem.order_id == oid).count()
    d.close()
    r, rid = qaytar(oid, iid, nom, 50, summa=250_000)
    d = SessionLocal()
    n1 = d.query(ReturnItem).filter(ReturnItem.order_id == oid).count()
    d.close()
    check("A4 eski (chegirmasiz) summa 50 × 5 000 = 250 000 → 400 'kelishilgan qiymatidan', yozuv yo'q",
          r.status_code == 400 and "kelishilgan" in xabar(r) and "225" in xabar(r) and n1 == n0,
          (r.status_code, xabar(r), n0, n1))
    r, rid = qaytar(oid, iid, nom, 50, summa=225_000)
    check("A4b aniq kelishilgan qiymat 225 000 → 200", r.status_code == 200, (r.status_code, xabar(r)))

    # A5 — pul qaytarishdan keyin (joriy kelishilgan kamaygan) narx O'ZGARMAYDI
    oid, iid, nom = buyurtma(kelishilgan=450_000, tolangan=450_000)
    r, r1 = qaytar(oid, iid, nom, 50)
    pr = pul_qaytdi(r1)
    h1 = holat(oid)
    it = api_item(oid, iid)
    r, r2 = qaytar(oid, iid, nom, 50)
    check("A5 1-yarim 225 000 → pul qaytdi: kelishilgan 225 000, naqd −225 000 (to'liq to'langan)",
          pr.status_code == 200 and taxminan(h1["agreed"], 225_000) and [t[1] for t in h1["manfiy"]] == [-225_000.0],
          (pr.status_code, h1))
    check("A5 2-yarim: birlik narxi baribir 4 500, summa 225 000 (ikkinchi qaytarish arzonlashmaydi)",
          taxminan(it.get("refund_price_per_unit"), 4_500) and taxminan((ri(r2) or {}).get("refund"), 225_000),
          (it, ri(r2)))
    pul_qaytdi(r2)
    h2 = holat(oid)
    check("A5 hammasi qaytdi: kelishilgan 0, naqd jami −450 000 (mijoz to'lagani), qarz 0",
          taxminan(h2["agreed"], 0) and taxminan(sum(t[1] for t in h2["manfiy"]), -450_000) and taxminan(h2["debt"], 0),
          h2)

    # A6 — g'alati chegirma: aniq nisbat (yaxlitlangan foiz EMAS)
    oid, iid, nom = buyurtma(kelishilgan=437_777)
    o = api_order(oid)
    r, rid = qaytar(oid, iid, nom, 100)
    check("A6 437 777 / 500 000 (foiz 12.44 — yaxlitlangan) — butun qaytarish AYNAN 437 777",
          taxminan(o.get("discount_percent"), 12.44) and taxminan((ri(rid) or {}).get("refund"), 437_777),
          (o.get("discount_percent"), ri(rid)))
    oid, iid, nom = buyurtma(kelishilgan=437_777)
    s = 0.0
    for m in (33.333, 33.333, 33.334):
        r, rid = qaytar(oid, iid, nom, m)
        s += (ri(rid) or {}).get("refund", 0)
    check(f"A6b uch bo'lak (33.333 + 33.333 + 33.334) yig'indisi {s} — 437 777 ± 1", abs(s - 437_777) <= 1, s)
    # A6c — g'alati chegirma + pul qaytarishdan keyin: 2-yarim ham ASL nisbatdan (delta bilan).
    # Faqat saqlangan (yaxlitlangan) foizga qaytilsa 2-yarim 218 900 bo'lardi (≈ 11 so'm farq).
    oid, iid, nom = buyurtma(kelishilgan=437_777, tolangan=437_777)
    r, r1 = qaytar(oid, iid, nom, 50)
    pul_qaytdi(r1)
    r, r2 = qaytar(oid, iid, nom, 50)
    y = (ri(r1) or {}).get("refund", 0) + (ri(r2) or {}).get("refund", 0)
    check(f"A6c 437 777: yarim + pul qaytdi + yarim = {y} — 437 777 ± 1 (ikkinchi yarim yaxlitlangan foizdan EMAS)",
          abs(y - 437_777) <= 1, (ri(r1), ri(r2)))

    # A7 — qarz kechirilgan (narx chegirmasi EMAS): saqlangan foiz ishlatiladi
    oid, iid, nom = buyurtma(kelishilgan=450_000)
    d = SessionLocal()
    d.get(Order, oid).agreed_amount = 400_000          # kechirish izi (write-off)
    d.commit()
    d.close()
    it = api_item(oid, iid)
    check("A7 kelishilgan kechirish bilan 400 000 ga tushgan — birlik narxi baribir 4 500 (chegirma 10 %)",
          taxminan(it.get("refund_price_per_unit"), 4_500), it)

    # A8 — chegirmasiz va ustama
    oid, iid, nom = buyurtma()
    it = api_item(oid, iid)
    r, rid = qaytar(oid, iid, nom, 100)
    check("A8 chegirmasiz: birlik 5 000, butun qaytarish 500 000",
          taxminan(it.get("refund_price_per_unit"), 5_000) and taxminan((ri(rid) or {}).get("refund"), 500_000),
          (it, ri(rid)))
    oid, iid, nom = buyurtma(kelishilgan=600_000)
    it = api_item(oid, iid)
    check("A8b ustama (kelishilgan 600 000 > jami): birlik 5 000 (qaror faqat chegirma haqida)",
          taxminan(it.get("refund_price_per_unit"), 5_000), it)

    # A9 — brak avvalgidek tan narx
    oid, iid, nom = buyurtma(kelishilgan=450_000)
    d = SessionLocal()
    o_ = d.get(Order, oid)
    oi_ = d.get(OrderItem, iid)
    tan = xavfsiz(services.get_order_item_unit_cost, d, o_, oi_)
    d.close()
    r, rid = qaytar(oid, iid, nom, 5, sabab="Brak")
    check("A9 brak summasi — tan narx (chegirma ta'sir qilmaydi)", r.status_code == 200 and isinstance(tan, (int, float))
          and taxminan((ri(rid) or {}).get("refund"), round(tan * 5)), (tan, ri(rid)))

    # A11 — yarim so'm: server avto-summasi UI (`Math.round` — 0.5 YUQORIGA) bilan bir xil
    oid, iid, nom = buyurtma(kelishilgan=450_050)          # 4 500.5 / metr
    u = api_item(oid, iid).get("refund_price_per_unit")
    r, rid = qaytar(oid, iid, nom, 1)
    check(f"A11 birlik {u} × 1 → server {(ri(rid) or {}).get('refund')} = UI {js_round(1 * (u or 0))} = 4 501",
          taxminan(u, 4_500.5) and taxminan((ri(rid) or {}).get("refund"), 4_501), (u, ri(rid)))

    # A10 — UI: `currentUnitPrice` kelishilgan narxni oladi (HAQIQIY funksiya matni, node)
    html = open(os.path.join(ROOT, "templates", "returns.html"), encoding="utf-8").read()
    m = re.search(r"function currentUnitPrice\(item\)\{.*?\n\}", html, re.S)
    natija = None
    if m:
        kod = ("const document={querySelector:(s)=>({value:globalThis.__sabab})};\n" + m.group(0) + "\n"
               "const out=[];\n"
               "globalThis.__sabab='Ortiqcha';\n"
               "out.push(currentUnitPrice({refund_price_per_unit:4500,price_per_unit_final:5000}));\n"
               "out.push(currentUnitPrice({price_per_unit_final:5000}));\n"
               "out.push(currentUnitPrice({refund_price_per_unit:0,price_per_unit_final:5000}));\n"
               "console.log(JSON.stringify(out));\n")
        p = os.path.join(tempfile.mkdtemp(), "cup.js")
        open(p, "w", encoding="utf-8").write(kod)
        k = subprocess.run(["node", p], capture_output=True, text=True)
        try:
            natija = json.loads(k.stdout.strip().splitlines()[-1])
        except Exception:                  # noqa: BLE001
            natija = (k.stdout, k.stderr[:300])
    check("A10 UI currentUnitPrice: kelishilgan 4 500; eski javobda 5 000; kelishilgan 0 — 0 (5 000 EMAS)",
          natija == [4500, 5000, 0], natija)


# ══════════════════════════════════════════════════════════════
# B. 24-band — "Pul qaytdi": naqd faqat ortiqcha to'langan qism
# ══════════════════════════════════════════════════════════════
def bolim_b():
    section("B. 24-band — to'lanmagan pul qaytarilmaydi, qarzdan chegiriladi")
    oid, iid, nom = buyurtma()
    r, rid = qaytar(oid, iid, nom, 30)
    pr = pul_qaytdi(rid)
    j = js(pr) or {}
    h = holat(oid)
    check("B1 to'lanmagan: 30 m → kelishilgan 350 000, to'lov YO'Q, qarz 350 000, holat unpaid",
          pr.status_code == 200 and taxminan(h["agreed"], 350_000) and h["tolovlar"] == []
          and taxminan(h["debt"], 350_000) and h["status"] == "unpaid", (pr.status_code, h))
    check("B1 javob: naqd 0, kamaydi 150 000, xabarda 'qarzdan chegirildi'", isinstance(j, dict)
          and taxminan(j.get("naqd_qaytarildi"), 0) and taxminan(j.get("kelishilgan_kamaydi"), 150_000)
          and "qarzdan chegirildi, naqd pul qaytarilmadi" in str(j.get("xabar")), j)
    check("B1 yozuv: pul qaytarilgan, delta 150 000", (ri(rid) or {}).get("is_refunded") is True
          and taxminan((ri(rid) or {}).get("delta"), 150_000), ri(rid))
    b1 = (oid, rid)

    oid, iid, nom = buyurtma(tolangan=200_000)
    r, rid = qaytar(oid, iid, nom, 60)
    pr = pul_qaytdi(rid)
    h = holat(oid)
    check("B2 200 000 to'langan, 300 000 qaytdi → naqd YO'Q, kelishilgan 200 000, qarz 0, holat paid",
          pr.status_code == 200 and h["manfiy"] == [] and taxminan(h["agreed"], 200_000)
          and taxminan(h["debt"], 0) and h["status"] == "paid", (pr.status_code, h))

    oid, iid, nom = buyurtma(tolangan=300_000)
    l0 = holat(oid)["loyiha"]
    r, rid = qaytar(oid, iid, nom, 60)
    pr = pul_qaytdi(rid)
    j = js(pr) or {}
    h = holat(oid)
    check("B3 300 000 to'langan, 300 000 qaytdi → kelishilgan 200 000, naqd −100 000 (ortiqcha qism), qarz 0",
          pr.status_code == 200 and taxminan(h["agreed"], 200_000) and [t[1] for t in h["manfiy"]] == [-100_000.0]
          and taxminan(h["debt"], 0) and h["status"] == "paid", (pr.status_code, h))
    check("B3 manfiy to'lov qaytarishga bog'langan, loyiha −100 000, javob naqd 100 000",
          [t[2] for t in h["manfiy"]] == [rid] and taxminan(h["loyiha"], l0 - 100_000)
          and taxminan(j.get("naqd_qaytarildi") if isinstance(j, dict) else None, 100_000)
          and "300 000 so'mga kamaydi; mijozga 100 000 so'm naqd" in str((j or {}).get("xabar")), (h, l0, j))
    b3 = (oid, rid)

    oid, iid, nom = buyurtma(tolangan=500_000)
    r, rid = qaytar(oid, iid, nom, 100)
    pr = pul_qaytdi(rid)
    h = holat(oid)
    check("B4 to'liq to'langan, to'liq qaytdi → naqd −500 000, kelishilgan 0, qarz 0, holat paid",
          pr.status_code == 200 and [t[1] for t in h["manfiy"]] == [-500_000.0] and taxminan(h["agreed"], 0)
          and taxminan(h["debt"], 0) and h["status"] == "paid", (pr.status_code, h))

    oid, rid = b3
    rr = req(C, "delete", f"/api/returns/{rid}")
    j = js(rr) or {}
    h = holat(oid)
    check("B5 B3 ni o'chirish → to'lov o'chdi, kelishilgan ASL 500 000, to'langan 300 000, qarz 200 000, partial",
          rr.status_code == 200 and h["manfiy"] == [] and taxminan(h["agreed"], 500_000)
          and taxminan(h["paid"], 300_000) and taxminan(h["debt"], 200_000) and h["status"] == "partial"
          and j.get("tolov_ochirildi") == 1,
          (rr.status_code, j, h))
    oid, rid = b1
    rr = req(C, "delete", f"/api/returns/{rid}")
    j = js(rr) or {}
    h = holat(oid)
    check("B6 B1 (to'lovsiz pul qaytarish) ni o'chirish → 200, kelishilgan 500 000, tolov_ochirildi 0",
          rr.status_code == 200 and taxminan(h["agreed"], 500_000) and j.get("tolov_ochirildi") == 0
          and taxminan(j.get("pul_bekor_qilindi"), 150_000), (rr.status_code, j, h))

    oid, iid, nom = buyurtma(tolangan=300_000)
    r, rid = qaytar(oid, iid, nom, 60)
    pul_qaytdi(rid)
    h1 = holat(oid)
    pr = pul_qaytdi(rid)
    h2 = holat(oid)
    check("B7 ikkinchi marta 'pul qaytdi' — hech narsa o'zgarmaydi", pr.status_code == 200 and h1 == h2, (h1, h2))


# ══════════════════════════════════════════════════════════════
# C. Brak — mijozga pul qaytarilmaydi
# ══════════════════════════════════════════════════════════════
def bolim_c():
    section("C. Brak yozuviga 'pul qaytdi' — rad")
    oid, iid, nom = buyurtma(tolangan=500_000)
    r, rid = qaytar(oid, iid, nom, 5, sabab="Brak")
    h0, x0 = holat(oid), ri(rid)
    pr = pul_qaytdi(rid)
    check("C1 → 400 'Brak — ishlab chiqarish zarari'", pr.status_code == 400
          and "ishlab chiqarish zarari" in xabar(pr), (pr.status_code, xabar(pr)))
    check("C2 kelishilgan summa, to'lovlar, yozuv O'ZGARMADI", holat(oid) == h0 and ri(rid) == x0,
          (h0, holat(oid), x0, ri(rid)))
    d = SessionLocal()
    v = xavfsiz(crud.mark_refunded, d, rid, refunded_by="QN", company_id=1)
    if not isinstance(v, str):
        v = f"qaytdi: {type(v).__name__}"       # sessiya yopilishidan OLDIN matnga (asl kodda qulamasin)
    d.rollback()
    d.close()
    check("C3 crud.mark_refunded to'g'ridan ham rad (ValueError)", isinstance(v, str) and "ValueError" in v
          and "Brak" in v, v)


# ══════════════════════════════════════════════════════════════
# D. K42-1 — kelishilgan summa 0 haqiqiy qiymat
# ══════════════════════════════════════════════════════════════
def bolim_d():
    section("D. K42-1 — kelishilgan 0 = 0 (jami summa EMAS)")
    oid, iid, nom = buyurtma()
    r, rid = qaytar(oid, iid, nom, 100)
    pul_qaytdi(rid)
    o = api_order(oid)
    h = holat(oid)
    check("D1 to'lanmagan, to'liq qaytgan: bazada 0, API agreed 0, qarz 0 (ilgari 1 000 000)",
          taxminan(h["agreed"], 0) and taxminan(o.get("agreed_amount"), 0) and taxminan(o.get("debt_amount"), 0),
          (h, {k: o.get(k) for k in ("agreed_amount", "debt_amount", "paid_amount", "payment_status")}))
    check("D2 holat paid (hisob yopiq), arxivda", h["status"] == "paid" and h["archived"] is True, h)
    d = SessionLocal()
    pr = xavfsiz(services.calculate_order_profit, d, oid, company_id=1)
    d.close()
    check("D3 foyda hisobi: sotuv narxi 0 (ilgari 500 000)", isinstance(pr, dict)
          and taxminan(pr.get("sotuv_narxi"), 0), str(pr)[:300])

    # D4 — ishga tushish migratsiyasi 0 ni tiriltirmaydi, NULL ni to'ldiradi
    oid2, _i, _n2 = buyurtma()
    d = SessionLocal()
    d.execute(text("UPDATE orders SET agreed_amount = NULL WHERE id = :i"), {"i": oid2})
    d.commit()
    d.close()
    with contextlib.redirect_stdout(_quiet):
        xavfsiz(main._migrate_payment_columns)
    check("D4 migratsiyadan keyin: to'liq qaytgan buyurtma 0 QOLDI", taxminan(holat(oid)["agreed"], 0), holat(oid))
    check("D4b NULL bo'lgan buyurtma jami summaga to'ldirildi (500 000)", taxminan(holat(oid2)["agreed"], 500_000),
          holat(oid2))

    # D5 — model: NULL → jami, 0 → 0
    d = SessionLocal()
    try:
        o = Order(company_id=1, project_id=PRJ_ID[0], order_type=OrderType.PRODUCT, total_amount=700, agreed_amount=None)
        k1 = getattr(o, "kelishilgan_summa", "YO'Q")
        o.agreed_amount = 0
        k2 = getattr(o, "kelishilgan_summa", "YO'Q")
        db2 = o.debt_amount
    finally:
        d.close()
    check("D5 Order.kelishilgan_summa: NULL → 700, 0 → 0; debt_amount 0", k1 == 700.0 and k2 == 0.0 and db2 == 0,
          (k1, k2, db2))

    # D6 — bo'sh (0 so'mlik) buyurtma arxivga TUSHMAYDI
    d = SessionLocal()
    try:
        o = Order(company_id=1, project_id=PRJ_ID[0], order_type=OrderType.PRODUCT, total_amount=0, agreed_amount=0)
        o.payments = []
        xavfsiz(crud._update_order_payment_status, d, o)
        st, ar = o.payment_status, bool(o.is_archived)
    finally:
        d.close()
    check("D6 0 so'mlik buyurtma: unpaid, arxivda EMAS", st == PaymentStatus.UNPAID and ar is False, (st, ar))

    # D7 — qarz to'liq kechirilgan to'lanmagan buyurtma (write-off): kelishilgan 0, qarz 0
    oid3, _i, _n3 = buyurtma()
    d = SessionLocal()
    o = d.get(Order, oid3)
    o.agreed_amount = 0
    xavfsiz(crud._update_order_payment_status, d, o)
    d.commit()
    d.close()
    h = holat(oid3)
    check("D7 kelishilgan 0 (kechirilgan): qarz 0, holat paid", taxminan(h["debt"], 0) and h["status"] == "paid", h)


# ══════════════════════════════════════════════════════════════
# S. Statik
# ══════════════════════════════════════════════════════════════
def bolim_s():
    section("S. Statik")
    manba = {}
    for f in ("crud.py", "main.py", "services.py", "models.py", "delivery_pdf.py", "pdf_service.py"):
        manba[f] = open(os.path.join(ROOT, f), encoding="utf-8").read()
    qoldiq = []
    for f, s in manba.items():
        for i, q in enumerate(s.splitlines(), 1):
            qs = q.split("#")[0]
            if re.search(r"agreed_amount\s+or\s+[a-zA-Z_]", qs) and '"""' not in q and "`" not in q:
                qoldiq.append(f"{f}:{i}")
    check("S1 `.py` da `agreed_amount or <jami>` (0 → jami) YO'Q", qoldiq == [], qoldiq)
    shab = []
    for fn in sorted(os.listdir(os.path.join(ROOT, "templates"))):
        if fn.endswith(".html"):
            s = open(os.path.join(ROOT, "templates", fn), encoding="utf-8").read()
            for i, q in enumerate(s.splitlines(), 1):
                if re.search(r"agreed_amount\s*\|\||agreed_amount\s+or\s+", q):
                    shab.append(f"{fn}:{i}")
    check("S2 shablonlarda `agreed_amount ||` / `or` YO'Q", shab == [], shab)
    m = manba["main.py"]
    check("S3 ishga tushish migratsiyasi faqat `agreed_amount IS NULL`",
          '"WHERE agreed_amount IS NULL"' in m and "agreed_amount IS NULL OR agreed_amount = 0" not in m)
    c = manba["crud.py"]
    b = c.find("def mark_refunded(")
    t = c[b:c.find("\ndef ", b + 10)] if b >= 0 else ""
    i_brak, i_qulf = t.find("ReturnReason.DEFECT"), t.find("_pul_qulfi(")
    check("S4 mark_refunded: brak tekshiruvi qulfdan OLDIN (hech narsa yozilmasdan)",
          0 <= i_brak < i_qulf, (i_brak, i_qulf))
    check("S5 mark_refunded: naqd = min(summa, max(0, to'langan − yangi)) va holat yangilanadi",
          "min(refund_amount, max(0.0, _tolangan - _yangi))" in t and "_update_order_payment_status(db, order)" in t)
    b2 = c.find("def create_return_item(")
    t2 = c[b2:c.find("\ndef ", b2 + 10)] if b2 >= 0 else ""
    check("S6 create_return_item: brakdan boshqasi `qaytarish_birlik_narxi` bilan", "qaytarish_birlik_narxi(db, _o, order_item)" in t2)


for _b in (bolim_a, bolim_b, bolim_c, bolim_d, bolim_s):
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
