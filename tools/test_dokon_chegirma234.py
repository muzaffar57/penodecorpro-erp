#!/usr/bin/env python3
"""
test_dokon_chegirma234.py — kech169 (zip 234 «Chegirmalar»; egasi QARORLARI «Onlayn do'kon rejasi» 30.10).

NIMA UCHUN KERAK
  Admin modelni tanlab chegirma qo'yadi: foiz yoki yangi narx (ikkinchisi o'zi), xohlasa faqat ayrim o'lchamlarga; tugash sanasi
  ixtiyoriy — o'tsa chegirma o'zi o'chadi; qo'lda ham o'chadi. Faqat ODDIY narxga (ulgurji o'zgarmaydi), qoplamali va qoplamasizga bir
  xil foiz, komplektga o'zi o'tadi (komplekt = chegirmali detallar yig'indisi), tannarxdan past — faqat ogohlantirish (saqlash
  to'silmaydi). Xato hisob — saytda noto'g'ri narx, ulgurji narxning tushib ketishi yoki zarariga sotish.
BO'LIMLAR
  S — statik: jadval, yagona kalit, zaxira tartibi, korxona qo'riqchisi, marshrutlar.
  A — API: belgi o'chiq — 404, Menejer — 403, B korxona — 404; foiz / o'lchamlar / sana tekshiruvlari; saqlash, o'zgartirish,
      o'zgarishsiz (jurnal yo'q), o'chirish; model o'chsa chegirmasi ham; jurnal matnida tannarx / ulgurji raqami yo'q.
  K — narx: mustaqil hisob (oracle) bilan AYNAN — narx qatori (qoplamasiz / qoplamali — alohida va avto), yaxlitlash (1 000 / 100,
      pastga), faqat tanlangan o'lchamlar, ulgurji o'zgarmaydi, komplekt (rom / eshik, kapitel-bazasiz), ulgurji rom chegirmasiz,
      ko'rish (saqlamasdan) = saqlangandan keyin, hech narsa yozilmaydi.
  T — tannarx: ERP funksiyasi (`services.get_order_item_unit_cost`) bilan AYNAN (o'lchamlar to'ri, penoplast narxi o'zgarsa);
      dona / kapitel — hisoblanmaydi; past — ogohlantirish, saqlanadi; katalogda soni; yashirin qator — ogohlantirishsiz.
  M — muddat: Toshkent kuni (UTC 18:59 / 19:00), tugash kuni amalda, ertasi — o'chgan (narxlar, komplekt, katalog), matni.
  O — o'lcham nomi: oxirgi qator qayta nomlansa — chegirma ro'yxatida ham; qolgan qator bo'lsa — yo'q; qo'shilish — kengaymaydi.
  Z — zaxira: eksport → tiklash AYNAN; buzilgan qatorlar — rad, hech narsa o'zgarmaydi.
  P — PG parallel: bir modelga ikki oynadan, chegirma va model o'chirish bir vaqtda — 500 yo'q, bitta qator.
  U — HAQIQIY brauzer: shtorka, ko'rish, «Yangi narx» → foiz, saqlash (boshqa maydondagi matn yo'qolmaydi), belgi, ogohlantirish,
      o'lchamlar, sana, o'chirish, escape, 375 px, JS xatosi yo'q.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` (U — faqat SQLite / TF1).
Asl kodga (zip 233b) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_dokon_chegirma234.py
"""
import os
import io
import re
import sys
import glob
import json
import time
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "dokon234_test"
_T = tempfile.mkdtemp(prefix="t234_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't234.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, ActivityLog, ErrorLog, DokonDetal, DokonModel, Inventory, OrderItem   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

DokonChegirma = getattr(models, "DokonChegirma", None)    # asl kodda (zip 233b) yo'q — sinov qulamasin

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if callable(detail):
        try:
            detail = detail()
        except Exception as e:             # noqa: BLE001
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


def det(r):
    d = js(r)
    return str(d.get("detail") if isinstance(d, dict) else d)


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def xavfsiz(fn, std=None):
    try:
        return db_ishi(fn)
    except Exception:                      # noqa: BLE001
        return std


def ch_bazada(cid=1):
    """{model_id: (foiz Decimal, olchamlar (list | None), tugash ISO | None)}"""
    if DokonChegirma is None:
        return {}
    return db_ishi(lambda d: {c.model_id: (Decimal(str(c.foiz)).quantize(Decimal("0.01")),
                                           None if c.olchamlar is None else json.loads(c.olchamlar),
                                           c.tugash.isoformat() if c.tugash else None)
                              for c in d.query(DokonChegirma).filter(DokonChegirma.company_id == cid).all()})


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Vaqt: hamma «bugun» — Toshkent 2026-11-03 12:00 (UTC 07:00); M bo'limida o'zgartiriladi
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
class _SoxtaVaqt:
    t = datetime(2026, 11, 3, 7, 0)

    @classmethod
    def utcnow(cls):
        return cls.t


_asl_dt = getattr(crud, "_dt233", None)
if _asl_dt is not None:
    crud._dt233 = _SoxtaVaqt
BUGUN = date(2026, 11, 3)

s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T234 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t234_admin", PAROL, UserRole.ADMIN, "T234 Admin", company_id=1)
    auth.create_user(s, "t234_plat", PAROL, UserRole.ADMIN, "T234 Platforma", company_id=1)
    auth.create_user(s, "t234_men", PAROL, UserRole.MANAGER, "T234 Menejer", company_id=1)
    auth.create_user(s, "t234_b", PAROL, UserRole.ADMIN, "T234 B Admin", company_id=2)
s.query(User).filter(User.username == "t234_plat").first().is_platform_admin = True
for _p in s.query(Inventory).filter(Inventory.company_id == 1, Inventory.is_penoplast == True).all():   # noqa: E712
    _p.is_default_penoplast = False
PENO = Inventory(company_id=1, item_name="Penoplast T234", unit="blok", is_penoplast=True, is_default_penoplast=True,
                 volume_per_unit=0.96, price_per_unit=410000, stock_quantity=5)
s.add(PENO)
s.commit()
PENO_ID = PENO.id
s.close()
main._send_telegram = lambda msg, *a, **k: True


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t234_admin")
CP = mijoz("t234_plat")
CM = mijoz("t234_men")
CB = mijoz("t234_b")
API = "/api/sayt-katalogi"


def CH(mid):
    return API + f"/modellar/{mid}/chegirma"


def jurnal(entity="dokon_chegirma", cid=1):
    return db_ishi(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == entity, ActivityLog.company_id == cid).count())


def jurnal_matnlari(entity="dokon_chegirma", cid=1):
    return db_ishi(lambda d: [(a.action, a.old_value or "", a.new_value or "") for a in d.query(ActivityLog)
                              .filter(ActivityLog.entity_type == entity, ActivityLog.company_id == cid).order_by(ActivityLog.id).all()])


def katalog(c=CA):
    d = js(c.get(API))
    return d if isinstance(d, dict) else {}


def detal(did):
    return next((x for x in katalog().get("detallar", []) if x.get("id") == did), {})


def ix(lst, i):
    return lst[i] if -len(lst) <= i < len(lst) else 0


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("S1 jadval `dokon_chegirmalar`: company_id, model_id, foiz Numeric(5, 2), olchamlar, tugash (Date); yagona (company_id, model_id)",
      lambda: DokonChegirma.__tablename__ == "dokon_chegirmalar"
      and {c.name for c in DokonChegirma.__table__.columns} >= {"company_id", "model_id", "foiz", "olchamlar", "tugash"}
      and (DokonChegirma.__table__.c.foiz.type.precision, DokonChegirma.__table__.c.foiz.type.scale) == (5, 2)
      and DokonChegirma.__table__.c.tugash.type.__class__.__name__ == "Date" and not DokonChegirma.__table__.c.foiz.nullable
      and any({c.name for c in u.columns} == {"company_id", "model_id"} for u in DokonChegirma.__table__.constraints
              if u.__class__.__name__ == "UniqueConstraint"))
_tart = [c.__name__ for c in crud._reset_table_order()]
check("S2 zaxira / tozalash tartibida DokonChegirma — DokonModel dan OLDIN (o'chirish), tiklashda keyin",
      lambda: "DokonChegirma" in _tart and _tart.index("DokonChegirma") < _tart.index("DokonModel"), _tart[-8:])
check("S3 korxona qo'riqchisi: chegirma FAQAT o'z korxonasining modeliga (`_TENANT_REFS`)",
      lambda: models._TENANT_REFS.get("DokonChegirma") == [("model_id", "DokonModel")])
_yol = {(m, r.path) for r in main.app.routes for m in (getattr(r, "methods", None) or ())}
_kerak = {("PUT", API + "/modellar/{model_id}/chegirma"), ("DELETE", API + "/modellar/{model_id}/chegirma"),
          ("POST", API + "/modellar/{model_id}/chegirma/korish")}
check("S4 3 ta yangi marshrut", _kerak <= _yol, sorted(_kerak - _yol))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_st = [CA.put(CH(1), json={"foiz": 10}).status_code, CA.delete(CH(1)).status_code,
       CA.post(CH(1) + "/korish", json={"foiz": 10}).status_code]
check("A1 belgi o'chiq — 3 ta yangi marshrut 404", _st == [404] * 3, _st)
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
_k = katalog()
ROM = next((b["id"] for b in _k.get("bolimlar", []) if b.get("qolip") == "komplekt"), None)
KAR = next((b["id"] for b in _k.get("bolimlar", []) if b.get("nom") == "Karnizlar"), None)
DEK = next((b["id"] for b in _k.get("bolimlar", []) if b.get("qolip") == "dona"), None)
check("A2 katalogda `chegirmalar` (bo'sh), `bugun` (Toshkent) va tannarx izohi",
      lambda: _k.get("chegirmalar") == {} and _k.get("bugun") == "2026-11-03" and "penoplast" in (_k.get("tannarx_izoh") or ""),
      {k: _k.get(k) for k in ("chegirmalar", "bugun")})

