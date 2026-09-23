#!/usr/bin/env python3
"""
test_detal_poyga.py — 5-bo'lim 14-band darvozasi (kech41, 2026-09-23):
detal tahriri / o'chirish / "Tayyor" va yetkazish orasidagi poygalar.

NIMA UCHUN KERAK (asl kod `dd457e1` da HAQIQIY PostgreSQL 16 da O'LCHANGAN —
`work/probe41.py`, har holat 3 / 3 urinishda takrorlandi)
--------------------------------------------------------------------
  R1  detal 10 → 6 ga kamaytirilayotganda (tasdiqlanmagan) 8 topshirilsa —
      ikkalasi saqlanardi: detal 6, topshirilgan 8.
  R1b teskari tartib (avval yuk, keyin tahrir) — xuddi shunday.
  R2a detal o'chirilayotganda undan 3 topshirilsa — detal o'chib, yuk xati
      qolardi; buyurtma summasi 0, penoplast TO'LIQ omborga "qaytardi".
  R2b teskari tartib — o'chirish FK xatosi (23503) bilan 500.
  R3  "Tayyor" bosilayotganda boshqa xodim 5 / 10 topshirsa — buyurtma READY,
      qolgan 5 topshirilmagan, summa yakunlanmagan (1 000 000 qolardi).
  R4  "Tayyor" ikki joydan bir vaqtda — ikkalasi ham "yakunlandi".
Ketma-ket (poygasiz) holatda hammasi to'g'ri rad etilardi — sabab QULF yo'qligi:
`update_order_item`, `delete_order_item`, `update_order_full` va
`services.complete_order` "topshirilgan" miqdorni qulfsiz o'qirdi.
Qo'shimcha (tuzatish paytida O'LCHANGAN): `services.adjust_inventory_diff`
va `_auto_release_mrp_reservations` (`log_activity` orqali) O'ZI `commit`
qilib qulfni muddatidan oldin bo'shatardi — qulf qo'yilgach ham R2a 500 berardi.

TUZATISH (kech41): to'rt funksiyada flush → qulf (101, buyurtma) → expire_all →
qulf ostida QAYTA o'qish; `complete_order` da holat DARHOL READY va oraliq
`commit` dan keyin qulf QAYTA olinib qisman / to'liq qarori yangi holatdan;
`adjust_inventory_diff(commit=False)`; audit yozuvi `db.add(ActivityLog(...))`.

REJIMLAR: odatiy SQLite (statik + ketma-ket xulq); `PG_URL` berilsa — YANGI PG
bazasi, qo'shimcha ravishda PARALLEL problar (P bo'limi).
    python3 tools/test_detal_poyga.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_detal_poyga.py
"""
import os
import sys
import inspect
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "detal_poyga_test"
_DB = os.path.join(tempfile.gettempdir(), "detal_poyga_test.db")

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
    import crud, auth, schemas, services           # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Delivery, DeliveryItem, Inventory,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


