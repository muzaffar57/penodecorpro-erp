#!/usr/bin/env python3
"""
test_mrp_xarajat_surat.py — kech94 darvozasi (2026-09-27, 122-band): ishlab chiqarish buyurtmasini
yakunlashdagi QO'SHIMCHA xarajat (`fixed_cost_per_unit` — 1 birlikka qat'iy summa, `percentage_cost` —
xomashyo tannarxiga foiz) SURATdan va FAQAT kiritilgan qatorlardan hisoblanadi.

O'LCHANGAN (asl kod = zip 87, `work/probe122.py`, SQLite = HAQIQIY PostgreSQL 16 AYNAN):
  (a) TANLANMAGAN ixtiyoriy qatorning xarajati ham qo'shilardi: qat'iy 1000 × 2 → tannarx 200 o'rniga
      2 200; foizli 50 % → 300;
  (b) boshlangandan KEYIN retseptga yozilgan xarajat tannarxni o'zgartirardi (500 × 2 → 1 200; 10 % → 220) —
      qoida #2 (surat o'zgarmasligi) buzilardi, xomashyo narxi esa suratdan olinardi. Retseptni sahifadan
      tahrirlash (`PUT /api/production/boms/{id}`) ham shunday ta'sir qilardi (izohi "boshlanganlarga ta'sir
      qilmaydi" desa ham);
  K93-2 dagi boshlash tekshiruvi ham tanlanmagan qator xarajatini qo'shib, sig'imga sig'adigan buyurtmani rad
  etardi.
Endi xarajat boshlashda suratga yoziladi (`fixed_cost_per_unit`, `percentage_cost` har qatorda) va
`production_service._qoshimcha_xarajat` bilan faqat `included` qatorlardan hisoblanadi (boshlash VA
yakunlash). Eski surat (kalitsiz — kech94 dan oldin boshlangan): joriy retseptdan, lekin `bom_item_id` bo'lsa
faqat suratdagi kiritilgan qatorlar; `bom_item_id` siz juda eski surat — avvalgi xulq AYNAN.

Bo'limlar: A — (a) tanlanmagan / tanlangan / majburiy qatorlar; B — (b) boshlangandan keyin retsept
o'zgarishi (Core va sahifa PUT yo'li); S — suratdagi kalitlar (API javobi); L — eski surat (orqaga moslik);
K — tannarx sig'imi (K93-2) surat qoidasi bilan; P — tiyin aniqligi; X — 5xx yo'q; H — statik.

Ishlatish:
    python3 tools/test_mrp_xarajat_surat.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_xarajat_surat.py
"""
import os
import sys
import json
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_xarajat_surat_test"
_T = tempfile.mkdtemp(prefix="mrp_xarajat_")
_DB = os.path.join(_T, "mrp_xarajat_surat_test.db")

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
import production_service as PSV                   # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, InventoryMovement, FinishedProduct   # noqa: E402
from production_models import BOMItem, ProductionOrder                      # noqa: E402
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


def detail(r):
    return (js(r) or {}).get("detail")


def pul(x):
    return None if x is None else round(float(x), 2)


# ════════════════════════════════════════════════════════════════
# Muhit: admin, 2 material (A — 100 so'm/kg, B — 50 so'm/kg), mahsulot turi
# ════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "xarajat_admin", "Parol123!", UserRole.ADMIN, "X", company_id=1)
_A = Inventory(company_id=1, item_name="XS asos", unit="kg", stock_quantity=1_000_000, price_per_unit=100)
_B = Inventory(company_id=1, item_name="XS qoplama", unit="kg", stock_quantity=1_000_000, price_per_unit=50)
s.add_all([_A, _B])
s.commit()
AID, BID = _A.id, _B.id
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
C.post("/login", data={"username": "xarajat_admin", "password": "Parol123!"}, follow_redirects=False)
_r = req(C, "post", "/api/production/product-types", json={"name": "XS mahsulot", "unit": "dona",
                                                           "input_template": "quantity_only", "pricing_formula": "unit_based"})
PT = (js(_r) or {}).get("id")

_SANOQ = [0]


