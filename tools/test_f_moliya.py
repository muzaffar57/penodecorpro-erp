#!/usr/bin/env python3
"""
test_f_moliya.py — kech120, F BOSQICH 1-qism (MOLIYA, QARZDORLAR, XARAJAT QO'SHISH — audit G3 qolgan bandlari).

NIMA UCHUN KERAK (audit kech114; 2026-10-01 da JORIY kodda qayta tekshirildi — work/f/tekshiruv_kech120.md; O'LCHANGAN work/f/f1_probe.py):
  G3-17  Kirim hujjatining qo'shimcha xarajati (transport, tushirish …) Moliya ro'yxatidan tahrirlanar / o'chirilar edi (SQLite va PG —
         200): hujjat bilan aloqasi uziladi. Toifasi ro'yxatda yo'q xarajatni tahrirlash — xom «'category' bo'sh» xatosi.
  G3-18  Ro'yxatda jami yo'q, majburiyat toifalari xom kod bilan («ijara_4821»), kirim xarajatlari filtrda yo'q.
  G3-16  Yangi xarajat sanasi — oyning 1-kuni (filtr sanasi).
  G3-15  Kassaga qo'lda kiritilgan xato yozuvni o'chirib bo'lmasdi (API bor — sahifada tugma yo'q), saqlash tasdiqsiz, boshlang'ich balans
         ikki marta — jim qo'shilardi.
  G3-13  Moliya «Bugungi holat» — «Sof foyda» deb yozilgan, aslida yalpi (xarajatlar ayirilmagan).
  G3-20  Oy / yil o'zgarsa hisobot yangilanmasdi, PDF esa tanlangan (ekrandagi emas) oyni olardi; yil chegarasi 2030.
  G3-03  Qarz to'lovida usul tanlanmasdi — hammasi «naqd».
  G3-04  Majburiyatni tez to'lash oynasida qaysi oy va qaysi sanaga yozilishi aytilmasdi; qarzdan ko'p summa — jim.
  G3-05  Majburiyat / hodim to'lov tarixi doim JORIY oyni ko'rsatardi (avgust qarzini bossa — oktabr to'lovlari).
  G3-08  Telefonda ro'yxat ichida alohida aylantirish (ichma-ich), sahifa ochilganda qarzdor kartasiga surilib ketardi.
  G3-24 / G3-25  «Xarajat qo'shish»: nima saqlangani ko'rinmasdi, boshqa oyga yozish — ogohlantirishsiz; summa — faqat butun raqam
         (umumiy qoidadan tashqarida), bir ish — uch nom.
BO'LIMLAR: S — statik; A — API (kirim xarajati qulfi 409, egalik 404 dan oldin, majburiyat nomi, to'lov usuli); B — HAQIQIY Chromium
  (Moliya, Qarzdorlar, Xarajat qo'shish — kompyuter va telefon 390 px; Moliyachi roli — o'chirish tugmasi yo'q).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 130) qarshi QULAMAYDI — yiqiladi.
BARQARORLIK (kech123, zip 142): B9 / B10 / B13 / B14 da qat'iy kutish o'rniga SHART (`shart_kut`, `qayta_yuklanib`) — etalon yuklamasida
  server javobi kechiksa ham natija o'zgarmaydi (O'LCHANGAN: eski sinov d150 da 5 urinishdan 3 tasida, d149 da 3 tadan 1 tasida
  yiqilgan — kod emas, vaqt poygasi).
TALAB: Python `playwright` + Chromium (B bo'limi).
ISHLATISH: python3 tools/test_f_moliya.py
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
PG_BAZA = "f_moliya_test"
_T = tempfile.mkdtemp(prefix="fmol_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'f_moliya_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal, tashkent_date  # noqa: E402
from models import (UserRole, Inventory, Supplier, Project, Order, OrderType, OrderStatus, Payment,   # noqa: E402
                    ExpenseTransaction, RecurringObligation)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return r.text[:300]


BUGUN = tashkent_date()
O_YIL, O_OY = (BUGUN.year, BUGUN.month - 1) if BUGUN.month > 1 else (BUGUN.year - 1, 12)
OY_NOMI = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAIN = oqi("main.py")
FIN = oqi("templates/finance.html")
DEB = oqi("templates/debts.html")
KX = oqi("templates/kunlik_xarajat.html")
check("S1 kirim xarajati qulfi — PUT va DELETE da (egalik tekshiruvidan keyin), 409 sababi bilan; ro'yxatda — 🔒 belgi",
      MAIN.count("_kirim_xarajati_qulfi(db, tx_id, auth.company_id_of(current_user))") == 2 and "status_code=409, detail=KIRIM_XARAJATI_QULF_XABARI" in MAIN
      and "🔒 Kirim hujjati" in FIN and "const kirimdan = (t.source === 'kirim_tannarx' || t.source === 'inventory_receipt');" in FIN)
check("S2 Moliya: «Yalpi foyda» (bugun), «Xarajatlar ro'yxati», oy / yil `onchange`, yil 2030 bilan cheklanmagan, PDF — ekrandagi oy",
      '<div class="fin-hero-label">Yalpi foyda</div>' in FIN and "Xarajatlar ro'yxati</div>" in FIN and '<select id="sel-month" onchange="loadReport()">' in FIN
      and 'max="2030"' not in FIN and "korsatilganOy = {year, month}" in FIN and "Kunlik xarajat tranzaksiyalari" not in FIN)
check("S3 Qarzdorlar: to'lov usuli (`pay-method` → `payment_method`), majburiyat oynasida oy va sana, tarix — qator oyi, telefonda ichma-ich "
      "aylantirish yo'q", 'id="pay-method"' in DEB and "payment_method: usul" in DEB and "function tarixOyi(" in DEB
      and "sanasiga yoziladi" in DEB and "@media(max-width:950px){.dbt-list{max-height:none;overflow-y:visible}}" in DEB
      and "selectOrderDebt(first, !!qayta)" in DEB)
check("S4 «Xarajat qo'shish»: umumiy pul qoidasi (`formatPriceInput` / `parseNum`), saqlangan yozuv tafsiloti, boshqa oy — tasdiq",
      'oninput="formatPriceInput(this)"' in KX and "parseNum(document.getElementById('kx-amount').value)" in KX and "✓ Saqlandi:" in KX
      and "joriy oy emas" in KX and "parseInt(document.getElementById('kx-amount')" not in KX)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Ma'lumot")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, MOLIYA, PAROL = "fmol_admin", "fmol_moliya", "Parol123!"
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="FM B korxona", code="FM-B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, ADMIN, PAROL, UserRole.ADMIN, "FM Admin", company_id=1)
    auth.create_user(_db, MOLIYA, PAROL, UserRole.ACCOUNTANT, "FM Moliya", company_id=1)
    auth.create_user(_db, "fmol_b", PAROL, UserRole.ADMIN, "FM B", company_id=2)
_m1 = Inventory(company_id=1, item_name="FM Kley", unit="kg", price_per_unit=1000)
_m2 = Inventory(company_id=1, item_name="FM Qum", unit="kg", price_per_unit=500)
_sup = Supplier(company_id=1, name="FM Ta'minotchi")
_obl = RecurringObligation(company_id=1, category="ijara_fm01", label="Ijara FM", monthly_target=500000, due_day=5, icon="🏠",
                           created_at=datetime.utcnow() - timedelta(days=75))
_prj = Project(company_id=1, project_number="FM-P1", project_name="FM loyiha", client_name="FM Mijoz", client_phone="+998901234567")
_db.add_all([_m1, _m2, _sup, _obl, _prj])
_db.commit()
_ord = Order(company_id=1, project_id=_prj.id, order_number="FM-P1-1", order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS,
             total_amount=500000, agreed_amount=500000)
_db.add(_ord)
_db.commit()
ID = {"m1": _m1.id, "m2": _m2.id, "sup": _sup.id, "ord": _ord.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_l = (C.post("/login", data={"username": ADMIN, "password": PAROL}, follow_redirects=False).status_code,
      CB.post("/login", data={"username": "fmol_b", "password": PAROL}, follow_redirects=False).status_code)
_k1 = C.post("/api/inventory/receipt", json={"items": [{"inventory_id": ID["m1"], "quantity": 10, "price_per_unit": 3000}],
                                            "supplier_id": ID["sup"], "document_number": "FM-1", "paid_now": 0, "transport_cost": 5000,
                                            "tushirish_cost": 0, "yuklash_cost": 0, "boshqa_cost": 0, "add_to_cost": True,
                                            "notes": "fm", "production_type": "umumiy"})
_k2 = C.post("/api/inventory/receipt", json={"items": [{"inventory_id": ID["m2"], "quantity": 4, "price_per_unit": 1000}],
                                            "supplier_id": ID["sup"], "document_number": "FM-2", "paid_now": 0, "transport_cost": 0,
                                            "tushirish_cost": 4000, "yuklash_cost": 0, "boshqa_cost": 0, "add_to_cost": False,
                                            "notes": "fm2", "production_type": "umumiy"})
_q = {"date": BUGUN.isoformat() + "T00:00:00"}
_t1 = C.post("/api/finance/transactions", json=dict(_q, category="boshqa", amount=7000, notes="FM qo'lda"))
_t2 = C.post("/api/finance/transactions", json=dict(_q, category="tushlik", amount=3000, notes="FM o'chiriladi"))
_t3 = C.post("/api/finance/transactions", json=dict(_q, category="ijara_fm01", amount=100000, notes="FM ijara"))
_tb = CB.post("/api/finance/transactions", json=dict(_q, category="boshqa", amount=1000, notes="FM B"))
check("D0 kirdi; ikki kirim (tannarxga / alohida xarajat), uchta qo'lda xarajat, B korxonada bitta", _l == (302, 302)
      and _k1.status_code == 200 and _k2.status_code == 200 and all(x.status_code == 200 for x in (_t1, _t2, _t3, _tb)),
      (_l, _k1.status_code, js(_k1), _k2.status_code, [x.status_code for x in (_t1, _t2, _t3, _tb)]))
TX = {x["source"] + ":" + x["category"]: x for x in (js(C.get(f"/api/finance/transactions?year={BUGUN.year}&month={BUGUN.month}")) or [])}
KT = next((v for k, v in TX.items() if k.startswith("kirim_tannarx:")), None)
KX_ = next((v for k, v in TX.items() if k.startswith("inventory_receipt:")), None)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = [C.put(f"/api/finance/transactions/{x['id']}", json={"amount": 1, "category": x["category"], "date": x["date"]}) for x in (KT, KX_) if x]
_d = [C.delete(f"/api/finance/transactions/{x['id']}") for x in (KT, KX_) if x]
check("A1 kirim xarajatini (tannarxga — `kirim_tannarx`, alohida — `inventory_receipt`) tahrirlash / o'chirish — 409, sababi: Omborxonada "
      "hujjatni bekor qilish", len(_r) == 2 and all(r.status_code == 409 and "kirim hujjatiga tegishli" in str(js(r)) and "bekor qilish" in str(js(r))
                                                    for r in _r + _d), [(r.status_code, str(js(r))[:120]) for r in _r + _d])
_qolgan = {x["source"] + ":" + x["category"]: x["amount"] for x in (js(C.get(f"/api/finance/transactions?year={BUGUN.year}&month={BUGUN.month}")) or [])}
check("A2 rad etilgach kirim xarajatlari o'zgarmadi (5 000 va 4 000)", _qolgan.get("kirim_tannarx:transport_kirim") == 5000
      and _qolgan.get("inventory_receipt:tushirish_kirim") == 4000, _qolgan)
_tid1, _tid2 = (js(_t1) or {}).get("id"), (js(_t2) or {}).get("id")
_p = C.put(f"/api/finance/transactions/{_tid1}", json={"amount": 7500, "category": "boshqa", "date": BUGUN.isoformat() + "T00:00:00"})
_x = C.delete(f"/api/finance/transactions/{_tid2}")
check("A3 qo'lda kiritilgan xarajat — tahrirlanadi (200) va o'chiriladi (200)", _p.status_code == 200 and (js(_p) or {}).get("amount") == 7500
      and _x.status_code == 200, (_p.status_code, _x.status_code))
_bid = (js(_tb) or {}).get("id")
_f1 = C.delete(f"/api/finance/transactions/{_bid}")
_f2 = C.put(f"/api/finance/transactions/{_bid}", json={"amount": 1, "category": "boshqa", "date": BUGUN.isoformat() + "T00:00:00"})
check("A4 BOSHQA korxona yozuvi — 404 (borligi oshkor qilinmaydi)", _f1.status_code == 404 and _f2.status_code == 404, (_f1.status_code, _f2.status_code))
_ro = {x["category"]: x.get("category_label") for x in (js(C.get(f"/api/finance/transactions?year={BUGUN.year}&month={BUGUN.month}")) or [])}
check("A5 ro'yxatda majburiyat toifasi nomi (`category_label`): ijara_fm01 → «Ijara FM»; oddiy toifalarda — yo'q", _ro.get("ijara_fm01") == "Ijara FM"
      and _ro.get("boshqa") is None, _ro)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Brauzer (HAQIQIY Chromium)")
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
    except Exception as _e:                # noqa: BLE001
        br = None
        _pw_x = f"{type(_e).__name__}: {_e}"
check("B0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO, SOROV = [], []


def kontekst(user=ADMIN, w=1280, h=900, tel=False):
    ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""), q.post_data)) if "/api/" in q.url else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


def tasdiq_matni(pg):
    pg.wait_for_function("() => { const m = document.getElementById('ccModal'); return m && getComputedStyle(m).display !== 'none'; }")
    return pg.evaluate("() => document.getElementById('ccModalMessage').textContent").replace("\xa0", " ").replace("\u202f", " ")


def tasdiqla(pg, ha=True):
    pg.click("#ccModalOk" if ha else "#ccModalCancel")
    pg.wait_for_timeout(150)


# kech123 (zip 142 — test barqarorligi, O'LCHANGAN: etalon d150 yuklamasida 3 marta ketma-ket, d149 da ham — U-13 dan oldingi sahifalarda):
# qat'iy kutish (700 / 900 / 800 ms) server javobidan oldin tugab qolardi — hisobot hali eski oyda (B9), yoki to'lovdan keyingi
# `location.reload` keyingi `goto` ni uzardi (net::ERR_ABORTED — qolgan hamma tekshiruv o'tkazib yuborilardi). Endi kutish SHARTGA
# bog'langan; shart bajarilmasa — jim davom etiladi va tekshiruvning o'zi yiqiladi (asl / buzilgan kodda — qulamaydi, yiqiladi).
def shart_kut(pg, ifoda, ms=15000):
    try:
        pg.wait_for_function(ifoda, timeout=ms)
        return True
    except Exception:                      # noqa: BLE001
        return False


def qayta_yuklanib(pg, amal, ms=15000):
    """`amal` (tasdiq bosilishi) sahifani qayta yuklaydi — yuklanish TUGAGUNCHA kutiladi; `amal` ning o'z xatosi yashirilmaydi."""
    bajarildi = [False]
    try:
        with pg.expect_navigation(timeout=ms):
            amal()
            bajarildi[0] = True
    except Exception:                      # noqa: BLE001
        if not bajarildi[0]:
            raise
        return False
    return True


