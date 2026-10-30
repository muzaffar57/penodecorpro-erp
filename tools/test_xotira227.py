#!/usr/bin/env python3
"""
test_xotira227.py — kech163 (zip 227 «kichik texnik qoldiqlar»: brauzer xotirasi yopiq bo'lsa sahifa xatosi — review225 O2; Salomatlik
server matni escape siz — review225 O3).

NIMA UCHUN KERAK
  Brauzer xotirasi (localStorage / sessionStorage) — faqat qulaylik (yozuv turi, tungi rejim, shtorka, qoralama). U ishlamasa (sayt ma'lumoti
  bloklangan, Android ilova ichidagi brauzerda DOM xotirasi o'chiq, xotira to'la) ilgari HAMMA sahifada JS xatosi bo'lardi: `base.html`
  `let currentScript = localStorage.getItem(...)` try siz — skript blokining qolgani (kirill → lotin o'girib yuboruvchi `fetch` o'rami)
  o'rnatilmasdi, «Кирилл» va tungi rejim tugmalari xato berardi, `typeof currentScript` (grafik o'rami) ham xato otib grafiklar chizilmasdi.
QOIDA: xotiraga murojaat — try bilan; o'qib bo'lmasa — Lotin / yorug'; yozib bo'lmasa — shu sahifada ishlaydi; tungi rejim yozilmasa —
  sahifa qayta yuklanmaydi. Salomatlikdagi server matni — `escapeHtml`.
BO'LIMLAR
  S — manba (try siz murojaat yo'q; Salomatlik escape). B — HAQIQIY Chromium, 4 rejim (oddiy / yopiq — SecurityError / null — Android
  WebView / quota — yozish xatosi) × 19 sahifa: JS xatosi yo'q (B1), grafiklar oddiy rejimdagidek (B2), «Кирилл» ishlaydi (B3), saqlanishi
  (B4), tungi rejim (B5), kirill matn serverga lotin bo'lib ketadi (B6). L — Salomatlik escape (javob ushlanadi).
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. (Faqat sahifa o'zgargan — PG bo'limi yo'q.)
Asl kodga (zip 226) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_xotira227.py
"""
import os
import io
import re
import sys
import json
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k227_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k227.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "PG_URL"):
    os.environ.pop(_k, None)

YORLIQ = "[TF1] " if TF else ""
OK = FAIL = 0
FAILED = []


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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


@contextlib.contextmanager
def bolim(nom):
    """Bo'lim xatosi (asl kodda yo'q element) — sinov qulamasin: bo'lim «yiqildi» deb yoziladi, keyingisi davom etadi."""
    try:
        yield
    except Exception as e:                 # noqa: BLE001
        check(f"{nom} — bo'lim oxirigacha bajarildi", False, f"{type(e).__name__}: {e}")


with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User                  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k227_pl", PAROL, UserRole.ADMIN, "K227 Platforma", company_id=1)
_u = s.query(User).filter(User.username == "k227_pl").first()
_u.is_platform_admin = True
s.commit()
s.close()
# Grafiklar chizilishi uchun ma'lumot: joriy oyning 1-kunida ikki xil xarajat (Moliya «xarajat tarkibi», Hisobotlar trend / doira)
import datetime as _dt                              # noqa: E402
_c0 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_c0.post("/login", data={"username": "k227_pl", "password": PAROL}, follow_redirects=False)
_H0 = {"Origin": "https://testserver", "Sec-Fetch-Site": "same-origin"}
_seed = [_c0.post("/api/finance/transactions", headers=_H0, json={"category": _k, "amount": 500000, "notes": "k227",
                                                                 "date": _dt.date.today().replace(day=1).isoformat()}).status_code
         for _k in ("arenda", "boshqa")]
assert _seed == [200, 200], _seed

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_B = open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8").read()
_L = open(os.path.join(ROOT, "templates", "logs.html"), encoding="utf-8").read()


