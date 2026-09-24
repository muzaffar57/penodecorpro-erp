#!/usr/bin/env python3
"""
test_brak_tahlil.py — 13-band 7-qadam darvozasi (kech56, 2026-09-24).

NIMA UCHUN: brak yozuvida qancha yo'qotilgani va (kech53 dan) qaysi bosqichda bo'lgani bor edi,
lekin NEGA bo'lgani (sabab) va KIM sabab bo'lgani yozilmasdi, brak ulushini (foizini) ko'rsatadigan
va me'yordan oshganda ogohlantiradigan tahlil yo'q edi (kech5 9-bo'lim, 1 / 7-kamchilik va 7-qadam).

FOYDALANUVCHI QARORLARI (kech56, tugma bilan, so'zma-so'z):
  * me'yor — "5 %";
  * sabab — "Ha, taklif qilingan ro'yxat bilan": Xomashyo sifati, Ishchi xatosi,
    Uskuna / stanok nosozligi, O'lcham / qolip xatosi, Boshqa;
  * javobgar hodim — "Ha, ixtiyoriy tanlov".

YECHIM (texnik — Claude):
  * `ReturnItem` / `FinishedProductLoss`: `brak_sabab` (String(20), STANDARTSIZ) va
    `brak_javobgar_id` (FK `employees.id` ON DELETE SET NULL, indeks); kodlar — `crud.BRAK_SABABLARI`,
    me'yor — `crud.BRAK_MEYORI_FOIZ`. Ikkalasi IXTIYORIY; buyurtma yozuvida FAQAT brakda;
    javobgar — shu korxonaning o'chirilmagan hodimi. Tekshiruv hech narsa yozilishidan OLDIN.
  * `services.get_brak_tahlil` + `GET /api/reports/brak-tahlil` (Moliya huquqi): ulush = Moliyadagi
    brak xarajati ÷ ishlab chiqarish tan narxi (`get_monthly_report` — BIR manba), me'yordan
    oshsa ogohlantirish; bosqich / sabab / javobgar / detal taqsimoti — yozuvlar qiymati bo'yicha;
    tayyor mahsulot yo'qotishlari ro'yxati; oxirgi N oy.
  * UI: `returns.html` brak oynasida `#brak-cause`, `#brak-worker`, ro'yxatda yorliq, admin uchun
    "Brak tahlili" kartasi; `finished.html` "Kamaytirish" oynasida `#loss-cause`, `#loss-worker`;
    `dashboard.html` brak kartasida ulush va ogohlantirish.
QAT'IY SHART (kech5 9-bo'lim): brak yozish oqimi O'ZGARMAYDI — sababli / javobgarli brak sababsiz
brak bilan AYNAN bir xil xomashyo yechimi va yozuv mazmunini hosil qilishi shu test bilan isbotlanadi.

ASL KOD: tuzatishdan OLDINGI kodga qarshi yiqilishi (qulamasligi) SHART — yangi nomlarga murojaat
`getattr` bilan, HTTP istisnolari 599.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_brak_tahlil.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_brak_tahlil.py
"""
import os
import sys
import re
import html as _html
import typing
import inspect
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "brak_tahlil_test"
_DB = os.path.join(tempfile.gettempdir(), "brak_tahlil_test.db")

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
    import crud, auth, services, schemas           # noqa: E402
    import database as _database                   # noqa: E402

from sqlalchemy import text as _sqltext            # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, OrderItem, Inventory, InventoryMovement, Recipe, RecipeIngredient,
    ReturnItem, ReturnReason, FinishedProduct, FinishedProductLoss, StockSource, ProductionStatus,
    Employee,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []

SABAB_KODLARI = ["xomashyo", "ishchi", "uskuna", "olcham", "boshqa"]
SABAB_YORLIQLARI = ["Xomashyo sifati", "Ishchi xatosi", "Uskuna / stanok nosozligi",
                    "O'lcham / qolip xatosi", "Boshqa"]
BOSQICH_YORLIQ = {"kesish": "Kesish (penoplast kesish)", "qoplash": "Qoplash (loy tortish)",
                  "quritish": "Quritish", "saqlash_tashish": "Saqlash / tashish"}


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


def xabar(r):
    """Rad javobidagi matn (detail matn yoki {message})."""
    d = js(r)
    if not isinstance(d, dict):
        return ""
    det = d.get("detail")
    if isinstance(det, dict):
        return str(det.get("message") or "")
    return str(det or "")


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
H1_ISM = "BT Kesuvchi <i class=xq>'A\" & B"
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="BT Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "BT_admin", "Parol123!", UserRole.ADMIN, "BT Admin", company_id=1)
    auth.create_user(_db, "BT_admin_b", "Parol123!", UserRole.ADMIN, "BT Admin B", company_id=2)
    auth.create_user(_db, "BT_ombor", "Parol123!", UserRole.WAREHOUSE, "BT Ombor", company_id=1)
    auth.create_user(_db, "BT_menejer", "Parol123!", UserRole.MANAGER, "BT Menejer", company_id=1)
    auth.create_user(_db, "BT_moliya", "Parol123!", UserRole.ACCOUNTANT, "BT Moliya", company_id=1)
PRJ = Project(company_id=1, client_name="BT Mijoz", project_name="BT loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="BT Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="BT Kley", unit="kg", stock_quantity=100_000,
                 price_per_unit=2_000, category="Kimyo")
AKR = Inventory(company_id=1, item_name="BT Akril", unit="kg", stock_quantity=100_000,
                price_per_unit=10_000, category="Kimyo")
H1 = Employee(company_id=1, name=H1_ISM, position="Kesuvchi", is_active=True, is_deleted=False)
H2 = Employee(company_id=1, name="BT Qoplovchi", position="Qoplovchi", is_active=True, is_deleted=False)
H3 = Employee(company_id=1, name="BT Nofaol", is_active=False, is_deleted=False)
H4 = Employee(company_id=1, name="BT Ochirilgan", is_active=True, is_deleted=True)
H5 = Employee(company_id=1, name="BT Ketadigan", is_active=True, is_deleted=False)
HB = Employee(company_id=2, name="BT Begona", is_active=True, is_deleted=False)
_db.add_all([PRJ, PENO, KLEY, AKR, H1, H2, H3, H4, H5, HB])
_db.commit()
R1 = Recipe(company_id=1, name="BT R1", batch_size_kg=100.0)
_db.add(R1)
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0)])
_db.commit()
PRJ_ID, PENO_ID, KLEY_ID, AKR_ID, R1_ID = PRJ.id, PENO.id, KLEY.id, AKR.id, R1.id
H1_ID, H2_ID, H3_ID, H4_ID, H5_ID, HB_ID = H1.id, H2.id, H3.id, H4.id, H5.id, HB.id
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


