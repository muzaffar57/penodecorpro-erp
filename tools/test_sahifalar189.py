#!/usr/bin/env python3
"""
test_sahifalar189.py — kech147 (zip 189): PRODUCTION skrinshotidan kichik ko'rinish nuqsonlari (16.10 23:24) va server chizadigan summalar
bitta son qoidasida. HAQIQIY Chromium (Playwright, `is_mobile`, `has_touch`, `device_scale_factor=2`), HAQIQIY lokal server, telefon brauzer
paneli bilan ko'rinadigan qism (375 × 548, 360 × 560, 320 × 460) va YOTIQ telefon (667 × 375).

NIMA UCHUN KERAK (staging da O'LCHANGAN, 384 px — `work/kech147_holat.md` 23:25):
  Q1 Moliya «Sof holat (bizga qarz − bizdan qarz)»: yorliq (2 qator, 33–231 px) va qiymat (231–346 px) orasida 0 px — «bizdan + 33,9 mln»
     yopishgan (flex, `gap` yo'q).
  Q2 Telefonda karta bo'lgan jadval katagida ikki tugun (Hisobotlar «Ombor» — holat nuqtasi + qoldiq; «Tayyor mahsulot yo'qotishlari» —
     «Tashlandi» + 🧩): `justify-content:space-between` birinchisini kartaning O'RTASIGA qo'yardi (nuqta 165–172 px, qiymat 256–320 px).
  Q4 Shablonda server chizadigan 21 ta summa (Qarzdorlar 14, Buyurtmalar 3, Qaytarishlar 2, Ombor 1, Retseptlar 1) — oddiy bo'shliq
     (tor ekranda raqam qator oxirida bo'linadi) va `"{:,.2f}"` — nuqtali kasr («1 234.50»); endi `|son(0)` / `|son`.
O'lchov — `tools/test_sahifalar186.py` TEKSHIR_JS (X yon tomonga suriladigan o'ram, T tor matn bloki, K kesilgan boshqaruv, M kesilgan matn,
H hujjat eni) va sahifa kontentining yon tomonga surilmasligi; S — statik: qoidalar shablonda / style.css da.
Ma'lumot — ilovaning O'Z API si orqali: `tools/test_c_telefon.py` ZANJIR_JS + `tools/test_oynalar184.py` QOSHIMCHA_JS +
`tools/test_sahifalar186.py` QOSHIMCHA186_JS (matnlari o'qiladi, fayllar BAJARILMAYDI).
REJIM: SQLite (`PG_URL` e'tiborsiz — ko'rinish baza turiga bog'liq emas); `TENANT_FILTER=1` ham. `T189_FAQAT=kalit1,kalit2` — faqat shu holatlar.
Asl kodga (zip 188) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_sahifalar189.py
"""
import os
import re
import io
import sys
import ast
import glob
import time
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
_T = tempfile.mkdtemp(prefix="sahifa189_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'sahifa189.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402

REJIM = "[TF1] " if os.environ.get("TENANT_FILTER") == "1" else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    return open(os.path.join(ROOT, yol), encoding="utf-8").read()


def _src_const(yol, nom):
    """Boshqa test faylidagi satr qiymatini faylni BAJARMASDAN o'qiydi."""
    tree = ast.parse(oqi(yol))
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == nom for t in n.targets):
            return ast.literal_eval(n.value)
    raise KeyError(nom)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik: qoidalar shablonda / style.css da")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_FN = oqi("templates/finance.html")
check("S1 Moliya «Sof holat» — yorliq va qiymat orasida joy (`gap`), sig'masa qiymat keyingi qatorda o'ngda, qiymat bo'linmaydi",
      '<div class="dg-sof" style="margin-top:14px;padding-top:14px;border-top:1px dashed var(--ch-e2e8f0);display:flex;flex-wrap:wrap;'   # kech155 (zip 208 — «Toza ko'k», MOSLANDI)
      'justify-content:space-between;align-items:center;gap:4px 12px">' in _FN
      and '<span style="font-size:18px;font-weight:800;white-space:nowrap;margin-left:auto" id="dg-net">—</span>' in _FN)
_CSS = oqi("static/style.css")
_ONCE = ("table.telefon-karta > tbody > tr > td::before { content: attr(data-label); color: var(--text3); font-size: 12px; font-weight: 600; "
         "text-align: left; flex-shrink: 0; max-width: 45%; margin-right: auto; }")
