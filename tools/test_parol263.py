#!/usr/bin/env python3
"""
test_parol263.py — kech199 (zip 263, xavfsizlik REJA 4-band — Fable F9 / Opus): YANGI parol qoidasi — kamida 10 belgi, login yo'q,
bir xil belgilar / faqat raqam / oddiy ketma-ketlik / «oddiy so'z + raqam» (Parol123!, Admin12345, Toshkent2024) — rad.
Mavjud (eski) parollar bilan kirish O'ZGARMAGAN.

BO'LIMLAR
  Q — `crud.parol_zaifligi` jadvali (rad / qabul);
  A — API: /api/users yaratish (qisqa, oddiy, login bilan — 400 o'zbekcha sabab; kuchli — 200), /api/users/{id}/password (admin
      tiklash — login qoidasi ham; o'z paroli), eski 6–9 belgili parol bilan kirish ishlaydi;
  S — users.html matnlari (10 belgi).
REJIMLAR: SQLite (odatiy); `PG_URL`; `TENANT_FILTER=1`. Asl kodga (894aa9b) qarshi YIQILADI (QULAMAYDI).
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "parol263_test"
_DB = os.path.join(tempfile.gettempdir(), "parol263_test.db")
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

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User                  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


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


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


zaif = getattr(crud, "parol_zaifligi", lambda p, login=None: "YO'Q")

section("Q — qoida jadvali")
RAD = [("Parol123!", None, "10 belgi"), ("Qisqa-9ta", None, "10 belgi"), ("Admin12345", None, "oddiy"), ("Qwerty2024!", None, "oddiy"),
       ("Toshkent2024", None, "oddiy"), ("1234567890", None, "raqam"), ("998901234567", None, "raqam"), ("qwertyuiop", None, "ketma"),
       ("abcdefgh12", None, "ketma"), ("asdfghjk!!", None, "ketma"), ("aaaaaaaaaa", None, "bir xil"), ("ababababab", None, "bir xil"),
       ("Ali_karimov01", "ali_karimov", "login"), ("PAROLIM2024", None, "oddiy"), ("Password123", None, "oddiy")]
QABUL = ["Parol-263-Kuchli", "MaxfiyYozuv7", "Uy-raqam-17-qavat", "Yangi-Parol-263!x", "zaxira-paroli-263", "Tog'-Olcha-58!"]
for p, lg, kut in RAD:
    check(f"Q rad: {p!r}" + (f" (login {lg})" if lg else ""), lambda p=p, lg=lg, kut=kut: (zaif(p, lg) or "") and kut in zaif(p, lg),
          zaif(p, lg))
for p in QABUL:
    check(f"Q qabul: {p!r}", lambda p=p: zaif(p) is None, zaif(p))
check("Q _PAROL_MIN = 10", lambda: crud._PAROL_MIN == 10)

section("A — API")
s = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "p263adm", "Eski6b", UserRole.ADMIN, "Admin", company_id=1)        # eski qisqa parol (bazada)
s.commit()
s.close()
c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
r = c.post("/login", data={"username": "p263adm", "password": "Eski6b"})
check("A1 eski 6 belgili parol bilan KIRISH ishlaydi", lambda: c.cookies.get("session_token"), r.status_code)
for p, kut in (("Parol123!", "10 belgi"), ("Admin12345", "oddiy"), ("1234567890", "raqam"), ("yangi_hisob1", "login")):
    r = c.post("/api/users", json={"username": "yangi_hisob1", "password": p, "role": "manager", "full_name": "Yangi"})
    check(f"A2 /api/users parol {p!r} — 400 «{kut}»", lambda r=r, kut=kut: r.status_code == 400 and kut in str(js(r).get("detail", "")),
          (r.status_code, r.text[:200]))
r = c.post("/api/users", json={"username": "yangi_hisob1", "password": "Parol-263-Kuchli", "role": "manager", "full_name": "Yangi"})
check("A3 kuchli parol — yaratildi", lambda: r.status_code == 200, (r.status_code, r.text[:200]))
s = SessionLocal()
uid = s.query(User).filter(User.username == "yangi_hisob1").first()
uid = uid.id if uid else 0
me = s.query(User).filter(User.username == "p263adm").first().id
s.close()
r = c.post(f"/api/users/{uid}/password", json={"new_password": "xx-yangi_hisob1-xx"})
check("A4 admin tiklashi — yangi parolda o'sha hisob logini — 400", lambda: r.status_code == 400 and "login" in js(r).get("detail", ""),
      (r.status_code, r.text[:200]))
r = c.post(f"/api/users/{uid}/password", json={"new_password": "Qwerty2024!"})
check("A5 admin tiklashi — oddiy parol — 400", lambda: r.status_code == 400 and "oddiy" in js(r).get("detail", ""), (r.status_code, r.text[:200]))
r = c.post(f"/api/users/{uid}/password", json={"new_password": "Boshqa-Kuchli-Parol7"})
check("A6 admin tiklashi — kuchli — 200", lambda: r.status_code == 200, (r.status_code, r.text[:200]))
r = c.post(f"/api/users/{me}/password", json={"new_password": "Qisqa-9ta", "current_password": "Eski6b"})
check("A7 o'z paroli — 9 belgi — 400", lambda: r.status_code == 400 and "10 belgi" in js(r).get("detail", ""), (r.status_code, r.text[:200]))
r = c.post(f"/api/users/{me}/password", json={"new_password": "Mening-Yangi-Parolim9", "current_password": "Eski6b"})
check("A8 o'z paroli — kuchli — 200", lambda: r.status_code == 200, (r.status_code, r.text[:200]))

section("B — 13-band: band login matni umumiy, yaratish urinishlari cheklangan")
from production_models import Company as _Co263       # noqa: E402
s = SessionLocal()
if not s.query(_Co263).filter(_Co263.id == 2).first():
    s.add(_Co263(id=2, name="Ikkinchi P", code="IKKI-P263B"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "boshqa_korxona_admini", "Parol123!", UserRole.ADMIN, "B", company_id=2)
s.commit()
s.close()
if hasattr(main, "_BAND_URINISHLAR"):
    main._BAND_URINISHLAR.clear()
r = c.post("/api/users", json={"username": "boshqa_korxona_admini", "password": "Parol-263-Kuchli", "role": "manager"})
check("B1 boshqa korxonadagi band login — 400, matnda «band» / «username» YO'Q (umumiy sabab)",
      lambda: r.status_code == 400 and "ishlatib bo'lmaydi" in js(r).get("detail", "") and "band" not in js(r).get("detail", "").lower()
      and "username" not in js(r).get("detail", "").lower(), (r.status_code, r.text[:200]))
r = c.post("/api/users", json={"username": "admin", "password": "Parol-263-Kuchli", "role": "manager"})
check("B2 platforma egasining «admin» i — xuddi shu umumiy matn", lambda: r.status_code == 400 and "ishlatib bo'lmaydi" in js(r).get("detail", ""),
      (r.status_code, r.text[:200]))
for i in range(5):
    c.post("/api/users", json={"username": f"yaroqsiz_{i}", "password": "1"})            # boshqa sabab bilan rad — sanalmaydi
for i in range(7):
    c.post("/api/users", json={"username": "boshqa_korxona_admini", "password": "Parol-263-Kuchli", "role": "manager"})
r9 = c.post("/api/users", json={"username": "boshqa_korxona_admini", "password": "Parol-263-Kuchli", "role": "manager"})
r10 = c.post("/api/users", json={"username": "terish_yangi", "password": "Parol-263-Kuchli", "role": "manager"})
check("B3 soatiga 10 ta «band» urinishdan keyin — yaratish 429 (oldingi 10-chisi hali 400), foydalanuvchi yaratilmadi",
      lambda: r9.status_code == 400 and r10.status_code == 429 and "band login" in js(r10).get("detail", "")
      and SessionLocal().query(User).filter(User.username == "terish_yangi").count() == 0, (r9.status_code, r10.status_code, r10.text[:200]))
if hasattr(main, "_BAND_URINISHLAR"):
    main._BAND_URINISHLAR.clear()
r = c.post("/api/users", json={"username": "terish_yangi2", "password": "Parol-263-Kuchli", "role": "manager"})
check("B4 oddiy ko'p yaratish cheklanmaydi (boshqa sabablar sanalmaydi) — 200", lambda: r.status_code == 200, (r.status_code, r.text[:200]))

section("S — users.html")
u = open(os.path.join(ROOT, "templates", "users.html"), encoding="utf-8").read()
check("S1 «Kamida 10 belgi», tekshiruv 10 (6 qolmadi)",
      lambda: "Kamida 10 belgi" in u and "kamida 10 belgi" in u and "length<10" in u and "length < 10" in u and "Kamida 6 belgi" not in u)

print("\n" + "=" * 70)
print(f"{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
