#!/usr/bin/env python3
"""
test_ochirish_loy.py — kech77 darvozasi (2026-09-25, 95-band + K77-1): qisman chiqqan buyurtmani o'chirishda
"Haqiqatda qancha loy ISHLATILGAN edi?" so'rovi va o'chirish <-> tiklash LOY simmetriyasi.

O'LCHANGAN (asl kod `53b6dba` (zip 72), `work/probe95.py`, SQLite = PG 16 AYNAN). Qoplamali profil 10 m, loy 10 kg,
4 m topshirilgan:
  * `orders.html` `deleteSelected` loy so'rovi `hasDelivery` (`o.deliveries`) ga bog'langan edi — `GET /api/orders/{id}`
    da `deliveries` YO'Q, so'rov HECH QACHON chiqmasdi (kech75 F11). Chiqqanda ham standart qiymat REJA (10) edi —
    "OK" bosilsa loy UMUMAN qaytmasdi (server taxmini 6 kg qaytaradi).
  * `crud.restore_order` loyni DOIM reja x qolgan ulush qayta yechardi ("aniq qiymat saqlanmagan") — `actual_loy_kg`
    bilan o'chirilgan buyurtma tiklansa loy qoldig'i ABADIY siljirdi: actual=10 -> -6, actual=7 -> -3, actual=12 -> -8,
    yuksiz "Tayyor" actual=3 -> -3 (K77-1).

TUZATISH: `Order.ochirishda_loy_kg` — o'chirishda HAQIQATDA qo'llangan loy (+ qaytgan, - qo'shimcha yechilgan);
tiklash AYNAN shuni teskari qiladi (NULL — eski qoida). O'chirish rejasi (`ochirish`) — `loy_reja`,
`loy_qaytadi_taxmin`, `loy_ishlatilgan_taxmin`, `loy_sorov`; UI so'rovi `loy_sorov` da, standart = taxmin,
o'zgartirilmasa / bo'sh — `actual_loy_kg` yuborilmaydi (natija AYNAN proporsional), "Bekor" — o'chirish bekor.

Bo'limlar: A — o'chirish -> tiklash loy simmetriyasi (HTTP); B — reja == amal (loy); C — UI (`deleteSelected` HAQIQIY
funksiyasi node da, HAQIQIY `GET /api/orders/{id}` javobi bilan; tanlangan DELETE keyin serverda bajariladi);
H — statik.

Ishlatish:
    python3 tools/test_ochirish_loy.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_ochirish_loy.py
"""
import os
import sys
import json
import inspect
import tempfile
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "ochirish_loy_test"
_T = tempfile.mkdtemp(prefix="ochirish_loy_")
_DB = os.path.join(_T, "ochirish_loy_test.db")

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


def sikl(lab, oid, actual, kutilgan_qaytish):
    """O'chirish (actual bilan) -> tiklash: loy qaytgani == kutilgan, tiklash AYNAN teskari, ustun."""
    k1 = kley()
    r = ochir(oid, actual)
    k2 = kley()
    u2 = ustun(oid)
    t = tikla(oid)
    k3 = kley()
    u3 = ustun(oid)
    check(f"{lab}: o'chirish 200, loy {kutilgan_qaytish:+} kg", r.status_code == 200 and taxminan(k2 - k1, kutilgan_qaytish, 1e-6),
          (r.status_code, round(k2 - k1, 6), xabar(r)))
    check(f"{lab}: ustun = qo'llangan ({kutilgan_qaytish:+})", isinstance(u2, (int, float)) and taxminan(u2, kutilgan_qaytish, 1e-6), u2)
    check(f"{lab}: tiklash AYNAN teskari (loy qoldig'i o'chirishdan oldingidek)", t.status_code == 200 and taxminan(k3, k1, 1e-6),
          (t.status_code, round(k3 - k1, 6), xabar(t)))
    check(f"{lab}: tiklashdan keyin ustun bo'sh (NULL)", u3 is None, u3)


