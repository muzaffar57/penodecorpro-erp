#!/usr/bin/env python3
"""
test_html_escape_dom.py — DINAMIK innerHTML / HTML in'ektsiya darvozasi
(5-bo'lim 2-band, kech29).

NIMA UCHUN KERAK
----------------
Server matn maydonlarida `<`, `>`, `"`, `'` belgilarini RAD ETMAYDI (nom,
izoh, kategoriya, telefon, birlik va h.k. — bu ataylab: ular biznes
matni). Demak xavfsizlik sahifa tomonida: foydalanuvchi matni
`innerHTML` ga `escapeHtml(...)` siz tushsa, u HTML sifatida chiziladi
(kech26 U1 — detal nomi `<img src=x onerror=...>` saqlanadi va ishga
tushardi).

kech28 da STATIK xarita qilingan edi (kod matnini qidirish). kech29 da
jonli sinov ko'rsatdi: statik qidiruv BILVOSITA chizuvchilarni ko'rmaydi —
masalan `reports.html` jadvali `<td>${h[1](row)}</td>` orqali chiziladi,
xom qiymat esa alohida ustun funksiyasida (`i => i.item_name`) qaytadi.
Shuning uchun bu test sahifani HAQIQIY brauzer muhitida (jsdom) ochib,
natijani DOM da O'LCHAYDI — jonli sinovdagi usulning o'zi, faqat
avtomatik va hamma sahifa uchun.

QANDAY ISHLAYDI
---------------
1. Vaqtinchalik SQLite bazada fikstura: loyiha, buyurtma, yetkazish,
   to'lov, qaytarish, xarajat, transport, xarid, ta'minotchi to'lovi,
   usta, hodim (avans, tuzatma), sovg'a davri, tayyor mahsulot, ombor
   (kam qoldiqli material — ogohlantirish / bildirishnoma), noto'g'ri
   login (login tarixi), xato jurnali. Har qadam 2xx bo'lishi SHART
   (fikstura jim eskirmasin).
2. Bazadagi HAR bir erkin matn ustuniga belgi yoziladi:
       '"><i class=xpN>ID
   Qo'shtirnoq atributni ham, `onclick="f('...')"` ichidagi JS satrini
   ham sindiradi — shuning uchun HTML matn, atribut va JS satri
   kontekstlari bitta aniqlagich (`<i class="xpN">` tuguni) bilan o'lchanadi.
   `xpN` — ustun raqami (qaysi ustun sizganini ko'rsatadi), oxiridagi ID
   noyoblik cheklovlari uchun (sig'masa tashlanadi). 18 belgidan qisqa
   ustunlar belgi sig'dira olmaydi (ro'yxati chiqariladi).
   Qaysi ustun ERKIN matn ekanini serverning o'z qoidalari aniqlaydi:
   `crud._val_rules` / `_upd_rules` / `_create_rules` da `matn` dan
   boshqa turdagi (masalan `tanlov`) maydon — server nazoratida,
   o'tkaziladi. Texnik ustunlar (token, parol xeshi, raqam generatori,
   JSON sozlamalar) `TEXNIK` ro'yxatida. Yangi matn ustunlari AVTOMATIK
   qamraladi.
3. Ilova lokal uvicorn serverida ko'tariladi, admin sifatida login
   qilinadi, har sahifa jsdom da ochiladi: sahifaning o'z skriptlari
   ishlaydi, `fetch` lokal serverga (cookie bilan) yo'naltiriladi,
   tarmoq tinchigach `i.xp` tugunlari sanaladi. Ba'zi sahifalarda
   yuklanishdan keyin qo'shimcha oqimlar chaqiriladi (`AMALLAR` —
   masalan hisobotning har bir turi, buyurtma tafsilotlari). Amallardan
   keyin sahifa ichida mantiqiy TEKSHIRUVLAR ham bajariladi (6-bo'lim,
   kech30): escape qo'shilgani sahifaning boshqa xulqini buzmaganini
   isbotlash uchun (masalan hisobot jadvalini saralash kaliti).
4. IJOBIY NAZORAT: har ishga tushirishda sun'iy sahifa xom `innerHTML`
   bilan chiziladi — belgi topilishi SHART. Bu "0 ta sizish" natijasi
   buzilgan qurilma (cookie, fetch, jsdom) tufayli emasligini isbotlaydi.
5. UMUMIY YORDAMCHILAR (3a-bo'lim, kech30): `escapeHtml` va
   `jsAttrEscape` HAQIQIY `templates/base.html` dan olinib, o'z
   kontekstida (matn, qo'shtirnoqli va yakka tirnoqli atribut, onclick
   ichidagi JS satri) 13 xil qiyin matn bilan sinaladi: natija AYNAN
   kiritilgan matn bo'lishi, kod bajarilmasligi, HTML tuguni
   yaratilmasligi SHART. Sabab: entity ko'rinishidagi tirnoq (`&#39;`)
   kodni bajaradi, lekin DOM tugun yaratmaydi — 5-bo'lim uni ko'rmaydi
   (kech30 da `jsAttrEscape` da aynan shunday nuqson O'LCHANGAN).

CHEKLOV: jsdom yuklanishda va AMALLAR da ishlaydigan kodni ko'radi;
faqat tugma bosilganda ochiladigan oynalar STATIK darvoza
(`tools/test_html_escape.py`) bilan qoplanadi. `/hodim` (PIN bilan
kiriladigan hodim paneli) bu testda ochilmaydi.

TALAB: `node` va `jsdom` (`npm install -g jsdom@24`). jsdom topilmasa
test YIQILADI (jim o'tkazib yubormaydi).

ISHLATISH
---------
    python3 tools/test_html_escape_dom.py
    TENANT_FILTER=1 python3 tools/test_html_escape_dom.py
Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bitta yiqildi.
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
import contextlib
import subprocess
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

_TMP = tempfile.mkdtemp(prefix="dom_esc_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'dom.db')}"

_quiet = io.StringIO()
OK = 0
FAIL = 0


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        print(f"  ❌ {label}" + (f"\n       ↳ {detail}" if detail else ""))


def section(t):
    print(f"\n--- {t} ---")


def info(t):
    print(f"  ℹ️  {t}")


# ══════════════════════════════════════════════════════════════
# Ustunlar siyosati
# ══════════════════════════════════════════════════════════════
# Texnik ustunlar: foydalanuvchi erkin matni EMAS (generator, token,
# xesh, JSON / sozlama, server qo'yadigan kod qiymatlari). Belgi
# yozilsa mantiq buziladi yoki ular foydalanuvchi kiritmaydigan qiymat.
TEXNIK = {
    "activity_logs": {"action", "entity_type"},
    "bom_items": {"component_type"},
    "companies": {"code", "logo_path"},
    "company_settings": {"key", "value"},
    "deliveries": {"delivery_number", "transport_payer"},
    "employee_compensation_history": {"per_unit_type"},
    "employee_sessions": {"token"},
    "employees": {"per_unit_type", "production_type", "pin_hash"},
    "error_logs": {"method"},
    "expense_transactions": {"source", "production_type"},
    "finished_product_sales": {"payment_method", "sale_group_id"},
    "finished_products": {"gips_additives_json", "return_reason"},
    "inventory_movements": {"movement_type"},
    "inventory_receipts": {"production_type"},
    "master_gift_period_redemptions": {"kind"},
    "order_attachments": {"file_url"},
    "order_items": {"gips_unit"},
    "orders": {"order_number"},
    "product_types": {"input_template", "pricing_formula"},
    "production_orders": {"source_type", "status", "selected_optional_bom_item_ids_json",
                          "recipe_snapshot_json"},
    "projects": {"project_number"},
    "recurring_obligations": {"icon"},
    "transport_expenses": {"production_type"},
    "user_sessions": {"token"},
    "users": {"password_hash"},
}
# Qoidalar lug'atidagi kalit model sinfi nomidan farq qiladigan holatlar
QOIDA_NOMI = {"ReturnItem": "Return"}

ADMIN_LOGIN = "DOM_admin"
ADMIN_PAROL = "Parol123!"

# Sahifalar: (yo'l, 200 majburiymi). Parametrli yo'llar fiksturadan keyin
# to'ldiriladi.
SAHIFALAR = ["/dashboard", "/debts", "/finance", "/finished", "/inventory", "/kpi",
             "/kunlik-xarajat", "/logs", "/orders", "/production", "/projects", "/recipes",
             "/reports", "/returns", "/suppliers", "/trash", "/users", "/ustalar"]
# `/tiklash` ADMIN uchun 403 (kech29 da o'lchangan) — bu testda ochilmaydi.

NODE_JS = r"""
let JSDOM, VirtualConsole, ResourceLoader;
try {
  ({ JSDOM, VirtualConsole, ResourceLoader } = require("jsdom"));
} catch (e) {
  console.log(JSON.stringify({ fatal: "jsdom topilmadi: " + String(e.message).slice(0, 200) }));
  process.exit(3);
}
const base = process.argv[2];
const cookie = process.argv[3];
const pages = JSON.parse(require("fs").readFileSync(process.argv[4], "utf8"));

