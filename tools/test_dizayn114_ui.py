#!/usr/bin/env python3
"""
test_dizayn114_ui.py — kech114: dizayn 5–10 (egasi QARORLARI «7A — Guruh, bosilsa ochiladi», «5B — Jadval», «6A — Bir qator
+ tugmalar»; 9 / 10 — texnik) va K114-1 ning sahifadagi qismi — HAQIQIY sahifalar (server bergan HTML, shablon + base.html
skriptlari) jsdom da, HAQIQIY lokal server bilan (uvicorn, test bazasi, admin sessiyasi). Soxta javob yo'q.

NIMA TEKSHIRILADI
  F — «Tayyor mahsulotlar» (7A): bir xil mahsulot partiyalari BITTA guruh qatorida («3 partiya», jami, «+12 qop jarayonda»,
      1 birlik tannarxi, «sotishda yoziladi», qiymat — tannarx bo'yicha), bosilsa partiyalari («Partiya №12» + sana) ochiladi,
      holat shu brauzerda eslab qolinadi; bitta partiyali mahsulot — oddiy qator (avvalgidek, belgilash katakchasi bilan);
      tugagan partiya standartda yashirin («ko'rsatish»); statistika: «Omborda» — birliklar bo'yicha, «Ombor qiymati» —
      server (narxsiz — tannarx), «Ishlab chiqarilmoqda» — miqdor; jarayondagi MRP qatorida faqat «Ishlab chiqarishda
      ochish →» (K114-1 — «Sotuvga tayyor» / «Bekor qilish» YO'Q), penoplast jarayondagisida — avvalgidek.
  P — «Ishlab chiqarish» (5B): mahsulot turlari — bitta jadval (bitta so'rov: /product-types/xulosa, har tur uchun /boms
      so'rovi YO'Q), omborda / jarayonda / band, retsept yonida 1 birlik taxminiy tannarxi; «+ Retsept», «Tahrirlash»;
      /production?po=ID — ishlab chiqarish oynasi ochiladi (Tayyor mahsulotlardan havola).
  B — yuqori panel (6A): sahifa tugmalari `.tb-amallar` ichida (tugmasiz sahifada bo'sh), «···» menyusi (tungi rejim,
      Кирилл / Lotin) ochiladi / yopiladi, bandlari ishlaydi.
  O — «Buyurtmalar» (9): yangi buyurtma oynasida faqat «Shu buyurtma» paneli (umumiy «Statistika» yashirinadi, yopilganda
      qaytadi), loy yorlig'i qisqa, izoh — maydon ostida; «Chapdan …» yo'q.
  N — namuna matnlari (10): shablonlarda haqiqiy odam / korxona nomi («Akmal aka», «Rustam aka», «Jo'rabek») va «Chapdan» yo'q.
  H — HTML in'ektsiya (mahsulot turi nomi HTML) — hamma joyda matn; X — sahifa / API xatolari yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan ham. Asl kodga qarshi QULAMAYDI (yangi funksiyalar yo'q — tekshiruvlar yiqiladi).
ISHLATISH: NODE_PATH=$(npm root -g) python3 tools/test_dizayn114_ui.py
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "dizayn114_ui_test"
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
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'dizayn114_ui_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
import schemas                                     # noqa: E402

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
section("0. Fikstura (API orqali — sahifa ko'radigan haqiqiy ma'lumot)")
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "DZ_A", "Parol123!", UserRole.ADMIN, "DZ Admin", company_id=1)
    _pen = crud.add_item(_db, schemas.InventoryCreate(item_name="DZ Penoplast", unit="blok", stock_quantity=100,
                                                      price_per_unit=500000, is_penoplast=True, volume_per_unit=1.0),
                         company_id=1)
PEN = _pen.id
_db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
req(C, "post", "/login", data={"username": "DZ_A", "password": "Parol123!"}, follow_redirects=False)
ID = {}
XSS_TUR = '<img src=x onerror="window.__xss=1">DZ<b>qalin</b>'


def mat(nom, unit, stock, price):
    return (js(req(C, "post", "/api/inventory", json={"item_name": nom, "unit": unit, "stock_quantity": stock,
                                                      "price_per_unit": price})) or {}).get("id")


def tur(nom, unit, shablon, formula, qoplama=False):
    t = {"name": nom, "unit": unit, "input_template": shablon, "pricing_formula": formula, "supports_coating": qoplama}
    if qoplama:
        t["coating_price_multiplier"] = 2
    return (js(req(C, "post", "/api/production/product-types", json=t)) or {}).get("id")


def retsept(pt, nom, items):
    return (js(req(C, "post", "/api/production/boms", json={"product_type_id": pt, "variant_name": nom,
                                                             "batch_quantity": 1, "items": items})) or {}).get("id")


def po(pt, bom, miq, *amallar):
    r = req(C, "post", "/api/production/orders", json={"product_type_id": pt, "bom_id": bom, "quantity": miq,
                                                       "source_type": "warehouse_stock"})
    pid = ((js(r) or {}).get("production_order") or {}).get("id")
    for a in amallar:
        req(C, "post", f"/api/production/orders/{pid}/{a}")
    return pid


def fp_of(pid):
    s = SessionLocal()
    try:
        p = s.get(ProductionOrder, pid)
        return p.finished_product_id if p else None
    finally:
        s.close()


def penoplast_tm(nom, narx):
    j = js(req(C, "post", "/api/finished/produce", json={
        "name": nom, "category": "profil", "is_coated": False, "penoplast_id": PEN, "price_per_m3": None,
        "unit_price": narx, "recipe_id": None, "notes": None, "width": 10, "thickness": 10, "length": 10,
        "quantity": 5})) or {}
    return j.get("id") or j.get("product_id") or (j.get("product") or {}).get("id")


ID["qum"] = mat("DZ Qum", "kg", 5000, 820)
ID["kley"] = mat("DZ Kley", "kg", 1000, 3150)
ID["setka"] = mat("DZ Setka", "m²", 1000, 2600)
ID["boyoq"] = mat("DZ Boyoq", "kg", 100, 24000)
ID["trav"] = tur("DZ Travertin", "m²", "quantity_only", "unit_based", True)
ID["kafel"] = tur("DZ Kafel kley", "qop", "weight_volume", "unit_based")
ID["xss"] = tur(XSS_TUR, "dona", "quantity_only", "unit_based")
ID["trav_b"] = retsept(ID["trav"], "Standart", [
    {"inventory_id": ID["qum"], "quantity": 5}, {"inventory_id": ID["kley"], "quantity": 1, "scrap_factor_percent": 10},
    {"inventory_id": ID["setka"], "quantity": 1, "scrap_factor_percent": 5},
    {"inventory_id": ID["boyoq"], "quantity": 0.15, "is_optional": True, "is_coating": True, "fixed_cost_per_unit": 800}])
ID["kafel_b"] = retsept(ID["kafel"], "25 kg qop", [{"inventory_id": ID["qum"], "quantity": 17.5},
                                                  {"inventory_id": ID["kley"], "quantity": 0.5}])
ID["xss_b"] = retsept(ID["xss"], "X", [{"inventory_id": ID["qum"], "quantity": 1}])
for _i in range(3):     # 3 qoralama — ishlab chiqarish raqamlari TM raqamlaridan farq qilsin (F12: kesishmaydi)
    ID[f"qoralama{_i}"] = po(ID["kafel"], ID["kafel_b"], 1)
ID["t10"] = po(ID["trav"], ID["trav_b"], 10, "start", "complete")
ID["t30"] = po(ID["trav"], ID["trav_b"], 30, "start", "complete")
ID["t40"] = po(ID["trav"], ID["trav_b"], 40, "start", "complete")
ID["k20"] = po(ID["kafel"], ID["kafel_b"], 20, "start", "complete")
ID["k12"] = po(ID["kafel"], ID["kafel_b"], 12, "start")
ID["x1"] = po(ID["xss"], ID["xss_b"], 1, "start", "complete")
ID["x2"] = po(ID["xss"], ID["xss_b"], 2, "start", "complete")
ID["fp_k12"] = fp_of(ID["k12"])
ID["fp_t40"] = fp_of(ID["t40"])
ID["karniz"] = penoplast_tm("DZ Karniz", 25000)
req(C, "post", f"/api/finished/{ID['karniz']}/complete")
ID["karniz2"] = penoplast_tm("DZ Karniz", 25000)
req(C, "post", f"/api/finished/{ID['karniz2']}/complete")
_sot = req(C, "post", "/api/finished/sell", json={"finished_product_id": ID["karniz2"], "quantity": 10, "unit_price": 25000,
                                                  "payment_method": "naqd", "master_id": None, "confirm_below_cost": True})
ID["panel_j"] = None
_pj = js(req(C, "post", "/api/finished/produce", json={
    "name": "DZ Panel jarayonda", "category": "panel", "is_coated": False, "penoplast_id": PEN, "price_per_m3": None,
    "unit_price": 30000, "recipe_id": None, "notes": None, "width": 10, "thickness": 10, "length": 5, "quantity": 2})) or {}
ID["panel_j"] = _pj.get("id") or _pj.get("product_id") or (_pj.get("product") or {}).get("id")
check("fikstura: 3 tur, 3 retsept, 7 ishlab chiqarish (1 jarayonda), penoplast 2 partiya (biri tugagan), jarayondagi panel",
      all(ID.get(k) for k in ("trav", "kafel", "xss", "trav_b", "kafel_b", "xss_b", "t10", "t30", "t40", "k20", "k12",
                              "fp_k12", "karniz", "karniz2", "panel_j")) and _sot.status_code == 200,
      (ID, _sot.status_code, getattr(_sot, "text", "")[:200]))
STATS = js(req(C, "get", "/api/finished/stats")) or {}
XULOSA = js(req(C, "get", "/api/production/product-types/xulosa")) or []

# ══════════════════════════════════════════════════════════════
# jsdom ssenariysi (node) — bir necha sahifa, har biri o'z qadamlari bilan
# ══════════════════════════════════════════════════════════════
NODE_JS = r"""
let JSDOM, VirtualConsole, ResourceLoader;
try { ({ JSDOM, VirtualConsole, ResourceLoader } = require("jsdom")); }
catch (e) { console.log(JSON.stringify({ fatal: "jsdom topilmadi: " + String(e.message).slice(0, 200) })); process.exit(3); }
const base = process.argv[2], cookie = process.argv[3];
const sahifalar = JSON.parse(require("fs").readFileSync(process.argv[4], "utf8"));
class FaqatOzimiz extends ResourceLoader {
  fetch(url, options) { return url.startsWith(base) ? super.fetch(url, options) : null; }
}
const kut = ms => new Promise(r => setTimeout(r, ms));
const res = { sahifa: {}, xato: [], api_xato: [], natija: {}, xss: false };
process.on("unhandledRejection", e => res.xato.push("va'da: " + String((e && (e.message || e)) || "").slice(0, 200)));
process.on("uncaughtException", e => res.xato.push("xato: " + String((e && (e.message || e)) || "").slice(0, 200)));
async function ochish(yol, qadamlar, storage) {
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
      if (storage) { try { Object.entries(storage).forEach(([k, v]) => w.localStorage.setItem(k, v)); } catch (e) {} }
      w.fetch = async (u, o) => {
        pending++; lastActive = Date.now();
        try {
          o = o || {};
          const h = Object.assign({}, o.headers || {}); h.cookie = cookie;
          const url = new URL(String(u), sahifaUrl).href;
          if (!url.startsWith(base)) throw new Error("tashqi so'rov: " + url);
          const resp = await fetch(url, Object.assign({}, o, { headers: h, redirect: "manual" }));
          if (resp.status >= 500) res.api_xato.push(resp.status + " " + url.slice(base.length, base.length + 120));
          w.__sorovlar.push({ url: url.slice(base.length), method: o.method || "GET", status: resp.status });
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
  if (w.__xss) res.xss = true;
  let saqlangan = {};
  try { for (let i = 0; i < w.localStorage.length; i++) { const k = w.localStorage.key(i); saqlangan[k] = w.localStorage.getItem(k); } } catch (e) {}
  w.close();
  return saqlangan;
}
(async () => {
  let storage = null;
  for (const s of sahifalar) {
    const saq = await ochish(s.yol, s.qadamlar, s.storage_davom ? storage : null);
    if (s.storage_saqla) storage = saq;
  }
  console.log(JSON.stringify(res));
  process.exit(0);
})().catch(e => { res.xato.push("yakuniy: " + String(e && e.message)); console.log(JSON.stringify(res)); process.exit(0); });
"""

YORDAM = r"""
window.__msg = [];
window.showMsg = (t, k) => { window.__msg.push([String(t), String(k || '')]); };
window.customConfirm = async () => true;
window.__m = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : null;
window.__guruhlar = () => [...document.querySelectorAll('#fpList .fp-guruh')].map(g => ({
  bosh: __m(g.querySelector('.fp-guruh-bosh')), ochiq: g.classList.contains('ochiq'),
  ichi_yashirin: g.querySelector('.fp-guruh-ichi').hidden,
  aria: g.querySelector('.fp-guruh-tugma').getAttribute('aria-expanded'),
  partiyalar: [...g.querySelectorAll('.fp-guruh-ichi .fp-row')].map(__m),
  havolalar: [...g.querySelectorAll('.fp-guruh-ichi a.fp-mrp-havola')].map(a => a.getAttribute('href')),
  tayyor_tugma: [...g.querySelectorAll('.fp-guruh-ichi button')].filter(b => /Sotuvga tayyor/.test(b.textContent)).length,
  kalit: g.dataset.kalit }));
window.__oddiy = () => [...document.querySelectorAll('#fpList > .fp-row')].map(r => ({
  matn: __m(r), katak: !!r.querySelector('.fp-batch-check'),
  tayyor_tugma: [...r.querySelectorAll('button')].filter(b => /Sotuvga tayyor/.test(b.textContent)).length,
  havola: (r.querySelector('a.fp-mrp-havola') || {}).href || null }));
window.__guruh = nom => [...document.querySelectorAll('#fpList .fp-guruh')].find(g => (__m(g.querySelector('.fp-name')) || '') === nom) || null;
return true;
"""


def q(nom, amal=None, natija=None):
    return {"nom": nom, "amal": amal, "natija": natija}


FIN = [
    q("yordam", natija=YORDAM),
    q("fin_yuklash", natija=r"""return {guruhlar: __guruhlar(), oddiy: __oddiy(),
      k_types: __m(document.getElementById('k-types')), k_partiya: __m(document.getElementById('k-partiya')),
      k_qty: __m(document.getElementById('k-total-qty')), v_total: __m(document.getElementById('v-total')),
      v_izoh: __m(document.getElementById('v-total-izoh')), k_prog: __m(document.getElementById('k-progress')),
      k_low: __m(document.getElementById('k-low')), yashirin: __m(document.getElementById('fpYashirinIzoh')),
      tugagan_katak: document.getElementById('fpTugaganlar') ? document.getElementById('fpTugaganlar').checked : null,
      sorovlar: window.__sorovlar.map(s => s.url)};"""),
    q("fin_och", amal="__guruh('DZ Travertin').querySelector('.fp-guruh-tugma').click();",
      natija="return {g: __guruhlar().find(g => g.bosh.startsWith('DZ Travertin')), saqlangan: localStorage.getItem('fp_ochiq_guruhlar')};"),
    q("fin_qayta", amal="renderFp();", natija="return __guruhlar().find(g => g.bosh.startsWith('DZ Travertin'));"),
    q("fin_kafel", amal="__guruh('DZ Kafel kley').querySelector('.fp-guruh-tugma').click();",
      natija="return __guruhlar().find(g => g.bosh.startsWith('DZ Kafel kley'));"),
    q("fin_yop", amal="__guruh('DZ Kafel kley').querySelector('.fp-guruh-tugma').click();",
      natija="return {g: __guruhlar().find(g => g.bosh.startsWith('DZ Kafel kley')), saqlangan: localStorage.getItem('fp_ochiq_guruhlar')};"),
    q("fin_tugagan", amal="document.querySelector('#fpYashirinIzoh button').click();",
      natija="return {guruhlar: __guruhlar(), oddiy: __oddiy(), katak: document.getElementById('fpTugaganlar').checked, yashirin: __m(document.getElementById('fpYashirinIzoh'))};"),
    q("fin_qidir", amal="document.getElementById('fpSearch').value = 'kafel'; renderFp();",
      natija="return {guruhlar: __guruhlar().map(g => g.bosh), oddiy: __oddiy().map(r => r.matn)};"),
    q("fin_saralash", amal="document.getElementById('fpSearch').value = ''; document.getElementById('fpSort').value = 'qty_desc'; renderFp();",
      natija="return [...document.querySelectorAll('#fpList > .fp-guruh > .fp-guruh-bosh .fp-name, #fpList > .fp-row .fp-name')].map(__m);"),
    # jsdom rasm yuklamaydi — brauzerdagi «rasm yuklanmadi» holatini qo'lda beramiz: nom HTML bo'lib qo'yilgan bo'lsa,
    # onerror ishlaydi va window.__xss = 1 (H3 yiqiladi)
    q("fin_xss", amal="document.querySelectorAll('#fpList img').forEach(i => i.dispatchEvent(new Event('error')));",
      natija=r"""return {img: document.querySelectorAll('#fpList img[onerror]').length,
      qalin: [...document.querySelectorAll('#fpList b')].filter(b => b.textContent === 'qalin').length,
      nom: __guruhlar().map(g => g.bosh).find(t => t.includes('onerror')) || null};"""),
    # yuqori panel (6A)
    q("panel", natija=r"""const a = document.querySelector('.tb-amallar'); const m = document.getElementById('tbKopMenyu');
      return {amallar: [...a.children].map(__m), menyu_yashirin: m.hidden, aria: document.getElementById('tbKop').getAttribute('aria-expanded')};"""),
    q("panel_och", amal="document.getElementById('tbKop').click();",
      natija=r"""return {yashirin: document.getElementById('tbKopMenyu').hidden, aria: document.getElementById('tbKop').getAttribute('aria-expanded'),
      bandlar: [...document.querySelectorAll('#tbKopMenyu [role=menuitem]')].map(__m)};"""),
    q("panel_tema", amal="document.getElementById('tbKopTema').click();",
      natija=r"""return {tema: document.documentElement.getAttribute('data-theme'), yashirin: document.getElementById('tbKopMenyu').hidden};"""),
    q("panel_tema2", amal="document.getElementById('tbKop').click();",
      natija="return __m(document.getElementById('tbKopTema'));"),
    q("panel_tashqi", amal="document.getElementById('fpList').click();",
      natija="return document.getElementById('tbKopMenyu').hidden;"),
    q("panel_yozuv", amal="document.getElementById('tbKop').click(); document.getElementById('tbKopYozuv').click(); document.getElementById('tbKop').click();",
      natija=r"""return {asl: __m(document.getElementById('script-toggle-btn')), band: __m(document.getElementById('tbKopYozuv')),
        skript: currentScript};"""),
    q("panel_yozuv_qayt", amal="tbKopYop(); toggleScript(); document.getElementById('tbKop').click();",
      natija="return {skript: currentScript, band: __m(document.getElementById('tbKopYozuv'))};"),
]
PROD = [
    q("yordam", natija=YORDAM),
    q("prod_yuklash", natija=r"""return {qatorlar: [...document.querySelectorAll('#pt-list .pt-jadval tbody tr')].map(__m),
      sarlavha: [...document.querySelectorAll('#pt-list .pt-jadval th')].map(__m),
      kartalar: document.querySelectorAll('#pt-list .pt-card').length,
      sorovlar: window.__sorovlar.map(s => s.url),
      amallar: [...document.querySelector('.tb-amallar').children].map(__m)};"""),
    q("prod_retsept", amal="[...document.querySelectorAll('#pt-list .pt-jadval tbody tr')].find(tr => (__m(tr) || '').startsWith('DZ Travertin')).querySelector('.pt-amallar button').click();",
      natija="return {ochiq: document.getElementById('bom-modal').classList.contains('open'), sarlavha: __m(document.getElementById('bom-modal-title'))};"),
    q("prod_xss", amal="document.querySelectorAll('#pt-list img').forEach(i => i.dispatchEvent(new Event('error')));",
      natija=r"""return {img: document.querySelectorAll('#pt-list img[onerror]').length,
      qalin: [...document.querySelectorAll('#pt-list b')].filter(b => b.textContent === 'qalin').length,
      qator: [...document.querySelectorAll('#pt-list .pt-jadval tbody tr')].map(__m).find(t => t.includes('onerror')) || null};"""),
]
PROD_PO = [
    q("yordam", natija=YORDAM),
    q("po_link", natija=r"""return {tab: (document.querySelector('.prod-tab.active') || {}).dataset ? document.querySelector('.prod-tab.active').dataset.tab : null,
      ochiq: document.getElementById('snapshot-modal').classList.contains('open'),
      sarlavha: __m(document.getElementById('snapshot-modal-title')),
      tugmalar: [...document.querySelectorAll('#snapshot-tugmalar button')].map(__m)};"""),
]
PROD_PO_YOQ = [
    q("yordam", natija=YORDAM),
    q("po_yoq", natija="return {xabar: document.body.textContent.includes('Ishlab chiqarish topilmadi'), ochiq: document.getElementById('snapshot-modal').classList.contains('open')};"),
]
ORD = [
    q("yordam", natija=YORDAM),
    q("ord_bosh", natija=r"""const u = document.getElementById('umumiyStat'), l = document.getElementById('liveStats');
      const lbl = document.querySelector('label[for=loy_kg]');
      return {umumiy: u ? u.style.display : 'YOQ', live: l ? l.style.display : 'YOQ',
        live_sarlavha: l ? __m(l.querySelector('h3')) : null, loy_yorliq: __m(lbl), loy_izoh: __m(document.getElementById('loy_kg_izoh')),
        chapdan: document.body.textContent.includes('Chapdan'), amallar: document.querySelector('.tb-amallar').innerHTML};"""),
    q("ord_yangi", amal="showNewForm(); updateLiveStats();",
      natija=r"""return {umumiy: document.getElementById('umumiyStat').style.display, live: document.getElementById('liveStats').style.display,
        detal: document.querySelectorAll('.detal').length};"""),
    q("ord_yop", amal="hideNewForm();",
      natija=r"""return {umumiy: document.getElementById('umumiyStat').style.display, live: document.getElementById('liveStats').style.display};"""),
]
SAHIFALAR = [
    {"yol": "/finished", "qadamlar": FIN, "storage_saqla": True},
    {"yol": "/finished", "qadamlar": [q("yordam", natija=YORDAM),
                                      q("fin_eslab", natija="return __guruhlar().map(g => ({bosh: g.bosh, ochiq: g.ochiq}));")],
     "storage_davom": True},
    {"yol": "/production", "qadamlar": PROD},
    {"yol": f"/production?po={ID.get('k12')}", "qadamlar": PROD_PO},
    {"yol": "/production?po=987654", "qadamlar": PROD_PO_YOQ},
    {"yol": "/orders", "qadamlar": ORD},
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
        lr = httpx.post(base + "/login", data={"username": "DZ_A", "password": "Parol123!"}, follow_redirects=False, timeout=30)
        cookie = "; ".join(h.split(";")[0] for h in lr.headers.get_list("set-cookie"))
        pj = os.path.join(_T, "sahifalar.json")
        with open(pj, "w", encoding="utf-8") as f:
            json.dump(SAHIFALAR, f, ensure_ascii=False)
        sj = os.path.join(_T, "dizayn114.js")
        with open(sj, "w", encoding="utf-8") as f:
            f.write(NODE_JS)
        k = subprocess.run([node, sj, base, cookie, pj], capture_output=True, text=True, timeout=900, env=env)
        try:
            NAT = json.loads((k.stdout or "").strip().splitlines()[-1])
        except Exception as e:             # noqa: BLE001
            NAT = {"fatal": f"{type(e).__name__}: {e}; stdout={k.stdout[-400:]} stderr={k.stderr[-400:]}"}
    finally:
        server.should_exit = True
        th.join(timeout=10)
N = NAT.get("natija") or {}
check("S0 sahifalar 200, ssenariy tugadi", "fatal" not in NAT and N.get("yordam") is True
      and all(v == 200 for v in (NAT.get("sahifa") or {}).values()) and len(NAT.get("sahifa") or {}) >= 5,
      {k: NAT.get(k) for k in ("sahifa", "fatal", "xato")})


def n(nom):
    v = N.get(nom)
    return v if isinstance(v, (dict, list)) else {}


def guruh(royxat, bosh):
    return next((g for g in (royxat or []) if isinstance(g, dict) and str(g.get("bosh") or "").startswith(bosh)), {})


def birlik_matn(royxat):
    """Sahifadagi `miqdorlarMatni` bilan bir qoida: birlik nomi (`unitLabel`), katta miqdordan kichikka."""
    # kech120 (zip 133 — G5-07, MOSLANDI): birlik — umumiy qoida (`birlikQisqa`): dona — «dona» (ilgari bu sahifada «ta»)
    xarita = {"metr": "m", "kvadrat": "m²", "dona": "dona", "ta": "dona", "m2": "m²"}
    jami = {}
    for r in royxat or []:
        b = xarita.get(r["birlik"], r["birlik"])
        jami[b] = jami.get(b, 0) + float(r["miqdor"])
    return " · ".join(f"{('%g' % m).replace('.', ',')} {b}" for b, m in sorted(jami.items(), key=lambda x: -x[1]) if m > 0)


# ══════════════════════════════════════════════════════════════
section("F. «Tayyor mahsulotlar» — 7A: guruh, bosilsa ochiladi")
# ══════════════════════════════════════════════════════════════
_f = n("fin_yuklash")
_tr = guruh(_f.get("guruhlar"), "DZ Travertin")
check("F1 Travertin — BITTA guruh qatori: «3 partiya», «80 m²», «sotishda yoziladi», 1 m² tannarxi, qiymat «tannarx bo'yicha»",
      lambda: all(x in _tr["bosh"] for x in ("3 partiya", "80 m²", "sotishda yoziladi", "tan: 10", "tannarx bo'yicha")), _tr)
check("F2 guruh standartda yig'iq (partiyalar yashirin, aria-expanded=false)",
      lambda: _tr["ochiq"] is False and _tr["ichi_yashirin"] is True and _tr["aria"] == "false", _tr)
_kf = guruh(_f.get("guruhlar"), "DZ Kafel kley")
check("F3 Kafel kley — guruh: «20 qop» + «+12 qop jarayonda», «2 partiya»",
      lambda: all(x in _kf["bosh"] for x in ("20 qop", "+12 qop jarayonda", "2 partiya")), _kf)
_od = _f.get("oddiy") or []
_karniz = next((r for r in _od if "DZ Karniz" in r["matn"]), {})
check("F4 bitta partiyali mahsulot (DZ Karniz — ikkinchisi tugagan, yashirin) — oddiy qator, belgilash katakchasi bor",
      lambda: _karniz["katak"] is True and "25 000/m" in _karniz["matn"] and not guruh(_f.get("guruhlar"), "DZ Karniz"), _od)
_panel = next((r for r in _od if "DZ Panel jarayonda" in r["matn"]), {})
check("F5 penoplast jarayondagi TM — «Sotuvga tayyor» joyida (eski yo'l o'zgarmagan), MRP havolasi yo'q",
      lambda: _panel["tayyor_tugma"] == 1 and _panel["havola"] is None, _panel)
check("F6 tugagan partiya yashirin: «Tugagan partiyalar yashirilgan: 1 ta — ko'rsatish», «Tugaganlar ham» belgilanmagan",
      lambda: _f["yashirin"] == "Tugagan partiyalar yashirilgan: 1 ta — ko'rsatish" and _f["tugagan_katak"] is False, _f.get("yashirin"))
check("F7 «Mahsulotlar» — guruhlar soni (DZ Travertin, DZ Kafel kley, XSS, DZ Karniz, DZ Panel = 5 ta), partiyalar 10",
      lambda: _f["k_types"] == "5 ta" and _f["k_partiya"] == "10 partiya", (_f.get("k_types"), _f.get("k_partiya")))
check("F8 «Omborda» — serverdan, birliklar bo'yicha (bitta «birlik» yig'indisi yo'q)",
      lambda: _f["k_qty"] == birlik_matn(STATS.get("miqdorlar")) and "80 m²" in _f["k_qty"] and "20 qop" in _f["k_qty"]
      and "birlik" not in _f["k_qty"], (_f.get("k_qty"), STATS.get("miqdorlar")))
check("F9 «Ombor qiymati» = server total_value; izohda narxsiz partiyalar tannarx bo'yicha",
      lambda: _f["v_total"] == f"{STATS['total_value']:,}".replace(",", " ") + " so'm"
      and f"narxsiz {STATS['narxsiz_soni']} ta" in _f["v_izoh"] and "tannarx bo'yicha" in _f["v_izoh"],
      (_f.get("v_total"), _f.get("v_izoh"), STATS))
check("F10 «Ishlab chiqarilmoqda» — miqdor (12 qop va jarayondagi panel)", lambda: "12 qop" in _f["k_prog"], _f.get("k_prog"))
_o = n("fin_och")
_otr = _o.get("g") or {}
check("F11 bosildi → ochiq: aria-expanded=true, 3 partiya qatori «Partiya №…» + sana, har birida amallar",
      lambda: _otr["ochiq"] is True and _otr["ichi_yashirin"] is False and _otr["aria"] == "true"
      and len(_otr["partiyalar"]) == 3 and all(p.startswith("Partiya №") for p in _otr["partiyalar"]), _otr)
check("F12 partiya raqami — ishlab chiqarish raqami (№{t10}, №{t30}, №{t40}), TM raqami EMAS".format(**ID),
      lambda: all(any(p.startswith(f"Partiya №{ID[k]} ") for p in _otr["partiyalar"]) for k in ("t10", "t30", "t40"))
      and not ({fp_of(ID[k]) for k in ("t10", "t30", "t40")} & {ID[k] for k in ("t10", "t30", "t40")}),
      (_otr.get("partiyalar"), ID.get("fp_t40")))
check("F13 ochiq guruh shu brauzerda saqlandi (localStorage) va qayta chizishda ochiq qoladi",
      lambda: _otr["kalit"] in json.loads(_o["saqlangan"]) and n("fin_qayta")["ochiq"] is True, (_o.get("saqlangan"), n("fin_qayta")))
_ok = n("fin_kafel")
check("F14 K114-1: jarayondagi MRP partiyasida faqat «Ishlab chiqarishda ochish →» (/production?po=ID), «Sotuvga tayyor» YO'Q",
      lambda: _ok["havolalar"] == [f"/production?po={ID['k12']}"] and _ok["tayyor_tugma"] == 0
      and any("Ishlab chiqarishda ochish" in p for p in _ok["partiyalar"]), _ok)
_oy = n("fin_yop")
check("F15 qayta bosildi → yig'iq, localStorage dan chiqdi", lambda: _oy["g"]["ochiq"] is False
      and _oy["g"]["kalit"] not in json.loads(_oy["saqlangan"]), _oy)
_ot = n("fin_tugagan")
_kz = guruh(_ot.get("guruhlar"), "DZ Karniz")
check("F16 «ko'rsatish» → «Tugaganlar ham» belgilandi, DZ Karniz endi guruh (2 partiya, biri «Tugagan»), izoh yo'q",
      lambda: _ot["katak"] is True and "2 partiya" in _kz["bosh"] and _ot["yashirin"] is None, _ot)
_q = n("fin_qidir")
check("F17 qidiruv «kafel» — faqat Kafel kley guruhi", lambda: len(_q["guruhlar"]) == 1 and _q["guruhlar"][0].startswith("DZ Kafel kley")
      and _q["oddiy"] == [], _q)
_sr = N.get("fin_saralash") or []
check("F18 «Qoldiq (ko'pdan-kamga)» — guruhlar jami qoldiq bo'yicha: DZ Travertin (80) birinchi",
      lambda: _sr[0] == "DZ Travertin" and _sr.index("DZ Travertin") < _sr.index("DZ Kafel kley"), _sr)
check("F19 ochiq guruh keyingi ochilishda ham ochiq (Travertin), yig'ilgani yig'iq (Kafel)",
      lambda: guruh(N.get("fin_eslab"), "DZ Travertin")["ochiq"] is True and guruh(N.get("fin_eslab"), "DZ Kafel kley")["ochiq"] is False,
      N.get("fin_eslab"))

# ══════════════════════════════════════════════════════════════
section("P. «Ishlab chiqarish» — 5B: mahsulot turlari jadvali, ?po= havola")
# ══════════════════════════════════════════════════════════════
_p = n("prod_yuklash")
_ptr = next((t for t in _p.get("qatorlar") or [] if t.startswith("DZ Travertin")), "")
# kech118 (zip 123 — G4-22 / G5-01, MOSLANDI): Ishlab chiqarishdagi «Retsept» — «Mahsulot tarkibi»; Tayyor mahsulotlarda
# «Penoplast detal» + «Retsept bo'yicha →»
check("P1 jadval sarlavhalari: «Mahsulot turi», «Mahsulot tarkibi va 1 birlik taxminiy tannarxi», «Omborda», «Jarayonda», «Band»",
      lambda: _p["sarlavha"][:5] == ["Mahsulot turi", "Mahsulot tarkibi va 1 birlik taxminiy tannarxi", "Omborda", "Jarayonda", "Band"],
      _p.get("sarlavha"))
check("P2 Travertin qatori: «m² · Faqat miqdor · narx: birlik narxi», «Qoplama mumkin · ×2», «Standart (1 m² uchun · 4 ta material)», "
      "«1 m² ≈ 10 295 so'm · qoplamali ≈ 14 695 so'm», omborda «80 m²»",
      lambda: all(x in _ptr for x in ("m² · Faqat miqdor · narx: birlik narxi", "Qoplama mumkin · ×2",
                                      "Standart (1 m² uchun · 4 ta material)", "1 m² ≈ 10 295 so'm · qoplamali ≈ 14 695 so'm",
                                      "80 m²", "Tahrirlash", "+ Tarkib")), _ptr)
_pkf = next((t for t in _p.get("qatorlar") or [] if t.startswith("DZ Kafel kley")), "")
check("P3 Kafel qatori: omborda «20 qop», jarayonda «12 qop», «1 qop ≈ 15 925 so'm» (qum 17,5 × 820 + kley 0,5 × 3 150)",
      lambda: "20 qop" in _pkf and "12 qop" in _pkf and "1 qop ≈ 15 925 so'm" in _pkf, _pkf)
check("P4 jadval tannarxi = server (`/product-types/xulosa`) — sahifada formula yo'q",
      lambda: any(abs(b["tannarx"]["doim"] - 10295) < 1e-6 for t in XULOSA if t["name"] == "DZ Travertin" for b in t["retseptlar"]), XULOSA)
check("P5 kartalar yo'q, BITTA so'rov (/product-types/xulosa), har tur uchun /boms so'rovi YO'Q",
      lambda: _p["kartalar"] == 0 and _p["sorovlar"].count("/api/production/product-types/xulosa") == 1
      and not any(s.startswith("/api/production/product-types/") and s.endswith("/boms") for s in _p["sorovlar"]), _p.get("sorovlar"))
check("P6 «+ Tarkib» → mahsulot tarkibi oynasi shu tur uchun ochiladi", lambda: n("prod_retsept")["ochiq"] is True
      and n("prod_retsept")["sarlavha"] == "Yangi mahsulot tarkibi — DZ Travertin", n("prod_retsept"))
check("P7 yuqori paneldagi sahifa tugmalari `.tb-amallar` ichida (2 ta)", lambda: len(_p["amallar"]) == 2
      and "Yangi mahsulot turi" in _p["amallar"][0] and "Yangi ishlab chiqarish" in _p["amallar"][1], _p.get("amallar"))
_pl = n("po_link")
check("P8 /production?po=ID — «Ishlab chiqarish» ro'yxati va shu ishlab chiqarish oynasi (Yakunlash / Bekor qilish)",
      lambda: _pl["tab"] == "orders" and _pl["ochiq"] is True and "DZ Kafel kley" in _pl["sarlavha"]
      and "Yakunlash" in _pl["tugmalar"] and "Ishlab chiqarishni bekor qilish" in _pl["tugmalar"], _pl)   # kech120 (zip 133 — G5-21, MOSLANDI)
check("P9 /production?po=<yo'q> — xabar «Ishlab chiqarish topilmadi», oyna ochilmaydi",
      lambda: n("po_yoq")["ochiq"] is False and n("po_yoq")["xabar"] is True, n("po_yoq"))

# ══════════════════════════════════════════════════════════════
section("B. Yuqori panel — 6A: «···» menyusi va sahifa tugmalari")
# ══════════════════════════════════════════════════════════════
_b = n("panel")
check("B1 «Tayyor mahsulotlar» tugmalari `.tb-amallar` ichida («Penoplast detal», «Retsept bo'yicha →»); «···» menyusi yopiq",
      lambda: _b["amallar"] == ["Penoplast detal", "Retsept bo'yicha →"]
      and _b["menyu_yashirin"] is True and _b["aria"] == "false", _b)
check("B2 «···» bosildi → menyu ochiq: «Tungi rejim», «Кирилл»", lambda: n("panel_och")["yashirin"] is False
      and n("panel_och")["aria"] == "true" and n("panel_och")["bandlar"] == ["Tungi rejim", "Кирилл"], n("panel_och"))
check("B3 «Tungi rejim» → tungi rejim yoqildi, menyu yopildi; qayta ochilganda — «Kunduzgi rejim»",
      lambda: n("panel_tema")["tema"] == "dark" and n("panel_tema")["yashirin"] is True and N.get("panel_tema2") == "Kunduzgi rejim",
      (n("panel_tema"), N.get("panel_tema2")))
check("B4 menyu tashqarisiga bosilsa — yopiladi", N.get("panel_tashqi") is True, N.get("panel_tashqi"))
check("B5 «Кирилл» bandi — yozuv kirillga o'tdi (`toggleScript`), band asl tugma bilan bir xil (Lotin / Лотин)",
      lambda: n("panel_yozuv")["skript"] == "kirill" and n("panel_yozuv")["band"] == n("panel_yozuv")["asl"].replace("🔤", "").strip()
      and n("panel_yozuv")["band"] in ("Lotin", "Лотин"), n("panel_yozuv"))
check("B6 qaytadan lotin — band «Кирилл»", lambda: n("panel_yozuv_qayt")["skript"] == "lotin"
      and n("panel_yozuv_qayt")["band"] == "Кирилл", n("panel_yozuv_qayt"))

# ══════════════════════════════════════════════════════════════
section("O. «Buyurtmalar» — 9: bitta «Shu buyurtma» paneli, qisqa loy yorlig'i")
# ══════════════════════════════════════════════════════════════
_ob = n("ord_bosh")
check("O1 boshida: umumiy «Statistika» ko'rinadi, «Shu buyurtma» yashirin (sarlavhasi «Shu buyurtma»)",
      lambda: _ob["umumiy"] != "none" and _ob["live"] == "none" and _ob["live_sarlavha"] == "Shu buyurtma", _ob)
check("O2 loy yorlig'i qisqa «Loy miqdori (kg)», izoh maydon ostida", lambda: _ob["loy_yorliq"] == "Loy miqdori (kg)"
      and _ob["loy_izoh"].startswith("Faqat qoplamali penoplast detallari uchun"), _ob)
check("O3 «Chapdan …» yo'q; tugmasiz sahifada `.tb-amallar` bo'sh", lambda: _ob["chapdan"] is False and _ob["amallar"] == "", _ob)
check("O4 yangi buyurtma oynasi → «Shu buyurtma» ko'rinadi, umumiy «Statistika» yashirinadi",
      lambda: n("ord_yangi")["live"] == "block" and n("ord_yangi")["umumiy"] == "none" and n("ord_yangi")["detal"] >= 1, n("ord_yangi"))
check("O5 oyna yopildi → umumiy «Statistika» qaytdi, «Shu buyurtma» yashirin",
      lambda: n("ord_yop")["umumiy"] == "" and n("ord_yop")["live"] == "none", n("ord_yop"))

# ══════════════════════════════════════════════════════════════
section("N. Namuna matnlari — 10 (statik)")
# ══════════════════════════════════════════════════════════════
_tpl = {}
for _fn in sorted(os.listdir(os.path.join(ROOT, "templates"))):
    if _fn.endswith(".html"):
        _tpl[_fn] = open(os.path.join(ROOT, "templates", _fn), encoding="utf-8").read()
for _i, (_so, _iz) in enumerate([("Akmal aka", "ta'minotchi namunasi"), ("Rustam aka", "ta'minotchi namunasi"),
                                  ("Jo'rabek", "hodim ismi"), ("Chapdan", "telefonda chap tomon yo'q")], 1):
    check(f"N{_i} shablonlarda «{_so}» yo'q ({_iz})", not any(_so in t for t in _tpl.values()),
          [k for k, t in _tpl.items() if _so in t])

# ══════════════════════════════════════════════════════════════
section("H / X. HTML in'ektsiya va xatolar")
# ══════════════════════════════════════════════════════════════
check("H1 HTML nomli mahsulot — guruh qatorida MATN (img onerror / <b> yo'q)", lambda: n("fin_xss")["img"] == 0
      and n("fin_xss")["qalin"] == 0 and "onerror" in (n("fin_xss")["nom"] or ""), n("fin_xss"))
check("H2 HTML nomli mahsulot turi — jadvalda MATN", lambda: n("prod_xss")["img"] == 0 and n("prod_xss")["qalin"] == 0
      and "onerror" in (n("prod_xss")["qator"] or ""), n("prod_xss"))
check("H3 skript ishlamadi — ro'yxatlardagi rasmlarga «yuklanmadi» hodisasi yuborildi, window.__xss yo'q", NAT.get("xss") is False, NAT.get("xss"))
check("X1 sahifa JS xatosi yo'q", not NAT.get("xato"), NAT.get("xato"))
check("X2 API 5xx yo'q", not NAT.get("api_xato"), NAT.get("api_xato"))
check("X3 qadamlarda istisno yo'q", not [k for k, v in N.items() if isinstance(v, dict) and "XATO" in v],
      {k: v for k, v in N.items() if isinstance(v, dict) and "XATO" in v})

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
