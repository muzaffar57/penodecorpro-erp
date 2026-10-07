#!/usr/bin/env python3
"""
test_e_royxat.py — kech120, E BOSQICH 2-qism (KATTA RO'YXATLAR — topish): Bosh sahifa «Bugungi vazifalar», Buyurtmalar ro'yxati
(holat filtri, keng qidiruv, shoshilinchlar tepada, qayta yuklanganda tanlov tiklanadi, yangi buyurtma ochiq holda), Qarzdorlar
(mijoz bo'yicha guruh, qidiruv, «Muddati o'tgan»).

NIMA UCHUN KERAK (audit kech114, «Katta Korxona» — 300 buyurtma / 60 loyiha; HAQIQIY brauzerda o'lchangan):
  G1-11  «Bugungi vazifalar» cheksiz (14 qator sahifa tepasini to'ldirardi), qatorlarni bosib bo'lmasdi, «119 ta buyurtma muddati
         o'tgan» — faqat son, qaysilari ekanini ko'rish yo'li yo'q.
  G2-13  Buyurtmalar: faqat yopiq loyiha guruhlari, «muddati o'tgan» / «bugun» / «ertaga» aralash, holat filtri yo'q; qidiruv 100 px,
         faqat raqam / mijoz / loyiha (telefon, detal, usta emas); har saqlash / to'lov / topshirishdan keyin tanlangan buyurtma va
         ochiq guruhlar yo'qolardi; yangi buyurtma qaytadan qidirilardi.
  G3-07  Qarzdorlar: «Bizga qarzdorlar (288)» — har buyurtma alohida, bir mijoz turli joyda, qidiruv / filtr / «muddati o'tgan»
         yo'q; sarlavhadagi son mijozlar emas; bo'sh korxonada «Barcha mijozlar to'liq to'lagan!».
BO'LIMLAR: S — statik; M — ma'lumot (brauzerda dasturning o'z API si: 3 loyiha / 3 mijoz, muddati bugun 7 ta, o'tgan 3 ta, ertaga 2 ta,
  bugun-«Tayyor» 1 ta, 7 kam qolgan material, ustalar, to'lovlar); V — `/api/dashboard/today-tasks`; O — Buyurtmalar sahifasi (server
  HTML va brauzer: filtr sonlari, filtrlar, qidiruv, «?royxat=», qayta yuklash, yangi ochilish, guruh tartibi); Q — Qarzdorlar (guruhlar,
  jami, tartib, qidiruv, filtr, qayta yuklash, havola; bo'sh korxona); T — telefon 390 px (ekrandan chiqmaydi); X — JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 127) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_e_royxat.py
"""
import os
import re
import sys
import io
import json
import glob
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
PG_BAZA = "e_royxat_test"
_T = tempfile.mkdtemp(prefix="eroy_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'e_royxat_test.db')}"
os.environ.pop("TENANT_FILTER", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Order                 # noqa: E402

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


def tartibda(src, *qismlar):
    p = 0
    for q in qismlar:
        i = src.find(q, p)
        if i < 0:
            return False
        p = i + len(q)
    return True


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
SV = oqi("services.py")
MAIN = oqi("main.py")
HOME = oqi("templates/home.html")
INV = oqi("templates/inventory.html")
ORD = oqi("templates/orders.html")
DBT = oqi("templates/debts.html")
check("S1 `get_today_tasks`: chegara 5, har qatorda `href`, bugungi ro'yxatda «Tayyor» yo'q (muddati o'tganlar va filtr bilan BIR qoida)",
      "BUGUNGI_VAZIFA_CHEGARA = 5" in SV and '"href": f"/orders?order={o.id}"' in SV and '"href": "/orders?royxat=bugun"' in SV
      and '"href": "/orders?royxat=otgan"' in SV and '"href": "/inventory?kam=1"' in SV
      and "Order.status.notin_([OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.READY]),\n        Order.is_deleted.isnot(True)\n    ).order_by(Order.deadline, Order.id)" in SV)
check("S2 Bosh sahifa: vazifa qatori — havola (faqat `/orders` / `/inventory`, matn escape); Ombor `?kam=1` — kam qolganlar",
      "vazifa-havola" in HOME and r"/^\/(orders|inventory)(\?[\w=&]*)?$/" in HOME and "get('kam') === '1'" in INV and "kamQolganlarniKorsat();" in INV)
check("S3 Buyurtmalar sahifasi: guruhlar — shoshilinch tepada (muddati o'tgan → bugun → ertaga, barqaror saralash)",
      '_shoshilinch = {"overdue": 0, "today": 1, "tomorrow": 2}' in MAIN
      and 'grouped.sort(key=lambda g: min((_shoshilinch.get(x.deadline_urgency, 3) for x in g["orders"]), default=3))' in MAIN)
check("S4 orders.html: filtr tugmalari, qator `data-urgency` / `data-qarz` / `data-phone` / `data-items`, filtr + qidiruv bitta funksiyada",
      'id="ordFiltr"' in ORD and 'data-urgency="{{ urgency }}"' in ORD and "data-qarz=" in ORD and "data-phone=" in ORD and "data-items=" in ORD
      and "function royxatniQoll()" in ORD and "const ROYXAT_FILTRLARI = {" in ORD and 'id="ordQidiruv"' in ORD)
check("S5 orders.html: qayta yuklanganda tiklash (`sessionStorage`, navigatsiya turi «reload»), yangi buyurtma — `/orders?order=ID`; "
      "o'qilmaydigan `localStorage` yozuvlari (`last_order`, `proj_`) yo'q",
      "function tanlovniTikla()" in ORD and "n.type === 'reload'" in ORD and "window.location.href = '/orders?order=' + Number(saved.id)" in ORD
      and "localStorage.setItem('last_order'" not in ORD and "localStorage.setItem('proj_'" not in ORD)
check("S6 Qarzdorlar: server — mijoz guruhlari (tiyin aniq jami), muddati o'tgan, `buyurtma_bor`; shablon — guruh, qidiruv, filtr, havola ID bilan",
      '"mijoz_guruhlari": mijoz_guruhlari' in MAIN and "o.qarz_muddati_otgan = bool(" in MAIN and '"buyurtma_bor": buyurtma_bor' in MAIN
      and 'class="dbt-mijoz' in DBT and 'id="qarzQidiruv"' in DBT and "function qarzRoyxatiniQoll()" in DBT
      and "/orders?order=${encodeURIComponent(d.id)}" in DBT and "Hali buyurtma yo'q" in DBT)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Ma'lumot — brauzerda dasturning o'z API si orqali")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "eroy_admin", "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, ADMIN, PAROL, UserRole.ADMIN, "Namuna Dekor", company_id=1)
s.close()

try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
check("M0 Python `playwright` bor", PW_BOR, _pw_x)

import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


port = _port()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
th = threading.Thread(target=server.run, daemon=True)
th.start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
check("M1 lokal server ishga tushdi", server.started)
B = f"http://127.0.0.1:{port}"
TK = datetime.utcnow() + timedelta(hours=5)
BUGUN = TK.strftime("%Y-%m-%d")
ERTAGA = (TK + timedelta(days=1)).strftime("%Y-%m-%d")
KECHA = (TK - timedelta(days=3)).strftime("%Y-%m-%d")
KEYIN = (TK + timedelta(days=10)).strftime("%Y-%m-%d")

MALUMOT_JS = r"""async (K) => {
  const L = [];
  const so = async (usul, url, tana) => {
    const o = {method: usul, cache: 'no-store'};
    if (tana !== undefined) { o.headers = {'Content-Type': 'application/json'}; o.body = JSON.stringify(tana); }
    let r; try { r = await fetch(url, o); } catch (e) { return {st: 599, t: String(e), j: null}; }
    const t = await r.text(); let j = null; try { j = JSON.parse(t); } catch (e) { j = null; }
    return {st: r.status, t, j};
  };
  const q = async (nom, usul, url, tana) => { const r = await so(usul, url, tana); L.push([nom, r.st, String(r.t || '').slice(0, 160)]); return r; };
  const id = r => r && r.j && (r.j.id || (r.j.project && r.j.project.id) || (r.j.order && r.j.order.id));
  const peno = id(await q('peno', 'POST', '/api/inventory', {item_name: 'ER Penoplast 15', category: 'Penoplast', unit: 'blok', stock_quantity: 50,
    min_stock: 0, is_penoplast: true, is_default_penoplast: true, volume_per_unit: 1.0, price_per_unit: 600000}));
  for (let i = 1; i <= 7; i++) {
    await q('kam' + i, 'POST', '/api/inventory', {item_name: 'ER Kam material ' + i, category: 'Boshqa', unit: 'kg', stock_quantity: i % 2 ? 0 : 3,
      min_stock: 10, price_per_unit: 1000, is_penoplast: false, is_default_penoplast: false, volume_per_unit: 1.0});
  }
  const usta = id(await q('usta', 'POST', '/api/masters', {name: 'Toshpo‘latov Ustaboy', phone: '+998901112233', cashback_percent: 5, kpi_percent: 0,
    region: 'Andijon', notes: ''}));
  const loy = [];
  const mijozlar = [['ER Loyiha Alfa', 'Alijon Valiyev', '+998 90 123 45 67'], ['ER Loyiha Beta', 'Bahodir Karimov', '+998 93 765 43 21'],
                    ['ER Loyiha Gamma', 'Gulnora Saidova', '+998 97 555 11 22']];
  for (const [p, c, t] of mijozlar) loy.push(id(await q('loyiha', 'POST', '/api/projects', {project_name: p, client_name: c, client_phone: t,
    client_address: 'Andijon', description: '', notes: ''})));
  const yarat = async (nom, pid, muddat, detal, ustami) => {
    const tana = {project_id: pid, order_type: 'product', recipe_id: null, master_id: ustami ? usta : null, deadline: muddat, is_draft: false,
      base_price: 600000, loy_kg: null, items: [{name: detal, category: 'profil', width: 10, thickness: 10, length: 20, quantity: 1, unit_price: 50000,
      is_coated: false, penoplast_id: peno, price_per_m3: null, finished_product_id: null, sub_details: []}]};
    let r = await so('POST', '/api/orders', tana);
    if (r.st === 409) r = await so('POST', '/api/orders?confirm_shortage=true', tana);
    L.push([nom, r.st, String(r.t || '').slice(0, 160)]);
    return id(r);
  };
  const I = {bugun: [], otgan: [], ertaga: [], keyin: [], tayyor_bugun: null};
  for (let i = 0; i < 7; i++) I.bugun.push(await yarat('bugun' + i, loy[i % 3], K.bugun, 'Bugungi karniz ' + i, i === 2));
  for (let i = 0; i < 3; i++) I.otgan.push(await yarat('otgan' + i, loy[i % 3], K.kecha, 'Kechikkan panel ' + i, false));
  for (let i = 0; i < 2; i++) I.ertaga.push(await yarat('ertaga' + i, loy[1], K.ertaga, 'Ertangi ustun ' + i, false));
  I.keyin.push(await yarat('keyin0', loy[2], K.keyin, 'Keyingi dekor 0', false));
  I.tayyor_bugun = await yarat('tayyor_bugun', loy[0], K.bugun, 'Tayyor bugungi 0', false);
  await q('tayyor', 'POST', '/api/orders/' + I.tayyor_bugun + '/ready');
  // to'lovlar: «Keyingi dekor 0» — to'liq (qarzi yo'q); qolganlari qisman / to'lovsiz
  await q('tolov_toliq', 'POST', '/api/payments', {order_id: I.keyin[0], amount: 50000, payment_type: 'final', payment_method: 'naqd', notes: 'er'});
  await q('tolov_qism', 'POST', '/api/payments', {order_id: I.bugun[0], amount: 10000, payment_type: 'partial', payment_method: 'naqd', notes: 'er'});
  return {L, I, loy, usta, yiqilgan: L.filter(x => !(typeof x[1] === 'number' && x[1] >= 200 && x[1] < 300))};
}"""

NAT = {}
pw_ctx = None
br = None
if PW_BOR and server.started:
    pw_ctx = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*", "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        check("M2 Chromium ishga tushdi", False, f"{type(_e).__name__}: {_e}")


def yonalish(route):
    return route.fulfill(status=204, body="")


def kontekst(w=1280, h=900, tel=False, user=ADMIN, parol=PAROL):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=tel, has_touch=tel,
                         timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|cdn\.jsdelivr\.net|unpkg\.com)/.*"),
              yonalish)
    pg = ctx.new_page()
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", parol)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