check("S2 telefon-karta katagi — yorliq chapda, katakdagi HAMMA tugun birga o'ngda (`::before` — `margin-right:auto`), ≤ 600 px va yotiq "
      "telefon bloklarida", _CSS.count(_ONCE) == 2 and "max-width: 45%; }" not in _CSS, _CSS.count(_ONCE))
_MAIN = oqi("main.py")
_sv = re.search(r'templates\.env\.globals\["static_version"\]\s*=\s*"([^"]+)"', _MAIN)
check("S3 kesh versiyasi yangilangan (style.css o'zgardi — telefonda eski uslub keshdan olinmasin): «20261016-1» dan keyingi",
      _sv and _sv.group(1) > "20261016-1", _sv.group(1) if _sv else None)
_TPL = {f: oqi(os.path.join("templates", f)) for f in sorted(os.listdir(os.path.join(ROOT, "templates"))) if f.endswith(".html")}
_ODDIY = {f: t.count('.replace(",", " ")') for f, t in _TPL.items() if '.replace(",", " ")' in t}
check("S4 shablonlarda server summasi oddiy bo'shliq bilan (`.replace(\",\", \" \")`) — YO'Q (hammasi `|son` / `|son(0)`)", not _ODDIY, _ODDIY)
_SON = ["{{ (total_customer_debt)|son(0) }}", "{{ (total_supplier_debt)|son(0) }}", "{{ (total_ortiqcha)|son }}", "{{ (g.jami)|son }}",
        "{{ (o.debt_amount)|son(0) }}", "{{ (ort)|son }}", "{{ (s.debt)|son(0) }}", "{{ (e.qolgan)|son(0) }}", "oylik {{ (e.amount)|son(0) }}",
        "{{ (e.avans)|son(0) }}", "{{ (e.qarz)|son(0) }}", "{{ (r.target)|son(0) }}", "{{ (r.paid)|son(0) }}", "{{ (r.debt)|son(0) }}"]
_yoq = [x for x in _SON if x not in _TPL["debts.html"]]
check("S5 Qarzdorlar — 14 ta summa `|son(0)` / `|son` (kasrli qolgan / ortiqcha — ortiqcha nolsiz, vergul bilan)", not _yoq, _yoq)
_yoq2 = [x for f, x in [("inventory.html", '{{ (item.price_per_unit)|son(0) if item.price_per_unit else "—" }}'),
                        ("orders.html", "{{ (o.kelishilgan_summa)|son(0) }}"), ("orders.html", "{{ (ort131)|son }}"),
                        ("orders.html", "{{ (debt)|son(0) }}"), ("recipes.html", "{{ (ins.cost_per_kg)|son(0) }}"),
                        ("returns.html", "{{ (r.refund_amount)|son(0) }}"), ("returns.html", "{{ ((brak_zarar or {}).get(r.id))|son(0) }}")]
         if x not in _TPL[f]]
check("S6 Ombor narxi, Buyurtmalar (kelishilgan summa, qaytarish, qarz), Retsept 1 kg tannarxi, Qaytarishlar (qaytarilgan pul, brak zarari) — "
      "`|son(0)` / `|son`", not _yoq2, _yoq2)
check("S7 Qaytarishlar — telefonda `margin-left:auto` FAQAT qaytarish kartasidagi tugmalarga (`.ret-row > .mini-btn`; Brak tahlili 🧩 ga tegmaydi)",
      "  .ret-row > .mini-btn{ order:99; flex-shrink:0; margin-left:auto; }" in oqi("templates/returns.html")
      and "\n  .mini-btn{ order:99; flex-shrink:0; margin-left:auto; }" not in oqi("templates/returns.html"))
# kech154 (zip 203 «Buyurtmalar ko'rinishi», MOSLANDI): ustuvor qator — summa o'z joyida (`.oi-summa`), muddat — alohida belgi
check("S8 Buyurtmalar ro'yxati (brauzer chizadi) — summa `sonKor(amount, 0)` (bo'linmas bo'shliq)",
      "<span class=\"oi-summa\">${sonKor(amount, 0)} so'm</span>" in oqi("templates/orders.html") and "${formatNum(amount)} so'm</span>" not in oqi("templates/orders.html"))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Ma'lumot va o'lchov
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "s189_admin", "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, ADMIN, PAROL, UserRole.ADMIN, "Andijon Fasad Dekor Bosh Administratori", company_id=1)
    s.commit()
