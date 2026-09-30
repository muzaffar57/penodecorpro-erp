#!/usr/bin/env python3
"""
test_b118_oyna.py — kech118, B bosqichi 1-qism: DASTURNING O'Z OYNALARI (xabar, kiritish, yopish) va o'zbekcha 404 / 403.

NIMA UCHUN KERAK (audit kech114 — O'LCHANGAN; asl kod = `staging` 1c5408e)
  U-07  brauzerning xom `alert()` oynasi 70 joyda (tepasida sayt manzili, sahifani to'xtatadi), `prompt()` 5 joyda (qarz
        to'lovi, sotuv narxi, xarid miqdori / narxi, «HAMMASINI-OCHIR»), `confirm()` 1 joyda (Telegram bot).
  U-08  61 oynadan 55 tasi Esc ga javob bermasdi, ko'pchiligi tashqariga bosishda ham yopilmasdi.
  U-11  noto'g'ri manzil — oq sahifada {"detail":"Not Found"}; ruxsatsiz sahifa — {"detail":"Bu sahifaga faqat admin,
        manager kira oladi"} (inglizcha rol nomlari).
QOIDA (base.html): `xabarOyna` (alert o'rniga; brauzerning native `alert` i shunga yo'naltiriladi), `kiritishOyna` (prompt
  o'rniga), Esc / tashqariga bosish — eng ustki oynaning `data-yopish` tugmasi (ma'lumot yozilgan bo'lsa — so'raladi),
  `data-yopish-ichki` — oyna ichidagi panel avval, `data-esc-ozi` — o'z Esc ishlovchisi bor oyna.
BO'LIMLAR: S — statik (shablonlar); H — HTTP (404 / 403 sahifa va JSON); J — HAQIQIY server + jsdom (sahifalarning o'z
  JavaScript'i: xabar oynasi, kiritish oynasi, Esc, tashqariga bosish, yozilgan ma'lumot, ichki panel, xom oynalar yo'q);
  X — JS xatolari / 5xx.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI (yangi nomlar — `getattr`,
  sahifada — `typeof`).
ISHLATISH: NODE_PATH=$(npm root -g) python3 tools/test_b118_oyna.py
"""
import os
import re
import sys
import json
import glob
import time
import socket
import shutil
import tempfile
import threading
import subprocess
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "b118_oyna_test"
_T = tempfile.mkdtemp(prefix="b118o_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'b118_oyna_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Project              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HOLATLAR = []


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
        print(f"  ✗ {label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.headers = {}

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    HOLATLAR.append((metod.upper() + " " + url.split("?")[0], r.status_code))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


TPL = os.path.join(ROOT, "templates")
SHABLON = {os.path.basename(f): open(f, encoding="utf-8").read() for f in sorted(glob.glob(os.path.join(TPL, "*.html")))}


def kod_qatorlari(src):
    """Izohsiz JS / HTML qatorlari (// … va <!-- … --> va {# … #} izohlari olib tashlanadi — izohda eski kod tilga olinadi)."""
    s = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src, flags=re.S)
    s = re.sub(r"\{#.*?#\}", lambda m: re.sub(r"[^\n]", " ", m.group(0)), s, flags=re.S)
    out = []
    for ln in s.split("\n"):
        t = ln.strip()
        if t.startswith("//") or t.startswith("*") or t.startswith("/*"):
            out.append("")
            continue
        out.append(re.sub(r"(?<![:'\"\\])//(?![^'\"`]*['\"`]\s*[,;)]).*$", "", ln))
    return out


section("S. Statik — shablonlar")
_xom = []
for fn, src in SHABLON.items():
    for i, ln in enumerate(kod_qatorlari(src), 1):
        for m in re.finditer(r"(?<![\w.$])(prompt|confirm)\s*\(", ln):
            _xom.append(f"{fn}:{i}: {ln.strip()[:90]}")
        for m in re.finditer(r"window\.(prompt|confirm)\s*\(", ln):
            _xom.append(f"{fn}:{i}: {ln.strip()[:90]}")
check("S1 shablonlarda brauzerning xom prompt() / confirm() chaqirig'i YO'Q (asl: 5 prompt, 1 confirm)", not _xom, _xom[:8])

_b = SHABLON.get("base.html", "")
check("S2 base.html: `xabarOyna`, `kiritishOyna`, `_xoAlertniUlash(window)` bor; alert FAQAT native bo'lsa almashtiriladi",
      "function xabarOyna(" in _b and "function kiritishOyna(" in _b and "_xoAlertniUlash(window);" in _b
      and "native code" in _b, "")

# har qoplama oyna (position:fixed + butun ekran) ichida `data-yopish` (yoki o'zi / `data-esc-ozi`)
_VOID = {"input", "img", "br", "hr", "meta", "link", "source", "area", "col", "embed", "param", "track", "wbr"}
_KLASS_QOPLAMA = {}
for fn, src in SHABLON.items():
    for m in re.finditer(r"\.([\w-]+)\s*\{[^}]*position:\s*fixed;\s*inset:\s*0", src):
        _KLASS_QOPLAMA.setdefault(fn, set()).add(m.group(1))
    for m in re.finditer(r"#([\w-]+)\s*\{[^}]*position:\s*fixed;\s*inset:\s*0", src):
        _KLASS_QOPLAMA.setdefault(fn, set()).add("#" + m.group(1))
_css = open(os.path.join(ROOT, "static", "style.css"), encoding="utf-8").read()
_UMUMIY_KLASS = set(re.findall(r"\.([\w-]+)\s*\{[^}]*position:\s*fixed;\s*inset:\s*0", _css))


class _Oyna(HTMLParser):
    def __init__(self, fn):
        super().__init__(convert_charrefs=True)
        self.fn, self.stack, self.oynalar = fn, [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        st, cl, idd = a.get("style") or "", (a.get("class") or "").split(), a.get("id") or ""
        kl = _KLASS_QOPLAMA.get(self.fn, set()) | _UMUMIY_KLASS
        qoplama = (re.search(r"position:\s*fixed", st) and re.search(r"inset:\s*0", st)) or any(c in kl for c in cl) \
            or ("#" + idd) in kl
        oyna = None
        if qoplama:
            oyna = {"id": idd or ".".join(cl), "qator": self.getpos()[0],
                    "belgi": ("data-yopish" in a) or ("data-esc-ozi" in a)}
            self.oynalar.append(oyna)
        if tag in _VOID:
            if "data-yopish" in a:
                self._belgila()
            return
        self.stack.append((tag, oyna))
        if "data-yopish" in a:
            self._belgila()

    def _belgila(self):
        for t, o in reversed(self.stack):
            if o is not None:
                o["belgi"] = True
                break

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


_belgisiz, _jami_oyna = [], 0
for fn, src in SHABLON.items():
    src2 = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", lambda m: re.sub(r"[^\n]", " ", m.group(0)), src, flags=re.S)
    p = _Oyna(fn)
    p.feed(src2)
    for o in p.oynalar:
        if o["id"] in ("sidebar-overlay",):
            pass
        _jami_oyna += 1
        if not o["belgi"]:
            _belgisiz.append(f"{fn}:{o['qator']} {o['id']}")
check(f"S3 har qoplama oyna (shablon belgilashi) yopish belgisiga ega — {_jami_oyna} ta oyna, belgisiz 0 (asl: hammasi belgisiz)",
      _jami_oyna >= 55 and not _belgisiz, (_jami_oyna, _belgisiz[:10]))

# JS da yaratiladigan qoplamalar: `position:fixed;inset:0` satridan keyingi 45 qatorda `data-yopish` bo'lsin
_RUXSAT_JS = {("users.html", "showAddedToast")}    # 0.9 s dan keyin sahifa o'zi yangilanadi
_js_belgisiz = []
for fn, src in SHABLON.items():
    L = src.split("\n")
    for i, ln in enumerate(L):
        if re.search(r"position:\s*fixed;\s*inset:\s*0", ln) and ("cssText" in ln or "`" in ln or "'" in ln.split("position")[0]) \
                and "<div" not in ln.split("position")[0][-30:] and not ln.strip().startswith("."):
            oyna_qismi = "\n".join(L[max(0, i - 3): i + 46])
            funk = ""
            for j in range(i, -1, -1):
                mm = re.match(r"\s*(?:async\s+)?function\s+(\w+)", L[j])
                if mm:
                    funk = mm.group(1)
                    break
            if (fn, funk) in _RUXSAT_JS:
                continue
            if "data-yopish" not in oyna_qismi:
                _js_belgisiz.append(f"{fn}:{i + 1} {funk}")
check("S4 JS da yaratiladigan qoplama oynalar ham belgili (MRP tanlash, foyda tafsiloti, sahifa xabar oynalari)",
      not _js_belgisiz, _js_belgisiz)
# JS da klass bilan yaratiladigan qoplamalar (`.inv-toast-overlay{position:fixed;inset:0}` → `x.className = 'inv-toast-overlay'`)
_klass_belgisiz = []
for fn, src in SHABLON.items():
    kl = _KLASS_QOPLAMA.get(fn, set()) | _UMUMIY_KLASS
    L = src.split("\n")
    for i, ln in enumerate(L):
        m = re.search(r"\.className\s*=\s*['\"]([\w-]+)['\"]", ln)
        if m and m.group(1) in kl and "data-yopish" not in "\n".join(L[i:i + 6]):
            _klass_belgisiz.append(f"{fn}:{i + 1} {m.group(1)}")
check("S4b JS da klass bilan yaratiladigan qoplamalar (Omborxona, Loyihalar, Retseptlar xabar oynalari) belgili",
      not _klass_belgisiz and sum(1 for fn, src in SHABLON.items() for ln in src.split("\n")
                                  if re.search(r"\.className\s*=\s*['\"][\w-]*toast-overlay['\"]", ln)) >= 3, _klass_belgisiz)

# xavfli amal tugmalariga belgi QO'YILMAGAN (Esc amalni bajarmasin)
_xavfli = []
for fn, src in SHABLON.items():
    for m in re.finditer(r"<[^>]*data-yopish[^>]*>", src):
        t = m.group(0)
        oc = re.search(r"onclick=\"([^\"]*)\"", t)
        oc = oc.group(1) if oc else ""
        if re.search(r"((?<![\w])delFp\(|doCancel|clearFinished|delete|Delete|ochir|save|Save|submit|Submit|confirm\w*\(|Tasdiq|reset)", oc):
            _xavfli.append(f"{fn}: {oc[:60]}")
check("S5 `data-yopish` faqat yopish tugmalarida (o'chirish / saqlash / bekor qilish AMALLARIDA yo'q)", not _xavfli, _xavfli)
_bekor = re.search(r"const bekorTugma = `([^`]*)`", SHABLON.get("production.html", ""))
check("S6 ishlab chiqarishni BEKOR QILISH tugmasi («Bekor qilish» → doCancel) belgisiz — Esc uni bosmaydi",
      _bekor and "doCancel(" in _bekor.group(1) and "data-yopish" not in _bekor.group(1), _bekor.group(1) if _bekor else None)

# xabar → sahifa yangilanadigan joylarda `await xabarOyna(...)` (dastur oynasi sahifani to'xtatmaydi)
_navbat = []
for fn, src in SHABLON.items():
    L = kod_qatorlari(src)
    for i, ln in enumerate(L):
        if re.search(r"(?<![\w.])alert\s*\(", ln):
            keyingi = next((x.strip() for x in L[i + 1:i + 4] if x.strip()), "")
            if re.match(r"(location\.reload|location\.href\s*=|window\.location)", keyingi) or \
                    re.search(r"alert\([^;]*\);\s*(location\.reload|location\.href\s*=)", ln):
                _navbat.append(f"{fn}:{i + 1}: {ln.strip()[:80]}")
check("S7 xabardan keyin sahifa yangilanadigan joyda xom alert YO'Q (`await xabarOyna` — asl: users / returns 2 joy)",
      not _navbat, _navbat)

_fok = re.search(r":where\(([^)]*)\):focus-visible\s*\{([^}]*)\}", _css)
check("S8 style.css: `:focus-visible` — tugma, havola, maydon, onclick li element; `outline … !important` (inline outline:none ustidan)",
      _fok is not None and all(x in _fok.group(1) for x in ("a", "button", "input", "select", "textarea", "[onclick]"))
      and "outline:" in _fok.group(2).replace(" ", "") and "!important" in _fok.group(2), _fok.group(0) if _fok else None)
_link = [fn for fn in ("base.html", "login.html", "hodim_login.html", "hodim_panel.html")
         if '/static/style.css?v={{ static_version }}"' not in SHABLON.get(fn, "")]
check("S9 style.css havolalari kesh versiyasi bilan (`?v={{ static_version }}`) — yangi uslub eski keshdan olinmasin",
      not _link, _link)

section("H. HTTP — 404 / 403 sahifasi (brauzer) va JSON (API)")
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "b118_admin", "Parol123!", UserRole.ADMIN, "B118 Admin", company_id=1)
    auth.create_user(s, "b118_ombor", "Parol123!", UserRole.WAREHOUSE, "B118 Omborchi", company_id=1)
PRJ = Project(company_id=1, client_name="B118 Mijoz", project_name="B118 loyiha", total_budget=0, total_paid=0)
s.add(PRJ)
s.commit()
s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "b118_admin", "password": "Parol123!"}, follow_redirects=False)
check("H0 login", _lr.status_code in (200, 302, 303), _lr.status_code)
HT = {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
r = req(C, "get", "/bunday-sahifa-yoq-118", headers=HT)
check("H1 yo'q sahifa (brauzer): 404, o'zbekcha «Bunday sahifa yo'q», «Bosh sahifaga» → /, JSON emas (asl: {\"detail\":\"Not Found\"})",
      r.status_code == 404 and "Bunday sahifa yo'q" in r.text.replace("&#39;", "'") and 'href="/"' in r.text
      and "Bosh sahifaga" in r.text and '"detail"' not in r.text, (r.status_code, r.text[:160]))
r = req(C, "get", "/bunday-sahifa-yoq-118")
check("H2 yo'q sahifa (brauzer emas — Accept */*): 404 JSON AYNAN avvalgidek", r.status_code == 404 and js(r) == {"detail": "Not Found"},
      (r.status_code, r.text[:120]))
r = req(C, "get", "/api/bunday-api-yoq-118", headers=HT)
check("H3 yo'q API (hatto text/html bilan): 404 JSON", r.status_code == 404 and js(r).get("detail") == "Not Found", r.text[:120])
r = req(C, "get", "/static/bunday-fayl-yoq-118.css", headers=HT)
check("H4 yo'q statik fayl: sahifa EMAS (404, HTML sahifa matni yo'q)", r.status_code == 404 and "Bosh sahifaga" not in r.text,
      (r.status_code, r.text[:120]))
r = req(C, "post", "/bunday-sahifa-yoq-118", headers=HT)
check("H5 POST yo'q manzilga: sahifa emas (JSON)", r.status_code in (404, 405) and "Bosh sahifaga" not in r.text, (r.status_code, r.text[:100]))
r = req(C, "get", "/hodim/bunday-yoq-118", headers=HT)
check("H6 hodim paneli yo'lida yo'q sahifa — «bosh sahifa» /hodim", r.status_code == 404 and 'href="/hodim"' in r.text, r.text[:200])
C2 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
req(C2, "post", "/login", data={"username": "b118_ombor", "password": "Parol123!"}, follow_redirects=False)
r = req(C2, "get", "/users", headers=HT)
check("H7 ruxsatsiz sahifa (Omborchi → /users, brauzer): 403, «Bu bo'limga ruxsatingiz yo'q», «Bosh sahifaga» (asl: xom JSON)",
      r.status_code == 403 and "ruxsatingiz yo" in r.text and "Bosh sahifaga" in r.text and '"detail"' not in r.text,
      (r.status_code, r.text[:200]))
r = req(C2, "get", "/api/employees")
_d = js(r).get("detail") or ""
check("H8 ruxsatsiz API: 403 JSON, rol nomlari o'zbekcha («Bu bo'lim faqat Admin uchun ochiq»; asl: «… faqat admin kira oladi»)",
      r.status_code == 403 and _d == "Bu bo'lim faqat Admin uchun ochiq", (r.status_code, _d))
_rm = getattr(auth, "rollar_matni", None)
check("H9 `auth.rollar_matni`: «Admin va Hodim», «Admin, Hodim va Omborchi», takrorsiz",
      _rm is not None and _rm([UserRole.ADMIN, UserRole.MANAGER]) == "Admin va Hodim"
      and _rm([UserRole.ADMIN, UserRole.MANAGER, UserRole.WAREHOUSE, UserRole.ADMIN]) == "Admin, Hodim va Omborchi"
      and _rm([UserRole.ADMIN]) == "Admin", _rm and _rm([UserRole.ADMIN, UserRole.MANAGER]))
_eng = [f"{f}" for f in ("admin", "manager", "warehouse", "accountant", "master") if f" {f}" in _d or f"{f}," in _d]
check("H10 rad sababida inglizcha rol qiymati yo'q", r.status_code == 403 and not _eng, _eng)
r = req(C2, "get", "/users", follow_redirects=False)
check("H11 ruxsatsiz sahifa (brauzer emas): 403 JSON — sabab o'zbekcha", r.status_code == 403 and "Bu bo'lim faqat" in (js(r).get("detail") or ""),
      (r.status_code, r.text[:100]))
r = req(C, "get", "/projects", headers=HT)
check("H12 oddiy sahifa o'zgarmadi (200)", r.status_code == 200, r.status_code)

# B118_JSDOM=0 — faqat S / H bo'limlari (mutatsiya tezligi uchun: server qoidasi o'zgarganda jsdom shart emas)
if os.environ.get("B118_JSDOM") == "0":
    print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
    if FAILED:
        print("YIQILGANLAR:")
        for f in FAILED:
            print("  -", f)
    sys.exit(0 if FAIL == 0 else 1)

# ══════════════════════════════════════════════════════════════
# J — HAQIQIY server + jsdom
# ══════════════════════════════════════════════════════════════
NODE_JS = r"""
let JSDOM, VirtualConsole, ResourceLoader;
try { ({ JSDOM, VirtualConsole, ResourceLoader } = require("jsdom")); }
catch (e) { console.log(JSON.stringify({ fatal: "jsdom topilmadi: " + String(e.message).slice(0, 200) })); process.exit(3); }
const base = process.argv[2], cookie = process.argv[3];
const sahifalar = JSON.parse(require("fs").readFileSync(process.argv[4], "utf8"));
const CHART_STUB = "window.Chart = function Chart(ctx, cfg) { this.config = cfg || {}; this.data = (cfg && cfg.data) || {datasets: []}; this.options = (cfg && cfg.options) || {}; };" +
  "window.Chart.prototype.destroy = function () {}; window.Chart.prototype.update = function () {}; window.Chart.register = function () {};" +
  "window.Chart.defaults = {font: {}, color: '', plugins: {legend: {labels: {}}, tooltip: {}}};";
class FaqatOzimiz extends ResourceLoader {
  fetch(url, options) {
    if (/chart\.umd(\.min)?\.js/i.test(url)) { const p = Promise.resolve(Buffer.from(CHART_STUB)); p.abort = () => {}; return p; }
    // jsdom tashqi uslub faylini sahifaning <style> bloklaridan KEYIN qo'shadi (brauzerda — hujjat tartibida): style.css dagi
    // `.modal-overlay{display:flex}` sahifaning `.modal-overlay{display:none}` ustidan yozilib, YOPIQ oynalar ochiqdek
    // hisoblanardi. Oynalar ko'rinishi sahifaning o'z uslublaridan (inline / <style>) — style.css yuklanmaydi.
    if (/\/static\/style\.css/.test(url)) return null;
    return url.startsWith(base) ? super.fetch(url, options) : null;
  }
}
const kut = ms => new Promise(r => setTimeout(r, ms));
const res = { sahifa: {}, xato: [], api_xato: [], natija: {} };
process.on("unhandledRejection", e => res.xato.push("va'da: " + String((e && (e.message || e)) || "").slice(0, 200)));
process.on("uncaughtException", e => res.xato.push("xato: " + String((e && (e.message || e)) || "").slice(0, 200)));
async function ochish(yol, qadamlar) {
  const r = await fetch(base + yol, { headers: { cookie }, redirect: "manual" });
  res.sahifa[yol] = r.status;
  const html = await r.text();
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => { const m = String((e && (e.message || e)) || "").slice(0, 300); if (!/Not implemented/.test(m)) res.xato.push(yol + ": " + m); });
  let pending = 0, lastActive = Date.now();
  const sahifaUrl = base + yol;
  const dom = new JSDOM(html, { url: sahifaUrl, runScripts: "dangerously", pretendToBeVisual: true,
    resources: new FaqatOzimiz(), virtualConsole: vc,
    beforeParse(w) {
      w.__sorovlar = [];
      w.fetch = async (u, o) => {
        pending++; lastActive = Date.now();
        try {
          o = o || {};
          const h = Object.assign({}, o.headers || {}); h.cookie = cookie;
          const url = new URL(String(u), sahifaUrl).href;
          if (!url.startsWith(base)) throw new Error("tashqi so'rov: " + url);
          w.__sorovlar.push({ url: url.slice(base.length), method: (o.method || "GET").toUpperCase(), body: o.body || null });
          const resp = await fetch(url, Object.assign({}, o, { headers: h, redirect: "manual" }));
          if (resp.status >= 500) res.api_xato.push(resp.status + " " + url.slice(base.length, base.length + 120));
          return resp;
        } finally { pending--; lastActive = Date.now(); }
      };
      // brauzerning HAQIQIY (native) oynalari o'rnida — Proxy (Function.prototype.toString — «[native code]»): chaqirilsa sanaladi
      w.__xom = { alert: [], prompt: 0, confirm: 0 };
      w.alert = new Proxy(function () {}, { apply(t, s, a) { w.__xom.alert.push(String(a[0]).slice(0, 80)); } });
      w.prompt = new Proxy(function () {}, { apply() { w.__xom.prompt++; return null; } });
      w.confirm = new Proxy(function () {}, { apply() { w.__xom.confirm++; return false; } });
      w.print = () => {}; w.scrollTo = () => {}; w.open = () => null;
      w.matchMedia = () => ({ matches: false, media: "", addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
      class K { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } }
      w.IntersectionObserver = K; w.ResizeObserver = K;
      w.HTMLCanvasElement.prototype.getContext = () => null;
      w.HTMLElement.prototype.scrollIntoView = () => {};
      w.__reload = 0;
      try { Object.defineProperty(w.location, "reload", { value: () => { w.__reload++; }, configurable: true }); } catch (e) {}
    } });
  const w = dom.window;
  await new Promise(r => { if (w.document.readyState === "complete") return r(); w.addEventListener("load", () => r()); setTimeout(r, 8000); });
  async function tinch() {
    await kut(700);
    const t0 = Date.now();
    while (Date.now() - t0 < 15000) { await kut(60); if (pending === 0 && Date.now() - lastActive > 400) return; }
    res.xato.push(yol + ": tarmoq 15 s ichida tinchimadi");
  }
  await tinch();
  for (const q of qadamlar) {
    try {
      // har qadam vaqt chegarasi bilan (mutatsiyada hal bo'lmaydigan va'da testni osib qo'ymasin)
      const chegara = (p) => Promise.race([p, kut(30000).then(() => { throw new Error("qadam 30 s ichida tugamadi"); })]);
      if (q.amal) { await chegara(w.eval("(async () => { " + q.amal + "\n})()")); await tinch(); }
      if (q.natija) res.natija[q.nom] = await chegara(w.eval("(async () => { " + q.natija + "\n})()"));
    } catch (e) {
      res.natija[q.nom] = { XATO: String((e && (e.stack || e.message)) || e).slice(0, 400) };
    }
  }
  w.close();
}
(async () => {
  for (const s of sahifalar) await ochish(s.yol, s.qadamlar);
  console.log(JSON.stringify(res));
  process.exit(0);
})().catch(e => { res.xato.push("yakuniy: " + String(e && e.message)); console.log(JSON.stringify(res)); process.exit(0); });
"""


def q(nom, amal=None, natija=None):
    return {"nom": nom, "amal": amal, "natija": natija}


# umumiy yordamchilar (sahifa ichida)
Y = r"""
const __d = id => { const e = document.getElementById(id); return e ? getComputedStyle(e).display : 'yoq'; };
const __esc = (el) => (el || document.activeElement || document.body).dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
const __tashqari = id => { const e = document.getElementById(id); e.dispatchEvent(new MouseEvent('mousedown', {bubbles: true})); e.dispatchEvent(new MouseEvent('click', {bubbles: true})); };
const __yoz = (el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); };
const __post = () => (window.__sorovlar || []).filter(x => x.method !== 'GET').map(x => x.method + ' ' + x.url);
"""
PRJ_Q = [
    q("p_alert", amal=Y + r"""alert('❌ Sinov: server bilan aloqa yo\'q'); alert('✅ Ikkinchi xabar');""",
      natija=Y + r"""const m = document.getElementById('xoModal');
        return {xom: window.__xom.alert.length, modal: __d('xoModal'), sarlavha: m ? m.querySelector('#xoSarlavha').textContent : null,
                matn: m ? m.querySelector('#xoMatn').textContent : null, tur: m ? m.getAttribute('data-tur') : null};"""),
    q("p_alert2", amal=Y + r"""__esc();""",
      natija=Y + r"""const m = document.getElementById('xoModal');
        return {modal: __d('xoModal'), matn: m ? m.querySelector('#xoMatn').textContent : null, tur: m ? m.getAttribute('data-tur') : null};"""),
    q("p_alert3", amal=Y + r"""document.getElementById('xoOk') && document.getElementById('xoOk').click();""",
      natija=Y + r"""return {modal: __d('xoModal')};"""),
    q("p_html", amal=Y + r"""alert('<img src=x onerror="window.__xss=1">');""",
      natija=Y + r"""const m = document.getElementById('xoModal'); const r = {img: m ? m.querySelectorAll('img').length : -1, xss: window.__xss || 0,
        matn: m ? m.querySelector('#xoMatn').textContent : null}; if (document.getElementById('xoOk')) document.getElementById('xoOk').click(); return r;"""),
    q("p_esc", amal=Y + r"""showAddModal(); window.__a = __d('addModal'); __esc();""",
      natija=Y + r"""return {oldin: window.__a, keyin: __d('addModal'), cc: __d('ccModal'), post: __post()};"""),
    q("p_tash", amal=Y + r"""showAddModal(); window.__a = __d('addModal'); __tashqari('addModal');""",
      natija=Y + r"""return {oldin: window.__a, keyin: __d('addModal'), cc: __d('ccModal')};"""),
    q("p_ichki", amal=Y + r"""showAddModal(); const b = document.getElementById('f-client');
        b.dispatchEvent(new MouseEvent('mousedown', {bubbles: true})); b.dispatchEvent(new MouseEvent('click', {bubbles: true}));
        window.__a = __d('addModal'); closeModal();""",
      natija=Y + r"""return {oyna_ichida_bosish: window.__a, keyin: __d('addModal')};"""),
    q("p_yoz", amal=Y + r"""showAddModal(); __yoz(document.getElementById('f-client'), 'B118 yozildi'); __tashqari('addModal');""",
      natija=Y + r"""return {modal: __d('addModal'), cc: __d('ccModal'), savol: document.getElementById('ccModalMessage').textContent,
        ok: document.getElementById('ccModalOk').textContent, bekor: document.getElementById('ccModalCancel').textContent};"""),
    q("p_yoz2", amal=Y + r"""document.getElementById('ccModalCancel').click();""",
      natija=Y + r"""return {modal: __d('addModal'), cc: __d('ccModal'), qiymat: document.getElementById('f-client').value};"""),
    q("p_yoz3", amal=Y + r"""__esc();""",
      natija=Y + r"""return {modal: __d('addModal'), cc: __d('ccModal')};"""),
    q("p_yoz4", amal=Y + r"""__esc(document.getElementById('ccModalOk'));""",
      natija=Y + r"""return {modal: __d('addModal'), cc: __d('ccModal')};"""),
    q("p_yoz5", amal=Y + r"""__esc(); await new Promise(r => setTimeout(r, 50)); document.getElementById('ccModalOk').click();""",
      natija=Y + r"""return {modal: __d('addModal'), cc: __d('ccModal')};"""),
    q("p_yoz6", amal=Y + r"""document.getElementById('f-client').value = ''; showAddModal(); __tashqari('addModal');""",
      natija=Y + r"""return {modal: __d('addModal'), cc: __d('ccModal'), post: __post()};"""),
    q("p_yoz7", amal=Y + r"""showAddModal(); __yoz(document.getElementById('f-client'), 'B118 yana');
        document.querySelector('#addModal [data-yopish]').click();                // o'z «Bekor» tugmasi (global ishlovchisiz)
        await new Promise(r => setTimeout(r, 50));                                // kuzatuvchi (MutationObserver) ishlaydi
        window.__a = __d('addModal'); showAddModal(); __tashqari('addModal');""",
      natija=Y + r"""return {yopildi: window.__a, modal: __d('addModal'), cc: __d('ccModal')};"""),
    q("p_nav", amal=Y + r"""showAddModal(); window.__a = __d('addModal');
        document.getElementById('f-client').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));""",
      natija=Y + r"""return {oldin: window.__a, keyin: __d('addModal')};"""),
    q("p_bosh", amal=Y + r"""__esc();""", natija=Y + r"""return {modal: __d('addModal'), xo: __d('xoModal'), cc: __d('ccModal')};"""),
    q("p_ulash", natija=r"""const f = window._xoAlertniUlash; if (typeof f !== 'function') return {yoq: true};
        const a = {alert: function () {}}, b = {alert: new Proxy(function () {}, {})}, c = {alert: 5};
        const ra = f(a), rb = f(b), rc = f(c);
        return {oddiy: ra, oddiy_tegilmadi: typeof a.alert === 'function' && !/native code/.test(Function.prototype.toString.call(a.alert)),
                native: rb, native_almashdi: !/native code/.test(Function.prototype.toString.call(b.alert)), boshqa: rc};"""),
    q("p_drag", amal=Y + r"""showAddModal(); const i = document.getElementById('f-client'), o = document.getElementById('addModal');
        i.dispatchEvent(new MouseEvent('mousedown', {bubbles: true})); o.dispatchEvent(new MouseEvent('click', {bubbles: true}));""",
      natija=Y + r"""const r = {modal: __d('addModal'), cc: __d('ccModal')}; closeModal(); return r;"""),
    # sun'iy oynalar: A (z 5000, hujjat BOSHIDA) · B (z 1000, oxirida) · C / D (z 1200, teng — hujjat tartibi) ·
    # E (o'z Esc i — data-esc-ozi, z 6000, B ustida) · P (z 10) ichida ichki fixed N (z 5, OLDIN turgan belgi bilan)
    q("s_tartib", amal=Y + r"""
        const yarat = (id, z, joy, ichki) => { const d = document.createElement('div'); d.id = id;
          d.style.cssText = 'display:flex;position:fixed;inset:0;z-index:' + z;
          d.innerHTML = (ichki || '') + '<div class="quti"><input type="text" id="' + id + '_i"><select id="' + id + '_s"><option>a</option><option>b</option></select>' +
            '<button type="button" data-yopish onclick="this.closest(\'#' + id + '\').style.display=\'none\'; (window.__yopildi = window.__yopildi || []).push(\'' + id + '\')">✕</button></div>';
          if (joy === 'bosh') document.body.insertBefore(d, document.body.firstChild); else document.body.appendChild(d); return d; };
        window.__yopildi = [];
        yarat('sA', 5000, 'bosh'); yarat('sB', 1000, 'oxir');
        __esc(); window.__t1 = [__d('sA'), __d('sB')];
        __esc(); window.__t2 = [__d('sA'), __d('sB')];
        yarat('sC', 1200, 'oxir'); yarat('sD', 1200, 'oxir');
        __esc(); window.__t3 = [__d('sC'), __d('sD')];
        __esc(); window.__t4 = [__d('sC'), __d('sD')];
        const b2 = yarat('sB2', 1000, 'oxir');
        const e = document.createElement('div'); e.id = 'sE'; e.setAttribute('data-esc-ozi', '');
        e.style.cssText = 'display:flex;position:fixed;inset:0;z-index:6000'; e.innerHTML = '<div>o\'z oynasi</div>'; document.body.appendChild(e);
        __esc(); window.__t5 = [__d('sE'), __d('sB2')];
        e.style.display = 'none'; __esc(); window.__t6 = __d('sB2');
        yarat('sP', 10, 'oxir', '<div id="sN" style="display:block;position:fixed;top:0;left:0;width:10px;height:10px;z-index:5">' +
          '<button type="button" data-yopish onclick="document.getElementById(\'sN\').style.display=\'none\'; window.__yopildi.push(\'sN\')">x</button></div>');
        __esc(); window.__t7 = [__d('sP'), __d('sN')];
        yarat('sF', 1000, 'oxir'); yarat('sG', 2000, 'oxir');
        __tashqari('sF'); window.__t8 = [__d('sF'), __d('sG')];
        __esc();
        const sel = document.getElementById('sF_s'); sel.value = 'b'; sel.dispatchEvent(new Event('change', {bubbles: true}));
        __tashqari('sF'); window.__t9 = [__d('sF'), __d('ccModal')];
        document.getElementById('ccModalOk').click(); await new Promise(r => setTimeout(r, 50));
        window.__t10 = __d('sF');
        const h = yarat('sH', 9000, 'oxir'); h.style.opacity = '0'; h.style.pointerEvents = 'none';
        yarat('sI', 100, 'oxir');
        __esc(); window.__t11 = [__d('sH'), __d('sI')];""",
      natija=r"""return {t1: window.__t1, t2: window.__t2, t3: window.__t3, t4: window.__t4, t5: window.__t5, t6: window.__t6,
                t7: window.__t7, t8: window.__t8, t9: window.__t9, t10: window.__t10, t11: window.__t11,
                yopildi: window.__yopildi};"""),
]
INV_Q = [
    q("i_ust", amal=Y + r"""openChiqimModal(); await new Promise(r => setTimeout(r, 200)); window.__v = customPrompt('B118 sinov', 'izoh', '5');
        window.__s = [__d('chiqimModal'), __d('cpModal')]; __esc();""",
      natija=Y + r"""const v = await Promise.race([window.__v, new Promise(r => setTimeout(() => r('kutilmoqda'), 300))]);
        return {oldin: window.__s, cp: __d('cpModal'), chiqim: __d('chiqimModal'), qiymat: v};"""),
    q("i_ust2", amal=Y + r"""__esc();""", natija=Y + r"""return {chiqim: __d('chiqimModal'), post: __post()};"""),
    q("i_xabar", amal=Y + r"""invToast('B118 xabar'); window.__a = __d('invToastOverlay'); __esc(); window.__b = __d('invToastOverlay');""",
      natija=Y + r"""return {oldin: window.__a, keyin: window.__b};"""),     # darhol (xabar 1,8 s dan keyin o'zi yopiladi)
]
PRD_Q = [
    q("m_yoz", amal=Y + r"""openProductTypeModal(); await new Promise(r => setTimeout(r, 150));
        const i = document.querySelector('#pt-modal input[type=text]'); __yoz(i, 'B118 tur'); __tashqari('pt-modal');""",
      natija=Y + r"""const r = {modal: __d('pt-modal'), cc: __d('ccModal')}; document.getElementById('ccModalOk').click();
        await new Promise(res => setTimeout(res, 50)); r.keyin = __d('pt-modal'); return r;"""),
    q("m_esc", amal=Y + r"""openProductTypeModal(); await new Promise(r => setTimeout(r, 150)); window.__a = __d('pt-modal'); __esc();""",
      natija=Y + r"""return {oldin: window.__a, keyin: __d('pt-modal'), post: __post()};"""),
    q("m_tash", amal=Y + r"""openProductTypeModal(); await new Promise(r => setTimeout(r, 150)); __tashqari('pt-modal');""",
      natija=Y + r"""return {keyin: __d('pt-modal')};"""),
]
REC_Q = [
    q("r_ichki", amal=Y + r"""await openAddModal(); await openIngredientPicker('f'); await new Promise(r => setTimeout(r, 200));
        window.__a = [__d('addModal'), !!document.querySelector('#f-picker-anchor .recp-picker-panel')]; __esc();""",
      natija=Y + r"""return {oldin: window.__a, panel: !!document.querySelector('#f-picker-anchor .recp-picker-panel'), oyna: __d('addModal')};"""),
    q("r_ichki2", amal=Y + r"""__esc();""", natija=Y + r"""return {oyna: __d('addModal')};"""),
]
USR_Q = [
    q("u_reset", amal=Y + r"""window.__sorovlar.length = 0; window.__f = startFactoryReset(false);
        await new Promise(r => setTimeout(r, 200)); document.getElementById('ccModalOk').click(); await new Promise(r => setTimeout(r, 200));""",
      natija=Y + r"""const ki = document.getElementById('kiModal');
        return {ki: __d('kiModal'), sarlavha: ki ? ki.querySelector('#kiSarlavha').textContent : null,
                izoh: ki ? ki.querySelector('#kiIzoh').textContent : null, xom: window.__xom.prompt};"""),
    q("u_reset2", amal=Y + r"""const m = document.getElementById('kiMaydon'); if (m) { m.value = 'NOTOGRI'; document.getElementById('kiOk').click(); }
        await window.__f;""",
      natija=Y + r"""const x = document.getElementById('xoModal');
        return {ki: __d('kiModal'), xo: __d('xoModal'), matn: x ? x.querySelector('#xoMatn').textContent : null, post: __post(),
                xom: window.__xom.alert.length};"""),
    q("u_reset3", amal=Y + r"""if (document.getElementById('xoOk')) document.getElementById('xoOk').click();
        window.__sorovlar.length = 0; window.__f = startFactoryReset(false);
        await new Promise(r => setTimeout(r, 200)); document.getElementById('ccModalOk').click(); await new Promise(r => setTimeout(r, 200));
        __esc(); await window.__f;""",
      natija=Y + r"""return {ki: __d('kiModal'), post: __post(), xo: __d('xoModal')};"""),
]
DBT_Q = [
    q("d_pay", amal=Y + r"""window.__sorovlar.length = 0; window.__f = quickPayObligation('arenda', 'Arenda', 150000, 0, 0);
        await new Promise(r => setTimeout(r, 200));""",
      natija=Y + r"""const ki = document.getElementById('kiModal');
        return {ki: __d('kiModal'), sarlavha: ki ? ki.querySelector('#kiSarlavha').textContent : null,
                qiymat: ki ? ki.querySelector('#kiMaydon').value : null, ok: ki ? ki.querySelector('#kiOk').textContent : null,
                xom: window.__xom.prompt};"""),
    q("d_pay2", amal=Y + r"""document.getElementById('kiBekor') && document.getElementById('kiBekor').click(); await window.__f;""",
      natija=Y + r"""return {ki: __d('kiModal'), post: __post()};"""),
    q("d_pay3", amal=Y + r"""window.__sorovlar.length = 0; window.__f = quickPayObligation('arenda', 'Arenda', 150000, 0, 0);
        await new Promise(r => setTimeout(r, 200)); const m = document.getElementById('kiMaydon');
        if (m) { m.value = '0'; m.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true})); }
        await window.__f;""",
      natija=Y + r"""const x = document.getElementById('xoModal');
        const r = {post: __post(), xo: __d('xoModal'), matn: x ? x.querySelector('#xoMatn').textContent : null};
        if (document.getElementById('xoOk')) document.getElementById('xoOk').click(); return r;"""),
    q("d_pay4", amal=Y + r"""window.__sorovlar.length = 0; window.__f = quickPayObligation('arenda', 'Arenda', 150000, 0, 0);
        await new Promise(r => setTimeout(r, 200)); const m = document.getElementById('kiMaydon');
        if (m) { m.value = '120 000'; document.getElementById('kiOk').click(); }
        await window.__f;""",
      natija=Y + r"""return {post: (window.__sorovlar || []).filter(x => x.method !== 'GET').map(x => [x.method + ' ' + x.url, x.body]),
                reload: window.__reload};"""),
]
LOG_Q = [
    q("l_tg", amal=Y + r"""window.__sorovlar.length = 0; window.__f = clearTgBot(); await new Promise(r => setTimeout(r, 150));
        window.__a = __d('ccModal'); document.getElementById('ccModalCancel').click(); await window.__f;""",
      natija=Y + r"""return {cc: window.__a, post: __post(), xom: window.__xom.confirm};"""),
]
SUP_Q = [
    q("s_tahrir", amal=Y + r"""window.__sorovlar.length = 0; window.__f = editPurchase(999999, 4, 12500, false);
        await new Promise(r => setTimeout(r, 150));
        const k = document.getElementById('kiModal'); window.__1 = [__d('kiModal'), k.querySelector('#kiSarlavha').textContent, k.querySelector('#kiMaydon').value];
        k.querySelector('#kiMaydon').value = '5'; document.getElementById('kiOk').click(); await new Promise(r => setTimeout(r, 150));
        window.__2 = [__d('kiModal'), k.querySelector('#kiSarlavha').textContent, k.querySelector('#kiMaydon').value];
        __esc(); await window.__f;""",
      natija=Y + r"""return {q1: window.__1, q2: window.__2, ki: __d('kiModal'), post: __post(), xom: window.__xom.prompt};"""),
]
FIN_Q = [
    q("f_narx", amal=Y + r"""window.fpItems = window.fpItems || []; if (typeof fpItems !== 'undefined') fpItems.push({id: 987654, name: 'B118 Karniz', unit: 'metr', unit_price: 45000});
        window.__sorovlar.length = 0; window.__f = editPrice(987654); await new Promise(r => setTimeout(r, 150));
        const k = document.getElementById('kiModal'); window.__1 = k ? [__d('kiModal'), k.querySelector('#kiSarlavha').textContent, k.querySelector('#kiIzoh').textContent, k.querySelector('#kiMaydon').value] : null;
        if (document.getElementById('kiBekor')) document.getElementById('kiBekor').click(); await window.__f;""",
      natija=Y + r"""return {q: window.__1, post: __post(), xom: window.__xom.prompt};"""),
]
SAHIFALAR = [{"yol": "/projects", "qadamlar": PRJ_Q}, {"yol": "/inventory", "qadamlar": INV_Q},
             {"yol": "/production", "qadamlar": PRD_Q}, {"yol": "/recipes", "qadamlar": REC_Q},
             {"yol": "/users", "qadamlar": USR_Q}, {"yol": "/debts", "qadamlar": DBT_Q}, {"yol": "/logs", "qadamlar": LOG_Q},
             {"yol": "/suppliers", "qadamlar": SUP_Q}, {"yol": "/finished", "qadamlar": FIN_Q}]

section("J0. Lokal server + jsdom")
node = shutil.which("node")
check("J0 node topildi", node is not None)
NAT = {}
if node:
    try:
        npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:                      # noqa: BLE001
        npm_root = ""
    env = dict(os.environ)
    env["NODE_PATH"] = os.pathsep.join(x for x in (os.environ.get("NODE_PATH", ""), npm_root,
                                                    os.path.join(ROOT, "node_modules")) if x)
    import uvicorn

    def _port():
        so = socket.socket()
        so.bind(("127.0.0.1", 0))
        p = so.getsockname()[1]
        so.close()
        return p

    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    check("J0 uvicorn ishga tushdi", server.started)
    base = f"http://127.0.0.1:{port}"
    try:
        import httpx
        lr = httpx.post(base + "/login", data={"username": "b118_admin", "password": "Parol123!"}, follow_redirects=False, timeout=30)
        cookie = "; ".join(hh.split(";")[0] for hh in lr.headers.get_list("set-cookie"))
        pj = os.path.join(_T, "sahifalar.json")
        with open(pj, "w", encoding="utf-8") as f:
            json.dump(SAHIFALAR, f, ensure_ascii=False)
        sj = os.path.join(_T, "b118o.js")
        with open(sj, "w", encoding="utf-8") as f:
            f.write(NODE_JS)
        k = subprocess.run([node, sj, base, cookie, pj], capture_output=True, text=True, timeout=900, env=env)
        try:
            NAT = json.loads((k.stdout or "").strip().splitlines()[-1])
        except Exception as e:             # noqa: BLE001
            NAT = {"fatal": f"{type(e).__name__}: {e}; stdout={(k.stdout or '')[-400:]} stderr={(k.stderr or '')[-400:]}"}
    finally:
        server.should_exit = True
        th.join(timeout=10)
N = NAT.get("natija") or {}
check("J0 sahifalar 200, ssenariy tugadi", "fatal" not in NAT and len(NAT.get("sahifa") or {}) == len(SAHIFALAR)
      and all(v == 200 for v in (NAT.get("sahifa") or {}).values()), {k: NAT.get(k) for k in ("sahifa", "fatal", "xato")})


def g(nom, kalit=None, std=None):
    v = N.get(nom)
    if kalit is None:
        return v
    return v.get(kalit, std) if isinstance(v, dict) else std


section("J1. Xabar oynasi (alert o'rniga)")
check("J1 alert() — brauzerning xom oynasi CHIQMADI, dastur oynasi: sarlavha «Xatolik», matn aynan, tur 'xato' (asl: xom oyna)",
      g("p_alert", "xom") == 0 and g("p_alert", "modal") == "flex" and g("p_alert", "sarlavha") == "Xatolik"
      and g("p_alert", "matn") == "❌ Sinov: server bilan aloqa yo'q" and g("p_alert", "tur") == "xato", N.get("p_alert"))
check("J2 ketma-ket ikkinchi xabar NAVBAT bilan: Esc birinchisini yopdi → ikkinchisi ko'rindi («✅» — tur 'ok')",
      g("p_alert2", "modal") == "flex" and g("p_alert2", "matn") == "✅ Ikkinchi xabar" and g("p_alert2", "tur") == "ok", N.get("p_alert2"))
check("J3 «Tushunarli» — oyna yopildi", g("p_alert3", "modal") == "none", N.get("p_alert3"))
check("J4 xabardagi HTML — matn (element yaratilmaydi)", g("p_html", "img") == 0 and not g("p_html", "xss")
      and "<img" in (g("p_html", "matn") or ""), N.get("p_html"))

check("J4b `_xoAlertniUlash`: oddiy (native EMAS) almashtirishga tegmaydi, native — almashtiradi, funksiya emas — tegmaydi",
      g("p_ulash", "oddiy") is False and g("p_ulash", "oddiy_tegilmadi") is True and g("p_ulash", "native") is True
      and g("p_ulash", "native_almashdi") is True and g("p_ulash", "boshqa") is False, N.get("p_ulash"))

section("J2. Esc va tashqariga bosish (Loyihalar)")
check("J5 Esc — «Yangi loyiha» oynasi yopildi, tasdiq so'ralmadi, hech narsa yuborilmadi (asl: Esc ga javob yo'q)",
      g("p_esc", "oldin") == "flex" and g("p_esc", "keyin") == "none" and g("p_esc", "cc") == "none" and g("p_esc", "post") == [],
      N.get("p_esc"))
check("J6 bo'sh oynaning tashqarisiga (qora fon) bosish — yopildi", g("p_tash", "oldin") == "flex" and g("p_tash", "keyin") == "none",
      N.get("p_tash"))
check("J7 oyna ICHIGA bosish (mousedown + click maydonda) yopmaydi", g("p_ichki", "oyna_ichida_bosish") == "flex", N.get("p_ichki"))
check("J8 ma'lumot yozilgan oyna — tashqariga bosishda SO'RALADI («… saqlanmaydi. Oyna yopilsinmi?», «Yopish» / «Davom etish»)",
      g("p_yoz", "modal") == "flex" and g("p_yoz", "cc") == "flex" and "saqlanmaydi" in (g("p_yoz", "savol") or "")
      and g("p_yoz", "ok") == "Yopish" and g("p_yoz", "bekor") == "Davom etish", N.get("p_yoz"))
check("J9 «Davom etish» — oyna va yozilgan matn joyida", g("p_yoz2", "modal") == "flex" and g("p_yoz2", "cc") == "none"
      and g("p_yoz2", "qiymat") == "B118 yozildi", N.get("p_yoz2"))
check("J10 ma'lumot yozilgan oynada Esc ham so'raydi", g("p_yoz3", "modal") == "flex" and g("p_yoz3", "cc") == "flex", N.get("p_yoz3"))
check("J11 tasdiq oynasida Esc — FAQAT tasdiq yopiladi (ostidagi oyna joyida)", g("p_yoz4", "cc") == "none" and g("p_yoz4", "modal") == "flex",
      N.get("p_yoz4"))
check("J12 Esc → «Yopish» — oyna yopildi", g("p_yoz5", "modal") == "none" and g("p_yoz5", "cc") == "none", N.get("p_yoz5"))
check("J13 yopilgach qayta ochilgan oyna — belgi tozalangan: tashqariga bosish so'ramasdan yopadi, so'rov yo'q",
      g("p_yoz6", "modal") == "none" and g("p_yoz6", "cc") == "none" and g("p_yoz6", "post") == [], N.get("p_yoz6"))
check("J13b oynaning O'Z «Bekor» tugmasi bilan yopilgan (yozilgan) oyna qayta ochilganda — belgi kuzatuvchi bilan tozalangan: "
      "tashqariga bosish so'ramasdan yopadi", g("p_yoz7", "yopildi") == "none" and g("p_yoz7", "modal") == "none"
      and g("p_yoz7", "cc") == "none", N.get("p_yoz7"))
check("J14 maydon ichida (fokus) Esc — oyna yopiladi", g("p_nav", "oldin") == "flex" and g("p_nav", "keyin") == "none", N.get("p_nav"))
check("J15 ochiq oyna yo'q — Esc hech narsa qilmaydi (xato yo'q)", g("p_bosh", "modal") == "none" and g("p_bosh", "xo") in ("none", "yoq")
      and g("p_bosh", "cc") == "none", N.get("p_bosh"))

check("J15b maydonda bosib (mousedown) qora fonda qo'yib yuborish (matn belgilash) — oyna YOPILMAYDI",
      g("p_drag", "modal") == "flex" and g("p_drag", "cc") == "none", N.get("p_drag"))

section("J3. Ustma-ust oynalar, ichki panel, sahifa xabar oynasi")
check("J16 Omborxona: chiqim oynasi + ustida kiritish oynasi — Esc FAQAT ustkisini yopdi (kiritish → null)",
      g("i_ust", "oldin") == ["flex", "flex"] and g("i_ust", "cp") == "none" and g("i_ust", "chiqim") == "flex"
      and g("i_ust", "qiymat") is None, N.get("i_ust"))
check("J17 ikkinchi Esc — chiqim oynasi yopildi, so'rov yo'q", g("i_ust2", "chiqim") == "none" and g("i_ust2", "post") == [], N.get("i_ust2"))
check("J18 sahifaning o'z xabar oynasi (invToast) Esc bilan yopiladi", g("i_xabar", "oldin") == "flex" and g("i_xabar", "keyin") == "none",
      N.get("i_xabar"))
check("J18b Ishlab chiqarish (klass bilan ochiladigan oyna): yozilgan ma'lumot — tashqariga bosishda so'raydi, «Yopish» — yopiladi",
      g("m_yoz", "modal") == "flex" and g("m_yoz", "cc") == "flex" and g("m_yoz", "keyin") == "none", N.get("m_yoz"))
check("J19 Ishlab chiqarish: mahsulot turi oynasi (klass bilan ochiladi) Esc — yopildi, yozuv yo'q",
      g("m_esc", "oldin") == "flex" and g("m_esc", "keyin") == "none" and g("m_esc", "post") == [], N.get("m_esc"))
check("J20 Ishlab chiqarish: tashqariga bosish — yopildi", g("m_tash", "keyin") == "none", N.get("m_tash"))
check("J21 Retseptlar: tarkib tanlash paneli ochiq — Esc AVVAL panelni yopdi, oyna joyida",
      (g("r_ichki", "oldin") or [None])[0] == "flex" and (g("r_ichki", "oldin") or [None, None])[1] is True
      and g("r_ichki", "panel") is False and g("r_ichki", "oyna") == "flex", N.get("r_ichki"))
check("J22 keyingi Esc — oyna yopildi", g("r_ichki2", "oyna") == "none", N.get("r_ichki2"))

_st = N.get("s_tartib") or {}
check("J22b eng ustki — z-index bo'yicha (hujjat boshidagi z 5000 avval, keyin z 1000)",
      _st.get("t1") == ["none", "flex"] and _st.get("t2") == ["none", "none"], (_st.get("t1"), _st.get("t2")))
check("J22c z-index teng — hujjatda KEYINGISI avval yopiladi", _st.get("t3") == ["flex", "none"] and _st.get("t4") == ["none", "none"],
      (_st.get("t3"), _st.get("t4")))
check("J22d o'z Esc ishlovchili oyna (data-esc-ozi) ustida turganda global Esc ostidagi oynaga TEGMAYDI; u yopilgach — yopadi",
      _st.get("t5") == ["flex", "flex"] and _st.get("t6") == "none", (_st.get("t5"), _st.get("t6")))
check("J22e oyna ichidagi (pastroq qatlamdagi) ichki qoplamaning belgisi — oynaning o'z yopish tugmasi EMAS",
      _st.get("t7") == ["none", "block"] and "sN" not in (_st.get("yopildi") or []), (_st.get("t7"), _st.get("yopildi")))
check("J22f ustki oyna ochiq turganda pastki oynaning foniga bosish — hech narsa yopilmaydi", _st.get("t8") == ["flex", "flex"],
      _st.get("t8"))
check("J22g ro'yxatdan TANLASH ham «yozilgan» hisoblanadi — tashqariga bosishda so'raydi; «Yopish» — yopiladi",
      _st.get("t9") == ["flex", "flex"] and _st.get("t10") == "none", (_st.get("t9"), _st.get("t10")))

check("J22h ko'rinmaydigan va bosilmaydigan qoplama (telefondagi yopiq menyu foni: opacity 0, pointer-events none) «ochiq» "
      "hisoblanmaydi — Esc ostidagi haqiqiy oynani yopadi (kech118 1-varianti: telefonda 37 oyna yopilmasdi)",
      _st.get("t11") == ["flex", "none"] and "sH" not in (_st.get("yopildi") or []), (_st.get("t11"), _st.get("yopildi")))

section("J4. Kiritish oynasi (prompt o'rniga)")
check("J23 «Hammasini o'chirish»: tasdiqdan keyin so'z — DASTUR oynasida (xom prompt chaqirilmadi), namuna «HAMMASINI-OCHIR»",
      g("u_reset", "ki") == "flex" and g("u_reset", "xom") == 0 and "AYNAN" in (g("u_reset", "sarlavha") or "")
      and g("u_reset", "izoh") == "HAMMASINI-OCHIR", N.get("u_reset"))
check("J24 noto'g'ri so'z — «So'z mos kelmadi — hech narsa o'chirilmadi» (dastur oynasida), so'rov YO'Q",
      g("u_reset2", "ki") == "none" and g("u_reset2", "xo") == "flex" and "mos kelmadi" in (g("u_reset2", "matn") or "")
      and g("u_reset2", "post") == [], N.get("u_reset2"))
check("J25 so'z oynasida Esc — bekor, so'rov YO'Q", g("u_reset3", "ki") == "none" and g("u_reset3", "post") == [], N.get("u_reset3"))
check("J26 Qarzdorlar «tez to'lash»: dastur oynasi, qiymat — qarz summasi, tugma «To'lovni yozish» (asl: xom prompt)",
      g("d_pay", "ki") == "flex" and g("d_pay", "xom") == 0 and "Arenda" in (g("d_pay", "sarlavha") or "")
      and (g("d_pay", "qiymat") or "").replace(" ", "").replace(" ", "") == "150000" and g("d_pay", "ok") == "To'lovni yozish",
      N.get("d_pay"))
check("J27 «Bekor» — so'rov yo'q", g("d_pay2", "ki") == "none" and g("d_pay2", "post") == [], N.get("d_pay2"))
check("J28 0 summa — «Summa noto'g'ri» xabari (dastur oynasi), so'rov yo'q", g("d_pay3", "post") == [] and g("d_pay3", "xo") == "flex"
      and "noto'g'ri" in (g("d_pay3", "matn") or ""), N.get("d_pay3"))
_p4 = g("d_pay4", "post") or []
check("J29 «120 000» — BITTA POST /api/finance/transactions, summa 120000, kategoriya arenda",
      len(_p4) == 1 and _p4[0][0] == "POST /api/finance/transactions" and json.loads(_p4[0][1] or "{}").get("amount") == 120000
      and json.loads(_p4[0][1] or "{}").get("category") == "arenda", _p4)
check("J30 Telegram botni tozalash: dastur tasdiq oynasi (xom confirm EMAS); «Bekor» — so'rov yo'q",
      g("l_tg", "cc") == "flex" and g("l_tg", "post") == [] and g("l_tg", "xom") == 0, N.get("l_tg"))
_q1, _q2 = g("s_tahrir", "q1") or [], g("s_tahrir", "q2") or []
check("J31 Ta'minotchi xaridi tahriri: 1-qadam «Miqdor» (4), 2-qadam narx (12 500) — dastur oynasida; Esc — bekor, so'rov yo'q",
      len(_q1) == 3 and _q1[0] == "flex" and _q1[1] == "Miqdor" and _q1[2] == "4" and len(_q2) == 3 and _q2[0] == "flex"
      and "narxi" in _q2[1] and _q2[2].replace(" ", "").replace(" ", "") == "12500" and g("s_tahrir", "ki") == "none"
      and g("s_tahrir", "post") == [] and g("s_tahrir", "xom") == 0, N.get("s_tahrir"))
_fq = g("f_narx", "q") or []
check("J32 Tayyor mahsulot narxi: dastur oynasi (sarlavha — birlik bilan, izoh — mahsulot nomi, qiymat 45 000); Bekor — so'rov yo'q",
      len(_fq) == 4 and _fq[0] == "flex" and "metr" in _fq[1] and _fq[2] == "B118 Karniz"
      and _fq[3].replace(" ", "").replace(" ", "") == "45000" and g("f_narx", "post") == [] and g("f_narx", "xom") == 0, N.get("f_narx"))

section("X. Xatolar")
check("X1 sahifa JS xatosi yo'q, 5xx yo'q", not NAT.get("xato") and not NAT.get("api_xato"), (NAT.get("xato"), NAT.get("api_xato")))
_5xx = [x for x in HOLATLAR if x[1] >= 500]
check("X2 API 5xx yo'q", not _5xx, _5xx[:5])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
