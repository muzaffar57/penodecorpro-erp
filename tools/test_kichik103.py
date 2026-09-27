#!/usr/bin/env python3
"""
test_kichik103.py — kech103 kichik bandlari darvozasi (server tomoni + shablonlar): 45, 63, 83, 90, 69 (+ 11, 25, 55,
64 — statik). UI funksiyalari (58 / 63 / 83 / 90 / 62 / 66 / K103-3 / K103-4) — `tools/test_kichik103_ui.js`.

NIMA UCHUN (asl kod `d081624` = zip 96 da O'LCHANGAN — `work/probe103ui.py`, HAQIQIY brauzer)
-------------------------------------------------------------------------------------------
  * 45: «Tayyor» javobidagi "👷 Usta KPI" eski formula edi — kelishilgan summaning 3 % + qoplamali metr × 1 000 so'm
    (profil metri `length × quantity`): 500 000 lik 10 m buyurtmada 25 000 (quantity 10 bo'lsa 115 000), ustaning
    haqiqiy KPI hissasi esa (buyurtma foydasi 430 000 × 10 %) 43 000. Endi shu buyurtma foydasi × ustaning KPI foizi.
  * 63: tahrirda omborga ORTIQCHA qaytarilgan qism sabab bo'lsa ham sarlavha "Topshirilgan miqdordan kam qilib bo'lmaydi!".
  * 83: yetkazish holatida MRP detalining TAYYOR (ishlab chiqarilgan) miqdori yo'q edi — oyna faqat qoldiqni ko'rsatardi.
  * 90: Qaytarishlar sahifasi o'chirish tasdig'i MRP ortiqchasini (band → erkin qoldiq, `mrp_ozod`) aytmasdi.
  * 69 (`work/probe69.py`): tahrirda penoplast VA yangi qoplama retsepti xomashyosi yetmasa 409 faqat penoplastni
    ko'rsatardi; tasdiqdan keyin retsept xomashyosi so'ralmay −19 kg ga tushdi.
  * 55 / 11 / 64: o'lik kod (`services.process_coating` va qo'shnilari — korxonasiz `ilike` bilan ombordan yechardi;
    `r.payment_warning`; `showProfit`); 25: `test_tayyor_qiymat.py` da `engine.dispose()` yo'q edi.

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_kichik103.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_kichik103.py
"""
import os
import sys
import json
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "kichik103_test"
_DB = os.path.join(tempfile.gettempdir(), "kichik103_test.db")

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
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime                      # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, services                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, Recipe, RecipeIngredient, ReturnItem, Master, Order, Payment,
    FinishedProduct,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
STATUSLAR = []


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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:400]}")


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
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    STATUSLAR.append((metod, url, r.status_code))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def taxminan(a, b, eps=0.5):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "K103_admin", "Parol123!", UserRole.ADMIN, "K103 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K103 Penoplast", unit="blok", stock_quantity=100_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="K103 Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000,
                 category="Kimyo")
QUM = Inventory(company_id=1, item_name="K103 Qum", unit="kg", stock_quantity=100_000, price_per_unit=1_000,
                category="Kimyo")
