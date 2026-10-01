#!/usr/bin/env python3
"""
test_zaxira_loy_narx.py — kech107, 36-band darvozasi: TAYYOR LOY ZAXIRASIDAN olingan qoplama narxi.

Egasining kech47 qarori ("Ishlatilgan paytdagi narxda muzlatilsin", 32-band) — QAYTA SO'RALMAYDI.
O'LCHANGAN (asl = staging `061e082`, `work/probe107c.py`, SQLite = PG; retsept R1: 1 kg = 5 200 so'm):
  * qoplama loyi TO'LIQ zaxiradan (50 kg) — tan narx 760 000; narxlar x3 bo'lgach 1 280 000 (qoplama JORIY narxda);
  * zaxira harakatining `unit_cost` i 0.0 (tayyor loy pozitsiyasi narxsiz);
  * brak zaxirali loyni 0 so'mga baholardi — yozuv summasi 38 000, brak harakatlari (Moliya "Brak") 25 000.
YECHIM: zaxiradan olishda harakat narxi — OLINGAN paytdagi retsept tannarxi; buyurtma qoplamasining zaxira qismi — o'sha
narxda, qolgani avvalgidek; eski (narxi 0 / NULL) zaxira harakati — avvalgi qoida (taxmin qilinmaydi).

BO'LIMLAR
  A — to'liq zaxiradan: harakat narxi, tan narx x1 = x3, qoplama qatori matni
  B — qisman zaxira (20 + 30): ikkala qism muzlatilgan
  C — zaxira olingan paytda narx boshqa (x2): zaxira qismi x2 da, yangi qism — o'z harakatlari narxida
  D — ishlatilgan loy zaxiradan olinganidan KAM: zaxira qismi ishlatilgan bilan cheklanadi
  E — eski zaxira harakati (narxi 0): avvalgi qoida AYNAN
  F — brak zaxirali buyurtmada: brak harakatlari qiymati = yozuv summasi (Moliya "Brak" loyni ham oladi)
  G — izolyatsiya: B korxonada shu nomli "Tayyor loy" pozitsiyasi A ga ta'sir qilmaydi
  H — pozitsiyaga egasi narx qo'ygan bo'lsa — o'sha narx (avvalgidek)
  S — statik

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_zaxira_loy_narx.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_zaxira_loy_narx.py
Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "zaxira_loy_narx_test"
_DB = os.path.join(tempfile.gettempdir(), "zaxira_loy_narx_test.db")

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
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, services                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Inventory, InventoryMovement, Recipe, RecipeIngredient, ReturnItem,
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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:500]}")


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
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona). Retsept R1: 60 kg kley (2 000) + 40 kg akril (10 000) / 100 kg
# → 1 kg = 1 200 + 4 000 = 5 200 so'm.
# ══════════════════════════════════════════════════════════════
BAZA = {"peno": 500_000, "kley": 2_000, "akr": 10_000}
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="ZL Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "ZL_admin", "Parol123!", UserRole.ADMIN, "ZL Admin", company_id=1)
PRJ = Project(company_id=1, client_name="ZL Mijoz", project_name="ZL loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="ZL Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=BAZA["peno"], volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="ZL Kley", unit="kg", stock_quantity=100_000, price_per_unit=BAZA["kley"], category="Kimyo")
AKR = Inventory(company_id=1, item_name="ZL Akril", unit="kg", stock_quantity=100_000, price_per_unit=BAZA["akr"], category="Kimyo")
_db.add_all([PRJ, PENO, KLEY, AKR])
_db.commit()
R1 = Recipe(company_id=1, name="ZL R1", batch_size_kg=100.0)
_db.add(R1)
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0)])
_db.commit()
PRJ_ID, PENO_ID, KLEY_ID, AKR_ID, R1_ID = PRJ.id, PENO.id, KLEY.id, AKR.id, R1.id
# B korxonada AYNAN shu nomli "Tayyor loy (ZL R1)" pozitsiyasi (begona, A nikidan OLDIN — kichik id) — A ning hisobiga
# aralashmasligi kerak (korxona sharti bo'lmasa birinchi topilgan — shu bo'lardi).
_db.add(Inventory(company_id=2, item_name="Tayyor loy (ZL R1)", unit="kg", stock_quantity=500, price_per_unit=None))
_db.commit()
with contextlib.redirect_stdout(_quiet):
    _loy = services.get_or_create_loy_stock(_db, _db.get(Recipe, R1_ID))
_loy.stock_quantity = 0.0
_db.commit()
LOY_ID = _loy.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_s1 = req(C, "post", "/login", data={"username": "ZL_admin", "password": "Parol123!"}, follow_redirects=False).status_code
if _s1 != 302:
    print(f"LOGIN BO'LMADI: {_s1}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def narxlar(k):
    d = SessionLocal()
    try:
        d.get(Inventory, PENO_ID).price_per_unit = BAZA["peno"] * k
        d.get(Inventory, KLEY_ID).price_per_unit = BAZA["kley"] * k
        d.get(Inventory, AKR_ID).price_per_unit = BAZA["akr"] * k
        d.commit()
    finally:
        d.close()


def loy_zaxira(kg):
    d = SessionLocal()
    try:
        d.get(Inventory, LOY_ID).stock_quantity = kg
        d.commit()
    finally:
        d.close()


def profil(uzunlik, qoplama=True):
    _n[0] += 1
    return {"name": f"ZL_D{_n[0]}", "category": "profil", "width": 20, "thickness": 10,
            "length": uzunlik, "quantity": 10, "unit_price": 50_000, "is_coated": bool(qoplama),
            "penoplast_id": PENO_ID, **({"recipe_id": R1_ID} if qoplama else {})}


def yarat(loy_kg):
    r = req(C, "post", "/api/orders", json={"project_id": PRJ_ID, "order_type": "product", "items": [profil(100)],
                                            "recipe_id": R1_ID, "loy_kg": loy_kg}, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    if not oid:
        raise RuntimeError(f"buyurtma yaratilmadi: {r.status_code} {r.text[:300]}")
    return oid


def tayyor(oid, loy):
    return req(C, "post", f"/api/orders/{oid}/ready", params={"loy_kg": str(loy)})


def foyda(oid):
    d = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            p = services.calculate_order_profit(d, oid, company_id=1)
        return (round(float(p.get("tan_narxi", 0)), 2), [(b["nomi"], round(float(b["summa"]), 2)) for b in p.get("breakdown", [])])
    except Exception as e:                 # noqa: BLE001
        return (f"XATO {type(e).__name__}: {e}", [])
    finally:
        d.close()


def qoplama(oid):
    for n, s in foyda(oid)[1]:
        if n.startswith("Qoplama"):
            return n, s
    return None, None


def zaxira_harakatlari(oid):
    d = SessionLocal()
    try:
        return [(h.movement_type, round(float(h.quantity), 4), None if h.unit_cost is None else round(float(h.unit_cost), 2))
                for h in d.query(InventoryMovement).filter(InventoryMovement.order_id == oid,
                                                           InventoryMovement.inventory_id == LOY_ID)
                .order_by(InventoryMovement.id).all()]
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════
section("A — to'liq zaxiradan (50 kg)")
narxlar(1)
loy_zaxira(100)
A = yarat(50)
r = tayyor(A, 50)
check("A0 'Tayyor' 200", r.status_code == 200, (r.status_code, r.text[:200]))
check("A1 zaxira harakati: 50 kg, narx — olingan paytdagi retsept tannarxi 5 200 (asl: 0.0)",
      zaxira_harakatlari(A) == [("out", 50.0, 5200.0)], zaxira_harakatlari(A))
t1 = foyda(A)[0]
check("A2 x1: 500 000 + 50 × 5 200 = 760 000", taxminan(t1, 760_000), t1)
narxlar(3)
t3 = foyda(A)[0]
n3, s3 = qoplama(A)
check("A3 x3: 760 000 O'ZGARMADI (asl: qoplama JORIY narxda — 1 280 000)", taxminan(t3, 760_000), (t1, t3))
check("A4 qoplama qatori: zaxiradan olingan qism ko'rsatiladi", n3 is not None and "50 kg tayyor loy zaxirasidan" in n3   # kech119 (G2-15): son_korinish — «50», «5 200»
      and taxminan(s3, 260_000), (n3, s3))
narxlar(1)

# ══════════════════════════════════════════════════════════════
section("B — qisman zaxira (20 kg zaxira + 30 kg yangi)")
loy_zaxira(20)
B = yarat(50)
r = tayyor(B, 50)
check("B0 'Tayyor' 200; zaxira harakati 20 kg × 5 200", r.status_code == 200 and zaxira_harakatlari(B) == [("out", 20.0, 5200.0)],
      (r.status_code, zaxira_harakatlari(B)))
narxlar(3)
nb, sb = qoplama(B)
check("B1 x3: 760 000 (zaxira 20 × 5 200 + yangi 30 × 5 200 — ikkalasi muzlatilgan)", taxminan(foyda(B)[0], 760_000)
      and taxminan(sb, 260_000) and "20 kg tayyor loy zaxirasidan" in (nb or "") and "30 kg" in (nb or ""), (foyda(B)[0], nb, sb))
narxlar(1)

# ══════════════════════════════════════════════════════════════
section("C — zaxira olingan paytda narx boshqa (x2)")
narxlar(2)
loy_zaxira(20)
Cq = yarat(50)                                    # 20 kg zaxira (x2: 10 400) + 30 kg yangi ingredient (x2)
narxlar(1)
r = tayyor(Cq, 50)
check("C0 zaxira harakati 20 kg × 10 400 (olingan paytdagi x2 narx)", zaxira_harakatlari(Cq) == [("out", 20.0, 10400.0)],
      zaxira_harakatlari(Cq))
narxlar(3)
check("C1 x3 da ham: 1 000 000 (penoplast x2) + 20 × 10 400 + 30 × 10 400 = 1 520 000",
      taxminan(foyda(Cq)[0], 1_520_000), foyda(Cq))
narxlar(1)

# ══════════════════════════════════════════════════════════════
section("D — ishlatilgan loy zaxiradan olinganidan KAM")
loy_zaxira(100)
D = yarat(50)                                     # 50 kg zaxiradan olindi
r = tayyor(D, 40)                                 # 40 kg ishlatildi (10 kg ortdi — zaxiraga qaytadi)
narxlar(3)
nd, sd = qoplama(D)
check("D1 x3: qoplama 40 × 5 200 = 208 000 (zaxira qismi ishlatilgan 40 kg bilan cheklangan)",
      r.status_code == 200 and taxminan(sd, 208_000) and "40 kg tayyor loy zaxirasidan" in (nd or ""), (r.status_code, nd, sd))
narxlar(1)

# ══════════════════════════════════════════════════════════════
section("E — eski zaxira harakati (narxi 0 — tuzatishdan oldin yozilgan): avvalgi qoida")
loy_zaxira(100)
E = yarat(50)
r = tayyor(E, 50)
_d = SessionLocal()
try:
    for h in _d.query(InventoryMovement).filter(InventoryMovement.order_id == E, InventoryMovement.inventory_id == LOY_ID).all():
        h.unit_cost = 0.0
    _d.commit()
finally:
    _d.close()
narxlar(3)
ne, se = qoplama(E)
check("E1 narxi 0 — noma'lum: butun loy avvalgidek (x3 da JORIY 50 × 15 600 = 780 000), matn avvalgi shaklda",
      taxminan(se, 780_000) and ne == "Qoplama (50 kg loy × 15\u00a0600 so'm/kg)", (ne, se))
narxlar(1)

# ══════════════════════════════════════════════════════════════
section("F — brak zaxirali buyurtmada")
loy_zaxira(100)
Fq = yarat(50)
_d = SessionLocal()
try:
    _it = _d.query(OrderItem).filter(OrderItem.order_id == Fq).order_by(OrderItem.id).first()
    _iid, _nom = _it.id, _it.name
finally:
    _d.close()
rb = req(C, "post", "/api/returns", json={"order_id": Fq, "order_item_id": _iid, "item_name": _nom, "quantity": 5, "unit": "metr",
                                          "brak_sabab": "boshqa", "reason": "Brak", "refund_amount": 0, "to_stock": False,
                                          "coating_applied": True})
RID = (js(rb) or {}).get("id")
_d = SessionLocal()
try:
    _hs = _d.query(InventoryMovement).filter(InventoryMovement.return_item_id == RID).all() if RID else []
    _qiymat = round(sum(float(h.quantity) * float(h.unit_cost or 0) for h in _hs), 2)
    _loy_h = [(round(float(h.quantity), 4), None if h.unit_cost is None else float(h.unit_cost)) for h in _hs if h.inventory_id == LOY_ID]
    _summa = round(float(_d.get(ReturnItem, RID).refund_amount or 0), 2) if RID else None
finally:
    _d.close()
check("F1 brak 200; zaxira loyi harakati narxi 5 200 (asl: 0.0)", rb.status_code == 200 and _loy_h == [(2.5, 5200.0)], (rb.status_code, _loy_h))
check("F2 brak harakatlari qiymati = yozuv summasi (38 000; asl: 25 000 — loy yo'qolardi)",
      _summa is not None and taxminan(_qiymat, _summa) and taxminan(_qiymat, 38_000), (_qiymat, _summa))
_rep = js(req(C, "get", "/api/returns/stats")) or {}
check("F3 karta (49-band — harakatlar) loyni ham oladi", taxminan(_rep.get("brak_month_value"), 38_000, 0.5), _rep.get("brak_month_value"))

# ══════════════════════════════════════════════════════════════
section("G — izolyatsiya")
_d = SessionLocal()
try:
    _b_loy = _d.query(Inventory).filter(Inventory.company_id == 2, Inventory.item_name == "Tayyor loy (ZL R1)").first()
    _b_loy_id = _b_loy.id if _b_loy else None
finally:
    _d.close()
check("G1 B korxonaning shu nomli pozitsiyasi A buyurtmasida ishlatilmadi (A zaxirasi — o'ziniki)",
      _b_loy_id is not None and _b_loy_id != LOY_ID and all(zaxira_harakatlari(x) for x in (A, B, D, E)), (_b_loy_id, LOY_ID))
_d = SessionLocal()
try:
    _hq = services._buyurtma_sarf_hisobi(_d, _d.get(Order, A)) if hasattr(services, "_buyurtma_sarf_hisobi") else {}
    _zx = services._buyurtma_zaxira_loyi(_d, _d.get(Order, A), _d.get(Recipe, R1_ID), _hq) \
        if hasattr(services, "_buyurtma_zaxira_loyi") else None
finally:
    _d.close()
check("G2 `_buyurtma_zaxira_loyi` — A ning o'z pozitsiyasi (50 kg, 5 200)", _zx == (50.0, 5200.0), _zx)

# ══════════════════════════════════════════════════════════════
section("H — pozitsiyaga egasi narx qo'ygan (> 0): o'sha narx (avvalgidek)")
_d = SessionLocal()
try:
    _d.get(Inventory, LOY_ID).price_per_unit = 4_000
    _d.get(Inventory, LOY_ID).stock_quantity = 100
    _d.commit()
finally:
    _d.close()
Hq = yarat(50)
r = tayyor(Hq, 50)
narxlar(3)
nh, sh = qoplama(Hq)
check("H1 zaxira harakati narxi — pozitsiya narxi 4 000 (retsept tannarxi emas); x3 da qoplama 50 × 4 000 = 200 000",
      zaxira_harakatlari(Hq) == [("out", 50.0, 4000.0)] and taxminan(sh, 200_000), (zaxira_harakatlari(Hq), nh, sh))
narxlar(1)
_d = SessionLocal()
try:
    _d.get(Inventory, LOY_ID).price_per_unit = None
    _d.commit()
finally:
    _d.close()

# ══════════════════════════════════════════════════════════════
section("S — statik")
_src_t = inspect.getsource(services.take_loy_from_stock)
check("S1 zaxiradan olish harakatiga retsept tannarxi beriladi (`unit_cost=_zaxira_narxi`; pozitsiya narxi bo'lsa — o'sha)",
      "get_loy_cost_per_kg(" in _src_t and "unit_cost=_zaxira_narxi" in _src_t
      and "if not float(stock.price_per_unit or 0) > 0:" in _src_t, "")
_src_l = inspect.getsource(crud.log_movement)
check("S2 `crud.log_movement(unit_cost=…)` — berilsa shu narx, aks holda joriy narx (avvalgidek)",
      "unit_cost: Optional[float] = None" in _src_l and "_narx = float(unit_cost)" in _src_l
      and "_narx = float(_inv_narx.price_per_unit or 0)" in _src_l, "")
_src_p = inspect.getsource(services.calculate_order_profit)
check("S3 tannarx hisobi BIR marta (`_buyurtma_sarf_hisobi`), zaxira qismi — `_buyurtma_zaxira_loyi`",
      _src_p.count("_buyurtma_sarf_hisobi(db, order)") == 1 and "_buyurtma_zaxira_loyi(db, order, recipe, _sarf_hisob)" in _src_p, "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   - " + f)
sys.exit(0 if FAIL == 0 else 1)
