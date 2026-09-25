#!/usr/bin/env python3
"""
test_ochirish_atomik.py — kech81 darvozasi (2026-09-26, 99-band): buyurtmani O'CHIRISH va TIKLASH atomik —
yo hammasi saqlanadi, yo hech biri (nosozlik in'ektsiyasi bilan).

O'LCHANGAN (asl kod `5ab360f` (zip 76), `work/probe99.py`, SQLite = PG 16 AYNAN, 72 dan 22 yiqilish):
`main.api_delete_order` xomashyoni `services.return_inventory_for_order` / `return_loy_ingredients` orqali
qaytarardi va ular O'ZI commit qilardi; keyingi qadam yiqilsa (tarmoq uzilishi, 404, istisno) ombor qaytgan,
buyurtma esa o'chmagan (`stock_returned` False) qolardi — qayta o'chirish IKKINCHI marta qaytarardi
(qoplamali 10 m, loy 10 kg: penoplast +0.2 / kley +20 o'rniga +0.1 / +10; qisman 4/10: +0.12 / +12 o'rniga
+0.06 / +6). `crud.restore_order` ham shunday (yuksiz READY: −0.2 / −20 o'rniga −0.1 / −10).

TUZATISH: `crud.bitta_tranzaksiya(db)` — blok ichida `commit` -> `flush`, oxirida BITTA commit, xatoda
rollback. `api_delete_order` (qaytarish + `crud.delete_order`) va `restore_order` (qayta yechish + jurnal)
shu blok ichida.

Bo'limlar: K — nazorat (nosozliksiz deltalar); D — o'chirish nosozliklari (qadam OLDIDAN / KEYIN, 404,
jurnal); R — tiklash nosozliklari; C — yordamchi (commit -> flush, rollback, ichma-ich); H — statik.
Nosozlik: funksiya modul atributi sifatida vaqtincha almashtiriladi (RuntimeError / asl ish + RuntimeError /
False), so'rov 500 (404) qaytaradi; keyin nosozliksiz qayta urinish — jami o'zgarish BIR marta bo'lishi shart.

Ishlatish:
    python3 tools/test_ochirish_atomik.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_ochirish_atomik.py
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
PG_BAZA = "ochirish_atomik_test"
_T = tempfile.mkdtemp(prefix="ochirish_atomik_")
_DB = os.path.join(_T, "ochirish_atomik_test.db")

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
# 99-band — nosozlik in'ektsiyasi
# ══════════════════════════════════════════════════════════════
import json as _json
from models import InventoryMovement, ActivityLog   # noqa: E402

NAT = {}


def boz(modul, nomi):
    """modul.nomi ni chaqirilganda RuntimeError beradigan qiladi; asl funksiyani qaytaradi."""
    asl = getattr(modul, nomi, None)

    def _f(*a, **k):
        raise RuntimeError(f"NOSOZLIK({nomi})")
    setattr(modul, nomi, _f)
    return asl


def boz_false(modul, nomi):
    """modul.nomi chaqirilganda False qaytaradi (masalan `crud.delete_order` "topilmadi" -> 404)."""
    asl = getattr(modul, nomi, None)

    def _f(*a, **k):
        return False
    setattr(modul, nomi, _f)
    return asl


def boz_keyin(modul, nomi):
    """modul.nomi ASL ishini BAJARADI, keyin RuntimeError beradi (keyingi qadam / yakuniy commit nosozligi)."""
    asl = getattr(modul, nomi, None)

    def _f(*a, **k):
        asl(*a, **k)
        raise RuntimeError(f"NOSOZLIK_KEYIN({nomi})")
    setattr(modul, nomi, _f)
    return asl


def rasm(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        orow = None
        if o is not None:
            orow = [bool(o.is_deleted), bool(o.stock_returned), o.status.value if o.status else None,
                    getattr(o, "ochirishda_loy_kg", None)]
        harakat = s.query(InventoryMovement.id).filter(InventoryMovement.order_id == oid).count()
        jurnal = s.query(ActivityLog.id).filter(ActivityLog.entity_type == "order", ActivityLog.entity_id == oid).count()
        return {"order": orow,
                "peno": round(float(s.get(Inventory, ID["PENO"]).stock_quantity or 0), 6),
                "kley": round(float(s.get(Inventory, ID["KLEY"]).stock_quantity or 0), 6),
                "harakat": harakat, "jurnal": jurnal}
    finally:
        s.close()


def farq(a, b):
    return {"peno": round(b["peno"] - a["peno"], 6), "kley": round(b["kley"] - a["kley"], 6)}


def nosoz_sikl(lab, oid, amal, modul, nomi, kutilgan_delta, keyin=False, kod=500):
    """amal: 'ochir' | 'tikla'. Nosozlik bilan chaqiradi, keyin nosozliksiz qayta.
    keyin=True — asl funksiya ishlaydi, so'ng xato; keyin="false" — funksiya False qaytaradi (404)."""
    oldin = rasm(oid)
    asl = (boz_false if keyin == "false" else boz_keyin if keyin else boz)(modul, nomi)
    try:
        r = ochir(oid) if amal == "ochir" else tikla(oid)
    finally:
        setattr(modul, nomi, asl)
    xato = rasm(oid)
    r2 = ochir(oid) if amal == "ochir" else tikla(oid)
    qayta = rasm(oid)
    d_xato = farq(oldin, xato)
    d_qayta = farq(oldin, qayta)
    NAT[lab] = {"nosozlik": f"{modul.__name__}.{nomi}", "amal": amal, "kod1": r.status_code, "kod2": r2.status_code,
                "oldin": oldin, "xato": xato, "qayta": qayta, "d_xato": d_xato, "d_qayta": d_qayta,
                "kutilgan_delta": kutilgan_delta}
    check(f"{lab}: nosozlikda {kod} (kod {r.status_code})", r.status_code == kod, xabar(r))
    check(f"{lab}: nosozlikdan keyin ombor O'ZGARMAGAN (d={d_xato})",
          taxminan(d_xato["peno"], 0) and taxminan(d_xato["kley"], 0), d_xato)
    check(f"{lab}: nosozlikdan keyin buyurtma holati O'ZGARMAGAN ({oldin['order']} -> {xato['order']})",
          oldin["order"] == xato["order"], xato["order"])
    check(f"{lab}: nosozlikdan keyin ombor harakati / faoliyat jurnali YOZILMAGAN "
          f"({oldin['harakat']}/{oldin['jurnal']} -> {xato['harakat']}/{xato['jurnal']})",
          oldin["harakat"] == xato["harakat"] and oldin["jurnal"] == xato["jurnal"], xato)
    check(f"{lab}: qayta urinish 200 (kod {r2.status_code})", r2.status_code == 200, xabar(r2))
    check(f"{lab}: qayta urinishdan keyin jami o'zgarish = BIR marta (d={d_qayta}, kutilgan {kutilgan_delta})",
          taxminan(d_qayta["peno"], kutilgan_delta["peno"]) and taxminan(d_qayta["kley"], kutilgan_delta["kley"]),
          d_qayta)


