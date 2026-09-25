"""test_tm_dona_narx.py — 78-band + K69-1 (kech69): "Tayyor mahsulotdan" (TM) olingan
DONALIK detal narxi.

Nuqsonlar (kech69 da O'LCHANGAN, `work/probe78.py`, `staging` = `5830d40`):
  K69-1  `pickFinished` Donalik TM narxini "1 dona narxi" maydoniga faqat `Math.round(...)` bilan
         yozardi (`row.dataset.unitprice` ga yozilmasdi): 1 dona 1 333.33 so'mlik TM 7 dona —
         9 331 (to'g'risi 9 333.31; profil TM da narx aniq). Qatorda oldingi hisobdan qolgan aniq
         narx bo'lsa (yaxlitlangani teng) — o'sha ESKI narx olinardi.
  78     Nusxa (`editSelected('duplicate')`) da Donalik TM ESKI (saqlangan) narxda, profil / panel /
         blok esa (75-band qarori) TM ro'yxatda bo'lsa JORIY narxda — nomuvofiqlik (1 500 va 2 000).

Tuzatish (`templates/orders.html`): `pickFinished` — `up.value = formatNum(narx)` +
`row.dataset.unitprice = narx` (aniq); `editSelected` fetch ichida — `(isDup || _tmSaqlangan ===
null) && cat === 'dona'` bo'lsa "1 dona narxi" maydoni ham JORIY TM narxiga. 'edit' rejimida
saqlangan narx o'zgarmaydi (75-band).

Bo'limlar:
  A  yaratish — haqiqiy /orders (uvicorn + jsdom), sahifaning O'Z `pickFinished` + `saveOrder`,
     natija BAZADAN
  B  tahrir — YANGI sahifada `editSelected('edit')` + `updateOrder`, BAZADAN
  C  nusxa — `editSelected('duplicate')` → `collectItems()`
  D  statik — tartib (orders.html matni)

Faqat SQLite (UI yo'li). jsdom (`npm install -g jsdom@24`) topilmasa A–C YIQILADI (jim o'tmaydi).
Ishga tushirish: python3 tools/test_tm_dona_narx.py
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
_T = tempfile.mkdtemp(prefix="tm_dona_")
os.environ["DATABASE_URL"] = f"sqlite:///{_T}/tm_dona.db"
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
# Fikstura + server
db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "TMD_admin", "Parol123!", UserRole.ADMIN, "TMD", company_id=1)
prj = Project(company_id=1, client_name="TMD Mijoz", project_name="TMD loyiha", total_budget=0, total_paid=0)
peno = Inventory(company_id=1, item_name="TMD PENO", unit="blok", stock_quantity=1000, min_stock=0,
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
      if (a5) {
        // qatorda OLDINGI hisobdan qolgan aniq narx (Donalik, qo'lda kiritilgan) — keyin TM tanlanadi
        const bt = row.querySelector('.type-opt[data-value="dona"]');
        if (bt) w.selectTypeOpt(bt, "dona");
        row = w.document.querySelectorAll(".detal")[0];
        // aniq narx formula hisobidan qolgan holat (maydon yaxlitlangan, dataset aniq — Donalik formulasi
        // yoki tahrir oynasi shunday yozadi; qo'lda kiritishda `formatPriceInput` maydonni butun qiladi)
        row.querySelector(".i-unitprice").value = w.formatNum(parseFloat(a5));
        row.dataset.unitprice = a5;
        w.calculateItem(row);
        row = w.document.querySelectorAll(".detal")[0];
        out.eski_ds = row.dataset.unitprice;
      }
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
      out.maydon_tanlov = (row.querySelector(".i-unitprice") || {}).value;
      set(row.querySelector(tur === "profil" ? ".i-l" : ".i-q"), a3);
      w.calculateItem(row);
      out.maydon = (row.querySelector(".i-unitprice") || {}).value;
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
      out.maydon = row ? (row.querySelector(".i-unitprice") || {}).value : null;
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
    _lr = httpx.post(BASE + "/login", data={"username": "TMD_admin", "password": "Parol123!"}, follow_redirects=False)
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


def yarat(lab, fid, miqdor, asosiy="", eski=""):
    """Buyurtmani UI yo'li bilan yaratadi; (oid, baza) yoki (None, xom). Oxirgi natija YARAT_OXIRGI da."""
    global YARAT_OXIRGI
    oldingi = oxirgi_buyurtma_id()
    y = sahifa("yarat", PRJ, fid, miqdor, asosiy, eski)
    YARAT_OXIRGI = y
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



YARAT_OXIRGI = {}


def detal(oid, **kw):
    """Birinchi detal ustunlarini to'g'ridan yozadi (bazadagi eski / buzilgan yozuv holati)."""
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        it = o.items[0]
        for k, v in kw.items():
            setattr(it, k, v)
        s.commit()
    finally:
        s.close()


