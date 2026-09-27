#!/usr/bin/env python3
"""test_material_korxona.py — kech99 (2026-09-27), 112-band.

NIMA UCHUN KERAK
----------------
O'LCHANGAN (kech99 `work/probe112.py`, asl = zip 92, SQLite = PG): A korxonasining detali / retsepti B korxonasining
materialiga ishora qilsa (faqat Core bilan: 2026-09-21 (12-sizish) dan OLDINGI yoki ko'chirilgan ma'lumot — ORM
`_TENANT_REFS` yangi yozuvda yo'l qo'ymaydi):
  * `calculate_order_profit` materialni korxonasiz (`Inventory.id == pid`) qidirardi — foyda B narxi / hajmi bilan
    (profil 0.05 m³ × 400 000; blok hajmi B ning 0.25 m³ i bilan 0.5; dona narx-nisbat hajmi 0.1; loy sotish B
    retsepti 3 000 so'm/kg); B narxi o'zgarsa A ning foydasi va oylik sof foydasi o'zgarardi;
  * `_item_volume_m3` (ombordan yechish, tahrir farqi, brak, qaytarish hajmi) — B penoplastining narxi / hajmi bilan;
  * retsept ingredienti B materialiga — `get_loy_cost_per_kg` / foyda B narxi bilan, A ning yetishmovchilik xabarida B
    material NOMI va QOLDIG'I; loy yechish / qaytarish B omboriga yozmoqchi bo'lib ORM qo'riqchisida 409 — A buyurtmasini
    yaratish, "Tayyor" (loy farqi), loy rejasi, o'chirish — hammasi rad etilardi;
  * Retseptlar sahifasi (`get_recipe_insights`, ingredient nomi) — B narxi va B material nomi A ga.
YECHIM (texnik — `_peno_of` / oylik hisobot `_inv_rep` qoidasi bilan BIR): begona material "topilmaydi" — na hisobda,
na omborda qatnashmaydi (`services._korxona_materiali`, `services._retsept_materiali`,
`RecipeIngredient._oz_materiali`); korxona noma'lum (`None`) — asl korxonasiz qidiruv.

BO'LIMLAR
---------
  A foyda (profil / blok / dona / loy sotish — toza va buzilgan; korxona bilan / korxonasiz; hisobot keshi bilan AYNAN);
  B hajm (`_item_volume_m3` — ORM detali, soxta detal korxona bilan / korxonasiz; `_group_volumes_by_penoplast`);
  C loy ingredientlari (1 kg narxi, yetishmovchilik, yaratish / loy rejasi / "Tayyor" / o'chirish — B ombori va
    harakatlari tegilmaydi; toza nazorat retsepti; B o'z retsepti bilan ishlaydi);
  D sezgirlik: B narxlari 2 barobar bo'lsa A ning foydasi / oylik hisoboti O'ZGARMAYDI;
  E Retseptlar sahifasi (`get_recipe_insights`, ingredient nomi / birligi);
  X 5xx yo'q; S statik.

ISHLATISH
---------
    python3 tools/test_material_korxona.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_material_korxona.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import inspect
import tempfile
import contextlib
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "material_korxona_test"
_T = tempfile.mkdtemp(prefix="mko_")
_DB = os.path.join(_T, "material_korxona_test.db")

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

import io                                          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402
import models                                      # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (UserRole, Project, Inventory, Recipe, RecipeIngredient,   # noqa: E402
                    OrderItem, InventoryMovement, Order)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HOLATLAR = []


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
    print(f"\n── {t} " + "─" * max(0, 90 - len(t)))


def yaqin(a, b, eps=1e-6):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def xavfsiz(fn, *a, **k):
    """Chaqiruv — istisno bo'lsa ("QULAMASLIK" uchun) `("XATO", matn)`."""
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {str(e)[:200]}")


# ── fikstura ────────────────────────────────────────────────────────────────────────────────────────────────
_db = SessionLocal()
_db.add(Company(id=2, name="MKO Korxona B"))
_db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "mko_a", "Parol123!", UserRole.ADMIN, "MKO A", company_id=1)
    auth.create_user(_db, "mko_b", "Parol123!", UserRole.ADMIN, "MKO B", company_id=2)
ID = {}