# Modellar: M1 — komplekt (kapitel / baza bor), M2 — karniz (juft metr), M3 — dekor (dona)
M1 = js(CA.post(API + "/modellar", json={"bolim_id": ROM, "kod": "R-18", "kapitel_baza_bor": True})).get("id")
M2 = js(CA.post(API + "/modellar", json={"bolim_id": KAR, "kod": "K-5"})).get("id")
M3 = js(CA.post(API + "/modellar", json={"bolim_id": DEK, "kod": "D-1"})).get("id")
# (turi, o'lcham): (narx, qoplamali (None — avto), ulgurji, ulgurji qoplamali, ko'rinadi, eni, qalinligi)
NARX = {
    ("karniz", "O'rta"): (15000, 32000, 26000, None, True, 15, 10),
    ("podokonnik", "O'rta"): (14000, None, 24000, None, True, 20, 4),
    ("nalichnik", "O'rta"): (12000, 24000, 22000, 50000, True, 8, 3),
    ("kapitel", "O'rta"): (25000, 50000, 40000, None, True, None, None),
    ("baza", "O'rta"): (21000, None, 35000, None, True, None, None),
    ("karniz", "Katta"): (19900, None, 30000, None, True, 18, 12),
    ("podokonnik", "Katta"): (17500, 33000, 28000, None, True, 25, 5),
    ("nalichnik", "Katta"): (14000, None, 25000, None, True, 10, 3),
    ("kapitel", "Katta"): (31000, None, 45000, None, False, None, None),
    ("baza", "Katta"): (27000, None, 39000, None, True, None, None),
    ("karniz", "Kichik"): (9500, None, 15000, None, False, 10, 8),
    ("podokonnik", "Kichik"): (8800, None, 14000, None, True, 15, 3),
    ("nalichnik", "Kichik"): (7300.5, None, 12000, None, True, 6, 2),
    ("kapitel", "Kichik"): (18000, None, 30000, None, True, None, None),
    ("baza", "Kichik"): (15500, None, 26000, None, True, None, None),
}
DID = {}
for (_t, _o), (_n, _nq, _u, _uq, _y, _e, _q) in NARX.items():
    _r = CA.post(API + "/detallar", json={"model_id": M1, "turi": _t, "olcham": _o, "narx": _n, "narx_qoplamali": _nq, "ulgurji_narx": _u,
                                          "ulgurji_qoplamali": _uq, "yoqilgan": _y, "eni_sm": _e, "qalinligi_sm": _q})
    DID[(_t, _o)] = js(_r).get("id")
NARX2 = {"O'rta": (99000, None, 150000, 15, 10), "Katta": (1500, 2900, 2000, 30, 12), "Kichik": (20900, None, 30000, None, None)}
D2 = {}
for _o, (_n, _nq, _u, _e, _q) in NARX2.items():
    D2[_o] = js(CA.post(API + "/detallar", json={"model_id": M2, "turi": "asosiy", "olcham": _o, "narx": _n, "narx_qoplamali": _nq,
                                                 "ulgurji_narx": _u, "eni_sm": _e, "qalinligi_sm": _q})).get("id")
D3 = js(CA.post(API + "/detallar", json={"model_id": M3, "turi": "asosiy", "olcham": "Standart", "narx": 50000, "eni_sm": 20,
                                         "qalinligi_sm": 20})).get("id")
check("A3 fikstura: 15 + 3 + 1 narx qatori", len([v for v in DID.values() if v]) == 15 and all(D2.values()) and D3, (DID, D2, D3))

_st = [CM.put(CH(M1), json={"foiz": 10}).status_code, CM.delete(CH(M1)).status_code,
       CM.post(CH(M1) + "/korish", json={"foiz": 10}).status_code]
check("A4 Menejer — hammasi 403, hech narsa yozilmadi", _st == [403] * 3 and ch_bazada() == {}, (_st, ch_bazada()))
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", True))
_st = [CB.put(CH(M1), json={"foiz": 10}).status_code, CB.delete(CH(M1)).status_code,
       CB.post(CH(M1) + "/korish", json={"foiz": 10}).status_code]
check("A5 B korxonasi (belgisi yoqilgan) A modeliga — 404, hech narsa yozilmadi", _st == [404] * 3 and ch_bazada() == {}
      and ch_bazada(2) == {}, _st)
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", None))
_st = [CA.put(CH(999999), json={"foiz": 10}).status_code, CA.delete(CH(999999)).status_code,
       CA.post(CH(999999) + "/korish", json={"foiz": 10}).status_code, CA.put(API + "/modellar/0/chegirma", json={"foiz": 10}).status_code,
       CA.put(API + "/modellar/2147483648/chegirma", json={"foiz": 10}).status_code]
check("A6 yo'q model — 404; id 0 / 2³¹ — 422", _st == [404, 404, 404, 422, 422], _st)

# Foiz tekshiruvi
_f = getattr(crud, "_dokon_foiz", None)


def _fz(x):
    try:
        return _f(x)
    except ValueError:
        return "RAD"


_foizlar = [(15, Decimal("15.00")), (12.5, Decimal("12.50")), (1, Decimal("1.00")), (99, Decimal("99.00")), (0.995, Decimal("1.00")),
            (14.144, Decimal("14.14")), (14.145, Decimal("14.15")), (0.99, "RAD"), (0, "RAD"), (-5, "RAD"), (99.01, "RAD"), (100, "RAD"),
            (10 ** 400, "RAD"), (float("inf"), "RAD"), (float("nan"), "RAD"), ("15", "RAD"), (True, "RAD"), (None, "RAD")]
check("A7 foiz: 1 … 99, 2 xonaga HALF_UP (14,145 → 14,15; 0,995 → 1); 0,99 / 0 / manfiy / 100 / 10⁴⁰⁰ / cheksiz / NaN / matn / "
      "true / null — rad", lambda: [_fz(k) for k, _ in _foizlar] == [v for _, v in _foizlar],
      lambda: [(repr(k)[:20], _fz(k), v) for k, v in _foizlar if _fz(k) != v])
_raw = [CA.put(CH(M1), content=b, headers={"Content-Type": "application/json"}).status_code
        for b in (b'{"foiz": NaN}', b'{"foiz": Infinity}', b'{"foiz": 1' + b'0' * 400 + b'}', b'{"foiz": "15"}', b'{"foiz": null}',
                  b'{}', b'{"foiz": 15, "x": 1}', b'{"foiz": 15, "ulgurji": true}')]
check("A8 so'rov: NaN / Infinity / 10⁴⁰⁰ / «15» matn / null / foizsiz / noma'lum kalit — 400 (500 emas), hech narsa yozilmadi",
      _raw == [400] * 8 and ch_bazada() == {}, _raw)
check("A8b ro'yxat tana — 422", CA.put(CH(M1), json=[15]).status_code == 422)

# O'lchamlar tekshiruvi
_st = [(CA.put(CH(M1), json={"foiz": 10, "olchamlar": x}).status_code, det(CA.put(CH(M1), json={"foiz": 10, "olchamlar": x})))
       for x in ([], "O'rta", ["Ulkan"], [1], ["O'rta"] * 51, [None])]
check("A9 o'lchamlar: bo'sh ro'yxat / matn / yo'q o'lcham («Ulkan») / son / 51 ta / null element — 400",
      [x[0] for x in _st] == [400] * 6 and "Ulkan" in _st[2][1] and ch_bazada() == {}, _st)
# Sana tekshiruvi
_st = [CA.put(CH(M1), json={"foiz": 10, "tugash": x}).status_code
       for x in ("2026-11-02", "2026-02-30", "05.11.2026", "2026-11-5", 20261105, "2027-11-05", "")]
check("A10 tugash: kecha (Toshkent) / yo'q kun / boshqa shakl / son / 366 kundan uzoq / bo'sh — 400", _st == [400] * 7, _st)
_m0 = js(CA.post(API + "/modellar", json={"bolim_id": KAR, "kod": "K-0"})).get("id")
_r = CA.put(CH(_m0), json={"foiz": 10})
check("A11 narx qatorisiz model — 400 «narx qatori yo'q»", _r.status_code == 400 and "narx qatori" in det(_r), det(_r))
CA.delete(API + f"/modellar/{_m0}")

# Saqlash
_j0 = jurnal()
_r = CA.put(CH(M1), json={"foiz": 15, "olchamlar": None, "tugash": None})
_d = js(_r)
check("A12 saqlash: 200, javobda chegirma (−15 %, hamma o'lcham, muddatsiz, amalda), 15 narx qatori, komplekt, ogohlantirish yo'q; "
      "bazada; jurnal 1 ta «created»",
      lambda: _r.status_code == 200 and _d["chegirma"]["foiz"] == 15.0 and _d["chegirma"]["olchamlar"] is None
      and _d["chegirma"]["tugash"] is None and _d["chegirma"]["faol"] is True and len(_d["qatorlar"]) == 15
      and len(_d["komplekt"]) == 3 and _d["ogohlantirish"] == [] and ch_bazada() == {M1: (Decimal("15.00"), None, None)}
      and jurnal() == _j0 + 1 and jurnal_matnlari()[-1][0] == "created", (_r.status_code, _r.text[:400]))
_r = CA.put(CH(M1), json={"foiz": 15.0})
check("A13 o'sha qiymat qayta (15,0) — 200, jurnal yozilmadi", _r.status_code == 200 and jurnal() == _j0 + 1, jurnal_matnlari()[-2:])
_r = CA.put(CH(M1), json={"foiz": 20, "olchamlar": ["o’rta", "KATTA", "O'rta"], "tugash": "2026-11-30"})
check("A14 o'zgartirish: o'lchamlar tutuq / katta-kichik harfsiz, takrorsiz, model tartibida va birinchi yozilishida («O'rta», «Katta»); "
      "jurnal «updated» eski → yangi", lambda: _r.status_code == 200
      and ch_bazada()[M1] == (Decimal("20.00"), ["O'rta", "Katta"], "2026-11-30")
      and jurnal_matnlari()[-1] == ("updated", "−15 %; o'lchamlar: hamma o'lchamlar; muddatsiz",
                                    "−20 %; o'lchamlar: O'rta, Katta; 30-noyabrgacha"), lambda: (det(_r), jurnal_matnlari()[-1:]))
