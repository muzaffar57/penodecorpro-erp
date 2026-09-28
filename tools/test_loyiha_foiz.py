#!/usr/bin/env python3
"""
test_loyiha_foiz.py — kech101 darvozasi (2026-09-27, 139-band + K101-5).

O'LCHANGAN (asl kod = zip 94, `work/probe139.py`, SQLite = PG AYNAN): loyiha — R1 / R2 «Tayyor», I1 jarayonda, D1 qoralama,
X1 qisman topshirilib o'chirilgan (READY — hisobotda qoladi), X2 / X3 kech100 dan oldin o'chirilgan (IN_PROGRESS).
  * Loyihalar kartasi chizig'i (`GET /api/projects/progress-map`) o'chirilganlarni ham sanardi — 50 % (3 / 6), kartada esa
    "4 ta buyurtma"; loyiha detali `progress_pct` boshqa formula (qoralama maxrajda) — 50 %. To'g'risi 67 % (2 / 3).
  * Loyiha detali "Sof foyda" (`/api/projects/{id}/detail-stats` `total_profit`) X1 foydasini (172 000) olmasdi — 630 000;
    oylik hisobot va Loyihalar sahifasi "Sof foyda" — 802 000.
YECHIM: `crud.loyiha_bajarilish_foizi` — yagona qoida (o'chirilmaganlar; qoralama / bekor — maxrajda emas); foyda — barcha
«Tayyor» (o'chirilgani ham, korxona filtri bilan).

Bo'limlar:  A — foiz (karta chizig'i = detal = qoida, "N ta buyurtma" / Buyurtmalar yorlig'i bilan bir to'plam);
            B — foyda (detal = oylik hisobot = Loyihalar sahifasi); C — chegaralar (faqat o'chirilganlar, bo'sh, faqat
            qoralama, hammasi tayyor, DELIVERED); K — korxona (begona buyurtma loyihaga Core bilan bog'langan — sanalmaydi);
            X — 5xx yo'q; S — statik.

Ishlatish:
    python3 tools/test_loyiha_foiz.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_loyiha_foiz.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "loyiha_foiz_test"
_T = tempfile.mkdtemp(prefix="loyiha_foiz_")
_DB = os.path.join(_T, "loyiha_foiz_test.db")

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
import re                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime, timedelta           # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
    import crud                                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, OrderItem, Order, OrderStatus, Recipe, RecipeIngredient, Master,
)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

crud.PUL_TAKROR_SONIYA = 0

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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:600]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


XATOLAR_5XX = []


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    if r.status_code >= 500:
        XATOLAR_5XX.append((metod, url, r.status_code, str(getattr(r, "text", ""))[:200]))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
_db.add(Company(id=2, name="LF Korxona B"))          # PG: users.company_id FK — B korxonasi oldin
_db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "LF_admin", "Parol123!", UserRole.ADMIN, "LF Admin", company_id=1)
    auth.create_user(_db, "LF_admin2", "Parol123!", UserRole.ADMIN, "LF Admin 2", company_id=2)
PENO = Inventory(company_id=1, item_name="LF Penoplast", unit="blok", stock_quantity=100_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="LF Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000,
                 category="Kimyo")
PENO2 = Inventory(company_id=2, item_name="LF2 Penoplast", unit="blok", stock_quantity=100_000,
                  price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_db.add_all([PENO, KLEY, PENO2])
_db.flush()
REC = Recipe(company_id=1, name="LF retsept", batch_size_kg=100.0)
_db.add(REC)
_db.flush()
_db.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
_db.commit()
ID = {"PENO": PENO.id, "KLEY": KLEY.id, "REC": REC.id, "PENO2": PENO2.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "LF_admin", "password": "Parol123!"}, follow_redirects=False)
C2 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr2 = req(C2, "post", "/login", data={"username": "LF_admin2", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302 or _lr2.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr2.status_code)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom(p="LF"):
    _n[0] += 1
    return f"{p}{_n[0]}"


def loyiha(cid=1):
    n = nom("P")
    s = SessionLocal()
    try:
        p = Project(company_id=cid, client_name=f"{n} Mijoz", project_name=f"{n} loyiha", total_budget=0, total_paid=0)
        m = Master(company_id=cid, name=f"{n} Usta", phone="+99893" + str(1_000_000 + _n[0]).zfill(7),
                   kpi_percent=10.0, is_active=True)
        s.add_all([p, m])
        s.commit()
        return p.id, m.id
    finally:
        s.close()


def yarat(pid, mid, yetk=None, draft=False, klient=None, peno=None):
    k = klient or C
    tana = {"project_id": pid, "order_type": "product", "loy_kg": 10.0 if k is C else 0.0, "master_id": mid,
            "items": [{"name": nom("D"), "category": "profil", "width": 20, "thickness": 10, "length": 10.0,
                       "quantity": 10, "unit_price": 50_000, "is_coated": k is C,
                       "penoplast_id": peno or ID["PENO"], **({"recipe_id": ID["REC"]} if k is C else {})}]}
    if k is C:
        tana["recipe_id"] = ID["REC"]
    if draft:
        tana["is_draft"] = True
    r = req(k, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id")
    s = SessionLocal()
    try:
        _i = s.query(OrderItem.id).filter(OrderItem.order_id == oid).first()
        iid = _i[0] if _i else None
    finally:
        s.close()
    if yetk and iid:
        req(k, "post", "/api/deliveries", json={
            "order_id": oid, "items": [{"order_item_id": iid, "quantity": yetk}], "notes": nom("yuk"),
            "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    return oid


def tayyor(oid, klient=None):
    return req(klient or C, "post", f"/api/orders/{oid}/ready").status_code


def ochir(oid):
    return req(C, "delete", f"/api/orders/{oid}").status_code


def eski_ochir(oid):
    """kech100 dan OLDINGI o'chirish (qisman topshirilgan): qolgan qism qaytadi, `stock_returned`, holat o'zgarmaydi."""
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if not o.is_fully_delivered:
            services.return_inventory_for_order_partial(s, o)
            o.stock_returned = True
        o.is_deleted = True
        s.commit()
    finally:
        s.close()


def holat_ozgar(oid, **k):
    s = SessionLocal()
    try:
        s.execute(Order.__table__.update().where(Order.__table__.c.id == oid).values(**k))
        s.commit()
    finally:
        s.close()


def xarita(k=None):
    d = js(req(k or C, "get", "/api/projects/progress-map")) or {}
    return {int(a): b for a, b in d.items()}


def detal(pid, k=None):
    r = req(k or C, "get", f"/api/projects/{pid}/detail-stats")
    return r.status_code, (js(r) or {})


def karta_soni(pid):
    h = req(C, "get", "/projects").text
    m = re.findall(r'data-id="%d"[^>]*?data-orders="(\d+)"' % pid, h) or re.findall(r'data-orders="(\d+)"[^>]*?data-id="%d"' % pid, h)
    return int(m[0]) if m else None


def yorliq(pid):
    return len(js(req(C, "get", "/api/orders", params={"project_id": pid})) or [])


def qoida(pid):
    """Mustaqil orakul — `crud` dan foydalanmasdan: o'chirilmagan, qoralama / bekor emas; READY / DELIVERED — bajarilgan."""
    s = SessionLocal()
    try:
        oo = s.query(Order).filter(Order.project_id == pid).all()
        jami = [o for o in oo if not o.is_deleted and o.status not in (OrderStatus.DRAFT, OrderStatus.CANCELLED)]
        tay = [o for o in jami if o.status in (OrderStatus.READY, OrderStatus.DELIVERED)]
        return round(len(tay) / len(jami) * 100) if jami else 0
    finally:
        s.close()


