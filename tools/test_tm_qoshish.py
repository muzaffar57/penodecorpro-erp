#!/usr/bin/env python3
"""
test_tm_qoshish.py — kech61 darvozasi (2026-09-24): tayyor mahsulotga "+" va foyda oynasi.

NIMA UCHUN (asl kod `5e736a8` da SQLite + PG da O'LCHANGAN — `work/probe61.py`)
------------------------------------------------------------------------------
  * K61-1: MRP (Ishlab chiqarish moduli) tayyor mahsulotiga "+10" — 200, HECH qanday xomashyo
    yechilmadi, tannarx 30 000 da qoldi, 1 birlik tannarxi 3 000 -> 1 500 (bepul mahsulot). Jonli
    sinov saytida ikkala tayyor mahsulot (55, 56) MRP va "+" tugmasi CHIZILADI.
  * K61-3: eski yozuv (`unit_volume_m3` bo'sh) — 100 m dan 80 m sotilgach "+10" jami hajmni QOLDIQQA
    bo'ldi: 0.1 o'rniga 0.5 blok yechildi (5 barobar), tannarx 250 000.
  * 46-band: `volume_m3` / `actual_loy_kg` jami (sotuvda kamaymaydi) — foyda oynasi 60 m sotilgach
    "Penoplast 500 000 + Loy 260 000", "Tan narxi 304 000"; qaytgan TM da penoplast 50 000 > tan 20 000.

YECHIM (texnik — Claude): MRP mahsulotiga "+" rad (UI tugmasi ham chizilmaydi); xomashyosiz "+" umuman
rad; eski yozuv zaxirasi — jami / JAMI ishlab chiqarilgan; foyda oynasi xarajatlari QOLDIQ ulushi bilan.

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_tm_qoshish.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tm_qoshish.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tm_qoshish_test"
_DB = os.path.join(tempfile.gettempdir(), "tm_qoshish_test.db")

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
    import crud, auth                              # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, Recipe, RecipeIngredient, ReturnItem, FinishedProduct,
    StockSource, ProductionStatus,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


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


def taxminan(a, b, eps=0.01):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def tartibda(src, *qismlar):
    """Qismlar src ichida AYNAN shu tartibda uchraydimi (find — topilmasa False)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TT_admin", "Parol123!", UserRole.ADMIN, "TT Admin", company_id=1)
PRJS = [Project(company_id=1, client_name=f"TT Mijoz {i}", project_name=f"TT loyiha {i}", total_budget=0,
                total_paid=0) for i in range(4)]
PENO = Inventory(company_id=1, item_name="TT Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TT Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000,
                 category="Kimyo")
AKR = Inventory(company_id=1, item_name="TT Akril", unit="kg", stock_quantity=100_000, price_per_unit=10_000,
                category="Kimyo")
