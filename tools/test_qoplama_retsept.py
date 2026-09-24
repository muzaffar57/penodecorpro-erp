#!/usr/bin/env python3
"""
test_qoplama_retsept.py — K58-1 / K58-2 / K58-3 (5-bo'lim 43-band) darvozasi (kech58, 2026-09-24).

NIMA UCHUN KERAK (O'LCHANGAN — asl kod `e7dd594`, `work/probe58.py`, SQLite va HAQIQIY PG 16 AYNAN)
-----------------------------------------------------------------------------------------------
Buyurtmaning UMUMIY qoplama loyi retsepti uch joyda uch xil tanlanardi:
  A) yechish / qaytarish (`resolve_recipe(order=...)`) va foyda (`calculate_order_profit`) —
     buyurtmadagi BIRINCHI `recipe_id` li detal ("Loy sotish" ham);
  B) brak summasi (`get_order_item_unit_cost`) — birinchi QOPLAMALI detal retsepti;
  C) brak yechimi (`deduct_raw_material_for_brak`) — detalning O'Z retsepti.
Retseptlar: R1 = 5 200 so'm/kg (Kley 60 + Akril 40), R2 = 20 000 so'm/kg (Bo'yoq 100).
  * K58-1 (UI): birinchi detal "Loy sotish" (R1), keyin qoplamali profil (buyurtma retsepti R2)
    → umumiy loy R1 dan (Kley 9, Akril 6, Bo'yoq 0), foydada qoplama 52 000 (to'g'risi 200 000).
    Ikki retseptli buyurtmada (faqat API) brak summasi 10 200, xarajati 25 000.
  * K58-2 (UI — retsept "— Yo'q —"): loy korxonaning birinchi retseptidan yechilardi, foydada
    qoplama xarajati UMUMAN yo'q edi. JONLI: buyurtma 185 — 234 564.48 so'm foydada yo'q.
  * K58-3 (UI "Tahrirlash"): retsept R1 -> R2 — ombor tegilmasdi, o'chirishda loy R2 ga qaytardi
    (Bo'yoq +10 olinmagan, Kley 6 / Akril 4 qaytmadi).

FOYDALANUVCHI QARORI (kech58, tugma): "Yo'q, faqat yangi buyurtmalar" — eski buyurtmalar foydasi
O'ZGARMAYDI. Shu sababli D bo'limi eski (NULL) buyurtma xulqini AYNAN saqlashni tekshiradi.

YECHIM (texnik — Claude): `orders.qoplama_retsept_id` — yaratishda BIR MARTA (yangi qoida:
qoplamali loy detali → "Loy sotish" dan boshqa → istalgan; hech biri bo'lmasa korxonaning birinchi
retsepti), yechish / qaytarish / foyda / brak summasi / brak yechimi — shu manbadan. Tahrirda:
qoralama — yangi tanlovga ergashadi; qoralama emas — loy yechilgan retsept saqlanadi.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_qoplama_retsept.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_qoplama_retsept.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qoplama_retsept_test"
_DB = os.path.join(tempfile.gettempdir(), "qoplama_retsept_test.db")

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
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Inventory, InventoryMovement, Recipe,
    RecipeIngredient, ReturnItem,
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
    _db.add(Company(id=2, name="QR Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "QR_admin", "Parol123!", UserRole.ADMIN, "QR Admin", company_id=1)
    auth.create_user(_db, "QR_admin_b", "Parol123!", UserRole.ADMIN, "QR Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="QR Mijoz", project_name="QR loyiha", total_budget=0, total_paid=0)
PRJB = Project(company_id=2, client_name="QR Mijoz B", project_name="QR loyiha B", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="QR Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
PENOB = Inventory(company_id=2, item_name="QR Penoplast B", unit="blok", stock_quantity=10_000,
                  price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="QR Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000, category="Kimyo")
AKR = Inventory(company_id=1, item_name="QR Akril", unit="kg", stock_quantity=100_000, price_per_unit=10_000, category="Kimyo")
BOYOQ = Inventory(company_id=1, item_name="QR Boyoq", unit="kg", stock_quantity=100_000, price_per_unit=20_000, category="Xom")
QUMB = Inventory(company_id=2, item_name="QR Qum B", unit="kg", stock_quantity=100_000, price_per_unit=3_000, category="Xom")
_db.add_all([PRJ, PRJB, PENO, PENOB, KLEY, AKR, BOYOQ, QUMB])
_db.commit()
R1 = Recipe(company_id=1, name="QR R1 arzon", batch_size_kg=100.0)
R2 = Recipe(company_id=1, name="QR R2 qimmat", batch_size_kg=100.0)
RB = Recipe(company_id=2, name="QR RB", batch_size_kg=100.0)
_db.add_all([R1, R2, RB])
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0),
             RecipeIngredient(recipe_id=R2.id, inventory_id=BOYOQ.id, quantity_kg=100.0),
             RecipeIngredient(recipe_id=RB.id, inventory_id=QUMB.id, quantity_kg=100.0)])
_db.commit()
ID = {k: v.id for k, v in dict(PRJ=PRJ, PRJB=PRJB, PENO=PENO, PENOB=PENOB, KLEY=KLEY, AKR=AKR,
                                BOYOQ=BOYOQ, QUMB=QUMB, R1=R1, R2=R2, RB=RB).items()}
with contextlib.redirect_stdout(_quiet):
    for _rid in (ID["R1"], ID["R2"], ID["RB"]):
        _st = services.get_or_create_loy_stock(_db, _db.get(Recipe, _rid))
        _st.stock_quantity = 0.0
        ID[f"LOY{_rid}"] = _st.id
_db.commit()
_db.close()
NOMI = {ID["KLEY"]: "Kley", ID["AKR"]: "Akril", ID["BOYOQ"]: "Boyoq", ID["QUMB"]: "QumB"}


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("QR_admin")
CB, _s2 = _kir("QR_admin_b")
if _s1 != 302 or _s2 != 302:
    print(f"LOGIN BO'LMADI: {_s1} / {_s2}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom():
    _n[0] += 1
    return f"QR_D{_n[0]}"


def profil(uzunlik, narx=50_000, peno="PENO", **k):
    t = {"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": uzunlik, "quantity": 1,
         "unit_price": narx, "is_coated": True, "penoplast_id": ID[peno]}
    t.update(k)
    return t


def loy_sotish(kg, rid, narx=30_000):
    return {"name": nom(), "category": "loy_sotish", "width": None, "thickness": None, "length": None,
            "quantity": kg, "unit_price": narx, "is_coated": False, "penoplast_id": None,
            "price_per_m3": None, "finished_product_id": None, "recipe_id": rid}


def tana(items, recipe_id, loy_kg, draft=False, prj="PRJ"):
    return {"project_id": ID[prj], "order_type": "product", "items": items, "recipe_id": recipe_id,
            "loy_kg": loy_kg, "is_draft": draft}


def yarat(items, recipe_id, loy_kg, draft=False, klient=None, prj="PRJ"):
    r = req(klient or C, "post", "/api/orders", json=tana(items, recipe_id, loy_kg, draft, prj),
            params={"confirm_shortage": "true"})
    d = js(r)
    return d.get("id") if isinstance(d, dict) else None


def detallar(oid):
    if not oid:
        return []
    d = SessionLocal()
    try:
        return [(i.id, i.name, i.category, i.recipe_id)
                for i in d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        d.close()


def qr(oid):
    if not oid:
        return "yo'q"
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        return getattr(o, "qoplama_retsept_id", None) if o else "yo'q"
    finally:
        d.close()


def stok():
    d = SessionLocal()
    try:
        return {k: round(float(d.get(Inventory, ID[k]).stock_quantity), 6) for k in ("KLEY", "AKR", "BOYOQ")}
    finally:
        d.close()


def farq(a, b):
    return {k: round(b[k] - a[k], 6) for k in a}


def buyurtma_loyi(oid):
    """Buyurtmaning (brakdan tashqari) loy xomashyosi harakatlari: nom -> kg (chiqim +, kirim -)."""
    if not oid:
        return {}
    d = SessionLocal()
    try:
        s = {}
        for h in d.query(InventoryMovement).filter(InventoryMovement.order_id == oid,
                                                   InventoryMovement.return_item_id.is_(None)).all():
            k = NOMI.get(h.inventory_id)
            if not k:
                continue
            ish = 1.0 if h.movement_type == "out" else -1.0
            s[k] = round(s.get(k, 0.0) + ish * float(h.quantity or 0), 6)
        return {k: v for k, v in s.items() if abs(v) > 1e-9}
    finally:
        d.close()


def brak(oid, iid, nomi, miqdor=1):
    t = {"order_id": oid, "order_item_id": iid, "item_name": nomi, "quantity": miqdor, "unit": "metr",
         "reason": "Brak", "refund_amount": 0, "to_stock": False, "coating_applied": True}
    r = req(C, "post", "/api/returns", json=t)
    d = js(r)
    return r.status_code, (d.get("id") if isinstance(d, dict) else None)


def brak_olchov(rid):
    if not rid:
        return {}
    d = SessionLocal()
    try:
        q = d.get(ReturnItem, rid)
        loy, jami = {}, 0.0
        for h in d.query(InventoryMovement).filter(InventoryMovement.return_item_id == rid).all():
            jami += float(h.quantity or 0) * float(h.unit_cost or 0)
            k = NOMI.get(h.inventory_id)
            if k:
                loy[k] = round(loy.get(k, 0.0) + float(h.quantity or 0), 6)
        return {"summa": float(q.refund_amount) if q else None, "xarajat": round(jami, 4), "loy": loy}
    finally:
        d.close()


def tayyor(oid, kg):
    return req(C, "post", f"/api/orders/{oid}/ready", params={"loy_kg": kg}).status_code


def foyda_qoplama(oid):
    """`calculate_order_profit` dagi "Qoplama" qatori summasi (qator yo'q — None)."""
    d = SessionLocal()
    try:
        p = services.calculate_order_profit(d, oid, company_id=1)
        for x in (p.get("breakdown") or []) if isinstance(p, dict) else []:
            if "Qoplama" in str(x.get("nomi", "")):
                return round(float(x.get("summa") or 0), 2)
        return None
    except Exception as e:                 # noqa: BLE001
        return f"XATO {type(e).__name__}"
    finally:
        d.close()


def ochir(oid):
    return req(C, "delete", f"/api/orders/{oid}").status_code


# ══════════════════════════════════════════════════════════════
section("A. Yangi buyurtma — qoplama retsepti bitta manbadan (K58-1 / K58-2)")
# ══════════════════════════════════════════════════════════════
# A1 — UI shakli: birinchi "Loy sotish" (R1), keyin qoplamali profil (buyurtma retsepti R2)
_s0 = stok()
o1 = yarat([loy_sotish(5, ID["R1"]), profil(10)], ID["R2"], 10)
_s1 = stok()
check("A1 buyurtma yaratildi", bool(o1), o1)
check("A1 qoplama_retsept_id = R2 (tanlangan retsept, \"Loy sotish\" niki EMAS)", qr(o1) == ID["R2"], qr(o1))
check("A1 umumiy loy R2 dan: Bo'yoq 10 kg", taxminan(farq(_s0, _s1)["BOYOQ"], -10), farq(_s0, _s1))
check("A1 \"Loy sotish\" o'z retseptidan: Kley 3 / Akril 2 (umumiy loy R1 dan YECHILMAGAN)",
      taxminan(farq(_s0, _s1)["KLEY"], -3) and taxminan(farq(_s0, _s1)["AKR"], -2), farq(_s0, _s1))
_d1 = detallar(o1)
_sc, _r1 = brak(o1, _d1[1][0], _d1[1][1]) if len(_d1) > 1 else (0, None)
_b1 = brak_olchov(_r1)
check("A1 profil braki yozildi (200)", _sc == 200, _sc)
check("A1 brak loyi R2 dan: Bo'yoq 1 kg", _b1.get("loy") == {"Boyoq": 1.0}, _b1)
check("A1 brak summasi = Moliya xarajati = 25 000", taxminan(_b1.get("summa"), 25_000, 0.5)
      and taxminan(_b1.get("xarajat"), 25_000, 0.5), _b1)
check("A1 tayyor (200)", tayyor(o1, 10) == 200)
check("A1 foydada qoplama 10 kg x 20 000 = 200 000", taxminan(foyda_qoplama(o1), 200_000, 0.5), foyda_qoplama(o1))

# A2 — nazorat: profil birinchi, "Loy sotish" keyin (asl kodda ham to'g'ri edi)
_s0 = stok()
o2 = yarat([profil(10), loy_sotish(5, ID["R1"])], ID["R2"], 10)
_s1 = stok()
check("A2 qoplama_retsept_id = R2", qr(o2) == ID["R2"], qr(o2))
check("A2 ombor: Bo'yoq 10, Kley 3, Akril 2", farq(_s0, _s1) == {"KLEY": -3.0, "AKR": -2.0, "BOYOQ": -10.0},
      farq(_s0, _s1))
check("A2 tayyor + foydada 200 000", tayyor(o2, 10) == 200 and taxminan(foyda_qoplama(o2), 200_000, 0.5),
      foyda_qoplama(o2))

# A3 — faqat API: ikki qoplamali profil, R1 va (aniq berilgan) R2; buyurtma retsepti R1
o3 = yarat([profil(10), profil(10, recipe_id=ID["R2"])], ID["R1"], 20)
check("A3 qoplama_retsept_id = R1 (birinchi qoplamali detal)", qr(o3) == ID["R1"], qr(o3))
check("A3 umumiy loy R1 dan: Kley 12 / Akril 8", buyurtma_loyi(o3) == {"Kley": 12.0, "Akril": 8.0}, buyurtma_loyi(o3))
_d3 = detallar(o3)
_sc, _r3 = brak(o3, _d3[1][0], _d3[1][1]) if len(_d3) > 1 else (0, None)
_b3 = brak_olchov(_r3)
check("A3 IKKINCHI detal braki loyi buyurtma loyi retseptidan (R1): Kley 0.6 / Akril 0.4",
      _b3.get("loy") == {"Kley": 0.6, "Akril": 0.4}, _b3)
check("A3 brak summasi = xarajat = 10 200 (asl kodda 10 200 / 25 000)",
      taxminan(_b3.get("summa"), 10_200, 0.5) and taxminan(_b3.get("xarajat"), 10_200, 0.5), _b3)

# A4 — retsept "— Yo'q —" (UI): korxonaning birinchi retsepti (R1) — foyda ham shuni ko'radi
_s0 = stok()
o4 = yarat([profil(10)], None, 10)
_s1 = stok()
check("A4 qoplama_retsept_id = korxonaning birinchi retsepti (R1)", qr(o4) == ID["R1"], qr(o4))
check("A4 loy R1 dan: Kley 6 / Akril 4", farq(_s0, _s1) == {"KLEY": -6.0, "AKR": -4.0, "BOYOQ": 0.0}, farq(_s0, _s1))
_d4 = detallar(o4)
_sc, _r4 = brak(o4, _d4[0][0], _d4[0][1]) if _d4 else (0, None)
_b4 = brak_olchov(_r4)
check("A4 brak summasi = xarajat = 10 200", taxminan(_b4.get("summa"), 10_200, 0.5)
      and taxminan(_b4.get("xarajat"), 10_200, 0.5), _b4)
check("A4 tayyor + foydada qoplama 10 x 5 200 = 52 000 (asl kodda qator YO'Q edi)",
      tayyor(o4, 10) == 200 and taxminan(foyda_qoplama(o4), 52_000, 0.5), foyda_qoplama(o4))

# A5 — yangi qoida funksiyasi (nomzodlar tartibi) — to'g'ridan
_f_yangi = getattr(services, "_qoplama_retsept_nomzodlari_yangi", None)
_f_nomz = getattr(services, "buyurtma_qoplama_retsept_nomzodlari", None)


class _It:
    def __init__(self, i, cat, rid, qop, fp=None):
        self.id, self.category, self.recipe_id, self.is_coated, self.finished_product_id = i, cat, rid, qop, fp


class _Ord:
    def __init__(self, items, saq=None):
        self.items, self.qoplama_retsept_id, self.company_id = items, saq, 1


def _chaqir(f, *a):
    try:
        return f(*a) if f else "funksiya yo'q"
    except Exception as e:                 # noqa: BLE001
        return f"XATO {type(e).__name__}"


# id tartibi ro'yxat tartibidan farqli (PG da UPDATE dan keyin shunday bo'lishi mumkin)
_o = _Ord([_It(9, "profil", 7, True), _It(3, "loy_sotish", 5, False), _It(5, "panel", 6, False)])
check("A5 yangi qoida: qoplamali loy detali birinchi, keyin boshqa, oxiri \"Loy sotish\" -> [7, 6, 5]",
      _chaqir(_f_yangi, _o) == [7, 6, 5], _chaqir(_f_yangi, _o))
_o = _Ord([_It(2, "profil", 7, True, fp=11), _It(4, "mrp_product", 8, True), _It(6, "profil", 9, True)])
check("A5 tayyor mahsulotdan / MRP detali buyurtma loyi detali EMAS -> 9 birinchi",
      (_chaqir(_f_yangi, _o) or [None])[0] == 9, _chaqir(_f_yangi, _o))
_o = _Ord([_It(1, "loy_sotish", 5, False), _It(2, "profil", 7, True)], saq=5)
check("A5 saqlangan retsept birinchi (5), so'ng eski qoida (5, 7)",
      _chaqir(_f_nomz, _o) == [5, 7], _chaqir(_f_nomz, _o))
_o = _Ord([_It(1, "loy_sotish", 5, False), _It(2, "profil", 7, True)], saq=None)
check("A5 saqlanmagan (eski) buyurtma — avvalgi qoida AYNAN: birinchi recipe_id li detal (5)",
      (_chaqir(_f_nomz, _o) or [None])[0] == 5, _chaqir(_f_nomz, _o))
# bir guruhdagi ikki detal: ro'yxat tartibi id tartibidan farqli -> id tartibi hal qiladi
_o = _Ord([_It(9, "profil", 7, True), _It(3, "profil", 8, True)])
check("A5 bir guruhda — id tartibi (3 -> 8 birinchi), ro'yxat tartibi EMAS -> [8, 7]",
      _chaqir(_f_yangi, _o) == [8, 7], _chaqir(_f_yangi, _o))
# korxona filtri: B buyurtmasida A retsepti nomzod bo'lsa ham (API ikkinchi to'siq — _TENANT_REFS)
_f_tanla = getattr(services, "buyurtma_qoplama_retseptini_tanla", None)
_dt = SessionLocal()
try:
    _o = _Ord([_It(1, "profil", ID["R1"], True)])
    _o.company_id = 2
    _rt = _f_tanla(_dt, _o) if _f_tanla else None
    _rid_t = getattr(_rt, "id", None)
except Exception as e:                     # noqa: BLE001
    _rid_t = f"XATO {type(e).__name__}"
finally:
    _dt.close()
check("A5 tanlash korxona doirasida: B uchun A retsepti (R1) EMAS, B niki (RB)", _rid_t == ID["RB"], _rid_t)

# ══════════════════════════════════════════════════════════════
section("B. O'chirish va qoralama — yechilgan retseptga qaytadi")
# ══════════════════════════════════════════════════════════════
_s0 = stok()
o5 = yarat([loy_sotish(5, ID["R1"]), profil(10)], ID["R2"], 10)
check("B1 o'chirish (200)", ochir(o5) == 200)
check("B1 o'chirishdan keyin ombor AYNAN (sof 0)", farq(_s0, stok()) == {"KLEY": 0.0, "AKR": 0.0, "BOYOQ": 0.0},
      farq(_s0, stok()))

_s0 = stok()
o6 = yarat([loy_sotish(5, ID["R1"]), profil(10)], ID["R2"], 10, draft=True)
check("B2 qoralama: qoplama_retsept_id = R2, ombor tegilmagan",
      qr(o6) == ID["R2"] and farq(_s0, stok()) == {"KLEY": 0.0, "AKR": 0.0, "BOYOQ": 0.0}, (qr(o6), farq(_s0, stok())))
_ra = req(C, "post", f"/api/orders/{o6}/activate")
check("B2 jarayonga olish (200)", _ra.status_code == 200, _ra.status_code)
check("B2 jarayonga olishda umumiy loy R2 dan: Bo'yoq 10",
      taxminan(farq(_s0, stok())["BOYOQ"], -10), farq(_s0, stok()))
check("B2 o'chirish (200) va ombor AYNAN", ochir(o6) == 200
      and farq(_s0, stok()) == {"KLEY": 0.0, "AKR": 0.0, "BOYOQ": 0.0}, farq(_s0, stok()))


# ══════════════════════════════════════════════════════════════
section("C. Tahrir — K58-3")
# ══════════════════════════════════════════════════════════════
_s0 = stok()
_t = tana([profil(10)], ID["R1"], 10)
_rc = req(C, "post", "/api/orders", json=_t, params={"confirm_shortage": "true"})
o7 = (js(_rc) or {}).get("id")
_s1 = stok()
_t["recipe_id"] = ID["R2"]
_ru = req(C, "put", f"/api/orders/{o7}", json=_t, params={"confirm_shortage": "true"})
check("C1 jarayondagi buyurtma tahriri R1 -> R2 (200)", _ru.status_code == 200, _ru.status_code)
check("C1 qoplama_retsept_id R1 da qoldi (loy R1 dan yechilgan)", qr(o7) == ID["R1"], qr(o7))
check("C1 tahrir omborga tegmadi", farq(_s1, stok()) == {"KLEY": 0.0, "AKR": 0.0, "BOYOQ": 0.0}, farq(_s1, stok()))
check("C1 o'chirish (200) va ombor AYNAN (asl kodda Bo'yoq +10, Kley -6, Akril -4)",
      ochir(o7) == 200 and farq(_s0, stok()) == {"KLEY": 0.0, "AKR": 0.0, "BOYOQ": 0.0}, farq(_s0, stok()))

_s0 = stok()
_t = tana([profil(10)], ID["R1"], 10, draft=True)
_rc = req(C, "post", "/api/orders", json=_t, params={"confirm_shortage": "true"})
o8 = (js(_rc) or {}).get("id")
_t["recipe_id"] = ID["R2"]
_ru = req(C, "put", f"/api/orders/{o8}", json=_t, params={"confirm_shortage": "true"})
check("C2 qoralama tahriri R1 -> R2 (200) — qoplama_retsept_id = R2 (hali hech narsa yechilmagan)",
      _ru.status_code == 200 and qr(o8) == ID["R2"], (_ru.status_code, qr(o8)))
_ra = req(C, "post", f"/api/orders/{o8}/activate")
check("C2 jarayonga olishda loy R2 dan: Bo'yoq 10, Kley / Akril 0",
      _ra.status_code == 200 and farq(_s0, stok()) == {"KLEY": 0.0, "AKR": 0.0, "BOYOQ": -10.0}, farq(_s0, stok()))
check("C2 o'chirish va ombor AYNAN", ochir(o8) == 200
      and farq(_s0, stok()) == {"KLEY": 0.0, "AKR": 0.0, "BOYOQ": 0.0}, farq(_s0, stok()))

_t = tana([profil(10)], ID["R2"], 10)
_rc = req(C, "post", "/api/orders", json=_t, params={"confirm_shortage": "true"})
o9 = (js(_rc) or {}).get("id")
_t["items"] = [dict(_t["items"][0], length=12)]
_ru = req(C, "put", f"/api/orders/{o9}", json=_t, params={"confirm_shortage": "true"})
check("C3 retseptsiz tahrir (uzunlik) — qoplama_retsept_id R2 da", _ru.status_code == 200 and qr(o9) == ID["R2"],
      (_ru.status_code, qr(o9)))

# C4 — qoralama: detal NOMI ham o'zgaradi (eski detal o'chiriladi, yangisi qo'shiladi) va retsept R1 -> R2
_s0 = stok()
_t = tana([profil(10)], ID["R1"], 10, draft=True)
_rc = req(C, "post", "/api/orders", json=_t, params={"confirm_shortage": "true"})
o10 = (js(_rc) or {}).get("id")
_t["recipe_id"] = ID["R2"]
_t["items"] = [dict(_t["items"][0], name=nom())]
_ru = req(C, "put", f"/api/orders/{o10}", json=_t, params={"confirm_shortage": "true"})
check("C4 qoralama: detal almashdi + R2 -> qoplama_retsept_id = R2 (o'chirilgan detal retsepti EMAS)",
      _ru.status_code == 200 and qr(o10) == ID["R2"], (_ru.status_code, qr(o10)))
_ra = req(C, "post", f"/api/orders/{o10}/activate")
check("C4 jarayonga olishda loy R2 dan: Bo'yoq 10", _ra.status_code == 200
      and farq(_s0, stok()) == {"KLEY": 0.0, "AKR": 0.0, "BOYOQ": -10.0}, farq(_s0, stok()))
check("C4 o'chirish va ombor AYNAN", ochir(o10) == 200
      and farq(_s0, stok()) == {"KLEY": 0.0, "AKR": 0.0, "BOYOQ": 0.0}, farq(_s0, stok()))

# ══════════════════════════════════════════════════════════════
section("D. ESKI buyurtma (qoplama_retsept_id NULL) — avvalgi xulq AYNAN (foydalanuvchi qarori)")
# ══════════════════════════════════════════════════════════════
# Eski buyurtma — yaratishda belgilash o'chirilgan holda (kech58 gacha yaratilganlar kabi).
_asl_tanla = getattr(services, "buyurtma_qoplama_retseptini_tanla", None)
if _asl_tanla is not None:
    services.buyurtma_qoplama_retseptini_tanla = lambda *a, **k: None
try:
    _s0 = stok()
    d1 = yarat([loy_sotish(5, ID["R1"]), profil(10)], ID["R2"], 10)
    _s1 = stok()
    d2 = yarat([profil(10)], None, 10)
    _t = tana([profil(10)], ID["R1"], 10)
    _rc = req(C, "post", "/api/orders", json=_t, params={"confirm_shortage": "true"})
    d3 = (js(_rc) or {}).get("id")
    _t2 = dict(_t)
    _t2["items"] = [dict(_t["items"][0], length=11, name=nom())]
    _rc = req(C, "post", "/api/orders", json=_t2, params={"confirm_shortage": "true"})
    d4 = (js(_rc) or {}).get("id")
finally:
    if _asl_tanla is not None:
        services.buyurtma_qoplama_retseptini_tanla = _asl_tanla
check("D0 eski buyurtmalar yaratildi (4 ta ALOHIDA), qoplama_retsept_id NULL",
      all(x for x in (d1, d2, d3, d4)) and len({d1, d2, d3, d4}) == 4
      and all(qr(x) is None for x in (d1, d2, d3, d4)),
      [(x, qr(x)) for x in (d1, d2, d3, d4)])
check("D1 eski S2 shakli: umumiy loy avvalgidek R1 dan (Kley 9 / Akril 6)",
      farq(_s0, _s1) == {"KLEY": -9.0, "AKR": -6.0, "BOYOQ": 0.0}, farq(_s0, _s1))
_dd1 = detallar(d1)
_sc, _rd1 = brak(d1, _dd1[1][0], _dd1[1][1]) if len(_dd1) > 1 else (0, None)
_bd1 = brak_olchov(_rd1)
check("D1 eski buyurtma braki — buyurtma loyi yechilgan retseptdan (R1), summa = xarajat = 10 200",
      _bd1.get("loy") == {"Kley": 0.6, "Akril": 0.4} and taxminan(_bd1.get("summa"), 10_200, 0.5)
      and taxminan(_bd1.get("xarajat"), 10_200, 0.5), _bd1)
check("D1 tayyor + foyda AVVALGIDEK: qoplama 10 x 5 200 = 52 000 (eski buyurtma foydasi o'zgarmaydi)",
      tayyor(d1, 10) == 200 and taxminan(foyda_qoplama(d1), 52_000, 0.5), foyda_qoplama(d1))
check("D2 eski retseptsiz buyurtma: tayyor + foydada qoplama qatori AVVALGIDEK YO'Q",
      tayyor(d2, 10) == 200 and foyda_qoplama(d2) is None, foyda_qoplama(d2))
_s0 = stok()
_t["recipe_id"] = ID["R2"]
_ru = req(C, "put", f"/api/orders/{d3}", json=_t, params={"confirm_shortage": "true"})
check("D3 eski buyurtma tahriri R1 -> R2: yechilgan retsept (R1) muzlatildi",
      _ru.status_code == 200 and qr(d3) == ID["R1"], (_ru.status_code, qr(d3)))
check("D3 o'chirish va ombor AYNAN (R1 ga qaytdi)", ochir(d3) == 200
      and farq(_s0, stok()) == {"KLEY": 6.0, "AKR": 4.0, "BOYOQ": 0.0}, farq(_s0, stok()))
_ru = req(C, "put", f"/api/orders/{d4}", json=dict(_t2, items=[dict(_t2["items"][0], length=12)]),
          params={"confirm_shortage": "true"})
check("D4 eski buyurtma retseptsiz tahriri (uzunlik) — qoplama_retsept_id NULL qoladi",
      _ru.status_code == 200 and qr(d4) is None, (_ru.status_code, qr(d4)))

# D5 — eski buyurtma: detal NOMI ham o'zgaradi + retsept R1 -> R2 -> yechilgan retsept (R1) muzlatiladi
if _asl_tanla is not None:
    services.buyurtma_qoplama_retseptini_tanla = lambda *a, **k: None
try:
    _s0 = stok()
    _t5 = tana([profil(10)], ID["R1"], 10)
    _rc = req(C, "post", "/api/orders", json=_t5, params={"confirm_shortage": "true"})
    d5 = (js(_rc) or {}).get("id")
finally:
    if _asl_tanla is not None:
        services.buyurtma_qoplama_retseptini_tanla = _asl_tanla
_t5["recipe_id"] = ID["R2"]
_t5["items"] = [dict(_t5["items"][0], name=nom())]
_ru = req(C, "put", f"/api/orders/{d5}", json=_t5, params={"confirm_shortage": "true"})
check("D5 eski buyurtma: detal almashdi + R2 -> yechilgan retsept (R1) muzlatildi",
      bool(d5) and _ru.status_code == 200 and qr(d5) == ID["R1"], (d5, _ru.status_code, qr(d5)))
check("D5 o'chirish va ombor AYNAN (R1 ga qaytdi)", ochir(d5) == 200
      and farq(_s0, stok()) == {"KLEY": 0.0, "AKR": 0.0, "BOYOQ": 0.0}, farq(_s0, stok()))

# ══════════════════════════════════════════════════════════════
section("E. Korxona chegarasi")
# ══════════════════════════════════════════════════════════════
ob = yarat([profil(10, peno="PENOB")], None, 10, klient=CB, prj="PRJB")
check("E1 B korxona retseptsiz buyurtmasi — o'z retsepti (RB), A niki EMAS", qr(ob) == ID["RB"], qr(ob))
_dbe = SessionLocal()
_xato = None
try:
    _o = _dbe.get(Order, ob)
    if _o is not None and hasattr(_o, "qoplama_retsept_id"):
        _o.qoplama_retsept_id = ID["R1"]
        _dbe.commit()
    else:
        _xato = "ustun yo'q"
except Exception as e:                     # noqa: BLE001
    _xato = type(e).__name__
    _dbe.rollback()
finally:
    _dbe.close()
check("E2 B buyurtmasiga A retsepti yozib bo'lmaydi (_TENANT_REFS)", _xato == "TenantMismatchError", _xato)
check("E2 qiymat o'zgarmadi (RB)", qr(ob) == ID["RB"], qr(ob))


# ══════════════════════════════════════════════════════════════
section("F. Migratsiya")
# ══════════════════════════════════════════════════════════════
from sqlalchemy import inspect as _insp   # noqa: E402
_i = _insp(engine)
_ust = {c["name"] for c in _i.get_columns("orders")}
_ix = {ix["name"] for ix in _i.get_indexes("orders")}
check("F1 orders.qoplama_retsept_id ustuni bor", "qoplama_retsept_id" in _ust)
check("F1 ix_orders_qoplama_retsept_id indeksi bor", "ix_orders_qoplama_retsept_id" in _ix, sorted(_ix))
_mig = getattr(main, "_migrate_qoplama_retsept", None)
check("F2 main._migrate_qoplama_retsept bor", callable(_mig))
if callable(_mig) and not PG_URL:
    with engine.connect() as _c:
        _c.execute(text("DROP INDEX IF EXISTS ix_orders_qoplama_retsept_id"))
        _c.commit()
    with contextlib.redirect_stdout(_quiet):
        _mig()
        _mig()
    _ix2 = {ix["name"] for ix in _insp(engine).get_indexes("orders")}
    check("F3 (SQLite) indeks olib tashlansa — migratsiya qayta yaratadi, ikki marta chaqiruv xatosiz",
          "ix_orders_qoplama_retsept_id" in _ix2, sorted(_ix2))
if PG_URL:
    with engine.connect() as _c:
        _fk = _c.execute(text(
            "SELECT c.confdeltype, ft.relname FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid JOIN pg_class ft ON ft.oid = c.confrelid "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey) "
            "WHERE t.relname = 'orders' AND c.contype = 'f' AND a.attname = 'qoplama_retsept_id'")).first()
    check("F3 (PG) chet el kaliti recipes(id) ON DELETE SET NULL",
          _fk is not None and _fk[0] == "n" and _fk[1] == "recipes", _fk)
    if callable(_mig):
        with contextlib.redirect_stdout(_quiet):
            _mig()
        with engine.connect() as _c:
            _n_fk = _c.execute(text(
                "SELECT COUNT(*) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey) "
                "WHERE t.relname = 'orders' AND c.contype = 'f' AND a.attname = 'qoplama_retsept_id'")).scalar()
        check("F4 (PG) migratsiya qayta chaqirilsa kalit takrorlanmaydi (1 ta)", _n_fk == 1, _n_fk)
    _d = SessionLocal()
    try:
        R3 = Recipe(company_id=1, name="QR R3 vaqtincha", batch_size_kg=100.0)
        _d.add(R3)
        _d.commit()
        _r3 = R3.id
        _o = _d.get(Order, o2)
        if hasattr(_o, "qoplama_retsept_id"):
            _o.qoplama_retsept_id = _r3
            _d.commit()
        _d.execute(text("DELETE FROM recipes WHERE id = :i"), {"i": _r3})
        _d.commit()
        _ok = True
    except Exception as e:                 # noqa: BLE001
        _d.rollback()
        _ok = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        _d.close()
    check("F5 (PG) retsept o'chirilsa buyurtma ustuni NULL bo'ladi (xato yo'q)", _ok is True and qr(o2) is None,
          (_ok, qr(o2)))
