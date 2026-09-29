#!/usr/bin/env python3
"""
test_a115_ui.py — kech115, A bosqich (pul va ma'lumot xatolari): «Qarzdorlar», «Buyurtmalar», «O'chirilganlar» sahifalari —
HAQIQIY sahifalar (server bergan HTML, shablon + base.html skriptlari) jsdom da, HAQIQIY lokal server bilan (uvicorn, test
bazasi, admin sessiyasi). Soxta javob yo'q (faqat tarmoq uzilishi ataylab beriladi).

NIMA UCHUN KERAK (audit kech114 — O'LCHANGAN, asl kod = `staging` d1ba2b0)
  G3-01  Qarzdorlar: qarzdor tanlanishi bilan «Summa» ga butun qarz o'zi yozilardi va «✓ To'lovni qabul qilish» BIR bosishda,
         tasdiqsiz to'lov yozardi (audit roboti bosganda kassa +380 000 va +264 000).
  G3-02  «Qolgan qarzni chegirma qilib yopish» (15 px katak) to'lovdan keyin qolgan HAR QANDAY qarzni jimgina kechirardi
         (380 000 qarzga 10 000 → 370 000 kechirildi, xabar faqat «10 000 qabul qilindi»).
  G2-03  Buyurtmalar: «Tayyor» oynasi so'rovdan OLDIN yopilardi, server rad etsa xato yashirin qutida qolardi; to'lovni
         o'chirish rad etilsa ham hech narsa ko'rinmasdi.
  G2-07  Yangi buyurtma narxsiz (0 so'm) OGOHLANTIRISHSIZ yaratilardi.
  G6-01  O'chirilganlar jurnali «o'chirildi» / «tiklandi» dan boshqa HAMMA amalni «butunlay o'chirildi» derdi.
BO'LIMLAR: Q — Qarzdorlar; T — «Tayyor» (rad, tarmoq uzilishi, muvaffaqiyat); P — to'lovni o'chirish rad; N — narxsiz
           buyurtma; J — O'chirilganlar jurnali; S — statik (chaqiruv joylari); X — sahifa / server xatosi yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI (yiqiladi).
ISHLATISH: NODE_PATH=$(npm root -g) python3 tools/test_a115_ui.py
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
PG_BAZA = "a115_ui_test"
_T = tempfile.mkdtemp(prefix="a115ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'a115_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import UserRole, Inventory, Project, Order, Payment, ActivityLog   # noqa: E402
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


def tartibda(src, *qismlar):
    """Statik tartib tekshiruvi — `index` EMAS (topilmasa False, qulamaydi)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "a115_admin", "Parol123!", UserRole.ADMIN, "A115 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="A115 Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
PRJ = [Project(company_id=1, client_name=n, project_name=f"A115 loyiha {i}", total_budget=0, total_paid=0)
       for i, n in enumerate(["A115 Mijoz Ali", "A115 Mijoz Vali", "A115 Mijoz Soli", "A115 Mijoz Gani"])]
s.add_all([PENO] + PRJ)
s.commit()
PENO_ID = PENO.id
PID = [p.id for p in PRJ]
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "a115_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _lr.status_code in (200, 302, 303), _lr.status_code)


def buyurtma(pid, narx, dona, nom):
    r = req(C, "post", "/api/orders", json={
        "project_id": pid, "order_type": "product", "deadline": (tashkent_date() + timedelta(days=5)).isoformat(),
        "items": [{"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 100, "quantity": dona,
                   "unit_price": narx, "is_coated": False, "penoplast_id": PENO_ID}]})
    d = SessionLocal()
    try:
        o = d.query(Order).filter(Order.project_id == pid).order_by(Order.id.desc()).first()
        return (o.id if o else None), (o.order_number if o else None), r.status_code
    finally:
        d.close()


