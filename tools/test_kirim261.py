#!/usr/bin/env python3
"""
test_kirim261.py — kech195 (zip 261): «Kirim qilish» oynasi — egasining varianti + «Ombordan tanlash» + 2-variant (alohida «Omborda»
ustuni, narx o'zgarishi belgisi «↑ x%»).

NIMA UCHUN KERAK (egasi so'rovi 06.11 00:38: «Kirim qilish oynasini optimallashtirish — o'z varianti (rasm) + omborda bor xomashyoni kirim
qilish tugmasi yo'q — kuchli g'oya qil»; QARORLARI: 00:44 — egasining varianti + «Ombordan tanlash» («juda zo'r»); 00:57 — qator ostidagi
qoldiq / narx yozuvi chalg'itadi → 2-variant: alohida «Omborda» ustuni (kam — qizil, «↓ kam»), narx oxirgi xariddan farq qilsa «↑ 2,3%»
(qimmat — sariq, arzon — yashil «↓»), bosilsa / sichqoncha — oxirgi narx va sana; farq yo'q — belgi yo'q).
ASL (zip 260, 4233321): «Material qo'shish» formasi + alohida «Materiallar ro'yxati» jadvali (qatorni o'zgartirib bo'lmaydi), «boshlang'ich
ombor» — belgi katagi, «Hozir to'langan summa» + «To'liq to'lash» tugmasi, omborda qancha borligi va oxirgi narx ko'rinmasdi, bir nechta
materialni birdan qo'shib bo'lmasdi; `/purchased-items` da oxirgi narx yo'q edi.
TALAB (har biri o'lchanadi):
  S  manba: segment ↔ yashirin `#ap-opening-stock`, «Omborda» ustuni, `rcvTrend`, `apQatorTahrir`, «Ombordan tanlash» (oyna yopish
     belgili), chala qator `submitReceive` da to'xtaydi, To'liq / Qisman / Qarzga, telefon paneli, eski ID lar saqlangan
  A  `get_supplier_purchased_items`: `oxirgi_narx` / `oxirgi_sana` — shu ta'minotchidan OXIRGI xarid (boshlang'ich qoldiq hisobga
     olinmaydi; teng vaqtda — katta id; boshqa ta'minotchi xaridi — yo'q), boshqa korxona — bo'sh ro'yxat (API ham)
  J  HAQIQIY Chromium (1440, 390, 320, tungi): segment; «Omborda» va «kam»; narx belgisi (+ / − / yo'q, bosilsa matn); joyida tahrir
     (jami, xulosa); «Ombordan tanlash» (filtr sonlari, qidiruv, ro'yxatdagilar o'chiq, ko'p tanlov → chala qatorlar, narx oxirgi
     xariddan); chala qator → «Kirimni tasdiqlash» to'xtaydi; miqdor yozilgach saqlanadi — bazada qatorlar / summa / to'lov / qarz;
     «To'liq» (to'lov = jami, muddat yo'q), «Qarzga» (to'lov 0); boshlang'ich rejim (qarz 0, to'lov 0, xarajat yozilmaydi); qoralama
     chala qator bilan tiklanadi; telefonda kartalar va yopishgan panel; gorizontal surilish yo'q; JS xato yo'q
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://…` (pul summalari bazada). Asl kodga (zip 260) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_kirim261.py   (ixtiyoriy `K261_RASM=<papka>` — skrinshotlar)
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

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "kirim261_test"
_T = tempfile.mkdtemp(prefix="k261_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k261.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)
YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
RASM = os.environ.get("K261_RASM") or ""

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
CRUD = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()


def fn(nom, src=SR):
    i = src.find("function " + nom + "(")
    if i < 0:
        return ""
    j = src.find("\nfunction ", i + 10)
    k = src.find("\nasync function ", i + 10)
    ends = [x for x in (j, k) if x > 0]
    return src[i:min(ends) if ends else len(src)]


_gpi = CRUD[CRUD.find("def get_supplier_purchased_items("):CRUD.find("\ndef ", CRUD.find("def get_supplier_purchased_items(") + 10)]
check("S1 `get_supplier_purchased_items` — `oxirgi_narx` / `oxirgi_sana`: boshlang'ich qoldiqsiz, vaqt va id bo'yicha kamayish",
      "is_opening_stock.isnot(True)" in _gpi and "order_by(InventoryPurchase.purchased_at.desc(), InventoryPurchase.id.desc())" in _gpi
      and '"oxirgi_narx"' in _gpi and '"oxirgi_sana"' in _gpi)
check("S2 segment «Kirim (xarid)» | «Boshlang'ich qoldiq» — yashirin `#ap-opening-stock` ni o'rnatadi va `change` yuboradi",
      'id="rcv-seg-kirim"' in SR and 'id="rcv-seg-boshl"' in SR and '<input type="checkbox" id="ap-opening-stock" hidden' in SR
      and "cb.dispatchEvent(new Event('change'" in fn("rcvSegment") and "rcv-boshl" in fn("rcvSegmentKor"))
check("S3 jadval sarlavhasi: № | Material | Omborda | Miqdor | Birlik | 1 birlik narxi | Summa; kiritish qatori — eski ID lar bilan",
      re.search(r"<th>№</th><th>Material <span[^>]*>\*</span></th><th class=\"r\">Omborda</th><th>Miqdor <span[^>]*>\*</span></th><th>Birlik</th>"
                r"<th>1 birlik narxi <span[^>]*>\*</span></th><th class=\"r\">Summa</th>", SR) is not None
      and all(f'id="{i}"' in SR for i in ("ap-item", "ap-qty", "ap-price", "ap-total", "ap-volume", "ap-volume-wrap", "ap-newitem-form",
                                          "rcv-basket-body", "rcv-pos-count", "rcv-pos-total", "ap-paid-now", "ap-due-date", "ap-hisob",
                                          "ap-notes", "sup-credit", "sup-paid", "sup-debt", "sup-quickpay-amount", "sup-quickpay-btn",
                                          "receive-submit-btn", "sum-opening-warn", "sum-date-warn", "rcv-history-body")))
check("S4 «Omborda» katagi — qoldiq, `min_stock > 0` va kam bo'lsa qizil + «kam»",
      "const kam = min > 0 && qoldiq < min;" in fn("rcvOmbordaKatak") and "rcv-omb${kam ? ' kam' : ''}" in fn("rcvOmbordaKatak"))
check("S5 narx belgisi `rcvTrend` — tiyinda teng bo'lsa yo'q, foiz — oxirgi narxdan; bosilsa izoh (`rcvTrendBos`)",
      "if (nT === oT) return null;" in fn("rcvTrend") and "(nT - oT) / oT * 100" in fn("rcvTrend")
      and 'onclick="rcvTrendBos(this)"' in fn("rcvTrendHtml") and "showMsg(" in fn("rcvTrendBos"))
check("S6 joyida tahrir `apQatorTahrir` — qator qayta chizilmaydi (innerHTML yo'q), chala belgisi, server qoidasi `buyurtmaJami`",
      "innerHTML" not in fn("apQatorTahrir").replace("joy.innerHTML", "") and "b.chala = !(Number(b.qty) > 0 && Number(b.price) > 0);" in fn("apQatorTahrir")
      and "buyurtmaJami(b.qty, b.price).jami" in fn("apQatorTahrir"))
check("S7 takror tekshiruvi chala qatorni va o'zini o'tkazib yuboradi",
      "i !== istisno && !b.chala" in fn("apTakrorQator"))
check("S8 «Ombordan tanlash» oynasi — yopish belgili (`data-yopish`), qidiruv `data-kiritish-emas`, chiplar, «Yangi material qo'shish»",
      re.search(r'id="ombordanOyna"[^>]*position:fixed;inset:0', SR) is not None and 'class="ot-x" data-yopish' in SR
      and 'id="ot-qidiruv" data-kiritish-emas' in SR and "ombordanFiltr('" in fn("ombordanChiz")
      and "apToggleNewItem(true); ombordanYop()" in fn("ombordanChiz"))
check("S9 `ombordanQosh` — chala qator (miqdor yo'q, narx — oxirgi xariddan, penoplast hajmi materialdan)",
      "qty: null, price: ox ? ox.narx : null, total: 0" in fn("ombordanQosh") and "chala: true" in fn("ombordanQosh")
      and "item.is_penoplast && Number(item.volume_per_unit) > 0" in fn("ombordanQosh"))
_sub = SR[SR.find("async function submitReceive("):SR.find("function showMsg(")]
check("S10 `submitReceive`: chala qator — to'xtaydi («N-qatorda … miqdorni yozing»), «Qisman» da summa majburiy, «To'liq» — muddat yo'q, "
      "boshlang'ichda xarajat yuborilmaydi",
      "-qatorda (' + b.itemName + ') ' + (qtyYoq ? 'miqdorni' : 'narxni') + ' yozing" in _sub and "rcvTolov === 'qisman' && !(_tolov > 0)" in _sub
      and "payment_due_date: (isOpeningStock || rcvTolov === 'toliq') ? null : dueDate" in _sub
      and "const ec = isOpeningStock ? {transport: 0, tushirish: 0, yuklash: 0, boshqa: 0} : apGetExtraCosts();" in _sub
      and _sub.find("chala qator") < _sub.find("const payload"))
check("S11 To'liq / Qisman / Qarzga — `rcvTolovTuri`; «To'liq» da summa savat bilan birga (`updateSummary`)",
      "if (tur === 'qarz') p.value = '';" in fn("rcvTolovTuri") and "p.readOnly = tur === 'toliq';" in fn("rcvTolovTuri")
      and "rcvTolov === 'toliq' && paidEl) paidEl.value = productsTotal > 0 ? narxKorinishi(productsTotal) : ''" in fn("updateSummary"))
check("S12 qoralama: to'lov turi, hisob; tiklanganda chala belgisi qayta hisoblanadi; hisob — savatdan KEYIN tiklanadi",
      "tolovTuri: rcvTolov," in fn("saveDraft") and "chala: !(Number(b.qty) > 0 && Number(b.price) > 0)" in fn("restoreDraft")
      and fn("restoreDraft").find("apBasket = draft.basket.map(") < fn("restoreDraft").find("hisobTanla('ap-hisob', draft.hisob)"))
check("S13 telefon paneli (`.rcv-dock`) — «Umumiy · Qarz · Kirimni tasdiqlash», ≤ 700 px da yopishgan",
      'id="rcv-dock"' in SR and 'id="receive-submit-dock" onclick="submitReceive()"' in SR
      and re.search(r"@media\(max-width:700px\)\{[^@]*\.rcv-dock\{display:block;position:sticky;bottom:0", SR) is not None)
check("S14 ruxsat qoidalari: «Yangi material» tugmalari `apToggleNewItem(` bilan boshlanadi (ruxsatsizga yashirin)",
      SR.count('onclick="apToggleNewItem()"') == 1 and "onclick=\"apToggleNewItem(true); ombordanYop()\"" in SR
      and '[onclick^="apToggleNewItem("] { display: none !important; }' in SR)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API — oxirgi narx")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_q = io.StringIO()
with contextlib.redirect_stdout(_q):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, Supplier, InventoryPurchase, InventoryReceipt, SupplierPayment,   # noqa: E402
                    ExpenseTransaction)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PAROL = "Parol123!"
db = SessionLocal()
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="K261 B korxona", code="K261-B"))
    db.commit()
with contextlib.redirect_stdout(_q):
    auth.create_user(db, "k261_admin", PAROL, UserRole.ADMIN, "K261 Admin", company_id=1)
    auth.create_user(db, "k261_b", PAROL, UserRole.ADMIN, "K261 B", company_id=2)
MAT = [  # nomi, kategoriya, birlik, qoldiq, min, penoplast, hajm, o'rtacha narx
    ("K261 Penoplast 15", "Penoplast", "blok", 6, 10, True, 1.4, 375000),
    ("K261 Penoplast 25", "Penoplast", "blok", 14, 8, True, 1.2, 520000),
    ("K261 Granula", "Kimyoviy qo'shimchalar", "kg", 2400, 1000, False, 1.0, 265),
    ("K261 Akril", "Kimyoviy qo'shimchalar", "kg", 45, 100, False, 1.0, 23000),
    ("K261 Ftalat", "Kimyoviy qo'shimchalar", "litr", 120, 0, False, 1.0, 31000),
    ("K261 Mel", "Qattiq qotishmalar", "kg", 900, 2000, False, 1.0, 350),
    ("K261 Mikrokalsit", "Qattiq qotishmalar", "kg", 640, 300, False, 1.0, 880),
]
ID = {}
for nm, cat, u, st, mn, peno, vol, narx in MAT:
    i = Inventory(company_id=1, item_name=nm, category=cat, unit=u, stock_quantity=st, min_stock=mn, is_penoplast=peno,
                  volume_per_unit=vol, price_per_unit=narx)
    db.add(i)
    db.commit()
    ID[nm] = i.id
SUP = Supplier(company_id=1, name="K261 GRANIT KIMYO")
SUP2 = Supplier(company_id=1, name="K261 Boshqa ta'minotchi")
db.add_all([SUP, SUP2])
db.commit()
SID, SID2 = SUP.id, SUP2.id
_bi = Inventory(company_id=2, item_name="K261 B material", category="Boshqa", unit="kg", stock_quantity=0, min_stock=0)
_bs = Supplier(company_id=2, name="K261 B ta'minotchi")
db.add_all([_bi, _bs])
db.commit()
BSID = _bs.id
_n = datetime.datetime(2026, 10, 1, 6, 0, 0)


def xarid(nom, narx, kun, sid=SID, opening=False, soat=6):
    p = InventoryPurchase(inventory_id=ID[nom], item_name=nom, quantity=1, unit="kg", price_per_unit=narx, total_amount=narx,
                          purchased_at=_n + datetime.timedelta(days=kun, hours=soat - 6), supplier_id=sid, is_opening_stock=opening)
    db.add(p)
    db.commit()
    return p.id


# Penoplast 15: 370 000 (01.10) → 375 000 (21.10) → boshlang'ich 999 999 (25.10, hisobga olinmaydi)
xarid("K261 Penoplast 15", 370000, 0)
xarid("K261 Penoplast 15", 375000, 20)
xarid("K261 Penoplast 15", 999999, 24, opening=True)
# Akril: ikki xarid AYNAN bir vaqtda — katta id (23 000)
xarid("K261 Akril", 22000, 4)
xarid("K261 Akril", 23000, 4)
# Granula: 265; Mel: 350 (12.10); Penoplast 25: faqat boshlang'ich (oxirgi narx yo'q)
xarid("K261 Granula", 265, 20)
xarid("K261 Mel", 350, 11)
xarid("K261 Penoplast 25", 500000, 2, opening=True)
# Mikrokalsit: BOSHQA ta'minotchidan (shu ta'minotchi ro'yxatida yo'q)
xarid("K261 Mikrokalsit", 880, 11, sid=SID2)
db.close()

db = SessionLocal()
_pi = {r["id"]: r for r in crud.get_supplier_purchased_items(db, SID, company_id=1)}
db.close()
check("A1 oxirgi xarid narxi va sanasi (Toshkent kuni): Penoplast 15 — 375 000, 21.10.2026 (boshlang'ich 999 999 hisobga olinmaydi)",
      _pi.get(ID["K261 Penoplast 15"], {}).get("oxirgi_narx") == 375000 and _pi[ID["K261 Penoplast 15"]].get("oxirgi_sana") == "21.10.2026", _pi)
check("A2 bir vaqtdagi ikki xarid — katta id (Akril 23 000)", _pi.get(ID["K261 Akril"], {}).get("oxirgi_narx") == 23000, _pi.get(ID["K261 Akril"]))
check("A3 faqat boshlang'ich qoldiq — ro'yxatda bor, oxirgi narx YO'Q (Penoplast 25)",
      ID["K261 Penoplast 25"] in _pi and _pi[ID["K261 Penoplast 25"]].get("oxirgi_narx") is None
      and _pi[ID["K261 Penoplast 25"]].get("oxirgi_sana") is None, _pi.get(ID["K261 Penoplast 25"]))
check("A4 boshqa ta'minotchi xaridi — shu ta'minotchi ro'yxatida yo'q (Mikrokalsit)", ID["K261 Mikrokalsit"] not in _pi, sorted(_pi))
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
C.post("/login", data={"username": "k261_admin", "password": PAROL}, follow_redirects=False)
_r = C.get(f"/api/suppliers/{SID}/purchased-items")
_ar = {x["id"]: x for x in (_r.json() if _r.status_code == 200 else [])}
check("A5 API `/api/suppliers/{id}/purchased-items` — xuddi shu (oxirgi_narx / oxirgi_sana)",
      _r.status_code == 200 and _ar.get(ID["K261 Granula"], {}).get("oxirgi_narx") == 265
      and _ar.get(ID["K261 Mel"], {}).get("oxirgi_sana") == "12.10.2026", (_r.status_code, _r.text[:300]))
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB.post("/login", data={"username": "k261_b", "password": PAROL}, follow_redirects=False)
_rb = CB.get(f"/api/suppliers/{SID}/purchased-items")
check("A6 boshqa korxona admini A ta'minotchisi uchun — bo'sh (narx sizmaydi)", _rb.status_code in (200, 404) and (_rb.status_code == 404 or _rb.json() == []),
      (_rb.status_code, _rb.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. Brauzer (HAQIQIY Chromium)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
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
SOROV = []


def kontekst(w=1440, h=900, tel=False, tema=None):
    ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:300]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""), q.post_data)) if "/api/inventory/receipt" in q.url else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", "k261_admin")
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    if tema:
        pg.evaluate("t => { try { localStorage.setItem('theme', t); } catch (e) {} }", tema)
    return ctx, pg


def sahifa(pg, tozala=True, tema=None):
    if tozala:
        pg.evaluate("() => { try { Object.keys(localStorage).filter(k => k.indexOf('pdp_receive_draft') === 0).forEach(k => localStorage.removeItem(k)); } catch (e) {} }")
    pg.goto(B + f"/suppliers/receive?supplier_id={SID}")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_function("() => typeof invItems !== 'undefined' && invItems.length > 0 && oxirgiNarxlar.size > 0", timeout=10000)
    if tema:
        pg.evaluate("t => document.documentElement.setAttribute('data-theme', t)", tema)


def xabar(pg):
    return pg.evaluate("() => { const b = document.getElementById('rcvMsgBox'); return b && b.style.display !== 'none' ? b.textContent : ''; }")


def tanla(pg, sel, qiymat):
    # asl <select> qidiruvli tanlagich ostida yashirin — qiymat va `change` (sahifaning o'z `onchange` i ishlaydi)
    pg.evaluate("([s, v]) => { const e = document.querySelector(s); e.value = v; e.dispatchEvent(new Event('change', {bubbles: true})); }", [sel, qiymat])


def qator(pg, nom):
    return pg.locator("#rcv-basket-body tr", has=pg.locator(".rcv-matnom", has_text=nom))


def surilish(pg):
    return pg.evaluate("() => { const p = document.querySelector('.rcv-wrap'); return [p.scrollWidth, p.clientWidth, document.documentElement.scrollWidth, innerWidth]; }")


def kirim_kut(pg, oldingi, matn="Kirim saqlandi"):
    """«Kirimni tasdiqlash» bosilgandan keyin: bazada YANGI kirim paydo bo'lguncha (≤ 15 s) va xabar matni"""
    for _ in range(150):
        k = oxirgi_kirim()
        if k and k["id"] != oldingi:
            pg.wait_for_function("m => (document.getElementById('rcvMsgBox') || {}).textContent && document.getElementById('rcvMsgBox').textContent.indexOf(m) >= 0",
                                 arg=matn, timeout=5000)
            return k
        time.sleep(0.1)
    return None


