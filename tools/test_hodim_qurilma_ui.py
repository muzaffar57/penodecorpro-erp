#!/usr/bin/env python3
"""
test_hodim_qurilma_ui.py — kech133 (zip 159): hodim telefoniga admin ruxsati va hodimning o'z PIN i — HAQIQIY brauzerda (Chromium,
Playwright), HAQIQIY lokal server bilan (uvicorn, test bazasi) O'LCHANADI: hodim — telefon (375 px), admin — kompyuter (1440 px).

NIMA UCHUN KERAK — egasi 09.10 14:50: «hodim tel no'meri va pin kodini tersa hamma odam kirsa bo'lar ekan — faqat o'zini telefonidan
kira oladigon qilsak». EGASI QARORLARI (tugmali): har yangi telefonga admin ruxsati (birinchisiga ham); PIN ni hodimning o'zi qo'yadi.

BO'LIMLAR
  U1 hodim telefondan kiradi (raqam bo'sh joyli — admin bo'sh joysiz saqlagan) → «Bu telefon hali tasdiqlanmagan», ekranga sig'adi;
  U2 admin Bosh sahifasi: «🔔 Hodim yangi telefondan kirmoqchi» oynasi (ism, telefon), avans so'rovlari oynasi bu paytda YO'Q;
  U3 «✅ Ruxsat berish» → qator yo'qoladi, oyna yopiladi, keyin avans so'rovlari oynasi chiqadi;
  U4 hodim sahifasi o'zi (so'rab turadi) PIN sahifasiga o'tadi: oson PIN — server sababi, mos emas — mijoz sababi, to'g'ri — panel
      («🔒 PIN» havolasi, sarlavha ekranga sig'adi);
  U5 «🔒 PIN» — hozirgi PIN noto'g'ri — sabab; to'g'ri — panelga qaytadi;
  U6 ikkinchi telefon (iPhone) — kutadi; admin KPI: qatorda «🔔 Yangi telefon ruxsat kutmoqda», «🔑 Kirish» oynasida telefon raqami
      (ilgari bo'sh), bog'langan va kutayotgan telefon; «❌ Rad etish» → hodim sahifasida «Bu telefonga ruxsat berilmadi»;
  U7 «Telefonni uzish» (tasdiq bilan) → «Telefon hali bog'lanmagan»; hodim sahifasi yangilansa — kirish sahifasi;
  U8 yangi so'rov — Bosh sahifadagi oyna Esc bilan yopiladi, keyin avans oynasi;
  U9 JS sahifa xatosi yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 158) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_hodim_qurilma_ui.py
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

PG_BAZA = "hodim_qurilma_ui159_test"
_T = tempfile.mkdtemp(prefix="hodim_qurilma_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'hodim_qurilma_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, AdvanceRequest        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

ANDROID = "Mozilla/5.0 (Linux; Android 13; SM-A525F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
          "Mobile/15E148 Safari/604.1")

# Fikstura: admin; hodim U (telefon «+998907776655», vaqtinchalik PIN 4321); boshqa hodim W ning kutilayotgan avans so'rovi
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "hqu_admin", "Parol123!", UserRole.ADMIN, "HQU admin", company_id=1)
s.commit()
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "hqu_admin", "password": "Parol123!"}, follow_redirects=False)
EU = A.post("/api/employees", json={"name": "Ulug'bek", "position": "Kesuvchi", "pay_type": "fixed",
                                    "fixed_amount": 11_000_000}).json().get("id")
A.post(f"/api/employees/{EU}/set-login", data={"phone": "+998907776655", "pin": "4321"})
EW = A.post("/api/employees", json={"name": "Jurabek", "position": "Qoplamachi", "pay_type": "fixed",
                                    "fixed_amount": 2_000_000}).json().get("id")
s = SessionLocal()
s.add(AdvanceRequest(employee_id=EW, amount=150_000, requested_date=datetime(2026, 10, 2, 7, 0), notes="U sinov so'rovi"))
s.commit()
s.close()

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

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def kontekst(w, h, ua=None):
            tel = w < 700
            k = {"viewport": {"width": w, "height": h}, "is_mobile": tel, "has_touch": tel, "timezone_id": "Asia/Tashkent",
                 "locale": "uz-UZ", "screen": {"width": w, "height": h}}
            if ua:
                k["user_agent"] = ua
            ctx = br.new_context(**k)
            ctx.set_default_timeout(15000)
            ctx.route(re.compile(r"^https://.*"), lambda r: r.fulfill(status=204, body=""))
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATO.append((w, str(e)[:300])))
            return ctx, pg

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def kut(pg, kod, ms=10000):
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

        def korinadi(pg, sel):
            return ev(pg, "(s) => { const e = document.querySelector(s); if (!e) return false; const r = e.getBoundingClientRect(); "
                          "return getComputedStyle(e).display !== 'none' && r.width > 0 && r.height > 0; }", sel)

        def hodim_kir(pg, tel, pin):
            xav(pg.goto, BU + "/hodim/login")
            xav(pg.fill, "input[name=phone]", tel)
            xav(pg.fill, "input[name=pin]", pin)
            xav(pg.click, "button[type=submit]")
            xav(pg.wait_for_load_state, "networkidle")

        SHKALA = {12, 13, 14, 16, 18, 24, 32}       # loyiha shrift shkalasi (test_u13 bilan bir xil)

        def shriftlar(pg):
            """Ko'rinadigan matnli elementlarning shrift o'lchamlari (px) — shkaladan tashqarisi."""
            r = ev(pg, """() => { const s = {}; for (const e of document.querySelectorAll('body *')) {
                const t = Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
                if (!t || !e.offsetParent && getComputedStyle(e).position !== 'fixed') continue;
                const f = parseFloat(getComputedStyle(e).fontSize); (s[f] = s[f] || []).push(e.tagName + '.' + e.className); }
                return s; }""")
            return {k: v[:3] for k, v in (r if isinstance(r, dict) else {"xato": [str(r)]}).items() if k == "xato" or float(k) not in SHKALA}

        def matn(pg):
            r = ev(pg, "() => document.body.innerText")
            return r if isinstance(r, str) else ""

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U1. Hodim yangi telefondan kiradi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        HC, HP = kontekst(375, 812, ANDROID)
        hodim_kir(HP, "+998 90 777 66 55", "4321")
        kut(HP, "(document.getElementById('kutishHolat') || {}).textContent && document.getElementById('kutishHolat').textContent.includes('-tekshiruv')", 9000)
        _u1 = ev(HP, "() => ({url: location.pathname, sig: document.documentElement.scrollWidth <= innerWidth, "
                     "holat: (document.getElementById('kutishHolat') || {}).textContent || null})")
        _sh1 = shriftlar(HP)
        check("U1 375 px: raqam bo'sh joyli (admin bo'sh joysiz saqlagan) — kirdi; «Bu telefon hali tasdiqlanmagan», holat qatori bor va "
              "so'rab turadi (tekshiruvlar soni), ekranga sig'adi (gorizontal surilish yo'q), shriftlar loyiha shkalasida",
              isinstance(_u1, dict) and _u1.get("url") == "/hodim" and "Bu telefon hali tasdiqlanmagan" in matn(HP)
              and _u1.get("sig") is True and "Ruxsat kutilmoqda" in str(_u1.get("holat")) and "-tekshiruv" in str(_u1.get("holat"))
              and not _sh1, (_u1, _sh1, matn(HP)[:300]))

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U2–U3. Admin Bosh sahifasida ruxsat beradi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        AC, AP = kontekst(1440, 900)
        xav(AP.goto, BU + "/login")
        xav(AP.fill, "input[name=username]", "hqu_admin")
        xav(AP.fill, "input[name=password]", "Parol123!")
        xav(AP.click, "button[type=submit]")
        xav(AP.wait_for_load_state, "networkidle")
        xav(AP.goto, BU + "/dashboard")
        kut(AP, "(() => { const m = document.getElementById('qurilmaModal'); return m && m.style.display === 'flex'; })()")
        _u2 = ev(AP, "() => ({q: (document.getElementById('qurilmaModal') || {style: {}}).style.display, "
                     "a: (document.getElementById('advReqModal') || {style: {}}).style.display, "
                     "t: (document.getElementById('qurilmaList') || {}).innerText || ''})")
        check("U2 Bosh sahifa: «🔔 Hodim yangi telefondan kirmoqchi» oynasi — ism, telefon (Android), vaqt; avans so'rovlari oynasi bu paytda "
              "YOPIQ (ikki oyna ustma-ust chiqmaydi)",
              isinstance(_u2, dict) and _u2.get("q") == "flex" and _u2.get("a") in ("none", "", None)
              and "Ulug'bek" in _u2.get("t", "") and "Android" in _u2.get("t", "") and "kirmoqchi bo'ldi" in _u2.get("t", ""), _u2)
        xav(AP.click, "#qurilmaList button:has-text('Ruxsat berish')")
        kut(AP, "(() => { const a = document.getElementById('advReqModal'); return a && a.style.display === 'flex'; })()")
        _u3 = ev(AP, "() => ({q: document.getElementById('qurilmaModal').style.display, a: document.getElementById('advReqModal').style.display, "
                     "n: document.querySelectorAll('#qurilmaList .qurilma-qator').length, t: document.getElementById('advReqList').innerText})")
        _sv = A.get("/api/admin/qurilma-sorovlari")
        _eu = next((x for x in (A.get("/api/employees").json() or []) if x.get("id") == EU), {})
        check("U3 «✅ Ruxsat berish» — qator yo'qoldi, oyna yopildi; KEYIN avans so'rovlari oynasi chiqdi (Jurabek, 150 000); serverda —"
              " telefon bog'landi, so'rov qolmadi",
              isinstance(_u3, dict) and _u3.get("q") == "none" and _u3.get("a") == "flex" and _u3.get("n") == 0
              and "Jurabek" in _u3.get("t", "") and _sv.status_code == 200 and _sv.json() == []
              and isinstance(_eu.get("qurilma"), dict) and "Android" in str(_eu["qurilma"].get("nomi")), (_u3, _sv.text[:200], _eu))
        xav(AP.click, "#advReqModal button[data-yopish]")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U4–U5. Hodim o'z PIN ini qo'yadi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _o = kut(HP, "location.pathname === '/hodim' && !!document.getElementById('pinYangi')", 12000)
        _u4a = ev(HP, "() => ({eski: !!document.getElementById('pinEski'), sig: document.documentElement.scrollWidth <= innerWidth})")
        _sh4 = shriftlar(HP)
        check("U4a ruxsatdan keyin kutish sahifasi O'ZI PIN sahifasiga o'tdi (≤ 12 s); hozirgi PIN so'ralmaydi; ekranga sig'adi; shriftlar "
              "loyiha shkalasida",
              _o and isinstance(_u4a, dict) and _u4a.get("eski") is False and _u4a.get("sig") is True
              and "O'z PIN kodingizni qo'ying" in matn(HP) and not _sh4, (_o, _u4a, _sh4, matn(HP)[:200]))
        xav(HP.fill, "#pinYangi", "1111")
        xav(HP.fill, "#pinTakror", "1111")
        xav(HP.click, "#pinSaqla")
        kut(HP, "(document.getElementById('pinXato') || {}).textContent && document.getElementById('pinXato').textContent.includes('oson')")
        _x1 = ev(HP, "() => document.getElementById('pinXato').textContent")
        xav(HP.fill, "#pinYangi", "5823")
        xav(HP.fill, "#pinTakror", "5832")
        xav(HP.click, "#pinSaqla")
        kut(HP, "document.getElementById('pinXato').textContent.includes('bir xil yozilmadi')", 6000)
        _x2 = ev(HP, "() => document.getElementById('pinXato').textContent")
        check("U4b oson PIN (1111) — server sababi («juda oson»); ikki marta mos emas — sabab (yuborilmaydi)",
              "juda oson" in str(_x1) and "bir xil yozilmadi" in str(_x2), (_x1, _x2))
        xav(HP.fill, "#pinTakror", "5823")
        xav(HP.click, "#pinSaqla")
        _o = kut(HP, "!!document.getElementById('submit-btn')")
        _u4c = ev(HP, "() => { const p = document.querySelector('a.h-pin'); const t = document.querySelector('.h-topbar'); "
                      "return {pin: p ? p.textContent.trim() : null, sig: document.documentElement.scrollWidth <= innerWidth, "
                      "top: t ? Math.round(t.scrollWidth - t.clientWidth) : null}; }")
        check("U4c to'g'ri PIN — panel (avans formasi); yuqorida «🔒 PIN» havolasi, sarlavha ekranga sig'adi",
              _o and isinstance(_u4c, dict) and _u4c.get("pin") == "🔒 PIN" and _u4c.get("sig") is True and _u4c.get("top") == 0, _u4c)
        xav(HP.click, "a.h-pin")
        xav(HP.wait_for_load_state, "networkidle")
        xav(HP.fill, "#pinEski", "9999")
        xav(HP.fill, "#pinYangi", "6043")
        xav(HP.fill, "#pinTakror", "6043")
        xav(HP.click, "#pinSaqla")
        kut(HP, "(document.getElementById('pinXato') || {}).textContent && document.getElementById('pinXato').textContent.includes('Hozirgi')")
        _x3 = ev(HP, "() => document.getElementById('pinXato').textContent")
        xav(HP.fill, "#pinEski", "5823")
        xav(HP.click, "#pinSaqla")
        _o = kut(HP, "!!document.getElementById('submit-btn')")
        check("U5 «🔒 PIN»: hozirgi PIN noto'g'ri — «Hozirgi PIN noto'g'ri»; to'g'ri — o'zgardi, panelga qaytdi",
              "Hozirgi PIN noto'g'ri" in str(_x3) and _o, (_x3, _o))

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U6. Ikkinchi telefon — admin KPI oynasida rad etadi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        IC, IP = kontekst(390, 844, IPHONE)
        hodim_kir(IP, "+998907776655", "6043")
        _i1 = "Bu telefon hali tasdiqlanmagan" in matn(IP)
        xav(AP.goto, BU + "/kpi")
        kut(AP, "!!document.querySelector('#empList .emp-qurilma')")
        _q = ev(AP, "() => Array.from(document.querySelectorAll('#empList .emp-qurilma')).map(e => e.textContent.trim())")
        xav(AP.click, f"#empList button[data-id='{EU}']:has-text('Kirish')")
        kut(AP, "document.getElementById('panelAccessModal').style.display === 'flex'")
        _m = ev(AP, "() => ({tel: document.getElementById('pa-phone').value, q: document.getElementById('pa-qurilma').innerText})")
        check("U6a ikkinchi telefon kutadi; KPI qatorida «🔔 Yangi telefon ruxsat kutmoqda: iPhone · Safari»; «🔑 Kirish» oynasida telefon "
              "raqami (ilgari doim bo'sh), bog'langan (Android) va kutayotgan (iPhone) telefon, PIN — hodimning o'zi qo'ygan",
              _i1 and isinstance(_q, list) and any("Yangi telefon ruxsat kutmoqda: iPhone · Safari" in x for x in _q)
              and isinstance(_m, dict) and _m.get("tel") == "+998907776655" and "Bog'langan telefon: Android" in _m.get("q", "")
              and "iPhone · Safari" in _m.get("q", "") and "PIN ni hodimning o'zi qo'ygan" in _m.get("q", ""), (_i1, _q, _m))
        xav(AP.click, "#pa-qurilma button:has-text('Rad etish')")
        kut(AP, "!document.getElementById('pa-qurilma').innerText.includes('iPhone')")
        _m2 = ev(AP, "() => document.getElementById('pa-qurilma').innerText")
        _o = kut(IP, "document.body.innerText.includes('Bu telefonga ruxsat berilmadi')", 12000)
        check("U6b «❌ Rad etish» — oynada faqat bog'langan telefon qoldi; iPhone sahifasi o'zi «Bu telefonga ruxsat berilmadi» ga o'tdi; "
              "asl telefon panelda ishlayveradi",
              "iPhone" not in str(_m2) and "Bog'langan telefon: Android" in str(_m2) and _o
              and xav(HP.reload) is not None and "Avans oldim deb yozish" in matn(HP), (_m2, _o, matn(IP)[:200]))

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U7. Telefonni uzish")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        xav(AP.click, "#pa-qurilma button:has-text('Telefonni uzish')")
        _ok_btn = kut(AP, "(() => { const b = document.getElementById('ccModalOk'); return !!(b && b.offsetParent) && b.textContent.trim() === 'Uzish'; })()", 3000)
        if _ok_btn:
            xav(AP.click, "#ccModalOk")
        kut(AP, "document.getElementById('pa-qurilma').innerText.includes(\"hali bog'lanmagan\")")
        _m3 = ev(AP, "() => document.getElementById('pa-qurilma').innerText")
        xav(HP.reload)
        xav(HP.wait_for_load_state, "networkidle")
        _hu = ev(HP, "() => location.pathname")
        check("U7 «Telefonni uzish» (tasdiq so'raladi — «Uzish» tugmasi) — «Telefon hali bog'lanmagan»; hodim sahifasi yangilansa — kirish sahifasi",
              _ok_btn is True and "hali bog'lanmagan" in str(_m3) and _hu == "/hodim/login", (_ok_btn, _m3, _hu))
        xav(AP.click, "#panelAccessModal button[data-yopish]")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U8. Bosh sahifadagi oyna — Esc")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        hodim_kir(HP, "+998907776655", "6043")
        xav(AP.goto, BU + "/dashboard")
        _o1 = kut(AP, "(() => { const m = document.getElementById('qurilmaModal'); return m && m.style.display === 'flex'; })()")
        xav(AP.keyboard.press, "Escape")
        _o2 = kut(AP, "(() => { const a = document.getElementById('advReqModal'); return a && a.style.display === 'flex'; })()")
        _u8 = ev(AP, "() => ({q: document.getElementById('qurilmaModal').style.display, a: document.getElementById('advReqModal').style.display})")
        check("U8 yangi so'rov — oyna chiqdi; Esc bilan yopildi (so'rov qoladi), keyin avans so'rovlari oynasi",
              _o1 and _o2 and isinstance(_u8, dict) and _u8.get("q") == "none" and _u8.get("a") == "flex"
              and len(A.get("/api/admin/qurilma-sorovlari").json()) == 1, (_o1, _o2, _u8))
        HC.close()
        IC.close()
        AC.close()
        br.close()

    section("U9. Sahifa xatosi")
    check("U9 JS sahifa xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])
    server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
