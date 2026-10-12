#!/usr/bin/env python3
"""
test_audit_ombor.py — kech142 (zip 170): AUDIT — OMBOR topilmalari (A-O04, A-O05, A-O06, A-O09, A-O10 b/c) va egasi QARORI
«O'chirishdan oldin 0 bo'lsin».

NIMA UCHUN KERAK (har biri O'LCHANGAN — asl kod zip 169, `work/audit/tasdiq/ombor/p_o0N.py`, `work/k170/probe_dev178/`):
  A-O04 `FOR UPDATE` qatorni qulflardi-yu, sessiya shu materialni OLDIN o'qigan bo'lsa ESKI qiymatni qaytarardi (SQLAlchemy
        identity map, `populate_existing` yo'q) — mutlaq yozuv (`qoldiq = eski − blok`) parallel kirimni YO'QOTARDI: penoplast
        119.95 + 10 kirim − 0.05 → 119.9 (to'g'risi 129.85); qoldiq ≠ Σ harakat. Yetishmovchilik tekshiruvi ham qulfsiz edi.
  A-O05 Qoldiq o'zgarib, ombor HARAKATI yozilmaydigan 5 joy: buyurtma o'chirilishi / tiklanishi (penoplast), qisman «Tayyor»,
        ortgan loy «Tayyor loy» ga, material boshlang'ich qoldiq bilan yaratilishi — «Harakatlar tarixi» qoldiqqa mos kelmasdi.
  A-O06 Manfiy qoldiqli penoplastga kirim — blok hajmi MANFIY eski miqdor bilan o'rtachalanardi: −1 @1.0 + 4 @1.4 → 1.5333 m³
        (ikkala partiyadan ham katta), −1.9 @1.4 + 2 @1.0 → −6.6 m³ (buyurtma penoplastni AYIRISH o'rniga QO'SHARDI).
  A-O09 Mavjud nom bilan material yaratish faol materialni jimgina QAYTA YOZARDI (birligi, penoplast va asosiy penoplast
        belgisi, hajmi, minimal qoldig'i — retseptda / harakatlarda ishlatilgan bo'lsa ham); yashirin materialni tiklashda eski
        qoldiq ustidan yozilib, izsiz yo'qolardi (30 kg + 5 → 5 kg, harakat yo'q); parallel yaratish — 400.
  EGASI QARORI (12.10): qoldig'i 0 bo'lmagan material O'CHIRILMAYDI (409 + sabab: avval «Chiqim / Kirim (tuzatish)»).
  A-O10 b — Kirim hujjati qatorining to'lov turi (nasiya ↔ naqd) API orqali o'zgarib, pul ikki marta hisoblanardi;
        c — «mayda birlik» (`base_unit`) koeffitsientsiz saqlanib, retsept «500 g» ko'rsatib ombordan 500 QOP yechilardi.
TALAB (bo'limlar): Q — qulf + qayta o'qish (A-O04); H — harakatlar (A-O05); V — blok hajmi (A-O06); N — nom bandligi (A-O09);
  D — qoldiqli materialni o'chirish (egasi qarori); K — A-O10 b / c; har ssenariydan keyin «qoldiq = Σ harakat» (INV).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (har ishga yangi baza; parallel poygalar faqat PG da).
ISHLATISH: python3 tools/test_audit_ombor.py
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
PG_BAZA = "audit_ombor_test"
_T = tempfile.mkdtemp(prefix="audit_ombor_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'audit_ombor_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402
from sqlalchemy import func, case, event           # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Order, OrderItem, Inventory, InventoryMovement, InventoryPurchase,  # noqa: E402
                    FinishedProduct, Recipe, RecipeIngredient, Master, Supplier)
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
    auth.create_user(db, "ombor_admin", PAROL, UserRole.ADMIN, "Ombor Admin", company_id=1)
PRJ = Project(company_id=1, client_name="AO Mijoz", project_name="AO loyiha", total_budget=0, total_paid=0)
db.add(PRJ)
db.commit()
PRJ_ID = PRJ.id
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


def kirish():
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": "ombor_admin", "password": PAROL}, follow_redirects=False)
    assert r.status_code == 302, (r.status_code, r.text[:200])
    return _Mijoz(c)


C = kirish()


# ── yordamchilar ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def mat(nom, unit="kg", qoldiq=0.0, narx=1000.0, peno=False, hajm=1.0, asosiy=False, toifa=None):
    """Material ORM bilan qoldiq 0 da yaratiladi, boshlang'ich qoldiq — jurnalli `crud.update_stock` bilan (eski va yangi kodda
    ham harakat yoziladi — ssenariy oldidan «qoldiq = Σ harakat»)."""
    s = SessionLocal()
    try:
        m = Inventory(company_id=1, item_name=nom, unit=unit, stock_quantity=0, price_per_unit=narx, volume_per_unit=hajm,
                      is_penoplast=peno, is_default_penoplast=asosiy, category=toifa or ("Penoplast" if peno else "Kimyo"))
        s.add(m)
        s.commit()
        mid = m.id
    finally:
        s.close()
    if qoldiq:
        s = SessionLocal()
        try:
            crud.update_stock(s, mid, qoldiq, performed_by="fikstura", notes="boshlang'ich (jurnal bilan)", company_id=1)
        finally:
            s.close()
    return mid


def qoldiq(mid):
    s = SessionLocal()
    try:
        r = s.get(Inventory, mid)
        return None if r is None else round(float(r.stock_quantity or 0), 6)
    finally:
        s.close()


def sigma(mid):
    """Σ harakat (in − out) — `inventory_movements` dan."""
    s = SessionLocal()
    try:
        v = s.query(func.coalesce(func.sum(case((InventoryMovement.movement_type == "in", InventoryMovement.quantity),
                                                else_=-InventoryMovement.quantity)), 0.0)).filter(
            InventoryMovement.inventory_id == mid).scalar()
        return round(float(v or 0), 6)
    finally:
        s.close()


def harakatlar(mid):
    s = SessionLocal()
    try:
        return [(m.movement_type, round(float(m.quantity), 6), m.reason, m.order_id, m.unit)
                for m in s.query(InventoryMovement).filter(InventoryMovement.inventory_id == mid)
                .order_by(InventoryMovement.id).all()]
    finally:
        s.close()


def mat_hol(mid):
    s = SessionLocal()
    try:
        x = s.get(Inventory, mid)
        if x is None:
            return None
        return {"unit": x.unit, "qoldiq": round(float(x.stock_quantity or 0), 6), "min": float(x.min_stock or 0),
                "narx": round(float(x.price_per_unit or 0), 2), "peno": bool(x.is_penoplast),
                "asosiy": bool(x.is_default_penoplast), "hajm": round(float(x.volume_per_unit or 0), 4),
                "toifa": x.category, "yashirin": bool(x.is_deleted), "base_unit": x.base_unit,
                "factor": x.conversion_factor,
                "xaridlar": s.query(InventoryPurchase).filter(InventoryPurchase.inventory_id == mid).count()}
    finally:
        s.close()


def inv_tekshir(etiket, ids):
    """INV: har material uchun qoldiq = Σ harakat (in − out)."""
    yomon = []
    for i in ids:
        q, sg = qoldiq(i), sigma(i)
        if q is None or abs(q - sg) > 1e-6:
            yomon.append((i, q, sg))
    check(f"{etiket} — INV: qoldiq = Σ harakat (in − out)", not yomon, yomon[:5])


def buyurtma(pn, nom, uzunlik=10.0, qoplama=False, rc=None, usta=None, loy=0.0):
    it = {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": uzunlik, "quantity": uzunlik,
          "unit_price": 50000, "is_coated": qoplama, "penoplast_id": pn}
    tana = {"project_id": PRJ_ID, "order_type": "product", "is_draft": False, "items": [it]}
    if qoplama:
        it["recipe_id"] = rc
        tana.update({"loy_kg": loy, "recipe_id": rc, "master_id": usta})
    r = C.post("/api/orders", params={"confirm_shortage": "true"}, json=tana)
    return r.status_code, js(r).get("id")


def detal(oid):
    s = SessionLocal()
    try:
        return s.query(OrderItem.id).filter(OrderItem.order_id == oid).scalar()
    finally:
        s.close()


def poyga(fn_a, fn_b, kech=1.0, b_kechikish=0.3):
    """A — o'z sessiyasida, commit `kech` soniya kechiktiriladi (qulfni ushlab turadi); B — `b_kechikish` dan keyin."""
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
        except Exception as e:             # noqa: BLE001
            nat[0] = f"ISTISNO {type(e).__name__}: {e}"
        finally:
            sess.close()

    def t_b():
        bar.wait(timeout=30)
        time.sleep(b_kechikish)
        try:
            nat[1] = fn_b()
        except Exception as e:             # noqa: BLE001
            nat[1] = f"ISTISNO {type(e).__name__}: {e}"
    ts = [threading.Thread(target=t_a), threading.Thread(target=t_b)]
    [x.start() for x in ts]
    [x.join(timeout=120) for x in ts]
    return nat


