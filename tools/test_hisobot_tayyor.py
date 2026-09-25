#!/usr/bin/env python3
"""
test_hisobot_tayyor.py — kech76 darvozasi (2026-09-25, 97-band): hisobotlar FAQAT "Tayyor" (READY)
buyurtmani sanaydi — 91-band FOYDALANUVCHI QARORI "B" ("to'liq topshirilgan buyurtma hisobotga / usta KPI
ga FAQAT hodim «Tayyor» bosganda").

O'LCHANGAN (asl kod, `work/probe96.py` va JONLI sinov sayti, kech76): to'liq yuk bilan DELIVERED bo'lgan,
lekin "Tayyor" bosilmagan buyurtma `services.get_daily_finance_summary` (Moliya — kunlik, `/api/finance/daily`)
savdosiga kirardi (jonli: 3 / 5 660 000 -> 4 / 5 670 000), oylik hisobot va usta KPI esa uni sanamaydi. Xuddi
shu READY + DELIVERED sharti `get_top_products_report` (`/api/reports/top-products`), `get_top_customers_report`
(`/api/reports/top-customers`) va `get_top_finished_products_sold` (`/api/dashboard/top-finished-products`) da.

Bo'limlar: A — kunlik moliya (DELIVERED kirmaydi, "Tayyor" dan keyin kiradi, oylik hisobot bilan bir xil son
va summa; nazorat: "Tayyor" avto yuk, yumshoq o'chirilgan READY, yuk o'chirilgach jarayondagi); B — eng ko'p
daromad mahsulotlar / mijozlar / tayyor mahsulotdan sotilganlar (crud to'g'ridan); C — HTTP marshrutlari;
H — statik (to'rt funksiyada DELIVERED yo'q, READY sharti bor).

Ishlatish:
    python3 tools/test_hisobot_tayyor.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_hisobot_tayyor.py
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
PG_BAZA = "hisobot_tayyor_test"
_T = tempfile.mkdtemp(prefix="hisobot_tayyor_")
_DB = os.path.join(_T, "hisobot_tayyor_test.db")

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



# ══════════════════════════════════════════════════════════════
# 97-band yordamchilari
# ══════════════════════════════════════════════════════════════


def bugun():
    return datetime.utcnow().date()


def kunlik():
    """services.get_daily_finance_summary — bugungi savdo (soni, summa)."""
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            r = services.get_daily_finance_summary(s, bugun(), company_id=1)
        sav = r.get("savdo") or r.get("sales") or {}
        return (int(sav.get("orders_count") or 0), round(float(sav.get("total") or 0), 2))
    finally:
        s.close()


def top_mahsulot(nomi):
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            r = services.get_top_products_report(s, days=30, limit=500, company_id=1)
        return [x for x in r if x.get("name") == nomi]
    finally:
        s.close()


def top_mijoz():
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            r = services.get_top_customers_report(s, days=90, limit=500, company_id=1)
        x = [y for y in r if (y.get("client_name") or y.get("name")) == "TY Mijoz"]
        return round(float((x[0].get("revenue") if x else 0) or 0), 2), (int(x[0].get("orders_count") or 0) if x else 0)
    finally:
        s.close()


def top_tm(nomi):
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            r = services.get_top_finished_products_sold(s, days=30, limit=500)
        return [x for x in r if x.get("name") == nomi]
    finally:
        s.close()


def kutilgan_mijoz():
    """READY buyurtmalar (o'chirilgani ham) kelishilgan / jami summasi — hisobot bilan bir xil ta'rif."""
    s = SessionLocal()
    try:
        q = s.query(Order).filter(Order.project_id == ID["PRJ"], Order.status == OrderStatus.READY).all()
        return round(sum(float(o.agreed_amount if o.agreed_amount is not None else (o.total_amount or 0)) for o in q), 2), len(q)
    finally:
        s.close()


def detal_nomi(oid):
    s = SessionLocal()
    try:
        it = s.query(OrderItem).filter(OrderItem.order_id == oid).first()
        return it.name if it else None
    finally:
        s.close()


def delivered_buyurtma():
    oid, iid = peno_buyurtma()
    st, did = yuk(oid, iid, 10)
    return oid, iid, st, did


# ══════════════════════════════════════════════════════════════
section("A — kunlik moliya (Moliya → kunlik)")
# ══════════════════════════════════════════════════════════════
try:
    k0, h0 = kunlik(), hisobot()
    oid1, iid1, st1, did1 = delivered_buyurtma()
    h1 = holat(oid1)
    check("A0 fikstura: to'liq yuk -> DELIVERED (completed_at bor)", st1 == 200 and h1 and h1["status"] == "delivered"
          and h1["completed_at"] is not None, f"{st1} {h1}")
    k1 = kunlik()
    check("A1 DELIVERED (Tayyor bosilmagan) kunlik savdoga KIRMAYDI", k1 == k0, f"oldin {k0} keyin {k1}")
    check("A1b oylik hisobot ham o'zgarmadi (nazorat)", hisobot() == h0, f"{h0} -> {hisobot()}")
    r = tayyor(oid1)
    k2, h2 = kunlik(), hisobot()
    check("A2 \"Tayyor\" dan keyin kunlik savdoga KIRDI (+1, +500 000)", r.status_code == 200 and k2 == (k0[0] + 1, round(k0[1] + 500_000, 2)),
          f"{r.status_code} {k0} -> {k2}")
    check("A2b oylik hisobot +1 (nazorat)", h2[0] == h0[0] + 1, f"{h0} -> {h2}")
    oid3, iid3 = peno_buyurtma()
    r3 = tayyor(oid3)
    k3, h3 = kunlik(), hisobot()
    check("A3 \"Tayyor\" (avto yuk) — READY qoladi va kunlikka kiradi", r3.status_code == 200 and holat(oid3)["status"] == "ready"
          and k3 == (k2[0] + 1, round(k2[1] + 500_000, 2)), f"{r3.status_code} {holat(oid3)} {k2} -> {k3}")
    check("A4 kunlik son == oylik hisobot soni (bir xil ta'rif)", k3[0] == h3[0], f"kunlik {k3} oylik {h3}")
    check("A4b kunlik summa == oylik daromad_buyurtmalardan", taxminan(k3[1], h3[1], 0.01), f"kunlik {k3} oylik {h3}")
    rd = req(C, "delete", f"/api/orders/{oid3}")
    check("A5 yumshoq o'chirilgan READY kunlikda QOLADI (moliyaviy tarix, nazorat)",
          rd.status_code == 200 and (holat(oid3) or {}).get("del") is True and kunlik() == k3, f"{rd.status_code} {holat(oid3)} {kunlik()}")
    oid6, iid6, st6, did6 = delivered_buyurtma()
    k6a = kunlik()
    ry = yuk_ochir(did6)
    check("A6 DELIVERED yuki o'chirildi -> jarayonda, kunlik o'zgarmaydi", st6 == 200 and ry.status_code == 200
          and holat(oid6)["status"] == "in_progress" and kunlik() == k6a == k3, f"{st6} {ry.status_code} {holat(oid6)} {k6a} {kunlik()}")
except Exception as e:                                      # noqa: BLE001
    import traceback; traceback.print_exc()
    check("A QULADI", False, f"{type(e).__name__}: {e}")

# ══════════════════════════════════════════════════════════════
section("B — eng ko'p daromad: mahsulotlar / mijozlar / tayyor mahsulotdan sotilganlar")
# ══════════════════════════════════════════════════════════════
try:
    oidb, iidb, stb, didb = delivered_buyurtma()
    nb = detal_nomi(oidb)
    m0, kut0 = top_mijoz(), kutilgan_mijoz()
    check("B0 fikstura DELIVERED", stb == 200 and holat(oidb)["status"] == "delivered", f"{stb} {holat(oidb)}")
    check("B1 top mahsulotlar: DELIVERED detal YO'Q", top_mahsulot(nb) == [], str(top_mahsulot(nb)))
    check("B2 top mijozlar: summa == faqat READY buyurtmalar", m0 == kut0, f"hisobot {m0} kutilgan {kut0}")
    _s = SessionLocal()
    fp = FinishedProduct(company_id=1, name=nom("TY_TM"), quantity=100, unit="metr", unit_price=50_000, cost_price=0)
    _s.add(fp); _s.flush()
    it = _s.query(OrderItem).filter(OrderItem.order_id == oidb).first()
    it.finished_product_id = fp.id
    _s.commit(); _s.close()
    check("B3 tayyor mahsulotdan sotilganlar: DELIVERED detal YO'Q", top_tm(nb) == [], str(top_tm(nb)))
    r = tayyor(oidb)
    tm_n, mah_n = top_tm(nb), top_mahsulot(nb)
    check("B4 \"Tayyor\" dan keyin top mahsulotlarda BOR (500 000)", r.status_code == 200 and len(mah_n) == 1
          and taxminan(float(mah_n[0].get("revenue") or 0), 500_000, 0.01), f"{r.status_code} {mah_n}")
    m1, kut1 = top_mijoz(), kutilgan_mijoz()
    check("B5 top mijozlar: \"Tayyor\" dan keyin +500 000 va == READY yig'indisi", m1 == kut1 and taxminan(m1[0], m0[0] + 500_000, 0.01),
          f"{m0} -> {m1}, kutilgan {kut1}")
    check("B6 tayyor mahsulotdan sotilganlarda \"Tayyor\" dan keyin BOR", len(tm_n) == 1, str(tm_n))
except Exception as e:                                      # noqa: BLE001
    import traceback; traceback.print_exc()
    check("B QULADI", False, f"{type(e).__name__}: {e}")

# ══════════════════════════════════════════════════════════════
section("C — HTTP marshrutlari")
# ══════════════════════════════════════════════════════════════
try:
    oidc, iidc, stc, didc = delivered_buyurtma()
    nc = detal_nomi(oidc)
    _s = SessionLocal()
    fpc = FinishedProduct(company_id=1, name=nom("TY_TMC"), quantity=100, unit="metr", unit_price=50_000, cost_price=0)
    _s.add(fpc); _s.flush()
    itc = _s.query(OrderItem).filter(OrderItem.order_id == oidc).first()
    itc.finished_product_id = fpc.id
    _s.commit(); _s.close()

    def http_hammasi():
        d = js(req(C, "get", "/api/finance/daily", params={"target_date": bugun().isoformat()})) or {}
        sav = d.get("savdo") or d.get("sales") or {}
        tp = json.dumps(js(req(C, "get", "/api/reports/top-products", params={"days": 30, "limit": 500})), ensure_ascii=False, default=str)
        tf = json.dumps(js(req(C, "get", "/api/dashboard/top-finished-products", params={"days": 30, "limit": 500})), ensure_ascii=False, default=str)
        tc = js(req(C, "get", "/api/reports/top-customers", params={"days": 90, "limit": 500})) or []
        mij = [y for y in tc if isinstance(y, dict) and (y.get("client_name") or y.get("name")) == "TY Mijoz"]
        return (int(sav.get("orders_count") or 0), round(float(sav.get("total") or 0), 2)), nc in tp, nc in tf, \
            (round(float(mij[0].get("revenue") or 0), 2) if mij else 0.0)

    c0 = http_hammasi()
    check("C0 fikstura DELIVERED", stc == 200 and holat(oidc)["status"] == "delivered", f"{stc} {holat(oidc)}")
    check("C1 /api/finance/daily — DELIVERED kirmaydi (== crud kunlik)", c0[0] == kunlik(), f"{c0[0]} {kunlik()}")
    check("C2 /api/reports/top-products — DELIVERED detal yo'q", c0[1] is False, str(c0))
    check("C3 /api/dashboard/top-finished-products — DELIVERED detal yo'q", c0[2] is False, str(c0))
    check("C4 /api/reports/top-customers — faqat READY summasi", taxminan(c0[3], kutilgan_mijoz()[0], 0.01), f"{c0[3]} {kutilgan_mijoz()}")
    r = tayyor(oidc)
    c1 = http_hammasi()
    check("C5 \"Tayyor\" dan keyin to'rttasida ham BOR", r.status_code == 200 and c1[0] == (c0[0][0] + 1, round(c0[0][1] + 500_000, 2))
          and c1[1] is True and c1[2] is True and taxminan(c1[3], c0[3] + 500_000, 0.01), f"{r.status_code} {c0} -> {c1}")
except Exception as e:                                      # noqa: BLE001
    import traceback; traceback.print_exc()
    check("C QULADI", False, f"{type(e).__name__}: {e}")

# ══════════════════════════════════════════════════════════════
section("H — statik")
# ══════════════════════════════════════════════════════════════
for _fn in ("get_daily_finance_summary", "get_top_products_report", "get_top_customers_report", "get_top_finished_products_sold"):
    _src = manba(services, _fn)
    check(f"H {_fn}: DELIVERED sharti yo'q, READY sharti bor", bool(_src) and "OrderStatus.DELIVERED" not in _src
          and "Order.status == OrderStatus.READY" in _src, _fn)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(0 if FAIL == 0 else 1)
