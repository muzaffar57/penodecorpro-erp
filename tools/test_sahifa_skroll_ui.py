#!/usr/bin/env python3
"""
test_sahifa_skroll_ui.py — kech139 (zip 167, egasi 11.10 17:19: «Platforma bilan sozlamalar bo'limi pastga tushmayapti»): HAR sahifa
foydalanuvchi surishi (sichqoncha g'ildiragi) bilan OXIRIGACHA suriladi — HAQIQIY brauzerda (Chromium, Playwright), HAQIQIY lokal
server bilan (uvicorn, test bazasi).

NIMA UCHUN KERAK (O'LCHANGAN — sinov saytida 375×812, zip 166): `base.html` da `.erp-main` — `overflow:hidden`, sahifa kontenti o'z
skroll konteyneriga muhtoj (`.erp-content` yoki `height:calc(…);overflow-y:auto`). 5 sahifada o'ram oddiy blok edi — kontent ekrandan
uzun bo'lsa pastga SURILMASDI: «Platforma» (3341 px, ko'rinadi 812), «Sozlamalar» (2353), «Tizim jurnallari» (1094), «O'chirilganlar»
(1347), «Ishlab chiqarish» va «Xarajat qo'shish» (qisqa — past ekranda).
TEKSHIRUV: har sahifa, ikki o'lcham (telefon 375×420, kompyuter 1280×520): sahifadagi ENG PASTKI ko'rinadigan element (modal / qotirilgan
qismlar va ichki cheklangan ro'yxatlardan tashqari) — boshida ekrandan pastda bo'lsa, kontent markazida g'ildirak bilan pastga surilgach
ekranda ko'rinadi (U); o'ram bolalari siqilmagan (U7); har sahifa kontenti o'rami (`.erp-main` ning bevosita bolasi) — skroll
konteyneri (U8).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 166) qarshi QULAMAYDI — 5 sahifada yiqiladi.
ISHLATISH: python3 tools/test_sahifa_skroll_ui.py
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

PG_BAZA = "sahifa_skroll_ui167_test"
_T = tempfile.mkdtemp(prefix="skroll_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'skroll_ui_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User                  # noqa: E402

s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    _u = auth.create_user(s, "skr_a", "Parol123!", UserRole.ADMIN, "Skroll admin", company_id=1)
s.query(User).filter(User.id == _u.id).update({User.is_platform_admin: True})
s.commit()
s.close()

SAHIFALAR = ["/", "/inventory", "/orders", "/projects", "/production", "/finished", "/returns", "/debts", "/finance", "/reports", "/kpi",
             "/ustalar", "/suppliers", "/suppliers/receive", "/recipes", "/users", "/rollar", "/logs", "/sozlamalar", "/trash",
             "/kunlik-xarajat", "/platforma"]
OLCHAMLAR = [("telefon", 375, 420, True), ("kompyuter", 1280, 520, False)]

ENG_PAST = r"""() => {
  const m = document.querySelector('.erp-main');
  if (!m) return {xato: 'erp-main yo\'q'};
  const korin = el => { const s = getComputedStyle(el); if (s.display === 'none' || s.visibility === 'hidden') return false;
                        const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const qotgan = el => { for (let e = el; e && e !== m; e = e.parentElement) { const p = getComputedStyle(e).position;
                         if (p === 'fixed' || p === 'sticky') return true; } return false; };
  // ichki ro'yxat (o'z balandligi cheklangan skroll qutisi) — sahifa o'rami (`.erp-main` ning bevosita bolasi) EMAS
  const ichki = el => { for (let e = el.parentElement; e && e !== m && e.parentElement !== m; e = e.parentElement) {
                        const s = getComputedStyle(e);
                        if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && e.clientHeight < e.scrollHeight - 1) return true; }
                        return false; };
  let past = null, eng = -1;
  for (const e of m.querySelectorAll('*')) {
    if (e.closest('.erp-topbar') || e.children.length || !korin(e) || qotgan(e) || ichki(e)) continue;
    const b = e.getBoundingClientRect().bottom;
    if (b > eng) { eng = b; past = e; }
  }
  if (!past) return {xato: 'element yo\'q'};
  past.setAttribute('data-skroll-past', '1');
  const r = past.getBoundingClientRect();
  let oram = past; while (oram.parentElement && oram.parentElement !== m) oram = oram.parentElement;
  const os = getComputedStyle(oram).overflowY;
  // o'ram bolalari SIQILMAGAN: overflow:hidden / clip li bola o'z kontentidan past bo'lmasin (cheklangan o'ramda flex-shrink)
  const siqilgan = [...oram.children].filter(c => { const s = getComputedStyle(c);
    return (s.overflowY === 'hidden' || s.overflowY === 'clip') && s.display !== 'none' && c.scrollHeight > c.clientHeight + 1
      && c.getBoundingClientRect().height > 0; }).map(c => (c.id ? '#' + c.id : '') + '.' + String(c.className || '').trim().split(/\s+/)[0]
      + ' ' + c.clientHeight + '/' + c.scrollHeight);
  return {top: Math.round(r.top), bottom: Math.round(r.bottom), ih: innerHeight, teg: past.tagName,
          matn: (past.textContent || past.getAttribute('aria-label') || past.className || '').trim().slice(0, 40),
          oram: (oram.id ? '#' + oram.id : '') + '.' + String(oram.className || '').trim().replace(/\s+/g, '.'),
          oramSkroll: os === 'auto' || os === 'scroll', siqilgan};
}"""
YANA = r"""() => { const e = document.querySelector('[data-skroll-past]'); if (!e) return null; const r = e.getBoundingClientRect();
  return {top: Math.round(r.top), bottom: Math.round(r.bottom), ih: innerHeight}; }"""

section("U. Brauzer — foydalanuvchi surishi")
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
    OGRAM = []
    SIQILGAN = []

    def tashqi(route):
        u = route.request.url
        if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
            return route.fulfill(status=200, content_type="application/javascript",
                                 body="window.Chart = function () { return {destroy() {}, update() {}}; };")
        return route.fulfill(status=204, body="")

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()
        for nom, w, h, tel in OLCHAMLAR:
            ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ")
            ctx.set_default_timeout(20000)
            ctx.add_init_script("try { window.addEventListener('load', () => document.querySelectorAll('details.sht').forEach(d => { d.open = true; })); } catch (e) {}")      # kech160 (zip 225): eng uzun holat — shtorkalar ochiq
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                                 r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), tashqi)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e, n=nom: JS_XATO.append((n, str(e)[:300])))
            pg.goto(BU + "/login")
            pg.fill("input[name=username]", "skr_a")
            pg.fill("input[name=password]", "Parol123!")
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            for y in SAHIFALAR:
                try:
                    pg.goto(BU + y, wait_until="networkidle")
                    pg.wait_for_timeout(500)
                    oldin = pg.evaluate(ENG_PAST)
                    pg.mouse.move(w / 2, min(h - 40, 58 + (h - 58) / 2))
                    for _ in range(40):
                        pg.mouse.wheel(0, 700)
                    pg.wait_for_timeout(400)
                    keyin = pg.evaluate(YANA)
                except Exception as ex:    # noqa: BLE001
                    oldin, keyin = {"xato": f"{type(ex).__name__}: {ex}"[:200]}, None
                uzun = isinstance(oldin, dict) and oldin.get("bottom", 0) > oldin.get("ih", 0) + 1
                OGRAM.append((nom, y, (oldin or {}).get("oram"), (oldin or {}).get("oramSkroll")))
                if (oldin or {}).get("siqilgan"):
                    SIQILGAN.append((nom, y, oldin["siqilgan"]))
                yetdi = isinstance(keyin, dict) and keyin["bottom"] <= keyin["ih"] + 1 and keyin["top"] < keyin["ih"]
                check(f"U {nom} {w}×{h} {y}: eng pastki element g'ildirak bilan ekranga suriladi"
                      + ("" if uzun else " (kontent ekranga sig'adi)"),
                      "xato" not in (oldin or {}) and (yetdi or not uzun), (oldin, keyin))
            ctx.close()
        br.close()
    _yomon = [x for x in OGRAM if not x[3]]
    check("U8 har sahifa kontenti o'rami (`.erp-main` ning bolasi) — skroll konteyneri (overflow-y auto) — `.erp-main` overflow:hidden",
          len(OGRAM) == len(SAHIFALAR) * len(OLCHAMLAR) and not _yomon, _yomon)
    check("U7 o'ram bolalari siqilmagan (overflow:hidden li karta o'z kontentidan past emas — ustma-ust tushmaydi)", not SIQILGAN,
          SIQILGAN[:6])
    check("U9 JS sahifa xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])
    server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