def foydalar(pid):
    s = SessionLocal()
    try:
        oo = s.query(Order).filter(Order.project_id == pid, Order.company_id == 1, Order.status == OrderStatus.READY).all()
        with contextlib.redirect_stdout(_quiet):
            return {o.id: round(float(services.calculate_order_profit(s, o.id, company_id=1).get("foyda", 0)), 2) for o in oo}
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════
# A — foiz
# ══════════════════════════════════════════════════════════════
section("A. Bajarilish foizi — karta chizig'i = loyiha detali = qoida; to'plam = \"N ta buyurtma\" / Buyurtmalar yorlig'i")
P1, M1 = loyiha()
R1 = yarat(P1, M1); tayyor(R1)
R2 = yarat(P1, M1, 4); tayyor(R2)
I1 = yarat(P1, M1, 3)
D1 = yarat(P1, M1, draft=True)
X1 = yarat(P1, M1, 4); ochir(X1)
X2 = yarat(P1, M1, 5); eski_ochir(X2)
X3 = yarat(P1, M1, 2); eski_ochir(X3)
s = SessionLocal()
try:
    hol = {k: (s.get(Order, v).status.value, bool(s.get(Order, v).is_deleted))
           for k, v in (("R1", R1), ("R2", R2), ("I1", I1), ("D1", D1), ("X1", X1), ("X2", X2), ("X3", X3))}
finally:
    s.close()
check("A0 fikstura: R1 / R2 ready, I1 jarayonda, D1 qoralama, X1 ready+o'chirilgan, X2 / X3 jarayonda+o'chirilgan",
      hol == {"R1": ("ready", False), "R2": ("ready", False), "I1": ("in_progress", False), "D1": ("draft", False),
              "X1": ("ready", True), "X2": ("in_progress", True), "X3": ("in_progress", True)}, hol)
