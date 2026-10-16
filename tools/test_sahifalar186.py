#!/usr/bin/env python3
"""
test_sahifalar186.py — kech147 (zip 186): SAHIFALAR TELEFONDA, 1-qism — BUZILISHLAR (tor ustun, ustma-ust matn, yashirin tugma, qirqilgan
summa, sahifaning yon tomonga toshishi). HAQIQIY Chromium (Playwright, `is_mobile`, `has_touch`, `device_scale_factor=2`), HAQIQIY lokal server,
telefon brauzer paneli bilan ko'rinadigan qism (375 × 548, 360 × 560, 320 × 460) va YOTIQ telefon (667 × 375).

NIMA UCHUN KERAK (egasining production skrinshoti 16.10 14:28 — KPI sahifasi «Hodimlar oylik hisob-kitobi» jadvali yon tomonga surilgan holda;
so'ng BARCHA sahifa O'LCHANGAN — `work/k186/olchov186.py`, zip 185 kodi):
  K1 KPI «Hodimlar oylik hisob-kitobi»: jadval o'rami 309 / 700 px — «+ Bonus», «− Kamaytirish», «Avans olingan», «Qolgan to'lov» birinchi
     ekranda yo'q (10 tugmadan 10 tasi), «Tafsilot» 81 px ustunda 12 satr (qator 250 px; 667 × 375 da ham); 667 × 375 da raqam kartalari
     (`repeat(5,1fr)` inline) sahifani 952 px ga kengaytirardi, ustalar / hodimlar ikki ustunida usta kartasi tugmalari qirqilardi.
  K2 Ta'minotchilar ro'yxati: nom 30 px ustunda 8 satr, qarz summasi telefon raqami USTIGA tushardi; sarlavhadagi 180 px qidiruv 320 px da
     kartadan chiqib qirqilardi.
  K3 Qaytarishlar ro'yxati: nom ustuni 5 px (15 satr) — kartadagi inline `flex:1` media qoidani bekor qilardi, «2 ta» nom ustida.
  K4 Tanlangan buyurtma detallari: nom 95 px (375) / 40 px (320 — 15 satr).
  K5 O'chirilganlar: hodim qatorida tugmalar nom ustida (nom 44 px), jurnal qatori 72 px — 8 satr.
  K6 `telefon-karta` jadvallari (Moliya tranzaksiyalari, Foydalanuvchilar) yotiq telefonda (667 × 375) karta EMAS edi — ✎ / 🗑 / «Parol»
     birinchi ekranda yo'q; karta sarlavhasi (h3 + havola / qidiruv) sig'masa qatorga o'tmasdi.
  K7 Loyiha «Xomashyo» / «Mahsulotlar»: nom 49 px (6 satr) va son formati («−5.400000000000001 blok»); «Moliya» yorlig'i 320 px da 6 px toshardi.
  K8 Moliya «Xarajatlar tafsiloti»: guruh sarlavhasi 320 px da 33 px (harfma-harf), «Hodimlar» / «Usta KPI» qatorida summa kartadan chiqib
     QIRQILARDI (346 > 287 px).
  K9 Rollar ro'yxati telefonda yon tomonga suriladigan tasma — 4 roldan 2 tasi ekranda yo'q.
  K10 Ishlab chiqarish ro'yxati filtri: «Mahsulot» tanlagichi uzun nom bilan 359 px — kontent 375 / 435 px.
  K11 Hisobotlar 320 px: raqam kartalari / grafik ustuni hisobotni 358 px ga kengaytirardi.
  K13 Moliya «Bugungi holat» katta summalari karta chetida QIRQILARDI (375 × 548 — «2 505 141 69…»; 667 × 375, 4 ustun — «1 644 00…»).
  K14 Qarzdorlar ro'yxatlari 320 px: qarz summasi karta chetida qirqilardi (0,84), nom / loyiha 63–107 px ustunda 4–6 satr.
O'lchov (TEKSHIR_JS — `work/k186/olchov186.py` dagi SAHIFA_JS bilan bir qoida, tekshiriladigan bo'lim — `root` ichida):
  X yon tomonga suriladigan o'ram (overflow-x auto / scroll, scrollWidth > clientWidth); T TOR MATN BLOKI (ichida faqat qator ichidagi elementlar,
  matni ≥ 24 belgi, eni < 120 px, HAQIQIY satrlari ≥ 4 — Range.getClientRects); K KESILGAN BOSHQARUV (tugma / maydon `overflow: hidden` ota yoki
  ekran cheti tufayli eni bo'yicha < 0.9 ko'rinadi); M KESILGAN MATN (matn bloki ota tufayli < 0.95 ko'rinadi; o'zining ellipsis i hisobga
  olinmaydi); H hujjat eni > ekran.
S — statik: klasslar / qoidalar shablonda, kesh versiyasi yangilangan.
Ma'lumot — ilovaning O'Z API si orqali: `tools/test_c_telefon.py` ZANJIR_JS + `tools/test_oynalar184.py` QOSHIMCHA_JS (matni o'qiladi) +
QOSHIMCHA186_JS (shu oy ichida ishga kirgan hodim — uzun «Tafsilot», «oylik + metr», ishbay hodim).
REJIM: SQLite (`PG_URL` e'tiborsiz — ko'rinish baza turiga bog'liq emas); `TENANT_FILTER=1` ham. `T186_FAQAT=kalit1,kalit2` — faqat shu holatlar.
Asl kodga (zip 185) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_sahifalar186.py
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
_T = tempfile.mkdtemp(prefix="sahifa186_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'sahifa186.db')}"
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
_K = oqi("templates/kpi.html")
check("S1 KPI oylik hisob-kitob jadvali — klasslar (`oylik-jadval`, `oylik-qator`, `oq-*` + `data-label`) va ≤ 768 px karta qoidasi",
      all(x in _K for x in ('class="oylik-jadval"', 'class="oylik-qator"', 'class="oq-hodim"', 'class="oq-tafsilot"', 'class="oq-asosiy" data-label="Asosiy hisob"',
                            'class="oq-avans" data-label="Avans olingan"', 'class="oq-qolgan" data-label="Qolgan to\'lov"', 'class="oq-bonus"', 'class="oq-kamay"',
                            'class="oylik-avans-qator"', 'class="oylik-avans-band"'))
      and re.search(r"@media \(max-width: 768px\) \{\s*\.oylik-jadval-orama\{overflow-x:visible !important\}", _K) is not None)
check("S2 KPI avans tafsiloti ochilganda qator uslubi bo'shatiladi ('' — telefonda karta, kompyuterda jadval qatori), 'table-row' emas",
      "row.style.display = '';" in _K and "row.style.display = 'table-row';" not in _K)
check("S3 KPI raqam kartalari 768 px gacha sig'ganicha (inline `repeat(N,1fr)` bekor) va `.kpi-two` 768 px gacha bitta ustun",
      re.search(r"@media \(max-width: 768px\) \{\s*\.kpi-two\{grid-template-columns:1fr\}\s*\.kpi-grid\[style\*=\"repeat\(\"\]\{grid-template-columns:repeat\(auto-fit,minmax\(150px,1fr\)\) !important\}", _K)
      is not None)
_S = oqi("templates/suppliers.html")
check("S4 Ta'minotchilar qatori — `sup-asosiy` / `sup-qarz` va ≤ 600 px qatordan o'tish qoidasi",
      'class="sup-asosiy"' in _S and 'class="sup-qarz"' in _S and ".sup-row{flex-wrap:wrap" in _S)
check("S5 Qaytarishlar — nom ustuni rasm yonidagi butun kenglik (`calc(100% - 54px) !important` — inline `flex:1` dan ustun)",
      ".ret-name{ order:1; flex:1 1 calc(100% - 54px) !important;" in oqi("templates/returns.html"))
check("S6 Buyurtma detali — telefonda `.prod-row` qatordan o'tadi, summa keyingi qatorda", ".prod-row{flex-wrap:wrap;row-gap:6px}" in oqi("templates/orders.html"))
_TR = oqi("templates/trash.html")
check("S7 O'chirilganlar — `savat-qator` (loyiha, buyurtma, hodim) va `savat-jurnal-qator`",
      _TR.count('class="savat-qator"') == 3 and 'class="savat-jurnal-qator"' in _TR)
_CSS = oqi("static/style.css")
check("S8 style.css: `telefon-karta` yotiq telefonda ham karta (≤ 950 px eni VA ≤ 500 px bo'yi), karta sarlavhasi ≤ 600 px da o'tadi",
      re.search(r"@media \(max-width: 950px\) and \(max-height: 500px\) \{\s*table\.telefon-karta, table\.telefon-karta > tbody", _CSS) is not None
      and ".card-head { flex-wrap: wrap; row-gap: 6px; column-gap: 10px; }" in _CSS)
_P = oqi("templates/projects.html")
check("S9 Loyiha xomashyo / mahsulot qatori — `zebra-qiymatli` / `zebra-matn`, miqdor `sonKor(…, 3)` bilan (xom kasr «5.400000000000001» emas)",
      _P.count('class="zebra-row zebra-qiymatli"') == 2 and "−${sonKor(m.quantity, 3)}" in _P and "${sonKor(i.order_qty_normalized, 3)}" in _P
      and "−${m.quantity}" not in _P)
_F = oqi("templates/finance.html")
check("S10 Moliya xarajat tafsiloti — guruh sarlavhasi / qator / `fin-exp-ichki` (2) / `fin-naqd-mat` qatordan o'tadi, naqd material miqdori sonKor",
      _F.count('class="fin-exp-ichki"') == 2 and 'class="fin-naqd-mat"' in _F and "(${sonKor(m.quantity, 3)}" in _F
      and ".fin-exp-group-head{ flex-wrap:wrap; row-gap:4px; }" in _F)
check("S11 Rollar ro'yxati telefonda to'r (yon tomonga suriladigan tasma emas)",
      ".rl-royxat{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr))}" in oqi("templates/rollar.html")   # zip 187: 140 → 160 px
      and ".rl-royxat{flex-direction:row;overflow-x:auto" not in oqi("templates/rollar.html"))
check("S12 Ishlab chiqarish filtri — yorliq / tanlagich `min-width:0` (uzun nom kontentni kengaytirmaydi)",
      ".po-saralash label{min-width:0;max-width:100%}" in oqi("templates/production.html"))
check("S13 Hisobotlar — raqam kartalari va grafik ustuni katagi `min-width:0`",
      ".bi-kpi-grid > *, .bi-charts-grid > *{min-width:0}" in oqi("templates/reports.html"))
check("S15 Moliya «Bugungi holat» summasi kesilmaydi (`overflow-wrap:anywhere`), 900 px gacha ikki ustun",
      ".fin-hero-value{ overflow-wrap:anywhere; }" in _F and "@media (max-width:900px){ .fin-hero-grid{ grid-template-columns:1fr 1fr; gap:12px; }" in _F)
check("S16 Qarzdorlar ro'yxati — telefonda summa sig'masa keyingi qatorga o'tadi",
      ".dbt-item-body > div:first-child{flex-wrap:wrap;column-gap:8px}" in oqi("templates/debts.html"))
_MAIN = oqi("main.py")
_sv = re.search(r'templates\.env\.globals\["static_version"\]\s*=\s*"([^"]+)"', _MAIN)
check("S14 kesh versiyasi yangilangan (style.css o'zgardi — telefonda eski uslub keshdan olinmasin): «20261005-2» dan keyingi",
      _sv and _sv.group(1) > "20261005-2", _sv.group(1) if _sv else None)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Ma'lumot va o'lchov
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "s186_admin", "Parol123!"
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

# KPI oylik hisob-kitobi uchun: shu oy ichida (2-kuni) ishga kirgan hodim — «Doimiy oylik × N/31 kun ishlagan (ishga kirgan …)»; «oylik +
# metr» va ishbay hodim (uzun «Tafsilot»)
QOSHIMCHA186_JS = r"""async (a) => {
  const L = []; const R = {};
  const so = async (u, usul, tana) => { const o = {method: usul || 'GET', credentials: 'same-origin'};
    if (tana !== undefined) { o.headers = {'Content-Type': 'application/json'}; o.body = JSON.stringify(tana); }
    const r = await fetch(u, o); const t = await r.text(); let j = null; try { j = JSON.parse(t); } catch (e) {} L.push([u, r.status, t.slice(0, 160)]); return {st: r.status, j}; };
  const kun = Math.min(a.kun, 2);
  const h = await so('/api/employees', 'POST', {name: a.M + ' Oy Ichida Kirgan Hodim', position: "Bo'yoqchi", pay_type: 'fixed', fixed_amount: 3100000,
                                               production_type: 'umumiy', ishga_kirgan_sana: a.yil + '-' + String(a.oy).padStart(2, '0') + '-' + String(kun).padStart(2, '0')});
  R.oy_ichida = h.j && h.j.id;
  const h2 = await so('/api/employees', 'POST', {name: a.M + " Bo'yoqchi Metr Hodim", position: "Bo'yoqchi", pay_type: 'fixed_plus_coating', fixed_amount: 1500000,
                                                per_unit_rate: 1000, per_unit_type: 'metr', production_type: 'umumiy', ishga_kirgan_sana: '2026-01-05'});
  R.metr = h2.j && h2.j.id;
  const h3 = await so('/api/employees', 'POST', {name: a.M + ' Ishbay Kesuvchi Hodim', position: 'Kesuvchi', pay_type: 'per_unit', per_unit_rate: 12500,
                                                per_unit_type: 'blok', production_type: 'umumiy', ishga_kirgan_sana: '2026-01-05'});
  R.ishbay = h3.j && h3.j.id;
  return {R, L: L.filter(x => !(x[1] >= 200 && x[1] < 300))};
}"""

# Tekshiriladigan bo'lim (`root`) ichida: X / T / K / M va hujjat eni — `work/k186/olchov186.py` SAHIFA_JS bilan bir qoida
TEKSHIR_JS = r"""(a) => {
  const vw = innerWidth; const CS = e => getComputedStyle(e); const R = e => e.getBoundingClientRect();
  const vis = e => { const r = R(e); const s = CS(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05; };
  const nom = e => { let s = e.tagName.toLowerCase() + (e.id ? '#' + e.id : '');
    if (typeof e.className === 'string' && e.className.trim()) s += '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.');
    const t = ((e.tagName === 'SELECT' ? '' : (e.innerText || e.value || e.getAttribute('aria-label') || e.getAttribute('placeholder') || '')) + '').trim().replace(/\s+/g, ' ').slice(0, 42);
    return t ? s + ' «' + t + '»' : s; };
  const rr = r => [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)];
  const QOLDIR = '.sidebar, .erp-sidebar, #sidebar, .mobile-nav, .bottom-nav, [role=dialog], .modal-overlay, .toast';
  const ILDIZ = a.root ? document.querySelector(a.root) : document.body;
  if (!ILDIZ || !vis(ILDIZ)) return {ildiz_yoq: a.root};
  const asosiy = [...(a.root ? [ILDIZ] : []), ...ILDIZ.querySelectorAll('*')].filter(e => !(e instanceof SVGElement)
      && !['STYLE', 'SCRIPT', 'OPTION', 'TEMPLATE', 'BR'].includes(e.tagName) && !e.closest(QOLDIR) && vis(e));
  const SCR = /(auto|scroll|overlay)/;
  const xs = asosiy.filter(e => SCR.test(CS(e).overflowX) && e.scrollWidth > e.clientWidth + 1 && e !== document.documentElement && e !== document.body
      && !(a.ruxsat && e.matches(a.ruxsat)));
  const BOS = 'button, a[href], input:not([type=hidden]), select, textarea, [role=button]';
  const xsur = xs.map(e => { const er = R(e); const cl = er.left + e.clientLeft, cr = cl + e.clientWidth;
    const bos = [...e.querySelectorAll(BOS)].filter(vis);
    const yashirin = bos.filter(b => { const r = R(b); return Math.max(0, Math.min(r.right, cr, vw) - Math.max(r.left, cl, 0)) / Math.max(1, r.width) < 0.6; });
    return {el: nom(e).slice(0, 80), cw: e.clientWidth, sw: e.scrollWidth, bos: bos.length, yashirin: yashirin.length, yashirin_m: yashirin.slice(0, 3).map(b => nom(b).slice(0, 50))}; });
  const INLINE = e => { const d = CS(e).display; return d === 'inline' || d === 'contents'; };
  const matnBlok = e => { if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON', 'IMG', 'CANVAS', 'IFRAME'].includes(e.tagName)) return false;
    if (INLINE(e) || CS(e).display === 'none') return false;
    return ![...e.children].filter(c => !(c instanceof SVGElement) && CS(c).display !== 'none').some(c => !INLINE(c) && c.tagName !== 'BR'); };
  const satrlar = e => { const rg = document.createRange(); rg.selectNodeContents(e);
    const tops = [...rg.getClientRects()].filter(x => x.width > 0.5 && x.height > 0.5).map(x => Math.round(x.top)).sort((p, q) => p - q);
    let n = 0, oxir = -1e9; for (const t of tops) { if (t - oxir > 6) { n++; oxir = t; } } return n; };
  const tor = asosiy.filter(e => matnBlok(e) && (e.innerText || '').trim().length >= 24 && R(e).width < 120 && satrlar(e) >= 4)
    .map(e => ({el: nom(e).slice(0, 70), w: Math.round(R(e).width), satr: satrlar(e)}));
  const kliplash = (e, ml, mr) => { let l = Math.max(ml, 0), g = Math.min(mr, vw);
    for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const s = CS(p);
      if (s.overflowX !== 'visible') { const pr = R(p); l = Math.max(l, pr.left + p.clientLeft); g = Math.min(g, pr.left + p.clientLeft + p.clientWidth); } }
    return Math.max(0, g - l) / Math.max(1, mr - ml); };
  const kesilgan = asosiy.filter(e => e.matches(BOS) && !xs.some(p => p.contains(e))).map(e => { const r = R(e); return {e, ul: kliplash(e, r.left, r.right)}; })
    .filter(x => x.ul < 0.9).map(x => ({el: nom(x.e).slice(0, 60), ul: Math.round(x.ul * 100) / 100, rect: rr(R(x.e))}));
  const kesikMatn = asosiy.filter(e => matnBlok(e) && (e.innerText || '').trim().length >= 2 && !xs.some(p => p.contains(e)) && CS(e).overflowX === 'visible').map(e => {
      const rg = document.createRange(); rg.selectNodeContents(e); const qs = [...rg.getClientRects()].filter(x => x.width > 0.5);
      if (!qs.length) return null; return {e, ul: kliplash(e, Math.min(...qs.map(x => x.left)), Math.max(...qs.map(x => x.right)))}; })
    .filter(x => x && x.ul < 0.95).map(x => ({el: nom(x.e).slice(0, 60), ul: Math.round(x.ul * 100) / 100, rect: rr(R(x.e))}));
  return {vw, hujjat_sw: document.documentElement.scrollWidth, xsur, tor, kesilgan, kesik_matn: kesikMatn};
}"""

SLEEP = "const uxla = ms => new Promise(r => setTimeout(r, ms));"
TANLA_KATTA = ("const tanla = async (id) => { const g = document.querySelector('.ord-item[data-order-id=\"' + id + '\"]');"
               " if (g) { const ph = g.closest('.proj-group'); if (ph && !ph.classList.contains('open')) { const h = ph.querySelector('.proj-head'); h && h.click(); await uxla(300); } g.click(); }"
               " else { await selectOrder(id); } await uxla(1500); }; await tanla(window.__I.katta);")
LOYIHA = "document.querySelector('.proj-card').click(); await uxla(1500); "
KAT = []


def holat(k, kod, url, och, root, kut=800, tekshir="XTKM", qosh=None, izoh="", ruxsat=None):
    """tekshir — qaysi o'lchovlar talab qilinadi (X / T / K / M; H — hujjat eni har doim); qosh — [(nom, JS, shart(qiymat, w, h))]"""
    KAT.append(dict(k=k, kod=kod, url=url, och=och, root=root, kut=kut, tekshir=tekshir, qosh=qosh or [], izoh=izoh, ruxsat=ruxsat))


