#!/usr/bin/env python3
"""
test_tayyor_qiymat.py — 17-band (17a) darvozasi: TAYYOR MAHSULOT qiymat yo'llari.

NIMA UCHUN KERAK
----------------
2026-09-21 da O'LCHANGAN (asl kod, har prob toza bazada):
  * `POST /api/finished/produce` — manfiy kenglik → manfiy hajm, penoplast
    YECHILMAY mahsulot bepul paydo bo'lardi; `unit_price` Infinity → 500,
    lekin yozuv qolib `/finished` va `/api/finished` BUTUNLAY 500; NaN /
    Infinity → 500 + yarim yozuv; `true` → 1, "5" → 5 JIM; bo'sh nom;
    noto'g'ri `category`; oddiy material penoplast o'rnida yechilardi;
  * `/sell` — 1e20 narx, Infinity (→ `/api/finished/sales` 500), noto'g'ri
    to'lov usuli, 500 belgili xaridor, mavjud bo'lmagan usta, JARAYONDAGI
    mahsulot sotilardi;
  * `/sell-batch` — bir mahsulot ikki qatorda (6 + 6, qoldiq 10) → qoldiq -2;
  * `/loss`, `/add`, `/reduce`, `/production-brak` — `true` → 1, cheksizlik.

Har yomon tana: 400 VA beshta jadval (tayyor mahsulot, sotuv, brak, ombor,
ombor harakati) bayt-bayt O'ZGARMAGAN. Nazorat: UI AYNAN yuboradigan
tanalar → 200 VA yozildi.

ISHLATISH
---------
    python tools/test_tayyor_qiymat.py            # TENANT_FILTER holicha
    TENANT_FILTER=1 python tools/test_tayyor_qiymat.py
Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bitta yiqildi.
"""
import os
import sys
import json
import tempfile
import io
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "tayyor_qiymat_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, schemas                     # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from sqlalchemy import event, text                 # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, FinishedProduct, StockSource, ProductionStatus,
)
from fastapi.testclient import TestClient          # noqa: E402
import tenant_context as _tc                       # noqa: E402


@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


# Telegram xabarlari sinovda yuborilmaydi
main._send_telegram = lambda *a, **k: None

db = SessionLocal()
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {detail}")


def section(t):
    print(f"\n--- {t} ---")


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik: A (1) — ishchi korxona, B (2) — begona
# ══════════════════════════════════════════════════════════════
for _cid, _nom in ((1, "A"), (2, "B")):
    if not db.query(Company).filter(Company.id == _cid).first():
        db.add(Company(id=_cid, name=_nom))
db.commit()

with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "tq_admin", "Parol123!", UserRole.ADMIN, "TQ", company_id=1)
    PENO = crud.add_item(db, schemas.InventoryCreate(
        item_name="TQ Penoplast 14", unit="blok", stock_quantity=1000,
        price_per_unit=500000, volume_per_unit=1.0, is_penoplast=True,
        is_default_penoplast=True), company_id=1)
    # Belgisi QO'YILMAGAN, lekin nomida "penoplast" — tizim uni penoplast
    # deb hisoblaydi (services.get_default_penoplast zaxira yo'li)
    PENO_NOM = crud.add_item(db, schemas.InventoryCreate(
        item_name="Eski PENOPLAST 25", unit="blok", stock_quantity=100,
        price_per_unit=400000, volume_per_unit=1.0), company_id=1)
    MAT = crud.add_item(db, schemas.InventoryCreate(
        item_name="TQ Kimyo", unit="kg", stock_quantity=100,
        price_per_unit=2000), company_id=1)
    LOY = crud.add_item(db, schemas.InventoryCreate(
        item_name="TQ Sement", unit="kg", stock_quantity=1000,
        price_per_unit=1000), company_id=1)
    REC = crud.create_recipe(db, schemas.RecipeCreate(
        name="TQ Retsept", batch_size_kg=10,
        ingredients=[schemas.RecipeIngredientCreate(inventory_id=LOY.id, quantity_kg=1)]),
        company_id=1)
    MS_A = crud.create_master(db, schemas.MasterCreate(
        name="TQ Usta A", phone="+998900000101"), company_id=1)
    MS_B = crud.create_master(db, schemas.MasterCreate(
        name="TQ Usta B", phone="+998900000102"), company_id=2)
    PENO_B = crud.add_item(db, schemas.InventoryCreate(
        item_name="TQB Penoplast", unit="blok", stock_quantity=100,
        price_per_unit=500000, volume_per_unit=1.0, is_penoplast=True,
        is_default_penoplast=True), company_id=2)

