#!/usr/bin/env python3
"""
test_hodim_avans_tasdiq_ui.py — kech134 (zip 160): hodim avanslari — HAQIQIY brauzerda (Chromium, Playwright), HAQIQIY lokal server bilan
(uvicorn, test bazasi) O'LCHANADI: hodim paneli — telefon (375 / 390 px) va kompyuter (1440 px); admin — Bosh sahifa, Dashboard, KPI.

NIMA UCHUN KERAK — egasi QARORLARI 09.10 (tugmali): «Mening so'rovlarim» — joriy oy ochiq, o'tgan oylar yopiq, kutilayotgan doim
birinchi; avans manbasi — «C — hodim tasdig'i bilan»: «📱 O'zingiz» / «🧑‍💼 Admin» belgilari, admin yozgan avansga hodim «✅ Ha, oldim /
❌ Olmaganman», «Olmaganman» — adminga ogohlantirish (Bosh sahifa / KPI). O'LCHANGAN (zip 159): panelda to'lov manbasi yo'q, so'rovlar
oxirgi 20 ta, ogohlantirish oynalari faqat Dashboard da (admin kirgach Bosh sahifaga tushadi).

BO'LIMLAR
  U1 «🔔 Admin yozgan to'lovlar» kartasi (formadan keyin, «Oyligim» dan oldin): summa, sana, «🧑‍💼 Admin · ism», izoh, ikki tugma;
  U2 «Oyligim»: «📱 O'zingiz» belgisi, admin yozganida «⏳ Javobingiz kutilmoqda», o'tgan oy (yopiq) — eski admin to'lovi belgisi;
  U3 «✅ Ha, oldim» avval so'raydi («Keyin o'zgartirib bo'lmaydi»); «Bekor qilish» — tugmalar qaytadi, so'rov YUBORILMAYDI;
  U4 «✅ Ha, tasdiqlayman» — saqlandi (server), kartadan ketdi, xabar, «Oyligim» da «✅ Siz tasdiqlagansiz»;
  U5 tarmoq uzilsa — qatorda sabab, tugmalar yana bosiladi, serverda o'zgarish yo'q;
  U6 javob boshqa joydan berilgan (409) — kartada server sababi, ro'yxat yangilandi;
  U7 «❌ Olmaganman» — xabar (admin ogohlantirildi), «Oyligim» da «❌ Siz «Olmaganman» degansiz» + «✅ Endi oldim» → so'raydi → «oldim»;
  U8 «Mening so'rovlarim»: kutilayotgan birinchi (eski oy bo'lsa ham), joriy oy ochiq, o'tgan oy yopiq («N ta so'rov · X so'm
      tasdiqlangan»), ochilsa qatorlar, avansi o'chirilgan so'rov «🗑 O'chirilgan» (kim o'chirgani bilan);
  U9 telefon (375 / 390 px): gorizontal surilish yo'q, javob tugmalari va yopiq oy sarlavhasi ≥ 44 px; 1440 px — sig'adi;
  U10 admin Bosh sahifasi: «❗ Hodim avansni olmaganini aytdi» oynasi (telefon so'rovi yo'q), avans so'rovlari oynasi bu paytda yopiq;
      «✔ Ko'rib chiqdim» — qator ketdi, oyna yopildi, KEYIN avans so'rovlari oynasi; serverda — ko'rib chiqildi;
  U11 Dashboard: o'sha oyna; «🗑 Avansni o'chirish» — tasdiq oynasi → avans o'chdi;
  U12 KPI: hodim qatorida «❗ … «Olmaganman» dedi … · Ko'rish» → «💰 Avans berish» oynasida nizo bo'limi, tarixda belgilar; «✔ Ko'rib
      chiqdim» — bo'lim ketdi, qator ogohlantirishi yo'qoldi;
  U13 admin Bosh sahifasi telefonda (390 px) — oyna ekranga sig'adi, tugmalar ≥ 44 px;
  U14 JS sahifa xatosi yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 159) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_hodim_avans_tasdiq_ui.py
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
from datetime import datetime, timedelta, timezone

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

PG_BAZA = "hodim_avans_tasdiq_ui160_test"
_T = tempfile.mkdtemp(prefix="hodim_avans_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'hodim_avans_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import UserRole, Employee, EmployeeAdvance, AdvanceRequest, AdvanceRequestStatus   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

OY = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
BUGUN = tashkent_date()
main._send_telegram = lambda text, company_id=None: None


def oldin(n):
    k = BUGUN.year * 12 + (BUGUN.month - 1) - n
    return k // 12, k % 12 + 1


def nomi(n):
    y, m = oldin(n)
    return f"{OY[m]} {y}"


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def javob_ol(aid):
    return db_ishi(lambda s: getattr(s.query(EmployeeAdvance).filter(EmployeeAdvance.id == aid).first(), "hodim_javobi", "YO'Q"))


def javob_qoy(aid, javob):
    """Javobni bazada to'g'ridan-to'g'ri qo'yadi (boshqa joydan berilgan javob). Asl kodda ustun yo'q — o'tkaziladi (sinov QULAMASIN)."""
    if not hasattr(EmployeeAdvance, "hodim_javobi"):
        return
    db_ishi(lambda s: s.query(EmployeeAdvance).filter(EmployeeAdvance.id == aid).update(
        {"hodim_javobi": javob, "hodim_javob_vaqti": datetime.now(timezone.utc).replace(tzinfo=None) if javob in ("oldim", "olmadim") else None}))


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ══════════════════════════════════════════════════════════════
# Fikstura: admin; hodim U (panel — telefon + o'z PIN i, sinovda brauzerdan); avanslar: admin AV1 205 000 «Uzumga toladim», AV2 50 000,
# AV3 30 000 (joriy oy); hodim so'rovi tasdiqlangan (120 000); o'tgan oyda eski admin to'lovi (savolsiz); so'rovlar: kutilayotgan
# (3 oy oldingi sana), joriy oyda tasdiqlangan, o'tgan oyda tasdiqlangan + rad etilgan, avansi o'chirilgan
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "hau_admin", "Parol123!", UserRole.ADMIN, "HAU admin", company_id=1)
s.commit()
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "hau_admin", "password": "Parol123!"}, follow_redirects=False)
EU = js(A.post("/api/employees", json={"name": "Ulug'bek", "position": "Kesuvchi", "pay_type": "fixed", "fixed_amount": 9_000_000})).get("id")
A.post(f"/api/employees/{EU}/set-login", data={"phone": "+998901131313", "pin": "4321"})
db_ishi(lambda s: s.query(Employee).filter(Employee.id == EU).update({"hire_date": datetime(2024, 1, 1)}))
_kun = BUGUN.isoformat()


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
    JAVOB_SOROV = []
    TELEFON = {"pin": "4321", "cookie": None}

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def yangi_kontekst(w, h):
            tel = w < 700
            ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ", screen={"width": w, "height": h})
            ctx.set_default_timeout(15000)
            ctx.route(re.compile(r"^https://.*"), lambda r: r.fulfill(status=204, body=""))
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATO.append((w, pg.url, str(e)[:300])))
            pg.on("request", lambda r: JAVOB_SOROV.append(r.url) if "/javob" in r.url else None)
            return ctx, pg

        def hodim_kontekst(w, h):
            """Bitta telefon (brauzer kaliti) — birinchi kontekstda admin ruxsat beradi, hodim o'z PIN ini qo'yadi; keyingilariga kalit."""
            ctx, pg = yangi_kontekst(w, h)
            if TELEFON.get("cookie"):
                ctx.add_cookies([TELEFON["cookie"]])
            pg.goto(BU + "/hodim/login")
            pg.fill("input[name=phone]", "+998901131313")
            pg.fill("input[name=pin]", TELEFON["pin"])
            pg.click("button[type=submit]")
            pg.wait_for_load_state("networkidle")
            if not TELEFON.get("cookie"):
                _q = A.get("/api/admin/qurilma-sorovlari")
                _q = _q.json() if _q.status_code == 200 else []
                _k = next((x.get("kalit") for x in _q if x.get("employee_id") == EU), None)
                if _k:
                    A.post(f"/api/employees/{EU}/qurilma/ruxsat", json={"kalit": _k})
                    pg.goto(BU + "/hodim")
                    pg.wait_for_load_state("networkidle")
                    if pg.query_selector("#pinYangi"):
                        pg.fill("#pinYangi", "4826")
                        pg.fill("#pinTakror", "4826")
                        pg.click("#pinSaqla")
                        pg.wait_for_selector("#submit-btn")
                        pg.wait_for_load_state("networkidle")
                        TELEFON["pin"] = "4826"
                    TELEFON["cookie"] = next((c for c in ctx.cookies() if c.get("name") == "emp_qurilma"), None)
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

        NB = "(t) => String(t == null ? '' : t).replace(/[\\u00a0\\u202f]/g, ' ')"

        def matn(pg, sel):
            return ev(pg, "(s) => { const nb = " + NB + "; const e = document.querySelector(s); return e ? nb(e.innerText) : null; }", sel)

        HC, HP = hodim_kontekst(390, 844)
        # ── ma'lumot (telefon bog'langach — hodim panelga kira oladi, admin avanslariga savol chiqadi) ──
        AV1 = js(A.post(f"/api/employees/{EU}/advance?amount=205000&notes=Uzumga%20toladim&adv_date={_kun}")).get("id")
        AV2 = js(A.post(f"/api/employees/{EU}/advance?amount=50000&adv_date={_kun}")).get("id")
        AV3 = js(A.post(f"/api/employees/{EU}/advance?amount=30000&notes=karta&adv_date={_kun}")).get("id")

        def sorov(summa, dt, holat, notes=None, sub=None):
            def f(s):
                r = AdvanceRequest(employee_id=EU, amount=summa, requested_date=dt, notes=notes, status=holat,
                                   submitted_at=sub or dt + timedelta(hours=2))
                s.add(r)
                s.flush()
                return r.id
            return db_ishi(f)
        _yo, _mo = oldin(1)
        RQ_T = js(A.post("/api/admin/advance-requests/{}/confirm".format(
            sorov(120_000, datetime(BUGUN.year, BUGUN.month, 1, 2, 0), AdvanceRequestStatus.PENDING, "ustadan")))).get("advance_id")
        R_KUT = sorov(64_000, datetime(*oldin(3), 12, 0, 0), AdvanceRequestStatus.PENDING, "eski kutilayotgan")
        R_O1 = sorov(40_000, datetime(_yo, _mo, 5, 0, 0), AdvanceRequestStatus.CONFIRMED, "o'tgan oy")
        R_O2 = sorov(25_000, datetime(_yo, _mo, 9, 0, 0), AdvanceRequestStatus.REJECTED, "rad")
        _rq_ochir = sorov(15_000, datetime(BUGUN.year, BUGUN.month, 1, 3, 0), AdvanceRequestStatus.PENDING, "o'chadi")
        AV_OCH = js(A.post(f"/api/admin/advance-requests/{_rq_ochir}/confirm")).get("advance_id")
        A.delete(f"/api/employees/advance/{AV_OCH}")
        db_ishi(lambda s: s.add(EmployeeAdvance(employee_id=EU, amount=70_000, date=datetime(_yo, _mo, 14, 7, 0), notes="eski naqd",
                                                given_by="Eski admin", avans_manba="admin") if hasattr(EmployeeAdvance, "avans_manba")
                                else EmployeeAdvance(employee_id=EU, amount=70_000, date=datetime(_yo, _mo, 14, 7, 0),
                                                     notes="eski naqd", given_by="Eski admin")))
        xav(HP.goto, BU + "/hodim")
        kut(HP, "document.querySelectorAll('#oylik-list .oy-blok').length > 0 && !!document.querySelector('#req-list .req-row')")
        kut(HP, "(() => { const k = document.getElementById('javob-karta'); return k && k.style.display !== 'none'; })()", 5000)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U1–U2. «🔔» kartasi va «Oyligim» belgilari (390 px)")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _u1 = ev(HP, """() => { const nb = """ + NB + """; const k = document.getElementById('javob-karta');
            const y = (s) => { const e = Array.from(document.querySelectorAll('.h-card-title')).find(x => x.textContent.includes(s));
                               return e ? Math.round(e.getBoundingClientRect().top + scrollY) : null; };
            return {kor: !!k && k.style.display !== 'none', qator: Array.from(document.querySelectorAll('#javob-list .javob-qator')).map(q => ({
                      id: q.dataset.id, t: nb(q.innerText),
                      tug: Array.from(q.querySelectorAll('button')).map(b => b.textContent.trim())})),
                    forma: y('Avans oldim deb yozish'), karta: y("Admin yozgan to'lovlar"), oylik: y('Oyligim')}; }""")
        _q1 = next((q for q in (_u1.get("qator") or []) if str(q.get("id")) == str(AV1)), {}) if isinstance(_u1, dict) else {}
        check("U1 «🔔 Admin yozgan to'lovlar» kartasi formadan KEYIN, «Oyligim» dan OLDIN; 3 ta to'lov; har birida summa, «🧑‍💼 Admin · "
              "ism», izoh, «✅ Ha, oldim» va «❌ Olmaganman»",
              isinstance(_u1, dict) and _u1.get("kor") is True and len(_u1.get("qator") or []) == 3
              and (_u1.get("forma") or 0) < (_u1.get("karta") or 0) < (_u1.get("oylik") or 0)
              and "205 000 so'm" in _q1.get("t", "") and "🧑‍💼 Admin · HAU admin" in _q1.get("t", "")
              and "💬 Uzumga toladim" in _q1.get("t", "") and _q1.get("tug") == ["✅ Ha, oldim", "❌ Olmaganman"], _u1)
        _u2 = ev(HP, """() => { const nb = """ + NB + """; const j = document.querySelector('#oylik-list > .oy-blok');
            return {joriy: j ? Array.from(j.querySelectorAll('.tolov-qator')).map(q => nb(q.innerText)) : null}; }""")
        _jr = (_u2 or {}).get("joriy") or [] if isinstance(_u2, dict) else []
        check("U2a «Oyligim» joriy oy: hodim so'ragan to'lov — «📱 O'zingiz» (izoh tizim qo'shimchasisiz), admin yozgani — «🧑‍💼 Admin · "
              "ism» va «⏳ Javobingiz kutilmoqda»; o'chirilgan avans yo'q",
              any("120 000 so'm" in t and "📱 O'zingiz" in t and "ustadan" in t and "xodim o'zi yozgan" not in t for t in _jr)
              and any("205 000 so'm" in t and "🧑‍💼 Admin · HAU admin" in t and "⏳ Javobingiz kutilmoqda" in t for t in _jr)
              and not any("15 000 so'm" in t for t in _jr), _jr)
        xav(HP.click, f"#oylik-list details:has(summary:has-text('{nomi(1)}')) > summary")
        kut(HP, "Array.from(document.querySelectorAll('#oylik-list details')).some(d => d.open)", 4000)
        _u2b = ev(HP, """() => { const nb = """ + NB + """; const d = Array.from(document.querySelectorAll('#oylik-list details')).find(x => x.open);
            return d ? Array.from(d.querySelectorAll('.tolov-qator')).map(q => nb(q.innerText)) : null; }""")
        check("U2b o'tgan oy (yopiq) ochilsa: eski admin to'lovi — «🧑‍💼 Admin · Eski admin», javob so'ralmaydi (holat qatori yo'q)",
              isinstance(_u2b, list) and any("70 000 so'm" in t and "🧑‍💼 Admin · Eski admin" in t and "Javobingiz" not in t
                                             and "tasdiqlagansiz" not in t for t in _u2b), _u2b)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U3–U4. «✅ Ha, oldim» — avval so'raladi; tasdiqlansa saqlanadi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _q = f"#javob-list .javob-qator[data-id='{AV1}']"
        n0 = len(JAVOB_SOROV)
        xav(HP.click, f"{_q} button:has-text('Ha, oldim')")
        _u3a = ev(HP, "(s) => { const nb = " + NB + "; const q = document.querySelector(s); return q ? {t: nb(q.innerText), "
                      "tug: Array.from(q.querySelectorAll('button')).map(b => b.textContent.trim())} : null; }", _q)
        xav(HP.click, f"{_q} button:has-text('Bekor qilish')")
        _u3b = ev(HP, "(s) => { const q = document.querySelector(s); return q ? Array.from(q.querySelectorAll('button')).map(b => b.textContent.trim()) : null; }", _q)
        check("U3 «Ha, oldim» — so'raydi («205 000 so'mni olganingizni tasdiqlaysizmi? Keyin o'zgartirib bo'lmaydi.»); «Bekor qilish» — "
              "tugmalar qaytdi, so'rov YUBORILMADI, serverda «kutilmoqda»",
              isinstance(_u3a, dict) and "205 000 so'mni olganingizni tasdiqlaysizmi? Keyin o'zgartirib bo'lmaydi." in _u3a.get("t", "")
              and _u3a.get("tug") == ["✅ Ha, tasdiqlayman", "Bekor qilish"] and _u3b == ["✅ Ha, oldim", "❌ Olmaganman"]
              and len(JAVOB_SOROV) == n0 and javob_ol(AV1) == "kutilmoqda", (_u3a, _u3b, JAVOB_SOROV[n0:]))
        xav(HP.click, f"{_q} button:has-text('Ha, oldim')")
        xav(HP.click, f"{_q} button:has-text('Ha, tasdiqlayman')")
        kut(HP, f"!document.querySelector(\"{_q}\")", 6000)
        _u4 = ev(HP, """(id) => { const nb = """ + NB + """; const j = document.querySelector('#oylik-list > .oy-blok');
            const r = j ? Array.from(j.querySelectorAll('.tolov-qator')).map(q => nb(q.innerText)) : [];
            return {msg: document.getElementById('javob-msg').textContent, n: document.querySelectorAll('#javob-list .javob-qator').length,
                    qator: r.find(t => t.includes('205 000')) || null}; }""", AV1)
        check("U4 «✅ Ha, tasdiqlayman» — serverda «oldim»; kartadan ketdi (2 ta qoldi), xabar «✅ Rahmat…», «Oyligim» da «✅ Siz "
              "tasdiqlagansiz»",
              javob_ol(AV1) == "oldim" and isinstance(_u4, dict) and _u4.get("n") == 2 and "Rahmat" in str(_u4.get("msg"))
              and "✅ Siz tasdiqlagansiz" in str(_u4.get("qator")), (javob_ol(AV1), _u4))

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U5–U6. Tarmoq uzilsa; javob boshqa joydan berilgan bo'lsa (409)")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _q2 = f"#javob-list .javob-qator[data-id='{AV2}']"
        xav(HC.route, re.compile(r".*/api/hodim/avans/\d+/javob$"), lambda r: r.abort())
        xav(HP.click, f"{_q2} button:has-text('Olmaganman')")
        kut(HP, f"((document.querySelector(\"{_q2} .javob-xabar\") || {{}}).textContent || '').includes('aloqa')", 6000)
        _u5 = ev(HP, "(s) => { const q = document.querySelector(s); return q ? {x: q.querySelector('.javob-xabar').textContent, "
                     "d: Array.from(q.querySelectorAll('button')).map(b => b.disabled)} : null; }", _q2)
        xav(HC.unroute, re.compile(r".*/api/hodim/avans/\d+/javob$"))
        check("U5 tarmoq uzildi — qatorda «Server bilan aloqa yo'q…», tugmalar yana bosiladi, serverda «kutilmoqda»",
              isinstance(_u5, dict) and "Server bilan aloqa yo'q" in _u5.get("x", "") and _u5.get("d") == [False, False]
              and javob_ol(AV2) == "kutilmoqda", _u5)
        javob_qoy(AV2, "oldim")             # boshqa joydan (masalan ikkinchi oynada) javob berilgan
        xav(HP.click, f"{_q2} button:has-text('Olmaganman')")
        kut(HP, f"!document.querySelector(\"{_q2}\")", 6000)
        _u6 = ev(HP, "() => ({msg: document.getElementById('javob-msg').textContent, n: document.querySelectorAll('#javob-list .javob-qator').length})")
        check("U6 javob boshqa joydan berilgan (409) — kartada server sababi («allaqachon «Ha, oldim»…»), ro'yxat yangilandi (1 ta qoldi)",
              isinstance(_u6, dict) and "allaqachon «Ha, oldim»" in _u6.get("msg", "") and _u6.get("n") == 1
              and javob_ol(AV2) == "oldim", _u6)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U7. «❌ Olmaganman» va keyin «✅ Endi oldim»")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _q3 = f"#javob-list .javob-qator[data-id='{AV3}']"
        xav(HP.click, f"{_q3} button:has-text('Olmaganman')")
        kut(HP, "(document.getElementById('javob-msg').textContent || '').includes('admin ogohlantirildi')", 6000)
        _u7a = ev(HP, """() => { const nb = """ + NB + """; const j = document.querySelector('#oylik-list > .oy-blok');
            const r = j ? Array.from(j.querySelectorAll('.tolov-qator')).map(q => nb(q.innerText)) : [];
            return {msg: document.getElementById('javob-msg').textContent, bosh: nb(document.getElementById('javob-list').innerText),
                    kor: document.getElementById('javob-karta').style.display !== 'none', qator: r.find(t => t.includes('30 000')) || null}; }""")
        check("U7a «Olmaganman» — serverda «olmadim»; xabar («admin ogohlantirildi…»), karta «Hamma to'lovlarga javob berdingiz»; "
              "«Oyligim» da «❌ Siz «Olmaganman» degansiz» va «✅ Endi oldim»",
              javob_ol(AV3) == "olmadim" and isinstance(_u7a, dict) and "admin ogohlantirildi" in _u7a.get("msg", "")
              and _u7a.get("kor") is True and "Hamma to'lovlarga javob berdingiz" in _u7a.get("bosh", "")
              and "❌ Siz «Olmaganman» degansiz" in str(_u7a.get("qator")) and "✅ Endi oldim" in str(_u7a.get("qator")), _u7a)
        _qo = f"#oylik-list > .oy-blok .javob-blok[data-id='{AV3}']"
        xav(HP.click, f"{_qo} button:has-text('Endi oldim')")
        _u7b = ev(HP, "(s) => { const nb = " + NB + "; const b = document.querySelector(s); return b ? nb(b.innerText) : null; }", _qo)
        xav(HP.click, f"{_qo} button:has-text('Ha, tasdiqlayman')")
        kut(HP, f"!document.querySelector(\"{_qo}\")", 6000)
        check("U7b «✅ Endi oldim» — avval so'raydi («30 000 so'mni olganingizni tasdiqlaysizmi?»), tasdiqlansa serverda «oldim»",
              "30 000 so'mni olganingizni tasdiqlaysizmi?" in str(_u7b) and javob_ol(AV3) == "oldim", (_u7b, javob_ol(AV3)))

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U8. «Mening so'rovlarim» — kutilayotgan birinchi, joriy oy ochiq, o'tgan oylar yopiq")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _u8 = ev(HP, """() => { const nb = """ + NB + """; const l = document.getElementById('req-list');
            return Array.from(l.children).map(c => ({tag: c.tagName, cls: c.className, open: c.open === undefined ? null : c.open,
                nomi: nb((c.querySelector('.sorov-guruh-nomi, summary > span') || {}).textContent),
                xulosa: nb((c.querySelector('summary .oy-xulosa') || {}).textContent), t: nb(c.innerText)})); }""")
        _g = _u8 if isinstance(_u8, list) else []
        check("U8a birinchi — «⏳ Admin tasdiqlashi kutilmoqda» (3 oy oldingi sana bilan kutilayotgan so'rov ham); keyin joriy oy «(joriy "
              "oy)» ochiq; o'tgan oy — yopiq `<details>`, sarlavhada «2 ta so'rov · 40 000 so'm tasdiqlangan»",
              len(_g) >= 3 and "Admin tasdiqlashi kutilmoqda" in _g[0].get("nomi", "") and "64 000 so'm" in _g[0].get("t", "")
              and _g[1].get("tag") == "DIV" and nomi(0) in _g[1].get("nomi", "") and "(joriy oy)" in _g[1].get("nomi", "")
              and _g[2].get("tag") == "DETAILS" and _g[2].get("open") is False and nomi(1) in _g[2].get("nomi", "")
              and _g[2].get("xulosa") == "2 ta so'rov · 40 000 so'm tasdiqlangan", _g)
        check("U8b joriy oyda avansi o'chirilgan so'rov — «🗑 O'chirilgan», «Tasdiqlangan edi, keyin admin o'chirgan (HAU admin) · sana — "
              "oyligingizda hisoblanmaydi»",
              len(_g) >= 2 and "🗑 O'chirilgan" in _g[1].get("t", "") and "keyin admin o'chirgan (HAU admin)" in _g[1].get("t", "")
              and "oyligingizda hisoblanmaydi" in _g[1].get("t", ""), _g[1:2])
        xav(HP.click, "#req-list details.sorov-oy > summary")
        _u8c = ev(HP, "() => { const nb = " + NB + "; const d = document.querySelector('#req-list details.sorov-oy'); "
                      "return d ? {open: d.open, t: nb(d.innerText)} : null; }")
        check("U8c o'tgan oy ochildi — tasdiqlangan (40 000, «✅ Tasdiqlandi») va rad etilgan (25 000, «❌ Rad etildi») so'rovlar",
              isinstance(_u8c, dict) and _u8c.get("open") is True and "40 000 so'm" in _u8c.get("t", "")
              and "✅ Tasdiqlandi" in _u8c.get("t", "") and "25 000 so'm" in _u8c.get("t", "") and "❌ Rad etildi" in _u8c.get("t", ""),
              _u8c)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U9. Telefon va kompyuter — sig'ish, tugma o'lchami")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        AV4 = js(A.post(f"/api/employees/{EU}/advance?amount=11000&adv_date={_kun}")).get("id")
        for w, h in ((375, 812), (390, 844), (1440, 900)):
            c2, p2 = hodim_kontekst(w, h)
            kut(p2, "!!document.querySelector('#javob-list .javob-qator') && !!document.querySelector('#req-list details')")
            _o = ev(p2, """() => { const r = (e) => Math.round(e.getBoundingClientRect().height);
                return {sw: document.documentElement.scrollWidth, iw: innerWidth,
                        tug: Array.from(document.querySelectorAll('#javob-list button')).map(r),
                        sum: Array.from(document.querySelectorAll('#req-list details > summary, #oylik-list details > summary')).map(r),
                        tolov_ichida: Array.from(document.querySelectorAll('.tolov-qator, .javob-qator')).every(q => q.scrollWidth <= q.clientWidth + 1)}; }""")
            _min = 44 if w < 700 else 40          # loyiha shkalasi: telefonda tugma ≥ 44 px, kompyuterda `--h-btn` 40 px
            check(f"U9 {w} px: gorizontal surilish yo'q; javob tugmalari ≥ {_min} px, yopiq oy sarlavhalari ≥ 44 px; to'lov qatorlari sig'adi",
                  isinstance(_o, dict) and _o.get("sw", 9e9) <= _o.get("iw", 0) and _o.get("tug") and min(_o["tug"]) >= _min
                  and _o.get("sum") and min(_o["sum"]) >= 44 and _o.get("tolov_ichida") is True, _o)
            xav(c2.close)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U10–U11. Admin — Bosh sahifa va Dashboard oynasi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        javob_qoy(AV4, "olmadim")
        AC, AP = yangi_kontekst(1440, 900)
        xav(AP.goto, BU + "/login")
        xav(AP.fill, "input[name=username]", "hau_admin")
        xav(AP.fill, "input[name=password]", "Parol123!")
        xav(AP.click, "button[type=submit]")
        xav(AP.wait_for_load_state, "networkidle")
        _url = AP.url
        kut(AP, "(() => { const m = document.getElementById('avansNizoModal'); return m && m.style.display === 'flex'; })()")
        _u10 = ev(AP, """() => { const nb = """ + NB + """; const d = (i) => (document.getElementById(i) || {style: {}}).style.display;
            return {n: d('avansNizoModal'), q: d('qurilmaModal'), a: d('advReqModal'), t: nb((document.getElementById('avansNizoList') || {}).innerText),
                    path: location.pathname}; }""")
        check("U10a admin kirgach Bosh sahifa (/): «❗ Hodim avansni olmaganini aytdi» oynasi — ism, 11 000 so'm, yozgan, «Olmaganman» "
              "vaqti; telefon va avans so'rovlari oynalari bu paytda yopiq",
              isinstance(_u10, dict) and _u10.get("path") == "/" and _u10.get("n") == "flex" and _u10.get("q") in ("none", "")
              and _u10.get("a") in ("none", "") and "Ulug'bek" in _u10.get("t", "") and "11 000 so'm" in _u10.get("t", "")
              and "yozgan: HAU admin" in _u10.get("t", "") and "«Olmaganman» dedi" in _u10.get("t", ""), (_url, _u10))
        xav(AP.click, "#avansNizoList button:has-text(\"Ko'rib chiqdim\")")
        kut(AP, "(() => { const a = document.getElementById('advReqModal'); return a && a.style.display === 'flex'; })()")
        _u10b = ev(AP, """() => { const nb = """ + NB + """; return {n: document.getElementById('avansNizoModal').style.display,
            a: document.getElementById('advReqModal').style.display, t: nb(document.getElementById('advReqList').innerText)}; }""")
        _nz = js(A.get("/api/admin/avans-nizolar"))
        check("U10b «✔ Ko'rib chiqdim» — oyna yopildi, KEYIN avans so'rovlari oynasi (64 000 — kutilayotgan); serverda ro'yxat bo'sh",
              isinstance(_u10b, dict) and _u10b.get("n") == "none" and _u10b.get("a") == "flex" and "64 000 so'm" in _u10b.get("t", "")
              and _nz == [], (_u10b, _nz))
        xav(AP.click, "#advReqModal button[data-yopish]")
        AV5 = js(A.post(f"/api/employees/{EU}/advance?amount=22000&notes=xato%20yozildi&adv_date={_kun}")).get("id")
        javob_qoy(AV5, "olmadim")
        xav(AP.goto, BU + "/dashboard")
        kut(AP, "(() => { const m = document.getElementById('avansNizoModal'); return m && m.style.display === 'flex'; })()")
        _u11a = ev(AP, "() => (document.getElementById('avansNizoList') || {}).innerText || ''")
        xav(AP.click, "#avansNizoList button:has-text(\"Avansni o'chirish\")")
        kut(AP, "(() => { const m = document.getElementById('ccModal'); return m && m.style.display === 'flex'; })()", 4000)
        xav(AP.click, "#ccModalOk")
        kut(AP, "(() => { const m = document.getElementById('avansNizoModal'); return m && m.style.display === 'none'; })()", 6000)
        _bor5 = db_ishi(lambda s: s.query(EmployeeAdvance).filter(EmployeeAdvance.id == AV5).count())
        check("U11 Dashboard: o'sha oyna (22 000, «xato yozildi»); «🗑 Avansni o'chirish» — tasdiq oynasi → avans o'chdi, oyna yopildi",
              "22 000" in str(_u11a).replace(" ", " ").replace(" ", " ") and "xato yozildi" in str(_u11a) and _bor5 == 0,
              (_u11a, _bor5))
        xav(AP.click, "#advReqModal button[data-yopish]")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U12. KPI — qator ogohlantirishi, avans oynasidagi nizo bo'limi va belgilar")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        AV6 = js(A.post(f"/api/employees/{EU}/advance?amount=33000&adv_date={_kun}")).get("id")
        javob_qoy(AV6, "olmadim")
        xav(AP.goto, BU + "/kpi")
        xav(AP.evaluate, "() => { const t = Array.from(document.querySelectorAll('button, .tab')).find(b => /Hodimlar/.test(b.textContent)); if (t) t.click(); }")
        kut(AP, "!!document.querySelector('.emp-nizo')", 8000)
        _u12a = ev(AP, "() => { const b = document.querySelector('.emp-nizo'); return b ? {t: b.textContent.replace(/[\\u00a0\\u202f]/g, ' '), "
                       "h: Math.round(b.getBoundingClientRect().height)} : null; }")
        xav(AP.click, ".emp-nizo")
        kut(AP, "!!document.querySelector('#adv-nizo .adv-nizo-qator') && !!document.querySelector('#adv-history .adv-manba')", 8000)
        _u12b = ev(AP, """() => { const nb = """ + NB + """; return {nizo: nb((document.getElementById('adv-nizo') || {}).innerText),
            tarix: nb((document.getElementById('adv-history') || {}).innerText), modal: document.getElementById('advanceModal').style.display}; }""")
        check("U12a qatorda «❗ 1 ta avansga «Olmaganman» dedi — 33 000 so'm · Ko'rish» (≥ 32 px); bosilsa «💰 Avans berish» oynasi: "
              "nizo bo'limi (33 000) va tarixda belgilar («🧑‍💼 Admin · HAU admin», «📱 Hodim o'zi yozgan», «✅ hodim «Ha, oldim» degan»)",
              isinstance(_u12a, dict) and "1 ta avansga «Olmaganman» dedi — 33 000 so'm" in _u12a.get("t", "") and _u12a.get("h", 0) >= 32
              and isinstance(_u12b, dict) and _u12b.get("modal") == "flex" and "33 000 so'm" in _u12b.get("nizo", "")
              and "🧑‍💼 Admin · HAU admin" in _u12b.get("tarix", "") and "📱 Hodim o'zi yozgan" in _u12b.get("tarix", "")
              and "✅ hodim «Ha, oldim» degan" in _u12b.get("tarix", ""), (_u12a, _u12b))
        xav(AP.click, "#adv-nizo button:has-text(\"Ko'rib chiqdim\")")
        kut(AP, "!document.querySelector('#adv-nizo .adv-nizo-qator') && !document.querySelector('.emp-nizo')", 8000)
        _u12c = ev(AP, "() => ({nizo: (document.getElementById('adv-nizo') || {}).innerText || '', qator: !!document.querySelector('.emp-nizo'), "
                       "tarix: (document.getElementById('adv-history') || {}).innerText || ''})")
        check("U12b «✔ Ko'rib chiqdim» — bo'lim ketdi, qator ogohlantirishi yo'qoldi, tarixda «(ko'rib chiqilgan: HAU admin)»",
              isinstance(_u12c, dict) and _u12c.get("nizo", "").strip() == "" and _u12c.get("qator") is False
              and "ko'rib chiqilgan: HAU admin" in _u12c.get("tarix", ""), _u12c)
        xav(AP.click, "#advanceModal button[data-yopish]")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U13. Admin Bosh sahifasi telefonda")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        AV7 = js(A.post(f"/api/employees/{EU}/advance?amount=44000&notes=juda%20uzun%20izoh%20{'x' * 60}&adv_date={_kun}")).get("id")
        javob_qoy(AV7, "olmadim")
        MC, MP = yangi_kontekst(390, 844)
        xav(MP.goto, BU + "/login")
        xav(MP.fill, "input[name=username]", "hau_admin")
        xav(MP.fill, "input[name=password]", "Parol123!")
        xav(MP.click, "button[type=submit]")
        xav(MP.wait_for_load_state, "networkidle")
        kut(MP, "(() => { const m = document.getElementById('avansNizoModal'); return m && m.style.display === 'flex'; })()")
        _u13 = ev(MP, """() => { const m = document.querySelector('#avansNizoModal > div'); const r = m ? m.getBoundingClientRect() : null;
            return {sig: !!r && r.left >= 0 && r.right <= innerWidth + 0.5, sw: document.documentElement.scrollWidth, iw: innerWidth,
                    tug: Array.from(document.querySelectorAll('#avansNizoModal button')).map(b => Math.round(b.getBoundingClientRect().height)),
                    qator: Array.from(document.querySelectorAll('#avansNizoList .nizo-qator')).every(q => q.scrollWidth <= q.clientWidth + 1)}; }""")
        check("U13 390 px: «Olmaganman» oynasi ekranga sig'adi (uzun izoh bilan ham), tugmalar ≥ 44 px",
              isinstance(_u13, dict) and _u13.get("sig") is True and _u13.get("qator") is True and _u13.get("tug")
              and min(_u13["tug"]) >= 44, _u13)

        section("U14. JS sahifa xatosi")
        check("U14 JS sahifa xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])
        br.close()
    server.should_exit = True

print("\n" + "=" * 70)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