_db.add_all([PENO, KLEY, QUM])
_db.flush()
REC = Recipe(company_id=1, name="K103 retsept", batch_size_kg=100.0)
_db.add(REC)
_db.flush()
_db.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
_db.commit()
ID = {"PENO": PENO.id, "REC": REC.id, "QUM": QUM.id, "KLEY": KLEY.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "K103_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom(p="K"):
    _n[0] += 1
    return f"{p}{_n[0]}"


PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "K103 Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Asosiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["QUM"], "quantity": 3}]})) or {}).get("id")


def muhit(kpi=10.0):
    n = nom("M")
    s = SessionLocal()
    try:
        p = Project(company_id=1, client_name=f"{n} Mijoz", project_name=f"{n} loyiha", total_budget=0, total_paid=0)
        m = Master(company_id=1, name=f"{n} Usta", phone="+99893" + str(1_000_000 + _n[0]).zfill(7),
                   kpi_percent=kpi, is_active=True)
        s.add_all([p, m])
        s.commit()
        return p.id, m.id
    finally:
        s.close()


def profil(n, narx, q=1):
    return {"name": nom("D"), "category": "profil", "width": 20, "thickness": 10, "length": n, "quantity": q,
            "unit_price": narx, "is_coated": True, "penoplast_id": ID["PENO"], "recipe_id": ID["REC"]}


def mrp(n, narx=100_000):
    return {"name": nom("D"), "category": "mrp_product", "quantity": n, "unit_price": narx, "is_coated": False,
            "penoplast_id": None, "product_type_id": PT}


def buyurtma(pid, mid, detallar, loy):
    tana = {"project_id": pid, "order_type": "product", "loy_kg": loy, "recipe_id": ID["REC"], "items": detallar}
    if mid:
        tana["master_id"] = mid
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    d = js(r) or {}
    ids = [x.get("id") for x in (d.get("items") or [])] if isinstance(d, dict) else []
    return r.status_code, (d.get("id") if isinstance(d, dict) else None), ids, tana


def yuk(oid, iid, miqdor):
    return req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom("yuk"),
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"}).status_code


def ishlab(oid, iid, miqdor):
    r = req(C, "post", "/api/production/orders", json={
        "product_type_id": PT, "bom_id": BOM, "quantity": miqdor, "source_type": "customer_order",
        "source_order_id": oid, "source_order_item_id": iid})
    po = ((js(r) or {}).get("production_order") or {}).get("id") if isinstance(js(r), dict) else None
    if not po:
        return None
    for q in ("start", "complete"):
        if req(C, "post", f"/api/production/orders/{po}/{q}").status_code != 200:
            return None
    return po


def usta_hissa(mid):
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            k = services.calculate_monthly_master_kpi(s, datetime.utcnow().year, datetime.utcnow().month, company_id=1)
        nomi = s.get(Master, mid).name
    finally:
        s.close()
    oy = [b for b in (k.get("breakdown") or []) if b.get("master_name") == nomi]
    return (float(oy[0]["monthly_profit"]), float(oy[0]["kpi_amount"])) if oy else (0.0, 0.0)


def foyda(oid):
    return float((js(req(C, "get", f"/api/orders/{oid}/profit")) or {}).get("foyda") or 0)


# ══════════════════════════════════════════════════════════════
section("A. 45 — «Tayyor» javobidagi usta KPI = shu buyurtma foydasi × ustaning KPI foizi")
# ══════════════════════════════════════════════════════════════
pid, mid = muhit(10.0)
s, oid, ids, _ = buyurtma(pid, mid, [profil(10.0, 500_000)], 10.0)
r = req(C, "post", f"/api/orders/{oid}/ready", params={"loy_kg": "10"})
k = (js(r) or {}).get("master_kpi") or {}
_f = foyda(oid)
check("A1 «Tayyor» 200, master_kpi bor", s == 200 and r.status_code == 200 and bool(k), (s, r.status_code, k))
check("A2 foiz = ustaning kpi_percent (10), foyda = buyurtma foydasi", taxminan(k.get("kpi_percent"), 10)
      and taxminan(k.get("foyda"), _f), (k, _f))
check("A3 total_kpi = foyda × 10 % (asl: 3 % + metr × 1 000 = 25 000)", taxminan(k.get("total_kpi"), round(_f * 0.10))
      and not taxminan(k.get("total_kpi"), 25_000), (k, _f))
_h = usta_hissa(mid)
check("A4 = ustaning HAQIQIY oylik KPI hissasi (calculate_monthly_master_kpi)", taxminan(k.get("total_kpi"), _h[1], 1),
      (k, _h))
check("A5 eski kalitlar yo'q (cashback_3%, meter_bonus)", "cashback_3%" not in k and "meter_bonus" not in k, k)
pid, mid = muhit(10.0)
s, oid, ids, _ = buyurtma(pid, mid, [profil(10.0, 50_000, q=10)], 10.0)
r = req(C, "post", f"/api/orders/{oid}/ready", params={"loy_kg": "10"})
k = (js(r) or {}).get("master_kpi") or {}
check("A6 profil quantity 10 — total_kpi foydadan (asl: 115 000 — metr length × quantity)",
      taxminan(k.get("total_kpi"), round(foyda(oid) * 0.10)) and taxminan(k.get("total_kpi"), usta_hissa(mid)[1], 1),
      (k, foyda(oid), usta_hissa(mid)))
pid, mid = muhit(0.0)
s, oid, ids, _ = buyurtma(pid, mid, [profil(5.0, 300_000)], 5.0)
r = req(C, "post", f"/api/orders/{oid}/ready", params={"loy_kg": "5"})
check("A7 ustaning KPI foizi 0 — master_kpi yo'q", r.status_code == 200 and not (js(r) or {}).get("master_kpi"),
      (r.status_code, (js(r) or {}).get("master_kpi")))
pid, _m = muhit(10.0)
s, oid, ids, _ = buyurtma(pid, None, [profil(5.0, 300_000)], 5.0)
r = req(C, "post", f"/api/orders/{oid}/ready", params={"loy_kg": "5"})
check("A8 ustasiz buyurtma — master_kpi yo'q", r.status_code == 200 and not (js(r) or {}).get("master_kpi"),
      (r.status_code, (js(r) or {}).get("master_kpi")))
pid, mid = muhit(10.0)
s, oid, ids, _ = buyurtma(pid, mid, [profil(10.0, 1_000)], 10.0)
r = req(C, "post", f"/api/orders/{oid}/ready", params={"loy_kg": "10"})
k = (js(r) or {}).get("master_kpi") or {}
check("A9 foyda manfiy — total_kpi 0 (oylik KPI kabi, manfiy KPI yo'q), foyda manfiy ko'rsatiladi",
      r.status_code == 200 and taxminan(k.get("total_kpi"), 0) and float(k.get("foyda") or 0) < 0, k)

# ══════════════════════════════════════════════════════════════
section("B. 63 — tahrir: omborga ortiqcha qaytarilgan qism sabab bo'lsa sarlavha shuni aytadi")
# ══════════════════════════════════════════════════════════════
pid, mid = muhit(10.0)
s, oid, ids, tana = buyurtma(pid, mid, [profil(10.0, 500_000)], 10.0)
check("B0 yuk 4 m 200", yuk(oid, ids[0], 4) == 200)
r = req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": ids[0], "item_name": "x", "quantity": 7,
                                         "unit": "metr", "reason": "Ortiqcha", "refund_amount": 0, "to_stock": True})
check("B1 qaytarish 7 m (4 topshirilgandan + 3 ortiqcha) 200", r.status_code == 200, r.text[:200])
_ds = js(req(C, "get", f"/api/orders/{oid}/delivery-status")) or {}
_it = (_ds.get("items") or [{}])[0]
check("B2 yetkazish holati: topshirilgan 4, ortiqcha 3, qoldi 3", taxminan(_it.get("delivered"), 4, 0.001)
      and taxminan(_it.get("ortiqcha"), 3, 0.001) and taxminan(_it.get("remaining"), 3, 0.001), _it)
t6 = dict(tana)
t6["items"] = [dict(tana["items"][0], length=6.0)]
r = req(C, "put", f"/api/orders/{oid}", json=t6, params={"confirm_shortage": "true"})
_d = (js(r) or {}).get("detail") or {}
check("B3 6 m (kamida 7) — 400, sarlavha ortiqchani aytadi",
      r.status_code == 400 and _d.get("message") == "Topshirilgan va omborga ortiqcha qaytarilgan miqdordan kam qilib bo'lmaydi!",
      (r.status_code, _d))