def retsept(items):
    """Retsept (API) → (bom_id, [qator id lari tartib bilan])."""
    _SANOQ[0] += 1
    r = req(C, "post", "/api/production/boms", json={"product_type_id": PT, "variant_name": f"v{_SANOQ[0]}",
                                                     "batch_quantity": 1, "items": items})
    bid = (js(r) or {}).get("id")
    s = SessionLocal()
    try:
        ids = [x.id for x in s.query(BOMItem).filter(BOMItem.bom_id == bid).order_by(BOMItem.id).all()]
    finally:
        s.close()
    return bid, ids


def buyurtma(bid, qty=2, sel=()):
    r = req(C, "post", "/api/production/orders", json={"product_type_id": PT, "bom_id": bid, "quantity": qty,
                                                       "source_type": "warehouse_stock",
                                                       "selected_optional_bom_item_ids": list(sel)})
    return ((js(r) or {}).get("production_order") or {}).get("id")


def bosh(poid):
    return req(C, "post", f"/api/production/orders/{poid}/start")


def yakun(poid):
    return req(C, "post", f"/api/production/orders/{poid}/complete")


def holat(poid):
    """(status, material, qo'shimcha, jami, TM cost_price, TM unit_cost_stable, surat)"""
    s = SessionLocal()
    try:
        po = s.get(ProductionOrder, poid) if poid else None
        if po is None:
            return (None,) * 7
        fp = s.get(FinishedProduct, po.finished_product_id) if po.finished_product_id else None
        try:
            surat = json.loads(po.recipe_snapshot_json or "[]")
        except Exception:                  # noqa: BLE001
            surat = None
        return (po.status, pul(po.total_material_cost), pul(po.total_extra_cost), pul(po.total_cost),
                None if fp is None else pul(fp.cost_price),
                None if fp is None or fp.unit_cost_stable is None else round(float(fp.unit_cost_stable), 4), surat)
    finally:
        s.close()


def bom_qator_yangila(qator_id, **qiymat):
    s = SessionLocal()
    try:
        s.execute(BOMItem.__table__.update().where(BOMItem.id == qator_id).values(**qiymat))
        s.commit()
    finally:
        s.close()


def surat_yoz(poid, surat):
    s = SessionLocal()
    try:
        s.execute(ProductionOrder.__table__.update().where(ProductionOrder.id == poid)
                  .values(recipe_snapshot_json=None if surat is None else json.dumps(surat)))
        s.commit()
    finally:
        s.close()


def inv(i):
    s = SessionLocal()
    try:
        x = s.get(Inventory, i)
        return None if x is None else round(float(x.stock_quantity or 0), 6)
    finally:
        s.close()


def harakatlar():
    s = SessionLocal()
    try:
        return s.query(InventoryMovement).count()
    finally:
        s.close()


def toliq(items, qty=2, sel_idx=(), oraliq=None):
    """Retsept → buyurtma → boshlash → (oraliq amal) → yakunlash; natija holat()."""
    bid, ids = retsept(items)
    poid = buyurtma(bid, qty, [ids[i] for i in sel_idx])
    r1 = bosh(poid)
    if oraliq:
        oraliq(bid, ids, poid)
    r2 = yakun(poid)
    return r1.status_code, r2.status_code, holat(poid), (bid, ids, poid)


ASOS = {"inventory_id": AID, "quantity": 1}

# ════════════════════════════════════════════════════════════════
section("A. (a) tanlanmagan ixtiyoriy qator xarajati tannarxga KIRMAYDI")
# ════════════════════════════════════════════════════════════════
check("A0 muhit: mahsulot turi yaratildi", PT is not None, str(_r.status_code))
r1, r2, h, _ = toliq([ASOS])
check("A1 nazorat (ixtiyoriysiz): 200 / 200, material 200, qo'shimcha 0, TM 200",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0), f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "is_coating": True,
                             "fixed_cost_per_unit": 1000}])
check("A2 TANLANMAGAN ixtiyoriy qat'iy 1000 → qo'shimcha 0, TM 200 (eski: 2 200)",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0) and h[5] == 100.0, f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "fixed_cost_per_unit": 1000}],
                     sel_idx=(1,))
