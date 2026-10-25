#!/usr/bin/env python3
"""
test_hajm217.py — kech157 (zip 217 «Kirim bekori — blok hajmi» — egasi tanlovi 25.10: «Kirim bekori — blok hajmi (Tavsiya)»).

NIMA UCHUN KERAK
  Penoplast xaridida «1 blok necha m³» o'rtachalanadi, lekin xarid o'chirilsa / kirim hujjati bekor qilinsa — narx qaytardi, HAJM qaytmasdi:
  10 blok × 1,0 m³ + xarid 10 × 1,4 → 1,2; xarid o'chirilgach hajm 1,2 da qolardi, 1 m³ narxi 833 333 (1 000 000 emas). O'LCHANGAN —
  `work/k217/probe217.py`, zip 216 kodi, SQLite = PG.
BO'LIMLAR
  S — manba (ustunlar, yordamchi, chaqiruv joylari).
  A — yakka xarid o'chirilsa hajm qaytadi (1 m³ narxi ham); orada sarf bo'lsa ham; orada boshqa kirim bo'lsa — tegilmaydi (narx qoidasi);
      xarid tahriri — tegilmaydi (narx kabi); penoplast bo'lmagan material — hajm izi yo'q; hajm berilmagan penoplast xaridi — iz bor,
      hajm o'zgarmaydi; eski (izsiz) xarid — tegilmaydi; kirim hujjati bekori (bitta va bir material ikki qatorda) — hajm qaytadi, bekor
      rejasi (`cancel-plan`) — joriy / yangi hajm; o'chirilgandan keyin buyurtma penoplastni to'g'ri yechadi.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL.
Asl kodga (zip 216) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_hajm217.py
"""
import os
import io
import sys
import tempfile
import datetime
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hajm217_test"
_T = tempfile.mkdtemp(prefix="k217_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k217.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


section("S — manba")
CRUD_SRC = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
MOD_SRC = open(os.path.join(ROOT, "models.py"), encoding="utf-8").read()
check("S1 `inventory_purchases.hajm_oldin` / `hajm_keyin` (Float, NULL, standartsiz); `crud._xarid_hajmini_qaytar`; yakka xarid o'chirish va "
      "kirim bekori uni chaqiradi",
      "hajm_oldin = Column(Float, nullable=True)" in MOD_SRC and "hajm_keyin = Column(Float, nullable=True)" in MOD_SRC
      and "def _xarid_hajmini_qaytar(" in CRUD_SRC and "inv.volume_per_unit = _xarid_hajmini_qaytar(inv.volume_per_unit, p)[0]" in CRUD_SRC
      and "_xarid_hajmini_qaytar(hajm, p) if inv.is_penoplast" in CRUD_SRC)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, InventoryPurchase, Project   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k217_a", PAROL, UserRole.ADMIN, "K217 Admin", company_id=1)
P1 = Project(company_id=1, client_name="K217 mijoz", project_name="K217 loyiha", client_phone="+998901112217", total_budget=0, total_paid=0)
s.add(P1)
s.commit()
PID = P1.id
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "k217_a", "password": PAROL}, follow_redirects=False)
_N = [0]


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def material(peno=True, hajm=1.0, qoldiq=10, narx=1_000_000):
    _N[0] += 1
    s2 = SessionLocal()
    p = Inventory(company_id=1, item_name=f"K217 {'Peno' if peno else 'Kley'} {_N[0]}", unit="blok" if peno else "kg", stock_quantity=qoldiq,
                  price_per_unit=narx, volume_per_unit=hajm if peno else None, is_penoplast=peno, is_default_penoplast=False,
                  category="Penoplast" if peno else "Kimyo")
    s2.add(p)
    s2.commit()
    i = p.id
    s2.close()
    return i


def holat(i):
    s2 = SessionLocal()
    try:
        p = s2.get(Inventory, i)
        return (round(float(p.stock_quantity), 6), round(float(p.price_per_unit), 2), None if p.volume_per_unit is None else round(float(p.volume_per_unit), 6))
    finally:
        s2.close()