PENO_ID, PENO_NOM_ID, MAT_ID, LOY_ID, REC_ID = PENO.id, PENO_NOM.id, MAT.id, LOY.id, REC.id
MS_A_ID, MS_B_ID = MS_A.id, MS_B.id

client = TestClient(main.app, base_url="https://testserver")
_r = client.post("/login", data={"username": "tq_admin", "password": "Parol123!"},
                 follow_redirects=False)
assert _r.status_code == 302, f"login bo'lmadi: {_r.status_code}"


class _Resp:
    def __init__(self, e):
        self.status_code = 500
        self.text = f"ISTISNO: {type(e).__name__}: {e}"

    def json(self):
        return {}


def req(method, url, **kw):
    """Server istisnosi skriptni qulatmasin (asl kodga qarshi mutatsiya)."""
    try:
        return getattr(client, method)(url, **kw)
    except Exception as e:                           # noqa: BLE001
        db.rollback()
        return _Resp(e)


def raw(s):
    return dict(content=s, headers={"Content-Type": "application/json"})


_TABLES = ["finished_products", "finished_product_sales", "finished_product_losses",
           "inventory", "inventory_movements"]


def snap():
    out = {}
    with engine.connect() as cn:
        for t in _TABLES:
            out[t] = sorted(repr(tuple(r)) for r in cn.execute(text(f'SELECT * FROM "{t}"')))
    return out


def diff(a, b):
    return {t: (len(set(b[t]) - set(a[t])), len(set(a[t]) - set(b[t])))
            for t in _TABLES if a[t] != b[t]}


_N = [0]


def nom(p="TQ"):
    _N[0] += 1
    return f"{p}_{_N[0]}"


def fp_yarat(ready=True, qty=10, company_id=1, source=StockSource.PRODUCED, status=None):
    """Tayyor mahsulot — to'g'ridan bazaga (HTTP ga bog'liq emas)."""
    if status is None:
        status = ProductionStatus.READY if ready else ProductionStatus.IN_PROGRESS
    kw = dict(company_id=company_id, name=nom("FP"), category="profil",
              width=20, thickness=10, quantity=qty, unit="metr",
              unit_price=100000, cost_price=50000 * qty / 10, source=source,
              penoplast_id=PENO_ID if company_id == 1 else PENO_B.id,
              volume_m3=0.01 * qty, unit_volume_m3=0.01, unit_loy_kg=0,
              planned_loy_kg=0, actual_loy_kg=0)
    if status != "yoq":
        kw["production_status"] = status
    fp = FinishedProduct(**kw)
    db.add(fp)
    db.commit()
    db.refresh(fp)
    return fp.id


def bad(label, method, url, **kw):
    """Yomon tana: 400 VA beshta jadval O'ZGARMAGAN."""
    a = snap()
    r = req(method, url, **kw)
    b = snap()
    d = diff(a, b)
    check(f"{label} \u2192 {r.status_code} (400 shart)", r.status_code == 400, r.text[:140])
    check(f"  \u21b3 {label}: hech narsa yozilmadi", not d, str(d))
    return r


print("=" * 66)
print("17a DARVOZASI — tayyor mahsulot qiymat yo'llari")
print("TENANT_FILTER = " + ("1 (YOQILGAN)" if _tc.ENABLED else "0 (ochiq emas)"))
print("=" * 66)

# ══════════════════════════════════════════════════════════════
section("A. POST /api/finished/produce — yomon tanalar")
# ══════════════════════════════════════════════════════════════
BASE = {"name": "TQ Karniz", "category": "profil", "is_coated": True,
        "penoplast_id": PENO_ID, "price_per_m3": None, "unit_price": 100000,
        "loy_kg": 0, "recipe_id": None, "notes": None,
        "width": 20, "thickness": 10, "length": 5, "quantity": 1}


def pb(**ch):
    d = dict(BASE)
    d.update(ch)
    if "name" not in ch:
        d["name"] = nom("PX")
    return d


