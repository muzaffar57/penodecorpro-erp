#!/usr/bin/env python3
"""
test_e_tanlov.py — kech120, E BOSQICH 4-qism (TANLAGICHLAR): qidiruvli tanlagich (`static/tanlov.js`) — Kirim formasi
(ta'minotchi, material), «Yangi qaytarish» (buyurtma), «Brak yozish» (loyiha, tayyor mahsulot); ta'minotchilar tabiiy tartibda;
Tayyor mahsulotlar kategoriya tugmalari korxonaning o'z mahsulot turlaridan.

NIMA UCHUN KERAK (audit kech114, «Katta Korxona»; kodda, rasmda va o'lchovda ko'rilgan):
  G4-20  Kirim formasida 104 material bitta oddiy ochiladigan ro'yxatda, qidiruvsiz; ta'minotchi maydoni ~145 px (uzun nomlar
         kesiladi), 30 ta ta'minotchida ham qidiruv yo'q; birinchi material OLDINDAN tanlangan («— Tanlang —» yo'q) — e'tiborsiz
         omborchi noto'g'ri materialga kirim qilishi mumkin; ta'minotchilar matn tartibida (1, 10, 11 … 2, 20).
  G5-19  «Yangi qaytarish» ga korxonaning HAMMA buyurtmalari, «Brak yozish» ga hamma loyihalar sahifa bilan birga chiziladi —
         qidiruvsiz; qaytarish 0 ta bo'lsa ham sahifa elementlari ikki barobar ko'p.
  G5-10  Tayyor mahsulotlarda «Profil / Panel / Donali» tugmalari faqat eski penoplast mahsulotini ajratadi — retsept bo'yicha
         ishlab chiqarilgan hamma mahsulot tugma bosilsa yo'qoladi; bo'lim sarlavhasi doim «PENOPLAST VA BOSHQA».
BO'LIMLAR: S — statik; A — API va sahifa HTML (tanlov ro'yxatlari — korxona, holat, tartib, ruxsat; tabiiy tartib; mahsulot turi
  nomi; Qaytarishlar sahifasida buyurtma ro'yxati yo'q); J — tanlagichning O'ZI (brauzerda, sinov `<select>` larida: tugma matni,
  qidiruv — matn / `data-qidiruv` / raqamlar / guruh, yashirin va o'chirilgan qatorlar, 300 dan ko'p, klaviatura, `change` bir marta,
  kod yozgan qiymat, ro'yxat almashsa, `disabled`, yashirish, tashqariga bosish); K — Kirim sahifasi; Q — Qaytarishlar («Yangi
  qaytarish», Esc — avval panel, keyin oyna, so'roqsiz; «Brak yozish»); M — Tayyor mahsulotlar kategoriyalari; T — telefon 390 px;
  X — JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 129) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium (J / K / Q / M / T bo'limlari).
ISHLATISH: python3 tools/test_e_tanlov.py
"""
import os
import re
import sys
import io
import glob
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "e_tanlov_test"
_T = tempfile.mkdtemp(prefix="etanlov_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'e_tanlov_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, Rol, Inventory, Supplier, Project, Order, OrderStatus, OrderType,  # noqa: E402
                    OrderItem, FinishedProduct, StockSource)
from production_models import Company, ProductType  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

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


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TJS = oqi("static/tanlov.js")
CSS = oqi("static/style.css")
BASE = oqi("templates/base.html")
RCV = oqi("templates/supplier_receive.html")
RET = oqi("templates/returns.html")
BRK = oqi("templates/_brak_oyna.html")
FIN = oqi("templates/finished.html")
MAIN = oqi("main.py")
check("S1 `static/tanlov.js` — `qidiruvliTanlov`, asl `<select>` qiymati / `change` hodisasi, kuzatuvchi, Esc ichki paneli",
      "window.qidiruvliTanlov = qidiruvliTanlov;" in TJS and "sel.dispatchEvent(new Event('change', {bubbles: true}))" in TJS
      and "new MutationObserver(yangila)" in TJS and "data-yopish-ichki" in TJS and "data-kiritish-emas" in TJS
      and "Object.defineProperty(HTMLSelectElement.prototype, 'value'" in TJS and "if (this._qt) this._qt.yangila();" in TJS)
check("S2 base.html — `tanlov.js` ulanadi (defer), qidiruv maydoni oynaga «ma'lumot yozildi» belgisini qo'ymaydi; style.css — .qt",
      '<script src="/static/tanlov.js?v={{ static_version }}" defer></script>' in BASE
      and "if (el.hasAttribute('data-kiritish-emas')) return;" in BASE and ".qt .qt-maydon" in CSS and "select.qt-asl" in CSS)
check("S3 qidiruvli: Kirim (ta'minotchi, material), «Yangi qaytarish» (buyurtma), «Brak yozish» (loyiha, tayyor mahsulot)",
      all(x in RCV for x in ('<select id="r-supplier" onchange="onSupplierChange()" data-qidiruvli',
                             '<select id="ap-item" onchange="apOnItemChange()" data-qidiruvli'))
      and '<select id="f-order" onchange="onOrderChange()" data-qidiruvli' in RET
      and '<select id="brak-project" onchange="onBrakProjectChange()" data-qidiruvli' in BRK
      and '<select id="brak-fp" onchange="brakFpTanla()" data-qidiruvli' in BRK)
check("S4 Kirim: birinchi qator «— Material tanlang —» (oldindan tanlanmaydi); Qaytarishlar sahifasiga buyurtma ro'yxati YOZILMAYDI",
      "sel.innerHTML = '<option value=\"\">— Material tanlang —</option>' + sortedCats" in RCV
      and "{% for o in orders %}" not in RET and "{% for p in (projects or []) %}" not in BRK
      and '@app.get("/api/tanlov/buyurtmalar")' in MAIN and '@app.get("/api/tanlov/loyihalar")' in MAIN)
check("S5 Tayyor mahsulotlar: kategoriya — `fpKalit` (mahsulot turi / penoplast turkumi), sarlavha «OMBORDA», API `product_type_name`",
      "function fpKalit(i)" in FIN and "if (category && fpKalit(i) !== category) return false;" in FIN
      and "PENOPLAST VA BOSHQA" not in FIN and "🏭 OMBORDA" in FIN and '"product_type_name": _tur_nomlari.get(' in MAIN)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Fikstura")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "etn_admin", "Parol123!"
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="ETN B korxona"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, ADMIN, PAROL, UserRole.ADMIN, "Tanlov Admin", company_id=1)
    auth.create_user(_db, "etn_b", PAROL, UserRole.ADMIN, "Begona Admin", company_id=2)
    auth.create_user(_db, "etn_hisob", PAROL, UserRole.ACCOUNTANT, "Hisobchi", company_id=1)
    auth.create_user(_db, "etn_korar", PAROL, UserRole.MANAGER, "Faqat ko'ruvchi", company_id=1)
