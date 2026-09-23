#!/usr/bin/env python3
"""
test_eski_narx_muzlash.py — 33-band darvozasi (kech49, 2026-09-24).

FOYDALANUVCHI QARORI (kech48, so'zma-so'z: "A JAVOBIM"): eski buyurtmalar BUGUNGI narxda muzlatilsin.

NIMA UCHUN: zip 47 gacha yozilgan chiqim harakatlarida `unit_cost` NULL — 32-band (zip 48)
dan keyin ham ESKI buyurtmalar tan narxi joriy narxda edi (kech47 jonli: penoplast x2 →
sentyabr sof foydasi ~10.6 mln ga siljidi).

YECHIM: `main._migrate_eski_buyurtma_narxi()` (ishga tushishda, IDEMPOTENT): buyurtma sarfi
(`order_id`, "out", `unit_cost` NULL, material mavjud, brak EMAS) ga shu paytdagi narx
yoziladi (narxsiz — 0). Brak (bog'langan yoki "Brak%"), kirim, buyurtmasiz harakat —
TEGILMAYDI; allaqachon yozilgan narx almashtirilmaydi.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_eski_narx_muzlash.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_eski_narx_muzlash.py
"""
import os
import sys
import json
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "eski_narx_test"
_DB = os.path.join(tempfile.gettempdir(), "eski_narx_test.db")

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
    import crud, auth, services                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, OrderItem, Inventory, InventoryMovement,
    Recipe, RecipeIngredient,
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


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
BAZA_NARX = {"peno": 500_000, "kley": 2_000, "akr": 10_000}

_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="TE Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TE_admin", "Parol123!", UserRole.ADMIN, "TE Admin", company_id=1)
    auth.create_user(_db, "TE_admin_b", "Parol123!", UserRole.ADMIN, "TE Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="TE Mijoz", project_name="TE loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="TE Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=BAZA_NARX["peno"], volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TE Kley", unit="kg", stock_quantity=100_000,
                 price_per_unit=BAZA_NARX["kley"], category="Kimyo")
AKR = Inventory(company_id=1, item_name="TE Akril", unit="kg", stock_quantity=100_000,
                price_per_unit=BAZA_NARX["akr"], category="Kimyo")
_db.add_all([PRJ, PENO, KLEY, AKR])
_db.commit()
R1 = Recipe(company_id=1, name="TE R1", batch_size_kg=100.0)
R2 = Recipe(company_id=1, name="TE R2", batch_size_kg=100.0)
_db.add_all([R1, R2])
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0),
             RecipeIngredient(recipe_id=R2.id, inventory_id=KLEY.id, quantity_kg=50.0),
             RecipeIngredient(recipe_id=R2.id, inventory_id=AKR.id, quantity_kg=50.0)])
_db.commit()
PRJ_ID, PENO_ID, KLEY_ID, AKR_ID, R1_ID, R2_ID = PRJ.id, PENO.id, KLEY.id, AKR.id, R1.id, R2.id
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