// Resurslar: o'z serverimiz — haqiqiy; CDN kutubxonalari — SOXTA tana
// (haqiqiy saytdagidek `window.Chart = ...` ni SKRIPT o'rnatadi: `base.html`
// `window.Chart` ga setter qo'yib, yuklangan konstruktorni o'raydi — soxtani
// oldindan qo'yish uni chetlab o'tardi, kech29 da o'lchangan); boshqasi — yo'q.
class FaqatOzimiz extends ResourceLoader {
  fetch(url, options) {
    if (url.startsWith(base)) return super.fetch(url, options);
    let tana = null;
    if (/chart(\.umd)?(\.min)?\.js/i.test(url)) tana = "window.Chart = window.__HAMMA;";
    else if (/xlsx/i.test(url)) tana = "window.XLSX = window.__HAMMA;";
    if (tana === null) return null;
    const pr = Promise.resolve(Buffer.from(tana));
    pr.abort = () => {};
    return pr;
  }
}

const BELGI = /^xp\d+$/;
const belgimi = el => el.tagName === "I" && BELGI.test(el.className || "");

function yol(el) {
  const s = [];
  let x = el.parentElement;
  while (x && belgimi(x)) x = x.parentElement;   // yopilmagan belgi tugunlari — ota emas
  for (let k = 0; k < 4 && x; k++) {
    if (belgimi(x)) { x = x.parentElement; k--; continue; }
    let t = x.tagName.toLowerCase();
    if (x.id) t += "#" + x.id;
    else if (typeof x.className === "string" && x.className.trim()) t += "." + x.className.trim().split(/\s+/)[0];
    s.push(t);
    if (x.id) break;
    x = x.parentElement;
  }
  return s.join("<");
}

const kut = ms => new Promise(r => setTimeout(r, ms));

// Canvas va shunga o'xshash API lar uchun: har xususiyat va har chaqiruv
// o'zini qaytaradi (masalan `ctx.createLinearGradient(...).addColorStop()`).
const HAMMA = new Proxy(function () {}, {
  get(t, k) {
    if (k === Symbol.toPrimitive) return () => 0;
    if (k === "then") return undefined;
    return HAMMA;
  },
  apply() { return HAMMA; },
  construct() { return HAMMA; },
});

// Sahifa skriptidagi ushlanmagan xato / rad etilgan va'da node jarayonini
// QULATMASIN — joriy sahifa natijasiga yoziladi.
let JORIY = null;
process.on("unhandledRejection", e => {
  if (JORIY) JORIY.xato.push("ushlanmagan va'da: " + String((e && (e.message || e)) || "").slice(0, 200));
});
process.on("uncaughtException", e => {
  if (JORIY) JORIY.xato.push("ushlanmagan xato: " + String((e && (e.message || e)) || "").slice(0, 200));
});