def _kartami(v, w, h):
    return isinstance(v, dict) and (v.get("thead") == "none" and v.get("qator") == "grid") if w <= 768 else isinstance(v, dict)


holat("kpi_oylik", "K1", "/kpi", "await uxla(1500);", "#empMonthlyReport", izoh="«Hodimlar oylik hisob-kitobi»",
      qosh=[("telefonda (≤ 768 px) har hodim — karta (sarlavha yashirin, qator — to'r)",
             "() => { const t = document.querySelector('.oylik-jadval'); if (!t) return null; const q = t.querySelector('tr.oylik-qator');"
             " return {thead: getComputedStyle(t.querySelector('thead')).display, qator: q ? getComputedStyle(q).display : null, n: t.querySelectorAll('tr.oylik-qator').length}; }",
             _kartami),
            ("«+ Bonus» / «− Kamaytirish» — HAMMA hodimda ekranda to'liq (yon tomonga surmasdan)",
             "() => [...document.querySelectorAll('#empMonthlyReport button')].filter(b => b.offsetParent).map(b => { const r = b.getBoundingClientRect();"
             " return Math.round(Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0)) / r.width * 100) / 100; })",
             lambda v, w, h: isinstance(v, list) and len(v) >= 8 and min(v) >= 0.99)])
holat("kpi_avans", "K1", "/kpi", "await uxla(1500); const q = document.querySelector('#empMonthlyReport tr[onclick^=\"toggleEmpAdvanceDetail\"]'); q.click(); await uxla(1500);",
      "#empMonthlyReport", izoh="avansli hodim qatori ochilgan",
      qosh=[("avans tafsiloti ochiq va izoh ustuni ≥ 150 px (summa sig'masa keyingi qatorda)",
             "() => { const r = document.querySelector('.oylik-avans-qator'); if (!r || !r.offsetParent) return null;"
             " return [...r.querySelectorAll('.oylik-avans-band > span:first-child')].map(s => Math.round(s.getBoundingClientRect().width)); }",
             lambda v, w, h: isinstance(v, list) and len(v) >= 4 and min(v) >= 150),
            ("telefonda (≤ 768 px) avans tafsiloti — karta ostida blok (jadval qatori emas)",
             "() => { const r = document.querySelector('.oylik-avans-qator, tr[id^=\"emp-adv-row-\"]'); return r && r.offsetParent ? getComputedStyle(r).display : null; }",
             lambda v, w, h: v == "block" if w <= 768 else v in ("table-row", "block"))])
