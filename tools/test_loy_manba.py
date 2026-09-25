#!/usr/bin/env python3
"""
test_loy_manba.py — kech82 darvozasi (2026-09-26, 102-band, FOYDALANUVCHI QARORI "A"): buyurtmaning
ishlatilmagan LOYI OLINGAN joyiga qaytadi — tayyor loy zaxirasidan olingani zaxiraga, xom ingredientlardan
olingani xomga; tiklash o'chirishning AYNAN teskarisi.

O'LCHANGAN (asl kod = zip 77 `e06abe6`, `work/probe102.py`, SQLite = PG 16 AYNAN, 103 dan 20 yiqilish; JONLI —
buyurtma 218, "Tayyor loy (Oq marmar)"): buyurtma loyni `deduct_loy_ingredients(use_stock=True)` bilan AVVAL
"Tayyor loy (<retsept>)" zaxirasidan olardi, `return_loy_ingredients` esa DOIM xom ingredientlarga qaytarardi —
o'chirish, "Loy sotish", qisman "Tayyor" dagi ortgan loy, loy rejasini kamaytirish, qoplama retseptini
almashtirish. Zaxiradan 10 kg olgan buyurtmani o'chirish -> tiklash -> o'chirish: zaxira -20, kley +20 (hech qachon
sotib olinmagan xomashyo). Eski buyurtmani tiklash o'chirish xomga qaytargan loyni ZAXIRADAN yechardi.

TUZATISH: `Order.loy_manba_json` (retsept bo'yicha: "r" — ushlab turilgan loy {z: zaxiradan, x: xomdan},
"o" — o'chirish nima qilgani); `services.loy_manba_rejimi(db, "ushla" | "ochirish" | "tiklash")` — chaqiruv
qatorlari o'zgarmagan. Qaytishda avval xom qism, qolgani zaxiraga (buyurtma tayyor loyni birinchi ishlatadi).
NULL — migratsiyadan oldingi buyurtma: eski qoida (xomga), tiklash — faqat xomdan.

Bo'limlar: P — ssenariylar (har birida (Zaxira R1, Kley, Zaxira R2, Akril) o'zgarishi VA harakatlar jurnali
qoldiq o'zgarishiga teng); J — buyurtma yozuvi; N — nosozlik (ombor + yozuv bitta tranzaksiyada); C —
yordamchilar; M — migratsiya; H — statik.

Ishlatish:
    python3 tools/test_loy_manba.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_loy_manba.py
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
PG_BAZA = "loy_manba_test"
_T = tempfile.mkdtemp(prefix="loy_manba_")
_DB = os.path.join(_T, "loy_manba_test.db")

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
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime                      # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, FinishedProduct, OrderItem, Order, OrderStatus, Delivery, Payment,
    Recipe, RecipeIngredient, Master,
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


def xabar(r):
    d = js(r)
    if isinstance(d, dict):
        det = d.get("detail", d)
        if isinstance(det, dict):
            return str(det.get("message") or det)
        return str(det)
    return str(getattr(r, "text", ""))[:300]


def taxminan(a, b, eps=1e-6):
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


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TY_admin", "Parol123!", UserRole.ADMIN, "TY Admin", company_id=1)
PRJ = Project(company_id=1, client_name="TY Mijoz", project_name="TY loyiha", total_budget=0, total_paid=0)
TOSH = Inventory(company_id=1, item_name="TY Tosh", unit="kg", stock_quantity=1_000_000, price_per_unit=1_000,
                 category="Kimyo")
PENO = Inventory(company_id=1, item_name="TY Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TY Kley", unit="kg", stock_quantity=10_000, price_per_unit=2_000,
                 category="Kimyo")
_db.add_all([PRJ, TOSH, PENO, KLEY])
_db.flush()
REC = Recipe(company_id=1, name="TY retsept", batch_size_kg=100.0)
_db.add(REC)
_db.flush()
_db.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
USTA = Master(company_id=1, name="TY Usta", phone="+998900007575")
_db.add(USTA)
_db.commit()
ID = {"PRJ": PRJ.id, "TOSH": TOSH.id, "PENO": PENO.id, "KLEY": KLEY.id, "REC": REC.id, "USTA": USTA.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "TY_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "TY Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Asosiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 3}]})) or {}).get("id")
print("PT", PT, "BOM", BOM)

_n = [0]


def nom(p="TY_D"):
    _n[0] += 1
    return f"{p}{_n[0]}"


def detal_idlar(oid):
    s = SessionLocal()
    try:
        return [x[0] for x in s.query(OrderItem.id).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        s.close()


def _yarat(tana):
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    if not oid:
        return None, None
    ids = detal_idlar(oid)
    return oid, (ids[0] if ids else None)


def peno_buyurtma(draft=False):
    """Oddiy profil 10 metr (penoplast 0.1 blok), 500 000 so'm."""
    tana = {"project_id": ID["PRJ"], "order_type": "product", "is_draft": draft,
            "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 10,
                       "quantity": 10, "unit_price": 50_000, "is_coated": False, "penoplast_id": ID["PENO"]}]}
    return _yarat(tana)


def qoplamali_buyurtma(loy=10.0):
    """Qoplamali profil 10 metr + retsept (loy 10 kg) + usta."""
    tana = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": loy, "recipe_id": ID["REC"],
            "master_id": ID["USTA"],
            "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 10,
                       "quantity": 10, "unit_price": 50_000, "is_coated": True, "penoplast_id": ID["PENO"],
                       "recipe_id": ID["REC"]}]}
    return _yarat(tana)


def mrp_buyurtma(soni=5):
    tana = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": 0,
            "items": [{"name": nom(), "category": "mrp_product", "quantity": soni, "unit_price": 100_000,
                       "is_coated": False, "penoplast_id": None, "product_type_id": PT}]}
    return _yarat(tana)


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
    s = SessionLocal()
    try:
        tm = s.query(FinishedProduct.id).filter(FinishedProduct.reserved_for_order_item_id == iid) \
            .order_by(FinishedProduct.id.desc()).first()
        return tm[0] if tm else None
    finally:
        s.close()