# «Qaytarishlar: Ko'rish» bor, «Yaratish» YO'Q — o'zi yaratilgan rol (tanlov ro'yxatlari ruxsati — yaratish)
_rol = Rol(company_id=1, nom="ETN faqat ko'rish", ruxsatlar='{"qaytarish": ["korish"]}')
_db.add(_rol)
_db.commit()
_db.query(User).filter(User.username == "etn_korar").first().rol_id = _rol.id
_db.commit()
_SUP = [f"Ta'minotchi {i}" for i in (10, 2, 1, 21, 3, 20, 11, 12)] + ["andijon Qurilish", "Andijon qurilish 9"]
for _n in _SUP:
    _db.add(Supplier(company_id=1, name=_n, phone="+998901234567"))
_db.add(Supplier(company_id=2, name="Ta'minotchi 5 BEGONA", phone="+998900000000"))
_KAT = ["Penoplast", "Kimyoviy qo'shimchalar", "Qattiq qotishmalar", "Gips", "Boshqa"]
for _i in range(1, 41):
    _db.add(Inventory(company_id=1, item_name=("ETN Penoplast 15 (asosiy blok)" if _i == 1 else f"ETN Material {_i}"), unit="kg",
                      stock_quantity=100, price_per_unit=1000, category=_KAT[_i % 5], is_penoplast=(_i == 1),
                      is_default_penoplast=(_i == 1), volume_per_unit=1.0))
_db.commit()
_PT = [ProductType(company_id=1, name=n, unit="dona", input_template="quantity_only", pricing_formula="unit_based")
       for n in ("Ustun", "Kafel kley", "Travertin 10")]
_PT_B = ProductType(company_id=2, name="BEGONA TUR", unit="dona", input_template="quantity_only", pricing_formula="unit_based")
_db.add_all(_PT + [_PT_B])
_db.commit()
for _k, _pt in enumerate(_PT):
    _db.add(FinishedProduct(company_id=1, name=f"{_pt.name} mahsulot", category="dynamic_bom", product_type_id=_pt.id, quantity=5 + _k,
                            unit="dona", unit_price=1000, source=StockSource.PRODUCED))
for _c in ("profil", "panel"):
    _db.add(FinishedProduct(company_id=1, name=f"ETN Penoplast {_c}", category=_c, quantity=3, unit="dona", unit_price=1000,
                            source=StockSource.PRODUCED))
_db.add(FinishedProduct(company_id=1, name="ETN Eski boshqa", category=None, quantity=2, unit="dona", unit_price=1000,
                        source=StockSource.PRODUCED))
# turi ham, penoplast turkumi ham bor mahsulot — BITTA kategoriyada (mahsulot turida), «Panel» da emas
_db.add(FinishedProduct(company_id=1, name="ETN Ustun panel", category="panel", product_type_id=_PT[0].id, quantity=1, unit="dona",
                        unit_price=1000, source=StockSource.PRODUCED))
_db.add(FinishedProduct(company_id=2, name="BEGONA mahsulot", category="dynamic_bom", product_type_id=None, quantity=1, unit="dona",
                        unit_price=1, source=StockSource.PRODUCED))
_db.commit()
_HOLAT = [OrderStatus.DRAFT, OrderStatus.IN_PROGRESS, OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.READY,
          OrderStatus.NEW, OrderStatus.COATING]
PRJ = {}
for _i in range(12):
    _p = Project(company_id=1, client_name=f"ETN Mijoz {_i}", project_name=f"ETN Loyiha {_i}", client_phone=f"+998 93 {_i:03d} 45 67",
                 total_budget=0, total_paid=0, is_deleted=(_i == 11))
    _db.add(_p)
    _db.commit()
    PRJ[_i] = _p.id
    for _j, _h in enumerate(_HOLAT):
        if _i >= 9 and _h not in (OrderStatus.DRAFT, OrderStatus.CANCELLED):
            continue                    # 9, 10 — faqat qoralama / bekor qilingan buyurtmali loyihalar (brak ro'yxatida YO'Q)
        _o = Order(company_id=1, project_id=_p.id, order_type=OrderType.PRODUCT, order_number=f"ETN-{_i:03d}-{_j + 1}", status=_h,
                   is_deleted=(_i == 8 and _j == 1))
        _db.add(_o)
        _db.commit()
        _db.add(OrderItem(company_id=1, order_id=_o.id, name=f"Detal {_i}-{_j}", category="panel", width=20, thickness=10, quantity=2,
                          unit_price=1000, total_price=2000, is_coated=False))
_pb = Project(company_id=2, client_name="BEGONA mijoz", project_name="BEGONA loyiha", client_phone="+998 99 999 99 99",
              total_budget=0, total_paid=0)
_db.add(_pb)
_db.commit()
_db.add(Order(company_id=2, project_id=_pb.id, order_type=OrderType.PRODUCT, order_number="BEGONA-1", status=OrderStatus.DELIVERED))
_db.commit()
_db.close()


def klient(user):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": PAROL}, follow_redirects=False)
    return c, r.status_code


C, _s1 = klient(ADMIN)
CB, _s2 = klient("etn_b")
CH, _s3 = klient("etn_hisob")
CK, _s4 = klient("etn_korar")
check("F0 foydalanuvchilar kirdi", (_s1, _s2, _s3, _s4) == (302, 302, 302, 302), (_s1, _s2, _s3, _s4))
XATO5 = []


def ol(c, url):
    try:
        r = c.get(url)
    except Exception as e:                 # noqa: BLE001
        XATO5.append((url, f"{type(e).__name__}: {e}"))
        return 599, None, ""
    if r.status_code >= 500:
        XATO5.append((url, r.status_code, r.text[:200]))
    try:
        return r.status_code, r.json(), r.text
    except Exception:                      # noqa: BLE001
        return r.status_code, None, r.text


def kutilgan_buyurtmalar(cid=1):
    s = SessionLocal()
    try:
        rows = s.query(Order).filter(Order.company_id == cid, Order.is_deleted.isnot(True),
                                     Order.status.notin_([OrderStatus.DRAFT, OrderStatus.CANCELLED])).all()
        rows.sort(key=lambda o: (o.created_at, o.id), reverse=True)
        return [o.order_number for o in rows]
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API va sahifa HTML")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
def royxat(x):
    """API javobi ro'yxat bo'lmasa (asl kodda 404 — `{"detail": …}`) — bo'sh ro'yxat (test qulamaydi, yiqiladi)."""
    return [i for i in x if isinstance(i, dict)] if isinstance(x, list) else []