_dbk = SessionLocal()
try:
    _bk = crud.export_full_backup(_dbk, company_id=1)
except Exception as e:                     # noqa: BLE001
    _bk = {"xato": f"{type(e).__name__}: {e}"}
finally:
    _dbk.close()
_bo = ((_bk.get("tables") or {}).get("orders") if isinstance(_bk, dict) else None) or []
check("F6 zaxira nusxada (export_full_backup) orders yozuvlarida qoplama_retsept_id kaliti bor",
      bool(_bo) and all("qoplama_retsept_id" in x for x in _bo), (len(_bo), str(_bk)[:160] if not _bo else ""))


# ══════════════════════════════════════════════════════════════
section("S. Statik — yagona manba")
# ══════════════════════════════════════════════════════════════
def _manba(f):
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


_src_res = _manba(services.resolve_recipe)
_src_fo = _manba(services.calculate_order_profit)
_src_uc = _manba(services.get_order_item_unit_cost)
_src_br = _manba(services.deduct_raw_material_for_brak)
_src_cr = _manba(crud.create_order)
_src_up = _manba(crud.update_order_full)
_src_mo = open(os.path.join(ROOT, "models.py"), encoding="utf-8").read()
_src_ma = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("S1 resolve_recipe buyurtma nomzodlarini buyurtma_qoplama_retsept_nomzodlari dan oladi",
      "buyurtma_qoplama_retsept_nomzodlari(order)" in _src_res)
