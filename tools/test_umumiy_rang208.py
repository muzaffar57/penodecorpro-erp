#!/usr/bin/env python3
"""
test_umumiy_rang208.py — kech155 (zip 208 «Umumiy rang — Toza ko'k»; EGASI 23.10: «2 oy ishlatib bildimki, rang tanlashda o'zim xato qilgan
ekanman — dasturning umumiy rangi juda bo'g'iq, charchatadi»; 3 prototip haqiqiy sahifalarda → TANLOVI «B · Toza ko'k»: oq menyu, ko'k
aksent, och ko'kish fon).

NIMA UCHUN KERAK: rang 60+ joyda xom (#B9783F, #9A6231, #8F5B2A, #A86B36, rgba(185,120,63,…)), 40+ iliq belgi (`--f-fdf8f0`, `--ch-d9b48c`,
`--m-8f5b2a` …), sahifa ichki palitralari (Moliya, Hisobotlar, Qarzdorlar, Kirim), kirish sahifasi — bittasi qolib ketsa, o'sha joy eski
oltin / qum bo'lib qoladi. Bu test HAQIQIY brauzerda har sahifaning HAR elementining hisoblangan rangini (matn, fon, chegara, soya)
eski oltin oilasi bilan solishtiradi.
BO'LIMLAR:
  S — manba: umumiy belgilar (yorug' / tungi), menyu belgilari, kesh belgisi, eski palitraning xom rangi yo'q (ruxsat etilganlar: «Bazalt»
      toifasi, `matnRangi` / `_TUNGI_GRAFIK` jadvallari, izohlar), iliq belgilar ro'yxatdan olingan (rang tusi bo'yicha), sahifa palitralari,
      kirish sahifasi, PDF ranglari o'sha; mustaqil tekshiruv (`work/k208/review208/HISOBOT.md`) topilmalari: tanlangan chip chegarasi,
      tungi grafik ko'k ustuni, qizil qarz summalari / «Chiqish», murojaat belgisi.
  D — HAQIQIY Chromium (Playwright) + lokal server, ma'lumot API orqali: 18 sahifa yorug' va tungi rejimda — hech bir elementda eski oltin
      rang yo'q; sahifa foni, menyu (oq / qorong'i), faol menyu bandi (≥ 4,5:1), oltin tugma o'rnida ko'k (oq yozuv ≥ 4,5:1), menyu belgisi /
      sonlari, aksent (ko'k) rangdagi HAR yozuv o'z fonida ≥ 4,5:1, tanlangan filtr chegarasi ≥ 3:1, kirish sahifasi; telefon 390 px —
      toshmaydi; JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. Asl kodga (zip 207) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_umumiy_rang208.py
"""
import os
import io
import re
import sys
import glob
import time
import socket
import tempfile
import datetime
import threading
import contextlib
import colorsys

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k208_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k208.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "PG_URL"):
    os.environ.pop(_k, None)

YORLIQ = "[TF1] " if TF else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


def rgb(s):
    m = re.findall(r"[\d.]+", s or "")
    return tuple(float(x) for x in m[:3]) if len(m) >= 3 else None


def _lum(c):
    def k(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2])