xm = xarita()
st, dt = detal(P1)
check("A1 karta chizig'i 67 % (R1, R2 / R1, R2, I1 — o'chirilganlar va qoralama maxrajda emas)", xm.get(P1) == 67, xm)
check("A2 loyiha detali progress_pct = karta chizig'i (67)", st == 200 and dt.get("progress_pct") == 67, (st, dt))
check("A3 qoida (mustaqil orakul) = karta = detal", qoida(P1) == xm.get(P1) == dt.get("progress_pct"), (qoida(P1), xm, dt))
check("A4 \"N ta buyurtma\" = Buyurtmalar yorlig'i = detal total_orders = 4 (o'chirilmaganlar, qoralama ham)",
      karta_soni(P1) == yorliq(P1) == dt.get("total_orders") == 4, (karta_soni(P1), yorliq(P1), dt.get("total_orders")))
check("A5 holatlar soni — o'chirilmaganlar (ready 2, in_progress 1, draft 1)",
      dt.get("status_counts") == {"ready": 2, "in_progress": 1, "draft": 1}, dt.get("status_counts"))
tayyor(I1)
xm = xarita()
st, dt = detal(P1)
check("A6 I1 «Tayyor» — 100 % (karta = detal = qoida)", xm.get(P1) == dt.get("progress_pct") == qoida(P1) == 100, (xm, dt))

# ══════════════════════════════════════════════════════════════
# B — foyda
# ══════════════════════════════════════════════════════════════
section("B. Loyiha \"Sof foyda\" — barcha «Tayyor» (o'chirilgan X1 ham) = oylik hisobot = Loyihalar sahifasi")
f = foydalar(P1)
st, dt = detal(P1)
_n0 = datetime.utcnow() + timedelta(hours=5)      # kech105: hisobot oyi — Toshkent devor soati
s = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        rep = services.get_monthly_report(s, _n0.year, _n0.month, company_id=1)
finally:
    s.close()
kpi = js(req(C, "get", "/api/projects/dashboard-stats")) or {}
check("B1 detal total_profit = R1 + R2 + I1 + X1 foydasi (o'chirilgan READY ham)",
      X1 in f and dt.get("total_profit") == round(sum(f.values())), (dt.get("total_profit"), f))
check("B2 detal total_profit = oylik hisobot buyurtmalar_foydasi = Loyihalar sahifasi total_profit (bitta loyiha)",
      dt.get("total_profit") == round(float(rep.get("buyurtmalar_foydasi") or 0)) == kpi.get("total_profit"),
      (dt.get("total_profit"), rep.get("buyurtmalar_foydasi"), kpi.get("total_profit")))
check("B3 X1 foydasi musbat (sinov ma'nosi — o'chirilgan qism haqiqatan hisobga kiradi)", f.get(X1, 0) > 0, f)

# ══════════════════════════════════════════════════════════════
# C — chegaralar
# ══════════════════════════════════════════════════════════════
section("C. Chegaralar")
P2, M2 = loyiha()
Y1 = yarat(P2, M2, 4); eski_ochir(Y1)
Y2 = yarat(P2, M2, 4); ochir(Y2)
xm = xarita()
st, dt = detal(P2)
check("C1 faqat o'chirilgan buyurtmalar — karta 0 (yoki yo'q), detal 0, total_orders 0",
      xm.get(P2, 0) == 0 and dt.get("progress_pct") == 0 and dt.get("total_orders") == 0, (xm.get(P2), dt))
check("C2 faqat o'chirilgan READY (Y2) foydasi — detal Sof foydada (hisobotda qolgan)",
      dt.get("total_profit") == round(sum(foydalar(P2).values())) and dt.get("total_profit") != 0, (dt, foydalar(P2)))
P3, M3 = loyiha()
yarat(P3, M3, draft=True)
xm = xarita()
st, dt = detal(P3)
check("C3 faqat qoralama — karta 0, detal 0 (qoralama maxrajda emas), total_orders 1",
      xm.get(P3, 0) == 0 and dt.get("progress_pct") == 0 and dt.get("total_orders") == 1, (xm.get(P3), dt))
P4, M4 = loyiha()
Z1 = yarat(P4, M4, 10)
Z2 = yarat(P4, M4)
holat_ozgar(Z1, status=OrderStatus.DELIVERED)
holat_ozgar(Z2, status=OrderStatus.CANCELLED)
xm = xarita()
st, dt = detal(P4)
check("C4 DELIVERED — bajarilgan, CANCELLED — maxrajda emas: 100 %", xm.get(P4) == dt.get("progress_pct") == qoida(P4) == 100,
      (xm.get(P4), dt))