# Q: qarzdor — 380 000 (38 000 × 10)
O_QARZ, N_QARZ, _st1 = buyurtma(PID[0], 38000, 10, "A115 Karniz Q")
# T: «Tayyor» — rad (allaqachon tayyor) va muvaffaqiyat
O_RAD, _n2, _st2 = buyurtma(PID[1], 20000, 5, "A115 Karniz R")
_r_rad = req(C, "post", f"/api/orders/{O_RAD}/ready")
O_OK, _n3, _st3 = buyurtma(PID[2], 21000, 5, "A115 Karniz T")
# P: to'lov — o'chirishga (o'chirishni rad ettirish uchun hisobchi emas, begona id — 404)
_tp = req(C, "post", "/api/payments", json={"order_id": O_OK, "amount": 1000, "payment_method": "naqd"})
check("0 tayyorgarlik: 3 buyurtma, bittasi «Tayyor», to'lov", all(x for x in (O_QARZ, O_RAD, O_OK))
      and (_st1, _st2, _st3) == (200, 200, 200) and _r_rad.status_code == 200 and _tp.status_code == 200,
      (_st1, _st2, _st3, _r_rad.status_code, getattr(_r_rad, "text", "")[:200], _tp.status_code))
_r_rad2 = req(C, "post", f"/api/orders/{O_RAD}/ready")
check("0 «Tayyor» buyurtmani qayta «Tayyor» — server rad etadi (4xx)", 400 <= _r_rad2.status_code < 500,
      (_r_rad2.status_code, getattr(_r_rad2, "text", "")[:200]))

# J: jurnal — har xil amallar (1-korxona) va begona korxona yozuvi
s = SessionLocal()
for amal, tur, eid, nom in [("created", "order", 901, "ORD-J-CREATED"), ("activated", "production_order", 902, "PO-J-ACT"),
                            ("produced", "production_order", 903, "PO-J-PROD"), ("updated", "order", 904, "ORD-J-UPD"),
                            ("deleted", "order", 905, "ORD-J-DEL"), ("restored", "order", 906, "ORD-J-RES"),
                            ("permanently_deleted", "project", 907, "PRJ-J-PERM")]:
    s.add(ActivityLog(company_id=1, action=amal, entity_type=tur, entity_id=eid, entity_label=nom, performed_by="A115"))
s.commit()
s.close()

# ══════════════════════════════════════════════════════════════
# jsdom
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
          const resp = await fetch(url, Object.assign({}, o, { headers: h, redirect: "manual" }));
          if (resp.status >= 500) res.api_xato.push(resp.status + " " + url.slice(base.length, base.length + 120));
          w.__sorovlar.push({ url: url.slice(base.length), method: o.method || "GET", status: resp.status,
                              body: (o.method && o.method !== "GET") ? String(o.body || "").slice(0, 4000) : null });
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
    await kut(300);
    const t0 = Date.now();
    while (Date.now() - t0 < 15000) { await kut(60); if (pending === 0 && Date.now() - lastActive > 300) return; }
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

YORDAM = r"""
window.__msg = [];
window.__tasdiq = [];
window.__javob = true;
window.showMsg = (t, k) => { window.__msg.push([String(t), String(k || '')]); };
window.customConfirm = async (t, o) => { window.__tasdiq.push([String(t), o || null]); return window.__javob; };
window.showConfirmModal = async (t, o) => { window.__tasdiq.push([String(t), o || null]); return window.__javob; };
window.__m = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : null;
window.__post = yol => window.__sorovlar.filter(x => x.method === 'POST' && (x.url === yol || x.url.startsWith(yol + '?') || (yol.endsWith('/') && x.url.startsWith(yol))));
return true;
"""


def q(nom, amal=None, natija=None):
    return {"nom": nom, "amal": amal, "natija": natija}