_db.add_all(PRJS + [PENO, KLEY, AKR])
_db.commit()
R1 = Recipe(company_id=1, name="TT R1", batch_size_kg=100.0)
_db.add(R1)
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0)])
_db.commit()
ID = dict(PENO=PENO.id, KLEY=KLEY.id, AKR=AKR.id, R1=R1.id)
PRJ = [p.id for p in PRJS]
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("TT_admin")
if _s1 != 302:
    print(f"LOGIN BO'LMADI: {_s1}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom():
    _n[0] += 1
    return f"TT_D{_n[0]}"


def narx(k):
    d = SessionLocal()
    try:
        d.get(Inventory, ID["PENO"]).price_per_unit = 500_000 * k
        d.get(Inventory, ID["KLEY"]).price_per_unit = 2_000 * k
        d.get(Inventory, ID["AKR"]).price_per_unit = 10_000 * k
        d.commit()
    finally:
        d.close()


def tm(fid):
    """(quantity, cost_price, unit_cost_stable yoki None, _fp_stable_unit_cost)"""
    d = SessionLocal()
    try:
        f = d.get(FinishedProduct, fid)
        if f is None:
            return (None, None, None, None)
        ucs = float(f.unit_cost_stable) if f.unit_cost_stable is not None else None
        return (float(f.quantity or 0), float(f.cost_price or 0), ucs, crud._fp_stable_unit_cost(d, f))
    finally:
        d.close()


def buyurtma(fid, uzunlik, prj):
    t = {"project_id": prj, "order_type": "product", "recipe_id": ID["R1"], "loy_kg": 0,
         "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": uzunlik,
                    "quantity": 1, "unit_price": 20_000, "is_coated": True, "penoplast_id": ID["PENO"],
                    "finished_product_id": fid}]}
    r = req(C, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
    d = js(r) or {}
    it = (d.get("items") or [{}])[0] if isinstance(d, dict) else {}
    return r.status_code, d.get("id") if isinstance(d, dict) else None, it.get("id"), it.get("name")


def tan(oid):
    d = js(req(C, "get", f"/api/orders/{oid}/profit")) or {}
    return d.get("tan_narxi")


def qaytar(oid, iid, nomi, miqdor):
    r = req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": iid, "item_name": nomi,
                                             "quantity": miqdor, "unit": "metr", "reason": "Ortiqcha",
                                             "refund_amount": 0, "to_stock": True})
    d = js(r) or {}
    rid = d.get("id") if (r.status_code == 200 and isinstance(d, dict)) else None
    fp = sc = None
    if rid:
        s = SessionLocal()
        try:
            ri = s.get(ReturnItem, rid)
            fp, sc = ri.finished_product_id, (float(ri.stock_cost) if ri.stock_cost is not None else None)
        finally:
            s.close()
    return r.status_code, rid, fp, sc





def inv(k):
    d = SessionLocal()
    try:
        return float(d.get(Inventory, ID[k]).stock_quantity)
    finally:
        d.close()


def fpx(fid):
    d = SessionLocal()
    try:
        f = d.get(FinishedProduct, fid)
        if f is None:
            return None
        return dict(q=float(f.quantity or 0), prod=float(f.produced_quantity or 0), cost=float(f.cost_price or 0),
                    ucs=(float(f.unit_cost_stable) if f.unit_cost_stable is not None else None),
                    vol=float(f.volume_m3 or 0), loy=float(f.actual_loy_kg or 0))
    finally:
        d.close()


def ishlab(nomi, uzunlik, loy_kg, qop=True, narx_m=20_000):
    t = {"name": nomi, "category": "profil", "width": 20, "thickness": 10, "length": uzunlik, "is_coated": qop,
         "penoplast_id": ID["PENO"], "unit_price": narx_m, "loy_kg": loy_kg}
    if loy_kg:
        t["recipe_id"] = ID["R1"]
    fid = (js(req(C, "post", "/api/finished/produce", json=t)) or {}).get("product_id")
    req(C, "post", f"/api/finished/{fid}/complete")
    return fid


def sot(fid, miqdor):
    return req(C, "post", "/api/finished/sell", json={"finished_product_id": fid, "quantity": miqdor,
                                                      "unit_price": 20_000, "buyer_name": nom(),
                                                      "confirm_below_cost": True}).status_code


# ── MRP: xomashyo, tur, BOM, ishlab chiqarish (10 m², 1 m² = Tosh 3 kg x 1 000) ──
_d = SessionLocal()
TOSH = Inventory(company_id=1, item_name="TQ Tosh", unit="kg", stock_quantity=10_000, price_per_unit=1_000, category="Kimyo")
_d.add(TOSH)
_d.commit()
ID["TOSH"] = TOSH.id
_d.close()
PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "TQ Travertin", "unit": "m²", "input_template": "quantity_only", "pricing_formula": "unit_based"})) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "V1", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 3}]})) or {}).get("id")
PO = ((js(req(C, "post", "/api/production/orders", json={"product_type_id": PT, "bom_id": BOM, "quantity": 10,
                                                          "source_type": "warehouse_stock"})) or {})
      .get("production_order") or {}).get("id")
