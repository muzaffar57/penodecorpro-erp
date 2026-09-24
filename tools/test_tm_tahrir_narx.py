"""test_tm_tahrir_narx.py — 75-band (kech67): "Tayyor mahsulotdan" (TM) olingan detal
narxi buyurtmani TAHRIRLAB saqlaganda o'zgarmasligi.

Nuqson (kech66 da O'LCHANGAN, `work/probe75.py`): `orders.html` `editSelected` TM qatori
narxini (`row.dataset.fpPrice`) tayyor mahsulotning JORIY narxidan (`/api/finished`)
olardi — TM narxi keyin o'zgargan bo'lsa detal narxi jimgina yangi narxga o'tardi
(4 500 -> 6 000); TM ro'yxatdan yashirin bo'lsa (qoldiq 0, eski) narx 0 bo'lardi yoki
buyurtmaning asosiy narxidan formula bilan qayta hisoblanardi.

Tuzatish: `tmSaqlanganBirlikNarxi(item, cat)` — detalning SAQLANGAN 1 birlik narxi;
'edit' rejimida fpPrice shundan (fetch dan OLDIN), `/api/finished` faqat qoldiq uchun;
'duplicate' (nusxa — yangi sotuv) rejimida TM ro'yxatda bo'lsa JORIY narx (yangi tanlov
kabi), yashirin bo'lsa saqlangan narx.

Bo'limlar:
  A  yordamchi `tmSaqlanganBirlikNarxi` — HAQIQIY orders.html dan ajratib, node da
  B  oqim — haqiqiy /orders sahifasi (uvicorn + jsdom): yaratish sahifaning O'Z
     `pickFinished` + `saveOrder`, tahrir YANGI sahifada `editSelected('edit')` +
     `updateOrder` (tasdiq -> true), natija BAZADAN o'qiladi
  C  nusxa (`editSelected('duplicate')`) — `collectItems()` tanasi
  D  statik — editSelected ichidagi tartib (orders.html matni)

Faqat SQLite (UI yo'li; bazaga bog'liq mantiq yo'q). jsdom (`npm install -g jsdom@24`)
topilmasa B / C bo'limlari YIQILADI (jim o'tmaydi).
Ishga tushirish: python3 tools/test_tm_tahrir_narx.py
"""
import os
import sys
import io
import json
import time
import socket
import shutil
import tempfile
import threading
import subprocess
import contextlib
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
_T = tempfile.mkdtemp(prefix="tm_tahrir_")
os.environ["DATABASE_URL"] = f"sqlite:///{_T}/tm_tahrir.db"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, FinishedProduct, Order, StockSource, ProductionStatus,
)

OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


def tartibda(src, *qismlar):
    """Qismlar matnda AYNAN shu tartibda (`find`, topilmasa False — qulamaydi)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def teng(a, b, tol=0.005):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


HTML_YOL = os.path.join(ROOT, "templates", "orders.html")
HTML = open(HTML_YOL, encoding="utf-8").read()


def funksiya_matni(src, nom):
    """`function nom(` dan qavs muvozanati bo'yicha tana oxirigacha; topilmasa None."""
    i = src.find("function " + nom + "(")
    if i < 0:
        return None
    j = src.find("{", i)
    if j < 0:
        return None
    d = 0
    k = j
    while k < len(src):
        c = src[k]
        if c == "{":
            d += 1
        elif c == "}":
            d -= 1
            if d == 0:
                return src[i:k + 1]
        k += 1
    return None


try:
    NODE_PATH = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=60).stdout.strip()
except Exception:
    NODE_PATH = ""
ENV = dict(os.environ)
ENV["NODE_PATH"] = NODE_PATH


def node_js(kod, *args, timeout=150):
    f = os.path.join(_T, "n_%d.js" % int(time.time() * 1e6))
    open(f, "w", encoding="utf-8").write(kod)
    try:
        k = subprocess.run(["node", f] + [str(a) for a in args], capture_output=True, text=True,
                           env=ENV, timeout=timeout)
    except Exception as e:
        return {"istisno_py": f"{type(e).__name__}: {e}"}
    for q in k.stdout.splitlines():
        if q.startswith("NATIJA_JSON "):
            try:
                return json.loads(q[len("NATIJA_JSON "):])
            except Exception as e:
                return {"istisno_py": f"json: {e}"}
    return {"stdout": k.stdout[-600:], "stderr": k.stderr[-600:]}