C, _s1 = _kir("TE_admin")
CB, _s2 = _kir("TE_admin_b")
if _s1 != 302 or _s2 != 302:
    print(f"LOGIN BO'LMADI: {_s1} / {_s2}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
# Yordamchilar
# ══════════════════════════════════════════════════════════════
_n = [0]


def narxlar(k):
    """Uchala material narxini asl narxning k barobariga qo'yadi."""
    d = SessionLocal()
    try:
        d.get(Inventory, PENO_ID).price_per_unit = BAZA_NARX["peno"] * k
        d.get(Inventory, KLEY_ID).price_per_unit = BAZA_NARX["kley"] * k
        d.get(Inventory, AKR_ID).price_per_unit = BAZA_NARX["akr"] * k
        d.commit()
    finally:
        d.close()


def profil(uzunlik, qoplama=False, nom=None):
    _n[0] += 1
    return {"name": nom or f"TE_D{_n[0]}", "category": "profil", "width": 20, "thickness": 10,
            "length": uzunlik, "quantity": 10, "unit_price": 50_000, "is_coated": bool(qoplama),
            "penoplast_id": PENO_ID, **({"recipe_id": R1_ID} if qoplama else {})}


def yarat(items, recipe_id=None, loy_kg=None, qoralama=False):
    tana = {"project_id": PRJ_ID, "order_type": "product", "items": items}
    if recipe_id:
        tana["recipe_id"] = recipe_id
    if loy_kg is not None:
        tana["loy_kg"] = loy_kg
    if qoralama:
        tana["is_draft"] = True
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    if not oid:
        raise RuntimeError(f"buyurtma yaratilmadi: {r.status_code} {r.text[:300]}")
    return oid


def tayyor(oid, loy=None):
    p = {"loy_kg": str(loy)} if loy is not None else {}
    return req(C, "post", f"/api/orders/{oid}/ready", params=p)


def detal_id(oid):
    d = SessionLocal()
    try:
        return d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).first().id
    finally:
        d.close()


def tahrir_uzunlik(oid, iid, uzunlik):
    it = profil(uzunlik, nom=f"TE_T{oid}")
    it["id"] = iid
    return req(C, "put", f"/api/orders/{oid}", json={"project_id": PRJ_ID, "order_type": "product",
                                                     "items": [it]}, params={"confirm_shortage": "true"})


def foyda(oid):
    """services.calculate_order_profit → (tan_narxi, breakdown [(nomi, summa)], volume_m3)."""
    d = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            p = services.calculate_order_profit(d, oid, company_id=1)
        return (round(float(p.get("tan_narxi", 0)), 4),
                [(b["nomi"], round(float(b["summa"]), 4)) for b in p.get("breakdown", [])],
                p.get("volume_m3"))
    except Exception as e:                 # noqa: BLE001
        return (f"XATO {type(e).__name__}: {e}", [], None)
    finally:
        d.close()


def tan(oid):
    return foyda(oid)[0]


def qator(oid, boshi):
    for nomi, summa in foyda(oid)[1]:
        if nomi.startswith(boshi):
            return summa
    return None


def harakatlar(oid):
    d = SessionLocal()
    try:
        return d.query(InventoryMovement).filter(InventoryMovement.order_id == oid).order_by(InventoryMovement.id).all()
    finally:
        d.close()


def jurnal(oid, inv_id, turi, miqdor, reason="TE qo'lda harakat"):
    """Haqiqiy `crud.log_movement` orqali (narx o'sha paytdagi — `unit_cost`)."""
    d = SessionLocal()
    try:
        inv = d.get(Inventory, inv_id)
        crud.log_movement(d, inv_id, inv.item_name, turi, miqdor, unit=inv.unit,
                          reason=reason, order_id=oid, company_id=1)
        d.commit()
    finally:
        d.close()


from datetime import datetime as _dt        # noqa: E402
_HOZ = _dt.utcnow()
YIL, OY = _HOZ.year, _HOZ.month


