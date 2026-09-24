#!/usr/bin/env python3
"""
test_brak_bosqich.py — 13-band 1-qadam darvozasi (kech53, 2026-09-24).

NIMA UCHUN: brak yozuvida faqat miqdor, qiymat va erkin izoh bor edi — brak QAYSI BOSQICHDA
bo'lgani (kesish, qoplash, quritish, saqlash / tashish) yozilmasdi, shuning uchun qaysi jarayon
eng ko'p zarar keltirayotganini bilib bo'lmasdi (kech5 9-bo'lim, 2-kamchilik). Bosqichlar ro'yxati —
foydalanuvchi qarori (kech45): Kesish (penoplast kesish), Qoplash (loy tortish), Quritish,
Saqlash / tashish.

YECHIM (texnik — Claude): `ReturnItem.brak_bosqich` va `FinishedProductLoss.brak_bosqich`
(String(20), STANDARTSIZ, NULL — tanlanmagan / eski yozuv); kodlar va yorliqlar YAGONA manbada —
`crud.BRAK_BOSQICHLARI`. Tanlov IXTIYORIY:
  * buyurtma braki (`POST /api/returns`, `returns.html` brak oynasi — butun ro'yxat uchun bitta);
    boshqa sababga ("Ortiqcha" va h.k.) bosqich berilsa — 400, hech narsa yozilmaydi;
  * "Kamaytirish" (`POST /api/finished/loss`) va ishlab chiqarish braki
    (`POST /api/finished/production-brak`) — `finished.html` "Kamaytirish" oynasi.
QAT'IY SHART (kech5 9-bo'lim): brak yozish oqimi (miqdor, qiymat, xomashyo yechimi, belgilar,
narx) O'ZGARMAYDI — bosqichli va bosqichsiz brak AYNAN bir xil yozuvlar hosil qilishi shu test
bilan isbotlanadi; noto'g'ri bosqich xomashyo yechilishidan OLDIN rad etiladi.

ASL KOD: bu test tuzatishdan OLDINGI kodga qarshi yiqilishi (qulamasligi) SHART — yangi nomlarga
murojaat `getattr` bilan, HTTP istisnolari 599.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_brak_bosqich.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_brak_bosqich.py
"""
import os
import sys
import re
import typing
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "brak_bosqich_test"
_DB = os.path.join(tempfile.gettempdir(), "brak_bosqich_test.db")

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
    import crud, auth, services, schemas           # noqa: E402
    import database as _database                   # noqa: E402

from sqlalchemy import text as _sqltext            # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, OrderItem, Inventory, InventoryMovement, Recipe, RecipeIngredient,
    ReturnItem, FinishedProduct, FinishedProductLoss, StockSource, ProductionStatus,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []

KODLAR = ["kesish", "qoplash", "quritish", "saqlash_tashish"]
YORLIQLAR = ["Kesish (penoplast kesish)", "Qoplash (loy tortish)", "Quritish", "Saqlash / tashish"]


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
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


def taxminan(a, b, eps=1e-6):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="BQ Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "BQ_admin", "Parol123!", UserRole.ADMIN, "BQ Admin", company_id=1)
    auth.create_user(_db, "BQ_admin_b", "Parol123!", UserRole.ADMIN, "BQ Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="BQ Mijoz", project_name="BQ loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="BQ Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="BQ Kley", unit="kg", stock_quantity=100_000,
                 price_per_unit=2_000, category="Kimyo")
AKR = Inventory(company_id=1, item_name="BQ Akril", unit="kg", stock_quantity=100_000,
                price_per_unit=10_000, category="Kimyo")
_db.add_all([PRJ, PENO, KLEY, AKR])
_db.commit()
R1 = Recipe(company_id=1, name="BQ R1", batch_size_kg=100.0)
_db.add(R1)
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0)])
_db.commit()
PRJ_ID, PENO_ID, KLEY_ID, AKR_ID, R1_ID = PRJ.id, PENO.id, KLEY.id, AKR.id, R1.id
with contextlib.redirect_stdout(_quiet):
    _loy = services.get_or_create_loy_stock(_db, _db.get(Recipe, R1_ID))
