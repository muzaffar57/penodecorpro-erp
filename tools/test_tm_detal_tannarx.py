#!/usr/bin/env python3
"""
test_tm_detal_tannarx.py — 5-bo'lim 56-band + K103-1 darvozasi (kech103, 2026-09-28): "Tayyor mahsulotdan"
olingan detal tannarxi OLINGAN paytda muzlaydi.

NIMA UCHUN (asl kod `d081624` = zip 96 da O'LCHANGAN — `work/probe56tm.py`, SQLite = PG)
------------------------------------------------------------------------------------------
Tayyor mahsulot (TM) 1 birlik tannarxi — og'irlikli o'rtacha (`unit_cost_stable`, 47-band). TM ga keyin
boshqa narxda partiya ("+" qo'shish) yoki qaytgan mahsulot qo'shilsa o'rtacha o'zgaradi va:
  * S1: 10 m × 7 600 = 76 000 ga olingan (va «Tayyor» qilingan) buyurtma tannarxi +20 m (narx x2) dan keyin
    89 818 bo'lib qoldi — o'tgan oy hisoboti ham o'zgarardi; qiymat balansi (kirgan = omborda + buyurtmalar +
    sotuvlar) −13 818;
  * S2: shu buyurtmadan 5 m omborga qaytsa qaytarish tannarxi 44 909 (olingani 38 000);
  * S3: +10 m dan keyin o'chirilgan buyurtmaning 10 m i 89 818 ga olinib 102 380 bo'lib qaytdi (+12 562 "havodan");
  * S4 (tahrir), S5 (tiklash), S6 (qisman «Tayyor»), S7 (qaytgan TM ga yana qaytarish qo'shilsa undan olingan
    buyurtma) — hammasida detal JORIY o'rtachada qayta baholanardi (balans −34 545 … −43 452).
  * K103-1 (S10): detal tahriri `PUT /api/order-items/{id}` TM li detalda TM omborini UMUMAN o'zgartirmasdi
    (10 → 15 m: 5 m yechilmadi, buyurtma tannarxi esa 15 m; 15 → 8: 7 m qaytmadi) — balans −87 431.

YECHIM (texnik — Claude; 32 / 34 / 47-band qarorlari "ishlatilgan paytdagi narxda" bilan bir xil):
  * `order_items.fp_unit_cost` — detal olingan paytdagi birlik (yangi partiya olinsa — detal bo'yicha og'irlikli);
  * buyurtma foydasi, omborga qaytgan mahsulot tannarxi (`muzlatilgan=True`) — shu birlik; brak summasi va TM
    sotuvi — avvalgidek JORIY o'rtacha (13-band 2-qadam, 47-band);
  * o'chirish / qisman «Tayyor» / tahrir / detal tahriri — qaytgan qism detal birligida, TM o'rtachasi og'irlikli
    qayta hisoblanadi; tiklash va yangi olingan qism — TM ning shu paytdagi o'rtachasi;
  * `update_order_item` — TM farqi (`_adjust_finished_diff`, to'liq tahrir bilan bitta yo'l);
  * `main._migrate_tm_detal_tannarx` — bo'sh (NULL) eski detallar BUGUNGI qiymatda (deploy paytida raqam o'zgarmaydi).

ORAKUL — QIYMAT BALANSI: kirgan TM qiymati (ishlab chiqarish + "+" partiyalari) = Σ TM cost_price + Σ hisobotdagi
buyurtmalar tannarxi (faqat TM detalli buyurtmalar) + Σ TM sotuvi tannarxi; farq ≤ bir necha tiyin (4 xonali birlik).

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_tm_detal_tannarx.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tm_detal_tannarx.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tm_detal_tannarx_test"
_DB = os.path.join(tempfile.gettempdir(), "tm_detal_tannarx_test.db")

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
from datetime import datetime                      # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, services                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, Recipe, RecipeIngredient, ReturnItem, FinishedProduct, FinishedProductSale,
    Order, OrderItem, OrderStatus, Master, StockSource, ProductionStatus,
)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
STATUSLAR = []


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
    STATUSLAR.append((metod, url, r.status_code))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def taxminan(a, b, eps=0.02):
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


def manba(f):
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
_db.add(Company(id=2, name="TD Korxona B"))          # PG: users.company_id FK — B korxonasi oldin
_db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TD_admin", "Parol123!", UserRole.ADMIN, "TD Admin", company_id=1)
PRJS = [Project(company_id=1, client_name=f"TD Mijoz {i}", project_name=f"TD loyiha {i}", total_budget=0,
                total_paid=0) for i in range(16)]
PENO = Inventory(company_id=1, item_name="TD Penoplast", unit="blok", stock_quantity=100_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TD Kley", unit="kg", stock_quantity=1_000_000, price_per_unit=2_000,
                 category="Kimyo")
AKR = Inventory(company_id=1, item_name="TD Akril", unit="kg", stock_quantity=1_000_000, price_per_unit=10_000,
                category="Kimyo")
USTA = Master(company_id=1, name="TD Usta", phone="+998917770001", kpi_percent=10.0, is_active=True)
_db.add_all(PRJS + [PENO, KLEY, AKR, USTA])
_db.commit()
R1 = Recipe(company_id=1, name="TD R1", batch_size_kg=100.0)
_db.add(R1)
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0)])
_db.commit()
ID = dict(PENO=PENO.id, KLEY=KLEY.id, AKR=AKR.id, R1=R1.id, USTA=USTA.id)
PRJ = [p.id for p in PRJS]
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r = req(C, "post", "/login", data={"username": "TD_admin", "password": "Parol123!"}, follow_redirects=False)
if _r.status_code != 302:
    print(f"LOGIN BO'LMADI: {_r.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]
_p = [0]


def nom():
    _n[0] += 1
    return f"TD_D{_n[0]}"


def loyiha():
    _p[0] += 1
    return PRJ[_p[0] - 1]


def narx(k):
    d = SessionLocal()
    try:
        d.get(Inventory, ID["PENO"]).price_per_unit = 500_000 * k
        d.get(Inventory, ID["KLEY"]).price_per_unit = 2_000 * k
        d.get(Inventory, ID["AKR"]).price_per_unit = 10_000 * k
        d.commit()
    finally:
        d.close()


def tm(fid):
    """(quantity, cost_price, unit_cost_stable yoki None)"""
    d = SessionLocal()
    try:
        f = d.get(FinishedProduct, fid)
        if f is None:
            return (None, None, None)
        ucs = float(f.unit_cost_stable) if f.unit_cost_stable is not None else None
        return (float(f.quantity or 0), float(f.cost_price or 0), ucs)
    finally:
        d.close()


def birlik(iid):
    d = SessionLocal()
    try:
        it = d.get(OrderItem, iid)
        v = getattr(it, "fp_unit_cost", None) if it is not None else None
        return float(v) if v is not None else None
    finally:
        d.close()


def core_detal(iid, **qiymat):
    """Core bilan detal ustunlarini yozadi (eski / buzilgan holat). Asl kodda ustun yo'q — jim o'tkaziladi."""
    _s = SessionLocal()
    try:
        _s.execute(OrderItem.__table__.update().where(OrderItem.__table__.c.id == iid).values(**qiymat))
        _s.commit()
        return True
    except Exception as e:                 # noqa: BLE001
        _s.rollback()
        print("  (core_detal:", type(e).__name__, str(e)[:120], ")")
        return False
    finally:
        _s.close()


KIRDI = [0.0]


def ishlab(uzunlik):
    r = req(C, "post", "/api/finished/produce", json={"name": "TD TM profil", "category": "profil", "width": 20,
                                                       "thickness": 10, "length": uzunlik, "is_coated": True,
                                                       "penoplast_id": ID["PENO"], "unit_price": 0,
                                                       "loy_kg": uzunlik / 2, "recipe_id": ID["R1"]})
    d = js(r) or {}
    fid = d.get("product_id")
    req(C, "post", f"/api/finished/{fid}/complete")
    KIRDI[0] += tm(fid)[1] or 0
    return fid


def qosh(fid, miqdor):
    oldin = tm(fid)[1]
    r = req(C, "post", f"/api/finished/{fid}/add", json={"quantity": miqdor})
    keyin = tm(fid)[1]
    KIRDI[0] += keyin - oldin
    return r.status_code


def buyurtma(fid, uzunlik, usta=None, narxi=20_000):
    t = {"project_id": loyiha(), "order_type": "product", "recipe_id": ID["R1"], "loy_kg": 0,
         "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": uzunlik,
                    "quantity": 1, "unit_price": narxi, "is_coated": True, "penoplast_id": ID["PENO"],
                    "finished_product_id": fid}]}
    if usta:
        t["master_id"] = usta
    r = req(C, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
    d = js(r) or {}
    it = (d.get("items") or [{}])[0] if isinstance(d, dict) else {}
    return r.status_code, (d.get("id") if isinstance(d, dict) else None), it.get("id"), it.get("name"), t


def detal(fid, uzunlik, nomi=None):
    return {"name": nomi or nom(), "category": "profil", "width": 20, "thickness": 10, "length": uzunlik,
            "quantity": 1, "unit_price": 20_000, "is_coated": True, "penoplast_id": ID["PENO"],
            "finished_product_id": fid}


def buyurtma_kop(detallar):
    t = {"project_id": loyiha(), "order_type": "product", "recipe_id": ID["R1"], "loy_kg": 0, "items": detallar}
    r = req(C, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
    d = js(r) or {}
    ids = [x.get("id") for x in (d.get("items") or [])] if isinstance(d, dict) else []
    return r.status_code, (d.get("id") if isinstance(d, dict) else None), ids, t


def detal_idlari(oid):
    s = SessionLocal()
    try:
        return {it.name: it.id for it in s.query(OrderItem).filter(OrderItem.order_id == oid).all()}
    finally:
        s.close()


def tahrir(oid, tana, uzunlik):
    t = dict(tana)
    t["items"] = [dict(tana["items"][0], length=uzunlik)]
    return req(C, "put", f"/api/orders/{oid}", json=t, params={"confirm_shortage": "true"}).status_code


def tan(oid):
    d = js(req(C, "get", f"/api/orders/{oid}/profit")) or {}
    try:
        return float(d.get("tan_narxi"))
    except Exception:                      # noqa: BLE001
        return None


def yuk(oid, iid, miqdor):
    r = req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom(),
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    return r.status_code


def qaytar(oid, iid, nomi, miqdor, sabab="Ortiqcha", ombor=True):
    r = req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": iid, "item_name": nomi,
                                             "quantity": miqdor, "unit": "metr", "reason": sabab,
                                             "refund_amount": 0, "to_stock": ombor})
    d = js(r) or {}
    rid = d.get("id") if (r.status_code == 200 and isinstance(d, dict)) else None
    fp = sc = summa = None
    if rid:
        s = SessionLocal()
        try:
            ri = s.get(ReturnItem, rid)
            fp = ri.finished_product_id
            sc = float(ri.stock_cost) if ri.stock_cost is not None else None
            summa = float(ri.refund_amount) if ri.refund_amount is not None else None
        finally:
            s.close()
    return r.status_code, rid, fp, sc, summa


def balans():
    """KIRDI − (Σ TM cost_price + Σ hisobotdagi buyurtmalar tannarxi + Σ sotuv tannarxi) — faqat 1-korxona."""
    s = SessionLocal()
    try:
        tmq = sum(float(f.cost_price or 0) for f in s.query(FinishedProduct).filter(FinishedProduct.company_id == 1).all())
        sot = sum(float(x.cost_amount or 0) for x in
                  s.query(FinishedProductSale).filter(FinishedProductSale.company_id == 1).all())
        # qoralama — hech narsa olinmagan (hisobotda ham yo'q); o'chirilgan, lekin topshirilgan qismi bilan
        # yakunlangan (READY / DELIVERED — 93 "A") — hisobotda qoladi
        faol = [o.id for o in s.query(Order).filter(Order.company_id == 1).all()
                if o.status != OrderStatus.DRAFT
                and ((not o.is_deleted) or o.status in (OrderStatus.READY, OrderStatus.DELIVERED))]
    finally:
        s.close()
    buy = sum(float(tan(o) or 0) for o in faol)
    return round(KIRDI[0] - (tmq + buy + sot), 2)


def hisobot_ishlab():
    n = datetime.utcnow()
    d = js(req(C, "get", "/api/finance/report", params={"year": n.year, "month": n.month})) or {}
    return d.get("ishlab_chiqarish_xarajat")


def usta_oy():
    n = datetime.utcnow()
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            k = services.calculate_monthly_master_kpi(s, n.year, n.month, company_id=1)
    finally:
        s.close()
    oy = [b for b in (k.get("breakdown") or []) if b.get("master_name") == "TD Usta"]
    return float(oy[0]["monthly_profit"]) if oy else None


# ══════════════════════════════════════════════════════════════
section("0. NAZORAT — o'rtacha o'zgarmaydi: avvalgi natijalar AYNAN")
# ══════════════════════════════════════════════════════════════
narx(1)
N0 = ishlab(100)
check("00 TM 100 m / 760 000, birlik 7 600", tm(N0) == (100.0, 760_000.0, 7_600.0), tm(N0))
s, O0, I0, _, T0 = buyurtma(N0, 10)
check("01 buyurtma 200, tannarx 76 000, detal birligi 7 600", s == 200 and taxminan(tan(O0), 76_000)
      and taxminan(birlik(I0), 7_600), (s, tan(O0), birlik(I0)))
check("02 TM 90 / 684 000 / 7 600", tm(N0) == (90.0, 684_000.0, 7_600.0), tm(N0))
check("03 tahrir 10 → 12: 200, TM 88 / 668 800, buyurtma 91 200", tahrir(O0, T0, 12) == 200
      and tm(N0) == (88.0, 668_800.0, 7_600.0) and taxminan(tan(O0), 91_200), (tm(N0), tan(O0)))
check("04 tahrir 12 → 9: 200, TM 91 / 691 600, buyurtma 68 400, birlik 7 600", tahrir(O0, T0, 9) == 200
      and tm(N0) == (91.0, 691_600.0, 7_600.0) and taxminan(tan(O0), 68_400) and taxminan(birlik(I0), 7_600),
      (tm(N0), tan(O0), birlik(I0)))
r = req(C, "delete", f"/api/orders/{O0}")
check("05 o'chirish 200 — TM AYNAN asli: 100 / 760 000 / 7 600 (o'rtacha qayta yozilmadi)",
      r.status_code == 200 and tm(N0) == (100.0, 760_000.0, 7_600.0), (r.status_code, tm(N0)))
check("06 balans 0", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("A. «Tayyor» buyurtma; TM ga narx x2 da +20 m — tannarx, oylik hisobot, usta KPI O'ZGARMAYDI (S1)")
# ══════════════════════════════════════════════════════════════
FP = ishlab(100)
s, O1, I1, N1, T1 = buyurtma(FP, 10, usta=ID["USTA"], narxi=300_000)
r = req(C, "post", f"/api/orders/{O1}/ready")
check("A0 buyurtma + «Tayyor» 200, tannarx 76 000", s == 200 and r.status_code == 200 and taxminan(tan(O1), 76_000),
      (s, r.status_code, tan(O1)))
H_OLDIN = hisobot_ishlab()
U_OLDIN = usta_oy()
narx(2)
check("A1 +20 m (narx x2) 200", qosh(FP, 20) == 200)
check("A2 TM o'rtachasi o'zgardi: 110 m / 988 000 / 8 981.8182", tm(FP)[0] == 110.0 and taxminan(tm(FP)[1], 988_000)
      and taxminan(tm(FP)[2], 8_981.8182, 0.0001), tm(FP))
check("A3 buyurtma tannarxi 76 000 (asl: 89 818.18)", taxminan(tan(O1), 76_000), tan(O1))
check("A4 detal birligi 7 600 (olingan paytdagi)", taxminan(birlik(I1), 7_600), birlik(I1))
check("A5 oylik hisobot ishlab chiqarish xarajati O'ZGARMADI", H_OLDIN is not None and taxminan(hisobot_ishlab(), H_OLDIN),
      (H_OLDIN, hisobot_ishlab()))
check("A6 usta KPI oylik foyda O'ZGARMADI (300 000 − 76 000)", U_OLDIN is not None and taxminan(usta_oy(), U_OLDIN)
      and taxminan(U_OLDIN, 224_000, 1), (U_OLDIN, usta_oy()))
check("A7 balans 0 (asl: −13 818.18)", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("B. Shu buyurtmadan 5 m omborga qaytadi (S2, K59-2 / 34-band)")
# ══════════════════════════════════════════════════════════════
s, RB, RFP, SC, _ = qaytar(O1, I1, N1, 5)
check("B0 qaytarish 200, yangi qaytgan TM", s == 200 and RFP and RFP != FP, (s, RFP))
check("B1 qaytarish tannarxi 38 000 (asl: 44 909.09 — joriy o'rtacha)", taxminan(SC, 38_000), SC)
check("B2 qaytgan TM 5 / 38 000, birlik 7 600", tm(RFP) == (5.0, 38_000.0, 7_600.0), tm(RFP))
check("B3 buyurtma tannarxi 38 000 (76 000 − 38 000; asl: 44 909.09)", taxminan(tan(O1), 38_000), tan(O1))
check("B4 balans 0", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("C. Buyurtma o'chiriladi (topshirilmagan) — o'rtacha o'zgargandan keyin (S3)")
# ══════════════════════════════════════════════════════════════
Q, Cc, Y = tm(FP)
s, O2, I2, _, _ = buyurtma(FP, 10)
check("C0 buyurtma 200, birlik = TM o'rtachasi", s == 200 and taxminan(birlik(I2), Y, 0.0001), (birlik(I2), Y))
C2 = 10 * Y
narx(3)
check("C1 +10 m (narx x3) 200", qosh(FP, 10) == 200)
check("C2 buyurtma tannarxi o'zgarmadi (asl: 102 380.16)", taxminan(tan(O2), C2), (tan(O2), C2))
Q, Cc, Yn = tm(FP)
r = req(C, "delete", f"/api/orders/{O2}")
_kut_c = Cc + C2
_kut_y = (Yn * Q + C2) / (Q + 10)
check("C3 o'chirish 200 — TM +10 m, tannarx + olingan qiymat (asl: + joriy o'rtachada)",
      r.status_code == 200 and tm(FP)[0] == Q + 10 and taxminan(tm(FP)[1], _kut_c), (r.status_code, tm(FP), _kut_c))
check("C4 TM o'rtachasi og'irlikli qayta hisoblandi", taxminan(tm(FP)[2], _kut_y, 0.0001), (tm(FP)[2], _kut_y))
check("C5 balans 0 (asl: −38 942.16)", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("D. To'liq tahrir 10 → 15 → 8 m, orada yangi partiya (S4)")
# ══════════════════════════════════════════════════════════════
Y3 = tm(FP)[2]
s, O3, I3, N3, T3 = buyurtma(FP, 10)
check("D0 buyurtma 200", s == 200 and taxminan(tan(O3), 10 * Y3), (tan(O3), 10 * Y3))
narx(1)
check("D1 +10 m (narx x1) 200", qosh(FP, 10) == 200)
Q, Cc, Y3b = tm(FP)
check("D2 tahrir 10 → 15: 200", tahrir(O3, T3, 15) == 200)
_k15 = 10 * Y3 + 5 * Y3b
check("D3 buyurtma tannarxi = 10 × eski + 5 × yangi o'rtacha (asl: 15 × yangi)", taxminan(tan(O3), _k15),
      (tan(O3), _k15))
check("D4 TM −5 m, tannarx −5 × o'rtacha", tm(FP)[0] == Q - 5 and taxminan(tm(FP)[1], Cc - 5 * Y3b), (tm(FP), Cc))
check("D5 balans 0", taxminan(balans(), 0), balans())
Q, Cc, Yd = tm(FP)
check("D6 tahrir 15 → 8: 200", tahrir(O3, T3, 8) == 200)
_c8 = _k15 / 15
check("D7 buyurtma tannarxi 8 × detal birligi (asl: 8 × joriy o'rtacha)", taxminan(tan(O3), 8 * _c8),
      (tan(O3), 8 * _c8))
check("D8 TM +7 m detal birligida, o'rtacha og'irlikli", tm(FP)[0] == Q + 7 and taxminan(tm(FP)[1], Cc + 7 * _c8)
      and taxminan(tm(FP)[2], (Yd * Q + 7 * _c8) / (Q + 7), 0.0001), (tm(FP), Cc + 7 * _c8))
check("D9 balans 0", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("D2. To'liq tahrir: TM li detal O'CHIRILIB, boshqa TM dan yangi detal qo'shiladi")
# ══════════════════════════════════════════════════════════════
TM2 = ishlab(50)
Yx = tm(FP)[2]
_dx = detal(FP, 10, "TD_X")
s, O11, _ids11, T11 = buyurtma_kop([_dx])
check("D2a buyurtma 200, X birligi = FP o'rtachasi", s == 200 and taxminan(birlik(_ids11[0]), Yx, 0.0001),
      (s, birlik(_ids11[0]) if _ids11 else None, Yx))
narx(2)
check("D2b +10 m FP (narx x2) 200", qosh(FP, 10) == 200)
Q, Cc, Yxb = tm(FP)
Q2, C2t, Y2t = tm(TM2)
T11b = dict(T11)
T11b["items"] = [detal(TM2, 8, "TD_Y")]
r = req(C, "put", f"/api/orders/{O11}", json=T11b, params={"confirm_shortage": "true"})
_iy = detal_idlari(O11).get("TD_Y")
check("D2c tahrir 200 — X o'chdi: FP +10 m X birligida, o'rtacha og'irlikli",
      r.status_code == 200 and tm(FP)[0] == Q + 10 and taxminan(tm(FP)[1], Cc + 10 * Yx)
      and taxminan(tm(FP)[2], (Yxb * Q + 10 * Yx) / (Q + 10), 0.0001), (r.status_code, tm(FP), r.text[:200]))
check("D2d TM2 −8 m, Y birligi = TM2 o'rtachasi", tm(TM2)[0] == Q2 - 8 and taxminan(tm(TM2)[1], C2t - 8 * Y2t)
      and taxminan(birlik(_iy), Y2t, 0.0001), (tm(TM2), birlik(_iy), Y2t))
check("D2e buyurtma tannarxi 8 × TM2 o'rtachasi", taxminan(tan(O11), 8 * Y2t), (tan(O11), 8 * Y2t))
check("D2f balans 0", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("D3. Bir TM dan ikki detal: A 10 → 5, B 5 → 10 (sof farq 0), o'rtacha o'zgargandan keyin")
# ══════════════════════════════════════════════════════════════
Ya = tm(FP)[2]
s, O12, _ids12, T12 = buyurtma_kop([detal(FP, 10, "TD_A"), detal(FP, 5, "TD_B")])
check("D3a buyurtma 200, ikkala birlik = o'rtacha", s == 200 and all(taxminan(birlik(i), Ya, 0.0001) for i in _ids12),
      (s, [birlik(i) for i in _ids12], Ya))
narx(3)
check("D3b +10 m FP (narx x3) 200", qosh(FP, 10) == 200)
Q, Cc, Yab = tm(FP)
T12b = dict(T12)
T12b["items"] = [detal(FP, 5, "TD_A"), detal(FP, 10, "TD_B")]
r = req(C, "put", f"/api/orders/{O12}", json=T12b, params={"confirm_shortage": "true"})
_Y3 = (Yab * Q + 5 * Ya) / (Q + 5)
check("D3c tahrir 200 — FP miqdori O'ZGARMADI, tannarx: +5 × A birligi − 5 × yangi o'rtacha",
      r.status_code == 200 and tm(FP)[0] == Q and taxminan(tm(FP)[1], Cc + 5 * Ya - 5 * _Y3),
      (r.status_code, tm(FP), Cc + 5 * Ya - 5 * _Y3, r.text[:200]))
check("D3d FP o'rtachasi — A qaytgani bilan og'irlikli", taxminan(tm(FP)[2], _Y3, 0.0001), (tm(FP)[2], _Y3))
_i12 = detal_idlari(O12)
check("D3e A birligi o'zgarmadi, B — 5 × eski + 5 × yangi o'rtacha", taxminan(birlik(_i12.get("TD_A")), Ya, 0.0001)
      and taxminan(birlik(_i12.get("TD_B")), (5 * Ya + 5 * _Y3) / 10, 0.0001),
      (birlik(_i12.get("TD_A")), birlik(_i12.get("TD_B")), Ya, _Y3))
check("D3f buyurtma tannarxi 5 × A + 10 × B", taxminan(tan(O12), 5 * Ya + 5 * Ya + 5 * _Y3), tan(O12))
check("D3g balans 0", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("E. 4 m topshirilib o'chiriladi, yangi partiya, tiklanadi (S5)")
# ══════════════════════════════════════════════════════════════
Y4 = tm(FP)[2]
s, O4, I4, _, _ = buyurtma(FP, 10)
check("E0 buyurtma 200 + yuk 4 m 200", s == 200 and yuk(O4, I4, 4) == 200)
Q, Cc, _ = tm(FP)
r = req(C, "delete", f"/api/orders/{O4}")
check("E1 o'chirish 200 — qolgan 6 m detal birligida qaytdi", r.status_code == 200 and tm(FP)[0] == Q + 6
      and taxminan(tm(FP)[1], Cc + 6 * Y4), (r.status_code, tm(FP), Cc + 6 * Y4))
check("E2 balans 0 (topshirilgan 4 m hisobotda)", taxminan(balans(), 0), balans())
narx(2)
check("E3 +10 m (narx x2) 200", qosh(FP, 10) == 200)
Q, Cc, Y4b = tm(FP)
r = req(C, "post", f"/api/orders/{O4}/restore")
_k4 = 4 * Y4 + 6 * Y4b
check("E4 tiklash 200 — 6 m joriy o'rtachada qayta olindi", r.status_code == 200 and tm(FP)[0] == Q - 6
      and taxminan(tm(FP)[1], Cc - 6 * Y4b), (r.status_code, tm(FP)))
check("E5 buyurtma tannarxi 4 × eski + 6 × yangi (asl: 10 × yangi)", taxminan(tan(O4), _k4), (tan(O4), _k4))
check("E6 detal birligi og'irlikli", taxminan(birlik(I4), _k4 / 10, 0.0001), (birlik(I4), _k4 / 10))
check("E7 balans 0", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("F. Qisman «Tayyor»: 4 m topshirilgan, yangi partiyadan keyin 6 m qaytadi (S6)")
# ══════════════════════════════════════════════════════════════
Y5 = tm(FP)[2]
s, O5, I5, _, _ = buyurtma(FP, 10)
check("F0 buyurtma 200 + yuk 4 m 200", s == 200 and yuk(O5, I5, 4) == 200)
narx(1)
check("F1 +10 m (narx x1) 200", qosh(FP, 10) == 200)
Q, Cc, Y5b = tm(FP)
r = req(C, "post", f"/api/orders/{O5}/ready")
check("F2 qisman «Tayyor» 200 — 6 m detal birligida qaytdi", r.status_code == 200 and tm(FP)[0] == Q + 6
      and taxminan(tm(FP)[1], Cc + 6 * Y5), (r.status_code, tm(FP), Cc + 6 * Y5))
check("F3 buyurtma tannarxi 4 × olingan birlik (asl: 4 × joriy)", taxminan(tan(O5), 4 * Y5), (tan(O5), 4 * Y5))
check("F4 TM o'rtachasi og'irlikli", taxminan(tm(FP)[2], (Y5b * Q + 6 * Y5) / (Q + 6), 0.0001), tm(FP))
check("F5 balans 0", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("G. Qaytgan TM dan olingan buyurtma; o'sha TM ga yana qaytarish qo'shiladi (S7)")
# ══════════════════════════════════════════════════════════════
YR = tm(RFP)[2]
s, O6, I6, _, _ = buyurtma(RFP, 3)
check("G0 buyurtma 200, tannarx 3 × 7 600", s == 200 and taxminan(tan(O6), 3 * YR) and taxminan(YR, 7_600),
      (tan(O6), YR))
s, RG, RFP2, SC2, _ = qaytar(O1, I1, N1, 2)
check("G1 yana 2 m qaytdi — o'sha qaytgan TM, tannarx 15 200 (asl: 2 × o'sha paytdagi o'rtacha)",
      s == 200 and RFP2 == RFP and taxminan(SC2, 15_200), (s, RFP2, SC2))
check("G2 qaytgan TM 4 / 30 400 / 7 600", taxminan(tm(RFP)[0], 4) and taxminan(tm(RFP)[1], 30_400)
      and taxminan(tm(RFP)[2], 7_600, 0.0001), tm(RFP))
check("G3 qaytgan TM dan olingan buyurtma tannarxi o'zgarmadi", taxminan(tan(O6), 3 * YR), tan(O6))
check("G4 birinchi buyurtma tannarxi 3 × 7 600 = 22 800", taxminan(tan(O1), 22_800), tan(O1))
check("G5 balans 0", taxminan(balans(), 0), balans())
r = req(C, "delete", f"/api/returns/{RG}")
check("G6 qaytarishni o'chirish 200 — qaytgan TM 2 / 15 200 / 7 600, buyurtma 38 000",
      r.status_code == 200 and taxminan(tm(RFP)[0], 2) and taxminan(tm(RFP)[1], 15_200)
      and taxminan(tm(RFP)[2], 7_600, 0.0001) and taxminan(tan(O1), 38_000), (r.status_code, tm(RFP), tan(O1)))
check("G7 balans 0", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("H. O'zgarmagan qoidalar: TM sotuvi va brak summasi — JORIY o'rtacha")
# ══════════════════════════════════════════════════════════════
Q, Cc, Yh = tm(FP)
r = req(C, "post", "/api/finished/sell", json={"finished_product_id": FP, "quantity": 5, "unit_price": 30_000,
                                                "buyer_name": "TD xaridor", "confirm_below_cost": True})
_s = SessionLocal()
try:
    _sot = _s.query(FinishedProductSale).order_by(FinishedProductSale.id.desc()).first()
    _sot_c = float(_sot.cost_amount) if _sot is not None else None
finally:
    _s.close()
check("H1 sotuv 200, tannarx 5 × joriy o'rtacha", r.status_code == 200 and taxminan(_sot_c, 5 * Yh), (_sot_c, 5 * Yh))
check("H2 balans 0", taxminan(balans(), 0), balans())
_t3 = tan(O3)
s, RBR, _, _, SUM = qaytar(O3, I3, N3, 1, sabab="Brak", ombor=False)
check("H3 brak 200, summa = joriy o'rtacha (13-band 2-qadam — o'zgarmagan)", s == 200 and SUM is not None
      and abs(SUM - Yh) <= 0.5, (s, SUM, Yh))
check("H4 brak buyurtma tannarxini o'zgartirmadi", taxminan(tan(O3), _t3), (tan(O3), _t3))
_s = SessionLocal()
try:
    _it3 = _s.get(OrderItem, I3)
    _o3 = _s.get(Order, O3)
    _u_joriy = services.get_order_item_unit_cost(_s, _o3, _it3)
    _u_muz = services.get_order_item_unit_cost(_s, _o3, _it3, muzlatilgan=True)
finally:
    _s.close()
check("H5 get_order_item_unit_cost: joriy — TM o'rtachasi, muzlatilgan — detal birligi",
      taxminan(_u_joriy, Yh, 0.0001) and taxminan(_u_muz, _c8, 0.0001), (_u_joriy, Yh, _u_muz, _c8))

# ══════════════════════════════════════════════════════════════
section("K. K103-1 — detal tahriri (PUT /api/order-items) TM omborini o'zgartiradi")
# ══════════════════════════════════════════════════════════════
Q, Cc, Yk = tm(FP)
s, O7, I7, _, _ = buyurtma(FP, 10)
check("K0 buyurtma 200", s == 200 and taxminan(tan(O7), 10 * Yk))
narx(3)
check("K1 +10 m (narx x3) 200", qosh(FP, 10) == 200)
Q, Cc, Ykb = tm(FP)
r = req(C, "put", f"/api/order-items/{I7}", json={"length": 15})
_k7 = 10 * Yk + 5 * Ykb
check("K2 10 → 15 m: 200, TM −5 m (asl: tegilmasdi)", r.status_code == 200 and tm(FP)[0] == Q - 5
      and taxminan(tm(FP)[1], Cc - 5 * Ykb), (r.status_code, tm(FP), r.text[:200]))
check("K3 buyurtma tannarxi 10 × eski + 5 × yangi", taxminan(tan(O7), _k7), (tan(O7), _k7))
check("K4 balans 0 (asl: −87 431.49)", taxminan(balans(), 0), balans())
Q, Cc, Yk2 = tm(FP)
r = req(C, "put", f"/api/order-items/{I7}", json={"length": 8})
check("K5 15 → 8 m: 200, TM +7 m detal birligida", r.status_code == 200 and tm(FP)[0] == Q + 7
      and taxminan(tm(FP)[1], Cc + 7 * _k7 / 15), (r.status_code, tm(FP)))
check("K6 buyurtma tannarxi 8 × detal birligi", taxminan(tan(O7), 8 * _k7 / 15), (tan(O7), 8 * _k7 / 15))
check("K7 balans 0", taxminan(balans(), 0), balans())
r = req(C, "put", f"/api/order-items/{I7}", json={"notes": "TD izoh"})
check("K8 miqdorsiz tahrir 200 — TM tegilmadi", r.status_code == 200 and tm(FP)[0] == Q + 7, tm(FP))
check("K9 balans 0", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("Q. Qoralama — olinmaydi; jarayonga olinganda SHU paytdagi o'rtacha")
# ══════════════════════════════════════════════════════════════
t = {"project_id": loyiha(), "order_type": "product", "recipe_id": ID["R1"], "loy_kg": 0, "is_draft": True,
     "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 4, "quantity": 1,
                "unit_price": 20_000, "is_coated": True, "penoplast_id": ID["PENO"], "finished_product_id": FP}]}
r = req(C, "post", "/api/orders", json=t, params={"confirm_shortage": "true"})
_dq = js(r) or {}
OQ = _dq.get("id") if isinstance(_dq, dict) else None
IQ = ((_dq.get("items") or [{}])[0] if isinstance(_dq, dict) else {}).get("id")
_s = SessionLocal()
try:
    _oq = _s.get(Order, OQ) if OQ else None
    _qor = _oq is not None and _oq.status == OrderStatus.DRAFT
finally:
    _s.close()
check("Q0 qoralama 200, detal birligi yo'q (hali olinmagan)", r.status_code == 200 and _qor and birlik(IQ) is None,
      (r.status_code, _qor, birlik(IQ)))
narx(1)
qosh(FP, 10)
Yq = tm(FP)[2]
r = req(C, "post", f"/api/orders/{OQ}/activate")
check("Q1 jarayonga olish 200 — detal birligi = shu paytdagi o'rtacha", r.status_code == 200
      and taxminan(birlik(IQ), Yq, 0.0001), (r.status_code, birlik(IQ), Yq, r.text[:200]))
check("Q2 balans 0", taxminan(balans(), 0), balans())

# ══════════════════════════════════════════════════════════════
section("L. Eski detal (fp_unit_cost NULL) — avvalgi qoida; migratsiya bugungi qiymatda, idempotent")
# ══════════════════════════════════════════════════════════════
s, O8, I8, _, _ = buyurtma(FP, 6)
Y8 = birlik(I8)
YqI = birlik(IQ)
check("L0 buyurtma 200, birliklar yozilgan", s == 200 and Y8 and YqI, (s, Y8, YqI))
core_detal(I8, fp_unit_cost=None)
core_detal(IQ, fp_unit_cost=None)
narx(2)
qosh(FP, 10)
Yl = tm(FP)[2]
check("L1 NULL — buyurtma tannarxi joriy o'rtachada (avvalgi qoida)", taxminan(tan(O8), 6 * Yl), (tan(O8), 6 * Yl))
t9 = {"project_id": loyiha(), "order_type": "product", "recipe_id": ID["R1"], "loy_kg": 0, "is_draft": True,
      "items": [{"name": nom(), "category": "profil", "width": 20, "thickness": 10, "length": 2, "quantity": 1,
                 "unit_price": 20_000, "is_coated": True, "penoplast_id": ID["PENO"], "finished_product_id": FP}]}
_d9 = js(req(C, "post", "/api/orders", json=t9, params={"confirm_shortage": "true"})) or {}
I9 = ((_d9.get("items") or [{}])[0] if isinstance(_d9, dict) else {}).get("id")
_t8 = tan(O8)
_mig = getattr(main, "_migrate_tm_detal_tannarx", None)
check("L2 main._migrate_tm_detal_tannarx mavjud", callable(_mig))
if callable(_mig):
    with contextlib.redirect_stdout(_quiet):
        try:
            _mig()
        except Exception as e:            # noqa: BLE001
            print("migratsiya xatosi", e)
check("L3 migratsiya: NULL detal — bugungi o'rtacha", taxminan(birlik(I8), Yl, 0.0001), (birlik(I8), Yl))
check("L4 migratsiyadan keyin tannarx O'ZGARMADI", taxminan(tan(O8), _t8), (tan(O8), _t8))
check("L5 qoralama detali to'ldirilmadi", I9 is not None and birlik(I9) is None, birlik(I9))
check("L6 jarayondagi NULL detal ham to'ldirildi", taxminan(birlik(IQ), Yl, 0.0001), (birlik(IQ), Yl))
narx(3)
qosh(FP, 10)
if callable(_mig):
    with contextlib.redirect_stdout(_quiet):
        try:
            _mig()
        except Exception as e:            # noqa: BLE001
            print("migratsiya xatosi", e)
check("L7 ikkinchi chaqiruv — idempotent (o'rtacha o'zgargan bo'lsa ham)", taxminan(birlik(I8), Yl, 0.0001),
      (birlik(I8), Yl))
check("L8 muzlagan — tannarx o'zgarmadi", taxminan(tan(O8), _t8), (tan(O8), _t8))
core_detal(I8, fp_unit_cost=0)
check("L8b buzilgan birlik 0 (Core) — avvalgi qoida (joriy o'rtacha), 0 tannarx EMAS", taxminan(tan(O8), 6 * tm(FP)[2])
      and tan(O8) > 0, (tan(O8), 6 * tm(FP)[2]))
core_detal(I8, fp_unit_cost=Yl)
_kut_L = -(6 * (Yl - (Y8 or 0)) + 4 * (Yl - (YqI or 0)))
check("L9 balans — NULL davridagi (avvalgi qoida) siljish AYNAN shu ikki detal: −(6 × ΔY + 4 × ΔY), keyin muzladi",
      taxminan(balans(), _kut_L, 0.05) and abs(_kut_L) > 1, (balans(), _kut_L))

# ══════════════════════════════════════════════════════════════
section("V. Manfiy qoldiq (ortiqcha sotilgan TM) — qaytgan qism o'rtachasi faqat o'zidan")
# ══════════════════════════════════════════════════════════════
narx(1)
TV = ishlab(5)
Yv = tm(TV)[2]
s, OV, IV, _, _ = buyurtma(TV, 8)
check("V0 5 m li TM dan 8 m (tasdiq bilan) — qoldiq −3, detal birligi = o'rtacha", s == 200 and tm(TV)[0] == -3.0
      and taxminan(birlik(IV), Yv, 0.0001), (s, tm(TV), birlik(IV), Yv))
narx(2)
check("V1 +10 m (narx x2) 200", qosh(TV, 10) == 200)
s, OW, IW, _, _ = buyurtma(TV, 12)
check("V2 yana 12 m — qoldiq −5", s == 200 and tm(TV)[0] == -5.0, (s, tm(TV)))
check("V3 o'rtacha endi boshqa (birlik farq qiladi)", abs((tm(TV)[2] or 0) - Yv) > 1, (tm(TV), Yv))
r = req(C, "delete", f"/api/orders/{OV}")
check("V4 8 m qaytdi — qoldiq 3, o'rtacha = qaytgan qism birligi (manfiy qoldiq og'irlik emas)",
      r.status_code == 200 and tm(TV)[0] == 3.0 and taxminan(tm(TV)[2], Yv, 0.0001), (r.status_code, tm(TV), Yv))

# ══════════════════════════════════════════════════════════════
section("M. Korxona — begona TM ga bog'langan detal (Core bilan buzilgan havola)")
# ══════════════════════════════════════════════════════════════
_s = SessionLocal()
try:
    FB = FinishedProduct(company_id=2, name="TD B TM", category="profil", is_coated=True, quantity=10,
                         produced_quantity=10, unit="metr", unit_price=0, cost_price=50_000,
                         source=StockSource.PRODUCED, unit_cost_stable=5_000, production_status=ProductionStatus.READY)
    _s.add(FB)
    _s.commit()
    FBID = FB.id
finally:
    _s.close()
s, O10, I10, _, _ = buyurtma(FP, 3)
_t10 = tan(O10)
if not core_detal(I10, finished_product_id=FBID, fp_unit_cost=None):
    core_detal(I10, finished_product_id=FBID)
if callable(_mig):
    with contextlib.redirect_stdout(_quiet):
        try:
            _mig()
        except Exception as e:            # noqa: BLE001
            print("migratsiya xatosi", e)
check("M1 migratsiya begona korxona TM sidan birlik yozmadi", birlik(I10) is None, birlik(I10))
core_detal(I10, fp_unit_cost=5_000)
check("M2 begona TM li detal (birlik yozilgan) — tannarxga KIRMAYDI (avvalgidek)", taxminan(tan(O10), 0),
      (tan(O10), _t10))
_s = SessionLocal()
try:
    _it10 = _s.get(OrderItem, I10)
    _o10 = _s.get(Order, O10)
    _u10 = services.get_order_item_unit_cost(_s, _o10, _it10, muzlatilgan=True)
finally:
    _s.close()
check("M3 get_order_item_unit_cost (muzlatilgan) begona TM — 0", taxminan(_u10, 0), _u10)

# ══════════════════════════════════════════════════════════════
section("X. Server xatosi (5xx) yo'q")
# ══════════════════════════════════════════════════════════════
_yomon = [x for x in STATUSLAR if x[2] >= 500]
check("X1 hech bir so'rov 5xx emas", not _yomon, _yomon[:5])

# ══════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════
_tk = manba(crud._take_finished_for_order)
check("S1 olish: detal birligi yoziladi (faqat birlik > 0 shoxida)",
      tartibda(_tk, "if unit_cost > 0:", "it.fp_unit_cost = unit_cost", "elif old_qty > 0 and fp.cost_price:"))
_rt = manba(crud._return_finished_for_order)
check("S2 qaytarish: detal birligi faqat sign > 0 da, tiklashda detal birligi og'irlikli",
      tartibda(_rt, "_c56 = _tm_detal_birligi(it) if sign > 0 else None", "_tm_qaytgan_ortacha(",
               "if sign < 0 and unit_cost > 0:", "_tm_detal_olindi(it, qty, unit_cost"))
_ad = manba(crud._adjust_finished_diff)
check("S3 tahrir farqi: detallar bo'yicha, birliklar teng bo'lsa avvalgi formula",
      tartibda(_ad, "detallar=None", "for _d56 in (detallar or []):", "if _D56 != 0.0:", "_tm_detal_olindi(_det",
               "if _D56 == 0.0:", "cost_delta = -unit_cost * diff"))
_uf = manba(crud.update_order_full)
check("S4 to'liq tahrir o'tishlarni beradi", tartibda(_uf, "_tm56 = []", "detallar=_tm56"))
_ui = manba(crud.update_order_item)
check("S5 detal tahriri (K103-1) TM farqini qo'llaydi",
      tartibda(_ui, "services.adjust_inventory_diff(db, old_snap, new_snap", "_adjust_finished_diff(db, old_snap, new_snap"))
_cp = manba(services.calculate_order_profit)
check("S6 foyda: detal birligi AVVAL, TM korxona tekshiruvidan KEYIN",
      tartibda(_cp, "if not fp_c:", "_c56 = _crud_fp59._tm_detal_birligi(item)", "unit_cost = _c56",
               "elif _muz59 > 0:"))
_gu = manba(services.get_order_item_unit_cost)
check("S7 birlik narxi: detal birligi faqat muzlatilgan=True da, korxona tekshiruvidan keyin",
      tartibda(_gu, "fp = _ucq.first()", "if fp:", "_tm_detal_birligi(item) if muzlatilgan else None"))
_m = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("S8 migratsiya birlik migratsiyasidan keyin modul darajasida chaqiriladi",
      tartibda(_m, "\n_migrate_tm_birlik_tannarx()\n", "def _migrate_tm_detal_tannarx", "\n_migrate_tm_detal_tannarx()\n"))
check("S9 model ustuni Numeric(14, 4)", "fp_unit_cost = Column(Numeric(14, 4), nullable=True)" in
      open(os.path.join(ROOT, "models.py"), encoding="utf-8").read())

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
