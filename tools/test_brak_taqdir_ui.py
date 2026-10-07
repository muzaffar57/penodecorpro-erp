#!/usr/bin/env python3
"""
test_brak_taqdir_ui.py — kech125 (zip 146) darvozasi: BRAK TAQDIRI — HAQIQIY brauzerda (Chromium, Playwright) O'LCHANADI.

EGASI QARORLARI 07.10 (QAYTA SO'RALMAYDI): taqdir — «Brak yozish» oynasida tanlanadi (standart «Tashlandi»), keyin ro'yxatdan
o'zgartiriladi; Tuzatildi (o'sha joyiga / omborga; tuzatish xomashyosi), Kesildi (ishlatilgan qism, yangi detal), 2-nav (narx brak
yozilganda — Q1).
BO'LIMLAR: S — statik (shablon: forma, oyna, tana yig'uvchi, tugmalar); P — tayyorgarlik (API orqali yozuvlar);
  B — brauzer 1440 px: B1 Qaytarishlar — brak qatorida taqdir belgisi va «🧩»; B2 «🧩» → oyna, joriy taqdir (2-nav, narx) tanlangan;
  B3 noto'g'ri tana (narxsiz 2-nav) — xato matni, so'rov YO'Q; B4 Kesildi saqlanadi — so'rov tanasi va javob, sahifada yangi belgi;
  B5 «Brak yozish» — omborda turgan mahsulot, 2-nav 9 000 → `/api/finished/loss` tanasida `taqdir`, Tayyor mahsulotlarda «2-NAV»;
  B6 «Tashlandi» (standart) — tanada `taqdir` YO'Q (avvalgi so'rov AYNAN); B7 Tuzatildi — xomashyo qatori (loy retsepti), joy —
  tanada `materiallar`, `joy`; B8 Brak tahlili — yo'qotishlar jadvalida «Taqdiri» va «🧩» (omborda turgan — «joy» tanlovi yo'q);
  B9 JS xatosi yo'q; R — telefon 390 px: oyna sig'adi, gorizontal aylantirish yo'q, kartalar bitta ustunda; tungi rejim (`data-theme`).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 145) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_brak_taqdir_ui.py
"""
import os
import re
import io
import sys
import json
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
PG_BAZA = os.environ.get("BTQ_PG_BAZA", "brak_taqdir_ui_test")
_T = tempfile.mkdtemp(prefix="brak_taqdir_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'brak_taqdir_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth, services                          # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Inventory, Recipe, RecipeIngredient, OrderItem, FinishedProduct,   # noqa: E402
                    StockSource, ProductionStatus)

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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def funksiya(src, nom):
    m = re.search(r"(async\s+)?function\s+" + re.escape(nom) + r"\s*\(", src)
    if not m:
        return ""
    j = src.find("{", m.end())
    if j < 0:
        return ""
    d = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            d += 1
        elif src[k] == "}":
            d -= 1
            if d == 0:
                return src[m.start():k + 1]
    return ""


# ══════════════════════════════════════════════════════════════
section("S. Statik — templates/_brak_oyna.html, returns.html, finished.html")
BO = oqi("templates/_brak_oyna.html")
RT = oqi("templates/returns.html")
FN = oqi("templates/finished.html")
_tf = funksiya(BO, "taqdirFormaChiz")
_tt = funksiya(BO, "taqdirTanaOl")
_sb = funksiya(BO, "saveBrakBatch")
_sl = funksiya(BO, "submitLoss")
check("S1 brak oynasida taqdir bo'limi (`#brak-taqdir-forma`) va alohida «Taqdir» oynasi (`#taqdirModal`, yopish — `data-yopish`)",
      'id="brak-taqdir-forma"' in BO and 'id="taqdirModal"' in BO and 'onclick="taqdirOynaYop()"' in BO
      and BO.count("data-yopish") >= 4, None)
