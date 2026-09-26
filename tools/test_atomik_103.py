#!/usr/bin/env python3
"""
test_atomik_103.py — kech84 darvozasi (2026-09-27, 103-band): YOZADIGAN endpointlar atomik — nosozlik bo'lsa
baza O'ZGARMAYDI, qayta urinish ishni BIR marta bajaradi.

O'LCHANGAN (asl kod `2170432` (zip 78), `work/probe103.py`, SQLite = PG 16 AYNAN, 149 dan 39 yiqilish):
endpoint tanasidagi yordamchilar (`crud.create_order`, `purchase_stock`, `deduct_loy_ingredients`, ...) HAR BIRI
o'zi saqlardi. Keyingi qadam yiqilsa birinchi qism bazada QOLARDI, foydalanuvchi qayta bossa ikkinchi marta
yozilardi: A buyurtma yaratish — 2 buyurtma, kley -20 (kutilgan -10); D «Tayyor» — loy yechilgan, avto yuk yo'q,
qayta urinish 400; E loy rejasi — kley 2x; F xarid — ombor +20, xarid 2, transport 2000; J brak, K / L / M
tayyor mahsulot — xomashyo 2x; N tayyor mahsulotni o'chirish — loy 2x qaytadi; O kirim hujjati — 2x.

TUZATISH: 10 endpoint tanasining yozadigan qismi `crud.bitta_tranzaksiya(db)` ichida (blokda `commit` -> `flush`,
oxirida BITTA commit, istalgan xatoda rollback); rad javobi (400) ham blok ichida; Telegram / PDF — blokdan keyin;
`POST /api/returns` — blokdan keyin `db.refresh` (javob shakli avvalgidek).

K84-1 (shu o'lchovda topildi, asl kodda ham): 8 s ichida AYNAN shunday tarkibli buyurtma qayta yuborilsa (ikki marta
bosish) `crud.create_order` mavjudini `_is_duplicate_submit` belgisi bilan qaytaradi, lekin `api_create_order`
penoplastni YANA yechardi (bitta buyurtma, penoplast -0.2). Belgi tekshiruvi 2026-08-22 da bor edi, `abb2044` da
tushib qolgan — qayta tiklandi (takrorda ombor / Telegram — hech narsa).

Bo'limlar: A D E F J K L M N O — har endpoint: nazorat + har nosozlik nuqtasi ikki rejimda (funksiya chaqirilishi
bilan xato / asl ishidan KEYIN xato): chaqirildi, javob xato, butun baza barmoq izi O'ZGARMAGAN, qayta urinish
2xx va jami o'zgarish nazorat bilan AYNAN; T — javob shakli (T1) va 8 s takror-yuborish himoyasi (T2);
H — statik (AST): yozuvchi chaqiruvlar blok ICHIDA, Telegram / PDF blokdan TASHQARIDA; takror belgisi.

Ishlatish:
    python3 tools/test_atomik_103.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_atomik_103.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "atomik_103_test"
_T = tempfile.mkdtemp(prefix="atomik_103_")
_DB = os.path.join(_T, "atomik_103_test.db")

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

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, OrderItem,
    Recipe, RecipeIngredient, Master,
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


def xabar(r):
    d = js(r)
    if isinstance(d, dict):
        det = d.get("detail", d)
        if isinstance(det, dict):
            return str(det.get("message") or det)
        return str(det)
    return str(getattr(r, "text", ""))[:300]


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
    auth.create_user(_db, "TY_admin", "Parol123!", UserRole.ADMIN, "TY Admin", company_id=1)
PRJ = Project(company_id=1, client_name="TY Mijoz", project_name="TY loyiha", total_budget=0, total_paid=0)
TOSH = Inventory(company_id=1, item_name="TY Tosh", unit="kg", stock_quantity=1_000_000, price_per_unit=1_000,
                 category="Kimyo")
PENO = Inventory(company_id=1, item_name="TY Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TY Kley", unit="kg", stock_quantity=10_000, price_per_unit=2_000,
                 category="Kimyo")
_db.add_all([PRJ, TOSH, PENO, KLEY])
_db.flush()
REC = Recipe(company_id=1, name="TY retsept", batch_size_kg=100.0)
_db.add(REC)
_db.flush()
_db.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
USTA = Master(company_id=1, name="TY Usta", phone="+998900007575")
_db.add(USTA)
_db.commit()
ID = {"PRJ": PRJ.id, "TOSH": TOSH.id, "PENO": PENO.id, "KLEY": KLEY.id, "REC": REC.id, "USTA": USTA.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "TY_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "TY Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Asosiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["TOSH"], "quantity": 3}]})) or {}).get("id")
print("PT", PT, "BOM", BOM)

_n = [0]


def nom(p="TY_D"):
    _n[0] += 1
    return f"{p}{_n[0]}"


def detal_idlar(oid):
    s = SessionLocal()
    try:
        return [x[0] for x in s.query(OrderItem.id).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        s.close()


def _yarat(tana):
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    if not oid:
        return None, None
    ids = detal_idlar(oid)
    return oid, (ids[0] if ids else None)




# ══════════════════════════════════════════════════════════════
# kech84 (103-band) — yozadigan endpointlar ATOMIK: nosozlik bo'lsa baza O'ZGARMAYDI, qayta urinish
# natijasi nosozliksiz so'rov bilan AYNAN (ish BIR marta bajariladi).
# ══════════════════════════════════════════════════════════════
import ast as _ast                                  # noqa: E402
import hashlib as _hl                               # noqa: E402
from sqlalchemy import select as _sel               # noqa: E402
from database import engine as _eng                 # noqa: E402
import models as _models                            # noqa: E402
from models import Supplier as _Supplier            # noqa: E402

_s0 = SessionLocal()
_SUP = _Supplier(company_id=1, name="TA Taminotchi")
_s0.add(_SUP)
_s0.commit()
ID["SUP"] = _SUP.id
_s0.close()

# Xato / sessiya jadvallari — so'rov xatosida yozilishi TABIIY (log_error, login)
_CHETLA = {"error_logs", "login_history", "login_attempts", "user_sessions", "employee_sessions", "sessions"}


def barmoq():
    """Har jadval: qatorlar soni + to'liq mazmun MD5."""
    natija = {}
    with _eng.connect() as c:
        for t in _models.Base.metadata.sorted_tables:
            if t.name in _CHETLA:
                continue
            try:
                rows = c.execute(_sel(t)).fetchall()
            except Exception as e:             # noqa: BLE001
                natija[t.name] = ("XATO", str(e)[:80])
                continue
            satr = sorted(repr(tuple(r)) for r in rows)
            natija[t.name] = (len(satr), _hl.md5("\n".join(satr).encode()).hexdigest())
    return natija


