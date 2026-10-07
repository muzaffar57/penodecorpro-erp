#!/usr/bin/env python3
"""
test_top_tm_korxona.py — kech78 darvozasi (2026-09-25, 98-band): Dashboard "Tayyor mahsulotdan eng ko'p
sotilganlar" (`/api/dashboard/top-finished-products`, `services.get_top_finished_products_sold`) KORXONA bilan
cheklanadi — global `TENANT_FILTER` ga tayanmasdan.

O'LCHANGAN (asl kod, `work/probe98.py`, kech78): funksiyada `company_id` yo'q edi, marshrut korxonasiz
chaqirardi — `TENANT_FILTER` o'chiq bo'lsa A korxona admini B ning tayyor mahsulot sotuvini (nomi, summasi)
ko'rardi va aksincha. `TENANT_FILTER=1` da global filtr yashirardi (bitta himoya qatlami).

Bo'limlar: A — HTTP (A va B adminlari faqat o'z ro'yxatini ko'radi, summa aynan); B — funksiya to'g'ridan
(company_id=1 / 2 / None — orqaga moslik); C — qaytarish so'rovi ham korxona bilan cheklanadi (B korxonasi
yozuvi A ning buyurtma id / nomi bilan — ORM qo'riqchisini chetlab, Core insert); D — sezgirlik (korxonasiz
chaqiruv fiksturada ikkala korxonani qaytaradi); H — statik.

Ishlatish:
    python3 tools/test_top_tm_korxona.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_top_tm_korxona.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "top_tm_korxona_test"
_T = tempfile.mkdtemp(prefix="top_tm_korxona_")
_DB = os.path.join(_T, "top_tm_korxona_test.db")

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
from datetime import datetime                      # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, FinishedProduct, OrderItem, Order, OrderStatus, OrderType, ReturnItem, ReturnReason,
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


def xabar(r):
    d = js(r)
    if isinstance(d, dict):
        det = d.get("detail", d)
        if isinstance(det, dict):
            return str(det.get("message") or det)
        return str(det)
    return str(getattr(r, "text", ""))[:300]


def taxminan(a, b, eps=1e-6):
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


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""



# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — ikki korxona, har birida bitta READY buyurtma (TM dan olingan detal)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if _db.get(Company, 2) is None:
    _db.add(Company(id=2, name="TT Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TT_A", "Parol123!", UserRole.ADMIN, "TT A", company_id=1)
    auth.create_user(_db, "TT_B", "Parol123!", UserRole.ADMIN, "TT B", company_id=2)
ID = {}
for _cid, _h, _summa in ((1, "A", 700_000), (2, "B", 900_000)):
    _prj = Project(company_id=_cid, client_name=f"TT mijoz {_h}", project_name=f"TT {_h}", total_budget=0, total_paid=0)
    _fp = FinishedProduct(company_id=_cid, name=f"TT_TM_{_h}", quantity=0)
    _db.add_all([_prj, _fp])
    _db.flush()
    _o = Order(company_id=_cid, project_id=_prj.id, order_number=f"ORD-TT{_h}-1", order_type=OrderType.PRODUCT,
               status=OrderStatus.READY, completed_at=datetime.utcnow(), total_amount=_summa)
    _db.add(_o)
    _db.flush()
    _db.add(OrderItem(company_id=_cid, order_id=_o.id, name=f"TT_TM_{_h}", category="profil", quantity=5,
                      unit_price=_summa / 5, total_price=_summa, finished_product_id=_fp.id))
    ID[_h] = {"order": _o.id, "fp": _fp.id}
_db.commit()
_db.close()


def klient(harf):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    lr = req(c, "post", "/login", data={"username": f"TT_{harf}", "password": "Parol123!"}, follow_redirects=False)
    return c, lr.status_code


def royxat_http(c):
    r = req(c, "get", "/api/dashboard/top-finished-products", params={"days": 30, "limit": 50})
    d = js(r)
    return r.status_code, {x.get("name"): (x.get("revenue"), x.get("quantity")) for x in (d if isinstance(d, list) else [])}


def royxat(company_id="YOQ"):
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            if company_id == "YOQ":
                r = services.get_top_finished_products_sold(s, days=30, limit=50)
            else:
                r = services.get_top_finished_products_sold(s, days=30, limit=50, company_id=company_id)
        return {x.get("name"): (x.get("revenue"), x.get("quantity")) for x in r}
    except TypeError as e:                 # asl kodda company_id parametri yo'q — QULAMASIN
        return {"__TypeError__": str(e)[:120]}
    finally:
        s.close()


CA, _la = klient("A")
CB, _lb = klient("B")
section("A — HTTP: har admin faqat o'z korxonasini ko'radi")
check(f"{YORLIQ}A0 ikkala login 302", _la == 302 and _lb == 302, f"{_la} {_lb}")
_sa, _ra = royxat_http(CA)
_sb, _rb = royxat_http(CB)
check(f"{YORLIQ}A1 A: 200", _sa == 200, _sa)
check(f"{YORLIQ}A2 A ro'yxatida o'zi (700 000 / 5)", _ra.get("TT_TM_A") == (700000, 5.0), _ra)
check(f"{YORLIQ}A3 A ro'yxatida B YO'Q", "TT_TM_B" not in _ra, _ra)
check(f"{YORLIQ}A4 B: 200", _sb == 200, _sb)
check(f"{YORLIQ}A5 B ro'yxatida o'zi (900 000 / 5)", _rb.get("TT_TM_B") == (900000, 5.0), _rb)
check(f"{YORLIQ}A6 B ro'yxatida A YO'Q", "TT_TM_A" not in _rb, _rb)
check(f"{YORLIQ}A7 A ro'yxati AYNAN 1 ta", len(_ra) == 1, _ra)
check(f"{YORLIQ}A8 B ro'yxati AYNAN 1 ta", len(_rb) == 1, _rb)

section("B — funksiya to'g'ridan")
_b1, _b2, _b0 = royxat(1), royxat(2), royxat()
check(f"{YORLIQ}B1 company_id=1 -> faqat A", set(_b1) == {"TT_TM_A"}, _b1)
check(f"{YORLIQ}B2 company_id=2 -> faqat B", set(_b2) == {"TT_TM_B"}, _b2)
check(f"{YORLIQ}B3 company_id YO'Q (orqaga moslik — korxonasiz ichki chaqiruv) -> ikkalasi",
      set(_b0) == {"TT_TM_A", "TT_TM_B"}, _b0)
check(f"{YORLIQ}B4 summa aynan (A 700 000, B 900 000)",
      _b1.get("TT_TM_A") == (700000, 5.0) and _b2.get("TT_TM_B") == (900000, 5.0), (_b1, _b2))

section("C — qaytarish so'rovi ham korxona bilan cheklanadi")
# B korxonasiga tegishli qaytarish yozuvi A ning buyurtma id va detal nomi bilan (ilovada bo'lmaydigan buzilgan
# holat — ORM qo'riqchisi (_TENANT_REFS) bunday yozuvni rad etadi, shuning uchun Core insert). Korxona filtri
# bo'lmasa u A ning sotuvidan AYRILADI (A ning ro'yxati 0 ga tushadi).
_s = SessionLocal()
_s.execute(ReturnItem.__table__.insert().values(
    company_id=2, order_id=ID["A"]["order"], item_name="TT_TM_A", quantity=5, unit="metr",
    reason=ReturnReason.CUSTOMER_REQUEST, refund_amount=0, is_refunded=False, returned_at=datetime.utcnow(),
    coating_applied=False))
_s.commit()
_s.close()
_c1 = royxat(1)
check(f"{YORLIQ}C1 funksiya: A ning sotuvi B qaytarishi bilan KAMAYMADI (700 000 / 5)",
      _c1.get("TT_TM_A") == (700000, 5.0), _c1)
_sc, _rc = royxat_http(CA)
check(f"{YORLIQ}C2 HTTP: A ning sotuvi o'zgarmadi", _rc.get("TT_TM_A") == (700000, 5.0), _rc)
_c0 = royxat()
check(f"{YORLIQ}C3 sezgirlik: korxonasiz chaqiruvda o'sha yozuv A ni kamaytiradi (fikstura sezgir)",
      _c0.get("TT_TM_A") == (0, 0.0), _c0)
# O'z korxonasidagi qaytarish HALI ham ayriladi (filtr ortiqcha kesmaydi)
_s = SessionLocal()
_s.execute(ReturnItem.__table__.insert().values(
    company_id=2, order_id=ID["B"]["order"], item_name="TT_TM_B", quantity=2, unit="metr",
    reason=ReturnReason.CUSTOMER_REQUEST, refund_amount=0, is_refunded=False, returned_at=datetime.utcnow(),
    coating_applied=False))
_s.commit()
_s.close()
_c4 = royxat(2)
check(f"{YORLIQ}C4 o'z korxonasi qaytarishi ayriladi (B: 900 000 x 3/5 = 540 000 / 3)",
      _c4.get("TT_TM_B") == (540000, 3.0), _c4)
_sd, _rd = royxat_http(CB)
check(f"{YORLIQ}C5 HTTP B: 540 000 / 3", _rd.get("TT_TM_B") == (540000, 3.0), _rd)

section("H — statik")
_fn = manba(services, "get_top_finished_products_sold")
_rt = manba(main, "api_dashboard_top_finished_products")
check(f"{YORLIQ}H1 funksiyada company_id parametri", "company_id: int = None" in _fn, _fn[:120])
check(f"{YORLIQ}H2 sotuv so'rovida korxona filtri", "sold_rows.filter(Order.company_id == company_id)" in _fn)
check(f"{YORLIQ}H3 qaytarish so'rovida korxona filtri", "returns.filter(ReturnItem.company_id == company_id)" in _fn)
check(f"{YORLIQ}H4 marshrut korxonani uzatadi", "company_id=auth.company_id_of(current_user)" in _rt, _rt[-200:])
check(f"{YORLIQ}H5 filtr group_by / all dan OLDIN",
      tartibda(_fn, "sold_rows.filter(Order.company_id == company_id)", "sold_rows = sold_rows.group_by(")
      and tartibda(_fn, "returns.filter(ReturnItem.company_id == company_id)", "returns = returns.group_by("))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
