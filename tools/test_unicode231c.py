#!/usr/bin/env python3
"""
test_unicode231c.py — kech166 (zip 231c «Buzilgan Unicode — ulanish buzilmasin»; sinov saytida JONLI tasdiqlandi 31.10, review231 №6).

NIMA UCHUN KERAK
  So'rov tanasida juft bo'lmagan surrogat («\\ud800» — buzilgan Unicode) bo'lsa pg8000 uni UTF-8 ga o'gira olmaydi: xato bayonot
  yuborilayotganda chiqadi, ulanish yarim holatda hovuzga qaytadi va KEYINGI so'rovlar (boshqa foydalanuvchi / korxonaniki ham)
  500 berardi. O'LCHANGAN (`work/k231c/probe231c.py`, asl = zip 231b): `/api/rollar` → 500, keyingi uchta so'rov 500.
  Endi: `database._unicode_ulanish_xatosi` (SQLAlchemy `handle_error`) — ulanish hovuzdan chiqariladi; `main.buzilgan_unicode_handler`
  — 400 tushunarli matn bilan; sayt katalogi matnlari — oldindan tekshiriladi (`crud._dokon_surrogatsiz`).
BO'LIMLAR
  S — statik: hodisa tinglovchisi va xato ishlovchisi ulangan.
  A — API: eski marshrut (`/api/rollar`) — 400, keyingi so'rovlar 200 (PG da ulanish buzilmaydi), B korxona ham 200; sayt katalogi
      (bo'lim nomi, model tavsifi) — 400 tushunarli matn; server xatosi jurnali bo'sh; oddiy (to'g'ri) Unicode — o'zgarishsiz saqlanadi.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (asosiy holat).
Asl kodga (zip 231b) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_unicode231c.py
"""
import os
import io
import sys
import tempfile
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "unicode231c_test"
_T = tempfile.mkdtemp(prefix="t231c_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't231c.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import database                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, ErrorLog              # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
SUR = '"\\ud800x"'                                  # JSON ichida juft bo'lmagan surrogat


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
        print(f"  ✗ {label}   {str(detail)[:600]}")


def section(t):
    print(f"\n--- {t} ---")


def xatolar():
    s = SessionLocal()
    try:
        return s.query(ErrorLog).count()
    finally:
        s.close()


s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T231c B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t231c_a", PAROL, UserRole.ADMIN, "T231c A", company_id=1)
    auth.create_user(s, "t231c_b", PAROL, UserRole.ADMIN, "T231c B", company_id=2)
_c1 = s.get(Company, 1)
if hasattr(_c1, "dokon_yoqilgan"):
    _c1.dokon_yoqilgan = True
    s.commit()
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            crud._dokon_bolimlarni_yarat(s, 1, "test")
            s.commit()
        except Exception:                  # noqa: BLE001
            s.rollback()
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t231c_a")
CB = mijoz("t231c_b")
JS = {"Content-Type": "application/json"}

section("S. Statik")
check("S1 `database._unicode_ulanish_xatosi` — Engine `handle_error` tinglovchisi",
      callable(getattr(database, "_unicode_ulanish_xatosi", None))
      and __import__("sqlalchemy").event.contains(database._Engine_yv, "handle_error", database._unicode_ulanish_xatosi))
check("S2 `UnicodeError` uchun xato ishlovchisi (400)", UnicodeError in main.app.exception_handlers)

section("A. API")
_x0 = xatolar()
_r = CA.post("/api/rollar", content='{"nom": ' + SUR + ', "tavsif": "y"}', headers=JS)
_keyin = [CA.get("/api/rollar").status_code for _ in range(5)]
check("A1 eski marshrut (Rollar) — buzilgan belgi: 400 tushunarli matn", _r.status_code == 400 and "buzilgan" in _r.text,
      (_r.status_code, _r.text[:200]))
check("A2 keyingi 5 so'rov — 200 (ulanish buzilmagan)", _keyin == [200] * 5, _keyin)
check("A3 boshqa korxona (B) so'rovi — 200", CB.get("/api/rollar").status_code == 200)
_r = CA.post("/api/sayt-katalogi/bolimlar", content='{"nom": ' + SUR + ', "qolip": "dona"}', headers=JS)
check("A4 sayt katalogi: bo'lim nomida buzilgan belgi — 400 «buzilgan belgi», inglizcha texnik matn yo'q",
      _r.status_code == 400 and "buzilgan" in _r.text and "codec" not in _r.text, (_r.status_code, _r.text[:200]))
_k = CA.get("/api/sayt-katalogi")
_bid = next((b["id"] for b in (_k.json().get("bolimlar") or []) if b.get("qolip") == "dona"), None) if _k.status_code == 200 else None
_r = CA.post("/api/sayt-katalogi/modellar", content='{"bolim_id": ' + str(_bid or 1) + ', "kod": "U-1", "tavsif": ' + SUR + '}', headers=JS)
check("A5 sayt katalogi: model tavsifida buzilgan belgi — 400, model yaratilmadi",
      _r.status_code == 400 and "buzilgan" in _r.text
      and not [m for m in (CA.get("/api/sayt-katalogi").json().get("modellar") or []) if m.get("kod") == "U-1"],
      (_r.status_code, _r.text[:200]))
check("A6 keyingi so'rovlar — 200", [CA.get("/api/sayt-katalogi").status_code for _ in range(3)] == [200] * 3)
_r = CA.post("/api/sayt-katalogi/bolimlar", json={"nom": "Ўзбек — ғ ҳ қ 😀", "qolip": "dona"})
check("A7 to'g'ri Unicode (Kirill, emoji) — o'zgarishsiz saqlanadi", _r.status_code == 200 and _r.json().get("nom") == "Ўзбек — ғ ҳ қ 😀",
      (_r.status_code, _r.text[:200]))
check("A8 server xatosi jurnali (ErrorLog) — yangi yozuv yo'q", xatolar() == _x0, (xatolar(), _x0))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
