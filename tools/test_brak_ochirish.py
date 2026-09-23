#!/usr/bin/env python3
"""
test_brak_ochirish.py — 13-band (brak tizimi) 6-qadam darvozasi (kech45, 2026-09-23).

NIMA UCHUN KERAK (JONLI va lokal O'LCHANGAN)
--------------------------------------------
  * Buyurtma detali brakini (`POST /api/returns`, sabab "Brak") yozish penoplastni
    va (qoplama tortilgan bo'lsa) loyni — tayyor loy zaxirasi + retsept
    ingredientlari — ombordan YECHADI (`services.deduct_raw_material_for_brak`).
  * Brak yozuvini O'CHIRISH (`DELETE /api/returns/{id}`) faqat yozuvni o'chirardi:
    yechilgan xomashyo omborga QAYTMASDI va uning qiymati "Brak xarajati" da
    (`crud.get_brak_material_summary` — sof foyda ham shundan) QOLARDI.
    Jonli (kech42, 1.0r): brak 2 865 so'm — o'chirishdan keyin penoplast
    24.053652272727263 → 24.050080844155833 qoldi, sof foyda −2 865.
  * Sabab: harakatlar brak yozuviga BOG'LANMAGAN edi (faqat matn "Brak — nom").

YECHIM (texnik — Claude): `InventoryMovement.return_item_id` (FK
`return_items.id` ON DELETE SET NULL). `create_return_item` brak xomashyosini
yechayotganda sessiyaga belgi qo'yadi (`db.info["_brak_qaytarish_id"]`,
`finally` da olinadi) — `crud.log_movement` va `services` dagi to'g'ridan
penoplast harakati shu raqamni yozadi. `delete_return_item` bog'langan "out"
harakatlarining miqdorini omborga qaytaradi va harakatlarni o'chiradi (BITTA
tranzaksiya). Bog'lamsiz ESKI brak — avvalgidek (taxmin qilinmaydi).
Brak YOZISH uslubi O'ZGARMAGAN (foydalanuvchining QAT'IY sharti, kech5 9-bo'lim).

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_brak_ochirish.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_brak_ochirish.py
"""
import os
import sys
import ast
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "brak_ochirish_test"
_DB = os.path.join(tempfile.gettempdir(), "brak_ochirish_test.db")

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

from sqlalchemy import text, inspect as sa_inspect  # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Inventory, InventoryMovement,
    ActivityLog, Recipe, RecipeIngredient,
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


