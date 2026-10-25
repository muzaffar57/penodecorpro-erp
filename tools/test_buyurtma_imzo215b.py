#!/usr/bin/env python3
"""
test_buyurtma_imzo215b.py — kech157 (zip 215b — zip 215 JONLI sinovida topilgan ESKI nuqson): 8 soniyalik «ikki marta yuborish» himoyasi
o'lchami boshqa buyurtmani YUTMASIN.

NIMA UCHUN KERAK
  `crud.create_order` shu loyihadagi so'nggi 8 s ichidagi buyurtmani faqat (nom, tur, miqdor) bo'yicha solishtirardi: «Karniz» 72 m saqlangach
  8 s ichida «Karniz» 40 m (profil, miqdor 1) — ikkinchi buyurtma YARATILMAY, birinchisi qaytardi (sinov sayti 25.10, O'LCHANGAN).
BO'LIMLAR
  S — imzoda eni / qalinlik / uzunlik.
  A — `POST /api/orders`: AYNAN bir xil tana ikki marta — bitta buyurtma, penoplast bir marta (himoya avvalgidek); uzunligi / eni / qalinligi
      boshqa — IKKI buyurtma, har biri o'z o'lchami bilan, penoplast ikkalasiga; bir nechta detalli tana — tartibi boshqa, o'zi bir xil —
      bitta; bitta detali o'lchami boshqa — ikki; boshqa loyiha — ikki (avvalgidek); donali (o'lchamsiz) bir xil — bitta.
  B — (mustaqil tekshiruv review215b dan keyin) sahifa yuboradigan shakldagi tanalar (`collectItems`: profil + ichki bo'lak, panel, donali —
      chiqishi bilan (uzunlik 7/3) va `null` o'lchamli, blok (10/3, `null`), loy sotish, MRP mahsuloti, tayyor mahsulot detali, hammasi bitta
      buyurtmada teskari tartibda, son matn ko'rinishida, 0 ↔ `null`, bir xil nomli `category: null` + «profil») — AYNAN takrorlansa bitta
      buyurtma (500 yo'q); qoplama, plotnost (penoplast), narx, ichki bo'lak, qoralama → haqiqiy, boshqa tayyor mahsulot — IKKI buyurtma;
      o'lcham / miqdorda NaN / cheksiz (yaratish, ichki bo'lak, tahrir) — 422, penoplast qoldig'i o'zgarmaydi.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL.
Asl kodga (zip 215) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_buyurtma_imzo215b.py
"""
import os
import io
import sys
import tempfile
import datetime
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "imzo215b_test"
_T = tempfile.mkdtemp(prefix="k215b_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k215b.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


section("S — manba")
CRUD_SRC = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
_i = CRUD_SRC.find("_recent_cutoff = datetime.utcnow() - _td_dup(seconds=8)")
_blok = CRUD_SRC[_i:_i + 2500] if _i >= 0 else ""
check("S1 8 s himoyasi imzosida eni, qalinlik, uzunlik (nom, tur, miqdor bilan birga)",
      '"width"' in _blok and '"thickness"' in _blok and '"length"' in _blok and "x.name, x.category" in _blok, _blok[:600])

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
import json                                        # noqa: E402
from models import UserRole, Inventory, Project, Order, OrderItem, FinishedProduct, Recipe, ProductionStatus   # noqa: E402
from production_models import ProductType         # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k215b_a", PAROL, UserRole.ADMIN, "K215b Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K215b Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P1 = Project(company_id=1, client_name="K215b mijoz", project_name="K215b loyiha", client_phone="+998901112251", total_budget=0, total_paid=0)
P2 = Project(company_id=1, client_name="K215b ikkinchi", project_name="K215b boshqa", client_phone="+998901112252", total_budget=0, total_paid=0)
s.add_all([PENO, P1, P2])
s.commit()
ID = {"PENO": PENO.id, "P1": P1.id, "P2": P2.id}
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "k215b_a", "password": PAROL}, follow_redirects=False)
BUGUN = datetime.date.today()