QARZ = [
    q("yordam", natija=YORDAM),
    q("q_yuk", amal=f"const el = document.querySelector('#tab-customers .dbt-item[data-id=\"{O_QARZ}\"]'); selectOrderDebt(el);",
      natija=r"""return {summa: document.getElementById('pay-amount').value, tugma: !!document.getElementById('pay-full-btn'),
        katak_h: (document.getElementById('pay-writeoff').getAttribute('style') || '')};"""),
    q("q_butun", amal="payButunQarz();", natija="return document.getElementById('pay-amount').value;"),
    q("q_kechir", amal=r"""document.getElementById('pay-amount').value = '10 000';
      document.getElementById('pay-amount').dispatchEvent(new Event('input'));
      const cb = document.getElementById('pay-writeoff'); cb.checked = true; cb.dispatchEvent(new Event('change'));""",
      natija=r"""const z = document.getElementById('pay-writeoff-izoh');
        return {ko: z ? z.style.display : null, matn: z ? __m(z) : null};"""),
    q("q_bekor", amal="window.__javob = false; await savePayment();",
      natija="return {post: __post('/api/payments').length, tasdiq: window.__tasdiq.map(x => x[0]), danger: window.__tasdiq.map(x => x[1] && x[1].danger)};"),
    q("q_saqla", amal="window.__javob = true; window.__tasdiq = []; await savePayment();",
      natija="return {post: __post('/api/payments').length, url: (__post('/api/payments')[0] || {}).url, tasdiq: window.__tasdiq.map(x => x[0]), xabar: __m(document.getElementById('pay-msg'))};"),
]
TAYYOR = [
    q("yordam", natija=YORDAM),
    q("t_rad", amal=f"selectedOrderId = {O_RAD}; await markReadySelected(); await submitReadyModal();",
      natija=r"""const x = document.getElementById('readyModalXato');
        return {oyna: document.getElementById('readyModalOverlay').style.display, xato_ko: x ? x.style.display : null,
          xato: x ? __m(x) : null, msg: window.__msg.map(m => m[0]), box: document.getElementById('resultBox').style.display,
          tugma: document.getElementById('readyModalOk') ? document.getElementById('readyModalOk').disabled : null};"""),
    q("t_tarmoq", amal=r"""closeReadyModal(); await markReadySelected();
      window.__asil = window.fetch; window.fetch = async (u, o) => { if (String(u).includes('/ready')) throw new TypeError('Failed to fetch'); return window.__asil(u, o); };
      window.__msg = []; await submitReadyModal(); window.fetch = window.__asil;""",
      natija=r"""const x = document.getElementById('readyModalXato');
        return {oyna: document.getElementById('readyModalOverlay').style.display, xato: x ? __m(x) : null,
          msg: window.__msg.map(m => m[0])};"""),
    q("t_qayta_och", amal="closeReadyModal(); await markReadySelected();",
      natija="const x = document.getElementById('readyModalXato'); return x ? x.style.display : null;"),
    q("t_ok", amal=f"closeReadyModal(); selectedOrderId = {O_OK}; await markReadySelected(); window.__msg = []; await submitReadyModal();",
      natija=r"""return {oyna: document.getElementById('readyModalOverlay').style.display, box: document.getElementById('resultBox').style.display,
          box_matn: __m(document.getElementById('resultBox'))};"""),
    # P: to'lovni o'chirish — server rad etadi (yo'q to'lov → 404)
    q("p_rad", amal="window.__msg = []; window.__javob = true; await deletePayment(987654);",
      natija="return window.__msg.map(m => m);"),
    # N: narxsiz yangi buyurtma
    q("n_bekor", amal=f"""showNewForm();
      if (!document.querySelector('.detal')) addItem();
      document.getElementById('project_id').value = '{PID[3]}';
      document.getElementById('deadline_input').value = '{(tashkent_date() + timedelta(days=7)).isoformat()}';
      const row = document.querySelector('.detal');
      row.querySelector('.i-name').value = 'A115 Narxsiz Karniz';
      row.querySelector('.i-type').value = 'profil';
      row.querySelector('.i-h').value = '20'; row.querySelector('.i-w').value = '10'; row.querySelector('.i-l').value = '100';
      row.querySelector('.i-q').value = '5'; row.querySelector('.i-c').value = 'false';
      const bp = document.getElementById('base_price'); if (bp) bp.value = '';
      calculateItem(row);
      window.__tasdiq = []; window.__javob = false; window.__msg = [];
      await saveOrder(false);""",
      natija=r"""return {post: __post('/api/orders').length, tasdiq: window.__tasdiq.map(x => x[0]),
        narx: collectItems().map(i => i.unit_price), msg: window.__msg.map(m => m[0])};"""),
    q("n_ha", amal="window.__tasdiq = []; window.__javob = true; await saveOrder(false);",
      natija=r"""const p = __post('/api/orders'); return {post: p.length, status: (p[p.length - 1] || {}).status,
        tasdiq: window.__tasdiq.map(x => x[0])};"""),
]
JURNAL = [
    q("j", natija=r"""const k = [...document.querySelectorAll('.card')].find(c => /jurnal/i.test(c.querySelector('h3') ? c.querySelector('h3').textContent : ''));
      if (!k) return {yoq: true};
      const qatorlar = [...k.querySelectorAll('div[style*="justify-content:space-between"]')].map(d => d.firstElementChild ? d.firstElementChild.textContent.replace(/\s+/g, ' ').trim() : '');
      return {sarlavha: k.querySelector('h3').textContent.replace(/\s+/g, ' ').trim(), qatorlar,
        havola: !!k.querySelector('a[href="/logs"]')};"""),
]
SAHIFALAR = [{"yol": "/debts", "qadamlar": QARZ}, {"yol": "/orders", "qadamlar": TAYYOR}, {"yol": "/trash", "qadamlar": JURNAL}]

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
        lr = httpx.post(base + "/login", data={"username": "a115_admin", "password": "Parol123!"}, follow_redirects=False,
                        timeout=30)
        cookie = "; ".join(hh.split(";")[0] for hh in lr.headers.get_list("set-cookie"))
        pj = os.path.join(_T, "sahifalar.json")
        with open(pj, "w", encoding="utf-8") as f:
            json.dump(SAHIFALAR, f, ensure_ascii=False)
        sj = os.path.join(_T, "a115_ui.js")
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
check("U0 sahifalar 200, ssenariy tugadi", "fatal" not in NAT and N.get("yordam") is True
      and all(v == 200 for v in (NAT.get("sahifa") or {}).values()) and len(NAT.get("sahifa") or {}) == 3,
      {k: NAT.get(k) for k in ("sahifa", "fatal", "xato")})


