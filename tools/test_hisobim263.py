#!/usr/bin/env python3
"""
test_hisobim263.py — kech199 (zip 263, xavfsizlik REJA 9 + 11-band): «🔐 Hisobim» — HAR kirgan foydalanuvchi o'z parolini va loginini
o'zgartiradi (joriy parol bilan).

NIMA UCHUN KERAK
----------------
  11 (Fable F7, O'LCHANGAN): Menejer o'z parolini almashtira olmasdi (`/api/users/{id}/password` — faqat Admin) → parolni doim admin bilardi.
  9 (egasi so'rovi 06.11 17:42): «admin» loginini o'zgartirmoqchi — interfeysda yo'q edi.

BO'LIMLAR
  P — /api/me/password (Menejer): kirishsiz 401; noto'g'ri joriy parol — 400 + urinish jurnalda; zaif / qisqa / login bilan — 400; o'sha
      parol — 400; to'g'ri — 200, joriy qurilma ishlaydi, boshqasi yopildi, yangi parol bilan kiradi (eskisi bilan — yo'q), jurnal;
      noma'lum kalit — 400; 5 xato joriy paroldan keyin — 429;
  L — /api/me/login: noto'g'ri shakl, o'sha login, boshqa korxonadagi band login (katta-kichik harf farqisiz) — umumiy matn; noto'g'ri parol;
      to'g'ri — 200, yangi login bilan kiradi, eskisi bilan — yo'q, boshqa qurilma yopildi, jurnal «login_ozgartirildi»; platforma egasi —
      bayrog'i saqlanadi;
  S — /hisobim sahifasi (Menejer, Usta roli ham), menyuda «Hisobim» havolasi.
REJIMLAR: SQLite; `PG_URL`; `TENANT_FILTER=1`. Asl kodga (894aa9b) qarshi YIQILADI (QULAMAYDI).
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hisobim263_test"
_DB = os.path.join(tempfile.gettempdir(), "hisobim263_test.db")
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
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, LoginHistory, ActivityLog   # noqa: E402
from production_models import Company             # noqa: E402
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


ESKI = "Eski-Parol-777"
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ikkinchi H", code="IKKI-H263"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "h263_men", ESKI, UserRole.MANAGER, "Menejer H", company_id=1)
    auth.create_user(s, "h263_usta", ESKI, UserRole.MASTER, "Usta H", company_id=1)
    auth.create_user(s, "h263_ega", ESKI, UserRole.ADMIN, "Egasi H", company_id=1)
    auth.create_user(s, "Boshqa_Band", ESKI, UserRole.ADMIN, "B admin", company_id=2)
s.commit()
s.query(User).filter(User.username == "h263_ega").update({"is_platform_admin": True})
s.commit()
s.close()
_IP = {"n": 1}


def mijoz():
    _IP["n"] += 1
    try:
        return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False,
                          client=(f"192.0.2.{_IP['n']}", 50000))
    except TypeError:
        return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)


def kir(login, parol):
    c = mijoz()
    r = c.post("/login", data={"username": login, "password": parol}, follow_redirects=False)
    return c, (r.status_code == 302 and bool(c.cookies.get("session_token")))


def jurnal(amal):
    db = SessionLocal()
    try:
        return [(a.entity_label or "") for a in db.query(ActivityLog).filter(ActivityLog.action == amal).all()]
    finally:
        db.close()


section("P — o'z paroli (Menejer)")
r = mijoz().post("/api/me/password", json={"current_password": ESKI, "new_password": "Yangi-Menejer-Parol"})
check("P1 kirishsiz — 401", lambda: r.status_code == 401, r.status_code)
M1, ok1 = kir("h263_men", ESKI)
M2, ok2 = kir("h263_men", ESKI)
check("P2 Menejer ikki qurilmada kirdi", lambda: ok1 and ok2)
r = M1.post("/api/me/password", json={"current_password": "notogri-parol", "new_password": "Yangi-Menejer-Parol"})
check("P3 noto'g'ri joriy parol — 400 «Joriy parol noto'g'ri»",
      lambda: r.status_code == 400 and "noto'g'ri" in js(r).get("detail", ""), (r.status_code, r.text[:200]))
db = SessionLocal()
n_x = db.query(LoginHistory).filter(LoginHistory.username == "h263_men", LoginHistory.success == False).count()   # noqa: E712
db.close()
check("P4 … urinish jurnalda (kirish cheklovi hisobida)", lambda: n_x == 1, n_x)
for p, kut in (("Qisqa-9ta", "10 belgi"), ("Admin12345", "oddiy"), ("xx-h263_men-xx", "login"), (ESKI, "farq")):
    r = M1.post("/api/me/password", json={"current_password": ESKI, "new_password": p})
    check(f"P5 yangi parol {p!r} — 400 «{kut}»", lambda r=r, kut=kut: r.status_code == 400 and kut in js(r).get("detail", ""),
          (r.status_code, r.text[:200]))
r = M1.post("/api/me/password", json={"current_password": ESKI, "new_password": "Yangi-Menejer-Parol", "role": "admin"})
check("P6 noma'lum kalit — 400", lambda: r.status_code == 400, r.status_code)
r = M1.post("/api/me/password", json={"current_password": ESKI, "new_password": "Yangi-Menejer-Parol"})
check("P7 to'g'ri — 200 (Menejer o'z parolini o'zgartirdi)", lambda: r.status_code == 200 and js(r).get("status") == "ok",
      (r.status_code, r.text[:200]))
check("P8 joriy qurilma ishlaydi, ikkinchisi yopildi", lambda: M1.get("/hisobim").status_code == 200
      and M2.get("/hisobim", follow_redirects=False).status_code in (302, 401), (M1.get("/hisobim").status_code,))
check("P9 yangi parol bilan kiradi, eskisi bilan — yo'q", lambda: kir("h263_men", "Yangi-Menejer-Parol")[1] and not kir("h263_men", ESKI)[1])
check("P10 jurnalda «parol_ozgartirildi»", lambda: any("h263_men" in x for x in jurnal("parol_ozgartirildi")))
U1, _ = kir("h263_usta", ESKI)
for _ in range(5):
    U1.post("/api/me/password", json={"current_password": "xato-parol", "new_password": "Usta-Yangi-Parol"})
r = U1.post("/api/me/password", json={"current_password": ESKI, "new_password": "Usta-Yangi-Parol"})
check("P11 5 ta noto'g'ri joriy paroldan keyin — 429 (to'g'risi ham)", lambda: r.status_code == 429, (r.status_code, r.text[:200]))

section("L — o'z logini")
E1, _ = kir("h263_ega", ESKI)
E2, _ = kir("h263_ega", ESKI)
for yangi, kut in (("ab", "3–50"), ("bo'sh joy bor", "3–50"), ("h263_ega", "bir xil"), ("boshqa_band", "ishlatib bo'lmaydi"),
                   ("BOSHQA_BAND", "ishlatib bo'lmaydi")):
    r = E1.post("/api/me/login", json={"current_password": ESKI, "new_username": yangi})
    check(f"L1 yangi login {yangi!r} — 400 «{kut}»", lambda r=r, kut=kut: r.status_code == 400 and kut in js(r).get("detail", ""),
          (r.status_code, r.text[:200]))
r = E1.post("/api/me/login", json={"current_password": "xato-parol", "new_username": "muzaffar_ega"})
check("L2 noto'g'ri joriy parol — 400", lambda: r.status_code == 400 and "noto'g'ri" in js(r).get("detail", ""), r.status_code)
r = E1.post("/api/me/login", json={"current_password": ESKI, "new_username": "muzaffar_ega"})
check("L3 to'g'ri — 200, yangi login javobda", lambda: r.status_code == 200 and js(r).get("username") == "muzaffar_ega", (r.status_code, r.text[:200]))
db = SessionLocal()
u = db.query(User).filter(User.username == "muzaffar_ega").first()
check("L4 bazada login o'zgardi, platforma egasi bayrog'i SAQLANDI", lambda: u is not None and u.is_platform_admin
      and db.query(User).filter(User.username == "h263_ega").count() == 0)
db.close()
check("L5 joriy qurilma ishlaydi, boshqasi yopildi", lambda: E1.get("/hisobim").status_code == 200
      and E2.get("/hisobim", follow_redirects=False).status_code in (302, 401))
check("L6 yangi login bilan kiradi, eskisi bilan — yo'q", lambda: kir("muzaffar_ega", ESKI)[1] and not kir("h263_ega", ESKI)[1])
check("L7 jurnalda «login_ozgartirildi» (eski → yangi)", lambda: any("h263_ega" in x and "muzaffar_ega" in x for x in jurnal("login_ozgartirildi")))
r = mijoz().post("/api/me/login", json={"current_password": ESKI, "new_username": "kimdir"})
check("L8 kirishsiz — 401", lambda: r.status_code == 401, r.status_code)

section("S — sahifa va menyu")
r = M1.get("/hisobim")
check("S1 Menejer — /hisobim 200, ikki forma", lambda: r.status_code == 200 and 'id="hbParolKarta"' in r.text and 'id="hbLoginKarta"' in r.text
      and "h263_men" in r.text, r.status_code)
r = M1.get("/hisobim")
check("S2 menyuda «Hisobim» havolasi", lambda: 'href="/hisobim"' in r.text)
r = mijoz().get("/hisobim", follow_redirects=False)
check("S3 kirishsiz /hisobim — kirishga yo'naltiriladi / 401", lambda: r.status_code in (302, 303, 401), r.status_code)

print("\n" + "=" * 70)
print(f"{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
