#!/usr/bin/env python3
"""
test_tayyor_ui177.py — kech144 (zip 177, AUDIT 2-to'lqin): «Tayyor mahsulotlar», «Qaytarishlar», «Qarzdorlar» — yuklovchilar, ruxsatsiz
tugmalar va amal xatolari matni. HAQIQIY Chromium, HAQIQIY lokal server (uvicorn, test bazasi). Tarmoq xatolari Playwright `route` bilan
ataylab beriladi: javob 502 / 500 / 401 / 403 / 422 (`fulfill`), so'rov serverda BAJARILIB javob 502 (`route.fetch` + `fulfill`), tarmoq
uzilishi (`abort`), javob ushlab turiladi (kech javob — poyga).

NIMA UCHUN KERAK (asl kod = zip 176; audit `work/k173_tayyorgarlik/agentlar/tayyor/HISOBOT.md` C va D bo'limlari)
  C#7   «Qaytarishlar» statistikasi — 401 / 500 da «undefined ta», «0 so'm» (yolg'on).
  C#8   «Tayyor mahsulotlar» statistikasi — 500 da «Ombor qiymati 0 so'm», «Omborda 0».
  C#9   Ro'yxat — sababsiz «Yuklashda xato» yoki 403 da `fpItems` obyekt bo'lib sahifa yiqilardi; kech javob yangisini bosardi.
  C#10  «Foyda hisobi» — yuklanmasa jim «Penoplast 0 so'm»; A ning raqamlari B sarlavhasi ostida.
  C#11  Loy narxi — yuklanmasa «retsept tanlanmagan» (tannarx kam); retsept tez almashtirilsa eski javob yangisini bosardi.
  C#14  Brak hisoboti — 403 da yolg'on «… topilmadi». C#15: brak tahlili — 502 da «Xato (502)», eski oy javobi yangisini bosardi;
        belgi jim. C#16: «To'lovlar tarixi» — 500 da yolg'on «Bu oyda to'lov yo'q», A ning qatorlari B ro'yxatida.
  C#17  «Hisob-kitob qilish» — internet uzilsa hech narsa, 502 da «❌ Xato».
  C#20  Server rad etadigan tugmalar hammaga ko'rinardi (bosilsa 403): «Penoplast detal», «Sotish», savatcha belgisi, guruh 💵, «Brak»,
        «Yana ishlab chiqarish», ✏️ / narx, «Sotuvga tayyor», «Bandni bekor qilish», ✕ / «O'chirish», rasm; qaytarish 🗑 / rasm;
        «To'lov qabul qilish», «Qaytarildi», «+ Yangi kategoriya», kategoriya ✕, «💰 To'lov qo'shish».
  Brak hisoboti: noto'g'ri sana (`2026-13-40`) — 500 («server javob bermadi»).
  D     «Xato», «Server xatosi», 502 da «Server bilan aloqa yo'q», inglizcha «Failed to fetch», 422 da «Xato yuz berdi»; «Qaytarildi»
        bayrog'i sahifa yangilanishidan 1,3 s oldin bo'shardi — ikkinchi bosish ikkinchi so'rov yuborardi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 176) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_tayyor_ui177.py
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
PG_BAZA = "tayyor_ui177_test"
_T = tempfile.mkdtemp(prefix="tui177_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tui177.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, Rol, Inventory, Recipe, RecipeIngredient, Project, FinishedProduct,   # noqa: E402
                    StockSource, ProductionStatus, ReturnItem, ReturnReason)
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
        print(f"  ✗ {label}   {str(detail)[:700]}")


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
    auth.create_user(s, "t177_admin", PAROL, UserRole.ADMIN, "T177 Admin", company_id=1)
    for _u in ("t177_kor", "t177_sot"):
        auth.create_user(s, _u, PAROL, UserRole.MANAGER, _u.upper(), company_id=1)
PENO = Inventory(company_id=1, item_name="T177 Penoplast", unit="blok", stock_quantity=10000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="T177 Kley", unit="kg", stock_quantity=100000, price_per_unit=2000, category="Kimyo")
PRJ = Project(company_id=1, client_name="T177 Mijoz", project_name="T177 loyiha", total_budget=0, total_paid=0)
s.add_all([PENO, KLEY, PRJ])
s.flush()
REC = Recipe(company_id=1, name="T177 retsept A", batch_size_kg=100.0)
REC2 = Recipe(company_id=1, name="T177 retsept B", batch_size_kg=100.0)
s.add_all([REC, REC2])
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
s.add(RecipeIngredient(recipe_id=REC2.id, inventory_id=KLEY.id, quantity_kg=50.0))


def tm(nom, miqdor, narx=50000, band=0.0, holat=ProductionStatus.READY):
    fp = FinishedProduct(company_id=1, name=nom, category="profil", quantity=miqdor, produced_quantity=miqdor, unit="metr",
                         unit_price=narx, cost_price=10000, source=StockSource.PRODUCED, reserved_quantity=band,
                         production_status=holat, is_coated=False)
    s.add(fp)
    s.flush()
    return fp.id


ID = {"R": tm("T177 Tayyor profil", 10, band=3.0), "J": tm("T177 Jarayon profil", 4, holat=ProductionStatus.IN_PROGRESS),
      "G1": tm("T177 Guruh profil", 5), "G2": tm("T177 Guruh profil", 6), "X": tm("T177 Ochiriladigan profil", 4),
      "B": tm("T177 Foyda B profil", 7, narx=70000)}
s.commit()
ID.update({"PENO": PENO.id, "KLEY": KLEY.id, "REC": REC.id, "REC2": REC2.id, "PRJ": PRJ.id})
s.close()
rol_qoy("t177_kor", {"tayyor": ["korish"], "sotuv": ["korish"], "qaytarish": ["korish"], "qarz": ["korish"], "tolov": ["korish"]},
        "T177 Faqat ko'rish")
rol_qoy("t177_sot", {"tayyor": ["korish"], "sotuv": ["korish", "yaratish"]}, "T177 Sotuvchi")

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert C.post("/login", data={"username": "t177_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)


def buyurtma(nom, narx, n):
    r = C.post("/api/orders?confirm_shortage=true", json={"project_id": ID["PRJ"], "order_type": "product", "items": [
        {"name": nom, "category": "panel", "width": 50, "thickness": 5, "quantity": n, "unit_price": narx, "is_coated": False}]})
    assert r.status_code == 200, r.text
    oid = js(r)["id"]
    oi = js(r)["items"][0]["id"]
    rd = C.post("/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": oi, "quantity": n}], "received_by": None,
                                         "notes": None, "transport_carrier": None, "transport_cost": 0, "transport_payer": "none",
                                         "payment_amount": None, "payment_method": "naqd"})
    assert rd.status_code == 200, rd.text
    return oid, oi


ID["OQ"], ID["OQI"] = buyurtma("T177 qarz detali", 10000, 5)              # qarzdor (to'lanmagan)
ID["OO"], ID["OOI"] = buyurtma("T177 ortiqcha detali", 10000, 2)          # ortiqcha to'langan — «Mijozga qaytarish kerak»
_rp = C.post("/api/payments", json={"order_id": ID["OO"], "amount": 50000, "payment_method": "naqd", "notes": "t177",
                                    "confirm_overpay": True})
assert _rp.status_code == 200, _rp.text
for _kat, _nom in (("t177_a", "T177 ijara A"), ("t177_b", "T177 ijara B")):
    _rk = C.post("/api/obligations/recurring", params={"category": _kat, "label": _nom, "monthly_target": "300000", "icon": "🏠",
                                                       "due_day": "5"})
    assert _rk.status_code == 200, _rk.text


def qaytarish(nom, sabab, summa):
    def f(d):
        r = ReturnItem(company_id=1, order_id=ID["OQ"], order_item_id=ID["OQI"], item_name=nom, quantity=1, unit="metr",
                       reason=sabab, refund_amount=summa, is_refunded=False)
        d.add(r)
        d.flush()
        return r.id
    return db_ishi(f)


ID["RQ"] = qaytarish("T177 qaytgan (hisob-kitob)", ReturnReason.CUSTOMER_REQUEST, 10000)
ID["RB"] = qaytarish("T177 brak qaytgan", ReturnReason.DEFECT, 0)


def tm_band(fp_id):
    return db_ishi(lambda d: float(d.get(FinishedProduct, fp_id).reserved_quantity or 0))


def tm_holat(fp_id):
    return db_ishi(lambda d: d.get(FinishedProduct, fp_id).production_status.value)


def qaytarish_bor(rid):
    return db_ishi(lambda d: d.get(ReturnItem, rid) is not None)


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


def kontekst(user="t177_admin", oldin=None):
    """`oldin` — sahifa ochilishidan OLDIN qo'yiladigan `route` lar: [(naqsh, ishlovchi), ...]."""
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, "")))
          if "/api/" in q.url and q.method in ("POST", "PUT", "DELETE") else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    for naqsh, h in (oldin or []):
        ctx.route(naqsh, h)
    return ctx, pg


