#!/usr/bin/env python3
"""
test_telegram_webhook.py — kech130 (zip 154): Telegram bot MANZILI himoyasi, holati va HAR KORXONAGA O'Z BOTI.

NIMA UCHUN KERAK (kech129 da O'LCHANGAN, 08.10)
---------------------------------------------
  1. «🔐 Telegram xavfsizligini yoqish» (`POST /api/system/telegram-setup-webhook-security`) qaysi saytda bosilsa, umumiy bot
     (@Penoustabot) o'sha saytga ulanadi. Staging va production bir xil tokenda bo'lganda staging dagi tugma production botini
     «o'g'irlagan» — ustalar xabarlari sinov saytiga borgan (staging logi `POST /telegram/webhook 200`, production logida yo'q).
     «Botni asl holatiga qaytarish» (`telegram-delete-webhook`) ham sinov saytidan production botini to'xtatardi.
  2. Bot hozir qayerga ulanganini ko'rishning yo'li yo'q edi (faqat Railway loglari); `telegram-debug` 409 sababini yutardi.
  3. EGASI QARORI (08.10 17:42): «Ulanmasin penoustabotga — u faqat men uchun bo'lsin» — asl kodda usta umumiy botda HAMMA
     korxonadan qidirilardi: mijoz korxona ustasi o'z korxonasi nomi, bonusi va sovg'a davrini @Penoustabot da ko'rardi.
  4. Korxona boti faqat CHIQUVCHI xabar yuborardi; ustalar menyusi (kiruvchi) korxona botida yo'q edi (egasi 08.10 17:34:
     «korxonalar uchun alohida bot»; mijoz O'ZI ulaydi).

BO'LIMLAR
  A — umumiy bot: ulash / uzish FAQAT asosiy muhitda (Railway «production»), aks holda 409 va Telegram'ga so'rov YO'Q;
  B — `GET /api/system/telegram-webhook-info` (faqat platforma admini, faqat o'qish; token / sir / IP javobda YO'Q);
  C — `telegram-debug` 409 tavsifi (webhook faol ↔ boshqa dastur getUpdates);
  D — umumiy bot FAQAT platforma korxonasi ustalariga;
  E — korxona botini ulash (`POST /api/settings/telegram-bot/ulash`): muhit, ruxsat, token tekshiruvlari, Telegram so'rovlari;
  F — korxona boti webhooki (`POST /telegram/webhook/<id>`): sir, korxona chegarasi, javob shu korxona tokeni bilan;
  G — token almashsa / tozalansa — eski bot uziladi (faqat asosiy muhitda va faqat bot AYNAN shu manzilda bo'lsa);
  H — sahifalar (statik + HTTP) va olib tashlangan `GET /api/cron/find-chat-id`.
Telegram'ga HECH NARSA chiqmaydi: `urllib.request.urlopen` soxtasi hamma so'rovni yozib oladi.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 153) qarshi YIQILADI (QULAMAYDI): A1–A3, B, C1/C2, D1–D3, E, F, G, H3/H4.
ISHLATISH: python3 tools/test_telegram_webhook.py
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "telegram_webhook154_test"
_DB = os.path.join(tempfile.gettempdir(), "telegram_webhook154_test.db")
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

UMUMIY_TOKEN = "111111111:UMUMIYbotTOKENi_aaaaaaaaaaaaaaaaaaaaaa"     # @BotFather ko'rinishida (35 belgi)
UMUMIY_SIR = "UMUMIY_WEBHOOK_SIRI_154"
B_TOKEN = "222222222:BkorxonaTOKENi_bbbbbbbbbbbbbbbbbbbbbbb"
B_TOKEN2 = "222222223:BkorxonaYANGItoken_cccccccccccccccccccc"
C_TOKEN = "333333333:CkorxonaTOKENi_ddddddddddddddddddddddd"
os.environ["TELEGRAM_BOT_TOKEN"] = UMUMIY_TOKEN
os.environ["TELEGRAM_WEBHOOK_SECRET"] = UMUMIY_SIR
# korxona boti ulanishi — korxona sozlamalari kalitlari (main.TG_KORXONA_*; asl kodda yo'q — test QULAMASLIGI uchun shu yerda)
SIR_K, URL_K, BOT_K = "telegram_webhook_secret", "telegram_webhook_url", "telegram_bot_username"
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
from models import UserRole, User, Master, ActivityLog   # noqa: E402
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
    """Railway muhit nomi (None — o'zgaruvchi yo'q)."""
    if nom is None:
        os.environ.pop("RAILWAY_ENVIRONMENT_NAME", None)
    else:
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = nom


# ══════════════════════════════════════════════════════════════
# Soxta Telegram — hamma so'rov yoziladi; javob metod (va token) bo'yicha
# ══════════════════════════════════════════════════════════════
CHAQ = []          # (token, metod, tana(dict), timeout)
YUB = []           # sendMessage: (token, chat_id, matn)
JAVOB = {}         # metod → natija / Exception / callable() → Exception
JAVOB_T = {}       # (token, metod) → ustun


class _Javob:
    def __init__(self, tana):
        self._t = json.dumps(tana).encode()

    def read(self):
        return self._t

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_xato(kod, tavsif):
    return lambda: urllib.error.HTTPError("https://api.telegram.org/x", kod, "xato", {},
                                          io.BytesIO(json.dumps({"ok": False, "error_code": kod,
                                                                 "description": tavsif}).encode()))


def _soxta_urlopen(so_rov, timeout=None, **k):
    url = getattr(so_rov, "full_url", so_rov if isinstance(so_rov, str) else "")
    qism = url.split("/bot", 1)[1] if "/bot" in url else ""
    token = qism.split("/", 1)[0]
    metod = qism.split("/", 1)[1].split("?", 1)[0] if "/" in qism else ""
    tana = {}
    _d = getattr(so_rov, "data", None)
    if isinstance(_d, (bytes, bytearray)) and _d:
        try:
            tana = json.loads(_d.decode("utf-8"))
        except Exception:                  # noqa: BLE001
            tana = {"_xom": True}
    CHAQ.append((token, metod, tana, timeout))
    if metod == "sendMessage":
        YUB.append((token, str(tana.get("chat_id")), tana.get("text", "")))
        return _Javob({"ok": True, "result": {"message_id": 1}})
    v = JAVOB_T.get((token, metod), JAVOB.get(metod, True))
    if callable(v):
        v = v()
    if isinstance(v, Exception):
        raise v
    return _Javob({"ok": True, "result": v})


urllib.request.urlopen = _soxta_urlopen


def chaq_tozala():
    CHAQ.clear()
    YUB.clear()


def metodlar():
    return [m for _, m, _, _ in CHAQ if m != "sendMessage"]


# ══════════════════════════════════════════════════════════════
# Fikstura: 1 — platforma egasi (PenoDecorPro), 2 — mijoz B, 3 — mijoz C
# ══════════════════════════════════════════════════════════════
db = SessionLocal()
for _cid, _nm in ((2, "BBB_KORXONA"), (3, "CCC_KORXONA")):
    if not db.query(Company).filter(Company.id == _cid).first():
        db.add(Company(id=_cid, name=_nm))
db.commit()
A_NOM = (db.query(Company).filter(Company.id == 1).first().name or "").strip()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "tw_plat", "Parol123!", UserRole.ADMIN, "TW Platforma", company_id=1)
    auth.create_user(db, "tw_a_adm", "Parol123!", UserRole.ADMIN, "TW A admin", company_id=1)
    auth.create_user(db, "tw_b_adm", "Parol123!", UserRole.ADMIN, "TW B admin", company_id=2)
    auth.create_user(db, "tw_b_men", "Parol123!", UserRole.MANAGER, "TW B menejer", company_id=2)
    auth.create_user(db, "tw_c_adm", "Parol123!", UserRole.ADMIN, "TW C admin", company_id=3)
db.query(User).filter(User.username == "tw_plat").first().is_platform_admin = True
db.commit()
db.add_all([
    Master(company_id=1, name="USTA_BIR", phone="+998900015401", telegram_id="901", is_active=True),
    Master(company_id=2, name="USTA_IKKI", phone="+998900015402", telegram_id="902", is_active=True),
    Master(company_id=1, name="USTA_UCH_A", phone="+998900015403", telegram_id="903", is_active=True),
    Master(company_id=2, name="USTA_UCH_B", phone="+998900015404", telegram_id="903", is_active=True),
])
db.commit()
_mid = {m.name: m.id for m in db.query(Master).all()}
_fx_xato = None
try:
    with contextlib.redirect_stdout(_quiet):
        crud.open_gift_period(db, [{"gift_name": "A_SOVGA_X", "threshold_amount": 1000000}], master_ids=[_mid["USTA_BIR"]],
                              performed_by="t", company_id=1)
        crud.open_gift_period(db, [{"gift_name": "B_SOVGA_X", "threshold_amount": 2000000}], master_ids=[_mid["USTA_IKKI"]],
                              performed_by="t", company_id=2)
except Exception as e:                     # noqa: BLE001
    _fx_xato = f"{type(e).__name__}: {e}"
db.close()


def kirgan(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    assert r.status_code == 302, f"{login} kirmadi: {r.status_code}"
    return c


CP, CA, CB, CBM, CC = (kirgan(u) for u in ("tw_plat", "tw_a_adm", "tw_b_adm", "tw_b_men", "tw_c_adm"))
C0 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
WH = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)


def sozlama(cid, kalit):
    s = SessionLocal()
    try:
        return crud.get_setting(s, kalit, "", company_id=cid) or ""
    finally:
        s.close()


def wh(yol, sir, chat, matn):
    """Telegram'dan kelgandek xabar → (status, [(token, matn)] shu chatga)."""
    YUB.clear()
    h = {} if sir is None else {"X-Telegram-Bot-Api-Secret-Token": sir}
    with contextlib.redirect_stdout(_quiet):
        r = WH.post(yol, json={"update_id": 1, "message": {"chat": {"id": int(chat)}, "text": matn}}, headers=h)
    return r.status_code, [(t, x) for t, ch, x in YUB if ch == str(chat)]