C, _s1 = _kir("BT_admin")
CB, _s2 = _kir("BT_admin_b")
CW, _s3 = _kir("BT_ombor")
CM, _s4 = _kir("BT_menejer")
CF, _s5 = _kir("BT_moliya")
if (_s1, _s2, _s3, _s4, _s5) != (302, 302, 302, 302, 302):
    print(f"LOGIN BO'LMADI: {(_s1, _s2, _s3, _s4, _s5)}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_BU = datetime.utcnow()
YIL, OY = _BU.year, _BU.month

# ══════════════════════════════════════════════════════════════
# Yordamchilar
# ══════════════════════════════════════════════════════════════
_n = [0]


def profil(uzunlik, qoplama=False):
    _n[0] += 1
    return {"name": f"BT_D{_n[0]}", "category": "profil", "width": 20, "thickness": 10,
            "length": uzunlik, "quantity": 10, "unit_price": 50_000, "is_coated": bool(qoplama),
            "penoplast_id": PENO_ID, **({"recipe_id": R1_ID} if qoplama else {})}


def yarat(items, recipe_id=None, loy_kg=None):
    tana = {"project_id": PRJ_ID, "order_type": "product", "items": items}
    if recipe_id:
        tana["recipe_id"] = recipe_id
    if loy_kg is not None:
        tana["loy_kg"] = loy_kg
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    d = js(r)
    oid = d.get("id") if isinstance(d, dict) else None
    if not oid:
        raise RuntimeError(f"buyurtma yaratilmadi: {r.status_code} {r.text[:300]}")
    return oid


def detal(oid):
    d = SessionLocal()
    try:
        it = d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).first()
        return it.id, it.name
    finally:
        d.close()


def brak_tana(oid, miqdor=10, qoplama=False, **qoshimcha):
    iid, nom = detal(oid)
    t = {"order_id": oid, "order_item_id": iid, "item_name": nom, "quantity": miqdor, "unit": "metr",
         "reason": "Brak", "refund_amount": 0, "to_stock": False, "coating_applied": bool(qoplama)}
    t.update(qoshimcha)
    return t


def stoklar():
    d = SessionLocal()
    try:
        return tuple(round(float(d.get(Inventory, i).stock_quantity or 0), 9)
                     for i in (PENO_ID, KLEY_ID, AKR_ID, LOY_ID))
    finally:
        d.close()


def holat():
    """Yozuv sonlari + material qoldiqlari + tayyor mahsulotlar miqdori — 'hech narsa yozilmadi' isboti."""
    d = SessionLocal()
    try:
        return (d.query(ReturnItem).count(), d.query(FinishedProductLoss).count(),
                d.query(InventoryMovement).count(),
                round(sum(float(f.quantity or 0) for f in d.query(FinishedProduct).all()), 9)) + stoklar()
    finally:
        d.close()


def qaytarish(rid):
    if rid is None:
        return None
    d = SessionLocal()
    try:
        return d.get(ReturnItem, rid)
    finally:
        d.close()


def sj(obj):
    """(sabab, javobgar) — yangi ustunlar (asl kodda 'USTUN YO'Q')."""
    if obj is None:
        return ("YOZUV YO'Q", "YOZUV YO'Q")
    return (getattr(obj, "brak_sabab", "USTUN YO'Q"), getattr(obj, "brak_javobgar_id", "USTUN YO'Q"))


def harakat_shakli(rid):
    """Brak yozuviga bog'langan harakatlar: (material, tur, miqdor, narx, is_brak) — id siz."""
    if rid is None:
        return []
    d = SessionLocal()
    try:
        return sorted((h.inventory_id, h.movement_type, round(float(h.quantity or 0), 9),
                       h.unit_cost, getattr(h, "is_brak", None))
                      for h in d.query(InventoryMovement).filter(InventoryMovement.return_item_id == rid).all())
    finally:
        d.close()


def yozuv_shakli(rid):
    """Brak yozuvining sabab / javobgardan boshqa hamma mazmuni (bosqich ham)."""
    q = qaytarish(rid)
    if not q:
        return None
    return (q.quantity, q.unit, str(q.reason), round(float(q.refund_amount or 0), 2), q.is_refunded,
            q.coating_applied, q.notes, q.stock_qty, q.finished_product_id, getattr(q, "brak_bosqich", None))


def fp_yarat(nom, tayyor=True):
    d = SessionLocal()
    try:
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=True, quantity=100,
                             produced_quantity=100, unit="metr", unit_price=0, cost_price=1_000_000,
                             source=StockSource.PRODUCED, penoplast_id=PENO_ID, recipe_id=R1_ID,
                             unit_volume_m3=0.01, unit_loy_kg=0.5,
                             production_status=(ProductionStatus.READY if tayyor else ProductionStatus.IN_PROGRESS))
        d.add(fp)
        d.commit()
        return fp.id
    finally:
        d.close()


def fp_holat(fp_id):
    d = SessionLocal()
    try:
        fp = d.get(FinishedProduct, fp_id)
        return (round(float(fp.quantity or 0), 9), round(float(fp.cost_price or 0), 4))
    finally:
        d.close()


def yoqotishlar(fp_id):
    """(miqdor, birlik, tan narx, sabab matni, bosqich, brak_sabab, javobgar) — mahsulot yo'qotishlari."""
    d = SessionLocal()
    try:
        return [(l.quantity, l.unit, round(float(l.cost_amount or 0), 2), l.reason,
                 getattr(l, "brak_bosqich", "YO'Q")) + sj(l)
                for l in d.query(FinishedProductLoss).filter(FinishedProductLoss.finished_product_id == fp_id)
                .order_by(FinishedProductLoss.id).all()]
    finally:
        d.close()


def delta(oldin, keyin):
    return tuple(round(k - o, 9) for o, k in zip(oldin, keyin))


def html(c, url):
    r = req(c, "get", url)
    return r.status_code, (r.text if r.status_code == 200 else "")


def tanlov(h, sel_id):
    """<select id=...> variantlari: [(qiymat, matn)] — matn HTML dan ochilgan."""
    m = re.search(r'<select id="' + re.escape(sel_id) + r'"[^>]*>(.*?)</select>', h, re.S)
    if not m:
        return None
    return [(v, _html.unescape(t)) for v, t in re.findall(r'<option value="([^"]*)">([^<]*)</option>', m.group(1))]


def tahlil(c, **params):
    r = req(c, "get", "/api/reports/brak-tahlil", params=params)
    return r.status_code, js(r)


# ══════════════════════════════════════════════════════════════
# A — lug'at, model, sxema, me'yor
# ══════════════════════════════════════════════════════════════
section("A — lug'at, model, sxema, me'yor")
_lugat = getattr(crud, "BRAK_SABABLARI", None)
check("A1 crud.BRAK_SABABLARI — foydalanuvchi ro'yxati (5 ta, tartib bilan, yorliqlar AYNAN)",
      isinstance(_lugat, dict) and list(_lugat.keys()) == SABAB_KODLARI
      and list(_lugat.values()) == SABAB_YORLIQLARI, _lugat)
check("A2 me'yor — crud.BRAK_MEYORI_FOIZ = 5.0 (foydalanuvchi qarori)",
      getattr(crud, "BRAK_MEYORI_FOIZ", None) == 5.0, getattr(crud, "BRAK_MEYORI_FOIZ", None))
