#!/usr/bin/env python3
"""
test_eski_brak_muzlash.py — 37-band darvozasi (kech51, 2026-09-24).

FOYDALANUVCHI QARORI (kech51, tugma bilan): "A — bugungi narxda muzlatilsin" — eski brak ham.

NIMA UCHUN: zip 47 gacha yozilgan BRAK chiqim harakatlarida `unit_cost` NULL — brak xulosasi
(`crud.get_brak_material_summary`, oylik hisobot `brak_xarajat` → sof foyda, liniya hisoboti)
ular uchun JORIY narxni oladi (kech47 / kech50 jonli: penoplast x2 → eski brak 747 343 →
1 494 352, sentyabr sof foydasi −747 009).

YECHIM: `main._migrate_eski_brak_narxi()` (ishga tushishda, 33-band migratsiyasidan KEYIN,
IDEMPOTENT): brak (bog'langan YOKI sabab "Brak%") "out", `unit_cost` NULL, material mavjud →
shu paytdagi narx (narxsiz — 0). `order_id` shart emas (ishlab chiqarish braki). Kirim, brakdan
boshqa chiqim, materialsiz harakat — TEGILMAYDI; allaqachon yozilgan narx almashtirilmaydi.

SEZGIRLIK: A1 / A2 — migratsiyasiz eski brak narx bilan o'zgarishini SHU fiksturada isbotlaydi.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_eski_brak_muzlash.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_eski_brak_muzlash.py
"""
import os
import sys
import json
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "eski_brak_test"
_DB = os.path.join(tempfile.gettempdir(), "eski_brak_test.db")

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
    UserRole, Project, OrderItem, Inventory, InventoryMovement, ReturnItem,
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
    _db.add(Company(id=2, name="TB Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TB_admin", "Parol123!", UserRole.ADMIN, "TB Admin", company_id=1)
    auth.create_user(_db, "TB_admin_b", "Parol123!", UserRole.ADMIN, "TB Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="TB Mijoz", project_name="TB loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="TB Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=BAZA_NARX["peno"], volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TB Kley", unit="kg", stock_quantity=100_000,
                 price_per_unit=BAZA_NARX["kley"], category="Kimyo")
AKR = Inventory(company_id=1, item_name="TB Akril", unit="kg", stock_quantity=100_000,
                price_per_unit=BAZA_NARX["akr"], category="Kimyo")
_db.add_all([PRJ, PENO, KLEY, AKR])
_db.commit()
R1 = Recipe(company_id=1, name="TB R1", batch_size_kg=100.0)
R2 = Recipe(company_id=1, name="TB R2", batch_size_kg=100.0)
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


C, _s1 = _kir("TB_admin")
CB, _s2 = _kir("TB_admin_b")
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
    return {"name": nom or f"TB_D{_n[0]}", "category": "profil", "width": 20, "thickness": 10,
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
    it = profil(uzunlik, nom=f"TB_T{oid}")
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


def jurnal(oid, inv_id, turi, miqdor, reason="TB qo'lda harakat"):
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
    """Oylik hisobot (ishlab chiqarish xarajati, brak xarajati, sof foyda) va liniya
    hisoboti (butun lug'at, JSON) — solishtirish uchun."""
    d = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            m = services.get_monthly_report(d, YIL, OY, company_id=1)
            sp = services.calculate_split_profit_report(d, YIL, OY, company_id=1)
        return (round(float(m.get("ishlab_chiqarish_xarajat") or 0), 4),
                round(float(m.get("brak_xarajat") or 0), 4),
                round(float(m.get("sof_foyda") or 0), 4),
                json.dumps(sp, sort_keys=True, default=str))
    except Exception as e:                 # noqa: BLE001
        return (f"XATO {type(e).__name__}: {e}", None, None, None)
    finally:
        d.close()


def brak_yoz(oid, qoplama=False, miqdor=10):
    d = SessionLocal()
    try:
        nom = d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).first().name
    finally:
        d.close()
    return req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": detal_id(oid), "item_name": nom,
                                              "quantity": miqdor, "unit": "metr", "reason": "Brak",
                                              "refund_amount": 0, "to_stock": False,
                                              "coating_applied": bool(qoplama)})


def surat():
    d = SessionLocal()
    try:
        return {h.id: h.unit_cost for h in d.query(InventoryMovement).order_by(InventoryMovement.id).all()}
    finally:
        d.close()


def brak_xulosa(korxona=1):
    d = SessionLocal()
    try:
        return json.dumps(crud.get_brak_material_summary(d, company_id=korxona), sort_keys=True, default=str)
    except Exception as e:                 # noqa: BLE001
        return f"XATO {type(e).__name__}: {e}"
    finally:
        d.close()