def g(nom, kalit=None, std=None):
    v = N.get(nom)
    if kalit is None:
        return v
    return v.get(kalit, std) if isinstance(v, dict) else std


def bosh(t):
    return " ".join(str(t or "").replace(" ", " ").replace(" ", " ").split())


section("Q. Qarzdorlar — G3-01 / G3-02")
check("Q1 qarzdor tanlanganda «Summa» BO'SH (asl: butun qarz 380 000 o'zi yozilardi), «Butun qarz» tugmasi bor",
      g("q_yuk", "summa") == "" and g("q_yuk", "tugma") is True, N.get("q_yuk"))
check("Q2 «Butun qarz» → 380 000", bosh(N.get("q_butun")) == "380 000", N.get("q_butun"))
check("Q3 belgi + 10 000 → «Kechiriladi: 370 000 so'm (qarzning 97,4 %)» ko'rinadi (asl: yozuv yo'q)",
      g("q_kechir", "ko") == "block" and "Kechiriladi: 370 000 so'm (qarzning 97,4 %)" in bosh(g("q_kechir", "matn")),
      N.get("q_kechir"))
_tq = [bosh(x) for x in (g("q_bekor", "tasdiq") or [])]
check("Q4 saqlashdan oldin tasdiq: mijoz, buyurtma, summa va «Qolgan 370 000 so'm KECHIRILADI» (danger)",
      len(_tq) == 1 and f"A115 Mijoz Ali · {N_QARZ}: 10 000 so'm" in _tq[0] and "Qolgan 370 000 so'm KECHIRILADI" in _tq[0]
      and (g("q_bekor", "danger") or [None])[0] is True, (N.get("q_bekor"), N_QARZ))