_loy.stock_quantity = 0.0
_db.commit()
LOY_ID = _loy.id
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("BQ_admin")
CB, _s2 = _kir("BQ_admin_b")
if _s1 != 302 or _s2 != 302:
    print(f"LOGIN BO'LMADI: {_s1} / {_s2}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
# Yordamchilar
# ══════════════════════════════════════════════════════════════
_n = [0]


def profil(uzunlik, qoplama=False):
    _n[0] += 1
    return {"name": f"BQ_D{_n[0]}", "category": "profil", "width": 20, "thickness": 10,
            "length": uzunlik, "quantity": 10, "unit_price": 50_000, "is_coated": bool(qoplama),
            "penoplast_id": PENO_ID, **({"recipe_id": R1_ID} if qoplama else {})}


def yarat(items, recipe_id=None, loy_kg=None):
    tana = {"project_id": PRJ_ID, "order_type": "product", "items": items}
    if recipe_id:
        tana["recipe_id"] = recipe_id
    if loy_kg is not None:
        tana["loy_kg"] = loy_kg
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    d = js(r)
    oid = d.get("id") if isinstance(d, dict) else None
    if not oid:
        raise RuntimeError(f"buyurtma yaratilmadi: {r.status_code} {r.text[:300]}")
    return oid


def detal(oid):
    d = SessionLocal()
    try:
        it = d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).first()
        return it.id, it.name
    finally:
        d.close()


def brak_tana(oid, miqdor=10, qoplama=False, **qoshimcha):
    iid, nom = detal(oid)
    t = {"order_id": oid, "order_item_id": iid, "item_name": nom, "quantity": miqdor, "unit": "metr",
         "reason": "Brak", "refund_amount": 0, "to_stock": False, "coating_applied": bool(qoplama)}
    t.update(qoshimcha)
    return t


def stoklar():
    d = SessionLocal()
    try:
        return tuple(round(float(d.get(Inventory, i).stock_quantity or 0), 9)
                     for i in (PENO_ID, KLEY_ID, AKR_ID, LOY_ID))
    finally:
        d.close()


def holat():
    """Yozuv sonlari + material qoldiqlari + tayyor mahsulotlar miqdori — 'hech narsa yozilmadi' isboti."""
    d = SessionLocal()
    try:
        return (d.query(ReturnItem).count(), d.query(FinishedProductLoss).count(),
                d.query(InventoryMovement).count(),
                round(sum(float(f.quantity or 0) for f in d.query(FinishedProduct).all()), 9)) + stoklar()
    finally:
        d.close()


def qaytarish(rid):
    if rid is None:
        return None
    d = SessionLocal()
    try:
        return d.get(ReturnItem, rid)
    finally:
        d.close()


def bosqich_q(rid):
    q = qaytarish(rid)
    return getattr(q, "brak_bosqich", "USTUN YO'Q") if q else "YOZUV YO'Q"


def harakat_shakli(rid):
    """Brak yozuviga bog'langan harakatlar: (material, tur, miqdor, narx, is_brak) — id siz."""
    if rid is None:
        return []
    d = SessionLocal()
    try:
        return sorted((h.inventory_id, h.movement_type, round(float(h.quantity or 0), 9),
                       h.unit_cost, getattr(h, "is_brak", None))
                      for h in d.query(InventoryMovement).filter(InventoryMovement.return_item_id == rid).all())
    finally:
        d.close()


def yozuv_shakli(rid):
    """Brak yozuvining bosqichdan boshqa hamma mazmuni."""
    q = qaytarish(rid)
    if not q:
        return None
    return (q.quantity, q.unit, str(q.reason), round(float(q.refund_amount or 0), 2), q.is_refunded,
            q.coating_applied, q.notes, q.stock_qty, q.finished_product_id)