def penoplast_tm(pn, nom):
    """Penoplast tayyor mahsuloti (karniz 10×10 sm, 10 m = 0.1 m³): `/api/finished/produce` + `/complete`."""
    r = C.post("/api/finished/produce", json={"name": nom, "category": "profil", "is_coated": False, "penoplast_id": pn,
                                              "unit_price": 100000, "loy_kg": 0, "width": 10, "thickness": 10, "length": 10,
                                              "quantity": 1})
    s = SessionLocal()
    try:
        fid = s.query(FinishedProduct.id).filter(FinishedProduct.name == nom).scalar()
    finally:
        s.close()
    rc = C.post(f"/api/finished/{fid}/complete")
    return r.status_code, rc.status_code, fid


def manba(obj):
    try:
        return inspect.getsource(obj)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q — A-O04: material qulfi — qiymat bazadan QAYTA o'qiladi (eski obyekt ustiga yozilmaydi)")
PNQ = mat("AO Q Penoplast", unit="blok", qoldiq=100, narx=500000, peno=True, hajm=1.0, asosiy=True)
_p = penoplast_tm(PNQ, "AO Q Karniz")
FQ = _p[2]
check("Q0 fikstura: penoplast mahsuloti yaratildi va yakunlandi (200 / 200)", _p[0] == 200 and _p[1] == 200 and FQ, _p)
inv_tekshir("Q0 fikstura", [PNQ])


def q_eskirgan(etiket, chaqiruv, mid, delta=10.0):
    """S1 materialni OLDIN o'qib havolani saqlaydi; S2 +delta kirim qilib commit; so'ng S1 da amal (chaqiruv(S1)).
    To'g'ri natija: yakuniy qoldiq = Σ harakat (S2 kirimi yo'qolmagan)."""
    s1 = SessionLocal()
    try:
        havola = s1.get(Inventory, mid)                      # obyekt S1 sessiyasida, havola SAQLANADI
        q_oldin = float(havola.stock_quantity or 0)
        s2 = SessionLocal()
        try:
            crud.update_stock(s2, mid, delta, performed_by="S2", notes="S2 parallel kirim", company_id=1)
        finally:
            s2.close()
        nat = chaqiruv(s1)
    finally:
        s1.close()
    q1, sg = qoldiq(mid), sigma(mid)
    check(f"{etiket}: S2 kirimi (+{delta:g}) yo'qolmadi — qoldiq = Σ harakat", abs(q1 - sg) < 1e-6,
          f"qoldiq {q1}, Σ {sg}, oldin (S1 ko'rgan) {q_oldin}, natija {str(nat)[:200]}")
    return nat


_q2 = xav(lambda: q_eskirgan("Q2 add_to_production (S1 penoplastni oldin o'qigan)",
                             lambda s: crud.add_to_production(s, FQ, 1, company_id=1), PNQ))
check("Q2b add_to_production muvaffaqiyatli", isinstance(_q2, dict) and _q2.get("success"), _q2)


def _q3(s):
    import schemas
    d = schemas.ProduceCreate(name="AO Q3 Karniz", category="profil", is_coated=False, penoplast_id=PNQ, unit_price=1000,
                              loy_kg=0, width=10, thickness=10, length=10, quantity=1)
    return crud.produce_finished_product(s, d, created_by="Q3", company_id=1)


xav(lambda: q_eskirgan("Q3 produce_finished_product (S1 penoplastni oldin o'qigan)", _q3, PNQ))


def _q5(s):
    r = crud.get_item_locked(s, PNQ, company_id=1)
    return float(r.stock_quantity)


_q5n = xav(lambda: q_eskirgan("Q5 get_item_locked qulf ostida bazadagi qiymatni qaytaradi", _q5, PNQ, delta=3))
check("Q5b get_item_locked natijasi = bazadagi qoldiq (S2 kirimi bilan)", lambda: abs(_q5n - qoldiq(PNQ)) < 1e-6,
      (_q5n, qoldiq(PNQ)))


def q5c():
    """Q5c: sessiyadagi YOZILMAGAN o'zgarish qulf + qayta o'qishda yo'qolmaydi (avval flush)."""
    m = mat("AO Q5c Mel", qoldiq=50)
    s = SessionLocal()
    try:
        x = s.get(Inventory, m)
        x.min_stock = 77                                     # hali flush qilinmagan
        y = crud.get_item_locked(s, m, company_id=1)
        v = float(y.min_stock or 0)
        s.commit()
    finally:
        s.close()
    check("Q5c yozilmagan o'zgarish (min 77) qulf + qayta o'qishda saqlanadi", v == 77 and mat_hol(m)["min"] == 77,
          (v, mat_hol(m)))


xav(q5c)


