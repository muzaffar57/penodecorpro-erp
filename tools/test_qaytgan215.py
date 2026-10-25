#!/usr/bin/env python3
"""
test_qaytgan215.py — kech157 (zip 215 «Qaytgan miqdor eslatmada» — egasi tanlovlari 25.10: «Qaytgan miqdor eslatmada (Tavsiya)»;
review213 №5; mustaqil tekshiruvdan keyin — «Brak alohida (Tavsiya)»).

NIMA UCHUN KERAK
  Zip 213 eslatmasi («ℹ️ Bu loyihada: ORD-064-3 — 72 m berilgan (19.10)») mijoz QAYTARGAN miqdorni ko'rsatmasdi: 72 m berilib 10 m
  qaytgan, hatto hammasi qaytgan detal ham «… m berilgan» bo'lib turardi (O'LCHANGAN — `work/k215/probe215.py`, zip 214 kodi, SQLite = PG).
  Endi: «ORD-064-3 — 72 m berilgan (19.10), 10 m qaytgan»; ochiq buyurtmada — «…, 10 m qaytgan, 10 m hali berilmagan».
  Qaytgan = brakdan BOSHQA qaytarish yozuvlarining TOPSHIRILGANDAN olingan qismi (`quantity − ortiqcha_miqdor`); omborga qo'yilgan ortiqcha
  (berilmagan qism) sanalmaydi; berilgandan ko'p emas. Brak (mijozda singan detal ham «Brak yozish» bilan yoziladi) — ALOHIDA: «…, 8 m brak»
  (shu detalga yozilgan hamma brak). «0» ga yaxlitlangan son yozilmaydi.
BO'LIMLAR
  S — manba: qoida joyi (`crud.loyiha_berilgan_detallar`), brauzer `takrorYozuv`.
  J — `takrorYozuv` (node): yopiq / ochiq / qaytgansiz / eski server (maydon yo'q) / kasr / berilmagan — AYNAN matn (bo'linmas bo'shliq bilan).
  A — `GET /api/projects/{id}/berilgan-detallar`: «Mijoz iltimosi», «Notog'ri o'lcham», «Ortiqcha» (topshirilgandan / omborga), brak, hammasi
      qaytgan, ikki qaytarish, bir buyurtmadagi bir xil nomli 2 detal (jamlanadi, kasr), qaytarish o'chirilsa, eski yozuv (`ortiqcha_miqdor`
      yo'q), detalsiz eski yozuv, berilgandan ko'p (eski yozuv) — chegaralanadi, o'chirilgan buyurtma, `istisno`, N+1 yo'q.
  U — HAQIQIY Chromium + lokal server: nom yozilganda «…, 10 m qaytgan» (yopiq va ochiq buyurtma), brakli detalda «qaytgan» yo'q,
      telefon (360 px) — eslatma qatordan toshmaydi, JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (U bo'limi faqat SQLite / TF1 da).
Asl kodga (zip 214) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_qaytgan215.py
"""
import os
import io
import re
import sys
import json
import glob
import time
import socket
import tempfile
import datetime
import threading
import subprocess
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qaytgan215_test"
_T = tempfile.mkdtemp(prefix="k215_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k215.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

NB = chr(0xA0)                                     # bo'linmas bo'shliq (son / birlik / sana orasida)
YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        if callable(detail):
            try:
                detail = detail()
            except Exception as e:         # noqa: BLE001
                detail = f"{type(e).__name__}: {e}"
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


def _fn(src, bosh, keyingi="\nfunction "):
    i = src.find(bosh)
    if i < 0:
        return ""
    j = src.find(keyingi, i + len(bosh))
    return src[i:j if j > 0 else len(src)]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ORD = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
CRUD_SRC = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
_cf = CRUD_SRC[CRUD_SRC.find("def loyiha_berilgan_detallar("):]
_cf = _cf[:_cf.find("\ndef ", 10)]
check("S1 `crud.loyiha_berilgan_detallar`: qaytgan — brakdan boshqa qaytarishlarning topshirilgandan olingan qismi (`quantity − "
      "ortiqcha_miqdor`), oldindan yuklangan `Order.returns` dan, berilgandan ko'p emas; javobda `qaytgan` / `qaytgan_matn`",
      "_r.reason == ReturnReason.DEFECT" in _cf and "float(_r.quantity or 0) - float(_r.ortiqcha_miqdor or 0)" in _cf
      and "for _r in (_o.returns or [])" in _cf and "_qayt = min(_qayt, _miq)" in _cf and 'd["qaytgan_matn"]' in _cf
      and 'd["brak_matn"]' in _cf and "selectinload(Order.returns)" in _cf, len(_cf))
_ty = _fn(ORD, "function takrorYozuv(d)")
check("S2 brauzer `takrorYozuv`: «, N m qaytgan» — faqat berilgan bo'lsa va `qaytgan` > 0; «, N m brak» (eski server — maydonsiz — avvalgidek)",
      bool(_ty) and "Number(d.qaytgan) > 0" in _ty and "qaytgan` : ''" in _ty and "${ber}${qay}${brk}" in _ty and "brak` : ''" in _ty,
      _ty[:400])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J — eslatma matni (node)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_JS_HOLLAR = [
    {"buyurtma": "ORD-064-3", "berilgan": 72, "berilgan_matn": "72", "birlik": "m", "sana_matn": "19.10", "ochiq": False, "qolgan": 0,
     "qolgan_matn": "0", "qaytgan": 10, "qaytgan_matn": "10"},
    {"buyurtma": "ORD-064-2", "berilgan": 30, "berilgan_matn": "30", "birlik": "m", "sana_matn": "20.10", "ochiq": True, "qolgan": 10,
     "qolgan_matn": "10", "qaytgan": 10, "qaytgan_matn": "10"},
    {"buyurtma": "ORD-064-1", "berilgan": 72, "berilgan_matn": "72", "birlik": "m", "sana_matn": "18.10", "ochiq": False, "qolgan": 0,
     "qolgan_matn": "0", "qaytgan": 0, "qaytgan_matn": "0"},
    {"buyurtma": "ORD-064-5", "berilgan": 72, "berilgan_matn": "72", "birlik": "m", "sana_matn": "18.10", "ochiq": False, "qolgan": 0,
     "qolgan_matn": "0"},
    {"buyurtma": "ORD-064-4", "berilgan": 0, "berilgan_matn": "0", "birlik": "m", "sana_matn": "", "ochiq": True, "qolgan": 72,
     "qolgan_matn": "72", "qaytgan": 0, "qaytgan_matn": "0"},
    {"buyurtma": "ORD-070-1", "berilgan": 12.5, "berilgan_matn": "12,5", "birlik": "dona", "sana_matn": "01.10.2025", "ochiq": False,
     "qolgan": 0, "qolgan_matn": "0", "qaytgan": 2.5, "qaytgan_matn": "2,5"},
    {"buyurtma": "ORD-070-2", "berilgan": 0, "berilgan_matn": "0", "birlik": "m", "sana_matn": "", "ochiq": True, "qolgan": 5,
     "qolgan_matn": "5", "qaytgan": 3, "qaytgan_matn": "3"},
    {"buyurtma": "ORD-070-3", "berilgan": 20, "berilgan_matn": "20", "birlik": "m", "sana_matn": "25.10", "ochiq": False, "qolgan": 0,
     "qolgan_matn": "0", "qaytgan": 0.003, "qaytgan_matn": "0", "brak": 0.001, "brak_matn": "0"},
    {"buyurtma": "ORD-064-3", "berilgan": 72, "berilgan_matn": "72", "birlik": "m", "sana_matn": "19.10", "ochiq": False, "qolgan": 0,
     "qolgan_matn": "0", "qaytgan": 10, "qaytgan_matn": "10", "brak": 8, "brak_matn": "8"},
    {"buyurtma": "ORD-064-4", "berilgan": 0, "berilgan_matn": "0", "birlik": "m", "sana_matn": "", "ochiq": True, "qolgan": 72,
     "qolgan_matn": "72", "qaytgan": 0, "qaytgan_matn": "0", "brak": 3, "brak_matn": "3"},
    {"buyurtma": "ORD-064-2", "berilgan": 30, "berilgan_matn": "30", "birlik": "m", "sana_matn": "20.10", "ochiq": True, "qolgan": 10,
     "qolgan_matn": "10", "qaytgan": 0, "qaytgan_matn": "0", "brak": 2.5, "brak_matn": "2,5"},
    {"buyurtma": "ORD-070-4", "berilgan": 0, "berilgan_matn": "0", "birlik": "m", "sana_matn": "", "ochiq": False, "qolgan": 0,
     "qolgan_matn": "0", "qaytgan": 3, "qaytgan_matn": "3"},
]
_JS_KUT = [
    f"ORD-064-3 —{NB}72{NB}m{NB}berilgan{NB}(19.10), 10{NB}m{NB}qaytgan",
    f"ORD-064-2 —{NB}30{NB}m{NB}berilgan{NB}(20.10), 10{NB}m{NB}qaytgan, 10{NB}m{NB}hali{NB}berilmagan",
    f"ORD-064-1 —{NB}72{NB}m{NB}berilgan{NB}(18.10)",
    f"ORD-064-5 —{NB}72{NB}m{NB}berilgan{NB}(18.10)",
    f"ORD-064-4 —{NB}72{NB}m{NB}(hali{NB}berilmagan)",
    f"ORD-070-1 —{NB}12,5{NB}dona{NB}berilgan{NB}(01.10.2025), 2,5{NB}dona{NB}qaytgan",
    f"ORD-070-2 —{NB}5{NB}m{NB}(hali{NB}berilmagan)",
    f"ORD-070-3 —{NB}20{NB}m{NB}berilgan{NB}(25.10)",
    f"ORD-064-3 —{NB}72{NB}m{NB}berilgan{NB}(19.10), 10{NB}m{NB}qaytgan, 8{NB}m{NB}brak",
    f"ORD-064-4 —{NB}72{NB}m{NB}(hali{NB}berilmagan), 3{NB}m{NB}brak",
    f"ORD-064-2 —{NB}30{NB}m{NB}berilgan{NB}(20.10), 2,5{NB}m{NB}brak, 10{NB}m{NB}hali{NB}berilmagan",
    f"ORD-070-4 —{NB}",
]
_node = None
if _ty:
    _p = subprocess.run(["node", "-e", _ty + "\nconsole.log(JSON.stringify(" + json.dumps(_JS_HOLLAR) + ".map(takrorYozuv)));"],
                        capture_output=True, text=True, timeout=60)
    try:
        _node = json.loads(_p.stdout.strip().splitlines()[-1])
    except Exception:                      # noqa: BLE001
        _node = _p.stderr[-300:]
_nj = _node if isinstance(_node, list) and len(_node) == len(_JS_KUT) else [None] * len(_JS_KUT)
check("J1 yopiq buyurtma, 10 m qaytgan — «ORD-064-3 — 72 m berilgan (19.10), 10 m qaytgan» (egasi namunasi)", _nj[0] == _JS_KUT[0],
      (_nj[0], _JS_KUT[0]))
check("J2 ochiq buyurtma — «… 30 m berilgan (20.10), 10 m qaytgan, 10 m hali berilmagan» (tartib: berilgan → qaytgan → berilmagan)",
      _nj[1] == _JS_KUT[1], (_nj[1], _JS_KUT[1]))
check("J3 qaytgan 0 — «qaytgan» so'zi yo'q (zip 213 matni AYNAN)", _nj[2] == _JS_KUT[2], _nj[2])
check("J4 eski server (javobda `qaytgan` yo'q) — zip 213 matni AYNAN, xato yo'q", _nj[3] == _JS_KUT[3], _nj[3])
check("J5 hali berilmagan ochiq buyurtma — «(hali berilmagan)» o'zgarmagan", _nj[4] == _JS_KUT[4], _nj[4])
check("J6 kasr va boshqa birlik — «12,5 dona berilgan (01.10.2025), 2,5 dona qaytgan»", _nj[5] == _JS_KUT[5], _nj[5])
check("J7 berilgan 0 bo'lsa (qaytgan > 0 kelsa ham) — «qaytgan» yozilmaydi", _nj[6] == _JS_KUT[6], _nj[6])
check("J8 «0» ga yaxlitlangan qaytgan / brak (0,003 m) — «0 m qaytgan» / «0 m brak» yozilmaydi (review215 №2)", _nj[7] == _JS_KUT[7], _nj[7])
check("J9 qaytgan va brak — «… 72 m berilgan (19.10), 10 m qaytgan, 8 m brak» (egasi tanlovi «Brak alohida»)", _nj[8] == _JS_KUT[8],
      (_nj[8], _JS_KUT[8]))
check("J10 hali berilmagan ochiq buyurtmada brak — «… 72 m (hali berilmagan), 3 m brak»", _nj[9] == _JS_KUT[9], _nj[9])
check("J12 yopiq, berilgan 0 (buzilgan ma'lumot) — «qaytgan» yozilmaydi (faqat berilgan bo'lsa)", _nj[11] == _JS_KUT[11], _nj[11])
check("J11 qisman berilgan ochiq buyurtmada brak — «… 30 m berilgan (20.10), 2,5 m brak, 10 m hali berilmagan»", _nj[10] == _JS_KUT[10],
      _nj[10])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master, Order, ReturnItem, ReturnReason   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k215_a", PAROL, UserRole.ADMIN, "K215 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K215 Penoplast", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P1 = Project(company_id=1, client_name="K215 mijoz", project_name="K215 loyiha", client_phone="+998901112215", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K215 Usta", phone="+998900002215", kpi_percent=10)
