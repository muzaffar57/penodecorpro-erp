#!/usr/bin/env python3
"""
test_kpi_loyiha_yuklash_ui.py — kech138 (zip 165): «Ustalar KPI» va «Loyihalar» sahifalari bitta so'rov xatosida QOTMAYDI, yolg'on
qiymat («0 so'm», «Hodim qo'shilmagan», «Yopiq», «Mahsulot yo'q», «xomashyo jurnali topilmadi») ko'rsatmaydi, ehson foizi yuklanmasa
«Saqlash» 0 % YOZMAYDI, loyiha bo'limi tez almashtirilsa kech kelgan javob boshqa bo'lim ustiga yozilmaydi, bo'limlar ruxsat bo'yicha —
HAQIQIY brauzerda (Chromium, Playwright), HAQIQIY lokal server bilan (uvicorn, test bazasi) O'LCHANADI. Ma'lumot —
`tools/test_c_telefon.py` ZANJIR_JS (dasturning o'z API si orqali to'liq ish zanjiri) + faol sovg'a davri + ehson 7 % + boshlang'ich kassa.

NIMA UCHUN KERAK (O'LCHANGAN — work/k164/olchov164.py, zip 163 kodi; egasi tanlovi 10.10 «Sahifalar qotmasin»; reja — zip 164 Moliya +
Hisobotlar, zip 165 KPI + Loyihalar)
  * KPI: ehson foizi yuklanmasa maydon «0» / bo'sh — «Saqlash» haqiqiy 7 % o'rniga 0 % yozardi; sovg'a davri yuklanmasa — FAOL davr
    «Yopiq» va «Davrni ochish» formasi; xato JSON — «Hisoblangan oylik 0 so'm», «To'lanmagan 0 so'm», «Bu oy uchun hech kimga to'lov
    hisoblanmagan», «Hodim qo'shilmagan»; ustalar / hodimlar ro'yxati abadiy «Yuklanmoqda...»; tayyor «Moliyachi» da hodimlar 403 →
    «Hodim qo'shilmagan»;
  * Loyihalar: «Sof foyda 0 so'm», to'lovlarda «0 so'm ·» qatori, «Mahsulot yo'q», «xomashyo jurnali topilmadi», tarixdan to'lovlar
    jimgina tushib qolardi; «🚚 Yetkazish» abadiy «…»; 6 bo'limda poyga (kech kelgan javob ochiq «Buyurtmalar» ustiga); «Moliyachi» da
    «Buyurtmalar», «To'lovlar», «Xomashyo», «Tarix» — 403, «Mahsulotlar» — «Mahsulot yo'q».
BO'LIMLAR
  K1 KPI — hammasi yuklandi (kutilgan qiymatlar, sabablar yashirin, ehson maydoni ochiq, so'rovlar bir martadan);
  K2 KPI — 7 so'rov × 5 xato (502 HTML, 500 JSON, tarmoq, 401, 403): o'sha blok «—» va O'SHA blokda aniq sabab, qolgani o'z qiymatida;
  K3 KPI — ehson: xato bo'lsa «Saqlash» so'rov yubormaydi (bazada 7 % qoladi); bo'sh maydon saqlanmaydi; to'g'ri qiymat saqlanadi;
  K4 KPI — poyga: yil almashtirildi (ustalar), oy almashtirildi (oylik hisob-kitob);
  K5 KPI — sovg'a davri oynasi xatoda: sabab, «Davrni ochish» formasi YO'Q;
  K6 KPI — oynalar: usta buyurtmalari, avans tarixi, to'lov tarixi, oylik avans tafsiloti — xato bo'lsa sabab;
  K7 KPI — rollar (HAQIQIY server): admin, Moliyachi, faqat «Ustalar KPI»;
  P1 Loyihalar — hammasi yuklandi;  P2 — bajarilish xaritasi va yetkazish holati × 5 xato;
  P3 Loyihalar — 7 bo'lim × so'rov × 5 xato (+ bir nechta so'rovdan bittasi xato);  P4 — poyga (6 bo'lim);
  P5 Loyihalar — rollar (HAQIQIY server): admin, Menejer, Moliyachi, faqat «Loyihalar»;
  T  telefon 390 / 320 px (kunduzgi / tungi): hamma so'rov xato — sahifa toshmaydi, sabab ekranda va o'qiladi (kontrast ≥ 4.5);
  S  statik.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 164) qarshi QULAMAYDI — yiqiladi.
TANLOV (mutatsiya sinovlari uchun; odatiy — HAMMASI): KL_BOLIM=K2,P3; KL_YOL=kpi-report,payments; KL_TUR=500_json.
ISHLATISH: python3 tools/test_kpi_loyiha_yuklash_ui.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import socket
import datetime
import tempfile
import threading
import contextlib
from urllib.parse import urlparse

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OK = FAIL = 0
FAILED = []
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
YORLIQ = "[PG] " if PG_URL else ""


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
        print(f"  ✗ {label}   {str(detail)[:1500]}")


def section(t):
    print(f"\n--- {t} ---")


_BOLIM = {x for x in (os.environ.get("KL_BOLIM") or "").split(",") if x}
_YOL = [x for x in (os.environ.get("KL_YOL") or "").split(",") if x]
_TUR = {x for x in (os.environ.get("KL_TUR") or "").split(",") if x}


def bolim(nom):
    return not _BOLIM or nom in _BOLIM


def tanlangan(yol, tur):
    return (not _YOL or any(x in yol for x in _YOL)) and (not _TUR or tur in _TUR)


def oqi(nom):
    try:
        with open(os.path.join(ROOT, "templates", nom), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def funksiya(src, nom):
    m = re.search(r"(async\s+)?function\s+" + nom + r"\s*\(", src)
    if not m:
        return ""
    j = src.find("{", m.end())
    d = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            d += 1
        elif src[k] == "}":
            d -= 1
            if d == 0:
                return src[m.start():k + 1]
    return ""


# ══════════════════════════════════════════════════════════════
section("S. Statik — kpi.html va projects.html tuzilishi")
# ══════════════════════════════════════════════════════════════
KPI, PRJ = oqi("kpi.html"), oqi("projects.html")
_xom = r"fetch\([^;]*?\)\s*\.then\(\s*r\s*=>\s*r\.json\(\)\s*\)"
check("S1 KPI va Loyihalar: xom `fetch(…).then(r => r.json())` (xato JSON «0 so'm» / «Mahsulot yo'q» bo'lib chizilardi) yo'q",
      not re.search(_xom, KPI) and not re.search(_xom, PRJ), (re.findall(r"[^\n]{0,50}" + _xom, KPI)[:3], re.findall(r"[^\n]{0,50}" + _xom, PRJ)[:3]))
check("S2 KPI boshlanishi — `Promise.allSettled` (biri yiqilsa qolganlari chiziladi); ehson maydoni va «Saqlash» boshida YOPIQ "
      "(`disabled`), saqlash — faqat yuklangan foiz bilan (`ehsonYuklandi`)",
      "const _boshla = () => Promise.allSettled([" in KPI
      and re.search(r'id="ehson-percent-input"[^>]*disabled', KPI) is not None
      and re.search(r'id="ehson-save-btn"[^>]*disabled', KPI) is not None
      and "ehsonYuklandi" in funksiya(KPI, "saveEhsonPercent"), "")
check("S3 KPI ruxsat bo'yicha bloklar: hodimlar («hodim»), oylik kartalar va hisob-kitob («moliya»), nofaol ustalar («usta»)",
      all(f"current_user.ruxsat('{b}', 'korish')" in KPI for b in ("hodim", "moliya", "usta"))
      and "{% if R_HODIM %}" in KPI and "{% if R_MOLIYA %}" in KPI and "{% if R_USTA %}" in KPI, "")
_rend = ["renderOrders", "renderYukXatlari", "renderFinance", "renderPayments", "renderProducts", "renderMaterials", "renderTimeline"]
check("S4 Loyihalar: har bo'lim chizuvchisi navbat oladi (`bolimNavbati()` — kech kelgan javob tashlanadi); bo'limlar ro'yxati "
      "(`data-bolimlar`), to'lovlar (`data-tolov`), ko'rsatkichlar (`data-korsatkich`) — server ruxsatidan",
      all("bolimNavbati()" in funksiya(PRJ, n) for n in _rend + ["renderAsosiy", "renderNotes"])
      and 'data-bolimlar="{{ _bolimlar|join(\',\') }}"' in PRJ and "data-korsatkich=" in PRJ and "data-tolov=" in PRJ,
      [n for n in _rend if "bolimNavbati()" not in funksiya(PRJ, n)])
_js_izoh = [m for m in re.findall(r"<script>([\s\S]*?)</script>", KPI + PRJ) if re.search(r"//[^\n]*\{%", m)]
check("S5 `<script>` ichidagi JS izohida Jinja tegi (`{% … %}`) yo'q (kech137: sahifa 500)", not _js_izoh, len(_js_izoh))

try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"

PG_BAZA = "kpi_loyiha_yuklash_ui165_test"
_T = tempfile.mkdtemp(prefix="kl_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'kl_ui_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol             # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "kl_a", PAROL, UserRole.ADMIN, "Namuna Dekor", company_id=1)
    auth.create_user(s, "kl_mol", PAROL, UserRole.ACCOUNTANT, "KL moliyachi", company_id=1)
    auth.create_user(s, "kl_men", PAROL, UserRole.MANAGER, "KL menejer", company_id=1)
    for _u in ("kl_kpi", "kl_loy"):
        auth.create_user(s, _u, PAROL, UserRole.MANAGER, _u.upper(), company_id=1)
ROLLAR = {"kl_kpi": {"kpi": ["korish"]}, "kl_loy": {"loyiha": ["korish"]}}
for _u, _rx in ROLLAR.items():
    _r = Rol(company_id=1, nom="KL165 " + _u, kod=None, ruxsatlar=json.dumps(_rx), tavsif="")
    s.add(_r)
    s.flush()
    s.query(User).filter(User.username == _u).first().rol_id = _r.id
s.commit()
s.close()

_src_tel = ""
try:
    with open(os.path.join(ROOT, "tools", "test_c_telefon.py"), encoding="utf-8") as _f:
        _src_tel = _f.read()
except OSError:
    pass


def _js_ol(nom):
    i = _src_tel.find(nom + ' = r"""')
    if i < 0:
        return ""
    i += len(nom + ' = r"""')
    return _src_tel[i:_src_tel.find('"""', i)]