def birinchi(b):
    return (b or {}).get("items", [{}])[0] if (b or {}).get("items") else {}


# ═════════════════════════════════════════════════════════════════════════
section("A. yaratish — sahifaning O'Z pickFinished (Donalik TM)")
TM_A1 = yangi_tm("TMD dona kasr", "dona", 1333.33, "dona")
oA1, bA1 = yarat("A1", TM_A1, "7")
yA1 = YARAT_OXIRGI
iA1 = (yA1.get("items") or [{}])[0]
check("A1a collectItems: 1 dona narxi ANIQ 1333.33 (yaxlitlanmagan)", teng(iA1.get("unit_price"), 1333.33), yA1)
check("A1b bazada qator narxi 9333.31 (7 x 1333.33)", teng(birinchi(bA1).get("total_price"), 9333.31), bA1)
check("A1c bazada 1 dona narxi 1333.33", teng(birinchi(bA1).get("unit_price"), 1333.33), bA1)
check("A1d buyurtma jami 9333.31", teng((bA1 or {}).get("total"), 9333.31), bA1)
check("A1e maydonda ko'rinishi yaxlitlangan '1 333' (formatNum)", yA1.get("maydon_tanlov") == "1 333", yA1.get("maydon_tanlov"))
check("A1f TM bog'lanishi bor", birinchi(bA1).get("fp") == TM_A1, bA1)

TM_A2 = yangi_tm("TMD dona eski ds", "dona", 1333.33, "dona")
oA2, bA2 = yarat("A2", TM_A2, "7", "", "1333.4")
yA2 = YARAT_OXIRGI
check("A2a sinov sharti: TM tanlashdan OLDIN qatorda eski aniq narx 1333.4 bor edi",
      teng(yA2.get("eski_ds"), 1333.4), yA2.get("eski_ds"))
check("A2b TM tanlangach narx TM niki (1333.33), eski 1333.4 EMAS",
      teng(((yA2.get("items") or [{}])[0]).get("unit_price"), 1333.33), yA2.get("items"))
check("A2c bazada qator narxi 9333.31", teng(birinchi(bA2).get("total_price"), 9333.31), bA2)

TM_A3 = yangi_tm("TMD dona butun", "dona", 1500, "dona")
oA3, bA3 = yarat("A3", TM_A3, "3")
check("A3 nazorat: butun narx 1500 x 3 = 4500", teng(birinchi(bA3).get("total_price"), 4500)
      and teng((bA3 or {}).get("total"), 4500), bA3)

TM_A4 = yangi_tm("TMD profil kasr", "profil", 1333.33)
oA4, bA4 = yarat("A4", TM_A4, "7")
check("A4 nazorat: profil TM 1333.33 x 7 m = 9333.31", teng(birinchi(bA4).get("total_price"), 9333.31), bA4)

# ═════════════════════════════════════════════════════════════════════════
section("B. tahrir — saqlangan narx o'zgarmaydi (75-band), aniqlanmasa joriy")
if oA1:
    narx_ozgart(TM_A1, 2000)
    tB1, kB1 = tahrir_saqla("B1 (A1, TM narxi 2000 ga o'zgardi)", oA1, bA1)
    check("B1e tahrirdan keyin ham 1 dona narxi 1333.33 (2000 EMAS)", teng(birinchi(kB1).get("unit_price"), 1333.33), kB1)
else:
    check("B1 A1 buyurtmasi yo'q", False)

TM_B2 = yangi_tm("TMD dona narxsiz", "dona", 1500, "dona")
oB2, bB2 = yarat("B2", TM_B2, "3")
if oB2:
    # API NULL narxni 0 qilib beradi — 0 esa haqiqiy saqlangan narx (75-band: 0 -> 0), o'zgartirilmaydi
    detal(oB2, unit_price=None)
    tB2 = sahifa("tahrir", oB2)
    iB2 = (tB2.get("items") or [{}])[0]
    check("B2a nazorat: saqlangan narx NULL (API da 0) -> tahrirda 0 qoladi (joriy 1500 ga o'tmaydi)",
          teng(iB2.get("unit_price"), 0), tB2)
    check("B2b maydonda '0'", tB2.get("maydon") == "0", tB2.get("maydon"))
else:
    check("B2 buyurtma yo'q", False)

TM_B3 = yangi_tm("TMD dona manfiy", "dona", 1500, "dona")
oB3, bB3 = yarat("B3", TM_B3, "3")
if oB3:
    detal(oB3, unit_price=-5)
    tB3 = sahifa("tahrir", oB3)
    check("B3 saqlangan narx buzilgan (manfiy) -> joriy narx 1500",
          teng(((tB3.get("items") or [{}])[0]).get("unit_price"), 1500), tB3)
else:
    check("B3 buyurtma yo'q", False)

