#!/usr/bin/env python3
"""test_transport_foyda.py — kech87 darvozasi (2026-09-26, 104-band).

FOYDALANUVCHI QARORI (kech87): korxona to'lagan transport — TO'LANGAN OYNING XARAJATI, sof foydadan ayriladi:
  (1) kirish transporti — xarid oynasidagi "o'z hisobimdan" (`transport_payer: self`) va alohida "Kirish
      transporti" (`/api/transport-expenses`) — `TransportExpense.expense_date` oyida;
  (2) yetkazish transporti — korxona hisobidan (`company` — to'liq, `split` — yarmi) — `Delivery.delivered_at`
      oyida.
TEXNIK (Claude): kirim hujjatida "tannarxga qo'shish" (`add_to_cost`) bilan yozilgan qo'shimcha xarajat sof
foydadan IKKINCHI marta ayrilmaydi (xomashyo tannarxi orqali ayriladi) — `ExpenseTransaction.source =
models.KIRIM_TANNARX_MANBA`; eski yozuvlar migratsiyada (`main._migrate_kirim_tannarx_manba`) belgilanadi.

ASL kodda (zip 80) O'LCHANGAN (probe104, SQLite = PG): (1) va (2) sof foydaga UMUMAN kirmasdi; "tannarxga
qo'shish" bilan 500 so'mlik transport sof foydani 1 000 ga kamaytirardi.

Bo'limlar: A kirish transporti · B yetkazish transporti · C kirim hujjati (bir marta) · D oy chegarasi ·
K boshqa korxona · M migratsiya · U interfeys (statik) · H kod tartibi (statik).
Ishga tushirish (repo ildizidan):
    python3 tools/test_transport_foyda.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_transport_foyda.py
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
PG_BAZA = "transport_foyda_test"
_T = tempfile.mkdtemp(prefix="transport_foyda_")
_DB = os.path.join(_T, "transport_foyda_test.db")

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
    import crud                                    # noqa: E402
    import services                                # noqa: E402
    import models                                  # noqa: E402

from database import SessionLocal                  # noqa: E402
from sqlalchemy import text as _sqtext            # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, OrderItem, ExpenseTransaction, InventoryReceipt, TransportExpense, Delivery,
)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

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
        self.headers = {}

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


def tartibda(src, *qismlar):
    """Qismlar src ichida AYNAN shu tartibda uchraydimi (find — topilmasa False)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def teng(a, b, tol=0.005):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:                      # noqa: BLE001
        return False


NOW = datetime.now()
Y, M = NOW.year, NOW.month
BUGUN = NOW.date().isoformat()
_OLDINGI = NOW.replace(day=1) - timedelta(days=1)
OY, OM = _OLDINGI.year, _OLDINGI.month
_OLDINGI_SANA = datetime(OY, OM, 15, 12, 0, 0)

_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TF87_admin", "Parol123!", UserRole.ADMIN, "TF87 Admin", company_id=1)
if not _db.get(Company, 2):
    _db.add(Company(id=2, name="TF87 Korxona B"))
    _db.commit()


def material(nom, peno=True, narx=1000.0, qoldiq=0.0, cid=1):
    it = Inventory(company_id=cid, item_name=nom, unit=("blok" if peno else "kg"), stock_quantity=qoldiq,
                   price_per_unit=narx, volume_per_unit=(1.0 if peno else None), is_penoplast=peno,
                   category=("Penoplast" if peno else "Akril"))
    _db.add(it)
    _db.commit()
    return it.id