holat("kpi_ustalar", "K1", "/kpi", "await uxla(1500);", ".kpi-two", tekshir="XK", izoh="ustalar va hodimlar kartalari (tugmalar qirqilmaydi)")
holat("kpi_raqamlar", "K1", "/kpi", "await uxla(1000);", ".kpi-grid", tekshir="XK", izoh="raqam kartalari (sahifa yon tomonga toshmaydi)")
holat("taminotchilar", "K2", "/suppliers", "await uxla(800);", None, izoh="butun sahifa",
      qosh=[("qarz summasi nom / telefon bloki bilan ustma-ust tushmaydi",
             "() => [...document.querySelectorAll('.sup-row')].filter(r => r.offsetParent).map(r => { const a = r.querySelector('.sup-asosiy, div'); const q = r.children[1];"
             " const A = a.getBoundingClientRect(), Q = q.getBoundingClientRect(); return !(Q.left < A.right - 1 && Q.right > A.left + 1 && Q.top < A.bottom - 1 && Q.bottom > A.top + 1); })",
             lambda v, w, h: isinstance(v, list) and len(v) >= 2 and all(v))])
holat("qaytarishlar", "K3", "/returns", "await uxla(500);", "#retList",
      qosh=[("nom ustuni qator enining kamida yarmi",
             "() => [...document.querySelectorAll('#retList .ret-row')].filter(r => r.offsetParent).map(r => Math.round(r.querySelector('.ret-name').getBoundingClientRect().width / r.clientWidth * 100) / 100)",
             lambda v, w, h: isinstance(v, list) and len(v) >= 2 and min(v) >= 0.5)])