def kontrast(a, b):
    if not a or not b:
        return 0
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(float(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def oqi(yol):
    return open(os.path.join(ROOT, yol), encoding="utf-8").read()


# eski OLTIN oilasi (yorug' va tungi): aksent, matn, tugma, och fon, tungi matn / och fon, kirish sahifasi, iliq chegaralar / fonlar
ESKI_OLTIN = ["#B9783F", "#9A6231", "#8F5B2A", "#A86B36", "#D09A63", "#F8F2EB", "#2E2418", "#C9793A", "#A85F27", "#FBF0E6", "#FDF8F0",
              "#D9B48C", "#E8D5C0", "#E3C9A8", "#F3EEE0", "#EDE6D8", "#E5DFD3", "#F0E6D2", "#EADFC9", "#F1DDBA", "#F3E4CC", "#7A4D23",
              "#E8E3DD", "#F0ECE6", "#F8F8F6", "#CFC5B8", "#FAF7F2", "#FBF7F0", "#FAF8F5", "#F5F3EF"]
ESKI_RGB = {hexrgb(h): h for h in ESKI_OLTIN}

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ST = oqi("static/style.css")
RC = oqi("static/ranglar.css")


def blok(css, bosh):
    i = css.find(bosh)
    if i < 0:
        return {}
    return {k: v.upper() for k, v in re.findall(r"--([\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})\s*;", css[i:css.find("}", i)])}


YB, TB = blok(ST, ":root {"), blok(ST, 'html[data-theme="dark"] {')
check("S1 umumiy belgilar (yorug'): aksent ko'k (--gold #2563EB, --gold-dark #1D4ED8, --gold-btn #2563EB, --gold-tint #EEF4FF), fon #F4F6FA, "
      "chegaralar sovuq (#E2E7EF / #EDF0F5), matn #1A1F2B / #4A5366 / #5B6476",
      {k: YB.get(k) for k in ("gold", "gold-dark", "gold-btn", "gold-tint", "gold-hover", "bg", "border", "border2", "text", "text2", "text3")}
      == {"gold": "#2563EB", "gold-dark": "#1D4ED8", "gold-btn": "#2563EB", "gold-tint": "#EEF4FF", "gold-hover": "#1D4ED8", "bg": "#F4F6FA",
          "border": "#E2E7EF", "border2": "#EDF0F5", "text": "#1A1F2B", "text2": "#4A5366", "text3": "#5B6476"}, YB)
check("S2 umumiy belgilar (tungi): ko'k aksent (--gold #3B82F6, matn #93B4F5, och fon #1A2741), qorong'i menyu",
      TB.get("gold") == "#3B82F6" and TB.get("gold-dark") == "#93B4F5" and TB.get("gold-tint") == "#1A2741" and TB.get("menu-fon") == "#181B22"
      and TB.get("menu-faol-matn") == "#93B4F5", TB)
_menyu = ST[ST.find(".sidebar {"):ST.find(".s-bottom {") + 200]
check("S3 menyu — `--menu-*` belgilaridan (yorug' — oq #FFFFFF, faol bandi #EEF4FF / #1D4ED8); menyu qoidalarida xom rang / --dark yo'q",
      YB.get("menu-fon") == "#FFFFFF" and YB.get("menu-faol-fon") == "#EEF4FF" and YB.get("menu-faol-matn") == "#1D4ED8"
      and "background: var(--menu-fon);" in _menyu and "var(--dark)" not in _menyu.replace("color: var(--dark);", "")
      and "#E5E5E0" not in _menyu and "rgba(185,120,63" not in _menyu, _menyu[:300])
_kesh = re.search(r'templates\.env\.globals\["static_version"\] = "([^"]+)"', oqi("main.py"))
check("S4 kesh belgisi yangilangan (brauzer eski style.css / ranglar.css ni ushlab qolmasin): «20261023-1»",
      _kesh and _kesh.group(1) == "20261023-1", _kesh and _kesh.group(1))
_xom = []
for _f in sorted(glob.glob(os.path.join(ROOT, "templates", "*.html"))) + [os.path.join(ROOT, "static", "style.css")]:
    _s = open(_f, encoding="utf-8").read()
    if _f.endswith("base.html"):     # `matnRangi`, `_TUNGI_GRAFIK` — eski / boshqa ranglarni TANIYDIGAN (kalit) jadvallar
        _s = _s[:_s.index("function matnRangi(")] + _s[_s.index("function birlikKor("):]
        _s = _s[:_s.index("const _TUNGI_GRAFIK")] + _s[_s.index("function _tungimi("):]
    _s = re.sub(r"(?<![\w\"'=])/\*.*?\*/", "", _s, flags=re.S)                # CSS izohlari (`accept="image/*"` — izoh EMAS)
    _s = re.sub(r"\{#.*?#\}", "", _s, flags=re.S)                              # Jinja izohlari
    _s = re.sub(r"<!--.*?-->", "", _s, flags=re.S)                              # HTML izohlari
    _s = re.sub(r"(?m)(^|\s)//.*$", "", _s)                                     # JS izohlari
    for _n, _q in enumerate(_s.split("\n"), 1):
        if '"Bazalt":' in _q:                                                    # «Bazalt» toifasi — tosh rangi (jigarrang), ma'noli
            continue
        for _m in re.finditer(r"(" + "|".join(ESKI_OLTIN) + r")\b|rgba\((185, ?120, ?63|201, ?121, ?58)\b", _q, re.I):
            _xom.append(f"{os.path.basename(_f)}: {_q.strip()[:140]}")
check("S5 shablonlar va style.css da eski palitraning xom rangi yo'q (oltin, qum, iliq kulrang — 30 ta; grafiklar ham; ruxsat: «Bazalt» "
      "toifasi rangi, `matnRangi` / `_TUNGI_GRAFIK` jadvallari, izohlar)", not _xom, _xom[:8])
_rc_root = RC[RC.index(":root"):RC.index("}", RC.index(":root"))]
_RUXSAT_ILIQ = {"f-f3e8d8", "m-a86b36",        # «Bazalt» toifasi (tosh rangi) — ma'noli
                "m-78350f",                    # ogohlantirish (to'q sariq) matni — ma'noli
                "doim-eceae6"}                 # tungi rejimdagi `.btn-dark` foni (och kulrang)
_yoq = []
for _k, _v in re.findall(r"--((?:f|m|ch|doim)-[0-9a-f]{6})\s*:\s*(#[0-9A-Fa-f]{6})", _rc_root):
    _h, _l, _st = colorsys.rgb_to_hls(*[int(_v[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    if 15 <= _h * 360 <= 50 and 0.12 <= _st <= 0.78 and _k not in _RUXSAT_ILIQ:     # oltin / qum / jigarrang / iliq kulrang oilasi
        _yoq.append(f"{_k} {_v}")
check("S6 umumiy ranglar ro'yxatida iliq (oltin / qum / jigarrang / iliq kulrang) belgi QOLMAGAN (ruxsat: «Bazalt», to'q sariq "
      "ogohlantirish, tungi `.btn-dark`); shablonlarda — ko'k / sovuq teng kuchlilari", not _yoq, _yoq)
_pal = {f: oqi(f"templates/{f}") for f in ("finance.html", "reports.html", "debts.html", "supplier_receive.html", "login.html")}
check("S7 sahifa ichki palitralari: Moliya / Hisobotlar / Qarzdorlar / Kirim — ko'k (#2563EB, och #EEF4FF, tungi #93B4F5), kirish sahifasi — "
      "#3B82F6",
      "--f-primary:#2563EB; --f-primary-tint:#EEF4FF;" in _pal["finance.html"] and "--f-primary:#93B4F5;" in _pal["finance.html"]
      and "--b-primary:#2563EB; --b-primary-tint:#EEF4FF;" in _pal["reports.html"] and "--b-primary:#93B4F5;" in _pal["reports.html"]
      and "--d-primary:#2563EB;" in _pal["debts.html"] and "--d-primary:#93B4F5;" in _pal["debts.html"]
      and "--r-primary:#2563EB;" in _pal["supplier_receive.html"] and "--r-primary:#93B4F5;" in _pal["supplier_receive.html"]
      and "--amber:#3B82F6;" in _pal["login.html"])
_pdf = {f: oqi(f) for f in ("pdf_service.py", "delivery_pdf.py")}
check("S8 PDF hujjatlar o'zgarmagan (chop etiladigan hujjat — o'z ranglari: oltin #C9A55A, qorong'i #1A252F; egasiga aytildi)",
      'GOLD = colors.HexColor("#C9A55A")' in _pdf["delivery_pdf.py"] and 'GOLD   = colors.HexColor("#C9A55A")' in _pdf["pdf_service.py"])
# mustaqil tekshiruv (`work/k208/review208/HISOBOT.md`) topilmalari — statik qismi
_fin = oqi("templates/finished.html")
check("S9 tanlangan chip / filtr chegarasi — aksent (`--gold`; och `--ch-bfdbfe` tanlanmagandan 1,14:1 farq qilardi): `.chip.active`, "
      "`.fp-chip.on`, `.fp-cat-opt.active`",
      '.chip.active, .chip[aria-pressed="true"] { background: var(--gold-tint); border-color: var(--gold); color: var(--gold-dark); }' in ST
      and ".fp-chip.on{background:var(--gold-tint);border-color:var(--gold);color:var(--gold-dark)}" in _fin
      and ".fp-cat-opt.active{background:var(--gold-tint);border-color:var(--gold);color:var(--gold-dark)}" in _fin)
_bs = oqi("templates/base.html")
_tg_map = _bs[_bs.index("const _TUNGI_GRAFIK"):_bs.index("function _tungimi(")]
check("S10 tungi rejimda grafikning ko'k ustuni (#2563EB — qorong'i kartada 3,1:1) yorqinroq #3B82F6 ga almashadi (`_TUNGI_GRAFIK`)",
      "'#2563eb': '#3B82F6'" in _tg_map and kontrast(hexrgb("#3B82F6"), hexrgb("#1E212A")) >= 4, _tg_map[:300])
_qz = {"orders.html": '<span id="pay-debt" style="font-weight:800;color:var(--m-b91c1c)">',
       "supplier_receive.html": '<div class="rcv-stat-value" style="color:var(--m-b91c1c)" id="sup-debt">',
       "suppliers.html": '<span style="color:var(--m-b91c1c)" id="hist-debt">',
       "kpi.html": '<div style="font-weight:700;color:var(--m-b91c1c)">${(() => { const k = list.reduce((s,e)=>s+(e.adjustment||0),0);'}
check("S11 och ko'kish fonda qizil yozuv ≥ 4,5:1: qarz summalari (`#pay-debt`, `#sup-debt`, `#hist-debt`, KPI «Kamaytirish jami») va "
      "«Chiqish» ustiga kelinganda — `--m-b91c1c` (#DC2626 / #EF4444 — 4,44 / 3,41); murojaat «Yangi javob» — `--gold-btn` + oq yozuv",
      all(v in oqi("templates/" + f) for f, v in _qz.items())
      and ".s-logout:hover { background: var(--menu-hover); color: var(--m-b91c1c); }" in ST
      and ".mj-yangi-javob{background:var(--gold-btn);color:#fff}" in oqi("templates/murojaat.html")
      and min(kontrast(hexrgb("#B91C1C"), hexrgb(x)) for x in ("#F4F6FA", "#EFF6FF", "#F1F4F9", "#FFFFFF")) >= 4.5,
      [f for f, v in _qz.items() if v not in oqi("templates/" + f)])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# tayyorgarlik — ma'lumot API orqali
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k208_a", PAROL, UserRole.ADMIN, "K208 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K208 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P1 = Project(company_id=1, client_name="Sardor K208", project_name="Andijon kottej K208", client_phone="+998901112208", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K208 Usta", phone="+998900002080")
s.add_all([PENO, P1, US])
s.commit()
ID = {"PENO": PENO.id, "P1": P1.id, "US": US.id}
s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lg = C.post("/login", data={"username": "k208_a", "password": PAROL}, follow_redirects=False)
TK = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).date()


def buyurtma(muddat, miqdor, narx):
    tana = {"project_id": ID["P1"], "order_type": "product", "recipe_id": None, "master_id": ID["US"], "deadline": muddat, "is_draft": False,
            "base_price": 600000, "loy_kg": None,
            "items": [{"name": "K208 panel", "category": "panel", "width": 60, "thickness": 5, "length": 0, "quantity": miqdor,
                       "unit_price": narx, "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}]}
    r = C.post("/api/orders?confirm_shortage=true", json=tana)
    return (r.json() or {}).get("id") if r.status_code == 200 else None


O1 = buyurtma((TK - datetime.timedelta(days=3)).isoformat(), 20, 22000)
O2 = buyurtma((TK + datetime.timedelta(days=4)).isoformat(), 10, 15000)
_am = [C.post("/api/payments", json={"order_id": O1, "amount": 100000, "payment_type": "zaklat", "payment_method": "naqd"}).status_code] if O1 else []
check("T0 fikstura: kirish, 2 buyurtma, to'lov — 200", _lg.status_code in (302, 303) and O1 and O2 and _am == [200], (O1, O2, _am))

import uvicorn                                     # noqa: E402
so = socket.socket()
so.bind(("127.0.0.1", 0))
port = so.getsockname()[1]
so.close()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
BU = f"http://127.0.0.1:{port}"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PW_BOR = True
try:
    from playwright.sync_api import sync_playwright
except Exception:                          # noqa: BLE001
    PW_BOR = False
check("D0 Python `playwright` bor", PW_BOR)

SKAN = r"""(eski) => {
  const E = new Set(eski);
  const toHex = (s) => { const m = (s || '').match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/); if (!m) return null;
    if (m[4] !== undefined && parseFloat(m[4]) === 0) return null;
    return '#' + [m[1], m[2], m[3]].map(x => Math.round(+x).toString(16).padStart(2, '0')).join('').toUpperCase(); };
  const topildi = [];
  const els = [document.documentElement, ...document.querySelectorAll('body, body *')];
  for (const el of els) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (el !== document.documentElement && el.tagName !== 'BODY' && (r.width === 0 || r.height === 0)) continue;
    const props = [['color', cs.color], ['background', cs.backgroundColor], ['border-top', cs.borderTopWidth !== '0px' && cs.borderTopStyle !== 'none' ? cs.borderTopColor : null],
      ['border-left', cs.borderLeftWidth !== '0px' && cs.borderLeftStyle !== 'none' ? cs.borderLeftColor : null], ['outline', cs.outlineStyle !== 'none' ? cs.outlineColor : null]];
    for (const [p, v] of props) { const h = toHex(v); if (h && E.has(h)) topildi.push(`${el.tagName.toLowerCase()}.${(el.className && el.className.baseVal === undefined ? el.className : '').toString().split(' ').slice(0, 2).join('.')} ${p} ${h} «${(el.innerText || '').trim().slice(0, 30)}»`); }
    for (const sh of [cs.boxShadow, cs.backgroundImage]) { if (sh && sh !== 'none') { for (const m of sh.matchAll(/rgba?\([^)]*\)/g)) { const h = toHex(m[0]); if (h && E.has(h)) topildi.push(`${el.tagName.toLowerCase()} shadow/gradient ${h}`); } } }
  }
  return topildi.slice(0, 40);
}"""
SAHIFALAR = ["/", "/dashboard", "/orders", "/inventory", "/finance", "/reports", "/debts", "/suppliers/receive", "/recipes", "/production",
             "/finished", "/users", "/projects", "/kpi", "/logs", "/returns", "/rollar", "/murojaat"]
NAT = {"yorug": {}, "tungi": {}, "tugma": {}, "chip": {}}
# aksent (ko'k) oilasidagi YOZUV — samarali fonida (ota-bobolar foni qatlamlari bilan) ≥ 4,5:1 (katta yozuv — 3:1). Mustaqil tekshiruv T1:
# qorong'i `--dark` fonda `--gold` yozuv 2,83:1 edi (Bosh sahifa «Ko'rish →», Foydalanuvchilar «Admin» belgisi, Rollar avatari).
AKSENT = r"""() => {
  const OILA = new Set(['#2563EB', '#1D4ED8', '#3B82F6', '#93B4F5', '#93C5FD', '#60A5FA']);
  const p = (s) => { const m = (s || '').match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
    return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null; };
  const hex = (c) => '#' + c.slice(0, 3).map(x => Math.round(x).toString(16).padStart(2, '0')).join('').toUpperCase();
  const lum = (c) => { const k = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2]); };
  const fon = (el) => { const q = []; for (let e = el; e; e = e.parentElement) { const c = p(getComputedStyle(e).backgroundColor);
      if (c && c[3] > 0) { q.push(c); if (c[3] >= 1) break; } }
    let r = document.documentElement.getAttribute('data-theme') === 'dark' ? [22, 24, 31] : [255, 255, 255];
    for (let i = q.length - 1; i >= 0; i--) { const a = q[i][3]; r = [0, 1, 2].map(j => q[i][j] * a + r[j] * (1 - a)); }
    return r; };
  const yomon = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') continue;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    const c = p(cs.color); if (!c || !OILA.has(hex(c))) continue;
    const b = fon(el), l1 = lum(c), l2 = lum(b), k = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const katta = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && +cs.fontWeight >= 700);
    if (k < (katta ? 3 : 4.5)) yomon.push(`${el.tagName.toLowerCase()}.${String(el.className || '').split(' ')[0]} «${el.textContent.trim().slice(0, 24)}» ${hex(c)} / ${hex(b)} ${k.toFixed(2)}`);
  }
  return yomon.slice(0, 20);
}"""
XATO = []

if PW_BOR and O1:
    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def kontekst(w, h, tel=False, tungi=False):
            ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https://.*"), lambda r: r.fulfill(status=204, body=""))
            ctx.add_init_script("try { localStorage.setItem('theme', '%s'); } catch (e) {}" % ("dark" if tungi else "light"))
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            return ctx, pg

        def kir(pg):
            xav(pg.goto, BU + "/login")
            NAT.setdefault("login_skan", xav(pg.evaluate, SKAN, ESKI_OLTIN))
            NAT.setdefault("login", xav(pg.evaluate, "() => { const s = getComputedStyle(document.documentElement); return {amber: s.getPropertyValue('--amber').trim()}; }"))
            xav(pg.fill, "input[name=username]", "k208_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")

        for tema in ("yorug", "tungi"):
            ctx, pg = kontekst(1440, 900, tungi=(tema == "tungi"))
            kir(pg)
            for yol in SAHIFALAR:
                xav(pg.goto, BU + yol)
                xav(pg.wait_for_load_state, "networkidle")
                xav(pg.wait_for_timeout, 500)
                if yol == "/orders":
                    xav(pg.evaluate, "() => document.querySelectorAll('.ord-list .proj-group').forEach(g => { if (!g.classList.contains('open')) toggleProject(g.dataset.projectId); })")
                    xav(pg.evaluate, f"() => {{ const e = document.querySelector('.ord-list .ord-item[data-order-id=\"{O1}\"]'); if (e) e.click(); }}")
                    xav(pg.wait_for_timeout, 700)
                if yol == "/finished":
                    NAT["chip"][tema] = xav(pg.evaluate, r"""() => { const a = document.querySelector('.fp-cat-opt.chip.active'), n = document.getElementById('chipLow');
                        return a && n ? {faol: getComputedStyle(a).borderTopColor, oddiy: getComputedStyle(n).borderTopColor} : null; }""")
                NAT[tema][yol] = {
                    "aksent": xav(pg.evaluate, AKSENT),
                    "skan": xav(pg.evaluate, SKAN, ESKI_OLTIN),
                    "meta": xav(pg.evaluate, r"""() => { const cs = (e, p) => e ? getComputedStyle(e)[p] : null;
                        const faol = document.querySelector('.sidebar .nav-item.active');
                        return {body: cs(document.body, 'backgroundColor'), main: cs(document.querySelector('.erp-main'), 'backgroundColor'),
                          menyu: cs(document.querySelector('.sidebar'), 'backgroundColor'), faol_fon: cs(faol, 'backgroundColor'),
                          faol_matn: cs(faol && faol.querySelector('.n-txt'), 'color'), band_matn: cs(document.querySelector('.sidebar .nav-item:not(.active) .n-txt'), 'color'),
                          tema: document.documentElement.getAttribute('data-theme'),
                          avatar: [cs(document.querySelector('.s-user .u-avatar'), 'backgroundColor'), cs(document.querySelector('.s-user .u-avatar'), 'color')],
                          nishon: [...document.querySelectorAll('.sidebar .n-badge')].filter(e => e.offsetParent).map(e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color])}; }"""),
                }
            # oltin tugma o'rnida ko'k: .btn-gold (bo'lsa — Buyurtmalar sahifasida ham namunasini yaratamiz)
            xav(pg.goto, BU + "/orders")
            xav(pg.wait_for_load_state, "networkidle")
            NAT["tugma"][tema] = xav(pg.evaluate, r"""() => { const b = document.createElement('button'); b.className = 'btn btn-gold'; b.textContent = 'Sinov';
                document.body.appendChild(b); const s = getComputedStyle(b); const r = {fon: s.backgroundColor, matn: s.color}; b.remove(); return r; }""")
            ctx.close()
        # telefon 390
        ctx, pg = kontekst(390, 844, tel=True)
        kir(pg)
        NAT["tel"] = {}
        for yol in ("/", "/orders", "/finance"):
            xav(pg.goto, BU + yol)
            xav(pg.wait_for_load_state, "networkidle")
            NAT["tel"][yol] = xav(pg.evaluate, "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ctx.close()
        br.close()

    _y = NAT["yorug"]
    _eski_y = {k: v["skan"] for k, v in _y.items() if v.get("skan")}
    check(f"D1 YORUG' rejim: {len(SAHIFALAR)} sahifada HECH bir elementda eski oltin / qum rang yo'q (matn, fon, chegara, soya, gradient)",
          len(_y) == len(SAHIFALAR) and not _eski_y and all(v.get("skan") is not None for v in _y.values()), _eski_y)
    _t = NAT["tungi"]
    _eski_t = {k: v["skan"] for k, v in _t.items() if v.get("skan")}
    check(f"D2 TUNGI rejim: {len(SAHIFALAR)} sahifada eski oltin rang yo'q", len(_t) == len(SAHIFALAR) and not _eski_t, _eski_t)
    _m = {k: v["meta"] for k, v in _y.items()}
    check("D3 yorug': sahifa foni #F4F6FA, menyu OQ (#FFFFFF)",
          all(rgb(x["main"]) == hexrgb("#F4F6FA") and rgb(x["menyu"]) == (255.0, 255.0, 255.0) for x in _m.values() if x and x.get("main")),
          {k: (x or {}).get("main") for k, x in list(_m.items())[:4]})
    _f = [(k, x["faol_fon"], x["faol_matn"]) for k, x in _m.items() if x and x.get("faol_matn")]
    check("D4 yorug': faol menyu bandi — och ko'k fon (#EEF4FF), ko'k matn (#1D4ED8, ≥ 4,5:1); oddiy band matni oq menyuda ≥ 4,5:1",
          _f and all(rgb(fn) == hexrgb("#EEF4FF") and rgb(mt) == hexrgb("#1D4ED8") and kontrast(rgb(mt), rgb(fn)) >= 4.5 for _, fn, mt in _f)
          and all(kontrast(rgb(x["band_matn"]), (255.0, 255.0, 255.0)) >= 4.5 for x in _m.values() if x and x.get("band_matn")), _f[:3])
    _mt = {k: v["meta"] for k, v in _t.items()}
    check("D5 tungi: menyu qorong'i (#181B22), faol band matni #93B4F5 (≥ 4,5:1)",
          all(rgb(x["menyu"]) == hexrgb("#181B22") for x in _mt.values() if x and x.get("menyu"))
          and all(kontrast(rgb(x["faol_matn"]), hexrgb("#181B22")) >= 4.5 for x in _mt.values() if x and x.get("faol_matn")),
          {k: ((x or {}).get("menyu"), (x or {}).get("faol_matn")) for k, x in list(_mt.items())[:3]})
    _tg = (NAT["tugma"].get("yorug") or {}), (NAT["tugma"].get("tungi") or {})
    check("D6 «oltin» tugma (`.btn-gold`) endi KO'K (#2563EB), oq yozuv ≥ 4,5:1 — yorug' va tungi",
          all(rgb(t.get("fon")) == hexrgb("#2563EB") and kontrast(rgb(t.get("matn")), rgb(t.get("fon"))) >= 4.5 for t in _tg), _tg)
    _av = [(t, k, (v.get("meta") or {}).get("avatar"), (v.get("meta") or {}).get("nishon")) for t in ("yorug", "tungi") for k, v in NAT[t].items()]
    check("D10 menyudagi foydalanuvchi belgisi (bosh harf) va menyu sonlari: yozuv fonda ≥ 4,5:1 — yorug' va tungi (tungi aksent #3B82F6 da oq yozuv 3,7 — yetmaydi)",
          len(_av) == 2 * len(SAHIFALAR) and all(a and a[0] and kontrast(rgb(a[1]), rgb(a[0])) >= 4.5 for _, _, a, _ in _av)
          and all(kontrast(rgb(b[1]), rgb(b[0])) >= 4.5 for _, _, _, n in _av for b in (n or [])),
          [(t, k, a, n) for t, k, a, n in _av if not (a and a[0] and kontrast(rgb(a[1]), rgb(a[0])) >= 4.5)][:4])
    check("D7 kirish sahifasi: aksent ko'k (--amber #3B82F6), eski oltin yo'q",
          (NAT.get("login") or {}).get("amber", "").upper() == "#3B82F6" and NAT.get("login_skan") == [], (NAT.get("login"), NAT.get("login_skan")))
    check("D8 telefon (390 px): Bosh sahifa, Buyurtmalar, Moliya yon tomonga toshmaydi",
          NAT.get("tel") and all(v is not None and v <= 1 for v in NAT["tel"].values()), NAT.get("tel"))
    _ak = {f"{t} {k}": v.get("aksent") for t in ("yorug", "tungi") for k, v in NAT[t].items()}
    check("D11 aksent (ko'k) rangdagi HAMMA yozuv o'z fonida ≥ 4,5:1 (katta — 3:1) — barcha sahifa, yorug' va tungi (qorong'i kartada / belgida "
          "`--gold` yozuv 2,83 edi)", len(_ak) == 2 * len(SAHIFALAR) and all(v == [] for v in _ak.values()),
          {k: v for k, v in _ak.items() if v != []})
    _ch = NAT.get("chip") or {}
    check("D12 tanlangan filtr (Tayyor mahsulotlar «Barcha kategoriya») chegarasi tanlanmagandan aniq farq qiladi (≥ 3:1) — yorug' va tungi",
          set(_ch) == {"yorug", "tungi"} and all(v and kontrast(rgb(v["faol"]), rgb(v["oddiy"])) >= 3 for v in _ch.values()),
          {k: (v, v and round(kontrast(rgb(v["faol"]), rgb(v["oddiy"])), 2)) for k, v in _ch.items()})
    check("D9 sahifalarda JS xatosi yo'q", not XATO, XATO[:5])
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