# ══════════════════════════════════════════════════════════════
section("A. O'chirish -> tiklash: LOY simmetriyasi (K77-1)")
# ══════════════════════════════════════════════════════════════
oa, _ = qisman_buyurtma(4)
sikl("A1 qisman 4/10, actual YO'Q (taxmin)", oa, None, 6.0)
sikl("A1b o'sha buyurtma ikkinchi sikl", oa, None, 6.0)
ob, _ = qisman_buyurtma(4)
sikl("A2 qisman 4/10, actual=10 (hammasi ishlatilgan)", ob, 10, 0.0)
oc_, _ = qisman_buyurtma(4)
sikl("A3 qisman 4/10, actual=7", oc_, 7, 3.0)
od, _ = qisman_buyurtma(4)
sikl("A4 qisman 4/10, actual=12 (rejadan ko'p — farqi yechiladi)", od, 12, -2.0)
oe, _ = qoplamali_buyurtma(10.0)
orm_yoz(oe, status=OrderStatus.READY)
sikl("A5 yuksiz \"Tayyor\", actual=3 (faqat API)", oe, 3, 7.0)
of, _ = qoplamali_buyurtma(10.0)
orm_yoz(of, status=OrderStatus.READY)
sikl("A6 yuksiz \"Tayyor\", actual YO'Q", of, None, 10.0)
# A7 — eski (kech77 dan OLDIN o'chirilgan) buyurtma: ustun NULL -> tiklash eski qoida (reja x qolgan ulush)
og, _ = qisman_buyurtma(4)
k1 = kley()
r = ochir(og)
k2 = kley()
orm_yoz(og, ochirishda_loy_kg=None) if ustun(og) != "YO'Q" else None
t = tikla(og)
k3 = kley()
check("A7 eski o'chirilgan (ustun NULL): tiklash reja x qolgan ulush (6 kg) — simmetrik",
      r.status_code == 200 and t.status_code == 200 and taxminan(k2 - k1, 6.0) and taxminan(k3, k1), (round(k2 - k1, 6), round(k3 - k1, 6)))
# A8 — noto'g'ri miqdor: 400, hech narsa o'zgarmaydi
oh, _ = qisman_buyurtma(4)
k1 = kley()
r = ochir(oh, -5)
check("A8 actual=-5 -> 400, buyurtma joyida, loy o'zgarmadi, ustun bo'sh",
      r.status_code == 400 and taxminan(kley(), k1) and holat(oh) is not None and not holat(oh)["del"] and ustun(oh) in (None, "YO'Q"),
      (r.status_code, xabar(r), kley() - k1, holat(oh), ustun(oh)))
# A9 — yuksiz jarayondagi: QATTIQ o'chadi (tiklanmaydi), actual bo'yicha qaytadi
oi, _ = qoplamali_buyurtma(10.0)
k1 = kley()
r = ochir(oi, 3)
check("A9 yuksiz jarayonda actual=3: qattiq o'chdi (404), loy +7", r.status_code == 200 and holat(oi) is None and taxminan(kley() - k1, 7.0),
      (r.status_code, holat(oi), kley() - k1))

# ══════════════════════════════════════════════════════════════
section("B. O'chirish rejasi (loy) == DELETE amali (actual_loy_kg SIZ)")
# ══════════════════════════════════════════════════════════════
LK = ("loy_reja", "loy_qaytadi_taxmin", "loy_ishlatilgan_taxmin", "loy_sorov")