check("A3 TANLANGAN ixtiyoriy qat'iy 1000 → material 300, qo'shimcha 2 000, TM 2 300",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 300.0, 2000.0, 2300.0, 2300.0), f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "percentage_cost": 50}])
check("A4 TANLANMAGAN ixtiyoriy foiz 50 → qo'shimcha 0, TM 200 (eski: 300)",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0), f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "percentage_cost": 50}],
                     sel_idx=(1,))
check("A5 TANLANGAN ixtiyoriy foiz 50 → 300 × 50 % = 150, TM 450",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 300.0, 150.0, 450.0, 450.0), f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([{"inventory_id": AID, "quantity": 1, "fixed_cost_per_unit": 5, "percentage_cost": 10}])
check("A6 majburiy qator qat'iy 5 + foiz 10 → 5 × 2 + 200 × 10 % = 30, TM 230",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 30.0, 230.0, 230.0), f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([{"inventory_id": AID, "quantity": 1, "fixed_cost_per_unit": 10},
                      {"inventory_id": BID, "quantity": 1, "is_optional": True, "fixed_cost_per_unit": 1000,
                       "percentage_cost": 50},
                      {"inventory_id": BID, "quantity": 2, "is_optional": True, "percentage_cost": 10}], sel_idx=(2,))
# material: A 200 + B(2 × 2 × 50) 200 = 400; qo'shimcha: 10 × 2 + 400 × 10 % = 60 (tanlanmagan 1000 / 50 % kirmaydi)
check("A7 ikki ixtiyoriy — faqat tanlangani: material 400, qo'shimcha 60, TM 460",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 400.0, 60.0, 460.0, 460.0), f"{r1} {r2} {h[:6]}")

# ════════════════════════════════════════════════════════════════
section("B. (b) boshlangandan KEYIN retsept o'zgarsa tannarx O'ZGARMAYDI (surat)")
# ════════════════════════════════════════════════════════════════
r1, r2, h, _ = toliq([ASOS], oraliq=lambda bid, ids, poid: bom_qator_yangila(ids[0], fixed_cost_per_unit=500))
check("B1 boshlangach qat'iy 500 yozildi → qo'shimcha 0, TM 200 (eski: 1 200)",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0), f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([ASOS], oraliq=lambda bid, ids, poid: bom_qator_yangila(ids[0], percentage_cost=10))
check("B2 boshlangach foiz 10 yozildi → qo'shimcha 0, TM 200 (eski: 220)",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0), f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "fixed_cost_per_unit": 1000}],
                     sel_idx=(1,), oraliq=lambda bid, ids, poid: bom_qator_yangila(ids[1], fixed_cost_per_unit=None))
check("B3 boshlangach retseptdan xarajat OLIB TASHLANDI → baribir suratdagi 2 000, TM 2 300",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 300.0, 2000.0, 2300.0, 2300.0), f"{r1} {r2} {h[:6]}")


def _yangi_qator(bid, ids, poid):
    s = SessionLocal()
    try:
        s.add(BOMItem(bom_id=bid, company_id=1, inventory_id=BID, quantity=1, fixed_cost_per_unit=700))
        s.commit()
    finally:
        s.close()


r1, r2, h, (_bid, _ids, _poid) = toliq([ASOS], oraliq=_yangi_qator)
check("B4 boshlangach retseptga YANGI qator (qat'iy 700) → material ham, xarajat ham kirmaydi, TM 200",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0) and inv(BID) is not None, f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "fixed_cost_per_unit": 1000}],
                     oraliq=lambda bid, ids, poid: bom_qator_yangila(ids[1], is_optional=False))
check("B5 boshlangach tanlanmagan qator MAJBURIY qilindi → kirmaydi (surat), TM 200",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0), f"{r1} {r2} {h[:6]}")


def _sahifa_tahrir(bid, ids, poid):
    r = req(C, "put", f"/api/production/boms/{bid}", json={
        "product_type_id": PT, "variant_name": f"tahrir{bid}", "batch_quantity": 1,
        "items": [{"inventory_id": AID, "quantity": 1, "fixed_cost_per_unit": 999, "percentage_cost": 25}]})
    _TAHRIR.append(r.status_code)


_TAHRIR = []
r1, r2, h, _ = toliq([ASOS], oraliq=_sahifa_tahrir)
check("B6 sahifa yo'li: PUT /api/production/boms (qat'iy 999, foiz 25) boshlangach → 200, tannarx O'ZGARMADI (TM 200)",
      _TAHRIR == [200] and (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0),
      f"{_TAHRIR} {r1} {r2} {h[:6]}")
