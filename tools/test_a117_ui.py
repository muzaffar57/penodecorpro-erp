#!/usr/bin/env python3
"""
test_a117_ui.py — kech117, A2: YO'NALISHLAR BO'YICHA MOLIYA — sahifalar (HAQIQIY server — uvicorn, sahifalar — jsdom,
sahifaning O'Z JavaScript'i). Server qoidalari — `tools/test_a117_yonalish.py`.

NIMA UCHUN KERAK (egasi QARORLARI kech114 00:08; audit G3-11 / G6-09)
  Sozlamalar (Tizim jurnallari → Sozlamalar)  yo'nalishlarni qo'shish, nomini o'zgartirish, yashirish, ishlatilmaganini
                       o'chirish (tasdiq oynasisiz ikki bosqich); asosiyni yashirib / o'chirib bo'lmaydi.
  Ishlab chiqarish     tur oynasida yo'nalish MAJBURIY; jadvalda yo'nalish belgisi / «belgilanmagan»; biriktirish oynasi.
  Hodimlar (KPI)       yo'nalish tanlovi — «Umumiy» + korxona yo'nalishlari (ilgari Penoplast / Gips).
  Moliya               «Yo'nalishlar bo'yicha sof foyda» jadvali (yig'indi = Moliya sof foydasi), PDF tugmasi, «Tannarx»
                       kartasi, «Tayyor mahsulot sotuvi tannarxi» qatori, daromad doirasi yo'nalishlar bo'yicha; xarajat
                       oynasida yo'nalish ro'yxati; bitta yo'nalishli korxonada bo'lim va doira yashirin.
  Kirim / Dashboard / Hisobotlar  yo'nalish tanlovi; grafiklar yo'nalishlar bo'yicha (bitta bo'lsa — yashirin).
  X                    foydalanuvchi yozgan yo'nalish nomi hech qayerda HTML bo'lib bajarilmaydi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI.
ISHLATISH: NODE_PATH=$(npm root -g) python3 tools/test_a117_ui.py
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
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "a117_ui_test"
_T = tempfile.mkdtemp(prefix="a117u_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'a117_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal, tashkent_date, tashkent_oy_oraligi   # noqa: E402
from models import (UserRole, Inventory, Project, ProjectStatus, Order, OrderItem, OrderType, OrderStatus,   # noqa: E402
                    FinishedProduct, FinishedProductSale, StockSource, ProductionStatus, Supplier, InventoryReceipt)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

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
        print(f"  ✗ {label}   {str(detail)[:800]}")


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
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
BUGUN = tashkent_date()
OY_BOSHI, _oy_oxiri = tashkent_oy_oraligi(BUGUN.year, BUGUN.month)
T = OY_BOSHI + timedelta(days=1, hours=3)
XSS = "Yog'och <img src=x onerror=\"window.__xss=1\">"
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="U117 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "u117_admin", "Parol123!", UserRole.ADMIN, "U117 Admin", company_id=1)
    auth.create_user(s, "u117_b", "Parol123!", UserRole.ADMIN, "U117 B", company_id=2)
PRJ = Project(company_id=1, project_number="PRJ-U117", client_name="U117 mijoz", project_name="U117 loyiha",
              status=ProjectStatus.DRAFT)
PENO = Inventory(company_id=1, item_name="U117 Penoplast", unit="dona", stock_quantity=1000, price_per_unit=900_000,
                 volume_per_unit=0.9, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
PRJB = Project(company_id=2, project_number="PRJ-U117B", client_name="U117 B mijoz", project_name="U117 B loyiha",
               status=ProjectStatus.DRAFT)
SUP = Supplier(company_id=1, name="U117 Ta'minotchi", is_active=True)
KLEY = Inventory(company_id=1, item_name="U117 Kley", unit="kg", stock_quantity=0, price_per_unit=1000,
                 category="Boshqa")
s.add_all([PRJ, PENO, PRJB, SUP, KLEY])
s.commit()
ID = {"PRJ": PRJ.id, "PENO": PENO.id, "PRJB": PRJB.id, "SUP": SUP.id, "KLEY": KLEY.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CBT = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "u117_admin", "password": "Parol123!"}, follow_redirects=False)
_lb = req(CBT, "post", "/login", data={"username": "u117_b", "password": "Parol123!"}, follow_redirects=False)
check("0 login (A va B)", _lr.status_code == 302 and _lb.status_code == 302, [_lr.status_code, _lb.status_code])
Y_ASOSIY = next((y.get("id") for y in (js(req(C, "get", "/api/yonalishlar")) or []) if isinstance(y, dict)
                 and y.get("asosiy")), None)
Y_M = (js(req(C, "post", "/api/yonalishlar", json={"nom": "Metall"})) or {}).get("id")
Y_X = (js(req(C, "post", "/api/yonalishlar", json={"nom": XSS})) or {}).get("id")
Y_BOSH = (js(req(C, "post", "/api/yonalishlar", json={"nom": "Bo'sh yo'nalish"})) or {}).get("id")
Y_YASH = (js(req(C, "post", "/api/yonalishlar", json={"nom": "Eski yo'nalish"})) or {}).get("id")
PT_M = (js(req(C, "post", "/api/production/product-types", json={
    "name": "U117 Travertin", "unit": "m²", "input_template": "quantity_only", "pricing_formula": "unit_based",
    "yonalish_id": Y_M})) or {}).get("id")
PT_N = (js(req(C, "post", "/api/production/product-types", json={
    "name": "U117 Belgisiz", "unit": "dona", "input_template": "quantity_only", "pricing_formula": "unit_based"})) or {}).get("id")
PT_N2 = (js(req(C, "post", "/api/production/product-types", json={
    "name": "U117 Belgisiz2", "unit": "dona", "input_template": "quantity_only", "pricing_formula": "unit_based"})) or {}).get("id")
PT_X = (js(req(C, "post", "/api/production/product-types", json={
    "name": "U117 XSS turi", "unit": "dona", "input_template": "quantity_only", "pricing_formula": "unit_based",
    "yonalish_id": Y_X})) or {}).get("id")
_eh = req(C, "post", "/api/employees", json={"name": "U117 Eski hodim", "pay_type": "fixed", "fixed_amount": 100_000,
                                             "yonalish_id": Y_YASH})
E_YASH = (js(_eh) or {}).get("id")
_tx_yash = req(C, "post", "/api/finance/transactions", json={"category": "boshqa", "amount": 1234.0, "yonalish_id": Y_YASH,
                                                             "date": T.strftime("%Y-%m-%dT%H:%M:%S")})
TX_YASH = (js(_tx_yash) or {}).get("id")
TX_X = (js(req(C, "post", "/api/finance/transactions", json={"category": "boshqa", "amount": 777.0, "yonalish_id": Y_X,
                                                             "date": T.strftime("%Y-%m-%dT%H:%M:%S")})) or {}).get("id")
req(C, "put", f"/api/yonalishlar/{Y_YASH}", json={"yashirin": True})
s = SessionLocal()
try:
    fp_p = FinishedProduct(company_id=1, name="U117 TM profil", category="profil", quantity=5, produced_quantity=10,
                           unit="metr", cost_price=100_000, source=StockSource.PRODUCED,
                           production_status=ProductionStatus.READY)
    s.add(fp_p)
    s.flush()
    o = Order(company_id=1, order_number="U117-1", project_id=ID["PRJ"], order_type=OrderType.PRODUCT,
              total_amount=1_150_000, agreed_amount=1_150_000, status=OrderStatus.READY, completed_at=T)
    s.add(o)
    s.flush()
    s.add(OrderItem(company_id=1, order_id=o.id, name="U117 profil", category="profil", width=20, thickness=10, length=4,
                    quantity=1, unit_price=600_000, total_price=600_000, is_coated=False, penoplast_id=ID["PENO"]))
    s.add(OrderItem(company_id=1, order_id=o.id, name="U117 travertin", category="mrp_product", quantity=10,
                    unit_price=40_000, total_price=400_000, product_type_id=PT_M))
    s.add(OrderItem(company_id=1, order_id=o.id, name="U117 belgisiz2", category="mrp_product", quantity=1,
                    unit_price=100_000, total_price=100_000, product_type_id=PT_N2))
    s.add(OrderItem(company_id=1, order_id=o.id, name="U117 xss", category="mrp_product", quantity=1,
                    unit_price=50_000, total_price=50_000, product_type_id=PT_X))
    s.add(FinishedProductSale(company_id=1, finished_product_id=fp_p.id, product_name=fp_p.name, quantity=1, unit="metr",
                              unit_price=90_000, total_amount=90_000, cost_amount=30_000, sold_at=T))
    # B korxona — bitta yo'nalish, daromad bor (bo'limlar YASHIRIN bo'lishi kerak)
    ob = Order(company_id=2, order_number="U117B-1", project_id=ID["PRJB"], order_type=OrderType.PRODUCT,
               total_amount=500_000, agreed_amount=500_000, status=OrderStatus.READY, completed_at=T)
    s.add(ob)
    s.flush()
    s.add(OrderItem(company_id=2, order_id=ob.id, name="U117B profil", category="panel", width=50, thickness=2,
                    quantity=1, unit_price=500_000, total_price=500_000))
    s.commit()
finally:
    s.close()
SPLIT = js(req(C, "get", "/api/finance/yonalishlar", params={"year": BUGUN.year, "month": BUGUN.month})) or {}
check("0 fikstura: 5 yo'nalish (bittasi yashirin), 4 MRP turi (ikkitasi yo'nalishsiz), hodim / xarajat yashirin yo'nalishda, buyurtma, TM sotuvi",
      all([Y_ASOSIY, Y_M, Y_X, Y_BOSH, Y_YASH, PT_M, PT_N, PT_N2, PT_X, E_YASH, TX_YASH, TX_X])
      and isinstance(SPLIT.get("yonalishlar"), list),
      [Y_ASOSIY, Y_M, Y_X, Y_BOSH, Y_YASH, PT_M, PT_N, PT_N2, PT_X, E_YASH, TX_YASH, TX_X,
       SPLIT if not isinstance(SPLIT.get("yonalishlar"), list) else "", _eh.text[:200], _tx_yash.text[:200]])

# ══════════════════════════════════════════════════════════════
# jsdom (test_a116_ui bilan bir harness)
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
      w.__promptlar = 0; w.__confirmlar = 0;
      w.alert = () => {}; w.confirm = () => { w.__confirmlar++; return false; }; w.prompt = () => { w.__promptlar++; return null; }; w.print = () => {};
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
    await kut(1200);
    const t0 = Date.now();
    while (Date.now() - t0 < 15000) { await kut(80); if (pending === 0 && Date.now() - lastActive > 600) return; }
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


M = r"const __m = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : null; const __vis = id => { const e = document.getElementById(id); return e ? e.style.display !== 'none' : null; };"
SOR = r"const __s = (metod, qism) => window.__sorovlar.filter(x => x.method === metod && x.url.includes(qism)).map(x => { let b = x.body; try { b = JSON.parse(x.body); } catch (e) {} return {url: x.url, body: b}; });"
TK = f"const __y = {BUGUN.year}, __o = {BUGUN.month};"
SOZ = [
    q("s1", amal="switchLogTab('settings');", natija=M + r"""
      const qatorlar = [...document.querySelectorAll('#yon-list .yon-qator')];
      return {qatorlar: qatorlar.map(r => ({id: r.dataset.id, nom: r.querySelector('.yon-nom').value,
        chip: [...r.querySelectorAll('.yon-chip')].map(__m),
        tugma: [...r.querySelectorAll('button')].map(__m)})), img: document.querySelectorAll('#yon-list img').length,
        xss: window.__xss || 0};"""),
    q("s2", amal=r"""window.__sorovlar.length = 0; document.getElementById('yon-yangi').value = '  '; await yonQosh();""",
      natija=M + SOR + r"""return {post: __s('POST', '/api/yonalishlar').length, status: __m(document.getElementById('yon-status'))};"""),
    q("s3", amal=r"""window.__sorovlar.length = 0; document.getElementById('yon-yangi').value = 'Plastik'; await yonQosh();""",
      natija=M + SOR + r"""return {post: __s('POST', '/api/yonalishlar'), status: __m(document.getElementById('yon-status')),
        yangi: [...document.querySelectorAll('#yon-list .yon-nom')].map(i => i.value), input: document.getElementById('yon-yangi').value};"""),
    q("s4", amal=r"""window.__sorovlar.length = 0; document.getElementById('yon-yangi').value = 'metall'; await yonQosh();""",
      natija=M + SOR + r"""return {post: __s('POST', '/api/yonalishlar').length, status: __m(document.getElementById('yon-status'))};"""),
    q("s5", amal=f"""window.__sorovlar.length = 0;
      const r = document.querySelector('#yon-list .yon-qator[data-id="{Y_M}"]');
      r.querySelector('.yon-nom').value = 'Metall konstruksiya';
      await yonNomSaqla([...r.querySelectorAll('button')].find(b => b.textContent.includes('Nomini')));""",
      natija=M + SOR + r"""return {put: __s('PUT', '/api/yonalishlar/'),
        nomlar: [...document.querySelectorAll('#yon-list .yon-nom')].map(i => i.value)};"""),
    q("s6", amal=f"""window.__sorovlar.length = 0;
      const b = document.querySelector('#yon-list .yon-qator[data-id="{Y_BOSH}"] .yon-ochir');
      await yonOchir(b);
      window.__s6_matn = b.textContent;""",
      natija=M + SOR + f"""return {{del: __s('DELETE', '/api/yonalishlar/').length, matn: window.__s6_matn,
        bor: !!document.querySelector('#yon-list .yon-qator[data-id="{Y_BOSH}"]'), confirm: window.__confirmlar}};"""),
    q("s7", amal=f"""window.__sorovlar.length = 0;
      await yonOchir(document.querySelector('#yon-list .yon-qator[data-id="{Y_BOSH}"] .yon-ochir'));""",
      natija=M + SOR + f"""return {{del: __s('DELETE', '/api/yonalishlar/{Y_BOSH}').length,
        bor: !!document.querySelector('#yon-list .yon-qator[data-id="{Y_BOSH}"]')}};"""),
    q("s8", amal=f"""window.__sorovlar.length = 0;
      const b = [...document.querySelectorAll('#yon-list .yon-qator[data-id="{Y_YASH}"] button')].find(x => x.textContent.includes("Ko'rsatish"));
      await yonYashir(b);""",
      natija=M + SOR + f"""const r = document.querySelector('#yon-list .yon-qator[data-id="{Y_YASH}"]');
        return {{put: __s('PUT', '/api/yonalishlar/{Y_YASH}'), chip: [...r.querySelectorAll('.yon-chip')].map(__m),
          tugma: [...r.querySelectorAll('button')].map(__m)}};"""),
    q("s9", amal=f"""
      const b = [...document.querySelectorAll('#yon-list .yon-qator[data-id="{Y_YASH}"] button')].find(x => x.textContent.includes('Yashirish'));
      await yonYashir(b);""",
      natija=M + f"""const r = document.querySelector('#yon-list .yon-qator[data-id="{Y_YASH}"]');
        return {{chip: [...r.querySelectorAll('.yon-chip')].map(__m)}};"""),
]
PROD = [
    q("p1", natija=M + r"""return {opts: [...document.querySelectorAll('#pt-f-yonalish option')].map(o => [o.value, o.textContent]),
      pty: [...document.querySelectorAll('#pty-f-yonalish option')].map(o => o.value),
      img: document.querySelectorAll('#pt-f-yonalish img, #pty-f-yonalish img').length};"""),
    q("p2", amal=r"""window.__sorovlar.length = 0; window.__xabar = null;
      const __asl = window.showMsg; window.showMsg = (t, tur) => { window.__xabar = {t: String(t), tur}; };
      try { openProductTypeModal(); document.getElementById('pt-f-name').value = 'U117 Yangi tur';
            document.getElementById('pt-f-unit').value = 'dona'; await saveProductType(); } finally { window.showMsg = __asl; }""",
      natija=SOR + r"""return {post: __s('POST', '/api/production/product-types').length, xabar: window.__xabar,
        modal: document.getElementById('pt-modal').classList.contains('open')};"""),
    q("p3", amal=f"""window.__sorovlar.length = 0;
      document.getElementById('pt-f-yonalish').value = '{Y_M}'; await saveProductType();""",
      natija=SOR + r"""return {post: __s('POST', '/api/production/product-types').map(x => x.body)};"""),
    q("p4", amal="await loadProductTypes();", natija=M + r"""
      const qator = nom => [...document.querySelectorAll('#pt-list tbody tr')].find(t => __m(t.querySelector('.pt-tur-nomi')) === nom);
      const q = n => { const t = qator(n); return t ? {chip: [...t.querySelectorAll('.pt-chip')].map(__m),
        tugma: [...t.querySelectorAll('.pt-amallar button')].map(__m)} : null; };
      return {m: q('U117 Travertin'), n: q('U117 Belgisiz'), yangi: q('U117 Yangi tur')};"""),
    q("p5", amal=f"""window.__sorovlar.length = 0;
      const b = [...document.querySelectorAll('#pt-list .pt-amallar button')].find(x => x.dataset.id === '{PT_N}' && x.dataset.nom);
      openTurYonalish(b);
      window.__p5 = {{tur: document.getElementById('pty-tur').textContent, qiymat: document.getElementById('pty-f-yonalish').value,
                     ochiq: document.getElementById('pty-modal').classList.contains('open')}};
      document.getElementById('pty-f-yonalish').value = '{Y_M}';
      await saveTurYonalish();""",
      natija=SOR + r"""return {oldin: window.__p5, patch: __s('PATCH', '/api/production/product-types/'),
        ochiq: document.getElementById('pty-modal').classList.contains('open')};"""),
]
KPI = [
    q("k1", natija=M + r"""const t = [...document.querySelectorAll('#e-prodtype-toggle .dir-opt')];
      return {opts: t.map(e => [e.dataset.val, __m(e)]), img: document.querySelectorAll('#e-prodtype-toggle img').length};"""),
    q("k2", amal=r"""window.__sorovlar.length = 0; openEmpModal(); document.getElementById('e-name').value = 'U117 Yangi hodim';
      document.getElementById('e-fixed').value = '100000'; await saveEmployee();""",
      natija=M + SOR + r"""return {post: __s('POST', '/api/employees').length, xato: __m(document.getElementById('emp-error'))};"""),
    q("k3", amal=r"""window.__sorovlar.length = 0; setProdType('umumiy'); await saveEmployee();""",
      natija=SOR + r"""return {post: __s('POST', '/api/employees').map(x => x.body)};"""),
    q("k4", amal=f"""await loadEmployees(); window.__sorovlar.length = 0; editEmployee({E_YASH});""",
      natija=M + r"""const t = [...document.querySelectorAll('#e-prodtype-toggle .dir-opt')];
        return {opts: t.map(e => [e.dataset.val, __m(e), e.classList.contains('active')]), qiymat: document.getElementById('e-prodtype').value};"""),
    q("k5", amal=r"""await saveEmployee();""",
      natija=SOR + r"""return {put: __s('PUT', '/api/employees/').map(x => x.body)};"""),
]
FIN = [
    q("f1", amal="await loadReport(); await new Promise(r => setTimeout(r, 900));", natija=M + TK + r"""
      const api = await (await fetch(`/api/finance/yonalishlar?year=${__y}&month=${__o}`)).json();
      const rep = await (await fetch(`/api/finance/report?year=${__y}&month=${__o}`)).json();
      const t = document.querySelector('#yonJadval table');
      const bosh = t ? [...t.querySelectorAll('thead th')].map(__m).slice(1) : [];
      const qator = nom => { const tr = t ? [...t.querySelectorAll('tbody tr')].find(r => __m(r.cells[0]) === nom) : null;
                             return tr ? [...tr.cells].slice(1).map(__m) : null; };
      return {api, rep: {sof_foyda: rep.sof_foyda, tannarx_jami: rep.tannarx_jami, jami_xarajat: rep.jami_xarajat,
                         fp_sales_tannarx: rep.fp_sales_tannarx},
        bolim: __vis('yonBolim'), bosh, sof: qator('Sof foyda'), daromad: qator('Daromad'),
        tannarx: qator('Tannarx (sotilgan mahsulot)'), tekshir: __m(document.getElementById('yonTekshiruv')),
        ogoh: __m(document.getElementById('yonOgoh')), ogoh_vis: __vis('yonOgoh'),
        img: document.querySelectorAll('#yonJadval img, #revDonutLegend img, #yonOgoh img').length, xss: window.__xss || 0,
        tannarx_karta: __m(document.getElementById('r-tannarx')),
        donut: document.getElementById('revDonutCard').style.display,
        legend: [...document.querySelectorAll('#revDonutLegend > div')].map(d => __m(d.querySelector('span:nth-child(2)'))),
        pdf: !!document.querySelector('#yonBolim button[onclick="downloadSplitProfitPdf()"]'),
        eski_pdf: document.body.innerHTML.includes('Gips vs'),
        jami_xarajat: __m([...document.querySelectorAll('#expDetail .fin-total-row')][0]),
        tm_tannarx: [...document.querySelectorAll('#expDetail .fin-exp-row')].map(__m).filter(x => x.includes('Tayyor mahsulot sotuvi tannarxi')),
        turlar: document.getElementById('expDetail').textContent.includes("Turlar bo'yicha")};"""),
    q("f2", natija=r"""return {opts: [...document.querySelectorAll('#tx-f-prodtype option')].map(o => [o.value, o.textContent]),
      img: document.querySelectorAll('#tx-f-prodtype img').length};"""),
    q("f3", amal=f"""window.__sorovlar.length = 0; openTxModal(); document.getElementById('tx-f-amount').value = '5 000';
      document.getElementById('tx-f-prodtype').value = '{Y_M}'; await saveTx();""",
      natija=SOR + r"""return {post: __s('POST', '/api/finance/transactions').map(x => x.body)};"""),
    q("f4", amal=f"""window.__sorovlar.length = 0;
      editTx({TX_YASH}, '{T.strftime("%Y-%m-%dT%H:%M:%S")}', 'boshqa', 1234, '', '{Y_YASH}');
      window.__f4 = {{qiymat: document.getElementById('tx-f-prodtype').value,
                     opts: [...document.querySelectorAll('#tx-f-prodtype option')].map(o => o.value)}};
      await saveTx();""",
      natija=SOR + r"""return {oldin: window.__f4, put: __s('PUT', '/api/finance/transactions/').map(x => x.body)};"""),
]
RCV = [
    q("r1", natija=M + r"""return {opts: [...document.querySelectorAll('#ap-prod-type-toggle .rcv-cat-opt')].map(e => [e.dataset.value, __m(e)]),
      sel: [...document.querySelectorAll('#ap-prod-type option')].map(o => o.value),
      img: document.querySelectorAll('#ap-prod-type-toggle img, #ap-prod-type img').length};"""),
    q("r2", amal=f"""selectProdType(document.querySelector('#ap-prod-type-toggle .rcv-cat-opt[data-value="{Y_M}"]'), '{Y_M}');""",
      natija=r"""return {qiymat: document.getElementById('ap-prod-type').value, chosen: prodTypeChosen,
        active: [...document.querySelectorAll('#ap-prod-type-toggle .rcv-cat-opt.active')].map(e => e.dataset.value)};"""),
    q("r3", amal=f"""window.__sorovlar.length = 0; currentSupplierId = {ID['SUP']};
      document.getElementById('r-date').value = tkISO();
      document.getElementById('ap-qty').value = ''; document.getElementById('ap-price').value = '';
      apBasket.push({{itemId: {ID['KLEY']}, itemName: 'U117 Kley', unit: 'kg', qty: 2, price: 1000, total: 2000,
                     isPenoplast: false, volumePerUnit: null}});
      await submitReceive();""",
      natija=SOR + r"""return {post: __s('POST', '/api/inventory/receipt').map(x => x.body)};"""),
]
DSH = [
    q("d1", natija=M + r"""const g = (window.__grafiklar || []).find(c => c && c.data && (c.data.datasets || []).some(d => d.label === 'Metall konstruksiya'));
      return {karta: document.getElementById('yonKarta').style.display, labels: g ? g.data.datasets.map(d => d.label) : null,
        bugun: [...document.querySelectorAll('#pg-today-split span')].map(__m), img: document.querySelectorAll('#pg-today-split img').length,
        xss: window.__xss || 0, eski: document.body.textContent.includes('Penoplast va 🧱 Gips')};"""),
]
REPS = [
    q("h1", natija=M + r"""const g = (window.__grafiklar || []).find(c => c && c.data && (c.data.datasets || []).some(d => d.label === 'Metall konstruksiya'));
      return {bolim: document.getElementById('yonDinamika').style.display, labels: g ? g.data.datasets.map(d => d.label) : null,
        eski: document.body.textContent.includes('Penoplast va 🧱 Gips')};"""),
]
B_FIN = [
    q("bf", amal="await loadReport(); await new Promise(r => setTimeout(r, 900));", natija=M + r"""
      return {bolim: __vis('yonBolim'), donut: document.getElementById('revDonutCard').style.display,
        opts: [...document.querySelectorAll('#tx-f-prodtype option')].map(o => o.textContent)};"""),
]
B_DSH = [q("bd", natija=r"""return {karta: document.getElementById('yonKarta').style.display};""")]
B_REP = [q("bh", natija=r"""return {bolim: document.getElementById('yonDinamika').style.display};""")]
SAHIFALAR_A = [{"yol": "/logs", "qadamlar": SOZ}, {"yol": "/production", "qadamlar": PROD}, {"yol": "/kpi", "qadamlar": KPI},
               {"yol": "/finance", "qadamlar": FIN}, {"yol": "/suppliers/receive", "qadamlar": RCV},
               {"yol": "/dashboard", "qadamlar": DSH}, {"yol": "/reports", "qadamlar": REPS}]
SAHIFALAR_B = [{"yol": "/finance", "qadamlar": B_FIN}, {"yol": "/dashboard", "qadamlar": B_DSH},
               {"yol": "/reports", "qadamlar": B_REP}]

section("1. Lokal server + jsdom")
node = shutil.which("node")
check("U0 node topildi", node is not None)
NAT, NATB = {}, {}
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
    sj = os.path.join(_T, "a117u.js")
    with open(sj, "w", encoding="utf-8") as f:
        f.write(NODE_JS)

    def yurgiz(login, sahifalar, fayl):
        import httpx
        lr = httpx.post(base + "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False,
                        timeout=30)
        cookie = "; ".join(hh.split(";")[0] for hh in lr.headers.get_list("set-cookie"))
        pj = os.path.join(_T, fayl)
        with open(pj, "w", encoding="utf-8") as f:
            json.dump(sahifalar, f, ensure_ascii=False)
        k = subprocess.run([node, sj, base, cookie, pj], capture_output=True, text=True, timeout=900, env=env)
        try:
            return json.loads((k.stdout or "").strip().splitlines()[-1])
        except Exception as e:             # noqa: BLE001
            return {"fatal": f"{type(e).__name__}: {e}; stdout={(k.stdout or '')[-400:]} stderr={(k.stderr or '')[-400:]}"}
    try:
        NAT = yurgiz("u117_admin", SAHIFALAR_A, "sahifalar_a.json")
        NATB = yurgiz("u117_b", SAHIFALAR_B, "sahifalar_b.json")
    finally:
        server.should_exit = True
        th.join(timeout=10)
N = dict(NAT.get("natija") or {})
N.update(NATB.get("natija") or {})
check("U0 sahifalar 200, ssenariy tugadi (A va B)", "fatal" not in NAT and "fatal" not in NATB
      and len(NAT.get("sahifa") or {}) == len(SAHIFALAR_A) and len(NATB.get("sahifa") or {}) == len(SAHIFALAR_B)
      and all(v == 200 for v in list((NAT.get("sahifa") or {}).values()) + list((NATB.get("sahifa") or {}).values())),
      {k: (NAT.get(k), NATB.get(k)) for k in ("sahifa", "fatal", "xato")})


def g(nom, kalit=None, std=None):
    v = N.get(nom)
    if kalit is None:
        return v
    return v.get(kalit, std) if isinstance(v, dict) else std


section("S. Sozlamalar — yo'nalishlar")
_q = {r.get("id"): r for r in (g("s1", "qatorlar") or [])}
_as = _q.get(str(Y_ASOSIY), {})
_me = _q.get(str(Y_M), {})
_bo = _q.get(str(Y_BOSH), {})
_ya = _q.get(str(Y_YASH), {})
check("S1 ro'yxat: 5 yo'nalish (yashirini ham), asosiy birinchi; asosiyda «Asosiy» belgisi, yashirish / o'chirish YO'Q",
      len(_q) == 5 and (g("s1", "qatorlar") or [{}])[0].get("id") == str(Y_ASOSIY) and "Asosiy" in _as.get("chip", [])
      and not any("Yashirish" in t or "O'chirish" in t for t in _as.get("tugma", [])), g("s1"))
check("S2 ishlatilgan (MRP turi) — ishlatilishi ko'rinadi, «Yashirish» bor, «O'chirish» YO'Q; ishlatilmagan — «O'chirish» bor",
      any("MRP turi: 1" in c for c in _me.get("chip", [])) and "Yashirish" in _me.get("tugma", [])
      and "O'chirish" not in _me.get("tugma", []) and "O'chirish" in _bo.get("tugma", [])
      and "ishlatilmagan" in _bo.get("chip", []), [_me, _bo])
check("S3 yashirin yo'nalish — «Yashirin» belgisi va «Ko'rsatish» tugmasi", "Yashirin" in _ya.get("chip", [])
      and "Ko'rsatish" in _ya.get("tugma", []), _ya)
check("S4 XSS: nom maydon QIYMATI sifatida (HTML emas), rasm elementi yo'q, skript bajarilmadi",
      _q.get(str(Y_X), {}).get("nom") == XSS and g("s1", "img") == 0 and g("s1", "xss") == 0, _q.get(str(Y_X)))
check("S5 bo'sh nom — so'rov YUBORILMAYDI, sababi ko'rinadi", g("s2", "post") == 0 and "nomini kiriting" in (g("s2", "status") or ""),
      g("s2"))
_p3 = g("s3", "post") or []
check("S6 qo'shish: POST {nom: 'Plastik'}, ro'yxat yangilandi, maydon tozalandi",
      len(_p3) == 1 and _p3[0].get("body") == {"nom": "Plastik"} and "Plastik" in (g("s3", "yangi") or [])
      and g("s3", "input") == "", g("s3"))
check("S7 takror nom — server sababi holat qatorida («allaqachon bor»)", g("s4", "post") == 1
      and "allaqachon" in (g("s4", "status") or ""), g("s4"))
_p5 = g("s5", "put") or []
check("S8 nomini saqlash: PUT {nom}, ro'yxatda yangi nom", len(_p5) == 1 and _p5[0].get("body") == {"nom": "Metall konstruksiya"}
      and "Metall konstruksiya" in (g("s5", "nomlar") or []), g("s5"))
check("S9 o'chirish — birinchi bosish faqat so'raydi (so'rov yo'q, `confirm()` yo'q), ikkinchisi DELETE; qator yo'qoldi",
      g("s6", "del") == 0 and "Yana bosing" in (g("s6", "matn") or "") and g("s6", "bor") is True and g("s6", "confirm") == 0
      and g("s7", "del") == 1 and g("s7", "bor") is False, [g("s6"), g("s7")])
_p8 = g("s8", "put") or []
check("S10 ko'rsatish: PUT {yashirin: false} → «Yashirish» tugmasi; qayta yashirish → «Yashirin» belgisi",
      len(_p8) == 1 and _p8[0].get("body") == {"yashirin": False} and "Yashirish" in (g("s8", "tugma") or [])
      and "Yashirin" in (g("s9", "chip") or []), [g("s8"), g("s9")])

section("P. Ishlab chiqarish — mahsulot turi yo'nalishi")
_opts = g("p1", "opts") or []
check("P1 tur oynasida «Yo'nalish» tanlovi: bo'sh + ko'rinadigan yo'nalishlar (yashirin / o'chirilgan yo'q), XSS nomi matn",
      [o[0] for o in _opts][:4] == ["", str(Y_ASOSIY), str(Y_M), str(Y_X)] and [o[1] for o in _opts][4:] == ["Plastik"]
      and [o[1] for o in _opts][3] == XSS and g("p1", "img") == 0 and g("p1", "pty") == [o[0] for o in _opts], _opts)
check("P2 yo'nalishsiz saqlash — so'rov YO'Q, xato xabari, oyna ochiq", g("p2", "post") == 0
      and "Yo'nalishni tanlang" in str((g("p2", "xabar") or {}).get("t")) and g("p2", "modal") is True, g("p2"))
_pp = g("p3", "post") or []
check("P3 yo'nalish bilan — POST tanasida yonalish_id (son)", len(_pp) == 1 and _pp[0].get("yonalish_id") == Y_M, _pp)
check("P4 jadval: Travertin — «🧭 Metall …» belgisi, «Yo'nalish» tugmasi; belgisiz — «Yo'nalish belgilanmagan» va «Yo'nalish tanlash»",
      any("Metall" in c for c in ((g("p4", "m") or {}).get("chip") or []))
      and "Yo'nalish" in ((g("p4", "m") or {}).get("tugma") or [])
      and "Yo'nalish belgilanmagan" in ((g("p4", "n") or {}).get("chip") or [])
      and "Yo'nalish tanlash" in ((g("p4", "n") or {}).get("tugma") or []), g("p4"))
_pa = g("p5", "patch") or []
check("P5 biriktirish oynasi: tur nomi, bo'sh qiymat bilan ochiladi; PATCH {yonalish_id}; oyna yopildi",
      "U117 Belgisiz" in str((g("p5", "oldin") or {}).get("tur")) and (g("p5", "oldin") or {}).get("qiymat") == ""
      and (g("p5", "oldin") or {}).get("ochiq") is True and len(_pa) == 1 and _pa[0].get("body") == {"yonalish_id": Y_M}
      and f"/api/production/product-types/{PT_N}" in _pa[0].get("url", "") and g("p5", "ochiq") is False, g("p5"))

section("K. Hodimlar — yo'nalish tanlovi")
_ko = g("k1", "opts") or []
check("K1 tanlov: «Umumiy» + ko'rinadigan yo'nalishlar (Gips yo'q), XSS nomi matn",
      [o[0] for o in _ko][:4] == ["umumiy", str(Y_ASOSIY), str(Y_M), str(Y_X)] and [o[1] for o in _ko][4:] == ["Plastik"]
      and [o[1] for o in _ko][3] == XSS and g("k1", "img") == 0 and not any("Gips" in o[1] for o in _ko), _ko)
check("K2 yo'nalish tanlanmasa — so'rov YO'Q, xato matni", g("k2", "post") == 0 and "Yo'nalishni tanlang" in (g("k2", "xato") or ""),
      g("k2"))
_kp = g("k3", "post") or []
check("K3 «Umumiy» — POST tanasida yonalish_id: null (production_type yuborilmaydi)",
      len(_kp) == 1 and "yonalish_id" in _kp[0] and _kp[0]["yonalish_id"] is None and "production_type" not in _kp[0], _kp)
_k4 = g("k4", "opts") or []
check("K4 yashirin yo'nalishli hodim: vaqtincha «(yashirin)» varianti qo'shildi va tanlangan",
      any(o[0] == str(Y_YASH) and "(yashirin)" in o[1] and o[2] for o in _k4) and g("k4", "qiymat") == str(Y_YASH), _k4)
_k5 = g("k5", "put") or []
check("K5 saqlash — yo'nalish YO'QOLMADI (PUT tanasida o'sha id)", len(_k5) == 1 and _k5[0].get("yonalish_id") == Y_YASH, _k5)

section("M. Moliya — yo'nalishlar bo'yicha sof foyda, G6-09")
_API = g("f1", "api") or {}
_REPJ = g("f1", "rep") or {}
_sp = _API.get("yonalishlar") or []


def _f(v):
    n = int(round(float(v or 0)))
    return ("−" if n < 0 else "") + str(abs(n))


def _toza(x):
    return "".join(str(x or "").split())


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


_sof_k = [_f(((y.get("som") or {}).get("sof_foyda"))) for y in _sp] + [_f((_API.get("jami") or {}).get("sof_foyda"))]
_sof_s = [_toza(x) for x in (g("f1", "sof") or [])]
_bosh_k = [y.get("nom", "") + (" (yashirin)" if y.get("yashirin") else "") for y in _sp] + ["Jami"]
check("M1 bo'lim ko'rinadi; ustunlar = yo'nalishlar (yashirini «(yashirin)» bilan) + Jami; «Sof foyda» qatori = server",
      g("f1", "bolim") is True and len(_sp) >= 4 and g("f1", "bosh") == _bosh_k and _sof_s == _sof_k,
      [g("f1", "bosh"), _bosh_k, _sof_s, _sof_k])
_yig = sum(int(round(_num((y.get("som") or {}).get("sof_foyda")))) for y in _sp)
check("M2 yig'indi: ustunlar sof foydasi = Jami = Moliya sof foydasi (sahifa ko'rsatgan hisobot bilan, so'mgacha)",
      _yig == int(round(_num((_API.get("jami") or {}).get("sof_foyda")))) == int(round(_num(_REPJ.get("sof_foyda"))))
      and "Moliya hisobotidagi sof foyda" in (g("f1", "tekshir") or "") and "daromad ulushiga qarab" in (g("f1", "tekshir") or ""),
      [_yig, (_API.get("jami") or {}).get("sof_foyda"), _REPJ.get("sof_foyda"), g("f1", "tekshir")])
_belg = [y for y in _sp if y.get("belgilanmagan")]
check("M3 «Belgilanmagan» ustuni va ogohlantirish (yo'nalishsiz MRP turi nomi bilan)",
      len(_belg) == 1 and "U117 Belgisiz2" in (_API.get("belgilanmagan_turlar") or [])
      and g("f1", "ogoh_vis") is True and "U117 Belgisiz2" in (g("f1", "ogoh") or "")
      and _belg[0].get("nom") in (g("f1", "bosh") or []), [g("f1", "ogoh"), _API.get("belgilanmagan_turlar"), _belg])
check("M4 XSS: jadval sarlavhasida nom MATN; jadval, ogohlantirish va doira afsonasida rasm elementi yo'q, skript bajarilmadi",
      XSS in (g("f1", "bosh") or []) and g("f1", "img") == 0 and g("f1", "xss") == 0,
      [g("f1", "bosh"), g("f1", "img"), g("f1", "xss")])
_tn = _num(_REPJ.get("tannarx_jami"))
check("M5 «Tannarx» kartasi to'ldirilgan; eski «Gips vs Penoplast» tugmasi yo'q, PDF tugmasi bo'limda",
      g("f1", "tannarx_karta") not in (None, "", "—") and _tn > 0 and g("f1", "pdf") is True and g("f1", "eski_pdf") is False,
      [g("f1", "tannarx_karta"), _tn, g("f1", "pdf"), g("f1", "eski_pdf")])
check("M6 xarajat tafsiloti: «Tayyor mahsulot sotuvi tannarxi» qatori (30 000), «Turlar bo'yicha» guruhi yo'q",
      len(g("f1", "tm_tannarx") or []) == 1 and "30000" in _toza((g("f1", "tm_tannarx") or [""])[0])
      and int(round(_num(_REPJ.get("fp_sales_tannarx")))) == 30000 and g("f1", "turlar") is False,
      [g("f1", "tm_tannarx"), _REPJ.get("fp_sales_tannarx"), g("f1", "turlar")])
_jx = _num(_REPJ.get("jami_xarajat")) + _tn
check("M7 «Jami xarajat» = xarajat + tannarx (tayyor mahsulot tannarxi ham)",
      str(int(round(_jx))) in _toza(g("f1", "jami_xarajat")), [g("f1", "jami_xarajat"), _jx])
check("M8 daromad doirasi — daromadli yo'nalishlar bo'yicha (Belgilanmagan ham), XSS nomi matn",
      g("f1", "donut") == "" and {"Metall konstruksiya", XSS, _belg[0].get("nom") if _belg else "?"} <= set(g("f1", "legend") or []),
      [g("f1", "donut"), g("f1", "legend")])
_fo = g("f2", "opts") or []
check("M9 xarajat oynasi: «Umumiy» + ko'rinadigan yo'nalishlar (Gips / penoplast qiymati yo'q), XSS matn",
      [o[0] for o in _fo][:4] == ["", str(Y_ASOSIY), str(Y_M), str(Y_X)] and [o[1] for o in _fo][4:] == ["Plastik"]
      and [o[1] for o in _fo][3] == XSS and g("f2", "img") == 0 and not any(o[0] in ("penoplast", "gips") for o in _fo), _fo)
_f3 = g("f3", "post") or []
check("M10 yangi xarajat: POST tanasida yonalish_id (son), production_type yo'q", len(_f3) == 1
      and _f3[0].get("yonalish_id") == Y_M and "production_type" not in _f3[0], _f3)
_f4 = g("f4", "put") or []
check("M11 yashirin yo'nalishli xarajatni tahrirlash: vaqtincha variant tanlangan, PUT da o'sha id (yo'qolmaydi)",
      (g("f4", "oldin") or {}).get("qiymat") == str(Y_YASH) and str(Y_YASH) in ((g("f4", "oldin") or {}).get("opts") or [])
      and len(_f4) == 1 and _f4[0].get("yonalish_id") == Y_YASH, g("f4"))

section("R. Kirim — yo'nalish tanlovi")
_ro = g("r1", "opts") or []
check("R1 tanlov: «Umumiy» + ko'rinadigan yo'nalishlar; yashirin select bilan bir xil; XSS matn",
      [o[0] for o in _ro][:4] == ["", str(Y_ASOSIY), str(Y_M), str(Y_X)] and g("r1", "sel") == [o[0] for o in _ro]
      and g("r1", "img") == 0, [_ro, g("r1", "sel")])
check("R2 tanlash — yashirin select qiymati = yo'nalish id, tanlangan belgisi",
      g("r2", "qiymat") == str(Y_M) and g("r2", "chosen") is True and g("r2", "active") == [str(Y_M)], g("r2"))
_r3 = g("r3", "post") or []
s = SessionLocal()
try:
    _kr = s.query(InventoryReceipt).filter(InventoryReceipt.company_id == 1,
                                           InventoryReceipt.supplier_id == ID["SUP"]).all()
    _kr_yon = [getattr(k, "yonalish_id", "?") for k in _kr]
finally:
    s.close()
check("R3 kirimni saqlash: POST tanasida yonalish_id (son); hujjat shu yo'nalish bilan yozildi",
      len(_r3) == 1 and _r3[0].get("yonalish_id") == Y_M and "production_type" not in _r3[0] and _kr_yon == [Y_M],
      [_r3, _kr_yon])

section("D. Dashboard va Hisobotlar — grafiklar")
check("D1 Dashboard: yo'nalishlar kartasi ko'rinadi, grafik ustunlari — yo'nalish nomlari; bugungi summa qatorlari; eski sarlavha yo'q",
      g("d1", "karta") == "" and "Metall konstruksiya" in (g("d1", "labels") or []) and g("d1", "img") == 0
      and g("d1", "xss") == 0 and g("d1", "eski") is False, g("d1"))
check("D2 Hisobotlar: «Yo'nalishlar — daromad dinamikasi» ko'rinadi, ustunlar — yo'nalish nomlari",
      g("h1", "bolim") == "" and "Metall konstruksiya" in (g("h1", "labels") or []) and g("h1", "eski") is False, g("h1"))

section("B. Bitta yo'nalishli korxona — bo'limlar yashirin")
check("B1 Moliya: yo'nalishlar bo'limi va daromad doirasi YASHIRIN; xarajat oynasida «Umumiy» + «Penoplast»",
      g("bf", "bolim") is False and g("bf", "donut") == "none" and g("bf", "opts") == ["Umumiy", "Penoplast"], g("bf"))
check("B2 Dashboard va Hisobotlar: yo'nalishlar grafiklari YASHIRIN", g("bd", "karta") == "none" and g("bh", "bolim") == "none",
      [g("bd"), g("bh")])

section("X. Xatolar")
check("X1 JS xatosi / 5xx yo'q (A va B)", not (NAT.get("xato") or []) and not (NAT.get("api_xato") or [])
      and not (NATB.get("xato") or []) and not (NATB.get("api_xato") or []),
      [NAT.get("xato"), NAT.get("api_xato"), NATB.get("xato"), NATB.get("api_xato")])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