holat("buyurtma_detal", "K4", "/orders", TANLA_KATTA, "#od-items-container", izoh="12 detalli katta buyurtma tanlangan")
holat("savat", "K5", "/trash", "await uxla(300);", None, izoh="butun sahifa",
      qosh=[("hodim qatorida tugmalar nom bilan ustma-ust tushmaydi",
             "() => [...document.querySelectorAll('.savat-qator')].filter(r => r.offsetParent).map(r => { const A = r.children[0].getBoundingClientRect(), Q = r.children[1].getBoundingClientRect();"
             " return !(Q.left < A.right - 1 && Q.right > A.left + 1 && Q.top < A.bottom - 1 && Q.bottom > A.top + 1); })",
             lambda v, w, h: isinstance(v, list) and len(v) >= 1 and all(v))])
holat("moliya_jadval", "K6", "/finance", "await uxla(2000);", ".fin-table-wrap", izoh="tranzaksiyalar jadvali",
      qosh=[("telefonda (yotiq ham) jadval — karta (sarlavha yashirin)",
             "() => { const t = document.querySelector('.fin-table-wrap table'); return t ? getComputedStyle(t.querySelector('thead')).display : null; }",
             lambda v, w, h: v == "none")])
holat("users_jadval", "K6", "/users", "await uxla(500);", ".users-table-wrap", izoh="foydalanuvchilar jadvali",
      qosh=[("telefonda (yotiq ham) jadval — karta (sarlavha yashirin)",
             "() => { const t = document.querySelector('.users-table-wrap table'); return t ? getComputedStyle(t.querySelector('thead')).display : null; }",
             lambda v, w, h: v == "none")])