def jsq(pg, kod, arg=None):
    try:
        return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
    except Exception as ex:                # noqa: BLE001
        return {"js_xato": f"{type(ex).__name__}: {str(ex)[:300]}"}


def bor(pg, url, kut=500):
    try:
        pg.goto(B + url, wait_until="networkidle")
        pg.wait_for_timeout(kut)
        return True
    except Exception as ex:                # noqa: BLE001
        return f"{type(ex).__name__}: {str(ex)[:200]}"


CTX = PG = None
DATA = {}
JS_XATO = []
if br:
    CTX, PG = kontekst()
    PG.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    check("M2 kirish", "/login" not in PG.url, PG.url)
    DATA = jsq(PG, MALUMOT_JS, {"bugun": BUGUN, "kecha": KECHA, "ertaga": ERTAGA, "keyin": KEYIN}) or {}
    check("M3 ma'lumot: hamma qadam 2xx (3 loyiha, 7 bugungi, 3 kechikkan, 2 ertangi, 1 keyingi, 1 bugun-«Tayyor», 7 kam material, to'lovlar)",
          isinstance(DATA, dict) and not DATA.get("yiqilgan") and len((DATA.get("I") or {}).get("bugun") or []) == 7, DATA.get("yiqilgan") or DATA)
I = DATA.get("I") or {}