# ═════════════════════════════════════════════════════════════════════════
section("A. tmSaqlanganBirlikNarxi — HAQIQIY orders.html dan")
FN = funksiya_matni(HTML, "tmSaqlanganBirlikNarxi")
check("A0 funksiya orders.html da bor", FN is not None)
HOLATLAR_A = [
    ("A1 profil 3 m, miqdor 1, qator 4500 -> 1 metr 1500",
     {"category": "profil", "unit_price": 4500, "length": 3, "quantity": 1}, "profil", 1500),
    ("A2 profil miqdor 2 (qator/miqdor = 2250) -> 1 metr 1500",
     {"category": "profil", "unit_price": 2250, "length": 3, "quantity": 2}, "profil", 1500),
    ("A3 profil miqdor yo'q -> 1 deb olinadi",
     {"category": "profil", "unit_price": 4500, "length": 3}, "profil", 1500),
    ("A4 profil uzunlik 0 -> null (aniqlab bo'lmaydi)",
     {"category": "profil", "unit_price": 4500, "length": 0, "quantity": 1}, "profil", None),
    ("A5 profil uzunlik yo'q -> null",
     {"category": "profil", "unit_price": 4500, "quantity": 1}, "profil", None),
    ("A6 panel -> unit_price o'zi",
     {"category": "panel", "unit_price": 1200, "length": 3, "quantity": 4}, "panel", 1200),
    ("A7 dona -> unit_price o'zi", {"category": "dona", "unit_price": 777.5, "quantity": 3}, "dona", 777.5),
    ("A8 blok -> unit_price o'zi", {"category": "blok", "unit_price": 950, "quantity": 5, "length": 0}, "blok", 950),
    ("A9 saqlangan narx 0 -> 0 (null EMAS)",
     {"category": "profil", "unit_price": 0, "length": 3, "quantity": 1}, "profil", 0),
    ("A10 unit_price null -> null", {"category": "panel", "unit_price": None}, "panel", None),
    ("A11 unit_price yo'q -> null", {"category": "panel"}, "panel", None),
    ("A12 unit_price '' -> null", {"category": "panel", "unit_price": ""}, "panel", None),
    ("A13 unit_price manfiy -> null", {"category": "panel", "unit_price": -5}, "panel", None),
    ("A14 unit_price son emas -> null", {"category": "panel", "unit_price": "abc"}, "panel", None),
    ("A15 unit_price matn '4500' (JSON satr) -> 1500",
     {"category": "profil", "unit_price": "4500", "length": "3", "quantity": "1"}, "profil", 1500),
    ("A16 kategoriya yo'q, cat 'profil' (editSelected standarti) -> profil formulasi",
     {"unit_price": 4500, "length": 3, "quantity": 1}, "profil", 1500),
    ("A17 item null -> null", None, "profil", None),
    ("A18 profil kasr: 7 m x 1333.33 = 9333.31 -> 1333.33",
     {"category": "profil", "unit_price": 9333.31, "length": 7, "quantity": 1}, "profil", 1333.33),
]
if FN is not None:
    js = FN + "\nconst H = " + json.dumps([[h[1], h[2]] for h in HOLATLAR_A]) + ";\n" + \
        "const r = H.map(([it, cat]) => { try { const v = tmSaqlanganBirlikNarxi(it, cat); " \
        "return (v === null) ? 'NULL' : (typeof v === 'number' && isFinite(v) ? v : 'XATO:' + String(v)); } " \
        "catch (e) { return 'ISTISNO:' + String(e); } });\n" \
        "console.log('NATIJA_JSON ' + JSON.stringify(r));\n"
    rA = node_js(js)
    if isinstance(rA, list) and len(rA) == len(HOLATLAR_A):
        for (lab, _it, _cat, kut), v in zip(HOLATLAR_A, rA):
            if kut is None:
                check(lab, v == "NULL", v)
            else:
                check(lab, isinstance(v, (int, float)) and abs(v - kut) < 1e-9, v)
    else:
        for h in HOLATLAR_A:
            check(h[0], False, rA)