_SON = ("() => { const t = document.getElementById('tabContent').innerText; const m = t.match(/\\d[.,]\\d{5,}/g); return {xom: m || [], uzunlik: t.length}; }",
        lambda v, w, h: isinstance(v, dict) and v.get("uzunlik", 0) > 50 and not v.get("xom"))
holat("loyiha_xomashyo", "K7", "/projects", LOYIHA + "switchTab('materials', true); await uxla(1500);", "#tabContent", izoh="«Xomashyo» yorlig'i",
      qosh=[("miqdor xom kasr bilan emas («5.400000000000001» yo'q)",) + _SON])
holat("loyiha_mahsulot", "K7", "/projects", LOYIHA + "switchTab('products', true); await uxla(1500);", "#tabContent", izoh="«Mahsulotlar» yorlig'i",
      qosh=[("miqdor xom kasr bilan emas",) + _SON])
holat("loyiha_moliya", "K7", "/projects", LOYIHA + "switchTab('finance', true); await uxla(1500);", "#tabContent", izoh="«Moliya» yorlig'i",
      qosh=[("loyiha sahifasi yon tomonga toshmaydi (`.proj-page` scrollWidth ≤ clientWidth)",
             "() => { const p = document.querySelector('.proj-page'); return p ? [p.scrollWidth, p.clientWidth] : null; }",
             lambda v, w, h: isinstance(v, list) and v[0] <= v[1] + 1)])