# ── Nazorat: nosozliksiz o'chirish / tiklash deltalari ──
section("K — nazorat (nosozliksiz)")
k1, _ = peno_buyurtma()
a = rasm(k1); r = ochir(k1); b = rasm(k1)
DK1 = farq(a, b)
check(f"K1 oddiy profil o'chirish 200, delta {DK1}", r.status_code == 200 and b["order"] is None, xabar(r))
k2, _ = qoplamali_buyurtma(10.0)
a = rasm(k2); r = ochir(k2); b = rasm(k2)
DK2 = farq(a, b)
check(f"K2 qoplamali o'chirish 200, delta {DK2}", r.status_code == 200 and b["order"] is None, xabar(r))
k3, _ = qisman_buyurtma(4)
a = rasm(k3); r = ochir(k3); b = rasm(k3)
DK3 = farq(a, b)
check(f"K3 qisman (4/10) o'chirish 200 yumshoq, delta {DK3}", r.status_code == 200 and b["order"] and b["order"][0], xabar(r))
r = tikla(k3); c = rasm(k3)
DK3T = farq(b, c)
check(f"K3T qisman tiklash 200, delta {DK3T} (= -{DK3})", r.status_code == 200 and taxminan(DK3T["peno"], -DK3["peno"])
      and taxminan(DK3T["kley"], -DK3["kley"]), c)
