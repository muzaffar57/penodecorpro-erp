#!/usr/bin/env python3
"""
test_tan_narx_muzlash.py — K47-1 (5-bo'lim 32-band) darvozasi (kech48, 2026-09-24).

NIMA UCHUN KERAK (O'LCHANGAN)
-----------------------------
  * JONLI (kech47): penoplast 276 narxi x2 qilinganda 2026-09 sof foydasi
    −6 119 924.62 → −17 503 066.90 ga siljidi; ~10.64 mln — tayyor buyurtmalar
    tan narxi. Sabab: `services.calculate_order_profit` penoplast
    (`inv_item.price_per_unit / volume_per_unit`), qoplama va "Loy sotish"
    ingredientlarini (`ing.inventory.price_per_unit`) JORIY narx bilan
    hisoblardi — narx o'zgarsa O'TGAN buyurtmalar foydasi, oylik hisobot
    (`get_monthly_report` `ishlab_chiqarish_xarajat` → sof foyda), liniya
    hisoboti (`calculate_split_profit_report`), kunlik ko'rinish va buyurtma
    kartasidagi "Foyda hisoblash" orqaga qarab o'zgarardi.
  * LOKAL (`work/probe47.py`, asl kod `953ea84`): narxlar x3 → tan narx
    992 000 → 2 976 000; tahrirda x2 narxda qo'shilgan 0.5 blok → butun
    1.5 blok x2 narxda (1 500 000, to'g'risi 1 000 000).

FOYDALANUVCHI QARORI (kech47, tugma): "Ishlatilgan paytdagi narxda muzlatilsin".

YECHIM (texnik — Claude): `services._buyurtma_sarf_narxlari` — shu buyurtmaning
ombor harakatlari (`order_id`, korxona), brakdan tashqari, `id` tartibida,
o'rtacha tannarx usulida (chiqim — `unit_cost`, u yo'q eski harakat — joriy
narx; kirim — o'sha paytdagi o'rtacha narxda ayiriladi). `calculate_order_profit`
hajm mantig'i O'ZGARMAGAN — faqat NARX manbai. Harakati yo'q material — joriy
narx (avvalgi xulq). Dona detalning zaxira hajm yo'li (`_item_volume_m3`
`penoplast_narxi`) ham shu narxni oladi — aks holda hajm joriy, narx muzlatilgan
bo'lib tan narx suzardi.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_tan_narx_muzlash.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tan_narx_muzlash.py
"""
import os
import sys
import json
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tan_narx_test"
_DB = os.path.join(tempfile.gettempdir(), "tan_narx_test.db")

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

