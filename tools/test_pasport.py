#!/usr/bin/env python3
"""
test_pasport.py — `LOYIHA_PASPORTI.md` (16-band) izchilligi va shablon → marshrut havolalari darvozasi (kech104, 2026-09-28).

NIMA UCHUN
----------
  * Pasport yangi chatga "repo + muammo tavsifi yetarli" bo'lishi uchun yozilgan. Uning xarita bo'limlari
    (sahifalar, API, ishga tushish tartibi, jadvallar, muhit o'zgaruvchilari, testlar) `tools/pasport_xarita.py`
    bilan KODDAN yasaladi; kod o'zgarib, pasport yangilanmasa — bu test yiqiladi (A). Qo'lda yozilgan qismda
    tilga olingan fayl va funksiyalar mavjudligi (D) va majburiy bo'limlar (E) ham tekshiriladi.
  * K104-1 (asl kod `bfad2d4` da O'LCHANGAN — `work/probe104.py`): "Foydalanuvchilar" sahifasidagi FAVQULODDA
    "Webhookni o'chirib, botni asl holatiga qaytarish" tugmasi `POST /api/system/telegram-delete-webhook` ni
    chaqirardi, marshrut esa 2026-09-01 da olib tashlangan edi — platforma admini bosganda 404 "Not Found".
    Umumiy qoida (B): shablon JavaScript'idagi HAR BIR `/api/...` havolasi mavjud marshrutga mos kelishi SHART.
    Tiklangan marshrut xulqi (C): qorovul (faqat platforma admini), token yo'q, Telegram javoblari — tarmoqsiz
    (`urllib.request.urlopen` soxtasi bilan).

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_pasport.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_pasport.py
"""
import os
import re
import sys
import json
import subprocess
import tempfile
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "pasport104_test"
_DB = os.path.join(tempfile.gettempdir(), "pasport104_test.db")

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
import urllib.request                              # noqa: E402
import urllib.error                                # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, services                    # noqa: E402
    import production_service                      # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import UserRole, User                  # noqa: E402
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
        print(f"  ✗ {label}   {str(detail)[:600]}")


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
        with open(os.path.join(ROOT, nom), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def _xarita_moduli():
    """tools/pasport_xarita.py — yo'q / buzuq bo'lsa None (test QULAMAYDI, tekshiruvlar yiqiladi)."""
    yol = os.path.join(ROOT, "tools", "pasport_xarita.py")
    try:
        spec = importlib.util.spec_from_file_location("pasport_xarita", yol)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:                 # noqa: BLE001
        print(f"  (pasport_xarita.py yuklanmadi: {type(e).__name__}: {e})")
        return None


PX = _xarita_moduli()
PASPORT = fayl("LOYIHA_PASPORTI.md")

# ══════════════════════════════════════════════════════════════
section("A. Pasportdagi AVTO bloklar KOD bilan AYNAN (tools/pasport_xarita.py --tekshir)")
# ══════════════════════════════════════════════════════════════
check("A1 LOYIHA_PASPORTI.md repo ildizida bor va bo'sh emas", len(PASPORT) > 1000, len(PASPORT))
check("A2 tools/pasport_xarita.py yuklandi", PX is not None)
BLOKLAR_NOMI = ("MUHIT", "ISHGA_TUSHISH", "SAHIFALAR", "API", "MODELLAR", "TESTLAR")
try:
    BLOKLAR = PX.hamma_bloklar() if PX else {}
except Exception as e:                     # noqa: BLE001
    BLOKLAR = {}
    print(f"  (hamma_bloklar xato: {type(e).__name__}: {e})")
for nom in BLOKLAR_NOMI:
    bosh = f"<!-- AVTO:{nom} BOSHI — qo'lda tahrirlamang: python3 tools/pasport_xarita.py --yoz -->"
    oxir = f"<!-- AVTO:{nom} OXIRI -->"
    check(f"A3 {nom}: bosh / oxir belgilari pasportda bittadan", PASPORT.count(bosh) == 1 and PASPORT.count(oxir) == 1,
          (PASPORT.count(bosh), PASPORT.count(oxir)))
try:
    FARQLAR = PX.farqlar(PASPORT, BLOKLAR) if (PX and BLOKLAR) else [("HAMMASI", "xarita yasalmadi")]
except Exception as e:                     # noqa: BLE001
    FARQLAR = [("HAMMASI", f"{type(e).__name__}: {e}")]
farq_nomlar = {n for n, _ in FARQLAR}
for nom in BLOKLAR_NOMI:
    izoh = next((i for n, i in FARQLAR if n == nom), "")
    check(f"A4 {nom}: pasport bloki = koddan yasalgan xarita (farq bo'lsa: python3 tools/pasport_xarita.py --yoz)",
          nom not in farq_nomlar and "HAMMASI" not in farq_nomlar, izoh)
# --tekshir rejimining chiqish kodi (skript sifatida)
try:
    _p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "pasport_xarita.py"), "--tekshir"],
                        capture_output=True, text=True, timeout=120, cwd=ROOT)
    check("A5 `pasport_xarita.py --tekshir` chiqish kodi 0", _p.returncode == 0, (_p.stdout + _p.stderr)[-500:])