ZANJIR_JS = _js_ol("ZANJIR_JS")
CHART_ORINBOSAR = _js_ol("CHART_ORINBOSAR") or "window.Chart = function () { return {destroy() {}, update() {}}; };"

SABAB = {"502_html": "server javob bermadi, sahifani yangilang",
         "500_json": "server javob bermadi, sahifani yangilang",
         "tarmoq": "internet aloqasi yo'q, sahifani yangilang",
         "401_json": "kirish muddati tugagan, qayta kiring",
         "403_json": "ko'rish ruxsati yo'q"}
SESSIYA = "⚠️ Kirish muddati tugagan — qayta kiring"
QIZIL = "rgb(185, 28, 28)"
EHSON_QOSHIMCHA = " («Saqlash» yopiq — joriy foiz ko'rinmaguncha o'zgartirilmaydi)"


def matn(nima, tur):
    return f"⚠️ {nima} yuklanmadi — {SABAB[tur]}"


def bs(x):
    return re.sub(r"\s+", "", x or "")


# ── KPI: kuzatiladigan elementlar va kutilgan qiymatlar (O'LCHANGAN — olchov_repo_dev172 / dev174) ──
K_IDS = ["k-master-count", "k-emp-count", "k-emp-calculated", "k-emp-unpaid", "k-total-gift", "k-top-master", "xato-kpi-kartalar",
         "mkList", "mkInactiveWrap", "empList", "emp-avans-1", "emp-fin-1", "emp-status-1", "xato-ehson", "giftPeriodStatusPill",
         "giftPeriodSummary", "xato-sovga", "empMonthlyReport", "yukSessiya"]
K_KUT = {"k-master-count": "1 ta", "k-emp-count": "1", "k-emp-calculated": "3 000 000 so'm", "k-emp-unpaid": "3 000 000 so'm",
         "k-total-gift": "0 so'm", "k-top-master": "hali yo'q", "giftPeriodStatusPill": "Faol", "giftPeriodSummary": "🎁 Namuna sovga",
         "emp-status-1": "🔴 To'lanmagan"}
K_ICHIDA = {"mkList": "Namuna Usta", "empList": "Namuna Hodim", "empMonthlyReport": "Namuna Hodim", "emp-fin-1": "QOLGAN"}
K_XATO_IDLAR = ["xato-kpi-kartalar", "xato-ehson", "xato-sovga", "yukSessiya"]
K_BLOK = {
    "/api/masters/kpi-report": {"chiziq": ["k-master-count", "k-total-gift", "k-top-master"], "royxat": ("mkList", "Hamkor ustalar"),
                                "yashirin": ["mkInactiveWrap"]},
    "/api/employees": {"chiziq": ["k-emp-count"], "royxat": ("empList", "Hodimlar"),
                       "yoq": ["emp-avans-1", "emp-fin-1", "emp-status-1"]},
    "/api/finance/report": {"chiziq": ["k-emp-calculated", "k-emp-unpaid", "emp-fin-1"], "bosh": ["emp-status-1"],
                            "sabab": ("xato-kpi-kartalar", "Joriy oy oyliklari"), "royxat": ("empMonthlyReport", "Oylik hisob-kitob"),
                            "ozgaradi": ["empList"]},
    "/api/settings/ehson-percent": {"ehson": True},
    "/api/gift-period": {"teng": {"giftPeriodStatusPill": "—", "giftPeriodSummary": ""}, "sabab": ("xato-sovga", "Sovg'a davri")},
    "/advances": {"matnli": ("emp-avans-1", "Bu oy avansi"), "ozgaradi": ["empList"]},
    "/api/masters": {"nofaol": True},
}