async function sahifa(p) {
  const res = { page: p.path, status: 0, xato: [], api_xato: [], topildi: [] };
  JORIY = res;
  let html = p.html || null;
  if (!html) {
    let r;
    try {
      r = await fetch(base + p.path, { headers: { cookie }, redirect: "manual" });
    } catch (e) {
      res.xato.push("sahifa fetch: " + e.message);
      return res;
    }
    res.status = r.status;
    if (r.status !== 200) return res;
    html = await r.text();
  } else {
    res.status = 200;
  }
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => {
    const m = String((e && (e.message || e)) || "").slice(0, 220);
    if (!/Not implemented/.test(m)) res.xato.push(m);
  });
  let pending = 0;
  let lastActive = Date.now();
  const sahifaUrl = base + (p.html ? "/__nazorat__" : p.path);
  const dom = new JSDOM(html, {
    url: sahifaUrl,
    runScripts: "dangerously",
    pretendToBeVisual: true,
    resources: new FaqatOzimiz(),
    virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => {
        pending++;
        lastActive = Date.now();
        try {
          o = o || {};
          const h = Object.assign({}, o.headers || {});
          h.cookie = cookie;
          const url = new URL(String(u), sahifaUrl).href;
          if (!url.startsWith(base)) throw new Error("tashqi so'rov: " + url);
          const resp = await fetch(url, Object.assign({}, o, { headers: h, redirect: "manual" }));
          if (resp.status >= 500) res.api_xato.push(resp.status + " " + url.slice(base.length, base.length + 90));
          return resp;
        } finally {
          pending--;
          lastActive = Date.now();
        }
      };
      w.alert = () => {};
      w.confirm = () => false;
      w.prompt = () => null;
      w.print = () => {};
      w.scrollTo = () => {};
      w.open = () => null;
      w.matchMedia = () => ({ matches: false, media: "", addListener() {}, removeListener() {},
                              addEventListener() {}, removeEventListener() {} });
      class Kuzatuvchi { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } }
      w.IntersectionObserver = Kuzatuvchi;
      w.ResizeObserver = Kuzatuvchi;
      w.__HAMMA = HAMMA;
      w.HTMLCanvasElement.prototype.getContext = () => HAMMA;
      w.HTMLElement.prototype.scrollIntoView = () => {};
    },
  });
  const w = dom.window;
  await new Promise(r => {
    if (w.document.readyState === "complete") return r();
    w.addEventListener("load", () => r());
    setTimeout(r, 6000);
  });
  async function tinch() {
    const t0 = Date.now();
    while (Date.now() - t0 < 12000) {
      await kut(100);
      if (pending === 0 && Date.now() - lastActive > 700) return;
    }
    res.xato.push("tarmoq 12 s ichida tinchimadi");
  }
  // Tugunlar yuklanishdan keyin VA har amaldan keyin yig'iladi: keyingi
  // amal oldingisining natijasini ustidan yozishi mumkin (masalan hisobot
  // turlari bitta jadvalga chiziladi).
  const korilgan = new Set();
  function yigish(bosqich) {
    for (const e of w.document.getElementsByTagName("i")) {
      if (!belgimi(e)) continue;
      const k = e.className + " @ " + yol(e);
      if (!korilgan.has(k)) { korilgan.add(k); res.topildi.push(k + (bosqich ? " [" + bosqich + "]" : "")); }
    }
  }
  await tinch();
  yigish("");
  for (const a of p.amallar || []) {
    try {
      await w.eval("(async () => { " + a + " })()");
    } catch (e) {
      res.xato.push("amal [" + a.slice(0, 60) + "]: " + String(e && e.message).slice(0, 160));
    }
    await tinch();
    yigish(a.slice(0, 40));
  }
  // Sahifa ichidagi mantiqiy tekshiruvlar (6-bo'lim): ifoda `true` qaytarsa o'tadi.
  res.tekshiruv = [];
  for (const [nom, ifoda] of p.tekshiruvlar || []) {
    let ok = false, qiymat = null;
    try {
      qiymat = await w.eval("(async () => { " + ifoda + " })()");
      ok = qiymat === true;
    } catch (e) {
      qiymat = "xato: " + String(e && e.message).slice(0, 160);
    }
    res.tekshiruv.push({ nom, ok, qiymat: typeof qiymat === "string" ? qiymat.slice(0, 200) : qiymat });
  }
  w.close();
  return res;
}

(async () => {
  for (const p of pages) {
    let r;
    try {
      r = await sahifa(p);
    } catch (e) {
      r = { page: p.path, status: -1, xato: ["QULADI: " + String(e && e.stack).slice(0, 300)], api_xato: [], topildi: [] };
    }
    console.log(JSON.stringify(r));
  }
  console.log(JSON.stringify({ tugadi: true }));
  process.exit(0);
})();
"""

NAZORAT_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<div id="k1"></div><div id="k2"></div>
<script>
fetch('/api/inventory').then(function (r) { return r.json(); }).then(function (a) {
  document.getElementById('k1').innerHTML = a.map(function (i) { return '<p>' + i.item_name + '</p>'; }).join('');
  document.getElementById('k2').innerHTML = a.map(function (i) { return '<b data-x="' + i.item_name + '">x</b>'; }).join('');
});
</script></body></html>"""

# ══════════════════════════════════════════════════════════════
# 3a. Umumiy yordamchilar: base.html dagi escapeHtml / jsAttrEscape
# ══════════════════════════════════════════════════════════════
# Nima uchun alohida: sahifa belgisi (`'"><i class=xpN>`) xom `'` va `"`
# ishlatadi. `jsAttrEscape` ularni to'g'ri ushlaydi, lekin kech30 da
# O'LCHANDI: `&#39;` kabi entity ko'rinishidagi tirnoq brauzer atributni
# o'qiganda ASL `'` ga aylanib, onclick JS satridan chiqib kod BAJARILARDI
# (`&` escape qilinmagan edi). Bunday bajarilish DOM tugunini yaratmaydi —
# 5-bo'lim uni ko'rmaydi. Shuning uchun har yordamchi o'zi ishlatiladigan
# kontekstda haqiqiy HTML tahlili bilan sinaladi. Talab: natija AYNAN
# kiritilgan matn, kod bajarilmagan, HTML tuguni yaratilmagan. Funksiyalar
# HAQIQIY `templates/base.html` dan olinadi (nusxa emas).
# Eslatma: HTML standarti matn va atributdagi `\r` ni `\n` ga aylantiradi
# (kirish oqimini normallashtirish) — bu nuqson emas, shuning uchun matn /
# atribut kontekstida kutilgan qiymatda `\r\n` / `\r` → `\n`. onclick JS
# satrida esa `\r` ham AYNAN qaytishi shart (jsAttrEscape `\\r` qiladi).
YORDAMCHI_YUKLAR = [
    ("xom belgi", "'\"><i class=xp0>"),
    ("&#39; entity", "&#39;);window.__p=1;//"),
    ("&apos; entity", "&apos;);window.__p=1;//"),
    ("&#x27; entity", "&#x27;);window.__p=1;//"),
    ("&quot; entity", "&quot;);window.__p=1;//"),
    ("tayyor entity matni", "&amp;lt;b&gt; &lt;"),
    ("qator uzilishi", "a\nb"),
    ("karetka qaytishi", "a\rb"),
    ("oxirida backslash", "a\\"),
    ("backslash + tirnoq", "\\'"),
    ("script yopilishi", "</script><i class=xp0>"),
    ("o'zbekcha matn", "Qo'rg'oshin \"A\" <5kg> & co"),
    ("emoji", "🔴 5 ta"),
]
YORDAMCHI_KONTEKSTLAR = ["matn", "atribut (\")", "atribut (')", "onclick JS satri"]