def fp_yarat(nom, tayyor=True):
    d = SessionLocal()
    try:
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=True, quantity=100,
                             produced_quantity=100, unit="metr", unit_price=0, cost_price=1_000_000,
                             source=StockSource.PRODUCED, penoplast_id=PENO_ID, recipe_id=R1_ID,
                             unit_volume_m3=0.01, unit_loy_kg=0.5,
                             production_status=(ProductionStatus.READY if tayyor else ProductionStatus.IN_PROGRESS))
        d.add(fp)
        d.commit()
        return fp.id
    finally:
        d.close()


def fp_holat(fp_id):
    d = SessionLocal()
    try:
        fp = d.get(FinishedProduct, fp_id)
        return (round(float(fp.quantity or 0), 9), round(float(fp.cost_price or 0), 4))
    finally:
        d.close()


def yoqotishlar(fp_id):
    """(miqdor, birlik, tan narx, sabab, bosqich) — shu mahsulotning yo'qotish yozuvlari."""
    d = SessionLocal()
    try:
        return [(l.quantity, l.unit, round(float(l.cost_amount or 0), 2), l.reason, getattr(l, "brak_bosqich", "YO'Q"))
                for l in d.query(FinishedProductLoss).filter(FinishedProductLoss.finished_product_id == fp_id)
                .order_by(FinishedProductLoss.id).all()]
    finally:
        d.close()


def delta(oldin, keyin):
    return tuple(round(k - o, 9) for o, k in zip(oldin, keyin))


def html(c, url):
    r = req(c, "get", url)
    return r.status_code, (r.text if r.status_code == 200 else "")


# ══════════════════════════════════════════════════════════════
# A — lug'at, model, sxema
# ══════════════════════════════════════════════════════════════
section("A — lug'at, model, sxema")
_lugat = getattr(crud, "BRAK_BOSQICHLARI", None)
check("A0 crud.BRAK_BOSQICHLARI — 4 bosqich, foydalanuvchi ro'yxati tartibida",
      isinstance(_lugat, dict) and list(_lugat) == KODLAR and list(_lugat.values()) == YORLIQLAR, _lugat)
for _m, _nom in ((ReturnItem, "ReturnItem"), (FinishedProductLoss, "FinishedProductLoss")):
    _col = _m.__table__.c.get("brak_bosqich")
    check(f"A1 {_nom}.brak_bosqich: String(20), nullable, standartSIZ",
          _col is not None and getattr(_col.type, "length", None) == 20 and _col.nullable
          and _col.default is None and _col.server_default is None, _col)
for _sx in ("ReturnItemCreate", "FinishedProductLossCreate", "FinishedProductProductionBrakCreate"):
    _f = getattr(getattr(schemas, _sx), "model_fields", {}).get("brak_bosqich")
    _args = []
    if _f is not None:
        for _a in typing.get_args(_f.annotation):
            _args += list(typing.get_args(_a))
    check(f"A2 schemas.{_sx}.brak_bosqich — Literal ro'yxati lug'at bilan AYNAN, standart None",
          _f is not None and _args == KODLAR and _f.default is None, (_f, _args))

# ══════════════════════════════════════════════════════════════
# B — buyurtma braki (POST /api/returns)
# ══════════════════════════════════════════════════════════════
section("B — buyurtma braki")
# B1 — oqim O'ZGARMAGAN: bosqichli va bosqichsiz brak AYNAN bir xil yozuv va harakatlar
Oa = yarat([profil(100)])
Ob = yarat([profil(100)])
s0 = stoklar()
ra = req(C, "post", "/api/returns", json=brak_tana(Oa))
s1 = stoklar()
rb = req(C, "post", "/api/returns", json=brak_tana(Ob, brak_bosqich="kesish"))
s2 = stoklar()
ida, idb = (js(ra) or {}).get("id"), (js(rb) or {}).get("id")
check("B1 bosqichsiz va bosqichli brak — ikkalasi 200", ra.status_code == 200 and rb.status_code == 200,
      (ra.status_code, ra.text[:200], rb.status_code, rb.text[:200]))
