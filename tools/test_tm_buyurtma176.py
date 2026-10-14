#!/usr/bin/env python3
"""
test_tm_buyurtma176.py — kech144 (zip 176, AUDIT A-O10 d): buyurtma TAYYOR MAHSULOTdan oladi — EGASI QARORLARI 13.10 21:2x:
«Minusga ruxsat bersin» (yetmasa — tasdiq bilan minus) va band — «Rad etsin».

NIMA UCHUN KERAK (O'LCHANGAN — `work/k176/probe176.py`, asl kod zip 175, `work/natija/k176/probe176_asl.txt`):
  F1 tahrir qoldiqni 0 da qisardi (−10 o'rniga 0), o'chirish keyin 20 m / 20 000 so'm qaytarardi (boshlang'ich 10 / 10 000 — «havodan»);
  F2 minusdagi qoldiqdan yana olish tannarxni 0 dan 5 000 ga OSHIRARDI; F3 band qoldiq e'tiborsiz (10 / 10 band → 6 m — 200, band >
  qoldiq — band buyurtma qotadi); F4 jarayondagi (tayyor emas) mahsulot olinardi; F5 qoralamani faollashtirish tayyor mahsulotni
  tekshirmasdi (−3, ogohlantirishsiz); F6 tekshiruv qulfsiz — parallel ikki buyurtma ogohlantirishsiz minusga.
QOIDA: bo'sh qoldiq (qoldiq − band) yetsa — olinadi; yetmasa: band bor — RAD (400, tasdiq bilan ham), band yo'q — 409 «davom etasizmi?»
(tasdiq bilan minus); tayyor emas — RAD. Tannarx faqat musbat qoldiq qismi bo'yicha.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (F6 poygasi — faqat PG); `TENANT_FILTER=1`.
Asl kodga (zip 175) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_tm_buyurtma176.py
"""
import os
import io
import sys
import json
import time
import tempfile
import threading
import subprocess
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tm_buyurtma176_test"
_T = tempfile.mkdtemp(prefix="tm176_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tm176.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas                                 # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Inventory, FinishedProduct, Order, StockSource,   # noqa: E402
                    ProductionStatus)
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def det(r):
    d = js(r)
    return d.get("detail") if isinstance(d, dict) else None


def det_matn(r):
    d = det(r)
    if isinstance(d, dict):
        return str(d.get("message") or "") + " | " + " | ".join(str(x) for x in (d.get("shortages") or []))
    return str(d or "")


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "tm176_admin", PAROL, UserRole.ADMIN, "TM176 Admin", company_id=1)
PRJ = Project(company_id=1, client_name="TM176 Mijoz", project_name="TM176 loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="TM176 PENO", unit="blok", stock_quantity=100000, min_stock=0, is_penoplast=True,
                 volume_per_unit=1, price_per_unit=500000, category="Penoplast")
s.add_all([PRJ, PENO])
s.commit()
PRJ_ID, PENO_ID = PRJ.id, PENO.id
s.close()