import crud as _crud_ui                             # noqa: E402
_m_yor = re.search(r"const BRAK_TAQDIR_YORLIQ = \{([^}]*)\};", BO)
_js_yor = dict(re.findall(r"(\w+): '([^']*)'", _m_yor.group(1))) if _m_yor else {}
_m_bir = re.search(r"const BRAK_TAQDIR_BIRLIKLAR = \[([^\]]*)\];", BO)
_js_bir = re.findall(r"'([^']*)'", _m_bir.group(1)) if _m_bir else []
check("S2 forma: to'rt taqdir — JS yorliqlari va birliklari serverdagi `BRAK_TAQDIRLARI` / `BRAK_TAQDIR_BIRLIKLARI` bilan AYNAN; "
      "Tuzatildi — joy (omborda turgan — yo'q) va xomashyo qatorlari, Kesildi — ishlatilgan / nom / miqdor / birlik, 2-nav — narx",
      _js_yor == getattr(_crud_ui, "BRAK_TAQDIRLARI", None) and tuple(_js_bir) == getattr(_crud_ui, "BRAK_TAQDIR_BIRLIKLARI", None)
      and "x.manba === 'ombor'" in _tf and "-tq-mat" in _tf and "-tq-ishlatildi" in _tf
      and "-tq-narx" in _tf and "taqdirMaterialQosh(this)" in _tf, (_js_yor, _js_bir, _tf[:300]))
check("S3 tana yig'uvchi: «Tashlandi» — null (tanaga qo'shilmaydi); 2-nav narxsiz / Kesildi ortiqcha qism — xato (so'rov yo'q)",
      "if (t === 'tashlandi') return null;" in _tt and "2-nav: sotuv narxini yozing" in _tt
      and "brak miqdoridan" in _tt, _tt[:300])
check("S4 saqlash: ikkala yo'lda taqdir — `typeof taqdirTanaOl === 'function'` bilan (eski sinov qobig'i qulamaydi), bir nechta "
      "detalda «Tashlandi» dan boshqasi — rad",
      "typeof taqdirTanaOl === 'function'" in _sb and "typeof taqdirTanaOl === 'function'" in _sl
      and "toSave.length > 1" in _sb and "taqdir: taqdirTana" in _sb and "...taqdirQism" in _sl, [_sb[:200], _sl[:200]])
check("S5 Qaytarishlar: brak qatorida taqdir belgisi va «🧩» (ruxsat bilan, `data-*`); tahlilda «Taqdiri» ustuni va «🧩»",
      "taqdirOynaOch(this)" in RT and 'data-turi="qaytarish"' in RT and "data-joriy='" in RT and "KORADI_BRAK_YARATISH" in RT
      and "Taqdir bo\\'yicha" in RT, None)
check("S6 Tayyor mahsulotlar: «2-NAV» / «BRAKDAN KESILGAN» / «TUZATILGAN» belgilari (`brak_taqdir`)",
      "i.brak_taqdir === 'ikkinchi_nav'" in FN and "2-NAV" in FN and "i.brak_taqdir === 'kesildi'" in FN, None)

# ══════════════════════════════════════════════════════════════
section("P. Tayyorgarlik")
ADMIN, PAROL = "btq_admin", "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, ADMIN, PAROL, UserRole.ADMIN, "Taqdir Admin", company_id=1)
prj = Project(company_id=1, client_name="UI Mijoz", project_name="UI loyiha", total_budget=0, total_paid=0)
peno = Inventory(company_id=1, item_name="UI Penoplast", unit="blok", stock_quantity=100, price_per_unit=1_000_000, volume_per_unit=1.0,
                 is_penoplast=True, category="Penoplast")
akr = Inventory(company_id=1, item_name="UI Akril", unit="kg", stock_quantity=100, price_per_unit=10_000, category="Kimyo")
s.add_all([prj, peno, akr])
s.commit()
rc = Recipe(company_id=1, name="UI loy", batch_size_kg=100.0)
s.add(rc)
s.commit()
s.add(RecipeIngredient(recipe_id=rc.id, inventory_id=akr.id, quantity_kg=100.0))
fp = FinishedProduct(company_id=1, name="UI tayyor karniz", category="profil", is_coated=False, quantity=50, produced_quantity=50,
                     unit="metr", unit_price=20_000, cost_price=500_000, source=StockSource.PRODUCED, penoplast_id=peno.id,
                     production_status=ProductionStatus.READY)
s.add(fp)
s.commit()
P = dict(prj=prj.id, peno=peno.id, akr=akr.id, rc=rc.id, fp=fp.id)
with contextlib.redirect_stdout(io.StringIO()):
    _l = services.get_or_create_loy_stock(s, s.get(Recipe, rc.id))
_l.stock_quantity = 0.0
s.commit()
s.close()

