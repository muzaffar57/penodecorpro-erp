#!/usr/bin/env python3
"""
test_a115_korinish.py — kech115, A bosqich, ko'rinish guruhi: G3-10 / G1-04 (manfiy raqamlar), G1-01 (o'tgan oy 0 —
«100 % oshdi»), G1-06 («Korxona sog'ligi»), G4-06 («Kam» filtri). Server funksiyalari + HAQIQIY sahifalar (jsdom, uvicorn).

NIMA UCHUN KERAK (audit kech114 — O'LCHANGAN, asl kod = `staging` d1ba2b0)
  G3-10 / G1-04  Moliya «Pul oqimi» minusni tashlardi (`Math.abs`), zarar oyida sof foyda «−2618028 so'm» (ajratgichsiz),
                 manfiy rentabellik YASHIL; Dashboard — xuddi shunday.
  G1-01          O'tgan oy 0 bo'lsa `change_pct` DOIM 100.0 — zarar oyida «Sof foyda 100 % oshdi»; ikkalasi 0 — «0 % oshdi»;
                 kartada xarajat o'sishi yashil, pastda qizil.
  G1-06          «Ombor» va «Ishlab chiqarish» kodda DOIM yashil; bo'sh korxonaga birinchi kuni qizil «Rentabellik».
  G4-06          Omborxona «Kam» filtri faqat «Oz» larni ko'rsatardi, «Kam!» lar «Tugagan» da; karta soni bilan mos emas.
  (kech116) K115-2  «Korxona sog'ligi» sababi holatdan qat'i nazar «(yaxshi — 15 % dan yuqori)» derdi (qizil kartada);
                    qarz sababida chegara yo'q edi. Endi matn holatga qarab (yaxshi / o'rtacha / past, chegara bilan) — H8–H10.
  (kech116) K115-3  Ogohlantirish bo'lmasa «Bugungi xulosa» umuman yig'ilmasdi (zarar oyida ham yashirin) — R10 / R11.
BO'LIMLAR: C — taqqoslash (server); H — sog'liq (server); R / I / F / D — Hisobotlar / Omborxona / Moliya / Dashboard
           sahifalari (jsdom); X — xatolar.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI.
ISHLATISH: NODE_PATH=$(npm root -g) python3 tools/test_a115_korinish.py
"""
import os
import sys
import json
import time
import socket
import shutil
import tempfile
import threading
import subprocess
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "a115_korinish_test"
_T = tempfile.mkdtemp(prefix="a115k_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'a115_korinish_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import services                                    # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import UserRole, Inventory, Project, Order, ExpenseTransaction   # noqa: E402
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
        print(f"  ✗ {label}   {str(detail)[:500]}")


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


# ══════════════════════════════════════════════════════════════
section("C. Taqqoslash — G1-01 (server)")
# ══════════════════════════════════════════════════════════════
_asl_report = services.get_monthly_report
BUGUN = tashkent_date()


def _soxta(joriy, otgan):
    def f(db, year, month, company_id=None):
        return joriy if (year, month) == (BUGUN.year, BUGUN.month) else otgan
    return f


def taqqos(joriy, otgan):
    services.get_monthly_report = _soxta(joriy, otgan)
    try:
        return services.get_monthly_comparison(None, BUGUN.year, BUGUN.month, company_id=1)
    except Exception as e:                 # noqa: BLE001
        return {"XATO": repr(e)}
    finally:
        services.get_monthly_report = _asl_report


_c = taqqos({"daromad": 1674000, "jami_xarajat": 3291802, "sof_foyda": -2618028, "foyda_foiz": -156.4},
            {"daromad": 0, "jami_xarajat": 0, "sof_foyda": 0, "foyda_foiz": 0})
check("C1 o'tgan oy 0 → foiz YO'Q (asl: 100.0), holat «malumot_yoq» (daromad, xarajat, sof foyda, rentabellik)",
      all((_c.get(k) or {}).get("change_pct", "x") is None and (_c.get(k) or {}).get("holat") == "malumot_yoq"
          for k in ("daromad", "jami_xarajat", "sof_foyda", "foyda_foiz")), _c)
_c = taqqos({"daromad": 0, "jami_xarajat": 0, "sof_foyda": 0, "foyda_foiz": 0},
            {"daromad": 0, "jami_xarajat": 0, "sof_foyda": 0, "foyda_foiz": 0})
check("C2 ikkalasi 0 → «ozgarmadi», foiz yo'q (asl: 0.0 — sahifada «0% oshdi»)",
      all((_c.get(k) or {}).get("holat") == "ozgarmadi" and (_c.get(k) or {}).get("change_pct", "x") is None
          for k in ("daromad", "sof_foyda")), _c)
_c = taqqos({"daromad": 150, "jami_xarajat": 90, "sof_foyda": -50, "foyda_foiz": 10},
            {"daromad": 100, "jami_xarajat": 100, "sof_foyda": 100, "foyda_foiz": 10})
check("C3 oddiy holat: +50 % oshdi, −10 % kamaydi, −150 % kamaydi, o'zgarmadi",
      (_c.get("daromad") or {}).get("change_pct") == 50.0 and _c["daromad"].get("holat") == "oshdi"
      and _c["jami_xarajat"].get("change_pct") == -10.0 and _c["jami_xarajat"].get("holat") == "kamaydi"
      and _c["sof_foyda"].get("change_pct") == -150.0 and _c["sof_foyda"].get("holat") == "kamaydi"
      and _c["foyda_foiz"].get("holat") == "ozgarmadi", _c)

# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k115_admin", "Parol123!", UserRole.ADMIN, "K115 Admin", company_id=1)
MAT = [("K115 Tugagan A", 0, 10), ("K115 Tugagan B", -2, 0), ("K115 Kam C", 5, 10), ("K115 Oz D", 14, 10),
       ("K115 Yetarli E", 100, 10), ("K115 Yetarli F", 50, 0)]
for nom, q, mn in MAT:
    s.add(Inventory(company_id=1, item_name=nom, unit="kg", stock_quantity=q, min_stock=mn, price_per_unit=1000,
                    is_penoplast=False, category="Kimyoviy qo'shimchalar"))
s.add(Inventory(company_id=1, item_name="Tayyor loy (K115)", unit="kg", stock_quantity=0, min_stock=0,
                price_per_unit=0, is_penoplast=False, category="Boshqa"))
PENO = Inventory(company_id=1, item_name="K115 Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
s.add(PENO)
PRJ = Project(company_id=1, client_name="K115 Mijoz", project_name="K115 loyiha", total_budget=0, total_paid=0)
s.add(PRJ)
s.commit()
PENO_ID, PRJ_ID = PENO.id, PRJ.id
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "k115_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _lr.status_code in (200, 302, 303), _lr.status_code)


def buyurtma(nom, muddat_kun):
    r = req(C, "post", "/api/orders", json={
        "project_id": PRJ_ID, "order_type": "product", "deadline": (BUGUN + timedelta(days=muddat_kun)).isoformat(),
        "items": [{"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 100, "quantity": 2,
                   "unit_price": 10000, "is_coated": False, "penoplast_id": PENO_ID}]})
    return r.status_code


def sogliq(cid=1):
    s = SessionLocal()
    try:
        return services.get_business_health(s, company_id=cid)
    except Exception as e:                 # noqa: BLE001
        return {"XATO": repr(e)}
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════
section("H. Korxona sog'ligi — G1-06 (server)")
# ══════════════════════════════════════════════════════════════
h = sogliq(2)
check("H1 bo'sh korxona → hamma ko'rsatkich «gray» (ma'lumot yetarli emas), sababi bilan (asl: rentabellik qizil)",
      all(h.get(k) == "gray" for k in ("pul_oqimi", "ombor", "rentabellik", "qarzdorlik", "ishlab_chiqarish", "material_sarfi"))
      and isinstance(h.get("sabablar"), dict) and h["sabablar"].get("ombor") == "Omborda material yo'q", h)
h = sogliq(1)
check("H2 ombor: 2 ta tugagan, 1 ta kam → «red», «2 ta material tugagan, 1 tasi kam» (asl: doim green); Tayyor loy — sanalmaydi",
      h.get("ombor") == "red" and (h.get("sabablar") or {}).get("ombor") == "2 ta material tugagan, 1 tasi kam", h)
check("H3 ishlab chiqarish: jarayondagi buyurtma yo'q → «gray»", h.get("ishlab_chiqarish") == "gray", h)
_st = [buyurtma("K115 O1", 3), buyurtma("K115 O2", 4)]
h = sogliq(1)
check("H4 2 buyurtma, muddati o'tmagan → «green»", _st == [200, 200] and h.get("ishlab_chiqarish") == "green"
      and "2 ta buyurtma" in (h.get("sabablar") or {}).get("ishlab_chiqarish", ""), (_st, h))
s = SessionLocal()
_ord = s.query(Order).filter(Order.project_id == PRJ_ID).order_by(Order.id).all()
_ord[0].deadline = datetime.utcnow() - timedelta(days=3)
s.commit()
s.close()
h = sogliq(1)
check("H5 1 ta muddati o'tgan → «orange» (sabab: «1 ta buyurtmaning muddati o'tgan (2 tadan)»)",
      h.get("ishlab_chiqarish") == "orange"
      and (h.get("sabablar") or {}).get("ishlab_chiqarish") == "1 ta buyurtmaning muddati o'tgan (2 tadan)", h)
_st = [buyurtma("K115 O3", 1), buyurtma("K115 O4", 1)]
s = SessionLocal()
for o in s.query(Order).filter(Order.project_id == PRJ_ID).all():
    o.deadline = datetime.utcnow() - timedelta(days=2)
s.commit()
s.close()
h = sogliq(1)
check("H6 4 ta muddati o'tgan → «red»", h.get("ishlab_chiqarish") == "red", h)
s = SessionLocal()
for it in s.query(Inventory).filter(Inventory.item_name.in_(["K115 Tugagan A", "K115 Tugagan B"])).all():
    it.stock_quantity = 100
s.commit()
s.close()
h = sogliq(1)
check("H7 tugaganlar to'ldirildi → ombor «orange», «1 ta material kam qolgan»",
      h.get("ombor") == "orange" and (h.get("sabablar") or {}).get("ombor") == "1 ta material kam qolgan", h)
s = SessionLocal()
for it in s.query(Inventory).filter(Inventory.item_name.in_(["K115 Tugagan A", "K115 Tugagan B"])).all():
    it.stock_quantity = 0 if it.item_name.endswith("A") else -2
s.commit()
s.close()
# bitta buyurtma «Tayyor» — shu oy daromad (20 000) bor, rentabellik manfiy bo'ladi; faol muddati o'tgan — 3 ta
s = SessionLocal()
_o1 = s.query(Order).filter(Order.project_id == PRJ_ID).order_by(Order.id).first().id
s.close()
_rdy = req(C, "post", f"/api/orders/{_o1}/ready")
check("0 bitta buyurtma «Tayyor» (daromad)", _rdy.status_code == 200, (_rdy.status_code, getattr(_rdy, "text", "")[:200]))
# Moliya — zarar (xarajat 3 000 000 bugun) → sahifalarda manfiy
s = SessionLocal()
s.add(ExpenseTransaction(company_id=1, date=datetime.utcnow(), category="arenda", amount=3000000, notes="K115 arenda",
                         created_by="K115"))
s.commit()
s.close()
_rep = js(req(C, "get", f"/api/finance/report?year={BUGUN.year}&month={BUGUN.month}"))
check("0 moliya: shu oy sof foyda manfiy (zarar)", float(_rep.get("sof_foyda", 0) or 0) < 0, _rep.get("sof_foyda"))

# kech116 (K115-2): sabab matni holatga qarab
import re as _re_k1152                             # noqa: E402
h = sogliq(1)
_rs = (h.get("sabablar") or {}).get("rentabellik", "")
check("H8 (K115-2) zarar oyi: rentabellik «red», sabab «… — past (5 % dan kam)», «yaxshi» so'zi YO'Q "
      "(asl: «(yaxshi — 15 % dan yuqori)»)", h.get("rentabellik") == "red" and _rs.startswith("Rentabellik -")
      and _rs.endswith(" % — past (5 % dan kam)") and "yaxshi" not in _rs, h)


def sogliq_soxta(foiz, daromad=1000000):
    services.get_monthly_report = lambda db, y, m, company_id=None: {
        "foyda_foiz": foiz, "daromad": daromad, "sof_foyda": 1, "jami_xarajat": 1, "naqd_xarajat_jami": 0}
    try:
        return sogliq(1)
    finally:
        services.get_monthly_report = _asl_report


_REN = {"green": "yaxshi (15 % va undan yuqori)", "orange": "o'rtacha (5–15 %)", "red": "past (5 % dan kam)"}
_chegaralar = [(15, "green"), (37.5, "green"), (14.9, "orange"), (5, "orange"), (4.9, "red"), (-8.4, "red"), (0, "red")]
_natija = []
for _foiz, _kut in _chegaralar:
    _h = sogliq_soxta(_foiz)
    _natija.append((_foiz, _h.get("rentabellik"), (_h.get("sabablar") or {}).get("rentabellik")))
check("H9 (K115-2) rentabellik chegaralari 15 / 5: baho va sabab BITTA qoida (15 → yaxshi, 14.9 / 5 → o'rtacha, "
      "4.9 / manfiy → past)",
      all(b == k and t == f"Rentabellik {f:g} % — {_REN[k]}" for (f, b, t), (_f2, k) in zip(_natija, _chegaralar)), _natija)
_qs = (h.get("sabablar") or {}).get("qarzdorlik", "")
_qm = _re_k1152.match(r"^Qarz — sotuvning (-?[0-9.]+) % — (.+)$", _qs or "")
_QAR = {"green": "yaxshi (15 % dan kam)", "orange": "o'rtacha (15–30 %)", "red": "yuqori (30 % va undan ko'p)"}
_qkut = None
if _qm:
    _qf = float(_qm.group(1))
    _qkut = "green" if _qf < 15 else ("orange" if _qf < 30 else "red")
check("H10 (K115-2) qarzdorlik sababi chegara bilan, baho ko'rsatilgan foizga mos (asl: «Qarz — sotuvning N %» — chegarasiz)",
      _qm is not None and h.get("qarzdorlik") == _qkut and _qm.group(2) == _QAR.get(_qkut), (h.get("qarzdorlik"), _qs))

# ══════════════════════════════════════════════════════════════
# jsdom
# ══════════════════════════════════════════════════════════════
NODE_JS = r"""
let JSDOM, VirtualConsole, ResourceLoader;
try { ({ JSDOM, VirtualConsole, ResourceLoader } = require("jsdom")); }
catch (e) { console.log(JSON.stringify({ fatal: "jsdom topilmadi: " + String(e.message).slice(0, 200) })); process.exit(3); }
const base = process.argv[2], cookie = process.argv[3];
const sahifalar = JSON.parse(require("fs").readFileSync(process.argv[4], "utf8"));
// Chart.js (CDN) o'rniga — kichik soxta konstruktor (grafik chizilmaydi; sahifa skriptlari to'xtamasin)
const CHART_STUB = "window.Chart = function Chart(ctx, cfg) { this.config = cfg || {}; this.data = (cfg && cfg.data) || {datasets: []}; this.options = (cfg && cfg.options) || {}; };" +
  "window.Chart.prototype.destroy = function () {}; window.Chart.prototype.update = function () {}; window.Chart.register = function () {};" +
  "window.Chart.defaults = {font: {}, color: '', plugins: {legend: {labels: {}}, tooltip: {}}};";
class FaqatOzimiz extends ResourceLoader {
  fetch(url, options) {
    if (/chart\.umd(\.min)?\.js/i.test(url)) { const p = Promise.resolve(Buffer.from(CHART_STUB)); p.abort = () => {}; return p; }
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
      w.alert = () => {}; w.confirm = () => false; w.prompt = () => null; w.print = () => {};
      w.scrollTo = () => {}; w.open = () => null;
      w.matchMedia = () => ({ matches: false, media: "", addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
      class K { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } }
      w.IntersectionObserver = K; w.ResizeObserver = K;
      w.HTMLCanvasElement.prototype.getContext = () => null;
      w.HTMLElement.prototype.scrollIntoView = () => {};
    } });
  const w = dom.window;
  await new Promise(r => { if (w.document.readyState === "complete") return r(); w.addEventListener("load", () => r()); setTimeout(r, 8000); });
  async function tinch() {
    await kut(1000);
    const t0 = Date.now();
    while (Date.now() - t0 < 15000) { await kut(80); if (pending === 0 && Date.now() - lastActive > 500) return; }
    res.xato.push(yol + ": tarmoq 15 s ichida tinchimadi");
  }
  await tinch();
  for (const q of qadamlar) {
    try {
      if (q.amal) { await w.eval("(async () => { " + q.amal + "\n})()"); await tinch(); }
      if (q.natija) res.natija[q.nom] = await w.eval("(async () => { " + q.natija + "\n})()");
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


M = r"const __m = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : null;"
HIS = [
    q("r", natija=M + r"""
      const kartalar = {};
      ['pul_oqimi','ombor','rentabellik','qarzdorlik','ishlab_chiqarish','material_sarfi'].forEach(k => {
        const el = document.getElementById('h-' + k);
        kartalar[k] = {holat: __m(el), sabab: el && el.parentElement.querySelector('.bi-health-sabab') ? __m(el.parentElement.querySelector('.bi-health-sabab')) : null};
      });
      const css = [...document.querySelectorAll('style')].map(s => s.textContent).join('\n');
      const m = /\.bi-health-status\{([^}]*)\}/.exec(css);
      return {kartalar, capitalize: m ? /capitalize/.test(m[1]) : null,
        ch: ['kpi-daromad-ch','kpi-xarajat-ch','kpi-foyda-ch','kpi-foiz-ch'].map(i => __m(document.getElementById(i))),
        comp: ['comp-daromad','comp-jami_xarajat','comp-sof_foyda'].map(i => __m(document.getElementById(i))),
        ai: __m(document.getElementById('aiSummaryList'))};"""),
    # kech116 (K115-3): ogohlantirishlar ro'yxati BO'SH bo'lsa ham «Bugungi xulosa» yig'iladi (sahifaning O'Z loadAlerts i;
    # faqat /api/reports/alerts javobi bo'sh ro'yxat bilan almashtiriladi — boshqa so'rovlar HAQIQIY server)
    q("r_xulosa", amal=r"""
      document.getElementById('aiSummary').style.display = 'none';
      document.getElementById('aiSummaryList').textContent = 'Yuklanmoqda...';
      const __asl = window.fetch;
      window.fetch = (u, o) => String(u).indexOf('/api/reports/alerts') >= 0
        ? Promise.resolve({ok: true, status: 200, json: async () => []}) : __asl(u, o);
      try { await loadAlerts(); } finally { window.fetch = __asl; }""",
      natija=M + r"""return {display: document.getElementById('aiSummary').style.display,
        matn: __m(document.getElementById('aiSummaryList')), bosh: __m(document.getElementById('alertsBody'))};"""),
    q("r_fn", natija=r"""return {
        yoq: ozgarishKorinishi('daromad', {change_pct: null, holat: 'malumot_yoq'}),
        ozg: ozgarishKorinishi('daromad', {change_pct: null, holat: 'ozgarmadi'}),
        xu: ozgarishKorinishi('jami_xarajat', {change_pct: 20, holat: 'oshdi'}),
        fu: ozgarishKorinishi('sof_foyda', {change_pct: 20, holat: 'oshdi'}),
        fk: ozgarishKorinishi('sof_foyda', {change_pct: -150, holat: 'kamaydi'})};"""),
]
INV = [
    q("i", natija=M + r"""
      const kor = () => [...document.querySelectorAll('#matList .mat-row')].filter(r => r.style.display !== 'none').map(r => r.dataset.name);
      const f = document.getElementById('statusFilter');
      const opt = [...f.options].map(o => [o.value, o.text]);
      const natija = {opt, karta: __m(document.querySelector('#kamQolganKarta .stat-val') || [...document.querySelectorAll('.stat-card')].find(c => /Kam qolganlar/.test(c.textContent)).querySelector('.stat-val'))};
      for (const v of ['yetarli', 'oz', 'kamqolgan', 'tugagan', 'warn', 'danger']) { f.value = v; filterMaterials(); natija[v] = f.value === v ? kor().filter(n => n.startsWith('k115')).sort() : null; }
      f.value = ''; filterMaterials();
      return natija;"""),
    q("i_karta", amal="kamQolganlarniKorsat();",
      natija=r"""return {filtr: document.getElementById('statusFilter').value,
        kor: [...document.querySelectorAll('#matList .mat-row')].filter(r => r.style.display !== 'none').map(r => r.dataset.name).filter(n => n.startsWith('k115')).sort()};"""),
]
FIN = [
    q("f", natija=M + r"""const o = document.getElementById('hero-oqim'), rf = document.getElementById('r-foyda'), rz = document.getElementById('r-foiz');
      return {oqim: __m(o), oqim_rang: o.style.color, foyda: __m(rf), foiz: __m(rz), foiz_rang: rz.style.color,
        q: [qisqaSumma(-2618028), qisqaSumma(-500), qisqaSumma(0), qisqaSumma(1500), qisqaSumma(-26817802), qisqaSumma(999.6), qisqaSumma(999999.6), qisqaSumma(-0.3)]};"""),
]
DASH = [
    q("d", natija=M + r"""return {sof: __m(document.getElementById('mf-sof-foyda')), fmt: [fmt(-2618028), fmt(-26817802), fmt(-700)]};"""),
]
SAHIFALAR = [{"yol": "/reports", "qadamlar": HIS}, {"yol": "/inventory", "qadamlar": INV},
             {"yol": "/finance", "qadamlar": FIN}, {"yol": "/dashboard", "qadamlar": DASH}]

section("1. Lokal server + jsdom")
node = shutil.which("node")
check("U0 node topildi", node is not None)
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
    check("U0 uvicorn ishga tushdi", server.started)
    base = f"http://127.0.0.1:{port}"
    try:
        import httpx
        lr = httpx.post(base + "/login", data={"username": "k115_admin", "password": "Parol123!"}, follow_redirects=False,
                        timeout=30)
        cookie = "; ".join(hh.split(";")[0] for hh in lr.headers.get_list("set-cookie"))
        pj = os.path.join(_T, "sahifalar.json")
        with open(pj, "w", encoding="utf-8") as f:
            json.dump(SAHIFALAR, f, ensure_ascii=False)
        sj = os.path.join(_T, "a115k.js")
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
check("U0 sahifalar 200, ssenariy tugadi", "fatal" not in NAT and len(NAT.get("sahifa") or {}) == 4
      and all(v == 200 for v in (NAT.get("sahifa") or {}).values()), {k: NAT.get(k) for k in ("sahifa", "fatal", "xato")})


def g(nom, kalit=None, std=None):
    v = N.get(nom)
    if kalit is None:
        return v
    return v.get(kalit, std) if isinstance(v, dict) else std


def bosh(t):
    return " ".join(str(t or "").replace(" ", " ").replace(" ", " ").split())


section("R. Hisobotlar — G1-06 / G1-01")
_k = g("r", "kartalar") or {}
check("R1 «Ombor — Muammoli» + sabab «2 ta material tugagan, 1 tasi kam» (asl: «Yaxshi», sababsiz)",
      (_k.get("ombor") or {}).get("holat") == "Muammoli"
      and (_k.get("ombor") or {}).get("sabab") == "2 ta material tugagan, 1 tasi kam", _k.get("ombor"))
check("R2 «Ishlab chiqarish — Muammoli» + sabab (3 ta muddati o'tgan)", (_k.get("ishlab_chiqarish") or {}).get("holat") == "Muammoli"
      and "3 ta buyurtmaning muddati o'tgan" in ((_k.get("ishlab_chiqarish") or {}).get("sabab") or ""), _k.get("ishlab_chiqarish"))
check("R3 har kartada sabab qatori bor", all((v or {}).get("sabab") for v in _k.values()) and len(_k) == 6, _k)
check("R4 holat matni har so'z bosh harf bilan EMAS (text-transform yo'q)", g("r", "capitalize") is False, g("r", "capitalize"))
_f = g("r_fn") or {}
check("R5 foiz yo'q → «o'tgan oyda ma'lumot yo'q» (kulrang, foizsiz)",
      (_f.get("yoq") or {}).get("matn") == "o'tgan oyda ma'lumot yo'q" and (_f.get("yoq") or {}).get("foizli") is False, _f.get("yoq"))
check("R6 o'zgarmadi → «o'zgarmadi»", (_f.get("ozg") or {}).get("matn") == "o'zgarmadi", _f.get("ozg"))
check("R7 xarajat o'sishi — QIZIL, sof foyda o'sishi — yashil (bir qoida)",
      (_f.get("xu") or {}).get("rang") == "var(--b-danger)" and (_f.get("fu") or {}).get("rang") == "var(--b-success)"
      and (_f.get("fk") or {}).get("matn") == "150% kamaydi", _f)
check("R8 kartalarda (o'tgan oy bo'sh) «o'tgan oyda ma'lumot yo'q» — «100%» YO'Q (asl: «↗ 100% o'tgan oyga nisbatan»)",
      g("r", "ch") and all("100%" not in (x or "") for x in g("r", "ch"))
      and sum(1 for x in g("r", "ch") if "o'tgan oyda ma'lumot yo'q" in (x or "")) >= 2, g("r", "ch"))
check("R9 xulosada «Bu oy zarar: …» (asl: «Sof foyda 100% oshdi»)", "Bu oy zarar" in (g("r", "ai") or "")
      and "100% oshdi" not in (g("r", "ai") or ""), g("r", "ai"))
check("R10 (K115-3) ogohlantirish YO'Q bo'lsa ham «Bugungi xulosa» ko'rinadi: «Bu oy zarar: …» (asl: yashirin, «Yuklanmoqda...»)",
      g("r_xulosa", "display") == "flex" and "Bu oy zarar" in (g("r_xulosa", "matn") or "")
      and "Yuklanmoqda" not in (g("r_xulosa", "matn") or ""), N.get("r_xulosa"))
check("R11 (K115-3) bo'sh ro'yxat matni «Hozircha muhim ogohlantirish yo'q»",
      "Hozircha muhim ogohlantirish yo'q" in (g("r_xulosa", "bosh") or ""), N.get("r_xulosa"))
check("R12 (K115-2) sahifadagi «Rentabellik» sababi — «past (5 % dan kam)», «yaxshi» YO'Q",
      ((_k.get("rentabellik") or {}).get("sabab") or "").endswith("— past (5 % dan kam)")
      and "yaxshi" not in ((_k.get("rentabellik") or {}).get("sabab") or ""), _k.get("rentabellik"))

section("I. Omborxona — G4-06")
_ki = g("i") or {}
check("I1 filtr nomlari belgilar bilan bir xil: Yetarli / Oz / Kam qolganlar / Tugagan",
      [o[0] for o in (_ki.get("opt") or [])] == ["", "yetarli", "oz", "kamqolgan", "tugagan"], _ki.get("opt"))
check("I2 «Kam qolganlar» — kam + tugagan (3 ta = karta soni)",
      _ki.get("kamqolgan") == ["k115 kam c", "k115 tugagan a", "k115 tugagan b"] and "3" in (_ki.get("karta") or ""),
      (_ki.get("kamqolgan"), _ki.get("karta")))
check("I3 «Oz» — faqat chegaraga yaqin (Oz D)", _ki.get("oz") == ["k115 oz d"], _ki.get("oz"))
check("I4 «Tugagan» — faqat 0 / manfiy", _ki.get("tugagan") == ["k115 tugagan a", "k115 tugagan b"], _ki.get("tugagan"))
check("I5 «Yetarli»", _ki.get("yetarli") == ["k115 penoplast", "k115 yetarli e", "k115 yetarli f"], _ki.get("yetarli"))
check("I6 kartani bosish → «Kam qolganlar» filtri, 3 ta", g("i_karta", "filtr") == "kamqolgan"
      and g("i_karta", "kor") == ["k115 kam c", "k115 tugagan a", "k115 tugagan b"], N.get("i_karta"))

section("F. Moliya — G3-10 / G1-04")
check("F1 «Pul oqimi» (bugun) — MINUS bilan, qizil (asl: minussiz)", bosh(g("f", "oqim")).startswith("-")
      and len(bosh(g("f", "oqim"))) > 8 and g("f", "oqim_rang") == "var(--f-danger)", N.get("f"))
_SOF = float(_rep.get("sof_foyda", 0) or 0)
_SOF_Q = ("-" if _SOF < 0 else "") + f"{abs(_SOF) / 1e6:.1f} mln so'm"
check(f"F2 oylik sof foyda — «{_SOF_Q}» (asl: ajratgichsiz «{int(_SOF)}»)", _SOF <= -1e6 and bosh(g("f", "foyda")) == _SOF_Q,
      (g("f", "foyda"), _SOF))
check("F3 manfiy rentabellik — QIZIL (asl: yashil)", g("f", "foiz_rang") == "var(--f-danger)", (g("f", "foiz"), g("f", "foiz_rang")))
check("F4 qisqaSumma: -2.6 mln / -500 / 0 / 2 ming / -26.8 mln / 1 000 dan kichik — butun",
      g("f", "q") == ["-2.6 mln", "-500", "0", "2 ming", "-26.8 mln", "1 ming", "1.0 mln", "0"], g("f", "q"))

section("D. Dashboard — G3-10")
check(f"D1 «Bu oy moliyaviy holat» sof foyda — «{_SOF_Q}» (asl: ajratgichsiz)", bosh(g("d", "sof")) == _SOF_Q, (g("d", "sof"), _SOF))
check("D2 fmt: manfiy ham qisqa (-2.6 mln / -26.8 mln / -700)", g("d", "fmt") == ["-2.6 mln", "-26.8 mln", "-700"], g("d", "fmt"))

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