def pb_raw(key, lit):
    d = pb()
    d[key] = "__X__"
    return raw(json.dumps(d).replace('"__X__"', lit))


P = "/api/finished/produce"
bad("produce width -20 (manfiy hajm)", "post", P, json=pb(width=-20))
bad("produce width -20 thickness -10", "post", P, json=pb(width=-20, thickness=-10))
bad("produce length -5", "post", P, json=pb(length=-5))
bad("produce panel quantity -3", "post", P, json=pb(category="panel", quantity=-3, length=None))
bad("produce length 1e20", "post", P, json=pb(length=1e20))
bad("produce length true", "post", P, json=pb(length=True))
bad("produce length \"5\"", "post", P, json=pb(length="5"))
bad("produce length NaN", "post", P, **pb_raw("length", "NaN"))
bad("produce length Infinity", "post", P, **pb_raw("length", "Infinity"))
bad("produce unit_price Infinity", "post", P, **pb_raw("unit_price", "Infinity"))
bad("produce unit_price 1e20", "post", P, json=pb(unit_price=1e20))
bad("produce unit_price -1", "post", P, json=pb(unit_price=-1))
bad("produce unit_price null", "post", P, json=pb(unit_price=None))
bad("produce price_per_m3 -5", "post", P, json=pb(price_per_m3=-5))
bad("produce unit_price_for_volume -5", "post", P, json=pb(unit_price_for_volume=-5))
bad("produce loy_kg Infinity", "post", P, **pb_raw("loy_kg", "Infinity"))
bad("produce loy_kg -1", "post", P, json=pb(loy_kg=-1))
bad("produce category \"xato\"", "post", P, json=pb(category="xato"))
bad("produce name \"    \"", "post", P, json=pb(name="    "))
bad("produce name \" a \" (bo'shliqsiz 1 belgi)", "post", P, json=pb(name=" a "))
bad("produce name 151 belgi", "post", P, json=pb(name="N" * 151))
bad("produce is_coated \"yes\"", "post", P, json=pb(is_coated="yes"))
bad("produce is_coated 0", "post", P, json=pb(is_coated=0))
bad("produce penoplast_id true", "post", P, json=pb(penoplast_id=True))
bad("produce penoplast_id \"5\"", "post", P, json=pb(penoplast_id=str(PENO_ID)))
bad("produce penoplast_id = oddiy material", "post", P, json=pb(penoplast_id=MAT_ID))
bad("produce penoplast_id = B korxonaniki", "post", P, json=pb(penoplast_id=PENO_B.id))
bad("produce recipe_id -1", "post", P, json=pb(recipe_id=-1))
bad("produce company_id (noma'lum kalit)", "post", P, json=pb(company_id=2))
bad("produce source (noma'lum kalit)", "post", P, json=pb(source="returned"))
bad("produce notes son", "post", P, json=pb(notes=5))
_a = snap()
_r = req("post", P, json=[1, 2])
check(f"produce tana ro'yxat \u2192 {_r.status_code} (FastAPI `dict` turi: 400/422)",
      _r.status_code in (400, 422), _r.text[:120])
check("  \u21b3 tana ro'yxat: hech narsa yozilmadi", snap() == _a)
r = bad("produce nom yo'q", "post", P, json={k: v for k, v in pb().items() if k != "name"})
check("  \u21b3 xato matni UI shaklida (detail.message)",
      isinstance(r.json().get("detail"), dict) and "message" in r.json().get("detail", {}),
      r.text[:120])

# ══════════════════════════════════════════════════════════════
section("B. /{id}/add va /{id}/reduce")
# ══════════════════════════════════════════════════════════════
F = fp_yarat()
for lbl, body in [("add 1e20", '{"quantity": 1e20}'), ("add Infinity", '{"quantity": Infinity}'),
                  ("add NaN", '{"quantity": NaN}'), ("add true", '{"quantity": true}'),
                  ("add \"2\"", '{"quantity": "2"}'), ("add -2", '{"quantity": -2}'),
                  ("add 0", '{"quantity": 0}'), ("add qo'shimcha kalit", '{"quantity": 1, "unit_price": 5}')]:
    bad(lbl, "post", f"/api/finished/{F}/add", **raw(body))