def api(url):
    r = jsq(PG, "async (u) => { const r = await fetch(u, {cache: 'no-store'}); return {s: r.status, t: await r.text()}; }", B + url) if PG else {}
    try:
        return r.get("s"), json.loads(r.get("t") or "null")
    except Exception:                      # noqa: BLE001
        return r.get("s"), r.get("t")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("V. Bosh sahifa «Bugungi vazifalar» — `/api/dashboard/today-tasks`")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_st, TT = api("/api/dashboard/today-tasks")
TT = TT if isinstance(TT, list) else []
_bug = [t for t in TT if "bugun topshirilishi kerak" in (t.get("text") or "") and not (t.get("text") or "").startswith("yana")]
_kut_bug = sorted(I.get("bugun") or [])[:5]
check("V1 bugungi buyurtmalar — 5 qator (7 tadan), har biri o'z buyurtmasiga havola (`/orders?order=ID`, muddat / id tartibida)",
      [t.get("href") for t in _bug] == [f"/orders?order={x}" for x in _kut_bug], [TT, _kut_bug])
_yana = [t for t in TT if (t.get("text") or "").startswith("yana 2 ta buyurtma bugun")]
check("V2 qolgan 2 tasi — bitta «yana 2 ta …» qatori → `/orders?royxat=bugun`", len(_yana) == 1 and _yana[0].get("href") == "/orders?royxat=bugun", TT)
check("V3 bugun-«Tayyor» buyurtma bugungi ro'yxatda YO'Q (yakunlangan — filtr bilan bir qoida)",
      not any(f"order={I.get('tayyor_bugun')}" in (t.get("href") or "") for t in TT) and len(_bug) + 2 == 7, TT)