section("0. Fikstura")
check("0.1 korxonalar, 5 foydalanuvchi, 4 usta (903 — ikki korxonada), sovg'a davrlari (A, B)",
      _fx_xato is None and A_NOM and len(_mid) == 4, (_fx_xato, A_NOM, _mid))
_s = SessionLocal()
check("0.2 platforma korxonalari = {1} (umumiy bot shularga)", lambda: main._umumiy_bot_korxonalari(_s) == {1},
      getattr(main, "_umumiy_bot_korxonalari", None))
_s.close()

# ══════════════════════════════════════════════════════════════
section("A. Umumiy bot — ulash / uzish FAQAT asosiy muhitda")
# ══════════════════════════════════════════════════════════════
SETUP = "/api/system/telegram-setup-webhook-security"
DELETE = "/api/system/telegram-delete-webhook"
for _mn, _ism, _k in ((None, "«aniqlanmadi»", "A1"), ("sinov", "«sinov»", "A2"), ("Production", "«Production»", "A2b"),
                      ("staging", "«staging»", "A2c")):
    muhit(_mn)
    chaq_tozala()
    r = CP.post(SETUP)
    check(f"{_k} setup: muhit {_ism} → 409 «asosiy sayt emas … {_ism}», Telegram'ga so'rov YO'Q",
          r.status_code == 409 and "asosiy sayt emas" in r.text and _ism in r.text and not CHAQ,
          (r.status_code, r.text[:200], metodlar()))