if br:
    ctx, pg = kontekst()
    try:
        # ── Moliya ──
        pg.goto(B + "/finance", wait_until="networkidle")
        pg.wait_for_timeout(400)
        _h = pg.evaluate("""() => ({lab: [...document.querySelectorAll('.fin-hero-label')].map(x => x.textContent.trim()),
                              sub: document.getElementById('hero-tannarx-sub').textContent})""")
        check("B1 Moliya «Bugungi holat»: «Yalpi foyda», izohda «xarajatlar ayirilmagan» (sof foyda — oylik hisobotda)",
              "Yalpi foyda" in _h["lab"] and "Sof foyda" not in _h["lab"] and "xarajatlar ayirilmagan" in _h["sub"], _h)
        _t = pg.evaluate("""() => [...document.querySelectorAll('#tx-body tr')].map(tr => ({cls: tr.className, matn: tr.innerText.replace(/\\s+/g, ' '),
                              tugma: tr.querySelectorAll('.fin-row-action').length, qulf: !!tr.querySelector('.tx-kirim-qulf')}))""")
        _kir = [x for x in _t if "kirim" in x["matn"].lower() and x["cls"] != "tx-jami"]
        _odd = [x for x in _t if "FM qo'lda" in x["matn"]]
        _jami = [x for x in _t if x["cls"] == "tx-jami"]
        check("B2 kirim xarajatlari (2) — «🔒 Kirim hujjati», tahrir / o'chirish tugmasi YO'Q; qo'lda kiritilgan — tugmalar bor",
              len(_kir) == 2 and all(x["qulf"] and x["tugma"] == 0 for x in _kir) and len(_odd) == 1 and _odd[0]["tugma"] == 2, _t)
        check("B3 ro'yxat ostida jami: hisobotdagi xarajat (7 500 + 100 000 + 4 000 = 111 500) va alohida — kirim tannarxida (5 000)",
              len(_jami) == 1 and "Jami (4 ta)" in _jami[0]["matn"] and "111 500" in _jami[0]["matn"] and "5 000" in _jami[0]["matn"]
              and "tannarxida" in _jami[0]["matn"] and any(x["cls"] == "tx-tannarxda" for x in _t), _jami)
        check("B4 majburiyat toifasi ro'yxatda nomi bilan («Ijara FM», xom «ijara_fm01» emas)",
              any("Ijara FM" in x["matn"] and "ijara_fm01" not in x["matn"] for x in _t), [x["matn"] for x in _t])
        _o = pg.evaluate("""() => { const r = {};
            openTxModal(); r.joriy = document.getElementById('tx-f-date').value; closeTxModal();
            const tk = tkHozir(); const oy = tk.oy === 1 ? 12 : tk.oy - 1, yil = tk.oy === 1 ? tk.yil - 1 : tk.yil;
            document.getElementById('tx-date').value = `${yil}-${String(oy).padStart(2, '0')}-01`;
            openTxModal(); r.otgan = document.getElementById('tx-f-date').value; closeTxModal();
            document.getElementById('tx-date').value = `${yil}-${String(oy).padStart(2, '0')}-17`;
            document.getElementById('tx-whole-month').checked = false;
            openTxModal(); r.kun = document.getElementById('tx-f-date').value; closeTxModal();
            document.getElementById('tx-whole-month').checked = true;
            r.bugun = tkISO(); r.kutilgan_kun = `${yil}-${String(oy).padStart(2, '0')}-17`; return r; }""")
        check("B5 yangi xarajat sanasi: joriy oy — BUGUN (1-kun emas); o'tgan oy («Butun oy») — bo'sh (o'zi tanlaydi); aniq kun — o'sha kun",
              _o["joriy"] == _o["bugun"] and _o["otgan"] == "" and _o["kun"] == _o["kutilgan_kun"], _o)
        pg.evaluate("""() => { const tk = tkHozir(); document.getElementById('tx-date').value = `${tk.yil}-${String(tk.oy).padStart(2, '0')}-01`; }""")
        pg.evaluate("() => loadDailyTransactions()")
        pg.wait_for_timeout(500)
        pg.evaluate("""() => { const b = [...document.querySelectorAll('#tx-body .fin-row-action[data-tx-category="ijara_fm01"]')][0]; b.click(); }""")
        _e = pg.evaluate("""() => { const s = document.getElementById('tx-f-category'); return {v: s.value, t: s.options[s.selectedIndex].textContent}; }""")
        del SOROV[:]
        pg.evaluate("() => saveTx()")
        pg.wait_for_timeout(600)
        _put = [x for x in SOROV if x[0] == "PUT"]
        check("B6 ro'yxatda yo'q toifali xarajatni tahrirlash: tanlovda «Ijara FM» (vaqtincha), saqlash — toifa o'zgarmaydi (PUT 200)",
              _e == {"v": "ijara_fm01", "t": "Ijara FM"} and len(_put) == 1 and json.loads(_put[0][2] or "{}").get("category") == "ijara_fm01", (_e, _put))
        # kassa: boshlang'ich balans
        _cb = C.post("/api/finance/cash-transaction", data={"category": "boshlangich", "amount": "1500000", "notes": "FM kassa"})
        pg.goto(B + "/finance", wait_until="networkidle")
        pg.wait_for_timeout(300)
        pg.evaluate("() => toggleCashTxHistory()")
        pg.wait_for_selector("#cashTxHistoryList .kassa-ochir")
        pg.evaluate("() => openCashTxModal('boshlangich')")
        pg.fill("#cashtx-amount", "200 000")
        del SOROV[:]
        pg.evaluate("() => { window.__s = saveCashTx(); }")
        _m = tasdiq_matni(pg)
        tasdiqla(pg, False)
        pg.wait_for_timeout(300)
        check("B7 kassa: saqlashdan oldin tasdiq; boshlang'ich balans AVVAL kiritilgan — ogohlantirish; «Bekor» — hech narsa yozilmaydi",
              _cb.status_code == 200 and "+200 000 so'm" in _m and "AVVAL kiritilgan" in _m
              and not any(x[1].startswith("/api/finance/cash-transaction") and x[0] == "POST" for x in SOROV), (_cb.status_code, _m, SOROV))
        pg.evaluate("() => document.getElementById('cashTxModal').style.display = 'none'")
        del SOROV[:]
        pg.click("#cashTxHistoryList .kassa-ochir")
        _m2 = tasdiq_matni(pg)
        tasdiqla(pg, True)
        pg.wait_for_function("() => !document.querySelector('#cashTxHistoryList .kassa-ochir')")
        _bal = js(C.get("/api/finance/cash-balance")) or {}
        _bal = {k: _bal.get(k) for k in ("balance", "boshlangich_kiritilgan")}
        check("B8 kassa yozuvini o'chirish: tasdiqda nomi va summasi, DELETE, ro'yxat bo'shadi, boshlang'ich balans yo'q holatga qaytdi",
              "Boshlang'ich balans" in _m2 and "1 500 000" in _m2 and any(x[0] == "DELETE" and "/api/finance/cash-transactions/" in x[1] for x in SOROV)
              and _bal.get("boshlangich_kiritilgan") is False, (_m2, SOROV, _bal))
        # oy o'zgarishi va PDF
        del SOROV[:]
        _oy = O_OY
        pg.select_option("#sel-month", str(_oy))
        shart_kut(pg, f"() => typeof korsatilganOy !== 'undefined' && !!korsatilganOy && String(korsatilganOy.month) === '{_oy}'")
        _rep = [x for x in SOROV if x[1].startswith("/api/finance/report?")]
        pg.evaluate("() => { window.__ochildi = []; window.open = (u) => { window.__ochildi.push(u); return null; }; downloadFinancePdf(); }")
        _pdf = pg.evaluate("() => window.__ochildi")
        # tanlov o'zgartirilib, hisobot hali yangilanmagan (masalan yil yozilmoqda) — PDF baribir EKRANDAGI oy
        _pdf2 = pg.evaluate("""() => { document.getElementById('sel-month').value = String(tkHozir().oy); window.__ochildi = []; downloadFinancePdf();
                                     return window.__ochildi; }""")
        _ymax = pg.evaluate("() => document.getElementById('sel-year').max")
        check("B9 oy tanlansa hisobot O'ZI yangilanadi (o'sha oy so'raladi); PDF — ekrandagi oy; yil chegarasi — joriy yil + 1",
              any(f"month={_oy}" in x[1] for x in _rep) and _pdf and f"month={_oy}" in _pdf[0] and _pdf2 and f"month={_oy}&" not in _pdf2[0]
              and _pdf2[0].endswith(f"month={_oy}") and str(_ymax) == str(BUGUN.year + 1), (_rep, _pdf, _pdf2, _ymax))
        # ── Qarzdorlar ──
        pg.goto(B + "/debts", wait_until="networkidle")
        pg.wait_for_timeout(300)
        pg.select_option("#pay-method", "plastik")
        pg.fill("#pay-amount", "1000")
        pg.evaluate("() => { window.__p = savePayment(); }")
        _m3 = tasdiq_matni(pg)
        qayta_yuklanib(pg, lambda: tasdiqla(pg, True))
        _db = SessionLocal()
        _pay = [(float(p.amount), (p.payment_method.value if hasattr(p.payment_method, "value") else str(p.payment_method)))
                for p in _db.query(Payment).filter(Payment.order_id == ID["ord"]).all()]
        _db.close()
        check("B10 qarz to'lovi: usul tanlanadi (Plastik), tasdiqda ko'rinadi, to'lov «plastik» bo'lib yoziladi (ilgari doim «naqd»)",
              "(plastik)" in _m3 and _pay == [(1000.0, "plastik")], (_m3, _pay))
        pg.goto(B + "/debts", wait_until="networkidle")
        pg.evaluate("() => switchTab('company')")
        _rows = pg.evaluate("""() => [...document.querySelectorAll('#tab-company .oblig-item[data-category="ijara_fm01"]')]
                                 .map(x => ({y: x.dataset.year, m: x.dataset.month, l: x.dataset.monthLabel}))""")
        check("B11 majburiyat qatorlari oy bilan (o'tgan oy va joriy oy alohida)", any(r["m"] == str(O_OY) for r in _rows), _rows)
        del SOROV[:]
        pg.evaluate(f"""() => document.querySelector('#tab-company .oblig-item[data-category="ijara_fm01"][data-month="{O_OY}"]').click()""")
        pg.wait_for_timeout(500)
        _tl = [x for x in SOROV if x[1].startswith("/api/obligations/timeline")]
        _sub = pg.evaluate("() => document.getElementById('tl-sub').textContent")
        pg.evaluate("() => closeTimelineModal()")
        check("B12 o'tgan oy qatori bosilganda tarix — O'SHA oy (so'rovda year / month, sarlavhada oy nomi)",
              len(_tl) == 1 and f"year={O_YIL}" in _tl[0][1] and f"month={O_OY}" in _tl[0][1] and OY_NOMI[O_OY] in _sub and str(O_YIL) in _sub,
              (_tl, _sub))
        del SOROV[:]
        pg.evaluate(f"""() => document.querySelector('#tab-company .oblig-item[data-category="ijara_fm01"][data-month="{O_OY}"] button').click()""")
        pg.wait_for_function("() => { const m = document.getElementById('kiModal'); return m && getComputedStyle(m).display !== 'none'; }")
        _izoh = pg.evaluate("() => document.getElementById('kiIzoh').textContent")
        pg.fill("#kiMaydon", "600 000")
        pg.click("#kiOk")
        _m4 = tasdiq_matni(pg)
        qayta_yuklanib(pg, lambda: tasdiqla(pg, True))
        _post = [json.loads(x[2] or "{}") for x in SOROV if x[0] == "POST" and x[1] == "/api/finance/transactions"]
        _kut_sana = f"{O_YIL}-{O_OY:02d}-28"
        check("B13 majburiyatni tez to'lash: oynada oy va «28.MM.YYYY sanasiga yoziladi»; qarzdan ko'p (600 000 > 500 000) — alohida tasdiq; "
              "o'sha oyning 28-sanasiga yoziladi", OY_NOMI[O_OY] in _izoh and f"28.{O_OY:02d}.{O_YIL} sanasiga yoziladi" in _izoh
              and "ko'p" in _m4 and len(_post) == 1 and _post[0].get("amount") == 600000 and _post[0].get("date", "").startswith(_kut_sana),
              (_izoh, _m4, _post))
        # ── Xarajat qo'shish ──
        pg.goto(B + "/kunlik-xarajat", wait_until="networkidle")
        pg.select_option("#kx-category", "tushlik")
        pg.type("#kx-amount", "150000,50")
        _v = pg.input_value("#kx-amount")
        del SOROV[:]
        pg.click("#kx-save-btn")
        shart_kut(pg, """() => { const o = document.getElementById('kx-success'), e = document.getElementById('kx-error');
                                return (!!o && o.style.display !== 'none' && o.textContent.trim() !== '') || (!!e && e.style.display !== 'none'); }""")
        _post = [json.loads(x[2] or "{}") for x in SOROV if x[0] == "POST" and x[1] == "/api/finance/transactions"]
        _ok = pg.evaluate("() => document.getElementById('kx-success').textContent")
        check("B14 «Xarajat qo'shish»: summa umumiy qoida bilan («150 000,50» → 150 000.5), saqlangach — summa, toifa, sana",
              _v == "150 000,50" and len(_post) == 1 and _post[0].get("amount") == 150000.5
              and _ok.replace("\xa0", " ") == f"✓ Saqlandi: 150 000.5 so'm · Tushlik · {BUGUN.strftime('%d.%m.%Y')}", (_v, _post, _ok))
        pg.fill("#kx-date", f"{O_YIL}-{O_OY:02d}-10")
        pg.fill("#kx-amount", "5000")
        del SOROV[:]
        pg.click("#kx-save-btn")
        _m5 = tasdiq_matni(pg)
        tasdiqla(pg, False)
        pg.wait_for_timeout(300)
        check("B15 boshqa oy sanasi — «joriy oy emas» tasdig'i; «Bekor» — yozilmaydi", "joriy oy emas" in _m5 and f"10.{O_OY:02d}.{O_YIL}" in _m5
              and not any(x[0] == "POST" for x in SOROV), (_m5, SOROV))
    except Exception as _e:                # noqa: BLE001
        check("B! kompyuter ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── Moliyachi: kassa yozuvini o'chira olmaydi ──
    C.post("/api/finance/cash-transaction", data={"category": "boshlangich", "amount": "100000", "notes": "FM kassa 2"})
    ctx, pg = kontekst(MOLIYA)
    try:
        pg.goto(B + "/finance", wait_until="networkidle")
        pg.evaluate("() => toggleCashTxHistory()")
        pg.wait_for_function("() => document.querySelectorAll('#cashTxHistoryList > div').length > 0")
        _n = pg.evaluate("() => ({tugma: document.querySelectorAll('#cashTxHistoryList .kassa-ochir').length, yozuv: document.querySelectorAll('#cashTxHistoryList > div').length})")
        check("B16 Moliyachi (kassa — faqat ko'rish): kassa tarixida o'chirish tugmasi YO'Q", _n["tugma"] == 0 and _n["yozuv"] >= 1, _n)
    except Exception as _e:                # noqa: BLE001
        check("B! Moliyachi ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── telefon 390 px: Qarzdorlar ──
    ctx, pg = kontekst(w=390, h=844, tel=True)
    try:
        pg.goto(B + "/debts", wait_until="networkidle")
        pg.wait_for_timeout(500)
        _ph = pg.evaluate("""() => ({skrol: document.querySelector('.dbt-wrap').scrollTop,
                              max: getComputedStyle(document.querySelector('.dbt-list')).maxHeight,
                              qidiruv: Math.round(document.getElementById('qarzQidiruv').getBoundingClientRect().top)})""")
        check("B17 telefon (390 px): sahifa ochilganda surilmaydi (qidiruv ekranda), ro'yxat ichida alohida aylantirish yo'q",
              _ph["skrol"] == 0 and _ph["max"] == "none" and 0 <= _ph["qidiruv"] < 844, _ph)
    except Exception as _e:                # noqa: BLE001
        check("B! telefon ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    check("B18 JS xatosi yo'q", not JS_XATO, JS_XATO)
if br:
    br.close()
if pw_ctx:
    pw_ctx.stop()
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