else:
    for h in HOLATLAR_A:
        check(h[0], False, "funksiya yo'q")


# ═════════════════════════════════════════════════════════════════════════
# Fikstura + server
db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "TMT_admin", "Parol123!", UserRole.ADMIN, "TMT", company_id=1)
prj = Project(company_id=1, client_name="TMT Mijoz", project_name="TMT loyiha", total_budget=0, total_paid=0)
peno = Inventory(company_id=1, item_name="TMT PENO", unit="blok", stock_quantity=1000, min_stock=0,
                 is_penoplast=True, volume_per_unit=1, price_per_unit=500000)
db.add_all([prj, peno])
db.commit()
PRJ, PENO = prj.id, peno.id
# "Blok" turi eskirgan va standart O'CHIQ (`main.cat_on`) — B8 uchun korxona sozlamasida
# yoqiladi (sozlamasi yoqilgan eski korxona holati). Kesh tozalanadi.
try:
    import crud                                    # noqa: E402
    _hamma = ",".join(k for k, _ in getattr(main, "IXTIYORIY_KATEGORIYALAR", []))
    crud.set_setting(db, "enabled_categories", _hamma, company_id=1)
    getattr(main, "_kategoriya_cache", {}).clear()
except Exception as _e:
    print("  (blok turini yoqib bo'lmadi:", _e, ")")
db.close()


def yangi_tm(nomi, kategoriya, narx, birlik="metr"):
    s = SessionLocal()
    try:
        f = FinishedProduct(company_id=1, name=nomi, category=kategoriya, is_coated=False, width=10, thickness=10,
                            quantity=100, produced_quantity=100, unit=birlik, unit_price=narx,
                            cost_price=100 * 1000, unit_cost_stable=1000, source=StockSource.PRODUCED,
                            penoplast_id=PENO, unit_volume_m3=0.005, production_status=ProductionStatus.READY)
        s.add(f)
        s.commit()
        return f.id
    finally:
        s.close()


def narx_ozgart(fid, yangi=2000):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid)
        f.unit_price = yangi
        s.commit()
    finally:
        s.close()


def yashir(fid):
    """Asosiy ro'yxatdan yashirinadi: qoldiq 0, 200 kun oldin, tayyor."""
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid)
        f.quantity = 0
        f.created_at = datetime.utcnow() - timedelta(days=200)
        s.commit()
    finally:
        s.close()