_sx_holat = []
for _cls in (schemas.ReturnItemCreate, schemas.FinishedProductLossCreate, schemas.FinishedProductProductionBrakCreate):
    _f = getattr(_cls, "model_fields", {}).get("brak_sabab")
    _args = []
    if _f is not None:
        for _a in typing.get_args(_f.annotation):
            _args.extend(typing.get_args(_a))
    _j = getattr(_cls, "model_fields", {}).get("brak_javobgar_id")
    _sx_holat.append((_cls.__name__, _args, _j is not None and _j.default is None))
check("A3 uchala sxemada brak_sabab Literal ro'yxati lug'at bilan AYNAN, brak_javobgar_id standarti None",
      all(a == SABAB_KODLARI and j for _, a, j in _sx_holat), _sx_holat)
_ust = []
for _m in (ReturnItem, FinishedProductLoss):
    _s = _m.__table__.c.get("brak_sabab")
    _j = _m.__table__.c.get("brak_javobgar_id")
    _fk = list(_j.foreign_keys) if _j is not None else []
    _ust.append((_m.__name__,
                 _s is not None and getattr(_s.type, "length", None) == 20 and _s.nullable and _s.default is None,
                 _j is not None and _j.nullable and _j.default is None and bool(_j.index)
                 and len(_fk) == 1 and _fk[0].target_fullname == "employees.id" and _fk[0].ondelete == "SET NULL"))
check("A4 modellarda ustunlar: brak_sabab String(20) STANDARTSIZ; brak_javobgar_id FK employees SET NULL + indeks",
      all(a and b for _, a, b in _ust), _ust)
import models as _models                           # noqa: E402
_tr = getattr(_models, "_TENANT_REFS", {})
check("A5 _TENANT_REFS: ikkala modelda (brak_javobgar_id, Employee) — begona hodim ORM darajasida ham rad",
      ("brak_javobgar_id", "Employee") in _tr.get("ReturnItem", [])
      and ("brak_javobgar_id", "Employee") in _tr.get("FinishedProductLoss", []), _tr.get("ReturnItem"))

# ══════════════════════════════════════════════════════════════
# B — buyurtma braki (POST /api/returns, returns.html)
# ══════════════════════════════════════════════════════════════
section("B — buyurtma braki: sabab va javobgar hodim")
oa, ob = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=10), \
    yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=10)
s0 = stoklar()
ra = req(C, "post", "/api/returns", json=brak_tana(oa, miqdor=5, qoplama=True, brak_bosqich="kesish"))
s1 = stoklar()
rb = req(C, "post", "/api/returns", json=brak_tana(ob, miqdor=5, qoplama=True, brak_bosqich="kesish",
                                                   brak_sabab="ishchi", brak_javobgar_id=H1_ID))
s2 = stoklar()
ida, idb = (js(ra) or {}).get("id"), (js(rb) or {}).get("id")
check("B1 brak: sababsiz va sabab 'ishchi' + javobgar H1 — ikkalasi 200",
      ra.status_code == 200 and rb.status_code == 200, (ra.status_code, ra.text[:200], rb.status_code, rb.text[:200]))
check("B1b yozuvda sabab 'ishchi' va javobgar H1; sababsizda NULL",
      sj(qaytarish(idb)) == ("ishchi", H1_ID) and sj(qaytarish(ida)) == (None, None),
      (sj(qaytarish(ida)), sj(qaytarish(idb))))
check("B1c QAT'IY SHART: xomashyo yechimi AYNAN (penoplast + loy)",
      delta(s0, s1) == delta(s1, s2) and delta(s0, s1)[0] < 0, (delta(s0, s1), delta(s1, s2)))
check("B1d QAT'IY SHART: yozuv mazmuni (miqdor, summa, bosqich, ...) va bog'langan harakatlar AYNAN",
      yozuv_shakli(ida) == yozuv_shakli(idb) and yozuv_shakli(ida) is not None
      and harakat_shakli(ida) == harakat_shakli(idb) and len(harakat_shakli(ida)) > 0,
      (yozuv_shakli(ida), yozuv_shakli(idb), harakat_shakli(ida), harakat_shakli(idb)))
_idlar = {}
for _kod in SABAB_KODLARI:
    _o = yarat([profil(40)])
    _x = req(C, "post", "/api/returns", json=brak_tana(_o, miqdor=2, brak_sabab=_kod))
    _idlar[_kod] = (js(_x) or {}).get("id")
check("B2 har 5 sabab kodi qabul qilinadi va AYNAN saqlanadi",
      all(sj(qaytarish(v))[0] == k for k, v in _idlar.items()), {k: sj(qaytarish(v)) for k, v in _idlar.items()})
_o = yarat([profil(40)])
_x1 = req(C, "post", "/api/returns", json=brak_tana(_o, miqdor=1, brak_sabab=None, brak_javobgar_id=None))
_o2 = yarat([profil(40)])
_x2 = req(C, "post", "/api/returns", json=brak_tana(_o2, miqdor=1, brak_sabab="  ", brak_javobgar_id=H3_ID))
check("B3 null / bo'sh sabab → NULL (200); nofaol (o'chirilmagan) hodim — qabul qilinadi",
      _x1.status_code == 200 and sj(qaytarish((js(_x1) or {}).get("id"))) == (None, None)
      and _x2.status_code == 200 and sj(qaytarish((js(_x2) or {}).get("id"))) == (None, H3_ID),
      (_x1.status_code, _x1.text[:150], _x2.status_code, _x2.text[:150]))
_ob = yarat([profil(40)])
for _nomi, _qiy in (("katta harf", "XOMASHYO"), ("yorliq matni", "Xomashyo sifati"), ("noma'lum", "sinish"),
                    ("son", 5), ("bool", True), ("ro'yxat", ["ishchi"])):
    h0 = holat()
    _x = req(C, "post", "/api/returns", json=brak_tana(_ob, miqdor=1, brak_sabab=_qiy))
    check(f"B4 sabab {_nomi} → 400, hech narsa yozilmadi, xomashyo yechilmadi",
          _x.status_code == 400 and "brak_sabab" in xabar(_x) and holat() == h0, (_x.status_code, _x.text[:200]))
for _nomi, _qiy, _kut in (("0", 0, "brak_javobgar_id"), ("manfiy", -1, "brak_javobgar_id"),
                          ("matn", "1", "brak_javobgar_id"), ("bool", True, "brak_javobgar_id"),
                          ("kasr", 1.5, "brak_javobgar_id"), ("juda katta", 2 ** 31, "brak_javobgar_id"),
                          ("yo'q hodim", 999_999, "Javobgar hodim topilmadi"),
                          ("begona korxona hodimi", HB_ID, "Javobgar hodim topilmadi"),
                          ("o'chirilgan hodim", H4_ID, "Javobgar hodim topilmadi")):
    h0 = holat()
    _x = req(C, "post", "/api/returns", json=brak_tana(_ob, miqdor=1, brak_javobgar_id=_qiy))
    check(f"B5 javobgar {_nomi} → 400 ({_kut}), hech narsa yozilmadi",
          _x.status_code == 400 and _kut in xabar(_x) and holat() == h0, (_x.status_code, _x.text[:200]))