def _q6(s):
    r = services._peno_of(s, PNQ, 1, lock=True)
    return float(r.stock_quantity)


_q6n = xav(lambda: q_eskirgan("Q6 services._peno_of(lock=True) — qayta o'qiydi", _q6, PNQ, delta=2))
check("Q6b _peno_of(lock=True) natijasi = bazadagi qoldiq", lambda: abs(_q6n - qoldiq(PNQ)) < 1e-6, (_q6n, qoldiq(PNQ)))


def q4():
    """Q4: qoplamali penoplast mahsuloti — «+» (add_to_production) loy ingredienti (Kley) S1 da oldin o'qilgan."""
    kl = mat("AO Q4 Kley", qoldiq=1000, narx=2000)
    s = SessionLocal()
    try:
        rec = Recipe(company_id=1, name="AO Q4 retsept", batch_size_kg=100.0)
        s.add(rec)
        s.flush()
        s.add(RecipeIngredient(recipe_id=rec.id, inventory_id=kl, quantity_kg=100.0))
        s.commit()
        rc = rec.id
    finally:
        s.close()
    r = C.post("/api/finished/produce", json={"name": "AO Q4 Karniz", "category": "profil", "is_coated": True,
                                              "penoplast_id": PNQ, "unit_price": 100000, "loy_kg": 10, "recipe_id": rc,
                                              "width": 10, "thickness": 10, "length": 10, "quantity": 1})
    s = SessionLocal()
    try:
        fid = s.query(FinishedProduct.id).filter(FinishedProduct.name == "AO Q4 Karniz").scalar()
    finally:
        s.close()
    rc2 = C.post(f"/api/finished/{fid}/complete")
    check("Q4 fikstura: qoplamali mahsulot (loy 10 kg) yaratildi va yakunlandi", r.status_code == 200 and rc2.status_code == 200,
          (r.status_code, js(r), rc2.status_code, js(rc2)))
    inv_tekshir("Q4 fikstura (Kley)", [kl])

    def amal(s1):
        rr = s1.get(Recipe, rc)
        _ = [ing.inventory.stock_quantity for ing in rr.ingredients]     # ingredient obyektlari S1 da (havola rr orqali)
        return crud.add_to_production(s1, fid, 5, company_id=1)
    nat = q_eskirgan("Q4 add_to_production — loy ingredienti (Kley) S1 da oldin o'qilgan", amal, kl, delta=100)
    check("Q4b «+» muvaffaqiyatli", isinstance(nat, dict) and nat.get("success"), nat)


xav(q4)

if PG_URL:
    def q1(urinish):
        q0 = qoldiq(PNQ)
        n = poyga(lambda s: crud.update_stock(s, PNQ, 10, performed_by="A", notes="A kirim", company_id=1),
                  lambda: C.post(f"/api/finished/{FQ}/add", json={"quantity": 10}))
        b = n[1]
        check(f"Q1 #{urinish} PG poyga: A +10 kirim (qulf ushlaydi) ∥ B «+» 10 m — B 200",
              getattr(b, "status_code", None) == 200, (getattr(b, "status_code", b), js(b) if hasattr(b, "json") else b))
        check(f"Q1 #{urinish} penoplast = oldin + 10 − 0.05 (10 m karniz; kirim yo'qolmadi)",
              lambda: abs(qoldiq(PNQ) - round(q0 + 10 - 0.05, 6)) < 1e-6, (q0, qoldiq(PNQ)))
        inv_tekshir(f"Q1 #{urinish}", [PNQ])
    for _u in (1, 2):
        xav(lambda u=_u: q1(u))

    def q7():
        """Q7: A penoplastdan chiqim (qulf ushlaydi) ∥ B «+» — A dan keyin qoldiq yetmaydi: B 400 «yetishmayapti», manfiy yo'q."""
        pn = mat("AO Q7 Penoplast", unit="blok", qoldiq=10, narx=500000, peno=True, hajm=1.0)
        _t = penoplast_tm(pn, "AO Q7 Karniz")
        fid = _t[2]
        q0 = qoldiq(pn)                                  # 10 − 0.05 = 9.95
        n = poyga(lambda s: crud.update_stock(s, pn, -(q0 - 0.04), performed_by="A", notes="A chiqim", company_id=1),
                  lambda: C.post(f"/api/finished/{fid}/add", json={"quantity": 10}))
        b = n[1]
        check("Q7 PG poyga: A chiqimidan keyin 0.04 blok qoladi, B «+» 10 m (0.05 blok) so'raydi — B 400 «yetishmayapti»",
              getattr(b, "status_code", None) == 400 and "yetishmay" in str(js(b)).lower(),
              (getattr(b, "status_code", b), js(b) if hasattr(b, "json") else b))
        check("Q7 penoplast qoldig'i = 0.04 (manfiy emas, A chiqimi yo'qolmadi)", lambda: abs(qoldiq(pn) - 0.04) < 1e-6,
              qoldiq(pn))
        inv_tekshir("Q7", [pn])
    xav(q7)
else:
    print("  (SQLite — parallel poygalar Q1 / Q7 o'tkazib yuborildi; PG_URL bilan ishga tushiring)")

section("QS — A-O04 statik: material qulflari bazadan qayta o'qiydi")
_qulf_funks = [
    ("crud.get_item_locked", crud.get_item_locked),
    ("crud.add_to_production", crud.add_to_production),
    ("crud.produce_finished_product", crud.produce_finished_product),
    ("crud.delete_purchase", getattr(crud, "delete_purchase", None)),
    ("services._peno_of", services._peno_of),
    ("services.deduct_loy_ingredients", services.deduct_loy_ingredients),
    ("services.return_loy_ingredients", services.return_loy_ingredients),
    ("services.get_or_create_loy_stock", services.get_or_create_loy_stock),
]


def inv_qulf_eski(src):
    """Manbadagi `Inventory` (`_Inv`) so'rovlarining `.with_for_update()` qulflari — `populate_existing` siz bo'lganlari
    (so'rov boshi — eng yaqin `db.query(` / `_q =` / `q =`)."""
    yomon = []
    i = src.find(".with_for_update()")
    while i >= 0:
        bosh = max(src.rfind("db.query(", 0, i), src.rfind("_q = ", 0, i), src.rfind(" q = ", 0, i))
        parcha = src[bosh if bosh >= 0 else max(0, i - 300):i + 30]
        if ("Inventory" in parcha or "_Inv" in parcha) and "populate_existing" not in parcha:
            yomon.append(parcha.strip()[:160])
        i = src.find(".with_for_update()", i + 1)
    return yomon


for _nom, _f in _qulf_funks:
    _m = manba(_f)
    _y = inv_qulf_eski(_m)
    check(f"QS {_nom}: Inventory qulfi `inventory_qulf` / `populate_existing` bilan (qayta o'qiydi)",
          bool(_m) and ("inventory_qulf" in _m or "populate_existing" in _m) and not _y, _y or _nom)