for _mn in (None, "sinov"):
    muhit(_mn)
    chaq_tozala()
    r = CP.post(DELETE)
    check(f"A3 delete: muhit {_mn!r} → 409, Telegram'ga so'rov YO'Q (sinov saytidan production botini to'xtatmaydi)",
          r.status_code == 409 and "asosiy sayt emas" in r.text and not CHAQ, (r.status_code, r.text[:200], metodlar()))
muhit("production")
chaq_tozala()
r1, r2 = CA.post(SETUP), CA.post(DELETE)
check("A4 korxona admini (platforma emas), production → setup / delete 403, so'rov YO'Q",
      r1.status_code == 403 and r2.status_code == 403 and not CHAQ, (r1.status_code, r2.status_code, metodlar()))
JAVOB["getWebhookInfo"] = {"url": "https://web-sinov.up.railway.app/telegram/webhook", "pending_update_count": 3}
chaq_tozala()
r = CP.post(SETUP)
d = js(r)
_sw = [t for _, m, t, _ in CHAQ if m == "setWebhook"]
check("A5 production → 200; Telegram: getWebhookInfo, keyin setWebhook (shu sayt manzili + javobdagi yangi sir)",
      r.status_code == 200 and metodlar() == ["getWebhookInfo", "setWebhook"] and _sw
      and _sw[0].get("url") == "https://testserver/telegram/webhook" and _sw[0].get("secret_token") == d.get("new_secret")
      and len(d.get("new_secret") or "") >= 40 and d.get("webhook_url") == "https://testserver/telegram/webhook",
      (r.status_code, metodlar(), _sw, d))
check("A5b javobda bot OLDIN qayerga ulangani (oldingi_url — sinov sayti)",
      d.get("oldingi_url") == "https://web-sinov.up.railway.app/telegram/webhook", d)
check("A5c setWebhook so'rovi umumiy bot tokeni bilan; javobda token YO'Q",
      [t for t, m, _, _ in CHAQ] == [UMUMIY_TOKEN, UMUMIY_TOKEN] and UMUMIY_TOKEN not in r.text, [t for t, m, _, _ in CHAQ])
JAVOB["getWebhookInfo"] = http_xato(401, "Unauthorized")
chaq_tozala()
r = CP.post(SETUP)
check("A6 getWebhookInfo xato bersa ham ulash davom etadi (oldingi_url = null), setWebhook yuborildi",
      r.status_code == 200 and js(r).get("oldingi_url") is None and metodlar() == ["getWebhookInfo", "setWebhook"],
      (r.status_code, r.text[:200], metodlar()))
JAVOB.pop("getWebhookInfo", None)
chaq_tozala()
r = CP.post(DELETE)
check("A7 delete, production → 200, BITTA so'rov deleteWebhook (eskisidek)",
      r.status_code == 200 and metodlar() == ["deleteWebhook"], (r.status_code, r.text[:200], metodlar()))

# ══════════════════════════════════════════════════════════════
section("B. GET /api/system/telegram-webhook-info — bot hozir qayerga ulangan")
# ══════════════════════════════════════════════════════════════
INFO = "/api/system/telegram-webhook-info"
r0, ra, rb = C0.get(INFO), CA.get(INFO), CB.get(INFO)
check("B1 kirmagan → 401; 1-korxona admini (platforma emas) → 403; mijoz admini → 403",
      r0.status_code == 401 and ra.status_code == 403 and rb.status_code == 403, (r0.status_code, ra.status_code, rb.status_code))
JAVOB["getMe"] = {"id": 8606089235, "is_bot": True, "first_name": "Usta kabinet", "username": "Penoustabot"}
JAVOB["getWebhookInfo"] = {"url": "https://testserver/telegram/webhook", "has_custom_certificate": False,
                           "pending_update_count": 2, "last_error_date": 1791457200,
                           "last_error_message": "Wrong response from the webhook: 403 Forbidden", "max_connections": 40,
                           "ip_address": "149.154.167.220", "allowed_updates": ["message"]}
muhit("production")
chaq_tozala()
r = CP.get(INFO)
d = js(r)
check("B2 mos: holat «mos», mos=true, bot @Penoustabot, muhit production, bu_sayt_url",
      r.status_code == 200 and d.get("holat") == "mos" and d.get("mos") is True
      and (d.get("bot") or {}).get("username") == "Penoustabot" and d.get("muhit") == "production"
      and d.get("asosiy_muhit") is True and d.get("bu_sayt_url") == "https://testserver/telegram/webhook"
      and d.get("token_sozlangan") is True and d.get("imzo_sozlangan") is True, d)