def olcham():
    """Biznes o'lchamlari: qoldiqlar va pul / yozuv yig'indilari."""
    from sqlalchemy import text as _t
    q = {}
    with _eng.connect() as c:
        for k, i in (("peno", ID["PENO"]), ("kley", ID["KLEY"]), ("tosh", ID["TOSH"])):
            q[k] = round(float(c.execute(_t("select stock_quantity from inventory where id = :i"), {"i": i}).scalar() or 0), 6)
        for k, sql in (("buyurtma", "select count(*) from orders"),
                       ("tolov", "select count(*) from payments"),
                       ("xarid", "select count(*) from inventory_purchases"),
                       ("tam_tolov", "select coalesce(sum(amount), 0) from supplier_payments"),
                       ("transport", "select coalesce(sum(amount), 0) from transport_expenses"),
                       ("yuk", "select count(*) from deliveries"),
                       ("tm", "select count(*) from finished_products"),
                       ("yoqotish", "select count(*) from finished_product_losses"),
                       ("qaytarish", "select count(*) from return_items"),
                       ("harakat", "select count(*) from inventory_movements")):
            q[k] = round(float(c.execute(_t(sql)).scalar() or 0), 4)
    return q


def delta(a, b):
    return {k: round(b[k] - a[k], 6) for k in a if round(b[k] - a[k], 6) != 0}


