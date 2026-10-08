#!/usr/bin/env python3
"""
test_telegram_xato_izoh.py — kech131 (zip 155): Telegram XATOLARI O'ZBEKCHA (egasi tanlovi 08.10 «Telegram xato izohi»).

NIMA UCHUN KERAK (kech130 jonli sinovi va 08.10 o'lchovi)
---------------------------------------------------------
  Foydalanuvchiga Telegram'ning XOM inglizcha javobi chiqardi — egasi ham, mijoz korxona admini ham o'qiy olmaydi:
    * «Foydalanuvchilar → 🔒 Telegram xavfsizligi → Bot hozir qayerga ulangan» — «❌ Telegram rad etdi: Not Found» (staging, 08.10);
    * «Oxirgi xato: Wrong response from the webhook: 403 Forbidden»;
    * «🔐 Telegram xavfsizligini yoqish» / «🔄 Botni asl holatiga qaytarish» / mijozning «🔗 Botni ulash» — «Telegram rad etdi: Unauthorized»;
    * `telegram-debug` — `bot_info_error` faqat «HTTP Error 404: Not Found», `updates_error_izoh` faqat 409 ni tushuntirardi.
  O'LCHANGAN (08.10 ~20:50, soxta tokenlar, ichki brauzer — Telegram'ning o'z javobi): token KO'RINISHI buzuq → HTTP 404 «Not Found»;
  ko'rinishi to'g'ri, lekin bot yo'q / token bekor → HTTP 401 «Unauthorized» (getMe, getWebhookInfo, getUpdates).

BO'LIMLAR
  A — yordamchilar (`_tg_xato_izohi`, `_tg_xato_matni`, `_tg_tarmoq_xato_matni`, `_tg_webhook_xato_izohi`, `TelegramRad.kod`);
  B — `GET /api/system/telegram-webhook-info`: 401 / 404 (asosiy sayt — Railway maslahati; SINOV saytida — «asosiy botning tokenini
      QO'YMANG», Railway ga qo'yish maslahati YO'Q), ok=false + error_code, tanilmagan — eskisidek, 429, tarmoq, oxirgi xato izohi;
  C — `telegram-debug`: getMe / getUpdates izohi, 409 matnlari AYNAN (eskisidek), tarmoq xatosida token YO'Q;
  D — umumiy bot ulash / uzish (production): 401 / 404 / 429 / «noma'lum sabab» / tarmoq / tarmoq EMAS xato;
  E — korxona boti «🔗 Botni ulash»: 401 — mijozga «Bot tokeni» maydoni va «Botni ulash» maslahati, Railway / TELEGRAM_BOT_TOKEN
      YO'Q; bad webhook; tarmoq (502); token javobda YO'Q;
  F — users.html: oxirgi xato izohi ko'rsatiladi (statik).
Telegram'ga HECH NARSA chiqmaydi: `urllib.request.urlopen` soxtasi hamma so'rovni yozib oladi.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 154) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_telegram_xato_izoh.py
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "telegram_xato155_test"
_DB = os.path.join(tempfile.gettempdir(), "telegram_xato155_test.db")
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

UMUMIY_TOKEN = "111111111:UMUMIYbotTOKENi_xxxxxxxxxxxxxxxxxxxxxx"     # @BotFather ko'rinishida (35 belgi)
UMUMIY_SIR = "UMUMIY_WEBHOOK_SIRI_155"
B_TOKEN = "222222222:BkorxonaTOKENi_yyyyyyyyyyyyyyyyyyyyyyy"
os.environ["TELEGRAM_BOT_TOKEN"] = UMUMIY_TOKEN
os.environ["TELEGRAM_WEBHOOK_SECRET"] = UMUMIY_SIR
SIR_K = "telegram_webhook_secret"
os.environ.pop("RAILWAY_ENVIRONMENT_NAME", None)
os.environ.pop("RAILWAY_ENVIRONMENT", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

import io                                          # noqa: E402
import json                                        # noqa: E402
import contextlib                                  # noqa: E402
import urllib.request                              # noqa: E402
import urllib.error                                # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User                  # noqa: E402
from production_models import Company              # noqa: E402
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


def muhit(nom):
    if nom is None:
        os.environ.pop("RAILWAY_ENVIRONMENT_NAME", None)
    else:
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = nom


def fn(nom):
    """Yangi yordamchi (asl kodda yo'q bo'lsa — chaqiruv xato beradi, `check` uni yiqilish deb yozadi, sinov QULAMAYDI)."""
    f = getattr(main, nom, None)
    if f is None:
        raise AttributeError(f"main.{nom} yo'q")
    return f


# ══════════════════════════════════════════════════════════════
# Soxta Telegram — hamma so'rov yoziladi; javob metod (va token) bo'yicha
# ══════════════════════════════════════════════════════════════
CHAQ = []          # (token, metod)
JAVOB = {}         # metod → natija | {"_tana": to'liq JSON} | bytes | Exception | callable() → Exception
JAVOB_T = {}       # (token, metod) → ustun


class _Javob:
    def __init__(self, bayt):
        self._t = bayt

    def read(self):
        return self._t

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_xato(kod, tavsif):
    """Telegram'ning HAQIQIY rad javobi shakli (08.10 o'lchovi): HTTP kod + {"ok":false,"error_code":kod,"description":…}."""
    return lambda: urllib.error.HTTPError("https://api.telegram.org/x", kod, "xato", {},
                                          io.BytesIO(json.dumps({"ok": False, "error_code": kod,
                                                                 "description": tavsif}).encode()))


def _soxta_urlopen(so_rov, timeout=None, **k):
    url = getattr(so_rov, "full_url", so_rov if isinstance(so_rov, str) else "")
    qism = url.split("/bot", 1)[1] if "/bot" in url else ""
    token = qism.split("/", 1)[0]
    metod = qism.split("/", 1)[1].split("?", 1)[0] if "/" in qism else ""
    CHAQ.append((token, metod))
    v = JAVOB_T.get((token, metod), JAVOB.get(metod, True))
    if callable(v):
        v = v()
    if isinstance(v, Exception):
        raise v
    if isinstance(v, (bytes, bytearray)):
        return _Javob(bytes(v))
    if isinstance(v, dict) and "_tana" in v:
        return _Javob(json.dumps(v["_tana"]).encode())
    return _Javob(json.dumps({"ok": True, "result": v}).encode())


urllib.request.urlopen = _soxta_urlopen


def metodlar():
    return [m for _, m in CHAQ]


ME = {"id": 8606089235, "is_bot": True, "first_name": "Usta kabinet", "username": "Penoustabot"}


def tikla():
    """Har bo'lim boshida — soxta Telegram «hammasi joyida» holatiga."""
    JAVOB.clear()
    JAVOB_T.clear()
    CHAQ.clear()
    JAVOB["getMe"] = ME
    JAVOB["getWebhookInfo"] = {"url": "https://testserver/telegram/webhook", "pending_update_count": 0}


