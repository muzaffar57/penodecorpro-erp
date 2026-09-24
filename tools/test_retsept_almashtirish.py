#!/usr/bin/env python3
"""
test_retsept_almashtirish.py — 5-bo'lim 53-band (+ 67-band) darvozasi (kech63, 2026-09-24):
jarayondagi buyurtmada QOPLAMA RETSEPTI o'zgartirilsa eski retsept loyi omborga QAYTADI, yangisidan
YECHILADI.

NIMA UCHUN (asl kod `25bcd8d` / `78debfd` da O'LCHANGAN — `work/probe53.py`)
----------------------------------------------------------------------------
Qoralama EMAS buyurtma (profil 10 m qoplamali, R1, loy 30 kg — Kley 18 + Akril 12 yechilgan) `PUT` R2 bilan:
200 "Buyurtma yangilandi!", ombor TEGILMADI (R2 xomashyosi 0), `qoplama_retsept_id` R1 da qoldi, detal
`recipe_id` R2 (tahrir oynasi R2 ni ko'rsatadi), API da `qoplama_retsept_id` kaliti YO'Q; o'chirish loyni
R1 ga qaytardi. Ya'ni foydalanuvchi retseptni almashtirdim deb o'ylaydi, ombor esa eski retseptda — JIM.
FOYDALANUVCHI QARORI (kech62, tugma): "Oq loy omborga qaytsin, Kulrang yechilsin".

YECHIM (texnik — Claude): `crud.update_order_full` — tanlov o'zgarsa va loy yechilgan retseptdan farq qilsa:
loy rejasi eski retseptga qaytadi (o'chirishdagi yo'l), yangisidan yechiladi (yaratishdagi yo'l, avval tayyor
loy zaxirasi); qisman chiqqan / "Tayyor" buyurtmada — 400 va HECH NARSA yozilmaydi; yangi retsept xomashyosi
yetmasa — 409 (`confirm_shortage`); qulf ostida `commit=False` (bitta tranzaksiya). API `qoplama_retsept_id`,
tahrir oynasi retseptni undan oladi (eski NULL / nusxa — detallardan).

ASL KOD: yiqilishi SHART, qulamasligi SHART (yangi nomlar `getattr`, HTTP istisno → 599).
REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_retsept_almashtirish.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_retsept_almashtirish.py
"""
import os
import sys
import json
import inspect
import tempfile
import subprocess

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "retsept_almashtirish_test"
_DB = os.path.join(tempfile.gettempdir(), "retsept_almashtirish_test.db")

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
    import auth, services, crud                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Inventory, Recipe, RecipeIngredient, InventoryMovement, ActivityLog,
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
        with contextlib.redirect_stdout(_quiet):
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
    """Qismlar src ichida AYNAN shu tartibda uchraydimi (find — topilmasa False)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def _manba(f):
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — R1 (Kley 60 + Akril 40), R2 (Qum 100), R3 (Kam 100 — ombor 5 kg)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "RA63_admin", "Parol123!", UserRole.ADMIN, "RA63 Admin", company_id=1)
PRJ = Project(company_id=1, client_name="RA63 Mijoz", project_name="RA63 loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="RA63 Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="RA63 Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000, category="Kimyo")
AKR = Inventory(company_id=1, item_name="RA63 Akril", unit="kg", stock_quantity=100_000, price_per_unit=10_000, category="Kimyo")
QUM = Inventory(company_id=1, item_name="RA63 Qum", unit="kg", stock_quantity=100_000, price_per_unit=20_000, category="Xom")
KAM = Inventory(company_id=1, item_name="RA63 Kam", unit="kg", stock_quantity=5, price_per_unit=1_000, category="Xom")
KAM4 = Inventory(company_id=1, item_name="RA63 Kam4", unit="kg", stock_quantity=1, price_per_unit=1_000, category="Xom")
_db.add_all([PRJ, PENO, KLEY, AKR, QUM, KAM, KAM4])
_db.commit()
R1 = Recipe(company_id=1, name="RA63 R1", batch_size_kg=100.0)
R2 = Recipe(company_id=1, name="RA63 R2", batch_size_kg=100.0)
R3 = Recipe(company_id=1, name="RA63 R3", batch_size_kg=100.0)
R4 = Recipe(company_id=1, name="RA63 R4", batch_size_kg=100.0)   # tayyor loy pozitsiyasi ATAYLAB yaratilmaydi (H4)
_db.add_all([R1, R2, R3, R4])
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0),
             RecipeIngredient(recipe_id=R2.id, inventory_id=QUM.id, quantity_kg=100.0),
             RecipeIngredient(recipe_id=R3.id, inventory_id=KAM.id, quantity_kg=100.0),
             RecipeIngredient(recipe_id=R4.id, inventory_id=KAM4.id, quantity_kg=100.0)])
_db.commit()
ID = {k: v.id for k, v in dict(PRJ=PRJ, PENO=PENO, KLEY=KLEY, AKR=AKR, QUM=QUM, KAM=KAM, KAM4=KAM4,
                                  R1=R1, R2=R2, R3=R3, R4=R4).items()}
with contextlib.redirect_stdout(_quiet):
    _l1 = services.get_or_create_loy_stock(_db, _db.get(Recipe, ID["R1"]))
    _l2 = services.get_or_create_loy_stock(_db, _db.get(Recipe, ID["R2"]))
    _l3 = services.get_or_create_loy_stock(_db, _db.get(Recipe, ID["R3"]))
for _l in (_l1, _l2, _l3):
    _l.stock_quantity = 0.0
_db.commit()
ID["LOY1"], ID["LOY2"], ID["LOY3"] = _l1.id, _l2.id, _l3.id
_db.close()
NOMI = {ID[k]: k for k in ("KLEY", "AKR", "QUM", "KAM", "KAM4", "LOY1", "LOY2", "LOY3")}

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_s = req(C, "post", "/login", data={"username": "RA63_admin", "password": "Parol123!"}, follow_redirects=False)
if _s.status_code != 302:
    print(f"LOGIN BO'LMADI: {_s.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom():
    _n[0] += 1
    return f"RA63_D{_n[0]}"


def profil(uzunlik, rid, narx=50_000, qop=True):
    t = {"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": uzunlik, "quantity": 1,
         "unit_price": narx, "is_coated": qop, "penoplast_id": ID["PENO"]}
    if qop and rid:
        t["recipe_id"] = rid
    return t


def loy_sotish(kg, rid):
    return {"name": nom(), "category": "loy_sotish", "quantity": kg, "unit_price": 10_000, "is_coated": False,
            "penoplast_id": None, "recipe_id": rid}


def _tana(items, rid, loy_kg, qoralama=False):
    return {"project_id": ID["PRJ"], "order_type": "product", "items": items, "recipe_id": rid,
            "loy_kg": loy_kg, "is_draft": qoralama}


def yarat(items, rid, loy_kg=0, qoralama=False):
    r = req(C, "post", "/api/orders", json=_tana(items, rid, loy_kg, qoralama), params={"confirm_shortage": "true"})
    d = js(r)
    return (d.get("id") if isinstance(d, dict) else None), r


def tahrir(oid, items, rid, loy_kg=None, tasdiq=False):
    """UI `updateOrder` kabi: detallar AYNAN o'sha nomlar bilan (moslashadi), yangi retsept."""
    p = {"confirm_shortage": "true" if tasdiq else "false"}
    if loy_kg is not None:
        p["loy_kg"] = loy_kg
    for it in items:
        if (it.get("category") or "") != "loy_sotish" and it.get("is_coated"):
            it["recipe_id"] = rid
    return req(C, "put", f"/api/orders/{oid}", json=_tana(items, rid, loy_kg), params=p)