req(C, "post", f"/api/production/orders/{PO}/start")
req(C, "post", f"/api/production/orders/{PO}/complete")
_d = SessionLocal()
try:
    from production_models import ProductionOrder as _PO
    MFP = _d.get(_PO, PO).finished_product_id
finally:
    _d.close()

# ══════════════════════════════════════════════════════════════
section("A. MRP tayyor mahsulotiga '+' rad etiladi (K61-1)")
# ══════════════════════════════════════════════════════════════
f0, t0 = fpx(MFP), inv("TOSH")
check("A0 fikstura: MRP TM 10 m², tannarx 30 000, birlik 3 000", f0 and taxminan(f0["q"], 10)
      and taxminan(f0["cost"], 30_000) and taxminan(f0["ucs"], 3_000), f0)
r = req(C, "post", f"/api/finished/{MFP}/add", json={"quantity": 10})
check("A1 '+10' -> 400", r.status_code == 400, (r.status_code, r.text[:200]))
check("A2 xabar: «Ishlab chiqarish» bo'limida yarating", "Ishlab chiqarish" in r.text and "partiyani" in r.text,
      r.text[:300])
f1 = fpx(MFP)
check("A3 TM o'zgarmadi (10 / 30 000 / 3 000)", f1 and taxminan(f1["q"], 10) and taxminan(f1["cost"], 30_000)
      and taxminan(f1["ucs"], 3_000) and taxminan(f1["prod"], 10), f1)
check("A4 xomashyo o'zgarmadi", taxminan(inv("TOSH"), t0), (t0, inv("TOSH")))
_d = SessionLocal()
try:
    _f = _d.get(FinishedProduct, MFP)
    _f.category = "profil"          # turi bor, lekin turkum boshqa — MRP sharti product_type_id dan ham
    _d.commit()
finally:
    _d.close()
r = crud.add_to_production(SessionLocal(), MFP, 5.0, performed_by="t", company_id=1)
check("A5 product_type_id li TM (turkum profil) ham rad", r.get("success") is False and "Ishlab chiqarish"
      in str(r.get("message")), r)
_d = SessionLocal()
try:
    _f = _d.get(FinishedProduct, MFP)
    _f.category = "dynamic_bom"
    _d.commit()
finally:
    _d.close()

# ══════════════════════════════════════════════════════════════
section("B. Xomashyosiz '+' — umumiy to'siq")
# ══════════════════════════════════════════════════════════════
_d = SessionLocal()
try:
    _x = FinishedProduct(company_id=1, name="TQ xomashyosiz", category="profil", unit="metr", quantity=10,
                         produced_quantity=10, source=StockSource.PRODUCED, production_status=ProductionStatus.READY,
                         unit_price=1_000, cost_price=5_000, volume_m3=0.0)
    _d.add(_x)
    _d.commit()
    XFP = _x.id
finally:
    _d.close()
r = req(C, "post", f"/api/finished/{XFP}/add", json={"quantity": 5})
check("B1 penoplast / loy yo'q TM ga '+5' -> 400", r.status_code == 400, (r.status_code, r.text[:200]))
check("B2 xabar: 1 birligiga qancha xomashyo noma'lum", "noma'lum" in r.text, r.text[:300])
check("B3 TM o'zgarmadi (10 / 5 000)", taxminan(fpx(XFP)["q"], 10) and taxminan(fpx(XFP)["cost"], 5_000), fpx(XFP))

# ══════════════════════════════════════════════════════════════
section("C. Oddiy '+' (unit_volume_m3 bor) — o'zgarmagan")
# ══════════════════════════════════════════════════════════════
CFP = ishlab("TQ oddiy", 100, 50)
sot(CFP, 60)
p0 = inv("PENO")
r = req(C, "post", f"/api/finished/{CFP}/add", json={"quantity": 20})
check("C1 '+20' 200, penoplast 0.2 blok (barqaror nisbat)", r.status_code == 200
      and taxminan(p0 - inv("PENO"), 0.2, 1e-6), (r.status_code, p0 - inv("PENO"), r.text[:200]))
