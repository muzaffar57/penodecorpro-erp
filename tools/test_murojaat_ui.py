#!/usr/bin/env python3
"""
test_murojaat_ui.py — kech127 (zip 151): «YORDAM / MUROJAAT» va «PLATFORMA → MUROJAATLAR» — HAQIQIY brauzerda (Chromium,
Playwright) O'LCHANADI. EGASI QARORLARI 08.10 01:40 (QAYTA SO'RALMAYDI): murojaatni FAQAT korxona admini yozadi; javob — DASTUR
ICHIDA (menyuda o'qilmagan javob soni).
BO'LIMLAR:
  B1 korxona admini «Buyurtmalar» dan menyudagi «Yordam / Murojaat» ga o'tadi — sahifa ochiladi, qaysi sahifadan kelgani (/orders)
     yozilgan; bo'sh matn — so'rov YO'Q (xabar); tur + matn (HTML belgilari bilan) + PNG rasm → yuborildi: so'rov tanasi (tur, matn,
     sahifa, ekran, fayl), ro'yxatda #raqam, yozishma ochildi, matn ASLICHA (HTML bajarilmaydi — XSS yo'q), rasm yuklandi;
  B2 platforma egasi: menyuda «Platforma» yonida son; «💬 Murojaatlar» — korxona nomi, «Yangi» sanog'i; ochilganda kontekst
     (sahifa /orders, ekran, oxirgi texnik xato), mijoz rasmi KO'RINADI (platforma admini uchun fayl himoyasi), matn aslicha;
     javob (rasm bilan) → «Javob berildi» chipiga o'tdi, menyu soni kamaydi;
  B3 korxona admini: menyuda son 1; ro'yxatda «Yangi javob»; ochganda — javob va uning rasmi, son yo'qoladi; qo'shimcha xabar →
     «Yangi»;
  B4 platforma egasi yopadi (tasdiq oynasi «Ha, yopish» / «Yo'q, qolsin»; «Yo'q» — o'zgarmaydi) → mijozda yozish formasi yo'q,
     «yopilgan» izohi;
  B5 telefon (390 px) va ilova yon paneli (756 px): gorizontal aylantirish yo'q, forma va yozishma sig'adi;
  B6 JS xatosi yo'q (har sahifa);
  B7 (kech128, zip 152 — staging jonli sinovida topilgan) platforma yozishma oynasi: rasm so'rovlari USHLAB turilib, yozishma
     chizilgandan keyin qo'yib yuboriladi — rasmlar yuklangach oyna eng pastda, eng yangi xabar to'liq ko'rinadi; foydalanuvchi
     o'zi tepaga aylantirgan bo'lsa — keyingi rasm yuklanganda oyna sakramaydi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 150) qarshi QULAMAYDI — yiqiladi (B7 — zip 151 ga
qarshi ham yiqiladi).
ISHLATISH: python3 tools/test_murojaat_ui.py
"""
import os
import re
import io
import sys
import glob
import time
import socket
import tempfile
import threading
import contextlib
from datetime import timedelta

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


try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"

PG_BAZA = "murojaat_ui_test"
_T = tempfile.mkdtemp(prefix="murojaat_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'murojaat_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User, ErrorLog, _uzb_now   # noqa: E402

Murojaat = getattr(models, "Murojaat", None)
MurojaatXabari = getattr(models, "MurojaatXabari", None)
TG = []
main._send_telegram = lambda matn, company_id=None: TG.append((matn, company_id)) or True

UPL = os.path.join(ROOT, "static", "uploads")
_BOSH = {p: (set(os.listdir(p)) if os.path.isdir(p) else set())
         for p in (os.path.join(UPL, "murojaat"), os.path.join(UPL, "_kichik", "murojaat"))}

_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="UI Alfa Dekor"))
    _db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "ui_ega", "Parol123!", UserRole.ADMIN, "Platforma Egasi", company_id=1)
    auth.create_user(_db, "ui_a_admin", "Parol123!", UserRole.ADMIN, "Alisher Admin", company_id=2)
_db.query(User).filter(User.username == "ui_ega").update({"is_platform_admin": True})
_db.query(User).filter(User.username == "ui_a_admin").update({"is_platform_admin": False})
_db.add(ErrorLog(company_id=2, error_message="ValueError: narx bo'sh", endpoint="/api/orders", method="POST",
                 created_at=_uzb_now() - timedelta(minutes=30)))