from fastapi.testclient import TestClient          # noqa: E402
_tc = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
check("P1 kirish (TestClient) — 302", _tc.post("/login", data={"username": ADMIN, "password": PAROL}, follow_redirects=False).status_code == 302)
_o = _tc.post("/api/orders", params={"confirm_shortage": "true"}, json={"project_id": P["prj"], "order_type": "product", "items": [
    {"name": "UI Karniz", "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 1, "unit_price": 50_000,
     "is_coated": False, "penoplast_id": P["peno"]}]})
OID = (_o.json() or {}).get("id") if _o.status_code == 200 else None
s = SessionLocal()
IID = s.query(OrderItem).filter(OrderItem.order_id == OID).first().id if OID else None
s.close()


def _brak(miqdor, taqdir=None):
    t = {"order_id": OID, "order_item_id": IID, "item_name": "UI Karniz", "quantity": miqdor, "unit": "metr", "brak_sabab": "boshqa",
         "reason": "Brak", "refund_amount": 0, "to_stock": False, "coating_applied": False}
    if taqdir:
        t["taqdir"] = taqdir
    r = _tc.post("/api/returns", json=t)
    return r.status_code, ((r.json() or {}).get("id") if r.status_code == 200 else None)


_s1, R1 = _brak(1.5, {"taqdir": "ikkinchi_nav", "narx": 8_000})
_s2, R2 = _brak(1)
_l3 = _tc.post("/api/finished/loss", json={"finished_product_id": P["fp"], "quantity": 2, "brak_sabab": "boshqa"})
L3 = (_l3.json() or {}).get("loss_id") if _l3.status_code == 200 else None
check("P2 yozuvlar: buyurtma detali braki 2-nav (8 000), taqdirsiz brak, omborda turgan mahsulot yo'qotishi — 200",
      OID and _s1 == 200 and _s2 == 200 and L3, (_o.status_code, _s1, _s2, _l3.status_code, _l3.text[:200]))

# ══════════════════════════════════════════════════════════════
section("B. Brauzer — 1440 px")
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"
check("B0 Python `playwright` bor", PW_BOR, _pw_xato)

import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


CHART_ORINBOSAR = "window.Chart = function () { return {destroy() {}, update() {}}; };"