def brak_jami(korxona=1):
    try:
        return float(json.loads(brak_xulosa(korxona)).get("total_value") or 0)
    except Exception:                      # noqa: BLE001
        return None


def idlar(*shartlar):
    d = SessionLocal()
    try:
        return sorted(h.id for h in d.query(InventoryMovement).filter(*shartlar).all())
    finally:
        d.close()


def narx(hid):
    d = SessionLocal()
    try:
        h = d.get(InventoryMovement, hid)
        return h.unit_cost if h else "YO'Q"
    finally:
        d.close()


def migratsiya(fn):
    """Migratsiyani chaqiradi: (xato yoki None, chiqish matni)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            fn()
        return None, buf.getvalue()
    except Exception as e:                 # noqa: BLE001
        return f"{type(e).__name__}: {e}", buf.getvalue()


# ══════════════════════════════════════════════════════════════
# Tayyorlash: "eski" brak harakatlari (zip 47 gacha — unit_cost NULL)
# ══════════════════════════════════════════════════════════════
section("0 — eski holatni yaratish")
O1 = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=50)
r = tayyor(O1, 50)
check("00 O1 'Tayyor' (buyurtma sarfi — brak EMAS)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
O2 = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=50)
r = brak_yoz(O2, qoplama=True)
check("01 O2 qoplamali brak 10 m (penoplast + loy ingredientlari, bog'langan)", r.status_code == 200,
      f"{r.status_code} {r.text[:200]}")
O3 = yarat([profil(100)])
r = brak_yoz(O3)
check("02 O3 brak 10 m (keyin bog'lami olinadi — zip 46 gacha kabi)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
O6 = yarat([profil(100)])
r = brak_yoz(O6)
check("03 O6 brak 10 m (bog'lam qoladi, sababi boshqa matn)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")

_d = SessionLocal()
NOLNARX = Inventory(company_id=1, item_name="TB narxsiz", unit="kg", stock_quantity=100, price_per_unit=None, category="Kimyo")
BPENO = Inventory(company_id=2, item_name="TB B penoplast", unit="blok", stock_quantity=100, price_per_unit=777.0,
                  volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_d.add_all([NOLNARX, BPENO])
_d.commit()
NOL_ID, BPENO_ID = NOLNARX.id, BPENO.id
_d.close()
jurnal(None, PENO_ID, "out", 0.5, reason="Brak (ishlab chiqarish) — TB mahsulot (5 birlik)")   # buyurtmasiz brak
jurnal(None, NOL_ID, "out", 5, reason="Brak — TB narxsiz (1 birlik)")                           # narxsiz → 0
jurnal(None, PENO_ID, "in", 0.2, reason="Brak — TB kirim")                                      # kirim — tegilmaydi
jurnal(None, PENO_ID, "out", 2.0, reason="TB qo'lda chiqim")                                    # brak emas
jurnal(None, KLEY_ID, "out", 1.0, reason="brak — TB kichik harf")                              # LIKE: SQLite ha, PG yo'q
_d = SessionLocal()
crud.log_movement(_d, None, "TB materialsiz", "out", 1.0, unit="kg", reason="Brak — TB materialsiz",
                  order_id=None, company_id=1)
crud.log_movement(_d, BPENO_ID, "TB B penoplast", "out", 3.0, unit="blok", reason="Brak — TB B korxona",
                  order_id=None, company_id=2)
_d.commit()
_d.query(InventoryMovement).filter(InventoryMovement.order_id == O3,
                                   InventoryMovement.reason.like("Brak%")).update({"return_item_id": None},
                                                                                 synchronize_session=False)
_d.query(InventoryMovement).filter(InventoryMovement.order_id == O6,
                                   InventoryMovement.reason.like("Brak%")).update({"reason": "TB bog'langan boshqa sabab"},
                                                                                 synchronize_session=False)
# HAMMA harakat — zip 47 gacha kabi narxsiz (kech52: va brak belgisisiz — eski harakatlarda NULL)
_d.query(InventoryMovement).update({"unit_cost": None}, synchronize_session=False)
if hasattr(InventoryMovement, "is_brak"):
    _d.query(InventoryMovement).update({"is_brak": None}, synchronize_session=False)
_d.commit()
_d.close()

# O4 — yangilanishdan KEYIN yozilgan brak (narx muzlatilgan, x1)
O4 = yarat([profil(100)])
r = brak_yoz(O4)
check("04 O4 (yangi) brak yozildi", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
H_O4 = idlar(InventoryMovement.order_id == O4, InventoryMovement.return_item_id.isnot(None))
check("05 O4 brak harakati narxli — 500 000 (x1)", len(H_O4) == 1 and taxminan(narx(H_O4[0]), 500_000),
      [narx(i) for i in H_O4])

# Kutilgan to'plamlar (fikstura bilimi bo'yicha — migratsiya mantig'idan MUSTAQIL)
H_O2 = idlar(InventoryMovement.order_id == O2, InventoryMovement.return_item_id.isnot(None))
H_O2_PENO = idlar(InventoryMovement.order_id == O2, InventoryMovement.return_item_id.isnot(None),
                  InventoryMovement.inventory_id == PENO_ID)
H_O2_KIMYO = idlar(InventoryMovement.order_id == O2, InventoryMovement.return_item_id.isnot(None),
                   InventoryMovement.inventory_id.in_([KLEY_ID, AKR_ID]))
H_O3 = idlar(InventoryMovement.order_id == O3, InventoryMovement.reason.like("Brak%"))
H_O6 = idlar(InventoryMovement.reason == "TB bog'langan boshqa sabab")
H_ISH = idlar(InventoryMovement.reason == "Brak (ishlab chiqarish) — TB mahsulot (5 birlik)")
H_NOL = idlar(InventoryMovement.reason == "Brak — TB narxsiz (1 birlik)")
H_KIR = idlar(InventoryMovement.reason == "Brak — TB kirim")
H_QOL = idlar(InventoryMovement.reason == "TB qo'lda chiqim")
H_KICH = idlar(InventoryMovement.reason == "brak — TB kichik harf")
H_MATS = idlar(InventoryMovement.reason == "Brak — TB materialsiz")
H_B = idlar(InventoryMovement.reason == "Brak — TB B korxona")
check("06 fikstura: O2 brakida penoplast VA loy ingredienti harakatlari bor",
      len(H_O2_PENO) == 1 and len(H_O2_KIMYO) >= 1, (H_O2, H_O2_PENO, H_O2_KIMYO))
check("07 fikstura: O3 (bog'lamsiz) va O6 (boshqa sabab) brak harakatlari — 1 tadan",
      len(H_O3) == 1 and len(H_O6) == 1, (H_O3, H_O6))
check("08 fikstura: qo'lda harakatlar — har biri 1 ta",
      all(len(x) == 1 for x in (H_ISH, H_NOL, H_KIR, H_QOL, H_KICH, H_MATS, H_B)),
      (H_ISH, H_NOL, H_KIR, H_QOL, H_KICH, H_MATS, H_B))
KUTILGAN = set(H_O2 + H_O3 + H_O6 + H_ISH + H_NOL + H_B + ([] if PG_URL else H_KICH))
_s_fikstura = surat()
check("09 fikstura: kutilgan brak harakatlari hammasi NULL (eski holat)",
      KUTILGAN and all(_s_fikstura.get(i) is None for i in KUTILGAN), {i: _s_fikstura.get(i) for i in KUTILGAN})

# ══════════════════════════════════════════════════════════════
# A — sezgirlik isboti, so'ng migratsiya
# ══════════════════════════════════════════════════════════════
section("A — migratsiya: hisobot raqamlari AYNAN qoladi, keyin muzlaydi")
narxlar(2)
_mig33 = getattr(main, "_migrate_eski_buyurtma_narxi", None)
_x33, _ = migratsiya(_mig33) if callable(_mig33) else ("yo'q", "")
check("A0 33-band migratsiyasi (buyurtma sarfi) xatosiz — ishga tushishdagi tartib", _x33 is None, _x33)
b0 = brak_jami()
x0 = brak_xulosa()
h0 = hisobotlar()
narxlar(3)
b_x3 = brak_jami()
h_x3 = hisobotlar()
_d = SessionLocal()
V4 = sum(float(_d.get(InventoryMovement, i).quantity) * float(_d.get(InventoryMovement, i).unit_cost or 0) for i in H_O4)
_d.close()
check("A1 SEZGIRLIK: migratsiyasiz eski brak x3 da 1.5 × (x2 qiymati − yangi O4), O4 esa o'zgarmaydi",
      b0 and V4 > 0 and b_x3 is not None and taxminan(b_x3, (b0 - V4) * 1.5 + V4, 1), (b0, b_x3, V4))
check("A2 SEZGIRLIK: x3 da sof foyda AYNAN brak farqi qadar kamaydi (buyurtma sarfi 33-band bilan muzlagan)",
      isinstance(h_x3[2], float) and taxminan(h0[2] - h_x3[2], b_x3 - b0, 1) and taxminan(h_x3[0], h0[0]),
      (h0[:3], h_x3[:3]))
narxlar(2)
s_oldin = surat()
_mig = getattr(main, "_migrate_eski_brak_narxi", None)
check("A3 main._migrate_eski_brak_narxi bor", callable(_mig))
_xato, _chiq = migratsiya(_mig) if callable(_mig) else ("yo'q", "")
check("A4 migratsiya xatosiz", _xato is None, _xato)
check(f"A5 xabar: \"muzlatildi: {len(KUTILGAN)} ta\"", f"muzlatildi: {len(KUTILGAN)} ta" in _chiq, _chiq.strip()[:200])
s_keyin = surat()
_ozgardi = {i for i in s_keyin if s_oldin.get(i) != s_keyin.get(i)}
check("A6 AYNAN kutilgan brak harakatlari o'zgardi (boshqasi — hech biri)", _ozgardi == KUTILGAN,
      (sorted(_ozgardi - KUTILGAN), sorted(KUTILGAN - _ozgardi)))
check("A7 brak jami migratsiya paytida AYNAN", taxminan(brak_jami(), b0), (b0, brak_jami()))
check("A8 brak xulosasi (material / buyurtma bo'yicha) AYNAN", brak_xulosa() == x0)
check("A9 oylik hisobot va liniya hisoboti AYNAN", hisobotlar() == h0, (h0[:3], hisobotlar()[:3]))
check("A10 eski brak narxlari bugungi (x2): penoplast 1 000 000 (O2, O3, O6, ishlab chiqarish)",
      all(taxminan(narx(i), 1_000_000) for i in H_O2_PENO + H_O3 + H_O6 + H_ISH),
      [narx(i) for i in H_O2_PENO + H_O3 + H_O6 + H_ISH])
_kimyo_ok = True
for i in H_O2_KIMYO:
    d = SessionLocal()
    h = d.get(InventoryMovement, i)
    kut = BAZA_NARX["kley"] * 2 if h.inventory_id == KLEY_ID else BAZA_NARX["akr"] * 2
    _kimyo_ok = _kimyo_ok and taxminan(h.unit_cost, kut)
    d.close()
check("A11 O2 loy ingredientlari bugungi (x2) narxda: kley 4 000, akril 20 000", _kimyo_ok,
      [narx(i) for i in H_O2_KIMYO])
narxlar(3)
check("A12 narx x3 bo'lgach brak jami O'ZGARMADI (migratsiyasiz 1.5 ×)", taxminan(brak_jami(), b0), (b0, brak_jami()))
check("A13 x3 da brak xulosasi AYNAN", brak_xulosa() == x0)
check("A14 x3 da oylik hisobot (brak xarajati, sof foyda) va liniya hisoboti AYNAN", hisobotlar() == h0,
      (h0[:3], hisobotlar()[:3]))
narxlar(1)
check("A15 x1 da ham hisobotlar AYNAN", hisobotlar() == h0 and brak_xulosa() == x0, (h0[:3], hisobotlar()[:3]))

# ══════════════════════════════════════════════════════════════
# B — nimaga TEGILMAYDI
# ══════════════════════════════════════════════════════════════
section("B — nimaga TEGILMAYDI")
check("B1 brak sababli KIRIM harakati NULL qoldi", all(narx(i) is None for i in H_KIR), [narx(i) for i in H_KIR])
check("B2 brak bo'lmagan buyurtmasiz chiqim NULL qoldi", all(narx(i) is None for i in H_QOL), [narx(i) for i in H_QOL])
check("B3 materialsiz brak chiqimi NULL qoldi", all(narx(i) is None for i in H_MATS), [narx(i) for i in H_MATS])
check("B4 yangi (O4) brak narxi ALMASHTIRILMADI (500 000, x2 emas)",
      all(taxminan(narx(i), 500_000) for i in H_O4), [narx(i) for i in H_O4])
_buyurtma = [i for i in s_oldin if i not in KUTILGAN and s_oldin.get(i) is not None]
check("B5 33-band muzlatgan buyurtma sarfi o'zgarmadi", _buyurtma and all(s_keyin.get(i) == s_oldin.get(i) for i in _buyurtma),
      len(_buyurtma))
if PG_URL:
    check("B6 kichik harfli 'brak' (PG) — PG LIKE katta-kichikka sezgir: xulosada ham, migratsiyada ham YO'Q",
          all(narx(i) is None for i in H_KICH), [narx(i) for i in H_KICH])
else:
    check("B6 [SQLite] kichik harfli 'brak' — SQLite LIKE sezgir emas: xulosa bilan bir xil, muzlatildi (kley 4 000)",
          all(taxminan(narx(i), 4_000) for i in H_KICH), [narx(i) for i in H_KICH])

# ══════════════════════════════════════════════════════════════
# C — chekkalar
# ══════════════════════════════════════════════════════════════
section("C — chekkalar")
check("C1 narxsiz material braki → 0 (NULL emas)", all(narx(i) is not None and taxminan(narx(i), 0) for i in H_NOL),
      [narx(i) for i in H_NOL])
check("C2 bog'langan brak (sababi 'Brak' emas) ham muzlatildi", all(taxminan(narx(i), 1_000_000) for i in H_O6),
      [narx(i) for i in H_O6])
check("C3 buyurtmasiz (ishlab chiqarish) braki muzlatildi", all(taxminan(narx(i), 1_000_000) for i in H_ISH),
      [narx(i) for i in H_ISH])
check("C4 2-korxona braki O'Z materiali narxida (777)", all(taxminan(narx(i), 777) for i in H_B), [narx(i) for i in H_B])
_s1 = surat()
_xato2, _chiq2 = migratsiya(_mig) if callable(_mig) else ("yo'q", "")
check("C5 qayta ishga tushirish (narx x1) hech narsani o'zgartirmaydi, xabar chiqmaydi",
      _xato2 is None and surat() == _s1 and "muzlatildi" not in _chiq2, (_xato2, _chiq2.strip()[:120]))
_d = SessionLocal()
_qolgan = [h.id for h in _d.query(InventoryMovement).filter(
    InventoryMovement.movement_type == "out", InventoryMovement.reason.like("Brak%"),
    InventoryMovement.unit_cost.is_(None), InventoryMovement.inventory_id.isnot(None)).all()]
_d.close()
check("C6 brak xulosasi o'qiydigan (reason LIKE 'Brak%') materialli chiqimlarning HAMMASI narxli", _qolgan == [], _qolgan)
# 13-band 6-qadam bilan birga: muzlatilgan brakni o'chirish xomashyoni qaytaradi, xulosadan chiqadi
_d = SessionLocal()
_ri = _d.query(ReturnItem).filter(ReturnItem.order_id == O2).first()
_ri_id = _ri.id if _ri else None
_peno_oldin = float(_d.get(Inventory, PENO_ID).stock_quantity)
_o2_peno_miq = float(_d.get(InventoryMovement, H_O2_PENO[0]).quantity) if H_O2_PENO else 0.0
_o2_qiymat = sum(float(_d.get(InventoryMovement, i).quantity) * float(_d.get(InventoryMovement, i).unit_cost or 0)
                 for i in H_O2)
_d.close()
_b_oldin = brak_jami()
r = req(C, "delete", f"/api/returns/{_ri_id}")
_d = SessionLocal()
_peno_keyin = float(_d.get(Inventory, PENO_ID).stock_quantity)
_d.close()
check("C7 muzlatilgan O2 brakini o'chirish → 200, penoplast omborga qaytdi",
      r.status_code == 200 and taxminan(_peno_keyin - _peno_oldin, _o2_peno_miq, 1e-9),
      f"{r.status_code} {r.text[:150]} {_peno_oldin} -> {_peno_keyin}")
check("C8 brak jami AYNAN O2 ning muzlatilgan qiymati qadar kamaydi",
      taxminan(_b_oldin - brak_jami(), _o2_qiymat, 1), (_b_oldin, brak_jami(), _o2_qiymat))
check("C9 2-korxona brak xulosasi 1-korxona harakatlarini ko'rmaydi (3 × 777 = 2 331)",
      taxminan(brak_jami(2), 2_331, 1), brak_jami(2))

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
_i3 = _msrc.find("\n_migrate_eski_brak_narxi()\n")
check("S1 migratsiya ishga tushishda chaqiriladi (unit_cost ustuni va 33-band migratsiyasidan KEYIN)",
      _i1 >= 0 and _i2 > _i1 and _i3 > _i2, (_i1, _i2, _i3))
try:
    _fsrc = inspect.getsource(_mig) if callable(_mig) else ""
except Exception:                          # noqa: BLE001
    _fsrc = ""
check("S2 brak sharti 33-band ta'rifi bilan bir xil (return_item_id IS NOT NULL OR reason LIKE 'Brak%')",
      '{"brak": "Brak%"}' in _fsrc and "return_item_id IS NOT NULL OR reason LIKE :brak" in _fsrc
      and "unit_cost IS NULL" in _fsrc and "movement_type = 'out'" in _fsrc)

print()
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   -", f)
sys.exit(0 if FAIL == 0 else 1)