check("C2 TM 60 m", taxminan(fpx(CFP)["q"], 60), fpx(CFP))

# ══════════════════════════════════════════════════════════════
section("D. Eski yozuv (unit_volume_m3 bo'sh) — sotuvdan keyin '+' (K61-3)")
# ══════════════════════════════════════════════════════════════
DFP = ishlab("TQ eski", 100, 50)
_d = SessionLocal()
try:
    _f = _d.get(FinishedProduct, DFP)
    _f.unit_volume_m3 = None
    _f.unit_loy_kg = None
    _d.commit()
finally:
    _d.close()
sot(DFP, 80)
p0, k0 = inv("PENO"), inv("KLEY")
r = req(C, "post", f"/api/finished/{DFP}/add", json={"quantity": 10})
d = js(r) or {}
check("D1 '+10' 200, penoplast 0.1 blok (1 blok / 100 m; asl: 0.5 — qoldiq 20 m ga bo'lardi)",
      r.status_code == 200 and taxminan(p0 - inv("PENO"), 0.1, 1e-6), (r.status_code, p0 - inv("PENO"), r.text[:200]))
check("D2 loy 5 kg (50 kg / 100 m) — Kley 3 kg (asl: 15 kg)", taxminan(k0 - inv("KLEY"), 3.0, 1e-6), k0 - inv("KLEY"))
check("D3 qo'shilgan tannarx 76 000 (50 000 + 26 000; asl: 380 000)", taxminan(d.get("add_cost"), 76_000, 1), d)
_d = SessionLocal()
try:
    _f = _d.get(FinishedProduct, DFP)
    _f.produced_quantity = None
    _d.commit()
finally:
    _d.close()
p0 = inv("PENO")
r = req(C, "post", f"/api/finished/{DFP}/add", json={"quantity": 10})
check("D4 produced_quantity bo'sh — zaxira qoldiq (jami 1.1 / 30 m x 10)", r.status_code == 200
      and taxminan(p0 - inv("PENO"), 1.1 / 30 * 10, 1e-6), (r.status_code, p0 - inv("PENO")))

# ══════════════════════════════════════════════════════════════
section("E. Foyda oynasi — xarajatlar QOLDIQ uchun (46-band)")
# ══════════════════════════════════════════════════════════════
EFP = ishlab("TQ foyda", 100, 50)
e0 = js(req(C, "get", f"/api/finished/{EFP}/profit")) or {}
check("E1 sotuvdan oldin: penoplast 500 000, loy 260 000 (50 kg), tan 760 000, hajm 1.0",
      taxminan(e0.get("penoplast_cost"), 500_000) and taxminan(e0.get("loy_cost"), 260_000)
      and taxminan(e0.get("loy_kg"), 50) and taxminan(e0.get("total_cost"), 760_000)
      and taxminan(e0.get("volume_m3"), 1.0, 1e-6), e0)
sot(EFP, 60)
e1 = js(req(C, "get", f"/api/finished/{EFP}/profit")) or {}
check("E2 60 m sotilgach: penoplast 200 000 (asl: 500 000)", taxminan(e1.get("penoplast_cost"), 200_000), e1)
check("E3 loy 20 kg / 104 000 (asl: 50 kg / 260 000)", taxminan(e1.get("loy_kg"), 20)
      and taxminan(e1.get("loy_cost"), 104_000), e1)
check("E4 qatorlar yig'indisi = tan narxi 304 000", taxminan(e1.get("penoplast_cost", 0) + e1.get("loy_cost", 0),
      e1.get("total_cost", -1), 1) and taxminan(e1.get("total_cost"), 304_000), e1)
check("E5 hajm 0.4 (qoldiq), jami 1.0 / 50 kg tarix uchun", taxminan(e1.get("volume_m3"), 0.4, 1e-6)
      and taxminan(e1.get("jami_volume_m3"), 1.0, 1e-6) and taxminan(e1.get("jami_loy_kg"), 50), e1)
