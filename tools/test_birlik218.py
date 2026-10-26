#!/usr/bin/env python3
"""
test_birlik218.py — kech158 (zip 218 «Plotnost nomi va material birligi» — egasi tanlovi 26.10: «1 va 2 ni tuzatish (Tavsiya)»).

NIMA UCHUN KERAK
  (2) Tarixi bor materialda `PUT /api/inventory/{id}` birlik va turni jimgina o'zgartirardi: 50 kg kirim, 10 kg chiqim qilingan «Akril» «litr»
      qilinsa qoldiq «40 litr», tarix «kg»; oddiy material penoplastga aylanardi (O'LCHANGAN — `work/k218/probe218a.py`, zip 217 kodi).
  (1) Buyurtma oynasidagi «Plotnost» tanlovi uzun nomning oxirini ko'rsatmasdi (320 px da «Penoplast 14P (1…», Kirill 901 / 1151 px), yonidagi
      yorliq — oxirgi so'z («uchun)», «(Toshkent)»); ichki detal «Turi» telefonda «📏 Pro» (O'LCHANGAN — `work/k218/probe218.py`, Chromium).
BO'LIMLAR
  S — manba (yordamchi, tekshiruv joyi, sahifa funksiyalari, belgilash, CSS).
  A — server: ishlatilgan materialda birlik / tur — 400, hech narsa yozilmaydi (qoldiq, harakatlar, xaridlar); faqat retsept / faqat qoldiq /
      faqat buyurtma plotnosti bilan ishlatilgan ham; bo'shliq farqi — o'zgarish emas; tarixsiz — avvalgidek; boshqa maydonlar — avvalgidek;
      retsept (BOM) birligi — 400, koeffitsient sonini tuzatish — 200; retseptsiz materialga mayda birlik — 200; `crud.update_item` ham.
  U — HAQIQIY Chromium (SQLite / TF1; PG da o'tkazilmaydi): yorliq qoidasi; tor ekranda to'liq nom chiqadi, kengda — yo'q; o'lcham
      o'zgarganda (hodisasiz) yangilanadi; Lotin ↔ Kirill; tahrirda saqlangan plotnost; ichki detal «Turi» sig'adi; sahifa yonga
      surilmaydi; tungi rejimda o'qiladi (≥ 4,5:1); JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (S + A).
Asl kodga (zip 217) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_birlik218.py
"""
import os
import io
import re
import sys
import glob
import time
import socket
import datetime
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "birlik218_test"
_T = tempfile.mkdtemp(prefix="k218_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k218.db')}"
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
        print(f"  ✗ {label}   {str(detail)[:1200]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
CRUD_SRC = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
ORD = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_ui = CRUD_SRC.find("def update_item(")
_ui_tana = CRUD_SRC[_ui:CRUD_SRC.find("\nclass MaterialQoldiqBor", _ui)] if _ui >= 0 else ""
check("S1 `crud.material_ishlatilganmi` (qoldiq + `models.Base.metadata` tashqi kalitlari) va `_retsept_birligi218`; `update_item` ularni "
      "yozishdan OLDIN tekshiradi (birlik, tur, retsept birligi)",
      "def material_ishlatilganmi(db: Session, item, jadvallar=None) -> bool:" in CRUD_SRC and "for _t in list(_Base218.metadata.tables.values()):" in CRUD_SRC
      and "def _retsept_birligi218(unit, base_unit, conversion_factor) -> str:" in CRUD_SRC
      and "material_ishlatilganmi(db, db_item)" in _ui_tana and 'material_ishlatilganmi(db, db_item, jadvallar=("bom_items",))' in _ui_tana
      and _ui_tana.find("material_ishlatilganmi(db, db_item)") < _ui_tana.find("setattr(db_item, field, value)"))
check("S2 sahifa: `penoToliqYangila`, `penoToliqHammasi`, `penoKuzat` (bitta `ResizeObserver`), Lotin / Kirill tugmasi tinglovchisi; "
      "`onPenoChange`, `addItem`, tahrirda chaqiriladi (`typeof` bilan); `.i-peno-toliq` belgilash va CSS; `shortPenoName` — raqamli so'z",
      "function penoToliqYangila(row) {" in ORD and "function penoToliqHammasi() {" in ORD and "function penoKuzat(row) {" in ORD
      and "e.target.closest('#script-toggle-btn" in ORD
      and ORD.count("if (typeof penoToliqYangila === 'function') penoToliqYangila(row);") == 2
      and "if (typeof penoKuzat === 'function') penoKuzat(div);" in ORD
      and '<div class="i-peno-toliq" hidden></div>' in ORD and ".i-peno-toliq[hidden]{display:none}" in ORD
      and "const zich = parts.find(s => /^\\d+[A-Za-z\\u0400-\\u04FF]{0,2}$/.test(s));" in ORD
      and "const raqamli = zich || parts.find(s => /\\d/.test(s));" in ORD)
check("S3 ichki qo'shimcha detal «Turi» — eng kichik kenglik 130 px (asl 90)",
      '<div style="flex:1;min-width:130px"><label style="font-size:12px;color:var(--m-475569)">Turi</label>' in ORD
      and '<div style="flex:1;min-width:90px"><label style="font-size:12px;color:var(--m-475569)">Turi</label>' not in ORD)

check("S4 (review218) telefon menyusidagi «Кирилл» (`#tbKopYozuv`) ham tinglanadi; to'liq nom chiqqanda qator tepadan tekislanadi; qoralama "
      "tiklanganda `onPenoChange`; `add_item` tiklashida retsept birligi; tekshiruvdan oldin `FOR UPDATE`; boshlangan ishlab chiqarish SURATI",
      "e.target.closest('#script-toggle-btn, #tbKopYozuv')" in ORD
      and ".dgrp-row.yb-qoplama-qator:has(> .i-peno-wrap > .i-peno-toliq:not([hidden])){align-items:flex-start}" in ORD
      and "if (typeof onPenoChange === 'function') onPenoChange(row); else calculateItem(row);" in ORD
      and "_rb0, _rb1 = _retsept_birligi218(e.unit, e.base_unit, e.conversion_factor), _retsept_birligi218(e.unit, _bu, _cf)" in CRUD_SRC
      and "db_item = inventory_qulf(db, db_item.id, ochirish=True) or db_item" in _ui_tana
      and "def _surat_ishlatadimi218(db: Session, item) -> bool:" in CRUD_SRC)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas                                 # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, InventoryPurchase, InventoryMovement, Project, Recipe,   # noqa: E402
                    RecipeIngredient)
from production_models import ProductType, BOM, BOMItem, ProductionOrder   # noqa: E402
from models import FinishedProduct                 # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k218_a", PAROL, UserRole.ADMIN, "K218 Admin", company_id=1)
s.add_all([Inventory(company_id=1, item_name="K218 Penoplast 25", unit="blok", stock_quantity=1000, price_per_unit=500_000,
                     volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast"),
           Inventory(company_id=1, item_name="K218 Penoplast 14P", unit="blok", stock_quantity=1250, price_per_unit=600_000,
                     volume_per_unit=1.0, is_penoplast=True, category="Penoplast"),
           Inventory(company_id=1, item_name="K218 Penoplast 35 zich (fasad uchun)", unit="blok", stock_quantity=1250,
                     price_per_unit=700_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")])
P1 = Project(company_id=1, client_name="K218 mijoz", project_name="K218 loyiha", client_phone="+998901112218", total_budget=0, total_paid=0)
s.add(P1)
s.commit()
PID = P1.id
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "k218_a", "password": PAROL}, follow_redirects=False)
_N = [0]


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def yarat(unit="kg", peno=False, base_unit=None, cf=None):
    _N[0] += 1
    b = {"item_name": f"K218 {'Peno' if peno else 'Mat'} {_N[0]}", "unit": unit, "stock_quantity": 0, "price_per_unit": 0,
         "is_penoplast": peno, "category": "Penoplast" if peno else "Boshqa"}
    if peno:
        b["volume_per_unit"] = 1.0
    if base_unit is not None:
        b["base_unit"] = base_unit
        b["conversion_factor"] = cf
    r = A.post("/api/inventory", json=b)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def kirim(i, q, narx=10_000):
    r = A.post(f"/api/inventory/{i}/purchase", json={"quantity": q, "price_per_unit": narx})
    assert r.status_code == 200, r.text


def chiqim(i, q):
    r = A.post(f"/api/inventory/{i}/stock", json={"quantity_change": -q, "reason": "K218 chiqim"})
    assert r.status_code == 200, r.text


def holat(i):
    s2 = SessionLocal()
    try:
        p = s2.get(Inventory, i)
        hr = [(m.movement_type, round(float(m.quantity), 6), m.unit) for m in
              s2.query(InventoryMovement).filter(InventoryMovement.inventory_id == i).order_by(InventoryMovement.id)]
        xr = [(round(float(x.quantity), 6), x.unit) for x in
              s2.query(InventoryPurchase).filter(InventoryPurchase.inventory_id == i).order_by(InventoryPurchase.id)]
        return {"unit": p.unit, "qoldiq": round(float(p.stock_quantity or 0), 6), "peno": bool(p.is_penoplast), "bu": p.base_unit,
                "cf": p.conversion_factor, "nom": p.item_name, "kat": p.category, "min": p.min_stock, "harakat": hr, "xarid": xr}
    finally:
        s2.close()


def put(i, b):
    r = A.put(f"/api/inventory/{i}", json=b)
    return r.status_code, str(js(r).get("detail") or "")


def bom_qator(inv_id, qty=500.0):
    s2 = SessionLocal()
    try:
        _N[0] += 1
        pt = ProductType(company_id=1, name=f"K218 tur {_N[0]}", unit="dona", input_template="quantity_only",
                         pricing_formula="unit_based")
        s2.add(pt)
        s2.flush()
        b = BOM(company_id=1, product_type_id=pt.id, variant_name="Standart", batch_quantity=1.0)
        s2.add(b)
        s2.flush()
        s2.add(BOMItem(bom_id=b.id, inventory_id=inv_id, company_id=1, component_type="raw_material", quantity=qty))
        s2.commit()
    finally:
        s2.close()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — server: ishlatilgan materialda birlik / tur")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
i = yarat("kg")
kirim(i, 50, 20_000)
chiqim(i, 10)
h0 = holat(i)
st, d = put(i, {"unit": "litr"})
check("A1 50 kg kirim + 10 kg chiqim qilingan material «litr» — 400 (asl: 200, qoldiq «40 litr», tarix «kg»), sababda eski va yangi birlik; "
      "HECH NARSA o'zgarmadi (birlik, qoldiq, harakatlar, xaridlar)",
      st == 400 and "«kg»" in d and "«litr»" in d and "yangi material" in d and holat(i) == h0
      and h0["harakat"] == [("in", 50.0, "kg"), ("out", 10.0, "kg")] and h0["xarid"] == [(50.0, "kg")], (st, d, holat(i)))
st, d = put(i, {"unit": "kg"})
st2, d2 = put(i, {"unit": " kg "})
check("A2 o'sha birlik (va chetdagi bo'shliq bilan « kg ») — o'zgarish emas, 200; birlik «kg» qoladi (bo'shliq yozilmaydi)",
      st == 200 and st2 == 200 and holat(i)["unit"] == "kg", (st, d, st2, d2, holat(i)["unit"]))
st, d = put(i, {"item_name": "K218 Akril yangi nom", "category": "Kimyo", "min_stock": 5, "notes": "izoh"})
h1 = holat(i)
check("A3 ishlatilgan materialda nom, kategoriya, minimal qoldiq, izoh — avvalgidek 200",
      st == 200 and h1["nom"] == "K218 Akril yangi nom" and h1["kat"] == "Kimyo" and h1["min"] == 5, (st, d, h1))
st, d = put(i, {"unit": "litr", "item_name": "K218 Akril boshqa nom"})
check("A4 birlik bilan birga boshqa maydon yuborilsa — 400, nom ham O'ZGARMADI (hammasi yoki hech narsa)",
      st == 400 and holat(i)["nom"] == "K218 Akril yangi nom" and holat(i)["unit"] == "kg", (st, d, holat(i)))
o = yarat("rulon")
kirim(o, 7)
st, d = put(o, {"is_penoplast": True})
check("A5 kirimi bor oddiy material → penoplast — 400 (asl: 200), o'zgarmadi", st == 400 and "penoplastga" in d and holat(o)["peno"] is False,
      (st, d, holat(o)))
p = yarat("blok", peno=True)
kirim(p, 10, 500_000)
st, d = put(p, {"is_penoplast": False})
check("A6 kirimi bor (asosiy bo'lmagan) penoplast → oddiy — 400, o'zgarmadi", st == 400 and "penoplastni oddiy" in d and holat(p)["peno"] is True,
      (st, d, holat(p)))
st, d = put(p, {"is_penoplast": True})
check("A7 o'sha tur (penoplast → penoplast) — 200", st == 200, (st, d))
# faqat qoldiq (eski yozuv: harakatsiz qoldiq)
s = SessionLocal()
q = Inventory(company_id=1, item_name="K218 Eski qoldiq", unit="qop", stock_quantity=3, price_per_unit=1000, is_penoplast=False,
              category="Boshqa")
s.add(q)
s.commit()
qid = q.id
s.close()
st, d = put(qid, {"unit": "kg"})
check("A8 harakatsiz, lekin qoldig'i bor (eski yozuv) material — 400", st == 400 and holat(qid)["unit"] == "qop", (st, d))
# faqat loy retseptida (qoldiq 0, harakat yo'q)
r_id = yarat("kg")
s = SessionLocal()
rc = Recipe(company_id=1, name=f"K218 retsept {_N[0]}", batch_size_kg=100)
s.add(rc)
s.flush()
s.add(RecipeIngredient(recipe_id=rc.id, inventory_id=r_id, quantity_kg=5))
s.commit()
s.close()
st, d = put(r_id, {"unit": "litr"})
check("A9 qoldiqsiz, harakatsiz — faqat LOY RETSEPTIDA ishlatilgan material — 400 (jadvallar — tashqi kalitlardan)",
      st == 400 and holat(r_id)["unit"] == "kg", (st, d))
# faqat buyurtma plotnosti (qoldiq qaytarildi — 0)
pb = yarat("blok", peno=True)
kirim(pb, 1, 500_000)
_N[0] += 1
b = {"project_id": PID, "order_type": "product", "recipe_id": None, "master_id": None,
     "deadline": (datetime.date.today() + datetime.timedelta(days=3)).isoformat(), "is_draft": False, "base_price": 600000, "loy_kg": None,
     "items": [{"name": "K218 Panel", "category": "panel", "width": 100, "thickness": 10, "length": 1, "quantity": 1, "unit_price": 10000,
                "is_coated": False, "penoplast_id": pb, "price_per_m3": None, "finished_product_id": None}]}
ob = A.post("/api/orders?confirm_shortage=true", json=b)
st, d = put(pb, {"is_penoplast": False})
check("A10 buyurtma detalida plotnost sifatida ishlatilgan penoplast → oddiy — 400", ob.status_code == 200 and st == 400 and holat(pb)["peno"],
      (ob.status_code, ob.text[:200], st, d))
# tarixsiz
t = yarat("kg")
st, d = put(t, {"unit": "litr"})
st2, d2 = put(t, {"is_penoplast": True})
check("A11 tarixsiz (yangi, qoldiq 0) material — birlik va tur avvalgidek o'zgaradi (200)",
      st == 200 and st2 == 200 and holat(t)["unit"] == "litr" and holat(t)["peno"] is True, (st, d, st2, d2, holat(t)))
# retsept (BOM)
g = yarat("qop", base_unit="g", cf=25000)
bom_qator(g)
st, d = put(g, {"base_unit": "kg", "conversion_factor": 25})
check("A12 ishlab chiqarish retseptidagi material: mayda birlik «g» → «kg» — 400 (retseptdagi miqdor «kg» deb o'qilardi), o'zgarmadi",
      st == 400 and "«g»" in d and "«kg»" in d and holat(g)["bu"] == "g" and holat(g)["cf"] == 25000, (st, d, holat(g)))
st, d = put(g, {"conversion_factor": 50000})
check("A13 o'sha retsept materialida koeffitsient SONINI tuzatish (birlik «g» qoladi) — 200", st == 200 and holat(g)["cf"] == 50000, (st, d))
st, d = put(g, {"base_unit": None, "conversion_factor": None})
check("A14 retsept materialidan mayda birlikni olib tashlash («g» → «qop») — 400, o'zgarmadi",
      st == 400 and holat(g)["bu"] == "g" and holat(g)["cf"] == 50000, (st, d, holat(g)))
k = yarat("kg")
bom_qator(k)
st, d = put(k, {"base_unit": "g", "conversion_factor": 1000})
check("A15 retseptda (mayda birliksiz, «kg») bo'lgan materialga mayda birlik «g» qo'shish — 400", st == 400 and holat(k)["bu"] is None, (st, d))
c = yarat("qop")
kirim(c, 5, 60_000)
st, d = put(c, {"base_unit": "kg", "conversion_factor": 50})
check("A16 retseptsiz (faqat kirimi bor) materialga mayda birlik + koeffitsient — 200 (tarixdagi «5 qop» o'zgarmaydi)",
      st == 200 and holat(c)["bu"] == "kg" and holat(c)["xarid"] == [(5.0, "qop")], (st, d, holat(c)))
# faqat tayyor mahsulot plotnosti (qoldiq 0, harakat / xarid yo'q — «faqat buyurtma / mahsulot» bog'lanishi)
fpn = yarat("blok", peno=True)
s = SessionLocal()
s.add(FinishedProduct(company_id=1, name=f"K218 TM {_N[0]}", quantity=0, penoplast_id=fpn))
s.commit()
s.close()
st, d = put(fpn, {"is_penoplast": False})
st2, d2 = put(fpn, {"unit": "dona"})
check("A19 qoldiqsiz, harakatsiz, xaridsiz — FAQAT tayyor mahsulot plotnostida (`finished_products.penoplast_id`) — tur va birlik 400",
      st == 400 and st2 == 400 and holat(fpn)["peno"] is True and holat(fpn)["unit"] == "blok" and holat(fpn)["harakat"] == []
      and holat(fpn)["xarid"] == [], (st, d, st2, d2, holat(fpn)))
u = yarat("kg")
st, d = put(u, {"unit": "  litr "})
check("A20 tarixsiz materialda o'zgargan birlik bo'shliqlarsiz yoziladi («  litr » → «litr»)", st == 200 and holat(u)["unit"] == "litr",
      (st, d, holat(u)))
# o'chirilgan (yashirilgan) retsept materiali qayta yaratilsa
rv = yarat("qop", base_unit="g", cf=25000)
bom_qator(rv)
_nom_rv = holat(rv)["nom"]
s = SessionLocal()
s.get(Inventory, rv).is_deleted = True          # yashirish (retsept qatori bor — `delete_item` PG da ham shunday qiladi; SQLite FK siz)
s.commit()
s.close()
_r1 = A.post("/api/inventory", json={"item_name": _nom_rv, "unit": "qop", "stock_quantity": 0, "price_per_unit": 0, "is_penoplast": False,
                                     "category": "Boshqa", "base_unit": "kg", "conversion_factor": 25})
s = SessionLocal()
_yash = bool(s.get(Inventory, rv).is_deleted)
s.close()
_r2 = A.post("/api/inventory", json={"item_name": _nom_rv, "unit": "qop", "stock_quantity": 0, "price_per_unit": 0, "is_penoplast": False,
                                     "category": "Boshqa", "base_unit": "g", "conversion_factor": 25000})
check("A21 yashirilgan retsept materiali qayta yaratilib mayda birligi «g» → «kg» — 400 (asl: «500 g» qatori «500 kg» bo'lardi), "
      "yashirinligicha; o'sha «g» bilan — tiklanadi (200)",
      _r1.status_code == 400 and _yash and holat(rv)["bu"] == "g" and _r2.status_code == 200,
      (_r1.status_code, js(_r1), _yash, _r2.status_code, holat(rv)))
# boshlangan ishlab chiqarish SURATIDA (retsept qatori o'chirilgan)
sm = yarat("kg")
s = SessionLocal()
_N[0] += 1
_pt = ProductType(company_id=1, name=f"K218 tur {_N[0]}", unit="dona", input_template="quantity_only", pricing_formula="unit_based")
s.add(_pt)
s.flush()
_bm = BOM(company_id=1, product_type_id=_pt.id, variant_name="Standart", batch_quantity=1.0)
s.add(_bm)
s.flush()
import json as _json                               # noqa: E402
s.add(ProductionOrder(company_id=1, product_type_id=_pt.id, bom_id=_bm.id, source_type="stock", quantity=1, status="in_progress",
                      recipe_snapshot_json=_json.dumps([{"inventory_id": sm, "item_name": "x", "unit": "kg", "stock_unit": "kg",
                                                         "total_quantity_needed_stock_unit": 5.0}])))
s.commit()
_bm_id = _bm.id
s.close()
st, d = put(sm, {"unit": "litr"})
s = SessionLocal()
s.query(ProductionOrder).filter(ProductionOrder.bom_id == _bm_id).update({"status": "completed"})
s.commit()
s.close()
st2, d2 = put(sm, {"unit": "litr"})
check("A22 material FAQAT boshlangan ishlab chiqarish suratida (retsept qatori yo'q) — 400; buyurtma yakunlangan (surat endi kerak emas) — 200",
      st == 400 and st2 == 200, (st, d, st2, d2))
_m = i
_x = None
s = SessionLocal()
try:
    crud.update_item(s, _m, schemas.InventoryUpdate(unit="litr"))
    s.rollback()
except ValueError as e:
    _x = str(e)
    s.rollback()
finally:
    s.close()
check("A17 `crud.update_item` to'g'ridan-to'g'ri chaqirilsa ham — ValueError, o'zgarmadi", _x is not None and holat(_m)["unit"] == "kg", _x)
_ish = None
s = SessionLocal()
try:
    _f = getattr(crud, "material_ishlatilganmi", None)
    if _f:
        _ish = (_f(s, s.get(Inventory, t)), _f(s, s.get(Inventory, i)), _f(s, s.get(Inventory, c), jadvallar=("bom_items",)),
                _f(s, s.get(Inventory, k), jadvallar=("bom_items",)))
finally:
    s.close()
check("A18 `material_ishlatilganmi`: tarixsiz — False, kirimli — True; faqat BOM bo'yicha: kirimli, retseptsiz — False, retseptli — True",
      _ish == (False, True, False, True), _ish)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U — HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    print("  (PG rejimida brauzer bo'limi o'tkazilmaydi — SQLite / TF1 da)")
else:
    PW_BOR = True
    try:
        from playwright.sync_api import sync_playwright
    except Exception:                      # noqa: BLE001
        PW_BOR = False
    check("U0 Python `playwright` bor", PW_BOR)
    # Tahrir uchun buyurtma: uzun nomli plotnost bilan
    s = SessionLocal()
    _uzun = s.query(Inventory.id).filter(Inventory.item_name == "K218 Penoplast 35 zich (fasad uchun)").scalar()
    _qisqa = s.query(Inventory.id).filter(Inventory.item_name == "K218 Penoplast 14P").scalar()
    s.close()
    b = {"project_id": PID, "order_type": "product", "recipe_id": None, "master_id": None,
         "deadline": (datetime.date.today() + datetime.timedelta(days=3)).isoformat(), "is_draft": False, "base_price": 600000,
         "loy_kg": None,
         "items": [{"name": "K218 Karniz", "category": "panel", "width": 100, "thickness": 10, "length": 1, "quantity": 1,
                    "unit_price": 10000, "is_coated": False, "penoplast_id": _uzun, "price_per_m3": 900000,
                    "finished_product_id": None}]}
    _ot = A.post("/api/orders?confirm_shortage=true", json=b)
    OID = js(_ot).get("id")
    HOLAT = r"""() => { const r = document.querySelector('#items .detal'); const sel = r.querySelector('.i-peno');
      const cap = r.querySelector('.i-peno-toliq'); const disp = r.querySelector('.i-peno-display');
      const cs = getComputedStyle(sel); const c = document.createElement('canvas').getContext('2d');
      c.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const opt = sel.options[sel.selectedIndex]; const t = opt ? opt.textContent.trim() : '';
      const joy = sel.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - 21;
      return {matn: t, kerak: Math.round(c.measureText(t).width * 10) / 10, joy: Math.round(joy * 10) / 10,
              toliq: cap ? (cap.hidden ? null : cap.textContent) : 'YOQ', yorliq: disp ? disp.textContent : null,
              cap_tosh: cap && !cap.hidden ? cap.scrollWidth > cap.clientWidth + 1 : false,
              cap_ichida: cap && !cap.hidden ? cap.getBoundingClientRect().right <= r.getBoundingClientRect().right + 1 : true,
              tosh: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""
    TANLA = r"""(nom) => { const r = document.querySelector('#items .detal'); const sel = r.querySelector('.i-peno');
      const o = [...sel.options].find(x => x.textContent.indexOf(nom) >= 0); if (!o) return false; sel.value = o.value;
      sel.dispatchEvent(new Event('change')); return true; }"""
    KIRILL_TAYYOR = r"""() => { const r = document.querySelector('#items .detal'); const sel = r.querySelector('.i-peno');
                const cs = getComputedStyle(sel); const c = document.createElement('canvas').getContext('2d');
                c.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
                const t = sel.options[sel.selectedIndex].textContent.trim();
                const lat = c.measureText(t).width; const kir = c.measureText(latinToCyrillic(t)).width;
                const ichki = Math.ceil((lat + kir) / 2 + parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight) + 24);
                const wrap = sel.closest('.unit-input-wrap'); const disp = wrap.querySelector('.i-peno-display');
                const tash = wrap.getBoundingClientRect().width - wrap.clientWidth;
                r.querySelector('.i-peno-wrap').style.flex = '0 0 auto';
                wrap.style.width = (ichki + disp.getBoundingClientRect().width + tash) + 'px';
                return {lat, kir, ichki}; }"""
    NAT = {}
    XATO = []
    if PW_BOR:
        import uvicorn                             # noqa: E402
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

        def sahifa(br, w, h, tel, yozuv="lotin", tungi=False, ro_yoq=False):
            ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel,
                                 has_touch=tel)
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
            ctx.add_init_script("try { localStorage.removeItem('penodecor_new_order_draft_v1'); localStorage.setItem('erp_script', '%s');"
                                " %s } catch (e) {}" % (yozuv, "localStorage.setItem('theme', 'dark');" if tungi else ""))
            if ro_yoq:     # eski brauzer: `ResizeObserver` yo'q — zaxira yo'l (`resize` tinglovchisi) va to'g'ridan-to'g'ri chaqiruvlar
                ctx.add_init_script("try { window.ResizeObserver = undefined; } catch (e) {}")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "k218_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.goto, BU + "/orders")
            xav(pg.wait_for_load_state, "networkidle")
            return ctx, pg

        with sync_playwright() as pw:
            _exe = None
            for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                    "chrome-linux", "chrome"))):
                _exe = _y
            br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()
            # U1 — yorliq qoidasi (sahifa funksiyasi)
            ctx, pg = sahifa(br, 1366, 768, False)
            NAT["yorliq"] = xav(pg.evaluate, r"""() => ['Penoplast 14P', 'Penoplast 35 zich (fasad uchun)', 'PSB-S 25 F fasad 1x1x2 m (Toshkent)',
                'Penoplast', 'Пенополистиролбетон', '  ', '(25)', 'Penoplast 10P', 'K218 Penoplast 35 zich (fasad uchun)', 'D25 Penoplast',
                'Пенопласт 14П'].map(x => shortPenoName(x))""", standart=[])
            # U2 — keng ekran: qisqa nom — to'liq nom qatori YO'Q; uzun nom — bor
            xav(pg.evaluate, "() => showNewForm()")
            xav(pg.wait_for_timeout, 300)
            xav(pg.evaluate, TANLA, "K218 Penoplast 14P")
            NAT["keng_qisqa"] = xav(pg.evaluate, HOLAT, standart={})
            xav(pg.evaluate, TANLA, "K218 Penoplast 35 zich")
            NAT["keng_uzun"] = xav(pg.evaluate, HOLAT, standart={})
            # U3 — o'lcham o'zgarishi (hodisasiz): qisqa nom 1366 → 320 → 1366
            xav(pg.evaluate, TANLA, "K218 Penoplast 14P")
            xav(pg.set_viewport_size, {"width": 320, "height": 640})
            xav(pg.wait_for_timeout, 400)
            NAT["tor_qisqa"] = xav(pg.evaluate, HOLAT, standart={})
            xav(pg.set_viewport_size, {"width": 1366, "height": 768})
            xav(pg.wait_for_timeout, 400)
            NAT["qayta_keng"] = xav(pg.evaluate, HOLAT, standart={})
            # U4 — Lotin ↔ Kirill: tanlov kengligi chegarada (Lotin sig'adi, Kirill sig'maydi)
            NAT["kirill_tayyor"] = xav(pg.evaluate, KIRILL_TAYYOR, standart={})
            xav(pg.wait_for_timeout, 300)
            NAT["kirill_oldin"] = xav(pg.evaluate, HOLAT, standart={})
            xav(pg.click, "#script-toggle-btn")
            xav(pg.wait_for_timeout, 400)
            NAT["kirill"] = xav(pg.evaluate, HOLAT, standart={})
            xav(pg.click, "#script-toggle-btn")
            xav(pg.wait_for_timeout, 400)
            NAT["kirill_keyin"] = xav(pg.evaluate, HOLAT, standart={})
            ctx.close()
            # U11 — 1440 px: to'liq nom chiqqanda Plotnost tanlovi Qoplama tugmalari bilan bir balandlikda (review218 №2: 20 px yuqorida edi)
            ctx, pg = sahifa(br, 1440, 900, False)
            xav(pg.evaluate, "() => showNewForm()")
            xav(pg.wait_for_timeout, 300)
            xav(pg.evaluate, TANLA, "K218 Penoplast 35 zich")
            xav(pg.wait_for_timeout, 200)
            NAT["tekis"] = xav(pg.evaluate, r"""() => { const r = document.querySelector('#items .detal');
                const y = s => Math.round(r.querySelector(s).getBoundingClientRect().top);
                const cap = r.querySelector('.i-peno-toliq');
                return {peno: y('.i-peno-wrap .unit-input-wrap'), qoplama: y('.i-coat-wrap .coat-toggle'), toliq: cap && !cap.hidden,
                        bir_qator: Math.abs(y('.i-peno-wrap') - y('.i-coat-wrap')) < 40}; }""", standart={})
            ctx.close()
            # U10 — telefon (390 px): «···» menyusidagi «Кирилл» (`#tbKopYozuv`), yorliq faqat raqam («25» — kengligi o'zgarmaydi), chegara
            ctx, pg = sahifa(br, 390, 844, True)
            xav(pg.evaluate, "() => showNewForm()")
            xav(pg.wait_for_timeout, 300)
            xav(pg.evaluate, TANLA, "K218 Penoplast 25")
            NAT["tel_tayyor"] = xav(pg.evaluate, KIRILL_TAYYOR, standart={})
            xav(pg.wait_for_timeout, 300)
            NAT["tel_oldin"] = xav(pg.evaluate, HOLAT, standart={})
            xav(pg.evaluate, "() => document.getElementById('tbKopYozuv').click()")
            xav(pg.wait_for_timeout, 400)
            NAT["tel_kirill"] = xav(pg.evaluate, HOLAT, standart={})
            ctx.close()
            # U5 — tahrir: saqlangan uzun nomli plotnost, 360 px (ResizeObserver YO'Q — tahrirdagi to'g'ridan-to'g'ri chaqiruv o'lchanadi)
            ctx, pg = sahifa(br, 360, 740, True, ro_yoq=True)
            if OID:
                xav(pg.evaluate, """async (id) => { const o = await (await fetch('/api/orders/' + id)).json(); selectedOrderId = id;
                    await editSelected('edit', o); }""", OID)
                xav(pg.wait_for_timeout, 600)
                NAT["tahrir"] = xav(pg.evaluate, HOLAT, standart={})
            # U9 — ResizeObserver YO'Q: yangi forma, qisqa nom 360 px da sig'maydi; oyna kengaysa (`resize`) — yo'qoladi
            xav(pg.evaluate, "() => showNewForm()")
            xav(pg.wait_for_timeout, 300)
            xav(pg.evaluate, TANLA, "K218 Penoplast 14P")
            NAT["ro_yoq_tor"] = xav(pg.evaluate, HOLAT, standart={})
            xav(pg.set_viewport_size, {"width": 1366, "height": 768})
            xav(pg.wait_for_timeout, 400)
            NAT["ro_yoq_keng"] = xav(pg.evaluate, HOLAT, standart={})
            # U6 — ichki qo'shimcha detal «Turi», Kirill, 375 / 360 px
            ctx.close()
            for w, h in ((375, 812), (360, 740), (320, 640)):
                ctx, pg = sahifa(br, w, h, True, yozuv="kirill")
                xav(pg.evaluate, "() => showNewForm()")
                xav(pg.wait_for_timeout, 300)
                NAT[f"sd_{w}"] = xav(pg.evaluate, r"""() => { const r = document.querySelector('#items .detal'); addSubDetailRow(r);
                    const wr = r.querySelector('.i-subdetails-wrap'); if (wr) wr.style.display = '';
                    const e = r.querySelector('.subdetail-row .sd-type'); const cs = getComputedStyle(e);
                    const c = document.createElement('canvas').getContext('2d'); c.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
                    const joy = e.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - 21;
                    return [...e.options].map(o => ({t: o.textContent, w: Math.round(c.measureText(o.textContent).width), joy: Math.round(joy)})); }""",
                                     standart=[])
                xav(pg.evaluate, TANLA, "K218 Penoplast 35 zich")
                xav(pg.wait_for_timeout, 200)
                NAT[f"tor_{w}"] = xav(pg.evaluate, HOLAT, standart={})
                ctx.close()
            # U8 — tungi rejim: to'liq nom qatori o'qiladi
            for tungi in (False, True):
                ctx, pg = sahifa(br, 360, 740, True, tungi=tungi)
                xav(pg.evaluate, "() => showNewForm()")
                xav(pg.wait_for_timeout, 300)
                xav(pg.evaluate, TANLA, "K218 Penoplast 35 zich")
                NAT[f"kontrast_{tungi}"] = xav(pg.evaluate, r"""() => {
                    const cap = document.querySelector('#items .detal .i-peno-toliq'); if (!cap || cap.hidden) return null;
                    const rgb = s => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
                    const lum = a => { const v = a.map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); });
                                       return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
                    let el = cap, bg = 'rgba(0, 0, 0, 0)';
                    while (el && (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent')) { bg = getComputedStyle(el).backgroundColor; el = el.parentElement; }
                    const a = lum(rgb(getComputedStyle(cap).color)), b = lum(rgb(bg));
                    return Math.round(((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)) * 100) / 100; }""", standart=None)
                ctx.close()
            br.close()

        _y = NAT.get("yorliq") or []
        check("U1 yorliq — plotnostga o'xshagan so'z («14P», «35», «25», «14П»; «K218 …» oldida bo'lsa ham), bo'lmasa birinchi raqamli so'z "
              "(«D25»), raqamsiz — oxirgi so'z; 10 belgidan uzuni qisqartiriladi; bo'sh — '' (asl: «uchun)», «(Toshkent)»)",
              _y == ["14P", "35", "25", "Penoplast", "Пенополис…", "", "25", "10P", "35", "D25", "14П"], _y)
        kq, ku = NAT.get("keng_qisqa") or {}, NAT.get("keng_uzun") or {}
        check("U2 1366 px: «Penoplast 14P» sig'adi — to'liq nom qatori YO'Q; «… 35 zich (fasad uchun)» sig'maydi — ostida TO'LIQ nomi, yorliq «35»",
              kq.get("toliq") is None and kq.get("kerak", 999) <= kq.get("joy", 0)
              and ku.get("toliq") == "K218 Penoplast 35 zich (fasad uchun) (1250)" and ku.get("kerak", 0) > ku.get("joy", 999)
              and ku.get("yorliq") == "35" and not ku.get("cap_tosh") and ku.get("cap_ichida"), (kq, ku))
        tq, qk = NAT.get("tor_qisqa") or {}, NAT.get("qayta_keng") or {}
        check("U3 hech qanday tanlovsiz o'lcham o'zgarsa (1366 → 320 → 1366): 320 px da «Penoplast 14P (1250)» sig'maydi — to'liq nom chiqadi, "
              "kengda yana yo'qoladi; 320 px da sahifa yonga surilmaydi",
              tq.get("kerak", 0) > tq.get("joy", 999) and tq.get("toliq") == "K218 Penoplast 14P (1250)" and tq.get("tosh") == 0
              and qk.get("toliq") is None, (tq, qk))
        ko, kk, kq2 = NAT.get("kirill_oldin") or {}, NAT.get("kirill") or {}, NAT.get("kirill_keyin") or {}
        check("U4 chegaradagi kenglik: Lotinda sig'adi — yo'q; «Кирилл» bosilganda Kirill matni sig'maydi — to'liq nom (Kirillda) chiqadi; "
              "qaytib Lotin — yana yo'q",
              ko.get("toliq") is None and kk.get("toliq") and "Пенопласт" in str(kk.get("toliq")) and kq2.get("toliq") is None,
              (NAT.get("kirill_tayyor"), ko, kk, kq2))
        th = NAT.get("tahrir") or {}
        check("U5 tahrir (360 px, ResizeObserver yo'q): saqlangan «… 35 zich (fasad uchun)» — tanlangan, yorliq «35», ostida to'liq nomi",
              bool(OID) and "35 zich" in str(th.get("matn")) and th.get("yorliq") == "35"
              and th.get("toliq") == "K218 Penoplast 35 zich (fasad uchun) (1250)", (OID, th))
        _sd = [(w, o) for w in (375, 360, 320) for o in (NAT.get(f"sd_{w}") or [])]
        check("U6 ichki qo'shimcha detal «Turi» (Kirill, 375 / 360 / 320 px) — «📏 Профил», «🔲 Панел» sig'adi (asl: «📏 Про», joy 52 px)",
              len(_sd) == 6 and all(o["w"] <= o["joy"] for _, o in _sd), _sd)
        _tr = [NAT.get(f"tor_{w}") or {} for w in (375, 360, 320)]
        check("U7 375 / 360 / 320 px (Kirill): uzun nom — to'liq nom qatori bor, toshmaydi, detal ichida; sahifa yonga surilmaydi; JS xatosi yo'q",
              all(x.get("toliq") not in (None, "", "YOQ") and not x.get("cap_tosh") and x.get("cap_ichida") and x.get("tosh") == 0 for x in _tr) and not XATO,
              (_tr, XATO[:3]))
        rt, rk = NAT.get("ro_yoq_tor") or {}, NAT.get("ro_yoq_keng") or {}
        check("U9 ResizeObserver yo'q (eski brauzer): 360 px da «Penoplast 14P (1250)» — to'liq nom bor; oyna 1366 px ga kengaysa — yo'qoladi",
              rt.get("toliq") == "K218 Penoplast 14P (1250)" and rk.get("toliq") is None and rk.get("kerak", 999) <= rk.get("joy", 0), (rt, rk))
        to, tk = NAT.get("tel_oldin") or {}, NAT.get("tel_kirill") or {}
        check("U10 telefon (390 px): «···» menyusidagi «Кирилл» bosilganda ham — chegaradagi «Penoplast 25 ⭐ (1000)» Kirillda sig'maydi, "
              "to'liq nom chiqadi (review218 №1: chiqmasdi)",
              to.get("toliq") is None and tk.get("toliq") and "Пенопласт" in str(tk.get("toliq")) and tk.get("yorliq") == "25",
              (NAT.get("tel_tayyor"), to, tk))
        te = NAT.get("tekis") or {}
        check("U11 1440 px: to'liq nom chiqqanda Plotnost tanlovi Qoplama tugmalari bilan bir balandlikda (±2 px; asl farq 20 px)",
              te.get("toliq") is True and te.get("bir_qator") and abs((te.get("peno") or 0) - (te.get("qoplama") or 999)) <= 2, te)
        k0, k1 = NAT.get("kontrast_False"), NAT.get("kontrast_True")
        check("U8 to'liq nom qatori yorug' va tungi rejimda o'qiladi (kontrast ≥ 4,5:1)", (k0 or 0) >= 4.5 and (k1 or 0) >= 4.5, (k0, k1))

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
