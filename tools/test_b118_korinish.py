#!/usr/bin/env python3
"""
test_b118_korinish.py — kech118, B bosqichi 2-qism: YAGONA KO'RINISH — o'qiladigan rang va yozuv o'lchami, raqam / sana /
birlik yozilishi, inglizcha va xom so'zlar.

NIMA UCHUN KERAK (audit kech114 — O'LCHANGAN; asl kod = `staging` 1c5408e + zip 117; HAQIQIY brauzer, 20 sahifa)
  U-03  xira yozuv: 809 joy 4.5:1 dan past (umumiy `--text3` #9A9DA6 — 2.7:1, 208 joy; qattiq yozilgan #9CA3AF, #aaa, #bbb,
        yashil #22C55E, sariq #F59E0B, oltin #B9783F …).
  U-04  mayda yozuv: 441 joy 12 px dan kichik (menyu bo'limlari 10 px, jadval sarlavhasi 11 px, belgilar 9–10 px).
  U-05  kasr «1.0 mln», «354.0 kg», «-156.4%» (nuqta) — boshqa joyda vergul; sana «2026-09-29», «2026 M09 29» (brauzer tiliga
        bog'liq); birlik «m2» / «m²».
  U-06  «draft», «product», «transport_kirim», «Top …», grafik oylari «Sep 2026».
QOIDA: `static/style.css` o'zgaruvchilari (`--text2`, `--text3`, `--gold-dark`); son — `base.html` `sonKor` / `foizKor` /
  `qisqaSumma` va shablonda `|son` filtri (ming — bo'sh joy, kasr — vergul); sana — `tkSana` / `tkVaqt` / `tkToliq` ('uz' —
  qo'lda, brauzerga bog'liq emas); birlik — `birlikKor`; server matni — `services._son_uz`, oy — `services._OY_QISQA`.
BO'LIMLAR: S — statik (uslub fayli va shablonlar); H — server (filtr, sahifa HTML, API matnlari); J — HAQIQIY server + jsdom
  (yordamchilar, Moliya, Bosh sahifa, Hisobotlar, Ishlab chiqarish); X — JS xatolari / 5xx.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI.
ISHLATISH: NODE_PATH=$(npm root -g) python3 tools/test_b118_korinish.py
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
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "b118_korinish_test"
_T = tempfile.mkdtemp(prefix="b118k_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'b118_korinish_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Inventory, ExpenseTransaction, Recipe, RecipeIngredient)   # noqa: E402
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


def lum(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g_, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4      # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g_) + 0.0722 * f(b)


def kontrast(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


CSS = open(os.path.join(ROOT, "static", "style.css"), encoding="utf-8").read()
TPL = {os.path.basename(f): open(f, encoding="utf-8").read() for f in sorted(glob.glob(os.path.join(ROOT, "templates", "*.html")))}

section("S. Statik — uslub fayli va shablonlar")
_root = CSS[CSS.find(":root"): CSS.find("}", CSS.find(":root"))]
_lg = re.search(r"--text3:\s*(#[0-9A-Fa-f]{6})", TPL.get("login.html", ""))


def ozg(nom):
    m = re.search(r"--" + nom + r":\s*(#[0-9A-Fa-f]{6})", _root)
    return m.group(1) if m else None


FONLAR = ["#ffffff", "#F8F8F6", "#FAF7F2", "#F8F2EB"]
_t2, _t3, _gd = ozg("text2"), ozg("text3"), ozg("gold-dark")
check("S1 `--text3` (yordamchi yozuv) och fonlarda ≥ 4.4:1, oq fonda ≥ 4.5:1 (asl #9A9DA6 — 2.4–2.7:1)",
      _t3 and kontrast(_t3, "#ffffff") >= 4.5 and all(kontrast(_t3, b) >= 4.4 for b in FONLAR),
      (_t3, [round(kontrast(_t3, b), 2) for b in FONLAR] if _t3 else None))
check("S2 `--text2` hamma och fonda ≥ 4.5:1 va `--text3` dan to'qroq (ierarxiya saqlanadi)",
      _t2 and _t3 and all(kontrast(_t2, b) >= 4.5 for b in FONLAR) and lum(_t2) < lum(_t3),
      (_t2, [round(kontrast(_t2, b), 2) for b in FONLAR] if _t2 else None))
check("S3 `--gold-dark` (oltin matn) hamma och fonda ≥ 4.5:1 (asl #A86B36 — oltin fonda 3.9:1)",
      _gd and all(kontrast(_gd, b) >= 4.5 for b in FONLAR), (_gd, [round(kontrast(_gd, b), 2) for b in FONLAR] if _gd else None))
check("S3b kirish sahifasi `--text3` (izoh «Davom etish uchun …») ≥ 4.5:1 (asl #9A9DA6 — 2.6)",
      _lg is not None and kontrast(_lg.group(1), "#faf9f7") >= 4.5, _lg.group(1) if _lg else None)
_mayda_css = re.findall(r"font-size:\s*(?:[0-9]|1[01])(?:\.\d+)?px", CSS)
check("S4 style.css da 12 px dan kichik yozuv YO'Q (asl: menyu bo'limlari 10 px, jadval sarlavhasi 11 px …)", not _mayda_css,
      _mayda_css[:10])
_KIRISH = set()     # kirish sahifalari ham (kech118: login --text3, hodim kirishi maydon yorlig'i)
_mayda_tpl = []
for fn, src in TPL.items():
    if fn in _KIRISH:
        continue
    for m in re.finditer(r"font-size\s*:\s*((?:[0-9]|1[01])(?:\.\d+)?)px", src):
        _mayda_tpl.append(f"{fn}:{src[:m.start()].count(chr(10)) + 1} {m.group(0)}")
check("S5 shablonlarda (kirish sahifalari ham) 12 px dan kichik yozuv YO'Q (asl: 252 joy)", not _mayda_tpl, _mayda_tpl[:10])
_XIRA = ("#bbb", "#bbbbbb", "#aaa", "#aaaaaa", "#999", "#999999", "#9ca3af", "#888", "#888888", "#777", "#777777", "#b8b2a5",
         "#94a3b8", "#9a9da6", "#22c55e", "#16a34a", "#f59e0b", "#d97706", "#ef4444", "#ea580c", "#b9783f", "#a86b36", "#b7770d")
_xira_tpl = []
for fn, src in TPL.items():
    if fn in _KIRISH:
        continue
    for i, ln in enumerate(src.split("\n"), 1):
        if any(q in ln for q in ("batchSellBar", "background:#0F172A", "background:#111", "background:var(--dark)", "background:#181B22")):
            continue
        for m in re.finditer(r"(?<![-\w])color\s*:\s*(#[0-9a-fA-F]{3,6})\b", ln):
            if m.group(1).lower() in _XIRA:
                _xira_tpl.append(f"{fn}:{i} {m.group(0)}")
check("S6 shablonlarda och fondagi xira matn rangi (kulrang #9CA3AF / #aaa / #bbb …, yashil #22C55E, sariq #F59E0B, oltin "
      "#B9783F …) YO'Q — o'rniga `var(--text3)` / to'q tuslar (asl: ~600 joy)", not _xira_tpl, _xira_tpl[:10])
_toplam = []
for fn, pre in (("finance.html", "f"), ("reports.html", "b"), ("debts.html", "d"), ("supplier_receive.html", "r")):
    for nom in ("text2", "text3", "success", "danger", "warning"):
        m = re.search(r"--" + pre + "-" + nom + r":\s*(#[0-9A-Fa-f]{6})", TPL.get(fn, ""))
        if m and kontrast(m.group(1), "#ffffff") < 4.5:
            _toplam.append(f"{fn} --{pre}-{nom} {m.group(1)} {kontrast(m.group(1), '#ffffff'):.2f}")
check("S6b sahifalarning o'z ranglar to'plami (Moliya --f-*, Hisobotlar --b-*, Qarzdorlar --d-*, Kirim --r-*): matn / holat "
      "tuslari oq fonda ≥ 4.5:1 (asl: --x-text3 #9CA3AF 2.5, --x-success #22C55E 2.3, --x-warning #F59E0B 2.2)", not _toplam, _toplam)


def klass_rang(sel, xos):
    # kech118 (zip 122 — tungi rejim, MOSLANDI): rang umumiy ro'yxatdan ham (var(--m-15803d) — yorug' rejimda #15803D)
    m = re.search(re.escape(sel) + r"\s*\{[^}]*?" + xos + r":\s*(#[0-9A-Fa-f]{6}|var\(--(?:f|m|ch|doim)-[0-9a-f]{6}\))", CSS)
    if not m:
        return None
    return m.group(1) if m.group(1).startswith("#") else "#" + m.group(1)[-7:-1].upper()


_kl = {"text-green": klass_rang(".text-green", "color"), "text-red": klass_rang(".text-red", "color"),
       "btn-green": klass_rang(".btn-green", "background"), "btn-red": klass_rang(".btn-red", "background"),
       "nav-active": klass_rang(".nav-item.active .n-txt", "color")}
check("S6c yashil / qizil matn ≥ 4.5:1, yashil / qizil tugmada oq yozuv ≥ 4.5:1, menyudagi faol band (qorong'i fon #322A27) ≥ 4.5:1",
      all(_kl.values()) and kontrast(_kl["text-green"], "#ffffff") >= 4.5 and kontrast(_kl["text-red"], "#ffffff") >= 4.5
      and kontrast("#ffffff", _kl["btn-green"]) >= 4.5 and kontrast("#ffffff", _kl["btn-red"]) >= 4.5
      and kontrast(_kl["nav-active"], "#322A27") >= 4.5, _kl)
_b, _h = TPL.get("base.html", ""), TPL.get("hodim_panel.html", "")
_tk = lambda s: s[s.find("function tkMs("): s.find("function tkHozir(")]          # noqa: E731
check("S7 Toshkent vaqti yordamchilari base.html va hodim_panel.html da AYNAN bir xil", _tk(_b) and _tk(_b) == _tk(_h),
      (len(_tk(_b)), len(_tk(_h))))
# kech118 (U-03, 2-o'tish): oq yozuvli oltin tugma / belgi — `--gold-btn`; sahifa to'plamlaridagi `--*-primary` — matn ham, tugma ham
_gb = re.search(r"--gold-btn:\s*(#[0-9A-Fa-f]{6})", CSS)
_pr = {n: re.search(r"--" + n + r"-primary:\s*(#[0-9A-Fa-f]{6})", TPL.get(f, "")) for n, f in
       (("f", "finance.html"), ("r", "supplier_receive.html"), ("b", "reports.html"), ("d", "debts.html"))}
_oq_oltin = []
for _fn, _src in list(TPL.items()) + [("style.css", CSS)]:
    for _m in re.finditer(r"background(?:-color)?:\s*(?:var\(--gold\)|#B9783F|#b9783f)\s*;[^\"'}]{0,40}?(?<![-\w])color:\s*(?:#fff\b|#ffffff|var\(--white\))", _src):
        _oq_oltin.append((_fn, _src.count("\n", 0, _m.start()) + 1))
check("S9b oq yozuvli oltin fon YO'Q (asl #B9783F — 3.6:1); `--gold-btn` oq yozuv bilan ≥ 4.5:1; Moliya / Kirim / Hisobotlar / "
      "Qarzdorlar `--*-primary` oq va och oltin fonda ≥ 4.5:1",
      not _oq_oltin and _gb and kontrast("#ffffff", _gb.group(1)) >= 4.5
      and all(m and kontrast(m.group(1), "#ffffff") >= 4.5 and kontrast(m.group(1), "#F8F2EB") >= 4.5 for m in _pr.values()),
      (_oq_oltin[:6], _gb and _gb.group(1), {k: m and m.group(1) for k, m in _pr.items()}))
check("S8 base.html: `sonKor`, `foizKor`, `birlikKor` bor; `qisqaSumma` — vergul", "function sonKor(" in _b and "function foizKor(" in _b
      and "function birlikKor(" in _b and ".toFixed(1).replace('.', ',') + ' mln'" in _b, "")

section("H. Server — filtr, sahifa HTML, API matnlari")
_sf = getattr(main, "_son_filtri", None)
_H1 = [(354.0, 2, "354"), (8.3, 2, "8,3"), (1234.5, 2, "1 234,5"), (1234567.891, 2, "1 234 567,89"), (-0.0, 2, "0"),
       (-0.004, 2, "0"), (None, 2, "—"), ("abc", 2, "—"), (float("inf"), 2, "—"), (12.34, 0, "12"), (-156.44, 1, "-156,4"),
       (0.5, 1, "0,5"), ("7.25", 2, "7,25")]
_h1 = [(a, k, e, _sf(a, k) if _sf else None) for a, k, e in _H1]
check("H1 Jinja `|son` filtri: «354», «8,3», «1 234,5», «-156,4», manfiy nol — «0», son emas — «—»; ming ajratgich — NBSP",
      _sf is not None and all(x[2] == (x[3] or "").replace("\u00a0", " ") for x in _h1) and "\u00a0" in (_sf(1234.5, 2) or ""),
      [x for x in _h1 if x[2] != (x[3] or "").replace("\u00a0", " ")])
check("H2 filtr shablonlarda ro'yxatdan o'tgan", "son" in main.templates.env.filters, "")
_su = getattr(services, "_son_uz", None)
check("H3 `services._son_uz`: -156.4 → «-156,4», 12.0 → «12», 0.35 → «0,35»",
      _su is not None and _su(-156.4) == "-156,4" and _su(12.0) == "12" and _su(0.35) == "0,35", _su and [_su(-156.4), _su(12.0)])

s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "b118k_admin", "Parol123!", UserRole.ADMIN, "B118K Admin", company_id=1)
INV = Inventory(company_id=1, item_name="B118K Kley", unit="kg", stock_quantity=8.3, price_per_unit=12000, category="Kimyoviy")
INV2 = Inventory(company_id=1, item_name="B118K Qum", unit="kg", stock_quantity=1234.5, price_per_unit=500, category="Kimyoviy")
s.add_all([INV, INV2])
s.flush()
RCP = Recipe(company_id=1, name="B118K Retsept", batch_size_kg=3.0) if hasattr(Recipe, "batch_size_kg") else None
if RCP is not None:
    s.add(RCP)
    s.flush()
    s.add(RecipeIngredient(recipe_id=RCP.id, inventory_id=INV.id, quantity_kg=1.0))
_bugun = datetime.utcnow()
s.add(ExpenseTransaction(company_id=1, date=_bugun, category="transport_kirim", amount=150000, notes="B118K", source="inventory_receipt"))
s.add(Project(company_id=1, client_name="B118K Mijoz", project_name="B118K loyiha", total_budget=0, total_paid=0))
s.commit()
s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "b118k_admin", "password": "Parol123!"}, follow_redirects=False)
check("H0 login", _lr.status_code in (200, 302, 303), _lr.status_code)
_inv = req(C, "get", "/inventory").text.replace("&nbsp;", " ")
check("H4 Omborxona: qoldiq «8,3 kg» va «1 234,5 kg» (asl: «8.3 kg», «1234.5 kg»)",
      "8,3 kg" in _inv and "1 234,5 kg" in _inv and "8.3 kg" not in _inv, [m for m in re.findall(r"[\d.,  ]+ kg", _inv)][:6])
if RCP is not None:
    _rc = req(C, "get", "/recipes").text
    check("H5 Retseptlar: ulush «33,3%» (asl: «33.3%»)", "33,3%" in _rc and "33.3%" not in _rc, re.findall(r"\d+[.,]\d%", _rc)[:4])
else:
    check("H5 Retsept modeli (batch_size_kg) — topildi", False, "Recipe.batch_size_kg yo'q")
_ch = js(req(C, "get", "/api/dashboard/charts"))
_lab = [m.get("label") for m in (_ch.get("months") or [])]
_oy = ("Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek")
check("H6 grafik oylari o'zbekcha («Sen 2026»; asl: «Sep 2026»)", _lab and all(re.fullmatch(r"(" + "|".join(_oy) + r") \d{4}", x or "")
                                                                      for x in _lab), _lab)
_bh = js(req(C, "get", "/api/reports/business-health"))
_sab = json.dumps(_bh.get("sabablar") or {}, ensure_ascii=False)
check("H7 «Korxona sog'ligi» sabablari: son ichida NUQTA yo'q (kasr — vergul)", _bh and not re.search(r"\d\.\d", _sab), _sab[:300])

# ══════════════════════════════════════════════════════════════
# J — HAQIQIY server + jsdom
# ══════════════════════════════════════════════════════════════
NODE_JS = r"""
let JSDOM, VirtualConsole, ResourceLoader;
try { ({ JSDOM, VirtualConsole, ResourceLoader } = require("jsdom")); }
catch (e) { console.log(JSON.stringify({ fatal: "jsdom topilmadi: " + String(e.message).slice(0, 200) })); process.exit(3); }
const base = process.argv[2], cookie = process.argv[3];
const sahifalar = JSON.parse(require("fs").readFileSync(process.argv[4], "utf8"));
const CHART_STUB = "window.Chart = function Chart(ctx, cfg) { this.config = cfg || {}; this.data = (cfg && cfg.data) || {datasets: []}; this.options = (cfg && cfg.options) || {}; window.__grafiklar = (window.__grafiklar || []).concat([cfg]); };" +
  "window.Chart.prototype.destroy = function () {}; window.Chart.prototype.update = function () {}; window.Chart.register = function () {};" +
  "window.Chart.defaults = {font: {}, color: '', plugins: {legend: {labels: {}}, tooltip: {}}};";
