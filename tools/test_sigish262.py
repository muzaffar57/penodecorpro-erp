#!/usr/bin/env python3
"""
test_sigish262.py — kech196 (zip 262): «Kirim qilish» sahifasida raqam / matn o'z katagiga SIG'ADI (hech narsa qirqilmaydi, qo'shni katakka
toshmaydi) — kompyuter, planshet, telefon kengliklarida, katta qiymatlar bilan.

NIMA UCHUN KERAK (egasi so'rovi 06.11 03:57, skrinshot: kiritish qatorida «43 960 000 so'm» summasi to'liq ko'rinmasdi — «shunaqa joylarini
o'zing ham kirib tekshirib, mainga chiqarishdan oldin to'g'rilab ber, mayda kamchiliklar qolmasin»). O'LCHOV (work/k262/olchov262.py —
19 kenglik × 2 holat, tungi ham) ASL kodda (zip 261, 10cde0a) topgan nuqsonlar:
  1) kiritish qatori summasi «43 960 000 so'm» 140 / 128 px (1920 … 1100 px jadvalda; 320 px kartada «9 812 500 000 so'm» 158 / 144);
  2) miqdor maydoni «12 345,5» (savat) va «12500» (kiritish) 78 / 64 px — oxirgi raqam ko'rinmasdi;
  3) «Omborda» katagidagi katta qoldiq («1 234 567,25 kg») material katagiga toshardi; № belgisi (34 px) ustundan (28 px) chiqardi;
  4) «Ombordan tanlash»: uzun nomli materialda «✓ ro'yxatda» belgisi nom bilan birga «…» ostida YO'QOLARDI;
  5) To'lov kartasi: 1024 … 1366 px da «Qaysi hisobdan» — «N…», «B…», «K…» (hisob nomlari o'qilmasdi);
  6) Kirimlar tarixi: 1150 … 1300 px va planshetda 6 ustun ~ 518 px ga siqilib «999 999 / so'm» ikki qatorga, nomlar 3 qatorga bo'linardi;
  7) kiritish qatorida «1 blok =» belgiga yopishgan, maydon savat qatorlaridagidan ~10 px chapda (`style.display = 'block'` flex ni bekor qilardi);
  8) telefon pastki paneli — uzun summalar bir qatorga sig'masa ikkinchi qatorga o'tmasdi.
TALAB (har biri o'lchanadi):
  S  manba: ustunlar (Omborda 80, Miqdor 84), `rcvSigdir` / `rcvSigKeyin` (apCalc, updateSummary, ResizeObserver, `input`), `.rcv-sig`
     belgilari, «✓» alohida (`ot-nom`), to'lov / tarix konteyner qoidalari, `#ap-volume-wrap` ichida `.rcv-vol`, panel `flex-wrap`
  J  HAQIQIY Chromium (412 / 375 px telefonlar ham — 375 da sarlavha segmenti JONLI sinovda topilgan): egasining holati (56 × 785 000)
     1920 / 1440 / 1100 — summa TO'LIQ, shrift kichraymagan (13 px); katta qiymatlar
     (12 345,5 × 1 234 567; 12 500 × 785 000; 1 234 567,25 kg qoldiq; uzun nom) 14 kenglikda — qirqilgan / toshgan matn va maydon YO'Q,
     gorizontal surilish yo'q; «✓ ro'yxatda» ko'rinadi (telefonda «✓»); hisob nomlari to'liq; tarix — 1180 da karta, 1440 da jadval (pul
     bir qatorda); «1 blok =» kiritish qatorida savat qatori bilan bir chiziqda; `rcvSigdir` — kichraytiradi (≥ 11 px), sig'masa izoh,
     qisqa qiymatda asliga qaytadi; JS xato yo'q
ASL kodga (zip 261) qarshi QULAMAYDI — yiqiladi.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. (PG — o'lchov faqat brauzerda, bazaga yozuv yo'q.)
ISHLATISH: python3 tools/test_sigish262.py   (ixtiyoriy `K262_RASM=<papka>` — skrinshotlar; `K262_MANBASIZ=1` — S bo'limisiz, faqat
           brauzer: mutatsiya sinovi xulqni tekshirsin, manba satrini emas — work/k262/mut262.py)
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

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

_T = tempfile.mkdtemp(prefix="k262_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k262.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)
YORLIQ = "[TF1] " if os.environ.get("TENANT_FILTER") == "1" else ""
RASM = os.environ.get("K262_RASM") or ""

OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        good = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        good = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if good:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        try:
            d = detail() if callable(detail) else detail
        except Exception as e:             # noqa: BLE001
            d = f"{type(e).__name__}: {e}"
        print(f"  ✗ {label}   {str(d)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
SR = open(os.path.join(ROOT, "templates", "supplier_receive.html"), encoding="utf-8").read()
MANBASIZ = os.environ.get("K262_MANBASIZ") == "1"
if MANBASIZ:
    _check_asl = check

    def check(label, cond, detail=""):     # noqa: F811 — S bo'limi o'tkaziladi (faqat mutatsiya sinovi uchun)
        print(f"  · {label[:60]} — o'tkazildi (K262_MANBASIZ)")


def fn(nom, src=SR):
    i = src.find("function " + nom + "(")
    if i < 0:
        return ""
    j = src.find("\nfunction ", i + 10)
    k = src.find("\nasync function ", i + 10)
    ends = [x for x in (j, k) if x > 0]
    return src[i:min(ends) if ends else len(src)]


check("S1 ustunlar: «Omborda» 80 px, «Miqdor» 84 px (narx 120, summa 140); № katagi ustunga sig'adi (o'ng chegara 0, belgi 32 px)",
      ".rcv-mat col.k-omb{width:80px}" in SR and ".rcv-mat col.k-qty{width:84px}" in SR and ".rcv-mat col.k-narx{width:120px}" in SR
      and ".rcv-mat col.k-sum{width:140px}" in SR and ".rcv-mat td.c-nr{padding-right:0}" in SR and ".rcv-mat .rcv-nr{width:32px}" in SR)
check("S2 `rcvSigdir`: ko'rinmasa o'tkazadi, kichraytiradi (eng kami RCV_SIG_MIN = 11), sig'masa izoh (o'zi qo'ygan izohni o'zi oladi)",
      "const RCV_SIG_MIN = 11;" in SR and "if (!cw) return;" in fn("rcvSigdir") and "Math.floor(asl * cw / sw * 2) / 2" in fn("rcvSigdir")
      and "el.dataset.sigIzoh = '1'" in fn("rcvSigdir") and "el.removeAttribute('title')" in fn("rcvSigdir"))
check("S3 o'lchov chaqiriladi: apCalc (kiritish qatori darhol), updateSummary va tarix statistikasi (`rcvSigKeyin`), ResizeObserver, `input`, shriftlar",
      "['ap-qty', 'ap-price', 'ap-total'].forEach(id => rcvSigdir(document.getElementById(id)))" in fn("apCalc")
      and "rcvSigKeyin()" in fn("updateSummary") and "new ResizeObserver(() => rcvSigKeyin())" in SR
      and "document.fonts.ready.then(() => rcvSigKeyin())" in SR and "e.target.classList.contains('rcv-sig')" in SR
      and "rcvSigKeyin()" in SR[SR.find("loadHistoryForSupplier.chiz = function"):SR.find("loadHistoryForSupplier.chiz = function") + 900])
check("S4 `.rcv-sig` belgilari: kiritish qatori (miqdor, narx, summa), savat (miqdor, narx, summa), «Omborda», xulosa summalari, ta'minotchi kartasi",
      all(re.search(r'<input class="rcv-q rcv-sig" type="[a-z]+" id="' + i + '"', SR) for i in ("ap-qty", "ap-price", "ap-total"))
      and "rcv-q rcv-sig rcv-q-qty" in SR and "rcv-q rcv-sig rcv-q-price" in SR and '<span class="rcv-sum rcv-sig">' in SR
      and '<span class="rcv-sig">${escapeHtml(sonKor(qoldiq, 2)' in fn("rcvOmbordaKatak")
      and all(f'<b class="rcv-sig" id="{i}">' in SR for i in ("sum-products", "sum-transport", "sum-grand", "sum-paid", "sum-debt", "sum-xarajat"))
      and all(re.search(r'class="rcv-stat-value rcv-sig"[^>]* id="' + i + '"', SR) for i in ("sup-credit", "sup-paid", "sup-debt")))
check("S5 «Ombordan tanlash»: nom — `ot-nom` («…»), «✓ ro'yxatda» — undan TASHQARIDA (qisqarmaydi); telefonda faqat «✓»",
      '<span class="ot-nom">${escapeHtml(i.item_name)}</span>${bor ? \'<span class="ot-royxatda"' in fn("ombordanChiz")
      and ".ot-nm > b > .ot-nom{min-width:0;overflow:hidden;text-overflow:ellipsis}" in SR and ".ot-royxatda{flex-shrink:0;" in SR
      and "@media(max-width:480px){.ot-royxatda .ot-r-matn{display:none}" in SR)
check("S6 to'lov kartasi — o'z kengligi bo'yicha (`rcvtolov`: < 760 — summa | muddat, hisob butun qator; < 440 — bitta ustun)",
      "#rcv-tolov-karta > .rcv-card-body{container:rcvtolov / inline-size}" in SR and "@container rcvtolov (max-width:759px)" in SR
      and "@container rcvtolov (max-width:439px)" in SR and "@media(max-width:900px){.rcv-row-tolov{grid-template-columns:1fr}}" not in SR)
check("S7 tarix — tor kartada (< 640 px) kirimlar kartalar; pul kataklari (`rcv-pul`) jadvalda bir qatorda",
      "#rcv-tarix-yigma > .rcv-card-body{container:rcvtarix / inline-size}" in SR and "@container rcvtarix (max-width:639px)" in SR
      and ".rcv-table td.rcv-pul{white-space:nowrap}" in SR and SR.count('class="rcv-pul"') == 2)
check("S8 kiritish qatori «1 blok =»: ko'rinish tashqi o'ramda (`style.display` — testlar va kod o'zgarmagan), joylashuv — ichki `.rcv-vol`",
      '<div id="ap-volume-wrap" style="display:none"><div class="rcv-vol">' in SR
      and "document.getElementById('ap-volume-wrap').style.display = (item && item.is_penoplast) ? 'block' : 'none';" in SR)
check("S9 telefon paneli — summalar sig'masa ikkinchi qatorga (`flex-wrap`)",
      ".rcv-dock-qator{display:flex;justify-content:space-between;flex-wrap:wrap;" in SR)
check("S10 (JONLI 375 px) sarlavha segmenti — ≤ 420 px da yozuv ikki qatorga o'tadi («Boshlang'ich qoldiq» tugmadan chiqmaydi)",
      "@media(max-width:420px){.rcv-seg button{white-space:normal;font-size:13px;line-height:16px;text-align:center}}" in SR)

if MANBASIZ:
    check = _check_asl                     # noqa: F811
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. Brauzer (HAQIQIY Chromium)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_q = io.StringIO()
with contextlib.redirect_stdout(_q):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Supplier, InventoryPurchase    # noqa: E402

PAROL = "Parol123!"
db = SessionLocal()
with contextlib.redirect_stdout(_q):
    auth.create_user(db, "k262_admin", PAROL, UserRole.ADMIN, "K262 Admin", company_id=1)
UZUN = "Polivinilatsetat dispersiyasi PVA-50 (oq, 50 kg qopda) — yuqori sifatli kimyoviy qo'shimcha"
MAT = [  # nomi, kategoriya, birlik, qoldiq, min, penoplast, hajm, o'rtacha narx
    ("Penoplast 14P", "Penoplast", "dona", 22, 0, True, 1.4, 785000),
    ("K262 Penoplast 15", "Penoplast", "blok", 6, 10, True, 1.4, 375000),
    ("K262 Granula", "Kimyoviy qo'shimchalar", "kg", 2400, 1000, False, 1.0, 265),
    (UZUN, "Kimyoviy qo'shimchalar", "kg", 1234567.25, 2000000, False, 1.0, 1234567),
    ("K262 Mel", "Qattiq qotishmalar", "kg", 900, 2000, False, 1.0, 350),
]
ID = {}
for nm, cat, u, st, mn, peno, vol, narx in MAT:
    i = Inventory(company_id=1, item_name=nm, category=cat, unit=u, stock_quantity=st, min_stock=mn, is_penoplast=peno,
                  volume_per_unit=vol, price_per_unit=narx)
    db.add(i)
    db.commit()
    ID[nm] = i.id
SUP = Supplier(company_id=1, name="MChJ «GRANIT KIMYO SAVDO INVEST» — Andijon viloyati, Asaka tumani bo'limi")
SUP2 = Supplier(company_id=1, name="K262 Yirik ta'minotchi")
db.add_all([SUP, SUP2])
db.commit()
SID, SID2 = SUP.id, SUP2.id
# review262 №3: juda katta statistika (124 mlrd) — kompyuterdagi 3 ustunli katakka 11 px da ham sig'maydi
db.add(InventoryPurchase(inventory_id=ID["K262 Granula"], item_name="K262 Granula", quantity=1, unit="kg", price_per_unit=124444443800,
                         total_amount=124444443800, purchased_at=datetime.datetime(2026, 10, 2, 6, 0, 0), supplier_id=SID2))
_n = datetime.datetime(2026, 10, 1, 6, 0, 0)
for k, (nm, narx) in enumerate((("Penoplast 14P", 700000), ("K262 Penoplast 15", 375000), ("K262 Granula", 265), (UZUN, 1000000),
                               ("K262 Mel", 350), ("K262 Penoplast 15", 999999), ("K262 Granula", 23000), ("Penoplast 14P", 500000))):
    db.add(InventoryPurchase(inventory_id=ID[nm], item_name=nm, quantity=1, unit="kg", price_per_unit=narx, total_amount=narx,
                             purchased_at=_n + datetime.timedelta(days=k), supplier_id=SID))
db.commit()
db.close()

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
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
B = f"http://127.0.0.1:{port}"
pw_ctx = br = None
if PW_BOR and server.started:
    pw_ctx = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*", "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception:                      # noqa: BLE001
        try:
            br = pw_ctx.chromium.launch()
        except Exception as _e2:           # noqa: BLE001
            br = None
            _pw_x = f"{type(_e2).__name__}: {_e2}"
check("J0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO = []


def kontekst(w=1440, h=900, tel=False):
    ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:300]))
    pg.goto(B + "/login")
    pg.fill("input[name=username]", "k262_admin")
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


def sahifa(pg, tema=None, sid=None):
    pg.evaluate("() => { try { Object.keys(localStorage).filter(k => k.indexOf('pdp_receive_draft') === 0).forEach(k => localStorage.removeItem(k)); } catch (e) {} }")
    pg.goto(B + f"/suppliers/receive?supplier_id={sid or SID}")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_function("() => typeof invItems !== 'undefined' && invItems.length > 0" + ("" if sid else " && oxirgiNarxlar.size > 0"), timeout=10000)
    if tema:
        pg.evaluate("t => document.documentElement.setAttribute('data-theme', t)", tema)


def tanla(pg, sel, qiymat):
    pg.evaluate("([s, v]) => { const e = document.querySelector(s); e.value = v; e.dispatchEvent(new Event('change', {bubbles: true})); }", [sel, qiymat])


def kiritish(pg, nom, miqdor, narx):
    tanla(pg, "#ap-item", str(ID[nom]))
    pg.fill("#ap-qty", miqdor)
    pg.fill("#ap-price", "")
    pg.type("#ap-price", narx)


def toldir(pg, katta):
    pg.evaluate("() => { if (typeof showAllMaterials === 'function') showAllMaterials(); }")
    for nom, q, p in (("Penoplast 14P", "56", "785000"), (UZUN, "12345.5", "1234567"), ("K262 Granula", "1250", "265.5"),
                      ("K262 Penoplast 15", "1250", "1575000")):
        kiritish(pg, nom, q, p)
        pg.evaluate("() => apAddToBasket()")
        pg.wait_for_timeout(100)
    kiritish(pg, "Penoplast 14P", "12500" if katta else "56", "785000")
    for sel, v in (("#ap-cost-transport", "12500000"), ("#ap-cost-tushirish", "1250000"), ("#ap-cost-yuklash", "950000"), ("#ap-cost-boshqa", "123456789")):
        pg.evaluate("([s, v]) => { const e = document.querySelector(s); e.value = v; formatPriceInput(e); updateSummary(); }", [sel, v])
    pg.evaluate("() => { document.querySelectorAll('details.rcv-yigma').forEach(d => d.open = true); rcvTolovTuri('qisman'); }")
    pg.evaluate("() => { const e = document.getElementById('ap-paid-now'); e.value = '1234567890'; formatPriceInput(e); updateSummary(); }")
    pg.evaluate("() => { const b = document.getElementById('sup-quickpay-och'); if (b) b.click(); const e = document.getElementById('sup-quickpay-amount');"
                " if (e) { e.value = '987654321'; formatPriceInput(e); e.dispatchEvent(new Event('input', {bubbles: true})); } }")
    pg.wait_for_timeout(300)


# Ko'rinadigan HAR element: maydon matni sig'adimi; matn o'z blokidan / katagidan chiqmaydimi (atayin «…» — alohida, izohi bilan)
TEKSHIR_JS = r"""
() => {
  const res = [];
  const yol = el => { const q = []; let e = el; for (let k = 0; e && k < 3 && e.nodeType === 1; k++, e = e.parentElement) {
      q.unshift(e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.classList && e.classList.length ? '.' + [...e.classList].join('.') : '')); }
    return q.join(' > '); };
  const kor = el => { if (!el.getClientRects().length) return false; const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none' && Number(cs.opacity) > 0.05; };
  const roots = [document.getElementById('rcvWrap'), document.getElementById('ombordanOyna')].filter(Boolean);
  const kurildi = new Set();
  for (const root of roots) {
    if (!kor(root)) continue;
    for (const el of root.querySelectorAll('*')) {
      if (kurildi.has(el)) continue; kurildi.add(el);
      if (!kor(el)) continue;
      if (el.tagName === 'INPUT' && !['checkbox', 'radio', 'date', 'hidden'].includes(el.type)) {
        if (el.scrollWidth > el.clientWidth + 1) res.push({t: 'MAYDON', yol: yol(el), matn: el.value, sw: el.scrollWidth, cw: el.clientWidth});
        continue;
      }
      if (el.tagName === 'SELECT') continue;
      const cs = getComputedStyle(el);
      if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) {
        if (!el.title && !(el.parentElement && el.parentElement.title)) res.push({t: 'IZOHSIZ_KESIM', yol: yol(el), matn: el.textContent.trim().slice(0, 60)});
        continue;
      }
      for (const n of el.childNodes) {
        if (n.nodeType !== 3 || !n.textContent.trim()) continue;
        const r = document.createRange(); r.selectNodeContents(n);
        const tr = r.getBoundingClientRect();
        if (!tr.width) continue;
        let b = el; while (b && getComputedStyle(b).display.startsWith('inline') && b.tagName !== 'BUTTON') b = b.parentElement;
        if (!b) continue;
        const br = b.getBoundingClientRect(), bs = getComputedStyle(b);
        if (tr.right > br.right - parseFloat(bs.borderRightWidth) + 1 || tr.left < br.left + parseFloat(bs.borderLeftWidth) - 1)
          res.push({t: 'TOSHGAN', yol: yol(b), matn: n.textContent.trim().slice(0, 60), tr: [Math.round(tr.left), Math.round(tr.right)], blok: [Math.round(br.left), Math.round(br.right)]});
        const td = el.closest('td, th, .rcv-stat-box, .rcv-kv, .ot-it, .rcv-ab, .rcv-ro, button, .rcv-field, .rcv-dock-qator');
        if (td && td !== b && !b.contains(td)) {
          const dr = td.getBoundingClientRect(), ds = getComputedStyle(td);
          if (tr.right > dr.right - parseFloat(ds.borderRightWidth) + 1 || tr.left < dr.left + parseFloat(ds.borderLeftWidth) - 1)
            res.push({t: 'KATAKDAN', yol: yol(el), matn: n.textContent.trim().slice(0, 60), tr: [Math.round(tr.left), Math.round(tr.right)], katak: [Math.round(dr.left), Math.round(dr.right)]});
        }
      }
    }
  }
  const p = document.getElementById('rcvWrap');
  if (p.scrollWidth > p.clientWidth || document.documentElement.scrollWidth > innerWidth) res.push({t: 'SURILISH', wrap: [p.scrollWidth, p.clientWidth], doc: [document.documentElement.scrollWidth, innerWidth]});
  return res;
}
"""


def _j_ssenariy():
    # ─── J1: egasining holati — 56 × 785 000 = 43 960 000 so'm, kiritish qatori (jadval) ───
    for w in (1920, 1440, 1100):
        ctx, pg = kontekst(w, 900)
        sahifa(pg)
        kiritish(pg, "Penoplast 14P", "56", "785000")
        pg.wait_for_timeout(150)
        _t = pg.evaluate("() => { const e = document.getElementById('ap-total'); const tr = e.closest('tr');"
                         " return [e.value, e.scrollWidth, e.clientWidth, getComputedStyle(e).fontSize, getComputedStyle(tr).display, e.title, e.style.fontSize]; }")
        check(f"J1 {w} px (egasining skrinshoti): kiritish qatori summasi «43 960 000 so'm» TO'LIQ sig'adi, shrift 13 px (kichraymagan), jadval",
              re.sub(r"[\s\u00a0\u202f]", " ", _t[0]) == "43 960 000 so'm" and _t[1] <= _t[2] + 1 and _t[3] == "13px" and _t[4] == "table-row" and not _t[5]
              and _t[6] == "", _t)   # mut262 U08: 13 px — qoidadan, `rcvSigdir` kichraytirgani emas
        if RASM and w == 1440:
            os.makedirs(RASM, exist_ok=True)
            pg.locator("#rcv-mat-jadval").screenshot(path=os.path.join(RASM, "j1_1440.png"))
        ctx.close()
    # ─── J2: katta qiymatlar — hech narsa qirqilmaydi / toshmaydi ───
    for w, h, tel in ((1920, 1000, False), (1440, 900, False), (1366, 768, False), (1180, 800, False), (1100, 800, False), (1024, 768, False),
                      (900, 800, False), (761, 900, False), (744, 900, False), (600, 900, False), (412, 915, True), (390, 844, True),
                      (375, 812, True), (320, 640, True)):
        for katta in (False, True):
            ctx, pg = kontekst(w, h, tel=tel)
            sahifa(pg, tema="dark" if (w == 1440 and katta) else None)
            toldir(pg, katta)
            _r = pg.evaluate(TEKSHIR_JS)
            pg.evaluate("() => ombordanOch()")
            pg.wait_for_timeout(250)
            _r2 = [x for x in pg.evaluate(TEKSHIR_JS) if x not in _r]
            check(f"J2 {w} px, {'katta qiymatlar' if katta else 'egasining qiymatlari'}{' (tungi)' if (w == 1440 and katta) else ''}: "
                  "qirqilgan / toshgan matn, sig'magan maydon, izohsiz «…», gorizontal surilish — YO'Q (sahifa va «Ombordan tanlash»)",
                  not _r and not _r2, (_r + _r2)[:6])
            if RASM and katta and w in (1440, 1180, 390):
                os.makedirs(RASM, exist_ok=True)
                pg.screenshot(path=os.path.join(RASM, f"j2_{w}_ombordan.png"))
            ctx.close()
    # ─── J3: «Ombordan tanlash» — ro'yxatdagi uzun nomli materialda belgi ko'rinadi ───
    for w, tel in ((1440, False), (390, True)):
        ctx, pg = kontekst(w, 900, tel=tel)
        sahifa(pg)
        pg.evaluate("() => showAllMaterials()")
        kiritish(pg, UZUN, "10", "1000000")
        pg.evaluate("() => apAddToBasket()")
        pg.wait_for_timeout(150)
        pg.evaluate("() => ombordanOch()")
        pg.click("#ot-chiplar [data-filtr='hammasi']")
        _b = pg.evaluate("""id => { const it = document.querySelector('#ot-royxat .ot-it[data-id="' + id + '"]'); const r = it.querySelector('.ot-royxatda');
            if (!r) return null; const a = r.getBoundingClientRect(), l = it.getBoundingClientRect(), n = it.querySelector('.ot-nom');
            return [Math.round(a.width), a.left >= l.left && a.right <= l.right, r.textContent, getComputedStyle(r.querySelector('.ot-r-matn')).display,
                    n.scrollWidth > n.clientWidth, Math.round(it.querySelector('.ot-nm > b').getBoundingClientRect().height)]; }""", ID[UZUN])
        if w == 1440:
            check("J3 1440 px: uzun nomli, ro'yxatdagi material — «✓ ro'yxatda» to'liq ko'rinadi (qatorda), nom «…» bilan, bir qator",
                  _b and _b[0] >= 60 and _b[1] and _b[2] == "✓ ro'yxatda" and _b[3] != "none" and _b[4] and _b[5] <= 20, _b)
        else:
            check("J3 390 px: belgi — faqat «✓» (nomga joy), ko'rinadi, nom bir qatorda",
                  _b and 10 <= _b[0] <= 30 and _b[1] and _b[3] == "none" and _b[5] <= 20, _b)
        ctx.close()
    # ─── J4: «Qaysi hisobdan» — hisob nomlari to'liq; tor kartada hisob butun qator ───
    for w in (1920, 1440, 1366, 1280, 1180, 1024, 900, 600, 390):
        ctx, pg = kontekst(w, 900, tel=(w <= 600))
        sahifa(pg)
        pg.evaluate("() => rcvTolovTuri('qisman')")
        _hT = pg.evaluate("""() => { rcvTolovTuri('toliq'); const f = document.querySelector('#rcv-tolov-karta .rcv-row-tolov > .rcv-field');
            const r = f.getBoundingClientRect(), q = f.parentElement.getBoundingClientRect(); const yon = getComputedStyle(f.parentElement).gridTemplateColumns.split(' ').length;
            const x = [Math.round(r.width), Math.round(q.width), yon, getComputedStyle(document.getElementById('ap-due-wrap')).display]; rcvTolovTuri('qisman'); return x; }""")
        check(f"J4b {w} px: «To'liq to'langan» (muddat yashirin) — summa maydoni bo'sh ustun qoldirmaydi (2 ustunda butun qator)",
              _hT[3] == "none" and (_hT[2] != 2 or abs(_hT[0] - _hT[1]) <= 1), _hT)
        _h = pg.evaluate("""() => { const sp = [...document.querySelectorAll('#ap-hisob .hisob-seg button span')];
            const f = [...document.querySelectorAll('#rcv-tolov-karta .rcv-row-tolov > .rcv-field')].map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width)]; });
            const inp = ['ap-paid-now', 'ap-due-date'].map(i => Math.round(document.getElementById(i).getBoundingClientRect().top));
            return {kesik: sp.filter(s => s.scrollWidth > s.clientWidth + 1).map(s => s.textContent), matn: sp.map(s => s.textContent), f, inp}; }""")
        check(f"J4 {w} px: «Naqd pul», «Bank», «Karta» — to'liq (qisqarmagan); summa va muddat maydonlari bir chiziqda (yonma-yon bo'lsa)",
              not _h["kesik"] and _h["matn"] == ["Naqd pul", "Bank", "Karta"]
              and (_h["f"][0][1] != _h["f"][2][1] or abs(_h["inp"][0] - _h["inp"][1]) <= 1), _h)
        ctx.close()
    # ─── J5: tarix — 1180 da kartalar, 1440 da jadval (pul bir qatorda) ───
    for w, kutish in ((1440, "table-row"), (1180, "block"), (1024, "table-row"), (900, "block")):
        ctx, pg = kontekst(w, 900)
        sahifa(pg)
        pg.evaluate("() => { document.getElementById('rcv-tarix-yigma').open = true; }")
        pg.wait_for_function("() => document.querySelectorAll('#rcv-history-body tr td.rcv-pul').length > 0", timeout=10000)
        _tr = pg.evaluate("""() => { const tr = document.querySelector('#rcv-history-body tr'); const pul = [...document.querySelectorAll('#rcv-history-body td.rcv-pul')];
            const qatorlar = pul.map(td => { const r = document.createRange(); r.selectNodeContents(td); return new Set([...r.getClientRects()].map(x => Math.round(x.top))).size; });
            const w = document.querySelector('#rcv-tarix-yigma .rcv-table-wrap'); return [getComputedStyle(tr).display, Math.max(...qatorlar), w.scrollWidth <= w.clientWidth + 1]; }""")
        check(f"J5 {w} px: kirimlar tarixi — {'jadval' if kutish == 'table-row' else 'kartalar'}; pul kataklari bir qatorda; ichki surilish yo'q",
              _tr[0] == kutish and _tr[1] == 1 and _tr[2], _tr)
        ctx.close()
    # ─── J6: kiritish qatori «1 blok =» — savat qatoridagi bilan bir chiziqda (flex) ───
    ctx, pg = kontekst(1440, 900)
    sahifa(pg)
    kiritish(pg, "Penoplast 14P", "5", "785000")
    pg.evaluate("() => apAddToBasket()")
    pg.wait_for_timeout(100)
    tanla(pg, "#ap-item", str(ID["K262 Penoplast 15"]))
    _v = pg.evaluate("""() => { const a = document.querySelector('#ap-volume-wrap .rcv-vol'), b = document.querySelector('#rcv-basket-body .rcv-vol');
        const ai = a.querySelector('input').getBoundingClientRect(), bi = b.querySelector('input').getBoundingClientRect();
        return [getComputedStyle(document.getElementById('ap-volume-wrap')).display, getComputedStyle(a).display, Math.round(ai.left), Math.round(bi.left),
                document.getElementById('ap-volume').value]; }""")
    check("J6 1440 px: «1 blok =» — kiritish qatorida flex, maydon savat qatoridagi bilan bir chiziqda (± 1 px), hajm o'zi yozilgan",
          _v[0] == "block" and _v[1] == "flex" and abs(_v[2] - _v[3]) <= 1 and _v[4] == "1,4", _v)
    # ─── J7: `rcvSigdir` — kichraytiradi, sig'masa izoh, qisqa qiymatda asliga qaytadi ───
    _s = pg.evaluate("""() => { const e = document.getElementById('ap-total'); const r = [];
        e.value = "9 999 999 999 999 999 so'm"; rcvSigdir(e); r.push([parseFloat(e.style.fontSize), e.scrollWidth > e.clientWidth + 1, e.title]);
        e.value = "1 812 500 000 so'm"; rcvSigdir(e); r.push([e.style.fontSize, e.scrollWidth <= e.clientWidth + 1, e.title, e.dataset.sigIzoh || '']);
        e.value = "56 so'm"; rcvSigdir(e); r.push([e.style.fontSize, e.title]);
        const q = document.getElementById('ap-qty'); q.value = '123456'; q.dispatchEvent(new Event('input', {bubbles: true}));
        r.push([parseFloat(q.style.fontSize) || 0, q.scrollWidth <= q.clientWidth + 1]);
        q.value = '12345678901234'; q.dispatchEvent(new Event('input', {bubbles: true}));
        r.push([parseFloat(q.style.fontSize) || 0, q.title]);
        // mut262 U15: o'z `oninput` ida xulosa yangilanmaydigan maydon («Eski qarzni to'lash» summasi) — `input` tinglovchisi bilan darhol
        document.getElementById('sup-quickpay-joy').hidden = false;   // (sinov ta'minotchisining eski qarzi yo'q — maydon qo'lda ochiladi)
        const k = document.getElementById('sup-quickpay-amount'); k.style.flex = '0 0 90px'; k.value = '123456789012'; formatPriceInput(k); k.dispatchEvent(new Event('input', {bubbles: true}));
        r.push([parseFloat(k.style.fontSize) || 0, !!k.title]);
        return r; }""")
    check("J7 `rcvSigdir`: juda uzun — 11 px va to'liq qiymat izohda; 10 xonali — kichraygan va sig'adi (izohsiz); qisqa — asl shrift; "
          "miqdor yozilganda (`input`) — darhol",
          _s[0][0] == 11 and _s[0][1] and _s[0][2] == "9 999 999 999 999 999 so'm"
          and (_s[1][0] == "" or float(_s[1][0][:-2]) >= 11) and _s[1][1] and _s[1][2] == "" and _s[1][3] == ""
          and _s[2] == ["", ""] and _s[3][1] and _s[4] == [11, "12345678901234"] and 11 <= _s[5][0] < 13 and _s[5][1], _s)
    ctx.close()
    # ─── J9: kenglik o'zgarsa (telefon kartasi → kompyuter jadvali) — qayta o'lchanadi (ResizeObserver) ───
    ctx, pg = kontekst(390, 844)
    sahifa(pg)
    kiritish(pg, "Penoplast 14P", "12500", "785000")
    pg.wait_for_timeout(200)
    _a = pg.evaluate("() => { const e = document.getElementById('ap-total'); return [getComputedStyle(e.closest('tr')).display, getComputedStyle(e).fontSize]; }")
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.wait_for_timeout(400)
    _b = pg.evaluate("() => { const e = document.getElementById('ap-total'); return [getComputedStyle(e.closest('tr')).display, getComputedStyle(e).fontSize,"
                     " e.scrollWidth <= e.clientWidth + 1, parseFloat(getComputedStyle(e).fontSize) >= 11]; }")
    check("J9 390 → 1440 px (oyna kengaytirildi): kiritish summasi «9 812 500 000 so'm» kartadan jadvalga o'tgach qayta o'lchanadi — sig'adi",
          _a[0] == "grid" and _b[0] == "table-row" and _b[2] and _b[3], (_a, _b))
    ctx.close()
    # ─── J10: «Hisob-kitob» yorliqlari bir qatorda (uzun summa — o'zi keyingi qatorga) ───
    for w in (1920, 1440):
        ctx, pg = kontekst(w, 900)
        sahifa(pg)
        toldir(pg, True)
        _k = pg.evaluate("""() => [...document.querySelectorAll('#rcv-hisob-karta .rcv-kv')].filter(e => e.getClientRects().length).map(e => {
            const s = e.querySelector(':scope > span'); const r = document.createRange(); r.selectNodeContents(s);
            return [s.textContent.trim(), new Set([...r.getClientRects()].map(x => Math.round(x.top))).size]; })""")
        check(f"J10 {w} px: «Hisob-kitob» yorliqlari («Umumiy summa», «Qarzga qoladi» …) — bittadan qator, katta summalarda ham",
              len(_k) >= 6 and all(n == 1 for _, n in _k), _k)
        ctx.close()
    # ─── J11 (review262 №1): kiritish qatorida material tanlanganda «Omborda» katta qoldig'i darhol o'lchanadi (savatga qo'shmasdan) ───
    for w in (1440, 1100):
        ctx, pg = kontekst(w, 900)
        sahifa(pg)
        pg.evaluate("() => showAllMaterials()")
        tanla(pg, "#ap-item", str(ID[UZUN]))
        _o = pg.evaluate("""() => { const sp = document.querySelector('#ap-omborda .rcv-sig'), td = document.getElementById('ap-omborda');
            const r = document.createRange(); r.selectNodeContents(sp); const a = r.getBoundingClientRect(), b = td.getBoundingClientRect();
            return [sp.textContent, Math.round(a.left - b.left), Math.round(b.right - a.right), sp.scrollWidth <= sp.clientWidth + 1]; }""")
        check(f"J11 {w} px: kiritish qatori «Omborda» — «1 234 567,25 kg» katakdan chiqmaydi (tanlangan zahoti)",
              _o[1] >= 0 and _o[2] >= 0 and _o[3], _o)
        ctx.close()
    # ─── J12 (review262 №2, №3): juda katta statistika — katakdan chiqmaydi; ta'minotchi bekor qilinsa «—» asl shriftda, eski izohsiz ───
    ctx, pg = kontekst(1440, 900)
    sahifa(pg, sid=SID2)
    pg.wait_for_function("() => /124/.test(document.getElementById('sup-credit').textContent)", timeout=10000)
    pg.wait_for_timeout(200)
    _st = pg.evaluate("""() => ['sup-credit', 'sup-paid', 'sup-debt'].map(id => { const e = document.getElementById(id), box = e.closest('.rcv-stat-box');
        const r = document.createRange(); r.selectNodeContents(e); const a = r.getBoundingClientRect(), b = box.getBoundingClientRect();
        return [e.textContent, a.left >= b.left - 0.5 && a.right <= b.right + 0.5, e.style.fontSize, e.title]; })""")
    check("J12 1440 px: «Jami xarid» / «Eski qarz» 124 444 443 800 so'm — 3 ustunli katakdan chiqmaydi (11 px, sig'masa katak ichida bo'linadi), izohda to'liq",
          all(x[1] for x in _st) and _st[0][2] == "11px" and "124" in _st[0][3], _st)
    tanla(pg, "#r-supplier", "")
    pg.wait_for_timeout(300)
    _st2 = pg.evaluate("() => ['sup-credit', 'sup-paid', 'sup-debt'].map(id => { const e = document.getElementById(id); return [e.textContent, e.style.fontSize, e.title, e.className]; })")
    check("J12b ta'minotchi bekor qilinsa: «—», shrift asliga qaytgan, oldingi summaning izohi va bo'linish belgisi yo'q",
          all(x[0] == "—" and x[1] == "" and x[2] == "" and "rcv-sig-sinmaydi" not in x[3] for x in _st2), _st2)
    ctx.close()
    # ─── J13 (mut262 U20 / U21 / U22): ODDIY qiymatlarda hech narsa kichraytirilmaydi (ustun kengliklari yetarli), № belgisi ustunida ───
    for w, h, tel in ((1440, 900, False), (1100, 800, False), (390, 844, True), (320, 640, True)):
        ctx, pg = kontekst(w, h, tel=tel)
        sahifa(pg)
        pg.evaluate("() => showAllMaterials()")
        for nom, q, p in (("Penoplast 14P", "56", "785000"), ("K262 Granula", "1250", "265.5"), ("K262 Penoplast 15", "12", "375000")):
            kiritish(pg, nom, q, p)
            pg.evaluate("() => apAddToBasket()")
            pg.wait_for_timeout(100)
        kiritish(pg, "Penoplast 14P", "56" if w > 400 else "12500", "785000")
        pg.wait_for_timeout(300)
        _o = pg.evaluate("""() => { const kich = [...document.querySelectorAll('#rcv-mat-jadval .rcv-sig')].filter(e => e.getClientRects().length && e.style.fontSize)
              .map(e => [e.id || e.className, e.tagName === 'INPUT' ? e.value : e.textContent, e.style.fontSize]);
            const nr = [...document.querySelectorAll('#rcv-mat-jadval td.c-nr')].filter(td => td.getClientRects().length).map(td => {
              const a = td.querySelector('.rcv-nr').getBoundingClientRect(), b = td.getBoundingClientRect(); return a.right <= b.right + 0.5 && a.left >= b.left - 0.5; });
            return {kich, nr: nr.every(Boolean), soni: nr.length}; }""")
        check(f"J13 {w} px: oddiy qiymatlar (22 dona, 2 400 kg, 56 / 1 250 / 12, 785 000 / 265,5{'' if w > 400 else ', kartada 9 812 500 000 so\'m'}) "
              "— hech biri kichraytirilmagan; № belgisi o'z katagida",
              not _o["kich"] and _o["nr"] and _o["soni"] >= 4, _o)
        ctx.close()
    check("J8 JS xatosi yo'q", not JS_XATO, JS_XATO[:5])


if br:
    try:
        _j_ssenariy()
    except Exception as _e:              # noqa: BLE001 — asl (zip 261) kodda yangi elementlar yo'q: yiqiladi, qulamaydi
        check("J! ssenariy oxirigacha bordi", False, f"{type(_e).__name__}: {str(_e)[:400]}")
    finally:
        try:
            br.close()
            pw_ctx.stop()
        except Exception:                # noqa: BLE001
            pass

print(f"\n{YORLIQ}NATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGAN:\n  " + "\n  ".join(FAILED))
sys.exit(1 if FAIL else 0)
