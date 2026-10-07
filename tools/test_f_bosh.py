#!/usr/bin/env python3
"""
test_f_bosh.py — kech120, F BOSQICH 5-qism (BOSH SAHIFA, DASHBOARD, HISOBOTLAR — audit G1 qolgan bandlari).

NIMA UCHUN KERAK (audit kech114; 2026-10-01 da JORIY kodda qayta tekshirildi — work/f/tekshiruv_kech120.md; O'LCHANGAN
work/f5/probe_g1.py):
  G1-07  «Faol buyurtmalar»: Bosh sahifada «Tayyor» dan boshqa HAMMASI (qoralama, yetkazilgan, bekor ham — 8 tadan 7), Dashboard avval
         shu sonni, so'ng qoralamali boshqasini (5) ko'rsatardi; «Korxona sog'ligi» oldindan to'langan (arxivdagi) yangi buyurtmani
         sanamasdi; «Faol ustalar» — HAMMA usta.
  G1-12  Usta reytingi: ko'rinmaydigan summa bo'yicha, ostida HAMMA buyurtma soni; buyurtmasiz ustalar «Top» da; uzun ism 4 qator.
  G1-13  Bo'sh korxona: grafik o'qi «0 0 1 1» / «0 1», materiali yo'q omborga «Barcha xomashyo yetarli», yo'l-yo'riq yo'q.
  G1-15  «Shu oy» — aslida oxirgi 30 kun, «Yil» — 365 kun; izoh «jadvalga birga qo'llanadi» der edi (qo'llanmaydi); joriy oy bloklari
         davrsiz.
  G1-17  Saralashda qidiruv yo'qoladi (Excel ham hammasini yuklaydi); Excel «20x15» → 20, «Qoldiq» birliksiz; bo'sh jadvalda xom
         oyna «Avval ma'lumot yuklanishini kuting».
  G1-25  Dashboard «Yangilash» hech narsa bildirmaydi, majburiyatlar va avans so'rovlarini yangilamaydi.
BO'LIMLAR: S — statik; D — ma'lumot (A korxona — har holatda buyurtma, 4 usta, 3 material; B — bo'sh; C — material va usta bor,
  buyurtma yo'q); A — API; R — server chizgan Dashboard; B — HAQIQIY Chromium (Bosh sahifa, Dashboard, Hisobotlar; Chart.js va
  SheetJS — CDN o'rniga yozib oluvchi soxta).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 134) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium (B).
ISHLATISH: python3 tools/test_f_bosh.py
"""
import os
import re
import io
import sys
import glob
import time
import uuid
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "f_bosh_test"
_T = tempfile.mkdtemp(prefix="fbosh_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'f_bosh_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Order, OrderType, OrderStatus, Master, Inventory)   # noqa: E402
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


def nb(s):
    return str(s or "").replace("\xa0", " ").replace(" ", " ")


OYLAR = ['', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr']
_TK = datetime.utcnow() + timedelta(hours=5)


def davr_matni(n):
    """reports.html `davrOylarMatni` ning kutilgan natijasi (Toshkent oyi bo'yicha)."""
    y, m = _TK.year, _TK.month - (n - 1)
    while m < 1:
        m += 12
        y -= 1
    if n <= 1:
        return f"{OYLAR[_TK.month]} {_TK.year}"
    return f"{OYLAR[m]} – {OYLAR[_TK.month]} {_TK.year}" if y == _TK.year else f"{OYLAR[m]} {y} – {OYLAR[_TK.month]} {_TK.year}"


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
SRV = oqi("services.py")
HOME = oqi("templates/home.html")
DASH = oqi("templates/dashboard.html")
REP = oqi("templates/reports.html")
BASE = oqi("templates/base.html")
CSS = oqi("static/style.css")
check("S1 «faol buyurtma» — BITTA qoida (`FAOL_HOLATLAR`: yangi, jarayonda, qoplamada) — Bosh sahifa, Dashboard, «Korxona sog'ligi»; "
      "eski ta'riflar («Tayyor» dan boshqasi, `notin_` READY/DELIVERED/CANCELLED, arxiv sharti) YO'Q; usta reytingi — tayyor buyurtmalar",
      "FAOL_HOLATLAR = (OrderStatus.NEW, OrderStatus.IN_PROGRESS, OrderStatus.COATING)" in SRV and SRV.count("Order.status.in_(FAOL_HOLATLAR)") >= 5
      and "Order.status != OrderStatus.READY, Order.is_deleted.isnot(True)).count()" not in SRV
      and "Order.status.notin_([OrderStatus.READY, OrderStatus.DELIVERED, OrderStatus.CANCELLED]),\n        Order.is_deleted.isnot(True)\n    ).count()" not in SRV
      and "Order.is_deleted.isnot(True), Order.is_archived.isnot(True),\n        Order.status.in_(" not in SRV
      and '"active_masters": active_masters,\n        "total_inventory_items"' in SRV
      and 'master_kpi.sort(key=lambda x: (-x["total"], -x["orders"], str(x["name"] or "").lower()))' in SRV)
check("S2 Bosh sahifa: «Ustalar» (ilgari «Faol ustalar») va faol buyurtmali ustalar soni, «Boshlash — 4 qadam», bo'sh ombor yozuvi; "
      "Dashboard: «Yangilash» (`dashYangila`), reyting mezoni, bitta qatorli ism, bo'sh grafik", ">Faol ustalar<" not in HOME
      and 'id="k-masters-sub"' in HOME and "function boshlashKorsat(s)" in HOME and "Omborda hali material yo" in HOME
      and 'onclick="dashYangila()"' in DASH and 'onclick="loadAll()"' not in DASH and "async function dashYangila()" in DASH
      and "tayyor buyurtmalar summasi bo'yicha" in DASH and ".master-ism{" in DASH and "ta tayyor buyurtma" in DASH
      and "grafikBosh('ordersCountChart'" in DASH)
check("S3 Hisobotlar: tugmalar — haqiqiy davr («Oxirgi 30 kun», «Oxirgi 12 oy»), izoh, bloklar davri, bo'sh grafik, qidiruv saralashdan "
      "keyin, Excel — son / birlik ustunlari, bo'sh jadvalda oddiy xabar; base.html `grafikBosh`, style.css `.grafik-bosh`",
      ">Shu oy</button>" not in REP and ">Oxirgi 30 kun</button>" in REP and ">Oxirgi 12 oy</button>" in REP
      and "jadvalga birga qo'llanadi" not in REP and "function davrOylarMatni(n)" in REP and "grafikBosh('mainTrendChart'" in REP
      and "function excelQatorlari()" in REP and "toNumberIfPossible" not in REP and "alert('Avval ma" not in REP
      and "  filterTable();\n}" in REP and "function grafikBosh(canvas, matn)" in BASE and ".grafik-bosh {" in CSS)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Ma'lumot")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, BOSH, YARIM, PAROL = "fbosh_admin", "fbosh_bosh", "fbosh_yarim", "Parol123!"
_db = SessionLocal()
for _cid, _nom in ((2, "FBo B korxona"), (3, "FBo C korxona")):
    if not _db.query(Company).filter(Company.id == _cid).first():
        _db.add(Company(id=_cid, name=_nom, code=f"FBO-{_cid}"))
        _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, ADMIN, PAROL, UserRole.ADMIN, "FBo Admin", company_id=1)
    auth.create_user(_db, BOSH, PAROL, UserRole.ADMIN, "FBo Bo'sh", company_id=2)
    auth.create_user(_db, YARIM, PAROL, UserRole.ADMIN, "FBo Yarim", company_id=3)
_n = uuid.uuid4().hex[:4]
UZUN = f"Abdulazizxon Abdurahmonov Muhammadjon o'g'li Ikki {_n}"
_m = [Master(company_id=1, name=f"FBo Usta Bir {_n}", phone=f"+9989011{_n}1"),
      Master(company_id=1, name=UZUN, phone=f"+9989011{_n}2"),
      Master(company_id=1, name=f"FBo Usta Uch {_n}", phone=f"+9989011{_n}3"),
      Master(company_id=1, name=f"FBo Bo'sh usta {_n}", phone=f"+9989011{_n}4"),
      Master(company_id=3, name=f"FBo C usta {_n}", phone=f"+9989011{_n}5")]
_db.add_all(_m)
_p = Project(company_id=1, project_number=f"FBo-{_n}", project_name=f"FBo Hovli {_n}", client_name="FBo Mijoz")
_db.add(_p)
_db.add_all([Inventory(company_id=1, item_name=f"20x15 profil {_n}", stock_quantity=12, unit="dona", min_stock=2, price_per_unit=15000),
             Inventory(company_id=1, item_name=f"Gips G-1 {_n}", stock_quantity=630.52, unit="kg", min_stock=10, price_per_unit=2500),
             Inventory(company_id=1, item_name=f"3D panel qolip {_n}", stock_quantity=1234.5, unit="m²", min_stock=0, price_per_unit=100),
             Inventory(company_id=3, item_name=f"FBo C gips {_n}", stock_quantity=50, unit="kg", min_stock=5, price_per_unit=2000)])
_db.commit()
_hozir = datetime.utcnow()
_kecha = _hozir - timedelta(days=1)


def _ord(teg, holat, summa, usta=None, **k):
    return Order(company_id=1, project_id=_p.id, order_number=f"FBo-{_n}-{teg}", order_type=OrderType.PRODUCT, status=holat,
                 total_amount=summa, agreed_amount=summa, master_id=usta.id if usta else None, **k)


_db.add_all([
    _ord("Q", OrderStatus.DRAFT, 10000, _m[2]),
    _ord("Y", OrderStatus.NEW, 20000, _m[2]),
    _ord("J", OrderStatus.IN_PROGRESS, 30000, _m[0]),
    _ord("P", OrderStatus.COATING, 40000, _m[1]),
    # teng summa (150 000): 1-usta — bitta buyurtma, 2-usta (keyin yaratilgan) — ikkita → 2-usta oldin (soni bo'yicha)
    _ord("T1", OrderStatus.READY, 150000, _m[0], completed_at=_hozir),
    _ord("T2", OrderStatus.READY, 100000, _m[1], completed_at=_hozir),
    _ord("T3", OrderStatus.READY, 50000, _m[1], completed_at=_hozir),
    _ord("TO", OrderStatus.READY, 70000, _m[2], completed_at=_hozir, is_deleted=True),     # o'chirilgan — moliyada qoladi
    _ord("YT", OrderStatus.DELIVERED, 60000),
    _ord("B", OrderStatus.CANCELLED, 80000),
    _ord("ARX", OrderStatus.NEW, 50000, _m[0], is_archived=True, deadline=_kecha),        # oldindan to'langan, muddati o'tgan
])
_db.commit()
ID = {"m": [x.id for x in _m], "p": _p.id}
_db.close()


def mijoz(user):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    return c, c.post("/login", data={"username": user, "password": PAROL}, follow_redirects=False).status_code


CA, _la = mijoz(ADMIN)
CB, _lb = mijoz(BOSH)
CC, _lc = mijoz(YARIM)
check("D0 kirdi; A — 11 buyurtma (har holatda, o'chirilgan tayyor, arxivdagi yangi), 5 usta, 3 material; B — bo'sh; C — material va usta",
      _la == _lb == _lc == 302 and all(ID["m"]), (_la, _lb, _lc))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_s = js(CA.get("/api/dashboard/stats"))
_t = js(CA.get("/api/dashboard/today"))
check("A1 «Faol buyurtmalar» — Bosh sahifa va Dashboard BIR xil: 4 (yangi, jarayonda, qoplamada, arxivdagi yangi; ilgari 7 va 5)",
      _s.get("active_orders") == 4 and _t.get("active_orders") == 4, (_s.get("active_orders"), _t.get("active_orders")))
check("A2 ustalar: jami 4 (faol, shu korxona), faol buyurtmalisi 3 — Bosh sahifa va Dashboard «Ishlayotgan ustalar» bir xil",
      _s.get("total_masters") == 4 and _s.get("active_masters") == 3 and _t.get("active_masters") == 3,
      (_s.get("total_masters"), _s.get("active_masters"), _t.get("active_masters")))
_h = js(CA.get("/api/reports/business-health"))
check("A3 «Korxona sog'ligi» — «Ishlab chiqarish»: arxivdagi (oldindan to'langan) muddati o'tgan yangi buyurtma ham sanaladi "
      "(«1 ta buyurtmaning muddati o'tgan (4 tadan)»; ilgari ko'rinmasdi)",
      isinstance(_h, dict) and _h.get("ishlab_chiqarish") == "orange"
      and (_h.get("sabablar") or {}).get("ishlab_chiqarish") == "1 ta buyurtmaning muddati o'tgan (4 tadan)", _h)
_mk = (js(CA.get("/api/dashboard/charts")) or {}).get("master_kpi")
check("A4 usta reytingi: faqat tayyor buyurtmasi bor ustalar (buyurtmasiz — yo'q); soni — summa bilan bir to'plam (tayyor, o'chirilgani "
      "ham); teng summada — soni ko'pi oldin",
      _mk == [{"name": UZUN, "total": 150000.0, "orders": 2}, {"name": f"FBo Usta Bir {_n}", "total": 150000.0, "orders": 1},
              {"name": f"FBo Usta Uch {_n}", "total": 70000.0, "orders": 1}], _mk)
_sb = js(CB.get("/api/dashboard/stats"))
_kb = (js(CB.get("/api/dashboard/charts")) or {}).get("master_kpi")
check("A5 bo'sh korxona: 0 faol, 0 usta, reyting bo'sh, materiallar 0", _sb.get("active_orders") == 0 and _sb.get("active_masters") == 0
      and _sb.get("total_inventory_items") == 0 and _kb == [], (_sb, _kb))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Server chizgan Dashboard")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_dh = CA.get("/dashboard").text
_ta = re.search(r'id="t-active">([^<]*)<', _dh)
check("R1 Dashboard sahifasi ochilishidagi «Faol buyurtmalar» — «4 ta» (keyin JS ham «4 ta»; ilgari 7 → 5 ga sakrardi)",
      _ta and _ta.group(1) == "4 ta", _ta.group(1) if _ta else None)

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
JS_XATO, SOROV, DIALOG = [], [], []

# Chart.js / SheetJS (CDN) o'rniga — yozib oluvchi soxtalar: qaysi grafik chizildi, Excel ga nima yozildi
CHART_SOXTA = """window.__grafiklar = []; window.Chart = function Chart(ctx, cfg) { const c = ctx && (ctx.canvas || ctx);
  window.__grafiklar.push((c && c.id) || '?'); this.config = cfg || {}; this.data = (cfg && cfg.data) || {datasets: []}; };
  window.Chart.prototype.destroy = function () {}; window.Chart.prototype.update = function () {}; window.Chart.register = function () {};
  window.Chart.defaults = {font: {}, color: '', plugins: {legend: {labels: {}}, tooltip: {}}};"""
XLSX_SOXTA = """window.__excel = null; window.XLSX = {utils: {aoa_to_sheet: a => { window.__excel = JSON.parse(JSON.stringify(a)); return {}; },
  book_new: () => ({}), book_append_sheet: () => {}}, writeFile: (wb, nom) => { window.__excelFayl = nom; }};"""


def kontekst(user=ADMIN, w=1440, h=900):
    ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    ctx.route(re.compile(r".*chart\.umd(\.min)?\.js.*"), lambda route: route.fulfill(status=200, content_type="text/javascript", body=CHART_SOXTA))
    ctx.route(re.compile(r".*xlsx\.full\.min\.js.*"), lambda route: route.fulfill(status=200, content_type="text/javascript", body=XLSX_SOXTA))
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""))) if "/api/" in q.url else None)
    pg.on("dialog", lambda d: (DIALOG.append(d.message), d.dismiss()))
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