for _nomi, _qosh in (("sabab", {"brak_sabab": "xomashyo"}), ("javobgar", {"brak_javobgar_id": H1_ID})):
    h0 = holat()
    _t = brak_tana(_ob, miqdor=1, **_qosh)
    _t.update({"reason": "Ortiqcha", "to_stock": False, "coating_applied": False})
    _x = req(C, "post", "/api/returns", json=_t)
    check(f"B6 'Ortiqcha' + {_nomi} → 400 (faqat brak uchun), hech narsa yozilmadi",
          _x.status_code == 400 and "faqat" in xabar(_x) and "Brak" in xabar(_x) and holat() == h0,
          (_x.status_code, _x.text[:200]))
_ro = js(req(C, "get", "/api/returns")) or []
_api = {x.get("id"): (x.get("brak_sabab", "YO'Q"), x.get("brak_javobgar_id", "YO'Q")) for x in _ro if isinstance(x, dict)}
check("B7 GET /api/returns — har yozuvda brak_sabab va brak_javobgar_id",
      _api.get(idb) == ("ishchi", H1_ID) and _api.get(ida) == (None, None), (_api.get(ida), _api.get(idb)))
_st, _h = html(C, "/returns")
_sab = [_html.unescape(x) for x in re.findall(r'<div class="brak-sabab"[^>]*>([^<]*)</div>', _h)]
_jav = [_html.unescape(x) for x in re.findall(r'<div class="brak-javobgar"[^>]*>([^<]*)</div>', _h)]
_sababli = sum(1 for x in _ro if isinstance(x, dict) and x.get("brak_sabab"))
_javobgarli = sum(1 for x in _ro if isinstance(x, dict) and x.get("brak_javobgar_id"))
check("B8 /returns ro'yxati: sababli HAR brak qatorida yorliq (kod emas), javobgarlida 👤 ism",
      _st == 200 and len(_sab) == _sababli and "Ishchi xatosi" in _sab and not any(x in SABAB_KODLARI for x in _sab)
      and len(_jav) == _javobgarli and ("👤 " + H1_ISM) in _jav, (_st, _sab[:8], _jav[:4]))
check("B8b hodim ismi HTML sifatida chizilmaydi (escape) — xom teg sahifada YO'Q",
      _st == 200 and "<i class=xq>" not in _h and "&lt;i class=xq&gt;" in _h, _st)
check("B8c brak oynasida #brak-cause: '— Tanlanmagan —' + 5 sabab (lug'atdan, tartib bilan)",
      tanlov(_h, "brak-cause") == [("", "— Tanlanmagan —")] + list(zip(SABAB_KODLARI, SABAB_YORLIQLARI)),
      tanlov(_h, "brak-cause"))
_w = tanlov(_h, "brak-worker") or []
_kut_w = sorted([(str(H1_ID), H1_ISM + " — Kesuvchi"), (str(H2_ID), "BT Qoplovchi — Qoplovchi"),
                 (str(H5_ID), "BT Ketadigan")], key=lambda t: t[1])
check("B8d brak oynasida #brak-worker: faqat FAOL, o'chirilmagan, O'Z korxonasi hodimlari (ism tartibida)",
      _w[:1] == [("", "— Tanlanmagan —")] and sorted(_w[1:], key=lambda t: t[1]) == _kut_w
      and [t[1] for t in _w[1:]] == sorted(t[1] for t in _w[1:]), _w)
_d = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        _sx = schemas.ReturnItemCreate(**brak_tana(_ob, miqdor=1))
    _sx.reason = "Ortiqcha"
    _sx.to_stock = False
    try:
        _sx.brak_javobgar_id = H1_ID
    except Exception:                      # noqa: BLE001
        pass
    h0 = holat()
    try:
        crud.create_return_item(_d, _sx, company_id=1)
        _b9 = "YOZILDI"
    except ValueError as e:
        _d.rollback()
        _b9 = f"ValueError: {e}"
    except Exception as e:                 # noqa: BLE001
        _d.rollback()
        _b9 = f"{type(e).__name__}: {e}"
finally:
    _d.close()
check("B9 crud.create_return_item (marshrutsiz): 'Ortiqcha' + javobgar → ValueError, hech narsa yozilmadi",
      _b9.startswith("ValueError") and "faqat" in _b9 and holat() == h0, (_b9, h0, holat()))

# ══════════════════════════════════════════════════════════════
# C — "Kamaytirish" va ishlab chiqarish braki (finished.html)
# ══════════════════════════════════════════════════════════════
section("C — tayyor mahsulot: kamaytirish va ishlab chiqarish braki")
F1, F2 = fp_yarat("BT tayyor 1"), fp_yarat("BT tayyor 2")
r1 = req(C, "post", "/api/finished/loss", json={"finished_product_id": F1, "quantity": 5, "reason": "tashishda sindi",
                                                 "brak_bosqich": "saqlash_tashish"})
r2 = req(C, "post", "/api/finished/loss", json={"finished_product_id": F2, "quantity": 5, "reason": "tashishda sindi",
                                                 "brak_bosqich": "saqlash_tashish", "brak_sabab": "boshqa",
                                                 "brak_javobgar_id": H2_ID})
y1, y2 = yoqotishlar(F1), yoqotishlar(F2)
check("C1 kamaytirish: sababsiz va sabab 'boshqa' + javobgar H2 — ikkalasi 200",
      r1.status_code == 200 and r2.status_code == 200, (r1.status_code, r1.text[:200], r2.status_code, r2.text[:200]))
check("C1b yozuv: sabab / javobgar yozildi (sababsizda NULL); qolgan mazmun AYNAN; qoldiq va tan narx AYNAN",
      len(y1) == 1 and len(y2) == 1 and y2[0][5:] == ("boshqa", H2_ID) and y1[0][5:] == (None, None)
      and y1[0][:5] == y2[0][:5] and fp_holat(F1) == fp_holat(F2) == (95.0, 950000.0), (y1, y2))
for _nomi, _tana, _kut in (("noma'lum sabab", {"brak_sabab": "sinish"}, "brak_sabab"),
                           ("begona hodim", {"brak_javobgar_id": HB_ID}, "Javobgar hodim topilmadi"),
                           ("o'chirilgan hodim", {"brak_javobgar_id": H4_ID}, "Javobgar hodim topilmadi"),
                           ("javobgar matn", {"brak_javobgar_id": "2"}, "brak_javobgar_id")):
    h0, f0 = holat(), fp_holat(F1)
    _x = req(C, "post", "/api/finished/loss", json={"finished_product_id": F1, "quantity": 5, **_tana})
    check(f"C2 kamaytirish {_nomi} → 400 ({_kut}), qoldiq va yozuvlar o'zgarmadi",
          _x.status_code == 400 and _kut in xabar(_x) and holat() == h0 and fp_holat(F1) == f0,
          (_x.status_code, _x.text[:200]))
F3, F4 = fp_yarat("BT jarayon 1", tayyor=False), fp_yarat("BT jarayon 2", tayyor=False)
s0 = stoklar()
p3 = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F3, "brak_qty": 4,
                                                             "brak_bosqich": "qoplash"})