# ── Loyihalar ──
P_IDS = ["statusPanel", "sp-bajarilgan", "sp-yetkazish", "pbaj-1", "xato-bajarilgan", "xato-yetkazish", "tabContent", "yukSessiya"]
BOLIM_YOL = {      # bo'lim → so'rov(lar), sabab nomi, xatosiz holatda borligi kutilgan matn
    "finance": ([("/detail-stats", "Sof foyda")], "Sof foyda 646 858 so'm"),
    "payments": ([("/api/orders", "To'lovlar"), ("/api/payments", None)], "250 000 so'm"),
    "products": ([("/items", "Mahsulotlar")], "Namuna Travertin"),
    "materials": ([("/api/orders", "Xomashyo jurnali"), ("/api/inventory/movements", None)], "4 ta xomashyo"),
    "timeline": ([("/api/orders", "Tarix"), ("/api/payments", None)], "Buyurtma yaratildi — ORD-001-2"),
    "orders": ([("/api/orders", "Buyurtmalar")], "ORD-001-1"),
    "yuklar": ([("/yuk-xatlari", "Yuk xatlari")], "3 ta yuk xati"),
}
BUYURTMA_SOZ = {"/api/payments": "to'lovlari", "/api/inventory/movements": "xomashyo jurnali"}

SNAP = r"""(idlar) => {
  const ko = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
  const o = {el: {}};
  idlar.forEach(i => { const e = document.getElementById(i);
    o.el[i] = e ? {v: ko(e) && !e.hidden, t: (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim(), c: getComputedStyle(e).color} : null; });
  o.qator_rang = {};
  document.querySelectorAll('.yuk-xato-qator').forEach(q => { const p = q.closest('[id]'); if (p && !(p.id in o.qator_rang)) o.qator_rang[p.id] = getComputedStyle(q).color; });
  const s = document.querySelector('#yukSessiya a');
  o.sessiya_havola = s ? s.getAttribute('href') : null;
  const inp = document.getElementById('ehson-percent-input'), btn = document.getElementById('ehson-save-btn');
  o.ehson = inp ? {qiymat: inp.value, yopiq: inp.disabled, tugma_yopiq: btn ? btn.disabled : null} : null;
  const kont = document.querySelector('.erp-main') || document.body;
  const m = kont.innerText || '';
  o.yuklanmoqda = (m.match(/Yuklanmoqda/g) || []).length;
  o.notogri = (m.match(/[^\n]{0,30}(undefined|NaN|\[object )[^\n]{0,30}/g) || []).slice(0, 4);
  return o;
}"""

KONTRAST = r"""() => {
  const rgba = c => { const m = (c.match(/[\d.]+/g) || []).map(Number); return [m[0] || 0, m[1] || 0, m[2] || 0, m.length > 3 ? m[3] : 1]; };
  const fonEl = e => { for (let p = e; p; p = p.parentElement) { const st = getComputedStyle(p);
                         const c = rgba(st.backgroundColor); if (c[3] > 0) return c; }
                       return rgba(getComputedStyle(document.documentElement).backgroundColor); };
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
                     return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const kon = (a, b) => { const x = lum(a), y = lum(b); return Math.round(100 * (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)) / 100; };
  const natija = [];
  document.querySelectorAll('.yuk-xato, .yuk-xato-qator').forEach(e => {
    if (!(e.offsetWidth || e.offsetHeight) || e.hidden) return;
    const r = e.getBoundingClientRect();
    natija.push({id: e.id || (e.parentElement && e.parentElement.id) || e.className, kontrast: kon(rgba(getComputedStyle(e).color), fonEl(e)),
                 chap: Math.round(r.left), ong: Math.round(r.right), toshgan: e.scrollWidth > e.clientWidth + 1});
  });
  return {el: natija, vw: innerWidth, sw: document.documentElement.scrollWidth};
}"""

section("0. Tayyorgarlik")
check("0a Python `playwright` bor va ish zanjiri (`tools/test_c_telefon.py` ZANJIR_JS) topildi", PW_BOR and len(ZANJIR_JS) > 1000, _pw_xato)

import uvicorn                                     # noqa: E402


def yol_mos(yol):
    if yol.startswith("/api/"):
        return lambda url: urlparse(url).path == yol
    return lambda url: urlparse(url).path.endswith(yol)


def jv(r, holat, tana):
    r.fulfill(status=holat, body=json.dumps(tana), content_type="application/json")


XATOLAR = {
    "502_html": lambda r: r.fulfill(status=502, body="<html><body>Bad Gateway</body></html>", content_type="text/html"),
    "500_json": lambda r: jv(r, 500, {"detail": "Ichki xato"}),
    "tarmoq": lambda r: r.abort("failed"),
    "401_json": lambda r: jv(r, 401, {"detail": "Iltimos, tizimga kiring"}),
    "403_json": lambda r: jv(r, 403, {"detail": "Ruxsat yo'q"}),
}