_r = CA.put(CH(M1), json={"foiz": 20, "tugash": "2026-11-03"})
check("A15 tugash — bugun (Toshkent) qabul; «olchamlar» yuborilmasa — hamma o'lcham (null)",
      _r.status_code == 200 and ch_bazada()[M1] == (Decimal("20.00"), None, "2026-11-03"), (det(_r), ch_bazada()))
_r = CA.put(CH(M1), json={"foiz": 20, "tugash": "2027-11-04"})
check("A15b tugash — bugundan 366 kun (2027-11-04) qabul", _r.status_code == 200 and ch_bazada()[M1][2] == "2027-11-04", det(_r))
_jm = " ".join(a + b + c for a, b, c in jurnal_matnlari())
check("A16 jurnal matnida tannarx (3 203 …) va ulgurji raqamlari (26 000, 24 000 …) YO'Q",
      lambda: not any(x in _jm for x in ("3 203", "3203", "26 000", "24 000", "22 000", "40 000", "35 000")) and "%" in _jm, _jm[:400])
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", True))
_kb = katalog(CB)
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", None))
check("A5b B korxonasi katalogida (belgisi yoqilgan) A ning chegirmasi YO'Q (A da bor)",
      lambda: M1 in ch_bazada() and _kb.get("chegirmalar") == {} and not any(x.get("chegirma") for x in _kb.get("detallar", [])),
      lambda: _kb.get("chegirmalar"))
check("A17 server xatosi yo'q (ErrorLog)", lambda: db_ishi(lambda d: d.query(ErrorLog).count()) == 0)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Narx — mustaqil hisob bilan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def o_ch(narx, foiz):
    """Mustaqil hisob (texnik qaror, review234 O1): narx × (100 − foiz) / 100 — 100 so'mgacha HALF_UP; asl narxdan kam va 0 dan katta
    bo'lmasa — 10 so'mgacha; u ham bo'lmasa — so'mning o'zi (kamida 0,01)."""
    if narx is None:
        return None
    n = Decimal(str(narx))
    a = n * (100 - Decimal(str(foiz))) / 100
    for q in (Decimal(100), Decimal(10)):
        x = (a / q).quantize(Decimal(1), rounding=ROUND_HALF_UP) * q
        if 0 < x < n:
            return float(x)
    return float(max(a.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), Decimal("0.01")))