def ozgargan(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


_MOD = {"crud": crud, "services": services}


def _ok(r):
    return 200 <= r.status_code < 300


def sinov(ssen, tayyorla, amal, nuqtalar):
    """ssen — nom; tayyorla() -> ctx; amal(ctx) -> javob; nuqtalar — [(modul, funksiya)].

    Har nuqta ikki rejimda: "oldin" — funksiya chaqirilishi bilan xato; "keyin" — asl ishi bajarilib,
    so'ng xato (o'zi saqlagan yordamchi). Har birida: chaqirildi, javob 2xx EMAS, baza (butun barmoq izi)
    O'ZGARMAGAN, nosozliksiz qayta urinish 2xx va jami o'zgarish nazorat bilan AYNAN."""
    section(ssen)
    ctx = tayyorla()
    b0 = barmoq()
    o0 = olcham()
    r = amal(ctx)
    b1 = barmoq()
    nazorat_d = delta(o0, olcham())
    check(f"{ssen}: nazorat (nosozliksiz) 2xx (kod {r.status_code})", _ok(r), xabar(r))
    check(f"{ssen}: nazorat bazani o'zgartirdi ({nazorat_d})", bool(ozgargan(b0, b1)) and bool(nazorat_d))
    for (m, nm) in nuqtalar:
        for rejim in ("oldin", "keyin"):
            kalit = f"{ssen} | {rejim} | {m}.{nm}"
            modul = _MOD.get(m)
            asl = getattr(modul, nm, None) if modul is not None else None
            if not callable(asl):
                check(f"{kalit}: funksiya mavjud", False, "modulda yo'q")
                continue
            ctx = tayyorla()
            b0 = barmoq()
            o0 = olcham()
            chaqirildi = [0]

            def _f(*a, _asl=asl, _nm=nm, _r=rejim, **k):
                chaqirildi[0] += 1
                if _r == "keyin":
                    _asl(*a, **k)
                raise RuntimeError(f"NOSOZLIK_{_r.upper()}({_nm})")
            setattr(modul, nm, _f)
            try:
                r = amal(ctx)
            finally:
                setattr(modul, nm, asl)
            b1 = barmoq()
            oz = ozgargan(b0, b1)
            d_xato = delta(o0, olcham())
            check(f"{kalit}: nosozlik nuqtasi chaqirildi", chaqirildi[0] > 0, "chaqirilmadi — sinov ma'nosiz")
            check(f"{kalit}: javob xato (kod {r.status_code})", not _ok(r), xabar(r))
            check(f"{kalit}: xatodan keyin baza O'ZGARMAGAN", not oz, f"o'zgargan: {oz} {d_xato}")
            r2 = amal(ctx)
            d_qayta = delta(o0, olcham())
            check(f"{kalit}: qayta urinish 2xx (kod {r2.status_code})", _ok(r2), xabar(r2))
            check(f"{kalit}: qayta urinishdan keyin jami o'zgarish = nazorat (BIR marta)",
                  d_qayta == nazorat_d, f"qayta {d_qayta} | nazorat {nazorat_d}")


def qoplamali_tana(loy=10.0, uzun=10, draft=False):
    return {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": loy, "recipe_id": ID["REC"],
            "master_id": ID["USTA"], "is_draft": draft,
            "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": uzun,
                       "quantity": 10, "unit_price": 50_000, "is_coated": True, "penoplast_id": ID["PENO"],
                       "recipe_id": ID["REC"]}]}


def yangi_qoplamali(draft=False):
    oid, iid = _yarat(qoplamali_tana(draft=draft))
    return {"oid": oid, "iid": iid}


_summa = [1000]


def summa():
    _summa[0] += 7
    return _summa[0]