_w = d.get("webhook") or {}
check("B3 webhook: kutayotgan xabarlar 2, oxirgi xato matni va Toshkent vaqti (08.10.2026 16:00), max_connections",
      _w.get("pending_update_count") == 2 and "403 Forbidden" in (_w.get("last_error_message") or "")
      and _w.get("last_error_vaqt") == "08.10.2026 16:00" and _w.get("max_connections") == 40, _w)
check("B4 javobda TOKEN, webhook SIRI va Telegram IP manzili YO'Q (qiymat bo'yicha)",
      UMUMIY_TOKEN not in r.text and UMUMIY_SIR not in r.text and "149.154.167.220" not in r.text
      and "222222222" not in r.text, r.text[:300])
check("B5 faqat O'QISH: Telegram'ga getMe + getWebhookInfo (setWebhook / deleteWebhook YO'Q)",
      metodlar() == ["getMe", "getWebhookInfo"], metodlar())
JAVOB["getWebhookInfo"] = {"url": "https://web-sinov.up.railway.app/telegram/webhook", "pending_update_count": 0}
d = js(CP.get(INFO))
check("B6 boshqa saytga ulangan: holat «boshqa_sayt», mos=false, webhook.url — o'sha manzil",
      d.get("holat") == "boshqa_sayt" and d.get("mos") is False
      and (d.get("webhook") or {}).get("url") == "https://web-sinov.up.railway.app/telegram/webhook", d)
JAVOB["getWebhookInfo"] = {"url": "", "pending_update_count": 0}
d = js(CP.get(INFO))
check("B7 ulanmagan: holat «ulanmagan»", d.get("holat") == "ulanmagan" and d.get("mos") is False, d)
muhit("sinov")
d = js(CP.get(INFO))
check("B8 sinov saytida ham O'QISH ishlaydi: asosiy_muhit=false, muhit «sinov»",
      d.get("asosiy_muhit") is False and d.get("muhit") == "sinov" and d.get("holat") == "ulanmagan", d)
muhit("production")
JAVOB["getMe"] = http_xato(401, "Unauthorized")
r = CP.get(INFO)
d = js(r)
check("B9 Telegram tokenni rad etsa: holat «xato», sabab «Unauthorized», token YO'Q",
      d.get("holat") == "xato" and "Unauthorized" in (d.get("xato") or "") and UMUMIY_TOKEN not in r.text, d)
JAVOB["getMe"] = urllib.error.URLError(f"https://api.telegram.org/bot{UMUMIY_TOKEN}/getMe ulanmadi")
r = CP.get(INFO)
d = js(r)
check("B10 tarmoq xatosi matnida token bo'lsa ham javobda token YO'Q («…»)",
      d.get("holat") == "xato" and "bog'lanishda xato" in (d.get("xato") or "") and UMUMIY_TOKEN not in r.text, d)
JAVOB["getMe"] = {"id": 8606089235, "is_bot": True, "first_name": "Usta kabinet", "username": "Penoustabot"}
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
chaq_tozala()
d = js(CP.get(INFO))
check("B11 shu saytda token yo'q: holat «token_yoq», Telegram'ga so'rov YO'Q",
      d.get("holat") == "token_yoq" and d.get("token_sozlangan") is False and not CHAQ, (d, metodlar()))
os.environ["TELEGRAM_BOT_TOKEN"] = UMUMIY_TOKEN

# ══════════════════════════════════════════════════════════════
section("C. telegram-debug — 409 sababi")
# ══════════════════════════════════════════════════════════════
JAVOB["getUpdates"] = http_xato(409, "Conflict: can't use getUpdates method while webhook is active; use deleteWebhook to "
                                     "delete the webhook first")
r = CP.get("/api/system/telegram-debug")
d = js(r)
check("C1 webhook faol: updates_error (eskisidek «HTTP Error 409»), updates_error_tavsif — Telegram sababi, izoh «webhook rejimida»",
      "409" in (d.get("updates_error") or "") and "webhook is active" in (d.get("updates_error_tavsif") or "")
      and "webhook rejimida" in (d.get("updates_error_izoh") or ""), d)
JAVOB["getUpdates"] = http_xato(409, "Conflict: terminated by other getUpdates request; make sure that only one bot instance "
                                     "is running")
d = js(CP.get("/api/system/telegram-debug"))
check("C2 boshqa dastur o'qiyapti: izoh «BOSHQA dastur»", "BOSHQA dastur" in (d.get("updates_error_izoh") or ""), d)
check("C3 debug javobida token YO'Q", UMUMIY_TOKEN not in CP.get("/api/system/telegram-debug").text)
JAVOB.pop("getUpdates", None)

# ══════════════════════════════════════════════════════════════
section("D. Umumiy bot (@Penoustabot) — FAQAT platforma korxonasi ustalari (egasi QARORI 08.10 17:42)")
# ══════════════════════════════════════════════════════════════
GW = "/telegram/webhook"
st, t = wh(GW, UMUMIY_SIR, "902", "/start")
_m = " | ".join(x for _, x in t)
check("D1 B ustasi umumiy botda /start → javob bor, lekin B korxona nomi YO'Q (bot egasi nomi), umumiy token bilan",
      st == 200 and len(t) == 1 and "BBB_KORXONA" not in _m and A_NOM in _m and t[0][0] == UMUMIY_TOKEN, (st, t))
st, t = wh(GW, UMUMIY_SIR, "902", "💰 Bonuslarim")
_m = " | ".join(x for _, x in t)
check("D2 B ustasi «💰 Bonuslarim» → «topilmadingiz», B usta ismi / korxona nomi YO'Q",
      st == 200 and "topilmadingiz" in _m and "USTA_IKKI" not in _m and "BBB_KORXONA" not in _m, _m[:300])