def yuk(oid, iid, miqdor, tolov=None):
    tana = {"order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom("yuk"),
            "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"}
    if tolov:
        tana["payment_amount"] = tolov
    r = req(C, "post", "/api/deliveries", json=tana)
    d = js(r) or {}
    return r.status_code, (d.get("delivery_id") if isinstance(d, dict) else None)


def yuk_ochir(did, tolov=None):
    return req(C, "delete", f"/api/deliveries/{did}" + (f"?tolov={tolov}" if tolov else ""))


def tayyor(oid, loy=None):
    return req(C, "post", f"/api/orders/{oid}/ready", params=({"loy_kg": str(loy)} if loy is not None else None))


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if not o:
            return None
        yuklar = sorted(x[0] for x in s.query(Delivery.id).filter(Delivery.order_id == oid).all())
        tol = sorted((round(float(p.amount or 0), 2), p.delivery_id)
                     for p in s.query(Payment).filter(Payment.order_id == oid).all())
        return {"status": o.status.value if o.status else None, "yuklar": yuklar, "tolovlar": tol,
                "completed_at": o.completed_at, "pin": bool(o.is_pinned), "del": bool(o.is_deleted)}
    finally:
        s.close()


def hisobot():
    s = SessionLocal()
    try:
        n = datetime.utcnow()
        with contextlib.redirect_stdout(_quiet):
            r = services.get_monthly_report(s, n.year, n.month, company_id=1)
        return (int(r.get("buyurtmalar_soni") or 0), round(float(r.get("daromad_buyurtmalardan") or 0), 2),
                round(float(r.get("ishlab_chiqarish_xarajat") or 0), 2))
    finally:
        s.close()


def qoldiq(inv_id):
    s = SessionLocal()
    try:
        return round(float(s.get(Inventory, inv_id).stock_quantity or 0), 6)
    finally:
        s.close()


def tm_holat(fid):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid) if fid else None
        if not f:
            return None
        return (round(float(f.quantity or 0), 6), round(float(f.reserved_quantity or 0), 6),
                round(float(f.cost_price or 0), 2))
    finally:
        s.close()


def orm_yoz(oid, **kv):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        for k, v in kv.items():
            setattr(o, k, v)
        s.commit()
    finally:
        s.close()



def reja(oid):
    d = js(req(C, "get", f"/api/orders/{oid}")) or {}
    return d.get("ochirish") if isinstance(d, dict) else None


def kley():
    return qoldiq(ID["KLEY"])


def ustun(oid):
    """Order.ochirishda_loy_kg (asl kodda ustun YO'Q -> "YO'Q")."""
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        return getattr(o, "ochirishda_loy_kg", "YO'Q") if o else "BUYURTMA YO'Q"
    finally:
        s.close()


def ochir(oid, actual=None):
    return req(C, "delete", f"/api/orders/{oid}", params=({"actual_loy_kg": str(actual)} if actual is not None else None))


def tikla(oid):
    return req(C, "post", f"/api/orders/{oid}/restore")


def qisman_buyurtma(yuk_m=4):
    """Qoplamali profil 10 m (loy 10 kg) + yuk_m metr topshirilgan."""
    oid, iid = qoplamali_buyurtma(10.0)
    if oid and yuk_m:
        yuk(oid, iid, yuk_m)
    return oid, iid



# ══════════════════════════════════════════════════════════════
# 102-band: buyurtma loyi — tayyor loy zaxirasi (Z) <-> xom ingredient (Kley / Akril)
# Kutilgan qiymatlar — QAROR "A" (loy OLINGAN joyiga qaytadi; qisman qaytishda avval XOM qism,
# chunki buyurtma tayyor loyni birinchi ishlatadi). ASL kodda qaysilari yiqilishi — o'lchov.
# ══════════════════════════════════════════════════════════════
from models import InventoryMovement                # noqa: E402

AKR = Inventory(company_id=1, item_name="TY Akril", unit="kg", stock_quantity=10_000, price_per_unit=3_000,
                category="Kimyo")
_s = SessionLocal()
_s.add(AKR)
_s.flush()
REC2 = Recipe(company_id=1, name="TY retsept2", batch_size_kg=100.0)
_s.add(REC2)
_s.flush()
_s.add(RecipeIngredient(recipe_id=REC2.id, inventory_id=AKR.id, quantity_kg=100.0))
_s.commit()
ID["AKR"] = AKR.id
ID["REC2"] = REC2.id
_s.close()


def zaxira_id(rid):
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            z = services.get_or_create_loy_stock(s, s.get(Recipe, rid))
        s.commit()
        return z.id
    finally:
        s.close()


Z1 = zaxira_id(ID["REC"])
Z2 = zaxira_id(ID["REC2"])


def zqoy(inv_id, q):
    s = SessionLocal()
    try:
        s.get(Inventory, inv_id).stock_quantity = float(q)
        s.commit()
    finally:
        s.close()


def akr():
    return qoldiq(ID["AKR"])


def hol():
    """(Z1, Kley, Z2, Akril)"""
    return (qoldiq(Z1), kley(), qoldiq(Z2), akr())


def farq(a, b):
    return tuple(round(y - x, 6) for x, y in zip(a, b))


def max_harakat():
    s = SessionLocal()
    try:
        m = s.query(InventoryMovement.id).order_by(InventoryMovement.id.desc()).first()
        return m[0] if m else 0
    finally:
        s.close()


def harakat_farq(dan):
    """Harakatlar jurnali bo'yicha (Z1, Kley, Z2, Akril) sof o'zgarish (in − out), `dan` id dan keyin."""
    s = SessionLocal()
    try:
        natija = []
        for inv in (Z1, ID["KLEY"], Z2, ID["AKR"]):
            q = 0.0
            for t, m in s.query(InventoryMovement.movement_type, InventoryMovement.quantity).filter(
                    InventoryMovement.inventory_id == inv, InventoryMovement.id > dan).all():
                q += float(m or 0) * (1 if t == "in" else -1)
            natija.append(round(q, 6))
        return tuple(natija)
    finally:
        s.close()