s.close()

ZANJIR_JS = _src_const("tools/test_c_telefon.py", "ZANJIR_JS")
CHART_ORINBOSAR = _src_const("tools/test_c_telefon.py", "CHART_ORINBOSAR")
QOSHIMCHA_JS = _src_const("tools/test_oynalar184.py", "QOSHIMCHA_JS")
M = _src_const("tools/test_oynalar184.py", "M")
UZUN = _src_const("tools/test_oynalar184.py", "UZUN")

# zip 186 testidagi qo'shimcha ma'lumot (shu oy ichida ishga kirgan hodim, «oylik + metr», ishbay hodim) va o'lchov — o'sha fayldan
QOSHIMCHA186_JS = _src_const("tools/test_sahifalar186.py", "QOSHIMCHA186_JS")
TEKSHIR_JS = _src_const("tools/test_sahifalar186.py", "TEKSHIR_JS")

SLEEP = "const uxla = ms => new Promise(r => setTimeout(r, ms));"
KAT = []


def holat(k, kod, url, och, root, kut=800, tekshir="XTKM", qosh=None, izoh="", ruxsat=None):
    """tekshir — qaysi o'lchovlar talab qilinadi (X / T / K / M; H — hujjat eni har doim); qosh — [(nom, JS, shart(qiymat, w, h))]"""
    KAT.append(dict(k=k, kod=kod, url=url, och=och, root=root, kut=kut, tekshir=tekshir, qosh=qosh or [], izoh=izoh, ruxsat=ruxsat))


def _telefon_karta(w, h):
    """style.css `table.telefon-karta` qoidasi qo'llanadigan o'lcham (≤ 600 px YOKI yotiq telefon ≤ 950 × 500)"""
    return w <= 600 or (w <= 950 and h <= 500)


# Q1 — «Sof holat»: production dagi qiymat («+ 33,9 mln so'm» — 16.10 23:24 skrinshoti) qo'yiladi (faqat ko'rinish). Yorliq va qiymat bir
# qatorda bo'lsa orasi ≥ 8 px; qiymat keyingi qatorga o'tsa — o'ng chetda; qiymat o'zi bitta satrda
_SOF = ("() => { const v = document.getElementById('dg-net'); if (!v) return null; const q = v.parentElement; const y = q.children[0];"
        " const A = y.getBoundingClientRect(), B = v.getBoundingClientRect(), Q = q.getBoundingClientRect();"
        " const rg = document.createRange(); rg.selectNodeContents(v); const satr = new Set([...rg.getClientRects()].filter(r => r.width > 0.5).map(r => Math.round(r.top))).size;"
        " const birga = B.top < A.bottom - 2 && B.bottom > A.top + 2;"
        " return {birga, oraliq: Math.round(B.left - A.right), ong: Math.round(Q.right - B.right), satr}; }")
holat("moliya_sof", "Q1", "/finance",
      "await uxla(2500); const v = document.getElementById('dg-net'); v.textContent = '+ 33,9 mln so\\'m'; await uxla(200);",
      "div:has(> #dg-net)", izoh="«Sof holat» — production dagi qiymat",
      qosh=[("yorliq va qiymat yopishmaydi (bir qatorda — orasi ≥ 8 px; keyingi qatorda — o'ng chetda), qiymat bitta satrda", _SOF,
             lambda v, w, h: isinstance(v, dict) and v.get("satr") == 1 and ((v["oraliq"] >= 8) if v["birga"] else (v["ong"] <= 2)))])