# Xabarlar, tasdiq va kiritish oynalari: `window.__msg`; tasdiq javobi — `window.__ha` (standart: true)
ILGAK = """() => { window.__msg = []; window.__ha = true; window.__kirit = null;
  window.showMsg = (t, ty) => { window.__msg.push([String(t), ty || '']); };
  window.alert = (t) => { window.__msg.push([String(t), 'alert']); };
  window.xabarOyna = async (t) => { window.__msg.push([String(t), 'oyna']); };
  window.customConfirm = async () => window.__ha;
  window.kiritishOyna = async () => window.__kirit;
  window.open = () => null; }"""
SAHIFA_502 = {"status": 502, "content_type": "text/html", "body": "<html><body><h1>502 Bad Gateway</h1></body></html>"}


def jsn(status, tana):
    return {"status": status, "content_type": "application/json", "body": json.dumps(tana)}


def ochiq(pg, yol, ilgak=True):
    pg.goto(B + yol, wait_until="networkidle")
    pg.wait_for_timeout(400)
    if ilgak:
        pg.evaluate(ILGAK)


def msg_matn(pg):
    try:
        return " || ".join(m[0] for m in (pg.evaluate("() => window.__msg || []") or []))
    except Exception:                      # noqa: BLE001
        return ""


def msg_tozala(pg):
    pg.evaluate("() => { window.__msg = []; }")


def matn(pg, sel):
    try:
        return pg.evaluate(f"() => {{ const e = document.querySelector({json.dumps(sel)}); return e ? e.textContent : null; }}")
    except Exception:                      # noqa: BLE001
        return None


def soni(pg, sel):
    try:
        return pg.evaluate(f"() => document.querySelectorAll({json.dumps(sel)}).length")
    except Exception:                      # noqa: BLE001
        return None


def baj(pg, ifoda, kutish=700):
    x = None
    try:
        pg.evaluate(ifoda)
    except Exception as e:                 # noqa: BLE001 — sahifa qayta yuklangan
        x = str(e)[:160]
    pg.wait_for_timeout(kutish)
    return x


def sorovlar(nima, usul="POST"):
    return [x for x in SOROV if nima in x[1] and x[0] == usul]