except Exception as e:                     # noqa: BLE001
    check("A5 `pasport_xarita.py --tekshir` chiqish kodi 0", False, f"{type(e).__name__}: {e}")
# Xarita haqiqatan kodni aks ettiradimi — bir necha mustaqil o'lchov (xarita funksiyalarini emas, ilovani o'zini so'raymiz)
_app_yollar = set()


def _yigish(routes):
    """FastAPI 0.141: `include_router` marshrutlarni `_IncludedRouter` ichida saqlaydi (`original_router.routes`)."""
    for _r in routes:
        _ichki = getattr(_r, "original_router", None)
        if _ichki is not None:
            _yigish(getattr(_ichki, "routes", []) or [])
            continue
        for _m in (getattr(_r, "methods", None) or []):
            if _m in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                _app_yollar.add((_m, getattr(_r, "path", "")))


_yigish(main.app.routes)
try:
    _xarita_yollar = {(r.usul, r.yol) for r in PX.hamma_marshrutlar()} if PX else set()
except Exception as e:                     # noqa: BLE001
    _xarita_yollar = set()
    print(f"  (hamma_marshrutlar xato: {type(e).__name__}: {e})")
# kech129 (zip 153, MOSLANDI): SaaS migratsiya sahifasi olib tashlandi — xarita va ilova marshrutlari AYNAN, `saas-migra` YO'Q.
_saas = {(u, y) for u, y in _xarita_yollar | _app_yollar if "saas-migra" in y}
check("A6 xaritadagi marshrutlar = ilova marshrutlari (main.app.routes)",
      _xarita_yollar == _app_yollar,
      f"xaritada ortiqcha: {sorted(_xarita_yollar - _app_yollar)[:8]}; "
      f"xaritada yo'q: {sorted(_app_yollar - _xarita_yollar)[:8]}")
check("A7 SaaS migratsiya marshrutlari (`saas-migra`) na xaritada, na ilovada YO'Q (kech129 — olib tashlandi)", not _saas, sorted(_saas))
_blok_api = BLOKLAR.get("API", "")
check("A8 API blokidagi 'Jami marshrutlar' soni = xaritadagi marshrutlar soni",
      f"Jami marshrutlar: {len(_xarita_yollar)} " in _blok_api, (len(_xarita_yollar), _blok_api[-200:]))
try:
    import models as _models
    importlib.import_module("production_models")          # MRP jadvallari metadata ga shu import bilan qo'shiladi
    _jadvallar = set(_models.Base.metadata.tables)
except Exception as e:                     # noqa: BLE001
    _jadvallar = set()
    print(f"  (metadata: {e})")
