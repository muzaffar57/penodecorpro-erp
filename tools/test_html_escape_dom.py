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
import datetime
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
        # kech33: axlat qutisi (`/trash`) uchun ALOHIDA buyurtma. kech32 da
        # `/trash` da buyurtma umuman yo'q edi — `permanentDelete('order', ...)`
        # chaqiruv joyi hech qachon chizilmasdi (ET01 mutatsiyasi 0 chiqqandi).
        o3 = crud.create_order(db, schemas.OrderCreate(
            project_id=p2.id, order_type="product",
            items=[schemas.OrderItemCreate(name="DOM Detal 4 axlat", category="panel", width=100,
                                           thickness=10, length=100, quantity=2, unit_price=40000,
                                           is_coated=False)]),
            performed_by="DOM")
    ids = dict(inv_a=inv_a.id, inv_kam=inv_kam.id, pen=pen.id, rec=rec.id, p1=p1.id, p2=p2.id,
               emp=emp.id, o1=o1.id, o2=o2.id, o3=o3.id, sup=sup.id)
    o1_items = [it.id for it in db.query(models.OrderItem).filter(models.OrderItem.order_id == o1.id)
                .order_by(models.OrderItem.id).all()]
    # Yetkazish qoralama buyurtmaga yozilmaydi — ish holatiga o'tkazamiz
    for oid in (o1.id, o2.id, o3.id):
        o = db.get(models.Order, oid)
        if str(getattr(o.status, "value", o.status)) == "draft":
            o.status = models.OrderStatus.IN_PROGRESS
    db.commit()
    db.close()
    check("crud fikstura yaratildi (material, retsept, loyiha, hodim, 3 buyurtma, ta'minotchi)", True)

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
        # kech33: doimiy majburiyat — `/debts` da `company_obligations.recurring`
        # va `recurring_targets` bo'limlarini CHIZDIRADI (ED01 / ED02 chaqiruv
        # joylari). `icon` String(10) — belgi sig'maydi, u statik darvoza ishi.
        ("doimiy majburiyat", "post", "/api/obligations/recurring",
         ("params", {"category": "dom_ijara", "label": "DOM Ijara", "monthly_target": "500000",
                     "icon": "\U0001F3E0", "due_day": "5"})),
        # kech33: Kirim hujjati — `inventory_receipts` jadvali kech32 gacha
        # BO'SH edi (ombor kirim tarixi va ta'minotchi sahifasi chizilmasdi).
        ("kirim hujjati", "post", "/api/inventory/receipt",
         {"items": [{"inventory_id": ids["inv_a"], "quantity": 3, "price_per_unit": 1200,
                     "notes": "kirim qatori izohi"}],
          "supplier_id": ids["sup"], "document_number": "DOM-KIRIM-1", "paid_now": 1000,
          "transport_cost": 500, "tushirish_cost": 0, "yuklash_cost": 0, "boshqa_cost": 0,
          "add_to_cost": False, "notes": "kirim hujjati izohi", "production_type": "umumiy"}),
        # kech33: MRP mahsulot turi — BELGILASHDAN OLDIN yaratiladi, shunda
        # 2-bo'lim `product_types.name` / `description` ga belgi yozadi.
        ("MRP mahsulot turi", "post", "/api/production/product-types",
         {"name": "DOM Mahsulot turi", "unit": "metr", "input_template": "quantity_only",
          "pricing_formula": "unit_based"}),
    ]
    for nom, usul, url, tana in qadamlar:
        if isinstance(tana, tuple) and tana and tana[0] == "params":
            rr = getattr(c, usul)(url, params=tana[1])
        else:
            rr = getattr(c, usul)(url, json=tana)
        check(f"fikstura: {nom} → {rr.status_code}", 200 <= rr.status_code < 300, rr.text[:200])

    # ── kech33: id talab qiladigan qadamlar (halqadan keyin) ──────────
    # (a) Tayyor mahsulot SOTUVI — `/reports` "top-products" va
    #     "sales" jadvallarini to'ldiradi (kech30 B16: mutatsiya 0 chiqqandi,
    #     chunki sotuv yo'q edi). `confirm_below_cost` — tan narxi tekshiruvi
    #     fikstura narxlariga bog'liq bo'lmasligi uchun.
    fp_ro = c.get("/api/finished")
    fp_royxat = fp_ro.json() if fp_ro.status_code == 200 else []
    fp_id = next((x["id"] for x in fp_royxat if x.get("name") == "DOM Karniz"), None)
    check("fikstura: tayyor mahsulot ro'yxatda topildi", fp_id is not None,
          fp_ro.text[:200])
    if fp_id is not None:
        # Sotishdan oldin "Tayyor" deb belgilanadi (ishlab chiqarilayotgan
        # mahsulot sotilmaydi — `_FP_JARAYONDA_XABAR`).
        rc_ = c.post(f"/api/finished/{fp_id}/complete")
        check(f"fikstura: tayyor mahsulot 'Tayyor' → {rc_.status_code}",
              200 <= rc_.status_code < 300, rc_.text[:300])
        rs = c.post("/api/finished/sell", json={
            "finished_product_id": fp_id, "quantity": 1, "unit_price": 100000,
            "buyer_name": "DOM Xaridor", "payment_method": "naqd", "notes": "sotuv izohi",
            "confirm_below_cost": True})
        check(f"fikstura: tayyor mahsulot sotuvi → {rs.status_code}",
              200 <= rs.status_code < 300, rs.text[:300])

    # (b) Hodim AVANS SO'ROVI — `/dashboard` "kutilayotgan avans so'rovlari"
    #     oynasi (kech30 B24). Xodim login oqimi (`/api/hodim/advance-request`)
    #     alohida sessiya talab qiladi — ildiz funksiya to'g'ridan chaqiriladi.
    db = SessionLocal()
    try:
        req = crud.create_advance_request(db, ids["emp"], 150000,
                                          datetime.datetime(2026, 9, 10), "avans sababi")
        if hasattr(req, "company_id") and getattr(req, "company_id", None) is None:
            req.company_id = 1
            db.commit()
        check("fikstura: hodim avans so'rovi (kutilmoqda)", req is not None and req.id > 0)
    except Exception as e:
        db.rollback()
        check("fikstura: hodim avans so'rovi (kutilmoqda)", False, repr(e)[:200])
    finally:
        db.close()

    # (c) Axlat qutisiga BUYURTMA — `/trash` da `permanentDelete('order', ...)`
    #     tugmasi chizilishi uchun (ET01).
    #     O'LCHANGAN (kech33): `api_delete_order` da
    #     `should_soft_delete = has_delivery or status in (READY, DELIVERED)`.
    #     Yetkazishsiz buyurtma BUTUNLAY o'chadi va axlatga TUSHMAYDI —
    #     shuning uchun avval bitta yetkazish yoziladi.
    dbx = SessionLocal()
    o3_item_id = dbx.query(models.OrderItem.id).filter(
        models.OrderItem.order_id == ids["o3"]).order_by(models.OrderItem.id).scalar()
    dbx.close()
    rdlv = c.post("/api/deliveries", json={
        "order_id": ids["o3"], "items": [{"order_item_id": o3_item_id, "quantity": 1}],
        "notes": "axlat yetkazishi", "received_by": "Qabul", "transport_carrier": "Tashuvchi",
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd",
        "payment_amount": 0})
    check(f"fikstura: axlat buyurtmasiga yetkazish → {rdlv.status_code}",
          200 <= rdlv.status_code < 300, rdlv.text[:300])
    rd = c.delete(f"/api/orders/{ids['o3']}")
    check(f"fikstura: buyurtma axlatga (soft delete) → {rd.status_code}",
          200 <= rd.status_code < 300, rd.text[:300])
    dbx = SessionLocal()
    o3_bor = dbx.query(models.Order).filter(models.Order.id == ids["o3"],
                                            models.Order.is_deleted.is_(True)).count()
    dbx.close()
    check("fikstura: buyurtma AXLATDA (is_deleted=True, butunlay o'chmagan)", o3_bor == 1,
          f"topildi={o3_bor}")

    # (d) Tayyor mahsulot YO'QOTISHI (`finished_product_losses`) — `/finished`
    #     sahifasidagi yo'qotish tarixi.
    if fp_id is not None:
        rl = c.post("/api/finished/loss", json={
            "finished_product_id": fp_id, "quantity": 1, "reason": "yo'qotish sababi"})
        check(f"fikstura: tayyor mahsulot yo'qotishi → {rl.status_code}",
              200 <= rl.status_code < 300, rl.text[:300])

    # (e) MRP retsepti (BOM) — mahsulot turi id si kerak, shuning uchun
    #     halqadan keyin. BELGILASHDAN OLDIN yaratiladi (2-bo'lim
    #     `boms.variant_name` / `bom_items.notes` ga belgi yozadi).
    rpt = c.get("/api/production/product-types")
    pt_royxat = rpt.json() if rpt.status_code == 200 else []
    pt_id = next((x["id"] for x in pt_royxat if x.get("name") == "DOM Mahsulot turi"), None)
    check("fikstura: MRP mahsulot turi ro'yxatda topildi", pt_id is not None, rpt.text[:200])
    ids["pt"] = pt_id
    ids["bom"] = None
    if pt_id is not None:
        rb = c.post("/api/production/boms", json={
            "product_type_id": pt_id, "variant_name": "DOM BOM varianti", "batch_quantity": 1,
            "notes": "BOM izohi",
            "items": [{"inventory_id": ids["inv_a"], "quantity": 1, "scrap_factor_percent": 0,
                       "is_optional": False, "is_coating": False,
                       "component_type": "raw_material", "notes": "BOM qatori izohi"}]})
        check(f"fikstura: MRP retsepti (BOM) → {rb.status_code}",
              200 <= rb.status_code < 300, rb.text[:300])
        if 200 <= rb.status_code < 300:
            ids["bom"] = rb.json().get("id")

    # (f) Kunlik / oylik xarajat (`monthly_expenses`) va buyurtma ILOVASI
    #     (`order_attachments`) — ikkalasi ham ildiz modeli orqali (birinchisi
    #     faqat sahifa formasi bilan yoziladi, ikkinchisi HAQIQIY fayl yuklashni
    #     talab qiladi; bu yerda kerakligi — CHIZILADIGAN matn ustunlari).
    db = SessionLocal()
    try:
        me_cls = next((m.class_ for m in Base.registry.mappers
                       if getattr(m.class_, "__tablename__", "") == "monthly_expenses"), None)
        if me_cls is not None:
            db.add(me_cls(company_id=1, year=2026, month=9, hodim1_ism="DOM Hodim 1",
                          notes="kunlik xarajat izohi"))
        oa_cls = next((m.class_ for m in Base.registry.mappers
                       if getattr(m.class_, "__tablename__", "") == "order_attachments"), None)
        if oa_cls is not None:
            db.add(oa_cls(order_id=ids["o1"], file_url="/static/uploads/dom_ilova.pdf",
                          file_name="DOM ilova.pdf", uploaded_by="DOM"))
        db.commit()
        check("fikstura: kunlik xarajat va buyurtma ilovasi yozuvlari",
              me_cls is not None and oa_cls is not None,
              f"monthly_expenses={me_cls is not None} order_attachments={oa_cls is not None}")
    except Exception as e:
        db.rollback()
        check("fikstura: kunlik xarajat va buyurtma ilovasi yozuvlari", False, repr(e)[:250])
    finally:
        db.close()

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
    # kech33 — uch sahifa rasmi (`onclick="open…Lightbox('{{ x }}')"` naqshi
    # `data-src` ga o'tkazilgan; eski kodda `'` JS satridan chiqardi).
    H2IJ = "/static/j');__h2j=1;//\"&amp;.png"
    H2IC = "/static/c');__h2c=1;//\"&amp;.png"
    H2IR = "/static/r');__h2r=1;//\"&amp;.png"
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
        # kech33: loyiha / retsept / qaytarish rasmlari. Loyiha — KO'RINADIGAN
        # p2 (p_h2 o'chirilgan, u `/trash` da). Qaytarish qatori fiksturada
        # bitta — eng kichik id.
        tj = Base.metadata.tables["projects"]
        tc_ = Base.metadata.tables["recipes"]
        tr_ = Base.metadata.tables["return_items"]
        con.execute(tj.update().where(tj.c.id == ids["p2"]).values(image_url=H2IJ))
        con.execute(tc_.update().where(tc_.c.id == ids["rec"]).values(image_url=H2IC))
        ret_id = con.execute(select(tr_.c.id).order_by(tr_.c.id)).first()
        h2["ret"] = ret_id[0] if ret_id else None
        if h2["ret"] is not None:
            con.execute(tr_.update().where(tr_.c.id == h2["ret"]).values(image_url=H2IR))
        # MRP "Batafsil" tugmasi snapshotda BELGILANGAN material nomini
        # tashiydi — kutilgan qiymat shu yerda o'qiladi (belgi raqami oldindan
        # ma'lum emas).
        h2["inv_a_nom"] = con.execute(
            select(ti.c.item_name).where(ti.c.id == ids["inv_a"])).scalar()
        h2["rasmlar"] = (
            con.execute(select(tj.c.image_url).where(tj.c.id == ids["p2"])).scalar(),
            con.execute(select(tc_.c.image_url).where(tc_.c.id == ids["rec"])).scalar(),
            (con.execute(select(tr_.c.image_url).where(tr_.c.id == h2["ret"])).scalar()
             if h2["ret"] is not None else None),
        )
        bazada = (
            tuple(con.execute(select(ti.c.item_name, ti.c.unit, ti.c.image_url).where(ti.c.id == h2["inv"])).first()),
            con.execute(select(tp.c.project_name).where(tp.c.id == h2["prj"])).scalar(),
            con.execute(select(te.c.name).where(te.c.id == h2["emp"])).scalar(),
            con.execute(select(tu.c.username).where(tu.c.id == uid)).scalar(),
        )
    check("H2 qiymatlari bazada AYNAN (material nomi / birligi / rasmi, loyiha, hodim, login)",
          bazada == ((H2N, H2U, H2I), H2P, H2E, H2L), repr(bazada)[:300])
    check("H2 rasm manzillari bazada AYNAN (loyiha / retsept / qaytarish)",
          h2["rasmlar"] == (H2IJ, H2IC, H2IR), repr(h2["rasmlar"])[:300])

    # ── kech33: ishlab chiqarish BUYURTMASI — belgilashdan KEYIN ───────
    # `recipe_snapshot_json` `start` paytida tuziladi va material NOMINI
    # ichiga oladi. Shu sababli buyurtma 2-bo'limdan KEYIN yaratiladi:
    # snapshot BELGILANGAN nomni oladi va `production.html` "Batafsil"
    # tugmasi (`data-snap`) uni JSON sifatida tashiydi. kech32 da bu jadval
    # bo'sh edi — EP00 mutatsiyasi 0 chiqqandi.
    ids["po"] = None
    if ids.get("pt") and ids.get("bom"):
        rpo = c.post("/api/production/orders", json={
            "product_type_id": ids["pt"], "bom_id": ids["bom"], "quantity": 2,
            "source_type": "warehouse_stock", "notes": "MRP buyurtma izohi"})
        check(f"fikstura: MRP ishlab chiqarish buyurtmasi → {rpo.status_code}",
              200 <= rpo.status_code < 300, rpo.text[:300])
        if 200 <= rpo.status_code < 300:
            ids["po"] = (rpo.json().get("production_order") or {}).get("id")
        if ids["po"]:
            rst = c.post(f"/api/production/orders/{ids['po']}/start")
            check(f"fikstura: MRP buyurtmasi boshlandi → {rst.status_code}",
                  200 <= rst.status_code < 300, rst.text[:300])
            rcm = c.post(f"/api/production/orders/{ids['po']}/complete")
            check(f"fikstura: MRP buyurtmasi yakunlandi → {rcm.status_code}",
                  200 <= rcm.status_code < 300, rcm.text[:300])

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
            # kech33: `#po-list` sahifa yuklanganda "Yuklanmoqda..." holicha
            # qoladi — `loadProductionOrders()` FAQAT "Buyurtmalar" yorlig'i
            # bosilganda chaqiriladi (O'LCHANGAN).
            "/production": ["await loadProductionOrders()"],
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
                        f"{json.dumps(chr(39) + chr(34) + '><i class=xp905>')})",
                        # kech33 (EO00 / EO01 / EOP): tayyor mahsulot taklifi.
                        # `.detal` qatori sahifada YO'Q — u `addItem()` bilan
                        # yaratiladi (O'LCHANGAN). Qidiruv so'zi "DOM" emas:
                        # 2-bo'lim tayyor mahsulot NOMINI belgi bilan
                        # almashtirgan, nomda "xp" bor. `searchFinished`
                        # kechiktirilgan (250 ms) — natijani kutamiz.
                        "addItem(); const inp = document.querySelector('.detal .i-name'); "
                        "if (inp) { inp.value = 'xp'; searchFinished(inp); "
                        "await new Promise(r => setTimeout(r, 1400)); }",
                        # kech33 (EO22–EO27): "Tayyor" natijasi. `openPdfSafe`
                        # jsdom da PDF ocha olmaydi — vaqtincha bo'sh funksiya
                        # (tekshirilayotgan narsa natija MATNINI chizish).
                        f"window.openPdfSafe = () => {{}}; selectedOrderId = {ids['o2']}; "
                        "await submitReadyModal();"],
        }
        # 6-bo'lim: sahifa ichidagi mantiqiy tekshiruvlar (ifoda `true` qaytarishi SHART).
        # /reports: jadval ustunlari endi escapeHtml bilan qaytadi; saralash kaliti
        # (`extractSortValue`) belgi kodlarini ASL belgiga qaytarishi shart — aks holda
        # "Qo'shimcha" kabi nomlar "qo&#39;shimcha" bo'lib saralanadi. Namunadagi
        # "&lt;" yozuvi `&amp;` ni OXIRIDA ochish tartibini ham tekshiradi.
        # kech33: `/trash` va `/debts` tekshiruvlari uchun kutilgan qiymatlar —
        # 2-bo'lim belgilaganidan KEYINGI HAQIQIY baza qiymatlari.
        with engine.begin() as con:
            t_ord = Base.metadata.tables["orders"]
            t_obl = Base.metadata.tables["recurring_obligations"]
            t_emp = Base.metadata.tables["employees"]
            o3_raqam = con.execute(
                select(t_ord.c.order_number).where(t_ord.c.id == ids["o3"])).scalar()
            # DIQQAT: `category` ustuni ham 2-bo'limda BELGILANGAN, shuning
            # uchun "dom_ijara" bo'yicha qidirib bo'lmaydi (kech33 da
            # o'lchangan) — birinchi (yagona) qator o'qiladi.
            _obl = con.execute(select(t_obl.c.category, t_obl.c.label)
                               .order_by(t_obl.c.id)).first()
            oblig_kod = _obl[0] if _obl else None
            oblig_nom = _obl[1] if _obl else None
            hodim_nom = con.execute(
                select(t_emp.c.name).where(t_emp.c.id == ids["emp"])).scalar()
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
        # kech33: `kutilgan` elementi [indeks, qiymat] yoki [yo'l, qiymat] —
        # yo'l JS ifodasi (masalan "[0][0].item_name"), chunki MRP "Batafsil"
        # tugmasi birinchi argument sifatida MASSIV uzatadi. Taqqoslash
        # avval `===`, so'ng JSON bilan (obyekt / massiv uchun).
        H2_GLOBALLAR = ["__h2n", "__h2u", "__h2i", "__h2p", "__h2e", "__h2l",
                        "__h2j", "__h2c", "__h2r", "__h2s", "__h2t"]

        def bos(tanlovchi, fn, kutilgan):
            g = json.dumps(H2_GLOBALLAR)
            return (f"const el = {tanlovchi}; if (!el) return 'element topilmadi'; "
                    f"let got = null; const asl = window.{fn}; window.{fn} = (...a) => {{ got = a; }}; "
                    f"for (const k of {g}) delete window[k]; "
                    f"try {{ el.click(); }} finally {{ window.{fn} = asl; }} "
                    f"const bajarildi = {g}.filter(k => k in window); "
                    f"const K = {json.dumps(kutilgan)}; "
                    "const ok = !!got && !bajarildi.length && K.every(([i, v]) => { "
                    "const x = (typeof i === 'number') ? got[i] "
                    ": (new Function('got', 'return got' + i))(got); "
                    "return x === v || JSON.stringify(x) === JSON.stringify(v); }); "
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
        # kech33 (EOP): taklif elementidagi `data-fp` JSON — `pickFinished`
        # uni AYNAN o'qishi shart. Eski kodda `'` → `&apos;` almashtirilar va
        # `&apos;` MATNLI nom buzilardi.
        tekshiruvlar["/orders"] = [
            ("EOP: tayyor mahsulot taklifi — data-fp JSON AYNAN o'qiladi",
             "const el = document.querySelector('.fp-sg-item[data-fp]'); "
             "if (!el) return 'taklif elementi topilmadi'; "
             "let fp; try { fp = JSON.parse(el.dataset.fp); } catch (e) { return 'JSON xato: ' + e.message; } "
             "const r = await fetch('/api/finished/search?q=' + encodeURIComponent('xp')); "
             "const d = await r.json(); "
             "const asl = (d.items || []).find(x => x.id === fp.id); "
             "return !!asl && asl.name === fp.name && asl.unit === fp.unit;"),
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
            # kech33 (ET01): axlatdagi BUYURTMA. `order_number` — server
            # generatori, lekin chaqiruv joyi shu tekshiruvsiz umuman
            # ishlamasdi (kech32 da axlatda buyurtma yo'q edi).
            ("H2: buyurtmani butunlay o'chirish — raqam AYNAN, kod bajarilmaydi",
             bos(f"document.querySelector('button[onclick*=\"permanentDelete(\\'order\\', {ids['o3']},\"]')",
                 "permanentDelete", [[0, "order"], [1, ids["o3"]], ["[2]", o3_raqam]])),
        ]
        # kech33 (EP00): MRP "Batafsil" — `data-snap` JSON massivini tashiydi.
        # Eski kodda `onclick='showSnapshot(${JSON.stringify(...)}, ...)'` edi:
        # material nomidagi bitta `'` butun tugmani BUZARDI.
        tekshiruvlar["/production"] = [
            ("EP00: Batafsil — snapshot massivi va holat AYNAN, kod bajarilmaydi",
             bos("document.querySelector('#po-list button[onclick*=\"showSnapshot\"]')",
                 "showSnapshot",
                 [["[0][0].item_name", h2["inv_a_nom"]], [1, "completed"]])),
        ]
        # kech33 (EJ00 / EC00 / ER02): uch sahifa rasmi — lightbox manzili.
        tekshiruvlar["/projects"] = [
            ("H2: loyiha rasmi — manzil AYNAN, kod bajarilmaydi",
             bos(f"[...document.querySelectorAll('img[onclick*=\"openProjLightbox\"]')]"
                 f".find(i => i.getAttribute('src') === {json.dumps(H2IJ)})",
                 "openProjLightbox", [[0, H2IJ]])),
        ]
        tekshiruvlar["/recipes"] = [
            ("H2: retsept rasmi — manzil AYNAN, kod bajarilmaydi",
             bos(f"[...document.querySelectorAll('img[onclick*=\"openRecLightbox\"]')]"
                 f".find(i => i.getAttribute('src') === {json.dumps(H2IC)})",
                 "openRecLightbox", [[0, H2IC]])),
        ]
        tekshiruvlar["/returns"] = [
            ("H2: qaytarish rasmi — manzil AYNAN, kod bajarilmaydi",
             bos(f"[...document.querySelectorAll('img[onclick*=\"openReturnLightbox\"]')]"
                 f".find(i => i.getAttribute('src') === {json.dumps(H2IR)})",
                 "openReturnLightbox", [[0, H2IR]])),
        ]
        # kech33 (ED00–ED02): qarzlar sahifasi — majburiyat / kategoriya /
        # hodim qatorlari. `|replace('"', '&quot;')` olib tashlangan; agar u
        # qaytsa, dataset da `&quot;` MATNI qolib, qiymat BUZILADI.
        tekshiruvlar["/debts"] = [
            ("ED01: majburiyat qatori — kategoriya va nom AYNAN",
             bos("document.querySelector('.oblig-item[onclick*=\"openObligTimeline\"]')",
                 "openObligTimeline", [["[0]", oblig_kod], ["[1]", oblig_nom]])),
            ("ED02: kategoriya chipi — nom AYNAN",
             bos("document.querySelector('span[onclick*=\"deleteCategory\"]')",
                 "deleteCategory", [["[1]", oblig_nom]])),
            ("ED00: hodim qarzi qatori — ism AYNAN",
             bos("document.querySelector('.oblig-item[onclick*=\"openEmpTimeline\"]')",
                 "openEmpTimeline", [["[1]", hodim_nom]])),
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
