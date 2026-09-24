#!/usr/bin/env python3
"""
test_brak_belgisi.py — 13-band 3-qadam darvozasi (kech52, 2026-09-24).

NIMA UCHUN: brak xarajati (`crud.get_brak_material_summary` → Moliya brak bo'limi, oylik hisobot
`brak_xarajat` → sof foyda, liniya hisoboti) va buyurtma tan narxidan brakni ajratish
(`services._buyurtma_sarf_narxlari`) harakat SABABI MATNIGA (`reason LIKE "Brak%"`) bog'langan
edi. kech52 da O'LCHANDI (SQLite va PG): brak harakati sababi boshqa tilda yozilsa (masalan
"Брак — ...") hisobot jimgina 0 ga tushadi, sof foyda brak qadar oshadi; Omborxonadagi qo'lda
"Chiqim" izohi "Brak" bilan boshlansa — tasodifan brak xarajati bo'ladi (kichik harfli "brak" —
SQLite da ha, PG da yo'q). Shuningdek K52-1: ishlab chiqarish braki sababi 201 belgi → PG 500.

YECHIM: `InventoryMovement.is_brak` (standartsiz, NULL = eski harakat), `crud.log_movement`
har doim True / False yozadi (brak oynasi — `db.info["_brak_qaytarish_id"]` yoki
`db.info["_brak_harakat"]`), `services.deduct_raw_material_for_brak` — True; o'qish —
`crud.brak_harakati_sharti` (belgi; NULL — eski ta'rif); `main._migrate_brak_belgisi()` NULL
qatorlarni eski ta'rif bilan to'ldiradi; ishlab chiqarish braki sababi `_jurnal_sabab` bilan.

ASL KOD: bu test tuzatishdan OLDINGI kodga qarshi yiqilishi (qulamasligi) SHART — yangi nomlarga
murojaat `getattr` / `hasattr` bilan.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_brak_belgisi.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_brak_belgisi.py
"""
import os
import sys
import json
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "brak_belgisi_test"
_DB = os.path.join(tempfile.gettempdir(), "brak_belgisi_test.db")

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
    _db.add(Company(id=2, name="BB Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "BB_admin", "Parol123!", UserRole.ADMIN, "BB Admin", company_id=1)
    auth.create_user(_db, "BB_admin_b", "Parol123!", UserRole.ADMIN, "BB Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="BB Mijoz", project_name="BB loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="BB Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=BAZA_NARX["peno"], volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="BB Kley", unit="kg", stock_quantity=100_000,
                 price_per_unit=BAZA_NARX["kley"], category="Kimyo")
AKR = Inventory(company_id=1, item_name="BB Akril", unit="kg", stock_quantity=100_000,
                price_per_unit=BAZA_NARX["akr"], category="Kimyo")
_db.add_all([PRJ, PENO, KLEY, AKR])
_db.commit()
R1 = Recipe(company_id=1, name="BB R1", batch_size_kg=100.0)
R2 = Recipe(company_id=1, name="BB R2", batch_size_kg=100.0)
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


C, _s1 = _kir("BB_admin")
CB, _s2 = _kir("BB_admin_b")
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
    return {"name": nom or f"BB_D{_n[0]}", "category": "profil", "width": 20, "thickness": 10,
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
    it = profil(uzunlik, nom=f"BB_T{oid}")
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


def jurnal(oid, inv_id, turi, miqdor, reason="BB qo'lda harakat"):
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
# 13-band 3-qadam — yordamchilar
# ══════════════════════════════════════════════════════════════
from sqlalchemy import text as _sqltext              # noqa: E402
from models import FinishedProduct, StockSource, FinishedProductLoss   # noqa: E402
import database as _database                         # noqa: E402

BELGI_BOR = hasattr(InventoryMovement, "is_brak")


def belgi(h):
    return getattr(h, "is_brak", "YO'Q")


def hammasi():
    d = SessionLocal()
    try:
        return [(h.id, h.movement_type, h.reason, h.order_id, h.return_item_id, belgi(h), h.inventory_id)
                for h in d.query(InventoryMovement).order_by(InventoryMovement.id).all()]
    finally:
        d.close()


def eski_tarif(h):
    """Tuzatishdan OLDINGI brak ta'rifi (Python da; PG LIKE — katta-kichik harfga sezgir)."""
    rs = h[2] or ""
    boshi = rs.startswith("Brak") if PG_URL else rs.lower().startswith("brak")
    return h[4] is not None or boshi


def yangi_idlar(oldin):
    return [h for h in hammasi() if h[0] not in oldin]


def idset():
    return {h[0] for h in hammasi()}


def sabab_ozgartir(idlar, fn):
    d = SessionLocal()
    try:
        for i in idlar:
            h = d.get(InventoryMovement, i)
            h.reason = fn(h.reason or "")
        d.commit()
    finally:
        d.close()


def belgi_qoy(idlar, qiymat):
    if not BELGI_BOR:
        return
    d = SessionLocal()
    try:
        d.query(InventoryMovement).filter(InventoryMovement.id.in_(list(idlar))).update(
            {"is_brak": qiymat}, synchronize_session=False)
        d.commit()
    finally:
        d.close()


def jami_holat():
    """Brak xulosasi (butun JSON), oylik (brak, sof) va liniya hisoboti — solishtirish uchun."""
    h = hisobotlar()
    return (brak_xulosa(), h[1], h[2], h[3])


def fp_yarat(nom, stok_peno=None):
    d = SessionLocal()
    try:
        pid = PENO_ID
        if stok_peno is not None:
            p = Inventory(company_id=1, item_name=f"{nom[:40]} penoplast", unit="blok", stock_quantity=stok_peno,
                          price_per_unit=BAZA_NARX["peno"], volume_per_unit=1.0, is_penoplast=True,
                          category="Penoplast")
            d.add(p)
            d.commit()
            pid = p.id
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=True, quantity=100,
                             produced_quantity=100, unit="metr", unit_price=0, cost_price=0,
                             source=StockSource.PRODUCED, penoplast_id=pid, recipe_id=R1_ID,
                             unit_volume_m3=0.01, unit_loy_kg=0.5)
        d.add(fp)
        d.commit()
        return fp.id
    finally:
        d.close()


def ish_brak(fp_id, miqdor, klient=None):
    return req(klient or C, "post", "/api/finished/production-brak",
               json={"finished_product_id": fp_id, "brak_qty": miqdor})


# ══════════════════════════════════════════════════════════════
# A — yozuvchilar: har yangi harakatda belgi True / False (NULL emas)
# ══════════════════════════════════════════════════════════════
section("A — yozuvchilar")
check("A0 model: InventoryMovement.is_brak ustuni bor", BELGI_BOR)

o = idset()
O1 = yarat([profil(100)])
r = brak_yoz(O1)
check("A1 buyurtma detali braki (qoplamasiz) yozildi", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
y = [h for h in yangi_idlar(o) if h[3] == O1 and h[1] == "out"]
check("A1b brakka bog'langan penoplast harakati bitta, belgisi True",
      [h[5] for h in y if h[4] is not None] == [True], y)
check("A1c buyurtma yaratilgandagi sarf (bog'lanmagan) — False (NULL emas)",
      [h[5] for h in y if h[4] is None] == [False], y)

o = idset()
O2 = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=50)
_d = SessionLocal()
_d.get(Inventory, LOY_ID).stock_quantity = 2.0          # tayyor loy zaxirasi — loy qismi undan olinadi
_d.commit()
_d.close()
r = brak_yoz(O2, qoplama=True)
check("A2 qoplamali brak yozildi (penoplast + tayyor loy + ingredientlar)", r.status_code == 200,
      f"{r.status_code} {r.text[:200]}")
y = [h for h in yangi_idlar(o) if h[1] == "out" and h[4] is not None]
check("A2b brak harakatlari: penoplast, tayyor loy, kley, akril — hammasi True",
      {h[6] for h in y} == {PENO_ID, LOY_ID, KLEY_ID, AKR_ID} and all(h[5] is True for h in y), y)
y = [h for h in yangi_idlar(o) if h[4] is None]
check("A2c shu buyurtmaning yaratilishdagi sarfi (penoplast, loy) — hammasi False",
      len(y) >= 3 and all(h[5] is False for h in y), y)

o = idset()
r = tayyor(O2, 50)
check("A3 'Tayyor' (buyurtma sarfi) o'tdi", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
y = [h for h in yangi_idlar(o)]
check("A3b 'Tayyor' dan keyingi yangi harakatlar (bo'lsa) — hammasi False", all(h[5] is False for h in y), y)

o = idset()
FP1 = fp_yarat("BB mahsulot 1")
r = ish_brak(FP1, 2)
check("A4 ishlab chiqarish braki (qoplamali) yozildi", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
y = [h for h in yangi_idlar(o) if h[1] == "out"]
check("A4b penoplast + kley + akril harakatlari True, buyurtmasiz",
      {h[6] for h in y} == {PENO_ID, KLEY_ID, AKR_ID} and all(h[5] is True and h[3] is None for h in y), y)

FP2 = fp_yarat("BB mahsulot 2", stok_peno=0.001)
_d = SessionLocal()
_n0 = _d.query(InventoryMovement).count()
_n0l = _d.query(FinishedProductLoss).count()
try:
    with contextlib.redirect_stdout(_quiet):
        _natija = crud.record_finished_product_production_brak(_d, FP2, 5, company_id=1)
except Exception as e:                     # noqa: BLE001
    _natija = {"success": "ISTISNO", "message": f"{type(e).__name__}: {e}"}
check("A5 penoplast yetishmasa — rad (success False)", _natija.get("success") is False, _natija)
check("A5b rad etilgach sessiyada brak belgisi QOLMAYDI", "_brak_harakat" not in _d.info, dict(_d.info))
_d.rollback()
_iv = _d.get(Inventory, KLEY_ID)
crud.log_movement(_d, KLEY_ID, _iv.item_name, "out", 1.0, unit="kg", reason="BB sessiya davomi", company_id=1)
_d.commit()
_h = _d.query(InventoryMovement).order_by(InventoryMovement.id.desc()).first()
check("A5c o'sha sessiyadagi keyingi chiqim — brak EMAS (False)", belgi(_h) is False, belgi(_h))
check("A5d rad etilganda hech narsa yozilmadi (harakat +1 — faqat A5c, yo'qotish 0)",
      _d.query(InventoryMovement).count() == _n0 + 1 and _d.query(FinishedProductLoss).count() == _n0l)
_d.close()

_asl_loy = services.deduct_loy_ingredients


def _yiqil(*a, **k):
    raise RuntimeError("BB sun'iy xato")


services.deduct_loy_ingredients = _yiqil
_d = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        crud.record_finished_product_production_brak(_d, FP1, 1, company_id=1)
    _ist = None
except Exception as e:                     # noqa: BLE001
    _ist = f"{type(e).__name__}: {e}"
finally:
    services.deduct_loy_ingredients = _asl_loy
check("A6 ichki xato (loy) — istisno chaqiruvchiga chiqadi", _ist is not None and "BB sun'iy" in _ist, _ist)
check("A6b istisnoda ham sessiyada brak belgisi QOLMAYDI (finally)", "_brak_harakat" not in _d.info, dict(_d.info))
_d.rollback()
_d.close()

o = idset()
_d = SessionLocal()
_iv = _d.get(Inventory, KLEY_ID)
_ok = True
try:
    crud.log_movement(_d, KLEY_ID, _iv.item_name, "out", 1.0, unit="kg", reason="BB aniq True",
                      company_id=1, is_brak=True)
    crud.log_movement(_d, KLEY_ID, _iv.item_name, "out", 1.0, unit="kg", reason="Brak — BB aniq False",
                      company_id=1, is_brak=False)
    _d.info["_brak_harakat"] = True
    crud.log_movement(_d, KLEY_ID, _iv.item_name, "in", 1.0, unit="kg", reason="BB oynadagi kirim", company_id=1)
    crud.log_movement(_d, KLEY_ID, _iv.item_name, "out", 1.0, unit="kg", reason="BB oynadagi chiqim", company_id=1)
    _d.info.pop("_brak_harakat", None)
    _d.commit()
except TypeError as e:
    _ok = f"TypeError: {e}"
    _d.info.pop("_brak_harakat", None)
    _d.rollback()
_d.close()
y = yangi_idlar(o)
check("A7 log_movement(is_brak=...) — aniq qiymat matndan ustun; oynada kirim False, chiqim True",
      _ok is True and [h[5] for h in y] == [True, False, False, True], (_ok, y))

# 38-band QAROR (kech52, tugma bilan): "C — Izoh 'Brak' bilan boshlansa, brak hisoblansin (hozirgidek)".
_bj8 = brak_jami()
_sof8 = hisobotlar()[2]
o = idset()
r = req(C, "post", f"/api/inventory/{PENO_ID}/stock", json={"quantity_change": -1, "reason": "Brak: blok sindi"})
y = yangi_idlar(o)
check("A8 Omborxona qo'lda chiqim (izoh 'Brak: ...') — 200, belgi True (38-band qarori C)",
      r.status_code == 200 and len(y) == 1 and y[0][5] is True, (r.status_code, y))
check("A8a ... brak xulosasi 1 blok narxi qadar oshdi, sof foyda shuncha kamaydi",
      taxminan(brak_jami() - _bj8, BAZA_NARX["peno"], 1.0) and taxminan(_sof8 - hisobotlar()[2], BAZA_NARX["peno"], 1.0),
      (brak_jami(), _bj8, hisobotlar()[2], _sof8))
_qolda = []
for _iz, _q in (("brak blok sindi", -1), ("Blok sindi (Brak)", -1), (" Brak bo'shliq bilan", -1),
                ("Brak kirim", 1), (None, -1)):
    o = idset()
    r = req(C, "post", f"/api/inventory/{PENO_ID}/stock", json={"quantity_change": _q, "reason": _iz})
    y = yangi_idlar(o)
    _qolda.append((_iz, _q, r.status_code, [h[5] for h in y]))
check("A8b kichik harf / o'rtada / bo'shliq bilan / kirim / izohsiz — 200, belgi False (ikkala bazada bir xil)",
      all(t[2] == 200 and t[3] == [False] for t in _qolda), _qolda)

_d = SessionLocal()
_null = _d.query(InventoryMovement).filter(InventoryMovement.is_brak.is_(None)).count() if BELGI_BOR else -1
_d.close()
check("A9 yangi kod yozgan HECH bir harakatda belgi NULL emas", _null == 0, _null)

# ══════════════════════════════════════════════════════════════
# B — o'qish matnga bog'liq EMAS
# ══════════════════════════════════════════════════════════════
section("B — hisobot sabab matniga bog'liq emas")
nazorat = jami_holat()
_bj = brak_jami()
check("B0 brak xulosasi musbat (sezgirlik uchun)", _bj and _bj > 0, _bj)
# Brak harakatlari fikstura bo'yicha (belgidan emas — ASL kodda ham topilsin): brakka bog'langan
# yoki sababi "Brak" bilan boshlanadigan chiqimlar (A7 / A8 ning "Brak ..." matnli, brak EMAS qatorlari ham).
BRAK_IDS = [h[0] for h in hammasi() if h[1] == "out" and (h[4] is not None or (h[2] or "").startswith("Brak"))]
check("B0b brak harakatlari bor", len(BRAK_IDS) >= 8, len(BRAK_IDS))
_tan0 = tan(O2)
sabab_ozgartir(BRAK_IDS, lambda s: "Брак" + s[4:] if s.startswith("Brak") else "X " + s)
check("B1 brak sababi boshqa tilga o'girildi — xulosa (JSON) AYNAN", brak_xulosa() == nazorat[0], brak_xulosa()[:300])
_h = hisobotlar()
check("B1b oylik brak xarajati va sof foyda AYNAN", (_h[1], _h[2]) == (nazorat[1], nazorat[2]), (_h[1:3], nazorat[1:3]))
check("B1c liniya hisoboti AYNAN", _h[3] == nazorat[3])
check("B1d buyurtma tan narxi AYNAN (brak unga aralashmadi)", tan(O2) == _tan0, (tan(O2), _tan0))
sabab_ozgartir(BRAK_IDS, lambda s: "Brak" + s[4:] if s.startswith("Брак") else s[2:])
SARF = [h[0] for h in hammasi() if h[3] == O2 and h[4] is None and h[1] == "out"
        and not (h[2] or "").startswith("Brak")]
_asl_sarf = {h[0]: h[2] for h in hammasi() if h[0] in SARF}
sabab_ozgartir(SARF, lambda s: "Brak — BB soxta matn")
check("B2 brak BO'LMAGAN sarf sababi 'Brak — ...' bo'lsa ham xulosa AYNAN", brak_xulosa() == nazorat[0],
      brak_xulosa()[:300])
check("B2b ... buyurtma tan narxi AYNAN (sarf hisobdan chiqib ketmadi)", tan(O2) == _tan0, (tan(O2), _tan0))
narxlar(3)
check("B2c ... narxlar x3 da ham tan narx AYNAN (sarf muzlatilgan narxi bilan hisobda qoldi)", tan(O2) == _tan0,
      (tan(O2), _tan0))
narxlar(1)
_d = SessionLocal()
for _i, _s in _asl_sarf.items():
    _d.get(InventoryMovement, _i).reason = _s
_d.commit()
_d.close()
check("B3 matnlar qaytarildi — hammasi AYNAN", jami_holat() == nazorat)

# ══════════════════════════════════════════════════════════════
# C — eski (belgisiz, NULL) harakatlar: eski ta'rif bilan AYNAN
# ══════════════════════════════════════════════════════════════
section("C — belgisiz eski harakatlar")
o = idset()
jurnal(None, PENO_ID, "out", 0.5, reason="Brak (ishlab chiqarish) — BB eski (5 birlik)")
jurnal(None, KLEY_ID, "out", 3.0, reason="brak — BB kichik harf")
jurnal(None, PENO_ID, "in", 0.2, reason="Brak — BB kirim")
jurnal(None, AKR_ID, "out", 1.0, reason=None)
jurnal(O2, KLEY_ID, "out", 2.0, reason=None)
ESKI = yangi_idlar(o)
_d = SessionLocal()
_d.get(InventoryMovement, ESKI[4][0]).unit_cost = 100_000.0     # o'rtacha narxni siljitadi (sezgirlik)
_d.commit()
_d.close()
belgi_qoy([h[0] for h in ESKI], None)
belgi_qoy(BRAK_IDS + SARF, None)
_d = SessionLocal()
_d.query(InventoryMovement).filter(InventoryMovement.id == ESKI[1][0]).update(
    {"return_item_id": None}, synchronize_session=False)
_d.commit()
_d.close()


def kutilgan_brak(bari_eski=False):
    """Xulosa kutilgani: belgi TRUE yoki (NULL va eski ta'rif); `bari_eski` — hammasi eski ta'rif."""
    d = SessionLocal()
    k = 0.0
    try:
        for h in hammasi():
            brakmi = eski_tarif(h) if (bari_eski or h[5] is None) else (h[5] is True)
            if h[1] == "out" and brakmi and h[6]:
                hr = d.get(InventoryMovement, h[0])
                k += float(hr.quantity) * (float(hr.unit_cost) if hr.unit_cost is not None
                                           else float(d.get(Inventory, h[6]).price_per_unit or 0))
    finally:
        d.close()
    return round(k)


_kutilgan = kutilgan_brak()
check("C1 belgisiz qatorlar — xulosa eski ta'rif bilan AYNAN (kichik harf: SQLite ha, PG yo'q)",
      taxminan(brak_jami(), _kutilgan, 1.0), (brak_jami(), _kutilgan))
check("C2 sababsiz (NULL) belgisiz chiqim buyurtma tan narxiga KIRADI (not_ NULL tuzog'i yo'q)",
      tan(O2) != _tan0, (tan(O2), _tan0))
belgi_qoy([ESKI[4][0]], False)
check("C3 o'sha qatorga False — natija o'zgarmaydi", tan(O2) != _tan0)

# ══════════════════════════════════════════════════════════════
# D — migratsiya
# ══════════════════════════════════════════════════════════════
section("D — migratsiya")
_mig = getattr(main, "_migrate_brak_belgisi", None)
check("D0 main._migrate_brak_belgisi bor", callable(_mig))
_oldin_tan = tan(O2)
if BELGI_BOR:
    with _database.engine.connect() as _c:
        _c.execute(_sqltext("ALTER TABLE inventory_movements DROP COLUMN is_brak"))
        _c.commit()
    with contextlib.redirect_stdout(_quiet):
        _database.sync_missing_columns()
    with _database.engine.connect() as _c:
        _null = _c.execute(_sqltext("SELECT COUNT(*) FROM inventory_movements WHERE is_brak IS NULL")).scalar()
        _jami = _c.execute(_sqltext("SELECT COUNT(*) FROM inventory_movements")).scalar()
else:
    _null, _jami = -1, 0
check("D1 eski baza: ustun qayta qo'shildi, HAMMA qator NULL (standart FALSE yozilmadi)",
      _jami > 0 and _null == _jami, (_null, _jami))
_kut_eski = kutilgan_brak(bari_eski=True)
check("D1b migratsiyadan OLDIN (hammasi NULL): xulosa eski ta'rif bilan, tan narx AYNAN",
      taxminan(brak_jami(), _kut_eski, 1.0) and tan(O2) == _oldin_tan, (brak_jami(), _kut_eski, tan(O2), _oldin_tan))
_oldin_xulosa = brak_xulosa()
_xato, _chiq = migratsiya(_mig) if callable(_mig) else ("yo'q", "")
check("D2 migratsiya xatosiz, xabarda son", _xato is None and "brak belgisi" in _chiq, (_xato, _chiq))
_hamma = hammasi()
check("D2b NULL qolmadi", all(h[5] in (True, False) for h in _hamma), [h for h in _hamma if h[5] not in (True, False)][:5])
check("D2c TRUE aynan eski ta'rifga mos qatorlar (kirim ham — ikkala o'quvchi uchun eski xulq)",
      all((h[5] is True) == eski_tarif(h) for h in _hamma),
      [h for h in _hamma if (h[5] is True) != eski_tarif(h)][:5])
check("D2d xulosa va tan narx AYNAN", brak_xulosa() == _oldin_xulosa and tan(O2) == _oldin_tan)
_ist_true = [h[0] for h in _hamma if h[5] is False and h[1] == "out"][:1]
_ist_false = [h[0] for h in _hamma if h[5] is True and h[1] == "out"][:1]
belgi_qoy(_ist_true, True)
belgi_qoy(_ist_false, False)
_x2, _c2 = migratsiya(_mig) if callable(_mig) else ("yo'q", "")
check("D3 qayta ishga tushirish jim (NULL yo'q)", _x2 is None and _c2.strip() == "", (_x2, _c2))
_hamma2 = {h[0]: h[5] for h in hammasi()}
check("D3b yozilgan belgi almashtirilmaydi (matnga zid True / False saqlandi)",
      all(_hamma2.get(i) is True for i in _ist_true) and all(_hamma2.get(i) is False for i in _ist_false),
      (_ist_true, _ist_false))
belgi_qoy(_ist_true, False)
belgi_qoy(_ist_false, True)

# ══════════════════════════════════════════════════════════════
# E — K52-1: ishlab chiqarish braki sababi ≤ 200 belgi
# ══════════════════════════════════════════════════════════════
section("E — K52-1")
o = idset()
_bj0 = brak_jami()
FP3 = fp_yarat("BB " + "Ю" * 147)
r = ish_brak(FP3, 12.345)
check("E1 150 belgili nom, qoplama, 12.345 — 200 (PG da asl kod 500)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
y = [h for h in yangi_idlar(o) if h[1] == "out"]
check("E2 sabablar ≤ 200 va 'Brak (ishlab chiqarish) — ' bilan boshlanadi, belgisi True",
      len(y) == 3 and all(len(h[2]) <= 200 and h[2].startswith("Brak (ishlab chiqarish) — ") and h[5] is True for h in y),
      [(len(h[2] or ""), h[5]) for h in y])
_js = js(r) or {}
check("E3 xulosa aynan brak qiymati qadar oshdi", taxminan(brak_jami() - _bj0, float(_js.get("cost_amount") or -1), 1.0),
      (brak_jami(), _bj0, _js.get("cost_amount")))

# ══════════════════════════════════════════════════════════════
# T — korxona
# ══════════════════════════════════════════════════════════════
section("T — korxona")
_bj_a = brak_jami(1)
_d = SessionLocal()
_bp = Inventory(company_id=2, item_name="BB B penoplast", unit="blok", stock_quantity=100, price_per_unit=777.0,
                volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_d.add(_bp)
_d.commit()
if BELGI_BOR:
    crud.log_movement(_d, _bp.id, "BB B penoplast", "out", 3.0, unit="blok",
                      reason="BB B korxona brak", company_id=2, is_brak=True)
    _d.commit()
_d.close()
check("T1 B korxona braki A xulosasiga kirmaydi", brak_jami(1) == _bj_a, (brak_jami(1), _bj_a))
check("T2 B korxona xulosasida bor", (brak_jami(2) or 0) > 0 or not BELGI_BOR, brak_jami(2))

# ══════════════════════════════════════════════════════════════
# S — statik
# ══════════════════════════════════════════════════════════════
section("S — statik")
_crud_src = inspect.getsource(crud)
_srv_src = inspect.getsource(services)
_main_src = inspect.getsource(main)
_xul = inspect.getsource(crud.get_brak_material_summary)
check("S1 xulosa yagona shartni ishlatadi, matn qidiruvi yo'q",
      "brak_harakati_sharti(InventoryMovement)" in _xul and 'reason.like("Brak%")' not in _xul)
check("S2 kodda 'reason.like(\"Brak%\")' qolmadi (crud, services)",
      'reason.like("Brak%")' not in _crud_src and 'reason.like("Brak%")' not in _srv_src)
_sarf = inspect.getsource(services._buyurtma_sarf_narxlari)
check("S3 buyurtma sarfi yagona shartni inkor qiladi", "_not_sn(_crud_sn.brak_harakati_sharti(_IMv))" in _sarf)
_ded = inspect.getsource(services.deduct_raw_material_for_brak)
check("S4 services penoplast brak harakati is_brak=True yozadi", "is_brak=True" in _ded)
_lm = inspect.getsource(crud.log_movement)
check("S5 log_movement: is_brak parametri va yozuvga uzatiladi",
      "is_brak: Optional[bool] = None" in _lm and "is_brak=_brak" in _lm and 'db.info.get("_brak_harakat")' in _lm)
_pb = inspect.getsource(crud.record_finished_product_production_brak)
_i0 = _pb.find('db.info["_brak_harakat"] = True')
check("S6 ishlab chiqarish braki: belgi -> try -> yordamchi -> finally pop",
      _i0 != -1 and _i0 < _pb.find("try:", _i0) < _pb.find("_ishlab_chiqarish_braki_xomashyo(", _i0)
      < _pb.find("finally:", _i0) < _pb.find('db.info.pop("_brak_harakat", None)', _i0))
_yor = inspect.getsource(getattr(crud, "_ishlab_chiqarish_braki_xomashyo", lambda: None))
check("S7 K52-1: ikkala sabab _jurnal_sabab bilan",
      _yor.count("_jurnal_sabab(f\"Brak (ishlab chiqarish)") == 2)
_col = InventoryMovement.__table__.c.get("is_brak") if BELGI_BOR else None
check("S8 ustunda standart qiymat YO'Q (sync_missing_columns eski qatorlarni FALSE qilmasin)",
      _col is not None and _col.default is None and _col.server_default is None and _col.nullable)
check("S9 migratsiya 37-band migratsiyasidan KEYIN chaqiriladi",
      _main_src.find("\n_migrate_eski_brak_narxi()\n") != -1
      and _main_src.find("\n_migrate_eski_brak_narxi()\n") < _main_src.find("\n_migrate_brak_belgisi()\n"))
_us = inspect.getsource(crud.update_stock)
check("S11 qo'lda chiqim: belgi faqat chiqimda va izoh QOLDA_BRAK_BOSHI ('Brak') bilan boshlansa (38-band C)",
      getattr(crud, "QOLDA_BRAK_BOSHI", None) == "Brak"
      and 'is_brak=(qc < 0 and str(notes or "").startswith(QOLDA_BRAK_BOSHI))' in _us)
_sh = str(crud.brak_harakati_sharti(InventoryMovement)) if hasattr(crud, "brak_harakati_sharti") else ""
check("S10 yagona shart: belgi TRUE yoki (NULL va (bog'langan yoki sababi bor va LIKE))",
      "is_brak IS true" in _sh.replace("IS 1", "IS true") and "is_brak IS NULL" in _sh
      and "return_item_id IS NOT NULL" in _sh and "reason IS NOT NULL" in _sh and "LIKE" in _sh, _sh)

print()
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
