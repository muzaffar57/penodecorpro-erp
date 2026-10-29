#!/usr/bin/env python3
"""
test_pul_oqimi223.py — kech160 (zip 223 «Pul oqimi — haqiqiy pul berilgan kunda»; egasi 29.10 «ZIP 223 ni boshlash (Tavsiya)», egasining
G1-03 qarori kech114 «Pul oqimi — haqiqiy pul»).

NIMA UCHUN KERAK (O'LCHANGAN — `work/k223/probe223.py`, zip 222b kodi; SQLite = PG AYNAN)
  «Pul oqimi» (`services._kassa_qismlari` → `get_pul_oqimi`) hodimga avans / oylikni va xarajatni faqat SANA bo'yicha olardi, hisoblar
  qoldig'i esa `pul_vaqti` (pul HAQIQATDA berilgan payt) bo'yicha. Natija: oyning 29–31-kunida «Oylikni yopish» (sana — 28-kun) pul
  oqimida 28-kunda, hisob qoldig'i bugun (test_hisoblar210 I1 — 29.10 da yiqildi); o'tgan oy oyligini yopish va Qarzdorlar o'tgan oy
  majburiyati (`pul_hozir`) — o'tgan (yopilgan) oy pul oqimiga orqaga tushardi. Qoldiqdan keyingi 8 kunda hisoblar ≠ pul oqimi.
QOIDA: davr sharti — `services._pul_vaqti_sharti` (pul oqimi va hisoblar qoldig'i — BITTA shart): `pul_vaqti` bor — o'sha payt, yo'q — sana.
  Butun davr (kassa balansi) va yozuv SANASI (oylik hisobot, hodim oyligi — hisobot oyi) O'ZGARMAYDI.
BO'LIMLAR
  S — manba (yagona shart, ikkala joy; `close_employee_debt` sana qoidasi o'zgarmagan).
  J — joriy oy: 29 / 30 / 31-kun (shu jumladan Toshkent 23:30 va 00:20 — UTC kuni boshqa) «oylikni yopish» — o'sha kun pul oqimida, 28-kunda
      yo'q, hisob o'sha kun o'zgaradi; 27-kun va fevral 28-kun — nazorat.
  O — o'tgan oy: noyabrda oktabr oyligini yopish va Qarzdorlar `pul_hozir` xarajati — noyabr pul oqimida, oktabrda yo'q; oktabr hodim
      oyligi va oylik hisobot «jami xarajat» (hisobot oyi) baribir o'zgaradi; 01.01 00:20 (UTC hali 31.12) dekabr oyligi — 01.01 da; oddiy (pul_hozirsiz) orqa sanali xarajat — sanasi bo'yicha (nazorat).
  I — izchillik (oracle): qoldiqdan keyingi HAR kun Σ hisoblar harakati (o'tkazishsiz) = o'sha kun pul oqimi; har oy Σ kunlar = oy pul
      oqimi; butun davr: kassa (`eski_balans`) = hisoblar jami − boshlang'ich (o'zgarmaydi).
  X — korxonalar: B korxonasining pul oqimi A ning yopishlaridan o'zgarmaydi.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL.
Vaqt — `time_machine` (sinov «bugun» ga bog'liq emas). Asl kodga (zip 222b) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_pul_oqimi223.py
"""
import os
import io
import sys
import inspect
import datetime
import tempfile
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import time_machine                                    # noqa: E402

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "puloqimi223_test" + (os.environ.get("PG_BAZA_QOSHIMCHA") or "")
_T = tempfile.mkdtemp(prefix="k223_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k223.db')}"
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


TZ = datetime.timezone(datetime.timedelta(hours=5))


def tosh(y, m, d, h=10, mi=0):
    """Toshkent vaqti (UTC+5)."""
    return datetime.datetime(y, m, d, h, mi, tzinfo=TZ)


_tm = time_machine.travel(tosh(2026, 10, 20, 9), tick=True)
_tm.start()
with contextlib.redirect_stdout(io.StringIO()):
    import main                                        # noqa: E402
    import auth                                        # noqa: E402
    import services                                    # noqa: E402
from database import SessionLocal                      # noqa: E402
from models import UserRole, Employee, PayType, EmployeeAdvance   # noqa: E402
from production_models import Company                 # noqa: E402
from fastapi.testclient import TestClient              # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="K223 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k223_a", PAROL, UserRole.ADMIN, "K223 Admin", company_id=1)
    auth.create_user(s, "k223_b", PAROL, UserRole.ADMIN, "K223 B Admin", company_id=2)
E1 = Employee(company_id=1, name="K223 Hodim", position="Kesuvchi", pay_type=PayType.FIXED, fixed_amount=5_000_000, is_active=True,
              hire_date=datetime.datetime(2026, 1, 1))
s.add(E1)
s.commit()
EID = E1.id
s.close()


def kirish(u="k223_a"):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": u, "password": PAROL}, follow_redirects=False)
    return c


def js(r):
    try:
        return r.json()
    except Exception:                                  # noqa: BLE001
        return {"_matn": r.text[:300], "_kod": r.status_code}


A = kirish()
HID = {h["turi"]: h["id"] for h in js(A.get("/api/finance/hisoblar")).get("hisoblar") or []}
_rq = A.post("/api/finance/hisoblar/qoldiq", json={"qoldiqlar": [{"hisob_id": HID.get("naqd", 0), "summa": 10_000_000},
                                                                 {"hisob_id": HID.get("bank", 0), "summa": 20_000_000},
                                                                 {"hisob_id": HID.get("karta", 0), "summa": 0}]})
BOSHLANG = 30_000_000
_tm.stop()


def bal(c):
    return {h["turi"]: h["balans"] for h in (js(c.get("/api/finance/hisoblar")).get("hisoblar") or [])}


def _qator(j, kalit):
    return next((x["summa"] for x in j.get("chiqim_qatorlar") or [] if x["kalit"] == kalit), None)


def oqim(c, **p):
    j = js(c.get("/api/finance/pul-oqimi", params=p))
    return {"balans": j.get("balans"), "hod": _qator(j, "hodimlarga"), "xar": _qator(j, "xarajatlar")}


def kun(c, d):
    return oqim(c, sana=d.isoformat())


def oy(c, y, m):
    return oqim(c, year=y, month=m)


def farq(b0, b1):
    return {k: round((b1.get(k) or 0) - (b0.get(k) or 0), 2) for k in ("naqd", "bank", "karta") if round((b1.get(k) or 0) - (b0.get(k) or 0), 2)}


def yop(c, y, m, summa, hisob="bank"):
    return c.post(f"/api/obligations/employee/{EID}/close", params={"year": y, "month": m, "amount": str(summa), "hisob": hisob,
                                                                     "confirm_excess": "true"})


def xarajat(c, sana_iso, summa, pul_hozir):
    t = {"category": "boshqa", "amount": summa, "notes": "K223", "hisob": "naqd", "date": sana_iso}
    if pul_hozir:
        t["pul_hozir"] = True
    return c.post("/api/finance/transactions", json=t)


def oxirgi_avans():
    _s = SessionLocal()
    try:
        ea = _s.query(EmployeeAdvance).filter(EmployeeAdvance.employee_id == EID).order_by(EmployeeAdvance.id.desc()).first()
        return (ea.date, getattr(ea, "pul_vaqti", None)) if ea else (None, None)
    finally:
        _s.close()


def hisobot_xarajat(y, m):
    _s = SessionLocal()
    try:
        return round(float(services.get_monthly_report(_s, y, m, company_id=1).get("jami_xarajat") or 0), 2)
    finally:
        _s.close()


def hodim_qolgan(y, m):
    _s = SessionLocal()
    try:
        return round(services.hodim_oy_qoldigi(_s, EID, 1, y, m), 2)
    finally:
        _s.close()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("S0 boshlanish: hisoblar qoldig'i kiritildi (3 hisob) — 200", _rq.status_code == 200, _rq.text[:200])
_sh = getattr(services, "_pul_vaqti_sharti", None)
check("S1 yagona shart `services._pul_vaqti_sharti` bor; butun davr (ikkala chegara None) — None (kassa shartsiz)",
      lambda: callable(_sh) and _sh(EmployeeAdvance.date, EmployeeAdvance.pul_vaqti, None, None) is None)
check("S2 `_kassa_qismlari` (pul oqimi) va `_pul_hisob_harakatlari` (hisoblar qoldig'i) — ikkalasi ham shu shartdan",
      lambda: "_pul_vaqti_sharti" in inspect.getsource(services._kassa_qismlari)
      and "_pul_vaqti_sharti" in inspect.getsource(services._pul_hisob_harakatlari))
check("S3 `close_employee_debt` — yozuv sanasi qoidasi (hisobot oyi, 28-kun) o'zgarmagan, `pul_vaqti` — hozir",
      lambda: "min(28, _bugun_t.day)" in inspect.getsource(services.close_employee_debt)
      and "pul_vaqti=datetime.utcnow()" in inspect.getsource(services.close_employee_debt))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J — joriy oy, 29–31-kun")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
with time_machine.travel(tosh(2026, 10, 25, 11), tick=True):
    c = kirish()
    b0 = bal(c)
    _ra = c.post(f"/api/employees/{EID}/advance", params={"amount": "50000", "notes": "K223 avans", "hisob": "naqd", "confirm_excess": "true"})
    check("J0 oddiy avans 25.10 50 000 (nazorat) — o'sha kun pul oqimida, Naqd −50 000",
          _ra.status_code == 200 and kun(c, datetime.date(2026, 10, 25))["hod"] == 50_000 and farq(b0, bal(c)) == {"naqd": -50_000},
          (_ra.status_code, _ra.text[:200]))

for _no, _vaqt, _summa in (("J1", tosh(2026, 10, 29, 10), 200_000),
                           ("J2", tosh(2026, 10, 30, 23, 30), 150_000),     # Toshkent 23:30 — UTC 18:30, o'sha kun
                           ("J3", tosh(2026, 10, 31, 0, 20), 130_000)):     # Toshkent 00:20 — UTC 30.10 19:20
    with time_machine.travel(_vaqt, tick=True):
        c = kirish()
        _d = _vaqt.date()
        _k28_0 = kun(c, datetime.date(2026, 10, 28))
        _oy0 = oy(c, 2026, 10)
        b0 = bal(c)
        _r = yop(c, 2026, 10, _summa)
        _kb = kun(c, _d)
        _k28 = kun(c, datetime.date(2026, 10, 28))
        _oy1 = oy(c, 2026, 10)
        _sana, _pul = oxirgi_avans()
        check(f"{_no} {_d.strftime('%d.%m')} {_vaqt.strftime('%H:%M')} «oylikni yopish» {_summa:,} — o'sha kun pul oqimi «Hodimlarga» = {_summa:,}, "
              f"28-kun o'zgarmadi, oy +{_summa:,}, Bank −{_summa:,} (o'sha kun); yozuv sanasi 28-kun, `pul_vaqti` bor",
              _r.status_code == 200 and _kb["hod"] == _summa and _kb["balans"] == -_summa and _k28 == _k28_0
              and abs((_oy1["hod"] or 0) - (_oy0["hod"] or 0) - _summa) < 0.01 and farq(b0, bal(c)) == {"bank": -_summa}
              and _sana is not None and (_sana.month, _sana.day) == (10, 28) and _pul is not None,
              (_r.status_code, _r.text[:150], _kb, _k28_0, _k28, _oy0, _oy1, farq(b0, bal(c)), _sana, _pul))

with time_machine.travel(tosh(2026, 10, 27, 12), tick=True):
    c = kirish()
    b0 = bal(c)
    _r = yop(c, 2026, 10, 110_000)
    _sana, _pul = oxirgi_avans()
    check("J4 27.10 «oylikni yopish» 110 000 (nazorat — 28-kundan oldin): sana 27-kun, o'sha kun pul oqimida, Bank −110 000",
          _r.status_code == 200 and kun(c, datetime.date(2026, 10, 27))["hod"] == 110_000 and farq(b0, bal(c)) == {"bank": -110_000}
          and _sana is not None and _sana.day == 27, (_r.status_code, _r.text[:150], _sana))
with time_machine.travel(tosh(2026, 10, 31, 12), tick=True):
    c = kirish()
    check("J5 28.10 pul oqimi — bo'sh (29–31-kunda yopilganlar o'z kunida), 29 / 30 / 31.10 — 200 000 / 150 000 / 130 000",
          kun(c, datetime.date(2026, 10, 28))["hod"] == 0 and [kun(c, datetime.date(2026, 10, x))["hod"] for x in (29, 30, 31)]
          == [200_000, 150_000, 130_000], [kun(c, datetime.date(2026, 10, x)) for x in (28, 29, 30, 31)])

with time_machine.travel(tosh(2027, 2, 28, 10), tick=True):
    c = kirish()
    b0 = bal(c)
    _r = yop(c, 2027, 2, 90_000)
    check("J6 fevral 28.02.2027 «oylikni yopish» 90 000 (nazorat — oyning oxirgi kuni 28) — o'sha kun pul oqimida, Bank −90 000",
          _r.status_code == 200 and kun(c, datetime.date(2027, 2, 28))["hod"] == 90_000 and farq(b0, bal(c)) == {"bank": -90_000},
          (_r.status_code, _r.text[:150]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("O — o'tgan oy oyligi / majburiyati")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
with time_machine.travel(tosh(2026, 11, 2, 10), tick=True):
    c = kirish()
    _oyO0, _oyN0 = oy(c, 2026, 10), oy(c, 2026, 11)
    _q0 = hodim_qolgan(2026, 10)
    b0 = bal(c)
    _r = yop(c, 2026, 10, 120_000)
    _sana, _pul = oxirgi_avans()
    _oyO1, _oyN1 = oy(c, 2026, 10), oy(c, 2026, 11)
    check("O1 02.11 oktabr oyligini yopish 120 000 — NOYABR pul oqimi +120 000 (02.11 kuni ham), OKTABR pul oqimi o'zgarmadi (yopilgan oy "
          "orqaga o'zgarmaydi), Bank −120 000",
          _r.status_code == 200 and _oyO1 == _oyO0 and abs((_oyN1["hod"] or 0) - (_oyN0["hod"] or 0) - 120_000) < 0.01
          and kun(c, datetime.date(2026, 11, 2))["hod"] == 120_000 and farq(b0, bal(c)) == {"bank": -120_000},
          (_r.status_code, _r.text[:150], _oyO0, _oyO1, _oyN0, _oyN1, farq(b0, bal(c))))
    check("O2 yozuv sanasi — oktabr 28-kun (hisobot oyi), oktabr hodim oyligidan qolgani −120 000 (oylik hisobot o'zgarmagan qoida)",
          _sana is not None and (_sana.year, _sana.month, _sana.day) == (2026, 10, 28) and _pul is not None
          and abs((_q0 - hodim_qolgan(2026, 10)) - 120_000) < 0.01, (_sana, _pul, _q0, hodim_qolgan(2026, 10)))

with time_machine.travel(tosh(2026, 11, 3, 10), tick=True):
    c = kirish()
    _oyO0, _oyN0 = oy(c, 2026, 10), oy(c, 2026, 11)
    _hxO0, _hxN0 = hisobot_xarajat(2026, 10), hisobot_xarajat(2026, 11)
    b0 = bal(c)
    _r = xarajat(c, "2026-10-15T00:00:00", 70_000, True)
    _hxO1, _hxN1 = hisobot_xarajat(2026, 10), hisobot_xarajat(2026, 11)
    _oyO1, _oyN1 = oy(c, 2026, 10), oy(c, 2026, 11)
    check("O3 03.11 Qarzdorlar o'tgan oy majburiyati (`pul_hozir`, sana 15.10) 70 000 — noyabr «Xarajatlar» +70 000 (03.11 kuni), "
          "oktabr va 15.10 o'zgarmadi, Naqd −70 000",
          _r.status_code == 200 and _oyO1 == _oyO0 and abs((_oyN1["xar"] or 0) - (_oyN0["xar"] or 0) - 70_000) < 0.01
          and kun(c, datetime.date(2026, 11, 3))["xar"] == 70_000 and kun(c, datetime.date(2026, 10, 15))["xar"] == 0
          and farq(b0, bal(c)) == {"naqd": -70_000}, (_r.status_code, _r.text[:150], _oyO0, _oyO1, _oyN0, _oyN1))
    check("O3b oylik hisobot (hisobot oyi) o'zgarmagan qoida: `pul_hozir` xarajati (sana 15.10) — OKTABR «jami xarajat» +70 000, noyabr — o'zgarmadi",
          abs((_hxO1 - _hxO0) - 70_000) < 0.01 and abs(_hxN1 - _hxN0) < 0.01, (_hxO0, _hxO1, _hxN0, _hxN1))
    _k01, _k03 = kun(c, datetime.date(2026, 11, 1)), kun(c, datetime.date(2026, 11, 3))
    _r = xarajat(c, "2026-11-01T00:00:00", 40_000, False)
    check("O4 orqa sanali oddiy xarajat (pul_hozirsiz, sana 01.11) 40 000 — sanasi bo'yicha (01.11 +40 000, 03.11 o'zgarmadi) — nazorat",
          _r.status_code == 200 and abs((kun(c, datetime.date(2026, 11, 1))["xar"] or 0) - (_k01["xar"] or 0) - 40_000) < 0.01
          and kun(c, datetime.date(2026, 11, 3)) == _k03, (_r.status_code, _k01, kun(c, datetime.date(2026, 11, 1)), _k03))

with time_machine.travel(tosh(2026, 12, 31, 15), tick=True):
    c = kirish()
    _r = yop(c, 2026, 12, 80_000)
    check("O5 31.12 «oylikni yopish» 80 000 — 31.12 pul oqimida, 28.12 da yo'q",
          _r.status_code == 200 and kun(c, datetime.date(2026, 12, 31))["hod"] == 80_000 and kun(c, datetime.date(2026, 12, 28))["hod"] == 0,
          (_r.status_code, _r.text[:150]))

with time_machine.travel(tosh(2027, 1, 1, 0, 20), tick=True):        # Toshkent 01.01 00:20 — UTC hali 31.12
    c = kirish()
    _oyD0 = oy(c, 2026, 12)
    b0 = bal(c)
    _r = yop(c, 2026, 12, 60_000)
    _sana, _pul = oxirgi_avans()
    check("O6 01.01.2027 00:20 (UTC 31.12) dekabr oyligini yopish 60 000 — 01.01 pul oqimida, dekabr (31.12 ham) o'zgarmadi, Bank −60 000; "
          "yozuv sanasi 28.12",
          _r.status_code == 200 and kun(c, datetime.date(2027, 1, 1))["hod"] == 60_000 and oy(c, 2026, 12) == _oyD0
          and kun(c, datetime.date(2026, 12, 31))["hod"] == 80_000 and farq(b0, bal(c)) == {"bank": -60_000}
          and _sana is not None and (_sana.year, _sana.month, _sana.day) == (2026, 12, 28),
          (_r.status_code, _r.text[:150], kun(c, datetime.date(2027, 1, 1)), _oyD0, oy(c, 2026, 12), _sana, _pul))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("I — izchillik (oracle: hisoblar ↔ pul oqimi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
with time_machine.travel(tosh(2027, 3, 10, 12), tick=True):
    c = kirish()
    _s = SessionLocal()
    _hr = services._pul_hisob_harakatlari(_s, 1, datetime.datetime(2026, 10, 19))
    _s.close()
    kun_h = {}
    for r in _hr:
        if r["tur"] == "otkazma":
            continue
        _dd = services._tashkent_date(r["vaqt"])
        kun_h[_dd] = round(kun_h.get(_dd, 0) + r["summa"], 2)
    farqlar, oy_yig, d = [], {}, datetime.date(2026, 10, 20)
    while d <= datetime.date(2027, 3, 10):
        o = kun(c, d)["balans"] or 0
        oy_yig[(d.year, d.month)] = round(oy_yig.get((d.year, d.month), 0) + o, 2)
        if abs(o - kun_h.get(d, 0)) > 0.011:
            farqlar.append((d.isoformat(), o, kun_h.get(d, 0)))
        d += datetime.timedelta(days=1)
    check("I1 qoldiqdan keyingi HAR kun (20.10.2026 … 10.03.2027): Σ hisoblar harakati (o'tkazishsiz) = o'sha kun pul oqimi balansi",
          not farqlar and len(kun_h) >= 10, farqlar[:12])
    _oyf = [(y, m, oy(c, y, m)["balans"], v) for (y, m), v in sorted(oy_yig.items())
            if (y, m) != (2026, 10) and abs((oy(c, y, m)["balans"] or 0) - v) > 0.011]
    check("I2 har oy (noyabr … mart): Σ kunlar = oy pul oqimi", not _oyf, _oyf)
    _cb = js(c.get("/api/finance/cash-balance"))
    _hb = js(c.get("/api/finance/hisoblar"))
    check("I3 butun davr o'zgarmaydi: kassa (`eski_balans`) = hisoblar jami − boshlang'ich (−1 100 000)",
          _cb.get("eski_balans") == -1_100_000 and abs((_hb.get("jami") or 0) - BOSHLANG + 1_100_000) < 0.01,
          (_cb.get("eski_balans"), _hb.get("jami")))
    check("I4 oktabr / noyabr pul oqimi «Hodimlarga»: 640 000 / 120 000, «Xarajatlar»: 0 / 110 000 (avvalgi: 760 000 / 0 va 70 000 / 40 000)",
          (oy(c, 2026, 10)["hod"], oy(c, 2026, 11)["hod"], oy(c, 2026, 10)["xar"], oy(c, 2026, 11)["xar"]) == (640_000, 120_000, 0, 110_000),
          (oy(c, 2026, 10), oy(c, 2026, 11)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("X — korxonalar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
with time_machine.travel(tosh(2027, 3, 10, 12), tick=True):
    B = kirish("k223_b")
    _bo = [oy(B, 2026, 10), oy(B, 2026, 11), kun(B, datetime.date(2026, 10, 29))]
    check("X1 B korxonasi pul oqimi — A ning yopishlari / xarajatlari ko'rinmaydi (oktabr, noyabr, 29.10 — 0)",
          all((x["hod"] or 0) == 0 and (x["xar"] or 0) == 0 for x in _bo), _bo)

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
