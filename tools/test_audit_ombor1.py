#!/usr/bin/env python3
"""
test_audit_ombor1.py — kech142 (zip 170): AUDIT — TAYYOR MAHSULOT topilmalari (A-O01, A-O08).

NIMA UCHUN KERAK (har biri O'LCHANGAN — asl kod zip 169, `work/audit/tasdiq/ombor/p_o01.py`, `p_o04b.py`, `p_o08.py`):
  A-O01 Bitta «Sotish» (`POST /api/finished/sell`) BUYURTMAGA BAND mahsulotni ham sotardi (savatcha sotuvi band ni hisobga
        olardi, bitta sotuv — yo'q): 10 m² ning hammasi band bo'lsa ham sotilib (qoldiq 0, band 10), o'sha buyurtmaning yuk
        xati, «Tayyor» va yangi ishlab chiqarishi uchalasi rad etilib, buyurtma QOTIB qolardi. Sahifa «Sotish» oynasida band
        qismni ham sotishga ruxsat berardi. Savatchada eski yozuv (band > qoldiq) uchun «faqat -10» xabari; barqaror narxsiz
        eski yozuvda tannarx band bo'lmagan qismga bo'linib, sotuv tannarxi shishardi (12 000 o'rniga 30 000).
  A-O08 «+» (`/api/finished/{id}/add`) va `/reduce` mahsulotni qulfsiz o'qib, mutlaq qiymat yozardi — parallel sotuv YO'QOLARDI
        (sotuv 5 ∥ «+» 2: 100 → 102, to'g'risi 97). `/reduce` tannarxni kamaytirmasdi (10 × 3 000 dan 4 → ombor qiymati 18 000
        o'rniga 30 000; 0 gacha — tannarx 30 000 abadiy), brak yozuvi yaratmasdi (Moliya «Tayyor mahsulot yo'qotishi» ko'rmasdi),
        sababsiz va «Brak: Yaratish» ruxsatisiz ishlardi, bandni hisobga olmasdi (band mahsulotni 0 gacha — buyurtma qotib
        qolardi). «Brak» (`/loss`) ham band mahsulotdan ayirib, bandni o'zgartirmasdi.
TALAB (bo'limlar): A — bitta / savatcha sotuvi va band (A-O01); B — brak / `/reduce` va band (A-O08); C — eski sessiya (qulf +
  qayta o'qish); P — parallel poygalar (faqat PG); S — statik (manba tartibi); R — ruxsat (`/reduce` — «Brak: Yaratish»).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (har ishga yangi baza; parallel poygalar faqat PG da).
ISHLATISH: python3 tools/test_audit_ombor1.py
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
PG_BAZA = "audit_ombor1_test"
_T = tempfile.mkdtemp(prefix="audit_ombor1_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'audit_ombor1_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas                                 # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, User, Project, OrderItem, Inventory, FinishedProduct, FinishedProductSale,  # noqa: E402
                    FinishedProductLoss, ActivityLog)
from production_models import ProductionOrder      # noqa: E402
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
    auth.create_user(db, "ao1_admin", PAROL, UserRole.ADMIN, "AO1 Admin", company_id=1)
    auth.create_user(db, "ao1_rol", PAROL, UserRole.MANAGER, "AO1 Rol", company_id=1)
TOSH = Inventory(company_id=1, item_name="AO1 Tosh", unit="kg", stock_quantity=100_000, price_per_unit=1000, category="Kimyo")
PENO = Inventory(company_id=1, item_name="AO1 Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
PRJ = Project(company_id=1, client_name="AO1 Mijoz", project_name="AO1 loyiha", total_budget=0, total_paid=0)
db.add_all([TOSH, PENO, PRJ])
db.commit()
TID, PNID, PRJ_ID = TOSH.id, PENO.id, PRJ.id
db.close()


class _Mijoz:
    """TestClient o'rami: har javob 5xx ni yig'adi (oxirida «500 yo'q» tekshiruvi)."""

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


def kirish(login="ao1_admin"):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code == 302, (r.status_code, r.text[:200])
    return _Mijoz(c)


C = kirish()
PT = js(C.post("/api/production/product-types", json={"name": "AO1 Travertin", "unit": "m²", "input_template": "quantity_only",
                                                      "pricing_formula": "unit_based"})).get("id")
BOM = js(C.post("/api/production/boms", json={"product_type_id": PT, "variant_name": "Oddiy", "batch_quantity": 1,
                                              "items": [{"inventory_id": TID, "quantity": 3}]})).get("id")


# ── yordamchilar ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def tm(fid):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid)
        if f is None:
            return None
        return {"q": round(float(f.quantity or 0), 6), "band": round(float(f.reserved_quantity or 0), 6),
                "cost": round(float(f.cost_price or 0), 2), "detal": f.reserved_for_order_item_id}
    finally:
        s.close()


def tm_ozgart(fid, **kv):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid)
        for k, v in kv.items():
            setattr(f, k, v)
        s.commit()
    finally:
        s.close()