def b_holat(lab, oid, sorov, reja_kg, qaytadi):
    rj = reja(oid) or {}
    k1 = kley()
    r = ochir(oid)
    k2 = kley()
    check(f"{lab}: rejada loy kalitlari", all(k in rj for k in LK), rj)
    check(f"{lab}: loy_sorov={sorov}, reja={reja_kg}, qaytadi={qaytadi}",
          rj.get("loy_sorov") is sorov and taxminan(rj.get("loy_reja"), reja_kg) and taxminan(rj.get("loy_qaytadi_taxmin"), qaytadi),
          {k: rj.get(k) for k in LK})
    check(f"{lab}: ishlatilgan_taxmin + qaytadi == reja (so'rov bo'lsa)",
          (not sorov) or taxminan((rj.get("loy_ishlatilgan_taxmin") or 0) + (rj.get("loy_qaytadi_taxmin") or 0), reja_kg), rj)
    check(f"{lab}: reja == amal (qaytgan loy {qaytadi})", r.status_code == 200 and taxminan(k2 - k1, qaytadi, 1e-6),
          (r.status_code, round(k2 - k1, 6)))


o1, _ = qisman_buyurtma(4)
b_holat("B1 qisman 4/10", o1, True, 10.0, 6.0)
o2, _ = qoplamali_buyurtma(10.0)
b_holat("B2 hech narsa topshirilmagan (jarayonda)", o2, False, 10.0, 10.0)
o3, _ = qoplamali_buyurtma(10.0)
orm_yoz(o3, status=OrderStatus.READY)
b_holat("B3 yuksiz \"Tayyor\"", o3, False, 10.0, 10.0)
o4, i4 = qoplamali_buyurtma(10.0)
yuk(o4, i4, 10)
b_holat("B4 to'liq yetkazilgan (delivered) — loy qaytmaydi", o4, False, 10.0, 0.0)
o5, _ = qoplamali_buyurtma(0.0)
yuk(o5, detal_idlar(o5)[0], 4)
b_holat("B5 qisman, loy rejasi 0 — so'rov YO'Q", o5, False, 0.0, 0.0)
# B6 — aralash: qoplamali profil (topshirilmagan) + qoplamasiz profil (to'liq topshirilgan) -> loy ulushi 1.0
_t6 = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": 10.0, "recipe_id": ID["REC"],
       "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 10,
                  "unit_price": 50_000, "is_coated": True, "penoplast_id": ID["PENO"], "recipe_id": ID["REC"]},
                 {"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 10,
                  "unit_price": 50_000, "is_coated": False, "penoplast_id": ID["PENO"]}]}
o6, _ = _yarat(_t6)
_d6 = detal_idlar(o6) if o6 else []
if len(_d6) == 2:
    yuk(o6, _d6[1], 10)
b_holat("B6 aralash: faqat qoplamasiz detal topshirilgan — loy HAMMASI qaytadi, ishlatilgan 0", o6, True, 10.0, 10.0)
# B7 — qoralama: hech narsa yechilmagan
o7, _ = _yarat({"project_id": ID["PRJ"], "order_type": "product", "is_draft": True, "loy_kg": 10.0, "recipe_id": ID["REC"],
                "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 10,
                           "unit_price": 50_000, "is_coated": True, "penoplast_id": ID["PENO"], "recipe_id": ID["REC"]}]})
_r7 = reja(o7) or {}
check("B7 qoralama: loy_sorov false, qaytadi 0", _r7.get("loy_sorov") is False and taxminan(_r7.get("loy_qaytadi_taxmin"), 0.0),
      {k: _r7.get(k) for k in LK})
req(C, "delete", f"/api/orders/{o7}")

# ══════════════════════════════════════════════════════════════
section("C. UI — deleteSelected (HAQIQIY funksiya, HAQIQIY GET /api/orders/{id} javobi)")
# ══════════════════════════════════════════════════════════════
_html = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_b = _html.find("async function deleteSelected() {")
_e = _html.find("\n}\n", _b)
FUNK = _html[_b:_e + 2] if _b >= 0 and _e > _b else ""
check("C0 deleteSelected topildi (Jinja belgisiz)", FUNK and "{{" not in FUNK and "{%" not in FUNK, len(FUNK))

