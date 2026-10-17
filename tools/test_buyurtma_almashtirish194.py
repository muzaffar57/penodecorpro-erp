#!/usr/bin/env python3
"""
test_buyurtma_almashtirish194.py — kech152 (zip 194, egasi tanlovi 17.10 «Buyurtmalarni tez almashtirish»): «Buyurtmalar» sahifasida
bir buyurtmada boshlangan amal / so'rov javobi KELGUNCHA boshqa buyurtma tanlansa (yoki filtr / retsept / qidiruv almashtirilsa) —
natija ESKISIGA tegishli bo'lib qolmasin. HAQIQIY Chromium, HAQIQIY lokal server (uvicorn, test bazasi); javoblar Playwright `route`
bilan USHLANIB, buyurtma almashtirilgandan keyin (yoki teskari tartibda) qo'yib yuboriladi.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k194/probe194.py`, asl kod = zip 193; natija `work/k194/probe194_asl.json`)
  V7   O'CHIRISH: A da «O'chirish» bosilib, ma'lumot yuklanguncha B tanlansa — tasdiq oynasi A niki («ORD-001-1 o'chirilsinmi? … 70 000
       so'm to'lov ham … o'chadi»), «O'chirish» esa B ni O'CHIRARDI (`DELETE /api/orders/2`).
  V8   Kelishilgan summa: oyna A ning summalari bilan B ustida, saqlash — A ga. V9 «Bir yo'la to'liq topshirish» — A oynasi B ustida,
       yuborish B + A detali → «bu detal shu buyurtmada topilmadi». V10 «Nusxa olish» — A oynasi B ustida. V11 «Tahrirlash» — yashirin
       forma A bilan to'ldiriladi, «✏️ A tahrirlash rejimida» B ekranida; «+ Yangi buyurtma» bosilsa ham.
  V1   «Foyda hisoblash»: B xulosasida A ning «Sotuv narxi 1 000 000» (B — 5 000 000), A ning «Foyda tahlili» oynasi; 500 / 401 — jim,
       internet — ushlanmagan xato.
  V12  «Yetkazish» oynasi: B oynasida A ning qarzi.
  V2   Pin: ikki marta tez bosish — ikki so'rov (pin + pindan olish); xato — jim; «Ustuvor buyurtmalar» — eski javob yangisini bosadi,
       xato — bo'lim jimgina yashirinadi.
  V3   Kam qoldiq kartasi — «2 815,14 kg» (omborxonada «2 815,138 kg»), `r.ok` yo'q.
  V4   Tayyor mahsulot tavsiyasi: eski javob yangisini bosadi, maydon tozalangach / mahsulot tanlangach ham ochiladi.
  V5   Loy zaxirasi: eski retsept javobi yangisini bosadi; «12.5 kg», «1234.5 kg».
  V6   Takliflar: «Bekor qilingan» filtri faol, ro'yxat — «Hammasi» javobi.
Har sahnada NAZORAT — almashtirmasdan amal avvalgidek ishlaydi (oyna ochiladi, so'rov o'sha buyurtmaga ketadi).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 193) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` (1.56: `unroute` ushlangan so'rovni o'zi davom ettiradi — shuning uchun avval qo'yib yuboriladi) + Chromium.
ISHLATISH: python3 tools/test_buyurtma_almashtirish194.py
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "buyurtma_almashtirish194_test"
_T = tempfile.mkdtemp(prefix="bal194_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'buyurtma_almashtirish194.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Recipe, RecipeIngredient, Project, Order   # noqa: E402
from production_models import ProductType          # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
NB = "\u00a0"


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
    auth.create_user(s, "u194_admin", PAROL, UserRole.ADMIN, "U194 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="U194 Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="U194 Kley", unit="kg", stock_quantity=2815.138, price_per_unit=2000, category="Kimyo",
                 min_stock=3815.25)
s.add_all([PENO, KLEY])
s.flush()
REC = Recipe(company_id=1, name="U194 retsept 1", batch_size_kg=100.0)
REC2 = Recipe(company_id=1, name="U194 retsept 2", batch_size_kg=100.0)
s.add_all([REC, REC2])
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
s.add(RecipeIngredient(recipe_id=REC2.id, inventory_id=KLEY.id, quantity_kg=100.0))
PRJ = Project(company_id=1, client_name="U194 Mijoz", project_name="U194 loyiha", total_budget=0, total_paid=0)
PT = ProductType(company_id=1, name="U194 Travertin", unit="m²", input_template="area_2d", pricing_formula="per_area",
                 supports_coating=True, coating_price_multiplier=2, is_active=True)
s.add_all([PRJ, PT])
s.commit()
ID = {"PENO": PENO.id, "KLEY": KLEY.id, "REC": REC.id, "REC2": REC2.id, "P": PRJ.id, "PT": PT.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert C.post("/login", data={"username": "u194_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)


def bu(nom, narx, n):
    it = {"name": nom, "category": "panel", "width": 50, "thickness": 5, "quantity": n, "unit_price": narx, "is_coated": False}
    r = C.post("/api/orders?confirm_shortage=true", json={"project_id": ID["P"], "order_type": "product", "items": [it]})
    assert r.status_code == 200, r.text
    return r.json()["id"]


ID["A"] = bu("U194 A detal", 100000, 10)          # jami 1 000 000; to'lov 70 000 → qarz 930 000; pin qilingan
ID["B"] = bu("U194 B detal", 1000000, 5)          # jami 5 000 000
ID["C"] = bu("U194 C detal", 30000, 4)            # pin sinovi
ID["D"] = bu("U194 D detal", 20000, 3)            # nazorat (to'liq topshirish / nusxa / tahrir oynalari)
ID["E"] = bu("U194 E detal", 50000, 2)            # nazorat: o'chirish (almashtirmasdan)
ID["A7"] = bu("U194 A7 detal", 100000, 3)         # V7 (o'chirish) — alohida: asl kodda B7 o'chadi, qolgan sahnalarga tegmasin
ID["B7"] = bu("U194 B7 detal", 200000, 2)
ID["A8"] = bu("U194 A8 detal", 100000, 1)         # V7f (tasdiq paytida tanlov o'zgardi)
ID["B8"] = bu("U194 B8 detal", 200000, 1)
_rm = C.post("/api/orders?confirm_shortage=true", json={"project_id": ID["P"], "order_type": "product", "items": [
    {"name": "U194 MRP Travertin", "category": "mrp_product", "width": 2, "length": 3, "quantity": 6, "unit_price": 50000,
     "is_coated": True, "product_type_id": ID["PT"]}]})
assert _rm.status_code == 200, _rm.text
ID["M"] = _rm.json()["id"]                         # V11i (tahrir — MRP turlari yuklanayotganda)
assert C.post("/api/payments", json={"order_id": ID["A"], "amount": 70000, "payment_type": "partial",
                                      "payment_method": "naqd"}).status_code == 200
assert C.post("/api/payments", json={"order_id": ID["A7"], "amount": 70000, "payment_type": "partial",
                                      "payment_method": "naqd"}).status_code == 200
assert C.post(f"/api/orders/{ID['A']}/pin").status_code == 200
NUM = {k: js(C.get(f"/api/orders/{ID[k]}")).get("order_number") for k in ("A", "B", "C", "D", "E", "A8", "B8", "M")}


def server_pinlar():
    return sorted(int(x["id"]) for x in (js(C.get("/api/orders/pinned")) or []))


def bor(oid):
    d = SessionLocal()
    try:
        o = d.query(Order).filter(Order.id == oid).first()
        return bool(o) and not bool(getattr(o, "is_deleted", False))
    finally:
        d.close()


def qarz_matn(oid):
    """serverdagi joriy qarz — sahifa ko'rinishida (butun so'm, ming — bo'shliq)"""
    q = float(js(C.get(f"/api/orders/{oid}")).get("debt_amount") or 0)
    return f"{int(round(q)):,}".replace(",", " ")


