#!/usr/bin/env python3
"""
test_usta_oxirgi_sana.py — kech91 darvozasi (2026-09-26, 115-band): Usta KPI hisobotidagi "Oxirgi buyurtma"
sanasi (`crud.get_masters_kpi_report` → `last_order_date`, `/api/masters/kpi-report`, `/masters` sahifasi)
ikkala bazada ham ustaning "Tayyor" buyurtmalari orasidagi eng oxirgi HAQIQIY `completed_at`.

O'LCHANGAN (asl kod, `work/probe90_null.py`, kech90): `last_order` = `ORDER BY completed_at DESC .first()` —
PostgreSQL `DESC` da NULL larni BIRINCHI qo'yadi (SQLite — oxirida). Ustaning birorta "Tayyor" buyurtmasida
`completed_at` NULL bo'lsa (eski / qo'lda tuzatilgan ma'lumot) PG da sana BO'SH ("Hali yo'q") chiqardi,
SQLite da — haqiqiy oxirgi sana. Tuzatish: `.desc().nullslast()`.

Bo'limlar: A — funksiya to'g'ridan (8 usta, har biri alohida holat: NULL aralash, faqat NULL, "Tayyor" yo'q,
DELIVERED keyinroq, o'chirilgan buyurtma, nofaol usta, o'tgan yil, begona korxona); B — kesh bilan / keshsiz
AYNAN; C — HTTP (A va B korxona adminlari); D — nazorat (oddiy `DESC` PG da haqiqatan NULL ni oladi —
fikstura sezgir) va MAX oracle (har usta uchun natija = MAX(completed_at)); E — dinamik (eng oxirgi sana
NULL qilinsa keyingisi olinadi, qaytarilsa yana o'zi); H — statik.

Ishlatish:
    python3 tools/test_usta_oxirgi_sana.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_usta_oxirgi_sana.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "usta_oxirgi_sana_test"
_T = tempfile.mkdtemp(prefix="usta_oxirgi_sana_")
_DB = os.path.join(_T, "usta_oxirgi_sana_test.db")

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
    import crud                                    # noqa: E402
    import services                                # noqa: E402

from sqlalchemy import func                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderStatus, OrderType, Master, ErrorLog,
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
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


def iso(d):
    return d.isoformat() if d is not None else None


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxonada 7 usta, 2-korxonada 1 usta; har usta alohida holat.
# Buyurtmalar ATAYLAB sana tartibida EMAS yaratiladi (id tartibi ≠ sana tartibi).
# ══════════════════════════════════════════════════════════════
Y = datetime.utcnow().year
D1 = datetime(Y, 1, 5, 10, 0, 0)
D2 = datetime(Y, 2, 10, 11, 0, 0)
D3 = datetime(Y, 3, 15, 12, 30, 0)
D4 = datetime(Y, 4, 2, 9, 0, 0)
D5 = datetime(Y, 5, 6, 8, 0, 0)
D6 = datetime(Y, 6, 7, 7, 0, 0)
D9 = datetime(Y, 7, 1, 6, 0, 0)
LY = datetime(Y - 1, 12, 20, 15, 0, 0)
R_, V_, N_, I_ = OrderStatus.READY, OrderStatus.DELIVERED, OrderStatus.NEW, OrderStatus.IN_PROGRESS

# (kalit, korxona, faol, [(holat, completed_at, o'chirilganmi), ...])
REJA = [
    ("U1", 1, True, [(R_, D2, False), (R_, D3, False), (R_, None, False), (R_, D1, False), (R_, None, False)]),
    ("U2", 1, True, [(R_, None, False), (R_, None, False)]),
    ("U3", 1, True, [(I_, None, False), (V_, D5, False), (N_, None, False)]),
    ("U4", 1, True, [(R_, D1, False), (V_, D5, False)]),
    ("U5", 1, True, [(R_, D2, False), (R_, D6, True)]),
    ("U6", 1, False, [(R_, None, False), (R_, D4, False)]),
    ("U8", 1, True, [(R_, LY, False), (R_, None, False)]),
    ("U7", 2, True, [(R_, D9, False), (R_, None, False)]),
]
KUTILGAN = {"U1": D3, "U2": None, "U3": None, "U4": D1, "U5": D6, "U6": D4, "U8": LY, "U7": D9}
SONI = {"U1": 3, "U2": 0, "U3": 0, "U4": 1, "U5": 2, "U6": 1, "U8": 0, "U7": 1}

_db = SessionLocal()
if _db.get(Company, 2) is None:
    _db.add(Company(id=2, name="US Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "US_A", "Parol123!", UserRole.ADMIN, "US A", company_id=1)
    auth.create_user(_db, "US_B", "Parol123!", UserRole.ADMIN, "US B", company_id=2)
MID = {}
OID = {}
_prj = {}
for _cid in (1, 2):
    _p = Project(company_id=_cid, client_name=f"US mijoz {_cid}", project_name=f"US {_cid}", total_budget=0, total_paid=0)
    _db.add(_p)
    _db.flush()
    _prj[_cid] = _p.id
_n = 0
for _k, _cid, _faol, _buyurtmalar in REJA:
    _m = Master(company_id=_cid, name=f"US Usta {_k}", phone=f"+99890{_n:07d}", kpi_percent=3.0, is_active=_faol)
    _db.add(_m)
    _db.flush()
    MID[_k] = _m.id
    OID[_k] = []
    for _holat, _sana, _och in _buyurtmalar:
        _n += 1
        _o = Order(company_id=_cid, project_id=_prj[_cid], order_number=f"ORD-US-{_n}", order_type=OrderType.PRODUCT,
                   status=_holat, completed_at=_sana, total_amount=100_000 * _n, agreed_amount=100_000 * _n,
                   master_id=_m.id, is_deleted=_och)
        _db.add(_o)
        _db.flush()
        OID[_k].append(_o.id)
    _n += 1
_db.commit()
_db.close()
KALIT_BO_YICHA_ID = {v: k for k, v in MID.items()}


def hisobot(company_id=1, include_inactive=True, keshsiz=False):
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            fn = getattr(crud.get_masters_kpi_report, "__wrapped__", None) if keshsiz else crud.get_masters_kpi_report
            if fn is None:
                return {"__xato__": "__wrapped__ yo'q"}
            return fn(s, Y, include_inactive=include_inactive, company_id=company_id)
    except Exception as e:                 # noqa: BLE001
        return {"__xato__": f"{type(e).__name__}: {e}"}
    finally:
        s.close()


def sanalar(rep):
    """{kalit: (last_order_date, orders_count)} — faqat fikstura ustalari."""
    out = {}
    for r in (rep.get("masters") or []) if isinstance(rep, dict) else []:
        k = KALIT_BO_YICHA_ID.get(r.get("id"))
        if k:
            out[k] = (r.get("last_order_date"), r.get("orders_count"))
    return out


def xato_soni():
    s = SessionLocal()
    try:
        return s.query(ErrorLog).count()
    finally:
        s.close()


_xato0 = xato_soni()

section("A — funksiya to'g'ridan (1-korxona, nofaollar bilan)")
_a = hisobot(1, True)
_sa = sanalar(_a)
check("A0 hisobot xatosiz", isinstance(_a, dict) and "__xato__" not in _a, _a)
check("A1 U1 (NULL aralash): oxirgi sana = eng oxirgi HAQIQIY sana (15.03)", _sa.get("U1", (0,))[0] == iso(D3), _sa.get("U1"))
check("A2 U1 yillik buyurtmalar soni 3 (NULL sanali yilga kirmaydi)", _sa.get("U1", (0, 0))[1] == 3, _sa.get("U1"))
check("A3 U2 (faqat NULL sanali 'Tayyor'): sana yo'q", "U2" in _sa and _sa["U2"][0] is None, _sa.get("U2"))
check("A4 U3 ('Tayyor' yo'q, DELIVERED / NEW / jarayonda): sana yo'q", "U3" in _sa and _sa["U3"][0] is None, _sa.get("U3"))
check("A5 U4: keyinroq DELIVERED hisobga olinmaydi (05.01)", _sa.get("U4", (0,))[0] == iso(D1), _sa.get("U4"))
check("A6 U5: o'chirilgan 'Tayyor' ham hisobga olinadi (moliyaviy tarix — 07.06)", _sa.get("U5", (0,))[0] == iso(D6), _sa.get("U5"))
check("A7 U6 (nofaol, NULL + 02.04): 02.04", _sa.get("U6", (0,))[0] == iso(D4), _sa.get("U6"))
check("A8 U8: oxirgi sana yil bilan cheklanmaydi (o'tgan yil 20.12), yillik soni 0",
      _sa.get("U8") == (iso(LY), 0), _sa.get("U8"))
check("A9 1-korxona hisobotida 2-korxona ustasi YO'Q", "U7" not in _sa, sorted(_sa))
check("A10 yillik sonlar (U1..U8) AYNAN", all(_sa.get(k, (None, -1))[1] == SONI[k] for k in _sa) and len(_sa) == 7,
      {k: v[1] for k, v in _sa.items()})
_a2 = sanalar(hisobot(2, True))
check("A11 2-korxona: faqat U7, sana 01.07 (NULL aralash)", _a2 == {"U7": (iso(D9), 1)}, _a2)
_af = sanalar(hisobot(1, False))
check("A12 faqat faollar: U6 YO'Q, U1 hali 15.03", "U6" not in _af and _af.get("U1", (0,))[0] == iso(D3), _af)
_an = sanalar(hisobot(None, True))
check("A13 korxonasiz (orqaga moslik): 8 usta, U1 15.03, U7 01.07",
      len(_an) == 8 and _an.get("U1", (0,))[0] == iso(D3) and _an.get("U7", (0,))[0] == iso(D9), _an)
check("A14 fikstura: hisobot paytida xato jurnali o'smadi", xato_soni() == _xato0, (xato_soni(), _xato0))

section("B — kesh bilan / keshsiz AYNAN")
_bk = hisobot(1, True, keshsiz=True)
check("B1 1-korxona: keshsiz natija AYNAN", isinstance(_bk, dict) and "__xato__" not in _bk and _bk == _a, str(_bk)[:300])
_bk2 = hisobot(2, True, keshsiz=True)
check("B2 2-korxona: keshsiz natija AYNAN", _bk2 == hisobot(2, True), str(_bk2)[:300])
_s = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        with services.hisobot_keshi(_s):
            _ichki = crud.get_masters_kpi_report(_s, Y, include_inactive=True, company_id=1)
    check("B3 tashqi kesh ichida chaqiruv ham AYNAN", _ichki == _a, str(_ichki)[:300])
except Exception as e:                     # noqa: BLE001
    check("B3 tashqi kesh ichida chaqiruv ham AYNAN", False, f"{type(e).__name__}: {e}")
finally:
    _s.close()


def klient(harf):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    lr = req(c, "post", "/login", data={"username": f"US_{harf}", "password": "Parol123!"}, follow_redirects=False)
    return c, lr.status_code


def http_hisobot(c, **params):
    r = req(c, "get", "/api/masters/kpi-report", params=params)
    d = js(r)
    return r.status_code, sanalar(d if isinstance(d, dict) else {})


CA, _la = klient("A")
CB, _lb = klient("B")
section("C — HTTP /api/masters/kpi-report")
check("C0 ikkala login 302", _la == 302 and _lb == 302, f"{_la} {_lb}")
_c1s, _c1 = http_hisobot(CA, year=Y, include_inactive="true")
check("C1 A: 200", _c1s == 200, _c1s)
check("C2 A: U1 15.03, U2 yo'q, U8 o'tgan yil", _c1.get("U1", (0,))[0] == iso(D3) and _c1.get("U2", (0,))[0] is None
      and _c1.get("U8", (0,))[0] == iso(LY), _c1)
check("C3 A: HTTP natija funksiya bilan AYNAN (7 usta)", _c1 == _sa, (_c1, _sa))
_c4s, _c4 = http_hisobot(CB, year=Y, include_inactive="true")
check("C4 B: faqat U7, 01.07", _c4s == 200 and _c4 == {"U7": (iso(D9), 1)}, (_c4s, _c4))
_c5s, _c5 = http_hisobot(CA)
check("C5 A: standart (joriy yil, faqat faollar) — U6 YO'Q, U1 15.03",
      _c5s == 200 and "U6" not in _c5 and _c5.get("U1", (0,))[0] == iso(D3), (_c5s, _c5))

section("D — nazorat (fikstura sezgirligi) va MAX oracle")
_s = SessionLocal()
try:
    _naz = _s.query(Order).filter(Order.master_id == MID["U1"], Order.status == OrderStatus.READY) \
        .order_by(Order.completed_at.desc()).first()
    _naz_sana = _naz.completed_at if _naz is not None else "YOQ"
    if PG_URL:
        check("D1 NAZORAT: PG da oddiy DESC haqiqatan NULL sanali buyurtmani oladi (asl nuqson holati)",
              _naz_sana is None, _naz_sana)
    else:
        check("D1 NAZORAT: SQLite da oddiy DESC NULL ni oxiriga qo'yadi (15.03)", _naz_sana == D3, _naz_sana)
    _nulls = _s.query(Order).filter(Order.master_id == MID["U1"], Order.status == OrderStatus.READY,
                                    Order.completed_at.is_(None)).count()
    check("D2 U1 da NULL sanali 'Tayyor' buyurtmalar 2 ta", _nulls == 2, _nulls)
    _mx = dict(_s.query(Order.master_id, func.max(Order.completed_at))
               .filter(Order.status == OrderStatus.READY, Order.master_id.in_(list(MID.values())))
               .group_by(Order.master_id).all())
    _orc = {k: iso(_mx.get(MID[k])) for k in MID}
    _hamma = dict(_sa)
    _hamma.update(_a2)
    check("D3 har usta uchun natija = MAX(completed_at) ('Tayyor', NULL siz) — 8 usta",
          all(_hamma.get(k, ("YOQ",))[0] == _orc[k] for k in MID), (_orc, _hamma))
    check("D4 kutilgan jadval bilan AYNAN", all(_hamma.get(k, ("YOQ",))[0] == iso(KUTILGAN[k]) for k in MID), _hamma)
finally:
    _s.close()

section("E — dinamik: eng oxirgi sana NULL qilinsa — keyingisi, qaytarilsa — yana o'zi")
_u1_d3 = OID["U1"][1]
_s = SessionLocal()
_s.execute(Order.__table__.update().where(Order.__table__.c.id == _u1_d3).values(completed_at=None))
_s.commit()
_s.close()
_e1 = sanalar(hisobot(1, True))
check("E1 15.03 NULL qilindi → U1 oxirgi sana 10.02 (keyingi haqiqiy sana)", _e1.get("U1", (0,))[0] == iso(D2), _e1.get("U1"))
check("E2 U1 yillik soni 2 ga tushdi", _e1.get("U1", (0, 0))[1] == 2, _e1.get("U1"))
_s = SessionLocal()
_s.execute(Order.__table__.update().where(Order.__table__.c.id.in_(OID["U1"])).values(completed_at=None))
_s.commit()
_s.close()
_e3 = sanalar(hisobot(1, True))
check("E3 U1 ning HAMMA 'Tayyor' sanasi NULL → sana yo'q, soni 0", _e3.get("U1") == (None, 0), _e3.get("U1"))
_s = SessionLocal()
for _oid, (_h, _sana, _och) in zip(OID["U1"], REJA[0][3]):
    _s.execute(Order.__table__.update().where(Order.__table__.c.id == _oid).values(completed_at=_sana))
_s.commit()
_s.close()
_e4 = sanalar(hisobot(1, True))
check("E4 sanalar qaytarildi → U1 yana 15.03, soni 3", _e4.get("U1") == (iso(D3), 3), _e4.get("U1"))
check("E5 boshqa ustalar o'zgarmadi", {k: v for k, v in _e4.items() if k != "U1"} == {k: v for k, v in _sa.items() if k != "U1"},
      _e4)

section("H — statik")
_fn = manba(crud, "get_masters_kpi_report")
check("H1 last_order: DESC NULLS LAST", ").order_by(Order.completed_at.desc().nullslast()).first()" in _fn, _fn[-900:])
check("H2 asl so'rov qatori saqlangan (lint baseline / test_kesh_oquvchi langari)",
      "        last_order = db.query(Order).filter(" in _fn)
try:
    _crud_src = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
except Exception as e:                     # noqa: BLE001
    _crud_src = f"{type(e).__name__}: {e}"
check("H3 crud.py da NULLS LAST SIZ `completed_at DESC .first()` qolmagan",
      ".order_by(Order.completed_at.desc()).first()" not in _crud_src)
check("H4 javob maydoni o'zgarmagan (completed_at, NULL himoyasi bilan)",
      '"last_order_date": last_order.completed_at.isoformat() if last_order and last_order.completed_at else None' in _fn)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