def _inv(k, cid, nom, unit, narx, vol=None, peno=False, std=False, kat="Kimyo"):
    i = Inventory(company_id=cid, item_name=nom, unit=unit, stock_quantity=100_000, price_per_unit=narx,
                  volume_per_unit=vol, is_penoplast=peno, is_default_penoplast=std, category=kat)
    _db.add(i)
    _db.commit()
    ID[k] = i.id


_inv("PA", 1, "MKO Penoplast A", "blok", 500_000, 1.0, True, True, "Penoplast")
_inv("PA2", 1, "MKO Blok A", "blok", 600_000, 0.5, True, False, "Penoplast")
_inv("KLEYA", 1, "MKO Kley A", "kg", 2_000)
_inv("QUMA", 1, "MKO Qum A", "kg", 1_000)
_inv("PB", 2, "MKO Penoplast Bega", "blok", 400_000, 1.0, True, True, "Penoplast")
_inv("PB2", 2, "MKO Blok Bega", "blok", 300_000, 0.25, True, False, "Penoplast")
_inv("QUMB", 2, "MKO Qum Bega", "l", 3_000)
for k, cid, nom, tarkib in (("RA", 1, "MKO RA", [("KLEYA", 100.0)]),
                            ("RA2", 1, "MKO RA2", [("KLEYA", 50.0), ("QUMA", 50.0)]),
                            ("RA3", 1, "MKO RA3 toza", [("KLEYA", 50.0), ("QUMA", 50.0)]),
                            ("RB", 2, "MKO RB", [("QUMB", 100.0)])):
    _r = Recipe(company_id=cid, name=nom, batch_size_kg=100.0)
    _db.add(_r)
    _db.commit()
    ID[k] = _r.id
    for ik, kg in tarkib:
        _db.add(RecipeIngredient(recipe_id=_r.id, inventory_id=ID[ik], quantity_kg=kg))
    _db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    for _rid in ("RA", "RA2", "RA3", "RB"):
        _st = services.get_or_create_loy_stock(_db, _db.get(Recipe, ID[_rid]))
        _st.stock_quantity = 0.0
_db.commit()
for k, cid in (("PRJ", 1), ("PRJB", 2)):
    _p = Project(company_id=cid, client_name=f"MKO {k}", project_name=f"MKO {k}", total_budget=0, total_paid=0)
    _db.add(_p)
    _db.commit()
    ID[k] = _p.id
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c


C = _kir("mko_a")
CB = _kir("mko_b")
_n = [0]


def so(klient, usul, url, **k):
    try:
        r = getattr(klient, usul)(url, **k)
    except Exception as e:                 # noqa: BLE001
        HOLATLAR.append((url, 599))
        return 599, f"{type(e).__name__}: {e}"
    HOLATLAR.append((url, r.status_code))
    try:
        return r.status_code, r.json()
    except Exception:                      # noqa: BLE001
        return r.status_code, r.text


def detal(cat, **k):
    _n[0] += 1
    t = {"name": f"MKO_D{_n[0]}", "category": cat, "quantity": 1, "unit_price": 50_000, "is_coated": False,
         "penoplast_id": None}
    t.update(k)
    return t