# Q2 — telefon-karta katagida bir nechta tugun (holat nuqtasi + qoldiq; «Tashlandi» + 🧩): tugunlar BIRGA o'ngda — qo'shni tugunlar orasi
# ≤ 24 px (nuqta o'ng chekkasi 7 px + `gap` 12 px), oxirgisi katak o'ng chetida. Ustunli jadval (karta emas) — tekshirilmaydi
_KOP = ("(sel) => [...document.querySelectorAll(sel + ' > tbody > tr > td')].filter(td => td.offsetParent && getComputedStyle(td).display === 'flex').map(td => {"
        " const t = [...td.childNodes].filter(n => (n.nodeType === 3 && n.textContent.trim()) || (n.nodeType === 1 && getComputedStyle(n).display !== 'none' && n.getBoundingClientRect().width > 0));"
        " if (t.length < 2) return null; const rr = t.map(n => { let b; if (n.nodeType === 3) { const r = document.createRange(); r.selectNodeContents(n); b = r.getBoundingClientRect(); } else b = n.getBoundingClientRect(); return [b.left, b.right]; });"
        " const tr = td.getBoundingClientRect(); let oraliq = 0; for (let i = 1; i < rr.length; i++) oraliq = Math.max(oraliq, rr[i][0] - rr[i - 1][1]);"
        " return {yorliq: td.getAttribute('data-label'), n: t.length, oraliq: Math.round(oraliq), ong: Math.round(tr.right - rr[rr.length - 1][1])}; }).filter(x => x)")


def _birga(yorliq):
    def shart(v, w, h):
        if not isinstance(v, list):
            return False
        if not _telefon_karta(w, h):
            return True
        bu = [x for x in v if x.get("yorliq") == yorliq]
        return len(bu) >= 1 and all(x["oraliq"] <= 24 and x["ong"] <= 2 for x in v)
    return shart


holat("ombor_qoldiq", "Q2", "/reports", "switchReport('inventory'); await uxla(2500);", ".bi-section-table", izoh="«Ombor» hisoboti",
      qosh=[("«Qoldiq» katagida holat nuqtasi qiymat YONIDA (katakdagi tugunlar birga o'ngda — orasi ≤ 24 px)",
             "() => (" + _KOP + ")('#repTable')", _birga("Qoldiq"))])
# «Tayyor mahsulot yo'qotishlari» — sinov bazasida yo'qotish yozuvi bo'lmasa sahifaning O'Z chizuvchisi (`brakTahlilHtml`) serverdan kelgan
# tahlilga BITTA namuna qator qo'shib chiziladi (ko'rinish tekshiriladi, ma'lumot yozilmaydi; zip 187 testi bilan bir usul)
_BRAK = ("toggleBrakTahlil(); await uxla(1800); const d = await (await fetch('/api/reports/brak-tahlil?oylar=6', {credentials: 'same-origin'})).json();"
         " if (!(d.yoqotishlar || []).length) d.yoqotishlar = [{id: 990001, sana: '2026-10-10T09:30:00', nomi: window.__M + ' Fasad ustuni (namuna, sinov)', miqdor: 3, birlik: 'dona',"
         " turi: 'Brak', bosqich: 'Qoplash', sabab: 'Qoplama ko\\'chdi', javobgar: window.__M + ' Usta', qiymat: 1234567, yozgan: 'admin', taqdir_yorliq: 'Tashlandi', manba: 'ombor'}];"
         " document.getElementById('brakTahlilContent').innerHTML = brakTahlilHtml(d); await uxla(300);")
holat("brak_taqdir", "Q2", "/returns", _BRAK, "#brakTahlilBody", izoh="«Tayyor mahsulot yo'qotishlari» — «Taqdiri» katagi",
      qosh=[("«Taqdiri» katagida yozuv va 🧩 birga o'ngda (orasi ≤ 24 px)", "() => (" + _KOP + ")('.brak-yoqotish-jadval')", _birga("Taqdiri"))])

# Q4 — server chizadigan summalar: raqam ichida ODDIY bo'shliq yo'q (bo'linmas bo'shliq — qator oxirida bo'linmaydi), nuqtali kasr yo'q;
# kamida bitta ≥ 1 000 summa (ajratgichli) ko'rinadi
_SUMMA = ("(sel) => [...document.querySelectorAll(sel)].filter(e => e.offsetParent && /\\d/.test(e.textContent))"
          ".map(e => e.textContent.trim()).map(t => { const u = t.replace(/\\d{2}\\.\\d{2}\\.\\d{4}/g, ' '); return {t: t.slice(0, 60), oddiy: /\\d \\d/.test(u),"
          " nuqta: /\\d\\.\\d/.test(u), nb: /\\d\\u00a0\\d/.test(u)}; })")


def _summa_shart(eng_kam_nb=1):
    def shart(v, w, h):
        return (isinstance(v, list) and len(v) >= 1 and not any(x["oddiy"] or x["nuqta"] for x in v)
                and sum(1 for x in v if x["nb"]) >= eng_kam_nb)
    return shart