for lbl, body in [("reduce Infinity", '{"quantity": Infinity}'), ("reduce true", '{"quantity": true}'),
                  ("reduce 1e20", '{"quantity": 1e20}'), ("reduce -1", '{"quantity": -1}'),
                  ("reduce reason 10001 belgi", json.dumps({"quantity": 1, "reason": "x" * 10001})),
                  ("reduce 50 (qoldiq 10)", '{"quantity": 50}')]:
    bad(lbl, "post", f"/api/finished/{F}/reduce", **raw(body))
F_IP = fp_yarat(ready=False)
bad("reduce JARAYONDAGI mahsulot", "post", f"/api/finished/{F_IP}/reduce", json={"quantity": 1})
FB = fp_yarat(company_id=2)
for u in (f"/api/finished/{FB}/add", f"/api/finished/{FB}/reduce", "/api/finished/99999999/add"):
    a = snap()
    r = req("post", u, json={"quantity": True})
    check(f"begona/yo'q ID + YOMON tana {u.split('/')[-1]} \u2192 {r.status_code} (404 shart — oracle yo'q)",
          r.status_code == 404, r.text[:120])
    check("  \u21b3 o'zgarmadi", snap() == a)

# ══════════════════════════════════════════════════════════════
section("C. POST /api/finished/loss")
# ══════════════════════════════════════════════════════════════
F = fp_yarat()
L = "/api/finished/loss"
bad("loss true", "post", L, json={"finished_product_id": F, "quantity": True})
bad("loss Infinity", "post", L, **raw('{"finished_product_id": %d, "quantity": Infinity}' % F))
bad("loss -1", "post", L, json={"finished_product_id": F, "quantity": -1})
bad("loss 50 (qoldiq 10)", "post", L, json={"finished_product_id": F, "quantity": 50})
bad("loss finished_product_id \"id\"", "post", L, json={"finished_product_id": str(F), "quantity": 1})
bad("loss finished_product_id yo'q", "post", L, json={"quantity": 1})
bad("loss JARAYONDAGI mahsulot", "post", L, json={"finished_product_id": F_IP, "quantity": 1})
bad("loss B korxonaniki", "post", L, json={"finished_product_id": FB, "quantity": 1})

# ══════════════════════════════════════════════════════════════
section("D. POST /api/finished/sell")
# ══════════════════════════════════════════════════════════════
S = "/api/finished/sell"


def sb(**ch):
    d = {"finished_product_id": F, "quantity": 1, "unit_price": 100000, "buyer_name": None,
         "payment_method": "naqd", "master_id": None, "confirm_below_cost": False}
    d.update(ch)
    return d


bad("sell unit_price 1e20", "post", S, json=sb(unit_price=1e20))
bad("sell unit_price Infinity", "post", S, **raw(json.dumps(sb(unit_price="__X__")).replace('"__X__"', "Infinity")))
bad("sell unit_price \"100000\"", "post", S, json=sb(unit_price="100000"))
bad("sell unit_price -1", "post", S, json=sb(unit_price=-1))
bad("sell quantity Infinity", "post", S, **raw(json.dumps(sb(quantity="__X__")).replace('"__X__"', "Infinity")))
bad("sell quantity true", "post", S, json=sb(quantity=True))
bad("sell quantity 50 (qoldiq 10)", "post", S, json=sb(quantity=50))
bad("sell miqdor × narx > Numeric(12,2)", "post", S, json=sb(quantity=10, unit_price=9_999_999_999))
bad("sell payment_method \"xato\"", "post", S, json=sb(payment_method="xato"))
bad("sell payment_method null", "post", S, json=sb(payment_method=None))
bad("sell buyer_name 151 belgi", "post", S, json=sb(buyer_name="B" * 151))
bad("sell master_id 99999999", "post", S, json=sb(master_id=99999999))
r = bad("sell master_id B korxona ustasi", "post", S, json=sb(master_id=MS_B_ID))
check("  \u21b3 sabab: \"Usta topilmadi\"", "Usta topilmadi" in r.text, r.text[:120])
bad("sell confirm_below_cost \"yes\"", "post", S, json=sb(confirm_below_cost="yes"))
bad("sell JARAYONDAGI mahsulot", "post", S, json=sb(finished_product_id=F_IP))
bad("sell company_id (noma'lum kalit)", "post", S, json=sb(company_id=1))

# ══════════════════════════════════════════════════════════════
section("E. POST /api/finished/sell-batch")
# ══════════════════════════════════════════════════════════════
B = "/api/finished/sell-batch"
F = fp_yarat()
F2 = fp_yarat()