YORDAMCHI_JS = r"""
let JSDOM, VirtualConsole;
try {
  ({ JSDOM, VirtualConsole } = require("jsdom"));
} catch (e) {
  console.log(JSON.stringify({ fatal: "jsdom topilmadi: " + String(e.message).slice(0, 200) }));
  process.exit(3);
}
const d = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
// Har kontekst sahifalardagi haqiqiy ishlatilishdek: innerHTML ga template
// literal bilan yoziladi.
const SHABLON = {
  "matn": "`<p id=t>${escapeHtml(window.__y)}</p>`",
  "atribut (\")": "`<b id=t data-x=\"${escapeHtml(window.__y)}\"></b>`",
  "atribut (')": "`<b id=t data-x='${escapeHtml(window.__y)}'></b>`",
  "onclick JS satri": "`<button id=t onclick=\"f('${jsAttrEscape(window.__y)}')\">x</button>`",
};
function bir(kontekst, y) {
  const xatolar = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => xatolar.push(String((e && (e.message || e)) || "").slice(0, 140)));
  const dom = new JSDOM("<!doctype html><html><body><div id=r></div><script>" + d.kod +
    "\nwindow.__arg = undefined; window.__p = 0; function f(a) { window.__arg = a; }</script></body></html>",
    { runScripts: "dangerously", virtualConsole: vc });
  const w = dom.window;
  w.__y = y;
  try {
    w.eval("document.getElementById('r').innerHTML = " + SHABLON[kontekst] + ";");
  } catch (e) {
    xatolar.push("chizish: " + String(e && e.message).slice(0, 140));
  }
  const kutilgan = kontekst === "onclick JS satri" ? y : y.replace(/\r\n?/g, "\n");
  const t = w.document.getElementById("t");
  const tugun = w.document.querySelectorAll("#r i").length;
  let olingan = null, ok = false;
  if (t) {
    if (kontekst === "matn") {
      olingan = t.textContent;
      ok = olingan === kutilgan && t.children.length === 0;
    } else if (kontekst.startsWith("atribut")) {
      olingan = t.getAttribute("data-x");
      ok = olingan === kutilgan && tugun === 0;
    } else {
      try { t.click(); } catch (e) { xatolar.push("bosish: " + String(e && e.message).slice(0, 140)); }
      olingan = w.__arg === undefined ? "(f chaqirilmadi)" : w.__arg;
      ok = w.__arg === kutilgan && w.__p === 0 && tugun === 0;
    }
  } else {
    xatolar.push("#t elementi chizilmadi");
  }
  const bajarildi = w.__p === 1;
  w.close();
  return { kontekst, ok, olingan, bajarildi, tugun, xato: xatolar.join(" | ") };
}
for (const k of d.kontekstlar) {
  for (const [nom, y] of d.yuklar) {
    let r;
    try {
      r = bir(k, y);
    } catch (e) {
      r = { kontekst: k, ok: false, olingan: null, bajarildi: false, tugun: 0,
            xato: "QULADI: " + String(e && e.message).slice(0, 200) };
    }
    r.nom = nom;
    console.log(JSON.stringify(r));
  }
}
console.log(JSON.stringify({ tugadi: true }));
process.exit(0);
"""


def yordamchi_kodi():
    """`templates/base.html` dan escapeHtml va jsAttrEscape funksiyalarining
    HAQIQIY matni (qavslar muvozanati bo'yicha). Topilmasa — None."""
    try:
        with open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8") as fh:
            s = fh.read()
    except OSError:
        return None
    qismlar = []
    for nom in ("escapeHtml", "jsAttrEscape"):
        i = s.find("function " + nom + "(")
        if i < 0:
            return None
        j = s.find("{", i)
        if j < 0:
            return None
        chuqurlik = 0
        k = j
        while k < len(s):
            if s[k] == "{":
                chuqurlik += 1
            elif s[k] == "}":
                chuqurlik -= 1
                if chuqurlik == 0:
                    break
            k += 1
        if k >= len(s):
            return None
        qismlar.append(s[i:k + 1])
    return "\n".join(qismlar)


def yordamchi_bolimi(node, env):
    section("3a. Umumiy yordamchilar (base.html escapeHtml / jsAttrEscape): "
            "haqiqiy HTML tahlilida AYNAN qaytishi SHART")
    kod = yordamchi_kodi()
    check("base.html dan escapeHtml va jsAttrEscape olindi", kod is not None)
    if kod is None:
        return
    pj = os.path.join(_TMP, "yordamchi.json")
    with open(pj, "w", encoding="utf-8") as fh:
        json.dump({"kod": kod, "yuklar": YORDAMCHI_YUKLAR, "kontekstlar": YORDAMCHI_KONTEKSTLAR},
                  fh, ensure_ascii=False)
    js = os.path.join(_TMP, "yordamchi.js")
    with open(js, "w", encoding="utf-8") as fh:
        fh.write(YORDAMCHI_JS)
    try:
        k = subprocess.run([node, js, pj], capture_output=True, text=True, timeout=240, env=env)
        chiqish, xato_matn = k.stdout, k.stderr
    except Exception as e:
        chiqish, xato_matn = "", repr(e)
    natija = {}
    fatal = None
    tugadi = False
    for q in chiqish.splitlines():
        q = q.strip()
        if not q.startswith("{"):
            continue
        try:
            d = json.loads(q)
        except Exception:
            continue
        if "fatal" in d:
            fatal = d["fatal"]
        elif d.get("tugadi"):
            tugadi = True
        elif "kontekst" in d:
            natija[(d["kontekst"], d.get("nom"))] = d
    check("yordamchi sinovi jsdom da ishladi", fatal is None and tugadi,
          (fatal or "") + " " + xato_matn[-300:])
    for kt in YORDAMCHI_KONTEKSTLAR:
        for nom, y in YORDAMCHI_YUKLAR:
            d = natija.get((kt, nom))
            if d is None:
                check(f"{kt}: {nom}", False, "natija yo'q")
                continue
            tafsil = (f"kiritilgan={y!r} olingan={d.get('olingan')!r} bajarildi={d.get('bajarildi')} "
                      f"tugun={d.get('tugun')} {d.get('xato') or ''}")
            check(f"{kt}: {nom}", d.get("ok") is True, tafsil[:400])