_hamma_eski = []
for _modul in (crud, services, __import__("production_service")):
    _y = inv_qulf_eski(manba(_modul))
    _hamma_eski += [(_modul.__name__, x) for x in _y]
check("QS crud / services / production_service: Inventory ning HAMMA `FOR UPDATE` qulfi qayta o'qiydi", not _hamma_eski,
      _hamma_eski[:6])
_ms = manba(services.deduct_raw_material_for_brak)
check("QS services.deduct_raw_material_for_brak: penoplast qulf bilan o'qiladi (`_peno_of(…, lock=True)`)",
      "_peno_of(db, pid, _bcid, lock=True)" in _ms)
_ma = manba(crud.add_to_production)
_i_q = _ma.find("inventory_qulf_sorov(")
_i_s = _ma.find("shortages.append")
check("QS add_to_production: penoplast yetishmovchilik tekshiruvi QULFLANGAN qatorda (qulf tekshiruvdan oldin)",
      0 <= _i_q < _i_s, (_i_q, _i_s))
_mp = manba(crud.produce_finished_product)
_i_q = _mp.find("p = _pf_inv(pid, lock=True)")
_i_s = _mp.find("shortages.append")
check("QS produce_finished_product: penoplast yetishmovchilik tekshiruvi QULFLANGAN qatorda", 0 <= _i_q < _i_s, (_i_q, _i_s))
_mi = manba(getattr(crud, "inventory_qulf_sorov", None))
_mi = _mi.split('"""')[-1] if _mi.count('"""') >= 2 else _mi          # izohsiz (kod qismi)
check("QS crud.inventory_qulf_sorov: avval flush, so'ng populate_existing + FOR UPDATE",
      "db.flush()" in _mi and "populate_existing().with_for_update()" in _mi
      and _mi.find("db.flush()") < _mi.find("populate_existing"), _mi[:300])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H — A-O05: qoldiq o'zgarishi ombor HARAKATI bilan (qoldiq = Σ harakat)")
PNH = mat("AO H Penoplast", unit="blok", qoldiq=100, narx=500000, peno=True, hajm=1.0)


def h_qadam(etiket, fn, ids, kutilgan=None):
    q0 = {i: qoldiq(i) for i in ids}
    h0 = {i: len(harakatlar(i)) for i in ids}
    r = fn()
    for i in ids:
        dq = round(qoldiq(i) - q0[i], 6)
        yangi = harakatlar(i)[h0[i]:]
        dm = round(sum(x[1] if x[0] == "in" else -x[1] for x in yangi), 6)
        check(f"{etiket} — Δqoldiq = Δharakat (#{i})", abs(dq - dm) < 1e-6, f"Δqoldiq {dq}, Δharakat {dm}, yangi {yangi}")
        if kutilgan and i in kutilgan:
            kut = kutilgan[i]
            check(f"{etiket} — harakat: {kut}", any(all(str(k) in str(x) for k in kut) for x in yangi), yangi)
    return r


def h1():
    st, o1 = buyurtma(PNH, "AO H1 profil")
    check("H1 fikstura: buyurtma yaratildi (penoplast yechildi)", st == 200 and o1, st)
    s = SessionLocal()
    nr = s.get(Order, o1).order_number
    s.close()
    h_qadam("H1 yetkazilmagan buyurtma o'chirildi — penoplast qaytdi «in»", lambda: C.delete(f"/api/orders/{o1}"), [PNH],
            {PNH: ("in", "o'chirildi", nr)})
    inv_tekshir("H1", [PNH])


xav(h1)


def h1c():
    """H1c: qaytish harakati DARHOL bazaga yoziladi — chaqiruvchi shu tranzaksiyada buyurtmani butunlay o'chirsa (`crud.delete_order`
    buyurtmaga bog'langan harakatlarni bitta UPDATE bilan uzadi), sessiyada kutib turgan yozuv o'chgan buyurtmaga bog'lanib qolmaydi
    (PG da FK xatosi bo'lardi)."""
    st, oc = buyurtma(PNH, "AO H1c profil")
    s = SessionLocal()
    try:
        o = s.get(Order, oc)
        services.return_inventory_for_order(s, o)
        crud.delete_order(s, oc, soft=False, performed_by="H1c")
        ok = True
        xato = None
    except Exception as e:                 # noqa: BLE001
        s.rollback()
        ok, xato = False, f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        s.close()
    check("H1c qaytish + darhol butunlay o'chirish (bitta tranzaksiya) — xatosiz, harakat qoldi (bog'lami uzilgan)",
          st == 200 and ok and any(x[0] == "in" and x[3] is None and "o'chirildi" in str(x[2]) for x in harakatlar(PNH)),
          (st, xato, harakatlar(PNH)[-2:]))
    inv_tekshir("H1c", [PNH])


xav(h1c)


def h4():
    """H4: to'liq tiklash shoxi (`return_inventory_for_order(sign=-1)` — savatdagi, hech narsa topshirilmagan buyurtma
    tiklanganda) — to'g'ridan-to'g'ri chaqiruv."""
    st, o4 = buyurtma(PNH, "AO H4 profil")
    s0 = SessionLocal()
    nr = s0.get(Order, o4).order_number
    s0.close()

    def amal():
        s = SessionLocal()
        try:
            r = services.return_inventory_for_order(s, s.get(Order, o4), sign=-1.0)
            s.commit()
            return r
        finally:
            s.close()
    h_qadam("H4 buyurtma tiklandi (to'liq) — penoplast qayta yechildi «out»", amal, [PNH], {PNH: ("out", "tiklandi", nr)})
    inv_tekshir("H4", [PNH])


xav(h4)


