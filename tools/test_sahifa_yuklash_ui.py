#!/usr/bin/env python3
"""
test_sahifa_yuklash_ui.py — kech138 (zip 164): «Moliya» va «Hisobotlar» sahifalari bitta so'rov xatosida QOTMAYDI, yolg'on qiymat
(«0 so'm», «Ma'lumot yo'q», «Hozircha muhim ogohlantirish yo'q») ko'rsatmaydi va eski oy / davr raqamini qoldirmaydi — HAQIQIY
brauzerda (Chromium, Playwright), HAQIQIY lokal server bilan (uvicorn, test bazasi) O'LCHANADI. Ma'lumot — `tools/test_c_telefon.py`
ZANJIR_JS (dasturning o'z API si orqali to'liq ish zanjiri) + ehson 7 % + boshlang'ich kassa 2 500 000 — nolsiz, haqiqiy qiymatlar.

NIMA UCHUN KERAK (O'LCHANGAN — work/k164/olchov164.py, zip 163 kodi; egasi tanlovi 10.10 «Sahifalar qotmasin»)
  * Moliya: oylik hisobot, ombor qiymati va qarzlar bitta `Promise.all` da edi — internet uzilsa xabarsiz to'xtardi (xarajatlar
    ro'yxati va yo'nalishlar ham yuklanmasdi); boshqa oy tanlanganda hisobot kelmasa ekranda OLDINGI oy raqamlari qolardi
    (tanlovda yangi oy); sekin eski javob yangi oy ustiga yozilardi (sentabr tanlangan — oktabr daromadi); kassa xato JSON da
    «0 so'm» (haqiqiy −17,8 mln), xarajatlar ro'yxati «Tranzaksiya topilmadi», kassa tarixi «Hali yozuv yo'q», ehson tugmasi
    maydonga «0» yozardi; Chart.js (CDN) kelmasa naqd xarajatlar, yo'nalishlar va xarajatlar ro'yxati umuman chiqmasdi;
  * Hisobotlar: 4 reyting bitta `Promise.all` da — biri xato bersa to'rttalasi abadiy «Yuklanmoqda...»; xato JSON — «Ma'lumot yo'q»,
    ogohlantirishlar — «Hozircha muhim ogohlantirish yo'q» (yolg'on); davr almashtirilganda eski davr reytingi yangisi ustiga
    yozilardi; tayyor «Moliyachi» da birinchi jadval («Ombor») 403 → «Yuklashda xato», «Mahsulotlar» — «Ma'lumot yo'q».
BO'LIMLAR
  M1 Moliya — hammasi yuklandi: kutilgan qiymatlar, sabab yozuvlari yashirin, so'rovlar bir martadan;
  M2 Moliya — 8 so'rov × 5 xato (502 HTML, 500 JSON, tarmoq, 401, 403): o'sha blok «—» va O'SHA blokda aniq sabab, qolgan bloklar
     o'z qiymatida, 401 — sahifa boshida «Kirish muddati tugagan — qayta kiring» (havola);
  M3 Moliya — boshqa oy tanlanganda hisobot / qarzlar kelmasa: eski oy raqami ko'rinmaydi, sabab bor; PDF — tanlangan oy;
  M4 Moliya — poyga: eski oy hisoboti / qarzlari, eski sana xarajatlari kech kelsa — tashlanadi;
  M5 Moliya — Chart.js yuklanmadi: hisobot, naqd xarajatlar, daromad taqsimoti, yo'nalishlar, xarajatlar ro'yxati chiqadi;
  M6 Moliya — rollar (HAQIQIY server): Moliyachi (ombor qiymati yo'q va so'ralmaydi), faqat «Moliyaviy hisobot» (kassa, pul oqimi,
     xarajatlar ro'yxati yo'q va so'ralmaydi), admin — hammasi; hech qayerda 403 yo'q;
  M7 Moliya — kassa tarixi (ochiladigan ro'yxat), ehson tugmasi, yo'nalishlar noto'g'ri davr (400 — serverning sababi);
  H1 Hisobotlar — hammasi yuklandi (`/api/inventory/kpi` endi so'ralmaydi);
  H2 Hisobotlar — 13 so'rov × 5 xato;
  H3 Hisobotlar — jadval bo'limlari (Mahsulotlar, Ustalar / KPI, Moliya) × xato;
  H4 Hisobotlar — poyga: davr almashtirildi (reyting, grafik), jadval bo'limi almashtirildi;
  H5 Hisobotlar — Chart.js / Excel kutubxonasi yuklanmadi;
  H6 Hisobotlar — rollar: Moliyachi (Ombor / Mahsulotlar yo'q, birinchi — «Ustalar / KPI»), faqat hisobot, hisobot + moliya; 403 yo'q;
  T  telefon 390 / 320 px (kunduzgi / tungi): hamma so'rov xato — sahifa yon tomonga toshmaydi, sabab ekranda, kontrast ≥ 4.5;
  S  statik: umumiy yordamchilar (base.html), sahifalarda xom `fetch(…).then(r => r.json())` va `fetch` li `Promise.all` yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 163) qarshi QULAMAYDI — yiqiladi.
TANLOV (mutatsiya sinovlari uchun; odatiy — HAMMASI): SY_BOLIM=M2,H2; SY_YOL=report,debt (M2 / H2 da yo'lida shu bo'lak); SY_TUR=500_json.
ISHLATISH: python3 tools/test_sahifa_yuklash_ui.py
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


_BOLIM = {x for x in (os.environ.get("SY_BOLIM") or "").split(",") if x}
_YOL = [x for x in (os.environ.get("SY_YOL") or "").split(",") if x]
_TUR = {x for x in (os.environ.get("SY_TUR") or "").split(",") if x}


def bolim(nom):
    return not _BOLIM or nom in _BOLIM


def oqi(nom):
    try:
        with open(os.path.join(ROOT, "templates", nom), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


# ══════════════════════════════════════════════════════════════
section("S. Statik — umumiy yordamchilar va sahifalar tuzilishi")
# ══════════════════════════════════════════════════════════════
BASE, MOL, HIS = oqi("base.html"), oqi("finance.html"), oqi("reports.html")
_yordam = ["yukXato", "yukOl", "yukSabab", "yukXatoMatn", "yukNavbat", "yukBlok", "yukXatoKor", "yukRoyxatXato", "yukSessiyaKor"]
check("S1 base.html: umumiy yuklash yordamchilari (`yukOl` — `r.ok` va JSON, `yukBlok` — rad etmaydi, `yukNavbat` — eski javob, "
      "sabab yozuvlari) va sahifa boshidagi sessiya xabari (`#yukSessiya` — /login havolasi)",
      all(re.search(r"(async\s+)?function\s+" + n + r"\s*\(", BASE) for n in _yordam)
      and re.search(r'id="yukSessiya"[^>]*hidden[^>]*>[^<]*<a href="/login">', BASE) is not None,
      [n for n in _yordam if not re.search(r"(async\s+)?function\s+" + n + r"\s*\(", BASE)])
_xom = r"\.then\(\s*r\s*=>\s*r\.json\(\)\s*\)"
check("S2 Moliya va Hisobotlar: xom `fetch(…).then(r => r.json())` (xato JSON «0 so'm» bo'lib chizilardi) yo'q",
      not re.search(_xom, MOL) and not re.search(_xom, HIS),
      (re.findall(r"[^\n]{0,60}" + _xom, MOL)[:3], re.findall(r"[^\n]{0,60}" + _xom, HIS)[:3]))
check("S3 `fetch` li `Promise.all` (biri yiqilsa hammasi to'xtardi) yo'q; Hisobotlarda `/api/inventory/kpi` so'ralmaydi (javobi "
      "ishlatilmasdi)", not re.search(r"Promise\.all\(\s*\[\s*fetch", MOL + HIS) and not re.search(r"['`\"]/api/inventory/kpi", re.sub(r"//[^\n]*", "", HIS))
      and "await Promise.all(" not in MOL, "")
check("S4 ruxsat bo'yicha bloklar: Moliya — kassa (`kassa`), ombor qiymati (`material`), xarajatlar ro'yxati (`kunlik`); Hisobotlar — "
      "moliya / kassa / dashboard / material / tayyor / kpi",
      all(x in MOL for x in ("current_user.ruxsat('kassa', 'korish')", "current_user.ruxsat('material', 'korish')",
                             "current_user.ruxsat('kunlik', 'korish')"))
      and all(f"current_user.ruxsat('{b}', 'korish')" in HIS for b in ("moliya", "kassa", "dashboard", "material", "tayyor", "kpi")), "")
_js_izoh = [m for m in re.findall(r"<script>([\s\S]*?)</script>", MOL + HIS) if re.search(r"//[^\n]*\{%", m)]
check("S5 `<script>` ichidagi JS izohida Jinja tegi (`{% … %}`) yo'q (kech137: sahifa 500)", not _js_izoh, len(_js_izoh))

try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"

PG_BAZA = "sahifa_yuklash_ui164_test"
_T = tempfile.mkdtemp(prefix="sy_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'sy_ui_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol             # noqa: E402

# ══════════════════════════════════════════════════════════════
# Fikstura: admin, tayyor «Moliyachi» (rolsiz — `users.role` = accountant), maxsus rollar
# ══════════════════════════════════════════════════════════════
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "sy_a", PAROL, UserRole.ADMIN, "Namuna Dekor", company_id=1)
    auth.create_user(s, "sy_mol", PAROL, UserRole.ACCOUNTANT, "SY moliyachi", company_id=1)
    for _u in ("sy_m", "sy_h", "sy_hm"):
        auth.create_user(s, _u, PAROL, UserRole.MANAGER, _u.upper(), company_id=1)
ROLLAR = {"sy_m": {"moliya": ["korish"]},
          "sy_h": {"hisobot": ["korish"]},
          "sy_hm": {"hisobot": ["korish"], "moliya": ["korish"]}}
for _u, _rx in ROLLAR.items():
    _r = Rol(company_id=1, nom="SY164 " + _u, kod=None, ruxsatlar=json.dumps(_rx), tavsif="")
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
QIZIL = "rgb(185, 28, 28)"           # `--m-b91c1c` (kunduzgi) — sabab matni rangi
SABAB_RANG = {"xato-kassa": "rgb(248, 113, 113)"}   # qora kassa kartasida — och qizil (`--m-f87171`, o'qiladigan)
KONTEYNER = {"monthlyReportWrap"}    # ichida boshqa bloklar — faqat ko'rinishi solishtiriladi


def matn(nima, tur):
    return f"⚠️ {nima} yuklanmadi — {SABAB[tur]}"


def bs(x):
    """bo'shliqsiz — ro'yxat qatorlari (`textContent`) kataklari orasida bo'shliq yo'q («1Namuna Mijoz1,6 mln so'm»)"""
    return re.sub(r"\s+", "", x or "")


# ── Moliya: kuzatiladigan elementlar va kutilgan (o'lchangan) qiymatlar ──
M_IDS = ["cash-balance-val", "xato-kassa", "cash-boshlangich-yoq", "hero-savdo", "hero-savdo-sub", "hero-xarajat", "hero-foyda",
         "hero-tannarx-sub", "xato-bugun", "d-material-list", "d-transport-total", "d-other-list", "hero-oqim", "hero-oqim-sub",
         "finReport", "r-daromad", "r-tannarx", "r-xarajat", "r-foyda", "r-ombor", "r-buyurtma", "r-foiz", "xato-ombor", "xato-hisobot",
         "emptyState", "monthlyReportWrap", "hisobotTahlil", "cash-total", "cash-purchase", "expDetail", "revDonutTotal", "dg-customer",
         "dg-customer-n", "dg-supplier", "dg-supplier-n", "dg-employee", "dg-employee-n", "dg-recurring", "dg-recurring-n", "dg-net",
         "xato-qarzlar", "yonBolim", "yonMazmun", "xato-yonalish", "yonKartalar", "tx-body", "yukSessiya"]
M_KUT = {
    "cash-balance-val": "⚠️ -15 255 000 so'm", "hero-savdo": "1 644 000 so'm", "hero-savdo-sub": "2 ta buyurtma yakunlandi",
    "hero-xarajat": "21 880 000 so'm", "hero-foyda": "646 858 so'm", "hero-tannarx-sub": "Tan narx: 997 142 so'm · xarajatlar ayirilmagan",
    "hero-oqim": "-17 755 000 so'm", "hero-oqim-sub": "Olingan 1 000 000 − to'langan 18 755 000 so'm (bugun)",
    "r-daromad": "1,6 mln so'm", "r-tannarx": "997 ming so'm", "r-xarajat": "3,3 mln so'm", "r-foyda": "-2,7 mln so'm",
    "r-ombor": "19,4 mln so'm", "r-buyurtma": "2 ta", "r-foiz": "-163,9%", "cash-total": "21,7 mln so'm",
    "dg-customer": "644 ming so'm", "dg-customer-n": "2 ta loyiha", "dg-supplier": "3,1 mln so'm", "dg-supplier-n": "1 ta ta'minotchi",
    "dg-employee": "3,0 mln so'm", "dg-employee-n": "1 ta hodim, oxirgi 3 oy", "dg-recurring": "500 ming so'm",
    "dg-recurring-n": "1 ta muddati o'tgan", "dg-net": "− 6,0 mln so'm",
}
M_XATO_IDLAR = ["xato-kassa", "xato-bugun", "xato-ombor", "xato-hisobot", "xato-qarzlar", "xato-yonalish", "yukSessiya"]
_DG = ["dg-customer", "dg-customer-n", "dg-supplier", "dg-supplier-n", "dg-employee", "dg-employee-n", "dg-recurring", "dg-recurring-n",
       "dg-net"]
# so'rov → blok: «—» bo'ladigan idlar, sabab yozuvi (id, nima), boshqa kutilgan holat; `ozgaradi` — solishtirilmaydigan idlar
M_BLOK = {
    # kech155 (zip 210 «Naqd / Bank / Karta», MOSLANDI): ogohlantirish («Naqd / Bank / Karta qoldig'i hali kiritilmagan») — kassa blokining o'zi: javob kelmasa yashiriladi
    "/api/finance/cash-balance": {"chiziq": ["cash-balance-val"], "sabab": ("xato-kassa", "Kassa qoldig'i"), "yashirin": ["cash-boshlangich-yoq"]},
    "/api/finance/daily": {"chiziq": ["hero-savdo", "hero-savdo-sub", "hero-xarajat", "hero-foyda", "hero-tannarx-sub", "d-material-list",
                                      "d-transport-total", "d-other-list"], "sabab": ("xato-bugun", "Bugungi holat")},
    "/api/finance/pul-oqimi": {"chiziq": ["hero-oqim"], "izoh": ("hero-oqim-sub", "Pul oqimi")},
    "/api/finance/report": {"yashirin": ["finReport", "hisobotTahlil", "emptyState"], "sabab": ("xato-hisobot", "Oylik hisobot"),
                            "ozgaradi": ["r-daromad", "r-tannarx", "r-xarajat", "r-foyda", "r-ombor", "r-buyurtma", "r-foiz", "xato-ombor",
                                         "cash-total", "cash-purchase", "expDetail", "revDonutTotal"]},
    "/api/inventory/kpi": {"chiziq": ["r-ombor"], "sabab": ("xato-ombor", "Ombor qiymati"), "ozgaradi": ["finReport"]},
    "/api/finance/debt-summary": {"chiziq": _DG, "sabab": ("xato-qarzlar", "Qarzlar")},
    "/api/finance/yonalishlar": {"korinadi": ["yonBolim"], "yashirin": ["yonMazmun"], "sabab": ("xato-yonalish", "Yo'nalishlar bo'yicha natija"),
                                 "ozgaradi": ["yonKartalar"]},
    "/api/finance/transactions": {"royxat": ("tx-body", "Xarajatlar ro'yxati")},
}

# ── Hisobotlar ──
H_IDS = ["h-pul_oqimi", "h-ombor", "h-rentabellik", "h-qarzdorlik", "h-ishlab_chiqarish", "h-material_sarfi", "xato-salomatlik",
         "kpi-daromad", "kpi-tannarx", "kpi-xarajat", "kpi-foyda", "kpi-buyurtma", "kpi-foiz", "kpi-tenglama", "kpi-daromad-ch",
         "kpi-xarajat-ch", "kpi-foyda-ch", "kpi-foiz-ch", "xato-kpi", "xato-kpi-taqqos", "kpi-oqim", "kpi-oqim-sub", "kpi-kassa",
         "kpi-kassa-sub", "trendDavr", "donutDavr", "donutLegend", "cashFlowBars", "topCustomers", "topProducts", "topMaterials",
         "topSuppliers", "comp-daromad", "comp-jami_xarajat", "comp-sof_foyda", "comp-foyda_foiz", "compDavr", "xato-taqqos",
         "forecastBody", "alertsBody", "aiSummaryList", "repBody", "repTitle", "yukSessiya"]
H_KUT = {
    "kpi-daromad": "1,6 mln so'm", "kpi-tannarx": "997 ming so'm", "kpi-xarajat": "3,3 mln so'm", "kpi-foyda": "-2,7 mln so'm",
    "kpi-buyurtma": "2 ta", "kpi-foiz": "-163,9%",
    "kpi-tenglama": "Daromad 1,6 mln − Tannarx 997 ming − Xarajat 3,3 mln = Sof foyda -2,7 mln so'm",
    "kpi-oqim": "-17,8 mln so'm", "kpi-oqim-sub": "olingan 1,0 mln − to'langan 18,8 mln", "kpi-kassa": "-15,3 mln so'm",
    "kpi-kassa-sub": "hozirgi qoldiq (naqd, karta, bank)", "topCustomers": "1 Namuna Mijoz 1,6 mln so'm",
    "topSuppliers": "1 Namuna Taminotchi 7,1 mln so'm", "alertsBody": "🟢 Bugun 2 ta buyurtma yakunlandi", "repTitle": "Ombor hisoboti",
}
H_ICHIDA = {"topMaterials": "1 Qum (mayda) 510 kg", "cashFlowBars": "Kirim (olingan pul) 1 000 000 so'm",
            "donutLegend": "Hodimlar oyligi", "forecastBody": "joriy tendentsiya asosida hisoblangan", "repBody": "Kley (akril)",
            "aiSummaryList": "Bu oy zarar: -2,7 mln so'm"}
_HH = ["h-pul_oqimi", "h-ombor", "h-rentabellik", "h-qarzdorlik", "h-ishlab_chiqarish", "h-material_sarfi"]
_KPI6 = ["kpi-daromad", "kpi-tannarx", "kpi-xarajat", "kpi-foyda", "kpi-buyurtma", "kpi-foiz"]
_CH = ["kpi-daromad-ch", "kpi-xarajat-ch", "kpi-foyda-ch", "kpi-foiz-ch"]
_COMP = ["comp-daromad", "comp-jami_xarajat", "comp-sof_foyda", "comp-foyda_foiz"]
H_BLOK = {
    "/api/reports/business-health": {"chiziq": _HH, "sabab": ("xato-salomatlik", "Korxona sog'ligi")},
    "/api/finance/history": {"chiziq": _KPI6, "bosh": ["kpi-tenglama", "donutLegend"], "sabab": ("xato-kpi", "Asosiy ko'rsatkichlar"),
                             "grafik": [("mainTrendChart", "Dinamika grafigi"), ("expenseDonut", "Xarajat tarkibi")],
                             "ozgaradi": ["trendDavr", "donutDavr"]},
    "/api/finance/pul-oqimi": {"chiziq": ["kpi-oqim"], "izoh": ("kpi-oqim-sub", "Pul oqimi"), "royxat": ("cashFlowBars", "Pul oqimi")},
    "/api/finance/cash-balance": {"chiziq": ["kpi-kassa"], "izoh": ("kpi-kassa-sub", "Kassa qoldig'i")},
    "/api/reports/top-customers": {"royxat": ("topCustomers", "Mijozlar reytingi")},
    "/api/dashboard/top-finished-products": {"royxat": ("topProducts", "Mahsulotlar reytingi")},
    "/api/reports/top-materials": {"royxat": ("topMaterials", "Xomashyo reytingi")},
    "/api/reports/top-suppliers": {"royxat": ("topSuppliers", "Ta'minotchilar reytingi")},
    "/api/reports/comparison": {"chiziq": _COMP, "bosh": _CH + ["compDavr"], "sabab": ("xato-taqqos", "O'tgan oy bilan taqqoslash"),
                                "sabab2": ("xato-kpi-taqqos", "O'tgan oy bilan taqqoslash"), "xulosa": True},
    "/api/reports/forecast": {"royxat": ("forecastBody", "Oy oxirigacha taxmin")},
    "/api/reports/alerts": {"royxat": ("alertsBody", "Ogohlantirishlar"), "xulosa": True},
    "/api/inventory": {"jadval": "Ombor hisoboti"},
}
TOLIQ_EMAS = "⚠️ Xulosa to'liq emas — ba'zi ma'lumotlar yuklanmadi, sahifani yangilang"

SNAP = r"""(idlar) => {
  const ko = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
  const o = {el: {}, grafik: {}};
  idlar.forEach(i => { const e = document.getElementById(i);
    o.el[i] = e ? {v: ko(e) && !e.hidden, t: (e.textContent || '').replace(/\s+/g, ' ').trim(), c: getComputedStyle(e).color,
                   qizil: e.classList.contains('yuk-qizil')} : null; });
  ['mainTrendChart', 'expenseDonut'].forEach(i => { const c = document.getElementById(i);
    const y = c && c.parentElement ? c.parentElement.querySelector('.grafik-bosh') : null;
    o.grafik[i] = c ? {kanvas: getComputedStyle(c).display, yozuv: y && y.style.display !== 'none' ? y.textContent : null,
                       xato: !!(y && y.classList.contains('xato')), rang: y ? getComputedStyle(y).color : null} : null; });
  o.qator_rang = {};
  document.querySelectorAll('.yuk-xato-qator').forEach(q => { const p = q.closest('[id]'); if (p) o.qator_rang[p.id] = getComputedStyle(q).color; });
  const s = document.querySelector('#yukSessiya a');
  o.sessiya_havola = s ? s.getAttribute('href') : null;
  const kont = document.querySelector('.erp-main') || document.body;
  const matn = kont.innerText || '';
  o.yuklanmoqda = (matn.match(/Yuklanmoqda/g) || []).length;
  o.notogri = (matn.match(/[^\n]{0,30}(undefined|NaN|\[object )[^\n]{0,30}/g) || []).slice(0, 4);
  return o;
}"""

KONTRAST = r"""() => {
  const rgba = c => { const m = (c.match(/[\d.]+/g) || []).map(Number); return [m[0] || 0, m[1] || 0, m[2] || 0, m.length > 3 ? m[3] : 1]; };
  const fonEl = e => { for (let p = e; p; p = p.parentElement) { const st = getComputedStyle(p);
                         if (st.backgroundImage && st.backgroundImage.includes('gradient')) return 'gradient';
                         const c = rgba(st.backgroundColor); if (c[3] > 0) return c; }
                       return rgba(getComputedStyle(document.documentElement).backgroundColor); };
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
                     return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const kon = (a, b) => { const x = lum(a), y = lum(b); return Math.round(100 * (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)) / 100; };
  const natija = [];
  document.querySelectorAll('.yuk-xato, .yuk-xato-qator, .yuk-qizil, .grafik-bosh.xato').forEach(e => {
    if (!(e.offsetWidth || e.offsetHeight) || e.hidden) return;
    const f = fonEl(e);
    const r = e.getBoundingClientRect();
    // qora kassa kartasi (gradient #111827 → #1F2937) — ikkala uchi bilan
    const k = f === 'gradient' ? Math.min(kon(rgba(getComputedStyle(e).color), [17, 24, 39]), kon(rgba(getComputedStyle(e).color), [31, 41, 55]))
                               : kon(rgba(getComputedStyle(e).color), f);
    // `toshgan` — matn o'z qutisidan chiqqan (blok eni konteynerniki bo'lib qolsa ham — `white-space:nowrap` da quti emas, matn toshadi)
    natija.push({id: e.id || (e.parentElement && e.parentElement.id) || e.className, kontrast: k, chap: Math.round(r.left), ong: Math.round(r.right),
                 toshgan: e.scrollWidth > e.clientWidth + 1});
  });
  return {el: natija, vw: innerWidth, sw: document.documentElement.scrollWidth};
}"""

section("M0 / H0. Tayyorgarlik")
check("0a Python `playwright` bor va ish zanjiri (`tools/test_c_telefon.py` ZANJIR_JS) topildi", PW_BOR and len(ZANJIR_JS) > 1000, _pw_xato)

import uvicorn                                     # noqa: E402


def yol_mos(yol):
    return lambda url: urlparse(url).path == yol


def jv(r, holat, tana):
    r.fulfill(status=holat, body=json.dumps(tana), content_type="application/json")


XATOLAR = {
    "502_html": lambda r: r.fulfill(status=502, body="<html><body>Bad Gateway</body></html>", content_type="text/html"),
    "500_json": lambda r: jv(r, 500, {"detail": "Ichki xato"}),
    "tarmoq": lambda r: r.abort("failed"),
    "401_json": lambda r: jv(r, 401, {"detail": "Iltimos, tizimga kiring"}),
    "403_json": lambda r: jv(r, 403, {"detail": "Ruxsat yo'q"}),
}


def tanlangan(yol, tur):
    return (not _YOL or any(x in yol for x in _YOL)) and (not _TUR or tur in _TUR)


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

        def kontekst(user="sy_a", w=1440, h=900, cdn=True):
            tel = w < 700
            ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ")
            ctx.set_default_timeout(20000)

            def tashqi(r):
                u = r.request.url
                if not cdn:
                    return r.abort("failed")
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
            return o if isinstance(o, dict) and "el" in o else {"el": {}, "grafik": {}, "xom": o}

        def t(o, i):
            e = (o.get("el") or {}).get(i)
            return e["t"] if e else None

        def v(o, i):
            e = (o.get("el") or {}).get(i)
            return bool(e and e["v"])

        def farqlar(o, asl, istisno):
            """istisnodan tashqari kuzatiladigan elementlar — asl (xatosiz) holatdagidek"""
            f = []
            for i, a in (asl.get("el") or {}).items():
                if i in istisno:
                    continue
                b = (o.get("el") or {}).get(i)
                if (a is None) != (b is None) or (a and (a["v"] != b["v"] or (a["v"] and i not in KONTEYNER and a["t"] != b["t"]))):
                    f.append((i, (a or {}).get("t", "")[:60], (b or {}).get("t", "")[:60]))
            return f

        def blok_tekshir(o, asl, b, tur, xato_idlar):
            """M2 / H2: o'sha blok «—» va aniq sabab bilan, qolgani asl holatda; xatolar ro'yxati"""
            x = []
            ist = set(b.get("ozgaradi", [])) | {"yukSessiya"}
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
            for i in b.get("korinadi", []):
                ist.add(i)
                if not v(o, i):
                    x.append(("ko'rinmaydi", i))
            for k in ("sabab", "sabab2"):
                if b.get(k):
                    sid, nima = b[k]
                    ist.add(sid)
                    e = (o.get("el") or {}).get(sid) or {}
                    if not (e.get("v") and e.get("t") == matn(nima, tur) and e.get("c") == SABAB_RANG.get(sid, QIZIL)):
                        x.append(("sabab", sid, e))
            if b.get("izoh"):
                iid, nima = b["izoh"]
                ist.add(iid)
                e = (o.get("el") or {}).get(iid) or {}
                if not (e.get("t") == matn(nima, tur) and e.get("c") == QIZIL):
                    x.append(("izoh", iid, e))
            if b.get("royxat"):
                rid, nima = b["royxat"]
                ist.add(rid)
                if t(o, rid) != matn(nima, tur) or (o.get("qator_rang") or {}).get(rid) != QIZIL:
                    x.append(("ro'yxat sababi", rid, t(o, rid), (o.get("qator_rang") or {}).get(rid)))
            if b.get("jadval"):
                ist.add("repBody")
                if t(o, "repBody") != matn(b["jadval"], tur):
                    x.append(("jadval sababi", t(o, "repBody")))
            for gid, nima in b.get("grafik", []):
                g = (o.get("grafik") or {}).get(gid) or {}
                if not (g.get("yozuv") == matn(nima, tur) and g.get("xato") and g.get("kanvas") == "none" and g.get("rang") == QIZIL):
                    x.append(("grafik", gid, g))
            if b.get("xulosa"):
                ist.add("aiSummaryList")
                if TOLIQ_EMAS not in (t(o, "aiSummaryList") or ""):
                    x.append(("xulosa «to'liq emas» yo'q", t(o, "aiSummaryList")))
            f = farqlar(o, asl, ist)
            if f:
                x.append(("boshqa bloklar o'zgardi", f[:6]))
            kor = [i for i in xato_idlar if i not in ist and v(o, i)]
            if kor:
                x.append(("boshqa sabab ko'rindi", kor))
            ss = (o.get("el") or {}).get("yukSessiya") or {}
            if tur == "401_json":
                if not (ss.get("v") and ss.get("t") == SESSIYA and o.get("sessiya_havola") == "/login"):
                    x.append(("sessiya xabari (kirish havolasi)", ss, o.get("sessiya_havola")))
            elif ss.get("v"):
                x.append(("sessiya xabari ko'rinmasligi kerak", ss))
            if o.get("yuklanmoqda") or o.get("notogri"):
                x.append(("Yuklanmoqda / undefined / NaN", o.get("yuklanmoqda"), o.get("notogri")))
            return x

        # ── ma'lumot: ish zanjiri (admin) + ehson 7 % + boshlang'ich kassa ──
        CTX = {u: kontekst(u) for u in ("sy_a", "sy_mol", "sy_m", "sy_h", "sy_hm")}
        _tk = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
        K = {"m": "Namuna", "sana": _tk.strftime("%Y-%m-%d"), "yil": _tk.year, "oy": _tk.month,
             "muddat": (_tk + datetime.timedelta(days=9)).strftime("%Y-%m-%d")}
        OY0 = _tk.month
        OY1 = OY0 - 1 if OY0 > 1 else 12
        pg = sahifa(CTX["sy_a"])
        och(pg, "/", 300)
        try:
            Z = pg.evaluate(ZANJIR_JS, K)
        except Exception as _e:            # noqa: BLE001
            Z = {"yiqilgan": [["istisno", 0, str(_e)[:300]]], "L": []}
        Q = ev(pg, """async () => {
            const fd = new FormData(); fd.append('percent', '7');
            const e = await fetch('/api/settings/ehson-percent', {method: 'PUT', body: fd});
            const fk = new FormData(); fk.append('category', 'boshlangich'); fk.append('amount', '2500000'); fk.append('notes', 'sy164');
            const k = await fetch('/api/finance/cash-transaction', {method: 'POST', body: fk});
            return [e.status, k.status]; }""")
        pg.close()
        # kech141 (zip 169, MOSLANDI — egasi QARORI 12.10 «Kirgan kundan»): zanjir hodimi BUGUN qo'shiladi — kirgan oy oyligi kirgan
        # kundan (kunlarga mutanosib). Bu test kutilgan qiymatlarni to'liq oylik (3 000 000) bilan o'lchaydi — hodim joriy oyning
        # 1-kuni (Toshkent 00:00) ishga kirgan deb yoziladi (o'tgan oyda baribir yo'q; eski kodda ta'sirsiz)
        _s141 = SessionLocal()
        try:
            from models import Employee as _E141
            for _e141 in _s141.query(_E141).all():
                _e141.hire_date = datetime.datetime(_tk.year, _tk.month, 1) - datetime.timedelta(hours=5)
            _s141.commit()
        finally:
            _s141.close()
        check("0c ish zanjiri: hamma qadam 2xx (ombor, kirim, retsept, usta, hodim, loyiha, 2 buyurtma, to'lov, yetkazish, qaytarish, brak, "
              "MRP, tayyor mahsulot, moliya, majburiyat), ehson 7 % va boshlang'ich kassa",
              not Z.get("yiqilgan") and len(Z.get("L") or []) >= 50 and Q == [200, 200], [Z.get("yiqilgan"), len(Z.get("L") or []), Q])

        # ══════════════════════════════════════════════════════════════
        # MOLIYA
        # ══════════════════════════════════════════════════════════════
        M_ASL = {}
        if bolim("M1") or bolim("M2"):
            section("M1. Moliya — hammasi yuklandi")
            pg = sahifa(CTX["sy_a"])
            och(pg, "/finance", 1500)
            M_ASL = snap(pg, M_IDS)
            _farq = [(k, t(M_ASL, k), w) for k, w in M_KUT.items() if t(M_ASL, k) != w]
            check("M1a har blok kutilgan qiymatda (kassa, bugungi holat, pul oqimi, oylik hisobot, ombor qiymati, qarzlar, naqd xarajatlar)",
                  not _farq, _farq)
            check("M1b sabab yozuvlari va sessiya xabari yashirin; hisobot, «Moliyaviy tahlillar», yo'nalishlar ko'rinadi; «Oy tanlang» "
                  "yashirin", not any(v(M_ASL, i) for i in M_XATO_IDLAR) and v(M_ASL, "finReport") and v(M_ASL, "hisobotTahlil")
                  and v(M_ASL, "yonBolim") and v(M_ASL, "yonMazmun") and not v(M_ASL, "emptyState"),
                  [(i, v(M_ASL, i)) for i in M_XATO_IDLAR + ["finReport", "hisobotTahlil", "yonBolim", "emptyState"]])
            # kech155 (zip 210 «Naqd / Bank / Karta», MOSLANDI): eski «boshlang'ich balans» kiritilgan bo'lsa ham Naqd / Bank / Karta qoldig'i hali yo'q — ogohlantirish KO'RINADI
            check("M1c xarajatlar ro'yxati (Transport (kirim) 150 000 so'm); kassa ogohlantirishi «Naqd / Bank / Karta qoldig'i hali "
                  "kiritilmagan» ko'rinadi (hisoblar qoldig'i kiritilmagan)",
                  "Transport (kirim)" in (t(M_ASL, "tx-body") or "") and "150 000 so'm" in (t(M_ASL, "tx-body") or "")
                  and v(M_ASL, "cash-boshlangich-yoq")
                  and "Naqd / Bank / Karta qoldig'i hali kiritilmagan" in (t(M_ASL, "cash-boshlangich-yoq") or ""), t(M_ASL, "tx-body"))
            check("M1d «Yuklanmoqda...», «undefined», «NaN» yo'q; JS xatosi yo'q", not M_ASL.get("yuklanmoqda") and not M_ASL.get("notogri")
                  and not pg.__xato, (M_ASL.get("yuklanmoqda"), M_ASL.get("notogri"), pg.__xato))
            _yollar = [urlparse(x.split(" ", 1)[1]).path for x in pg.__sorov if x.startswith("GET ")]
            _bir = [y for y in M_BLOK if _yollar.count(y) != 1]
            check("M1e har blok so'rovi bir martadan (kassa, kunlik, pul oqimi, hisobot, ombor qiymati, qarzlar, yo'nalishlar, xarajatlar)",
                  not _bir, (_bir, _yollar))
            pg.close()

        if bolim("M2") and M_ASL:
            section("M2. Moliya — har so'rov × har xato: faqat o'sha blok, aniq sabab bilan")
            for yol, b in M_BLOK.items():
                for tur, xf in XATOLAR.items():
                    if not tanlangan(yol, tur):
                        continue
                    pg = sahifa(CTX["sy_a"])
                    pg.route(yol_mos(yol), xf)
                    och(pg, "/finance", 1300)
                    o = snap(pg, M_IDS)
                    x = blok_tekshir(o, M_ASL, b, tur, M_XATO_IDLAR)
                    if yol == "/api/finance/pul-oqimi" and not ((o.get("el") or {}).get("hero-oqim-sub") or {}).get("qizil"):
                        x.append(("izoh qizil klassi (`yuk-qizil`) yo'q",))
                    if pg.__xato:
                        x.append(("JS xatosi", pg.__xato[:2]))
                    check(f"M2 {yol} {tur}: o'sha blok «—» va sabab bilan, qolgani o'z qiymatida", not x, x)
                    pg.close()

        if bolim("M3"):
            section("M3. Moliya — boshqa oy tanlandi, hisobot / qarzlar kelmadi: eski oy raqami ko'rinmaydi")
            pg = sahifa(CTX["sy_a"])
            och(pg, "/finance", 1300)
            xav(pg.select_option, "#sel-month", str(OY1))
            pg.wait_for_timeout(1500)
            NAZ = snap(pg, M_IDS)
            check("M3a nazorat: xatosiz boshqa oy — hisobot o'sha oyniki (daromad «0 so'm»), sabab yo'q, PDF — o'sha oy",
                  t(NAZ, "r-daromad") == "0 so'm" and not v(NAZ, "xato-hisobot")
                  and ev(pg, "() => JSON.stringify(korsatilganOy)") == json.dumps({"year": str(_tk.year), "month": str(OY1)}).replace(" ", ""),
                  (t(NAZ, "r-daromad"), ev(pg, "() => JSON.stringify(korsatilganOy)")))
            pg.close()
            for tur in ("502_html", "500_json", "tarmoq", "403_json"):
                pg = sahifa(CTX["sy_a"])
                och(pg, "/finance", 1300)
                pg.route(yol_mos("/api/finance/report"), XATOLAR[tur])
                xav(pg.select_option, "#sel-month", str(OY1))
                pg.wait_for_timeout(1500)
                o = snap(pg, M_IDS)
                _matn = ev(pg, "() => (document.querySelector('.erp-main') || document.body).innerText")
                eski = [k for k in ("r-daromad", "r-xarajat", "r-foyda", "cash-total") if v(o, k)]
                check(f"M3b {tur}: oktabr hisobotidan keyin sentabr kelmadi — oylik kartalar va «Moliyaviy tahlillar» yashirin (eski oy "
                      "daromadi, xarajati, sof foydasi ko'rinmaydi), «Oylik hisobot yuklanmadi» sababi; PDF — tanlangan oy",
                      not eski and not v(o, "finReport") and not v(o, "hisobotTahlil")
                      and t(o, "xato-hisobot") == matn("Oylik hisobot", tur) and v(o, "xato-hisobot")
                      and "3,3 mln so'm" not in (_matn if isinstance(_matn, str) else "")
                      and ev(pg, "() => korsatilganOy") is None and not pg.__xato,
                      (eski, t(o, "xato-hisobot"), ev(pg, "() => korsatilganOy"), pg.__xato))
                pg.close()
            for tur in ("502_html", "tarmoq"):
                pg = sahifa(CTX["sy_a"])
                och(pg, "/finance", 1300)
                pg.route(yol_mos("/api/finance/debt-summary"), XATOLAR[tur])
                xav(pg.select_option, "#sel-month", str(OY1))
                pg.wait_for_timeout(1500)
                o = snap(pg, M_IDS)
                check(f"M3c {tur}: boshqa oy qarzlari kelmadi — hamma qarz qiymati «—» (eski oy «3,0 mln so'm» qolmaydi), sabab",
                      all(t(o, i) == "—" for i in _DG) and t(o, "xato-qarzlar") == matn("Qarzlar", tur) and t(o, "r-daromad") == "0 so'm",
                      [(i, t(o, i)) for i in _DG] + [t(o, "xato-qarzlar")])
                pg.close()
            # xato tuzalgach — qiymatlar qaytadi, sabab yo'qoladi
            pg = sahifa(CTX["sy_a"])
            pg.route(yol_mos("/api/finance/report"), XATOLAR["500_json"])
            och(pg, "/finance", 1300)
            xav(pg.unroute, "**/api/finance/report*")
            pg.unroute_all(behavior="ignoreErrors")
            xav(pg.click, "button:has-text(\"Ko'rish\")")
            pg.wait_for_timeout(1500)
            o = snap(pg, M_IDS)
            check("M3d xato tuzalgach «Ko'rish» — hisobot qaytadi (daromad 1,6 mln so'm), sabab yashirin",
                  t(o, "r-daromad") == "1,6 mln so'm" and v(o, "finReport") and v(o, "hisobotTahlil") and not v(o, "xato-hisobot"),
                  (t(o, "r-daromad"), v(o, "finReport"), v(o, "xato-hisobot")))
            pg.close()

        if bolim("M4"):
            section("M4. Moliya — poyga: eski javob kech kelsa tashlanadi")

            def ushlovchi(ushla):
                def _u(r):
                    if not ushla:
                        ushla.append(r)
                    else:
                        r.continue_()
                return _u
            for yol, el, ozgartir, yomon in (
                    ("/api/finance/report", "r-daromad", lambda j: dict(j, daromad=88888888), "88,9 mln so'm"),
                    ("/api/finance/debt-summary", "dg-customer", lambda j: dict(j, customer_debt=77777777), "77,8 mln so'm")):
                pg = sahifa(CTX["sy_a"])
                och(pg, "/finance", 1300)
                ushla = []
                pg.route(yol_mos(yol), ushlovchi(ushla))
                xav(pg.click, "button:has-text(\"Ko'rish\")")           # 1-so'rov (joriy oy) — ushlanadi
                pg.wait_for_timeout(500)
                xav(pg.select_option, "#sel-month", str(OY1))           # 2-so'rov (boshqa oy) — o'tadi
                pg.wait_for_timeout(1500)
                yangi = t(snap(pg, [el]), el)
                if ushla:
                    try:
                        jj = ushla[0].fetch().json()
                        ushla[0].fulfill(status=200, body=json.dumps(ozgartir(jj)), content_type="application/json")
                    except Exception as _e:    # noqa: BLE001
                        yangi = f"{yangi} [fulfill: {_e}]"
                pg.wait_for_timeout(1500)
                keyin = t(snap(pg, [el]), el)
                check(f"M4 {yol}: sentabr tanlangan, oktabr javobi kech keldi — ekranda sentabr qiymati qoladi ({yomon} emas)",
                      len(ushla) == 1 and keyin == yangi and keyin != yomon, (len(ushla), yangi, keyin))
                pg.close()
            # xarajatlar ro'yxati: sana almashtirildi, eski sana javobi kech keldi
            pg = sahifa(CTX["sy_a"])
            och(pg, "/finance", 1300)
            ushla = []
            pg.route(yol_mos("/api/finance/transactions"), ushlovchi(ushla))
            xav(pg.uncheck, "#tx-whole-month")                          # 1-so'rov — ushlanadi
            pg.wait_for_timeout(400)
            xav(pg.check, "#tx-whole-month")                            # 2-so'rov — o'tadi
            pg.wait_for_timeout(1200)
            yangi = t(snap(pg, ["tx-body"]), "tx-body")
            if ushla:
                ushla[0].fulfill(status=200, body=json.dumps([{"id": 999, "date": K["sana"] + "T00:00:00", "category": "boshqa",
                                                                "amount": 123456, "notes": "ESKI JAVOB", "source": "manual"}]),
                                 content_type="application/json")
            pg.wait_for_timeout(1200)
            keyin = t(snap(pg, ["tx-body"]), "tx-body")
            check("M4c xarajatlar ro'yxati: filtr almashtirildi, eski javob kech keldi — tashlanadi («ESKI JAVOB» qatori yo'q)",
                  len(ushla) == 1 and keyin == yangi and "ESKI JAVOB" not in (keyin or ""), (len(ushla), (keyin or "")[:120]))
            pg.close()

        if bolim("M5"):
            section("M5. Moliya — Chart.js (internetdan) yuklanmadi")
            ctx = kontekst("sy_a", cdn=False)
            pg = sahifa(ctx)
            och(pg, "/finance", 1500)
            o = snap(pg, M_IDS)
            _f = [(k, t(o, k), w) for k, w in M_KUT.items() if t(o, k) != w]
            check("M5a hisobot, naqd xarajatlar, qarzlar — hammasi qiymati bilan (ilgari `new Chart` yiqilib qolgani chiqmasdi)", not _f, _f)
            check("M5b daromad taqsimoti jami, yo'nalishlar va xarajatlar ro'yxati chiqadi; JS xatosi yo'q",
                  t(o, "revDonutTotal") not in (None, "", "—") and v(o, "yonMazmun") and "Transport (kirim)" in (t(o, "tx-body") or "")
                  and not pg.__xato, (t(o, "revDonutTotal"), v(o, "yonMazmun"), (t(o, "tx-body") or "")[:60], pg.__xato))
            pg.close()
            ctx.close()

        if bolim("M6"):
            section("M6. Moliya — rollar (HAQIQIY server)")
            for user, bor, yoq, sorov_yoq in (
                    ("sy_a", ["cash-balance-val", "hero-oqim", "r-ombor", "tx-body"], [], []),
                    ("sy_mol", ["cash-balance-val", "hero-oqim", "tx-body"], ["r-ombor"], ["/api/inventory/kpi"]),
                    ("sy_m", ["r-daromad", "dg-customer"], ["cash-balance-val", "hero-oqim", "r-ombor", "tx-body"],
                     ["/api/finance/cash-balance", "/api/finance/pul-oqimi", "/api/inventory/kpi", "/api/finance/transactions"])):
                pg = sahifa(CTX[user])
                och(pg, "/finance", 1300)
                o = snap(pg, M_IDS)
                rad = [j for j in pg.__javob if j[1] >= 400]
                _yollar = [y for y, _ in pg.__javob]
                check(f"M6 {user}: blok bor {bor}, yo'q {yoq}; so'ralmaydi {sorov_yoq}; 403 / xato javob yo'q; sabab yozuvlari yashirin",
                      all((o.get("el") or {}).get(i) is not None for i in bor) and all((o.get("el") or {}).get(i) is None for i in yoq)
                      and not any(y in _yollar for y in sorov_yoq) and not rad and not any(v(o, i) for i in M_XATO_IDLAR)
                      and not pg.__xato and t(o, "r-daromad") == "1,6 mln so'm",
                      ([i for i in bor if (o.get("el") or {}).get(i) is None], [i for i in yoq if (o.get("el") or {}).get(i) is not None],
                       [y for y in sorov_yoq if y in _yollar], rad, pg.__xato, t(o, "r-daromad")))
                pg.close()

        if bolim("M7"):
            section("M7. Moliya — kassa tarixi, ehson tugmasi, yo'nalishlar davri")
            for tur in [None] + list(XATOLAR):
                pg = sahifa(CTX["sy_a"])
                och(pg, "/finance", 1200)
                if tur:
                    pg.route(yol_mos("/api/finance/cash-transactions"), XATOLAR[tur])
                ev(pg, "() => { toggleCashTxHistory(); }")
                pg.wait_for_timeout(1000)
                r = ev(pg, "() => (document.getElementById('cashTxHistoryList').textContent || '').replace(/\\s+/g, ' ').trim()")
                if tur is None:
                    check("M7a kassa tarixi (xatosiz): «Boshlang'ich balans … +2 500 000 so'm»",
                          isinstance(r, str) and "Boshlang'ich balans" in r and "2 500 000" in r, r)
                else:
                    check(f"M7b kassa tarixi {tur}: «Kassa tarixi yuklanmadi — …» (yolg'on «Hali qo'lda kiritilgan yozuv yo'q» emas)",
                          r == matn("Kassa tarixi", tur), r)
                pg.close()
            for tur in ("500_json", "tarmoq"):
                pg = sahifa(CTX["sy_a"])
                och(pg, "/finance", 1200)
                ev(pg, "() => { openCashTxModal('ehson'); }")
                pg.wait_for_timeout(300)
                xav(pg.fill, "#cashtx-amount", "12 345")
                pg.route(yol_mos("/api/finance/report"), XATOLAR[tur])
                xav(pg.click, "#ehsonFetchBtnWrap button")
                pg.wait_for_timeout(900)
                r = ev(pg, """() => ({qiymat: document.getElementById('cashtx-amount').value,
                                       tugma: (document.querySelector('#ehsonFetchBtnWrap button') || {}).textContent})""")
                check(f"M7c ehson tugmasi {tur}: maydon o'zgarmaydi («0» yozilmaydi), tugmada sabab",
                      isinstance(r, dict) and r.get("qiymat") == "12 345"
                      and (r.get("tugma") or "").strip() == "⚠️ Yuklanmadi — " + SABAB[tur], r)
                pg.close()
            pg = sahifa(CTX["sy_a"])
            pg.route(yol_mos("/api/finance/yonalishlar"), lambda r: jv(r, 400, {"detail": "Davr noto'g'ri: boshlanish oyi oxirgi oydan keyin"}))
            och(pg, "/finance", 1300)
            o = snap(pg, M_IDS)
            check("M7d yo'nalishlar 400 (noto'g'ri davr) — bo'limda serverning sababi",
                  t(o, "xato-yonalish") == "⚠️ Yo'nalishlar bo'yicha natija yuklanmadi — Davr noto'g'ri: boshlanish oyi oxirgi oydan keyin"
                  and v(o, "yonBolim") and not v(o, "yonMazmun"), (t(o, "xato-yonalish"), v(o, "yonBolim"), v(o, "yonMazmun")))
            pg.close()

        # ══════════════════════════════════════════════════════════════
        # HISOBOTLAR
        # ══════════════════════════════════════════════════════════════
        H_ASL = {}
        H_XATO_IDLAR = ["xato-salomatlik", "xato-kpi", "xato-kpi-taqqos", "xato-taqqos", "yukSessiya"]
        if bolim("H1") or bolim("H2"):
            section("H1. Hisobotlar — hammasi yuklandi")
            pg = sahifa(CTX["sy_a"])
            och(pg, "/reports", 1500)
            H_ASL = snap(pg, H_IDS)
            _farq = [(k, t(H_ASL, k), w) for k, w in H_KUT.items() if bs(t(H_ASL, k)) != bs(w)]
            _farq += [(k, (t(H_ASL, k) or "")[:80], w) for k, w in H_ICHIDA.items() if bs(w) not in bs(t(H_ASL, k))]
            check("H1a har blok kutilgan qiymatda (ko'rsatkichlar, pul oqimi, kassa, reytinglar, ogohlantirishlar, xulosa, Ombor jadvali)",
                  not _farq, _farq)
            check("H1b korxona sog'ligi baholangan, taqqoslash va taxmin chiqqan; sabab yozuvlari yashirin; grafiklar kanvasda",
                  all(t(H_ASL, i) not in (None, "", "—") for i in _HH + _COMP + ["compDavr"])
                  and not any(v(H_ASL, i) for i in H_XATO_IDLAR)
                  and all((g or {}).get("yozuv") is None and (g or {}).get("kanvas") != "none" for g in H_ASL["grafik"].values()),
                  ([(i, t(H_ASL, i)) for i in _HH + _COMP], [i for i in H_XATO_IDLAR if v(H_ASL, i)], H_ASL.get("grafik")))
            _yollar = [urlparse(x.split(" ", 1)[1]).path for x in pg.__sorov if x.startswith("GET ")]
            check("H1c `/api/inventory/kpi` so'ralmaydi; «Yuklanmoqda...», «undefined», «NaN», JS xatosi yo'q",
                  "/api/inventory/kpi" not in _yollar and not H_ASL.get("yuklanmoqda") and not H_ASL.get("notogri") and not pg.__xato,
                  (_yollar, H_ASL.get("yuklanmoqda"), H_ASL.get("notogri"), pg.__xato))
            pg.close()

        if bolim("H2") and H_ASL:
            section("H2. Hisobotlar — har so'rov × har xato")
            for yol, b in H_BLOK.items():
                for tur, xf in XATOLAR.items():
                    if not tanlangan(yol, tur):
                        continue
                    pg = sahifa(CTX["sy_a"])
                    pg.route(yol_mos(yol), xf)
                    och(pg, "/reports", 1300)
                    o = snap(pg, H_IDS)
                    x = blok_tekshir(o, H_ASL, b, tur, H_XATO_IDLAR)
                    if pg.__xato:
                        x.append(("JS xatosi", pg.__xato[:2]))
                    check(f"H2 {yol} {tur}: o'sha blok «—» va sabab bilan, qolgani o'z qiymatida", not x, x)
                    pg.close()

        if bolim("H3"):
            section("H3. Hisobotlar — jadval bo'limlari × xato")
            TAB = {"products": ("/api/finished", "Mahsulotlar hisoboti", "Namuna Tayyor karniz"),
                   "masters": ("/api/masters/kpi-report", "Hamkor ustalar / KPI hisoboti", "Namuna Usta"),
                   "finance": ("/api/finance/history", "Moliyaviy hisobot", "1 644 000 so'm")}
            for tab, (yol, nom, kut) in TAB.items():
                pg = sahifa(CTX["sy_a"])
                och(pg, "/reports", 1200)
                ev(pg, "t => { switchReport(t); }", tab)
                pg.wait_for_timeout(1000)
                r = t(snap(pg, ["repBody"]), "repBody")
                check(f"H3 {tab} (xatosiz): jadval to'ldi ({kut})", kut in (r or ""), (r or "")[:120])
                pg.close()
                for tur, xf in XATOLAR.items():
                    if not tanlangan(yol, tur):
                        continue
                    pg = sahifa(CTX["sy_a"])
                    och(pg, "/reports", 1200)
                    pg.route(yol_mos(yol), xf)
                    ev(pg, "t => { switchReport(t); }", tab)
                    pg.wait_for_timeout(1000)
                    o = snap(pg, ["repBody", "repTitle"])
                    check(f"H3 {tab} {tur}: jadvalda «{nom} yuklanmadi — …» (yolg'on «Ma'lumot yo'q» / sababsiz «Yuklashda xato» emas)",
                          t(o, "repBody") == matn(nom, tur) and (o.get("qator_rang") or {}).get("repBody") == QIZIL and not pg.__xato,
                          (t(o, "repBody"), (o.get("qator_rang") or {}).get("repBody"), pg.__xato))
                    pg.close()
            for tur in ("500_json", "tarmoq"):
                pg = sahifa(CTX["sy_a"])
                och(pg, "/reports", 1200)
                pg.route(lambda u: urlparse(u).path == "/api/finance/report", XATOLAR[tur])
                ev(pg, "t => { switchReport(t); }", "masters")
                pg.wait_for_timeout(1000)
                r = ev(pg, """() => ({body: (document.getElementById('repBody').textContent || '').replace(/\\s+/g, ' '),
                                       banner: getComputedStyle(document.getElementById('ehsonSummaryBanner')).display})""")
                check(f"H3d Ustalar / KPI — ehson hisoboti {tur}: jadval baribir chiqadi, banner ko'rsatilmaydi",
                      isinstance(r, dict) and "Namuna Usta" in r.get("body", "") and r.get("banner") == "none", r)
                pg.close()

        if bolim("H4"):
            section("H4. Hisobotlar — poyga")

            def ushlovchi2(ushla, shart=None):
                def _u(r):
                    if not ushla and (shart is None or shart(r.request.url)):
                        ushla.append(r)
                    else:
                        r.continue_()
                return _u
            pg = sahifa(CTX["sy_a"])
            ushla = []
            pg.route(yol_mos("/api/reports/top-customers"), ushlovchi2(ushla))
            och(pg, "/reports", 800)
            xav(pg.click, "[data-days='30']")
            pg.wait_for_timeout(1500)
            yangi = t(snap(pg, ["topCustomers"]), "topCustomers")
            if ushla:
                jv(ushla[0], 200, [{"client_name": "ESKI DAVR MIJOZI", "revenue": 111111}])
            pg.wait_for_timeout(1200)
            keyin = t(snap(pg, ["topCustomers"]), "topCustomers")
            check("H4a davr 90 → 30 kun, 90 kunlik reyting kech keldi — tashlanadi («ESKI DAVR MIJOZI» yo'q)",
                  len(ushla) == 1 and keyin == yangi and "ESKI DAVR" not in (keyin or ""), (len(ushla), yangi, keyin))
            pg.close()
            pg = sahifa(CTX["sy_a"])
            ushla = []
            pg.route(yol_mos("/api/finance/history"), ushlovchi2(ushla, lambda u: "months=3" in u))
            och(pg, "/reports", 800)
            xav(pg.click, "[data-days='30']")
            pg.wait_for_timeout(1500)
            if ushla:
                jv(ushla[0], 200, [])
            pg.wait_for_timeout(1200)
            r = ev(pg, """() => ({davr: document.getElementById('trendDavr').textContent,
                                   yozuv: (document.querySelector('#mainTrendChart').parentElement.querySelector('.grafik-bosh') || {}).textContent || ''})""")
            check("H4b grafik: 90 kunlik (3 oy) tarix kech keldi — 30 kunlik (1 oy) grafik qoladi (davr yozuvi va «ma'lumot yo'q» emas)",
                  len(ushla) == 1 and isinstance(r, dict) and r.get("davr") == "— " + ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
                                                                                      "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr",
                                                                                      "Dekabr"][OY0] + f" {_tk.year}"
                  and "hali daromad" not in r.get("yozuv", ""), (len(ushla), r))
            pg.close()
            pg = sahifa(CTX["sy_a"])
            och(pg, "/reports", 1200)
            ushla = []
            pg.route(yol_mos("/api/finished"), ushlovchi2(ushla))
            ev(pg, "t => { switchReport(t); }", "products")
            pg.wait_for_timeout(500)
            ev(pg, "t => { switchReport(t); }", "masters")
            pg.wait_for_timeout(1300)
            if ushla:
                jv(ushla[0], 200, [{"name": "ESKI BO'LIM", "source": "produced", "quantity": 1, "unit": "dona", "unit_price": 1,
                                    "total_value": 1}])
            pg.wait_for_timeout(1000)
            o = snap(pg, ["repBody", "repTitle"])
            check("H4c jadval: «Mahsulotlar» javobi «Ustalar / KPI» tanlangandan keyin keldi — tashlanadi (ustalar jadvali qoladi)",
                  len(ushla) == 1 and "Namuna Usta" in (t(o, "repBody") or "") and "ESKI BO'LIM" not in (t(o, "repBody") or "")
                  and t(o, "repTitle") == "Hamkor ustalar / KPI hisoboti", (len(ushla), t(o, "repBody"), t(o, "repTitle")))
            pg.close()

        if bolim("H5"):
            section("H5. Hisobotlar — Chart.js / Excel kutubxonasi (internetdan) yuklanmadi")
            ctx = kontekst("sy_a", cdn=False)
            pg = sahifa(ctx)
            och(pg, "/reports", 1500)
            o = snap(pg, H_IDS)
            _f = [(k, t(o, k), w) for k, w in H_KUT.items() if bs(t(o, k)) != bs(w)]
            check("H5a ko'rsatkichlar, pul oqimi, reytinglar, jadval — hammasi qiymati bilan; xarajat tarkibi ro'yxati (foizlar) chiqadi",
                  not _f and "Hodimlar oyligi" in (t(o, "donutLegend") or "") and not pg.__xato, (_f, t(o, "donutLegend"), pg.__xato))
            g = o.get("grafik") or {}
            check("H5b grafik o'rnida yozuv: dinamika — «Grafik chizilmadi — internet aloqasini tekshiring», xarajat tarkibi — «Grafik chizilmadi»",
                  (g.get("mainTrendChart") or {}).get("yozuv") == "Grafik chizilmadi — internet aloqasini tekshiring"
                  and (g.get("expenseDonut") or {}).get("yozuv") == "Grafik chizilmadi", g)
            xav(pg.click, "button:has-text('Excel')")
            pg.wait_for_timeout(500)
            r = ev(pg, """() => [...document.body.children].filter(e => getComputedStyle(e).position === 'fixed' && (e.innerText || '').trim())
                           .map(e => e.innerText.trim())""")
            check("H5c «Excel» — kutubxona yo'q: «Excel fayli yaratilmadi — kutubxona yuklanmadi, sahifani yangilang» (JS xatosi emas)",
                  isinstance(r, list) and "Excel fayli yaratilmadi — kutubxona yuklanmadi, sahifani yangilang" in r and not pg.__xato,
                  (r, pg.__xato))
            pg.close()
            ctx.close()

        if bolim("H6"):
            section("H6. Hisobotlar — rollar (HAQIQIY server)")
            for user, tablar, faol, bor, yoq in (
                    ("sy_a", ["inventory", "products", "masters", "finance"], "inventory",
                     ["kpi-daromad", "kpi-kassa", "cashFlowBars", "topProducts", "trendDavr"], []),
                    ("sy_mol", ["masters", "finance"], "masters", ["kpi-daromad", "kpi-kassa", "cashFlowBars", "topProducts", "trendDavr"], []),
                    ("sy_h", [], None, ["topCustomers", "forecastBody", "alertsBody"],
                     ["kpi-daromad", "kpi-kassa", "cashFlowBars", "topProducts", "trendDavr", "repBody"]),
                    ("sy_hm", ["finance"], "finance", ["kpi-daromad", "trendDavr"], ["kpi-kassa", "cashFlowBars", "topProducts"])):
                pg = sahifa(CTX[user])
                och(pg, "/reports", 1500)
                o = snap(pg, H_IDS)
                r = ev(pg, """() => ({tablar: [...document.querySelectorAll('#repTabs .bi-tab')].map(b => b.dataset.r),
                                       faol: (document.querySelector('#repTabs .bi-tab.active') || {dataset: {}}).dataset.r || null})""")
                rad = [j for j in pg.__javob if j[1] >= 400]
                ok_ = (isinstance(r, dict) and r.get("tablar") == tablar and r.get("faol") == faol
                       and all((o.get("el") or {}).get(i) is not None for i in bor) and all((o.get("el") or {}).get(i) is None for i in yoq)
                       and not rad and not pg.__xato and not any(v(o, i) for i in H_XATO_IDLAR)
                       and "Yuklashda xato" not in (t(o, "repBody") or "") and "yuklanmadi" not in (t(o, "repBody") or ""))
                check(f"H6 {user}: jadval bo'limlari {tablar}, birinchisi {faol}; blok bor {bor}, yo'q {yoq}; 403 / xato yo'q",
                      ok_, (r, [i for i in bor if (o.get("el") or {}).get(i) is None], [i for i in yoq if (o.get("el") or {}).get(i) is not None],
                            rad, pg.__xato, (t(o, "repBody") or "")[:80]))
                pg.close()

        if bolim("T"):
            section("T. Telefon 390 / 320 px — hamma so'rov xato")
            for w in (390, 320):
                for tema in ("light", "dark"):
                    ctx = kontekst("sy_a", w=w, h=844)
                    for url in ("/finance", "/reports"):
                        pg = sahifa(ctx)
                        if tema == "dark":
                            # base.html boshida `localStorage.theme` o'qiladi (tungi rejim — sahifa chizilishidan oldin)
                            pg.add_init_script("try { localStorage.setItem('theme', 'dark'); } catch (e) {}")
                        pg.route(lambda u: urlparse(u).path.startswith("/api/") and urlparse(u).path != "/api/notifications",
                                 XATOLAR["500_json"])
                        och(pg, url, 1300)
                        if tema == "dark":
                            ev(pg, "() => document.documentElement.setAttribute('data-theme', 'dark')")
                            pg.wait_for_timeout(200)
                        r = ev(pg, KONTRAST)
                        els = (r or {}).get("el") or [] if isinstance(r, dict) else []
                        yomon = [e for e in els if e["kontrast"] < 4.5 or e["ong"] > r["vw"] + 1 or e["chap"] < -1 or e["toshgan"]]
                        check(f"T {url} {w} px {tema}: sahifa toshmaydi (eni {w}), sabablar ekranda, qutisidan chiqmaydi va o'qiladi (kontrast ≥ 4.5), "
                              f"kamida 5 ta sabab", isinstance(r, dict) and r.get("sw", 9999) <= w + 1 and len(els) >= 5 and not yomon
                              and not pg.__xato, (r.get("sw") if isinstance(r, dict) else r, len(els), yomon[:4], pg.__xato[:1]))
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