NATIJA = {}


def olch(kalit, a, b, kutilgan, dan=None):
    f = farq(a, b)
    NATIJA[kalit] = f
    check(f"{kalit}: (Z1, Kley, Z2, Akril) o'zgarishi = {kutilgan}", f == tuple(float(x) for x in kutilgan), f)
    if dan is not None:
        hf = harakat_farq(dan)
        check(f"{kalit}: harakatlar jurnali qoldiq o'zgarishiga TENG", hf == f, (hf, f))


def loysot_buyurtma(kg, rid):
    tana = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": 0,
            "items": [{"name": nom(), "category": "loy_sotish", "quantity": kg, "unit_price": 10_000,
                       "is_coated": False, "penoplast_id": None, "recipe_id": rid}]}
    return _yarat(tana)


def qoralama_qoplamali(loy=10.0):
    tana = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": loy, "recipe_id": ID["REC"],
            "is_draft": True,
            "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 10,
                       "quantity": 10, "unit_price": 50_000, "is_coated": True, "penoplast_id": ID["PENO"],
                       "recipe_id": ID["REC"]}]}
    return _yarat(tana)


def faollashtir(oid):
    for yol in (f"/api/orders/{oid}/activate", f"/api/orders/{oid}/confirm"):
        r = req(C, "post", yol)
        if r.status_code != 404 and r.status_code != 405:
            return r
    return r


def loy_reja(oid, kg):
    return req(C, "put", f"/api/orders/{oid}/loy", params={"loy_kg": str(kg)})