_otg = [t for t in TT if "muddati o'tgan" in (t.get("text") or "")]
check("V4 muddati o'tgan — «3 ta buyurtma muddati o'tgan» → `/orders?royxat=otgan`",
      len(_otg) == 1 and _otg[0].get("text", "").startswith("3 ta") and _otg[0].get("href") == "/orders?royxat=otgan", _otg)
_kam = [t for t in TT if re.search(r"ER Kam material \d (kam qolgan|tugagan) \(", t.get("text") or "")]
_kamy = [t for t in TT if (t.get("text") or "").startswith("yana 2 ta material kam qolgan")]
check("V5 kam qolgan xomashyo — 5 qator (7 tadan) + «yana 2 ta material …», hammasi `/inventory?kam=1`",
      len(_kam) == 5 and len(_kamy) == 1 and all(t.get("href") == "/inventory?kam=1" for t in _kam + _kamy), TT)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("O. Buyurtmalar sahifasi — filtr, qidiruv, «?royxat=», qayta yuklash, guruh tartibi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
class _B:
    """Buyurtma ma'lumoti (sessiya yopilgandan keyin ham o'qiladi)."""
    def __init__(self, o):
        self.id = o.id
        self.project_id = o.project_id
        self.client_name = o.project.client_name if o.project else None
        self.status = o.status.value
        self.debt = float(o.debt_amount or 0)
        self.deadline = o.deadline
        self.urgency = crud.get_deadline_urgency(o.deadline, o.status.value, o.is_fully_delivered)


s = SessionLocal()
_hamma = [_B(o) for o in s.query(Order).filter(Order.company_id == 1, Order.is_deleted.isnot(True)).all()]
s.close()
_urg = {o.id: o.urgency for o in _hamma}
_kutilgan_son = {"hammasi": len(_hamma), "otgan": sum(1 for v in _urg.values() if v == "overdue"),
                 "bugun": sum(1 for v in _urg.values() if v == "today"),
                 "jarayonda": sum(1 for o in _hamma if o.status in ("new", "in_progress", "coating")),
                 "qarz": sum(1 for o in _hamma if o.debt > 0),
                 "tugagan": sum(1 for o in _hamma if o.status in ("ready", "delivered"))}
OLCH_JS = r"""() => ({
  sanoq: Object.fromEntries([...document.querySelectorAll('#ordFiltr [data-f]')].map(b => [b.dataset.f, Number((b.querySelector('.f-son') || {}).textContent)])),
  faol: (document.querySelector('#ordFiltr .active') || {}).dataset ? document.querySelector('#ordFiltr .active').dataset.f : null,
  korinadi: [...document.querySelectorAll('.ord-list .ord-item')].filter(e => e.offsetParent !== null).map(e => Number(e.dataset.orderId)),
  guruh_korinmas: [...document.querySelectorAll('.ord-list .proj-group')].filter(g => g.style.display === 'none').length,
  guruhlar: [...document.querySelectorAll('.ord-list .proj-group')].map(g => g.dataset.projectId),
  tanlangan: (document.querySelector('.ord-list .ord-item.active') || {}).id || null,
  ochiq: [...document.querySelectorAll('.ord-list .proj-group.open')].map(g => g.dataset.projectId),
  bosh: (document.getElementById('ordFiltrBosh') || {}).style ? document.getElementById('ordFiltrBosh').style.display : null,
  url: location.pathname + location.search,
  emptyMid: (document.getElementById('emptyMid') || {}).style ? document.getElementById('emptyMid').style.display : null})"""

if PG:
    bor(PG, "/orders")
    o0 = jsq(PG, OLCH_JS)
    check("O1 filtr tugmalaridagi sonlar = bazadagi (urgency — `crud.get_deadline_urgency`, qarz, holat)",
          isinstance(o0, dict) and o0.get("sanoq") == _kutilgan_son, [o0.get("sanoq") if isinstance(o0, dict) else o0, _kutilgan_son])
    _pid_urg = {}
    for _o in _hamma:
        _r = {"overdue": 0, "today": 1, "tomorrow": 2}.get(_o.urgency, 3)
        _pid_urg[str(_o.project_id)] = min(_pid_urg.get(str(_o.project_id), 3), _r)
    _gl = (o0 or {}).get("guruhlar") or []
    check("O2 guruhlar tartibi — shoshilinchlik o'smaydi (muddati o'tgani bor guruh tepada)",
          len(_gl) >= 3 and [_pid_urg.get(x, 3) for x in _gl] == sorted(_pid_urg.get(x, 3) for x in _gl), [_gl, _pid_urg])
    _f = {}
    for _k, _pred in (("otgan", lambda o: _urg[o.id] == "overdue"), ("bugun", lambda o: _urg[o.id] == "today"),
                      ("jarayonda", lambda o: o.status in ("new", "in_progress", "coating")),
                      ("qarz", lambda o: o.debt > 0), ("tugagan", lambda o: o.status in ("ready", "delivered"))):
        jsq(PG, f"() => royxatFiltrla('{_k}')")
        _m = jsq(PG, OLCH_JS)
        _f[_k] = (sorted(_m.get("korinadi") or []), sorted(o.id for o in _hamma if _pred(o)))
    check("O3 har filtr: ko'rinadigan qatorlar AYNAN mos buyurtmalar (otgan, bugun, jarayonda, qarz, tugagan)",
          all(a == b and (b or k == "tugagan") for k, (a, b) in _f.items()), _f)
    jsq(PG, "() => royxatFiltrla('hammasi')")
    # qidiruv: telefon raqami (faqat raqamlar), detal nomi, usta, filtr bilan birga
    _q = {}
    for _nom, _soz in (("tel", "765 43"), ("tel_raqam", "93765"), ("detal", "Ertangi ustun"), ("usta", "toshpo")):
        jsq(PG, f"() => {{ const i = document.getElementById('ordQidiruv'); i.value = {json.dumps(_soz)}; searchOrders(i.value); }}")
        _q[_nom] = sorted((jsq(PG, OLCH_JS) or {}).get("korinadi") or [])
    _beta = sorted(o.id for o in _hamma if o.client_name == "Bahodir Karimov")
    check("O4 qidiruv — telefon («765 43» va faqat raqam «93765»): faqat shu mijoz buyurtmalari",
          _q.get("tel") == _beta and _q.get("tel_raqam") == _beta and _beta, [_q, _beta])
    check("O5 qidiruv — detal nomi («Ertangi ustun» — 2 ta) va usta («toshpo» — kichik harf bilan)",
          _q.get("detal") == sorted(I.get("ertaga") or []) and _q.get("usta") == [I["bugun"][2]] if I.get("bugun") else False, _q)
    jsq(PG, "() => { const i = document.getElementById('ordQidiruv'); i.value = 'Alijon'; searchOrders(i.value); royxatFiltrla('otgan'); }")
    _m = jsq(PG, OLCH_JS) or {}
    _alf_otg = sorted(o.id for o in _hamma if o.client_name == "Alijon Valiyev" and _urg[o.id] == "overdue")
    check("O6 qidiruv + filtr BIRGA (Alijon + muddati o'tgan)", sorted(_m.get("korinadi") or []) == _alf_otg and _alf_otg, [_m.get("korinadi"), _alf_otg])
    jsq(PG, "() => { const i = document.getElementById('ordQidiruv'); i.value = 'zzzyyy'; searchOrders(i.value); }")
    _m = jsq(PG, OLCH_JS) or {}
    check("O7 hech narsa topilmasa — «… buyurtma yo'q» xabari, hamma guruh yashirin", _m.get("bosh") == "block" and not _m.get("korinadi")
          and _m.get("guruh_korinmas") == len(_m.get("guruhlar") or []), _m)
    # «?royxat=otgan» — Bosh sahifa havolasi
    bor(PG, "/orders?royxat=otgan")
    _m = jsq(PG, OLCH_JS) or {}
    check("O8 «/orders?royxat=otgan»: filtr yoqildi, faqat muddati o'tganlar, manzil tozalandi",
          _m.get("faol") == "otgan" and sorted(_m.get("korinadi") or []) == sorted(I.get("otgan") or []) and _m.get("url") == "/orders", _m)
    # Qayta yuklash — tanlov, ochiq guruhlar, filtr tiklanadi; yangi ochilishda — yo'q
    bor(PG, "/orders")
    _tan = I["ertaga"][0] if I.get("ertaga") else None
    jsq(PG, f"""() => {{ royxatFiltrla('qarz'); const el = document.querySelector('.ord-list #oi-{_tan}'); openProject(el.dataset.projectId);
                       selectOrder({_tan}, el); }}""")
    _oldin = jsq(PG, OLCH_JS) or {}
    try:
        PG.reload(wait_until="networkidle")
        PG.wait_for_timeout(600)
    except Exception:                      # noqa: BLE001
        pass
    _keyin = jsq(PG, OLCH_JS) or {}
    check("O9 qayta yuklangach (to'lov / saqlashdan keyingi `location.reload()` kabi): tanlangan buyurtma, ochiq guruhlar va filtr TIKLANDI",
          _keyin.get("tanlangan") == f"oi-{_tan}" and _keyin.get("faol") == "qarz" and set(_oldin.get("ochiq") or []) <= set(_keyin.get("ochiq") or [])
          and _keyin.get("emptyMid") == "none", [_oldin, _keyin])
    bor(PG, "/orders")
    _yangi = jsq(PG, OLCH_JS) or {}
    check("O10 yangi ochilishda (havola / menyu) — hech narsa avtomatik tanlanmaydi, filtr «Hammasi»",
          _yangi.get("tanlangan") is None and _yangi.get("faol") == "hammasi" and _yangi.get("emptyMid") != "none", _yangi)
    _ah = jsq(PG, """() => [...document.querySelectorAll('.ord-list .ord-item')].slice(0, 400).every(e => e.dataset.urgency && (e.dataset.qarz === '0' || e.dataset.qarz === '1'))""")
    check("O11 har qatorda `data-urgency` va `data-qarz`", _ah is True, _ah)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Qarzdorlar — mijoz guruhlari, qidiruv, «Muddati o'tgan», qayta yuklash, havola, bo'sh korxona")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_qarzli = [o for o in _hamma if o.debt > 0.5 and o.status != "draft"]
_mijoz = {}
for _o in _qarzli:
    _mijoz.setdefault(_o.client_name, []).append(_o)
_jami = {k: round(sum(x.debt for x in v), 2) for k, v in _mijoz.items()}
_otgan_q = sorted(_o.id for _o in _qarzli if _o.deadline is not None and _o.deadline.date() < TK.date())
QOLCH = r"""() => ({
  tab: (document.querySelector('.dbt-tab[data-t="customers"]') || {}).textContent || '',
  guruh: [...document.querySelectorAll('#tab-customers .dbt-mijoz')].map(g => [g.dataset.mijoz,
         Number((g.querySelector('.dbt-mijoz-bosh .dbt-item-amount') || {}).textContent.replace(/[^0-9,]/g, '').replace(',', '.')),
         g.querySelectorAll('.dbt-item').length, g.classList.contains('ochiq'), g.style.display !== 'none']),
  korinadi: [...document.querySelectorAll('#tab-customers .dbt-item')].filter(e => e.offsetParent !== null).map(e => Number(e.dataset.id)),
  tanlangan: Number((document.querySelector('#tab-customers .dbt-item.active') || {dataset: {}}).dataset.id) || null,
  havola: ((document.querySelector('#cd-body a') || {}).getAttribute ? document.querySelector('#cd-body a').getAttribute('href') : null),
  bosh: (document.getElementById('qarzBosh') || {}).style ? document.getElementById('qarzBosh').style.display : null})"""
if PG:
    bor(PG, "/debts")
    q0 = jsq(PG, QOLCH) or {}
    _g = q0.get("guruh") or []
    check("Q1 sarlavha: «3 mijoz · N buyurtma»", f"({len(_mijoz)} mijoz · {len(_qarzli)} buyurtma)" in (q0.get("tab") or ""), [q0.get("tab"), len(_mijoz), len(_qarzli)])
    check("Q2 guruhlar: har mijoz BITTA guruh, jami qarz = buyurtmalari qarzi yig'indisi, buyurtmalar soni to'g'ri",
          len(_g) == len(_mijoz) and all(abs(x[1] - _jami.get(x[0], -1)) < 0.6 and x[2] == len(_mijoz.get(x[0], [])) for x in _g), [_g, _jami])
    check("Q3 guruhlar jami qarz kamayishi bo'yicha; birinchisi ochiq, uning birinchi buyurtmasi tanlangan",
          [x[1] for x in _g] == sorted((x[1] for x in _g), reverse=True) and _g and _g[0][3] and not any(x[3] for x in _g[1:])
          and q0.get("tanlangan") in [o.id for o in _mijoz.get(_g[0][0], [])], [_g, q0.get("tanlangan")])
    check("Q4 «Buyurtmalar sahifasida ochish →» — AYNAN shu buyurtma (`/orders?order=ID`)", q0.get("havola") == f"/orders?order={q0.get('tanlangan')}", q0.get("havola"))
    jsq(PG, "() => { const i = document.getElementById('qarzQidiruv'); i.value = '555 11'; qarzQidir(i.value); }")
    _m = jsq(PG, QOLCH) or {}
    _gul = sorted(o.id for o in _mijoz.get("Gulnora Saidova", []))
    check("Q5 qidiruv — telefon («555 11»): faqat shu mijoz guruhi, guruh ochildi",
          sorted(_m.get("korinadi") or []) == _gul and _gul and [x[0] for x in _m.get("guruh") or [] if x[4]] == ["Gulnora Saidova"], _m)
    jsq(PG, "() => { const i = document.getElementById('qarzQidiruv'); i.value = ''; qarzQidir(''); qarzFiltrla('otgan'); }")
    _m = jsq(PG, QOLCH) or {}
    check("Q6 «Muddati o'tgan» filtri — faqat topshirish muddati o'tgan qarzlar (= baza)", sorted(_m.get("korinadi") or []) == _otgan_q and _otgan_q,
          [_m.get("korinadi"), _otgan_q])
    _bel = jsq(PG, """() => [...document.querySelectorAll('#tab-customers .dbt-item')].filter(e => e.dataset.muddatOtgan === '1')
                         .every(e => /muddati o'tgan/.test(e.textContent))""")
    check("Q7 muddati o'tgan qatorda belgi («muddati o'tgan (sana)»)", _bel is True, _bel)
    jsq(PG, "() => { const i = document.getElementById('qarzQidiruv'); i.value = 'qwertyz'; qarzQidir(i.value); }")
    _m = jsq(PG, QOLCH) or {}
    check("Q8 topilmasa — xabar, guruhlar yashirin", _m.get("bosh") == "block" and not _m.get("korinadi"), _m)
    # qayta yuklash (to'lovdan keyingi kabi) — o'sha buyurtma; yangi ochilishda — birinchisi
    bor(PG, "/debts")
    _ikkinchi = _mijoz[_g[1][0]][0].id if len(_g) > 1 else None
    jsq(PG, f"() => selectOrderDebt(document.querySelector('#tab-customers .dbt-item[data-id=\"{_ikkinchi}\"]'))")
    try:
        PG.reload(wait_until="networkidle")
        PG.wait_for_timeout(500)
    except Exception:                      # noqa: BLE001
        pass
    _m = jsq(PG, QOLCH) or {}
    check("Q9 qayta yuklangach — oldin tanlangan buyurtma (ikkinchi mijoz) qayta tanlandi, guruhi ochiq",
          _m.get("tanlangan") == _ikkinchi and any(x[0] == _g[1][0] and x[3] for x in _m.get("guruh") or []), [_m.get("tanlangan"), _ikkinchi])
    bor(PG, "/debts")
    _m = jsq(PG, QOLCH) or {}
    check("Q10 yangi ochilishda — birinchi mijozning birinchi buyurtmasi", _m.get("tanlangan") == q0.get("tanlangan"), [_m.get("tanlangan"), q0.get("tanlangan")])
    # bo'sh korxona (buyurtmasi yo'q) — «Hali buyurtma yo'q»; buyurtmasi bor, qarzi yo'q korxona — «to'liq to'lagan»
    _pl = SessionLocal()
    try:
        from production_models import Company
        _c2 = Company(name="ER Bo'sh Korxona")
        _pl.add(_c2)
        _pl.commit()
        _c2id = _c2.id
    finally:
        _pl.close()
    s = SessionLocal()
    with contextlib.redirect_stdout(io.StringIO()):
        auth.create_user(s, "eroy_bosh", PAROL, UserRole.ADMIN, "Bo'sh Korxona", company_id=_c2id)
    s.close()
    _c2x, _p2 = kontekst(user="eroy_bosh")
    bor(_p2, "/debts")
    _bo = jsq(_p2, "() => document.querySelector('#tab-customers').innerText")
    _c2x.close()
    check("Q11 bo'sh korxonada (buyurtma yo'q) — «Hali buyurtma yo'q» (ilgari «Barcha mijozlar to'liq to'lagan!»)",
          isinstance(_bo, str) and "Hali buyurtma yo'q" in _bo and "to'liq to'lagan" not in _bo, _bo)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Bosh sahifa (brauzer) — vazifa qatori bosilsa o'sha joy ochiladi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG:
    bor(PG, "/")
    _hv = jsq(PG, "() => [...document.querySelectorAll('#tasksList > *')].map(e => [e.tagName, e.getAttribute('href')])") or []
    check("H1 bugungi vazifalar — havolalar (bugungi 5 + «yana», muddati o'tgan, kam qolganlar)",
          isinstance(_hv, list) and sum(1 for x in _hv if x[0] == "A") >= 12 and all(x[0] == "A" for x in _hv), _hv)
    try:
        PG.click("#tasksList a[href^='/orders?order=']")
        PG.wait_for_load_state("networkidle")
        PG.wait_for_timeout(600)
    except Exception:                      # noqa: BLE001
        pass
    _m = jsq(PG, OLCH_JS) or {}
    check("H2 birinchi bugungi buyurtma bosildi → Buyurtmalar sahifasida AYNAN shu buyurtma tanlangan",
          _m.get("tanlangan") == f"oi-{sorted(I.get('bugun') or [0])[0]}", _m.get("tanlangan"))
    bor(PG, "/")
    try:
        PG.click("#tasksList a[href='/inventory?kam=1']")
        PG.wait_for_load_state("networkidle")
        PG.wait_for_timeout(600)
    except Exception:                      # noqa: BLE001
        pass
    _iv = jsq(PG, "() => ({f: (document.getElementById('statusFilter') || {}).value, url: location.pathname + location.search})")
    check("H3 kam qolgan qatori → Omborda «Kam qolganlar» filtri yoqilgan, manzil tozalangan", _iv == {"f": "kamqolgan", "url": "/inventory"}, _iv)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Telefon 390 px — Buyurtmalar va Qarzdorlar ekrandan chiqmaydi, qidiruv maydoni yetarli")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TEL_JS = r"""(sel) => { const vw = innerWidth; const ch = [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect();
    const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.position !== 'fixed' && !e.closest('.sidebar')
    && (r.right > vw + 1 || r.left < -1); }).filter(e => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX; if ((o === 'auto' || o === 'scroll') && p.clientWidth < vw * 0.85) return false; } return true; });
  const q = document.querySelector(sel);
  return {chiqqan: ch.slice(0, 5).map(e => e.tagName + '.' + String(e.className).split(' ')[0]), hujjat: document.documentElement.scrollWidth, vw,
          qidiruv: q ? Math.round(q.getBoundingClientRect().width) : null}; }"""
if br:
    _c3, _p3 = kontekst(390, 844, True)
    _p3.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    _tel = {}
    for _u, _sel in (("/orders", "#ordQidiruv"), ("/debts", "#qarzQidiruv")):
        bor(_p3, _u)
        _tel[_u] = jsq(_p3, TEL_JS, _sel)
    _c3.close()
    for _u, _m in _tel.items():
        check(f"T1 390 px {_u}: ekrandan chiqqan element yo'q, sahifa kengaymaydi, qidiruv maydoni ≥ 150 px",
              isinstance(_m, dict) and not _m.get("chiqqan") and _m.get("hujjat", 9e9) <= _m.get("vw", 0) and (_m.get("qidiruv") or 0) >= 150, _m)

section("X. JS xatosi yo'q")
check("X1 sahifalarda JS xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])

if pw_ctx is not None:
    try:
        if br:
            br.close()
        pw_ctx.stop()
    except Exception:                      # noqa: BLE001
        pass
server.should_exit = True
th.join(timeout=10)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  - " + f)
sys.exit(0 if FAIL == 0 else 1)