s1 = stoklar()
p4 = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F4, "brak_qty": 4,
                                                             "brak_bosqich": "qoplash", "brak_sabab": "uskuna",
                                                             "brak_javobgar_id": H1_ID})
s2 = stoklar()
y3, y4 = yoqotishlar(F3), yoqotishlar(F4)
check("C3 ishlab chiqarish braki: sababsiz va 'uskuna' + H1 — ikkalasi 200",
      p3.status_code == 200 and p4.status_code == 200, (p3.status_code, p3.text[:200], p4.status_code, p4.text[:200]))
check("C3b QAT'IY SHART: xomashyo yechimi, tan narx, sabab matni AYNAN; sabab / javobgar yozildi",
      delta(s0, s1) == delta(s1, s2) and delta(s0, s1)[0] < 0 and len(y3) == 1 and len(y4) == 1
      and y3[0][:5] == y4[0][:5] and y4[0][5:] == ("uskuna", H1_ID) and y3[0][5:] == (None, None),
      (delta(s0, s1), delta(s1, s2), y3, y4))
for _nomi, _tana, _kut in (("noma'lum sabab", {"brak_sabab": "Uskuna"}, "brak_sabab"),
                           ("begona hodim", {"brak_javobgar_id": HB_ID}, "Javobgar hodim topilmadi"),
                           ("yo'q hodim", {"brak_javobgar_id": 987_654}, "Javobgar hodim topilmadi")):
    h0 = holat()
    _x = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F3, "brak_qty": 4, **_tana})
    check(f"C4 ishlab chiqarish braki {_nomi} → 400 ({_kut}), xomashyo YECHILMADI, yozuv yo'q",
          _x.status_code == 400 and _kut in xabar(_x) and holat() == h0, (_x.status_code, _x.text[:200]))
_st, _hf = html(C, "/finished")
_wf = tanlov(_hf, "loss-worker") or []
check("C5 /finished 'Kamaytirish' oynasida #loss-cause (5 sabab) va #loss-worker (faol hodimlar)",
      _st == 200 and tanlov(_hf, "loss-cause") == [("", "— Tanlanmagan —")] + list(zip(SABAB_KODLARI, SABAB_YORLIQLARI))
      and sorted(_wf[1:], key=lambda t: t[1]) == _kut_w and "<i class=xq>" not in _hf,
      (_st, tanlov(_hf, "loss-cause"), _wf))

# ══════════════════════════════════════════════════════════════
# D — tahlil: ulush, me'yor, ogohlantirish (get_monthly_report almashtirilgan)
# ══════════════════════════════════════════════════════════════
section("D — tahlil: ulush va me'yor")
_asl_rep = services.get_monthly_report
FAKE = {}


def _soxta_rep(db, year, month, company_id=None):
    b, i = FAKE.get((year, month), (0, 0))
    return {"brak_xarajat": b, "ishlab_chiqarish_xarajat": i}


def _tahlil_soxta(yil, oy, oylar=1):
    services.get_monthly_report = _soxta_rep
    try:
        return tahlil(C, year=yil, month=oy, oylar=oylar)
    finally:
        services.get_monthly_report = _asl_rep


FAKE[(2030, 3)] = (5_000, 100_000)
_s, _d1 = _tahlil_soxta(2030, 3)
_d1 = _d1 or {}
check("D1 aynan me'yorda (5 000 / 100 000 = 5 %) → ulush 5.0, ogohlantirish YO'Q",
      _s == 200 and _d1.get("brak_foizi") == 5.0 and _d1.get("meyordan_oshdi") is False
      and _d1.get("ogohlantirish") is None and _d1.get("meyor_foiz") == 5.0, (_s, str(_d1)[:300]))
FAKE[(2030, 4)] = (5_010, 100_000)
_s, _d2 = _tahlil_soxta(2030, 4)
_d2 = _d2 or {}
check("D2 me'yordan oshdi (5.01 %) → meyordan_oshdi, ogohlantirish matni AYNAN",
      _s == 200 and _d2.get("brak_foizi") == 5.01 and _d2.get("meyordan_oshdi") is True
      and _d2.get("ogohlantirish") == "Brak me'yordan oshdi: 5.01 % (me'yor 5 %)", (_s, str(_d2)[:300]))
FAKE[(2030, 5)] = (5_004, 100_000)
_s, _d2b = _tahlil_soxta(2030, 5)
check("D2b 5.004 % → 5.0 (2 xona) — ko'rsatilgan son bilan bir xil: ogohlantirish YO'Q",
      _s == 200 and (_d2b or {}).get("brak_foizi") == 5.0 and (_d2b or {}).get("meyordan_oshdi") is False,
      (_s, str(_d2b)[:300]))
FAKE[(2030, 6)] = (1_000, 0)
_s, _d3 = _tahlil_soxta(2030, 6)
_d3 = _d3 or {}
check("D3 ishlab chiqarish 0 → ulush None (hisoblab bo'lmaydi), ogohlantirish YO'Q",
      _s == 200 and "brak_foizi" in _d3 and _d3.get("brak_foizi") is None and _d3.get("meyordan_oshdi") is False
      and _d3.get("ogohlantirish") is None and _d3.get("brak_xarajat") == 1000, (_s, str(_d3)[:300]))
FAKE[(2030, 7)] = (0, 250_000)
_s, _d3b = _tahlil_soxta(2030, 7)
check("D3b brak 0 → ulush 0.0, ogohlantirish yo'q",
      _s == 200 and (_d3b or {}).get("brak_foizi") == 0.0 and (_d3b or {}).get("meyordan_oshdi") is False,
      (_s, str(_d3b)[:200]))
FAKE.update({(2029, 11): (7_000, 100_000), (2029, 12): (1_000, 50_000), (2030, 1): (3_333, 99_990)})
_s, _d4 = _tahlil_soxta(2030, 1, oylar=3)
_tr = (_d4 or {}).get("trend") or []
check("D4 oylar=3 (yil o'tishi): 2029-11, 2029-12, 2030-01 — eskisidan yangisiga, har oy o'z ulushi",
      _s == 200 and [(t.get("yil"), t.get("oy")) for t in _tr] == [(2029, 11), (2029, 12), (2030, 1)]
      and [t.get("brak_foizi") for t in _tr] == [7.0, 2.0, 3.33]
      and [t.get("meyordan_oshdi") for t in _tr] == [True, False, False]
      and (_d4 or {}).get("brak_foizi") == 3.33 and (_d4 or {}).get("ogohlantirish") is None, (_s, _tr))
_s, _d4b = _tahlil_soxta(2030, 1, oylar=1)
check("D4b oylar=1 — faqat tanlangan oy",
      _s == 200 and len((_d4b or {}).get("trend") or []) == 1, (_s, str(_d4b)[:200]))
for _nomi, _p in (("oy 13", {"year": 2026, "month": 13}), ("oy 0", {"year": 2026, "month": 0}),
                  ("yil 1999", {"year": 1999, "month": 5}), ("oylar 0", {"oylar": 0}), ("oylar 25", {"oylar": 25}),
                  ("oy matn", {"month": "abc"})):
    _s, _ = tahlil(C, **_p)
    check(f"D5 noto'g'ri so'rov ({_nomi}) → 400 / 422", _s in (400, 422), _s)