check("B1b bosqich yozildi ('kesish'), bosqichsiz — NULL", bosqich_q(idb) == "kesish" and bosqich_q(ida) is None,
      (bosqich_q(ida), bosqich_q(idb)))
check("B1c brak yozuvi mazmuni (miqdor, sabab, qiymat, qoplama, izoh) AYNAN",
      yozuv_shakli(ida) is not None and yozuv_shakli(ida) == yozuv_shakli(idb), (yozuv_shakli(ida), yozuv_shakli(idb)))
check("B1d xomashyo yechimi AYNAN (penoplast kamaydi, farq bir xil)",
      delta(s0, s1) == delta(s1, s2) and delta(s0, s1)[0] < 0, (delta(s0, s1), delta(s1, s2)))
check("B1e bog'langan harakatlar (material, miqdor, narx, is_brak) AYNAN",
      harakat_shakli(ida) and harakat_shakli(ida) == harakat_shakli(idb), (harakat_shakli(ida), harakat_shakli(idb)))
_r = js(rb) or {}
check("B1f POST javobida brak_bosqich", _r.get("brak_bosqich") == "kesish", str(_r)[:300])

# B2 — qoplamali brak (loy tortilgandan keyin) — 'qoplash' bilan, oqim AYNAN
Oc = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=50)
Od = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=50)
s0 = stoklar()
rc = req(C, "post", "/api/returns", json=brak_tana(Oc, qoplama=True))
s1 = stoklar()
rd = req(C, "post", "/api/returns", json=brak_tana(Od, qoplama=True, brak_bosqich="qoplash"))
s2 = stoklar()
idc, idd = (js(rc) or {}).get("id"), (js(rd) or {}).get("id")
check("B2 qoplamali brak: ikkalasi 200, bosqich 'qoplash' / NULL",
      rc.status_code == 200 and rd.status_code == 200 and bosqich_q(idd) == "qoplash" and bosqich_q(idc) is None,
      (rc.status_code, rd.status_code, rd.text[:200]))
check("B2b penoplast + kley + akril yechimi AYNAN, loy ingredientlari yechildi",
      delta(s0, s1) == delta(s1, s2) and delta(s0, s1)[1] < 0 and delta(s0, s1)[2] < 0, (delta(s0, s1), delta(s1, s2)))
check("B2c bog'langan harakatlar AYNAN (3 material)",
      len(harakat_shakli(idc)) >= 3 and harakat_shakli(idc) == harakat_shakli(idd),
      (harakat_shakli(idc), harakat_shakli(idd)))

# B3 — hamma kodlar, null, bo'sh satr, bo'shliqli
for _k in KODLAR[2:]:
    _o = yarat([profil(50)])
    _x = req(C, "post", "/api/returns", json=brak_tana(_o, miqdor=5, brak_bosqich=_k))
    check(f"B3 '{_k}' → 200 va yozildi", _x.status_code == 200 and bosqich_q((js(_x) or {}).get("id")) == _k,
          (_x.status_code, _x.text[:200]))
for _nomi, _qiy in (("null", None), ("bo'sh satr", ""), ("faqat bo'shliq", "   ")):
    _o = yarat([profil(50)])
    _x = req(C, "post", "/api/returns", json=brak_tana(_o, miqdor=5, brak_bosqich=_qiy))
    check(f"B4 bosqich {_nomi} → 200, NULL (tanlanmagan)",
          _x.status_code == 200 and bosqich_q((js(_x) or {}).get("id")) is None, (_x.status_code, _x.text[:200]))
_o = yarat([profil(50)])
_x = req(C, "post", "/api/returns", json=brak_tana(_o, miqdor=5, brak_bosqich="  quritish "))
check("B5 chetidagi bo'shliq olinadi ('  quritish ' → 'quritish')",
      _x.status_code == 200 and bosqich_q((js(_x) or {}).get("id")) == "quritish", (_x.status_code, _x.text[:200]))

