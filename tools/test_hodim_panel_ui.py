#!/usr/bin/env python3
"""
test_hodim_panel_ui.py — kech133 (zip 158): hodim paneli (`/hodim`) — HAQIQIY brauzerda (Chromium, Playwright), HAQIQIY lokal server
bilan (uvicorn, test bazasi) O'LCHANADI: telefon (375 / 390 px) va kompyuter (1440 px).

NIMA UCHUN KERAK — egasi 09.10 12:00: hodimlar telefondan «avans yozadigan joyni topa olishmayapti, pastga surilmayapti».
  O'LCHANGAN (zip 157 kodi, `work/k158/hodim_skrol.py`): `body` — `height` = ekran, `overflow: hidden` (style.css), 20 to'lovda forma
  915 px da (ekran 812), g'ildirak bilan siljish 0. EGASI QARORLARI: forma TEPADA; joriy oy ochiq, tugagan oylar yopiq, oxirgi 12 oy.

BO'LIMLAR
  U1 375 / 390 / 1440 px: sahifa suriladi (g'ildirak — siljish > 0, eng pastki «Mening so'rovlarim» ko'rinadi), `body` surishni to'smaydi;
  U2 forma BIRINCHI: sahifa ochilganda «Yuborish» tugmasi ekranda va bosiladi; tartib forma → Oyligim → So'rovlarim;
  U3 Oyligim: joriy oy ochiq («(joriy oy — hozirgacha)», to'lovlar), o'tgan oy — yopiq, sarlavhada «Qolgan … so'm», ochilsa to'lovlar;
      eski oylar — yopiq «Ko'rish», ochilganda BITTA so'rov (`?oy=`), sarlavha «Qolgan …» bo'ladi, qayta ochilganda so'rov YO'Q;
      ishga kirishdan oldingi to'lov oyi — «Ortiqcha olingan …»; sarlavha bosish maydoni ≥ 44 px;
  U4 server xatosi (500) — «Yuklashda xato» + «🔄 Qayta yuklash»; tugma bosilsa — qayta so'raladi va chiziladi;
  U5 telefonda forma orqali avans yuboriladi — «✅ Yuborildi!», «Mening so'rovlarim» da «⏳ Kutilmoqda»;
  U6 JS sahifa xatosi yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 157) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_hodim_panel_ui.py
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
from datetime import datetime

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
        print(f"  ✗ {label}   {str(detail)[:1500]}")


def section(t):
    print(f"\n--- {t} ---")


try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"

PG_BAZA = "hodim_panel_ui158_test"
_T = tempfile.mkdtemp(prefix="hodim_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'hodim_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import UserRole, Employee, EmployeeAdvance  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

OY = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
BUGUN = tashkent_date()


def oldin(n):
    y, m = BUGUN.year, BUGUN.month
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return y, m


def nomi(n):
    y, m = oldin(n)
    return f"{OY[m]} {y}"


# Fikstura: hodim U — 4 oy oldin ishga kirgan, 11 000 000; to'lovlar: joriy 8, o'tgan 12, 3-oy 1, 6-oy (ishga kirishdan oldin) 1
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "hpu_admin", "Parol123!", UserRole.ADMIN, "HPU admin", company_id=1)
s.commit()
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "hpu_admin", "password": "Parol123!"}, follow_redirects=False)
EU = A.post("/api/employees", json={"name": "Ulug'bek", "position": "Kesuvchi", "pay_type": "fixed",
                                    "fixed_amount": 11_000_000}).json().get("id")
A.post(f"/api/employees/{EU}/set-login", data={"phone": "+998901119911", "pin": "4321"})
_yh, _mh = oldin(4)
s = SessionLocal()
s.query(Employee).filter(Employee.id == EU).update({"hire_date": datetime(_yh, _mh, 1, 5, 0)})
for i in range(min(8, BUGUN.day)):
    s.add(EmployeeAdvance(employee_id=EU, amount=50_000 + i * 1_000, date=datetime(*oldin(0), 1 + i % BUGUN.day, 7, 0), notes="naqd"))
for i in range(12):
    s.add(EmployeeAdvance(employee_id=EU, amount=30_000 + i * 1_000, date=datetime(*oldin(1), 1 + i * 2, 7, 0), notes="naqd"))
s.add(EmployeeAdvance(employee_id=EU, amount=70_000, date=datetime(*oldin(3), 10, 7, 0), notes="naqd"))
s.add(EmployeeAdvance(employee_id=EU, amount=90_000, date=datetime(*oldin(6), 15, 7, 0), notes="naqd"))
s.commit()
s.close()
OTGAN_QOLGAN = 11_000_000 - sum(30_000 + i * 1_000 for i in range(12))
QOLGAN_3 = 11_000_000 - 70_000


def pul(n):
    return f"{abs(n):,}".replace(",", " ") + " so'm"


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
    JS_XATO = []
    SOROV = []

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def kontekst(w, h):
            tel = w < 700
            ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ", screen={"width": w, "height": h})
            ctx.set_default_timeout(15000)
            ctx.route(re.compile(r"^https://.*"), lambda r: r.fulfill(status=204, body=""))
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATO.append((w, str(e)[:300])))
            pg.on("request", lambda r: SOROV.append((w, r.url)) if "/api/hodim/oylik" in r.url else None)
            pg.goto(BU + "/hodim/login")
            pg.fill("input[name=phone]", "+998901119911")
            pg.fill("input[name=pin]", "4321")
            pg.click("button[type=submit]")
            pg.wait_for_load_state("networkidle")
            return ctx, pg

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def kut(pg, kod, ms=8000):
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

        # son ko'rinishi `toLocaleString('ru-RU')` — ming ajratgich bo'linmas bo'shliq (U+00A0 / U+202F): o'lchovda oddiy bo'shliqqa
        NB = "(t) => String(t == null ? '' : t).replace(/[\\u00a0\\u202f]/g, ' ')"

        def yopiqlar(pg):
            return ev(pg, """() => { const nb = """ + NB + """; return Array.from(document.querySelectorAll('#oylik-list details')).map(d => {
                const s = d.querySelector('summary'); const r = s.getBoundingClientRect();
                return {nomi: (s.querySelector('span') || {}).textContent, xulosa: nb((s.querySelector('.oy-xulosa') || {}).textContent),
                        ochiq: d.open, oy: d.dataset.oy || null, h: Math.round(r.height), ichi: nb(d.innerText)}; }); }""")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U1–U2. Sahifa suriladi, forma birinchi (375 / 390 / 1440 px)")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        for w, h in ((375, 812), (390, 844), (1440, 900)):
            ctx, pg = kontekst(w, h)
            kut(pg, "document.querySelectorAll('#oylik-list .oy-blok').length > 0")
            _b = ev(pg, """() => { const t = (s) => { const e = Array.from(document.querySelectorAll('.h-card-title')).find(x => x.textContent.includes(s));
                return e ? Math.round(e.getBoundingClientRect().top) : null; }; const b = document.getElementById('submit-btn').getBoundingClientRect();
                const e = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
                return {forma: t('Avans oldim deb yozish'), oylik: t('Oyligim'), sorov: t("Mening so'rovlarim"), vh: innerHeight,
                        tugma_ekranda: b.top >= 0 && b.bottom <= innerHeight, tugma_bosiladi: !!(e && e.closest('#submit-btn')),
                        doc: document.documentElement.scrollHeight, ov: getComputedStyle(document.body).overflowY}; }""")
            xav(pg.mouse.move, w / 2, h / 2)
            for _ in range(20):
                xav(pg.mouse.wheel, 0, 700)
                xav(pg.wait_for_timeout, 60)
            xav(pg.wait_for_timeout, 400)
            _k = ev(pg, """() => { const r = document.getElementById('req-list').getBoundingClientRect();
                return {y: Math.round(scrollY), pastki_korinadi: r.top < innerHeight && r.bottom > 0,
                        oxiri: Math.round(scrollY + innerHeight) >= document.documentElement.scrollHeight - 2}; }""")
            check(f"U1 {w} px: sahifa suriladi — g'ildirak bilan siljish > 0 va oxirigacha, «Mening so'rovlarim» ko'rinadi; `body` surishni "
                  "to'smaydi (ilgari `overflow: hidden`, siljish 0)",
                  isinstance(_b, dict) and isinstance(_k, dict) and _b.get("ov") != "hidden" and _k.get("y", 0) > 0 and _k.get("oxiri") is True
                  and _k.get("pastki_korinadi") is True and _b.get("doc", 0) > _b.get("vh", 0), (_b, _k))
            check(f"U2 {w} px: «💰 Avans oldim deb yozish» BIRINCHI (Oyligim va So'rovlardan oldin); sahifa ochilganda «Yuborish» ekranda va "
                  "bosiladi (ustida boshqa element yo'q)",
                  isinstance(_b, dict) and _b.get("forma") is not None and _b.get("oylik") is not None and _b.get("sorov") is not None
                  and _b["forma"] < _b["oylik"] < _b["sorov"] and _b.get("tugma_ekranda") is True and _b.get("tugma_bosiladi") is True, _b)
            if w != 375:
                ctx.close()
            else:
                C375, P375 = ctx, pg

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U3–U4. Oyligim — joriy oy ochiq, tugagan oylar yopiq (375 px)")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        pg = P375
        xav(pg.evaluate, "window.scrollTo(0, 0)")
        _j = ev(pg, """() => { const nb = """ + NB + """; const b = document.querySelector('#oylik-list > .oy-blok');
            return b ? {matn: nb(b.innerText), ichida: !!b.closest('details')} : null; }""")
        check("U3a joriy oy OCHIQ (shtorkasiz): «" + nomi(0) + " (joriy oy — hozirgacha)», Hisoblangan 11 000 000, to'lovlar ro'yxati",
              isinstance(_j, dict) and _j.get("ichida") is False and nomi(0) in _j.get("matn", "") and "(joriy oy — hozirgacha)" in _j["matn"]
              and "11 000 000 so'm" in _j["matn"] and "— 50 000 so'm" in _j["matn"], _j)
        _y = yopiqlar(pg)
        _kut_nomlar = [nomi(1), nomi(2), nomi(3), nomi(4), nomi(6)]
        check("U3b tugagan oylar — YOPIQ: o'tgan oy (sarlavhada «Qolgan " + pul(OTGAN_QOLGAN) + "»), keyin 3-…5-oy (ishga kirgan oy — 5-oy) va "
              "7-oy (ishga kirishdan oldingi to'lov) — «Ko'rish»; ishga kirmagan to'lovsiz 6-oy YO'Q; sarlavha balandligi ≥ 44 px",
              isinstance(_y, list) and [x.get("nomi") for x in _y] == _kut_nomlar and all(x.get("ochiq") is False for x in _y)
              and _y[0].get("xulosa") == "Qolgan " + pul(OTGAN_QOLGAN) and all(x.get("xulosa") == "Ko'rish" for x in _y[1:])
              and all(x.get("h", 0) >= 44 for x in _y), _y)
        _n0 = len([x for x in SOROV if x[0] == 375])
        xav(pg.click, "#oylik-list details:nth-of-type(1) > summary")
        xav(pg.wait_for_timeout, 300)
        _y = yopiqlar(pg)
        check("U3c o'tgan oy sarlavhasi bosilsa — ochiladi, 12 to'lov ko'rinadi, server so'rovi YO'Q (ma'lumot oldindan keladi)",
              isinstance(_y, list) and len(_y) >= 1 and _y[0].get("ochiq") is True and _y[0].get("ichi", "").count("so'm") >= 14
              and len([x for x in SOROV if x[0] == 375]) == _n0, (_y[:1], SOROV[_n0:]))
        _n0 = len([x for x in SOROV if x[0] == 375])
        xav(pg.click, "#oylik-list details[data-oy] >> nth=1 >> summary")
        kut(pg, "(() => { const d = document.querySelectorAll('#oylik-list details[data-oy]')[1]; return d && d.dataset.yuklandi === '1'; })()")
        _y = yopiqlar(pg)
        _yangi = [x[1] for x in SOROV if x[0] == 375][_n0:]
        _y3, _m3 = oldin(3)
        check("U3d eski oy (3-oy) ochilsa — BITTA so'rov `?oy=" + f"{_y3:04d}-{_m3:02d}" + "`, sarlavha «Qolgan " + pul(QOLGAN_3) + "», ichida «— 70 000 so'm»",
              isinstance(_y, list) and len(_y) == 5 and _y[2].get("ochiq") is True and _y[2].get("xulosa") == "Qolgan " + pul(QOLGAN_3)
              and "— 70 000 so'm" in _y[2].get("ichi", "") and len(_yangi) == 1 and _yangi[0].endswith(f"?oy={_y3:04d}-{_m3:02d}"),
              (_y[2:3] if isinstance(_y, list) else _y, _yangi))
        # SARLAVHA bosiladi (ochiq `<details>` markazi — ichidagi matn, u yopmaydi); orada pauza — tez bosilsa `toggle` birlashadi
        xav(pg.click, "#oylik-list details[data-oy] >> nth=1 >> summary")
        xav(pg.wait_for_timeout, 700)
        xav(pg.click, "#oylik-list details[data-oy] >> nth=1 >> summary")
        xav(pg.wait_for_timeout, 900)
        check("U3e o'sha oy yopib qayta ochilsa — qayta so'rov YO'Q (bir marta yuklanadi)",
              len([x for x in SOROV if x[0] == 375]) == _n0 + 1, [x[1] for x in SOROV if x[0] == 375][_n0:])
        xav(pg.click, "#oylik-list details[data-oy] >> nth=3 >> summary")
        kut(pg, "(() => { const d = document.querySelectorAll('#oylik-list details[data-oy]')[3]; return d && d.dataset.yuklandi === '1'; })()")
        _y = yopiqlar(pg)
        check("U3f ishga kirishdan oldingi to'lov oyi — «Ortiqcha olingan 90 000 so'm» (minussiz)",
              isinstance(_y, list) and len(_y) == 5 and _y[4].get("xulosa") == "Ortiqcha olingan 90 000 so'm"
              and "Ortiqcha olingan" in _y[4].get("ichi", ""), _y[4:] if isinstance(_y, list) else _y)
        _yol = re.compile(r".*/api/hodim/oylik\?oy=.*")
        xav(pg.route, _yol, lambda r: r.fulfill(status=500, content_type="application/json", body='{"detail":"x"}'))
        xav(pg.click, "#oylik-list details[data-oy] >> nth=2 >> summary")
        kut(pg, "(() => { const d = document.querySelectorAll('#oylik-list details[data-oy]')[2]; return d && d.innerText.includes('Yuklashda xato'); })()")
        _x = yopiqlar(pg)
        xav(pg.unroute, _yol)
        xav(pg.click, "#oylik-list details[data-oy] >> nth=2 >> .oy-qayta")
        kut(pg, "(() => { const d = document.querySelectorAll('#oylik-list details[data-oy]')[2]; return d && d.dataset.yuklandi === '1'; })()")
        _y = yopiqlar(pg)
        check("U4 server xatosi — «Yuklashda xato» + «🔄 Qayta yuklash» tugmasi; tugma bosilsa — qayta so'raladi va chiziladi («Qolgan 11 000 000 so'm»)",
              isinstance(_x, list) and len(_x) == 5 and "Yuklashda xato" in _x[3].get("ichi", "") and "Qayta yuklash" in _x[3].get("ichi", "")
              and isinstance(_y, list) and len(_y) == 5 and _y[3].get("xulosa") == "Qolgan 11 000 000 so'm", (_x[3:4] if isinstance(_x, list) else _x,
                                                                                                          _y[3:4] if isinstance(_y, list) else _y))

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U5. Telefonda avans yuborish")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        xav(pg.evaluate, "window.scrollTo(0, 0)")
        xav(pg.fill, "#f-amount", "125000")
        xav(pg.fill, "#f-notes", "U5 sinov")
        xav(pg.click, "#submit-btn")
        kut(pg, "(document.getElementById('h-msg') || {}).textContent && document.getElementById('h-msg').textContent.includes('Yuborildi')")
        kut(pg, "(document.getElementById('req-list') || {}).innerText && document.getElementById('req-list').innerText.includes('125 000')")
        _m = ev(pg, "() => { const nb = " + NB + "; return {msg: document.getElementById('h-msg').textContent, list: nb(document.getElementById('req-list').innerText)}; }")
        check("U5 375 px: forma to'ldirilib «Yuborish» — «✅ Yuborildi! Admin tasdiqlashini kuting.», «Mening so'rovlarim» da 125 000 — «⏳ Kutilmoqda»",
              isinstance(_m, dict) and "✅ Yuborildi" in _m.get("msg", "") and "125 000 so'm" in _m.get("list", "")
              and "Kutilmoqda" in _m.get("list", ""), _m)
        C375.close()
        br.close()

    section("U6. Sahifa xatosi")
    check("U6 JS sahifa xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])
    server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