def mijoz():
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    assert c.post("/login", data={"username": "tm176_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)
    return c


A = mijoz()
_n = {"tm": 0, "d": 0}


def yangi_tm(miqdor=10.0, holat=ProductionStatus.READY, band=0.0):
    _n["tm"] += 1
    nom = f"TM176 mahsulot {_n['tm']}"

    def f(s):
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=False, quantity=miqdor, produced_quantity=miqdor,
                             unit="metr", unit_price=0, cost_price=miqdor * 1000, unit_cost_stable=1000, source=StockSource.PRODUCED,
                             penoplast_id=PENO_ID, unit_volume_m3=0.01, production_status=holat, reserved_quantity=band)
        s.add(fp)
        s.flush()
        return fp.id
    return db_ishi(f)


def detal(uz, fid):
    _n["d"] += 1                           # 8 s «takroriy yuborish» imzosi (nom, tur, soni) — har detal nomi noyob
    return {"name": f"TM176 detal {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": uz, "quantity": 1,
            "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID, "finished_product_id": fid}


def tana(*d, qoralama=False):
    t = {"project_id": PRJ_ID, "order_type": "product", "loy_kg": 0, "items": list(d)}
    if qoralama:
        t["is_draft"] = True
    return t


def tm(fid):
    def f(s):
        x = s.get(FinishedProduct, fid)
        return (round(float(x.quantity), 3), round(float(x.cost_price or 0), 2), round(float(x.reserved_quantity or 0), 3))
    return db_ishi(f)


def buyurtma(c, *d, tasdiq=False, qoralama=False):
    return c.post("/api/orders" + ("?confirm_shortage=true" if tasdiq else ""), json=tana(*d, qoralama=qoralama))


def tahrir(c, oid, fid, uz, tasdiq=False):
    o = js(c.get(f"/api/orders/{oid}"))
    it = (o.get("items") or [{}])[0]
    t = tana(dict(detal(uz, fid), id=it.get("id"), name=it.get("name")))
    t["notes"] = o.get("notes")
    return c.put(f"/api/orders/{oid}" + ("?confirm_shortage=true" if tasdiq else ""), json=t)


def holat(oid):
    def f(s):
        o = s.get(Order, oid)
        return getattr(o.status, "value", o.status) if o else None
    return db_ishi(f)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Minus (egasi qarori «Minusga ruxsat bersin») — tannarx faqat musbat qism bo'yicha (F1, F2)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FA = yangi_tm(10)
r = buyurtma(A, detal(15, FA))
check("M1 15 m / 10 m, tasdiqsiz — 409 «davom etasizmi?», ro'yxatda «omborda 10 metr, kerak 15 metr»",
      r.status_code == 409 and (det(r) or {}).get("type") == "stock_shortage_warning" and "omborda 10 metr, kerak 15 metr" in det_matn(r)
      and tm(FA) == (10.0, 10000.0, 0.0), (r.status_code, det_matn(r), tm(FA)))
rx = buyurtma(A, detal(15, FA), tasdiq=True)
OX = js(rx).get("id")
check("M2 tasdiq bilan — 200, qoldiq −5, tannarx 0", rx.status_code == 200 and tm(FA) == (-5.0, 0.0, 0.0), (rx.status_code, tm(FA)))
r = buyurtma(A, detal(3, FA))
check("M3 minusdagi mahsulotdan yana 3 m, tasdiqsiz — 409", r.status_code == 409 and tm(FA) == (-5.0, 0.0, 0.0), (r.status_code, tm(FA)))
ry = buyurtma(A, detal(3, FA), tasdiq=True)
OY = js(ry).get("id")
check("M4 tasdiq bilan — −8, tannarx 0 da QOLDI (asl: 0 → 5 000 — F2)", ry.status_code == 200 and tm(FA) == (-8.0, 0.0, 0.0),
      (ry.status_code, tm(FA)))
A.delete(f"/api/orders/{OY}")
check("M5 3 m li buyurtma o'chirildi — −5, tannarx 0", tm(FA) == (-5.0, 0.0, 0.0), tm(FA))
A.delete(f"/api/orders/{OX}")
check("M6 15 m li buyurtma o'chirildi — boshlang'ich 10 m / 10 000 so'm AYNAN (asl: 10 m da 15 000 — 5 000 «havodan»)",
      tm(FA) == (10.0, 10000.0, 0.0), tm(FA))

FB = yangi_tm(10)
ob = js(buyurtma(A, detal(15, FB), tasdiq=True)).get("id")
r = tahrir(A, ob, FB, 20)
check("M7 tahrir 15 → 20 (minusda), tasdiqsiz — 409 (ilgari tekshirilmasdi), hech narsa o'zgarmadi",
      r.status_code == 409 and (det(r) or {}).get("type") == "stock_shortage_warning" and tm(FB) == (-5.0, 0.0, 0.0),
      (r.status_code, det_matn(r), tm(FB)))
r = tahrir(A, ob, FB, 20, tasdiq=True)
check("M8 tasdiq bilan — qoldiq −10 (asl: 0 ga QISILARDI — F1), tannarx 0", r.status_code == 200 and tm(FB) == (-10.0, 0.0, 0.0),
      (r.status_code, det_matn(r), tm(FB)))
A.delete(f"/api/orders/{ob}")
check("M9 o'chirildi — boshlang'ich 10 m / 10 000 AYNAN (asl: 20 m / 20 000)", tm(FB) == (10.0, 10000.0, 0.0), tm(FB))

FC = yangi_tm(10)
oc = js(buyurtma(A, detal(6, FC))).get("id")
check("M10 6 m / 10 m — 200, qoldiq 4 / 4 000", oc and tm(FC) == (4.0, 4000.0, 0.0), tm(FC))
r = tahrir(A, oc, FC, 12)
check("M11 tahrir 6 → 12 (6 qo'shimcha, bor 4), tasdiqsiz — 409", r.status_code == 409 and tm(FC) == (4.0, 4000.0, 0.0),
      (r.status_code, tm(FC)))
r = tahrir(A, oc, FC, 12, tasdiq=True)
check("M12 tasdiq bilan — −2, tannarx 0 (faqat musbat 4 m tannarxi ketdi)", r.status_code == 200 and tm(FC) == (-2.0, 0.0, 0.0),
      (r.status_code, tm(FC)))
r = tahrir(A, oc, FC, 3)
check("M13 tahrir 12 → 3 (9 m qaytdi) — qoldiq 7, tannarx 7 000 (musbatga chiqqan 7 m)", r.status_code == 200 and tm(FC) == (7.0, 7000.0, 0.0),
      (r.status_code, det_matn(r), tm(FC)))
A.delete(f"/api/orders/{oc}")
check("M14 o'chirildi — 10 / 10 000 AYNAN", tm(FC) == (10.0, 10000.0, 0.0), tm(FC))
FD = yangi_tm(10)
od = js(buyurtma(A, detal(4, FD))).get("id")
r = tahrir(A, od, FD, 7)
check("M15 musbat qoldiq ichida tahrir 4 → 7 — tasdiqsiz 200, 3 / 3 000 (avvalgidek)", r.status_code == 200 and tm(FD) == (3.0, 3000.0, 0.0),
      (r.status_code, tm(FD)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Band (egasi qarori «Rad etsin») — tasdiq bilan ham o'tmaydi (F3)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FE = yangi_tm(10, band=10)
r = buyurtma(A, detal(6, FE))
check("B1 10 m, hammasi band, 6 m — 400 (asl: 200 va band > qoldiq): «shundan 10 metr boshqa buyurtmaga band — bo'sh 0 metr, kerak 6 metr»",
      r.status_code == 400 and "shundan 10 metr boshqa buyurtmaga band — bo'sh 0 metr, kerak 6 metr" in det_matn(r)
      and tm(FE) == (10.0, 10000.0, 10.0), (r.status_code, det_matn(r), tm(FE)))
r = buyurtma(A, detal(6, FE), tasdiq=True)
check("B2 tasdiq bilan ham — 400, qoldiq va band o'zgarmadi", r.status_code == 400 and tm(FE) == (10.0, 10000.0, 10.0), (r.status_code, tm(FE)))
FF = yangi_tm(10, band=4)
r = buyurtma(A, detal(6, FF))
check("B3 10 m, 4 band, 6 m (bo'sh 6) — 200, qoldiq 4 (band 4 tegilmadi)", r.status_code == 200 and tm(FF) == (4.0, 4000.0, 4.0),
      (r.status_code, det_matn(r), tm(FF)))
r = buyurtma(A, detal(1, FF), tasdiq=True)
check("B4 yana 1 m (bo'sh 0, band 4) — tasdiq bilan ham 400 (minus band hisobidan bo'lmaydi)",
      r.status_code == 400 and "bo'sh 0 metr" in det_matn(r) and tm(FF) == (4.0, 4000.0, 4.0), (r.status_code, det_matn(r), tm(FF)))
FG = yangi_tm(10, band=4)
r = buyurtma(A, detal(8, FG), tasdiq=True)
check("B5 10 m, 4 band, 8 m — 400 «bo'sh 6 metr, kerak 8 metr»", r.status_code == 400 and "bo'sh 6 metr, kerak 8 metr" in det_matn(r)
      and tm(FG) == (10.0, 10000.0, 4.0), (r.status_code, det_matn(r)))
FH = yangi_tm(10)
oh = js(buyurtma(A, detal(5, FH))).get("id")
db_ishi(lambda s: setattr(s.get(FinishedProduct, FH), "reserved_quantity", 5.0))      # qolgan 5 m boshqa buyurtmaga band bo'ldi
r = tahrir(A, oh, FH, 6, tasdiq=True)
check("B6 tahrir 5 → 6 (qolgan 5 m band) — 400, tahrir BUTUNLAY bekor (qoldiq 5, detal 5 m)",
      r.status_code == 400 and "band" in det_matn(r) and tm(FH) == (5.0, 5000.0, 5.0)
      and float((js(A.get(f"/api/orders/{oh}")).get("items") or [{}])[0].get("length") or 0) == 5.0,
      (r.status_code, det_matn(r), tm(FH)))
r = tahrir(A, oh, FH, 3)
check("B7 kamaytirish 5 → 3 — band bo'lsa ham 200 (qaytadi)", r.status_code == 200 and tm(FH) == (7.0, 7000.0, 5.0), (r.status_code, tm(FH)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. Jarayondagi (tayyor emas) mahsulot — rad (F4)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FJ = yangi_tm(10, holat=ProductionStatus.IN_PROGRESS)
r = buyurtma(A, detal(6, FJ), tasdiq=True)
check("J1 jarayondagi mahsulot — tasdiq bilan ham 400 «hali ishlab chiqarilmoqda (tayyor emas)» (asl: 200, olinardi)",
      r.status_code == 400 and "tayyor emas" in det_matn(r) and tm(FJ) == (10.0, 10000.0, 0.0), (r.status_code, det_matn(r), tm(FJ)))
r = buyurtma(A, detal(6, FJ), qoralama=True)
check("J2 QORALAMA — 200 (ombor tegilmaydi; jarayonga olishda tekshiriladi)", r.status_code == 200 and tm(FJ) == (10.0, 10000.0, 0.0),
      (r.status_code, det_matn(r)))
QJ = js(r).get("id")
r = A.post(f"/api/orders/{QJ}/activate?confirm_shortage=true")
check("J3 jarayondagi mahsulotli qoralamani jarayonga olish — 400, qoralama qoldi", r.status_code == 400 and "tayyor emas" in det_matn(r)
      and holat(QJ) == "draft" and tm(FJ) == (10.0, 10000.0, 0.0), (r.status_code, det_matn(r), holat(QJ)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Qoralamani jarayonga olish — tayyor mahsulot tekshiriladi (F5)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FQ = yangi_tm(10)
QQ = js(buyurtma(A, detal(8, FQ), qoralama=True)).get("id")
db_ishi(lambda s: setattr(s.get(FinishedProduct, FQ), "quantity", 5.0) or setattr(s.get(FinishedProduct, FQ), "cost_price", 5000.0))
r = A.post(f"/api/orders/{QQ}/activate")
check("Q1 8 m qoralama, qoldiq 5 — 409 «davom etasizmi?» (asl: 200, −3 ogohlantirishsiz), qoralama qoldi, qoldiq 5",
      r.status_code == 409 and (det(r) or {}).get("type") == "stock_shortage_warning" and "omborda 5 metr, kerak 8 metr" in det_matn(r)
      and holat(QQ) == "draft" and tm(FQ) == (5.0, 5000.0, 0.0), (r.status_code, det_matn(r), holat(QQ), tm(FQ)))
r = A.post(f"/api/orders/{QQ}/activate?confirm_shortage=true")
check("Q2 tasdiq bilan — 200, jarayonda, qoldiq −3, tannarx 0", r.status_code == 200 and holat(QQ) == "in_progress"
      and tm(FQ) == (-3.0, 0.0, 0.0), (r.status_code, det_matn(r), holat(QQ), tm(FQ)))
FR = yangi_tm(10)
QR = js(buyurtma(A, detal(6, FR), qoralama=True)).get("id")
db_ishi(lambda s: setattr(s.get(FinishedProduct, FR), "reserved_quantity", 8.0))
r = A.post(f"/api/orders/{QR}/activate?confirm_shortage=true")
check("Q3 band (bo'sh 2, kerak 6) — tasdiq bilan ham 400, qoralama qoldi", r.status_code == 400 and "band" in det_matn(r)
      and holat(QR) == "draft" and tm(FR) == (10.0, 10000.0, 8.0), (r.status_code, det_matn(r), holat(QR)))
FS = yangi_tm(10)
QS = js(buyurtma(A, detal(4, FS), qoralama=True)).get("id")
r = A.post(f"/api/orders/{QS}/activate")
check("Q4 yetarli — tasdiqsiz 200, 6 / 6 000 (avvalgidek)", r.status_code == 200 and tm(FS) == (6.0, 6000.0, 0.0), (r.status_code, tm(FS)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Taklif ogohlantirishlari — band ham ko'rinadi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FT = yangi_tm(10, band=10)
_tb = schemas.OrderCreate(**tana(detal(3, FT)))
_og = db_ishi(lambda s: crud.taklif_ogohlantirishlari(s, 1, _tb))
check("T1 taklif (omborga tegmaydi) — ogohlantirishlarda band qatori", any("band" in str(x) for x in (_og or [])), _og)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. Parallel ikki buyurtma — qulf ostida qayta tekshiruv (F6) — faqat PG")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    FP = yangi_tm(10)
    _asl_chk = crud.check_finished_for_order

    def _sekin(*a, **k):                   # ikkalasi ham tekshiruvdan o'tsin (qoldiq 10 ni ko'rib), so'ng olishga bir vaqtda
        r_ = _asl_chk(*a, **k)
        time.sleep(0.6)
        return r_
    crud.check_finished_for_order = _sekin
    to_siq = threading.Barrier(2)
    nat = []

    def _yur():
        c = mijoz()
        to_siq.wait()
        nat.append(buyurtma(c, detal(6, FP)).status_code)
    _t = [threading.Thread(target=_yur) for _ in range(2)]
    [x.start() for x in _t]
    [x.join(60) for x in _t]
    crud.check_finished_for_order = _asl_chk
    check("P1 ikki parallel 6 m / 10 m (tasdiqsiz) — biri 200, ikkinchisi 409 (asl: ikkalasi 200, −2 ogohlantirishsiz), qoldiq 4",
          sorted(nat) == [200, 409] and tm(FP) == (4.0, 4000.0, 0.0), (sorted(nat), tm(FP)))
else:
    print("  · P (parallel) — faqat PG rejimida")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. «▶️ Jarayonga olish» (orders.html, node): 409 — so'raydi, «Davom etish» — `confirm_shortage=true`")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_orders = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_base = open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8").read()


def js_funksiya(matn, nom_):
    for bosh in ("async function " + nom_ + "(", "function " + nom_ + "("):
        i = matn.find(bosh)
        if i >= 0:
            k = matn.find("\n}", i)
            return matn[i:k + 2] if k >= 0 else ""
    return ""


_kod = "\n".join(js_funksiya(_base, n) for n in ("xatoSababi", "yukSessiyaKor", "amalSababi")) + "\n" + js_funksiya(_orders, "activateDraft")
_harness = r"""
const LOG = []; let JAVOBLAR = []; let HA = true; const XABAR = [];
globalThis.document = { getElementById: () => null };
globalThis.location = { reload() {} };
globalThis.setTimeout = () => 0;
globalThis.escapeHtml = s => String(s);
globalThis.showMsg = (t, k) => XABAR.push([String(t), k]);
globalThis.showConfirmModal = async () => true;
globalThis.customConfirm = async (a, b) => { LOG.push('so\'radi: ' + String(a)); return HA; };
function javob(holat, tana) { return { ok: holat >= 200 && holat < 300, status: holat, json: async () => tana,
  clone() { return javob(holat, tana); } }; }
globalThis.fetch = async (url, opt) => { LOG.push(String(url)); return JAVOBLAR.shift(); };
let selectedOrderId = 77;
__KOD__
(async () => {
  const S409 = {detail: {type: 'stock_shortage_warning', message: 'Tayyor mahsulot omborda yetmaydi', shortages: ['🏭 X: omborda 5 metr, kerak 8 metr']}};
  JAVOBLAR = [javob(409, S409), javob(200, {success: true})]; HA = true;
  await activateDraft();
  const a = {log: LOG.slice(), xabar: XABAR.slice()};
  LOG.length = 0; XABAR.length = 0;
  JAVOBLAR = [javob(409, S409)]; HA = false;
  await activateDraft();
  const b = {log: LOG.slice(), xabar: XABAR.slice()};
  LOG.length = 0; XABAR.length = 0;
  JAVOBLAR = [javob(400, {detail: {success: false, message: "Tayyor mahsulotni olib bo'lmaydi!", shortages: ['🏭 Y: band']}})]; HA = true;
  await activateDraft();
  const c = {log: LOG.slice(), xabar: XABAR.slice()};
  console.log(JSON.stringify({a, b, c}));
})().catch(e => console.log(JSON.stringify({xato: String(e)})));
"""
_skript = _harness.replace("__KOD__", _kod)
try:
    _p = subprocess.run(["node", "-e", _skript], capture_output=True, text=True, timeout=60)
    _u = json.loads((_p.stdout.strip().splitlines() or ["{}"])[-1])
except Exception as e:                     # noqa: BLE001
    _u = {"xato": f"{type(e).__name__}: {e}"}
_a, _b, _c = _u.get("a") or {}, _u.get("b") or {}, _u.get("c") or {}
check("U1 409 → so'radi, «Davom etish» → AYNAN o'sha so'rov `?confirm_shortage=true` bilan; xabar «jarayonga olindi (… minusda)»",
      _a.get("log") == ["/api/orders/77/activate", "so'radi: ⚠ Tayyor mahsulot omborda yetmaydi", "/api/orders/77/activate?confirm_shortage=true"]
      and any("jarayonga olindi" in x[0] and "minus" in x[0] for x in _a.get("xabar") or []), _u)
check("U2 «Bekor» — ikkinchi so'rov YO'Q", _b.get("log") == ["/api/orders/77/activate", "so'radi: ⚠ Tayyor mahsulot omborda yetmaydi"]
      and not (_b.get("xabar") or []), _b)
check("U3 400 (band) — so'ramaydi, sabab va ro'yxat", _c.get("log") == ["/api/orders/77/activate"]
      and any("Tayyor mahsulotni olib bo'lmaydi" in x[0] and "band" in x[0] for x in _c.get("xabar") or []), _c)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