def it(fid=None, q=1, p=100000):
    return {"finished_product_id": fid or F, "quantity": q, "unit_price": p}


r = bad("batch BIR mahsulot 2 qatorda 6 + 6 (qoldiq 10)", "post", B,
        json={"items": [it(q=6), it(q=6)], "payment_method": "naqd"})
check("  \u21b3 sabab yig'indini aytadi (12)", "12" in r.text, r.text[:140])
with engine.connect() as cn:
    q0 = cn.execute(text("SELECT quantity FROM finished_products WHERE id=:i"), {"i": F}).scalar()
check(f"  \u21b3 qoldiq 10 da qoldi (manfiy emas): {q0}", q0 == 10)
bad("batch 3 qator 4 + 4 + 4 (qoldiq 10)", "post", B,
    json={"items": [it(q=4), it(F2, q=1), it(q=4), it(q=4)], "payment_method": "naqd"})
bad("batch items bo'sh", "post", B, json={"items": [], "payment_method": "naqd"})
bad("batch items yo'q", "post", B, json={"payment_method": "naqd"})
bad("batch items matn", "post", B, json={"items": "x", "payment_method": "naqd"})
bad("batch qator unit_price Infinity", "post", B,
    **raw('{"items": [{"finished_product_id": %d, "quantity": 1, "unit_price": Infinity}]}' % F))
bad("batch qator quantity true", "post", B, json={"items": [it(q=True)]})
bad("batch qator noma'lum kalit", "post", B, json={"items": [dict(it(), cost=1)]})
bad("batch qator son emas (ro'yxatda 5)", "post", B, json={"items": [5]})
bad("batch agreed_amount 1e20", "post", B, json={"items": [it()], "agreed_amount": 1e20})
bad("batch agreed_amount NaN", "post", B,
    **raw('{"items": [{"finished_product_id": %d, "quantity": 1, "unit_price": 100000}], "agreed_amount": NaN}' % F))
bad("batch agreed_amount -5", "post", B, json={"items": [it()], "agreed_amount": -5})
bad("batch payment_method \"xato\"", "post", B, json={"items": [it()], "payment_method": "xato"})
bad("batch master_id B ustasi", "post", B, json={"items": [it()], "master_id": MS_B_ID})
bad("batch JARAYONDAGI mahsulot", "post", B, json={"items": [it(F_IP)]})
bad("batch 201 qator", "post", B, json={"items": [it(q=0.01)] * 201})
bad("batch qator miqdor × narx > Numeric(12,2)", "post", B,
    json={"items": [it(q=10, p=9_999_999_999)], "confirm_below_cost": True})

# ══════════════════════════════════════════════════════════════
section("F. POST /api/finished/production-brak")
# ══════════════════════════════════════════════════════════════
PB = "/api/finished/production-brak"
bad("brak brak_qty 1e20", "post", PB, json={"finished_product_id": F, "brak_qty": 1e20})
bad("brak brak_qty Infinity", "post", PB, **raw('{"finished_product_id": %d, "brak_qty": Infinity}' % F))
bad("brak brak_qty true", "post", PB, json={"finished_product_id": F, "brak_qty": True})
bad("brak brak_qty yo'q", "post", PB, json={"finished_product_id": F})
bad("brak gips_kg_brak (endi noma'lum)", "post", PB, json={"finished_product_id": F, "brak_qty": 1, "gips_kg_brak": 5})
bad("brak notes son", "post", PB, json={"finished_product_id": F, "brak_qty": 1, "notes": 7})

# ══════════════════════════════════════════════════════════════
section("G. Ildiz: crud to'g'ridan (marshrut va pydantic chetlab)")
# ══════════════════════════════════════════════════════════════
def root(label, fn):
    a = snap()
    try:
        res = fn()
    except Exception as e:                           # noqa: BLE001
        db.rollback()
        res = {"success": None, "message": f"ISTISNO {type(e).__name__}"}
    ok = isinstance(res, dict) and res.get("success") is False
    check(f"ildiz: {label} \u2192 rad", ok, str(res)[:140])
    check(f"  \u21b3 ildiz: {label}: o'zgarmadi", snap() == a, str(diff(a, snap())))


