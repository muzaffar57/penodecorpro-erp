#!/usr/bin/env python3
"""
test_taminotchisiz_xarid.py — kech100 darvozasi (2026-09-27, 109-band).

O'LCHANGAN (`work/probe109.py`, asl = zip 93, SQ = PG): `POST /api/inventory/{id}/purchase` —
  • ta'minotchisiz xarid `paid_now` < jami bo'lsa EGASIZ NASIYA (`is_credit` True): oylik xarid hisobotida +10 000,
    kassada 0, qarzda 0; to'langan qismi (5 000) hech qayerga yozilmasdi;
  • ta'minotchi + boshlang'ich ombor — ta'minotchiga QARZ +10 000;
  • `PUT /api/inventory/purchases/{id}` ta'minotchisiz naqd xaridni `is_credit=true` qilsa kassadan 10 000 yo'qolardi.
NAZORAT: Ombor Kirim hujjati (`POST /api/inventory/receipt`) — `is_credit = not opening and supplier`: ta'minotchisiz — naqd,
boshlang'ich ombor — qarz yo'q.

YECHIM: xarid yo'li kirim hujjati qoidasi bilan — ta'minotchisiz doim NAQD (to'liq summa kassadan), boshlang'ich ombor —
xarid emas (kassa ham, qarz ham yo'q; `paid_now` > 0 — 400), ta'minotchili — o'zgarmagan. Tahrirda nasiya faqat
ta'minotchili, boshlang'ich ombor bo'lmagan xaridga.

Bo'limlar: A — ta'minotchisiz / boshlang'ich ombor; B — ta'minotchili (o'zgarmagan); C — kirim hujjati bilan AYNAN (NAZORAT
yo'li); D — tahrir; E — eski egasiz nasiya yozuvi (tuzatish yo'li); X — 5xx; S — statik.

Ishlatish:
    python3 tools/test_taminotchisiz_xarid.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_taminotchisiz_xarid.py
"""
import os
import sys
import inspect
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "taminotchisiz_xarid_test"
_T = tempfile.mkdtemp(prefix="taminotchisiz_xarid_")
_DB = os.path.join(_T, "taminotchisiz_xarid_test.db")

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

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
    import crud                                    # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from models import UserRole, Inventory, InventoryPurchase, SupplierPayment, TransportExpense   # noqa: E402
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


def taxminan(a, b, eps=0.005):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


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
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TX_admin", "Parol123!", UserRole.ADMIN, "TX Admin", company_id=1)
_db.commit()
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
if req(C, "post", "/login", data={"username": "TX_admin", "password": "Parol123!"}, follow_redirects=False).status_code != 302:
    print("LOGIN BO'LMADI")
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)
SUP = (js(req(C, "post", "/api/suppliers", json={"name": "TX Ta'minotchi"})) or {}).get("id")
SUP2 = (js(req(C, "post", "/api/suppliers", json={"name": "TX Ta'minotchi 2"})) or {}).get("id")
_n = [0]


def material():
    _n[0] += 1
    s = SessionLocal()
    try:
        m = Inventory(company_id=1, item_name=f"TX Material {_n[0]}", unit="kg", stock_quantity=0, price_per_unit=1000,
                      category="Kimyo")
        s.add(m)
        s.commit()
        return m.id
    finally:
        s.close()


def holat(sup=None):
    s = SessionLocal()
    try:
        k = services.get_cash_balance(s, company_id=1)
        n = datetime.utcnow() + timedelta(hours=5)      # kech105: hisobot oyi — Toshkent devor soati
        return {
            "naqd": float(k["chiqim_xomashyo_naqd"]),
            "taminotchiga": float(k["chiqim_yetkazib_beruvchi"]),
            "balans": float(k["balance"]),
            "qarz": {sid: round(float(crud.get_supplier_debt(s, sid, company_id=1)["debt"]), 2) for sid in (SUP, SUP2)},
            "oylik": float(services.get_purchase_stats_for_period(s, n.year, n.month, company_id=1)["total_amount"]),
            "xarid_soni": s.query(InventoryPurchase).count(),
            "stp_soni": s.query(SupplierPayment).count(),
            "transport": s.query(TransportExpense).count(),
        }
    finally:
        s.close()


