#!/usr/bin/env python3
"""test_hisobot_kesh.py — kech89 darvozasi (2026-09-26, 52-band: Moliya hisobotidagi N+1 so'rovlar).

52-band (O'LCHANGAN — kech88 `probe52`, kech89 `dump52 IZ=1`, SQLite = PG): `GET /api/finance/report` SQL
so'rovlari = 31 + 17 × N (N — shu oy "Tayyor" buyurtmalar), `/api/finance/history` = 350 + 17 × N; jonli 21
buyurtma → ~388 so'rov (~3.5 s). Sabab — `calculate_order_profit` (hisobot, Ehson, usta KPI — har buyurtma
uchun 2–3 marta) buyurtma / standart penoplast / harakatlar / material / detallar / ichki detallar / PO /
retsept / ustani ALOHIDA so'raydi, hisobot esa har detal uchun materialni (`_inv_rep`).

YECHIM (texnik): `services.hisobot_keshi` — hisobot funksiyalari (`@_hisobot_keshi_bilan`: oylik, kunlik, tarix,
bo'lingan foyda, brak tahlili) davomida sessiyada kesh; buyurtmalar `_hk_tayyorla` bilan bir necha IN so'rovi
orqali oldindan o'qiladi (korxona bo'yicha cheklangan). Hisob-kitob mantig'i O'ZGARMAYDI: kesh bo'lsa — keshdan
(asl filtr / tartib), bo'lmasa — ASL so'rov satri. `services.HISOBOT_KESHI_YOQIQ = False` — ASL yo'l.

Bo'limlar:
  A — kesh bilan va keshsiz (ASL yo'l) natija AYNAN: murakkab fikstura (qoplamali profil + ichki detallar,
      karniz, panel, dona o'lchamli / eski / zaxira penoplast, blok, loy sotish, TM detal, MRP detal (tugagan +
      bekor PO), narx o'zgarishi, yumshoq o'chirilgan, o'tgan oylar, kelishilgan summa, usta cashback / KPI,
      hodimlar, brak, eski NULL harakatlar, KORXONALARARO buzilgan havolalar) — oylik (3 korxona holati), tarix,
      kunlik, Ehson, KPI, bo'lingan, brak tahlili, taqqoslash, bashorat, holat, majburiyatlar;
  B — N+1 YO'Q: 20 ta qo'shimcha "Tayyor" buyurtmadan keyin so'rovlar soni o'zgarmaydi (oylik, tarix, kunlik);
  C — kesh xulqi: faol / ichma-ich / tozalanadi (xatoda ham) / o'chiq bayroq / korxona sharti / alohida
      `calculate_order_profit` keshsiz / oldindan o'qish faqat o'z korxonasi;
  H — kod (statik).
Ishga tushirish (repo ildizidan):
    python3 tools/test_hisobot_kesh.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_hisobot_kesh.py
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
PG_BAZA = "hisobot_kesh_test"
_T = tempfile.mkdtemp(prefix="hisobot_kesh_")
_DB = os.path.join(_T, "hisobot_kesh_test.db")

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
    MonthlyExpense,
)
from sqlalchemy import event                       # noqa: E402
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
    _db.add(Company(id=2, name="HK Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "HK_a", "Parol123!", UserRole.ADMIN, "HK A", company_id=1)
    auth.create_user(_db, "HK_b", "Parol123!", UserRole.ADMIN, "HK B", company_id=2)


def _inv(cid, nom, unit, narx, vol=None, peno=False, std=False, kat="Kimyo"):
    i = Inventory(company_id=cid, item_name=nom, unit=unit, stock_quantity=100_000, price_per_unit=narx,
                  volume_per_unit=vol, is_penoplast=peno, is_default_penoplast=std, category=kat)
    _db.add(i)
    _db.commit()
    return i.id


ID["P1"] = _inv(1, "HK Penoplast 15", "blok", 500_000, 1.0, True, True, "Penoplast")
ID["P2"] = _inv(1, "HK Penoplast 25", "blok", 720_000, 1.2, True, False, "Penoplast")
ID["KLEY"] = _inv(1, "HK Kley", "kg", 2_000)
ID["AKR"] = _inv(1, "HK Akril", "kg", 10_000)
ID["BOYOQ"] = _inv(1, "HK Boyoq", "kg", 20_000)
ID["TOSH"] = _inv(1, "HK Tosh", "kg", 5_000, kat="Xom")
ID["PB"] = _inv(2, "HK Penoplast B", "blok", 400_000, 1.0, True, True, "Penoplast")
ID["QUMB"] = _inv(2, "HK Qum B", "kg", 3_000, kat="Xom")
for _k, _cid, _nom in (("R1", 1, "HK R1"), ("R2", 1, "HK R2"), ("RB", 2, "HK RB")):
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
for _k, _cid, _nom, _cb, _kpi, _akt in (("M1", 1, "HK Usta 1", 10.0, 5.0, True), ("M2", 1, "HK Usta 2", 0.0, 3.0, True),
                                        ("M3", 1, "HK Usta 3", 0.0, 7.0, False),
                                        ("MB", 2, "HK Usta B", 0.0, 4.0, True)):
    _m = Master(company_id=_cid, name=_nom, phone="+99891000" + _k, cashback_percent=_cb, kpi_percent=_kpi,
                is_active=_akt)
    _db.add(_m)
    _db.commit()
    ID[_k] = _m.id
for _k, _cid in (("PA1", 1), ("PA2", 1), ("PB", 2)):
    _p = Project(company_id=_cid, client_name=f"HK {_k}", project_name=f"HK {_k}", total_budget=0, total_paid=0)
    _db.add(_p)
    _db.commit()
    ID["J" + _k] = _p.id
_db.add_all([
    Employee(company_id=1, name="HK Sotuvchi", pay_type=PayType.PERCENT_SALES, percent_value=1.5, is_active=True),
    Employee(company_id=1, name="HK Boshqaruvchi", pay_type=PayType.PERCENT_PROFIT, percent_value=4.0,
             is_active=True),
    Employee(company_id=1, name="HK Kesuvchi", pay_type=PayType.PER_UNIT, per_unit_rate=1_300, per_unit_type="metr",
             is_active=True),
    Employee(company_id=1, name="HK Blokchi", pay_type=PayType.PER_UNIT, per_unit_rate=7_000, per_unit_type="blok",
             is_active=True),
    Employee(company_id=1, name="HK Qoplamachi", pay_type=PayType.FIXED_PLUS_COATING, fixed_amount=1_000_000,
             per_unit_rate=900, is_active=True),
    Employee(company_id=2, name="HK B hodim", pay_type=PayType.PERCENT_SALES, percent_value=2.0, is_active=True),
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


C = _kir("HK_a")
CB = _kir("HK_b")

ID["PT"] = (js(qayd("PT", req(C, "post", "/api/production/product-types", json={
    "name": "HK Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"}))) or {}).get("id")
ID["BOM"] = (js(qayd("BOM", req(C, "post", "/api/production/boms", json={
    "product_type_id": ID["PT"], "variant_name": "Asosiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 3}]}))) or {}).get("id")

_n = [0]


def nom():
    _n[0] += 1
    return f"HK_D{_n[0]}"


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
_fp1 = FinishedProduct(company_id=1, name="HK TM profil", category="profil", is_coated=True, quantity=50,
                       produced_quantity=50, unit="metr", unit_price=0, cost_price=50 * 7_600,
                       source=StockSource.PRODUCED, penoplast_id=ID["P1"], recipe_id=ID["R1"], unit_volume_m3=0.01,
                       unit_loy_kg=0.5, production_status=ProductionStatus.READY)
_fp2 = FinishedProduct(company_id=1, name="HK TM dona", category="dona", quantity=20, produced_quantity=20,
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
        "notes": f"HK yuk {_payer}", "transport_cost": _s, "transport_payer": _payer}))
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
    _db.add(OrderItem(company_id=1, order_id=ID["O3"], name="HK gips eski", category="gips", quantity=4,
                      unit_price=25_000, total_price=100_000, is_coated=False))
    _o3.total_amount = float(_o3.total_amount or 0) + 100_000
    _db.commit()
_harakatlar = [
    dict(company_id=1, inventory_id=ID["P1"], item_name="HK Penoplast 15", movement_type="out", quantity=0.2,
         unit="blok", reason="HK brak belgi", order_id=ID.get("O8"), unit_cost=999_999.0, is_brak=True),
    dict(company_id=1, inventory_id=ID["P1"], item_name="HK Penoplast 15", movement_type="out", quantity=0.1,
         unit="blok", reason="Brak (eski) HK", order_id=ID.get("O8"), unit_cost=888_888.0, is_brak=None),
    dict(company_id=1, inventory_id=ID["KLEY"], item_name="HK Kley", movement_type="out", quantity=3.0, unit="kg",
         reason="HK eski harakat (narxsiz)", order_id=ID.get("O8"), unit_cost=None, is_brak=None),
    dict(company_id=1, inventory_id=ID["P1"], item_name="HK Penoplast 15", movement_type="in", quantity=0.004,
         unit="blok", reason="HK tahrir qaytishi", order_id=ID.get("O1"), unit_cost=None, is_brak=False),
    # KORXONALARARO buzilgan: B korxona harakati A buyurtmasiga; A harakati B materiali bilan (narxsiz)
    dict(company_id=2, inventory_id=ID["P1"], item_name="HK begona", movement_type="out", quantity=5.0,
         unit="blok", reason="HK begona harakat", order_id=ID.get("O1"), unit_cost=1.0, is_brak=False),
    dict(company_id=1, inventory_id=ID["PB"], item_name="HK begona material", movement_type="out", quantity=0.01,
         unit="blok", reason="HK begona material", order_id=ID.get("O4"), unit_cost=None, is_brak=False),
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
_fpb = FinishedProduct(company_id=2, name="HK TM B", category="dona", quantity=5, produced_quantity=5,
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
_db.add(FinishedProduct(company_id=1, name="HK TM ishlab", category="panel", is_coated=True, quantity=30,
                        produced_quantity=30, unit="metr", unit_price=0, cost_price=100_000,
                        source=StockSource.PRODUCED, penoplast_id=ID["P2"], volume_m3=0.9,
                        production_status=ProductionStatus.READY, finished_production_at=_hozir))
_db.add_all([
    FinishedProductLoss(company_id=1, finished_product_id=ID["FP2"], product_name="HK TM dona", category="dona",
                        quantity=1, cost_amount=1_234.5, reason="HK sinib qoldi", lost_at=_hozir),
    FinishedProductLoss(company_id=1, finished_product_id=ID["FP2"], product_name="HK TM dona", category="dona",
                        quantity=1, cost_amount=5_000, reason=crud._ISH_BRAK_BELGI + " HK", lost_at=_hozir),
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
qayd("kirish transporti", req(C, "post", "/api/transport-expenses", json={"amount": 55_000, "materials_note": "HK",
                                                                          "notes": "HK kirish"}))
qayd("kirim hujjati", req(C, "post", "/api/inventory/receipt", json={
    "items": [{"inventory_id": ID["AKR"], "quantity": 100, "price_per_unit": 10_500}], "transport_cost": 30_000,
    "add_to_cost": False, "notes": "HK kirim"}))

section("0. Fikstura")
check("F1 fikstura qadamlari xatosiz (API javoblari kutilgandek)", not QADAM, QADAM[:5])
_s = SessionLocal()
_tayyorlar = _s.query(Order).filter(Order.company_id == 1, Order.completed_at >= _hozir.replace(
    day=1, hour=0, minute=0, second=0, microsecond=0)).count()
_s.close()
check("F2 joriy oyda A korxonaning yakunlangan buyurtmalari >= 11", _tayyorlar >= 11, _tayyorlar)

# ══════════════════════════════════════════════════════════════
# SQL hisoblagich va chaqiruv yordamchilari
# ══════════════════════════════════════════════════════════════
SANOQ = {"n": 0, "on": False}


@event.listens_for(engine, "before_cursor_execute")
def _sana(conn, cursor, statement, parameters, context, executemany):
    if SANOQ["on"]:
        SANOQ["n"] += 1


def _jsonla(v):
    return json.dumps(v, default=str, sort_keys=True)


def chaqir(fn, kesh=True):
    """(natija JSON, so'rovlar soni) — alohida sessiyada; xato ham natija (turi va matni)."""
    _eski = getattr(services, "HISOBOT_KESHI_YOQIQ", None)
    services.HISOBOT_KESHI_YOQIQ = kesh
    s = SessionLocal()
    SANOQ["n"] = 0
    SANOQ["on"] = True
    try:
        with contextlib.redirect_stdout(_quiet):
            v = _jsonla(fn(s))
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
        if _eski is None:
            try:
                delattr(services, "HISOBOT_KESHI_YOQIQ")
            except Exception:              # noqa: BLE001
                pass
        else:
            services.HISOBOT_KESHI_YOQIQ = _eski
    return v, n


hozir = datetime.utcnow()
Y, M = hozir.year, hozir.month


def oy_oldin(y, m, k):
    for _ in range(k):
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return y, m


OYLAR = [oy_oldin(Y, M, k) for k in range(3)]
KUNLAR = sorted({hozir.date(), _kecha.date(), _oy1.date()})

# ══════════════════════════════════════════════════════════════
section("A. Kesh bilan va keshsiz (ASL yo'l) natija AYNAN")
# ══════════════════════════════════════════════════════════════
CHAQIRUVLAR = []
for _cid in (1, 2, None):
    for (_y, _m) in OYLAR:
        CHAQIRUVLAR.append((f"oylik c{_cid} {_y}-{_m:02d}",
                            lambda s, y=_y, m=_m, c=_cid: services.get_monthly_report(s, y, m, company_id=c)))
    CHAQIRUVLAR.append((f"tarix c{_cid}", lambda s, c=_cid: services.get_finance_history(s, 4, company_id=c)))
    for _d in KUNLAR:
        CHAQIRUVLAR.append((f"kunlik c{_cid} {_d}",
                            lambda s, d=_d, c=_cid: services.get_daily_finance_summary(s, d, company_id=c)))
for _cid in (1, 2):
    for (_y, _m) in OYLAR[:2]:
        CHAQIRUVLAR += [
            (f"Ehson c{_cid} {_y}-{_m}", lambda s, y=_y, m=_m, c=_cid: services.calculate_monthly_ehson(s, y, m, company_id=c)),
            (f"KPI c{_cid} {_y}-{_m}", lambda s, y=_y, m=_m, c=_cid: services.calculate_monthly_master_kpi(s, y, m, company_id=c)),
            (f"bo'lingan c{_cid} {_y}-{_m}",
             lambda s, y=_y, m=_m, c=_cid: services.calculate_split_profit_report(s, y, m, company_id=c)),
            (f"brak tahlili (1 oy) c{_cid} {_y}-{_m}",
             lambda s, y=_y, m=_m, c=_cid: services.get_brak_tahlil(s, y, m, company_id=c, oylar=1)),
            (f"majburiyatlar c{_cid} {_y}-{_m}",
             lambda s, y=_y, m=_m, c=_cid: services.get_company_obligations_status(s, y, m, company_id=c)),
        ]
    CHAQIRUVLAR += [
        (f"brak tahlili (3 oy) c{_cid}", lambda s, c=_cid: services.get_brak_tahlil(s, Y, M, company_id=c, oylar=3)),
        (f"taqqoslash c{_cid}", lambda s, c=_cid: services.get_monthly_comparison(s, Y, M, company_id=c)),
        (f"bashorat c{_cid}", lambda s, c=_cid: services.get_simple_forecast(s, Y, M, company_id=c)),
        (f"holat c{_cid}", lambda s, c=_cid: services.get_business_health(s, company_id=c)),
    ]
SOROV_ON, SOROV_OFF = {}, {}
for _nom, _fn in CHAQIRUVLAR:
    _off, SOROV_OFF[_nom] = chaqir(_fn, kesh=False)
    _on, SOROV_ON[_nom] = chaqir(_fn, kesh=True)
    check(f"A {_nom}: kesh bilan = keshsiz", _on == _off and not _off.startswith("XATO"),
          f"keshsiz={_off[:160]} | kesh={_on[:160]}")
_k1 = f"oylik c1 {Y}-{M:02d}"
check("A2 joriy oy hisoboti (A) — kesh so'rovlarni kamaytiradi (bo'sh isbot emas)",
      SOROV_ON.get(_k1, 10**9) * 2 < SOROV_OFF.get(_k1, 0), f"kesh={SOROV_ON.get(_k1)} keshsiz={SOROV_OFF.get(_k1)}")
_s = SessionLocal()
_oid_hammasi = sorted(o.id for o in _s.query(Order).all())
_s.close()
_farq = []
for _oid in _oid_hammasi:
    for _cid in (None, 1, 2):
        def _f(s, oid=_oid, c=_cid):
            with services.hisobot_keshi(s):
                _o = s.query(Order).filter(Order.id.in_(_oid_hammasi)).all()
                services._hk_tayyorla(s, _o)
                return services.calculate_order_profit(s, oid, company_id=c)
        _v_on, _ = chaqir(_f, kesh=True)
        _v_off, _ = chaqir(lambda s, oid=_oid, c=_cid: services.calculate_order_profit(s, oid, company_id=c), kesh=False)
        if _v_on != _v_off:
            _farq.append((_oid, _cid, _v_off[:120], _v_on[:120]))
check("A3 har buyurtma foydasi (3 xil korxona) — oldindan o'qilgan keshda = ASL", not _farq, _farq[:3])

# ══════════════════════════════════════════════════════════════
section("B. N+1 YO'Q — buyurtmalar soni so'rovlar sonini o'zgartirmaydi")
# ══════════════════════════════════════════════════════════════
B_FN = {
    "oylik": lambda s: services.get_monthly_report(s, Y, M, company_id=1),
    "tarix": lambda s: services.get_finance_history(s, 3, company_id=1),
    "kunlik": lambda s: services.get_daily_finance_summary(s, hozir.date(), company_id=1),
}
B0 = {k: chaqir(f, kesh=True)[1] for k, f in B_FN.items()}
_qoshildi = 0
for _i in range(20):
    _usta = ID["M1"] if _i % 2 == 0 else ID["M2"]
    _kalit = f"N{_i}"
    if _i % 3 == 0:
        buyurtma(_kalit, [detal("profil", width=20, thickness=10, length=3 + _i, unit_price=40_000, is_coated=True,
                                penoplast_id=ID["P1"])], master_id=_usta, recipe_id=ID["R1"], loy_kg=2)
        tayyor(_kalit, 2)
    else:
        buyurtma(_kalit, [detal("panel", width=30, thickness=5, quantity=2 + _i, unit_price=30_000,
                                penoplast_id=ID["P2"])], master_id=_usta, loy_kg=0)
        tayyor(_kalit)
    _qoshildi += 1 if ID.get(_kalit) else 0
check("B0 20 ta qo'shimcha buyurtma yaratildi va \"Tayyor\"", _qoshildi == 20 and not QADAM, QADAM[-3:])
B20 = {k: chaqir(f, kesh=True)[1] for k, f in B_FN.items()}
B20_off = {k: chaqir(f, kesh=False)[1] for k, f in B_FN.items()}
for _k in B_FN:
    check(f"B1 {_k}: +20 buyurtma — so'rovlar {B0[_k]} -> {B20[_k]} (farq <= 2)", B20[_k] - B0[_k] <= 2,
          f"oldin={B0[_k]} keyin={B20[_k]}")
    check(f"B2 {_k}: ASL yo'l N+1 (nazorat — o'lchov sezgir): keshsiz {B20_off[_k]} > kesh {B20[_k]} + 100",
          B20_off[_k] > B20[_k] + 100, f"keshsiz={B20_off[_k]} kesh={B20[_k]}")
_on, _ = chaqir(B_FN["oylik"], kesh=True)
_off, _ = chaqir(B_FN["oylik"], kesh=False)
check("B3 +20 buyurtmadan keyin ham oylik hisobot kesh bilan = keshsiz", _on == _off, f"{_off[:120]} | {_on[:120]}")
_on, _ = chaqir(B_FN["tarix"], kesh=True)
_off, _ = chaqir(B_FN["tarix"], kesh=False)
check("B4 +20 buyurtmadan keyin ham tarix kesh bilan = keshsiz", _on == _off, f"{_off[:120]} | {_on[:120]}")

# ══════════════════════════════════════════════════════════════
section("C. Kesh xulqi")
# ══════════════════════════════════════════════════════════════
_hk = getattr(services, "_hk", None)
_hkx = getattr(services, "hisobot_keshi", None)
_tay = getattr(services, "_hk_tayyorla", None)
check("C0 services.hisobot_keshi / _hk / _hk_tayyorla bor", callable(_hk) and callable(_hkx) and callable(_tay))


def _xulq():
    r = {}
    s = SessionLocal()
    try:
        services.HISOBOT_KESHI_YOQIQ = True
        with _hkx(s) as k1:
            r["faol"] = k1 is not None and _hk(s) is k1
            with _hkx(s) as k2:
                r["ichma_ich_tashqi"] = k2 is k1
            r["ichkidan_keyin_faol"] = _hk(s) is k1
        r["tozalandi"] = _hk(s) is None
        try:
            with _hkx(s):
                raise ValueError("sinov")
        except ValueError:
            pass
        r["xatoda_tozalandi"] = _hk(s) is None
        services.HISOBOT_KESHI_YOQIQ = False
        with _hkx(s) as k3:
            r["ochiq_bayroq"] = k3 is None and _hk(s) is None
        services.HISOBOT_KESHI_YOQIQ = True
        # korxona sharti: A buyurtmasi keshda, B korxona nomidan so'ralsa — topilmaydi (asl so'rovdagidek)
        _o1 = s.get(Order, ID["O1"])
        with _hkx(s):
            _tay(s, [_o1, s.get(Order, ID["O4"]), s.get(Order, ID["O5"])])
            _kk = _hk(s)
            _d = getattr(_kk, "d", {})
            _kor = {getattr(x, "company_id", None) for bolim in ("harakat", "po") for lst in _d.get(bolim, {}).values()
                    for x in lst}
            _kor |= {getattr(x, "company_id", None) for bolim in ("inv", "tm") for x in _d.get(bolim, {}).values()
                     if x is not None}
            r["oldindan_korxona"] = sorted(_kor)
            r["begona_korxona"] = services.calculate_order_profit(s, ID["O1"], company_id=2).get("success")
            r["oz_korxona"] = _jsonla(services.calculate_order_profit(s, ID["O1"], company_id=1))
        r["oz_korxona_asl"] = _jsonla(services.calculate_order_profit(s, ID["O1"], company_id=1))
        # hisobotdan keyin sessiyada kesh qolmaydi
        services.get_monthly_report(s, Y, M, company_id=1)
        r["hisobotdan_keyin"] = _hk(s) is None and "_hisobot_keshi" not in s.info
    except Exception as e:                 # noqa: BLE001
        r["xato"] = f"{type(e).__name__}: {e}"
    finally:
        services.HISOBOT_KESHI_YOQIQ = True
        s.close()
    return r


_r = _xulq() if (callable(_hk) and callable(_hkx) and callable(_tay)) else {"xato": "yordamchilar yo'q"}
check("C1 kesh faol (with ichida `_hk(db)` o'sha obyekt)", _r.get("faol") is True, _r)
check("C2 ichma-ich chaqiruv TASHQI keshni ishlatadi, ichkisidan keyin ham faol",
      _r.get("ichma_ich_tashqi") is True and _r.get("ichkidan_keyin_faol") is True, _r)
check("C3 with tugagach kesh o'chadi", _r.get("tozalandi") is True, _r)
check("C4 xato bilan chiqilganda ham kesh o'chadi", _r.get("xatoda_tozalandi") is True, _r)
check("C5 HISOBOT_KESHI_YOQIQ = False — kesh umuman yoqilmaydi", _r.get("ochiq_bayroq") is True, _r)
check("C6 keshdagi buyurtma BOSHQA korxona nomidan — \"topilmadi\" (asl so'rov kabi)",
      _r.get("begona_korxona") is False, _r.get("begona_korxona"))
check("C7 keshdagi buyurtma O'Z korxonasi nomidan — asl natija bilan AYNAN",
      _r.get("oz_korxona") and _r.get("oz_korxona") == _r.get("oz_korxona_asl"), _r.get("xato"))
check("C8 oldindan o'qilgan harakat / PO / material / TM — faqat buyurtmalar korxonasi (1)",
      _r.get("oldindan_korxona") == [1],
      _r.get("oldindan_korxona"))
check("C9 hisobotdan keyin sessiyada kesh qolmaydi", _r.get("hisobotdan_keyin") is True, _r)
_n_on = chaqir(lambda s: services.calculate_order_profit(s, ID["O1"], company_id=1), kesh=True)
_n_off = chaqir(lambda s: services.calculate_order_profit(s, ID["O1"], company_id=1), kesh=False)
check("C10 alohida calculate_order_profit keshsiz (so'rovlar soni bayroqqa bog'liq emas)",
      _n_on == _n_off, f"{_n_on[1]} / {_n_off[1]}")

# ══════════════════════════════════════════════════════════════
section("H. Kod (statik)")
# ══════════════════════════════════════════════════════════════
for _fn in ("get_monthly_report", "get_daily_finance_summary", "get_finance_history",
            "calculate_split_profit_report", "get_brak_tahlil"):
    check(f"H1 {_fn} hisobot keshi dekoratori bilan", hasattr(getattr(services, _fn, None), "__wrapped__"))
try:
    _srcr = inspect.getsource(services.get_monthly_report)
    _srcd = inspect.getsource(services.get_daily_finance_summary)
    _srcp = inspect.getsource(services.calculate_order_profit)
    _srct = inspect.getsource(_tay) if callable(_tay) else ""
except Exception:                          # noqa: BLE001
    _srcr = _srcd = _srcp = _srct = ""
check("H2 oylik: buyurtmalar ro'yxati o'qilgach DARHOL oldindan o'qiladi",
      "ready_orders = _roq.all()\n    _hk_tayyorla(db, ready_orders)" in _srcr)
check("H3 kunlik: buyurtmalar ro'yxati o'qilgach DARHOL oldindan o'qiladi",
      "orders_today = _otq.all()\n    _hk_tayyorla(db, orders_today)" in _srcd)
check("H4 foyda: ASL so'rovlar else-shoxida o'zgarishsiz (material, PO, TM, retsept)",
      tartibda(_srcp, "inv_item = db.query(Inventory).filter(Inventory.id == pid).first()",
               "_PO_cost.source_order_item_id == item.id", "_fpq = db.query(_FP_cost).filter(_FP_cost.id == fpid)",
               "recipe = db.query(Recipe).filter(Recipe.id == item.recipe_id).first()",
               "_rq = db.query(Recipe).filter(Recipe.id == _qrid)"))
check("H5 oldindan o'qish korxona bilan cheklangan (buyurtma, harakat, PO, material, TM)",
      tartibda(_srct, "Order.company_id.in_(cids)", "InventoryMovement.company_id.in_(cids)",
               "ProductionOrder.company_id.in_(cids)", "Inventory.company_id.in_(cids)",
               "FinishedProduct.company_id.in_(cids)"))
check("H6 harakatlar `id` tartibida va brak EMAS sharti bilan oldindan o'qiladi",
      tartibda(_srct, "_not_hk(_crud_hk.brak_harakati_sharti(InventoryMovement))",
               ".order_by(InventoryMovement.id).all()"))
check("H7 PO — faqat tugagan (asl so'rov sharti)", tartibda(_srct, 'ProductionOrder.status == "completed"'))

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
engine.dispose()
sys.exit(1 if FAIL else 0)