_pr = Project(company_id=1, client_name="TF87 mijoz", project_name="TF87 loyiha", total_budget=0, total_paid=0)
_db.add(_pr)
_db.commit()
PRJ = _pr.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = C.post("/login", data={"username": "TF87_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _lr.status_code in (200, 302, 303), _lr.status_code)


def hisobot(y=None, m=None):
    r = req(C, "get", "/api/finance/report", params={"year": y or Y, "month": m or M})
    d = js(r)
    return d if isinstance(d, dict) else {}


def sof(y=None, m=None):
    return hisobot(y, m).get("sof_foyda")


def tarix_sof(y=None, m=None):
    d = js(req(C, "get", "/api/finance/history"))
    if not isinstance(d, list):
        return None
    x = next((h for h in d if isinstance(h, dict) and h.get("year") == (y or Y) and h.get("month") == (m or M)), None)
    return x.get("sof_foyda") if x else None


def kun_transport():
    d = js(req(C, "get", "/api/finance/daily", params={"target_date": BUGUN}))
    try:
        return float(d["expenses"]["transport"]["total"])
    except Exception:                      # noqa: BLE001
        return None


def narx(mid):
    s = SessionLocal()
    try:
        x = s.get(Inventory, mid)
        return float(x.price_per_unit) if x else None
    finally:
        s.close()


def ayir(a, b):
    try:
        return float(b) - float(a)
    except Exception:                      # noqa: BLE001
        return None


_n = [0]


def xarid(mid, q, bir_narx, payer="none", tr=0):
    return req(C, "post", f"/api/inventory/{mid}/purchase",
               json={"quantity": q, "price_per_unit": bir_narx, "transport_payer": payer, "transport_cost": tr})


def kirim(mid, q, bir_narx, tr, add, turi=None, boshlangich=False):
    _n[0] += 1
    return req(C, "post", "/api/inventory/receipt",
               json={"items": [{"inventory_id": mid, "quantity": q, "price_per_unit": bir_narx,
                                "is_opening_stock": boshlangich}],
                     "transport_cost": tr, "add_to_cost": add, "production_type": turi,
                     "document_number": f"TF87-{_n[0]}", "notes": f"TF87 kirim {_n[0]}"})


def tx_manba(receipt_id):
    s = SessionLocal()
    try:
        return sorted(str(t.source) for t in s.query(ExpenseTransaction).filter(
            ExpenseTransaction.notes.like(f"%Kirim #{receipt_id}%")).all())
    finally:
        s.close()


def buyurtma(mid, uzunlik, narx_=100_000, nom=None):
    _n[0] += 1
    r = req(C, "post", "/api/orders?confirm_shortage=true", json={
        "project_id": PRJ, "order_type": "product",
        "items": [{"name": nom or f"TF87 profil {_n[0]}", "category": "profil", "width": 50, "thickness": 50,
                   "length": uzunlik, "quantity": 1, "unit_price": narx_, "is_coated": False, "penoplast_id": mid}]})
    d = js(r) or {}
    return d.get("id") if isinstance(d, dict) else None


def tayyor(oid):
    return req(C, "post", f"/api/orders/{oid}/ready")


def element(oid):
    s = SessionLocal()
    try:
        x = s.query(OrderItem.id).filter(OrderItem.order_id == oid).first()
        return x[0] if x else None
    finally:
        s.close()


def yuk(oid, iid, payer, summa):
    _n[0] += 1
    r = req(C, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": iid, "quantity": 0.3}],
                                                "notes": f"TF87 yuk {_n[0]}", "transport_cost": summa,
                                                "transport_payer": payer})
    d = js(r) or {}
    return r.status_code, (d.get("delivery_id") if isinstance(d, dict) else None)


# ═══════════════════════════════════════════════════════════════════════════
section("A — kirish transporti (xarid oynasi, alohida yozuv) — to'langan oyning xarajati")
M_A0, M_A1, M_A2, M_A3 = (material("TF87 A0", False), material("TF87 A1", False), material("TF87 A2", False),
                          material("TF87 A3", False))
s0, k0 = sof(), kun_transport()
r = xarid(M_A0, 10, 1000.0)
s1 = sof()
check("A0 nazorat: transportsiz xarid — sof foyda O'ZGARMAYDI", r.status_code == 200 and teng(ayir(s0, s1), 0),
      [r.status_code, s0, s1])
h0 = hisobot()
r = xarid(M_A1, 10, 1001.0, "self", 333.33)
h1 = hisobot()
check("A1 \"o'z hisobimdan\" 333.33 — sof foyda AYNAN −333.33 (tiyingacha)",
      r.status_code == 200 and teng(ayir(h0.get("sof_foyda"), h1.get("sof_foyda")), -333.33),
      [r.status_code, ayir(h0.get("sof_foyda"), h1.get("sof_foyda"))])
check("A2 jami_xarajat +333.33, transport_xarajat_kirish +333.33, transport_xarajat +333.33",
      teng(ayir(h0.get("jami_xarajat"), h1.get("jami_xarajat")), 333.33)
      and teng(ayir(h0.get("transport_xarajat_kirish"), h1.get("transport_xarajat_kirish")), 333.33)
      and teng(ayir(h0.get("transport_xarajat"), h1.get("transport_xarajat")), 333.33),
      [h1.get("jami_xarajat"), h1.get("transport_xarajat_kirish"), h1.get("transport_xarajat")])
check("A3 xomashyo narxi — faqat xarid narxi (transport tannarxga QO'SHILMAYDI)", teng(narx(M_A1), 1001.0), narx(M_A1))
check("A4 tarix sof foydasi == hisobot sof foydasi", teng(tarix_sof(), h1.get("sof_foyda")), [tarix_sof(), h1.get("sof_foyda")])
k1 = kun_transport()
check("A5 kunlik transport xarajati +333 (kirish transporti kunlikka ham kiradi)", teng(ayir(k0, k1), 333, 1.0), [k0, k1])
s2 = sof()
r = xarid(M_A2, 10, 1002.0, "supplier", 500)
s3 = sof()
check("A6 nazorat: ta'minotchi to'laydigan transport — sof foyda O'ZGARMAYDI", r.status_code == 200 and teng(ayir(s2, s3), 0),
      [r.status_code, s2, s3])
s4, k4 = sof(), kun_transport()
r = req(C, "post", "/api/transport-expenses", json={"amount": 700.25, "materials_note": "TF87", "notes": "TF87 alohida"})
te_id = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
s5 = sof()
check("A7 alohida \"Kirish transporti\" 700.25 — sof foyda AYNAN −700.25", r.status_code == 200 and teng(ayir(s4, s5), -700.25),
      [r.status_code, ayir(s4, s5)])
check("A8 kunlik transport +700", teng(ayir(k4, kun_transport()), 700, 1.0), [k4, kun_transport()])
r = req(C, "delete", f"/api/transport-expenses/{te_id}")
s6 = sof()
check("A9 transport yozuvi o'chirilsa — sof foyda AYNAN tiklanadi", r.status_code == 200 and teng(s6, s4), [r.status_code, s4, s6])
s7 = sof()
r = xarid(M_A3, 10, 1003.0, "none", 900)
check("A10 nazorat: transport_payer \"none\" (summa bilan ham) — sof foyda O'ZGARMAYDI",
      r.status_code == 200 and teng(ayir(s7, sof()), 0), [r.status_code, s7, sof()])

# ═══════════════════════════════════════════════════════════════════════════
section("B — yetkazish transporti (korxona hisobidan) — to'langan oyning xarajati")
M_B = material("TF87 B peno", True, 1000.0, 1000.0)
OB = buyurtma(M_B, 8, 50_000)
IB = element(OB)
check("B0 yuk buyurtmasi yaratildi", OB and IB, [OB, IB])
h0 = hisobot()
kod, d_company = yuk(OB, IB, "company", 300.5)
h1 = hisobot()
check("B1 \"company\" 300.5 — sof foyda AYNAN −300.5", kod == 200 and teng(ayir(h0.get("sof_foyda"), h1.get("sof_foyda")), -300.5),
      [kod, ayir(h0.get("sof_foyda"), h1.get("sof_foyda"))])
check("B2 transport_xarajat_yetkazish +300.5, transport_xarajat +300.5",
      teng(ayir(h0.get("transport_xarajat_yetkazish"), h1.get("transport_xarajat_yetkazish")), 300.5)
      and teng(ayir(h0.get("transport_xarajat"), h1.get("transport_xarajat")), 300.5),
      [h1.get("transport_xarajat_yetkazish"), h1.get("transport_xarajat")])
s0 = sof()
kod, _d = yuk(OB, IB, "client", 400)
check("B3 \"client\" — sof foyda O'ZGARMAYDI", kod == 200 and teng(ayir(s0, sof()), 0), [kod, s0, sof()])
s1 = sof()
kod, _d = yuk(OB, IB, "split", 601)
check("B4 \"split\" 601 — sof foyda AYNAN −300 (korxona qismi = `Delivery.company_transport_cost` = round(601 / 2))",
      kod == 200 and teng(ayir(s1, sof()), -300),
      [kod, ayir(s1, sof())])
s2 = sof()
kod, _d = yuk(OB, IB, "none", 0)
check("B5 transportsiz yuk — sof foyda O'ZGARMAYDI", kod == 200 and teng(ayir(s2, sof()), 0), [kod, s2, sof()])
s3 = sof()
r = req(C, "delete", f"/api/deliveries/{d_company}")
check("B6 \"company\" yuk o'chirilsa — sof foyda +300.5 (AYNAN tiklanadi)", r.status_code == 200 and teng(ayir(s3, sof()), 300.5),
      [r.status_code, ayir(s3, sof())])
check("B7 tarix sof foydasi == hisobot sof foydasi", teng(tarix_sof(), sof()), [tarix_sof(), sof()])

# ═══════════════════════════════════════════════════════════════════════════
section("C — kirim hujjati: qo'shimcha xarajat sof foydadan BIR MARTA")
M_C3, M_C4 = material("TF87 C3 peno", True), material("TF87 C4 peno", True)
s0 = sof()
r = kirim(M_C3, 10, 1000.0, 500, False, "penoplast")
rid3 = (js(r) or {}).get("receipt_id") if isinstance(js(r), dict) else None
s1 = sof()
check("C1 tannarxga qo'shilmasa — sof foyda darhol −500 (oddiy xarajat)", r.status_code == 200 and teng(ayir(s0, s1), -500),
      [r.status_code, ayir(s0, s1)])
check("C2 ... Moliya yozuvi manbasi \"inventory_receipt\", narx o'zgarmagan", tx_manba(rid3) == ["inventory_receipt"]
      and teng(narx(M_C3), 1000.0), [tx_manba(rid3), narx(M_C3)])
tb0 = ((hisobot().get("turlar_boyicha") or {}).get("penoplast") or {}).get("qoshimcha_xarajat")
r = kirim(M_C4, 10, 1000.0, 500, True, "penoplast")
rid4 = (js(r) or {}).get("receipt_id") if isinstance(js(r), dict) else None
s2 = sof()
check("C3 tannarxga qo'shilsa — sof foyda darhol O'ZGARMAYDI (ikki marta EMAS)", r.status_code == 200 and teng(ayir(s1, s2), 0),
      [r.status_code, ayir(s1, s2)])
check("C4 ... narx +50 / blok (tannarxda), Moliya yozuvi manbasi KIRIM_TANNARX_MANBA",
      teng(narx(M_C4), 1050.0) and tx_manba(rid4) == [getattr(models, "KIRIM_TANNARX_MANBA", "?")],
      [narx(M_C4), tx_manba(rid4)])
tb1 = ((hisobot().get("turlar_boyicha") or {}).get("penoplast") or {}).get("qoshimcha_xarajat")
check("C5 turlar bo'linishi (penoplast qo'shimcha xarajati) — tannarxdagi xarajat qayta qo'shilmaydi", teng(ayir(tb0, tb1), 0),
      [tb0, tb1])
check("C6 ... tannarxga qo'shilmagan kirim xarajati bo'linishda BOR (nazorat)", teng(tb0, 500) or (tb0 or 0) >= 500, tb0)
qh = hisobot().get("qoshimcha_xarajatlar") or {}
check("C7 qo'shimcha xarajatlar ro'yxatida transport_kirim = 500 (faqat tannarxsiz hujjat)", teng(qh.get("transport_kirim"), 500), qh)
o3, o4 = buyurtma(M_C3, 80), buyurtma(M_C4, 80)
s3 = sof()
r3 = tayyor(o3)
s4 = sof()
r4 = tayyor(o4)
s5 = sof()
d3, d4 = ayir(s3, s4), ayir(s4, s5)
check("C8 ikki egizak buyurtma (10 blokdan) — tannarxli xomashyoda foyda 500 ga kam (xarajat SHU YERDA)",
      r3.status_code == 200 and r4.status_code == 200 and teng(d3 - d4, 500) if (d3 is not None and d4 is not None) else False,
      [r3.status_code, r4.status_code, d3, d4])
check("C9 yakuniy: ikki yo'l ham sof foydani AYNAN bir xil (−500) kamaytirdi — ikki marta hisob YO'Q",
      teng(ayir(s0, s1) + (d3 - 90_000 if d3 is not None else 0), ayir(s1, s2) + (d4 - 90_000 if d4 is not None else 0) + 0)
      and teng(ayir(s0, s1), -500) and teng(ayir(s1, s2) + (d4 - 90_000 if d4 is not None else 0), -500),
      [ayir(s0, s1), ayir(s1, s2), d3, d4])
M_C5 = material("TF87 C5 peno", True)
s6 = sof()
r = kirim(M_C5, 10, 1000.0, 400, True, None, boshlangich=True)
check("C10 nazorat: boshlang'ich ombor kirimi — Moliya yozuvi yo'q, sof foyda O'ZGARMAYDI",
      r.status_code == 200 and teng(ayir(s6, sof()), 0), [r.status_code, ayir(s6, sof())])

# ═══════════════════════════════════════════════════════════════════════════
section("D — oy chegarasi: transport TO'LANGAN oyda")
so0, sj0 = sof(OY, OM), sof()
r = req(C, "post", "/api/transport-expenses", json={"amount": 1234.5, "notes": "TF87 oldingi oy"})
d_id = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
s = SessionLocal()
_te = s.get(TransportExpense, d_id) if d_id else None
if _te is not None:
    _te.expense_date = _OLDINGI_SANA
    s.commit()
s.close()
check("D1 oldingi oy sanasidagi kirish transporti — oldingi oy sof foydasi −1234.5", teng(ayir(so0, sof(OY, OM)), -1234.5),
      [so0, sof(OY, OM)])
check("D2 ... joriy oy sof foydasi O'ZGARMAYDI", teng(sj0, sof()), [sj0, sof()])
so1, sj1 = sof(OY, OM), sof()
kod, dd = yuk(OB, IB, "company", 111)
s = SessionLocal()
_dl = s.get(Delivery, dd) if dd else None
if _dl is not None:
    _dl.delivered_at = _OLDINGI_SANA
    s.commit()
s.close()
check("D3 oldingi oyda yetkazilgan yuk transporti — oldingi oyda −111, joriyda 0",
      teng(ayir(so1, sof(OY, OM)), -111) and teng(sj1, sof()), [ayir(so1, sof(OY, OM)), sj1, sof()])

# ═══════════════════════════════════════════════════════════════════════════
section("K — boshqa korxona transporti bu korxona foydasiga TEGMAYDI")
s0, kk0 = sof(), kun_transport()
s = SessionLocal()
s.add(TransportExpense(company_id=2, amount=5000, notes="TF87 B korxona"))
s.commit()
s.close()
check("K1 B korxonaning kirish transporti — A sof foydasi O'ZGARMAYDI", teng(s0, sof()), [s0, sof()])
_s = SessionLocal()
try:
    _hB = services.get_monthly_report(_s, Y, M, company_id=2)
finally:
    _s.close()
check("K2 ... B korxona hisobotida −5000 (transport_xarajat 5000)", teng(_hB.get("transport_xarajat"), 5000),
      _hB.get("transport_xarajat"))
check("K3 ... A korxonaning KUNLIK transport xarajati ham O'ZGARMAYDI", teng(kk0, kun_transport()), [kk0, kun_transport()])

# ═══════════════════════════════════════════════════════════════════════════
section("M — migratsiya: eski \"tannarxga qo'shish\" kirim xarajatlari belgilanadi (idempotent)")
_mig = getattr(main, "_migrate_kirim_tannarx_manba", None)
check("M0 main._migrate_kirim_tannarx_manba mavjud", callable(_mig))
s = SessionLocal()
_rT = InventoryReceipt(company_id=1, transport_cost=300, add_to_cost=True, notes="TF87 eski T")
_rF = InventoryReceipt(company_id=1, transport_cost=200, add_to_cost=False, notes="TF87 eski F")
_rB = InventoryReceipt(company_id=2, transport_cost=100, add_to_cost=True, notes="TF87 eski B")
s.add_all([_rT, _rF, _rB])
s.commit()
ESKI = {}
for kal, rr, summa, cid in (("T", _rT, 300, 1), ("F", _rF, 200, 1), ("X", _rB, 150, 1)):
    tx = ExpenseTransaction(company_id=cid, date=NOW, category="transport_kirim", amount=summa,
                            notes=f"Transport (kirim) — Kirim #{rr.id}", created_by="TF87", source="inventory_receipt")
    s.add(tx)
    s.commit()
    ESKI[kal] = tx.id
_txN = ExpenseTransaction(company_id=1, date=NOW, category="transport_kirim", amount=50, notes="TF87 izohsiz",
                          created_by="TF87", source="inventory_receipt")
s.add(_txN)
s.commit()
ESKI["N"] = _txN.id
s.close()
s0 = sof()


def manba(tid):
    s = SessionLocal()
    try:
        x = s.get(ExpenseTransaction, tid)
        return x.source if x else None
    finally:
        s.close()


with contextlib.redirect_stdout(_quiet):
    try:
        _mig()
    except Exception as e:             # noqa: BLE001
        print("migratsiya xato", e)
s1 = sof()
check("M1 add_to_cost hujjat xarajati → KIRIM_TANNARX_MANBA", manba(ESKI["T"]) == getattr(models, "KIRIM_TANNARX_MANBA", "?"),
      manba(ESKI["T"]))
check("M2 add_to_cost YO'Q hujjat xarajati — o'zgarmaydi", manba(ESKI["F"]) == "inventory_receipt", manba(ESKI["F"]))
check("M3 BOSHQA korxona hujjatiga ishora qilgan yozuv — o'zgarmaydi", manba(ESKI["X"]) == "inventory_receipt", manba(ESKI["X"]))
check("M4 izohida \"Kirim #N\" yo'q yozuv — o'zgarmaydi", manba(ESKI["N"]) == "inventory_receipt", manba(ESKI["N"]))
check("M5 sof foyda +300 (tannarxdagi eski xarajat endi ikkinchi marta ayrilmaydi)", teng(ayir(s0, s1), 300), [s0, s1])
with contextlib.redirect_stdout(_quiet):
    try:
        _mig()
    except Exception as e:             # noqa: BLE001
        print("migratsiya xato", e)
check("M6 ikkinchi ishga tushirish — hech narsa o'zgarmaydi (idempotent)",
      manba(ESKI["T"]) == getattr(models, "KIRIM_TANNARX_MANBA", "?") and manba(ESKI["F"]) == "inventory_receipt"
      and teng(s1, sof()), [manba(ESKI["T"]), manba(ESKI["F"]), s1, sof()])
s = SessionLocal()
_txNull = ExpenseTransaction(company_id=1, date=NOW, category="kutilmagan", amount=77, notes="TF87 null", created_by="TF87")
s.add(_txNull)
s.commit()
s.execute(_sqtext("UPDATE expense_transactions SET source = NULL WHERE id = :i"), {"i": _txNull.id})
s.commit()
s.close()
s2 = sof()
check("M7 NULL manbali eski xarajat — sof foydadan AYRILADI (or_ bilan, `!=` NULL ni tashlamaydi)",
      teng(ayir(s1, s2), -77), [s1, s2])

# ═══════════════════════════════════════════════════════════════════════════
section("U — interfeys (statik)")
try:
    _fin = open(os.path.join(ROOT, "templates", "finance.html"), encoding="utf-8").read()
except Exception:                          # noqa: BLE001
    _fin = ""
try:
    _dash = open(os.path.join(ROOT, "templates", "dashboard.html"), encoding="utf-8").read()
except Exception:                          # noqa: BLE001
    _dash = ""
check("U1 Moliya: transport qatori (d.transport_xarajat) \"Jami xarajat\" qatoridan OLDIN, tailHtml ichida",
      tartibda(_fin, "if ((d.brak_xarajat||0) > 0)", "if ((d.transport_xarajat||0) > 0)", "tailHtml +=",
               "${fmtFull(d.transport_xarajat||0)}", "<span>Jami xarajat:</span>"))
check("U2 Moliya: manba nomlari — kirim_tannarx va inventory_receipt",
      "kirim_tannarx:'Kirim (tannarxda)'" in _fin and "inventory_receipt:'Kirim hujjati'" in _fin)
check("U3 Bosh sahifa \"Chiqim\": transport ikki marta qo'shilmaydi",
      "const chiqim = (d.jami_xarajat||0)+(d.naqd_xarajat_jami||0)-(d.transport_xarajat||0);" in _dash
      and "const chiqim = (d.jami_xarajat||0)+(d.naqd_xarajat_jami||0);" not in _dash)

# ═══════════════════════════════════════════════════════════════════════════
section("H — kod tartibi (statik)")
try:
    _srcr = inspect.getsource(services.get_monthly_report)
except Exception:                          # noqa: BLE001
    _srcr = ""
try:
    _srct = inspect.getsource(services.get_transport_stats_for_period)
except Exception:                          # noqa: BLE001
    _srct = ""
try:
    _srcd = inspect.getsource(services.get_daily_finance_summary)
except Exception:                          # noqa: BLE001
    _srcd = ""
try:
    _srck = inspect.getsource(crud.create_inventory_receipt)
except Exception:                          # noqa: BLE001
    _srck = ""
try:
    _srcm = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
except Exception:                          # noqa: BLE001
    _srcm = ""
check("H1 hisobot: transport jami_xarajat_eski ICHIDA va sof_foyda_before_emp dan OLDIN (hodim % ham shu foydadan)",
      tartibda(_srcr, "transport_xarajat = transport_xarajat_kirish + transport_xarajat_yetkazish", "jami_xarajat_eski = (",
               "brak_xarajat +", "transport_xarajat", ")", "sof_foyda_before_emp = "))
check("H2 hisobot: YAXLITLANMAGAN qiymatlar (inbound_aniq / outbound_company_aniq)",
      '"inbound_aniq"' in _srcr and '"outbound_company_aniq"' in _srcr
      and '"inbound_aniq": float(inbound_total)' in _srct and '"outbound_company_aniq": float(outbound_company)' in _srct)
check("H3 qo'shimcha xarajatlar: KIRIM_TANNARX_MANBA chiqariladi, NULL saqlanadi (or_)",
      "_or_kt(ExpenseTransaction.source.is_(None), ExpenseTransaction.source != _KTM)" in _srcr)
check("H4 turlar bo'linishi: gips va penoplast ikkalasida _et_foydaga",
      "_ET.production_type == 'gips', _et_foydaga," in _srcr and "_ET.production_type == 'penoplast', _et_foydaga," in _srcr)
check("H5 kunlik: kirish transporti korxona filtri bilan qo'shiladi",
      tartibda(_srcd, "_teq_day = db.query(_func_td.sum(_TE_day.amount))", "_TE_day.company_id == company_id",
               "transport_total += float(_teq_day.scalar() or 0)", "total_expense = "))
check("H6 kirim hujjati: manba sharti extra_share sharti bilan bir xil",
      "_tannarxga = bool(add_to_cost and total_extra > 0 and items_total_value > 0)" in _srck
      and "source=(KIRIM_TANNARX_MANBA if _tannarxga else \"inventory_receipt\")" in _srck)
check("H7 main: migratsiya aniqlangan va chaqirilgan (buyurtma hisoblagichidan keyin)",
      tartibda(_srcm, "\n_migrate_buyurtma_raqam_hisoblagich()\n", "def _migrate_kirim_tannarx_manba():",
               "_IR87.add_to_cost.is_(True)", "_r.company_id != _t.company_id", "\n_migrate_kirim_tannarx_manba()\n"))
check("H8 models: KIRIM_TANNARX_MANBA ustun sig'imiga sig'adi (String(20))",
      isinstance(getattr(models, "KIRIM_TANNARX_MANBA", None), str) and 0 < len(getattr(models, "KIRIM_TANNARX_MANBA", "")) <= 20)

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
sys.exit(1 if FAIL else 0)