def ombor(mid):
    s = SessionLocal()
    try:
        return float(s.get(Inventory, mid).stock_quantity)
    finally:
        s.close()


def oxirgi_xarid(mid):
    s = SessionLocal()
    try:
        p = s.query(InventoryPurchase).filter(InventoryPurchase.inventory_id == mid).order_by(InventoryPurchase.id.desc()).first()
        return None if p is None else {"id": p.id, "is_credit": bool(p.is_credit), "supplier_id": p.supplier_id,
                                       "opening": bool(p.is_opening_stock), "jami": float(p.total_amount)}
    finally:
        s.close()


def farq(a, b):
    return {"naqd": round(b["naqd"] - a["naqd"], 2), "taminotchiga": round(b["taminotchiga"] - a["taminotchiga"], 2),
            "qarz": {k: round(b["qarz"][k] - a["qarz"][k], 2) for k in a["qarz"]}, "oylik": round(b["oylik"] - a["oylik"], 2),
            "xarid": b["xarid_soni"] - a["xarid_soni"], "stp": b["stp_soni"] - a["stp_soni"], "transport": b["transport"] - a["transport"]}


def xarid(mid, **kw):
    tana = {"quantity": 10, "price_per_unit": 1000}
    tana.update(kw)
    a = holat()
    r = req(C, "post", f"/api/inventory/{mid}/purchase", json=tana)
    b = holat()
    return r, farq(a, b)


NOL_QARZ = {SUP: 0.0, SUP2: 0.0}

section("A. Ta'minotchisiz / boshlang'ich ombor — nasiya YO'Q")
m1 = material()
r, f = xarid(m1)
j = js(r) or {}
x = oxirgi_xarid(m1)
check("A1 ta'minotchisiz, paid_now yo'q: 200, NAQD (is_credit False), javob paid_now = jami, debt_remains 0",
      r.status_code == 200 and x and x["is_credit"] is False and taxminan(j.get("paid_now"), 10_000)
      and taxminan(j.get("debt_remains"), 0), (r.status_code, j, x))
check("A1 kassa (xomashyo naqd) +10 000, qarz yo'q, oylik xarid +10 000, ombor +10",
      f["naqd"] == 10_000 and f["qarz"] == NOL_QARZ and f["oylik"] == 10_000 and f["stp"] == 0 and ombor(m1) == 10, (f, ombor(m1)))
m2 = material()
r, f = xarid(m2, paid_now=5_000)
j = js(r) or {}
check("A2 ta'minotchisiz, paid_now 5 000 (yarmi): NAQD — kassa to'liq +10 000 (to'lov YO'QOLMAYDI), qarz yo'q",
      r.status_code == 200 and (oxirgi_xarid(m2) or {}).get("is_credit") is False and f["naqd"] == 10_000
      and f["qarz"] == NOL_QARZ and taxminan(j.get("paid_now"), 10_000) and taxminan(j.get("debt_remains"), 0), (r.status_code, j, f))
m3 = material()
r, f = xarid(m3, paid_now=10_000)
check("A3 ta'minotchisiz, to'liq to'langan (NAZORAT — asl ham shunday): naqd +10 000",
      r.status_code == 200 and (oxirgi_xarid(m3) or {}).get("is_credit") is False and f["naqd"] == 10_000, (r.status_code, f))
m4 = material()
r, f = xarid(m4, quantity=3, price_per_unit=1000.125)
x = oxirgi_xarid(m4) or {}
# kassa butun so'mga yaxlitlab ko'rsatadi — delta = round(jami); javob paid_now — yozuv jamisi AYNAN (tiyin bilan)
check("A4 ta'minotchisiz tiyinli (3 × 1000.125 → jami tiyinli): javob paid_now = yozuv jamisi, kassa +round(jami)",
      r.status_code == 200 and x.get("is_credit") is False and abs(float(x.get("jami") or 0) - round(float(x.get("jami") or 0))) > 0.001
      and f["naqd"] == round(float(x.get("jami") or 0)) and taxminan((js(r) or {}).get("paid_now"), x.get("jami"))
      and taxminan((js(r) or {}).get("purchase_total"), x.get("jami")), (r.status_code, f, x, js(r)))
