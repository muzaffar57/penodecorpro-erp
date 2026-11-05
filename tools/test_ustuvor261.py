#!/usr/bin/env python3
"""
test_ustuvor261.py — kech194 (zip 261): «Buyurtmalar» — «⭐ Ustuvor buyurtmalar» loyiha kartalari bilan BIR ko'rinishda.

NIMA UCHUN KERAK (egasi so'rovi 06.11 01:20: «buyurtmalar jadvalini o'zgartirgan edik, ustuvor buyurtmalar o'zgarmay qolgan ekan — ularni ham
qolgan jadvallar bilan bir xil chiqadigan qilib qo'ysak»; namunadan keyin QARORI 01:24: «ma'qul, faqat … bir xil bo'lsa bo'ldi»).
O'LCHANGAN (asl — zip 260, 4233321): ustuvor buyurtmalar — oq fonda bir-biriga yopishgan qatorlar (karta, oraliq, yumaloq, to'lov chizig'i
YO'Q), balandligi 100 px (loyiha yopiq kartasi 67 px), qarz / to'langan belgisi yo'q, loyiha nomi yo'q; ro'yxat qayta chizilganda
(pin / pindan olish) tanlangan buyurtma belgisi yo'qolardi; to'lov o'zgarsa ustuvor qator eskirib qolardi.
TALAB (har biri o'lchanadi):
  S  manba: `crud.get_pinned_orders` — `debt_amount` (= `Order.debt_amount`), `kelishilgan_summa`; `renderPinnedOrders` — `data-pul`,
     `.pin-past` (loyiha · mijoz + «Qarz» / «✓ To'langan» / summa), tanlangan buyurtma `active` bilan chiziladi; CSS — karta, chiziq;
     `royxatPulSinxron` ustuvor ro'yxatni ham yangilaydi
  A  API `/api/orders/pinned`: qarzli — debt_amount > 0, to'langan — 0, kelishilgan summa — buyurtma API si bilan bir xil
  J  HAQIQIY Chromium (1440, 390, tungi, 1000): ustuvor kartalar — orasi ≥ 6 px, yumaloq ≥ 10 px, chap chiziq (qarzli qizil, to'langan
     yashil), balandligi loyiha yopiq kartasi bilan BIR XIL (± 1 px); matnda «Qarz:» / «✓ To'langan» va loyiha nomi; tanlansa ikkala nusxa
     tanlangan («▶ OCHIQ», 3 px ramka), ro'yxat qayta chizilsa ham tanlangani saqlanadi; to'lov o'chirilsa (sahifa yuklanmasdan) ustuvor
     karta yashil → qizil; eski server javobi (maydonsiz) va summasiz buyurtma — kulrang, summa matni; gorizontal surilish yo'q; JS xato yo'q
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. Asl kodga (zip 260) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_ustuvor261.py   (ixtiyoriy `U261_RASM=<papka>` — skrinshotlar)
"""
import os
import io
import re
import sys
import time
import socket
import tempfile
import datetime
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