def _j_tayyor():
    c = yangi_qoplamali()
    c["tana"] = {"order_id": c["oid"], "order_item_id": c["iid"], "item_name": nom("brak"), "quantity": 1,
                 "unit": "metr", "reason": "Brak", "refund_amount": 0, "to_stock": False, "coating_applied": True}
    return c


def _tm_tana():
    return {"name": nom("TM"), "category": "profil", "is_coated": True, "penoplast_id": ID["PENO"],
            "price_per_m3": None, "unit_price": 100000, "recipe_id": ID["REC"], "notes": "t103",
            "width": 10, "thickness": 10, "length": 10, "quantity": 5, "loy_kg": 5}


def _tm_id(r):
    d = js(r) or {}
    if not isinstance(d, dict):
        return None
    return d.get("product_id") or d.get("id") or d.get("finished_product_id")


def _tm_bor():
    r = req(C, "post", "/api/finished/produce", json=_tm_tana())
    return {"fp": _tm_id(r), "k": r.status_code}


# Nosozlik nuqtalari — tuzatishdan OLDINGI kodning (zip 78) endpoint zanjiridagi, CHAQIRILADIGAN va xato
# javob beradigan HAR funksiya (`work/skan103.py` + `work/probe103.py`, kech83 o'lchovi; `crud.log_error` /
# chaqirilmaydigan / xatosi yutiladigan `crud.log_activity` — tashqarida).
NUQTALAR = {'A': [('services', 'check_loy_ingredients_for_order'),
       ('services', 'get_or_create_loy_stock'),
       ('crud', 'create_order'),
       ('services', 'deduct_loy_ingredients'),
       ('services', 'take_loy_from_stock'),
       ('crud', 'log_movement'),
       ('services', 'deduct_inventory_for_order')],
 'D': [('services', 'complete_order'),
       ('services', 'deduct_loy_ingredients'),
       ('services', 'take_loy_from_stock'),
       ('services', 'get_or_create_loy_stock'),
       ('crud', 'log_movement'),
       ('crud', 'create_delivery')],
 'E': [('crud', 'update_order_loy'),
       ('services', 'adjust_loy_diff'),
       ('services', 'deduct_loy_ingredients'),
       ('services', 'take_loy_from_stock'),
       ('services', 'get_or_create_loy_stock'),
       ('crud', 'log_movement')],
 'F': [('crud', 'purchase_stock'),
       ('crud', '_purchase_stock_no_commit'),
       ('crud', 'log_movement'),
       ('crud', 'create_transport_expense'),
       ('crud', 'create_supplier_payment')],
 'J': [('crud', 'create_return_item'),
       ('services', 'deduct_raw_material_for_brak'),
       ('crud', 'log_movement'),
       ('services', 'deduct_loy_ingredients'),
       ('services', 'take_loy_from_stock'),
       ('services', 'get_or_create_loy_stock')],
 'K': [('crud', 'produce_finished_product'), ('crud', 'log_movement'), ('services', 'deduct_loy_ingredients')],
 'L': [('crud', 'add_to_production'), ('crud', 'log_movement'), ('services', 'deduct_loy_ingredients')],
 'M': [('crud', 'record_finished_product_production_brak'),
       ('crud', 'log_movement'),
       ('crud', '_ishlab_chiqarish_braki_xomashyo'),
       ('services', 'deduct_loy_ingredients')],
 'N': [('crud', 'delete_finished_product'), ('crud', 'log_movement'), ('services', 'return_loy_ingredients')],
 'O': [('crud', 'create_inventory_receipt'), ('crud', '_purchase_stock_no_commit'), ('crud', 'log_movement')]}

# A — buyurtma yaratish (qoplamali, loy 10)
sinov("A POST /api/orders", lambda: {},
      lambda c: req(C, "post", "/api/orders", json=qoplamali_tana(), params={"confirm_shortage": "true"}),
      NUQTALAR["A"])