_bid6, _ids6 = retsept([ASOS])
_po6 = buyurtma(_bid6, 2)
_r = bosh(_po6)
_ = req(C, "put", f"/api/production/boms/{_bid6}", json={
    "product_type_id": PT, "variant_name": f"tahrir{_bid6}", "batch_quantity": 1,
    "items": [{"inventory_id": AID, "quantity": 1, "fixed_cost_per_unit": 999, "percentage_cost": 25}]})
_po6b = buyurtma(_bid6, 2)
_r1b, _r2b = bosh(_po6b).status_code, yakun(_po6b).status_code
_r2 = yakun(_po6).status_code
_h6, _h6b = holat(_po6), holat(_po6b)
check("B7 tahrirdan KEYIN boshlangan buyurtma yangi xarajatni oladi (999 × 2 + 200 × 25 % = 2 048), eskisi — 0",
      (_r1b, _r2b, _r2) == (200, 200, 200) and _h6b[2] == 2048.0 and _h6b[4] == 2248.0 and _h6[2] == 0.0,
      f"{_r1b} {_r2b} {_r2} {_h6b[:5]} {_h6[:5]}")

# ════════════════════════════════════════════════════════════════
section("S. Surat — har qatorda xarajat kalitlari (API javobi)")
# ════════════════════════════════════════════════════════════════
_bid, _ids = retsept([{"inventory_id": AID, "quantity": 1, "fixed_cost_per_unit": 12.5, "percentage_cost": 7.5},
                      {"inventory_id": BID, "quantity": 1, "is_optional": True, "fixed_cost_per_unit": 1000}])
_poS = buyurtma(_bid, 2)
_r = bosh(_poS)
_surat = (((js(_r) or {}).get("production_order") or {}).get("recipe_snapshot")) or []
_q = {l.get("bom_item_id"): l for l in _surat if isinstance(l, dict)}
check("S1 boshlash 200, javobdagi surat 2 qator", _r.status_code == 200 and len(_surat) == 2, f"{_r.status_code} {len(_surat)}")
check("S2 kiritilgan qator: fixed_cost_per_unit 12.5, percentage_cost 7.5",
      _q.get(_ids[0], {}).get("fixed_cost_per_unit") == 12.5 and _q.get(_ids[0], {}).get("percentage_cost") == 7.5
      and _q.get(_ids[0], {}).get("included") is True, json.dumps(_q.get(_ids[0]))[:300])
check("S3 tanlanmagan qator ham xarajati bilan (shaffoflik), lekin included = false",
      _q.get(_ids[1], {}).get("fixed_cost_per_unit") == 1000.0 and _q.get(_ids[1], {}).get("percentage_cost") == 0.0
      and _q.get(_ids[1], {}).get("included") is False, json.dumps(_q.get(_ids[1]))[:300])
_royxat = js(req(C, "get", "/api/production/orders")) or []
_rq = [l for p in _royxat if isinstance(p, dict) and p.get("id") == _poS for l in (p.get("recipe_snapshot") or [])]
check("S3b ro'yxat javobida (GET /api/production/orders) ham xarajat kalitlari: [12.5, 1000] / [7.5, 0]",
      sorted(l.get("fixed_cost_per_unit") or 0 for l in _rq) == [12.5, 1000.0]
      and sorted(l.get("percentage_cost") or 0 for l in _rq) == [0.0, 7.5], json.dumps(_rq)[:300])
_r = yakun(_poS)
_hS = holat(_poS)
check("S4 yakunlash: 12.5 × 2 + 200 × 7.5 % = 40, TM 240", _r.status_code == 200 and _hS[2] == 40.0 and _hS[4] == 240.0,
      f"{_r.status_code} {_hS[:5]}")

# ════════════════════════════════════════════════════════════════
section("L. Eski surat (kech94 dan OLDIN boshlangan — xarajat kalitsiz): orqaga moslik")
# ════════════════════════════════════════════════════════════════


def eski_qil(kalitlar=("fixed_cost_per_unit", "percentage_cost")):
    def f(bid, ids, poid):
        h = holat(poid)
        sur = h[6] or []
        for l in sur:
            for k in kalitlar:
                l.pop(k, None)
        surat_yoz(poid, sur)
    return f