def tana(detallar, pid=None):
    return {"project_id": pid or ID["P1"], "order_type": "product", "recipe_id": None, "master_id": None,
            "deadline": (BUGUN + datetime.timedelta(days=3)).isoformat(), "is_draft": False, "base_price": 600000, "loy_kg": None,
            "items": [dict({"category": "profil", "width": 20, "thickness": 10, "length": 0, "quantity": 1, "unit_price": 10000, "is_coated": False,
                            "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}, **d) for d in detallar]}


def yarat(t):
    r = A.post("/api/orders", json=t)
    if r.status_code == 409:
        r = A.post("/api/orders?confirm_shortage=true", json=t)
    try:
        return r.status_code, r.json().get("id")
    except Exception:                      # noqa: BLE001
        return r.status_code, None


def stok():
    s2 = SessionLocal()
    try:
        return float(s2.get(Inventory, ID["PENO"]).stock_quantity)
    finally:
        s2.close()


def sanoq():
    s2 = SessionLocal()
    try:
        return s2.query(Order).filter(Order.company_id == 1).count()
    finally:
        s2.close()


def uzunliklar(oid):
    s2 = SessionLocal()
    try:
        return sorted((it.name, float(it.width or 0), float(it.thickness or 0), float(it.length or 0))
                      for it in s2.query(OrderItem).filter(OrderItem.order_id == oid).all())
    finally:
        s2.close()


section("A — buyurtma yaratish")
n0, s0 = sanoq(), stok()
r1 = yarat(tana([{"name": "Karniz A", "length": 72}]))
s1 = stok()
r2 = yarat(tana([{"name": "Karniz A", "length": 72}]))
check("A1 AYNAN bir xil tana ikki marta (ikki marta bosish) — bitta buyurtma, ikkinchisi o'shani qaytaradi, penoplast BIR marta",
      r1[0] == 200 and r2[0] == 200 and r1[1] and r1[1] == r2[1] and sanoq() == n0 + 1 and abs(stok() - s1) < 1e-9 and s1 < s0,
      (r1, r2, sanoq() - n0, s0, s1, stok()))
s1 = stok()
r3 = yarat(tana([{"name": "Karniz A", "length": 40}]))
check("A2 8 s ichida nomi / turi / miqdori o'sha, UZUNLIGI boshqa (72 → 40 m) — YANGI buyurtma (40 m), penoplast unga ham yechiladi",
      r3[0] == 200 and r3[1] and r3[1] != r1[1] and uzunliklar(r3[1]) == [("Karniz A", 20.0, 10.0, 40.0)] and stok() < s1,
      (r3, uzunliklar(r3[1]) if r3[1] else None, s1, stok()))
r4 = yarat(tana([{"name": "Karniz A", "length": 40, "width": 30}]))
check("A3 ENI boshqa (20 → 30 sm) — yangi buyurtma", r4[0] == 200 and r4[1] and r4[1] not in (r1[1], r3[1])
      and uzunliklar(r4[1]) == [("Karniz A", 30.0, 10.0, 40.0)], (r4, r3, r1))
r5 = yarat(tana([{"name": "Karniz A", "length": 40, "width": 30, "thickness": 15}]))
check("A4 QALINLIGI boshqa (10 → 15 sm) — yangi buyurtma", r5[0] == 200 and r5[1] and r5[1] not in (r1[1], r3[1], r4[1])
      and uzunliklar(r5[1]) == [("Karniz A", 30.0, 15.0, 40.0)], (r5, r4))
r5b = yarat(tana([{"name": "Karniz A", "length": 40, "width": 30, "thickness": 15}]))
check("A5 oxirgisi AYNAN takrorlansa — o'sha buyurtma (himoya o'lchamli imzo bilan ham ishlaydi)", r5b[0] == 200 and r5b[1] == r5[1],
      (r5b, r5))
k1 = yarat(tana([{"name": "Ustun B", "length": 3}, {"name": "Panel C", "category": "panel", "width": 100, "thickness": 5, "length": 2}]))
k2 = yarat(tana([{"name": "Panel C", "category": "panel", "width": 100, "thickness": 5, "length": 2}, {"name": "Ustun B", "length": 3}]))
check("A6 bir nechta detal — tartibi boshqa, o'zi AYNAN — bitta buyurtma", k1[0] == 200 and k2[0] == 200 and k1[1] and k1[1] == k2[1], (k1, k2))
k3 = yarat(tana([{"name": "Ustun B", "length": 3}, {"name": "Panel C", "category": "panel", "width": 100, "thickness": 5, "length": 2.5}]))
check("A7 bir nechta detal — bittasining uzunligi boshqa (2 → 2,5 m) — yangi buyurtma", k3[0] == 200 and k3[1] and k3[1] != k1[1], (k3, k1))
p2 = yarat(tana([{"name": "Ustun B", "length": 3}, {"name": "Panel C", "category": "panel", "width": 100, "thickness": 5, "length": 2.5}],
                pid=ID["P2"]))
check("A8 boshqa loyiha — o'zi AYNAN bo'lsa ham yangi buyurtma (avvalgidek)", p2[0] == 200 and p2[1] and p2[1] != k3[1], (p2, k3))
d1 = yarat(tana([{"name": "Gul D", "category": "dona", "width": 0, "thickness": 0, "length": 0, "quantity": 6, "unit_price": 5000}]))
d2 = yarat(tana([{"name": "Gul D", "category": "dona", "width": 0, "thickness": 0, "length": 0, "quantity": 6, "unit_price": 5000}]))
d3 = yarat(tana([{"name": "Gul D", "category": "dona", "width": 0, "thickness": 0, "length": 0, "quantity": 7, "unit_price": 5000}]))
check("A9 o'lchamsiz donali: AYNAN — bitta; miqdori boshqa — yangi (avvalgidek)", d1[0] == 200 and d1[1] == d2[1] and d3[1] and d3[1] != d1[1],
      (d1, d2, d3))
check("A10 jami buyurtmalar: 72 m, 40 m, eni 30, qalinlik 15, ikki detalli, 2,5 m li, boshqa loyiha, donali 6, donali 7 — 9 ta",
      sanoq() == n0 + 9, sanoq() - n0)

section("B — sahifa shaklidagi tanalar (review215b)")
s = SessionLocal()
PENO2 = Inventory(company_id=1, item_name="K215b Penoplast 25", unit="blok", stock_quantity=1000, price_per_unit=700_000,
                  volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=False, category="Penoplast")
s.add(PENO2)
s.commit()
FP = FinishedProduct(company_id=1, name="Karniz TM", category="profil", width=20, thickness=10, is_coated=False, quantity=500, produced_quantity=500,
                     unit="metr", unit_price=1000, cost_price=0, penoplast_id=ID["PENO"], production_status=ProductionStatus.READY)
FP2 = FinishedProduct(company_id=1, name="Karniz TM", category="profil", width=20, thickness=10, is_coated=False, quantity=500, produced_quantity=500,
                      unit="metr", unit_price=1000, cost_price=0, penoplast_id=ID["PENO"], production_status=ProductionStatus.READY)
REC = Recipe(company_id=1, name="K215b retsept", batch_size_kg=100)
PT = ProductType(company_id=1, name="K215b Plita", unit="dona", input_template="dimensional_3d", pricing_formula="fixed_price", fixed_unit_price=1000)
s.add_all([FP, FP2, REC, PT])
s.commit()
ID.update({"PENO2": PENO2.id, "FP": FP.id, "FP2": FP2.id, "REC": REC.id, "PT": PT.id})
s.close()
_PN = [0]


def loyiha():
    _PN[0] += 1
    s2 = SessionLocal()
    p = Project(company_id=1, client_name=f"K215b B {_PN[0]}", project_name=f"K215b B loyiha {_PN[0]}", client_phone=f"+99890222{_PN[0]:04d}",
                total_budget=0, total_paid=0)
    s2.add(p)
    s2.commit()
    pid = p.id
    s2.close()
    return pid


def btana(pid, items, **kw):
    d = {"project_id": pid, "order_type": "product", "recipe_id": None, "master_id": None, "agreed_amount": None, "deadline": None,
         "is_draft": False, "items": items, "base_price": 600000, "blok_base_price": None, "loy_kg": None}
    d.update(kw)
    return d


def bpost(b, xom=None):
    if xom is not None:
        r = A.post("/api/orders?confirm_shortage=true", content=xom, headers={"Content-Type": "application/json"})
    else:
        r = A.post("/api/orders?confirm_shortage=true", json=b)
    try:
        j = r.json()
    except Exception:                      # noqa: BLE001
        j = {}
    return r.status_code, (j.get("id") if isinstance(j, dict) else None)


def juft(b1, b2, xom1=None, xom2=None):
    r1, r2 = bpost(b1, xom1), bpost(b2, xom2)
    return r1, r2, (r1[0] == 200 and r2[0] == 200 and r1[1] is not None and r1[1] == r2[1])


def profil(**kw):
    d = {"name": "Karniz A", "category": "profil", "width": 20, "thickness": 10, "length": 72.35, "quantity": 1, "unit_price": 123456.789,
         "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None,
         "sub_details": [{"name": None, "category": "profil", "width": 5, "thickness": 3, "length": 72.35, "quantity": 1, "is_coated": False}]}
    d.update(kw)
    return d


def panel(**kw):
    d = {"name": "Panel B", "category": "panel", "width": 100.5, "thickness": 5, "length": 2.333, "quantity": 3, "unit_price": 99999.995,
         "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": 650000, "finished_product_id": None}
    d.update(kw)
    return d


def dona_chiq(**kw):
    d = {"name": "Gul C", "category": "dona", "width": 12, "thickness": 4, "length": 7 / 3, "quantity": 7, "unit_price": 5000,
         "unit_price_for_volume": 4999.9, "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None,
         "notes": "dona_yield=3"}
    d.update(kw)
    return d


def dona_null(**kw):
    d = {"name": "Gul D", "category": "dona", "width": None, "thickness": None, "length": None, "quantity": 6, "unit_price": 5000,
         "unit_price_for_volume": 5000, "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None, "notes": None}
    d.update(kw)
    return d


def blok(**kw):
    d = {"name": "Blok E", "category": "blok", "width": None, "thickness": None, "length": 10 / 3, "quantity": 10, "unit_price": 33333.3333,
         "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None, "blok_birlik": "metr", "blok_chiqishi": 3,
         "blok_narxi": None, "blok_koef": 2, "notes": "blok_narxi=100000,blok_yield=3"}
    d.update(kw)
    return d


def loy(**kw):
    d = {"name": "Loy F", "category": "loy_sotish", "width": None, "thickness": None, "length": None, "quantity": 12.5, "unit_price": 3000,
         "is_coated": False, "penoplast_id": None, "price_per_m3": None, "finished_product_id": None, "recipe_id": ID["REC"]}
    d.update(kw)
    return d


def mrp(**kw):
    d = {"name": "K215b Plita", "category": "mrp_product", "width": 60, "thickness": 2, "length": 1.2, "quantity": 4, "unit_price": 1000,
         "is_coated": False, "penoplast_id": None, "price_per_m3": None, "finished_product_id": None, "product_type_id": ID["PT"]}
    d.update(kw)
    return d


def tm(**kw):
    d = {"name": "Karniz TM", "category": "profil", "width": 20, "thickness": 10, "length": 5.5, "quantity": 1, "unit_price": 1000,
         "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": ID["FP"], "sub_details": []}
    d.update(kw)
    return d


_bir = []
for _nom, _f in (("profil + ichki bo'lak", profil), ("panel", panel), ("donali (chiqishi, 7/3)", dona_chiq), ("donali (null)", dona_null),
                 ("blok (10/3, null)", blok), ("loy sotish", loy), ("MRP mahsuloti", mrp), ("tayyor mahsulot detali", tm)):
    _pid = loyiha()
    _bir.append((_nom,) + juft(btana(_pid, [_f()]), btana(_pid, [_f()])))
check("B1 AYNAN takror (sahifa shakli) — 8 tur: har birida BITTA buyurtma (500 yo'q)", all(x[3] for x in _bir),
      [(x[0], x[1], x[2]) for x in _bir if not x[3]])
_pid = loyiha()
_hamma = [profil(), panel(), dona_chiq(), dona_null(), blok(), loy(), mrp(), tm()]
check("B2 8 turli detal bitta buyurtmada, takrori teskari tartibda — bitta", juft(btana(_pid, _hamma), btana(_pid, list(reversed(_hamma))))[2])
_pid = loyiha()
check("B3 o'lcham 0 ↔ null (bir xil ma'no) — bitta",
      juft(btana(_pid, [dona_null(width=0, thickness=0, length=0)]), btana(_pid, [dona_null()]))[2])
_pid = loyiha()
_xm = json.dumps(btana(_pid, [profil(length="72.35", quantity="1")]))
check("B4 son matn ko'rinishida (\"72.35\") ikki marta — bitta", juft(None, None, _xm, _xm)[2])
_pid = loyiha()
_cn = [dict(profil(), category=None, sub_details=[]), dict(profil(), sub_details=[])]
_r = juft(btana(_pid, _cn), btana(_pid, _cn))
check("B5 bir xil nom — `category: null` va «profil» bitta buyurtmada, takrori — bitta (ilgari ikkinchi so'rov 500)", _r[2], _r)
_farq = []
for _nom, _b1, _b2 in (
        ("qoplama", lambda p: btana(p, [panel()], recipe_id=ID["REC"]), lambda p: btana(p, [panel(is_coated=True)], recipe_id=ID["REC"])),
        ("plotnost (penoplast)", lambda p: btana(p, [panel()]), lambda p: btana(p, [panel(penoplast_id=ID["PENO2"])])),
        ("narx", lambda p: btana(p, [panel()]), lambda p: btana(p, [panel(unit_price=50000)])),
        ("ichki bo'lak", lambda p: btana(p, [profil()]), lambda p: btana(p, [profil(sub_details=[{"name": None, "category": "profil", "width": 8,
                                                                                                  "thickness": 4, "length": 72.35, "quantity": 1,
                                                                                                  "is_coated": False}])])),
        ("qoralama → haqiqiy", lambda p: btana(p, [panel()], is_draft=True), lambda p: btana(p, [panel()])),
        ("boshqa tayyor mahsulot", lambda p: btana(p, [tm()]), lambda p: btana(p, [tm(finished_product_id=ID["FP2"])]))):
    _pid = loyiha()
    _r = juft(_b1(_pid), _b2(_pid))
    _farq.append((_nom, _r[0], _r[1], (not _r[2]) and _r[0][0] == 200 and _r[1][0] == 200))
for _i, (_nom, _a, _b, _ok) in enumerate(_farq):
    check(f"B{6 + _i} 8 s ichida faqat {_nom} boshqa — IKKI buyurtma (review215b №1)", _ok, (_a, _b))
_s0 = stok()
_pid = loyiha()
_n = [bpost(None, json.dumps(btana(_pid, [profil(width=float("nan"))]), allow_nan=True))[0],
      bpost(None, json.dumps(btana(_pid, [profil(length="nan")])))[0],
      bpost(None, json.dumps(btana(_pid, [profil(thickness=float("inf"))]), allow_nan=True))[0],
      bpost(None, json.dumps(btana(_pid, [panel(quantity=float("inf"))]), allow_nan=True))[0],
      bpost(None, json.dumps(btana(_pid, [profil(sub_details=[{"name": None, "category": "profil", "width": float("nan"), "thickness": 3,
                                                                 "length": 1, "quantity": 1, "is_coated": False}])]), allow_nan=True))[0]]
check("B12 o'lcham / miqdorda NaN / cheksiz (eni NaN, uzunlik \"nan\", qalinlik ∞, miqdor ∞, ichki bo'lak eni NaN) — hammasi 422, penoplast "
      "qoldig'i o'zgarmaydi (PG da NaN bo'lardi — review215b №4)", _n == [422] * 5 and stok() == _s0, (_n, _s0, stok()))
_ok1 = bpost(btana(_pid, [panel(name="Panel tahrir")]))
_t = A.put(f"/api/orders/{_ok1[1]}", content=json.dumps(btana(_pid, [panel(name="Panel tahrir", width=float("nan"))]), allow_nan=True),
           headers={"Content-Type": "application/json"}) if _ok1[1] else None
_s1 = stok()
check("B13 tahrirda (PUT) eni NaN — 422, buyurtma o'lchami o'zgarmagan", _t is not None and _t.status_code == 422
      and uzunliklar(_ok1[1]) == [("Panel tahrir", 100.5, 5.0, 2.333)] and stok() == _s1, (_ok1, _t.status_code if _t is not None else None))

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