st, t = wh(GW, UMUMIY_SIR, "902", "🎁 Sovg'alar")
_m = " | ".join(x for _, x in t)
check("D3 B ustasi «🎁 Sovg'alar» → B sovg'a davri (B_SOVGA_X) YO'Q", st == 200 and "B_SOVGA_X" not in _m
      and "USTA_IKKI" not in _m and "topilmadingiz" in _m, _m[:300])
st, t = wh(GW, UMUMIY_SIR, "901", "/bonus")
_m1 = " | ".join(x for _, x in t)
st2, t2 = wh(GW, UMUMIY_SIR, "901", "/sovgalar")
_m2 = " | ".join(x for _, x in t2)
check("D4 platforma korxonasi ustasi — eskisidek: bonus (USTA_BIR), sovg'a (A_SOVGA_X)",
      "USTA_BIR" in _m1 and "A_SOVGA_X" in _m2 and "B_SOVGA_X" not in _m2, (_m1[:200], _m2[:200]))
st, t = wh(GW, UMUMIY_SIR, "903", "/bonus")
_m = " | ".join(x for _, x in t)
check("D5 ikki korxonada ro'yxatdagi usta — umumiy botda FAQAT platforma korxonasidagi yozuvi (USTA_UCH_A), «bir nechta» YO'Q",
      "USTA_UCH_A" in _m and "USTA_UCH_B" not in _m and "bir nechta" not in _m, _m[:300])
st, t = wh(GW, UMUMIY_SIR, "902", "🪪 Mening ID raqamim")
check("D6 «🪪 Mening ID raqamim» — eskisidek (chat ID, umumiy token)",
      len(t) == 1 and "`902`" in t[0][1] and t[0][0] == UMUMIY_TOKEN, t)
st, _ = wh(GW, "noto'g'ri", "901", "/start")
st2, _ = wh(GW, None, "901", "/start")
check("D7 umumiy webhook: noto'g'ri / yo'q imzo → 403 (eskisidek)", st == 403 and st2 == 403, (st, st2))

# ══════════════════════════════════════════════════════════════
section("E. Korxona botini ulash — POST /api/settings/telegram-bot/ulash")
# ══════════════════════════════════════════════════════════════
ULASH = "/api/settings/telegram-bot/ulash"
r = CB.put("/api/settings/telegram-bot", data={"token": B_TOKEN, "chat_id": "-100500"})
d = js(CB.get("/api/settings/telegram-bot"))
check("E0 B tokenni saqladi: configured, ulangan=false, bot nomi / manzil bo'sh",
      r.status_code == 200 and d.get("configured") is True and d.get("ulangan") is False and d.get("bot_username") == ""
      and d.get("webhook_url") == "", (r.status_code, d))
for _mn, _k in ((None, "E1"), ("sinov", "E1b")):
    muhit(_mn)
    chaq_tozala()
    r = CB.post(ULASH)
    check(f"{_k} muhit {_mn!r} → 409 «asosiy sayt emas», Telegram'ga so'rov YO'Q, ulanmadi",
          r.status_code == 409 and "asosiy sayt emas" in r.text and not CHAQ and not sozlama(2, SIR_K),
          (r.status_code, r.text[:160], metodlar()))
check("E1c GET: sinov saytida asosiy_muhit=false (tugma o'chiq bo'ladi)", js(CB.get("/api/settings/telegram-bot")).get("asosiy_muhit") is False)
muhit("production")
chaq_tozala()
r0, rm = C0.post(ULASH), CBM.post(ULASH)
check("E2 kirmagan → 401; B menejeri (Sozlamalar: Tahrirlash yo'q) → 403; so'rov YO'Q",
      r0.status_code == 401 and rm.status_code == 403 and not CHAQ, (r0.status_code, rm.status_code))
JAVOB_T[(B_TOKEN, "getMe")] = {"id": 222222222, "is_bot": True, "first_name": "B bot", "username": "b_korxona_bot"}
chaq_tozala()
r = CB.post(ULASH)
d = js(r)
_sw = [(tk, t) for tk, m, t, _ in CHAQ if m == "setWebhook"]
_sir = sozlama(2, SIR_K)
check("E3 production → 200 «✅ Bot ulandi: @b_korxona_bot → https://testserver/telegram/webhook/2»",
      r.status_code == 200 and d.get("message") == "✅ Bot ulandi: @b_korxona_bot → https://testserver/telegram/webhook/2"
      and d.get("bot") == "@b_korxona_bot", (r.status_code, d))
check("E4 Telegram: getMe, setWebhook — B TOKENI bilan; url …/telegram/webhook/2, secret_token = bazadagi sir (≥40), "
      "allowed_updates [message]",
      metodlar() == ["getMe", "setWebhook"] and all(tk == B_TOKEN for tk, _, _, _ in CHAQ) and _sw
      and _sw[0][1].get("url") == "https://testserver/telegram/webhook/2" and _sw[0][1].get("secret_token") == _sir
      and len(_sir) >= 40 and _sw[0][1].get("allowed_updates") == ["message"], (metodlar(), _sw, len(_sir)))
d = js(CB.get("/api/settings/telegram-bot"))
check("E5 GET: ulangan=true, bot_username, webhook_url", d.get("ulangan") is True and d.get("bot_username") == "b_korxona_bot"
      and d.get("webhook_url") == "https://testserver/telegram/webhook/2", d)