P5, M5 = loyiha()
st, dt = detal(P5)
check("C5 buyurtmasiz loyiha — detal 0, xaritada yo'q", st == 200 and dt.get("progress_pct") == 0 and P5 not in xarita(),
      (st, dt))

# ══════════════════════════════════════════════════════════════
# K — korxona
# ══════════════════════════════════════════════════════════════
section("K. Korxona")
Q2p, Q2m = loyiha(2)
Q2 = yarat(Q2p, Q2m, klient=C2, peno=ID["PENO2"])
tayyor(Q2, klient=C2)
holat_ozgar(Q2, project_id=P1)          # buzilgan (korxonalararo) bog'lanish — B korxonasining READY buyurtmasi A loyihasida
xm = xarita()
st, dt = detal(P1)
check("K1 begona korxona buyurtmasi A loyihasi foizida / soni / foydasida sanalmaydi (karta = detal 100 %, 4 ta, foyda o'zgarmadi)",
      xm.get(P1) == 100 and dt.get("progress_pct") == 100 and dt.get("total_orders") == 4
      and dt.get("status_counts") == {"ready": 3, "draft": 1}
      and dt.get("total_profit") == round(sum(foydalar(P1).values())), (xm.get(P1), dt, foydalar(P1)))
xm2 = xarita(C2)
s = SessionLocal()
try:
    _b = s.query(Order).filter(Order.company_id == 2).all()
    _kut = {}
    for _pid in {o.project_id for o in _b}:
        _j = [o for o in _b if o.project_id == _pid and not o.is_deleted
              and o.status not in (OrderStatus.DRAFT, OrderStatus.CANCELLED)]
        if _j:
            _kut[_pid] = round(len([o for o in _j if o.status in (OrderStatus.READY, OrderStatus.DELIVERED)]) / len(_j) * 100)
finally:
    s.close()
check("K2 B korxonasi xaritasi — FAQAT B buyurtmalaridan (orakul bilan AYNAN; A buyurtmalari sanalmaydi)",
      xm2 == _kut, (xm2, _kut))
st, dt = detal(P1, C2)
check("K3 A loyihasi detali B korxonasidan — 404", st == 404, (st, dt))
check("K4 loyiha_bajarilish_foizi — crud da (yagona qoida)", callable(getattr(crud, "loyiha_bajarilish_foizi", None)), "")
s = SessionLocal()
try:
    _hamma = s.query(Order).filter(Order.project_id == P1, Order.company_id == 1).all()     # o'chirilganlar HAM
    _f = getattr(crud, "loyiha_bajarilish_foizi", None)
    _v = _f(_hamma) if _f else None
finally:
    s.close()
check("K5 qoida O'ZI o'chirilganlarni tashlaydi (ro'yxatga o'chirilganlar bilan berilsa ham — 100 %, X1 / X2 / X3 sanalmaydi)",
      _v == 100 == qoida(P1), (_v, qoida(P1)))

# ══════════════════════════════════════════════════════════════
# X / S
# ══════════════════════════════════════════════════════════════
section("X. Server xatosi (5xx) yo'q")
check("X1 test davomida 5xx yo'q", not XATOLAR_5XX, XATOLAR_5XX[:5])

section("S. Statik")
_pm = manba(main, "api_projects_progress_map")
check("S1 progress-map: qoralama / bekor, o'chirilgan va korxona filtri", tartibda(
    _pm, "Order.status.notin_([OrderStatus.DRAFT, OrderStatus.CANCELLED])", "Order.is_deleted.isnot(True)",
    "Order.company_id == auth.company_id_of(current_user)"), "")
_ds = manba(main, "api_project_detail_stats")
check("S2 detail-stats: foyda — korxonali READY (o'chirilgan ham); foiz — crud.loyiha_bajarilish_foizi(orders)",
      tartibda(_ds, "Order.is_deleted.isnot(True),", "Order.company_id == auth.company_id_of(current_user)).all()",
               "Order.company_id == auth.company_id_of(current_user),",
               "Order.status == OrderStatus.READY", "calculate_order_profit(", "progress_pct = crud.loyiha_bajarilish_foizi(orders)"), "")
_lf = manba(crud, "loyiha_bajarilish_foizi")
check("S3 qoida: o'chirilgan / qoralama / bekor o'tkaziladi, READY / DELIVERED — bajarilgan",
      tartibda(_lf, "if o.is_deleted or o.status in (_OS139.DRAFT, _OS139.CANCELLED):", "continue", "jami += 1",
               "if o.status in (_OS139.READY, _OS139.DELIVERED):"), "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(0 if FAIL == 0 else 1)
