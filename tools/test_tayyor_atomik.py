#!/usr/bin/env python3
"""
test_tayyor_atomik.py — kech101 darvozasi (2026-09-27, 142-band + K101-1 … K101-4).

O'LCHANGAN (asl kod = zip 94, `work/probe142.py`, SQLite = PG AYNAN):
  * «Tayyor» (`services.complete_order`) oraliq `commit` lar bilan yozilgan (kech41). API (`POST /api/orders/{id}/ready`)
    uni kech84 dan beri `crud.bitta_tranzaksiya` ichida chaqiradi — istisnoli 9 nosozlik nuqtasida holat AYNAN oldingi.
    LEKIN: (1) avtomatik yuk xati istisnosiz rad etilsa (`success: False`) «Tayyor» 200 qaytarib buyurtmani YUKSIZ
    READY qilardi (oylik hisobot / usta KPI +1, qayta «Tayyor» — "allaqachon tayyor"); (2) funksiya tranzaksiyasiz
    chaqirilsa har qanday xato READY + loy yechilgan yarim holatni SAQLAB qolardi (qayta urinish rad).
  * Poyga (HAQIQIY PG): «Tayyor» qulfni oxirigacha ushlaganda o'chirish qulfdan OLDIN o'qigan holatni qulfdan keyin
    qayta o'qimasa (kmut100 N19) — READY buyurtma IKKINCHI marta "yakunlanardi" va eskirgan IN_PROGRESS surati yozilardi
    (tiklash READY buyurtmani IN_PROGRESS ga qaytarardi). Endi bu dinamik tekshiriladi (P1).
  * kech100 dan OLDIN o'chirilgan (IN_PROGRESS / DELIVERED, `stock_returned`) buyurtma ustida: «Tayyor» 200 (qisman —
    penoplast IKKINCHI marta qaytdi, hisobotga +1), to'liq tahrir 200 (Savatdagi buyurtma uchun 0.02 blok yechildi),
    yuk xatini o'chirish 200 (tiklashda topshirilgan 4 m xomashyosi IKKI marta yechildi), MRP detaliga ishlab chiqarish
    200 (mahsulot Savatdagi buyurtmaga band). Yuk xati qo'shish / detal tahriri 2026-09 auditdan beri rad etadi.

YECHIM: `complete_order` BUTUN ishi `crud.bitta_tranzaksiya` ichida (API bilan ichma-ich — bitta), yuk xati rad
etilsa `_TayyorBekor` (rollback, 400 sabab bilan); o'chirilgan buyurtma — `crud.OCHIRILGAN_BUYURTMA_XABARI`
(«Tayyor», to'liq tahrir, yuk xatini o'chirish, ishlab chiqarish yaratish / boshlash).

Bo'limlar:
  A — API: 10 nosozlik nuqtasi (istisno / jim rad) — xatodan keyin holat AYNAN oldingi; qayta urinish = NAZORAT.
  B — `services.complete_order` TRANZAKSIYASIZ — o'sha 10 nuqta: holat AYNAN oldingi; qayta urinish = NAZORAT.
  C — o'chirilgan buyurtma: «Tayyor» / tahrir / yuk xatini o'chirish / ishlab chiqarish — rad, hech narsa o'zgarmaydi;
      yangi uslub (READY) — "allaqachon tayyor"; tiklangach hammasi ishlaydi (NAZORAT bilan AYNAN).
  P — poyga (FAQAT PG): «Tayyor» ∥ o'chirish (N19), «Tayyor» ∥ «Tayyor», «Tayyor» ∥ yuk xati.
  X — kutilmagan 5xx yo'q.   S — statik.

Ishlatish:
    python3 tools/test_tayyor_atomik.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tayyor_atomik.py
"""
import os
import sys
import time
import inspect
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tayyor_atomik_test"
_T = tempfile.mkdtemp(prefix="tayyor_atomik_")
_DB = os.path.join(_T, "tayyor_atomik_test.db")

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
    import production_service                      # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, OrderItem, Order, Recipe, RecipeIngredient, Master, Delivery, User,
    FinishedProduct, StockSource, ProductionStatus, ActivityLog, InventoryMovement, Payment,
)
from fastapi.testclient import TestClient          # noqa: E402

crud.PUL_TAKROR_SONIYA = 0      # bir xil summali to'lovlar / yuklar (turli buyurtmalarda) takror deb yutilmasin