_blok_mod = BLOKLAR.get("MODELLAR", "")
_mod_jadval = set(re.findall(r"^- `([a-z_]+)` — `", _blok_mod, re.M))
check("A9 MODELLAR bloki jadvallari = SQLAlchemy metadata jadvallari", _mod_jadval == _jadvallar and len(_jadvallar) > 40,
      f"ortiqcha {sorted(_mod_jadval - _jadvallar)}; yo'q {sorted(_jadvallar - _mod_jadval)}")
_blok_test = BLOKLAR.get("TESTLAR", "")
_test_fayllar = set(os.path.basename(p) for p in os.listdir(os.path.join(ROOT, "tools"))
                    if p.startswith("test_") and p.endswith((".py", ".js")))
check("A10 TESTLAR bloki = tools/test_*.py|js fayllari (shu fayl ham)",
      set(re.findall(r"^- `(test_[a-z0-9_]+\.(?:py|js))`", _blok_test, re.M)) == _test_fayllar
      and "test_pasport.py" in _test_fayllar, len(_test_fayllar))

# ══════════════════════════════════════════════════════════════
section("B. Shablon JavaScript'idagi HAR BIR /api/ havolasi mavjud marshrutga mos (K104-1 sinfi)")
# ══════════════════════════════════════════════════════════════
_naqshlar = {re.sub(r"\{[^}]*\}", "{}", y) for _, y in _app_yollar} | {re.sub(r"\{[^}]*\}", "{}", y) for _, y in _xarita_yollar}
_osiq = []
_jami_havola = 0
for _sh in sorted(os.listdir(os.path.join(ROOT, "templates"))):
    if not _sh.endswith(".html"):
        continue
    try:
        _yollar = PX.shablon_api_yollari("templates/" + _sh) if PX else []
    except Exception as e:                 # noqa: BLE001
        _yollar = []
        _osiq.append((_sh, f"xato {e}"))
    for _y in _yollar:
        _jami_havola += 1
        if _y not in _naqshlar:
            _osiq.append((_sh, _y))
check("B1 shablonlardan kamida 150 ta /api/ havolasi o'qildi (o'quvchi ishlayapti)", _jami_havola >= 150, _jami_havola)
check("B2 o'lik havola YO'Q (har /api/ yo'li biror marshrutga mos)", not _osiq, _osiq[:10])
check("B3 users.html → /api/system/telegram-delete-webhook havolasi marshrutga mos (K104-1)",
      "/api/system/telegram-delete-webhook" in _naqshlar)
# O'quvchining o'zi to'g'riligini nazorat: ma'lum murakkab shakllar
try:
    # kech111: platforma korxonalari UI si `logs.html` dan alohida sahifaga (`platforma.html`) ko'chdi — shakl AYNAN
    # (`'/api/platform/companies/' + id + '/reset-admin-password'`), o'quvchining o'zi tekshiriladi.
    _logs = PX.shablon_api_yollari("templates/platforma.html") if PX else []
    _ord = PX.shablon_api_yollari("templates/orders.html") if PX else []
except Exception:                          # noqa: BLE001
    _logs, _ord = [], []
check("B4 o'quvchi: `'/api/platform/companies/' + id + '/reset-admin-password'` → `.../{}/reset-admin-password` (platforma.html)",
      "/api/platform/companies/{}/reset-admin-password" in _logs, _logs)
check("B5 o'quvchi: shablon satri `${id}` → `{}` (orders.html `/api/orders/{}/profit`)", "/api/orders/{}/profit" in _ord, _ord[:12])

# ══════════════════════════════════════════════════════════════
section("C. K104-1 — POST /api/system/telegram-delete-webhook (FAQAT platforma admini, tarmoqsiz)")
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "P104_plat", "Parol123!", UserRole.ADMIN, "P104 Platforma", company_id=1)
    auth.create_user(_db, "P104_adm", "Parol123!", UserRole.ADMIN, "P104 Korxona admini", company_id=1)
_db.query(User).filter(User.username == "P104_plat").first().is_platform_admin = True
_db.query(User).filter(User.username == "P104_adm").first().is_platform_admin = False
_db.commit()
_db.close()


