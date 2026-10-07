"""test_ochirilgan_tur.py — 77-band (kech68): korxonada O'CHIRILGAN detal turi (eskirgan `blok`,
ixtiyoriy `loy_sotish`) bilan saqlangan MAVJUD detal buyurtma formasida jimgina '' turga
aylanmasligi va server bo'sh turni rad etishi.

Nuqson (kech67 da O'LCHANGAN, `work/probe67_blok.py`): `orders.html` shabloni `.i-type`
variantini va `.type-opt` tugmasini faqat korxonada YOQILGAN turlar uchun chizadi (`main.cat_on`;
`blok` ESKIRGAN — sozlanmagan korxonada standart O'CHIQ). Blok detalli buyurtmani ochib hech
narsaga tegmay "Saqlash" — `typeEl.value = 'blok'` jimgina '' bo'lardi: kategoriya '', narx
300 000 -> 0, `length` 0.5 blok -> 40, izoh (blok narxi) yo'qoldi, penoplast 0.5 blok SOXTA
qaytdi. Server `category: ''` ni qabul qilardi.

Tuzatish: `turVariantiniTaminla(row, cat)` — shu QATORGA variant va tugma (tahrir / nusxa,
tayyor mahsulot `pickFinished`, qoralama tiklash); `addItem` o'chirilgan turni yangi qatorga
o'tkazmaydi (`turVariantiBor`); server (`crud._detal_turi_tekshir` — `update_order_full`,
`create_order`, `POST /api/orders` marshruti) bo'sh turni 400 bilan rad etadi.

Bo'limlar:
  A  yordamchilar — HAQIQIY /orders sahifasida (uvicorn + jsdom), ikkala ixtiyoriy tur O'CHIQ
  B  oqim — haqiqiy /orders: yaratish sahifaning O'Z funksiyalari bilan (tur YOQIQ paytda),
     keyin tur o'chiriladi, tahrir YANGI sahifada `editSelected('edit')` + `updateOrder`
     (tasdiq -> true), natija BAZADAN o'qiladi; nusxa, tayyor mahsulot, qoralama, eski noma'lum tur
  C  server to'sig'i — HTTP va `crud` to'g'ridan
  D  statik — chaqiruv tartibi (orders.html, crud, main)

Faqat SQLite: UI yo'li va sxema tekshiruvi — bazaga bog'liq yaxlitlash / sig'im yo'q (narxlar
butun so'm). jsdom (`npm install -g jsdom@24`) topilmasa A / B bo'limlari YIQILADI (jim o'tmaydi).
Ishga tushirish: python3 tools/test_ochirilgan_tur.py
"""
import os
import sys
import io
import json
import time
import socket
import inspect
import tempfile
import threading
import subprocess
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
_T = tempfile.mkdtemp(prefix="ochirilgan_tur_")
os.environ["DATABASE_URL"] = f"sqlite:///{_T}/ochirilgan_tur.db"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas                                 # noqa: E402

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
    if not src:
        return False
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
    """`function nom(` (yoki `async function nom(`) dan qavs muvozanati bo'yicha tana oxirigacha."""
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


def manba(obj, nom):
    f = getattr(obj, nom, None)
    try:
        return inspect.getsource(f) if f is not None else ""
    except Exception:
        return ""


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
# Fikstura
db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "OTT_admin", "Parol123!", UserRole.ADMIN, "OTT", company_id=1)
prj = Project(company_id=1, client_name="OTT Mijoz", project_name="OTT loyiha", total_budget=0, total_paid=0)
peno = Inventory(company_id=1, item_name="OTT PENO", unit="blok", stock_quantity=1000, min_stock=0,
                 is_penoplast=True, volume_per_unit=1, price_per_unit=500000)
db.add_all([prj, peno])
db.commit()
PRJ, PENO = prj.id, peno.id
db.close()

HAMMA = ",".join(k for k, _ in getattr(main, "IXTIYORIY_KATEGORIYALAR", []))


def sozla(qiymat):
    """Korxonaning ixtiyoriy turlar sozlamasi (`enabled_categories`) + kesh tozalash."""
    s = SessionLocal()
    try:
        crud.set_setting(s, "enabled_categories", qiymat, company_id=1)
    finally:
        s.close()
    getattr(main, "_kategoriya_cache", {}).clear()


def yangi_tm(nomi, kategoriya, narx):
    s = SessionLocal()
    try:
        f = FinishedProduct(company_id=1, name=nomi, category=kategoriya, is_coated=False, width=10, thickness=10,
                            quantity=100, produced_quantity=100, unit="metr", unit_price=narx,
                            cost_price=100 * 1000, unit_cost_stable=1000, source=StockSource.PRODUCED,
                            penoplast_id=PENO, unit_volume_m3=0.005, production_status=ProductionStatus.READY)
        s.add(f)
        s.commit()
        return f.id
    finally:
        s.close()


def tm_qoldiq(fid):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid)
        return float(f.quantity) if f else None
    finally:
        s.close()