# ═════════════════════════════════════════════════════════════════════════
section("C. nusxa (duplicate) — Donalik TM ham JORIY narxda (profil kabi)")
TM_C1 = yangi_tm("TMD dona nusxa", "dona", 1500, "dona")
oC1, bC1 = yarat("C1", TM_C1, "3")
if oC1:
    narx_ozgart(TM_C1, 2000)
    nC1 = sahifa("nusxa", oC1)
    iC1 = (nC1.get("items") or [{}])[0]
    check("C1a nusxa: TM narxi 1500 -> 2000; Donalik nusxa narxi 2000", teng(iC1.get("unit_price"), 2000), nC1)
    check("C1b nusxa maydonida '2 000'", nC1.get("maydon") == "2 000", nC1.get("maydon"))
    check("C1c asl buyurtma o'zgarmadi (1500 x 3)", teng(birinchi(buyurtma(oC1)).get("total_price"), 4500), buyurtma(oC1))
else:
    check("C1 buyurtma yo'q", False)

TM_C2 = yangi_tm("TMD dona nusxa kasr", "dona", 1500, "dona")
oC2, bC2 = yarat("C2", TM_C2, "3")
if oC2:
    narx_ozgart(TM_C2, 1333.33)
    nC2 = sahifa("nusxa", oC2)
    check("C2 nusxa: joriy kasrli narx ANIQ 1333.33",
          teng(((nC2.get("items") or [{}])[0]).get("unit_price"), 1333.33), nC2)
else:
    check("C2 buyurtma yo'q", False)

TM_C3 = yangi_tm("TMD dona nusxa yashirin", "dona", 1500, "dona")
oC3, bC3 = yarat("C3", TM_C3, "3")
if oC3:
    narx_ozgart(TM_C3, 2000)
    yashir(TM_C3)
    nC3 = sahifa("nusxa", oC3)
    check("C3 nazorat: TM ro'yxatda YO'Q (yashirin) -> saqlangan narx 1500",
          teng(((nC3.get("items") or [{}])[0]).get("unit_price"), 1500), nC3)
else:
    check("C3 buyurtma yo'q", False)

TM_C4 = yangi_tm("TMD dona nusxa bir xil", "dona", 1500, "dona")
oC4, bC4 = yarat("C4", TM_C4, "3")
if oC4:
    nC4 = sahifa("nusxa", oC4)
    check("C4 nazorat: narx o'zgarmagan -> 1500",
          teng(((nC4.get("items") or [{}])[0]).get("unit_price"), 1500), nC4)
else:
    check("C4 buyurtma yo'q", False)

TM_C5 = yangi_tm("TMD profil nusxa", "profil", 1500)
oC5, bC5 = yarat("C5", TM_C5, "3")
if oC5:
    narx_ozgart(TM_C5, 2000)
    nC5 = sahifa("nusxa", oC5)
    check("C5 nazorat: profil nusxa joriy narx (3 m x 2000 = 6000)",
          teng(((nC5.get("items") or [{}])[0]).get("unit_price"), 6000), nC5)
else:
    check("C5 buyurtma yo'q", False)

if oA1:
    tE = sahifa("tahrir", oA1)
    check("C6 nazorat: 'edit' rejimida (nusxa emas) Donalik saqlangan narxda (1333.33, joriy 2000 EMAS)",
          teng(((tE.get("items") or [{}])[0]).get("unit_price"), 1333.33), tE)

# ═════════════════════════════════════════════════════════════════════════
section("D. statik — tartib")
PF = funksiya_matni(HTML, "pickFinished") or ""
ES = funksiya_matni(HTML, "editSelected") or ""
check("D1 pickFinished va editSelected topildi", bool(PF) and bool(ES))
check("D2 pickFinished: maydon formatNum, aniq narx row.dataset.unitprice ga",
      tartibda(PF, "const up = row.querySelector('.i-unitprice');", "const fpNarx = parseFloat(fp.unit_price) || 0;",
               "up.value = formatNum(fpNarx);", "row.dataset.unitprice = fpNarx;"))
_yaxlit = [x for x in PF.splitlines() if "up.value = Math.round(" in x]
check("D3 pickFinished da `up.value = Math.round(...)` kod qatori YO'Q", not _yaxlit, _yaxlit)
check("D4 editSelected fetch ichida: fpPrice qoidasi, so'ng Donalik maydoni, so'ng calculateItem",
      tartibda(ES, "fetch(`/api/finished`)", "if (isDup || _tmSaqlangan === null) row.dataset.fpPrice = fp.unit_price;",
               "if ((isDup || _tmSaqlangan === null) && cat === 'dona') {", "upTm.value = formatNum(fpNarxTm);",
               "row.dataset.unitprice = fpNarxTm;", "calculateItem(row);", "checkFpLimit(row);"))

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
