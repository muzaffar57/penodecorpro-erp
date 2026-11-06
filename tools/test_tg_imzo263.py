#!/usr/bin/env python3
"""
test_tg_imzo263.py — kech200 (zip 263, xavfsizlik REJA 21-band): «🔐 Telegram xavfsizligini yoqish» YANGI imzo YARATMAYDI —
umumiy botga (@Penoustabot) Railway dagi MAVJUD `TELEGRAM_WEBHOOK_SECRET` beriladi.

NIMA UCHUN KERAK (kech198 da O'LCHANGAN, 06.11 17:50)
---------------------------------------------------
  Egasi production'da tugmani bosdi — eski kod tasodifiy YANGI sirni Telegram'ga berdi va sahifada «Railway ga qo'shing» deb
  ko'rsatdi; server esa hali ESKI `TELEGRAM_WEBHOOK_SECRET` bilan tekshirardi → egasi Railway ni yangilaguncha @Penoustabot
  xabarlari 403 («Wrong response from the webhook: 403 Forbidden»), ustalar javob olmadi. Endi tartib teskari: AVVAL Railway da
  imzo, keyin tugma o'sha imzoni botga beradi — server va Telegram doim bir xil imzoda, oraliq uzilish yo'q.

BO'LIMLAR
  A — `main._tg_umumiy_sir_xatosi`: bo'sh / ruxsatsiz belgi (bo'shliq, «+», «/», 257 belgi) / qisqa (< 20) → sabab; yaroqli → «»;
      sirning o'zi sabab matniga KIRMAYDI;
  B — marshrut: imzo yo'q / yaroqsiz → 409 + sabab + tasodifiy `taklif` (yaroqli, har safar boshqa), Telegram'ga so'rov YO'Q;
      yaroqli → 200, setWebhook `secret_token` = Railway imzosi, javobda sir / `new_secret` YO'Q; ikkinchi bosish — o'sha imzo;
      shundan keyin webhook o'sha imzoni qabul qiladi, boshqasini 403; tartib: muhit (409) → token (400) → imzo (409); ruxsat;
  C — sahifa (Chromium, Playwright): 409 — sariq blok, sabab, taklif (`#tg-sir-taklif`, nusxalanadi), 3 qadam, «Muvaffaqiyatli» /
      eski «Endi … nusxalab» YO'Q; 200 — «✅ Bot shu saytga xavfsiz imzo bilan ulandi», sir sahifada YO'Q; «Bot hozir qayerga
      ulangan» da 403 maslahati (faqat asosiy sayt, mos, kutayotgan xabar > 0, oxirgi xato 403); telefon 390 px — gorizontal
      aylantirish yo'q; JS xatosi yo'q.
Telegram'ga HECH NARSA chiqmaydi (`urllib.request.urlopen` soxtasi).
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (894aa9b — zip 263 1-qism) qarshi YIQILADI, QULAMAYDI.
ISHLATISH: python3 tools/test_tg_imzo263.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tg_imzo263_test"
_T = tempfile.mkdtemp(prefix="tg_imzo263_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tg_imzo263_test.db')}"

UMUMIY_TOKEN = "111111111:UMUMIYbotTOKENi_imzo263_aaaaaaaaaaaaaa"
RAILWAY_SIR = "Railway_Imzo-263_abcdefghijklmnopqrstuvwxyz0123456789"     # 53 belgi, Telegram qoidasiga mos
os.environ["TELEGRAM_BOT_TOKEN"] = UMUMIY_TOKEN
os.environ["TELEGRAM_WEBHOOK_SECRET"] = RAILWAY_SIR
os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)          # 2FA (platforma egasi kodi) bu sinovga tegmasin

import urllib.request                              # noqa: E402
import urllib.error                                # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
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
        print(f"  ✗ {REJIM}{label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ══════════════════════════════════════════════════════════════
# Soxta Telegram — hamma so'rov yoziladi
# ══════════════════════════════════════════════════════════════
CHAQ = []          # (token, metod, tana)
JAVOB = {}         # metod → natija
_qulf = threading.Lock()


class _Javob:
    def __init__(self, tana):
        self._t = json.dumps(tana).encode()

    def read(self):
        return self._t

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


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
    with _qulf:
        CHAQ.append((token, metod, tana))
        v = JAVOB.get(metod, True)
    return _Javob({"ok": True, "result": v})


urllib.request.urlopen = _soxta_urlopen


def chaq_tozala():
    with _qulf:
        CHAQ.clear()


def metodlar():
    with _qulf:
        return [m for _, m, _ in CHAQ if m != "sendMessage"]


def setwebhooklar():
    with _qulf:
        return [t for _, m, t in CHAQ if m == "setWebhook"]


def railway_sir(qiymat):
    """Railway dagi TELEGRAM_WEBHOOK_SECRET (server o'zgaruvchisi ishga tushganda o'qiladi — sinovda modul qiymati)."""
    main.TELEGRAM_WEBHOOK_SECRET = qiymat


def muhit(nom):
    if nom is None:
        os.environ.pop("RAILWAY_ENVIRONMENT_NAME", None)
    else:
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = nom


# ══════════════════════════════════════════════════════════════
# Fikstura: 1 — platforma egasi, 2 — mijoz korxona
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="IMZO263 Mijoz"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "ti_plat", "Parol123!", UserRole.ADMIN, "Platforma Egasi", company_id=1)
    auth.create_user(_db, "ti_a_adm", "Parol123!", UserRole.ADMIN, "A admin", company_id=1)
    auth.create_user(_db, "ti_b_adm", "Parol123!", UserRole.ADMIN, "B admin", company_id=2)
_db.query(User).filter(User.username == "ti_plat").update({"is_platform_admin": True})
_db.query(User).filter(User.username.in_(["ti_a_adm", "ti_b_adm"])).update({"is_platform_admin": False}, synchronize_session=False)
_db.commit()
_db.close()


def kirgan(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    assert r.status_code == 302, f"{login} kirmadi: {r.status_code}"
    return c


CP, CA, CB = (kirgan(u) for u in ("ti_plat", "ti_a_adm", "ti_b_adm"))
C0 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
WH = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
SETUP = "/api/system/telegram-setup-webhook-security"
BU_URL = "https://testserver/telegram/webhook"
TG_NAQSH = re.compile(r"^[A-Za-z0-9_-]{20,256}$")

# ══════════════════════════════════════════════════════════════
section("A. _tg_umumiy_sir_xatosi — Railway imzosi Telegram'ga yaroqlimi")
# ══════════════════════════════════════════════════════════════
fn = getattr(main, "_tg_umumiy_sir_xatosi", None)
check("A0 `main._tg_umumiy_sir_xatosi` bor, TG_UMUMIY_SIR_MIN = 20", callable(fn) and getattr(main, "TG_UMUMIY_SIR_MIN", None) == 20,
      (fn, getattr(main, "TG_UMUMIY_SIR_MIN", None)))
if callable(fn):
    check("A1 bo'sh / None → «Railway da TELEGRAM_WEBHOOK_SECRET sozlanmagan»",
          fn("") == "Railway da TELEGRAM_WEBHOOK_SECRET sozlanmagan" and fn(None) == fn(""), (fn(""), fn(None)))
    _yomon = {"bo'shliq": "Imzo bor lekin ichida bo'shliq_12345", "oxirida bo'shliq": RAILWAY_SIR + " ",
              "yangi qator": RAILWAY_SIR + "\n", "«+» va «/»": "abcdefghij+klmnopqrst/uvwxyz",
              "«=»": "abcdefghijklmnopqrstuvwx==", "kirill": "ИмзоИмзоИмзоИмзоИмзоИмзо", "257 belgi": "a" * 257}
    _n = {k: fn(v) for k, v in _yomon.items()}
    check("A2 ruxsatsiz belgi (bo'shliq, yangi qator, «+», «/», «=», kirill) yoki 257 belgi → «Telegram qabul qilmaydigan belgi bor … "
          "ko'pi bilan 256 belgi»",
          all("Telegram qabul qilmaydigan belgi bor" in v and "256 belgi" in v for v in _n.values()), _n)
    _q = [fn("a" * n) for n in (1, 19)] + [fn("Ab_-" * 4 + "xyz")]
    check("A3 qisqa (1, 19, 19 belgi) → «juda qisqa (N belgi) — kamida 20 belgi»",
          "juda qisqa (1 belgi)" in _q[0] and "juda qisqa (19 belgi)" in _q[1] and "juda qisqa (19 belgi)" in _q[2]
          and all("kamida 20 belgi" in v for v in _q), _q)
    check("A4 yaroqli: 20 belgi, 256 belgi, token_urlsafe(32), RAILWAY_SIR, «_» va «-» bilan → «»",
          fn("a" * 20) == "" and fn("Z9_-" * 64) == "" and fn(RAILWAY_SIR) == "" and fn("-_" * 10) == ""
          and fn(__import__("secrets").token_urlsafe(32)) == "", [fn("a" * 20), fn("Z9_-" * 64)])
    _sirli = ["MAXFIY_SIR_BOSHIBUZUQ +", "MAXFIYqisqa"]
    check("A5 sirning o'zi sabab matniga KIRMAYDI", all(s.strip() not in fn(s) for s in _sirli), [fn(s) for s in _sirli])

# ══════════════════════════════════════════════════════════════
section("B. Marshrut — imzo Railway dan, yangi sir YO'Q")
# ══════════════════════════════════════════════════════════════
muhit("production")
JAVOB["getWebhookInfo"] = {"url": "https://web-production-a064.up.railway.app/telegram/webhook", "pending_update_count": 5}
railway_sir("")
chaq_tozala()
r = CP.post(SETUP)
d = js(r)
check("B1 Railway da imzo YO'Q → 409, imzo «yoq», sabab «sozlanmagan», Telegram'ga so'rov YO'Q (bot hozirgi ulanishida)",
      r.status_code == 409 and d.get("imzo") == "yoq" and d.get("sabab") == "Railway da TELEGRAM_WEBHOOK_SECRET sozlanmagan"
      and metodlar() == [], (r.status_code, r.text[:400], metodlar()))
_t1 = d.get("taklif") or ""
check("B2 taklif — Telegram qoidasiga mos (A–Z a–z 0–9 _ -), ≥ 40 belgi va `_tg_umumiy_sir_xatosi` dan o'tadi",
      bool(TG_NAQSH.match(_t1)) and len(_t1) >= 40 and callable(fn) and fn(_t1) == "", _t1)
check("B3 detail: «Bot ulanmadi — Telegram'da hech narsa o'zgarmadi … Railway → Variables → TELEGRAM_WEBHOOK_SECRET … Deploy "
      "tugagach «🔐 Telegram xavfsizligini yoqish» ni qayta bosing»",
      d.get("detail", "").startswith("Railway da TELEGRAM_WEBHOOK_SECRET sozlanmagan. Bot ulanmadi — Telegram'da hech narsa o'zgarmadi")
      and "Railway → Variables → TELEGRAM_WEBHOOK_SECRET" in d.get("detail", "")
      and "Deploy tugagach «🔐 Telegram xavfsizligini yoqish» ni qayta bosing" in d.get("detail", "")
      and "new_secret" not in d and UMUMIY_TOKEN not in r.text, d)
r2 = CP.post(SETUP)
check("B4 qayta bosish — yana 409, taklif HAR SAFAR boshqa (saqlanmaydi), Telegram'ga so'rov YO'Q",
      r2.status_code == 409 and (js(r2).get("taklif") or "") not in ("", _t1) and metodlar() == [],
      (r2.status_code, js(r2).get("taklif"), _t1, metodlar()))
for _k, _qiy, _imzo, _bolak in (("B5", "Imzo bor lekin bo'shliq bilan_123", "yaroqsiz", "Telegram qabul qilmaydigan belgi bor"),
                                ("B6", RAILWAY_SIR + "\n", "yaroqsiz", "Telegram qabul qilmaydigan belgi bor"),
                                ("B7", "qisqa_imzo_123", "yaroqsiz", "juda qisqa (14 belgi)")):
    railway_sir(_qiy)
    chaq_tozala()
    r = CP.post(SETUP)
    d = js(r)
    check(f"{_k} Railway imzosi yaroqsiz ({_bolak}) → 409, imzo «{_imzo}», taklif bor, sir javobda YO'Q, Telegram'ga so'rov YO'Q",
          r.status_code == 409 and d.get("imzo") == _imzo and _bolak in d.get("sabab", "") and TG_NAQSH.match(d.get("taklif") or "")
          and _qiy.strip() not in r.text and metodlar() == [], (r.status_code, r.text[:400], metodlar()))
railway_sir(RAILWAY_SIR)
chaq_tozala()
r = CP.post(SETUP)
d = js(r)
_sw = setwebhooklar()
check("B8 Railway imzosi yaroqli → 200; Telegram: getWebhookInfo, setWebhook (shu sayt manzili, secret_token = RAILWAY imzosi)",
      r.status_code == 200 and metodlar() == ["getWebhookInfo", "setWebhook"] and len(_sw) == 1
      and _sw[0].get("url") == BU_URL and _sw[0].get("secret_token") == RAILWAY_SIR, (r.status_code, r.text[:300], metodlar(), _sw))
check("B9 javobda sir YO'Q (`new_secret` kaliti yo'q, qiymat matnda yo'q), imzo «railway», oldingi_url, «hech narsa o'zgartirish "
      "shart emas»",
      "new_secret" not in d and RAILWAY_SIR not in r.text and UMUMIY_TOKEN not in r.text and d.get("imzo") == "railway"
      and d.get("oldingi_url") == "https://web-production-a064.up.railway.app/telegram/webhook" and d.get("webhook_url") == BU_URL
      and "Railway da hech narsa o'zgartirish shart emas" in d.get("message", "") and "nusxalab" not in d.get("message", ""), d)
chaq_tozala()
r = CP.post(SETUP)
_sw2 = setwebhooklar()
check("B10 ikkinchi bosish — o'sha Railway imzosi (yangi sir yaratilmadi)",
      r.status_code == 200 and len(_sw2) == 1 and _sw2[0].get("secret_token") == RAILWAY_SIR, (r.status_code, _sw2))
with contextlib.redirect_stdout(_quiet):
    _w_ok = WH.post("/telegram/webhook", json={"update_id": 1}, headers={"X-Telegram-Bot-Api-Secret-Token": _sw2[0]["secret_token"]
                                                                         if _sw2 else "yoq"})
    _w_yomon = WH.post("/telegram/webhook", json={"update_id": 2}, headers={"X-Telegram-Bot-Api-Secret-Token": _t1 or "boshqa"})
check("B11 server Telegram'ga berilgan imzoni QABUL qiladi (403 emas); boshqa imzo (taklif) — 403",
      _w_ok.status_code != 403 and _w_ok.status_code < 500 and _w_yomon.status_code == 403,
      (_w_ok.status_code, _w_ok.text[:200], _w_yomon.status_code))
railway_sir("")
for _mn in ("sinov", None):
    muhit(_mn)
    chaq_tozala()
    r = CP.post(SETUP)
    check(f"B12 muhit {_mn!r} + imzo yo'q → 409 «asosiy sayt emas» (muhit birinchi), taklif YO'Q, Telegram'ga so'rov YO'Q",
          r.status_code == 409 and "asosiy sayt emas" in r.text and "taklif" not in js(r) and metodlar() == [],
          (r.status_code, r.text[:300], metodlar()))
muhit("production")
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
chaq_tozala()
r = CP.post(SETUP)
check("B13 production, token yo'q, imzo yo'q → 400 «TELEGRAM_BOT_TOKEN sozlanmagan» (token imzodan oldin), so'rov YO'Q",
      r.status_code == 400 and js(r).get("detail") == "TELEGRAM_BOT_TOKEN sozlanmagan" and metodlar() == [], (r.status_code, r.text[:300]))
os.environ["TELEGRAM_BOT_TOKEN"] = UMUMIY_TOKEN
railway_sir(RAILWAY_SIR)
chaq_tozala()
_r0, _ra, _rb = C0.post(SETUP), CA.post(SETUP), CB.post(SETUP)
check("B14 kirmagan → 401; platforma korxonasi admini (egasi emas) → 403; mijoz admini → 403; Telegram'ga so'rov YO'Q",
      _r0.status_code == 401 and _ra.status_code == 403 and _rb.status_code == 403 and metodlar() == [],
      (_r0.status_code, _ra.status_code, _rb.status_code, metodlar()))
railway_sir("")
chaq_tozala()
_ra, _rb = CA.post(SETUP), CB.post(SETUP)
check("B15 imzo yo'q paytida ham korxona adminlariga 403 — taklif / sabab ularga CHIQMAYDI",
      _ra.status_code == 403 and _rb.status_code == 403 and "taklif" not in _ra.text + _rb.text and metodlar() == [],
      (_ra.text[:200], _rb.text[:200]))
railway_sir(RAILWAY_SIR)

# ══════════════════════════════════════════════════════════════
section("C. Sahifa (Chromium) — «Foydalanuvchilar» → Telegram xavfsizligi")
# ══════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"
check("C0 Python `playwright` bor", PW_BOR, _pw_xato)

if PW_BOR:
    import uvicorn                                 # noqa: E402
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    port = so.getsockname()[1]
    so.close()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    check("C0b lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"
    UI_URL = f"https://127.0.0.1:{port}/telegram/webhook"
    JAVOB["getMe"] = {"id": 8606089235, "is_bot": True, "first_name": "Usta kabinet", "username": "Penoustabot"}
    JAVOB["getWebhookInfo"] = {"url": UI_URL, "pending_update_count": 0}
    JS_XATO = []

    def yonalish(route):
        u = route.request.url
        if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
            return route.fulfill(status=200, content_type="application/javascript",
                                 body="window.Chart = function () { return {destroy() {}, update() {}}; };")
        if u.startswith("https://fonts.googleapis.com/"):
            return route.fulfill(status=200, content_type="text/css", body="")
        return route.fulfill(status=204, body="")

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def kontekst(login, w=1440, h=900):
            tel = w < 700
            ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ", screen={"width": w, "height": h})
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                                 r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATO.append((login, str(e)[:300])))
            pg.goto(BU + "/login")
            pg.fill("input[name=username]", login)
            pg.fill("input[name=password]", "Parol123!")
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            return ctx, pg

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def kut(pg, kod, ms=15000):
            try:
                pg.wait_for_function(kod, timeout=ms)
                return True
            except Exception:              # noqa: BLE001
                return False

        def xav(f, *a, **k):
            try:
                return f(*a, **k)
            except Exception as ex:        # noqa: BLE001
                print(f"    (amal bajarilmadi: {getattr(f, '__name__', f)} {a[:1]} — {type(ex).__name__})")
                return None

        def matn(pg, sel):
            return ev(pg, "(s) => { const e = document.querySelector(s); return e ? e.textContent : null; }", sel)

        def holat_kut(pg):
            return kut(pg, "(() => { const e = document.getElementById('tg-holat-matn'); "
                           "return e && e.textContent && !e.textContent.includes('Tekshirilmoqda'); })()")

        def yangila(pg):
            xav(pg.reload)
            xav(pg.wait_for_load_state, "networkidle")
            holat_kut(pg)
            return matn(pg, "#tg-holat-matn") or ""

        def tugma_bos(pg):
            """«🔐 Telegram xavfsizligini yoqish» → tasdiq oynasi «Ulash» → natija bloki ko'ringuncha."""
            ev(pg, "() => { const b = document.getElementById('tg-security-result'); if (b) { b.style.display = 'none'; b.innerHTML = ''; } }")
            xav(pg.click, "#tg-security-btn")
            kut(pg, "(() => { const m = document.getElementById('ccModal'); return m && getComputedStyle(m).display !== 'none'; })()", 5000)
            xav(pg.click, "#ccModalOk")
            kut(pg, "(() => { const b = document.getElementById('tg-security-result'); return b && b.style.display === 'block' && "
                    "b.textContent.trim().length > 0; })()")
            kut(pg, "(() => { const b = document.getElementById('tg-security-btn'); return b && !b.disabled; })()", 5000)
            return matn(pg, "#tg-security-result") or ""

        SARIQ = None
        cp, pp = kontekst("ti_plat")
        xav(pp.goto, BU + "/users")
        xav(pp.wait_for_load_state, "networkidle")
        holat_kut(pp)
        SARIQ = ev(pp, "(() => { const d = document.createElement('div'); d.style.background = 'var(--f-fef3c7)'; document.body.appendChild(d);"
                       " const c = getComputedStyle(d).backgroundColor; d.remove(); return c; })()")
        railway_sir("")
        chaq_tozala()
        _m = tugma_bos(pp)
        _tk = matn(pp, "#tg-sir-taklif") or ""
        _fon = ev(pp, "getComputedStyle(document.getElementById('tg-security-result')).backgroundColor")
        _tanlash = ev(pp, "(() => { const e = document.getElementById('tg-sir-taklif'); return e ? getComputedStyle(e).userSelect : null; })()")
        check("C1 imzo yo'q: sariq blok «⚠️ Bot ulanmadi: Railway da TELEGRAM_WEBHOOK_SECRET sozlanmagan», «hech narsa o'zgarmadi», "
              "Telegram'ga so'rov (setWebhook) YO'Q",
              "⚠️ Bot ulanmadi: Railway da TELEGRAM_WEBHOOK_SECRET sozlanmagan" in _m and "Telegram'da hech narsa o'zgarmadi" in _m
              and _fon == SARIQ and "setWebhook" not in metodlar(), (_m[:400], _fon, SARIQ, metodlar()))
        check("C2 taklif — alohida maydonda (#tg-sir-taklif), Telegram qoidasiga mos, butunligicha tanlanadi (user-select: all)",
              bool(TG_NAQSH.match(_tk.strip())) and len(_tk.strip()) >= 40 and _tanlash == "all", (_tk, _tanlash))
        check("C3 3 qadam: «1) Railway → Variables → TELEGRAM_WEBHOOK_SECRET … shu taklifni qo'ying», «2) Deploy tugashini kuting», "
              "«3) … «🔐 Telegram xavfsizligini yoqish» ni qayta bosing»; «Muvaffaqiyatli» / «Endi … nusxalab» YO'Q",
              "1) Railway → Variables → TELEGRAM_WEBHOOK_SECRET" in _m and "shu taklifni qo'ying" in _m
              and "2) Deploy tugashini kuting" in _m and "3) Shu sahifani yangilab, «🔐 Telegram xavfsizligini yoqish» ni qayta bosing" in _m
              and "Muvaffaqiyatli" not in _m and "nusxalab" not in _m and "❌" not in _m, _m[:600])
        _btn = ev(pp, "(() => { const b = document.getElementById('tg-security-btn'); return [b.disabled, b.textContent.trim()]; })()")
        check("C4 tugma qayta yoqiq, yozuvi asl holida", _btn == [False, "🔐 Telegram xavfsizligini yoqish"], _btn)
        railway_sir("bo'shliqli imzo bor_123456789")
        chaq_tozala()
        _m = tugma_bos(pp)
        check("C5 imzo yaroqsiz (bo'shliq): «⚠️ Bot ulanmadi: Railway dagi TELEGRAM_WEBHOOK_SECRET da Telegram qabul qilmaydigan belgi "
              "bor …», sir sahifada YO'Q, setWebhook YO'Q",
              "⚠️ Bot ulanmadi: Railway dagi TELEGRAM_WEBHOOK_SECRET da Telegram qabul qilmaydigan belgi bor" in _m
              and "bo'shliqli imzo bor_123456789" not in str(ev(pp, "document.documentElement.outerHTML"))
              and "setWebhook" not in metodlar(), (_m[:400], metodlar()))
        railway_sir(RAILWAY_SIR)
        chaq_tozala()
        _m = tugma_bos(pp)
        _sw = setwebhooklar()
        _html = str(ev(pp, "document.documentElement.outerHTML"))
        check("C6 imzo yaroqli: «✅ Bot shu saytga xavfsiz imzo bilan ulandi!», «Railway da hech narsa o'zgartirish shart emas»; "
              "setWebhook — Railway imzosi bilan; sir sahifada YO'Q; taklif maydoni YO'Q",
              "✅ Bot shu saytga xavfsiz imzo bilan ulandi!" in _m and "Railway da hech narsa o'zgartirish shart emas" in _m
              and len(_sw) == 1 and _sw[0].get("secret_token") == RAILWAY_SIR and RAILWAY_SIR not in _html
              and ev(pp, "!!document.getElementById('tg-sir-taklif')") is False and "nusxalab" not in _m,
              (_m[:400], _sw))
        MASLAHAT = "💡 Bot xabarlari sayt imzosiga mos kelmayapti (403)"
        JAVOB["getWebhookInfo"] = {"url": UI_URL, "pending_update_count": 3, "last_error_date": 1791457200,
                                   "last_error_message": "Wrong response from the webhook: 403 Forbidden"}
        _h = yangila(pp)
        check("C7 «Bot hozir qayerga ulangan»: mos + kutayotgan 3 + oxirgi xato 403 → maslahat «💡 … (403). «🔐 Telegram "
              "xavfsizligini yoqish» ni bossangiz, Railway dagi TELEGRAM_WEBHOOK_SECRET botga qayta beriladi …»",
              MASLAHAT in _h and "«🔐 Telegram xavfsizligini yoqish» ni bossangiz, Railway dagi TELEGRAM_WEBHOOK_SECRET botga qayta beriladi"
              in _h and "✅ @Penoustabot shu saytga ulangan" in _h, _h)
        _yoq = {}
        JAVOB["getWebhookInfo"] = {"url": UI_URL, "pending_update_count": 0, "last_error_date": 1791457200,
                                   "last_error_message": "Wrong response from the webhook: 403 Forbidden"}
        _yoq["kutayotgan 0"] = MASLAHAT in yangila(pp)
        JAVOB["getWebhookInfo"] = {"url": UI_URL, "pending_update_count": 3, "last_error_date": 1791457200,
                                   "last_error_message": "Wrong response from the webhook: 502 Bad Gateway"}
        _yoq["oxirgi xato 502"] = MASLAHAT in yangila(pp)
        JAVOB["getWebhookInfo"] = {"url": "https://boshqa.example/telegram/webhook", "pending_update_count": 3,
                                   "last_error_date": 1791457200, "last_error_message": "Wrong response from the webhook: 403 Forbidden"}
        _yoq["boshqa sayt"] = MASLAHAT in yangila(pp)
        JAVOB["getWebhookInfo"] = {"url": UI_URL, "pending_update_count": 3, "last_error_date": 1791457200,
                                   "last_error_message": "Wrong response from the webhook: 403 Forbidden"}
        muhit("sinov")
        _yoq["sinov sayti"] = MASLAHAT in yangila(pp)
        muhit("production")
        railway_sir("")
        _yoq["imzo sozlanmagan"] = MASLAHAT in yangila(pp)
        railway_sir(RAILWAY_SIR)
        check("C8 maslahat FAQAT shu holatda: kutayotgan 0 / oxirgi xato 502 / boshqa saytga ulangan / sinov sayti / imzo "
              "sozlanmagan — YO'Q", not any(_yoq.values()), _yoq)
        cp.close()

        JAVOB["getWebhookInfo"] = {"url": UI_URL, "pending_update_count": 3, "last_error_date": 1791457200,
                                   "last_error_message": "Wrong response from the webhook: 403 Forbidden"}
        cx, px = kontekst("ti_plat", 390, 844)
        xav(px.goto, BU + "/users")
        xav(px.wait_for_load_state, "networkidle")
        holat_kut(px)
        railway_sir("")
        tugma_bos(px)
        _o = ev(px, """() => { const e = document.getElementById('tg-security-result'), t = document.getElementById('tg-sir-taklif'),
                               h = document.getElementById('tg-holat-matn');
                               if (!e || !t || !h) return null;
                               const r = e.getBoundingClientRect(), q = t.getBoundingClientRect(), s = h.getBoundingClientRect();
                               return {sc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                                       l: Math.round(r.left), r: Math.round(r.right), tl: Math.round(q.left), tr: Math.round(q.right),
                                       hr: Math.round(s.right), tsc: t.scrollWidth - t.clientWidth}; }""")
        check("C9 telefon 390 px: natija bloki, taklif maydoni va 403 maslahati ekranga sig'adi, gorizontal aylantirish yo'q",
              isinstance(_o, dict) and _o.get("sc") == 0 and _o.get("l", -1) >= 0 and _o.get("r", 999) <= 390
              and _o.get("tl", -1) >= 0 and _o.get("tr", 999) <= 390 and _o.get("hr", 999) <= 390 and _o.get("tsc", 9) <= 0, _o)
        railway_sir(RAILWAY_SIR)
        cx.close()
        br.close()
    check("C10 JS xatosi yo'q", not JS_XATO, JS_XATO)
    server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