def buyurtma(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if o is None:
            return None
        return {
            "items": sorted([(i.name, i.category, round(float(i.unit_price or 0), 4), round(float(i.total_price or 0), 4),
                              round(float(i.quantity or 0), 6), round(float(i.length or 0), 6), i.notes or "",
                              i.finished_product_id) for i in o.items], key=lambda x: str(x[0])),
            "total": round(float(o.total_amount or 0), 4),
            "agreed": round(float(o.agreed_amount or 0), 4),
        }
    finally:
        s.close()


def peno_qoldiq():
    s = SessionLocal()
    try:
        return float(s.get(Inventory, PENO).stock_quantity)
    finally:
        s.close()


def buyurtma_idlari():
    s = SessionLocal()
    try:
        return sorted(o.id for o in s.query(Order).all())
    finally:
        s.close()


def yangi_buyurtma_id(oldin):
    y = [i for i in buyurtma_idlari() if i not in oldin]
    return y[0] if len(y) == 1 else None


NODE_SAHIFA = r"""
const { JSDOM, VirtualConsole, ResourceLoader } = require("jsdom");
const [base, cookie, rejim, a1, a2, a3, a4] = process.argv.slice(2);
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
    out.html_blok = html.includes('<option value="blok">');
    out.html_loy = html.includes('<option value="loy_sotish">');
    const vc = new VirtualConsole();
    vc.on("jsdomError", e => { const m = String(e && (e.message || e)).slice(0, 200); if (!/Not implemented|parse CSS/.test(m)) out.xato.push(m); });
    let pending = 0;
    const posts = [];
    const dom = new JSDOM(html, {
      url: base + "/orders", runScripts: "dangerously", pretendToBeVisual: true, resources: new R(), virtualConsole: vc,
      beforeParse(w) {
        w.fetch = async (u, o) => {
          const url = new URL(String(u), base + "/orders").href;
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
    const soddala = its => (its || []).map(i => ({ name: i.name, category: i.category, unit_price: i.unit_price, quantity: i.quantity,
                                                   length: i.length, finished_product_id: i.finished_product_id, notes: i.notes || null }));
    const qatorlar = () => Array.from(w.document.querySelectorAll(".detal")).map(r => ({
      nom: r.querySelector(".i-name").value,
      tur: r.querySelector(".i-type").value,
      faol: Array.from(r.querySelectorAll(".type-opt.active")).map(o => o.dataset.value),
      variant: Array.from(r.querySelector(".i-type").options).map(o => o.value),
      tugma: Array.from(r.querySelectorAll(".type-opt")).map(o => o.dataset.value),
    }));
    const sinab = fn => { try { return fn(); } catch (e) { return "ISTISNO:" + String(e).slice(0, 120); } };
    const fnn = nm => (typeof w[nm] === "function") ? w[nm] : null;
    const tasdiqYoz = () => {
      const tasdiq = [];
      w.showConfirmModal = async (m) => { tasdiq.push(String(m).slice(0, 200)); return true; };
      w.customConfirm = async (...m) => { tasdiq.push(m.join(" | ").slice(0, 200)); return true; };
      w.showMsg = (m) => { tasdiq.push("MSG " + String(m).slice(0, 300)); };
      return tasdiq;
    };

    if (rejim === "birlik") {
      const T = fnn("turVariantiniTaminla"), B = fnn("turVariantiBor");
      out.fn = [!!T, !!B];
      w.eval("addItem()");
      const row = w.document.querySelectorAll(".detal")[0];
      const sel = () => row.querySelector(".i-type");
      const opts = () => Array.from(sel().options).map(o => o.value);
      const tugmalar = () => Array.from(row.querySelectorAll(".type-opt")).map(o => o.dataset.value);
      const tg = row.querySelector(".type-toggle");
      const seplar = Array.from(tg.children).filter(c => c.classList.contains("tur-sep"));
      out.boshlang = { opts: opts(), tugma: tugmalar(), sep: seplar.length };
      out.bor = sinab(() => B ? [B(row, "blok"), B(row, "profil"), B(row, ""), B(null, "profil"), B(row, null)] : "YOQ");
      out.t1 = sinab(() => T ? T(row, "blok") : "YOQ");
      out.t1_opts = opts(); out.t1_tugma = tugmalar();
      out.t2 = sinab(() => T ? T(row, "blok") : "YOQ");
      out.t2_opts = opts(); out.t2_tugma = tugmalar();
      out.bor_keyin = sinab(() => B ? B(row, "blok") : "YOQ");
      sel().value = "blok"; out.qiymat = sel().value;
      const bt = row.querySelector('.type-opt[data-value="blok"]');
      out.orni_blok = bt ? (bt.previousElementSibling === seplar[0]) : "tugma yoq";
      out.tugma_matn = bt ? bt.textContent : null;
      out.tugma_sarlavha = bt ? bt.title : null;
      out.nomalum = sinab(() => T ? [T(row, "gips"), T(row, ""), T(row, null), T(row, "toString"), T(row, "__proto__"), T(null, "blok")] : "YOQ");
      out.nomalum_opts = opts();
      out.mrp = sinab(() => T ? T(row, "mrp_product") : "YOQ");
      out.mrp_opts = opts();
      row.querySelector('.type-opt[data-value="profil"]').click();
      out.bos_profil = [sel().value, Array.from(row.querySelectorAll(".type-opt.active")).map(o => o.dataset.value)];
      if (bt) bt.click();
      out.bos_blok = [sel().value, Array.from(row.querySelectorAll(".type-opt.active")).map(o => o.dataset.value),
                      row.querySelector(".i-blokprice-wrap") ? row.querySelector(".i-blokprice-wrap").style.display : "yoq"];
      out.loy = sinab(() => T ? T(row, "loy_sotish") : "YOQ");
      const lt = row.querySelector('.type-opt[data-value="loy_sotish"]');
      out.orni_loy = lt ? (lt.previousElementSibling === seplar[1]) : "tugma yoq";
      out.loy_opts = opts();
      out.loy_tugma = tugmalar();
      // yangi qator — oldingi qator (blok) turi o'tmasligi kerak
      out.oldingi_tur = sel().value;
      w.eval("addItem()");
      const yangi = w.document.querySelectorAll(".detal")[0];
      out.yangi = { tur: yangi.querySelector(".i-type").value,
                    opts: Array.from(yangi.querySelector(".i-type").options).map(o => o.value),
                    tugma: Array.from(yangi.querySelectorAll(".type-opt")).map(o => o.dataset.value),
                    faol: Array.from(yangi.querySelectorAll(".type-opt.active")).map(o => o.dataset.value) };
      out.eski_qator = sel().value;
    } else if (rejim === "yarat") {
      // a1 = loyiha, a2 = qatorlar JSON, a3 = asosiy narx
      set(w.document.getElementById("project_id"), a1);
      set(w.document.getElementById("deadline_input"), "2026-12-30");
      set(w.document.getElementById("base_price"), a3 || "");
      const spec = JSON.parse(a2);
      spec.forEach(() => w.eval("addItem()"));
      const rows = Array.from(w.document.querySelectorAll(".detal"));
      spec.forEach((s, i) => {
        const row = rows[rows.length - 1 - i];
        const btn = row.querySelector('.type-opt[data-value="' + s.tur + '"]');
        if (!btn) throw new Error("tugma yoq: " + s.tur);
        w.selectTypeOpt(btn, s.tur);
        set(row.querySelector(".i-name"), s.nom);
        set(row.querySelector(".i-peno"), String(s.peno));
        if (s.tur === "blok") {
          set(row.querySelector(".i-blokprice"), s.blokprice);
          set(row.querySelector(".i-l"), s.l);
          set(row.querySelector(".i-q"), s.q);
        } else {
          set(row.querySelector(".i-h"), s.h);
          set(row.querySelector(".i-w"), s.w);
          set(row.querySelector(".i-l"), s.l);
        }
        w.calculateItem(row);
      });
      out.qatorlar = qatorlar();
      out.items = soddala(w.eval("collectItems()"));
      const tasdiq = tasdiqYoz();
      await w.eval("saveOrder(false)");
      await tinch();
      out.tasdiq = tasdiq;
      out.posts = posts.map(p => [p[0], p[1], p[2]]);
    } else if (rejim === "tm") {
      // a1 = loyiha, a2 = TM id, a3 = miqdor
      set(w.document.getElementById("project_id"), a1);
      set(w.document.getElementById("deadline_input"), "2026-12-30");
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
      out.qatorlar = qatorlar();
      const tur = row.querySelector(".i-type").value;
      set(row.querySelector(tur === "profil" ? ".i-l" : ".i-q"), a3);
      w.calculateItem(row);
      out.items = soddala(w.eval("collectItems()"));
      const tasdiq = tasdiqYoz();
      await w.eval("saveOrder(false)");
      await tinch();
      out.tasdiq = tasdiq;
      out.posts = posts.map(p => [p[0], p[1], p[2]]);
    } else if (rejim === "qoralama") {
      // a1 = qoralama JSON
      await w.restoreDraftLS(JSON.parse(a1));
      await tinch();
      out.qatorlar = qatorlar();
      out.items = soddala(w.eval("collectItems()"));
      w.eval("addItem()");
      out.qatorlar_keyin = qatorlar();
      out.posts = posts.map(p => [p[0], p[1], p[2]]);
    } else if (rejim === "tahrir" || rejim === "nusxa") {
      // a1 = buyurtma id, a2 = "saqla" | "yangi" | ""
      w.eval("selectedOrderId = " + Number(a1));
      await w.eval(rejim === "nusxa" ? "editSelected('duplicate')" : "editSelected('edit')");
      await tinch(); await kut(400); await tinch();
      out.qatorlar = qatorlar();
      out.items = soddala(w.eval("collectItems()"));
      if (rejim === "tahrir" && a2 === "yangi") {
        w.eval("addItem()");
        out.qatorlar_keyin = qatorlar();
      }
      if (rejim === "tahrir" && a2 === "saqla") {
        const tasdiq = tasdiqYoz();
        await w.eval("updateOrder(" + Number(a1) + ")");
        await tinch();
        out.tasdiq = tasdiq;
        const put = posts.filter(p => p[0] === "PUT");
        out.put = put.map(p => [p[1], p[2]]);
        try { out.put_items = put.length ? soddala(JSON.parse(put[put.length - 1][3]).items) : null; } catch (e) { out.put_items = "PARSE: " + e; }
      }
      out.posts = posts.map(p => [p[0], p[1], p[2]]);
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
    _lr = httpx.post(BASE + "/login", data={"username": "OTT_admin", "password": "Parol123!"}, follow_redirects=False)
    COOKIE = "; ".join(h.split(";")[0] for h in _lr.headers.get_list("set-cookie"))
except Exception as e:
    SERVER_XATO = f"{type(e).__name__}: {e}"


def sahifa(*a):
    if SERVER_XATO:
        return {"istisno_py": SERVER_XATO}
    return node_js(NODE_SAHIFA, BASE, COOKIE, *a)


def api(metod, yol, tana=None):
    """HTTP (joriy sessiya). Istisno -> (599, matn) — test qulamaydi."""
    try:
        r = httpx.request(metod, BASE + yol, json=tana, headers={"cookie": COOKIE}, timeout=60)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text
    except Exception as e:
        return 599, f"{type(e).__name__}: {e}"


def xabar(javob):
    """Server javobidan xabar matni (detail satr yoki detail.message)."""
    if isinstance(javob, dict):
        d = javob.get("detail", javob)
        if isinstance(d, dict):
            return str(d.get("message", d))
        return str(d)
    return str(javob)


section("B0. muhit")
_jsdom_bor = subprocess.run(["node", "-e", "require('jsdom')"], capture_output=True, env=ENV).returncode == 0
check("B0a jsdom mavjud (NODE_PATH)", _jsdom_bor, NODE_PATH)
check("B0b lokal server ishga tushdi va login cookie olindi", SERVER_XATO is None and bool(COOKIE), SERVER_XATO)


# ═════════════════════════════════════════════════════════════════════════
section("A. yordamchilar — HAQIQIY /orders, blok va loy_sotish O'CHIQ")
sozla("")
rA = sahifa("birlik")
check("A0 sahifa ishladi (istisno yo'q)", "istisno" not in rA and "istisno_py" not in rA, rA.get("istisno") or rA.get("istisno_py") or rA.get("stdout"))
check("A1 fikstura sezgirligi: shablonda blok / loy_sotish varianti CHIZILMAGAN",
      rA.get("html_blok") is False and rA.get("html_loy") is False
      and "blok" not in (rA.get("boshlang") or {}).get("opts", ["blok"])
      and "loy_sotish" not in (rA.get("boshlang") or {}).get("tugma", ["loy_sotish"]), rA.get("boshlang"))
check("A2 turVariantiBor / turVariantiniTaminla sahifada bor", rA.get("fn") == [True, True], rA.get("fn"))
check("A3 turVariantiBor: blok yo'q, profil bor, '' / null qator / null tur -> false",
      rA.get("bor") == [False, True, False, False, False], rA.get("bor"))
check("A4 turVariantiniTaminla(row, 'blok') -> true; variant va tugma qo'shildi",
      rA.get("t1") is True and (rA.get("t1_opts") or []).count("blok") == 1
      and (rA.get("t1_tugma") or []).count("blok") == 1, [rA.get("t1"), rA.get("t1_opts"), rA.get("t1_tugma")])
check("A5 ikkinchi chaqiruv takror QO'SHMAYDI (variant 1, tugma 1)",
      rA.get("t2") is True and (rA.get("t2_opts") or []).count("blok") == 1
      and (rA.get("t2_tugma") or []).count("blok") == 1, [rA.get("t2"), rA.get("t2_opts"), rA.get("t2_tugma")])
check("A6 qo'shilgandan keyin turVariantiBor(row, 'blok') -> true", rA.get("bor_keyin") is True, rA.get("bor_keyin"))
check("A7 `.i-type` qiymati 'blok' qoladi ('' EMAS)", rA.get("qiymat") == "blok", rA.get("qiymat"))
check("A8 blok tugmasi shablondagi o'rnida — 1-ajratgichdan keyin", rA.get("orni_blok") is True, rA.get("orni_blok"))
check("A9 tugma matni va izohi (o'chirilgan tur — faqat shu detal)",
      rA.get("tugma_matn") == "🧊 Blok (butun narxda)" and "o'chirilgan" in str(rA.get("tugma_sarlavha")),
      [rA.get("tugma_matn"), rA.get("tugma_sarlavha")])
check("A10 noma'lum / bo'sh / prototip kalit / null qator -> false, variant QO'SHILMAYDI",
      rA.get("nomalum") == [False, False, False, False, False, False]
      and not any(v in (rA.get("nomalum_opts") or []) for v in ("gips", "", "toString", "__proto__")),
      [rA.get("nomalum"), rA.get("nomalum_opts")])
check("A11 har doim bor tur (mrp_product) -> true, takror variant yo'q",
      rA.get("mrp") is True and (rA.get("mrp_opts") or []).count("mrp_product") == 1, [rA.get("mrp"), rA.get("mrp_opts")])
check("A12 profil tugmasi bosilsa -> profil, faqat profil faol",
      rA.get("bos_profil") == ["profil", ["profil"]], rA.get("bos_profil"))
check("A13 qo'shilgan blok tugmasi BOSILADI -> blok, faqat blok faol, blok maydonlari ko'rinadi",
      (rA.get("bos_blok") or [None])[0] == "blok" and (rA.get("bos_blok") or [None, None])[1] == ["blok"]
      and (rA.get("bos_blok") or [None, None, "none"])[2] != "none", rA.get("bos_blok"))
check("A14 loy_sotish ham qo'shiladi (variant 1, tugma 2-ajratgichdan keyin)",
      rA.get("loy") is True and (rA.get("loy_opts") or []).count("loy_sotish") == 1 and rA.get("orni_loy") is True,
      [rA.get("loy"), rA.get("loy_opts"), rA.get("orni_loy")])
check("A15 yangi qator: oldingi (blok) qator turi O'TMAYDI — profil, faol profil",
      rA.get("oldingi_tur") == "blok" and (rA.get("yangi") or {}).get("tur") == "profil"
      and (rA.get("yangi") or {}).get("faol") == ["profil"], [rA.get("oldingi_tur"), rA.get("yangi")])
check("A16 yangi qatorda blok / loy varianti ham, tugmasi ham YO'Q (faqat mavjud detal qatori)",
      "blok" not in (rA.get("yangi") or {}).get("opts", ["blok"]) and "blok" not in (rA.get("yangi") or {}).get("tugma", ["blok"])
      and "loy_sotish" not in (rA.get("yangi") or {}).get("opts", ["loy_sotish"]), rA.get("yangi"))
check("A17 eski (blok) qator o'zgarmadi", rA.get("eski_qator") == "blok", rA.get("eski_qator"))
check("A18 jsdom xatosi yo'q", not rA.get("xato"), rA.get("xato"))


# ═════════════════════════════════════════════════════════════════════════
section("B. oqim — yaratish tur YOQIQ, tahrir tur O'CHIQ (bazadan)")
sozla(HAMMA)
BLOK = {"tur": "blok", "nom": "OTT blok detal", "peno": PENO, "blokprice": "600000", "l": "40", "q": "20"}
_old = buyurtma_idlari()
p0 = peno_qoldiq()
r = sahifa("yarat", PRJ, json.dumps([BLOK]), "")
O1 = yangi_buyurtma_id(_old)
b1 = buyurtma(O1) if O1 else None
check("B0a blok buyurtma sahifa orqali yaratildi (POST 200, 1 ta yangi)",
      O1 is not None and [p[:3] for p in (r.get("posts") or []) if p[0] == "POST"] == [["POST", "/api/orders", 200]],
      [r.get("posts"), r.get("istisno"), r.get("tasdiq")])
_it1 = (b1 or {}).get("items") or [()]
check("B0b saqlangan: blok, 1 metr 15 000, jami 300 000, uzunlik 0.5 blok, izohda blok narxi",
      len(_it1) == 1 and _it1[0][1] == "blok" and teng(_it1[0][2], 15000) and teng(_it1[0][3], 300000)
      and teng(_it1[0][5], 0.5) and "blok_narxi=600000" in str(_it1[0][6]) and teng((b1 or {}).get("total"), 300000), b1)
check("B0c penoplast 0.5 blok yechildi", teng(peno_qoldiq(), p0 - 0.5, 1e-6), [p0, peno_qoldiq()])

PROFIL = {"tur": "profil", "nom": "OTT profil detal", "peno": PENO, "h": "10", "w": "10", "l": "3"}
BLOK2 = {"tur": "blok", "nom": "OTT blok 2", "peno": PENO, "blokprice": "400000", "l": "20", "q": "10"}
_old = buyurtma_idlari()
r = sahifa("yarat", PRJ, json.dumps([BLOK2, PROFIL]), "500000")
O2 = yangi_buyurtma_id(_old)
b2 = buyurtma(O2) if O2 else None
check("B0d aralash buyurtma (blok + profil) yaratildi",
      O2 is not None and len((b2 or {}).get("items") or []) == 2
      and sorted(i[1] for i in (b2 or {}).get("items") or []) == ["blok", "profil"]
      and all(i[3] > 0 for i in (b2 or {}).get("items") or []), [b2, r.get("posts"), r.get("istisno")])

# loy_sotish va eski noma'lum tur — API bilan (sahifada loy sotish retseptsiz saqlanmaydi; eski tur shablonda yo'q)
_s, _j = api("POST", "/api/orders?confirm_shortage=true", {"project_id": PRJ, "items": [
    {"name": "OTT loy sotish", "category": "loy_sotish", "quantity": 3, "unit_price": 20000, "is_coated": False}]})
O3 = _j.get("id") if isinstance(_j, dict) else None
_s4, _j4 = api("POST", "/api/orders?confirm_shortage=true", {"project_id": PRJ, "items": [
    {"name": "OTT eski gips", "category": "gips", "quantity": 5, "unit_price": 1000, "length": 5,
     "is_coated": False, "penoplast_id": PENO}]})
O4 = _j4.get("id") if isinstance(_j4, dict) else None
check("B0e loy_sotish (60 000) va eski 'gips' (5 000) buyurtmalari API bilan yaratildi",
      _s == 200 and _s4 == 200 and teng((buyurtma(O3) or {}).get("total"), 60000) and teng((buyurtma(O4) or {}).get("total"), 5000),
      [_s, _j, _s4, _j4])

# B1 — nazorat: tur YOQIQ holatda tahrir -> saqlash AYNAN
oldin = buyurtma(O1)
p0 = peno_qoldiq()
r = sahifa("tahrir", O1, "saqla")
check("B1a (nazorat, blok YOQIQ) PUT 200", (r.get("put") or [[None, None]])[-1][1] == 200, [r.get("put"), r.get("tasdiq"), r.get("istisno")])
check("B1b (nazorat) buyurtma va penoplast AYNAN", buyurtma(O1) == oldin and teng(peno_qoldiq(), p0, 1e-9), [oldin, buyurtma(O1)])

# ── tur O'CHIQ (sozlangan korxona: faqat loy_sotish yoqiq — blok standart kabi o'chiq) ──
sozla("loy_sotish")
oldin = buyurtma(O1)
p0 = peno_qoldiq()
r = sahifa("tahrir", O1, "saqla")
q = (r.get("qatorlar") or [{}])
check("B2a fikstura sezgirligi: sahifada blok varianti CHIZILMAGAN", r.get("html_blok") is False, r.get("html_blok"))
check("B2b tahrir oynasi: detal turi 'blok', faol tugma blok", [x.get("tur") for x in q] == ["blok"] and q[0].get("faol") == ["blok"], q)
check("B2c collectItems: blok, 1 metr 15 000, 20 metr, 0.5 blok",
      [(i.get("category"), i.get("unit_price"), i.get("quantity"), i.get("length")) for i in r.get("items") or []]
      == [("blok", 15000, 20, 0.5)], r.get("items"))
check("B2d PUT 200 va tanada kategoriya 'blok' ('' EMAS)",
      (r.get("put") or [[None, None]])[-1][1] == 200 and [i.get("category") for i in (r.get("put_items") or [])] == ["blok"],
      [r.get("put"), r.get("put_items"), r.get("tasdiq")])
check("B2e bazada AYNAN: kategoriya, narx, jami, uzunlik, izoh, buyurtma jami", buyurtma(O1) == oldin, [oldin, buyurtma(O1)])
check("B2f penoplast SOXTA qaytmadi (AYNAN)", teng(peno_qoldiq(), p0, 1e-9), [p0, peno_qoldiq()])
check("B2g jsdom xatosi yo'q", not r.get("xato"), r.get("xato"))

oldin = buyurtma(O2)
p0 = peno_qoldiq()
r = sahifa("tahrir", O2, "saqla")
check("B3a aralash buyurtma tahriri: turlar blok + profil",
      sorted(x.get("tur") for x in r.get("qatorlar") or []) == ["blok", "profil"], r.get("qatorlar"))
check("B3b aralash: PUT 200, bazada ikkala detal AYNAN, penoplast AYNAN",
      (r.get("put") or [[None, None]])[-1][1] == 200 and buyurtma(O2) == oldin and teng(peno_qoldiq(), p0, 1e-9),
      [r.get("put"), oldin, buyurtma(O2), p0, peno_qoldiq()])
_prof = [x for x in r.get("qatorlar") or [] if x.get("tur") == "profil"]
check("B3c profil qatorida blok varianti YO'Q (faqat blok detal qatoriga qo'shilgan)",
      len(_prof) == 1 and "blok" not in _prof[0].get("variant", ["blok"]) and "blok" not in _prof[0].get("tugma", ["blok"]), _prof)

r = sahifa("tahrir", O1, "yangi")
qk = r.get("qatorlar_keyin") or []
check("B4a tahrirda yangi detal qo'shilsa — profil (o'chirilgan blok turi o'tmaydi)",
      len(qk) == 2 and qk[0].get("tur") == "profil" and qk[0].get("faol") == ["profil"], qk)
check("B4b yangi qatorda blok varianti yo'q, mavjud blok qatori blok qoladi",
      len(qk) == 2 and "blok" not in qk[0].get("variant", ["blok"]) and qk[1].get("tur") == "blok", qk)

_old = buyurtma_idlari()
r = sahifa("nusxa", O1)
check("B5a nusxa: detal turi blok", [x.get("tur") for x in r.get("qatorlar") or []] == ["blok"], r.get("qatorlar"))
check("B5b nusxa collectItems: blok, 15 000, 20 metr, 0.5 blok, izohda blok narxi",
      [(i.get("category"), i.get("unit_price"), i.get("quantity"), i.get("length")) for i in r.get("items") or []]
      == [("blok", 15000, 20, 0.5)] and "blok_narxi=600000" in str((r.get("items") or [{}])[0].get("notes")), r.get("items"))
check("B5c nusxa hech narsa yozmadi", not r.get("posts") and buyurtma_idlari() == _old, r.get("posts"))

TMB = yangi_tm("OTT tayyor blok", "blok", 1500)
_old = buyurtma_idlari()
r = sahifa("tm", PRJ, TMB, "5")
O5 = yangi_buyurtma_id(_old)
b5 = buyurtma(O5) if O5 else None
check("B6a blok TM tanlandi (blok O'CHIQ): qator turi blok",
      [x.get("tur") for x in r.get("qatorlar") or []] == ["blok"], r.get("qatorlar"))
check("B6b TM collectItems: blok, 1 metr 1 500, 5 metr, TM bog'langan",
      [(i.get("category"), i.get("unit_price"), i.get("quantity"), i.get("finished_product_id")) for i in r.get("items") or []]
      == [("blok", 1500, 5, TMB)], r.get("items"))
check("B6c bazada: blok, 1 500, jami 7 500, TM qoldig'i 95",
      O5 is not None and [(i[1], i[2], i[3], i[7]) for i in (b5 or {}).get("items") or []] == [("blok", 1500, 7500, TMB)]
      and teng((b5 or {}).get("total"), 7500) and teng(tm_qoldiq(TMB), 95, 1e-9),
      [b5, tm_qoldiq(TMB), r.get("posts"), r.get("tasdiq")])

QORALAMA = {"ts": 1, "project_id": str(PRJ), "deadline_input": "2026-12-30", "rows": [
    {"i-type": "blok", "i-name": "OTT qoralama blok", "i-peno": str(PENO), "i-blokprice": "600000",
     "i-l": "40", "i-q": "20", "i-c": "false"}]}
r = sahifa("qoralama", json.dumps(QORALAMA))
check("B7a qoralama tiklandi: detal turi blok, faol blok",
      [x.get("tur") for x in r.get("qatorlar") or []] == ["blok"] and (r.get("qatorlar") or [{}])[0].get("faol") == ["blok"],
      [r.get("qatorlar"), r.get("istisno")])
check("B7b qoralama collectItems: blok, 15 000, 20 metr, 0.5 blok",
      [(i.get("category"), i.get("unit_price"), i.get("quantity"), i.get("length")) for i in r.get("items") or []]
      == [("blok", 15000, 20, 0.5)], r.get("items"))
qk = r.get("qatorlar_keyin") or []
check("B7c qoralamadan keyin yangi detal — profil",
      len(qk) == 2 and qk[0].get("tur") == "profil" and qk[1].get("tur") == "blok", qk)
check("B7d qoralama hech narsa yozmadi", not r.get("posts"), r.get("posts"))

# ── HAMMA ixtiyoriy tur O'CHIQ ──
sozla("")
oldin = buyurtma(O3)
r = sahifa("tahrir", O3, "saqla")
check("B8a loy_sotish O'CHIQ: sahifada variant yo'q (sezgirlik), tahrirda tur loy_sotish",
      r.get("html_loy") is False and [x.get("tur") for x in r.get("qatorlar") or []] == ["loy_sotish"], r.get("qatorlar"))
check("B8b loy_sotish: PUT 200, bazada AYNAN (loy_sotish, 20 000, jami 60 000)",
      (r.get("put") or [[None, None]])[-1][1] == 200 and buyurtma(O3) == oldin, [r.get("put"), oldin, buyurtma(O3), r.get("tasdiq")])

oldin = buyurtma(O4)
p0 = peno_qoldiq()
r = sahifa("tahrir", O4, "saqla")
check("B9a eski noma'lum tur ('gips'): forma uni tanimaydi — PUT 400 (jimgina saqlanmaydi)",
      (r.get("put") or [[None, None]])[-1][1] == 400, [r.get("put"), r.get("put_items")])
check("B9b foydalanuvchiga aniq xabar (detal turi ko'rsatilmagan)",
      any("turi ko'rsatilmagan" in str(t) for t in r.get("tasdiq") or []), r.get("tasdiq"))
check("B9c bazada AYNAN (gips, 1 000, jami 5 000), penoplast AYNAN",
      buyurtma(O4) == oldin and teng(peno_qoldiq(), p0, 1e-9), [oldin, buyurtma(O4), p0, peno_qoldiq()])


# ═════════════════════════════════════════════════════════════════════════
section("C. server to'sig'i — bo'sh detal turi")
DT = getattr(crud, "_detal_turi_tekshir", None)
check("C0 crud._detal_turi_tekshir bor", callable(DT))


def dt_natija(items):
    if not callable(DT):
        return "YOQ"
    try:
        DT(items)
        return "OK"
    except ValueError as e:
        return "RAD:" + str(e)
    except Exception as e:
        return "ISTISNO:" + f"{type(e).__name__}: {e}"


_it = schemas.OrderItemCreate
C_HOLAT = [
    ("C1 None (maydon berilmagan) — rad EMAS (tor to'siq)", [_it(name="aa", quantity=1)], "OK"),
    ("C2 'profil' — rad emas", [_it(name="aa", category="profil", quantity=1)], "OK"),
    ("C3 '' — rad", [_it(name="aa", category="", quantity=1)], "RAD"),
    ("C4 '   ' (faqat bo'shliq) — rad", [_it(name="aa", category="   ", quantity=1)], "RAD"),
    ("C5 lug'at shakli '' — rad", [{"name": "aa", "category": ""}], "RAD"),
    ("C6 lug'at shakli None — rad emas", [{"name": "aa", "category": None}], "OK"),
    ("C7 bo'sh ro'yxat / None — rad emas", [], "OK"),
    ("C8 eski noma'lum 'gips' — rad EMAS (faqat bo'sh tur)", [_it(name="aa", category="gips", quantity=1)], "OK"),
]
for lab, items, kut in C_HOLAT:
    v = dt_natija(items)
    check(lab, str(v).startswith(kut), v)
v = dt_natija(None)
check("C9 items None — rad emas", v == "OK", v)
v = dt_natija([_it(name="Birinchi", category="panel", quantity=1), _it(name="Ikkinchi detal", category="", quantity=1)])
check("C10 xabarda qator raqami va detal nomi", "2-detal" in str(v) and "Ikkinchi detal" in str(v), v)

# HTTP — PUT
oldin = buyurtma(O1)
p0 = peno_qoldiq()
_s, _j = api("PUT", f"/api/orders/{O1}", {"project_id": PRJ, "items": [
    {"name": "OTT blok detal", "category": "", "quantity": 20, "unit_price": 15000, "length": 0.5,
     "is_coated": False, "penoplast_id": PENO}]})
check("C11 PUT bo'sh tur -> 400, xabar aniq", _s == 400 and "turi ko'rsatilmagan" in xabar(_j), [_s, _j])
check("C12 PUT rad: bazada va omborda AYNAN", buyurtma(O1) == oldin and teng(peno_qoldiq(), p0, 1e-9), [oldin, buyurtma(O1)])
_s, _j = api("PUT", f"/api/orders/{O1}", {"project_id": PRJ, "items": [
    {"name": "OTT blok detal", "category": "  ", "quantity": 20, "unit_price": 15000, "length": 0.5,
     "is_coated": False, "penoplast_id": PENO}]})
check("C13 PUT '  ' -> 400, bazada AYNAN", _s == 400 and buyurtma(O1) == oldin, [_s, _j])

# HTTP — POST
_old = buyurtma_idlari()
p0 = peno_qoldiq()
_s, _j = api("POST", "/api/orders?confirm_shortage=true", {"project_id": PRJ, "items": [
    {"name": "OTT C14", "category": "", "quantity": 2, "unit_price": 100, "length": 2, "is_coated": False, "penoplast_id": PENO}]})
check("C14 POST bo'sh tur -> 400, buyurtma yaratilmadi, ombor AYNAN",
      _s == 400 and "turi ko'rsatilmagan" in xabar(_j) and buyurtma_idlari() == _old and teng(peno_qoldiq(), p0, 1e-9),
      [_s, _j, buyurtma_idlari(), _old])
_s, _j = api("POST", "/api/orders", {"project_id": PRJ, "items": [
    {"name": "OTT C15 katta", "category": "profil", "width": 100, "thickness": 100, "length": 100000, "quantity": 1,
     "unit_price": 1, "is_coated": False, "penoplast_id": PENO},
    {"name": "OTT C15 bosh", "category": "", "quantity": 1, "unit_price": 1, "length": 1, "is_coated": False}]})
check("C15 POST bo'sh tur + yetishmovchilik -> 400 (409 \"davom etasizmi\" dan OLDIN), yaratilmadi",
      _s == 400 and buyurtma_idlari() == _old, [_s, str(_j)[:200]])

# crud to'g'ridan (ildiz to'sig'i — marshrutni chetlab)
_old = buyurtma_idlari()
_st = None
s = SessionLocal()
try:
    crud.create_order(s, schemas.OrderCreate(project_id=PRJ, items=[
        _it(name="OTT C16", category="", quantity=1, unit_price=100, length=1, is_coated=False)]), company_id=1)
    _st = "yaratildi"
except Exception as e:
    _st = getattr(e, "status_code", None) or f"{type(e).__name__}: {e}"
finally:
    s.close()
check("C16 crud.create_order bo'sh tur -> HTTPException 400, yaratilmadi", _st == 400 and buyurtma_idlari() == _old, [_st, buyurtma_idlari()])

oldin = buyurtma(O1)
p0 = peno_qoldiq()
s = SessionLocal()
try:
    _res = crud.update_order_full(s, O1, schemas.OrderCreate(project_id=PRJ, items=[
        _it(name="OTT blok detal", category="", quantity=20, unit_price=15000, length=0.5, is_coated=False, penoplast_id=PENO)]))
except Exception as e:
    _res = {"istisno": f"{type(e).__name__}: {e}"}
finally:
    s.close()
check("C17 crud.update_order_full bo'sh tur -> success False, xabar aniq",
      isinstance(_res, dict) and _res.get("success") is False and "turi ko'rsatilmagan" in str(_res.get("message")), _res)
check("C18 update_order_full rad: bazada va omborda AYNAN", buyurtma(O1) == oldin and teng(peno_qoldiq(), p0, 1e-9),
      [oldin, buyurtma(O1)])

# nazorat: server tur o'chiq bo'lsa ham to'g'ri blok detalni qabul qiladi (UI dagi yashirish — ixtiyoriy)
_old = buyurtma_idlari()
_s, _j = api("POST", "/api/orders?confirm_shortage=true", {"project_id": PRJ, "items": [
    {"name": "OTT C19 blok", "category": "blok", "quantity": 4, "unit_price": 10000, "length": 0.1,
     "is_coated": False, "penoplast_id": PENO, "notes": "blok_narxi=400000,blok_yield=40"}]})
check("C19 (nazorat) to'g'ri blok detal -> 200", _s == 200 and len(buyurtma_idlari()) == len(_old) + 1, [_s, str(_j)[:200]])


# ═════════════════════════════════════════════════════════════════════════
section("D. statik — chaqiruv tartibi")
_es = funksiya_matni(HTML, "editSelected")
_pf = funksiya_matni(HTML, "pickFinished")
_rd = funksiya_matni(HTML, "restoreDraftLS")
_ai = funksiya_matni(HTML, "addItem")
check("D1 editSelected: turVariantiniTaminla(row, cat) -> typeEl.value = cat",
      tartibda(_es, "turVariantiniTaminla(row, cat);", "typeEl.value = cat;"))
check("D2 pickFinished: turVariantiniTaminla -> typeEl.value = effectiveType",
      tartibda(_pf, "turVariantiniTaminla(row, effectiveType);", "typeEl.value = effectiveType;"))
check("D3 restoreDraftLS: turVariantiniTaminla -> typeEl.value = rowData['i-type']",
      tartibda(_rd, "turVariantiniTaminla(row, rowData['i-type']);", "typeEl.value = rowData['i-type'];"))
check("D4 addItem: oldingi tur faqat yangi qatorda variant BO'LSA o'tadi",
      tartibda(_ai, "turVariantiBor(div, lastTypeAsl) ? lastTypeAsl : null", "typeSel.value = lastType"))
check("D5 yordamchilar orders.html da AYNAN bittadan",
      HTML.count("function turVariantiniTaminla(") == 1 and HTML.count("function turVariantiBor(") == 1)
_uo = manba(crud, "update_order_full")
check("D6 update_order_full: bo'sh tur tekshiruvi qulf va o'qishdan OLDIN",
      tartibda(_uo, "_detal_turi_tekshir(", "return {\"success\": False", "_pul_qulfi("))
_co = manba(crud, "create_order")
check("D7 create_order: bo'sh tur tekshiruvi birinchi yozuvdan (db.add) OLDIN",
      tartibda(_co, "_detal_turi_tekshir(", "status_code=400", "db.add("))
_ac = manba(main, "api_create_order")
check("D8 POST /api/orders: tekshiruv yetishmovchilik tekshiruvidan OLDIN",
      tartibda(_ac, "_detal_turi_tekshir(order.items)", "except ValueError", "check_inventory_for_order("))


print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
