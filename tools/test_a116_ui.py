#!/usr/bin/env python3
"""
test_a116_ui.py — kech116, A bosqich 2-qism: sahifalar (HAQIQIY server — uvicorn, sahifalar — jsdom, sahifaning O'Z
JavaScript'i). Server qoidalari — `tools/test_a116_pdf.py`, `tools/test_a116_pul.py`, `tools/test_a116_kirish.py`.

NIMA UCHUN KERAK (audit kech114 — O'LCHANGAN, asl kod = `staging` 44c40ee)
  G2-04 (Buyurtmalar)  buyurtma oynasidagi «Hisob-kitob»: to'lovda kechirilgan qarz «Chegirma» ichida edi, ustama
                       ko'rinmasdi — PDF lar bilan bir qator emas.
  G1-03 / G1-02        Hisobotlar «Pul oqimi» kartasi = daromad − xarajat, bloki ham; «Tannarx» yo'q, doira xarajatning bir
                       qismi; Moliya bugungi «Pul oqimi» = savdo − xarajat; Dashboard «Pul oqimi (bu oy)» — uchinchi
                       formula, «Jami xarajat» = xarajat + tannarx, qatorlar unga teng emas.
  G2-01 (Loyihalar)    «Loyiha qiymati», «Qolgan to'lov», «N% to'langan», «Moliya» — «Byudjet» maydonidan (odatda 0).
  G6-06 (Foydalanuvchilar)  parol `prompt()` da ochiq yozilardi (o'z parolida uch oyna).
BO'LIMLAR: B — Buyurtmalar (hisob qatorlari); H — Hisobotlar; M — Moliya; D — Dashboard; L — Loyihalar;
  F — Foydalanuvchilar (parol oynasi); X — JS xatolari / 5xx.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI.
ISHLATISH: NODE_PATH=$(npm root -g) python3 tools/test_a116_ui.py
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
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "a116_ui_test"
_T = tempfile.mkdtemp(prefix="a116u_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'a116_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, Inventory, Project, OrderItem, ExpenseTransaction, TransportExpense,   # noqa: E402
                    FinishedProductSale, CashTransaction, User, UserSession)
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


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — buyurtmalar (qaytarish; chegirma + kechirilgan; ustama), pul harakatlari, loyiha
# ══════════════════════════════════════════════════════════════
BUGUN = tashkent_date()
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "u116_admin", "Parol123!", UserRole.ADMIN, "U116 Admin", company_id=1)
    auth.create_user(s, "u116_boshqa", "Parol123!", UserRole.MANAGER, "U116 <img src=x onerror=alert(1)>", company_id=1)
PRJ = [Project(company_id=1, client_name=f"U116 Mijoz {i}", project_name=f"U116 loyiha {i}", total_budget=0, total_paid=0)
       for i in range(4)]
PENO = Inventory(company_id=1, item_name="U116 Penoplast", unit="blok", stock_quantity=100000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
s.add_all(PRJ + [PENO])
s.commit()
PRJ_ID, PENO_ID = [p.id for p in PRJ], PENO.id
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "u116_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _lr.status_code in (200, 302, 303), _lr.status_code)

_n = [0]


def buyurtma(prj_i, narx, dona, kelishilgan=None):
    _n[0] += 1
    nom = f"U116_D{_n[0]}"
    r = req(C, "post", "/api/orders", json={
        "project_id": PRJ_ID[prj_i], "order_type": "product", "items": [
            {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 100, "quantity": dona,
             "unit_price": narx, "is_coated": False, "penoplast_id": PENO_ID}]})
    d = SessionLocal()
    try:
        oi = d.query(OrderItem).filter(OrderItem.name == nom).order_by(OrderItem.id.desc()).first()
        oid, iid = (oi.order_id, oi.id) if oi is not None else (None, None)
    finally:
        d.close()
    if oid and kelishilgan is not None:
        req(C, "put", f"/api/orders/{oid}/agreed-amount", json={"agreed_amount": kelishilgan})
    return oid, iid, nom, r.status_code


# A — qaytarish (loyiha 0): jami 900 000, to'langan 600 000, 36 000 qaytarish → qarz 264 000
oA, iA, nA, _ = buyurtma(0, 50000, 18)
req(C, "post", "/api/payments", json={"order_id": oA, "amount": 600000, "payment_method": "naqd"})
_it = next((x for x in (js(req(C, "get", f"/api/orders/{oA}")).get("items") or []) if x.get("id") == iA), {})
_u = float(_it.get("refund_price_per_unit") or 0)
_rr = req(C, "post", "/api/returns", json={"order_id": oA, "order_item_id": iA, "item_name": nA,
                                            "quantity": round(36000 / _u, 4) if _u else 0, "unit": "metr",
                                            "reason": "Ortiqcha", "refund_amount": 36000, "to_stock": False, "notes": None,
                                            "coating_applied": False})
_rid = (js(_rr) or {}).get("id") if isinstance(js(_rr), dict) else None
if _rid:
    req(C, "post", f"/api/returns/{_rid}/refund")
# B — chegirma 10 % + kechirilgan 5 000 (loyiha 1)
oB, iB, nB, _ = buyurtma(1, 50000, 20, kelishilgan=900000)
req(C, "post", "/api/payments?write_off_remainder=true", json={"order_id": oB, "amount": 895000, "payment_method": "naqd"})
# C — ustama (loyiha 1): jami 1 000 000, kelishilgan 1 100 000
oC, iC, nC, _ = buyurtma(1, 50000, 20, kelishilgan=1100000)
# D — qoralama loyiha 2 da (loyiha qiymatiga KIRMAYDI)
_rd = req(C, "post", "/api/orders", json={
    "project_id": PRJ_ID[2], "order_type": "product", "is_draft": True, "items": [
        {"name": "U116_QORALAMA", "category": "profil", "width": 20, "thickness": 10, "length": 100, "quantity": 5,
         "unit_price": 50000, "is_coated": False, "penoplast_id": PENO_ID}]})
# pul harakatlari — bugun
s = SessionLocal()
s.add(ExpenseTransaction(company_id=1, date=datetime.utcnow(), category="arenda", amount=400000, created_by="u116"))
s.add(TransportExpense(company_id=1, amount=60000, expense_date=datetime.utcnow()))
s.add(FinishedProductSale(company_id=1, product_name="U116 TM", quantity=1, unit="dona", unit_price=70000,
                          total_amount=70000, cost_amount=30000, sold_at=datetime.utcnow()))
s.add(CashTransaction(company_id=1, category="boshlangich", amount=10000000, created_at=datetime.utcnow()))
s.commit()
s.close()
_rdy = req(C, "post", f"/api/orders/{oB}/ready")
check("0 fikstura: 3 buyurtma, qaytarish, «Tayyor»", all([oA, oB, oC]) and _rid and _rdy.status_code == 200,
      (oA, oB, oC, _rid, _rdy.status_code, getattr(_rdy, "text", "")[:200]))


def uid(login):
    d = SessionLocal()
    try:
        return d.query(User.id).filter(User.username == login).scalar()
    finally:
        d.close()


# «boshqa» foydalanuvchi ikki joyda kirgan (parol almashtirilgach yopilishi kerak)
C_BOSHQA = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
req(C_BOSHQA, "post", "/login", data={"username": "u116_boshqa", "password": "Parol123!"}, follow_redirects=False)
BOSHQA_ID = uid("u116_boshqa")
ADMIN_ID = uid("u116_admin")

# ══════════════════════════════════════════════════════════════
# jsdom
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
      w.__promptlar = 0;
      w.alert = () => {}; w.confirm = () => false; w.prompt = () => { w.__promptlar++; return null; }; w.print = () => {};
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


M = r"const __m = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : null; const __k = id => { const e = document.getElementById(id); return e ? {matn: __m(e), korinadi: e.style.display !== 'none'} : null; };"
HISOB = M + r"""return {jami: __k('pay-total'), cheg: __k('pay-discount-row'), cheg_nom: __k('pay-discount-label'),
  cheg_qiy: __k('pay-discount'), qayt: __k('pay-refund-row'), qayt_qiy: __k('pay-refund'), kech: __k('pay-writeoff-row'),
  kech_qiy: __k('pay-writeoff'), kel: __k('pay-agreed'), tol: __k('pay-paid'), qarz: __k('pay-debt')};"""
BUY = [
    q("bA", amal=f"await loadPayments({oA});", natija=HISOB),
    q("bB", amal=f"await loadPayments({oB});", natija=HISOB),
    q("bC", amal=f"await loadPayments({oC});", natija=HISOB),
]
TK = f"const __y = {BUGUN.year}, __o = {BUGUN.month};"
HIS = [
    q("h", natija=M + TK + r"""
      const po = await (await fetch(`/api/finance/pul-oqimi?year=${__y}&month=${__o}`)).json();
      const kas = await (await fetch('/api/finance/cash-balance')).json();
      const hi = await (await fetch('/api/finance/history?months=1')).json();
      const cur = hi[hi.length - 1] || {};
      const tarkib = (cur.xarajat_tarkibi || []).filter(t => Number(t.summa) > 0);
      return {
        oqim: __m(document.getElementById('kpi-oqim')), oqim_k: fmtShort(po.balans) + " so'm",
        oqim_sub: __m(document.getElementById('kpi-oqim-sub')),
        kassa: __m(document.getElementById('kpi-kassa')), kassa_k: fmtShort(kas.balance) + " so'm",
        tannarx: __m(document.getElementById('kpi-tannarx')), tannarx_k: fmtShort(cur.tannarx_jami) + " so'm",
        xarajat: __m(document.getElementById('kpi-xarajat')), xarajat_k: fmtShort(cur.jami_xarajat) + " so'm",
        tenglama: __m(document.getElementById('kpi-tenglama')),
        teng_k: [fmtShort(cur.daromad), fmtShort(cur.tannarx_jami), fmtShort(cur.jami_xarajat), fmtShort(cur.sof_foyda)],
        legend: document.querySelectorAll('#donutLegend .bi-legend-row').length, tarkib_soni: tarkib.length,
        markaz: __m(document.getElementById('donutCenterValue')), markaz_k: fmtShort(cur.jami_xarajat),
        doira_nomlari: [...document.querySelectorAll('#donutLegend .bi-legend-name')].map(__m),
        fb_kirim: __m(document.getElementById('fb-kirim-summa')), fb_chiqim: __m(document.getElementById('fb-chiqim-summa')),
        fb_balans: __m(document.getElementById('fb-balans')), fb_k: [fmt(po.kirim) + " so'm", fmt(po.chiqim) + " so'm", fmt(po.balans) + " so'm"],
        fb_tarkib: [...document.querySelectorAll('#fb-chiqim-tarkib .bi-flow-qator')].length,
        davr: __m(document.getElementById('cashFlowDavr')), po_harakat: po.harakat_bor, cur_tarkib: tarkib.map(t => t.nom)};"""),
]
MOL = [
    # animateCounter (700 ms) tugashini kutish
    q("m", amal="await new Promise(r => setTimeout(r, 1200));", natija=M + r"""
      const bugun = tkISO();
      const po = await (await fetch(`/api/finance/pul-oqimi?sana=${bugun}`)).json();
      return {oqim: __m(document.getElementById('hero-oqim')), oqim_k: fmtFull(po.balans) + " so'm",
              sub: __m(document.getElementById('hero-oqim-sub')), kirim: po.kirim, chiqim: po.chiqim,
              rang: document.getElementById('hero-oqim').style.color};"""),
]
DASH = [
    q("d", natija=M + TK + r"""
      const po = await (await fetch(`/api/finance/pul-oqimi?year=${__y}&month=${__o}`)).json();
      const r = await (await fetch(`/api/finance/report?year=${__y}&month=${__o}`)).json();
      const qatorlar = [...document.querySelectorAll('#mf-expense-lines .dash-info-row')].map(__m);
      return {kirim: __m(document.getElementById('cf-kirim')), chiqim: __m(document.getElementById('cf-chiqim')),
              balans: __m(document.getElementById('cf-balans')), k: [fmt(po.kirim), fmt(po.chiqim), fmt(po.balans)],
              tannarx: __m(document.getElementById('mf-tannarx')), tannarx_k: '−' + fmt(r.tannarx_jami) + " so'm",
              jami: __m(document.getElementById('mf-jami-xarajat')), jami_k: fmt(r.jami_xarajat) + " so'm",
              qatorlar, tarkib_soni: (r.xarajat_tarkibi || []).filter(t => Number(t.summa) > 0).length};"""),
]
PRJ_JS = [
    q("l", natija=M + r"""
      const kartalar = [...document.querySelectorAll('.proj-card')].map(k => ({id: k.dataset.id, name: k.dataset.name,
        qiymat: k.dataset.qiymat, paid: k.dataset.paid, qarz: k.dataset.qarz, budget: k.dataset.budget,
        foiz: __m(k.querySelector('.proj-footer span:last-child'))}));
      return {kartalar, f_budget: !!document.getElementById('f-budget'), e_budget: !!document.getElementById('e-budget')};"""),
    q("l1", amal=f"selectProj(document.querySelector('.proj-card[data-id=\"{PRJ_ID[1]}\"]')); await new Promise(r => setTimeout(r, 300));",
      natija=M + r"""return {money: [...document.querySelectorAll('#moneyRow > div')].map(__m),
                              panel: __m(document.querySelector('#statusPanel .status-panel-item'))};"""),
    q("l2", amal="await renderFinance(document.querySelector('.proj-card.active').dataset);",
      natija=M + r"""return {fin: [...document.querySelectorAll('#tabContent .fin-stat')].map(__m)};"""),
    q("l3", amal=r"""
      openEditModal();
      window.__sorovlar.length = 0;
      const __aslFetch = window.fetch;
      window.fetch = async (u, o) => { window.__sorovlar.push({url: String(u), method: (o && o.method) || 'GET', body: o && o.body}); return {ok: false, status: 400, json: async () => ({detail: 'sinov'})}; };
      try { await saveEditProject(); } finally { window.fetch = __aslFetch; }""",
      natija=r"""const t = window.__sorovlar.find(x => x.method === 'PUT');
        let tana = null; try { tana = t ? JSON.parse(t.body) : null; } catch (e) { tana = {XATO: String(e)}; }
        return {tana};"""),
]
USR = [
    q("f1", amal=f"""
      const b = document.querySelector('button[data-username="u116_boshqa"]');
      changePass({BOSHQA_ID}, b ? b.dataset.username : 'u116_boshqa', b);""",
      natija=M + r"""return {modal: document.getElementById('parolModal') ? document.getElementById('parolModal').style.display : null,
        sarlavha: __m(document.getElementById('parol-sarlavha')), eski: document.getElementById('parol-eski-qator') ? document.getElementById('parol-eski-qator').style.display : null,
        turlar: ['parol-eski','parol-yangi','parol-takror'].map(i => document.getElementById(i) ? document.getElementById(i).type : null),
        prompt: window.__promptlar};"""),
    q("f2", amal=r"""
      document.getElementById('parol-yangi').value = 'Yangi123';
      document.getElementById('parol-takror').value = 'Boshqa123';
      window.__sorovlar.length = 0;
      await parolSaqlash();""",
      natija=M + r"""return {xato: __m(document.getElementById('parol-xato')), sorov: window.__sorovlar.filter(x => x.method === 'POST').length,
        modal: document.getElementById('parolModal').style.display};"""),
    q("f3", amal=r"""parolKozcha('parol-yangi', document.querySelector('#parolModal button[onclick*="parol-yangi"]'));""",
      natija=r"""const t1 = document.getElementById('parol-yangi').type;
        parolKozcha('parol-yangi', document.querySelector('#parolModal button[onclick*="parol-yangi"]'));
        return {ochiq: t1, yopiq: document.getElementById('parol-yangi').type};"""),
    q("f4", amal=r"""
      document.getElementById('parol-takror').value = 'Yangi123';
      window.__sorovlar.length = 0;
      window.__xabar = null;
      const __aslMsg = window.showMsg;
      window.showMsg = (t, tur) => { window.__xabar = {t: String(t), tur}; };
      try { await parolSaqlash(); } finally { window.showMsg = __aslMsg; }""",
      natija=r"""const p = window.__sorovlar.filter(x => x.method === 'POST');
        return {sorov: p.map(x => ({url: x.url, body: x.body})), modal: document.getElementById('parolModal').style.display,
                xabar: window.__xabar, maydon: document.getElementById('parol-yangi').value};"""),
    q("f5", amal=r"""
      parolKozcha('parol-takror', document.querySelector('#parolModal button[onclick*="parol-takror"]'));
      window.__f5_oldin = document.getElementById('parol-takror').type;
      parolYopish();
      changeMyPassword();""",
      natija=M + r"""return {eski: document.getElementById('parol-eski-qator').style.display, sarlavha: __m(document.getElementById('parol-sarlavha')),
        oldin: window.__f5_oldin, turlar: ['parol-eski','parol-yangi','parol-takror'].map(i => document.getElementById(i).type)};"""),
    q("f6", amal=r"""
      document.getElementById('parol-eski').value = 'notogri';
      document.getElementById('parol-yangi').value = 'Yangi456';
      document.getElementById('parol-takror').value = 'Yangi456';
      window.__sorovlar.length = 0;
      await parolSaqlash();""",
      natija=M + r"""return {xato: __m(document.getElementById('parol-xato')), modal: document.getElementById('parolModal').style.display,
        sorov: window.__sorovlar.filter(x => x.method === 'POST').length};"""),
    q("f7", amal=r"""
      document.getElementById('parol-eski').value = '';
      window.__sorovlar.length = 0;
      await parolSaqlash();""",
      natija=M + r"""return {xato: __m(document.getElementById('parol-xato')), sorov: window.__sorovlar.filter(x => x.method === 'POST').length};"""),
    q("f8", amal=r"""
      document.getElementById('parolModal').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));""",
      natija=r"""return {modal: document.getElementById('parolModal').style.display,
        img: document.querySelectorAll('#parol-sarlavha img, #parolModal img').length, prompt: window.__promptlar};"""),
    q("f9", amal=f"""
      const b = document.querySelector('button[data-username="u116_boshqa"]');
      changePass({BOSHQA_ID}, '<img src=x onerror="window.__xss=1">', b);""",
      natija=r"""return {img: document.querySelectorAll('#parol-sarlavha img').length, xss: window.__xss || 0,
        sarlavha: document.getElementById('parol-sarlavha').textContent};"""),
]
SAHIFALAR = [{"yol": "/orders", "qadamlar": BUY}, {"yol": "/reports", "qadamlar": HIS},
             {"yol": "/finance", "qadamlar": MOL}, {"yol": "/dashboard", "qadamlar": DASH},
             {"yol": "/projects", "qadamlar": PRJ_JS}, {"yol": "/users", "qadamlar": USR}]

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
        lr = httpx.post(base + "/login", data={"username": "u116_admin", "password": "Parol123!"}, follow_redirects=False,
                        timeout=30)
        cookie = "; ".join(hh.split(";")[0] for hh in lr.headers.get_list("set-cookie"))
        pj = os.path.join(_T, "sahifalar.json")
        with open(pj, "w", encoding="utf-8") as f:
            json.dump(SAHIFALAR, f, ensure_ascii=False)
        sj = os.path.join(_T, "a116u.js")
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
check("U0 sahifalar 200, ssenariy tugadi", "fatal" not in NAT and len(NAT.get("sahifa") or {}) == len(SAHIFALAR)
      and all(v == 200 for v in (NAT.get("sahifa") or {}).values()), {k: NAT.get(k) for k in ("sahifa", "fatal", "xato")})


def g(nom, kalit=None, std=None):
    v = N.get(nom)
    if kalit is None:
        return v
    return v.get(kalit, std) if isinstance(v, dict) else std


def m(nom, kalit):
    v = g(nom, kalit) or {}
    return v.get("matn") if isinstance(v, dict) else None


def k(nom, kalit):
    v = g(nom, kalit) or {}
    return v.get("korinadi") if isinstance(v, dict) else None


def bosh(t):
    return " ".join(str(t or "").replace(" ", " ").replace(" ", " ").split())


section("B. Buyurtmalar — «Hisob-kitob» qatorlari (PDF lar bilan bir qoida)")
check("B1 qaytarish: Jami 900 000, «Qaytarish −36 000», chegirma va kechirilgan qatorlari YO'Q, kelishilgan 864 000, "
      "qarz 264 000", bosh(m("bA", "jami")) == "900 000 so'm" and k("bA", "cheg") is False and k("bA", "qayt") is True
      and bosh(m("bA", "qayt_qiy")) == "−36 000 so'm" and k("bA", "kech") is False and bosh(m("bA", "kel")) == "864 000 so'm"
      and bosh(m("bA", "qarz")) == "264 000 so'm", N.get("bA"))
check("B2 chegirma + kechirilgan: «Chegirma −100 000 (10%)» (kechirilgan chegirmaga QO'SHILMAGAN), «Kechirilgan qarz −5 000», "
      "kelishilgan 895 000, qarz 0 (asl: «Chegirma −105 000»)",
      bosh(m("bB", "cheg_qiy")) == "−100 000 so'm (10%)" and bosh(m("bB", "cheg_nom")) == "Chegirma:"
      and k("bB", "kech") is True and bosh(m("bB", "kech_qiy")) == "−5 000 so'm" and bosh(m("bB", "kel")) == "895 000 so'm"
      and bosh(m("bB", "qarz")) == "0 so'm", N.get("bB"))
check("B3 ustama: «Ustama: +100 000», kelishilgan 1 100 000, qarz 1 100 000 (asl: ustama ko'rinmasdi)",
      k("bC", "cheg") is True and bosh(m("bC", "cheg_nom")) == "Ustama:" and bosh(m("bC", "cheg_qiy")) == "+100 000 so'm"
      and bosh(m("bC", "kel")) == "1 100 000 so'm" and bosh(m("bC", "qarz")) == "1 100 000 so'm", N.get("bC"))

section("H. Hisobotlar — pul oqimi (haqiqiy pul), tannarx, xarajat bitta ta'rif")
check("H1 «Pul oqimi» kartasi = /api/finance/pul-oqimi balansi (asl: daromad − xarajat)", g("h", "oqim") and g("h", "oqim") == g("h", "oqim_k"),
      (g("h", "oqim"), g("h", "oqim_k")))
check("H2 «Pul oqimi» izohi — olingan − to'langan", "olingan" in (g("h", "oqim_sub") or "") and "to'langan" in (g("h", "oqim_sub") or ""),
      g("h", "oqim_sub"))
check("H3 «Kassa» kartasi = kassa balansi", g("h", "kassa") and g("h", "kassa") == g("h", "kassa_k"), (g("h", "kassa"), g("h", "kassa_k")))
check("H4 «Tannarx» kartasi = `tannarx_jami`; «Xarajat» = `jami_xarajat`", g("h", "tannarx") == g("h", "tannarx_k")
      and g("h", "xarajat") == g("h", "xarajat_k") and g("h", "tannarx_k") not in (None, "0 so'm"), N.get("h"))
_tg = g("h", "tenglama") or ""
check("H5 tenglama «Daromad … − Tannarx … − Xarajat … = Sof foyda …» — kartalardagi qiymatlar bilan",
      _tg.startswith("Daromad") and all((x or "") in _tg for x in (g("h", "teng_k") or ["?"])), (_tg, g("h", "teng_k")))
check("H6 «Xarajat tarkibi» doirasi — to'liq tarkib (transport ham), markaz = «Xarajat» (asl: 5 tur, transport / brak yo'q)",
      g("h", "legend") == g("h", "tarkib_soni") and (g("h", "tarkib_soni") or 0) >= 2 and g("h", "markaz") == g("h", "markaz_k")
      and "Transport" in (g("h", "doira_nomlari") or []), (g("h", "legend"), g("h", "tarkib_soni"), g("h", "markaz"),
                                                            g("h", "markaz_k"), g("h", "doira_nomlari")))
check("H7 «Pul oqimi» bloki: kirim / chiqim / balans = API (haqiqiy pul), chiqim tarkibi ko'rinadi",
      [bosh(x) for x in (g("h", "fb_kirim"), g("h", "fb_chiqim"), g("h", "fb_balans"))] == [bosh(x) for x in (g("h", "fb_k") or [])]
      and (g("h", "fb_tarkib") or 0) >= 2
      and "olingan va to'langan pul" in (g("h", "davr") or ""), (g("h", "fb_kirim"), g("h", "fb_chiqim"), g("h", "fb_balans"),
                                                                  g("h", "fb_k"), g("h", "fb_tarkib"), g("h", "davr")))

section("M. Moliya — bugungi «Pul oqimi» haqiqiy pul")
check("M1 kartadagi qiymat = /api/finance/pul-oqimi?sana=bugun balansi (asl: savdo − xarajat)",
      g("m", "oqim") and bosh(g("m", "oqim")) == bosh(g("m", "oqim_k")),
      N.get("m"))
check("M2 izoh «Olingan … − to'langan … so'm (bugun)»; manfiy — qizil",
      (g("m", "sub") or "").startswith("Olingan") and "(bugun)" in (g("m", "sub") or "")
      and ((g("m", "rang") == "var(--f-danger)") == (float(g("m", "kirim") or 0) < float(g("m", "chiqim") or 0))), N.get("m"))

section("D. Dashboard — pul oqimi va «Bu oy moliyaviy holat»")
# kech118 (zip 124 — egasi QARORI G1-09 «Vazifalar ajratilsin», MOSLANDI): «Pul oqimi (bu oy)» va «Bu oy moliyaviy holat»
# Dashboard dan OLIB TASHLANDI (oylik tahlil — Hisobotlar: kpi-oqim / cashFlowBars / «Asosiy ko'rsatkichlar», yuqoridagi bo'limlar).
check("D1 Dashboard da «Pul oqimi (bu oy)» va «Bu oy moliyaviy holat» bloklari YO'Q (Hisobotlar da — takror emas)",
      [g("d", "kirim"), g("d", "chiqim"), g("d", "balans"), g("d", "tannarx"), g("d", "jami")] == [None] * 5
      and not (g("d", "qatorlar") or []), (g("d", "kirim"), g("d", "tannarx"), g("d", "jami"), g("d", "qatorlar")))

section("L. Loyihalar — qiymat buyurtmalardan")
_kart = {c.get("id"): c for c in (g("l", "kartalar") or [])}
_p0, _p1, _p2 = _kart.get(str(PRJ_ID[0]), {}), _kart.get(str(PRJ_ID[1]), {}), _kart.get(str(PRJ_ID[2]), {})
check("L1 loyiha 0 (qaytarishli buyurtma): qiymat 864 000, to'langan 600 000, qarz 264 000, «69% to'langan» (asl: byudjet 0 — «0%»)",
      abs(float(_p0.get("qiymat") or -1) - 864000) < 0.01 and abs(float(_p0.get("paid") or -1) - 600000) < 0.01
      and abs(float(_p0.get("qarz") or -1) - 264000) < 0.01 and _p0.get("foiz") == "69% to'langan", _p0)
check("L2 loyiha 1 (chegirmali + ustamali): qiymat 895 000 + 1 100 000 = 1 995 000, to'langan 895 000, qarz 1 100 000",
      abs(float(_p1.get("qiymat") or -1) - 1995000) < 0.01 and abs(float(_p1.get("qarz") or -1) - 1100000) < 0.01
      and _p1.get("foiz") == "45% to'langan", _p1)
check("L3 loyiha 2 — faqat qoralama: qiymat 0 (qoralama hisobga KIRMAYDI)", abs(float(_p2.get("qiymat") or -1)) < 0.01, _p2)
check("L4 kartada `data-budget` yo'q; formalarda «Byudjet» maydoni yo'q", all(c.get("budget") is None for c in _kart.values())
      and g("l", "f_budget") is False and g("l", "e_budget") is False, (g("l", "f_budget"), g("l", "e_budget")))
_mon = [bosh(x) for x in (g("l1", "money") or [])]
check("L5 tanlangan loyiha: «Loyiha qiymati 1 995 000 · To'langan 895 000 · Qolgan to'lov 1 100 000», panel «45%»",
      _mon == ["Loyiha qiymati 1 995 000 so'm", "To'langan 895 000 so'm", "Qolgan to'lov 1 100 000 so'm"]
      and bosh(g("l1", "panel") or "").startswith("45%"), (_mon, g("l1", "panel")))
_fin = [bosh(x) for x in (g("l2", "fin") or [])]
check("L6 «Moliya» yorlig'i: «Loyiha qiymati 1 995 000», «To'langan 895 000», «Qarz 1 100 000» («Byudjet» yo'q)",
      len(_fin) == 4 and _fin[0] == "Loyiha qiymati 1 995 000 so'm" and _fin[1] == "To'langan 895 000 so'm"
      and _fin[2] == "Qarz 1 100 000 so'm", _fin)
_tana = g("l3", "tana") or {}
check("L7 tahrir saqlash tanasida `total_budget` YO'Q (bazadagi ustunga tegilmaydi)", isinstance(_tana, dict) and _tana
      and "total_budget" not in _tana and _tana.get("project_name"), _tana)

section("F. Foydalanuvchilar — parol oynasi")
check("F1 «Parol» — dastur oynasi (prompt EMAS), maydonlar yashirin (password), joriy parol qatori yashirin",
      g("f1", "modal") == "flex" and g("f1", "prompt") == 0 and g("f1", "turlar") == ["password", "password", "password"]
      and g("f1", "eski") == "none" and "u116_boshqa" in (g("f1", "sarlavha") or ""), N.get("f1"))
check("F2 takror mos emas — oynada xato, so'rov yuborilmadi", "mos kelmadi" in (g("f2", "xato") or "") and g("f2", "sorov") == 0
      and g("f2", "modal") == "flex", N.get("f2"))
check("F3 ko'zcha: ko'rsatish (text) ↔ yashirish (password)", g("f3", "ochiq") == "text" and g("f3", "yopiq") == "password", N.get("f3"))
_f4 = g("f4", "sorov") or []
check("F4 to'g'ri — BITTA POST /api/users/{id}/password {new_password}, oyna yopildi, maydonlar tozalandi, xabar «ochiq kirishlari yopildi»",
      len(_f4) == 1 and _f4[0].get("url") == f"/api/users/{BOSHQA_ID}/password"
      and json.loads(_f4[0].get("body") or "{}") == {"new_password": "Yangi123"} and g("f4", "modal") == "none"
      and g("f4", "maydon") == "" and "kirishlari yopildi" in ((g("f4", "xabar") or {}).get("t") or ""), N.get("f4"))
check("F5 «Parolimni o'zgartirish» — joriy parol qatori ko'rinadi", g("f5", "eski") == "" and "Parolimni" in (g("f5", "sarlavha") or ""),
      N.get("f5"))
check("F5b ko'zcha ochiq qoldirilib yopilgan oyna qayta ochilganda — uchala maydon yana yashirin (password)",
      g("f5", "oldin") == "text" and g("f5", "turlar") == ["password", "password", "password"], N.get("f5"))
check("F6 joriy parol noto'g'ri — server sababi oynada («Joriy parol noto'g'ri»), oyna ochiq", "noto'g'ri" in (g("f6", "xato") or "")
      and g("f6", "modal") == "flex" and g("f6", "sorov") == 1, N.get("f6"))
check("F7 joriy parol bo'sh — so'rovsiz xato", "Joriy parolni kiriting" in (g("f7", "xato") or "") and g("f7", "sorov") == 0, N.get("f7"))
check("F8 Esc — oyna yopiladi; butun ssenariyda prompt() chaqirilmadi", g("f8", "modal") == "none" and g("f8", "prompt") == 0, N.get("f8"))
check("F9 nomdagi HTML — matn (element yaratilmaydi)", g("f9", "img") == 0 and not g("f9", "xss")
      and "<img" in (g("f9", "sarlavha") or ""), N.get("f9"))
_d = SessionLocal()
try:
    _bs = _d.query(UserSession).filter(UserSession.user_id == BOSHQA_ID).count()
    _as = _d.query(UserSession).filter(UserSession.user_id == ADMIN_ID).count()
finally:
    _d.close()
check("F10 sahifadan parol almashtirilgach «boshqa» ning ochiq kirishi yopildi; admin sessiyalari joyida",
      _bs == 0 and _as >= 1 and req(C_BOSHQA, "get", "/api/orders").status_code == 401, (_bs, _as))

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