# B6 — noto'g'ri qiymat → 400, HECH NARSA yozilmaydi (xomashyo ham yechilmaydi)
Oe = yarat([profil(100)])
for _nomi, _qiy in (("noma'lum kod", "sinish"), ("katta harf", "Kesish"), ("yorliq matni", "Quritish"),
                    ("son", 3), ("bool", True), ("ro'yxat", ["kesish"]), ("21 belgi", "k" * 21)):
    h0 = holat()
    _x = req(C, "post", "/api/returns", json=brak_tana(Oe, brak_bosqich=_qiy))
    _d = js(_x) or {}
    check(f"B6 {_nomi} → 400 aniq sabab bilan, hech narsa yozilmadi",
          _x.status_code == 400 and "brak_bosqich" in str(_d.get("detail")) and holat() == h0,
          (_x.status_code, _x.text[:200], h0, holat()))

# B7 — bosqich faqat brak uchun; boshqa sababga → 400, hech narsa yozilmaydi
for _sabab in ("Ortiqcha", "Notog'ri o'lcham", "Mijoz iltimosi"):
    h0 = holat()
    _t = brak_tana(Oe, miqdor=1, brak_bosqich="kesish")
    _t.update({"reason": _sabab, "to_stock": True})
    _x = req(C, "post", "/api/returns", json=_t)
    check(f"B7 '{_sabab}' + bosqich → 400 (\"faqat Brak\"), hech narsa yozilmadi",
          _x.status_code == 400 and "Brak" in str((js(_x) or {}).get("detail")) and holat() == h0,
          (_x.status_code, _x.text[:200]))
_t = brak_tana(Oe, miqdor=1)
_t.update({"reason": "Ortiqcha", "to_stock": False})
_x = req(C, "post", "/api/returns", json=_t)
check("B7b boshqa sabab BOSQICHSIZ — avvalgidek 200, bosqich NULL",
      _x.status_code == 200 and bosqich_q((js(_x) or {}).get("id")) is None, (_x.status_code, _x.text[:200]))

# B8 — ikkinchi to'siq: crud ildizi (marshrutni chetlab) boshqa sababli bosqichni rad etadi
h0 = holat()
_d = SessionLocal()
try:
    _iid, _nom = detal(Oe)
    _sx = schemas.ReturnItemCreate(order_id=Oe, order_item_id=_iid, item_name=_nom, quantity=1.0, unit="metr",
                                   reason="Ortiqcha", to_stock=False, brak_bosqich="kesish")
    with contextlib.redirect_stdout(_quiet):
        crud.create_return_item(_d, _sx, company_id=1)
    _b8 = "YOZILDI"
except ValueError as e:
    _d.rollback()
    _b8 = f"ValueError: {e}"
except Exception as e:                     # noqa: BLE001
    _d.rollback()
    _b8 = f"{type(e).__name__}: {e}"
finally:
    _d.close()
check("B8 crud.create_return_item: 'Ortiqcha' + bosqich → ValueError, hech narsa yozilmadi",
      _b8.startswith("ValueError") and "Brak" in _b8 and holat() == h0, (_b8, h0, holat()))

# B9 — GET /api/returns va /returns sahifasi
_ro = js(req(C, "get", "/api/returns")) or []
_bq = {x.get("id"): x.get("brak_bosqich", "YO'Q") for x in _ro if isinstance(x, dict)}
check("B9 GET /api/returns — har yozuvda brak_bosqich (bosqichli / NULL)",
      _bq.get(idb) == "kesish" and _bq.get(idd) == "qoplash" and _bq.get(ida) is None and _bq.get(idc) is None,
      {k: _bq.get(k) for k in (ida, idb, idc, idd)})
_st, _h = html(C, "/returns")
_nishon = re.findall(r'<div class="brak-bosqich"[^>]*>([^<]*)</div>', _h)
_bosqichli = sum(1 for x in _ro if isinstance(x, dict) and x.get("brak_bosqich"))
check("B9b /returns ro'yxati: bosqichli HAR brak qatorida yorliq (kod emas), bosqichsizda yo'q",
      _st == 200 and len(_nishon) == _bosqichli and "Kesish (penoplast kesish)" in _nishon
      and "Qoplash (loy tortish)" in _nishon and not any(x in KODLAR for x in _nishon),
      (_st, _nishon, _bosqichli))
