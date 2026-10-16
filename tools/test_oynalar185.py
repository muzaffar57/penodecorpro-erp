#!/usr/bin/env python3
"""
test_oynalar185.py — kech147 (zip 185): OYNALAR 2-qism — TELEFON BRAUZER PANELI BILAN (ekranning ko'rinadigan qismi kichik: 375 × 548 —
iPhone SE Safari, 360 × 560 — Android Chrome, 320 × 460 — kichik telefon) va YOTIQ telefon (667 × 375); TOR MATN USTUNLARI.
HAQIQIY Chromium (Playwright, `is_mobile`, `has_touch`, `device_scale_factor=2`), HAQIQIY lokal server.

NIMA UCHUN KERAK (O'LCHANGAN — zip 184 kodi, `work/k185/olchov185.py`, `work/natija/k185/oldin/`):
  O1 «Usta qo'shish / tahrirlash» (`#masterModal` — Ustalar KPI va «Ustalar» sahifasi): 375 × 548 da 14 px, 320 × 460 da 58 px tepa / past
     kesilgan, «Saqlash» / «Bekor» 0,23 / 0 ko'rinadi — hech narsa surilmaydi; O2 «Hodim QR kodi» (`#hodimQrModal`) 320 × 460 — 29 px;
     O3 Moliya «Xarajat qo'shish / tahrirlash» (`#txModal`) 375 × 548 — 6 px, 320 × 460 — 50 px («Saqlash» 0,45). Qolgan ichki uslubli
     oynalar bugun sig'adi (zaxirasi kam) — yotiq telefonda (375 px balandlik) kesiladi: hammasiga zip 184 qoidasi (quti ekran balandligigacha,
     ichi suriladi).
  U1 (N1 — staging jonli sinovi 16.10, 320 × 640) «Avans berish» → «Shu oy jami avanslar»: izohli avansda matn ustuni 86–97 px, 8–10 qator;
  U2 sovg'a davri ustalar jadvali — usta nomi 94–104 px, 9–12 qator; U3 «Xaridlar tarixi» YAKKA xarid qatori — 88–94 px, 8–9 qator;
  U4 ta'minotchi tarixidagi TO'LOV qatori — 89 px, 6 qator; B1 «Panel kirishi» dagi «QR kod (chop etish) →» — bosish nishoni 16 px;
  U5 (yotiq 667 × 375 — kompyuterda ham, 600 px dan keng) «Loy retseptlari» tarkibidagi material nomi «…» bilan kesilgan (283 / 471 px).
O'lchov: `tools/test_oynalar184.py` dagi OLCH_JS / QUTI_JS / OCHIQ_JS (fayl BAJARILMAYDI — matni o'qiladi) + TOR_JS (matni ≥ 24 belgi, eni
< 120 px, balandligi ≥ 4 qator — so'zma-so'z bo'linadi; boshqa o'lchov buni ko'rmaydi: hech narsa toshmaydi). Baho — zip 184 testi bilan bir
qoida (P2 / P3 bo'lsa YIQILADI), ataylab qilingan istisno — `#cat-icon` (bitta emoji maydoni, 34 px).
S — statik: hamma shablondagi ichki uslubli oyna (`position:fixed;inset:0`, `display:none`) qutisida balandlik cheklovi; base.html dagi JS
yasaydigan `#xoModal` / `#kiModal` qutilari ham.
Ma'lumot — ilovaning O'Z API si orqali: `tools/test_c_telefon.py` ZANJIR_JS + `tools/test_oynalar184.py` QOSHIMCHA_JS (matni o'qiladi).
REJIM: SQLite (`PG_URL` e'tiborsiz — ko'rinish baza turiga bog'liq emas); `TENANT_FILTER=1` ham. `T185_FAQAT=kalit1,kalit2` — faqat shu oynalar
(mutatsiya yurishlari uchun; odatiy — hammasi).
Asl kodga (zip 184) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_oynalar185.py
"""
import os
import re
import io
import sys
import ast
import glob
import json
import time
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
_T = tempfile.mkdtemp(prefix="oyna185_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'oyna185.db')}"
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
section("S. Statik: ichki uslubli oynalar qutisida balandlik cheklovi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
OYNA_RE = re.compile(r"position:\s*fixed;\s*inset:\s*0")


def ichki_oynalar():
    """[(fayl, qator, id, quti_qatori)] — `display:none` li ichki uslubli oyna va undan keyingi birinchi teg qatori (izohlar o'tkaziladi)."""
    nat = []
    for f in sorted(glob.glob(os.path.join(ROOT, "templates", "*.html"))):
        q = open(f, encoding="utf-8").read().split("\n")
        for i, x in enumerate(q):
            if not (OYNA_RE.search(x) and "display:none" in x.replace(" ", "") and x.lstrip().startswith("<div")):
                continue
            j = i + 1
            while j < len(q):
                t = q[j].strip()
                if t.startswith("{#"):
                    while "#}" not in q[j]:
                        j += 1
                    j += 1
                    continue
                if not t or t.startswith("<!--"):
                    j += 1
                    continue
                break
            m = re.search(r'id="([^"]+)"', x)
            nat.append((os.path.relpath(f, ROOT), i + 1, m.group(1) if m else "?", q[j].strip() if j < len(q) else ""))
    return nat


_OY = ichki_oynalar()
_inline = [o for o in _OY if re.match(r'<div style="', o[3])]
_yoq = [(f, n, i, b[:90]) for f, n, i, b in _inline if not re.search(r"max-height\s*:", b)]
check(f"S1 ichki uslubli oynalar topildi ({len(_inline)} ta qutisi o'z uslubida; zip 185 dagi 19 ta ham — masterModal, txModal, hodimQrModal …)",
      len(_inline) >= 40 and {"masterModal", "txModal", "hodimQrModal", "cpModal", "delFpModal"} <= {o[2] for o in _inline}, [o[2] for o in _inline])
check("S2 HAR ichki uslubli oyna qutisida balandlik cheklovi (max-height) bor — telefon brauzer paneli / yotiq ekranda kesilmaydi", not _yoq, _yoq)
_B = oqi("templates/base.html")
_KI = _B[_B.index("m.id = 'kiModal';"):][:1500]
_XO = _B[_B.index("m.id = 'xoModal';"):][:1500]
check("S3 base.html JS yasaydigan «kiritishOyna» (#kiModal) va «xabarOyna» (#xoModal) qutilari ham ekran balandligigacha va suriladi",
      all("max-height:calc(100dvh - 40px)" in s and "overflow-y:auto" in s for s in (_KI, _XO)), (_KI[:300], _XO[:300]))
_K = oqi("templates/kpi.html")
check("S4 sovg'a davri ustalar jadvali — telefonda kartaga aylanadi (`sovga-jadval` klassi va ≤ 600 px qoidasi)",
      'class="sovga-jadval"' in _K and re.search(r"@media \(max-width:600px\)\{\s*\.sovga-jadval, \.sovga-jadval tbody\{display:block\}", _K) is not None)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Ma'lumot va o'lchov
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "o185_admin", "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, ADMIN, PAROL, UserRole.ADMIN, "Andijon Fasad Dekor Bosh Administratori", company_id=1)
    s.commit()
s.close()

ZANJIR_JS = _src_const("tools/test_c_telefon.py", "ZANJIR_JS")
CHART_ORINBOSAR = _src_const("tools/test_c_telefon.py", "CHART_ORINBOSAR")
QOSHIMCHA_JS = _src_const("tools/test_oynalar184.py", "QOSHIMCHA_JS")
OLCH_JS = _src_const("tools/test_oynalar184.py", "OLCH_JS")
QUTI_JS = _src_const("tools/test_oynalar184.py", "QUTI_JS")
OCHIQ_JS = _src_const("tools/test_oynalar184.py", "OCHIQ_JS")
M = _src_const("tools/test_oynalar184.py", "M")
UZUN = _src_const("tools/test_oynalar184.py", "UZUN")

# TOR MATN USTUNI: to'g'ridan-to'g'ri matni ≥ 24 belgi bo'lgan blok — eni < 120 px va balandligi ≥ 4 qator (kech147 — `work/k185/olchov185.py`
# dagi metrika bilan bir qoida)
TOR_JS = r"""(a) => {
  const R = e => e.getBoundingClientRect(); const CS = e => getComputedStyle(e);
  const vis = e => { const r = R(e); const s = CS(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05; };
  const roots = [...document.querySelectorAll(a.root)].filter(vis);
  if (!roots.length) return {ochilmadi: true};
  const root = roots[roots.length - 1];
  return [...root.querySelectorAll('*')].filter(e => { if (!vis(e)) return false; const s = CS(e);
      if (s.display === 'inline' || s.display === 'contents' || ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON', 'OPTION', 'svg', 'IMG', 'CANVAS', 'STYLE', 'SCRIPT'].includes(e.tagName)) return false;
      const t = [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim(); if (t.length < 24) return false;
      const r = R(e); const lh = parseFloat(s.lineHeight) || parseFloat(s.fontSize) * 1.3; return r.width < 120 && r.height >= 4 * lh - 1; })
    .slice(0, 8).map(e => ({el: e.tagName.toLowerCase() + ' «' + (e.innerText || '').replace(/\s+/g, ' ').slice(0, 40) + '»',
                            w: Math.round(R(e).width), h: Math.round(R(e).height)}));
}"""

SLEEP = "const uxla = ms => new Promise(r => setTimeout(r, ms));"
KAT = []


def oyna(k, url, root, och, kut=900, guruh="O", kod=None, izoh="", oldin=None, keyin=None, ustun=None, ustun_min=0, ustun_kenglik=999):
    KAT.append(dict(k=k, url=url, root=root, och=och, kut=kut, guruh=guruh, kod=kod or guruh, izoh=izoh, oldin=oldin, keyin=keyin, ustun=ustun,
                    ustun_min=ustun_min, ustun_kenglik=ustun_kenglik))


def ustun_js(sel):
    return ("() => [...document.querySelectorAll(" + json.dumps(sel) + ")].filter(e => e.offsetParent !== null).slice(0, 4).map(e => ({"
            "w: Math.round(e.getBoundingClientRect().width), h: Math.round(e.getBoundingClientRect().height), matn: (e.innerText || '').replace(/\\s+/g, ' ').slice(0, 50)}))")


# ── O: balandlik cheklovi (zip 185 o'zgartirgan HAMMA ichki uslubli oyna + base.html JS oynalari) ──
oyna("base_kiritish", "/users", "#kiModal",
     "kiritishOyna('Nega rad etasiz?', {izoh: \"Sabab hodimning panelida ko'rinadi. Hech qanday moliyaviy yozuv yaratilmaydi.\", okText: 'Rad etish'});", 400)
oyna("base_xabar_uzun", "/users", "#xoModal",
     "xabarOyna('❌ Saqlanmadi: ' + Array.from({length: 14}, (_, i) => (i + 1) + '. " + UZUN
     + " — omborda yetarli emas (kerak 1 234 567,5 kg, bor 12 345,25 kg)').join('\\n'));", 400, izoh="14 qatorli xabar")
oyna("kpi_usta_yangi", "/kpi", "#masterModal", "openMasterModal();", 500, kod="O1")
oyna("kpi_usta_tahrir", "/kpi", "#masterModal", "document.querySelector('[onclick^=\"editMaster(\"]').click();", 600, kod="O1")
oyna("ustalar_yangi", "/ustalar", "#masterModal", "openMasterModal();", 500, kod="O1")
oyna("ustalar_tahrir", "/ustalar", "#masterModal", "document.querySelector('[onclick^=\"editMaster(\"]').click();", 700, kod="O1")
oyna("kpi_ketish", "/kpi", "#empKetishModal", "const e = empItems.find(x => x.name.includes('Abdulazizov')) || empItems[0]; deleteEmployee(e.id);", 500)
oyna("kpi_bonus", "/kpi", "#arModal", SLEEP + "await loadEmpMonthlyReport(); await uxla(600); document.querySelector('[onclick*=\"editEmpBonus(\"]').click();", 600)
oyna("tm_ochirish", "/finished", "#delFpModal", "confirmDeleteFp(" + json.dumps(UZUN) + ");", 500)
oyna("ombor_chiqim", "/inventory", "#chiqimModal", "document.querySelector('.act-btn.out').click();", 600)
oyna("ombor_tuz_kirim", "/inventory", "#tuzKirimModal", "document.querySelector('.act-btn.in').click();", 600)
oyna("ombor_chegara", "/inventory", "#cpModal", "document.querySelector('[aria-label=\"Chegarani tuzatish\"]').click();", 600)
oyna("user_yangi", "/users", "#addModal", "showAddModal();", 500)
oyna("user_parol_ozim", "/users", "#parolModal", "changeMyPassword();", 700)
oyna("user_parol_boshqa", "/users", "#parolModal", "const b = [...document.querySelectorAll('[onclick^=\"changePass(\"]')].pop(); b.click();", 700)
oyna("user_qr", "/users", "#hodimQrModal", "showHodimQR();", 1000, kod="O2")
oyna("rol_yangi", "/rollar", "#rlYangiModal", "yangiRol();", 600)
oyna("rol_user", "/rollar", "#rlUserModal", "userQoshOch();", 700)
oyna("qarz_kategoriya", "/debts", "#addCategoryModal", "openAddCategoryModal();", 500)
oyna("moliya_xarajat", "/finance", "#txModal", "openTxModal();", 700, kod="O3")
oyna("moliya_tahrir", "/finance", "#txModal", "document.querySelector('[onclick=\"editTxFromRow(this)\"]').click();", 700, kod="O3")
oyna("moliya_kassa", "/finance", "#cashTxModal", "openCashTxModal(Object.keys(CASH_TX_LABELS)[0]);", 600)
oyna("taminotchi_yangi", "/suppliers", "#supplierModal", "openSupplierModal();", 500)
oyna("taminotchi_tahrir", "/suppliers", "#supplierModal", "document.querySelector('[onclick*=\"editSupplier(\"]').click();", 600)
oyna("kirim_taminotchi", "/suppliers/receive", "#newSupplierModal", "openNewSupplier();", 500)
oyna("savat_hodim_tiklash", "/trash", "#hodimTiklashModal", "document.querySelector('[onclick^=\"hodimTiklash(\"]').click();", 600)
# ── U / B: tor ustunlar va bosish nishoni ──
oyna("kpi_avans", "/kpi", "#advanceModal", "document.querySelector('.emp-tugmalar .mini-btn').click();", 1000, guruh="U",
     kod="U1", izoh="N1 — 4 ta izohli avans", ustun="#adv-history > div > span:first-child", ustun_min=150)
oyna("kpi_sovga_ochiq", "/kpi", "#giftPeriodModal", "openGiftPeriodModal();", 1200, guruh="U", kod="U2", izoh="ochiq davr (3 bosqich, hamma ustalar)",
     oldin="""async () => { const so = async (u, t) => (await fetch(u, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(t)})).status;
       return await so('/api/gift-period/open', {tiers: [{gift_name: 'Samsung Galaxy A54 smartfon (128 GB, qora)', threshold_amount: 123456789},
         {gift_name: 'Artel konditsioner 12 000 BTU (inverter)', threshold_amount: 456789012}, {gift_name: 'Chevrolet Cobalt avtomobili (2026, oq)', threshold_amount: 1234567890}], master_ids: null}); }""",
     keyin="""async () => (await fetch('/api/gift-period/close', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({force: true})})).status""",
     ustun="#giftPeriodModal tbody tr > td:first-child", ustun_min=150, ustun_kenglik=600)
oyna("ombor_xaridlar", "/inventory", "#historyModal", "openPurchaseHistory();", 1500, guruh="U", kod="U3", izoh="yakka xaridlar",
     ustun="#historyModal div[style*='padding:10px 0;border-bottom:1px solid var(--border2)'] > div:first-child", ustun_min=150)
oyna("taminotchi_tarix", "/suppliers", "#historyModal",
     "const b = [...document.querySelectorAll('.sup-tarix')]; (b.find(x => x.closest('.sup-row') && /MChJ/.test(x.closest('.sup-row').innerText)) || b[0]).click();",
     1600, guruh="U", kod="U4", izoh="to'lov qatori", ustun="#hist-payments > div > div:first-child", ustun_min=150)
oyna("retsept_tahrir", "/recipes", "#editModal", "document.querySelector('[aria-label=\"Tahrirlash\"][onclick^=\"openEditModal\"]').click();", 1000,
     guruh="U", kod="U5", izoh="tarkibda uzun material nomi")
oyna("kpi_kirish", "/kpi", "#panelAccessModal", "document.querySelector('.emp-tugmalar .btn-gold-outline').click();", 600, guruh="U",
     kod="B1", izoh="«QR kod (chop etish) →»")

FAQAT = [x.strip() for x in os.environ.get("T185_FAQAT", "").split(",") if x.strip()]
ISTISNO_TOR = {"cat-icon"}      # «Yangi doimiy majburiyat» — bitta emoji maydoni (34 px) — ataylab


def baho(o, w):
    """(daraja, [sabablar]) — `tools/test_oynalar184.py` dagi `baho` bilan bir qoida (+ ataylab qilingan `#cat-icon`)."""
    if not isinstance(o, dict) or o.get("ochilmadi") or o.get("js_xato"):
        return "OCHILMADI", [str(o)[:120]]
    p2, p3 = [], []
    k = o.get("kesilgan") or {}
    if k.get("ust", 0) > 2:
        p2.append(f"top {k['ust']} px cut off (unreachable)")
    if k.get("ost", 0) > 2:
        p2.append(f"bottom {k['ost']} px cut off (unreachable)")
    for y in o.get("yetmas") or []:
        p2.append(f"unreachable control {y['el']} visible {y['ulush']:.2f} rect {y['rect']}")
    if (o.get("hujjat_sw") or 0) > int(w):
        p2.append(f"document scrollWidth {o['hujjat_sw']} > {w}")
    for c in o.get("chiqqan") or []:
        p2.append(f"off-screen {c['el']} {c['rect']}")
    for c in o.get("qutidan") or []:
        p3.append(f"spills out of box {c['el']} {c['rect']} (box {o['box']['rect']})")
    for x in o.get("xsur") or []:
        if x.get("quti"):
            p3.append(f"box scrolls sideways {x['el']} {x['cw']}/{x['sw']}")
    for x in o.get("tor") or []:
        if x.get("id") in ISTISNO_TOR:
            continue
        (p2 if x["joy"] < 24 else p3).append(f"narrow field {x['el']} text area {x['joy']} px (field {x['w']} px) value «{x['qiymat']}»")
    for x in o.get("toshgan") or []:
        p3.append(f"text overflows its own box {x['el']} {x['cw']}/{x['sw']} rect {x['rect']}")
    if ((o.get("box") or {}).get("scrollLeft") or 0) > 0:
        p2.append(f"box opened scrolled sideways: scrollLeft {o['box']['scrollLeft']} px")
    for x in o.get("kesik") or []:
        p3.append(f"clipped text {x['el']} {x['cw']}/{x['sw']}{' (ellipsis)' if x.get('ellipsis') else ''}")
    for x in o.get("kichik") or []:
        p3.append(f"tap target {x['h']} px {x['el']}")
    for x in o.get("shrift") or []:
        p3.append(f"input font {x['fs']} px {x['el']}")
    if p2:
        return "P2", p2 + p3
    if p3:
        return "P3", p3
    return "OK", []


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
# telefon brauzer paneli bilan ko'rinadigan qism va yotiq telefon
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

        def kut_royxat(p, kod, arg=None):
            """Ro'yxat o'lchovi — og'ir yuk ostida ma'lumot kechikishi mumkin: bo'sh bo'lsa 10 s gacha qayta o'lchanadi."""
            u = js(p, kod, arg)
            for _ in range(20):
                if isinstance(u, list) and u:
                    break
                p.wait_for_timeout(500)
                u = js(p, kod, arg)
            return u

        ctx, pg = kontekst(390, 844)
        Z = pg.evaluate(ZANJIR_JS, K)
        Q = pg.evaluate(QOSHIMCHA_JS, {"I": Z.get("I") or {}, "M": M, "U": UZUN, "muddat": K["muddat"], "sana": K["sana"]})
        ctx.close()
        I = dict(Z.get("I") or {})
        I.update(Q.get("R") or {})
        check("T1 ma'lumot zanjiri (ilovaning o'z API si) — yiqilgan so'rov yo'q",
              not Z.get("yiqilgan") and not Q.get("L") and I.get("katta"), (Z.get("yiqilgan"), Q.get("L"), sorted(I)))
        for w, h in OLCHAMLAR:
            section(f"O / U. Oynalar — {w} × {h}" + (" (yotiq telefon)" if w > h else " (telefon brauzer paneli bilan)"))
            ctx, pg = kontekst(w, h)
            pg.on("pageerror", lambda ex, w=w: JS_XATO.append(f"{w}: {str(ex)[:200]}"))
            for e in KAT:
                if FAQAT and e["k"] not in FAQAT:
                    continue
                if e["oldin"]:
                    js(pg, e["oldin"])
                try:
                    pg.goto(B + e["url"], wait_until="networkidle")
                except Exception:          # noqa: BLE001
                    pass
                pg.wait_for_timeout(500)
                och = js(pg, "async () => { try { " + e["och"] + " return 'ok'; } catch (ex) { return 'XATO: ' + String(ex); } }")
                pg.wait_for_timeout(e["kut"])
                if js(pg, OCHIQ_JS, e["root"]) is not True:
                    try:
                        pg.wait_for_function(OCHIQ_JS, arg=e["root"], timeout=10000)
                    except Exception:      # noqa: BLE001
                        pass
                    pg.wait_for_timeout(600)
                q = js(pg, QUTI_JS, {"root": e["root"], "box": None})
                m = js(pg, OLCH_JS, {"root": e["root"], "box": None})
                d, sab = baho(m, str(w))
                b = (m.get("box") or {}) if isinstance(m, dict) else {}
                nom = f"{e['kod']} {e['k']} @{w}x{h} — {e['root']}"
                check(f"{nom}: OK (quti {b.get('w', '?')}×{b.get('h', '?')})" + (f" — {e['izoh']}" if e["izoh"] else ""), och == "ok" and d == "OK", (och, d, sab[:6]))
                q_ok = isinstance(q, dict) and not q.get("ochilmadi") and not q.get("js_xato")
                check(f"{nom}: quti ekranga sig'adi (tepa ≥ 0, past ≤ {h}) va mazmuni pastga toshmaydi (sig'adi yoki quti o'zi suriladi)",
                      q_ok and not q.get("toshadi") and q["quti"][0] >= 0 and q["quti"][1] <= h, q)
                if e["guruh"] == "O":
                    mh = (b.get("maxH") or "none")
                    check(f"{nom}: qutida balandlik cheklovi (max-height {mh}) va surish (overflow-y {b.get('ovY')})",
                          mh not in ("none", "") and b.get("ovY") in ("auto", "scroll"), b)
                # ro'yxatli oynada AVVAL qatorlar chizilishi kutiladi (og'ir yukda ma'lumot kechikadi), keyin tor ustun o'lchanadi
                u = kut_royxat(pg, ustun_js(e["ustun"])) if e["ustun"] else None
                tor = js(pg, TOR_JS, {"root": e["root"]})
                check(f"{nom}: tor matn ustuni yo'q (matn < 120 px ustunda 4+ qatorga bo'linmaydi)", isinstance(tor, list) and not tor, tor)
                if e["ustun"] and w <= e["ustun_kenglik"]:
                    eng = min((x.get("w", 0) for x in u), default=0) if isinstance(u, list) else 0
                    check(f"{nom}: matn ustuni ≥ {e['ustun_min']} px (eng tori {eng})", isinstance(u, list) and len(u) > 0 and eng >= e["ustun_min"], u)
                if e["k"] == "kpi_kirish":
                    qr = js(pg, "() => { const a = document.getElementById('pa-qr-havola'); if (!a || !a.offsetParent) return null;"
                                " const r = a.getBoundingClientRect(); return {h: Math.round(r.height), w: Math.round(r.width)}; }")
                    check(f"{nom}: «QR kod (chop etish) →» bosish nishoni ≥ 36 px", isinstance(qr, dict) and qr.get("h", 0) >= 36, qr)
                if e["keyin"]:
                    js(pg, e["keyin"])
            ctx.close()
        br.close()
server.should_exit = True
th.join(timeout=10)

section("Z. Sahifa xatolari")
check("Z1 oynalar ochilganda ushlanmagan JS xatosi yo'q", not JS_XATO, JS_XATO[:5])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