holat("moliya_xarajat", "K8", "/finance", "await uxla(2000);", "#expDetail", izoh="«Xarajatlar tafsiloti»")
holat("rollar", "K9", "/rollar", "await uxla(1000);", "#rlRoyxat",
      qosh=[("HAMMA rol kartasi ekranda to'liq", "() => [...document.querySelectorAll('#rlRoyxat .rl-item')].map(b => { const r = b.getBoundingClientRect();"
             " return Math.round(Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0)) / r.width * 100) / 100; })",
             lambda v, w, h: isinstance(v, list) and len(v) >= 4 and min(v) >= 0.99)])
holat("ishlab_royxat", "K10", "/production", "switchProdTab('orders'); await uxla(1500);", "#prod-sahifa", izoh="«Ishlab chiqarish» ro'yxati",
      qosh=[("«Mahsulot» tanlagichi ekranda to'liq", "() => { const r = document.getElementById('po-mahsulot').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right), innerWidth]; }",
             lambda v, w, h: isinstance(v, list) and v[0] >= 0 and v[1] <= v[2])])
holat("hisobot_raqamlar", "K11", "/reports", "switchReport('finance'); await uxla(2000);", ".bi-kpi-grid",
      qosh=[("hisobot (`.bi-wrap`) yon tomonga toshmaydi", "() => { const p = document.querySelector('.bi-wrap'); return p ? [p.scrollWidth, p.clientWidth] : null; }",
             lambda v, w, h: isinstance(v, list) and v[0] <= v[1] + 1)])
holat("hisobot_grafik", "K11", "/reports", "switchReport('finance'); await uxla(2000);", ".bi-charts-grid")
holat("moliya_bugun", "K13", "/finance", "await uxla(2000);", "#heroGrid", izoh="«Bugungi holat» kartalari")
holat("qarz_mijozlar", "K14", "/debts", "switchTab('customers'); await uxla(800);", "#tab-customers", izoh="«Bizga qarzdorlar»")
holat("qarz_taminotchi", "K14", "/debts", "switchTab('suppliers'); await uxla(800);", "#tab-suppliers", izoh="«Ta'minotchilarga qarzimiz»")

FAQAT = [x.strip() for x in os.environ.get("T186_FAQAT", "").split(",") if x.strip()]

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
                pg.evaluate("(I) => { window.__I = I; }", I)
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