_sel = re.search(r'<select id="brak-stage">(.*?)</select>', _h, re.S)
_opt = re.findall(r'<option value="([^"]*)">([^<]*)</option>', _sel.group(1)) if _sel else []
check("B9c brak oynasida #brak-stage: '— Tanlanmagan —' + 4 bosqich (lug'atdan, tartib bilan)",
      _opt == [("", "— Tanlanmagan —")] + list(zip(KODLAR, YORLIQLAR)), _opt)
_i_bos, _i_izoh, _i_qop = _h.find('id="brak-stage"'), _h.find('id="brak-notes"'), _h.find('name="brak-coating-applied"')
check("B9d tanlov brak oynasida, \"loy tortilganmi\" savolidan KEYIN, izohdan OLDIN (mavjud maydonlar joyida)",
      -1 < _i_qop < _i_bos < _i_izoh and _h.find('id="brakModal"') < _i_bos, (_i_qop, _i_bos, _i_izoh))

# B10 — begona korxona: B o'z brakiga bosqich yozadi, A ning ro'yxatida ko'rinmaydi
_rb2 = js(req(CB, "get", "/api/returns")) or []
check("B10 B korxonasi A ning bosqichli yozuvlarini ko'rmaydi",
      not any(isinstance(x, dict) and x.get("id") in (ida, idb, idc, idd) for x in _rb2), len(_rb2))

# ══════════════════════════════════════════════════════════════
# C — "Kamaytirish" va ishlab chiqarish braki (finished.html)
# ══════════════════════════════════════════════════════════════
section("C — tayyor mahsulot: kamaytirish va ishlab chiqarish braki")
F1, F2 = fp_yarat("BQ tayyor 1"), fp_yarat("BQ tayyor 2")
r1 = req(C, "post", "/api/finished/loss", json={"finished_product_id": F1, "quantity": 5, "reason": "tashishda sindi"})
r2 = req(C, "post", "/api/finished/loss", json={"finished_product_id": F2, "quantity": 5, "reason": "tashishda sindi",
                                                 "brak_bosqich": "saqlash_tashish"})
y1, y2 = yoqotishlar(F1), yoqotishlar(F2)
check("C1 kamaytirish: bosqichsiz va 'saqlash_tashish' — ikkalasi 200",
      r1.status_code == 200 and r2.status_code == 200, (r1.status_code, r1.text[:200], r2.status_code, r2.text[:200]))
check("C1b yozuv: bosqich 'saqlash_tashish' / NULL; qolgan mazmun (miqdor, tan narx, sabab) AYNAN",
      len(y1) == 1 and len(y2) == 1 and y2[0][4] == "saqlash_tashish" and y1[0][4] is None
      and y1[0][:4] == y2[0][:4], (y1, y2))
check("C1c mahsulot qoldig'i va tan narxi AYNAN kamaydi", fp_holat(F1) == fp_holat(F2) == (95.0, 950000.0),
      (fp_holat(F1), fp_holat(F2)))
for _nomi, _qiy in (("noma'lum", "sinish"), ("son", 1)):
    h0, f0 = holat(), fp_holat(F1)
    _x = req(C, "post", "/api/finished/loss", json={"finished_product_id": F1, "quantity": 5, "brak_bosqich": _qiy})
    _m = ((js(_x) or {}).get("detail") or {})
    check(f"C2 kamaytirish {_nomi} bosqich → 400 (xabar), qoldiq va yozuvlar o'zgarmadi",
          _x.status_code == 400 and "brak_bosqich" in str(_m.get("message") if isinstance(_m, dict) else _m)
          and holat() == h0 and fp_holat(F1) == f0, (_x.status_code, _x.text[:200]))