m5 = material()
r, f = xarid(m5, supplier_id=SUP, is_opening_stock=True)
j = js(r) or {}
check("A5 ta'minotchi + boshlang'ich ombor (paid 0): 200, nasiya YO'Q, ta'minotchi qarzi O'ZGARMADI (asl +10 000), kassa 0, oylik 0",
      r.status_code == 200 and (oxirgi_xarid(m5) or {}).get("is_credit") is False and f["qarz"] == NOL_QARZ
      and f["naqd"] == 0 and f["oylik"] == 0 and ombor(m5) == 10 and taxminan(j.get("paid_now"), 0)
      and taxminan(j.get("debt_remains"), 0), (r.status_code, j, f))
m6 = material()
r, f = xarid(m6, is_opening_stock=True)
check("A6 ta'minotchisiz boshlang'ich ombor: nasiya belgisi YO'Q, kassa / qarz / oylik 0, ombor +10",
      r.status_code == 200 and (oxirgi_xarid(m6) or {}).get("is_credit") is False and f["naqd"] == 0
      and f["qarz"] == NOL_QARZ and f["oylik"] == 0 and ombor(m6) == 10, (r.status_code, f))
m7 = material()
r, f = xarid(m7, supplier_id=SUP, is_opening_stock=True, paid_now=4_000, transport_payer="self", transport_cost=500)
check("A7 boshlang'ich ombor + paid_now 4 000: 400 (to'lov jim tashlanmaydi), HECH NARSA yozilmadi (xarid, ombor, to'lov, transport)",
      r.status_code == 400 and "Boshlang'ich" in str((js(r) or {}).get("detail")) and f["xarid"] == 0 and f["stp"] == 0
      and f["transport"] == 0 and f["naqd"] == 0 and ombor(m7) == 0, (r.status_code, js(r), f))
r, f = xarid(m7, is_opening_stock=True, paid_now=1)
check("A8 ta'minotchisiz boshlang'ich ombor + paid_now 1: 400, hech narsa yozilmadi",
      r.status_code == 400 and f["xarid"] == 0 and ombor(m7) == 0, (r.status_code, f))
m9 = material()
r, f = xarid(m9, transport_payer="self", transport_cost=700)
check("A9 ta'minotchisiz + transport \"o'z hisobimdan\": xarid naqd, transport xarajati yozildi (o'zgarmagan)",
      r.status_code == 200 and f["naqd"] == 10_000 and f["transport"] == 1, (r.status_code, f))

section("B. Ta'minotchili xarid — O'ZGARMAGAN")
b1 = material()
r, f = xarid(b1, supplier_id=SUP)
j = js(r) or {}
check("B1 ta'minotchi, paid 0: NASIYA, qarz +10 000, kassa 0, ta'minotchi to'lovi yo'q",
      r.status_code == 200 and (oxirgi_xarid(b1) or {}).get("is_credit") is True and f["qarz"][SUP] == 10_000
      and f["naqd"] == 0 and f["stp"] == 0 and taxminan(j.get("debt_remains"), 10_000), (r.status_code, j, f))
b2 = material()
r, f = xarid(b2, supplier_id=SUP, paid_now=3_000)
j = js(r) or {}
check("B2 ta'minotchi, paid 3 000: nasiya, ta'minotchi to'lovi 3 000, qarz +7 000, kassa ta'minotchiga +3 000",
      r.status_code == 200 and (oxirgi_xarid(b2) or {}).get("is_credit") is True and f["stp"] == 1 and f["qarz"][SUP] == 7_000
      and f["taminotchiga"] == 3_000 and f["naqd"] == 0 and taxminan(j.get("paid_now"), 3_000)
      and taxminan(j.get("debt_remains"), 7_000), (r.status_code, j, f))
