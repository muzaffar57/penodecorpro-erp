#!/usr/bin/env python3
"""
test_mrp_bosh_tannarx.py — kech101 darvozasi (2026-09-27, 138-band): MRP detali tannarxi — BO'SHAGAN dona ikki marta emas.

O'LCHANGAN (asl kod = zip 94, `work/probe138.py`, SQLite = PG AYNAN): MRP detali (10 dona, BOM 3 kg qum × 1 000) ishlab
chiqarilib 4 tasi topshirilgach buyurtma yakunlansa (qisman «Tayyor» / o'chirish — K100-3a: qolgan 6 dona band dan ERKIN
omborga), buyurtma tannarxi ishlab chiqarishning BUTUN `total_cost` i (30 000) qolardi, erkin 6 dona sotilganda yana 18 000:
oylik hisobotda 30 000 lik ishlab chiqarish uchun 48 000 xarajat. Ikki ishlab chiqarish (4 × 3 000 + 6 × 6 000) — 84 000
(to'g'risi 48 000). "Ortiqcha" (topshirilmagan) qaytarish bilan erkin qilingan dona ham xuddi shunday.

YECHIM: `services._mrp_detal_tannarxi` — har ishlab chiqarish (Q, T) uchun SHU buyurtma ishlatgani (yuk xatidagi manba TM
`mrp_olingan` + hali band) × T / Q; hech narsa bo'shamagan bo'lsa (detal miqdori ≥ ishlab chiqarilgan) — AYNAN asl qoida.

Bo'limlar:
  A — stsenariylar: buyurtma tannarxi va oylik hisobot (buyurtmalar xarajati + TM sotuvi tannarxi) = ishlab chiqarish xarajati.
  B — o'zgarmagan holatlar (to'liq topshirilgan, jarayondagi, faqat topshirilgani ishlab chiqarilgan, tiyinli narx) — AYNAN
      Σ total_cost (yaxlitlash siljishi yo'q), qo'shimcha SQL so'rov YO'Q.
  C — eski ma'lumot: manbasi yozilmagan yuk xati — asl qoida; bo'shatilmagan (qotib qolgan) band — to'liq.
  D — Loyihalar sahifasi / usta KPI / kunlik — buyurtma foydasi bilan izchil.
  X — 5xx yo'q.   S — statik.

Ishlatish:
    python3 tools/test_mrp_bosh_tannarx.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_bosh_tannarx.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_bosh_tannarx_test"
_T = tempfile.mkdtemp(prefix="mrp_bosh_tannarx_")
_DB = os.path.join(_T, "mrp_bosh_tannarx_test.db")

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
    import crud                                    # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, OrderItem, Order, Master, FinishedProduct, DeliveryItem,
)
from production_models import ProductionOrder      # noqa: E402
from sqlalchemy import event                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

crud.PUL_TAKROR_SONIYA = 0

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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:600]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


XATOLAR_5XX = []


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    if r.status_code >= 500:
        XATOLAR_5XX.append((metod, url, r.status_code, str(getattr(r, "text", ""))[:200]))
    return r


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
    auth.create_user(_db, "MB_admin", "Parol123!", UserRole.ADMIN, "MB Admin", company_id=1)
QUM = Inventory(company_id=1, item_name="MB Qum", unit="kg", stock_quantity=1_000_000, price_per_unit=1_000,
                category="Kimyo")
_db.add(QUM)
_db.commit()
QUM_ID = QUM.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "MB_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom(p="MB"):
    _n[0] += 1
    return f"{p}{_n[0]}"


PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "MB Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Asosiy", "batch_quantity": 1,
    "items": [{"inventory_id": QUM_ID, "quantity": 3}]})) or {}).get("id")


def qum_narx(narx):
    s = SessionLocal()
    try:
        s.get(Inventory, QUM_ID).price_per_unit = narx
        s.commit()
    finally:
        s.close()


def ishlab(oid, iid, miqdor):
    r = req(C, "post", "/api/production/orders", json={
        "product_type_id": PT, "bom_id": BOM, "quantity": miqdor, "source_type": "customer_order",
        "source_order_id": oid, "source_order_item_id": iid})
    d = js(r)
    po = ((d or {}).get("production_order") or {}).get("id") if isinstance(d, dict) else None
    if not po:
        return None
    for q in ("start", "complete"):
        if req(C, "post", f"/api/production/orders/{po}/{q}").status_code != 200:
            return None
    return po


def mrp_buyurtma(miqdor=10.0, narx=100_000):
    n = nom("M")
    s = SessionLocal()
    try:
        p = Project(company_id=1, client_name=f"{n} Mijoz", project_name=f"{n} loyiha", total_budget=0, total_paid=0)
        m = Master(company_id=1, name=f"{n} Usta", phone="+99894" + str(1_000_000 + _n[0]).zfill(7),
                   kpi_percent=10.0, is_active=True)
        s.add_all([p, m])
        s.commit()
        pid, mid = p.id, m.id
    finally:
        s.close()
    r = req(C, "post", "/api/orders", json={
        "project_id": pid, "order_type": "product", "loy_kg": 0, "master_id": mid,
        "items": [{"name": nom("D"), "category": "mrp_product", "quantity": miqdor, "unit_price": narx,
                   "is_coated": False, "penoplast_id": None, "product_type_id": PT}]}, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id")
    s = SessionLocal()
    try:
        iid = s.query(OrderItem.id).filter(OrderItem.order_id == oid).first()[0]
    finally:
        s.close()
    return oid, iid


def yuk(oid, iid, miqdor):
    return req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom("yuk"),
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"}).status_code


def qaytar(oid, iid, miqdor, sabab="Ortiqcha"):
    return req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": iid, "item_name": "x",
                                                 "quantity": miqdor, "unit": "m²", "reason": sabab,
                                                 "refund_amount": 0, "to_stock": True}).status_code


def tannarx(oid):
    s = SessionLocal()
    try:
        return round(float(services.calculate_order_profit(s, oid, company_id=1).get("tan_narxi") or 0), 2)
    finally:
        s.close()


def foyda(oid):
    s = SessionLocal()
    try:
        return round(float(services.calculate_order_profit(s, oid, company_id=1).get("foyda") or 0), 2)
    finally:
        s.close()


def hisobot():
    s = SessionLocal()
    n = datetime.utcnow()
    try:
        with contextlib.redirect_stdout(_quiet):
            rep = services.get_monthly_report(s, n.year, n.month, company_id=1)
        d = float(rep.get("fp_sales_daromad") or 0)
        f = float(rep.get("fp_sales_foyda") or 0)
        return {"x": round(float(rep.get("ishlab_chiqarish_xarajat") or 0), 2), "tm": round(d - f, 2)}
    finally:
        s.close()


def po_jami(iid):
    s = SessionLocal()
    try:
        return round(sum(float(p.total_cost or 0) for p in s.query(ProductionOrder).filter(
            ProductionOrder.source_order_item_id == iid, ProductionOrder.status == "completed").all()), 2)
    finally:
        s.close()


def erkin_sot():
    """PT turidagi BARCHA erkin TM ni sotadi — (sotilgan dona, tannarx yig'indisi hisobotdan emas)."""
    s = SessionLocal()
    try:
        fps = [(f.id, float(f.quantity or 0) - float(f.reserved_quantity or 0))
               for f in s.query(FinishedProduct).filter(FinishedProduct.product_type_id == PT).order_by(FinishedProduct.id).all()]
    finally:
        s.close()
    jami = 0.0
    for fid, erkin in fps:
        if erkin > 1e-9:
            r = req(C, "post", "/api/finished/sell", json={"finished_product_id": fid, "quantity": erkin, "unit_price": 100_000,
                                                           "buyer_name": nom("xar"), "confirm_below_cost": True})
            if r.status_code == 200:
                jami += erkin
    return round(jami, 6)


def stsenariy(ishlab_miq, yetk, amal, yukdan_oldin=None):
    """Hisobot farqi (buyurtmalar xarajati + TM sotuvi tannarxi), buyurtma tannarxi, ishlab chiqarish jami."""
    h0 = hisobot()
    oid, iid = mrp_buyurtma()
    for q in ishlab_miq:
        if isinstance(q, tuple):
            q, narx = q
            qum_narx(narx)
        ishlab(oid, iid, q)
    qum_narx(1_000)
    if yukdan_oldin:
        qaytar(oid, iid, yukdan_oldin)
    yuk(oid, iid, yetk)
    if amal == "tayyor":
        st = req(C, "post", f"/api/orders/{oid}/ready").status_code
    elif amal == "ochir":
        st = req(C, "delete", f"/api/orders/{oid}").status_code
    else:
        st = None
    tn = tannarx(oid)
    sotildi = erkin_sot()
    h1 = hisobot()
    return {"oid": oid, "iid": iid, "st": st, "tannarx": tn, "sotildi": sotildi, "ishlab": po_jami(iid),
            "hisobot": round((h1["x"] - h0["x"]) + (h1["tm"] - h0["tm"]), 2), "h_x": round(h1["x"] - h0["x"], 2)}


# ══════════════════════════════════════════════════════════════
# A — stsenariylar
# ══════════════════════════════════════════════════════════════
section("A. Bo'shagan dona — buyurtma tannarxida EMAS; hisobot jami = ishlab chiqarish xarajati")
a1 = stsenariy([10], 4, "tayyor")
check("A1 qisman «Tayyor» 4/10: buyurtma tannarxi 12 000 (4 × 3 000), erkin 6 sotildi, hisobot jami 30 000 = ishlab chiqarish",
      a1["st"] == 200 and taxminan(a1["tannarx"], 12_000) and taxminan(a1["sotildi"], 6, 1e-9)
      and taxminan(a1["hisobot"], a1["ishlab"]) and taxminan(a1["ishlab"], 30_000), a1)
a2 = stsenariy([10], 4, "ochir")
check("A2 o'chirish (yakunlash) 4/10: tannarx 12 000, hisobot jami 30 000 = ishlab chiqarish",
      a2["st"] == 200 and taxminan(a2["tannarx"], 12_000) and taxminan(a2["hisobot"], a2["ishlab"]) and taxminan(a2["ishlab"], 30_000), a2)
a3 = stsenariy([(4, 1_000), (6, 2_000)], 4, "tayyor")
check("A3 ikki ishlab chiqarish (4 × 3 000 + 6 × 6 000), 4 topshirildi (birinchisidan): tannarx 12 000, hisobot jami 48 000",
      a3["st"] == 200 and taxminan(a3["tannarx"], 12_000) and taxminan(a3["hisobot"], a3["ishlab"]) and taxminan(a3["ishlab"], 48_000), a3)
a4 = stsenariy([10], 4, "tayyor", yukdan_oldin=3)
check("A4 3 «Ortiqcha» (topshirilmagan) qaytarish, keyin 4 topshirilib «Tayyor»: tannarx 12 000, hisobot jami 30 000",
      a4["st"] == 200 and taxminan(a4["tannarx"], 12_000) and taxminan(a4["hisobot"], a4["ishlab"]) and taxminan(a4["ishlab"], 30_000), a4)
a5 = stsenariy([(6, 2_000), (4, 1_000)], 7, "tayyor")
check("A5 ikki ishlab chiqarish (6 × 6 000 + 4 × 3 000), 7 topshirildi: tannarx = yuk xatlaridagi manba bo'yicha, hisobot jami = ishlab",
      a5["st"] == 200 and taxminan(a5["hisobot"], a5["ishlab"]) and taxminan(a5["ishlab"], 48_000)
      and 21_000 - 0.01 <= a5["tannarx"] <= 45_000 + 0.01, a5)

# ══════════════════════════════════════════════════════════════
# B — o'zgarmagan holatlar
# ══════════════════════════════════════════════════════════════
section("B. Hech narsa bo'shamagan — AYNAN Σ total_cost, qo'shimcha so'rov yo'q")
b1 = stsenariy([10], 10, "tayyor")
check("B1 10 / 10 «Tayyor» — 30 000 (Σ total_cost AYNAN)", a1 and b1["tannarx"] == b1["ishlab"] == 30_000.0, b1)
b2 = stsenariy([4], 4, "tayyor")
check("B2 faqat 4 ishlab chiqarilgan, 4 topshirilib «Tayyor» — 12 000", b2["tannarx"] == b2["ishlab"] == 12_000.0, b2)
b3 = stsenariy([10], 4, None)
check("B3 jarayonda (yakunlanmagan) 4 / 10 — 30 000 (kech59 J: topshirish tannarxni kamaytirmaydi)",
      b3["tannarx"] == b3["ishlab"] == 30_000.0 and b3["sotildi"] == 0, b3)
qum_narx(1_234.57)
b4 = stsenariy([(7, 1_234.57), (3, 1_234.57)], 10, "tayyor")
qum_narx(1_000)
check("B4 tiyinli narx, ikki ishlab chiqarish, to'liq topshirilgan — tannarx AYNAN Σ total_cost (yaxlitlash siljishi yo'q)",
      b4["tannarx"] == b4["ishlab"] and b4["ishlab"] > 0, b4)
# qo'shimcha so'rov yo'q (hech narsa bo'shamagan)
_sorov = [0]


def _sanoq(conn, cursor, statement, parameters, context, executemany):
    _sorov[0] += 1


s = SessionLocal()
try:
    _o = s.get(Order, b1["oid"])
    _it = s.get(OrderItem, b1["iid"])
    _pol = s.query(ProductionOrder).filter(ProductionOrder.source_order_item_id == b1["iid"]).all()
    _f = getattr(services, "_mrp_detal_tannarxi", None)
    event.listen(engine, "before_cursor_execute", _sanoq)
    try:
        _v = _f(s, _o, _it, _pol) if _f else None
    finally:
        event.remove(engine, "before_cursor_execute", _sanoq)
finally:
    s.close()
check("B5 hech narsa bo'shamagan detal uchun yordamchi SQL so'rov YUBORMAYDI va Σ total_cost qaytaradi",
      _v == 30_000.0 and _sorov[0] == 0, (_v, _sorov[0]))

# ══════════════════════════════════════════════════════════════
# C — eski ma'lumot
# ══════════════════════════════════════════════════════════════
section("C. Eski ma'lumot — taxmin qilinmaydi")
c1 = stsenariy([10], 4, "tayyor")
s = SessionLocal()
try:
    s.execute(DeliveryItem.__table__.update().where(DeliveryItem.__table__.c.order_item_id == c1["iid"]).values(mrp_olingan=None))
    s.commit()
finally:
    s.close()
check("C1 manbasi yozilmagan (kech71 dan oldingi) yuk xati — asl qoida (30 000)", tannarx(c1["oid"]) == 30_000.0, tannarx(c1["oid"]))
oid, iid = mrp_buyurtma()
ishlab(oid, iid, 10)
yuk(oid, iid, 4)
req(C, "post", f"/api/orders/{oid}/ready")
s = SessionLocal()
try:
    _fp = s.query(FinishedProduct).filter(FinishedProduct.product_type_id == PT).order_by(FinishedProduct.id.desc()).first()
    _fp.reserved_quantity = 6.0              # kech100 dan oldingi «Tayyor» — band bo'shatilmagan (qotib qolgan)
    _fp.reserved_for_order_item_id = iid
    s.commit()
finally:
    s.close()
check("C2 bo'shatilmagan (qotib qolgan) band — to'liq (topshirilgan 4 + band 6 = 10 → 30 000)", tannarx(oid) == 30_000.0,
      tannarx(oid))

# ══════════════════════════════════════════════════════════════
# D — izchillik
# ══════════════════════════════════════════════════════════════
section("D. Boshqa ko'rsatkichlar — buyurtma foydasi bilan izchil")
d1 = stsenariy([10], 4, "tayyor")
f1 = foyda(d1["oid"])
check("D1 buyurtma foydasi = 400 000 (4 topshirilgan) − 12 000 (4 dona tannarxi) = 388 000", taxminan(f1, 388_000), f1)
s = SessionLocal()
try:
    _p = s.get(Order, d1["oid"]).project_id
finally:
    s.close()
ds = js(req(C, "get", f"/api/projects/{_p}/detail-stats")) or {}
check("D2 loyiha detali Sof foyda = buyurtma foydasi", taxminan(ds.get("total_profit"), round(f1), 0.6), (ds, f1))

# ══════════════════════════════════════════════════════════════
# X / S
# ══════════════════════════════════════════════════════════════
section("X. Server xatosi (5xx) yo'q")
check("X1 test davomida 5xx yo'q", not XATOLAR_5XX, XATOLAR_5XX[:5])

section("S. Statik")
_cp = manba(services, "calculate_order_profit")
check("S1 calculate_order_profit: MRP shoxi — _mrp_detal_tannarxi (PO ro'yxati bilan)",
      tartibda(_cp, "_po_royxat = _pq.all()", "tayyor_mahsulot_xarajat += _mrp_detal_tannarxi(db, order, item, _po_royxat)"), "")
_md = manba(services, "_mrp_detal_tannarxi")
check("S2 yordamchi: miqdor ≥ ishlab chiqarilgan — asl qoida (so'rovsiz); manbasiz yuk — asl qoida; korxona sharti; T × ishlatilgan / Q",
      tartibda(_md, "if miqdor <= 0 or float(item.quantity or 0) >= miqdor - 1e-6:", "return jami",
               "if getattr(order, 'company_id', None) is not None:\n        _dq = _dq.join(Order, Order.id == _D138.order_id).filter(Order.company_id == order.company_id)",
               "_crud138._mrp_olingan_oqi(_di)", "if _o is None:", "return jami",
               "_FP138.company_id == order.company_id",
               "_f.reserved_for_order_item_id == item.id", "_T if _ishlatilgan >= _Q - 1e-6 else _T * _ishlatilgan / _Q"), "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(0 if FAIL == 0 else 1)