NODE_UI = r"""
const fs = require("fs"); const vm = require("vm");
const inp = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = {prompt: [], confirm: [], del: [], msg: []};
const ctx = {
  selectedOrderId: inp.oid, console, Math, Number, String, JSON, isNaN, parseFloat, encodeURIComponent, Promise,
  setTimeout: () => 0, location: {reload: () => {}},
  document: {getElementById: () => null},
  escapeHtml: (x) => String(x), formatNum: (x) => String(x), showMsg: (m, t) => out.msg.push(String(m) + "|" + t),
  showConfirmModal: async (m) => { out.confirm.push(String(m)); return true; },
  showPromptModal: async (m, d, o) => { out.prompt.push({m: String(m), d: String(d), t: (o || {}).type || ""}); return inp.javob; },
  fetch: async (url, opt) => {
    if (opt && opt.method === "DELETE") { out.del.push(String(url)); return {ok: true, json: async () => ({status: "ok", inventory_log: []})}; }
    if (String(url) === "/api/orders/" + inp.oid) return {ok: true, json: async () => inp.buyurtma};
    return {ok: false, json: async () => ({})};
  },
};
vm.createContext(ctx);
try {
  vm.runInContext(inp.funk + "\n;globalThis.__f = deleteSelected;", ctx);
  ctx.__f().then(() => { console.log("NATIJA_JSON " + JSON.stringify(out)); })
           .catch((e) => { out.istisno = String(e); console.log("NATIJA_JSON " + JSON.stringify(out)); });
} catch (e) { out.istisno = String(e); console.log("NATIJA_JSON " + JSON.stringify(out)); }
"""
_nf = os.path.join(_T, "ui77.js")
open(_nf, "w", encoding="utf-8").write(NODE_UI)


def ui(oid, javob):
    """deleteSelected ni node da yurgizadi: HAQIQIY GET javobi, so'rovga `javob`. -> natija dict."""
    bj = js(req(C, "get", f"/api/orders/{oid}")) or {}
    f = os.path.join(_T, f"ui77_{oid}.json")
    json.dump({"oid": oid, "javob": javob, "buyurtma": bj, "funk": FUNK}, open(f, "w", encoding="utf-8"))
    try:
        p = subprocess.run(["node", _nf, f], capture_output=True, text=True, timeout=60)
        for q in p.stdout.splitlines():
            if q.startswith("NATIJA_JSON "):
                return json.loads(q[len("NATIJA_JSON "):])
        return {"istisno": (p.stdout + p.stderr)[-400:]}
    except Exception as e:                 # noqa: BLE001
        return {"istisno": repr(e)}


def del_param(n):
    d = (n or {}).get("del") or []
    if len(d) != 1:
        return None
    u = d[0]
    return u.split("?", 1)[1] if "?" in u else ""


def serverda(oid, n):
    """UI tanlagan DELETE ni serverda bajaradi -> qaytgan loy (kg)."""
    q = del_param(n)
    if q is None:
        return None
    k1 = kley()
    r = req(C, "delete", f"/api/orders/{oid}" + (("?" + q) if q else ""))
    return round(kley() - k1, 6) if r.status_code == 200 else f"HTTP {r.status_code}"


