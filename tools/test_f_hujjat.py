#!/usr/bin/env python3
"""
test_f_hujjat.py — kech120, F BOSQICH 5-qism 2-bo'lagi (HUJJATLAR VA KPI — audit G6-08, G6-12, G6-13 (texnik qismi), G6-14).

NIMA UCHUN KERAK (audit kech114; 2026-10-01 da JORIY kodda qayta tekshirildi — work/f/tekshiruv_kech120.md):
  G6-12  Buyurtma hisobi PDF: birlik «M», «TA», «KG» (yuk xatida «30 metr», hisob-kitobda «30 m»; hisob-kitob varaqasida metrdan
         boshqasi — «ta»), ming ajratgich vergul («900,000»), chegirmasiz buyurtmada «Umumiy jami» va «TO'LOV SUMMASI» — bir xil raqam
         ikki qatorda, «TURI: Mahsulot», shior / «Imzo / Sana» juda och, fayl sarlavhasi «(anonymous)»; kasrli miqdor yaxlitlanardi
         («2.5 m» → «2»).
  G6-13  Yuk xati — chop etilgan kundagi holat: Y-1 (faqat karniz) qayta chop etilsa «BUYURTMA TO'LIQ TOPSHIRILDI», «tugadi».
  G6-14  KPI: karta va jadvalda «Hisoblangan» — ikki xil raqam; «🔴 Qarzdor» (korxona qarzdor); sovg'a 0 da ham «TOP: …»; «+-1 026»;
         Jami qatorida avans minussiz; bonus / kamaytirish oynasida summa ajratgichsiz («20000»).
  G6-08  Hodim kartasi 1440 px da: yozuvlar ustma-ust, «Bu oy avans» har so'zi alohida qatorda, ✕ kartadan chiqadi.
BO'LIMLAR: S — statik; D — ma'lumot; P — PDF matni (pypdf); B — HAQIQIY Chromium (KPI sahifasi).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 135) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium (B), `pypdf` (P).
ISHLATISH: python3 tools/test_f_hujjat.py
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
PG_BAZA = "f_hujjat_test"
_T = tempfile.mkdtemp(prefix="fhuj_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'f_hujjat_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Order, OrderItem, OrderType, OrderStatus, Delivery, DeliveryItem, Master)   # noqa: E402
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


def nb(s):
    return re.sub(r"[ \t]+", " ", str(s or "").replace("\xa0", " ").replace(" ", " "))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PDFS = oqi("pdf_service.py")
DPDF = oqi("delivery_pdf.py")
KPI = oqi("templates/kpi.html")
check("S1 buyurtma hisobi PDF: birlik — umumiy qoida (`birlik_korinish`), summa — `_pul_matni` (bo'shliq), «TURI» yo'q, takror "
      "«TO'LOV SUMMASI» qatori yo'q, sarlavha (title), to'q izoh rangi", "from services import birlik_korinish as _bk136, son_korinish as _sk136" in PDFS
      and "return 'TA' if b == 'dona' else b.upper()" not in PDFS and "def _pul_matni(n)" in PDFS and ':,.0f}", st["table_cell_r"]' not in PDFS
      and 'Paragraph("TURI", st["section_label"])' not in PDFS and "totals_data.insert(1, [" not in PDFS
      and 'title=f"Buyurtma hisobi {order.order_number or order.id}"' in PDFS and 'IZOH_RANG = colors.HexColor("#4B5563")' in PDFS)
check("S2 yuk xati: shu yuk paytidagi holat (`_yuk_holati`), «tugadi» yo'q, birlik — `_birlik` (4 joyda), «chop etilgan kun»",
      "def _yuk_holati(delivery):" in DPDF and '"tugadi"' not in DPDF and DPDF.count("_birlik(") >= 6
      and "u = 'm' if di.unit == 'metr' else 'ta'" not in DPDF and "(chop etilgan kun)" in DPDF)
check("S3 KPI: hodim kartasi ikki qatorda (kompyuterda ham), «To'lanmagan», TOP — sovg'a bo'lsa, `kpiIshora`, «Asosiy hisob», avans "
      "jami minus bilan, oyna summasi — umumiy qoida", ".emp-row{flex-wrap:wrap;row-gap:10px}" in KPI and "🔴 Qarzdor" not in KPI
      and "🔴 To'lanmagan" in KPI and "Number(top.gift_amount) > 0" in KPI and "function kpiIshora(n)" in KPI and "+${fmt(r.kpi_amount)}" not in KPI
      and ">Asosiy hisob</th>" in KPI and '<input type="number" id="arModal-amount"' not in KPI and "narxKorinishi(opts.currentAmount)" in KPI)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Ma'lumot")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "fhuj_admin", "Parol123!"
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, ADMIN, PAROL, UserRole.ADMIN, "FH Admin", company_id=1)
_n = uuid.uuid4().hex[:4]
_p = Project(company_id=1, project_number=f"FH-{_n}", project_name=f"FH Hovli {_n}", client_name="FH Mijoz")
_db.add(_p)
_db.add(Master(company_id=1, name=f"FH Usta {_n}", phone=f"+99890{_n}77"))
_db.commit()
# O1 — chegirmasiz (bitta «TO'LOV SUMMASI»), kasrli profil 2,5 m, dona, termopanel m², loy kg
_o1 = Order(company_id=1, project_id=_p.id, order_number=f"FH-{_n}-1", order_type=OrderType.PRODUCT, status=OrderStatus.NEW,
            total_amount=1125000, agreed_amount=1125000)
# O2 — chegirmali (Umumiy jami 1 000 000 → TO'LOV SUMMASI 900 000)
_o2 = Order(company_id=1, project_id=_p.id, order_number=f"FH-{_n}-2", order_type=OrderType.PRODUCT, status=OrderStatus.NEW,
            total_amount=1000000, agreed_amount=900000)
# O3 — ikki yuk: Y-1 karniz 30 m (oldin), Y-2 panel 10 m (keyin)
_o3 = Order(company_id=1, project_id=_p.id, order_number=f"FH-{_n}-3", order_type=OrderType.PRODUCT, status=OrderStatus.READY,
            total_amount=1800000, agreed_amount=1800000)
# O4 — loy (kg) bitta yukda: hisob-kitob varaqasida ilgari «25 ta»
_o4 = Order(company_id=1, project_id=_p.id, order_number=f"FH-{_n}-4", order_type=OrderType.PRODUCT, status=OrderStatus.READY,
            total_amount=75000, agreed_amount=75000)
_db.add_all([_o1, _o2, _o3, _o4])
_db.commit()
_i = [OrderItem(company_id=1, order_id=_o1.id, name="FH Karniz K-1", category="profil", length=2.5, quantity=1, unit_price=250000,
                total_price=250000, is_coated=False),
      OrderItem(company_id=1, order_id=_o1.id, name="FH Vaza", category="dona", quantity=4, unit_price=50000, total_price=200000,
                is_coated=False),
      OrderItem(company_id=1, order_id=_o1.id, name="FH Termopanel", category="termopanel", quantity=6, unit_price=100000,
                total_price=600000, is_coated=False),
      OrderItem(company_id=1, order_id=_o1.id, name="FH Loy", category="loy_sotish", quantity=25, unit_price=3000, total_price=75000,
                is_coated=False),
      OrderItem(company_id=1, order_id=_o2.id, name="FH Panel P-2", category="dona", quantity=10, unit_price=100000, total_price=1000000,
                is_coated=False),
      OrderItem(company_id=1, order_id=_o3.id, name="FH Karniz K-3", category="profil", length=30, quantity=1, unit_price=1200000,
                total_price=1200000, is_coated=False),
      OrderItem(company_id=1, order_id=_o3.id, name="FH Panel P-3", category="panel", quantity=10, unit_price=60000, total_price=600000,
                is_coated=False),
      OrderItem(company_id=1, order_id=_o4.id, name="FH Loy L-4", category="loy_sotish", quantity=25, unit_price=3000, total_price=75000,
                is_coated=False)]
_db.add_all(_i)
_db.commit()
_hozir = datetime.utcnow()
_y1 = Delivery(order_id=_o3.id, delivery_number=f"FH-{_n}-3/Y-1", delivered_at=_hozir - timedelta(days=2))
_y2 = Delivery(order_id=_o3.id, delivery_number=f"FH-{_n}-3/Y-2", delivered_at=_hozir - timedelta(days=1))
_y4 = Delivery(order_id=_o4.id, delivery_number=f"FH-{_n}-4/Y-1", delivered_at=_hozir - timedelta(days=1))
for _d in (_y1, _y2, _y4):
    if hasattr(Delivery, "company_id"):
        _d.company_id = 1
_db.add_all([_y1, _y2, _y4])
_db.commit()
_di = [DeliveryItem(delivery_id=_y1.id, order_item_id=_i[5].id, quantity=30, unit="metr"),
       DeliveryItem(delivery_id=_y2.id, order_item_id=_i[6].id, quantity=10, unit="metr"),
       DeliveryItem(delivery_id=_y4.id, order_item_id=_i[7].id, quantity=25, unit="kg")]
for _d in _di:
    if hasattr(DeliveryItem, "company_id"):
        _d.company_id = 1
_db.add_all(_di)
_db.commit()
ID = {"o1": _o1.id, "o2": _o2.id, "o3": _o3.id, "o4": _o4.id, "y1": _y1.id, "y2": _y2.id, "y4": _y4.id}
_db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_l = C.post("/login", data={"username": ADMIN, "password": PAROL}, follow_redirects=False).status_code
_tk = datetime.utcnow() + timedelta(hours=5)
_e1 = C.post("/api/employees", json={"name": f"FH Hodim Bir {_n}", "pay_type": "fixed", "fixed_amount": 3000000, "position": "Kesuvchi"})
_e2 = C.post("/api/employees", json={"name": f"FH Hodim Ikki {_n}", "pay_type": "fixed", "fixed_amount": 2000000})
_eid1 = (_e1.json() or {}).get("id") if _e1.status_code == 200 else None
_eid2 = (_e2.json() or {}).get("id") if _e2.status_code == 200 else None
_av = C.post(f"/api/employees/{_eid2}/advance?amount=100000") if _eid2 else None
_bo = C.post(f"/api/employees/{_eid1}/monthly-adjustment?year={_tk.year}&month={_tk.month}&bonus_amount=50000&reduction_amount=80000") if _eid1 else None
check("D0 kirdi; 3 buyurtma (chegirmasiz, chegirmali, ikki yukli), 2 hodim (birida bonus 50 000 va kamaytirish 80 000, birida avans "
      "100 000), usta (sovg'asi 0)", _l == 302 and _eid1 and _eid2 and _av is not None and _av.status_code == 200
      and _bo is not None and _bo.status_code == 200, (_l, _e1.status_code, _e2.status_code, _av and _av.status_code, _bo and _bo.status_code))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PDF matni")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from pypdf import PdfReader                        # noqa: E402


def pdf(url):
    r = C.get(url)
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        return r.status_code, "", None
    rd = PdfReader(io.BytesIO(r.content))
    return 200, nb("\n".join((p.extract_text() or "") for p in rd.pages)), rd.metadata


_k1, _t1, _m1 = pdf(f"/api/orders/{ID['o1']}/pdf")
_qatorlar = [x.strip() for x in _t1.split("\n")]
check("P1 buyurtma hisobi: birlik — «m», «dona», «m²», «kg» (ilgari «M», «TA», «M²», «KG»); kasrli miqdor «2,5» (ilgari «2»)",
      _k1 == 200 and re.search(r"\bdona\b", _t1) and re.search(r"\bkg\b", _t1) and "m²" in _t1 and not re.search(r"\b(TA|KG|M)\b", _t1)
      and re.search(r"\b2,5\b", _t1), _t1[:900])
check("P2 buyurtma hisobi: ming ajratgich — bo'shliq («1 125 000», «250 000»), vergulli «1,125,000» yo'q",
      _k1 == 200 and "1 125 000" in _t1 and "250 000" in _t1 and not re.search(r"\d,\d{3}", _t1), _t1[-600:])
check("P3 chegirmasiz buyurtma: «TO'LOV SUMMASI» — BITTA qator, «Umumiy jami» takrori yo'q; «TURI» yo'q; fayl sarlavhasi «Buyurtma hisobi …»",
      _k1 == 200 and _t1.count("TO'LOV SUMMASI") == 1 and "Umumiy jami" not in _t1 and "TURI" not in _t1
      and _m1 is not None and (_m1.title or "") == f"Buyurtma hisobi FH-{_n}-1", (_t1[-500:], _m1 and _m1.title))
try:
    _oqim = PdfReader(io.BytesIO(C.get(f"/api/orders/{ID['o1']}/pdf").content)).pages[0].get_contents().get_data()
except Exception:                          # noqa: BLE001
    _oqim = b""
_izoh_rg = len(re.findall(rb"\.294118 \.333333 \.388235 rg", _oqim))
_och_rg = len(re.findall(rb"\.741176 \.764706 \.780392 rg", _oqim))
check("P9 «Berdi», «Qabul qildi», «Imzo / Sana» — to'q kulrang (#4B5563, ~7,5:1); juda och #BDC3C7 matn yo'q (chop etilganda ko'rinmasdi)",
      _izoh_rg >= 4 and _och_rg == 0, (_izoh_rg, _och_rg))
_k2, _t2, _ = pdf(f"/api/orders/{ID['o2']}/pdf")
check("P4 chegirmali buyurtma: «Umumiy jami: 1 000 000», chegirma va «TO'LOV SUMMASI: 900 000» (qatorlar avvalgidek)",
      _k2 == 200 and "Umumiy jami" in _t2 and "1 000 000" in _t2 and "900 000" in _t2 and _t2.count("TO'LOV SUMMASI") == 1, _t2[-500:])
_ky1, _ty1, _ = pdf(f"/api/deliveries/{ID['y1']}/pdf")
check("P5 eski yuk xati Y-1 (keyin Y-2 ham topshirilgan): holat — SHU yuk paytidagi («Buyurtma bajarilishi: 75%», «shu yuk xati bo'yicha»; "
      "ilgari «BUYURTMA TO'LIQ TOPSHIRILDI»), «QISMAN YETKAZISH», «Jami bo'yicha 30 / 30», «Qoldi» — «0» (ilgari «tugadi»)",
      _ky1 == 200 and "TO'LIQ TOPSHIRILDI" not in _ty1 and "Buyurtma bajarilishi: 75%" in _ty1 and "shu yuk xati bo'yicha" in _ty1
      and "QISMAN YETKAZISH" in _ty1 and "30 / 30" in _ty1 and "tugadi" not in _ty1, _ty1[:1500])
check("P6 Y-1: «Keyingi yetkazishda kutilayotgan» — panel «10 m» (birlik qoidasi); JAMI summa bo'shliq bilan («1 800 000»); pul holati — "
      "«chop etilgan kun»", _ky1 == 200 and "Keyingi yetkazishda kutilayotgan" in _ty1 and re.search(r"FH Panel P-3\s+10 m\b", _ty1)
      and "1 800 000" in _ty1 and "1,800,000" not in _ty1 and "(chop etilgan kun)" in _ty1 and "30 m" in _ty1 and "30 metr" not in _ty1,
      _ty1[:1800])
_ky2, _ty2, _ = pdf(f"/api/deliveries/{ID['y2']}/pdf")
check("P7 oxirgi yuk xati Y-2 — hozirgi holat: «BUYURTMA TO'LIQ TOPSHIRILDI» (izohsiz), «QISMAN» yo'q",
      _ky2 == 200 and "BUYURTMA TO'LIQ TOPSHIRILDI" in _ty2 and "shu yuk xati bo'yicha" not in _ty2 and "QISMAN" not in _ty2, _ty2[-700:])
_ks, _ts, _ = pdf(f"/api/orders/{ID['o3']}/summary-pdf")
_ks4, _ts4, _ = pdf(f"/api/orders/{ID['o4']}/summary-pdf")
_ky4, _ty4, _ = pdf(f"/api/deliveries/{ID['y4']}/pdf")
check("P8 hisob-kitob varaqasi va yuk xati: birlik — umumiy qoida («30 m», «10 m», loy «25 kg»; ilgari varaqada metrdan boshqasi — "
      "«25 ta»)", _ks == 200 and "30 m" in _ts and "10 m" in _ts and _ks4 == 200 and "25 kg" in _ts4 and "25 ta" not in _ts4
      and _ky4 == 200 and "25 kg" in _ty4, (_ts[:600], _ts4[:600]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Brauzer (HAQIQIY Chromium) — KPI sahifasi")
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


def kontekst(w=1440, h=900):
    ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""))) if "/api/" in q.url else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", ADMIN)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


KARTA_JS = """id => { const r = document.getElementById('emp-fin-' + id).closest('.emp-row'); const q = s => r.querySelector(s).getBoundingClientRect();
  const k = r.getBoundingClientRect(), a = q('.emp-asosiy'), f = q('.emp-fin'), t = q('.emp-tugmalar'), x = r.querySelector('.emp-tugmalar button:last-child').getBoundingClientRect();
  const av = document.getElementById('emp-avans-' + id);
  return {ikkiQator: f.top >= a.bottom - 1, ustma: !(f.right <= a.left || f.left >= a.right || f.bottom <= a.top || f.top >= a.bottom),
          xIchida: x.right <= k.right + 0.5 && x.left >= k.left, avansBal: av && av.textContent ? Math.round(av.getBoundingClientRect().height) : 0,
          avans: av ? av.textContent : '', holat: (document.getElementById('emp-status-' + id) || {}).textContent || '',
          tolangan: document.getElementById('emp-fin-' + id).innerText.replace(/\\s+/g, ' ')}; }"""

if br:
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/kpi", wait_until="networkidle")
        pg.wait_for_timeout(1200)
        _c1 = pg.evaluate(KARTA_JS, _eid1)
        _c2 = pg.evaluate(KARTA_JS, _eid2)
        check("B1 hodim kartasi 1440 px: IKKI qator (To'langan / Qolgan — ism ostida, ustma-ust emas), ✕ karta ichida, «Bu oy avans» bir "
              "qatorda", _c1["ikkiQator"] and not _c1["ustma"] and _c1["xIchida"] and _c2["ikkiQator"] and not _c2["ustma"] and _c2["xIchida"]
              and "avans" in _c2["avans"] and 0 < _c2["avansBal"] <= 20, (_c1, _c2))
        check("B2 holat: to'lanmagan oylik — «🔴 To'lanmagan» (ilgari «Qarzdor» — aslida korxona qarzdor); avansli — «Qisman to'langan»",
              "To'lanmagan" in _c1["holat"] and "Qarzdor" not in _c1["holat"] + _c2["holat"] and "Qisman" in _c2["holat"], (_c1, _c2))
        _top = pg.evaluate("() => document.getElementById('k-top-master').textContent")
        _ish = pg.evaluate("() => [kpiIshora(-1026), kpiIshora(1500), kpiIshora(0)]")
        check("B3 ustalar sovg'asi 0 — «TOP: hali yo'q» (ilgari birinchi usta nomi); KPI ishorasi qiymatga qarab: «−1 026», «+1 500», «0» "
              "(ilgari «+-1 026»)", _top == "hali yo'q" and [nb(x) for x in _ish] == ["−1 026", "+1 500", "0"], (_top, _ish))
        _kc = pg.evaluate("() => document.getElementById('k-emp-calculated').closest('.kpi-card').innerText")
        pg.evaluate("() => loadEmpMonthlyReport()")
        pg.wait_for_timeout(1000)
        _jd = pg.evaluate("""() => { const b = document.getElementById('empMonthlyReport');
            return {sar: [...b.querySelectorAll('thead th')].map(t => t.textContent.trim()), jami: b.querySelector('.kpi-oylik-jami').innerText.replace(/\\s+/g, ' ')}; }""")
        check("B4 «Hisoblangan» — bir ma'noda: karta «bonus va kamaytirish bilan», jadvalda «Asosiy hisob»; Jami — avans minus bilan "
              "(«Avans jami -100 000 so'm»; ilgari minussiz)", "bonus va kamaytirish bilan" in _kc and "Asosiy hisob" in _jd["sar"]
              and "Hisoblangan" not in _jd["sar"] and "Avans jami -100 000 so'm" in nb(_jd["jami"]), (_kc, _jd))
        pg.evaluate(f"() => {{ window.__ar = editEmpBonus({_eid1}, 'FH', {_tk.year}, {_tk.month}, 50000, 'yaxshi'); }}")
        pg.wait_for_timeout(300)
        _v0 = pg.evaluate("() => document.getElementById('arModal-amount').value")
        pg.fill("#arModal-amount", "")
        pg.type("#arModal-amount", "20000")
        _v1 = pg.evaluate("() => document.getElementById('arModal-amount').value")
        del SOROV[:]
        pg.click("#arModal-ok")
        pg.wait_for_timeout(700)
        _ps = [u for m, u in SOROV if m == "POST" and "/monthly-adjustment" in u]
        check("B5 bonus oynasi: joriy summa «50 000», yozilgan «20000» → «20 000» (ilgari ajratgichsiz); saqlashda bonus_amount=20000",
              nb(_v0) == "50 000" and nb(_v1) == "20 000" and len(_ps) == 1 and "bonus_amount=20000&" in _ps[0], (_v0, _v1, _ps))
    except Exception as _e:                # noqa: BLE001
        check("B! KPI ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    check("B6 JS xatosi yo'q", not JS_XATO, JS_XATO)
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