XABAR = getattr(crud, "OCHIRILGAN_BUYURTMA_XABARI", "Bu buyurtma o'chirilgan — avval uni tiklang")
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
        print(f"  ✗ {label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


XATOLAR_5XX = []
KUTILGAN_5XX = [False]


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    if r.status_code >= 500 and not KUTILGAN_5XX[0]:
        XATOLAR_5XX.append((metod, url, r.status_code, str(getattr(r, "text", ""))[:200]))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def xabar(d):
    """Javobdagi xabar matni (detail obyekt / matn / natija)."""
    if not isinstance(d, dict):
        return str(d)
    det = d.get("detail", d)
    if isinstance(det, dict):
        return str(det.get("message") or det)
    return str(det)


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
    auth.create_user(_db, "TA_admin", "Parol123!", UserRole.ADMIN, "TA Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="TA Penoplast", unit="blok", stock_quantity=100_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TA Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000,
                 category="Kimyo")
QUM = Inventory(company_id=1, item_name="TA Qum", unit="kg", stock_quantity=100_000, price_per_unit=1_000,
                category="Kimyo")
_db.add_all([PENO, KLEY, QUM])
_db.flush()
REC = Recipe(company_id=1, name="TA retsept", batch_size_kg=100.0)
RLOY = Recipe(company_id=1, name="TA loy sotish", batch_size_kg=100.0)
_db.add_all([REC, RLOY])
_db.flush()
_db.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
_db.add(RecipeIngredient(recipe_id=RLOY.id, inventory_id=QUM.id, quantity_kg=100.0))
TMP = FinishedProduct(company_id=1, name="TA TM profil", category="profil", width=20, thickness=10, is_coated=True,
                      quantity=1_000, produced_quantity=1_000, unit="metr", unit_price=0, cost_price=3_000_000,
                      source=StockSource.PRODUCED, penoplast_id=PENO.id, recipe_id=REC.id, unit_volume_m3=0.01,
                      unit_loy_kg=0.5, production_status=ProductionStatus.READY)
_db.add(TMP)
_db.commit()
ID = {"PENO": PENO.id, "KLEY": KLEY.id, "QUM": QUM.id, "REC": REC.id, "RLOY": RLOY.id, "TMP": TMP.id}
UID = _db.query(User.id).filter(User.username == "TA_admin").first()[0]
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "TA_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom(p="TA"):
    _n[0] += 1
    return f"{p}{_n[0]}"


PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "TA Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Asosiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["QUM"], "quantity": 3}]})) or {}).get("id")


def po_yarat(oid, iid, miqdor):
    r = req(C, "post", "/api/production/orders", json={
        "product_type_id": PT, "bom_id": BOM, "quantity": miqdor, "source_type": "customer_order",
        "source_order_id": oid, "source_order_item_id": iid})
    d = js(r)
    po = ((d or {}).get("production_order") or {}).get("id") if isinstance(d, dict) else None
    return r.status_code, po, d


def ishlab(oid, iid, miqdor):
    """MRP detali uchun ishlab chiqarish (yaratish + boshlash + yakunlash) — mahsulot shu detalga band."""
    st, po, _d = po_yarat(oid, iid, miqdor)
    if not po:
        return None
    for q in ("start", "complete"):
        if req(C, "post", f"/api/production/orders/{po}/{q}").status_code != 200:
            return None
    return po


def muhit():
    """Har yo'l — alohida loyiha (mijoz) va usta (KPI 10 %)."""
    n = nom("M")
    s = SessionLocal()
    try:
        p = Project(company_id=1, client_name=f"{n} Mijoz", project_name=f"{n} loyiha", total_budget=0, total_paid=0)
        m = Master(company_id=1, name=f"{n} Usta", phone="+99892" + str(1_000_000 + _n[0]).zfill(7),
                   kpi_percent=10.0, is_active=True)
        s.add_all([p, m])
        s.commit()
        return p.id, m.id, f"{n} Mijoz"
    finally:
        s.close()


def _profil(n=10.0, narx=50_000):
    return {"category": "profil", "width": 20, "thickness": 10, "length": n, "quantity": 10, "unit_price": narx,
            "is_coated": True, "penoplast_id": ID["PENO"], "recipe_id": ID["REC"]}


def _tm_profil(n=10.0, narx=40_000):
    return {"category": "profil", "width": 20, "thickness": 10, "length": n, "quantity": 1, "unit_price": narx,
            "is_coated": True, "penoplast_id": ID["PENO"], "finished_product_id": ID["TMP"]}


def _mrp(n=10.0, narx=100_000):
    return {"category": "mrp_product", "quantity": n, "unit_price": narx, "is_coated": False, "penoplast_id": None,
            "product_type_id": PT}


def _loy_sotish(kg=20.0, narx=5_000):
    return {"category": "loy_sotish", "quantity": kg, "unit_price": narx, "is_coated": False,
            "penoplast_id": None, "recipe_id": ID["RLOY"]}


# (detallar, yetkaziladi {detal indeksi: miqdor}, loy reja, MRP ishlab chiqarish miqdori)
SHAKLLAR = {
    "S1 profil 4/10": ([_profil()], {0: 4}, 10.0, None),
    "S6 loy sotish 8/20": ([_loy_sotish()], {0: 8}, 0.0, None),
    "S8 tayyor mahsulotdan 4/10": ([_tm_profil()], {0: 4}, 0.0, None),
    "S9 MRP 4/10": ([_mrp()], {0: 4}, 0.0, 10.0),
    "N0 profil 0/10": ([_profil()], {}, 10.0, None),
    "N1 profil 10/10": ([_profil()], {0: 10}, 10.0, None),
    "M4 MRP 4/10 (4 ishlab chiqarilgan)": ([_mrp()], {0: 4}, 0.0, 4.0),
}


def buyurtma(pid, mid, detallar, loy):
    items = []
    for d in detallar:
        x = dict(d)
        x["name"] = nom("D")
        items.append(x)
    tana = {"project_id": pid, "order_type": "product", "loy_kg": loy, "recipe_id": ID["REC"], "master_id": mid,
            "items": items}
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    d = js(r) or {}
    oid = d.get("id") if isinstance(d, dict) else None
    s = SessionLocal()
    try:
        ids = [x[0] for x in s.query(OrderItem.id).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        s.close()
    return oid, ids


def yuk(oid, iid, miqdor):
    r = req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom("yuk"),
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    return r.status_code


def tayyorla(shakl):
    detallar, yetkaz, loy, mrp_miq = SHAKLLAR[shakl]
    pid, mid, mijoz = muhit()
    oid, ids = buyurtma(pid, mid, detallar, loy)
    for idx, d in enumerate(detallar):
        if d.get("category") == "mrp_product" and mrp_miq:
            ishlab(oid, ids[idx], mrp_miq)
    for idx, miq in yetkaz.items():
        yuk(oid, ids[idx], miq)
    return oid, ids, mid, mijoz


def tayyor(oid, loy):
    r = req(C, "post", f"/api/orders/{oid}/ready", params=({"loy_kg": str(loy)} if loy else None))
    return r.status_code, (js(r) or {})


def ochir(oid):
    r = req(C, "delete", f"/api/orders/{oid}")
    return r.status_code, (js(r) or {})


def tiklash(oid):
    return req(C, "post", f"/api/orders/{oid}/restore").status_code


def yuk_idlari(oid):
    s = SessionLocal()
    try:
        return [d.id for d in s.query(Delivery).filter(Delivery.order_id == oid).order_by(Delivery.id).all()]
    finally:
        s.close()


def yuk_ochir(oid):
    """Buyurtmaning birinchi yuk xatini o'chirish (yuk xati bo'lmasa — 598, test qulamaydi)."""
    _yi = yuk_idlari(oid)
    if not _yi:
        return _Xato(ValueError("yuk xati yo'q"))
    return req(C, "delete", f"/api/deliveries/{_yi[0]}")


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if not o:
            return None
        return {"status": o.status.value, "del": bool(o.is_deleted), "total": round(float(o.total_amount or 0), 2),
                "agreed": (round(float(o.agreed_amount), 2) if o.agreed_amount is not None else None),
                "paid": round(float(o.paid_amount or 0), 2), "debt": round(float(o.debt_amount or 0), 2),
                "completed": bool(o.completed_at), "notes": o.notes, "actual_loy": o.actual_loy_kg,
                "stock_returned": bool(o.stock_returned), "json": bool(getattr(o, "ochirish_yopish_json", None)),
                "items": [(i.quantity, i.length, round(float(i.unit_price or 0), 2), round(float(i.total_price or 0), 2))
                          for i in o.items]}
    finally:
        s.close()


def ombor():
    s = SessionLocal()
    try:
        d = {k: round(float(s.get(Inventory, ID[k]).stock_quantity), 6) for k in ("PENO", "KLEY", "QUM")}
        d["TMP"] = round(float(s.get(FinishedProduct, ID["TMP"]).quantity or 0), 6)
        _mrp_tm = s.query(FinishedProduct).filter(FinishedProduct.product_type_id == PT).all() if PT else []
        d["MRP_TM"] = round(sum(float(f.quantity or 0) for f in _mrp_tm), 6)
        d["MRP_BAND"] = round(sum(float(f.reserved_quantity or 0) for f in _mrp_tm), 6)
        return d
    finally:
        s.close()


def ombor_farq(a, b):
    return {k: round(b[k] - a[k], 6) for k in a}


def korsatkich(mid, mijoz):
    s = SessionLocal()
    n = datetime.utcnow()
    try:
        with contextlib.redirect_stdout(_quiet):
            rep = services.get_monthly_report(s, n.year, n.month, company_id=1)
            yil = crud.get_masters_kpi_report(s, n.year, include_inactive=True, company_id=1)
        _usta = mijoz.split()[0] + " Usta"
        uy = [r for r in (yil.get("masters") or []) if r.get("name") == _usta]
        return {"rep_soni": rep.get("buyurtmalar_soni"), "rep_daromad": rep.get("daromad_buyurtmalardan"),
                "rep_xarajat": round(float(rep.get("ishlab_chiqarish_xarajat") or 0), 2),
                "rep_usta_kpi": rep.get("usta_kpi_xarajat"),
                "kpi_yil": ((uy[0].get("yearly_sales"), uy[0].get("yearly_profit"), uy[0].get("orders_count"))
                            if uy else None)}
    finally:
        s.close()


def surat(oid, mid, mijoz):
    s = SessionLocal()
    try:
        dl = s.query(Delivery).filter(Delivery.order_id == oid).all()
        yetk = round(sum(float(di.quantity or 0) for d in dl for di in d.items), 6)
        tol = s.query(Payment).filter(Payment.order_id == oid).count()
        harakat = s.query(InventoryMovement).count()
        audit = s.query(ActivityLog).count()
        po = s.query(FinishedProduct).filter(FinishedProduct.reserved_quantity > 0).count()
    finally:
        s.close()
    return {"h": holat(oid), "ombor": ombor(), "yuk_soni": len(dl), "yetk": yetk, "tolov_soni": tol,
            "harakat": harakat, "audit": audit, "band_soni": po, "k": korsatkich(mid, mijoz)}


def delta(a, b):
    """Yo'l natijasi — boshqa buyurtma bilan solishtirish uchun (id siz)."""
    o = {"h": b["h"], "ombor": ombor_farq(a["ombor"], b["ombor"]), "yuk_soni": b["yuk_soni"] - a["yuk_soni"],
         "yetk": round(b["yetk"] - a["yetk"], 6), "harakat": b["harakat"] - a["harakat"]}
    k = {}
    for kk in a["k"]:
        if kk == "kpi_yil":
            k[kk] = b["k"][kk]
        else:
            k[kk] = round(float(b["k"][kk] or 0) - float(a["k"][kk] or 0), 2)
    o["k"] = k
    return o


def farqlar(a, b):
    o = {}
    for k in a:
        if a[k] != b[k]:
            if isinstance(a[k], dict):
                o[k] = {kk: (a[k].get(kk), b[k].get(kk)) for kk in a[k] if a[k].get(kk) != b[k].get(kk)}
            else:
                o[k] = (a[k], b[k])
    return o


class Xato(Exception):
    pass


@contextlib.contextmanager
def buz(obj, nom_, shart=None, jim=False):
    """Bir martalik nosozlik: istisno (`Xato`) yoki jim rad (`success: False`)."""
    asl = getattr(obj, nom_)
    qoldi = [1]

    def _o(*a, **k):
        if qoldi[0] > 0 and (shart is None or shart(*a, **k)):
            qoldi[0] -= 1
            if jim:
                return {"success": False, "message": "sun'iy rad"}
            raise Xato(f"sun'iy xato: {nom_}")
        return asl(*a, **k)
    setattr(obj, nom_, _o)
    KUTILGAN_5XX[0] = not jim
    try:
        yield qoldi
    finally:
        setattr(obj, nom_, asl)
        KUTILGAN_5XX[0] = False


def srv(oid, loy):
    """`services.complete_order` TRANZAKSIYASIZ (to'g'ridan) — xatoda chaqiruvchi `rollback` qiladi."""
    s = SessionLocal()
    try:
        r = services.complete_order(s, oid, loy)
        return ("ok" if r.get("success") else "rad: " + str(r.get("message")))
    except Exception as e:                         # noqa: BLE001
        try:
            s.rollback()
        except Exception:                          # noqa: BLE001
            pass
        return f"xato {type(e).__name__}: {e}"
    finally:
        s.close()


_bez_ret = lambda *a, **k: "recipe_id" not in k    # noqa: E731
_ret = lambda *a, **k: "recipe_id" in k            # noqa: E731
HOLATLAR = [
    ("1 qisman, loy 5 — ortgan loy xom xomashyo bo'lib qaytishi", "S1 profil 4/10", 5.0,
     (services, "return_loy_ingredients", _bez_ret, False)),
    ("2 qisman, loy 5 — qolgan qism xomashyosi", "S1 profil 4/10", 5.0,
     (services, "return_inventory_for_order_partial", None, False)),
    ("3 qisman, loy 5 — miqdor / summa yakunlash", "S1 profil 4/10", 5.0,
     (crud, "finalize_partial_order_quantities", None, False)),
    ("4 tayyor mahsulotdan 4/10 — TM qaytishi", "S8 tayyor mahsulotdan 4/10", None,
     (crud, "_return_finished_for_order", None, False)),
    ("5 MRP 4/10 — band ozod", "S9 MRP 4/10", None, (crud, "_auto_release_mrp_reservations", None, False)),
    ("6 loy sotish 8/20 — qolgan ingredient qaytishi", "S6 loy sotish 8/20", None,
     (services, "return_loy_ingredients", _ret, False)),
    ("7 yuksiz, loy 12 — qo'shimcha loy yechish", "N0 profil 0/10", 12.0, (services, "deduct_loy_ingredients", None, False)),
    ("8 yuksiz, loy 12 — avtomatik yuk xati (istisno)", "N0 profil 0/10", 12.0, (crud, "create_delivery", None, False)),
    ("9 yuksiz, loy 12 — avtomatik yuk xati JIM rad", "N0 profil 0/10", 12.0, (crud, "create_delivery", None, True)),
    ("10 yuksiz, loy 8 — ortgan loy omborga", "N0 profil 0/10", 8.0, (services, "add_loy_to_stock", None, False)),
]
NAZORAT = {}


def nazorat(shakl, loy):
    kalit = (shakl, loy)
    if kalit not in NAZORAT:
        oid, ids, mid, mijoz = tayyorla(shakl)
        s0 = surat(oid, mid, mijoz)
        st, _d = tayyor(oid, loy)
        NAZORAT[kalit] = {"st": st, "d": delta(s0, surat(oid, mid, mijoz))}
    return NAZORAT[kalit]


# ══════════════════════════════════════════════════════════════
# A — API
# ══════════════════════════════════════════════════════════════
section("A. «Tayyor» API — nosozlik har bosqichda: holat AYNAN oldingi, qayta urinish = NAZORAT")
for nomi, shakl, loy, (mod, fn, shart, jim) in HOLATLAR:
    nz = nazorat(shakl, loy)
    oid, ids, mid, mijoz = tayyorla(shakl)
    s0 = surat(oid, mid, mijoz)
    with buz(mod, fn, shart, jim) as q:
        st, d = tayyor(oid, loy)
    s1 = surat(oid, mid, mijoz)
    st2, d2 = tayyor(oid, loy)
    s2 = surat(oid, mid, mijoz)
    kut = 400 if jim else 500
    check(f"A{nomi}: nosozlik ishladi, javob {kut}, HECH NARSA saqlanmadi",
          q[0] == 0 and st == kut and not farqlar(s0, s1), (q[0], st, farqlar(s0, s1)))
    check(f"A{nomi}: xatosiz qayta urinish 200 va natija = NAZORAT (o'sha shakl, nosozliksiz)",
          nz["st"] == 200 and st2 == 200 and delta(s0, s2) == nz["d"], (st2, farqlar(nz["d"], delta(s0, s2))))
    if jim:
        check(f"A{nomi}: rad xabarida sabab (yuk xati yozilmadi, «Tayyor» bekor)",
              "yuk xati yozilmadi" in xabar(d) and "sun'iy rad" in xabar(d), xabar(d))

# ══════════════════════════════════════════════════════════════
# B — tranzaksiyasiz
# ══════════════════════════════════════════════════════════════
section("B. services.complete_order TRANZAKSIYASIZ — o'sha nosozliklar: yarim holat YO'Q")
for nomi, shakl, loy, (mod, fn, shart, jim) in HOLATLAR:
    nz = nazorat(shakl, loy)
    oid, ids, mid, mijoz = tayyorla(shakl)
    s0 = surat(oid, mid, mijoz)
    with buz(mod, fn, shart, jim) as q:
        r = srv(oid, loy)
    s1 = surat(oid, mid, mijoz)
    st2, d2 = tayyor(oid, loy)
    s2 = surat(oid, mid, mijoz)
    check(f"B{nomi}: nosozlik ishladi ({r[:60]}), HECH NARSA saqlanmadi",
          q[0] == 0 and r != "ok" and not farqlar(s0, s1), (q[0], r, farqlar(s0, s1)))
    check(f"B{nomi}: keyin «Tayyor» 200 va natija = NAZORAT (\"allaqachon tayyor\" emas)",
          st2 == 200 and delta(s0, s2) == nz["d"], (st2, xabar(d2), farqlar(nz["d"], delta(s0, s2))))

# ══════════════════════════════════════════════════════════════
# C — o'chirilgan buyurtma
# ══════════════════════════════════════════════════════════════
section("C. O'chirilgan buyurtma: «Tayyor» / tahrir / yuk xatini o'chirish / ishlab chiqarish — rad, tiklangach ishlaydi")


def eski_ochir(oid):
    """kech100 dan OLDINGI o'chirish (qisman / to'liq topshirilgan): qolgan qism xomashyosi qaytadi, `stock_returned`,
    yumshoq o'chirish — holat O'ZGARMAYDI (IN_PROGRESS / DELIVERED). MRP bandi ozod (asl `delete_order`)."""
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if not o.is_fully_delivered:
            services.return_inventory_for_order_partial(s, o)
            o.stock_returned = True
        crud._auto_release_mrp_reservations(s, [i.id for i in o.items], "test")
        o.is_deleted = True
        s.commit()
        return o.status.value
    finally:
        s.close()


# C1 / C2 — «Tayyor»
for kod, shakl in (("C1", "S1 profil 4/10"), ("C2", "N1 profil 10/10")):
    oid, ids, mid, mijoz = tayyorla(shakl)
    st_asl = eski_ochir(oid)
    s0 = surat(oid, mid, mijoz)
    st, d = tayyor(oid, None)
    s1 = surat(oid, mid, mijoz)
    check(f"{kod} eski uslubda o'chirilgan ({st_asl}) — «Tayyor» 400 \"{XABAR}\", hech narsa o'zgarmadi "
          f"(ombor, holat, hisobot)", st == 400 and xabar(d) == XABAR and not farqlar(s0, s1),
          (st, xabar(d), farqlar(s0, s1)))
    tr = tiklash(oid)
    q_t = ombor()
    st3, d3 = tayyor(oid, None)
    h3 = holat(oid)
    if kod == "C1":
        check("C1b tiklangach «Tayyor» 200: qolgan qism penoplasti BIR marta (+0.06 — NAZORAT S1 bilan AYNAN)",
              tr == 200 and st3 == 200 and h3["status"] == "ready" and not h3["del"]
              and taxminan(ombor_farq(q_t, ombor())["PENO"], 0.06, 1e-9)
              and taxminan(nazorat("S1 profil 4/10", None)["d"]["ombor"]["PENO"], 0.06, 1e-9),
              (tr, st3, h3, ombor_farq(q_t, ombor())))
    else:
        check("C2b tiklangach «Tayyor» 200 (to'liq topshirilgan — ombor o'zgarmaydi)",
              tr == 200 and st3 == 200 and h3["status"] == "ready" and not h3["del"]
              and not any(ombor_farq(q_t, ombor()).values()), (tr, st3, h3, ombor_farq(q_t, ombor())))

# C3 — to'liq tahrir
oid, ids, mid, mijoz = tayyorla("S1 profil 4/10")
eski_ochir(oid)
s = SessionLocal()
try:
    _o3 = s.get(Order, oid)
    tana3 = {"project_id": _o3.project_id, "order_type": "product", "loy_kg": 10.0, "recipe_id": ID["REC"],
             "master_id": mid, "items": [dict(_profil(12.0), name=s.get(OrderItem, ids[0]).name)]}
finally:
    s.close()
s0 = surat(oid, mid, mijoz)
r = req(C, "put", f"/api/orders/{oid}", json=tana3, params={"confirm_shortage": "true"})
s1 = surat(oid, mid, mijoz)
check(f"C3 eski uslubda o'chirilgan — to'liq tahrir (10 → 12 m) 400 \"{XABAR}\", ombor / detal o'zgarmadi",
      r.status_code == 400 and xabar(js(r)) == XABAR and not farqlar(s0, s1), (r.status_code, xabar(js(r)), farqlar(s0, s1)))
tiklash(oid)
q_t = ombor()
r = req(C, "put", f"/api/orders/{oid}", json=tana3, params={"confirm_shortage": "true"})
check("C3b tiklangach tahrir 200: 2 m uchun penoplast yechildi (−0.02)",
      r.status_code == 200 and taxminan(ombor_farq(q_t, ombor())["PENO"], -0.02, 1e-9) and holat(oid)["items"][0][1] == 12.0,
      (r.status_code, xabar(js(r)), ombor_farq(q_t, ombor())))

# C4 — yangi uslub (READY)
oid, ids, mid, mijoz = tayyorla("S1 profil 4/10")
ochir(oid)
s0 = surat(oid, mid, mijoz)
st, d = tayyor(oid, None)
check("C4 yangi uslubda o'chirilgan (READY) — «Tayyor» 400 \"allaqachon tayyor\" (o'zgarmagan xulq), hech narsa o'zgarmadi",
      st == 400 and "allaqachon tayyor" in xabar(d) and not farqlar(s0, surat(oid, mid, mijoz)), (st, xabar(d)))

# C5 — yuk xatini o'chirish
oid, ids, mid, mijoz = tayyorla("S1 profil 4/10")
q0 = ombor()
eski_ochir(oid)
s0 = surat(oid, mid, mijoz)
r = yuk_ochir(oid)
s1 = surat(oid, mid, mijoz)
check(f"C5 eski uslubda o'chirilgan qisman — yuk xatini o'chirish 400 \"{XABAR}\", yuk / ombor o'zgarmadi",
      r.status_code == 400 and xabar(js(r)) == XABAR and not farqlar(s0, s1) and len(yuk_idlari(oid)) == 1,
      (r.status_code, xabar(js(r)), farqlar(s0, s1)))
tiklash(oid)
r = yuk_ochir(oid)
yol5 = ombor_farq(q0, ombor())                         # o'chirish → (rad) → tiklash → yuk xatini o'chirish
oidn, idsn, _mn, _mjn = tayyorla("S1 profil 4/10")
n0 = ombor()
rn = yuk_ochir(oidn)
naz5 = ombor_farq(n0, ombor())                         # NAZORAT: o'chirilmagan buyurtmada yuk xatini o'chirish
check("C5b tiklangach yuk xatini o'chirish 200; o'chirishdan oldingiga nisbatan penoplast = NAZORAT (o'chirilmagan "
      "buyurtmada yuk xatini o'chirish) — topshirilgan 4 m IKKI marta yechilmaydi",
      r.status_code == 200 and rn.status_code == 200 and taxminan(yol5["PENO"], naz5["PENO"], 1e-9)
      and taxminan(naz5["PENO"], 0.0, 1e-9), (r.status_code, rn.status_code, yol5, naz5))

# C6 — ishlab chiqarish (MRP)
oid, ids, mid, mijoz = tayyorla("M4 MRP 4/10 (4 ishlab chiqarilgan)")
st_q, po_q, _dq = po_yarat(oid, ids[0], 3)            # o'chirishdan OLDIN yaratilgan qoralama
eski_ochir(oid)
b0 = surat(oid, mid, mijoz)
st, po, d = po_yarat(oid, ids[0], 3)
check(f"C6 eski uslubda o'chirilgan MRP detaliga ishlab chiqarish yaratish — 400 \"{XABAR}\"",
      st == 400 and xabar(d) == XABAR and po is None, (st, xabar(d)))
r = req(C, "post", f"/api/production/orders/{po_q}/start")
b1 = surat(oid, mid, mijoz)
check(f"C6b o'chirishdan OLDIN yaratilgan qoralamani boshlash — rad \"{XABAR}\", mahsulot band qilinmadi, ombor "
      f"o'zgarmadi", st_q == 200 and r.status_code in (400, 409) and xabar(js(r)) == XABAR and not farqlar(b0, b1),
      (st_q, r.status_code, xabar(js(r)), farqlar(b0, b1)))
tiklash(oid)
r = req(C, "post", f"/api/production/orders/{po_q}/start")
check("C6c tiklangach o'sha qoralama boshlanadi (200) — mahsulot shu detalga band",
      r.status_code == 200 and ombor()["MRP_BAND"] >= b1["ombor"]["MRP_BAND"] + 3 - 1e-9,
      (r.status_code, xabar(js(r)), ombor()["MRP_BAND"], b1["ombor"]["MRP_BAND"]))

check("C7 rad matni yagona manbadan (crud.OCHIRILGAN_BUYURTMA_XABARI) — yuk xati qo'shish ham AYNAN",
      getattr(crud, "OCHIRILGAN_BUYURTMA_XABARI", None) == "Bu buyurtma o'chirilgan — avval uni tiklang", "")
oid, ids, mid, mijoz = tayyorla("S1 profil 4/10")
eski_ochir(oid)
r = req(C, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": ids[0], "quantity": 1}],
                                              "notes": nom("yuk"), "transport_cost": 0, "transport_payer": "none",
                                              "payment_method": "naqd"})
check("C8 yuk xati qo'shish (2026-09 audit) — o'sha matn bilan rad", r.status_code == 400 and xabar(js(r)) == XABAR,
      (r.status_code, xabar(js(r))))

# ══════════════════════════════════════════════════════════════
# P — poyga (FAQAT PG)
# ══════════════════════════════════════════════════════════════
section("P. Poyga (HAQIQIY PG): «Tayyor» qulfni oxirigacha ushlaydi")
if not PG_URL:
    print("  (SQLite — haqiqiy parallellik yo'q, o'tkazildi)")
else:
    _asl_q = services.return_inventory_for_order_partial
    KUT = [0.0]

    def _sekin(*a, **k):
        if KUT[0]:
            time.sleep(KUT[0])
        return _asl_q(*a, **k)

    services.return_inventory_for_order_partial = _sekin

    def _tayyor_oqim(oid, nat, kalit, b, kechik=0.0):
        s = SessionLocal()
        try:
            user = s.get(User, UID)
            b.wait()
            if kechik:
                time.sleep(kechik)
            try:
                r = main.api_mark_order_ready(oid, None, db=s, current_user=user)
                nat[kalit] = bool(r.get("success"))
            except Exception as e:                 # noqa: BLE001
                nat[kalit] = f"rad {type(e).__name__}: {xabar({'detail': getattr(e, 'detail', str(e))})}"
        finally:
            s.close()

    def _ochir_oqim(oid, nat, b, kechik):
        s = SessionLocal()
        try:
            user = s.get(User, UID)
            b.wait()
            time.sleep(kechik)
            try:
                r = main.api_delete_order(oid, None, db=s, current_user=user)
                nat["ochir"] = bool(r.get("yopildi"))
            except Exception as e:                 # noqa: BLE001
                nat["ochir"] = f"xato {type(e).__name__}"
        finally:
            s.close()

    def _yuk_oqim(oid, iid, nat, b, kechik):
        from schemas import DeliveryCreate, DeliveryItemCreate
        s = SessionLocal()
        try:
            b.wait()
            time.sleep(kechik)
            try:
                r = crud.create_delivery(s, DeliveryCreate(order_id=oid, items=[DeliveryItemCreate(order_item_id=iid, quantity=2)],
                                                           notes=nom("par")), delivered_by="P")
                nat["yuk"] = bool(r.get("success"))
            except Exception as e:                 # noqa: BLE001
                try:
                    s.rollback()
                except Exception:                  # noqa: BLE001
                    pass
                nat["yuk"] = f"xato {type(e).__name__}"
        finally:
            s.close()

    # P1 — kmut100 N19: «Tayyor» qulfni OLDIN oladi (qisman qaytarish 0.8 s — qulf ostida), o'chirish 0.3 s keyin
    # boshlanadi va buyurtmani qulfdan OLDIN (hali IN_PROGRESS — «Tayyor» saqlanmagan) o'qiydi. Qulfdan keyin QAYTA
    # o'qilmasa READY buyurtma ikkinchi marta "yakunlanadi" va eskirgan surat yoziladi — tiklash uni IN_PROGRESS qilardi.
    oid, ids, mid, mijoz = tayyorla("S1 profil 4/10")
    q0 = ombor()
    KUT[0] = 0.8
    nat = {}
    b = threading.Barrier(2)
    t1 = threading.Thread(target=_tayyor_oqim, args=(oid, nat, "tayyor", b))
    t2 = threading.Thread(target=_ochir_oqim, args=(oid, nat, b, 0.3))
    t1.start(); t2.start(); t1.join(); t2.join()
    KUT[0] = 0.0
    h = holat(oid)
    check(f"P1 «Tayyor» ∥ o'chirish (o'chirish qulfdan OLDIN o'qigan): «Tayyor» o'tdi, o'chirish READY ni ko'rdi — "
          f"ikkinchi yakunlash YO'Q, surat yo'q, penoplast BIR marta (+0.06) ({nat})",
          nat.get("tayyor") is True and nat.get("ochir") is False and h["status"] == "ready" and h["del"]
          and not h["json"] and taxminan(h["items"][0][1], 4.0, 1e-9)
          and taxminan(ombor_farq(q0, ombor())["PENO"], 0.06, 1e-9), (nat, h, ombor_farq(q0, ombor())))
    tr = tiklash(oid)
    h = holat(oid)
    check("P1b tiklash: buyurtma READY qoladi (eskirgan IN_PROGRESS surati bilan qaytmaydi), miqdor 4 m",
          tr == 200 and h["status"] == "ready" and not h["del"] and taxminan(h["items"][0][1], 4.0, 1e-9), (tr, h))

    # P2 — «Tayyor» ∥ «Tayyor»
    oid, ids, mid, mijoz = tayyorla("S1 profil 4/10")
    q0 = ombor()
    KUT[0] = 0.6
    nat = {}
    b = threading.Barrier(2)
    t1 = threading.Thread(target=_tayyor_oqim, args=(oid, nat, "t1", b))
    t2 = threading.Thread(target=_tayyor_oqim, args=(oid, nat, "t2", b, 0.2))
    t1.start(); t2.start(); t1.join(); t2.join()
    KUT[0] = 0.0
    h = holat(oid)
    natijalar = [nat.get("t1"), nat.get("t2")]
    check(f"P2 «Tayyor» ∥ «Tayyor»: bittasi o'tdi, ikkinchisi \"allaqachon tayyor\", penoplast BIR marta ({nat})",
          natijalar.count(True) == 1 and any("allaqachon tayyor" in str(x) for x in natijalar)
          and h["status"] == "ready" and taxminan(ombor_farq(q0, ombor())["PENO"], 0.06, 1e-9), (nat, h, ombor_farq(q0, ombor())))

    # P3 — «Tayyor» ∥ yuk xati (yuk «Tayyor» qulfini kutadi)
    oid, ids, mid, mijoz = tayyorla("S1 profil 4/10")
    q0 = ombor()
    KUT[0] = 0.6
    nat = {}
    b = threading.Barrier(2)
    t1 = threading.Thread(target=_tayyor_oqim, args=(oid, nat, "tayyor", b))
    t2 = threading.Thread(target=_yuk_oqim, args=(oid, ids[0], nat, b, 0.2))
    t1.start(); t2.start(); t1.join(); t2.join()
    KUT[0] = 0.0
    h = holat(oid)
    s = SessionLocal()
    try:
        yetk = sum(float(di.quantity or 0) for d in s.query(Delivery).filter(Delivery.order_id == oid).all() for di in d.items)
    finally:
        s.close()
    check(f"P3 «Tayyor» ∥ yuk xati: izchil — detal miqdori = topshirilgan, summa unga mos, penoplast qolgan qism uchun "
          f"BIR marta ({nat}, topshirilgan {yetk:g})",
          nat.get("tayyor") is True and h["status"] == "ready" and taxminan(h["items"][0][1], yetk, 1e-9)
          and taxminan(h["agreed"] if h["agreed"] is not None else h["total"], 50_000 * yetk, 0.01)
          and taxminan(ombor_farq(q0, ombor())["PENO"], 0.01 * (10 - yetk), 1e-9), (nat, h, yetk, ombor_farq(q0, ombor())))
    services.return_inventory_for_order_partial = _asl_q


# ══════════════════════════════════════════════════════════════
# X — 5xx
# ══════════════════════════════════════════════════════════════
section("X. Server xatosi (5xx) yo'q (sun'iy nosozliklardan tashqari)")
check("X1 kutilmagan 5xx yo'q", not XATOLAR_5XX, XATOLAR_5XX[:5])


# ══════════════════════════════════════════════════════════════
# S — statik
# ══════════════════════════════════════════════════════════════
section("S. Statik")
_co = manba(services, "complete_order")
check("S1 complete_order: loy tekshiruvi → bitta_tranzaksiya → birinchi o'qish → qulf → READY / o'chirilgan / qoralama",
      tartibda(_co, "_query_loy(", "with _crud_tr.bitta_tranzaksiya(db):", "order = db.query(Order).filter(Order.id == order_id).first()",
               "_pul_qulfi(db, 101, order.id)", "if order.status == OrderStatus.READY:", "if order.is_deleted:",
               "if order.status == OrderStatus.DRAFT:"), _co[:200])
check("S2 complete_order: avtomatik yuk rad — _TayyorBekor; oxirida except _TayyorBekor → natija",
      tartibda(_co, "if dres.get(\"success\"):", "else:", "raise _TayyorBekor(", "return result",
               "except _TayyorBekor as _rad101:", "return _rad101.natija"), "")
_uf = manba(crud, "update_order_full")
check("S3 update_order_full: qulf → qayta o'qish → READY → o'chirilgan rad → tahrir",
      tartibda(_uf, "_pul_qulfi(db, 101, order.id)", "db.expire_all()", "if order.status == OrderStatus.READY:",
               "if order.is_deleted:", "OCHIRILGAN_BUYURTMA_XABARI", "_audit_before ="), "")
_dd = manba(crud, "delete_delivery")
check("S4 delete_delivery: qulf → qayta o'qish → READY → o'chirilgan rad → to'lov so'rovi",
      tartibda(_dd, "_pul_qulfi(db, 101, order.id)", "db.expire_all()", "if order.status == OrderStatus.READY:",
               "if order.is_deleted:", "raise ValueError(OCHIRILGAN_BUYURTMA_XABARI)", "if tolovlar and tolov is None:"), "")
_cp = manba(production_service, "create_production_order")
_sp = manba(production_service, "start_production_order")
check("S5 ishlab chiqarish: yaratishda (detal topilgach) va boshlashda (qulflangan detal) o'chirilgan buyurtma rad",
      tartibda(_cp, "if not order_item:", "_ob101.is_deleted", "OCHIRILGAN_BUYURTMA_XABARI", "mrp_detal_kerak(")
      and tartibda(_sp, ".with_for_update().first()", "if locked_item:", "_ob101.is_deleted", "db.rollback()",
                   "OCHIRILGAN_BUYURTMA_XABARI", "_k = mrp_detal_kerak(db, locked_item)"), "")
_cd = manba(crud, "create_delivery")
check("S6 create_delivery: o'chirilgan rad — yagona matn (konstanta)",
      '"message": OCHIRILGAN_BUYURTMA_XABARI' in _cd and "avval uni tiklang\"}" not in _cd, "")
_am = manba(main, "api_mark_order_ready")
check("S7 API «Tayyor» — bitta_tranzaksiya ichida (kech84) — o'zgarmagan",
      tartibda(_am, "with crud.bitta_tranzaksiya(db):", "result = services.complete_order(db, order_id, loy_kg)",
               "raise HTTPException(status_code=400, detail=result)"), "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(0 if FAIL == 0 else 1)
