#!/usr/bin/env python3
"""
test_hodim_avans.py — kech107 darvozasi (5-bo'lim 10-band, "hodim paneli"): hodim o'zi yozadigan "avans oldim" so'rovi
(`POST /api/hodim/advance-request`, `/hodim` paneli — telefon + PIN) — QAT'IY tekshiruv va takror himoyasi.

NIMA UCHUN (asl kod staging `061e082` = zip 101 da O'LCHANGAN — `work/probe107h.py`, SQLite va PG)
------------------------------------------------------------------------------------------------
  * Bu yo'l 17c qat'iy tekshiruvidan CHETDA qolgan edi (admin yo'li `POST /api/employees/{id}/advance` —
    `crud._clean_avans` bilan): `amount: float` faqat `<= 0` bilan rad etilardi. SQLite: `inf`, `1e20`, `1e13`
    SAQLANDI, `nan` — 500; PG: `nan` SAQLANDI (Numeric NaN ni qabul qiladi), `inf` / `1e20` / `1e13` — 500.
    `0.001` → 0.00 lik so'rov, sana 0001-01-01 / 9999-12-31, 200 000 belgili izoh — hammasi saqlandi.
  * Admin TASDIQLASA yozuv `EmployeeAdvance` ga o'tadi: oylik hisobot (`/api/finance/report`), hodim avanslari va
    kutilayotganlar ro'yxati (va hodimning o'z ro'yxati) — 500 (ikkala bazada).
  * Bir xil so'rov ikki marta — ikki so'rov (admin ikkalasini tasdiqlasa — avans ikki marta).

TUZATISH: marshrut summani MATN sifatida oladi va `crud._clean_avans` bilan tekshiradi (summa musbat, chekli, sig'im
ichida, kamida 1 tiyin; sana MAJBURIY, 2000–2100; izoh chegarasi) — xato 400, sababi hodimga tushunarli nomlar bilan
(Summa / Sana / Izoh); `crud.create_advance_request` — bir xil (hodim, summa, sana) KUTILAYOTGAN so'rov
`PUL_TAKROR_SONIYA` ichida bo'lsa o'sha so'rov qaytadi, PG da hodim bo'yicha qulf (`_pul_qulfi(107, …)`).

BO'LIMLAR: A — kirish tekshiruvi; B — takror himoyasi; C — admin tasdig'i va hisobotlar; D — PG parallel (faqat PG);
E — statik.

REJIMLAR: SQLite; `PG_URL` berilsa — YANGI PG bazasi.
    python3 tools/test_hodim_avans.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_hodim_avans.py
"""
import os
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hodim_avans_test"
_DB = os.path.join(tempfile.gettempdir(), "hodim_avans_test.db")

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
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402

from database import SessionLocal, tashkent_date   # noqa: E402
from models import UserRole, AdvanceRequest, EmployeeAdvance   # noqa: E402
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


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


def sorovlar(emp=None):
    s = SessionLocal()
    try:
        q = s.query(AdvanceRequest)
        if emp:
            q = q.filter(AdvanceRequest.employee_id == emp)
        return [(r.id, str(r.amount), r.requested_date.strftime("%Y-%m-%d") if r.requested_date else None,
                 r.status.value if r.status else None) for r in q.order_by(AdvanceRequest.id).all()]
    finally:
        s.close()


s = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "ha_admin", "Parol123!", UserRole.ADMIN, "HA admin", company_id=1)
s.commit()
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
req(A, "post", "/login", data={"username": "ha_admin", "password": "Parol123!"}, follow_redirects=False)


def hodim(nom, tel, pin):
    r = req(A, "post", "/api/employees", json={"name": nom, "pay_type": "fixed", "fixed_amount": 3_000_000})
    eid = (js(r) or {}).get("id") if r.status_code == 200 else None
    req(A, "post", f"/api/employees/{eid}/set-login", data={"phone": tel, "pin": pin})
    h = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(h, "post", "/hodim/login", data={"phone": tel, "pin": pin, "korxona": ""}, follow_redirects=False)
    # kech133 (zip 159, MOSLANDI): panel endi FAQAT admin ruxsat bergan telefondan va hodimning O'Z PIN i bilan ochiladi (egasi
    # qarorlari 09.10). Bu sinov avans so'rovini sinaydi — admin telefonga ruxsat beradi, hodim o'z PIN ini qo'yadi (asl kodda bu
    # yo'llar yo'q — 404, sinov eskisidek ishlaydi).
    _q = js(req(A, "get", "/api/admin/qurilma-sorovlari"))
    _k = next((x.get("kalit") for x in (_q if isinstance(_q, list) else []) if x.get("employee_id") == eid), None)
    if _k:
        req(A, "post", f"/api/employees/{eid}/qurilma/ruxsat", json={"kalit": _k})
        req(h, "post", "/api/hodim/pin", json={"yangi": "4826", "takror": "4826"})
    return eid, h, r.status_code


E1, H1, _st = hodim("HA Hodim 1", "+998907770011", "4321")
check("0 hodim paneliga kirish (302 → /hodim)", E1 and _st == 302, _st)
BUGUN = tashkent_date()
SANA = BUGUN.strftime("%Y-%m-%d")