def tartibda(src, *qismlar):
    """Qismlar matnda AYNAN shu tartibda (`find`, topilmasa False — qulamaydi)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


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


def manba(obj, nom):
    f = getattr(obj, nom, None)
    try:
        return inspect.getsource(f) if f else ""
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "DP_admin", "Parol123!", UserRole.ADMIN, "DP Admin", company_id=1)
PRJ = Project(company_id=1, client_name="DP Mijoz", project_name="DP loyiha",
              total_budget=0, total_paid=0)
_db.add(PRJ)
_db.commit()
PRJ_ID = PRJ.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "DP_admin", "password": "Parol123!"},
          follow_redirects=False)
if _lr.status_code != 302:
    print(f"LOGIN BO'LMADI: {_lr.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_rp = req(C, "post", "/api/inventory", json={"item_name": "DP PENO 14P", "unit": "blok",
                                             "stock_quantity": 1000, "min_stock": 0,
                                             "is_penoplast": True, "volume_per_unit": 1})
PENO = (js(_rp) or {}).get("id")
check("fikstura: penoplast yaratildi (200)", _rp.status_code == 200 and bool(PENO),
      f"{_rp.status_code} {getattr(_rp, 'text', '')[:160]}")

_n = [0]


def yangi(miqdor=10):
    """YANGI buyurtma (panel, penoplastli, jarayonda) → (order_id, detal_id)."""
    _n[0] += 1
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            o = crud.create_order(s, schemas.OrderCreate(
                project_id=PRJ_ID, order_type="product",
                items=[schemas.OrderItemCreate(
                    name=f"DP_D{_n[0]}", category="panel", width=100, thickness=10,
                    length=100, quantity=miqdor, unit_price=100_000, is_coated=False,
                    penoplast_id=PENO)]), performed_by="DP")
        it = s.query(OrderItem).filter(OrderItem.order_id == o.id).first()
        return o.id, it.id
    finally:
        s.close()


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        its = s.query(OrderItem).filter(OrderItem.order_id == oid).all()
        det = {}
        for i in its:
            berilgan = sum(float(x.quantity) for x in s.query(DeliveryItem).filter(
                DeliveryItem.order_item_id == i.id).all())
            det[i.id] = (round(float(i.quantity), 3), round(berilgan, 3))
        pen = s.query(Inventory).filter(Inventory.id == PENO).first()
        return {"status": o.status.value, "total": round(float(o.total_amount or 0), 2),
                "detal": det, "yuk": s.query(Delivery).filter(Delivery.order_id == oid).count(),
                "peno": round(float(pen.stock_quantity), 4) if pen else None}
    finally:
        s.close()


def dlv_api(oid, iid, q, izoh):
    return req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": q}], "notes": izoh})


def yuk(oid, iid, q, izoh):
    return lambda s: crud.create_delivery(s, schemas.DeliveryCreate(
        order_id=oid, items=[schemas.DeliveryItemCreate(order_item_id=iid, quantity=q)],
        notes=izoh), delivered_by="DP", company_id=1)


# ══════════════════════════════════════════════════════════════
# 1. STATIK — qulf + qayta o'qish tartibi
# ══════════════════════════════════════════════════════════════
def bolim_statik():
    section("1. Statik: qulf (101, buyurtma) → expire_all → qulf ostida qayta o'qish")
    u = manba(crud, "update_order_item")
    check("update_order_item: flush → qulf → expire_all → qayta o'qish → 'topshirilgan' tekshiruvi",
          tartibda(u, "db_item = _q.first()", "db.flush()", "_pul_qulfi(db, 101, db_item.order_id)",
                   "db.expire_all()", "db_item = _q.first()", "delivered = db_item.delivered_qty"))
    d = manba(crud, "delete_order_item")
    check("delete_order_item: flush → qulf → expire_all → qayta o'qish → 'topshirilgan' tekshiruvi",
          tartibda(d, "db_item = _iq.first()", "db.flush()", "_pul_qulfi(db, 101, db_item.order_id)",
                   "db.expire_all()", "db_item = _iq.first()", "if db_item.delivered_qty > 0.001"))
    f = manba(crud, "update_order_full")
    check("update_order_full: qulf → expire_all → korxona filtrli qayta o'qish → READY tekshiruvi → detallar",
          tartibda(f, "db.flush()", "_pul_qulfi(db, 101, order.id)", "db.expire_all()",
                   "Order.company_id == _cid_q", "if order.status == OrderStatus.READY",
                   "delivered = oi.delivered_qty"))
    c = manba(services, "complete_order")
    check("complete_order: qulf → expire_all → qayta o'qish → READY tekshiruvi (boshida)",
          tartibda(c, "_pul_qulfi(db, 101, order.id)", "db.expire_all()",
                   "Order.company_id == _cid_q", "if order.status == OrderStatus.READY"))
    check("complete_order: holat DARHOL READY — loy hisobidan (oraliq commit lardan) OLDIN",
          tartibda(c, "=== HAMMA NARSA TAYYOR", "order.status = OrderStatus.READY", "=== LOY HISOB-KITOBI"))
    check("complete_order: oraliq commit dan keyin qulf QAYTA + qisman/to'liq qarori QAYTA hisoblanadi",
          tartibda(c, "=== LOY HISOB-KITOBI", "db.commit()", "_pul_qulfi(db, 101, order.id)",
                   "db.expire_all()", "is_partial_completion = bool(order.deliveries)",
                   "=== QISMAN TOPSHIRILGAN"))
    check("complete_order: qulf AYNAN 2 marta olinadi",
          c.count("_pul_qulfi(db, 101, order.id)") == 2, str(c.count("_pul_qulfi(db, 101, order.id)")))
    a = manba(services, "adjust_inventory_diff")
    check("adjust_inventory_diff: `commit` parametri, False bo'lsa faqat flush",
          "commit: bool = True" in a and tartibda(a, "if commit:", "db.commit()", "else:", "db.flush()"))
    check("update_order_item / delete_order_item: adjust_inventory_diff(commit=False)",
          "company_id=db_item.company_id, commit=False)" in u
          and "company_id=db_item.company_id, commit=False)" in d)
    r = manba(crud, "_auto_release_mrp_reservations")
    check("_auto_release_mrp_reservations: log_activity / commit YO'Q, audit db.add bilan",
          bool(r) and "log_activity(" not in r and "db.commit(" not in r and "db.add(" in r
          and "auto_release_reservation" in r)


# ══════════════════════════════════════════════════════════════
# 2. Ketma-ket xulq (ikkala rejimda) — tuzatish oddiy oqimni buzmagan
# ══════════════════════════════════════════════════════════════
def bolim_ketma_ket():
    section("2. Ketma-ket xulq (API)")
    O, I = yangi()
    r = dlv_api(O, I, 8, "dp k1")
    check("yuk 8 → 200", r.status_code == 200 and (js(r) or {}).get("success"), getattr(r, "text", "")[:200])
    r = req(C, "put", f"/api/order-items/{I}", json={"quantity": 6})
    check("keyin detal 10 → 6 → 400 'Topshirilgan miqdordan (8) kam qilib bo'lmaydi'",
          r.status_code == 400 and "Topshirilgan miqdordan" in str((js(r) or {}).get("detail")),
          f"{r.status_code} {getattr(r, 'text', '')[:200]}")
    h = holat(O)
    check("holat o'zgarmagan: detal 10, berilgan 8", h["detal"].get(I) == (10.0, 8.0), str(h))
    r = req(C, "put", f"/api/order-items/{I}", json={"quantity": 9})
    check("detal 10 → 9 (berilgandan ko'p) → 200", r.status_code == 200, f"{r.status_code} {getattr(r, 'text', '')[:200]}")
    check("detal 9, berilgan 8", holat(O)["detal"].get(I) == (9.0, 8.0), str(holat(O)))
    r = req(C, "delete", f"/api/order-items/{I}")
    check("topshirilgan detalni o'chirish → 404 (o'chmaydi)", r.status_code == 404, f"{r.status_code}")
    check("detal joyida", I in holat(O)["detal"], str(holat(O)))

    O2, I2 = yangi()
    p0 = holat(O2)["peno"]
    r = req(C, "put", f"/api/order-items/{I2}", json={"quantity": 6})
    check("topshirilmagan detal 10 → 6 → 200", r.status_code == 200, f"{r.status_code} {getattr(r, 'text', '')[:200]}")
    h = holat(O2)
    check("summa 600 000, penoplast 0.4 blok omborga qaytdi (commit=False ham SAQLANADI)",
          h["total"] == 600000.0 and abs(h["peno"] - p0 - 0.4) < 1e-6, f"{h} {p0}")
    r = req(C, "delete", f"/api/order-items/{I2}")
    check("topshirilmagan detalni o'chirish → 200", r.status_code == 200, f"{r.status_code} {getattr(r, 'text', '')[:200]}")
    h = holat(O2)
    check("detal yo'q, summa 0, penoplast yana 0.6 blok qaytdi (jami 1.0)",
          h["detal"] == {} and h["total"] == 0.0 and abs(h["peno"] - p0 - 1.0) < 1e-6, f"{h} {p0}")

    O3, I3 = yangi()
    r = req(C, "post", f"/api/orders/{O3}/ready")
    check("'Tayyor' → 200", r.status_code == 200, f"{r.status_code} {getattr(r, 'text', '')[:200]}")
    h = holat(O3)
    check("hammasi avtomatik topshirildi (10 / 10), holat ready", h["detal"].get(I3) == (10.0, 10.0)
          and h["status"] == "ready" and h["yuk"] == 1, str(h))
    r = req(C, "post", f"/api/orders/{O3}/ready")
    check("ikkinchi 'Tayyor' → 400 'allaqachon tayyor'", r.status_code == 400
          and "allaqachon tayyor" in str(js(r)), f"{r.status_code} {getattr(r, 'text', '')[:200]}")
    check("yuk xati hali 1 ta", holat(O3)["yuk"] == 1, str(holat(O3)))

    O4, I4 = yangi()
    dlv_api(O4, I4, 5, "dp k4")
    r = req(C, "post", f"/api/orders/{O4}/ready")
    h = holat(O4)
    check("5 / 10 dan keyin 'Tayyor' → 200, qisman yakunlash: detal 5, summa 500 000, ready",
          r.status_code == 200 and h["detal"].get(I4) == (5.0, 5.0) and h["total"] == 500000.0
          and h["status"] == "ready", f"{r.status_code} {h}")

    O5, I5 = yangi()
    dlv_api(O5, I5, 4, "dp k5")
    r = req(C, "put", f"/api/orders/{O5}", json={
        "project_id": PRJ_ID, "order_type": "product",
        "items": [{"name": f"DP_D{_n[0]}", "category": "panel", "width": 100, "thickness": 10,
                   "length": 100, "quantity": 3, "unit_price": 100000, "is_coated": False,
                   "penoplast_id": PENO}]})
    check("to'liq tahrir (PUT /api/orders): berilgan 4 dan kam (3) — rad, detal 10 / 4 o'zgarmagan",
          r.status_code in (400, 409, 200) and holat(O5)["detal"].get(I5) == (10.0, 4.0),
          f"{r.status_code} {getattr(r, 'text', '')[:200]} {holat(O5)}")


# ══════════════════════════════════════════════════════════════
# 3. PARALLEL (faqat HAQIQIY PG) — kech38 12m naqshi
# ══════════════════════════════════════════════════════════════
def sekin(s):
    asl = s.commit

    def f():
        time.sleep(0.4)
        asl()
    s.commit = f


def poyga(birinchi, ikkinchi):
    """birinchi(s) — commit 0.4 s kechiktiriladi; ikkinchi(s) 0.15 s keyin."""
    nat = [None, None]
    bar = threading.Barrier(2)

    def t(k, fn, kech):
        s = SessionLocal()
        if kech:
            sekin(s)
        try:
            try:
                bar.wait(timeout=30)
            except Exception:                   # noqa: BLE001
                pass
            if not kech:
                time.sleep(0.15)
            try:
                nat[k] = fn(s)
            except Exception as e:              # noqa: BLE001
                try:
                    s.rollback()
                except Exception:               # noqa: BLE001
                    pass
                nat[k] = f"ISTISNO {type(e).__name__}: {str(e)[:200]}"
        finally:
            s.close()
    ts = [threading.Thread(target=t, args=(0, birinchi, True)),
          threading.Thread(target=t, args=(1, ikkinchi, False))]
    for x in ts:
        x.start()
    for x in ts:
        x.join(timeout=120)
    return nat


def bolim_parallel():
    section("3. Parallel (HAQIQIY PG, har holat 3 urinish)")
    if not PG_URL:
        print("  (faqat PG rejimida)")
        return
    upd6 = lambda i: (lambda s: crud.update_order_item(s, i, {"quantity": 6}, company_id=1))  # noqa: E731
    dele = lambda i: (lambda s: crud.delete_order_item(s, i, company_id=1))                    # noqa: E731
    yomon = {k: [] for k in ("R1", "R1b", "R2a", "R2b", "R3", "R4")}
    for k in range(3):
        O, I = yangi()
        n = poyga(upd6(I), yuk(O, I, 8, "dp r1"))
        h = holat(O)
        if not (h["detal"].get(I) == (6.0, 0.0) and isinstance(n[1], dict) and not n[1].get("success")):
            yomon["R1"].append((n, h))
        O, I = yangi()
        n = poyga(yuk(O, I, 8, "dp r1b"), upd6(I))
        h = holat(O)
        if not (h["detal"].get(I) == (10.0, 8.0) and "Topshirilgan miqdordan" in str(n[1])):
            yomon["R1b"].append((n, h))
        O, I = yangi()
        n = poyga(dele(I), yuk(O, I, 3, "dp r2a"))
        h = holat(O)
        if not (h["detal"] == {} and h["yuk"] == 0 and isinstance(n[1], dict)
                and "topilmadi" in str(n[1].get("message"))):
            yomon["R2a"].append((n, h))
        O, I = yangi()
        n = poyga(yuk(O, I, 3, "dp r2b"), dele(I))
        h = holat(O)
        if not (h["detal"].get(I) == (10.0, 3.0) and n[1] is False):
            yomon["R2b"].append((n, h))
        O, I = yangi()
        n = poyga(yuk(O, I, 5, "dp r3"), lambda s, o=O: services.complete_order(s, o))
        h = holat(O)
        if not (h["status"] == "ready" and h["detal"].get(I) == (5.0, 5.0) and h["total"] == 500000.0):
            yomon["R3"].append((n, h))
        O, I = yangi()
        n = poyga(lambda s, o=O: services.complete_order(s, o), lambda s, o=O: services.complete_order(s, o))
        h = holat(O)
        ok2 = [isinstance(x, dict) and x.get("success") for x in n]
        if not (ok2 == [True, False] and "allaqachon tayyor" in str(n[1]) and h["yuk"] == 1
                and h["detal"].get(I) == (10.0, 10.0)):
            yomon["R4"].append((n, h))
    check("R1 tahrir 10→6 (tasdiqlanmagan) || yuk 8: yuk rad, detal 6 / 0", not yomon["R1"], str(yomon["R1"][:1]))
    check("R1b yuk 8 (tasdiqlanmagan) || tahrir 10→6: tahrir rad, detal 10 / 8", not yomon["R1b"], str(yomon["R1b"][:1]))
    check("R2a o'chirish (tasdiqlanmagan) || yuk 3: yuk rad 'topilmadi', yuk xati yo'q", not yomon["R2a"], str(yomon["R2a"][:1]))
    check("R2b yuk 3 (tasdiqlanmagan) || o'chirish: o'chirish rad (500 EMAS), detal 10 / 3", not yomon["R2b"], str(yomon["R2b"][:1]))
    check("R3 yuk 5 (tasdiqlanmagan) || 'Tayyor': qisman yakunlash — 5 / 5, summa 500 000", not yomon["R3"], str(yomon["R3"][:1]))
    check("R4 'Tayyor' || 'Tayyor': faqat bittasi bajariladi", not yomon["R4"], str(yomon["R4"][:1]))


def kumulyativ():
    section("4. 5xx yo'q")
    r = req(C, "get", "/api/orders")
    check("/api/orders → 200", r.status_code == 200, f"{r.status_code}")


for _b in (bolim_statik, bolim_ketma_ket, bolim_parallel, kumulyativ):
    try:
        _b()
    except Exception as _e:                # noqa: BLE001
        check(f"{_b.__name__}: kutilmagan istisno yo'q", False, f"{type(_e).__name__}: {_e}")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