_s, _d5 = tahlil(C, oylar=1)
check("D5b parametrsiz — joriy oy (UTC, Moliya bilan bir xil)",
      _s == 200 and (_d5 or {}).get("yil") == YIL and (_d5 or {}).get("oy") == OY, (_s, str(_d5)[:200]))
_ruxsat = [(n, tahlil(c, oylar=1)[0]) for n, c in (("ombor", CW), ("menejer", CM), ("moliyachi", CF), ("admin", C))]
check("D6 huquq: ombor / menejer → 403; moliyachi va admin → 200 (pul ma'lumoti — Moliya huquqi)",
      _ruxsat == [("ombor", 403), ("menejer", 403), ("moliyachi", 200), ("admin", 200)], _ruxsat)

# ══════════════════════════════════════════════════════════════
# E — tahlil: haqiqiy yozuvlar bo'yicha taqsimot
# ══════════════════════════════════════════════════════════════
section("E — taqsimot (bosqich, sabab, javobgar, detal, yo'qotishlar)")
# Qo'shimcha: brakdan boshqa qaytarish (hisobga KIRMAYDI) va o'tgan oyga surilgan brak.
_oo = yarat([profil(40)])
_ort = req(C, "post", "/api/returns", json=dict(brak_tana(_oo, miqdor=1), reason="Ortiqcha", to_stock=False,
                                                coating_applied=False))
_oe = yarat([profil(40)])
_eski = req(C, "post", "/api/returns", json=brak_tana(_oe, miqdor=3, brak_sabab="xomashyo"))
_eski_id = (js(_eski) or {}).get("id")
_OY_OLDIN = (YIL - 1, 12) if OY == 1 else (YIL, OY - 1)
_d = SessionLocal()
try:
    _q = _d.get(ReturnItem, _eski_id)
    if _q is not None:
        _q.returned_at = datetime(_OY_OLDIN[0], _OY_OLDIN[1], 15, 12, 0, 0)
        _d.commit()
finally:
    _d.close()


def kutilgan(korxona=1, yil=YIL, oy=OY):
    """Test o'zi (mustaqil) hisoblagan taqsimot: shu oy brak yozuvlari + yo'qotishlar."""
    d = SessionLocal()
    try:
        yoz = []
        for r in d.query(ReturnItem).filter(ReturnItem.company_id == korxona).all():
            if r.reason == ReturnReason.DEFECT and r.returned_at and (r.returned_at.year, r.returned_at.month) == (yil, oy):
                yoz.append((r.item_name, r.unit, float(r.quantity), float(r.refund_amount or 0),
                            getattr(r, "brak_bosqich", None), getattr(r, "brak_sabab", None),
                            getattr(r, "brak_javobgar_id", None)))
        for l in d.query(FinishedProductLoss).filter(FinishedProductLoss.company_id == korxona).all():
            if l.lost_at and (l.lost_at.year, l.lost_at.month) == (yil, oy):
                yoz.append((l.product_name, l.unit, float(l.quantity), float(l.cost_amount or 0),
                            getattr(l, "brak_bosqich", None), getattr(l, "brak_sabab", None),
                            getattr(l, "brak_javobgar_id", None)))
        return yoz
    finally:
        d.close()


def guruh(yoz, idx):
    g = {}
    for y in yoz:
        a = g.setdefault(y[idx], [0, 0.0])
        a[0] += 1
        a[1] += y[3]
    return g


def jadval_tekshir(arr, g, yorliq):
    """API qatorlari: (kod → soni, qiymat) AYNAN; qiymat kamayishi; 'Belgilanmagan' oxirida; yorliqlar.
    Kutilmagan shakl (mutatsiya) — yiqilgan tekshiruv, qulamaydi."""
    try:
        return _jadval_tekshir(arr, g, yorliq)
    except Exception as e:                 # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def _jadval_tekshir(arr, g, yorliq):
    if not isinstance(arr, list):
        return False, "ro'yxat emas"
    api = {x.get("kod"): (x.get("soni"), round(float(x.get("qiymat") or 0), 2)) for x in arr}
    kut = {k: (v[0], round(v[1], 2)) for k, v in g.items()}
    if api != kut:
        return False, (api, kut)
    kodlilar = [x for x in arr if x.get("kod") is not None]
    if [x.get("qiymat") for x in kodlilar] != sorted([x.get("qiymat") for x in kodlilar], reverse=True):
        return False, "tartib"
    if None in g and arr[-1].get("kod") is not None:
        return False, "Belgilanmagan oxirida emas"
    for x in arr:
        kut_nom = "Belgilanmagan" if x.get("kod") is None else yorliq(x.get("kod"))
        if x.get("nomi") != kut_nom:
            return False, ("yorliq", x)
    return True, ""


_yoz = kutilgan()
_s, _e = tahlil(C, year=YIL, month=OY, oylar=1)
_e = _e or {}
_jami = round(sum(y[3] for y in _yoz), 2)
check("E1 yozuvlar soni va qiymati — shu oyning brak yozuvlari + yo'qotishlar (brakdan boshqasi va o'tgan oy YO'Q)",
      _s == 200 and _e.get("yozuvlar_soni") == len(_yoz) and taxminan(_e.get("yozuvlar_qiymati"), _jami, 0.01)
      and _ort.status_code == 200 and _eski.status_code == 200,
      (_s, _e.get("yozuvlar_soni"), len(_yoz), _e.get("yozuvlar_qiymati"), _jami))
_ok, _det = jadval_tekshir(_e.get("bosqichlar"), guruh(_yoz, 4), lambda k: BOSQICH_YORLIQ.get(k, k))
check("E2 bosqich bo'yicha: soni va qiymat AYNAN, qiymat kamayishi, 'Belgilanmagan' oxirida", _ok, _det)
_ok, _det = jadval_tekshir(_e.get("sabablar"), guruh(_yoz, 5), lambda k: dict(zip(SABAB_KODLARI, SABAB_YORLIQLARI)).get(k, k))
check("E3 sabab bo'yicha: soni va qiymat AYNAN, yorliqlar lug'atdan", _ok, _det)
_ismlar = {H1_ID: H1_ISM, H2_ID: "BT Qoplovchi", H3_ID: "BT Nofaol", H5_ID: "BT Ketadigan"}
_ok, _det = jadval_tekshir(_e.get("javobgarlar"), guruh(_yoz, 6), lambda k: _ismlar.get(k, "?"))
check("E4 javobgar bo'yicha: soni va qiymat AYNAN, ismlar (xom — UI escape qiladi)", _ok, _det)
_ul = sum(float(x.get("ulush") or 0) for x in (_e.get("sabablar") or []))
check("E5 ulushlar yig'indisi ~100 %", abs(_ul - 100.0) <= 0.5, _ul)
_top = _e.get("top_detallar") or []
_dg = {}
for y in _yoz:
    a = _dg.setdefault((y[0], y[1]), [0, 0.0, 0.0])
    a[0] += 1
    a[1] += y[2]
    a[2] += y[3]
