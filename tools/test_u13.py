#!/usr/bin/env python3
"""
test_u13.py — kech123, U-13 YAGONA KO'RINISH (egasi QARORI 02.10 «Avval yagona ko'rinish», `main` keyin) — HAQIQIY brauzerda
(Chromium, Playwright) O'LCHANADI.

NIMA UCHUN KERAK (audit kech114 U-13; kech123 da `work/u13/olchov.py` bilan zip 138 kodida O'LCHANGAN — 23 sahifa, 1440 / 390 px):
  bir xil vazifadagi tugmalar 31 xil balandlikda (15–74 px: «+ Yangi buyurtma» 25, «Kirim qilish» 29, «Кирилл» 27, ombor amallari
  38, «Saqlash» 36…), 11 xil burchakda (0–20 px, yumaloq), tugma yozuvi 12 xil (12 / 12,5 / 13,3 / 13,5 / 17 …), sahifa matni 21 xil
  o'lchamda (12 … 32 px, oraliqda 12,5 / 13,3 / 13,5 / 14,5 / 15,5 / 18,7 / 19 / 25); maydonlar 17 xil balandlikda (27–48 px).
  Har sahifa biroz boshqacha ko'rinardi, har yangi o'zgarish qo'lda ko'p joyda qilinardi.
QOIDA (static/style.css «U-13 — YAGONA KO'RINISH»; o'lchamlar — token, sahifalar klass ishlatadi):
  tugma         kompyuter  telefon (≤ 768)   vazifasi
  .btn-sm         32         36              jadval / qator / karta ichidagi amal
  .btn-md         36         40              yuqori panel, bo'lim sarlavhasidagi amal; `.tab` — ham shu
  .btn            40         44              asosiy amal (forma, oyna, sahifa); `.maydon` — ham shu (yonma-yon tekis)
  .btn-lg         44         48              kirish sahifalari
  .btn-icon — kvadrat, o'lchami yonidagi klassdan; `.chip` (filtr) — `.btn-sm` balandligida, to'liq yumaloq.
  Burchak — 8 px. Yozuv shkalasi: 12 / 13 / 14 / 16 / 18 / 24 / 32 px.
  Sahifalar zip-ma-zip o'tkaziladi — `U13_SAHIFALAR` / `U13_SHABLONLAR` shu ro'yxat bilan o'sadi (zip 139: umumiy qobiq — yon menyu,
  yuqori panel, umumiy oynalar; Bosh sahifa, Dashboard, Hisobotlar, Foydalanuvchilar; zip 140: Buyurtmalar, Loyihalar,
  Omborxona, Kirim qilish, Ta'minotchilar, Loy retseptlari, Ishlab chiqarish, Tayyor mahsulotlar, Qaytarishlar va brak oynasi; zip 141: Qarzdorlar, Moliya, Xarajat qo'shish,
  Ustalar KPI / Hodimlar, Ustalar, Rollar).
  ISTISNO (tugma qoidasidan tashqari, sababi bilan): rasm ustidagi mayda belgilar (`.attach-thumb .rm` / `.dl`, `*-thumb-cam`,
  `.cam-overlay` — rasmni yopmasligi uchun; detal / tayyor mahsulot rasmi `.prod-thumb`, `.fp-thumb`), teg ichidagi «×» (`.fp-tag button`), bosiladigan
  yorliq (`.cat-badge` — toifa yorlig'i, bosilsa tahrirlanadi), matn ichidagi havola-tugma (`.btn-link` — «To'liq to'lash»). Bo'lakli tanlov (`.segment` — «Qoplama: Yo'q / Bor»)
  bitta boshqaruv sifatida o'lchanadi (ichidagi bo'laklar emas). Izohli tanlov tugmasi (`.btn-tanlov` — sarlavha va izoh, masalan
  «O'chirish va xomashyoni qaytarish») va izohli tanlov kartasi (`.tanlov-karta` — rol kartasi: belgi, nom, izoh) — kamida `.btn`
  balandligida, burchak 8 px (balandligi matniga qarab).
BO'LIMLAR: S — statik (style.css tokenlari va klasslari; o'tkazilgan shablonlarda yozuv o'lchamlari shkalada, tugma o'z balandligi /
  ichki joyi / burchagi / yozuvini yozmaydi; kesh versiyasi); M — ma'lumot (brauzerda dasturning o'z API si orqali to'liq ish zanjiri —
  `tools/test_c_telefon.py` ZANJIR_JS); D — o'tkazilgan sahifalar 1440 / 390 px, yorug' / tungi: har tugma, maydon, belgilash katagi, matn o'lchami;
  O — oynalar (umumiy xabar / kiritish / tasdiqlash; Foydalanuvchilar — yangi foydalanuvchi, parol, QR; Dashboard — avans so'rovlari;
  har o'tkazilgan sahifaning oynalari — Buyurtmalar, Loyihalar, Ombor, Kirim, Ta'minotchilar, Retseptlar, Ishlab chiqarish, Tayyor
  mahsulotlar, Qaytarishlar, Brak yozish, Qarzdorlar, Moliya, Ustalar KPI / Hodimlar, Ustalar, Rollar);
  Y — yuqori panel HAMMA sahifada (qobiq bir xil).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 138) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` va Chromium (`PLAYWRIGHT_BROWSERS_PATH` / `/opt/pw-browsers`). Shriftlar va Chart.js tashqi manbadan
  yuklanmaydi (balandlik qat'iy yozuv qatori bilan hisoblanadi — shriftga bog'liq emas).
ISHLATISH: python3 tools/test_u13.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = os.environ.get("U13_PG_BAZA", "u13_test")   # parallel PG yugurishlar bir-biriga tegmasin (etalon bilan bir vaqtda)
_T = tempfile.mkdtemp(prefix="u13_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'u13_test.db')}"
os.environ.pop("TENANT_FILTER", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


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
        print(f"  ✗ {label}   {str(detail)[:1400]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


# ── O'tkazilgan qism (har U-13 zipida kengayadi) ──
U13_SHABLONLAR = ["base.html", "home.html", "dashboard.html", "reports.html", "users.html", "orders.html", "projects.html",
                  "inventory.html", "supplier_receive.html", "suppliers.html", "recipes.html", "production.html", "finished.html",
                  "returns.html", "_brak_oyna.html", "debts.html", "finance.html", "kunlik_xarajat.html", "kpi.html", "masters_manage.html",
                  "rollar.html"]
U13_SAHIFALAR = ["/", "/dashboard", "/reports", "/users", "/orders", "/projects", "/inventory", "/suppliers/receive", "/suppliers", "/recipes",
                 "/production", "/finished", "/returns", "/debts", "/finance", "/kunlik-xarajat", "/kpi", "/ustalar", "/rollar"]
ISTISNO_SEL = (".attach-thumb .rm, .attach-thumb .dl, .prod-thumb, .prod-thumb-cam, .proj-thumb-cam, .mat-thumb-cam, .cam-overlay, "
               ".fp-tag button, .cat-badge, .btn-link, .fp-thumb")
SHKALA = {12.0, 13.0, 14.0, 16.0, 18.0, 24.0, 32.0}
TUGMA_H = {1440: {32.0, 36.0, 40.0}, 390: {36.0, 40.0, 44.0}}
MAYDON_H = {1440: {32.0, 40.0}, 390: {36.0, 44.0}}
TUGMA_FS = {13.0, 14.0, 16.0}
MAYDON_FS = {1440: {13.0, 14.0}, 390: {16.0}}


def bormi(qiymat, toplam, tol=0.6):
    return any(abs(qiymat - x) <= tol for x in toplam)


CSS = oqi("static/style.css")
MAIN = oqi("main.py")
TPL = {os.path.basename(f): open(f, encoding="utf-8").read() for f in sorted(glob.glob(os.path.join(ROOT, "templates", "*.html")))}


def blok(css, sel):
    """`sel {` qoidalari tanasi (sel aniq, oldida boshqa selektor yo'q) — HAMMASI birlashtirilib (asosiy qoida va telefon qoidasi)."""
    return " ".join(m.group(2) for m in re.finditer(r"(^|\n|\}|\{)\s*" + re.escape(sel) + r"\s*\{([^}]*)\}", css))


section("S. Statik — style.css tokenlari, klasslar, yozuv shkalasi; o'tkazilgan shablonlar")
_root = blok(CSS, ":root")
_tok = dict(re.findall(r"--(h-sm|h-md|h-btn|h-lg|r-btn)\s*:\s*([^;]+);", CSS))
_ilk = {}
for _m in re.finditer(r"--(h-sm|h-md|h-btn|h-lg|r-btn)\s*:\s*([\d.]+px)", CSS):
    _ilk.setdefault(_m.group(1), _m.group(2))
check("S1 o'lcham tokenlari: --h-sm 32, --h-md 36, --h-btn 40, --h-lg 44, --r-btn 8 px",
      _ilk == {"h-sm": "32px", "h-md": "36px", "h-btn": "40px", "h-lg": "44px", "r-btn": "8px"}, _ilk)
_tel = re.search(r"@media\s*\(max-width:\s*768px\)\s*\{\s*:root\s*\{([^}]*)\}", CSS)
_telv = dict(re.findall(r"--(h-sm|h-md|h-btn|h-lg|fs-maydon)\s*:\s*([\d.]+px)", _tel.group(1))) if _tel else {}
check("S2 telefonda (≤ 768 px) — barmoq uchun kattaroq: --h-sm 36, --h-md 40, --h-btn 44, --h-lg 48; maydon yozuvi 16 px "
      "(iPhone fokusda sahifani kattalashtirmaydi)",
      _telv == {"h-sm": "36px", "h-md": "40px", "h-btn": "44px", "h-lg": "48px", "fs-maydon": "16px"}, _telv)
_btn = blok(CSS, ".btn")
check("S3 `.btn` — asosiy tugma: min-height var(--h-btn), burchak var(--r-btn), qat'iy yozuv qatori (20 px) va ichki joy "
      "balandlikdan hisoblanadi (display qanday bo'lmasin — bir xil balandlik), 14 px",
      "min-height: var(--h-btn)" in _btn and "border-radius: var(--r-btn)" in _btn and "line-height: 20px" in _btn
      and "calc((var(--h-btn) - 22px) / 2)" in _btn and "font-size: 14px" in _btn and "border: 1px solid transparent" in _btn, _btn[:400])
_klass = {k: blok(CSS, k) for k in (".btn-sm, .btn-xs", ".btn-md", ".btn-lg", ".btn-icon", ".chip", ".tab", ".maydon", ".maydon-sm")}
check("S4 o'lcham klasslari: `.btn-sm` (= `.btn-xs`) / `.btn-md` / `.btn-lg` — o'z tokeni bilan; `.btn-icon` — kvadrat; `.chip` — "
      "sm balandlik, to'liq yumaloq; `.tab` — md; `.maydon` — `.btn` balandligida; `.maydon-sm` — sm",
      "var(--h-sm)" in _klass[".btn-sm, .btn-xs"] and "var(--h-md)" in _klass[".btn-md"] and "var(--h-lg)" in _klass[".btn-lg"]
      and "width: var(--h-btn)" in _klass[".btn-icon"] and "height: var(--h-btn)" in _klass[".btn-icon"]
      and "var(--h-sm)" in _klass[".chip"] and "999px" in _klass[".chip"] and "var(--h-md)" in _klass[".tab"]
      and "var(--h-btn)" in _klass[".maydon"] and "var(--h-sm)" in _klass[".maydon-sm"],
      {k: v[:120] for k, v in _klass.items()})
_hisob = {".btn-sm, .btn-xs": "calc((var(--h-sm) - 20px) / 2)", ".btn-md": "calc((var(--h-md) - 20px) / 2)",
          ".btn-lg": "calc((var(--h-lg) - 22px) / 2)", ".chip": "calc((var(--h-sm) - 20px) / 2)", ".tab": "calc((var(--h-md) - 20px) / 2)"}
check("S4b har o'lchamda ichki joy balandlikdan HISOBLANADI (yozuv qatori + ramka = token) — tugma `display: block` bo'lsa ham yozuv "
      "o'rtada va balandlik aynan token", all(v in _klass.get(k, "") for k, v in _hisob.items()),
      {k: _klass.get(k, "")[:160] for k, v in _hisob.items() if v not in _klass.get(k, "")})
check("S5 eski `.btn-xs` (3 px ichki joy, 6 px burchak — Foydalanuvchilar «O'chir» / «Parol» 23 px) alohida qoidasi yo'q",
      not re.search(r"\.btn-xs\s*\{[^}]*border-radius:\s*6px", CSS), re.findall(r"\.btn-xs\s*\{[^}]*\}", CSS))


def shkala_tashqari(matn):
    yomon = []
    for m in re.finditer(r"font-size:\s*(\d+(?:\.\d+)?)px", matn):
        if float(m.group(1)) not in SHKALA:
            q = matn.count("\n", 0, m.start()) + 1
            yomon.append(f"{q}: {m.group(0)}")
    for m in re.finditer(r"font\s*:\s*\{\s*size\s*:\s*(\d+(?:\.\d+)?)", matn):
        if float(m.group(1)) not in SHKALA:
            q = matn.count("\n", 0, m.start()) + 1
            yomon.append(f"{q}: Chart.js {m.group(0)}")
    return yomon


_s6 = shkala_tashqari(CSS)
check("S6 style.css da HAR yozuv o'lchami shkalada (12 / 13 / 14 / 16 / 18 / 24 / 32 px)", not _s6, _s6[:20])
_s7 = {fn: shkala_tashqari(TPL.get(fn, "")) for fn in U13_SHABLONLAR}
_s7 = {k: v for k, v in _s7.items() if v}
check(f"S7 o'tkazilgan shablonlarda ({', '.join(U13_SHABLONLAR)}) HAR yozuv o'lchami shkalada (CSS, `style=\"…\"`, JS satrlari, "
      f"Chart.js yozuvi)", not _s7 and all(fn in TPL for fn in U13_SHABLONLAR), _s7)
_OLCHAM_RE = re.compile(r"(?:^|;|\s)(height|min-height|padding(?:-top|-bottom)?|font-size|border-radius|line-height)\s*:")


def tugma_inline(matn):
    yomon = []
    for m in re.finditer(r"<(button|a|label|input)\b[^>]*>", matn):
        teg = m.group(0)
        if m.group(1) in ("a", "label", "input") and not re.search(r"""class=["'][^"']*\b(btn|chip|tab)\b""", teg):
            continue
        if m.group(1) == "input" and not re.search(r"""type=["'](button|submit|reset)""", teg):
            continue
        st = re.search(r"""style=(["'])(.*?)\1""", teg, re.S)
        if st and _OLCHAM_RE.search(st.group(2)):
            q = matn.count("\n", 0, m.start()) + 1
            yomon.append(f"{q}: {teg[:140]}")
    return yomon


_s8 = {fn: tugma_inline(TPL.get(fn, "")) for fn in U13_SHABLONLAR}
_s8 = {k: v for k, v in _s8.items() if v}
check("S8 o'tkazilgan shablonlarda tugma (button, `.btn` / `.chip` / `.tab` havolasi) o'z balandligi / ichki joyi / burchagi / "
      "yozuv o'lchamini `style=\"…\"` da yozmaydi — o'lcham faqat klassdan (bitta joyda o'zgaradi)", not _s8, _s8)
_sv = re.search(r'templates\.env\.globals\["static_version"\]\s*=\s*"([^"]+)"', MAIN)
check("S9 kesh versiyasi yangilangan (style.css o'zgardi — eski uslub keshdan olinmasin): «20261005-1» dan keyingi",
      _sv and _sv.group(1) > "20261005-1", _sv.group(1) if _sv else None)
_bs = TPL.get("base.html", "")
check("S10 yuqori panel tugmalari umumiy klassda: tungi rejim va qo'ng'iroqcha — `.btn-icon` (`title` / `aria-label` bilan), «Кирилл» — "
      "`.btn-md`; obuna belgisi — `.btn-md`",
      re.search(r'id="themeToggle" class="[^"]*\bbtn-icon\b[^"]*"[^>]*aria-label=', _bs)
      and re.search(r'id="notifBell" class="[^"]*\bbtn-icon\b[^"]*"[^>]*aria-label=', _bs)
      and re.search(r'class="[^"]*\bbtn-md\b[^"]*"[^>]*id="script-toggle-btn"', _bs)
      and re.search(r'id="obunaBanner"[\s\S]{0,300}class="btn btn-md"', _bs), None)
_tb = blok(CSS, ".erp-topbar .tb-right")
check("S11 yuqori panel: o'ng tomon (tugmalar) siqilmaydi, chapdagi uzun izoh «…» bilan qisqaradi va to'liq matni sichqoncha ustida "
      "(ilgari «Loy retseptlari»da «Кирилл» / «Yangi loy retsepti» ikki qatorga o'tib 54 px edi)",
      "flex-shrink: 0" in _tb and "text-overflow: ellipsis" in blok(CSS, ".erp-topbar .tb-left .page-title, .erp-topbar .tb-left .page-sub")
      and 'class="page-sub" title="{{ self.page_sub()|striptags|trim }}"' in _bs, _tb)
_bk = blok(CSS, ".form-group input[type=checkbox],\n.form-group input[type=radio]")
check("S12 forma maydoni qoidasi (`.form-group input` — 100 % kenglik, 40 px) belgilash katagi / tanlov doirasiga TUSHMAYDI "
      "(ilgari «Yangi qaytarish» oynasida pul varianti doirasi 40 px edi); variant yorlig'i bosh harflarda emas",
      "min-height: 0" in _bk and "width: auto" in _bk and "padding: 0" in _bk
      and "text-transform: none" in blok(CSS, ".form-group label:has(> input[type=checkbox]),\n.form-group label:has(> input[type=radio])"), _bk)

ADMIN, PAROL = "u13_admin", "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, ADMIN, PAROL, UserRole.ADMIN, "Namuna Dekor", company_id=1)
s.close()

_src_tel = oqi("tools/test_c_telefon.py")


def _js_ol(nom):
    i = _src_tel.find(nom + ' = r"""')
    if i < 0:
        return ""
    i += len(nom + ' = r"""')
    return _src_tel[i:_src_tel.find('"""', i)]


ZANJIR_JS = _js_ol("ZANJIR_JS")
CHART_ORINBOSAR = _js_ol("CHART_ORINBOSAR") or "window.Chart = function () { return {destroy() {}, update() {}}; };"

# O'lchov: ko'rinib turgan tugmalar (balandlik, burchak, yozuv), maydonlar va matn o'lchamlari. `root` — oyna selektori yoki null
# (butun sahifa; `yon` — yon menyu ham). Tugma: button, input[type=button|submit|reset], role=button (qator / karta emas),
# `.btn` / `.chip` / `.tab` klassli a / label / span / div, onclick li va o'z foni / ramkasi bor kichik a / span / div.
U13_JS = r"""(arg) => {
  const root = arg && arg.root ? document.querySelector(arg.root) : document.body;
  if (!root) return null;
  const CS = e => getComputedStyle(e);
  const vis = e => { const r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return false; const s = CS(e);
    return s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05; };
  const kes = (t, n) => (t || '').trim().replace(/\s+/g, ' ').slice(0, n || 40);
  const klass = e => String(typeof e.className === 'string' ? e.className : (e.getAttribute('class') || '')).trim().split(/\s+/).filter(Boolean);
  const sel = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + klass(e).map(c => '.' + c).join('');
  const r1 = v => Math.round(v * 10) / 10;
  const radius = e => { const s = CS(e); const v = s.borderTopLeftRadius; if (/%$/.test(v)) { const r = e.getBoundingClientRect(); return r1(Math.min(r.width, r.height) * parseFloat(v) / 100); } return r1(parseFloat(v) || 0); };
  const shaffof = c => !c || /rgba\(0, 0, 0, 0\)|transparent/.test(c);
  const yonMenyu = e => !!e.closest('.sidebar, .erp-sidebar, .sidebar-overlay');
  const tugmaTuri = e => {
    const t = e.tagName;
    const c = klass(e).join(' ');
    if (arg && arg.istisno && e.matches(arg.istisno)) return null;
    if (e.parentElement && e.parentElement.classList.contains('segment')) return null;   // bo'lakli tanlov — butunligicha o'lchanadi
    if (klass(e).includes('segment')) return 'segment';
    if (/(^|\s)qt-(maydon|yop|band)(\s|$)/.test(c)) return null;
    if (klass(e).includes('btn-tanlov') || klass(e).includes('tanlov-karta')) return 'tanlov';   // izohli tanlov — balandligi matniga qarab (kamida `.btn`)
    if (t === 'BUTTON') return 'button';
    if (t === 'INPUT' && /^(button|submit|reset)$/i.test(e.type)) return 'input';
    if (e.getAttribute('role') === 'button') { const r = e.getBoundingClientRect(); return r.height > 56 || e.querySelector('.stat-val, .kpi-val, table') ? 'karta' : 'role'; }
    if (/(^|\s)(btn|tugma|chip|tab)(\s|$)|(^|\s)btn-|-btn(\s|$)/.test(c) && /^(A|LABEL|SPAN|DIV)$/.test(t)) return 'klass';
    if (/^(A|SPAN|DIV|LABEL)$/.test(t) && e.hasAttribute('onclick')) {
      const s = CS(e); const r = e.getBoundingClientRect();
      const ramka = parseFloat(s.borderTopWidth) > 0 && s.borderTopStyle !== 'none';
      if ((!shaffof(s.backgroundColor) || ramka) && r.height <= 56 && kes(e.innerText, 80).length <= 40 && !e.querySelector('table, .card, .kpi-card, .stat-card')) return 'onclick';
    }
    return null;
  };
  const rgb = c => { const m = String(c).match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(parseFloat); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const lum = o => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(o.r) + 0.7152 * f(o.g) + 0.0722 * f(o.b); };
  const kontrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const tugmalar = [], maydonlar = [], belgilar = [], shrift = {};
  const els = root === document.body ? [...document.querySelectorAll('body *')] : [root, ...root.querySelectorAll('*')];
  for (const e of els) {
    if ((!arg || !arg.yon) && yonMenyu(e)) continue;
    if (!vis(e)) continue;
    const s = CS(e);
    let bevosita = '';
    for (const n of e.childNodes) if (n.nodeType === 3) bevosita += n.nodeValue;
    bevosita = bevosita.trim();
    if (bevosita && !/^(SCRIPT|STYLE|NOSCRIPT|OPTION)$/.test(e.tagName)) {
      const k = String(r1(parseFloat(s.fontSize)));
      const o = shrift[k] || (shrift[k] = {n: 0, misol: []});
      o.n += 1;
      if (o.misol.length < 5) o.misol.push(sel(e).slice(0, 70) + ' «' + kes(bevosita, 24) + '»');
    }
    const tur = tugmaTuri(e);
    const r = e.getBoundingClientRect();
    if (tur) {
      const fon = rgb(s.backgroundColor), rang = rgb(s.color);
      tugmalar.push({tur, sel: sel(e).slice(0, 110), chip: klass(e).includes('chip'), ikon: klass(e).includes('btn-icon'),
        yozuv: kes(e.innerText || e.value || '', 30), matn: kes(e.innerText || e.value || e.title || e.getAttribute('aria-label') || '', 30),
        h: r1(r.height), w: r1(r.width), rad: radius(e), fs: r1(parseFloat(s.fontSize)),
        toshdi: tur !== 'karta' && e.scrollWidth > e.clientWidth + 1 && s.textOverflow !== 'ellipsis',
        k: fon && rang && fon.a > 0.9 && kes(e.innerText || e.value || '', 30) ? Math.round(kontrast(fon, rang) * 10) / 10 : null});
    } else if (e.tagName === 'INPUT' && /^(checkbox|radio)$/i.test(e.type)) {
      belgilar.push({sel: sel(e).slice(0, 100), tur: e.type, h: r1(r.height), w: r1(r.width)});
    } else if ((e.tagName === 'INPUT' && !/^(hidden|checkbox|radio|file|range|color|button|submit|reset|image)$/i.test(e.type)) || e.tagName === 'SELECT' || e.tagName === 'TEXTAREA'
               || klass(e).includes('qt-maydon')) {
      // birlik qo'shimchali o'ram ichidagi maydon — ko'rinadigan maydon o'ramning o'zi (chegara, burchak, balandlik)
      const ora = e.parentElement && e.parentElement.matches('.unit-input-wrap, .dval-box, .recp-ing-qty, .birlik-guruh, .bi-guruh') ? e.parentElement : null;
      const rr = ora ? ora.getBoundingClientRect() : r;
      maydonlar.push({sel: sel(e).slice(0, 100), tur: e.tagName.toLowerCase(), h: r1(rr.height), rad: radius(ora || e), fs: r1(parseFloat(s.fontSize)),
        ro: !!e.readOnly, ch: parseFloat(getComputedStyle(ora || e).borderTopWidth) || 0});
    }
  }
  return {tugmalar, maydonlar, belgilar, shrift};
}"""

section("M. Ma'lumot — brauzerda dasturning o'z API si orqali to'liq ish zanjiri")
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"
check("M0 Python `playwright` bor (HAQIQIY brauzer o'lchovi shart — taxmin bilan emas) va ish zanjiri (`test_c_telefon.py` ZANJIR_JS) "
      "topildi", PW_BOR and len(ZANJIR_JS) > 1000, _pw_xato)

import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


NAT = {}
if PW_BOR:
    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    check("M1 lokal server ishga tushdi", server.started)
    B = f"http://127.0.0.1:{port}"
    tk = datetime.utcnow() + timedelta(hours=5)
    K = {"m": "Namuna", "sana": tk.strftime("%Y-%m-%d"), "yil": tk.year, "oy": tk.month,
         "muddat": (tk + timedelta(days=9)).strftime("%Y-%m-%d")}

    def yonalish(route):
        u = route.request.url
        if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
            return route.fulfill(status=200, content_type="application/javascript", body=CHART_ORINBOSAR)
        if u.startswith("https://fonts.googleapis.com/"):
            return route.fulfill(status=200, content_type="text/css", body="")
        return route.fulfill(status=204, body="")

    def balandlik(w):
        return 900 if w >= 1000 else 844

    with sync_playwright() as pw:
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                  "chrome-linux", "chrome"))):
            _exe = _yol
        try:
            br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()
        except Exception as _e:            # noqa: BLE001
            br = None
            check("M2 Chromium ishga tushdi", False, f"{type(_e).__name__}: {_e}")

        def kontekst(w, tema=None):
            tel = w < 1000
            ctx = br.new_context(viewport={"width": w, "height": balandlik(w)}, device_scale_factor=1, is_mobile=tel, has_touch=tel,
                                 timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                                 r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
            if tema:
                ctx.add_init_script(f"try {{ localStorage.setItem('theme', '{tema}'); }} catch (e) {{}}")
            pg = ctx.new_page()
            pg.goto(B + "/login")
            pg.fill("input[name=username]", ADMIN)
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            return ctx, pg

        def js(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def och(pg, url, kut=700):
            try:
                pg.goto(B + url, wait_until="networkidle")
            except Exception:              # noqa: BLE001
                pass
            pg.wait_for_timeout(kut)

        if br:
            ctx, pg = kontekst(1440)
            check("M2 kirish (lokal sinov foydalanuvchisi)", "/login" not in pg.url, pg.url)
            try:
                Z = pg.evaluate(ZANJIR_JS, K)
            except Exception as _e:        # noqa: BLE001
                Z = {"yiqilgan": [["istisno", 0, str(_e)[:300]]], "L": []}
            # zip 140: Buyurtmalar oynalari uchun — topshirilmagan qismi bor buyurtma (1 / 3 topshirilgan)
            UB = js(pg, """async (I) => {
              const so = async (u, usul, tana) => { const o = {method: usul || 'GET', credentials: 'same-origin'};
                if (tana) { o.headers = {'Content-Type': 'application/json'}; o.body = JSON.stringify(tana); }
                const r = await fetch(u, o); let j = null; try { j = await r.json(); } catch (e) {} return {st: r.status, j}; };
              const tana = {project_id: I.loyiha, order_type: 'product', recipe_id: I.retsept, master_id: I.usta || null, deadline: null,
                is_draft: false, base_price: 600000, loy_kg: 5,
                items: [{name: 'U13 Karniz', category: 'profil', width: 20, thickness: 15, length: 10, quantity: 3, unit_price: 100000,
                         is_coated: false, penoplast_id: I.peno, price_per_m3: null, finished_product_id: null, sub_details: []}]};
              let r = await so('/api/orders', 'POST', tana);
              if (r.st === 409) r = await so('/api/orders?confirm_shortage=true', 'POST', tana);
              const oid = r.j && r.j.id;
              if (!oid) return {st: r.st, j: r.j};
              const h = await so('/api/orders/' + oid + '/delivery-status');
              const it = h.j && h.j.items && h.j.items[0];
              const d = it ? await so('/api/deliveries', 'POST', {order_id: oid, items: [{order_item_id: it.id, quantity: 1}], received_by: 'U13 Qabul', notes: 'U13 yuk'}) : {st: 0};
              return {oid, st: r.st, yetkazish: d.st};
            }""", Z.get("I") or {})
            # zip 140: Ishlab chiqarish oynasi uchun — qoralama (boshlanmagan) ishlab chiqarish
            UP = js(pg, """async (I) => {
              if (!I.tur || !I.bom) return {st: 0, sabab: 'tur yoki tarkib topilmadi'};
              const r = await fetch('/api/production/orders', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({product_type_id: I.tur, bom_id: I.bom, quantity: 2, source_type: 'warehouse_stock', notes: 'U13 qoralama'})});
              return {st: r.status};
            }""", Z.get("I") or {})
            ctx.close()
            check("M5 Ishlab chiqarish oynasi uchun qoralama (boshlanmagan) ishlab chiqarish yaratildi",
                  isinstance(UP, dict) and UP.get("st") in (200, 201), UP)
            check("M4 Buyurtmalar oynalari uchun topshirilmagan qismi bor buyurtma yaratildi (3 dan 1 topshirildi)",
                  isinstance(UB, dict) and UB.get("oid") and UB.get("yetkazish") in (200, 201), UB)
            check("M3 ish zanjiri: hamma qadam 2xx (ombor, kirim, retsept, usta, hodim, loyiha, buyurtmalar, to'lov, yetkazish, "
                  "qaytarish, MRP, tayyor mahsulot, moliya, majburiyat)",
                  not Z.get("yiqilgan") and len(Z.get("L") or []) >= 50, [Z.get("yiqilgan"), len(Z.get("L") or [])])

            SOXTA_AVANS = [{"id": 999001, "employee_name": "Namuna Hodim", "requested_date": K["sana"], "amount": 150000,
                            "notes": "Sinov izohi"}]
            for tema in ("light", "dark"):
                for w in (1440, 390):
                    R = NAT.setdefault((tema, w), {})
                    ctx, pg = kontekst(w, tema if tema == "dark" else None)
                    xs = []
                    pg.on("pageerror", lambda e, xs=xs: xs.append(str(e)[:200]))
                    for url in U13_SAHIFALAR:
                        del xs[:]
                        och(pg, url)
                        R[url] = {"o": js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": None, "yon": True}), "xato": list(xs),
                                  "tema": js(pg, "() => document.documentElement.getAttribute('data-theme')")}
                    # ── D6: har klass `display: block` / `inline-block` / `flex` bilan ham aynan token balandligida, yozuv o'rtada ──
                    och(pg, "/users")
                    R["korinish"] = js(pg, """() => {
                      const joy = document.querySelector('.erp-content') || document.body;
                      const KL = ['btn btn-outline', 'btn btn-outline btn-sm', 'btn btn-outline btn-xs', 'btn btn-outline btn-md', 'btn btn-outline btn-lg', 'chip', 'tab',
                                  'btn btn-outline btn-icon', 'btn btn-outline btn-icon btn-md', 'btn btn-outline btn-icon btn-sm'];
                      const out = [];
                      for (const kl of KL) for (const d of ['block', 'inline-block', 'flex', '']) {
                        const b = document.createElement('button'); b.className = kl; b.textContent = kl.includes('btn-icon') ? '✕' : 'Saqlash ✓';
                        if (d) b.style.display = d;
                        if (!kl.includes('btn-icon')) b.style.width = '160px';
                        joy.prepend(b);
                        const r = b.getBoundingClientRect();
                        const t = document.createRange(); t.selectNodeContents(b); const q = t.getBoundingClientRect();
                        out.push({kl, d, h: Math.round(r.height * 10) / 10, kv: Math.round(r.width * 10) / 10,
                                  siljish: Math.round(Math.abs((q.top + q.bottom) / 2 - (r.top + r.bottom) / 2) * 10) / 10});
                        b.remove();
                      }
                      const tok = {}; const cs = getComputedStyle(document.documentElement);
                      ['--h-sm', '--h-md', '--h-btn', '--h-lg'].forEach(k => tok[k] = parseFloat(cs.getPropertyValue(k)));
                      return {out, tok};
                    }""")
                    if tema == "light":
                        # ── O: oynalar ──
                        och(pg, "/users")
                        oy = R.setdefault("oynalar", {})
                        js(pg, "() => { xabarOyna('Sinov xabari — matn shu yerda', {sarlavha: 'Sinov sarlavhasi'}); }")   # va'da (Promise) kutilmaydi
                        pg.wait_for_timeout(300)
                        oy["xabar"] = js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": "#xoModal"})
                        js(pg, "() => { const m = document.getElementById('xoModal'); m && (m.style.display = 'none'); }")
                        js(pg, "() => { window.__ki = kiritishOyna('Sinov kiritish', {izoh: 'Izoh matni', qiymat: '12'}); }")
                        pg.wait_for_timeout(300)
                        oy["kiritish"] = js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": "#kiModal"})
                        js(pg, "() => { const m = document.getElementById('kiModal'); m && (m.style.display = 'none'); }")
                        js(pg, "() => { window.__cc = customConfirm('Sinov tasdiqlash matni'); }")
                        pg.wait_for_timeout(300)
                        oy["tasdiq"] = js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": "#ccModal"})
                        js(pg, "() => { const m = document.getElementById('ccModal'); m && (m.style.display = 'none'); }")
                        js(pg, "() => { showAddModal(); }")
                        pg.wait_for_timeout(300)
                        oy["yangi_foydalanuvchi"] = js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": "#addModal"})
                        js(pg, "() => { document.getElementById('addModal').style.display = 'none'; }")
                        js(pg, "() => { changeMyPassword(); }")
                        pg.wait_for_timeout(500)
                        oy["parol"] = js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": "#parolModal"})
                        js(pg, "() => { document.getElementById('parolModal').style.display = 'none'; }")
                        js(pg, "() => { showHodimQR(); }")
                        pg.wait_for_timeout(900)
                        oy["qr"] = js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": "#hodimQrModal"})
                        pg.route("**/api/admin/pending-advance-requests", lambda r: r.fulfill(status=200, content_type="application/json",
                                                                                              body=json.dumps(SOXTA_AVANS)))
                        och(pg, "/dashboard")
                        js(pg, "() => { checkPendingAdvanceRequests(); }")
                        pg.wait_for_timeout(600)
                        oy["avans"] = js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": "#advReqModal"})
                        pg.unroute("**/api/admin/pending-advance-requests")
                        # ── Buyurtmalar: yangi buyurtma formasi, tanlangan buyurtma, to'lov formasi, oynalar (zip 140) ──
                        def oyna(kod, root=None, kut=700):
                            js(pg, "() => { try { " + kod + " } catch (e) { window.__u13x = String(e); } }")
                            pg.wait_for_timeout(kut)
                            return js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": root})
                        och(pg, "/orders")
                        oy["yangi_buyurtma"] = oyna("showNewForm(); addItem(); addItem();", None, 900)
                        js(pg, "() => { const d = document.querySelectorAll('.detal')[1]; const s = d && d.querySelector('.type-opt[data-value=\"dona\"]'); s && s.click(); }")
                        pg.wait_for_timeout(300)
                        js(pg, "() => { const d = document.querySelector('.detal'); const b = d && d.querySelector('.i-subdetails-wrap button'); "
                               "const w = d && d.querySelector('.i-subdetails-wrap'); if (w) w.style.display = ''; b && b.click(); }")
                        pg.wait_for_timeout(300)
                        oy["yangi_buyurtma_detal"] = js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": "#newOrderForm"})
                        och(pg, "/orders")
                        oy["tanlangan_id"] = js(pg, """async () => { for (const e of document.querySelectorAll('.ord-item[data-order-id]')) {
                            const r = await fetch('/api/orders/' + e.dataset.orderId + '/delivery-status'); const j = r.ok ? await r.json() : {};
                            if ((j.items || []).some(x => x.remaining > 0.0001)) { e.click(); return e.dataset.orderId; } } return null; }""")
                        pg.wait_for_timeout(1500)
                        oy["tanlangan_buyurtma"] = js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": None})
                        oy["tolov_formasi"] = oyna("openPaymentForm();", "#payBody", 500)
                        oy["yetkazish_oynasi"] = oyna("openDeliveryModal();", "#dlvModal", 900)
                        js(pg, "() => { const m = document.getElementById('dlvModal'); m && (m.style.display = 'none'); }")
                        oy["hisob_kitob_oynasi"] = oyna("openSummaryModal();", "#sumModal", 900)
                        js(pg, "() => { const m = document.getElementById('sumModal'); m && (m.style.display = 'none'); }")
                        oy["buyurtma_tasdiq"] = oyna("showConfirmModal('Sinov savoli', {title: 'Sinov'});", "#genericConfirmOverlay", 400)
                        # ── Loyihalar: tanlangan loyiha (tablar, amallar), yangi / tahrir oynasi ──
                        och(pg, "/projects")
                        oy["loyiha_tanlangan"] = oyna("const c = document.querySelector('.proj-card'); c && c.click();", None, 1200)
                        oy["loyiha_yangi"] = oyna("showAddModal();", "#addModal", 400)
                        js(pg, "() => { document.getElementById('addModal').style.display = 'none'; }")
                        oy["loyiha_tahrir"] = oyna("openEditModal();", "#editModal", 600)
                        # ── Ombor, Kirim, Ta'minotchilar, Retseptlar (zip 140) ──
                        och(pg, "/inventory")
                        oy["ombor_chiqim"] = oyna("document.querySelector('.act-btn.out').click();", "#chiqimModal", 500)
                        js(pg, "() => { document.getElementById('chiqimModal').style.display = 'none'; }")
                        oy["ombor_tuz_kirim"] = oyna("document.querySelector('.act-btn.in').click();", "#tuzKirimModal", 500)
                        js(pg, "() => { document.getElementById('tuzKirimModal').style.display = 'none'; }")
                        oy["ombor_chegara"] = oyna("document.querySelector('[aria-label=\"Chegarani tuzatish\"]').click();", "#cpModal", 500)
                        js(pg, "() => { document.getElementById('cpModal').style.display = 'none'; }")
                        oy["ombor_xaridlar"] = oyna("openPurchaseHistory();", "#historyModal", 1200)
                        oy["ombor_kirim_hujjati"] = oyna("const p = (phAllPurchases || []).find(x => x.receipt_id); p && openPhDrawer(p.receipt_id);",
                                                       "#phDrawerOverlay", 600)
                        och(pg, "/inventory")
                        oy["ombor_harakatlar"] = oyna("openMovements();", "#movementsModal", 1200)
                        och(pg, "/suppliers/receive")
                        oy["kirim_tanlangan"] = oyna("const s = document.getElementById('r-supplier'); const o = [...s.options].find(x => x.value); "
                                                     "if (o) { s.value = o.value; s.dispatchEvent(new Event('change')); }", None, 1500)
                        oy["kirim_yangi_material"] = oyna("apToggleNewItem(); const c = document.getElementById('ap-newitem-category'); "
                                                          "c.value = 'Penoplast'; onNewItemCategoryChange();", None, 600)
                        oy["kirim_yangi_taminotchi"] = oyna("openNewSupplier();", "#newSupplierModal", 400)
                        och(pg, "/suppliers")
                        oy["taminotchi_yangi"] = oyna("openSupplierModal();", "#supplierModal", 400)
                        js(pg, "() => { document.getElementById('supplierModal').style.display = 'none'; }")
                        oy["taminotchi_tarix"] = oyna("document.querySelector('.sup-tarix').click();", "#historyModal", 1500)
                        oy["taminotchi_xarid"] = oyna("openAddPurchase(); apToggleNewItem();", "#historyModal", 800)
                        och(pg, "/recipes")
                        oy["retsept_yangi"] = oyna("openAddModal(); openIngredientPicker('f');", "#addModal", 900)
                        js(pg, "() => { closeIngredientPicker('f'); document.getElementById('addModal').style.display = 'none'; }")
                        oy["retsept_tahrir"] = oyna("document.querySelector('[aria-label=\"Tahrirlash\"][onclick^=\"openEditModal\"]').click();", "#editModal", 900)
                        # ── Ishlab chiqarish, Tayyor mahsulotlar, Qaytarishlar va brak oynasi (zip 140) ──
                        och(pg, "/production")
                        oy["ich_tur_yangi"] = oyna("openProductTypeModal();", "#pt-modal", 500)
                        js(pg, "() => { closeModal('pt-modal'); }")
                        oy["ich_tur_yonalish"] = oyna("document.querySelector('[onclick^=\"openTurYonalish\"]').click();", "#pty-modal", 500)
                        js(pg, "() => { closeModal('pty-modal'); }")
                        oy["ich_tarkib"] = oyna("const p = productTypesCache.find(x => (x.retseptlar || []).length); "
                                                "p && openBomModal(p.id, p.retseptlar[0].id);", "#bom-modal", 1500)
                        js(pg, "() => { closeModal('bom-modal'); }")
                        oy["ich_royxat"] = oyna("switchProdTab('orders');", None, 1500)
                        oy["ich_yangi"] = oyna("openProductionOrderModal();", "#po-modal", 1500)
                        js(pg, "() => { closeModal('po-modal'); }")
                        oy["ich_qoralama"] = oyna("const p = poRoyxat.find(x => x.status === 'draft'); p && poOyna(p.id, 'boshlash');", "#snapshot-modal", 1500)
                        js(pg, "() => { closeModal('snapshot-modal'); }")
                        oy["ich_surat"] = oyna("const b = document.querySelector('[data-snap]'); b && b.click();", "#snapshot-modal", 800)
                        och(pg, "/finished")
                        oy["tm_yangi"] = oyna("openProduceModal();", "#prodModal", 800)
                        js(pg, "() => { document.getElementById('prodModal').style.display = 'none'; }")
                        oy["tm_sotish"] = oyna("const i = fpItems.find(x => x.quantity > 0); i && openSellModal(i.id, i.name, i.quantity, i.unit, i.unit_price || 0);",
                                               "#sellModal", 600)
                        js(pg, "() => { document.getElementById('sellModal').style.display = 'none'; }")
                        oy["tm_savat"] = oyna("const c = [...document.querySelectorAll('.fp-batch-check')].find(x => parseFloat(x.dataset.qty) > 0); "
                                              "if (c) { c.checked = true; onBatchCheckChange(); openBatchSellModal(); }", "#batchSellModal", 600)
                        js(pg, "() => { document.getElementById('batchSellModal').style.display = 'none'; }")
                        oy["tm_malumot"] = oyna("const i = fpItems[0]; i && openHistoryModal(i.id);", "#historyModal", 600)
                        js(pg, "() => { document.getElementById('historyModal').style.display = 'none'; }")
                        oy["tm_foyda"] = oyna("const i = fpItems[0]; i && openProfitModal(i.id);", "#profitModal", 1200)
                        js(pg, "() => { document.getElementById('profitModal').style.display = 'none'; }")
                        oy["tm_ochirish"] = oyna("confirmDeleteFp('Sinov mahsulot');", "#delFpModal", 400)
                        js(pg, "() => { _delFpResolveWith(null); }")
                        och(pg, "/returns")
                        oy["qaytarish_yangi"] = oyna("showAddModal();", "#addModal", 900)
                        js(pg, "() => { document.getElementById('addModal').style.display = 'none'; }")
                        oy["brak_buyurtma"] = oyna("showBrakModal('buyurtma');", "#brakModal", 1200)
                        oy["brak_ombor"] = oyna("brakManbaTanla('ombor');", "#brakModal", 900)
                        oy["brak_ishlab"] = oyna("brakManbaTanla('ishlab');", "#brakModal", 900)
                        # ── Qarzdorlar, Moliya (zip 141) ──
                        och(pg, "/debts")
                        oy["qarz_tolov"] = oyna("const e = document.querySelector('#tab-customers .dbt-item'); e && selectOrderDebt(e);", None, 900)
                        oy["qarz_qaytarish"] = oyna("switchTab('refunds'); const e = document.querySelector('#tab-refunds .dbt-item'); e && selectRefund(e);", None, 700)
                        oy["qarz_majburiyat"] = oyna("switchTab('company');", None, 600)
                        oy["qarz_kategoriya"] = oyna("openAddCategoryModal();", "#addCategoryModal", 400)
                        js(pg, "() => { closeAddCategoryModal(); }")
                        oy["qarz_tarix"] = oyna("const o = document.querySelector('#tab-company .oblig-item'); o && o.click();", "#timelineModal", 1200)
                        och(pg, "/finance")
                        oy["moliya_xarajat"] = oyna("openTxModal();", "#txModal", 600)
                        js(pg, "() => { closeTxModal(); }")
                        oy["moliya_kassa"] = oyna("openCashTxModal(Object.keys(CASH_TX_LABELS)[0]);", "#cashTxModal", 500)
                        js(pg, "() => { document.getElementById('cashTxModal').style.display = 'none'; }")
                        oy["moliya_yonalish"] = oyna("document.getElementById('yonBolim').style.display = 'block'; "
                                                     "document.getElementById('yonDavr').value = 'oraliq'; yonDavrOzgardi();", "#yonBolim", 900)
                        # ── Ustalar KPI / Hodimlar, Ustalar, Rollar (zip 141) ──
                        och(pg, "/kpi")
                        oy["kpi_usta_detal"] = oyna("const b = document.querySelector('.mk-tugmalar .mini-btn'); b && b.click();", "#masterDetailModal", 1200)
                        js(pg, "() => { document.getElementById('masterDetailModal').style.display = 'none'; }")
                        oy["kpi_usta_yangi"] = oyna("openMasterModal();", "#masterModal", 500)
                        js(pg, "() => { closeMasterModal(); }")
                        oy["kpi_hodim_yangi"] = oyna("openEmpModal();", "#empModal", 600)
                        js(pg, "() => { closeEmpModal(); }")
                        oy["kpi_avans"] = oyna("const b = document.querySelector('.emp-tugmalar .mini-btn'); b && b.click();", "#advanceModal", 900)
                        js(pg, "() => { closeAdvanceModal(); }")
                        oy["kpi_kirish"] = oyna("const b = document.querySelector('.emp-tugmalar .btn-gold-outline'); b && b.click();", "#panelAccessModal", 600)
                        js(pg, "() => { document.getElementById('panelAccessModal').style.display = 'none'; }")
                        oy["kpi_sovga"] = oyna("openGiftPeriodModal();", "#giftPeriodModal", 1200)
                        js(pg, "() => { closeGiftPeriodModal(); }")
                        oy["kpi_oylik"] = oyna("loadEmpMonthlyReport();", "#empMonthlyReport", 1500)
                        och(pg, "/ustalar")
                        oy["ustalar_yangi"] = oyna("openMasterModal();", "#masterModal", 500)
                        och(pg, "/rollar")
                        oy["rol_yangi"] = oyna("yangiRol();", "#rlYangiModal", 500)
                        js(pg, "() => { yangiRolYop(); }")
                        oy["rol_user"] = oyna("userQoshOch();", "#rlUserModal", 600)
                        js(pg, "() => { userQoshYop(); }")
                        oy["rol_yordam"] = oyna("yordamOch();", "#rlYordamModal", 400)
                        # ── Y: yuqori panel HAMMA sahifada ──
                        yp = R.setdefault("yuqori", {})
                        for url in ["/projects", "/orders", "/inventory", "/suppliers", "/suppliers/receive", "/recipes", "/production",
                                    "/finished", "/returns", "/debts", "/finance", "/kunlik-xarajat", "/kpi", "/ustalar", "/rollar",
                                    "/sozlamalar", "/logs", "/trash"]:
                            och(pg, url, 500)
                            yp[url] = js(pg, U13_JS, {"istisno": ISTISNO_SEL, "root": ".erp-topbar"})
                    ctx.close()


def tugma_yomon(o, w):
    """Ruxsat etilmagan tugmalar: balandlik / burchak / yozuv o'lchami."""
    yomon = []
    for t in (o or {}).get("tugmalar") or []:
        if t["tur"] == "karta":
            continue
        xato = []
        if t["tur"] == "tanlov":
            if t["h"] < max(TUGMA_H[w]) - 0.6:
                xato.append(f"h={t['h']} (tanlov — kamida {int(max(TUGMA_H[w]))})")
        elif not bormi(t["h"], TUGMA_H[w]):
            xato.append(f"h={t['h']}")
        if t["chip"]:
            if t["rad"] < t["h"] / 2 - 1:
                xato.append(f"rad={t['rad']} (chip)")
        elif abs(t["rad"] - 8) > 0.5:
            xato.append(f"rad={t['rad']}")
        belgi = not re.search(r"[A-Za-z0-9\u0400-\u04FF\u2019\u02BB]", t.get("yozuv", t["matn"]) or "")
        if t["fs"] not in TUGMA_FS and not (belgi and t["fs"] == 18.0):
            xato.append(f"fs={t['fs']}")
        if t.get("ikon") and abs(t["w"] - t["h"]) > 1:
            xato.append(f"belgi-tugma kvadrat emas {t['w']}×{t['h']}")
        if t.get("toshdi"):
            xato.append("yozuv tugmaga sig'madi (chetidan chiqadi)")
        if xato:
            yomon.append(f"{t['sel'][:70]} «{t['matn'][:20]}» " + " ".join(xato))
    return yomon


def belgi_yomon(o):
    """Belgilash katagi / tanlov doirasi o'z o'lchamida (≤ 22 px) — forma maydoni qoidasi bilan cho'zilmagan."""
    return [f"{b['sel'][:60]} {b['w']}×{b['h']}" for b in (o or {}).get("belgilar") or [] if b["h"] > 22 or b["w"] > 22]


def maydon_yomon(o, w):
    yomon = []
    for m in (o or {}).get("maydonlar") or []:
        xato = []
        if m["tur"] != "textarea" and not bormi(m["h"], MAYDON_H[w]):
            xato.append(f"h={m['h']}")
        if abs(m["rad"] - 8) > 0.5 and m.get("ch", 1) > 0:      # chegarasiz (qidiruv qatoriga joylangan) maydonda burchak yo'q
            xato.append(f"rad={m['rad']}")
        # faqat o'qiladigan natija qutisi (hajm, narx — `.dval-box`) — ajratilgan raqam, 16 px ham ruxsat
        if m["fs"] not in MAYDON_FS[w] and not (w == 1440 and m["fs"] in (13.0, 14.0)) and not (m.get("ro") and m["fs"] == 16.0):
            xato.append(f"fs={m['fs']}")
        if xato:
            yomon.append(f"{m['sel'][:60]} " + " ".join(xato))
    return yomon


def shrift_yomon(o):
    return {k: v["misol"][:3] for k, v in ((o or {}).get("shrift") or {}).items() if float(k) not in SHKALA}


section("D. O'tkazilgan sahifalar — 1440 / 390 px, yorug' / tungi: tugma, maydon, matn")
if PW_BOR and NAT:
    for tema in ("light", "dark"):
        for w in (1440, 390):
            R = NAT.get((tema, w)) or {}
            nom = "yorug'" if tema == "light" else "tungi"
            for url in U13_SAHIFALAR:
                rec = R.get(url) or {}
                o = rec.get("o") or {}
                tb = [t for t in o.get("tugmalar") or [] if t["tur"] != "karta"]
                check(f"D1 {url} {w} px {nom}: HAR tugma ruxsat etilgan balandlikda ({'/'.join(str(int(x)) for x in sorted(TUGMA_H[w]))} px), "
                      f"burchak 8 px (filtr chipi — yumaloq), yozuvi 13 / 14 / 16 px va tugmaga sig'adi",
                      tb and not tugma_yomon(o, w) and (tema == "light" or rec.get("tema") == "dark"),
                      [tugma_yomon(o, w)[:12], len(tb), rec.get("tema"), o.get("js_xato")])
                if tema == "light":
                    check(f"D2 {url} {w} px: HAR matn yozuvi shkalada (12 / 13 / 14 / 16 / 18 / 24 / 32 px) — yon menyu va yuqori panel ham",
                          o.get("shrift") and not shrift_yomon(o), shrift_yomon(o))
                    check(f"D3 {url} {w} px: maydonlar (kiritish / tanlash) tugma bilan bir balandlikda "
                          f"({'/'.join(str(int(x)) for x in sorted(MAYDON_H[w]))} px), burchak 8 px; belgilash katagi / tanlov doirasi o'z o'lchamida (≤ 22 px)",
                          not maydon_yomon(o, w) and not belgi_yomon(o), [maydon_yomon(o, w)[:10], belgi_yomon(o)[:6]])
                    check(f"D4 {url} {w} px: JS xatosi yo'q", not rec.get("xato"), rec.get("xato"))
                else:
                    past = [f"{t['sel'][:60]} «{t['matn']}» {t['k']}" for t in tb if t.get("k") is not None and t["k"] < 3]
                    check(f"D5 {url} {w} px tungi: fonli tugmalar yozuvi o'qiladi (kontrast ≥ 3:1)", not past, past)

if PW_BOR and NAT:
    KUT = {"btn btn-outline": "--h-btn", "btn btn-outline btn-sm": "--h-sm", "btn btn-outline btn-xs": "--h-sm", "btn btn-outline btn-md": "--h-md",
           "btn btn-outline btn-lg": "--h-lg", "chip": "--h-sm", "tab": "--h-md", "btn btn-outline btn-icon": "--h-btn",
           "btn btn-outline btn-icon btn-md": "--h-md", "btn btn-outline btn-icon btn-sm": "--h-sm"}
    for tema in ("light", "dark"):
        for w in (1440, 390):
            kr = (NAT.get((tema, w)) or {}).get("korinish") or {}
            tok = kr.get("tok") or {}
            yomon = [x for x in kr.get("out") or [] if not tok.get(KUT.get(x["kl"], "")) or abs(x["h"] - tok[KUT[x["kl"]]]) > 0.6 or x["siljish"] > 1.5
                     or ("btn-icon" in x["kl"] and abs(x.get("kv", 0) - tok[KUT[x["kl"]]]) > 0.6)]
            tnom = "yorug'" if tema == "light" else "tungi"
            check(f"D6 {w} px {tnom}: har o'lcham klassi (`.btn`, `-sm`, `-xs`, `-md`, `-lg`, `.chip`, `.tab`; belgi-tugma `.btn-icon` — kvadrat, "
                  f"`+ .btn-md`, `+ .btn-sm`) `display` block / inline-block / flex / standart bo'lsa ham aynan token balandligida, yozuv o'rtada (±1,5 px)",
                  len(kr.get("out") or []) == 40 and len(tok) == 4 and not yomon, [yomon[:8], tok, kr.get("js_xato") if isinstance(kr, dict) else kr])

section("O. Oynalar — tugma, maydon, matn (umumiy xabar / kiritish / tasdiqlash; o'tkazilgan sahifalarning oynalari)")
if PW_BOR and NAT:
    for w in (1440, 390):
        oy = (NAT.get(("light", w)) or {}).get("oynalar") or {}
        for kalit, nom in (("xabar", "xabar oynasi (`xabarOyna`)"), ("kiritish", "kiritish oynasi (`kiritishOyna`)"),
                           ("tasdiq", "tasdiqlash oynasi (`customConfirm`)"), ("yangi_foydalanuvchi", "«Yangi foydalanuvchi»"),
                           ("parol", "«Parolni o'zgartirish»"), ("qr", "«Hodim kirishi — QR»"), ("avans", "Dashboard — avans so'rovlari"),
                           ("yangi_buyurtma", "Buyurtmalar — yangi buyurtma formasi (2 detal)"),
                           ("yangi_buyurtma_detal", "Buyurtmalar — detal turlari, qoplama, ichki qo'shimcha detal"),
                           ("tanlangan_buyurtma", "Buyurtmalar — tanlangan buyurtma (amallar, yetkazish, to'lovlar)"),
                           ("tolov_formasi", "Buyurtmalar — to'lov qo'shish formasi"), ("yetkazish_oynasi", "Buyurtmalar — «Qisman topshirish» oynasi"),
                           ("hisob_kitob_oynasi", "Buyurtmalar — «Hisob-kitob» oynasi"), ("buyurtma_tasdiq", "Buyurtmalar — tasdiqlash oynasi"),
                           ("loyiha_tanlangan", "Loyihalar — tanlangan loyiha (tablar, amallar)"), ("loyiha_yangi", "Loyihalar — «Yangi loyiha» oynasi"),
                           ("loyiha_tahrir", "Loyihalar — tahrirlash oynasi"),
                           ("ombor_chiqim", "Omborxona — «Chiqim (tuzatish)»"), ("ombor_tuz_kirim", "Omborxona — «Kirim (tuzatish)»"),
                           ("ombor_chegara", "Omborxona — chegarani tuzatish oynasi"), ("ombor_xaridlar", "Omborxona — «Xaridlar tarixi»"),
                           ("ombor_kirim_hujjati", "Omborxona — kirim hujjati (yon panel)"), ("ombor_harakatlar", "Omborxona — «Ombor harakatlari»"),
                           ("kirim_tanlangan", "Kirim qilish — ta'minotchi tanlangan (qarz, to'lov, tarix)"),
                           ("kirim_yangi_material", "Kirim qilish — yangi material (penoplast: hajm, asosiy plotnost katagi)"),
                           ("kirim_yangi_taminotchi", "Kirim qilish — «Yangi ta'minotchi»"), ("taminotchi_yangi", "Ta'minotchilar — yangi ta'minotchi"),
                           ("taminotchi_tarix", "Ta'minotchilar — tarix oynasi"), ("taminotchi_xarid", "Ta'minotchilar — «Xarid qo'shish» (yangi material)"),
                           ("retsept_yangi", "Loy retseptlari — yangi retsept va material tanlash"), ("retsept_tahrir", "Loy retseptlari — tahrirlash"),
                           ("ich_tur_yangi", "Ishlab chiqarish — «Yangi mahsulot turi»"), ("ich_tur_yonalish", "Ishlab chiqarish — tur yo'nalishi"),
                           ("ich_tarkib", "Ishlab chiqarish — tarkib (retsept) tahriri"), ("ich_royxat", "Ishlab chiqarish — ro'yxat (filtrlar, amallar)"),
                           ("ich_yangi", "Ishlab chiqarish — «Yangi ishlab chiqarish»"), ("ich_qoralama", "Ishlab chiqarish — boshlash oynasi (reja)"),
                           ("ich_surat", "Ishlab chiqarish — yakunlangan (surat)"),
                           ("tm_yangi", "Tayyor mahsulotlar — «Yangi mahsulot»"), ("tm_sotish", "Tayyor mahsulotlar — sotish"),
                           ("tm_savat", "Tayyor mahsulotlar — savatcha (bir nechtasini sotish)"), ("tm_malumot", "Tayyor mahsulotlar — «Ma'lumot»"),
                           ("tm_foyda", "Tayyor mahsulotlar — «Foyda hisobi»"), ("tm_ochirish", "Tayyor mahsulotlar — o'chirish tanlovi"),
                           ("qaytarish_yangi", "Qaytarishlar — yangi qaytarish"), ("brak_buyurtma", "Brak yozish — buyurtmadan"),
                           ("brak_ombor", "Brak yozish — ombordan"), ("brak_ishlab", "Brak yozish — ishlab chiqarishdan"),
                           ("qarz_tolov", "Qarzdorlar — tanlangan qarz va to'lov formasi"), ("qarz_qaytarish", "Qarzdorlar — mijozga qaytarish"),
                           ("qarz_majburiyat", "Qarzdorlar — boshqa majburiyatlar"), ("qarz_kategoriya", "Qarzdorlar — yangi doimiy majburiyat"),
                           ("qarz_tarix", "Qarzdorlar — to'lovlar tarixi"), ("moliya_xarajat", "Moliya — xarajat qo'shish / tahrirlash"),
                           ("moliya_kassa", "Moliya — kassa yozuvi oynasi"), ("moliya_yonalish", "Moliya — yo'nalishlar bo'yicha natija (oraliq davr)"),
                           ("kpi_usta_detal", "Ustalar KPI — har buyurtma bo'yicha KPI"), ("kpi_usta_yangi", "Ustalar KPI — «Yangi usta»"),
                           ("kpi_hodim_yangi", "Hodimlar — «Yangi hodim» (yo'nalish tanlovi)"), ("kpi_avans", "Hodimlar — avans berish"),
                           ("kpi_kirish", "Hodimlar — telefondan kirish (PIN)"), ("kpi_sovga", "Ustalar KPI — sovg'a davrini boshqarish"),
                           ("kpi_oylik", "Hodimlar — oylik hisobot (bonus / kamaytirish)"), ("ustalar_yangi", "Ustalar — «Yangi usta»"),
                           ("rol_yangi", "Rollar — yangi rol"), ("rol_user", "Rollar — foydalanuvchi qo'shish"), ("rol_yordam", "Rollar — yordam")):
            o = oy.get(kalit) or {}
            tb = [t for t in o.get("tugmalar") or [] if t["tur"] != "karta"]
            if kalit == "tanlangan_buyurtma" and not oy.get("tanlangan_id"):
                tb = []
            check(f"O1 {w} px {nom}: tugmalar / maydonlar / belgilash kataklari / matn — yagona qoidada",
                  tb and not tugma_yomon(o, w) and not maydon_yomon(o, w) and not belgi_yomon(o) and not shrift_yomon(o),
                  [tugma_yomon(o, w)[:8], maydon_yomon(o, w)[:6], belgi_yomon(o)[:4], shrift_yomon(o), len(tb),
                   o.get("js_xato") if isinstance(o, dict) else o])

section("Y. Yuqori panel HAMMA sahifada bir xil (umumiy qobiq — base.html)")
if PW_BOR and NAT:
    for w in (1440, 390):
        yp = (NAT.get(("light", w)) or {}).get("yuqori") or {}
        yomon = {u: tugma_yomon(o, w) for u, o in yp.items() if tugma_yomon(o, w)}
        shr = {u: shrift_yomon(o) for u, o in yp.items() if shrift_yomon(o)}
        check(f"Y1 {w} px: 18 sahifaning yuqori panelida har tugma ruxsat etilgan balandlikda, burchak 8 px, yozuv shkalada "
              f"(«Кирилл», tungi rejim, qo'ng'iroqcha, sahifa tugmalari)", len(yp) == 18 and not yomon and not shr,
              [len(yp), yomon, shr])
        if w == 1440:
            boshqa = {u: [f"{t['sel'][:60]} h={t['h']}" for t in (o or {}).get("tugmalar") or [] if t["tur"] != "karta" and abs(t["h"] - 36) > 0.6]
                      for u, o in yp.items()}
            boshqa = {u: v for u, v in boshqa.items() if v}
            check("Y2 1440 px: yuqori paneldagi HAMMA tugma — bir xil o'rta balandlikda (36 px): tungi rejim, qo'ng'iroqcha, «Кирилл», "
                  "obuna belgisi va sahifa tugmalari (ilgari 27 / 32 / 36 aralash)", len(yp) == 18 and not boshqa, boshqa)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  - " + f)
sys.exit(0 if FAIL == 0 else 1)