def bosh_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main_ish():
    with contextlib.redirect_stdout(_quiet):
        import main
        import crud
        import auth
        import schemas
        import models
    from database import SessionLocal, engine, Base
    from models import UserRole
    from sqlalchemy import String, Text, Enum as SAEnum, select
    from fastapi.testclient import TestClient

    # ─────────────────────────────────────────────────────────
    section("1. Fikstura (har qadam 2xx bo'lishi SHART)")
    db = SessionLocal()
    with contextlib.redirect_stdout(_quiet):
        auth.create_user(db, ADMIN_LOGIN, ADMIN_PAROL, UserRole.ADMIN, "DOM Admin", company_id=1)
        for k, rol in enumerate(r for r in UserRole if r != UserRole.ADMIN):
            auth.create_user(db, f"DOM_rol{k}", ADMIN_PAROL, rol, f"DOM Rol {k}", company_id=1)
        inv_a = crud.add_item(db, schemas.InventoryCreate(
            item_name="DOM Material A", unit="kg", stock_quantity=100, price_per_unit=1000,
            category="kimyo", notes="izoh"), company_id=1)
        inv_kam = crud.add_item(db, schemas.InventoryCreate(
            item_name="DOM Material Kam", unit="kg", stock_quantity=0, min_stock=5,
            price_per_unit=1000), company_id=1)
        pen = crud.add_item(db, schemas.InventoryCreate(
            item_name="DOM Penoplast", unit="blok", stock_quantity=100, price_per_unit=500000,
            is_penoplast=True, volume_per_unit=1.0), company_id=1)
        rec = crud.create_recipe(db, schemas.RecipeCreate(
            name="DOM Retsept", batch_size_kg=10,
            ingredients=[schemas.RecipeIngredientCreate(inventory_id=inv_a.id, quantity_kg=1)]),
            company_id=1)
        p1 = crud.create_project(db, schemas.ProjectCreate(
            project_name="DOM Loyiha 1", client_name="DOM Mijoz 1", client_phone="+998901234567",
            client_address="Manzil", description="Tavsif", notes="Izoh"), company_id=1)
        p2 = crud.create_project(db, schemas.ProjectCreate(
            project_name="DOM Loyiha 2", client_name="DOM Mijoz 2"), company_id=1)
        emp = crud.create_employee(db, schemas.EmployeeCreate(
            name="DOM Hodim", position="Usta", pay_type="fixed", fixed_amount=1000000), company_id=1)
        o1 = crud.create_order(db, schemas.OrderCreate(
            project_id=p1.id, order_type="product",
            items=[schemas.OrderItemCreate(name="DOM Detal 1", category="panel", width=100, thickness=10,
                                           length=100, quantity=10, unit_price=100000, is_coated=False),
                   schemas.OrderItemCreate(name="DOM Detal 2", category="panel", width=100, thickness=10,
                                           length=100, quantity=5, unit_price=50000, is_coated=False)]),
            performed_by="DOM")
        o2 = crud.create_order(db, schemas.OrderCreate(
            project_id=p2.id, order_type="product",
            items=[schemas.OrderItemCreate(name="DOM Detal 3", category="panel", width=100, thickness=10,
                                           length=100, quantity=3, unit_price=70000, is_coated=False)]),
            performed_by="DOM")
        sup = crud.create_supplier(db, schemas.SupplierCreate(name="DOM Taminotchi", phone="+998907654321"),
                                   company_id=1)
    ids = dict(inv_a=inv_a.id, inv_kam=inv_kam.id, pen=pen.id, rec=rec.id, p1=p1.id, p2=p2.id,
               emp=emp.id, o1=o1.id, o2=o2.id, sup=sup.id)
    o1_items = [it.id for it in db.query(models.OrderItem).filter(models.OrderItem.order_id == o1.id)
                .order_by(models.OrderItem.id).all()]
    # Yetkazish qoralama buyurtmaga yozilmaydi — ish holatiga o'tkazamiz
    for oid in (o1.id, o2.id):
        o = db.get(models.Order, oid)
        if str(getattr(o.status, "value", o.status)) == "draft":
            o.status = models.OrderStatus.IN_PROGRESS
    db.commit()
    db.close()
    check("crud fikstura yaratildi (material, retsept, loyiha, hodim, buyurtma, ta'minotchi)", True)

    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": ADMIN_LOGIN, "password": ADMIN_PAROL}, follow_redirects=False)
    check(f"TestClient login → {r.status_code}", r.status_code in (200, 302, 303), r.text[:160])

    sabab = sorted(getattr(crud, "_QAYTARISH_SABABI", {"Brak": "Brak"}).keys())[0]
    qadamlar = [
        ("yetkazish (to'lov bilan)", "post", "/api/deliveries",
         {"order_id": ids["o1"], "items": [{"order_item_id": o1_items[0], "quantity": 2}],
          "notes": "izoh", "received_by": "Qabul qiluvchi", "transport_carrier": "Tashuvchi",
          "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd",
          "payment_amount": 1000}),
        ("to'lov", "post", "/api/payments", {"order_id": ids["o1"], "amount": 5000, "notes": "tolov izohi"}),
        ("qaytarish", "post", "/api/returns",
         {"order_id": ids["o1"], "order_item_id": o1_items[0], "item_name": "DOM Detal 1",
          "quantity": 1, "reason": sabab, "notes": "qaytarish izohi"}),
        ("xarajat", "post", "/api/finance/transactions",
         {"date": "2026-09-22", "category": "Boshqa", "amount": 1234, "notes": "xarajat izohi",
          "production_type": "umumiy"}),
        ("transport xarajati", "post", "/api/transport-expenses",
         {"amount": 10000, "materials_note": "yuk", "notes": "izoh", "production_type": "umumiy"}),
        ("xarid", "post", f"/api/inventory/{ids['inv_a']}/purchase",
         {"quantity": 2, "price_per_unit": 1000, "supplier_id": ids["sup"], "notes": "xarid izohi"}),
        ("ta'minotchiga to'lov", "post", f"/api/suppliers/{ids['sup']}/payment",
         {"amount": 500, "notes": "tolov"}),
        ("usta", "post", "/api/masters",
         {"name": "DOM Usta", "phone": "+998901112233", "region": "Andijon", "notes": "izoh",
          "telegram_id": "7700123"}),
        ("hodim avansi", "post", f"/api/employees/{ids['emp']}/advance",
         ("params", {"amount": 1000, "notes": "avans"})),
        ("hodim tuzatmasi", "post", f"/api/employees/{ids['emp']}/monthly-adjustment",
         ("params", {"year": 2026, "month": 9, "reduction_amount": 100, "reason": "sabab"})),
        ("sovg'a davri", "post", "/api/gift-period/open",
         {"tiers": [{"gift_name": "DOM Sovga", "threshold_amount": 1000000}]}),
        ("tayyor mahsulot", "post", "/api/finished/produce",
         {"name": "DOM Karniz", "category": "profil", "is_coated": False, "penoplast_id": ids["pen"],
          "price_per_m3": None, "unit_price": 100000, "recipe_id": None, "notes": "izoh",
          "width": 10, "thickness": 10, "length": 10, "quantity": 5}),
    ]
    for nom, usul, url, tana in qadamlar:
        if isinstance(tana, tuple) and tana and tana[0] == "params":
            rr = getattr(c, usul)(url, params=tana[1])
        else:
            rr = getattr(c, usul)(url, json=tana)
        check(f"fikstura: {nom} → {rr.status_code}", 200 <= rr.status_code < 300, rr.text[:200])
    # Login tarixi: noto'g'ri urinish (username — hujumchi nazoratidagi matn)
    c2 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c2.post("/login", data={"username": "DOM_yoq", "password": "notogri"}, follow_redirects=False)
    # Xato jurnali: bitta yozuv (belgi keyin yoziladi)
    db = SessionLocal()
    try:
        el_cls = next((m.class_ for m in Base.registry.mappers
                       if getattr(m.class_, "__tablename__", "") == "error_logs"), None)
        if el_cls is not None:
            kw = {"error_message": "DOM xato", "endpoint": "/api/dom", "method": "GET"}
            if hasattr(el_cls, "company_id"):
                kw["company_id"] = 1
            db.add(el_cls(**kw))
            db.commit()
            check("fikstura: xato jurnali yozuvi", True)
        else:
            check("fikstura: xato jurnali modeli topildi", False, "error_logs modeli yo'q")
    except Exception as e:
        db.rollback()
        check("fikstura: xato jurnali yozuvi", False, repr(e)[:200])
    finally:
        db.close()

    # ─────────────────────────────────────────────────────────
    section("2. Har erkin matn ustuniga belgi yozish")
    qoidalar = {}
    for fn in ("_val_rules", "_upd_rules", "_create_rules"):
        f = getattr(crud, fn, None)
        if f is None:
            continue
        try:
            for model, maydonlar in f().items():
                for m, q in maydonlar.items():
                    qoidalar.setdefault(model, {}).setdefault(m, set()).add(q[0])
        except Exception as e:
            info(f"{fn} o'qilmadi: {e!r}"[:160])
    jadval_sinf = {}
    for mp in Base.registry.mappers:
        tn = getattr(mp.class_, "__tablename__", None)
        if tn:
            jadval_sinf[tn] = mp.class_.__name__
    ustunlar = []          # (jadval, ustun)
    nazoratda = []
    qisqa = []
    bosh_jadval = []
    with engine.begin() as con:
        for t in Base.metadata.sorted_tables:
            if "id" not in t.columns:
                continue
            sinf = jadval_sinf.get(t.name, "")
            model_qoida = qoidalar.get(QOIDA_NOMI.get(sinf, sinf), {})
            matn_ustunlar = []
            for col in t.columns:
                if isinstance(col.type, SAEnum) or not isinstance(col.type, (String, Text)):
                    continue
                if col.primary_key or col.foreign_keys:
                    continue
                if col.name in TEXNIK.get(t.name, set()):
                    continue
                turlar = model_qoida.get(col.name)
                if turlar and "matn" not in turlar:
                    nazoratda.append(f"{t.name}.{col.name}")
                    continue
                uz = getattr(col.type, "length", None)
                if uz is not None and uz < len("'\"><i class=xp000>"):
                    qisqa.append(f"{t.name}.{col.name}:{uz}")
                    continue
                matn_ustunlar.append(col)
            if not matn_ustunlar:
                continue
            qatorlar = [row[0] for row in con.execute(select(t.c.id))]
            if not qatorlar:
                bosh_jadval.append(t.name)
                continue
            for col in matn_ustunlar:
                n = len(ustunlar)
                ustunlar.append(f"{t.name}.{col.name}")
                uz = getattr(col.type, "length", None)
                for rid in qatorlar:
                    if t.name == "users" and col.name == "username":
                        joriy = con.execute(select(t.c.username).where(t.c.id == rid)).scalar()
                        if joriy == ADMIN_LOGIN:
                            continue
                    toliq = f"'\"><i class=xp{n}>{rid}"
                    if uz is None or len(toliq) <= uz:
                        qiymat = toliq
                    else:
                        qiymat = f"'\"><i class=xp{n}>"
                    con.execute(t.update().where(t.c.id == rid).values({col.name: qiymat}))
    info(f"belgilangan ustunlar: {len(ustunlar)}")
    info(f"server nazoratidagi (o'tkazildi): {', '.join(nazoratda) or '—'}")
    info(f"15 belgidan qisqa (belgi sig'maydi): {', '.join(qisqa) or '—'}")
    info(f"matn ustuni bor, lekin fiksturada BO'SH jadvallar: {', '.join(bosh_jadval) or '—'}")
    check("kamida 60 ta erkin matn ustuni belgilandi", len(ustunlar) >= 60, str(len(ustunlar)))
    rr = c.get("/api/inventory")
    check("belgi bazada AYNAN saqlangan (GET /api/inventory da `class=xp` bor)",
          rr.status_code == 200 and "class=xp" in rr.text, rr.text[:160])

    # ─────────────────────────────────────────────────────────
    section("2b. H2: server shablonidagi onclick JS satrlari uchun maxsus qiymatlar (kech32)")
    # H2 (kech31 topilma, kech32 da jonli saytda O'LCHANGAN): Jinja autoescape `'` ni `&#39;`
    # qiladi, brauzer atributni o'qiyotganda uni qaytaradi — `onclick="f('{{ x }}')"` da qiymat JS
    # satridan chiqib KOD BAJARADI; `|replace("'", "\\'")` esa `\` bilan aylanib o'tiladi. Bunda DOM
    # tuguni yaratilmaydi — 5-bo'lim ko'rmaydi. Shuning uchun maxsus qiymatlar (`\`, `'`, `"`, `&amp;`,
    # `</script>`, yangi qator) yoziladi va 6-bo'limda tugma BOSILADI: chaqirilgan funksiya AYNAN
    # bazadagi qiymatni olishi va `__h2*` o'zgaruvchisi paydo bo'lmasligi SHART.
    # Qatorlar belgilashdan (2-bo'lim) KEYIN yaratiladi — belgili qatorlar o'z holicha qoladi.
    H2N = "Qo'rg'oshin \\');__h2n=1;// \"A\" &amp; </script>\n2-qator"
    H2U = "\\');__h2u=1;//&amp;"
    H2I = "/static/x');__h2i=1;//\"&amp;.png"
    H2P = "Loyiha \\');__h2p=1;// \"B\" &amp;"
    H2E = "Hodim \\');__h2e=1;// &amp;\n2"
    H2L = "u\\');__h2l=1;//&amp;"
    db = SessionLocal()
    with contextlib.redirect_stdout(_quiet):
        inv_h2 = crud.add_item(db, schemas.InventoryCreate(
            item_name="DOM H2 material", unit="kg", stock_quantity=10, price_per_unit=1000,
            category="kimyo"), company_id=1)
        p_h2 = crud.create_project(db, schemas.ProjectCreate(
            project_name="DOM H2 loyiha", client_name="DOM H2 mijoz"), company_id=1)
        e_h2 = crud.create_employee(db, schemas.EmployeeCreate(
            name="DOM H2 hodim", position="Usta", pay_type="fixed", fixed_amount=1000), company_id=1)
    h2 = dict(inv=inv_h2.id, prj=p_h2.id, prj_num=p_h2.project_number, emp=e_h2.id)
    db.close()
    with engine.begin() as con:
        ti = Base.metadata.tables["inventory"]
        tp = Base.metadata.tables["projects"]
        te = Base.metadata.tables["employees"]
        tu = Base.metadata.tables["users"]
        con.execute(ti.update().where(ti.c.id == h2["inv"]).values(item_name=H2N, unit=H2U, image_url=H2I))
        con.execute(tp.update().where(tp.c.id == h2["prj"]).values(project_name=H2P, is_deleted=True))
        con.execute(te.update().where(te.c.id == h2["emp"]).values(name=H2E, is_deleted=True))
        uid = con.execute(select(tu.c.id).where(tu.c.username != ADMIN_LOGIN).order_by(tu.c.id)).first()[0]
        con.execute(tu.update().where(tu.c.id == uid).values(username=H2L))
        h2["user"] = uid
        bazada = (
            tuple(con.execute(select(ti.c.item_name, ti.c.unit, ti.c.image_url).where(ti.c.id == h2["inv"])).first()),
            con.execute(select(tp.c.project_name).where(tp.c.id == h2["prj"])).scalar(),
            con.execute(select(te.c.name).where(te.c.id == h2["emp"])).scalar(),
            con.execute(select(tu.c.username).where(tu.c.id == uid)).scalar(),
        )
    check("H2 qiymatlari bazada AYNAN (material nomi / birligi / rasmi, loyiha, hodim, login)",
          bazada == ((H2N, H2U, H2I), H2P, H2E, H2L), repr(bazada)[:300])

    # ─────────────────────────────────────────────────────────
    section("3. Lokal server + jsdom")
    node = shutil.which("node")
    check("node topildi", node is not None)
    if node is None:
        return
    try:
        npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:
        npm_root = ""
    env = dict(os.environ)
    env["NODE_PATH"] = os.pathsep.join(x for x in (os.environ.get("NODE_PATH", ""), npm_root,
                                                    os.path.join(ROOT, "node_modules")) if x)
    yordamchi_bolimi(node, env)
    import uvicorn
    port = bosh_port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port,
                                           log_level="critical", lifespan="off"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    check("uvicorn ishga tushdi", server.started)
    if not server.started:
        return
    base = f"http://127.0.0.1:{port}"
    try:
        import httpx
        lr = httpx.post(base + "/login", data={"username": ADMIN_LOGIN, "password": ADMIN_PAROL},
                        follow_redirects=False, timeout=30)
        cookie = "; ".join(h.split(";")[0] for h in lr.headers.get_list("set-cookie"))
        check("server login cookie olindi (session_token)", "session_token=" in cookie,
              f"{lr.status_code} {lr.text[:120]}")

        sahifalar = [{"path": "__nazorat__", "html": NAZORAT_HTML}]
        amallar = {
            "/reports": [f"switchReport('{t}')" for t in
                         ("inventory", "sales", "products", "masters", "finance", "production",
                          "top-products", "top-materials")],
            "/orders": [f"openProject({ids['p1']})", f"await loadOrderItems({ids['o1']})",
                        f"await loadDeliveries({ids['o1']})", f"await loadPayments({ids['o1']})",
                        f"await loadOrderAttachments({ids['o1']})",
                        # kech32 (E guruhi): server rad javobi / tekshiruv matnlarini ko'rsatadigan
                        # oynalar belgini HTML sifatida chizmasligi SHART (5-bo'lim yig'adi).
                        f"showStockShortageModal([{json.dumps(chr(39) + chr(34) + '><i class=xp901>')}], {{}}, false, 0, 'naqd')",
                        f"showValidationModal([{{text: {json.dumps(chr(39) + chr(34) + '><i class=xp902>')}, targetId: 'x'}}])",
                        f"showConfirmModal({json.dumps(chr(39) + chr(34) + '><i class=xp903>')})",
                        f"showPromptModal({json.dumps(chr(39) + chr(34) + '><i class=xp904>')}, "
                        f"{json.dumps(chr(39) + chr(34) + '><i class=xp905>')})"],
        }
        # 6-bo'lim: sahifa ichidagi mantiqiy tekshiruvlar (ifoda `true` qaytarishi SHART).
        # /reports: jadval ustunlari endi escapeHtml bilan qaytadi; saralash kaliti
        # (`extractSortValue`) belgi kodlarini ASL belgiga qaytarishi shart — aks holda
        # "Qo'shimcha" kabi nomlar "qo&#39;shimcha" bo'lib saralanadi. Namunadagi
        # "&lt;" yozuvi `&amp;` ni OXIRIDA ochish tartibini ham tekshiradi.
        saralash_namuna = "Qo'rg'oshin & <A> \"B\" &lt;"
        tekshiruvlar = {
            "/reports": [
                ("saralash kaliti escape qilingan matnni AYNAN tiklaydi (extractSortValue)",
                 f"const s = {json.dumps(saralash_namuna)}; "
                 "return extractSortValue('<span>' + escapeHtml(s) + '</span>').val === s.toLowerCase();"),
            ],
        }

        # kech32 — H2 tugmalari: `bos(tanlovchi, funksiya, ...kutilgan)` tugmani bosadi, funksiyani
        # vaqtincha almashtirib argumentlarini oladi; `kutilgan` — [argument indeksi, qiymat] juftlari.
        # Eski kodda: qiymat JS satridan chiqadi (`__h2*` paydo bo'ladi) yoki SyntaxError (argument yo'q).
        def bos(tanlovchi, fn, kutilgan):
            return (f"const el = {tanlovchi}; if (!el) return 'element topilmadi'; "
                    f"let got = null; const asl = window.{fn}; window.{fn} = (...a) => {{ got = a; }}; "
                    "for (const k of ['__h2n','__h2u','__h2i','__h2p','__h2e','__h2l']) delete window[k]; "
                    f"try {{ el.click(); }} finally {{ window.{fn} = asl; }} "
                    "const bajarildi = ['__h2n','__h2u','__h2i','__h2p','__h2e','__h2l'].filter(k => k in window); "
                    f"const K = {json.dumps(kutilgan)}; "
                    "const ok = !!got && !bajarildi.length && K.every(([i, v]) => got[i] === v); "
                    "return ok || JSON.stringify({got, bajarildi});")
        tekshiruvlar["/inventory"] = [
            ("H2: Chiqim tugmasi — nom va birlik AYNAN, kod bajarilmaydi",
             bos(f"document.querySelector('button[onclick*=\"openChiqimModal({h2['inv']},\"]')",
                 "openChiqimModal", [[0, h2["inv"]], [1, H2N], [2, H2U]])),
            ("H2: Chegara tugmasi — birlik AYNAN, kod bajarilmaydi",
             bos(f"document.querySelector('button[onclick*=\"editMinStock({h2['inv']},\"]')",
                 "editMinStock", [[0, h2["inv"]], [2, H2U]])),
            ("H2: rasm — lightbox manzili AYNAN, kod bajarilmaydi",
             bos(f"[...document.querySelectorAll('img[onclick*=\"openInvLightbox\"]')]"
                 f".find(i => i.getAttribute('src') === {json.dumps(H2I)})",
                 "openInvLightbox", [[0, H2I]])),
        ]
        tekshiruvlar["/users"] = [
            ("H2: Parol tugmasi — login AYNAN, kod bajarilmaydi",
             bos(f"document.querySelector('button[onclick*=\"changePass({h2['user']},\"]')",
                 "changePass", [[0, h2["user"]], [1, H2L]])),
        ]
        tekshiruvlar["/trash"] = [
            ("H2: loyihani butunlay o'chirish — nom AYNAN, kod bajarilmaydi",
             bos(f"document.querySelector('button[onclick*=\"permanentDelete(\\'project\\', {h2['prj']},\"]')",
                 "permanentDelete", [[0, "project"], [1, h2["prj"]], [2, f"{h2['prj_num']} — {H2P}"]])),
            ("H2: hodimni butunlay o'chirish — ism AYNAN, kod bajarilmaydi",
             bos(f"document.querySelector('button[onclick*=\"permanentDelete(\\'employee\\', {h2['emp']},\"]')",
                 "permanentDelete", [[0, "employee"], [1, h2["emp"]], [2, H2E]])),
        ]
        # DOM_SAHIFALAR=/reports,/dashboard — faqat shu sahifalar (nuqtali mutatsiya
        # ishlarini tezlatish uchun). Oddiy ishda (hammasi.sh) O'RNATILMAYDI.
        faqat = [x.strip() for x in os.environ.get("DOM_SAHIFALAR", "").split(",") if x.strip()]
        if faqat:
            info(f"DOM_SAHIFALAR filtri: faqat {faqat} — to'liq tekshiruv EMAS")
        for pth in SAHIFALAR + [f"/suppliers/receive?supplier_id={ids['sup']}"]:
            if faqat and pth.split("?")[0] not in faqat:
                continue
            sahifalar.append({"path": pth, "amallar": amallar.get(pth, []),
                              "tekshiruvlar": tekshiruvlar.get(pth, [])})
        pj = os.path.join(_TMP, "sahifalar.json")
        with open(pj, "w", encoding="utf-8") as fh:
            json.dump(sahifalar, fh, ensure_ascii=False)
        js = os.path.join(_TMP, "render.js")
        with open(js, "w", encoding="utf-8") as fh:
            fh.write(NODE_JS)
        t0 = time.time()
        k = subprocess.run([node, js, base, cookie, pj], capture_output=True, text=True,
                           timeout=800, env=env)
        info(f"jsdom: {time.time() - t0:.0f} s, rc={k.returncode}")
        natijalar = []
        fatal = None
        tugadi = False
        for q in k.stdout.splitlines():
            q = q.strip()
            if not q.startswith("{"):
                continue
            try:
                d = json.loads(q)
            except Exception:
                continue
            if "fatal" in d:
                fatal = d["fatal"]
            elif d.get("tugadi"):
                tugadi = True
            else:
                natijalar.append(d)
        check("jsdom yuklandi va barcha sahifalar ishlandi", fatal is None and tugadi,
              (fatal or "") + " " + k.stderr[-300:])

        def nomla(x):
            sinf, _, joy = x.partition(" @ ")
            n = sinf[2:]
            if n.isdigit() and int(n) < len(ustunlar):
                return ustunlar[int(n)] + " @ " + joy
            return sinf + " @ " + joy

        section("4. Ijobiy nazorat (qurilma ishlayaptimi)")
        naz = next((d for d in natijalar if d["page"] == "__nazorat__"), None)
        check("sun'iy xom innerHTML sahifasida belgi TOPILDI (matn + atribut, ≥ 2)",
              naz is not None and len(naz["topildi"]) >= 2,
              json.dumps(naz, ensure_ascii=False)[:300] if naz else "natija yo'q")

        section("5. Sahifalar: foydalanuvchi matni HTML sifatida chizilmasligi SHART (xpN tuguni = 0)")
        for d in natijalar:
            if d["page"] == "__nazorat__":
                continue
            check(f"{d['page']} → {d['status']} (200 shart)", d["status"] == 200,
                  "; ".join(d["xato"])[:200])
            if d["status"] != 200:
                continue
            if d["xato"]:
                info(f"{d['page']} skript xatolari ({len(d['xato'])}): " + " | ".join(d["xato"])[:300])
            if d["api_xato"]:
                info(f"{d['page']} API 5xx: " + " | ".join(d["api_xato"])[:300])
            topildi = [nomla(x) for x in d["topildi"]]
            check(f"{d['page']}: in'ektsiya yo'q (topildi {len(topildi)})", not topildi,
                  "\n       ↳ ".join(sorted(set(topildi)))[:5000])

        section("6. Sahifa ichidagi mantiqiy tekshiruvlar (escape boshqa xulqni buzmagan)")
        for pth, royxat in tekshiruvlar.items():
            if faqat and pth not in faqat:
                continue
            d = next((x for x in natijalar if x["page"] == pth), None)
            olingan = {t["nom"]: t for t in (d or {}).get("tekshiruv", [])}
            for nom, _ in royxat:
                t = olingan.get(nom)
                check(f"{pth}: {nom}", t is not None and t.get("ok") is True,
                      json.dumps(t, ensure_ascii=False)[:300] if t else "natija yo'q")
    finally:
        server.should_exit = True
        th.join(timeout=10)


if __name__ == "__main__":
    try:
        main_ish()
    except SystemExit:
        raise
    except BaseException:
        FAIL += 1
        print("  ❌ KUTILMAGAN ISTISNO:\n" + traceback.format_exc()[-2500:])
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
    sys.exit(0 if FAIL == 0 else 1)