def _trysiz(matn):
    """`localStorage.` / `sessionStorage.` murojaati — o'sha qatorda `try {` yoki yuqoridagi ochiq `try {` blokida emas (qavs chuqurligi
    bo'yicha, izoh qatorlari tashlanadi). Faqat <script> ichidagi oddiy kod uchun — taxminiy, lekin bu loyiha uslubiga yetarli."""
    yomon = []
    qatorlar = matn.split("\n")
    for i, q in enumerate(qatorlar):
        t = q.strip()
        if t.startswith("//") or t.startswith("*") or t.startswith("/*") or t.startswith("{#"):
            continue
        for m in re.finditer(r"\b(localStorage|sessionStorage)\.", q):
            if "try" in q[:m.start()] and "{" in q[:m.start()]:
                continue
            # yuqoriga qarab: murojaatni o'rab turgan bloklar — eng yaqin `try {` (funksiya / `<script>` chegarasigacha)
            chuqur = 0
            topildi = False
            for j in range(i - 1, max(-1, i - 300), -1):
                qj = re.sub(r"//.*$", "", qatorlar[j])
                if "<script" in qj:
                    break
                chuqur += qj.count("}") - qj.count("{")
                if chuqur < 0:                      # shu qator o'rab turgan blokni ochadi
                    if re.search(r"\btry\s*\{", qj):
                        topildi = True
                        break
                    if re.search(r"\bfunction\b|=>", qj):
                        break                       # funksiya chegarasi — tashqaridagi try chaqiruv paytida himoya qilmaydi
                    chuqur = 0
            if not topildi:
                yomon.append(f"{i + 1}: {t[:90]}")
    return yomon


_trysizlar = {}
for _f in sorted(os.listdir(os.path.join(ROOT, "templates"))):
    if _f.endswith(".html"):
        _y = _trysiz(open(os.path.join(ROOT, "templates", _f), encoding="utf-8").read())
        if _y:
            _trysizlar[_f] = _y
for _f in sorted(os.listdir(os.path.join(ROOT, "static"))):
    if _f.endswith(".js"):
        _y = _trysiz(open(os.path.join(ROOT, "static", _f), encoding="utf-8").read())
        if _y:
            _trysizlar["static/" + _f] = _y
check("S1 shablonlarda va skriptlarda brauzer xotirasiga try siz murojaat yo'q (hamma `templates/*.html`, `static/*.js`)", not _trysizlar, _trysizlar)
check("S2 base.html: yozuv turi — avval «lotin», o'qish try ichida; saqlash try ichida; tungi rejim — yozilmasa qayta yuklanmaydi",
      "let currentScript = 'lotin';\ntry { currentScript = localStorage.getItem('erp_script') || 'lotin'; } catch (e) {" in _B
      and "try { localStorage.setItem('erp_script', currentScript); } catch (e) {" in _B
      and "if (saqlandi) location.reload();" in _B and "let currentScript = localStorage" not in _B)
check("S3 logs.html (review225 O3): Salomatlikda jadval / ustun / to'g'ri qiymatlar / moliya turi — `escapeHtml` bilan",
      "(${issue.table}.${issue.column})" not in _L and "issue.valid_names.join(" not in _L
      and "(${TYPE_LABEL[iss.type] || iss.type})" not in _L
      and "${escapeHtml(issue.table)}.${escapeHtml(issue.column)}" in _L and "map(v => escapeHtml(v))" in _L
      and "escapeHtml(TYPE_LABEL[iss.type] || iss.type)" in _L)

import uvicorn                                      # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402
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
BU = f"http://127.0.0.1:{port}"

SAHIFALAR = ["/", "/dashboard", "/orders", "/projects", "/inventory", "/finance", "/finished", "/returns", "/debts", "/kpi", "/suppliers",
             "/suppliers/receive", "/production", "/logs", "/sozlamalar", "/rollar", "/trash", "/users", "/reports"]