check("B4 izoh qatori o'zgarmagan (kamida 7)", any("kamida 7" in str(x) for x in (_d.get("shortages") or [])), _d)
pid, mid = muhit(10.0)
s, oid, ids, tana = buyurtma(pid, mid, [profil(10.0, 500_000)], 10.0)
yuk(oid, ids[0], 4)
t3 = dict(tana)
t3["items"] = [dict(tana["items"][0], length=3.0)]
r = req(C, "put", f"/api/orders/{oid}", json=t3, params={"confirm_shortage": "true"})
_d = (js(r) or {}).get("detail") or {}
check("B5 ortiqchasiz (faqat topshirilgan 4) — eski sarlavha AYNAN",
      r.status_code == 400 and _d.get("message") == "Topshirilgan miqdordan kam qilib bo'lmaydi!", (r.status_code, _d))

# ══════════════════════════════════════════════════════════════
section("C. 83 — yetkazish holatida MRP detalining TAYYOR miqdori")
# ══════════════════════════════════════════════════════════════
pid, mid = muhit(10.0)
s, oid, ids, _ = buyurtma(pid, mid, [mrp(10.0), profil(5.0, 200_000)], 5.0)
check("C0 MRP buyurtma 200 + ishlab chiqarish 4", s == 200 and ishlab(oid, ids[0], 4) is not None)
_ds = js(req(C, "get", f"/api/orders/{oid}/delivery-status")) or {}
_its = {x.get("id"): x for x in (_ds.get("items") or [])}
check("C1 MRP detali: mrp_tayyor 4, qoldi 10", taxminan(_its.get(ids[0], {}).get("mrp_tayyor"), 4, 0.001)
      and taxminan(_its.get(ids[0], {}).get("remaining"), 10, 0.001), _its.get(ids[0]))
check("C2 MRP emas detal: mrp_tayyor None", ids[1] in _its and _its[ids[1]].get("mrp_tayyor") is None, _its.get(ids[1]))
check("C3 yuk 4 (tayyor) 200", yuk(oid, ids[0], 4) == 200)
_ds = js(req(C, "get", f"/api/orders/{oid}/delivery-status")) or {}
_its = {x.get("id"): x for x in (_ds.get("items") or [])}
check("C4 topshirilgach: mrp_tayyor 0, qoldi 6", taxminan(_its.get(ids[0], {}).get("mrp_tayyor"), 0, 0.001)
      and taxminan(_its.get(ids[0], {}).get("remaining"), 6, 0.001), _its.get(ids[0]))
r = req(C, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": ids[0], "quantity": 1}],
                                            "notes": nom("yuk"), "transport_cost": 0, "transport_payer": "none",
                                            "payment_method": "naqd"})
check("C5 server qoidasi o'zgarmagan: tayyordan ko'p — 400", r.status_code == 400, (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════
section("D. 90 — MRP ortiqchasi (band → erkin qoldiq): model xossasi va Qaytarishlar sahifasi")
# ══════════════════════════════════════════════════════════════
pid, mid = muhit(10.0)
s, oid, ids, _ = buyurtma(pid, mid, [mrp(10.0)], 0.0)
check("D0 ishlab chiqarish 10 + yuk 4", ishlab(oid, ids[0], 10) is not None and yuk(oid, ids[0], 4) == 200)
r = req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": ids[0], "item_name": "x", "quantity": 7,
                                         "unit": "m²", "reason": "Ortiqcha", "refund_amount": 0, "to_stock": True})
RID = (js(r) or {}).get("id") if r.status_code == 200 else None
_s = SessionLocal()
try:
    _ri = _s.get(ReturnItem, RID) if RID else None
    _mo = getattr(_ri, "mrp_ozod_miqdor", None) if _ri is not None else None
    _sq = float(_ri.stock_qty or 0) if _ri is not None else None
finally:
    _s.close()
check("D1 qaytarish 200: omborga 4 (topshirilgandan), mrp_ozod_miqdor 3", RID and taxminan(_sq, 4, 0.001)
      and taxminan(_mo, 3, 0.001), (r.status_code, _sq, _mo, r.text[:150]))
_h = req(C, "get", "/returns")
_m = _h.text if _h.status_code == 200 else ""
_i = _m.find(f'id="row-{RID}"')
_satr = _m[_i:_i + 600] if _i >= 0 else ""
check("D2 /returns qatorida data-mrp=\"3 m²\" va data-stock=\"4 m²\"", 'data-mrp="3 m²"' in _satr
      and 'data-stock="4 m²"' in _satr, _satr[:400])
_s = SessionLocal()
try:
    _b1 = ReturnItem(company_id=1, item_name="b", quantity=1, unit="dona", mrp_ozod=None)
    _b2 = ReturnItem(company_id=1, item_name="b", quantity=1, unit="dona", mrp_ozod="buzilgan")
    _b3 = ReturnItem(company_id=1, item_name="b", quantity=1, unit="dona", mrp_ozod=json.dumps([[1, 1.5], [2, 2.25]]))
    _xs = tuple(getattr(_b, "mrp_ozod_miqdor", None) for _b in (_b1, _b2, _b3))
finally:
    _s.close()
check("D3 mrp_ozod_miqdor: NULL 0, buzilgan 0, ikki TM 3.75", _xs == (0.0, 0.0, 3.75), _xs)
_i2 = _m.find('data-mrp="')
check("D4 boshqa qatorlarda data-mrp bo'sh (ortiqchasiz qaytarish)", _m.count('data-mrp=""') >= 1 or _m.count('data-mrp="') == 1,
      _m.count('data-mrp='))