def h2():
    st, o2 = buyurtma(PNH, "AO H2 profil")
    i2 = detal(o2)
    rd = C.post("/api/deliveries", json={"order_id": o2, "items": [{"order_item_id": i2, "quantity": 4}], "notes": "h2",
                                         "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    check("H2 fikstura: buyurtma + yuk xati 4 m", st == 200 and rd.status_code == 200, (st, rd.status_code, js(rd)))
    h_qadam("H2 qisman topshirilgan buyurtma o'chirildi — qolgan qism penoplasti «in» (qolgan qism)",
            lambda: C.delete(f"/api/orders/{o2}"), [PNH], {PNH: ("in", "qolgan qism")})
    h_qadam("H3 qisman buyurtma tiklandi — qolgan qism penoplasti «out»", lambda: C.post(f"/api/orders/{o2}/restore"), [PNH],
            {PNH: ("out", "qolgan qism")})
    inv_tekshir("H2/H3", [PNH])


xav(h2)


def h5():
    st, o5 = buyurtma(PNH, "AO H5 profil")
    i5 = detal(o5)
    C.post("/api/deliveries", json={"order_id": o5, "items": [{"order_item_id": i5, "quantity": 4}], "notes": "h5",
                                    "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    h_qadam("H5 qisman topshirilgan buyurtma «Tayyor» — qolgan qism penoplasti «in» («Tayyor» (qisman))",
            lambda: C.post(f"/api/orders/{o5}/ready"), [PNH], {PNH: ("in", "«Tayyor» (qisman)")})
    inv_tekshir("H5", [PNH])


xav(h5)


def h6():
    kl = mat("AO H6 Kley", qoldiq=10000, narx=2000)
    s = SessionLocal()
    try:
        rec = Recipe(company_id=1, name="AO H6 retsept", batch_size_kg=100.0)
        s.add(rec)
        s.flush()
        s.add(RecipeIngredient(recipe_id=rec.id, inventory_id=kl, quantity_kg=100.0))
        usta = Master(company_id=1, name="AO H6 Usta", phone="+998900007601")
        s.add(usta)
        s.commit()
        rc, us = rec.id, usta.id
    finally:
        s.close()
    st, o6 = buyurtma(PNH, "AO H6 profil", qoplama=True, rc=rc, usta=us, loy=10.0)
    check("H6 fikstura: qoplamali buyurtma (loy 10 kg)", st == 200 and o6, st)
    s = SessionLocal()
    nr = s.get(Order, o6).order_number
    s.close()
    r = C.post(f"/api/orders/{o6}/ready", params={"loy_kg": "7"})
    check("H6 «Tayyor» (loy 7 kg) — 200", r.status_code == 200, (r.status_code, js(r)))
    s = SessionLocal()
    try:
        zx = s.query(Inventory).filter(Inventory.item_name == "Tayyor loy (AO H6 retsept)").first()
        zid = zx.id if zx else None
    finally:
        s.close()
    check("H6 ortgan loy «Tayyor loy (AO H6 retsept)» zaxirasiga +3 kg", zid and abs(qoldiq(zid) - 3.0) < 1e-6,
          (zid, zid and qoldiq(zid)))
    if zid:
        hz = harakatlar(zid)
        check("H6 «Tayyor loy» kirimi ombor harakati bilan («in» 3, sababda buyurtma raqami, order_id BO'SH)",
              any(x[0] == "in" and abs(x[1] - 3.0) < 1e-6 and nr in str(x[2]) and x[3] is None for x in hz), hz)
        inv_tekshir("H6 (Tayyor loy, Kley)", [zid, kl])


xav(h6)


def h7():
    r = C.post("/api/inventory", json={"item_name": "AO H7 Gips", "unit": "kg", "stock_quantity": 50, "price_per_unit": 1000})
    check("H7 POST /api/inventory qoldiq 50, narx 1000 — 200", r.status_code == 200, (r.status_code, js(r)))
    mid = js(r).get("id")
    if mid:
        hz = harakatlar(mid)
        check("H7 boshlang'ich qoldiq «in» 50 harakati (sabab «Boshlang'ich qoldiq»)",
              any(x[0] == "in" and abs(x[1] - 50) < 1e-6 and "Boshlang'ich qoldiq" in str(x[2]) for x in hz), hz)
        check("H7 xarid yozuvi 1 ta (Moliya)", mat_hol(mid)["xaridlar"] == 1, mat_hol(mid))
        inv_tekshir("H7", [mid])
    r = C.post("/api/inventory", json={"item_name": "AO H7b Qum", "unit": "kg", "stock_quantity": 20})
    mid = js(r).get("id")
    check("H7b narxsiz qoldiq 20 — 200, «in» 20 harakati, xarid YO'Q",
          r.status_code == 200 and mid and any(x[0] == "in" and abs(x[1] - 20) < 1e-6 for x in harakatlar(mid))
          and mat_hol(mid)["xaridlar"] == 0, (r.status_code, js(r), mid and harakatlar(mid)))
    if mid:
        inv_tekshir("H7b", [mid])


xav(h7)

section("HS — A-O05 statik: qoldiq yozuvi bor funksiyalarda harakat yozuvi ham bor")
for _nom, _f in (("services.return_inventory_for_order", services.return_inventory_for_order),
                 ("services.return_inventory_for_order_partial", services.return_inventory_for_order_partial),
                 ("services.add_loy_to_stock", services.add_loy_to_stock),
                 ("crud.add_item", crud.add_item)):
    _m = manba(_f)
    check(f"HS {_nom}: `log_movement` / `_penoplast_qaytish_harakati` chaqiriladi",
          "log_movement(" in _m or "_penoplast_qaytish_harakati(" in _m, _nom)
_ml = manba(services.add_loy_to_stock)
check("HS add_loy_to_stock: harakat `order_id=None` bilan (yakunlangan buyurtma qoplama tannarxi o'zgarmasin)",
      "order_id=None" in _ml)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("V — A-O06: penoplast blok hajmi — eski qoldiq 0 / manfiy bo'lsa o'rtachaga kirmaydi")


def manfiy_penoplast(nom, eski, hajm, narx=400000):
    """Penoplast eski qoldiq `eski` (manfiy) bilan — jurnalli (chiqim harakati)."""
    pn = mat(nom, unit="blok", qoldiq=0, narx=narx, peno=True, hajm=hajm)
    s = SessionLocal()
    try:
        x = s.get(Inventory, pn)
        x.stock_quantity = eski
        crud.log_movement(s, pn, nom, "out", -eski, unit="blok", reason="fikstura: buyurtmaga yechilgan (qoldiq manfiy)",
                          company_id=1)
        s.commit()
    finally:
        s.close()
    return pn


def kirim(pn, q, narx, hajm):
    return C.post(f"/api/inventory/{pn}/purchase", json={"quantity": q, "price_per_unit": narx, "volume_per_unit": hajm})


def v1():
    pn = manfiy_penoplast("AO V1 Penoplast", -1.0, 1.0)
    r = kirim(pn, 4, 560000, 1.4)
    h = mat_hol(pn)
    check("V1 −1 blok @1.0 m³ + kirim 4 @1.4 → hajm 1.4 (ilgari 1.5333 — ikkala partiyadan ham katta)",
          r.status_code == 200 and abs(h["hajm"] - 1.4) < 1e-6, (r.status_code, h))
    check("V1 narx 560 000 (yangi), qoldiq 3", abs(h["narx"] - 560000) < 0.01 and abs(h["qoldiq"] - 3) < 1e-6, h)
    check("V1 javob: new_volume / volume_changed = saqlangan qiymat",
          abs(float(js(r).get("new_volume", 0) or 0) - h["hajm"]) < 1e-4 if "new_volume" in js(r) else True, js(r))
    q0 = qoldiq(pn)
    s = SessionLocal()
    try:
        _o = C.post("/api/orders", params={"confirm_shortage": "true"}, json={
            "project_id": PRJ_ID, "order_type": "product", "is_draft": False,
            "items": [{"name": "AO V2 blok", "category": "profil", "width": 100, "thickness": 100, "length": 1.4,
                       "quantity": 1.4, "unit_price": 50000, "is_coated": False, "penoplast_id": pn}]})
    finally:
        s.close()
    check("V2 keyingi buyurtma 0.7 m³ — 0.5 blok yechildi (ilgari 0.4565)",
          _o.status_code == 200 and abs((q0 - qoldiq(pn)) - 0.5) < 1e-6, (_o.status_code, q0, qoldiq(pn)))
    inv_tekshir("V1/V2", [pn])


xav(v1)


def v3():
    pn = manfiy_penoplast("AO V3 Penoplast", -1.9, 1.4)
    r = kirim(pn, 2, 400000, 1.0)
    h = mat_hol(pn)
    check("V3 −1.9 @1.4 + kirim 2 @1.0 → hajm 1.0 (ilgari −6.6 — manfiy hajm)", r.status_code == 200 and abs(h["hajm"] - 1.0) < 1e-6,
          (r.status_code, h))
    q0 = qoldiq(pn)
    _o = C.post("/api/orders", params={"confirm_shortage": "true"}, json={
        "project_id": PRJ_ID, "order_type": "product", "is_draft": False,
        "items": [{"name": "AO V3b blok", "category": "profil", "width": 100, "thickness": 100, "length": 0.05,
                   "quantity": 0.05, "unit_price": 50000, "is_coated": False, "penoplast_id": pn}]})
    check("V3b keyingi buyurtma penoplastni KAMAYTIRADI (oshirmaydi)", _o.status_code == 200 and qoldiq(pn) < q0,
          (_o.status_code, q0, qoldiq(pn)))
    inv_tekshir("V3", [pn])


xav(v3)


def v4():
    pn = manfiy_penoplast("AO V4 Penoplast", -3.9, 1.0)
    r = kirim(pn, 4, 560000, 1.4)
    h = mat_hol(pn)
    check("V4 −3.9 @1.0 + kirim 4 @1.4 → hajm 1.4 (ilgari 17.0)", r.status_code == 200 and abs(h["hajm"] - 1.4) < 1e-6,
          (r.status_code, h))
    inv_tekshir("V4", [pn])


xav(v4)


def v5():
    pn = mat("AO V5 Penoplast", unit="blok", qoldiq=0, narx=400000, peno=True, hajm=1.0)
    kirim(pn, 2, 400000, 1.0)
    r = kirim(pn, 4, 560000, 1.4)
    h = mat_hol(pn)
    check("V5 NAZORAT +2 @1.0 + 4 @1.4 → o'rtacha 1.2667 (avvalgidek)", r.status_code == 200 and abs(h["hajm"] - 1.2667) < 1e-4,
          (r.status_code, h))
    pn6 = mat("AO V6 Penoplast", unit="blok", qoldiq=0, narx=400000, peno=True, hajm=1.0)
    r = kirim(pn6, 4, 560000, 1.4)
    check("V6 qoldiq 0 + kirim 4 @1.4 → 1.4", r.status_code == 200 and abs(mat_hol(pn6)["hajm"] - 1.4) < 1e-6, mat_hol(pn6))
    inv_tekshir("V5/V6", [pn, pn6])


xav(v5)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("N — A-O09: mavjud nom bilan material yaratish — faol material qayta yozilmaydi (409 + id)")


def n1():
    r = C.post("/api/inventory", json={"item_name": "AO N1 Akril", "unit": "kg", "min_stock": 25, "price_per_unit": 3000,
                                       "category": "Kimyoviy qo'shimchalar"})
    a = js(r).get("id")
    C.post(f"/api/inventory/{a}/stock", json={"quantity_change": 10, "reason": "inventarizatsiya"})
    C.post(f"/api/inventory/{a}/stock", json={"quantity_change": -10, "reason": "ishlatildi"})
    oldin = mat_hol(a)
    r2 = C.post("/api/inventory", json={"item_name": "AO N1 Akril", "unit": "litr", "min_stock": 0, "is_penoplast": True,
                                        "volume_per_unit": 2.5, "category": "Penoplast"})
    d = js(r2).get("detail")
    check("N1 faol (ishlatilgan, qoldiq 0) material nomi boshqa birlik / penoplast bilan — 409",
          r2.status_code == 409, (r2.status_code, js(r2)))
    check("N1 409 javobi: type «material_nomi_band», mavjud material id si, birligi",
          isinstance(d, dict) and d.get("type") == "material_nomi_band" and d.get("id") == a and d.get("unit") == "kg", d)
    check("N1 mavjud material O'ZGARMADI (birlik, penoplast, asosiy belgisi, hajm, min, toifa)", mat_hol(a) == oldin,
          (oldin, mat_hol(a)))
    pen = js(C.get("/api/penoplasts"))
    check("N2 /api/penoplasts — «AO N1 Akril» penoplast emas", "AO N1 Akril" not in str(pen), str(pen)[:300])
    inv_tekshir("N1", [a])


xav(n1)


def n3():
    r = C.post("/api/inventory", json={"item_name": "AO N3 Lenta", "unit": "metr", "min_stock": 50, "price_per_unit": 200})
    lid = js(r).get("id")
    oldin = mat_hol(lid)
    r2 = C.post("/api/inventory", json={"item_name": "AO N3 Lenta", "unit": "rulon", "min_stock": 2})
    check("N3 faol, hech ishlatilmagan material — boshqa birlik bilan qayta yaratish 409, o'zgarmadi",
          r2.status_code == 409 and mat_hol(lid) == oldin and (js(r2).get("detail") or {}).get("id") == lid,
          (r2.status_code, js(r2), mat_hol(lid)))
    r3 = C.post("/api/inventory", json={"item_name": "AO N3 Lenta", "unit": "metr", "min_stock": 50, "price_per_unit": 200})
    check("N4 AYNAN bir xil tana bilan ham — 409 (id bilan; jim qayta ishlatish yo'q)",
          r3.status_code == 409 and (js(r3).get("detail") or {}).get("id") == lid, (r3.status_code, js(r3)))
    r4 = C.post("/api/inventory", json={"item_name": "  AO N3 Lenta  ", "unit": "metr"})
    check("N4b chetida bo'shliqli nom ham — 409", r4.status_code == 409, (r4.status_code, js(r4)))


xav(n3)


def yashirin_mat(nom, unit="kg", q=30.0, narx=1000.0, peno=False, hajm=1.0):
    """Eski holat: yashirilgan (is_deleted) material, qoldig'i bor, tarixi bilan (endi o'chirib bo'lmaydi — faqat eski ma'lumot)."""
    m = mat(nom, unit=unit, qoldiq=q, narx=narx, peno=peno, hajm=hajm)
    s = SessionLocal()
    try:
        s.get(Inventory, m).is_deleted = True
        s.commit()
    finally:
        s.close()
    return m


def n5():
    m = yashirin_mat("AO N5 Mel", q=30, narx=1000)
    x0 = mat_hol(m)["xaridlar"]
    r = C.post("/api/inventory", json={"item_name": "AO N5 Mel", "unit": "kg", "stock_quantity": 5, "price_per_unit": 1200})
    h = mat_hol(m)
    check("N5 yashirin material (qoldiq 30) shu birlikda qayta yaratildi — 200, o'sha id, ko'rinadi",
          r.status_code == 200 and js(r).get("id") == m and not h["yashirin"], (r.status_code, js(r), h))
    check("N5 qoldiq 35 (eski 30 saqlandi + 5), «in» 5 harakati, xarid +1",
          abs(h["qoldiq"] - 35) < 1e-6 and h["xaridlar"] == x0 + 1
          and any(x[0] == "in" and abs(x[1] - 5) < 1e-6 for x in harakatlar(m)), (h, harakatlar(m)))
    check("N5 narx o'rtacha vaznli (30·1000 + 5·1200)/35 = 1028.57", abs(h["narx"] - 1028.57) < 0.01, h)
    inv_tekshir("N5", [m])


xav(n5)


def n6():
    m = yashirin_mat("AO N6 Bo'r", q=12)
    oldin = mat_hol(m)
    r = C.post("/api/inventory", json={"item_name": "AO N6 Bo'r", "unit": "qop", "stock_quantity": 2})
    d = js(r).get("detail")
    check("N6 yashirin material boshqa birlik bilan — 409 «material_nomi_yashirin», qator o'zgarmadi va yashirin",
          r.status_code == 409 and isinstance(d, dict) and d.get("type") == "material_nomi_yashirin" and mat_hol(m) == oldin,
          (r.status_code, d, mat_hol(m)))
    r2 = C.post("/api/inventory", json={"item_name": "AO N6 Bo'r", "unit": "kg", "is_penoplast": True, "category": "Penoplast"})
    check("N6b yashirin oddiy material penoplast sifatida — 409, o'zgarmadi", r2.status_code == 409 and mat_hol(m) == oldin,
          (r2.status_code, js(r2), mat_hol(m)))
    inv_tekshir("N6", [m])


xav(n6)


def n7():
    m = yashirin_mat("AO N7 Penoplast", unit="blok", q=0, narx=500000, peno=True, hajm=1.4)
    r = C.post("/api/inventory", json={"item_name": "AO N7 Penoplast", "unit": "blok", "is_penoplast": True,
                                       "category": "Penoplast"})
    h = mat_hol(m)
    check("N7 yashirin penoplast (hajm 1.4) hajmsiz qayta yaratildi — hajm 1.4 QOLDI (ilgari 1.0)",
          r.status_code == 200 and abs(h["hajm"] - 1.4) < 1e-6, (r.status_code, js(r), h))
    inv_tekshir("N7", [m])


xav(n7)


def n8():
    m = yashirin_mat("AO N8 Eski qop", unit="qop", q=0)
    s = SessionLocal()
    try:
        s.get(Inventory, m).base_unit = "g"  # eski yozuv: koeffitsientsiz mayda birlik
        s.commit()
    finally:
        s.close()
    r = C.post("/api/inventory", json={"item_name": "AO N8 Eski qop", "unit": "qop", "stock_quantity": 2})
    check("N8 eski (koeffitsientsiz) yashirin material — mayda birlik yuborilmasa tiklanadi (200, o'sha id)",
          r.status_code == 200 and js(r).get("id") == m and not mat_hol(m)["yashirin"], (r.status_code, js(r)))
    r2 = C.post("/api/inventory", json={"item_name": "AO N8b Eski", "unit": "qop", "base_unit": "g"})
    check("N8b yangi material koeffitsientsiz mayda birlik bilan — 400 (yangi qoida o'z kuchida)", r2.status_code == 400,
          (r2.status_code, js(r2)))
    inv_tekshir("N8", [m])


xav(n8)

if PG_URL:
    def n9():
        nom = "AO N9 Parallel"

        def sekin(sess, ctx, instances):
            if any(isinstance(o, Inventory) and o.item_name == nom for o in sess.new):
                time.sleep(0.6)
        event.listen(SessionLocal, "before_flush", sekin)
        try:
            nat = [None, None]
            bar = threading.Barrier(2)

            def t(k):
                bar.wait(timeout=30)
                nat[k] = C.post("/api/inventory", json={"item_name": nom, "unit": "kg", "stock_quantity": 0})
            ts = [threading.Thread(target=t, args=(k,)) for k in (0, 1)]
            [x.start() for x in ts]
            [x.join(timeout=60) for x in ts]
        finally:
            event.remove(SessionLocal, "before_flush", sekin)
        kodlar = sorted(getattr(x, "status_code", 0) for x in nat)
        check("N9 PG: bir nom bilan ikki parallel yaratish — biri 200, ikkinchisi 409 (400 / 500 emas)",
              kodlar == [200, 409], [(getattr(x, "status_code", x), js(x) if hasattr(x, "json") else x) for x in nat])
        _409 = next((x for x in nat if getattr(x, "status_code", 0) == 409), None)
        _200 = next((x for x in nat if getattr(x, "status_code", 0) == 200), None)
        check("N9 409 javobida yaratilgan material id si",
              _409 is not None and _200 is not None and (js(_409).get("detail") or {}).get("id") == js(_200).get("id"),
              (_409 is not None and js(_409), _200 is not None and js(_200)))
    xav(n9)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — EGASI QARORI «O'chirishdan oldin 0 bo'lsin»: qoldig'i bor material o'chirilmaydi")


def d1():
    m = mat("AO D1 Kraska", qoldiq=7, narx=5000)
    oldin = mat_hol(m)
    r = C.delete(f"/api/inventory/{m}")
    check("D1 qoldig'i 7 kg material — DELETE 409, sababda «Chiqim (tuzatish)»",
          r.status_code == 409 and "Chiqim (tuzatish)" in str(js(r).get("detail")), (r.status_code, js(r)))
    check("D1 material o'zgarmadi (ko'rinadi, qoldiq 7)", mat_hol(m) == oldin, mat_hol(m))
    r2 = C.post(f"/api/inventory/{m}/stock", json={"quantity_change": -7, "reason": "inventarizatsiya — yo'q"})
    r3 = C.delete(f"/api/inventory/{m}")
    check("D2 qoldiq tuzatish bilan 0 qilingach — DELETE 200", r2.status_code == 200 and r3.status_code == 200,
          (r2.status_code, r3.status_code, js(r3)))
    m2 = manfiy_penoplast("AO D3 Penoplast", -2.0, 1.0)
    r4 = C.delete(f"/api/inventory/{m2}")
    check("D3 manfiy qoldiqli material — DELETE 409, sababda «Kirim (tuzatish)»",
          r4.status_code == 409 and "Kirim (tuzatish)" in str(js(r4).get("detail")) and not mat_hol(m2)["yashirin"],
          (r4.status_code, js(r4)))
    m3 = mat("AO D4 Bo'sh", qoldiq=0)
    r5 = C.delete(f"/api/inventory/{m3}")
    check("D4 qoldig'i 0 material — DELETE 200 (avvalgidek)", r5.status_code == 200, (r5.status_code, js(r5)))
    # D5: korxonaning ASOSIY penoplasti (boshqa penoplast bor) qoldig'i bilan — avval tuzilma sababi (400 «asosiy qiling»), qoldiq
    # sababi emas: foydalanuvchi qoldiqni behuda 0 qilib, keyin baribir o'chira olmay qolmasin.
    s = SessionLocal()
    try:
        _asosiy = s.query(Inventory.id).filter(Inventory.company_id == 1, Inventory.is_default_penoplast == True,  # noqa: E712
                                               Inventory.is_deleted.isnot(True)).scalar()
    finally:
        s.close()
    r6 = C.delete(f"/api/inventory/{_asosiy}")
    check("D5 asosiy penoplast (qoldig'i bor, boshqa penoplast bor) — 400 «avval boshqa penoplastni asosiy qiling» (qoldiq "
          "sababidan OLDIN)", r6.status_code == 400 and "asosiy qiling" in str(js(r6).get("detail")) and qoldiq(_asosiy) > 0,
          (r6.status_code, js(r6), _asosiy))


xav(d1)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K — A-O10 b (Kirim qatori to'lov turi) va c (mayda birlik — koeffitsient bilan)")


def k2():
    s = SessionLocal()
    try:
        sp = Supplier(company_id=1, name="AO K2 Ta'minotchi", phone="+998900007602")
        s.add(sp)
        s.commit()
        sid = sp.id
    finally:
        s.close()
    m = mat("AO K2 Sement", qoldiq=0, narx=1000)
    r = C.post("/api/inventory/receipt", json={
        "items": [{"inventory_id": m, "quantity": 10, "price_per_unit": 1000}], "transport_cost": 0, "tushirish_cost": 0,
        "yuklash_cost": 0, "boshqa_cost": 0, "add_to_cost": False, "supplier_id": sid, "document_number": "AO-K2",
        "paid_now": 10000, "notes": "k2"})
    check("K2 fikstura: Kirim hujjati (ta'minotchi, hozir to'langan 10 000) — 200", r.status_code == 200, (r.status_code, js(r)))
    s = SessionLocal()
    try:
        p = s.query(InventoryPurchase).filter(InventoryPurchase.inventory_id == m).order_by(InventoryPurchase.id.desc()).first()
        pid, kredit0 = p.id, bool(p.is_credit)
    finally:
        s.close()
    r1 = C.put(f"/api/inventory/purchases/{pid}", json={"is_credit": not kredit0})
    s = SessionLocal()
    try:
        kredit1 = bool(s.get(InventoryPurchase, pid).is_credit)
    finally:
        s.close()
    check("K2 Kirim hujjati qatorining to'lov turi o'zgartirilsa — 400, o'zgarmadi", r1.status_code == 400 and kredit1 == kredit0,
          (r1.status_code, js(r1), kredit0, kredit1))
    r2 = C.put(f"/api/inventory/purchases/{pid}", json={"is_credit": kredit0})
    check("K2b o'sha qiymat (o'zgarmaydi) — 200", r2.status_code == 200, (r2.status_code, js(r2)))
    r3 = C.put(f"/api/inventory/purchases/{pid}", json={"quantity": 10, "price_per_unit": 1100})
    check("K2c miqdor / narx tahriri — avvalgidek 200", r3.status_code == 200, (r3.status_code, js(r3)))


xav(k2)


def k3():
    r = C.post("/api/inventory", json={"item_name": "AO K3 Gips qop", "unit": "qop", "base_unit": "g"})
    check("K3 mayda birlik «g» koeffitsientsiz — 400", r.status_code == 400 and "koeffitsient" in str(js(r)).lower(),
          (r.status_code, js(r)))
    r = C.post("/api/inventory", json={"item_name": "AO K3 Gips qop", "unit": "qop", "base_unit": "g", "conversion_factor": 25000})
    mid = js(r).get("id")
    check("K3b koeffitsient bilan (1 qop = 25 000 g) — 200", r.status_code == 200 and mid, (r.status_code, js(r)))
    if mid:
        r2 = C.put(f"/api/inventory/{mid}", json={"conversion_factor": None})
        check("K3c koeffitsient o'chirilib mayda birlik qolsa — 400, o'zgarmadi",
              r2.status_code == 400 and mat_hol(mid)["factor"] == 25000, (r2.status_code, js(r2), mat_hol(mid)))
    m = mat("AO K3d Oddiy", unit="kg")
    r3 = C.put(f"/api/inventory/{m}", json={"base_unit": "g"})
    check("K3d oddiy materialga koeffitsientsiz mayda birlik — 400", r3.status_code == 400 and mat_hol(m)["base_unit"] is None,
          (r3.status_code, js(r3), mat_hol(m)))
    r4 = C.post("/api/inventory", json={"item_name": "AO K3e Kg", "unit": "kg", "base_unit": "kg"})
    check("K3e mayda birlik = ombor birligi (koeffitsientsiz) — 200", r4.status_code == 200, (r4.status_code, js(r4)))
    m5 = mat("AO K3f Eski", unit="qop")
    s = SessionLocal()
    try:
        x = s.get(Inventory, m5)
        x.base_unit = "g"                    # eski yozuv: koeffitsientsiz mayda birlik
        s.commit()
    finally:
        s.close()
    r5 = C.put(f"/api/inventory/{m5}", json={"min_stock": 3})
    check("K3f eski (koeffitsientsiz) materialning boshqa tahriri (minimal qoldiq) — 200 (birlik tekshiruvi faqat birlik "
          "o'zgarganda)", r5.status_code == 200 and mat_hol(m5)["min"] == 3, (r5.status_code, js(r5)))


xav(k3)


def k4():
    import production_models as pm
    m = mat("AO K4 Eski qop", unit="qop")
    s = SessionLocal()
    try:
        x = s.get(Inventory, m)
        x.base_unit = "g"                    # eski yozuv: koeffitsientsiz mayda birlik (bazada qolgan)
        x.conversion_factor = None
        s.commit()
        bi = pm.BOMItem(company_id=1, inventory_id=m, quantity=1)
        bi.inventory = s.get(Inventory, m)
        u = bi.unit
    finally:
        s.close()
    check("K4 koeffitsientsiz eski material — retsept qatori birligi ombor birligi («qop»; hisob bilan bir xil)", u == "qop", u)


xav(k4)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("X — umumiy")
s = SessionLocal()
try:
    _hamma = [i for (i,) in s.query(Inventory.id).filter(Inventory.company_id == 1).all()]
finally:
    s.close()
inv_tekshir("INV-HAMMA (korxona 1, yashirinlar ham)", _hamma)
check("X1 butun yurishda 5xx javob yo'q", not SERVER_500, SERVER_500[:5])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
