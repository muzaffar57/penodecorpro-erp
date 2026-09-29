#!/usr/bin/env python3
"""
test_mrp_sahifa_ui.py — kech113: Ishlab chiqarish (MRP) sahifasi, variant "A — Jadval + oynalar" — HAQIQIY sahifa
(server bergan HTML, `templates/production.html` + `base.html` skriptlari) jsdom da, HAQIQIY lokal server bilan
(uvicorn, test bazasi, admin sessiyasi). Soxta javob yo'q: ro'yxat, reja, retsept hisobi — serverning o'zidan.

NIMA UCHUN KERAK: egasi qarori "MRP asosiy: 1–4" (kech113) — (1) hamma yozuv o'zbekcha; (2) retsept oynasida har qator
narxi va taxminiy tannarx, «Qachon ishlatiladi» tanlovi saqlanadi, izoh yo'qolmaydi; (3) «Yangi ishlab chiqarish»
oynasida xomashyo yetadimi, «Miqdorni N qilish», «Boshlash» shu yerning o'zida, o'nlik vergul ("2,5"); (4) ro'yxatda sana
(Toshkent), birlik, buyurtma raqami va mijoz, holat chiplari, mahsulot / qidiruv / davr saralashi, qoralama uchun
«xomashyo yetadi / yetmaydi» belgisi; boshlash / yakunlash / batafsil / bekor qilish oynalari. Foydalanuvchi kiritgan
matn (mahsulot, material, mijoz nomi) HTML bo'lib chizilmasligi SHART.

BO'LIMLAR: U — yuklash va kartalar; R — ro'yxat va saralash; Y — yangi ishlab chiqarish oynasi; O — boshlash / yakunlash /
batafsil / bekor oynalari; T — retsept oynasi; M — mahsulot turi oynasi; H — HTML in'ektsiya; X — xatolar.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan ham. Asl kodga qarshi QULAMAYDI (sahifa funksiyalari yo'q — tekshiruvlar
yiqiladi). ISHLATISH: NODE_PATH=$(npm root -g) python3 tools/test_mrp_sahifa_ui.py
"""
import os
import sys
import json
import time
import shutil
import socket
import tempfile
import datetime
import threading
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_sahifa_ui_test"
_T = tempfile.mkdtemp()
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'mrp_sahifa_ui_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402
from production_models import ProductionOrder      # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        detail = f"{detail} [{type(e).__name__}: {e}]"
        cond = False
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
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


# ══════════════════════════════════════════════════════════════
# Fikstura (API orqali — sahifa ko'radigan haqiqiy ma'lumot)
# ══════════════════════════════════════════════════════════════
section("0. Fikstura")
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "MRU_A", "Parol123!", UserRole.ADMIN, "MRU Admin", company_id=1)
_db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "MRU_A", "password": "Parol123!"}, follow_redirects=False)
ID = {}


def mat(nom, unit, stock, price):
    return (js(req(C, "post", "/api/inventory", json={"item_name": nom, "unit": unit, "stock_quantity": stock,
                                                      "price_per_unit": price})) or {}).get("id")


XSS_TUR = 'MRU <img src=x onerror="window.__xss=1">Dekor'
XSS_MAT = "MRU \"'><i class=xpm>Material"
XSS_MIJOZ = "MRU Mijoz <b>qalin</b>"
ID["qum"] = mat("MRU Qum", "kg", 480, 820)
ID["kley"] = mat("MRU Kley", "kg", 36, 3150)
ID["setka"] = mat("MRU Setka", "m²", 120, 2600)
ID["boyoq"] = mat("MRU Bo'yoq", "kg", 18, 24000)
ID["xmat"] = mat(XSS_MAT, "kg", 100, 1000)
ID["trav"] = (js(req(C, "post", "/api/production/product-types", json={
    "name": "MRU Travertin", "unit": "m²", "input_template": "quantity_only", "pricing_formula": "unit_based",
    "supports_coating": True, "coating_price_multiplier": 2})) or {}).get("id")
_b = js(req(C, "post", "/api/production/boms", json={
    "product_type_id": ID["trav"], "variant_name": "Standart", "batch_quantity": 1,
    "items": [{"inventory_id": ID["qum"], "quantity": 5, "notes": "izoh-qator"},
              {"inventory_id": ID["kley"], "quantity": 1, "scrap_factor_percent": 10},
              {"inventory_id": ID["setka"], "quantity": 1, "scrap_factor_percent": 5},
              {"inventory_id": ID["boyoq"], "quantity": 0.15, "is_optional": True, "is_coating": True,
               "fixed_cost_per_unit": 800}]})) or {}
ID["trav_b"] = _b.get("id")
ID["xtur"] = (js(req(C, "post", "/api/production/product-types", json={
    "name": XSS_TUR, "unit": "dona", "input_template": "quantity_only", "pricing_formula": "unit_based"})) or {}).get("id")
ID["xtur_b"] = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": ID["xtur"], "variant_name": "Standart <u>v</u>", "batch_quantity": 1,
    "items": [{"inventory_id": ID["xmat"], "quantity": 2}]})) or {}).get("id")
ID["loyiha"] = (js(req(C, "post", "/api/projects", json={"project_name": "MRU Loyiha", "client_name": XSS_MIJOZ})) or {}).get("id")
_o = js(req(C, "post", "/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": ID["loyiha"], "order_type": "product", "deadline": "2026-12-10", "is_draft": False,
    "items": [{"name": "MRU Travertin Q", "category": "mrp_product", "quantity": 10, "unit_price": 50000, "is_coated": True,
               "product_type_id": ID["trav"]}]})) or {}
ID["o"] = _o.get("id")
ORD = _o.get("order_number")
ID["d_q"] = ((_o.get("items") or [{}])[0]).get("id")


def po(tana, *amallar):
    r = req(C, "post", "/api/production/orders", json=dict({"product_type_id": ID["trav"], "bom_id": ID["trav_b"],
                                                          "source_type": "warehouse_stock"}, **tana))
    pid = ((js(r) or {}).get("production_order") or {}).get("id")
    for a in amallar:
        req(C, "post", f"/api/production/orders/{pid}/{a}")
    return pid