k4, _ = qoplamali_buyurtma(10.0)
orm_yoz(k4, status=OrderStatus.READY)
a = rasm(k4); r = ochir(k4); b = rasm(k4)
DK4 = farq(a, b)
check(f"K4 yuksiz READY (eski ma'lumot) o'chirish 200 yumshoq, TO'LIQ qaytdi, delta {DK4}",
      r.status_code == 200 and b["order"] and b["order"][0] and DK4["peno"] > 0 and DK4["kley"] > 0, xabar(r))
r = tikla(k4); c = rasm(k4)
DK4T = farq(b, c)
check(f"K4T yuksiz READY tiklash 200, delta {DK4T}", r.status_code == 200 and taxminan(DK4T["peno"], -DK4["peno"])
      and taxminan(DK4T["kley"], -DK4["kley"]), c)
k5, _ = qoplamali_buyurtma(10.0)
rt = tayyor(k5, 10.0)
a = rasm(k5); r = ochir(k5); b = rasm(k5)
DK5 = farq(a, b)
check(f"K5 Tayyor (avto yuk — to'liq topshirilgan) o'chirish 200, ombor ishi YO'Q, delta {DK5} (tayyor {rt.status_code})",
      r.status_code == 200 and b["order"] and b["order"][0] and taxminan(DK5["peno"], 0) and taxminan(DK5["kley"], 0),
      xabar(r))

# ── D: o'chirish ──
section("D — o'chirish, nosozlik in'ektsiyasi")
o, _ = peno_buyurtma()
nosoz_sikl("D1 profil, qattiq, oxirgi qadam (_loyiha_tolangan_yangila)", o, "ochir", crud, "_loyiha_tolangan_yangila", DK1)
o, _ = qoplamali_buyurtma(10.0)
nosoz_sikl("D2 qoplamali, qattiq, oxirgi qadam (_loyiha_tolangan_yangila)", o, "ochir", crud, "_loyiha_tolangan_yangila", DK2)
o, _ = qoplamali_buyurtma(10.0)
nosoz_sikl("D3 qoplamali, o'rta qadam (return_loy_ingredients)", o, "ochir", services, "return_loy_ingredients", DK2)
o, _ = qoplamali_buyurtma(10.0)
nosoz_sikl("D4 qoplamali, TM qaytarish qadami (_return_finished_for_order)", o, "ochir", crud, "_return_finished_for_order", DK2)
o, _ = qisman_buyurtma(4)
nosoz_sikl("D5 qisman, yumshoq (_auto_release_mrp_reservations)", o, "ochir", crud, "_auto_release_mrp_reservations", DK3)
o, _ = qoplamali_buyurtma(10.0)
orm_yoz(o, status=OrderStatus.READY)
nosoz_sikl("D6 yuksiz READY, yumshoq (_auto_release_mrp_reservations)", o, "ochir", crud, "_auto_release_mrp_reservations", DK4)
o, _ = qoplamali_buyurtma(10.0)
nosoz_sikl("D7 qoplamali, loy qaytgandan KEYIN (return_loy_ingredients ishlab, so'ng xato)", o, "ochir", services,
           "return_loy_ingredients", DK2, keyin=True)
o, _ = qoplamali_buyurtma(10.0)
tayyor(o, 10.0)
nosoz_sikl("D8 Tayyor (to'liq topshirilgan), yumshoq — ombor ishi yo'q (nazorat)", o, "ochir", crud,
           "_auto_release_mrp_reservations", DK5)
o, _ = qoplamali_buyurtma(10.0)
nosoz_sikl("D9 qoplamali, delete_order 'topilmadi' (404 — tranzaksiya ichida)", o, "ochir", crud, "delete_order", DK2,
           keyin="false", kod=404)
o, _ = qoplamali_buyurtma(10.0)
nosoz_sikl("D10 qoplamali, qattiq, faoliyat jurnali yiqildi (log_activity)", o, "ochir", crud, "log_activity", DK2)
o, _ = qisman_buyurtma(4)
nosoz_sikl("D11 qisman, yumshoq, faoliyat jurnali yiqildi (log_activity)", o, "ochir", crud, "log_activity", DK3)

