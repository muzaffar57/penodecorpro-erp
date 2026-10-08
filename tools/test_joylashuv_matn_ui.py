#!/usr/bin/env python3
"""
test_joylashuv_matn_ui.py — kech132 (zip 156): joylashuv so'zlarisiz matnlar va Telegram tugmasining `title` i — HAQIQIY brauzerda
(Chromium, Playwright), HAQIQIY lokal server bilan (uvicorn, test bazasi) O'LCHANADI.

BO'LIMLAR
  U1 asosiy sayt (RAILWAY_ENVIRONMENT_NAME = «production»), platforma admini, /users: «🔄 Botni asl holatiga qaytarish» tugmasining
     `title` i ASLIDEK («Webhookni o'chirib, botni asl (polling) holatiga qaytarish» — kech123: yozuv qisqargani uchun to'liq ma'nosi
     shu yerda); asl kodda holat yuklangach '' bo'lib qolardi; ikkala tugma yoqiq;
  U2 «↻ Tekshirish» qayta bosilsa ham `title` asli qoladi;
  U3 sinov sayti («sinov»): `title` — «Faqat asosiy saytda», tugmalar o'chiq; o'sha sahifada muhit asosiyga o'tib «↻ Tekshirish» —
     asl `title` qaytadi (asli birinchi chaqiruvda saqlangan);
  U4 zip 156 matnlari CHIZILGAN sahifada (server HTML + skriptlar): Moliya bo'sh holati, Tayyor mahsulotlar «Ombor bo'sh» maslahati
     (skript chizadi), Loy retseptlari oynasi, Kirim belgisi, Murojaat izohi, Sozlamalar → Telegram shiori, Foydalanuvchilar
     ogohlantirishlari — yangi matn bor, joylashuv so'zi yo'q;
  U5 HAMMA sahifa (platforma admini 24 + korxona admini 3 + kirish sahifalari 2): ko'rinadigan matn va title / placeholder /
     aria-label / alt — joylashuv so'zi faqat ruxsat etilgan «Quyidagi …:» ketma-ketliklarida (tools/test_joylashuv_matn.py RUXSAT);
     U5c — o'lchovning o'zi (yashirin matn / atribut topiladi, <script> ichi — yo'q);
  U6 telefon (390 px): /users, /murojaat, /sozlamalar, /finance — gorizontal aylantirish yo'q; /users ogohlantirishlari ekranga sig'adi;
  U7 JS xatosi yo'q.
Telegram'ga HECH NARSA chiqmaydi (`urllib.request.urlopen` soxtasi; server shu jarayonda — ip oqimida).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 155) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_joylashuv_matn_ui.py
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
from collections import Counter

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
        print(f"  ✗ {label}   {str(detail)[:2500]}")


def section(t):
    print(f"\n--- {t} ---")


try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"

PG_BAZA = "joylashuv_ui156_test"
_T = tempfile.mkdtemp(prefix="joy_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'joy_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)
UMUMIY_TOKEN = "111111111:UMUMIYbotTOKENi_joy_xxxxxxxxxxxxxxxxxx"
os.environ["TELEGRAM_BOT_TOKEN"] = UMUMIY_TOKEN
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "UMUMIY_WEBHOOK_SIRI_JOY"
os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"

import urllib.request                              # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User                  # noqa: E402

CHAQ = []
JAVOB = {}
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
    metod = qism.split("/", 1)[1].split("?", 1)[0] if "/" in qism else ""
    with _qulf:
        CHAQ.append(metod)
        v = JAVOB.get(metod, True)
    return _Javob({"ok": True, "result": v})


urllib.request.urlopen = _soxta_urlopen

_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="JOY Dekor"))
    _db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "ui_joy_plat", "Parol123!", UserRole.ADMIN, "Platforma Egasi", company_id=1)
    auth.create_user(_db, "ui_joy_b", "Parol123!", UserRole.ADMIN, "B Admin", company_id=2)
_db.query(User).filter(User.username == "ui_joy_plat").update({"is_platform_admin": True})
_db.query(User).filter(User.username == "ui_joy_b").update({"is_platform_admin": False})
_db.commit()
_db.close()

ASL_TITLE = "Webhookni o'chirib, botni asl (polling) holatiga qaytarish"
JOY = re.compile(r"(?<![A-Za-z])((?:past|yuqori|quyi|tepa|chap|o[ʻ’‘'`]ng)(?:da|dagi|dan)[a-z]*|(?:yon|ost)ida[a-z]*)(?![A-Za-z])",
                 re.I)
# Chizilgan matnda ruxsat etilgan «Quyidagi …» ketma-ketliklari (tools/test_joylashuv_matn.py RUXSAT ning sahifada ko'rinadigan
# qismi; teglar olib tashlangan ko'rinishi)
RUXSAT_MATN = ["Quyidagi ma'lumotlarni tekshiring", "Quyidagi maydonlarni to'ldiring:",
               "👤 Quyidagi ma'lumotlar — faqat tanlangan ta'minotchiga tegishli:", "Quyidagi taqsimot — shu oyning brak yozuvlari",
               "Bekor qilingan — xomashyo ombordan yechilmagan. Quyida — boshlangandagi reja.",
               "Endi quyidagi qiymatni nusxalab, Railway → Variables", "Tasdiqlash uchun quyidagi so'zni AYNAN shunday yozing:"]
SAHIFALAR_PLAT = ["/", "/dashboard", "/orders", "/projects", "/finished", "/production", "/recipes", "/inventory", "/suppliers",
                  "/suppliers/receive", "/finance", "/debts", "/kpi", "/reports", "/returns", "/kunlik-xarajat", "/trash", "/users",
                  "/rollar", "/sozlamalar", "/logs", "/platforma", "/users/hodim-qr", "/bunday-sahifa-yoq-156"]
SAHIFALAR_B = ["/murojaat", "/sozlamalar", "/users"]

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
    JAVOB["getMe"] = {"id": 8606089235, "is_bot": True, "first_name": "Usta kabinet", "username": "Penoustabot"}
    JAVOB["getWebhookInfo"] = {"url": f"https://127.0.0.1:{port}/telegram/webhook", "pending_update_count": 0}

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
            pg.on("pageerror", lambda e: JS_XATO.append((login, pg.url, str(e)[:300])))
            if login:
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

        def ochish(pg, yol):
            xav(pg.goto, BU + yol)
            xav(pg.wait_for_load_state, "networkidle")

        def holat_kut(pg):
            return kut(pg, "(() => { const e = document.getElementById('tg-holat-matn'); "
                           "return e && e.textContent && !e.textContent.includes('Tekshirilmoqda'); })()")

        def tugma(pg, tid):
            return ev(pg, "(s) => { const b = document.getElementById(s); return b ? {t: b.title, d: b.disabled, "
                          "a: b.getAttribute('data-asl-title')} : null; }", tid)

        def korinadigan(pg):
            """Ko'rinadigan matn: body (script / style / template / noscript olib tashlangan) + title / placeholder / aria-label / alt."""
            return ev(pg, """() => { const c = document.body.cloneNode(true);
                c.querySelectorAll('script,style,template,noscript').forEach(e => e.remove());
                let t = c.textContent;
                document.querySelectorAll('[title],[placeholder],[aria-label],[alt]').forEach(e => {
                  for (const a of ['title', 'placeholder', 'aria-label', 'alt']) { const v = e.getAttribute(a); if (v) t += '\\n' + v; } });
                return t.replace(/[ \\t\\r\\n]+/g, ' '); }""")

        def joylashuv_topilmalari(matn):
            if not isinstance(matn, str):
                return [("matn olinmadi", str(matn)[:200])]
            oraliqlar = []                  # ruxsat etilgan ketma-ketliklar egallagan oraliqlar — so'z AYNAN ularning ICHIDA bo'lsin
            for r in RUXSAT_MATN:
                k = matn.find(r)
                while k >= 0:
                    oraliqlar.append((k, k + len(r)))
                    k = matn.find(r, k + 1)
            nat = []
            for x in JOY.finditer(matn):
                if not any(a <= x.start() and x.end() <= b for a, b in oraliqlar):
                    nat.append((x.group(1), matn[max(0, x.start() - 70): x.end() + 70]))
            return nat

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U1–U3. «🔄 Botni asl holatiga qaytarish» — `title`")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        cp, pp = kontekst("ui_joy_plat")
        ochish(pp, "/users")
        holat_kut(pp)
        _d1, _s1 = tugma(pp, "tg-delete-webhook-btn"), tugma(pp, "tg-security-btn")
        check("U1 asosiy sayt: holat yuklangach «🔄 Botni asl holatiga qaytarish» `title` i ASLIDEK (to'liq ma'nosi), ikkala tugma yoqiq",
              isinstance(_d1, dict) and _d1.get("t") == ASL_TITLE and _d1.get("d") is False
              and isinstance(_s1, dict) and _s1.get("t") == "" and _s1.get("d") is False, (_d1, _s1))
        xav(pp.click, "#tg-holat-btn")
        kut(pp, "(() => { const e = document.getElementById('tg-holat-matn'); return e && e.textContent.includes('shu saytga ulangan'); })()")
        time.sleep(0.4)
        _d2 = tugma(pp, "tg-delete-webhook-btn")
        check("U2 «↻ Tekshirish» qayta bosilgach ham `title` asli qoladi", isinstance(_d2, dict) and _d2.get("t") == ASL_TITLE, _d2)
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "sinov"
        ochish(pp, "/users")
        holat_kut(pp)
        _d3, _s3 = tugma(pp, "tg-delete-webhook-btn"), tugma(pp, "tg-security-btn")
        check("U3a sinov sayti: ikkala tugma o'chiq, `title` — «Faqat asosiy saytda»",
              isinstance(_d3, dict) and _d3.get("t") == "Faqat asosiy saytda" and _d3.get("d") is True
              and isinstance(_s3, dict) and _s3.get("t") == "Faqat asosiy saytda" and _s3.get("d") is True, (_d3, _s3))
        os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"
        xav(pp.click, "#tg-holat-btn", force=True)
        kut(pp, "(() => { const b = document.getElementById('tg-delete-webhook-btn'); return b && !b.disabled; })()")
        _d4, _s4 = tugma(pp, "tg-delete-webhook-btn"), tugma(pp, "tg-security-btn")
        check("U3b o'sha sahifada muhit asosiyga o'tib «↻ Tekshirish» — asl `title` QAYTADI, tugmalar yoqiq",
              isinstance(_d4, dict) and _d4.get("t") == ASL_TITLE and _d4.get("d") is False
              and isinstance(_s4, dict) and _s4.get("t") == "" and _s4.get("d") is False, (_d4, _s4))

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U4. Zip 156 matnlari chizilgan sahifada")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        ochish(pp, "/users")
        holat_kut(pp)
        _u = korinadigan(pp) or ""
        check("U4a /users: «Diqqat» — ««🔐 Telegram xavfsizligini yoqish» tugmasini bosish …», «… «🔄 Botni asl holatiga qaytarish» tugmasi "
              "orqali darhol tuzatib …»; qizil — «Agar «🔐 …» tugmasini bosgandan keyin … «🔄 …» tugmasi orqali qaytaring:»",
              "alohida serverda ishlasa — «🔐 Telegram xavfsizligini yoqish» tugmasini bosish o'sha botni vaqtincha" in _u
              and "Agar shunday bo'lsa — «🔄 Botni asl holatiga qaytarish» tugmasi orqali darhol tuzatib olishingiz mumkin." in _u
              and ("⚠️ Agar «🔐 Telegram xavfsizligini yoqish» tugmasini bosgandan keyin botingiz (boshqa, alohida serverdagi) ishlamay "
                   "qolgan bo'lsa — «🔄 Botni asl holatiga qaytarish» tugmasi orqali qaytaring:") in _u
              and "pastdagi" not in _u and "quyidagi tugma" not in _u, _u[:300])
        ochish(pp, "/finance")
        _f = ev(pp, "(() => { const e = document.getElementById('emptyState'); return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; })()")
        check("U4b /finance bo'sh holati: «Oy tanlang Oy va yilni tanlang yoki «Ko'rish» tugmasini bosing»; «Ko'rish» tugmasi bor",
              _f == "Oy tanlang Oy va yilni tanlang yoki «Ko'rish» tugmasini bosing"
              and ev(pp, "[...document.querySelectorAll('.fin-filterbar button')].some(b => b.textContent.trim() === \"Ko'rish\")") is True,
              _f)
        ochish(pp, "/finished")
        kut(pp, "((document.getElementById('fpList') || {}).textContent || '').includes('Ombor bo')")
        _fp = ev(pp, "(() => { const e = document.getElementById('fpList'); return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; })()")
        _ptug = ev(pp, "[...document.querySelectorAll('button')].some(b => b.textContent.trim() === 'Penoplast detal' && "
                       "b.querySelector('i.ti-plus') && getComputedStyle(b).display !== 'none')")
        check("U4c /finished (bo'sh ombor — skript chizadi): «Penoplast detal — + Penoplast detal tugmasi; boshqa mahsulot — Retsept bo'yicha …»; "
              "«+ Penoplast detal» tugmasi sahifada ko'rinadi",
              isinstance(_fp, str) and "Ombor bo'sh" in _fp and "Penoplast detal — + Penoplast detal tugmasi; boshqa mahsulot — Retsept "
              "bo'yicha («Ishlab chiqarish» bo'limi)" in _fp and "yuqoridagi" not in _fp and _ptug is True, (_fp, _ptug))
        ochish(pp, "/recipes")
        _r = ev(pp, "[...document.querySelectorAll('.recp-section-sub')].map(e => e.textContent.trim())")
        _rl = ev(pp, "(() => { const i = document.getElementById('f-batch'); const f = i && i.closest('.recp-field'); "
                     "const l = f && f.querySelector('label'); return l ? l.textContent.trim() : null; })()")
        check("U4d /recipes yangi retsept oynasi: «Har biridan — «Partiya hajmi (kg)» uchun kerak miqdor (kg)»; maydon yorlig'i aynan «Partiya hajmi (kg)»",
              isinstance(_r, list) and "Har biridan — «Partiya hajmi (kg)» uchun kerak miqdor (kg)" in _r and _rl == "Partiya hajmi (kg)",
              (_r, _rl))
        ochish(pp, "/suppliers/receive")
        _k = ev(pp, "(() => { const c = document.getElementById('ap-add-to-cost'); const l = c && c.closest('label'); "
                    "return l ? l.textContent.replace(/\\s+/g, ' ').trim() : null; })()")
        check("U4e /suppliers/receive: «Qo'shimcha xarajatlarni tannarxga qo'shish — yoqilsa, bu xarajatlar materiallar qiymatiga …»",
              isinstance(_k, str) and _k.startswith("Qo'shimcha xarajatlarni tannarxga qo'shish — yoqilsa, bu xarajatlar materiallar "
                                                    "qiymatiga proporsional taqsimlanib") and "yuqoridagi" not in _k, _k)
        cb, pb = kontekst("ui_joy_b")
        ochish(pb, "/murojaat")
        _m = korinadigan(pb) or ""
        check("U4f /murojaat (korxona admini): «… menyudagi «Yordam / Murojaat» bandida son paydo bo'ladi.»; menyuda shu nomli band bor",
              "Javob shu sahifada chiqadi — menyudagi «Yordam / Murojaat» bandida son paydo bo'ladi." in _m and "yonida son" not in _m
              and ev(pb, "[...document.querySelectorAll('.n-txt')].some(e => e.textContent.trim() === 'Yordam / Murojaat')") is True,
              _m[:300])
        ochish(pb, "/sozlamalar")
        _sz = ev(pb, "(() => { const i = document.getElementById('co-tg-tagline'); const e = i && i.nextElementSibling; "
                     "return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; })()")
        check("U4g /sozlamalar → Telegram shiori izohi: «Yangi usta qo'shilganda bot salom xabarining oxirida chiqadi: «🏗 Korxona nomi — shior»»",
              _sz == "Yangi usta qo'shilganda bot salom xabarining oxirida chiqadi: «🏗 Korxona nomi — shior»", _sz)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U5. Hamma sahifa — ko'rinadigan matnda joylashuv so'zi faqat ruxsat etilgan ketma-ketlikda")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _yomon, _korildi = [], []
        for kim, pg_, royxat in (("platforma admini", pp, SAHIFALAR_PLAT), ("korxona admini", pb, SAHIFALAR_B)):
            for yol in royxat:
                ochish(pg_, yol)
                time.sleep(0.3)
                _mt = korinadigan(pg_)
                _korildi.append((kim, yol, len(_mt) if isinstance(_mt, str) else None))
                for t in joylashuv_topilmalari(_mt):
                    _yomon.append((kim, yol) + t)
        # U5c — o'lchov o'zi: sahifaga yashirin matn, placeholder, title va <script> qo'shiladi — birinchi uchtasi topiladi, skript EMAS.
        # Sahifa — ruxsat etilgan «Quyidagi …» bor sahifa (Kirim): u o'tkaziladi, qo'shilgan so'zlar esa — yo'q. Natija — qo'shishdan
        # OLDINGI topilmalarga nisbatan FARQ (sahifaning o'z matni — masalan asl kodda «yuqoridagi xarajatlar» — bu tekshiruvga ta'sir qilmaydi)
        ochish(pp, "/suppliers/receive")
        _u5c_oldin = Counter(t[0] for t in joylashuv_topilmalari(korinadigan(pp)))
        ev(pp, """() => { const d = document.createElement('div'); d.style.display = 'none'; d.id = 'u5c';
            d.innerHTML = '<span>Sinov pastdagi blok</span><input placeholder="yuqoridagi maydon"><b title="chapdagi menyu">x</b>';
            const sc = document.createElement('script'); sc.type = 'text/plain'; sc.textContent = "var t = 'tepadagi';";
            d.appendChild(sc); document.body.appendChild(d); }""")
        _u5c = sorted((Counter(t[0] for t in joylashuv_topilmalari(korinadigan(pp))) - _u5c_oldin).elements())
        check("U5c o'lchov o'zi: yashirin matn, placeholder, title — topiladi; <script> ichi — YO'Q",
              _u5c == ["chapdagi", "pastdagi", "yuqoridagi"], _u5c)
        cp.close()
        cb.close()
        cl, pl = kontekst(None)
        for yol in ("/login", "/hodim/login"):
            ochish(pl, yol)
            _mt = korinadigan(pl)
            _korildi.append(("kirmagan", yol, len(_mt) if isinstance(_mt, str) else None))
            for t in joylashuv_topilmalari(_mt):
                _yomon.append(("kirmagan", yol) + t)
        cl.close()
        _bosh = [k for k in _korildi if not k[2] or k[2] < 40]
        check(f"U5a {len(_korildi)} sahifa ochildi, har birida matn bor", len(_korildi) == len(SAHIFALAR_PLAT) + len(SAHIFALAR_B) + 2
              and not _bosh, _bosh)
        check("U5b ko'rinadigan matn va title / placeholder / aria-label / alt da joylashuv so'zi YO'Q (ruxsat etilgan «Quyidagi …» dan "
              "tashqari)", not _yomon, _yomon[:20])

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U6–U7. Telefon (390 px), JS xatolari")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _tel = []
        for login, royxat in (("ui_joy_plat", ["/users", "/finance"]), ("ui_joy_b", ["/murojaat", "/sozlamalar"])):
            cx, px = kontekst(login, 390, 844)
            for yol in royxat:
                ochish(px, yol)
                if yol == "/users":
                    holat_kut(px)
                # /users: har tugmadan OLDINGI blok — uning ogohlantirishi (Diqqat / qizil); faqat joylashuv o'lchanadi (matn — U4a)
                _o = ev(px, """() => { const sc = document.documentElement.scrollWidth - document.documentElement.clientWidth;
                    const bloklar = [...document.querySelectorAll('#tg-security-btn, #tg-delete-webhook-btn')].map(b => {
                      const w = b.previousElementSibling; if (!w || w.tagName !== 'DIV') return {yoq: true};
                      const r = w.getBoundingClientRect(); return {l: Math.round(r.left), r: Math.round(r.right), h: Math.round(r.height)}; });
                    return {sc, bloklar}; }""")
                _yaxshi = isinstance(_o, dict) and _o.get("sc") == 0 \
                    and all(not b.get("yoq") and b["l"] >= 0 and b["r"] <= 390 and b["h"] > 0 for b in _o.get("bloklar", []))
                if yol == "/users":
                    _yaxshi = _yaxshi and len(_o.get("bloklar", [])) == 2
                if not _yaxshi:
                    _tel.append((yol, _o))
            cx.close()
        check("U6 telefon 390 px: /users (ikkala ogohlantirish ekranga sig'adi), /finance, /murojaat, /sozlamalar — gorizontal aylantirish yo'q",
              not _tel, _tel)
        check("U7 JS xatosi yo'q (hamma sahifa)", not JS_XATO, JS_XATO[:5])
        br.close()
    server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
