#!/usr/bin/env python3
"""
test_royxat260.py — kech191 (zip 260): «Buyurtmalar» ro'yxati — 2-namuna «Aksentli chap chiziq».

NIMA UCHUN KERAK (egasi so'rovi 05.11 18:18: «hodimlar — buyurtmalar jadvali juda zich, ko'z toliqib qolyapti»; to'rt namunadan
QARORI — 2-namuna; «faqat Muddati o'tgan degan yozuv bo'lmasin»; ochilgandagi namunasi — «ma'qul»). O'LCHANGAN (asl — zip 259):
loyiha guruhlari bir-biriga yopishgan kulrang qatorlar (oraliq 0), chap chiziq — MUDDAT (qizil / sariq), sarlavhada va buyurtma
qatorlarida «Muddati o'tgan» / «Bugun muddati» / «Ertaga muddati» belgilari; ochiq loyiha — papka quloq'i + 20 px bo'shliq.
TALAB (har biri o'lchanadi):
  S  manba: guruhda `data-pul` (qarz / tolangan / yoq — sarlavhadagi «Qarz» / «✓ To'langan» bilan bir shart), `data-urgency` qoladi
     (filtr); «Muddati o'tgan» / «Bugun muddati» / «Ertaga muddati» belgilari — guruh, buyurtma qatori, ustuvor (pin) ro'yxatida YO'Q;
     CSS: karta (oraliq, yumaloq), to'lov chizig'i (yashil / qizil / kulrang), muddat chizig'i qoidalari YO'Q, papka quloq'i YO'Q
  H  HTTP (/orders): 3 loyiha — to'langan / qarzli / qiymatsiz (qoralama) — `data-pul` to'g'ri; ro'yxatda (`.ord-list`) muddat
     belgisi matni yo'q; muddati o'tgan buyurtma `data-urgency="overdue"` saqlangan; filtr tugmasi «Muddati o'tgan» bor
  J  HAQIQIY Chromium (1440 va 390, tungi rejim): kartalar orasi ≥ 6 px, yumaloq ≥ 10 px; chap chiziq rangi — to'langan yashil,
     qarzli qizil, qiymatsiz kulrang; ochilgan loyiha — ko'k chegara, papka quloq'i yo'q (`::before` yo'q), ichidagi buyurtmalar —
     alohida kartalar (oraliq ≥ 5 px), tanlangan — «▶ OCHIQ» va 3 px ramka, muddat chizig'i yo'q; «Muddati o'tgan» filtri — faqat
     muddati o'tgan buyurtmalar qoladi; ko'rinadigan matnda «Muddati o'tgan» faqat filtr tugmasida; gorizontal surilish yo'q; JS xato yo'q
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. Asl kodga (zip 259) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_royxat260.py   (ixtiyoriy `R260_RASM=<papka>` — skrinshotlar)
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

_T = tempfile.mkdtemp(prefix="r260_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'r260.db')}"
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


MUDDAT_SOZ = ("Muddati o'tgan", "Bugun muddati", "Ertaga muddati")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ORD = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
CSS = ORD[ORD.find("<style>"):ORD.find("</style>")]
_gr = ORD[ORD.find("{% for g in grouped %}"):ORD.find("<!-- Buyurtmalar -->", ORD.find("{% for g in grouped %}"))]
_qb = ORD[ORD.find("{% for o in g.orders %}"):ORD.find("{% endfor %}", ORD.find("{% for o in g.orders %}"))]
_pin = ORD[ORD.find("function renderPinnedOrders(rows)"):ORD.find("async function toggleOrderPin(")]
_izohsiz = lambda t: re.sub(r"\{#.*?#\}", "", re.sub(r"//[^\n]*", "", t), flags=re.S)
check("S1 guruh: `data-pul` — qarz / tolangan / yoq (sarlavhadagi «Qarz» / «✓ To'langan» sharti bilan bir xil), `data-urgency` qoladi",
      'data-pul="{{ \'qarz\' if g.debt > 0 else (\'tolangan\' if g.total > 0 else \'yoq\') }}"' in _gr
      and 'data-urgency="{{ g_urgency }}"' in _gr and "{% if g.debt > 0 %}" in ORD and "{% elif g.total > 0 %}" in ORD, _gr[:300])
check("S2 «Muddati o'tgan» / «Bugun muddati» / «Ertaga muddati» belgisi — guruh sarlavhasida, buyurtma qatorida, ustuvor (pin) qatorida YO'Q; "
      "`data-urgency` qatorlarda qoladi (filtr)",
      _gr and _qb and _pin and not any(w in _izohsiz(_gr + _qb + _pin) for w in MUDDAT_SOZ) and "pg-belgi" not in _izohsiz(_gr)
      and "urgencyText" not in _pin and 'data-urgency="{{ urgency }}"' in _qb and 'data-urgency="${urg}"' in _pin)
check("S3 filtr «Muddati o'tgan» / «Bugun» o'sha (`data-f=\"otgan\"`, `d.urgency === 'overdue'`)",
      "royxatFiltrla('otgan')\">Muddati o'tgan" in ORD and "otgan: d => d.urgency === 'overdue'" in ORD
      and "bugun: d => d.urgency === 'today'" in ORD)
_css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
check("S4 CSS: karta (`.ord-list .proj-group` — oraliq 8 px, yumaloq 12 px), to'lov chizig'i (`data-pul` — yashil / qizil, standart kulrang)",
      ".ord-list .proj-group{margin:0 10px 8px;background:var(--white);border:1px solid var(--border);border-radius:12px;" in _css
      and '.proj-group[data-pul="tolangan"] > .proj-head{box-shadow:inset 4px 0 0 var(--m-15803d)}' in _css
      and '.proj-group[data-pul="qarz"] > .proj-head{box-shadow:inset 4px 0 0 var(--m-dc2626)}' in _css
      and "box-shadow:inset 4px 0 0 var(--border)}" in _css)
check("S5 CSS: muddat chizig'i qoidalari (`[data-urgency=...]` — guruh, qator, tanlangan qator) va papka quloq'i (`.proj-group.open::before`) YO'Q",
      "[data-urgency=" not in _css and ".proj-group.open::before" not in _css and ".pg-belgi" not in _css)
check("S6 CSS: ochiq loyiha — ko'k chegara 1,5 px, och ko'k sarlavha, ichki buyurtmalar — oq karta (oraliq 6 px, yumaloq 10 px)",
      ".ord-list .proj-group.open{border:1.5px solid var(--gold);" in _css
      and ".proj-group.open > .proj-head, .proj-group.open > .proj-head:hover{background:var(--f-eff6ff)}" in _css
      and "border:1px solid var(--border);border-radius:10px;margin-top:6px;" in _css)

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
    auth.create_user(s, "r260_a", PAROL, UserRole.ADMIN, "R260 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="R260 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
PT = Project(company_id=1, client_name="Tillo aka", project_name="NAYMAN KOCHA R260", client_phone="+998901112233", total_budget=0, total_paid=0)
PQ = Project(company_id=1, client_name="Oltinko'l", project_name="OLTINKOL MASJID R260", client_phone="+998935554411", total_budget=0,
             total_paid=0)
PB = Project(company_id=1, client_name="Yangi mijoz", project_name="QORALAMA R260", client_phone="+998935554412", total_budget=0, total_paid=0)
US = Master(company_id=1, name="R260 Usta", phone="+998900002600")
s.add_all([PENO, PT, PQ, PB, US])
s.commit()
ID = {"PENO": PENO.id, "PT": PT.id, "PQ": PQ.id, "PB": PB.id, "US": US.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lg = C.post("/login", data={"username": "r260_a", "password": PAROL}, follow_redirects=False)
TK = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).date()


def kun(n):
    return (TK + datetime.timedelta(days=n)).isoformat()


def buyurtma(pid, muddat, miqdor, narx, qoralama=False):
    tana = {"project_id": pid, "order_type": "product", "recipe_id": None, "master_id": ID["US"], "deadline": muddat, "is_draft": qoralama,
            "base_price": 600000, "loy_kg": None,
            "items": [{"name": "R260 panel", "category": "panel", "width": 60, "thickness": 5, "length": 0, "quantity": miqdor,
                       "unit_price": narx, "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}]}
    r = C.post("/api/orders", json=tana)
    if r.status_code == 409:
        r = C.post("/api/orders?confirm_shortage=true", json=tana)
    return (r.json() or {}).get("id") if r.status_code == 200 else None


def tolov(oid, summa, tur="partial"):
    return C.post("/api/payments", json={"order_id": oid, "amount": summa, "payment_type": tur, "payment_method": "naqd", "notes": "R260"})


O = {"tolangan": buyurtma(ID["PT"], kun(-3), 12, 25000),        # 300 000 — muddati o'tgan, lekin to'liq to'langan
     "qarzli": buyurtma(ID["PQ"], kun(-4), 20, 22000),          # 440 000 — muddati o'tgan, qarzi bor
     "bugun": buyurtma(ID["PQ"], kun(0), 10, 15000),            # bugun muddati, qarzi bor
     "qoralama": buyurtma(ID["PB"], kun(5), 8, 18000, qoralama=True)}
_am = []
if all(O.values()):
    _am.append(tolov(O["tolangan"], 300000, "final").status_code)
    _am.append(tolov(O["qarzli"], 100000, "zaklat").status_code)
    _am.append(C.post(f"/api/orders/{O['qarzli']}/pin").status_code)
INFO = {k: (C.get(f"/api/orders/{v}").json() if v else {}) for k, v in O.items()}
NUM = {k: v.get("order_number") for k, v in INFO.items()}
check("0.1 fikstura: kirish, 4 buyurtma (to'langan, qarzli muddati o'tgan, bugungi, qoralama), to'lovlar, pin — 200",
      _lg.status_code in (302, 303) and all(O.values()) and _am and all(x == 200 for x in _am)
      and float(INFO["tolangan"].get("debt_amount") or 0) <= 0 and float(INFO["qarzli"].get("debt_amount") or 0) > 0, (O, _am))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Sahifa (HTTP)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
H = C.get("/orders").text


def guruh_pul(pid):
    m = re.search(r'<div class="proj-group" data-project-id="%d"[^>]*?data-pul="([a-z]+)"' % pid, H, re.S)
    return m.group(1) if m else None


check("H1 `data-pul`: to'langan loyiha — tolangan, qarzli — qarz, qoralama (qiymati yo'q) — yoq",
      guruh_pul(ID["PT"]) == "tolangan" and guruh_pul(ID["PQ"]) == "qarz" and guruh_pul(ID["PB"]) == "yoq",
      (guruh_pul(ID["PT"]), guruh_pul(ID["PQ"]), guruh_pul(ID["PB"])))
_ol = H[H.find('<div class="ord-list">'):H.find("<!-- Yangi buyurtma tugmasi -->")]      # ro'yxat — «Yangi buyurtma» tugmasigacha
check("H2 ro'yxatda (`.ord-list`) «Muddati o'tgan» / «Bugun muddati» / «Ertaga muddati» matni yo'q; muddati o'tgan qator "
      "`data-urgency=\"overdue\"`, bugungisi — `today` (filtr shundan)",
      '<div class="ord-list">' in H and not any(w in _ol for w in MUDDAT_SOZ)
      and re.search(r'id="oi-%d"[^>]*data-urgency="overdue"' % O["qarzli"], H, re.S)
      and re.search(r'id="oi-%d"[^>]*data-urgency="today"' % O["bugun"], H, re.S), [w for w in MUDDAT_SOZ if w in _ol])
check("H3 filtr tugmasi «Muddati o'tgan» sahifada (ro'yxatdan tashqarida)",
      "royxatFiltrla('otgan')\">Muddati o'tgan" in H and H.find("royxatFiltrla('otgan')") < H.find('<div class="ord-list">'))

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
RASM = os.environ.get("R260_RASM")

OLCH = """() => {
  const L = document.querySelector('.ord-list'); const gs = [...L.querySelectorAll(':scope > .proj-group')];
  const r = e => e.getBoundingClientRect();
  const oraliq = gs.slice(1).map((g, i) => Math.round((r(g).top - r(gs[i]).bottom) * 10) / 10);
  const guruh = gs.map(g => { const h = g.querySelector('.proj-head'); const cs = getComputedStyle(g); const hs = getComputedStyle(h);
     const bf = getComputedStyle(g, '::before');
     return {pid: g.dataset.projectId, pul: g.dataset.pul, ochiq: g.classList.contains('open'), radius: parseFloat(cs.borderTopLeftRadius),
             chiziq: hs.boxShadow, chegara: cs.borderTopColor, chegaraEn: parseFloat(cs.borderTopWidth), fon: hs.backgroundColor,
             quloq: bf.content, eni: Math.round(r(g).width)}; });
  const ichki = [...L.querySelectorAll('.proj-group.open > .proj-body .ord-item')];
  const ichOraliq = ichki.slice(1).map((x, i) => Math.round((r(x).top - r(ichki[i]).bottom) * 10) / 10);
  const tanl = L.querySelector('.ord-item.active');
  const matn = L.innerText + ' | ' + ((document.getElementById('pinnedOrdersList') || {}).innerText || '');
  const filtr = [...document.querySelectorAll('.ord-f')].map(x => x.innerText).join(' | ');
  const muddatSoni = (matn.match(/Muddati o'tgan/g) || []).length;
  return {oraliq, guruh, ichOraliq, ichRadius: ichki.map(x => parseFloat(getComputedStyle(x).borderTopLeftRadius)),
          tanl: tanl ? {ochiq: getComputedStyle(tanl, '::before').content, soya: getComputedStyle(tanl).boxShadow} : null,
          muddatSoni, bugunSoni: (matn.match(/Bugun muddati|Ertaga muddati/g) || []).length, filtr,
          surilish: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1}; }"""
J = {}
XATO = []
try:
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for nom, w, h, tungi in (("kompyuter", 1440, 900, False), ("telefon", 390, 844, False), ("tungi", 1440, 900, True)):
            ctx = br.new_context(viewport={"width": w, "height": h})
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:200]))
            pg.goto(BU + "/login", wait_until="networkidle")
            pg.fill("input[name=username]", "r260_a")
            pg.fill("input[name=password]", PAROL)
            pg.click("button[type=submit]")
            pg.wait_for_load_state("networkidle")
            pg.goto(BU + "/orders", wait_until="networkidle")
            if tungi:
                pg.evaluate("() => document.documentElement.setAttribute('data-theme', 'dark')")
            pg.wait_for_timeout(300)
            J[(nom, "yopiq")] = pg.evaluate(OLCH)
            pg.evaluate(f"() => toggleProject({ID['PQ']})")
            pg.wait_for_timeout(300)
            pg.locator(f".proj-group[data-project-id='{ID['PQ']}'] #oi-{O['qarzli']}").first.click()
            pg.wait_for_timeout(800)
            J[(nom, "ochiq")] = pg.evaluate(OLCH)
            if RASM:
                pg.locator(".ord-list").first.screenshot(path=os.path.join(RASM, f"royxat_{nom}.png"))
            if nom == "kompyuter":
                pg.click("button.ord-f[data-f='otgan']")
                pg.wait_for_timeout(400)
                J["filtr"] = pg.evaluate("""() => [...document.querySelectorAll('.ord-list .ord-item')].filter(x => x.offsetParent !== null)
                                           .map(x => x.dataset.urgency)""")
            ctx.close()
        br.close()
except Exception as e:                     # noqa: BLE001
    J["xato"] = f"{type(e).__name__}: {e}"


def rang(sh, rgb):
    return isinstance(sh, str) and rgb in sh.replace(" ", "")


def _guruh(v, pid):
    return next((x for x in (v or {}).get("guruh", []) if x["pid"] == str(pid)), None)


_k = J.get(("kompyuter", "yopiq"))
check("J1 kompyuter: loyihalar — alohida kartalar: orasi ≥ 6 px, yumaloq ≥ 10 px; to'langan — yashil chiziq (#15803D), qarzli — qizil "
      "(#DC2626), qoralama — kulrang", _k and len(_k["guruh"]) == 3 and all(x >= 6 for x in _k["oraliq"])
      and all(g["radius"] >= 10 for g in _k["guruh"])
      and rang(_guruh(_k, ID["PT"])["chiziq"], "rgb(21,128,61)") and rang(_guruh(_k, ID["PQ"])["chiziq"], "rgb(220,38,38)")
      and not rang(_guruh(_k, ID["PB"])["chiziq"], "rgb(220,38,38)") and not rang(_guruh(_k, ID["PB"])["chiziq"], "rgb(21,128,61)"),
      (J.get("xato"), _k))
check("J2 ro'yxat va «Ustuvor buyurtmalar» ko'rinadigan matnida «Muddati o'tgan» / «Bugun muddati» / «Ertaga muddati» yo'q (yopiq va "
      "ochilganda; muddati o'tgan va bugungi qarzli buyurtmalar bor); filtr tugmasi «Muddati o'tgan» ko'rinadi",
      _k and _k["muddatSoni"] == 0 and _k["bugunSoni"] == 0 and J.get(("kompyuter", "ochiq"))
      and J[("kompyuter", "ochiq")]["muddatSoni"] == 0 and J[("kompyuter", "ochiq")]["bugunSoni"] == 0 and "Muddati o'tgan" in _k["filtr"],
      (_k and (_k["muddatSoni"], _k["bugunSoni"], _k["filtr"])))
_o = J.get(("kompyuter", "ochiq"))
_og = _guruh(_o, ID["PQ"])
check("J3 ochilgan loyiha: ko'k chegara (1,5 px — 1× ekranda Chromium 1 px chizadi), och ko'k sarlavha, papka quloq'i YO'Q, chap chiziq — to'lov (qizil); boshqa kartalar bilan "
      "orasi ≥ 6 px", _og and _og["ochiq"] and _og["chegaraEn"] >= 1 and _og["chegara"] == "rgb(37, 99, 235)" and _og["fon"] == "rgb(239, 246, 255)"
      and _og["quloq"] in ("none", "normal") and rang(_og["chiziq"], "rgb(220,38,38)") and all(x >= 6 for x in _o["oraliq"]), _o)
check("J4 ochiq loyiha ichidagi buyurtmalar — alohida kartalar (oraliq ≥ 5 px, yumaloq ≥ 9 px); tanlangan — «▶ OCHIQ» va 3 px ramka, "
      "muddat chizig'i (qizil) YO'Q", _o and len(_o["ichOraliq"]) >= 1 and all(x >= 5 for x in _o["ichOraliq"])
      and all(x >= 9 for x in _o["ichRadius"]) and _o["tanl"] and "OCHIQ" in _o["tanl"]["ochiq"]
      and "rgb(220, 38, 38)" not in _o["tanl"]["soya"] and "3px" in _o["tanl"]["soya"], _o)
check("J5 «Muddati o'tgan» filtri: faqat muddati o'tgan buyurtmalar qoladi (filtr `data-urgency` dan — avvalgidek)",
      J.get("filtr") and all(x == "overdue" for x in J["filtr"]), J.get("filtr"))
_t, _to = J.get(("telefon", "yopiq")), J.get(("telefon", "ochiq"))
check("J6 telefon (390): kartalar orasi ≥ 6 px, chiziq ranglari o'sha, ochilganda ham gorizontal surilish yo'q",
      _t and _to and all(x >= 6 for x in _t["oraliq"]) and rang(_guruh(_t, ID["PT"])["chiziq"], "rgb(21,128,61)")
      and not _t["surilish"] and not _to["surilish"] and _guruh(_to, ID["PQ"])["ochiq"], (_t, _to and _to["surilish"]))
_q = J.get(("tungi", "ochiq"))
check("J7 tungi rejim: karta foni to'q (sahifa bilan bir xil emas — ajralib turadi), chiziq ranglari bor, ochiq loyiha ko'k chegarada",
      _q and _guruh(_q, ID["PQ"])["ochiq"] and _guruh(_q, ID["PT"])["fon"] not in ("rgb(255, 255, 255)",)
      and rang(_guruh(_q, ID["PT"])["chiziq"], "rgb(") and _guruh(_q, ID["PQ"])["chegaraEn"] >= 1
      and _guruh(_q, ID["PQ"])["chegara"] != _guruh(_q, ID["PT"])["chegara"], _q)
check("J8 sahifalarda JS xatosi yo'q", not XATO and "xato" not in J, (XATO[:3], J.get("xato")))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _f in FAILED:
        print("  " + _f)
sys.exit(1 if FAIL else 0)