mc = schemas.ProduceCreate.model_construct
root("produce width -20", lambda: crud.produce_finished_product(
    db, mc(**dict(pb(width=-20))), company_id=1))
root("produce penoplast = oddiy material", lambda: crud.produce_finished_product(
    db, mc(**dict(pb(penoplast_id=MAT_ID))), company_id=1))
root("produce unit_price inf", lambda: crud.produce_finished_product(
    db, mc(**dict(pb(unit_price=float("inf")))), company_id=1))
F = fp_yarat()
root("sell unit_price nan", lambda: crud.sell_finished_product(
    db, schemas.FinishedProductSaleCreate.model_construct(**sb(finished_product_id=F, unit_price=float("nan"))),
    company_id=1))
root("sell JARAYONDAGI", lambda: crud.sell_finished_product(
    db, schemas.FinishedProductSaleCreate(**sb(finished_product_id=F_IP)), company_id=1))
root("sell B ustasi", lambda: crud.sell_finished_product(
    db, schemas.FinishedProductSaleCreate(**sb(finished_product_id=F, master_id=MS_B_ID)), company_id=1))
root("batch bir mahsulot 6 + 6", lambda: crud.sell_finished_products_batch(
    db, schemas.FinishedProductSaleBatchCreate(items=[it(F, q=6), it(F, q=6)]), company_id=1))
root("loss JARAYONDAGI", lambda: crud.record_finished_product_loss(
    db, schemas.FinishedProductLossCreate(finished_product_id=F_IP, quantity=1), company_id=1))
root("loss quantity inf", lambda: crud.record_finished_product_loss(
    db, schemas.FinishedProductLossCreate.model_construct(finished_product_id=F, quantity=float("inf")),
    company_id=1))
root("add quantity nan", lambda: crud.add_to_production(db, F, float("nan"), company_id=1))
root("add quantity inf", lambda: crud.add_to_production(db, F, float("inf"), company_id=1))
root("reduce quantity inf", lambda: crud.reduce_production(db, F, float("inf"), company_id=1))
root("reduce JARAYONDAGI", lambda: crud.reduce_production(db, F_IP, 1, company_id=1))
root("brak brak_qty inf", lambda: crud.record_finished_product_production_brak(
    db, F, float("inf"), company_id=1))
root("brak brak_qty nan", lambda: crud.record_finished_product_production_brak(
    db, F, float("nan"), company_id=1))
root("batch qator unit_price nan (pydantic chetlab)", lambda: crud.sell_finished_products_batch(
    db, schemas.FinishedProductSaleBatchCreate.model_construct(items=[
        schemas.FinishedProductSaleBatchItem.model_construct(
            finished_product_id=F, quantity=1, unit_price=float("nan"))]), company_id=1))
# Manfiy narx + tasdiq: asl crud mantig'i buni JIM yozadi (SQLite da ham) —
# faqat ildizdagi qat'iy tekshiruv ushlaydi.
root("batch qator unit_price -5 + tasdiq (pydantic chetlab)", lambda: crud.sell_finished_products_batch(
    db, schemas.FinishedProductSaleBatchCreate.model_construct(items=[
        schemas.FinishedProductSaleBatchItem.model_construct(
            finished_product_id=F, quantity=1, unit_price=-5.0)], confirm_below_cost=True,
        payment_method="naqd"), company_id=1))
root("sell unit_price -5 + tasdiq (pydantic chetlab)", lambda: crud.sell_finished_product(
    db, schemas.FinishedProductSaleCreate.model_construct(**sb(
        finished_product_id=F, unit_price=-5.0, confirm_below_cost=True)), company_id=1))

# ══════════════════════════════════════════════════════════════
section("H. Statik: qoidalar sxemalar bilan mos")
# ══════════════════════════════════════════════════════════════
_rules = crud._val_rules() if hasattr(crud, "_val_rules") else None
if _rules is None:
    check("crud._val_rules mavjud (17-band qoidalari)", False, "topilmadi")
    _rules = {m: {} for m in ("Produce", "StockAdjust", "Loss", "ProductionBrak",
                              "Sale", "SaleBatchItem", "SaleBatch")}