b3 = material()
r, f = xarid(b3, supplier_id=SUP, paid_now=10_000)
check("B3 ta'minotchi, to'liq to'langan: NAQD xarid, qarz 0, to'lov yozuvi yo'q, kassa naqd +10 000",
      r.status_code == 200 and (oxirgi_xarid(b3) or {}).get("is_credit") is False and f["qarz"][SUP] == 0
      and f["stp"] == 0 and f["naqd"] == 10_000, (r.status_code, f))
b4 = material()
r, f = xarid(b4, supplier_id=SUP, paid_now=25_000)
check("B4 ta'minotchi, paid_now > jami: javob paid_now = jami (ortiqcha to'lanmaydi), naqd +10 000",
      r.status_code == 200 and taxminan((js(r) or {}).get("paid_now"), 10_000) and f["naqd"] == 10_000 and f["stp"] == 0,
      (r.status_code, js(r), f))

section("C. Kirim hujjati bilan AYNAN (NAZORAT yo'li)")


def kirim(mid, supplier_id=None, opening=False, paid_now=0):
    tana = {"items": [{"inventory_id": mid, "quantity": 10, "price_per_unit": 1000, "is_opening_stock": opening}],
            "paid_now": paid_now}
    if supplier_id:
        tana["supplier_id"] = supplier_id
    a = holat()
    r = req(C, "post", "/api/inventory/receipt", json=tana)
    b = holat()
    return r, farq(a, b)


for nom, kw in (("ta'minotchisiz", {}), ("ta'minotchi + boshlang'ich", {"supplier_id": SUP2, "opening": True}),
                ("ta'minotchisiz boshlang'ich", {"opening": True}), ("ta'minotchi, paid 0", {"supplier_id": SUP2})):
    ma, mb = material(), material()
    rk, fk = kirim(ma, **kw)
    xk = oxirgi_xarid(ma) or {}
    rx, fx = xarid(mb, **({"supplier_id": kw["supplier_id"]} if kw.get("supplier_id") else {}),
                   **({"is_opening_stock": True} if kw.get("opening") else {}))
    xx = oxirgi_xarid(mb) or {}
    _kal = ("naqd", "taminotchiga", "qarz", "oylik", "stp")
    check(f"C {nom}: xarid yo'li = kirim hujjati (nasiya belgisi, kassa, qarz, oylik xarid, to'lov)",
          rk.status_code == 200 and rx.status_code == 200 and xk.get("is_credit") == xx.get("is_credit")
          and all(fk[k] == fx[k] for k in _kal), (rk.status_code, rx.status_code, xk, xx, fk, fx))

section("D. Tahrir — nasiya faqat ta'minotchili, boshlang'ich ombor bo'lmagan xaridga")


def tahrir(mid, tana):
    pid = (oxirgi_xarid(mid) or {}).get("id")
    a = holat()
    r = req(C, "put", f"/api/inventory/purchases/{pid}", json=tana)
    b = holat()
    return r, farq(a, b)


r, f = tahrir(m1, {"is_credit": True})
check("D1 ta'minotchisiz naqd → is_credit true: 400, o'zgarmadi (asl — kassadan 10 000 yo'qolardi)",
      r.status_code == 400 and "nasiya" in str((js(r) or {}).get("detail")) and (oxirgi_xarid(m1) or {}).get("is_credit") is False
      and f["naqd"] == 0, (r.status_code, js(r), f))
r, f = tahrir(m5, {"is_credit": True})
check("D2 boshlang'ich ombor (ta'minotchili) → is_credit true: 400, qarz o'zgarmadi",
      r.status_code == 400 and (oxirgi_xarid(m5) or {}).get("is_credit") is False and f["qarz"] == NOL_QARZ, (r.status_code, f))
r, f = tahrir(m1, {"is_credit": True, "quantity": 20})
check("D3 nasiya + miqdor bitta tanada: 400, miqdor ham YOZILMADI (ombor 10)",
      r.status_code == 400 and ombor(m1) == 10 and f["naqd"] == 0, (r.status_code, ombor(m1), f))
r, f = tahrir(b3, {"is_credit": True})
check("D4 ta'minotchili naqd → is_credit true: 200, qarz +10 000, kassa naqd −10 000 (o'zgarmagan xulq)",
      r.status_code == 200 and f["qarz"][SUP] == 10_000 and f["naqd"] == -10_000, (r.status_code, f))
