#!/usr/bin/env python3
"""
test_pin_qulf263.py — kech199 (zip 263, xavfsizlik REJA 3-band — Fable F3): hodim paneli PIN i — KETMA-KET 10 ta xato → QULF (to'g'ri PIN
bilan ham kirmaydi), admin «🔑 Kirish» dan yangi PIN bersa ochiladi; 5-xatoda korxona chatiga ogohlantirish.

NIMA UCHUN KERAK
----------------
  O'LCHANGAN (Fable `work/k263/fable/probes/pin_probe.py`, Opus P3): turli IP lardan 15 daqiqada 30 ta PIN qabul qilinardi (kuniga ≈ 2 900)
  — 4 xonali PIN ~3,5 kunda topiladi; korxona korxona kodini (QR varag'i) va hodim telefonini bilish kifoya.

BO'LIMLAR
  P — 4 xato — xabar yo'q; 5-xato — korxona chatiga ogohlantirish (bir marta); 10-xato — qulf + «qulflandi» xabari; qulfda to'g'ri PIN —
      rad (sessiya yo'q), urinish jurnalda; admin yangi PIN — ochildi, yangi PIN bilan kiradi; to'g'ri kirish sanoqni 0 qiladi (9 + 9
      ≠ qulf); o'z PIN ini almashtirish ham 0; boshqa korxonadagi o'sha raqam — tegilmaydi; /api/employees da `pin_qulflangan`;
  S — shablon: hodimlar qatorida va «🔑 Kirish» oynasida qulf belgisi.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 263 1-qism, 894aa9b) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_pin_qulf263.py
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "pin_qulf263_test"
_DB = os.path.join(tempfile.gettempdir(), "pin_qulf263_test.db")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

import html as _html                               # noqa: E402
import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Employee, LoginHistory   # noqa: E402
from production_models import Company             # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
YANGI = hasattr(crud, "hodim_pin_xato")


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


XABAR = []
main._send_telegram = lambda text, company_id=None: XABAR.append((text, company_id))
TEL = "+998 90 263 11 22"
PIN, PIN2 = "4826", "7391"

s = SessionLocal()
c1 = s.query(Company).filter(Company.id == 1).first()
if not c1.code:
    c1.code = "BOSH-P263"
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ikkinchi P", code="IKKI-P263"))
s.commit()
KOD1, KOD2 = s.query(Company).get(1).code, "IKKI-P263"
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "p263_admin", "Parol263!xyz", UserRole.ADMIN, "Admin", company_id=1)
s.commit()
e1 = Employee(company_id=1, name="Hodim P263", position="usta", is_active=True)
e2 = Employee(company_id=2, name="Boshqa korxona hodimi", position="usta", is_active=True)
s.add_all([e1, e2])
s.commit()
E1, E2 = e1.id, e2.id
crud.set_employee_login(s, E1, TEL, PIN)
crud.set_employee_login(s, E2, TEL, PIN)
s.close()
_IP = {"n": 1}


def hodim(kod=KOD1, pin=PIN):
    _IP["n"] += 1
    ip = f"100.64.{_IP['n'] // 250}.{_IP['n'] % 250 + 1}"          # har urinish — boshqa IP (hujumchi)
    try:
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False, follow_redirects=False,
                       client=(ip, 50000))
    except TypeError:
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False, follow_redirects=False)
    r = c.post("/hodim/login", data={"phone": TEL, "pin": pin, "korxona": kod})
    return r, c


def holat(eid):
    db = SessionLocal()
    try:
        e = db.query(Employee).filter(Employee.id == eid).first()
        return int(getattr(e, "pin_xato_soni", 0) or 0), bool(getattr(e, "pin_qulflangan", False))
    finally:
        db.close()


def kirdimi(r):
    return r.status_code == 302 and r.headers.get("location") == "/hodim"


def tarix_tozala():
    db = SessionLocal()
    db.query(LoginHistory).delete(synchronize_session=False)
    db.commit()
    db.close()


section("P — ketma-ket xatolar, qulf, ochish")
XABAR.clear()
for _ in range(4):
    hodim(pin="0000")
check("P1 4 ta xato — sanoq 4, xabar yo'q", lambda: holat(E1) == (4, False) and XABAR == [], (holat(E1), XABAR))
hodim(pin="0000")
check("P2 5-xato — korxona chatiga ogohlantirish (bir marta, 1-korxona)",
      lambda: len(XABAR) == 1 and XABAR[0][1] == 1 and "5 marta" in XABAR[0][0] and "Hodim P263" in XABAR[0][0], XABAR)
for _ in range(5):
    tarix_tozala()
    hodim(pin="0000")
check("P3 10-xato — QULF, «qulflandi» xabari", lambda: holat(E1) == (10, True) and len(XABAR) == 2 and "qulflandi" in XABAR[1][0],
      (holat(E1), XABAR))
tarix_tozala()
r, c = hodim(pin=PIN)
check("P4 qulfda TO'G'RI PIN — rad, «qulflangan», sessiya yo'q",
      lambda: not kirdimi(r) and "qulflangan" in _html.unescape(r.text) and not c.cookies.get("emp_session_token"), (r.status_code,))
db = SessionLocal()
n_lh = db.query(LoginHistory).filter(LoginHistory.success == False).count()   # noqa: E712
db.close()
check("P5 … urinish jurnalda (cheklov hisobida)", lambda: n_lh >= 1, n_lh)
r, c = hodim(kod=KOD2, pin=PIN)
check("P6 boshqa korxonadagi o'sha raqam — tegilmagan (kiradi), sanog'i 0",
      lambda: kirdimi(r) and holat(E2)[1] is False, (r.status_code, holat(E2)))
X0 = len(XABAR)
for _ in range(3):
    hodim(pin="0000")
check("P7 qulfda xato — sanoq oshmaydi, xabar takrorlanmaydi", lambda: holat(E1) == (10, True) and len(XABAR) == X0, (holat(E1), XABAR[X0:]))
# kech200 (zip 263, review263 R6): «qulflangan» — faqat TO'G'RI PIN bilan; noto'g'ri PIN — yo'q raqam bilan AYNAN bir xil matn
tarix_tozala()
r_q, _ = hodim(pin="0000")
_yoq_tel = TEL
TEL = "+998 90 999 00 77"                                  # bu korxonada yo'q raqam
r_y, _ = hodim(pin="0000")
TEL = _yoq_tel


def _xato_matni(r):
    import re as _re
    m = _re.search(r'class="[^"]*\b(?:error|xato)[^"]*"[^>]*>(.*?)</', r.text, _re.S)
    return _html.unescape(m.group(1)).strip() if m else _html.unescape(r.text)


check("P7b qulfda NOTO'G'RI PIN — «qulflangan» YO'Q, «Telefon yoki PIN noto'g'ri!» (yo'q raqam javobi bilan bir xil — raqam borligi oshkor emas)",
      lambda: not kirdimi(r_q) and "qulflangan" not in _html.unescape(r_q.text)
      and "Telefon yoki PIN noto'g'ri!" in _html.unescape(r_q.text) and "Telefon yoki PIN noto'g'ri!" in _html.unescape(r_y.text)
      and _html.unescape(r_q.text).replace("90 263 11 22", "X").replace("90 999 00 77", "X")
      == _html.unescape(r_y.text).replace("90 263 11 22", "X").replace("90 999 00 77", "X"),
      (_xato_matni(r_q)[:200], _xato_matni(r_y)[:200]))
tarix_tozala()
r, c = hodim(pin=PIN)
check("P7c qulfda TO'G'RI PIN — hali ham «qulflangan» (hodimning o'zi biladi), qulf ochilmadi",
      lambda: not kirdimi(r) and "qulflangan" in _html.unescape(r.text) and holat(E1) == (10, True), (r.status_code, holat(E1)))
ca = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
ra = ca.post("/login", data={"username": "p263_admin", "password": "Parol263!xyz"})
rj = ca.get("/api/employees")
emp_js = next((e for e in (rj.json() if rj.status_code == 200 else []) if e.get("id") == E1), {}) if rj.status_code == 200 else {}
check("P8 /api/employees — `pin_qulflangan: true`", lambda: emp_js.get("pin_qulflangan") is True, (rj.status_code, emp_js))
r = ca.post(f"/api/employees/{E1}/set-login", data={"phone": TEL, "pin": PIN2})
check("P9 admin yangi PIN berdi — 200, qulf ochildi, sanoq 0", lambda: r.status_code == 200 and holat(E1) == (0, False),
      (r.status_code, r.text[:200], holat(E1)))
tarix_tozala()
r, c = hodim(pin=PIN2)
check("P10 yangi PIN bilan kiradi", lambda: kirdimi(r), (r.status_code, r.text[-200:]))
tarix_tozala()
for _ in range(9):
    hodim(pin="0000")
tarix_tozala()
r, c = hodim(pin=PIN2)
check("P11 9 xato + to'g'ri — kirdi, sanoq 0", lambda: kirdimi(r) and holat(E1) == (0, False), (r.status_code, holat(E1)))
for _ in range(9):
    hodim(pin="0000")
check("P12 yana 9 xato — QULF YO'Q (ketma-ket sanoq)", lambda: holat(E1) == (9, False), holat(E1))
if YANGI:
    db = SessionLocal()
    e = db.query(Employee).filter(Employee.id == E1).first()
    try:
        crud.hodim_pin_almashtir(db, e, "5937", "5937", majburiy=True)
        xx = None
    except Exception as ex:                # noqa: BLE001
        xx = ex
    db.close()
    check("P13 hodim o'z PIN ini almashtirdi — sanoq 0", lambda: xx is None and holat(E1) == (0, False), (xx, holat(E1)))
    check("P14 doimiylar: 5 / 10", lambda: crud.PIN_OGOH_XATO == 5 and crud.PIN_QULF_XATO == 10)

section("S — shablon")
kpi = open(os.path.join(ROOT, "templates", "kpi.html"), encoding="utf-8").read()
check("S1 hodimlar qatori: qulf belgisi (`emp-pin-qulf`, «Kirish qulflangan»)", lambda: "emp-pin-qulf" in kpi and "Kirish qulflangan" in kpi)
check("S2 «🔑 Kirish» oynasi: qulf izohi (`pa-pin-qulf`)", lambda: "pa-pin-qulf" in kpi)

print("\n" + "=" * 70)
print(f"{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