def yubor(h, summa, sana=SANA, izoh="HA"):
    return req(h, "post", "/api/hodim/advance-request", data={"amount": summa, "requested_date": sana, "notes": izoh})


# ══════════════════════════════════════════════════════════════
section("A — kirish tekshiruvi (admin yo'li bilan BIR qoida)")
crud.PUL_TAKROR_SONIYA = 0          # takror himoyasi bu bo'limda aralashmasin
r = yubor(H1, "500000", izoh="HA oddiy")
check("A0 oddiy 500 000 — 200", r.status_code == 200 and (js(r) or {}).get("id"), (r.status_code, r.text[:160]))
_n0 = len(sorovlar())
_natija = {}
for nom, summa, sana, izoh in (("nan", "nan", SANA, "x"), ("inf", "inf", SANA, "x"), ("-inf", "-inf", SANA, "x"),
                               ("1e20", "1e20", SANA, "x"), ("1e13", "10000000000000", SANA, "x"),
                               ("0.001", "0.001", SANA, "x"), ("0", "0", SANA, "x"), ("manfiy", "-5", SANA, "x"),
                               ("matn", "abc", SANA, "x"), ("sana 0001", "1000", "0001-01-01", "x"),
                               ("sana 9999", "1000", "9999-12-31", "x"), ("sana 13-oy", "1000", "2026-13-45", "x"),
                               ("sana bo'sh", "1000", "", "x"), ("summa bo'sh", "", SANA, "x"),
                               ("izoh 200 000", "1000", SANA, "x" * 200000)):
    r = yubor(H1, summa, sana, izoh)
    _natija[nom] = (r.status_code, str((js(r) or {}).get("detail"))[:70])
check("A1 NaN / ±cheksiz / 1e20 / 1e13 / 0.001 / 0 / manfiy / matn / sana 0001, 9999, 13-oy, bo'sh / summa bo'sh / "
      "200 000 belgili izoh — HAMMASI 400 va sabab MATN (asl: saqlanardi, 500 yoki 422 ro'yxati)",
      all(v[0] == 400 for v in _natija.values()), [(k, v) for k, v in _natija.items() if v[0] != 400])
check("A2 rad etilganlardan HECH BIRI yozilmadi", len(sorovlar()) == _n0, sorovlar())
check("A3 sabab hodimga tushunarli (texnik nom yo'q: 'Summa …', 'Sana …', 'Izoh …')",
      all(("'amount'" not in v[1] and "'adv_date'" not in v[1] and "'notes'" not in v[1]) for v in _natija.values())
      and _natija["1e20"][1].startswith("Summa") and _natija["sana 0001"][1].startswith("Sana")
      and _natija["izoh 200 000"][1].startswith("Izoh"), _natija)
r = yubor(H1, "1 250.50".replace(" ", ""), izoh="HA tiyin")
check("A4 kasrli summa 1250.50 — 200, bazada 1250.50", r.status_code == 200 and any(x[1] == "1250.50" for x in sorovlar()),
      (r.status_code, sorovlar()[-1:]))

# ══════════════════════════════════════════════════════════════
section("B — takror himoyasi")
crud.PUL_TAKROR_SONIYA = 8
_n0 = len(sorovlar())
r1 = yubor(H1, "70000", izoh="HA takror")
r2 = yubor(H1, "70000", izoh="HA takror")
_id1, _id2 = (js(r1) or {}).get("id"), (js(r2) or {}).get("id")
check("B1 bir xil so'rov ikki marta (8 s ichida) — BITTA yozuv, ikkinchisi o'sha id (asl: ikki so'rov)",
      r1.status_code == 200 and r2.status_code == 200 and _id1 and _id1 == _id2 and len(sorovlar()) == _n0 + 1,
      (r1.status_code, r2.status_code, _id1, _id2, len(sorovlar()) - _n0))
r3 = yubor(H1, "70001", izoh="HA takror")
check("B2 boshqa summa — yangi so'rov", r3.status_code == 200 and (js(r3) or {}).get("id") not in (None, _id1), r3.text[:120])
_kecha = (BUGUN.replace(day=1) if BUGUN.day != 1 else BUGUN).strftime("%Y-%m-%d")
r4 = yubor(H1, "70000", sana=_kecha if _kecha != SANA else "2026-01-02", izoh="HA takror")
check("B3 boshqa sana — yangi so'rov", r4.status_code == 200 and (js(r4) or {}).get("id") not in (None, _id1), r4.text[:120])
E2, H2, _ = hodim("HA Hodim 2", "+998907770022", "5678")
r5 = yubor(H2, "70000", izoh="HA takror")
check("B4 BOSHQA hodim, bir xil summa / sana — yangi so'rov (himoya hodim bo'yicha)",
      r5.status_code == 200 and (js(r5) or {}).get("id") not in (None, _id1), r5.text[:120])