def retsept_almashtir(oid, rid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        items = []
        for it in o.items:
            items.append({"name": it.name, "category": it.category, "width": it.width, "thickness": it.thickness,
                          "length": it.length, "quantity": float(it.quantity), "unit_price": float(it.unit_price),
                          "is_coated": bool(it.is_coated), "penoplast_id": it.penoplast_id,
                          "recipe_id": rid if it.is_coated else it.recipe_id})
        loy = services._get_planned_loy(o)
    finally:
        s.close()
    return req(C, "put", f"/api/orders/{oid}", json={"project_id": ID["PRJ"], "order_type": "product",
                                                    "items": items, "recipe_id": rid, "loy_kg": loy},
               params={"confirm_shortage": "true"})


def jsonsiz(oid):
    """Migratsiyadan OLDINGI (eski) buyurtma: loy manbasi yozuvi yo'q."""
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if hasattr(Order, "loy_manba_json"):
            o.loy_manba_json = None
        s.commit()
    finally:
        s.close()


def kod(r, kutilgan=200):
    check(f"  HTTP {kutilgan}", r.status_code == kutilgan, (r.status_code, xabar(r)[:300]))


# ── P1: to'liq zaxiradan, hech narsa topshirilmagan — o'chirish / tiklash ──
section("P1 zaxira 50, loy 10 (hammasi zaxiradan) — o'chirish, tiklash, qayta o'chirish")
zqoy(Z1, 50)
a = hol()
oid, _ = qoplamali_buyurtma(10.0)
b = hol()
olch("P1a yaratish", a, b, (-10, 0, 0, 0))
d = max_harakat()
r = ochir(oid)
kod(r)
c = hol()
olch("P1b o'chirish (A: zaxiraga +10, kley 0)", b, c, (10, 0, 0, 0), d)
check("P1b' yuksiz jarayondagi — QATTIQ o'chirildi (tiklash yo'q)", tikla(oid).status_code == 404)
olch("P1e yaratish + o'chirish sof", a, c, (0, 0, 0, 0))

section("P1r zaxira 50, loy 10, yuksiz READY (eski ma'lumot, yumshoq) — o'chirish, tiklash, qayta o'chirish")
zqoy(Z1, 50)
a = hol()
oid, _ = qoplamali_buyurtma(10.0)
orm_yoz(oid, status=OrderStatus.READY)
b = hol()
olch("P1ra yaratish", a, b, (-10, 0, 0, 0))
d = max_harakat()
kod(ochir(oid))
c = hol()
olch("P1rb o'chirish (A: zaxiraga +10)", b, c, (10, 0, 0, 0), d)
d = max_harakat()
kod(tikla(oid))
e = hol()
olch("P1rc tiklash (A: zaxiradan −10)", c, e, (-10, 0, 0, 0), d)
d = max_harakat()
kod(ochir(oid))
f = hol()
olch("P1rd qayta o'chirish (A: zaxiraga +10)", e, f, (10, 0, 0, 0), d)
olch("P1re butun sikl sof", a, f, (0, 0, 0, 0))

# ── P2: aralash (zaxira 4 + xom 6) — to'liq o'chirish ──
section("P2 zaxira 4, loy 10 (4 zaxira + 6 xom), yuksiz READY — o'chirish / tiklash")
zqoy(Z1, 4)
a = hol()
oid, _ = qoplamali_buyurtma(10.0)
orm_yoz(oid, status=OrderStatus.READY)
b = hol()
olch("P2a yaratish", a, b, (-4, -6, 0, 0))
d = max_harakat()
kod(ochir(oid))
c = hol()
olch("P2b o'chirish (A: zaxira +4, kley +6)", b, c, (4, 6, 0, 0), d)
d = max_harakat()
kod(tikla(oid))
e = hol()
olch("P2c tiklash (A: zaxira −4, kley −6)", c, e, (-4, -6, 0, 0), d)

# ── P3: qisman 4/10, hammasi zaxiradan ──
section("P3 zaxira 50, qisman 4/10 (loy 10 zaxiradan) — o'chirish / tiklash")
zqoy(Z1, 50)
a = hol()
oid, iid = qisman_buyurtma(4)
b = hol()
olch("P3a yaratish + yuk", a, b, (-10, 0, 0, 0))
d = max_harakat()
kod(ochir(oid))
c = hol()
olch("P3b o'chirish qisman (A: zaxira +6)", b, c, (6, 0, 0, 0), d)
d = max_harakat()
kod(tikla(oid))
e = hol()
olch("P3c tiklash (A: zaxira −6)", c, e, (-6, 0, 0, 0), d)

# ── P4: qisman 4/10, aralash (zaxira 4 + xom 6) ──
section("P4 zaxira 4, qisman 4/10 (4 zaxira + 6 xom) — o'chirish / tiklash")
zqoy(Z1, 4)
a = hol()
oid, iid = qisman_buyurtma(4)
b = hol()
olch("P4a yaratish + yuk", a, b, (-4, -6, 0, 0))
d = max_harakat()
kod(ochir(oid))
c = hol()
olch("P4b o'chirish qisman 6 (A: avval xom — kley +6, zaxira 0)", b, c, (0, 6, 0, 0), d)
d = max_harakat()
kod(tikla(oid))
e = hol()
olch("P4c tiklash (A: kley −6)", c, e, (0, -6, 0, 0), d)

# ── P5: actual_loy_kg (ishlatilgan 7 — 3 qaytadi) ──
section("P5 zaxira 50, qisman 4/10, o'chirishda haqiqiy 7 kg")
zqoy(Z1, 50)
oid, iid = qisman_buyurtma(4)
b = hol()
d = max_harakat()
kod(ochir(oid, actual=7))
c = hol()
olch("P5b o'chirish actual=7 (A: zaxira +3)", b, c, (3, 0, 0, 0), d)
d = max_harakat()
kod(tikla(oid))
e = hol()
olch("P5c tiklash (A: zaxira −3)", c, e, (-3, 0, 0, 0), d)

# ── P6: actual_loy_kg 12 (2 kg qo'shimcha yechiladi) ──
section("P6 zaxira 50, qisman 4/10, o'chirishda haqiqiy 12 kg (qo'shimcha 2)")
zqoy(Z1, 50)
oid, iid = qisman_buyurtma(4)
b = hol()
d = max_harakat()
kod(ochir(oid, actual=12))
c = hol()
olch("P6b o'chirish actual=12 (zaxiradan −2)", b, c, (-2, 0, 0, 0), d)
d = max_harakat()
kod(tikla(oid))
e = hol()
olch("P6c tiklash (A: 2 kg ZAXIRAGA qaytadi)", c, e, (2, 0, 0, 0), d)

# ── P7: tiklashda zaxira yetmaydi (oraliqda ishlatilgan) ──
section("P7 zaxira 50, loy 10 zaxiradan, yuksiz READY, o'chirish, zaxira 5 ga tushdi, tiklash")
zqoy(Z1, 50)
oid, _ = qoplamali_buyurtma(10.0)
orm_yoz(oid, status=OrderStatus.READY)
kod(ochir(oid))
zqoy(Z1, 5)
b = hol()
d = max_harakat()
kod(tikla(oid))
c = hol()
olch("P7c tiklash (zaxiradan 5, qolgan 5 xomdan)", b, c, (-5, -5, 0, 0), d)
d = max_harakat()
kod(ochir(oid))
e = hol()
olch("P7d qayta o'chirish (5 zaxiraga, 5 xomga)", c, e, (5, 5, 0, 0), d)

# ── P8: "Loy sotish" detali ──
section("P8 zaxira(R2) 50, loy sotish 10 kg R2 — o'chirish (qattiq)")
zqoy(Z2, 50)
a = hol()
oid, _ = loysot_buyurtma(10.0, ID["REC2"])
b = hol()
olch("P8a yaratish", a, b, (0, 0, -10, 0))
d = max_harakat()
kod(ochir(oid))
c = hol()
olch("P8b o'chirish (A: Z2 +10, akril 0)", b, c, (0, 0, 10, 0), d)

section("P8q zaxira(R2) 50, loy sotish 10 kg R2, 4 kg topshirilgan — o'chirish / tiklash")
zqoy(Z2, 50)
oid, iid = loysot_buyurtma(10.0, ID["REC2"])
yuk(oid, iid, 4)
b = hol()
d = max_harakat()
kod(ochir(oid))
c = hol()
olch("P8qb o'chirish qolgan 6 (A: Z2 +6)", b, c, (0, 0, 6, 0), d)
d = max_harakat()
kod(tikla(oid))
e = hol()
olch("P8qc tiklash (A: Z2 −6)", c, e, (0, 0, -6, 0), d)

# ── P9: «Tayyor» qisman (yuk bor), haqiqiy loy kam ──
section("P9 zaxira 50, qisman 4/10, «Tayyor» loy 7 (3 kg ortdi)")
zqoy(Z1, 50)
oid, iid = qisman_buyurtma(4)
b = hol()
d = max_harakat()
kod(tayyor(oid, 7))
c = hol()
olch("P9b «Tayyor» qisman (A: ortgan 3 kg zaxiraga)", b, c, (3, 0, 0, 0), d)

section("P9x zaxira 4, qisman 4/10 (4 zaxira + 6 xom), «Tayyor» loy 7")
zqoy(Z1, 4)
oid, iid = qisman_buyurtma(4)
b = hol()
d = max_harakat()
kod(tayyor(oid, 7))
c = hol()
olch("P9xb «Tayyor» qisman (A: ortgan 3 kg xomga — zaxira loyi birinchi ishlatilgan)", b, c, (0, 3, 0, 0), d)

# ── P10: loy rejasini o'zgartirish ──
section("P10 zaxira 50, loy 10 (zaxiradan) — reja 6 ga, 12 ga, o'chirish")
zqoy(Z1, 50)
oid, _ = qoplamali_buyurtma(10.0)
b = hol()
d = max_harakat()
kod(loy_reja(oid, 6))
c = hol()
olch("P10b reja 10 -> 6 (A: 4 kg zaxiraga)", b, c, (4, 0, 0, 0), d)
d = max_harakat()
kod(loy_reja(oid, 12))
e = hol()
olch("P10c reja 6 -> 12 (zaxiradan 6)", c, e, (-6, 0, 0, 0), d)
d = max_harakat()
kod(ochir(oid))
f = hol()
olch("P10d o'chirish (A: 12 zaxiraga)", e, f, (12, 0, 0, 0), d)

# ── P11: qoplama retseptini almashtirish (53-band) ──
section("P11 zaxira(R1) 50, zaxira(R2) 0, loy 10 R1 — retsept R2 ga")
zqoy(Z1, 50)
zqoy(Z2, 0)
oid, _ = qoplamali_buyurtma(10.0)
b = hol()
d = max_harakat()
r = retsept_almashtir(oid, ID["REC2"])
kod(r)
c = hol()
olch("P11b almashtirish (A: R1 loyi zaxiraga +10; R2 dan akril −10)", b, c, (10, 0, 0, -10), d)
d = max_harakat()
kod(ochir(oid))
e = hol()
olch("P11c o'chirish (A: R2 loyi akrilga +10)", c, e, (0, 0, 0, 10), d)

# ── P12: qoralama -> faollashtirish -> o'chirish ──
section("P12 zaxira 50, qoralama loy 10 — faollashtirish, o'chirish")
zqoy(Z1, 50)
oid, _ = qoralama_qoplamali(10.0)
b = hol()
r = faollashtir(oid)
kod(r)
c = hol()
olch("P12b faollashtirish (zaxiradan −10)", b, c, (-10, 0, 0, 0))
d = max_harakat()
kod(ochir(oid))
e = hol()
olch("P12c o'chirish (A: zaxiraga +10)", c, e, (10, 0, 0, 0), d)

# ── P13: ESKI buyurtma (manba yozuvi yo'q) — eski qoida: o'chirish xomga, tiklash ham xomdan ──
section("P13 ESKI buyurtma (loy_manba_json NULL), zaxira 50, loy 10 zaxiradan, yuksiz READY")
zqoy(Z1, 50)
oid, _ = qoplamali_buyurtma(10.0)
orm_yoz(oid, status=OrderStatus.READY)
jsonsiz(oid)
b = hol()
d = max_harakat()
kod(ochir(oid))
c = hol()
olch("P13b o'chirish (eski qoida: kley +10)", b, c, (0, 10, 0, 0), d)
d = max_harakat()
kod(tikla(oid))
e = hol()
olch("P13c tiklash (o'chirishning AYNAN teskarisi: kley −10, zaxira tegilmaydi)", c, e, (0, -10, 0, 0), d)

# ── P14: ESKI qoralama (manba NULL) faollashtirilsa — kuzatuv boshlanadi ──
section("P14 ESKI qoralama (NULL), zaxira 50 — faollashtirish, o'chirish")
zqoy(Z1, 50)
oid, _ = qoralama_qoplamali(10.0)
jsonsiz(oid)
kod(faollashtir(oid))
b = hol()
d = max_harakat()
kod(ochir(oid))
c = hol()
olch("P14c o'chirish (qoralamada hech narsa yechilmagan edi — A: zaxiraga +10)", b, c, (10, 0, 0, 0), d)


# ── P15: "Loy sotish" miqdorini tahrirda kamaytirish ──
def loysot_tahrir(oid, kg):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        items = []
        for it in o.items:
            items.append({"name": it.name, "category": it.category, "quantity": float(kg), "unit_price": float(it.unit_price),
                          "is_coated": False, "penoplast_id": None, "recipe_id": it.recipe_id})
    finally:
        s.close()
    return req(C, "put", f"/api/orders/{oid}", json={"project_id": ID["PRJ"], "order_type": "product", "items": items,
                                                    "loy_kg": 0},
               params={"confirm_shortage": "true"})


section("P15 zaxira(R2) 50, loy sotish 10 kg R2 — tahrirda 6 ga, keyin 9 ga, o'chirish")
zqoy(Z2, 50)
oid, _ = loysot_buyurtma(10.0, ID["REC2"])
b = hol()
d = max_harakat()
kod(loysot_tahrir(oid, 6))
c = hol()
olch("P15b loy sotish 10 -> 6 (A: Z2 +4)", b, c, (0, 0, 4, 0), d)
d = max_harakat()
kod(loysot_tahrir(oid, 9))
e = hol()
olch("P15c loy sotish 6 -> 9 (Z2 dan −3)", c, e, (0, 0, -3, 0), d)
d = max_harakat()
kod(ochir(oid))
f = hol()
olch("P15d o'chirish (A: Z2 +9)", e, f, (0, 0, 9, 0), d)

# ── P16: umumiy loy VA "Loy sotish" BIR retseptda (R1) — tiklashda o'chirish yozuvi qismlarga to'g'ri bo'linadi ──
section("P16 zaxira(R1) 10: qoplama loyi 10 (zaxiradan) + loy sotish 5 R1 (xomdan), yuksiz READY — o'chirish / tiklash")
zqoy(Z1, 10)
a = hol()
tana16 = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": 10.0, "recipe_id": ID["REC"],
          "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 10,
                     "unit_price": 50_000, "is_coated": True, "penoplast_id": ID["PENO"], "recipe_id": ID["REC"]},
                    {"name": nom(), "category": "loy_sotish", "quantity": 5, "unit_price": 10_000, "is_coated": False,
                     "penoplast_id": None, "recipe_id": ID["REC"]}]}
