#!/usr/bin/env python3
"""
test_qaytarish_ochirish.py — 5-bo'lim 22-band (K39-1) va K40-1 darvozasi (kech40, 2026-09-23).

NIMA UCHUN KERAK (asl kod `42da36b` da O'LCHANGAN — SQLite va HAQIQIY
PostgreSQL 16, `work/probe40.py`, `work/probe40b.py`)
--------------------------------------------------------------------
  * Qaytarish yozuvini o'chirish faqat yozuvni o'chirardi. Omborga qaytgan
    detal tayyor mahsulotlarda QOLARDI — qayta kiritilsa ikki baravar
    (10 → 20); qaytgan mahsulot qisman sotilgan / band qilingan bo'lsa ham
    o'chirish jim 200.
  * "Pul qaytdi" bosilgan yozuv o'chirilsa — kamaytirilgan kelishilgan summa
    (1 000 000 → 700 000) va manfiy to'lov (−300 000) QOLARDI; qayta kiritib
    yana bosilsa 400 000 va −600 000 (pul ikki marta qaytarilgandek).
  * K40-1: qaytgan (RETURNED) tayyor mahsulot bazada IN_PROGRESS bo'lib
    yaratilardi — `DELETE /api/finished/{id}` 100 metr qoldig'i bor qaytgan
    mahsulotni jim o'chirar va penoplastini xomashyo omboriga soxta
    QAYTARARDI (99 → 100 blok).
  * `mark_refunded` qulfsiz edi — ikki parallel "pul qaytdi" ikki manfiy
    to'lov yozardi; `add_returned_to_stock` mahsulot qatorini qulfsiz
    o'qib-yozardi — parallel sotuvning kamaytirishi yo'qolardi.

FOYDALANUVCHI QARORI (kech40, B): pul qaytarilgan qaytarish o'chirilsa HAMMASI
orqaga qaytadi (kelishilgan summa tiklanadi, manfiy to'lov o'chadi, loyiha
"To'langan" summasi yangilanadi, jurnalga yoziladi). Yangilanishdan OLDIN
belgilangan pul qaytarish (to'lov bog'lami yo'q) — o'chirish rad (taxmin
qilinmaydi).

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi (P —
parallel bo'limlari faqat PG da).
    python3 tools/test_qaytarish_ochirish.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_qaytarish_ochirish.py
"""
import os
import sys
import ast
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qaytarish_ochirish_test"
_DB = os.path.join(tempfile.gettempdir(), "qaytarish_ochirish_test.db")

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
    import crud, auth, schemas                     # noqa: E402
    import database                                # noqa: E402

from sqlalchemy import text, inspect as sa_inspect  # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, ReturnItem, FinishedProduct, StockSource,
    Inventory, InventoryMovement, Payment, ActivityLog, FinishedProductSale,
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
    """Rad javobidagi sabab matni (`detail.message` yoki `detail` matn)."""
    d = js(r)
    if isinstance(d, dict):
        det = d.get("detail")
        if isinstance(det, dict):
            return str(det.get("message") or "")
        return str(det or "")
    return ""