# ══════════════════════════════════════════════════════════════
# Fikstura: 1 — platforma egasi, 2 — mijoz B
# ══════════════════════════════════════════════════════════════
db = SessionLocal()
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="BBB_XATO_KORXONA"))
db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "tx_plat", "Parol123!", UserRole.ADMIN, "TX Platforma", company_id=1)
    auth.create_user(db, "tx_b_adm", "Parol123!", UserRole.ADMIN, "TX B admin", company_id=2)
db.query(User).filter(User.username == "tx_plat").first().is_platform_admin = True
db.commit()
db.close()


def kirgan(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    assert r.status_code == 302, f"{login} kirmadi: {r.status_code}"
    return c


CP, CB = kirgan("tx_plat"), kirgan("tx_b_adm")


def sozlama(cid, kalit):
    s = SessionLocal()
    try:
        return crud.get_setting(s, kalit, "", company_id=cid) or ""
    finally:
        s.close()


TOKEN_401 = "Telegram bu bot tokenini qabul qilmadi"
TOKEN_404 = "Telegram bunday botni topmadi"
RAILWAY_QOY = "Railway → Variables → TELEGRAM_BOT_TOKEN ga qo'ying"
SINOV_QOYMANG = "asosiy botning tokenini bu yerga QO'YMANG"
KORXONA_MASLAHAT = "«Bot tokeni» maydoniga yozing, «Saqlash» ni bosing, so'ng «🔗 Botni ulash» ni qayta bosing"
TARMOQ = "Server Telegram bilan bog'lana olmadi"
IZOH_409_WEBHOOK = ("Bot webhook rejimida ishlayapti — bu NORMAL (xabarlar saytga keladi). Qaysi saytga ulanganini «Bot hozir qayerga "
                    "ulangan» qatori ko'rsatadi.")
IZOH_409_BOSHQA = ("Shu token bilan BOSHQA dastur (alohida server) xabarlarni o'qiyapti — bot bu saytga emas, o'sha dasturga "
                   "ishlayapti.")

# ══════════════════════════════════════════════════════════════
section("A. Yordamchilar")
# ══════════════════════════════════════════════════════════════
muhit("production")
check("A1 401 (asosiy sayt): «qabul qilmadi» + Railway → TELEGRAM_BOT_TOKEN maslahati",
      lambda: TOKEN_401 in fn("_tg_xato_izohi")(401, "Unauthorized", "umumiy")
      and RAILWAY_QOY in fn("_tg_xato_izohi")(401, "Unauthorized", "umumiy"))
check("A2 404 (asosiy sayt): «bunday botni topmadi» + Railway maslahati",
      lambda: TOKEN_404 in fn("_tg_xato_izohi")(404, "Not Found", "umumiy") and RAILWAY_QOY in fn("_tg_xato_izohi")(404, "Not Found"))
check("A3 kod yo'q, faqat tavsif («Unauthorized» / «Not Found», katta-kichik harf farqsiz) — o'sha izohlar",
      lambda: TOKEN_401 in fn("_tg_xato_izohi")(None, "UNAUTHORIZED") and TOKEN_404 in fn("_tg_xato_izohi")("", " not found "))
check("A4 korxona joyi: «Bot tokeni» maydoni / «Botni ulash» maslahati, Railway / TELEGRAM_BOT_TOKEN YO'Q",
      lambda: KORXONA_MASLAHAT in fn("_tg_xato_izohi")(401, "Unauthorized", "korxona")
      and "Railway" not in fn("_tg_xato_izohi")(401, "Unauthorized", "korxona")
      and "TELEGRAM_BOT_TOKEN" not in fn("_tg_xato_izohi")(404, "Not Found", "korxona"))
muhit("sinov")
check("A5 SINOV saytida umumiy bot: «asosiy botning tokenini bu yerga QO'YMANG», Railway ga QO'YISH maslahati YO'Q",
      lambda: SINOV_QOYMANG in fn("_tg_xato_izohi")(404, "Not Found", "umumiy")
      and RAILWAY_QOY not in fn("_tg_xato_izohi")(404, "Not Found", "umumiy")
      and RAILWAY_QOY not in fn("_tg_xato_izohi")(401, "Unauthorized", "umumiy"))
muhit(None)
check("A5b muhit ANIQLANMAGAN (Railway dan tashqari) — ham sinov maslahati (asosiy emas)",
      lambda: SINOV_QOYMANG in fn("_tg_xato_izohi")(401, "Unauthorized", "umumiy"))
muhit("production")
check("A6 409 matnlari — eski `telegram-debug` izohlari bilan AYNAN",
      lambda: fn("_tg_xato_izohi")(409, "Conflict: can't use getUpdates method while webhook is active; use deleteWebhook to delete "
                                         "the webhook first") == IZOH_409_WEBHOOK
      and fn("_tg_xato_izohi")(409, "Conflict: terminated by other getUpdates request; make sure that only one bot instance is "
                                    "running") == IZOH_409_BOSHQA)
check("A7 429 «retry after 17» → «17 soniyadan keyin»; sonsiz → «birozdan keyin»",
      lambda: "17 soniyadan keyin" in fn("_tg_xato_izohi")(429, "Too Many Requests: retry after 17")
      and "birozdan keyin" in fn("_tg_xato_izohi")(429, "Too Many Requests"))
check("A8 «bad webhook» → «sayt manzili qabul qilinmadi»; 5xx → «Telegram serverida vaqtincha nosozlik»",
      lambda: "sayt manzili qabul qilinmadi" in fn("_tg_xato_izohi")(400, "Bad Request: bad webhook: HTTPS url must be provided for "
                                                                          "webhook")
      and "Telegram serverida vaqtincha nosozlik" in fn("_tg_xato_izohi")(502, "Bad Gateway"))
check("A9 tanilmagan (400 «chat not found», kod yo'q «Soxta») → bo'sh izoh; «Not Found: method» 404 kodisiz — tanilmaydi",
      lambda: fn("_tg_xato_izohi")(400, "Bad Request: chat not found") == "" and fn("_tg_xato_izohi")(None, "Soxta") == ""
      and fn("_tg_xato_izohi")(400, "Bad Request: not found here") == "")
check("A10 _tg_xato_matni: izoh + «(Telegram rad etdi: Unauthorized)»; tanilmagan — AYNAN «Telegram rad etdi: X»; bo'sh — «noma'lum sabab»",
      lambda: fn("_tg_xato_matni")(401, "Unauthorized", "umumiy").endswith(" (Telegram rad etdi: Unauthorized)")
      and fn("_tg_xato_matni")(401, "Unauthorized", "umumiy").startswith(TOKEN_401)
      and fn("_tg_xato_matni")(400, "Soxta rad") == "Telegram rad etdi: Soxta rad"
      and fn("_tg_xato_matni")(None, None) == "Telegram rad etdi: noma'lum sabab")
check("A10b kod satr ko'rinishida («401») ham, noto'g'ri kod («abc») — qulamaydi",
      lambda: TOKEN_401 in fn("_tg_xato_izohi")("401", "x") and fn("_tg_xato_izohi")("abc", "x") == "")
_u = urllib.error.URLError(f"https://api.telegram.org/bot{UMUMIY_TOKEN}/getMe timed out")
check("A11 tarmoq (URLError, TimeoutError) → «Server Telegram bilan bog'lana olmadi» + «(Telegram bilan bog'lanishda xato: …)», token «…»",
      lambda: fn("_tg_tarmoq_xato_matni")(_u, UMUMIY_TOKEN).startswith(TARMOQ)
      and "(Telegram bilan bog'lanishda xato: " in fn("_tg_tarmoq_xato_matni")(_u, UMUMIY_TOKEN)
      and UMUMIY_TOKEN not in fn("_tg_tarmoq_xato_matni")(_u, UMUMIY_TOKEN)
      and fn("_tg_tarmoq_xato_matni")(TimeoutError("timed out"), "").startswith(TARMOQ))
check("A12 tarmoq EMAS xato (ValueError — javob o'qilmadi) → «tarmoq» deb atalmaydi, eskisidek xom matn",
      lambda: fn("_tg_tarmoq_xato_matni")(ValueError("buzuq JSON"), "") == "Telegram bilan bog'lanishda xato: buzuq JSON")
check("A13 oxirgi xato: 403 → «maxfiy imzo … mos kelmadi»; 502 → «javob bermadi (502)»; 503; 404; 500; boshqa kod",
      lambda: "maxfiy imzo (TELEGRAM_WEBHOOK_SECRET)" in fn("_tg_webhook_xato_izohi")("Wrong response from the webhook: 403 Forbidden")
      and "javob bermadi (502)" in fn("_tg_webhook_xato_izohi")("Wrong response from the webhook: 502 Bad Gateway")
      and "(503)" in fn("_tg_webhook_xato_izohi")("Wrong response from the webhook: 503 Service Unavailable")
      and "topilmadi (404)" in fn("_tg_webhook_xato_izohi")("Wrong response from the webhook: 404 Not Found")
      and "ichki xato bo'ldi (500)" in fn("_tg_webhook_xato_izohi")("Wrong response from the webhook: 500 Internal Server Error")
      and "(418)" in fn("_tg_webhook_xato_izohi")("Wrong response from the webhook: 418 I'm a teapot"))
check("A14 oxirgi xato: vaqt tugadi / domen / SSL / rad etdi; tanilmagan va bo'sh → bo'sh",
      lambda: fn("_tg_webhook_xato_izohi")("Connection timed out") == "sayt o'z vaqtida javob bermadi"
      and fn("_tg_webhook_xato_izohi")("Read timeout expired") == "sayt o'z vaqtida javob bermadi"
      and "domen" in fn("_tg_webhook_xato_izohi")("Failed to resolve host: Name or service not known")
      and "SSL" in fn("_tg_webhook_xato_izohi")("SSL error {error:0A000086:SSL routines}")
      and fn("_tg_webhook_xato_izohi")("Connection refused") == "sayt ulanishni rad etdi"
      and fn("_tg_webhook_xato_izohi")("Boshqa narsa") == "" and fn("_tg_webhook_xato_izohi")(None) == "")


def _rad(kod):
    return fn("TelegramRad")("Unauthorized", kod=kod).kod


check("A15 TelegramRad: `kod` maydoni (401), kodsiz — None; matn — tavsif",
      lambda: _rad(401) == 401 and fn("TelegramRad")("x").kod is None and str(fn("TelegramRad")("Not Found", kod=404)) == "Not Found")
tikla()
JAVOB["getMe"] = http_xato(404, "Not Found")
try:
    main._tg_api(UMUMIY_TOKEN, "getMe")
    _ta = None
except Exception as _e:                    # noqa: BLE001
    _ta = (type(_e).__name__, getattr(_e, "kod", "kod_yoq"), str(_e))
check("A16 _tg_api: HTTP 404 → TelegramRad(kod=404, «Not Found»)", _ta == ("TelegramRad", 404, "Not Found"), _ta)
JAVOB["getMe"] = {"_tana": {"ok": False, "error_code": 401, "description": "Unauthorized"}}
try:
    main._tg_api(UMUMIY_TOKEN, "getMe")
    _ta = None
except Exception as _e:                    # noqa: BLE001
    _ta = (type(_e).__name__, getattr(_e, "kod", "kod_yoq"), str(_e))
check("A17 _tg_api: 200 + ok=false + error_code 401 → TelegramRad(kod=401)", _ta == ("TelegramRad", 401, "Unauthorized"), _ta)

# ══════════════════════════════════════════════════════════════
section("B. GET /api/system/telegram-webhook-info — «Bot hozir qayerga ulangan»")
# ══════════════════════════════════════════════════════════════
INFO = "/api/system/telegram-webhook-info"
tikla()
muhit("production")
JAVOB["getMe"] = http_xato(401, "Unauthorized")
r = CP.get(INFO)
d = js(r)
check("B1 asosiy sayt, getMe 401 → holat «xato»: «Telegram bu bot tokenini qabul qilmadi … Railway → … TELEGRAM_BOT_TOKEN ga qo'ying "
      "(Telegram rad etdi: Unauthorized)»; token javobda YO'Q",
      d.get("holat") == "xato" and (d.get("xato") or "").startswith(TOKEN_401) and RAILWAY_QOY in (d.get("xato") or "")
      and (d.get("xato") or "").endswith("(Telegram rad etdi: Unauthorized)") and UMUMIY_TOKEN not in r.text, d)
JAVOB["getMe"] = http_xato(404, "Not Found")
d = js(CP.get(INFO))
check("B2 asosiy sayt, getMe 404 → «Telegram bunday botni topmadi … (Telegram rad etdi: Not Found)»",
      d.get("holat") == "xato" and (d.get("xato") or "").startswith(TOKEN_404)
      and (d.get("xato") or "").endswith("(Telegram rad etdi: Not Found)"), d)
muhit("sinov")
r = CP.get(INFO)
d = js(r)
check("B3 SINOV sayti (staging holati — 08.10 jonli «Not Found»): «asosiy botning tokenini bu yerga QO'YMANG», Railway ga QO'YISH "
      "maslahati YO'Q",
      d.get("holat") == "xato" and (d.get("xato") or "").startswith(TOKEN_404) and SINOV_QOYMANG in (d.get("xato") or "")
      and RAILWAY_QOY not in (d.get("xato") or "") and d.get("asosiy_muhit") is False, d)
muhit("production")
JAVOB["getMe"] = ME
JAVOB["getWebhookInfo"] = http_xato(401, "Unauthorized")
d = js(CP.get(INFO))
check("B4 getMe o'tdi, getWebhookInfo 401 → ham izoh", d.get("holat") == "xato" and (d.get("xato") or "").startswith(TOKEN_401), d)
JAVOB["getWebhookInfo"] = {"url": "https://testserver/telegram/webhook", "pending_update_count": 0}
JAVOB["getMe"] = {"_tana": {"ok": False, "error_code": 401, "description": "Unauthorized"}}
d = js(CP.get(INFO))
check("B5 200 + ok=false + error_code 401 (HTTP xatosiz) → izoh (kod javob tanasidan)",
      d.get("holat") == "xato" and (d.get("xato") or "").startswith(TOKEN_401), d)
JAVOB["getMe"] = http_xato(400, "Bad Request: soxta sabab")
d = js(CP.get(INFO))
check("B6 tanilmagan rad → eskisidek AYNAN «Telegram rad etdi: Bad Request: soxta sabab»",
      d.get("xato") == "Telegram rad etdi: Bad Request: soxta sabab", d)
JAVOB["getMe"] = http_xato(429, "Too Many Requests: retry after 9")
d = js(CP.get(INFO))
check("B7 429 → «9 soniyadan keyin qayta urinib ko'ring»", "9 soniyadan keyin qayta urinib ko'ring" in (d.get("xato") or ""), d)
JAVOB["getMe"] = urllib.error.URLError(f"https://api.telegram.org/bot{UMUMIY_TOKEN}/getMe timed out")
r = CP.get(INFO)
d = js(r)
check("B8 tarmoq xatosi → «Server Telegram bilan bog'lana olmadi … (Telegram bilan bog'lanishda xato: …)», token YO'Q",
      d.get("holat") == "xato" and (d.get("xato") or "").startswith(TARMOQ) and "bog'lanishda xato" in (d.get("xato") or "")
      and UMUMIY_TOKEN not in r.text, d)
JAVOB["getMe"] = ME
JAVOB["getWebhookInfo"] = {"url": "https://testserver/telegram/webhook", "pending_update_count": 1, "last_error_date": 1791457200,
                           "last_error_message": "Wrong response from the webhook: 403 Forbidden"}
d = js(CP.get(INFO))
_w = d.get("webhook") or {}
check("B9 oxirgi xato 403 → `last_error_izoh` «maxfiy imzo … mos kelmadi»; xom `last_error_message` o'zgarmagan; holat «mos»",
      d.get("holat") == "mos" and "maxfiy imzo (TELEGRAM_WEBHOOK_SECRET)" in (_w.get("last_error_izoh") or "")
      and _w.get("last_error_message") == "Wrong response from the webhook: 403 Forbidden", _w)
JAVOB["getWebhookInfo"] = {"url": "https://testserver/telegram/webhook", "pending_update_count": 0,
                           "last_error_message": "Boshqa <b>xato</b> matni"}
_w = js(CP.get(INFO)).get("webhook") or {}
check("B10 tanilmagan oxirgi xato → `last_error_izoh` bo'sh (kalit bor)", "last_error_izoh" in _w and _w.get("last_error_izoh") == "", _w)
JAVOB["getWebhookInfo"] = {"url": "https://testserver/telegram/webhook", "pending_update_count": 0}
_w = js(CP.get(INFO)).get("webhook") or {}
check("B11 xato yo'q → `last_error_izoh` bo'sh", "last_error_izoh" in _w and _w.get("last_error_izoh") == "", _w)

# ══════════════════════════════════════════════════════════════
section("C. GET /api/system/telegram-debug")
# ══════════════════════════════════════════════════════════════
DEBUG = "/api/system/telegram-debug"
tikla()
JAVOB["getMe"] = http_xato(404, "Not Found")
JAVOB["getUpdates"] = http_xato(404, "Not Found")
r = CP.get(DEBUG)
d = js(r)
check("C1 getMe 404 → bot_info_error (eskisidek «404»), bot_info_tavsif «Not Found», bot_info_izoh «bunday botni topmadi»",
      "404" in (d.get("bot_info_error") or "") and d.get("bot_info_tavsif") == "Not Found"
      and (d.get("bot_info_izoh") or "").startswith(TOKEN_404), d)
check("C2 getUpdates 404 → updates_error_izoh (ilgari bo'sh) «bunday botni topmadi»",
      (d.get("updates_error_izoh") or "").startswith(TOKEN_404) and d.get("updates_error_tavsif") == "Not Found", d)
JAVOB["getMe"] = ME
JAVOB["getUpdates"] = http_xato(401, "Unauthorized")
d = js(CP.get(DEBUG))
check("C3 getUpdates 401 → «qabul qilmadi»", (d.get("updates_error_izoh") or "").startswith(TOKEN_401), d)
JAVOB["getUpdates"] = http_xato(409, "Conflict: can't use getUpdates method while webhook is active; use deleteWebhook to delete "
                                     "the webhook first")
d1 = js(CP.get(DEBUG))
JAVOB["getUpdates"] = http_xato(409, "Conflict: terminated by other getUpdates request; make sure that only one bot instance is "
                                     "running")
d2 = js(CP.get(DEBUG))
check("C4 409 izohlari eskisidek AYNAN (webhook faol / boshqa dastur)",
      d1.get("updates_error_izoh") == IZOH_409_WEBHOOK and d2.get("updates_error_izoh") == IZOH_409_BOSHQA, (d1, d2))
JAVOB["getUpdates"] = http_xato(400, "Bad Request: soxta")
d = js(CP.get(DEBUG))
check("C5 tanilmagan → updates_error_izoh bo'sh (eskisidek)", d.get("updates_error_izoh") == "", d)
JAVOB["getMe"] = urllib.error.URLError(f"https://api.telegram.org/bot{UMUMIY_TOKEN}/getMe tarmoq yo'q")
JAVOB["getUpdates"] = urllib.error.URLError(f"https://api.telegram.org/bot{UMUMIY_TOKEN}/getUpdates tarmoq yo'q")
r = CP.get(DEBUG)
d = js(r)
check("C6 tarmoq xatosi (getMe, getUpdates) → izoh «Server Telegram bilan bog'lana olmadi»; matnda token BO'LSA HAM javobda YO'Q",
      (d.get("bot_info_izoh") or "").startswith(TARMOQ) and (d.get("updates_error_izoh") or "").startswith(TARMOQ)
      and UMUMIY_TOKEN not in r.text and "tarmoq yo'q" in (d.get("bot_info_error") or ""), r.text[:400])
JAVOB["getMe"] = b"buzuq-json"
JAVOB["getUpdates"] = b"buzuq-json"
d = js(CP.get(DEBUG))
check("C7 tarmoq EMAS xato (Telegram javobi o'qilmadi) → «tarmoq» deb atalmaydi (izoh bo'sh), xato matni bor",
      d.get("bot_info_izoh") == "" and d.get("updates_error_izoh") == "" and d.get("bot_info_error")
      and d.get("updates_error"), d)

# ══════════════════════════════════════════════════════════════
section("D. Umumiy bot — «🔐 Telegram xavfsizligini yoqish» / «🔄 Botni asl holatiga qaytarish» (asosiy sayt)")
# ══════════════════════════════════════════════════════════════
SETUP = "/api/system/telegram-setup-webhook-security"
DELETE = "/api/system/telegram-delete-webhook"
tikla()
muhit("production")
JAVOB["setWebhook"] = http_xato(401, "Unauthorized")
r = CP.post(SETUP)
check("D1 setup: setWebhook 401 → 400 «qabul qilmadi … Railway … TELEGRAM_BOT_TOKEN ga qo'ying (Telegram rad etdi: Unauthorized)»",
      r.status_code == 400 and js(r).get("detail", "").startswith(TOKEN_401) and RAILWAY_QOY in r.text
      and js(r).get("detail", "").endswith("(Telegram rad etdi: Unauthorized)") and UMUMIY_TOKEN not in r.text, (r.status_code, r.text[:300]))
JAVOB["deleteWebhook"] = http_xato(404, "Not Found")
r = CP.post(DELETE)
check("D2 delete: 404 → 400 «bunday botni topmadi … (Telegram rad etdi: Not Found)»",
      r.status_code == 400 and js(r).get("detail", "").startswith(TOKEN_404)
      and js(r).get("detail", "").endswith("(Telegram rad etdi: Not Found)"), (r.status_code, r.text[:300]))
JAVOB["setWebhook"] = {"_tana": {"ok": False, "error_code": 429, "description": "Too Many Requests: retry after 5"}}
r = CP.post(SETUP)
check("D3 setup: 200 + ok=false + error_code 429 → 400 «5 soniyadan keyin»", r.status_code == 400 and "5 soniyadan keyin" in r.text,
      (r.status_code, r.text[:300]))
JAVOB["deleteWebhook"] = {"_tana": {"ok": False}}
r = CP.post(DELETE)
check("D4 delete: ok=false, sababsiz → «Telegram rad etdi: noma'lum sabab» (ilgari «… None»)",
      r.status_code == 400 and js(r).get("detail") == "Telegram rad etdi: noma'lum sabab", (r.status_code, r.text[:300]))
JAVOB["setWebhook"] = urllib.error.URLError(f"https://api.telegram.org/bot{UMUMIY_TOKEN}/setWebhook tarmoq yo'q")
JAVOB["deleteWebhook"] = urllib.error.URLError(f"https://api.telegram.org/bot{UMUMIY_TOKEN}/deleteWebhook tarmoq yo'q")
r1, r2 = CP.post(SETUP), CP.post(DELETE)
check("D5 tarmoq xatosi (setup, delete) → 500 «Server Telegram bilan bog'lana olmadi», token YO'Q",
      r1.status_code == 500 and r2.status_code == 500 and js(r1).get("detail", "").startswith(TARMOQ)
      and js(r2).get("detail", "").startswith(TARMOQ) and UMUMIY_TOKEN not in r1.text + r2.text, (r1.text[:300], r2.text[:300]))
JAVOB["setWebhook"] = b"buzuq-json"
r = CP.post(SETUP)
check("D6 Telegram javobi o'qilmadi (tarmoq EMAS) → 500, «tarmoq» deb atalmaydi («Telegram bilan bog'lanishda xato: …»)",
      r.status_code == 500 and js(r).get("detail", "").startswith("Telegram bilan bog'lanishda xato: ")
      and TARMOQ not in r.text, (r.status_code, r.text[:300]))
muhit("sinov")
CHAQ.clear()
r = CP.post(SETUP)
check("D7 sinov saytida — eskisidek 409 (Telegram'ga so'rov YO'Q; izoh o'zgarishi himoyaga tegmadi)",
      r.status_code == 409 and not CHAQ, (r.status_code, metodlar()))
muhit("production")

# ══════════════════════════════════════════════════════════════
section("E. Korxona boti — «🔗 Botni ulash» (mijoz admini)")
# ══════════════════════════════════════════════════════════════
ULASH = "/api/settings/telegram-bot/ulash"
tikla()
r = CB.put("/api/settings/telegram-bot", data={"token": B_TOKEN, "chat_id": ""})
check("E0 B tokenni saqladi", r.status_code == 200, (r.status_code, r.text[:200]))
JAVOB_T[(B_TOKEN, "getMe")] = http_xato(401, "Unauthorized")
CHAQ.clear()
r = CB.post(ULASH)
_d = js(r).get("detail", "")
check("E1 getMe 401 → 400: «qabul qilmadi … «Bot tokeni» maydoniga yozing, «Saqlash» … «🔗 Botni ulash» … (Telegram rad etdi: "
      "Unauthorized)»; Railway / TELEGRAM_BOT_TOKEN YO'Q (mijozga tegishli emas); B tokeni YO'Q; ulanmadi",
      r.status_code == 400 and _d.startswith(TOKEN_401) and KORXONA_MASLAHAT in _d and _d.endswith("(Telegram rad etdi: Unauthorized)")
      and "Railway" not in _d and "TELEGRAM_BOT_TOKEN" not in _d and B_TOKEN not in r.text and not sozlama(2, SIR_K)
      and metodlar() == ["getMe"], (r.status_code, _d, metodlar()))
JAVOB_T[(B_TOKEN, "getMe")] = {"id": 222222222, "is_bot": True, "first_name": "B bot", "username": "b_xato_bot"}
JAVOB_T[(B_TOKEN, "setWebhook")] = http_xato(400, "Bad Request: bad webhook: HTTPS url must be provided for webhook")
r = CB.post(ULASH)
check("E2 setWebhook «bad webhook» → 400 «sayt manzili qabul qilinmadi … (Telegram rad etdi: Bad Request: bad webhook: …)», ulanmadi",
      r.status_code == 400 and "sayt manzili qabul qilinmadi" in r.text and "bad webhook" in r.text and not sozlama(2, SIR_K),
      (r.status_code, r.text[:300]))
JAVOB_T[(B_TOKEN, "setWebhook")] = urllib.error.URLError(f"tarmoq yo'q ({B_TOKEN})")
r = CB.post(ULASH)
check("E3 tarmoq xatosi → 502 «Server Telegram bilan bog'lana olmadi», B tokeni YO'Q",
      r.status_code == 502 and js(r).get("detail", "").startswith(TARMOQ) and B_TOKEN not in r.text, (r.status_code, r.text[:300]))
JAVOB_T.pop((B_TOKEN, "setWebhook"), None)
r = CB.post(ULASH)
check("E4 Telegram qabul qilsa — eskisidek «✅ Bot ulandi: @b_xato_bot → …»",
      r.status_code == 200 and js(r).get("message") == "✅ Bot ulandi: @b_xato_bot → https://testserver/telegram/webhook/2", r.text[:300])

# ══════════════════════════════════════════════════════════════
section("F. Sahifa (statik)")
# ══════════════════════════════════════════════════════════════
_uh = open(os.path.join(ROOT, "templates", "users.html"), encoding="utf-8").read()
check("F1 users.html: oxirgi xato — `last_error_izoh` ko'rsatiladi, xom matn «(Telegram: …)» qavsda, escapeHtml bilan",
      "d.webhook.last_error_izoh" in _uh and "' (Telegram: ' + escapeHtml(d.webhook.last_error_message) + ')'" in _uh)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