def sotuvlar(fid):
    s = SessionLocal()
    try:
        return [(round(float(x.quantity), 6), round(float(x.cost_amount or 0), 2))
                for x in s.query(FinishedProductSale).filter(FinishedProductSale.finished_product_id == fid).all()]
    finally:
        s.close()


def yoqotishlar(fid):
    s = SessionLocal()
    try:
        return [(x.id, round(float(x.quantity), 6), round(float(x.cost_amount or 0), 2))
                for x in s.query(FinishedProductLoss).filter(FinishedProductLoss.finished_product_id == fid).all()]
    finally:
        s.close()


def mijoz_buyurtma(miqdor=10):
    r = C.post("/api/orders", params={"confirm_shortage": "true"}, json={
        "project_id": PRJ_ID, "order_type": "product", "loy_kg": 0,
        "items": [{"name": f"AO1 detal {time.time()}", "category": "mrp_product", "quantity": miqdor, "unit_price": 100000,
                   "is_coated": False, "penoplast_id": None, "product_type_id": PT}]})
    oid = js(r).get("id")
    s = SessionLocal()
    try:
        iid = s.query(OrderItem.id).filter(OrderItem.order_id == oid).scalar()
    finally:
        s.close()
    return oid, iid


def mrp_tm(miqdor=10, mijozga=True):
    """MRP tayyor mahsuloti: mijoz buyurtmasi uchun (band = miqdor) yoki omborga (band 0); 1 m² = 3 kg × 1 000 = 3 000."""
    oid = iid = None
    tana = {"product_type_id": PT, "bom_id": BOM, "quantity": miqdor, "source_type": "warehouse_stock"}
    if mijozga:
        oid, iid = mijoz_buyurtma(miqdor)
        tana.update({"source_type": "customer_order", "source_order_id": oid, "source_order_item_id": iid})
    po = js(C.post("/api/production/orders", json=tana)).get("production_order", {}).get("id")
    st = [C.post(f"/api/production/orders/{po}/{q}").status_code for q in ("start", "complete")]
    s = SessionLocal()
    try:
        fid = s.get(ProductionOrder, po).finished_product_id
    finally:
        s.close()
    return {"oid": oid, "iid": iid, "po": po, "fid": fid, "st": st}


def penoplast_tm(nom):
    r = C.post("/api/finished/produce", json={"name": nom, "category": "profil", "is_coated": False, "penoplast_id": PNID,
                                              "unit_price": 100000, "loy_kg": 0, "width": 10, "thickness": 10, "length": 10,
                                              "quantity": 1})
    s = SessionLocal()
    try:
        fid = s.query(FinishedProduct.id).filter(FinishedProduct.name == nom).scalar()
    finally:
        s.close()
    rc = C.post(f"/api/finished/{fid}/complete")
    return r.status_code, rc.status_code, fid


def sotish(fid, q, narx=50000):
    return C.post("/api/finished/sell", json={"finished_product_id": fid, "quantity": q, "unit_price": narx,
                                              "payment_method": "naqd", "confirm_below_cost": True})


def savat(fid, q, narx=50000):
    return C.post("/api/finished/sell-batch", json={"items": [{"finished_product_id": fid, "quantity": q, "unit_price": narx}],
                                                    "payment_method": "naqd", "confirm_below_cost": True})


def xabar(r):
    d = js(r).get("detail")
    return (d.get("message") if isinstance(d, dict) else d) or ""


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
section("A — A-O01: bitta «Sotish» buyurtmaga band qismni sotmaydi")
F1 = xav(lambda: mrp_tm(10), {})
FA = F1.get("fid")
check("A1 fikstura: mijoz buyurtmasi uchun MRP mahsuloti — qoldiq 10, band 10, tannarx 30 000",
      F1.get("st") == [200, 200] and tm(FA) == {"q": 10.0, "band": 10.0, "cost": 30000.0, "detal": F1.get("iid")},
      (F1, tm(FA)))
r = sotish(FA, 10)
check("A2 to'liq band mahsulot — bitta sotuv 10: 400, xabarda «band» va «Bandni bekor qilish»",
      r.status_code == 400 and "band" in xabar(r) and "Bandni bekor qilish" in xabar(r), (r.status_code, js(r)))