# ══════════════════════════════════════════════════════════════
section("E. 69 — tahrir: penoplast VA yangi qoplama retsepti xomashyosi yetmasa — birinchi 409 IKKALASINI ko'rsatadi")
# ══════════════════════════════════════════════════════════════
_s = SessionLocal()
try:
    _pk = Inventory(company_id=1, item_name="K103 Penoplast kam", unit="blok", stock_quantity=0.05, price_per_unit=500_000,
                    volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
    _ak = Inventory(company_id=1, item_name="K103 Akril kam", unit="kg", stock_quantity=1.0, price_per_unit=10_000,
                    category="Kimyo")
    _mo = Inventory(company_id=1, item_name="K103 Marmar kop", unit="kg", stock_quantity=100_000, price_per_unit=1_000,
                    category="Kimyo")
    _s.add_all([_pk, _ak, _mo])
    _s.flush()
    _r2 = Recipe(company_id=1, name="K103 R2 kam", batch_size_kg=100.0)
    _r3 = Recipe(company_id=1, name="K103 R3 kop", batch_size_kg=100.0)
    _s.add_all([_r2, _r3])
    _s.flush()
    _s.add_all([RecipeIngredient(recipe_id=_r2.id, inventory_id=_ak.id, quantity_kg=100.0),
                RecipeIngredient(recipe_id=_r3.id, inventory_id=_mo.id, quantity_kg=100.0)])
    _s.commit()
    ID.update(PK=_pk.id, AK=_ak.id, R2=_r2.id, R3=_r3.id)
finally:
    _s.close()


def ombor69():
    _s = SessionLocal()
    try:
        return (round(float(_s.get(Inventory, ID["PK"]).stock_quantity), 4), round(float(_s.get(Inventory, ID["AK"]).stock_quantity), 4))
    finally:
        _s.close()


def tahrir69(retsept, uzunlik, tasdiq=False, peno=0.05, bosh_retsept=None, yuk_oldin=0.0):
    _s = SessionLocal()
    try:      # har holat o'z boshlang'ich qoldig'idan (oldingi tasdiqlangan tahrir manfiyga tushirgan bo'lishi mumkin)
        _s.get(Inventory, ID["PK"]).stock_quantity = peno
        _s.get(Inventory, ID["AK"]).stock_quantity = 1.0
        _s.commit()
    finally:
        _s.close()
    pid, mid = muhit(10.0)
    _br = bosh_retsept or ID["REC"]
    det = {"name": nom("D"), "category": "profil", "width": 20, "thickness": 10, "length": 4.0, "quantity": 1,
           "unit_price": 200_000, "is_coated": True, "penoplast_id": ID["PK"], "recipe_id": _br}
    tana = {"project_id": pid, "order_type": "product", "loy_kg": 20.0, "recipe_id": _br, "master_id": mid, "items": [det]}
    r0 = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    oid = (js(r0) or {}).get("id")
    if yuk_oldin:
        _iid = ((js(r0) or {}).get("items") or [{}])[0].get("id")
        yuk(oid, _iid, yuk_oldin)
    t2 = dict(tana)
    t2["recipe_id"] = retsept
    t2["items"] = [dict(det, length=uzunlik, recipe_id=retsept)]
    oldin = ombor69()
    r = req(C, "put", f"/api/orders/{oid}", json=t2, params=({"confirm_shortage": "true"} if tasdiq else None))
    return r0.status_code, r, oldin, ombor69()


s0, r, o1, o2 = tahrir69(ID["R2"], 40.0)
_d = (js(r) or {}).get("detail") or {}
_sh = [str(x) for x in (_d.get("shortages") or [])]
check("E1 R1 → R2 (kam) + 4 → 40 m: 409, penoplast VA R2 xomashyosi qatorlari (asl: faqat penoplast)",
      s0 == 200 and r.status_code == 409 and any("K103 Penoplast kam" in x for x in _sh)
      and any("K103 Akril kam" in x for x in _sh), (r.status_code, _sh))
check("E2 409 — ombor o'zgarmadi", o1 == o2, (o1, o2))
s0, r, o1, o2 = tahrir69(ID["R2"], 40.0, tasdiq=True)
check("E3 tasdiq bilan — 200 (avvalgidek; foydalanuvchi ikkalasini ko'rgan)", r.status_code == 200, (r.status_code, r.text[:200]))
s0, r, o1, o2 = tahrir69(ID["REC"], 40.0)
_sh = [str(x) for x in (((js(r) or {}).get("detail") or {}).get("shortages") or [])]
check("E4 retsept o'zgarmaydi — faqat penoplast qatori (NAZORAT)", r.status_code == 409 and len(_sh) == 1
      and "K103 Penoplast kam" in _sh[0], (r.status_code, _sh))
s0, r, o1, o2 = tahrir69(ID["R3"], 40.0)
_sh = [str(x) for x in (((js(r) or {}).get("detail") or {}).get("shortages") or [])]
check("E5 R3 (xomashyo yetarli) — faqat penoplast qatori", r.status_code == 409 and len(_sh) == 1
      and "K103 Penoplast kam" in _sh[0], (r.status_code, _sh))
s0, r, o1, o2 = tahrir69(ID["R2"], 4.5, peno=100.0)
_d = (js(r) or {}).get("detail") or {}
check("E6 penoplast yetadi, R2 kam — 409 faqat loy (5-qadam, avvalgidek)", r.status_code == 409
      and all("K103 Penoplast kam" not in str(x) for x in (_d.get("shortages") or []))
      and any("K103 Akril kam" in str(x) for x in (_d.get("shortages") or [])), (r.status_code, _d))
s0, r, o1, o2 = tahrir69(ID["R2"], 40.0, bosh_retsept=ID["R2"])
_sh = [str(x) for x in (((js(r) or {}).get("detail") or {}).get("shortages") or [])]
check("E8 retsept o'zgarmaydi (R2 → R2), R2 xomashyosi manfiy — faqat penoplast qatori (almashmasa loy so'ralmaydi)",
      r.status_code == 409 and len(_sh) == 1 and "K103 Penoplast kam" in _sh[0], (r.status_code, _sh))
s0, r, o1, o2 = tahrir69(ID["R2"], 40.0, yuk_oldin=1.0)
_sh = [str(x) for x in (((js(r) or {}).get("detail") or {}).get("shortages") or [])]
check("E9 buyurtmadan qisman chiqqan (retseptni almashtirib bo'lmaydi — 5-qadam 400) — oldindan loy qatori YO'Q",
      r.status_code == 409 and len(_sh) == 1 and "K103 Penoplast kam" in _sh[0], (r.status_code, _sh))
try:
    _uf = inspect.getsource(crud.update_order_full)
except Exception:                          # noqa: BLE001
    _uf = ""
check("E7 statik: oldindan loy tekshiruvi FAQAT tasdiqsiz 409 shoxida, rollback bilan",
      tartibda(_uf, "if _all_short and not confirm_shortage:", "_tahrir_loy_oldindan(db, order, order_data", "db.rollback()",
               '"shortages": _all_short'))


# ══════════════════════════════════════════════════════════════
section("F. 59 — qaytarish yozuvi (ortiqcha / brak) bor buyurtma o'chirilsa YUMSHOQ: buyurtma, qaytarish, to'lov saqlanadi")
# ══════════════════════════════════════════════════════════════
def xomashyo():
    _s = SessionLocal()
    try:
        return {i.id: round(float(i.stock_quantity), 4) for i in _s.query(Inventory).filter(Inventory.company_id == 1)}
    finally:
        _s.close()


def baza59(oid, rid, fpid=None):
    _s = SessionLocal()
    try:
        o = _s.get(Order, oid)
        ri = _s.get(ReturnItem, rid) if rid else None
        fp = _s.get(FinishedProduct, fpid) if fpid else None
        return {"bor": o is not None, "del": bool(o.is_deleted) if o else None, "qaytarish": ri is not None,
                "tolov": _s.query(Payment).filter(Payment.order_id == oid).count(),
                "tm": (round(float(fp.quantity), 4), round(float(fp.cost_price), 2)) if fp else None}
    finally:
        _s.close()


def reja59(oid):
    return ((js(req(C, "get", f"/api/orders/{oid}")) or {}).get("ochirish") or {})


pid, mid = muhit(10.0)
s0, oid59, ids59, _ = buyurtma(pid, mid, [profil(10.0, 500_000)], 10.0)
_t = req(C, "post", "/api/payments", json={"order_id": oid59, "amount": 100_000, "payment_type": "partial",
                                           "payment_method": "naqd", "notes": nom("tolov")}).status_code
r = req(C, "post", "/api/returns", json={"order_id": oid59, "order_item_id": ids59[0] if ids59 else None, "item_name": "K59",
                                         "quantity": 3, "unit": "metr", "reason": "Ortiqcha", "refund_amount": 0,
                                         "to_stock": True})
rid59 = (js(r) or {}).get("id") if r.status_code == 200 else None
_s = SessionLocal()
try:
    _ri = _s.get(ReturnItem, rid59) if rid59 else None
    fp59 = _ri.finished_product_id if _ri else None
finally:
    _s.close()
check("F0 tayyorgarlik: buyurtma, 100 000 to'lov, 3 m ortiqcha omborga (yetkazishsiz)",
      s0 == 200 and _t == 200 and rid59 and fp59, (s0, _t, r.status_code, rid59, fp59))
_rj = reja59(oid59)
check("F1 o'chirish rejasi: yumshoq = True, qaytarish_bor = True (asl: yumshoq False)",
      _rj.get("yumshoq") is True and _rj.get("qaytarish_bor") is True, _rj)
x0 = xomashyo()
r = req(C, "delete", f"/api/orders/{oid59}")
x1 = xomashyo()
_b = baza59(oid59, rid59, fp59)
check("F2 o'chirish: 200, soft_deleted = True (asl: False — buyurtma butunlay o'chardi)",
      r.status_code == 200 and (js(r) or {}).get("soft_deleted") is True, (r.status_code, r.text[:200]))
check("F3 bazada: buyurtma «o'chirilgan» belgisi bilan, qaytarish yozuvi va 100 000 to'lov SAQLANDI; TM 3 m (21 000)",
      _b["bor"] and _b["del"] is True and _b["qaytarish"] and _b["tolov"] == 1 and _b["tm"] is not None
      and taxminan(_b["tm"][0], 3.0, 1e-6), _b)
_dx = {k: round(x1[k] - x0.get(k, 0), 4) for k in x1 if abs(x1[k] - x0.get(k, 0)) > 1e-9}
check("F4 ombor ishi o'zgarmagan: faqat QOLGAN 7 m xomashyosi qaytdi (penoplast +, kley +7 kg — loy 10 × 7/10)",
      taxminan(_dx.get(ID["KLEY"], 0), 7.0, 1e-6) and _dx.get(ID["PENO"], 0) > 0 and len(_dx) == 2, _dx)
check("F5 plan (yumshoq) = amal (soft_deleted)", _rj.get("yumshoq") == (js(r) or {}).get("soft_deleted"), (_rj, js(r)))
r = req(C, "post", f"/api/orders/{oid59}/restore")
x2 = xomashyo()
_b = baza59(oid59, rid59, fp59)
check("F6 tiklash: 200, buyurtma faol, ombor o'chirishdan OLDINGI holatga AYNAN, TM 3 m, to'lov 1",
      r.status_code == 200 and _b["del"] is False and x2 == x0 and _b["tolov"] == 1 and taxminan(_b["tm"][0], 3.0, 1e-6),
      (r.status_code, _b, {k: (x0.get(k), x2.get(k)) for k in x2 if x2.get(k) != x0.get(k)}))
r = req(C, "delete", f"/api/orders/{oid59}")
check("F7 qayta o'chirish: yana yumshoq, ombor birinchi o'chirishdagi bilan AYNAN",
      r.status_code == 200 and (js(r) or {}).get("soft_deleted") is True and xomashyo() == x1, (r.status_code, r.text[:200]))
r = req(C, "delete", f"/api/returns/{rid59}")
check("F8 o'chirilgan buyurtmaning ortiqcha qaytarishini o'chirib bo'lmaydi (kech60 himoyasi — 400)",
      r.status_code == 400 and "Avval buyurtmani tiklang" in r.text, (r.status_code, r.text[:200]))


def brak_holati():
    _s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            h = services.get_monthly_report(_s, datetime.utcnow().year, datetime.utcnow().month, company_id=1)
    finally:
        _s.close()
    st = js(req(C, "get", "/api/returns/stats")) or {}
    return h.get("brak_xarajat"), st.get("brak_month_value"), st.get("brak_month_count")


pid, mid = muhit(10.0)
s0, oidb, idsb, _ = buyurtma(pid, mid, [profil(10.0, 500_000)], 10.0)
hb0 = brak_holati()
r = req(C, "post", "/api/returns", json={"order_id": oidb, "order_item_id": idsb[0] if idsb else None, "item_name": "K59 brak",
                                         "quantity": 2, "unit": "metr", "reason": "Brak", "refund_amount": 0, "to_stock": False})
ridb = (js(r) or {}).get("id") if r.status_code == 200 else None
hb1 = brak_holati()
r = req(C, "delete", f"/api/orders/{oidb}")
hb2 = brak_holati()
_b = baza59(oidb, ridb)
check("F9 brak (yetkazishsiz) bor buyurtma o'chirilsa: yumshoq, brak yozuvi qoladi",
      s0 == 200 and ridb and r.status_code == 200 and (js(r) or {}).get("soft_deleted") is True and _b["qaytarish"], (r.text[:200], _b))
check("F10 brak xarajati hisobot bilan statistikada BIR XIL qoladi (asl: statistika 0 ga tushib, hisobot 10 000 qolardi)",
      hb1 == hb2 and hb1[0] is not None and float(hb1[0] or 0) > float(hb0[0] or 0)
      and float(hb1[1] or 0) > float(hb0[1] or 0), (hb0, hb1, hb2))
pid, mid = muhit(10.0)
s0, oidn, _, _ = buyurtma(pid, mid, [profil(10.0, 500_000)], 10.0)
req(C, "post", "/api/payments", json={"order_id": oidn, "amount": 50_000, "payment_type": "partial", "payment_method": "naqd",
                                      "notes": nom("tolov")})
_rj = reja59(oidn)
r = req(C, "delete", f"/api/orders/{oidn}")
_b = baza59(oidn, None)
check("F11 NAZORAT: qaytarishsiz / yetkazishsiz buyurtma — avvalgidek BUTUNLAY o'chadi (to'lov ham)",
      _rj.get("yumshoq") is False and _rj.get("qaytarish_bor") in (False, None) and r.status_code == 200
      and (js(r) or {}).get("soft_deleted") is False and not _b["bor"] and _b["tolov"] == 0, (_rj, r.text[:200], _b))
try:
    _ad = inspect.getsource(main.api_delete_order)
    _rp = inspect.getsource(main._buyurtma_ochirish_rejasi)
    _yq = inspect.getsource(crud.ochirishda_yumshoqmi)
except Exception:                          # noqa: BLE001
    _ad = _rp = _yq = ""
check("F12 statik: o'chirish va reja BITTA shartdan (crud.ochirishda_yumshoqmi), unda qaytarish yozuvi",
      "should_soft_delete = crud.ochirishda_yumshoqmi(order)" in _ad and "yumshoq = crud.ochirishda_yumshoqmi(order)" in _rp
      and "or bool(order.returns)" in _yq)


# ══════════════════════════════════════════════════════════════
section("G. 54 — loy rejalashtirilgan buyurtmada qoplama retsepti MAJBURIY (+ K103-6 zaxira retsept tartibi)")
# ══════════════════════════════════════════════════════════════
_s = SessionLocal()
try:
    _by = Inventory(company_id=1, item_name="K103 Boyoq", unit="kg", stock_quantity=100_000, price_per_unit=3_000,
                    category="Kimyo")
    _s.add(_by)
    _s.flush()
    _r54 = Recipe(company_id=1, name="K103 R54", batch_size_kg=100.0)
    _rl = Recipe(company_id=1, name="K103 loy sotish", batch_size_kg=100.0)
    _s.add_all([_r54, _rl])
    _s.flush()
    _s.add_all([RecipeIngredient(recipe_id=_r54.id, inventory_id=_by.id, quantity_kg=100.0),
                RecipeIngredient(recipe_id=_rl.id, inventory_id=ID["QUM"], quantity_kg=100.0)])
    _s.commit()
    ID.update(BOY=_by.id, R54=_r54.id, RL=_rl.id)
finally:
    _s.close()


def det54(**k):
    d = {"name": nom("G"), "category": "profil", "width": 20, "thickness": 10, "length": 4.0, "quantity": 1,
         "unit_price": 100_000, "is_coated": True, "penoplast_id": ID["PENO"]}
    d.update(k)
    return d


def buyurtmalar_soni(pid):
    _s = SessionLocal()
    try:
        return _s.query(Order).filter(Order.project_id == pid).count()
    finally:
        _s.close()


def yarat54(tana, **params):
    pid, mid = muhit(10.0)
    t = {"project_id": pid, "order_type": "product", "master_id": mid}
    t.update(tana)
    x0 = xomashyo()
    r = req(C, "post", "/api/orders", json=t, params=dict({"confirm_shortage": "true"}, **params))
    return r, pid, t, x0, xomashyo()


for _nomi, _tana, _par, _bolak in [
    ("G1 qoplamali, loy 10, retseptsiz", {"loy_kg": 10.0, "items": [det54()]}, {}, "Qoplama retsepti tanlanmagan"),
    ("G2 retsept 999999 (yo'q)", {"loy_kg": 10.0, "recipe_id": 999999, "items": [det54()]}, {},
     "Tanlangan qoplama retsepti (№999999) topilmadi"),
    ("G3 qoplamasiz detal, loy 10, retseptsiz", {"loy_kg": 10.0, "items": [det54(is_coated=False)]}, {},
     "Qoplama retsepti tanlanmagan"),
    ("G4 loy so'rov qatorida (?loy_kg=10), retseptsiz", {"items": [det54()]}, {"loy_kg": "10"}, "Qoplama retsepti tanlanmagan"),
    ("G5 loy sotish retsepti bor, qoplama uchun tanlanmagan", {"loy_kg": 10.0, "items": [det54(), {
        "name": nom("GL"), "category": "loy_sotish", "quantity": 5.0, "unit_price": 5_000, "is_coated": False,
        "recipe_id": ID["RL"]}]}, {}, "Qoplama retsepti tanlanmagan"),
    ("G6 qoralama ham", {"loy_kg": 10.0, "is_draft": True, "items": [det54()]}, {}, "Qoplama retsepti tanlanmagan"),
]:
    r, pid, t, x0, x1 = yarat54(_tana, **_par)
    check(f"{_nomi} — 400, sabab aytiladi, buyurtma yaratilmadi, ombor o'zgarmadi (asl: 200, loy zaxira retseptdan)",
          r.status_code == 400 and _bolak in str((js(r) or {}).get("detail")) and buyurtmalar_soni(pid) == 0 and x0 == x1,
          (r.status_code, r.text[:250], buyurtmalar_soni(pid)))
r, pid, t, x0, x1 = yarat54({"loy_kg": 0.0, "items": [det54()]})
check("G7 NAZORAT: loy 0, retseptsiz — 200 (retsept hech narsaga ta'sir qilmaydi; loy xomashyosi o'zgarmadi)",
      r.status_code == 200 and all(x0[k] == x1[k] for k in (ID["KLEY"], ID["QUM"], ID["BOY"])),
      (r.status_code, r.text[:200]))
oid_l0 = (js(r) or {}).get("id")
r, pid, t, x0, x1 = yarat54({"loy_kg": 10.0, "recipe_id": ID["R54"], "items": [det54()]})
check("G8 buyurtma retsepti R54 — 200, loy R54 dan (bo'yoq −10)", r.status_code == 200
      and taxminan(x1[ID["BOY"]] - x0[ID["BOY"]], -10.0, 1e-6), (r.status_code, r.text[:200]))
oid_r54, t_r54 = (js(r) or {}).get("id"), t
r, pid, t, x0, x1 = yarat54({"loy_kg": 10.0, "items": [det54(recipe_id=ID["R54"])]})
check("G9 faqat detal retsepti R54 — 200, loy R54 dan", r.status_code == 200
      and taxminan(x1[ID["BOY"]] - x0[ID["BOY"]], -10.0, 1e-6), (r.status_code, r.text[:200]))

# Tahrir (PUT): tanada retsept yo'q — rad, hech narsa o'zgarmaydi; retsept bilan — o'tadi
t2 = dict(t_r54)
t2.pop("recipe_id", None)
t2["items"] = [dict(t_r54["items"][0], length=5.0)]
x0 = xomashyo()
r = req(C, "put", f"/api/orders/{oid_r54}", json=t2, params={"loy_kg": "10", "confirm_shortage": "true"})
_s = SessionLocal()
try:
    _rs = [i.recipe_id for i in _s.get(Order, oid_r54).items]
    _len = [float(i.length or 0) for i in _s.get(Order, oid_r54).items]
finally:
    _s.close()
check("G10 tahrir, tanada retsept yo'q — 400 {message}, ombor / detal (4 m, R54) o'zgarmadi (asl: 200, R54 → zaxira)",
      r.status_code == 400 and "Qoplama retsepti tanlanmagan" in str(((js(r) or {}).get("detail") or {}).get("message"))
      and xomashyo() == x0 and _rs == [ID["R54"]] and _len == [4.0], (r.status_code, r.text[:200], _rs, _len))
t3 = dict(t2, recipe_id=ID["R54"])
r = req(C, "put", f"/api/orders/{oid_r54}", json=t3, params={"loy_kg": "10", "confirm_shortage": "true"})
check("G11 tahrir retsept bilan — 200 (NAZORAT)", r.status_code == 200, (r.status_code, r.text[:200]))
r = req(C, "put", f"/api/orders/{oid_r54}", json=dict(t2), params={"loy_kg": "0", "confirm_shortage": "true"})
check("G12 tahrirda loy 0 ga tushirilsa — retseptsiz ham o'tadi (loy yo'q — retsept kerak emas)", r.status_code == 200,
      (r.status_code, r.text[:200]))

# Loy rejasini o'zgartirish (PUT /loy): retseptsiz buyurtmada 0 → 10 — rad
x0 = xomashyo()
r = req(C, "put", f"/api/orders/{oid_l0}/loy", params={"loy_kg": "10"})
check("G13 PUT /loy retseptsiz buyurtmada 0 → 10 — 400, ombor o'zgarmadi (asl: zaxira retseptdan −10)",
      r.status_code == 400 and "qoplama retsepti tanlanmagan" in r.text and xomashyo() == x0, (r.status_code, r.text[:200]))

# Eski (retseptsiz) qoralama: jarayonga olish rad → tahrirda retsept tanlanadi → jarayonga olinadi
r, pid, t, x0, x1 = yarat54({"loy_kg": 10.0, "recipe_id": ID["R54"], "is_draft": True, "items": [det54()]})
oid_q = (js(r) or {}).get("id")
_s = SessionLocal()
try:
    for _i in _s.get(Order, oid_q).items:
        _i.recipe_id = None                # eski qoralama (54-banddan oldin retseptsiz saqlangan) — to'g'ridan-to'g'ri
    _s.commit()
finally:
    _s.close()
x0 = xomashyo()
r = req(C, "post", f"/api/orders/{oid_q}/activate")
_s = SessionLocal()
try:
    _st = _s.get(Order, oid_q).status.value
finally:
    _s.close()
check("G14 eski retseptsiz qoralama (loy 10) jarayonga olinmaydi — 400, 'Qoralamada … qoplama retsepti tanlanmagan', "
      "ombor o'zgarmadi, holat qoralama", r.status_code == 400 and "Qoralamada" in r.text and xomashyo() == x0 and _st == "draft",
      (r.status_code, r.text[:250], _st))
r = req(C, "put", f"/api/orders/{oid_q}", json=dict(t, recipe_id=ID["R54"], is_draft=False), params={"loy_kg": "10"})
r2 = req(C, "post", f"/api/orders/{oid_q}/activate")
x1 = xomashyo()
check("G15 tahrirda retsept tanlangach — jarayonga olindi, loy R54 dan (bo'yoq −10)",
      r.status_code == 200 and r2.status_code == 200 and taxminan(x1[ID["BOY"]] - x0[ID["BOY"]], -10.0, 1e-6),
      (r.status_code, r.text[:150], r2.status_code, r2.text[:150]))

# Eski qoralama, faqat "Loy sotish" detali (o'z retsepti bilan) va loy > 0 — jarayonga olish TO'SILMAYDI (boshi berk yo'q)
r, pid, t, x0, x1 = yarat54({"loy_kg": 5.0, "recipe_id": ID["R54"], "is_draft": True, "items": [{
    "name": nom("GL"), "category": "loy_sotish", "quantity": 5.0, "unit_price": 5_000, "is_coated": False,
    "recipe_id": ID["RL"]}]})
oid_ql = (js(r) or {}).get("id")
r2 = req(C, "post", f"/api/orders/{oid_ql}/activate") if oid_ql else None
check("G14b qoralama faqat 'Loy sotish' detali (o'z retsepti) + loy 5 — yaratildi va jarayonga olindi (saqlangan qoida: "
      "detallar retsepti)", r.status_code == 200 and r2 is not None and r2.status_code == 200,
      (r.status_code, r.text[:150], getattr(r2, "status_code", None), getattr(r2, "text", "")[:150]))

# Boshqa korxonaning retsepti — tanlov emas (korxona sharti)
from production_models import Company as _Company54   # noqa: E402
_s = SessionLocal()
try:
    if not _s.query(_Company54).filter(_Company54.id == 2).first():
        _s.add(_Company54(id=2, name="K103 Korxona B"))
        _s.commit()
    _rb = Recipe(company_id=2, name="K103 B retsept", batch_size_kg=100.0)
    _s.add(_rb)
    _s.commit()
    ID["RB"] = _rb.id
finally:
    _s.close()
r, pid, t, x0, x1 = yarat54({"loy_kg": 10.0, "recipe_id": ID["RB"], "items": [det54()]})
check("G18 boshqa korxonaning retsepti — 400 'topilmadi', buyurtma yaratilmadi, ombor o'zgarmadi",
      r.status_code == 400 and f"(№{ID['RB']}) topilmadi" in str((js(r) or {}).get("detail")) and buyurtmalar_soni(pid) == 0
      and x0 == x1, (r.status_code, r.text[:200]))

# K103-6: zaxira "birinchi retsept" — id tartibida (PG da jismoniy tartib UPDATE dan keyin o'zgaradi)
_s = SessionLocal()
try:
    _eng_kichik = _s.query(Recipe).filter(Recipe.company_id == 1).order_by(Recipe.id).first()
    _eng_kichik.name = _eng_kichik.name + " "      # UPDATE — PG da qator jismoniy joyi ko'chadi (oxirga)
    _s.commit()
    _ki = _eng_kichik.id
    _z = services.resolve_recipe(_s, company_id=1)
    _zid = _z.id if _z else None
finally:
    _s.close()
check("G16 K103-6: services.resolve_recipe zaxirasi — korxonaning ENG KICHIK id li retsepti (UPDATE dan keyin ham)",
      _zid == _ki, (_zid, _ki))
try:
    _ac = inspect.getsource(main.api_create_order)
    _uo = inspect.getsource(crud.update_order_full)
except Exception:                          # noqa: BLE001
    _ac = _uo = ""
check("G17 statik: yaratishda tekshiruv yetishmovchilik (409) dan OLDIN; tahrirda o'zgarishlardan OLDIN",
      tartibda(_ac, "crud.qoplama_retsepti_tekshir(", "check = services.check_inventory_for_order(")
      and tartibda(_uo, "if order.is_deleted:", "qoplama_retsepti_tekshir(db, order.company_id", "old_snapshot = ["))

# ══════════════════════════════════════════════════════════════
section("X. Server xatosi (5xx) yo'q")
# ══════════════════════════════════════════════════════════════
_yomon = [x for x in STATUSLAR if x[2] >= 500]
check("X1 hech bir so'rov 5xx emas", not _yomon, _yomon[:5])

# ══════════════════════════════════════════════════════════════
section("S. Statik: o'lik kod olib tashlandi (55 / 11 / 64), 25, 45")
# ══════════════════════════════════════════════════════════════
for _nomi in ("process_coating", "process_cutting", "calculate_coating_materials", "check_admin_role"):
    check(f"S1 services.{_nomi} yo'q", not hasattr(services, _nomi))
_sv = fayl("services.py")
check("S2 services.py da retsept komponenti NOMI bo'yicha korxonasiz qidiruv yo'q (process_coating shakli)",
      'Inventory.item_name.ilike(f"%{comp_name}%")' not in _sv and "CUTTING_LOSS_PERCENT" not in _sv
      and "KG_PER_SQUARE_METER" not in _sv and len(_sv) > 1000)
_bl = fayl("tools/tenant_lint_baseline.json")
check("S3 tenant lint baseline da process_coating / process_cutting yo'q", "process_coating" not in _bl
      and "process_cutting" not in _bl and len(_bl) > 100)
_o = fayl("templates/orders.html")
check("S4 orders.html da o'lik payment_warning tarmog'i yo'q (11)", "if (r.payment_warning)" not in _o
      and "r.payment_warning ? 9000" not in _o and len(_o) > 1000)
_f = fayl("templates/finished.html")
check("S5 finished.html da o'lik showProfit yo'q (64)", "showProfit(" not in _f and len(_f) > 1000)
_tq = fayl("tools/test_tayyor_qiymat.py")
check("S6 test_tayyor_qiymat: FK tinglovchisidan KEYIN engine.dispose() (25)",
      tartibda(_tq, '@event.listens_for(engine, "connect")', 'cur.execute("PRAGMA foreign_keys=ON")', "\nengine.dispose()\n"))
try:
    _co = inspect.getsource(services.complete_order)
except Exception:                          # noqa: BLE001
    _co = ""
check("S7 complete_order: usta KPI holat READY bo'lgach, yakun_foydasi × kpi_percent (45)",
      tartibda(_co, "order.status = OrderStatus.READY", "yakun_foydasi(db, order", "_pct45 / 100")
      and "* 0.03" not in _co and "total_meters * 1000" not in _co)
check("S8 complete_order: usta korxona sharti bilan", "_mq45.filter(Master.company_id == order.company_id)" in _co)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
