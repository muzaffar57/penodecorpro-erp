#!/usr/bin/env python3
"""
test_loyiha_bajarilgan_ui.py — kech124 (zip 145) darvozasi: Loyihalar sahifasi holat paneli «🏭 Bajarilgan» — HAQIQIY brauzerda
(Chromium, Playwright) O'LCHANADI.

NIMA UCHUN (staging zip 144 jonli sinovida O'LCHANGAN, 06.10.2026 22:1x, PRJ-051): sahifa ochilganda birinchi loyiha `window.load` da
tanlanadi, `loadProgressMap()` (fetch `/api/projects/progress-map`) undan KEYIN qaytsa, panel «🏭 Bajarilgan» `progressMap[id] || 0`
dan BIR MARTA yozilgan 0 % bo'lib QOLARDI — xaritada 40 %, chapdagi ro'yxat kartasida 40 %, panelda 0 %. Xarita xato yoki 403
qaytarsa ham panel 0 % (yolg'on raqam). Bu xato zip 144 dan oldin ham bor edi (staging `a2e278e`).
QOIDA (zip 145, `templates/projects.html`): xarita kelguncha panelda «…», kelganda — HOZIR tanlangan loyiha foizi (xarita qaysi paytda
kelsa ham, `bajarilganYangila()`), kelmasa (HTTP xato, ruxsat yo'q, xarita emas) — «—». Ro'yxat kartalari avvalgidek.
BO'LIMLAR: S — statik (shablon); P — tayyorgarlik (xarita API qiymatlari); B — brauzer 1440 px: B1 oddiy yuklash, B2 xarita KECHIKADI
  (birinchi loyiha), B3 kechikkan paytda BOSHQA loyiha tanlanadi, B4 xarita kelgach loyihalar orasida almashish, B5 xarita 500
  (darhol va loyiha tanlangandan KEYIN), B6 xarita 403 (keyin), B7 xarita `null` va ro'yxat (obyekt emas), B8 sahifa yuklanishiga
  bitta xarita so'rovi, B9 sahifada JS xatosi yo'q; R — telefon 390 px (B2).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 144) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` va Chromium (`PLAYWRIGHT_BROWSERS_PATH` / `/opt/pw-browsers`).
ISHLATISH: python3 tools/test_loyiha_bajarilgan_ui.py
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = os.environ.get("BAJ_PG_BAZA", "loyiha_bajarilgan_test")
_T = tempfile.mkdtemp(prefix="loyiha_baj_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'loyiha_bajarilgan_test.db')}"
os.environ.pop("TENANT_FILTER", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Project, Order, OrderStatus, OrderType   # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def funksiya(src, nom):
    """`function nom(` (yoki `async function`) tanasi — qavslar muvozanati bilan; topilmasa ''."""
    m = re.search(r"(async\s+)?function\s+" + re.escape(nom) + r"\s*\(", src)
    if not m:
        return ""
    j = src.find("{", m.end())
    if j < 0:
        return ""
    d = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            d += 1
        elif src[k] == "}":
            d -= 1
            if d == 0:
                return src[m.start():k + 1]
    return ""


# ══════════════════════════════════════════════════════════════
section("S. Statik — templates/projects.html")
PRJ = oqi("templates/projects.html")
_lsp = funksiya(PRJ, "loadStatusPanel")
_lpm = funksiya(PRJ, "loadProgressMap")
_bm = funksiya(PRJ, "bajarilganMatni")
_by = funksiya(PRJ, "bajarilganYangila")
check("S1 holat paneli «🏭 Bajarilgan» qiymati o'z id si bilan (`sp-bajarilgan`) va `bajarilganMatni(d.id)` dan — xarita holatiga "
      "qarab; ilgari `progressMap[d.id] || 0` — xarita kelmagan bo'lsa yolg'on 0 %",
      'id="sp-bajarilgan"' in _lsp and "bajarilganMatni(d.id)" in _lsp and "progressMap[d.id] || 0" not in PRJ,
      _lsp[:600])
check("S2 `loadProgressMap` — HTTP holati tekshiriladi (`r.ok`), javob obyekt bo'lishi shart; muvaffaqiyatda holat 'tayyor', xatoda "
      "'xato'; ikkala holatda ham oxirida `bajarilganYangila()` (xarita qachon kelsa ham panel yangilanadi)",
      "r.ok" in _lpm and "progressMapHolat = 'tayyor'" in _lpm and "progressMapHolat = 'xato'" in _lpm
      and re.search(r"catch\s*\(e\)\s*\{[^}]*\}\s*bajarilganYangila\(\);\s*\}$", _lpm.strip()) is not None, _lpm[:900])
check("S3 `bajarilganMatni`: 'tayyor' — foiz (`Number(...) || 0` + '%'), 'xato' — «—», aks holda «…»; `bajarilganYangila` — HOZIR "
      "tanlangan loyiha (`selectedProjId`) uchun `sp-bajarilgan` ni yozadi",
      "progressMapHolat === 'tayyor'" in _bm and "'—'" in _bm and "'…'" in _bm
      and "getElementById('sp-bajarilgan')" in _by and "bajarilganMatni(selectedProjId)" in _by,
      [_bm[:300], _by[:300]])
check("S4 boshlang'ich holat — `let progressMapHolat = 'kutilmoqda';` (sahifa ochilganda xarita hali yo'q)",
      "let progressMapHolat = 'kutilmoqda';" in PRJ, None)

# ══════════════════════════════════════════════════════════════
section("P. Tayyorgarlik — 3 loyiha (A 50 %, B 100 %, C 0 %) va xarita API")
ADMIN, PAROL = "baj_admin", "Parol123!"
_hozir = datetime.now(timezone.utc).replace(tzinfo=None)      # bazada UTC (naive) — dastur qoidasi
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, ADMIN, PAROL, UserRole.ADMIN, "Bajarilgan Admin", company_id=1)


def _loyiha(nom, kun, holatlar):
    p = Project(company_id=1, client_name=f"{nom} Mijoz", project_name=f"{nom} loyiha", project_number=f"PRJ-B{nom}",
                total_budget=0, total_paid=0, start_date=_hozir - timedelta(days=kun))
    s.add(p)
    s.flush()
    for i, h in enumerate(holatlar, 1):
        s.add(Order(company_id=1, project_id=p.id, order_number=f"ORD-B{nom}-{i}", order_type=OrderType.PRODUCT, status=h,
                    total_amount=0, agreed_amount=0,
                    completed_at=_hozir if h in (OrderStatus.READY, OrderStatus.DELIVERED) else None))
    s.flush()
    return p.id


A = _loyiha("A", 0, [OrderStatus.READY, OrderStatus.IN_PROGRESS])
B = _loyiha("B", 1, [OrderStatus.READY])
C = _loyiha("C", 2, [])
s.commit()
s.close()

from fastapi.testclient import TestClient          # noqa: E402
_tc = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = _tc.post("/login", data={"username": ADMIN, "password": PAROL}, follow_redirects=False)
check("P1 kirish (TestClient) — 302", _lr.status_code == 302, _lr.status_code)
_xr = _tc.get("/api/projects/progress-map")
try:
    XARITA = {int(k): v for k, v in _xr.json().items()}
except Exception as _e:                    # noqa: BLE001
    XARITA = {"xato": f"{type(_e).__name__}: {_e}"}
check("P2 `GET /api/projects/progress-map` — A 50 %, B 100 % (yagona qoida `crud.loyiha_bajarilish_foizi`), C (buyurtmasiz) — 0 "
      "yoki yo'q", _xr.status_code == 200 and XARITA.get(A) == 50 and XARITA.get(B) == 100 and XARITA.get(C, 0) == 0,
      [_xr.status_code, XARITA])

# ══════════════════════════════════════════════════════════════
section("B. Brauzer — Loyihalar sahifasi, 1440 px")
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"
check("B0 Python `playwright` bor (HAQIQIY brauzer o'lchovi shart — taxmin bilan emas)", PW_BOR, _pw_xato)

import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


CHART_ORINBOSAR = "window.Chart = function () { return {destroy() {}, update() {}}; };"
PANEL_JS = r"""() => {
  const it = [...document.querySelectorAll('#statusPanel .status-panel-item')]
    .find(e => { const l = e.querySelector('.status-panel-lbl'); return l && l.textContent.includes('Bajarilgan'); });
  return it ? it.querySelector('.status-panel-val').textContent.trim() : null;
}"""
XARITA_RE = re.compile(r"/api/projects/progress-map(\?.*)?$")

if PW_BOR:
    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    check("B0a lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"

    def yonalish(route):
        u = route.request.url
        if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
            return route.fulfill(status=200, content_type="application/javascript", body=CHART_ORINBOSAR)
        if u.startswith("https://fonts.googleapis.com/"):
            return route.fulfill(status=200, content_type="text/css", body="")
        return route.fulfill(status=204, body="")

    with sync_playwright() as pw:
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                  "chrome-linux", "chrome"))):
            _exe = _yol
        try:
            br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()
        except Exception as _e:            # noqa: BLE001
            br = None
            check("B0b Chromium ishga tushdi", False, f"{type(_e).__name__}: {_e}")

        JS_XATOLAR = []

        def kontekst(w):
            tel = w < 1000
            ctx = br.new_context(viewport={"width": w, "height": 900 if not tel else 844}, device_scale_factor=1, is_mobile=tel,
                                 has_touch=tel, timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                                 r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
            pg = ctx.new_page()
            pg.goto(BU + "/login")
            pg.fill("input[name=username]", ADMIN)
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
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

        def panel(pg):
            return ev(pg, PANEL_JS)

        def karta_matni(pg, pid):
            return ev(pg, "(id) => { const e = document.getElementById('pbaj-' + id); return e ? e.textContent.trim() : null; }", str(pid))

        def tanlangan(pg):
            return ev(pg, "() => (typeof selectedProjId === 'undefined' || selectedProjId === null) ? null : String(selectedProjId)")

        def bos(pg, pid):
            try:
                pg.click(f'.proj-card[data-id="{pid}"]', timeout=5000)
                return True
            except Exception:              # noqa: BLE001
                return False

        def sahifa(w=1440, ushla=False, javob=None):
            """Yangi sahifa: `ushla` — xarita so'rovi to'xtatib turiladi (qo'lda qo'yib yuboriladi); `javob` — (status, body)
            bilan soxta javob. Qaytaradi: ctx, pg, ushlanganlar, so'rovlar soni, sahifa xatolari."""
            ctx, pg = kontekst(w)
            tutilgan, sorov, xatolar = [], [], []
            pg.on("pageerror", lambda e: xatolar.append(str(e)[:200]))
            pg.on("request", lambda r: sorov.append(r.url) if XARITA_RE.search(r.url) else None)

            def _x(route):
                if ushla:
                    tutilgan.append(route)
                    return None
                if javob is not None:
                    return route.fulfill(status=javob[0], content_type="application/json", body=javob[1])
                return route.continue_()
            pg.route(XARITA_RE, _x)
            pg.goto(BU + "/projects")
            kut(pg, "() => document.querySelector('#statusPanel .status-panel-item') !== null")
            return ctx, pg, tutilgan, sorov, xatolar

        def qoyib_yubor(pg, tutilgan):
            for r in tutilgan:
                try:
                    r.continue_()
                except Exception:          # noqa: BLE001
                    pass
            # kartalar xarita kelgach yoziladi (ikkala kodda ham) — panel o'shandan keyin o'qiladi
            return kut(pg, f"() => {{ const e = document.getElementById('pbaj-{A}'); return !!e && e.textContent.includes('%'); }}")

        def javob_ber(pg, tutilgan, status, body):
            """Ushlangan xarita so'roviga KECH (loyiha tanlangandan keyin) soxta javob; panel «…» dan chiqishini kutadi."""
            for r in tutilgan:
                try:
                    r.fulfill(status=status, content_type="application/json", body=body)
                except Exception:          # noqa: BLE001
                    pass
            return kut(pg, "() => { const v = (" + PANEL_JS + ")(); return v !== null && v !== '…'; }", 6000)

        if br:
            # B1 — oddiy yuklash (xarita darhol)
            ctx, pg, _t, sor1, xat1 = sahifa()
            kut(pg, f"() => {{ const e = document.getElementById('pbaj-{A}'); return !!e && e.textContent.includes('%'); }}")
            kut(pg, "() => { const v = (" + PANEL_JS + ")(); return v !== null && v !== '…'; }", 4000)
            _birinchi = ev(pg, "() => { const c = document.querySelector('.proj-card'); return c ? c.dataset.id : null; }")
            check("B1a tayyorgarlik: ro'yxatda birinchi karta — A (eng yangi sana), sahifa ochilganda u tanlanadi",
                  _birinchi == str(A) and tanlangan(pg) == str(A), [_birinchi, tanlangan(pg), A])
            check("B1b oddiy yuklash: panel «🏭 Bajarilgan» — 50% (xarita bilan AYNAN), ro'yxat kartasi «🏭 Bajarilgan 50%»",
                  panel(pg) == "50%" and karta_matni(pg, A) == "🏭 Bajarilgan 50%", [panel(pg), karta_matni(pg, A)])
            check("B8a sahifa yuklanishiga BITTA xarita so'rovi", len(sor1) == 1, sor1)
            JS_XATOLAR += xat1
            ctx.close()

            # B2 — xarita kechikadi: birinchi loyiha tanlanadi, so'ng xarita keladi
            ctx, pg, tut, sor2, xat2 = sahifa(ushla=True)
            _oldin = panel(pg)
            check("B2a xarita hali kelmagan (so'rov to'xtatib turilgan): panelda «…» (ilgari — yolg'on «0%»)",
                  len(tut) == 1 and tanlangan(pg) == str(A) and _oldin == "…", [len(tut), tanlangan(pg), _oldin])
            _kel = qoyib_yubor(pg, tut)
            check("B2b xarita KEYIN keldi: panel — 50% (A, hozir tanlangan; ilgari 0% bo'lib QOLARDI — staging PRJ-051 da O'LCHANGAN)",
                  _kel and panel(pg) == "50%", [_kel, panel(pg), karta_matni(pg, A)])
            check("B8b kechikkan holatda ham bitta xarita so'rovi", len(sor2) == 1, sor2)
            JS_XATOLAR += xat2
            ctx.close()

            # B3 — xarita kechikkan paytda boshqa loyiha tanlanadi
            ctx, pg, tut, _s, xat3 = sahifa(ushla=True)
            _bosdi = bos(pg, B)
            _oldin = panel(pg)
            check("B3a xarita kelmasdan B tanlandi: panelda «…» (ilgari «0%»)", _bosdi and tanlangan(pg) == str(B) and _oldin == "…",
                  [_bosdi, tanlangan(pg), _oldin])
            _kel = qoyib_yubor(pg, tut)
            check("B3b xarita keldi: panel — B ning 100% i (HOZIR tanlangan loyiha; birinchi A ning 50% i EMAS, ilgari 0%)",
                  _kel and tanlangan(pg) == str(B) and panel(pg) == "100%", [_kel, tanlangan(pg), panel(pg)])
            JS_XATOLAR += xat3

            # B4 — xarita kelgach almashish (shu sahifada)
            _q = []
            for pid, kutil in ((A, "50%"), (C, "0%"), (B, "100%"), (A, "50%")):
                _ok = bos(pg, pid)
                _q.append((pid, _ok, tanlangan(pg), panel(pg), kutil))
            check("B4 xarita kelgach loyihalar orasida almashish: A 50%, C (buyurtmasiz) 0%, B 100%, A 50%",
                  all(ok and t == str(pid) and v == k for pid, ok, t, v, k in _q), _q)
            ctx.close()

            # B5a — xarita 500 (darhol)
            ctx, pg, _t, _s, xat5 = sahifa(javob=(500, '{"detail": "sinov xatosi"}'))
            kut(pg, "() => { const v = (" + PANEL_JS + ")(); return v !== null && v !== '…'; }", 6000)
            _v5 = panel(pg)
            _bosdi = bos(pg, B)
            _v5b = panel(pg)
            check("B5a xarita 500 qaytardi: panelda «—» (yolg'on «0%» emas), boshqa loyiha tanlanganda ham «—»; ro'yxat kartasida foiz "
                  "yozilmaydi", _v5 == "—" and _bosdi and _v5b == "—" and karta_matni(pg, A) == "", [_v5, _bosdi, _v5b, karta_matni(pg, A)])
            JS_XATOLAR += xat5
            ctx.close()

            # B5b — xarita 500, lekin KECH (loyiha tanlangandan keyin)
            ctx, pg, tut, _s, xat5b = sahifa(ushla=True)
            _oldin = panel(pg)
            _kel = javob_ber(pg, tut, 500, '{"detail": "sinov xatosi"}')
            check("B5b xarita 500 ni loyiha tanlangandan KEYIN qaytardi: panel «…» dan «—» ga o'tadi (ilgari «0%» bo'lib qolardi)",
                  len(tut) == 1 and _oldin == "…" and _kel and panel(pg) == "—", [len(tut), _oldin, _kel, panel(pg)])
            JS_XATOLAR += xat5b
            ctx.close()

            # B6 — xarita 403 (ruxsat yo'q), KECH
            ctx, pg, tut, _s, xat6 = sahifa(ushla=True)
            _oldin = panel(pg)
            _kel = javob_ber(pg, tut, 403, '{"detail": "Ruxsat yo\'q"}')
            check("B6 xarita 403 (ruxsat yo'q) loyiha tanlangandan keyin: panel «…» dan «—» ga (ilgari «0%»)",
                  len(tut) == 1 and _oldin == "…" and _kel and panel(pg) == "—", [len(tut), _oldin, _kel, panel(pg)])
            JS_XATOLAR += xat6
            ctx.close()

            # B7 — xarita 200, lekin `null`
            ctx, pg, _t, _s, xat7 = sahifa(javob=(200, "null"))
            kut(pg, "() => { const v = (" + PANEL_JS + ")(); return v !== null && v !== '…'; }", 6000)
            _v7 = panel(pg)
            _bosdi = bos(pg, C)
            _v7b = panel(pg)
            check("B7 xarita `null` (obyekt emas): panelda «—», keyin boshqa loyiha tanlanganda ham panel chiziladi («—»), sahifada "
                  "JS xatosi yo'q", _v7 == "—" and _bosdi and _v7b == "—" and not xat7, [_v7, _bosdi, _v7b, xat7])
            JS_XATOLAR += xat7
            ctx.close()

            # B7c — xarita 200, lekin ro'yxat (obyekt emas) — hamma loyiha uchun yolg'on «0%» chiqmasin
            ctx, pg, _t, _s, xat7c = sahifa(javob=(200, "[50, 100]"))
            kut(pg, "() => { const v = (" + PANEL_JS + ")(); return v !== null && v !== '…'; }", 6000)
            _v7c = panel(pg)
            check("B7c xarita ro'yxat ko'rinishida (`[50, 100]` — obyekt emas): panelda «—» (yolg'on «0%» emas)", _v7c == "—", _v7c)
            JS_XATOLAR += xat7c
            ctx.close()

            check("B9 B1–B7 da sahifada JS xatosi (pageerror) yo'q", not JS_XATOLAR, JS_XATOLAR)

            # R — telefon 390 px
            section("R. Telefon — 390 px")
            ctx, pg, tut, _s, xatr = sahifa(w=390, ushla=True)
            _oldin = panel(pg)
            _kel = qoyib_yubor(pg, tut)
            check("R1 telefon: xarita kelguncha «…», kelgach 50% (A), JS xatosi yo'q",
                  len(tut) == 1 and _oldin == "…" and _kel and panel(pg) == "50%" and not xatr, [len(tut), _oldin, _kel, panel(pg), xatr])
            ctx.close()
            br.close()
    server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
