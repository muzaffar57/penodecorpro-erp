#!/usr/bin/env python3
"""
test_tm_qulf.py — 5-bo'lim 68-band + K64-1 + K65-1 darvozasi (kech65, 2026-09-25):
tayyor mahsulot (TM) qatorini o'zgartiradigan amallar orasidagi poygalar.

NIMA UCHUN KERAK (asl kod `6a5ee26` da HAQIQIY PostgreSQL 16 da O'LCHANGAN —
`work/probe68.py`, `work/probe65b.py`, har holat 3 / 3 urinishda takrorlandi)
--------------------------------------------------------------------
  S1b  bir buyurtmani (TM detali + penoplast detali) ikki joydan tahrirlash
       (TM 10 → 15 || → 18) — TM 87 (to'g'risi 82): 5 m YO'QOLARDI.
  S2   TM sotuvi 5 || buyurtma tahriri 10 → 15 — TM 85 (to'g'risi 80): sotuv yo'qolardi.
  S6   TM sotuvi 5 || buyurtmani o'chirish (TM +10) — TM 100 (to'g'risi 95) (K64-1).
  S5b  tahrir TM bosqichida istisno bersa — YARIM saqlanardi (detal va penoplast
       o'zgargan, TM o'zgarmagan).
  S7   savatcha [B, A] || shu TM lar bilan buyurtma tahriri — deadlock (40P01),
       tahrir yiqilardi (K65-1).
  S8   savatcha [A, B] || savatcha [B, A] — ikkinchisi "Xato yuz berdi: ... deadlock".
  S10  TM sotuvi 5 || TM 7 li qoralamani jarayonga olish — TM 93 (to'g'risi 88).
  S11  bir qoralamani ikki joydan (ikki marta bosib) jarayonga olish — IKKALASI ham
       "jarayonga olindi", penoplast IKKI MARTA yechilardi (K65-2, `work/probe65c.py`).
SABAB: `_fp_for_tenant` TM ni QULFSIZ o'qiydi, chaqiruvchilar esa MUTLAQ qiymat
yozadi; `update_order_full` 6-qadamida `adjust_inventory_diff` standart `commit=True`
qulfni (101, buyurtma) muddatidan oldin bo'shatib, tahrirni ikki tranzaksiyaga
bo'lardi; savatcha qatorlarni savatcha TARTIBIDA qulflardi; `activate_draft_order`
holatni qulfsiz o'qir, `deduct_inventory_for_order` esa o'rtada commit qilardi.

TUZATISH (kech64 / kech65): `crud._fp_qulf` — flush → id TARTIBIDA
`SELECT ... FOR UPDATE` + `populate_existing` (korxona filtri bilan); u
`_take_finished_for_order`, `_return_finished_for_order`, `_adjust_finished_diff`
va `sell_finished_products_batch` boshida chaqiriladi; 6-qadam
`adjust_inventory_diff` / "Loy sotish" `deduct` / `return` — `commit=False`,
bitta `db.commit()`. `activate_draft_order` — flush → qulf (101, buyurtma) →
expire_all → korxona filtrli qayta o'qish → holat tekshiruvi; penoplast / loy
yechish `commit=False`, bitta `db.commit()` (K65-2).

REJIMLAR: odatiy SQLite (statik + birlik + ketma-ket xulq); `PG_URL` berilsa —
YANGI PG bazasi, qo'shimcha ravishda qulf isboti (NOWAIT) va PARALLEL problar.
    python3 tools/test_tm_qulf.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tm_qulf.py
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
PG_BAZA = "tm_qulf_test"
_DB = os.path.join(tempfile.gettempdir(), "tm_qulf_test.db")

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

from sqlalchemy import event, text                 # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, FinishedProduct, Order, OrderItem, StockSource, ProductionStatus,
)
from production_models import Company              # noqa: E402
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


def kod(src):
    """Faqat KOD qatorlari — izoh qatorlari (`#` bilan boshlanadigan) olib tashlanadi."""
    return "\n".join(q for q in src.splitlines() if not q.strip().startswith("#"))


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
    auth.create_user(_db, "TQ_admin", "Parol123!", UserRole.ADMIN, "TQ Admin", company_id=1)
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="TQ Korxona B"))
    _db.commit()
PRJ = Project(company_id=1, client_name="TQ Mijoz", project_name="TQ loyiha", total_budget=0, total_paid=0)
PENO_OBJ = Inventory(company_id=1, item_name="TQ PENO", unit="blok", stock_quantity=100000, min_stock=0,
                     is_penoplast=True, volume_per_unit=1, price_per_unit=500000)
_db.add_all([PRJ, PENO_OBJ])
_db.commit()
PRJ_ID, PENO = PRJ.id, PENO_OBJ.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "TQ_admin", "password": "Parol123!"},
          follow_redirects=False)
if _lr.status_code != 302:
    print(f"LOGIN BO'LMADI: {_lr.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom(bosh):
    """Har detal / buyurtmaga YANGI nom (8 s takror-yuborish himoyasi birlashtirmasin)."""
    _n[0] += 1
    return f"TQ {bosh}{_n[0]}"


def yangi_tm(miqdor=100.0, cid=1):
    """YANGI tayyor mahsulot (profil, metr, 1 metr tan narxi 1 000 — barqaror)."""
    s = SessionLocal()
    try:
        f = FinishedProduct(company_id=cid, name=nom("TM"), category="profil", is_coated=False,
                            quantity=miqdor, produced_quantity=miqdor, unit="metr", unit_price=0,
                            cost_price=miqdor * 1000, unit_cost_stable=1000, source=StockSource.PRODUCED,
                            penoplast_id=PENO if cid == 1 else None, unit_volume_m3=0.01,
                            production_status=ProductionStatus.READY)
        s.add(f)
        s.commit()
        return f.id
    finally:
        s.close()


def detal(nomi, uzunlik, fid=None):
    d = {"name": nomi, "category": "profil", "width": 20, "thickness": 10, "length": uzunlik,
         "quantity": 1, "unit_price": 20000, "is_coated": False, "penoplast_id": PENO}
    if fid:
        d["finished_product_id"] = fid
    return d


def tana(*detallar):
    return {"project_id": PRJ_ID, "order_type": "product", "loy_kg": 0, "items": list(detallar)}


def yangi_buyurtma(*detallar):
    r = req(C, "post", "/api/orders", json=tana(*detallar), params={"confirm_shortage": "true"})
    return r.status_code, (js(r) or {}).get("id")


def yangi_qoralama(*detallar):
    t = tana(*detallar)
    t["is_draft"] = True
    r = req(C, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
    return r.status_code, (js(r) or {}).get("id")


def holat_q(fid, oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        return {"tm": round(float(s.get(FinishedProduct, fid).quantity), 4) if fid else None,
                "peno": round(float(s.get(Inventory, PENO).stock_quantity), 4),
                "status": o.status.value if o else None}
    finally:
        s.close()


def faollashtir(oid):
    return lambda s: crud.activate_draft_order(s, oid)


def holat(fids, oid=None):
    s = SessionLocal()
    try:
        h = {"tm": {}, "cost": {}}
        for f in fids:
            fp = s.get(FinishedProduct, f)
            h["tm"][f] = round(float(fp.quantity or 0), 4) if fp else None
            h["cost"][f] = round(float(fp.cost_price or 0), 2) if fp else None
        if oid:
            its = s.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()
            h["detal"] = [round(float(i.length or 0), 4) for i in its]
        h["peno"] = round(float(s.get(Inventory, PENO).stock_quantity), 4)
        return h
    finally:
        s.close()


def tahrir(oid, *detallar):
    return lambda s: crud.update_order_full(s, oid, schemas.OrderCreate(**tana(*detallar)),
                                            confirm_shortage=True)


def sotuv(fid, miqdor):
    return lambda s: crud.sell_finished_product(
        s, schemas.FinishedProductSaleCreate(finished_product_id=fid, quantity=miqdor, unit_price=1000),
        created_by="tq", company_id=1)


def savat(juftlar):
    return lambda s: crud.sell_finished_products_batch(s, schemas.FinishedProductSaleBatchCreate(
        items=[{"finished_product_id": f, "quantity": q, "unit_price": 1000} for f, q in juftlar]),
        created_by="tq", company_id=1)


def yarat(*detallar):
    return lambda s: crud.create_order(s, schemas.OrderCreate(**tana(*detallar)), company_id=1)


# SQL kuzatuvchi: tayyor mahsulot qatorini id bo'yicha o'qiydigan so'rovlar (birlik bo'limi)
# va "qulfdan keyin sekin" (parallel bo'lim) — oqimga bog'langan bayroqlar bilan.
_tl = threading.local()
_KUZAT = []


def _birinchi_param(p):
    if isinstance(p, dict):
        for k, v in p.items():
            if str(k).startswith("id"):
                return v
        return None
    try:
        return list(p)[0]
    except Exception:                      # noqa: BLE001
        return None


def _kuzatuvchi(conn, cursor, statement, parameters, context, executemany):
    st = str(statement)
    if getattr(_tl, "kuzat", False) and "FROM finished_products" in st and "finished_products.id =" in st:
        _KUZAT.append((st, _birinchi_param(parameters)))
    if (getattr(_tl, "qulf_sekin", False) and not getattr(_tl, "qulf_bir", False)
            and "FOR UPDATE" in st and "finished_products" in st):
        _tl.qulf_bir = True
        time.sleep(0.4)


event.listen(engine, "after_cursor_execute", _kuzatuvchi)


# ══════════════════════════════════════════════════════════════
# 1. STATIK — qulf va bitta tranzaksiya tartibi
# ══════════════════════════════════════════════════════════════
def bolim_statik():
    section("1. Statik: _fp_qulf va uning chaqiruv joylari, 6-qadam commit=False")
    q = kod(manba(crud, "_fp_qulf"))
    check("_fp_qulf: korxona yo'q → chiqish → sorted → flush → korxona filtri → populate_existing → FOR UPDATE",
          tartibda(q, "if company_id is None:", "sorted(", "db.flush()", "FinishedProduct.company_id == company_id",
                   ".populate_existing()", ".with_for_update()"), q[:200])
    t = kod(manba(crud, "_take_finished_for_order"))
    check("_take_finished_for_order: _fp_qulf TM o'qilishidan (_fp_for_tenant) OLDIN",
          tartibda(t, "_fp_qulf(db, ", "for it in order.items:", "fp = _fp_for_tenant(db, fpid, cid)"))
    r = kod(manba(crud, "_return_finished_for_order"))
    check("_return_finished_for_order: _fp_qulf TM o'qilishidan OLDIN",
          tartibda(r, "_fp_qulf(db, ", "for it in order.items:", "fp = _fp_for_tenant(db, fpid, cid)"))
    a = kod(manba(crud, "_adjust_finished_diff"))
    check("_adjust_finished_diff: _fp_qulf (eski + yangi TM) → sorted sikl → TM o'qish",
          tartibda(a, "_fp_qulf(db, set(old_g) | set(new_g), company_id)",
                   "for fpid in sorted(set(old_g) | set(new_g)):", "fp = _fp_for_tenant(db, fpid, company_id)"))
    b = kod(manba(crud, "sell_finished_products_batch"))
    check("sell_finished_products_batch: _fp_qulf (savatchadagi HAMMA TM) qator-qator qulfdan OLDIN",
          tartibda(b, "_fp_qulf(db, [getattr(_it, 'finished_product_id', None) for _it in data.items], company_id)",
                   "for item in data.items:",
                   "get_finished_product(db, item.finished_product_id, company_id, lock=True)"))
    f = manba(crud, "update_order_full")
    i6 = f.find("# 6) Omborni farq")
    i7 = f.find("# 7) To'lov holatini")
    seg = kod(f[i6:i7]) if 0 <= i6 < i7 else ""
    check("update_order_full 6-qadam: adjust_inventory_diff(commit=False) → TM farqi → loy sotish (commit=False) → bitta commit",
          tartibda(seg, "services.adjust_inventory_diff(", "company_id=order.company_id, commit=False)",
                   "_adjust_finished_diff(", "services.deduct_loy_ingredients(db, order, diff, recipe_id=rid,",
                   "commit=False)", "services.return_loy_ingredients(db, order, abs(diff), recipe_id=rid,",
                   "commit=False)", "db.commit()"), seg[:300])
    check("update_order_full 6-qadam: kod qatorlarida commit=False AYNAN 3, db.commit() AYNAN 1",
          seg.count("commit=False)") == 3 and seg.count("db.commit()") == 1,
          f"{seg.count('commit=False)')} / {seg.count('db.commit()')}")
    ad = kod(manba(crud, "activate_draft_order"))
    check("activate_draft_order: flush → qulf → expire_all → korxona filtrli qayta o'qish → holat → yechish → bitta commit",
          tartibda(ad, "db.flush()", "_pul_qulfi(db, 101, order.id)", "db.expire_all()",
                   "Order.company_id == _cid_q", "order = _oq.first()", "if order.status != OrderStatus.DRAFT:",
                   "deduct_inventory_for_order(db, order, commit=False)", "_take_finished_for_order(db, order)",
                   "db.commit()"), ad[:200])
    check("activate_draft_order: kod qatorlarida commit=False AYNAN 3, db.commit() AYNAN 1",
          ad.count("commit=False)") == 3 and ad.count("db.commit()") == 1,
          f"{ad.count('commit=False)')} / {ad.count('db.commit()')}")
    di = kod(manba(services, "deduct_inventory_for_order"))
    check("deduct_inventory_for_order: `commit` parametri, False bo'lsa faqat flush",
          "commit: bool = True" in di and tartibda(di, "if commit:", "db.commit()", "else:", "db.flush()"))


# ══════════════════════════════════════════════════════════════
# 2. BIRLIK — _fp_qulf xulqi (ikkala rejimda; qulf isboti — faqat PG)
# ══════════════════════════════════════════════════════════════
def _qulfda(fid):
    """Boshqa sessiya qatorni NOWAIT bilan qulflay oladimi (faqat PG). True — band."""
    s2 = SessionLocal()
    try:
        try:
            s2.execute(text("SELECT id FROM finished_products WHERE id = :i FOR UPDATE NOWAIT"),
                       {"i": fid}).fetchall()
            return False
        except Exception as e:             # noqa: BLE001
            return "55P03" in str(e) or "could not obtain lock" in str(e)
    finally:
        try:
            s2.rollback()
        except Exception:                  # noqa: BLE001
            pass
        s2.close()


def bolim_birlik():
    section("2. Birlik: _fp_qulf")
    fq = getattr(crud, "_fp_qulf", None)
    check("crud._fp_qulf mavjud", callable(fq))
    if not callable(fq):
        for nomi in ("korxona yo'q → TM so'rovi yo'q", "id lar TARTIBDA, takror / bo'sh id siz",
                     "populate_existing: boshqa sessiya yozgan qiymat o'qiladi",
                     "flush: sessiyadagi yozilmagan o'zgarish yo'qolmaydi",
                     "begona korxona TM i: istisno yo'q, qiymati o'zgarmaydi"):
            check(nomi, False, "_fp_qulf yo'q")
        if PG_URL:
            for nomi in ("PG: har so'rov FOR UPDATE", "PG: o'z TM i qulflandi (NOWAIT band)", "PG: korxona yo'q → qulf yo'q",
                         "PG: begona korxona TM i qulflanmadi"):
                check(nomi, False, "_fp_qulf yo'q")
        return
    A, B = yangi_tm(), yangi_tm()
    F2 = yangi_tm(cid=2)

    s = SessionLocal()
    try:
        _KUZAT.clear()
        _tl.kuzat = True
        try:
            fq(s, [B, A], None)
        finally:
            _tl.kuzat = False
        check("korxona yo'q → TM so'rovi yo'q (eski chaqiruv xulqi)", _KUZAT == [], str(_KUZAT[:2]))
        _KUZAT.clear()
        _tl.kuzat = True
        try:
            fq(s, [B, None, A, A, 0], 1)
        finally:
            _tl.kuzat = False
        ids = [p for _, p in _KUZAT]
        check("id lar TARTIBDA, takror / bo'sh id siz: [A, B]", ids == [A, B], f"{ids} A={A} B={B}")
        if PG_URL:
            check("PG: har so'rov FOR UPDATE", bool(_KUZAT) and all("FOR UPDATE" in st for st, _ in _KUZAT),
                  str([st[-60:] for st, _ in _KUZAT]))
    finally:
        s.rollback()
        s.close()

    s1 = SessionLocal()
    try:
        fp1 = s1.get(FinishedProduct, A)
        _ = float(fp1.quantity)
        s2 = SessionLocal()
        try:
            s2.get(FinishedProduct, A).quantity = 70
            s2.commit()
        finally:
            s2.close()
        fq(s1, [A], 1)
        check("populate_existing: boshqa sessiya yozgan qiymat (70) o'qiladi", float(fp1.quantity) == 70.0,
              str(fp1.quantity))
    finally:
        s1.rollback()
        s1.close()

    s1 = SessionLocal()
    try:
        fp1 = s1.get(FinishedProduct, B)
        fp1.quantity = 55
        fq(s1, [B], 1)
        check("flush: sessiyadagi yozilmagan o'zgarish (55) yo'qolmaydi", float(fp1.quantity) == 55.0,
              str(fp1.quantity))
    finally:
        s1.rollback()
        s1.close()

    s1 = SessionLocal()
    try:
        xato = None
        try:
            fq(s1, [F2], 1)
        except Exception as e:             # noqa: BLE001
            xato = f"{type(e).__name__}: {e}"
        fp2 = s1.get(FinishedProduct, F2)
        check("begona korxona TM i: istisno yo'q, qiymati o'zgarmaydi (100)",
              xato is None and float(fp2.quantity) == 100.0, f"{xato} {fp2.quantity}")
    finally:
        s1.rollback()
        s1.close()

    if PG_URL:
        s1 = SessionLocal()
        try:
            fq(s1, [A], 1)
            check("PG: o'z TM i qulflandi (NOWAIT band)", _qulfda(A) is True)
        finally:
            s1.rollback()
            s1.close()
        s1 = SessionLocal()
        try:
            fq(s1, [A], None)
            check("PG: korxona yo'q → qulf yo'q", _qulfda(A) is False)
        finally:
            s1.rollback()
            s1.close()
        s1 = SessionLocal()
        try:
            fq(s1, [F2], 1)
            check("PG: begona korxona TM i qulflanmadi", _qulfda(F2) is False)
        finally:
            s1.rollback()
            s1.close()


# ══════════════════════════════════════════════════════════════
# 3. Ketma-ket xulq (ikkala rejimda) — tuzatish oddiy oqimni buzmagan
# ══════════════════════════════════════════════════════════════
def bolim_ketma_ket():
    section("3. Ketma-ket xulq (API)")
    F = yangi_tm()
    a = nom("D")
    st, O = yangi_buyurtma(detal(a, 10, F))
    h = holat([F], O)
    check("TM dan buyurtma 10 m → 200, TM 90, tan narx 90 000", st == 200 and h["tm"][F] == 90.0
          and h["cost"][F] == 90000.0, f"{st} {h}")
    r = req(C, "put", f"/api/orders/{O}", json=tana(detal(a, 15, F)), params={"confirm_shortage": "true"})
    h = holat([F], O)
    check("tahrir 10 → 15 → 200, TM 85, tan narx 85 000, detal 15", r.status_code == 200
          and h["tm"][F] == 85.0 and h["cost"][F] == 85000.0 and h["detal"] == [15.0],
          f"{r.status_code} {getattr(r, 'text', '')[:160]} {h}")
    r = req(C, "put", f"/api/orders/{O}", json=tana(detal(a, 8, F)), params={"confirm_shortage": "true"})
    h = holat([F], O)
    check("tahrir 15 → 8 → 200, TM 92 (7 m qaytdi), tan narx 92 000", r.status_code == 200
          and h["tm"][F] == 92.0 and h["cost"][F] == 92000.0, f"{r.status_code} {h}")
    r = req(C, "delete", f"/api/orders/{O}")
    h = holat([F])
    check("buyurtmani o'chirish → 200, TM 100, tan narx 100 000", r.status_code == 200
          and h["tm"][F] == 100.0 and h["cost"][F] == 100000.0, f"{r.status_code} {h}")

    F = yangi_tm()
    a, b = nom("T"), nom("P")
    st, O = yangi_buyurtma(detal(a, 10, F), detal(b, 100))
    h0 = holat([F], O)
    r = req(C, "put", f"/api/orders/{O}", json=tana(detal(a, 15, F), detal(b, 120)),
            params={"confirm_shortage": "true"})
    h = holat([F], O)
    check("aralash buyurtma (TM 10 + penoplast 100) → 15 / 120: TM 85, penoplast 0.2 blok ko'p yechildi",
          st == 200 and r.status_code == 200 and h["tm"][F] == 85.0 and h["detal"] == [15.0, 120.0]
          and abs(h0["peno"] - h["peno"] - 0.2) < 1e-6, f"{st} {r.status_code} {h0} {h}")

    F = yangi_tm()
    a, b = nom("T"), nom("P")
    st, O = yangi_buyurtma(detal(a, 10, F), detal(b, 100))
    h0 = holat([F], O)
    _asl = crud._adjust_finished_diff

    def _yiqil(*x, **k):
        raise RuntimeError("TQ sun'iy xato (TM bosqichi)")
    crud._adjust_finished_diff = _yiqil
    s = SessionLocal()
    try:
        try:
            crud.update_order_full(s, O, schemas.OrderCreate(**tana(detal(a, 15, F), detal(b, 120))),
                                   confirm_shortage=True)
            javob = "istisno YO'Q"
        except Exception as e:             # noqa: BLE001
            s.rollback()
            javob = f"ISTISNO {type(e).__name__}: {e}"
    finally:
        s.close()
        crud._adjust_finished_diff = _asl
    h = holat([F], O)
    check("S5b atomarlik: TM bosqichi istisno bersa tahrir HECH NARSA saqlamaydi (detal, penoplast, TM)",
          "ISTISNO" in javob and h == h0, f"{javob[:120]} {h0} {h}")

    A, B = yangi_tm(), yangi_tm()
    r = req(C, "post", "/api/finished/sell-batch", json={"items": [
        {"finished_product_id": B, "quantity": 5, "unit_price": 1000},
        {"finished_product_id": A, "quantity": 5, "unit_price": 1000}]})
    h = holat([A, B])
    check("savatcha [B 5, A 5] → 200, A 95, B 95", r.status_code == 200 and h["tm"] == {A: 95.0, B: 95.0},
          f"{r.status_code} {getattr(r, 'text', '')[:200]} {h}")
    F2 = yangi_tm(cid=2)
    r = req(C, "post", "/api/finished/sell-batch", json={"items": [
        {"finished_product_id": A, "quantity": 5, "unit_price": 1000},
        {"finished_product_id": F2, "quantity": 5, "unit_price": 1000}]})
    h = holat([A, B, F2])
    check("savatchada begona korxona TM i → 400 'topilmadi', hech narsa yechilmadi",
          r.status_code == 400 and "topilmadi" in str(js(r)) and h["tm"] == {A: 95.0, B: 95.0, F2: 100.0},
          f"{r.status_code} {getattr(r, 'text', '')[:200]} {h}")
    r = req(C, "post", "/api/finished/sell-batch", json={"items": [
        {"finished_product_id": A, "quantity": 60, "unit_price": 1000},
        {"finished_product_id": A, "quantity": 50, "unit_price": 1000}]})
    h = holat([A])
    check("savatchada bir TM ikki qatorda (60 + 50 > 95) → 400, A 95", r.status_code == 400
          and h["tm"] == {A: 95.0}, f"{r.status_code} {getattr(r, 'text', '')[:200]} {h}")

    F = yangi_tm()
    st, O = yangi_qoralama(detal(nom("T"), 7, F), detal(nom("P"), 100))
    h0 = holat_q(F, O)
    check("qoralama (TM 7 + penoplast 100) → 200, TM va penoplast tegilmadi", st == 200
          and h0["tm"] == 100.0 and h0["status"] == "draft", f"{st} {h0}")
    r = req(C, "post", f"/api/orders/{O}/activate")
    h = holat_q(F, O)
    check("jarayonga olish → 200: TM 93, penoplast 1.0 blok yechildi, holat in_progress", r.status_code == 200
          and h["tm"] == 93.0 and abs(h0["peno"] - h["peno"] - 1.0) < 1e-6 and h["status"] == "in_progress",
          f"{r.status_code} {getattr(r, 'text', '')[:160]} {h0} {h}")
    r = req(C, "post", f"/api/orders/{O}/activate")
    check("ikkinchi marta jarayonga olish → 400 'qoralama emas', hech narsa yechilmadi", r.status_code == 400
          and "qoralama emas" in str(js(r)) and holat_q(F, O) == h, f"{r.status_code} {holat_q(F, O)}")

    F = yangi_tm()
    st, O = yangi_qoralama(detal(nom("T"), 7, F), detal(nom("P"), 100))
    h0 = holat_q(F, O)
    _asl_t = crud._take_finished_for_order

    def _yiqil_t(*x, **k):
        raise RuntimeError("TQ sun'iy xato (TM yechish)")
    crud._take_finished_for_order = _yiqil_t
    s = SessionLocal()
    try:
        try:
            crud.activate_draft_order(s, O)
            javob = "istisno YO'Q"
        except Exception as e:             # noqa: BLE001
            s.rollback()
            javob = f"ISTISNO {type(e).__name__}: {e}"
    finally:
        s.close()
        crud._take_finished_for_order = _asl_t
    h = holat_q(F, O)
    check("jarayonga olish atomar: TM bosqichi istisno bersa penoplast yechilmaydi, holat draft",
          "ISTISNO" in javob and h == h0, f"{javob[:120]} {h0} {h}")


# ══════════════════════════════════════════════════════════════
# 4. PARALLEL (faqat HAQIQIY PG)
# ══════════════════════════════════════════════════════════════
def poyga(birinchi, ikkinchi, tur="commit"):
    """birinchi(s) — `commit` 0.4 s kechiktiriladi (tur="commit") yoki birinchi TM qatori
    qulflangach 0.4 s kutadi (tur="qulf"); ikkinchi(s) 0.15 s keyin boshlanadi."""
    nat = [None, None]
    bar = threading.Barrier(2)

    def t(k, fn, kech):
        s = SessionLocal()
        _tl.qulf_sekin = bool(kech and tur == "qulf")
        _tl.qulf_bir = False
        if kech and tur == "commit":
            asl = s.commit

            def _sekin():
                time.sleep(0.4)
                asl()
            s.commit = _sekin
        try:
            try:
                bar.wait(timeout=30)
            except Exception:                   # noqa: BLE001
                pass
            if not kech:
                time.sleep(0.15)
            try:
                r = fn(s)
                nat[k] = ({kk: r.get(kk) for kk in ("success", "message")} if isinstance(r, dict)
                          else (r if isinstance(r, int) else str(r)[:200]))
            except Exception as e:              # noqa: BLE001
                try:
                    s.rollback()
                except Exception:               # noqa: BLE001
                    pass
                nat[k] = f"ISTISNO {type(e).__name__}: {str(e)[:200]}"
        finally:
            _tl.qulf_sekin = False
            s.close()
    ts = [threading.Thread(target=t, args=(0, birinchi, True)),
          threading.Thread(target=t, args=(1, ikkinchi, False))]
    for x in ts:
        x.start()
    for x in ts:
        x.join(timeout=120)
    return nat


def _ok(x):
    return isinstance(x, dict) and x.get("success") is True


def bolim_parallel():
    section("4. Parallel (HAQIQIY PG, har holat 3 urinish)")
    if not PG_URL:
        print("  (faqat PG rejimida)")
        return
    yomon = {k: [] for k in ("S1b", "S2", "S2b", "S6", "S7", "S8", "S9", "S10", "S11", "S3", "S4c")}
    for _u in range(3):
        F = yangi_tm()
        a, b = nom("T"), nom("P")
        st, O = yangi_buyurtma(detal(a, 10, F), detal(b, 100))
        n = poyga(tahrir(O, detal(a, 15, F), detal(b, 120)), tahrir(O, detal(a, 18, F), detal(b, 130)))
        h = holat([F], O)
        if not (h["tm"][F] == 82.0 and h["cost"][F] == 82000.0 and h["detal"] == [18.0, 130.0]):
            yomon["S1b"].append((st, n, h))

        F = yangi_tm()
        a = nom("D")
        st, O = yangi_buyurtma(detal(a, 10, F))
        n = poyga(sotuv(F, 5), tahrir(O, detal(a, 15, F)))
        h = holat([F], O)
        if not (h["tm"][F] == 80.0 and h["cost"][F] == 80000.0 and _ok(n[0]) and _ok(n[1])):
            yomon["S2"].append((st, n, h))

        F = yangi_tm()
        a, b = nom("T"), nom("P")
        st, O = yangi_buyurtma(detal(a, 10, F), detal(b, 100))
        n = poyga(sotuv(F, 5), tahrir(O, detal(a, 15, F), detal(b, 120)))
        h = holat([F], O)
        if not (h["tm"][F] == 80.0 and h["detal"] == [15.0, 120.0] and _ok(n[0]) and _ok(n[1])):
            yomon["S2b"].append((st, n, h))

        F = yangi_tm()
        st, O = yangi_buyurtma(detal(nom("D"), 10, F))
        n = poyga(sotuv(F, 5), lambda s, o=O: req(C, "delete", f"/api/orders/{o}").status_code)
        h = holat([F])
        if not (h["tm"][F] == 95.0 and h["cost"][F] == 95000.0 and _ok(n[0]) and n[1] == 200):
            yomon["S6"].append((st, n, h))

        A, B = yangi_tm(), yangi_tm()
        a, b = nom("A"), nom("B")
        st, O = yangi_buyurtma(detal(a, 10, A), detal(b, 10, B))
        n = poyga(savat([(B, 5), (A, 5)]), tahrir(O, detal(a, 15, A), detal(b, 15, B)), tur="qulf")
        h = holat([A, B], O)
        if not (h["tm"] == {A: 80.0, B: 80.0} and _ok(n[0]) and _ok(n[1])):
            yomon["S7"].append((st, n, h))

        A, B = yangi_tm(), yangi_tm()
        n = poyga(savat([(A, 5), (B, 5)]), savat([(B, 3), (A, 3)]), tur="qulf")
        h = holat([A, B])
        if not (h["tm"] == {A: 92.0, B: 92.0} and _ok(n[0]) and _ok(n[1])):
            yomon["S8"].append((n, h))

        A, B = yangi_tm(), yangi_tm()
        x1, x2, y1, y2 = nom("X"), nom("X"), nom("Y"), nom("Y")
        s1, OX = yangi_buyurtma(detal(x1, 10, A), detal(x2, 10, B))
        s2, OY = yangi_buyurtma(detal(y1, 10, B), detal(y2, 10, A))
        n = poyga(tahrir(OX, detal(x1, 15, A), detal(x2, 15, B)),
                  tahrir(OY, detal(y1, 15, B), detal(y2, 15, A)))
        h = holat([A, B])
        if not (h["tm"] == {A: 70.0, B: 70.0} and _ok(n[0]) and _ok(n[1])):
            yomon["S9"].append((s1, s2, n, h))

        F = yangi_tm()
        st, O = yangi_qoralama(detal(nom("Q"), 7, F))
        n = poyga(sotuv(F, 5), faollashtir(O))
        h = holat_q(F, O)
        if not (h["tm"] == 88.0 and h["status"] == "in_progress" and _ok(n[0]) and _ok(n[1])):
            yomon["S10"].append((st, n, h))

        st, O = yangi_qoralama(detal(nom("Q"), 100))
        h0 = holat_q(None, O)
        n = poyga(faollashtir(O), faollashtir(O))
        h = holat_q(None, O)
        if not (_ok(n[0]) and isinstance(n[1], dict) and n[1].get("success") is False
                and "qoralama emas" in str(n[1].get("message")) and abs(h0["peno"] - h["peno"] - 1.0) < 1e-6
                and h["status"] == "in_progress"):
            yomon["S11"].append((st, n, h0, h))

        F = yangi_tm()
        a = nom("D")
        st, O = yangi_buyurtma(detal(a, 10, F))
        n = poyga(tahrir(O, detal(a, 15, F)), sotuv(F, 5))
        h = holat([F], O)
        if not (h["tm"][F] == 80.0 and _ok(n[0]) and _ok(n[1])):
            yomon["S3"].append((st, n, h))

        F = yangi_tm()
        st, O = yangi_buyurtma(detal(nom("D"), 10, F))
        n = poyga(sotuv(F, 5), yarat(detal(nom("Y"), 7, F)))
        h = holat([F])
        if not (h["tm"][F] == 78.0 and _ok(n[0])):
            yomon["S4c"].append((st, n, h))

    check("S1b aralash buyurtmani ikki joydan tahrirlash (15 / 120 || 18 / 130): TM 82, tan narx 82 000",
          not yomon["S1b"], str(yomon["S1b"][:1]))
    check("S2 TM sotuvi 5 || tahrir 10 → 15: TM 80, ikkalasi bajarildi", not yomon["S2"], str(yomon["S2"][:1]))
    check("S2b TM sotuvi 5 || aralash tahrir: TM 80", not yomon["S2b"], str(yomon["S2b"][:1]))
    check("S6 TM sotuvi 5 || buyurtmani o'chirish (TM +10): TM 95 (K64-1)", not yomon["S6"], str(yomon["S6"][:1]))
    check("S7 savatcha [B, A] || tahrir (A, B): deadlock YO'Q, A 80, B 80 (K65-1)", not yomon["S7"],
          str(yomon["S7"][:1]))
    check("S8 savatcha [A, B] || savatcha [B, A]: deadlock YO'Q, A 92, B 92 (K65-1)", not yomon["S8"],
          str(yomon["S8"][:1]))
    check("S9 ikki buyurtma [A, B] / [B, A] (teskari tartib) parallel tahrir: deadlock YO'Q, A 70, B 70",
          not yomon["S9"],
          str(yomon["S9"][:1]))
    check("S10 TM sotuvi 5 || TM 7 li qoralamani jarayonga olish: TM 88", not yomon["S10"], str(yomon["S10"][:1]))
    check("S11 bir qoralamani ikki joydan jarayonga olish: bittasi bajariladi, penoplast BIR marta (K65-2)",
          not yomon["S11"], str(yomon["S11"][:1]))
    check("S3 (nazorat) tahrir 10 → 15 || sotuv 5: TM 80", not yomon["S3"], str(yomon["S3"][:1]))
    check("S4c (nazorat) sotuv 5 || yangi buyurtma TM dan 7: TM 78", not yomon["S4c"], str(yomon["S4c"][:1]))


def kumulyativ():
    section("5. 5xx yo'q")
    r = req(C, "get", "/api/orders")
    check("/api/orders → 200", r.status_code == 200, f"{r.status_code}")
    r = req(C, "get", "/api/finished")
    check("/api/finished → 200", r.status_code == 200, f"{r.status_code}")


for _b in (bolim_statik, bolim_birlik, bolim_ketma_ket, bolim_parallel, kumulyativ):
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