_majb = getattr(crud, "_VAL_MAJBURIY", {})
_sx = {"Produce": schemas.ProduceCreate, "StockAdjust": schemas.StockAdjust,
       "Loss": schemas.FinishedProductLossCreate,
       "ProductionBrak": schemas.FinishedProductProductionBrakCreate,
       "Sale": schemas.FinishedProductSaleCreate,
       "SaleBatchItem": schemas.FinishedProductSaleBatchItem,
       "SaleBatch": schemas.FinishedProductSaleBatchCreate}
for m, sx in _sx.items():
    extra = set(_rules[m]) - set(sx.model_fields)
    check(f"{m}: har qoida maydoni sxemada bor", not extra, str(extra))
    maj = set(_majb.get(m, {})) - set(_rules[m])
    check(f"{m}: majburiy maydonlar qoidada bor", not maj, str(maj))
    for k, sf in sx.model_fields.items():
        if sf.is_required():
            check(f"{m}: sxemada majburiy '{k}' — qoidada ham majburiy",
                  k in _majb.get(m, {}), "")
check("ProductionBrak: gips maydonlari ruxsat ro'yxatida YO'Q",
      not ({"gips_kg_brak", "additives_brak"} & set(_rules["ProductionBrak"])))
check("Produce: kategoriya ro'yxati UI dagi 4 tur",
      set(getattr(crud, "_FP_KATEGORIYA", {})) == {"profil", "panel", "dona", "blok"})
check("To'lov usuli UI dagi 3 tur",
      set(getattr(crud, "_TOLOV_USULI", {})) == {"naqd", "karta", "bank"})
_ui = open(os.path.join(ROOT, "templates", "finished.html"), encoding="utf-8").read()
for v in ("naqd", "karta", "bank"):
    check(f"finished.html da to'lov usuli '{v}' bor", f'value="{v}"' in _ui)

# ══════════════════════════════════════════════════════════════
section("I. Nazorat: UI AYNAN yuboradigan tanalar → 200 VA yozildi")
# ══════════════════════════════════════════════════════════════
def fp_q(fid):
    with engine.connect() as cn:
        return cn.execute(text("SELECT quantity FROM finished_products WHERE id=:i"), {"i": fid}).scalar()


def inv_q(iid):
    with engine.connect() as cn:
        return cn.execute(text("SELECT stock_quantity FROM inventory WHERE id=:i"), {"i": iid}).scalar()


p0 = inv_q(PENO_ID)
r = req("post", P, json=pb())
check(f"UI produce profil \u2192 {r.status_code} (200 shart)", r.status_code == 200, r.text[:140])
check("  \u21b3 penoplast YECHILDI (5 m × 0.01 = 0.05 blok)",
      abs((p0 - inv_q(PENO_ID)) - 0.05) < 1e-6, f"{p0} -> {inv_q(PENO_ID)}")
r = req("post", P, json=pb(category="panel", width=20, thickness=10, length=None, quantity=3))
check(f"UI produce panel \u2192 {r.status_code}", r.status_code == 200, r.text[:140])
r = req("post", P, json=pb(category="dona", width=None, thickness=None, length=None,
                             quantity=4, unit_price_for_volume=50000, price_per_m3=1000000))
check(f"UI produce dona (narx-nisbat) \u2192 {r.status_code}", r.status_code == 200, r.text[:140])
r = req("post", P, json=pb(category="blok", width=None, thickness=None, length=0, quantity=2))
check(f"UI produce blok (length 0 — UI `_blokKerak || 0`) \u2192 {r.status_code}",
      r.status_code == 200, r.text[:140])
p1 = inv_q(PENO_NOM_ID)
r = req("post", P, json=pb(penoplast_id=PENO_NOM_ID))
check(f"UI produce: belgisiz, nomida \"penoplast\" \u2192 {r.status_code} (tizim ta'rifi)",
      r.status_code == 200, r.text[:140])
check("  \u21b3 o'sha material YECHILDI", inv_q(PENO_NOM_ID) < p1)
l0 = inv_q(LOY_ID)
r = req("post", P, json=pb(loy_kg=20, recipe_id=REC_ID))
check(f"UI produce loy + retsept \u2192 {r.status_code}", r.status_code == 200, r.text[:140])
check("  \u21b3 loy ingredienti yechildi", inv_q(LOY_ID) < l0)

