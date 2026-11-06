#!/usr/bin/env python3
"""
test_review263.py — kech200 (zip 263): mustaqil tekshiruv review263 (`work/k263/review263/HISOBOT.md`) topilmalari R2 … R5, R8.
(R1 — `test_ikki_bosqich263.py` C2 … C5; R6 — `test_pin_qulf263.py` P7b / P7c; R7 — `test_parol263.py` Q jadvali.)

NIMA UCHUN KERAK (review263 da O'LCHANGAN, probe — `work/k263/review263/probes/`)
  R2 — `/api/me/login`: har kirgan foydalanuvchi (menejer ham) platformadagi loginlarni cheklovsiz aniqlardi (28 urinish — 429 yo'q);
  R3 — `/api/users`: «boshqa_korxona_boss» bor bo'lsa ham «Boshqa_Korxona_Boss» yaratilardi (katta-kichik harf qoidasi bir xil emas);
  R4 — egasi «admin» loginini o'zgartirgach boshqa korxona admini o'zini «admin» qila olardi; `RESET_ADMIN_PASSWORD` esa «admin» nomli
       (begona) hisobni tiklardi;
  R5 — `/api/masters/kpi-report?year=1` (99999, -5) va `/api/reports/forecast?month=13` (0) — 500;
  R8 — tana chegarasi: oldinroq buzuq cookie bo'lsa `session_token` o'qilmay, platforma egasining katta zaxirasi 413 olardi.
BO'LIMLAR: A (R2), B (R3), C (R4), D (R5), E (R8).
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (611f839 — review dan oldingi zip 263) qarshi YIQILADI, QULAMAYDI.
ISHLATISH: python3 tools/test_review263.py
"""
import os
import sys
import asyncio
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "review263_test"
_T = tempfile.mkdtemp(prefix="review263_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'review263_test.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "ADMIN_PASSWORD", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User, UserSession     # noqa: E402
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
        print(f"  ✗ {REJIM}{label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


PAROL = "Kuchli-Sinov-Parol-263"
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Review B korxona", code="REV-B263"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "rv_egasi", PAROL, UserRole.ADMIN, "Platforma egasi", company_id=1)
    auth.create_user(s, "rv_menejer", PAROL, UserRole.MANAGER, "Menejer", company_id=1)
    auth.create_user(s, "rv_b_admin", PAROL, UserRole.ADMIN, "B admin", company_id=2)
    auth.create_user(s, "boshqa_korxona_boss", PAROL, UserRole.ADMIN, "B boss", company_id=2)
# ishga tushishdagi standart «admin» (bo'sh bazada) — boshqa nomga (sinov «admin» nomining bo'shligiga tayanadi)
s.query(User).filter(User.username == "admin").update({"username": "standart_admin_eski"}, synchronize_session=False)
s.query(User).filter(User.username == "rv_egasi").update({"is_platform_admin": True})
s.query(User).filter(User.username != "rv_egasi").update({"is_platform_admin": False}, synchronize_session=False)
s.commit()
s.close()


def kirgan(login, parol=PAROL):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": parol}, follow_redirects=False)
    assert r.status_code == 302, f"{login} kirmadi: {r.status_code} {r.text[-200:]}"
    return c


def band_tozala():
    if hasattr(main, "_BAND_URINISHLAR"):
        main._BAND_URINISHLAR.clear()


CM, CB, CE = kirgan("rv_menejer"), kirgan("rv_b_admin"), kirgan("rv_egasi")

# ══════════════════════════════════════════════════════════════
section("A — R2: /api/me/login — loginlarni terib aniqlash cheklangan")
# ══════════════════════════════════════════════════════════════
band_tozala()
_kodlar = []
for i in range(10):
    r = CM.post("/api/me/login", json={"current_password": PAROL, "new_username": "boshqa_korxona_boss"})
    _kodlar.append(r.status_code)
r11 = CM.post("/api/me/login", json={"current_password": PAROL, "new_username": "boshqa_korxona_boss"})
r12 = CM.post("/api/me/login", json={"current_password": PAROL, "new_username": "menejer_yangi_bosh"})
check("A1 menejer: 10 ta «band» urinish — 400 (umumiy matn), 11-chisi — 429; shu soatda bo'sh loginga ham 429 (terish to'xtadi)",
      _kodlar == [400] * 10 and r11.status_code == 429 and r12.status_code == 429 and "band login" in js(r11).get("detail", ""),
      (_kodlar, r11.status_code, r12.status_code, r11.text[:200]))
s = SessionLocal()
check("A2 … login o'zgarmadi", lambda: s.query(User).filter(User.username == "rv_menejer").count() == 1)
s.close()
band_tozala()
_kodlar = [CM.post("/api/me/login", json={"current_password": "notogri-parol-x", "new_username": "yangi_bir_login"}).status_code
           for _ in range(3)]
check("A3 noto'g'ri joriy parol «band» deb sanalmaydi (o'z cheklovi — kirish cheklovi)", lambda: _kodlar == [400, 400, 400]
      and len(main._BAND_URINISHLAR.get(SessionLocal().query(User.id).filter(User.username == "rv_menejer").scalar(), [])) == 0,
      _kodlar)
band_tozala()

# ══════════════════════════════════════════════════════════════
section("B — R3: login yagonaligi katta-kichik harf farqisiz (/api/users)")
# ══════════════════════════════════════════════════════════════
band_tozala()
r = CE.post("/api/users", json={"username": "Boshqa_Korxona_Boss", "password": PAROL, "role": "manager", "full_name": "X"})
check("B1 «Boshqa_Korxona_Boss» (boshqa korxonada «boshqa_korxona_boss» bor) — 400 umumiy matn, yaratilmadi",
      r.status_code == 400 and js(r).get("detail") == auth.LOGIN_BAND_XABARI
      and SessionLocal().query(User).filter(User.username == "Boshqa_Korxona_Boss").count() == 0, (r.status_code, r.text[:200]))
r = CE.post("/api/users", json={"username": "RV_MENEJER", "password": PAROL, "role": "manager", "full_name": "X"})
check("B2 o'z korxonasidagi login katta harf bilan — ham 400", r.status_code == 400 and js(r).get("detail") == auth.LOGIN_BAND_XABARI,
      (r.status_code, r.text[:200]))
r = CE.post("/api/users", json={"username": "rv_yangi_xodim", "password": PAROL, "role": "manager", "full_name": "X"})
check("B3 yangi login — 200", r.status_code == 200, (r.status_code, r.text[:200]))
band_tozala()

# ══════════════════════════════════════════════════════════════
section("C — R4: «admin» va boshqa ajratilgan nomlar; RESET_ADMIN_PASSWORD nishoni")
# ══════════════════════════════════════════════════════════════
check("C0 auth.ZAXIRALANGAN_LOGINLAR: admin, root, administrator …",
      lambda: {"admin", "root", "administrator", "superadmin"} <= set(auth.ZAXIRALANGAN_LOGINLAR))
_rad = {}
for nom in ("admin", "Admin", "ROOT", "administrator", "superadmin"):
    band_tozala()
    r = CB.post("/api/me/login", json={"current_password": PAROL, "new_username": nom})
    _rad[nom] = (r.status_code, js(r).get("detail"))
check("C1 boshqa korxona admini o'zini «admin» / «Admin» / «ROOT» / «administrator» / «superadmin» qila OLMAYDI — 400 umumiy matn",
      all(v == (400, auth.LOGIN_BAND_XABARI) for v in _rad.values()), _rad)
band_tozala()
_rad2 = {nom: CB.post("/api/users", json={"username": nom, "password": PAROL, "role": "manager", "full_name": "X"}).status_code
         for nom in ("admin", "root", "Administrator")}
check("C2 … «/api/users» orqali ham yaratilmaydi (400)", all(v == 400 for v in _rad2.values()), _rad2)
band_tozala()
r = CE.post("/api/me/login", json={"current_password": PAROL, "new_username": "admin"})
check("C3 platforma egasi «admin» ga o'ta OLADI (bo'sh bo'lsa) — 200", r.status_code == 200 and js(r).get("username") == "admin",
      (r.status_code, r.text[:200]))
# eski bazada boshqa korxonada «admin» nomli hisob bo'lib qolgan holat (ajratilgan nomlar qoidasidan oldin) — tiklash unga TEGMASIN
s = SessionLocal()
ega = s.query(User).filter(User.is_platform_admin == True).first()          # noqa: E712
ega.username = "egasi_yangi_nomi"
s.commit()
for _i, _u in enumerate(s.query(User).filter(User.username == "admin").all()):       # asl kodda C1 da kimdir «admin» bo'lib qolgan
    _u.username = f"admin_band_{_i}"
s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "admin", PAROL, UserRole.ADMIN, "Begona admin", company_id=2)
s.commit()
_begona = s.query(User).filter(User.username == "admin").first()
_bx, _ex = _begona.password_hash, ega.password_hash
_bid, _eid = _begona.id, ega.id
s.close()
os.environ["ADMIN_PASSWORD"] = "Tiklangan-Parol-263-Egasi"
os.environ["RESET_ADMIN_PASSWORD"] = "true"
s = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_default_admin(s)
s.close()
for _k in ("ADMIN_PASSWORD", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)
s = SessionLocal()
_b2 = s.query(User).filter(User.id == _bid).first().password_hash
_e2u = s.query(User).filter(User.id == _eid).first()
s.close()
check("C4 RESET_ADMIN_PASSWORD — PLATFORMA EGASI paroli tiklandi, boshqa korxonadagi «admin» nomli hisobga TEGILMADI",
      lambda: _b2 == _bx and _e2u.password_hash != _ex and auth.verify_password("Tiklangan-Parol-263-Egasi", _e2u.password_hash),
      (_b2 == _bx, _e2u.password_hash != _ex))
s = SessionLocal()
check("C5 … egasining sessiyalari yopildi", lambda: s.query(UserSession).filter(UserSession.user_id == _eid).count() == 0)
s.close()
check("C6 login_zaxiralanganmi: platforma egasi uchun — yo'q; boshqaga — ha; oddiy nom — yo'q",
      lambda: not auth.login_zaxiralanganmi("admin", type("U", (), {"is_platform_admin": True})())
      and auth.login_zaxiralanganmi(" Admin ") and not auth.login_zaxiralanganmi("admin_yordamchi"))

# ══════════════════════════════════════════════════════════════
section("D — R5: hisobot davri — 500 emas, 400")
# ══════════════════════════════════════════════════════════════
try:
    CE2 = kirgan("egasi_yangi_nomi", "Tiklangan-Parol-263-Egasi")
except AssertionError as _e:                       # asl kodda tiklash begona «admin» ga tushadi — egasi kira olmaydi (C4 yiqiladi)
    print(f"    (egasi kira olmadi: {str(_e)[:80]} — eski parol bilan)")
    CE2 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    CE2.post("/login", data={"username": "egasi_yangi_nomi", "password": PAROL}, follow_redirects=False)
_d = {}
for url in ("/api/masters/kpi-report?year=1", "/api/masters/kpi-report?year=99999", "/api/masters/kpi-report?year=-5",
            "/api/reports/forecast?year=2026&month=13", "/api/reports/forecast?year=2026&month=0",
            "/api/reports/forecast?year=1&month=5"):
    r = CE2.get(url)
    _j = js(r)
    _d[url] = (r.status_code, str(_j.get("detail", "") if isinstance(_j, dict) else _j)[:60])
check("D1 kpi-report year=1 / 99999 / -5, forecast month=13 / 0 / year=1 — 400 «Davr noto'g'ri» (500 emas)",
      all(v[0] == 400 and "Davr noto'g'ri" in v[1] for v in _d.values()), _d)
_ok = {u: CE2.get(u).status_code for u in ("/api/masters/kpi-report?year=2026", "/api/reports/forecast?year=2026&month=11",
                                          "/api/masters/kpi-report")}
check("D2 oddiy davr — 200 (o'zgarmagan)", all(v == 200 for v in _ok.values()), _ok)

# ══════════════════════════════════════════════════════════════
section("E — R8: tana chegarasi — buzuq cookie bo'lsa ham session_token o'qiladi")
# ══════════════════════════════════════════════════════════════
_tok = CE2.cookies.get("session_token")


def tana_sinov(cookie, uzunlik):
    """Middleware ni to'g'ridan-to'g'ri: /tiklash multipart, Content-Length = `uzunlik` (tana o'qilmaydi). Natija — ilova
    chaqirildimi (True) yoki 413 (False)."""
    holat = {"ilova": False, "kod": None}

    async def ilova(scope, receive, send):
        holat["ilova"] = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(x):
        if x.get("type") == "http.response.start":
            holat["kod"] = x.get("status")

    scope = {"type": "http", "method": "POST", "path": "/tiklash", "headers": [
        (b"content-type", b"multipart/form-data; boundary=x"), (b"content-length", str(uzunlik).encode()),
        (b"cookie", cookie.encode("latin-1"))]}
    asyncio.run(main._TanaChegarasi(ilova)(scope, receive, send))
    return holat["ilova"], holat["kod"]


_mb50 = 50 * 1024 * 1024
_n = {"toza cookie": tana_sinov(f"session_token={_tok}", _mb50),
      "oldinroq buzuq cookie": tana_sinov(f'a="x; b; session_token={_tok}; c=d', _mb50),
      "buzuq + sessiyasiz": tana_sinov('a="x; b; c=d', _mb50),
      "begona token": tana_sinov('a="x; session_token=soxta-token-123', _mb50)}
check("E1 platforma egasi sessiyasi, 50 MB zaxira: toza cookie va OLDINROQ BUZUQ cookie bilan — ilovaga o'tadi (413 emas)",
      _n["toza cookie"] == (True, 200) and _n["oldinroq buzuq cookie"] == (True, 200), _n)
check("E2 sessiyasiz / begona token — 413 (ilova chaqirilmaydi)",
      _n["buzuq + sessiyasiz"] == (False, 413) and _n["begona token"] == (False, 413), _n)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