check("Q5 tasdiqda «Bekor» → to'lov YOZILMADI (asl: bir bosishda yozilardi)", g("q_bekor", "post") == 0, N.get("q_bekor"))
s = SessionLocal()
_o = s.query(Order).filter(Order.id == O_QARZ).first()
_pay = [float(p.amount) for p in s.query(Payment).filter(Payment.order_id == O_QARZ).all()]
_kech = float(_o.kechirilgan_qarz or 0) if _o is not None else None
s.close()
check("Q6 «Ha» → bitta so'rov (write_off_remainder=true), serverda to'lov 10 000, kechirilgan 370 000",
      g("q_saqla", "post") == 1 and "write_off_remainder=true" in (g("q_saqla", "url") or "") and _pay == [10000.0]
      and _kech == 370000.0, (N.get("q_saqla"), _pay, _kech))
check("Q7 natija xabarida kechirilgan summa (asl: faqat «10 000 qabul qilindi»)",
      "370 000 so'm chegirma qilib kechirildi" in bosh(g("q_saqla", "xabar")), g("q_saqla", "xabar"))

section("T. «Tayyor» — G2-03")
check("T1 server rad etdi → oyna OCHIQ, sabab oynada (qizil) va xabarda (asl: oyna yopilib, xato yashirin qutida)",
      g("t_rad", "oyna") == "flex" and g("t_rad", "xato_ko") == "block" and "«Tayyor» saqlanmadi" in (g("t_rad", "xato") or "")
      and any(m.startswith("❌") for m in (g("t_rad", "msg") or [])) and g("t_rad", "tugma") is False, N.get("t_rad"))
check("T2 sabab — serverning o'z matni (texnik belgi / [object Object] yo'q)",
      len(bosh(g("t_rad", "xato"))) > 25 and "object" not in (g("t_rad", "xato") or "") and "{" not in (g("t_rad", "xato") or ""),
      g("t_rad", "xato"))
check("T3 tarmoq uzildi → oyna ochiq, «aloqa yo'q» — oynada va xabarda",
      g("t_tarmoq", "oyna") == "flex" and "aloqa yo'q" in (g("t_tarmoq", "xato") or "")
      and any("aloqa yo'q" in m for m in (g("t_tarmoq", "msg") or [])), N.get("t_tarmoq"))
check("T4 oyna qayta ochilganda eski xato ko'rinmaydi", N.get("t_qayta_och") == "none", N.get("t_qayta_och"))
check("T5 muvaffaqiyat → oyna yopildi, natija qutisi ko'rindi", g("t_ok", "oyna") == "none" and g("t_ok", "box") == "block"
      and "Buyurtma tayyor" in (g("t_ok", "box_matn") or ""), N.get("t_ok"))
s = SessionLocal()
_st_ok = s.query(Order).filter(Order.id == O_OK).first()
_st_ok = _st_ok.status.value if _st_ok is not None and _st_ok.status is not None else None
s.close()
check("T6 serverda buyurtma «Tayyor»", _st_ok == "ready", _st_ok)

section("P. To'lovni o'chirish rad etilsa — sabab")
_pm = N.get("p_rad") or []
check("P1 server rad etdi → qizil xabar sabab bilan (asl: hech narsa)", len(_pm) == 1 and _pm[0][1] == "error"
      and _pm[0][0].startswith("❌") and "topilmadi" in _pm[0][0].lower(), _pm)

section("N. Narxsiz yangi buyurtma — G2-07")
check("N1 narx kiritilmagan detal → tasdiq so'raldi, nom bilan (asl: OGOHLANTIRISHSIZ saqlanardi)",
      len(g("n_bekor", "tasdiq") or []) == 1 and "narxi KIRITILMAGAN" in (g("n_bekor", "tasdiq") or [""])[0]
      and "A115 Narxsiz Karniz" in (g("n_bekor", "tasdiq") or [""])[0] and g("n_bekor", "narx") == [0], N.get("n_bekor"))
