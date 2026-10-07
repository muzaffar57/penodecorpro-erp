#!/usr/bin/env python3
"""
test_f_buyurtma.py — kech120, F BOSQICH 4-qism (BUYURTMALAR VA LOYIHALAR — audit G2 qolgan bandlari).

NIMA UCHUN KERAK (audit kech114; 2026-10-01 da JORIY kodda qayta tekshirildi — work/f/tekshiruv_kech120.md):
  G2-08  Namuna matni rangi berilmagan (brauzer #757575 — yorliqdan to'q, qiymatga yaqin): «Karniz M-06», «Karimov Botir» yozib qo'yilgandek.
  G2-09  Saqlashda xatolar bittadan, turli joyda («Loyiha tanlang!» ekran tepasida 4 s); «Yetkazib berish muddati» (maydon — «Topshirish
         sanasi»); nomsiz detal JIM tashlanadi; server xatosi «Xato: {…}»; loy maydoni doim oltin ramkada; majburiy belgisi yo'q.
  G2-10  Profil tanlansa «"Miqdor" (dona) bo'yicha hisoblanadi» — aslida uzunlik.
  G2-11  «Detal #1 — nomi kiritilmagan» — ekrandagi o'rin raqami (tepadagi «Detal #2» ni «#1» der edi), forma ochilishi bilanoq.
  G2-12  Buyurtma amallari xulosa ostida (1440 × 900 da faqat «Pindan olish» ko'rinardi), «Pin» birinchi; detallar yopiq; tayyor buyurtmada
         «Tahrirlash» izohsiz yo'qoladi.
  G2-14  Loyiha qarzi butun millionga yaxlitlanib («🔴 0 mln» — 384 000), faqat 2+ buyurtmali loyihada.
  G2-16  Ikki summa paneli («Shu buyurtma» — kelishilgan, «Buyurtma hisob-kitobi» — JAMI chegirmasiz); 0 qarz qizil.
  G2-19  Loyiha kartasidagi chiziq (bajarilish) «to'langan» yozuvi ostida; «Yetkazish» faqat loyiha «Yakunlangan» bo'lsa.
  G2-22  Bo'sh korxonada «avval loyiha» aytilmaydi, formadan loyiha yaratish yo'li yo'q; Loyihalar — bo'sh holat va 8 ta ishlamaydigan tab.
  G2-23  `--border-strong` hech qayerda aniqlanmagan — yuklash joyi ramkasiz, «JPG» kesiladi.
  G2-24  «Timeline», «SMS uchun».
BO'LIMLAR: S — statik; J — `|qisqa_summa` (Python) = `qisqaSumma` (brauzer); A — API (`/api/projects/{id}/topshirish`); R — server chizgan
  Buyurtmalar ro'yxati; B — HAQIQIY Chromium (Buyurtmalar — yangi forma, saqlash tekshiruvi, buyurtma ko'rinishi; Loyihalar; bo'sh korxona).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 133) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium (B), Node (J).
ISHLATISH: python3 tools/test_f_buyurtma.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import uuid
import socket
import tempfile
import threading
import contextlib
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "f_buyurtma_test"
_T = tempfile.mkdtemp(prefix="fbuy_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'f_buyurtma_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Order, OrderItem, OrderType, OrderStatus, Delivery, DeliveryItem)   # noqa: E402
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


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAIN = oqi("main.py")
ORD = oqi("templates/orders.html")
PRJ = oqi("templates/projects.html")
CSS = oqi("static/style.css")
check("S1 Buyurtmalar: bitta kamchiliklar ro'yxati (`buyurtmaUmumiyKamchiliklar`), detal yorlig'i raqami, «Topshirish sanasi», server sababi "
      "oddiy gap, loy maydoni oltin ramkasiz, majburiy belgilar, profil — «Uzunlik»",
      "function buyurtmaUmumiyKamchiliklar(items)" in ORD and "function detalYorligi(row, idx)" in ORD
      and "Topshirish sanasi kiritilmagan" in ORD and "Yetkazib berish muddati" not in ORD and "JSON.stringify(e.detail)" not in ORD
      and "showMsg('Loyiha tanlang!'" not in ORD and 'style="border-color:var(--gold)" aria-describedby="loy_kg_izoh"' not in ORD
      and ORD.count('<span class="majburiy"') >= 3 and "«Uzunlik» (m) bo'yicha hisoblanadi" in ORD
      and "const umumiy134 = buyurtmaUmumiyKamchiliklar(items);" in ORD and "const issues = buyurtmaUmumiyKamchiliklar(items);" in ORD)
check("S2 Buyurtmalar: loyiha qarzi `|qisqa_summa` (har loyihada), bitta hisob-kitob paneli, amallar tepada, detallar ochiq, bo'sh holat, "
      "«+ Yangi loyiha yaratish…», yuklash joyi", "🔴 Qarz: {{ g.debt|qisqa_summa }}" in ORD and "{% if g.orders|length > 1 %}" not in ORD
      and ORD.count('id="liveStats"') == 1 and 'id="liveTotal" style="display:none;border-left' not in ORD and "#sumBody > .yb-amallar{order:-1" in ORD
      and 'style="padding:12px;display:none" id="odBody"' not in ORD and "Hali loyiha yo'q" in ORD and 'value="__yangi"' in ORD
      and ".dropzone{display:block;" in ORD and 'id="btn-edit-izoh"' in ORD)
check("S3 Loyihalar: «Tarix», «Telegram xabari uchun», bo'sh holat, `?yangi=1`, «Bajarilgan» yozuvi, «Yetkazish» — buyurtmalardan; "
      "style.css — `--border-strong`, namuna rangi; server — `/topshirish`, `qisqa_summa`",
      ">Tarix</button>" in PRJ and ">Timeline<" not in PRJ and "SMS uchun" not in PRJ and "Birinchi loyihani yaratish" in PRJ
      and "p.get('yangi') !== '1'" in PRJ and "'🏭 Bajarilgan '" in PRJ and "/topshirish`" in PRJ
      and "--border-strong:" in CSS and "::placeholder { color: var(--placeholder); opacity: 1; }" in CSS
      and '@app.get("/api/projects/{project_id}/topshirish")' in MAIN and 'templates.env.filters["qisqa_summa"]' in MAIN)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. Qisqa summa — Python = brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
NAMUNA = [0, 384000, 764000, 999499, 999500, 1234567, -200, 999.4, 999.5, -0.4, 2500, 1500, 1250000, 1050000, -2500, 0.5, -0.5, 15500000]
_f = main.templates.env.filters.get("qisqa_summa") or (lambda x: str(x))
_py = [_f(x) for x in NAMUNA]
_base = oqi("templates/base.html")
_i = _base.find("function qisqaSumma(n)")
_k = _base.find("\n}", _i) + 2
try:
    _jsn = json.loads(subprocess.run(["node", "-e", _base[_i:_k] + ";console.log(JSON.stringify(" + json.dumps(NAMUNA) + ".map(qisqaSumma)))"],
                                     capture_output=True, text=True, timeout=60).stdout or "[]")
except Exception as _e:                    # noqa: BLE001
    _jsn = [str(_e)]
check("J1 `|qisqa_summa` = `qisqaSumma` (18 namuna, teng bo'lganda yuqoriga: 2 500 → «3 ming», 1 250 000 → «1,3 mln»)",
      _py == _jsn and _py[1] == "384 ming" and _py[10] == "3 ming" and _py[12] == "1,3 mln", {"py": _py, "js": _jsn})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Ma'lumot")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, BOSH, PAROL = "fbuy_admin", "fbuy_bosh", "Parol123!"
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="FB B korxona", code="FB-B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, ADMIN, PAROL, UserRole.ADMIN, "FB Admin", company_id=1)
    auth.create_user(_db, BOSH, PAROL, UserRole.ADMIN, "FB Bo'sh", company_id=2)
_n = uuid.uuid4().hex[:4]
_p1 = Project(company_id=1, project_number=f"FB-{_n}-1", project_name=f"FB Hovli {_n}", client_name="FB Mijoz Bir")
_p2 = Project(company_id=1, project_number=f"FB-{_n}-2", project_name=f"FB Dacha {_n}", client_name="FB Mijoz Ikki")
_db.add_all([_p1, _p2])
_db.commit()
# P1: ikki buyurtma — biri to'liq topshirilgan (READY), biri jarayonda; P2: bitta buyurtma, qarzi 384 000
_o1 = Order(company_id=1, project_id=_p1.id, order_number=f"FB-{_n}-1-1", order_type=OrderType.PRODUCT, status=OrderStatus.READY,
            total_amount=200000, agreed_amount=200000)
_o2 = Order(company_id=1, project_id=_p1.id, order_number=f"FB-{_n}-1-2", order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS,
            total_amount=100000, agreed_amount=100000)
_o3 = Order(company_id=1, project_id=_p2.id, order_number=f"FB-{_n}-2-1", order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS,
            total_amount=384000, agreed_amount=384000)
_db.add_all([_o1, _o2, _o3])
_db.commit()
_i1 = OrderItem(company_id=1, order_id=_o1.id, name="Karniz K-1", category="dona", quantity=4, unit_price=50000, total_price=200000)
_i2 = OrderItem(company_id=1, order_id=_o2.id, name="Karniz K-2", category="dona", quantity=2, unit_price=50000, total_price=100000)
_i3 = OrderItem(company_id=1, order_id=_o3.id, name="Panel P-3", category="dona", quantity=8, unit_price=48000, total_price=384000)
_db.add_all([_i1, _i2, _i3])
_db.commit()
_dv = Delivery(order_id=_o1.id, delivery_number=f"FB-{_n}-1-1/Y-1")
if hasattr(Delivery, "company_id"):
    _dv.company_id = 1
_db.add(_dv)
_db.commit()
_di = DeliveryItem(delivery_id=_dv.id, order_item_id=_i1.id, quantity=4, unit="dona")
if hasattr(DeliveryItem, "company_id"):
    _di.company_id = 1
_db.add(_di)
_db.commit()
ID = {"p1": _p1.id, "p2": _p2.id, "o1": _o1.id, "o2": _o2.id, "o3": _o3.id}
_db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_l = C.post("/login", data={"username": ADMIN, "password": PAROL}, follow_redirects=False).status_code
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB.post("/login", data={"username": BOSH, "password": PAROL}, follow_redirects=False)
check("D0 kirdi; 2 loyiha (biri ikki buyurtmali — biri to'liq topshirilgan; biri bitta buyurtmali, qarzi 384 000), bo'sh korxona",
      _l == 302 and all(ID.values()), ID)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_t1 = C.get(f"/api/projects/{ID['p1']}/topshirish")
_t2 = C.get(f"/api/projects/{ID['p2']}/topshirish")
_t3 = CB.get(f"/api/projects/{ID['p1']}/topshirish")
check("A1 `/api/projects/{id}/topshirish`: P1 — 1 / 2 to'liq topshirilgan, P2 — 0 / 1; boshqa korxona — 404",
      _t1.status_code == 200 and js(_t1) == {"jami": 2, "topshirilgan": 1} and js(_t2) == {"jami": 1, "topshirilgan": 0}
      and _t3.status_code == 404, (js(_t1), js(_t2), _t3.status_code))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Server chizgan Buyurtmalar ro'yxati")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_h = C.get("/orders").text
_qarz = [nb(x) for x in re.findall(r'<div class="proj-debt"[^>]*>(.*?)</div>', _h)]
check("R1 loyiha qarzi — «🔴 Qarz: 384 ming» (bitta buyurtmali loyihada ham; ilgari «🔴 0 mln» va faqat 2+ buyurtmada)",
      "🔴 Qarz: 384 ming" in _qarz and not any("mln" in q and q.startswith("🔴 0") for q in _qarz), _qarz)
_hb = CB.get("/orders").text
check("R2 bo'sh korxona Buyurtmalar: «Hali loyiha yo'q», «avval loyiha qo'shing», «+ Loyiha yaratish» → /projects?yangi=1",
      "Hali loyiha yo'q" in _hb and "avval loyiha qo'shing" in _hb and 'href="/projects?yangi=1"' in _hb, None)

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


def kontekst(user=ADMIN, w=1440, h=900):
    ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ")
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


XABAR_ILGAK = "() => { window.__msg = []; const _a = window.showMsg; window.showMsg = (t, ty) => { window.__msg.push([String(t), ty]); if (_a) _a(t, ty); }; }"

if br:
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/orders", wait_until="networkidle")
        pg.wait_for_timeout(400)
        pg.evaluate(XABAR_ILGAK)
        pg.evaluate("() => showNewForm()")
        pg.wait_for_timeout(500)
        _ph = pg.evaluate("""() => { const n = document.querySelector('.detal .i-name');
            return {ph: n.getAttribute('placeholder'), rang: getComputedStyle(n, '::placeholder').color, qiymat: getComputedStyle(n).color,
                    loy: getComputedStyle(document.getElementById('loy_kg')).borderTopColor,
                    yangi: [...document.getElementById('project_id').options].map(o => o.textContent).filter(t => t.includes('Yangi loyiha')),
                    panel: (document.querySelector('#liveStats h3') || {}).textContent || '', ichida: !!document.querySelector('#liveStats #liveTotal'),
                    paneller: document.querySelectorAll('#liveTotal.card').length}; }""")
        check("B1 yangi forma: namuna «Masalan: Karniz M-06» och kulrang (rgb(161, 164, 173) — qiymat rangidan farqli), loy maydoni oltin "
              "ramkasiz, loyiha ro'yxatida «+ Yangi loyiha yaratish…», BITTA «Buyurtma hisob-kitobi» paneli",
              _ph["ph"] == "Masalan: Karniz M-06" and _ph["rang"] == "rgb(161, 164, 173)" and _ph["rang"] != _ph["qiymat"]
              and _ph["loy"] != "rgb(185, 120, 63)" and _ph["yangi"] == ["+ Yangi loyiha yaratish…"] and "Buyurtma hisob-kitobi" in _ph["panel"]
              and _ph["ichida"] and _ph["paneller"] == 0, _ph)
        _pr = pg.evaluate("() => (document.querySelector('.detal .type-confirm-text') || {}).textContent || ''")
        pg.evaluate("() => { const r = document.querySelector('.detal'); selectTypeOpt(r.querySelector('.type-opt[data-value=profil]'), 'profil'); }")
        _pr = pg.evaluate("() => document.querySelector('.detal .type-confirm-text').textContent")
        check("B2 profil tanlansa — ««Uzunlik» (m) bo'yicha hisoblanadi» (ilgari «Miqdor (dona)»)", "«Uzunlik» (m) bo'yicha hisoblanadi" in _pr, _pr)
        # ikkinchi detal — tepada «Detal #2»; faqat unga o'lcham yoziladi, nomsiz
        pg.evaluate("() => addItem()")
        pg.wait_for_timeout(200)
        _bosh = pg.evaluate("() => document.getElementById('liveTotalBody').innerText")
        pg.evaluate("""() => { const r = [...document.querySelectorAll('.detal')].find(x => x.querySelector('.detal-badge').textContent.trim() === 'Detal #2');
                              const h = r.querySelector('.i-h'); h.value = '12'; h.dispatchEvent(new Event('input', {bubbles: true})); }""")
        pg.wait_for_timeout(200)
        _ogoh = pg.evaluate("() => document.getElementById('liveTotalBody').innerText")
        check("B3 ogohlantirish: hech narsa yozilmagan detallar uchun YO'Q; o'lcham yozilgan nomsiz detal — «Detal #2 — nomi kiritilmagan» "
              "(yorlig'idagi raqam; ilgari ekrandagi o'rin «#1»)", "nomi kiritilmagan" not in _bosh
              and "Detal #2 — nomi kiritilmagan" in _ogoh and "Detal #1 — nomi" not in _ogoh, (_bosh, _ogoh))
        del SOROV[:]
        pg.evaluate("() => saveOrder(false)")
        pg.wait_for_timeout(400)
        _val = pg.evaluate("""() => ({kor: getComputedStyle(document.getElementById('validationModal')).display,
                                     q: [...document.querySelectorAll('#validationList .val-item')].map(x => x.innerText.trim())})""")
        check("B4 saqlash — BARCHA kamchiliklar bitta ro'yxatda: «Loyiha tanlanmagan», «Detal #2 — nomi kiritilmagan (nomsiz detal saqlanmaydi)», "
              "«Topshirish sanasi kiritilmagan»; so'rov yo'q", _val["kor"] == "flex" and "Loyiha tanlanmagan" in _val["q"]
              and "Detal #2 — nomi kiritilmagan (nomsiz detal saqlanmaydi)" in _val["q"] and "Topshirish sanasi kiritilmagan" in _val["q"]
              and not any(x[0] == "POST" and x[1].startswith("/api/orders") for x in SOROV), _val)
        pg.evaluate("() => closeValidationModal()")
        _qz = pg.evaluate("() => ({t: document.getElementById('ls-debt').textContent, red: document.getElementById('ls-debt').classList.contains('red')})")
        check("B5 qarz 0 — kulrang (qizil emas)", _qz["red"] is False and nb(_qz["t"]).startswith("0"), _qz)
        # loyiha tanlovi — «+ Yangi loyiha»
        pg.select_option("#project_id", "__yangi")
        pg.wait_for_function("() => { const m = document.getElementById('ccModal'); return m && getComputedStyle(m).display !== 'none'; }")
        _cm = pg.evaluate("() => document.getElementById('ccModalMessage').textContent")
        pg.click("#ccModalCancel")
        pg.wait_for_timeout(200)
        check("B6 «+ Yangi loyiha yaratish…» — tasdiq (qoralama saqlanadi, Loyihalar sahifasi); «Qolish» — tanlov bo'shaydi, sahifa o'sha",
              "Loyihalar sahifasiga o'tilsinmi?" in _cm and pg.evaluate("() => document.getElementById('project_id').value") == ""
              and pg.url.startswith(B + "/orders"), (_cm, pg.url))
        # server xatosi — oddiy gap
        pg.route(re.compile(r".*/api/orders(\?.*)?$"), lambda route: route.fulfill(status=400, content_type="application/json",
                                                                                     body=json.dumps({"detail": "Sinov sababi: narx noto'g'ri"}))
                 if route.request.method == "POST" else route.continue_())
        pg.evaluate("() => { window.__msg = []; submitOrderRequest({project_id: 1, items: []}, false, 0, 'naqd', false); }")
        pg.wait_for_timeout(500)
        _m = pg.evaluate("() => window.__msg")
        check("B7 server rad etsa — sababi oddiy gap («❌ Sinov sababi: …», ilgari «Xato: {…}»)",
              any(m[0] == "❌ Sinov sababi: narx noto'g'ri" for m in _m) and not any("{" in m[0] for m in _m), _m)
        pg.unroute(re.compile(r".*/api/orders(\?.*)?$"))
        # buyurtma ko'rinishi — amallar tepada, detallar ochiq, tayyorda izoh
        pg.goto(B + f"/orders?order={ID['o1']}", wait_until="networkidle")
        pg.wait_for_timeout(900)
        _ok = pg.evaluate("""() => { const a = document.querySelector('#sumBody > .yb-amallar'), n = document.getElementById('s-num');
            const t = [...a.children].filter(x => x.offsetParent).map(x => x.id || x.className);
            return {amal_tepada: a.getBoundingClientRect().top < n.getBoundingClientRect().top, tartib: t,
                    izoh: getComputedStyle(document.getElementById('btn-edit-izoh')).display, tahrir: getComputedStyle(document.getElementById('btn-edit')).display,
                    detallar: getComputedStyle(document.getElementById('odBody')).display,
                    ekranda: document.getElementById('btn-pdf').getBoundingClientRect().bottom <= innerHeight}; }""")
        check("B8 buyurtma ko'rinishi: AMALLAR xulosaning tepasida (PDF 1440 × 900 ekranda), «O'chirish» oxirida, «Pin» undan oldin; detallar ochiq; "
              "tayyor buyurtmada «Tahrirlash» o'rnida izoh", _ok["amal_tepada"] and _ok["ekranda"] and _ok["tartib"][-1] == "btn-delete"
              and _ok["tartib"].index("btn-pin") > _ok["tartib"].index("btn-pdf") and _ok["izoh"] == "block" and _ok["tahrir"] == "none"
              and _ok["detallar"] != "none", _ok)
        _dz = pg.evaluate("""() => { const d = document.querySelector('.dropzone'); const s = getComputedStyle(d);
            return {disp: s.display, uslub: s.borderTopStyle, rang: s.borderTopColor, belgi: !!d.querySelector('.ti-upload')}; }""")
        check("B9 fayl yuklash joyi — blok, uzuq chiziqli ramka (`--border-strong` — rgb(207, 197, 184)), yuklash belgisi",
              _dz == {"disp": "block", "uslub": "dashed", "rang": "rgb(207, 197, 184)", "belgi": True}, _dz)
        # Loyihalar
        pg.goto(B + "/projects", wait_until="networkidle")
        pg.wait_for_timeout(800)
        _pj = pg.evaluate(f"""() => ({{baj: (document.getElementById('pbaj-{ID['p1']}') || {{}}).textContent || '',
            tab: [...document.querySelectorAll('.tab-btn')].map(b => b.textContent.trim())}})""")
        pg.evaluate(f"() => document.querySelector('.proj-card[data-id=\"{ID['p1']}\"]').click()")
        pg.wait_for_function("() => { const e = document.getElementById('sp-yetkazish'); return e && e.textContent !== '…'; }")
        _sp = pg.evaluate("() => document.getElementById('sp-yetkazish').textContent")
        check("B10 Loyihalar: kartada «🏭 Bajarilgan 50%», tab «Tarix» (Timeline emas), holat panelida «Yetkazish — 1/2 topshirildi» "
              "(ilgari loyiha yakunlanmaguncha «Kutilmoqda»)", _pj["baj"] == "🏭 Bajarilgan 50%" and "Tarix" in _pj["tab"] and "Timeline" not in _pj["tab"]
              and _sp == "1/2 topshirildi", (_pj, _sp))
    except Exception as _e:                # noqa: BLE001
        check("B! Buyurtmalar / Loyihalar ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    ctx, pg = kontekst(BOSH)
    try:
        pg.goto(B + "/projects", wait_until="networkidle")
        pg.wait_for_timeout(400)
        _eb = pg.evaluate("""() => ({m: (document.querySelector('.proj-bosh') || {}).innerText || '',
                                     detal: getComputedStyle(document.getElementById('projDetail')).display})""")
        pg.goto(B + "/projects?yangi=1", wait_until="networkidle")
        pg.wait_for_timeout(400)
        _ym = pg.evaluate("() => ({oyna: getComputedStyle(document.getElementById('addModal')).display, url: location.search})")
        check("B11 bo'sh korxona Loyihalar: «Hali loyiha yo'q» va «+ Birinchi loyihani yaratish» (8 ta bo'sh tab ko'rinmaydi); `?yangi=1` — "
              "yangi loyiha oynasi ochiladi, manzil tozalanadi", "Hali loyiha yo'q" in _eb["m"] and "Birinchi loyihani yaratish" in _eb["m"]
              and _eb["detal"] == "none" and _ym == {"oyna": "flex", "url": ""}, (_eb, _ym))
    except Exception as _e:                # noqa: BLE001
        check("B! bo'sh korxona ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    check("B12 JS xatosi yo'q", not JS_XATO, JS_XATO)
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
