#!/usr/bin/env python3
"""
test_telegram_webhook_ui.py — kech130 (zip 154): «🔒 Telegram xavfsizligi» (Foydalanuvchilar, platforma admini) va
«📱 Telegram bot» (Sozlamalar, korxona admini) — HAQIQIY brauzerda (Chromium, Playwright) O'LCHANADI.

BO'LIMLAR
  U1 platforma admini, asosiy sayt: «Bot hozir qayerga ulangan» — «✅ @Penoustabot shu saytga ulangan: <manzil>»;
  U2 bot boshqa saytda — qizil «BOSHQA manzilga ulangan» + shu sayt manzili; «↻ Tekshirish» qayta o'qiydi;
  U3 sinov sayti: ogohlantirish, ikkala tugma O'CHIQ — bosilsa ham Telegram'ga so'rov YO'Q;
  U4 «🔐 Telegram xavfsizligini yoqish» — avval TASDIQ oynasi (shu sayt manzili); «Bekor» — so'rov yo'q; «Ulash» — setWebhook shu
     saytga, oynada yangi sir (Telegram'ga ketgani bilan AYNAN), holat qayta o'qildi;
  U5 korxona admini: token saqlangach «🔗 Botni ulash» ko'rinadi, «Bot hali ulanmagan»; qadamlar matni bor;
  U6 «🔗 Botni ulash» → tasdiq → setWebhook B tokeni bilan …/telegram/webhook/2 → «✅ Bot ulandi: @… → …», qayta ochganda
     «✅ Ustalar boti ulangan», tugma «🔗 Qayta ulash»;
  U7 sinov saytida korxona admini: tugma O'CHIQ, izoh;
  U8 token almashtirildi → «eski bot uzildi» xabari, deleteWebhook ESKI token bilan;
  U9 telefon (390 px): /users va /sozlamalar — gorizontal aylantirish yo'q, holat bloki va tugmalar ekranga sig'adi;
  U10 korxona admini /users — holat so'rovi YUBORILMAYDI; sahifalarda token / sir yo'q; JS xatosi yo'q.
Telegram'ga HECH NARSA chiqmaydi (`urllib.request.urlopen` soxtasi; server shu jarayonda — ip oqimida).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 153) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_telegram_webhook_ui.py
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

OK = FAIL = 0
FAILED = []
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
YORLIQ = "[PG] " if PG_URL else ""


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


try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"

PG_BAZA = "telegram_webhook_ui154_test"
_T = tempfile.mkdtemp(prefix="tg_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tg_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)
UMUMIY_TOKEN = "111111111:UMUMIYbotTOKENi_aaaaaaaaaaaaaaaaaaaaaa"
UMUMIY_SIR = "UMUMIY_WEBHOOK_SIRI_UI"
B_TOKEN = "222222222:BkorxonaTOKENi_bbbbbbbbbbbbbbbbbbbbbbb"
B_TOKEN2 = "222222223:BkorxonaYANGItoken_cccccccccccccccccccc"
os.environ["TELEGRAM_BOT_TOKEN"] = UMUMIY_TOKEN
os.environ["TELEGRAM_WEBHOOK_SECRET"] = UMUMIY_SIR
os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"

import urllib.request                              # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User                  # noqa: E402

CHAQ = []          # (token, metod, tana)
JAVOB = {}         # metod → natija
JAVOB_T = {}       # (token, metod) → natija
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
            tana = {}
    with _qulf:
        CHAQ.append((token, metod, tana))
    v = JAVOB_T.get((token, metod), JAVOB.get(metod, True))
    return _Javob({"ok": True, "result": v})


urllib.request.urlopen = _soxta_urlopen


def metodlar():
    with _qulf:
        return [m for _, m, _ in CHAQ]


def sozlama(cid, kalit):
    s = SessionLocal()
    try:
        return crud.get_setting(s, kalit, "", company_id=cid) or ""
    finally:
        s.close()


_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="UI BBB Dekor"))
    _db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "ui_tg_plat", "Parol123!", UserRole.ADMIN, "Platforma Egasi", company_id=1)
    auth.create_user(_db, "ui_tg_b", "Parol123!", UserRole.ADMIN, "B Admin", company_id=2)
_db.query(User).filter(User.username == "ui_tg_plat").update({"is_platform_admin": True})
_db.query(User).filter(User.username == "ui_tg_b").update({"is_platform_admin": False})
_db.commit()
_db.close()

section("U0. Tayyorgarlik")
check("U0 Python `playwright` bor", PW_BOR, _pw_xato)

import uvicorn                                     # noqa: E402

if PW_BOR:
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
    check("U0b lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"
    HOST = f"127.0.0.1:{port}"
    BU_URL = f"https://127.0.0.1:{port}/telegram/webhook"          # server http → https (Railway proksisi kabi)
    JAVOB["getMe"] = {"id": 8606089235, "is_bot": True, "first_name": "Usta kabinet", "username": "Penoustabot"}
    JAVOB["getWebhookInfo"] = {"url": BU_URL, "pending_update_count": 0}

    def yonalish(route):
        u = route.request.url
        if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
            return route.fulfill(status=200, content_type="application/javascript",
                                 body="window.Chart = function () { return {destroy() {}, update() {}}; };")
        if u.startswith("https://fonts.googleapis.com/"):
            return route.fulfill(status=200, content_type="text/css", body="")
        return route.fulfill(status=204, body="")

    JS_XATO = []
    SOROV = []

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
            pg.on("request", lambda rq: SOROV.append((login, rq.method, rq.url)) if "/api/" in rq.url else None)
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
            """Brauzer amali — element topilmasa (asl kodda / mutatsiyada) sinov QULAMAYDI, tekshiruv yiqiladi."""
            try:
                return f(*a, **k)
            except Exception as ex:        # noqa: BLE001
                print(f"    (amal bajarilmadi: {getattr(f, '__name__', f)} {a[:1]} — {type(ex).__name__})")
                return None

        def matn(pg, sel):
            return ev(pg, "(s) => { const e = document.querySelector(s); return e ? e.textContent : null; }", sel)

        def ochiq(pg, sel):
            return ev(pg, "(s) => { const e = document.querySelector(s); return e ? !e.disabled : null; }", sel)

        def modal_matn(pg):
            return ev(pg, """() => { const m = document.getElementById('ccModal');
                                    if (!m || getComputedStyle(m).display === 'none') return null;
                                    return (document.getElementById('ccModalMessage') || {}).textContent || ''; }""")

        def holat_kut(pg):
            return kut(pg, "(() => { const e = document.getElementById('tg-holat-matn'); "
                           "return e && e.textContent && !e.textContent.includes('Tekshirilmoqda'); })()")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U1–U4. Platforma admini — «🔒 Telegram xavfsizligi»")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        cp, pp = kontekst("ui_tg_plat")
        xav(pp.goto, BU + "/users")
        pp.wait_for_load_state("networkidle")
        holat_kut(pp)
        _h = matn(pp, "#tg-holat-matn") or ""
        check("U1 «✅ @Penoustabot shu saytga ulangan: <shu sayt manzili>»; tugmalar YOQIQ",
              "✅ @Penoustabot shu saytga ulangan" in _h and BU_URL in _h and ochiq(pp, "#tg-security-btn") is True
              and ochiq(pp, "#tg-delete-webhook-btn") is True, _h)
        JAVOB["getWebhookInfo"] = {"url": "https://web-sinov.up.railway.app/telegram/webhook", "pending_update_count": 4,
                                   "last_error_date": 1791457200, "last_error_message": "Connection timed out"}
        xav(pp.click, "#tg-holat-btn")
        kut(pp, "((document.getElementById('tg-holat-matn') || {}).textContent || '').includes('BOSHQA')")
        _h = matn(pp, "#tg-holat-matn") or ""
        _rang = ev(pp, "getComputedStyle(document.querySelector('#tg-holat-matn div')).color")
        check("U2 «↻ Tekshirish» — «⚠️ @Penoustabot BOSHQA manzilga ulangan: web-sinov …», shu sayt manzili, kutayotgan 4, oxirgi xato",
              "BOSHQA manzilga ulangan" in _h and "web-sinov.up.railway.app" in _h and BU_URL in _h and "Yetkazilmagan xabarlar: 4" in _h
              and "Connection timed out" in _h and "08.10.2026 16:00" in _h, (_h, _rang))
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "sinov"
        xav(pp.reload)
        pp.wait_for_load_state("networkidle")
        holat_kut(pp)
        _h = matn(pp, "#tg-holat-matn") or ""
        n0 = len(metodlar())
        # force — o'chiq tugmani ham «bosadi» (sichqoncha hodisasi); brauzer o'chiq tugmada onclick ni ishga tushirmasligi o'lchanadi
        xav(pp.click, "#tg-security-btn", force=True, timeout=3000)
        xav(pp.click, "#tg-delete-webhook-btn", force=True, timeout=3000)
        time.sleep(0.4)
        _yangi = metodlar()[n0:]
        check("U3 sinov sayti: «Bu sinov sayti (muhit: «sinov»)», ikkala tugma O'CHIQ, bosilsa ham Telegram'ga yozish so'rovi YO'Q",
              "Bu sinov sayti (muhit: «sinov»)" in _h and ochiq(pp, "#tg-security-btn") is False
              and ochiq(pp, "#tg-delete-webhook-btn") is False and "setWebhook" not in _yangi and "deleteWebhook" not in _yangi,
              (_h, ochiq(pp, "#tg-security-btn"), _yangi))
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"
        JAVOB["getWebhookInfo"] = {"url": "https://web-sinov.up.railway.app/telegram/webhook", "pending_update_count": 0}
        xav(pp.reload)
        pp.wait_for_load_state("networkidle")
        holat_kut(pp)
        n0 = len(metodlar())
        xav(pp.click, "#tg-security-btn")
        kut(pp, "(() => { const m = document.getElementById('ccModal'); return m && getComputedStyle(m).display !== 'none'; })()", 5000)
        _mm = modal_matn(pp) or ""
        xav(pp.click, "#ccModalCancel")
        time.sleep(0.4)
        check("U4 avval TASDIQ oynasi: «Umumiy bot SHU saytga ulanadi: <shu sayt>»; «Bekor» — setWebhook YO'Q",
              "Umumiy bot SHU saytga ulanadi" in _mm and HOST in _mm and "setWebhook" not in metodlar()[n0:], (_mm, metodlar()[n0:]))
        xav(pp.click, "#tg-security-btn")
        kut(pp, "(() => { const m = document.getElementById('ccModal'); return m && getComputedStyle(m).display !== 'none'; })()", 5000)
        xav(pp.click, "#ccModalOk")
        kut(pp, "((document.getElementById('tg-security-result') || {}).textContent || '').includes('Muvaffaqiyatli')")
        time.sleep(0.5)
        with _qulf:
            _sw = [t for _, m, t in CHAQ[n0:] if m == "setWebhook"]
        _nat = matn(pp, "#tg-security-result") or ""
        check("U4b «Ulash» → setWebhook SHU saytga; oynadagi yangi sir = Telegram'ga ketgan sir; keyin holat qayta o'qildi",
              len(_sw) == 1 and _sw[0].get("url") == BU_URL and _sw[0].get("secret_token") and _sw[0]["secret_token"] in _nat
              and metodlar()[n0:].count("getWebhookInfo") >= 2, (_sw, _nat[:200], metodlar()[n0:]))
        check("U4b2 natijada bot OLDIN qayerda bo'lgani: «Bot oldin shu manzilga ulangan edi: …web-sinov…»",
              "Bot oldin shu manzilga ulangan edi: https://web-sinov.up.railway.app/telegram/webhook" in _nat, _nat[-300:])
        _html = ev(pp, "document.documentElement.outerHTML") or ""
        check("U4c sahifada umumiy bot TOKENI yo'q", UMUMIY_TOKEN not in str(_html))
        cp.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U5–U8. Korxona admini — «📱 Telegram bot» → «🔗 Botni ulash»")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        cb, pb = kontekst("ui_tg_b")
        xav(pb.goto, BU + "/sozlamalar")
        pb.wait_for_load_state("networkidle")
        _korin = ev(pb, "(() => { const b = document.getElementById('tg-ulash-btn'); return b ? getComputedStyle(b).display : null; })()")
        _q = matn(pb, "#tg-qadamlar") or ""
        check("U5 token yo'q — «🔗 Botni ulash» YASHIRIN; qadamlar: @BotFather → /newbot, «🪪 Mening ID raqamim»",
              _korin == "none" and "@BotFather" in _q and "/newbot" in _q and "🪪 Mening ID raqamim" in _q, (_korin, _q[:200]))
        xav(pb.fill, "#tg-token", B_TOKEN)
        xav(pb.click, "button[onclick='saveTgBot()']")
        kut(pb, "(() => { const b = document.getElementById('tg-ulash-btn'); return b && getComputedStyle(b).display !== 'none'; })()")
        _u = matn(pb, "#tg-ulanish") or ""
        _korin = ev(pb, "(() => { const b = document.getElementById('tg-ulash-btn'); return b ? getComputedStyle(b).display : null; })()")
        check("U5b saqlagach — tugma KO'RINADI va yoqiq («🔗 Botni ulash»), «Bot hali ulanmagan»",
              _korin not in (None, "none") and ochiq(pb, "#tg-ulash-btn") is True
              and (matn(pb, "#tg-ulash-btn") or "").strip() == "🔗 Botni ulash" and "Bot hali ulanmagan" in _u, (_korin, _u))
        JAVOB_T[(B_TOKEN, "getMe")] = {"id": 222222222, "is_bot": True, "first_name": "B bot", "username": "b_korxona_bot"}
        n0 = len(metodlar())
        xav(pb.click, "#tg-ulash-btn")
        kut(pb, "(() => { const m = document.getElementById('ccModal'); return m && getComputedStyle(m).display !== 'none'; })()", 5000)
        _mm = modal_matn(pb) or ""
        xav(pb.click, "#ccModalOk")
        kut(pb, "((document.getElementById('tg-ulanish') || {}).textContent || '').includes('Bot ulandi')")
        with _qulf:
            _sw = [(tk, t) for tk, m, t in CHAQ[n0:] if m == "setWebhook"]
        _u = matn(pb, "#tg-ulanish") or ""
        _kut_url = f"https://127.0.0.1:{port}/telegram/webhook/2"
        check("U6 tasdiq oynasi (shu sayt), keyin setWebhook B tokeni bilan …/telegram/webhook/2 → «✅ Bot ulandi: @b_korxona_bot → …»",
              "Botingiz SHU saytga ulanadi" in _mm and HOST in _mm and len(_sw) == 1 and _sw[0][0] == B_TOKEN
              and _sw[0][1].get("url") == _kut_url and f"✅ Bot ulandi: @b_korxona_bot → {_kut_url}" in _u, (_mm, _sw, _u))
        _sir = sozlama(2, "telegram_webhook_secret")
        xav(pb.reload)
        pb.wait_for_load_state("networkidle")
        kut(pb, "((document.getElementById('tg-ulanish') || {}).textContent || '').includes('ulangan')")
        _u = matn(pb, "#tg-ulanish") or ""
        _html = ev(pb, "document.documentElement.outerHTML") or ""
        check("U6b qayta ochganda «✅ Ustalar boti ulangan: @b_korxona_bot», tugma «🔗 Qayta ulash»; sir / token sahifada YO'Q",
              "✅ Ustalar boti ulangan: @b_korxona_bot" in _u and (matn(pb, "#tg-ulash-btn") or "").strip() == "🔗 Qayta ulash"
              and _sir and _sir not in str(_html) and B_TOKEN not in str(_html), _u)
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "sinov"
        xav(pb.reload)
        pb.wait_for_load_state("networkidle")
        kut(pb, "((document.getElementById('tg-ulanish') || {}).textContent || '').includes('sinov')")
        check("U7 sinov saytida: tugma O'CHIQ, «Bu sinov sayti — botni ulash faqat asosiy saytda»",
              ochiq(pb, "#tg-ulash-btn") is False and "Bu sinov sayti — botni ulash faqat asosiy saytda" in (matn(pb, "#tg-ulanish") or ""),
              matn(pb, "#tg-ulanish"))
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"
        xav(pb.reload)
        pb.wait_for_load_state("networkidle")
        JAVOB_T[(B_TOKEN, "getWebhookInfo")] = {"url": _kut_url, "pending_update_count": 0}
        n0 = len(metodlar())
        xav(pb.fill, "#tg-token", B_TOKEN2)
        xav(pb.click, "button[onclick='saveTgBot()']")
        kut(pb, "((document.getElementById('tg-ulanish') || {}).textContent || '').includes('eski bot uzildi')")
        with _qulf:
            _dw = [tk for tk, m, t in CHAQ[n0:] if m == "deleteWebhook"]
        _u = matn(pb, "#tg-ulanish") or ""
        check("U8 token almashtirildi → «eski bot uzildi … Botni ulash», deleteWebhook ESKI token bilan, holat «Bot hali ulanmagan»",
              "eski bot uzildi" in _u and "Bot hali ulanmagan" in _u and _dw == [B_TOKEN], (_u, _dw))

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U9–U10. Telefon, korxona admini /users, JS xatolari")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _bad = []
        for _login, _yol, _bl in (("ui_tg_plat", "/users", "#tg-holat"), ("ui_tg_b", "/sozlamalar", "#tg-ulanish")):
            cx, px = kontekst(_login, 390, 844)
            xav(px.goto, BU + _yol)
            px.wait_for_load_state("networkidle")
            time.sleep(0.4)
            _sc = ev(px, "document.documentElement.scrollWidth - document.documentElement.clientWidth")
            _bx = ev(px, """(s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect();
                                    return [Math.round(r.left), Math.round(r.right)]; }""", _bl)
            _tug = ev(px, """() => [...document.querySelectorAll('#tg-security-btn, #tg-delete-webhook-btn, #tg-holat-btn, #tg-ulash-btn')]
                               .filter(b => getComputedStyle(b).display !== 'none')
                               .map(b => { const r = b.getBoundingClientRect(); return [b.id, Math.round(r.right)]; })""")
            if _sc != 0 or not _bx or _bx[1] > 390 or any(r > 390 for _, r in (_tug or [])):
                _bad.append((_yol, _sc, _bx, _tug))
            cx.close()
        check("U9 telefon 390 px: /users (platforma) va /sozlamalar — gorizontal aylantirish yo'q, blok va tugmalar sig'adi", not _bad, _bad)
        SOROV.clear()
        xav(pb.goto, BU + "/users")
        pb.wait_for_load_state("networkidle")
        time.sleep(0.3)
        check("U10 korxona admini /users — holat bloki yo'q, /api/system/telegram-webhook-info so'rovi YUBORILMADI",
              ev(pb, "!!document.getElementById('tg-holat')") is False
              and not [s for s in SOROV if "telegram-webhook-info" in s[2]], [s for s in SOROV if "telegram" in s[2]])
        cb.close()
        check("U10b JS xatosi yo'q (hamma sahifa)", not JS_XATO, JS_XATO[:5])
        br.close()
    server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