class FaqatOzimiz extends ResourceLoader {
  fetch(url, options) {
    if (/chart\.umd(\.min)?\.js/i.test(url)) { const p = Promise.resolve(Buffer.from(CHART_STUB)); p.abort = () => {}; return p; }
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
      w.fetch = async (u, o) => {
        pending++; lastActive = Date.now();
        try {
          o = o || {};
          const h = Object.assign({}, o.headers || {}); h.cookie = cookie;
          const url = new URL(String(u), sahifaUrl).href;
          if (!url.startsWith(base)) throw new Error("tashqi so'rov: " + url);
          const resp = await fetch(url, Object.assign({}, o, { headers: h, redirect: "manual" }));
          if (resp.status >= 500) res.api_xato.push(resp.status + " " + url.slice(base.length, base.length + 120));
          return resp;
        } finally { pending--; lastActive = Date.now(); }
      };
      w.alert = () => {}; w.confirm = () => false; w.prompt = () => null; w.print = () => {}; w.scrollTo = () => {}; w.open = () => null;
      w.matchMedia = () => ({ matches: false, media: "", addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
      class K { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } }
      w.IntersectionObserver = K; w.ResizeObserver = K;
      w.HTMLCanvasElement.prototype.getContext = () => null;
      w.HTMLElement.prototype.scrollIntoView = () => {};
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


M = r"const __m = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : null; const __f = (n, ...a) => (typeof window[n] === 'function') ? window[n](...a) : 'YOQ:' + n;"
YORD = [
    q("tk", natija=M + r"""return {
        sana: __f('tkSana', '2026-09-30T20:30:00'), sana_kun: __f('tkSana', '2026-01-05'),
        uzun: __f('tkSana', '2026-09-30T20:30:00', 'uz', {day: 'numeric', month: 'long', year: 'numeric'}),
        uzun_yilsiz: __f('tkSana', '2026-09-28T10:00:00', 'uz', {day: 'numeric', month: 'long'}),
        vaqt: __f('tkVaqt', '2026-09-30T20:30:00'), sv: __f('tkSanaVaqt', '2026-09-30T20:30:05'),
        toliq: __f('tkToliq', '2026-09-30T20:30:05'), ru: __f('tkSana', '2026-09-30T20:30:00', 'ru-RU'),
        bosh: __f('tkSana', ''), yoq: __f('tkSana', null), notogri: __f('tkSana', 'abc')};"""),
    q("son", natija=M + r"""return {
        a: __f('sonKor', 354), b: __f('sonKor', 8.3), c: __f('sonKor', 1234.5), d: __f('sonKor', 1234567.891),
        e: __f('sonKor', -0.001), f: __f('sonKor', null), g: __f('sonKor', 'abc'), h: __f('sonKor', 0.5, 0), i: __f('sonKor', '7.25'),
        fa: __f('foizKor', -156.44), fb: __f('foizKor', 33.333), fc: __f('foizKor', null), fd: __f('foizKor', 12, 0),
        q1: __f('qisqaSumma', 1000000), q2: __f('qisqaSumma', -2618028), q3: __f('qisqaSumma', 25300000), q4: __f('qisqaSumma', 999.6),
        b1: __f('birlikKor', 'm2'), b2: __f('birlikKor', 'M3'), b3: __f('birlikKor', 'dona'), b4: __f('birlikKor', 'm2 lik'),
        b5: __f('birlikKor', null), b6: __f('birlikKor', 'sm2'),
        r: ['#22C55E', '#16a34a', '#F59E0B', '#D97706', '#EF4444', '#0EA5E9', '#94A3B8', '#9CA3AF', '#B9783F', '#7C3AED', null]
             .map(c => __f('matnRangi', c)),
        rf: ['#22C55E', '#EF4444', '#F59E0B', '#0EA5E9', '#9CA3AF', '#B9783F', '#DB2777', '#7C3AED'].map(c => __f('matnRangi', c, 1))};"""),
]
FIN = [
    q("fin", amal=r"""const d = document.getElementById('tx-date'); if (d) d.value = tkISO(); const w = document.getElementById('tx-whole-month');
        if (w) w.checked = true; if (typeof loadDailyTransactions === 'function') await loadDailyTransactions();""",
      natija=M + r"""const rows = Array.from(document.querySelectorAll('#tx-body tr')).map(tr => __m(tr));
        return {rows: rows, xom: rows.filter(r => /transport_kirim/.test(r)).length,
                sana_iso: rows.filter(r => /\b20\d\d-\d\d-\d\d\b/.test(r)).length};"""),
]
HOME = [
    q("home", natija=M + r"""return {labels: (typeof STATUS_LABELS !== 'undefined') ? STATUS_LABELS : null,
        tur: (typeof TUR_NOMI !== 'undefined') ? TUR_NOMI : null,
        top: Array.from(document.querySelectorAll('.card-head h3')).map(__m),
        fmtM: (typeof fmtM === 'function') ? fmtM(2600000) : null};"""),
]
REP = [
    q("rep", natija=M + r"""return {fmtShort: (typeof fmtShort === 'function') ? [fmtShort(2600000), fmtShort(-1560000), fmtShort(4500)] : null,
        sarlavha: Array.from(document.querySelectorAll('.bi-section-title')).map(__m).filter(t => /reyting/i.test(t)),
        kartalar: Array.from(document.querySelectorAll('.bi-top-grid .bi-card-body > div:first-child')).map(__m)};"""),
]
SAHIFALAR = [{"yol": "/", "qadamlar": YORD + HOME}, {"yol": "/finance", "qadamlar": FIN}, {"yol": "/reports", "qadamlar": REP}]

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
        lr = httpx.post(base + "/login", data={"username": "b118k_admin", "password": "Parol123!"}, follow_redirects=False, timeout=30)
        cookie = "; ".join(hh.split(";")[0] for hh in lr.headers.get_list("set-cookie"))
        pj = os.path.join(_T, "sahifalar.json")
        with open(pj, "w", encoding="utf-8") as f:
            json.dump(SAHIFALAR, f, ensure_ascii=False)
        sj = os.path.join(_T, "b118k.js")
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


def g(nom, kalit=None):
    v = N.get(nom)
    if kalit is None:
        return v
    return v.get(kalit) if isinstance(v, dict) else None


def b(t):
    return str(t or "").replace(" ", " ").replace(" ", " ")


section("J1. Sana va vaqt — brauzer tiliga bog'liq emas")
check("J1 tkSana: «01.10.2026» (Toshkent — UTC 20:30 dan keyingi kun), «05.01.2026» (asl: brauzer tiliga qarab «2026-09-30» / "
      "«01/10/2026»)", g("tk", "sana") == "01.10.2026" and g("tk", "sana_kun") == "05.01.2026", N.get("tk"))
check("J2 oy nomi bilan: «1-oktabr, 2026» va yilsiz «28-sentabr» (asl: «2026 M10 1»)",
      g("tk", "uzun") == "1-oktabr, 2026" and g("tk", "uzun_yilsiz") == "28-sentabr", (g("tk", "uzun"), g("tk", "uzun_yilsiz")))
check("J3 tkVaqt «01:30», tkSanaVaqt «01.10.2026 01:30», tkToliq «01.10.2026, 01:30:05»",
      g("tk", "vaqt") == "01:30" and g("tk", "sv") == "01.10.2026 01:30" and g("tk", "toliq") == "01.10.2026, 01:30:05", N.get("tk"))
check("J4 boshqa til ('ru-RU') — o'zgarmadi «01.10.2026»; bo'sh / yo'q / noto'g'ri — ''",
      g("tk", "ru") == "01.10.2026" and g("tk", "bosh") == "" and g("tk", "yoq") == "" and g("tk", "notogri") == "", N.get("tk"))

section("J2. Son, foiz, qisqa summa, birlik")
check("J5 sonKor: «354», «8,3», «1 234,5», «1 234 567,89»; manfiy nol — «0»; yo'q / son emas — «—»; kasr 0 — «1»; matn «7,25»",
      [b(g("son", k)) for k in "abcdefghi"] == ["354", "8,3", "1 234,5", "1 234 567,89", "0", "—", "—", "1", "7,25"],
      [b(g("son", k)) for k in "abcdefghi"])
check("J6 foizKor: «-156,4%», «33,3%», «—», «12%»", [b(g("son", k)) for k in ("fa", "fb", "fc", "fd")] == ["-156,4%", "33,3%", "—", "12%"],
      [b(g("son", k)) for k in ("fa", "fb", "fc", "fd")])
check("J7 qisqaSumma: «1,0 mln», «-2,6 mln», «25,3 mln», «1 ming» (asl: «1.0 mln»)",
      [g("son", k) for k in ("q1", "q2", "q3", "q4")] == ["1,0 mln", "-2,6 mln", "25,3 mln", "1 ming"], [g("son", k) for k in ("q1", "q2", "q3", "q4")])
check("J8 birlikKor: «m2» → «m²», «M3» → «m³», «sm2» → «sm²»; boshqa matn o'zgarmaydi",
      [g("son", k) for k in ("b1", "b2", "b3", "b4", "b5", "b6")] == ["m²", "m³", "dona", "m2 lik", "", "sm²"],
      [g("son", k) for k in ("b1", "b2", "b3", "b4", "b5", "b6")])

_mr = g("son", "r") or []
check("J8b matnRangi: yorqin holat rangi → to'q tus (#22C55E / #16A34A → #15803D, #F59E0B / #D97706 → #B45309, #EF4444 → #DC2626, "
      "#0EA5E9 → #0369A1, kulrang → #696D78, oltin → #8F5B2A), har biri oq fonda ≥ 4.5:1; boshqa rang o'zgarmaydi",
      _mr[:10] == ["#15803D", "#15803D", "#B45309", "#B45309", "#DC2626", "#0369A1", "#696D78", "#696D78", "#8F5B2A", "#7C3AED"]
      and len(_mr) == 11 and _mr[10] is None and all(kontrast(c, "#ffffff") >= 4.5 for c in _mr[:9]), _mr)
_mrf = g("son", "rf") or []
_TINT = ("#FEF2F2", "#F0FDF4", "#FFFBEB", "#EBF8FD", "#F8F2EB", "#FDF2F8", "#E2F7EA", "#F0EBE0")
check("J8b2 matnRangi(c, fon) — och rangli fon ustida yanada to'q (#166534, #B91C1C, #92400E, #075985, #5B6170, #7A4D23, #9D174D): "
      "hamma och fonda ≥ 4.5:1; noma'lum rang o'zgarmaydi",
      _mrf == ["#166534", "#B91C1C", "#92400E", "#075985", "#5B6170", "#7A4D23", "#9D174D", "#7C3AED"]
      and all(kontrast(c, t) >= 4.5 for c in _mrf[:7] for t in _TINT), _mrf)
_fin_t, _dash_t = TPL.get("finished.html", ""), TPL.get("dashboard.html", "")
check("J8c yozuvga holat rangi `matnRangi` orqali: Tayyor mahsulotlar qoldig'i (4 joy, belgida — fon ustidagi tus), Dashboard "
      "ombor qoldig'i, qarzlar holati va majburiyatlar belgisi",
      # kech118 (D-1, G5-11): qoldiq rangi — faqat holat ko'rinsa (chegara yozilgan / tugagan), aks holda oddiy matn rangi
      _fin_t.count("? matnRangi(stColor) : 'var(--text)'}") == 2 and _fin_t.count("color:${matnRangi(stColor, 1)}") == 2
      # kech118 (zip 124 — G1-09, MOSLANDI): Dashboard «Ombor ogohlantirishlari» (matnRangi(st.color)) olib tashlandi — kam
      # qoldiq Bosh sahifada (`kamQoldiqHtml` — matnRangi(color), test_kam_qoldiq_ui)
      and "matnRangi(st.color)" not in _dash_t and "color:${matnRangi(s[2])}" in _dash_t and "color:${matnRangi(badgeColor, 1)}" in _dash_t,
      (_fin_t.count("? matnRangi(stColor) : 'var(--text)'}"), _fin_t.count("color:${matnRangi(stColor, 1)}"), "matnRangi(st.color)" in _dash_t))

section("J3. Sahifalar")
_fr = g("fin", "rows") or []
check("J9 Moliya kunlik ro'yxat: kirim xarajati «Transport (kirim)» (xom «transport_kirim» YO'Q), sana ISO emas",
      _fr and g("fin", "xom") == 0 and g("fin", "sana_iso") == 0 and any("Transport (kirim)" in r for r in _fr), _fr[:3])
_lb = g("home", "labels") or {}
check("J10 Bosh sahifa holat nomlari: qoralama «Qoralama», qoplamada «Qoplamada» (asl: «draft»)",
      _lb.get("draft") == "Qoralama" and _lb.get("coating") == "Qoplamada", _lb)
# kech118 (zip 124 — G1-09, MOSLANDI): «Eng faol ustalar» Bosh sahifadan olib tashlandi (Dashboard «Usta reytingi» bilan takror)
check("J11 Bosh sahifa: buyurtma turi «Mahsulot» / «Xizmat» (asl: «product»), «Eng faol ustalar» YO'Q (Dashboard «Usta reytingi» da), "
      "«2,6 mln»", (g("home", "tur") or {}).get("product") == "Mahsulot" and "Eng faol ustalar" not in (g("home", "top") or [])
      and "Bugungi vazifalar" in (g("home", "top") or [])
      and g("home", "fmtM") == "2,6 mln", (g("home", "tur"), g("home", "top"), g("home", "fmtM")))
check("J12 Hisobotlar: «2,6 mln», «-1,6 mln», «5 ming»; «Reytinglar», kartalarda «Top» so'zi YO'Q",
      [b(x) for x in (g("rep", "fmtShort") or [])] == ["2,6 mln", "-1,6 mln", "5 ming"] and g("rep", "sarlavha")
      and not any("Top" in (x or "") for x in (g("rep", "kartalar") or []) + (g("rep", "sarlavha") or [])),
      (g("rep", "fmtShort"), g("rep", "sarlavha"), g("rep", "kartalar")))

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