def buyurtma(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if o is None:
            return None
        return {
            "items": [{"name": i.name, "unit_price": float(i.unit_price or 0), "total_price": float(i.total_price or 0),
                       "fp": i.finished_product_id, "length": float(i.length or 0), "quantity": float(i.quantity or 0)}
                      for i in o.items],
            "total": float(o.total_amount or 0),
            "agreed": float(o.agreed_amount or 0),
        }
    finally:
        s.close()


def oxirgi_buyurtma_id():
    s = SessionLocal()
    try:
        return max([o.id for o in s.query(Order).all()] or [0])
    finally:
        s.close()


NODE_SAHIFA = r"""
const { JSDOM, VirtualConsole, ResourceLoader } = require("jsdom");
const [base, cookie, rejim, a1, a2, a3, a4, a5] = process.argv.slice(2);
class R extends ResourceLoader {
  fetch(url, o) {
    if (url.startsWith(base)) return super.fetch(url, o);
    const p = Promise.resolve(Buffer.from("window.Chart = function(){return {destroy(){},update(){}}};"));
    p.abort = () => {};
    return p;
  }
}
const kut = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const out = { xato: [] };
  try {
    const html = await (await fetch(base + "/orders", { headers: { cookie } })).text();
    const vc = new VirtualConsole();
    vc.on("jsdomError", e => { const m = String(e && (e.message || e)).slice(0, 200); if (!/Not implemented|parse CSS/.test(m)) out.xato.push(m); });
    let pending = 0;
    const posts = [];
    const bloklaFinished = (rejim === "tahrir_blok");
    const dom = new JSDOM(html, {
      url: base + "/orders", runScripts: "dangerously", pretendToBeVisual: true, resources: new R(), virtualConsole: vc,
      beforeParse(w) {
        w.fetch = async (u, o) => {
          const url = new URL(String(u), base + "/orders").href;
          if (bloklaFinished && w.__tahrirBoshlandi && /\/api\/finished(\?|$)/.test(url.slice(base.length))) {
            throw new Error("sinov: /api/finished bloklandi");
          }
          pending++;
          try {
            o = o || {};
            const h = Object.assign({}, o.headers || {}); h.cookie = cookie;
            const r = await fetch(url, Object.assign({}, o, { headers: h, redirect: "manual" }));
            if (o.method && o.method !== "GET") posts.push([o.method, url.slice(base.length), r.status, o.body ? String(o.body).slice(0, 4000) : null]);
            return r;
          } finally { pending--; }
        };
        w.alert = () => {}; w.confirm = () => true; w.scrollTo = () => {}; w.open = () => null;
        w.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
        w.HTMLElement.prototype.scrollIntoView = function () {};
      },
    });
    const w = dom.window;
    const tinch = async () => { for (let i = 0; i < 100; i++) { await kut(100); if (pending === 0) { await kut(300); if (pending === 0) return; } } };
    await kut(500); await tinch();
    const set = (el, v) => { el.value = v; el.dispatchEvent(new w.Event("input", { bubbles: true })); el.dispatchEvent(new w.Event("change", { bubbles: true })); };
    const soddala = its => (its || []).map(i => ({ category: i.category, unit_price: i.unit_price, quantity: i.quantity,
                                                   length: i.length, finished_product_id: i.finished_product_id, price_per_m3: i.price_per_m3 }));
    if (rejim === "yarat") {
      // a1 = loyiha, a2 = TM id, a3 = miqdor (profil — uzunlik, qolganlari .i-q), a4 = asosiy narx
      set(w.document.getElementById("project_id"), a1);
      set(w.document.getElementById("deadline_input"), "2026-12-30");
      set(w.document.getElementById("base_price"), a4 || "");
      w.eval("addItem()");
      let row = w.document.querySelectorAll(".detal")[0];
      const list = await (await w.fetch("/api/finished")).json();
      const fp = list.find(f => String(f.id) === String(a2));
      if (!fp) throw new Error("TM ro'yxatda yo'q: " + a2);
      const el = w.document.createElement("div");
      el.dataset.fp = JSON.stringify(fp);
      row.appendChild(el);
      w.pickFinished(el, fp.id);
      el.remove();
      row = w.document.querySelectorAll(".detal")[0];
      const tur = row.querySelector(".i-type").value;
      set(row.querySelector(tur === "profil" ? ".i-l" : ".i-q"), a3);
      w.calculateItem(row);
      out.items = soddala(w.eval("collectItems()"));
      await w.eval("saveOrder(false)");
      await tinch();
      out.posts = posts.map(p => [p[0], p[1], p[2]]);
    } else if (rejim === "tahrir" || rejim === "tahrir_blok" || rejim === "nusxa") {
      // a1 = buyurtma id, a2 = "saqla" (faqat tahrir)
      w.__tahrirBoshlandi = true;
      w.eval("selectedOrderId = " + Number(a1));
      await w.eval(rejim === "nusxa" ? "editSelected('duplicate')" : "editSelected('edit')");
      await tinch(); await kut(400); await tinch();
      const row = w.document.querySelectorAll(".detal")[0];
      out.fpPrice = row ? (row.dataset.fpPrice === undefined ? null : row.dataset.fpPrice) : null;
      out.fpId = row ? row.dataset.fpId : null;
      out.items = soddala(w.eval("collectItems()"));
      if (rejim === "tahrir" && a2 === "saqla") {
        const tasdiq = [];
        w.showConfirmModal = async (m) => { tasdiq.push(String(m).slice(0, 200)); return true; };
        w.customConfirm = async (...m) => { tasdiq.push(m.join(" | ").slice(0, 200)); return true; };
        w.showMsg = (m) => { tasdiq.push("MSG " + String(m).slice(0, 200)); };
        await w.eval("updateOrder(" + Number(a1) + ")");
        await tinch();
        out.tasdiq = tasdiq;
        const put = posts.filter(p => p[0] === "PUT");
        out.put = put.map(p => [p[1], p[2]]);
        try { out.put_items = put.length ? soddala(JSON.parse(put[put.length - 1][3]).items) : null; } catch (e) { out.put_items = "PARSE: " + e; }
      }
    }
  } catch (e) { out.istisno = String(e && (e.stack || e)).slice(0, 600); }
  console.log("NATIJA_JSON " + JSON.stringify(out));
  process.exit(0);
})();
"""


def bosh_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


BASE = COOKIE = None
SERVER_XATO = None
try:
    import uvicorn                                 # noqa: E402
    import httpx                                   # noqa: E402
    _port = bosh_port()
    _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=_port, log_level="critical", lifespan="off"))
    threading.Thread(target=_srv.run, daemon=True).start()
    for _ in range(150):
        if _srv.started:
            break
        time.sleep(0.1)
    BASE = f"http://127.0.0.1:{_port}"
    _lr = httpx.post(BASE + "/login", data={"username": "TMT_admin", "password": "Parol123!"}, follow_redirects=False)
    COOKIE = "; ".join(h.split(";")[0] for h in _lr.headers.get_list("set-cookie"))