# ── R: tiklash ──
section("R — tiklash, nosozlik in'ektsiyasi")
o, _ = qoplamali_buyurtma(10.0)
orm_yoz(o, status=OrderStatus.READY)
ochir(o)
nosoz_sikl("R1 yuksiz READY (to'liq qaytgan), loy qadami (deduct_loy_ingredients)", o, "tikla", services,
           "deduct_loy_ingredients", DK4T)
o, _ = qoplamali_buyurtma(10.0)
orm_yoz(o, status=OrderStatus.READY)
ochir(o)
nosoz_sikl("R2 yuksiz READY (to'liq qaytgan), TM qadami (_return_finished_for_order)", o, "tikla", crud,
           "_return_finished_for_order", DK4T)
o, _ = qisman_buyurtma(4)
ochir(o)
nosoz_sikl("R3 qisman, loy qadami (deduct_loy_ingredients)", o, "tikla", services, "deduct_loy_ingredients", DK3T)
o, _ = qisman_buyurtma(4)
ochir(o)
nosoz_sikl("R4 qisman, loy yechilgandan KEYIN xato (deduct_loy_ingredients ishlab, so'ng)", o, "tikla", services,
           "deduct_loy_ingredients", DK3T, keyin=True)
o, _ = qoplamali_buyurtma(10.0)
orm_yoz(o, status=OrderStatus.READY)
ochir(o)
nosoz_sikl("R5 yuksiz READY, loy yechilgandan KEYIN xato", o, "tikla", services, "deduct_loy_ingredients", DK4T,
           keyin=True)
o, _ = qisman_buyurtma(4)
ochir(o)
nosoz_sikl("R6 qisman, faoliyat jurnali yiqildi (log_activity)", o, "tikla", crud, "log_activity", DK3T)

# ── C: yordamchi ──
section("C — crud.bitta_tranzaksiya")


def qoldiq_x(inv_id):
    try:
        return qoldiq(inv_id)
    except Exception as e:                 # noqa: BLE001
        return f"XATO {type(e).__name__}"


BT = getattr(crud, "bitta_tranzaksiya", None)
check("C1 crud.bitta_tranzaksiya bor", callable(BT))
if callable(BT):
    _s = SessionLocal()
    try:
        _q0 = qoldiq_x(ID["TOSH"])
        _inv = _s.get(Inventory, ID["TOSH"])
        _ichki = None
        try:
            with BT(_s):
                _inv.stock_quantity = float(_q0) + 5
                _s.commit()
                _ichki = ("commit" in _s.__dict__, qoldiq_x(ID["TOSH"]))
                raise RuntimeError("C_SINOV")
        except RuntimeError:
            pass
        check(f"C2 blok ichida commit — faqat flush (boshqa sessiya eski qiymatni ko'radi): {_ichki}",
              _ichki is not None and _ichki[0] and taxminan(_ichki[1], _q0), _ichki)
        check(f"C3 istisnodan keyin o'zgarish BEKOR ({qoldiq_x(ID['TOSH'])} = {_q0})", taxminan(qoldiq_x(ID["TOSH"]), _q0))
        try:
            _oz = round(float(_s.query(Inventory.stock_quantity).filter(Inventory.id == ID["TOSH"]).scalar()), 6)
        except Exception as _e:            # noqa: BLE001
            _oz = f"XATO {type(_e).__name__}"
        check(f"C3b istisnodan keyin O'SHA sessiya ham eski qiymatni ko'radi — rollback qilingan ({_oz} = {_q0})",
              taxminan(_oz, _q0), _oz)
        check("C4 istisnodan keyin sessiyaning commit i asliga qaytgan", "commit" not in _s.__dict__)
        _inv = _s.get(Inventory, ID["TOSH"])
        _ichma = None
        with BT(_s):
            _inv.stock_quantity = float(_q0) + 7
            with BT(_s):
                _inv.stock_quantity = float(_q0) + 8
            _ichma = ("commit" in _s.__dict__, qoldiq_x(ID["TOSH"]))
        check(f"C5 ichma-ich: ichki blok tugagach haqiqiy commit YO'Q, tashqi hali faol: {_ichma}",
              _ichma is not None and _ichma[0] and taxminan(_ichma[1], _q0), _ichma)
        check(f"C6 tashqi blok tugagach BITTA commit ({qoldiq_x(ID['TOSH'])} = {float(_q0) + 8})",
              taxminan(qoldiq_x(ID["TOSH"]), float(_q0) + 8))
        check("C7 tashqi blokdan keyin sessiyaning commit i asliga qaytgan", "commit" not in _s.__dict__)
        _inv = _s.get(Inventory, ID["TOSH"])
        _inv.stock_quantity = float(_q0)
        _s.commit()
        check("C8 blokdan keyin oddiy commit ishlaydi (qiymat asliga)", taxminan(qoldiq_x(ID["TOSH"]), _q0))
    finally:
        _s.close()