REJIMLAR = {
    "oddiy": "",
    "yopiq": """(() => { for (const n of ['localStorage', 'sessionStorage']) { try { Object.defineProperty(window, n, {configurable: true,
        get() { throw new DOMException('The operation is insecure.', 'SecurityError'); }}); } catch (e) {} } })();""",
    "null": """(() => { for (const n of ['localStorage', 'sessionStorage']) { try { Object.defineProperty(window, n, {configurable: true,
        get() { return null; }}); } catch (e) {} } })();""",
    "quota": """(() => { try { Storage.prototype.setItem = function () { throw new DOMException('Quota', 'QuotaExceededError'); }; } catch (e) {} })();""",
}
# Grafik kutubxonasi (internetdan) o'rniga — chaqiruvlarni sanaydigan soxta `Chart` (base.html o'rami uni o'z ichiga oladi)
DASH_CHARTS = {"finance": {"total_paid": 12345678, "total_budget": 23456789},
               "months": [{"label": "Sen", "orders": 4}, {"label": "Okt", "orders": 5}],
               "statuses": {"new": 3, "in_progress": 2, "ready": 6}, "master_kpi": []}
CHART_STUB = "window.Chart = function (ctx, cfg) { return {destroy() {}, update() {}, config: cfg, data: cfg && cfg.data}; };"
LOTIN_TUGMA = ("🔤 Lotin", "🔤 Лотин")
OLCHOV = """() => {
  const b = document.getElementById('script-toggle-btn'), ik = document.getElementById('themeIcon');
  const m = (document.querySelector('main, .main-content, .content') || document.body).innerText.replace(/Кирилл/g, '');
  return {grafik: (window._chartInstances || []).length, tugma: b ? b.textContent.trim() : null, kirill: /[\\u0400-\\u04FF]{3,}/.test(m),
          tema: document.documentElement.getAttribute('data-theme'), ikon: ik ? ik.className : null};
}"""


def kontekst(br, rejim, yozuv=None, tema=None):
    c = br.new_context(viewport={"width": 1280, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    c.set_default_timeout(20000)
    c.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"),
            lambda r: r.fulfill(status=200, body=CHART_STUB, content_type="application/javascript")
            if re.search(r"chart(\.umd)?(\.min)?\.js", r.request.url, re.I) else r.fulfill(status=204, body=""))
    c.route("**/api/dashboard/charts", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(DASH_CHARTS)))
    lg = c.new_page()
    lg.goto(BU + "/login")
    lg.fill("input[name=username]", "k227_pl")
    lg.fill("input[name=password]", PAROL)
    lg.press("input[name=password]", "Enter")
    lg.wait_for_load_state("networkidle")
    if yozuv:
        lg.evaluate(f"() => {{ try {{ localStorage.setItem('erp_script', '{yozuv}'); }} catch (e) {{}} }}")
    if tema:
        lg.evaluate(f"() => {{ try {{ localStorage.setItem('theme', '{tema}'); }} catch (e) {{}} }}")
    lg.close()
    if REJIMLAR[rejim]:
        c.add_init_script(REJIMLAR[rejim])
    return c


def sahifa(c, yol, kut=500):
    pg = c.new_page()
    pg._x227 = []
    pg.on("pageerror", lambda e: pg._x227.append(str(e).split("\n")[0][:200]))
    # review227 F2: sahifa ushlab faqat konsolga yozadigan xato (Bosh panel grafigi: «currentScript is not defined») — ham sanaladi
    pg.on("console", lambda m: pg._x227.append("konsol: " + m.text[:200])
          if m.type == "error" and re.search(r"currentScript|insecure|localStorage|sessionStorage|QuotaExceeded|reading '(get|set)Item'", m.text)
          else None)
    pg.goto(BU + yol)
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(kut)
    return pg