_T = tempfile.mkdtemp(prefix="u261_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'u261.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "PG_URL"):
    os.environ.pop(_k, None)

OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
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
        print(f"  ✗ {label}   {str(d)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ORD = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
CRUD = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
_izohsiz = lambda t: re.sub(r"/\*.*?\*/", "", re.sub(r"(?m)^\s*//[^\n]*", "", t), flags=re.S)
_gp = CRUD[CRUD.find("def get_pinned_orders("):CRUD.find("\ndef ", CRUD.find("def get_pinned_orders(") + 10)]
_pin = ORD[ORD.find("function renderPinnedOrders(rows)"):ORD.find("async function toggleOrderPin(")]
_css = _izohsiz(ORD[ORD.find("<style>"):ORD.find("</style>")])
_sx = ORD[ORD.find("async function royxatPulSinxron("):ORD.find("function royxatSanoqlari(")]
check("S1 `get_pinned_orders` — `debt_amount` (`Order.debt_amount`) va `kelishilgan_summa` (`Order.kelishilgan_summa`) — ro'yxat qatori bilan bir manba",
      '"debt_amount": float(o.debt_amount or 0)' in _gp and '"kelishilgan_summa": float(o.kelishilgan_summa or 0)' in _gp, _gp[-600:])
check("S2 `renderPinnedOrders`: `data-pul` (qarz > 0 → qarz; summa > 0 → tolangan; aks holda yoq), `.pin-past` (loyiha · mijoz), belgi — "
      "`proj-debt` (qisqa summa) / `proj-paid` / summa; tanlangan buyurtma `active` bilan chiziladi",
      'data-pul="${pul}"' in _pin and "if (qarz > 0) pul = 'qarz';" in _pin and "pul = 'tolangan';" in _pin
      and '<div class="pin-past"><span class="pin-loyiha">${escapeHtml(o.project_name)} · ${escapeHtml(o.client_name)}</span>${belgi}</div>' in _pin
      and 'class="proj-debt"' in _pin and "qisqaSumma(qarz)" in _pin and 'class="proj-paid">✓ To\'langan' in _pin
      and "Number(selectedOrderId) === Number(o.id)) ? ' active' : ''" in _pin and 'class="ord-item${tanlangan}"' in _pin, _pin[:400])
check("S3 CSS: `#pinnedOrdersList` — kulrang tag; karta (oraliq 8 px, yumaloq 12 px, min 58 px — loyiha kartasi bilan bir), chiziq "
      "(qizil / yashil / kulrang), tanlangani — 3 px ramka",
      "#pinnedOrdersList{background:var(--bg);padding:10px 0 2px}" in _css
      and "#pinnedOrdersList .ord-item{margin:0 10px 8px;padding:9px 14px 9px 12px;min-height:58px;box-sizing:border-box;" in _css
      and "border-radius:12px;box-shadow:inset 4px 0 0 var(--border)" in _css
      and '#pinnedOrdersList .ord-item[data-pul="qarz"]{box-shadow:inset 4px 0 0 var(--m-dc2626)' in _css
      and '#pinnedOrdersList .ord-item[data-pul="tolangan"]{box-shadow:inset 4px 0 0 var(--m-15803d)' in _css
      and "box-shadow:inset 0 0 0 3px var(--gold);padding-top:24px}" in _css)
check("S4 `royxatPulSinxron` — shu buyurtma ustuvor bo'lsa ustuvor ro'yxatni qayta o'qiydi (`loadPinnedOrders`), keyin loyiha guruhi",
      "#pinnedOrdersList .ord-item[data-order-id=" in _sx and "loadPinnedOrders();" in _sx
      and _sx.find("loadPinnedOrders();") < _sx.find("const qator = document.querySelector("), _sx[:500])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# tayyorgarlik — ma'lumot API orqali
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

for _n in ("_send_telegram", "_send_telegram_to", "_send_telegram_document", "_send_telegram_to_qoplamachi"):
    if hasattr(main, _n):
        setattr(main, _n, lambda *a, **k: False)

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "u261_a", PAROL, UserRole.ADMIN, "U261 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="U261 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
PT = Project(company_id=1, client_name="Tillo aka", project_name="NAYMAN KOCHA U261", client_phone="+998901112261", total_budget=0, total_paid=0)
PQ = Project(company_id=1, client_name="Oltinko'l", project_name="OLTINKOL MASJID U261", client_phone="+998935554261", total_budget=0,
             total_paid=0)
US = Master(company_id=1, name="U261 Usta", phone="+998900002610")
s.add_all([PENO, PT, PQ, US])
s.commit()
ID = {"PENO": PENO.id, "PT": PT.id, "PQ": PQ.id, "US": US.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lg = C.post("/login", data={"username": "u261_a", "password": PAROL}, follow_redirects=False)
TK = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).date()


def kun(n):
    return (TK + datetime.timedelta(days=n)).isoformat()


def buyurtma(pid, muddat, miqdor, narx):
    tana = {"project_id": pid, "order_type": "product", "recipe_id": None, "master_id": ID["US"], "deadline": muddat, "is_draft": False,
            "base_price": 600000, "loy_kg": None,
            "items": [{"name": "U261 panel", "category": "panel", "width": 60, "thickness": 5, "length": 0, "quantity": miqdor,
                       "unit_price": narx, "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}]}
    r = C.post("/api/orders", json=tana)
    if r.status_code == 409:
        r = C.post("/api/orders?confirm_shortage=true", json=tana)
    return (r.json() or {}).get("id") if r.status_code == 200 else None


def tolov(oid, summa, tur="partial"):
    return C.post("/api/payments", json={"order_id": oid, "amount": summa, "payment_type": tur, "payment_method": "naqd", "notes": "U261"})


O = {"tolangan": buyurtma(ID["PT"], kun(3), 12, 25000),        # 300 000 — to'liq to'langan, ustuvor
     "qarzli": buyurtma(ID["PQ"], kun(-4), 20, 122000),        # 2 440 000 — qarzi bor, ustuvor
     "oddiy": buyurtma(ID["PQ"], kun(6), 4, 15000)}            # ustuvor emas
_am = []
PAY_T = None
if all(O.values()):
    _rt = tolov(O["tolangan"], 300000, "final")
    _am.append(_rt.status_code)
    PAY_T = (_rt.json() or {}).get("payment_id") if _rt.status_code == 200 else None
    _am.append(tolov(O["qarzli"], 100000, "zaklat").status_code)
    _am.append(C.post(f"/api/orders/{O['qarzli']}/pin").status_code)
    _am.append(C.post(f"/api/orders/{O['tolangan']}/pin").status_code)
INFO = {k: (C.get(f"/api/orders/{v}").json() if v else {}) for k, v in O.items()}
check("0.1 fikstura: kirish, 3 buyurtma (to'langan, qarzli, oddiy), to'lovlar, 2 ta pin — 200",
      _lg.status_code in (302, 303) and all(O.values()) and len(_am) == 4 and all(x == 200 for x in _am) and PAY_T
      and float(INFO["tolangan"].get("debt_amount") or 0) <= 0 and float(INFO["qarzli"].get("debt_amount") or 0) > 0, (O, _am))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_rp = C.get("/api/orders/pinned")
PINS = {p.get("id"): p for p in (_rp.json() if _rp.status_code == 200 else [])}
_pq, _pt = PINS.get(O["qarzli"]) or {}, PINS.get(O["tolangan"]) or {}
check("A1 `/api/orders/pinned`: 2 ta (oddiy — yo'q); qarzli — `debt_amount` = buyurtma API qarzi (2 340 000), to'langan — 0",
      _rp.status_code == 200 and set(PINS) == {O["qarzli"], O["tolangan"]}
      and abs(float(_pq.get("debt_amount", -1)) - float(INFO["qarzli"].get("debt_amount") or 0)) < 0.005
      and abs(float(_pq.get("debt_amount", -1)) - 2340000) < 0.005 and float(_pt.get("debt_amount", -1)) == 0, (_rp.status_code, PINS))
check("A2 `kelishilgan_summa` — buyurtma API si bilan bir xil (2 440 000 / 300 000)",
      abs(float(_pq.get("kelishilgan_summa", -1)) - 2440000) < 0.005 and abs(float(_pt.get("kelishilgan_summa", -1)) - 300000) < 0.005,
      (_pq, _pt))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
import uvicorn                                     # noqa: E402
from playwright.sync_api import sync_playwright    # noqa: E402
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
RASM = os.environ.get("U261_RASM")

OLCH = """() => {
  const r = e => e.getBoundingClientRect();
  const L = document.getElementById('pinnedOrdersList');
  const ps = [...L.querySelectorAll(':scope > .ord-item')];
  const gs = [...document.querySelectorAll('.ord-list > .proj-group:not(.open)')];
  const oraliq = ps.slice(1).map((p, i) => Math.round((r(p).top - r(ps[i]).bottom) * 10) / 10);
  return {listFon: getComputedStyle(L).backgroundColor,
          pin: ps.map(p => ({id: p.dataset.orderId, pul: p.dataset.pul, h: Math.round(r(p).height * 10) / 10, radius: parseFloat(getComputedStyle(p).borderTopLeftRadius),
                             chiziq: getComputedStyle(p).boxShadow, fon: getComputedStyle(p).backgroundColor, matn: p.innerText,
                             faol: p.classList.contains('active')})),
          guruhH: gs.map(g => Math.round(r(g).height * 10) / 10), oraliq,
          surilish: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1}; }"""
J = {}
XATO = []


def kir(pg):
    pg.goto(BU + "/login", wait_until="networkidle")
    pg.fill("input[name=username]", "u261_a")
    pg.fill("input[name=password]", PAROL)
    pg.click("button[type=submit]")
    pg.wait_for_load_state("networkidle")
    pg.goto(BU + "/orders", wait_until="networkidle")
    pg.wait_for_function("() => document.querySelectorAll('#pinnedOrdersList .ord-item').length > 0", timeout=15000)


try:
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for nom, w, h, tungi in (("kompyuter", 1440, 900, False), ("telefon", 390, 844, False), ("tungi", 1440, 900, True), ("tor", 1000, 900, False)):
            ctx = br.new_context(viewport={"width": w, "height": h})
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:200]))
            kir(pg)
            if tungi:
                pg.evaluate("() => document.documentElement.setAttribute('data-theme', 'dark')")
            pg.wait_for_timeout(300)
            J[nom] = pg.evaluate(OLCH)
            if RASM:
                pg.locator("#pinnedOrdersSection").first.screenshot(path=os.path.join(RASM, f"ustuvor_{nom}.png"))
            if nom == "kompyuter":
                pg.locator(f"#pinnedOrdersList .ord-item[data-order-id='{O['qarzli']}']").first.click()
                pg.wait_for_timeout(800)
                J["tanlov"] = pg.evaluate("""(id) => ({faollar: [...document.querySelectorAll('.ord-item.active')].map(x => x.dataset.orderId),
                    pin: (() => { const e = document.querySelector(`#pinnedOrdersList .ord-item[data-order-id="${id}"]`);
                                  return {ochiq: getComputedStyle(e, '::before').content, soya: getComputedStyle(e).boxShadow}; })()})""", O["qarzli"])
                pg.evaluate("() => loadPinnedOrders()")
                pg.wait_for_timeout(800)
                J["qayta"] = pg.evaluate("""(id) => [...document.querySelectorAll('#pinnedOrdersList .ord-item.active')].map(x => x.dataset.orderId)""",
                                         O["qarzli"])
                J["sintetik"] = pg.evaluate("""() => {
                    renderPinnedOrders([{id: 900001, order_number: 'ESKI-1', client_name: 'Mijoz', project_name: 'Loyiha', status: 'in_progress',
                                         total_amount: 50000, agreed_amount: null, master_name: '—', created_at: '01.11.2026', deadline: null,
                                         deadline_urgency: 'normal', project_id: 1},
                                        {id: 900002, order_number: 'NOL-1', client_name: 'Mijoz', project_name: 'Loyiha', status: 'draft',
                                         total_amount: 0, agreed_amount: null, master_name: '—', created_at: '01.11.2026', deadline: null,
                                         deadline_urgency: 'normal', project_id: 1, debt_amount: 0, kelishilgan_summa: 0}]);
                    const q = [...document.querySelectorAll('#pinnedOrdersList .ord-item')];
                    return q.map(e => ({pul: e.dataset.pul, matn: e.innerText, chiziq: getComputedStyle(e).boxShadow})); }""")
            ctx.close()
        # to'lov o'chirilsa — sahifa yuklanmasdan ustuvor karta yangilanadi (holat o'zgaradi — eng OXIRIDA)
        ctx = br.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: XATO.append(str(e)[:200]))
        kir(pg)
        pg.locator(f"#pinnedOrdersList .ord-item[data-order-id='{O['tolangan']}']").first.click()
        pg.wait_for_timeout(800)
        SX = """(id) => { const e = document.querySelector(`#pinnedOrdersList .ord-item[data-order-id="${id}"]`);
                 return {belgi: window.belgi261 || null, pul: e.dataset.pul, matn: e.innerText, chiziq: getComputedStyle(e).boxShadow,
                         faol: e.classList.contains('active')}; }"""
        J["x0"] = pg.evaluate(SX, O["tolangan"])
        pg.evaluate("() => { window.belgi261 = 'shu-sahifa'; window.showConfirmModal = async () => true; }")
        pg.evaluate(f"() => deletePayment({PAY_T})")
        pg.wait_for_timeout(2500)
        J["x1"] = pg.evaluate(SX, O["tolangan"])
        ctx.close()
        br.close()
except Exception as e:                     # noqa: BLE001
    J["xato"] = f"{type(e).__name__}: {e}"


def rang(sh, rgb):
    return isinstance(sh, str) and rgb in sh.replace(" ", "")


def _p(v, oid):
    return next((x for x in (v or {}).get("pin", []) if x["id"] == str(oid)), None) or {}


_k = J.get("kompyuter") or {}
check("J1 kompyuter: ustuvor buyurtmalar — alohida kartalar (orasi ≥ 6 px, yumaloq ≥ 10 px), kulrang tagda; qarzli — qizil chiziq "
      "(#DC2626), to'langan — yashil (#15803D)",
      len(_k.get("pin") or []) == 2 and all(x >= 6 for x in _k["oraliq"]) and all(p["radius"] >= 10 for p in _k["pin"])
      and _k["listFon"] == "rgb(244, 246, 250)" and all(p["fon"] == "rgb(255, 255, 255)" for p in _k["pin"])
      and _p(_k, O["qarzli"]).get("pul") == "qarz" and rang(_p(_k, O["qarzli"]).get("chiziq"), "rgb(220,38,38)4px")
      and _p(_k, O["tolangan"]).get("pul") == "tolangan" and rang(_p(_k, O["tolangan"]).get("chiziq"), "rgb(21,128,61)4px"),
      (J.get("xato"), _k))
_gh = sorted(set(_k.get("guruhH") or []))
check("J2 balandlik — loyiha yopiq kartasi bilan BIR XIL (± 1 px; egasi QARORI «bir xil bo'lsa bo'ldi»)",
      _gh and all(abs(p["h"] - _gh[0]) <= 1 for p in _k.get("pin") or [{"h": -99}]) and max(_gh) - min(_gh) <= 1,
      ([p.get("h") for p in _k.get("pin") or []], _gh))
check("J3 matn: qarzli — «Qarz: 2,3 mln» va loyiha nomi; to'langan — «✓ To'langan» va loyiha nomi",
      "Qarz: 2,3 mln" in _p(_k, O["qarzli"]).get("matn", "") and "OLTINKOL MASJID U261" in _p(_k, O["qarzli"]).get("matn", "")
      and "✓ To'langan" in _p(_k, O["tolangan"]).get("matn", "") and "NAYMAN KOCHA U261" in _p(_k, O["tolangan"]).get("matn", ""),
      [p.get("matn") for p in _k.get("pin") or []])
_tv = J.get("tanlov") or {}
check("J4 ustuvordan tanlansa — ikkala nusxa (ustuvor va loyiha ichidagi) tanlangan; ustuvor karta — «▶ OCHIQ» va 3 px ramka",
      sorted(_tv.get("faollar") or []) == [str(O["qarzli"])] * 2 and "OCHIQ" in ((_tv.get("pin") or {}).get("ochiq") or "")
      and "3px" in ((_tv.get("pin") or {}).get("soya") or ""), _tv)
check("J5 ustuvor ro'yxat qayta chizilganda (pin / pindan olish, to'lov sinxroni) tanlangan buyurtma belgisi SAQLANADI (asl kodda yo'qolardi)",
      J.get("qayta") == [str(O["qarzli"])], J.get("qayta"))
_sn = J.get("sintetik") or []
check("J6 eski server javobi (qarz maydoni yo'q) va summasi 0 buyurtma — kulrang chiziq, summa matni («50 000 so'm» / «0 so'm»), belgi yo'q",
      len(_sn) == 2 and all(x["pul"] == "yoq" for x in _sn) and "50 000 so'm" in _sn[0]["matn"].replace("\xa0", " ")
      and "0 so'm" in _sn[1]["matn"]
      and not any(("Qarz" in x["matn"] or "To'langan" in x["matn"]) for x in _sn)
      and all(rang(x["chiziq"], "rgb(226,231,239)4px") for x in _sn), _sn)
_t, _q, _tr = J.get("telefon") or {}, J.get("tungi") or {}, J.get("tor") or {}
check("J7 telefon (390) va tor ekran (1000): kartalar, chiziq ranglari, loyiha kartasi bilan bir balandlik; gorizontal surilish yo'q",
      all(len(v.get("pin") or []) == 2 and not v.get("surilish") and all(x >= 6 for x in v["oraliq"])
          and rang(_p(v, O["qarzli"]).get("chiziq"), "rgb(220,38,38)4px")
          and v.get("guruhH") and all(abs(p["h"] - v["guruhH"][0]) <= 1 for p in v["pin"]) for v in (_t, _tr)),
      ({k: (v.get("surilish"), [p.get("h") for p in v.get("pin") or []], v.get("guruhH")) for k, v in (("telefon", _t), ("tor", _tr))}))
check("J8 tungi rejim: karta foni ro'yxat tagidan farqli, chiziqlar 4 px va bir-biridan farqli",
      len(_q.get("pin") or []) == 2 and all(p["fon"] != _q.get("listFon") for p in _q["pin"])
      and all("4px" in p["chiziq"] for p in _q["pin"]) and _q["pin"][0]["chiziq"] != _q["pin"][1]["chiziq"], _q)
_x0, _x1 = J.get("x0") or {}, J.get("x1") or {}
check("J9 to'lov o'chirilganda (sahifa QAYTA YUKLANMAYDI) ustuvor karta yangilanadi: `data-pul` tolangan → qarz, «✓ To'langan» → "
      "«Qarz: 300 ming»; tanlangan holat (3 px ramka) saqlanadi",
      _x0.get("pul") == "tolangan" and "✓ To'langan" in (_x0.get("matn") or "") and _x1.get("belgi") == "shu-sahifa"
      and _x1.get("pul") == "qarz" and "Qarz: 300 ming" in (_x1.get("matn") or "")
      and _x1.get("faol") and "3px" in (_x1.get("chiziq") or ""), (_x0, _x1))
check("J10 sahifalarda JS xatosi yo'q", not XATO and "xato" not in J, (XATO[:3], J.get("xato")))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _f in FAILED:
        print("  " + _f)
sys.exit(1 if FAIL else 0)
