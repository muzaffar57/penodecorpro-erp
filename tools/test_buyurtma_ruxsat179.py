#!/usr/bin/env python3
"""
test_buyurtma_ruxsat179.py — kech144 (zip 179, AUDIT 2-to'lqin — Buyurtmalar P2-16): «Buyurtmalar» sahifasida server rad etadigan (403)
tugmalar ko'rinmaydi — har biri o'z marshruti ruxsati bilan. HAQIQIY Chromium, HAQIQIY lokal server (uvicorn, test bazasi); ko'rinish —
`getComputedStyle` + o'lcham (JS `style.display = 'block'` qilgandan keyin ham).

NIMA UCHUN KERAK (asl kod = zip 178; audit `work/k173_tayyorgarlik/agentlar/buyurtma/HISOBOT.md` P2-16): faqat «Buyurtmalar: Ko'rish»
roli «+ Yangi buyurtma», «Tahrirlash», «Tayyor», «O'chirish», «📌», «Jarayonga olish», kelishilgan summa ✏️, «+ Qisman topshirish»,
«Bir yo'la to'liq topshirish», «+ To'lov qo'shish», to'lov / yuk xati / fayl ✕, fayl yuklash maydonini ko'rardi — formani to'ldirib,
oxirida 403 «ruxsat yo'q» olardi; «/orders?yangi=1» ham formani ochardi.
  R1  Admin — hamma tugma ko'rinadi (ijobiy nazorat).
  R2  «Faqat ko'rish» — yozuvchi tugmalar YO'Q (ro'yxat, tafsilot, PDF, «Hisob-kitob» — bor).
  R3  «To'lov qabul qiluvchi» (to'lov: yaratish) — «+ To'lov qo'shish» BOR, to'lov ✕ va boshqalari YO'Q.
  R4  «Faqat ko'rish» — qoralama banneridagi «▶️ Jarayonga olish» YO'Q; «?yangi=1» — forma ochilmaydi, sabab ko'rinadi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 178) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_buyurtma_ruxsat179.py
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

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "buyurtma_ruxsat179_test"
_T = tempfile.mkdtemp(prefix="br179_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'br179.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol, Project, OrderAttachment   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def rol_qoy(login, ruxsat, nom):
    def f(s):
        u = s.query(User).filter(User.username == login).first()
        r = Rol(company_id=u.company_id, nom=nom, kod=None, ruxsatlar=json.dumps(ruxsat), tavsif="")
        s.add(r)
        s.flush()
        u.rol_id = r.id
        return r.id
    return db_ishi(f)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "b179_admin", PAROL, UserRole.ADMIN, "B179 Admin", company_id=1)
    for _u in ("b179_kor", "b179_tol"):
        auth.create_user(s, _u, PAROL, UserRole.MANAGER, _u.upper(), company_id=1)
PRJ = Project(company_id=1, client_name="B179 Mijoz", project_name="B179 loyiha", total_budget=0, total_paid=0)
s.add(PRJ)
s.commit()
ID = {"PRJ": PRJ.id}
s.close()
KOR = {"buyurtma": ["korish"], "tolov": ["korish"], "yetkazish": ["korish"], "buyurtma_fayl": ["korish"], "loyiha": ["korish"]}
rol_qoy("b179_kor", KOR, "B179 Faqat ko'rish")
rol_qoy("b179_tol", dict(KOR, tolov=["korish", "yaratish"]), "B179 To'lov qabul qiluvchi")

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert C.post("/login", data={"username": "b179_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)


def buyurtma(nom, n=4, draft=False):
    tana = {"project_id": ID["PRJ"], "order_type": "product", "items": [
        {"name": nom, "category": "panel", "width": 50, "thickness": 5, "quantity": n, "unit_price": 10000, "is_coated": False}]}
    if draft:
        tana["is_draft"] = True
    r = C.post("/api/orders?confirm_shortage=true", json=tana)
    assert r.status_code == 200, r.text
    return js(r)["id"], js(r)["items"][0]["id"]


ID["O"], ID["OI"] = buyurtma("B179 asosiy detal", 4)
_rd = C.post("/api/deliveries", json={"order_id": ID["O"], "items": [{"order_item_id": ID["OI"], "quantity": 1}], "received_by": None,
                                      "notes": None, "transport_carrier": None, "transport_cost": 0, "transport_payer": "none",
                                      "payment_amount": None, "payment_method": "naqd"})
assert _rd.status_code == 200, _rd.text
_rp = C.post("/api/payments", json={"order_id": ID["O"], "amount": 5000, "payment_method": "naqd", "notes": "b179"})
assert _rp.status_code == 200, _rp.text
db_ishi(lambda d: d.add(OrderAttachment(order_id=ID["O"], file_url="/static/uploads/order_attachments/b179_yoq.png",
                                        file_name="b179.png", uploaded_by="B179")))
ID["D"], _ = buyurtma("B179 qoralama detal", 2, draft=True)

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
JS_XATO = []

# Ko'rinish: element bor, `display` none emas, o'lchami bor. JS «ko'rsatadigan» holatda tekshiriladi: tugma `style.display` i majburan
# 'block' qilinadi (JS shuni qiladi) — ruxsatsizda baribir ko'rinmasligi kerak.
SELEKTOR = {
    "«+ Yangi buyurtma»": '[onclick^="showNewForm("]',
    "«📋 Nusxa olish»": "#btn-duplicate",
    "«✓ Tayyor»": "#btn-ready",
    "«✏️ Tahrirlash»": "#btn-edit",
    "«📌 Pin»": "#btn-pin",
    "ro'yxatdagi 📌": ".pin-toggle-btn",
    "kelishilgan summa ✏️": '[onclick^="editAgreedAmount("]',
    "«🗑 O'chirish»": "#btn-delete",
    "«+ Qisman topshirish»": "#btn-new-delivery",
    "«✅ Bir yo'la to'liq»": "#btn-quick-deliver",
    "yuk xati ✕": '[onclick^="deleteDelivery("]',
    "«+ To'lov qo'shish»": "#btn-add-payment",
    "to'lov ✕": '[onclick^="deletePayment("]',
    "fayl yuklash": "#ordPageWrap .dropzone",
    "fayl ✕": '[onclick^="deleteOrderAttachment("]',
}
KORINISH = """(sels) => { const n = {};
  for (const [k, s] of Object.entries(sels)) {
    const els = [...document.querySelectorAll(s)];
    // JS «ko'rsatadigan» holat: inline `display: none` olib tashlanadi (JS shunday ochadi) — ruxsatsizda CSS `!important` baribir yashiradi
    els.forEach(e => { if (e.style && e.style.display === 'none') e.style.display = ''; });
    n[k] = els.filter(e => getComputedStyle(e).display !== 'none').length;
  }
  return n; }"""


def kontekst(user):
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


def tanla(pg, oid):
    pg.goto(B + f"/orders?order={oid}", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    try:
        pg.evaluate("""() => { document.querySelectorAll('#payBody, #dlvBody').forEach(e => { e.style.display = ''; }); }""")
    except Exception:                      # noqa: BLE001
        pass
    pg.wait_for_timeout(300)
    return pg.evaluate(KORINISH, SELEKTOR)


br = pw_ctx = None
if PW_BOR and server.started:
    pw_ctx = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                              "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        _pw_x = f"{type(_e).__name__}: {_e}"
check("T0 lokal server va Chromium", bool(server.started and br), _pw_x)

if br:
    section("R1. Admin — hamma tugma (ijobiy nazorat)")
    ctx, pg = kontekst("b179_admin")
    try:
        _a = tanla(pg, ID["O"])
        check("R1 admin: hamma yozuvchi tugma ko'rinadi", all((v or 0) > 0 for v in _a.values()), _a)
    except Exception as _x:               # noqa: BLE001
        check("R1 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    section("R2 / R4. «Faqat ko'rish»")
    ctx, pg = kontekst("b179_kor")
    try:
        _k = tanla(pg, ID["O"])
        _pdf = pg.evaluate("() => { const a = document.getElementById('btn-pdf'); return !!a && getComputedStyle(a).display !== 'none'; }")
        check("R2 «Faqat ko'rish» — yozuvchi tugmalar YO'Q (ilgari hammasi ko'rinardi — oxirida 403); PDF havolasi bor",
              all(v == 0 for v in _k.values()) and _pdf, (_k, _pdf))
        pg.goto(B + f"/orders?order={ID['D']}", wait_until="networkidle")
        pg.wait_for_timeout(1500)
        _qb = pg.evaluate("""() => { const b = document.getElementById('draftBanner'); const t = document.querySelector('[onclick^="activateDraft("]');
            return {banner: !!b && getComputedStyle(b).display !== 'none', tugma: !!t && getComputedStyle(t).display !== 'none'}; }""")
        check("R4a qoralama — banner bor, «▶️ Jarayonga olish» YO'Q (`/activate` — «Buyurtmalar: Tahrirlash»)",
              _qb.get("banner") is True and _qb.get("tugma") is False, _qb)
        pg.goto(B + "/orders?yangi=1", wait_until="networkidle")
        pg.wait_for_timeout(1200)
        _f = pg.evaluate("""() => { const f = document.getElementById('newOrderForm');
            return {forma: !!f && getComputedStyle(f).display !== 'none', url: location.search,
                    xabar: (document.querySelector('.toast, #toast, .msg-box, .show-msg') || {}).textContent || ''}; }""")
        check("R4b «?yangi=1» — yaratish ruxsati yo'q: forma OCHILMAYDI (ilgari ochilib, saqlashda 403)",
              _f.get("forma") is False and "yangi" not in (_f.get("url") or ""), _f)
    except Exception as _x:               # noqa: BLE001
        check("R2 / R4 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    section("R3. «To'lov qabul qiluvchi» (to'lov: yaratish)")
    ctx, pg = kontekst("b179_tol")
    try:
        _t = tanla(pg, ID["O"])
        check("R3 «+ To'lov qo'shish» BOR; to'lov ✕ (to'lov: o'chirish) va boshqa yozuvchi tugmalar YO'Q",
              _t.get("«+ To'lov qo'shish»", 0) > 0 and all(v == 0 for k, v in _t.items() if k != "«+ To'lov qo'shish»"), _t)
    except Exception as _x:               # noqa: BLE001
        check("R3 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    section("Z. Sahifa xatolari")
    check("Z1 ushlanmagan JS xatosi yo'q", not JS_XATO, JS_XATO[:5])

try:
    if br:
        br.close()
    if pw_ctx:
        pw_ctx.stop()
except Exception:                          # noqa: BLE001
    pass
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