def stok():
    d = SessionLocal()
    try:
        return {k: float(d.get(Inventory, ID[k]).stock_quantity or 0) for k in NOMI.values()}
    finally:
        d.close()


def farq(a, b):
    return {k: round(b[k] - a[k], 6) for k in a if abs(b[k] - a[k]) > 1e-9}


def holat(oid):
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        if o is None:
            return {}
        its = d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()
        return {"qr": getattr(o, "qoplama_retsept_id", None), "reja": services._get_planned_loy(o),
                "detal_retsept": [i.recipe_id for i in its], "status": o.status.value if o.status else None,
                "jami": float(o.total_amount or 0)}
    finally:
        d.close()


def detallar(oid):
    d = SessionLocal()
    try:
        return [i.id for i in d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        d.close()


def harakatlar(oid):
    d = SessionLocal()
    try:
        q = d.query(InventoryMovement).filter(InventoryMovement.order_id == oid).order_by(InventoryMovement.id).all()
        return [(NOMI.get(h.inventory_id, h.inventory_id), h.movement_type, round(float(h.quantity or 0), 6),
                 h.reason or "") for h in q]
    finally:
        d.close()


def jurnal(r):
    d = js(r)
    return list((d or {}).get("inventory_log") or []) if isinstance(d, dict) else []


def detail(r):
    d = js(r)
    if isinstance(d, dict) and isinstance(d.get("detail"), dict):
        return d["detail"]
    return {}


# ══════════════════════════════════════════════════════════════
section("A. R1 -> R2, hech narsa topshirilmagan, loy 30 kg")
# ══════════════════════════════════════════════════════════════
s0 = stok()
itA = [profil(10, ID["R1"])]
oA, _r = yarat(itA, ID["R1"], loy_kg=30)
check("A0 buyurtma yaratildi", oA, getattr(_r, "text", "")[:200])
s1 = stok()
check("A1 yaratishda R1 dan 30 kg (Kley 18, Akril 12)", farq(s0, s1) == {"KLEY": -18.0, "AKR": -12.0}, farq(s0, s1))
check("A2 qoplama retsepti R1", holat(oA).get("qr") == ID["R1"], holat(oA))
_r = tahrir(oA, itA, ID["R2"])
s2 = stok()
check("A3 PUT R2 — 200", _r.status_code == 200, getattr(_r, "text", "")[:300])
check("A4 R1 loyi omborga QAYTDI (Kley +18, Akril +12), R2 dan 30 kg YECHILDI (Qum −30)",
      farq(s1, s2) == {"KLEY": 18.0, "AKR": 12.0, "QUM": -30.0}, farq(s1, s2))
hA = holat(oA)
check("A5 qoplama_retsept_id = R2", hA.get("qr") == ID["R2"], hA)
check("A6 detal retsepti R2, loy rejasi 30 (o'zgarmadi)", hA.get("detal_retsept") == [ID["R2"]] and taxminan(hA.get("reja"), 30), hA)
_j = jurnal(_r)
check("A7 jurnal boshida almashtirish qatori (ikkala retsept nomi, 30 kg)",
      _j and "almashtirildi" in _j[0] and "RA63 R1" in _j[0] and "RA63 R2" in _j[0] and "30 kg" in _j[0], _j[:3])
check("A8 jurnalda qaytarish va yechish qatorlari", any("Kley" in x and "+18.00" in x for x in _j)
      and any("Qum" in x and "-30.00" in x for x in _j), _j)
_h = harakatlar(oA)
check("A9 harakat: R1 ingredientlari 'in', sababi 'qoplama retsepti almashtirildi', order_id bilan",
      ("KLEY", "in", 18.0) in [x[:3] for x in _h] and ("AKR", "in", 12.0) in [x[:3] for x in _h]
      and all("almashtirildi" in x[3] for x in _h if x[1] == "in" and x[0] in ("KLEY", "AKR")), _h)
check("A10 harakat: Qum 'out' 30, sababi 'yangi qoplama retsepti'",
      any(x[:3] == ("QUM", "out", 30.0) and "yangi qoplama retsepti" in x[3] for x in _h), _h)
_g = js(req(C, "get", f"/api/orders/{oA}")) or {}
check("A11 GET /api/orders/{id} — qoplama_retsept_id kaliti = R2 (67-band)",
      isinstance(_g, dict) and _g.get("qoplama_retsept_id") == ID["R2"], {k: _g.get(k) for k in ("qoplama_retsept_id",)})
_d = SessionLocal()
try:
    _al = _d.query(ActivityLog).filter(ActivityLog.entity_type == "order", ActivityLog.entity_id == oA,
                                       ActivityLog.action == "updated").order_by(ActivityLog.id.desc()).first()
    _alv = (_al.new_value or "") if _al else ""
finally:
    _d.close()
check("A12 audit (ActivityLog) — qoplama retsepti «RA63 R1» → «RA63 R2»", "«RA63 R1» → «RA63 R2»" in _alv, _alv)
_r = tahrir(oA, itA, ID["R2"])
s3 = stok()
check("A13 xuddi shu retsept qayta saqlansa — 200 va ombor TEGILMAYDI", _r.status_code == 200 and farq(s2, s3) == {},
      (getattr(_r, "status_code", None), farq(s2, s3)))
_r = req(C, "delete", f"/api/orders/{oA}")
s4 = stok()
check("A14 o'chirish — loy R2 ga qaytdi (Qum +30), R1 ga tegilmadi", _r.status_code == 200 and farq(s3, s4) == {"QUM": 30.0},
      (getattr(_r, "status_code", None), farq(s3, s4)))
check("A15 butun aylanish sof: yaratishdan oldingi zaxira AYNAN", farq(s0, s4) == {}, farq(s0, s4))

# ══════════════════════════════════════════════════════════════
section("B. R1 -> R2 va loy 30 -> 40 BIRGA (PUT ?loy_kg=40)")
# ══════════════════════════════════════════════════════════════
itB = [profil(10, ID["R1"])]
oB, _r = yarat(itB, ID["R1"], loy_kg=30)
s0 = stok()
_r = tahrir(oB, itB, ID["R2"], loy_kg=40)
s1 = stok()
check("B1 PUT 200", _r.status_code == 200, getattr(_r, "text", "")[:300])
check("B2 R1 +30 (Kley 18, Akril 12), R2 −40 (Qum)", farq(s0, s1) == {"KLEY": 18.0, "AKR": 12.0, "QUM": -40.0}, farq(s0, s1))
check("B3 reja 40, qoplama R2", taxminan(holat(oB).get("reja"), 40) and holat(oB).get("qr") == ID["R2"], holat(oB))
_r = req(C, "delete", f"/api/orders/{oB}")
s2 = stok()
check("B4 o'chirish — R2 ga 40 qaytdi", farq(s1, s2) == {"QUM": 40.0}, farq(s1, s2))
_r = req(C, "post", f"/api/orders/{oB}/restore")
s3 = stok()
check("B5 tiklash (restore) — R2 dan 40 qayta yechildi (yoki buyurtma butunlay o'chgan)",
      (_r.status_code == 200 and farq(s2, s3) == {"QUM": -40.0}) or (_r.status_code in (404, 400) and farq(s2, s3) == {}),
      (getattr(_r, "status_code", None), farq(s2, s3)))

# ══════════════════════════════════════════════════════════════
section("C. Loy sotish detali o'z retseptida qoladi; loy 0 — faqat tanlov yoziladi")
# ══════════════════════════════════════════════════════════════
itC = [profil(10, ID["R1"]), loy_sotish(5, ID["R1"])]
oC, _r = yarat(itC, ID["R1"], loy_kg=30)
s0 = stok()
_r = tahrir(oC, itC, ID["R2"])
s1 = stok()
check("C1 PUT 200", _r.status_code == 200, getattr(_r, "text", "")[:300])
check("C2 faqat umumiy loy ko'chdi (R1 +30, Qum −30) — Loy sotish 5 kg R1 da qoldi",
      farq(s0, s1) == {"KLEY": 18.0, "AKR": 12.0, "QUM": -30.0}, farq(s0, s1))
_hc = holat(oC)
check("C3 Loy sotish detali retsepti R1, profil R2, qoplama R2",
      _hc.get("detal_retsept") == [ID["R2"], ID["R1"]] and _hc.get("qr") == ID["R2"], _hc)
itC0 = [profil(10, ID["R1"])]
oC0, _r = yarat(itC0, ID["R1"], loy_kg=0)
s2 = stok()
_r = tahrir(oC0, itC0, ID["R2"])
s3 = stok()
check("C4 loy 0 — PUT 200, ombor tegilmadi, qoplama R2", _r.status_code == 200 and farq(s2, s3) == {}
      and holat(oC0).get("qr") == ID["R2"], (getattr(_r, "status_code", None), farq(s2, s3), holat(oC0)))
check("C4b loy 0 — jurnalda almashtirish (loy ko'chirish) qatori YO'Q", not any("almashtirildi" in x for x in jurnal(_r)),
      jurnal(_r))
_r = req(C, "put", f"/api/orders/{oC0}/loy", params={"loy_kg": 10})
s4 = stok()
check("C5 keyin loy 10 kg — YANGI retseptdan (Qum −10)", _r.status_code == 200 and farq(s3, s4) == {"QUM": -10.0},
      (getattr(_r, "status_code", None), farq(s3, s4)))

# ══════════════════════════════════════════════════════════════
section("D. Qisman chiqqan buyurtma — 400, HECH NARSA yozilmaydi")
# ══════════════════════════════════════════════════════════════
itD = [profil(10, ID["R1"])]
oD, _r = yarat(itD, ID["R1"], loy_kg=30)
iD = (detallar(oD) + [None])[0]
_r = req(C, "post", "/api/deliveries", json={"order_id": oD, "items": [{"order_item_id": iD, "quantity": 3}],
                                             "notes": "RA63 yuk D"})
check("D0 3 m topshirildi", _r.status_code == 200, getattr(_r, "text", "")[:200])
s0, h0 = stok(), holat(oD)
_r = tahrir(oD, itD, ID["R2"])
s1, h1 = stok(), holat(oD)
_dt = detail(_r)
check("D1 PUT R2 — 400", _r.status_code == 400, getattr(_r, "text", "")[:300])
check("D2 xabar: retseptni o'zgartirib bo'lmaydi + sabab (topshirilgan) + eski retsept nomi",
      "o'zgartirib bo'lmaydi" in str(_dt.get("message", "")) and "topshirilgan" in " ".join(_dt.get("shortages") or [])
      and "RA63 R1" in " ".join(_dt.get("shortages") or []), _dt)
check("D3 ombor AYNAN", farq(s0, s1) == {}, farq(s0, s1))
check("D4 buyurtma AYNAN (qoplama R1, detal retsepti R1 — rollback)", h0 == h1 and h1.get("qr") == ID["R1"], (h0, h1))
_r = tahrir(oD, itD, ID["R1"])
check("D5 retseptni o'zgartirmasdan tahrir — 200 (avvalgidek)", _r.status_code == 200 and farq(s1, stok()) == {},
      getattr(_r, "text", "")[:200])
itD2 = [profil(10, ID["R1"])]
oD2, _r = yarat(itD2, ID["R1"], loy_kg=30)
iD2 = (detallar(oD2) + [None])[0]
_r = req(C, "post", "/api/returns", json={"order_id": oD2, "order_item_id": iD2, "item_name": itD2[0]["name"],
                                          "quantity": 2, "unit": "metr", "reason": "Ortiqcha", "refund_amount": 0,
                                          "to_stock": True})
check("D6 2 m ortiqcha omborga qaytarildi", _r.status_code == 200, getattr(_r, "text", "")[:200])
s2 = stok()
_r = tahrir(oD2, itD2, ID["R2"])
check("D7 ortiqcha qaytarilgan buyurtma — 400 va ombor AYNAN", _r.status_code == 400 and farq(s2, stok()) == {}
      and holat(oD2).get("qr") == ID["R1"], (getattr(_r, "text", "")[:200], farq(s2, stok())))

# ══════════════════════════════════════════════════════════════
section("E. Haqiqiy loy yozilgan (\"Tayyor\") buyurtma — 400")
# ══════════════════════════════════════════════════════════════
itE = [profil(10, ID["R1"])]
oE, _r = yarat(itE, ID["R1"], loy_kg=30)
_d = SessionLocal()
try:
    _o = _d.get(Order, oE)
    _o.actual_loy_kg = 30
    _d.commit()
finally:
    _d.close()
s0 = stok()
_r = tahrir(oE, itE, ID["R2"])
_dt = detail(_r)
check("E1 actual_loy_kg bor — 400, sabab «Tayyor», ombor AYNAN, qoplama R1",
      _r.status_code == 400 and "Tayyor" in " ".join(_dt.get("shortages") or []) and farq(s0, stok()) == {}
      and holat(oE).get("qr") == ID["R1"], (getattr(_r, "text", "")[:300], farq(s0, stok())))
itE2 = [profil(10, ID["R1"])]
oE2, _r = yarat(itE2, ID["R1"], loy_kg=30)
_r = req(C, "post", f"/api/orders/{oE2}/ready", params={"loy_kg": 30})
check("E2 'Tayyor' 200", _r.status_code == 200, getattr(_r, "text", "")[:200])
s1 = stok()
_r = tahrir(oE2, itE2, ID["R2"])
check("E3 Tayyor buyurtmani tahrir — 400, ombor AYNAN", _r.status_code == 400 and farq(s1, stok()) == {},
      getattr(_r, "text", "")[:200])

# ══════════════════════════════════════════════════════════════
section("F. Qoralama — ombor tegilmaydi, yangi tanlovga ergashadi (avvalgidek)")
# ══════════════════════════════════════════════════════════════
itF = [profil(10, ID["R1"])]
oF, _r = yarat(itF, ID["R1"], loy_kg=30, qoralama=True)
s0 = stok()
check("F0 qoralama yaratildi, ombor tegilmadi", oF and holat(oF).get("status") == "draft", holat(oF))
_r = tahrir(oF, itF, ID["R2"])
check("F1 PUT 200, ombor AYNAN, qoplama R2", _r.status_code == 200 and farq(s0, stok()) == {}
      and holat(oF).get("qr") == ID["R2"], (getattr(_r, "text", "")[:200], farq(s0, stok()), holat(oF)))

# ══════════════════════════════════════════════════════════════
section("G. Eski buyurtma (qoplama_retsept_id NULL)")
# ══════════════════════════════════════════════════════════════
itG = [profil(10, ID["R1"])]
oG, _r = yarat(itG, ID["R1"], loy_kg=30)
_d = SessionLocal()
try:
    _d.get(Order, oG).qoplama_retsept_id = None
    _d.commit()
finally:
    _d.close()
s0 = stok()
_r = tahrir(oG, itG, ID["R2"])
s1 = stok()
check("G1 NULL buyurtma R1 -> R2 — almashtirildi (R1 +30, Qum −30), qoplama R2",
      _r.status_code == 200 and farq(s0, s1) == {"KLEY": 18.0, "AKR": 12.0, "QUM": -30.0} and holat(oG).get("qr") == ID["R2"],
      (getattr(_r, "text", "")[:200], farq(s0, s1), holat(oG)))
# K58-1 shakli: birinchi detal "Loy sotish" (R2), keyin qoplamali profil (R1); eski qoida (NULL) — R2;
# foydalanuvchi TANLOVI (profil) R1 o'zgarmasa — ombor tegilmaydi, kech58 qoidasi AYNAN.
itG2 = [loy_sotish(5, ID["R2"]), profil(10, ID["R1"])]
oG2, _r = yarat(itG2, ID["R1"], loy_kg=30)
_d = SessionLocal()
try:
    _d.get(Order, oG2).qoplama_retsept_id = None
    _d.commit()
finally:
    _d.close()
s2 = stok()
_r = tahrir(oG2, itG2, ID["R1"])
s3 = stok()
check("G2 NULL, K58-1 shakli, tanlov o'zgarmagan — 200, ombor TEGILMADI", _r.status_code == 200 and farq(s2, s3) == {},
      (getattr(_r, "text", "")[:200], farq(s2, s3)))
check("G3 kech58 qoidasi AYNAN: eski qoida retsepti o'zgarmadi — ustun NULL qoladi, almashtirish qatori YO'Q",
      holat(oG2).get("qr") is None and not any("almashtirildi" in x for x in jurnal(_r)), (holat(oG2), jurnal(_r)))

# ══════════════════════════════════════════════════════════════
section("H. Yangi retsept xomashyosi yetmaydi — 409, tasdiq bilan 200")
# ══════════════════════════════════════════════════════════════
itH = [profil(10, ID["R1"])]
oH, _r = yarat(itH, ID["R1"], loy_kg=30)
s0, h0 = stok(), holat(oH)
_r = tahrir(oH, itH, ID["R3"])
_dt = detail(_r)
check("H1 tasdiqsiz — 409 stock_shortage_warning, Kam (loy uchun) aytiladi", _r.status_code == 409
      and _dt.get("type") == "stock_shortage_warning" and "RA63 Kam" in " ".join(_dt.get("shortages") or []),
      getattr(_r, "text", "")[:300])
check("H2 409 da ombor va buyurtma AYNAN (rollback)", farq(s0, stok()) == {} and holat(oH) == h0, (farq(s0, stok()), holat(oH)))
_r = tahrir(oH, itH, ID["R3"], tasdiq=True)
s1 = stok()
check("H3 tasdiq bilan — 200, R1 +30, Kam −30 (qoldiq manfiy, 19-band), qoplama R3",
      _r.status_code == 200 and farq(s0, s1) == {"KLEY": 18.0, "AKR": 12.0, "KAM": -30.0} and taxminan(s1["KAM"], -25)
      and holat(oH).get("qr") == ID["R3"], (getattr(_r, "text", "")[:200], farq(s0, s1), s1["KAM"]))

itH4 = [profil(10, ID["R1"])]
oH4, _r = yarat(itH4, ID["R1"], loy_kg=30)
s2, h2 = stok(), holat(oH4)


def _loy4_soni():
    d = SessionLocal()
    try:
        return d.query(Inventory).filter(Inventory.item_name == "Tayyor loy (RA63 R4)").count()
    finally:
        d.close()


_r = tahrir(oH4, itH4, ID["R4"])
check("H4 tayyor loy pozitsiyasi yo'q retseptga 409 — pozitsiya ham, tahrir ham YOZILMAYDI (tekshiruv commit qilmaydi)",
      _r.status_code == 409 and _loy4_soni() == 0 and holat(oH4) == h2 and farq(s2, stok()) == {},
      (getattr(_r, "status_code", None), _loy4_soni(), holat(oH4), farq(s2, stok())))

# ══════════════════════════════════════════════════════════════
section("I. Yangi retseptning tayyor loy zaxirasi avval ishlatiladi (yaratishdagidek)")
# ══════════════════════════════════════════════════════════════
itI = [profil(10, ID["R1"])]
oI, _r = yarat(itI, ID["R1"], loy_kg=30)
_d = SessionLocal()
try:
    _d.get(Inventory, ID["LOY2"]).stock_quantity = 10.0
    _d.commit()
finally:
    _d.close()
s0 = stok()
_r = tahrir(oI, itI, ID["R2"])
s1 = stok()
check("I1 Tayyor loy (R2) −10, Qum −20, R1 +30", _r.status_code == 200
      and farq(s0, s1) == {"KLEY": 18.0, "AKR": 12.0, "LOY2": -10.0, "QUM": -20.0}, farq(s0, s1))

# ══════════════════════════════════════════════════════════════
section("J. Almashtirishdan keyin brak loyi YANGI retseptdan (43-band yagona manba)")
# ══════════════════════════════════════════════════════════════
itJ = [profil(10, ID["R1"])]
oJ, _r = yarat(itJ, ID["R1"], loy_kg=30)
_r = tahrir(oJ, itJ, ID["R2"])
iJ = (detallar(oJ) + [None])[0]
s0 = stok()
_r = req(C, "post", "/api/returns", json={"order_id": oJ, "order_item_id": iJ, "item_name": itJ[0]["name"], "quantity": 1,
                                          "unit": "metr", "reason": "Brak", "refund_amount": 0, "to_stock": False,
                                          "coating_applied": True})
s1 = stok()
_f = farq(s0, s1)
check("J1 brak 200, loy Qum (R2) dan yechildi, Kley / Akril tegilmadi",
      _r.status_code == 200 and _f.get("QUM", 0) < 0 and "KLEY" not in _f and "AKR" not in _f,
      (getattr(_r, "text", "")[:200], _f))

# ══════════════════════════════════════════════════════════════
section("K. Foyda (\"Tayyor\"dan keyin) qoplama qatori YANGI retsept narxida")
# ══════════════════════════════════════════════════════════════
itK = [profil(10, ID["R1"])]
oK, _r = yarat(itK, ID["R1"], loy_kg=30)
_r = tahrir(oK, itK, ID["R2"])
_r2 = req(C, "post", f"/api/orders/{oK}/ready", params={"loy_kg": 30})
check("K0 almashtirish va 'Tayyor' 200", _r.status_code == 200 and _r2.status_code == 200,
      (getattr(_r, "text", "")[:150], getattr(_r2, "text", "")[:150]))
_d = SessionLocal()
try:
    _p = services.calculate_order_profit(_d, oK, company_id=1)
except Exception as e:                     # noqa: BLE001
    _p = {"xato": str(e)}
finally:
    _d.close()
_qop = [x for x in (_p.get("breakdown") or []) if "Qoplama" in str(x.get("nomi", ""))] if isinstance(_p, dict) else []
_qs = sum(float(x.get("summa") or 0) for x in _qop)
check("K1 qoplama = 30 kg × Qum 20 000 = 600 000 (R1 narxida 156 000 bo'lardi)", taxminan(_qs, 600_000, 1), _qop)

# ══════════════════════════════════════════════════════════════
section("N. Nomuvofiq buyurtma (loy R1 da, detallar R2 — zip 58–62 davridagi tahrir izi)")
# ══════════════════════════════════════════════════════════════
itN = [profil(10, ID["R1"])]
oN, _r = yarat(itN, ID["R1"], loy_kg=30)
_d = SessionLocal()
try:
    for _it in _d.query(OrderItem).filter(OrderItem.order_id == oN).all():
        _it.recipe_id = ID["R2"]
    _d.commit()
finally:
    _d.close()
_hn0 = holat(oN)
check("N0 holat: qoplama R1, detal R2", _hn0.get("qr") == ID["R1"] and _hn0.get("detal_retsept") == [ID["R2"]], _hn0)
s0 = stok()
_hv0 = len(harakatlar(oN))
_r = tahrir(oN, itN, ID["R1"])
s1 = stok()
check("N1 UI R1 ni ko'rsatadi, R1 bilan saqlansa — 200, ombor TEGILMAYDI, yangi harakat YO'Q",
      _r.status_code == 200 and farq(s0, s1) == {} and len(harakatlar(oN)) == _hv0, (getattr(_r, "text", "")[:200], farq(s0, s1)))
check("N2 almashtirish qatori YO'Q; detal retsepti R1 ga to'g'rilandi, qoplama R1",
      not any("almashtirildi" in x for x in jurnal(_r)) and holat(oN).get("detal_retsept") == [ID["R1"]]
      and holat(oN).get("qr") == ID["R1"], (jurnal(_r), holat(oN)))
_r = tahrir(oN, itN, ID["R2"])
check("N3 keyin R2 — haqiqiy almashtirish (R1 +30, Qum −30)", _r.status_code == 200
      and farq(s1, stok()) == {"KLEY": 18.0, "AKR": 12.0, "QUM": -30.0}, farq(s1, stok()))

# ══════════════════════════════════════════════════════════════
section("L. UI: tahrir oynasi retseptni qoplama_retsept_id dan oladi (shablondagi HAQIQIY blok, node)")
# ══════════════════════════════════════════════════════════════
_html = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_b0 = _html.find("const recipeSel = document.getElementById('recipe_id');")
_b1 = _html.find("// \"1 m³ asosiy narxi\"", _b0) if _b0 >= 0 else -1
_blok = _html[_b0:_b1] if (_b0 >= 0 and _b1 > _b0) else ""
check("L0 shablonda tahrir retsept bloki topildi", bool(_blok), (_b0, _b1))
_jsk = r"""
function yurgiz(order, itemsToUse, isDup, opts) {
  const recipeSel = { value: '', options: opts.map(v => ({ value: String(v) })) };
  const document = { getElementById: (x) => (x === 'recipe_id' ? recipeSel : null) };
  __BLOK__
  return String(recipeSel.value);
}
const it = [{ recipe_id: 2, category: 'profil' }, { recipe_id: 1, category: 'loy_sotish' }];
const n = {
  l1: yurgiz({ qoplama_retsept_id: 1 }, [{ recipe_id: 2, category: 'profil' }], false, ['', 1, 2]),
  l2: yurgiz({ qoplama_retsept_id: 1 }, [{ recipe_id: 2, category: 'profil' }], true, ['', 1, 2]),
  l3: yurgiz({ qoplama_retsept_id: 9 }, [{ recipe_id: 2, category: 'profil' }], false, ['', 1, 2]),
  l4: yurgiz({ qoplama_retsept_id: null }, it, false, ['', 1, 2]),
};
console.log(JSON.stringify(n));
"""
_nat, _xato = {}, ""
if _blok:
    _blok2 = _blok.replace("const recipeSel = document.getElementById('recipe_id');", "", 1)
    _tf = os.path.join(tempfile.gettempdir(), "retsept_almashtirish_ui.js")
    with open(_tf, "w", encoding="utf-8") as _f:
        _f.write(_jsk.replace("__BLOK__", _blok2))
    try:
        _p = subprocess.run(["node", _tf], capture_output=True, text=True, timeout=60)
        _nat = json.loads((_p.stdout or "").strip().splitlines()[-1]) if _p.returncode == 0 and _p.stdout.strip() else {}
        _xato = (_p.stderr or "")[:300]
    except Exception as e:                 # noqa: BLE001
        _xato = f"{type(e).__name__}: {e}"
check("L1 tahrir: qoplama_retsept_id (1) — detallar R2 bo'lsa ham 1 tanlanadi", _nat.get("l1") == "1", (_nat, _xato))
check("L2 nusxa (duplicate): avvalgidek detallardan (2)", _nat.get("l2") == "2", (_nat, _xato))
check("L3 qoplama_retsept_id ro'yxatda yo'q — detallardan (2)", _nat.get("l3") == "2", (_nat, _xato))
check("L4 qoplama_retsept_id NULL — detallardan, Loy sotish emas (2)", _nat.get("l4") == "2", (_nat, _xato))

# ══════════════════════════════════════════════════════════════
section("S. Statik: tartib va commit=False (qulf ostida bitta tranzaksiya)")
# ══════════════════════════════════════════════════════════════
_uf = _manba(crud.update_order_full)
check("S1 tanlov (oldin) va loy rejasi — detallar o'zgarishidan OLDIN",
      tartibda(_uf, "_qr53_tanlov_oldin = ", "_loy53 = ", "# 4) Detallarni yangilaymiz"), "")
check("S2 almashtirish bloki: rad (400) -> 409 tekshiruvi -> qaytarish -> yechish -> adjust_inventory_diff",
      tartibda(_uf, "_qr53_keyin = services.buyurtma_qoplama_retseptini_tanla", "buyurtmadan_qisman_chiqqan(order)",
               "db.rollback()", "check_loy_ingredients_for_order(", "db.rollback()", "services.return_loy_ingredients(",
               "services.deduct_loy_ingredients(", "services.adjust_inventory_diff("), "")
_blk = _uf[_uf.find("_qr53_keyin = services"):_uf.find("services.adjust_inventory_diff(")] if "_qr53_keyin = services" in _uf else ""
check("S3 almashtirishda return / deduct / tekshiruv — commit=False (3 ta)", _blk.count("commit=False") == 3, _blk.count("commit=False"))
_sig = {f: list(inspect.signature(getattr(services, f)).parameters) for f in
        ("get_or_create_loy_stock", "take_loy_from_stock", "deduct_loy_ingredients", "return_loy_ingredients",
         "check_loy_ingredients_for_order") if hasattr(services, f)}
check("S4 services loy yordamchilarida commit parametri (5 ta)", all("commit" in v for v in _sig.values()) and len(_sig) == 5, _sig)
_tk = _manba(services.take_loy_from_stock)
check("S5 take_loy_from_stock commit ni get_or_create_loy_stock ga uzatadi",
      "get_or_create_loy_stock(db, recipe, commit=commit)" in _tk, "")
_dl = _manba(services.deduct_loy_ingredients)
check("S6 deduct_loy_ingredients commit ni take_loy_from_stock ga uzatadi", "commit=commit)" in _dl, "")
_ifc = {f: ("if commit:\n" in _manba(getattr(services, f, None)) and "db.flush()" in _manba(getattr(services, f, None)))
        for f in ("get_or_create_loy_stock", "take_loy_from_stock", "deduct_loy_ingredients", "return_loy_ingredients")}
check("S7 4 ta yordamchida 'if commit: ... else: db.flush()' bloki", all(_ifc.values()), _ifc)
_ck = _manba(getattr(services, "check_loy_ingredients_for_order", None))
check("S8 check_loy_ingredients_for_order commit ni get_or_create_loy_stock ga uzatadi",
      "get_or_create_loy_stock(db, recipe, commit=commit)" in _ck, "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