# D — «Tayyor» (loy 12 — rejadan 2 kg ko'p; avto yuk xati)
sinov("D POST /api/orders/{id}/ready", yangi_qoplamali,
      lambda c: req(C, "post", f"/api/orders/{c['oid']}/ready", params={"loy_kg": "12"}),
      NUQTALAR["D"])
# E — loy rejasini o'zgartirish (10 -> 15)
sinov("E PUT /api/orders/{id}/loy", yangi_qoplamali,
      lambda c: req(C, "put", f"/api/orders/{c['oid']}/loy", params={"loy_kg": "15"}),
      NUQTALAR["E"])
# F — xarid (nasiya + hoziroq to'lov + transport); har tayyorlovda BOSHQA narx (8 s takror himoyasi)
sinov("F POST /api/inventory/{id}/purchase",
      lambda: {"tana": {"quantity": 10, "price_per_unit": 2000 + summa(), "supplier_id": ID["SUP"],
                        "paid_now": 5000, "transport_payer": "self", "transport_cost": 1000}},
      lambda c: req(C, "post", f"/api/inventory/{ID['KLEY']}/purchase", json=c["tana"]),
      NUQTALAR["F"])
# J — brak (qoplamali detal, 1 metr, qoplama surtilgan)
sinov("J POST /api/returns", _j_tayyor, lambda c: req(C, "post", "/api/returns", json=c["tana"]),
      NUQTALAR["J"])
# K — tayyor mahsulot ishlab chiqarish (qoplamali, loy 5)
sinov("K POST /api/finished/produce", lambda: {"tana": _tm_tana()},
      lambda c: req(C, "post", "/api/finished/produce", json=c["tana"]),
      NUQTALAR["K"])
# L — tayyor mahsulotga qo'shish
sinov("L POST /api/finished/{id}/add", _tm_bor,
      lambda c: req(C, "post", f"/api/finished/{c['fp']}/add", json={"quantity": 5}),
      NUQTALAR["L"])
# M — ishlab chiqarish braki
sinov("M POST /api/finished/production-brak", _tm_bor,
      lambda c: req(C, "post", "/api/finished/production-brak", json={"finished_product_id": c["fp"], "brak_qty": 1}),
      NUQTALAR["M"])
# N — tayyor mahsulotni o'chirish (jarayonda — loy / penoplast qaytadi)
sinov("N DELETE /api/finished/{id}", _tm_bor, lambda c: req(C, "delete", f"/api/finished/{c['fp']}"),
      NUQTALAR["N"])
# O — kirim hujjati (nasiya + hoziroq to'lov)
sinov("O POST /api/inventory/receipt",
      lambda: {"tana": {"items": [{"inventory_id": ID["KLEY"], "quantity": 3, "price_per_unit": 1200 + summa(),
                                   "notes": "t103"}],
                        "supplier_id": ID["SUP"], "document_number": nom("KIRIM"), "paid_now": 1000}},
      lambda c: req(C, "post", "/api/inventory/receipt", json=c["tana"]),
      NUQTALAR["O"])

# ── T — o'ramdan keyin ham avvalgi xulq ────────────────────────────────────────────────────
section("T — javob shakli va takror-yuborish himoyasi")
# T1 — POST /api/returns javobi (ORM obyekti) to'liq: blok oxiridagi saqlash obyektni eskirtiradi — yangilanmasa
# FastAPI javobi maydonlarsiz chiqardi.
_c = _j_tayyor()
_r = req(C, "post", "/api/returns", json=_c["tana"])
_d = js(_r) if _ok(_r) else None
_d = _d if isinstance(_d, dict) else {}
check("T1 POST /api/returns 2xx", _ok(_r), xabar(_r))
check("T1 javobda id (son) bor", isinstance(_d.get("id"), int), str(_d)[:200])
check("T1 javobda order_id = buyurtma, reason = Brak",
      _d.get("order_id") == _c["oid"] and _d.get("reason") == "Brak", str(_d)[:200])