def taxminan(a, b, eps=0.011):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="QO Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "QO_admin", "Parol123!", UserRole.ADMIN, "QO Admin", company_id=1)
    auth.create_user(_db, "QO_admin_b", "Parol123!", UserRole.ADMIN, "QO Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="QO Mijoz", project_name="QO loyiha", total_budget=0, total_paid=0)
PRJ_B = Project(company_id=2, client_name="QO Mijoz B", project_name="QO loyiha B", total_budget=0, total_paid=0)
# 2-loyiha (1-korxona): AYNAN bir xil detal ikkinchi buyurtmada — `create_order` 8 s takror-himoyasi
# (bir loyiha + bir xil tarkib) mavjud buyurtmani qaytarmasligi uchun
PRJ_2 = Project(company_id=1, client_name="QO Mijoz 2", project_name="QO loyiha 2", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="QO Penoplast", unit="blok", stock_quantity=1000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
PENO_B = Inventory(company_id=2, item_name="QO Penoplast B", unit="blok", stock_quantity=1000,
                   price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_db.add_all([PRJ, PRJ_B, PRJ_2, PENO, PENO_B])
_db.commit()
PRJ_ID, PRJB_ID, PRJ2_ID, PENO_ID, PENOB_ID = PRJ.id, PRJ_B.id, PRJ_2.id, PENO.id, PENO_B.id
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("QO_admin")
CB, _s2 = _kir("QO_admin_b")
if _s1 != 302 or _s2 != 302:
    print(f"LOGIN BO'LMADI: {_s1} / {_s2}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def buyurtma(nom=None, dona=10, narx=50_000, b=False, prj=None):
    """API orqali YANGI buyurtma (profil, penoplastli — tan narxi va hajm NOLDAN
    farqli; 10 dona × 100 sm = 100 metr) → (order_id, detal_id, buyurtmadagi miqdor)."""
    _n[0] += 1
    nom = nom or f"QO_D{_n[0]}"
    r = req(CB if b else C, "post", "/api/orders", json={
        "project_id": PRJB_ID if b else (prj or PRJ_ID), "order_type": "product", "items": [
            {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 100,
             "quantity": dona, "unit_price": narx, "is_coated": False,
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
        return oi.order_id, oi.id, float(oi.order_qty_normalized)
    finally:
        d.close()


def detal_nomi(iid):
    d = SessionLocal()
    try:
        return d.get(OrderItem, iid).name
    finally:
        d.close()


def qaytar(oid, iid, miqdor, sabab="Ortiqcha", b=False, **kw):
    t = {"order_id": oid, "order_item_id": iid, "item_name": detal_nomi(iid),
         "quantity": miqdor, "unit": "metr", "reason": sabab}
    t.update(kw)
    r = req(CB if b else C, "post", "/api/returns", json=t)
    rid = (js(r) or {}).get("id") if (r.status_code == 200 and isinstance(js(r), dict)) else None
    return r, rid


def ochir(rid, c=None):
    return req(c or C, "delete", f"/api/returns/{rid}")


def pul_qaytdi(rid, c=None):
    return req(c or C, "post", f"/api/returns/{rid}/refund")


def ri(rid):
    d = SessionLocal()
    try:
        x = d.get(ReturnItem, rid)
        if x is None:
            return None
        return {"fp": x.finished_product_id, "stock_qty": getattr(x, "stock_qty", "YO'Q"),
                "stock_cost": (float(x.stock_cost) if getattr(x, "stock_cost", None) is not None
                               else getattr(x, "stock_cost", "YO'Q")),
                "stock_volume": getattr(x, "stock_volume_m3", "YO'Q"),
                "refunded_at": getattr(x, "refunded_at", "YO'Q"),
                "delta": (float(x.refund_agreed_delta) if getattr(x, "refund_agreed_delta", None) is not None
                          else getattr(x, "refund_agreed_delta", "YO'Q")),
                "is_refunded": bool(x.is_refunded), "refund": float(x.refund_amount or 0)}
    finally:
        d.close()


def fp_by_name(nom):
    d = SessionLocal()
    try:
        return [(f.id, round(float(f.quantity or 0), 6)) for f in d.query(FinishedProduct).filter(
            FinishedProduct.name == nom, FinishedProduct.source == StockSource.RETURNED).order_by(FinishedProduct.id).all()]
    finally:
        d.close()


def fp(fid):
    if fid is None:
        return None
    d = SessionLocal()
    try:
        f = d.get(FinishedProduct, fid)
        if f is None:
            return None
        return {"qty": round(float(f.quantity or 0), 6), "produced": round(float(f.produced_quantity or 0), 6),
                "cost": float(f.cost_price or 0), "vol": round(float(f.volume_m3 or 0), 6),
                "reserved": float(f.reserved_quantity or 0),
                "status": getattr(f.production_status, "value", f.production_status)}
    finally:
        d.close()


def peno(pid=None):
    d = SessionLocal()
    try:
        x = d.get(Inventory, pid or PENO_ID)
        mv = d.query(InventoryMovement).filter(InventoryMovement.inventory_id == (pid or PENO_ID)).count()
        return round(float(x.stock_quantity), 6), mv
    finally:
        d.close()


def pul(oid):
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        p = d.get(Project, o.project_id)
        ps = [(x.id, float(x.amount), getattr(x, "return_item_id", "YO'Q"))
              for x in d.query(Payment).filter(Payment.order_id == oid).order_by(Payment.id).all()]
        return {"agreed": float(o.agreed_amount) if o.agreed_amount is not None else None,
                "status": str(getattr(o.payment_status, "value", o.payment_status)),
                "tolovlar": ps, "manfiy": [t for t in ps if t[1] < 0],
                "loyiha": float(p.total_paid or 0)}
    finally:
        d.close()


def fp_id_of(rid):
    """Qaytarish omborga qo'shgan mahsulot. Yozuvda bog'lam bo'lmasa (asl kod —
    `finished_product_id` hech qachon to'ldirilmasdi) — detal nomi bo'yicha
    qaytgan mahsulot (test asl kodga qarshi ham QULAMASDAN o'lchasin)."""
    x = ri(rid)
    if x and x.get("fp"):
        return x["fp"]
    d = SessionLocal()
    try:
        z = d.get(ReturnItem, rid)
        if z is None:
            return None
        f = d.query(FinishedProduct).filter(FinishedProduct.name == z.item_name,
                                            FinishedProduct.source == StockSource.RETURNED).order_by(
            FinishedProduct.id.desc()).first()
        return f.id if f else None
    finally:
        d.close()


def orm(fn):
    d = SessionLocal()
    try:
        fn(d)
        d.commit()
    finally:
        d.close()


def jurnal(entity_type, entity_id):
    d = SessionLocal()
    try:
        return [(a.action, a.new_value or "") for a in d.query(ActivityLog).filter(
            ActivityLog.entity_type == entity_type, ActivityLog.entity_id == entity_id).all()]
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════
# M. MIGRATSIYA (BIRINCHI — PG da ustun butunlay olib tashlanadi)
# ══════════════════════════════════════════════════════════════
def _pay_indekslar():
    return {ix["name"] for ix in sa_inspect(engine).get_indexes("payments")}


def _pay_ustunlar():
    return {c["name"] for c in sa_inspect(engine).get_columns("payments")}


def _fk_turi():
    with engine.connect() as c:
        r = c.execute(text(
            "SELECT c.confdeltype FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey) "
            "WHERE t.relname = 'payments' AND c.contype = 'f' "
            "AND a.attname = 'return_item_id'")).first()
    if not r:
        return None
    v = r[0]
    return v.decode() if isinstance(v, (bytes, bytearray)) else str(v)


def bolim_migratsiya():
    section("M. Migratsiya: payments.return_item_id (ustun, indeks, PG FK), qaytgan mahsulot holati")
    check("M0 yangi baza: payments.return_item_id ustuni bor", "return_item_id" in _pay_ustunlar(),
          sorted(_pay_ustunlar()))
    check("M0 yangi baza: indeks ix_payments_return_item_id", "ix_payments_return_item_id" in _pay_indekslar(),
          sorted(_pay_indekslar()))
    ri_ust = {c["name"] for c in sa_inspect(engine).get_columns("return_items")}
    check("M0 return_items: stock_qty / stock_cost / stock_volume_m3 / refunded_at / refund_agreed_delta",
          {"stock_qty", "stock_cost", "stock_volume_m3", "refunded_at", "refund_agreed_delta"} <= ri_ust,
          sorted(ri_ust))
    if PG_URL:
        check("M0 PG: FK ON DELETE SET NULL", _fk_turi() == "n", _fk_turi())

    # Eski holat: qaytgan mahsulot IN_PROGRESS (asl kodning standarti), ustun / indeks yo'q
    O, i1, _b = buyurtma("QO_MIG")
    r, rid = qaytar(O, i1, 5)
    fid = fp_id_of(rid) or (fp_by_name("QO_MIG")[0][0] if fp_by_name("QO_MIG") else None)
    with engine.connect() as c:
        c.execute(text("UPDATE finished_products SET production_status = 'IN_PROGRESS' "
                       "WHERE source = 'RETURNED'"))
        if PG_URL:
            if "return_item_id" in _pay_ustunlar():
                c.execute(text("ALTER TABLE payments DROP COLUMN return_item_id"))
        else:
            c.execute(text("DROP INDEX IF EXISTS ix_payments_return_item_id"))
        c.commit()
    engine.dispose()
    check("M1 tayyorgarlik: qaytgan mahsulot IN_PROGRESS", (fp(fid) or {}).get("status") == "in_progress", fp(fid))

    mig = getattr(main, "_migrate_qaytarish_orqaga", None)
    chiq = io.StringIO()
    with contextlib.redirect_stdout(chiq):
        try:
            database.sync_missing_columns()
        except Exception as e:                  # noqa: BLE001
            print(f"SYNC ISTISNO {e}")
        if mig:
            try:
                mig()
            except Exception as e:              # noqa: BLE001
                print(f"MIG ISTISNO {e}")
    matn = chiq.getvalue()
    engine.dispose()
    check("M1 migratsiya funksiyasi bor", mig is not None)
    check("M1 migratsiya istisnosiz", "ISTISNO" not in matn and "o'tkazib yuborildi" not in matn, matn[-300:])
    check("M1 ustun bor", "return_item_id" in _pay_ustunlar(), sorted(_pay_ustunlar()))
    check("M1 indeks bor", "ix_payments_return_item_id" in _pay_indekslar(), sorted(_pay_indekslar()))
    if PG_URL:
        check("M1 PG: FK ON DELETE SET NULL qo'yildi", _fk_turi() == "n", _fk_turi())
    check("M1 qaytgan mahsulot holati → ready", (fp(fid) or {}).get("status") == "ready", fp(fid))
    check("M1 log: 'holati tuzatildi ... 1 ta'", "holati tuzatildi" in matn and ": 1 ta" in matn, matn[-300:])

    chiq2 = io.StringIO()
    with contextlib.redirect_stdout(chiq2):
        try:
            if mig:
                mig()
        except Exception as e:                  # noqa: BLE001
            print(f"MIG ISTISNO {e}")
    engine.dispose()
    m2 = chiq2.getvalue()
    check("M2 qayta ishga tushirish: jim, istisnosiz (idempotent)",
          "ISTISNO" not in m2 and "holati tuzatildi" not in m2 and "qo'shildi" not in m2, m2[-300:])
    r2 = ochir(rid)
    check("M3 migratsiyadan keyin qaytarishni o'chirish → 200", r2.status_code == 200, (r2.status_code, xabar(r2)))

    # F6 naqshi — statik: chaqiruv modul darajasida, e'lon va `_migrate_return_order_item()` dan keyin
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read().splitlines()
    _def = [k for k, q in enumerate(src) if q.startswith("def _migrate_qaytarish_orqaga(")]
    _ch = [k for k, q in enumerate(src) if q.strip() == "_migrate_qaytarish_orqaga()" and not q.startswith(" ")]
    _asl = [k for k, q in enumerate(src) if q.strip() == "_migrate_return_order_item()" and not q.startswith(" ")]
    check("M4 statik: _migrate_qaytarish_orqaga() modul darajasida, e'londan va 3-band migratsiyasidan keyin",
          len(_def) == 1 and len(_ch) == 1 and len(_asl) == 1 and _def[0] < _ch[0] and _asl[0] < _ch[0],
          (_def, _ch, _asl))


# ══════════════════════════════════════════════════════════════
# A. Ombor — asosiy (K39-1)
# ══════════════════════════════════════════════════════════════
def bolim_ombor():
    section("A. Ombor: o'chirish omborga qo'shilganini AYNAN olib tashlaydi")
    O, i1, buy = buyurtma("QO_A")
    p0 = peno()
    r, rid = qaytar(O, i1, 10)
    check("A1 qaytarish 10 → 200", r.status_code == 200, (r.status_code, xabar(r)))
    x = ri(rid) or {}
    f = fp(x.get("fp"))
    check("A1 yozuv tayyor mahsulotga bog'landi (finished_product_id)", f is not None, x)
    check("A1 stock_qty = 10", taxminan(x.get("stock_qty"), 10, 1e-9), x)
    check("A1 stock_cost = mahsulot tan narxi (> 0)", f is not None and x.get("stock_cost") not in (None, "YO'Q")
          and taxminan(x.get("stock_cost"), f["cost"]) and f["cost"] > 0, (x, f))
    check("A1 stock_volume_m3 = mahsulot hajmi (> 0)", f is not None and x.get("stock_volume") not in (None, "YO'Q")
          and taxminan(x.get("stock_volume"), f["vol"], 1e-9) and f["vol"] > 0, (x, f))
    check("A1 K40-1: yangi qaytgan mahsulot holati 'ready'", (f or {}).get("status") == "ready", f)
    fid = x.get("fp")
    r = ochir(rid)
    j = js(r) or {}
    check("A2 o'chirish → 200", r.status_code == 200, (r.status_code, xabar(r)))
    check("A2 javob: ombordan_olindi 10, mahsulot_ochirildi true",
          isinstance(j, dict) and taxminan(j.get("ombordan_olindi"), 10, 1e-9) and j.get("mahsulot_ochirildi") is True, j)
    check("A2 yozuv o'chdi", ri(rid) is None)
    check("A2 faqat shu qaytarishdan paydo bo'lgan mahsulot butunlay o'chdi", fp(fid) is None, fp(fid))
    check("A2 penoplast ombori O'ZGARMADI (soxta qaytish yo'q)", peno() == p0, (p0, peno()))
    jr = jurnal("return", rid)
    check("A2 jurnal: 'return' 'deleted', 'ombordan olindi: 10'",
          any(a == "deleted" and "ombordan olindi: 10" in v for a, v in jr), jr)
    r, rid2 = qaytar(O, i1, 10)
    check("A3 yana 10 → 200", r.status_code == 200, (r.status_code, xabar(r)))
    check("A3 omborda 10 (20 EMAS)", [q for _, q in fp_by_name("QO_A")] == [10.0], fp_by_name("QO_A"))


# ══════════════════════════════════════════════════════════════
# B. Birlashgan mahsulot (bir nechta qaytarish bitta kartada)
# ══════════════════════════════════════════════════════════════
def bolim_birlashish():
    section("B. Birlashish: 4 + 3 bitta kartada — 4 ni o'chirish AYNAN 3 ni qoldiradi")
    O, i1, _b = buyurtma("QO_B")
    _, ra = qaytar(O, i1, 4)
    _, rb = qaytar(O, i1, 3)
    xa, xb = ri(ra) or {}, ri(rb) or {}
    check("B1 ikkala qaytarish bitta mahsulotda", xa.get("fp") is not None and xa.get("fp") == xb.get("fp"), (xa, xb))
    fid = xa.get("fp")
    f7 = fp(fid) or {}
    check("B1 mahsulot 7", taxminan(f7.get("qty"), 7, 1e-9), f7)
    r = ochir(ra)
    f3 = fp(fid) or {}
    check("B2 4 ni o'chirish → 200", r.status_code == 200, (r.status_code, xabar(r)))
    check("B2 qoldiq 3, ishlab chiqarilgan 3", taxminan(f3.get("qty"), 3, 1e-9) and taxminan(f3.get("produced"), 3, 1e-9), f3)
    check("B2 tan narxi = 3 niki (stock_cost)", taxminan(f3.get("cost"), xb.get("stock_cost")), (f3, xb))
    check("B2 hajm = 3 niki (stock_volume_m3)", taxminan(f3.get("vol"), xb.get("stock_volume"), 1e-6), (f3, xb))
    check("B2 mahsulot O'CHMADI (boshqa qaytarish bog'langan)", fp(fid) is not None)
    r = ochir(rb)
    check("B3 3 ni o'chirish → 200, mahsulot o'chdi", r.status_code == 200 and fp(fid) is None,
          (r.status_code, xabar(r), fp(fid)))


# ══════════════════════════════════════════════════════════════
# C / D / E. Mahsulot ishlatilgan — rad
# ══════════════════════════════════════════════════════════════
def bolim_ishlatilgan():
    section("C. Kamaytirilgan: 10 qaytdi, 8 chiqarildi — o'chirish rad, hech narsa o'zgarmaydi")
    O, i1, _b = buyurtma("QO_C")
    _, rc = qaytar(O, i1, 10)
    fid = fp_id_of(rc)
    r = req(C, "post", f"/api/finished/{fid}/reduce", json={"quantity": 8, "reason": "QO singan"})
    check("C0 kamaytirish 8 → 200", r.status_code == 200, (r.status_code, r.text[:200]))
    f0 = fp(fid)
    r = ochir(rc)
    check("C1 o'chirish → 400", r.status_code == 400, (r.status_code, xabar(r)))
    check("C1 sabab: 10 qo'shilgan, bo'sh qoldig'i 2",
          "10 metr qo'shilgan" in xabar(r) and "bo'sh qoldig'i 2 metr" in xabar(r), xabar(r))
    check("C1 yozuv qoldi, mahsulot o'zgarmadi", ri(rc) is not None and fp(fid) == f0, (ri(rc), fp(fid), f0))

    section("D. Band qilingan: 6 qaytdi, 5 band — rad; band bekor qilinsa — o'chadi")
    O, i1, _b = buyurtma("QO_D")
    _, rd = qaytar(O, i1, 6)
    fid = fp_id_of(rd)
    orm(lambda d: setattr(d.get(FinishedProduct, fid), "reserved_quantity", 5.0))
    r = ochir(rd)
    check("D1 o'chirish → 400, sababda 'band'", r.status_code == 400 and "band" in xabar(r), (r.status_code, xabar(r)))
    check("D1 yozuv qoldi, qoldiq 6", ri(rd) is not None and taxminan((fp(fid) or {}).get("qty"), 6, 1e-9), fp(fid))
    orm(lambda d: setattr(d.get(FinishedProduct, fid), "reserved_quantity", 0.0))
    r = ochir(rd)
    check("D2 band bekor → o'chirish 200, mahsulot o'chdi", r.status_code == 200 and fp(fid) is None,
          (r.status_code, xabar(r), fp(fid)))

    section("E. Sotuv tarixi bor birlashgan mahsulot (10 + 5, 3 sotildi)")
    # ikkinchi buyurtma BOSHQA loyihada — `create_order` 8 s takror-himoyasi AYNAN bir xil
    # buyurtmani qayta qaytarmasin; detal aynan bir xil — mahsulotlar birlashadi
    O1, a1, _b = buyurtma("QO_E")
    O2, a2, _b = buyurtma("QO_E", prj=PRJ2_ID)
    _, r10 = qaytar(O1, a1, 10)
    _, r5 = qaytar(O2, a2, 5)
    fid = fp_id_of(r10)
    check("E0 ikki xil buyurtma", O1 != O2, (O1, O2))
    check("E0 bitta mahsulotda 15", fid is not None and fid == fp_id_of(r5) and taxminan((fp(fid) or {}).get("qty"), 15, 1e-9),
          (fid, fp_id_of(r5), fp(fid)))
    r = req(C, "post", "/api/finished/sell", json={"finished_product_id": fid, "quantity": 3, "unit_price": 1000,
                                                   "confirm_below_cost": True})
    check("E0 sotuv 3 → 200", r.status_code == 200, (r.status_code, r.text[:200]))
    r = ochir(r10)
    f = fp(fid) or {}
    check("E1 10 ni o'chirish → 200", r.status_code == 200, (r.status_code, xabar(r)))
    check("E1 qoldiq 2, ishlab chiqarilgan 5, mahsulot SAQLANDI (sotuv tarixi)",
          taxminan(f.get("qty"), 2, 1e-9) and taxminan(f.get("produced"), 5, 1e-9), f)
    r = ochir(r5)
    check("E2 5 ni o'chirish → 400 (bo'sh 2)", r.status_code == 400 and "bo'sh qoldig'i 2" in xabar(r),
          (r.status_code, xabar(r)))


# ══════════════════════════════════════════════════════════════
# F. Mahsulotning o'zi o'chirilgan + K40-1
# ══════════════════════════════════════════════════════════════
def bolim_mahsulot_ochirish():
    section("F. K40-1: qoldig'i bor qaytgan mahsulotni o'chirish rad; nolga tushgach o'chadi; bog'lam uziladi")
    O, i1, _b = buyurtma("QO_F")
    _, rf = qaytar(O, i1, 5)
    fid = fp_id_of(rf)
    p0 = peno()
    r = req(C, "delete", f"/api/finished/{fid}")
    check("F1 DELETE /api/finished (qoldiq 5) → 400", r.status_code == 400, (r.status_code, xabar(r)))
    check("F1 mahsulot qoldi, penoplast ombori o'zgarmadi", fp(fid) is not None and peno() == p0, (fp(fid), p0, peno()))
    # Eski qator: holat IN_PROGRESS (migratsiyadan oldingi) — baribir tayyor hisoblanadi
    def _jarayonda(d):
        f = d.get(FinishedProduct, fid)
        if f is not None:               # asl kodda F1 uni o'chirib yuborgan bo'ladi
            f.production_status = __import__("models").ProductionStatus.IN_PROGRESS
    orm(_jarayonda)
    r = req(C, "delete", f"/api/finished/{fid}")
    check("F2 eski IN_PROGRESS qaytgan mahsulot (qoldiq 5) ham → 400", r.status_code == 400,
          (r.status_code, xabar(r)))
    check("F2 penoplast soxta qaytmadi", peno() == p0, (p0, peno()))
    r = req(C, "post", f"/api/finished/{fid}/reduce", json={"quantity": 5, "reason": "QO nolga"})
    r = req(C, "delete", f"/api/finished/{fid}")
    check("F3 nolga tushgach DELETE → 200 (PG da FK 500 EMAS)", r.status_code == 200, (r.status_code, r.text[:200]))
    check("F3 penoplast ombori o'zgarmadi (IN_PROGRESS qatorda ham)", peno() == p0, (p0, peno()))
    check("F3 qaytarish yozuvi qoldi, bog'lam uzildi", (ri(rf) or {}).get("fp", "x") is None, ri(rf))
    r = ochir(rf)
    j = js(r) or {}
    check("F4 keyin qaytarishni o'chirish → 200, ombordan hech narsa olinmadi",
          r.status_code == 200 and isinstance(j, dict) and j.get("ombordan_olindi") == 0, (r.status_code, j))


# ══════════════════════════════════════════════════════════════
# G / H / I. Omborga tushmagan / eski / brak
# ══════════════════════════════════════════════════════════════
def bolim_boshqa():
    section("G / H / I. to_stock=false, yangilanishdan oldingi yozuv, brak")
    O, i1, _b = buyurtma("QO_G")
    _, rg = qaytar(O, i1, 3, to_stock=False)
    x = ri(rg) or {}
    check("G1 to_stock=false: bog'lam yo'q", x.get("fp") is None and x.get("stock_qty") is None, x)
    r = ochir(rg)
    check("G2 o'chirish → 200, mahsulot yaratilmagan", r.status_code == 200 and fp_by_name("QO_G") == [],
          (r.status_code, fp_by_name("QO_G")))

    O, i1, _b = buyurtma("QO_H")
    _, rh = qaytar(O, i1, 4)

    def eski(d):
        z = d.get(ReturnItem, rh)
        z.finished_product_id = None
        for k in ("stock_qty", "stock_cost", "stock_volume_m3"):
            if hasattr(z, k):
                setattr(z, k, None)
    orm(eski)
    r = ochir(rh)
    check("H1 eski (bog'lamsiz) yozuv → 200, ombor avvalgidek o'zgarmadi (bog'lam noma'lum)",
          r.status_code == 200 and [q for _, q in fp_by_name("QO_H")] == [4.0], (r.status_code, fp_by_name("QO_H")))

    O, i1, _b = buyurtma("QO_I")
    _, rb = qaytar(O, i1, 2, sabab="Brak")
    check("I1 brak: ombor bog'lami yo'q", (ri(rb) or {}).get("stock_qty", "x") is None, ri(rb))
    r = ochir(rb)
    check("I2 brakni o'chirish → 200", r.status_code == 200, (r.status_code, xabar(r)))


# ══════════════════════════════════════════════════════════════
# R. Pul (FOYDALANUVCHI QARORI B)
# ══════════════════════════════════════════════════════════════
def bolim_pul():
    section("R. Pul qaytarilgan qaytarishni o'chirish — hammasi orqaga")
    O, i1, _b = buyurtma("QO_R", dona=10, narx=100_000)        # 1 000 000, 100 metr → 10 000 / metr
    # kech42 (24-band): naqd faqat mijoz ORTIQCHA to'lagan qism uchun — manfiy to'lov
    # (va uning bog'lami / o'chirilishi) sinalishi uchun buyurtma to'liq to'langan.
    req(C, "post", "/api/payments", json={"order_id": O, "amount": 1_000_000, "payment_method": "naqd"})
    p0 = pul(O)
    _, rr = qaytar(O, i1, 30, to_stock=False)                  # 300 000
    r = pul_qaytdi(rr)
    p1 = pul(O)
    x = ri(rr) or {}
    check("R1 pul qaytdi → 200; kelishilgan 700 000, manfiy −300 000", r.status_code == 200
          and taxminan(p1["agreed"], 700_000) and [t[1] for t in p1["manfiy"]] == [-300_000.0], (r.status_code, p1))
    check("R1 manfiy to'lov qaytarishga bog'langan (return_item_id)",
          [t[2] for t in p1["manfiy"]] == [rr], p1["manfiy"])
    check("R1 refunded_at yozildi, delta 300 000", x.get("refunded_at") not in (None, "YO'Q")
          and taxminan(x.get("delta"), 300_000), x)
    check("R1 loyiha 'To'langan' −300 000", taxminan(p1["loyiha"], p0["loyiha"] - 300_000), (p0, p1))
    pid = p1["manfiy"][0][0] if p1["manfiy"] else None
    r = ochir(rr)
    j = js(r) or {}
    p2 = pul(O)
    check("R2 o'chirish → 200, javobda pul_bekor_qilindi 300 000, tolov_ochirildi 1",
          r.status_code == 200 and isinstance(j, dict) and taxminan(j.get("pul_bekor_qilindi"), 300_000)
          and j.get("tolov_ochirildi") == 1, (r.status_code, j))
    check("R2 kelishilgan summa tiklandi (1 000 000)", taxminan(p2["agreed"], p0["agreed"]), (p0, p2))
    check("R2 manfiy to'lov o'chdi", p2["manfiy"] == [], p2)
    check("R2 loyiha 'To'langan' tiklandi", taxminan(p2["loyiha"], p0["loyiha"]), (p0, p2))
    check("R2 to'lov holati avvalgidek", p2["status"] == p0["status"], (p0, p2))
    check("R2 jurnal: to'lov o'chirilgani yozildi",
          pid is not None and any(a == "deleted" and "pul qaytarish bekor qilindi" in v for a, v in jurnal("payment", pid)),
          jurnal("payment", pid) if pid else None)
    _, rr2 = qaytar(O, i1, 30, to_stock=False)
    pul_qaytdi(rr2)
    p3 = pul(O)
    check("R3 qayta kiritib yana pul qaytdi: 700 000 va BITTA −300 000 (ikki marta EMAS)",
          taxminan(p3["agreed"], 700_000) and [t[1] for t in p3["manfiy"]] == [-300_000.0], p3)

    section("R4. Kelishilgan summa 0 da to'xtagan (max(0, …)) — AYNAN kamaygan qism tiklanadi")
    O, i1, _b = buyurtma("QO_R4", dona=10, narx=100_000)
    orm(lambda d: setattr(d.get(Order, O), "agreed_amount", 100_000))
    _, r4 = qaytar(O, i1, 20, to_stock=False)                  # 200 000 > 100 000
    pul_qaytdi(r4)
    check("R4 pul qaytdi: kelishilgan 0, delta 100 000", taxminan(pul(O)["agreed"], 0)
          and taxminan((ri(r4) or {}).get("delta"), 100_000), (pul(O), ri(r4)))
    r = ochir(r4)
    check("R4 o'chirish → 200, kelishilgan 100 000", r.status_code == 200 and taxminan(pul(O)["agreed"], 100_000),
          (r.status_code, xabar(r), pul(O)))

    section("R5. Yangilanishdan OLDIN belgilangan pul qaytarish — rad, hech narsa o'zgarmaydi")
    O, i1, _b = buyurtma("QO_R5", dona=10, narx=100_000)
    _, r5 = qaytar(O, i1, 30, to_stock=False)

    def eski_pul(d):
        z = d.get(ReturnItem, r5)
        z.is_refunded = True
        if hasattr(z, "refunded_at"):
            z.refunded_at = None
        o = d.get(Order, O)
        o.agreed_amount = 700_000
        d.add(Payment(order_id=O, amount=-300_000, notes="eski pul qaytarish"))
    orm(eski_pul)
    pa = pul(O)
    r = ochir(r5)
    check("R5 o'chirish → 400, sababda 'OLDIN'", r.status_code == 400 and "OLDIN" in xabar(r), (r.status_code, xabar(r)))
    check("R5 yozuv, kelishilgan summa va to'lov o'zgarmadi", ri(r5) is not None and pul(O) == pa, (pa, pul(O)))

    section("R6. Pul qaytarilgan, summa 0 — o'chiriladi")
    O, i1, _b = buyurtma("QO_R6", dona=10, narx=100_000)
    _, r6 = qaytar(O, i1, 5, to_stock=False)
    orm(lambda d: setattr(d.get(ReturnItem, r6), "refund_amount", 0))
    pul_qaytdi(r6)
    r = ochir(r6)
    check("R6 → 200, to'lovlar yo'q", r.status_code == 200 and pul(O)["tolovlar"] == [], (r.status_code, xabar(r), pul(O)))

    section("R7. Manfiy to'lov qo'lda o'chirilgan — qaytarishni o'chirish baribir kelishilgan summani tiklaydi")
    O, i1, _b = buyurtma("QO_R7", dona=10, narx=100_000)
    req(C, "post", "/api/payments", json={"order_id": O, "amount": 1_000_000, "payment_method": "naqd"})  # kech42: to'langan
    _, r7 = qaytar(O, i1, 30, to_stock=False)
    pul_qaytdi(r7)
    m = pul(O)["manfiy"]
    rr_ = req(C, "delete", f"/api/payments/{m[0][0]}") if m else None
    check("R7 manfiy to'lovni o'chirish → 200", rr_ is not None and rr_.status_code == 200,
          (rr_.status_code, rr_.text[:200]) if rr_ is not None else m)
    r = ochir(r7)
    check("R7 qaytarishni o'chirish → 200, kelishilgan 1 000 000", r.status_code == 200
          and taxminan(pul(O)["agreed"], 1_000_000), (r.status_code, xabar(r), pul(O)))

    section("R8. Ombor + pul: mahsulot sotilgan → rad, pul ham O'ZGARMAYDI (bir tranzaksiya)")
    O, i1, _b = buyurtma("QO_R8", dona=10, narx=100_000)
    _, r8 = qaytar(O, i1, 10)
    pul_qaytdi(r8)
    fid = fp_id_of(r8)
    req(C, "post", f"/api/finished/{fid}/reduce", json={"quantity": 4, "reason": "QO R8"})
    pa, fa = pul(O), fp(fid)
    r = ochir(r8)
    check("R8 → 400", r.status_code == 400, (r.status_code, xabar(r)))
    check("R8 pul, mahsulot, yozuv o'zgarmadi", pul(O) == pa and fp(fid) == fa and ri(r8) is not None,
          (pa, pul(O), fa, fp(fid)))

    section("R9. To'liq to'langan buyurtma: pul qaytdi → o'chirish → yana to'liq to'langan")
    O, i1, _b = buyurtma("QO_R9", dona=10, narx=100_000)
    rp = req(C, "post", "/api/payments", json={"order_id": O, "amount": 1_000_000, "payment_type": "final",
                                               "payment_method": "naqd"})
    check("R9 to'lov 1 000 000 → 200", rp.status_code == 200, (rp.status_code, rp.text[:200]))
    s0 = pul(O)
    _, r9 = qaytar(O, i1, 30, to_stock=False)
    pul_qaytdi(r9)
    r = ochir(r9)
    s2 = pul(O)
    check("R9 o'chirish → 200; holat, kelishilgan summa va to'lovlar avvalgidek",
          r.status_code == 200 and s2["status"] == s0["status"] and taxminan(s2["agreed"], s0["agreed"])
          and [t[1] for t in s2["tolovlar"]] == [t[1] for t in s0["tolovlar"]], (s0, s2))

    section("R10. Pul qaytarilgan qaytarishi bor buyurtmani o'chirish (PG da FK)")
    O, i1, _b = buyurtma("QO_R10", dona=10, narx=100_000)
    _, r10 = qaytar(O, i1, 10, to_stock=False)
    pul_qaytdi(r10)
    r = req(C, "delete", f"/api/orders/{O}")
    check("R10 buyurtmani o'chirish → 200 (500 EMAS)", r.status_code == 200, (r.status_code, r.text[:200]))


# ══════════════════════════════════════════════════════════════
# T. Tenant
# ══════════════════════════════════════════════════════════════
def bolim_tenant():
    section("T. Begona korxona")
    O, i1, _b = buyurtma("QO_T", dona=10, narx=100_000)
    _, rt = qaytar(O, i1, 10)
    r = ochir(rt, CB)
    check("T1 B korxona: o'chirish → 404", r.status_code == 404, (r.status_code, xabar(r)))
    r = pul_qaytdi(rt, CB)
    check("T1 B korxona: pul qaytdi → 404", r.status_code == 404, (r.status_code, xabar(r)))
    s = SessionLocal()
    try:
        try:
            v = crud.delete_return_item(s, rt, company_id=2)
        except Exception as e:                  # noqa: BLE001
            s.rollback()
            v = f"ISTISNO {type(e).__name__}"
        check("T2 crud.delete_return_item(company_id=2) → False", v is False, v)
        try:
            v = crud.mark_refunded(s, rt, refunded_by="B", company_id=2)
        except Exception as e:                  # noqa: BLE001
            s.rollback()
            v = f"ISTISNO {type(e).__name__}"
        check("T2 crud.mark_refunded(company_id=2) → None", v is None, v)
    finally:
        s.close()
    check("T2 yozuv va ombor o'zgarmadi", ri(rt) is not None and (ri(rt) or {}).get("is_refunded") is False
          and taxminan((fp(fp_id_of(rt)) or {}).get("qty"), 10, 1e-9), (ri(rt), fp(fp_id_of(rt))))
    OB, b1, _b = buyurtma("QO_TB", b=True)
    _, rtb = qaytar(OB, b1, 2, b=True)
    d = SessionLocal()
    xato = None
    try:
        d.add(Payment(order_id=O, amount=-1000, return_item_id=rtb))
        d.commit()
    except Exception as e:                      # noqa: BLE001
        xato = type(e).__name__
        d.rollback()
    finally:
        d.close()
    check("T3 ORM: 1-korxona to'lovi 2-korxona qaytarishiga → TenantMismatchError", xato == "TenantMismatchError", xato)


# ══════════════════════════════════════════════════════════════
# P. Parallel (faqat HAQIQIY PG)
# ══════════════════════════════════════════════════════════════
def _ikki(birinchi, ikkinchi, kech=0.15, sekin=0.4):
    """`birinchi` sessiyasining commit i `sekin` s kechiktiriladi; `ikkinchi`
    `kech` s keyin boshlanadi. Natija [n1, n2]."""
    natija = [None, None]
    bar = threading.Barrier(2)

    def a():
        s = SessionLocal()
        _asl = s.commit

        def _sekin():
            time.sleep(sekin)
            _asl()
        s.commit = _sekin
        try:
            try:
                bar.wait(timeout=30)
            except Exception:                   # noqa: BLE001
                pass
            try:
                natija[0] = birinchi(s)
            except Exception as e:              # noqa: BLE001
                s.rollback()
                natija[0] = f"ISTISNO {type(e).__name__}: {str(e)[:80]}"
        finally:
            s.close()

    def b():
        s = SessionLocal()
        try:
            try:
                bar.wait(timeout=30)
            except Exception:                   # noqa: BLE001
                pass
            time.sleep(kech)
            try:
                natija[1] = ikkinchi(s)
            except Exception as e:              # noqa: BLE001
                s.rollback()
                natija[1] = f"ISTISNO {type(e).__name__}: {str(e)[:80]}"
        finally:
            s.close()
    ts = [threading.Thread(target=a), threading.Thread(target=b)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=120)
    return natija


def bolim_parallel():
    if not PG_URL:
        print("  (P parallel — faqat PG rejimida)")
        return
    section("P. Parallel (commit 0.4 s kechiktiriladi, ikkinchi so'rov 0.15 s keyin)")
    yomon = []
    for k in range(3):
        O, i1, _b = buyurtma(f"QO_P1_{k}", dona=10, narx=100_000)
        # kech42 (24-band): to'langan — aks holda naqd (manfiy to'lov) umuman yozilmaydi va poyga ko'rinmaydi
        req(C, "post", "/api/payments", json={"order_id": O, "amount": 1_000_000, "payment_method": "naqd"})
        _, rp = qaytar(O, i1, 30, to_stock=False)
        n = _ikki(lambda s: bool(crud.mark_refunded(s, rp, refunded_by="P1a")),
                  lambda s: bool(crud.mark_refunded(s, rp, refunded_by="P1b")))
        p = pul(O)
        if not ([t[1] for t in p["manfiy"]] == [-300_000.0] and taxminan(p["agreed"], 700_000)):
            yomon.append((n, p))
    check("P1 ikki parallel 'pul qaytdi' (3 urinish): BITTA −300 000, kelishilgan 700 000", not yomon, str(yomon[:1]))

    yomon = []
    for k in range(3):
        O, i1, _b = buyurtma(f"QO_P2_{k}", dona=10, narx=100_000)
        # kech42 (24-band): to'langan — aks holda naqd (manfiy to'lov) umuman yozilmaydi va poyga ko'rinmaydi
        req(C, "post", "/api/payments", json={"order_id": O, "amount": 1_000_000, "payment_method": "naqd"})
        _, rp = qaytar(O, i1, 30, to_stock=False)
        n = _ikki(lambda s: crud.delete_return_item(s, rp),
                  lambda s: crud.mark_refunded(s, rp, refunded_by="P2"))
        p = pul(O)
        if not (ri(rp) is None and p["manfiy"] == [] and taxminan(p["agreed"], 1_000_000)):
            yomon.append((n, p, ri(rp)))
    check("P2 o'chirish + parallel 'pul qaytdi' (3 urinish): bog'lamsiz manfiy to'lov / kamaygan summa QOLMADI",
          not yomon, str(yomon[:1])[:400])

    yomon = []
    for k in range(3):
        nom = f"QO_P3_{k}"
        O, i1, _b = buyurtma(nom)
        _, rp = qaytar(O, i1, 10)
        fid = fp_id_of(rp)

        def sot(s, fid=fid):
            return crud.sell_finished_product(s, schemas.FinishedProductSaleCreate(
                finished_product_id=fid, quantity=3, unit_price=1000, confirm_below_cost=True),
                created_by="P3", company_id=1)
        n = _ikki(lambda s: crud.delete_return_item(s, rp), sot)
        d = SessionLocal()
        try:
            sotuv = d.query(FinishedProductSale).filter(FinishedProductSale.product_name == nom).count() \
                if hasattr(FinishedProductSale, "product_name") else None
        finally:
            d.close()
        f = fp(fid)
        bor = ri(rp) is not None
        togri = ((not bor) and f is None and not sotuv) or (bor and f is not None and taxminan(f["qty"], 7, 1e-9) and sotuv == 1)
        if not togri:
            yomon.append((n, bor, f, sotuv))
    check("P3 qaytarishni o'chirish + parallel sotuv (3 urinish): holat izchil (yoki o'chdi va sotuv yo'q, yoki qoldi va 7)",
          not yomon, str(yomon[:1])[:400])

    yomon = []
    for k in range(3):
        nom = f"QO_P4_{k}"
        O1, a1, _b = buyurtma(nom)
        O2, a2, _b = buyurtma(nom, prj=PRJ2_ID)
        _, r1 = qaytar(O1, a1, 10)
        fid = fp_id_of(r1)
        nm = detal_nomi(a2)

        def sot(s, fid=fid):
            return crud.sell_finished_product(s, schemas.FinishedProductSaleCreate(
                finished_product_id=fid, quantity=3, unit_price=1000, confirm_below_cost=True),
                created_by="P4", company_id=1)

        def yangi(s, O2=O2, a2=a2, nm=nm):
            return crud.create_return_item(s, schemas.ReturnItemCreate(
                order_id=O2, order_item_id=a2, item_name=nm, quantity=4, unit="metr", reason="Ortiqcha"),
                company_id=1)
        n = _ikki(sot, yangi)
        f = fp(fid) or {}
        if not taxminan(f.get("qty"), 11, 1e-9):
            yomon.append((n, f))
    check("P4 sotuv + parallel yangi qaytarish shu mahsulotga (3 urinish): 10 − 3 + 4 = 11 (yo'qolgan yangilanish YO'Q)",
          not yomon, str(yomon[:1])[:400])


# ══════════════════════════════════════════════════════════════
# S. Statik — tartib va to'siqlar
# ══════════════════════════════════════════════════════════════
def tartibda(src, *qismlar):
    p = 0
    for q in qismlar:
        k = src.find(q, p)
        if k < 0:
            return False
        p = k + len(q)
    return True


def _fn_src(fayl, nom):
    s = open(os.path.join(ROOT, fayl), encoding="utf-8").read()
    try:
        t = ast.parse(s)
    except SyntaxError:
        return ""
    for n in ast.walk(t):
        if isinstance(n, ast.FunctionDef) and n.name == nom:
            return ast.get_source_segment(s, n) or ""
    return ""


def bolim_statik():
    section("S. Statik")
    cr = _fn_src("crud.py", "create_return_item")
    check("S1 create_return_item: add_returned_to_stock(..., commit=False, natija=...)",
          tartibda(cr, "add_returned_to_stock(", "commit=False", "natija=") and "item.stock_qty" in cr)
    ad = _fn_src("crud.py", "add_returned_to_stock")
    check("S2 add_returned_to_stock: mavjud mahsulot qatori FOR UPDATE bilan o'qiladi",
          "existing = _rq.with_for_update().first()" in ad)
    check("S2 add_returned_to_stock: yangi mahsulot READY", "production_status=_PS_ret.READY" in ad)
    dr = _fn_src("crud.py", "delete_return_item")
    check("S3 delete_return_item: flush → qulf (101) → expire_all → qayta o'qish",
          tartibda(dr, "db.flush()", "_pul_qulfi(db, 101", "db.expire_all()", "item = db.query(ReturnItem)"))
    check("S3 delete_return_item: HAMMA rad (raise) o'zgartirishdan (db.delete) OLDIN",
          dr.rfind("raise ValueError") >= 0 and dr.find("db.delete(") > dr.rfind("raise ValueError"))
    check("S3 delete_return_item: log_activity ISHLATILMAYDI (u commit qiladi)", "log_activity(" not in dr and dr != "")
    check("S3 delete_return_item: mahsulot FOR UPDATE (lock=True)", "lock=True" in dr)
    mr = _fn_src("crud.py", "mark_refunded")
    check("S4 mark_refunded: qulf → qayta o'qish → to'lov bog'lami",
          tartibda(mr, "_pul_qulfi(db, 101", "db.expire_all()", "return_item_id=item.id", "refunded_at"))
    df = _fn_src("crud.py", "delete_finished_product")
    check("S5 delete_finished_product: 'jarayonda' tarmog'i `_fp_tayyormi` bilan (K40-1)",
          "if not _fp_tayyormi(fp):" in df and "if fp.production_status == _PS.IN_PROGRESS:" not in df)
    check("S5 delete_finished_product: qaytarish bog'lami ikkala tarmoqda uziladi",
          df.count("db.query(ReturnItem).filter(ReturnItem.finished_product_id == fp_id") == 2)
    mn = _fn_src("main.py", "api_delete_finished")
    check("S6 api_delete_finished: `crud._fp_tayyormi` bilan qoldiq tekshiruvi",
          "crud._fp_tayyormi(fp) and float(fp.quantity or 0) > 0.001" in mn)
    md = _fn_src("main.py", "api_delete_return")
    check("S6 api_delete_return: ValueError → rollback → 400",
          tartibda(md, "except ValueError", "db.rollback()", "status_code=400"))
    mm = _fn_src("main.py", "api_mark_refunded")
    check("S6 api_mark_refunded: korxona crud ga ham beriladi (ikki to'siq)", "company_id=auth.company_id_of" in mm)


def kumulyativ():
    section("K. 5xx yo'q")
    for u in ("/api/returns", "/api/returns/stats", "/returns", "/finished", "/api/finished?show_all=true",
              "/api/payments"):
        r = req(C, "get", u)
        check(f"K {u} 200", r.status_code == 200, r.status_code)


for _fn in (bolim_migratsiya, bolim_ombor, bolim_birlashish, bolim_ishlatilgan, bolim_mahsulot_ochirish,
            bolim_boshqa, bolim_pul, bolim_tenant, bolim_parallel, bolim_statik, kumulyativ):
    try:
        _fn()
    except Exception as _e:                    # noqa: BLE001
        check(f"{_fn.__name__}: kutilmagan istisno", False, f"{type(_e).__name__}: {_e}")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