_matnlar = [CB.get(y).text for y in ("/api/settings/telegram-bot", "/api/settings/company", "/sozlamalar", "/logs", "/users")]
_matnlar += [CP.get(y).text for y in ("/api/platform/companies", "/platforma", "/users", INFO)]
check("E6 SIR va B TOKENI hech bir javob / sahifada YO'Q (qiymat bo'yicha: sozlamalar, korxona, sahifalar, platforma)",
      _sir and not any(_sir in x for x in _matnlar) and not any(B_TOKEN in x for x in _matnlar),
      [i for i, x in enumerate(_matnlar) if _sir in x or B_TOKEN in x])
_s = SessionLocal()
_al = [(a.action, a.company_id, a.performed_by, a.new_value) for a in _s.query(ActivityLog).filter(
    ActivityLog.action == "telegram_bot_ulandi").all()]
_s.close()
check("E7 audit jurnali: «telegram_bot_ulandi» — korxona 2, kim tw_b_adm, bot va manzil",
      _al == [("telegram_bot_ulandi", 2, "tw_b_adm", "@b_korxona_bot → https://testserver/telegram/webhook/2")], _al)
chaq_tozala()
r = CC.post(ULASH)
check("E8 C da token yo'q → 400 «Avval bot tokenini», so'rov YO'Q", r.status_code == 400 and "Avval bot tokenini" in r.text
      and not CHAQ, (r.status_code, r.text[:160]))
for _tk, _k, _kut, _st in (("123 / deleteWebhook?x", "E9", "noto'g'ri ko'rinishda", 400),
                           (UMUMIY_TOKEN, "E10", "umumiy boti", 400),
                           (B_TOKEN, "E11", "boshqa korxonaning", 409)):
    CC.put("/api/settings/telegram-bot", data={"token": _tk})
    chaq_tozala()
    r = CC.post(ULASH)
    check(f"{_k} C tokeni: {_kut} → {_st}, Telegram'ga so'rov YO'Q, token javobda YO'Q",
          r.status_code == _st and _kut in r.text and not CHAQ and (_tk not in r.text or len(_tk) < 30),
          (r.status_code, r.text[:200], metodlar()))
CC.put("/api/settings/telegram-bot", data={"token": C_TOKEN})
JAVOB_T[(C_TOKEN, "getMe")] = http_xato(401, "Unauthorized")
chaq_tozala()
r = CC.post(ULASH)
check("E12 Telegram tokenni rad etsa (getMe 401) → 400 «Telegram rad etdi: Unauthorized», setWebhook YO'Q, ulanmadi",
      r.status_code == 400 and "Telegram rad etdi: Unauthorized" in r.text and metodlar() == ["getMe"]
      and not sozlama(3, SIR_K), (r.status_code, r.text[:200], metodlar()))
JAVOB_T[(C_TOKEN, "getMe")] = {"id": 333333333, "is_bot": True, "first_name": "C bot", "username": "c_korxona_bot"}
JAVOB_T[(C_TOKEN, "setWebhook")] = http_xato(400, "Bad Request: bad webhook: HTTPS url must be provided for webhook")
chaq_tozala()
r = CC.post(ULASH)
check("E13 setWebhook rad etilsa → 400 Telegram sababi bilan, bazaga sir YOZILMADI",
      r.status_code == 400 and "bad webhook" in r.text and not sozlama(3, SIR_K), (r.status_code, r.text[:200]))
JAVOB_T[(C_TOKEN, "setWebhook")] = urllib.error.URLError(f"tarmoq yo'q ({C_TOKEN})")
r = CC.post(ULASH)
check("E14 tarmoq xatosi → 502 «bog'lanishda xato», token javobda YO'Q", r.status_code == 502 and "bog'lanishda xato" in r.text
      and C_TOKEN not in r.text, (r.status_code, r.text[:200]))