def xarid(i, q, hajm=None, narx=1_000_000):
    tana = {"quantity": q, "price_per_unit": narx, "paid_now": 0, "transport_cost": 0, "transport_payer": "none", "is_opening_stock": True}
    if hajm is not None:
        tana["volume_per_unit"] = hajm
    r = A.post(f"/api/inventory/{i}/purchase", json=tana)
    s2 = SessionLocal()
    try:
        p = s2.query(InventoryPurchase).filter(InventoryPurchase.inventory_id == i).order_by(InventoryPurchase.id.desc()).first()
        return r.status_code, (p.id if p else None), (None if p is None else (getattr(p, "hajm_oldin", "ustun yo'q"), getattr(p, "hajm_keyin", "ustun yo'q")))   # asl kodda — qulamasin
    finally:
        s2.close()


def ochir(pid):
    return A.delete(f"/api/inventory/purchases/{pid}?reverse_stock=true").status_code


section("A — xarid va kirim bekori")
i = material()
st, pid, iz = xarid(i, 10, 1.4)
h1 = holat(i)
d = ochir(pid)
check("A1 10 × 1,0 + xarid 10 × 1,4 → 1,2 m³; xarid o'chirilsa — 10 blok, 1 000 000, HAJM 1,0 (ilgari 1,2 da qolardi); xarid izi (1,0 → 1,2)",
      st == 200 and h1 == (20.0, 1000000.0, 1.2) and iz == (1.0, 1.2) and d == 200 and holat(i) == (10.0, 1000000.0, 1.0), (st, h1, iz, d, holat(i)))
i = material()
st, pid, iz = xarid(i, 10, 1.4)
c = A.post(f"/api/inventory/{i}/stock", json={"quantity_change": -5, "reason": "K217 sarf"}).status_code
d = ochir(pid)
check("A2 orada 5 blok sarf — o'chirilgach 5 blok, hajm 1,0 (sarf hajmni o'zgartirmaydi)", st == 200 and c == 200 and d == 200
      and holat(i) == (5.0, 1000000.0, 1.0), holat(i))
i = material()
st, pid, _ = xarid(i, 10, 1.4)
st2, pid2, _ = xarid(i, 10, 1.0, narx=1_000_001)
h2 = holat(i)
d = ochir(pid)
check("A3 orada BOSHQA kirim (10 × 1,0) — birinchisi o'chirilsa hajm TEGILMAYDI (narx qoidasi bilan bir xil — teskari hisob noaniq)",
      st == st2 == 200 and d == 200 and holat(i)[2] == h2[2] and h2[2] == round((20 * 1.2 + 10 * 1.0) / 30, 4), (h2, holat(i)))
i = material()
st, pid, _ = xarid(i, 10, 1.4)
u = A.put(f"/api/inventory/purchases/{pid}", json={"quantity": 5})
check("A4 xarid TAHRIRI (10 → 5) — hajm qayta hisoblanmaydi (narx kabi, avvalgidek: 1,2)", st == 200 and u.status_code == 200
      and holat(i) == (15.0, 1000000.0, 1.2), (u.status_code, u.text[:200], holat(i)))
k = material(peno=False)
_hk = holat(k)
st, pid, iz = xarid(k, 50, None, narx=1000)
d = ochir(pid)
check("A5 penoplast bo'lmagan material — hajm izi YO'Q (NULL), o'chirish avvalgidek (qoldiq / narx / hajm ustuni o'zgarmagan)",
      st == 200 and iz == (None, None) and d == 200 and holat(k) == _hk, (iz, _hk, holat(k)))
i = material(hajm=1.3)
st, pid, iz = xarid(i, 5, None)
h = holat(i)
d = ochir(pid)
check("A6 hajmi berilmagan penoplast xaridi — hajm o'zgarmaydi (1,3), iz 1,3 → 1,3, o'chirilgach ham 1,3", st == 200 and iz == (1.3, 1.3)
      and h[2] == 1.3 and d == 200 and holat(i) == (10.0, 1000000.0, 1.3), (iz, h, holat(i)))