st, BY, _ = ol(C, "/api/tanlov/buyurtmalar")
BY = royxat(BY)
_kb = kutilgan_buyurtmalar()
check("A1 `/api/tanlov/buyurtmalar`: faqat shu korxona, o'chirilmagan, qoralama / bekor qilinganlarsiz (yangi, jarayonda, qoplamada, "
      "tayyor, yetkazilgan), yangisi tepada",
      st == 200 and isinstance(BY, list) and [b["raqam"] for b in BY] == _kb and len(_kb) == 9 * 5 - 1
      and not any(b["raqam"].startswith("BEGONA") for b in BY), (st, len(BY or []), len(_kb)))
_b0 = next((b for b in (BY or []) if b["raqam"] == "ETN-003-3"), {})
check("A2 har qatorda mijoz, loyiha, telefon, holat (o'zbekcha)", _b0.get("mijoz") == "ETN Mijoz 3" and _b0.get("loyiha") == "ETN Loyiha 3"
      and _b0.get("telefon") == "+998 93 003 45 67" and _b0.get("holat") == "yetkazilgan"
      and {b["holat"] for b in BY} == {"yangi", "jarayonda", "qoplamada", "tayyor", "yetkazilgan"}, _b0)
st, LY, _ = ol(C, "/api/tanlov/loyihalar")
LY = royxat(LY)
check("A3 `/api/tanlov/loyihalar`: shu korxona, o'chirilmagan, ishdagi buyurtmasi bor (faqat qoralama / bekor — YO'Q), yangisi tepada",
      st == 200 and [p["loyiha"] for p in LY] == [f"ETN Loyiha {i}" for i in range(8, -1, -1)]
      and all(p["telefon"] for p in LY), (st, [p.get("loyiha") for p in (LY or [])]))
st, BYB, _ = ol(CB, "/api/tanlov/buyurtmalar")
st2, LYB, _ = ol(CB, "/api/tanlov/loyihalar")
BYB, LYB = royxat(BYB), royxat(LYB)
check("A4 B korxona — faqat o'zi", [b["raqam"] for b in (BYB or [])] == ["BEGONA-1"] and [p["loyiha"] for p in (LYB or [])] == ["BEGONA loyiha"],
      (BYB, LYB))
st, _, _ = ol(CH, "/api/tanlov/buyurtmalar")
st2, _, _ = ol(CH, "/api/tanlov/loyihalar")
st3, _, _ = ol(CK, "/api/tanlov/buyurtmalar")
st4, _, _ = ol(CK, "/api/tanlov/loyihalar")
st5, _, _ = ol(CK, "/returns")
check("A5 ruxsat — «Qaytarishlar: Yaratish» siz (Moliyachi; faqat «Ko'rish» li rol — sahifa ochiladi) — ro'yxatlar 403",
      (st, st2, st3, st4, st5) == (403, 403, 403, 403, 200), (st, st2, st3, st4, st5))
_s = SessionLocal()
try:
    _sup = [x.name for x in crud.get_suppliers(_s, company_id=1)]
finally:
    _s.close()
check("A6 ta'minotchilar TABIIY tartibda (2 < 10 < 20; katta-kichik harf farqsiz)",
      _sup == ["andijon Qurilish", "Andijon qurilish 9", "Ta'minotchi 1", "Ta'minotchi 2", "Ta'minotchi 3", "Ta'minotchi 10",
               "Ta'minotchi 11", "Ta'minotchi 12", "Ta'minotchi 20", "Ta'minotchi 21"], _sup)
st, _, H = ol(C, "/suppliers/receive")
_ops = re.findall(r'<option value="(\d+)">([^<]+)</option>', re.search(r'<select id="r-supplier".*?</select>', H, re.S).group(0)) \
    if st == 200 and '<select id="r-supplier"' in H else []
check("A7 Kirim sahifasi: ta'minotchi ro'yxati tabiiy tartibda, begona yo'q", [n for _i, n in _ops] == [n.replace("'", "&#39;") for n in _sup]
      or [n.replace("&#39;", "'") for _i, n in _ops] == _sup, _ops[:6])
st, FN, _ = ol(C, "/api/finished")
FN = royxat(FN)
_ptn = {f["name"]: f.get("product_type_name") for f in (FN or [])}
check("A8 `/api/finished`: `product_type_name` — mahsulot turi nomi (penoplast / eski — null)",
      _ptn.get("Ustun mahsulot") == "Ustun" and _ptn.get("Kafel kley mahsulot") == "Kafel kley" and _ptn.get("ETN Penoplast panel") is None
      and "product_type_name" in (FN or [{}])[0], _ptn)