JAVOB_T.pop((C_TOKEN, "setWebhook"), None)
r = CC.post(ULASH)
_csir = sozlama(3, SIR_K)
check("E15 C ham ulandi (o'z tokeni) — siri B nikidan boshqa", r.status_code == 200 and _csir and _csir != _sir,
      (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════
section("F. Korxona boti webhooki — POST /telegram/webhook/<id>")
# ══════════════════════════════════════════════════════════════
BW = "/telegram/webhook/2"
st, t = wh(BW, _sir, "902", "/start")
_m = " | ".join(x for _, x in t)
check("F1 B ustasi o'z korxonasi botida /start → B nomi, javob B TOKENI bilan",
      st == 200 and len(t) == 1 and "*BBB_KORXONA* bot ga xush kelibsiz!" in _m and t[0][0] == B_TOKEN, (st, t))
st, t = wh(BW, _sir, "902", "💰 Bonuslarim")
_m = " | ".join(x for _, x in t)
check("F2 «💰 Bonuslarim» → B ustasi (USTA_IKKI), B imzosi, B tokeni; platforma nomi YO'Q",
      st == 200 and "USTA_IKKI" in _m and "BBB_KORXONA" in _m and (not A_NOM or A_NOM not in _m)
      and all(tk == B_TOKEN for tk, _ in t), (st, t))
st, t = wh(BW, _sir, "902", "🎁 Sovg'alar")
_m = " | ".join(x for _, x in t)
check("F3 «🎁 Sovg'alar» → B davri (B_SOVGA_X), A davri YO'Q", st == 200 and "B_SOVGA_X" in _m and "A_SOVGA_X" not in _m, _m[:300])
st, t = wh(BW, _sir, "902", "🪪 Mening ID raqamim")
check("F4 «🪪 Mening ID raqamim» → chat ID, B tokeni", len(t) == 1 and "`902`" in t[0][1] and t[0][0] == B_TOKEN, t)
st, t = wh(BW, _sir, "901", "/bonus")
_m = " | ".join(x for _, x in t)
check("F5 platforma korxonasi ustasi B botida → «topilmadingiz», USTA_BIR YO'Q, imzo — B, token — B",
      "topilmadingiz" in _m and "USTA_BIR" not in _m and "BBB_KORXONA" in _m and all(tk == B_TOKEN for tk, _ in t), _m[:300])
st, t = wh(BW, _sir, "903", "/bonus")
_m = " | ".join(x for _, x in t)
check("F6 ikki korxonadagi usta B botida — B dagi yozuvi (USTA_UCH_B), «bir nechta» YO'Q",
      "USTA_UCH_B" in _m and "USTA_UCH_A" not in _m and "bir nechta" not in _m, _m[:300])
_rad = []
for _yol, _s_, _izoh in ((BW, "noto'g'ri", "noto'g'ri sir"), (BW, None, "sarlavhasiz"), (BW, _csir, "C ning siri B yo'lida"),
                         ("/telegram/webhook/3", _sir, "B siri C yo'lida"), (BW, UMUMIY_SIR, "umumiy bot siri B yo'lida"),
                         (GW, _sir, "B siri umumiy yo'lda"), ("/telegram/webhook/99", _sir, "yo'q korxona"),
                         ("/telegram/webhook/1", _sir, "ulanmagan korxona (1)"), (BW, _sir + "x", "sir + belgi")):
    st, t = wh(_yol, _s_, "902", "/bonus")
    if st != 403 or t:
        _rad.append((_izoh, st, t))
check("F7 9 xil begona / noto'g'ri so'rov → HAMMASI 403 va hech narsa yuborilmadi", not _rad, _rad)
st, t = wh(GW, UMUMIY_SIR, "901", "/bonus")
check("F8 B ulangandan keyin ham umumiy bot eskisidek (USTA_BIR, umumiy token)",
      st == 200 and t and "USTA_BIR" in t[0][1] and t[0][0] == UMUMIY_TOKEN, t)
st, t = wh("/telegram/webhook/3", _csir, "902", "/bonus")
check("F9 B ustasi C botida → «topilmadingiz» (C tokeni bilan), B ma'lumoti YO'Q",
      st == 200 and t and "topilmadingiz" in t[0][1] and "USTA_IKKI" not in t[0][1] and t[0][0] == C_TOKEN, t)
YUB.clear()
with contextlib.redirect_stdout(_quiet):
    _r1 = WH.post(BW, content=b"buzuq{", headers={"X-Telegram-Bot-Api-Secret-Token": _sir})
    _r2 = WH.post(BW, json=[1, 2], headers={"X-Telegram-Bot-Api-Secret-Token": _sir})
    _r3 = WH.post(BW, json={"message": {"chat": {"id": 902}, "text": 5}}, headers={"X-Telegram-Bot-Api-Secret-Token": _sir})
check("F10 buzuq tana / ro'yxat / matn emas → 200 ok, hech narsa yuborilmaydi, 500 YO'Q",
      (_r1.status_code, _r2.status_code, _r3.status_code) == (200, 200, 200) and not YUB,
      (_r1.status_code, _r2.status_code, _r3.status_code, YUB))

# ══════════════════════════════════════════════════════════════
section("G. Token almashsa / tozalansa — eski bot uziladi")
# ══════════════════════════════════════════════════════════════
r = CB.put("/api/settings/telegram-bot", data={"token": B_TOKEN, "chat_id": ""})
check("G0 o'sha tokenni qayta saqlash — bot UZILMAYDI", r.status_code == 200 and not js(r).get("bot_uzildi")
      and sozlama(2, SIR_K) == _sir, (r.status_code, js(r)))
r = CB.put("/api/settings/telegram-bot", data={"token": "", "chat_id": "-100600"})
check("G0b bo'sh token (o'zgartirmaslik) — bot UZILMAYDI", r.status_code == 200 and not js(r).get("bot_uzildi")
      and sozlama(2, SIR_K) == _sir, js(r))
muhit("production")
JAVOB_T[(B_TOKEN, "getWebhookInfo")] = {"url": "https://testserver/telegram/webhook/2", "pending_update_count": 0}
chaq_tozala()
r = CB.put("/api/settings/telegram-bot", data={"token": B_TOKEN2})
d = js(r)
_dw = [(tk, t) for tk, m, t, _ in CHAQ if m == "deleteWebhook"]
check("G1 token almashdi (production, bot shu manzilda) → bot_uzildi, xabar «eski bot uzildi … Botni ulash»",
      r.status_code == 200 and d.get("bot_uzildi") is True and "eski bot uzildi" in (d.get("message") or ""), d)
check("G2 Telegram: ESKI token bilan getWebhookInfo, keyin deleteWebhook (drop_pending_updates=false)",
      metodlar() == ["getWebhookInfo", "deleteWebhook"] and all(tk == B_TOKEN for tk, _, _, _ in CHAQ)
      and _dw and _dw[0][1].get("drop_pending_updates") is False, (metodlar(), _dw))
d = js(CB.get("/api/settings/telegram-bot"))
check("G3 GET: ulangan=false, bot nomi / manzil bo'sh; bazada sir / manzil / nom tozalangan",
      d.get("ulangan") is False and d.get("bot_username") == "" and not sozlama(2, SIR_K)
      and not sozlama(2, URL_K) and not sozlama(2, BOT_K), d)
st, t = wh(BW, _sir, "902", "/bonus")
check("G4 eski sir bilan kelgan xabar → 403 (hech narsa yuborilmadi)", st == 403 and not t, (st, t))
_s = SessionLocal()
_al = [(a.company_id, a.performed_by, a.old_value, a.new_value) for a in _s.query(ActivityLog).filter(
    ActivityLog.action == "telegram_bot_uzildi").all()]
_s.close()
check("G5 audit: «telegram_bot_uzildi» — korxona 2, eski bot va manzil, «bot tokeni almashtirildi»",
      _al == [(2, "tw_b_adm", "@b_korxona_bot → https://testserver/telegram/webhook/2", "bot tokeni almashtirildi")], _al)
JAVOB_T[(B_TOKEN2, "getMe")] = {"id": 222222223, "is_bot": True, "first_name": "B bot 2", "username": "b_yangi_bot"}
r = CB.post(ULASH)
_sir2 = sozlama(2, SIR_K)
check("G6 yangi bot ulandi — yangi sir, yangi token bilan javob", lambda: r.status_code == 200 and _sir2 and _sir2 != _sir
      and wh(BW, _sir2, "902", "/start")[1][0][0] == B_TOKEN2, (r.status_code, r.text[:200]))
JAVOB_T[(B_TOKEN2, "getWebhookInfo")] = {"url": "https://boshqa-xizmat.example/hook", "pending_update_count": 0}
chaq_tozala()
r = CB.put("/api/settings/telegram-bot", data={"token": "-", "chat_id": "-"})
d = js(r)
check("G7 tozalash, bot BOSHQA manzilga ko'chgan (mijoz boshqa joyda ishlatyapti) → deleteWebhook YUBORILMAYDI, xabar «tozalandi»",
      d.get("bot_uzildi") is True and "tozalandi" in (d.get("message") or "") and metodlar() == ["getWebhookInfo"]
      and not sozlama(2, SIR_K), (d, metodlar()))
# sinov saytiga ko'chirilgan baza (production nusxasi): ulanish belgilari bor — token almashsa Telegram'ga TEGILMAYDI
_s = SessionLocal()
for _k, _v in (("telegram_bot_token", B_TOKEN), (SIR_K, "NUSXA_SIR_" + "z" * 40),
               (URL_K, "https://web-production-a064.up.railway.app/telegram/webhook/2"),
               (BOT_K, "b_korxona_bot")):
    crud.set_setting(_s, _k, _v, company_id=2)
_s.close()
muhit("sinov")
chaq_tozala()
r = CB.put("/api/settings/telegram-bot", data={"token": B_TOKEN2})
check("G8 sinov saytida token almashdi → Telegram'ga so'rov YO'Q (production dagi botga tegilmaydi), belgilar tozalandi",
      js(r).get("bot_uzildi") is True and not CHAQ and not sozlama(2, SIR_K), (js(r), metodlar()))
muhit("production")

# ══════════════════════════════════════════════════════════════
section("H. Sahifalar va olib tashlangan marshrut")
# ══════════════════════════════════════════════════════════════
_uh = open(os.path.join(ROOT, "templates", "users.html"), encoding="utf-8").read()
_lh = open(os.path.join(ROOT, "templates", "logs.html"), encoding="utf-8").read()
check("H1 users.html: holat bloki (id=tg-holat) GET /api/system/telegram-webhook-info dan; ulashdan OLDIN tasdiq oynasi (sayt manzili)",
      lambda: 'id="tg-holat"' in _uh and "fetch('/api/system/telegram-webhook-info')" in _uh
      and _uh.index("customConfirm(\"Umumiy bot SHU saytga ulanadi") < _uh.index("fetch('/api/system/telegram-setup-webhook-security'"))
_hp, _ha = CP.get("/users").text, CA.get("/users").text
check("H2 holat bloki FAQAT platforma admini sahifasida", 'id="tg-holat"' in _hp and 'id="tg-holat"' not in _ha)
check("H3 logs.html: «🔗 Botni ulash» tugmasi → POST /api/settings/telegram-bot/ulash; qadamlar (@BotFather, /newbot, ID)",
      'id="tg-ulash-btn"' in _lh and "fetch('/api/settings/telegram-bot/ulash', { method: 'POST' })" in _lh
      and "@BotFather" in _lh and "/newbot" in _lh and "🪪 Mening ID raqamim" in _lh)
_sz = CB.get("/sozlamalar").text
check("H3b /sozlamalar (mijoz admini): ulash tugmasi va qadamlar sahifada", 'id="tg-ulash-btn"' in _sz and 'id="tg-qadamlar"' in _sz)
_yollar = {getattr(r_, "path", "") for r_ in main.app.routes}
r = C0.get("/api/cron/find-chat-id", params={"secret": "x"})
check("H4 GET /api/cron/find-chat-id OLIB TASHLANDI (marshrut yo'q → 404)",
      "/api/cron/find-chat-id" not in _yollar and r.status_code == 404, (r.status_code, r.text[:120]))
_mp = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("H5 main.py: korxona boti siri faqat Telegram'ga (setWebhook) va solishtirishga — hech bir `return {` da TG_KORXONA_SIR yo'q",
      all("TG_KORXONA_SIR" not in q for q in _mp.split("\n") if "return {" in q))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