check("T1 javobda refund_amount kaliti bor (brak tannarxi)", "refund_amount" in _d, str(_d)[:200])
# T2 (K84-1) — buyurtma yaratish: AYNAN bir xil tana ketma-ket ikki marta (8 s takror himoyasi) — bitta
# buyurtma, ombor BIR marta. O'LCHANGAN: asl kodda (zip 78) ikkinchi so'rov penoplastni YANA yechardi (-0.2).
_t = qoplamali_tana()
_o0 = olcham()
_r1 = req(C, "post", "/api/orders", json=_t, params={"confirm_shortage": "true"})
_d1 = delta(_o0, olcham())
_r2 = req(C, "post", "/api/orders", json=_t, params={"confirm_shortage": "true"})
_d2 = delta(_o0, olcham())
_j1 = js(_r1) if _ok(_r1) else {}
_j2 = js(_r2) if _ok(_r2) else {}
check("T2 ikkala so'rov 2xx", _ok(_r1) and _ok(_r2), xabar(_r2))
check("T2 ikkinchi so'rov MAVJUD buyurtmani qaytardi (id bir xil)",
      isinstance(_j1, dict) and isinstance(_j2, dict) and _j1.get("id") and _j1.get("id") == _j2.get("id"),
      f"{(_j1 or {}).get('id')} / {(_j2 or {}).get('id')}")
check("T2 buyurtma +1, ombor BIR marta (ikkinchi so'rov hech narsa o'zgartirmadi)",
      _d1.get("buyurtma") == 1 and _d2 == _d1, f"birinchi {_d1} | ikkalasi {_d2}")

# ── H — statik: har endpointda yozadigan chaqiruvlar `crud.bitta_tranzaksiya` bloki ICHIDA, tashqi ta'sirlar
# (Telegram, PDF) — blokdan TASHQARIDA ────────────────────────────────────────────────────────
section("H — statik (AST): bloklar")
try:
    _MAIN_AST = _ast.parse(open(os.path.join(ROOT, "main.py"), encoding="utf-8").read())
except Exception as _e:                                         # noqa: BLE001
    _MAIN_AST = None
    check("H0 main.py o'qildi", False, str(_e))


def _nuqtali(n):
    """Chaqiruv nomi: `crud.create_order`, `_send_telegram`, `db.refresh`."""
    f = n.func
    qism = []
    while isinstance(f, _ast.Attribute):
        qism.append(f.attr)
        f = f.value
    if isinstance(f, _ast.Name):
        qism.append(f.id)
    return ".".join(reversed(qism))


def _funksiya(nom_):
    if _MAIN_AST is None:
        return None
    for n in _ast.walk(_MAIN_AST):
        if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and n.name == nom_:
            return n
    return None


def _bt_bloklari(fn):
    """Funksiyadagi `with crud.bitta_tranzaksiya(db):` bloklari."""
    out = []
    for n in _ast.walk(fn):
        if isinstance(n, _ast.With):
            for it in n.items:
                e = it.context_expr
                if isinstance(e, _ast.Call) and _nuqtali(e) == "crud.bitta_tranzaksiya":
                    out.append(n)
    return out


def _chaqiruvlar(tugunlar):
    s = set()
    for t in tugunlar:
        for n in _ast.walk(t):
            if isinstance(n, _ast.Call):
                s.add(_nuqtali(n))
    return s


def _raise_ichida(bloklar):
    for b in bloklar:
        for n in _ast.walk(b):
            if isinstance(n, _ast.Raise):
                return True
    return False