st, _, H = ol(C, "/returns")
_fo = re.search(r'<select id="f-order".*?</select>', H, re.S)
_bp = re.search(r'<select id="brak-project".*?</select>', H, re.S)
check("A9 Qaytarishlar sahifasi: buyurtma va loyiha ro'yxati sahifaga yozilmagan (bitta bo'sh qator), sahifada «ETN-0» yo'q",
      st == 200 and _fo and _fo.group(0).count("<option") == 1 and _bp and _bp.group(0).count("<option") == 1 and "ETN-0" not in H,
      (st, _fo and _fo.group(0)[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
check("B0 Python `playwright` bor", PW_BOR, _pw_x)
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
check("B1 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO, AMAL_XATO = [], []


def kontekst(w=1280, h=900, tel=False):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=tel, has_touch=tel,
                         timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|cdn\.jsdelivr\.net|unpkg\.com)/.*"),
              lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(8000)          # topilmagan element (asl kod) — 30 s emas, 8 s kutiladi
    pg.on("pageerror", lambda e: JS_XATO.append((w, str(e)[:200])))
    try:
        pg.goto(B + "/login")
        pg.fill("input[name=username]", ADMIN)
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
    except Exception as ex:                # noqa: BLE001
        AMAL_XATO.append(("login", f"{type(ex).__name__}: {str(ex)[:160]}"))
    return ctx, pg


def jsq(pg, kod, arg=None):
    try:
        return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
    except Exception as ex:                # noqa: BLE001
        return {"js_xato": f"{type(ex).__name__}: {str(ex)[:300]}"}


def bor(pg, url):
    try:
        pg.goto(B + url, wait_until="networkidle")
        pg.wait_for_timeout(300)
        return True
    except Exception as ex:                # noqa: BLE001
        AMAL_XATO.append((url, f"{type(ex).__name__}: {str(ex)[:160]}"))
        return False


def amal(fn, nom):
    try:
        fn()
        return True
    except Exception as ex:                # noqa: BLE001
        AMAL_XATO.append((nom, f"{type(ex).__name__}: {str(ex)[:160]}"))
        return False


def kut(pg, kod, ms=6000):
    try:
        pg.wait_for_function(kod, timeout=ms)
        return True
    except Exception:                      # noqa: BLE001
        return False


def qt(sel_id):
    return f'.qt[data-qt-uchun="{sel_id}"]'


def och(pg, sel_id, nom):
    """Tanlagichni ochadi va qidiruv maydoni fokusda bo'lishini kutadi (keyingi yozuv — qidiruvga)."""
    amal(lambda: pg.click(qt(sel_id) + " .qt-maydon"), nom)
    kut(pg, f"""() => document.activeElement === document.querySelector('{qt(sel_id)} .qt-qidiruv input')""", 3000)


HOLAT_JS = r"""(id) => { const w = document.querySelector('.qt[data-qt-uchun="' + id + '"]'); const s = document.getElementById(id);
  if (!w || !s) return {yoq: true};
  return {matn: w.querySelector('.qt-matn').textContent, qiymat: s.value, ochiq: !w.querySelector('.qt-panel').hidden,
    bandlar: [...w.querySelectorAll('.qt-band')].map(e => e.textContent), guruhlar: [...w.querySelectorAll('.qt-guruh')].map(e => e.textContent),
    faol: w.querySelector('.qt-band.qt-faol')?.textContent || null, soni: w.querySelector('.qt-soni').hidden ? '' : w.querySelector('.qt-soni').textContent,
    yoq_xabar: !!w.querySelector('.qt-yoq'), korinadi: getComputedStyle(w).display !== 'none', tugma_ochiq_emas: w.querySelector('.qt-maydon').disabled,
    fokus: document.activeElement === w.querySelector('.qt-maydon') ? 'tugma' : (document.activeElement === w.querySelector('.qt-qidiruv input') ? 'qidiruv' : 'boshqa'),
    oqimda: w.classList.contains('qt-oqimda')}; }"""

if br:
    CTX, PG = kontekst()
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("J. Tanlagichning o'zi (sinov ro'yxatlari)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    bor(PG, "/finished")
    jsq(PG, r"""() => {
      const d = document.createElement('div'); d.id = 'sinovJoy'; d.style.cssText = 'padding:20px;max-width:420px';
      d.innerHTML = '<label for="sinov1">Sinov</label><select id="sinov1"><option value="">— Tanlang —</option>' +
        '<optgroup label="Mevalar"><option value="1" data-qidiruv="+998 90 111 22 33">Olma</option><option value="2">Nok</option>' +
        '<option value="3" disabled>Behi (tugagan)</option><option value="4" hidden>Yashirin anor</option></optgroup>' +
        '<optgroup label="Sabzavotlar"><option value="5">O\u2018rik bargi</option><option value="6">Sabzi 10</option><option value="7">sabzi 2</option></optgroup></select>' +
        '<select id="sinov2"></select><div id="tashqi" style="height:40px">tashqi</div>';
      document.querySelector('.fp-page').prepend(d);
      window._sinovOzgarish = 0;
      document.getElementById('sinov1').addEventListener('change', () => { window._sinovOzgarish++; });
      let h = ''; for (let i = 1; i <= 350; i++) h += '<option value="' + i + '">Qator ' + i + '</option>';
      document.getElementById('sinov2').innerHTML = h;
      qidiruvliTanlov(document.getElementById('sinov1')); qidiruvliTanlov(document.getElementById('sinov2'));
    }""")
    _j1 = jsq(PG, HOLAT_JS, "sinov1")
    check("J1 tugma — tanlangan qator matni («— Tanlang —»), asl `<select>` ko'rinmaydi, panel yopiq",
          isinstance(_j1, dict) and _j1.get("matn") == "— Tanlang —" and not _j1.get("ochiq")
          and jsq(PG, "() => { const r = document.getElementById('sinov1').getBoundingClientRect(); return r.width <= 1 && r.height <= 1; }") is True, _j1)
    och(PG, "sinov1", "J ochish")
    _j2 = jsq(PG, HOLAT_JS, "sinov1")
    check("J2 ochildi: guruh sarlavhalari, yashirin qator YO'Q, o'chirilgan qator bor (tanlab bo'lmaydi), fokus — qidiruvda",
          isinstance(_j2, dict) and _j2.get("ochiq") and _j2.get("guruhlar") == ["Mevalar", "Sabzavotlar"]
          and "Yashirin anor" not in _j2.get("bandlar", []) and "Behi (tugagan)" in _j2.get("bandlar", []) and _j2.get("fokus") == "qidiruv", _j2)
    amal(lambda: PG.keyboard.type("SABZI"), "J yozish")
    _j3 = jsq(PG, HOLAT_JS, "sinov1")
    check("J3 qidiruv — katta-kichik harf farqsiz («SABZI» → «Sabzi 10», «sabzi 2»), birinchisi belgilangan, «2 ta topildi»",
          isinstance(_j3, dict) and _j3.get("bandlar") == ["Sabzi 10", "sabzi 2"] and _j3.get("faol") == "Sabzi 10" and _j3.get("soni") == "2 ta topildi", _j3)
    amal(lambda: PG.fill(qt("sinov1") + " .qt-qidiruv input", "11122"), "J raqam")      # bo'shliqsiz — faqat raqamlar bo'yicha topiladi
    _j4a = jsq(PG, HOLAT_JS, "sinov1")
    amal(lambda: PG.fill(qt("sinov1") + " .qt-qidiruv input", "o'rik"), "J tutuq")
    _j4b = jsq(PG, HOLAT_JS, "sinov1")
    amal(lambda: PG.fill(qt("sinov1") + " .qt-qidiruv input", "sabzavot"), "J guruh")
    _j4c = jsq(PG, HOLAT_JS, "sinov1")
    amal(lambda: PG.fill(qt("sinov1") + " .qt-qidiruv input", "yo'q narsa"), "J yo'q")
    _j4d = jsq(PG, HOLAT_JS, "sinov1")
    check("J4 qidiruv `data-qidiruv` raqamlari bo'yicha («11122» → Olma, «+998 90 111 22 33» da bo'shliq bilan), tutuq belgisi farqsiz («o'rik» → «O\u2018rik bargi»), guruh nomi "
          "bo'yicha, topilmasa — «Topilmadi»",
          (_j4a or {}).get("bandlar") == ["Olma"] and (_j4b or {}).get("bandlar") == ["O\u2018rik bargi"]
          and (_j4c or {}).get("bandlar") == ["O\u2018rik bargi", "Sabzi 10", "sabzi 2"] and (_j4d or {}).get("yoq_xabar"), [_j4a, _j4b, _j4c, _j4d])
    amal(lambda: PG.fill(qt("sinov1") + " .qt-qidiruv input", "mevalar"), "J guruh2")
    _j5a = jsq(PG, HOLAT_JS, "sinov1")
    amal(lambda: PG.keyboard.press("ArrowDown"), "J pastga")
    _j5b = jsq(PG, HOLAT_JS, "sinov1")
    amal(lambda: PG.keyboard.press("ArrowDown"), "J pastga2")
    _j5c = jsq(PG, HOLAT_JS, "sinov1")
    amal(lambda: PG.keyboard.press("ArrowUp"), "J tepaga")
    amal(lambda: PG.keyboard.press("ArrowDown"), "J pastga3")
    amal(lambda: PG.keyboard.press("Enter"), "J enter")
    _j5 = jsq(PG, HOLAT_JS, "sinov1")
    check("J5 «mevalar» — Olma, Nok, Behi (o'chirilgan; yashirin anor yo'q); ↓ — Nok, yana ↓ — o'chirilgan qatorga O'TMAYDI, Enter — "
          "tanlandi: `select.value`, tugma matni, `change` BIR marta, panel yopildi, fokus tugmada",
          (_j5a or {}).get("bandlar") == ["Olma", "Nok", "Behi (tugagan)"] and (_j5a or {}).get("faol") == "Olma"
          and (_j5b or {}).get("faol") == "Nok" and (_j5c or {}).get("faol") == "Nok"
          and isinstance(_j5, dict) and _j5.get("qiymat") == "2" and _j5.get("matn") == "Nok" and not _j5.get("ochiq") and _j5.get("fokus") == "tugma"
          and jsq(PG, "() => window._sinovOzgarish") == 1, [_j5a, _j5b, _j5c, _j5])
    och(PG, "sinov1", "J ochish2")
    # o'chirilgan qator `aria-disabled` — Playwright uni bosmaydi; foydalanuvchi bosishi — DOM `click()` bilan
    jsq(PG, """() => [...document.querySelectorAll('.qt[data-qt-uchun="sinov1"] .qt-band')].find(e => e.textContent.startsWith('Behi')).click()""")
    _j6a = jsq(PG, HOLAT_JS, "sinov1")
    jsq(PG, """() => [...document.querySelectorAll('.qt[data-qt-uchun="sinov1"] .qt-band')].find(e => e.textContent === 'Nok').click()""")
    _j6 = jsq(PG, "() => window._sinovOzgarish")
    check("J6 o'chirilgan qator bosilsa — tanlanmaydi (panel ochiq qoladi); o'sha qiymat qayta tanlansa — `change` YUBORILMAYDI",
          isinstance(_j6a, dict) and _j6a.get("ochiq") and _j6a.get("qiymat") == "2" and _j6 == 1, [_j6a, _j6])
    jsq(PG, "() => { document.getElementById('sinov1').value = '2'; }")
    _j7a = jsq(PG, HOLAT_JS, "sinov1")
    jsq(PG, "() => { document.getElementById('sinov1').selectedIndex = 0; }")
    _j7b = jsq(PG, HOLAT_JS, "sinov1")
    jsq(PG, "() => { document.getElementById('sinov1').innerHTML = '<option value=\"9\">Yangi ro\\'yxat</option>'; }")
    PG.wait_for_timeout(100)
    _j7c = jsq(PG, HOLAT_JS, "sinov1")
    check("J7 kod qiymatni yozsa (`value`, `selectedIndex`) yoki ro'yxatni almashtirsa (`innerHTML`) — tugma matni darhol yangi",
          (_j7a or {}).get("matn") == "Nok" and (_j7b or {}).get("matn") == "— Tanlang —" and (_j7c or {}).get("matn") == "Yangi ro'yxat",
          [_j7a, _j7b, _j7c])
    jsq(PG, "() => { const s = document.getElementById('sinov1'); s.disabled = true; }")
    PG.wait_for_timeout(100)
    _j8a = jsq(PG, HOLAT_JS, "sinov1")
    jsq(PG, "() => { const s = document.getElementById('sinov1'); s.disabled = false; s.style.display = 'none'; }")
    PG.wait_for_timeout(100)
    _j8b = jsq(PG, HOLAT_JS, "sinov1")
    jsq(PG, "() => { document.getElementById('sinov1').style.display = 'block'; }")
    PG.wait_for_timeout(100)
    _j8c = jsq(PG, HOLAT_JS, "sinov1")
    check("J8 `disabled` — tugma ham o'chiq; sahifa `<select>` ni yashirsa (`display: none`) — tanlagich ham yashirinadi, qaytsa — qaytadi",
          (_j8a or {}).get("tugma_ochiq_emas") and (_j8b or {}).get("korinadi") is False and (_j8c or {}).get("korinadi") is True, [_j8a, _j8b, _j8c])
    och(PG, "sinov2", "J ochish3")
    _j9 = jsq(PG, HOLAT_JS, "sinov2")
    jsq(PG, "() => document.getElementById('tashqi').click()")     # panel ustini yopib turadi — tashqi joyga DOM bosish
    _j9b = jsq(PG, HOLAT_JS, "sinov2")
    check("J9 350 qatorli ro'yxat — 300 tasi chiziladi, «Yana 50 ta — qidiruvni aniqlashtiring»; tashqariga bosilsa — yopiladi",
          isinstance(_j9, dict) and len(_j9.get("bandlar", [])) == 300 and _j9.get("soni") == "Yana 50 ta — qidiruvni aniqlashtiring"
          and (_j9b or {}).get("ochiq") is False, [{k: v for k, v in (_j9 or {}).items() if k != "bandlar"}, _j9b])
    och(PG, "sinov2", "J ochish4")
    amal(lambda: PG.keyboard.press("Escape"), "J esc")
    _j10 = jsq(PG, HOLAT_JS, "sinov2")
    amal(lambda: PG.click('label[for="sinov1"]'), "J yorliq")
    _j10b = jsq(PG, HOLAT_JS, "sinov1")
    check("J10 Esc (oynasiz sahifa) — panel yopiladi, fokus tugmaga; `<label for>` bosilsa — tugmaga fokus",
          (_j10 or {}).get("ochiq") is False and (_j10 or {}).get("fokus") == "tugma" and (_j10b or {}).get("fokus") == "tugma", [_j10, _j10b])
    jsq(PG, "() => document.getElementById('sinovJoy').remove()")

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("K. Kirim sahifasi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    bor(PG, "/suppliers/receive")
    kut(PG, "() => document.getElementById('ap-item').options.length > 2")
    _k1 = jsq(PG, HOLAT_JS, "ap-item")
    _k1s = jsq(PG, HOLAT_JS, "r-supplier")
    check("K1 material — «— Material tanlang —» (oldindan TANLANMAGAN), ta'minotchi — «— Tanlang —»; ikkalasi qidiruvli",
          isinstance(_k1, dict) and _k1.get("qiymat") == "" and _k1.get("matn") == "— Material tanlang —"
          and isinstance(_k1s, dict) and _k1s.get("qiymat") == "" and _k1s.get("matn") == "— Tanlang —", [_k1, _k1s])
    och(PG, "r-supplier", "K ochish")
    amal(lambda: PG.keyboard.type("1"), "K yozish")
    _k2 = jsq(PG, HOLAT_JS, "r-supplier")
    amal(lambda: PG.keyboard.press("Enter"), "K enter")
    kut(PG, "() => typeof currentSupplierId !== 'undefined' && currentSupplierId")
    _k2b = jsq(PG, "() => ({id: currentSupplierId, qiymat: document.getElementById('r-supplier').value})")
    _sid = {n: i for i, n in [(i, n.replace("&#39;", "'")) for i, n in _ops]}
    check("K2 ta'minotchi: «1» → tabiiy tartibda (1, 10, 11, 12, 21), Enter — tanlandi va sahifa mantig'i ishladi (`onSupplierChange`)",
          isinstance(_k2, dict) and _k2.get("bandlar") == ["Ta'minotchi 1", "Ta'minotchi 10", "Ta'minotchi 11", "Ta'minotchi 12", "Ta'minotchi 21"]
          and isinstance(_k2b, dict) and str(_k2b.get("id")) == _sid.get("Ta'minotchi 1") == _k2b.get("qiymat"), [_k2, _k2b])
    _sh = jsq(PG, """() => { const a = document.querySelector('.qt[data-qt-uchun="r-supplier"]').getBoundingClientRect();
        const b = document.querySelector('.qt[data-qt-uchun="ap-item"]').getBoundingClientRect(); return [Math.round(a.width), Math.round(b.width)]; }""")
    check("K3 kenglik (1280 px): ta'minotchi maydoni ≥ 380 px (ilgari ~145), material ≥ 300 px", isinstance(_sh, list) and _sh[0] >= 380 and _sh[1] >= 300, _sh)
    och(PG, "ap-item", "K material")
    amal(lambda: PG.keyboard.type("material 3"), "K yozish2")
    _k4 = jsq(PG, HOLAT_JS, "ap-item")
    amal(lambda: PG.keyboard.type(" ("), "K yozish3")
    _k4a = jsq(PG, HOLAT_JS, "ap-item")
    amal(lambda: PG.keyboard.press("Enter"), "K enter2")
    _k4b = jsq(PG, HOLAT_JS, "ap-item")
    check("K4 material: «material 3» → 11 ta (3, 30–39) kategoriya guruhlarida; «material 3 (» → faqat «ETN Material 3 (kg)», Enter — tanlandi",
          isinstance(_k4, dict) and len(_k4.get("bandlar", [])) == 11 and _k4.get("soni") == "11 ta topildi" and len(_k4.get("guruhlar", [])) == 5
          and (_k4a or {}).get("bandlar") == ["ETN Material 3 (kg)"]
          and (_k4b or {}).get("matn") == "ETN Material 3 (kg)" and (_k4b or {}).get("qiymat") not in ("", None), [_k4, _k4a, _k4b])
    amal(lambda: PG.fill("#ap-qty", "2"), "K miqdor")
    amal(lambda: PG.fill("#ap-price", "1500"), "K narx")
    jsq(PG, "() => apAddToBasket()")
    kut(PG, "() => apBasket.length === 1")
    PG.wait_for_timeout(200)
    _k5 = jsq(PG, HOLAT_JS, "ap-item")
    _k5b = jsq(PG, "() => apBasket.map(b => b.itemName)")
    check("K5 «ro'yxatga qo'shish» — savatda AYNAN tanlangan material; maydon tozalandi → tugma «— Material tanlang —»",
          _k5b == ["ETN Material 3"] and isinstance(_k5, dict) and _k5.get("qiymat") == "" and _k5.get("matn") == "— Material tanlang —", [_k5, _k5b])
    jsq(PG, "() => apToggleNewItem()")
    _k6a = jsq(PG, HOLAT_JS, "ap-item")
    jsq(PG, "() => apToggleNewItem()")
    _k6b = jsq(PG, HOLAT_JS, "ap-item")
    check("K6 «Ro'yxatda yo'q — yangi material» — tanlagich yashirinadi, qaytilganda ko'rinadi", (_k6a or {}).get("korinadi") is False
          and (_k6b or {}).get("korinadi") is True, [_k6a, _k6b])
    jsq(PG, "() => { try { localStorage.removeItem(RCV_DRAFT_KEY); } catch (e) {} }")

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("Q. Qaytarishlar — «Yangi qaytarish», «Brak yozish»")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    SOROV = []
    PG.on("request", lambda r: SOROV.append(r.url) if "/api/tanlov/" in r.url else None)
    bor(PG, "/returns")
    _dom = jsq(PG, "() => document.querySelectorAll('*').length")
    jsq(PG, "() => showAddModal()")
    PG.wait_for_timeout(300)
    _q0 = sum("buyurtmalar" in u for u in SOROV)
    och(PG, "f-order", "Q ochish")
    kut(PG, "() => document.getElementById('f-order').options.length > 1")
    _q1 = jsq(PG, "() => [...document.getElementById('f-order').options].map(o => o.text)")
    _q1b = jsq(PG, HOLAT_JS, "f-order")
    check("Q1 ro'yxat tanlagich BIRINCHI ochilganda yuklandi (oyna ochilishi so'rov yubormaydi), BIR marta, qatorlar = API (raqam — mijoz · "
          "holat), ochiq panelda darhol ko'rinadi",
          _q0 == 0 and isinstance(_q1, list) and len(_q1) == len(_kb) + 1 and _q1[1].startswith(_kb[0] + " — ETN Mijoz")
          and sum("buyurtmalar" in u for u in SOROV) == 1 and isinstance(_q1b, dict) and _q1b.get("ochiq") and len(_q1b.get("bandlar", [])) == len(_kb) + 1,
          (_q0, _q1[:3] if isinstance(_q1, list) else _q1, SOROV))
    amal(lambda: PG.keyboard.type("93005"), "Q telefon")      # bo'shliqsiz — raqamlar bo'yicha («+998 93 005 45 67»)
    _q2 = jsq(PG, HOLAT_JS, "f-order")
    check("Q2 qidiruv — telefon raqami bo'yicha, bo'shliqsiz yozilsa ham («93005» → ETN Mijoz 5 buyurtmalari, 5 ta)",
          isinstance(_q2, dict) and len(_q2.get("bandlar", [])) == 5 and all("ETN Mijoz 5" in b for b in _q2.get("bandlar", [])), _q2)
    amal(lambda: PG.fill(qt("f-order") + " .qt-qidiruv input", "ETN-004-3"), "Q raqam")
    amal(lambda: PG.keyboard.press("Enter"), "Q enter")
    kut(PG, "() => !document.getElementById('f-item').disabled")
    _q3 = jsq(PG, "() => ({buyurtma: document.getElementById('f-order').selectedOptions[0]?.text, detal: [...document.getElementById('f-item').options].map(o => o.text)})")
    check("Q3 tanlandi → buyurtma detallari yuklandi (`onOrderChange`)", isinstance(_q3, dict) and (_q3.get("buyurtma") or "").startswith("ETN-004-3")
          and any("Detal 4-2" in d for d in _q3.get("detal", [])), _q3)
    och(PG, "f-order", "Q ochish2")
    amal(lambda: PG.keyboard.type("x"), "Q yozish")
    amal(lambda: PG.keyboard.press("Escape"), "Q esc1")
    _q4a = jsq(PG, """() => ({panel: !document.querySelector('.qt[data-qt-uchun="f-order"] .qt-panel').hidden,
        oyna: getComputedStyle(document.getElementById('addModal')).display})""")
    jsq(PG, "() => { document.getElementById('f-order').value = ''; onOrderChange(); }")
    PG.wait_for_timeout(200)
    jsq(PG, "() => { const m = document.getElementById('addModal'); if (m) m.__kiritildi = false; }")
    amal(lambda: PG.keyboard.press("Escape"), "Q esc2")
    PG.wait_for_timeout(200)
    _q4b = jsq(PG, """() => ({oyna: getComputedStyle(document.getElementById('addModal')).display,
        sorov: !!document.getElementById('ccModal') && getComputedStyle(document.getElementById('ccModal')).display !== 'none'})""")
    check("Q4 oyna ichida Esc: 1-chi — faqat panel yopiladi (oyna ochiq), 2-chi — oyna yopiladi", isinstance(_q4a, dict) and _q4a.get("panel") is False
          and _q4a.get("oyna") == "flex" and isinstance(_q4b, dict) and _q4b.get("oyna") == "none", [_q4a, _q4b])
    jsq(PG, "() => showAddModal()")
    och(PG, "f-order", "Q ochish3")
    amal(lambda: PG.keyboard.type("ETN"), "Q yozish2")
    amal(lambda: PG.keyboard.press("Escape"), "Q esc3")
    amal(lambda: PG.keyboard.press("Escape"), "Q esc4")
    PG.wait_for_timeout(300)
    _q5 = jsq(PG, """() => ({oyna: getComputedStyle(document.getElementById('addModal')).display,
        sorov: [...document.querySelectorAll('div')].some(d => getComputedStyle(d).position === 'fixed' && /saqlanmaydi/.test(d.textContent) && d.offsetParent !== null)})""")
    check("Q5 faqat QIDIRUV yozilgan oyna (ma'lumot kiritilmagan) — Esc da «ma'lumot saqlanmaydi» so'rovisiz yopiladi; ro'yxat qayta "
          "so'ralmadi (kesh)", isinstance(_q5, dict) and _q5.get("oyna") == "none" and not _q5.get("sorov") and sum("buyurtmalar" in u for u in SOROV) == 1,
          [_q5, SOROV])
    jsq(PG, "() => showBrakModal()")
    jsq(PG, "() => { const r = document.querySelector('input[name=\"brak-manba\"][value=\"buyurtma\"]'); if (r) { r.click(); } }")
    PG.wait_for_timeout(300)
    _q6a = sum("loyihalar" in u for u in SOROV)
    och(PG, "brak-project", "Q brak ochish")
    kut(PG, "() => document.getElementById('brak-project').options.length > 1")
    _q6 = jsq(PG, "() => [...document.getElementById('brak-project').options].map(o => o.text)")
    check("Q6 «Brak yozish»: loyihalar tanlagich ochilganda yuklandi (oldin so'rov yo'q) — ishdagi buyurtmasi bor loyihalar (9 ta), "
          "o'chirilgani / faqat qoralama — yo'q",
          _q6a == 0 and isinstance(_q6, list) and _q6[1:] == [f"ETN Loyiha {i} — ETN Mijoz {i}" for i in range(8, -1, -1)]
          and sum("loyihalar" in u for u in SOROV) == 1, (_q6a, _q6))
    amal(lambda: PG.keyboard.type("93 002"), "Q brak yozish")
    amal(lambda: PG.keyboard.press("Enter"), "Q brak enter")
    kut(PG, "() => /Detal 2-/.test(document.getElementById('brakList').textContent)")
    _q7 = jsq(PG, "() => ({loyiha: document.getElementById('brak-project').selectedOptions[0]?.text, royxat: document.getElementById('brakList').textContent.includes('Detal 2-')})")
    check("Q7 brak: telefon bo'yicha topildi, tanlandi → loyiha detallari yuklandi (`onBrakProjectChange`)",
          isinstance(_q7, dict) and (_q7.get("loyiha") or "").startswith("ETN Loyiha 2") and _q7.get("royxat"), _q7)
    _q8 = jsq(PG, "() => document.querySelectorAll('*').length")
    check("Q8 Qaytarishlar sahifasi DOM — buyurtma / loyiha ro'yxatisiz (sahifa ochilganda < 700 element)", isinstance(_dom, int) and _dom < 700, _dom)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("M. Tayyor mahsulotlar — kategoriyalar")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    bor(PG, "/finished")
    kut(PG, "() => document.querySelectorAll('#fpCategoryToggle .fp-cat-opt').length > 1")
    _m1 = jsq(PG, """() => ({tugma: [...document.querySelectorAll('#fpCategoryToggle .fp-cat-opt')].map(e => e.textContent),
        sarlavha: [...document.querySelectorAll('.fp-sec-label')].map(e => e.textContent.trim())})""")
    check("M1 tugmalar — omborda BOR turlar: Barcha, Profil, Panel, so'ng mahsulot turlari (Kafel kley, Travertin 10, Ustun), «Boshqa» — "
          "oxirida; Blok / Donali YO'Q (bunday mahsulot yo'q); sarlavha «🏭 OMBORDA»",
          isinstance(_m1, dict) and _m1.get("tugma") == ["Barcha kategoriya", "Profil", "Panel", "Kafel kley", "Travertin 10", "Ustun", "Boshqa"]
          and "🏭 OMBORDA" in (_m1.get("sarlavha") or []) and not any("PENOPLAST" in x for x in (_m1.get("sarlavha") or [])), _m1)
    QATOR = "() => [...document.querySelectorAll('#fpList .fp-row .fp-name, #fpList .fp-row [class*=name]')].map(e => e.textContent.trim()).filter(Boolean)"
    _m_hamma = jsq(PG, "() => document.getElementById('fpList').textContent")
    amal(lambda: PG.click('#fpCategoryToggle .fp-cat-opt:has-text("Kafel kley")'), "M kafel")
    PG.wait_for_timeout(200)
    _m2 = jsq(PG, "() => ({faol: document.querySelector('#fpCategoryToggle .fp-cat-opt.active')?.textContent, matn: document.getElementById('fpList').textContent})")
    amal(lambda: PG.click('#fpCategoryToggle .fp-cat-opt:has-text("Panel")'), "M panel")
    PG.wait_for_timeout(200)
    _m3 = jsq(PG, "() => document.getElementById('fpList').textContent")
    amal(lambda: PG.click('#fpCategoryToggle .fp-cat-opt:has-text("Boshqa")'), "M boshqa")
    PG.wait_for_timeout(200)
    _m4 = jsq(PG, "() => document.getElementById('fpList').textContent")
    check("M2 «Kafel kley» — faqat shu tur mahsuloti (ilgari retseptli mahsulot har tugmada yo'qolardi); «Panel» — faqat penoplast panel "
          "(turi bor «ETN Ustun panel» — o'z turida, bitta kategoriyada); «Boshqa» — turkumsiz eski mahsulot",
          isinstance(_m2, dict) and _m2.get("faol") == "Kafel kley" and "Kafel kley mahsulot" in _m2.get("matn", "")
          and "Ustun mahsulot" not in _m2.get("matn", "") and "ETN Penoplast panel" not in _m2.get("matn", "")
          and isinstance(_m3, str) and "ETN Penoplast panel" in _m3 and "Kafel kley mahsulot" not in _m3 and "ETN Penoplast profil" not in _m3
          and "ETN Ustun panel" not in _m3
          and isinstance(_m4, str) and "ETN Eski boshqa" in _m4 and "Ustun mahsulot" not in _m4
          and isinstance(_m_hamma, str) and all(x in _m_hamma for x in ("Kafel kley mahsulot", "ETN Penoplast panel", "ETN Eski boshqa")),
          [_m2 if not isinstance(_m2, dict) else _m2.get("faol"), (_m3 or "")[:200]])
    jsq(PG, "() => loadFp()")
    PG.wait_for_timeout(500)
    _m5 = jsq(PG, "() => ({faol: document.querySelector('#fpCategoryToggle .fp-cat-opt.active')?.textContent, qiymat: document.getElementById('fpCategory').value})")
    check("M3 ro'yxat qayta yuklansa (sotuv / yangilash) — tanlangan kategoriya saqlanadi", isinstance(_m5, dict) and _m5.get("faol") == "Boshqa"
          and _m5.get("qiymat") == "boshqa", _m5)
    CTX.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("T. Telefon 390 px")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    CTX, PG = kontekst(390, 844, True)
    bor(PG, "/suppliers/receive")
    kut(PG, "() => document.getElementById('ap-item').options.length > 2")
    och(PG, "ap-item", "T ochish")
    PG.wait_for_timeout(300)
    _t1 = jsq(PG, """() => { const p = document.querySelector('.qt[data-qt-uchun="ap-item"] .qt-panel').getBoundingClientRect();
        const w = document.querySelector('.qt[data-qt-uchun="ap-item"]');
        return {oqimda: w.classList.contains('qt-oqimda'), l: Math.round(p.left), r: Math.round(p.right), vw: document.documentElement.clientWidth,
                sahifa: document.documentElement.scrollWidth, bandH: Math.round(w.querySelector('.qt-band').getBoundingClientRect().height)}; }""")
    check("T1 390 px Kirim: panel oqim ichida (kesilmaydi), ekran kengligida, sahifa kengaymaydi, qator balandligi ≥ 36 px",
          isinstance(_t1, dict) and "l" in _t1 and _t1["oqimda"] and _t1["l"] >= 0 and _t1["r"] <= _t1["vw"] and _t1["sahifa"] <= _t1["vw"]
          and _t1["bandH"] >= 36, _t1)
    bor(PG, "/returns")
    jsq(PG, "() => showAddModal()")
    och(PG, "f-order", "T qaytarish")
    kut(PG, "() => document.getElementById('f-order').options.length > 1")
    PG.wait_for_timeout(300)
    _t2 = jsq(PG, """() => { const p = document.querySelector('.qt[data-qt-uchun="f-order"] .qt-panel').getBoundingClientRect();
        const m = document.querySelector('#addModal > div').getBoundingClientRect();
        return {l: Math.round(p.left), r: Math.round(p.right), ml: Math.round(m.left), mr: Math.round(m.right),
                tugmaH: Math.round(document.querySelector('.qt[data-qt-uchun="f-order"] .qt-maydon').getBoundingClientRect().height)}; }""")
    check("T2 390 px «Yangi qaytarish»: panel oyna ichida (chetdan chiqmaydi), tugma balandligi ≥ 40 px",
          isinstance(_t2, dict) and "l" in _t2 and _t2["l"] >= _t2["ml"] and _t2["r"] <= _t2["mr"] and _t2["tugmaH"] >= 40, _t2)
    CTX.close()
if br:
    br.close()
if pw_ctx:
    pw_ctx.stop()
server.should_exit = True

section("X. Xatolar")
check("X1 brauzerda JS xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])
check("X2 serverda 5xx yo'q", not XATO5, XATO5[:5])
check("X3 brauzer amallari bajarildi (element topilmadi / vaqt tugadi YO'Q)", not AMAL_XATO, AMAL_XATO[:5])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