def o_avto(n, koeff=2):
    a = Decimal(str(n)) * Decimal(str(koeff))
    x = (a / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 1000
    return x if x > 0 else a.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


_chn = getattr(crud, "dokon_chegirma_narx", None)
_qolda = [((15000, 15), 12800.0), ((198000, 15), 168300.0), ((1500, 10), 1400.0), ((1050, 1), 1000.0), ((20900, 1), 20700.0),
          ((10000, 5), 9500.0), ((9999, 5), 9500.0), ((0.05, 99), 0.01), ((7300.5, 20), 5800.0), ((19900, 20), 15900.0),
          ((10000, 1), 9900.0), ((1000, 1), 990.0), ((100, 1), 99.0), ((25000, 3), 24300.0)]
check("K1 qo'lda hisob (100 so'mgacha): 15 000 × 15 % = 12 750 → 12 800; 10 000 × 1 % → 9 900 (ilgari 9 000 — review234 O1); 1 000 × 1 % = "
      "990 (100 gacha → 1 000 = asl → 10 gacha); 100 × 1 % = 99; 25 000 × 3 % → 24 300; 0,05 × 99 % → 0,01",
      lambda: [float(_chn(n, f)) for (n, f), _ in _qolda] == [o_ch(n, f) for (n, f), _ in _qolda]
      and [o_ch(n, f) for (n, f), _ in _qolda] == [k for _, k in _qolda],
      lambda: [(n, f, float(_chn(n, f)), o_ch(n, f)) for (n, f), _ in _qolda])
_tor = [(n, f) for n in (100, 999, 1000, 4550, 9950, 9999.99, 10000, 10499, 10500, 15000, 99999, 198000, 1234567.89)
        for f in (1, 2.5, 10, 14.14, 33.33, 50, 75, 99)]
check(f"K2 to'r: {len(_tor)} ta (narx × foiz) — kod = mustaqil hisob, chegirmali har doim asl narxdan kam, > 0 va aniq hisobdan ≤ 50 so'm",
      lambda: all(float(_chn(n, Decimal(str(f)))) == o_ch(n, f) and 0 < float(_chn(n, Decimal(str(f)))) < n
                  and abs(float(_chn(n, Decimal(str(f)))) - n * (100 - f) / 100) <= 50 for n, f in _tor),
      lambda: [(n, f, float(_chn(n, Decimal(str(f)))), o_ch(n, f)) for n, f in _tor if float(_chn(n, Decimal(str(f)))) != o_ch(n, f)][:5])

# 15 %, hamma o'lcham
CA.put(CH(M1), json={"foiz": 15})
_k = katalog()


def _det_kut(t, o, foiz):
    n, nq, u, uq, y, e, q = NARX[(t, o)]
    return {"foiz": float(foiz), "narx": o_ch(n, foiz), "narx_qoplamali": o_ch(nq if nq is not None else o_avto(n), foiz)}


_kod = {k: next((x.get("chegirma") for x in _k.get("detallar", []) if x.get("id") == v), "YOQ") for k, v in DID.items()}
check("K3 katalog narx qatorlarida «chegirma» — 15 qatorning hammasi mustaqil hisob bilan AYNAN (qoplamali — alohida yozilgani yoki avto "
      "× 2 dan; yashirin qatorda ham)", lambda: all(_kod[k] == _det_kut(*k, 15) for k in DID), lambda: {k: (_kod[k], _det_kut(*k, 15))
                                                                                                        for k in DID if _kod[k] != _det_kut(*k, 15)})
_ulg = {k: next(((x.get("ulgurji_narx"), x.get("ulgurji_qoplamali"), x.get("narx")) for x in _k.get("detallar", []) if x.get("id") == v), None)
        for k, v in DID.items()}
check("K4 ulgurji narx va asl narx O'ZGARMAGAN (faqat oddiy narxga; chegirmali narx — alohida maydonda)",
      lambda: all(_ulg[k] == (float(NARX[k][2]), None if NARX[k][3] is None else float(NARX[k][3]), float(NARX[k][0])) for k in DID), _ulg)
STD = {"rom": {"karniz": 2, "podokonnik": 2, "nalichnik": 4, "kapitel": 2, "baza": 2},
       "eshik": {"karniz": 2, "nalichnik": 5, "kapitel": 2, "baza": 2}}


def o_komplekt(foiz, olchamlar=None, koeff=2):
    """{o'lcham: {"rom"|"eshik": {nom: summa | None}} | None} — chegirmali komplekt, NARX jadvalidan (kod funksiyalarisiz)."""
    nat = {}
    for ol in ("O'rta", "Katta", "Kichik"):
        if olchamlar is not None and ol.casefold() not in [x.casefold() for x in olchamlar]:
            nat[ol] = None
            continue
        nat[ol] = {}
        for kom in ("rom", "eshik"):
            q = STD[kom]
            y = {}
            for qop in (False, True):
                for kbsiz in (False, True):
                    jami = Decimal(0)
                    for t, m_ in q.items():
                        if not m_ or (kbsiz and t in ("kapitel", "baza")):
                            continue
                        v = NARX.get((t, ol))
                        if v is None or not v[4]:
                            jami = None
                            break
                        asl = v[0] if not qop else (v[1] if v[1] is not None else o_avto(v[0], koeff))
                        jami += Decimal(str(o_ch(asl, foiz))) * m_
                    y[("qoplamali" if qop else "qoplamasiz") + ("_kbsiz" if kbsiz else "")] = (
                        None if jami is None else float(jami.quantize(Decimal("0.01"))))
            nat[ol][kom] = y
    return nat


def kod_komplekt(mid=None):
    r = (katalog().get("komplekt") or {}).get(str(mid or M1)) or []
    return {x["olcham"]: (None if x.get("chegirma") is None else {k: x["chegirma"].get(k) for k in ("rom", "eshik")}) for x in r}


check("K5 komplekt (15 %, hamma o'lcham): rom / eshik × qoplamasiz / qoplamali × to'liq / kapitel-bazasiz — mustaqil hisob bilan AYNAN "
      "(Katta: kapitel yashirin → to'liq narxsiz)", lambda: kod_komplekt() == o_komplekt(15), lambda: (kod_komplekt(), o_komplekt(15)))
_o = (kod_komplekt().get("O'rta") or {}).get("rom") or {}
check("K5b qo'lda: O'rta rom = 2×12 800 + 2×11 900 + 4×10 200 + 2×21 300 + 2×17 900 = 168 600 (chegirmasiz 198 000 dan); kapitelsiz "
      "90 200", _o.get("qoplamasiz") == 168600.0 and _o.get("qoplamasiz_kbsiz") == 90200.0, _o)
_kx = (katalog().get("komplekt") or {}).get(str(M1)) or []
check("K6 komplektda chegirmasiz narxlar va ULGURJI rom o'zgarmagan, foiz — 15",
      lambda: next(x for x in _kx if x["olcham"] == "O'rta")["rom"]["qoplamasiz"] == 198000.0
      and next(x for x in _kx if x["olcham"] == "O'rta")["ulgurji_rom"]["qoplamasiz"] == 26000 + 24000 + 2 * 22000 + 2 * 40000 + 2 * 35000.0
      and "ulgurji_rom" not in (next(x for x in _kx if x["olcham"] == "O'rta")["chegirma"] or {})
      and next(x for x in _kx if x["olcham"] == "O'rta")["chegirma"]["foiz"] == 15.0, str(_kx)[:500])
_r = CA.get(API + f"/modellar/{M1}/komplekt")
check("K7 bitta model komplekt marshruti = katalogdagi (chegirma bilan)", lambda: js(_r).get("komplekt") == _kx)
# faqat ayrim o'lchamlar
CA.put(CH(M1), json={"foiz": 25, "olchamlar": ["Kichik", "Katta"]})
_k = katalog()
_kod = {k: next((x.get("chegirma") for x in _k.get("detallar", []) if x.get("id") == v), "YOQ") for k, v in DID.items()}
check("K8 faqat Katta va Kichik: O'rta qatorlarida chegirma yo'q (None), qolganlari — 25 % mustaqil hisob bilan",
      lambda: all(_kod[k] is None for k in DID if k[1] == "O'rta") and all(_kod[k] == _det_kut(*k, 25) for k in DID if k[1] != "O'rta"),
      _kod)
check("K9 komplekt: O'rta — chegirma yo'q, Katta / Kichik — 25 %", lambda: kod_komplekt() == o_komplekt(25, ["Katta", "Kichik"]),
      lambda: (kod_komplekt(), o_komplekt(25, ["Katta", "Kichik"])))
# ko'rish = saqlash, hech narsa yozmaydi
_j0, _b0 = jurnal(), ch_bazada()
_kor = js(CA.post(CH(M1) + "/korish", json={"foiz": 33.33, "olchamlar": ["O'rta"], "tugash": "2026-11-10"}))
check("K10 ko'rish (33,33 %, O'rta, 10-noyabr) — bazaga va jurnalga YOZILMADI", ch_bazada() == _b0 and jurnal() == _j0, ch_bazada())
_sq = js(CA.put(CH(M1), json={"foiz": 33.33, "olchamlar": ["O'rta"], "tugash": "2026-11-10"}))
check("K11 ko'rish javobi = saqlash javobi (narxlar, komplekt, ogohlantirish) — bitta hisob",
      lambda: {k: _kor[k] for k in ("qatorlar", "komplekt", "ogohlantirish")} == {k: _sq[k] for k in ("qatorlar", "komplekt", "ogohlantirish")}
      and _sq["chegirma"]["tugash_matni"] == "10-noyabrgacha" and _kor["chegirma"]["foiz"] == 33.33, (str(_kor)[:300], str(_sq)[:300]))
_r = js(CA.post(CH(M1) + "/korish", json={"foiz": None}))
check("K12 ko'rish «foiz»: null — asl narxlar va tannarx (chegirmali — yo'q), chegirma — null",
      lambda: _r["chegirma"] is None and all(q["chegirmali"] is None and q["qoplamali_chegirmali"] is None for q in _r["qatorlar"])
      and next(q for q in _r["qatorlar"] if q["detal_id"] == DID[("karniz", "O'rta")])["narx"] == 15000.0, str(_r)[:300])
_r = CA.post(CH(M1) + "/korish", json={"foiz": 120})
check("K12b ko'rishda ham tekshiruv: 120 % — 400", _r.status_code == 400 and "99" in det(_r), det(_r))
# M2: kichik narx, alohida qoplamali; narx qatori PUT javobi
CA.put(CH(M2), json={"foiz": 10})
_d2 = {o: detal(i).get("chegirma") for o, i in D2.items()}
check("K13 karniz modeli (10 %): 99 000 → 89 100 (qoplamali avto 198 000 → 178 200); 1 500 → 1 400 (qoplamali 2 900 → 2 600); "
      "20 900 → 18 800 (qoplamali avto 42 000 → 37 800)", _d2 == {"O'rta": {"foiz": 10.0, "narx": 89100.0, "narx_qoplamali": 178200.0},
                                            "Katta": {"foiz": 10.0, "narx": 1400.0, "narx_qoplamali": 2600.0},
                                            "Kichik": {"foiz": 10.0, "narx": 18800.0, "narx_qoplamali": 37800.0}}, _d2)
D2_ORTA = D2["O'rta"]
_r = CA.put(API + f"/detallar/{D2_ORTA}", json={"narx": 100000})
check("K14 narx qatori tahriri javobida — yangi chegirmali narx (100 000 → 90 000); katalog ham", lambda: js(_r).get("chegirma") ==
      {"foiz": 10.0, "narx": 90000.0, "narx_qoplamali": 180000.0} and (detal(D2["O'rta"]).get("chegirma") or {}).get("narx") == 90000.0, lambda: js(_r))
CA.put(API + f"/detallar/{D2_ORTA}", json={"narx": 99000})
_r = CA.post(API + "/detallar", json={"model_id": M2, "turi": "asosiy", "olcham": "Ulkan", "narx": 40000})
check("K15 yangi narx qatori (POST) javobida ham chegirma (hamma o'lchamga — yangi o'lcham ham): 40 000 → 36 000",
      js(_r).get("chegirma") == {"foiz": 10.0, "narx": 36000.0, "narx_qoplamali": 72000.0}, js(_r))
CA.delete(API + f"/detallar/{js(_r).get('id', 0)}")
_r = CA.post(API + "/detallar", json={"model_id": M2, "turi": "asosiy", "olcham": "Narxsiz"})
check("K16 narxi kiritilmagan qator — chegirma null", _r.status_code == 200 and js(_r).get("chegirma") is None, js(_r))
CA.delete(API + f"/detallar/{js(_r).get('id', 0)}")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Tannarx — ERP hisobi bilan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_dt = getattr(crud, "dokon_detal_tannarxi", None)


def erp(eni, qal, peno_id=None):
    def _f(d):
        it = OrderItem(category="profil", width=eni, thickness=qal, length=1, quantity=1, company_id=1, penoplast_id=peno_id)
        return services.get_order_item_unit_cost(d, None, it, include_coating=False)
    return db_ishi(_f)


def kod_tn(eni, qal, birlik="metr"):
    def _f(d):
        p = crud.dokon_tannarx_penoplasti(d, 1)
        x = DokonDetal(company_id=1, model_id=M2, turi="asosiy", olcham="x", birlik=birlik, eni_sm=eni, qalinligi_sm=qal)
        return _dt(x, p)[0]
    return db_ishi(_f)


_tor = [(e, q) for e in (0.5, 3, 7.5, 8, 10, 12.2, 15, 20.4, 33.3, 60) for q in (0.5, 2, 3, 4.5, 10, 12.25, 25)]
check(f"T1 {len(_tor)} ta (eni × qalinlik): 1 m tannarxi — ERP `get_order_item_unit_cost` (profil, qoplamasiz) bilan AYNAN",
      lambda: all(kod_tn(e, q) == erp(e, q) for e, q in _tor), lambda: [(e, q, kod_tn(e, q), erp(e, q)) for e, q in _tor
                                                                         if kod_tn(e, q) != erp(e, q)][:5])
db_ishi(lambda d: setattr(d.get(Inventory, PENO_ID), "price_per_unit", 515000))
check("T2 penoplast narxi o'zgardi (515 000) — tannarx ham, ERP bilan AYNAN (15 × 10 sm)",
      lambda: kod_tn(15, 10) == erp(15, 10) and kod_tn(15, 10) == round((0.15 * 0.10 / 2) / 0.96 * 515000), lambda: (kod_tn(15, 10), erp(15, 10)))
db_ishi(lambda d: setattr(d.get(Inventory, PENO_ID), "price_per_unit", 410000))
check("T3 dona / kapitel (birlik dona) va eni / qalinligi yo'q qator — tannarx hisoblanmaydi (sababi bilan)",
      lambda: kod_tn(20, 20, "dona") is None and kod_tn(None, 10) is None and kod_tn(15, None) is None)
_r = js(CA.put(CH(M1), json={"foiz": 85}))
_q = {q["detal_id"]: q for q in _r.get("qatorlar", [])}
_past = sorted(k for k, v in DID.items() if _q.get(v, {}).get("past"))
_tn15 = round((0.15 * 0.10 / 2) / 0.96 * 410000)
check("T4 85 %: tannarxi bor (metrli, eni / qalinlik) qatorlarda «past» — mustaqil hisob bilan; kapitel / baza — tannarx null va sabab",
      lambda: _q[DID[("karniz", "O'rta")]]["tannarx"] == _tn15 == 3203
      and _q[DID[("karniz", "O'rta")]]["past"] == ["qoplamasiz"]
      and _q[DID[("kapitel", "O'rta")]]["tannarx"] is None and "metrli" in _q[DID[("kapitel", "O'rta")]]["tannarx_sabab"]
      and all((v["past"] == [n for n, x in (("qoplamasiz", v["chegirmali"]), ("qoplamali", v["qoplamali_chegirmali"]))
                              if v["tannarx"] is not None and x is not None and x < v["tannarx"]]) for v in _q.values()),
      lambda: {k: (_q[v]["chegirmali"], _q[v]["qoplamali_chegirmali"], _q[v]["tannarx"], _q[v]["past"]) for k, v in DID.items()})
check("T5 85 % saqlandi (ogohlantirish to'smaydi) — ogohlantirishlar faqat saytda ko'rinadigan «past» qatorlar uchun, matnida "
      "narx va tannarx («3 203 so'm»)", lambda: ch_bazada()[M1][0] == Decimal("85.00")
      and len(_r["ogohlantirish"]) == len([k for k in _past if NARX[k][4]]) > 0
      and any("Rom karnizi — O'rta" in x and "3 203 so'm" in x and "2 300 so'm (qoplamasiz)" in x for x in _r["ogohlantirish"]),
      lambda: (_past, _r.get("ogohlantirish")))
check("T6 katalogda «ogohlantirish_soni» = javobdagi ogohlantirishlar soni", lambda: katalog()["chegirmalar"][str(M1)]["ogohlantirish_soni"]
      == len(_r["ogohlantirish"]), lambda: katalog().get("chegirmalar"))
_r3 = js(CA.post(CH(M2) + "/korish", json={"foiz": 10}))
_q3 = next((q for q in _r3.get("qatorlar", []) if q.get("detal_id") == D2["Katta"]), {})
check("T4b karniz Katta (30 × 12 sm, tannarx 7 688; 1 500 → 1 400, qoplamali 2 900 → 2 600) — ikkalasi ham past; ogohlantirishda "
      "«(qoplamasiz) va … (qoplamali)»", lambda: _q3["tannarx"] == round((0.30 * 0.12 / 2) / 0.96 * 410000) == 7688
      and _q3["past"] == ["qoplamasiz", "qoplamali"]
      and any("1\u00a0400 so'm (qoplamasiz) va 2\u00a0600 so'm (qoplamali)" in x for x in _r3["ogohlantirish"]), lambda: (_q3, _r3.get("ogohlantirish")))
db_ishi(lambda d: setattr(d.get(Inventory, PENO_ID), "is_default_penoplast", False))
db_ishi(lambda d: setattr(d.get(Inventory, PENO_ID), "is_penoplast", False))
_r2 = js(CA.post(CH(M1) + "/korish", json={"foiz": 85}))
check("T7 asosiy penoplast yo'q — tannarx null («asosiy penoplast … kiritilmagan»), ogohlantirish yo'q, xato yo'q",
      lambda: _r2["ogohlantirish"] == [] and all(q["tannarx"] is None for q in _r2["qatorlar"])
      and "penoplast" in next(q for q in _r2["qatorlar"] if q["detal_id"] == DID[("karniz", "O'rta")])["tannarx_sabab"], str(_r2)[:300])
db_ishi(lambda d: (setattr(d.get(Inventory, PENO_ID), "is_penoplast", True), setattr(d.get(Inventory, PENO_ID), "is_default_penoplast", True)))
_t7b = []
for _maydon in ("price_per_unit", "volume_per_unit"):
    db_ishi(lambda d: setattr(d.get(Inventory, PENO_ID), _maydon, 0))
    _rr = CA.post(CH(M1) + "/korish", json={"foiz": 85})
    _t7b.append((_rr.status_code, [q.get("tannarx") for q in js(_rr).get("qatorlar", [])][:3], len(js(_rr).get("ogohlantirish", [1]))))
    db_ishi(lambda d: setattr(d.get(Inventory, PENO_ID), _maydon, 410000 if _maydon == "price_per_unit" else 0.96))
check("T7b asosiy penoplast narxi 0 / blok hajmi 0 — tannarx null (0 emas, 500 emas), ogohlantirish yo'q",
      lambda: all(st == 200 and tn == [None, None, None] and og == 0 for st, tn, og in _t7b), _t7b)
CA.put(CH(M1), json={"foiz": 15})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Muddat (Toshkent)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bg = getattr(crud, "dokon_bugun", None)
_vaqtlar = [(datetime(2026, 11, 4, 18, 59), date(2026, 11, 4)), (datetime(2026, 11, 4, 19, 0), date(2026, 11, 5)),
            (datetime(2026, 12, 31, 19, 0), date(2027, 1, 1)), (datetime(2026, 11, 3, 0, 0), date(2026, 11, 3))]
_sx = _SoxtaVaqt.t
check("M1 bugungi kun — Toshkent: UTC 18:59 — o'sha kun, 19:00 — ertasi (yil almashuvi ham)",
      lambda: [_bg(t) for t, _ in _vaqtlar] == [k for _, k in _vaqtlar], lambda: [_bg(t) for t, _ in _vaqtlar])
CA.put(CH(M1), json={"foiz": 15, "tugash": "2026-11-05"})
CA.put(CH(M2), json={"foiz": 10, "tugash": "2027-01-05"})
_SoxtaVaqt.t = datetime(2026, 11, 5, 18, 59)              # Toshkent 5-noyabr 23:59 — amalda
_a = katalog()
_SoxtaVaqt.t = datetime(2026, 11, 5, 19, 0)               # Toshkent 6-noyabr 00:00 — tugagan
_b = katalog()
check("M2 tugash kuni (5-noyabr 23:59) — amalda; 6-noyabr 00:00 — o'chgan: chegirma «faol» false, narx qatorlarida chegirma null, "
      "komplektda null, ogohlantirish soni 0; bazada QOLADI",
      lambda: _a["chegirmalar"][str(M1)]["faol"] is True and _b["chegirmalar"][str(M1)]["faol"] is False
      and next(x for x in _a["detallar"] if x["id"] == DID[("karniz", "O'rta")])["chegirma"] is not None
      and next(x for x in _b["detallar"] if x["id"] == DID[("karniz", "O'rta")])["chegirma"] is None
      and all(x["chegirma"] is None for x in _b["komplekt"][str(M1)]) and _b["chegirmalar"][str(M1)]["ogohlantirish_soni"] == 0
      and M1 in ch_bazada(), lambda: (_a.get("chegirmalar"), _b.get("chegirmalar")))
_r = CA.put(CH(M1), json={"foiz": 15, "tugash": "2026-11-05"})
_r2 = CA.put(CH(M1), json={"foiz": 15, "tugash": "2026-11-06"})
check("M3 muddati o'tgan sana bilan qayta saqlash — 400; bugungi (6-noyabr) bilan — 200, yana amalda",
      _r.status_code == 400 and _r2.status_code == 200 and (js(_r2).get("chegirma") or {}).get("faol") is True, (det(_r), det(_r2)))
check("M4 matn: shu yil — «6-noyabrgacha», keyingi yil — «2027-yil 5-yanvargacha», muddatsiz — null",
      lambda: katalog()["chegirmalar"][str(M1)]["tugash_matni"] == "6-noyabrgacha"
      and katalog()["chegirmalar"][str(M2)]["tugash_matni"] == "2027-yil 5-yanvargacha"
      and crud.dokon_chegirma_muddat_matni(None) is None, lambda: katalog().get("chegirmalar"))
_SoxtaVaqt.t = _sx
CA.put(CH(M1), json={"foiz": 15})
CA.put(CH(M2), json={"foiz": 10})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("O. O'lcham nomi o'zgarsa")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
CA.put(CH(M2), json={"foiz": 10, "olchamlar": ["Katta", "Kichik"]})
_j0 = jurnal("dokon_detal")
CA.put(API + f"/detallar/{D2['Katta']}", json={"olcham": "Katta (30 sm)"})
check("O1 o'lchamdagi yagona qator qayta nomlandi — chegirma ro'yxatida ham («Katta (30 sm)», tartib saqlangan), qator jurnalida izoh",
      lambda: ch_bazada()[M2][1] == ["Katta (30 sm)", "Kichik"] and (detal(D2["Katta"]).get("chegirma") or {}).get("narx") == 1400.0
      and "chegirma o'lchami" in jurnal_matnlari("dokon_detal")[-1][2], lambda: (ch_bazada().get(M2), jurnal_matnlari("dokon_detal")[-1:]))
CA.put(API + f"/detallar/{D2['Katta']}", json={"olcham": "Katta"})
CA.put(CH(M1), json={"foiz": 15, "olchamlar": ["Katta"]})
CA.put(API + f"/detallar/{DID[('karniz', 'Katta')]}", json={"olcham": "Katta+"})
check("O2 o'lchamda boshqa qatorlar qoldi (podokonnik, nalichnik … «Katta») — eski nom QOLDI, yangi nom («Katta+», modelda yangi) QO'SHILDI; "
      "qayta nomlangan qator ham chegirmali (review234 Y1)", lambda: ch_bazada()[M1][1] == ["Katta", "Katta+"]
      and (detal(DID[("karniz", "Katta")]).get("chegirma") or {}).get("foiz") == 15.0, ch_bazada().get(M1))
CA.put(API + f"/detallar/{DID[('karniz', 'Katta')]}", json={"olcham": "Katta"})
check("O2b qaytarib «Katta» (bor o'lcham) — «Katta+» oxirgi qatori ketdi, ro'yxatdan olindi: [«Katta»]",
      lambda: ch_bazada()[M1][1] == ["Katta"], ch_bazada().get(M1))
CA.put(CH(M2), json={"foiz": 10, "olchamlar": ["Kichik"]})
M4 = js(CA.post(API + "/modellar", json={"bolim_id": ROM, "kod": "R-O3"})).get("id")
_a3 = js(CA.post(API + "/detallar", json={"model_id": M4, "turi": "karniz", "olcham": "Kichik", "narx": 10000})).get("id")
_b3 = js(CA.post(API + "/detallar", json={"model_id": M4, "turi": "podokonnik", "olcham": "Katta", "narx": 12000})).get("id")
CA.put(CH(M4), json={"foiz": 10, "olchamlar": ["Katta"]})
_r = CA.put(API + f"/detallar/{_b3}", json={"olcham": "KICHIK"})
check("O3 qator boshqa (chegirmasiz) o'lchamga qo'shildi (podokonnik «Katta» → «KICHIK», karniz «Kichik» bor) — chegirma kengaymadi: "
      "ro'yxatdan chiqdi (bo'sh), ikkala qator chegirmasiz", lambda: _r.status_code == 200 and ch_bazada()[M4][1] == []
      and detal(_a3).get("chegirma") is None and detal(_b3).get("chegirma") is None
      and katalog()["chegirmalar"][str(M4)]["olchamlar"] == [], lambda: (det(_r), ch_bazada().get(M4)))
CA.delete(API + f"/modellar/{M4}")
CA.put(CH(M2), json={"foiz": 10, "olchamlar": ["Kichik"]})
CA.delete(API + f"/detallar/{D2['Kichik']}")
check("O4 o'lchamning oxirgi qatori o'chirildi — chegirmada «narx qatori qolmagan o'lcham» (yoq_olchamlar)",
      lambda: katalog()["chegirmalar"][str(M2)]["yoq_olchamlar"] == ["Kichik"], lambda: katalog()["chegirmalar"].get(str(M2)))
_KAT = [DID[(_t, "Katta")] for _t in ("karniz", "podokonnik", "nalichnik", "kapitel", "baza")]
CA.put(CH(M1), json={"foiz": 15, "olchamlar": ["Katta"]})
_j0 = jurnal()
_hol = []
for _did in _KAT:
    CA.put(API + f"/detallar/{_did}", json={"olcham": "Katta 25 sm"})
    _hol.append(ch_bazada().get(M1, (0, None))[1])
_kk = next((x for x in (katalog().get("komplekt") or {}).get(str(M1), []) if x["olcham"] == "Katta 25 sm"), {})
check("O6 komplekt o'lchami (5 qator) bittalab qayta nomlandi — ro'yxat: [Katta, Katta 25 sm] × 4, oxirida [Katta 25 sm]; hamma 5 qator va "
      "komplekt «Katta 25 sm» chegirmali; chegirma jurnalida 2 ta yozuv (qo'shildi, eski olindi) (review234 Y1 / P4)",
      lambda: _hol == [["Katta", "Katta 25 sm"]] * 4 + [["Katta 25 sm"]]
      and all((detal(i).get("chegirma") or {}).get("foiz") == 15.0 for i in _KAT) and (_kk.get("chegirma") or {}).get("foiz") == 15.0
      and jurnal() == _j0 + 2 and "«Katta» → «Katta 25 sm»" in jurnal_matnlari()[-1][2], lambda: (_hol, jurnal_matnlari()[-2:]))
for _did in _KAT:
    CA.put(API + f"/detallar/{_did}", json={"olcham": "Katta"})
D2["Kichik"] = js(CA.post(API + "/detallar", json={"model_id": M2, "turi": "asosiy", "olcham": "Kichik", "narx": 20900,
                                                   "ulgurji_narx": 30000})).get("id")
check("O5 o'sha o'lcham qayta qo'shildi — chegirma yana amalda (20 900 → 18 800)",
      lambda: (detal(D2["Kichik"]).get("chegirma") or {}).get("narx") == 18800.0 and katalog()["chegirmalar"][str(M2)]["yoq_olchamlar"] == [])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
CA.put(CH(M1), json={"foiz": 12.5, "olchamlar": ["O'rta", "Kichik"], "tugash": "2026-12-01"})
_oldin = ch_bazada()
_zax = db_ishi(lambda d: crud.export_full_backup(d, company_id=1))
_zax = json.loads(json.dumps(_zax, default=str))


def _tikla(o):
    z = json.loads(json.dumps(_zax))
    _asl = json.loads(json.dumps((_zax.get("tables") or {}).get("dokon_chegirmalar") or []))
    # asl kodda (zip 233b) eksportda jadval yo'q — sinov qulamasin (namuna qator)
    z.setdefault("tables", {})["dokon_chegirmalar"] = o(_asl or [{"id": 901, "company_id": 1, "model_id": M1, "foiz": 10.0, "olchamlar": None,
                                                              "tugash": None}])
    s2 = SessionLocal()
    try:
        return crud.import_full_backup(s2, z, company_id=1, replace=True)
    except Exception as e:                 # noqa: BLE001
        return {"success": False, "message": f"QULADI {type(e).__name__}: {e}"}
    finally:
        s2.close()


_nat = _tikla(lambda r: r)
check("Z1 eksport (2 ta chegirma) → tiklash: muvaffaqiyatli, chegirmalar AYNAN (foiz, o'lchamlar, tugash)",
      lambda: len((_zax.get("tables") or {}).get("dokon_chegirmalar") or []) == 2 and _nat.get("success") is True
      and ch_bazada() == _oldin, lambda: (str(_nat)[:300], ch_bazada(), _oldin))
_buzuq = [lambda r: [dict(r[0], foiz=0)] + r[1:], lambda r: [dict(r[0], foiz=150)] + r[1:], lambda r: [dict(r[0], foiz="abc")] + r[1:],
          lambda r: [dict(r[0], foiz=True)] + r[1:], lambda r: [dict(r[0], olchamlar="{bu json emas")] + r[1:],
          lambda r: [dict(r[0], olchamlar="[1, 2]")] + r[1:], lambda r: [dict(r[0], olchamlar=json.dumps(["x" * 41]))] + r[1:],
          lambda r: [dict(r[0], tugash="2026-13-01")] + r[1:], lambda r: [dict(r[0], tugash=20261201)] + r[1:],
          lambda r: r + [dict(r[0], id=9999)], lambda r: [dict(r[0], model_id=987654)] + r[1:],
          lambda r: [dict(r[0], olchamlar=json.dumps(["O'rta", "\ud800"]))] + r[1:], lambda r: [dict(r[0], olchamlar=json.dumps(["O'rta\u0000"]))] + r[1:],
          lambda r: [dict(r[0], olchamlar=json.dumps([" O'rta"]))] + r[1:], lambda r: [dict(r[0], model_id=None)] + r[1:]]
_nat2 = [_tikla(f) for f in _buzuq]
check(f"Z2 qo'lda buzilgan zaxira ({len(_buzuq)} xil: foiz 0 / 150 / matn / true, o'lchamlar JSON emas / sonlar / 41 belgi / buzilgan "
      "Unicode / NUL / chetida bo'shliq (review234 O2), sana yo'q kun / son, bir modelga ikki chegirma, begona / bo'sh model) — rad, hech "
      "narsa o'zgarmadi",
      lambda: all(n.get("success") is False and "dokon_" in n.get("message", "") for n in _nat2) and ch_bazada() == _oldin,
      lambda: ([str(n.get("message"))[:90] for n in _nat2], ch_bazada()))
_r = CA.delete(API + f"/modellar/{M3}")
_m6 = js(CA.post(API + "/modellar", json={"bolim_id": DEK, "kod": "D-2"})).get("id")
CA.post(API + "/detallar", json={"model_id": _m6, "turi": "asosiy", "olcham": "S", "narx": 1000})
_st = [CA.put(CH(_m6), json={"foiz": 5}).status_code, CA.delete(API + f"/modellar/{_m6}").status_code]
check("Z3 chegirmasi yo'q modelni o'chirish — 200; chegirmali model o'chirilsa chegirmasi ham o'chadi, model jurnalida «chegirma −5 %»",
      lambda: _r.status_code == 200 and _st == [200, 200] and _m6 not in ch_bazada()
      and xavfsiz(lambda d: d.query(DokonChegirma).filter(DokonChegirma.model_id == _m6).count()) == 0
      and "chegirma −5 %" in jurnal_matnlari("dokon_model")[-1][1], lambda: (_st, jurnal_matnlari("dokon_model")[-1:]))
_r = CA.delete(CH(M2))
_r2 = CA.delete(CH(M2))
check("Z4 chegirmani o'chirish — 200, ikkinchi marta — 404 «chegirma yo'q»; jurnal «deleted»",
      _r.status_code == 200 and _r2.status_code == 404 and "chegirma" in det(_r2) and M2 not in ch_bazada()
      and jurnal_matnlari()[-1][0] == "deleted", (det(_r), det(_r2)))
check("Z5 server xatosi yo'q (ErrorLog)", lambda: db_ishi(lambda d: d.query(ErrorLog).count()) == 0,
      lambda: db_ishi(lambda d: [e.message[:200] for e in d.query(ErrorLog).limit(3).all()]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PG parallel")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    from concurrent.futures import ThreadPoolExecutor

    def parallel(fns):
        with ThreadPoolExecutor(max_workers=len(fns)) as ex:
            return [f.result() for f in [ex.submit(fn) for fn in fns]]

    _c1, _c2 = mijoz("t234_admin"), mijoz("t234_admin")
    _asl_ch = getattr(crud, "_dokon_chegirma_of", None)

    def _sekin(*a, **k):
        r = _asl_ch(*a, **k)
        time.sleep(0.4)                    # o'qishdan KEYIN kechikish — qulfsiz kodda ikkalasi ham «chegirma yo'q» ko'rardi
        return r
    if _asl_ch:
        crud._dokon_chegirma_of = _sekin
    _j0 = jurnal()
    _st = sorted(parallel([lambda: _c1.put(CH(M2), json={"foiz": 11}).status_code, lambda: _c2.put(CH(M2), json={"foiz": 22}).status_code]))
    check("P1 bir modelga ikki oynadan bir vaqtda chegirma — ikkalasi 200 (ketma-ket), bazada BITTA qator, jurnal: created + updated",
          _st == [200, 200] and ch_bazada()[M2][0] in (Decimal("11.00"), Decimal("22.00"))
          and [a for a, _, _ in jurnal_matnlari()[-2:]] == ["created", "updated"] and jurnal() == _j0 + 2, (_st, ch_bazada().get(M2)))
    _m5 = js(CA.post(API + "/modellar", json={"bolim_id": KAR, "kod": "K-P"})).get("id")
    CA.post(API + "/detallar", json={"model_id": _m5, "turi": "asosiy", "olcham": "S", "narx": 50000})
    _st = sorted(parallel([lambda: _c1.put(CH(_m5), json={"foiz": 30}).status_code,
                           lambda: _c2.delete(API + f"/modellar/{_m5}").status_code]))
    check("P2 chegirma saqlash va modelni o'chirish bir vaqtda — 500 yo'q; model o'chdi, yetim chegirma qolmadi",
          _st in ([200, 200], [200, 404]) and _m5 not in ch_bazada()
          and xavfsiz(lambda d: d.query(DokonModel).filter(DokonModel.id == _m5).count()) == 0, (_st, ch_bazada()))
    if _asl_ch:
        crud._dokon_chegirma_of = _asl_ch
    # review234 P6 (zip 231 dan beri): o'lcham nomi va modelni o'chirish bir vaqtda — qulf tartibi bir xil (model → qator), deadlock yo'q
    _m7 = js(CA.post(API + "/modellar", json={"bolim_id": KAR, "kod": "K-D"})).get("id")
    _d7 = js(CA.post(API + "/detallar", json={"model_id": _m7, "turi": "asosiy", "olcham": "S", "narx": 50000})).get("id")
    _asl_mo = getattr(crud, "_dokon_model_of", None)

    def _sekin_m(*a, **k):
        r = _asl_mo(*a, **k)
        if k.get("lock"):
            time.sleep(0.6)                # model qulfidan KEYIN kechikish — eski tartibda (qator → model) ikki so'rov bir-birini kutardi
        return r
    crud._dokon_model_of = _sekin_m

    def _nom7():
        time.sleep(0.15)
        return _c1.put(API + f"/detallar/{_d7}", json={"olcham": "Yangi"}).status_code
    _st = parallel([lambda: _c2.delete(API + f"/modellar/{_m7}").status_code, _nom7])
    crud._dokon_model_of = _asl_mo
    check("P4 modelni o'chirish va uning o'lchamini qayta nomlash bir vaqtda — deadlock / 500 yo'q: o'chirish 200, nom 200 yoki 404 "
          "(review234 P6)", _st[0] == 200 and _st[1] in (200, 404)
          and xavfsiz(lambda d: d.query(DokonModel).filter(DokonModel.id == _m7).count()) == 0, _st)
    check("P3 server xatosi yo'q", lambda: db_ishi(lambda d: d.query(ErrorLog).count()) == 0,
          lambda: db_ishi(lambda d: [e.message[:200] for e in d.query(ErrorLog).limit(3).all()]))
else:
    print("  (faqat PG rejimida)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
br = pw_ctx = server = None
if PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
    try:
        from playwright.sync_api import sync_playwright
        PW_BOR, _pw_x = True, ""
    except Exception as _e:                # noqa: BLE001
        PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
    import uvicorn                                 # noqa: E402

    def _port():
        so = socket.socket()
        so.bind(("127.0.0.1", 0))
        p = so.getsockname()[1]
        so.close()
        return p

    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    B = f"http://127.0.0.1:{port}"
    if PW_BOR and server.started:
        pw_ctx = sync_playwright().start()
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                  "chrome-linux", "chrome"))):
            _exe = _yol
        try:
            br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
        except Exception as _e:            # noqa: BLE001
            br = None
            _pw_x = f"{type(_e).__name__}: {_e}"
    check("U0 lokal server va Chromium", bool(server.started and br), _pw_x)
    JS_XATO, SOROV, KONSOL = [], [], []

    def kontekst(login, kenglik=1440):
        ctx = br.new_context(viewport={"width": kenglik, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
        ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
        pg.on("console", lambda m: KONSOL.append(m.text[:200]) if m.type == "error" else None)
        pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""))) if "/api/" in q.url else None)
        pg.goto(B + "/login")
        pg.fill("input[name=username]", login)
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
        return ctx, pg

    def kut(pg, ifoda, ms=8000):
        try:
            pg.wait_for_function(ifoda, timeout=ms)
            return True
        except Exception:                  # noqa: BLE001
            return False

    def matn(pg, sel):
        return pg.evaluate(f"(document.querySelector(\"{sel}\") || {{}}).innerText || ''")

    if br:
        try:
            CA.delete(CH(M1))
            _xss = js(CA.post(API + "/detallar", json={"model_id": M1, "turi": "karniz", "olcham": '"><b>XSS</b>', "narx": 30000})).get("id")
            ctx, pg = kontekst("t234_admin")
            pg.goto(B + "/sayt-katalogi")
            kut(pg, "document.querySelectorAll('#skBolimlar .sk-bolim').length > 3")
            pg.evaluate("() => { const b = [...document.querySelectorAll('#skBolimlar .sk-bolim')].find(x => x.innerText.includes('Rom va eshik')); b && b.click(); }")
            kut(pg, f"!!document.querySelector('[data-och=\"{M1}\"]')")
            pg.evaluate(f"() => {{ const x = document.querySelector('[data-och=\"{M1}\"]'); x && x.click(); }}")
            CHS = f"[data-chegirma='{M1}']"
            _y = kut(pg, f"!!document.querySelector(\"{CHS} details.sht\")")
            check("U1 model ichida «🏷 Chegirma» shtorkasi, holati «yo'q»; sarlavhada chegirma belgisi yo'q",
                  _y and "Chegirma" in matn(pg, CHS + " summary") and "yo'q" in matn(pg, CHS + " summary")
                  and matn(pg, f"[data-chbelgi='{M1}']").strip() == "", matn(pg, CHS + " summary"))
            _bas = len(SOROV)
            pg.click(CHS + " summary")
            _y = kut(pg, f"document.querySelectorAll(\"{CHS} [data-chnatija] tbody tr\").length >= 16")
            check("U2 shtorka ochildi — narxlar serverdan (ko'rish, foiz null): 16 qator, karniz O'rta tannarxi 3 203, «→» yo'q",
                  _y and "3 203" in matn(pg, CHS + " [data-chnatija]").replace(" ", " ") and "→" not in matn(pg, CHS + " [data-chnatija]")
                  and ("POST", CH(M1) + "/korish") in SOROV[_bas:], matn(pg, CHS + " [data-chnatija]")[:300])
            check("U3 o'lcham nomidagi HTML — matn bo'lib (escape): checkbox yorlig'ida va jadvalda «\"><b>XSS</b>», «XSS» li <b> teg yo'q",
                  '"><b>XSS</b>' in matn(pg, CHS + " [data-cholcham]") and '"><b>XSS</b>' in matn(pg, CHS + " [data-chnatija]")
                  and pg.evaluate(f"![...document.querySelectorAll(\"{CHS} b, [data-model='{M1}'] b\")].some(b => b.textContent === 'XSS')"),
                  matn(pg, CHS + " [data-cholcham]")[:200])
            # model nomiga yozilgan, saqlanmagan matn — chegirma amallaridan keyin yo'qolmasin
            pg.fill(f".sk-model[data-model='{M1}'] [data-mf=nom]", "Klassik (saqlanmagan)")
            _bas = len(SOROV)
            pg.fill(CHS + " [data-chf=foiz]", "15")
            _y = kut(pg, f"(document.querySelector(\"{CHS} [data-chnatija]\").innerText || '').replace(/\\s/g, '').indexOf('168600') >= 0")
            check("U4 foiz 15 yozildi — ko'rish (saqlamasdan): «198 000 → 168 600» komplekt, «15 000 → 12 800»; PUT yo'q",
                  _y and "15000→12800" in matn(pg, CHS + " [data-chnatija]").replace(" ", "").replace(" ", "")
                  and not [x for x in SOROV[_bas:] if x[0] == "PUT"] and ch_bazada() == {}, matn(pg, CHS + " [data-chnatija]")[:400])
            pg.evaluate("""() => { const f = window.fetch; window.__asl_fetch = f;
                window.fetch = (u, o) => (o && o.method === 'POST' && /chegirma\\/korish/.test(String(u)) && /"foiz":15[,}]/.test(String(o.body || '')))
                  ? new Promise(r => setTimeout(r, 1800)).then(() => f(u, o)) : f(u, o); }""")
            pg.fill(CHS + " [data-chf=foiz]", "")
            pg.wait_for_timeout(500)
            pg.fill(CHS + " [data-chf=foiz]", "15")
            pg.wait_for_timeout(600)                      # 15 % so'rovi ketdi (sekin)
            pg.fill(CHS + " [data-chf=foiz]", "25")
            _y = kut(pg, f"(document.querySelector(\"{CHS} [data-chnatija]\").innerText || '').replace(/\\s/g, '').indexOf('148800') >= 0")
            pg.wait_for_timeout(2200)                     # sekin (eski) javob ham keldi
            _nt5 = matn(pg, CHS + " [data-chnatija]").replace("\u00a0", "").replace(" ", "")
            check("U5b sekin tarmoq: 15 % ko'rish javobi kech keldi — ekranda oxirgi (25 %) natija qoldi (komplekt 198 000 → 148 800)",
                  _y and "148800" in _nt5 and "168600" not in _nt5, _nt5[:300])
            pg.evaluate("() => { window.fetch = window.__asl_fetch; }")
            _kar = f"{CHS} [data-chyangi='15000']"
            pg.fill(_kar, "12000")
            pg.press(_kar, "Tab")
            _y = kut(pg, f"document.querySelector(\"{CHS} [data-chf=foiz]\").value === '20'")
            _y2 = kut(pg, f"(document.querySelector(\"{CHS} [data-chnatija]\").innerText || '').replace(/\\s/g, '').indexOf('15000→12000') >= 0")
            check("U5 «Yangi narx» 12 000 (karniz O'rta 15 000) — foiz o'zi 20 bo'ldi, narxlar qayta (15 000 → 12 000)", _y and _y2,
                  (pg.evaluate(f"document.querySelector(\"{CHS} [data-chf=foiz]\").value"), matn(pg, CHS + " [data-chnatija]")[:200]))
            _bas = len(SOROV)
            pg.click(CHS + " [data-chsaqla]")
            _y = kut(pg, f"(document.querySelector(\"[data-chbelgi='{M1}']\").innerText || '').indexOf('20') >= 0")
            check("U6 «Chegirmani saqlash» — bazada 20 %, sarlavhada «−20 %», komplekt blokida «chegirmali (−20 %)», 1 ta PUT; model nomiga "
                  "yozilgan saqlanmagan matn joyida",
                  _y and ch_bazada().get(M1, (None,))[0] == Decimal("20.00") and "−20 %" in matn(pg, f"[data-chbelgi='{M1}']")
                  and "chegirmali (−20 %)" in matn(pg, f"[data-komplekt='{M1}']")
                  and [x for x in SOROV[_bas:] if x[0] == "PUT"] == [("PUT", CH(M1))]
                  and pg.evaluate(f"document.querySelector(\".sk-model[data-model='{M1}'] [data-mf=nom]\").value") == "Klassik (saqlanmagan)",
                  (ch_bazada(), matn(pg, f"[data-chbelgi='{M1}']"), SOROV[_bas:]))
            pg.fill(CHS + " [data-chf=foiz]", "90")
            pg.wait_for_timeout(200)
            pg.click(CHS + " [data-chsaqla]")
            _y = kut(pg, f"(document.querySelector(\"[data-chbelgi='{M1}']\").innerText || '').indexOf('tannarxdan past') >= 0")
            check("U7 90 % — saqlandi (to'silmadi), qizil ogohlantirish bloki va sarlavhada «⚠ tannarxdan past», shtorka holati qizil",
                  _y and ch_bazada()[M1][0] == Decimal("90.00") and "tannarxdan" in matn(pg, CHS + " .sk-ch-ogoh")
                  and pg.evaluate(f"!!document.querySelector(\"{CHS} .sht-holat.yomon\")"),
                  (matn(pg, CHS + " .sk-ch-ogoh")[:200], matn(pg, f"[data-chbelgi='{M1}']")))
            pg.fill(CHS + " [data-chf=foiz]", "10")
            pg.uncheck(CHS + " [data-chf=hammasi]")
            pg.wait_for_timeout(200)
            pg.evaluate(f"() => {{ [...document.querySelectorAll(\"{CHS} [data-cho]\")].forEach(x => {{ x.checked = x.dataset.cho === 'Kichik'; }}); }}")
            pg.dispatch_event(CHS + " [data-cho='Kichik']", "change")
            pg.fill(CHS + " [data-chf=tugash]", "2026-11-20")
            pg.click(CHS + " [data-chsaqla]")
            _y = kut(pg, f"(document.querySelector(\"[data-chbelgi='{M1}']\").innerText || '').indexOf('20-noyabrgacha') >= 0")
            _nt = matn(pg, CHS + " [data-chnatija]")
            check("U8 o'lchamlar: faqat «Kichik», 10 %, tugash 20-noyabr — bazada; sarlavhada «−10 % · 20-noyabrgacha»; O'rta qatorlari "
                  "«bu o'lchamga chegirma yo'q»", _y and ch_bazada()[M1] == (Decimal("10.00"), ["Kichik"], "2026-11-20")
                  and "bu o'lchamga chegirma yo'q" in _nt and "tannarxdan past" not in matn(pg, f"[data-chbelgi='{M1}']"),
                  (ch_bazada().get(M1), _nt[:200]))
            # narx katagi o'zgardi — ochiq chegirma bloki yangilanadi
            _nk = f"tr[data-detal='{DID[('karniz', 'Kichik')]}'] [data-df=narx]"
            pg.fill(_nk, "11000")
            pg.press(_nk, "Tab")
            _y = kut(pg, f"(document.querySelector(\"{CHS} [data-chnatija]\").innerText || '').replace(/\\s/g, '').indexOf('11000→9900') >= 0", 10000)
            check("U9 narx katagi (karniz Kichik 9 500 → 11 000) saqlangach — ochiq chegirma blokida yangi narx (11 000 → 9 900)", _y,
                  matn(pg, CHS + " [data-chnatija]")[:300])
            pg.click(CHS + " [data-chochir]")
            pg.click("#ccModalOk")
            _y = kut(pg, f"(document.querySelector(\"[data-chbelgi='{M1}']\").innerText || '').trim() === ''")
            _y2 = kut(pg, f"!document.querySelector(\"{CHS} [data-chochir]\") && (document.querySelector(\"{CHS} [data-chnatija]\").innerText || '').indexOf('→') < 0 && document.querySelectorAll(\"{CHS} [data-chnatija] tbody tr\").length >= 16")
            check("U10 «Chegirmani o'chirish» (tasdiq oynasi) — bazada yo'q, belgi yo'q, forma bo'sh, jadval — asl narxlar",
                  _y and _y2 and M1 not in ch_bazada() and pg.evaluate(f"document.querySelector(\"{CHS} [data-chf=foiz]\").value") == "",
                  (ch_bazada(), matn(pg, CHS + " [data-chnatija]")[:200]))
            # review234 P2: shtorka YOPIQ — narx katagi o'zgarib chegirmali narx tannarxdan past tushdi → sarlavhada «⚠» darhol
            CA.put(CH(M1), json={"foiz": 70})

            def _yangi_sahifa():
                pg.reload()
                kut(pg, "document.querySelectorAll('#skBolimlar .sk-bolim').length > 3")
                pg.evaluate("() => { const b = [...document.querySelectorAll('#skBolimlar .sk-bolim')].find(x => x.innerText.includes('Rom va eshik')); b && b.click(); }")
                kut(pg, f"!!document.querySelector('[data-och=\"{M1}\"]')")
                pg.evaluate(f"() => {{ const m = document.querySelector('.sk-model[data-model=\"{M1}\"]'); if (m && !m.classList.contains('ochiq')) m.querySelector('[data-och]').click(); }}")
                kut(pg, f"!!document.querySelector(\"{CHS} details.sht\")")
            _yangi_sahifa()
            pg.evaluate(f"() => {{ const d = document.querySelector(\"{CHS} details.sht\"); if (d && d.open) d.querySelector('summary').click(); }}")
            _b0 = matn(pg, f"[data-chbelgi='{M1}']")
            _nk2 = f"tr[data-detal='{DID[('karniz', 'O' + chr(39) + 'rta')]}'] [data-df=narx]"
            pg.fill(_nk2, "10000")
            pg.press(_nk2, "Tab")
            _y = kut(pg, f"(document.querySelector(\"[data-chbelgi='{M1}']\").innerText || '').indexOf('tannarxdan past') >= 0", 10000)
            check("U9b shtorka yopiq: karniz O'rta 15 000 → 10 000 (70 % → 3 000 < tannarx 3 203) — sarlavhada «⚠ tannarxdan past» darhol, "
                  "shtorka muammo bilan o'zi ochildi (review234 P2)", _y and "tannarxdan" not in _b0
                  and pg.evaluate(f"document.querySelector(\"{CHS} details.sht\").open"),
                  (_b0, matn(pg, f"[data-chbelgi='{M1}']")))
            pg.fill(_nk2, "15000")
            pg.press(_nk2, "Tab")
            kut(pg, f"(document.querySelector(\"[data-chbelgi='{M1}']\").innerText || '').indexOf('tannarxdan past') < 0", 10000)
            # review234 P1: muddati tugagan chegirma — formada eski sana; o'zgartirib saqlansa — jimgina muddatsiz bo'lmaydi (400, o'zgarmadi)
            CA.put(CH(M1), json={"foiz": 10, "tugash": "2026-11-04"})
            _SoxtaVaqt.t = datetime(2026, 11, 5, 7, 0)
            _yangi_sahifa()
            pg.evaluate(f"() => {{ const d = document.querySelector(\"{CHS} details.sht\"); if (d && !d.open) d.querySelector('summary').click(); }}")
            kut(pg, f"document.querySelectorAll(\"{CHS} [data-chnatija] tbody tr\").length >= 16")
            _sana = pg.evaluate(f"document.querySelector(\"{CHS} [data-chf=tugash]\").value")
            pg.fill(CHS + " [data-chf=foiz]", "12")
            pg.wait_for_timeout(500)
            pg.click(CHS + " [data-chsaqla]")
            pg.wait_for_timeout(800)
            check("U9c muddati tugagan: belgi «chegirma tugagan», formada eski sana (2026-11-04); foiz 12 bilan saqlash — rad etildi, bazada "
                  "o'zgarmadi (jimgina muddatsiz bo'lmadi, review234 P1)", _sana == "2026-11-04"
                  and "tugagan" in matn(pg, f"[data-chbelgi='{M1}']") and ch_bazada()[M1] == (Decimal("10.00"), None, "2026-11-04"),
                  (_sana, ch_bazada().get(M1), matn(pg, f"[data-chbelgi='{M1}']")))
            _SoxtaVaqt.t = datetime(2026, 11, 3, 7, 0)
            CA.put(CH(M1), json={"foiz": 20})
            _yangi_sahifa()
            pg.evaluate(f"() => {{ const d = document.querySelector(\"{CHS} details.sht\"); if (d && !d.open) d.querySelector('summary').click(); }}")
            kut(pg, f"document.querySelectorAll(\"{CHS} [data-chnatija] tbody tr\").length >= 16")
            pg.fill(CHS + " [data-chf=foiz]", "20")
            kut(pg, f"(document.querySelector(\"{CHS} [data-chnatija]\").innerText || '').indexOf('→') >= 0")
            for _w in (375, 320):
                pg.set_viewport_size({"width": _w, "height": 800})
                pg.wait_for_timeout(300)
                _ust = pg.evaluate("""() => { const bad = []; document.querySelectorAll('.sk-kjadval td').forEach(td => {
                    const r = td.getBoundingClientRect(); if (!r.width) return;
                    const k = [...td.querySelectorAll('.sk-kn')].map(x => x.getBoundingClientRect()).filter(x => x.width);
                    for (let i = 1; i < k.length; i++) if (k[i].top < k[i - 1].bottom - 1) bad.push(td.innerText.slice(0, 40));
                    k.forEach(x => { if (x.right > r.right + 1) bad.push('chiqdi: ' + td.innerText.slice(0, 40)); }); }); return bad; }""")
                check(f"U11b telefon ({_w} px): komplekt va chegirma jadvallari kataklarida qatorlar USTMA-UST (yonma-yon siqilmagan), katakdan "
                      "chiqmaydi (review234 O3)", lambda: not _ust and pg.evaluate("document.querySelectorAll('.sk-kjadval .sk-ch-kn').length") > 0,
                      _ust[:5])
                check(f"U11 telefon ({_w} px) — sahifa gorizontal toshmaydi, chegirma jadvali va formasi sig'adi",
                      not pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
                      and pg.evaluate(f"[...document.querySelectorAll(\"{CHS} table, {CHS} .sk-forma, {CHS} input\")].every(t => t.getBoundingClientRect().right <= window.innerWidth + 1)"),
                      pg.evaluate(f"[document.documentElement.scrollWidth, window.innerWidth, [...document.querySelectorAll(\"{CHS} table\")].map(t => t.getBoundingClientRect().right)]"))
            ctx.close()
            CA.delete(API + f"/detallar/{_xss}")
            check("U12 JS xatosi yo'q", not JS_XATO, JS_XATO[:3])
            check("U13 konsolda xato yo'q (U9c dagi ataylab rad etilgan 400 dan tashqari)", not [k for k in KONSOL if "400" not in k], KONSOL[:3])
        except Exception as e:             # noqa: BLE001
            import traceback
            print("".join(traceback.format_exc().splitlines(True)[-12:])[:3000])
            check("U* brauzer sinovi qulamadi", False, f"{type(e).__name__}: {e}")
    if br:
        br.close()
    if pw_ctx:
        pw_ctx.stop()
    if server:
        server.should_exit = True

if _asl_dt is not None:
    crud._dt233 = _asl_dt
print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