BOSH_JS = """() => { const k = document.getElementById('boshlashCard');
  return {kor: !!k && getComputedStyle(k).display !== 'none',
          qadam: [...document.querySelectorAll('#boshlashQadamlar .boshlash-qadam')].map(q => ({teg: q.tagName.toLowerCase(),
            href: q.getAttribute('href'), baj: q.classList.contains('bajarildi'), raqam: q.querySelector('.bq-raqam').textContent,
            nom: q.querySelector('b').textContent})),
          kam: document.getElementById('lowStock').innerText.trim()}; }"""

if br:
    # ── Bosh sahifa ──
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/", wait_until="networkidle")
        pg.wait_for_timeout(500)
        _ha = pg.evaluate("""() => { const kart = [...document.querySelectorAll('#statGrid .stat-card')].map(c => ({l: c.querySelector('.stat-label').textContent.trim(),
            v: c.querySelector('.stat-val').textContent.trim(), t: (c.querySelector('.stat-trend') || {}).textContent || ''}));
            return {kart}; }""")
        _bo = pg.evaluate(BOSH_JS)
        _fk = next((k for k in _ha["kart"] if k["l"] == "Faol buyurtmalar"), {})
        _uk = next((k for k in _ha["kart"] if k["l"] == "Ustalar"), {})
        check("B1 Bosh sahifa: «Faol buyurtmalar» 4 («Yangi, jarayonda, qoplamada»), «Ustalar» 4 — «3 tasida faol buyurtma» (ilgari «Faol "
              "ustalar» 4); buyurtmasi bor korxonada «Boshlash» yo'q", _fk.get("v") == "4" and "jarayonda" in _fk.get("t", "")
              and _uk.get("v") == "4" and nb(_uk.get("t")).strip() == "3 tasida faol buyurtma"
              and not any(k["l"] == "Faol ustalar" for k in _ha["kart"]) and not _bo["kor"], (_ha, _bo))
    except Exception as _e:                # noqa: BLE001
        check("B! Bosh sahifa (A)", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    ctx, pg = kontekst(BOSH)
    try:
        pg.goto(B + "/", wait_until="networkidle")
        pg.wait_for_timeout(500)
        _bo = pg.evaluate(BOSH_JS)
        check("B2 bo'sh korxona Bosh sahifa: «Boshlash — 4 qadam» (xomashyo, usta, loyiha, buyurtma — har biri o'z sahifasiga havola); "
              "«Kam qolgan xomashyo» — «Omborda hali material yo'q» (ilgari «Barcha xomashyo yetarli»)",
              _bo["kor"] and [q["href"] for q in _bo["qadam"]] == ["/suppliers/receive", "/ustalar", "/projects?yangi=1", "/orders?yangi=1"]
              and [q["raqam"] for q in _bo["qadam"]] == ["1", "2", "3", "4"] and not any(q["baj"] for q in _bo["qadam"])
              and _bo["kam"] == "Omborda hali material yo'q", _bo)
        _rx = pg.evaluate("""() => { BOSHLASH_RUXSAT.kirim = false; boshlashKorsat({total_orders: 0, total_inventory_items: 0, total_masters: 0,
            total_projects: 0}); const q = document.querySelector('#boshlashQadamlar .boshlash-qadam'); return {teg: q.tagName.toLowerCase(),
            href: q.getAttribute('href')}; }""")
        check("B3 «Kirim qilish» ruxsati yo'q — 1-qadam havolasiz (oddiy yozuv)", _rx == {"teg": "div", "href": None}, _rx)
    except Exception as _e:                # noqa: BLE001
        check("B! Bosh sahifa (bo'sh korxona)", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    ctx, pg = kontekst(YARIM)
    try:
        pg.goto(B + "/", wait_until="networkidle")
        pg.wait_for_timeout(500)
        _bo = pg.evaluate(BOSH_JS)
        check("B4 material va usta bor, buyurtma yo'q: 1–2-qadam «✓ Bajarildi» (havolasiz, chizilgan), 3–4 — havola; ombor — «Barcha "
              "xomashyo yetarli»", _bo["kor"] and [(q["teg"], q["baj"], q["raqam"]) for q in _bo["qadam"]]
              == [("div", True, "✓"), ("div", True, "✓"), ("a", False, "3"), ("a", False, "4")] and _bo["kam"] == "Barcha xomashyo yetarli", _bo)
    except Exception as _e:                # noqa: BLE001
        check("B! Bosh sahifa (C korxona)", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ── Dashboard ──
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/dashboard", wait_until="networkidle")
        pg.wait_for_timeout(700)
        _da = pg.evaluate("""() => ({faol: document.getElementById('t-active').textContent.trim(),
            usta: [...document.querySelectorAll('#masterList .master-item')].map(x => { const i = x.querySelector('.master-ism') || x.querySelector('div > div');
              return {ism: i.textContent, title: i.getAttribute('title'), sub: x.innerText.split('\\n').map(s => s.trim()).filter(Boolean),
                      bal: Math.round(i.getBoundingClientRect().height), toshdi: i.scrollWidth > i.clientWidth,
                      uslub: getComputedStyle(i).whiteSpace + '/' + getComputedStyle(i).textOverflow}; }),
            mezon: document.getElementById('masterList').closest('.card').querySelector('.card-head').innerText,
            grafik: window.__grafiklar || []})""")
        _uz = next((u for u in _da["usta"] if u["ism"] == UZUN), {})
        check("B5 Dashboard: «Faol buyurtmalar» 4 ta; reyting — 3 usta, «N ta tayyor buyurtma», mezon «tayyor buyurtmalar summasi bo'yicha»; "
              "uzun ism BIR qatorda (… bilan), to'liq ismi ko'rsatkichda", _da["faol"] == "4 ta"
              and [u["ism"] for u in _da["usta"]] == [UZUN, f"FBo Usta Bir {_n}", f"FBo Usta Uch {_n}"]
              and [u["sub"][2] for u in _da["usta"]] == ["2 ta tayyor buyurtma", "1 ta tayyor buyurtma", "1 ta tayyor buyurtma"]
              and "tayyor buyurtmalar summasi bo'yicha" in _da["mezon"] and _uz.get("title") == UZUN and _uz.get("bal", 99) <= 20
              and _uz.get("uslub") == "nowrap/ellipsis" and "ordersCountChart" in _da["grafik"], _da)
        pg.set_viewport_size({"width": 390, "height": 844})
        pg.wait_for_timeout(300)
        _tel = pg.evaluate("""() => { const i = [...document.querySelectorAll('#masterList .master-ism')].find(x => x.getAttribute('title').startsWith('Abdulazizxon'));
            return i ? {bal: Math.round(i.getBoundingClientRect().height), toshdi: i.scrollWidth > i.clientWidth,
                        summa: Math.round(i.closest('.master-item').lastElementChild.getBoundingClientRect().right)} : null; }""")
        check("B5b telefon 390 px: uzun ism sig'maydi — BIR qatorda, «…» bilan qisqaradi (ilgari 4 qator), summa ekranda",
              _tel and _tel["bal"] <= 20 and _tel["toshdi"] and _tel["summa"] <= 390, _tel)
        pg.set_viewport_size({"width": 1440, "height": 900})
        pg.evaluate("""() => { window.__sekin = (orig => (u, o) => String(u).includes('/api/dashboard/charts')
            ? new Promise(r => setTimeout(r, 900)).then(() => orig(u, o)) : orig(u, o))(window.fetch); window.fetch = window.__sekin; }""")
        del SOROV[:]
        pg.click("#dashYangilaBtn")
        pg.wait_for_timeout(250)
        _yj = pg.evaluate("""() => { const b = document.getElementById('dashYangilaBtn');
            return {aylan: b.classList.contains('yuklanmoqda'), yopiq: b.disabled, yoz: document.getElementById('dashYangilandi').textContent}; }""")
        pg.wait_for_timeout(1800)
        _ys = pg.evaluate("""() => { const b = document.getElementById('dashYangilaBtn');
            return {aylan: b.classList.contains('yuklanmoqda'), yopiq: b.disabled, yoz: document.getElementById('dashYangilandi').textContent}; }""")
        _ss = [u for _, u in SOROV]
        check("B6 «Yangilash»: bosilganda aylanuvchi belgi va «Yangilanmoqda…» (tugma qayta bosilmaydi), tugagach «Yangilandi: SS:DD»; "
              "majburiyatlar bloki va avans so'rovlari ham qayta so'raladi (ilgari — hech narsa ko'rinmasdi, ular yangilanmasdi)",
              _yj == {"aylan": True, "yopiq": True, "yoz": "Yangilanmoqda…"} and not _ys["aylan"] and not _ys["yopiq"]
              and re.fullmatch(r"Yangilandi: \d{2}:\d{2}", _ys["yoz"] or "") and any(u.startswith("/api/dashboard/stats") for u in _ss)
              and any(u.startswith("/api/obligations/status") for u in _ss) and any(u.startswith("/api/admin/pending-advance-requests") for u in _ss),
              (_yj, _ys, _ss))
    except Exception as _e:                # noqa: BLE001
        check("B! Dashboard (A)", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    ctx, pg = kontekst(BOSH)
    try:
        pg.goto(B + "/dashboard", wait_until="networkidle")
        pg.wait_for_timeout(700)
        _db2 = pg.evaluate("""() => { const c = document.getElementById('ordersCountChart'); const y = c.parentElement.querySelector('.grafik-bosh');
            return {kanva: getComputedStyle(c).display, yoz: y ? y.textContent : null, yozKor: y ? getComputedStyle(y).display : null,
                    usta: document.getElementById('masterList').innerText.trim(), grafik: window.__grafiklar || []}; }""")
        check("B7 bo'sh korxona Dashboard: «Buyurtmalar soni» grafigi o'rnida «Hali buyurtma yo'q» (o'q «0 1» chizilmaydi); reyting — «Hali "
              "tayyor buyurtma yo'q»", _db2["kanva"] == "none" and _db2["yoz"] == "Hali buyurtma yo'q" and _db2["yozKor"] != "none"
              and "ordersCountChart" not in _db2["grafik"] and _db2["usta"] == "Hali tayyor buyurtma yo'q", _db2)
    except Exception as _e:                # noqa: BLE001
        check("B! Dashboard (bo'sh korxona)", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ── Hisobotlar ──
    REP_JS = """() => { const c = document.getElementById('mainTrendChart'); const y = c.parentElement.querySelector('.grafik-bosh');
      return {kanva: getComputedStyle(c).display, yoz: y && getComputedStyle(y).display !== 'none' ? y.textContent : null,
              tugma: [...document.querySelectorAll('[data-days]')].map(b => b.textContent.trim()),
              izoh: document.getElementById('filtrIzoh').textContent, trend: document.getElementById('trendDavr').textContent,
              donut: document.getElementById('donutDavr').textContent, reyting: document.getElementById('reytingDavr').textContent,
              jadval: document.getElementById('repDavr').textContent, grafik: (window.__grafiklar || []).slice()}; }"""
    ctx, pg = kontekst(BOSH)
    try:
        pg.goto(B + "/reports", wait_until="networkidle")
        pg.wait_for_timeout(800)
        _r1 = pg.evaluate(REP_JS)
        check("B8 bo'sh korxona Hisobotlar: dinamika o'rnida «Bu davrda hali daromad yoki xarajat yo'q» (o'q «0 0 1 1» yo'q)",
              _r1["kanva"] == "none" and _r1["yoz"] == "Bu davrda hali daromad yoki xarajat yo'q" and "mainTrendChart" not in _r1["grafik"], _r1)
        check("B9 davr filtri: tugmalar «Oxirgi 30 kun / 90 kun / 6 oy / 12 oy» (ilgari «Shu oy», «Yil»); izoh — nimaga qo'llanadi va nima "
              "joriy oy; dinamika — qaysi oylar, «Xarajat tarkibi» — joriy oy, reytinglar — oxirgi N kun, «Ombor» — hozirgi qoldiq",
              _r1["tugma"] == ["Oxirgi 30 kun", "Oxirgi 90 kun", "Oxirgi 6 oy", "Oxirgi 12 oy"]
              and "joriy oy" in _r1["izoh"] and "jadvalga birga" not in _r1["izoh"] and _r1["trend"] == "— " + davr_matni(3)
              and _r1["donut"] == "— " + davr_matni(1) + " (joriy oy)" and _r1["reyting"] == "— oxirgi 90 kun"
              and _r1["jadval"] == "— hozirgi qoldiq", (_r1, davr_matni(3)))
        pg.evaluate("() => setPeriod(30)")
        pg.wait_for_timeout(700)
        _r2 = pg.evaluate(REP_JS)
        check("B10 «Oxirgi 30 kun» — dinamika joriy oy, reytinglar «oxirgi 30 kun»", _r2["trend"] == "— " + davr_matni(1)
              and _r2["reyting"] == "— oxirgi 30 kun", _r2)
        pg.evaluate("() => { window.__msg = []; const _a = window.showMsg; window.showMsg = (t, ty) => { window.__msg.push([String(t), ty]); if (_a) _a(t, ty); }; }")
        del DIALOG[:]
        pg.evaluate("() => exportCSV()")
        pg.wait_for_timeout(200)
        _ex = pg.evaluate("() => ({msg: window.__msg, excel: window.__excel})")
        check("B11 bo'sh jadval — «Excel»: oddiy xabar «Yuklash uchun ma'lumot yo'q» (ilgari xom oyna «Avval ma'lumot yuklanishini kuting»), "
              "fayl yozilmaydi", not DIALOG and _ex["excel"] is None and _ex["msg"] and "Yuklash uchun ma'lumot yo'q" in _ex["msg"][0][0], (DIALOG, _ex))
    except Exception as _e:                # noqa: BLE001
        check("B! Hisobotlar (bo'sh korxona)", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/reports", wait_until="networkidle")
        pg.wait_for_timeout(800)
        _r3 = pg.evaluate(REP_JS)
        check("B12 ma'lumotli korxona: dinamika grafigi chiziladi (yozuv yo'q)", _r3["kanva"] != "none" and _r3["yoz"] is None
              and "mainTrendChart" in _r3["grafik"], _r3)
        VIS = "() => [...document.querySelectorAll('#repBody tr')].filter(t => t.style.display !== 'none').map(t => t.cells[0].textContent.trim())"
        pg.fill("#tableSearch", "gips")
        pg.wait_for_timeout(150)
        _v0 = pg.evaluate(VIS)
        pg.evaluate("() => sortTableBy(2)")
        pg.wait_for_timeout(150)
        _v1 = pg.evaluate(VIS)
        pg.evaluate("() => setPeriod(180)")
        pg.wait_for_timeout(900)
        _v2 = pg.evaluate(VIS)
        pg.evaluate("() => exportCSV()")
        pg.wait_for_timeout(200)
        _e1 = pg.evaluate("() => window.__excel")
        check("B13 qidiruv «gips» — saralashdan va davr almashgandan keyin ham faqat mos qator (ilgari hamma qator qaytardi); «Excel» — faqat "
              "ko'ringan qator", _v0 == _v1 == _v2 == [f"Gips G-1 {_n}"] and _e1 and len(_e1) == 2 and _e1[1][0] == f"Gips G-1 {_n}",
              (_v0, _v1, _v2, _e1))
        pg.fill("#tableSearch", "")
        pg.evaluate("() => filterTable()")
        pg.evaluate("() => exportCSV()")
        pg.wait_for_timeout(200)
        _e2 = pg.evaluate("() => window.__excel") or []
        _q = {r[0]: r for r in _e2[1:]}
        _bosh = _e2[0] if _e2 else []
        _i = {h: k for k, h in enumerate(_bosh)}
        _p20, _p3d, _gp = _q.get(f"20x15 profil {_n}", []), _q.get(f"3D panel qolip {_n}", []), _q.get(f"Gips G-1 {_n}", [])
        check("B14 Excel: nomi raqam bilan boshlangan mahsulot — MATN («20x15 profil», «3D panel qolip»; ilgari 20 va 3); «Qoldiq» — son, "
              "birligi ALOHIDA ustunda («kg», «m²»); narx / qiymat — son",
              _bosh[:4] == ["Nomi", "Kategoriya", "Qoldiq", "Qoldiq birligi"] and "Min. qoldiq birligi" in _bosh
              and _p20 and _p20[0] == f"20x15 profil {_n}" and _p3d and _p3d[0] == f"3D panel qolip {_n}"
              and _gp and _gp[_i["Qoldiq"]] == 630.52 and _gp[_i["Qoldiq birligi"]] == "kg" and _p3d[_i["Qoldiq"]] == 1234.5
              and _p3d[_i["Qoldiq birligi"]] == "m²" and _gp[_i["1 birlik narxi"]] == 2500 and _p20[_i["Jami qiymat"]] == 180000, _e2)
    except Exception as _e:                # noqa: BLE001
        check("B! Hisobotlar (A)", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    check("B15 JS xatosi yo'q", not JS_XATO, JS_XATO)
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