def kelishilgan(oid):
    o = js(C.get(f"/api/orders/{oid}"))
    return o.get("agreed_amount") if o.get("agreed_amount") is not None else o.get("total_amount")


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
JS_XATO, SOROV = [], []


def kontekst():
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""), q.post_data))
          if "/api/" in q.url and q.method in ("POST", "PUT", "DELETE") else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", "u194_admin")
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


# Xabarlar / tasdiq / so'rov oynalari: `window.__msg`, `window.__tasdiq`, `window.__prompt`; javoblar — `window.__ha` (true),
# `window.__promptJavob` (null — «Bekor»); `window.__haKech` — tasdiq oynasi javobi `window.__haBer(true|false)` gacha kutadi
ILGAK = """() => { window.__msg = []; window.__tasdiq = []; window.__prompt = []; window.__ha = true; window.__promptJavob = null;
  window.showMsg = (t, ty) => { window.__msg.push([String(t), ty]); };
  window.showConfirmModal = async (m) => { window.__tasdiq.push(String(m));
    if (window.__haKech) return await new Promise(r => { window.__haBer = r; }); return window.__ha; };
  window.customConfirm = async (a, b) => { window.__tasdiq.push(String(a) + (typeof b === 'string' ? ' | ' + b : '')); return window.__ha; };
  window.showPromptModal = async (m, d) => { window.__prompt.push(String(m) + ' || ' + String(d)); return window.__promptJavob; };
  window.open = () => null; window.openPdfSafe = () => null; }"""
HOLAT = """() => { const t = (i) => (document.getElementById(i) || {}).textContent || '';
  const v = (i) => { const e = document.getElementById(i); return e ? getComputedStyle(e).display : null; };
  const m = document.getElementById('profitModal');
  return {sel: typeof selectedOrderId !== 'undefined' ? selectedOrderId : null, num: t('s-num'), total: t('s-total'), cost: t('s-cost'),
          profit: t('s-profit'), profitRow: v('profitRow'), modal: m ? (m.style.display + ' | ' + m.innerText.replace(/\\s+/g, ' ').slice(0, 200)) : null,
          forma: v('newOrderForm'), sarlavha: t('formTitle'), editId: (typeof currentEditOrderId !== 'undefined') ? currentEditOrderId : 'yoq',
          editMode: (typeof editMode !== 'undefined') ? editMode : 'yoq',
          sessiya: (document.getElementById('yukSessiya') || {}).hidden === false}; }"""
XATO_500 = {"status": 500, "content_type": "application/json", "body": '{"detail":"Serverda kutilmagan xato yuz berdi"}'}
XATO_401 = {"status": 401, "content_type": "application/json", "body": '{"detail":"Kirish talab qilinadi"}'}


def ochiq(pg, oid=None):
    """Sahifa ochiladi. Asl kodda (masalan o'chirish muvaffaqiyatidan keyin) sahifa 2,5 – 3 s dan keyin O'ZI qayta yuklanadi — `goto` u bilan
    to'qnashsa (net::ERR_ABORTED) — kutib, qayta urinadi (3 marta)."""
    for _n in range(3):
        try:
            pg.goto(f"{B}/orders" + (f"?order={oid}" if oid else ""), wait_until="networkidle")
            break
        except Exception as _e:            # noqa: BLE001
            if "ERR_ABORTED" not in str(_e) or _n == 2:
                raise
            pg.wait_for_timeout(3500)
    pg.wait_for_timeout(500)
    pg.evaluate(ILGAK)


def tanla(pg, oid, kut=1200):
    pg.evaluate(f"() => selectOrder({oid}, document.getElementById('oi-{oid}'))")
    pg.wait_for_timeout(kut)


def msg(pg):
    return pg.evaluate("() => window.__msg || []")


def sorovlar(nima, usul=None):
    return [x for x in SOROV if nima in x[1] and (usul is None or x[0] == usul)]


def ushla(pg, naqsh, usul="GET"):
    """Birinchi mos so'rov USHLANADI (keyingilari o'tadi). Qaytaradi: (ushlanganlar, handler)."""
    lst = []

    def h(route):
        if route.request.method != usul or lst:
            route.continue_()
            return
        lst.append(route)
    pg.route(naqsh, h)
    return lst, h


