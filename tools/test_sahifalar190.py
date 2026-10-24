#!/usr/bin/env python3
"""
test_sahifalar190.py — kech150 (zip 190): BRAUZER chizadigan summalar bitta son qoidasida — raqam qator oxirida bo'linmaydi (bo'linmas
bo'shliq), kasr — vergul. HAQIQIY Chromium (Playwright, `is_mobile`, `has_touch`, `device_scale_factor=2`), HAQIQIY lokal server, telefon
brauzer paneli bilan ko'rinadigan qism (375 × 548, 360 × 560, 320 × 460) va YOTIQ telefon (667 × 375).

NIMA UCHUN KERAK (egasi tanlovi 17.10 «Buyurtma summalari»; O'LCHANGAN — `work/k190/olchov190.py`, zip 189 kodi):
  P1 Buyurtmalar `formatNum` — ming ajratgich ODDIY bo'shliq (to'lovlar paneli, detallar, «Hisob-kitob», «Foyda tahlili», tahrir — 12 holatda
     bo'linmas 0 ta): 320 px da «Mijozning joriy qarzi: 246 873 | 519 so'm» (yetkazish oynasi), «📈 Standartdan ortiq: +1 229 667 | 840 so'm»
     (tahrir) — raqam IKKI qatorga bo'lindi.
  P2 `narxKorinishi` (kiritish maydoni formatlagichi — oddiy bo'shliq, NUQTALI kasr) 7 sahifada MATNDA (50 joy): kirim ro'yxati jami
     «15 432 | 093.75 so'm» (360 / 320 px), ta'minotchi xaridi savati «15 432 | 093.75» (375 / 360 / 320 px), qaytarish tafsiloti
     «1 234 567 890.5 so'm», kunlik xarajat «1 234 567.5 so'm», takliflar «jami 1 234 567 890.5». Endi `pulKor` (base.html) — AYNAN o'sha son
     (2 xonagacha, yaxlitlanmaydi; manfiy / son emas — «0»), bo'linmas bo'shliq va vergul. Kiritish maydoni QIYMATI o'zgarmaydi.
  P3 Buyurtmalar topshirish foizi «📦 1.4%» → «1,4%»; P4 kirim / xarid ro'yxatida miqdor «12.5 kg» → «12,5 kg».
O'lchov (har holat — `root` ichida, ko'rinadigan HAR matn tugunida): guruhli son (\\d{1,3}( \\d{3})+) — ajratgich turi (oddiy bo'shliq — xato,
telefon raqami hisobga olinmaydi) va Range bo'yicha satrlar soni (2+ — bo'lingan); nuqtali kasr (sana dd.mm.yyyy dan tashqari); kamida bitta
bo'linmas bo'shliqli summa ko'rinadi. J — `pulKor` / `formatNum` qiymatlari sahifaning O'Z funksiyalari bilan (eski qiymat bilan AYNAN son).
S — statik: shablonlarda. F — kiritish maydoni qiymati o'zgarmagan (to'lov summasi — oddiy bo'shliq, `parseNum` to'g'ri o'qiydi).
Ma'lumot — ilovaning O'Z API si: `tools/test_c_telefon.py` ZANJIR_JS + `tools/test_oynalar184.py` QOSHIMCHA_JS + `tools/test_sahifalar186.py`
QOSHIMCHA186_JS (fayllar BAJARILMAYDI) + bugungi kunlik xarajat; ma'lumoti bo'lmagan ko'rinish (taklif, qaytarish, kirim / xarid savati) —
sahifaning O'Z chizuvchisi namuna yozuv bilan (zip 187 / 189 usuli; serverga yozilmaydi).
REJIM: SQLite (`PG_URL` e'tiborsiz — ko'rinish baza turiga bog'liq emas); `TENANT_FILTER=1` ham. `T190_FAQAT=kalit1,kalit2` — faqat shu holatlar.
Asl kodga (zip 189) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_sahifalar190.py
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
_T = tempfile.mkdtemp(prefix="sahifa190_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'sahifa190.db')}"
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
section("S. Statik: shablonlarda")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_BASE = oqi("templates/base.html")
check("S1 base.html — `pulKor(n)`: `narxKorinishi` soni (2 xonagacha, manfiy / son emas — «0»), bo'linmas bo'shliq va vergul",
      """function pulKor(n) {
  const x = Number(n);
  const s = (isFinite(x) ? x : 0).toFixed(2).replace(/\\.?0+$/, '');
  if (s.indexOf('-') >= 0) return '0';
  const q = s.split('.');
  return q[0].replace(/\\B(?=(\\d{3})+(?!\\d))/g, '\\u00a0') + (q.length > 1 ? ',' + q[1] : '');
}""" in _BASE)
_ORD = oqi("templates/orders.html")
check("S2 Buyurtmalar `formatNum` — ming ajratgich bo'linmas bo'shliq (son o'zi o'zgarmagan: `Math.round`, bo'sh — «0»)",
      """function formatNum(num) {
  if (!num || isNaN(num)) return '0';
  return Math.round(num).toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, '\\u00a0');
}""" in _ORD and "(?!\\d))/g, ' ');\n}" not in _ORD.split("function formatNum(num)")[1][:200])
# `narxKorinishi(` — faqat kiritish maydoni QIYMATIDA (`.value =`, `value="${…}"`, `kiritishOyna` `qiymat`); matnda — `pulKor(`
# kech155 (zip 211, MOSLANDI): orders.html 16 → 19 (blok maydonlari va review211 №8 solishtiruvi), finished.html 4 → 3
_KUT = {"debts.html": (3, 15), "finance.html": (2, 1), "finished.html": (3, 2), "kunlik_xarajat.html": (0, 2), "orders.html": (19, 9),
        "supplier_receive.html": (2, 14), "suppliers.html": (1, 8)}
_SON = {}
for _f, (_nk, _pk) in _KUT.items():
    _t = oqi("templates/" + _f)
    _SON[_f] = (_t.count("narxKorinishi(") - _t.count("function narxKorinishi("), _t.count("pulKor("))
check("S3 7 sahifada `narxKorinishi(` faqat maydon qiymatida (matnda — `pulKor(`): sahifa bo'yicha soni (maydon, matn)",
      all(_SON[f] == v for f, v in _KUT.items()), {f: (_SON[f], _KUT[f]) for f in _KUT if _SON[f] != _KUT[f]})
_MAYDON = re.compile(r"(\.value\s*=\s*(\([^;]*?\?\s*)?[^;]*$|value=\"\$\{$|qiymat:\s*$|^\s*$)")
_yomon = []
for _f in _KUT:
    for _i, _q in enumerate(oqi("templates/" + _f).split("\n"), 1):
        for _m in re.finditer(r"narxKorinishi\(", _q):
            _old = _q[:_m.start()]
            if "function narxKorinishi(" in _q or "return narxMatni(" in _q:
                continue
            # kech155 (zip 211, MOSLANDI — review211 №8): ikki ko'rinishni solishtirish (maydondagi narx o'zgarmaganmi) — matnga chiqmaydi
            if "narxKorinishi(aniq) === narxKorinishi(oz)" in _q:
                continue
            if not (re.search(r"\.value\s*=", _old) or _old.endswith('value="${') or _old.rstrip().endswith("qiymat:") or not _old.strip()):
                _yomon.append(f"{_f}:{_i}: {_q.strip()[:100]}")
check("S4 qolgan `narxKorinishi(` hammasi kiritish maydoni qiymatiga yoziladi (`.value =` / `value=\"${` / `qiymat:` / kiritish oynasi argumenti)",
      not _yomon, _yomon[:6])
# kech154 (zip 203 «Buyurtmalar ko'rinishi», MOSLANDI): ro'yxat qatorida foiz — belgida mini chiziqdan keyin (📦 belgisisiz)
_FOIZ = ["</i></span>{{ dpct|son(1) }}%</span>", "textContent = foizKor(pct, 1);", "🟡 ${foizKor(pct, 1)}</span>", "Bajarilish: ${foizKor(r.delivery_percent, 1)}`",
         "boshlagan (${foizKor(Number.isFinite(foiz) ? foiz : 0, 1)})", "Topshirish: <b>${foizKor(result.delivery_percent, 1)}</b>",
         "qisman topshirilgan (${foizKor(o.delivery_percent || 0, 1)})."]
_ESKI_FOIZ = ["📦 {{ dpct }}%", "textContent = pct + '%';", "🟡 ${pct}%", "Bajarilish: ${r.delivery_percent}%", "foiz : 0}%)",
              "Topshirish: <b>${result.delivery_percent}%</b>", "(${o.delivery_percent || 0}%)"]
check("S5 Buyurtmalar topshirish foizi — `|son(1)` / `foizKor(…, 1)` (vergul), chiziq eni (`width:{{ dpct }}%`) — xom son",
      all(x in _ORD for x in _FOIZ) and not any(x in _ORD for x in _ESKI_FOIZ) and "width:{{ dpct }}%" in _ORD,
      ([x for x in _FOIZ if x not in _ORD], [x for x in _ESKI_FOIZ if x in _ORD]))
check("S6 Kirim va ta'minotchi xaridi ro'yxatida miqdor — `sonKor(b.qty, 4)` (vergul)",
      '<td data-label="Miqdor">${sonKor(b.qty, 4)} ${escapeHtml(b.unit)}</td>' in oqi("templates/supplier_receive.html")
      and "— ${sonKor(b.qty, 4)} ${escapeHtml(b.unit)} × ${pulKor(b.price)}</span>" in oqi("templates/suppliers.html"))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Ma'lumot va o'lchov
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "s190_admin", "Parol123!"
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
QOSHIMCHA186_JS = _src_const("tools/test_sahifalar186.py", "QOSHIMCHA186_JS")

# bugungi kunlik xarajat (shu foydalanuvchi — «Bugun men kiritganlar» ro'yxati), kasrli summa
KUNLIK_JS = r"""async (a) => {
  const h = await (await fetch('/kunlik-xarajat', {credentials: 'same-origin'})).text();
  const d = new DOMParser().parseFromString(h, 'text/html'); const sel = d.getElementById('kx-category');
  const cat = sel && sel.options.length ? sel.options[0].value : 'boshqa';
  const r = await fetch('/api/finance/transactions', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({date: a.sana + 'T00:00:00', category: cat, amount: 1234567.5, notes: a.M + ' kunlik xarajat (sinov)'})});
  return r.status;
}"""

# O'lchov: guruhli son — ajratgich, satrlar; nuqtali kasr; telefon raqami (`+998 …`, `tel:` havolasi) hisobga olinmaydi
SON_JS = r"""(a) => {
  const CS = e => getComputedStyle(e);
  const vis = e => { if (!e) return false; const r = e.getBoundingClientRect(); const s = CS(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const satrlar = rects => { const tops = rects.filter(r => r.width > 0.5 && r.height > 0.5).map(r => r.top).sort((x, y) => x - y);
    let n = 0, oxir = -1e9; for (const t of tops) { if (t - oxir > 4) { n++; oxir = t; } } return n; };
  const ILDIZ = a.root ? document.querySelector(a.root) : document.body;
  if (!ILDIZ) return {ildiz_yoq: a.root};
  const GURUH = /\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?/g;
  const NUQTA = /(^|[^\d.])(\d{1,3}(?:[   ]\d{3})*|\d+)\.(\d+)(?![\d.])/g;
  const tw = document.createTreeWalker(ILDIZ, NodeFilter.SHOW_TEXT);
  const sonlar = [], nuqta = [];
  let n;
  while ((n = tw.nextNode())) {
    const p = n.parentElement;
    if (!p || ['SCRIPT', 'STYLE', 'TEMPLATE', 'OPTION', 'TEXTAREA', 'NOSCRIPT'].includes(p.tagName) || !vis(p) || p.closest('a[href^="tel:"]')) continue;
    const t = n.textContent;
    let m; GURUH.lastIndex = 0;
    while ((m = GURUH.exec(t))) {
      const s = m[0];
      if (/\+\d*\s*$/.test(t.slice(Math.max(0, m.index - 6), m.index))) continue;
      const rg = document.createRange(); rg.setStart(n, m.index); rg.setEnd(n, m.index + s.length);
      const rr = [...rg.getClientRects()];
      if (!rr.some(r => r.width > 0.5)) continue;
      sonlar.push({s: s.replace(/ /g, '⍽'), oddiy: s.indexOf(' ') >= 0, nb: /[  ]/.test(s), satr: satrlar(rr),
                   k: t.slice(Math.max(0, m.index - 24), m.index + s.length + 10).replace(/\s+/g, ' ').trim()});
    }
    const u = t.replace(/\d{1,2}\.\d{1,2}\.\d{2,4}/g, ' ');
    NUQTA.lastIndex = 0;
    while ((m = NUQTA.exec(u))) nuqta.push(u.slice(Math.max(0, m.index - 24), m.index + m[0].length + 10).replace(/\s+/g, ' ').trim());
  }
  return {jami: sonlar.length, nb: sonlar.filter(x => x.nb).length, oddiy: sonlar.filter(x => x.oddiy).slice(0, 8),
          bolingan: sonlar.filter(x => x.satr > 1).slice(0, 8), nuqta: nuqta.slice(0, 8)};
}"""

SLEEP = "const uxla = ms => new Promise(r => setTimeout(r, ms));"
TANLA_KATTA = SLEEP + ("const tanla = async (id) => { const g = document.querySelector('.ord-item[data-order-id=\"' + id + '\"]');"
                       " if (g) { const ph = g.closest('.proj-group'); if (ph && !ph.classList.contains('open')) { const h = ph.querySelector('.proj-head'); h && h.click(); await uxla(300); } g.click(); }"
                       " else { await selectOrder(id); } await uxla(1800); }; await tanla(window.__I.katta);")
KAT = []


def holat(k, kod, url, och, root=None, kut=800, eng_kam=1, izoh=""):
    KAT.append(dict(k=k, kod=kod, url=url, och=och, root=root, kut=kut, eng_kam=eng_kam, izoh=izoh))


holat("b_tanlangan", "P1", "/orders", TANLA_KATTA, None, 1200, 20, "katta buyurtma — detallar, to'lovlar paneli, «Hisob-kitob»")
holat("b_yetkazish", "P1", "/orders", TANLA_KATTA + " openDeliveryModal(); await uxla(900); if (typeof fillAllRemaining === 'function') fillAllRemaining(); await uxla(300);",
      "#dlvModal", 600, 1, "yetkazish oynasi — «Mijozning joriy qarzi»")
holat("b_hisob", "P1", "/orders", TANLA_KATTA + " openSummaryModal(); await uxla(600);", "#sumModal", 600, 2, "«Hisob-kitob» oynasi")
holat("b_foyda", "P1", "/orders", TANLA_KATTA + " await loadProfit(); await uxla(600);", "#profitModal", 600, 4, "«Foyda tahlili»")
holat("b_tahrir", "P1", "/orders", TANLA_KATTA + " await editSelected(); await uxla(2000);", None, 800, 20, "katta buyurtma tahrirda — jami, chegirma, detal xulosalari")
holat("b_taklif", "P2", "/orders", SLEEP + "await takliflarOch(); await uxla(900); takliflarChiz({sonlar: {hammasi: 1, faol: 1}, filtr: 'hammasi', sahifa: 1, sahifalar: 1, jami: 1,"
      " takliflar: [{id: 990001, raqam: 'TK-0001', holat: 'yangi', mijoz: window.__M + ' Mijoz', telefon: '+998 90 111 22 33', detallar: ['Karniz 20x10'], detallar_soni: 1,"
      " amal_muddati: '2026-12-31', yaratilgan: '2026-10-16T09:30:00', yaratgan: 'admin', jami: 1234567890.5, kelishilgan: 1200000000}]}); await uxla(300);",
      "#takliflarPanel", 600, 2, "takliflar ro'yxati (namuna)")
holat("qarz_qaytarish", "P2", "/debts", SLEEP + "switchTab('refunds'); await uxla(600); let el = document.querySelector('#tab-refunds .dbt-item');"
      " if (!el) { el = document.createElement('div'); el.className = 'dbt-item'; Object.assign(el.dataset, {id: '990001', orderNumber: 'ORD-990-1', client: window.__M + ' Mijoz',"
      " phone: '—', project: 'Loyiha', agreed: '1234567890.5', paid: '1300000000', ortiqcha: '65432109.5', deleted: 'false'});"
      " (document.querySelector('#tab-refunds .dbt-list') || document.getElementById('tab-refunds')).appendChild(el); }"
      " selectRefund(el); await uxla(600);", "#refDetailCard", 600, 3, "ortiqcha to'lov — qaytarish tafsiloti")
holat("qarz_kechir", "P2", "/debts", SLEEP + "switchTab('customers'); await uxla(600); const d = document.querySelector('#tab-customers .dbt-item'); if (d) { d.click(); await uxla(1200); }"
      " const a = document.getElementById('pay-amount'); if (a) { a.value = '100 000'; a.dispatchEvent(new Event('input')); }"
      " const w = document.getElementById('pay-writeoff'); if (w) { w.checked = true; w.dispatchEvent(new Event('change')); } if (typeof payYozuv === 'function') payYozuv(); await uxla(300);",
      "#pay-writeoff-izoh", 600, 1, "qolganini kechirish izohi")
holat("kunlik", "P2", "/kunlik-xarajat", "await uxla(300);", "#kx-bugun-list", 1200, 1, "bugungi xarajat (1 234 567,5)")
holat("kirim_savat", "P2", "/suppliers/receive", SLEEP + "await uxla(800); apBasket.push({itemId: 1, itemName: window.__M + ' Penoplast 25P blok', unit: 'm³', qty: 12.5,"
      " price: 1234567.5, total: buyurtmaJami(12.5, 1234567.5).jami, isPenoplast: false, volumePerUnit: null}); renderBasket(); if (typeof updateSummary === 'function') updateSummary(); await uxla(300);",
      None, 600, 4, "kirim — ro'yxat va jami (namuna qator)")
holat("taminotchi_savat", "P2", "/suppliers", SLEEP + "document.querySelector('.sup-tarix').click(); await uxla(1500); openAddPurchase(); await uxla(400);"
      " apBasket.push({itemId: 1, itemName: window.__M + ' Akril', unit: 'kg', qty: 12.5, price: 1234567.5, total: buyurtmaJami(12.5, 1234567.5).jami});"
      " renderApBasket(); await uxla(300);", "#ap-basket", 600, 3, "ta'minotchi xaridi savati (namuna)")
holat("tayyor_yangi", "P2", "/finished", SLEEP + "openProduceModal(); await uxla(400); const f = (id, v) => { const e = document.getElementById(id); if (e) { e.value = v;"
      " e.dispatchEvent(new Event('input')); } }; f('p-h', '120'); f('p-w', '15'); f('p-l', '3.5'); f('p-m3', '1 234 567'); await uxla(300);",
      "#p-calc", 600, 1, "tayyor mahsulot qo'shish — narx hisobi")

FAQAT = [x.strip() for x in os.environ.get("T190_FAQAT", "").split(",") if x.strip()]

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

# J — sahifaning O'Z funksiyalari: `pulKor` = `narxKorinishi` soni (bo'linmas bo'shliq, vergul); `formatNum` = butun so'm, bo'linmas bo'shliq
J_JS = r"""() => {
  const Q = [0, 1, -1, -0.001, 0.5, 0.125, 1.005, 999.995, 1000, 1234.5, 15432093.75, 1234567890.5, NaN, null, undefined, '', Infinity, -5000, '1234.56'];
  const R = {pul: typeof pulKor === 'function', nk: typeof narxKorinishi === 'function', fn: typeof formatNum === 'function', farq: [], fn_farq: []};
  if (R.pul && R.nk) for (const v of Q) { const a = pulKor(v), e = narxKorinishi(v).replace(/ /g, ' ').replace('.', ','); if (a !== e) R.farq.push([String(v), a, e]); }
  if (R.fn) for (const v of [0, 7, 999, 1000, 1234567.6, -1234567, 1234527840, NaN]) {
    const e = (!v || isNaN(v)) ? '0' : Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' '); const a = formatNum(v); if (a !== e) R.fn_farq.push([String(v), a, e]); }
  R.namuna = R.pul ? [pulKor(15432093.75), pulKor(1234567890.5), pulKor(-5), pulKor(2000)] : null;
  return R;
}"""


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
        KX = pg.evaluate(KUNLIK_JS, {"M": M, "sana": K["sana"]})
        I = dict(Z.get("I") or {})
        I.update(Q.get("R") or {})
        I.update(Q2.get("R") or {})
        check("T1 ma'lumot zanjiri (ilovaning o'z API si) — yiqilgan so'rov yo'q, katta buyurtma va bugungi xarajat bor",
              not Z.get("yiqilgan") and not Q.get("L") and not Q2.get("L") and I.get("katta") and KX == 200,
              (Z.get("yiqilgan"), Q.get("L"), Q2.get("L"), KX, sorted(I)))

        section("J. `pulKor` / `formatNum` — sahifaning o'z funksiyalari")
        for _u in ("/orders", "/debts", "/suppliers/receive"):
            pg.goto(B + _u, wait_until="networkidle")
            j = js(pg, J_JS)
            check(f"J1 {_u}: `pulKor(x)` = `narxKorinishi(x)` soni (bo'linmas bo'shliq, vergul) — 19 qiymat (manfiy / son emas — «0», 2 xonagacha)",
                  isinstance(j, dict) and j.get("pul") and j.get("nk") and not j.get("farq")
                  and j.get("namuna") == ["15 432 093,75", "1 234 567 890,5", "0", "2 000"], j)
        pg.goto(B + "/orders", wait_until="networkidle")
        j = js(pg, J_JS)
        check("J2 Buyurtmalar `formatNum` — butun so'm (`Math.round`), bo'linmas bo'shliq, bo'sh / son emas — «0»",
              isinstance(j, dict) and j.get("fn") and not j.get("fn_farq"), j)

        section("F. Kiritish maydoni qiymati o'zgarmagan")
        pg.evaluate("(a) => { window.__I = a.I; window.__M = a.M; }", {"I": I, "M": M})
        f = js(pg, "async () => { " + TANLA_KATTA + " openPaymentForm(); await uxla(300); fillFullDebt(); await uxla(300);"
                   " const v = document.getElementById('pf-amount').value; const qarz = (document.getElementById('pay-debt') || {}).textContent || '';"
                   " return {v, son: parseNum(v), qarz}; }")
        check("F1 «To'liq qarz» — to'lov maydonida `narxKorinishi` ko'rinishi (oddiy bo'shliq), `parseNum` aynan qarz summasini o'qiydi; panelda — bo'linmas",
              isinstance(f, dict) and re.fullmatch(r"\d{1,3}( \d{3})*(\.\d{1,2})?", f.get("v") or "") and f.get("son") == 246873519
              and "246 873 519" in (f.get("qarz") or ""), f)
        ctx.close()

        for w, h in OLCHAMLAR:
            section(f"D. Summalar — {w} × {h}" + (" (yotiq telefon)" if w > h else " (telefon brauzer paneli bilan)"))
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
                m = js(pg, SON_JS, {"root": e["root"]})
                nom = f"{e['kod']} {e['k']} @{w}x{h}" + (f" ({e['izoh']})" if e["izoh"] else "")
                bor = och == "ok" and isinstance(m, dict) and not m.get("ildiz_yoq") and not m.get("js_xato")
                check(f"{nom}: ochildi, kamida {e['eng_kam']} ta summa bo'linmas bo'shliq bilan", bor and m["nb"] >= e["eng_kam"], (och, m))
                if not bor:
                    continue
                check(f"{nom}: oddiy bo'shliqli summa yo'q", not m["oddiy"], m["oddiy"])
                check(f"{nom}: raqam qator oxirida bo'linmaydi (bitta satrda)", not m["bolingan"], m["bolingan"])
                check(f"{nom}: nuqtali kasr yo'q (vergul)", not m["nuqta"], m["nuqta"])
            ctx.close()
        br.close()
    check("T2 sahifalarda JS xatosi yo'q", not JS_XATO, JS_XATO[:5])
server.should_exit = True
th.join(timeout=10)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