r, f = tahrir(b3, {"is_credit": False})
check("D5 va qaytib false: 200, qarz −10 000, kassa +10 000",
      r.status_code == 200 and f["qarz"][SUP] == -10_000 and f["naqd"] == 10_000, (r.status_code, f))
r, f = tahrir(m2, {"is_credit": False, "notes": "tuzatildi"})
check("D6 ta'minotchisiz → is_credit false (o'zgarishsiz) + izoh: 200", r.status_code == 200 and f["naqd"] == 0, (r.status_code, f))
r, f = tahrir(m3, {"quantity": 12})
check("D7 ta'minotchisiz naqd xarid miqdori 10 → 12: 200, kassa +2 000 (tahrir yo'li o'zgarmagan)",
      r.status_code == 200 and f["naqd"] == 2_000 and ombor(m3) == 12, (r.status_code, f, ombor(m3)))

section("E. Eski EGASIZ nasiya yozuvi (zip 94 dan oldin yaratilgan) — tuzatish yo'li")
me = material()
_s = SessionLocal()
try:
    _p = InventoryPurchase(inventory_id=me, item_name="TX eski", quantity=10, unit="kg", price_per_unit=1000,
                           total_amount=10_000, supplier_id=None, is_credit=True, purchased_by="eski")
    _s.add(_p)
    _s.commit()
except Exception as _e:                    # noqa: BLE001
    _s.rollback()
    print("  (E tayyorlash xatosi:", _e, ")")
finally:
    _s.close()
xe = oxirgi_xarid(me) or {}
check("E0 eski egasiz nasiya yozuvi bor (kassada yo'q)", xe.get("is_credit") is True and xe.get("supplier_id") is None, xe)
r, f = tahrir(me, {"notes": "izoh"})
check("E1 faqat izoh tahriri (is_credit tanada yo'q): 200 — eski yozuvni tahrirlash bloklanmaydi", r.status_code == 200, (r.status_code, js(r)))
r, f = tahrir(me, {"is_credit": False})
check("E2 is_credit false: 200 — kassaga +10 000 tushdi (egasiz nasiya tuzatildi)",
      r.status_code == 200 and f["naqd"] == 10_000 and (oxirgi_xarid(me) or {}).get("is_credit") is False, (r.status_code, f))

section("X. Server xatosi (5xx) yo'q")
check("X1 test davomida 5xx yo'q", not XATOLAR_5XX, XATOLAR_5XX[:5])

section("S. Statik")
_ap = manba(main, "api_purchase_stock")
check("S1 api_purchase_stock: boshlang'ich ombor → ta'minotchisiz → ta'minotchili qoidasi tranzaksiyadan OLDIN",
      tartibda(_ap, "if data.is_opening_stock:", "paid_now, debt_remains, is_credit = 0.0, 0.0, False",
               "elif not data.supplier_id:", "paid_now, debt_remains, is_credit = total_amount, 0.0, False",
               "is_credit = debt_remains > 0.01", "with crud.bitta_tranzaksiya(db):"), "")
check("S2 api_purchase_stock: tanadagi is_credit ishlatilmaydi", "data.is_credit" not in _ap, "")
_up = manba(crud, "update_purchase")
check("S3 update_purchase: nasiya to'sig'i yozuvdan OLDIN (ta'minotchisiz yoki boshlang'ich)",
      tartibda(_up, "p = _purchase_of_company(", "if toza.get(\"is_credit\") is True and (not p.supplier_id or p.is_opening_stock):",
               "raise ValueError(", "eski_qty = float(p.quantity or 0)", "p.is_credit = toza[\"is_credit\"]"), "")

print("\n" + "=" * 66)
print(f"REJIM: {'PostgreSQL' if PG_URL else 'SQLite'}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
if PG_URL:
    try:
        engine.dispose()
        _adm2 = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm2.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm2.dispose()
    except Exception:                      # noqa: BLE001
        pass
sys.exit(1 if FAIL else 0)
