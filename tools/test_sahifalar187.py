#!/usr/bin/env python3
"""
test_sahifalar187.py — kech147 (zip 187): SAHIFALAR TELEFONDA, 2-qism — O'RTACHA NUQSONLAR (yashirin bo'limlar, yon tomonga suriladigan
jadvallar, tor ustunda 4+ satrli matn, bo'linib ketgan summa). HAQIQIY Chromium (Playwright, `is_mobile`, `has_touch`, `device_scale_factor=2`),
HAQIQIY lokal server, telefon brauzer paneli bilan ko'rinadigan qism (375 × 548, 360 × 560, 320 × 460) va YOTIQ telefon (667 × 375).

NIMA UCHUN KERAK (zip 186 dan KEYIN barcha sahifa qayta O'LCHANGAN — `work/k186/olchov186.py`, `natija_187a`):
  L1 Loyiha bo'limlari tasmasi: 9 bo'limdan 6 tasi (375 × 548) / 3 tasi (667 × 375) ekrandan tashqarida — surish kerakligi bilinmasdi;
     «Asosiy» bo'limida yorliq qiymatga yopishib qolardi («MijozAndijon Fasad Dekor …»).
  L2 Hisobotlar jadvali (Moliya, Ombor, Ustalar, Mahsulotlar) yon tomonga surilardi — «Xarajat», «Sof foyda», «Rentabellik» birinchi ekranda
     yo'q, nom ustuni 4–6 satr. Endi telefonda KARTA, ustun sarlavhalari — saralash tugmachalari (bosilsa saralanadi).
  L3 Hisobot reytingi: summa nomni 107 px ga siqardi (6 satr); «Salomatlik» kartasi sababi 104 px da 4–5 satr.
  L4 Tayyor mahsulotlar / Qaytarishlar raqam kartalari tasmasi: karta matni 68 px (320) / 94 px (375) — izoh 4–5 satr.
  L5 Retsept, mahsulot turi tarkibi, Dashboard qarzdor buyurtma, usta kartasi: nom tugmalar / summa bilan bir qatorda 76–117 px — 4–7 satr.
  L6 Qarzdorlar «Boshqa majburiyatlarimiz»: qolgan summa uzun izoh bilan bir qatorda 33–46 px ustunda 3 satrga bo'linardi.
  L7 Kirim: «Materiallar ro'yxati» va «Kirimlar tarixi» jadvallari yon tomonga surilardi — «Summa», 🗑, «Holati» ekrandan tashqarida.
  L8 KPI raqam kartalari 320 px: ikona yonida matn 70–72 px — 3–4 satr.
  L9 Moliya «Yo'nalishlar bo'yicha» kartalari: izoh 97–117 px da 4–6 satr.
  L10 Brak tahlili «Tayyor mahsulot yo'qotishlari» — 10 ustunli jadval yon tomonga surilardi (🧩 tugmasi oxirgi ustunda); Brak tahlili /
      hisoboti 4 ustunli jadvallarida nom 87–98 px — 4–6 satr.
  L11 Moliya «Bugungi xarajat batafsil» yotiq telefonda (667 × 375) 3 ustun — material nomi summa yonida 90 px, 6 satr.
  L12 Kirim: uzun nomli ta'minotchi tanlanganda tanlagich matni to'r ustunini kengaytirib, sahifa 375 px da 672 px — «+ Yangi», «Hujjat
      raqami», «Sana» ekrandan tashqarida; katta summalar 360 px da sahifani 370 px qilardi.
  L13 Rollar to'ri (JONLI sinov — staging): 140 px ustunda rol izohi 75–77 px, 4 satr (360 × 560, 667 × 375).
  L14 Qarzdorlar bo'lim tugmasi (JONLI sinov — staging, 320 px): «Bizga qarzdorlar (10 mijoz · 15 buyurtma)» bir qatorda 309 px — kontent
      yon tomonga surilardi.
  L15 Moliya «Qarzlar va majburiyatlar» (PRODUCTION skrinshoti 16.10 21:57): «Arenda/Soliq/Komm | unal» — so'z o'rtasidan bo'linardi.
O'lchov — `tools/test_sahifalar186.py` TEKSHIR_JS (X yon tomonga suriladigan o'ram, T tor matn bloki, K kesilgan boshqaruv, M kesilgan matn,
H hujjat eni) va sahifa kontentining yon tomonga surilmasligi; S — statik: klasslar / qoidalar shablonda.
Ma'lumot — ilovaning O'Z API si orqali: `tools/test_c_telefon.py` ZANJIR_JS + `tools/test_oynalar184.py` QOSHIMCHA_JS +
`tools/test_sahifalar186.py` QOSHIMCHA186_JS (matnlari o'qiladi, fayllar BAJARILMAYDI).
REJIM: SQLite (`PG_URL` e'tiborsiz — ko'rinish baza turiga bog'liq emas); `TENANT_FILTER=1` ham. `T187_FAQAT=kalit1,kalit2` — faqat shu holatlar.
Asl kodga (zip 186) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_sahifalar187.py
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
_T = tempfile.mkdtemp(prefix="sahifa187_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'sahifa187.db')}"
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
section("S. Statik: klasslar va telefon qoidalari shablonda")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_P = oqi("templates/projects.html")
check("S1 Loyiha bo'limlari — ≤ 900 px da qatorga sig'masa o'tadi (yon tomonga suriladigan tasma emas)",
      "@media (max-width:900px){ #tabBar.tab-bar{flex-wrap:wrap;overflow-x:visible;row-gap:6px} }" in _P)
check("S2 Loyiha «Asosiy» — yorliq va qiymat orasida bo'shliq, uzun qiymat o'ngda o'raladi",
      ".info-row{display:flex;justify-content:space-between;gap:12px;" in _P and ".info-row > span:last-child{min-width:0;text-align:right;overflow-wrap:anywhere}" in _P)
_RP = oqi("templates/reports.html")
check("S3 Hisobot jadvali — `telefon-karta`, kataklarda `data-label` (ustun nomi), sarlavhalar telefonda saralash tugmachalari",
      '<table class="bi-table telefon-karta" id="repTable">' in _RP and '`<td data-label="${escapeHtml(h[0])}">${h[1](row)}</td>`' in _RP
      and "#repTable.telefon-karta > thead{display:block;margin-bottom:10px}" in _RP)
check("S4 Hisobot reytingi — summa sig'masa keyingi qatorga; «Salomatlik» ≤ 360 px da bitta ustun",
      ".bi-top-row{flex-wrap:wrap;row-gap:2px}" in _RP and "@media(max-width:360px){.bi-health-grid{grid-template-columns:1fr}}" in _RP)
check("S5 Raqam kartalari tasmasi (Tayyor mahsulotlar, Qaytarishlar) — ≤ 420 px da karta 62 %",
      "@media(max-width:420px){ .fp-stat-tasma > .stat-card{flex:0 0 62%} }" in oqi("templates/finished.html")
      and "@media(max-width:420px){ .ret-stat-tasma > .stat-card{flex:0 0 62%} }" in oqi("templates/returns.html"))
_RC = oqi("templates/recipes.html")
_DB = oqi("templates/dashboard.html")
_MM = oqi("templates/masters_manage.html")
check("S6 Retsept / mahsulot turi tarkibi / Dashboard qarzdor buyurtma / usta kartasi — sig'masa tugmalar (summa) keyingi qatorga o'tadi",
      'class="rec-nom"' in _RC and 'class="rec-amal"' in _RC and ".rec-head{flex-wrap:wrap;row-gap:10px}" in _RC
      and ".pt-retsept{flex-wrap:wrap;row-gap:6px}" in oqi("templates/production.html")
      and all(x in _DB for x in ('class="dash-qarz-qator"', 'class="dash-qarz-chap"', 'class="dash-qarz-ong"', "${escapeHtml(d.order_number)}",
                                 "  .dash-qarz-qator{flex-wrap:wrap;row-gap:4px}"))
      and 'class="mk-asosiy"' in _MM and 'class="mk-tugmalar"' in _MM and ".mk-card{flex-wrap:wrap;row-gap:10px;padding:12px}" in _MM)
_D = oqi("templates/debts.html")
check("S7 Qarzdorlar «Boshqa majburiyatlarimiz» — `oblig-sarlavha` / `oblig-chap` / `oblig-summa` (hodim va doimiy), summa bo'linmaydi",
      _D.count('class="oblig-sarlavha"') == 2 and _D.count('class="oblig-chap"') == 2 and _D.count('class="oblig-summa"') == 2
      and ".oblig-summa{flex-shrink:0;white-space:nowrap;text-align:right}" in _D)
_SR = oqi("templates/supplier_receive.html")
check("S8 Kirim — «Materiallar ro'yxati» va «Kirimlar tarixi» jadvallari `telefon-karta`, kataklarda `data-label`",
      _SR.count('<table class="rcv-table telefon-karta">') == 2 and 'data-label="Holati" class="kirim-holat"' in _SR
      and '<td data-label="Material nomi"' in _SR and '<td data-label="" style="text-align:right"><button class="rcv-icon-btn" onclick="apRemoveFromBasket(${i})"' in _SR)
check("S12 Kirim — to'r katagi mazmun (uzun ta'minotchi nomi, katta summa) bilan kengaymaydi, ≤ 420 px da summalar bitta ustunda",
      ".rcv-row > *{min-width:0}" in _SR and ".rcv-stat-grid > *{min-width:0}" in _SR and "  .rcv-stat-grid{grid-template-columns:1fr}" in _SR)
check("S9 KPI raqam kartalari — ≤ 380 px da ikona matn ustida",
      '@media (max-width: 380px) {\n  .kpi-grid > .kpi-card[style*="display:flex"]{flex-direction:column;' in oqi("templates/kpi.html"))
check("S10 Moliya «Yo'nalishlar bo'yicha» kartalari — ≤ 380 px da bitta ustun",
      "@media(max-width:380px){ .yon-kartalar{ grid-template-columns:minmax(0, 1fr); } }" in oqi("templates/finance.html"))
_RT = oqi("templates/returns.html")
check("S11 Brak tahlili «Tayyor mahsulot yo'qotishlari» jadvali — `telefon-karta`, 10 katakda `data-label`",
      'class="telefon-karta brak-yoqotish-jadval"' in _RT
      and all(f'<td data-label="{x}"' in _RT for x in ("Sana", "Mahsulot", "Miqdor", "Turi", "Bosqich", "Sabab", "Javobgar", "Qiymati", "Yozgan", "Taqdiri")))
check("S13 Brak tahlili / hisoboti 4 ustunli jadvallari — `brak-jadval` (guruh, «Eng ko'p brak», «Oylar bo'yicha», «Material bo'yicha jami»), "
      "raqam kataklarida `data-label`",
      _RT.count('class="brak-jadval"') == 4 and "table.brak-jadval > tbody > tr > td:not(:first-child)::before{content:attr(data-label)" in _RT
      and '<td data-label="Ulushi"' in _RT and '<td data-label="m³"' in _RT)
check("S14 Moliya «Bugungi xarajat batafsil» — 641–900 px da ikki ustun, qatorda summa bo'linmaydi",
      "@media (min-width:641px) and (max-width:900px){ #todayDetailPanel > div{ grid-template-columns:1fr 1fr !important; } }" in oqi("templates/finance.html")
      and ".fin-breakdown-row > span:last-child{ flex-shrink:0; white-space:nowrap; margin-left:auto; }" in oqi("templates/finance.html"))
check("S15 Rollar to'ri — har ustun kamida 160 px; Qarzdorlar bo'lim tugmasi telefonda ikki qatorga o'tadi",
      ".rl-royxat{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr))}" in oqi("templates/rollar.html")
      and "@media(max-width:600px){.dbt-tab{white-space:normal;max-width:100%;min-width:0;text-align:center}}" in _D)
check("S16 Moliya «Qarzlar va majburiyatlar» — «Arenda/Soliq/Kommunal» yozuvida «/» dan keyin bo'linish joyi (so'z o'rtasidan bo'linmaydi)",
      "🏛️ Arenda/<wbr>Soliq/<wbr>Kommunal</div>" in oqi("templates/finance.html") and "🏛️ Arenda/Soliq/Kommunal</div>" not in oqi("templates/finance.html"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Ma'lumot va o'lchov
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "s187_admin", "Parol123!"
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


# element ekranda to'liq ko'rinadigan ulushi (eni bo'yicha)
KORINISH = ("() => [...document.querySelectorAll(%s)].filter(b => b.offsetParent).map(b => { const r = b.getBoundingClientRect();"
            " return Math.round(Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0)) / r.width * 100) / 100; })")


def _toliq(eng_kam):
    return lambda v, w, h: isinstance(v, list) and len(v) >= eng_kam and min(v) >= 0.99


def _telefon_karta(w, h):
    """style.css `table.telefon-karta` qoidasi qo'llanadigan o'lcham (≤ 600 px YOKI yotiq telefon ≤ 950 × 500)"""
    return w <= 600 or (w <= 950 and h <= 500)


LOYIHA = "document.querySelector('.proj-card').click(); await uxla(1500); "
holat("loyiha_tablar", "L1", "/projects", LOYIHA, "#tabBar", tekshir="XK", izoh="bo'limlar tugmalari",
      qosh=[("HAMMA bo'lim tugmasi (9 ta) birinchi ekranda to'liq — surish shart emas", KORINISH % "'#tabBar .tab-btn'", _toliq(9))])
holat("loyiha_asosiy", "L1", "/projects", LOYIHA + "switchTab('asosiy', true); await uxla(800);", "#tabContent", izoh="«Asosiy» bo'limi",
      qosh=[("yorliq va qiymat yopishmaydi (bir qatorda bo'lsa orasi ≥ 8 px)",
             "() => [...document.querySelectorAll('#tabContent .info-row')].filter(r => r.offsetParent && r.children.length === 2 && r.children[0].tagName === 'SPAN')"
             ".map(r => { const A = r.children[0].getBoundingClientRect(), B = r.children[1].getBoundingClientRect();"
             " return B.top < A.bottom - 2 ? Math.round(B.left - A.right) : 99; })",
             lambda v, w, h: isinstance(v, list) and len(v) >= 5 and min(v) >= 8)])
_JADVAL_KARTA = ("() => { const t = document.getElementById('repTable'); if (!t) return null; const q = t.querySelector('tbody tr');"
                 " const ths = [...t.querySelectorAll('thead th')]; const nomlar = ths.map(x => x.textContent.replace(/[▲▼]/g, '').trim());"
                 " const yorliq = q ? [...q.children].map(td => td.getAttribute('data-label')) : [];"
                 " return {thead: getComputedStyle(t.querySelector('thead')).display, qator: q ? getComputedStyle(q).display : null, n: t.querySelectorAll('tbody tr').length,"
                 " yorliq_mos: yorliq.length === nomlar.length && yorliq.every((y, i) => y === nomlar[i]),"
                 " tugma: ths.map(b => { const r = b.getBoundingClientRect(); return Math.round(Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0)) / r.width * 100) / 100; })}; }")
_SARALASH = ("() => { const ths = document.querySelectorAll('#repTable thead th'); if (ths.length < 2) return null; ths[1].click();"
             " const t2 = document.querySelectorAll('#repTable thead th')[1]; const q = document.querySelector('#repTable tbody tr');"
             " return {belgi: t2.textContent.includes('▲') || t2.textContent.includes('▼'), yorliq: q ? q.children[1].getAttribute('data-label') : null,"
             " nom: t2.textContent.replace(/[▲▼]/g, '').trim()}; }")


def _jadval_karta_shart(v, w, h):
    if not isinstance(v, dict) or not v.get("yorliq_mos") or v.get("n", 0) < 1:
        return False
    if _telefon_karta(w, h):
        return v.get("qator") == "block" and v.get("thead") == "block" and v.get("tugma") and min(v["tugma"]) >= 0.99
    return v.get("qator") == "table-row"


for _kalit, _r, _nom in (("moliya", "finance", "Moliya"), ("ombor", "inventory", "Ombor"), ("ustalar", "masters", "Ustalar"), ("mahsulot", "products", "Mahsulotlar")):
    holat(f"hisobot_jadval_{_kalit}", "L2", "/reports", f"switchReport('{_r}'); await uxla(2000);", ".bi-section-table", izoh=f"«{_nom}» hisoboti jadvali",
          qosh=[("telefonda (yotiq ham) jadval — KARTA, ustun sarlavhalari — ekranda to'liq saralash tugmachalari; kataklarda ustun nomi", _JADVAL_KARTA,
                 _jadval_karta_shart),
                ("sarlavha (tugmacha) bosilsa saralanadi (▲ / ▼), katak nomi saralashdan keyin ham to'g'ri", _SARALASH,
                 lambda v, w, h: isinstance(v, dict) and v.get("belgi") and v.get("yorliq") == v.get("nom"))])
holat("hisobot_reyting", "L3", "/reports", "switchReport('finance'); await uxla(2000);", ".bi-top-grid", izoh="reytinglar (eng ko'p …)")
holat("hisobot_salomatlik", "L3", "/reports", "switchReport('finance'); await uxla(2000);", "#healthGrid", izoh="«Salomatlik» kartalari")


def _tasma_shart(v, w, h):
    """≤ 420 px — karta tasma enining ≥ 58 % i; 421–600 px — tasma (46 %); > 600 px — tasma emas (to'r), shart yo'q"""
    if not (isinstance(v, list) and len(v) >= 3):
        return False
    return min(v) >= 0.58 if w <= 420 else (min(v) >= 0.4 if w <= 600 else True)


holat("tayyor_tasma", "L4", "/finished", "await uxla(1200);", ".fp-stat-tasma", tekshir="XT", ruxsat=".fp-stat-tasma", izoh="raqam kartalari tasmasi (ataylab suriladi)",
      qosh=[("≤ 420 px da karta tasma enining ≥ 58 % i (matn tor ustunga siqilmaydi)",
             "() => { const t = document.querySelector('.fp-stat-tasma'); return [...t.children].map(c => Math.round(c.getBoundingClientRect().width / t.clientWidth * 100) / 100); }",
             _tasma_shart)])
holat("qaytarish_tasma", "L4", "/returns", "await uxla(800);", "#kpiRow", tekshir="XT", ruxsat="#kpiRow", izoh="raqam kartalari tasmasi (ataylab suriladi)",
      qosh=[("≤ 420 px da karta tasma enining ≥ 58 % i",
             "() => { const t = document.getElementById('kpiRow'); return [...t.children].filter(c => c.offsetParent).map(c => Math.round(c.getBoundingClientRect().width / t.clientWidth * 100) / 100); }",
             _tasma_shart)])
holat("retseptlar", "L5", "/recipes", "await uxla(500);", ".rec-grid", izoh="retsept kartalari",
      qosh=[("✏️ / 🗑 ekranda to'liq", KORINISH % "'.rec-amal > button'", _toliq(2)),
            ("✏️ va 🗑 bir qatorda (birga o'tadi)",
             "() => [...document.querySelectorAll('.rec-amal')].filter(a => a.offsetParent).map(a => { const b = [...a.children].map(x => Math.round(x.getBoundingClientRect().top));"
             " return b.length === 2 && b[0] === b[1]; })", lambda v, w, h: isinstance(v, list) and len(v) >= 1 and all(v))])
holat("ishlab_turlar", "L5", "/production", "await uxla(1200);", ".pt-jadval-qobiq", izoh="mahsulot turlari va tarkiblari",
      qosh=[("tarkib «Tahrirlash» / 🗑 ekranda to'liq", KORINISH % "'.pt-retsept-amal .btn'", _toliq(1))])
holat("dashboard_qarz", "L5", "/dashboard", "await uxla(1500);", "#debtList", izoh="qarzdor buyurtmalar",
      qosh=[("qarz summasi mijoz / loyiha bilan ustma-ust tushmaydi",
             "() => [...document.querySelectorAll('.dash-qarz-qator')].map(r => { const A = r.querySelector('.dash-qarz-chap').getBoundingClientRect(),"
             " Q = r.querySelector('.dash-qarz-ong').getBoundingClientRect(); return !(Q.left < A.right - 1 && Q.right > A.left + 1 && Q.top < A.bottom - 1 && Q.bottom > A.top + 1); })",
             lambda v, w, h: isinstance(v, list) and len(v) >= 1 and all(v))])
holat("ustalar", "L5", "/ustalar", "await uxla(800);", "#mkList", izoh="ustalar ro'yxati",
      qosh=[("✏️ / 🚫 ekranda to'liq", KORINISH % "'#mkList .mk-tugmalar button'", _toliq(2))])
holat("qarz_korxona", "L6", "/debts", "switchTab('company'); await uxla(800);", "#tab-company", izoh="«Boshqa majburiyatlarimiz»",
      qosh=[("qolgan summa bitta qatorda (bo'linmaydi)",
             "() => [...document.querySelectorAll('#tab-company .oblig-summa')].filter(e => e.offsetParent).map(e => { const n = e.children.length ? e.children[0] : e;"
             " const rg = document.createRange(); rg.selectNodeContents(n); return new Set([...rg.getClientRects()].filter(r => r.width > 0.5).map(r => Math.round(r.top))).size; })",
             lambda v, w, h: isinstance(v, list) and len(v) >= 2 and max(v) == 1)])
# eng UZUN nomli ta'minotchi tanlanadi (tanlagich matni ustunni kengaytirmasin — L12)
_SAVAT = ("const s = document.getElementById('r-supplier'); const o = [...s.options].filter(x => x.value).sort((p, q) => q.text.length - p.text.length)[0];"
          " if (o) { s.value = o.value; await onSupplierChange(); await uxla(1500); }"
          " apBasket.push({itemName: window.__M + ' Kley akril (oq, ichki va tashqi ishlar uchun)', qty: 12.5, unit: 'kg', price: 125000, total: 1562500, isPenoplast: false});"
          " renderBasket(); await uxla(300);")


def _jadval_kartami(sel):
    return ("() => { const t = document.querySelector('%s'); if (!t) return null; const q = t.querySelector('tbody tr');"
            " return {thead: getComputedStyle(t.querySelector('thead')).display, qator: q ? getComputedStyle(q).display : null,"
            " yorliq: q ? [...q.children].map(td => td.getAttribute('data-label')) : []}; }" % sel)


def _kartami(v, w, h):
    if not isinstance(v, dict) or v.get("qator") is None:
        return False
    return (v.get("thead") == "none" and v.get("qator") == "block") if _telefon_karta(w, h) else v.get("qator") == "table-row"


holat("kirim_savat", "L7", "/suppliers/receive", _SAVAT, ".rcv-card:has(#rcv-basket-body)", izoh="«Materiallar ro'yxati» (1 material qo'shilgan)",
      qosh=[("telefonda (yotiq ham) jadval — KARTA, kataklarda ustun nomi", _jadval_kartami(".rcv-card:has(#rcv-basket-body) table"),
             lambda v, w, h: _kartami(v, w, h) and v["yorliq"][:5] == ["№", "Material nomi", "Miqdor", "1 birlik narxi", "Summa"]),
            ("🗑 (ro'yxatdan olib tashlash) ekranda to'liq", KORINISH % "'#rcv-basket-body .rcv-icon-btn'", _toliq(1))])
holat("kirim_taminotchi", "L12", "/suppliers/receive", _SAVAT, ".rcv-card", izoh="eng uzun nomli ta'minotchi tanlangan",
      qosh=[("kirim sahifasi (`.rcv-wrap`) yon tomonga toshmaydi", "() => { const p = document.querySelector('.rcv-wrap'); return p ? [p.scrollWidth, p.clientWidth] : null; }",
             lambda v, w, h: isinstance(v, list) and v[0] <= v[1] + 1),
            ("«+ Yangi» (ta'minotchi) ekranda to'liq", KORINISH % "'.rcv-supplier-row .rcv-btn'", _toliq(1))])
holat("kirim_tarix", "L7", "/suppliers/receive", _SAVAT, ".rcv-card:has(#rcv-history-body)", izoh="«Kirimlar tarixi» (ta'minotchi tanlangan)",
      qosh=[("telefonda (yotiq ham) jadval — KARTA, kataklarda ustun nomi", _jadval_kartami(".rcv-card:has(#rcv-history-body) table"),
             lambda v, w, h: _kartami(v, w, h) and v["yorliq"] == ["Sana", "Material", "Miqdor", "1 birlik narxi", "Summa", "Holati"])])
holat("kpi_raqamlar_matn", "L8", "/kpi", "await uxla(1500);", ".kpi-grid", izoh="raqam kartalari (matn tor ustunga siqilmaydi)")
holat("moliya_yonalish", "L9", "/finance", "await uxla(2500);", ".yon-kartalar", izoh="«Yo'nalishlar bo'yicha» kartalari")
# «Tayyor mahsulot yo'qotishlari» — sinov bazasida yo'qotish yozuvi bo'lmasa, sahifaning O'Z chizuvchisi (`brakTahlilHtml`) serverdan kelgan
# tahlilga BITTA namuna qator qo'shib chiziladi (ko'rinish tekshiriladi, ma'lumot yozilmaydi)
_BRAK = ("toggleBrakTahlil(); await uxla(1800); const d = await (await fetch('/api/reports/brak-tahlil?oylar=6', {credentials: 'same-origin'})).json();"
         " if (!(d.yoqotishlar || []).length) d.yoqotishlar = [{id: 990001, sana: '2026-10-10T09:30:00', nomi: window.__M + ' Fasad ustuni (namuna, sinov)', miqdor: 3, birlik: 'dona',"
         " turi: 'Brak', bosqich: 'Qoplash', sabab: 'Qoplama ko\\'chdi', javobgar: window.__M + ' Usta', qiymat: 1234567, yozgan: 'admin', taqdir_yorliq: 'Tashlandi', manba: 'ombor'}];"
         " document.getElementById('brakTahlilContent').innerHTML = brakTahlilHtml(d); await uxla(300);")
holat("brak_yoqotish", "L10", "/returns", _BRAK, "#brakTahlilBody", izoh="«Brak tahlili» ochiq",
      qosh=[("«Tayyor mahsulot yo'qotishlari» telefonda (yotiq ham) — KARTA", _jadval_kartami(".brak-yoqotish-jadval"),
             lambda v, w, h: _kartami(v, w, h) and len(v["yorliq"]) == 10),
            ("🧩 (taqdirini o'zgartirish) ekranda to'liq", KORINISH % "'.brak-yoqotish-jadval .brak-taqdir-btn'", _toliq(1))])
holat("moliya_bugun_batafsil", "L11", "/finance", "await uxla(1500); toggleTodayDetail(); await uxla(1200);", "#todayDetailPanel",
      izoh="«Bugungi xarajat batafsil» ochiq")
holat("rollar_ustun", "L13", "/rollar", "await uxla(1000);", "#rlRoyxat", izoh="rollar to'ri",
      qosh=[("har rol kartasi ≥ 150 px (izoh tor ustunga siqilmaydi)", "() => [...document.querySelectorAll('#rlRoyxat .rl-item')].filter(b => b.offsetParent).map(b => Math.round(b.getBoundingClientRect().width))",
             lambda v, w, h: isinstance(v, list) and len(v) >= 2 and min(v) >= 150)])
# staging da «Bizga qarzdorlar (10 mijoz · 15 buyurtma)» — sinov bazasida yozuv qisqa: o'sha uzunlikdagi yozuv qo'yiladi (faqat ko'rinish)
holat("qarz_tablar", "L14", "/debts", "const t = document.querySelector('.dbt-tab'); t.lastChild.textContent = ' Bizga qarzdorlar (10 mijoz · 15 buyurtma)'; await uxla(300);",
      ".dbt-tabs", izoh="uzun yozuvli bo'lim tugmasi",
      qosh=[("bo'lim tugmalari ekranda to'liq", KORINISH % "'.dbt-tabs .dbt-tab'", _toliq(3))])
# «Kommunal» so'zi bitta satrda (zip 186 dagi `overflow-wrap:anywhere` bilan «Komm | unal» bo'linardi — production skrinshoti)
_SOZ_BUTUN = ("() => { const e = [...document.querySelectorAll('#debt-summary-grid .dg-box > div')].find(d => d.textContent.includes('Kommunal')); if (!e) return null;"
              " const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode()) && !n.textContent.includes('Kommunal')) {} if (!n) return null;"
              " const i = n.textContent.indexOf('Kommunal'); const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 8);"
              " return new Set([...r.getClientRects()].filter(x => x.width > 0.5).map(x => Math.round(x.top))).size; }")
holat("moliya_qarzlar", "L15", "/finance", "await uxla(2500);", "#debt-summary-grid", izoh="«Qarzlar va majburiyatlar» kartalari",
      qosh=[("«Kommunal» so'zi bo'linmaydi (bitta satrda)", _SOZ_BUTUN, lambda v, w, h: v == 1)])

FAQAT = [x.strip() for x in os.environ.get("T187_FAQAT", "").split(",") if x.strip()]

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
