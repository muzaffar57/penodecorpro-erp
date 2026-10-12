#!/usr/bin/env python3
"""
test_audit_mrp.py — kech142 (zip 170): AUDIT — MRP (ishlab chiqarish) topilmalari (A-O02, A-O03, A-O10 a).

NIMA UCHUN KERAK (har biri O'LCHANGAN — asl kod zip 169, `work/audit/tasdiq/ombor/p_o02.py`, `p_o03.py`, `p_o03b.py`):
  A-O02 Retseptni (mahsulot tarkibini) saqlash hamma qatorni o'chirib, qaytadan yaratardi (yangi id). Qoralama ishlab chiqarish
        ixtiyoriy / qoplama tanlovini qator id lari bilan saqlardi — O'ZGARISHSIZ saqlash ham qoplamani «tanlanmagan» qilardi:
        qoplamali buyurtma detali uchun qoplama yechilmas, mahsulot «qoplamasiz», tannarx 12 300 o'rniga 4 800 (PG da har
        safar; SQLite da qatorlar jadval oxirida bo'lsa — rowid qayta ishlatilib — niqoblanardi). Ikki parallel saqlash PG da
        qatorlarni ikki baravar qilishi mumkin edi.
  A-O03 «Boshlash» / «Yakunlash» / «Bekor qilish» ishlab chiqarish qatorini qulflamasdi: ikki parallel «Yakunlash» xomashyoni
        IKKI marta yechardi (30 kg o'rniga 60, ikki harakat), ikki «Boshlash» (omborga) ikkita tayyor mahsulot yaratardi —
        biri «ishlab chiqarilmoqda» holatida abadiy qolardi (yakunlab ham, o'chirib ham, sotib ham bo'lmasdi).
  A-O10 a Yakunlashda materiali o'chirilgan qator tannarxdan jimgina TUSHIB qolardi (izoh «surat narxi bilan» derdi).
TALAB (bo'limlar): R — retsept tahriri va qoralama tanlovi (A-O02); P — holat o'tishlari qulfi (A-O03; poygalar faqat PG);
  K — o'chirilgan material tannarxi (A-O10 a); S — statik (manba).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (har ishga yangi baza; parallel poygalar faqat PG da).
ISHLATISH: python3 tools/test_audit_mrp.py
"""
import os
import sys
import time
import inspect
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "audit_mrp_test"
_T = tempfile.mkdtemp(prefix="audit_mrp_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'audit_mrp_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import production_service as ps                # noqa: E402
    import production_routes as pr                 # noqa: E402
    import production_models as pm                 # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Project, OrderItem, Inventory, InventoryMovement, FinishedProduct   # noqa: E402
from production_models import ProductionOrder, BOMItem   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
SERVER_500 = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def xav(fn, standart=None):
    """Bitta qadam yiqilsa butun test qulamasin (keyingi tekshiruvlar o'z holatini o'zi yaratadi)."""
    try:
        return fn()
    except Exception as e:                 # noqa: BLE001
        print(f"    (qadam yiqildi: {type(e).__name__}: {str(e)[:300]})")
        return standart


PAROL = "Parol123!"
with TestClient(main.app, base_url="https://testserver") as _c0:      # startup (jadvallar, migratsiyalar, standart admin)
    _c0.get("/login")

db = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(db, "mrp_admin", PAROL, UserRole.ADMIN, "MRP Admin", company_id=1)
QUM = Inventory(company_id=1, item_name="AM Qum", unit="kg", stock_quantity=100_000, price_per_unit=800, category="Kimyo")
KR = Inventory(company_id=1, item_name="AM Kraska", unit="kg", stock_quantity=100_000, price_per_unit=5000, category="Kimyo")
KR2 = Inventory(company_id=1, item_name="AM Kraska2", unit="kg", stock_quantity=100_000, price_per_unit=6000, category="Kimyo")
QD = Inventory(company_id=1, item_name="AM Qadoq", unit="dona", stock_quantity=100_000, price_per_unit=300, category="Kimyo")
TOSH = Inventory(company_id=1, item_name="AM Tosh", unit="kg", stock_quantity=100_000, price_per_unit=1000, category="Kimyo")
PRJ = Project(company_id=1, client_name="AM Mijoz", project_name="AM loyiha", total_budget=0, total_paid=0)
db.add_all([QUM, KR, KR2, QD, TOSH, PRJ])
db.commit()
Q, K, K2, QDID, T, PRJ_ID = QUM.id, KR.id, KR2.id, QD.id, TOSH.id, PRJ.id
db.close()


class _Mijoz:
    def __init__(self, c):
        self.c = c

    def __getattr__(self, nom):
        f = getattr(self.c, nom)
        if nom not in ("get", "post", "put", "delete", "patch"):
            return f

        def o(*a, **k):
            r = f(*a, **k)
            if r.status_code >= 500:
                SERVER_500.append((nom, a[:1], r.status_code, r.text[:200]))
            return r
        return o


def kirish():
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": "mrp_admin", "password": PAROL}, follow_redirects=False)
    assert r.status_code == 302, (r.status_code, r.text[:200])
    return _Mijoz(c)


C = kirish()


# ── yordamchilar ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def qoldiq(mid):
    s = SessionLocal()
    try:
        r = s.get(Inventory, mid)
        return None if r is None else round(float(r.stock_quantity or 0), 6)
    finally:
        s.close()


_n = [0]


def tur(qoplama=True):
    _n[0] += 1
    return js(C.post("/api/production/product-types", json={
        "name": f"AM Dekor {_n[0]}", "unit": "dona", "input_template": "quantity_only", "pricing_formula": "unit_based",
        "supports_coating": qoplama, "coating_price_multiplier": 2})).get("id")


def boshqa_retsept():
    """Tekshirilayotgan retseptdan KEYIN boshqa retsept — uning qatorlari jadval oxirida turmasin (SQLite rowid qayta
    ishlatilishi id o'zgarishini niqoblamasin)."""
    pt2 = tur(False)
    C.post("/api/production/boms", json={"product_type_id": pt2, "variant_name": "Standart", "batch_quantity": 1,
                                         "items": [{"inventory_id": Q, "quantity": 1}]})


BOM_PT = {}


def retsept(pt, items):
    tana = {"product_type_id": pt, "variant_name": "Standart", "batch_quantity": 1, "items": items}
    b = js(C.post("/api/production/boms", json=tana))
    BOM_PT[b.get("id")] = pt
    return b.get("id"), tana, b


STD = [{"inventory_id": Q, "quantity": 2}, {"inventory_id": K, "quantity": 0.5, "is_optional": True, "is_coating": True}]


def mijoz_po(pt, bom, miqdor=3, qoplamali=True):
    r = C.post("/api/orders", params={"confirm_shortage": "true"}, json={
        "project_id": PRJ_ID, "order_type": "product", "deadline": "2026-12-10", "is_draft": False,
        "items": [{"name": f"AM detal {time.time()}", "category": "mrp_product", "quantity": miqdor, "unit_price": 50000,
                   "is_coated": qoplamali, "product_type_id": pt}]})
    oid = js(r).get("id")
    s = SessionLocal()
    try:
        iid = s.query(OrderItem.id).filter(OrderItem.order_id == oid).scalar()
    finally:
        s.close()
    po = js(C.post("/api/production/orders", json={"product_type_id": pt, "bom_id": bom, "quantity": miqdor,
                                                   "source_type": "customer_order", "source_order_id": oid,
                                                   "source_order_item_id": iid})).get("production_order") or {}
    return po.get("id"), oid, iid


def ombor_po(pt, bom, miqdor, tanlangan=None):
    tana = {"product_type_id": pt, "bom_id": bom, "quantity": miqdor, "source_type": "warehouse_stock"}
    if tanlangan is not None:
        tana["selected_optional_bom_item_ids"] = tanlangan
    return (js(C.post("/api/production/orders", json=tana)).get("production_order") or {}).get("id")


def yurgiz(po):
    st = C.post(f"/api/production/orders/{po}/start")
    cm = C.post(f"/api/production/orders/{po}/complete")
    s = SessionLocal()
    try:
        o = s.get(ProductionOrder, po)
        fp = s.get(FinishedProduct, o.finished_product_id) if o.finished_product_id else None
        return {"st": st.status_code, "cm": cm.status_code, "cost": round(float(o.total_cost or 0), 2),
                "qoplamali": bool(fp.is_coated) if fp else None, "xabar": (js(st), js(cm)) if st.status_code != 200
                or cm.status_code != 200 else None}
    finally:
        s.close()


def qator_idlari(bom):
    """Retsept qatorlari API tartibida: (id, material, qoplamami) — `GET /api/production/product-types/{id}/boms`."""
    b = next((x for x in js(C.get(f"/api/production/product-types/{BOM_PT.get(bom)}/boms")) if x.get("id") == bom), {})
    return [(x["id"], x["inventory_id"], bool(x.get("is_coating"))) for x in b.get("items", [])]


def royxat_po(po):
    d = js(C.get("/api/production/orders"))
    rows = d if isinstance(d, list) else (d.get("items") or d.get("orders") or [])
    return next((x for x in rows if x.get("id") == po), {})


def manba(obj):
    try:
        return inspect.getsource(obj)
    except Exception:                      # noqa: BLE001
        return ""


def tartibda(src, *parchalar):
    i = -1
    for p in parchalar:
        j = src.find(p, i + 1)
        if j < 0:
            return False
        i = j
    return True


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R — A-O02: retsept tahriri qoralama ishlab chiqarishning qoplama / ixtiyoriy tanlovini yo'qotmaydi")


def r1_r4():
    pt = tur()
    bom, tana, b = retsept(pt, STD)
    boshqa_retsept()
    eski = qator_idlari(bom)
    po_m, _, _ = mijoz_po(pt, bom, 3)
    qopl = next(x[0] for x in eski if x[2])
    po_o = ombor_po(pt, bom, 4, [qopl])
    ru = C.put(f"/api/production/boms/{bom}", json=tana)
    check("R1 o'zgarishsiz saqlash — qatorlar id lari o'zgarmadi", ru.status_code == 200 and qator_idlari(bom) == eski,
          (ru.status_code, eski, qator_idlari(bom)))
    pv = js(C.get(f"/api/production/orders/{po_m}/preview"))
    kr = next((x for x in pv.get("qatorlar", []) if x.get("is_coating")), {})
    check("R2 qoplamali detal qoralamasi — «Boshlash» rejasi: qoplama qatori kiritilgan, tannarx 12 300 (ilgari 4 800)",
          kr.get("included") is True and abs(float(pv.get("tannarx") or 0) - 12300) < 0.01, (kr, pv.get("tannarx")))
    li = royxat_po(po_m)
    check("R11 ro'yxat: qoralama taxminiy tannarxi 12 300 = reja, ixtiyoriy_idlar = [qoplama qatori]",
          abs(float(li.get("taxminiy_tannarx") or 0) - 12300) < 0.01 and li.get("ixtiyoriy_idlar") == [qopl],
          {k: li.get(k) for k in ("taxminiy_tannarx", "ixtiyoriy_idlar")})
    k0, q0 = qoldiq(K), qoldiq(Q)
    y = yurgiz(po_m)
    check("R3 boshlash + yakunlash: Kraska −1.5, Qum −6, mahsulot qoplamali, tannarx 12 300",
          y["st"] == 200 and y["cm"] == 200 and abs((k0 - qoldiq(K)) - 1.5) < 1e-6 and abs((q0 - qoldiq(Q)) - 6) < 1e-6
          and y["qoplamali"] is True and abs(y["cost"] - 12300) < 0.01, (y, k0 - qoldiq(K), q0 - qoldiq(Q)))
    k0 = qoldiq(K)
    y = yurgiz(po_o)
    check("R4 omborga qoralama (qoplama belgilangan) — Kraska −2, tannarx 16 400 (ilgari 6 400)",
          y["st"] == 200 and y["cm"] == 200 and abs((k0 - qoldiq(K)) - 2) < 1e-6 and abs(y["cost"] - 16400) < 0.01,
          (y, k0 - qoldiq(K)))


xav(r1_r4)


def r5_r6():
    pt = tur()
    bom, tana, _ = retsept(pt, STD)
    boshqa_retsept()
    eski = qator_idlari(bom)
    qopl = next(x[0] for x in eski if x[2])
    po5, _, _ = mijoz_po(pt, bom, 3)
    t5 = dict(tana, items=[{"inventory_id": Q, "quantity": 2},
                           {"inventory_id": K2, "quantity": 0.5, "is_optional": True, "is_coating": True}])
    ru = C.put(f"/api/production/boms/{bom}", json=t5)
    yangi_qopl = next((x[0] for x in qator_idlari(bom) if x[2]), None)
    check("R5 qoplama materiali almashtirildi (Kraska → Kraska2) — qoplama qatori id si o'sha", ru.status_code == 200
          and yangi_qopl == qopl, (ru.status_code, eski, qator_idlari(bom)))
    k0, k20 = qoldiq(K), qoldiq(K2)
    y = yurgiz(po5)
    check("R5b qoralama Kraska2 dan 1.5 kg yechdi, Kraska tegilmadi, tannarx 13 800",
          y["cm"] == 200 and abs((k20 - qoldiq(K2)) - 1.5) < 1e-6 and abs(k0 - qoldiq(K)) < 1e-9 and abs(y["cost"] - 13800) < 0.01,
          (y, k20 - qoldiq(K2), k0 - qoldiq(K)))
    po6, _, _ = mijoz_po(pt, bom, 3)
    t6 = dict(tana, items=[{"inventory_id": Q, "quantity": 2},
                           {"inventory_id": K2, "quantity": 0.8, "is_optional": True, "is_coating": True}])
    C.put(f"/api/production/boms/{bom}", json=t6)
    k20 = qoldiq(K2)
    y = yurgiz(po6)
    check("R6 qoplama miqdori 0.5 → 0.8 — qoralama 2.4 kg yechdi, tannarx 19 200",
          y["cm"] == 200 and abs((k20 - qoldiq(K2)) - 2.4) < 1e-6 and abs(y["cost"] - 19200) < 0.01, (y, k20 - qoldiq(K2)))


xav(r5_r6)


def r7():
    pt = tur()
    bom, tana, _ = retsept(pt, [{"inventory_id": Q, "quantity": 2}])
    boshqa_retsept()
    po, _, _ = mijoz_po(pt, bom, 3)
    C.put(f"/api/production/boms/{bom}", json=dict(tana, items=STD))
    k0 = qoldiq(K)
    y = yurgiz(po)
    check("R7 qoplama qatori retseptga qoralamadan KEYIN qo'shildi — qoplamali detal uchun kiritildi (−1.5, 12 300)",
          y["cm"] == 200 and abs((k0 - qoldiq(K)) - 1.5) < 1e-6 and abs(y["cost"] - 12300) < 0.01 and y["qoplamali"] is True,
          (y, k0 - qoldiq(K)))


xav(r7)


def r8():
    pt = tur()
    bom, _, _ = retsept(pt, STD)
    boshqa_retsept()
    po, _, iid = mijoz_po(pt, bom, 3)
    s = SessionLocal()
    try:
        s.get(OrderItem, iid).is_coated = False          # detal qoplamasi qoralamadan keyin olib tashlandi
        s.commit()
    finally:
        s.close()
    k0 = qoldiq(K)
    y = yurgiz(po)
    check("R8 detal qoplamasi qoralamadan KEYIN olib tashlandi — qoplama yechilmadi, mahsulot qoplamasiz, tannarx 4 800",
          y["cm"] == 200 and abs(k0 - qoldiq(K)) < 1e-9 and y["qoplamali"] is False and abs(y["cost"] - 4800) < 0.01,
          (y, k0 - qoldiq(K)))


xav(r8)


def r9():
    pt = tur()
    items = [{"inventory_id": Q, "quantity": 2}, {"inventory_id": QDID, "quantity": 1, "is_optional": True}]
    bom, tana, _ = retsept(pt, items)
    boshqa_retsept()
    qd_line = next(x[0] for x in qator_idlari(bom) if x[1] == QDID)
    po = ombor_po(pt, bom, 4, [qd_line])
    C.put(f"/api/production/boms/{bom}", json=tana)
    d0 = qoldiq(QDID)
    y = yurgiz(po)
    check("R9 qoplama bo'lmagan ixtiyoriy qator (Qadoq) tanlangan, o'zgarishsiz saqlash — Qadoq −4, tannarx 7 600",
          y["cm"] == 200 and abs((d0 - qoldiq(QDID)) - 4) < 1e-6 and abs(y["cost"] - 7600) < 0.01, (y, d0 - qoldiq(QDID)))


xav(r9)


def r10_r12():
    pt = tur()
    bom, tana, _ = retsept(pt, STD)
    boshqa_retsept()
    po, _, _ = mijoz_po(pt, bom, 3)
    st = C.post(f"/api/production/orders/{po}/start")
    C.put(f"/api/production/boms/{bom}", json=dict(tana, items=[{"inventory_id": Q, "quantity": 2},
                                                                {"inventory_id": K, "quantity": 0.8, "is_optional": True,
                                                                 "is_coating": True}]))
    k0 = qoldiq(K)
    cm = C.post(f"/api/production/orders/{po}/complete")
    check("R10 jarayondagi ishlab chiqarish — boshlangandan keyingi tahrir ta'sir qilmaydi (surat: 1.5 kg)",
          st.status_code == 200 and cm.status_code == 200 and abs((k0 - qoldiq(K)) - 1.5) < 1e-6, (st.status_code, cm.status_code))
    po2, _, _ = mijoz_po(pt, bom, 3)
    ru = C.put(f"/api/production/boms/{bom}", json=dict(tana, items=[{"inventory_id": Q, "quantity": 2}]))
    k0 = qoldiq(K)
    y = yurgiz(po2)
    check("R12 qoplama qatori retseptdan olib tashlandi — 1 qator qoldi, qoralama xatosiz qoplamasiz boshlandi",
          ru.status_code == 200 and len(qator_idlari(bom)) == 1 and y["st"] == 200 and y["cm"] == 200
          and abs(k0 - qoldiq(K)) < 1e-9, (ru.status_code, qator_idlari(bom), y))


xav(r10_r12)


def r13_r14():
    pt = tur()
    items = [{"inventory_id": K, "quantity": 1}, {"inventory_id": K, "quantity": 0.5, "is_optional": True, "is_coating": True}]
    bom, tana, _ = retsept(pt, items)
    boshqa_retsept()
    eski = qator_idlari(bom)
    C.put(f"/api/production/boms/{bom}", json=tana)
    check("R13 bir material ikki qatorda (xomashyo + qoplama) — o'zgarishsiz saqlashda ikkala id saqlandi",
          qator_idlari(bom) == eski, (eski, qator_idlari(bom)))
    pt2 = tur()
    bom2, tana2, _ = retsept(pt2, STD)
    boshqa_retsept()
    C.put(f"/api/production/boms/{bom2}", json=dict(tana2, items=[{"inventory_id": Q, "quantity": 3}, STD[1]]))
    check("R14 Qum miqdori o'zgardi — qatorlar tartibi [Qum, Kraska] (id tartibi)",
          [x[1] for x in qator_idlari(bom2)] == [Q, K], qator_idlari(bom2))


xav(r13_r14)

if PG_URL:
    def r16():
        """R16 (PG): ikki parallel saqlash — A qoplama qatorini OLIB TASHLAYDI (yozib, commit gacha ushlab turadi), B shu qatorning
        miqdorini o'zgartiradi. Retsept qatori qulfi bilan B A ni kutadi va yangi qatorlarni ko'radi (500 / StaleDataError yo'q),
        natija — B ning tanasi; qatorlar ikki baravar emas."""
        pt = tur()
        bom, tana, _ = retsept(pt, STD)
        asl = pr._retsept_farqi

        def sekin(*a, **k):
            time.sleep(0.6)
            return asl(*a, **k)
        pr._retsept_farqi = sekin
        ta = dict(tana, items=[{"inventory_id": Q, "quantity": 2}])
        tb = dict(tana, items=[{"inventory_id": Q, "quantity": 2},
                               {"inventory_id": K, "quantity": 0.8, "is_optional": True, "is_coating": True}])
        try:
            nat = [None, None]
            bar = threading.Barrier(2)

            def t(i, tn, kech):
                bar.wait(timeout=30)
                time.sleep(kech)
                nat[i] = C.put(f"/api/production/boms/{bom}", json=tn)
            ts = [threading.Thread(target=t, args=(0, ta, 0)), threading.Thread(target=t, args=(1, tb, 0.25))]
            [x.start() for x in ts]
            [x.join(timeout=60) for x in ts]
        finally:
            pr._retsept_farqi = asl
        s = SessionLocal()
        try:
            qat = sorted((float(x.quantity), bool(x.is_coating)) for x in s.query(BOMItem).filter(BOMItem.bom_id == bom).all())
        finally:
            s.close()
        check("R16 PG: parallel saqlash (A qoplamani olib tashlaydi ∥ B miqdorini 0.8 qiladi) — 200 / 200, 500 yo'q, natija B: "
              "[Qum 2, Kraska 0.8]", [getattr(x, "status_code", 0) for x in nat] == [200, 200] and qat == [(0.8, True), (2.0, False)],
              ([getattr(x, "status_code", x) for x in nat], qat))
    xav(r16)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P — A-O03: boshlash / yakunlash / bekor qilish — qator qulfi, holat qulfdan keyin tekshiriladi")
PT3 = tur(False)
BOM3, _, _ = retsept(PT3, [{"inventory_id": T, "quantity": 3}])


def tosh_harakati(po):
    s = SessionLocal()
    try:
        return [(m.movement_type, m.quantity) for m in s.query(InventoryMovement).filter(
            InventoryMovement.inventory_id == T, InventoryMovement.reason == f"Ishlab chiqarish buyurtmasi #{po} yakunlandi").all()]
    finally:
        s.close()


def p7():
    po = ombor_po(PT3, BOM3, 2)
    C.post(f"/api/production/orders/{po}/start")
    c1 = C.post(f"/api/production/orders/{po}/complete")
    c2 = C.post(f"/api/production/orders/{po}/complete")
    check("P7 ketma-ket: ikkinchi «Yakunlash» — 409 «… yakunlangan», bitta harakat",
          c1.status_code == 200 and c2.status_code == 409 and "yakunlangan" in str(js(c2)) and len(tosh_harakati(po)) == 1,
          (c1.status_code, c2.status_code, js(c2), tosh_harakati(po)))
    cb = C.post(f"/api/production/orders/{po}/cancel")
    check("P7b yakunlangandan keyin «Bekor qilish» — 409", cb.status_code == 409, (cb.status_code, js(cb)))
    po2 = ombor_po(PT3, BOM3, 2)
    C.post(f"/api/production/orders/{po2}/cancel")
    sb = C.post(f"/api/production/orders/{po2}/start")
    check("P7c bekor qilingandan keyin «Boshlash» — 409", sb.status_code == 409, (sb.status_code, js(sb)))


xav(p7)

if PG_URL:
    def poyga(fn1, fn2, kech=0.8):
        nat = [None, None]
        bar = threading.Barrier(2)

        def t(k, fn, sekin):
            sess = SessionLocal()
            if sekin:
                asl = sess.commit

                def f():
                    time.sleep(kech)
                    asl()
                sess.commit = f
            try:
                bar.wait(timeout=30)
                if not sekin:
                    time.sleep(0.25)
                try:
                    nat[k] = fn(sess)
                except Exception as e:     # noqa: BLE001
                    try:
                        sess.rollback()
                    except Exception:      # noqa: BLE001
                        pass
                    nat[k] = f"ISTISNO {type(e).__name__}: {str(e)[:200]}"
            finally:
                sess.close()
        ts = [threading.Thread(target=t, args=(0, fn1, True)), threading.Thread(target=t, args=(1, fn2, False))]
        [x.start() for x in ts]
        [x.join(timeout=120) for x in ts]
        return nat

    def muv(n):
        return [isinstance(x, dict) and bool(x.get("success")) for x in n]

    for _u in (1, 2):
        def p1(u=_u):
            po = ombor_po(PT3, BOM3, 10)
            C.post(f"/api/production/orders/{po}/start")
            t0 = qoldiq(T)
            n = poyga(lambda s: ps.complete_production_order(s, po, 1, "A"), lambda s: ps.complete_production_order(s, po, 1, "B"))
            check(f"P1 #{u} PG: ikki parallel «Yakunlash» — bittasi muvaffaqiyatli, Tosh −30 (60 emas), bitta harakat",
                  sorted(muv(n)) == [False, True] and abs((t0 - qoldiq(T)) - 30) < 1e-6 and len(tosh_harakati(po)) == 1,
                  (n, t0 - qoldiq(T), tosh_harakati(po)))
            xato = next((x for x in n if isinstance(x, dict) and not x.get("success")), {})
            check(f"P1 #{u} yutqazganning xabari — «Faqat jarayondagi … yakunlangan»",
                  "yakunlangan" in str(xato.get("message")), xato)
        xav(p1)

    def p3():
        po = ombor_po(PT3, BOM3, 5)
        n = poyga(lambda s: ps.start_production_order(s, po, 1, "A"), lambda s: ps.start_production_order(s, po, 1, "B"))
        s = SessionLocal()
        try:
            o = s.get(ProductionOrder, po)
            yetim = s.query(FinishedProduct).filter(
                FinishedProduct.category == "dynamic_bom", FinishedProduct.product_type_id == PT3,
                FinishedProduct.id != (o.finished_product_id or 0),
                ~FinishedProduct.id.in_(s.query(ProductionOrder.finished_product_id).filter(
                    ProductionOrder.finished_product_id.isnot(None)))).count()
        finally:
            s.close()
        check("P3 PG: ikki parallel «Boshlash» (omborga) — bittasi muvaffaqiyatli, yetim «ishlab chiqarilmoqda» mahsulot yo'q",
              sorted(muv(n)) == [False, True] and yetim == 0, (n, yetim))
    xav(p3)

    def p5():
        po = ombor_po(PT3, BOM3, 10)
        C.post(f"/api/production/orders/{po}/start")
        t0 = qoldiq(T)
        n = poyga(lambda s: ps.complete_production_order(s, po, 1, "A"), lambda s: ps.cancel_production_order(s, po, 1, "B"))
        s = SessionLocal()
        try:
            o = s.get(ProductionOrder, po)
            fp = s.get(FinishedProduct, o.finished_product_id) if o.finished_product_id else None
            holat = (o.status, fp is not None, round(t0 - qoldiq(T), 6), len(tosh_harakati(po)))
        finally:
            s.close()
        check("P5 PG: «Yakunlash» ∥ «Bekor qilish» — natija izchil: (yakunlangan, mahsulot bor, −30, 1 harakat) — xomashyo "
              "izsiz yo'qolmaydi", holat == ("completed", True, 30.0, 1), (n, holat))
    xav(p5)

    def p8():
        po = ombor_po(PT3, BOM3, 2)
        C.post(f"/api/production/orders/{po}/start")
        C.post(f"/api/production/orders/{po}/complete")
        s1 = SessionLocal()
        s2 = SessionLocal()
        try:
            n = ps.complete_production_order(s1, po, 1, "A")
            try:
                s2.execute(text("SELECT id FROM production_orders WHERE id = :i FOR UPDATE NOWAIT"), {"i": po}).all()
                bosh = True
            except Exception:              # noqa: BLE001
                bosh = False
        finally:
            s2.rollback()
            s2.close()
            s1.close()
        check("P8 PG: rad etilgan «Yakunlash» qulfni darhol bo'shatadi (boshqa sessiya NOWAIT bilan qulflay oladi)",
              isinstance(n, dict) and not n.get("success") and bosh, (n, bosh))
    xav(p8)
else:
    print("  (SQLite — parallel poygalar P1 / P3 / P5 / P8 o'tkazib yuborildi; PG_URL bilan ishga tushiring)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K — A-O10 a: yakunlashda o'chirilgan material — ombordan yechilmaydi, tannarxga surat narxi bilan kiradi")


def k1():
    s = SessionLocal()
    try:
        m = Inventory(company_id=1, item_name="AM K1 Gips", unit="kg", stock_quantity=100, price_per_unit=2000, category="Kimyo")
        s.add(m)
        s.commit()
        mid = m.id
    finally:
        s.close()
    pt = tur(False)
    bom, tana, _ = retsept(pt, [{"inventory_id": Q, "quantity": 2}, {"inventory_id": mid, "quantity": 1}])
    po = ombor_po(pt, bom, 2)
    st = C.post(f"/api/production/orders/{po}/start")
    C.put(f"/api/production/boms/{bom}", json=dict(tana, items=[{"inventory_id": Q, "quantity": 2}]))
    s = SessionLocal()
    try:
        s.delete(s.get(Inventory, mid))                      # material bazadan o'chdi (havolasi yo'q)
        s.commit()
    finally:
        s.close()
    pv = js(C.get(f"/api/production/orders/{po}/preview"))
    check("K1 reja (yakunlash): o'chirilgan material ko'rsatiladi, tannarx 7 200 (Qum 3 200 + Gips 4 000)",
          st.status_code == 200 and "AM K1 Gips" in str(pv.get("topilmadi")) and abs(float(pv.get("tannarx") or 0) - 7200) < 0.01,
          (st.status_code, pv.get("topilmadi"), pv.get("tannarx")))
    cm = C.post(f"/api/production/orders/{po}/complete")
    s = SessionLocal()
    try:
        o = s.get(ProductionOrder, po)
        tc = round(float(o.total_cost or 0), 2)
    finally:
        s.close()
    check("K1b yakunlash 200, tannarx 7 200 = reja (ilgari 3 200 — o'chirilgan material puli tushib qolardi)",
          cm.status_code == 200 and abs(tc - 7200) < 0.01, (cm.status_code, js(cm), tc))


xav(k1)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — statik (manba)")
for _nom, _f, _hol in (("start_production_order", ps.start_production_order, "po.status != ProductionOrderStatus.DRAFT.value"),
                       ("complete_production_order", ps.complete_production_order,
                        "po.status != ProductionOrderStatus.IN_PROGRESS.value"),
                       ("cancel_production_order", ps.cancel_production_order, "po.status not in (")):
    check(f"S1 {_nom}: `_po_qulfli` holat tekshiruvidan OLDIN", tartibda(manba(_f), "_po_qulfli(db, po_id, company_id)", _hol))
_mq = manba(getattr(ps, "_po_qulfli", None))
_mq = _mq.split('"""')[-1] if _mq.count('"""') >= 2 else _mq
check("S1b _po_qulfli: flush, so'ng populate_existing + FOR UPDATE", tartibda(_mq, "db.flush()", "populate_existing().with_for_update()"))
_mu = manba(pr.update_bom)
check("S2 update_bom: retsept qatori qulfi `_holat120` dan OLDIN, qatorlarni ommaviy o'chirish yo'q, joyida yangilash",
      tartibda(_mu, "with_for_update()", "_holat120 = _retsept_holati(bom)") and "db.query(BOMItem)" not in _mu
      and "retsept_qatorlarini_yangila(" in _mu)
check("S3 BOM.items — id tartibida (`order_by`)", lambda: pm.BOM.items.property.order_by is not False
      and "id" in str(pm.BOM.items.property.order_by))
for _nom, _f in (("start_production_order", ps.start_production_order),
                 ("mavjud_ishlab_chiqarish_rejasi", ps.mavjud_ishlab_chiqarish_rejasi),
                 ("royxat_qoshimchalari", ps.royxat_qoshimchalari)):
    check(f"S4 {_nom}: qoralama tanlovi `_qoralama_tanlovi(` bilan", "_qoralama_tanlovi(" in manba(_f))
_mc = manba(ps.complete_production_order)
check("S5 complete_production_order: o'chirilgan material qatori tannarxga qo'shiladi",
      tartibda(_mc, "if not inv:", 'total_material_cost += float(line.get("line_cost") or 0)', "continue"))
_mo = manba(ps._qoralama_tanlovi) if hasattr(ps, "_qoralama_tanlovi") else ""
check("S6 _qoralama_tanlovi so'rov yubormaydi (ro'yxat so'rovlari soni qatorlarga bog'liq emas)",
      bool(_mo) and "db.query" not in _mo and ".query(" not in _mo)

section("X — umumiy")
check("X1 butun yurishda 5xx javob yo'q", not SERVER_500, SERVER_500[:5])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