F3, F4 = fp_yarat("BQ jarayon 1", tayyor=False), fp_yarat("BQ jarayon 2", tayyor=False)
s0 = stoklar()
p3 = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F3, "brak_qty": 4})
s1 = stoklar()
p4 = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F4, "brak_qty": 4,
                                                             "brak_bosqich": "qoplash"})
s2 = stoklar()
y3, y4 = yoqotishlar(F3), yoqotishlar(F4)
check("C3 ishlab chiqarish braki: bosqichsiz va 'qoplash' — ikkalasi 200",
      p3.status_code == 200 and p4.status_code == 200, (p3.status_code, p3.text[:200], p4.status_code, p4.text[:200]))
check("C3b xomashyo yechimi AYNAN (penoplast + loy ingredientlari)",
      delta(s0, s1) == delta(s1, s2) and delta(s0, s1)[0] < 0 and delta(s0, s1)[1] < 0, (delta(s0, s1), delta(s1, s2)))
check("C3c yo'qotish yozuvi: bosqich 'qoplash' / NULL; miqdor, tan narx, sabab AYNAN, mahsulot soni o'zgarmadi",
      len(y3) == 1 and len(y4) == 1 and y4[0][4] == "qoplash" and y3[0][4] is None and y3[0][:4] == y4[0][:4]
      and fp_holat(F3)[0] == fp_holat(F4)[0] == 100.0, (y3, y4, fp_holat(F3), fp_holat(F4)))
check("C3d javob mazmuni (tan narx) AYNAN", (js(p3) or {}).get("cost_amount") == (js(p4) or {}).get("cost_amount"),
      ((js(p3) or {}).get("cost_amount"), (js(p4) or {}).get("cost_amount")))
for _nomi, _qiy in (("noma'lum", "kesib"), ("bool", False), ("ro'yxat", ["qoplash"])):
    h0 = holat()
    _x = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F3, "brak_qty": 4,
                                                                 "brak_bosqich": _qiy})
    check(f"C4 ishlab chiqarish braki {_nomi} bosqich → 400, xomashyo YECHILMADI, yozuv yo'q",
          _x.status_code == 400 and holat() == h0, (_x.status_code, _x.text[:200], h0, holat()))
h0 = holat()
_d = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        _c4 = crud.record_finished_product_production_brak(_d, F3, 4, None, created_by="t", company_id=1,
                                                           brak_bosqich="yomon")
except Exception as e:                     # noqa: BLE001
    _d.rollback()
    _c4 = {"xato": f"{type(e).__name__}: {e}"}
finally:
    _d.close()
check("C4b crud ildizi ham noto'g'ri bosqichni rad etadi (xomashyo yechilmasdan)",
      isinstance(_c4, dict) and _c4.get("success") is False and "brak_bosqich" in str(_c4.get("message"))
      and holat() == h0, (_c4, h0, holat()))
_st, _h = html(C, "/finished")
_sel = re.search(r'<select id="loss-stage"[^>]*>(.*?)</select>', _h, re.S)
_opt = re.findall(r'<option value="([^"]*)">([^<]*)</option>', _sel.group(1)) if _sel else []
check("C5 /finished \"Kamaytirish\" oynasida #loss-stage: '— Tanlanmagan —' + 4 bosqich",
      _st == 200 and _opt == [("", "— Tanlanmagan —")] + list(zip(KODLAR, YORLIQLAR)), (_st, _opt))
_i_lm, _i_sab, _i_bos = _h.find('id="lossModal"'), _h.find('id="loss-reason"'), _h.find('id="loss-stage"')
check("C5b tanlov \"Kamaytirish\" oynasi ichida, sababdan KEYIN", -1 < _i_lm < _i_sab < _i_bos, (_i_lm, _i_sab, _i_bos))

# ══════════════════════════════════════════════════════════════
# D — eski baza (ustunlarsiz) → sync_missing_columns
# ══════════════════════════════════════════════════════════════
section("D — eski baza")
_ustun_bor = (ReturnItem.__table__.c.get("brak_bosqich") is not None
              and FinishedProductLoss.__table__.c.get("brak_bosqich") is not None)