u1, _ = qisman_buyurtma(4)
n = ui(u1, "4")
_p = (n.get("prompt") or [{}])[0] if n.get("prompt") else {}
check("C1 qisman: so'rov CHIQDI (ilgari hech qachon)", len(n.get("prompt") or []) == 1, n)
check("C2 standart qiymat = taxminiy ishlatilgan (4), reja emas (10)", _p.get("d") == "4", _p)
check("C3 so'rov matni: reja 10, taxmin 4 ishlatilgan, 6 qaytadi", all(x in (_p.get("m") or "") for x in ("10 kg", "4 kg", "6 kg")), _p.get("m"))
check("C4 o'zgartirilmadi -> actual_loy_kg YUBORILMAYDI", del_param(n) == "", n.get("del"))
check("C5 ... serverda loy +6 (taxmin AYNAN)", taxminan(serverda(u1, n), 6.0), n.get("del"))
u2, _ = qisman_buyurtma(4)
n = ui(u2, "7")
check("C6 7 yozildi -> ?actual_loy_kg=7", del_param(n) == "actual_loy_kg=7", n.get("del"))
check("C7 ... serverda loy +3", taxminan(serverda(u2, n), 3.0), n.get("del"))
u3, _ = qisman_buyurtma(4)
n = ui(u3, "")
check("C8 bo'sh -> param YO'Q, serverda +6", del_param(n) == "" and taxminan(serverda(u3, n), 6.0), n.get("del"))
u4, _ = qisman_buyurtma(4)
n = ui(u4, None)
check("C9 \"Bekor\" -> DELETE YUBORILMADI (o'chirish bekor)", len(n.get("prompt") or []) == 1 and (n.get("del") or []) == [], n)
check("C9b ... buyurtma joyida", holat(u4) is not None and not holat(u4)["del"], holat(u4))
u5, _ = qisman_buyurtma(4)
n = ui(u5, "4.0")
check("C10 \"4.0\" (taxminga teng) -> param YO'Q", del_param(n) == "", n.get("del"))
u6, _ = qoplamali_buyurtma(10.0)
n = ui(u6, "3")
check("C11 hech narsa topshirilmagan -> so'rov YO'Q, param YO'Q", (n.get("prompt") or []) == [] and del_param(n) == "", n)
check("C11b ... serverda loy +10 (hammasi)", taxminan(serverda(u6, n), 10.0), n.get("del"))
u7, _ = qisman_buyurtma(4)
n = ui(u7, "12")
check("C12 12 (rejadan ko'p) -> ?actual_loy_kg=12, serverda -2", del_param(n) == "actual_loy_kg=12" and taxminan(serverda(u7, n), -2.0), n.get("del"))
check("C13 istisno yo'q", not any("istisno" in (x or {}) for x in [n]), n.get("istisno"))

# ══════════════════════════════════════════════════════════════
section("H. Statik")
# ══════════════════════════════════════════════════════════════
_ad = manba(main, "api_delete_order")
check("H1 api_delete_order: qo'llangan loy buyurtmaga yoziladi (loy_sotish dan OLDIN)",
      tartibda(_ad, "loy_qollangan = 0.0", "loy_qollangan = diff", "loy_qollangan = diff", "loy_qollangan = float(planned_loy)",
               "loy_qollangan = proportional_loy", "order.ochirishda_loy_kg = loy_qollangan", "'loy_sotish'"))
_ro = manba(crud, "restore_order")
check("H2 restore_order: saqlangan miqdor AYNAN teskari, NULL — eski qoida, keyin tozalanadi",
      tartibda(_ro, "_qollangan = getattr(db_order, 'ochirishda_loy_kg', None)", "if _qollangan is not None:",
               "services.deduct_loy_ingredients(db, db_order, _qollangan)", "services.return_loy_ingredients(",
               "else:", "redo_loy = planned_loy * loy_remaining_fraction", "db_order.ochirishda_loy_kg = None"))
_mm = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("H3 migratsiya: orders.ochirishda_loy_kg", "ALTER TABLE orders ADD COLUMN ochirishda_loy_kg FLOAT" in _mm)
_rj = manba(main, "_buyurtma_ochirish_rejasi")
check("H4 reja: loy shoxlari api_delete_order bilan bir xil (loy_relevant_remaining_fraction, qisman)",
      tartibda(_rj, "loy_reja = services._get_planned_loy(order)", "not order.stock_returned", "elif not qisman:",
               "services.loy_relevant_remaining_fraction(order)", "\"loy_sorov\": bool(loy_shoxi and qisman)"))
check("H5 orders.html: so'rov oc.loy_sorov dan, hasDelivery o'zgaruvchisi YO'Q",
      tartibda(FUNK, "if (oc.loy_sorov) loyReja = oc;", "showConfirmModal(", "if (loyReja) {", "showPromptModal(",
               "if (actual === null) return;") and "hasDelivery = (" not in FUNK and "if (hasDelivery)" not in FUNK)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(0 if FAIL == 0 else 1)
