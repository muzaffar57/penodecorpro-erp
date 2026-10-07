#!/usr/bin/env python3
"""test_donalik_hajm_snapshot.py — kech96 (2026-09-27), 126-band.

NIMA UCHUN KERAK
----------------
Donalik detali "eski usul"da (o'lchamsiz — hajm narxdan): 1 dona hajmi = (qulflangan narx `unit_price_for_volume`
yoki narx) ÷ (detal "1 m³ narxi" → buyurtma "Asosiy narx"i → penoplast 1 m³ tannarxi). Yaratishda yechish va
buyurtmani o'chirish bu qoidani OrderItem obyekti bilan qo'llaydi. Tahrir / detalni o'chirish / yetishlik
tekshiruvi esa dict snapshot (`services._FakeItem`) bilan ishlaydi — unda buyurtma asosiy narxi YO'Q edi, detal
tahriri va detalni o'chirish snapshotlarida qulflangan narx va o'z "1 m³ narxi" ham yo'q edi. O'LCHANGAN
(kech96 `work/probe126.py`, asl = zip 89, SQLite = PG; penoplast 1 blok = 1 m³, 500 000; Donalik 10 000 × 34 —
1 dona = 0.01 m³):
  • detal o'z "1 m³ narxi" 1 000 000: `PUT /api/order-items` 34 → 40 — 0.12 yechildi (kerak 0.06),
    `DELETE /api/order-items` — 0.80 qaytdi (kerak 0.40): omborda +0.34 m³ "yo'qdan" paydo bo'ldi;
  • buyurtma asosiy narxi 1 000 000 — xuddi shunday; qulflangan narx (sotuv 12 000) — 0.144 / 0.96;
  • asosiy narx bilan TO'LIQ tahrir (UI yo'li) 34 → 40 — 0.12 yechildi (buyurtma o'chirilgach −0.06);
  • yaratishda yetishlik tekshiruvi (asosiy narx): qoldiq 0.5 blok, kerak 0.34 — "kerak 0.7 blok" (soxta 409).

BO'LIMLAR
---------
  A detal tahriri + detalni o'chirish (o'z "1 m³ narxi", asosiy narx, qulflangan narx, zaxira — tannarx);
  B to'liq tahrir + buyurtmani o'chirish (shu holatlar; asosiy narxni o'zgartirish);
  C yetishlik tekshiruvi (yaratish); D yangi usul (o'lchamli) Donalik — o'zgarmagan (nazorat);
  X 5xx yo'q; S statik.

ISHLATISH
---------
    python3 tools/test_donalik_hajm_snapshot.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_donalik_hajm_snapshot.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "donalik_hajm_snapshot_test"
_T = tempfile.mkdtemp(prefix="dhs_")
_DB = os.path.join(_T, "donalik_hajm_snapshot_test.db")

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

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
import services                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, OrderItem   # noqa: E402
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
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    HOLATLAR.append((metod.upper() + " " + url.split("?")[0], r.status_code))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def teng(a, b, tol=1e-6):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:                      # noqa: BLE001
        return False


s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "dhs_admin", "Parol123!", UserRole.ADMIN, "DHS Admin", company_id=1)
PRJ = [Project(company_id=1, client_name=f"DHS{i}", project_name=f"DHS L{i}", total_budget=0, total_paid=0)
       for i in range(30)]
PENO = Inventory(company_id=1, item_name="DHS Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
s.add_all(PRJ + [PENO])
s.commit()
PRJ_ID = [p.id for p in PRJ]
PID = PENO.id
s.close()
_loy = iter(range(len(PRJ_ID)))

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = C.post("/login", data={"username": "dhs_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _lr.status_code in (200, 302, 303), _lr.status_code)


def qoldiq():
    s = SessionLocal()
    try:
        return float(s.get(Inventory, PID).stock_quantity)
    finally:
        s.close()


def qoldiq_qoy(v):
    s = SessionLocal()
    try:
        s.get(Inventory, PID).stock_quantity = v
        s.commit()
    finally:
        s.close()


def dona(narx, miqdor, **kw):
    d = {"name": "DHS Donalik", "category": "dona", "quantity": miqdor, "unit_price": narx, "is_coated": False,
         "penoplast_id": PID}
    d.update(kw)
    return d


def yarat(item, **kw):
    tana = {"project_id": PRJ_ID[next(_loy)], "order_type": "product", "items": [item]}
    tana.update(kw)
    r = req(C, "post", "/api/orders", json=tana)
    if r.status_code != 200:
        return None, None, r
    oid = js(r).get("id")
    s = SessionLocal()
    iid = s.query(OrderItem.id).filter(OrderItem.order_id == oid).scalar()
    s.close()
    return oid, iid, r


HOLLAR = [
    ("o'z \"1 m³ narxi\" 1 000 000", dona(10000, 34, price_per_m3=1000000), {}, 0.01),
    ("buyurtma asosiy narxi 1 000 000", dona(10000, 34), {"base_price": 1000000}, 0.01),
    ("qulflangan narx 10 000 (sotuv 12 000), o'z narx 1 000 000",
     dona(12000, 34, price_per_m3=1000000, unit_price_for_volume=10000), {}, 0.01),
    ("qulflangan 10 000 + asosiy narx 1 000 000", dona(12000, 34, unit_price_for_volume=10000), {"base_price": 1000000}, 0.01),
    ("zaxira — penoplast tannarxi 500 000", dona(10000, 34), {}, 0.02),
    ("o'z narx 2 000 000 (asosiy 1 000 000 dan ustun)", dona(10000, 34, price_per_m3=2000000), {"base_price": 1000000}, 0.005),
]

# ══════════════════════════════════════════════════════════════
section("A. Detal tahriri (PUT /api/order-items) va detalni o'chirish (DELETE /api/order-items)")
# ══════════════════════════════════════════════════════════════
for i, (nom, item, kw, birlik) in enumerate(HOLLAR, 1):
    q0 = qoldiq()
    oid, iid, r = yarat(item, **kw)
    q1 = qoldiq()
    check(f"A{i}a {nom}: yaratish — {34 * birlik:.4f} m³ yechildi", oid and teng(q0 - q1, 34 * birlik), (r.status_code, q0 - q1))
    r = req(C, "put", f"/api/order-items/{iid}", json={"quantity": 40})
    q2 = qoldiq()
    check(f"A{i}b {nom}: detal 34 → 40 — AYNAN {6 * birlik:.4f} m³ yechildi", r.status_code == 200 and teng(q1 - q2, 6 * birlik),
          (r.status_code, round(q1 - q2, 6)))
    r = req(C, "put", f"/api/order-items/{iid}", json={"quantity": 30})
    q3 = qoldiq()
    check(f"A{i}c {nom}: detal 40 → 30 — AYNAN {10 * birlik:.4f} m³ qaytdi", r.status_code == 200 and teng(q3 - q2, 10 * birlik),
          (r.status_code, round(q3 - q2, 6)))
    r = req(C, "delete", f"/api/order-items/{iid}")
    q4 = qoldiq()
    check(f"A{i}d {nom}: detalni o'chirish — AYNAN {30 * birlik:.4f} m³ qaytdi, ombor asliga",
          r.status_code == 200 and teng(q4 - q3, 30 * birlik) and teng(q4, q0), (r.status_code, round(q4 - q3, 6), round(q4 - q0, 6)))

# ══════════════════════════════════════════════════════════════
section("B. To'liq tahrir (PUT /api/orders) va buyurtmani o'chirish")
# ══════════════════════════════════════════════════════════════


def toliq(oid, item, **kw):
    o = js(req(C, "get", f"/api/orders/{oid}"))
    tana = {"project_id": o.get("project_id"), "order_type": o.get("order_type") or "product", "items": [item]}
    tana.update(kw)
    return req(C, "put", f"/api/orders/{oid}", json=tana)


for i, (nom, item, kw, birlik) in enumerate(HOLLAR, 1):
    q0 = qoldiq()
    oid, iid, r = yarat(item, **kw)
    q1 = qoldiq()
    yangi = dict(item)
    yangi["quantity"] = 40
    r = toliq(oid, yangi, **kw)
    q2 = qoldiq()
    check(f"B{i}a {nom}: to'liq tahrir 34 → 40 — AYNAN {6 * birlik:.4f} m³", r.status_code == 200 and teng(q1 - q2, 6 * birlik),
          (r.status_code, round(q1 - q2, 6), r.text[:150]))
    r = toliq(oid, yangi, **kw)
    q3 = qoldiq()
    check(f"B{i}b {nom}: o'zgarishsiz qayta saqlash — ombor o'zgarmaydi", r.status_code == 200 and teng(q3, q2),
          (r.status_code, round(q3 - q2, 6)))
    r = req(C, "delete", f"/api/orders/{oid}")
    q4 = qoldiq()
    check(f"B{i}c {nom}: buyurtmani o'chirish — ombor asliga (jami yechilgan = qaytgan)", r.status_code == 200 and teng(q4, q0),
          (r.status_code, round(q4 - q0, 6)))
# asosiy narx o'zgartirilsa (o'z narxi yo'q) — yangi asosiy narx bilan (buyurtmani o'chirish shu narx bilan qaytaradi)
q0 = qoldiq()
oid, iid, r = yarat(dona(10000, 34), base_price=1000000)
q1 = qoldiq()
r = toliq(oid, dona(10000, 34), base_price=2000000)
q2 = qoldiq()
check("B7 asosiy narx 1 000 000 → 2 000 000 (o'z narxsiz Donalik): hajm 0.34 → 0.17, 0.17 qaytdi",
      r.status_code == 200 and teng(q2 - q1, 0.17), (r.status_code, round(q2 - q1, 6)))
r = req(C, "delete", f"/api/orders/{oid}")
check("B8 keyin buyurtmani o'chirish — ombor asliga", r.status_code == 200 and teng(qoldiq(), q0), round(qoldiq() - q0, 6))

# ══════════════════════════════════════════════════════════════
section("C. Yaratishda yetishlik tekshiruvi")
# ══════════════════════════════════════════════════════════════
_asl = qoldiq()
qoldiq_qoy(0.5)
oid, iid, r = yarat(dona(10000, 34), base_price=1000000)
check("C1 asosiy narx 1 000 000, qoldiq 0.5 blok, kerak 0.34 → 200 (asl: 409 \"kerak 0.7 blok\")",
      r.status_code == 200, (r.status_code, r.text[:200]))
qoldiq_qoy(0.3)
oid2, iid2, r = yarat(dona(10000, 34), base_price=1000000)
check("C2 qoldiq 0.3 blok, kerak 0.34 → 409 ogohlantirish (haqiqiy yetishmovchilik)",
      r.status_code == 409 and "0.3 blok" in r.text, (r.status_code, r.text[:200]))
qoldiq_qoy(0.5)
oid3, iid3, r = yarat(dona(10000, 34, price_per_m3=1000000))
check("C3 o'z \"1 m³ narxi\" bilan (nazorat) → 200", r.status_code == 200, (r.status_code, r.text[:200]))
qoldiq_qoy(_asl)

# ══════════════════════════════════════════════════════════════
section("D. Yangi usul (o'lchamli Donalik) — o'zgarmagan (nazorat)")
# ══════════════════════════════════════════════════════════════
q0 = qoldiq()
oid, iid, r = yarat(dona(10000, 6, width=10, thickness=10, length=2, price_per_m3=910000), base_price=1000000)
q1 = qoldiq()
check("D1 Eni 10 × Qalinlik 10 × uzunlik ekv. 2 → 0.01 m³ yechildi", oid and teng(q0 - q1, 0.01), (r.status_code, q0 - q1))
r = req(C, "put", f"/api/order-items/{iid}", json={"quantity": 9})
check("D2 detal miqdori o'zgardi (o'lcham o'zgarmas) — ombor o'zgarmaydi", r.status_code == 200 and teng(qoldiq(), q1),
      (r.status_code, round(qoldiq() - q1, 6)))
r = req(C, "delete", f"/api/order-items/{iid}")
check("D3 detalni o'chirish — 0.01 qaytdi", r.status_code == 200 and teng(qoldiq(), q0), round(qoldiq() - q0, 6))

# ══════════════════════════════════════════════════════════════
section("E. API 3 xonali qiymatlar — detal tahriri bazaga 2 xona yozadi, o'zgarishsiz tahrir omborga tegmaydi")
# ══════════════════════════════════════════════════════════════
# Snapshot endi qulflangan narx va "1 m³ narxi" ni o'qiydi — yangi holat bazaga YOZILADIGAN (2 xona) qiymat bilan bo'lmasa,
# eski holat (bazada 2 xona) bilan farq chiqadi: 3 997.125 ↔ 3 997.13, 10.125 ↔ 10.13 (kichik "1 m³ narxi" — farq ko'rinadi).
_de = dona(3997.13, 34, price_per_m3=10.125, unit_price_for_volume=3997.125)


def detal_bazada(iid):
    s = SessionLocal()
    try:
        i = s.get(OrderItem, iid) if iid else None
        if i is None:
            return (None, None)
        return (None if i.unit_price_for_volume is None else float(i.unit_price_for_volume),
                None if i.price_per_m3 is None else float(i.price_per_m3))
    finally:
        s.close()


_e_asl = qoldiq()
qoldiq_qoy(1e7)          # kichik "1 m³ narxi" — hajm katta (34 × 3 997.13 / 10.13 ≈ 13 416 m³)
oid, iid, r = yarat(_de)
check("E1 yaratish (qulflangan 3 997.125, \"1 m³ narxi\" 10.125) → bazada 3 997.13 / 10.13", oid and detal_bazada(iid) == (3997.13, 10.13),
      (r.status_code, detal_bazada(iid) if oid else None))
q1 = qoldiq()
r = req(C, "put", f"/api/order-items/{iid}", json={"unit_price": 3997.13, "unit_price_for_volume": 3997.125, "price_per_m3": 10.13})
check("E2 o'zgarishsiz detal tahriri (qulflangan narx 3 xona bilan) → ombor o'zgarmaydi, bazada 3 997.13",
      r.status_code == 200 and teng(qoldiq(), q1) and detal_bazada(iid)[0] == 3997.13, (r.status_code, round(qoldiq() - q1, 6), detal_bazada(iid)))
r = req(C, "put", f"/api/order-items/{iid}", json={"unit_price": 3997.13, "unit_price_for_volume": 3997.13, "price_per_m3": 10.125})
check("E3 o'zgarishsiz detal tahriri (\"1 m³ narxi\" 3 xona bilan) → ombor o'zgarmaydi, bazada 10.13",
      r.status_code == 200 and teng(qoldiq(), q1) and detal_bazada(iid)[1] == 10.13, (r.status_code, round(qoldiq() - q1, 6), detal_bazada(iid)))
r = req(C, "delete", f"/api/orders/{oid}")
check("E4 buyurtmani o'chirish — yechilgan AYNAN qaytdi (qoldiq 10 000 000)", r.status_code == 200 and teng(qoldiq(), 1e7),
      (r.status_code, round(qoldiq() - 1e7, 6)))
qoldiq_qoy(_e_asl)

# ══════════════════════════════════════════════════════════════
section("X. 5xx yo'q")
# ══════════════════════════════════════════════════════════════
_5xx = [h for h in HOLATLAR if h[1] >= 500]
check("X hech bir so'rov 5xx qaytarmadi", not _5xx, _5xx[:5])

# ══════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════


def manba(mod, nom):
    try:
        return inspect.getsource(getattr(mod, nom))
    except Exception:                      # noqa: BLE001
        return ""


_fi = manba(services, "_FakeItem")
check("S1 `_FakeItem` buyurtma asosiy narxini oladi (`order_base_price` → `order.base_price`)",
      "d.get('order_base_price')" in _fi and "self.order =" in _fi)
_uoi = manba(crud, "update_order_item")
check("S2 detal tahriri snapshotlari: qulflangan narx, o'z \"1 m³ narxi\", asosiy narx (2 tadan)",
      _uoi.count('"unit_price_for_volume": float(db_item.unit_price_for_volume)') == 2
      and _uoi.count('"price_per_m3": float(db_item.price_per_m3)') == 2 and _uoi.count('"order_base_price": _bp126') == 2)
_doi = manba(crud, "delete_order_item")
check("S3 detalni o'chirish snapshoti: qulflangan narx, o'z narx, asosiy narx",
      '"unit_price_for_volume": float(db_item.unit_price_for_volume)' in _doi and '"price_per_m3": float(db_item.price_per_m3)' in _doi
      and '"order_base_price":' in _doi)
_uof = manba(crud, "update_order_full")
check("S4 to'liq tahrir: eski (tahrirdan oldingi) va yangi asosiy narx snapshotda",
      '"order_base_price": float(order.base_price) if order.base_price is not None else None' in _uof
      and "\"order_base_price\": (float(getattr(order_data, 'base_price', None))" in _uof)
_cio = manba(services, "check_inventory_for_order")
check("S5 yetishlik tekshiruvi asosiy narxni sxema detallariga beradi",
      "_sxema_detal_dict(it, _tek_bp)" in _cio and "hasattr(it, 'order')" in _cio)

print()
print("=" * 60)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
