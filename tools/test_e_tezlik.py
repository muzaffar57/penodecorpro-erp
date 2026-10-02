#!/usr/bin/env python3
"""
test_e_tezlik.py — kech120, E BOSQICH 1-qism (TEZLIK): hisobotlar so'rovlar ORASIDA eslab qolinadi (yozuv bo'lsa darhol
eskiradi), sahifa bir ochilishida bir xil so'rov bir marta, Bosh sahifa faqat 5 ta buyurtma oladi, kirish sahifasi rasmi siqilgan,
Hisobotlardagi taqqoslash kartalari telefonda ekranga sig'adi.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k127/tez.py`, 300 buyurtma, SQLite va HAQIQIY PG 16; sinov sayti — ichki brauzer):
  U-09  «Hisobotlar» bir ochilishda oylik hisobotni 12 marta (4 xil oy kaliti) hisoblardi — serverda ~8 s, 623 SQL; «Dashboard»
        — 4 marta, ~5,7 s; «Moliya» — 6; sinov saytida (kam ma'lumot) har hisobot so'rovi 0,5–1,2 s. Brauzer: taqqoslash 3 marta,
        pul oqimi 2 marta, KPI da `/api/finance/report` 2 marta so'ralardi. Bosh sahifa «So'nggi 5 buyurtma» uchun HAMMA buyurtmani
        olardi — 373 KB.
  U-10  kirish sahifasi foni `login-bg.png` 1 475 KB (siqilmaydi), chap panel logotipi 42 px uchun 1024 × 1024.
  K120-1 (JONLI topilgan, 360 px, skrinshot) «O'tgan oy bilan taqqoslash»: «o'zgarmadi» so'zi kartani kengaytirib, o'ng kartalar
        ekrandan chiqardi, panel yon tomonga surilardi (375–390 px da — panel ichki chetidan 28 px).
QOIDA (xotira): natija faqat (1) shu jarayonda hech qanday yozuv bo'lmagan, (2) hisob paytida ham yozuv bo'lmagan, (3) sessiya
  toza (kutilayotgan o'zgarish yo'q, ulanish shu tranzaksiyada yozmagan), (4) natija oddiy ma'lumot, (5) 60 s dan yosh bo'lsa
  qaytariladi; bir nechta ishchi (`WEB_CONCURRENCY` > 1) — xotira o'chiq. Xotira bilan va xotirasiz natija AYNAN.
BO'LIMLAR: S — statik; M — ma'lumot (brauzerda dasturning o'z API si: joriy oy — to'liq ish zanjiri, o'tgan oy (vaqt sayohati)
  — loyiha, buyurtmalar, to'lov, «Tayyor», xarajat); A — xotira bilan = ASL hisob (xotira ham, hisobot keshi ham o'chiq); B — yozuvdan keyin darhol yangilanadi
  (API va to'g'ridan-to'g'ri baza yozuvi); C — poyga (boshqa sessiyaning ochiq tranzaksiyasi); D — iflos sessiya; E — hisob paytidagi
  yozuv; F — qaytarilgan natijani o'zgartirish xotirani buzmaydi; G — muddat; H — bir nechta ishchi; I — kalitlar (oy kesimi,
  korxona); K — brauzer (takroriy so'rov, Bosh sahifa, `bittaYuklash`, rasm,
  taqqoslash kartalari 360–1440 px); L — Hisobotlar sahifasi sovuq ochilishda oylik hisob soni.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 126) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium, `time_machine`, `Pillow`.
ISHLATISH: python3 tools/test_e_tezlik.py
"""
import os
import re
import sys
import io
import json
import glob
import math
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
PG_BAZA = "e_tezlik_test"
_T = tempfile.mkdtemp(prefix="etez_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'e_tezlik_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("WEB_CONCURRENCY", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
    import database                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402

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
    """`qismlar` matnda shu TARTIBDA uchraydimi (topilmasa False — `index` emas)."""
    p = 0
    for q in qismlar:
        i = src.find(q, p)
        if i < 0:
            return False
        p = i + len(q)
    return True


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik: yozuv versiyasi, hisobot xotirasi, bitta yuklash, Bosh sahifa, rasm")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
DB_SRC = oqi("database.py")
SV_SRC = oqi("services.py")
BASE = oqi("templates/base.html")
REP = oqi("templates/reports.html")
KPI = oqi("templates/kpi.html")
HOME = oqi("templates/home.html")
LOGIN = oqi("templates/login.html")
MAIN = oqi("main.py")
CRUD = oqi("crud.py")

check("S1 database.py: yozuv hodisalari `Engine` SINFIGA (jarayondagi hamma dvigatel) — bayonot, commit, rollback; hovuzga qaytish",
      tartibda(DB_SRC, '@_event_yv.listens_for(_Engine_yv, "before_cursor_execute")', '_event_yv.listen(_Engine_yv, "commit"',
               '_event_yv.listen(_Engine_yv, "rollback"', '_event_yv.listen(_Pool_yv, "checkin"'))
_ybm = getattr(database, "yozuv_bayonotimi", None)
_hol = {}
if callable(_ybm):
    for _st, _kut in (("SELECT 1", False), ("  select * from orders", False), ("-- izoh\nSELECT 1", False), ("/* x */ SELECT 1", False),
                      ("PRAGMA foreign_keys", False), ("EXPLAIN SELECT 1", False), ("INSERT INTO t VALUES (1)", True),
                      ("update orders set notes='x'", True), ("DELETE FROM t", True), ("WITH x AS (UPDATE t SET a=1 RETURNING a) SELECT * FROM x", True),
                      ("CREATE TABLE t (a int)", True), ("-- faqat izoh", True), ("", True)):
        _hol[_st] = (_ybm(_st), _kut)
check("S2 `yozuv_bayonotimi`: SELECT / PRAGMA / EXPLAIN (izohdan keyin ham) — o'qish; INSERT / UPDATE / DELETE / CTE / DDL / bo'sh — YOZUV "
      "(shubhada — yozuv: xotira hech qachon eski natija bermaydi)", _hol and all(a == b for a, b in _hol.values()), _hol)
check("S3 services.py: `get_monthly_report` — tashqi `@_hisobot_xotirasi_bilan`, ichki `@_hisobot_keshi_bilan`",
      tartibda(SV_SRC, "@_hisobot_xotirasi_bilan", "@_hisobot_keshi_bilan", "def get_monthly_report("))
check("S4 xotira qoidalari kodda: versiya (oldin = keyin), sessiya tozaligi, oddiy ma'lumot, muddat, `WEB_CONCURRENCY`, `deepcopy`",
      all(x in SV_SRC for x in ("_yv_hx() == _v0 and _hx_sessiya_tozami(_db) and _hx_oddiymi(natija)", "HISOBOT_XOTIRASI_MUDDAT",
                                 '_os_hx.environ.get("WEB_CONCURRENCY")', "_copy_hx.deepcopy(_n)", "db.new or db.dirty or db.deleted")))
_i_bitta = BASE.find("window.bittaYuklash")
_i_blok = BASE.find("{% block scripts %}")
_i_kirill = BASE.find("const _originalFetch = window.fetch;")
check("S5 base.html: `bittaYuklash` sahifa skriptlaridan OLDIN (`{% block scripts %}`), kirill o'ramidan oldin (u buni o'raydi)",
      0 <= _i_bitta < _i_blok < _i_kirill, [_i_bitta, _i_blok, _i_kirill])
check("S6 reports.html `loadAll` — `bittaYuklash` orqali (typeof bilan — JS testlari funksiyani alohida oladi); kpi.html boshlanishi — ham",
      "typeof bittaYuklash === 'function' ? bittaYuklash(_hammasi) : _hammasi()" in REP
      and "typeof bittaYuklash === 'function' ? bittaYuklash(_boshla) : _boshla()" in KPI)
check("S7 Bosh sahifa — `/api/orders?limit=5` (hammasi emas); API `limit` (1–500), crud tartibi yaratilgan vaqt + id",
      "fetch('/api/orders?limit=5')" in HOME and "fetch('/api/orders')" not in HOME
      and "limit: Optional[int] = Query(None, ge=1, le=500)" in MAIN
      and "order_by(Order.created_at.desc(), Order.id.desc()).limit(int(limit))" in CRUD)
check("S8 login.html: fon — `login-bg.jpg` (hamma brauzer) + `image-set` WebP; `login-bg.png` endi so'ralmaydi (faqat izohda)",
      "url('/static/login-bg.jpg')" in LOGIN and "image-set(url('/static/login-bg.webp') type('image/webp')" in LOGIN
      and "url('/static/login-bg.png')" not in LOGIN)
check("S9 base.html: chap panel logotipi — `logo_round_128.jpg`", 'src="/static/logo_round_128.jpg"' in BASE and 'src="/static/logo_round.jpg"' not in BASE)
_rasm = {}
try:
    from PIL import Image, ImageChops, ImageStat
    _asl_png = Image.open(os.path.join(ROOT, "static/login-bg.png")).convert("RGB")

    def _psnr(a, b):
        d = ImageChops.difference(a, b)
        st = ImageStat.Stat(d.point(lambda x: x * x))
        mse = sum(st.mean) / 3
        return 99.0 if mse == 0 else 10 * math.log10(255 ** 2 / mse)
    for _f in ("static/login-bg.webp", "static/login-bg.jpg"):
        _p = os.path.join(ROOT, _f)
        _im = Image.open(_p).convert("RGB")
        _rasm[_f] = {"kb": os.path.getsize(_p) // 1024, "olcham": _im.size, "psnr": round(_psnr(_asl_png, _im), 1)}
    _lp = os.path.join(ROOT, "static/logo_round_128.jpg")
    _rasm["logo"] = {"kb": os.path.getsize(_lp) // 1024, "olcham": Image.open(_lp).size}
except Exception as _e:                    # noqa: BLE001
    _rasm["xato"] = f"{type(_e).__name__}: {_e}"
check("S10 rasmlar: WebP ≤ 100 KB, JPEG ≤ 130 KB (asl 1 475 KB), o'lcham asl bilan bir xil (1122 × 1402), sifat PSNR ≥ 42 dB; "
      "logotip 128 × 128, ≤ 10 KB",
      _rasm.get("static/login-bg.webp", {}).get("kb", 999) <= 100 and _rasm.get("static/login-bg.jpg", {}).get("kb", 999) <= 130
      and all(_rasm.get(k, {}).get("olcham") == (1122, 1402) and _rasm.get(k, {}).get("psnr", 0) >= 42
              for k in ("static/login-bg.webp", "static/login-bg.jpg"))
      and _rasm.get("logo", {}).get("olcham") == (128, 128) and _rasm.get("logo", {}).get("kb", 99) <= 10, _rasm)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Ma'lumot — o'tgan oy (vaqt sayohati) va joriy oy: dasturning o'z API si orqali to'liq ish zanjiri")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "etez_admin", "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, ADMIN, PAROL, UserRole.ADMIN, "Namuna Dekor", company_id=1)
s.close()

_src_tel = oqi("tools/test_c_telefon.py")


def _js_ol(nom):
    i = _src_tel.find(nom + ' = r"""')
    if i < 0:
        return ""
    i += len(nom + ' = r"""')
    return _src_tel[i:_src_tel.find('"""', i)]


ZANJIR_JS = _js_ol("ZANJIR_JS")
CHART_ORINBOSAR = _js_ol("CHART_ORINBOSAR") or "window.Chart = function () { return {destroy() {}, update() {}}; };"
check("M0 ish zanjiri (`tools/test_c_telefon.py` ZANJIR_JS) topildi", len(ZANJIR_JS) > 1000)

try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"
check("M1 Python `playwright` bor", PW_BOR, _pw_xato)
try:
    import time_machine
    TM_BOR = True
except Exception:                          # noqa: BLE001
    TM_BOR = False
check("M1b `time_machine` bor (o'tgan oy ma'lumoti — vaqt sayohati bilan)", TM_BOR)

import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


SOROVLAR = []          # serverga kelgan so'rovlar (usul, yo'l + so'rov satri) — brauzer bo'limi uchun
_SOR_ON = {"on": False}


class Sanagich:
    """ASGI o'rami: `_SOR_ON` yoqilganda har HTTP so'rovni yozib boradi (dastur kodi o'zgarmaydi)."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and _SOR_ON["on"]:
            _q = (scope.get("query_string") or b"").decode()
            SOROVLAR.append((scope.get("method"), scope.get("path") + ("?" + _q if _q else "")))
        return await self.app(scope, receive, send)


port = _port()
server = uvicorn.Server(uvicorn.Config(Sanagich(main.app), host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
th = threading.Thread(target=server.run, daemon=True)
th.start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
check("M2 lokal server ishga tushdi", server.started)
B = f"http://127.0.0.1:{port}"

# Toshkent hozir; o'tgan oy — 27-kun 12:00 (oy kesimi «1–N kun» bilan farq qilsin: bugun 27 dan oldin bo'lsa kesim uni chiqaradi)
TK = datetime.utcnow() + timedelta(hours=5)
Y, M = TK.year, TK.month
PY, PM = (Y, M - 1) if M > 1 else (Y - 1, 12)
PPY, PPM = (PY, PM - 1) if PM > 1 else (PY - 1, 12)
OTGAN_TK = datetime(PY, PM, 27, 12, 0, 0)


def yonalish(route):
    u = route.request.url
    if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
        return route.fulfill(status=200, content_type="application/javascript", body=CHART_ORINBOSAR)
    if u.startswith("https://fonts.googleapis.com/"):
        return route.fulfill(status=200, content_type="text/css", body="")
    return route.fulfill(status=204, body="")


def xotira_holati():
    f = getattr(services, "hisobot_xotirasi_holati", None)
    return f() if callable(f) else {}


def xotira_tozala():
    f = getattr(services, "hisobot_xotirasini_tozala", None)
    if callable(f):
        f()


@contextlib.contextmanager
def bayroqlar(**kv):
    """`services` modul bayroqlarini vaqtincha o'rnatadi (asl kodda yo'q bo'lsa — qo'shib, keyin olib tashlaydi)."""
    eski = {k: getattr(services, k, "__yoq__") for k in kv}
    for k, v in kv.items():
        setattr(services, k, v)
    try:
        yield
    finally:
        for k, v in eski.items():
            if v == "__yoq__":
                try:
                    delattr(services, k)
                except Exception:          # noqa: BLE001
                    pass
            else:
                setattr(services, k, v)


NAT = {}
pw_ctx = None
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
        check("M3 Chromium ishga tushdi", False, f"{type(_e).__name__}: {_e}")
else:
    br = None


def kontekst(w=1440, h=900, tel=False):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=tel, has_touch=tel,
                         timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                         r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
    pg = ctx.new_page()
    pg.goto(B + "/login")
    pg.fill("input[name=username]", ADMIN)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


OLISH_JS = """async (u) => { try { const r = await fetch(u, {cache: 'no-store'}); return {s: r.status, t: await r.text()}; }
                            catch (e) { return {s: 599, t: String(e)}; } }"""
YUBOR_JS = """async ([usul, u, tana]) => { try { const o = {method: usul, cache: 'no-store'};
                 if (tana !== null) { o.headers = {'Content-Type': 'application/json'}; o.body = JSON.stringify(tana); }
                 const r = await fetch(u, o); return {s: r.status, t: await r.text()}; } catch (e) { return {s: 599, t: String(e)}; } }"""
KICHIK_JS = r"""async (K) => {
  const L = [];
  const so = async (usul, url, tana) => {
    const o = {method: usul, cache: 'no-store', credentials: 'same-origin'};
    if (tana !== undefined) { o.headers = {'Content-Type': 'application/json'}; o.body = JSON.stringify(tana); }
    let r; try { r = await fetch(url, o); } catch (e) { return {st: 599, t: String(e), j: null}; }
    const t = await r.text(); let j = null; try { j = JSON.parse(t); } catch (e) { j = null; }
    return {st: r.status, t, j};
  };
  const q = async (nom, usul, url, tana) => { const r = await so(usul, url, tana); L.push([nom, r.st, String(r.t || '').slice(0, 200)]); return r; };
  const inv = (await so('GET', '/api/inventory')).j;
  const ro = Array.isArray(inv) ? inv : ((inv && inv.items) || []);
  const peno = ro.find(x => x.is_default_penoplast) || ro.find(x => x.is_penoplast);
  if (!peno) return {L, yiqilgan: [['penoplast', 0, "yo'q"]], ids: []};
  const lo = await q('loyiha', 'POST', '/api/projects', {project_name: 'Oldingi oy loyihasi', client_name: 'Oldingi Mijoz', client_phone: '+998900007777',
                                                        client_address: 'Andijon', description: '', notes: ''});
  const pid = lo.j && (lo.j.id || (lo.j.project && lo.j.project.id));
  const ids = [];
  for (let i = 0; i < 4; i++) {
    const tana = {project_id: pid, order_type: 'product', recipe_id: null, master_id: null, deadline: K.muddat, is_draft: false, base_price: 600000,
      loy_kg: null, items: [{name: 'Oldingi karniz ' + i, category: 'profil', width: 20, thickness: 10, length: 30, quantity: 2 + i,
      unit_price: 70000 + i * 1000, is_coated: false, penoplast_id: peno.id, price_per_m3: null, finished_product_id: null, sub_details: []}]};
    let r = await so('POST', '/api/orders', tana);
    if (r.st === 409) r = await so('POST', '/api/orders?confirm_shortage=true', tana);
    L.push(['buyurtma' + i, r.st, String(r.t || '').slice(0, 200)]);
    const oid = r.j && (r.j.id || (r.j.order && r.j.order.id));
    ids.push(oid);
    await q('tolov' + i, 'POST', '/api/payments', {order_id: oid, amount: 50000 + i * 10000, payment_type: 'partial', payment_method: 'naqd', notes: 'oldingi'});
    if (i < 2) await q('tayyor' + i, 'POST', '/api/orders/' + oid + '/ready');
  }
  await q('xarajat', 'POST', '/api/finance/transactions', {date: K.sana + 'T00:00:00', category: 'Boshqa', amount: 210000, notes: 'oldingi xarajat',
                                                          production_type: 'umumiy'});
  await q('transport', 'POST', '/api/transport-expenses', {amount: 45000, materials_note: 'oldingi yuk', notes: 'oldingi transport', production_type: 'umumiy'});
  return {L, yiqilgan: L.filter(x => !(typeof x[1] === 'number' && x[1] >= 200 && x[1] < 300)), ids};
}"""

# Korxona 1 logotipi — `main` / `staging` dagi holat (ishga tushish migratsiyasi `logo_path` ni standart logotipga to'ldiradi; bu test
# `lifespan="off"` bilan yuradi)
try:
    from production_models import Company as _Co
    _sc = SessionLocal()
    try:
        _c1 = _sc.query(_Co).filter(_Co.id == 1).first()
        if _c1 is not None and not (getattr(_c1, "logo_path", None) or "").strip():
            _c1.logo_path = "static/logo_transparent.png"
            _sc.commit()
    finally:
        _sc.close()
except Exception as _e:                    # noqa: BLE001
    print("logotip sozlanmadi:", _e)

PG = None
CTX = None
Z1 = Z2 = None
if br:
    CTX, PG = kontekst()
    check("M3 kirish (lokal sinov foydalanuvchisi)", "/login" not in PG.url, PG.url)
    try:
        Z2 = PG.evaluate(ZANJIR_JS, {"m": "Namuna", "sana": TK.strftime("%Y-%m-%d"), "yil": Y, "oy": M,
                                     "muddat": (TK + timedelta(days=9)).strftime("%Y-%m-%d")})
    except Exception as _e:                # noqa: BLE001
        Z2 = {"yiqilgan": [["istisno", 0, f"{type(_e).__name__}: {str(_e)[:300]}"]], "L": []}
    check("M4 joriy oy — to'liq ish zanjiri (ombor, kirim, retsept, usta, hodim, loyiha, buyurtmalar, to'lov, yetkazish, qaytarish, brak, "
          "MRP, tayyor mahsulot, moliya, majburiyat): hamma qadam 2xx", Z2 and not Z2.get("yiqilgan") and len(Z2.get("L") or []) >= 50,
          (Z2 or {}).get("yiqilgan"))
    if TM_BOR:
        try:
            with time_machine.travel(OTGAN_TK - timedelta(hours=5), tick=True):
                Z1 = PG.evaluate(KICHIK_JS, {"sana": OTGAN_TK.strftime("%Y-%m-%d"),
                                             "muddat": (OTGAN_TK + timedelta(days=9)).strftime("%Y-%m-%d")})
        except Exception as _e:            # noqa: BLE001
            Z1 = {"yiqilgan": [["istisno", 0, f"{type(_e).__name__}: {str(_e)[:300]}"]], "L": []}
    check(f"M5 o'tgan oy ({PY}-{PM:02d}-27, vaqt sayohati): loyiha, 4 buyurtma, to'lovlar, 2 ta «Tayyor», xarajat, transport — hamma 2xx",
          Z1 and not Z1.get("yiqilgan") and len(Z1.get("L") or []) >= 13, (Z1 or {}).get("yiqilgan"))


def jsq(pg, kod, arg=None):
    """`page.evaluate` — sahifadagi xato testni QULATMAYDI: {"js_xato": …} qaytadi (mutatsiya / asl kodda ham NATIJA chiqadi)."""
    try:
        return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
    except Exception as ex:                # noqa: BLE001
        return {"js_xato": f"{type(ex).__name__}: {str(ex)[:300]}"}


def ol(url):
    """Brauzer sessiyasi bilan GET → (status, matn)."""
    if PG is None:
        return 599, "brauzer yo'q"
    r = jsq(PG, OLISH_JS, B + url)
    return r.get("s", 599), r.get("t", r.get("js_xato"))


def yubor(usul, url, tana=None):
    if PG is None:
        return 599, "brauzer yo'q"
    r = jsq(PG, YUBOR_JS, [usul, B + url, tana])
    return r.get("s", 599), r.get("t", r.get("js_xato"))


def jsonla(t):
    try:
        return json.loads(t)
    except Exception:                      # noqa: BLE001
        return t


HISOBOTLAR = [
    f"/api/finance/report?year={Y}&month={M}", f"/api/finance/report?year={PY}&month={PM}", f"/api/finance/report?year={PPY}&month={PPM}",
    f"/api/reports/comparison?year={Y}&month={M}", f"/api/reports/comparison?year={PY}&month={PM}",
    "/api/finance/history?months=3", "/api/finance/history?months=1",
    f"/api/reports/forecast?year={Y}&month={M}", "/api/reports/business-health", "/api/reports/alerts",
    f"/api/obligations/status?year={Y}&month={M}", f"/api/finance/debt-summary?year={Y}&month={M}",
    f"/api/finance/yonalishlar?year={Y}&month={M}&gacha_yil={Y}&gacha_oy={M}",
    "/api/reports/brak-tahlil?oylar=1", "/api/reports/brak-tahlil?oylar=3", "/api/dashboard/today", "/api/finance/daily",
    f"/api/masters/kpi-report?year={Y}", "/api/dashboard/charts",
]


def toplam(xotira=True, kesh=True):
    """Hamma hisobot so'rovlari (bir xil tartibda) — {url: (status, JSON)}."""
    natija = {}
    with bayroqlar(HISOBOT_XOTIRASI_YOQIQ=xotira, HISOBOT_KESHI_YOQIQ=kesh):
        for u in HISOBOTLAR:
            st, t = ol(u)
            natija[u] = (st, jsonla(t))
    return natija


def farqlar(a, b):
    return [u for u in HISOBOTLAR if a.get(u) != b.get(u)]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Xotira bilan = ASL hisob (xotira ham, hisobot keshi ham o'chiq) — 19 hisobot so'rovi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
xotira_tozala()
ASL1 = toplam(xotira=False, kesh=False)
ASL2 = toplam(xotira=False, kesh=False)
_beqaror = farqlar(ASL1, ASL2)
check("A0 ASL hisob ikki marta — AYNAN (taqqoslash ishonchli; vaqtga bog'liq maydon yo'q)", not _beqaror, _beqaror)
check("A0b hamma so'rov 200 va ma'lumot bor (bo'sh isbot emas: joriy va o'tgan oy daromadi > 0)",
      all(ASL1[u][0] == 200 for u in HISOBOTLAR)
      and float((ASL1[HISOBOTLAR[0]][1] or {}).get("daromad", 0) or 0) > 0 and float((ASL1[HISOBOTLAR[1]][1] or {}).get("daromad", 0) or 0) > 0,
      {u: ASL1[u][0] for u in HISOBOTLAR})
xotira_tozala()
X1 = toplam()
_h1 = xotira_holati()
X2 = toplam()
_h2 = xotira_holati()
check("A1 xotira bilan (birinchi o'tish — hisoblanadi) = ASL", not farqlar(ASL1, X1), farqlar(ASL1, X1))
check("A2 xotira bilan (ikkinchi o'tish — xotiradan) = ASL", not farqlar(ASL1, X2), farqlar(ASL1, X2))
check("A3 ikkinchi o'tishda oylik hisob QAYTA hisoblanmadi (hisoblandi o'zgarmadi, topildi oshdi)",
      _h2.get("hisoblandi") == _h1.get("hisoblandi") and _h2.get("topildi", 0) > _h1.get("topildi", 0) and _h1.get("hisoblandi", 0) >= 3,
      [_h1, _h2])
X3 = toplam(xotira=True, kesh=False)
check("A4 xotira bilan, hisobot keshi o'chiq — ham = ASL", not farqlar(ASL1, X3), farqlar(ASL1, X3))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Yozuvdan keyin DARHOL yangilanadi (xotira yoqiq): API yozuvlari va to'g'ridan-to'g'ri baza yozuvi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def yozuv_sinovi(nom, yoz, kutilgan_ozgarish):
    """Xotirani to'ldiradi → yozadi → xotira bilan natija = ASL (yangi) va kutilgan so'rov(lar) haqiqatan o'zgargan."""
    xotira_tozala()
    oldin = toplam()
    toplam()                                    # xotiradan (ikkinchi o'tish)
    _h0 = xotira_holati()
    info = yoz()
    _st = info[0] if isinstance(info, tuple) else 200
    keyin = toplam()
    asl = toplam(xotira=False, kesh=False)
    _oz = [u for u in kutilgan_ozgarish if oldin.get(u) != asl.get(u)]
    check(f"B {nom}: yozuvdan keyin xotira bilan = ASL (19 so'rov)", not farqlar(asl, keyin), [farqlar(asl, keyin), info])
    check(f"B {nom}: yozuv natijani haqiqatan o'zgartirdi ({', '.join(x.split('?')[0] for x in kutilgan_ozgarish)}) — bo'sh isbot emas",
          _oz and _h0.get("topildi", 0) > 0 and 200 <= int(_st or 0) < 300, [_oz, str(info)[:200], _h0])


_ord_hammasi = jsonla(ol("/api/orders")[1]) if PG else []
_tayyor_emas = [o for o in (_ord_hammasi if isinstance(_ord_hammasi, list) else []) if o.get("status") in ("new", "in_progress", "coating")]


def _xarajat():
    return yubor("POST", "/api/finance/transactions", {"date": TK.strftime("%Y-%m-%d") + "T00:00:00", "category": "Boshqa", "amount": 123457,
                                                        "notes": "etez xarajat", "production_type": "umumiy"})


yozuv_sinovi("B1 xarajat qo'shildi (Moliya)", _xarajat, [f"/api/finance/report?year={Y}&month={M}", "/api/finance/history?months=1"])
if _tayyor_emas:
    _oid = _tayyor_emas[0]["id"]
    yozuv_sinovi("B2 buyurtma «Tayyor»", lambda: yubor("POST", f"/api/orders/{_oid}/ready"),
                 [f"/api/finance/report?year={Y}&month={M}", f"/api/reports/comparison?year={Y}&month={M}"])
else:
    check("B2 «Tayyor» qilinadigan buyurtma topildi", False, [o.get("status") for o in _ord_hammasi][:10] if isinstance(_ord_hammasi, list) else _ord_hammasi)


def _bazaga_tog_ridan():
    from models import ExpenseTransaction
    s2 = SessionLocal()
    try:
        t = s2.query(ExpenseTransaction).filter(ExpenseTransaction.notes == "etez xarajat").first()
        if t is None:
            return "yozuv topilmadi"
        t.amount = float(t.amount or 0) + 1000000
        s2.commit()
        return f"ExpenseTransaction #{t.id} +1 000 000"
    finally:
        s2.close()


yozuv_sinovi("B3 to'g'ridan-to'g'ri baza yozuvi (HTTP siz, boshqa sessiya + commit)", _bazaga_tog_ridan,
             [f"/api/finance/report?year={Y}&month={M}"])

# B4 — commit hodisasi BO'LMAYDIGAN yozuv (AUTOCOMMIT ulanish: bayonot darhol saqlanadi, tranzaksiya yo'q): faqat bayonot
# paytidagi versiya oshishi ushlaydi (dasturda hozir AUTOCOMMIT yo'q — kelajak skriptlari / migratsiyalar uchun himoya)
from sqlalchemy import text as _text_b4     # noqa: E402


def _b4_hisob():
    _sb = SessionLocal()
    try:
        return json.loads(json.dumps(services.get_monthly_report(_sb, Y, M, company_id=1), default=str, sort_keys=True))
    finally:
        _sb.close()


xotira_tozala()
_b4_0 = _b4_hisob()
_b4 = {}
try:
    from models import ExpenseTransaction as _ET_b4
    from sqlalchemy import create_engine as _ce_b4
    # alohida dvigatel, DVIGATEL darajasida AUTOCOMMIT (har bayonot darhol saqlanadi). Ulanish darajasidagi
    # `execution_options(isolation_level="AUTOCOMMIT")` ilova dvigatelida (pg8000 + `pool_pre_ping`) ishlamaydi — tekshiruv
    # «SELECT 1» tranzaksiyani ochib qo'yadi, yozuv yopilganda bekor bo'ladi (O'LCHANGAN; dasturda AUTOCOMMIT ishlatilmaydi)
    _eb4 = _ce_b4(database.engine.url, isolation_level="AUTOCOMMIT")
    _cb4 = _eb4.connect()
    try:
        _b4["qator"] = _cb4.execute(_text_b4(f"UPDATE {_ET_b4.__tablename__} SET amount = amount + 4321 WHERE notes = 'etez xarajat'")).rowcount
        _s_b4 = SessionLocal()
        try:
            _b4["saqlandi"] = float(_s_b4.query(_ET_b4.amount).filter(_ET_b4.notes == "etez xarajat").scalar() or 0)
        finally:
            _s_b4.close()
        _b4["keyin"] = _b4_hisob()
        _b4["holat"] = xotira_holati()
        with bayroqlar(HISOBOT_XOTIRASI_YOQIQ=False):
            _b4["asl"] = _b4_hisob()
    finally:
        _cb4.close()
        _eb4.dispose()
except Exception as _e:                    # noqa: BLE001
    _b4["xato"] = f"{type(_e).__name__}: {_e}"
check("B4 AUTOCOMMIT yozuvi (commit hodisasi yo'q; boshqa ulanishga darhol ko'rinadi) — keyingi hisob YANGI (= ASL), xotiradagi eski "
      "natija qaytmadi",
      "xato" not in _b4 and _b4.get("qator") == 1 and _b4.get("keyin") == _b4.get("asl") and _b4.get("keyin") != _b4_0,
      [_b4.get("xato"), _b4.get("qator"), _b4.get("saqlandi"), _b4.get("holat")]
      + [(x or {}).get("jami_xarajat") for x in (_b4_0, _b4.get("keyin"), _b4.get("asl"))])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Poyga: boshqa sessiya yozdi (tranzaksiya OCHIQ) → hisob saqlandi → commit → keyingi hisob YANGI ma'lumotda")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def hisob(s, y=Y, m=M, c=1):
    return json.loads(json.dumps(services.get_monthly_report(s, y, m, company_id=c), default=str, sort_keys=True))


def asl_hisob(y=Y, m=M, c=1):
    with bayroqlar(HISOBOT_XOTIRASI_YOQIQ=False):
        s3 = SessionLocal()
        try:
            return hisob(s3, y, m, c)
        finally:
            s3.close()


xotira_tozala()
from models import ExpenseTransaction       # noqa: E402
s1 = SessionLocal()
_r1 = _r2 = None
_h_c = []
try:
    _t = s1.query(ExpenseTransaction).filter(ExpenseTransaction.notes == "etez xarajat").first()
    _t.amount = float(_t.amount or 0) + 777000
    s1.flush()                                   # UPDATE bajarildi — commit YO'Q (boshqa sessiyaga ko'rinmaydi)
    s2 = SessionLocal()
    try:
        _r1 = hisob(s2)
        _h_c.append(xotira_holati())
    finally:
        s2.close()
    s1.commit()
    s4 = SessionLocal()
    try:
        _r2 = hisob(s4)
        _h_c.append(xotira_holati())
    finally:
        s4.close()
finally:
    s1.close()
_asl_c = asl_hisob()
check("C1 ochiq tranzaksiya paytidagi hisob saqlandi (o'sha paytdagi tasdiqlangan ma'lumot) — bo'sh isbot emas",
      _h_c and _h_c[0].get("saqlandi", 0) >= 1, _h_c)
check("C2 commit dan keyin hisob YANGI ma'lumotda (= ASL) va oldingisidan farq qiladi (commit versiyani oshiradi — eski natija qaytmaydi)",
      _r2 == _asl_c and _r1 != _r2, [str(_r1)[:150], str(_r2)[:150]])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Iflos sessiya (kutilayotgan o'zgarish / shu tranzaksiyada yozuv) — xotira ishlatilmaydi, ASL hisob")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
xotira_tozala()
_s = SessionLocal()
try:
    hisob(_s)                                    # xotira to'ldi
finally:
    _s.close()
_d = {}
s5 = SessionLocal()
try:
    _t5 = s5.query(ExpenseTransaction).filter(ExpenseTransaction.notes == "etez xarajat").first()
    _h0 = xotira_holati()
    _t5.amount = float(_t5.amount or 0) + 5000   # flush YO'Q — faqat sessiyada (dirty)
    _d["dirty"] = hisob(s5)
    _d["h_dirty"] = xotira_holati()
    s5.flush()                                   # endi ulanish shu tranzaksiyada yozdi
    _d["flush"] = hisob(s5)
    _d["h_flush"] = xotira_holati()
    with bayroqlar(HISOBOT_XOTIRASI_YOQIQ=False):
        _d["asl_flush"] = hisob(s5)
    s5.rollback()
finally:
    s5.close()
check("D1 kutilayotgan o'zgarishi bor sessiya — xotira rad etdi (rad oshdi), xotiradan olinmadi",
      _d.get("h_dirty", {}).get("rad", 0) > _h0.get("rad", 0) and _d.get("h_dirty", {}).get("topildi") == _h0.get("topildi"),
      [_h0, _d.get("h_dirty")])
check("D2 shu tranzaksiyada yozgan sessiya — rad, natija o'z (tasdiqlanmagan) holatida = ASL",
      _d.get("h_flush", {}).get("rad", 0) > _d.get("h_dirty", {}).get("rad", 0) and _d.get("flush") == _d.get("asl_flush"),
      [_d.get("h_flush"), str(_d.get("flush"))[:120], str(_d.get("asl_flush"))[:120]])
_s = SessionLocal()
try:
    _d3 = hisob(_s)
finally:
    _s.close()
check("D3 rollback dan keyin — xotira bilan = ASL (bekor qilingan o'zgarish ko'rinmaydi)", _d3 == asl_hisob())

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Hisob PAYTIDA boshqa yozuv bo'lsa — natija saqlanmaydi (keyingi chaqiruv qayta hisoblaydi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
xotira_tozala()
_asl_tr = services.get_transport_stats_for_period
_yozildi = {"n": 0}


def _tr_yozuvli(*a, **k):
    if _yozildi["n"] == 0:
        _yozildi["n"] += 1
        s6 = SessionLocal()
        try:
            _x = s6.query(ExpenseTransaction).filter(ExpenseTransaction.notes == "etez xarajat").first()
            _x.notes = "etez xarajat"            # o'zgarishsiz — lekin UPDATE baribir yuboriladi
            s6.query(ExpenseTransaction).filter(ExpenseTransaction.id == _x.id).update({"notes": "etez xarajat"})
            s6.commit()
        finally:
            s6.close()
    return _asl_tr(*a, **k)


services.get_transport_stats_for_period = _tr_yozuvli
try:
    _he0 = xotira_holati()
    _s = SessionLocal()
    try:
        _e1 = hisob(_s)
    finally:
        _s.close()
    _he1 = xotira_holati()
finally:
    services.get_transport_stats_for_period = _asl_tr
_s = SessionLocal()
try:
    _e2 = hisob(_s)
finally:
    _s.close()
_he2 = xotira_holati()
check("E1 hisob paytida yozuv bo'ldi — natija SAQLANMADI (saqlandi o'zgarmadi, hisoblandi oshdi)",
      _yozildi["n"] == 1 and _he1.get("saqlandi") == _he0.get("saqlandi") and _he1.get("hisoblandi", 0) > _he0.get("hisoblandi", 0),
      [_he0, _he1, _yozildi])
check("E2 keyingi chaqiruv qayta hisoblandi va saqlandi; natija = ASL",
      _he2.get("hisoblandi", 0) > _he1.get("hisoblandi", 0) and _he2.get("saqlandi", 0) > _he1.get("saqlandi", 0) and _e2 == asl_hisob(),
      [_he1, _he2])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. Qaytarilgan natijani o'zgartirish xotirani buzmaydi (har chaqiruvga alohida nusxa)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
xotira_tozala()
_s = SessionLocal()
try:
    _f1 = services.get_monthly_report(_s, Y, M, company_id=1)
    _f1_json = json.dumps(_f1, default=str, sort_keys=True)
    for _k in list(_f1.keys()):
        if isinstance(_f1[_k], list):
            _f1[_k].clear()
        elif isinstance(_f1[_k], dict):
            _f1[_k].clear()
        else:
            _f1[_k] = -1
    _f2 = services.get_monthly_report(_s, Y, M, company_id=1)
    _f2["daromad"] = -999
    _f3 = services.get_monthly_report(_s, Y, M, company_id=1)
finally:
    _s.close()
check("F1 birinchi natija va uning ichki ro'yxatlari buzildi → keyingilar xotiradan, lekin ASL holatda",
      json.dumps(_f3, default=str, sort_keys=True) == _f1_json and xotira_holati().get("topildi", 0) >= 2, xotira_holati())

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. Muddat: `HISOBOT_XOTIRASI_MUDDAT` dan eski yozuv ishlatilmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
xotira_tozala()
with bayroqlar(HISOBOT_XOTIRASI_MUDDAT=0.0):
    _s = SessionLocal()
    try:
        hisob(_s)
        hisob(_s)
    finally:
        _s.close()
    _hg = xotira_holati()
check("G1 muddat 0 — ikki chaqiruv ikkalasi hisoblandi (xotiradan olinmadi)", _hg.get("hisoblandi") == 2 and _hg.get("topildi") == 0, _hg)
check("G2 standart muddat — 60 s", getattr(services, "HISOBOT_XOTIRASI_MUDDAT", None) == 60.0)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Bir nechta ishchi (`WEB_CONCURRENCY` > 1) — xotira o'chiq (boshqa jarayon yozuvlarini ko'rmaydi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
xotira_tozala()
os.environ["WEB_CONCURRENCY"] = "2"
try:
    _s = SessionLocal()
    try:
        _w1 = hisob(_s)
        _w2 = hisob(_s)
    finally:
        _s.close()
    _hw = xotira_holati()
finally:
    os.environ.pop("WEB_CONCURRENCY", None)
check("H1 WEB_CONCURRENCY=2 — xotira ishlamadi (yozuvlar 0, topildi 0), natija = ASL",
      callable(getattr(services, "hisobot_xotirasi_holati", None)) and _hw.get("yozuvlar") == 0 and _hw.get("topildi") == 0
      and _w1 == _w2 == asl_hisob(), _hw)
os.environ["WEB_CONCURRENCY"] = "1"
try:
    xotira_tozala()
    _s = SessionLocal()
    try:
        hisob(_s)
        hisob(_s)
    finally:
        _s.close()
    _hw1 = xotira_holati()
finally:
    os.environ.pop("WEB_CONCURRENCY", None)
check("H2 WEB_CONCURRENCY=1 — xotira ishlaydi", _hw1.get("topildi") == 1, _hw1)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("I. Kalitlar: oy kesimi («shu kunlar» bilan taqqoslash) va korxona — alohida, har biri = ASL")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
xotira_tozala()
_kesim = getattr(database, "tashkent_oy_kesimi", None)
_ik = {}
_s = SessionLocal()
try:
    _ik["toliq"] = hisob(_s, PY, PM)
    if _kesim:
        with _kesim(PY, PM, 1):
            _ik["kesim1"] = hisob(_s, PY, PM)
    _ik["toliq2"] = hisob(_s, PY, PM)
    _ik["hammasi"] = hisob(_s, PY, PM, None)
finally:
    _s.close()
_hi = xotira_holati()
with bayroqlar(HISOBOT_XOTIRASI_YOQIQ=False):
    _s = SessionLocal()
    try:
        _ik_asl_kesim = None
        if _kesim:
            with _kesim(PY, PM, 1):
                _ik_asl_kesim = hisob(_s, PY, PM)
        _ik_asl_hammasi = hisob(_s, PY, PM, None)
    finally:
        _s.close()
check("I1 o'tgan oy to'liq va «1–1 kun» kesimi — ikki ALOHIDA yozuv, har biri = ASL; kesim to'liq oydan farq qiladi (27-kun ma'lumoti)",
      _ik.get("toliq") == asl_hisob(PY, PM) and _ik.get("kesim1") == _ik_asl_kesim and _ik.get("kesim1") != _ik.get("toliq")
      and _ik.get("toliq2") == _ik.get("toliq"), _hi)
check("I2 korxona: `company_id=None` (hamma) — alohida kalit, = ASL; yozuvlar soni 3 (to'liq, kesim, hamma)",
      _ik.get("hammasi") == _ik_asl_hammasi and _hi.get("yozuvlar") == 3 and _hi.get("topildi") == 1, _hi)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Brauzer: takroriy so'rov yo'q, Bosh sahifa 5 ta buyurtma, `bittaYuklash`, kirish rasmi, taqqoslash kartalari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def sahifa_sorovlari(url, kut=1500):
    del SOROVLAR[:]
    _SOR_ON["on"] = True
    try:
        PG.goto(B + url, wait_until="networkidle")
        PG.wait_for_timeout(kut)
    except Exception as ex:                # noqa: BLE001
        SOROVLAR.append(("XATO", f"{type(ex).__name__}: {str(ex)[:200]}"))
    finally:
        _SOR_ON["on"] = False
    return [x for x in SOROVLAR if x[1].startswith("/api/")]


if PG is not None:
    xotira_tozala()
    _konsol = []
    _kon_ush = (lambda m: _konsol.append(m.text[:200]) if m.type == "error" else None)
    PG.on("console", _kon_ush)
    _rq = sahifa_sorovlari("/reports", 2500)
    PG.remove_listener("console", _kon_ush)
    _hr = xotira_holati()
    _toldi = jsq(PG, """() => { const t = id => ((document.getElementById(id) || {}).textContent || '').trim();
        const ai = document.getElementById('aiSummary');
        return {comp: t('comp-daromad'), kpi_ch: t('kpi-daromad-ch'), oqim: t('kpi-oqim'), oqim_sub: t('kpi-oqim-sub'),
                pul_oqimi: t('cashFlowBars').slice(0, 40), ai: ai ? getComputedStyle(ai).display : null}; }""")
    check("K0 Hisobotlar sahifasi bir yuklashda TO'LIQ to'ldi (taqqoslash, KPI o'zgarishi, pul oqimi kartasi va bloki, «Oy xulosasi») — "
          "konsolda xato yo'q (eslab qolingan javobni ikkinchi o'quvchi ham o'qiy oladi)",
          isinstance(_toldi, dict) and _toldi.get("comp") not in ("", "—") and _toldi.get("kpi_ch") and _toldi.get("oqim") not in ("", "—")
          and "olingan" in (_toldi.get("oqim_sub") or "") and "Kirim" in (_toldi.get("pul_oqimi") or "") and _toldi.get("ai") == "flex"
          and not _konsol, [_toldi, _konsol[:3]])
    _sanoq = {}
    for _u, _p in _rq:
        _sanoq[(_u, _p)] = _sanoq.get((_u, _p), 0) + 1
    _ikki = {f"{k[0]} {k[1]}": v for k, v in _sanoq.items() if v > 1}
    check("K1 Hisobotlar sahifasi: hech bir API so'rovi IKKI marta yuborilmadi (ilgari taqqoslash 3, pul oqimi 2)", _rq and not _ikki,
          [_ikki, len(_rq)])
    check("K2 Hisobotlar: taqqoslash 1, pul oqimi 1 marta",
          sum(1 for _u, _p in _rq if _p.startswith("/api/reports/comparison")) == 1
          and sum(1 for _u, _p in _rq if _p.startswith("/api/finance/pul-oqimi")) == 1, _rq)
    check("L1 Hisobotlar sahifasi sovuq ochilishi: oylik hisob ≤ 4 marta (joriy, o'tgan (kesim), o'tgan, oldingi; ilgari 12)",
          isinstance(_hr.get("hisoblandi"), int) and 1 <= _hr["hisoblandi"] <= 4, _hr)
    _rk = sahifa_sorovlari("/kpi", 2000)
    _fr = [p for u, p in _rk if p.startswith("/api/finance/report")]
    check("K3 KPI sahifasi: `/api/finance/report` (joriy oy) 1 marta (ilgari 2)", len(_fr) == 1, _rk)
    _rh = sahifa_sorovlari("/", 1500)
    _ho = [p for u, p in _rh if p.startswith("/api/orders")]
    check("K4 Bosh sahifa: faqat `/api/orders?limit=5` (hammasi emas)", _ho == ["/api/orders?limit=5"], _rh)
    _so = jsq(PG, """() => [...document.querySelectorAll('#recentOrders a.list-row')].map(a => a.getAttribute('href'))""")
    _hammasi = jsonla(ol("/api/orders")[1])
    _kut5 = []
    if isinstance(_hammasi, list):
        _kut5 = [f"/orders?order={o['id']}" for o in sorted(_hammasi, key=lambda o: (o.get("created_at") or "", o["id"]), reverse=True)[:5]]
    check("K5 Bosh sahifa «So'nggi buyurtmalar» — 5 ta eng yangi (yaratilgan vaqt, teng bo'lsa id kamayishi)", _so == _kut5, [_so, _kut5])
    _l5 = jsonla(ol("/api/orders?limit=5")[1])
    check("K6 API `limit=5` = to'liq ro'yxatning eng yangi 5 tasi; `limit=0` / `limit=501` — 422; limitsiz — hammasi",
          isinstance(_l5, list) and [f"/orders?order={o['id']}" for o in _l5] == _kut5 and ol("/api/orders?limit=0")[0] == 422
          and ol("/api/orders?limit=501")[0] == 422 and isinstance(_hammasi, list) and len(_hammasi) >= 6,
          [len(_l5) if isinstance(_l5, list) else _l5, ol("/api/orders?limit=0")[0], ol("/api/orders?limit=501")[0],
           len(_hammasi) if isinstance(_hammasi, list) else _hammasi])
    # `bittaYuklash` — HAQIQIY brauzerda: blok ichida bir xil GET bir marta (har o'quvchi o'z nusxasini o'qiydi); yozuv so'rovi tozalaydi;
    # blokdan tashqarida — oddiy fetch
    del SOROVLAR[:]
    _SOR_ON["on"] = True
    try:
        _by = jsq(PG, """async () => {
          if (typeof bittaYuklash !== 'function') return {yoq: true};
          const n = await bittaYuklash(async () => {
            const [a, b] = await Promise.all([fetch('/api/inventory'), fetch('/api/inventory')]);
            const ta = await a.text(), tb = await b.text();
            const c = await (await fetch('/api/inventory')).text();
            await fetch('/api/etez-yoq-manzil', {method: 'POST'}).catch(() => null);
            const d = await (await fetch('/api/inventory')).text();
            return {ta: ta.length, tb: tb.length, td: d.length, teng: ta === tb && tb === c, json: Array.isArray(JSON.parse(d))};
          });
          await fetch('/api/inventory'); await fetch('/api/inventory');
          return n;
        }""")
    finally:
        _SOR_ON["on"] = False
    _bn = [p for u, p in SOROVLAR if p == "/api/inventory"]
    check("K7 `bittaYuklash`: blok ichida 3 ta bir xil GET → 1 so'rov, yozuv so'rovidan keyin → yana 1; blokdan tashqarida 2 → 2 (jami 4); "
          "hamma o'quvchi to'liq javob oldi", isinstance(_by, dict) and _by.get("teng") and _by.get("ta", 0) > 100 and _by.get("json")
          and len(_bn) == 4,
          [_by, len(_bn), SOROVLAR[:8]])
    # Kirish sahifasi foni
    _ctx2 = br.new_context(viewport={"width": 1280, "height": 800})
    _p2 = _ctx2.new_page()
    _rasm_sor = []
    _p2.on("response", lambda r: _rasm_sor.append((r.url.replace(B, ""), r.status)) if "login-bg" in r.url else None)
    try:
        _p2.goto(B + "/login", wait_until="networkidle")
    except Exception as _e:                # noqa: BLE001
        _rasm_sor.append(("XATO", str(_e)[:200]))
    _fon = jsq(_p2, "() => { const s = document.querySelector('.side'); return s ? getComputedStyle(s).backgroundImage : null; }")
    _ctx2.close()
    check("K8 kirish sahifasi: fon — `login-bg.webp` (Chromium image-set), 200; `login-bg.png` so'ralmadi",
          _fon and "login-bg.webp" in _fon and ("/static/login-bg.webp", 200) in _rasm_sor and not any("login-bg.png" in u for u, s_ in _rasm_sor),
          [_fon, _rasm_sor])
    _lg = jsq(PG, """async () => { await new Promise(r => setTimeout(r, 300)); const i = document.querySelector('.s-logo img');
                         return i ? {src: i.getAttribute('src'), w: i.naturalWidth, h: i.naturalHeight} : null; }""")
    check("K9 chap panel logotipi — 128 × 128 (yuklandi)", _lg and _lg.get("src") == "/static/logo_round_128.jpg" and _lg.get("w") == 128, _lg)

    # K120-1: taqqoslash kartalari — eng uzun matnlar bilan, 360–1440 px
    KARTA_JS = r"""async () => {
      const q = id => document.getElementById(id);
      for (let i = 0; i < 40 && !(q('comp-daromad') && q('comp-daromad').textContent.trim() !== '—'); i++) await new Promise(r => setTimeout(r, 100));
      q('comp-daromad').textContent = "o'zgarmadi";
      q('comp-jami_xarajat').innerHTML = '<i class="ti ti-arrow-up-right"></i> 1 234,5%';
      q('comp-sof_foyda').textContent = "o'tgan oyda ma'lumot yo'q";
      q('comp-foyda_foiz').textContent = "o'zgarmadi";
      await new Promise(r => setTimeout(r, 120));
      const g = q('compGrid'); const p = g.parentElement; const ps = getComputedStyle(p); const vw = innerWidth;
      const pr = p.getBoundingClientRect();
      const ichki_o = pr.right - parseFloat(ps.paddingRight) - parseFloat(ps.borderRightWidth);
      const kartalar = [...g.children].map(c => { const r = c.getBoundingClientRect(); const a = c.querySelector('.bi-comp-arrow');
        const l = c.querySelector('.bi-comp-label'); const cs = getComputedStyle(a); const fs = parseFloat(cs.fontSize);
        const lh = parseFloat(cs.lineHeight) || fs * 1.25;
        return {l: Math.round(r.left * 10) / 10, r: Math.round(r.right * 10) / 10, sw: c.scrollWidth, cw: c.clientWidth, a_sw: a.scrollWidth,
                a_cw: a.clientWidth, l_sw: l.scrollWidth, l_cw: l.clientWidth, qator: Math.round(a.getBoundingClientRect().height / lh),
                fs, t: a.textContent.trim()}; });
      const w = document.querySelector('.bi-wrap');
      return {vw, ichki_o: Math.round(ichki_o * 10) / 10, hujjat: document.documentElement.scrollWidth,
              wrap: w ? [w.clientWidth, w.scrollWidth] : null, kartalar};
    }"""
    _kr = {}
    for _w in (360, 375, 390, 768, 1024, 1280, 1440):
        _tel = _w < 768
        _c3 = br.new_context(viewport={"width": _w, "height": 900 if _w >= 1000 else 800}, device_scale_factor=1, is_mobile=_tel,
                             has_touch=_tel, timezone_id="Asia/Tashkent", locale="uz-UZ")
        _c3.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                             r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
        _c3.add_cookies(CTX.cookies())
        _p3 = _c3.new_page()
        try:
            _p3.goto(B + "/reports", wait_until="networkidle")
            _kr[_w] = jsq(_p3, KARTA_JS)
        except Exception as _e:            # noqa: BLE001
            _kr[_w] = {"istisno": f"{type(_e).__name__}: {str(_e)[:200]}"}
        _c3.close()
    for _w, _m in _kr.items():
        _ks = _m.get("kartalar") or []
        _yomon = [k for k in _ks if k["r"] > _m.get("ichki_o", 0) + 0.5 or k["sw"] > k["cw"] + 1 or k["a_sw"] > k["a_cw"] + 1
                  or k["l_sw"] > k["l_cw"] + 1]
        check(f"K10 {_w} px: 4 karta panel ichida (o'ng chet ≤ panel ichki cheti), karta / yozuv o'z qutisidan chiqmaydi, sahifa va "
              f"panel yon tomonga surilmaydi", len(_ks) == 4 and not _yomon and _m.get("hujjat", 9e9) <= _m.get("vw", 0)
              and _m.get("wrap") and _m["wrap"][1] <= _m["wrap"][0] + 1, [_yomon, _m.get("ichki_o"), _m.get("wrap"), _m.get("hujjat")])
        _oz = [k for k in _ks if k["t"] in ("o'zgarmadi", "1 234,5%")]
        check(f"K11 {_w} px: «o'zgarmadi» va «1 234,5%» BIR qatorda (so'z bo'linmaydi), yozuv ≥ 16 px",
              len(_oz) == 3 and all(k["qator"] == 1 and k["fs"] >= 16 for k in _oz), _oz)

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