def hisobotlar():
    """Oylik hisobot (xarajat, sof foyda), liniya hisoboti (butun lug'at),
    kunlik ko'rinish (butun lug'at) — JSON matn sifatida (solishtirish uchun)."""
    d = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            m = services.get_monthly_report(d, YIL, OY, company_id=1)
            sp = services.calculate_split_profit_report(d, YIL, OY, company_id=1)
            kun = services.get_daily_finance_summary(d, _dt.now().date(), company_id=1)
            kun2 = services.get_daily_finance_summary(d, _HOZ.date(), company_id=1)
        return (round(float(m.get("ishlab_chiqarish_xarajat") or 0), 4),
                round(float(m.get("sof_foyda") or 0), 4),
                json.dumps(sp, sort_keys=True, default=str),
                json.dumps([kun, kun2], sort_keys=True, default=str))
    except Exception as e:                 # noqa: BLE001
        return (f"XATO {type(e).__name__}: {e}", None, None, None)
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════
# Tayyorlash: "eski" harakatlar (zip 47 gacha — unit_cost NULL)
# ══════════════════════════════════════════════════════════════
section("0 — eski holatni yaratish")
O1 = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=50)
r = tayyor(O1, 50)
check("00 O1 'Tayyor' (profil 1 blok + qoplama 50 kg)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
O2 = yarat([profil(100)])
_d = SessionLocal()
_o2nom = _d.query(OrderItem).filter(OrderItem.order_id == O2).first().name
_d.close()
r = req(C, "post", "/api/returns", json={"order_id": O2, "order_item_id": detal_id(O2), "item_name": _o2nom,
                                          "quantity": 10, "unit": "metr", "reason": "Brak", "refund_amount": 0,
                                          "to_stock": False, "coating_applied": False})
check("01 O2 brak 10 m (bog'langan brak harakati)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
O3 = yarat([profil(100)])
_d = SessionLocal()
_o3nom = _d.query(OrderItem).filter(OrderItem.order_id == O3).first().name
_d.close()
r = req(C, "post", "/api/returns", json={"order_id": O3, "order_item_id": detal_id(O3), "item_name": _o3nom,
                                          "quantity": 10, "unit": "metr", "reason": "Brak", "refund_amount": 0,
                                          "to_stock": False, "coating_applied": False})
check("02 O3 brak 10 m (keyin bog'lami olinadi — eski brak)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
_d = SessionLocal()
NOLNARX = Inventory(company_id=1, item_name="TE narxsiz", unit="kg", stock_quantity=100, price_per_unit=None, category="Kimyo")
_d.add(NOLNARX)
_d.commit()
NOL_ID = NOLNARX.id
_d.close()
O5 = yarat([profil(100)], qoralama=True)
# qo'lda (haqiqiy crud.log_movement) harakatlar
jurnal(O5, NOL_ID, "out", 5, reason="TE narxsiz material")          # narxsiz → 0
jurnal(O5, PENO_ID, "out", 1.0, reason=None)                         # sababsiz
jurnal(O1, KLEY_ID, "in", 3, reason="TE kirim")                      # kirim — NULL qoladi
jurnal(None, PENO_ID, "out", 2.0, reason="TE qo'lda chiqim")         # buyurtmasiz
_d = SessionLocal()
crud.log_movement(_d, None, "TE materialsiz", "out", 1.0, unit="kg", reason="TE materialsiz", order_id=O5, company_id=1)
_d.commit()
# O3 brak — bog'lamini olib tashlash (zip 46 gacha yozilgan brak kabi)
_d.query(InventoryMovement).filter(InventoryMovement.order_id == O3,
                                   InventoryMovement.reason.like("Brak%")).update({"return_item_id": None},
                                                                                 synchronize_session=False)
# O2 brak — bog'lam QOLADI, sabab boshqa (faqat `return_item_id` to'sig'ini sinash uchun)
_d.query(InventoryMovement).filter(InventoryMovement.order_id == O2,
                                   InventoryMovement.reason.like("Brak%")).update({"reason": "TE bog'langan boshqa sabab"},
                                                                                 synchronize_session=False)
# HAMMA harakat — zip 47 gacha kabi narxsiz
_d.query(InventoryMovement).update({"unit_cost": None}, synchronize_session=False)
_d.commit()
_d.close()
# O4 — yangilanishdan KEYIN yozilgan (narx muzlatilgan, x1)
O4 = yarat([profil(100)])
_h4 = [h for h in harakatlar(O4) if h.movement_type == "out"]
check("03 O4 (yangi) harakati narxli — 500 000", len(_h4) == 1 and taxminan(_h4[0].unit_cost, 500_000), [(h.unit_cost) for h in _h4])


def narx_suratlari():
    d = SessionLocal()
    try:
        return {h.id: h.unit_cost for h in d.query(InventoryMovement).order_by(InventoryMovement.id).all()}
    finally:
        d.close()


def brak_jami():
    d = SessionLocal()
    try:
        return float(crud.get_brak_material_summary(d, company_id=1).get("total_value") or 0)
    finally:
        d.close()


def oylik_xarajat():
    d = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            m = services.get_monthly_report(d, YIL, OY, company_id=1)
        return round(float(m.get("ishlab_chiqarish_xarajat") or 0), 4)
    except Exception as e:                 # noqa: BLE001
        return f"XATO {type(e).__name__}: {e}"
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════
# A — migratsiya: hisobot raqamlari AYNAN qoladi, keyin muzlaydi
# ══════════════════════════════════════════════════════════════
section("A — bugungi narxda muzlatish")
narxlar(2)
t_oldin = tan(O1)
o_oldin = oylik_xarajat()
b_oldin = brak_jami()
check("A0 migratsiyadan oldin O1 joriy (x2) narxda: 1 000 000 + 50 × 10 400 = 1 520 000", taxminan(t_oldin, 1_520_000), t_oldin)
_mig = getattr(main, "_migrate_eski_buyurtma_narxi", None)
check("A1 main._migrate_eski_buyurtma_narxi bor", callable(_mig))
try:
    with contextlib.redirect_stdout(_quiet):
        _mig()
    _xato = None
except Exception as e:                     # noqa: BLE001
    _xato = f"{type(e).__name__}: {e}"
check("A2 migratsiya xatosiz", _xato is None, _xato)
_s1 = narx_suratlari()
check("A3 O1 tan narxi migratsiya paytida AYNAN (1 520 000)", taxminan(tan(O1), t_oldin), f"{t_oldin} -> {tan(O1)}")
check("A4 oylik ishlab chiqarish xarajati AYNAN", taxminan(oylik_xarajat(), o_oldin), f"{o_oldin} -> {oylik_xarajat()}")
_o1 = {h.inventory_id: h.unit_cost for h in harakatlar(O1) if h.movement_type == "out"}
check("A5 O1 chiqimlari bugungi (x2) narxda: penoplast 1 000 000, kley 4 000, akril 20 000",
      taxminan(_o1.get(PENO_ID), 1_000_000) and taxminan(_o1.get(KLEY_ID), 4_000) and taxminan(_o1.get(AKR_ID), 20_000), _o1)
narxlar(3)
check("A6 narx x3 bo'lgach O1 tan narxi O'ZGARMADI (1 520 000; migratsiyasiz 2 280 000)", taxminan(tan(O1), t_oldin), tan(O1))
check("A7 oylik xarajat x3 da ham AYNAN", taxminan(oylik_xarajat(), o_oldin), f"{o_oldin} -> {oylik_xarajat()}")

# ══════════════════════════════════════════════════════════════
# B — nimaga TEGILMAYDI
# ══════════════════════════════════════════════════════════════
section("B — tegilmaydigan harakatlar")
_bog = [h for h in harakatlar(O2) if h.return_item_id is not None]
check("B1 brak yozuviga bog'langan harakat (sababi 'Brak' emas bo'lsa ham) NULL qoldi",
      _bog and all(h.unit_cost is None for h in _bog), [(h.unit_cost, h.return_item_id, h.reason) for h in _bog])
_eski_brak = [h for h in harakatlar(O3) if (h.reason or "").startswith("Brak")]
check("B2 eski (bog'lamsiz) brak harakati NULL qoldi", _eski_brak and all(h.unit_cost is None and h.return_item_id is None for h in _eski_brak),
      [(h.unit_cost, h.return_item_id) for h in _eski_brak])
check("B3 brak xulosasi joriy narxda qoldi (13-band 2-qadam): x3 da 1.5 × x2 qiymati", taxminan(brak_jami(), b_oldin * 1.5, 1),
      f"{b_oldin} -> {brak_jami()}")
_kirim = [h for h in harakatlar(O1) if h.movement_type == "in"]
check("B4 kirim harakati NULL qoldi", _kirim and all(h.unit_cost is None for h in _kirim), [(h.unit_cost) for h in _kirim])
_d = SessionLocal()
try:
    _buyurtmasiz = _d.query(InventoryMovement).filter(InventoryMovement.order_id.is_(None),
                                                     InventoryMovement.reason == "TE qo'lda chiqim").all()
    _materialsiz = _d.query(InventoryMovement).filter(InventoryMovement.inventory_id.is_(None),
                                                     InventoryMovement.order_id == O5).all()
finally:
    _d.close()
check("B5 buyurtmasiz chiqim NULL qoldi", _buyurtmasiz and all(h.unit_cost is None for h in _buyurtmasiz),
      [(h.unit_cost) for h in _buyurtmasiz])
check("B6 materialsiz (inventory_id NULL) chiqim NULL qoldi", _materialsiz and all(h.unit_cost is None for h in _materialsiz),
      [(h.unit_cost) for h in _materialsiz])
_h4b = [h for h in harakatlar(O4) if h.movement_type == "out"]
check("B7 allaqachon narxli (O4, 500 000) harakat ALMASHTIRILMADI", len(_h4b) == 1 and taxminan(_h4b[0].unit_cost, 500_000),
      [(h.unit_cost) for h in _h4b])
check("B8 O4 tan narxi 500 000", taxminan(tan(O4), 500_000), tan(O4))

# ══════════════════════════════════════════════════════════════
# C — chekkalar
# ══════════════════════════════════════════════════════════════
section("C — chekkalar")
_o5 = [h for h in harakatlar(O5) if h.inventory_id == NOL_ID]
check("C1 narxsiz material chiqimi → 0", len(_o5) == 1 and _o5[0].unit_cost is not None and taxminan(_o5[0].unit_cost, 0),
      [(h.unit_cost) for h in _o5])
_sab = [h for h in harakatlar(O5) if h.inventory_id == PENO_ID and h.reason is None]
check("C2 sababsiz buyurtma chiqimi → bugungi (x2) narx 1 000 000", len(_sab) == 1 and taxminan(_sab[0].unit_cost, 1_000_000),
      [(h.unit_cost) for h in _sab])
_s2_oldin = narx_suratlari()
try:
    with contextlib.redirect_stdout(_quiet):
        _mig()
except Exception as e:                     # noqa: BLE001
    print("  (qayta ishga tushirish xatosi)", e)
_s2 = narx_suratlari()
check("C3 qayta ishga tushirish (narx x3) hech narsani o'zgartirmaydi", _s2 == _s2_oldin and _s2 == _s1,
      [(k, _s1.get(k), v) for k, v in _s2.items() if _s1.get(k) != v][:5])
narxlar(1)
check("C4 narx x1 da ham O1 1 520 000", taxminan(tan(O1), t_oldin), tan(O1))

# ══════════════════════════════════════════════════════════════
# S — statik
# ══════════════════════════════════════════════════════════════
section("S — statik")
try:
    _msrc = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
except Exception:                          # noqa: BLE001
    _msrc = ""
_i1 = _msrc.find("\n_migrate_harakat_narx()\n")
_i2 = _msrc.find("\n_migrate_eski_buyurtma_narxi()\n")
check("S1 migratsiya ishga tushishda chaqiriladi (unit_cost ustuni migratsiyasidan KEYIN)", _i1 >= 0 and _i2 > _i1, (_i1, _i2))
try:
    _fsrc = inspect.getsource(_mig) if callable(_mig) else ""
except Exception:                          # noqa: BLE001
    _fsrc = ""
check("S2 brak sharti brak xulosasi bilan bir xil (reason LIKE 'Brak%', return_item_id IS NULL)",
      '"Brak%"' in _fsrc and "return_item_id IS NULL" in _fsrc and "unit_cost IS NULL" in _fsrc)

print()
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   -", f)
sys.exit(0 if FAIL == 0 else 1)