holat("qarz_summalar", "Q4", "/debts", "await uxla(900);", ".dbt-summary-grid", izoh="Qarzdorlar — umumiy summalar va mijoz qarzlari",
      qosh=[("summalar bo'linmas bo'shliq bilan (oddiy bo'shliq / nuqtali kasr yo'q)",
             "() => (" + _SUMMA + ")('.dbt-summary-value, .dbt-item-amount')", _summa_shart())])
holat("qarz_korxona_summalar", "Q4", "/debts", "switchTab('company'); await uxla(900);", "#tab-company", izoh="«Bizning qarzlarimiz»",
      qosh=[("summalar bo'linmas bo'shliq bilan (hodim / ta'minotchi / majburiyat qarzi)",
             "() => (" + _SUMMA + ")('#tab-company .oblig-summa, #tab-company .oblig-item div[style*=\"font-weight:800\"]')",
             _summa_shart())])
holat("buyurtma_summalar", "Q4", "/orders", "await uxla(900);", None, izoh="Buyurtmalar ro'yxati — kelishilgan summa",
      tekshir="X", qosh=[("summalar bo'linmas bo'shliq bilan", "() => (" + _SUMMA + ")('.ord-date')", _summa_shart())])
holat("retsept_summalar", "Q4", "/recipes", "await uxla(800);", ".rec-grid", izoh="Retseptlar — 1 kg tannarxi", tekshir="X",
      qosh=[("summalar bo'linmas bo'shliq bilan", "() => (" + _SUMMA + ")('.rec-stat-val')", _summa_shart())])
holat("ombor_narx", "Q4", "/inventory", "await uxla(900);", None, izoh="Ombor — 1 birlik narxi", tekshir="X",
      qosh=[("narxlar bo'linmas bo'shliq bilan", "() => (" + _SUMMA + ")('[id^=\"price-\"]')", _summa_shart())])

FAQAT = [x.strip() for x in os.environ.get("T189_FAQAT", "").split(",") if x.strip()]

try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
import uvicorn                                     # noqa: E402


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
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
B = f"http://127.0.0.1:{port}"
tk = datetime.utcnow() + timedelta(hours=5)
K = {"m": M, "sana": tk.strftime("%Y-%m-%d"), "yil": tk.year, "oy": tk.month, "muddat": (tk + timedelta(days=9)).strftime("%Y-%m-%d")}
OLCHAMLAR = [(375, 548), (360, 560), (320, 460), (667, 375)]


def yonalish(route):
    u = route.request.url
    if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
        return route.fulfill(status=200, content_type="application/javascript", body=CHART_ORINBOSAR)
    if u.startswith("https://fonts.googleapis.com/"):
        return route.fulfill(status=200, content_type="text/css", body="")
    return route.fulfill(status=204, body="")


