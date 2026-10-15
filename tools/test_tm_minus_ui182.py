#!/usr/bin/env python3
"""
test_tm_minus_ui182.py — kech145 (zip 182, N5): minusdagi tayyor mahsulot KO'RINISHI. HAQIQIY Chromium, HAQIQIY lokal server (uvicorn,
test bazasi). EGASI QARORLARI 14.10 05:3x (QAYTA SO'RALMAYDI) + texnik qarorlar (`work/k182/REJA_182.md`).

NIMA UCHUN KERAK (O'LCHANGAN — staging 14.10 05:0x, FP 83 −5 m): «Tayyor mahsulotlar» da minusdagi partiya «Tugagan» deb YASHIRINARDI
(«Tugagan partiyalar yashirilgan: 1 ta»), «Kam qolganlar» 0 ta, ochilganda «-100 000 jami», «Foyda: 100%», «Sotish» / «Brak» / savatcha
belgisi / «O'chirish» faol; «Ma'lumot» va «Foyda hisobi» oynalarida manfiy qiymat va «FOYDA -100 000»; «Ishlab chiqarish» jadvalida
minus ko'rinmasdi; buyurtma tahririda «-5 m bor» va o'zgarmagan miqdor qizil (agent hisoboti 3-bo'lim).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 181) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_tm_minus_ui182.py
"""
import os
import re
import io
import sys
import glob
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tm_minus_ui182_test"
_T = tempfile.mkdtemp(prefix="tmui182_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tmui182.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, FinishedProduct, StockSource, ProductionStatus   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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
        print(f"  ✗ {label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "tmui182_admin", PAROL, UserRole.ADMIN, "TMUI182 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="TMUI182 Penoplast", unit="blok", stock_quantity=10000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
PRJ = Project(company_id=1, client_name="TMUI182 Mijoz", project_name="TMUI182 loyiha", total_budget=0, total_paid=0)
s.add_all([PENO, PRJ])
s.commit()
PENO_ID, PRJ_ID = PENO.id, PRJ.id
s.close()


def tm(nom, miqdor, narx=20000, kategoriya="profil", birlik="metr", tur=None):
    def f(d):
        fp = FinishedProduct(company_id=1, name=nom, category=kategoriya, width=20 if kategoriya == "profil" else None,
                             thickness=10 if kategoriya == "profil" else None, quantity=miqdor, produced_quantity=max(miqdor, 0),
                             unit=birlik, unit_price=narx, cost_price=max(miqdor, 0) * 1000, unit_cost_stable=1000,
                             source=StockSource.PRODUCED, production_status=ProductionStatus.READY, is_coated=False,
                             penoplast_id=PENO_ID if kategoriya == "profil" else None, unit_volume_m3=0.01 if kategoriya == "profil" else None,
                             volume_m3=0.01 * max(miqdor, 0), product_type_id=tur)
        d.add(fp)
        d.flush()
        return fp.id
    d = SessionLocal()
    try:
        r = f(d)
        d.commit()
        return r
    finally:
        d.close()


C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert C.post("/login", data={"username": "tmui182_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)

ID = {}
ID["M"] = tm("TMUI182 Minus karniz", 10)
# buyurtma minusga tushiradi (haqiqiy yo'l): 10 m dan 15 m (tasdiq) — qoldiq −5
_ro = C.post("/api/orders?confirm_shortage=true", json={"project_id": PRJ_ID, "order_type": "product", "loy_kg": 0, "items": [
    {"name": "TMUI182 detal", "category": "profil", "width": 20, "thickness": 10, "length": 15, "quantity": 1, "unit_price": 20000,
     "is_coated": False, "penoplast_id": PENO_ID, "finished_product_id": ID["M"]}]})
assert _ro.status_code == 200, _ro.text
ID["O"] = js(_ro)["id"]
ID["G1"], ID["G2"] = tm("TMUI182 Guruh karniz", -3), tm("TMUI182 Guruh karniz", 10)       # bazada majburan (ko'rinish sinovi)
ID["Z"] = tm("TMUI182 Tugagan karniz", 0)
_pt = js(C.post("/api/production/product-types", json={"name": "TMUI182 Travertin", "unit": "m2", "input_template": "quantity_only",
                                                       "pricing_formula": "unit_based"}))
ID["PT"] = _pt.get("id")
ID["PM"] = tm("TMUI182 Travertin", -2, narx=0, kategoriya="dynamic_bom", birlik="m2", tur=ID["PT"])


def tm_kalit(nom, eni=20, manba=StockSource.PRODUCED, taqdir=None):
    """Guruh kaliti sinovi (F10) — qoldiq 1 (yashirilmaydi, minus emas — boshqa tekshiruvlar sanog'iga tegmaydi)."""
    d = SessionLocal()
    try:
        fp = FinishedProduct(company_id=1, name=nom, category="profil", width=eni, thickness=10, quantity=1, produced_quantity=1,
                             unit="metr", unit_price=20000, cost_price=1000, unit_cost_stable=1000, source=manba,
                             production_status=ProductionStatus.READY, is_coated=False, penoplast_id=PENO_ID, unit_volume_m3=0.01,
                             volume_m3=0.01, brak_taqdir=taqdir)
        d.add(fp)
        d.commit()
        return fp.id
    finally:
        d.close()


KALIT = [tm_kalit("TMUI182 Kalit  karniz"), tm_kalit("TMUI182 Kalit karniz"),                 # nom ichida ikki bo'shliq — bitta guruh
         tm_kalit("TMUI182 Eni karniz", eni=0), tm_kalit("TMUI182 Eni karniz", eni=None),     # eni 0 va eni yo'q — ikki guruh
         tm_kalit("TMUI182 Qaytgan karniz", manba=StockSource.RETURNED),
         tm_kalit("TMUI182 Qaytgan karniz", manba=StockSource.RETURNED, taqdir="ikkinchi_nav")]   # 2-nav — alohida mahsulot

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Server va brauzer
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
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                              "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        br = None
        _pw_x = f"{type(_e).__name__}: {_e}"
check("T0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO = []


def kontekst(kenglik=1440):
    ctx = br.new_context(viewport={"width": kenglik, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.goto(B + "/login")
    pg.fill("input[name=username]", "tmui182_admin")
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


def ochiq(pg, yol):
    pg.goto(B + yol, wait_until="networkidle")
    pg.wait_for_timeout(500)


def qator(pg, fid):
    """Partiya qatori (guruh ichida yoki yakka) — `#fp-more-<id>` ning qatori."""
    return f"(() => {{ const m = document.getElementById('fp-more-{fid}'); return m ? m.closest('.fp-row') : null; }})()"


def qator_baho(pg, fid, ifoda):
    return pg.evaluate(f"() => {{ const r = {qator(pg, fid)}; if (!r) return null; return ({ifoda}); }}")


if br:
    ctx, pg = kontekst()
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("F. «Tayyor mahsulotlar» — minusdagi partiya")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ochiq(pg, "/finished")
    check("F1 minusdagi partiya «ko'rsatish» siz KO'RINADI (ilgari «Tugagan partiyalar yashirilgan» ichida); yashirilgani — faqat 0 li",
          qator_baho(pg, ID["M"], "true") is True and "yashirilgan: 1 ta" in (pg.evaluate(
              "() => (document.getElementById('fpYashirinIzoh') || {}).textContent || ''") or ""),
          pg.evaluate("() => (document.getElementById('fpYashirinIzoh') || {}).textContent || ''"))
    _q = qator_baho(pg, ID["M"], """{
        belgi: [...r.querySelectorAll('.fp-stock-col .fp-badge')].map(b => b.textContent.trim()).join('|'),
        izoh: (r.querySelector('.fp-minus-qator') || {}).textContent || '',
        sotish: !!r.querySelector('.fp-amal-sotish'), brak: !!r.querySelector('.fp-amal-brak'),
        katak: !!r.querySelector('.fp-batch-check'), yana: [...r.querySelectorAll('.fp-amal')].some(b => b.textContent.includes('Yana ishlab chiqarish')),
        ochir: [...r.querySelectorAll('.fp-more-band')].some(b => b.textContent.includes("O'chirish")),
        qiymat: (r.querySelector('.fp-total-col') || {}).textContent.replace(/\\s+/g, ' ').trim(),
        meta: (r.querySelector('.fp-meta') || {}).textContent || '', narx: (r.querySelector('.fp-price-col') || {}).textContent.replace(/\\s+/g, ' ').trim(),
        miqdor: (r.querySelector('.fp-qty') || {}).textContent.trim() }""")
    check("F2 belgi «Minusda» (ilgari «Tugagan»), izoh «ishlab chiqarish kerak: 5 m», miqdor «-5 m»",
          _q and _q["belgi"] == "Minusda" and _q["izoh"].strip() == "ishlab chiqarish kerak: 5 m" and _q["miqdor"] == "-5 m", _q)
    check("F3 «Sotish», «Brak», savatcha belgisi, «O'chirish» YO'Q; «Yana ishlab chiqarish» bor (minusni yopadi)",
          _q and not _q["sotish"] and not _q["brak"] and not _q["katak"] and not _q["ochir"] and _q["yana"], _q)
    check("F4 qiymat «— omborda yo'q» (ilgari «-100 000 jami»), «Foyda %» yo'q, «tan: —»",
          _q and _q["qiymat"] == "— omborda yo'q" and "Foyda" not in _q["meta"] and "tan: —" in _q["narx"], _q)
    _km = pg.evaluate("() => (document.getElementById('k-minus') || {}).textContent || ''")
    check("F5 «Kam qolganlar» kartasi ostida qizil izoh «⚠️ Minusda: 3 ta — 8 m · 2 m² ishlab chiqarish kerak» (−5, guruhdagi −3, MRP −2 m²)",
          "Minusda: 3 ta" in _km and "8 m" in _km and "2 m²" in _km and "ishlab chiqarish kerak" in _km, _km)
    _rang = pg.evaluate("() => { const e = document.getElementById('k-minus'); return e ? getComputedStyle(e).color : ''; }")
    check("F6 izoh rangi — `--m-b91c1c` (qizil, `.stat-izoh` kulrangidan ustun)", _rang == "rgb(185, 28, 28)", _rang)
    _g = pg.evaluate("""() => { const g = [...document.querySelectorAll('.fp-guruh')].find(x => x.textContent.includes('TMUI182 Guruh karniz'));
        if (!g) return null; const b = g.querySelector('.fp-guruh-bosh');
        return { izoh: (b.querySelector('.fp-minus-guruh') || {}).textContent || '', miqdor: (b.querySelector('.fp-qty') || {}).textContent.trim(),
                 sotish: !!b.querySelector('[onclick^="fpGuruhSotish"]') }; }""")
    check("F7 guruh (−3 va +10): sarlavha «7 m», izoh «omborda 10 · qarz 3 m — ishlab chiqarish kerak», guruh «Sotish» bor (7 > 0)",
          _g and _g["miqdor"] == "7 m" and _g["izoh"].strip() == "omborda 10 · qarz 3 m — ishlab chiqarish kerak" and _g["sotish"], _g)
    # F10 — sahifa guruhi = server guruhi (server shu guruh bo'yicha minusni yopadi va bo'sh qoldiqni ushlaydi)
    import crud as _crud_k                         # noqa: E402
    _kf = getattr(_crud_k, "tm_guruh_kaliti", None)
    _d = SessionLocal()
    try:
        _srv = {i: (_kf(_d.get(FinishedProduct, i)) if _kf else None) for i in KALIT}
    finally:
        _d.close()
    _ui = pg.evaluate("(ids) => Object.fromEntries(ids.map(id => [id, fpGuruhKaliti(fpItems.find(x => x.id === id) || {})]))", KALIT)
    _ui = {int(k): v for k, v in (_ui or {}).items()}
    _farq = [(a, b) for a in KALIT for b in KALIT if a < b and (_ui.get(a) == _ui.get(b)) != (_srv[a] == _srv[b])]
    check("F10 sahifa guruhi = server guruhi: nom ichidagi ikki bo'shliq — bitta guruh, eni 0 / eni yo'q — ikki, 2-nav — alohida",
          bool(_kf) and not _farq and len(_ui) == len(KALIT), (_farq, _ui, _srv))
    pg.evaluate(f"() => openHistoryModal({ID['M']})")
    pg.wait_for_timeout(300)
    _h = pg.evaluate("() => document.getElementById('hist-body').innerText")
    check("F8 «Ma'lumot»: «Buyurtmalarga qarz (ishlab chiqarish kerak) 5 m», «Joriy qiymati» «—» (ilgari «-100 000 so'm»)",
          "Buyurtmalarga qarz (ishlab chiqarish kerak)" in _h and "5 m" in _h and "-100" not in _h and re.search(r"Joriy qiymati[^\n]*\n?\s*—", _h),
          _h)
    pg.evaluate("() => closeHistoryModal()")
    pg.evaluate(f"() => openProfitModal({ID['M']})")
    pg.wait_for_timeout(1200)
    _p = pg.evaluate("() => document.getElementById('pm-body').innerText")
    check("F9 «Foyda hisobi»: «Mahsulot minusda (5 m buyurtmalarga qarz …)», «FOYDA» va «-100 000» yo'q",
          "Mahsulot minusda (5 m buyurtmalarga qarz" in _p and "FOYDA" not in _p and "-100" not in _p, _p)
    ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("W. Telefon / planshet kengligida — yon surilish yo'q")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    for _k in (390, 320, 768):
        ctx, pg = kontekst(_k)
        ochiq(pg, "/finished")
        _w = pg.evaluate("""() => ({ sahifa: document.documentElement.scrollWidth - innerWidth,
            izohlar: [...document.querySelectorAll('.fp-minus-izoh')].map(e => e.scrollWidth - e.clientWidth),
            kor: [...document.querySelectorAll('.fp-minus-izoh')].filter(e => e.getClientRects().length).length })""")
        check(f"W{_k} {_k} px: sahifa yon surilishi 0, minus izohlari toshmaydi (3 ta ko'rinadi)",
              _w["sahifa"] <= 0 and all(x <= 0 for x in _w["izohlar"]) and _w["kor"] >= 3, _w)
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("P / O. «Ishlab chiqarish» jadvali va buyurtma tahriri")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    ochiq(pg, "/production")
    pg.wait_for_timeout(800)
    _pm = pg.evaluate("() => [...document.querySelectorAll('.pt-minus')].map(e => e.textContent.trim())")
    check("P1 mahsulot turi qatorida «minusda 2 m² — ishlab chiqarish kerak»", _pm == ["minusda 2 m² — ishlab chiqarish kerak"], _pm)
    ochiq(pg, f"/orders?order={ID['O']}")
    pg.wait_for_timeout(800)
    pg.evaluate("() => editSelected('edit')")
    pg.wait_for_timeout(2000)
    _o = pg.evaluate("""() => { const t = document.querySelector('[id^="fptag-"]'); const row = t ? document.getElementById(t.id.replace('fptag-', '')) : null;
        return { teg: t ? t.firstChild.textContent : null, xato: row ? (row.dataset.fpError || '') : null, max: row ? row.dataset.fpMax : null }; }""")
    check("O1 tahrir: teg «minusda 5 m — ishlab chiqarish kerak» (ilgari «-5 m bor»), o'zgarmagan 15 m qizil EMAS (limit 15)",
          _o and (_o["teg"] or "").strip() == "🏭 Tayyor mahsulotdan · minusda 5 m — ishlab chiqarish kerak" and _o["xato"] != "1"
          and str(_o["max"]) == "15", _o)
    ctx.close()
    check("J0 sahifalarda JS xatosi yo'q", not JS_XATO, JS_XATO)
    br.close()
    pw_ctx.stop()

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:\n  - " + "\n  - ".join(FAILED))
sys.exit(0 if FAIL == 0 else 1)