r1, r2, h, _ = toliq([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "fixed_cost_per_unit": 1000}],
                     oraliq=eski_qil())
check("L1 eski surat (bom_item_id bor): tanlanmagan qat'iy 1000 → kirmaydi, TM 200",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0), f"{r1} {r2} {h[:6]}")


def _eski_va_tahrir(bid, ids, poid):
    eski_qil()(bid, ids, poid)
    bom_qator_yangila(ids[0], fixed_cost_per_unit=500)


r1, r2, h, _ = toliq([ASOS], oraliq=_eski_va_tahrir)
check("L2 eski surat: boshlangach retsept xarajati 500 → joriy retseptdan (avvalgi xulq): qo'shimcha 1 000",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 1000.0, 1200.0, 1200.0), f"{r1} {r2} {h[:6]}")


def _eski_va_yangi_qator(bid, ids, poid):
    eski_qil()(bid, ids, poid)
    _yangi_qator(bid, ids, poid)


r1, r2, h, _ = toliq([ASOS], oraliq=_eski_va_yangi_qator)
check("L3 eski surat: boshlangach qo'shilgan qator (qat'iy 700) → kirmaydi (suratda yo'q), TM 200",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0), f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "fixed_cost_per_unit": 1000}],
                     oraliq=eski_qil(("fixed_cost_per_unit", "percentage_cost", "bom_item_id")))
check("L4 juda eski surat (bom_item_id YO'Q): butun joriy retsept — avvalgi xulq AYNAN (qo'shimcha 2 000)",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 2000.0, 2200.0, 2200.0), f"{r1} {r2} {h[:6]}")

# ════════════════════════════════════════════════════════════════
section("K. Tannarx sig'imi (K93-2) — boshlash tekshiruvi ham surat qoidasi bilan")
# ════════════════════════════════════════════════════════════════
r1, r2, h, _ = toliq([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "fixed_cost_per_unit": 9_000_000_000}])
check("K1 TANLANMAGAN ixtiyoriy qat'iy 9e9 (× 2 = 18e9 > sig'im) → boshlash 200 (eski: 409), yakunlash 200, TM 200",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 200.0, 0.0, 200.0, 200.0), f"{r1} {r2} {h[:6]}")
_bid, _ids = retsept([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "fixed_cost_per_unit": 9_000_000_000}])
_poK = buyurtma(_bid, 2, [_ids[1]])
_r = bosh(_poK)
check("K2 TANLANGAN ixtiyoriy qat'iy 9e9 → boshlash 409 'tannarxi juda katta', qoralama qoldi",
      _r.status_code == 409 and "tannarxi juda katta" in str(detail(_r)) and holat(_poK)[0] == "draft",
      f"{_r.status_code} {str(detail(_r))[:160]}")
_bid, _ids = retsept([ASOS])
_poK3 = buyurtma(_bid, 2)
_r = bosh(_poK3)
_asl = holat(_poK3)[6]
_sur = json.loads(json.dumps(_asl or []))
for _l in _sur:
    _l["fixed_cost_per_unit"] = 9_000_000_000
surat_yoz(_poK3, _sur)
_i0, _m0 = inv(AID), harakatlar()
_r = yakun(_poK3)
check("K3 suratdagi qat'iy 9e9 → yakunlash 409, JARAYONDA qoldi, xomashyo ayirilmadi, harakat yo'q",
      _r.status_code == 409 and "tannarxi juda katta" in str(detail(_r)) and holat(_poK3)[0] == "in_progress"
      and inv(AID) == _i0 and harakatlar() == _m0, f"{_r.status_code} {str(detail(_r))[:120]} {_i0} -> {inv(AID)}")
surat_yoz(_poK3, _asl)
_r = yakun(_poK3)
check("K4 surat asliga qaytgach yakunlash 200, TM 200", _r.status_code == 200 and holat(_poK3)[4] == 200.0,
      f"{_r.status_code} {holat(_poK3)[:5]}")