if _ustun_bor:
    with _database.engine.connect() as _c:
        _c.execute(_sqltext("ALTER TABLE return_items DROP COLUMN brak_bosqich"))
        _c.execute(_sqltext("ALTER TABLE finished_product_losses DROP COLUMN brak_bosqich"))
        _c.commit()
    with contextlib.redirect_stdout(_quiet):
        _database.sync_missing_columns()
    with _database.engine.connect() as _c:
        _n1 = _c.execute(_sqltext("SELECT COUNT(*), COUNT(brak_bosqich) FROM return_items")).fetchone()
        _n2 = _c.execute(_sqltext("SELECT COUNT(*), COUNT(brak_bosqich) FROM finished_product_losses")).fetchone()
else:
    _n1 = _n2 = (0, -1)
check("D1 ustunlar qayta qo'shildi, ESKI qatorlar HAMMASI NULL (standart yozilmadi)",
      _n1[0] > 0 and _n1[1] == 0 and _n2[0] > 0 and _n2[1] == 0, (_n1, _n2))
_ro = js(req(C, "get", "/api/returns")) or []
check("D2 eski yozuvlar API da NULL bosqich bilan ko'rinadi",
      len(_ro) > 0 and all(isinstance(x, dict) and x.get("brak_bosqich", "YO'Q") is None for x in _ro),
      [x.get("brak_bosqich", "YO'Q") for x in _ro if isinstance(x, dict)][:10])
_o = yarat([profil(50)])
_x = req(C, "post", "/api/returns", json=brak_tana(_o, miqdor=5, brak_bosqich="quritish"))
_st, _h = html(C, "/returns")
check("D3 ustun qo'shilgach yangi brak bosqich bilan yoziladi, sahifa ochiladi",
      _x.status_code == 200 and bosqich_q((js(_x) or {}).get("id")) == "quritish" and _st == 200
      and _h.count('class="brak-bosqich"') == 1, (_x.status_code, _x.text[:200], _st))

# ══════════════════════════════════════════════════════════════
# S — statik: tartib va marshrutlar
# ══════════════════════════════════════════════════════════════
section("S — statik")
_cr = inspect.getsource(crud.create_return_item)
check("S1 create_return_item: bosqich tekshiruvi yozuv yaratilishidan va xomashyo yechilishidan OLDIN",
      -1 < _cr.find("Brak bosqichi faqat") < _cr.find("item = ReturnItem(") < _cr.find("deduct_raw_material_for_brak"),
      (_cr.find("Brak bosqichi faqat"), _cr.find("item = ReturnItem(")))
check("S2 create_return_item: bosqich faqat DEFECT da yoziladi",
      "brak_bosqich=(_bosqich if reason_enum == ReturnReason.DEFECT else None)" in _cr)
_pb = inspect.getsource(crud.record_finished_product_production_brak)
_i_cv = _pb.find('"brak_bosqich": brak_bosqich})')
check("S3 ishlab chiqarish braki: bosqich _clean_val da, xomashyo yechimidan OLDIN",
      -1 < _i_cv < _pb.find("_ishlab_chiqarish_braki_xomashyo(") and "brak_bosqich=brak_bosqich" in _pb, _i_cv)
_ms = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("S4 marshrut ishlab chiqarish brakiga bosqichni uzatadi", "brak_bosqich=data.brak_bosqich," in _ms)
check("S5 /returns va /finished kontekstida lug'at (YAGONA manba)",
      _ms.count('"brak_bosqichlari": crud.BRAK_BOSQICHLARI,') == 2)
_rules = crud._val_rules()
check("S6 _val_rules: Return / Loss / ProductionBrak — bosqich 'tanlov', bo'sh mumkin, lug'at kodlari",
      all(_rules.get(k, {}).get("brak_bosqich", (None,))[0] == "tanlov"
          and _rules[k]["brak_bosqich"][1] is True and list(_rules[k]["brak_bosqich"][2]) == KODLAR
          for k in ("Return", "Loss", "ProductionBrak")))

print()
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