STATIK = [
    # (belgi, endpoint, blok ICHIDA bo'lishi shart, blokdan TASHQARIDA bo'lishi shart, rad (raise) blok ichida)
    ("A", "api_create_order", ["crud.create_order", "services.deduct_inventory_for_order"], ["_send_telegram"], False),
    ("D", "api_mark_order_ready", ["services.complete_order"],
     ["_send_telegram", "_send_telegram_to", "_send_delivery_pdf_to_customer", "crud.get_order"], True),
    ("E", "api_update_loy", ["crud.update_order_loy"], [], True),
    ("F", "api_purchase_stock", ["crud.purchase_stock", "crud.create_transport_expense", "crud.create_supplier_payment"],
     ["_send_telegram", "crud.get_suppliers_with_debt"], True),
    ("J", "api_create_return", ["crud.create_return_item"], ["db.refresh"], False),
    ("K", "api_produce", ["crud.produce_finished_product"], ["_send_telegram", "crud.get_low_stock_items"], True),
    ("L", "api_add_production", ["crud.add_to_production"], ["_send_telegram", "crud.get_low_stock_items"], True),
    ("M", "api_finished_production_brak", ["crud.record_finished_product_production_brak"], [], True),
    ("N", "api_delete_finished", ["crud.delete_finished_product"], [], True),
    ("O", "api_create_inventory_receipt", ["crud.create_inventory_receipt"], [], False),
]
for (_b, _fn, _ich, _tash, _rad) in STATIK:
    _f = _funksiya(_fn)
    check(f"H{_b} {_fn}: funksiya topildi", _f is not None)
    if _f is None:
        continue
    _bl = _bt_bloklari(_f)
    check(f"H{_b} {_fn}: `with crud.bitta_tranzaksiya(db):` bloki bor", len(_bl) >= 1, f"{len(_bl)} ta")
    _ichki = _chaqiruvlar(_bl)
    _hamma = _chaqiruvlar([_f])
    for _c1 in _ich:
        check(f"H{_b} {_fn}: `{_c1}(` blok ICHIDA", _c1 in _ichki, f"blokda: {sorted(_ichki)[:12]}")
    for _c2 in _tash:
        check(f"H{_b} {_fn}: `{_c2}(` funksiyada bor va blokdan TASHQARIDA",
              _c2 in _hamma and _c2 not in _ichki, f"funksiyada {_c2 in _hamma}, blokda {_c2 in _ichki}")
    if _rad:
        check(f"H{_b} {_fn}: rad javobi (raise HTTPException) blok ICHIDA — yozilgani bekor bo'ladi",
              _raise_ichida(_bl))


# K84-1 — takror yuborilgan buyurtma: `crud.create_order` belgisi (`_is_duplicate_submit`) endpointda tekshiriladi
_fa = _funksiya("api_create_order")
_belgi = False
if _fa is not None:
    for _n in _ast.walk(_fa):
        if isinstance(_n, _ast.Call) and _nuqtali(_n) == "getattr" and len(_n.args) >= 2 \
                and isinstance(_n.args[1], _ast.Constant) and _n.args[1].value == "_is_duplicate_submit":
            _belgi = True
check("HK84 api_create_order: takror belgisi (`_is_duplicate_submit`) tekshiriladi", _belgi)
_qaytish = False
_shart = False
if _fa is not None:
    for _n in _ast.walk(_fa):
        # `if takror: return new_order` — Telegram / ombor ogohlantirishidan OLDIN darhol qaytish
        if isinstance(_n, _ast.If) and isinstance(_n.test, _ast.Name) and _n.test.id == "takror" \
                and _n.body and isinstance(_n.body[0], _ast.Return):
            _qaytish = True
        # penoplast yechish sharti takrorni ham tekshiradi
        if isinstance(_n, _ast.If) and any(isinstance(_c, _ast.Call) and _nuqtali(_c) == "services.deduct_inventory_for_order"
                                           for _b in _n.body for _c in _ast.walk(_b)):
            _shart = any(isinstance(_x, _ast.Name) and _x.id == "takror" for _x in _ast.walk(_n.test))
check("HK84 api_create_order: takrorda darhol qaytadi (`if takror: return`) — Telegram qayta ketmaydi", _qaytish)
check("HK84 api_create_order: penoplast yechish sharti `takror` ni tekshiradi", _shart)

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
sys.exit(1 if FAIL else 0)