req(A, "post", f"/api/admin/advance-requests/{_id1}/confirm")
r6 = yubor(H1, "70000", izoh="HA takror")
check("B5 tasdiqlangan so'rovdan keyin bir xil yangi so'rov — yangi yozuv (faqat KUTILAYOTGANLAR takror hisoblanadi)",
      r6.status_code == 200 and (js(r6) or {}).get("id") not in (None, _id1), r6.text[:120])
crud.PUL_TAKROR_SONIYA = 0
r7 = yubor(H1, "70000", izoh="HA takror")
check("B6 oyna tugagach (PUL_TAKROR_SONIYA = 0) — bir xil so'rov yana yoziladi (cheksiz blok emas)",
      r7.status_code == 200 and (js(r7) or {}).get("id") not in (None, (js(r6) or {}).get("id")), r7.text[:120])

# ══════════════════════════════════════════════════════════════
section("C — admin tasdig'i va hisobotlar")
for _rid, _summa, _sana, _holat in sorovlar():
    if _holat == "pending":
        req(A, "post", f"/api/admin/advance-requests/{_rid}/confirm")
r = req(A, "get", f"/api/finance/report?year={BUGUN.year}&month={BUGUN.month}")
check("C1 oylik hisobot 200 (asl: tasdiqlangan inf / NaN avans — 500)", r.status_code == 200, (r.status_code, r.text[:160]))
r = req(A, "get", f"/api/employees/{E1}/advances?year={BUGUN.year}&month={BUGUN.month}")
check("C2 hodim avanslari 200, jami chekli", r.status_code == 200 and isinstance((js(r) or {}).get("total"), (int, float)),
      (r.status_code, r.text[:160]))
r = req(A, "get", "/api/admin/pending-advance-requests")
check("C3 kutilayotganlar ro'yxati 200", r.status_code == 200, (r.status_code, r.text[:160]))
r = req(H1, "get", "/api/hodim/my-requests")
check("C4 hodimning o'z so'rovlari 200", r.status_code == 200, (r.status_code, r.text[:160]))
s = SessionLocal()
try:
    _av = [float(a.amount) for a in s.query(EmployeeAdvance).all()]
finally:
    s.close()
check("C5 hamma avans chekli, musbat va sig'im ichida", _av and all(0 < x < 1e10 for x in _av), _av)

# ══════════════════════════════════════════════════════════════
section("D — PG: parallel ikki bir xil so'rov (haqiqiy qulf)")
if PG_URL:
    crud.PUL_TAKROR_SONIYA = 8
    _bar = threading.Barrier(2)
    _nat = []

    def _ish():
        _s = SessionLocal()
        try:
            _bar.wait(timeout=10)
            _r = crud.create_advance_request(_s, E2, 33333.0, BUGUN_DT, "HA parallel")
            _nat.append(_r.id)
        except Exception as e:             # noqa: BLE001
            _nat.append(f"{type(e).__name__}: {e}")
        finally:
            _s.close()
    from datetime import datetime as _dt
    BUGUN_DT = _dt(BUGUN.year, BUGUN.month, BUGUN.day)
    _n0 = len(sorovlar(E2))
    _t = [threading.Thread(target=_ish) for _ in range(2)]
    for t in _t:
        t.start()
    for t in _t:
        t.join(30)
    check("D1 ikki parallel bir xil so'rov — BITTA yozuv, ikkalasi bir id", len(sorovlar(E2)) == _n0 + 1 and
          len(set(_nat)) == 1, (_nat, len(sorovlar(E2)) - _n0))
else:
    print("  (SQLite — o'tkazildi: haqiqiy parallellik yo'q)")

# ══════════════════════════════════════════════════════════════
section("E — statik")
_m = fayl("main.py")
_i = _m.find('@app.post("/api/hodim/advance-request")')
_fn = _m[_i:_m.find("\n@app.", _i + 10)] if _i >= 0 else ""
check("E1 marshrut summani MATN sifatida oladi va `crud._clean_avans` bilan tekshiradi",
      "amount: Optional[str] = Form(None)" in _fn and "crud._clean_avans(amount, notes, requested_date)" in _fn
      and "company_id=emp.company_id" in _fn, _fn[:200])
check("E2 sana majburiy (bo'sh — 400)", 'toza["adv_date"] is None' in _fn, "")
_c = fayl("crud.py")
_i = _c.find("def create_advance_request(")
_fn = _c[_i:_c.find("\ndef ", _i + 10)] if _i >= 0 else ""
check("E3 `create_advance_request` — qulf (`_pul_qulfi(db, 107, …)`) va takror tekshiruvi (`PUL_TAKROR_SONIYA`)",
      tartibda(_fn, "_pul_qulfi(db, 107, employee_id)", "AdvanceRequestStatus.PENDING", "PUL_TAKROR_SONIYA", "return _oldingi"), "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   -", f)

try:
    from database import engine as _eng
    _eng.dispose()
except Exception:                          # noqa: BLE001
    pass
if PG_URL:
    try:
        from sqlalchemy import create_engine as _ce2, text as _tx2
        _adm = _ce2(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
                    isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c2:
            _c2.execute(_tx2(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass
else:
    try:
        os.remove(_DB)
    except OSError:
        pass
sys.exit(1 if FAIL else 0)