class Bajar502:
    """So'rov serverga YETADI va bajariladi (`route.fetch`), lekin brauzerga 502 HTML qaytadi (deploy almashinuvi)."""

    def __init__(self):
        self.holat = []

    def __call__(self, route):
        try:
            j = route.fetch()
            self.holat.append(j.status)
        except Exception as e:             # noqa: BLE001
            self.holat.append(f"{type(e).__name__}")
        route.fulfill(**SAHIFA_502)


class Ushla:
    """Shartga mos so'rov ushlab turiladi (keyin `qoyib_yubor` — berilgan javob bilan), qolganlari o'tadi."""

    def __init__(self, shart):
        self.shart = shart
        self.ushlangan = []

    def __call__(self, route):
        if self.shart(route.request.url) and not self.ushlangan:
            self.ushlangan.append(route)
            return
        route.continue_()

    def qoyib_yubor(self, **javob):
        for r in self.ushlangan:
            try:
                r.fulfill(**javob)
            except Exception:              # noqa: BLE001
                pass


FP_ROYXAT = re.compile(r".*/api/finished(\?show_all=true)?$")
UZILISH = "internet aloqasi yo'q"
SERVER = "server javob bermadi"

if br:
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("A. «Tayyor mahsulotlar» — yuklovchilar (C#8, C#9, C#10, C#11)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/finished")
        # kech145 (MOSLANDI — mut177 M01): kartalar HTML da «—» bilan boshlanadi — avval yuklangan qiymat, so'ng yiqilgan qayta so'rov
        _vt0, _vq0 = matn(pg, "#v-total"), matn(pg, "#k-total-qty")
        pg.route("**/api/finished/stats", lambda r: r.fulfill(**jsn(500, {"detail": "Internal Server Error"})))
        baj(pg, "() => { loadStats(); }")
        _vt, _vq, _iz = matn(pg, "#v-total"), matn(pg, "#k-total-qty"), matn(pg, "#v-total-izoh")
        check("A1 (C#8) statistika yuklangan, keyingi so'rov 500 — «Ombor qiymati» va «Omborda» «—» (ESKI qiymat qolmaydi), izohda sabab "
              "(ilgari «0 so'm» / eski qiymat)",
              _vt0 not in (None, "—") and _vq0 not in (None, "—") and _vt == "—" and _vq == "—"
              and "Statistika yuklanmadi" in (_iz or "") and SERVER in (_iz or ""), (_vt0, _vq0, _vt, _vq, _iz))
        pg.unroute("**/api/finished/stats")

        pg.route(FP_ROYXAT, lambda r: r.fulfill(**jsn(403, {"detail": "Ruxsat yo'q"})))
        baj(pg, "() => { loadFp(); }")
        _l = matn(pg, "#fpList") or ""
        check("A2 (C#9) ro'yxat 403 — sabab ro'yxat o'rnida, `fpItems` massiv qoladi (ilgari obyekt — sahifa yiqilardi)",
              "Tayyor mahsulotlar yuklanmadi" in _l and "ruxsati yo'q" in _l
              and pg.evaluate("() => Array.isArray(fpItems) && fpItems.length > 0"), _l[:200])
        pg.unroute(FP_ROYXAT)
        pg.route(FP_ROYXAT, lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, "() => { loadFp(); }")
        _l = matn(pg, "#fpList") or ""
        check("A3 (C#9) ro'yxat 502 — «… yuklanmadi — server javob bermadi» (ilgari sababsiz «Yuklashda xato»)",
              "Tayyor mahsulotlar yuklanmadi" in _l and SERVER in _l, _l[:200])
        pg.unroute(FP_ROYXAT)

        # birinchi (eski) so'rov — `show_all` siz (ushlanadi), ikkinchisi — `?show_all=true` (o'tadi): qaysi biri eski — URL dan aniq
        _u = Ushla(lambda u: "show_all" not in u)
        pg.route(FP_ROYXAT, _u)
        baj(pg, "() => { showAllFp = false; loadFp(); showAllFp = true; loadFp(); }", 1800)
        _u.qoyib_yubor(**jsn(200, []))
        pg.wait_for_timeout(700)
        _l = matn(pg, "#fpList") or ""
        check("A4 (C#9) kech kelgan ESKI javob (bo'sh ro'yxat) yangisini bosmaydi — mahsulotlar ko'rinib turadi",
              len(_u.ushlangan) == 1 and "T177 Tayyor profil" in _l and pg.evaluate("() => fpItems.length > 0"),
              (len(_u.ushlangan), _l[:200]))
        pg.unroute(FP_ROYXAT)
        baj(pg, "() => { showAllFp = false; loadFp(); }", 900)

        # C#10 — foyda oynasi
        pg.route(f"**/api/finished/{ID['R']}/profit", lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, f"() => {{ openProfitModal({ID['R']}); }}", 900)
        _pb = matn(pg, "#pm-body") or ""
        check("A5 (C#10) «Foyda hisobi» 502 — sabab (ilgari jim «Penoplast 0 so'm» va butun tannarx «narx farqi»)",
              "Foyda hisobi yuklanmadi" in _pb and SERVER in _pb, _pb[:200])
        pg.unroute(f"**/api/finished/{ID['R']}/profit")
        _u = Ushla(lambda u: f"/api/finished/{ID['R']}/profit" in u)
        pg.route("**/api/finished/*/profit", _u)
        baj(pg, f"() => {{ openProfitModal({ID['R']}); }}", 500)
        baj(pg, f"() => {{ openProfitModal({ID['B']}); }}", 1200)
        _u.qoyib_yubor(**jsn(200, {"success": True, "penoplast_cost": 777777, "loy_cost": 0, "loy_cost_per_kg": 0, "recipe": "",
                                   "volume_m3": 0.5, "loy_kg": 0}))
        pg.wait_for_timeout(700)
        _pb, _ps = matn(pg, "#pm-body") or "", matn(pg, "#pm-sub") or ""
        check("A6 (C#10) A ochilib darhol B ochilsa — A ning kech raqamlari (777 777) B sarlavhasi ostiga tushmaydi",
              len(_u.ushlangan) == 1 and "T177 Foyda B profil" in _ps and "777" not in _pb and "Yuklanmoqda" not in _pb, (_ps, _pb[:300]))
        pg.unroute("**/api/finished/*/profit")
        baj(pg, "() => { closeProfitModal(); }", 200)

        # C#11 — loy narxi
        baj(pg, """() => { openProduceModal(); const v = (id, x) => { const e = document.getElementById(id); if (e) e.value = x; };
              v('p-type', 'profil'); v('p-h', '10'); v('p-w', '10'); v('p-l', '10'); v('p-q', '1'); v('p-m3', '500000'); v('p-loy', '5');
              pCalc(); }""", 500)
        pg.route("**/api/loy-cost*", lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, f"() => loadLoyCost('{ID['REC']}')", 900)
        _pc = matn(pg, "#p-calc") or ""
        check("A7 (C#11) loy narxi 502 — kalkulyatorda sabab (ilgari «retsept tanlanmagan», tannarx loysiz)",
              "Loy narxi yuklanmadi" in _pc and SERVER in _pc and "retsept tanlanmagan" not in _pc, _pc[:300])
        pg.unroute("**/api/loy-cost*")
        _u = Ushla(lambda u: f"recipe_id={ID['REC']}" in u)
        pg.route("**/api/loy-cost*", _u)
        baj(pg, f"() => {{ loadLoyCost('{ID['REC']}'); }}", 400)
        baj(pg, f"() => loadLoyCost('{ID['REC2']}')", 1200)
        _b_narx = pg.evaluate("() => loyCostPerKg")
        _u.qoyib_yubor(**jsn(200, {"cost_per_kg": 999999, "recipe": "A-BELGI"}))
        pg.wait_for_timeout(600)
        _k = pg.evaluate("() => [loyCostPerKg, loyRecipeName]")
        check("A8 (C#11) retsept tez almashtirilsa — eski (A) javob yangi (B) loy narxini bosmaydi",
              len(_u.ushlangan) == 1 and _k[0] == _b_narx and _k[0] != 999999 and _k[1] != "A-BELGI", (_b_narx, _k))
        pg.unroute("**/api/loy-cost*")
        baj(pg, "() => { closeProduceModal(); }", 200)
    except Exception as _x:               # noqa: BLE001 — asl kodda yo'q funksiya / belgi: bo'lim yiqiladi, sinov QULAMAYDI
        check("A bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("B. «Tayyor mahsulotlar» — amal xatolari matni (D)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/finished")
        pg.evaluate("() => { window.__kirit = '60000'; }")
        pg.route(f"**/api/finished/{ID['R']}", lambda r: r.abort())
        baj(pg, f"() => editPrice({ID['R']})", 900)
        _m = msg_matn(pg)
        check("B1 narx — internet uzilsa «⚠️ Narx natijasi noma'lum: internet aloqasi yo'q …» (ilgari «Xato»)",
              "Narx natijasi noma'lum" in _m and UZILISH in _m, _m)
        pg.unroute(f"**/api/finished/{ID['R']}")
        msg_tozala(pg)
        pg.route(f"**/api/finished/{ID['R']}", lambda r: r.fulfill(**jsn(400, {"detail": "Narx juda katta"})))
        baj(pg, f"() => editPrice({ID['R']})", 900)
        _m = msg_matn(pg)
        check("B2 narx rad etildi — «❌ Narx saqlanmadi: <server sababi>»", "❌ Narx saqlanmadi: Narx juda katta" in _m, _m)
        pg.unroute(f"**/api/finished/{ID['R']}")
        msg_tozala(pg)

        pg.route(f"**/api/finished/{ID['X']}?*", lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, f"() => delFp({ID['X']}, 'produced')", 900)
        _m = msg_matn(pg)
        check("B3 o'chirish 502 — «⚠️ O'chirish natijasi noma'lum: server javob bermadi …» (ilgari «❌ Xato»)",
              "O'chirish natijasi noma'lum" in _m and SERVER in _m, _m)
        pg.unroute(f"**/api/finished/{ID['X']}?*")
        msg_tozala(pg)

        _h = Bajar502()
        pg.route(f"**/api/finished/{ID['J']}/complete", _h)
        baj(pg, f"() => markReady({ID['J']})", 1200)
        _m = msg_matn(pg)
        check("B4 «Sotuvga tayyor» bajarilib 502 qaytdi — «⚠️ «Sotuvga tayyor» natijasi noma'lum: server javob bermadi» (ilgari "
              "«❌ Server xatosi»)", _h.holat == [200] and "«Sotuvga tayyor» natijasi noma'lum" in _m and SERVER in _m
              and tm_holat(ID["J"]) == "ready", (_h.holat, _m, tm_holat(ID["J"])))
        pg.unroute(f"**/api/finished/{ID['J']}/complete")
        msg_tozala(pg)

        _h = Bajar502()
        pg.route(f"**/api/finished/{ID['R']}/release-reservation", _h)
        baj(pg, f"() => releaseFpReservation({ID['R']}, 'T177 Tayyor profil')", 1200)
        _m = msg_matn(pg)
        check("B5 «Bandni bekor qilish» bajarilib 502 — «⚠️ Band bekor qilish natijasi noma'lum …» (ilgari «Server bilan aloqa yo'q»)",
              _h.holat == [200] and "Band bekor qilish natijasi noma'lum" in _m and SERVER in _m and tm_band(ID["R"]) == 0,
              (_h.holat, _m, tm_band(ID["R"])))
        pg.unroute(f"**/api/finished/{ID['R']}/release-reservation")
        msg_tozala(pg)

        pg.route(f"**/api/finished/{ID['R']}/image", lambda r: r.abort())
        baj(pg, f"""() => uploadFpImage({ID['R']}, {{files: [new File([new Uint8Array([137, 80, 78, 71])], 'a.png', {{type: 'image/png'}})],
                                                    value: 'a.png'}})""", 900)
        _m = msg_matn(pg)
        check("B6 rasm — internet uzilsa «⚠️ Rasm natijasi noma'lum: internet aloqasi yo'q …» (ilgari «Server xatosi»)",
              "Rasm natijasi noma'lum" in _m and UZILISH in _m, _m)
        pg.unroute(f"**/api/finished/{ID['R']}/image")
        msg_tozala(pg)

        pg.evaluate("() => { window.__kirit = '5'; }")
        pg.route(f"**/api/finished/{ID['R']}/kam-chegara", lambda r: r.abort())
        baj(pg, f"() => fpKamChegaraYoz({ID['R']})", 900)
        _m = msg_matn(pg)
        check("B7 «Kam» chegarasi — internet uzilsa «⚠️ «Kam» chegarasi natijasi noma'lum …» (ilgari «Xato»)",
              "«Kam» chegarasi natijasi noma'lum" in _m and UZILISH in _m, _m)
        pg.unroute(f"**/api/finished/{ID['R']}/kam-chegara")
        msg_tozala(pg)

        pg.route("**/api/brak/tuzatish-materiallari", lambda r: r.abort())
        baj(pg, """() => { _tqMateriallar = null; const d = document.createElement('div'); d.id = 'zz177-tq-mat';
              document.body.appendChild(d); taqdirMaterialQosh({dataset: {p: 'zz177'}}); }""", 900)
        _m = msg_matn(pg)
        check("B8 brak taqdiri — xomashyo ro'yxati yuklanmasa «Xomashyo ro'yxati yuklanmadi — internet aloqasi yo'q» (ilgari "
              "inglizcha «Failed to fetch»)", "Xomashyo ro'yxati yuklanmadi" in _m and UZILISH in _m and "Failed to fetch" not in _m, _m)
        pg.unroute("**/api/brak/tuzatish-materiallari")
    except Exception as _x:               # noqa: BLE001
        check("B bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("C. «Qaytarishlar» — yuklovchilar va amallar (C#7, C#14, C#15, C#17, D)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst(oldin=[("**/api/returns/stats", lambda r: r.fulfill(**jsn(401, {"detail": "Not authenticated"}))),
                              ("**/api/reports/brak-tahlil?oylar=1", lambda r: r.fulfill(**SAHIFA_502))])
    try:
        ochiq(pg, "/returns")
        _bm, _tz = matn(pg, "#k-brak-month"), matn(pg, "#k-total-izoh") or ""
        _ss = pg.evaluate("() => { const x = document.getElementById('yukSessiya'); return !!x && !x.hidden; }")
        check("C1 (C#7) statistika 401 — «—» va «Statistika yuklanmadi — kirish muddati tugagan», kirish havolasi (ilgari «undefined ta»)",
              _bm == "—" and "Statistika yuklanmadi" in _tz and "kirish muddati" in _tz and _ss, (_bm, _tz, _ss))
        _bg = pg.evaluate("() => { const b = document.getElementById('brakTahlilBadge'); return b ? [b.textContent, b.title] : null; }")
        check("C2 brak ulushi belgisi 502 — «⚠️» va sabab (ilgari jim — bo'sh)",
              bool(_bg) and "⚠️" in _bg[0] and "Brak ulushi yuklanmadi" in (_bg[1] or ""), _bg)
        ctx.unroute("**/api/returns/stats")
        ctx.unroute("**/api/reports/brak-tahlil?oylar=1")

        pg.route("**/api/reports/brak-materials*", lambda r: r.fulfill(**jsn(403, {"detail": "Ruxsat yo'q"})))
        baj(pg, "() => loadBrakSummary()", 900)
        _c = matn(pg, "#brakSummaryContent") or ""
        check("C3 (C#14) brak hisoboti 403 — «Brak hisoboti yuklanmadi — ko'rish ruxsati yo'q» (ilgari yolg'on «… topilmadi»)",
              "Brak hisoboti yuklanmadi" in _c and "ruxsati yo'q" in _c and "topilmadi" not in _c, _c[:200])
        pg.unroute("**/api/reports/brak-materials*")

        pg.route("**/api/reports/brak-tahlil?oylar=6*", lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, "() => loadBrakTahlil()", 900)
        _c = matn(pg, "#brakTahlilContent") or ""
        check("C4 (C#15) brak tahlili 502 — «Brak tahlili yuklanmadi — server javob bermadi» (ilgari «❌ Xato (502)»)",
              "Brak tahlili yuklanmadi" in _c and SERVER in _c, _c[:200])
        pg.unroute("**/api/reports/brak-tahlil?oylar=6*")
        pg.evaluate("""() => { window.__chizildi = []; const asl = brakTahlilHtml;
            brakTahlilHtml = (d) => { window.__chizildi.push((d && d.__belgi) || 'yangi'); return asl(d); }; }""")
        _u = Ushla(lambda u: "month=1&" in u or u.endswith("month=1"))
        pg.route("**/api/reports/brak-tahlil?oylar=6*", _u)
        baj(pg, "() => { document.getElementById('brak-tahlil-oy').value = '2026-01'; loadBrakTahlil(); }", 400)
        baj(pg, "() => { document.getElementById('brak-tahlil-oy').value = '2026-02'; loadBrakTahlil(); }", 1200)
        _asl = None
        if _u.ushlangan:
            try:
                _asl = _u.ushlangan[0].fetch().json()
            except Exception:              # noqa: BLE001
                _asl = None
        _u.qoyib_yubor(**jsn(200, dict(_asl or {}, __belgi="A")))
        pg.wait_for_timeout(700)
        _ch = pg.evaluate("() => window.__chizildi")
        check("C5 (C#15) oy tez almashtirilsa — eski oy (yanvar) javobi yangi oy (fevral) jadvalini bosmaydi",
              len(_u.ushlangan) == 1 and _ch == ["yangi"], (len(_u.ushlangan), _ch))
        pg.unroute("**/api/reports/brak-tahlil?oylar=6*")

        # kech155 (zip 210 «Naqd / Bank / Karta», MOSLANDI): manzilda `?payment_method=…` (tasdiq oynasida tanlangan hisob) — naqsh oxirida «*»
        pg.route(f"**/api/returns/{ID['RQ']}/refund*", lambda r: r.abort())
        baj(pg, f"() => toggleRefund({ID['RQ']}, false)", 900)
        _m = msg_matn(pg)
        check("C6 (C#17) «Hisob-kitob qilish» — internet uzilsa «⚠️ Hisob-kitob natijasi noma'lum: internet aloqasi yo'q» (ilgari "
              "hech narsa)", "Hisob-kitob natijasi noma'lum" in _m and UZILISH in _m, _m)
        pg.unroute(f"**/api/returns/{ID['RQ']}/refund*")
        msg_tozala(pg)
        pg.route(f"**/api/returns/{ID['RQ']}/refund*", lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, f"() => toggleRefund({ID['RQ']}, false)", 900)
        _m = msg_matn(pg)
        check("C7 (C#17) «Hisob-kitob qilish» 502 — natija noma'lum, qayta bosish ikki marta hisoblamaydi (ilgari «❌ Xato»)",
              "Hisob-kitob natijasi noma'lum" in _m and SERVER in _m, _m)
        pg.unroute(f"**/api/returns/{ID['RQ']}/refund*")
        msg_tozala(pg)

        pg.route(f"**/api/returns/{ID['RQ']}", lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, f"() => deleteReturn({ID['RQ']})", 900)
        _m = msg_matn(pg)
        check("C8 qaytarishni o'chirish 502 — «⚠️ O'chirish natijasi noma'lum: server javob bermadi» (ilgari «❌ Xato»)",
              "O'chirish natijasi noma'lum" in _m and SERVER in _m and qaytarish_bor(ID["RQ"]), _m)
        pg.unroute(f"**/api/returns/{ID['RQ']}")
        msg_tozala(pg)
        pg.route(f"**/api/returns/{ID['RQ']}", lambda r: r.fulfill(**jsn(404, {"detail": "Qaytarish topilmadi"})))
        baj(pg, f"() => deleteReturn({ID['RQ']})", 900)
        _m = msg_matn(pg)
        check("C9 qaytarishni o'chirish rad etildi — «❌ <server sababi>»", _m == "❌ Qaytarish topilmadi", _m)
        pg.unroute(f"**/api/returns/{ID['RQ']}")
        msg_tozala(pg)

        pg.route(f"**/api/returns/{ID['RQ']}/image", lambda r: r.abort())
        baj(pg, f"""() => uploadReturnImage({ID['RQ']}, {{files: [new File([new Uint8Array([137, 80, 78, 71])], 'a.png',
                                                       {{type: 'image/png'}})], value: 'a.png'}})""", 900)
        _m = msg_matn(pg)
        check("C10 qaytarish rasmi — internet uzilsa «❌ Rasm yuklanmadi: internet aloqasi yo'q …» (ilgari «Server xatosi»)",
              "❌ Rasm yuklanmadi: " in _m and UZILISH in _m, _m)
        pg.unroute(f"**/api/returns/{ID['RQ']}/image")
        msg_tozala(pg)

        pg.route(f"**/api/returns/{ID['RB']}/taqdir", lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, f"""() => {{ const b = [...document.querySelectorAll('.brak-taqdir-btn')].find(x => x.dataset.id === '{ID['RB']}');
              taqdirOynaOch(b); taqdirSaqla(); }}""", 1000)
        _e = matn(pg, "#taqdir-error") or ""
        check("C11 brak taqdiri 502 — «⚠️ Taqdir natijasi noma'lum: server javob bermadi» (ilgari «❌ Taqdir saqlanmadi» — sababsiz)",
              "Taqdir natijasi noma'lum" in _e and SERVER in _e, _e)
        pg.unroute(f"**/api/returns/{ID['RB']}/taqdir")
    except Exception as _x:               # noqa: BLE001
        check("C bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("D. «Qarzdorlar» — to'lovlar tarixi, to'lov va «Qaytarildi» (C#16, D)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/debts")
        pg.route("**/api/obligations/timeline*", lambda r: r.fulfill(**jsn(500, {"detail": "Internal Server Error"})))
        baj(pg, "() => { openObligTimeline('t177_a', 'T177 ijara A', '', '', ''); }", 900)
        _t = matn(pg, "#tl-list") or ""
        check("D1 (C#16) to'lovlar tarixi 500 — «To'lovlar tarixi yuklanmadi — server javob bermadi» (ilgari yolg'on «Bu oyda to'lov yo'q»)",
              "To'lovlar tarixi yuklanmadi" in _t and SERVER in _t and "to'lov yo'q" not in _t, _t[:200])
        pg.unroute("**/api/obligations/timeline*")
        _u = Ushla(lambda u: "category=t177_a" in u)
        pg.route("**/api/obligations/timeline*", _u)
        baj(pg, "() => { openObligTimeline('t177_a', 'T177 ijara A', '', '', ''); }", 400)
        baj(pg, "() => { openObligTimeline('t177_b', 'T177 ijara B', '', '', ''); }", 1200)
        _u.qoyib_yubor(**jsn(200, [{"date": "2026-10-01T10:00:00", "amount": 123, "notes": "A-BELGI777", "created_by": ""}]))
        pg.wait_for_timeout(700)
        _t, _tt = matn(pg, "#tl-list") or "", matn(pg, "#tl-title") or ""
        check("D2 (C#16) A yopilib B ochilsa — A ning kech kelgan qatorlari B ro'yxatiga tushmaydi",
              len(_u.ushlangan) == 1 and "ijara B" in _tt and "A-BELGI777" not in _t, (_tt, _t[:200]))
        pg.unroute("**/api/obligations/timeline*")
        baj(pg, "() => { closeTimelineModal(); }", 200)

        pg.route("**/api/payments*", lambda r: r.fulfill(**jsn(422, {"detail": [{"loc": ["body", "amount"], "msg": "Summa noto'g'ri",
                                                                                  "type": "value_error"}]}))
                 if r.request.method == "POST" else r.continue_())
        baj(pg, """() => { const el = document.querySelector('.dbt-item[onclick^="selectOrderDebt"]'); selectOrderDebt(el);
              document.getElementById('pay-amount').value = '1000'; savePayment(); }""", 1000)
        _pm = matn(pg, "#pay-msg") or ""
        check("D3 to'lov 422 — maydon sababi «❌ amount: Summa noto'g'ri» (ilgari «❌ Xato yuz berdi»)",
              "amount: Summa noto'g'ri" in _pm, _pm)
        pg.unroute("**/api/payments*")

        pg.route(f"**/api/orders/{ID['OO']}/refund-overpayment", lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, f"""() => {{ switchTab('refunds'); const el = document.querySelector('#tab-refunds .dbt-item[data-id="{ID['OO']}"]');
              selectRefund(el); document.getElementById('ref-amount').value = '1000'; saveRefund(); }}""", 1000)
        _rm = matn(pg, "#ref-msg") or ""
        check("D4 «Qaytarildi» 502 — «⚠️ Natija noma'lum: server javob bermadi …» (ilgari «❌ Xato yuz berdi»)",
              "Natija noma'lum" in _rm and SERVER in _rm, _rm)
        pg.unroute(f"**/api/orders/{ID['OO']}/refund-overpayment")
        n0 = len(sorovlar(f"/api/orders/{ID['OO']}/refund-overpayment"))
        baj(pg, "() => { document.getElementById('ref-amount').value = '1000'; saveRefund(); }", 500)
        baj(pg, "() => { saveRefund(); }", 600)
        _q = sorovlar(f"/api/orders/{ID['OO']}/refund-overpayment")[n0:]
        check("D5 «Qaytarildi» muvaffaqiyatdan keyin (sahifa yangilanguncha) qayta bosish — ikkinchi so'rov YO'Q",
              len(_q) == 1, _q)
        try:
            pg.wait_for_load_state("networkidle")
        except Exception:                  # noqa: BLE001
            pass
    except Exception as _x:               # noqa: BLE001
        check("D bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("E. Ruxsatsiz tugmalar ko'rinmaydi (C#20) — har tugma o'z marshruti ruxsati bilan")
    # B4 / B5 (502 — server bajargan) «Jarayon» ni tayyor, «Tayyor» bandini 0 qilgan — E1 uchun holat qaytariladi

    def _e_holat(d):
        d.query(FinishedProduct).filter(FinishedProduct.id == ID["J"]).update(
            {FinishedProduct.production_status: ProductionStatus.IN_PROGRESS}, synchronize_session=False)
        d.query(FinishedProduct).filter(FinishedProduct.id == ID["R"]).update(
            {FinishedProduct.reserved_quantity: 3.0}, synchronize_session=False)
    db_ishi(_e_holat)
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    FP_SEL = {
        "«Penoplast detal»": '[onclick^="openProduceModal"]',
        "«Sotish»": ".fp-amal-sotish",
        "savatcha belgisi": ".fp-batch-check",
        "guruh 💵": '[onclick^="fpGuruhSotish"]',
        "«Brak»": '[onclick^="openLossModal"]',
        "«Yana ishlab chiqarish»": '[onclick^="yanaIshlabChiqarish"]',
        "✏️ / narx": '[onclick^="editPrice"]',
        "«Sotuvga tayyor»": '[onclick^="markReady"]',
        "«Bandni bekor qilish»": '[onclick^="releaseFpReservation"]',
        "✕ / «O'chirish»": '[onclick^="delFp"]',
        "rasm": '.fp-thumb .cam-overlay, input[id^="fpimg-"]',
    }

    def fp_sanoq(pg):
        return {k: soni(pg, v) for k, v in FP_SEL.items()}

    ctx, pg = kontekst()
    try:
        ochiq(pg, "/finished", ilgak=False)
        _a = fp_sanoq(pg)
        check("E1 Admin — hamma tugmalar bor (ijobiy nazorat)", all((n or 0) > 0 for n in _a.values()), _a)
    except Exception as _x:               # noqa: BLE001
        check("E1 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    ctx, pg = kontekst("t177_kor")
    try:
        ochiq(pg, "/finished", ilgak=False)
        _k = fp_sanoq(pg)
        _mal = soni(pg, '[onclick^="openHistoryModal"]')
        check("E2 «Faqat ko'rish» roli — tayyor mahsulotlarda amal tugmasi YO'Q (ilgari hammasi ko'rinardi — bosilsa 403), «Ma'lumot» bor",
              all(n == 0 for n in _k.values()) and (_mal or 0) > 0 and "T177 Tayyor profil" in (matn(pg, "#fpList") or ""), (_k, _mal))
        ochiq(pg, "/returns", ilgak=False)
        _r = {"🗑": soni(pg, '[onclick^="deleteReturn"]'), "rasm": soni(pg, '.ret-icon .cam-overlay, input[id^="retimg-"]'),
              "yangi qaytarish rasmi": soni(pg, "#f-rasm")}
        check("E3 «Faqat ko'rish» — qaytarishlarda 🗑 va rasm qo'yish YO'Q (ro'yxat bor)",
              all(n == 0 for n in _r.values()) and soni(pg, ".ret-row") >= 2, (_r, soni(pg, ".ret-row")))
        ochiq(pg, "/debts", ilgak=False)
        _d = {"+ Yangi kategoriya": soni(pg, '[onclick^="openAddCategoryModal"]'), "kategoriya ✕": soni(pg, '[onclick^="deleteCategory"]'),
              "💰 To'lov qo'shish": soni(pg, '[onclick*="quickPayObligation"]'), "To'lovni qabul qilish": soni(pg, '[onclick^="savePayment"]'),
              "Qaytarildi": soni(pg, '[onclick^="saveRefund"]')}
        baj(pg, """() => { const el = document.querySelector('.dbt-item[onclick^="selectOrderDebt"]'); if (el) selectOrderDebt(el);
              switchTab('refunds'); const r = document.querySelector('#tab-refunds .dbt-item'); if (r) selectRefund(r); }""", 500)
        _kar = pg.evaluate("() => [document.getElementById('payCard').style.display, document.getElementById('refundCard').style.display]")
        check("E4 «Faqat ko'rish» — qarzdorlarda to'lov / qaytarish kartalari ochilmaydi, kategoriya va majburiyat tugmalari YO'Q",
              all(n == 0 for n in _d.values()) and _kar == ["none", "none"], (_d, _kar))
    except Exception as _x:               # noqa: BLE001
        check("E2–E4 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    ctx, pg = kontekst("t177_sot")
    try:
        ochiq(pg, "/finished", ilgak=False)
        _s = fp_sanoq(pg)
        _bor = {k: _s[k] for k in ("«Sotish»", "savatcha belgisi", "guruh 💵")}
        _yoq = {k: v for k, v in _s.items() if k not in _bor}
        check("E5 «Sotuvchi» (sotuv: yaratish) — «Sotish», savatcha va guruh 💵 BOR; brak, narx, o'chirish, ishlab chiqarish YO'Q",
              all((n or 0) > 0 for n in _bor.values()) and all(n == 0 for n in _yoq.values()), _s)
    except Exception as _x:               # noqa: BLE001
        check("E5 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    ctx, pg = kontekst()
    try:
        ochiq(pg, "/returns", ilgak=False)
        _r = {"🗑": soni(pg, '[onclick^="deleteReturn"]'), "rasm": soni(pg, 'input[id^="retimg-"]'), "yangi qaytarish rasmi": soni(pg, "#f-rasm")}
        ochiq(pg, "/debts", ilgak=False)
        _d = {"+ Yangi kategoriya": soni(pg, '[onclick^="openAddCategoryModal"]'), "kategoriya ✕": soni(pg, '[onclick^="deleteCategory"]'),
              "💰 To'lov qo'shish": soni(pg, '[onclick*="quickPayObligation"]'), "To'lovni qabul qilish": soni(pg, '[onclick^="savePayment"]'),
              "Qaytarildi": soni(pg, '[onclick^="saveRefund"]')}
        baj(pg, """() => { const el = document.querySelector('.dbt-item[onclick^="selectOrderDebt"]'); if (el) selectOrderDebt(el); }""", 300)
        _kar = pg.evaluate("() => document.getElementById('payCard').style.display")
        check("E6 Admin — qaytarish 🗑 / rasm, qarzdorlar tugmalari va to'lov kartasi BOR (ijobiy nazorat)",
              all((n or 0) > 0 for n in list(_r.values()) + list(_d.values())) and _kar == "block", (_r, _d, _kar))
    except Exception as _x:               # noqa: BLE001
        check("E6 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    section("Z. Sahifa xatolari")
    check("Z1 sahifalarda ushlanmagan JS xatosi yo'q", not JS_XATO, JS_XATO[:5])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Shablon — ruxsat shartlari server marshrutlari bilan bir xil (C#20)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_db = open(os.path.join(ROOT, "templates", "debts.html"), encoding="utf-8").read()
_i = _db.find("closeEmployeeDebt(this.closest")
check("S1 debts.html «✓ To'liq to'landi deb belgilash» — «Qarzlar: Tahrirlash» sharti ostida (`…/employee/{id}/close` marshruti)",
      _i > 0 and _db.rfind("{% if current_user.ruxsat('qarz', 'tahrirlash') %}", 0, _i) > _db.rfind("{% endif %}", 0, _i), _i)

_r1 = C.get("/api/reports/brak-materials", params={"start_date": "2026-13-40", "end_date": "2026-10-13"})
_r2 = C.get("/api/reports/brak-materials", params={"start_date": "2026-10-01", "end_date": "abc"})
_r3 = C.get("/api/reports/brak-materials", params={"start_date": "2026-10-01", "end_date": "2026-10-13"})
check("S2 brak hisoboti — noto'g'ri sana 400 va sabab (ilgari 500 — «server javob bermadi»), to'g'ri sana 200",
      _r1.status_code == 400 and "Boshlanish sanasi noto'g'ri" in str(js(_r1).get("detail")) and _r2.status_code == 400
      and "Tugash sanasi noto'g'ri" in str(js(_r2).get("detail")) and _r3.status_code == 200,
      (_r1.status_code, _r1.text[:150], _r2.status_code, _r3.status_code))

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