check("A2b mahsulot o'zgarmadi (10 / band 10 / 30 000), sotuv yozuvi yo'q",
      tm(FA) == {"q": 10.0, "band": 10.0, "cost": 30000.0, "detal": F1.get("iid")} and sotuvlar(FA) == [], (tm(FA), sotuvlar(FA)))
r = sotish(FA, 1)
check("A3 band mahsulotdan 1 ham — 400", r.status_code == 400 and tm(FA)["q"] == 10.0, (r.status_code, js(r), tm(FA)))
r = savat(FA, 10)
check("A7 NAZORAT savatcha sotuvi 10 — 400, «band»", r.status_code == 400 and "band" in xabar(r), (r.status_code, js(r)))


def a11():
    s = SessionLocal()
    try:
        d = schemas.FinishedProductSaleCreate(finished_product_id=FA, quantity=2, unit_price=50000, payment_method="naqd",
                                              confirm_below_cost=True)
        n = crud.sell_finished_product(s, d, created_by="A11", company_id=1)
    finally:
        s.close()
    check("A11 to'g'ridan-to'g'ri crud.sell_finished_product band mahsulotda — success False, o'zgarmadi",
          isinstance(n, dict) and not n.get("success") and tm(FA)["q"] == 10.0, (n, tm(FA)))