_kut_top = sorted(_dg.items(), key=lambda kv: (-kv[1][2], kv[0][0], kv[0][1]))[:5]
check("E6 eng ko'p brak — ko'pi bilan 5 ta, (nom, birlik) bo'yicha, qiymat kamayishi, miqdor va soni AYNAN",
      len(_top) == min(5, len(_dg)) and
      [(x.get("nomi"), x.get("birlik"), x.get("soni"), round(float(x.get("miqdor") or 0), 3),
        round(float(x.get("qiymat") or 0), 2)) for x in _top]
      == [(k[0], k[1], v[0], round(v[1], 3), round(v[2], 2)) for k, v in _kut_top], (_top, _kut_top))
_yq = _e.get("yoqotishlar") or []


def _nkal(t):
    """None / har xil turli kortejni xavfsiz saralash kaliti (mutatsiyada qulamaslik uchun)."""
    return tuple("" if v is None else str(v) for v in t)


_turlar = sorted(((x.get("nomi"), x.get("turi"), x.get("sabab"), x.get("javobgar"), x.get("bosqich"))
                  for x in _yq if isinstance(x, dict)), key=_nkal)
check("E7 yo'qotishlar ro'yxati: 4 ta (2 kamaytirish + 2 ishlab chiqarish braki), turi / sabab / javobgar / bosqich yorliqlari",
      len(_yq) == 4 and _turlar == sorted([
          ("BT tayyor 1", "Yo'qotish (tayyor turgan)", None, None, "Saqlash / tashish"),
          ("BT tayyor 2", "Yo'qotish (tayyor turgan)", "Boshqa", "BT Qoplovchi", "Saqlash / tashish"),
          ("BT jarayon 1", "Ishlab chiqarish braki", None, None, "Qoplash (loy tortish)"),
          ("BT jarayon 2", "Ishlab chiqarish braki", "Uskuna / stanok nosozligi", H1_ISM, "Qoplash (loy tortish)")],
          key=_nkal),
      _turlar)
_s, _eo = tahlil(C, year=_OY_OLDIN[0], month=_OY_OLDIN[1], oylar=1)
check("E8 o'tgan oy so'ralsa — o'sha oyga surilgan brak (1 ta, sabab 'xomashyo') ko'rinadi",
      _s == 200 and (_eo or {}).get("yozuvlar_soni") == 1
      and [x.get("kod") for x in (_eo or {}).get("sabablar") or []] == ["xomashyo"], (_s, str(_eo)[:300]))
_rep = js(req(C, "get", "/api/finance/report", params={"year": YIL, "month": OY})) or {}
_ich = float(_rep.get("ishlab_chiqarish_xarajat") or 0)
_kut_f = round(float(_rep.get("brak_xarajat") or 0) / _ich * 100, 2) if _ich > 0 else None
check("E9 ulush Moliya bilan BIR manba: brak_xarajat va ishlab chiqarish /api/finance/report bilan AYNAN",
      _e.get("brak_xarajat") == _rep.get("brak_xarajat") and _e.get("ishlab_chiqarish_xarajat") == round(_ich)
      and _e.get("brak_foizi") == _kut_f and "brak_foizi" in _e,
      (_e.get("brak_xarajat"), _rep.get("brak_xarajat"), _e.get("ishlab_chiqarish_xarajat"), _ich, _e.get("brak_foizi")))
_s, _eb = tahlil(CB, year=YIL, month=OY, oylar=1)
check("E10 korxona B — A ning yozuvlari, hodimlari va yo'qotishlari KO'RINMAYDI",
      _s == 200 and (_eb or {}).get("yozuvlar_soni") == 0 and (_eb or {}).get("javobgarlar") == []
      and (_eb or {}).get("yoqotishlar") == [] and (_eb or {}).get("brak_xarajat") == 0, (_s, str(_eb)[:300]))
# E11 — hodim butunlay o'chirilsa: PG — FK SET NULL (yozuv 'Belgilanmagan'), SQLite — "O'chirilgan hodim".
_o5 = yarat([profil(40)])
_x5 = req(C, "post", "/api/returns", json=brak_tana(_o5, miqdor=2, brak_sabab="ishchi", brak_javobgar_id=H5_ID))
_id5 = (js(_x5) or {}).get("id")
_d = SessionLocal()
try:
    _hh = _d.get(Employee, H5_ID)
    _d.delete(_hh)
    _d.commit()
    _e11 = "o'chirildi"
except Exception as e:                     # noqa: BLE001
    _d.rollback()
    _e11 = f"{type(e).__name__}: {e}"
finally:
    _d.close()
_s, _e2 = tahlil(C, year=YIL, month=OY, oylar=1)
_jav = {x.get("kod"): x.get("nomi") for x in (_e2 or {}).get("javobgarlar") or []}
if PG_URL:
    check("E11 [PG] hodim butunlay o'chirildi → yozuvda javobgar NULL (FK ON DELETE SET NULL), brak saqlandi",
          _x5.status_code == 200 and _e11 == "o'chirildi" and sj(qaytarish(_id5)) == ("ishchi", None)
          and H5_ID not in _jav, (_x5.status_code, _e11, sj(qaytarish(_id5)), _jav))
else:
    check("E11 hodim butunlay o'chirildi → tahlilda 'O'chirilgan hodim' (tarixiy yozuv nomsiz qolmaydi)",
          _x5.status_code == 200 and _e11 == "o'chirildi" and _jav.get(H5_ID) == "O'chirilgan hodim",
          (_x5.status_code, _e11, _jav))
_st, _h = html(C, "/returns")
_stw, _hw = html(CW, "/returns")
_std, _hd = html(C, "/dashboard")
check("E12 /returns: admin sahifasida 'Brak tahlili' kartasi bor, omborchida YO'Q; /dashboard da ulush qatori",
      _st == 200 and 'id="brakTahlilCard"' in _h and _stw == 200 and 'id="brakTahlilCard"' not in _hw
      and _std == 200 and 'id="brk-foiz"' in _hd and 'id="brk-ogohlantirish"' in _hd, (_st, _stw, _std))

# ══════════════════════════════════════════════════════════════
# M — migratsiya (eski baza)
# ══════════════════════════════════════════════════════════════
section("M — migratsiya")
_mig = getattr(main, "_migrate_brak_sabab_javobgar", None)
_ustun_bor = (ReturnItem.__table__.c.get("brak_sabab") is not None
              and FinishedProductLoss.__table__.c.get("brak_sabab") is not None)