ID["p_yakun"] = po({"quantity": 3}, "start", "complete")
ID["p_bekor"] = po({"quantity": 1}, "cancel")
ID["p_jarayon"] = po({"quantity": 5}, "start")
ID["p_ok"] = po({"quantity": 20})
ID["p_yet"] = po({"quantity": 40})
ID["p_mijoz"] = po({"quantity": 4, "source_type": "customer_order", "source_order_item_id": ID["d_q"]})
ID["p_xss"] = po({"product_type_id": ID["xtur"], "bom_id": ID["xtur_b"], "quantity": 2})
ID["p_vaqt"] = po({"quantity": 2})
_s = SessionLocal()
try:
    _p = _s.get(ProductionOrder, ID["p_vaqt"])
    _p.created_at = datetime.datetime(2026, 9, 28, 20, 30)      # UTC → Toshkent 29.09.2026 01:30
    _s.commit()
finally:
    _s.close()
check("F1 fikstura: materiallar, 2 mahsulot turi (biri HTML nomli), mijoz buyurtmasi, 8 ishlab chiqarish (hamma holatda)",
      _lr.status_code == 302 and all(v is not None for v in ID.values()) and ORD, ID)
_bugun = __import__("database").tashkent_date()
JORIY = f"{_bugun.year:04d}-{_bugun.month:02d}"
API_ROYXAT = js(req(C, "get", "/api/production/orders", params={"oy": JORIY})) or []
API_40 = js(req(C, "get", "/api/production/orders/preview", params={
    "product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 40, "source_type": "warehouse_stock"})) or {}

# ══════════════════════════════════════════════════════════════
# jsdom ssenariysi (node)
# ══════════════════════════════════════════════════════════════
NODE_JS = r"""
let JSDOM, VirtualConsole, ResourceLoader;
try { ({ JSDOM, VirtualConsole, ResourceLoader } = require("jsdom")); }
catch (e) { console.log(JSON.stringify({ fatal: "jsdom topilmadi: " + String(e.message).slice(0, 200) })); process.exit(3); }
const base = process.argv[2], cookie = process.argv[3];
const qadamlar = JSON.parse(require("fs").readFileSync(process.argv[4], "utf8"));
class FaqatOzimiz extends ResourceLoader {
  fetch(url, options) { return url.startsWith(base) ? super.fetch(url, options) : null; }
}
const kut = ms => new Promise(r => setTimeout(r, ms));
const res = { status: 0, xato: [], api_xato: [], natija: {} };
process.on("unhandledRejection", e => res.xato.push("va'da: " + String((e && (e.message || e)) || "").slice(0, 200)));
process.on("uncaughtException", e => res.xato.push("xato: " + String((e && (e.message || e)) || "").slice(0, 200)));
(async () => {
  const r = await fetch(base + "/production", { headers: { cookie }, redirect: "manual" });
  res.status = r.status;
  const html = await r.text();
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => { const m = String((e && (e.message || e)) || "").slice(0, 300); if (!/Not implemented/.test(m)) res.xato.push(m); });
  let pending = 0, lastActive = Date.now();
  const sahifaUrl = base + "/production";
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
          const resp = await fetch(url, Object.assign({}, o, { headers: h, redirect: "manual" }));
          if (resp.status >= 500) res.api_xato.push(resp.status + " " + url.slice(base.length, base.length + 120));
          w.__sorovlar.push({ url: url.slice(base.length), method: o.method || "GET", body: o.body || null, status: resp.status });
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
    await kut(450);
    const t0 = Date.now();
    while (Date.now() - t0 < 15000) { await kut(80); if (pending === 0 && Date.now() - lastActive > 450) return; }
    res.xato.push("tarmoq 15 s ichida tinchimadi");
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
  res.xss = !!w.__xss;
  console.log(JSON.stringify(res));
  process.exit(0);
})().catch(e => { res.xato.push("yakuniy: " + String(e && e.message)); console.log(JSON.stringify(res)); process.exit(0); });
"""

YORDAM = r"""
window.__msg = [];
window.showMsg = (t, k) => { window.__msg.push([String(t), String(k || '')]); };
window.customConfirm = async () => true;
window.__m = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : null;
window.__qator = id => [...document.querySelectorAll('#po-list tr.po-qator')].find(tr => __m(tr.querySelector('.po-c-no')) === String(id)) || null;
window.__qatorlar = () => [...document.querySelectorAll('#po-list tr.po-qator')].map(tr => ({id: __m(tr.querySelector('.po-c-no')), matn: __m(tr)}));
window.__tanla = (id, v) => { const e = document.getElementById(id); e.value = String(v); e.dispatchEvent(new Event('change', {bubbles: true})); };
window.__yoz = (id, v) => { const e = document.getElementById(id); e.value = String(v); e.dispatchEvent(new Event('input', {bubbles: true})); };
window.__tugmalar = sel => [...document.querySelectorAll(sel + ' button')];
window.__tugma = (sel, matn) => __tugmalar(sel).find(b => __m(b) === matn) || null;
window.__boshi = (sel, matn) => __tugmalar(sel).find(b => (__m(b) || '').startsWith(matn)) || null;
window.__ochiq = id => document.getElementById(id).classList.contains('open');
window.__reja = () => ({
  jadval: [...document.querySelectorAll('#po-reja .xm-jadval tbody tr')].map(__m),
  sarlavha: __m(document.querySelector('#po-reja .xm-bosh')),
  ogoh: [...document.querySelectorAll('#po-reja .ogoh')].map(__m),
  tugma: __m(document.querySelector('#po-reja .ogoh button')),
  tannarx: __m(document.querySelector('#po-reja .tannarx-quti')),
  boshlash_yopiq: document.getElementById('po-boshlash-btn').disabled,
  miqdor: document.getElementById('po-f-quantity').value,
});
window.__oyna = () => ({
  sarlavha: __m(document.getElementById('snapshot-modal-title')),
  matn: __m(document.getElementById('snapshot-list')),
  jadval_bosh: [...document.querySelectorAll('#snapshot-list .xm-jadval th')].map(__m),
  jadval: [...document.querySelectorAll('#snapshot-list .xm-jadval tbody tr')].map(__m),
  tugmalar: __tugmalar('#snapshot-tugmalar').map(b => ({matn: __m(b), yopiq: b.disabled})),
  havolalar: [...document.querySelectorAll('#snapshot-tugmalar a')].map(a => ({matn: __m(a), href: a.getAttribute('href')})),
  ochiq: __ochiq('snapshot-modal'),
});
return true;
"""


def q(nom, amal=None, natija=None):
    return {"nom": nom, "amal": amal, "natija": natija}


T, X, P = ID["trav"], ID["xtur"], ID
QADAMLAR = [
    q("yordam", natija=YORDAM),
    q("yuklash", natija=r"""return {
      turlar: [...document.querySelectorAll('#pt-list .pt-card')].map(__m),
      po_soni: __m(document.getElementById('po-soni')),
      chiplar: __tugmalar('#po-holat-chiplar').map(__m),
      qatorlar: __qatorlar(),
      xulosa: __m(document.getElementById('po-xulosa')),
      davr: {qiymat: document.getElementById('po-davr').value,
             birinchi: __m(document.getElementById('po-davr').options[0]),
             oxirgi: __m(document.getElementById('po-davr').options[document.getElementById('po-davr').options.length - 1]),
             soni: document.getElementById('po-davr').options.length},
      royxat_matn: __m(document.getElementById('po-list')),
      oy_sorov: window.__sorovlar.filter(s => s.url.startsWith('/api/production/orders?')).map(s => s.url),
      mahsulotlar: [...document.getElementById('po-mahsulot').options].map(__m),
    };"""),
    q("chip_qoralama", amal="__boshi('#po-holat-chiplar', 'Qoralama').click();",
      natija="return {qatorlar: __qatorlar(), bosilgan: __boshi('#po-holat-chiplar', 'Qoralama').getAttribute('aria-pressed')};"),
    q("chip_hammasi", amal="__boshi('#po-holat-chiplar', 'Hammasi').click();", natija="return __qatorlar().length;"),
    q("mahsulot_filtr", amal=f"__tanla('po-mahsulot', {X});",
      natija="return {qatorlar: __qatorlar(), chiplar: __tugmalar('#po-holat-chiplar').map(__m)};"),
    q("qidiruv", amal=f"__tanla('po-mahsulot', ''); __yoz('po-qidiruv', {json.dumps(ORD or '')});", natija="return __qatorlar();"),
    q("qidiruv_raqam", amal=f"__yoz('po-qidiruv', '№{P['p_ok']}');", natija="return __qatorlar();"),
    q("davr_hammasi", amal="__yoz('po-qidiruv', ''); __tanla('po-davr', 'hammasi');",
      natija="return {qatorlar: __qatorlar().length, oxirgi: window.__sorovlar.filter(s => s.url.startsWith('/api/production/orders?')).pop()};"),
    # ── Yangi ishlab chiqarish oynasi ──
    q("yangi_ochish", amal=f"__tanla('po-davr', {json.dumps(JORIY)}); openProductionOrderModal(); __tanla('po-f-product-type', {T});",
      natija="""return {ochiq: __ochiq('po-modal'), bom: [...document.getElementById('po-f-bom').options].map(__m),
                birlik: __m(document.getElementById('po-f-birlik')), reja: __reja(),
                ixtiyoriy: __m(document.getElementById('po-optional-list'))};"""),
    q("yangi_40", amal="__yoz('po-f-quantity', '40');", natija="return __reja();"),
    q("yangi_maks", amal="document.querySelector('#po-reja .ogoh button').click();", natija="return __reja();"),
    q("yangi_vergul", amal="__yoz('po-f-quantity', '2,5');", natija="return __reja();"),
    q("yangi_notogri", amal="__yoz('po-f-quantity', '2,5,1');", natija="return __reja();"),
    q("yangi_boshlash", amal="__yoz('po-f-quantity', '2,5'); await new Promise(r => setTimeout(r, 700)); document.getElementById('po-boshlash-btn').click();",
      natija="return {ochiq: __ochiq('po-modal'), msg: window.__msg.slice(-1)[0], qatorlar: __qatorlar(), panel: document.getElementById('panel-orders').classList.contains('active')};"),
    q("mijoz", amal=f"openProductionOrderModal(); __tanla('po-f-product-type', {T}); await new Promise(r => setTimeout(r, 900)); "
                    "document.querySelector('#po-modal .segment button[data-manba=\"customer_order\"]').click();",
      natija="""return {detallar: [...document.getElementById('po-f-source-order-item').options].map(__m),
                segment: [...document.querySelectorAll('#po-modal .segment button')].map(b => b.getAttribute('aria-checked'))};"""),
    q("mijoz_detal", amal=f"__tanla('po-f-source-order-item', {P['d_q']});",
      natija="""const c = document.querySelector('#po-optional-list .po-opt');
                return Object.assign(__reja(), {qoplama_belgi: c ? c.checked : null, qoplama_qulf: c ? c.disabled : null,
                  izoh: __m(document.getElementById('po-source-order-hint'))});"""),
    q("mijoz_yop", amal="closeModal('po-modal');", natija="return __ochiq('po-modal');"),
    # ── Boshlash / yakunlash / batafsil / bekor ──
    q("oyna_yetmaydi", amal=f"__qator({P['p_yet']}).querySelector('.po-amallar .btn-dark').click();",
      natija="return __oyna();"),
    q("oyna_ok", amal=f"closeModal('snapshot-modal'); __qator({P['p_ok']}).querySelector('.po-amallar .btn-dark').click();",
      natija="return __oyna();"),
    q("oyna_ok_boshla", amal="document.getElementById('po-oyna-amal').click();",
      natija=f"return {{ochiq: __ochiq('snapshot-modal'), qator: __m(__qator({P['p_ok']})), msg: window.__msg.slice(-1)[0]}};"),
    q("oyna_yakunlash", amal=f"__qator({P['p_jarayon']}).querySelector('.po-amallar .btn-dark').click();", natija="return __oyna();"),
    q("oyna_yakunla", amal="document.getElementById('po-oyna-amal').click();",
      natija=f"return {{ochiq: __ochiq('snapshot-modal'), qator: __m(__qator({P['p_jarayon']})), msg: window.__msg.slice(-1)[0]}};"),
    q("batafsil", amal=f"__qator({P['p_yakun']}).querySelector('.po-amallar button').click();", natija="return __oyna();"),
    q("bekor_oyna", amal=f"closeModal('snapshot-modal'); __qator({P['p_mijoz']}).querySelector('.po-uch').click();",
      natija="return __oyna();"),
    q("bekor", amal="__tugma('#snapshot-tugmalar', 'Bekor qilish').click();",
      natija=f"return {{ochiq: __ochiq('snapshot-modal'), qator: __m(__qator({P['p_mijoz']})), msg: window.__msg.slice(-1)[0]}};"),
    q("bekor_batafsil", amal=f"__qator({P['p_bekor']}).querySelector('.po-amallar button').click();", natija="return __oyna();"),
    q("xss_oyna", amal=f"closeModal('snapshot-modal'); __qator({P['p_xss']}).querySelector('.po-amallar .btn-dark').click();",
      natija="return __oyna();"),
    # ── Retsept oynasi ──
    q("retsept", amal=f"closeModal('snapshot-modal'); switchProdTab('types'); await openBomModal({T}, {P['trav_b']});",
      natija=r"""return {
        sarlavha: __m(document.getElementById('bom-modal-title')),
        tarkib: __m(document.getElementById('bom-tarkib-sarlavha')),
        partiya_birlik: __m(document.getElementById('bom-batch-birlik')),
        qatorlar: [...document.querySelectorAll('#bom-items-wrap .bomitem-row')].map(r => ({
          material: __m(r.querySelector('.bi-inventory').selectedOptions[0]), miqdor: r.querySelector('.bi-quantity').value,
          birlik: __m(r.querySelector('.bi-birlik')), isrof: r.querySelector('.bi-scrap').value,
          narx: __m(r.querySelector('.bi-narx')), chiplar: __m(r.querySelector('.bi-chiplar')),
          sozlama: !r.querySelector('.bi-sozlama').hidden,
          qachon: (r.querySelector('.bi-sozlama input[type=radio]:checked') || {}).value || null,
          izoh: r.querySelector('.bi-notes').value})),
        jami: __m(document.getElementById('bom-jami')), ogoh: __m(document.getElementById('bom-ogoh')),
      };"""),
    q("retsept_ozgartir", amal=r"""const r = document.querySelectorAll('#bom-items-wrap .bomitem-row')[1];
        r.querySelector('.bi-sozlama-tugma').click();
        const rad = r.querySelector('.bi-sozlama input[value=tanlansa]'); rad.checked = true; rad.dispatchEvent(new Event('change', {bubbles: true}));
        const s = r.querySelector('.bi-scrap'); s.value = '12,5'; s.dispatchEvent(new Event('input', {bubbles: true}));""",
      natija=r"""const r = document.querySelectorAll('#bom-items-wrap .bomitem-row')[1];
        return {chiplar: __m(r.querySelector('.bi-chiplar')), narx: __m(r.querySelector('.bi-narx')),
                ixt: r.querySelector('.bi-optional').checked, qopl: r.querySelector('.bi-coating').checked,
                jami: __m(document.getElementById('bom-jami')), ogoh: __m(document.getElementById('bom-ogoh'))};"""),
    q("retsept_yangi_qator", amal=f"addBomItemRow(); await new Promise(r => setTimeout(r, 600)); "
                                  f"const rr = [...document.querySelectorAll('#bom-items-wrap .bomitem-row')].pop(); "
                                  f"const s = rr.querySelector('.bi-inventory'); s.value = '{P['xmat']}'; s.dispatchEvent(new Event('change', {{bubbles: true}})); "
                                  "const m = rr.querySelector('.bi-quantity'); m.value = '0,5'; m.dispatchEvent(new Event('input', {bubbles: true}));",
      natija=r"""const rr = [...document.querySelectorAll('#bom-items-wrap .bomitem-row')].pop();
        return {narx: __m(rr.querySelector('.bi-narx')), birlik: __m(rr.querySelector('.bi-birlik')),
                variantlar: [...rr.querySelector('.bi-inventory').options].map(__m)};"""),
    q("retsept_ochir", amal="[...document.querySelectorAll('#bom-items-wrap .bomitem-row')].pop().querySelector('.bomitem-del').click();",
      natija="return {soni: document.querySelectorAll('#bom-items-wrap .bomitem-row').length, jami: __m(document.getElementById('bom-jami'))};"),
    q("retsept_saqla", amal="await saveBom();",
      natija="return {ochiq: __ochiq('bom-modal'), put: window.__sorovlar.filter(s => s.method === 'PUT').pop()};"),
    q("retsept_xato", amal=f"await openBomModal({T}, {P['trav_b']}); await new Promise(r => setTimeout(r, 600)); "
                           "const r = document.querySelectorAll('#bom-items-wrap .bomitem-row')[0]; r.querySelector('.bi-quantity').value = 'abc'; "
                           "window.__msg = []; await saveBom();",
      natija="return {msg: window.__msg.slice(-1)[0], ochiq: __ochiq('bom-modal')};"),
    q("retsept_xss", amal=f"closeModal('bom-modal'); await openBomModal({X}, {P['xtur_b']});",
      natija="return {sarlavha: __m(document.getElementById('bom-modal-title')), tanlangan: __m(document.querySelector('#bom-items-wrap .bi-inventory').selectedOptions[0])};"),
    # ── Mahsulot turi ──
    q("tur_yangi", amal=r"""closeModal('bom-modal'); openProductTypeModal();
        document.getElementById('pt-f-name').value = 'MRU Yangi tur'; document.getElementById('pt-f-unit').value = 'm²';
        __tanla('pt-f-pricing-formula', 'fixed_price'); document.getElementById('pt-f-fixed-price').value = '150 000';
        const c = document.getElementById('pt-f-supports-coating'); c.checked = true; c.dispatchEvent(new Event('change', {bubbles: true}));
        document.getElementById('pt-f-coating-mult').value = '2,5'; await saveProductType();""",
      natija="return {post: window.__sorovlar.filter(s => s.method === 'POST' && s.url === '/api/production/product-types').pop(), ochiq: __ochiq('pt-modal')};"),
    q("tur_xato", amal=r"""openProductTypeModal(); document.getElementById('pt-f-name').value = 'MRU Xato tur';
        document.getElementById('pt-f-unit').value = 'dona'; __tanla('pt-f-pricing-formula', 'fixed_price');
        document.getElementById('pt-f-fixed-price').value = 'o\'n ming'; window.__msg = []; await saveProductType();""",
      natija="return {msg: window.__msg.slice(-1)[0], ochiq: __ochiq('pt-modal')};"),
    q("yakun", amal="closeModal('pt-modal'); await loadProductTypes(); switchProdTab('orders');",
      natija=r"""return {xss: !!window.__xss, img: document.querySelectorAll('img[onerror]').length,
        xpm: document.querySelectorAll('i.xpm').length, qalin: [...document.querySelectorAll('b')].filter(b => b.textContent === 'qalin').length,
        u: [...document.querySelectorAll('u')].filter(b => b.textContent === 'v').length,
        turlar: [...document.querySelectorAll('#pt-list .pt-card')].map(__m)};"""),
]

section("1. Lokal server + jsdom")
node = shutil.which("node")
check("node topildi", node is not None)
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
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
        s.close()
        return p

    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    check("uvicorn ishga tushdi", server.started)
    base = f"http://127.0.0.1:{port}"
    try:
        import httpx
        lr = httpx.post(base + "/login", data={"username": "MRU_A", "password": "Parol123!"}, follow_redirects=False, timeout=30)
        cookie = "; ".join(h.split(";")[0] for h in lr.headers.get_list("set-cookie"))
        pj = os.path.join(_T, "qadamlar.json")
        with open(pj, "w", encoding="utf-8") as f:
            json.dump(QADAMLAR, f, ensure_ascii=False)
        sj = os.path.join(_T, "mrp_sahifa.js")
        with open(sj, "w", encoding="utf-8") as f:
            f.write(NODE_JS)
        k = subprocess.run([node, sj, base, cookie, pj], capture_output=True, text=True, timeout=600, env=env)
        try:
            NAT = json.loads((k.stdout or "").strip().splitlines()[-1])
        except Exception as e:             # noqa: BLE001
            NAT = {"fatal": f"{type(e).__name__}: {e}; stdout={k.stdout[-400:]} stderr={k.stderr[-400:]}"}
    finally:
        server.should_exit = True
        th.join(timeout=10)
N = NAT.get("natija") or {}
check("S0 sahifa 200, ssenariy tugadi", NAT.get("status") == 200 and "fatal" not in NAT and N.get("yordam") is True,
      {k: NAT.get(k) for k in ("status", "fatal", "xato")})


def n(nom):
    v = N.get(nom)
    return v if isinstance(v, dict) else {}


def qatorlar(nom, kalit=None):
    v = N.get(nom)
    if kalit:
        v = (v or {}).get(kalit) if isinstance(v, dict) else None
    return v if isinstance(v, list) else []


def qator_matn(royxat, pid):
    return next((x.get("matn") or "" for x in royxat if isinstance(x, dict) and x.get("id") == str(pid)), "")


# ══════════════════════════════════════════════════════════════
section("U. Yuklash — mahsulot turlari kartalari")
# ══════════════════════════════════════════════════════════════
_y = n("yuklash")
_trav_k = next((t for t in _y.get("turlar") or [] if t.startswith("MRU Travertin")), "")
check("U1 karta o'zbekcha: «Birlik: m²», «Kiritish: Faqat miqdor», «Narx: birlik narxi», «Qoplama mumkin · ×2»",
      all(x in _trav_k for x in ("Birlik: m²", "Kiritish: Faqat miqdor", "Narx: birlik narxi", "Qoplama mumkin · ×2")), _trav_k)
check("U2 retsept qatori: «Standart (1 m² uchun)», «4 ta material», «Tahrirlash»",
      all(x in _trav_k for x in ("Standart (1 m² uchun)", "4 ta material", "Tahrirlash")), _trav_k)
check("U3 inglizcha texnik qiymat yo'q (quantity_only / unit_based / BOM)",
      all(x not in " ".join(_y.get("turlar") or []) for x in ("quantity_only", "unit_based", "BOM")), _y.get("turlar"))

# ══════════════════════════════════════════════════════════════
section("R. Ro'yxat, holat chiplari, saralash")
# ══════════════════════════════════════════════════════════════
_q = _y.get("qatorlar") or []
check("R1 davr — server oyi (data-joriy-oy), 12 oy + «Hammasi»; ro'yxat serverdan ?oy= bilan so'raldi",
      lambda: _y["davr"]["qiymat"] == JORIY and _y["davr"]["soni"] == 13 and _y["davr"]["oxirgi"] == "Hammasi"
      and any(f"oy={JORIY}" in u for u in _y["oy_sorov"]), _y.get("davr"))
check("R2 qatorlar soni = server ro'yxati (shu oy); yorliqdagi son ham", lambda: len(_q) == len(API_ROYXAT) == int(_y["po_soni"]),
      (len(_q), len(API_ROYXAT), _y.get("po_soni")))
_holat_soni = {h: sum(1 for x in API_ROYXAT if x.get("status") == h) for h in ("draft", "in_progress", "completed", "cancelled")}
check("R3 chiplar: «Hammasi · N», «Qoralama · N», «Jarayonda · N», «Yakunlandi · N», «Bekor qilingan · N» (server bilan)",
      lambda: _y["chiplar"] == [f"Hammasi · {len(API_ROYXAT)}", f"Qoralama · {_holat_soni['draft']}",
                                f"Jarayonda · {_holat_soni['in_progress']}", f"Yakunlandi · {_holat_soni['completed']}",
                                f"Bekor qilingan · {_holat_soni['cancelled']}"], _y.get("chiplar"))
_mj = qator_matn(_q, ID["p_mijoz"])
check("R4 mijoz buyurtmasi qatori: buyurtma raqami, mijoz (HTML emas — matn), «qoplamali», «Qoralama», «✓ xomashyo yetadi», "
      "≈ 58 780 so'm (4 × 14 695), 14 695 so'm / m²",
      all(x in _mj for x in (ORD or "?", XSS_MIJOZ, "qoplamali", "Qoralama", "✓ xomashyo yetadi", "≈ 58 780 so'm",
                              "14 695 so'm / m²", "4 m²", "«Standart» retsepti")), _mj)
check("R5 kley yetmaydigan qoralama: «✗ MRU Kley yetmaydi», «Omborga», «Tayyor mahsulotlarga»",
      all(x in qator_matn(_q, ID["p_yet"]) for x in ("✗ MRU Kley yetmaydi", "Omborga", "Tayyor mahsulotlarga", "40 m²")),
      qator_matn(_q, ID["p_yet"]))
check("R6 jarayondagi: «Jarayonda», «… dan», «≈ 51 475 so'm», «Yakunlash»",
      all(x in qator_matn(_q, ID["p_jarayon"]) for x in ("Jarayonda", " dan", "≈ 51 475 so'm", "Yakunlash")),
      qator_matn(_q, ID["p_jarayon"]))
check("R7 yakunlangan: «Yakunlandi», «30 885 so'm», «10 295 so'm / m²», «Batafsil»; bekor qilingan: «Bekor qilindi»",
      all(x in qator_matn(_q, ID["p_yakun"]) for x in ("Yakunlandi", "30 885 so'm", "10 295 so'm / m²", "Batafsil"))
      and "Bekor qilindi" in qator_matn(_q, ID["p_bekor"]), (qator_matn(_q, ID["p_yakun"]), qator_matn(_q, ID["p_bekor"])))
check("R8 sana — Toshkent vaqti (UTC 28.09 20:30 → «29.09.2026» «01:30»)",
      all(x in qator_matn(_q, ID["p_vaqt"]) for x in ("29.09.2026", "01:30")), qator_matn(_q, ID["p_vaqt"]))
check("R9 ro'yxat matnida holat kodi yo'q (draft / in_progress / completed / cancelled)",
      all(x not in (_y.get("royxat_matn") or "x draft") for x in ("draft", "in_progress", "completed", "cancelled")),
      _y.get("royxat_matn", "")[:300])
check("R10 xulosa: yakunlanganlar soni va jami tannarx, jarayonda / qoralama soni",
      lambda: "1 ta yakunlandi" in _y["xulosa"] and "30 885 so'm" in _y["xulosa"] and "Jarayonda: 1" in _y["xulosa"],
      _y.get("xulosa"))
_c = n("chip_qoralama")
check("R11 «Qoralama» chipi — faqat qoralamalar, chip bosilgan (aria-pressed)",
      lambda: _c["bosilgan"] == "true" and len(_c["qatorlar"]) == _holat_soni["draft"]
      and all("Qoralama" in x["matn"] for x in _c["qatorlar"]), _c)
check("R12 «Hammasi» — hamma qator qaytdi", N.get("chip_hammasi") == len(API_ROYXAT), N.get("chip_hammasi"))
_m = n("mahsulot_filtr")
check("R13 mahsulot bo'yicha — faqat shu mahsulot; chip sonlari ham shu mahsulot bo'yicha",
      lambda: [x["id"] for x in _m["qatorlar"]] == [str(ID["p_xss"])] and _m["chiplar"][0] == "Hammasi · 1", _m)
check("R14 qidiruv: buyurtma raqami — faqat o'sha buyurtmaniki; «№id» — o'sha ishlab chiqarish",
      [x.get("id") for x in qatorlar("qidiruv")] == [str(ID["p_mijoz"])]
      and [x.get("id") for x in qatorlar("qidiruv_raqam")] == [str(ID["p_ok"])], (qatorlar("qidiruv"), qatorlar("qidiruv_raqam")))
check("R15 davr «Hammasi» — serverdan ?oy=hammasi", lambda: "oy=hammasi" in n("davr_hammasi")["oxirgi"]["url"],
      n("davr_hammasi"))

# ══════════════════════════════════════════════════════════════
section("Y. «Yangi ishlab chiqarish» oynasi")
# ══════════════════════════════════════════════════════════════
_o = n("yangi_ochish")
check("Y1 mahsulot tanlandi: retsept «Standart — 1 m² uchun, 4 ta material», birlik m², qoplama katakchasi matni",
      lambda: _o["ochiq"] and _o["bom"] == ["Standart — 1 m² uchun, 4 ta material"] and _o["birlik"] == "m²"
      and "Qoplama qo'shilsin — MRU Bo'yoq 0,15 kg (1 m² ga) · + 800 so'm har 1 m² ga" in _o["ixtiyoriy"]
      and _o["reja"]["boshlash_yopiq"] is True, _o)
_r = n("yangi_40")
_maks = int(float(API_40.get("maks_bosh") or 0))
check("Y2 40 m²: jadval — qum «Yetadi», kley «… yetmaydi» (+ jarayondagi bilan), setka «Yetadi»; «Boshlash» yopiq",
      lambda: any("MRU Qum" in x and "Yetadi" in x for x in _r["jadval"])
      and any("MRU Kley" in x and "yetmaydi" in x and "jarayondagi" in x for x in _r["jadval"])
      and len(_r["jadval"]) == 3 and _r["boshlash_yopiq"] is True and "40 m² uchun" in _r["sarlavha"], _r)
check(f"Y3 ogohlantirish: «MRU Kley yetmaydi — hozir boshlab bo'lmaydi», eng ko'pi {_maks} m², «Miqdorni {_maks} m² qilish»",
      lambda: "MRU Kley yetmaydi — hozir boshlab bo'lmaydi." in _r["ogoh"][0] and f"eng ko'pi {_maks} m²" in _r["ogoh"][0]
      and _r["tugma"] == f"Miqdorni {_maks} m² qilish" and _maks > 0, (_r.get("ogoh"), _r.get("tugma"), API_40.get("maks_bosh")))
check("Y4 taxminiy tannarx 411 800 so'm, 1 m² — 10 295 so'm", lambda: "411 800 so'm" in _r["tannarx"] and "1 m² — 10 295 so'm" in _r["tannarx"],
      _r.get("tannarx"))
_r = n("yangi_maks")
check("Y5 «Miqdorni N qilish» — miqdor N, ogohlantirish yo'q, «Boshlash» ochiq",
      lambda: _r["miqdor"] == str(_maks) and not [x for x in _r["ogoh"] if "yetmaydi — hozir" in x] and _r["boshlash_yopiq"] is False, _r)
_r = n("yangi_vergul")
check("Y6 o'nlik vergul «2,5» — 2,5 m² uchun, tannarx 25 738 so'm (2,5 × 10 295)",
      lambda: "2,5 m² uchun" in _r["sarlavha"] and "25 738 so'm" in _r["tannarx"] and _r["boshlash_yopiq"] is False, _r)
_r = n("yangi_notogri")
check("Y7 noto'g'ri son «2,5,1» — reja yo'q, «Boshlash» yopiq", lambda: _r["sarlavha"] is None and _r["boshlash_yopiq"] is True, _r)
_r = n("yangi_boshlash")
_po_idlar = {str(v) for k, v in ID.items() if k.startswith("p_")}
_yangi = [x for x in (_r.get("qatorlar") or []) if x.get("id") not in _po_idlar]
check("Y8 «Boshlash» — yaratildi va boshlandi: oyna yopildi, ro'yxatda yangi qator «Jarayonda», xabar «boshlandi — №…»",
      lambda: _r["ochiq"] is False and _r["panel"] is True and len(_yangi) == 1 and "Jarayonda" in _yangi[0]["matn"]
      and "2,5 m²" in _yangi[0]["matn"] and _r["msg"][0].startswith("Ishlab chiqarish boshlandi — №") and _r["msg"][1] == "success",
      (_r.get("msg"), _yangi))
_r = n("mijoz")
check("Y9 «Mijoz buyurtmasiga»: segment tanlandi, detallar — buyurtma raqami, mijoz, «kerak 10 m²», «qoplamali»",
      lambda: _r["segment"] == ["false", "true"] and any((ORD or "?") in d and XSS_MIJOZ in d and "kerak 10 m²" in d
                                                         and "qoplamali" in d for d in _r["detallar"]), _r)
_r = n("mijoz_detal")
check("Y10 detal tanlandi: miqdor = kerak (10), qoplama katakchasi O'ZI belgilangan va qulflangan, tannarx 146 950 (10 × 14 695)",
      lambda: _r["miqdor"] == "10" and _r["qoplama_belgi"] is True and _r["qoplama_qulf"] is True
      and "146 950 so'm" in _r["tannarx"] and any("MRU Bo'yoq" in x and "(qoplama)" in x for x in _r["jadval"]), _r)

# ══════════════════════════════════════════════════════════════
section("O. Boshlash / yakunlash / batafsil / bekor qilish oynalari")
# ══════════════════════════════════════════════════════════════
_r = n("oyna_yetmaydi")
check("O1 kley yetmaydigan qoralama — «Boshlash — №…» oynasi: kley «yetmaydi», ogohlantirish, «Boshlash» YOPIQ, «Bekor qilish» bor",
      lambda: _r["sarlavha"].startswith(f"Boshlash — №{ID['p_yet']}") and "yetmaydi — hozir boshlab bo'lmaydi" in _r["matn"]
      and any(t["matn"] == "Boshlash" and t["yopiq"] for t in _r["tugmalar"])
      and any(t["matn"] == "Bekor qilish" for t in _r["tugmalar"]), _r)
_r = n("oyna_ok")
check("O2 yetadigan qoralama — «Boshlash» OCHIQ, vaqt chizig'i (Yaratildi / Boshlanmagan)",
      lambda: any(t["matn"] == "Boshlash" and not t["yopiq"] for t in _r["tugmalar"]) and "Yaratildi" in _r["matn"]
      and "Boshlanmagan" in _r["matn"] and "Taxminiy tannarx" in _r["matn"], _r)
_r = n("oyna_ok_boshla")
check("O3 «Boshlash» — oyna yopildi, qator «Jarayonda», xabar", lambda: _r["ochiq"] is False and "Jarayonda" in _r["qator"]
      and _r["msg"][0] == f"Ishlab chiqarish boshlandi — №{ID['p_ok']}", _r)
_r = n("oyna_yakunlash")
check("O4 «Yakunlash — №…» oynasi: «Yakunlashda ombordan yechiladi», ustun «Yechiladi», tannarx boshlangan kundagi narx bilan",
      lambda: _r["sarlavha"].startswith(f"Yakunlash — №{ID['p_jarayon']}") and "Yakunlashda ombordan yechiladi" in _r["matn"]
      and "Yechiladi" in _r["jadval_bosh"] and "51 475 so'm" in _r["matn"]
      and any(t["matn"] == "Yakunlash" and not t["yopiq"] for t in _r["tugmalar"]), _r)
_r = n("oyna_yakunla")
check("O5 «Yakunlash» — qator «Yakunlandi», haqiqiy tannarx 51 475 so'm, xabar «Tayyor mahsulotlar» ga tushdi",
      lambda: _r["ochiq"] is False and "Yakunlandi" in _r["qator"] and "51 475 so'm" in _r["qator"] and "≈" not in _r["qator"]
      and "Tayyor mahsulotlar" in _r["msg"][0], _r)
_r = n("batafsil")
check("O6 «Batafsil» (yakunlangan): vaqt chizig'i, ustunlar, qoplama «ishlatilmadi — qoplamasiz», xomashyo / qo'shimcha / tannarx / 1 m²",
      lambda: all(x in _r["matn"] for x in ("Yaratildi", "Boshlandi (narx qotdi)", "Yakunlandi", "xomashyo ombordan yechildi",
                                            "ishlatilmadi — qoplamasiz", "30 885 so'm", "1 m² tannarxi", "10 295 so'm"))
      and _r["jadval_bosh"] == ["Material", "Retsept bo'yicha", "Isrof", "Sarflandi", "Narx (o'sha kuni)", "Summa"]
      and any("MRU Kley" in x and "3,3 kg" in x and "3 150 so'm / kg" in x and "10 395 so'm" in x for x in _r["jadval"])
      and _r["havolalar"] == [{"matn": "Tayyor mahsulotlarda ko'rish", "href": "/finished"}], _r)
check("O7 «Batafsil» sarlavhasi — «№… — MRU Travertin, 3 m²»", lambda: n("batafsil")["sarlavha"] == f"№{ID['p_yakun']} — MRU Travertin, 3 m²",
      n("batafsil").get("sarlavha"))
_r = n("bekor_oyna")
check("O8 «···» — batafsil va bekor qilish oynasi (qoralama): «Bekor qilish», «Yopish», «Boshlash»",
      lambda: [t["matn"] for t in _r["tugmalar"]] == ["Bekor qilish", "Yopish", "Boshlash"], _r)
_r = n("bekor")
check("O9 «Bekor qilish» — qator «Bekor qilindi», xabar", lambda: "Bekor qilindi" in _r["qator"] and _r["ochiq"] is False
      and _r["msg"][0] == f"№{ID['p_mijoz']} bekor qilindi", _r)
_r = n("bekor_batafsil")
check("O10 boshlanmasdan bekor qilingan — «xomashyo ishlatilmagan», «Bekor qilindi» vaqti",
      lambda: "Boshlanmasdan bekor qilingan — xomashyo ishlatilmagan" in _r["matn"] and "Bekor qilindi" in _r["matn"], _r)

# ══════════════════════════════════════════════════════════════
section("T. Retsept oynasi")
# ══════════════════════════════════════════════════════════════
_r = n("retsept")
_rq = _r.get("qatorlar") or [{}, {}, {}, {}]
check("T1 sarlavha «Retsept — MRU Travertin «Standart»», «Tarkibi — 1 m² uchun», partiya birligi m²",
      lambda: _r["sarlavha"] == "Retsept — MRU Travertin «Standart»" and _r["tarkib"] == "Tarkibi — 1 m² uchun"
      and _r["partiya_birlik"] == "m²", _r)
check("T2 qatorlar: material + ombordagi qoldiq, miqdor yonida birlik, isrof; narx serverdan (4 100 / 3 465 «1,1 kg × 3 150» / 2 730 / 3 600)",
      lambda: _rq[0]["material"].startswith("MRU Qum — omborda") and _rq[0]["birlik"] == "kg" and _rq[0]["narx"].startswith("4 100 so'm")
      and _rq[1]["narx"] == "3 465 so'm1,1 kg × 3 150" and _rq[1]["isrof"] == "10" and _rq[2]["narx"].startswith("2 730 so'm")
      and _rq[2]["birlik"] == "m²" and _rq[3]["narx"].startswith("3 600 so'm"), _rq)
check("T3 qoplama qatori: Sozlama OCHIQ, «Faqat qoplamali buyurtmada» tanlangan, chiplar «Qoplama — faqat qoplamali buyurtmada», «+800 so'm / m²»",
      lambda: _rq[3]["sozlama"] is True and _rq[3]["qachon"] == "qoplama"
      and "Qoplama — faqat qoplamali buyurtmada" in _rq[3]["chiplar"] and "+800 so'm / m²" in _rq[3]["chiplar"]
      and _rq[0]["sozlama"] is False and _rq[0]["qachon"] == "doim" and _rq[0]["izoh"] == "izoh-qator", _rq)
check("T4 jami: «Xomashyo (har doim) 10 295 so'm», «Qoplamali bo'lsa + 4 400 so'm», «1 m² taxminiy tannarxi 10 295 so'm · qoplamali 14 695 so'm»",
      lambda: all(x in _r["jami"] for x in ("Xomashyo (har doim) 10 295 so'm", "Qoplamali bo'lsa + 4 400 so'm",
                                            "1 m² taxminiy tannarxi 10 295 so'm · qoplamali 14 695 so'm")), _r.get("jami"))
_r = n("retsept_ozgartir")
check("T5 kley → «Ishlab chiqarishda tanlansa», isrof «12,5»: chip «Ixtiyoriy …», narx 3 544 so'm (1,125 × 3 150), jami qayta hisoblandi",
      lambda: _r["ixt"] is True and _r["qopl"] is False and "Ixtiyoriy — ishlab chiqarishda tanlanadi" in _r["chiplar"]
      and _r["narx"].startswith("3 544 so'm") and "Xomashyo (har doim) 6 830 so'm" in _r["jami"]
      and "Ixtiyoriy tarkib tanlansa — 14 774 so'm gacha." in _r["ogoh"], _r)
_r = n("retsept_yangi_qator")
check("T6 yangi qator: material tanlovi (HTML nomli material MATN bo'lib), «0,5» → narx 500 so'm",
      lambda: _r["narx"].startswith("500 so'm") and _r["birlik"] == "kg"
      and any(v.startswith(XSS_MAT + " — omborda") for v in _r["variantlar"]), _r)
check("T7 qator o'chirildi — 4 qator, jami qayta hisoblandi", lambda: n("retsept_ochir")["soni"] == 4
      and "6 830 so'm" in n("retsept_ochir")["jami"], n("retsept_ochir"))
_r = n("retsept_saqla")
_bom = next((b for b in (js(req(C, "get", f"/api/production/product-types/{ID['trav']}/boms")) or []) if b.get("id") == ID["trav_b"]), {})
_bi = {i.get("item_name"): i for i in _bom.get("items") or []}
check("T8 saqlandi (PUT): kley ixtiyoriy (qoplama emas), isrof 12,5; bo'yoq qoplama + 800; qum izohi SAQLANDI",
      lambda: _r["ochiq"] is False and _r["put"]["status"] == 200 and _bi["MRU Kley"]["is_optional"] is True
      and _bi["MRU Kley"]["is_coating"] is False and _bi["MRU Kley"]["scrap_factor_percent"] == 12.5
      and _bi["MRU Bo'yoq"]["is_coating"] is True and _bi["MRU Bo'yoq"]["fixed_cost_per_unit"] == 800
      and _bi["MRU Qum"]["notes"] == "izoh-qator" and len(_bi) == 4, (_r, _bom))
check("T9 noto'g'ri miqdor — saqlanmaydi, qaysi qator ekani aytiladi", lambda: n("retsept_xato")["msg"][0] == "1-qator: miqdorni to'g'ri kiriting"
      and n("retsept_xato")["ochiq"] is True, n("retsept_xato"))
check("T10 HTML nomli mahsulot / retsept / material — sarlavha va tanlovda MATN", lambda: n("retsept_xss")["sarlavha"] ==
      f"Retsept — {XSS_TUR} «Standart <u>v</u>»" and n("retsept_xss")["tanlangan"].startswith(XSS_MAT), n("retsept_xss"))

# ══════════════════════════════════════════════════════════════
section("M. Mahsulot turi oynasi — son maydonlari")
# ══════════════════════════════════════════════════════════════
_r = n("tur_yangi")
_pt = next((p for p in (js(req(C, "get", "/api/production/product-types")) or []) if p.get("name") == "MRU Yangi tur"), {})
check("M1 «150 000» va «2,5» — 150 000 so'm va ×2,5 saqlandi (ilgari parseFloat(\"150 000\") = 150)",
      lambda: _r["ochiq"] is False and _pt["fixed_unit_price"] == 150000 and _pt["coating_price_multiplier"] == 2.5, (_r, _pt))
check("M2 noto'g'ri narx «o'n ming» — saqlanmaydi, sabab aytiladi", lambda: n("tur_xato")["msg"][0].startswith("Qat'iy narxni to'g'ri kiriting")
      and n("tur_xato")["ochiq"] is True and not any(p.get("name") == "MRU Xato tur" for p in (js(req(C, "get", "/api/production/product-types")) or [])),
      n("tur_xato"))

# ══════════════════════════════════════════════════════════════
section("H. HTML in'ektsiya — foydalanuvchi matni HTML bo'lib chizilmaydi")
# ══════════════════════════════════════════════════════════════
_r = n("yakun")
check("H1 skript ishlamadi (window.__xss yo'q), <img onerror> / <i class=xpm> / <b>qalin</b> / <u>v</u> elementi YO'Q",
      lambda: NAT.get("xss") is False and _r["xss"] is False and _r["img"] == 0 and _r["xpm"] == 0 and _r["qalin"] == 0 and _r["u"] == 0, _r)
check("H2 HTML nomli mahsulot kartasi — nomi MATN", lambda: any(t.startswith(XSS_TUR) for t in _r["turlar"]), _r.get("turlar"))
check("H3 HTML nomli mahsulotning boshlash oynasi — nomi matn, material nomi matn",
      lambda: XSS_TUR in n("xss_oyna")["sarlavha"] and XSS_MAT in n("xss_oyna")["matn"], n("xss_oyna"))

# ══════════════════════════════════════════════════════════════
section("X. Xatolar")
# ══════════════════════════════════════════════════════════════
check("X1 sahifada JS xatosi yo'q (jsdomError, ushlanmagan va'da)", not NAT.get("xato"), NAT.get("xato"))
check("X2 hech bir so'rov 500 bermadi", not NAT.get("api_xato"), NAT.get("api_xato"))
check("X3 hamma qadam bajarildi (XATO yo'q)", all(not (isinstance(v, dict) and "XATO" in v) for v in N.values()) and len(N) == len(QADAMLAR),
      {k: v for k, v in N.items() if isinstance(v, dict) and "XATO" in v})

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