s, O1, I1, N1 = buyurtma(None, 10, PRJ[0])
req(C, "post", "/api/deliveries", json={"order_id": O1, "items": [{"order_item_id": I1, "quantity": 10}], "notes": nom()})
s2, RID, RFP, SC = qaytar(O1, I1, N1, 10)
sot(RFP, 6)
e2 = js(req(C, "get", f"/api/finished/{RFP}/profit")) or {}
check("E6 qaytgan TM 6 / 10 sotilgach: penoplast = tan narxi (qolgan 4 m)", RFP and
      taxminan(e2.get("penoplast_cost"), e2.get("total_cost", -1), 1) and e2.get("total_cost", 0) > 0, (s2, e2))
check("E7 MRP TM: penoplast / loy 0, tan narxi 30 000", taxminan((js(req(C, "get", f"/api/finished/{MFP}/profit"))
      or {}).get("total_cost"), 30_000) and (js(req(C, "get", f"/api/finished/{MFP}/profit")) or {}).get(
      "penoplast_cost") == 0, js(req(C, "get", f"/api/finished/{MFP}/profit")))
_d = SessionLocal()
try:
    _f = _d.get(FinishedProduct, EFP)
    _f.quantity = 150.0             # buzilgan / qo'lda o'zgartirilgan yozuv: qoldiq > jami ishlab chiqarilgan
    _d.commit()
finally:
    _d.close()
e3 = js(req(C, "get", f"/api/finished/{EFP}/profit")) or {}
check("E8 qoldiq > jami bo'lsa ulush 1 da cheklanadi (hajm 1.0, 1.5 EMAS; loy 50 kg)",
      taxminan(e3.get("volume_m3"), 1.0, 1e-6) and taxminan(e3.get("loy_kg"), 50), e3)

# ══════════════════════════════════════════════════════════════
section("F. API va UI (statik)")
# ══════════════════════════════════════════════════════════════
_l = js(req(C, "get", "/api/finished")) or []
_l = _l if isinstance(_l, list) else (_l.get("items") or [])
_e = [x for x in _l if x.get("id") == EFP]
check("F1 /api/finished produced_quantity beradi (100)", _e and taxminan(_e[0].get("produced_quantity"), 100), _e[:1])
_h = open(os.path.join(ROOT, "templates", "finished.html"), encoding="utf-8").read()
check("F2 '+' tugmasi MRP da chizilmaydi (shart stepFp dan OLDIN)",
      tartibda(_h, "${(i.category !== 'dynamic_bom' && !i.product_type_id) ? `", 'id="fq-${i.id}"',
               'onclick="stepFp(${i.id})"'))
check("F3 '+' oldindan ko'rish: jami / produced_quantity",
      "const bol = (item.produced_quantity > 0) ? item.produced_quantity : item.quantity;" in _h
      and "unitVol = (item.volume_m3 || 0) / bol;" in _h and "unitLoy = (item.actual_loy_kg || 0) / bol;" in _h)
check("F4 foyda oynasi hajm / loy serverdan (qoldiq)",
      "qVol = d.volume_m3 || 0;" in _h and "📦 Hajm (qoldiq): <b>${qVol.toFixed(4)} m³</b>" in _h
      and "row(`🧱 Loy (${qLoyTxt} kg" in _h and "row(`🧱 Loy (${i.actual_loy_kg} kg" not in _h)
_c = inspect.getsource(crud.add_to_production)
check("F5 crud: MRP sharti base_qty dan OLDIN, umumiy to'siq yetarlilik tekshiruvidan OLDIN",
      tartibda(_c, 'if fp.category == "dynamic_bom" or getattr(fp, "product_type_id", None) is not None:',
               "base_qty = float(fp.quantity or 0)", "if add_volume <= 0 and add_loy <= 0:", "shortages = []"))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