if PW_BOR:
    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    check("B0a lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"

    def yonalish(route):
        u = route.request.url
        if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
            return route.fulfill(status=200, content_type="application/javascript", body=CHART_ORINBOSAR)
        if u.startswith("https://fonts.googleapis.com/"):
            return route.fulfill(status=200, content_type="text/css", body="")
        return route.fulfill(status=204, body="")

    with sync_playwright() as pw:
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                  "chrome-linux", "chrome"))):
            _exe = _yol
        try:
            br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()
        except Exception as _e:            # noqa: BLE001
            br = None
            check("B0b Chromium ishga tushdi", False, f"{type(_e).__name__}: {_e}")

        JS_XATOLAR = []
        SOROVLAR = []

        def kontekst(w):
            tel = w < 1000
            ctx = br.new_context(viewport={"width": w, "height": 900 if not tel else 844}, device_scale_factor=1, is_mobile=tel,
                                 has_touch=tel, timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                                 r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATOLAR.append(str(e)[:300]))
            pg.on("request", lambda rq: SOROVLAR.append((rq.method, rq.url, rq.post_data)) if rq.method == "POST" else None)
            pg.goto(BU + "/login")
            pg.fill("input[name=username]", ADMIN)
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            return ctx, pg

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def kut(pg, kod, ms=8000):
            try:
                pg.wait_for_function(kod, timeout=ms)
                return True
            except Exception:              # noqa: BLE001
                return False

        def tana(qism):
            """Oxirgi POST so'rovi tanasi (URL qismi bo'yicha) — dict yoki None."""
            for m, u, d in reversed(SOROVLAR):
                if qism in u:
                    try:
                        return json.loads(d or "null")
                    except Exception:      # noqa: BLE001
                        return {"xom": d}
            return None

        if br is not None:
            ctx, pg = kontekst(1440)
            pg.goto(BU + "/returns")
            pg.wait_for_load_state("networkidle")
            q1 = ev(pg, """(id) => { const r = document.getElementById('row-' + id); if (!r) return null;
                const b = r.querySelector('.dest-taqdir'); const t = r.querySelector('.brak-taqdir-btn');
                return {belgi: b ? b.textContent.trim() : null, tugma: !!t, joriy: t ? t.dataset.joriy : null}; }""", R1)
            q2 = ev(pg, """(id) => { const r = document.getElementById('row-' + id); if (!r) return null;
                return {chiqindi: (r.querySelector('.dest-scrap') || {}).textContent || null, tugma: !!r.querySelector('.brak-taqdir-btn')}; }""", R2)
            check("B1 Qaytarishlar: 2-nav brak qatorida «🏷️ 2-nav — omborda» va «🧩»; taqdirsiz brakda «Chiqindiga ketdi» va «🧩»",
                  isinstance(q1, dict) and "2-nav — omborda" in (q1.get("belgi") or "") and q1.get("tugma")
                  and isinstance(q2, dict) and "Chiqindiga ketdi" in (q2.get("chiqindi") or "") and q2.get("tugma"), [q1, q2])
            ev(pg, "(id) => document.querySelector('#row-' + id + ' .brak-taqdir-btn').click()", R1)
            ok_oyna = kut(pg, "() => getComputedStyle(document.getElementById('taqdirModal')).display === 'flex'")
            q3 = ev(pg, """() => ({tanlangan: (document.querySelector('input[name="tm-taqdir"]:checked') || {}).value,
                narx: (document.getElementById('tm-tq-narx') || {}).value, sub: document.getElementById('taqdir-sarlavha-sub').textContent,
                panel: !document.getElementById('tm-tq-panel-ikkinchi_nav').hidden})""")
            check("B2 «🧩» → «Taqdir» oynasi: joriy taqdir (2-nav) tanlangan, narx «8 000», sarlavhada nom va miqdor",
                  ok_oyna and isinstance(q3, dict) and q3.get("tanlangan") == "ikkinchi_nav" and q3.get("narx") == "8 000"
                  and q3.get("panel") and "UI Karniz" in (q3.get("sub") or ""), q3)
            n0 = len(SOROVLAR)
            ev(pg, "() => { document.getElementById('tm-tq-narx').value = ''; }")
            ev(pg, "() => document.getElementById('taqdir-saqla-btn').click()")
            time.sleep(0.4)
            q4 = ev(pg, "() => document.getElementById('taqdir-error').textContent")
            check("B3 narxsiz 2-nav — oynada xato matni, so'rov YUBORILMADI",
                  "narxini yozing" in str(q4) and not any("/taqdir" in u for _, u, _d in SOROVLAR[n0:]), (q4, SOROVLAR[n0:]))
            ev(pg, "() => { const r = document.querySelector('input[name=\"tm-taqdir\"][value=\"kesildi\"]'); r.checked = true; r.dispatchEvent(new Event('change')); }")
            ev(pg, """() => { document.getElementById('tm-tq-ishlatildi').value = '1';
                document.getElementById('tm-tq-nomi').value = 'UI kesilgan bo\\'lak';
                document.getElementById('tm-tq-miqdor').value = '2'; document.getElementById('tm-tq-birlik').value = 'dona'; }""")
            try:
                with pg.expect_navigation(timeout=15000):
                    ev(pg, "() => document.getElementById('taqdir-saqla-btn').click()")
                pg.wait_for_load_state("networkidle")
            except Exception:                  # noqa: BLE001 — sahifa yangilanmadi (asl kod): B4 yiqiladi, sinov qulamaydi
                pass
            t4 = tana(f"/api/returns/{R1}/taqdir")
            q5 = ev(pg, "(id) => (document.querySelector('#row-' + id + ' .dest-taqdir') || {}).textContent || null", R1)
            check("B4 Kesildi saqlandi: tana {taqdir: kesildi, ishlatildi 1, nomi, miqdor 2, birlik dona}; sahifa yangilandi — «✂️ Kesildi → …»",
                  t4 == {"taqdir": "kesildi", "ishlatildi": 1, "nomi": "UI kesilgan bo'lak", "miqdor": 2, "birlik": "dona"}
                  and "Kesildi → UI kesilgan bo'lak" in str(q5), (t4, q5))
            # B5 — «Brak yozish»: omborda turgan, 2-nav 9 000
            ev(pg, "() => showBrakModal('ombor')")
            kut(pg, "() => document.querySelector('#brak-fp option[value]:not([value=\"\"])') !== null")
            ev(pg, """(fid) => { const s = document.getElementById('brak-fp'); s.value = String(fid); s.dispatchEvent(new Event('change'));
                document.getElementById('loss-qty').value = '2'; document.getElementById('brak-cause').value = 'boshqa';
                const r = document.querySelector('input[name="bt-taqdir"][value="ikkinchi_nav"]'); r.checked = true;
                r.dispatchEvent(new Event('change')); document.getElementById('bt-tq-narx').value = '9 000'; }""", P["fp"])
            ev(pg, "() => brakSaqlash()")
            kut(pg, "() => getComputedStyle(document.getElementById('brakModal')).display === 'none'", 10000)
            time.sleep(0.6)
            t5 = tana("/api/finished/loss")
            check("B5 «Brak yozish» (omborda turgan): `/api/finished/loss` tanasida taqdir {ikkinchi_nav, narx 9000}",
                  isinstance(t5, dict) and t5.get("taqdir") == {"taqdir": "ikkinchi_nav", "narx": 9000} and t5.get("quantity") == 2, t5)
            pg.goto(BU + "/finished")
            pg.wait_for_load_state("networkidle")
            kut(pg, "() => document.querySelector('.fp-2nav') !== null", 8000)
            q6 = ev(pg, "() => [...document.querySelectorAll('.fp-2nav')].length")
            check("B5b Tayyor mahsulotlar: «🏷️ 2-NAV» belgili qatorlar (shu sinovdagi 2 ta 2-nav: avvalgisi kesildi bo'ldi → 1)", q6 == 1, q6)
            # B6 — Tashlandi (standart): tanada `taqdir` YO'Q
            pg.goto(BU + "/returns")
            pg.wait_for_load_state("networkidle")
            ev(pg, "() => showBrakModal('ombor')")
            kut(pg, "() => document.querySelector('#brak-fp option[value]:not([value=\"\"])') !== null")
            ev(pg, """(fid) => { const s = document.getElementById('brak-fp'); s.value = String(fid); s.dispatchEvent(new Event('change'));
                document.getElementById('loss-qty').value = '1'; document.getElementById('brak-cause').value = 'boshqa'; }""", P["fp"])
            ev(pg, "() => brakSaqlash()")
            kut(pg, "() => getComputedStyle(document.getElementById('brakModal')).display === 'none'", 10000)
            time.sleep(0.6)
            t6 = tana("/api/finished/loss")
            check("B6 standart «Tashlandi» — tanada `taqdir` kaliti YO'Q (avvalgi so'rov AYNAN)",
                  isinstance(t6, dict) and "taqdir" not in t6 and t6.get("quantity") == 1, t6)
            # B7 — Tuzatildi: xomashyo qatori (loy retsepti 0,4), joy — joyiga (buyurtma detali braki R2)
            ev(pg, "(id) => document.querySelector('#row-' + id + ' .brak-taqdir-btn').click()", R2)
            kut(pg, "() => getComputedStyle(document.getElementById('taqdirModal')).display === 'flex'")
            ev(pg, "() => { const r = document.querySelector('input[name=\"tm-taqdir\"][value=\"tuzatildi\"]'); r.checked = true; r.dispatchEvent(new Event('change')); }")
            ev(pg, "() => document.querySelector('#tm-tq-panel-tuzatildi button[data-p]').click()")
            kut(pg, "() => document.querySelector('#tm-tq-mat .brk-tq-mat-sel option[value^=\"r:\"]') !== null")
            q7a = ev(pg, """() => ({opt: [...document.querySelectorAll('#tm-tq-mat .brk-tq-mat-sel option')].map(o => o.value),
                joy: document.querySelectorAll('input[name="tm-joy"]').length})""")
            ev(pg, """(rid) => { const q = document.querySelector('#tm-tq-mat [data-tq-qator]'); q.querySelector('select').value = 'r:' + rid;
                q.querySelector('.brk-tq-mat-miq').value = '0,4'; document.querySelector('input[name="tm-joy"][value="joyiga"]').checked = true; }""", P["rc"])
            try:
                with pg.expect_navigation(timeout=15000):
                    ev(pg, "() => document.getElementById('taqdir-saqla-btn').click()")
                pg.wait_for_load_state("networkidle")
            except Exception:                  # noqa: BLE001 — sahifa yangilanmadi (asl kod): B7 yiqiladi, sinov qulamaydi
                pass
            t7 = tana(f"/api/returns/{R2}/taqdir")
            check("B7 Tuzatildi: xomashyo ro'yxatida loy retsepti va materiallar, joy tanlovi (2 ta); tana {joy: joyiga, materiallar: [retsept 0,4]}",
                  isinstance(q7a, dict) and f"r:{P['rc']}" in q7a.get("opt", []) and f"m:{P['akr']}" in q7a.get("opt", [])
                  and q7a.get("joy") == 2
                  and t7 == {"taqdir": "tuzatildi", "joy": "joyiga", "materiallar": [{"retsept_id": P["rc"], "miqdor": 0.4}]}, (q7a, t7))
            # B8 — Brak tahlili: yo'qotishlar jadvali
            ev(pg, "() => toggleBrakTahlil()")
            kut(pg, "() => document.querySelector('.brak-yoqotish-qator .brak-taqdir-btn') !== null", 10000)
            q8 = ev(pg, """(lid) => { const b = document.querySelector('.brak-yoqotish-qator .brak-taqdir-btn[data-id="' + lid + '"]');
                return b ? {manba: b.dataset.manba, turi: b.dataset.turi} : null; }""", L3)
            ev(pg, "(lid) => document.querySelector('.brak-yoqotish-qator .brak-taqdir-btn[data-id=\"' + lid + '\"]').click()", L3)
            kut(pg, "() => getComputedStyle(document.getElementById('taqdirModal')).display === 'flex'")
            ev(pg, "() => { const r = document.querySelector('input[name=\"tm-taqdir\"][value=\"tuzatildi\"]'); r.checked = true; r.dispatchEvent(new Event('change')); }")
            q8b = ev(pg, "() => ({joy: document.querySelectorAll('input[name=\"tm-joy\"]').length, izoh: document.getElementById('tm-tq-panel-tuzatildi').textContent})")
            check("B8 Brak tahlili: yo'qotishlar jadvalida «🧩» (turi yoqotish, manba ombor); omborda turgan — «joy» tanlovi YO'Q, izoh bor",
                  q8 == {"manba": "ombor", "turi": "yoqotish"} and isinstance(q8b, dict) and q8b.get("joy") == 0
                  and "o'sha partiyaga qaytadi" in (q8b.get("izoh") or ""), (q8, q8b))
            ev(pg, "() => taqdirOynaYop()")
            # tungi rejim
            ev(pg, "() => { document.documentElement.setAttribute('data-theme', 'dark'); }")
            ev(pg, "(id) => document.querySelector('#row-' + id + ' .brak-taqdir-btn').click()", R2)
            q9 = ev(pg, """() => { const m = document.querySelector('#taqdirModal > div'); const c = getComputedStyle(m);
                return {fon: c.backgroundColor, rang: getComputedStyle(document.getElementById('taqdir-sarlavha')).color}; }""")
            check("B9 tungi rejim (`data-theme`) — oyna foni va sarlavha rangi tungi (oq fon emas)",
                  isinstance(q9, dict) and q9.get("fon") not in ("rgb(255, 255, 255)", None) and q9.get("fon") != q9.get("rang"), q9)
            ev(pg, "() => { taqdirOynaYop(); document.documentElement.removeAttribute('data-theme'); }")
            ctx.close()

            # R — telefon 390 px
            ctx, pg = kontekst(390)
            pg.goto(BU + "/returns")
            pg.wait_for_load_state("networkidle")
            ev(pg, "(id) => document.querySelector('#row-' + id + ' .brak-taqdir-btn').click()", R2)
            kut(pg, "() => getComputedStyle(document.getElementById('taqdirModal')).display === 'flex'")
            qR = ev(pg, """() => { const m = document.querySelector('#taqdirModal > div').getBoundingClientRect();
                const k = [...document.querySelectorAll('#taqdir-forma label.brk-taqdir')].map(l => l.getBoundingClientRect());
                return {sw: document.documentElement.scrollWidth, iw: window.innerWidth, chap: m.left, ong: m.right,
                        ustun: new Set(k.map(r => Math.round(r.left))).size, tugma: document.getElementById('taqdir-saqla-btn').getBoundingClientRect().height}; }""")
            check("R1 telefon 390 px: oyna ekran ichida, sahifada gorizontal aylantirish yo'q, taqdir kartalari BITTA ustunda, tugma ≥ 36 px",
                  isinstance(qR, dict) and qR.get("sw", 999) <= qR.get("iw", 0) and qR.get("chap", -1) >= 0
                  and qR.get("ong", 999) <= qR.get("iw", 0) and qR.get("ustun") == 1 and qR.get("tugma", 0) >= 36, qR)
            ctx.close()
            check("B10 sahifalarda JS xatosi yo'q", not JS_XATOLAR, JS_XATOLAR[:5])
            br.close()
    server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  - " + f)
sys.exit(0 if FAIL == 0 else 1)
