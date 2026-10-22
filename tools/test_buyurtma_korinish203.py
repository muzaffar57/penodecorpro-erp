#!/usr/bin/env python3
"""
test_buyurtma_korinish203.py — kech154 (zip 203 «Buyurtmalar ko'rinishi»; EGASI SO'ROVI 22.10 06:37, TANLOVLARI: «B · Toza kartochkalar»,
ro'yxatda «1 · Qalin ramka + OCHIQ», filtr «F1 · Teng kataklar»): Buyurtmalar oynasida ochilgan buyurtma aniq ko'rinadi, ro'yxat tartibli.
FAQAT KO'RINISH — hisob-kitob, filtr, qidiruv, tanlovni tiklash avvalgidek.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k203/olchov203.py`, zip 202 kodi, haqiqiy Chromium):
  * hodimlar: «buyurtmani bosib ochsak ham ochilgani sezilmaydi» — qator holat rangi INLINE `style` edi va tanlov uslubini bosib ketardi:
    muddati o'tgan qatorda tanlanganda faqat fon #FFFFFF → #FDF8F0; qarzli tugagan qatorda pushti fon o'zgarmasdi (faqat 3 px chiziq);
    ustuvor ro'yxatdagi nusxa tanlanmasdi; o'rta ustunda birinchi «Yetkazish», qaysi buyurtma ochilgani yozilmagan;
  * «ro'yxat tartibsiz» — har qator har xil (fon / chiziq / 3–5 qator emoji yozuv), filtr tugmalari har xil enda 3 qatorga notekis.
BO'LIMLAR:
  S — manba (`templates/orders.html`): qator va loyiha guruhida holat rangi INLINE emas; qatorning `data-*` / `onclick` (filtr, qidiruv,
      tanlov shulardan) o'sha; `selectOrder` ikkala nusxani tanlaydi va sarlavhani to'ldiradi; sarlavha → tarkib → Yetkazish tartibi;
      bo'lim sarlavhalari klass bilan.
  D — HAQIQIY Chromium (Playwright) + lokal server, ma'lumot API orqali (muddati o'tgan qarzli qisman topshirilgan, bugungi, to'langan
      tugagan, qarzli tugagan, qoralama, ustuvor (pin) muddati o'tgan): har turdagi qator tanlanganda — 3 px oltin ramka, och oltin fon,
      «▶ OCHIQ» yorlig'i (oldin yo'q); ikkinchi nusxa ham; o'rtada sarlavha (raqam, holat, loyiha · mijoz · telefon; yonadi; surilganda
      tepada); filtr — 2 ustun, bir xil en, sonlar va filtrlash avvalgidek; belgilar (Muddati o'tgan, Qarz, To'langan, Topshirildi);
      hisob-kitob paneli avvalgidek; tungi rejimda kontrast; telefon (390 px) — xulosa sarlavhasida katta raqam, yon tomonga surilmaydi;
      qayta yuklanganda tanlov tiklanadi; JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. Asl kodga (zip 202) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_buyurtma_korinish203.py
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

TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k203_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k203.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "PG_URL"):
    os.environ.pop(_k, None)

YORLIQ = "[TF1] " if TF else ""
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
        if callable(detail):
            try:
                detail = detail()
            except Exception as e:         # noqa: BLE001
                detail = f"{type(e).__name__}: {e}"
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


def rgb(s):
    m = re.findall(r"[\d.]+", s or "")
    return tuple(float(x) for x in m[:3]) if len(m) >= 3 else None


def _lum(c):
    def k(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2])


def kontrast(a, b):
    if not a or not b:
        return 0
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ORD = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_qb = ORD[ORD.find("{% for o in g.orders %}"):ORD.find("{% endfor %}", ORD.find("{% for o in g.orders %}"))]
_pin = ORD[ORD.find("function renderPinnedOrders(rows)"):ORD.find("async function toggleOrderPin(")]
_gr = ORD[ORD.find("{% for g in grouped %}"):ORD.find("<!-- Loyiha sarlavhasi -->")]
check("S1 holat rangi INLINE emas: buyurtma qatori, ustuvor (pin) qatori, loyiha guruhi — `border-left` / fon `style` da yo'q, `data-urgency` bor",
      _qb and _pin and _gr and "border-left:3px" not in _qb and "row_bg" not in _qb and "urgency_border" not in _qb
      and "urgencyBorder" not in _pin and "border-left:3px" not in _pin and 'data-urgency="${urg}"' in _pin
      and "border-left:3px" not in _gr and 'data-urgency="{{ g_urgency }}"' in _gr and 'data-urgency="{{ urgency }}"' in _qb,
      (len(_qb), len(_pin), len(_gr)))
_DATA = ("data-num=", "data-client=", "data-project=", "data-status=", "data-total=", "data-master=", "data-date=", "data-project-id=",
         "data-order-id=", "data-pinned=", "data-urgency=", "data-qarz=", "data-phone=", "data-items=")
check("S2 qator ma'lumoti o'sha (filtr / qidiruv / tanlovni tiklash shulardan): `id`, `onclick`, 14 ta `data-*`; filtr — 6 tugma "
      "(`data-f`, `royxatFiltrla`, `.f-son`)",
      'id="oi-{{ o.id }}" onclick="selectOrder({{ o.id }}, this)"' in _qb and all(a in _qb for a in _DATA)
      and all(f'data-f="{f}"' in ORD and f"royxatFiltrla('{f}')" in ORD for f in ("hammasi", "otgan", "bugun", "jarayonda", "qarz", "tugagan"))
      and ORD.count('<span class="f-son"></span>') >= 6)
_so = ORD[ORD.find("function selectOrder(id, el)"):]
_so = _so[:_so.find("\nfunction ", 10)]
check("S3 `selectOrder`: shu buyurtmaning IKKALA nusxasi tanlanadi (`data-order-id`), sarlavha `ochilganSarlavha` bilan to'ldiriladi; "
      "eski `od-num` yo'q",
      'document.querySelectorAll(`.ord-item[data-order-id="${id}"]`).forEach(i => i.classList.add(\'active\'))' in _so
      and "ochilganSarlavha(d, statusEl.innerHTML)" in _so and "od-num" not in ORD and "function ochilganSarlavha(d, holatHtml)" in ORD)
_iS, _iT, _iY = ORD.find('id="odSarlavha"'), ORD.find('id="odBody"'), ORD.find("<!-- YETKAZISH BO'LIMI -->")
check("S4 o'rta ustun tartibi: ochilgan buyurtma sarlavhasi → «Buyurtma tarkibi» → Yetkazish",
      -1 < _iS < _iT < _iY and "Buyurtma tarkibi</h3>" in ORD, (_iS, _iT, _iY))
check("S5 ro'yxat bo'lim sarlavhalari (Ustuvor, So'nggi 90 kun, Barchasi) — `ro-bolim` klassi (inline uslub emas)",
      '<div class="ro-bolim"><span>⭐ Ustuvor buyurtmalar</span>' in ORD and ORD.count('<div class="ro-bolim">') == 2
      and ORD.count('<div class="ro-bolim ogoh">') == 1 and "background:var(--gold-tint);font-size:12px;font-weight:700" not in ORD)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# tayyorgarlik — ma'lumot API orqali (xodim bosadigan amallar)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bosh = io.StringIO()
with contextlib.redirect_stdout(_bosh):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k203_a", PAROL, UserRole.ADMIN, "K203 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K203 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P1 = Project(company_id=1, client_name="Aziz K203", project_name="Yunusobod K203", client_phone="+998901112233", total_budget=0, total_paid=0)
P2 = Project(company_id=1, client_name="Dilnoza K203", project_name="Chilonzor K203", client_phone="+998935554411", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K203 Usta", phone="+998900002030")
s.add_all([PENO, P1, P2, US])
s.commit()
ID = {"PENO": PENO.id, "P1": P1.id, "P2": P2.id, "US": US.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lg = C.post("/login", data={"username": "k203_a", "password": PAROL}, follow_redirects=False)
TK = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).date()


def kun(n):
    return (TK + datetime.timedelta(days=n)).isoformat()


def buyurtma(pid, muddat, miqdor, narx, qoralama=False):
    tana = {"project_id": pid, "order_type": "product", "recipe_id": None, "master_id": ID["US"], "deadline": muddat, "is_draft": qoralama,
            "base_price": 600000, "loy_kg": None,
            "items": [{"name": "K203 panel", "category": "panel", "width": 60, "thickness": 5, "length": 0, "quantity": miqdor,
                       "unit_price": narx, "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}]}
    r = C.post("/api/orders", json=tana)
    if r.status_code == 409:
        r = C.post("/api/orders?confirm_shortage=true", json=tana)
    return (r.json() or {}).get("id") if r.status_code == 200 else None


def tolov(oid, summa, tur="partial"):
    return C.post("/api/payments", json={"order_id": oid, "amount": summa, "payment_type": tur, "payment_method": "naqd", "notes": "K203"})


def topshir(oid, ulush):
    h = ((C.get(f"/api/orders/{oid}/delivery-status").json() or {}).get("items")) or []
    items = [{"order_item_id": x["id"], "quantity": round(x["remaining"] * ulush, 2)} for x in h if x.get("remaining", 0) > 0.0001]
    return C.post("/api/deliveries", json={"order_id": oid, "items": items, "received_by": "Qabul K203", "notes": "",
                                           "transport_carrier": "", "transport_cost": 0, "transport_payer": "client"})


O = {}
O["otgan"] = buyurtma(ID["P1"], kun(-4), 20, 22000)            # 440 000 — muddati o'tgan, qisman to'langan, yarmi topshirilgan
O["bugun"] = buyurtma(ID["P1"], kun(0), 10, 15000)             # bugun muddati
O["tolangan"] = buyurtma(ID["P1"], kun(5), 12, 25000)          # to'liq to'langan, topshirilgan, «Tayyor»
O["qarzli"] = buyurtma(ID["P2"], kun(6), 15, 20000)            # topshirilgan, «Tayyor», qarzi bor
O["qoralama"] = buyurtma(ID["P2"], kun(9), 8, 18000, qoralama=True)
O["pin"] = buyurtma(ID["P2"], kun(-2), 6, 30000)               # muddati o'tgan, ustuvor
_am = []
if all(O.values()):
    _am.append(tolov(O["otgan"], 200000, "zaklat").status_code)
    _am.append(topshir(O["otgan"], 0.5).status_code)
    _am.append(tolov(O["tolangan"], 300000, "final").status_code)
    _am.append(topshir(O["tolangan"], 1).status_code)
    _am.append(C.post(f"/api/orders/{O['tolangan']}/ready").status_code)
    _am.append(topshir(O["qarzli"], 1).status_code)
    _am.append(tolov(O["qarzli"], 100000).status_code)
    _am.append(C.post(f"/api/orders/{O['qarzli']}/ready").status_code)
    _am.append(C.post(f"/api/orders/{O['pin']}/pin").status_code)
INFO = {k: (C.get(f"/api/orders/{v}").json() if v else {}) for k, v in O.items()}
NUM = {k: v.get("order_number") for k, v in INFO.items()}
check("T0 fikstura: kirish, 6 buyurtma, to'lov / topshirish / «Tayyor» / pin — hammasi 200",
      _lg.status_code in (302, 303) and all(O.values()) and _am and all(x == 200 for x in _am)
      and float(INFO["otgan"].get("debt_amount") or 0) > 0 and float(INFO["qarzli"].get("debt_amount") or 0) > 0
      and float(INFO["tolangan"].get("debt_amount") or 0) <= 0, (O, _am))

# ── lokal server
import uvicorn                                     # noqa: E402
so = socket.socket()
so.bind(("127.0.0.1", 0))
port = so.getsockname()[1]
so.close()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
BU = f"http://127.0.0.1:{port}"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PW_BOR = True
try:
    from playwright.sync_api import sync_playwright
except Exception:                          # noqa: BLE001
    PW_BOR = False
check("D0 Python `playwright` bor", PW_BOR)

USLUB = r"""([id, joy]) => {
  const e = document.querySelector((joy === 'pin' ? '#pinnedOrdersList' : '.ord-list') + ' .ord-item[data-order-id="' + id + '"]');
  if (!e) return null;
  const s = getComputedStyle(e), b = getComputedStyle(e, '::before');
  return {fon: s.backgroundColor, soya: s.boxShadow, yorliq: b.content, yorliq_fon: b.backgroundColor, yorliq_rang: b.color,
          raqam_rang: getComputedStyle(e.querySelector('.ord-num')).color, faol: e.classList.contains('active'),
          inline: e.getAttribute('style') || ''};
}"""
QATOR = r"""(id) => {
  const e = document.querySelector('.ord-list .ord-item[data-order-id="' + id + '"]');
  if (!e) return null;
  const b = [...e.querySelectorAll('.oi-belgilar > *')].map(x => (x.innerText || '').trim());
  return {bosh: !!e.querySelector('.oi-bosh .ord-num'), sana: !!e.querySelector('.ord-date .oi-sana'), summa: (e.querySelector('.oi-summa') || {}).innerText || '',
          belgilar: b, klass: e.className, inline: e.getAttribute('style') || ''};
}"""
SARLAVHA = r"""() => {
  const q = i => document.getElementById(i);
  const h = q('odSarlavha'), r = e => e ? Math.round(e.getBoundingClientRect().top) : null;
  const tarkib = q('odBody') ? q('odBody').closest('.card') : null;
  const yetk = q('dlvBody') ? q('dlvBody').closest('.card') : null;
  return {bor: !!h, korinadi: !!h && h.offsetParent !== null, raqam: q('ods-raqam') ? q('ods-raqam').innerText : null,
          nom: q('ods-nom') ? q('ods-nom').innerText : null, holat: q('ods-holat') ? q('ods-holat').innerText : null,
          yonadi: !!h && h.classList.contains('ochildi'), anim: h ? getComputedStyle(h).animationName : null,
          y_sarlavha: r(h), y_tarkib: r(tarkib), y_yetk: r(yetk),
          tarkib_nomi: tarkib ? (tarkib.querySelector('h3') || {}).innerText : null};
}"""
FILTR = r"""() => {
  const t = [...document.querySelectorAll('#ordFiltr [data-f]')].map(b => { const r = b.getBoundingClientRect();
    return {f: b.dataset.f, x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width * 10) / 10, son: (b.querySelector('.f-son') || {}).innerText,
            toshdi: b.scrollWidth > b.clientWidth + 1}; });
  return t;
}"""
TOSH = r"""() => { const c = document.querySelector('.ord-chap');
  const qator = [...document.querySelectorAll('.ord-chap .ord-item')].filter(e => e.offsetParent !== null && e.scrollWidth > e.clientWidth + 1).map(e => e.dataset.orderId);
  return {chap: c.scrollWidth - c.clientWidth, sahifa: document.documentElement.scrollWidth - document.documentElement.clientWidth, qator}; }"""
KORINADI = r"""() => [...document.querySelectorAll('.ord-list .ord-item')].filter(e => e.offsetParent !== null).map(e => Number(e.dataset.orderId)).sort((a, b) => a - b)"""
OCH = "() => document.querySelectorAll('.ord-list .proj-group').forEach(g => openProject(g.dataset.projectId))"
NAT = {}
XATO = []

if PW_BOR and all(O.values()):
    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def sahifa(w, h, tel=False, tungi=False):
            ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https://.*"), lambda r: r.fulfill(status=204, body=""))
            if tungi:
                ctx.add_init_script("try { localStorage.setItem('theme', 'dark'); } catch (e) {}")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "k203_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.goto, BU + "/orders")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.wait_for_function, "() => document.querySelectorAll('#pinnedOrdersList .ord-item').length > 0", timeout=15000)
            xav(pg.evaluate, OCH)
            return ctx, pg

        def tanla(pg, id, joy="ro'yxat"):
            sel = ('#pinnedOrdersList' if joy == 'pin' else '.ord-list') + f' .ord-item[data-order-id="{id}"]'
            xav(pg.evaluate, f"() => {{ const e = document.querySelector('{sel}'); if (e) e.click(); }}")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.wait_for_timeout, 500)

        # ── kompyuter 1440 × 900
        ctx, pg = sahifa(1440, 900)
        NAT["qator"] = {k: xav(pg.evaluate, QATOR, O[k]) for k in O}
        NAT["guruh"] = xav(pg.evaluate, r"""() => [...document.querySelectorAll('.ord-list .proj-group')].map(g => ({
            urg: g.dataset.urgency || null, inline: g.getAttribute('style') || '',
            belgi: [...g.querySelectorAll('.proj-head .pg-belgi, .proj-head .proj-debt, .proj-head .proj-paid')].map(x => x.className + '|' + x.innerText.trim())}))""")
        NAT["bolim"] = xav(pg.evaluate, r"""() => [...document.querySelectorAll('.ord-chap .ro-bolim')].map(e => (e.getAttribute('style') || '') + '|' + e.innerText.trim())""")
        NAT["filtr"] = xav(pg.evaluate, FILTR)
        _korinish = {}
        for k, joy in (("otgan", "ro'yxat"), ("bugun", "ro'yxat"), ("tolangan", "ro'yxat"), ("qarzli", "ro'yxat"), ("qoralama", "ro'yxat"),
                       ("pin", "pin")):
            oldin = xav(pg.evaluate, USLUB, [O[k], "pin" if joy == "pin" else "list"])
            tanla(pg, O[k], joy)
            keyin = xav(pg.evaluate, USLUB, [O[k], "pin" if joy == "pin" else "list"])
            _korinish[k] = {"oldin": oldin, "keyin": keyin,
                            "faollar": xav(pg.evaluate, "() => [...document.querySelectorAll('.ord-item.active')].map(e => Number(e.dataset.orderId))")}
            if k == "pin":
                _korinish[k]["ikkinchi"] = xav(pg.evaluate, USLUB, [O[k], "list"])
        NAT["korinish"] = _korinish
        # sarlavha, hisob-kitob, yopishqoq
        tanla(pg, O["otgan"])
        xav(pg.wait_for_function, "() => (document.getElementById('pay-debt') || {}).innerText && document.getElementById('pay-debt').innerText !== '—'", timeout=15000)
        NAT["sarlavha"] = xav(pg.evaluate, SARLAVHA)
        NAT["hisob"] = xav(pg.evaluate, "() => ['pay-total', 'pay-agreed', 'pay-paid', 'pay-debt'].map(i => (document.getElementById(i) || {}).innerText || '')")
        xav(pg.evaluate, "() => { const w = document.getElementById('ordPageWrap'); w.scrollTop = w.scrollHeight; }")
        xav(pg.wait_for_timeout, 300)
        NAT["yopishqoq"] = xav(pg.evaluate, r"""() => { const w = document.getElementById('ordPageWrap'), h = document.getElementById('odSarlavha');
            return {wrap: Math.round(w.getBoundingClientRect().top), sarlavha: Math.round(h.getBoundingClientRect().top), surildi: w.scrollTop}; }""")
        xav(pg.evaluate, "() => { document.getElementById('ordPageWrap').scrollTop = 0; }")
        # filtr ishlashi (avvalgidek)
        xav(pg.evaluate, "() => royxatFiltrla('otgan')")
        NAT["filtr_otgan"] = xav(pg.evaluate, KORINADI)
        NAT["filtr_faol"] = xav(pg.evaluate, "() => { const b = document.querySelector('#ordFiltr [data-f=\"otgan\"]'); return {faol: b.classList.contains('active'), soya: getComputedStyle(b).boxShadow, son_fon: getComputedStyle(b.querySelector('.f-son')).backgroundColor}; }")
        xav(pg.evaluate, "() => royxatFiltrla('hammasi')")
        NAT["filtr_hammasi"] = xav(pg.evaluate, KORINADI)
        # qayta yuklanganda tanlov tiklanadi (`tanlovniTikla`) — sarlavha ham
        xav(pg.reload)
        xav(pg.wait_for_load_state, "networkidle")
        xav(pg.wait_for_timeout, 600)
        NAT["tiklash"] = xav(pg.evaluate, "() => ({faol: [...document.querySelectorAll('.ord-list .ord-item.active')].map(e => Number(e.dataset.orderId)), raqam: (document.getElementById('ods-raqam') || {}).innerText || null})")
        ctx.close()

        # ── tor ekranlar: 1100 px (ro'yxat ustuni 260 px) va telefon 320 px — hech narsa chiqib, kesilmaydi
        NAT["tor"] = {}
        for _w, _tel in ((1100, False), (320, True)):
            ctx, pg = sahifa(_w, 800, tel=_tel)
            tanla(pg, O["otgan"])
            xav(pg.evaluate, "() => { document.getElementById('ordPageWrap').scrollTop = 0; window.scrollTo(0, 0); }")
            NAT["tor"][_w] = {"filtr": xav(pg.evaluate, FILTR), "tosh": xav(pg.evaluate, TOSH)}
            ctx.close()

        # ── tungi rejim
        ctx, pg = sahifa(1440, 900, tungi=True)
        tanla(pg, O["otgan"])
        NAT["tungi"] = xav(pg.evaluate, r"""(id) => { const e = document.querySelector('.ord-list .ord-item[data-order-id="' + id + '"]');
            const s = getComputedStyle(e), b = getComputedStyle(e, '::before'), k = getComputedStyle(document.querySelector('.ord-chap'));
            return {tema: document.documentElement.getAttribute('data-theme'), fon: s.backgroundColor, soya: s.boxShadow, karta: k.backgroundColor,
                    yorliq: b.content, yorliq_fon: b.backgroundColor, yorliq_rang: b.color, raqam_rang: getComputedStyle(e.querySelector('.ord-num')).color}; }""", O["otgan"])
        ctx.close()

        # ── telefon 390 × 844
        ctx, pg = sahifa(390, 844, tel=True)
        tanla(pg, O["otgan"])
        xav(pg.wait_for_timeout, 500)
        NAT["telefon"] = xav(pg.evaluate, r"""(id) => { const k = document.getElementById('sumCard'), r = document.getElementById('sumRaqam'),
            m = document.querySelector('#sumCard .sum-sarlavha-matn'), e = document.querySelector('.ord-list .ord-item[data-order-id="' + id + '"]');
            return {karta_y: Math.round(k.getBoundingClientRect().top), raqam: r ? r.innerText : null, raqam_korinadi: !!r && r.offsetParent !== null,
                    raqam_px: r ? parseFloat(getComputedStyle(r).fontSize) : 0, nom: (document.getElementById('sumNom') || {}).innerText || null,
                    matn_display: m ? getComputedStyle(m).display : null, kenglik: document.documentElement.scrollWidth,
                    yorliq: getComputedStyle(e, '::before').content, faol: e.classList.contains('active')}; }""", O["otgan"])
        ctx.close()
        br.close()

    OLTIN, OLTIN_OCH = (185.0, 120.0, 63.0), (248.0, 242.0, 235.0)

    def tanlangan_aniq(v):
        """oldin — yorliq yo'q, fon och oltin emas; keyin — 3 px oltin ramka, och oltin fon, «▶ OCHIQ», raqam to'q oltin"""
        o, k = (v or {}).get("oldin") or {}, (v or {}).get("keyin") or {}
        return (o.get("yorliq") in ("none", "normal") and rgb(o.get("fon")) != OLTIN_OCH and k.get("faol")
                and rgb(k.get("fon")) == OLTIN_OCH and "rgb(185, 120, 63) 0px 0px 0px 3px inset" in (k.get("soya") or "")
                and k.get("yorliq") == '"▶ OCHIQ"' and not re.search(r"background|border-left", k.get("inline") or ""))

    _kor = NAT.get("korinish") or {}
    check("D1 muddati o'tgan qarzli qator tanlanganda — 3 px oltin ramka, och oltin fon, «▶ OCHIQ» (ilgari faqat fon #FFF → #FDF8F0)",
          tanlangan_aniq(_kor.get("otgan")), _kor.get("otgan"))
    check("D1b bugungi, to'langan tugagan, qarzli tugagan (ilgari pushti fon o'zgarmasdi), qoralama qatorlari ham — xuddi shunday",
          all(tanlangan_aniq(_kor.get(k)) for k in ("bugun", "tolangan", "qarzli", "qoralama")),
          {k: (_kor.get(k) or {}).get("keyin") for k in ("bugun", "tolangan", "qarzli", "qoralama")})
    check("D1c muddat chizig'i ramka bilan birga: muddati o'tgan tanlangan qatorda 7 px qizil chiziq + oltin ramka",
          "rgb(220, 38, 38) 7px 0px 0px 0px inset" in (((_kor.get("otgan") or {}).get("keyin") or {}).get("soya") or ""),
          ((_kor.get("otgan") or {}).get("keyin") or {}).get("soya"))
    check("D2 ustuvor (pin) ro'yxatdan tanlansa — loyiha ichidagi nusxasi ham tanlangan (2 ta, faqat shu buyurtma); boshqasida — 1 ta",
          tanlangan_aniq(_kor.get("pin")) and sorted((_kor.get("pin") or {}).get("faollar") or []) == [O["pin"], O["pin"]]
          and ((_kor.get("pin") or {}).get("ikkinchi") or {}).get("yorliq") == '"▶ OCHIQ"'
          and (_kor.get("bugun") or {}).get("faollar") == [O["bugun"]],
          {k: (_kor.get(k) or {}).get("faollar") for k in ("pin", "bugun")})
    _sr = NAT.get("sarlavha") or {}
    check("D3 o'rtada ochilgan buyurtma sarlavhasi: raqam, holat «Jarayonda», loyiha · mijoz · telefon; ochilganda yonadi",
          _sr.get("korinadi") and _sr.get("raqam") == NUM["otgan"] and "Jarayonda" in (_sr.get("holat") or "")
          and all(x in (_sr.get("nom") or "") for x in ("Yunusobod K203", "Aziz K203", "+998901112233"))
          and _sr.get("yonadi") and _sr.get("anim") == "odsYonish", _sr)
    check("D3b tartib: sarlavha → «Buyurtma tarkibi» → Yetkazish (ilgari birinchi «Yetkazish», raqam yozilmagan)",
          _sr.get("y_sarlavha") is not None and _sr.get("y_tarkib") is not None and _sr.get("y_yetk") is not None
          and _sr["y_sarlavha"] < _sr["y_tarkib"] < _sr["y_yetk"] and "Buyurtma tarkibi" in (_sr.get("tarkib_nomi") or ""), _sr)
    _ys = NAT.get("yopishqoq") or {}
    check("D4 kompyuterda sahifa oxirigacha surilganda sarlavha tepada qoladi",
          _ys.get("surildi", 0) >= 150 and _ys.get("wrap") is not None and abs(_ys["sarlavha"] - _ys["wrap"]) <= 2, _ys)
    _f = NAT.get("filtr") or []
    _q = NAT.get("qator") or {}
    _kut_son = {"hammasi": 6, "otgan": 2, "bugun": 1, "jarayonda": 3,
                "qarz": sum(1 for k in O if (_q.get(k) or {}).get("belgilar") and any(b.startswith("Qarz:") for b in _q[k]["belgilar"])),
                "tugagan": 2}
    def _ustunlar(f):
        """6 tugma: 2 ustun × 3 qator, har ustunda eni bir xil, mazmun tugmadan chiqmaydi"""
        xs = sorted({t["x"] for t in f})
        return (len(f) == 6 and len(xs) == 2 and len({t["y"] for t in f}) == 3 and not any(t["toshdi"] for t in f)
                and all(max(t["w"] for t in f if t["x"] == x) - min(t["w"] for t in f if t["x"] == x) <= 1 for x in xs))

    check("D5 filtr — «Teng kataklar»: 6 tugma 2 ustun × 3 qator (har ustunda bir xil en, yozuv tugmadan chiqmaydi); sonlar avvalgidek",
          _ustunlar(_f) and all(str(_kut_son[t["f"]]) == (t["son"] or "").strip() for t in _f), (_f, _kut_son))
    _tor = NAT.get("tor") or {}
    check("D5c tor ekran — 1100 px (ro'yxat ustuni 260 px) va telefon 320 px: filtr 2 ustun, hech bir tugma / qator / ro'yxat ustuni "
          "chiqib kesilmaydi, sahifa yon tomonga surilmaydi",
          set(_tor) == {1100, 320} and all(_ustunlar(v.get("filtr") or []) and (v.get("tosh") or {}).get("chap", 9) <= 1
                                           and (v.get("tosh") or {}).get("sahifa", 9) <= 1 and not (v.get("tosh") or {}).get("qator", [1])
                                           for v in _tor.values()), _tor)
    _fa = NAT.get("filtr_faol") or {}
    check("D5b filtrlash avvalgidek: «Muddati o'tgan» — faqat 2 muddati o'tgan buyurtma; tanlangan tugma oltin ramkali, soni oltin fonda; "
          "«Hammasi» — 6",
          NAT.get("filtr_otgan") == sorted([O["otgan"], O["pin"]]) and NAT.get("filtr_hammasi") == sorted(O.values())
          and _fa.get("faol") and "rgb(185, 120, 63)" in (_fa.get("soya") or "") and rgb(_fa.get("son_fon")) == (154.0, 98.0, 49.0),
          (NAT.get("filtr_otgan"), NAT.get("filtr_hammasi"), _fa))
    _dq = INFO["otgan"].get("debt_amount")
    _bel = {k: (_q.get(k) or {}).get("belgilar") or [] for k in O}
    check("D6 qator tuzilmasi bir xil (raqam + holat, sana + summa, belgilar); qatorda inline fon / chiziq yo'q",
          all(v and v["bosh"] and v["sana"] and v["summa"].endswith("so'm") and not re.search(r"background|border-left", v["inline"])
              for v in _q.values()), _q)
    check("D6b belgilar: muddati o'tgan — «Muddati o'tgan», «Qarz: …», topshirish % ; bugungi — «Bugun muddati»; to'langan tugagan — "
          "«✓ To'langan», «To'liq topshirildi» (klass oi-tolangan); qarzli tugagan — «Qarz: …» (oi-qarzli)",
          "Muddati o'tgan" in _bel["otgan"] and any(b.startswith("Qarz:") for b in _bel["otgan"]) and any(b.endswith("%") for b in _bel["otgan"])
          and "Bugun muddati" in _bel["bugun"] and "✓ To'langan" in _bel["tolangan"] and "To'liq topshirildi" in _bel["tolangan"]
          and "oi-tolangan" in (_q.get("tolangan") or {}).get("klass", "") and any(b.startswith("Qarz:") for b in _bel["qarzli"])
          and "oi-qarzli" in (_q.get("qarzli") or {}).get("klass", "") and not any(b.startswith("Qarz:") for b in _bel["tolangan"]), _bel)
    _g = NAT.get("guruh") or []
    check("D6c loyiha guruhi: muddat — `data-urgency` (inline chiziq yo'q), muddati o'tgan / qarz — belgi (emoji yo'q)",
          len(_g) == 2 and all(not re.search(r"border-left", x["inline"]) for x in _g) and all(x["urg"] == "overdue" for x in _g)
          and all(any("pg-belgi qizil|Muddati o'tgan" in b for b in x["belgi"]) and any(b.startswith("proj-debt|Qarz:") for b in x["belgi"]) for x in _g), _g)
    check("D6d ro'yxat bo'lim sarlavhalari (Ustuvor, So'nggi 90 kun) — klass bilan, inline uslubsiz",
          len(NAT.get("bolim") or []) == 2 and all(b.startswith("|") for b in NAT["bolim"]), NAT.get("bolim"))
    _h = NAT.get("hisob") or []
    _raqam = lambda t: re.sub(r"[^\d]", "", t or "")             # noqa: E731
    check("D7 hisob-kitob paneli avvalgidek: «Qarz qoldi» = API qarzi (so'm), jami / kelishilgan / to'langan to'ldirilgan",
          len(_h) == 4 and all(_raqam(x) for x in _h) and _raqam(_h[3]) == str(int(round(float(_dq or 0)))), (_h, _dq))
    _tg = NAT.get("tungi") or {}
    check("D8 tungi rejim: «▶ OCHIQ» yozuvi ≥ 4,5:1, oltin ramka kartaga nisbatan ≥ 3:1, raqam fonda ≥ 4,5:1",
          _tg.get("tema") == "dark" and _tg.get("yorliq") == '"▶ OCHIQ"'
          and kontrast(rgb(_tg.get("yorliq_rang")), rgb(_tg.get("yorliq_fon"))) >= 4.5
          and kontrast(OLTIN, rgb(_tg.get("karta"))) >= 3 and kontrast(rgb(_tg.get("raqam_rang")), rgb(_tg.get("fon"))) >= 4.5,
          (_tg, kontrast(rgb(_tg.get("yorliq_rang")), rgb(_tg.get("yorliq_fon"))), kontrast(OLTIN, rgb(_tg.get("karta"))),
           kontrast(rgb(_tg.get("raqam_rang")), rgb(_tg.get("fon")))))
    _ko = ((_kor.get("otgan") or {}).get("keyin")) or {}
    check("D8b yorug' rejim: «▶ OCHIQ» ≥ 4,5:1, raqam och oltin fonda ≥ 4,5:1, oltin ramka oq kartaga nisbatan ≥ 3:1",
          kontrast(rgb(_ko.get("yorliq_rang")), rgb(_ko.get("yorliq_fon"))) >= 4.5
          and kontrast(rgb(_ko.get("raqam_rang")), OLTIN_OCH) >= 4.5 and kontrast(OLTIN, (255.0, 255.0, 255.0)) >= 3, _ko)
    _tl = NAT.get("telefon") or {}
    check("D9 telefon (390 px): tanlanganda xulosa kartasi ko'rinadi, sarlavhasida katta raqam (≥ 18 px) va loyiha · mijoz; yon tomonga "
          "surilmaydi; ro'yxatdagi qatorda «▶ OCHIQ»",
          0 <= (_tl.get("karta_y") if _tl.get("karta_y") is not None else -1) <= 200 and _tl.get("raqam") == NUM["otgan"]
          and _tl.get("raqam_korinadi") and _tl.get("raqam_px", 0) >= 18 and _tl.get("matn_display") == "none"
          and "Yunusobod K203" in (_tl.get("nom") or "") and _tl.get("kenglik", 999) <= 391 and _tl.get("yorliq") == '"▶ OCHIQ"'
          and _tl.get("faol"), _tl)
    _tk = NAT.get("tiklash") or {}
    check("D10 qayta yuklanganda (saqlash / to'lovdan keyin) tanlangan buyurtma tiklanadi — avvalgidek",
          _tk.get("faol") == [O["otgan"]], _tk)
    check("D10b … va sarlavha ham to'ladi", _tk.get("raqam") == NUM["otgan"], _tk)
    check("D11 sahifada JS xatosi yo'q (kompyuter, tungi, telefon)", not XATO, XATO)
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