i = material()
st, pid, _ = xarid(i, 10, 1.4)
s = SessionLocal()
_p = s.get(InventoryPurchase, pid)
_p.hajm_oldin = None
_p.hajm_keyin = None
s.commit()
s.close()
d = ochir(pid)
check("A7 eski (zip 217 dan oldingi, izsiz) xarid o'chirilsa — hajm TEGILMAYDI (1,2; avvalgi xulq)", st == 200 and d == 200
      and holat(i) == (10.0, 1000000.0, 1.2), holat(i))
i = material()
r = A.post("/api/inventory/receipt", json={"items": [{"inventory_id": i, "quantity": 10, "price_per_unit": 1_000_000, "volume_per_unit": 1.4,
                                                      "is_opening_stock": True}], "paid_now": 0, "transport_cost": 0})
rid = js(r).get("receipt_id") or js(r).get("id")
pl = js(A.get(f"/api/inventory/receipts/{rid}/cancel-plan"))
_m = (pl.get("materiallar") or [{}])[0]
c = A.post(f"/api/inventory/receipts/{rid}/cancel", json={})
check("A8 kirim hujjati (10 × 1,4) bekor qilinsa — hajm 1,0; bekor rejasida joriy 1,2 → yangi 1,0 («hajm_qaytdi»)",
      r.status_code == 200 and c.status_code == 200 and holat(i) == (10.0, 1000000.0, 1.0) and _m.get("joriy_hajm") == 1.2
      and _m.get("yangi_hajm") == 1.0 and _m.get("hajm_qaytdi") is True, (r.status_code, c.status_code, holat(i), _m))
i = material()
r = A.post("/api/inventory/receipt", json={"items": [{"inventory_id": i, "quantity": 10, "price_per_unit": 1_000_000, "volume_per_unit": 1.4,
                                                      "is_opening_stock": True},
                                                     {"inventory_id": i, "quantity": 20, "price_per_unit": 1_000_000, "volume_per_unit": 2.0,
                                                      "is_opening_stock": True}], "paid_now": 0, "transport_cost": 0})
rid = js(r).get("receipt_id") or js(r).get("id")
h = holat(i)
c = A.post(f"/api/inventory/receipts/{rid}/cancel", json={})
check("A9 bir material hujjatda IKKI qatorda (10 × 1,4 va 20 × 2,0 — 1,0 → 1,2 → 1,6) — bekor qilinsa ketma-ket 1,6 → 1,2 → 1,0",
      r.status_code == 200 and h == (40.0, 1000000.0, 1.6) and c.status_code == 200 and holat(i) == (10.0, 1000000.0, 1.0), (h, holat(i)))
i = material(qoldiq=100)
st, pid, _ = xarid(i, 100, 1.4)
d = ochir(pid)
_N[0] += 1
b = {"project_id": PID, "order_type": "product", "recipe_id": None, "master_id": None,
     "deadline": (datetime.date.today() + datetime.timedelta(days=3)).isoformat(), "is_draft": False, "base_price": 600000, "loy_kg": None,
     "items": [{"name": "K217 Panel", "category": "panel", "width": 100, "thickness": 10, "length": 1, "quantity": 1, "unit_price": 10000,
                "is_coated": False, "penoplast_id": i, "price_per_m3": None, "finished_product_id": None}]}
o = A.post("/api/orders?confirm_shortage=true", json=b)
check("A10 o'chirilgandan keyin buyurtma (0,1 m³ panel) — penoplast 1,0 m³ li blok bilan: 100 − 0,1 = 99,9 blok (1,2 da 99,9167 bo'lardi)",
      st == 200 and d == 200 and o.status_code == 200 and abs(holat(i)[0] - 99.9) < 1e-6, (o.status_code, o.text[:200], holat(i)))

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