if PW_BOR and ZANJIR_JS:
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
    check("0b lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def xav(f, *a, **k):
            """Brauzer amali — element topilmasa (asl kodda / mutatsiyada) sinov QULAMAYDI, tekshiruv yiqiladi."""
            try:
                return f(*a, **k)
            except Exception as ex:        # noqa: BLE001
                print(f"    (amal bajarilmadi: {getattr(f, '__name__', f)} {a[:1]} — {type(ex).__name__})")
                return None

        def kontekst(user="kl_a", w=1440, h=900):
            tel = w < 700
            ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ")
            ctx.set_default_timeout(20000)

            def tashqi(r):
                u = r.request.url
                if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
                    return r.fulfill(status=200, content_type="application/javascript", body=CHART_ORINBOSAR)
                if u.startswith("https://fonts.googleapis.com/"):
                    return r.fulfill(status=200, content_type="text/css", body="")
                return r.fulfill(status=204, body="")
            ctx.route(re.compile(r"^https://.*"), tashqi)
            pg = ctx.new_page()
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", user)
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            pg.close()
            return ctx

        def sahifa(ctx):
            pg = ctx.new_page()
            pg.__xato = []
            pg.__sorov = []
            pg.__javob = []
            pg.on("pageerror", lambda e: pg.__xato.append(str(e)[:300]))
            pg.on("request", lambda r: pg.__sorov.append(r.method + " " + r.url.replace(BU, "")) if "/api/" in r.url else None)
            pg.on("response", lambda r: pg.__javob.append((urlparse(r.url).path, r.status)) if "/api/" in r.url else None)
            return pg

        def och(pg, url, kut=1300):
            xav(pg.goto, BU + url, wait_until="networkidle")
            pg.wait_for_timeout(kut)

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def snap(pg, idlar):
            o = ev(pg, SNAP, idlar)
            return o if isinstance(o, dict) and "el" in o else {"el": {}, "xom": o}

        def t(o, i):
            e = (o.get("el") or {}).get(i)
            return e["t"] if e else None

        def v(o, i):
            e = (o.get("el") or {}).get(i)
            return bool(e and e["v"])

        def farqlar(o, asl, istisno):
            f = []
            for i, a in (asl.get("el") or {}).items():
                if i in istisno:
                    continue
                b = (o.get("el") or {}).get(i)
                if (a is None) != (b is None) or (a and (a["v"] != b["v"] or (a["v"] and a["t"] != b["t"]))):
                    f.append((i, (a or {}).get("t", "")[:60], (b or {}).get("t", "")[:60]))
            return f

        def sessiya_tekshir(o, tur, x):
            ss = (o.get("el") or {}).get("yukSessiya") or {}
            if tur == "401_json":
                if not (ss.get("v") and ss.get("t") == SESSIYA and o.get("sessiya_havola") == "/login"):
                    x.append(("sessiya xabari (kirish havolasi)", ss, o.get("sessiya_havola")))
            elif ss.get("v"):
                x.append(("sessiya xabari ko'rinmasligi kerak", ss))

        CTX = {u: kontekst(u) for u in ("kl_a", "kl_mol", "kl_men", "kl_kpi", "kl_loy")}
        _tk = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
        K = {"m": "Namuna", "sana": _tk.strftime("%Y-%m-%d"), "yil": _tk.year, "oy": _tk.month,
             "muddat": (_tk + datetime.timedelta(days=9)).strftime("%Y-%m-%d")}
        pg = sahifa(CTX["kl_a"])
        och(pg, "/", 300)
        try:
            Z = pg.evaluate(ZANJIR_JS, K)
        except Exception as _e:            # noqa: BLE001
            Z = {"yiqilgan": [["istisno", 0, str(_e)[:300]]], "L": []}
        Q = ev(pg, """async () => {
            const g = await fetch('/api/gift-period/open', {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tiers: [{gift_name: 'Namuna sovga', threshold_amount: 5000000}], master_ids: []})});
            const fd = new FormData(); fd.append('percent', '7');
            const e = await fetch('/api/settings/ehson-percent', {method: 'PUT', body: fd});
            const fk = new FormData(); fk.append('category', 'boshlangich'); fk.append('amount', '2500000'); fk.append('notes', 'kl165');
            const k = await fetch('/api/finance/cash-transaction', {method: 'POST', body: fk});
            return [g.status, e.status, k.status]; }""")
        pg.close()
        check("0c ish zanjiri: hamma qadam 2xx, faol sovg'a davri, ehson 7 %, boshlang'ich kassa",
              not Z.get("yiqilgan") and len(Z.get("L") or []) >= 50 and Q == [200, 200, 200], [Z.get("yiqilgan"), len(Z.get("L") or []), Q])

        def ehson_bazada():
            pg_ = sahifa(CTX["kl_a"])
            och(pg_, "/", 200)
            r_ = ev(pg_, "async () => (await (await fetch('/api/settings/ehson-percent')).json()).ehson_percent")
            pg_.close()
            return r_

        # ══════════════════════════════════════════════════════════════
        # KPI
        # ══════════════════════════════════════════════════════════════
        K_ASL = {}
        if bolim("K1") or bolim("K2"):
            section("K1. Ustalar KPI — hammasi yuklandi")
            pg = sahifa(CTX["kl_a"])
            och(pg, "/kpi", 1500)
            K_ASL = snap(pg, K_IDS)
            _farq = [(k, t(K_ASL, k), w) for k, w in K_KUT.items() if t(K_ASL, k) != w]
            _farq += [(k, (t(K_ASL, k) or "")[:80], w) for k, w in K_ICHIDA.items() if w not in (t(K_ASL, k) or "")]
            check("K1a har blok kutilgan qiymatda (ustalar, hodimlar, oylik kartalar, sovg'a davri, oylik hisob-kitob)", not _farq, _farq)
            check("K1b ehson maydoni ochiq va «7», «Saqlash» ochiq; sabab yozuvlari yashirin; «Yuklanmoqda», «undefined», JS xatosi yo'q",
                  K_ASL.get("ehson") == {"qiymat": "7", "yopiq": False, "tugma_yopiq": False}
                  and not any(v(K_ASL, i) for i in K_XATO_IDLAR) and not K_ASL.get("yuklanmoqda") and not K_ASL.get("notogri")
                  and not pg.__xato, (K_ASL.get("ehson"), [i for i in K_XATO_IDLAR if v(K_ASL, i)], K_ASL.get("yuklanmoqda"),
                                      K_ASL.get("notogri"), pg.__xato))
            _yollar = [urlparse(x.split(" ", 1)[1]).path for x in pg.__sorov if x.startswith("GET ")]
            _kut1 = ["/api/masters/kpi-report", "/api/employees", "/api/finance/report", "/api/settings/ehson-percent", "/api/gift-period",
                     "/api/masters", "/api/employees/1/advances"]
            check("K1c har so'rov bir martadan (joriy oy hisoboti — kartalar va hisob-kitob uchun BITTA)",
                  all(_yollar.count(y) == 1 for y in _kut1), [(y, _yollar.count(y)) for y in _kut1])
            pg.close()

        if bolim("K2") and K_ASL:
            section("K2. Ustalar KPI — har so'rov × har xato")
            for yol, b in K_BLOK.items():
                for tur, xf in XATOLAR.items():
                    if not tanlangan(yol, tur):
                        continue
                    pg = sahifa(CTX["kl_a"])
                    pg.route(yol_mos(yol), xf)
                    och(pg, "/kpi", 1300)
                    if b.get("nofaol"):
                        xav(pg.click, "#mkInactiveBtn")
                        pg.wait_for_timeout(300)
                    o = snap(pg, K_IDS + ["mkInactiveList"])
                    x = []
                    ist = set(b.get("ozgaradi", [])) | {"yukSessiya", "mkInactiveList"}
                    for i in b.get("chiziq", []):
                        ist.add(i)
                        if t(o, i) != "—":
                            x.append(("«—» emas", i, t(o, i)))
                    for i in b.get("bosh", []):
                        ist.add(i)
                        if (t(o, i) or "") != "":
                            x.append(("bo'sh emas", i, t(o, i)))
                    for i in b.get("yashirin", []):
                        ist.add(i)
                        if v(o, i):
                            x.append(("ko'rinib turibdi", i))
                    for i in b.get("yoq", []):
                        ist.add(i)
                        if (o.get("el") or {}).get(i) is not None:
                            x.append(("element qoldi", i))
                    for i, w in (b.get("teng") or {}).items():
                        ist.add(i)
                        if (t(o, i) or "") != w:
                            x.append(("qiymat", i, t(o, i), w))
                    if b.get("sabab"):
                        sid, nima = b["sabab"]
                        ist.add(sid)
                        e = (o.get("el") or {}).get(sid) or {}
                        if not (e.get("v") and e.get("t") == matn(nima, tur) and e.get("c") == QIZIL):
                            x.append(("sabab", sid, e))
                    if b.get("royxat"):
                        rid, nima = b["royxat"]
                        ist.add(rid)
                        if t(o, rid) != matn(nima, tur) or (o.get("qator_rang") or {}).get(rid) != QIZIL:
                            x.append(("ro'yxat sababi", rid, t(o, rid), (o.get("qator_rang") or {}).get(rid)))
                    if b.get("matnli"):
                        mid, nima = b["matnli"]
                        ist.add(mid)
                        e = (o.get("el") or {}).get(mid) or {}
                        if not (e.get("t") == matn(nima, tur) and e.get("c") == QIZIL):
                            x.append(("qator sababi", mid, e))
                    if b.get("ehson"):
                        ist.add("xato-ehson")
                        e = (o.get("el") or {}).get("xato-ehson") or {}
                        if not (o.get("ehson") == {"qiymat": "", "yopiq": True, "tugma_yopiq": True}
                                and e.get("v") and e.get("t") == matn("Ehson foizi", tur) + EHSON_QOSHIMCHA):
                            x.append(("ehson: maydon / tugma yopiq emas yoki sabab", o.get("ehson"), e))
                    if yol == "/api/masters/kpi-report":     # qidiruv / saralash ro'yxatni qayta chizadi — sabab qoladi («Usta yo'q» emas)
                        ev(pg, "() => { renderMasterKpiList(); }")
                        _qayta = t(snap(pg, ["mkList"]), "mkList")
                        if _qayta != matn("Hamkor ustalar", tur):
                            x.append(("qidiruvdan keyin ro'yxat", _qayta))
                    if b.get("nofaol"):
                        ist.add("mkInactiveWrap")
                        if t(o, "mkInactiveList") != matn("Nofaol ustalar ro'yxati", tur):
                            x.append(("nofaol ustalar sababi", t(o, "mkInactiveList")))
                    f = farqlar(o, K_ASL, ist)
                    if f:
                        x.append(("boshqa bloklar o'zgardi", f[:6]))
                    kor = [i for i in K_XATO_IDLAR if i not in ist and v(o, i)]
                    if kor:
                        x.append(("boshqa sabab ko'rindi", kor))
                    sessiya_tekshir(o, tur, x)
                    if o.get("yuklanmoqda") or o.get("notogri") or pg.__xato:
                        x.append(("Yuklanmoqda / undefined / JS xatosi", o.get("yuklanmoqda"), o.get("notogri"), pg.__xato[:2]))
                    check(f"K2 {yol} {tur}: o'sha blok «—» va sabab bilan, qolgani o'z qiymatida", not x, x)
                    pg.close()

        if bolim("K3"):
            section("K3. Ehson foizi — 0 % yozib yuborilmaydi")
            for tur in ("502_html", "500_json", "tarmoq"):
                pg = sahifa(CTX["kl_a"])

                def _faqat_get(xf):
                    def _h(r):                  # bitta parametr (Playwright 2 parametrli ishlovchiga `request` ni beradi)
                        return xf(r) if r.request.method == "GET" else r.continue_()
                    return _h
                pg.route(yol_mos("/api/settings/ehson-percent"), _faqat_get(XATOLAR[tur]))
                och(pg, "/kpi", 1200)
                xav(pg.click, "#ehson-save-btn", timeout=1500)
                ev(pg, "() => { saveEhsonPercent(); }")
                pg.wait_for_timeout(700)
                put = [x for x in pg.__sorov if x.startswith("PUT ") and "/ehson-percent" in x]
                pg.close()
                check(f"K3a {tur}: foiz yuklanmadi — «Saqlash» (tugma va funksiya) so'rov YUBORMAYDI; bazada 7 % qoldi",
                      not put and ehson_bazada() == 7, (put, ehson_bazada()))
            pg = sahifa(CTX["kl_a"])
            och(pg, "/kpi", 1200)
            xav(pg.fill, "#ehson-percent-input", "")
            ev(pg, "() => { saveEhsonPercent(); }")
            pg.wait_for_timeout(600)
            put = [x for x in pg.__sorov if x.startswith("PUT ")]
            o = snap(pg, ["xato-ehson"])
            check("K3b bo'sh maydon — saqlanmaydi, «⚠️ Foizni kiriting (ehson bo'lmasa — 0)»",
                  not put and t(o, "xato-ehson") == "⚠️ Foizni kiriting (ehson bo'lmasa — 0)" and ehson_bazada() == 7, (put, t(o, "xato-ehson")))
            xav(pg.fill, "#ehson-percent-input", "5")
            xav(pg.click, "#ehson-save-btn")
            pg.wait_for_timeout(800)
            put = [x for x in pg.__sorov if x.startswith("PUT ")]
            check("K3c to'g'ri qiymat (5) — saqlanadi, sabab yo'qoladi", len(put) == 1 and ehson_bazada() == 5 and not v(snap(pg, ["xato-ehson"]), "xato-ehson"),
                  (put, ehson_bazada()))
            xav(pg.fill, "#ehson-percent-input", "7")
            xav(pg.click, "#ehson-save-btn")
            pg.wait_for_timeout(800)
            pg.close()
            check("K3d qaytarildi — 7 %", ehson_bazada() == 7, ehson_bazada())

        if bolim("K4"):
            section("K4. Ustalar KPI — poyga")

            def ushlovchi(ushla, shart=None):
                def _u(r):
                    if not ushla and (shart is None or shart(r.request.url)):
                        ushla.append(r)
                    else:
                        r.continue_()
                return _u
            pg = sahifa(CTX["kl_a"])
            och(pg, "/kpi", 1200)
            ushla = []
            eski_yil = _tk.year - 1
            pg.route(yol_mos("/api/masters/kpi-report"), ushlovchi(ushla, lambda u: f"year={eski_yil}" in u))
            ev(pg, "y => { document.getElementById('kpi-year').value = y; loadMasterKpi(); }", eski_yil)
            pg.wait_for_timeout(400)
            ev(pg, "y => { document.getElementById('kpi-year').value = y; loadMasterKpi(); }", _tk.year)
            pg.wait_for_timeout(1200)
            yangi = t(snap(pg, ["mkList"]), "mkList")
            if ushla:
                jv(ushla[0], 200, {"year": eski_yil, "total_gift": 999999, "masters": [{"id": 77, "name": "ESKI YIL USTASI", "region": "",
                   "kpi_percent": 1, "gift_amount": 999999, "yearly_sales": 1, "yearly_profit": 1, "orders_count": 1}]})
            pg.wait_for_timeout(1000)
            o = snap(pg, ["mkList", "k-total-gift", "k-year"])
            check("K4a yil: eski yil ro'yxati kech keldi — tashlanadi (joriy yil ustalari qoladi, «ESKI YIL USTASI» / 999 999 yo'q)",
                  len(ushla) == 1 and t(o, "mkList") == yangi and "ESKI YIL" not in (t(o, "mkList") or "") and t(o, "k-total-gift") == "0 so'm",
                  (len(ushla), t(o, "mkList"), t(o, "k-total-gift")))
            pg.close()
            pg = sahifa(CTX["kl_a"])
            och(pg, "/kpi", 1200)
            ushla = []
            boshqa_oy = _tk.month - 1 if _tk.month > 1 else 12
            pg.route(yol_mos("/api/finance/report"), ushlovchi(ushla, lambda u: f"month={boshqa_oy}&" in u or u.endswith(f"month={boshqa_oy}")))
            ev(pg, "m => { document.getElementById('emp-report-month').value = String(m); loadEmpMonthlyReport(); }", boshqa_oy)
            pg.wait_for_timeout(400)
            ev(pg, "m => { document.getElementById('emp-report-month').value = String(m); loadEmpMonthlyReport(); }", _tk.month)
            pg.wait_for_timeout(1200)
            yangi = t(snap(pg, ["empMonthlyReport"]), "empMonthlyReport")
            if ushla:
                jv(ushla[0], 200, {"hodimlar_breakdown": [{"employee_id": 1, "name": "ESKI OY HODIMI", "detail": "", "amount": 1, "bonus": 0,
                                                           "adjustment": 0, "avans": 0, "qolgan": 1}]})
            pg.wait_for_timeout(1000)
            keyin = t(snap(pg, ["empMonthlyReport"]), "empMonthlyReport")
            check("K4b oylik hisob-kitob: boshqa oy javobi kech keldi — tashlanadi («ESKI OY HODIMI» yo'q, joriy oy jadvali qoladi)",
                  len(ushla) == 1 and keyin == yangi and "ESKI OY" not in (keyin or "") and "Namuna Hodim" in (keyin or ""), (len(ushla), keyin))
            pg.close()

        if bolim("K5"):
            section("K5. Sovg'a davri oynasi — xatoda forma yo'q")
            for tur in ("502_html", "403_json"):
                pg = sahifa(CTX["kl_a"])
                pg.route(yol_mos("/api/gift-period"), XATOLAR[tur])
                och(pg, "/kpi", 1200)
                ev(pg, "() => { openGiftPeriodModal(); }")
                pg.wait_for_timeout(300)
                r = ev(pg, """() => ({matn: (document.getElementById('giftPeriodBox').innerText || '').replace(/\\s+/g, ' ').trim(),
                                       forma: !!document.querySelector('#giftPeriodBox [onclick*="submitOpenGiftPeriod"]'),
                                       pill: document.getElementById('giftPeriodStatusPill').textContent.trim()})""")
                check(f"K5 {tur}: oynada «Sovg'a davri yuklanmadi — …», «Davrni ochish» formasi YO'Q, holat «—» (yolg'on «Yopiq» emas)",
                      isinstance(r, dict) and r.get("matn") == matn("Sovg'a davri", tur) and not r.get("forma") and r.get("pill") == "—", r)
                pg.close()

        if bolim("K6"):
            section("K6. KPI oynalari — xatoda sabab")
            OYNA = [("/kpi-detail", "() => { openMasterDetail(document.querySelector('.mk-tugmalar').dataset.id, 'Namuna Usta'); }",
                     "md-list", "Buyurtmalar bo'yicha KPI"),
                    ("/advances", "() => { openAdvanceModal(1, 'Namuna Hodim'); }", "adv-history", "Bu oy avanslari"),
                    ("/compensation-history", "() => { loadCompHistory(1); }", "ch-list", "To'lov tarixi")]
            for qism, kod, quti, nima in OYNA:
                for tur in ("502_html", "500_json"):
                    pg = sahifa(CTX["kl_a"])
                    och(pg, "/kpi", 1200)
                    pg.route(yol_mos(qism), XATOLAR[tur])
                    ev(pg, kod)
                    pg.wait_for_timeout(700)
                    o = snap(pg, [quti, "adv-total"])
                    qosh = (t(o, "adv-total") == "—") if quti == "adv-history" else True
                    check(f"K6 {qism} {tur}: oynada «{nima} yuklanmadi — …»", t(o, quti) == matn(nima, tur) and qosh and not pg.__xato,
                          (t(o, quti), t(o, "adv-total"), pg.__xato[:1]))
                    pg.close()

        if bolim("K7"):
            section("K7. Ustalar KPI — rollar (HAQIQIY server)")
            for user, bor, yoq, sorov_yoq in (
                    ("kl_a", ["empList", "k-emp-count", "k-emp-calculated", "empMonthlyReport", "mkInactiveWrap"], [], []),
                    ("kl_mol", ["k-emp-calculated", "empMonthlyReport", "mkList"], ["empList", "k-emp-count", "mkInactiveWrap"],
                     ["/api/employees", "/api/masters"]),
                    ("kl_kpi", ["mkList", "giftPeriodStatusPill"], ["empList", "k-emp-count", "k-emp-calculated", "empMonthlyReport",
                                                                    "mkInactiveWrap"],
                     ["/api/employees", "/api/masters", "/api/finance/report"])):
                pg = sahifa(CTX[user])
                och(pg, "/kpi", 1400)
                o = snap(pg, K_IDS + ["mkList", "giftPeriodStatusPill"])
                rad = [j for j in pg.__javob if j[1] >= 400]
                _yollar = [y for y, _ in pg.__javob]
                check(f"K7 {user}: blok bor {bor}, yo'q {yoq}; so'ralmaydi {sorov_yoq}; 403 / xato javob yo'q; sabablar yashirin",
                      all((o.get("el") or {}).get(i) is not None for i in bor) and all((o.get("el") or {}).get(i) is None for i in yoq)
                      and not any(y in _yollar for y in sorov_yoq) and not rad and not any(v(o, i) for i in K_XATO_IDLAR)
                      and not pg.__xato and "Namuna Usta" in (t(o, "mkList") or ""),
                      ([i for i in bor if (o.get("el") or {}).get(i) is None], [i for i in yoq if (o.get("el") or {}).get(i) is not None],
                       [y for y in sorov_yoq if y in _yollar], rad, pg.__xato[:1]))
                pg.close()

        # ══════════════════════════════════════════════════════════════
        # LOYIHALAR
        # ══════════════════════════════════════════════════════════════
        def loyiha(pg, kut=1300):
            och(pg, "/projects", 800)
            xav(pg.click, ".proj-card")
            pg.wait_for_timeout(kut)

        def bolimga(pg, tab, kut=1400):
            ev(pg, "t => { switchTab(t); }", tab)
            pg.wait_for_timeout(kut)
            return ev(pg, """() => ({matn: (document.getElementById('tabContent').innerText || '').replace(/\\s+/g, ' ').trim(),
                                    qatorlar: [...document.querySelectorAll('#tabContent .yuk-xato-qator')].map(e => e.innerText.trim()),
                                    rang: [...document.querySelectorAll('#tabContent .yuk-xato-qator, #tabContent .yuk-xato')].map(e => getComputedStyle(e).color),
                                    bolim: currentTab})""")

        P_ASL = {}
        if bolim("P1") or bolim("P2"):
            section("P1. Loyihalar — hammasi yuklandi")
            pg = sahifa(CTX["kl_a"])
            loyiha(pg)
            P_ASL = snap(pg, P_IDS)
            r = ev(pg, "() => document.getElementById('tabBar').dataset.bolimlar")
            check("P1a holat paneli: «🏭 Bajarilgan 100%», «🚚 Hammasi topshirildi»; kartada «🏭 Bajarilgan 100%»; sabablar yashirin",
                  t(P_ASL, "sp-bajarilgan") == "100%" and t(P_ASL, "sp-yetkazish") == "Hammasi topshirildi"
                  and t(P_ASL, "pbaj-1") == "🏭 Bajarilgan 100%" and not v(P_ASL, "xato-bajarilgan") and not v(P_ASL, "xato-yetkazish")
                  and not pg.__xato, (t(P_ASL, "sp-bajarilgan"), t(P_ASL, "sp-yetkazish"), t(P_ASL, "pbaj-1"), pg.__xato[:1]))
            check("P1b admin — hamma bo'lim (`data-bolimlar`)", r == "asosiy,orders,yuklar,finance,payments,products,materials,timeline,notes", r)
            _bor = []
            for tab, (_yl, kut) in BOLIM_YOL.items():
                rr = bolimga(pg, tab)
                if not (isinstance(rr, dict) and kut in rr.get("matn", "") and not rr.get("qatorlar")):
                    _bor.append((tab, (rr or {}).get("matn", "")[:120] if isinstance(rr, dict) else rr))
            check("P1c har bo'lim xatosiz to'ldi (moliya, to'lovlar, mahsulotlar, xomashyo, tarix, buyurtmalar, yuk xatlari)", not _bor, _bor)
            pg.close()

        if bolim("P2") and P_ASL:
            section("P2. Loyihalar — bajarilish xaritasi va yetkazish holati × xato")
            for yol, sid, nima, qiymatlar in (
                    ("/api/projects/progress-map", "xato-bajarilgan", "Bajarilish foizi", {"sp-bajarilgan": "—", "pbaj-1": "🏭 Bajarilgan —"}),
                    ("/topshirish", "xato-yetkazish", "Yetkazish holati", {"sp-yetkazish": "—"})):
                for tur, xf in XATOLAR.items():
                    if not tanlangan(yol, tur):
                        continue
                    pg = sahifa(CTX["kl_a"])
                    pg.route(yol_mos(yol), xf)
                    loyiha(pg)
                    o = snap(pg, P_IDS)
                    x = [(i, t(o, i), w) for i, w in qiymatlar.items() if t(o, i) != w]
                    e = (o.get("el") or {}).get(sid) or {}
                    if not (e.get("v") and e.get("t") == matn(nima, tur) and e.get("c") == QIZIL):
                        x.append(("sabab", sid, e))
                    f = farqlar(o, P_ASL, set(qiymatlar) | {sid, "statusPanel", "yukSessiya"})
                    if f:
                        x.append(("boshqa joy o'zgardi", f[:4]))
                    sessiya_tekshir(o, tur, x)
                    if pg.__xato:
                        x.append(("JS xatosi", pg.__xato[:2]))
                    check(f"P2 {yol} {tur}: «—» va panel ostida sabab (abadiy «…» / yolg'on emas)", not x, x)
                    pg.close()

        if bolim("P3"):
            section("P3. Loyihalar — bo'limlar × so'rov × xato")
            for tab, (yollar, kut) in BOLIM_YOL.items():
                for yol, nima in yollar:
                    pg = None
                    for tur, xf in XATOLAR.items():
                        if not tanlangan(yol + " " + tab, tur):
                            continue
                        if pg is None:          # bitta sahifa — har xato turi uchun yo'naltirish almashtiriladi (tezlik)
                            pg = sahifa(CTX["kl_a"])
                            loyiha(pg, 900)
                        bolimga(pg, "notes", 300)
                        pred = yol_mos(yol)
                        pg.route(pred, xf)
                        js0 = len(pg.__xato)
                        r = bolimga(pg, tab)
                        xav(pg.unroute, pred)
                        x = []
                        if not isinstance(r, dict):
                            x.append(("baho yo'q", r))
                        elif tab == "finance":
                            if not (r["matn"] == f"Loyiha qiymati 1 644 000 so'm To'langan 1 000 000 so'm Qarz 644 000 so'm Sof foyda — "
                                                f"{matn(nima, tur)}"):
                                x.append(("moliya", r["matn"]))
                        elif nima:
                            if r["qatorlar"] != [matn(nima, tur)] or r["matn"] != matn(nima, tur):
                                x.append(("bo'lim sababi", r["matn"][:200]))
                        else:
                            kutq = [matn(f"{n} {BUYURTMA_SOZ[yol]}", tur) for n in ("ORD-001-2", "ORD-001-1")]
                            if r["qatorlar"] != kutq:
                                x.append(("buyurtma sabablari", r["qatorlar"]))
                            if tab == "timeline" and "Buyurtma yaratildi — ORD-001-2" not in r["matn"]:
                                x.append(("tarix — buyurtma voqealari yo'qoldi", r["matn"][:200]))
                        if isinstance(r, dict) and any(c != QIZIL for c in r.get("rang") or []):
                            x.append(("rang", r.get("rang")))
                        if isinstance(r, dict) and r.get("bolim") != tab:
                            x.append(("bo'lim", r.get("bolim")))
                        if pg.__xato[js0:]:
                            x.append(("JS xatosi", pg.__xato[js0:js0 + 2]))
                        check(f"P3 {tab} {yol} {tur}: aniq sabab (yolg'on «0 so'm» / «yo'q» / sababsiz «Yuklashda xato» emas)", not x, x)
                    if pg is not None:
                        pg.close()
                    if nima is None and tanlangan(yol + " " + tab, "500_json"):
                        pg = sahifa(CTX["kl_a"])
                        loyiha(pg, 900)
                        bolimga(pg, "notes", 300)
                        sana = []

                        def _bir_yasa(sana):
                            def _bir(r_):
                                sana.append(1)
                                if len(sana) == 1:
                                    return jv(r_, 500, {"detail": "Ichki xato"})
                                return r_.continue_()
                            return _bir
                        pg.route(yol_mos(yol), _bir_yasa(sana))
                        r = bolimga(pg, tab)
                        _kutq = [matn(f"ORD-001-2 {BUYURTMA_SOZ[yol]}", "500_json")]
                        _qolgan = {"payments": "100 000 so'm", "materials": "ORD-001-1", "timeline": "To'lov qabul qilindi"}[tab]
                        check(f"P3 {tab} {yol} bittasi 500: o'sha buyurtma — sabab, qolgan buyurtmalar ma'lumoti chiziladi («{_qolgan}»)",
                              isinstance(r, dict) and r["qatorlar"] == _kutq and _qolgan in r["matn"] and "0 so'm ·" not in r["matn"],
                              r if not isinstance(r, dict) else (r["qatorlar"], r["matn"][:200]))
                        pg.close()

        if bolim("P4"):
            section("P4. Loyihalar — poyga: kech kelgan javob boshqa bo'lim ustiga yozilmaydi")
            BIRINCHI = {"finance": "/detail-stats", "payments": "/api/orders", "products": "/items", "materials": "/api/orders",
                        "timeline": "/api/orders", "yuklar": "/yuk-xatlari"}
            for tab, qism in BIRINCHI.items():
                pg = sahifa(CTX["kl_a"])
                loyiha(pg, 900)
                bolimga(pg, "notes", 300)
                ushla = []

                def _yasa(ushla):
                    def _tut(r_):
                        if not ushla:
                            ushla.append(r_)
                        else:
                            r_.continue_()
                    return _tut
                pg.route(yol_mos(qism), _yasa(ushla))
                ev(pg, "t => { switchTab(t); }", tab)
                pg.wait_for_timeout(500)
                oldin = bolimga(pg, "orders", 1300)
                for r_ in ushla:
                    xav(r_.continue_)
                pg.wait_for_timeout(1500)
                keyin = ev(pg, "() => ({matn: (document.getElementById('tabContent').innerText || '').replace(/\\s+/g, ' ').trim(), bolim: currentTab})")
                check(f"P4 {tab}: «Buyurtmalar» ochilgandan keyin kelgan «{tab}» javobi tashlandi (ochiq bo'lim o'zgarmadi)",
                      len(ushla) == 1 and isinstance(oldin, dict) and isinstance(keyin, dict) and keyin.get("bolim") == "orders"
                      and keyin.get("matn") == oldin.get("matn") and "ORD-001-1" in keyin.get("matn", ""),
                      (len(ushla), (oldin or {}).get("matn", "")[:80] if isinstance(oldin, dict) else oldin,
                       (keyin or {}).get("matn", "")[:80] if isinstance(keyin, dict) else keyin))
                pg.close()

        if bolim("P4"):
            # so'rovsiz bo'limlar ham navbat oladi: «Asosiy» / «Izohlar» ochilgandan keyin kelgan javob ularni bosmaydi
            for tab, qism, ikkinchi, belgi in (("payments", "/api/orders", "asosiy", "PRJ-001"), ("finance", "/detail-stats", "notes", "umumiy izoh")):
                pg = sahifa(CTX["kl_a"])
                loyiha(pg, 900)
                bolimga(pg, "notes" if ikkinchi == "asosiy" else "asosiy", 300)
                ushla = []
                pg.route(yol_mos(qism), _yasa(ushla))
                ev(pg, "t => { switchTab(t); }", tab)
                pg.wait_for_timeout(500)
                oldin = bolimga(pg, ikkinchi, 600)
                for r_ in ushla:
                    xav(r_.continue_)
                pg.wait_for_timeout(1500)
                keyin = ev(pg, "() => ({matn: (document.getElementById('tabContent').innerText || '').replace(/\\s+/g, ' ').trim(), bolim: currentTab})")
                check(f"P4 {tab} → {ikkinchi}: so'rovsiz bo'lim ochilgandan keyin kelgan «{tab}» javobi tashlandi",
                      len(ushla) == 1 and isinstance(oldin, dict) and isinstance(keyin, dict) and keyin.get("bolim") == ikkinchi
                      and keyin.get("matn") == oldin.get("matn") and belgi in keyin.get("matn", ""),
                      (len(ushla), (oldin or {}).get("matn", "")[:80] if isinstance(oldin, dict) else oldin,
                       (keyin or {}).get("matn", "")[:80] if isinstance(keyin, dict) else keyin))
                pg.close()

        if bolim("P5"):
            section("P5. Loyihalar — rollar (HAQIQIY server)")
            for user, kut_bolim, panel_bor in (
                    ("kl_men", "asosiy,orders,yuklar,payments,products,materials,timeline,notes", True),
                    ("kl_mol", "asosiy,finance,notes", True),
                    ("kl_loy", "asosiy,products,notes", False)):
                pg = sahifa(CTX[user])
                loyiha(pg)
                r = ev(pg, """() => ({bolimlar: document.getElementById('tabBar').dataset.bolimlar,
                                       tugmalar: [...document.querySelectorAll('#tabBar .tab-btn')].map(b => b.dataset.tab).join(','),
                                       panel: !!document.getElementById('sp-bajarilgan') && !!document.getElementById('sp-yetkazish'),
                                       asosiy: (document.getElementById('tabContent').innerText || '').replace(/\\s+/g, ' ')})""")
                for tab in ("orders", "yuklar", "finance", "payments", "products", "materials", "timeline", "notes", "asosiy"):
                    bolimga(pg, tab, 900)
                oxir = ev(pg, "() => currentTab")
                rad = [j for j in pg.__javob if j[1] >= 400]
                _yollar = [y for y, _ in pg.__javob]
                _sabab = ev(pg, "() => [...document.querySelectorAll('.yuk-xato-qator, .yuk-xato')].filter(e => !e.hidden && (e.offsetWidth || e.offsetHeight)).length")
                _bl = kut_bolim.split(",")
                _tugmalar_asosiy = isinstance(r, dict) and all(
                    (yozuv in r.get("asosiy", "")) == (tab_ in _bl)
                    for yozuv, tab_ in (("Buyurtmalari", "orders"), ("To'lovlarni ko'rish", "payments"), ("Mahsulotlar ro'yxati", "products")))
                _asosiy_ok = isinstance(r, dict) and "PRJ-001" in r.get("asosiy", "")
                check(f"P5 {user}: bo'limlar «{kut_bolim}» (tugmalar ham), holat paneli {'bor' if panel_bor else 'YOQ'}; hamma bo'limga o'tish — 403 "
                      "yo'q, ruxsatsiz bo'lim «Asosiy» ga qaytadi; «Asosiy» dagi tugmalar ham ruxsat bo'yicha",
                      isinstance(r, dict) and r.get("bolimlar") == kut_bolim and r.get("tugmalar") == kut_bolim and r.get("panel") == panel_bor
                      and _asosiy_ok and _tugmalar_asosiy and oxir == "asosiy" and not rad and not _sabab and not pg.__xato
                      and (panel_bor or "/api/projects/progress-map" not in _yollar),
                      (r, oxir, rad, _sabab, pg.__xato[:1]))
                pg.close()

        if bolim("T"):
            section("T. Telefon 390 / 320 px — hamma so'rov xato")
            for w in (390, 320):
                for tema in ("light", "dark"):
                    ctx = kontekst("kl_a", w=w, h=844)
                    for url, eng_kam in (("/kpi", 6), ("/projects", 2)):
                        pg = sahifa(ctx)
                        if tema == "dark":
                            pg.add_init_script("try { localStorage.setItem('theme', 'dark'); } catch (e) {}")
                        pg.route(lambda u: urlparse(u).path.startswith("/api/") and urlparse(u).path != "/api/notifications",
                                 XATOLAR["500_json"])
                        och(pg, url, 1300)
                        if url == "/projects":
                            xav(pg.click, ".proj-card")
                            pg.wait_for_timeout(800)
                            ev(pg, "t => { switchTab(t); }", "payments")
                            pg.wait_for_timeout(600)
                        if tema == "dark":
                            ev(pg, "() => document.documentElement.setAttribute('data-theme', 'dark')")
                            pg.wait_for_timeout(200)
                        r = ev(pg, KONTRAST)
                        els = (r or {}).get("el") or [] if isinstance(r, dict) else []
                        yomon = [e for e in els if e["kontrast"] < 4.5 or e["ong"] > r["vw"] + 1 or e["chap"] < -1 or e["toshgan"]]
                        check(f"T {url} {w} px {tema}: sahifa toshmaydi (eni {w}), sabablar ekranda, qutisidan chiqmaydi va o'qiladi "
                              f"(kontrast ≥ 4.5), kamida {eng_kam} ta sabab",
                              isinstance(r, dict) and r.get("sw", 9999) <= w + 1 and len(els) >= eng_kam and not yomon and not pg.__xato,
                              (r.get("sw") if isinstance(r, dict) else r, len(els), yomon[:4], pg.__xato[:1]))
                        pg.close()
                    ctx.close()

        for c in CTX.values():
            c.close()
        br.close()
    server.should_exit = True

print("\n" + "=" * 70)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   -", f)
sys.exit(1 if FAIL else 0)