_f = getattr(PSV, "_qoshimcha_xarajat", None)
check("K5 production_service._qoshimcha_xarajat mavjud", callable(_f))
if callable(_f):
    class _PO:
        quantity = 3
        bom_id = None
    _sur = [{"included": True, "fixed_cost_per_unit": 10.0, "percentage_cost": 5.0},
            {"included": False, "fixed_cost_per_unit": 1000.0, "percentage_cost": 50.0},
            {"included": True, "fixed_cost_per_unit": 0.0, "percentage_cost": 0.0}, "buzuq"]
    _s = SessionLocal()
    try:
        _v = _f(_s, _PO(), _sur, 400.0, 1)
        _v0 = _f(_s, _PO(), [], 400.0, 1)
    except Exception as e:                 # noqa: BLE001
        _v = _v0 = f"{type(e).__name__}: {e}"
    finally:
        _s.close()
    check("K6 yordamchi: 10 × 3 + 400 × 5 % = 50 (tanlanmagan / noto'g'ri qator o'tkazib yuboriladi)", _v == 50.0, str(_v))
    check("K7 yordamchi: bo'sh surat, retsept topilmasa → 0", _v0 == 0.0, str(_v0))
else:
    check("K6 yordamchi: 10 × 3 + 400 × 5 % = 50", False, "yo'q")
    check("K7 yordamchi: bo'sh surat → 0", False, "yo'q")

# ════════════════════════════════════════════════════════════════
section("P. Tiyin aniqligi (Numeric) — qat'iy 1 234.56 × 3, foiz 12.5")
# ════════════════════════════════════════════════════════════════
r1, r2, h, _ = toliq([{"inventory_id": AID, "quantity": 1, "fixed_cost_per_unit": 1234.56}], qty=3)
check("P1 qat'iy 1 234.56 × 3 = 3 703.68, material 300, TM 4 003.68, 1 birlik 1 334.56",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 300.0, 3703.68, 4003.68, 4003.68) and h[5] == 1334.56,
      f"{r1} {r2} {h[:6]}")
r1, r2, h, _ = toliq([ASOS, {"inventory_id": BID, "quantity": 1, "is_optional": True, "percentage_cost": 12.5}],
                     qty=3, sel_idx=(1,))
check("P2 foiz 12.5 — material 450 × 12.5 % = 56.25, TM 506.25",
      (r1, r2) == (200, 200) and h[:5] == ("completed", 450.0, 56.25, 506.25, 506.25), f"{r1} {r2} {h[:6]}")

# ════════════════════════════════════════════════════════════════
section("X. 5xx yo'q")
# ════════════════════════════════════════════════════════════════
_besh = [h for h in HOLATLAR if h[1] >= 500]
check(f"X1 {len(HOLATLAR)} so'rovda 5xx yo'q", not _besh, str(_besh[:5]))

# ════════════════════════════════════════════════════════════════
section("H. Statik")
# ════════════════════════════════════════════════════════════════


def manba(mod, nom):
    try:
        return inspect.getsource(getattr(mod, nom))
    except Exception:                      # noqa: BLE001
        return ""


_c = manba(PSV, "complete_production_order")
_st = manba(PSV, "start_production_order")
check("H1 complete: xarajat _qoshimcha_xarajat(... snapshot, total_material_cost ...) bilan; JORIY retsept sikli yo'q",
      "_qoshimcha_xarajat(db, po, snapshot, total_material_cost, company_id)" in _c
      and "for item in bom.items" not in _c, "")
check("H2 start: qatorga xarajat kalitlari yoziladi va sig'im tekshiruvi shu yordamchi bilan",
      'line["fixed_cost_per_unit"] = float(item.fixed_cost_per_unit or 0)' in _st
      and 'line["percentage_cost"] = float(item.percentage_cost or 0)' in _st
      and "_qoshimcha_xarajat(db, po, snapshot, _tm, company_id)" in _st and "for _bi in bom.items" not in _st, "")
_h = manba(PSV, "_qoshimcha_xarajat")
check("H3 yordamchi: faqat included qatorlar (yangi va eski surat), eski suratda bom_item_id filtri",
      'if not l.get("included")' in _h and "idli and item.id not in kiritilgan" in _h, "")

print("\n" + "=" * 66)
print(f"REJIM: {'PostgreSQL' if PG_URL else 'SQLite'}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
sys.exit(1 if FAIL else 0)