with sync_playwright() as pw:
    br = pw.chromium.launch()
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("B — brauzer xotirasi: 4 rejim × 19 sahifa")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    NAT = {}
    with bolim("B"):
        for rejim in REJIMLAR:
            c = kontekst(br, rejim)
            for yol in SAHIFALAR:
                pg = sahifa(c, yol)
                y = {"bosh": pg.evaluate(OLCHOV)}
                n0 = len(pg._x227)
                pg.evaluate("() => { try { toggleScript(); } catch (e) { setTimeout(() => { throw e; }); } }")
                pg.wait_for_timeout(500)
                y["kirill"] = pg.evaluate(OLCHOV)
                pg.evaluate("() => { try { toggleScript(); } catch (e) { setTimeout(() => { throw e; }); } }")
                pg.wait_for_timeout(300)
                y["lotin"] = pg.evaluate(OLCHOV)
                y["kirill_xato"] = pg._x227[n0:]
                y["xato"] = sorted(set(pg._x227))
                NAT.setdefault(rejim, {})[yol] = y
                pg.close()
            c.close()
        _xatolar = {f"{r}{y}": v["xato"] for r, d in NAT.items() for y, v in d.items() if v["xato"]}
        check("B1 4 rejim (oddiy / yopiq / null / quota) × 19 sahifa: ochilganda va «Кирилл» ↔ «Lotin» almashganda JS xatosi YO'Q",
              not _xatolar and len(NAT) == 4 and all(len(d) == 19 for d in NAT.values()), _xatolar)
        _gr = {r: {y: NAT[r][y]["bosh"]["grafik"] for y in ("/dashboard", "/finance", "/reports")} for r in NAT}
        check("B2 grafiklar: Bosh panel / Moliya / Hisobotlar — xotira yopiq / yo'q / to'la bo'lsa ham oddiy rejimdagidek chiziladi (oddiyda Bosh panel 2 — buyurtmalar soni va holatlar, Hisobotlar 2 — trend va xarajat doirasi)",
              _gr["oddiy"]["/dashboard"] == 2 and _gr["oddiy"]["/reports"] == 2 and all(_gr[r] == _gr["oddiy"] for r in _gr), _gr)
        _kr = {f"{r}{y}": (v["kirill"]["tugma"], v["kirill"]["kirill"], v["lotin"]["tugma"], v["lotin"]["kirill"])
               for r, d in NAT.items() for y, v in d.items()
               if not (v["kirill"]["tugma"] in LOTIN_TUGMA and v["kirill"]["kirill"] and v["lotin"]["tugma"] == "🔤 Кирилл"
                       and not v["lotin"]["kirill"] and v["bosh"]["tugma"] == "🔤 Кирилл")}
        check("B3 «Кирилл» tugmasi HAR rejimda ishlaydi: bosilgach tugma «🔤 Lotin» («Лотин»), sahifa kirillda; qayta bosilgach — Lotin (19 sahifa × 4)",
              not _kr, _kr)
    # B4 — saqlanishi: oddiy — keyingi sahifa kirillda; yopiq / null — keyingi sahifa Lotin, xatosiz; quota (avval 'kirill' saqlangan) — kirillda
    with bolim("B4"):
        _b4 = {}
        for rejim in REJIMLAR:
            c = kontekst(br, rejim)
            pg = sahifa(c, "/orders")
            pg.evaluate("() => { try { toggleScript(); } catch (e) {} }")
            pg.wait_for_timeout(300)
            pg.close()
            pg = sahifa(c, "/finance")
            _t4 = pg.evaluate(OLCHOV)["tugma"]
            _b4[rejim] = ("🔤 Lotin" if _t4 in LOTIN_TUGMA else _t4, pg._x227[:2])
            pg.close()
            c.close()
        c = kontekst(br, "quota", yozuv="kirill")
        pg = sahifa(c, "/orders")
        _t4 = pg.evaluate(OLCHOV)["tugma"]
        _b4["quota_kirill"] = ("🔤 Lotin" if _t4 in LOTIN_TUGMA else _t4, pg._x227[:2])
        pg.close()
        c.close()
        check("B4 yozuv turi saqlanishi: oddiy — keyingi sahifa kirillda (avvalgidek); xotira yopiq / yo'q — keyingi sahifa Lotin, xatosiz; "
              "xotira to'la (avval «kirill» saqlangan) — kirillda",
              _b4 == {"oddiy": ("🔤 Lotin", []), "yopiq": ("🔤 Кирилл", []), "null": ("🔤 Кирилл", []), "quota": ("🔤 Кирилл", []),
                      "quota_kirill": ("🔤 Lotin", [])}, _b4)
    # B5 — tungi rejim
    with bolim("B5"):
        _b5 = {}
        for rejim in REJIMLAR:
            c = kontekst(br, rejim)
            pg = sahifa(c, "/finance")
            _nav = []
            pg.on("framenavigated", lambda f, n=_nav, p=pg: n.append(1) if f == p.main_frame else None)
            pg.evaluate("() => { try { toggleTheme(); } catch (e) { setTimeout(() => { throw e; }); } }")
            pg.wait_for_timeout(1200)
            pg.wait_for_load_state("networkidle")
            o = pg.evaluate(OLCHOV)
            _b5[rejim] = {"tema": o["tema"], "ikon": o["ikon"], "qayta": len(_nav), "xato": pg._x227[:2]}
            if rejim == "oddiy":
                pg.close()
                pg = sahifa(c, "/orders")
                _b5["oddiy_keyingi"] = pg.evaluate(OLCHOV)["tema"]
            pg.close()
            c.close()
        c = kontekst(br, "quota", tema="dark")
        pg = sahifa(c, "/finance")
        _bosh5 = pg.evaluate(OLCHOV)["tema"]
        _nav = []
        pg.on("framenavigated", lambda f, n=_nav, p=pg: n.append(1) if f == p.main_frame else None)
        pg.evaluate("() => { try { toggleTheme(); } catch (e) { setTimeout(() => { throw e; }); } }")
        pg.wait_for_timeout(1200)
        pg.wait_for_load_state("networkidle")
        o = pg.evaluate(OLCHOV)
        _b5["quota_tungidan"] = {"bosh": _bosh5, "tema": o["tema"], "ikon": o["ikon"], "qayta": len(_nav), "xato": pg._x227[:2]}
        pg.close()
        c.close()
        check("B5 tungi rejim: oddiy — sahifa BIR marta qayta yuklanadi, rejim saqlanadi (keyingi sahifa ham tungi); xotira yopiq / yo'q / to'la — "
              "rejim shu sahifada almashadi, belgi «☀», qayta yuklanmaydi (aks holda darhol yorug'ga qaytardi), xatosiz; xotira to'la va avval «tungi» saqlangan — tungidan yorug'ga ham (review227 F1)",
              _b5.get("oddiy", {}).get("tema") == "dark" and _b5["oddiy"]["qayta"] == 1 and not _b5["oddiy"]["xato"]
              and _b5.get("oddiy_keyingi") == "dark"
              and all(_b5[r] == {"tema": "dark", "ikon": "ti ti-sun", "qayta": 0, "xato": []} for r in ("yopiq", "null", "quota"))
              and _b5.get("quota_tungidan") == {"bosh": "dark", "tema": None, "ikon": "ti ti-moon", "qayta": 0, "xato": []}, _b5)
    # B6 — kirill matn serverga lotin bo'lib ketadi (umumiy `fetch` o'rami xotira yopiq bo'lsa ham o'rnatilgan)
    with bolim("B6"):
        _b6 = {}
        for rejim in REJIMLAR:
            c = kontekst(br, rejim)
            pg = sahifa(c, "/orders", 200)
            _tana = []

            def _ushla(t):
                def _h(r):                 # kech138b: route ishlovchisi — BITTA parametr (ikkinchisiga `request` beriladi)
                    try:
                        t.append(r.request.post_data)
                    except Exception:      # noqa: BLE001
                        t.append(None)
                    r.fulfill(status=200, content_type="application/json", body="{}")
                return _h
            pg.route("**/api/__k227_sinov", _ushla(_tana))
            pg.evaluate("""() => fetch('/api/__k227_sinov', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                                             body: JSON.stringify({nom: 'Карниз', ich: ['Устун']})}).then(r => r.status)""")
            _b6[rejim] = json.loads(_tana[0]) if _tana and _tana[0] else None
            pg.close()
            c.close()
        check("B6 kirillcha yozilgan matn serverga LOTIN bo'lib ketadi — HAR rejimda (xotira yopiq bo'lsa ham umumiy o'ram ishlaydi)",
              all(v == {"nom": "Karniz", "ich": ["Ustun"]} for v in _b6.values()) and len(_b6) == 4, _b6)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("L — Salomatlik: server matni escape")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("L"):
        c = kontekst(br, "oddiy")
        pg = sahifa(c, "/logs?tab=health", 300)
        _zarar = '<img src=x data-k227="1">'
        _javob = {"checked_at": "2026-10-30T13:00:00", "total_checks": 12, "issues_found": 2, "technical_hidden": False,
                  "issues": [{"id": 1, "label": "A", "table": "orders" + _zarar, "column": "status" + _zarar, "bad_value": "q",
                              "valid_names": ["NEW", "X" + _zarar]},
                             {"id": "7" + _zarar, "label": "", "table": "orders", "column": "status", "bad_value": "w", "valid_names": ["NEW"]}],
                  "sxema": {"tekshirildi": True, "jadvallar": 63, "ustunlar": 786, "farqlar": [], "kengaytirilgan": [],
                            "ishga_tushish": {"xatolar": []}},
                  "financial": {"issues_found": 2, "issues": [{"label": "ORD-1", "type": "yangi_tur" + _zarar, "detail": "z"},
                                                              {"label": "ORD-2", "type": "debt_mismatch", "detail": "y"}]}}

        def _hs(r):
            r.fulfill(status=200, content_type="application/json", body=json.dumps(_javob))
        pg.route("**/api/system/health-check", _hs)
        pg.evaluate("() => { runHealthCheck(); }")
        pg.wait_for_timeout(900)
        _l = pg.evaluate("""() => { const q = document.querySelector('details.sht[data-sht="jr-qiymat"] .sht-ich');
          const m = document.querySelector('details.sht[data-sht="jr-moliya"] .sht-ich');
          return {img: document.querySelectorAll('img[data-k227]').length, q: q ? q.textContent.replace(/\\s+/g, ' ') : null,
                  m: m ? m.textContent.replace(/\\s+/g, ' ') : null}; }""")
        check("L1 Salomatlik: jadval / ustun / to'g'ri qiymatlar / raqam / moliya turi ichidagi HTML — MATN (element yaratilmaydi)",
              _l["img"] == 0 and _l["q"] and "(orders" + _zarar + ".status" + _zarar + ")" in _l["q"]
              and "To'g'ri qiymatlar: NEW, X" + _zarar in _l["q"] and "#7" + _zarar in _l["q"]
              and _l["m"] and "(yangi_tur" + _zarar + ")" in _l["m"], _l)
        check("L2 oddiy qiymatlar avvalgidek: «(orders.status)», «To'g'ri qiymatlar: NEW», moliya turi nomi «Qarz hisobi mos emas»",
              _l["q"] and "(orders.status)" in _l["q"] and "To'g'ri qiymatlar: NEW" in _l["q"] and _l["m"] and "(Qarz hisobi mos emas)" in _l["m"], _l)
        check("L3 sahifa JS xatosi yo'q", not pg._x227, pg._x227[:3])
        pg.close()
        c.close()
    br.close()
server.should_exit = True

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