check("S2 calculate_order_profit qoplama retsepti — buyurtma_qoplama_retsept_nomzodlari",
      "buyurtma_qoplama_retsept_nomzodlari(order)" in _src_fo
      and "            if item.recipe_id:\n                recipe = db.query(Recipe)" not in _src_fo)
check("S3 get_order_item_unit_cost loy retsepti — resolve_recipe(order=...)",
      "resolve_recipe(db, order=order" in _src_uc and "if not recipe_id and oi.recipe_id:" not in _src_uc)
check("S4 brak yechimi detalning o'z retseptini ishlatmaydi",
      "recipe_id=order_item.recipe_id" not in _src_br and "recipe_id=None," in _src_br)
check("S5 create_order: flush -> belgilash -> umumiy loy yechimi (tartib)",
      tartibda(_src_cr, "db.flush()", "buyurtma_qoplama_retseptini_tanla(db, db_order)",
               "db_order.qoplama_retsept_id =", "_services.deduct_loy_ingredients(db, db_order, _planned_loy_general)"))
check("S6 update_order_full: oldingi retsept detallar o'zgarishidan OLDIN, qaror flush dan keyin",
      tartibda(_src_up, "_qr58_oldin = services.resolve_recipe(", "oi.recipe_id = ",
               "db.flush()", "if is_draft:", "order.qoplama_retsept_id = _qr58_oldin.id"))
check("S7 models: Order.qoplama_retsept_id FK recipes ON DELETE SET NULL + _TENANT_REFS",
      'qoplama_retsept_id = Column(Integer, ForeignKey("recipes.id", ondelete="SET NULL")' in _src_mo
      and '("qoplama_retsept_id", "Recipe")' in _src_mo)
check("S8 main: migratsiya modul darajasida chaqiriladi",
      "\n_migrate_qoplama_retsept()\n" in _src_ma)


print(f"\n{'=' * 60}")
print(f"{YORLIQ}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