def taxminan(a, b, eps=1e-6):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def tartibda(src, *qismlar):
    """Qismlar matnda shu tartibda uchraydimi (`find`, topilmasa False)."""
    p = 0
    for q in qismlar:
        i = src.find(q, p)
        if i < 0:
            return False
        p = i + len(q)
    return True


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="BO Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "BO_admin", "Parol123!", UserRole.ADMIN, "BO Admin", company_id=1)
    auth.create_user(_db, "BO_admin_b", "Parol123!", UserRole.ADMIN, "BO Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="BO Mijoz", project_name="BO loyiha", total_budget=0, total_paid=0)
PRJ_B = Project(company_id=2, client_name="BO Mijoz B", project_name="BO loyiha B", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="BO Penoplast", unit="blok", stock_quantity=1000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
PENO_B = Inventory(company_id=2, item_name="BO Penoplast B", unit="blok", stock_quantity=1000,
                   price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="BO Kley", unit="kg", stock_quantity=1000,
                 price_per_unit=2_000, category="Kimyo")
_db.add_all([PRJ, PRJ_B, PENO, PENO_B, KLEY])
_db.commit()
RET = Recipe(company_id=1, name="BO Retsept", batch_size_kg=100.0)
_db.add(RET)
_db.commit()
_db.add(RecipeIngredient(recipe_id=RET.id, inventory_id=KLEY.id, quantity_kg=100.0))
_db.commit()
PRJ_ID, PRJB_ID, PENO_ID, PENOB_ID, KLEY_ID, RET_ID = (
    PRJ.id, PRJ_B.id, PENO.id, PENO_B.id, KLEY.id, RET.id)
# Tayyor loy zaxirasi — brak loyining bir qismi shundan olinadi (3 kg)
with contextlib.redirect_stdout(_quiet):
    _loy = services.get_or_create_loy_stock(_db, _db.get(Recipe, RET_ID))
_loy.stock_quantity = 3.0
_db.commit()
LOY_ID = _loy.id
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("BO_admin")
CB, _s2 = _kir("BO_admin_b")
if _s1 != 302 or _s2 != 302:
    print(f"LOGIN BO'LMADI: {_s1} / {_s2}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def buyurtma(qoplama=False, b=False):
    """API orqali YANGI buyurtma (profil, 10 dona × 100 sm = 100 metr, penoplastli).
    `qoplama=True` — detal qoplamali, retsept bog'lanadi va haqiqiy loy 100 kg
    (ORM bilan — \"Tayyor\" bosilgandagi qiymat) → (order_id, detal_id)."""
    _n[0] += 1
    nom = f"BO_D{_n[0]}"
    r = req(CB if b else C, "post", "/api/orders", json={
        "project_id": PRJB_ID if b else PRJ_ID, "order_type": "product", "items": [
            {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 100,
             "quantity": 10, "unit_price": 50_000, "is_coated": bool(qoplama),
             "penoplast_id": PENOB_ID if b else PENO_ID}]})
    oid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    d = SessionLocal()
    try:
        q = d.query(OrderItem).filter(OrderItem.name == nom)
        if oid:
            q = q.filter(OrderItem.order_id == oid)
        oi = q.order_by(OrderItem.id.desc()).first()
        if oi is None:
            raise RuntimeError(f"buyurtma yaratilmadi: {r.status_code} {r.text[:200]}")
        if qoplama:
            oi.is_coated = True
            oi.recipe_id = RET_ID
            d.get(Order, oi.order_id).actual_loy_kg = 100.0
            d.commit()
        return oi.order_id, oi.id
    finally:
        d.close()


def detal_nomi(iid):
    d = SessionLocal()
    try:
        return d.get(OrderItem, iid).name
    finally:
        d.close()


def brak(oid, iid, miqdor, qoplama_tortilgan=False, b=False):
    t = {"order_id": oid, "order_item_id": iid, "item_name": detal_nomi(iid),
         "quantity": miqdor, "unit": "metr", "reason": "Brak", "refund_amount": 0,
         "to_stock": False, "coating_applied": bool(qoplama_tortilgan)}
    r = req(CB if b else C, "post", "/api/returns", json=t)
    rid = (js(r) or {}).get("id") if (r.status_code == 200 and isinstance(js(r), dict)) else None
    return r, rid


def ochir(rid, c=None):
    return req(c or C, "delete", f"/api/returns/{rid}")


def ombor(*ids):
    d = SessionLocal()
    try:
        return tuple(round(float(d.get(Inventory, i).stock_quantity or 0), 9) for i in ids)
    finally:
        d.close()


def harakatlar(rid):
    """Shu brak yozuviga bog'langan harakatlar: [(inventory_id, turi, miqdor)]."""
    d = SessionLocal()
    try:
        if not hasattr(InventoryMovement, "return_item_id"):
            return []
        return [(m.inventory_id, m.movement_type, round(float(m.quantity), 9))
                for m in d.query(InventoryMovement).filter(
                    InventoryMovement.return_item_id == rid).order_by(InventoryMovement.id).all()]
    finally:
        d.close()


def brak_harakat_soni():
    d = SessionLocal()
    try:
        return d.query(InventoryMovement).filter(InventoryMovement.reason.like("Brak%")).count()
    finally:
        d.close()


def jami_harakat():
    d = SessionLocal()
    try:
        return d.query(InventoryMovement).count()
    finally:
        d.close()


def brak_qiymati():
    d = SessionLocal()
    try:
        return float(crud.get_brak_material_summary(d, company_id=1).get("total_value") or 0)
    finally:
        d.close()


def audit(rid):
    d = SessionLocal()
    try:
        x = d.query(ActivityLog).filter(ActivityLog.entity_type == "return",
                                        ActivityLog.entity_id == rid,
                                        ActivityLog.action == "deleted").order_by(ActivityLog.id.desc()).first()
        return (x.new_value or "") if x else ""
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════
# A. Qoplamasiz detal braki — penoplast qaytadi
# ══════════════════════════════════════════════════════════════
section("A. Qoplamasiz brak — penoplast omborga qaytadi, xarajat yo'qoladi")
try:
    O, I = buyurtma()
    p0, = ombor(PENO_ID)
    v0 = brak_qiymati()
    h_boshqa0 = jami_harakat()
    r, rid = brak(O, I, 2)
    check("A1 brak yozildi → 200", r.status_code == 200 and rid, (r.status_code, r.text[:200]))
    p1, = ombor(PENO_ID)
    check("A2 penoplast yechildi (brak yozish O'ZGARMAGAN)", p1 < p0 - 1e-9, (p0, p1))
    hs = harakatlar(rid)
    check("A3 yechilgan penoplast harakati brak yozuviga BOG'LANDI",
          len(hs) == 1 and hs[0][0] == PENO_ID and hs[0][1] == "out" and taxminan(hs[0][2], p0 - p1), hs)
    v1 = brak_qiymati()
    check("A4 brak xarajati oshdi", v1 > v0 + 1, (v0, v1))
    r = ochir(rid)
    j = js(r) or {}
    check("A5 o'chirish → 200, xomashyo_qaytdi = 1", r.status_code == 200 and j.get("xomashyo_qaytdi") == 1,
          (r.status_code, r.text[:300]))
    check("A6 penoplast AYNAN asliga qaytdi", taxminan(ombor(PENO_ID)[0], p0, 1e-9), (p0, ombor(PENO_ID)))
    check("A7 bog'langan harakatlar o'chdi", harakatlar(rid) == [], harakatlar(rid))
    check("A8 brak xarajati asliga qaytdi (sof foyda ham)", taxminan(brak_qiymati(), v0, 0.5), (v0, brak_qiymati()))
    check("A9 boshqa harakatlarga tegilmadi (jami soni asliga)", jami_harakat() == h_boshqa0, (h_boshqa0, jami_harakat()))
    a = audit(rid)
    check("A10 jurnalda \"brak xomashyosi omborga qaytdi\" va material nomi",
          "brak xomashyosi omborga qaytdi" in a and "BO Penoplast" in a, a)
except Exception as e:                     # noqa: BLE001
    check("A bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# B. Qoplama tortilgan brak — penoplast + tayyor loy + ingredient qaytadi
# ══════════════════════════════════════════════════════════════
section("B. Qoplama tortilgandan keyingi brak — uch xil xomashyo")
try:
    O, I = buyurtma(qoplama=True)
    s0 = ombor(PENO_ID, LOY_ID, KLEY_ID)
    v0 = brak_qiymati()
    r, rid = brak(O, I, 10, qoplama_tortilgan=True)
    check("B1 brak yozildi → 200", r.status_code == 200 and rid, (r.status_code, r.text[:200]))
    s1 = ombor(PENO_ID, LOY_ID, KLEY_ID)
    # 100 kg loy / 100 metr × 10 metr = 10 kg: 3 kg tayyor loydan, 7 kg retseptdan (kley 7 kg)
    check("B2 yechildi: penoplast kamaydi, tayyor loy 3 → 0, kley −7",
          s1[0] < s0[0] - 1e-9 and taxminan(s1[1], 0) and taxminan(s0[2] - s1[2], 7.0), (s0, s1))
    hs = harakatlar(rid)
    check("B3 uchala harakat ham brak yozuviga bog'landi",
          sorted(h[0] for h in hs) == sorted([PENO_ID, LOY_ID, KLEY_ID]) and all(h[1] == "out" for h in hs), hs)
    r = ochir(rid)
    j = js(r) or {}
    check("B4 o'chirish → 200, xomashyo_qaytdi = 3", r.status_code == 200 and j.get("xomashyo_qaytdi") == 3,
          (r.status_code, r.text[:300]))
    s2 = ombor(PENO_ID, LOY_ID, KLEY_ID)
    check("B5 penoplast, tayyor loy, kley — AYNAN asliga", all(taxminan(a, b, 1e-9) for a, b in zip(s0, s2)), (s0, s2))
    check("B6 harakatlar o'chdi, brak xarajati asliga",
          harakatlar(rid) == [] and taxminan(brak_qiymati(), v0, 0.5), (harakatlar(rid), v0, brak_qiymati()))
    a = audit(rid)
    check("B7 jurnalda uchala material", all(n in a for n in ("BO Penoplast", "BO Kley", "Tayyor loy")), a)
except Exception as e:                     # noqa: BLE001
    check("B bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# C. Qoplamali detal, lekin qoplamagacha brak — faqat penoplast
# ══════════════════════════════════════════════════════════════
section("C. Qoplamagacha brak (loy tortilmagan)")
try:
    O, I = buyurtma(qoplama=True)
    s0 = ombor(PENO_ID, LOY_ID, KLEY_ID)
    r, rid = brak(O, I, 5, qoplama_tortilgan=False)
    hs = harakatlar(rid)
    check("C1 faqat penoplast yechildi va bog'landi", r.status_code == 200 and [h[0] for h in hs] == [PENO_ID], (r.status_code, hs))
    r = ochir(rid)
    check("C2 o'chirish → hammasi asliga", r.status_code == 200 and all(
        taxminan(a, b, 1e-9) for a, b in zip(s0, ombor(PENO_ID, LOY_ID, KLEY_ID))), (s0, ombor(PENO_ID, LOY_ID, KLEY_ID)))
except Exception as e:                     # noqa: BLE001
    check("C bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# D. ESKI (bog'lamsiz) brak — avvalgidek, taxmin qilinmaydi
# ══════════════════════════════════════════════════════════════
section("D. Yangilanishdan oldingi brak — xomashyo qaytmaydi")
try:
    O, I = buyurtma()
    r, rid = brak(O, I, 3)
    p1, = ombor(PENO_ID)
    n1 = brak_harakat_soni()
    d = SessionLocal()
    try:
        if hasattr(InventoryMovement, "return_item_id"):
            d.query(InventoryMovement).filter(InventoryMovement.return_item_id == rid).update(
                {InventoryMovement.return_item_id: None}, synchronize_session=False)
            d.commit()
    finally:
        d.close()
    r = ochir(rid)
    j = js(r) or {}
    check("D1 o'chirish → 200, xomashyo_qaytdi = 0", r.status_code == 200 and j.get("xomashyo_qaytdi", 0) == 0,
          (r.status_code, r.text[:300]))
    check("D2 penoplast O'ZGARMADI, eski harakat QOLDI", taxminan(ombor(PENO_ID)[0], p1, 1e-9) and brak_harakat_soni() == n1,
          (p1, ombor(PENO_ID), n1, brak_harakat_soni()))
except Exception as e:                     # noqa: BLE001
    check("D bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# E. Boshqa sabablar va boshqa harakatlar — tegilmaydi
# ══════════════════════════════════════════════════════════════
section("E. Brakdan boshqa qaytarish / boshqa harakatlar")
try:
    O, I = buyurtma()
    h0 = jami_harakat()
    p0, = ombor(PENO_ID)
    t = {"order_id": O, "order_item_id": I, "item_name": detal_nomi(I), "quantity": 2, "unit": "metr",
         "reason": "Mijoz iltimosi", "refund_amount": 0, "to_stock": False}
    r = req(C, "post", "/api/returns", json=t)
    rid = (js(r) or {}).get("id")
    check("E1 brakdan boshqa qaytarish harakat yaratmaydi", r.status_code == 200 and harakatlar(rid) == [] and jami_harakat() == h0,
          (r.status_code, harakatlar(rid), h0, jami_harakat()))
    r = ochir(rid)
    check("E2 o'chirish → 200, xomashyo_qaytdi = 0, ombor o'zgarmadi",
          r.status_code == 200 and (js(r) or {}).get("xomashyo_qaytdi", 0) == 0 and taxminan(ombor(PENO_ID)[0], p0, 1e-9),
          (r.status_code, r.text[:200], p0, ombor(PENO_ID)))
    # Sessiya belgisi brakdan KEYIN qolmaydi — shu sessiyadagi keyingi chiqim bog'lanmaydi
    d = SessionLocal()
    try:
        from schemas import ReturnItemCreate
        O2, I2 = buyurtma()
        with contextlib.redirect_stdout(_quiet):
            it = crud.create_return_item(d, ReturnItemCreate(
                order_id=O2, order_item_id=I2, item_name=detal_nomi(I2), quantity=1.0, unit="metr",
                reason="Brak", refund_amount=0, to_stock=False), company_id=1)
        check("E3 sessiyada belgi QOLMADI", "_brak_qaytarish_id" not in d.info, dict(d.info))
        crud.log_movement(d, KLEY_ID, "BO Kley", movement_type="out", quantity=1.5, unit="kg",
                          reason="E3 boshqa chiqim", company_id=1)
        d.commit()
        m = d.query(InventoryMovement).filter(InventoryMovement.reason == "E3 boshqa chiqim").first()
        check("E4 keyingi chiqim brakka BOG'LANMADI", m is not None and getattr(m, "return_item_id", None) is None,
              getattr(m, "return_item_id", "yo'q"))
        check("E5 crud orqali yozilgan brakda ham harakat bog'landi", len(harakatlar(it.id)) == 1, harakatlar(it.id))
    finally:
        d.close()
    # Brak xomashyosini yechish yiqilsa ham belgi olib tashlanadi (finally)
    d = SessionLocal()
    _asl = services.deduct_raw_material_for_brak
    try:
        def _yiqil(*a, **k):
            raise RuntimeError("sinov: yechish yiqildi")
        services.deduct_raw_material_for_brak = _yiqil
        O3, I3 = buyurtma()
        try:
            with contextlib.redirect_stdout(_quiet):
                crud.create_return_item(d, ReturnItemCreate(
                    order_id=O3, order_item_id=I3, item_name=detal_nomi(I3), quantity=1.0, unit="metr",
                    reason="Brak", refund_amount=0, to_stock=False), company_id=1)
        except RuntimeError:
            pass
        check("E6 yechish yiqilganda ham belgi olib tashlandi", "_brak_qaytarish_id" not in d.info, dict(d.info))
    finally:
        services.deduct_raw_material_for_brak = _asl
        d.rollback()
        d.close()
except Exception as e:                     # noqa: BLE001
    check("E bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# T. Korxona chegarasi
# ══════════════════════════════════════════════════════════════
section("T. Korxona (tenant)")
try:
    O, I = buyurtma()
    p0, = ombor(PENO_ID)
    r, rid = brak(O, I, 2)
    p1, = ombor(PENO_ID)
    r = ochir(rid, CB)
    check("T1 begona korxona A ning brakini o'chira olmaydi (404), hech narsa o'zgarmadi",
          r.status_code == 404 and taxminan(ombor(PENO_ID)[0], p1, 1e-9) and len(harakatlar(rid)) == 1,
          (r.status_code, p1, ombor(PENO_ID), harakatlar(rid)))
    r = ochir(rid)
    check("T2 o'z korxonasi o'chiradi → asliga", r.status_code == 200 and taxminan(ombor(PENO_ID)[0], p0, 1e-9),
          (r.status_code, p0, ombor(PENO_ID)))
    # B korxonasi braki: o'z penoplasti yechiladi va qaytadi, A ombori tegilmaydi
    OB, IB = buyurtma(b=True)
    pa0, pb0 = ombor(PENO_ID, PENOB_ID)
    r, ridb = brak(OB, IB, 2, b=True)
    pb1, = ombor(PENOB_ID)
    r = ochir(ridb, CB)
    check("T3 B braki: B penoplasti yechilib qaytdi, A ombori tegilmadi",
          pb1 < pb0 - 1e-9 and r.status_code == 200 and taxminan(ombor(PENOB_ID)[0], pb0, 1e-9)
          and taxminan(ombor(PENO_ID)[0], pa0, 1e-9), (pb0, pb1, ombor(PENOB_ID), pa0, ombor(PENO_ID)))
    # Harakatni begona korxona brak yozuviga bog'lash — yozishdayoq rad
    O, I = buyurtma()
    r, rid_a = brak(O, I, 1)
    d = SessionLocal()
    rad = False
    try:
        d.add(InventoryMovement(company_id=2, inventory_id=PENOB_ID, item_name="BO Penoplast B",
                                movement_type="out", quantity=0.1, unit="blok", reason="T4",
                                return_item_id=rid_a))
        d.commit()
    except Exception:                      # noqa: BLE001
        rad = True
        d.rollback()
    finally:
        d.close()
    check("T4 B korxona harakatini A brakiga bog'lash — RAD (_TENANT_REFS)", rad)
    ochir(rid_a)
except Exception as e:                     # noqa: BLE001
    check("T bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# M. Migratsiya
# ══════════════════════════════════════════════════════════════
section("M. Migratsiya")
try:
    _i = sa_inspect(engine)
    ust = {c["name"] for c in _i.get_columns("inventory_movements")}
    ind = {ix["name"] for ix in _i.get_indexes("inventory_movements")}
    check("M1 ustun va indeks bor", "return_item_id" in ust and "ix_inventory_movements_return_item_id" in ind, (ust, ind))
    with engine.connect() as c:
        c.execute(text("DROP INDEX IF EXISTS ix_inventory_movements_return_item_id"))
        c.commit()
    with contextlib.redirect_stdout(_quiet):
        getattr(main, "_migrate_brak_harakat")()
    ind = {ix["name"] for ix in sa_inspect(engine).get_indexes("inventory_movements")}
    check("M2 migratsiya indeksni qayta yaratadi (idempotent)", "ix_inventory_movements_return_item_id" in ind, ind)
    if PG_URL:
        with engine.connect() as c:
            k = c.execute(text(
                "SELECT c.confdeltype FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey) "
                "WHERE t.relname = 'inventory_movements' AND c.contype = 'f' "
                "AND a.attname = 'return_item_id'")).first()
        check("M3 PG: chet el kaliti ON DELETE SET NULL", k is not None and k[0] == "n", k)
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    check("M4 migratsiya modul darajasida, e'londan KEYIN chaqiriladi",
          tartibda(src, "def _migrate_brak_harakat", "\n_migrate_brak_harakat()"), "")
except Exception as e:                     # noqa: BLE001
    check("M bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════
# S. Statik
# ══════════════════════════════════════════════════════════════
section("S. Statik")
try:
    csrc = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
    ssrc = open(os.path.join(ROOT, "services.py"), encoding="utf-8").read()
    ast.parse(csrc)
    t = csrc[csrc.find("def create_return_item"):]
    t = t[:t.find("\ndef ", 10)]
    check("S1 create_return_item: belgi → yechish → finally olish",
          tartibda(t, 'db.info["_brak_qaytarish_id"] = item.id', "try:", "deduct_raw_material_for_brak",
                   "finally:", 'db.info.pop("_brak_qaytarish_id"'), "")
    lm = csrc[csrc.find("def log_movement"):]
    lm = lm[:lm.find("\ndef ", 10)]
    check("S2 log_movement faqat \"out\" ni bog'laydi", 'db.info.get("_brak_qaytarish_id") if movement_type == "out"' in lm
          and "return_item_id=_brak_rid" in lm, "")
    dd = ssrc[ssrc.find("def deduct_raw_material_for_brak"):]
    dd = dd[:dd.find("\ndef ", 10)]
    check("S3 services penoplast harakati ham bog'lanadi", 'return_item_id=db.info.get("_brak_qaytarish_id")' in dd, "")
    dl = csrc[csrc.find("def delete_return_item"):]
    dl = dl[:dl.find("\ndef ", 10)]
    check("S4 delete_return_item: xomashyo qaytarish — korxona filtri va FOR UPDATE, yozuv o'chirilishidan OLDIN",
          tartibda(dl, "_IM4.return_item_id == item.id", "_IM4.company_id == _cid", "Inventory.company_id == _cid",
                   ".with_for_update()", "db.delete(_h)", "db.delete(item)"), "")
    check("S5 delete_return_item BITTA commit", dl.count("db.commit()") == 1, dl.count("db.commit()"))
except Exception as e:                     # noqa: BLE001
    check("S bo'limi QULAMADI", False, f"{type(e).__name__}: {e}")


print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