_db.commit()
_db.close()


def png_fayl(nom, rang):
    from PIL import Image
    y = os.path.join(_T, nom)
    Image.new("RGB", (120, 80), rang).save(y, "PNG")
    return y


RASM1 = png_fayl("ekran1.png", (220, 40, 40))
RASM2 = png_fayl("javob.png", (40, 40, 220))
XSS = "Saqlashda xato <img src=x onerror=\"window.__xss=1\"> & «qo'shtirnoq»\n2-qator"


def baza(fn):
    s = SessionLocal()
    try:
        return fn(s)
    except Exception as e:                 # noqa: BLE001
        return f"XATO: {type(e).__name__}: {e}"
    finally:
        s.close()


section("B0. Tayyorgarlik")
check("B0 Python `playwright` bor", PW_BOR, _pw_xato)
check("B0a modellar bor (`Murojaat`, `MurojaatXabari`)", Murojaat is not None and MurojaatXabari is not None)

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
    check("B0b lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"

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
            ctx.set_default_timeout(30000)
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                                 r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATO.append((login, str(e)[:300])))
            pg.on("request", lambda rq: SOROV.append((rq.method, rq.url, rq.post_data_buffer)) if rq.method == "POST"
                  and "/murojaat" in rq.url else None)
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

        def kut(pg, kod, ms=30000):
            try:
                pg.wait_for_function(kod, timeout=ms)
                return True
            except Exception:              # noqa: BLE001
                return False

        def xav(f, *a, **k):
            """Brauzer amali — element topilmasa (masalan, asl kodda yoki mutatsiyada) sinov QULAMAYDI, tekshiruv yiqiladi."""
            try:
                return f(*a, **k)
            except Exception as ex:        # noqa: BLE001
                print(f"    (amal bajarilmadi: {getattr(f, '__name__', f)} {a[:1]} — {type(ex).__name__})")
                return None

        def nav_soni(pg, href):
            return ev(pg, """(h) => { const a = document.querySelector('a.nav-item[href="' + h + '"]');
                                     if (!a) return null; const b = a.querySelector('.n-badge'); return b ? b.textContent.trim() : ''; }""", href)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("B1. Korxona admini — yangi murojaat")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        ca, pa = kontekst("ui_a_admin")
        xav(pa.goto, BU + "/orders")
        pa.wait_for_load_state("networkidle")
        _bor = ev(pa, "!!document.querySelector('a.nav-item[href=\"/murojaat\"]')")
        if _bor is True:
            xav(pa.click, "a.nav-item[href='/murojaat']")
            pa.wait_for_load_state("networkidle")
        check("B1 menyudagi «Yordam / Murojaat» dan sahifa ochildi (Buyurtmalardan)", _bor is True and pa.url.endswith("/murojaat"), pa.url)
        _iz = ev(pa, "document.getElementById('mjSahifaIzoh') ? document.getElementById('mjSahifaIzoh').textContent : null")
        check("B1a qaysi sahifadan kelgani yozilgan (/orders)", isinstance(_iz, str) and "/orders" in _iz, _iz)
        SOROV.clear()
        if _bor is True:
            xav(pa.click, "#mjYubor")
            time.sleep(0.5)
        _msg = ev(pa, "(document.querySelector('.msg-box, #msgBox, .toast, [class*=\"msg\"]') || {}).textContent || ''")
        check("B1b bo'sh matn — so'rov YUBORILMAYDI", not [s for s in SOROV if s[1].endswith("/api/murojaatlar")], SOROV)
        if _bor is True:
            xav(pa.check, "input[name=mjTuri][value=xato]")
            xav(pa.fill, "#mjMatn", XSS)
            xav(pa.set_input_files, "#mjRasm", RASM1)
            xav(pa.click, "#mjYubor")
            kut(pa, "!document.getElementById('mjYozishma').hidden && document.querySelectorAll('#mjXabarlar .mj-xabar').length === 1")
            kut(pa, "(() => { const i = document.querySelector('#mjXabarlar img'); return i && i.complete && i.naturalWidth > 0; })()", 15000)
        _post = [s for s in SOROV if s[1].endswith("/api/murojaatlar")]
        _tana = (_post[0][2] or b"").decode("utf-8", "replace") if _post else ""
        check("B1c so'rov tanasi: tur «xato», matn, sahifa /orders, ekran 1440x900, PNG fayl",
              len(_post) == 1 and 'name="turi"\r\n\r\nxato' in _tana and 'name="sahifa"\r\n\r\n/orders' in _tana
              and 'name="ekran"\r\n\r\n1440x900' in _tana and 'filename="ekran1.png"' in _tana and "window.__xss=1" in _tana,
              (len(_post), _tana[:400]))
        _m = baza(lambda s: [(m.id, m.turi, m.kelgan_sahifa) for m in s.query(Murojaat).all()]) if Murojaat is not None else []
        M1 = _m[0][0] if isinstance(_m, list) and _m else None
        _hol = ev(pa, """() => { const x = document.querySelector('#mjXabarlar .mj-xabar');
            const img = x ? x.querySelector('img') : null;
            return {t: x ? x.querySelector('.t').textContent : null, inj: x ? x.querySelectorAll('.t img, .t *').length : -1,
                    xss: window.__xss || 0, img: img ? img.complete && img.naturalWidth > 0 : false,
                    royxat: document.getElementById('mjRoyxat').innerText,
                    sarlavha: document.getElementById('mjYozSarlavha').innerText}; }""")
        check("B1d yozishma ochildi: matn ASLICHA (HTML bajarilmadi, XSS yo'q), rasm yuklandi; ro'yxatda #raqam, «Xato», «Yangi»",
              isinstance(_hol, dict) and _hol.get("t") == XSS and _hol.get("inj") == 0 and _hol.get("xss") == 0 and _hol.get("img") is True
              and M1 is not None and f"#{M1}" in (_hol.get("royxat") or "") and "Xato" in (_hol.get("royxat") or "")
              and "Yangi" in (_hol.get("sarlavha") or ""), (_hol, _m))
        check("B1e bazada: tur «xato», sahifa /orders", isinstance(_m, list) and _m and _m[0][1:] == ("xato", "/orders"), _m)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("B2. Platforma egasi — ko'rish va javob")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        ce, pe = kontekst("ui_ega")
        xav(pe.goto, BU + "/platforma")
        pe.wait_for_load_state("networkidle")
        check("B2 menyuda «Platforma» yonida son 1; «Yordam / Murojaat» bandi yo'q", nav_soni(pe, "/platforma") == "1"
              and nav_soni(pe, "/murojaat") is None, (nav_soni(pe, "/platforma"), nav_soni(pe, "/murojaat")))
        kut(pe, "document.querySelectorAll('#mpRoyxat [data-mp-id]').length === 1")
        _r = ev(pe, """() => ({royxat: document.getElementById('mpRoyxat').innerText,
                              yangi: (document.querySelector('#mpChiplar [data-son="yangi"]') || {}).textContent})""")
        check("B2a «💬 Murojaatlar»: korxona nomi, parcha (matn aslicha), «Yangi · 1»", isinstance(_r, dict)
              and "UI Alfa Dekor" in (_r.get("royxat") or "") and "<img src=x" in (_r.get("royxat") or "") and _r.get("yangi") == "1", _r)
        if M1:
            xav(pe.click, f"#mpRoyxat [data-mp-id='{M1}']")
            kut(pe, "document.querySelectorAll('#mpXabarlar .mp-xabar').length === 1")
            kut(pe, "(() => { const i = document.querySelector('#mpXabarlar img'); return i && i.complete && i.naturalWidth > 0; })()", 15000)
        _y = ev(pe, """() => { const k = document.querySelector('#mpYozishma .mp-kontekst');
            const x = document.querySelector('#mpXabarlar .mp-xabar'); const i = x ? x.querySelector('img') : null;
            return {k: k ? k.innerText : '', t: x ? x.querySelector('.t').textContent : null, xss: window.__xss || 0,
                    img: i ? i.complete && i.naturalWidth > 0 : false}; }""")
        check("B2b kontekst: korxona, admin (login), sahifa /orders, ekran 1440x900, oxirgi texnik xato; matn aslicha; mijoz rasmi KO'RINADI",
              isinstance(_y, dict) and all(w in (_y.get("k") or "") for w in ("UI Alfa Dekor", "Alisher Admin (ui_a_admin)", "sahifa: /orders",
                                                                               "1440x900", "ValueError: narx bo'sh"))
              and _y.get("t") == XSS and _y.get("xss") == 0 and _y.get("img") is True, _y)
        if M1:
            xav(pe.fill, "#mpMatn", "Rahmat! Tuzatdik — sahifani yangilang.")
            xav(pe.set_input_files, "#mpRasm", RASM2)
            xav(pe.click, "#mpYozishma button[data-mp='javob']")
            kut(pe, "document.querySelectorAll('#mpXabarlar .mp-xabar').length === 2")
        _z = ev(pe, """() => ({n: document.querySelectorAll('#mpXabarlar .mp-xabar').length,
                              oxirgi: (document.querySelector('#mpXabarlar .mp-xabar.platforma .t') || {}).textContent,
                              yangi: (document.querySelector('#mpChiplar [data-son="yangi"]') || {}).textContent,
                              javob: (document.querySelector('#mpChiplar [data-son="javob_berildi"]') || {}).textContent})""")
        check("B2c javob yuborildi: yozishmada 2 xabar, «Yangi · 0», «Javob berildi · 1», menyu soni yo'qoldi",
              isinstance(_z, dict) and _z.get("n") == 2 and _z.get("oxirgi") == "Rahmat! Tuzatdik — sahifani yangilang."
              and _z.get("yangi") == "0" and _z.get("javob") == "1" and nav_soni(pe, "/platforma") == "", (_z, nav_soni(pe, "/platforma")))

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("B3. Korxona admini — javobni o'qish")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        xav(pa.goto, BU + "/projects")
        pa.wait_for_load_state("networkidle")
        check("B3 menyuda «Yordam / Murojaat» yonida son 1", nav_soni(pa, "/murojaat") == "1", nav_soni(pa, "/murojaat"))
        xav(pa.goto, BU + "/murojaat")
        pa.wait_for_load_state("networkidle")
        kut(pa, "document.querySelectorAll('#mjRoyxat [data-id]').length === 1")
        _q = ev(pa, "document.getElementById('mjRoyxat').innerText")
        check("B3a ro'yxatda «Yangi javob» va «Javob berildi»", isinstance(_q, str) and "Yangi javob" in _q and "Javob berildi" in _q, _q)
        if M1:
            xav(pa.click, f"#mjRoyxat [data-id='{M1}']")
            kut(pa, "document.querySelectorAll('#mjXabarlar .mj-xabar').length === 2")
            kut(pa, "(() => { const i = document.querySelector('#mjXabarlar .mj-xabar.platforma img'); return i && i.complete && i.naturalWidth > 0; })()", 15000)
        _q = ev(pa, """() => { const x = document.querySelector('#mjXabarlar .mj-xabar.platforma'); const i = x ? x.querySelector('img') : null;
            return {t: x ? x.querySelector('.t').textContent : null, m: x ? x.querySelector('.m').textContent : '',
                    img: i ? i.complete && i.naturalWidth > 0 : false, royxat: document.getElementById('mjRoyxat').innerText}; }""")
        check("B3b javob ko'rindi («Dastur xizmati»), javob rasmi yuklandi; «Yangi javob» belgisi va menyu soni yo'qoldi",
              isinstance(_q, dict) and _q.get("t") == "Rahmat! Tuzatdik — sahifani yangilang." and "Dastur xizmati" in (_q.get("m") or "")
              and _q.get("img") is True and "Yangi javob" not in (_q.get("royxat") or "") and nav_soni(pa, "/murojaat") == "",
              (_q, nav_soni(pa, "/murojaat")))
        if M1:
            xav(pa.fill, "#mjJavobMatn", "Rahmat, endi ishlayapti. Yana bir savol bor.")
            xav(pa.click, "#mjJavobYubor")
            kut(pa, "document.querySelectorAll('#mjXabarlar .mj-xabar').length === 3")
        _h = baza(lambda s: s.query(Murojaat).filter(Murojaat.id == M1).first().holat) if M1 else None
        check("B3c qo'shimcha xabar — yozishmada 3 xabar, holat «Yangi»", _h == "yangi"
              and ev(pa, "document.querySelectorAll('#mjXabarlar .mj-xabar').length") == 3
              and "Yangi" in (ev(pa, "document.getElementById('mjYozSarlavha').innerText") or ""), _h)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("B4. Platforma egasi — yopish")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        xav(pe.goto, BU + "/platforma")
        pe.wait_for_load_state("networkidle")
        kut(pe, "document.querySelectorAll('#mpRoyxat [data-mp-id]').length === 1")
        if M1:
            xav(pe.click, f"#mpRoyxat [data-mp-id='{M1}']")
            kut(pe, "!!document.querySelector('#mpYozishma button[data-mp=\"yop\"]')")
            xav(pe.click, "#mpYozishma button[data-mp='yop']")
            kut(pe, "getComputedStyle(document.getElementById('ccModal')).display !== 'none'")
        _o = ev(pe, """() => ({sar: (document.getElementById('ccModalTitle') || {}).textContent, ok: (document.getElementById('ccModalOk') || {}).textContent,
                              yoq: (document.getElementById('ccModalCancel') || {}).textContent})""")
        check("B4 tasdiq oynasi: «Murojaatni yopish», «Ha, yopish» / «Yo'q, qolsin»", isinstance(_o, dict)
              and _o.get("sar") == "Murojaatni yopish" and _o.get("ok") == "Ha, yopish" and _o.get("yoq") == "Yo'q, qolsin", _o)
        if M1:
            xav(pe.click, "#ccModalCancel")
            time.sleep(0.4)
        _h = baza(lambda s: s.query(Murojaat).filter(Murojaat.id == M1).first().holat) if M1 else None
        check("B4a «Yo'q, qolsin» — o'zgarmadi", _h == "yangi", _h)
        if M1:
            xav(pe.click, "#mpYozishma button[data-mp='yop']")
            kut(pe, "getComputedStyle(document.getElementById('ccModal')).display !== 'none'")
            xav(pe.click, "#ccModalOk")
            kut(pe, "!document.querySelector('#mpYozishma button[data-mp=\"yop\"]') && !document.getElementById('mpMatn')")
        _h = baza(lambda s: s.query(Murojaat).filter(Murojaat.id == M1).first().holat) if M1 else None
        check("B4b yopildi — platformada javob formasi va «Yopish» yo'q; bazada «yopildi»", _h == "yopildi"
              and ev(pe, "!document.getElementById('mpMatn') && document.getElementById('mpYozishma').innerText.includes('yopilgan')") is True, _h)
        xav(pa.goto, BU + "/murojaat")
        pa.wait_for_load_state("networkidle")
        kut(pa, "document.querySelectorAll('#mjRoyxat [data-id]').length === 1")
        if M1:
            xav(pa.click, f"#mjRoyxat [data-id='{M1}']")
            kut(pa, "!document.getElementById('mjYozishma').hidden")
        check("B4c mijozda — yozish formasi yo'q, «yopilgan» izohi", ev(pa, "document.getElementById('mjYoz').hidden && "
                                                                         "!document.getElementById('mjYopiqIzoh').hidden") is True)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("B5. Telefon va ilova yon paneli")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _bad = []
        for _w in (390, 756):
            for _login, _url in (("ui_a_admin", "/murojaat"), ("ui_ega", "/platforma")):
                cx, px = kontekst(_login, _w, 844)
                xav(px.goto, BU + _url)
                px.wait_for_load_state("networkidle")
                time.sleep(0.5)
                _sc = ev(px, "document.documentElement.scrollWidth - document.documentElement.clientWidth")
                _el = ev(px, """(id) => { const e = document.getElementById(id); if (!e) return null; const r = e.getBoundingClientRect();
                                         return r.right <= document.documentElement.clientWidth + 1 && r.left >= -1; }""",
                         "mjMatn" if _url == "/murojaat" else "mpRoyxat")
                if not (isinstance(_sc, (int, float)) and _sc <= 1 and _el is True):
                    _bad.append((_w, _url, _sc, _el))
                cx.close()
        check("B5 390 px va 756 px: gorizontal aylantirish yo'q, forma / ro'yxat ekranga sig'adi", not _bad, _bad)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("B7. Platforma yozishma oynasi — rasmlar KEYIN yuklansa ham eng yangi xabar ko'rinadi (kech128, zip 152)")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        # O'LCHANGAN (staging, 08.10): oyna (420 px) rasmlar yuklanishidan OLDIN pastga aylantirilardi; rasmlar keyin yuklanib
        # balandlik oshgach eng yangi xabar pastda yashirinib qolardi (3 xabar, 2 rasm: oyna boshida — 578 / 420 px). Rasm so'rovlari
        # USHLAB turiladi (`page.route`) va yozishma chizilgandan KEYIN qo'yib yuboriladi — kechikish aniq takrorlanadi.
        def baland_png(rang):
            from PIL import Image
            b = io.BytesIO()
            Image.new("RGB", (300, 900), rang).save(b, "PNG")
            return b.getvalue()

        _YUBOR = """async ([yol, maydonlar, b64]) => {
            const fd = new FormData();
            for (const k in maydonlar) fd.append(k, maydonlar[k]);
            if (b64) { const s = atob(b64); const u = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i);
                       fd.append('file', new Blob([u], {type: 'image/png'}), 'baland.png'); }
            const r = await fetch(yol, {method: 'POST', body: fd, credentials: 'same-origin'});
            let d = null; try { d = await r.json(); } catch (e) { d = null; }
            return {st: r.status, id: d && d.id}; }"""

        def yozishma_yasa(nomi, rang1, rang2):
            """Mijoz (rasm bilan) → platforma javobi (rasm bilan) → mijozning eng yangi xabari (rasmsiz) — o'z sahifalaridan
            (brauzer seansi bilan). Murojaat raqami yoki None."""
            import base64
            r1 = ev(pa, _YUBOR, ["/api/murojaatlar", {"turi": "savol", "matn": nomi + " — 1-xabar"},
                                 base64.b64encode(baland_png(rang1)).decode()])
            mid = r1.get("id") if isinstance(r1, dict) and r1.get("st") == 200 else None
            if not mid:
                print(f"    (yozishma yasalmadi: {r1})")
                return None
            r2 = ev(pe, _YUBOR, [f"/api/platform/murojaatlar/{mid}/javob", {"matn": nomi + " — platforma javobi"},
                                 base64.b64encode(baland_png(rang2)).decode()])
            r3 = ev(pa, _YUBOR, [f"/api/murojaatlar/{mid}/xabar", {"matn": nomi + " — ENG YANGI XABAR"}, ""])
            if not (isinstance(r2, dict) and r2.get("st") == 200 and isinstance(r3, dict) and r3.get("st") == 200):
                print(f"    (yozishma to'liq yasalmadi: {r2} {r3})")
                return None
            return mid

        USHLANGAN = []
        RASM_YOL = re.compile(r".*/static/uploads/murojaat/.*")

        def ushla(route):
            USHLANGAN.append(route)

        def qoyib_yubor():
            while USHLANGAN:
                rt = USHLANGAN.pop(0)
                try:
                    rt.continue_()
                except Exception:          # noqa: BLE001
                    pass

        _OYNA = """() => { const xs = document.getElementById('mpXabarlar'); if (!xs) return null;
            const x = xs.querySelectorAll('.mp-xabar'); const oxirgi = x.length ? x[x.length - 1].getBoundingClientRect() : null;
            const q = xs.getBoundingClientRect();
            return {n: x.length, sh: xs.scrollHeight, ch: xs.clientHeight, st: Math.round(xs.scrollTop),
                    pastda: xs.scrollHeight - xs.clientHeight - xs.scrollTop < 24,
                    oxirgiKorinadi: !!oxirgi && oxirgi.bottom <= q.bottom + 1 && oxirgi.top >= q.top - 1,
                    oxirgiMatn: x.length ? x[x.length - 1].querySelector('.t').textContent : '',
                    rasmlar: [...xs.querySelectorAll('img')].map(i => i.complete && i.naturalWidth > 0)}; }"""
        M2 = yozishma_yasa("B7 birinchi", (200, 60, 60), (60, 160, 60))
        M3 = yozishma_yasa("B7 ikkinchi", (60, 60, 200), (200, 160, 40))
        check("B7 tayyorgarlik: 2 ta yozishma (har birida 3 xabar, 2 baland rasm)", M2 is not None and M3 is not None, (M2, M3))
        xav(pe.goto, BU + "/platforma")
        pe.wait_for_load_state("networkidle")
        xav(pe.route, RASM_YOL, ushla)
        _o1 = _o2 = _o3 = None
        if M2:
            kut(pe, f"!!document.querySelector('#mpRoyxat [data-mp-id=\"{M2}\"]')")
            xav(pe.click, f"#mpRoyxat [data-mp-id='{M2}']")
            kut(pe, "document.querySelectorAll('#mpXabarlar .mp-xabar').length === 3")
            kut(pe, "false", 1500)                                  # rasm so'rovlari ushlandi — chizilgan holat
            _o1 = ev(pe, _OYNA)
            qoyib_yubor()
            kut(pe, "[...document.querySelectorAll('#mpXabarlar img')].every(i => i.complete && i.naturalWidth > 0)", 15000)
            kut(pe, "false", 600)                                   # `load` ishlovchilari
            _o2 = ev(pe, _OYNA)
        check("B7a rasmlar yuklanguncha — xabarlar chizildi, rasmlar hali kelmagan (kechikish takrorlandi)",
              isinstance(_o1, dict) and _o1.get("n") == 3 and _o1.get("rasmlar") and not any(_o1.get("rasmlar")), _o1)
        check("B7b rasmlar yuklangach — oyna toshdi (balandlik > oyna) va eng PASTDA: eng yangi xabar to'liq ko'rinadi",
              isinstance(_o2, dict) and all(_o2.get("rasmlar") or [False]) and _o2.get("sh", 0) > _o2.get("ch", 0) + 100
              and _o2.get("pastda") is True and _o2.get("oxirgiKorinadi") is True
              and (_o2.get("oxirgiMatn") or "").endswith("ENG YANGI XABAR"), _o2)
        _n_ushlangan = -1
        if M3:
            xav(pe.click, f"#mpRoyxat [data-mp-id='{M3}']")
            kut(pe, "document.querySelectorAll('#mpXabarlar .mp-xabar').length === 3 && "
                    "document.querySelector('#mpXabarlar .mp-xabar:last-child .t').textContent.includes('B7 ikkinchi')")
            kut(pe, "false", 1500)
            _n_ushlangan = len(USHLANGAN)
            if USHLANGAN:                                          # faqat BIRINCHI rasm keladi — oyna toshadi
                try:
                    USHLANGAN.pop(0).continue_()
                except Exception:          # noqa: BLE001
                    pass
            kut(pe, "[...document.querySelectorAll('#mpXabarlar img')].filter(i => i.complete && i.naturalWidth > 0).length === 1", 15000)
            kut(pe, "false", 600)
            # foydalanuvchi eski xabarni o'qish uchun oynani TEPAGA aylantiradi (g'ildirak — haqiqiy `scroll` hodisasi)
            _q = ev(pe, "() => { const r = document.getElementById('mpXabarlar').getBoundingClientRect(); return [r.x + r.width / 2, r.y + 60]; }")
            if isinstance(_q, list):
                xav(pe.mouse.move, _q[0], _q[1])
                xav(pe.mouse.wheel, 0, -5000)
            kut(pe, "document.getElementById('mpXabarlar').scrollTop === 0", 3000)
            kut(pe, "false", 300)
            qoyib_yubor()                                          # ikkinchi rasm endi keladi
            kut(pe, "[...document.querySelectorAll('#mpXabarlar img')].every(i => i.complete && i.naturalWidth > 0)", 15000)
            kut(pe, "false", 600)
            _o3 = ev(pe, _OYNA)
        check("B7c foydalanuvchi o'zi tepaga aylantirgan bo'lsa — keyingi rasm yuklanganda oyna SAKRAMAYDI (tepada qoladi)",
              _n_ushlangan == 2 and isinstance(_o3, dict) and all(_o3.get("rasmlar") or [False]) and _o3.get("st") == 0
              and _o3.get("sh", 0) > _o3.get("ch", 0) + 100, (_n_ushlangan, _o3))
        xav(pe.unroute, RASM_YOL)
        qoyib_yubor()

        section("B6. JS xatolari")
        check("B6 hech bir sahifada JS xatosi yo'q", not JS_XATO, JS_XATO[:5])
        ca.close()
        ce.close()
        br.close()

# test yaratgan fayllar (repo papkasida qolmasin)
for _p, _b in _BOSH.items():
    for _f in (set(os.listdir(_p)) if os.path.isdir(_p) else set()) - _b:
        try:
            os.remove(os.path.join(_p, _f))
        except OSError:
            pass

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
os._exit(0 if not FAIL else 1)