from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Inventory, InventoryMovement,
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
    _db.add(Company(id=2, name="TN Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TN_admin", "Parol123!", UserRole.ADMIN, "TN Admin", company_id=1)
    auth.create_user(_db, "TN_admin_b", "Parol123!", UserRole.ADMIN, "TN Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="TN Mijoz", project_name="TN loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="TN Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=BAZA_NARX["peno"], volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TN Kley", unit="kg", stock_quantity=100_000,
                 price_per_unit=BAZA_NARX["kley"], category="Kimyo")
AKR = Inventory(company_id=1, item_name="TN Akril", unit="kg", stock_quantity=100_000,
                price_per_unit=BAZA_NARX["akr"], category="Kimyo")
_db.add_all([PRJ, PENO, KLEY, AKR])
_db.commit()
R1 = Recipe(company_id=1, name="TN R1", batch_size_kg=100.0)
R2 = Recipe(company_id=1, name="TN R2", batch_size_kg=100.0)
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


C, _s1 = _kir("TN_admin")
CB, _s2 = _kir("TN_admin_b")
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
    return {"name": nom or f"TN_D{_n[0]}", "category": "profil", "width": 20, "thickness": 10,
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
    it = profil(uzunlik, nom=f"TN_T{oid}")
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


def jurnal(oid, inv_id, turi, miqdor, reason="TN qo'lda harakat"):
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
# A — asosiy: penoplast + qoplama + loy sotish; narxlar x3
# ══════════════════════════════════════════════════════════════
section("A — narxlar o'zgarsa buyurtma tan narxi va hisobotlar O'ZGARMAYDI")
A = yarat([profil(100, qoplama=True),
           {"name": "TN loy sotish", "category": "loy_sotish", "quantity": 30, "unit_price": 20_000,
            "is_coated": False, "recipe_id": R2_ID}], recipe_id=R1_ID, loy_kg=50)
r = tayyor(A, 60)
check("A0 buyurtma 'Tayyor' (haqiqiy loy 60 kg, reja 50)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
_hh = harakatlar(A)
check("A0b hamma chiqim harakatida unit_cost bor (zip 47)",
      _hh and all(h.unit_cost is not None for h in _hh if h.movement_type == "out"),
      [(h.inventory_id, h.movement_type, h.unit_cost) for h in _hh])
t1, b1, v1 = foyda(A)
check("A1 x1: tan narx 992 000 (penoplast 500 000 + loy sotish 180 000 + qoplama 312 000)",
      taxminan(t1, 992_000), f"{t1} {b1}")
api1 = js(req(C, "get", f"/api/orders/{A}/profit")) or {}
h1 = hisobotlar()
narxlar(3)
t3, b3, v3 = foyda(A)
check("A2 x3: tan narx O'ZGARMADI (asl kodda 2 976 000)", taxminan(t3, t1), f"{t1} -> {t3}")
check("A3 x3: breakdown qatorlari (nom + summa) AYNAN", b3 == b1, f"{b1} -> {b3}")
check("A3b x3: volume_m3 AYNAN", v3 == v1, f"{v1} -> {v3}")
check("A3c penoplast qatori 500 000, loy sotish 180 000, qoplama 312 000",
      taxminan(qator(A, "TN Penoplast"), 500_000) and taxminan(qator(A, "TN loy sotish"), 180_000)
      and taxminan(qator(A, "Qoplama"), 312_000), b3)
api3 = js(req(C, "get", f"/api/orders/{A}/profit")) or {}
check("A4 API /api/orders/{id}/profit: tan narx va foyda AYNAN",
      api1.get("tan_narxi") is not None and taxminan(api3.get("tan_narxi"), api1.get("tan_narxi"))
      and taxminan(api3.get("foyda"), api1.get("foyda")), f"{api1.get('tan_narxi')} -> {api3.get('tan_narxi')}")
h3 = hisobotlar()
check("A5 oylik hisobot: ishlab chiqarish xarajati AYNAN (992 000)",
      taxminan(h3[0], h1[0]) and taxminan(h1[0], 992_000), f"{h1[0]} -> {h3[0]}")
check("A6 oylik hisobot: sof foyda AYNAN", h1[1] is not None and taxminan(h3[1], h1[1]), f"{h1[1]} -> {h3[1]}")
check("A7 liniya hisoboti (calculate_split_profit_report) AYNAN", h1[2] is not None and h3[2] == h1[2],
      f"{str(h1[2])[:150]} || {str(h3[2])[:150]}")
check("A8 kunlik moliya ko'rinishi AYNAN", h1[3] is not None and h3[3] == h1[3],
      f"{str(h1[3])[:150]} || {str(h3[3])[:150]}")
narxlar(1)

# ══════════════════════════════════════════════════════════════
# B — tahrir: o'rtacha tannarx (kirim o'rtacha narxda ayiriladi)
# ══════════════════════════════════════════════════════════════
section("B — tahrirda qo'shilgan / kamaytirilgan miqdor")
B = yarat([profil(100)])
BI = detal_id(B)
check("B1 x1: 1 blok → 500 000", taxminan(tan(B), 500_000), tan(B))
narxlar(2)
r = tahrir_uzunlik(B, BI, 150)
check("B2a tahrir 150 m (x2 narxda +0.5 blok) → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
check("B2 1.0 × 500 000 + 0.5 × 1 000 000 = 1 000 000 (asl kodda 1 500 000)", taxminan(tan(B), 1_000_000), tan(B))
narxlar(3)
check("B3 x3 da ham 1 000 000", taxminan(tan(B), 1_000_000), tan(B))
r = tahrir_uzunlik(B, BI, 50)
check("B4a tahrir 50 m (−1.0 blok kirim) → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
check("B4 qolgan 0.5 blok o'rtacha 666 666.67 da → 333 333.33", taxminan(tan(B), 1_000_000 / 3), tan(B))
narxlar(4)
r = tahrir_uzunlik(B, BI, 100)
check("B5a tahrir 100 m (x4 narxda +0.5 blok) → 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
check("B5 (0.5 × 666 666.67 + 0.5 × 2 000 000) = 1 333 333.33 (faqat chiqimlar o'rtachasi 1 000 000 berardi)",
      taxminan(tan(B), 4_000_000 / 3), tan(B))
narxlar(1)
check("B6 x1 ga qaytganda ham 1 333 333.33", taxminan(tan(B), 4_000_000 / 3), tan(B))
_bk = [h for h in harakatlar(B) if h.movement_type == "in"]
check("B7 kamaytirish kirim harakatida unit_cost NULL (o'rtachada narx sifatida ishlatilmaydi)",
      _bk and all(h.unit_cost is None for h in _bk), [(h.quantity, h.unit_cost) for h in _bk])

# ══════════════════════════════════════════════════════════════
# C — eski buyurtmalar (narx yozilmagan) — JORIY narx (avvalgi xulq)
# ══════════════════════════════════════════════════════════════
section("C — narxi yozilmagan eski harakatlar / harakatsiz buyurtma")
Cq = yarat([profil(100)])
_d = SessionLocal()
_d.query(InventoryMovement).filter(InventoryMovement.order_id == Cq).update({"unit_cost": None}, synchronize_session=False)
_d.commit()
_d.close()
check("C1 unit_cost NULL, x1 → 500 000", taxminan(tan(Cq), 500_000), tan(Cq))
narxlar(2)
check("C2 unit_cost NULL, x2 → 1 000 000 (joriy — eski narx noma'lum)", taxminan(tan(Cq), 1_000_000), tan(Cq))
narxlar(1)
Cy = yarat([profil(100)])
_d = SessionLocal()
_d.query(InventoryMovement).filter(InventoryMovement.order_id == Cy).delete(synchronize_session=False)
_d.commit()
_d.close()
narxlar(3)
check("C3 harakatsiz buyurtma, x3 → 1 500 000 (joriy)", taxminan(tan(Cy), 1_500_000), tan(Cy))
narxlar(1)
Cm = yarat([profil(100)])
CmI = detal_id(Cm)
narxlar(2)
tahrir_uzunlik(Cm, CmI, 150)
_d = SessionLocal()
_birinchi = _d.query(InventoryMovement).filter(InventoryMovement.order_id == Cm).order_by(InventoryMovement.id).first()
_birinchi.unit_cost = None
_d.commit()
_d.close()
narxlar(3)
check("C4 aralash: 1.0 blok narxsiz (joriy 1 500 000) + 0.5 blok 1 000 000 → 2 000 000",
      taxminan(tan(Cm), 2_000_000), tan(Cm))
narxlar(1)

# ══════════════════════════════════════════════════════════════
# D — brak harakatlari buyurtma narxiga aralashmaydi
# ══════════════════════════════════════════════════════════════
section("D — brak harakatlari chiqarib tashlanadi")
D = yarat([profil(100)])
check("D0 x1: 500 000", taxminan(tan(D), 500_000), tan(D))
narxlar(2)
_d = SessionLocal()
_di = _d.query(OrderItem).filter(OrderItem.order_id == D).first()
_dnom = _di.name
_d.close()
r = req(C, "post", "/api/returns", json={"order_id": D, "order_item_id": detal_id(D), "item_name": _dnom,
                                          "quantity": 10, "unit": "metr", "reason": "Brak", "refund_amount": 0,
                                          "to_stock": False, "coating_applied": False})
_brak_id = (js(r) or {}).get("id") if r.status_code == 200 else None
check("D1a brak 10 m yozildi (x2 narxda 0.1 blok)", _brak_id, f"{r.status_code} {r.text[:200]}")
_bh = [h for h in harakatlar(D) if (h.reason or "").startswith("Brak")]
check("D1b brak harakati buyurtmaga bog'langan (order_id), narxi 1 000 000",
      len(_bh) == 1 and taxminan(_bh[0].unit_cost, 1_000_000), [(h.quantity, h.unit_cost, h.return_item_id) for h in _bh])
check("D1 buyurtma tan narxi 500 000 (brak kirmaydi; kirsa ~545 454.55)", taxminan(tan(D), 500_000), tan(D))
_d = SessionLocal()
_bm = _d.query(InventoryMovement).filter(InventoryMovement.order_id == D, InventoryMovement.reason.like("Brak%")).first()
_asl_sabab = _bm.reason if _bm else None
if _bm:
    _bm.reason = "TN boshqa sabab"
    _d.commit()
_d.close()
check("D4 brak yozuviga bog'langan harakat sababi 'Brak' bilan boshlanmasa ham kirmaydi → 500 000",
      _bm is not None and taxminan(tan(D), 500_000), tan(D))
_d = SessionLocal()
_d.query(InventoryMovement).filter(InventoryMovement.order_id == D,
                                   InventoryMovement.reason == "TN boshqa sabab").update({"reason": _asl_sabab},
                                                                                        synchronize_session=False)
_d.commit()
_d.close()
_d = SessionLocal()
_d.query(InventoryMovement).filter(InventoryMovement.order_id == D,
                                   InventoryMovement.reason.like("Brak%")).update({"return_item_id": None},
                                                                                 synchronize_session=False)
_d.commit()
_d.close()
check("D2 eski brak (bog'lamsiz, sabab 'Brak …') ham kirmaydi → 500 000", taxminan(tan(D), 500_000), tan(D))
_d = SessionLocal()
try:
    _bx = crud.get_brak_material_summary(_d, company_id=1)
finally:
    _d.close()
check("D3 brak xulosasi o'z narxida (0.1 × 1 000 000 = 100 000)", taxminan(_bx.get("total_value"), 100_000, 1),
      _bx.get("total_value"))
narxlar(1)

# ══════════════════════════════════════════════════════════════
# E — qoplama: tayyor loy zaxirasidan olingan qism
# ══════════════════════════════════════════════════════════════
section("E — tayyor loy zaxirasi")


def loy_zaxira(kg):
    d = SessionLocal()
    try:
        d.get(Inventory, LOY_ID).stock_quantity = kg
        d.commit()
    finally:
        d.close()


loy_zaxira(20)
E = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=50)
r = tayyor(E, 50)
check("E0 'Tayyor' (50 kg: 20 zaxiradan, 30 yangi)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
check("E1 x1: 500 000 + 50 × 5 200 = 760 000", taxminan(tan(E), 760_000), tan(E))
narxlar(3)
check("E2 x3: 760 000 — zaxira qismi ham o'sha paytdagi (yangi qism) narxda", taxminan(tan(E), 760_000), tan(E))
narxlar(1)
loy_zaxira(100)
F = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=50)
r = tayyor(F, 50)
check("E3a 'Tayyor' (50 kg — hammasi zaxiradan)", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
_fi = [h for h in harakatlar(F) if h.inventory_id in (KLEY_ID, AKR_ID)]
check("E3b ingredient harakati YO'Q (hammasi tayyor loydan)", not _fi, [(h.inventory_id, h.quantity) for h in _fi])
narxlar(3)
check("E3 x3: penoplast muzlatilgan 500 000 + qoplama JORIY 50 × 15 600 = 780 000 → 1 280 000 (narx noma'lum)",
      taxminan(tan(F), 1_280_000), tan(F))
narxlar(1)
loy_zaxira(0)

# ══════════════════════════════════════════════════════════════
# F — loy xomashyosi kirimi (qaytish) va qayta chiqim — o'rtacha
# ══════════════════════════════════════════════════════════════
section("F — loy ingredientlari: kirim / qayta chiqim")
G = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=50)
_d = SessionLocal()
_d.get(Order, G).actual_loy_kg = 50.0
_d.commit()
_d.close()
check("F0 x1: 500 000 + 50 × 5 200 = 760 000", taxminan(tan(G), 760_000), tan(G))
jurnal(G, KLEY_ID, "in", 10, reason="Buyurtma TN bekor qilindi (loy qaytarildi)")
narxlar(3)
jurnal(G, KLEY_ID, "out", 10, reason="Buyurtma TN (loy)")
check("F1 kley: 30@2 000 → −10 → +10@6 000 → o'rtacha 3 333.33; qoplama 50 × (0.6 × 3 333.33 + 0.4 × 10 000) = 300 000",
      taxminan(qator(G, "Qoplama"), 300_000), foyda(G)[1])
check("F2 jami 800 000", taxminan(tan(G), 800_000), tan(G))
narxlar(1)

# ══════════════════════════════════════════════════════════════
# G — dona detallar
# ══════════════════════════════════════════════════════════════
section("G — dona: 1 m³ narxi bilan va zaxira yo'l (narx penoplastdan)")
H = yarat([{"name": "TN dona m3", "category": "dona", "quantity": 5, "unit_price": 100_000,
            "price_per_m3": 1_000_000, "is_coated": False, "penoplast_id": PENO_ID}])
check("G1 x1: 0.5 m³ → 250 000", taxminan(tan(H), 250_000), tan(H))
narxlar(3)
check("G2 x3: 250 000", taxminan(tan(H), 250_000), tan(H))
narxlar(1)
Hz = yarat([{"name": "TN dona zaxira", "category": "dona", "quantity": 5, "unit_price": 100_000,
             "is_coated": False, "penoplast_id": PENO_ID}])
_hz = [h for h in harakatlar(Hz) if h.inventory_id == PENO_ID]
check("G3a zaxira yo'l: 500 000 / 500 000 = 1.0 blok yechilgan", len(_hz) == 1 and taxminan(_hz[0].quantity, 1.0, 1e-9),
      [(h.quantity, h.unit_cost) for h in _hz])
check("G3 x1: 500 000", taxminan(tan(Hz), 500_000), tan(Hz))
narxlar(3)
check("G4 x3: 500 000 (hajm ham muzlatilgan narxdan; aks holda 166 666.67)", taxminan(tan(Hz), 500_000), tan(Hz))
check("G5 x3: volume_m3 1.0 (yechilgan hajm)", foyda(Hz)[2] == 1.0, foyda(Hz)[2])
narxlar(1)

# ══════════════════════════════════════════════════════════════
# H — korxona: begona korxona harakati hisobga olinmaydi
# ══════════════════════════════════════════════════════════════
section("H — korxona chegarasi")
K = yarat([profil(100)])
_d = SessionLocal()
try:
    _d.execute(text("INSERT INTO inventory_movements (company_id, inventory_id, item_name, movement_type, quantity, "
                    "unit, reason, order_id, unit_cost, created_at) VALUES (2, :i, 'TN soxta', 'out', 1.0, 'blok', "
                    "'TN soxta', :o, 9000000, :t)"), {"i": PENO_ID, "o": K, "t": _dt.utcnow()})
    _d.commit()
    _soxta = True
except Exception as e:                     # noqa: BLE001
    _d.rollback()
    _soxta = f"{type(e).__name__}: {e}"
finally:
    _d.close()
check("H0 begona korxona (2) harakati yozildi (xom SQL)", _soxta is True, _soxta)
check("H1 tan narx 500 000 (begona harakat kirmaydi; kirsa 4 750 000)", taxminan(tan(K), 500_000), tan(K))
r = req(CB, "get", f"/api/orders/{K}/profit")
check("H2 begona korxona foydani ko'rmaydi (404)", r.status_code == 404, f"{r.status_code} {r.text[:120]}")

# ══════════════════════════════════════════════════════════════
# I — ishlatilgan paytda narx 0 edi
# ══════════════════════════════════════════════════════════════
section("I — narx belgilanmagan paytda ishlatilgan")
_d = SessionLocal()
_d.get(Inventory, PENO_ID).price_per_unit = 0
_d.commit()
_d.close()
I = yarat([profil(100)])
narxlar(1)
check("I1 keyin narx 500 000 qo'yildi — tan narx 0 (ishlatilgan paytda 0 edi; brak 2-qadam bilan bir qoida)",
      taxminan(tan(I), 0), foyda(I))
check("I2 volume_m3 0 (narxsiz penoplast avvalgidek hisobdan tashqari)", foyda(I)[2] == 0, foyda(I)[2])

# ══════════════════════════════════════════════════════════════
# J — jurnal chekkalari
# ══════════════════════════════════════════════════════════════
section("J — jurnal chekka holatlari")
J = yarat([profil(100)])
narxlar(2)
_d = SessionLocal()
crud.log_movement(_d, PENO_ID, "TN Penoplast", "out", 1.0, unit="blok", reason=None, order_id=J, company_id=1)
_d.commit()
_jn = _d.query(InventoryMovement).filter(InventoryMovement.order_id == J, InventoryMovement.reason.is_(None)).count()
_d.close()
check("J1a sababsiz (reason NULL) chiqim yozildi", _jn == 1, _jn)
check("J1 sababsiz chiqim hisobga olinadi: (500 000 + 1 000 000) / 2 = 750 000", taxminan(tan(J), 750_000), tan(J))
narxlar(1)
Q = yarat([profil(100)])
jurnal(Q, PENO_ID, "in", 1.0, reason="TN hammasi qaytdi")
narxlar(3)
check("J2 hammasi qaytgan (jurnal 0) — oxirgi ma'lum narx 500 000 (joriy 1 500 000 emas)", taxminan(tan(Q), 500_000), tan(Q))
narxlar(1)
W = yarat([profil(100)], qoralama=True)
check("J3a qoralama — harakat yo'q", not harakatlar(W), len(harakatlar(W)))
jurnal(W, PENO_ID, "in", 0.5, reason="TN chiqimsiz kirim")
narxlar(2)
jurnal(W, PENO_ID, "out", 1.0, reason="TN chiqim")
narxlar(3)
check("J3 chiqimdan oldingi kirim e'tiborsiz: 1.0 × 1 000 000 = 1 000 000", taxminan(tan(W), 1_000_000), tan(W))
narxlar(1)
Z = yarat([profil(100)])
jurnal(Z, PENO_ID, "in", 1.5, reason="TN ortiqcha kirim")
narxlar(2)
jurnal(Z, PENO_ID, "out", 1.0, reason="TN qayta chiqim")
check("J4 ushlanganidan ko'p kirim (1.5 > 1.0) nolga tushiradi, keyingi chiqim 1 000 000 → 1 000 000",
      taxminan(tan(Z), 1_000_000), tan(Z))
narxlar(1)

# ══════════════════════════════════════════════════════════════
# S — statik
# ══════════════════════════════════════════════════════════════
section("S — statik")
_yord = getattr(services, "_buyurtma_sarf_narxlari", None)
check("S1 services._buyurtma_sarf_narxlari bor", callable(_yord))
try:
    _cop = inspect.getsource(services.calculate_order_profit)
except Exception as e:                     # noqa: BLE001
    _cop = ""
    print("  (manba o'qilmadi)", e)
check("S2 calculate_order_profit yordamchini chaqiradi", "_buyurtma_sarf_narxlari(db, order)" in _cop)
check("S3 penoplast narxi joriy narxdan emas (`float(inv_item.price_per_unit)` yo'q)",
      _cop and "float(inv_item.price_per_unit)" not in _cop)
check("S4 ingredient narxi joriy narxdan emas (`float(ing.inventory.price_per_unit)` yo'q)",
      _cop and "float(ing.inventory.price_per_unit)" not in _cop)
check("S5 dona zaxira yo'liga muzlatilgan narx beriladi", "penoplast_narxi=_sarf_narx.get(" in _cop)
try:
    _ys = inspect.getsource(_yord) if callable(_yord) else ""
except Exception:                          # noqa: BLE001
    _ys = ""
try:
    _bs = inspect.getsource(crud.get_brak_material_summary)
except Exception:                          # noqa: BLE001
    _bs = ""
check("S6 yordamchi brakni brak xulosasi bilan AYNAN bir shartda chiqaradi (reason.like(\"Brak%\"))",
      'reason.like("Brak%")' in _ys and 'reason.like("Brak%")' in _bs and "return_item_id.is_(None)" in _ys)
check("S7 yordamchi korxona filtri bilan", "_IMv.company_id == _cid_sn" in _ys and "Inventory.company_id == _cid_sn" in _ys)

print()
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   -", f)
sys.exit(0 if FAIL == 0 else 1)