def qoy(pg, naqsh, lst, h, kut=1500):
    """Ushlangan so'rov(lar) davom ettiriladi — `unroute` dan OLDIN (Playwright 1.56: `unroute` ularni o'zi davom ettiradi)."""
    for r in lst:
        try:
            r.continue_()
        except Exception:                  # noqa: BLE001
            pass
    pg.unroute(naqsh, h)
    pg.wait_for_timeout(kut)


def teskari(pg, naqsh, b1, b2):
    """1-so'rov USHLANADI (javobi b1), keyingilari darhol b2; `bitir()` — 1-sini endi beradi (teskari tartib)."""
    held = []

    def h(route):
        if not held:
            held.append(route)
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(b2))
    pg.route(naqsh, h)

    def bitir(kut=1200):
        for r in held:
            try:
                r.fulfill(status=200, content_type="application/json", body=json.dumps(b1))
            except Exception:              # noqa: BLE001
                pass
        pg.unroute(naqsh, h)
        pg.wait_for_timeout(kut)
    return held, bitir


if br:
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V7 — O'CHIRISH: ma'lumot yuklanguncha boshqa buyurtma tanlansa — hech narsa o'chmaydi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["A7"])
        nq = f"**/api/orders/{ID['A7']}"
        lst, h = ushla(pg, nq)
        pg.evaluate("() => { deleteSelected(); }")
        pg.wait_for_timeout(300)
        tanla(pg, ID["B7"])
        SOROV.clear()
        qoy(pg, nq, lst, h, 2500)
        _t = pg.evaluate("() => window.__tasdiq")
        check("V7a A da «O'chirish», yuklanguncha B tanlandi → tasdiq oynasi OCHILMADI (asl: «A o'chirilsinmi? … to'lov ham o'chadi»)",
              len(lst) == 1 and not _t, (len(lst), _t))
        check("V7b … va DELETE so'rovi YO'Q (asl: `DELETE /api/orders/<B>` — B o'chardi)", not sorovlar("/api/orders/", "DELETE"), SOROV)
        pg.wait_for_timeout(500)
        check("V7c A ham, B ham joyida", bor(ID["A7"]) and bor(ID["B7"]), (bor(ID["A7"]), bor(ID["B7"])))
        check("V7d tanlov — B (ekranda B)", str(pg.evaluate("() => selectedOrderId")) == str(ID["B7"]), pg.evaluate("() => selectedOrderId"))
        # V7f — tasdiq oynasi ochiq turganda tanlov o'zgardi (dastur orqali — oyna ekranni yopadi): o'chirish faqat tasdiqlangan buyurtmaga
        ochiq(pg, ID["A8"])
        SOROV.clear()
        pg.evaluate("() => { window.__haKech = true; deleteSelected(); }")
        pg.wait_for_timeout(1200)
        _t = pg.evaluate("() => window.__tasdiq")
        tanla(pg, ID["B8"])
        pg.evaluate("() => { window.__haBer(true); }")
        pg.wait_for_timeout(2500)
        _d = sorovlar("/api/orders/", "DELETE")
        check("V7f «A8 o'chirilsinmi?» tasdiqlanguncha B8 tanlandi → B8 O'CHMAYDI, DELETE yo'q (asl: `DELETE /api/orders/<B8>`)",
              len(_t) == 1 and NUM["A8"] in _t[0] and not _d and bor(ID["A8"]) and bor(ID["B8"]), (_t, _d, bor(ID["A8"]), bor(ID["B8"])))
        # nazorat: almashtirmasdan — tasdiq E niki, E o'chadi
        ochiq(pg, ID["E"])
        SOROV.clear()
        try:
            with pg.expect_navigation(timeout=12000):
                pg.evaluate("() => { deleteSelected(); }")
        except Exception:                  # noqa: BLE001
            pass
        pg.wait_for_load_state("networkidle")
        _d = sorovlar("/api/orders/", "DELETE")
        check("V7e NAZORAT almashtirmasdan: `DELETE /api/orders/<E>`, E o'chdi, A7 joyida",
              len(_d) == 1 and _d[0][1].startswith(f"/api/orders/{ID['E']}") and not bor(ID["E"]) and bor(ID["A7"]), (_d, bor(ID["E"])))
    except Exception as _e:                # noqa: BLE001
        check("V7! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V8 / V9 / V10 — kelishilgan summa, «Bir yo'la to'liq topshirish», «Nusxa olish»: boshqa buyurtma ustida oyna ochilmaydi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        k0 = kelishilgan(ID["A"])
        ochiq(pg, ID["A"])
        nq = f"**/api/orders/{ID['A']}"
        lst, h = ushla(pg, nq)
        SOROV.clear()
        pg.evaluate("() => { window.__promptJavob = '777 777'; editAgreedAmount(); }")
        pg.wait_for_timeout(300)
        tanla(pg, ID["B"])
        qoy(pg, nq, lst, h, 2000)
        _p = pg.evaluate("() => window.__prompt")
        check("V8a ✏️ A da, yuklanguncha B tanlandi → oyna OCHILMADI, PUT YO'Q (asl: A summalari bilan oyna, PUT A ga)",
              len(lst) == 1 and not _p and not sorovlar("/agreed-amount"), (_p, SOROV))
        check("V8b A ning kelishilgan summasi o'zgarmadi", kelishilgan(ID["A"]) == k0, (k0, kelishilgan(ID["A"])))
        # nazorat
        ochiq(pg, ID["D"])
        SOROV.clear()
        pg.evaluate("() => { window.__promptJavob = null; editAgreedAmount(); }")
        pg.wait_for_timeout(1200)
        _p = pg.evaluate("() => window.__prompt")
        check("V8c NAZORAT almashtirmasdan: oyna ochildi (D ning jami 60 000), «Bekor» — PUT yo'q",
              len(_p) == 1 and "60 000" in _p[0].replace(NB, " ") and not sorovlar("/agreed-amount"), (_p, SOROV))
        # V9 — «Bir yo'la to'liq topshirish»
        ochiq(pg, ID["A"])
        pg.wait_for_timeout(400)
        lst, h = ushla(pg, nq)
        pg.evaluate("() => { quickFullDelivery(); }")
        pg.wait_for_timeout(300)
        tanla(pg, ID["B"])
        qoy(pg, nq, lst, h, 1200)
        _o = pg.evaluate("""() => ({k: getComputedStyle(document.getElementById('fullDlvModalOverlay')).display,
            m: ((document.getElementById('fullDlvModalBody') || {}).innerText || '').slice(0, 200)})""")
        check("V9a «Bir yo'la to'liq topshirish» A da, yuklanguncha B tanlandi → oyna OCHILMADI (asl: A detali va qarzi bilan B ustida)",
              len(lst) == 1 and _o["k"] == "none", _o)
        ochiq(pg, ID["D"])
        pg.wait_for_timeout(400)
        pg.evaluate("() => { quickFullDelivery(); }")
        pg.wait_for_timeout(1200)
        _o = pg.evaluate("""() => ({k: getComputedStyle(document.getElementById('fullDlvModalOverlay')).display,
            m: ((document.getElementById('fullDlvModalBody') || {}).innerText || '').slice(0, 200)})""")
        check("V9b NAZORAT almashtirmasdan: oyna ochildi, D detali bilan", _o["k"] == "flex" and "U194 D detal" in _o["m"], _o)
        pg.evaluate("() => { closeFullDlvModal(); }")
        # V10 — «Nusxa olish»
        ochiq(pg, ID["A"])
        lst, h = ushla(pg, nq)
        pg.evaluate("() => { duplicateSelected(); }")
        pg.wait_for_timeout(300)
        tanla(pg, ID["B"])
        qoy(pg, nq, lst, h, 1200)
        _o = pg.evaluate("() => ({k: getComputedStyle(document.getElementById('dupPickModal')).display, s: document.getElementById('dup-modal-sub').textContent})")
        check("V10a «Nusxa olish» A da, yuklanguncha B tanlandi → oyna OCHILMADI (asl: A ning oynasi B ustida)",
              len(lst) == 1 and _o["k"] == "none", _o)
        ochiq(pg, ID["D"])
        pg.evaluate("() => { duplicateSelected(); }")
        pg.wait_for_timeout(1200)
        _o = pg.evaluate("() => ({k: getComputedStyle(document.getElementById('dupPickModal')).display, s: document.getElementById('dup-modal-sub').textContent})")
        check("V10b NAZORAT almashtirmasdan: oyna ochildi, D raqami bilan", _o["k"] == "flex" and NUM["D"] in _o["s"], _o)
    except Exception as _e:                # noqa: BLE001
        check("V8! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V11 — «Tahrirlash»: yuklanguncha boshqa buyurtma tanlansa / «+ Yangi buyurtma» bosilsa — forma A bilan to'lmaydi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["A"])
        nq = f"**/api/orders/{ID['A']}"
        lst, h = ushla(pg, nq)
        GETLAR = []
        _gl = lambda q: GETLAR.append(q.url.replace(B, "")) if q.method == "GET" and "/api/" in q.url else None   # noqa: E731
        pg.evaluate("() => { editSelected(); }")
        pg.wait_for_timeout(300)
        tanla(pg, ID["B"])
        pg.on("request", _gl)
        qoy(pg, nq, lst, h, 2500)
        pg.remove_listener("request", _gl)
        _h = pg.evaluate(HOLAT)
        _m = msg(pg)
        _det = pg.evaluate("() => [...document.querySelectorAll('#items .detal .i-name')].map(e => e.value)")
        check("V11a «Tahrirlash» A da, yuklanguncha B tanlandi → tahrir rejimi YOQILMADI (asl: currentEditOrderId = A, sarlavha «Buyurtmani "
              "tahrirlash»)", len(lst) == 1 and _h["editId"] in (None, "yoq") and _h["sarlavha"] != "Buyurtmani tahrirlash"
              and "U194 A detal" not in _det, (_h, _det))
        check("V11b … va «✏️ A tahrirlash rejimida» xabari B ekranida YO'Q", not any("tahrirlash rejimida" in m[0] for m in _m), _m)
        check("V11c ekranda B (forma yopiq)", str(_h["sel"]) == str(ID["B"]) and _h["forma"] == "none", _h)
        _ort = [u for u in GETLAR if u.startswith(f"/api/orders/{ID['A']}/")]
        check("V11f eskirgan tahrir keyingi so'rovlarni YUBORMAYDI (A ning topshirish holati / loy rejasi; asl: ikkalasi)", not _ort, GETLAR)
        # V11g — tanlov topshirish holati yuklanayotganda o'zgardi
        for _nom, _yol, _kut in (("V11g", "delivery-status", 800), ("V11h", "planned-loy", 1200)):
            ochiq(pg, ID["A"])
            _q = f"**/api/orders/{ID['A']}/{_yol}"
            lst, h = ushla(pg, _q)
            pg.evaluate("() => { editSelected(); }")
            pg.wait_for_timeout(_kut)
            tanla(pg, ID["B"])
            qoy(pg, _q, lst, h, 2500)
            _h = pg.evaluate(HOLAT)
            _m = msg(pg)
            _det = pg.evaluate("() => [...document.querySelectorAll('#items .detal .i-name')].map(e => e.value)")
            if _nom == "V11g":
                check("V11g «Tahrirlash» A da, topshirish holati yuklanguncha B tanlandi → forma A bilan TO'LMADI, tahrir rejimi yo'q",
                      len(lst) == 1 and _h["editId"] in (None, "yoq") and "U194 A detal" not in _det
                      and not any("tahrirlash rejimida" in m[0] for m in _m), (len(lst), _h, _det, _m))
            else:
                check("V11h «Tahrirlash» A da, loy rejasi yuklanguncha B tanlandi → «✏️ A tahrirlash rejimida» YO'Q, sarlavha / saqlash tugmasi "
                      "tahrirga o'tmadi", len(lst) == 1 and _h["sarlavha"] != "Buyurtmani tahrirlash"
                      and not any("tahrirlash rejimida" in m[0] for m in _m) and str(_h["sel"]) == str(ID["B"]), (len(lst), _h, _m))
        # V11i — MRP turlari yuklanayotganda (MRP detalli buyurtma)
        ochiq(pg, ID["M"])
        pg.evaluate("() => { _mrpProductTypesCache = null; }")
        _q = "**/api/production/product-types*"
        lst, h = ushla(pg, _q)
        pg.evaluate("() => { editSelected(); }")
        pg.wait_for_timeout(1200)
        tanla(pg, ID["B"])
        qoy(pg, _q, lst, h, 2500)
        _h = pg.evaluate(HOLAT)
        _det = pg.evaluate("() => [...document.querySelectorAll('#items .detal .i-name')].map(e => e.value)")
        check("V11i MRP detalli buyurtma: turlar yuklanguncha B tanlandi → forma MRP detali bilan TO'LMADI, tahrir rejimi yo'q",
              len(lst) == 1 and _h["editId"] in (None, "yoq") and "U194 MRP Travertin" not in _det
              and not any("tahrirlash rejimida" in m[0] for m in msg(pg)), (len(lst), _h, _det))
        # «+ Yangi buyurtma» yuklanish paytida
        ochiq(pg, ID["A"])
        lst, h = ushla(pg, nq)
        pg.evaluate("() => { editSelected(); }")
        pg.wait_for_timeout(300)
        pg.evaluate("() => { showNewForm(); }")
        pg.wait_for_timeout(300)
        qoy(pg, nq, lst, h, 2500)
        _h = pg.evaluate(HOLAT)
        _det = pg.evaluate("() => [...document.querySelectorAll('#items .detal .i-name')].map(e => e.value)")
        check("V11d yuklanish paytida «+ Yangi buyurtma» → forma YANGI qoladi (sarlavha «Yangi buyurtma», A detali yo'q, tahrir yo'q)",
              len(lst) == 1 and _h["sarlavha"] == "Yangi buyurtma" and _h["editId"] in (None, "yoq") and "U194 A detal" not in _det
              and _h["forma"] == "block", (_h, _det))
        # nazorat
        ochiq(pg, ID["D"])
        pg.evaluate("() => { editSelected(); }")
        pg.wait_for_timeout(2500)
        _h = pg.evaluate(HOLAT)
        _det = pg.evaluate("() => [...document.querySelectorAll('#items .detal .i-name')].map(e => e.value)")
        check("V11e NAZORAT almashtirmasdan: tahrir ochildi (D, «Buyurtmani tahrirlash», D detali)",
              _h["sarlavha"] == "Buyurtmani tahrirlash" and str(_h["editId"]) == str(ID["D"]) and "U194 D detal" in _det and _h["forma"] == "block",
              (_h, _det))
    except Exception as _e:                # noqa: BLE001
        check("V11! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V1 — «Foyda hisoblash»: javob faqat o'sha buyurtma tanlangan bo'lsa; xato — sabab bilan")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["A"])
        nq = f"**/api/orders/{ID['A']}/profit"
        lst, h = ushla(pg, nq)
        pg.evaluate("() => { loadProfit(); }")
        pg.wait_for_timeout(300)
        tanla(pg, ID["B"])
        qoy(pg, nq, lst, h, 1500)
        _h = pg.evaluate(HOLAT)
        check("V1a A da «Foyda hisoblash», javob kelguncha B tanlandi → B xulosasi B niki («Sotuv narxi» 5 000 000), tan narxi / foyda "
              "qatori yashirin, «Foyda tahlili» oynasi YO'Q (asl: A ning 1 000 000 / 125 000 / 875 000 va oynasi)",
              len(lst) == 1 and str(_h["sel"]) == str(ID["B"]) and _h["total"].replace(NB, " ") == "5 000 000 so'm"
              and _h["profitRow"] == "none" and not _h["modal"], _h)
        # nazorat
        pg.evaluate("() => { loadProfit(); }")
        pg.wait_for_timeout(1500)
        _h = pg.evaluate(HOLAT)
        check("V1b NAZORAT almashtirmasdan: B ning foydasi chizildi (tan narxi 62 500, oyna ochiq)",
              _h["cost"].replace(NB, " ") == "62 500 so'm" and _h["profitRow"] == "flex" and bool(_h["modal"]) and _h["modal"].startswith("flex"), _h)
        pg.evaluate("() => { const m = document.getElementById('profitModal'); if (m) m.remove(); window.__msg = []; }")
        nb = f"**/api/orders/{ID['B']}/profit"
        _h5 = lambda r: r.fulfill(**XATO_500)                                                   # noqa: E731
        pg.route(nb, _h5)
        pg.evaluate("() => { loadProfit(); }")
        pg.wait_for_timeout(1000)
        _m = msg(pg)
        check("V1c 500 → «❌ Foyda hisoblanmadi: server javob bermadi …» (asl: jim)",
              any(m[0].startswith("❌ Foyda hisoblanmadi") and "server javob bermadi" in m[0] for m in _m), _m)
        pg.unroute(nb, _h5)
        n0 = len(JS_XATO)
        pg.evaluate("() => { window.__msg = []; }")
        _ha = lambda r: r.abort()                                                              # noqa: E731
        pg.route(nb, _ha)
        pg.evaluate("() => { loadProfit(); }")
        pg.wait_for_timeout(1000)
        _m = msg(pg)
        check("V1d internet uzildi → «internet aloqasi yo'q», ushlanmagan JS xatosi YO'Q (asl: jim + «Failed to fetch»)",
              any("internet aloqasi yo'q" in m[0] for m in _m) and len(JS_XATO) == n0, (_m, JS_XATO[n0:]))
        pg.unroute(nb, _ha)
        pg.evaluate("() => { window.__msg = []; }")
        _h4 = lambda r: r.fulfill(**XATO_401)                                                  # noqa: E731
        pg.route(nb, _h4)
        pg.evaluate("() => { loadProfit(); }")
        pg.wait_for_timeout(1000)
        _m = msg(pg)
        _h = pg.evaluate(HOLAT)
        check("V1e 401 → «kirish muddati tugagan», sahifa boshidagi «qayta kiring» havolasi ko'rinadi (asl: jim)",
              any("kirish muddati tugagan" in m[0] for m in _m) and _h["sessiya"], (_m, _h))
        pg.unroute(nb, _h4)
    except Exception as _e:                # noqa: BLE001
        check("V1! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V12 — «Yetkazish» oynasidagi qarz — faqat o'sha buyurtmaniki")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["A"])
        pg.wait_for_timeout(400)
        nq = f"**/api/orders/{ID['A']}"
        lst, h = ushla(pg, nq)
        pg.evaluate("() => { openDeliveryModal(); }")
        pg.wait_for_timeout(300)
        pg.evaluate("() => { closeDeliveryModal(); }")
        tanla(pg, ID["B"], 1500)
        pg.evaluate("() => { openDeliveryModal(); }")
        pg.wait_for_timeout(1000)
        qoy(pg, nq, lst, h, 1200)
        _o = pg.evaluate("() => ({s: document.getElementById('dlv-modal-sub').textContent, q: document.getElementById('dlv-debt-info').textContent})")
        _qa = qarz_matn(ID["A"])
        check(f"V12a A oynasi yopilib B oynasi ochildi, A javobi keyin keldi → B oynasida B ning qarzi (5 000 000), A niki ({_qa}) EMAS",
              len(lst) == 1 and NUM["B"] in _o["s"] and "5 000 000 so'm" in _o["q"].replace(NB, " ") and _qa + " so'm" not in _o["q"].replace(NB, " "), _o)
        pg.evaluate("() => { closeDeliveryModal(); }")
        tanla(pg, ID["A"], 1500)
        pg.evaluate("() => { openDeliveryModal(); }")
        pg.wait_for_timeout(1200)
        _o = pg.evaluate("() => ({s: document.getElementById('dlv-modal-sub').textContent, q: document.getElementById('dlv-debt-info').textContent})")
        check(f"V12b NAZORAT: A oynasida A ning qarzi ({qarz_matn(ID['A'])})", NUM["A"] in _o["s"]
              and qarz_matn(ID["A"]) + " so'm" in _o["q"].replace(NB, " "), _o)
        pg.evaluate("() => { closeDeliveryModal(); }")
    except Exception as _e:                # noqa: BLE001
        check("V12! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V2 — pin: ikki marta bosish bitta so'rov, xato — sabab, «Ustuvor buyurtmalar» — oxirgi javob")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        p0 = server_pinlar()
        ochiq(pg, ID["C"])
        SOROV.clear()
        pg.evaluate(f"() => {{ toggleOrderPin({ID['C']}); toggleOrderPin({ID['C']}); }}")
        pg.wait_for_timeout(1500)
        _s = sorovlar(f"/api/orders/{ID['C']}/pin", "POST")
        p1 = server_pinlar()
        _t = pg.evaluate("() => document.getElementById('btn-pin').textContent")
        check("V2a pin tugmasi ikki marta tez → BITTA so'rov, C pin qilindi, tugma «📌 Pindan olish» (asl: ikki so'rov — pin + pindan olish)",
              ID["C"] not in p0 and len(_s) == 1 and ID["C"] in p1 and "Pindan olish" in _t, (p0, _s, p1, _t))
        _vis = pg.evaluate("() => [...document.querySelectorAll('#pinnedOrdersList .ord-item')].map(e => +e.dataset.orderId).sort((a, b) => a - b)")
        check("V2b «Ustuvor buyurtmalar» ro'yxati = server (A, C)", _vis == p1, (_vis, p1))
        pn = f"**/api/orders/{ID['C']}/pin"
        _h5 = lambda r: r.fulfill(**XATO_500)                                                   # noqa: E731
        pg.route(pn, _h5)
        pg.evaluate(f"() => {{ window.__msg = []; toggleOrderPin({ID['C']}); }}")
        pg.wait_for_timeout(1200)
        _m = msg(pg)
        check("V2c pin 500 → «❌ Pin o'zgarmadi: server javob bermadi — sahifani yangilab tekshiring» (asl: jim)",
              any(m[0].startswith("❌ Pin o'zgarmadi") and "server javob bermadi" in m[0] for m in _m), _m)
        pg.unroute(pn, _h5)
        # V2d — eski ro'yxat javobi kech keladi: A pindan olinadi (ro'yxat javobi ushlanadi), D pin qilinadi
        ochiq(pg, ID["C"])
        held = []

        def _hp(route):
            if not held:
                held.append((route, route.fetch()))
            else:
                route.continue_()
        pg.route("**/api/orders/pinned", _hp)
        pg.evaluate(f"() => {{ toggleOrderPin({ID['A']}); }}")
        pg.wait_for_timeout(800)
        pg.evaluate(f"() => {{ toggleOrderPin({ID['D']}); }}")
        pg.wait_for_timeout(1200)
        for _r, _resp in held:
            _r.fulfill(response=_resp)
        pg.unroute("**/api/orders/pinned", _hp)
        pg.wait_for_timeout(1200)
        p2 = server_pinlar()
        _v = pg.evaluate("""() => ({b: getComputedStyle(document.getElementById('pinnedOrdersSection')).display,
            r: [...document.querySelectorAll('#pinnedOrdersList .ord-item')].map(e => +e.dataset.orderId).sort((a, b) => a - b)})""")
        check("V2d A pindan olindi, D pin qilindi, birinchi ro'yxat javobi kech keldi → ko'rinish = server (D bor, A yo'q) (asl: eski ro'yxat)",
              len(held) == 1 and ID["D"] in p2 and ID["A"] not in p2 and _v["r"] == p2 and _v["b"] == "block", (p2, _v))
        _h5l = lambda r: r.fulfill(**XATO_500)                                                  # noqa: E731
        pg.route("**/api/orders/pinned", _h5l)
        pg.evaluate("() => { loadPinnedOrders(); }")
        pg.wait_for_timeout(1000)
        _v = pg.evaluate("""() => ({b: getComputedStyle(document.getElementById('pinnedOrdersSection')).display,
            t: document.getElementById('pinnedOrdersSection').innerText})""")
        check("V2e ro'yxat 500 → bo'lim ko'rinadi, «⚠️ Ustuvor buyurtmalar yuklanmadi — server javob bermadi …» (asl: jimgina yashirinardi)",
              _v["b"] == "block" and "Ustuvor buyurtmalar yuklanmadi" in _v["t"] and "server javob bermadi" in _v["t"], _v)
        pg.unroute("**/api/orders/pinned", _h5l)
        # nazorat: yana bir bosish — D holati almashadi (bitta so'rov), ro'yxat = server
        _p0 = server_pinlar()
        SOROV.clear()
        pg.evaluate(f"() => {{ toggleOrderPin({ID['D']}); }}")
        pg.wait_for_timeout(1200)
        _p1 = server_pinlar()
        _v = pg.evaluate("() => [...document.querySelectorAll('#pinnedOrdersList .ord-item')].map(e => +e.dataset.orderId).sort((a, b) => a - b)")
        check("V2f NAZORAT: bitta bosish — D holati almashdi (bitta so'rov), ro'yxat = server",
              (ID["D"] in _p0) != (ID["D"] in _p1) and len(sorovlar(f"/api/orders/{ID['D']}/pin", "POST")) == 1 and _v == _p1, (_p0, _p1, _v))
    except Exception as _e:                # noqa: BLE001
        check("V2! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V3 — kam qoldiq kartasi: miqdor 3 xona, xato — karta yashirin, JS xatosi yo'q")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, ID["B"])
        _t = pg.evaluate("() => (document.getElementById('alertBody') || {}).innerText || ''")
        check("V3a «U194 Kley» — «2 815,138 kg» (asl: «2 815,14 kg»; omborxonada va server xabarlarida 2 815,138)",
              "U194 Kley" in _t and "2 815,138 kg" in _t.replace(NB, " "), repr(_t))
        n0 = len(JS_XATO)
        _h5 = lambda r: r.fulfill(**XATO_500)                                                   # noqa: E731
        pg.route("**/api/warnings/low-stock", _h5)
        tanla(pg, ID["D"])
        _k = pg.evaluate("() => getComputedStyle(document.getElementById('alertCard')).display")
        check("V3b 500 → karta yashirin, JS xatosi yo'q", _k == "none" and len(JS_XATO) == n0, (_k, JS_XATO[n0:]))
        pg.unroute("**/api/warnings/low-stock", _h5)
    except Exception as _e:                # noqa: BLE001
        check("V3! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V4 / V5 — yangi buyurtma formasi: tayyor mahsulot tavsiyasi va loy zaxirasi — oxirgi so'rov")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg)
        pg.evaluate("() => { showNewForm(); }")
        pg.wait_for_timeout(500)
        if pg.evaluate("() => document.querySelectorAll('#items .detal').length") == 0:
            pg.evaluate("() => addItem()")
        SG1 = {"items": [{"id": 1, "name": "ESKI tavsiya", "source_label": "", "quantity": 7, "unit": "dona", "unit_price": 1000}]}
        SG2 = {"items": [{"id": 2, "name": "YANGI tavsiya", "source_label": "", "quantity": 3, "unit": "dona", "unit_price": 1000}]}
        KIR = "(v) => { const i = document.querySelector('#items .detal .i-name'); i.value = v; searchFinished(i); }"
        KUTU = """() => { const b = document.querySelector('#items .detal .fp-suggest');
            return {v: document.querySelector('#items .detal .i-name').value, k: b.style.display, m: b.innerText.slice(0, 80)}; }"""
        held, bitir = teskari(pg, "**/api/finished/search*", SG1, SG2)
        pg.evaluate(KIR, "ka")
        pg.wait_for_timeout(600)
        pg.evaluate(KIR, "karniz")
        pg.wait_for_timeout(700)
        bitir()
        _k = pg.evaluate(KUTU)
        check("V4a «ka» → «karniz», «ka» javobi kech keldi → tavsiya «karniz» niki (asl: ESKI javob bosardi)",
              len(held) == 1 and "YANGI tavsiya" in _k["m"] and "ESKI" not in _k["m"], _k)
        held, bitir = teskari(pg, "**/api/finished/search*", SG1, SG2)
        pg.evaluate(KIR, "ka")
        pg.wait_for_timeout(600)
        pg.evaluate(KIR, "")
        pg.wait_for_timeout(300)
        bitir()
        _k = pg.evaluate(KUTU)
        check("V4b so'rov ketgach maydon tozalandi → tavsiya OCHILMAYDI (asl: bo'sh maydon ostida ESKI tavsiya)",
              len(held) == 1 and _k["v"] == "" and _k["k"] == "none", _k)
        held, bitir = teskari(pg, "**/api/finished/search*", SG1, SG2)
        pg.evaluate(KIR, "ka")
        pg.wait_for_timeout(600)
        pg.evaluate("() => { const r = document.querySelector('#items .detal'); r.dataset.fpId = '1'; r.querySelector('.fp-suggest').style.display = 'none'; }")
        bitir()
        _k = pg.evaluate(KUTU)
        pg.evaluate("() => { delete document.querySelector('#items .detal').dataset.fpId; }")
        check("V4c so'rov ketgach mahsulot tanlandi → tavsiya qayta OCHILMAYDI", len(held) == 1 and _k["k"] == "none", _k)
        _hs = lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(SG2))    # noqa: E731
        pg.route("**/api/finished/search*", _hs)
        pg.evaluate(KIR, "kar")
        pg.wait_for_timeout(900)
        _k = pg.evaluate(KUTU)
        check("V4d NAZORAT bitta so'rov → tavsiya ochildi", _k["k"] == "block" and "YANGI tavsiya" in _k["m"], _k)
        pg.unroute("**/api/finished/search*", _hs)
        pg.evaluate(KIR, "")
        # V5 — loy zaxirasi
        pg.evaluate(f"""() => {{ const s = document.getElementById('recipe_id');
            [{ID['REC']}, {ID['REC2']}].forEach(v => {{ if (![...s.options].some(o => o.value == v)) {{ const o = document.createElement('option');
              o.value = v; o.textContent = 'R' + v; s.appendChild(o); }} }}); }}""")
        LOY = "() => { const e = document.getElementById('loy-stock-info'); return {k: e.style.display, m: e.innerText}; }"
        held, bitir = teskari(pg, "**/api/loy-stock*", {"stock_kg": 0}, {"stock_kg": 50})
        pg.evaluate(f"() => {{ document.getElementById('loy_kg').value = '12.5'; document.getElementById('recipe_id').value = '{ID['REC']}'; checkLoyStock(); }}")
        pg.wait_for_timeout(300)
        pg.evaluate(f"() => {{ document.getElementById('recipe_id').value = '{ID['REC2']}'; checkLoyStock(); }}")
        pg.wait_for_timeout(700)
        bitir()
        _l = pg.evaluate(LOY)
        check("V5a retsept 1 → 2, retsept 1 javobi kech keldi → «🟢 Omborda 50 kg tayyor loy bor» (asl: «Omborda tayyor loy yo'q»)",
              len(held) == 1 and _l["m"].startswith("🟢 Omborda 50 kg"), _l)
        held, bitir = teskari(pg, "**/api/loy-stock*", {"stock_kg": 40}, {"stock_kg": 40})
        pg.evaluate("() => { document.getElementById('loy_kg').value = '12.5'; checkLoyStock(); }")
        pg.wait_for_timeout(300)
        pg.evaluate("() => { document.getElementById('loy_kg').value = ''; checkLoyStock(); }")
        pg.wait_for_timeout(300)
        bitir()
        _l = pg.evaluate(LOY)
        check("V5b loy o'chirildi (bo'sh), oldingi javob kech keldi → ma'lumot qatori yashirin qoladi", len(held) == 1 and _l["k"] == "none", _l)
        _hz = lambda r: r.fulfill(status=200, content_type="application/json", body='{"stock_kg": 0}')     # noqa: E731
        pg.route("**/api/loy-stock*", _hz)
        pg.evaluate("() => { document.getElementById('loy_kg').value = '1234.5'; checkLoyStock(); }")
        pg.wait_for_timeout(700)
        _l = pg.evaluate(LOY)
        check("V5c loy 1234.5, zaxira yo'q → «… 1 234,5 kg uchun xomashyo ayiriladi» (asl: «1234.5 kg»)",
              "1 234,5 kg uchun" in _l["m"].replace(NB, " "), repr(_l["m"]))
        pg.unroute("**/api/loy-stock*", _hz)
        _hq = lambda r: r.fulfill(status=200, content_type="application/json", body='{"stock_kg": 10.25}')  # noqa: E731
        pg.route("**/api/loy-stock*", _hq)
        pg.evaluate("() => { document.getElementById('loy_kg').value = '12.5'; checkLoyStock(); }")
        pg.wait_for_timeout(700)
        _l = pg.evaluate(LOY)
        check("V5d loy 12,5, zaxira 10,25 → «Omborda 10,25 kg … qolgan 2,25 kg» (asl: 1 xona — «10,3» / «2,3»)",
              "Omborda 10,25 kg" in _l["m"] and "qolgan 2,25 kg" in _l["m"], repr(_l["m"]))
        pg.unroute("**/api/loy-stock*", _hq)
    except Exception as _e:                # noqa: BLE001
        check("V4! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V6 — takliflar ro'yxati: filtr tez almashtirilsa — oxirgi javob")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg)
        T1 = {"sonlar": {"hammasi": 1}, "filtr": "hammasi", "takliflar": [{"id": 901, "raqam": "TK-ESKI", "holat": "yangi", "mijoz": "Eski mijoz",
              "detallar": [], "detallar_soni": 0, "amal_muddati": "2026-12-31", "jami": 1000, "kelishilgan": 1000}]}
        T2 = {"sonlar": {"bekor": 0}, "filtr": "bekor", "takliflar": []}
        held, bitir = teskari(pg, "**/api/takliflar?*", T1, T2)
        pg.evaluate("() => { takliflarOch(); }")
        pg.wait_for_timeout(300)
        pg.evaluate("() => { takliflarFiltr('bekor'); }")
        pg.wait_for_timeout(700)
        bitir()
        _v = pg.evaluate("""() => ({f: [...document.querySelectorAll('#takliflarPanel .tk-f.active')].map(b => b.dataset.f),
            m: ((document.getElementById('tkRoyxat') || {}).innerText || '').slice(0, 160)})""")
        check("V6a «Hammasi» → «Bekor qilingan», birinchi javob kech keldi → ro'yxat «Bekor qilingan» niki (asl: TK-ESKI)",
              len(held) == 1 and _v["f"] == ["bekor"] and "TK-ESKI" not in _v["m"] and "taklif yo'q" in _v["m"], _v)
        _ht = lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(T1))       # noqa: E731
        pg.route("**/api/takliflar?*", _ht)
        pg.evaluate("() => { takliflarFiltr('hammasi'); }")
        pg.wait_for_timeout(900)
        _v = pg.evaluate("() => ((document.getElementById('tkRoyxat') || {}).innerText || '').slice(0, 160)")
        check("V6b NAZORAT bitta so'rov → ro'yxat chizildi (TK-ESKI)", "TK-ESKI" in _v, _v)
        pg.unroute("**/api/takliflar?*", _ht)
    except Exception as _e:                # noqa: BLE001
        check("V6! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    check("X1 sahifalarda ushlanmagan JS xatosi yo'q", not JS_XATO, JS_XATO)
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
