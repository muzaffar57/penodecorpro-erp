#!/usr/bin/env python3
"""
test_sahifalar_almashtirish195.py — kech152 (zip 195, egasi tanlovi 20.10 «Boshqa sahifalarda ham»): ZIP 194 dagi «kutish paytida tanlov
o'zgaradi» xavfi boshqa sahifalarda. HAQIQIY Chromium, HAQIQIY lokal server (uvicorn, test bazasi); javoblar Playwright `route` bilan
USHLANIB, tanlov almashtirilgandan keyin (yoki teskari tartibda) qo'yib yuboriladi.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k195/probe195.py`, asl kod = zip 194; natija `work/k195/probe195_asl.json`, xulosa
`work/k195/OLCHOV195.md`; statik skanerlar `work/k195/skan195*.py` — «boshqa narsani o'chirish» Buyurtmalardan tashqari YO'Q)
  S5  «Kirim qilish»: oxirgi qatorda YANGI material yaratilayotganda ta'minotchi A dan B ga almashtirilsa — kirim B ga yuborilardi.
  S1  «Yordam / Murojaat»: #1 ochilayotganda #2 bosilsa — #1 ning kech javobi #2 ni bosardi (javob ham #1 ga ketardi).
  S2  Hodimlar → «To'lov tarixi»: A oynasi yopilib B niki ochilgach — B oynasida A ning tarixi.
  S4  Sozlamalar → Telegram bot (jurnal N3): ochilgandagi so'rov kech kelsa — chat ID maydonida ESKI qiymat.
Har sahnada NAZORAT — almashtirmasdan avvalgidek ishlaydi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 194) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` (1.56: `unroute` ushlangan so'rovni o'zi davom ettiradi — shuning uchun avval qo'yib yuboriladi) + Chromium.
ISHLATISH: python3 tools/test_sahifalar_almashtirish195.py
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
PG_BAZA = "sahifalar_almashtirish195_test"
_T = tempfile.mkdtemp(prefix="sal195_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'sahifalar_almashtirish195.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory             # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

main._send_telegram = lambda matn, company_id=None: True     # murojaat — platforma egasiga Telegram (sinovda yuborilmaydi)

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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
# Tayyorgarlik — 2-korxona admini (platforma egasi EMAS: «Yordam / Murojaat» faqat mijoz korxonasiga)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="U195 Ikki"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "u195_admin", PAROL, UserRole.ADMIN, "U195 Admin", company_id=2)
KLEY = Inventory(company_id=2, item_name="U195 Kley", unit="kg", stock_quantity=100, price_per_unit=2000, category="Kimyo")
s.add(KLEY)
s.commit()
ID = {"KLEY": KLEY.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert C.post("/login", data={"username": "u195_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)
for _n in ("A", "B"):
    _r = C.post("/api/suppliers", json={"name": f"U195 Taminotchi {_n}", "phone": "+998901112233"})
    assert _r.status_code == 200, _r.text
    ID["S" + _n] = js(_r).get("id") or (js(_r).get("supplier") or {}).get("id")
for _n in ("A", "B"):
    _r = C.post("/api/murojaatlar", data={"turi": "savol", "matn": f"U195 murojaat {_n} matni"})
    assert _r.status_code == 200, _r.text
    ID["M" + _n] = js(_r).get("id")
assert all(ID.values()), ID

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


def kontekst():
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.goto(B + "/login")
    pg.fill("input[name=username]", "u195_admin")
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


ILGAK = """() => { window.__msg = []; window.showMsg = (t, ty) => { window.__msg.push([String(t), ty]); };
  window.customConfirm = async () => true; window.showConfirmModal = async () => true; }"""


def och(pg, yol):
    for _n in range(3):
        try:
            pg.goto(B + yol, wait_until="networkidle")
            break
        except Exception as _e:            # noqa: BLE001
            if "ERR_ABORTED" not in str(_e) or _n == 2:
                raise
            pg.wait_for_timeout(3500)
    pg.wait_for_timeout(500)
    pg.evaluate(ILGAK)


def msg(pg):
    return pg.evaluate("() => window.__msg || []")


def teskari(pg, naqsh, b1, b2):
    """1-GET USHLANADI (javobi b1), keyingilari darhol b2; `bitir()` — 1-sini endi beradi (avval javob, keyin `unroute`)."""
    held = []

    def h(route):
        if route.request.method != "GET":
            route.continue_()
            return
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
    section("S5 — «Kirim qilish»: yangi material yaratilayotganda ta'minotchi almashtirilsa — kirim yuborilmaydi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx = pg = None
    try:
        TAYYORLA = """(sid) => { const s = document.getElementById('r-supplier'); s.value = String(sid); onSupplierChange();
            if (!apCreatingNewItem) apToggleNewItem();
            document.getElementById('ap-newitem-name').value = 'U195 Yangi material';
            const c = document.getElementById('ap-newitem-category');
            if (c) { const o = [...c.options].find(o => o.value && o.value !== 'Penoplast'); if (o) c.value = o.value; }
            document.getElementById('ap-qty').value = '5'; document.getElementById('ap-price').value = '1000';
            const u = document.querySelector('#ap-prod-type-toggle .rcv-cat-opt'); if (u) selectProdType(u, u.dataset.value); }"""
        YARATILDI = json.dumps({"id": ID["KLEY"], "item_name": "U195 Yangi material", "unit": "kg", "category": "Kimyo",
                                "is_penoplast": False, "volume_per_unit": 1.0})

        def kirim_sahna(almashtir):
            """har sahna — YANGI brauzer konteksti (savat qoralamasi brauzer xotirasida saqlanadi va sahifa ochilganda tiklanadi)"""
            global ctx, pg
            if ctx:
                ctx.close()
            ctx, pg = kontekst()
            och(pg, "/suppliers/receive")
            pg.evaluate(TAYYORLA, ID["SA"])
            pg.wait_for_timeout(1200)
            ush, yub = [], []

            def h(route):
                rq = route.request
                if rq.method == "POST" and rq.url.endswith("/api/inventory") and not ush:
                    ush.append(route)
                elif rq.method == "POST" and "/api/inventory/receipt" in rq.url:
                    yub.append(rq.post_data)
                    route.fulfill(status=500, content_type="application/json", body='{"detail":"sinov — saqlanmadi"}')
                else:
                    route.continue_()
            pg.route("**/api/inventory**", h)
            pg.evaluate("() => { submitReceive(); }")
            pg.wait_for_timeout(600)
            if almashtir:
                pg.evaluate("(sid) => { const s = document.getElementById('r-supplier'); s.value = String(sid); onSupplierChange(); }", ID["SB"])
                pg.wait_for_timeout(1200)
            for r in ush:
                r.fulfill(status=200, content_type="application/json", body=YARATILDI)
            pg.wait_for_timeout(2500)
            pg.unroute("**/api/inventory**", h)
            return ush, [json.loads(x).get("supplier_id") if x else None for x in yub], msg(pg)
        ush, yub, m = kirim_sahna(True)
        check("S5a ta'minotchi A, yangi material yaratilayotganda B tanlandi → kirim YUBORILMADI (asl: `supplier_id` = B bilan yuborilardi)",
              len(ush) == 1 and not yub, (len(ush), yub, m))
        check("S5b … sabab: «Ta'minotchi o'zgartirildi — kirim yuborilmadi …», savat joyida",
              any("Ta'minotchi o'zgartirildi" in x[0] for x in m) and pg.evaluate("() => apBasket.length") >= 1, m)
        ush, yub, m = kirim_sahna(False)
        check("S5c NAZORAT almashtirmasdan: kirim A ta'minotchiga yuborildi", len(ush) == 1 and yub == [ID["SA"]], (len(ush), yub, m))
    except Exception as _e:                # noqa: BLE001
        check("S5! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        if ctx:
            ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("S1 — «Yordam / Murojaat»: oxirgi bosilgan murojaat ochiladi, javob unga ketadi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        och(pg, "/murojaat")
        held = []

        def h1(route):
            if route.request.method == "GET" and route.request.url.rstrip("/").endswith(f"/api/murojaatlar/{ID['MA']}") and not held:
                held.append(route)
            else:
                route.continue_()
        pg.route("**/api/murojaatlar/*", h1)
        pg.evaluate("(id) => { mjOch(id); }", ID["MA"])
        pg.wait_for_timeout(400)
        pg.evaluate("(id) => { mjOch(id); }", ID["MB"])
        pg.wait_for_timeout(1200)
        for r in held:
            r.continue_()
        pg.unroute("**/api/murojaatlar/*", h1)
        pg.wait_for_timeout(1500)
        _h = pg.evaluate("() => ({ochiq: MJ.ochiq, s: document.getElementById('mjYozSarlavha').textContent, "
                         "x: document.getElementById('mjXabarlar').innerText})")
        check(f"S1a #{ID['MA']} ochilayotganda #{ID['MB']} bosildi, #{ID['MA']} javobi keyin keldi → #{ID['MB']} ochiq qoldi "
              f"(asl: #{ID['MA']} bosardi)", len(held) == 1 and _h["ochiq"] == ID["MB"] and f"#{ID['MB']}" in _h["s"]
              and "U195 murojaat B" in _h["x"] and "U195 murojaat A" not in _h["x"], _h)
        yub = []
        pg.on("request", lambda q: yub.append(q.url.replace(B, "")) if q.method == "POST" and "/xabar" in q.url else None)
        pg.evaluate("() => { document.getElementById('mjJavobMatn').value = 'U195 qo\\'shimcha'; mjJavob(); }")
        pg.wait_for_timeout(2000)
        _xb = js(C.get(f"/api/murojaatlar/{ID['MB']}")).get("xabarlar") or []
        check(f"S1b «Yuborish» → #{ID['MB']} ga (asl: #{ID['MA']} ga)", yub == [f"/api/murojaatlar/{ID['MB']}/xabar"]
              and any("U195 qo'shimcha" in (x.get("matn") or "") for x in _xb), (yub, _xb[-1:] if _xb else None))
        och(pg, "/murojaat")
        pg.evaluate("(id) => { mjOch(id); }", ID["MA"])
        pg.wait_for_timeout(1500)
        _h = pg.evaluate("() => ({ochiq: MJ.ochiq, s: document.getElementById('mjYozSarlavha').textContent})")
        check(f"S1c NAZORAT: #{ID['MA']} ochildi", _h["ochiq"] == ID["MA"] and f"#{ID['MA']}" in _h["s"], _h)
    except Exception as _e:                # noqa: BLE001
        check("S1! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("S2 — Hodimlar → «To'lov tarixi»: oynada faqat o'sha hodimning tarixi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        och(pg, "/kpi")
        H1 = [{"pay_type": "fixed", "fixed_amount": 1000000, "effective_month": 1, "effective_year": 2026, "reason": "ESKI A tarixi"}]
        H2 = [{"pay_type": "fixed", "fixed_amount": 2000000, "effective_month": 2, "effective_year": 2026, "reason": "YANGI B tarixi"}]
        held, bitir = teskari(pg, "**/api/employees/*/compensation-history", H1, H2)
        pg.evaluate("() => { editingEmpId = 9001; openCompHistoryModal(); }")
        pg.wait_for_timeout(400)
        pg.evaluate("() => { closeCompHistoryModal(); editingEmpId = 9002; openCompHistoryModal(); }")
        pg.wait_for_timeout(800)
        bitir()
        _t = pg.evaluate("() => document.getElementById('ch-list').textContent")
        check("S2a A oynasi yopilib B niki ochildi, A javobi keyin keldi → B oynasida B ning tarixi (asl: «ESKI A tarixi»)",
              len(held) == 1 and "YANGI B tarixi" in _t and "ESKI A tarixi" not in _t, _t[:200])
        held, bitir = teskari(pg, "**/api/employees/*/compensation-history", H1, H2)
        pg.evaluate("() => { editingEmpId = 9001; openCompHistoryModal(); }")
        pg.wait_for_timeout(400)
        pg.evaluate("() => { closeCompHistoryModal(); editingEmpId = null; }")
        bitir()
        _t = pg.evaluate("() => document.getElementById('ch-list').textContent")
        check("S2b oyna yopilib hodim tahriri ham yopildi, javob keyin keldi → yashirin ro'yxatga yozilmadi", len(held) == 1
              and "ESKI A tarixi" not in _t, (len(held), _t[:200]))
        _hs = lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(H2))   # noqa: E731
        pg.route("**/api/employees/*/compensation-history", _hs)
        pg.evaluate("() => { editingEmpId = 9002; openCompHistoryModal(); }")
        pg.wait_for_timeout(1000)
        _t = pg.evaluate("() => document.getElementById('ch-list').textContent")
        check("S2c NAZORAT bitta so'rov → tarix chizildi", "YANGI B tarixi" in _t, _t[:200])
        pg.unroute("**/api/employees/*/compensation-history", _hs)
    except Exception as _e:                # noqa: BLE001
        check("S2! ssenariy", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("S4 — Sozlamalar → Telegram bot: chat ID — oxirgi javobdan (jurnal N3)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        held = []

        def h4(route):
            if route.request.method != "GET":
                route.continue_()
                return
            if not held:
                held.append(route)
            else:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps({"configured": False, "uses_system_bot": True, "chat_id": "YANGI_777"}))
        pg.route("**/api/settings/telegram-bot", h4)
        pg.goto(B + "/sozlamalar", wait_until="domcontentloaded")     # ochilgandagi so'rov USHLANGAN — `networkidle` bo'lmaydi
        pg.wait_for_timeout(1500)
        pg.evaluate(ILGAK)
        pg.evaluate("() => { loadTgBot(); }")
        pg.wait_for_timeout(1000)
        for r in held:
            r.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"configured": False, "uses_system_bot": True, "chat_id": "ESKI_111"}))
        pg.unroute("**/api/settings/telegram-bot", h4)
        pg.wait_for_timeout(1200)
        _v = pg.evaluate("() => (document.getElementById('tg-chat') || {}).value")
        check("S4a ochilgandagi so'rov keyingisidan kech keldi → chat ID «YANGI_777» (asl: «ESKI_111»)", len(held) == 1 and _v == "YANGI_777", _v)
        _hs = lambda r: r.fulfill(status=200, content_type="application/json",                      # noqa: E731
                                  body=json.dumps({"configured": False, "uses_system_bot": True, "chat_id": "BITTA_555"}))
        pg.route("**/api/settings/telegram-bot", _hs)
        pg.evaluate("() => { loadTgBot(); }")
        pg.wait_for_timeout(1000)
        _v = pg.evaluate("() => (document.getElementById('tg-chat') || {}).value")
        check("S4b NAZORAT bitta so'rov → chat ID «BITTA_555»", _v == "BITTA_555", _v)
        pg.unroute("**/api/settings/telegram-bot", _hs)
    except Exception as _e:                # noqa: BLE001
        check("S4! ssenariy", False, f"{type(_e).__name__}: {_e}")
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