xav(a11)
rd = C.post("/api/deliveries", json={"order_id": F1.get("oid"), "items": [{"order_item_id": F1.get("iid"), "quantity": 10}],
                                     "notes": "a5", "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
rr = C.post(f"/api/orders/{F1.get('oid')}/ready")
check("A5 buyurtma qotmadi: yuk xati 10 — 200, «Tayyor» — 200 (ilgari ikkalasi 400)",
      rd.status_code == 200 and rr.status_code == 200, (rd.status_code, js(rd), rr.status_code, js(rr)))
check("A5b yuk xatidan keyin mahsulot 0 / band 0", lambda: tm(FA)["q"] == 0 and tm(FA)["band"] == 0, tm(FA))


def a4():
    f = mrp_tm(10, mijozga=False)
    fid = f["fid"]
    tm_ozgart(fid, reserved_quantity=6.0)                  # 6 si buyurtmaga band (ORM — fikstura)
    r5 = sotish(fid, 5)
    check("A4 qoldiq 10, band 6 — sotuv 5: 400 (sotsa bo'ladigani 4)", r5.status_code == 400 and "4" in xabar(r5),
          (r5.status_code, js(r5)))
    r4 = sotish(fid, 4)
    check("A4b sotuv 4 — 200, qoldiq 6, band 6, sotuv tannarxi 12 000",
          r4.status_code == 200 and tm(fid)["q"] == 6.0 and tm(fid)["band"] == 6.0 and sotuvlar(fid) == [(4.0, 12000.0)],
          (r4.status_code, js(r4), tm(fid), sotuvlar(fid)))
    check("A4c javobda band va sotsa bo'ladigan qoldiq", js(r4).get("band") == 6.0 and js(r4).get("sotsa_boladi") == 0.0, js(r4))


xav(a4)


def a9():
    f = mrp_tm(5, mijozga=False)
    fid = f["fid"]
    r = sotish(fid, 6)
    check("A9 bandsiz mahsulot — qoldiqdan ko'p: 400, xabar avvalgidek «Omborda faqat 5 … bor»",
          r.status_code == 400 and "Omborda faqat 5" in xabar(r), (r.status_code, js(r)))
    r = sotish(fid, 5)
    check("A9b aynan qoldiq — 200", r.status_code == 200 and tm(fid)["q"] == 0, (r.status_code, js(r), tm(fid)))


xav(a9)


def a10():
    f = mrp_tm(10, mijozga=False)
    fid = f["fid"]
    tm_ozgart(fid, quantity=0.0, reserved_quantity=10.0)   # eski yozuv: band qoldiqdan katta
    r = savat(fid, 1)
    check("A10 eski yozuv (qoldiq 0, band 10) savatcha sotuvi — 400, xabarda manfiy son yo'q",
          r.status_code == 400 and "-10" not in xabar(r) and "band" in xabar(r), (r.status_code, js(r)))


xav(a10)


def a12():
    f = mrp_tm(10, mijozga=False)
    fid = f["fid"]
    tm_ozgart(fid, reserved_quantity=6.0, unit_cost_stable=None)    # eski yozuv: barqaror 1 birlik tannarxi yo'q
    r = savat(fid, 4)
    check("A12 eski yozuv (barqaror narxsiz, tannarx 30 000, 10 dan 6 band) — savatcha 4: tannarx 12 000 (30 000 emas)",
          r.status_code == 200 and sotuvlar(fid) == [(4.0, 12000.0)], (r.status_code, js(r), sotuvlar(fid)))


xav(a12)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B — A-O08: brak (`/loss`, `/reduce`) — tannarx, brak yozuvi, band")


def b_reduce():
    f = mrp_tm(10, mijozga=False)
    fid = f["fid"]
    r = C.post(f"/api/finished/{fid}/reduce", json={"quantity": 4, "reason": "singan"})
    check("B1 /reduce sababsiz — 400 «Brak sababini tanlang», hech narsa o'zgarmadi",
          r.status_code == 400 and "Brak sababini" in xabar(r) and tm(fid)["q"] == 10 and yoqotishlar(fid) == [],
          (r.status_code, js(r), tm(fid)))
    r = C.post(f"/api/finished/{fid}/reduce", json={"quantity": 4, "reason": "singan", "brak_sabab": "boshqa"})
    y = yoqotishlar(fid)
    check("B2 /reduce 4 (sabab bilan) — 200: qoldiq 6, tannarx 18 000 (ilgari 30 000)",
          r.status_code == 200 and tm(fid)["q"] == 6 and tm(fid)["cost"] == 18000, (r.status_code, js(r), tm(fid)))
    check("B2b brak yozuvi 1 ta: 4, tannarx 12 000 (Moliya «Tayyor mahsulot yo'qotishi»)",
          len(y) == 1 and y[0][1:] == (4.0, 12000.0), y)
    row = next((x for x in js(C.get("/api/finished", params={"show_all": "true"})) if x.get("id") == fid), {})
    check("B2c ro'yxatda ombor qiymati 18 000", abs(float(row.get("ombor_qiymati") or 0) - 18000) < 0.01, row)
    check("B11 /reduce javobida eski maydonlar (new_qty, unit, lost_value, product_id, name) + loss_id",
          all(k in js(r) for k in ("new_qty", "unit", "lost_value", "product_id", "name", "loss_id")) and js(r).get("new_qty") == 6,
          js(r))
    r = C.post(f"/api/finished/{fid}/reduce", json={"quantity": 6, "brak_sabab": "uskuna"})
    check("B3 /reduce 0 gacha — qoldiq 0, tannarx 0 (ilgari 30 000 abadiy qolardi)",
          r.status_code == 200 and tm(fid)["q"] == 0 and tm(fid)["cost"] == 0, (r.status_code, js(r), tm(fid)))
    return fid


xav(b_reduce)


def b4():
    f = mrp_tm(10, mijozga=False)
    fid = f["fid"]
    C.post(f"/api/finished/{fid}/reduce", json={"quantity": 5, "brak_sabab": "boshqa"})
    r = sotish(fid, 5)
    check("B4 /reduce 5, so'ng qolgan 5 sotildi — qoldiq 0, tannarx 0 (ilgari 15 000 qolardi)",
          r.status_code == 200 and tm(fid) and tm(fid)["q"] == 0 and tm(fid)["cost"] == 0, (r.status_code, js(r), tm(fid)))


xav(b4)


def b5():
    b = tashkent_date()
    s = SessionLocal()
    try:
        m0 = float(services.get_monthly_report(s, b.year, b.month, company_id=1).get("fp_loss_xarajat") or 0)
    finally:
        s.close()
    f = mrp_tm(10, mijozga=False)
    r = C.post(f"/api/finished/{f['fid']}/reduce", json={"quantity": 4, "brak_sabab": "olcham"})
    s = SessionLocal()
    try:
        m1 = float(services.get_monthly_report(s, b.year, b.month, company_id=1).get("fp_loss_xarajat") or 0)
    finally:
        s.close()
    check("B5 oylik hisobot «Tayyor mahsulot yo'qotishi» +12 000 (/reduce endi Moliyada ko'rinadi)",
          r.status_code == 200 and abs((m1 - m0) - 12000) < 1, (m0, m1, r.status_code))
    lid = js(r).get("loss_id")
    rd = C.delete(f"/api/finished/loss/{lid}")
    s = SessionLocal()
    try:
        m2 = float(services.get_monthly_report(s, b.year, b.month, company_id=1).get("fp_loss_xarajat") or 0)
    finally:
        s.close()
    check("B5b brak yozuvi o'chirildi — hisobot avvalgi holatda, mahsulot 10 / 30 000",
          rd.status_code == 200 and abs(m2 - m0) < 1 and tm(f["fid"])["q"] == 10 and tm(f["fid"])["cost"] == 30000,
          (rd.status_code, js(rd), m0, m2, tm(f["fid"])))


xav(b5)


def b6():
    f = mrp_tm(10)
    fid, iid, oid = f["fid"], f["iid"], f["oid"]
    r = C.post(f"/api/finished/{fid}/reduce", json={"quantity": 10, "brak_sabab": "boshqa"})
    check("B6 to'liq band mahsulot /reduce 10 — 200: qoldiq 0, band 0 (bog'lam saqlanadi)",
          r.status_code == 200 and tm(fid)["q"] == 0 and tm(fid)["band"] == 0 and tm(fid)["detal"] == iid
          and js(r).get("band_kamaydi") == 10, (r.status_code, js(r), tm(fid)))
    s = SessionLocal()
    try:
        lg = s.query(ActivityLog).filter(ActivityLog.entity_type == "finished_product", ActivityLog.entity_id == fid,
                                         ActivityLog.old_value == "band: 10").first()
    finally:
        s.close()
    check("B6b jurnalda «band: 10 → 0 … yana 10 ishlab chiqarish kerak»", lg is not None and "band: 0" in (lg.new_value or ""),
          lg and lg.new_value)
    rp = C.post("/api/production/orders", json={"product_type_id": PT, "bom_id": BOM, "quantity": 10,
                                                "source_type": "customer_order", "source_order_id": oid,
                                                "source_order_item_id": iid})
    check("B6c shu detal uchun yangi ishlab chiqarish 10 — qabul qilinadi (ilgari 400 «endi faqat 0»)", rp.status_code == 200,
          (rp.status_code, js(rp)))
    rr = C.post(f"/api/orders/{oid}/ready")
    check("B6d «Tayyor» — 400 «kerak 10, tayyor 0» (to'g'ri: mahsulot yo'q, buyurtma qotmagan)",
          rr.status_code == 400 and "tayyor 0" in str(js(rr)), (rr.status_code, js(rr)))


xav(b6)


def b7():
    f = mrp_tm(10, mijozga=False)
    fid = f["fid"]
    tm_ozgart(fid, reserved_quantity=6.0, reserved_for_order_item_id=None)
    r1 = C.post("/api/finished/loss", json={"finished_product_id": fid, "quantity": 3, "brak_sabab": "boshqa"})
    check("B7 qoldiq 10, band 6 — brak 3: qoldiq 7, band 6 (bo'sh qismdan), band_kamaydi 0",
          r1.status_code == 200 and tm(fid)["q"] == 7 and tm(fid)["band"] == 6 and js(r1).get("band_kamaydi") == 0,
          (r1.status_code, js(r1), tm(fid)))
    r2 = C.post("/api/finished/loss", json={"finished_product_id": fid, "quantity": 3, "brak_sabab": "boshqa"})
    check("B7b yana brak 3 — qoldiq 4, band 4, band_kamaydi 2",
          r2.status_code == 200 and tm(fid)["q"] == 4 and tm(fid)["band"] == 4 and js(r2).get("band_kamaydi") == 2,
          (r2.status_code, js(r2), tm(fid)))


xav(b7)


def b8_b10():
    f = mrp_tm(10)
    fid, iid, oid = f["fid"], f["iid"], f["oid"]
    r = C.post("/api/finished/loss", json={"finished_product_id": fid, "quantity": 10, "brak_sabab": "boshqa"})
    check("B8 «Brak» 10 to'liq band mahsulotda — band 0, band_kamaydi 10",
          r.status_code == 200 and tm(fid)["band"] == 0 and js(r).get("band_kamaydi") == 10, (r.status_code, js(r), tm(fid)))
    rd = C.delete(f"/api/finished/loss/{js(r).get('loss_id')}")
    check("B10 brak bekor qilindi — mahsulot 10, band 10 qaytdi (detalga hali kerak)",
          rd.status_code == 200 and tm(fid)["q"] == 10 and tm(fid)["band"] == 10 and js(rd).get("band_tiklandi") == 10,
          (rd.status_code, js(rd), tm(fid)))
    r = C.post("/api/finished/loss", json={"finished_product_id": fid, "quantity": 10, "brak_sabab": "boshqa"})
    rp = C.post("/api/production/orders", json={"product_type_id": PT, "bom_id": BOM, "quantity": 10,
                                                "source_type": "customer_order", "source_order_id": oid,
                                                "source_order_item_id": iid})
    po = (js(rp).get("production_order") or {}).get("id")
    rs = C.post(f"/api/production/orders/{po}/start")
    rd = C.delete(f"/api/finished/loss/{js(r).get('loss_id')}")
    check("B10b brakdan keyin yangi ishlab chiqarish boshlandi (yangi band 10), so'ng brak bekor — eski mahsulot 10, band 0 "
          "(ortiqcha band yo'q)", rp.status_code == 200 and rs.status_code == 200 and rd.status_code == 200
          and tm(fid)["q"] == 10 and tm(fid)["band"] == 0, (rp.status_code, rs.status_code, rd.status_code, js(rd), tm(fid)))


xav(b8_b10)


def b9():
    f = mrp_tm(10)
    fid = f["fid"]
    r = C.post("/api/finished/loss", json={"finished_product_id": fid, "quantity": 2, "brak_sabab": "boshqa",
                                           "taqdir": {"taqdir": "tuzatildi", "materiallar": [{"inventory_id": TID, "miqdor": 0.1}]}})
    check("B9 to'liq band partiya — brak 2 «Tuzatildi» (o'sha partiyaga qaytdi): band 10 qoladi",
          r.status_code == 200 and tm(fid)["band"] == 10 and tm(fid)["q"] == 10, (r.status_code, js(r), tm(fid)))


xav(b9)


def b12():
    f = mrp_tm(10, mijozga=False)
    fid = f["fid"]
    r = C.post(f"/api/finished/{fid}/reduce", json={"quantity": 11, "brak_sabab": "boshqa"})
    check("B12 qoldiqdan ko'p /reduce — 400, o'zgarmadi", r.status_code == 400 and tm(fid)["q"] == 10, (r.status_code, js(r)))
    yomon = [C.post(f"/api/finished/{fid}/reduce", json=t).status_code for t in (
        {"quantity": "Infinity", "brak_sabab": "boshqa"}, {"quantity": True, "brak_sabab": "boshqa"},
        {"quantity": -1, "brak_sabab": "boshqa"}, {"quantity": 1, "brak_sabab": "boshqa", "reason": "x" * 10001},
        {"quantity": 1, "brak_sabab": "noma'lum"}, {"quantity": 1, "brak_sabab": "boshqa", "finished_product_id": fid + 1},
        {"quantity": 1, "brak_sabab": "boshqa", "taqdir": {"taqdir": "tashlandi"}})]
    check("B12b yomon tanalar — hammasi 400, o'zgarmadi", all(x == 400 for x in yomon) and tm(fid)["q"] == 10, yomon)
    r = C.post("/api/finished/9999999/reduce", json={"quantity": "yomon"})
    check("B12c yo'q id + yomon tana — 404 (tana tekshiruvidan oldin)", r.status_code == 404, r.status_code)
    s = SessionLocal()
    try:
        po = ProductionOrder
        rj = js(C.post("/api/production/orders", json={"product_type_id": PT, "bom_id": BOM, "quantity": 2,
                                                         "source_type": "warehouse_stock"}))
        pid = (rj.get("production_order") or {}).get("id")
        C.post(f"/api/production/orders/{pid}/start")
        jf = s.get(po, pid).finished_product_id
    finally:
        s.close()
    r = C.post(f"/api/finished/{jf}/reduce", json={"quantity": 1, "brak_sabab": "boshqa"})
    check("B12d ishlab chiqarilayotgan mahsulot /reduce — 400", r.status_code == 400, (r.status_code, js(r)))


xav(b12)


def b14():
    f = mrp_tm(10, mijozga=False)
    fid = f["fid"]
    s = SessionLocal()
    try:
        n = crud.reduce_production(s, fid, 1, "x", company_id=1)
    finally:
        s.close()
    check("B14 to'g'ridan-to'g'ri crud.reduce_production(db, id, 1, 'x') — brak yozuvi bor, tannarx kamaydi (27 000)",
          isinstance(n, dict) and n.get("success") and len(yoqotishlar(fid)) == 1 and tm(fid)["cost"] == 27000, (n, tm(fid)))


xav(b14)

section("R — `/reduce` ruxsati = «Brak: Yaratish» (`/loss` bilan bir xil)")


def r_ruxsat():
    s = SessionLocal()
    try:
        uid = s.query(User.id).filter(User.username == "ao1_rol").scalar()
    finally:
        s.close()
    r1 = C.post("/api/rollar", json={"nom": "AO1 Tayyor tahrir", "ruxsatlar": {"tayyor": ["korish", "tahrirlash"]}})
    r2 = C.post("/api/rollar", json={"nom": "AO1 Brakchi", "ruxsatlar": {"tayyor": ["korish"], "brak": ["yaratish"]}})
    check("R0 fikstura: ikki rol yaratildi", r1.status_code == 200 and r2.status_code == 200, (js(r1), js(r2)))
    f = mrp_tm(10, mijozga=False)
    fid = f["fid"]
    C.put(f"/api/users/{uid}/rol", json={"rol_id": js(r1).get("id")})
    k = kirish("ao1_rol")
    r = k.post(f"/api/finished/{fid}/reduce", json={"quantity": 1, "brak_sabab": "boshqa"})
    check("R1 «Tayyor mahsulotlar: Tahrirlash» bor, «Brak: Yaratish» yo'q — /reduce 403, o'zgarmadi",
          r.status_code == 403 and tm(fid)["q"] == 10, (r.status_code, js(r)))
    C.put(f"/api/users/{uid}/rol", json={"rol_id": js(r2).get("id")})
    r = k.post(f"/api/finished/{fid}/reduce", json={"quantity": 1, "brak_sabab": "boshqa"})
    check("R2 «Brak: Yaratish» bor — /reduce 200", r.status_code == 200 and tm(fid)["q"] == 9, (r.status_code, js(r)))


xav(r_ruxsat)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C — eski sessiya: mahsulot qatori qulf ostida bazadan QAYTA o'qiladi")


def c_eski(etiket, amal, kutilgan_q):
    _p = penoplast_tm(f"AO1 C {etiket}")
    fid = _p[2]
    s = SessionLocal()
    try:
        _eski = s.get(FinishedProduct, fid)                 # S1 mahsulotni OLDIN o'qigan (havola saqlanadi)
        q_s1 = float(_eski.quantity)
        r = sotish(fid, 3, narx=1_000_000)                  # S2 (HTTP) — 3 sotildi, commit
        n = amal(s, fid)
    finally:
        s.close()
    check(f"{etiket}: S2 sotuvi (3) yo'qolmadi — yakuniy qoldiq {kutilgan_q:g}",
          r.status_code == 200 and tm(fid)["q"] == kutilgan_q, (r.status_code, q_s1, tm(fid), str(n)[:200]))
    return fid, n


xav(lambda: c_eski("C1 add_to_production (+1)", lambda s, f: crud.add_to_production(s, f, 1, company_id=1), 8.0))


def _c2(s, f):
    d = schemas.FinishedProductLossCreate(finished_product_id=f, quantity=1, brak_sabab="boshqa")
    return crud.record_finished_product_loss(s, d, created_by="C2", company_id=1)


_c2n = xav(lambda: c_eski("C2 record_finished_product_loss (−1)", _c2, 6.0), (None, None))


def _c3(s, f):
    d = schemas.FinishedProductSaleCreate(finished_product_id=f, quantity=1, unit_price=1_000_000, payment_method="naqd",
                                          confirm_below_cost=True)
    return crud.sell_finished_product(s, d, created_by="C3", company_id=1)


xav(lambda: c_eski("C3 sell_finished_product (−1)", _c3, 6.0))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    section("P — parallel poygalar (PG)")

    def poyga(fn_a, fn_b, kech=1.0, b_kechikish=0.3):
        nat = [None, None]
        bar = threading.Barrier(2)

        def t_a():
            sess = SessionLocal()
            asl = sess.commit

            def sek():
                time.sleep(kech)
                asl()
            sess.commit = sek
            try:
                bar.wait(timeout=30)
                nat[0] = fn_a(sess)
            except Exception as e:         # noqa: BLE001
                nat[0] = f"ISTISNO {type(e).__name__}: {e}"
            finally:
                sess.close()

        def t_b():
            bar.wait(timeout=30)
            time.sleep(b_kechikish)
            try:
                nat[1] = fn_b()
            except Exception as e:         # noqa: BLE001
                nat[1] = f"ISTISNO {type(e).__name__}: {e}"
        ts = [threading.Thread(target=t_a), threading.Thread(target=t_b)]
        [x.start() for x in ts]
        [x.join(timeout=120) for x in ts]
        return nat

    def p1(urinish):
        _p = penoplast_tm(f"AO1 P1 Karniz {urinish}")
        fid = _p[2]
        C.post(f"/api/finished/{fid}/add", json={"quantity": 90})          # qoldiq 100
        q0 = tm(fid)["q"]
        d = schemas.FinishedProductSaleCreate(finished_product_id=fid, quantity=5, unit_price=1_000_000, payment_method="naqd",
                                              confirm_below_cost=True)
        n = poyga(lambda s: crud.sell_finished_product(s, d, created_by="A", company_id=1),
                  lambda: C.post(f"/api/finished/{fid}/add", json={"quantity": 2}))
        check(f"P1 #{urinish} sotuv 5 (qulf ushlaydi) ∥ «+» 2 — {q0:g} → {q0 - 5 + 2:g} (sotuv yo'qolmadi)",
              getattr(n[1], "status_code", 0) == 200 and tm(fid)["q"] == q0 - 5 + 2,
              (q0, tm(fid), n[0] if isinstance(n[0], (str, dict)) else n[0], getattr(n[1], "status_code", n[1])))
    for _u in (1, 2):
        xav(lambda u=_u: p1(u))

    def p2():
        f = mrp_tm(10, mijozga=False)
        fid = f["fid"]
        d = schemas.FinishedProductLossCreate(finished_product_id=fid, quantity=6, brak_sabab="boshqa")
        n = poyga(lambda s: crud.record_finished_product_loss(s, d, created_by="A", company_id=1),
                  lambda: C.post(f"/api/finished/{fid}/reduce", json={"quantity": 6, "brak_sabab": "boshqa"}))
        check("P2 «Brak» 6 (qulf ushlaydi) ∥ /reduce 6 (qoldiq 10) — ikkinchisi 400, qoldiq 4, brak yozuvi 1 ta",
              isinstance(n[0], dict) and n[0].get("success") and getattr(n[1], "status_code", 0) == 400
              and tm(fid)["q"] == 4 and len(yoqotishlar(fid)) == 1,
              (n[0], getattr(n[1], "status_code", n[1]), js(n[1]) if hasattr(n[1], "json") else None, tm(fid)))
    xav(p2)
else:
    print("\n  (SQLite — parallel poygalar P o'tkazib yuborildi; PG_URL bilan ishga tushiring)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — statik (manba)")
_ms = manba(crud.sell_finished_product)
check("S1 sell_finished_product: tekshiruv `_fp_bosh_qoldiq(fp)` bilan (qulfdan keyin)",
      tartibda(_ms, "get_finished_product(db, data.finished_product_id, company_id, lock=True)",
               "if data.quantity > _fp_bosh_qoldiq(fp) + 0.001:"))
_mg = manba(crud.get_finished_product)
_mg = _mg.split('"""')[-1] if _mg.count('"""') >= 2 else _mg
# kech145 (zip 182, MOSLANDI): FOR NO KEY UPDATE (`key_share=True`) — tashqi kalit KEY SHARE bilan to'qnashmaydi
check("S1b get_finished_product(lock=True): flush, so'ng populate_existing + FOR NO KEY UPDATE",
      tartibda(_mg, "if lock:", "db.flush()", "populate_existing().with_for_update(key_share=True)"))
_mb = manba(crud.sell_finished_products_batch)
check("S2 sell_finished_products_batch: `_fp_bosh_qoldiq` va eski yozuv tannarxi JAMI qoldiqqa bo'linadi",
      "available = _fp_bosh_qoldiq(fp)" in _mb and "unit_cost = float(fp.cost_price or 0) / _jami_qoldiq142" in _mb)
_ma = manba(crud.add_to_production)
check("S3 add_to_production: mahsulot QULF bilan o'qiladi", "get_finished_product(db, fp_id, company_id, lock=True)" in _ma)
_ml = manba(crud.record_finished_product_loss)
check("S4 record_finished_product_loss: band moslash taqdirdan KEYIN, commit dan OLDIN",
      tartibda(_ml, "_taqdir_natija", "_fp_band_qoldiqqa_moslash(db, fp", "db.commit()"))
_mr = manba(crud.reduce_production)
_mr_kod = _mr.split('"""')[-1] if _mr.count('"""') >= 2 else _mr
check("S5 reduce_production — «Brak» yo'li (`record_finished_product_loss`), o'zi qoldiq yozmaydi",
      "record_finished_product_loss(" in _mr_kod and "fp.quantity =" not in _mr_kod)
_mx = manba(main.api_reduce_production)
check("S6 /reduce marshruti: ruxsat «brak / yaratish», sabab majburiy, bitta tranzaksiya",
      'auth.ruxsat("brak", "yaratish")' in _mx and "BRAK_SABABI_XATO" in _mx and "bitta_tranzaksiya" in _mx)
_md = manba(crud.delete_finished_product_loss)
check("S7 delete_finished_product_loss: buyurtma detali qatori TM dan OLDIN qulflanadi (detal → TM)",
      tartibda(_md, "OrderItem", "with_for_update()", "FinishedProduct.id == loss.finished_product_id",
               "with_for_update(key_share=True)"))      # kech145 (zip 182, MOSLANDI): TM — FOR NO KEY UPDATE

section("X — umumiy")
check("X1 butun yurishda 5xx javob yo'q", not SERVER_500, SERVER_500[:5])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