o16, _ = _yarat(tana16)
orm_yoz(o16, status=OrderStatus.READY)
b = hol()
olch("P16a yaratish (zaxira −10, kley −5)", a, b, (-10, -5, 0, 0))
d = max_harakat()
kod(ochir(o16))
c = hol()
olch("P16b o'chirish (A: zaxira +10, kley +5)", b, c, (10, 5, 0, 0), d)
zqoy(Z1, qoldiq(Z1) + 20)
c = hol()
d = max_harakat()
kod(tikla(o16))
e = hol()
olch("P16c tiklash (zaxiradan AYNAN 10, kley −5 — zaxirada ortiqcha 20 bo'lsa ham)", c, e, (-10, -5, 0, 0), d)

# ══════════════════════════════════════════════════════════════
section("J — buyurtmadagi loy manbasi yozuvi (Order.loy_manba_json)")
# ══════════════════════════════════════════════════════════════


def manba_yozuv(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if o is None:
            return "BUYURTMA YO'Q"
        raw = getattr(o, "loy_manba_json", "USTUN YO'Q")
        if raw in (None, "USTUN YO'Q"):
            return raw
        try:
            return json.loads(raw)
        except Exception:                  # noqa: BLE001
            return f"BUZUQ: {raw}"
    finally:
        s.close()


RK = str(ID["REC"])
zqoy(Z1, 50)
oj, _ = qoplamali_buyurtma(10.0)
orm_yoz(oj, status=OrderStatus.READY)
j1 = manba_yozuv(oj)
check("J1 yangi buyurtma: r = {retsept: z 10, x 0}", isinstance(j1, dict) and j1.get("r") == {RK: {"x": 0.0, "z": 10.0}}, j1)
ochir(oj)
j2 = manba_yozuv(oj)
check("J2 o'chirilgach: r bo'shadi (0 / 0), o = {z +10, x 0}", isinstance(j2, dict)
      and j2.get("r") == {RK: {"x": 0.0, "z": 0.0}} and j2.get("o") == {RK: {"x": 0.0, "z": 10.0}}, j2)
tikla(oj)
j3 = manba_yozuv(oj)
check("J3 tiklangach: o YO'Q, r = {z 10, x 0}", isinstance(j3, dict) and "o" not in j3
      and j3.get("r") == {RK: {"x": 0.0, "z": 10.0}}, j3)
oq, _ = qoralama_qoplamali(10.0)
j5 = manba_yozuv(oq)
check("J4 qoralama: '{\"r\": {}}' (hech narsa yechilmagan)", j5 == {"r": {}}, j5)
zqoy(Z1, 50)
oe, _ = qoplamali_buyurtma(10.0)
orm_yoz(oe, status=OrderStatus.READY)
jsonsiz(oe)
ochir(oe)
j6 = manba_yozuv(oe)
check("J5 ESKI buyurtma o'chirilgach: faqat o (xomga 10), r YO'Q (kuzatilmaydi)", isinstance(j6, dict) and "r" not in j6
      and j6.get("o") == {RK: {"x": 10.0, "z": 0.0}}, j6)
tikla(oe)
j7 = manba_yozuv(oe)
check("J6 ESKI buyurtma tiklangach: yana NULL", j7 is None, j7)

# ══════════════════════════════════════════════════════════════
section("N — nosozlik: ombor VA loy manbasi yozuvi birga qaytadi (bitta tranzaksiya)")
# ══════════════════════════════════════════════════════════════


def boz(modul, nomi):
    asl = getattr(modul, nomi, None)

    def _f(*a, **k):
        raise RuntimeError(f"NOSOZLIK({nomi})")
    setattr(modul, nomi, _f)
    return asl


def buyurtma_bayroq(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        return (bool(o.is_deleted), bool(o.stock_returned)) if o else None
    finally:
        s.close()


zqoy(Z1, 50)
on, _ = qoplamali_buyurtma(10.0)
orm_yoz(on, status=OrderStatus.READY)
a, ja, fa = hol(), manba_yozuv(on), buyurtma_bayroq(on)
_asl = boz(crud, "delete_order")
try:
    r = ochir(on)
finally:
    setattr(crud, "delete_order", _asl)
b, jb, fb = hol(), manba_yozuv(on), buyurtma_bayroq(on)
check("N1 o'chirishda nosozlik (crud.delete_order) — 500", r.status_code == 500, (r.status_code, xabar(r)))
check("N2 nosozlikdan keyin zaxira / xom / loy manbasi / bayroqlar O'ZGARMAGAN", a == b and ja == jb and fa == fb,
      (farq(a, b), ja, jb, fa, fb))
r = ochir(on)
c = hol()
check("N3 qayta urinish 200, zaxiraga BIR marta +10", r.status_code == 200 and farq(b, c) == (10.0, 0.0, 0.0, 0.0),
      (r.status_code, farq(b, c)))
a, ja = hol(), manba_yozuv(on)
_asl = boz(crud, "log_activity")
try:
    r = tikla(on)
finally:
    setattr(crud, "log_activity", _asl)
b, jb = hol(), manba_yozuv(on)
check("N4 tiklashda nosozlik (crud.log_activity) — 500", r.status_code == 500, (r.status_code, xabar(r)))
check("N5 nosozlikdan keyin zaxira / xom / loy manbasi O'ZGARMAGAN (o yozuvi saqlandi)", a == b and ja == jb,
      (farq(a, b), ja, jb))
r = tikla(on)
c = hol()
check("N6 qayta urinish 200, zaxiradan BIR marta −10", r.status_code == 200 and farq(b, c) == (-10.0, 0.0, 0.0, 0.0),
      (r.status_code, farq(b, c)))

# ══════════════════════════════════════════════════════════════
section("C — yordamchilar (rejim, yozuv, rejimsiz chaqiruvlar)")
# ══════════════════════════════════════════════════════════════
_rej = getattr(services, "loy_manba_rejimi", None)
_kal = getattr(services, "LOY_MANBA_KALIT", "_loy_manba_rejimi")
_s = SessionLocal()
try:
    if _rej is None:
        raise RuntimeError("services.loy_manba_rejimi YO'Q")
    with _rej(_s, "ushla"):
        c1a = _s.info.get(_kal)
        with _rej(_s, "tiklash"):
            c1b = _s.info.get(_kal)
        c1c = _s.info.get(_kal)
    c1d = _s.info.get(_kal, "YO'Q")
    check("C1 rejim o'rnatiladi, ichma-ich blokdan keyin tashqisi qaytadi, oxirida olib tashlanadi",
          (c1a, c1b, c1c, c1d) == ("ushla", "tiklash", "ushla", "YO'Q"), (c1a, c1b, c1c, c1d))
    try:
        with _rej(_s, "ochirish"):
            raise KeyError("sinov")
    except KeyError:
        pass
    check("C2 blok ichida istisno — rejim baribir olib tashlanadi", _s.info.get(_kal, "YO'Q") == "YO'Q", _s.info.get(_kal))
    try:
        with _rej(_s, "boshqa"):
            pass
        c3 = False
    except ValueError:
        c3 = True
    check("C3 noma'lum rejim — ValueError", c3)
except Exception as e:                     # noqa: BLE001
    check("C1-C3 yordamchi ishladi", False, f"{type(e).__name__}: {e}")
finally:
    _s.close()


class _Soxta:
    """loy_manba_json atributi yo'q soxta buyurtma (brak / tayyor mahsulot yo'llari)."""
    id = None
    order_number = "SOXTA"
    company_id = 1
    recipe_id = None
    items = []


_s = SessionLocal()
try:
    _jr = getattr(services, "_loy_manba_joriy_rejim", None)
    with (_rej(_s, "ochirish") if _rej else contextlib.nullcontext()):
        c4 = _jr(_s, _Soxta()) if _jr else "YO'Q"
    check("C4 soxta buyurtma (atributsiz) — rejim ichida ham hisobga olinmaydi (None)", c4 is None, c4)
finally:
    _s.close()

_ol = getattr(services, "loy_manba_ol", None)


class _B:
    def __init__(self, raw):
        self.loy_manba_json = raw


check("C5 buzuq yozuv ('{', '[]', 'null', '') — None", _ol is not None
      and [_ol(_B(x)) for x in ("{", "[]", "null", "", None)] == [None] * 5,
      [_ol(_B(x)) for x in ("{", "[]", "null", "", None)] if _ol else "YO'Q")

# C6 — rejimsiz chaqiruv (brak yo'li kabi) buyurtma yozuvini O'ZGARTIRMAYDI
zqoy(Z1, 50)
oc, _ = qoplamali_buyurtma(10.0)
j0 = manba_yozuv(oc)
z0 = qoldiq(Z1)
_s = SessionLocal()
try:
    _o = _s.get(Order, oc)
    with contextlib.redirect_stdout(_quiet):
        services.deduct_loy_ingredients(_s, _o, 2.0, reason_override="SINOV rejimsiz (brak kabi)")
    _s.commit()
finally:
    _s.close()
check("C6 rejimsiz yechish: zaxiradan −2 (avvalgidek), buyurtma yozuvi O'ZGARMADI",
      taxminan(qoldiq(Z1), z0 - 2) and manba_yozuv(oc) == j0, (qoldiq(Z1), z0, manba_yozuv(oc), j0))

# C7 — rejimda, hammasi zaxiradan (erta qaytish yo'li), commit=True: yozuv SHU chaqiruvda saqlanadi
_s = SessionLocal()
try:
    _o = _s.get(Order, oc)
    with (_rej(_s, "ushla") if _rej else contextlib.nullcontext()):
        with contextlib.redirect_stdout(_quiet):
            services.deduct_loy_ingredients(_s, _o, 3.0, reason_override="SINOV rejim, zaxiradan")
finally:
    _s.close()
j7 = manba_yozuv(oc)
check("C7 rejimda hammasi zaxiradan (commit=True) — yozuv boshqa sessiyada ko'rinadi: r z 10 -> 13",
      isinstance(j7, dict) and j7.get("r") == {RK: {"x": 0.0, "z": 13.0}}, j7)

# C8 — butunlay zaxiraga qaytishda xom ingredientga 0 miqdorli harakat YOZILMAYDI
_s = SessionLocal()
try:
    nol0 = _s.query(InventoryMovement).filter(InventoryMovement.quantity == 0).count()
finally:
    _s.close()
zqoy(Z1, 50)
o8, _ = qoplamali_buyurtma(10.0)
r8 = ochir(o8)
_s = SessionLocal()
try:
    nol1 = _s.query(InventoryMovement).filter(InventoryMovement.quantity == 0).count()
finally:
    _s.close()
check("C8 hammasi zaxiraga qaytganda 0 miqdorli harakat yo'q", nol1 == nol0, (nol0, nol1))
# C9 — ikkinchi to'siq (`crud.log_movement` 0 ni yozmaydi) ortida: javob jurnalida "+0.00 qaytarildi" qatorlari
# ham YO'Q (xom qism 0 bo'lsa ingredient sikli umuman ishlamaydi) — kmut82 M23 saboqi.
_j8 = (js(r8) or {}).get("inventory_log") if isinstance(js(r8), dict) else None
check("C9 hammasi zaxiraga qaytganda javob jurnalida xom ingredientga '+0.00' qatori yo'q, zaxira qatori bor",
      isinstance(_j8, list) and not any("+0.00 qaytarildi" in str(x) for x in _j8)
      and any("tayyor loy zaxirasiga qaytarildi" in str(x) for x in _j8), _j8)

# ══════════════════════════════════════════════════════════════
section("M — migratsiya")
# ══════════════════════════════════════════════════════════════
from sqlalchemy import inspect as _sa_inspect      # noqa: E402
from database import engine as _eng               # noqa: E402
_cols = [c["name"] for c in _sa_inspect(_eng).get_columns("orders")]
check("M1 orders.loy_manba_json ustuni bor", "loy_manba_json" in _cols, _cols[-6:])
try:
    with contextlib.redirect_stdout(_quiet):
        main._migrate_payment_columns()
    m2 = True
    _m2x = ""
except Exception as e:                     # noqa: BLE001
    m2 = False
    _m2x = f"{type(e).__name__}: {e}"
check("M2 migratsiya qayta ishga tushsa xato yo'q (idempotent)", m2, _m2x)

# ══════════════════════════════════════════════════════════════
section("H — statik (rejim bloklari to'g'ri joyda)")
# ══════════════════════════════════════════════════════════════
import ast as _ast                                 # noqa: E402
import textwrap as _tw                             # noqa: E402


def with_ichida(fn_src, ctx, nomlar):
    """fn_src ichida `with <ctx>:` bloklari bormi va `nomlar` dagi HAR BIR chaqiruv shu bloklardan birining
    ICHIDAmi. Natija: (bloklar_soni, ichida_yo'qlar)."""
    try:
        t = _ast.parse(_tw.dedent(fn_src))
    except Exception:                      # noqa: BLE001
        return 0, list(nomlar)
    soni = 0
    ichida = set()
    for n in _ast.walk(t):
        if isinstance(n, _ast.With) and any(_ast.unparse(w.context_expr) == ctx for w in n.items):
            soni += 1
            for b in n.body:
                for x in _ast.walk(b):
                    if isinstance(x, _ast.Call):
                        f = x.func
                        ichida.add(f.attr if isinstance(f, _ast.Attribute) else getattr(f, "id", ""))
    return soni, [q for q in nomlar if q not in ichida]


def chaqiruvlar_soni(fn_src, nom):
    try:
        t = _ast.parse(_tw.dedent(fn_src))
    except Exception:                      # noqa: BLE001
        return -1
    k = 0
    for x in _ast.walk(t):
        if isinstance(x, _ast.Call):
            f = x.func
            if (f.attr if isinstance(f, _ast.Attribute) else getattr(f, "id", "")) == nom:
                k += 1
    return k


_ad = manba(main, "api_delete_order")
_n, _yoq = with_ichida(_ad, "services.loy_manba_rejimi(db, 'ochirish')", ("return_loy_ingredients", "deduct_loy_ingredients"))
check(f"H1 api_delete_order: loy qaytarish / qo'shimcha yechish 'ochirish' rejimida (tashqarida: {_yoq})", _n == 1 and not _yoq,
      (_n, _yoq))
check("H2 api_delete_order: o'chirish yozuvi qaytarishdan OLDIN yangidan boshlanadi",
      tartibda(_ad, "if can_return and not order.stock_returned:", "services.loy_manba_ochirish_boshla(order)",
               "services.return_inventory_for_order", "services.loy_manba_rejimi(db, \"ochirish\")"))
_ro = manba(crud, "restore_order")
_n, _yoq = with_ichida(_ro, "services.loy_manba_rejimi(db, 'tiklash')", ("return_loy_ingredients", "deduct_loy_ingredients"))
check(f"H3 restore_order: loy qayta yechish / qaytarish 'tiklash' rejimida (tashqarida: {_yoq})",
      _n == 1 and not _yoq and chaqiruvlar_soni(_ro, "deduct_loy_ingredients") == 3, (_n, _yoq))
check("H4 restore_order: o'chirish yozuvi tiklashdan KEYIN tozalanadi",
      tartibda(_ro, "services.loy_manba_rejimi(db, \"tiklash\")", "db_order.ochirishda_loy_kg = None",
               "services.loy_manba_ochirish_tozala(db_order)", "db_order.is_deleted = False"))
_co = manba(crud, "create_order")
_n, _yoq = with_ichida(_co, "_services.loy_manba_rejimi(db, 'ushla')", ("deduct_loy_ingredients",))
check(f"H5 create_order: yangi buyurtma yozuvi va loy yechish 'ushla' rejimida (tashqarida: {_yoq})",
      _n == 1 and not _yoq and "db_order.loy_manba_json = _services.LOY_MANBA_BOSH" in _co
      and chaqiruvlar_soni(_co, "deduct_loy_ingredients") == 2, (_n, _yoq))
_ac = manba(crud, "activate_draft_order")
_n, _yoq = with_ichida(_ac, "services.loy_manba_rejimi(db, 'ushla')", ("deduct_loy_ingredients",))
check(f"H6 activate_draft_order: yozuv (NULL bo'lsa) + loy yechish 'ushla' rejimida (tashqarida: {_yoq})",
      _n == 1 and not _yoq and tartibda(_ac, "order.loy_manba_json = services.LOY_MANBA_BOSH",
                                        "services.deduct_inventory_for_order("), (_n, _yoq))
_uf = manba(crud, "update_order_full")
_n, _yoq = with_ichida(_uf, "services.loy_manba_rejimi(db, 'ushla')", ("return_loy_ingredients", "deduct_loy_ingredients"))
check(f"H7 update_order_full: retsept almashtirish va 'Loy sotish' farqi 'ushla' rejimida (2 blok; tashqarida: {_yoq})",
      _n == 2 and not _yoq and chaqiruvlar_soni(_uf, "deduct_loy_ingredients") == 2
      and chaqiruvlar_soni(_uf, "return_loy_ingredients") == 2, (_n, _yoq))
_cp = manba(services, "complete_order")
_n, _yoq = with_ichida(_cp, "loy_manba_rejimi(db, 'ushla')", ("return_loy_ingredients",))
check(f"H8 complete_order: qisman yakunlashda ortgan loy qaytishi 'ushla' rejimida (tashqarida: {_yoq})",
      _n == 1 and not _yoq and chaqiruvlar_soni(_cp, "return_loy_ingredients") == 1, (_n, _yoq))
_al = manba(services, "adjust_loy_diff")
_n, _yoq = with_ichida(_al, "loy_manba_rejimi(db, 'ushla')", ("return_loy_ingredients", "deduct_loy_ingredients"))
check(f"H9 adjust_loy_diff: ikkala yo'nalish 'ushla' rejimida (tashqarida: {_yoq})", _n == 1 and not _yoq, (_n, _yoq))
check("H10 migratsiya va model ustuni",
      "ALTER TABLE orders ADD COLUMN loy_manba_json TEXT" in manba(main, "_migrate_payment_columns")
      and hasattr(Order, "loy_manba_json"))

print("\nO'LCHOV:", json.dumps(NATIJA, ensure_ascii=False))
print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(0 if FAIL == 0 else 1)