except Exception as e:
    SERVER_XATO = f"{type(e).__name__}: {e}"


def sahifa(*a):
    if SERVER_XATO:
        return {"istisno_py": SERVER_XATO}
    return node_js(NODE_SAHIFA, BASE, COOKIE, *a)


section("B0. muhit")
_jsdom_bor = subprocess.run(["node", "-e", "require('jsdom')"], capture_output=True, env=ENV).returncode == 0
check("B0a jsdom topildi (topilmasa B / C bo'limlari yiqiladi)", _jsdom_bor, NODE_PATH)
check("B0b sinov serveri ko'tarildi va login cookie bor", SERVER_XATO is None and bool(COOKIE), SERVER_XATO)


def yarat(lab, fid, miqdor, asosiy=""):
    """Buyurtmani UI yo'li bilan yaratadi; (oid, baza) yoki (None, xom)."""
    oldingi = oxirgi_buyurtma_id()
    y = sahifa("yarat", PRJ, fid, miqdor, asosiy)
    post = [p for p in (y.get("posts") or []) if p[0] == "POST" and p[1].startswith("/api/orders")]
    oid = oxirgi_buyurtma_id()
    ok = bool(post) and post[-1][2] == 200 and oid > oldingi and not y.get("istisno")
    check(f"{lab}: UI da yaratildi (POST 200)", ok, y)
    if not ok:
        return None, y
    return oid, buyurtma(oid)


def tahrir_saqla(lab, oid, oldin):
    """Tahrir oynasida HECH narsaga tegmay 'Saqlash'; keyin bazadagi narx va jami o'zgarmagani."""
    t = sahifa("tahrir", oid, "saqla")
    keyin = buyurtma(oid)
    put_ok = bool(t.get("put")) and t["put"][-1][1] == 200
    check(f"{lab}: tahrir PUT 200, istisno yo'q", put_ok and not t.get("istisno"), t)
    if not (oldin and keyin and oldin["items"] and keyin["items"]):
        check(f"{lab}: detal narxi o'zgarmadi", False, (oldin, keyin))
        check(f"{lab}: buyurtma jami o'zgarmadi", False, (oldin, keyin))
        return t, keyin
    o0, k0 = oldin["items"][0], keyin["items"][0]
    check(f"{lab}: detal qator narxi o'zgarmadi ({o0['total_price']})",
          teng(o0["total_price"], k0["total_price"]), (o0, k0, "fpPrice", t.get("fpPrice")))
    check(f"{lab}: detal unit_price x miqdor o'zgarmadi",
          teng(o0["unit_price"] * o0["quantity"], k0["unit_price"] * k0["quantity"]), (o0, k0))
    check(f"{lab}: buyurtma jami (total_amount) o'zgarmadi ({oldin['total']})",
          teng(oldin["total"], keyin["total"]), (oldin["total"], keyin["total"]))
    check(f"{lab}: TM bog'lanishi saqlandi", k0["fp"] == o0["fp"], (o0, k0))
    return t, keyin