_m1 = ("o'tkazildi",)
if _ustun_bor:
    try:
        with _database.engine.connect() as _c:
            for _t in ("return_items", "finished_product_losses"):
                _c.execute(_sqltext(f"ALTER TABLE {_t} DROP COLUMN brak_sabab"))
                if PG_URL:
                    _c.execute(_sqltext(f"ALTER TABLE {_t} DROP COLUMN brak_javobgar_id"))
                else:
                    _c.execute(_sqltext(f"DROP INDEX IF EXISTS ix_{_t}_brak_javobgar_id"))
            _c.commit()
        with contextlib.redirect_stdout(_quiet):
            _database.sync_missing_columns()
        with _database.engine.connect() as _c:
            _m1 = tuple(tuple(_c.execute(_sqltext(f"SELECT COUNT(*), COUNT(brak_sabab), COUNT(brak_javobgar_id) FROM {_t}"))
                              .fetchone()) for _t in ("return_items", "finished_product_losses"))
    except Exception as e:                 # noqa: BLE001
        _m1 = (f"{type(e).__name__}: {e}",)
if PG_URL:
    check("M1 [PG] ustunlar olib tashlanib qayta qo'shildi — ESKI qatorlarda sabab va javobgar HAMMASI NULL (standart yo'q)",
          len(_m1) == 2 and all(isinstance(x, tuple) and x[0] > 0 and x[1] == 0 and x[2] == 0 for x in _m1), _m1)
else:
    check("M1 sabab ustuni olib tashlanib qayta qo'shildi — ESKI qatorlarda HAMMASI NULL (standart yo'q)",
          len(_m1) == 2 and all(isinstance(x, tuple) and x[0] > 0 and x[1] == 0 for x in _m1), _m1)


def _indekslar():
    from sqlalchemy import inspect as _ins
    i = _ins(_database.engine)
    return tuple(f"ix_{t}_brak_javobgar_id" in {ix["name"] for ix in i.get_indexes(t)}
                 for t in ("return_items", "finished_product_losses"))


def _fk():
    if not PG_URL:
        return ("SQLite",)
    with _database.engine.connect() as c:
        return tuple(tuple(r) for r in c.execute(_sqltext(
            "SELECT t.relname, c.confdeltype FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey) "
            "WHERE c.contype = 'f' AND a.attname = 'brak_javobgar_id' ORDER BY t.relname")).fetchall())


_oldin = (_indekslar(), _fk())
_xato = ""
try:
    with contextlib.redirect_stdout(_quiet):
        _mig()
        _mig()
except Exception as e:                     # noqa: BLE001
    _xato = f"{type(e).__name__}: {e}"
_keyin = (_indekslar(), _fk())
check("M2 migratsiya (ikki marta — idempotent): indeks ikkala jadvalda; PG da FK employees ON DELETE SET NULL (bittadan)",
      not _xato and _keyin[0] == (True, True)
      and (_keyin[1] == ("SQLite",) or _keyin[1] == (("finished_product_losses", "n"), ("return_items", "n"))),
      (_xato, _oldin, _keyin))
_o6 = yarat([profil(40)])
_x6 = req(C, "post", "/api/returns", json=brak_tana(_o6, miqdor=1, brak_sabab="olcham", brak_javobgar_id=H2_ID))
check("M3 migratsiyadan keyin yangi brak sabab va javobgar bilan yoziladi",
      _x6.status_code == 200 and sj(qaytarish((js(_x6) or {}).get("id"))) == ("olcham", H2_ID), (_x6.status_code, _x6.text[:200]))

# ══════════════════════════════════════════════════════════════
# S — statik: tartib, marshrutlar, yagona manba
# ══════════════════════════════════════════════════════════════
section("S — statik")


def tartibda(src, *qismlar):
    i = -1
    for q in qismlar:
        j = src.find(q, i + 1)
        if j < 0:
            return False
        i = j
    return True


_cr = inspect.getsource(crud.create_return_item)
check("S1 create_return_item: sabab / javobgar tekshiruvi yozuvdan va xomashyo yechilishidan OLDIN",
      tartibda(_cr, "Brak sababi va javobgar hodim faqat", "_brak_javobgar_tekshir(db, _javobgar, _o.company_id)",
               "item = ReturnItem(", "deduct_raw_material_for_brak"))
check("S2 create_return_item: sabab va javobgar faqat DEFECT da yoziladi",
      "brak_sabab=(_sabab if reason_enum == ReturnReason.DEFECT else None)" in _cr
      and "brak_javobgar_id=(_javobgar if reason_enum == ReturnReason.DEFECT else None)" in _cr)
_pb = inspect.getsource(crud.record_finished_product_production_brak)
check("S3 ishlab chiqarish braki: sabab _clean_val da, javobgar tekshiruvi xomashyo yechimidan va yozuvdan OLDIN",
      tartibda(_pb, '"brak_sabab": brak_sabab,', "_brak_javobgar_tekshir(db, brak_javobgar_id",
               "_ishlab_chiqarish_braki_xomashyo(", "loss = FinishedProductLoss(")
      and tartibda(_pb, "_brak_javobgar_tekshir(db, brak_javobgar_id", "_mrp_ishlab_chiqarish_braki_xomashyo(")
      and "brak_javobgar_id=brak_javobgar_id" in _pb)
_lo = inspect.getsource(crud.record_finished_product_loss)
check("S4 kamaytirish: javobgar tekshiruvi qoldiq o'zgarishidan va yozuvdan OLDIN",
      tartibda(_lo, "_brak_javobgar_tekshir(db, getattr(data, 'brak_javobgar_id', None)",
               "fp.quantity = available - data.quantity", "loss = FinishedProductLoss("))
_jt = inspect.getsource(getattr(crud, "_brak_javobgar_tekshir", lambda: None))
check("S5 javobgar tekshiruvi: o'chirilmagan hodim va korxona filtri",
      "Employee.is_deleted.isnot(True)" in _jt and "Employee.company_id == company_id" in _jt)
_ms = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("S6 marshrutlar: ishlab chiqarish braki sabab va javobgarni uzatadi; /returns va /finished kontekstida lug'at",
      "brak_sabab=data.brak_sabab," in _ms and "brak_javobgar_id=data.brak_javobgar_id," in _ms
      and _ms.count('"brak_sabablari": crud.BRAK_SABABLARI,') == 2)
_i7 = _ms.find('@app.get("/api/reports/brak-tahlil")')
_bosh7 = _ms[_i7:_ms.find('"""', _i7)] if _i7 >= 0 else ""
check("S7 tahlil marshruti Moliya huquqi bilan (admin_or_financier)",
      "def api_brak_tahlil(" in _bosh7 and "current_user=Depends(auth.admin_or_financier)" in _bosh7, _bosh7[:200])
check("S8 migratsiya: 37 / 38-band migratsiyalaridan KEYIN chaqiriladi, e'londan keyin",
      tartibda(_ms, "\n_migrate_brak_belgisi()\n", "def _migrate_brak_sabab_javobgar():", "\n_migrate_brak_sabab_javobgar()\n"))
_sv = inspect.getsource(getattr(services, "get_brak_tahlil", lambda: None))
check("S9 tahlil: ulush get_monthly_report dan (Moliya bilan BIR manba), me'yor crud.BRAK_MEYORI_FOIZ dan",
      "get_monthly_report(db, yy, mm, company_id=company_id)" in _sv and "_cr.BRAK_MEYORI_FOIZ" in _sv
      and "ReturnItem.company_id == company_id" in _sv and "FinishedProductLoss.company_id == company_id" in _sv)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