def buyurtma(kalit, items, klient=None, prj="PRJ", **k):
    t = {"project_id": ID[prj], "order_type": "product", "items": items, "loy_kg": 0}
    t.update(k)
    kod, d = so(klient or C, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
    ID[kalit] = d.get("id") if (kod == 200 and isinstance(d, dict)) else None
    ID[kalit + "_it"] = [it.get("id") for it in (d.get("items") or [])] if (kod == 200 and isinstance(d, dict)) else []
    return kod


SHAKL = {
    "profil": detal("profil", width=20, thickness=10, length=5, unit_price=20_000, penoplast_id=ID["PA"]),
    "blok": detal("blok", width=50, thickness=50, length=2, quantity=12, unit_price=90_000, penoplast_id=ID["PA2"]),
    "dona": detal("dona", quantity=4, unit_price=10_000, penoplast_id=ID["PA"]),
    "loy": {"name": "MKO_LOY", "category": "loy_sotish", "quantity": 10, "unit_price": 30_000, "is_coated": False,
            "penoplast_id": None, "recipe_id": ID["RA"]},
}
_yarat = []
for kat, d in SHAKL.items():
    for tur in ("toza", "buz"):
        _yarat.append(buyurtma(f"{kat}_{tur}", [dict(d, name=d["name"] + tur)]))
        _yarat.append(so(C, "post", f"/api/orders/{ID[f'{kat}_{tur}']}/ready")[0])
# buzishdan OLDIN toza yaratilgan qoplamali buyurtma (o'chirishda loy qaytishi uchun)
# A ning loy sotish detali — A retsepti RA2 (buzilgach ingredienti B materialiga) — ingredient to'sig'i ALOHIDA ko'rinadi (N13)
_yarat.append(buyurtma("loy_ra2", [{"name": "MKO_LOY_RA2", "category": "loy_sotish", "quantity": 10, "unit_price": 31_000,
                                    "is_coated": False, "penoplast_id": None, "recipe_id": ID["RA2"]}]))
_yarat.append(so(C, "post", f"/api/orders/{ID['loy_ra2']}/ready")[0])
_yarat.append(buyurtma("loy_old", [detal("panel", width=40, thickness=8, quantity=5, unit_price=36_000, is_coated=True,
                                         penoplast_id=ID["PA"])], recipe_id=ID["RA2"], loy_kg=10))
# B ning loy sotish detali (keyin Core bilan A retseptiga ulanadi — "ishlatilgan" ro'yxatiga chiqmasligi shart)
_yarat.append(buyurtma("b_loy", [{"name": "MKO_B_MAXFIY_DETAL", "category": "loy_sotish", "quantity": 5,
                                  "unit_price": 10_000, "is_coated": False, "penoplast_id": None,
                                  "recipe_id": ID["RB"]}], klient=CB, prj="PRJB"))

_db = SessionLocal()
_it = OrderItem.__table__
for tur in ("toza", "buz"):
    _db.execute(_it.update().where(_it.c.id == ID[f"dona_{tur}_it"][0]).values(
        width=None, thickness=None, length=None, price_per_m3=None, unit_price_for_volume=None))
    _db.execute(Order.__table__.update().where(Order.__table__.c.id == ID[f"dona_{tur}"]).values(base_price=None))
_db.execute(_it.update().where(_it.c.id == ID["profil_buz_it"][0]).values(penoplast_id=ID["PB"]))
_db.execute(_it.update().where(_it.c.id == ID["blok_buz_it"][0]).values(penoplast_id=ID["PB2"]))
_db.execute(_it.update().where(_it.c.id == ID["dona_buz_it"][0]).values(penoplast_id=ID["PB"]))
_db.execute(_it.update().where(_it.c.id == ID["loy_buz_it"][0]).values(recipe_id=ID["RB"]))
if ID.get("b_loy_it"):
    _db.execute(_it.update().where(_it.c.id == ID["b_loy_it"][0]).values(recipe_id=ID["RA2"]))
# kech99 (kmut99 N05 tahlili, (d)): harakat BLOK buyurtmasiga — profil buyurtmasida bo'lsa `_buyurtma_sarf_narxlari` B penoplastiga
# 0 narx berib, korxonasiz penoplast qidiruvini (N05) YASHIRARDI.
_db.execute(InventoryMovement.__table__.insert().values(
    company_id=1, inventory_id=ID["PB"], item_name="MKO begona harakat", movement_type="out", quantity=0.01,
    unit="blok", reason="MKO begona material harakati", order_id=ID["blok_buz"], unit_cost=None, is_brak=False,
    created_at=datetime.utcnow()))
_ri = RecipeIngredient.__table__
_db.execute(_ri.update().where(_ri.c.recipe_id == ID["RA2"], _ri.c.inventory_id == ID["QUMA"]).values(
    inventory_id=ID["QUMB"]))
_db.commit()
_db.close()

section("0 fikstura")
check("F1 fikstura: buyurtmalar va 'Tayyor' — hammasi 200", all(k == 200 for k in _yarat), _yarat)


def foyda(oid, cid=1, kesh=False):
    s = SessionLocal()
    try:
        if kesh:
            with services.hisobot_keshi(s):
                services._hk_tayyorla(s, s.query(Order).filter(Order.company_id == 1).all())
                return xavfsiz(services.calculate_order_profit, s, oid, company_id=cid)
        return xavfsiz(services.calculate_order_profit, s, oid, company_id=cid)
    finally:
        s.close()


def tan(p):
    return p.get("tan_narxi") if isinstance(p, dict) else p


def matn(p):
    return " | ".join(b.get("nomi", "") for b in p.get("breakdown", [])) if isinstance(p, dict) else str(p)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A foyda")
KUT = {"profil": 0.05 * 500_000, "blok": 2 * 0.5 * 1_200_000, "dona": 0.08 * 500_000, "loy": 10 * 2_000}
_A = {}
for kat in SHAKL:
    for tur in ("toza", "buz"):
        _A[(kat, tur)] = foyda(ID[f"{kat}_{tur}"])
for kat, v in KUT.items():
    check(f"A1 {kat} toza — tan narxi o'z materiali bilan {v:,.0f}", yaqin(tan(_A[(kat, 'toza')]), v, 1e-4),
          tan(_A[(kat, "toza")]))
for kat in SHAKL:
    p = _A[(kat, "buz")]
    check(f"A2 {kat} buzilgan (B materiali / retsepti) — tan narxi 0 (begona material hisobga kirmaydi)",
          yaqin(tan(p), 0), (tan(p), matn(p)))
    check(f"A3 {kat} buzilgan — B material nomi / narxi qatorlarda YO'Q",
          isinstance(p, dict) and "Bega" not in matn(p) and "400,000" not in matn(p) and "3,000 so'm/kg" not in matn(p),
          matn(p))
for kat in SHAKL:
    for tur in ("toza", "buz"):
        p0 = _A[(kat, tur)]
        p1 = foyda(ID[f"{kat}_{tur}"], cid=None)
        p2 = foyda(ID[f"{kat}_{tur}"], kesh=True)
        check(f"A4 {kat} {tur} — korxonasiz chaqiruv va hisobot keshi bilan AYNAN",
              yaqin(tan(p0), tan(p1)) and yaqin(tan(p0), tan(p2)) and matn(p0) == matn(p1) == matn(p2),
              (tan(p0), tan(p1), tan(p2)))
_lr2 = foyda(ID["loy_ra2"])
check("A6 loy sotish (A retsepti, ingredienti begona) — faqat Kley A: 10 kg × 50 / 100 × 2 000 = 10 000; B nomi / narxi YO'Q",
      yaqin(tan(_lr2), 10_000) and "3,000" not in matn(_lr2), (tan(_lr2), matn(_lr2)))
check("A5 profil buzilgan — hajm 0 (begona penoplast bo'yicha guruhlanmaydi)",
      isinstance(_A[("profil", "buz")], dict) and yaqin(_A[("profil", "buz")].get("volume_m3"), 0),
      _A[("profil", "buz")])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B hajm")
s = SessionLocal()
_std = services.get_default_penoplast(s, company_id=1)
_hj = {}
for kat in ("profil", "blok", "dona"):
    for tur in ("toza", "buz"):
        _hj[(kat, tur)] = xavfsiz(services._item_volume_m3, s, s.get(OrderItem, ID[f"{kat}_{tur}_it"][0]), _std)
check("B1 profil — o'lchamdan (toza = buzilgan = 0.05; material qidirilmaydi)",
      yaqin(_hj[("profil", "toza")], 0.05) and yaqin(_hj[("profil", "buz")], 0.05), _hj)
check("B2 blok — toza 2 × 0.5 = 1.0, buzilgan (B bloki) 0", yaqin(_hj[("blok", "toza")], 1.0)
      and yaqin(_hj[("blok", "buz")], 0), (_hj[("blok", "toza")], _hj[("blok", "buz")]))
check("B3 dona (narx-nisbat) — toza 40 000 / 500 000 = 0.08, buzilgan (B penoplasti) 0",
      yaqin(_hj[("dona", "toza")], 0.08) and yaqin(_hj[("dona", "buz")], 0), (_hj[("dona", "toza")], _hj[("dona", "buz")]))
_fk = xavfsiz(services._FakeItem, {"category": "dona", "quantity": 4, "unit_price": 10_000, "penoplast_id": ID["PB"]})
_fk_b = xavfsiz(services._FakeItem, {"category": "blok", "length": 2, "quantity": 12, "unit_price": 90_000,
                                     "penoplast_id": ID["PB2"]})
_v1 = xavfsiz(services._item_volume_m3, s, _fk, _std, company_id=1)
_v2 = xavfsiz(services._item_volume_m3, s, _fk, _std)
_v3 = xavfsiz(services._item_volume_m3, s, _fk_b, _std, company_id=1)
_v4 = xavfsiz(services._item_volume_m3, s, _fk, _std, company_id=2)
check("B4 soxta detal (korxonasiz obyekt) + company_id=1 — begona penoplast: dona 0, blok 0",
      yaqin(_v1, 0) and yaqin(_v3, 0), (_v1, _v3))
check("B5 soxta detal, korxona berilmagan — asl korxonasiz qidiruv (40 000 / 400 000 = 0.1)", yaqin(_v2, 0.1), _v2)
check("B6 soxta detal + company_id=2 (penoplast o'z korxonasida) — 0.1", yaqin(_v4, 0.1), _v4)
_gv = xavfsiz(services._group_volumes_by_penoplast, s, [_fk, _fk_b], company_id=1)
check("B7 `_group_volumes_by_penoplast` (A) — B penoplastlari guruhda YO'Q", isinstance(_gv, dict)
      and ID["PB"] not in _gv and ID["PB2"] not in _gv, _gv)
s.close()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C loy ingredientlari")


def ombor():
    s = SessionLocal()
    try:
        d = {k: round(float(s.get(Inventory, ID[k]).stock_quantity), 6) for k in ("KLEYA", "QUMA", "QUMB")}
        h = s.query(InventoryMovement).filter(InventoryMovement.inventory_id == ID["QUMB"]).count()
        return d, h
    finally:
        s.close()


s = SessionLocal()
_lc = xavfsiz(services.get_loy_cost_per_kg, s, ID["RA2"], company_id=1)
_lc3 = xavfsiz(services.get_loy_cost_per_kg, s, ID["RA3"], company_id=1)
s.close()
check("C1 1 kg narxi — begona ingredientsiz: 50 / 100 × 2 000 = 1 000; B nomi YO'Q",
      isinstance(_lc, dict) and yaqin(_lc.get("cost_per_kg"), 1_000)
      and all("Bega" not in b.get("name", "") for b in _lc.get("breakdown", [])), _lc)
check("C2 nazorat — toza retsept (Kley 50 + Qum A 50): 1 000 + 500 = 1 500", isinstance(_lc3, dict)
      and yaqin(_lc3.get("cost_per_kg"), 1_500), _lc3)
_s = SessionLocal()
_s.get(Inventory, ID["QUMB"]).stock_quantity = 1.0
_s.commit()
_s.close()
s = SessionLocal()
_ch = xavfsiz(services.check_loy_ingredients_for_order, s, ID["RA2"], 10, company_id=1, commit=False)
s.rollback()
s.close()
check("C3 yetishmovchilik tekshiruvi — B materiali (qoldig'i 1) xabarda YO'Q, yetarli",
      isinstance(_ch, dict) and _ch.get("enough") is True and "Bega" not in str(_ch.get("shortages")), _ch)
_o0 = ombor()
kod, d = so(C, "post", "/api/orders", json={
    "project_id": ID["PRJ"], "order_type": "product", "recipe_id": ID["RA2"], "loy_kg": 10,
    "items": [detal("panel", width=40, thickness=8, quantity=5, unit_price=35_000, is_coated=True,
                    penoplast_id=ID["PA"])]})
ID["loyli"] = d.get("id") if (kod == 200 and isinstance(d, dict)) else None
_o1 = ombor()
check("C4 qoplamali buyurtma (A retsepti, begona ingredienti bilan) — 200 (asl: 409), yetishmovchilik oynasisiz",
      kod == 200 and ID["loyli"], (kod, str(d)[:300]))
check("C5 yaratish — Kley A −5, Qum A tegilmagan, B ombori tegilmagan, B materialiga yangi harakat YO'Q",
      yaqin(_o1[0]["KLEYA"], _o0[0]["KLEYA"] - 5) and yaqin(_o1[0]["QUMA"], _o0[0]["QUMA"])
      and yaqin(_o1[0]["QUMB"], _o0[0]["QUMB"]) and _o1[1] == _o0[1], (_o0, _o1))
kod2, _ = so(C, "put", f"/api/orders/{ID['loyli']}/loy", params={"loy_kg": "16"})
_o2 = ombor()
check("C6 loy rejasi 10 → 16 — 200, Kley A −3, B tegilmagan", kod2 == 200 and yaqin(_o2[0]["KLEYA"], _o1[0]["KLEYA"] - 3)
      and yaqin(_o2[0]["QUMB"], _o1[0]["QUMB"]) and _o2[1] == _o1[1], (kod2, _o1, _o2))
kod3, _ = so(C, "post", f"/api/orders/{ID['loyli']}/ready", params={"loy_kg": "18"})
_o3 = ombor()
check("C7 'Tayyor' loy 18 (+2) — 200, Kley A −1, B tegilmagan", kod3 == 200
      and yaqin(_o3[0]["KLEYA"], _o2[0]["KLEYA"] - 1) and yaqin(_o3[0]["QUMB"], _o2[0]["QUMB"]) and _o3[1] == _o2[1],
      (kod3, _o2, _o3))
_pl = foyda(ID["loyli"])
check("C8 foyda — qoplama 18 kg × 1 000 (begona ingredientsiz), penoplast 0.16 × 500 000",
      isinstance(_pl, dict) and yaqin(tan(_pl), 18 * 1_000 + 0.16 * 500_000, 1e-4) and "Bega" not in matn(_pl), _pl)
_o4 = ombor()
kod4, _ = so(C, "delete", f"/api/orders/{ID['loy_old']}")
_o5 = ombor()
check("C9 buzishdan OLDIN yaratilgan buyurtmani o'chirish — 200 (asl: 409); Kley A +5; B tegilmagan",
      kod4 == 200 and yaqin(_o5[0]["KLEYA"], _o4[0]["KLEYA"] + 5) and yaqin(_o5[0]["QUMB"], _o4[0]["QUMB"])
      and _o5[1] == _o4[1], (kod4, _o4, _o5))
check("C10 Qum A qaytmaydi (ingredient havolasi endi begona — yechilgan qism noma'lum, taxmin qilinmaydi)",
      yaqin(_o5[0]["QUMA"], _o4[0]["QUMA"]), (_o4, _o5))
# B o'z retsepti bilan — o'z ombori
_s = SessionLocal()
_s.get(Inventory, ID["QUMB"]).stock_quantity = 1_000.0
_s.commit()
_s.close()
_ob0 = ombor()
kod5 = buyurtma("b_qoplama", [{"name": "MKO_B_panel", "category": "panel", "width": 40, "thickness": 8, "quantity": 5,
                               "unit_price": 35_000, "is_coated": True, "penoplast_id": ID["PB"]}],
                klient=CB, prj="PRJB", recipe_id=ID["RB"], loy_kg=10)
_ob1 = ombor()
check("C11 nazorat — B o'z retsepti (RB) bilan: Qum B −10 (o'z ombori), A tegilmagan",
      kod5 == 200 and yaqin(_ob1[0]["QUMB"], _ob0[0]["QUMB"] - 10) and yaqin(_ob1[0]["KLEYA"], _ob0[0]["KLEYA"])
      and _ob1[1] == _ob0[1] + 1, (kod5, _ob0, _ob1))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D sezgirlik — B narxlari")
_oy = datetime.utcnow()


def oylik():
    s = SessionLocal()
    try:
        r = xavfsiz(services.get_monthly_report, s, _oy.year, _oy.month, company_id=1)
        return r.get("sof_foyda") if isinstance(r, dict) else r
    finally:
        s.close()


def jami_blok():
    s = SessionLocal()
    try:
        r = xavfsiz(services.get_monthly_report, s, _oy.year, _oy.month, company_id=1)
        return r.get("jami_blok") if isinstance(r, dict) else r
    finally:
        s.close()


_j0 = jami_blok()
_f0 = {k: tan(foyda(ID[f"{k}_buz"])) for k in SHAKL}
_m0 = oylik()
_s = SessionLocal()
for k in ("PB", "PB2", "QUMB"):
    _x = _s.get(Inventory, ID[k])
    _x.price_per_unit = float(_x.price_per_unit) * 2
_s.commit()
_s.close()
_f1 = {k: tan(foyda(ID[f"{k}_buz"])) for k in SHAKL}
_m1 = oylik()
check("D1 B narxlari 2× — A buyurtmalari tan narxi O'ZGARMAYDI", _f0 == _f1, (_f0, _f1))
_s = SessionLocal()
for k in ("PB", "PB2"):
    _x = _s.get(Inventory, ID[k])
    _x.volume_per_unit = float(_x.volume_per_unit) * 2
_s.commit()
_s.close()
_j1 = jami_blok()
check("D4 B bloklari hajmi 2× — A oylik hisobotidagi ishlatilgan blok soni O'ZGARMAYDI", _j0 is not None and _j0 == _j1,
      (_j0, _j1))
check("D2 B narxlari 2× — A oylik sof foydasi O'ZGARMAYDI", _m0 is not None and _m0 == _m1, (_m0, _m1))
s = SessionLocal()
_lcb = xavfsiz(services.get_loy_cost_per_kg, s, ID["RA2"], company_id=1)
s.close()
check("D3 B narxlari 2× — A retseptining 1 kg narxi O'ZGARMAYDI (1 000)", isinstance(_lcb, dict)
      and yaqin(_lcb.get("cost_per_kg"), 1_000), _lcb)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E Retseptlar sahifasi")
s = SessionLocal()
try:
    _ri1 = xavfsiz(crud.get_recipe_insights, s, ID["RA2"], company_id=1)
    _ri2 = xavfsiz(crud.get_recipe_insights, s, ID["RA2"], company_id=2)
    _ri0 = xavfsiz(crud.get_recipe_insights, s, ID["RA2"])
    _ra2 = s.get(Recipe, ID["RA2"])
    _nom = sorted(i.item_name for i in _ra2.ingredients)
    _bir = sorted(i.unit for i in _ra2.ingredients)
    _rb = s.get(Recipe, ID["RB"])
    _nom_b = [i.item_name for i in _rb.ingredients]
finally:
    s.close()
check("E1 A retsepti 1 kg narxi (sahifa) — begona ingredientsiz 1 000 (asl: 2 500)", isinstance(_ri1, dict)
      and yaqin(_ri1.get("cost_per_kg"), 1_000), _ri1)
check("E2 'ishlatilgan' ro'yxatida B buyurtmasining detali YO'Q", isinstance(_ri1, dict)
      and "MKO_B_MAXFIY_DETAL" not in (_ri1.get("used_in") or []), _ri1)
check("E3 boshqa korxona nomidan (company_id=2) — A retsepti topilmaydi", isinstance(_ri2, dict)
      and _ri2.get("cost_per_kg") == 0 and _ri2.get("used_in") == [], _ri2)
check("E4 korxonasiz chaqiruv — retsept o'z korxonasi bo'yicha (1 000)", isinstance(_ri0, dict)
      and yaqin(_ri0.get("cost_per_kg"), 1_000), _ri0)
check("E5 ingredient nomi — begona material '—' (B nomi YO'Q)", _nom == sorted(["MKO Kley A", "—"]), _nom)
check("E6 ingredient birligi — begona material 'kg' (B birligi 'l' YO'Q)", _bir == ["kg", "kg"], _bir)
check("E7 B o'z retseptida o'z materiali nomi bilan", _nom_b == ["MKO Qum Bega"], _nom_b)
kod6, _html = so(C, "get", "/recipes")
check("E8 /recipes sahifasi 200, B material nomi YO'Q", kod6 == 200 and "Bega" not in str(_html), kod6)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K hisobot keshi — begona material qayta so'ralmaydi")
from sqlalchemy import event as _ev    # noqa: E402
_sanoq = [0]


def _sana(*a, **k):
    _sanoq[0] += 1


_ev.listen(engine, "before_cursor_execute", _sana)
_kk = {}
try:
    s = SessionLocal()
    try:
        with services.hisobot_keshi(s):
            services._hk_tayyorla(s, s.query(Order).filter(Order.company_id == 1).all())
            for kat in ("profil", "blok", "dona"):
                for tur in ("toza", "buz"):
                    xavfsiz(services.calculate_order_profit, s, ID[f"{kat}_{tur}"], company_id=1)
                    _sanoq[0] = 0
                    xavfsiz(services.calculate_order_profit, s, ID[f"{kat}_{tur}"], company_id=1)
                    _kk[(kat, tur)] = _sanoq[0]
    finally:
        s.close()
finally:
    _ev.remove(engine, "before_cursor_execute", _sana)
for kat in ("profil", "blok", "dona"):
    check(f"K1 {kat}: keshda 2-chaqiruv so'rovlari — buzilgan = toza (begona material keshda 'yo'q' deb eslanadi)",
          _kk.get((kat, "buz")) == _kk.get((kat, "toza")), (_kk.get((kat, "toza")), _kk.get((kat, "buz"))))
# K2: korxonasiz hisobot keshi (ikkala korxona buyurtmalari oldindan o'qilgan — B penoplasti "inv" da B qatori sifatida
# turadi) — A ning buzilgan detali uni O'QIMASLIGI shart (keshdagi qatorda korxona tekshiriladi)
_k2 = {}
s = SessionLocal()
try:
    with services.hisobot_keshi(s):
        services._hk_tayyorla(s, s.query(Order).all())
        _k2["kesh_PB"] = getattr(services._hk_ol(s, "inv", ID["PB"]), "company_id", None)
        for kat in ("profil", "dona"):
            _k2[kat] = tan(xavfsiz(services.calculate_order_profit, s, ID[f"{kat}_buz"], company_id=1))
finally:
    s.close()
check("K2 ikki korxonali kesh (B penoplasti keshda) — A buzilgan profil / dona tan narxi 0",
      _k2.get("kesh_PB") == 2 and yaqin(_k2.get("profil"), 0) and yaqin(_k2.get("dona"), 0), _k2)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("X 5xx")
_xx = [h for h in HOLATLAR if h[1] >= 500]
check(f"X1 {len(HOLATLAR)} so'rovda 5xx yo'q", not _xx, _xx[:5])

section("S statik")


def manba(obj):
    try:
        return inspect.getsource(obj)
    except Exception:                      # noqa: BLE001
        return ""


_sp = manba(services.calculate_order_profit)
_sv = manba(services._item_volume_m3)
_km = getattr(services, "_korxona_materiali", None)
_rm = getattr(services, "_retsept_materiali", None)
check("S1 `_korxona_materiali` — korxona sharti va 'begona' kesh bo'limi", _km is not None
      and "_q = _q.filter(Inventory.company_id == company_id)" in manba(_km) and '"inv_begona"' in manba(_km))
check("S2 foyda: blok va penoplast `_korxona_materiali` bilan, korxonasiz so'rov YO'Q",
      "p_blok = _korxona_materiali(db, pid_for_blok, _cid112)" in _sp and "inv_item = _korxona_materiali(db, pid, _cid112)" in _sp
      and "db.query(Inventory).filter(Inventory.id == pid).first()" not in _sp
      and "db.query(Inventory).filter(Inventory.id == pid_for_blok).first()" not in _sp)
check("S3 foyda: loy sotish retsepti korxona bilan ('retsept_k'), ingredientlar `_retsept_materiali` bilan",
      '_hk_ol(db, "retsept_k", (item.recipe_id, _lcid))' in _sp and "_lrq = _lrq.filter(Recipe.company_id == _lcid)" in _sp
      and _sp.count("_ing_inv = _retsept_materiali(ing, recipe)") == 2 and "_narx(ing.inventory)" not in _sp)
check("S3b foyda: dona hajmi — detalning O'Z korxonasi (`_item_volume_m3` standarti; ortiqcha parametr YO'Q)",
      "penoplast_narxi=_sarf_narx.get(_pid_dona))" in _sp)
check("S4 `_item_volume_m3` — company_id parametri, ikkala qidiruv `_korxona_materiali` bilan",
      "company_id=None" in _sv.split("\n")[0] and _sv.count("_korxona_materiali(db, pid, _cid_v)") == 2
      and "db.query(Inventory)" not in _sv)
_sl = {n: manba(getattr(services, n, None)) for n in ("check_loy_ingredients_for_order", "deduct_loy_ingredients",
                                                     "return_loy_ingredients", "get_loy_cost_per_kg")}
check("S5 loy ingredientlari (4 funksiya) — `_retsept_materiali`, `ing.inventory` shart sifatida YO'Q",
      all("_retsept_materiali(ing, recipe)" in v and "not ing.inventory" not in v for v in _sl.values()),
      {k: ("_retsept_materiali(ing, recipe)" in v, "not ing.inventory" not in v) for k, v in _sl.items()})
check("S6 yechish / qaytarish / tekshirish so'rovi korxona bilan",
      all("Inventory.company_id == recipe.company_id" in _sl[n] for n in
          ("check_loy_ingredients_for_order", "deduct_loy_ingredients", "return_loy_ingredients")))
check("S7 `_retsept_materiali` — retsept korxonasi bilan solishtiradi", _rm is not None
      and 'getattr(_inv, "company_id", None) != _rcid' in manba(_rm))
check("S8 `RecipeIngredient.item_name` / `unit` — `_oz_materiali` orqali",
      "_oz_materiali" in manba(models.RecipeIngredient) and "self.inventory.item_name if self.inventory" not in
      manba(models.RecipeIngredient))

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
engine.dispose()
if PG_URL:
    try:
        _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
                   isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass
sys.exit(1 if FAIL else 0)