# ═════════════════════════════════════════════════════════════════════════
section("B1. profil — nazorat: TM ko'rinadi, narxi o'zgarmagan")
fB1 = yangi_tm("TMT profil bir", "profil", 1500)
oB1, bB1 = yarat("B1", fB1, "3")
if oB1:
    check("B1: yaratishda qator narxi 4500 (3 m x 1500)", teng(bB1["items"][0]["total_price"], 4500), bB1)
    tahrir_saqla("B1", oB1, bB1)

section("B2. profil — TM narxi buyurtmadan KEYIN o'zgardi (1500 -> 2000)")
fB2 = yangi_tm("TMT profil ikki", "profil", 1500)
oB2, bB2 = yarat("B2", fB2, "3")
if oB2:
    narx_ozgart(fB2, 2000)
    tB2, _ = tahrir_saqla("B2", oB2, bB2)
    check("B2: tahrir oynasida fpPrice = saqlangan 1 metr (1500), joriy 2000 EMAS",
          teng(tB2.get("fpPrice"), 1500, 1e-6), tB2.get("fpPrice"))
    check("B2: PUT tanasida unit_price 4500 (6000 EMAS)",
          isinstance(tB2.get("put_items"), list) and tB2["put_items"] and teng(tB2["put_items"][0]["unit_price"], 4500),
          tB2.get("put_items"))

section("B3. profil — TM ro'yxatdan YASHIRIN (qoldiq 0, eski), asosiy narx bo'sh")
fB3 = yangi_tm("TMT profil uch", "profil", 1500)
oB3, bB3 = yarat("B3", fB3, "3")
if oB3:
    yashir(fB3)
    tB3, _ = tahrir_saqla("B3", oB3, bB3)
    check("B3: fpPrice saqlangan narxdan (TM ro'yxatda bo'lmasa ham)", teng(tB3.get("fpPrice"), 1500, 1e-6), tB3.get("fpPrice"))

section("B3b. profil — yashirin TM + buyurtma asosiy narxi 400 000 (formula yo'li EMAS)")
fB3b = yangi_tm("TMT profil tort", "profil", 1500)
oB3b, bB3b = yarat("B3b", fB3b, "3", "400000")
if oB3b:
    yashir(fB3b)
    tahrir_saqla("B3b", oB3b, bB3b)

section("B4. profil — kasr narx: 7 m x 1333.33, keyin TM narxi o'zgardi")
fB4 = yangi_tm("TMT profil besh", "profil", 1333.33)
oB4, bB4 = yarat("B4", fB4, "7")
if oB4:
    check("B4: yaratishda qator narxi 9333.31", teng(bB4["items"][0]["total_price"], 9333.31), bB4)
    narx_ozgart(fB4, 1500)
    tahrir_saqla("B4", oB4, bB4)

section("B5. panel — TM narxi o'zgardi")
fB5 = yangi_tm("TMT panel bir", "panel", 1200)
oB5, bB5 = yarat("B5", fB5, "4")
if oB5:
    check("B5: yaratishda qator narxi 4800 (4 m x 1200)", teng(bB5["items"][0]["total_price"], 4800), bB5)
    narx_ozgart(fB5, 3000)
    tB5, _ = tahrir_saqla("B5", oB5, bB5)
    check("B5: fpPrice = 1200", teng(tB5.get("fpPrice"), 1200, 1e-6), tB5.get("fpPrice"))

section("B6. panel — TM yashirin")
fB6 = yangi_tm("TMT panel ikki", "panel", 1200)
oB6, bB6 = yarat("B6", fB6, "4")
if oB6:
    yashir(fB6)
    tahrir_saqla("B6", oB6, bB6)

section("B7. dona — nazorat (narx .i-unitprice dan, ikkala kodda ham to'g'ri)")
fB7 = yangi_tm("TMT dona bir", "dona", 900, birlik="dona")
oB7, bB7 = yarat("B7", fB7, "5")
if oB7:
    check("B7: yaratishda qator narxi 4500 (5 x 900)", teng(bB7["items"][0]["total_price"], 4500), bB7)
    narx_ozgart(fB7, 2000)
    tahrir_saqla("B7", oB7, bB7)