def _oxid():
    k = oxirgi_kirim()
    return k["id"] if k else None


def oxirgi_kirim():
    d = SessionLocal()
    try:
        r = d.query(InventoryReceipt).order_by(InventoryReceipt.id.desc()).first()
        if not r:
            return None
        pr = d.query(InventoryPurchase).filter(InventoryPurchase.receipt_id == r.id).order_by(InventoryPurchase.id).all()
        tl = d.query(SupplierPayment).filter(SupplierPayment.notes.like(f"%Kirim to'lovi — #{r.id}%")).all()
        xr = d.query(ExpenseTransaction).filter(ExpenseTransaction.notes.like(f"%Kirim #{r.id}%")).all()
        return {"id": r.id, "qatorlar": [(p.inventory_id, float(p.quantity), float(p.price_per_unit), float(p.total_amount), bool(p.is_credit),
                                          bool(p.is_opening_stock), (float(p.volume_per_unit) if getattr(p, "volume_per_unit", None) else None))
                                         for p in pr],
                "tolov": sum(float(t.amount) for t in tl), "xarajat": sum(float(x.amount) for x in xr),
                "muddat": [p.payment_due_date for p in pr]}
    finally:
        d.close()


def _j_ssenariy():
    # ─── 1440: ko'rinish, segment, Omborda, narx belgisi ───
    ctx, pg = kontekst()
    sahifa(pg)
    pg.click("#rcv-seg-boshl")
    _s1 = pg.evaluate("() => [document.getElementById('ap-opening-stock').checked, document.getElementById('rcvWrap').classList.contains('rcv-boshl'),"
                      " getComputedStyle(document.getElementById('rcv-tolov-karta')).display, getComputedStyle(document.getElementById('rcv-xarajat-karta')).display,"
                      " document.getElementById('receive-submit-btn').textContent.trim(), getComputedStyle(document.getElementById('sum-opening-warn')).display]")
    pg.click("#rcv-seg-kirim")
    _s2 = pg.evaluate("() => [document.getElementById('ap-opening-stock').checked, getComputedStyle(document.getElementById('rcv-tolov-karta')).display,"
                      " document.getElementById('receive-submit-btn').textContent.trim()]")
    check("J1 segment ↔ yashirin belgi: «Boshlang'ich qoldiq» — belgi, to'lov va xarajat kartalari yashirin, tugma «Qoldiqni omborga kiritish»; "
          "«Kirim (xarid)» — qaytadi",
          _s1[:4] == [True, True, "none", "none"] and "Qoldiqni omborga kiritish" in _s1[4] and _s1[5] != "none"
          and _s2 == [False, "block", "✓ Kirimni tasdiqlash"], (_s1, _s2))

    # kiritish qatori: Akril (kam, min 100), narx 23 000 → belgi yo'q; 23 529 → ↑ 2,3%; 22 000 → ↓
    tanla(pg, "#ap-item", str(ID["K261 Akril"]))
    _k = pg.evaluate("() => [document.querySelector('#ap-omborda .rcv-omb').className, document.querySelector('#ap-omborda').textContent.replace(/\\s+/g, ' ').trim(),"
                     " document.getElementById('ap-unit').textContent]")
    pg.fill("#ap-price", "23000")
    _t0 = pg.evaluate("() => document.getElementById('ap-trend').innerHTML")
    pg.fill("#ap-price", "23529")
    _t1 = pg.evaluate("() => { const b = document.querySelector('#ap-trend .rcv-trend'); return b ? [b.className, b.textContent.trim(), b.title.replace(/\\u00a0/g, ' ')] : null; }")
    pg.fill("#ap-price", "22000")
    _t2 = pg.evaluate("() => { const b = document.querySelector('#ap-trend .rcv-trend'); return b ? [b.className, b.textContent.trim()] : null; }")
    check("J2 kiritish qatori: «Omborda» — 45 kg, qizil «kam»; birlik — kg (materialdan)",
          "kam" in _k[0] and "45" in _k[1] and "kam" in _k[1] and _k[2] == "kg", _k)
    check("J3 narx belgisi: teng — yo'q; 23 529 — «↑ 2,3%» (sariq, izohda oxirgi narx 23 000 va sana); 22 000 — «↓ 4,3%» (yashil)",
          _t0 == "" and _t1 and _t1[0] == "rcv-trend" and _t1[1] == "2,3%" and "23 000" in _t1[2] and "05.10.2026" in _t1[2]
          and _t2 and "dn" in _t2[0] and _t2[1] == "4,3%", (_t0, _t1, _t2))
    pg.fill("#ap-qty", "200")
    pg.click("#rcv-kiritish-body .rcv-qosh")
    pg.wait_for_timeout(150)
    _r1 = qator(pg, "K261 Akril")
    check("J4 «+» — qator ro'yxatga qo'shildi (Omborda, birlik, belgi «↓», summa 4 400 000), kiritish qatori tozalandi",
          _r1.count() == 1 and "kam" in _r1.locator(".c-omb").inner_text() and _r1.locator(".rcv-unit").inner_text() == "kg"
          and _r1.locator(".rcv-trend.dn").count() == 1 and _r1.locator(".rcv-sum").inner_text().replace("\u00a0", " ") == "4 400 000 so'm"
          and pg.input_value("#ap-qty") == "" and pg.input_value("#ap-price") == "", _r1.count() and _r1.inner_text())
    _r1.locator(".rcv-trend").click()
    check("J5 belgi bosilsa — oxirgi narx va sana xabarda", "23 000" in xabar(pg).replace("\u00a0", " ") and "05.10.2026" in xabar(pg), xabar(pg))
    # joyida tahrir
    _r1.locator(".rcv-q-qty").fill("150")
    _r1.locator(".rcv-q-price").fill("23000")
    _j = pg.evaluate("() => [apBasket[0].qty, apBasket[0].price, apBasket[0].total, document.getElementById('rcv-pos-total').textContent,"
                     " document.getElementById('sum-products').textContent, document.querySelectorAll('#rcv-basket-body .rcv-trend').length,"
                     " document.activeElement && document.activeElement.classList.contains('rcv-q-price')]")
    check("J6 joyida tahrir: 150 × 23 000 — qator / jami / xulosa 3 450 000, belgi yo'qoldi, fokus maydonda qoldi (qator qayta chizilmadi)",
          _j[:3] == [150, 23000, 3450000] and "3 450 000" in _j[3].replace("\u00a0", " ") and "3 450 000" in _j[4].replace("\u00a0", " ")
          and _j[5] == 0 and _j[6] is True, _j)

    # Ombordan tanlash
    pg.click("#rcv-ombordan-btn")
    pg.wait_for_timeout(150)
    _o = pg.evaluate("() => ({och: getComputedStyle(document.getElementById('ombordanOyna')).display,"
                     " chip: [...document.querySelectorAll('#ot-chiplar .ot-chip')].map(c => [c.dataset.filtr, c.classList.contains('on'), c.querySelector('b').textContent]),"
                     " qatorlar: [...document.querySelectorAll('#ot-royxat .ot-it')].map(e => +e.dataset.id),"
                     " dis: [...document.querySelectorAll('#ot-royxat .ot-it.dis')].map(e => +e.dataset.id),"
                     " grp: [...document.querySelectorAll('#ot-royxat .ot-grp')].map(e => e.textContent)})")
    _shu = sorted(ID[n] for n in ("K261 Penoplast 15", "K261 Penoplast 25", "K261 Akril", "K261 Granula", "K261 Mel"))
    check("J7 «Ombordan tanlash» ochildi: «Hammasi 7», «Shu ta'minotchidan 5» (tanlangan), «Kam qolganlar 3»; ro'yxat — shu ta'minotchiniki",
          _o["och"] != "none" and _o["chip"] == [["hammasi", False, "7"], ["shu", True, "5"], ["kam", False, "3"]]
          and sorted(_o["qatorlar"]) == _shu, _o)
    check("J8 ro'yxatda bor material (Akril) — «✓ ro'yxatda», o'chiq; kategoriyalar «Penoplast», «Kimyoviy…», «Mineral qo'shimchalar»",
          _o["dis"] == [ID["K261 Akril"]] and pg.locator(f"#ot-royxat .ot-it[data-id='{ID['K261 Akril']}'] input").is_disabled()
          and [g.upper() for g in _o["grp"]] == ["PENOPLAST", "KIMYOVIY QO'SHIMCHALAR", "MINERAL QO'SHIMCHALAR"], _o)
    _p15 = pg.locator(f"#ot-royxat .ot-it[data-id='{ID['K261 Penoplast 15']}']").inner_text().replace("\u00a0", " ")
    _p25 = pg.locator(f"#ot-royxat .ot-it[data-id='{ID['K261 Penoplast 25']}']").inner_text().replace("\u00a0", " ")
    check("J9 qatorda: oxirgi narx va sana (Penoplast 15 — 375 000, 21.10, kam · min 10); oxirgisiz — o'rtacha tannarx (Penoplast 25)",
          "375 000" in _p15 and "21.10" in _p15 and "kam" in _p15 and "min 10" in _p15 and "o'rtacha tannarx" in _p25 and "520 000" in _p25,
          (_p15, _p25))
    pg.click("#ot-chiplar [data-filtr='kam']")
    _kam = pg.evaluate("() => [...document.querySelectorAll('#ot-royxat .ot-it')].map(e => +e.dataset.id).sort((a,b)=>a-b)")
    pg.click("#ot-chiplar [data-filtr='hammasi']")
    pg.fill("#ot-qidiruv", "mikro")
    _qd = pg.evaluate("() => [...document.querySelectorAll('#ot-royxat .ot-it')].map(e => +e.dataset.id)")
    pg.fill("#ot-qidiruv", "")
    check("J10 «Kam qolganlar» — Penoplast 15, Akril, Mel; qidiruv «mikro» (Hammasi) — Mikrokalsit",
          _kam == sorted([ID["K261 Penoplast 15"], ID["K261 Akril"], ID["K261 Mel"]]) and _qd == [ID["K261 Mikrokalsit"]], (_kam, _qd))
    for nm in ("K261 Penoplast 15", "K261 Ftalat", "K261 Mel"):
        pg.locator(f"#ot-royxat .ot-it[data-id='{ID[nm]}'] input").check()
    _ft = pg.evaluate("() => [document.getElementById('ot-holat').textContent, document.getElementById('ot-qosh-btn').disabled, document.getElementById('ot-qosh-btn').textContent.trim()]")
    check("J11 pastki satr: «3 ta tanlandi · 1 tasi ro'yxatda bor», «Ro'yxatga qo'shish (3)»",
          "3 ta tanlandi" in _ft[0] and "1 tasi ro'yxatda bor" in _ft[0] and _ft[1] is False and _ft[2].endswith("(3)"), _ft)
    pg.click("#ot-qosh-btn")
    pg.wait_for_timeout(200)
    _b = pg.evaluate("() => apBasket.map(b => [b.itemId, b.qty, b.price, b.chala, b.volumePerUnit])")
    _ff = pg.evaluate("() => document.activeElement && document.activeElement.closest('tr') ? +document.activeElement.closest('tr').dataset.i : null")
    check("J12 qo'shildi — CHALA qatorlar: Penoplast 15 (narx 375 000, hajm 1,4), Ftalat (narx yo'q), Mel (350); fokus — birinchisining miqdori; oyna yopildi",
          _b[1:] == [[ID["K261 Penoplast 15"], None, 375000, True, 1.4], [ID["K261 Ftalat"], None, None, True, None], [ID["K261 Mel"], None, 350, True, None]]
          and _ff == 1 and pg.evaluate("() => getComputedStyle(document.getElementById('ombordanOyna')).display") == "none", (_b, _ff))
    _x = pg.evaluate("() => [document.getElementById('rcv-pos-count').textContent, document.getElementById('sum-products').textContent,"
                     " document.querySelectorAll('#rcv-basket-body tr.chala').length]")
    check("J13 chala qatorlar jamiga kirmaydi (4 pozitsiya, materiallar 3 450 000), qizil belgili",
          _x[0] == "4" and "3 450 000" in _x[1].replace("\u00a0", " ") and _x[2] == 3, _x)

    # chala qator → submit to'xtaydi
    pg.click("#ap-prod-type-toggle .rcv-cat-opt >> nth=0")
    _n0 = len(SOROV)
    pg.click("#receive-submit-btn")
    pg.wait_for_timeout(300)
    _m = xabar(pg)
    check("J14 chala qator — «Kirimni tasdiqlash» TO'XTAYDI («2-qatorda (K261 Penoplast 15) miqdorni yozing»), so'rov yuborilmadi",
          "2-qatorda (K261 Penoplast 15) miqdorni yozing" in _m and len(SOROV) == _n0
          and pg.evaluate("() => document.activeElement && document.activeElement.classList.contains('rcv-q-qty')"), _m)
    qator(pg, "K261 Penoplast 15").locator(".rcv-q-qty").fill("20")
    qator(pg, "K261 Penoplast 15").locator(".rcv-q-price").fill("380000")
    qator(pg, "K261 Ftalat").locator(".rcv-q-qty").fill("30")
    qator(pg, "K261 Mel").locator(".rcv-q-qty").fill("6500")
    pg.click("#receive-submit-btn")
    pg.wait_for_timeout(300)
    _m2 = xabar(pg)
    check("J15 narxsiz qator — «… narxni yozing»", "3-qatorda (K261 Ftalat) narxni yozing" in _m2, _m2)
    qator(pg, "K261 Ftalat").locator(".rcv-q-price").fill("31000")
    pg.fill("#ap-cost-transport", "600000")
    # «Qisman to'langan» — summasiz to'xtaydi
    pg.click("#rcv-tolov-turi [data-tur='qisman']")
    pg.click("#receive-submit-btn")
    pg.wait_for_timeout(300)
    check("J16 «Qisman to'langan» summasiz — to'xtaydi", "to'langan summani yozing" in xabar(pg) and len(SOROV) == _n0, xabar(pg))
    pg.fill("#ap-paid-now", "5000000")
    pg.fill("#ap-due-date", (datetime.date.today() + datetime.timedelta(days=14)).isoformat())
    _sum = pg.evaluate("() => ['sum-products','sum-transport','sum-grand','sum-paid','sum-debt','sum-xarajat-yorliq','dock-qarz'].map(i => document.getElementById(i).textContent.replace(/\\u00a0/g, ' '))")
    # 3 450 000 + 7 600 000 + 930 000 + 2 275 000 = 14 255 000
    check("J17 xulosa: materiallar 14 255 000, xarajat 600 000, umumiy 14 855 000, to'landi 5 000 000, qarz 9 255 000, «Xarajatlar (naqd puldan)»",
          _sum[:5] == ["14 255 000 so'm", "600 000 so'm", "14 855 000 so'm", "5 000 000 so'm", "9 255 000 so'm"] and _sum[5] == "Xarajatlar (naqd puldan)",
          _sum)
    if RASM:
        os.makedirs(RASM, exist_ok=True)
        pg.screenshot(path=os.path.join(RASM, "j_1440.png"), full_page=True)
    _old = _oxid()
    pg.click("#receive-submit-btn")
    _kr = kirim_kut(pg, _old, "Kirim saqlandi")
    try:
        import json as _json
        _yuk = _json.loads(SOROV[-1][2])
        _p15hajm = [x.get("volume_per_unit") for x in _yuk["items"] if x["inventory_id"] == ID["K261 Penoplast 15"]]
    except Exception as _e:                # noqa: BLE001
        _p15hajm = [repr(_e)]
    _q = sorted((q[0], q[1], q[2], q[3]) for q in (_kr or {}).get("qatorlar", []))
    _kut = sorted([(ID["K261 Akril"], 150.0, 23000.0, 3450000.0), (ID["K261 Penoplast 15"], 20.0, 380000.0, 7600000.0),
                   (ID["K261 Ftalat"], 30.0, 31000.0, 930000.0), (ID["K261 Mel"], 6500.0, 350.0, 2275000.0)])
    check("J18 bazada: 4 qator (miqdor / narx / summa AYNAN), to'lov 5 000 000, xarajat 600 000, qarz muddati yozilgan; so'rovda penoplast hajmi 1,4",
          _kr and _q == _kut and abs(_kr["tolov"] - 5000000) < 0.01 and abs(_kr["xarajat"] - 600000) < 0.01
          and all(m is not None for m in _kr["muddat"])
          and _p15hajm == [1.4], (_kr, _p15hajm))
    _ps = pg.evaluate("() => [apBasket.length, rcvTolov, document.getElementById('ap-paid-now').value, document.getElementById('ap-opening-stock').checked]")
    check("J19 saqlangach: savat bo'sh, to'lov turi — «Qarzga olindi» (summa bo'sh)", _ps == [0, "qarz", "", False], _ps)
    pg.fill("#ap-paid-now", "100")
    _ps2 = pg.evaluate("() => [rcvTolov, document.querySelector('#rcv-tolov-turi .rcv-ro.on').dataset.tur, getComputedStyle(document.getElementById('ap-paid-req')).display]")
    pg.click("#rcv-tolov-turi [data-tur='qarz']")
    check("J19b «Qarzga olindi» da summa yozilsa — «Qisman to'langan» ga o'tadi; «Qarzga» qayta bosilsa — summa tozalanadi",
          _ps2[:2] == ["qisman", "qisman"] and _ps2[2] != "none" and pg.input_value("#ap-paid-now") == "", _ps2)

    # «To'liq to'langan»: summa = jami, savat o'zgarsa o'zi, muddat yashirin va yuborilmaydi
    pg.click("#ap-prod-type-toggle .rcv-cat-opt >> nth=0")
    tanla(pg, "#ap-item", str(ID["K261 Granula"]))
    pg.fill("#ap-qty", "1000")
    pg.fill("#ap-price", "270")
    pg.click("#rcv-kiritish-body .rcv-qosh")
    pg.click("#rcv-tolov-turi [data-tur='toliq']")
    _t = pg.evaluate("() => [document.getElementById('ap-paid-now').value, document.getElementById('ap-paid-now').readOnly, getComputedStyle(document.getElementById('ap-due-wrap')).display]")
    qator(pg, "K261 Granula").locator(".rcv-q-qty").fill("2000")
    _t2 = pg.evaluate("() => [document.getElementById('ap-paid-now').value, document.getElementById('sum-debt').textContent.replace(/\\u00a0/g, ' ')]")
    # yashirin maydonda eski qiymat qolgan bo'lsa ham yuborilmaydi
    pg.evaluate("v => { document.getElementById('ap-due-date').value = v; }", (datetime.date.today() + datetime.timedelta(days=5)).isoformat())
    _old = _oxid()
    pg.click("#receive-submit-btn")
    _kr2 = kirim_kut(pg, _old, "Kirim saqlandi")
    check("J20 «To'liq to'langan»: summa 270 000 (o'zgarmas), muddat yashirin; miqdor 2 000 — summa 540 000, qarz 0",
          _t == ["270 000", True, "none"] and _t2 == ["540 000", "0 so'm"], (_t, _t2))
    check("J21 bazada: to'lov 540 000 (= materiallar jami), qarz muddati YO'Q (yashirin maydonda qiymat qolgan bo'lsa ham)",
          _kr2 and abs(_kr2["tolov"] - 540000) < 0.01 and all(m is None for m in _kr2["muddat"]), _kr2)

    # «Qarzga olindi»: to'lov 0
    pg.click("#ap-prod-type-toggle .rcv-cat-opt >> nth=0")
    tanla(pg, "#ap-item", str(ID["K261 Granula"]))
    pg.fill("#ap-qty", "10")
    pg.fill("#ap-price", "280")
    pg.click("#rcv-kiritish-body .rcv-qosh")
    pg.click("#rcv-tolov-turi [data-tur='toliq']")
    pg.click("#rcv-tolov-turi [data-tur='qarz']")
    _q3 = pg.evaluate("() => [document.getElementById('ap-paid-now').value, document.getElementById('ap-paid-now').readOnly, document.getElementById('sum-debt').textContent.replace(/\\u00a0/g, ' ')]")
    _old = _oxid()
    pg.click("#receive-submit-btn")
    _kr3 = kirim_kut(pg, _old, "Kirim saqlandi")
    check("J22 «Qarzga olindi»: summa bo'sh, qarz 2 800; bazada to'lov 0, qator nasiya",
          _q3 == ["", False, "2 800 so'm"] and _kr3 and _kr3["tolov"] == 0 and _kr3["qatorlar"][0][4] is True, (_q3, _kr3))

    # Boshlang'ich: qarz / to'lov 0, xarajat yozilmaydi (yozilgan bo'lsa ham)
    pg.click("#ap-prod-type-toggle .rcv-cat-opt >> nth=0")
    pg.fill("#ap-cost-transport", "50000")
    pg.click("#rcv-seg-boshl")
    tanla(pg, "#ap-item", str(ID["K261 Ftalat"]))
    pg.fill("#ap-qty", "5")
    pg.fill("#ap-price", "900")
    pg.click("#rcv-kiritish-body .rcv-qosh")
    _bo = pg.evaluate("() => [document.getElementById('sum-omborga').textContent, document.getElementById('sum-products-yorliq').textContent,"
                      " document.getElementById('sum-transport').textContent.replace(/\\u00a0/g, ' ')]")
    _old = _oxid()
    pg.click("#receive-submit-btn")
    _kr4 = kirim_kut(pg, _old, "Boshlang'ich qoldiq omborga kiritildi")
    check("J23 boshlang'ich: xulosa «Materiallar qiymati», «Omborga kiradi 1 ta material», xarajat 0",
          _bo == ["1 ta material", "Materiallar qiymati", "0 so'm"], _bo)
    check("J24 bazada: boshlang'ich qator, nasiya emas, to'lov 0, xarajat 0; keyin segment — «Kirim (xarid)»",
          _kr4 and _kr4["qatorlar"][0][5] is True and _kr4["qatorlar"][0][4] is False and _kr4["tolov"] == 0 and _kr4["xarajat"] == 0
          and pg.evaluate("() => [document.getElementById('ap-opening-stock').checked, document.getElementById('rcv-seg-kirim').classList.contains('on')]") == [False, True],
          _kr4)

    # Qoralama: chala qator bilan tiklanadi
    pg.click("#rcv-ombordan-btn")
    pg.locator(f"#ot-royxat .ot-it[data-id='{ID['K261 Akril']}'] input").check()
    pg.click("#ot-qosh-btn")
    qator(pg, "K261 Akril").locator(".rcv-q-qty").fill("7")
    pg.click("#rcv-ombordan-btn")
    pg.locator(f"#ot-royxat .ot-it[data-id='{ID['K261 Mel']}'] input").check()
    pg.click("#ot-qosh-btn")
    pg.click("#rcv-tolov-turi [data-tur='qisman']")
    pg.fill("#ap-paid-now", "1000")
    pg.wait_for_timeout(100)
    _sq = pg.evaluate("() => document.getElementById('rcv-saqlandi').textContent")
    sahifa(pg, tozala=False)
    pg.wait_for_timeout(300)
    _tk = pg.evaluate("() => [apBasket.map(b => [b.itemId, b.qty, b.price, b.chala]), rcvTolov, document.getElementById('ap-paid-now').value,"
                      " document.querySelectorAll('#rcv-basket-body tr.chala').length, document.querySelector('#rcv-basket-body tr[data-i=\"0\"] .rcv-q-qty').value]")
    check("J25 qoralama: «Qoralama avtomatik saqlandi · HH:MM»; qayta ochilganda chala qator bilan tiklandi, «Qisman» 1 000",
          re.search(r"Qoralama avtomatik saqlandi · \d\d:\d\d", _sq or "") is not None
          and _tk[0] == [[ID["K261 Akril"], 7, 23000, False], [ID["K261 Mel"], None, 350, True]] and _tk[1] == "qisman" and _tk[2] == "1 000"
          and _tk[3] == 1 and _tk[4] == "7", (_sq, _tk))
    pg.close()
    ctx.close()

    # ─── takror qator joyida tahrirda ───
    ctx, pg = kontekst()
    sahifa(pg)
    for q in ("5", "6"):
        tanla(pg, "#ap-item", str(ID["K261 Granula"]))
        pg.fill("#ap-qty", q)
        pg.fill("#ap-price", "270")
        pg.click("#rcv-kiritish-body .rcv-qosh")
    _inp = pg.locator("#rcv-basket-body tr[data-i='1'] .rcv-q-qty")
    _inp.click()
    _inp.fill("5")
    _inp.press("Tab")
    pg.wait_for_timeout(150)
    check("J26 joyida tahrir boshqa qator bilan AYNAN bir xil bo'lsa — xabar va maydon avvalgi qiymatiga (6) qaytadi",
          "AYNAN bir xil" in xabar(pg) and _inp.input_value() == "6" and pg.evaluate("() => apBasket[1].qty") == 6, (xabar(pg), _inp.input_value()))
    ctx.close()

    # ─── telefon 390 / 320 va tungi ───
    for w in (390, 320):
        ctx, pg = kontekst(w, 844, tel=True)
        sahifa(pg)
        pg.click("#rcv-ombordan-btn")
        _pl = pg.evaluate("() => { const r = document.querySelector('.ot-panel').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right), Math.round(r.top)]; }")
        for nm in ("K261 Penoplast 15", "K261 Mel"):
            pg.locator(f"#ot-royxat .ot-it[data-id='{ID[nm]}'] input").check()
        pg.click("#ot-qosh-btn")
        qator(pg, "K261 Penoplast 15").locator(".rcv-q-qty").fill("20")
        _tr = pg.evaluate("() => { const tr = document.querySelector('#rcv-basket-body tr'); return [getComputedStyle(tr).display, getComputedStyle(document.querySelector('.rcv-mat thead')).display,"
                          " getComputedStyle(document.querySelector('#rcv-basket-body .c-unit')).display, document.querySelector('#rcv-basket-body .c-qty .rcv-yorliq-ichki').textContent]; }")
        _dk = pg.evaluate("() => { const d = document.getElementById('rcv-dock'); const r = d.getBoundingClientRect(); return [getComputedStyle(d).display, getComputedStyle(d).position, Math.round(r.bottom), innerHeight,"
                          " document.getElementById('dock-umumiy').textContent.replace(/\\u00a0/g, ' ')]; }")
        _sw = surilish(pg)
        check(f"J27 telefon {w}: «Ombordan tanlash» pastdan (to'liq eni), qatorlar — KARTA (birlik — yorliqda «Miqdor (blok)»), ustun nomlari yashirin",
              _pl[0] == 0 and _pl[1] == w and _pl[2] > 0 and _tr == ["grid", "none", "none", "Miqdor (blok)"], (_pl, _tr))
        check(f"J28 telefon {w}: pastda yopishgan panel (ekran pastida, «Umumiy: 7 600 000 so'm»), gorizontal surilish yo'q",
              _dk[0] == "block" and _dk[1] == "sticky" and _dk[3] - 6 <= _dk[2] <= _dk[3] + 1 and _dk[4] == "7 600 000 so'm"
              and _sw[0] <= _sw[1] + 1 and _sw[2] <= _sw[3] + 1, (_dk, _sw))
        if RASM:
            pg.screenshot(path=os.path.join(RASM, f"j_{w}.png"))
        ctx.close()
    ctx, pg = kontekst(1440, 900, tema="dark")
    sahifa(pg, tema="dark")
    pg.click("#rcv-ombordan-btn")
    _dr = pg.evaluate("() => [getComputedStyle(document.querySelector('.ot-panel')).backgroundColor, getComputedStyle(document.querySelector('.rcv-card')).backgroundColor,"
                      " getComputedStyle(document.body).backgroundColor]")
    check("J29 tungi rejim: oyna va kartalar to'q (oq emas)", all(c not in ("rgb(255, 255, 255)",) for c in _dr[:2]), _dr)
    if RASM:
        pg.screenshot(path=os.path.join(RASM, "j_tun.png"))
    ctx.close()
    for w in (1440, 1100):
        ctx, pg = kontekst(w, 900)
        sahifa(pg)
        _sw = surilish(pg)
        _tr = pg.evaluate("() => [getComputedStyle(document.querySelector('#rcv-kiritish-body tr')).display, getComputedStyle(document.querySelector('.rcv-mat thead')).display]")
        check(f"J30 kompyuter {w}: jadval (qator — table-row, sarlavha ko'rinadi), gorizontal surilish yo'q",
              _tr == ["table-row", "table-header-group"] and _sw[0] <= _sw[1] + 1, (_tr, _sw))
        ctx.close()
    check("J31 JS xatosi yo'q", not JS_XATO, JS_XATO[:5])


if br:
    try:
        _j_ssenariy()
    except Exception as _e:              # noqa: BLE001 — asl (zip 260) kodda sahifada yangi elementlar yo'q: yiqiladi, qulamaydi
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