section("T. Server, brauzer, ma'lumot")
check("T0 lokal server va Playwright", bool(server.started and PW_BOR), _pw_x)
JS_XATO = []
if server.started and PW_BOR:
    with sync_playwright() as pw:
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*", "chrome-linux",
                                                  "chrome"))):
            _exe = _yol
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def kontekst(w, h):
            ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                 timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|cdn\.jsdelivr\.net|unpkg\.com)/.*"),
                      yonalish)
            pg = ctx.new_page()
            pg.set_default_timeout(15000)
            pg.goto(B + "/login")
            pg.fill("input[name=username]", ADMIN)
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            return ctx, pg

        def js(p, kod, arg=None):
            try:
                return p.evaluate(kod, arg) if arg is not None else p.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        ctx, pg = kontekst(390, 844)
        Z = pg.evaluate(ZANJIR_JS, K)
        Q = pg.evaluate(QOSHIMCHA_JS, {"I": Z.get("I") or {}, "M": M, "U": UZUN, "muddat": K["muddat"], "sana": K["sana"]})
        Q2 = pg.evaluate(QOSHIMCHA186_JS, {"M": M, "yil": tk.year, "oy": tk.month, "kun": tk.day})
        ctx.close()
        I = dict(Z.get("I") or {})
        I.update(Q.get("R") or {})
        I.update(Q2.get("R") or {})
        check("T1 ma'lumot zanjiri (ilovaning o'z API si) — yiqilgan so'rov yo'q",
              not Z.get("yiqilgan") and not Q.get("L") and not Q2.get("L") and I.get("katta") and I.get("hodim3") and I.get("metr"),
              (Z.get("yiqilgan"), Q.get("L"), Q2.get("L"), sorted(I)))
        for w, h in OLCHAMLAR:
            section(f"K. Sahifalar — {w} × {h}" + (" (yotiq telefon)" if w > h else " (telefon brauzer paneli bilan)"))
            ctx, pg = kontekst(w, h)
            pg.on("pageerror", lambda ex, w=w: JS_XATO.append(f"{w}: {str(ex)[:200]}"))
            for e in KAT:
                if FAQAT and e["k"] not in FAQAT:
                    continue
                try:
                    pg.goto(B + e["url"], wait_until="networkidle")
                except Exception:          # noqa: BLE001
                    pass
                pg.wait_for_timeout(500)
                pg.evaluate("(a) => { window.__I = a.I; window.__M = a.M; }", {"I": I, "M": M})
                och = js(pg, "async () => { " + SLEEP + " try { " + e["och"] + " return 'ok'; } catch (ex) { return 'XATO: ' + String(ex); } }")
                pg.wait_for_timeout(e["kut"])
                m = js(pg, TEKSHIR_JS, {"root": e["root"], "ruxsat": e["ruxsat"]})
                nom = f"{e['kod']} {e['k']} @{w}x{h} — {e['root'] or 'sahifa'}" + (f" ({e['izoh']})" if e["izoh"] else "")
                bor = isinstance(m, dict) and not m.get("ildiz_yoq") and not m.get("js_xato")
                check(f"{nom}: ochildi, sahifa ekrandan kengaymaydi (hujjat eni {m.get('hujjat_sw') if isinstance(m, dict) else '?'} ≤ {w})",
                      och == "ok" and bor and m["hujjat_sw"] <= w, (och, m if not bor else m.get("hujjat_sw")))
                if not bor:
                    continue
                if "X" in e["tekshir"]:
                    check(f"{nom}: yon tomonga suriladigan joy yo'q (tugma / ustun birinchi ekranda yashirinmaydi)", not m["xsur"], m["xsur"])
                if "T" in e["tekshir"]:
                    check(f"{nom}: tor matn bloki yo'q (matn < 120 px da 4+ satrga bo'linmaydi)", not m["tor"], m["tor"][:6])
                if "K" in e["tekshir"]:
                    check(f"{nom}: tugma / maydon karta yoki ekran chetida qirqilmaydi", not m["kesilgan"], m["kesilgan"][:6])
                if "M" in e["tekshir"]:
                    check(f"{nom}: matn / summa karta chetida qirqilmaydi", not m["kesik_matn"], m["kesik_matn"][:6])
                # sahifaning o'z (tikka) suriladigan o'ramlari (`overflow-y: auto / scroll`, mazmuni pastga suriladi, eni ≥ 85 %, bo'yi ≥ 50 % ekran —
                # `.erp-content`, `.proj-page` …; yorliq / jadval tasmalari emas) yon
                # tomonga surilmaydi; ichidagi ataylab suriladigan tasmalar (o'z o'rami bilan) bunga ta'sir qilmaydi (667 × 375 da KPI kontenti
                # 667 / 952 px edi — hujjat eni o'zgarmasdan)
                kont = js(pg, "() => [...document.querySelectorAll('body *')].filter(e => { const s = getComputedStyle(e); const r = e.getBoundingClientRect();"
                              " return /(auto|scroll)/.test(s.overflowY) && e.scrollHeight > e.clientHeight + 1 && r.width >= innerWidth * 0.85 && r.height >= innerHeight * 0.5"
                              " && !e.closest('.sidebar, .erp-sidebar, [role=dialog]'); })"
                              ".map(e => [e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0] : ''),"
                              " e.scrollWidth, e.clientWidth])")
                check(f"{nom}: sahifa kontenti yon tomonga surilmaydi (o'ramlarda scrollWidth ≤ clientWidth)",
                      isinstance(kont, list) and all(x[1] <= x[2] + 1 for x in kont), kont)
                for q_nom, q_js, q_shart in e["qosh"]:
                    v = js(pg, q_js)
                    check(f"{nom}: {q_nom}", q_shart(v, w, h), v)
            ctx.close()
        br.close()
    check("T2 sahifalarda JS xatosi yo'q", not JS_XATO, JS_XATO[:5])
server.should_exit = True
th.join(timeout=10)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