section("B8. blok — TM narxi o'zgardi, keyin yashirin")
fB8 = yangi_tm("TMT blok bir", "blok", 950)
oB8, bB8 = yarat("B8", fB8, "6")
if oB8:
    check("B8: yaratishda qator narxi 5700 (6 m x 950)", teng(bB8["items"][0]["total_price"], 5700), bB8)
    narx_ozgart(fB8, 2000)
    tahrir_saqla("B8a", oB8, bB8)
    yashir(fB8)
    tahrir_saqla("B8b", oB8, bB8)

section("B9. /api/finished javob bermasa ham narx SAQLANGAN narxdan (fetch dan OLDIN o'rnatiladi)")
fB9 = yangi_tm("TMT profil olti", "profil", 1500)
oB9, bB9 = yarat("B9", fB9, "3")
if oB9:
    tB9 = sahifa("tahrir_blok", oB9)
    its = tB9.get("items") or []
    check("B9: fetch bloklanganda fpPrice = 1500", teng(tB9.get("fpPrice"), 1500, 1e-6), tB9)
    check("B9: collectItems unit_price 4500", bool(its) and teng(its[0].get("unit_price"), 4500), its)


# ═════════════════════════════════════════════════════════════════════════
section("C. nusxa (duplicate) — yangi sotuv")
if oB2:
    # B2 TM joriy narxi 2000, ro'yxatda ko'rinadi
    tC1 = sahifa("nusxa", oB2)
    its = tC1.get("items") or []
    check("C1: nusxada TM ro'yxatda — JORIY narx (2000 x 3 = 6000), yangi tanlov kabi",
          bool(its) and teng(its[0].get("unit_price"), 6000), tC1)
    check("C1: nusxada fpPrice = 2000", teng(tC1.get("fpPrice"), 2000, 1e-6), tC1.get("fpPrice"))
else:
    check("C1: nusxa (B2 buyurtmasi yo'q)", False)
    check("C1: nusxada fpPrice", False)
if oB3:
    tC2 = sahifa("nusxa", oB3)
    its = tC2.get("items") or []
    check("C2: nusxada TM yashirin — saqlangan narx (4500), 0 EMAS",
          bool(its) and teng(its[0].get("unit_price"), 4500), tC2)
else:
    check("C2: nusxa (B3 buyurtmasi yo'q)", False)
check("C3: nusxa yozuv qilmadi (buyurtmalar soni o'zgarmadi)",
      oxirgi_buyurtma_id() == max([x for x in (oB1, oB2, oB3, oB3b, oB4, oB5, oB6, oB7, oB8, oB9) if x] or [0]))


# ═════════════════════════════════════════════════════════════════════════
section("D. statik — editSelected ichidagi tartib")
ES = funksiya_matni(HTML, "editSelected") or ""
check("D1 editSelected topildi", bool(ES))
check("D2 saqlangan narx fetch dan OLDIN o'rnatiladi",
      tartibda(ES, "if (item.finished_product_id) {", "const _tmSaqlangan = tmSaqlanganBirlikNarxi(item, cat);",
               "if (_tmSaqlangan !== null) row.dataset.fpPrice = String(_tmSaqlangan);", "fetch(`/api/finished`)"))
check("D3 fetch ichida joriy narx FAQAT nusxa yoki saqlangan narx yo'q bo'lsa",
      tartibda(ES, "fetch(`/api/finished`)", "if (isDup || _tmSaqlangan === null) row.dataset.fpPrice = fp.unit_price;"))
_shartsiz = [q for q in ES.splitlines() if "row.dataset.fpPrice = fp.unit_price" in q and "if (" not in q]
check("D4 editSelected da shartsiz `row.dataset.fpPrice = fp.unit_price` qatori YO'Q", not _shartsiz, _shartsiz)
check("D5 yordamchi editSelected dan OLDIN e'lon qilingan (bir marta)",
      HTML.count("function tmSaqlanganBirlikNarxi(") == 1
      and tartibda(HTML, "function tmSaqlanganBirlikNarxi(", "async function editSelected("))

try:
    shutil.rmtree(_T, ignore_errors=True)
except Exception:
    pass
print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