s.add_all([PENO, P1, US])
s.commit()
ID = {"PENO": PENO.id, "P1": P1.id, "US": US.id}
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    return c


A = mijoz("k215_a")
BUGUN = datetime.date.today()
AM = []
_SANOQ = [0]


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def db(fn):
    s2 = SessionLocal()
    try:
        r = fn(s2)
        s2.commit()
        return r
    finally:
        s2.close()


def buyurtma(detallar):
    """detallar: [(nom, uzunlik_m)] — profil detallari (+ to'ldiruvchi donali — 8 soniyalik takror-himoya bir xil deb olmasin)."""
    _SANOQ[0] += 1
    items = [{"name": n, "category": "profil", "width": 20, "thickness": 10, "length": L, "quantity": 1, "unit_price": 10000} for n, L in detallar]
    items.append({"name": f"K215 to'ldiruvchi {_SANOQ[0]}", "category": "dona", "width": 0, "thickness": 0, "length": 0,
                  "quantity": _SANOQ[0], "unit_price": 5000})
    tana = {"project_id": ID["P1"], "order_type": "product", "recipe_id": None, "master_id": ID["US"],
            "deadline": (BUGUN + datetime.timedelta(days=3)).isoformat(), "is_draft": False, "base_price": 600000, "loy_kg": None,
            "items": [dict({"is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}, **it)
                      for it in items]}
    r = A.post("/api/orders", json=tana)
    if r.status_code == 409:
        r = A.post("/api/orders?confirm_shortage=true", json=tana)
    AM.append(("buyurtma", detallar[0][0], r.status_code))
    return js(r).get("id") if r.status_code == 200 else None


def detallar(oid):
    return js(A.get(f"/api/orders/{oid}/delivery-status")).get("items") or [] if oid else []


def topshir(oid, miqdorlar):
    """miqdorlar: [(detal tartibi — shu nomdagi nechanchisi, nom, miqdor)]"""
    h = detallar(oid)
    items = []
    for i, nom, q in miqdorlar:
        mos = [x for x in h if x.get("name") == nom]
        if len(mos) > i:
            items.append({"order_item_id": mos[i]["id"], "quantity": q})
    r = A.post("/api/deliveries", json={"order_id": oid, "items": items, "received_by": "K215", "notes": "", "transport_carrier": "",
                                        "transport_cost": 0, "transport_payer": "client"})
    AM.append(("yuk", oid, r.status_code))


def qaytar(oid, nom, q, sabab, i=0):
    mos = [x for x in detallar(oid) if x.get("name") == nom]
    if len(mos) <= i:
        AM.append(("qaytar", nom, "detal yo'q"))
        return None
    tana = {"order_id": oid, "order_item_id": mos[i]["id"], "item_name": nom, "quantity": float(q), "unit": "metr", "reason": sabab,
            "to_stock": True}
    if sabab == "Brak":
        tana["brak_sabab"] = "boshqa"
    r = A.post("/api/returns", json=tana)
    AM.append(("qaytar", nom, q, sabab, r.status_code))
    return js(r).get("id") if r.status_code == 200 else None


O = {}
O["q1"] = buyurtma([("Karniz Q1", 72)]); topshir(O["q1"], [(0, "Karniz Q1", 72)])
AM.append(("ready", A.post(f"/api/orders/{O['q1']}/ready").status_code))
qaytar(O["q1"], "Karniz Q1", 10, "Mijoz iltimosi")
O["q2"] = buyurtma([("Karniz Q2", 40)]); topshir(O["q2"], [(0, "Karniz Q2", 30)]); qaytar(O["q2"], "Karniz Q2", 10, "Notog'ri o'lcham")
O["q3"] = buyurtma([("Karniz Q3", 20)]); qaytar(O["q3"], "Karniz Q3", 5, "Ortiqcha")
O["q4"] = buyurtma([("Karniz Q4", 25)]); topshir(O["q4"], [(0, "Karniz Q4", 25)]); qaytar(O["q4"], "Karniz Q4", 3, "Brak")
O["q5"] = buyurtma([("Karniz Q5", 15)]); topshir(O["q5"], [(0, "Karniz Q5", 15)]); qaytar(O["q5"], "Karniz Q5", 15, "Mijoz iltimosi")
O["q6"] = buyurtma([("Karniz Q6", 30)]); topshir(O["q6"], [(0, "Karniz Q6", 30)])
qaytar(O["q6"], "Karniz Q6", 4, "Mijoz iltimosi"); qaytar(O["q6"], "Karniz Q6", 6, "Ortiqcha")
O["q7"] = buyurtma([("Karniz Q7", 12)]); topshir(O["q7"], [(0, "Karniz Q7", 12)]); qaytar(O["q7"], "Karniz Q7", 12, "Ortiqcha")
O["q8"] = buyurtma([("Karniz Q8", 10), ("karniz  q8", 7)])
topshir(O["q8"], [(0, "Karniz Q8", 10), (0, "karniz  q8", 7)])
qaytar(O["q8"], "Karniz Q8", 2, "Mijoz iltimosi"); qaytar(O["q8"], "karniz  q8", 3.5, "Notog'ri o'lcham"); qaytar(O["q8"], "karniz  q8", 1, "Brak")
O["q9"] = buyurtma([("Karniz Q9", 20)]); topshir(O["q9"], [(0, "Karniz Q9", 20)])
R9 = qaytar(O["q9"], "Karniz Q9", 6, "Mijoz iltimosi")
O["q10"] = buyurtma([("Karniz Q10", 20)]); topshir(O["q10"], [(0, "Karniz Q10", 20)])
O["q11"] = buyurtma([("Karniz Q11", 20)]); topshir(O["q11"], [(0, "Karniz Q11", 20)])
O["q12"] = buyurtma([("Karniz Q12", 20)]); topshir(O["q12"], [(0, "Karniz Q12", 5)])
O["q13"] = buyurtma([("Karniz Q13", 20)]); topshir(O["q13"], [(0, "Karniz Q13", 20)]); qaytar(O["q13"], "Karniz Q13", 4, "Mijoz iltimosi")
O["q14"] = buyurtma([("Karniz Q14", 9)]); topshir(O["q14"], [(0, "Karniz Q14", 9)]); qaytar(O["q14"], "Karniz Q14", 9, "Brak")
# q15: 20 m dan 10 m berilgan, «Ortiqcha» 12 m (10 — topshirilgandan, 2 — omborga), keyin yana 5 m berilgan (jami 15)
O["q15"] = buyurtma([("Karniz Q15", 20)]); topshir(O["q15"], [(0, "Karniz Q15", 10)]); qaytar(O["q15"], "Karniz Q15", 12, "Ortiqcha")
topshir(O["q15"], [(0, "Karniz Q15", 5)])
# q16: 20 m — hech narsa berilmasdan 5 m «Ortiqcha» omborga, keyin 15 m berilgan (review215 №5 — qaytgan 0 bo'lishi kerak)
O["q16"] = buyurtma([("Karniz Q16", 20)]); qaytar(O["q16"], "Karniz Q16", 5, "Ortiqcha"); topshir(O["q16"], [(0, "Karniz Q16", 15)])
# q17: ochiq, hech narsa berilmagan, tayyorlashda 2 m brak
O["q17"] = buyurtma([("Karniz Q17", 20)]); qaytar(O["q17"], "Karniz Q17", 2, "Brak")
# q18: 20 m berilgan, 0,003 m qaytgan (ko'rinishi «0»)
O["q18"] = buyurtma([("Karniz Q18", 20)]); topshir(O["q18"], [(0, "Karniz Q18", 20)]); qaytar(O["q18"], "Karniz Q18", 0.003, "Mijoz iltimosi")


def _eski_yozuvlar(s2):
    """zip 60 dan oldingi qaytarish (ortiqcha_miqdor NULL) va detalsiz eski yozuv; o'chirilgan buyurtma (q13)."""
    def _det(oid, nom):
        return [it for it in s2.get(Order, oid).items if it.name == nom][0]
    _d10 = _det(O["q10"], "Karniz Q10")
    s2.add(ReturnItem(company_id=1, order_id=O["q10"], order_item_id=_d10.id, item_name="Karniz Q10", quantity=4, unit="metr",
                      reason=ReturnReason.CUSTOMER_REQUEST, ortiqcha_miqdor=None))
    s2.add(ReturnItem(company_id=1, order_id=O["q11"], order_item_id=None, item_name="Karniz Q11", quantity=7, unit="metr",
                      reason=ReturnReason.CUSTOMER_REQUEST, ortiqcha_miqdor=None))
    _d12 = _det(O["q12"], "Karniz Q12")
    s2.add(ReturnItem(company_id=1, order_id=O["q12"], order_item_id=_d12.id, item_name="Karniz Q12", quantity=9, unit="metr",
                      reason=ReturnReason.WRONG_SIZE, ortiqcha_miqdor=None))
    s2.get(Order, O["q13"]).is_deleted = True
    return True


_ey = db(_eski_yozuvlar) if all(O.values()) else False
NUM = db(lambda s2: {k: s2.get(Order, v).order_number for k, v in O.items() if v})
_yomon = [x for x in AM if 200 not in x]
check(f"T0 fikstura: {len(O)} buyurtma, yuk xatlari, qaytarishlar, eski yozuvlar — hammasi 200",
      all(O.values()) and not _yomon and _ey is True and len(NUM) == len(O), (_yomon, O))


def royxat(istisno=None):
    r = A.get(f"/api/projects/{ID['P1']}/berilgan-detallar" + (f"?istisno={istisno}" if istisno else ""))
    D = js(r).get("detallar") if isinstance(js(r), dict) else None
    return r.status_code, (D if isinstance(D, list) else [])


def yoz(D, k):
    """shu buyurtmaning «Karniz …» yozuvlari (to'ldiruvchi donali detal — alohida nom, hisobga olinmaydi)"""
    return [d for d in D if d.get("order_id") == O[k] and str(d.get("nomi", "")).lower().startswith("karniz")]


def bitta(D, k):
    x = yoz(D, k)
    return x[0] if len(x) == 1 else {}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — marshrut")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
st, D = royxat()
_kar = [d for d in D if str(d.get("nomi", "")).lower().startswith("karniz")]
check("A1 200; har yozuvda `qaytgan` / `brak` (son) va `qaytgan_matn` / `brak_matn` (matn); narx / summa yo'q",
      st == 200 and _kar and all(isinstance(d.get("qaytgan"), (int, float)) and isinstance(d.get("qaytgan_matn"), str)
                                 and isinstance(d.get("brak"), (int, float)) and isinstance(d.get("brak_matn"), str) for d in D)
      and not any(k in d for d in D for k in ("narx", "summa", "price", "total")), (st, D[:2]))
_d = bitta(D, "q1")
check("A2 «Tayyor» buyurtma, 72 m berilgan, mijoz 10 m qaytargan («Mijoz iltimosi») — qaytgan 10, «10»; berilgan 72 o'zgarmagan; brak 0",
      _d.get("berilgan") == 72 and _d.get("qaytgan") == 10 and _d.get("qaytgan_matn") == "10" and _d.get("ochiq") is False
      and _d.get("brak") == 0 and _d.get("brak_matn") == "0", _d)
_d = bitta(D, "q2")
check("A3 ochiq buyurtma: 30 m berilgan, 10 m qaytgan («Notog'ri o'lcham») — qaytgan 10, hali berilmagan 10 (avvalgidek)",
      _d.get("berilgan") == 30 and _d.get("qaytgan") == 10 and _d.get("qolgan") == 10 and _d.get("ochiq") is True, _d)
_d = bitta(D, "q3")
check("A4 hech narsa berilmagan, 5 m omborga ORTIQCHA — qaytgan 0 (berilmagan qism; «hali berilmagan» 15 — avvalgidek)",
      _d.get("berilgan") == 0 and _d.get("qaytgan") == 0 and _d.get("qaytgan_matn") == "0" and _d.get("qolgan") == 15, _d)
_d, _d14 = bitta(D, "q4"), bitta(D, "q14")
check("A5 BRAK (3 m, butun 9 m ham) — «qaytgan» ga kirmaydi (0), ALOHIDA `brak` 3 / 9 («3», «9») — egasi tanlovi «Brak alohida»",
      _d.get("berilgan") == 25 and _d.get("qaytgan") == 0 and _d.get("brak") == 3 and _d.get("brak_matn") == "3"
      and _d14.get("berilgan") == 9 and _d14.get("qaytgan") == 0 and _d14.get("brak") == 9, (_d, _d14))
_d = bitta(D, "q5")
check("A6 hammasi qaytgan (15 / 15) — yozuv qoladi, qaytgan 15", _d.get("berilgan") == 15 and _d.get("qaytgan") == 15, _d)
_d = bitta(D, "q6")
check("A7 ikki qaytarish (4 «Mijoz iltimosi» + 6 «Ortiqcha» — topshirilgandan) — qaytgan 10", _d.get("qaytgan") == 10, _d)
_d = bitta(D, "q7")
check("A8 «Ortiqcha» 12 m, hammasi topshirilgan edi — topshirilgandan olingan: qaytgan 12", _d.get("berilgan") == 12 and _d.get("qaytgan") == 12,
      _d)
_d = yoz(D, "q8")
check("A9 bir buyurtmada bir xil nomli 2 detal (10 + 7 m; 2 + 3,5 m qaytgan, ikkinchisida 1 m brak) — BITTA yozuv, berilgan 17, qaytgan 5,5 "
      "(«5,5»), brak 1",
      len(_d) == 1 and _d[0].get("berilgan") == 17 and _d[0].get("qaytgan") == 5.5 and _d[0].get("qaytgan_matn") == "5,5"
      and _d[0].get("brak") == 1, _d)
_d = bitta(D, "q10")
check("A10 eski qaytarish yozuvi (`ortiqcha_miqdor` yo'q — zip 60 dan oldin) — to'liq topshirilgandan: qaytgan 4",
      _d.get("qaytgan") == 4, _d)
_d = bitta(D, "q11")
check("A11 detalsiz eski yozuv (qaysi detalniki noma'lum) — taxmin qilinmaydi: qaytgan 0", _d.get("berilgan") == 20 and _d.get("qaytgan") == 0,
      _d)
_d = bitta(D, "q12")
check("A12 eski yozuv berilgandan ko'p (5 m berilgan, 9 m qaytgan deb yozilgan) — berilgandan oshmaydi: qaytgan 5",
      _d.get("berilgan") == 5 and _d.get("qaytgan") == 5, _d)
check("A13 o'chirilgan buyurtma (qaytarishi bilan) — ro'yxatda yo'q", O["q13"] and not yoz(D, "q13"), yoz(D, "q13"))
_d = bitta(D, "q9")
_o9 = A.delete(f"/api/returns/{R9}").status_code if R9 else None
_d9b = bitta(royxat()[1], "q9")
check("A14 qaytarish o'chirilsa — qaytgan yana 0 (6 → 0)", _d.get("qaytgan") == 6 and _o9 == 200 and _d9b.get("qaytgan") == 0,
      (_d, _o9, _d9b))
_d = bitta(D, "q15")
check("A19 «Ortiqcha» 12 m (10 topshirilgandan + 2 omborga), keyin yana 5 m berilgan — qaytgan 10 (omborga qo'yilgan 2 m — sanalmaydi), "
      "berilgan 15, hali berilmagan 3",
      _d.get("berilgan") == 15 and _d.get("qaytgan") == 10 and _d.get("qolgan") == 3 and _d.get("ochiq") is True, _d)
_d = bitta(D, "q16")
check("A20 berilmasdan omborga qo'yilgan 5 m «Ortiqcha», keyin 15 m berilgan — qaytgan 0 (review215 №5), berilgan 15, hali berilmagan 0",
      _d.get("berilgan") == 15 and _d.get("qaytgan") == 0 and _d.get("qolgan") == 0, _d)
_d = bitta(D, "q17")
check("A21 ochiq, berilmagan detalda tayyorlashdagi 2 m brak — yozuv bor: hali berilmagan 20 (brak ayirilmaydi), brak 2",
      _d.get("berilgan") == 0 and _d.get("qolgan") == 20 and _d.get("brak") == 2 and _d.get("ochiq") is True, _d)
_d = bitta(D, "q18")
check("A22 0,003 m qaytarish — `qaytgan` 0,003, ko'rinishi «0» (brauzer yozmaydi — J8)",
      abs(float(_d.get("qaytgan") or 0) - 0.003) < 1e-9 and _d.get("qaytgan_matn") == "0", _d)
_sti, _Di = royxat(istisno=O["q1"])
check("A15 `istisno` — tahrirlanayotgan buyurtma (q1) o'zi sanalmaydi; boshqalarining qaytgani o'zgarmaydi",
      _sti == 200 and not yoz(_Di, "q1") and bitta(_Di, "q2").get("qaytgan") == 10, [d.get("buyurtma") for d in _Di])
_tart = [d.get("order_id") for d in _kar]
_tart2 = [d.get("order_id") for d in royxat()[1] if str(d.get("nomi", "")).lower().startswith("karniz")]
_och = [bool(d.get("ochiq")) for d in _kar]
check("A16 tartib o'zgarmagan — ochiqlari birinchi (q17, q15, q12, q3, q2 — yangisi birinchi), keyin yopiqlar",
      _tart[:5] == [O["q17"], O["q15"], O["q12"], O["q3"], O["q2"]] and _och == sorted(_och, reverse=True) and _och.count(True) == 5,
      (_tart, _och))
_sql = []
from sqlalchemy import event as _ev                # noqa: E402
from database import engine as _eng                # noqa: E402


def _say(*a, **k):
    _sql.append(1)


_ev.listen(_eng, "before_cursor_execute", _say)
royxat()
_ev.remove(_eng, "before_cursor_execute", _say)
check(f"A17 so'rovlar soni qaytarishlar soniga bog'liq emas (N+1 yo'q): {len(_kar)} yozuv, 19 qaytarish — ≤ 12 SQL (review215 №5: detal "
      "boshiga so'rov — 21)", 0 < len(_sql) <= 12, len(_sql))
check("A18 boshqa maydonlar o'zgarmagan (berilgan, qolgan, ochiq, sana) — tartib ikki so'rovda bir xil", _tart == _tart2 and all(
      {"kalit", "nomi", "order_id", "buyurtma", "berilgan", "berilgan_matn", "birlik", "sana", "sana_matn", "qolgan", "qolgan_matn", "ochiq"}
      <= set(d) for d in D), _tart2)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U — HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PW_BOR = not PG_URL
try:
    from playwright.sync_api import sync_playwright
except Exception:                          # noqa: BLE001
    PW_BOR = False
if PG_URL:
    print("  (PG: brauzer bo'limi — SQLite / TF1 rejimida)")
else:
    check("U0 Python `playwright` bor", PW_BOR)

XATO = []
if PW_BOR and all(O.values()):
    import uvicorn                                 # noqa: E402
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    port = so.getsockname()[1]
    so.close()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    BU = f"http://127.0.0.1:{port}"
    DRAFT_KEY = "penodecor_new_order_draft_v1"
    ILGAK = """() => { window.__msg = []; window.__ha = true;
      window.showMsg = (t, ty) => { window.__msg.push([String(t), ty]); };
      window.showConfirmModal = async () => window.__ha; window.customConfirm = async () => window.__ha; }"""
    ESLATMA = """(i) => { const r = document.querySelectorAll('#items .detal')[i || 0]; if (!r) return null;
      const e = r.querySelector('.i-takror');
      return {ko: !!e && e.style.display === 'block' && e.offsetParent !== null, matn: e ? e.textContent : null,
              img: e ? e.querySelectorAll('img').length : -1, ew: e ? e.scrollWidth : 0, ecw: e ? e.clientWidth : 0,
              rw: r.getBoundingClientRect().width, er: e ? e.getBoundingClientRect().right : 0, rr: r.getBoundingClientRect().right,
              dw: document.documentElement.scrollWidth, vw: window.innerWidth}; }"""
    _SANA = {d.get("order_id"): d.get("sana_matn") for d in _kar}

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def sahifa(w=1440, h=900, tel=False):
            ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
            ctx.add_init_script("try { localStorage.removeItem('%s'); } catch (e) {}" % DRAFT_KEY)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "k215_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.goto, BU + "/orders")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.evaluate, ILGAK)
            xav(pg.evaluate, "() => showNewForm()")
            xav(pg.evaluate, """() => { document.getElementById('items').innerHTML = '';
                if (typeof itemCount !== 'undefined') itemCount = 0; addItem(); }""")
            xav(pg.evaluate, f"""() => {{ const p = document.getElementById('project_id'); p.value = '{ID["P1"]}';
                p.dispatchEvent(new Event('change')); }}""")
            xav(pg.wait_for_timeout, 300)
            return ctx, pg

        def eslatma(pg, nom, korinsin=True):
            loc = pg.locator("#items .detal .i-name").nth(0)
            xav(loc.fill, "")
            xav(loc.press_sequentially, nom, delay=15)
            xav(pg.wait_for_function, """(k) => { const e = document.querySelector('#items .detal .i-takror');
                return !!e && ((e.style.display === 'block') === k); }""", arg=korinsin, timeout=6000)
            xav(pg.wait_for_timeout, 250)
            return xav(pg.evaluate, ESLATMA, 0, standart={}) or {}

        ctx, pg = sahifa()
        try:
            e1 = eslatma(pg, "Karniz Q1")
            _m = e1.get("matn") or ""
            _k1 = f"{NUM['q1']} —{NB}72{NB}m{NB}berilgan{NB}({_SANA.get(O['q1'])}), 10{NB}m{NB}qaytgan"
            check("U1 yopiq buyurtma: «ℹ️ Bu loyihada: ORD-… — 72 m berilgan (dd.mm), 10 m qaytgan»",
                  e1.get("ko") and _m == "ℹ️ Bu loyihada: " + _k1, (_m, _k1))
            e2 = eslatma(pg, "Karniz Q2")
            _m = e2.get("matn") or ""
            _k2 = f"{NUM['q2']} —{NB}30{NB}m{NB}berilgan{NB}({_SANA.get(O['q2'])}), 10{NB}m{NB}qaytgan, 10{NB}m{NB}hali{NB}berilmagan"
            check("U2 ochiq buyurtma: «… 30 m berilgan (dd.mm), 10 m qaytgan, 10 m hali berilmagan»", e2.get("ko") and _m.endswith(_k2), (_m, _k2))
            e3 = eslatma(pg, "Karniz Q4")
            _m = e3.get("matn") or ""
            check("U3 brakli detal — «qaytgan» yo'q, brak alohida («… 25 m berilgan (dd.mm), 3 m brak»)",
                  e3.get("ko") and _m.endswith(f"{NUM['q4']} —{NB}25{NB}m{NB}berilgan{NB}({_SANA.get(O['q4'])}), 3{NB}m{NB}brak")
                  and "qaytgan" not in _m, _m)
            e3b = eslatma(pg, "Karniz Q18")
            _m = e3b.get("matn") or ""
            check("U3b 0,003 m qaytarish — «0 m qaytgan» yozilmaydi («… 20 m berilgan (dd.mm)»)",
                  e3b.get("ko") and _m.endswith(f"{NUM['q18']} —{NB}20{NB}m{NB}berilgan{NB}({_SANA.get(O['q18'])})"), _m)
            e4 = eslatma(pg, "Karniz Q8")
            _m = e4.get("matn") or ""
            check("U4 jamlangan yozuv, kasr — «… 17 m berilgan (dd.mm), 5,5 m qaytgan, 1 m brak»; matn `textContent` (rasm / teg yo'q)",
                  e4.get("ko") and _m.endswith(f"17{NB}m{NB}berilgan{NB}({_SANA.get(O['q8'])}), 5,5{NB}m{NB}qaytgan, 1{NB}m{NB}brak")
                  and e4.get("img") == 0, e4)
        finally:
            ctx.close()
        ctx, pg = sahifa(360, 780, tel=True)
        try:
            e5 = eslatma(pg, "Karniz Q2")
            check("U5 telefon (360 px): uzun eslatma qator ichida o'raladi — toshmaydi, sahifa yonga surilmaydi",
                  e5.get("ko") and "qaytgan" in (e5.get("matn") or "") and e5.get("ew", 0) <= e5.get("ecw", 0) + 1
                  and e5.get("er", 0) <= e5.get("rr", 0) + 1 and e5.get("dw", 0) <= e5.get("vw", 0) + 1, e5)
        finally:
            ctx.close()
        br.close()
    server.should_exit = True
    check("U6 sahifada JS xatosi yo'q", not XATO, XATO[:3])

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