def kirgan(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


CP, _s1 = kirgan("P104_plat")
CA, _s2 = kirgan("P104_adm")
C0 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
check("C0 ikkala login 302", _s1 == 302 and _s2 == 302, (_s1, _s2))
YOL = "/api/system/telegram-delete-webhook"
check("C1 marshrut ilovada bor (POST)", ("POST", YOL) in _app_yollar)
r = req(C0, "post", YOL)
check("C2 kirmagan → 401", r.status_code == 401, (r.status_code, r.text[:120]))
r = req(CA, "post", YOL)
check("C3 KORXONA admini (platforma emas) → 403", r.status_code == 403 and "platforma" in r.text, (r.status_code, r.text[:160]))
# kech130 (zip 154, MOSLANDI): bot manzilini o'zgartiruvchi amal FAQAT asosiy muhitda (Railway «production») — C4 … C10 shu
# muhitda; asosiy bo'lmagan muhit — C4a / C4b (409, Telegram'ga so'rov ketmaydi).
os.environ.pop("RAILWAY_ENVIRONMENT_NAME", None)
os.environ.pop("RAILWAY_ENVIRONMENT", None)
os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"
r = req(CP, "post", YOL)
check("C4 platforma admini, TELEGRAM_BOT_TOKEN yo'q → 400 'TELEGRAM_BOT_TOKEN sozlanmagan'",
      r.status_code == 400 and "TELEGRAM_BOT_TOKEN sozlanmagan" in r.text, (r.status_code, r.text[:160]))

_ASL_URLOPEN = urllib.request.urlopen
_CHAQIRUVLAR = []


class _Javob:
    def __init__(self, tana):
        self._t = json.dumps(tana).encode()

    def read(self):
        return self._t

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _soxta(natija):
    def f(so_rov, timeout=None, **k):
        _CHAQIRUVLAR.append((getattr(so_rov, "full_url", str(so_rov)), getattr(so_rov, "get_method", lambda: "?")(), timeout))
        if isinstance(natija, Exception):
            raise natija
        return _Javob(natija)
    return f


os.environ["TELEGRAM_BOT_TOKEN"] = "123:SOXTA"
try:
    urllib.request.urlopen = _soxta({"ok": True, "result": True, "description": "Webhook was deleted"})
    r = req(CP, "post", YOL)
    d = js(r) or {}
    check("C5 Telegram ok → 200, status ok, xabar 'Webhook o'chirildi'",
          r.status_code == 200 and d.get("status") == "ok" and "Webhook o'chirildi" in (d.get("message") or ""),
          (r.status_code, r.text[:200]))
    _u = _CHAQIRUVLAR[-1] if _CHAQIRUVLAR else ("", "", None)
    check("C6 Telegram'ga BIR so'rov: .../bot123:SOXTA/deleteWebhook?drop_pending_updates=false, POST, timeout 10",
          len(_CHAQIRUVLAR) == 1 and _u[0] == "https://api.telegram.org/bot123:SOXTA/deleteWebhook?drop_pending_updates=false"
          and _u[1] == "POST" and _u[2] == 10, _CHAQIRUVLAR)
    urllib.request.urlopen = _soxta({"ok": False, "description": "Soxta rad"})
    r = req(CP, "post", YOL)
    check("C7 Telegram ok=false → 400 'Telegram rad etdi: Soxta rad'",
          r.status_code == 400 and "Telegram rad etdi: Soxta rad" in r.text, (r.status_code, r.text[:200]))
    _he = urllib.error.HTTPError("https://api.telegram.org/x", 401, "Unauthorized", {},
                                 io.BytesIO(json.dumps({"ok": False, "description": "Unauthorized"}).encode()))
    urllib.request.urlopen = _soxta(_he)
    r = req(CP, "post", YOL)
    check("C8 Telegram HTTP 401 (JSON sabab) → 400 'Telegram rad etdi: Unauthorized'",
          r.status_code == 400 and "Telegram rad etdi: Unauthorized" in r.text, (r.status_code, r.text[:200]))
    urllib.request.urlopen = _soxta(urllib.error.URLError("tarmoq yo'q"))
    r = req(CP, "post", YOL)
    check("C9 tarmoq xatosi → 500 'Telegram bilan bog'lanishda xato'",
          r.status_code == 500 and "Telegram bilan bog'lanishda xato" in r.text, (r.status_code, r.text[:200]))
    _n = len(_CHAQIRUVLAR)
    r = req(CA, "post", YOL)
    check("C10 token BOR bo'lsa ham korxona admini → 403 va Telegram'ga so'rov KETMAYDI",
          r.status_code == 403 and len(_CHAQIRUVLAR) == _n, (r.status_code, len(_CHAQIRUVLAR) - _n))
    # kech130 (zip 154): sinov saytida (kech129 — staging token bilan production botini «o'g'irlagan») bu tugma production
    # botining webhookini o'chirib, ustalar botini to'xtatardi
    urllib.request.urlopen = _soxta({"ok": True, "result": True, "description": "Webhook was deleted"})
    for _mn, _ism in (("sinov", "«sinov»"), ("", "«aniqlanmadi»")):
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = _mn
        _n = len(_CHAQIRUVLAR)
        r = req(CP, "post", YOL)
        check(f"C4{'a' if _mn else 'b'} muhit {_ism} (asosiy emas), token BOR, platforma admini → 409 «asosiy sayt emas» va "
              f"Telegram'ga so'rov KETMAYDI",
              r.status_code == 409 and "asosiy sayt emas" in r.text and _ism in r.text and len(_CHAQIRUVLAR) == _n,
              (r.status_code, r.text[:200], len(_CHAQIRUVLAR) - _n))
finally:
    urllib.request.urlopen = _ASL_URLOPEN
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ.pop("RAILWAY_ENVIRONMENT_NAME", None)

_uh = fayl("templates/users.html")
check("C11 users.html: deleteTelegramWebhook() aynan shu yo'lga POST yuboradi",
      tartibda(_uh, "async function deleteTelegramWebhook()",
               "fetch('/api/system/telegram-delete-webhook', { method: 'POST' })"))
_hp = req(CP, "get", "/users").text
_ha = req(CA, "get", "/users").text
check("C12 tugma (id=\"tg-delete-webhook-btn\") FAQAT platforma admini sahifasida",
      'id="tg-delete-webhook-btn"' in _hp and 'id="tg-delete-webhook-btn"' not in _ha,
      ('id="tg-delete-webhook-btn"' in _hp, 'id="tg-delete-webhook-btn"' in _ha))
_m = fayl("main.py")
check("C13 main.py: qorovul `Depends(auth.platform_admin_only)` (qo'shni setup-webhook-security bilan bir xil)",
      tartibda(_m, '@app.post("/api/system/telegram-delete-webhook")',
               "def api_telegram_delete_webhook(current_user=Depends(auth.platform_admin_only)):"))

# ══════════════════════════════════════════════════════════════
section("F. K104-2 — FastAPI API hujjatlari (/openapi.json, /docs, /redoc) YOPIQ")
# ══════════════════════════════════════════════════════════════
for _p in ("/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"):
    r0 = req(C0, "get", _p, follow_redirects=False)
    rp = req(CP, "get", _p, follow_redirects=False)
    check(f"F1 {_p}: kirmagan → 404, platforma admini ham → 404",
          r0.status_code == 404 and rp.status_code == 404, (r0.status_code, rp.status_code, r0.text[:80]))
check("F2 ilova marshrutlarida /openapi.json, /docs, /redoc YO'Q",
      not any(y in ("/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect") for _, y in _app_yollar))
check("F3 main.py: FastAPI(..., docs_url=None, redoc_url=None, openapi_url=None)",
      tartibda(_m, "app = FastAPI(", "docs_url=None, redoc_url=None, openapi_url=None)"))

# ══════════════════════════════════════════════════════════════
section("D. Pasportning qo'lda yozilgan qismi — tilga olingan fayl va funksiyalar MAVJUD")
# ══════════════════════════════════════════════════════════════
_qolda = PASPORT
for nom in BLOKLAR_NOMI:
    bosh = f"<!-- AVTO:{nom} BOSHI"
    oxir = f"<!-- AVTO:{nom} OXIRI -->"
    i, j = _qolda.find(bosh), _qolda.find(oxir)
    if i != -1 and j != -1 and j > i:
        _qolda = _qolda[:i] + _qolda[j + len(oxir):]
_fayl_havolalari = sorted(set(re.findall(r"`((?:tools|templates|static)/[A-Za-z0-9_./-]+\.(?:py|html|js|sh|json|css))`", _qolda))
                          | set(re.findall(r"`([a-z_]+\.py)`", _qolda)))
# Ildizdagi nom (`crud.py`) yoki `tools/` ichidagi nom (`tenant_lint.py`) — ikkalasidan biri bo'lsa yetarli.
_yoq = [f for f in _fayl_havolalari
        if not os.path.exists(os.path.join(ROOT, f)) and not os.path.exists(os.path.join(ROOT, "tools", f))]
check("D1 qo'lda yozilgan qismda kamida 25 ta fayl havolasi", len(_fayl_havolalari) >= 25, len(_fayl_havolalari))
check("D2 tilga olingan HAR fayl repoda bor", not _yoq, _yoq)
_modullar = {"crud": crud, "services": services, "auth": auth, "production_service": production_service, "main": main}
_funk = sorted(set((m, n) for m, n in re.findall(r"`(crud|services|auth|production_service|main)\.([A-Za-z_][A-Za-z0-9_]*)", _qolda)
                   if n != "py"))
_yoq_f = [f"{m}.{n}" for m, n in _funk if not hasattr(_modullar[m], n)]
check("D3 qo'lda yozilgan qismda kamida 25 ta `modul.funksiya` havolasi", len(_funk) >= 25, len(_funk))
check("D4 tilga olingan HAR `crud.` / `services.` / `auth.` / `production_service.` / `main.` nomi mavjud", not _yoq_f, _yoq_f)

# ══════════════════════════════════════════════════════════════
section("E. Majburiy bo'limlar va tools/hammasi.sh")
# ══════════════════════════════════════════════════════════════
for sarlavha in ("## 0. Bu fayl nima", "## 1. Ish qoidalari", "## 2. Muhit: `staging` va `main`",
                 "## 3. Tuzilma", "## 4. Asosiy qoidalar (kodda)", "## 5. Testlar va darvozalar",
                 "## 6. Qabul qilingan BIZNES qarorlari", "## 7. Ochiq masalalar", "## 8. Texnik saboqlar",
                 "## 9. Xarita (AVTOMATIK)"):
    check(f"E1 sarlavha bor: {sarlavha}", sarlavha in PASPORT)
_hs = fayl("tools/hammasi.sh")
check("E2 tools/hammasi.sh bor va tools/test_*.py hamda tools/test_*.js ni yig'adi",
      "tools/test_*.py" in _hs and "tools/test_*.js" in _hs and "NATIJA" in _hs, len(_hs))
try:
    _b = subprocess.run(["bash", "-n", os.path.join(ROOT, "tools", "hammasi.sh")], capture_output=True, text=True, timeout=30)
    check("E3 tools/hammasi.sh sintaksisi (bash -n)", _b.returncode == 0, _b.stderr[:300])
except Exception as e:                     # noqa: BLE001
    check("E3 tools/hammasi.sh sintaksisi (bash -n)", False, f"{type(e).__name__}: {e}")

# "TODO" so'zi qoidalar matnida ("TODO qoldirilmaydi") bor — shuning uchun faqat joy-to'ldiruvchi belgilari.
_toldiruvchi = [t for t in ("SONLAR_", "XXX", "FIXME", "TBD", "<<") if t in _qolda]
check("E4 pasportning qo'lda yozilgan qismida joy-to'ldiruvchi / TODO YO'Q", not _toldiruvchi, _toldiruvchi)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