check("N2 «Bekor» → buyurtma YUBORILMADI", g("n_bekor", "post") == 0, N.get("n_bekor"))
check("N3 «Ha, 0 bilan saqlash» → yuborildi (server 0 narxni qabul qiladi)", g("n_ha", "post") == 1
      and g("n_ha", "status") == 200 and any("narxi KIRITILMAGAN" in t for t in (g("n_ha", "tasdiq") or [])), N.get("n_ha"))

section("J. O'chirilganlar jurnali — G6-01")
_jq = g("j", "qatorlar") or []
check("J1 faqat o'chirish / tiklash / butunlay o'chirish (yaratildi, jarayonga olindi, ishlab chiqarildi, tahrir — YO'Q)",
      len(_jq) == 3 and not any(("CREATED" in x or "PO-J-ACT" in x or "PO-J-PROD" in x or "ORD-J-UPD" in x) for x in _jq), _jq)
check("J2 har amal o'z nomi bilan: o'chirildi / tiklandi / butunlay o'chirildi",
      any("ORD-J-DEL o'chirildi" in x for x in _jq) and any("ORD-J-RES tiklandi" in x for x in _jq)
      and any("PRJ-J-PERM butunlay o'chirildi" in x for x in _jq), _jq)
check("J3 «Barcha amallar — Tizim jurnallari» havolasi", g("j", "havola") is True, N.get("j"))
s = SessionLocal()
_cj = crud.get_activity_log(s, limit=50, company_id=1, amallar=getattr(crud, "CHIQINDI_JURNAL_AMALLARI", None)) \
    if "amallar" in crud.get_activity_log.__code__.co_varnames else []
s.close()
check("J4 `crud.get_activity_log(amallar=...)` — faqat 3 tur", sorted({a.action for a in _cj}) == ["deleted", "permanently_deleted", "restored"],
      sorted({a.action for a in _cj}))

section("S. Statik — chaqiruv joylari")
_ord = open(os.path.join(ROOT, "templates/orders.html"), encoding="utf-8").read()


def funksiya(src, nom):
    """Funksiya matni (qavslar bo'yicha); topilmasa ''."""
    i = src.find("function " + nom + "(")
    if i < 0:
        return ""
    j = src.find("{", i)
    d = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            d += 1
        elif src[k] == "}":
            d -= 1
            if d == 0:
                return src[i:k + 1]
    return ""


_upd, _sav, _rdy = funksiya(_ord, "updateOrder"), funksiya(_ord, "saveOrder"), funksiya(_ord, "submitReadyModal")
check("S1 tahrirda ham YANGI narxsiz qator tasdiqlanadi (`updateOrder` → `_narxsizTasdiq(_narxsizDetallar(items, true)`)",
      tartibda(_upd, "_narxsizTasdiq(_narxsizDetallar(items, true)", "O'zgarishlar saqlansinmi?"))
check("S2 yaratishda tasdiq tekshiruvlardan KEYIN, so'rovdan OLDIN",
      tartibda(_sav, "showValidationModal(issues)", "_narxsizTasdiq(_narxsizDetallar(items, false), isDraft)",
               "await submitOrderRequest("))
check("S3 «Tayyor» oynasi so'rovdan OLDIN yopilmaydi (faqat muvaffaqiyatda)",
      tartibda(_rdy, "await fetch(url", "closeReadyModal();") and not tartibda(_rdy, "closeReadyModal();", "await fetch(url"))

section("X. Xatolar")
check("X1 sahifa JS xatosi yo'q, 5xx yo'q", not NAT.get("xato") and not NAT.get("api_xato"), (NAT.get("xato"), NAT.get("api_xato")))
_5xx = [h for h in HOLATLAR if h[1] >= 500]
check("X2 API 5xx yo'q", not _5xx, _5xx[:5])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
