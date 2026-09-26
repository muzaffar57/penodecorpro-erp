#!/usr/bin/env python3
"""test_kesh_oquvchi.py — kech90 darvozasi (2026-09-26, 110-band: Moliyadan tashqaridagi N+1 o'quvchilar).

110-band (O'LCHANGAN — kech89 `dump52`, kech90 `dump110 IZ=1` va JONLI `tenant_filter.stats`): kech89 hisobot keshi
(52-band) faqat Moliya oilasida edi; boshqa o'quvchilar har "Tayyor" buyurtma uchun `calculate_order_profit` ni
keshsiz chaqirib, buyurtma / detal / harakat / material / PO / TM / retsept / ustani ALOHIDA so'rardi:
bosh sahifa "bugun" (`get_today_stats`), loyihalar KPI (`crud.get_projects_dashboard_stats` — yana har loyiha
uchun `p.orders`), usta KPI hisoboti (`crud.get_masters_kpi_report`), usta KPI tafsiloti
(`crud.get_master_kpi_detail`), keshbek ("Bonuslarim", `crud.get_master_yearly_cashback`), loyiha detali
(`/api/projects/{id}/detail-stats`). Jonli (sinov): `/api/projects/dashboard-stats` 254 so'rov, ~2 s.

YECHIM (texnik): o'sha hisobot keshi — services: `get_today_stats` o'raladi (`_hisobot_keshi_bilan`) +
`_hk_tayyorla`; `_hk_loyihalar` (loyihalar `orders` ro'yxati bir necha IN so'rovi bilan + "Tayyor"lari);
crud: `_hisobot_keshida` dekoratori (services chaqiruv paytida import); main: `with services.hisobot_keshi(db)`.
Hisob-kitob mantig'i O'ZGARMAYDI; `services.HISOBOT_KESHI_YOQIQ = False` — ASL yo'l. Sovg'a davri YOPILISHI
(`crud._gift_period_profit_since` — yozuvchi) tegilmagan.

Bo'limlar:
  A — kesh bilan va keshsiz (ASL yo'l) natija AYNAN: fikstura test_hisobot_kesh dagidek (qoplamali / MRP / TM /
      brak / gips / KORXONALARARO buzilgan havolalar) + ko'p buyurtmali loyihalar (buyurtma loyihalar orasida
      ko'chirilgan), yopilgan sovg'a davri va keshbek o'tkazmasi; funksiyalar (3 korxona holati) va API
      (bosh sahifa, loyihalar KPI, /projects sahifasi, usta KPI, KPI tafsiloti, loyiha detali — ikki korxona);
  B — N+1 YO'Q: 10 yangi loyiha + 20 "Tayyor" buyurtmadan keyin so'rovlar soni o'zgarmaydi, ASL yo'l o'sadi;
  C — kesh xulqi: loyiha buyurtmalari ro'yxati (to'plam va TARTIB) lazy bilan AYNAN, kesh yo'q — hech narsa,
      takroriy chaqiruv 0 so'rov, faqat o'z korxonasi, oldin yuklanganlar qayta o'qilmaydi, xato yo'li
      (`db.rollback()`) kesh bilan ham AYNAN;
  H — kod (statik).
Ishga tushirish (repo ildizidan):
    python3 tools/test_kesh_oquvchi.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_kesh_oquvchi.py
"""
import os
import sys
import json
import inspect
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "kesh_oquvchi_test"
_T = tempfile.mkdtemp(prefix="kesh_oquvchi_")
_DB = os.path.join(_T, "kesh_oquvchi_test.db")

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

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from production_models import Company, ProductionOrder   # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, Recipe, RecipeIngredient, Master, Employee, PayType, Order, OrderItem,
    InventoryMovement, FinishedProduct, FinishedProductLoss, StockSource, ProductionStatus, ExpenseTransaction,
    MonthlyExpense, OrderStatus,
)
from sqlalchemy import event                       # noqa: E402
from sqlalchemy import inspect as sa_inspect       # noqa: E402
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
        print(f"  ✗ {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.headers = {}

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


def tartibda(src, *qismlar):
    """Qismlar src ichida AYNAN shu tartibda uchraydimi (find — topilmasa False)."""
    p = 0
    for q in qismlar:
        i = src.find(q, p)
        if i < 0:
            return False
        p = i + len(q)
    return True


# ══════════════════════════════════════════════════════════════
# Fikstura — 1-korxona (A), 2-korxona (B)
# ══════════════════════════════════════════════════════════════
QADAM = []
ID = {}


def qayd(nom, r, kutilgan=(200,)):
    kod = getattr(r, "status_code", r)
    if kod not in kutilgan:
        QADAM.append(f"{nom}: {kod} {str(getattr(r, 'text', ''))[:200]}")
    return r


_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="KO Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "KO_a", "Parol123!", UserRole.ADMIN, "KO A", company_id=1)
    auth.create_user(_db, "KO_b", "Parol123!", UserRole.ADMIN, "KO B", company_id=2)


def _inv(cid, nom, unit, narx, vol=None, peno=False, std=False, kat="Kimyo"):
    i = Inventory(company_id=cid, item_name=nom, unit=unit, stock_quantity=100_000, price_per_unit=narx,
                  volume_per_unit=vol, is_penoplast=peno, is_default_penoplast=std, category=kat)
    _db.add(i)
    _db.commit()
    return i.id


ID["P1"] = _inv(1, "KO Penoplast 15", "blok", 500_000, 1.0, True, True, "Penoplast")
ID["P2"] = _inv(1, "KO Penoplast 25", "blok", 720_000, 1.2, True, False, "Penoplast")
ID["KLEY"] = _inv(1, "KO Kley", "kg", 2_000)
ID["AKR"] = _inv(1, "KO Akril", "kg", 10_000)
ID["BOYOQ"] = _inv(1, "KO Boyoq", "kg", 20_000)
ID["TOSH"] = _inv(1, "KO Tosh", "kg", 5_000, kat="Xom")
ID["PB"] = _inv(2, "KO Penoplast B", "blok", 400_000, 1.0, True, True, "Penoplast")
ID["QUMB"] = _inv(2, "KO Qum B", "kg", 3_000, kat="Xom")
for _k, _cid, _nom in (("R1", 1, "KO R1"), ("R2", 1, "KO R2"), ("RB", 2, "KO RB")):
    _r = Recipe(company_id=_cid, name=_nom, batch_size_kg=100.0)
    _db.add(_r)
    _db.commit()
    ID[_k] = _r.id
_db.add_all([RecipeIngredient(recipe_id=ID["R1"], inventory_id=ID["KLEY"], quantity_kg=60.0),
             RecipeIngredient(recipe_id=ID["R1"], inventory_id=ID["AKR"], quantity_kg=40.0),
             RecipeIngredient(recipe_id=ID["R2"], inventory_id=ID["BOYOQ"], quantity_kg=70.0),
             RecipeIngredient(recipe_id=ID["R2"], inventory_id=ID["KLEY"], quantity_kg=30.0),
             RecipeIngredient(recipe_id=ID["RB"], inventory_id=ID["QUMB"], quantity_kg=100.0)])
_db.commit()
with contextlib.redirect_stdout(_quiet):
    for _rid in ("R1", "R2", "RB"):
        _st = services.get_or_create_loy_stock(_db, _db.get(Recipe, ID[_rid]))
        _st.stock_quantity = 0.0
_db.commit()
for _k, _cid, _nom, _cb, _kpi, _akt in (("M1", 1, "KO Usta 1", 10.0, 5.0, True), ("M2", 1, "KO Usta 2", 0.0, 3.0, True),
                                        ("M3", 1, "KO Usta 3", 0.0, 7.0, False),
                                        ("MB", 2, "KO Usta B", 0.0, 4.0, True)):
    _m = Master(company_id=_cid, name=_nom, phone="+99891000" + _k, cashback_percent=_cb, kpi_percent=_kpi,
                is_active=_akt)
    _db.add(_m)
    _db.commit()
    ID[_k] = _m.id
for _k, _cid in (("PA1", 1), ("PA2", 1), ("PB", 2)):
    _p = Project(company_id=_cid, client_name=f"KO {_k}", project_name=f"KO {_k}", total_budget=0, total_paid=0)
    _db.add(_p)
    _db.commit()
    ID["J" + _k] = _p.id
_db.add_all([
    Employee(company_id=1, name="KO Sotuvchi", pay_type=PayType.PERCENT_SALES, percent_value=1.5, is_active=True),
    Employee(company_id=1, name="KO Boshqaruvchi", pay_type=PayType.PERCENT_PROFIT, percent_value=4.0,
             is_active=True),
    Employee(company_id=1, name="KO Kesuvchi", pay_type=PayType.PER_UNIT, per_unit_rate=1_300, per_unit_type="metr",
             is_active=True),
    Employee(company_id=1, name="KO Blokchi", pay_type=PayType.PER_UNIT, per_unit_rate=7_000, per_unit_type="blok",
             is_active=True),
    Employee(company_id=1, name="KO Qoplamachi", pay_type=PayType.FIXED_PLUS_COATING, fixed_amount=1_000_000,
             per_unit_rate=900, is_active=True),
    Employee(company_id=2, name="KO B hodim", pay_type=PayType.PERCENT_SALES, percent_value=2.0, is_active=True),
])
_db.commit()
with contextlib.redirect_stdout(_quiet):
    crud.set_setting(_db, "ehson_percent", "2", company_id=1)
    crud.set_setting(_db, "ehson_percent", "3", company_id=2)
_db.commit()
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    qayd(f"login {login}", r, (302,))
    return c


C = _kir("KO_a")
CB = _kir("KO_b")

ID["PT"] = (js(qayd("PT", req(C, "post", "/api/production/product-types", json={
    "name": "KO Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"}))) or {}).get("id")
ID["BOM"] = (js(qayd("BOM", req(C, "post", "/api/production/boms", json={
    "product_type_id": ID["PT"], "variant_name": "Asosiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 3}]}))) or {}).get("id")

_n = [0]


def nom():
    _n[0] += 1
    return f"KO_D{_n[0]}"


def detal(cat, **k):
    t = {"name": nom(), "category": cat, "quantity": 1, "unit_price": 50_000, "is_coated": False, "penoplast_id": None}
    t.update(k)
    return t


def buyurtma(kalit, items, klient=None, prj="JPA1", **k):
    t = {"project_id": ID[prj], "order_type": "product", "items": items}
    t.update(k)
    r = qayd(f"buyurtma {kalit}", req(klient or C, "post", "/api/orders", json=t, params={"confirm_shortage": "true"}))
    d = js(r) or {}
    ID[kalit] = d.get("id") if isinstance(d, dict) else None
    ID[kalit + "_it"] = [it.get("id") for it in (d.get("items") or [])] if isinstance(d, dict) else []
    return ID[kalit]


def tayyor(kalit, loy=None, klient=None):
    p = {"loy_kg": str(loy)} if loy is not None else None
    return qayd(f"tayyor {kalit}", req(klient or C, "post", f"/api/orders/{ID[kalit]}/ready", params=p))


buyurtma("O1", [
    detal("profil", width=20, thickness=10, length=10, unit_price=50_000, is_coated=True, penoplast_id=ID["P1"],
          sub_details=[{"category": "profil", "width": 10, "thickness": 5, "length": 10, "quantity": 2, "is_coated": True},
                       {"category": "panel", "width": 10, "thickness": 5, "quantity": 3, "is_coated": True},
                       {"category": "profil", "width": 5, "thickness": 5, "length": 4, "quantity": 1, "is_coated": False}]),
    detal("karniz", width=15, thickness=10, length=6, quantity=2, unit_price=30_000, is_coated=True, penoplast_id=ID["P1"]),
], master_id=ID["M1"], recipe_id=ID["R1"], loy_kg=15, agreed_amount=1_300_000)
tayyor("O1", 15.5)
buyurtma("O2", [
    detal("panel", width=50, thickness=5, quantity=20, unit_price=40_000, is_coated=True, penoplast_id=ID["P2"]),
    detal("dona", width=10, thickness=10, length=6, quantity=30, unit_price=5_000, is_coated=True,
          penoplast_id=ID["P1"]),
    detal("dona", quantity=40, unit_price=8_000, is_coated=False, penoplast_id=ID["P1"]),
], master_id=ID["M2"], recipe_id=ID["R2"], loy_kg=10, base_price=2_000_000)
tayyor("O2", 9.25)
buyurtma("O3", [
    detal("blok", width=50, thickness=50, length=2, quantity=12, unit_price=90_000, penoplast_id=ID["P2"]),
    {"name": nom(), "category": "loy_sotish", "quantity": 25, "unit_price": 30_000, "is_coated": False,
     "penoplast_id": None, "recipe_id": ID["R1"]},
    detal("dona", quantity=10, unit_price=7_000, is_coated=False, penoplast_id=ID["P2"]),
], prj="JPA2", loy_kg=0)
tayyor("O3")
_db = SessionLocal()
_fp1 = FinishedProduct(company_id=1, name="KO TM profil", category="profil", is_coated=True, quantity=50,
                       produced_quantity=50, unit="metr", unit_price=0, cost_price=50 * 7_600,
                       source=StockSource.PRODUCED, penoplast_id=ID["P1"], recipe_id=ID["R1"], unit_volume_m3=0.01,
                       unit_loy_kg=0.5, production_status=ProductionStatus.READY)
_fp2 = FinishedProduct(company_id=1, name="KO TM dona", category="dona", quantity=20, produced_quantity=20,
                       unit="dona", unit_price=0, cost_price=20 * 1_234.5, unit_cost_stable=1_234.5,
                       source=StockSource.PRODUCED, production_status=ProductionStatus.READY)
_db.add_all([_fp1, _fp2])
_db.commit()
ID["FP1"], ID["FP2"] = _fp1.id, _fp2.id
_db.close()
buyurtma("O4", [
    detal("profil", width=20, thickness=10, length=5, unit_price=20_000, is_coated=True, penoplast_id=ID["P1"],
          finished_product_id=ID["FP1"]),
    detal("dona", quantity=3, unit_price=4_000, finished_product_id=ID["FP2"]),
    detal("profil", width=20, thickness=10, length=3, unit_price=25_000, penoplast_id=ID["P2"]),
    detal("dona", quantity=2, unit_price=4_000, finished_product_id=ID["FP2"]),
], prj="JPA2", master_id=ID["M1"], loy_kg=0)
tayyor("O4")
buyurtma("O5", [{"name": nom(), "category": "mrp_product", "quantity": 10, "unit_price": 100_000,
                 "is_coated": False, "penoplast_id": None, "product_type_id": ID["PT"]}], master_id=ID["M1"], loy_kg=0)


def po(miqdor, qadamlar):
    r = qayd(f"PO {miqdor}", req(C, "post", "/api/production/orders", json={
        "product_type_id": ID["PT"], "bom_id": ID["BOM"], "quantity": miqdor, "source_type": "customer_order",
        "source_order_id": ID["O5"], "source_order_item_id": (ID["O5_it"] or [None])[0]}))
    pid = ((js(r) or {}).get("production_order") or {}).get("id")
    for q in qadamlar:
        qayd(f"PO {miqdor} {q}", req(C, "post", f"/api/production/orders/{pid}/{q}"))
    return pid


ID["PO_bekor"] = po(2, ("start", "cancel"))
po(4, ("start", "complete"))
_db = SessionLocal()
_db.get(Inventory, ID["TOSH"]).price_per_unit = 5_333.33
_db.commit()
_db.close()
po(3, ("start", "complete"))
po(3, ("start", "complete"))
tayyor("O5")
buyurtma("O6", [detal("profil", width=30, thickness=20, length=20, unit_price=60_000, is_coated=True,
                      penoplast_id=ID["P2"])], prj="JPA2", recipe_id=ID["R1"], loy_kg=8)
qayd("xarid P2", req(C, "post", f"/api/inventory/{ID['P2']}/purchase", json={
    "quantity": 10, "price_per_unit": 810_000, "transport_payer": "none", "transport_cost": 0}))
qayd("xarid KLEY", req(C, "post", f"/api/inventory/{ID['KLEY']}/purchase", json={
    "quantity": 500, "price_per_unit": 2_600, "transport_payer": "self", "transport_cost": 40_000}))
tayyor("O6", 8.4)
buyurtma("O7", [detal("profil", width=20, thickness=20, length=5, unit_price=45_000, penoplast_id=ID["P1"])],
         master_id=ID["M2"], loy_kg=0)
tayyor("O7")
qayd("o'chir O7", req(C, "delete", f"/api/orders/{ID['O7']}"))
buyurtma("O8", [detal("panel", width=40, thickness=8, quantity=15, unit_price=35_000, is_coated=True,
                      penoplast_id=ID["P1"])], recipe_id=ID["R2"], loy_kg=6)
tayyor("O8", 6)
buyurtma("O9a", [detal("profil", width=25, thickness=10, length=12, unit_price=55_000, is_coated=True,
                       penoplast_id=ID["P1"])], master_id=ID["M1"], recipe_id=ID["R1"], loy_kg=5)
tayyor("O9a", 5)
buyurtma("O9b", [detal("panel", width=60, thickness=5, quantity=10, unit_price=38_000, penoplast_id=ID["P2"])],
         master_id=ID["M2"], loy_kg=0)
tayyor("O9b")
buyurtma("O9c", [detal("dona", width=12, thickness=8, length=4, quantity=12, unit_price=6_000, penoplast_id=ID["P1"])],
         loy_kg=0)
tayyor("O9c")
buyurtma("O10", [detal("profil", width=20, thickness=10, length=7, unit_price=48_000, penoplast_id=ID["P1"])],
         master_id=ID["M3"], loy_kg=0)
tayyor("O10")
buyurtma("O11", [detal("panel", width=30, thickness=5, quantity=6, unit_price=30_000, penoplast_id=ID["P1"])],
         agreed_amount=0, loy_kg=0)
tayyor("O11")
buyurtma("O12", [detal("profil", width=20, thickness=10, length=9, unit_price=50_000, penoplast_id=ID["P1"])],
         master_id=ID["M1"], loy_kg=0)
buyurtma("O13", [detal("profil", width=20, thickness=10, length=8, unit_price=50_000, penoplast_id=ID["P1"])],
         master_id=ID["M1"], loy_kg=0)
for _payer, _s in (("company", 150_000), ("split", 90_001)):
    qayd(f"yuk {_payer}", req(C, "post", "/api/deliveries", json={
        "order_id": ID["O13"], "items": [{"order_item_id": (ID["O13_it"] or [None])[0], "quantity": 2}],
        "notes": f"KO yuk {_payer}", "transport_cost": _s, "transport_payer": _payer}))
tayyor("O13")
buyurtma("OB1", [detal("profil", width=20, thickness=10, length=10, unit_price=70_000, is_coated=True,
                       penoplast_id=ID["PB"])], klient=CB, prj="JPB", master_id=ID["MB"], recipe_id=ID["RB"], loy_kg=4)
tayyor("OB1", 4, klient=CB)
buyurtma("OB2", [detal("panel", width=40, thickness=5, quantity=8, unit_price=33_000, penoplast_id=ID["PB"])],
         klient=CB, prj="JPB", loy_kg=0)
tayyor("OB2", klient=CB)

# ── ORM / Core qo'shimchalar (migratsiyalardan KEYIN — eski NULL qatorlar NULL qoladi) ──
_db = SessionLocal()
_hozir = datetime.utcnow()
_oy1 = (_hozir.replace(day=1) - timedelta(days=1)).replace(day=14, hour=9, minute=0, second=0, microsecond=0)
_oy2 = (_oy1.replace(day=1) - timedelta(days=1)).replace(day=20, hour=11, minute=0, second=0, microsecond=0)
_kecha = (_hozir - timedelta(days=1)).replace(hour=7, minute=30, second=0, microsecond=0)
if _kecha.month != _hozir.month:
    _kecha = _hozir.replace(hour=0, minute=5, second=0, microsecond=0)
for _k, _t in (("O9a", _oy1), ("O9b", _oy2), ("O9c", _kecha)):
    if ID.get(_k):
        _db.get(Order, ID[_k]).completed_at = _t
_db.commit()
if ID.get("O3"):
    _o3 = _db.get(Order, ID["O3"])
    _db.add(OrderItem(company_id=1, order_id=ID["O3"], name="KO gips eski", category="gips", quantity=4,
                      unit_price=25_000, total_price=100_000, is_coated=False))
    _o3.total_amount = float(_o3.total_amount or 0) + 100_000
    _db.commit()
_harakatlar = [
    dict(company_id=1, inventory_id=ID["P1"], item_name="KO Penoplast 15", movement_type="out", quantity=0.2,
         unit="blok", reason="KO brak belgi", order_id=ID.get("O8"), unit_cost=999_999.0, is_brak=True),
    dict(company_id=1, inventory_id=ID["P1"], item_name="KO Penoplast 15", movement_type="out", quantity=0.1,
         unit="blok", reason="Brak (eski) KO", order_id=ID.get("O8"), unit_cost=888_888.0, is_brak=None),
    dict(company_id=1, inventory_id=ID["KLEY"], item_name="KO Kley", movement_type="out", quantity=3.0, unit="kg",
         reason="KO eski harakat (narxsiz)", order_id=ID.get("O8"), unit_cost=None, is_brak=None),
    dict(company_id=1, inventory_id=ID["P1"], item_name="KO Penoplast 15", movement_type="in", quantity=0.004,
         unit="blok", reason="KO tahrir qaytishi", order_id=ID.get("O1"), unit_cost=None, is_brak=False),
    # KORXONALARARO buzilgan: B korxona harakati A buyurtmasiga; A harakati B materiali bilan (narxsiz)
    dict(company_id=2, inventory_id=ID["P1"], item_name="KO begona", movement_type="out", quantity=5.0,
         unit="blok", reason="KO begona harakat", order_id=ID.get("O1"), unit_cost=1.0, is_brak=False),
    dict(company_id=1, inventory_id=ID["PB"], item_name="KO begona material", movement_type="out", quantity=0.01,
         unit="blok", reason="KO begona material", order_id=ID.get("O4"), unit_cost=None, is_brak=False),
]
for _a in _harakatlar:
    _db.execute(InventoryMovement.__table__.insert().values(created_at=_hozir, **_a))
_db.commit()
if ID.get("PO_bekor"):
    # bekor qilingan PO da ham summa bo'lsa — asl so'rov ("completed" sharti) uni sanamaydi
    _db.execute(ProductionOrder.__table__.update().where(ProductionOrder.__table__.c.id == ID["PO_bekor"]).values(
        total_cost=12_345.0))
if ID.get("O5_it"):
    _db.execute(ProductionOrder.__table__.insert().values(
        company_id=2, product_type_id=ID["PT"], bom_id=ID["BOM"], source_type="customer_order",
        source_order_id=ID["O5"], source_order_item_id=ID["O5_it"][0], quantity=1.0, status="completed",
        total_cost=777_777.0, created_at=_hozir, completed_at=_hozir))
_fpb = FinishedProduct(company_id=2, name="KO TM B", category="dona", quantity=5, produced_quantity=5,
                       unit="dona", unit_price=0, cost_price=5 * 999.0, unit_cost_stable=999.0,
                       source=StockSource.PRODUCED, production_status=ProductionStatus.READY)
_db.add(_fpb)
_db.commit()
ID["FPB"] = _fpb.id
if len(ID.get("O4_it") or []) >= 3:
    _db.execute(OrderItem.__table__.update().where(OrderItem.__table__.c.id == ID["O4_it"][1]).values(
        finished_product_id=ID["FPB"]))
    _db.execute(OrderItem.__table__.update().where(OrderItem.__table__.c.id == ID["O4_it"][2]).values(
        penoplast_id=ID["PB"]))
if ID.get("O8"):
    _db.execute(Order.__table__.update().where(Order.__table__.c.id == ID["O8"]).values(qoplama_retsept_id=ID["RB"]))
if ID.get("OB2_it"):
    _db.execute(OrderItem.__table__.update().where(OrderItem.__table__.c.id == ID["OB2_it"][0]).values(
        penoplast_id=None))
_db.add(FinishedProduct(company_id=1, name="KO TM ishlab", category="panel", is_coated=True, quantity=30,
                        produced_quantity=30, unit="metr", unit_price=0, cost_price=100_000,
                        source=StockSource.PRODUCED, penoplast_id=ID["P2"], volume_m3=0.9,
                        production_status=ProductionStatus.READY, finished_production_at=_hozir))
_db.add_all([
    FinishedProductLoss(company_id=1, finished_product_id=ID["FP2"], product_name="KO TM dona", category="dona",
                        quantity=1, cost_amount=1_234.5, reason="KO sinib qoldi", lost_at=_hozir),
    FinishedProductLoss(company_id=1, finished_product_id=ID["FP2"], product_name="KO TM dona", category="dona",
                        quantity=1, cost_amount=5_000, reason=crud._ISH_BRAK_BELGI + " KO", lost_at=_hozir),
    ExpenseTransaction(company_id=1, date=_hozir, category="arenda", amount=1_000_000, source="manual"),
    ExpenseTransaction(company_id=1, date=_hozir, category="reklama", amount=200_000, source="manual",
                       production_type="penoplast"),
    ExpenseTransaction(company_id=1, date=_hozir, category="kutilmagan", amount=75_500.5, source="manual",
                       production_type="gips"),
    ExpenseTransaction(company_id=2, date=_hozir, category="arenda", amount=333_000, source="manual"),
    MonthlyExpense(company_id=1, year=_oy1.year, month=_oy1.month, arenda=900_000, elektr=150_000, tushlik=80_000,
                   soliqlar=50_000),
])
_db.commit()
_db.close()
qayd("TM sotuv", req(C, "post", "/api/finished/sell", json={"finished_product_id": ID["FP1"], "quantity": 4,
                                                          "unit_price": 30_000, "master_id": ID["M1"]}))
qayd("kirish transporti", req(C, "post", "/api/transport-expenses", json={"amount": 55_000, "materials_note": "KO",
                                                                          "notes": "KO kirish"}))
qayd("kirim hujjati", req(C, "post", "/api/inventory/receipt", json={
    "items": [{"inventory_id": ID["AKR"], "quantity": 100, "price_per_unit": 10_500}], "transport_cost": 30_000,
    "add_to_cost": False, "notes": "KO kirim"}))

# ── kech90 (110-band) qo'shimchalari ────────────────────────────────────────────
# * JPA3 — 3 buyurtma (2 "Tayyor" + 1 jarayonda), JPA4 — 1 "Tayyor", B da JPB2 — 1 "Tayyor";
# * O1 JPA1 dan JPA3 ga KO'CHIRILADI (Core), P3a qayta yoziladi — PG da qator yangi joyga tushadi (jismoniy
#   tartib id tartibidan farq qiladi) — loyiha buyurtmalari ro'yxati tartibi lazy va oldindan o'qishda bir xilmi;
# * yopilgan sovg'a davri (O9a — M1, O9b — M2 shu davrda) — keshbekdan chiqariladi; M1 ga keshbekka o'tkazma.
from models import GiftPeriod, MasterGiftPeriodRedemption      # noqa: E402
_db = SessionLocal()
for _k, _cid in (("PA3", 1), ("PA4", 1), ("PB2", 2)):
    _p = Project(company_id=_cid, client_name=f"KO {_k}", project_name=f"KO {_k}", total_budget=0, total_paid=0)
    _db.add(_p)
    _db.commit()
    ID["J" + _k] = _p.id
_db.close()
buyurtma("P3a", [detal("panel", width=40, thickness=5, quantity=7, unit_price=36_000, penoplast_id=ID["P2"])],
         prj="JPA3", master_id=ID["M2"], loy_kg=0)
tayyor("P3a")
buyurtma("P3b", [detal("profil", width=20, thickness=10, length=6, unit_price=52_000, is_coated=True,
                       penoplast_id=ID["P1"])], prj="JPA3", master_id=ID["M1"], recipe_id=ID["R1"], loy_kg=3)
tayyor("P3b", 3)
buyurtma("P3c", [detal("profil", width=20, thickness=10, length=4, unit_price=50_000, penoplast_id=ID["P1"])],
         prj="JPA3", master_id=ID["M1"], loy_kg=0)
buyurtma("P4a", [detal("dona", quantity=15, unit_price=6_500, penoplast_id=ID["P2"])], prj="JPA4", loy_kg=0)
tayyor("P4a")
buyurtma("PB2a", [detal("panel", width=30, thickness=5, quantity=4, unit_price=31_000, penoplast_id=ID["PB"])],
         klient=CB, prj="JPB2", master_id=ID["MB"], loy_kg=0)
tayyor("PB2a", klient=CB)
_db = SessionLocal()
if ID.get("O1") and ID.get("JPA3"):
    _db.execute(Order.__table__.update().where(Order.__table__.c.id == ID["O1"]).values(project_id=ID["JPA3"]))
if ID.get("P3a"):
    _db.execute(Order.__table__.update().where(Order.__table__.c.id == ID["P3a"]).values(notes="KO qayta yozildi"))
_db.commit()
_gp = GiftPeriod(company_id=1, is_active=False, started_at=_oy2 - timedelta(days=2), closed_at=_oy1 + timedelta(days=1),
                 created_by="KO")
_db.add(_gp)
_db.commit()
ID["GP1"] = _gp.id
_db.add(MasterGiftPeriodRedemption(period_id=_gp.id, master_id=ID["M1"], gift_name="KO keshbek", sales_amount=0,
                                   profit_amount=12_345.67, kind="cashback_conversion", redeemed_at=_hozir))
_db.commit()
_db.close()

section("0. Fikstura")
check("F1 fikstura qadamlari xatosiz (API javoblari kutilgandek)", not QADAM, QADAM[:5])
_s = SessionLocal()
_bugun_tayyor = _s.query(Order).filter(Order.company_id == 1, Order.status == OrderStatus.READY,
                                       Order.completed_at >= _hozir.replace(hour=0, minute=0, second=0,
                                                                            microsecond=0)).count()
_pa3 = sorted(o.id for o in _s.query(Order).filter(Order.project_id == ID.get("JPA3")).all())
_s.close()
check("F2 bugun \"Tayyor\" bo'lgan A buyurtmalari >= 8", _bugun_tayyor >= 8, _bugun_tayyor)
check("F3 JPA3 da 4 buyurtma (O1 ko'chirilgan + P3a / P3b / P3c)", len(_pa3) == 4, _pa3)

# ══════════════════════════════════════════════════════════════
# SQL hisoblagich va chaqiruv yordamchilari
# ══════════════════════════════════════════════════════════════
SANOQ = {"n": 0, "on": False, "sql": []}


@event.listens_for(engine, "before_cursor_execute")
def _sana(conn, cursor, statement, parameters, context, executemany):
    if SANOQ["on"]:
        SANOQ["n"] += 1
        SANOQ["sql"].append(" ".join(str(statement).split()))


def _jsonla(v):
    return json.dumps(v, default=str, sort_keys=True)


def _bayroq(kesh):
    _eski = getattr(services, "HISOBOT_KESHI_YOQIQ", None)
    services.HISOBOT_KESHI_YOQIQ = kesh
    return _eski


def _bayroq_qaytar(_eski):
    if _eski is None:
        try:
            delattr(services, "HISOBOT_KESHI_YOQIQ")
        except Exception:                  # noqa: BLE001
            pass
    else:
        services.HISOBOT_KESHI_YOQIQ = _eski


def chaqir(fn, kesh=True):
    """(natija JSON, so'rovlar soni, sessiyada kesh qoldimi) — alohida sessiyada; xato ham natija."""
    _eski = _bayroq(kesh)
    s = SessionLocal()
    SANOQ["n"] = 0
    SANOQ["on"] = True
    qoldi = None
    try:
        with contextlib.redirect_stdout(_quiet):
            v = _jsonla(fn(s))
        qoldi = "_hisobot_keshi" in getattr(s, "info", {})
    except Exception as e:                 # noqa: BLE001
        v = f"XATO {type(e).__name__}: {e}"
    finally:
        SANOQ["on"] = False
        n = SANOQ["n"]
        try:
            s.rollback()
        except Exception:                  # noqa: BLE001
            pass
        s.close()
        _bayroq_qaytar(_eski)
    return v, n, qoldi


def api(klient, url, params=None, kesh=True):
    """(javob kodi + matni, so'rovlar soni) — to'liq so'rov (TestClient)."""
    _eski = _bayroq(kesh)
    SANOQ["n"] = 0
    SANOQ["on"] = True
    try:
        r = req(klient, "get", url, params=params)
        v = f"{r.status_code} {r.text}"
    except Exception as e:                 # noqa: BLE001
        v = f"XATO {type(e).__name__}: {e}"
    finally:
        SANOQ["on"] = False
        n = SANOQ["n"]
        _bayroq_qaytar(_eski)
    return v, n


hozir = datetime.utcnow()
Y = hozir.year
_s = SessionLocal()
USTALAR = sorted((m.id, m.company_id) for m in _s.query(Master).all())
LOYIHALAR = sorted((p.id, p.company_id) for p in _s.query(Project).all())
_s.close()

# ══════════════════════════════════════════════════════════════
section("A. Kesh bilan va keshsiz (ASL yo'l) natija AYNAN")
# ══════════════════════════════════════════════════════════════
CHAQIRUVLAR = []
for _cid in (1, 2, None):
    CHAQIRUVLAR += [
        (f"bugun c{_cid}", lambda s, c=_cid: services.get_today_stats(s, company_id=c)),
        (f"loyihalar KPI c{_cid}", lambda s, c=_cid: crud.get_projects_dashboard_stats(s, company_id=c)),
        (f"usta KPI (hammasi) c{_cid}",
         lambda s, c=_cid: crud.get_masters_kpi_report(s, Y, include_inactive=True, company_id=c)),
        (f"usta KPI (faol) c{_cid}",
         lambda s, c=_cid: crud.get_masters_kpi_report(s, Y, include_inactive=False, company_id=c)),
    ]
for (_mid, _mc) in USTALAR:
    for _cid in (_mc, None, 3 - _mc):
        CHAQIRUVLAR += [
            (f"usta KPI tafsiloti m{_mid} c{_cid}",
             lambda s, m=_mid, c=_cid: crud.get_master_kpi_detail(s, m, Y, company_id=c)),
            (f"keshbek m{_mid} c{_cid}", lambda s, m=_mid, c=_cid: crud.get_master_yearly_cashback(s, m, Y, company_id=c)),
        ]
SOROV_ON, SOROV_OFF = {}, {}
_qoldi = []
for _nom, _fn in CHAQIRUVLAR:
    _off, SOROV_OFF[_nom], _ = chaqir(_fn, kesh=False)
    _on, SOROV_ON[_nom], _q = chaqir(_fn, kesh=True)
    if _q is not False:
        _qoldi.append((_nom, _q))
    check(f"A {_nom}: kesh bilan = keshsiz", _on == _off and not _off.startswith("XATO"),
          f"keshsiz={_off[:160]} | kesh={_on[:160]}")
check("A1 funksiyadan keyin sessiyada hisobot keshi QOLMAYDI (hamma chaqiruv)", not _qoldi, _qoldi[:5])
API_CHAQIRUV = []
for _kn, _kl in (("A", C), ("B", CB)):
    API_CHAQIRUV += [
        (f"API {_kn} /api/dashboard/today", _kl, "/api/dashboard/today", None),
        (f"API {_kn} /api/projects/dashboard-stats", _kl, "/api/projects/dashboard-stats", None),
        (f"API {_kn} /projects (sahifa)", _kl, "/projects", None),
        (f"API {_kn} /api/masters/kpi-report", _kl, "/api/masters/kpi-report", None),
        (f"API {_kn} /api/masters/kpi-report (nofaol ham)", _kl, "/api/masters/kpi-report",
         {"include_inactive": "true"}),
    ]
    for (_mid, _mc) in USTALAR:
        API_CHAQIRUV.append((f"API {_kn} kpi-detail m{_mid}", _kl, f"/api/masters/{_mid}/kpi-detail", None))
    for (_pid, _pc) in LOYIHALAR:
        API_CHAQIRUV.append((f"API {_kn} detail-stats p{_pid}", _kl, f"/api/projects/{_pid}/detail-stats", None))
API_ON, API_OFF = {}, {}
for _nom, _kl, _url, _par in API_CHAQIRUV:
    _off, API_OFF[_nom] = api(_kl, _url, _par, kesh=False)
    _on, API_ON[_nom] = api(_kl, _url, _par, kesh=True)
    check(f"A {_nom}: kesh bilan = keshsiz", _on == _off and _off[:3] in ("200", "404"),
          f"keshsiz={_off[:160]} | kesh={_on[:160]}")
for _nom, _chegara in (("loyihalar KPI c1", 2), ("bugun c1", 2), ("usta KPI (hammasi) c1", 2),
                       (f"usta KPI tafsiloti m{ID['M1']} c1", 2), (f"keshbek m{ID['M1']} c1", 1.5)):
    check(f"A2 {_nom} — kesh so'rovlarni kamaytiradi (bo'sh isbot emas): {SOROV_ON.get(_nom)} < "
          f"{SOROV_OFF.get(_nom)} / {_chegara}", SOROV_ON.get(_nom, 10**9) * _chegara < SOROV_OFF.get(_nom, 0),
          f"kesh={SOROV_ON.get(_nom)} keshsiz={SOROV_OFF.get(_nom)}")
_kp = f"API A detail-stats p{ID['JPA2']}"
check(f"A3 loyiha detali (JPA2) — kesh so'rovlarni kamaytiradi: {API_ON.get(_kp)} * 2 < {API_OFF.get(_kp)}",
      API_ON.get(_kp, 10**9) * 2 < API_OFF.get(_kp, 0), f"kesh={API_ON.get(_kp)} keshsiz={API_OFF.get(_kp)}")

# ══════════════════════════════════════════════════════════════
section("B. N+1 YO'Q — buyurtmalar / loyihalar soni so'rovlar sonini o'zgartirmaydi")
# ══════════════════════════════════════════════════════════════
B_FN = {
    "bugun": lambda s: services.get_today_stats(s, company_id=1),
    "loyihalar KPI": lambda s: crud.get_projects_dashboard_stats(s, company_id=1),
    "usta KPI": lambda s: crud.get_masters_kpi_report(s, Y, include_inactive=True, company_id=1),
    "usta KPI tafsiloti (M1)": lambda s: crud.get_master_kpi_detail(s, ID["M1"], Y, company_id=1),
    "keshbek (M1)": lambda s: crud.get_master_yearly_cashback(s, ID["M1"], Y, company_id=1),
}
B_API = {"loyiha detali (JPA1)": f"/api/projects/{ID['JPA1']}/detail-stats",
         "API loyihalar KPI": "/api/projects/dashboard-stats"}
B0 = {k: chaqir(f, kesh=True)[1] for k, f in B_FN.items()}
B0.update({k: api(C, u, kesh=True)[1] for k, u in B_API.items()})
_db = SessionLocal()
for _i in range(10):
    _p = Project(company_id=1, client_name=f"KO N{_i}", project_name=f"KO N{_i}", total_budget=0, total_paid=0)
    _db.add(_p)
    _db.commit()
    ID[f"JN{_i}"] = _p.id
_db.close()
_qoshildi = 0
for _i in range(20):
    _usta = ID["M1"] if _i % 2 == 0 else ID["M2"]
    _prj = "JPA1" if _i % 2 == 0 else f"JN{_i // 2}"
    _kalit = f"N{_i}"
    if _i % 3 == 0:
        buyurtma(_kalit, [detal("profil", width=20, thickness=10, length=3 + _i, unit_price=40_000, is_coated=True,
                                penoplast_id=ID["P1"])], prj=_prj, master_id=_usta, recipe_id=ID["R1"], loy_kg=2)
        tayyor(_kalit, 2)
    else:
        buyurtma(_kalit, [detal("panel", width=30, thickness=5, quantity=2 + _i, unit_price=30_000,
                                penoplast_id=ID["P2"])], prj=_prj, master_id=_usta, loy_kg=0)
        tayyor(_kalit)
    _qoshildi += 1 if ID.get(_kalit) else 0
check("B0 10 ta yangi loyiha + 20 ta \"Tayyor\" buyurtma (10 tasi JPA1 da) yaratildi", _qoshildi == 20 and not QADAM,
      QADAM[-3:])
B20 = {k: chaqir(f, kesh=True)[1] for k, f in B_FN.items()}
B20.update({k: api(C, u, kesh=True)[1] for k, u in B_API.items()})
B20_off = {k: chaqir(f, kesh=False)[1] for k, f in B_FN.items()}
B20_off.update({k: api(C, u, kesh=False)[1] for k, u in B_API.items()})
B_LOY = {"loyihalar KPI", "API loyihalar KPI"}
for _k in list(B_FN) + list(B_API):
    _ch = 2 + (10 if _k in B_LOY else 0)
    check(f"B1 {_k}: +20 buyurtma" + (" / +10 loyiha (ro'yxat ataylab lazy — loyiha boshiga 1)" if _k in B_LOY else "")
          + f" — so'rovlar {B0[_k]} -> {B20[_k]} (farq <= {_ch})", B20[_k] - B0[_k] <= _ch,
          f"oldin={B0[_k]} keyin={B20[_k]}")
    check(f"B2 {_k}: ASL yo'l N+1 (nazorat — o'lchov sezgir): keshsiz {B20_off[_k]} > kesh {B20[_k]} + 60",
          B20_off[_k] > B20[_k] + 60, f"keshsiz={B20_off[_k]} kesh={B20[_k]}")
for _k, _f in B_FN.items():
    _on, _, _ = chaqir(_f, kesh=True)
    _off, _, _ = chaqir(_f, kesh=False)
    check(f"B3 +20 buyurtmadan keyin ham {_k}: kesh bilan = keshsiz", _on == _off and not _off.startswith("XATO"),
          f"{_off[:120]} | {_on[:120]}")
for _k, _u in B_API.items():
    _on, _ = api(C, _u, kesh=True)
    _off, _ = api(C, _u, kesh=False)
    check(f"B3 +20 buyurtmadan keyin ham {_k}: kesh bilan = keshsiz", _on == _off and _off.startswith("200"),
          f"{_off[:120]} | {_on[:120]}")

# ══════════════════════════════════════════════════════════════
section("C. Kesh xulqi (loyihalar yordamchisi, xato yo'li)")
# ══════════════════════════════════════════════════════════════
_hk = getattr(services, "_hk", None)
_hkx = getattr(services, "hisobot_keshi", None)
_loy = getattr(services, "_hk_loyihalar", None)
check("C0 services._hk_loyihalar bor", callable(_loy))


def _loyiha_tartib(kesh):
    """({loyiha_id: [buyurtma id lari — p.orders tartibida]}, loyihalar ro'yxatini o'qigan SQL lar)."""
    _eski = _bayroq(True)
    s = SessionLocal()
    try:
        prj = s.query(Project).order_by(Project.id).all()
        SANOQ["sql"] = []
        SANOQ["on"] = True
        if kesh:
            with _hkx(s):
                _loy(s, prj)
                SANOQ["on"] = False
                return {p.id: [o.id for o in p.orders] for p in prj}, list(SANOQ["sql"])
        r = {p.id: [o.id for o in p.orders] for p in prj}
        SANOQ["on"] = False
        return r, list(SANOQ["sql"])
    except Exception as e:                 # noqa: BLE001
        return {"xato": f"{type(e).__name__}: {e}"}, []
    finally:
        SANOQ["on"] = False
        s.close()
        _bayroq_qaytar(_eski)


def _loyiha_sql(sqllar):
    """Loyiha buyurtmalari ro'yxatini o'qigan SQL lar: (lazy `= ?` soni, IN / boshqa shakl soni)."""
    _r = [q for q in sqllar if q.startswith("SELECT orders.") and "orders.project_id" in q.split(" WHERE ")[-1]]
    lazy_n = sum(1 for q in _r if " IN " not in q.split(" WHERE ")[-1])
    return lazy_n, len(_r) - lazy_n


_t_asl, _sql_asl = _loyiha_tartib(False)
_t_kesh, _sql_kesh = (_loyiha_tartib(True) if (callable(_loy) and callable(_hkx))
                      else ({"xato": "yordamchi yo'q"}, []))
check("C1 loyiha buyurtmalari ro'yxati (to'plam VA tartib) — keshda lazy bilan AYNAN (hamma loyiha)",
      _t_kesh == _t_asl and "xato" not in _t_asl, {k: (_t_asl.get(k), _t_kesh.get(k)) for k in list(_t_asl)[:4]})
_la, _ia = _loyiha_sql(_sql_asl)
_lk, _ik = _loyiha_sql(_sql_kesh)
check(f"C1b ro'yxatlar keshda ham ASL (lazy, `project_id = ?`) so'rov bilan: lazy {_lk} = {_la} (loyihalar "
      f"{len(_t_asl)}), IN / boshqa shakl {_ik} = 0 — PG da IN tartibi farq qilishi o'lchangan (kech90)",
      _lk == _la == len(_t_asl) and _ik == 0 and _ia == 0, f"asl={_la}/{_ia} kesh={_lk}/{_ik}")
_j3 = _t_asl.get(ID.get("JPA3")) or []
print(f"  (ma'lumot) JPA3 lazy tartibi: {_j3} — id bo'yicha tartiblangan: {_j3 == sorted(_j3)}")


def _yordamchi_olchov():
    r = {}
    _eski = _bayroq(True)
    s = SessionLocal()
    try:
        prj = s.query(Project).filter(Project.company_id == 1).all()
        SANOQ["n"] = 0
        SANOQ["on"] = True
        _loy(s, prj)                                   # kesh YO'Q — hech narsa qilmaydi
        SANOQ["on"] = False
        r["keshsiz_sorov"] = SANOQ["n"]
        r["keshsiz_yuklanmadi"] = all("orders" not in sa_inspect(p).dict for p in prj)
        with _hkx(s):
            SANOQ["n"] = 0
            SANOQ["on"] = True
            _loy(s, prj)
            SANOQ["on"] = False
            r["birinchi"] = SANOQ["n"]
            SANOQ["n"] = 0
            SANOQ["on"] = True
            _loy(s, prj)                               # hammasi yuklangan / keshda — so'rov YO'Q
            SANOQ["on"] = False
            r["ikkinchi"] = SANOQ["n"]
            _d = getattr(_hk(s), "d", {})
            _kor = {getattr(x, "company_id", None) for bolim in ("harakat", "po") for lst in _d.get(bolim, {}).values()
                    for x in lst}
            _kor |= {getattr(x, "company_id", None) for bolim in ("inv", "tm", "buyurtma")
                     for x in _d.get(bolim, {}).values() if x is not None}
            r["korxonalar"] = sorted(_kor, key=str)
            r["tayyorlar"] = sorted(_d.get("buyurtma", {}))
        s.close()
        s = SessionLocal()
        prj = s.query(Project).filter(Project.company_id == 1).all()
        for p in prj:
            list(p.orders)                             # /projects sahifasidagidek — oldin yuklangan
        with _hkx(s):
            SANOQ["n"] = 0
            SANOQ["on"] = True
            _loy(s, prj)
            SANOQ["on"] = False
            r["yuklangan_loyiha_sorovi"] = SANOQ["n"]
            r["yuklangan_tayyorlar"] = sorted(_d2 for _d2 in getattr(_hk(s), "d", {}).get("buyurtma", {}))
    except Exception as e:                 # noqa: BLE001
        r["xato"] = f"{type(e).__name__}: {e}"
    finally:
        SANOQ["on"] = False
        s.close()
        _bayroq_qaytar(_eski)
    return r


_r = _yordamchi_olchov() if (callable(_loy) and callable(_hkx) and callable(_hk)) else {"xato": "yordamchi yo'q"}
check("C2 kesh YO'Q — _hk_loyihalar hech narsa qilmaydi (0 so'rov, ro'yxatlar yuklanmaydi)",
      _r.get("keshsiz_sorov") == 0 and _r.get("keshsiz_yuklanmadi") is True, _r)
check("C3 kesh bor — birinchi chaqiruv o'qiydi, ikkinchisi 0 so'rov (yuklangan / keshdagilar qayta o'qilmaydi)",
      (_r.get("birinchi") or 0) > 0 and _r.get("ikkinchi") == 0, _r)
check("C4 oldindan o'qilgan buyurtma / harakat / PO / material / TM — faqat A korxonasi (1)",
      _r.get("korxonalar") == [1], _r.get("korxonalar"))
_s = SessionLocal()
_kutilgan_t = sorted(o.id for o in _s.query(Order).join(Project, Project.id == Order.project_id).filter(
    Project.company_id == 1, Order.status == OrderStatus.READY).all())
_s.close()
check("C5 keshga loyihalardagi HAMMA \"Tayyor\" buyurtmalar tushadi (o'chirilgan ham — lazy kabi)",
      _r.get("tayyorlar") == _kutilgan_t, f"{_r.get('tayyorlar')} / {_kutilgan_t}")
check("C6 ro'yxatlari oldin yuklangan loyihalar (/projects sahifasi) QAYTA o'qilmaydi — faqat \"Tayyor\"lar",
      _r.get("yuklangan_tayyorlar") == _kutilgan_t and 0 < (_r.get("yuklangan_loyiha_sorovi") or 0) < (
          _r.get("birinchi") or 0), _r)

# Xato yo'li: bitta buyurtma foydasi xato bersa (asl kod `db.rollback()` / log bilan davom etadi) — kesh bilan ham AYNAN
_asl_cop = services.calculate_order_profit
_XATO_OID = ID.get("O4")


def _xatoli_cop(db, order_id, company_id=None):
    if order_id == _XATO_OID:
        raise RuntimeError("KO sinov xatosi")
    return _asl_cop(db, order_id, company_id=company_id)


services.calculate_order_profit = _xatoli_cop
try:
    for _k, _f in B_FN.items():
        _on, _, _q = chaqir(_f, kesh=True)
        _off, _, _ = chaqir(_f, kesh=False)
        check(f"C7 xato yo'li ({_k}, O4 foydasi xato): kesh bilan = keshsiz, kesh qolmaydi",
              _on == _off and not _off.startswith("XATO") and _q is False, f"{_off[:120]} | {_on[:120]} | {_q}")
    _on, _ = api(C, f"/api/projects/{ID['JPA2']}/detail-stats", kesh=True)
    _off, _ = api(C, f"/api/projects/{ID['JPA2']}/detail-stats", kesh=False)
    check("C7 xato yo'li (loyiha detali JPA2): kesh bilan = keshsiz", _on == _off and _off.startswith("200"),
          f"{_off[:120]} | {_on[:120]}")
    _asl_natija, _, _ = chaqir(lambda s: crud.get_projects_dashboard_stats(s, company_id=1), kesh=False)
finally:
    services.calculate_order_profit = _asl_cop
_normal, _, _ = chaqir(lambda s: crud.get_projects_dashboard_stats(s, company_id=1), kesh=False)
check("C8 xato yo'li haqiqatan ishladi (nazorat: xatoli natija ≠ normal natija)", _asl_natija != _normal,
      f"{_asl_natija[:100]} | {_normal[:100]}")

# ══════════════════════════════════════════════════════════════
section("H. Kod (statik)")
# ══════════════════════════════════════════════════════════════
for _mod, _fn in ((services, "get_today_stats"), (crud, "get_projects_dashboard_stats"),
                  (crud, "get_masters_kpi_report"), (crud, "get_master_kpi_detail"),
                  (crud, "get_master_yearly_cashback")):
    check(f"H1 {_mod.__name__}.{_fn} hisobot keshi bilan o'ralgan", hasattr(getattr(_mod, _fn, None), "__wrapped__"))


def _manba(obj):
    try:
        return inspect.getsource(obj)
    except Exception:                      # noqa: BLE001
        return ""


_s_bugun = _manba(services.get_today_stats)
_s_loy = _manba(crud.get_projects_dashboard_stats)
_s_rep = _manba(crud.get_masters_kpi_report)
_s_det = _manba(crud.get_master_kpi_detail)
_s_kb = _manba(crud.get_master_yearly_cashback)
_s_api = _manba(main.api_project_detail_stats)
_s_yl = _manba(_loy) if callable(_loy) else ""
_s_dek = _manba(getattr(crud, "_hisobot_keshida", None)) if getattr(crud, "_hisobot_keshida", None) else ""
check("H2 bugun: buyurtmalar o'qilgach DARHOL oldindan o'qiladi",
      "        Order.status == OrderStatus.READY\n    ).all()\n    _hk_tayyorla(db, completed_today)" in _s_bugun)
check("H2 loyihalar KPI: loyihalar o'qilgach DARHOL `_hk_loyihalar`",
      "    projects = _dq.all()\n    services._hk_loyihalar(db, projects)" in _s_loy)
check("H2 usta KPI: buyurtmalar o'qilgach DARHOL oldindan o'qiladi",
      "    ).all() if master_ids else []\n    services._hk_tayyorla(db, all_orders)" in _s_rep)
check("H2 usta KPI tafsiloti: buyurtmalar o'qilgach DARHOL oldindan o'qiladi",
      "    ).order_by(Order.completed_at.desc()).all()\n    services._hk_tayyorla(db, orders)" in _s_det)
check("H2 keshbek: buyurtmalar o'qilgach DARHOL oldindan o'qiladi",
      "    orders = _oq.order_by(Order.completed_at.desc()).all()\n    services._hk_tayyorla(db, orders)" in _s_kb)
check("H3 loyiha detali: sikl hisobot keshi ichida, \"Tayyor\"lar sikldan OLDIN oldindan o'qiladi",
      tartibda(_s_api, "    with services.hisobot_keshi(db):\n",
               "        services._hk_tayyorla(db, [o for o in orders if o.status == OrderStatus.READY])\n",
               "        for o in orders:\n"))
check("H4 _hk_loyihalar: kesh yo'q — chiqadi; ro'yxatlar ASL (lazy) yo'l bilan; \"Tayyor\"lar oldindan o'qiladi",
      tartibda(_s_yl, "if _hk(db) is None or not projects:",
               "_hk_tayyorla(db, [o for p in projects for o in (p.orders or []) if o.status == _OS_hk.READY])")
      and "selectinload(" not in _s_yl and ".options(" not in _s_yl and "db.query(" not in _s_yl)
check("H5 crud dekoratori services.hisobot_keshi ni chaqiruv paytida ishlatadi",
      tartibda(_s_dek, "import services as _sv_hk", "with _sv_hk.hisobot_keshi(_db):", "return fn(*args, **kwargs)"))
_s_gp = _manba(crud._gift_period_profit_since)
check("H6 sovg'a davri YOPILISHI (yozuvchi) — tegilmagan: o'ralmagan, kesh / oldindan o'qish yo'q",
      _s_gp and not hasattr(crud._gift_period_profit_since, "__wrapped__") and "_hk_tayyorla" not in _s_gp
      and "hisobot_keshi" not in _s_gp)
check("H7 asl so'rov satrlari o'zgarmagan (lint baseline langarlari)",
      "    orders = db.query(Order).filter(Order.project_id == project_id, Order.is_deleted.isnot(True)).all()" in _s_api
      and "    all_orders = db.query(Order).filter(" in _s_rep and "        last_order = db.query(Order).filter(" in _s_rep
      and "    orders = db.query(Order).filter(\n        Order.master_id == master_id," in _s_det)

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
engine.dispose()
sys.exit(1 if FAIL else 0)