F = fp_yarat()
r = req("post", f"/api/finished/{F}/add", json={"quantity": 2})
check(f"UI add +2 \u2192 {r.status_code}", r.status_code == 200 and fp_q(F) == 12, f"{r.status_code} {fp_q(F)}")
F_IP2 = fp_yarat(ready=False)
r = req("post", f"/api/finished/{F_IP2}/add", json={"quantity": 2})
check(f"JARAYONDAGIga qo'shish (ishlab chiqarish amali) RUXSAT \u2192 {r.status_code}",
      r.status_code == 200 and fp_q(F_IP2) == 12, f"{r.status_code} {fp_q(F_IP2)}")
r = req("post", L, json={"finished_product_id": F, "quantity": 1, "reason": None})
check(f"UI loss 1 \u2192 {r.status_code}", r.status_code == 200 and fp_q(F) == 11, f"{r.status_code} {fp_q(F)}")
p2 = inv_q(PENO_ID)
r = req("post", PB, json={"finished_product_id": F, "brak_qty": 2, "notes": None})
check(f"UI production-brak 2 \u2192 {r.status_code}", r.status_code == 200 and inv_q(PENO_ID) < p2,
      r.text[:140])
r = req("post", PB, json={"finished_product_id": F_IP2, "brak_qty": 1, "notes": "kesishda"})
check(f"JARAYONDAGI production-brak RUXSAT \u2192 {r.status_code}", r.status_code == 200, r.text[:140])
r = req("post", f"/api/finished/{F}/reduce", json={"quantity": 1, "reason": "singan"})
check(f"reduce 1 \u2192 {r.status_code}", r.status_code == 200 and fp_q(F) == 10, f"{r.status_code} {fp_q(F)}")
r = req("post", S, json=sb(finished_product_id=F, quantity=2, buyer_name="Ali",
                           payment_method="karta", master_id=MS_A_ID, confirm_below_cost=False))
check(f"UI sell (o'z ustasi, karta) \u2192 {r.status_code}", r.status_code == 200 and fp_q(F) == 8,
      r.text[:140])
r = req("post", S, json=sb(finished_product_id=F, quantity=1, unit_price=0, confirm_below_cost=True))
check(f"UI sell tan narxdan past + tasdiq \u2192 {r.status_code}", r.status_code == 200, r.text[:140])
# Qaytarilgan mahsulot — holati belgilanmaydi (bazada standart IN_PROGRESS),
# UI uni doim sotadi: server ham sotishi SHART.
F_RET = fp_yarat(source=StockSource.RETURNED, status="yoq")
with engine.connect() as cn:
    _st = cn.execute(text("SELECT production_status FROM finished_products WHERE id=:i"),
                     {"i": F_RET}).scalar()
check(f"qaytarilgan mahsulot bazada holati: {_st} (standart)", _st == "IN_PROGRESS")
r = req("post", S, json=sb(finished_product_id=F_RET, quantity=1))
check(f"QAYTARILGAN mahsulot sotiladi \u2192 {r.status_code}", r.status_code == 200, r.text[:140])
r = req("post", L, json={"finished_product_id": F_RET, "quantity": 1, "reason": "yoriq"})
check(f"QAYTARILGAN mahsulot brak \u2192 {r.status_code}", r.status_code == 200, r.text[:140])
F3, F4 = fp_yarat(), fp_yarat()
r = req("post", B, json={"items": [it(F3, q=3), it(F4, q=2)], "buyer_name": None,
                         "payment_method": "bank", "agreed_amount": 450000,
                         "master_id": MS_A_ID, "confirm_below_cost": False})
check(f"UI batch 2 mahsulot + chegirma \u2192 {r.status_code}",
      r.status_code == 200 and fp_q(F3) == 7 and fp_q(F4) == 8, r.text[:140])
F5 = fp_yarat()
r = req("post", B, json={"items": [it(F5, q=5), it(F5, q=5)], "payment_method": "naqd"})
check(f"batch bir mahsulot 5 + 5 = qoldiq (10) — RUXSAT \u2192 {r.status_code}",
      r.status_code == 200 and fp_q(F5) == 0, f"{r.status_code} {fp_q(F5)}")

for u in ("/finished", "/api/finished", "/api/finished/sales", "/api/finished/stats"):
    rr = req("get", u)
    check(f"sahifa {u} \u2192 {rr.status_code}", rr.status_code == 200, rr.text[:100])

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 66)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
sys.exit(1 if FAIL else 0)
