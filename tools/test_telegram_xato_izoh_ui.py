#!/usr/bin/env python3
"""
test_telegram_xato_izoh_ui.py — kech131 (zip 155): Telegram xatolari O'ZBEKCHA — HAQIQIY brauzerda (Chromium, Playwright) O'LCHANADI.

BO'LIMLAR
  X1 platforma admini, asosiy sayt, Telegram tokenni rad etdi (401): «Bot hozir qayerga ulangan» — qizil «❌ Telegram bu bot tokenini
     qabul qilmadi … Railway → … (Telegram rad etdi: Unauthorized)»;
  X2 SINOV sayti, buzuq token (404 — staging dagi holat, 08.10 jonli): «… asosiy botning tokenini bu yerga QO'YMANG …», Railway ga
     QO'YISH maslahati YO'Q, tugmalar o'chiq;
  X3 oxirgi xato 403: «Oxirgi xato (08.10.2026 16:00): sayt Telegram xabarini rad etdi (403) — … (Telegram: Wrong response …)»;
  X4 tanilmagan oxirgi xato (HTML belgilari bilan) — xom matn, qavssiz, HTML sifatida CHIZILMAYDI;
  X5 korxona admini «🔗 Botni ulash», Telegram 401: «❌ Telegram bu bot tokenini qabul qilmadi … «Bot tokeni» maydoniga …», Railway YO'Q;
  X6 telefon (390 px): uzun xato matni bilan /users va /sozlamalar — gorizontal aylantirish yo'q, blok ekranga sig'adi;
  X7 JS xatosi yo'q.
Telegram'ga HECH NARSA chiqmaydi (`urllib.request.urlopen` soxtasi; server shu jarayonda — ip oqimida).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 154) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_telegram_xato_izoh_ui.py
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

PG_BAZA = "telegram_xato_ui155_test"
_T = tempfile.mkdtemp(prefix="tg_xato_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tg_xato_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)
UMUMIY_TOKEN = "111111111:UMUMIYbotTOKENi_xxxxxxxxxxxxxxxxxxxxxx"
UMUMIY_SIR = "UMUMIY_WEBHOOK_SIRI_XUI"
B_TOKEN = "222222222:BkorxonaTOKENi_yyyyyyyyyyyyyyyyyyyyyyy"
os.environ["TELEGRAM_BOT_TOKEN"] = UMUMIY_TOKEN
os.environ["TELEGRAM_WEBHOOK_SECRET"] = UMUMIY_SIR
os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"

import urllib.request                              # noqa: E402
import urllib.error                                # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User                  # noqa: E402

CHAQ = []          # (token, metod)
JAVOB = {}         # metod → natija | ("xato", kod, tavsif)
JAVOB_T = {}       # (token, metod) → ustun
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
    with _qulf:
        CHAQ.append((token, metod))
        v = JAVOB_T.get((token, metod), JAVOB.get(metod, True))
    if isinstance(v, tuple) and v and v[0] == "xato":
        # Telegram'ning HAQIQIY rad javobi shakli (08.10 o'lchovi): HTTP kod + {"ok":false,"error_code":…,"description":…}
        raise urllib.error.HTTPError("https://api.telegram.org/x", v[1], "xato", {},
                                     io.BytesIO(json.dumps({"ok": False, "error_code": v[1], "description": v[2]}).encode()))
    return _Javob({"ok": True, "result": v})


urllib.request.urlopen = _soxta_urlopen

_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="UI XATO Dekor"))
    _db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "ui_tx_plat", "Parol123!", UserRole.ADMIN, "Platforma Egasi", company_id=1)
    auth.create_user(_db, "ui_tx_b", "Parol123!", UserRole.ADMIN, "B Admin", company_id=2)
_db.query(User).filter(User.username == "ui_tx_plat").update({"is_platform_admin": True})
_db.query(User).filter(User.username == "ui_tx_b").update({"is_platform_admin": False})
_db.commit()
_db.close()

TOKEN_401 = "Telegram bu bot tokenini qabul qilmadi"
TOKEN_404 = "Telegram bunday botni topmadi"
RAILWAY_QOY = "Railway → Variables → TELEGRAM_BOT_TOKEN ga qo'ying"
SINOV_QOYMANG = "asosiy botning tokenini bu yerga QO'YMANG"
KORXONA_MASLAHAT = "«Bot tokeni» maydoniga yozing, «Saqlash» ni bosing, so'ng «🔗 Botni ulash» ni qayta bosing"

section("X0. Tayyorgarlik")
check("X0 Python `playwright` bor", PW_BOR, _pw_xato)

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
    check("X0b lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"
    BU_URL = f"https://127.0.0.1:{port}/telegram/webhook"          # server http → https (Railway proksisi kabi)
    ME = {"id": 8606089235, "is_bot": True, "first_name": "Usta kabinet", "username": "Penoustabot"}
    JAVOB["getMe"] = ("xato", 401, "Unauthorized")
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

        def holat_kut(pg):
            return kut(pg, "(() => { const e = document.getElementById('tg-holat-matn'); "
                           "return e && e.textContent && !e.textContent.includes('Tekshirilmoqda'); })()")

        def yangila(pg):
            xav(pg.reload)
            xav(pg.wait_for_load_state, "networkidle")
            holat_kut(pg)
            return matn(pg, "#tg-holat-matn") or ""

        QIZIL = None

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("X1–X4. Platforma admini — «Bot hozir qayerga ulangan»")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        cp, pp = kontekst("ui_tx_plat")
        xav(pp.goto, BU + "/users")
        xav(pp.wait_for_load_state, "networkidle")
        holat_kut(pp)
        _h = matn(pp, "#tg-holat-matn") or ""
        QIZIL = ev(pp, "(() => { const d = document.createElement('div'); d.style.color = 'var(--m-dc2626)'; document.body.appendChild(d);"
                       " const c = getComputedStyle(d).color; d.remove(); return c; })()")
        _rang = ev(pp, "(() => { const e = document.querySelector('#tg-holat-matn div'); return e ? getComputedStyle(e).color : null; })()")
        check("X1 asosiy sayt, 401: qizil «❌ Telegram bu bot tokenini qabul qilmadi … Railway → … TELEGRAM_BOT_TOKEN ga qo'ying "
              "(Telegram rad etdi: Unauthorized)»; token sahifada YO'Q",
              ("❌ " + TOKEN_401) in _h and RAILWAY_QOY in _h and "(Telegram rad etdi: Unauthorized)" in _h and _rang == QIZIL
              and UMUMIY_TOKEN not in str(ev(pp, "document.documentElement.outerHTML")), (_h, _rang, QIZIL))
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "sinov"
        JAVOB["getMe"] = ("xato", 404, "Not Found")
        _h = yangila(pp)
        check("X2 SINOV sayti, 404 (staging holati): «bunday botni topmadi … asosiy botning tokenini bu yerga QO'YMANG», Railway ga "
              "QO'YISH maslahati YO'Q, tugmalar o'chiq",
              ("❌ " + TOKEN_404) in _h and SINOV_QOYMANG in _h and RAILWAY_QOY not in _h and "(Telegram rad etdi: Not Found)" in _h
              and ochiq(pp, "#tg-security-btn") is False and ochiq(pp, "#tg-delete-webhook-btn") is False, _h)
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"
        JAVOB["getMe"] = ME
        JAVOB["getWebhookInfo"] = {"url": BU_URL, "pending_update_count": 1, "last_error_date": 1791457200,
                                   "last_error_message": "Wrong response from the webhook: 403 Forbidden"}
        _h = yangila(pp)
        check("X3 oxirgi xato 403: «Oxirgi xato (08.10.2026 16:00): sayt Telegram xabarini rad etdi (403) — … maxfiy imzo … "
              "(Telegram: Wrong response from the webhook: 403 Forbidden)»",
              "✅ @Penoustabot shu saytga ulangan" in _h
              and "Oxirgi xato (08.10.2026 16:00): sayt Telegram xabarini rad etdi (403) — saytdagi maxfiy imzo" in _h
              and "(Telegram: Wrong response from the webhook: 403 Forbidden)" in _h, _h)
        JAVOB["getWebhookInfo"] = {"url": BU_URL, "pending_update_count": 0, "last_error_date": 1791457200,
                                   "last_error_message": "Noma'lum <b id=\"tgxss\">xato</b> matni"}
        _h = yangila(pp)
        check("X4 tanilmagan oxirgi xato — xom matn qavssiz («(Telegram:» YO'Q), HTML belgilari matn sifatida (element chizilmadi)",
              "Oxirgi xato (08.10.2026 16:00): Noma'lum <b id=\"tgxss\">xato</b> matni" in _h and "(Telegram:" not in _h
              and ev(pp, "!!document.getElementById('tgxss')") is False, _h)
        cp.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("X5. Korxona admini — «🔗 Botni ulash», Telegram tokenni rad etdi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        cb, pb = kontekst("ui_tx_b")
        xav(pb.goto, BU + "/sozlamalar")
        xav(pb.wait_for_load_state, "networkidle")
        xav(pb.fill, "#tg-token", B_TOKEN)
        xav(pb.click, "button[onclick='saveTgBot()']")
        kut(pb, "(() => { const b = document.getElementById('tg-ulash-btn'); return b && getComputedStyle(b).display !== 'none'; })()")
        JAVOB_T[(B_TOKEN, "getMe")] = ("xato", 401, "Unauthorized")
        xav(pb.click, "#tg-ulash-btn")
        kut(pb, "(() => { const m = document.getElementById('ccModal'); return m && getComputedStyle(m).display !== 'none'; })()", 5000)
        xav(pb.click, "#ccModalOk")
        kut(pb, "((document.getElementById('tg-ulanish') || {}).textContent || '').includes('❌')")
        _u = matn(pb, "#tg-ulanish") or ""
        check("X5 «❌ Telegram bu bot tokenini qabul qilmadi … «Bot tokeni» maydoniga yozing … «🔗 Botni ulash» … (Telegram rad etdi: "
              "Unauthorized)»; Railway / TELEGRAM_BOT_TOKEN YO'Q; tugma yana yoqiq",
              ("❌ " + TOKEN_401) in _u and KORXONA_MASLAHAT in _u and "(Telegram rad etdi: Unauthorized)" in _u
              and "Railway" not in _u and "TELEGRAM_BOT_TOKEN" not in _u and ochiq(pb, "#tg-ulash-btn") is True, _u)
        cb.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("X6–X7. Telefon (uzun xato matni), JS xatolari")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        JAVOB["getMe"] = ("xato", 401, "Unauthorized")
        _bad = []
        cx, px = kontekst("ui_tx_plat", 390, 844)
        xav(px.goto, BU + "/users")
        xav(px.wait_for_load_state, "networkidle")
        holat_kut(px)
        _o1 = ev(px, """() => { const e = document.getElementById('tg-holat-matn'); if (!e) return null;
                               const r = e.getBoundingClientRect();
                               return {sc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                                       l: Math.round(r.left), r: Math.round(r.right), t: e.textContent.slice(0, 60)}; }""")
        if not isinstance(_o1, dict) or _o1.get("sc") != 0 or _o1.get("r", 999) > 390 or _o1.get("l", -1) < 0 \
                or TOKEN_401 not in str(_o1.get("t")):
            _bad.append(("/users", _o1))
        cx.close()
        cy, py = kontekst("ui_tx_b", 390, 844)
        xav(py.goto, BU + "/sozlamalar")
        xav(py.wait_for_load_state, "networkidle")
        kut(py, "(() => { const b = document.getElementById('tg-ulash-btn'); return b && getComputedStyle(b).display !== 'none'; })()")
        xav(py.click, "#tg-ulash-btn")
        kut(py, "(() => { const m = document.getElementById('ccModal'); return m && getComputedStyle(m).display !== 'none'; })()", 5000)
        xav(py.click, "#ccModalOk")
        kut(py, "((document.getElementById('tg-ulanish') || {}).textContent || '').includes('❌')")
        _o2 = ev(py, """() => { const e = document.getElementById('tg-ulanish'); if (!e) return null;
                               const r = e.getBoundingClientRect();
                               return {sc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                                       l: Math.round(r.left), r: Math.round(r.right), t: e.textContent.slice(0, 60)}; }""")
        if not isinstance(_o2, dict) or _o2.get("sc") != 0 or _o2.get("r", 999) > 390 or _o2.get("l", -1) < 0 \
                or TOKEN_401 not in str(_o2.get("t")):
            _bad.append(("/sozlamalar", _o2))
        cy.close()
        check("X6 telefon 390 px: uzun xato matni bilan /users (holat bloki) va /sozlamalar (ulash xatosi) — gorizontal aylantirish yo'q, "
              "blok ekranga sig'adi", not _bad, (_bad, _o1, _o2))
        check("X7 JS xatosi yo'q (hamma sahifa)", not JS_XATO, JS_XATO[:5])
        br.close()
    server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