# ── H: statik ──
section("H — statik")
import ast as _ast           # noqa: E402
import textwrap as _tw       # noqa: E402


def with_ichida(fn_src, ctx, nomlar):
    """fn_src ichida `with <ctx>:` bloki bormi va `nomlar` dagi HAR BIR chaqiruv (atribut / nom oxiri) shu
    blok ICHIDAmi. Natija: (blok_bor, ichida_yo'qlar)."""
    try:
        t = _ast.parse(_tw.dedent(fn_src))
    except Exception:                      # noqa: BLE001
        return False, list(nomlar)
    for n in _ast.walk(t):
        if isinstance(n, _ast.With) and any(_ast.unparse(w.context_expr) == ctx for w in n.items):
            ichida = set()
            for b in n.body:
                for x in _ast.walk(b):
                    if isinstance(x, _ast.Call):
                        f = x.func
                        ichida.add(f.attr if isinstance(f, _ast.Attribute) else getattr(f, "id", ""))
            return True, [q for q in nomlar if q not in ichida]
    return False, list(nomlar)


_ad = manba(main, "api_delete_order")
_b, _yoq = with_ichida(_ad, "crud.bitta_tranzaksiya(db)",
                       ("return_inventory_for_order", "return_inventory_for_order_partial", "_return_finished_for_order",
                        "return_loy_ingredients", "deduct_loy_ingredients", "flush", "delete_order"))
check(f"H1 api_delete_order: qaytarish + delete_order BITTA `with crud.bitta_tranzaksiya(db)` ichida (tashqarida: {_yoq})",
      _b and not _yoq, (_b, _yoq))
check("H2 api_delete_order: blok xomashyo qaytarishdan OLDIN boshlanadi",
      tartibda(_ad, "with crud.bitta_tranzaksiya(db):", "if can_return and not order.stock_returned:",
               "services.return_inventory_for_order(db, order)", "crud.delete_order(db, order_id"))
_ro = manba(crud, "restore_order")
_b, _yoq = with_ichida(_ro, "bitta_tranzaksiya(db)",
                       ("return_inventory_for_order", "return_inventory_for_order_partial", "_return_finished_for_order",
                        "deduct_loy_ingredients", "return_loy_ingredients", "commit", "log_activity"))
check(f"H3 restore_order: qayta yechish + commit + jurnal BITTA `with bitta_tranzaksiya(db)` ichida (tashqarida: {_yoq})",
      _b and not _yoq, (_b, _yoq))
_bt = manba(crud, "bitta_tranzaksiya")
check("H4 bitta_tranzaksiya: commit -> flush, xatoda rollback + qayta ko'tarish, oxirida BITTA commit",
      tartibda(_bt, "db.commit = db.flush", "yield db", "except BaseException:", "_qaytar()", "db.rollback()", "raise",
               "_qaytar()", "db.commit()"))
check("H5 crud.delete_order o'zi o'zgarmagan (boshqa chaqiruvchilar uchun commit saqlanadi)",
      "db.commit()" in manba(crud, "delete_order") and "bitta_tranzaksiya" not in manba(crud, "delete_order"))

_out = os.environ.get("PROBE_OUT")
if _out:
    with open(_out, "w", encoding="utf-8") as _f:
        _json.dump(NAT, _f, ensure_ascii=False, indent=1, default=str)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for x in FAILED:
    print("  YIQILDI:", x)
sys.exit(0 if FAIL == 0 else 1)
