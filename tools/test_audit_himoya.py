#!/usr/bin/env python3
"""
test_audit_himoya.py — kech143 (zip 171): AUDIT — HIMOYA QATLAMI (A-X04, A-X05, A-X06, A-X08, A-X09) va jonli topilma N1
(material nomi katta-kichik harf).

NIMA UCHUN KERAK (har biri O'LCHANGAN — asl kod zip 170, `work/audit/tasdiq/himoya/p_himoya.py`, SQLite = PG):
  A-X04 Server so'rov QAYSI saytdan kelganini tekshirmasdi (himoya — faqat cookie `SameSite=Lax`): Origin=evil +
        Sec-Fetch-Site=cross-site POST, tanasiz DELETE — 200; boshqa saytdagi `/logout` havolasi (yuqori darajali o'tish —
        Lax cookie yuboriladi) foydalanuvchini tizimdan chiqarardi.
  A-X05 EGASI QARORI (13.10 «Sotuv o'tadi, sizga xabar»): «Tannarx va foyda» ruxsati yo'q menejer tannarxdan past narx
        ogohlantirishidan aniq tannarxni bilib olardi (1 233 — «past», 1 234 — «yaxshi»). Endi unga ogohlantirish yo'q, sotuv
        o'tadi, «Faoliyat jurnali» va Telegram ga TANNARXSIZ xabar; admin — avvalgidek ogohlantirish.
  A-X06 Hodim QR sahifasi `manzil=` da istalgan xostni qabul qilardi (chop etilgan QR begona saytga, korxona kodi bilan).
  A-X08 Bitta IP dan 5 xato urinish istalgan hisobni (platforma egasini, hodim telefonini ham) HAMMA joydan 15 daqiqaga
        yopardi. Endi (login, IP) — 5, IP — 20, login jami — 30 (tanish IP — oxirgi 30 kunda muvaffaqiyatli kirgan — ozod).
  A-X09 CRON siri faqat manzilda va `!=`; sessiya tokeni bazada XOM; eski tuzsiz SHA-256 parol / PIN xeshi (egasi kirmaguncha)
        bazada qolardi.
  N1    «Oq mel» / «oq mel» / «Oq  mel» / «Bo'yoq» — «Boʻyoq» / «МЕЛ» — «мел» — ALOHIDA materiallar bo'lib yaratilardi; boshqa
        material nomiga harf farqi bilan qayta nomlash o'tardi.
BO'LIMLAR: A — manba (A-X04); B — tannarxdan past sotuv (A-X05); C — hodim QR (A-X06); D — kirish cheklovi (A-X08);
  E — cron, sessiya tokeni, eski xesh (A-X09); F — material nomi kaliti (N1); X — 5xx yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (parallel nom poygasi faqat PG da). Asl kodga qarshi QULAMAYDI
  (yangi nomlar — `getattr`).
ISHLATISH: python3 tools/test_audit_himoya.py
"""
import os
import sys
import time
import hashlib
import tempfile
import threading
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "audit_himoya_test"
_T = tempfile.mkdtemp(prefix="audit_himoya_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'audit_himoya_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "RESET_ADMIN_PASSWORD", "TELEGRAM_WEBHOOK_SECRET"):
    os.environ.pop(_k, None)
os.environ["CRON_SECRET"] = "himoya-cron-143"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, UserSession, EmployeeSession, Employee, Inventory,  # noqa: E402
                    LoginHistory, ActivityLog, FinishedProduct, StockSource, ProductionStatus)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HOLATLAR = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
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


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.headers = {}
        self.cookies = {}

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    HOLATLAR.append((metod.upper() + " " + url.split("?")[0], r.status_code))
    return r


def xav(fn, standart=None):
    """Bitta qadam yiqilsa butun test qulamasin."""
    try:
        return fn()
    except Exception as e:                 # noqa: BLE001
        print(f"    (qadam yiqildi: {type(e).__name__}: {str(e)[:300]})")
        return standart


PAROL = "Parol123!"
with TestClient(main.app, base_url="https://testserver") as _c0:      # startup (jadvallar, migratsiyalar, standart admin)
    _c0.get("/login")

db = SessionLocal()
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="Himoya B", code="HIMB"))
db.get(Company, 1).code = "HIMA"
db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    for _u, _rol, _cid in (("h_admin", UserRole.ADMIN, 1), ("h_egasi", UserRole.ADMIN, 1), ("h_men", UserRole.MANAGER, 1),
                           ("h_b_admin", UserRole.ADMIN, 2), ("h_qurbon", UserRole.ADMIN, 1), ("h_tanish", UserRole.ADMIN, 1),
                           ("h_ip_a", UserRole.ADMIN, 1), ("h_ip_b", UserRole.ADMIN, 1), ("h_eski", UserRole.ADMIN, 1),
                           ("h_parol", UserRole.ADMIN, 1), ("h_none", UserRole.ADMIN, 1)):
        auth.create_user(db, _u, PAROL, _rol, _u.upper(), company_id=_cid)
db.query(User).filter(User.is_platform_admin == True).update({User.is_platform_admin: False})   # noqa: E712
db.query(User).filter(User.username == "h_egasi").update({User.is_platform_admin: True})
db.commit()
db.close()

_IP_N = [0]


def yangi_ip():
    _IP_N[0] += 1
    return f"198.51.{100 + _IP_N[0] // 250}.{_IP_N[0] % 250 + 1}"


def mijoz(ip=None, base="https://testserver"):
    ip = ip or yangi_ip()
    try:
        return TestClient(main.app, base_url=base, raise_server_exceptions=False, client=(ip, 50000))
    except TypeError:                      # eski Starlette — `client=` yo'q
        return TestClient(main.app, base_url=base, raise_server_exceptions=False)


def kir(c, login, parol=PAROL, **k):
    return req(c, "post", "/login", data={"username": login, "password": parol}, follow_redirects=False, **k)


def kirdimi(r):
    return r.status_code in (302, 303) and "session_token" in (r.headers.get("set-cookie") or "")


def ishlaydimi(c):
    return req(c, "get", "/api/inventory").status_code


ADM = mijoz("203.0.113.1")
check("S0 admin kirdi", kirdimi(kir(ADM, "h_admin")))
MAQSAD = getattr(main, "MANBA_RAD_XABARI", None)
_TG = []
main._send_telegram = lambda matn, company_id=None: _TG.append((matn, company_id))    # Telegram — yozib olinadi


def material_soni(nom):
    d = SessionLocal()
    try:
        return d.query(Inventory).filter(Inventory.company_id == 1, Inventory.item_name == nom).count()
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════
section("A. Boshqa saytdan kelgan yozuvchi so'rov (A-X04)")
# ══════════════════════════════════════════════════════════════
_mr = getattr(main, "manba_rad_sababi", None)


def mr(usul, yol, sar):
    if _mr is None:
        return "YO'Q: main.manba_rad_sababi (asl kod)"
    return _mr(usul, yol, sar)


_TS = {"host": "testserver"}
HOLLAR = [
    ("A1a GET (cross-site ham) — o'tadi", "GET", "/api/x", {"sec-fetch-site": "cross-site", **_TS}, False),
    ("A1b POST same-origin — o'tadi", "POST", "/api/x", {"sec-fetch-site": "same-origin", **_TS}, False),
    ("A1c POST none (foydalanuvchi o'zi) — o'tadi", "POST", "/api/x", {"sec-fetch-site": "none", **_TS}, False),
    ("A1d POST cross-site — rad", "POST", "/api/x", {"sec-fetch-site": "cross-site", **_TS}, True),
    ("A1e POST same-site (qo'shni subdomen) — rad", "POST", "/api/x", {"sec-fetch-site": "same-site", **_TS}, True),
    ("A1f Sec-Fetch-Site yo'q, Origin o'z xosti — o'tadi", "POST", "/api/x", {"origin": "https://testserver", **_TS}, False),
    ("A1g Sec-Fetch-Site yo'q, Origin begona — rad", "POST", "/api/x", {"origin": "https://evil.example", **_TS}, True),
    ("A1h Origin «null» — rad", "POST", "/api/x", {"origin": "null", **_TS}, True),
    ("A1i ikkalasi yo'q (cron, Telegram, test mijozi) — o'tadi", "POST", "/api/x", dict(_TS), False),
    ("A1j DELETE begona Origin — rad", "DELETE", "/api/x/1", {"origin": "https://evil.example", **_TS}, True),
    ("A1k PUT / PATCH begona Origin — rad", "PATCH", "/api/x/1", {"origin": "https://evil.example", **_TS}, True),
    ("A1l Telegram webhook (cross-site bo'lsa ham) — istisno", "POST", "/telegram/webhook", {"sec-fetch-site": "cross-site", **_TS}, False),
    ("A1m korxona webhooki /telegram/webhook/2 — istisno", "POST", "/telegram/webhook/2", {"origin": "https://evil.example", **_TS}, False),
    ("A1n «/telegram/webhookX» — istisno EMAS", "POST", "/telegram/webhookX", {"sec-fetch-site": "cross-site", **_TS}, True),
    ("A1o Origin xosti katta harf bilan — o'tadi", "POST", "/api/x", {"origin": "https://TestServer", **_TS}, False),
    ("A1p Origin porti boshqa — rad", "POST", "/api/x", {"origin": "https://testserver:8443", **_TS}, True),
    ("A1q Sec-Fetch-Site same-origin ustun (Origin begona bo'lsa ham)", "POST", "/api/x",
     {"sec-fetch-site": "same-origin", "origin": "https://evil.example", **_TS}, False),
    ("A1r Sec-Fetch-Site cross-site ustun (Origin o'zi bo'lsa ham)", "POST", "/api/x",
     {"sec-fetch-site": "cross-site", "origin": "https://testserver", **_TS}, True),
    ("A1s Host sarlavhasi yo'q, Origin bor — rad", "POST", "/api/x", {"origin": "https://testserver"}, True),
]
for nom, usul, yol, sar, rad in HOLLAR:
    _n = xav(lambda: mr(usul, yol, sar), "ISTISNO")
    check(nom, (isinstance(_n, str) and not _n.startswith("YO'Q") and _n != "ISTISNO") if rad else (_n is None), _n)

_r = req(ADM, "post", "/api/inventory", json={"item_name": "A2 material", "unit": "kg", "min_stock": 0},
         headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
check("A2 POST /api/inventory boshqa saytdan — 403, sababi bilan, material YARATILMADI (asl: 200, yaratilardi)",
      _r.status_code == 403 and MAQSAD and js(_r).get("detail") == MAQSAD and material_soni("A2 material") == 0,
      (_r.status_code, js(_r), material_soni("A2 material")))
check("A2b 403 javobida xavfsizlik sarlavhalari (nosniff, DENY)",
      _r.status_code == 403 and _r.headers.get("x-content-type-options") == "nosniff"
      and _r.headers.get("x-frame-options") == "DENY", dict(_r.headers))
_r = req(ADM, "post", "/api/inventory", json={"item_name": "A3 material", "unit": "kg", "min_stock": 0},
         headers={"Origin": "https://testserver", "Sec-Fetch-Site": "same-origin"})
A3_ID = js(_r).get("id")
check("A3 o'z saytidan (same-origin) — 200, yaratildi", _r.status_code == 200 and material_soni("A3 material") == 1,
      (_r.status_code, js(_r)))
_r = req(ADM, "delete", f"/api/inventory/{A3_ID}", headers={"Origin": "https://evil.example"})
check("A4 tanasiz DELETE begona Origin bilan — 403, material joyida (asl: 200, o'chirilardi)",
      _r.status_code == 403 and material_soni("A3 material") == 1, (_r.status_code, js(_r)))
_r = req(ADM, "delete", f"/api/inventory/{A3_ID}", headers={"Origin": "https://testserver"})
check("A4b o'sha DELETE o'z Origin i bilan — 200", _r.status_code == 200, (_r.status_code, js(_r)))
_r = req(ADM, "get", "/api/inventory", headers={"Sec-Fetch-Site": "cross-site"})
check("A5 o'qish (GET) boshqa saytdan ham — 200 (CORS javobni o'qitmaydi; GET holat o'zgartirmaydi)", _r.status_code == 200,
      _r.status_code)
_l = mijoz()
_r = req(_l, "post", "/login", data={"username": "h_admin", "password": PAROL}, follow_redirects=False,
         headers={"Origin": "https://evil.example"})
check("A6 kirish formasi boshqa saytdan — 403 matn (sessiya berilmadi)", _r.status_code == 403
      and "session_token" not in (_r.headers.get("set-cookie") or "") and MAQSAD and MAQSAD in (_r.text or ""),
      (_r.status_code, (_r.text or "")[:200]))
_r = req(_l, "post", "/login", data={"username": "h_admin", "password": PAROL}, follow_redirects=False,
         headers={"Origin": "https://testserver", "Sec-Fetch-Site": "same-origin"})
check("A6b kirish formasi o'z saytidan — 302", kirdimi(_r), _r.status_code)

L = mijoz()
kir(L, "h_admin")
_r = req(L, "get", "/logout", headers={"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate"}, follow_redirects=False)
check("A7 boshqa saytdagi «/logout» havolasi — CHIQARMAYDI (302 → /), sessiya ishlaydi (asl: chiqarardi)",
      _r.status_code == 302 and _r.headers.get("location") == "/" and ishlaydimi(L) == 200,
      (_r.status_code, _r.headers.get("location"), ishlaydimi(L)))
_r = req(L, "get", "/logout", headers={"Sec-Fetch-Site": "same-site"}, follow_redirects=False)
check("A7b same-site havola ham chiqarmaydi", _r.status_code == 302 and ishlaydimi(L) == 200,
      (_r.status_code, ishlaydimi(L)))
_r = req(L, "get", "/logout", headers={"Sec-Fetch-Site": "same-origin"}, follow_redirects=False)
check("A7c o'z sahifasidagi «Chiqish» (same-origin) — chiqaradi (302 → /login), sessiya 401",
      _r.status_code == 302 and _r.headers.get("location") == "/login" and ishlaydimi(L) == 401,
      (_r.status_code, _r.headers.get("location"), ishlaydimi(L)))
L2 = mijoz()
kir(L2, "h_admin")
_r = req(L2, "get", "/logout", headers={"Sec-Fetch-Site": "none"}, follow_redirects=False)
check("A7d manzilni o'zi yozgan (none) — chiqaradi", _r.status_code == 302 and ishlaydimi(L2) == 401,
      (_r.status_code, ishlaydimi(L2)))
L3 = mijoz()
kir(L3, "h_admin")
_r = req(L3, "get", "/logout", follow_redirects=False)
check("A7e sarlavhasiz (eski brauzer / test) — chiqaradi (avvalgidek)", _r.status_code == 302 and ishlaydimi(L3) == 401,
      (_r.status_code, ishlaydimi(L3)))
# hodim paneli: telefon kaliti (cookie) + sessiya — `auth.hodim_holati` qoidasi bilan
_kalit9 = "k" * 43
_d = SessionLocal()
try:
    _e9 = Employee(company_id=1, name="A9 Hodim", position="Kesuvchi", phone="+998901439999", pin_hash=auth.hash_pin("4826"),
                   qurilma_hash=auth.qurilma_hash_ol(_kalit9), pin_vaqtinchalik=False)
    _d.add(_e9)
    _d.commit()
    _et9 = auth.create_employee_session(_d, _e9.id, qurilma_hash=auth.qurilma_hash_ol(_kalit9))
finally:
    _d.close()
HC = mijoz()
HC.cookies.set("emp_session_token", _et9, domain="testserver.local")
HC.cookies.set(auth.QURILMA_COOKIE, _kalit9, domain="testserver.local")


def hodim_sessiyasi_bormi():
    _s = SessionLocal()
    try:
        return auth.get_employee_session(_s, _et9) is not None
    finally:
        _s.close()


_h0 = req(HC, "get", "/hodim", follow_redirects=False).status_code
_r = req(HC, "get", "/hodim/logout", headers={"Sec-Fetch-Site": "cross-site"}, follow_redirects=False)
check("A9a boshqa saytdagi «/hodim/logout» havolasi — hodim CHIQMAYDI (302 → /hodim), sessiya joyida (asl: chiqarardi)",
      _h0 == 200 and _r.status_code == 302 and _r.headers.get("location") == "/hodim" and hodim_sessiyasi_bormi(),
      (_h0, _r.status_code, _r.headers.get("location"), hodim_sessiyasi_bormi()))
_r = req(HC, "get", "/hodim/logout", headers={"Sec-Fetch-Site": "same-origin"}, follow_redirects=False)
check("A9b hodim panelidagi «Chiqish» (same-origin) — chiqaradi (302 → /hodim/login), sessiya yo'q",
      _r.status_code == 302 and _r.headers.get("location") == "/hodim/login" and not hodim_sessiyasi_bormi(),
      (_r.status_code, _r.headers.get("location"), hodim_sessiyasi_bormi()))
_r = req(mijoz(), "post", "/telegram/webhook", json={"update_id": 1}, headers={"Sec-Fetch-Site": "cross-site"})
check("A8 Telegram webhook cross-site sarlavha bilan — manba qatlami TO'XTATMAYDI (o'z sir tekshiruvi ishlaydi)",
      not (_r.status_code == 403 and MAQSAD and MAQSAD in (_r.text or "")) and _r.status_code in (403, 503),
      (_r.status_code, (_r.text or "")[:200]))

# ══════════════════════════════════════════════════════════════
section("B. Tannarxdan past sotuv — tannarx ruxsatisiz menejer (A-X05, egasi qarori)")
# ══════════════════════════════════════════════════════════════


def tm(nom, tannarx=1234.0, miqdor=100.0, taqdir=None):
    d = SessionLocal()
    try:
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=False, quantity=miqdor,
                             produced_quantity=miqdor, unit="metr", unit_price=0, cost_price=tannarx * miqdor,
                             source=StockSource.RETURNED, production_status=ProductionStatus.READY, reserved_quantity=0,
                             unit_cost_stable=tannarx)
        if taqdir:
            fp.brak_taqdir = taqdir
        d.add(fp)
        d.commit()
        return fp.id
    finally:
        d.close()


def jurnal(amal="tannarxdan_past_sotuv"):
    d = SessionLocal()
    try:
        return [(a.entity_label, a.performed_by, a.new_value, a.company_id)
                for a in d.query(ActivityLog).filter(ActivityLog.action == amal).order_by(ActivityLog.id).all()]
    finally:
        d.close()


def ichki(r):
    b = js(r)
    return b.get("detail") if isinstance(b.get("detail"), dict) else b


MEN = mijoz("203.0.113.3")
check("B0 menejer kirdi; «Tannarx va foyda» ruxsati yo'q", kirdimi(kir(MEN, "h_men"))
      and not __import__("ruxsatlar").bormi(SessionLocal().query(User).filter(User.username == "h_men").first(),
                                            "tannarx", "korish"))
FP1 = tm("B Profil savatcha")
_j0, _t0 = len(jurnal()), len(_TG)
_r = req(MEN, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": FP1, "quantity": 1, "unit_price": 1233}],
                                                        "buyer_name": "B xaridor", "payment_method": "naqd"})
_b = js(_r)
check("B1 menejer savatcha 1 233 so'm (tannarx 1 234) — 200, ogohlantirish YO'Q, javobda «tannarxdan_past» ham yo'q "
      "(asl: 400 below_cost_warning — tannarx oshkor)",
      _r.status_code == 200 and "type" not in _b and "tannarxdan_past" not in _b and "below_cost" not in (_r.text or ""),
      (_r.status_code, _b))
_jr = jurnal()
check("B2 «Faoliyat jurnali»: «tannarxdan_past_sotuv» — mahsulot, sotuvchi, miqdor × narx; TANNARX (1 234) YO'Q",
      len(_jr) == _j0 + 1 and _jr[-1][0] == "B Profil savatcha" and _jr[-1][1] == "H_MEN" and "1 233" in (_jr[-1][2] or "")
      and "1234" not in (_jr[-1][2] or "") and "1 234" not in (_jr[-1][2] or "") and _jr[-1][3] == 1, _jr[-2:])
check("B3 Telegram xabari: «Tannarxdan past narxda sotuv», mahsulot, sotuvchi, xaridor; tannarxsiz; o'z korxonasiga",
      len(_TG) == _t0 + 1 and "Tannarxdan past" in _TG[-1][0] and "B Profil savatcha" in _TG[-1][0] and "H_MEN" in _TG[-1][0]
      and "B xaridor" in _TG[-1][0] and "1 234" not in _TG[-1][0] and "1234" not in _TG[-1][0] and _TG[-1][1] == 1,
      _TG[-1:])
_j0, _t0 = len(jurnal()), len(_TG)
_r = req(MEN, "post", "/api/finished/sell", json={"finished_product_id": FP1, "quantity": 2, "unit_price": 1000,
                                                  "buyer_name": "B2 xaridor", "payment_method": "naqd"})
check("B4 menejer bitta sotuv 1 000 so'm — 200, ogohlantirishsiz; jurnal + Telegram (asl: 400)",
      _r.status_code == 200 and "type" not in js(_r) and "tannarxdan_past" not in js(_r) and len(jurnal()) == _j0 + 1
      and len(_TG) == _t0 + 1 and "2 metr" in (jurnal()[-1][2] or ""), (_r.status_code, js(_r), jurnal()[-1:]))
_j0, _t0 = len(jurnal()), len(_TG)
_r1 = req(MEN, "post", "/api/finished/sell", json={"finished_product_id": FP1, "quantity": 1, "unit_price": 1234,
                                                   "payment_method": "naqd"})
_r2 = req(MEN, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": FP1, "quantity": 1, "unit_price": 1500}],
                                                         "payment_method": "naqd"})
check("B5 tannarxga teng / yuqori narx — 200, jurnal va Telegram YO'Q", _r1.status_code == 200 and _r2.status_code == 200
      and len(jurnal()) == _j0 and len(_TG) == _t0, (_r1.status_code, _r2.status_code, len(jurnal()) - _j0, len(_TG) - _t0))
_r = req(ADM, "post", "/api/finished/sell", json={"finished_product_id": FP1, "quantity": 1, "unit_price": 1233,
                                                  "payment_method": "naqd"})
check("B6 ADMIN (tannarx ko'radi) 1 233 — avvalgidek 400 below_cost_warning", _r.status_code == 400
      and (ichki(_r) or {}).get("type") == "below_cost_warning", (_r.status_code, js(_r)))
_j0, _t0 = len(jurnal()), len(_TG)
_r = req(ADM, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": FP1, "quantity": 1, "unit_price": 1233}],
                                                        "payment_method": "naqd", "confirm_below_cost": True})
check("B6b admin «Baribir sotish» (tasdiq) — 200, «tannarxdan past» jurnali YO'Q (o'zi ko'rib qaror qildi)",
      _r.status_code == 200 and len(jurnal()) == _j0 and len(_TG) == _t0, (_r.status_code, js(_r)))
_j0 = len(jurnal())
_r = req(MEN, "post", "/api/finished/sell", json={"finished_product_id": FP1, "quantity": 1, "unit_price": 900,
                                                  "payment_method": "naqd", "confirm_below_cost": True})
check("B7 menejer tasdiq belgisini o'zi yuborsa ham — sotuv jurnalga yoziladi (aylanib o'tib bo'lmaydi)",
      _r.status_code == 200 and len(jurnal()) == _j0 + 1, (_r.status_code, len(jurnal()) - _j0))
FP2 = tm("B 2-nav", taqdir="ikkinchi_nav")
_j0 = len(jurnal())
_r = req(MEN, "post", "/api/finished/sell", json={"finished_product_id": FP2, "quantity": 1, "unit_price": 100,
                                                  "payment_method": "naqd"})
check("B8 2-nav (brakdan) arzon sotuv — jurnalga «tannarxdan past» yozilmaydi (egasi qarori Q2 — tabiiy)",
      _r.status_code == 200 and len(jurnal()) == _j0, (_r.status_code, len(jurnal()) - _j0))
FP3 = tm("B Ikkinchi mahsulot", tannarx=500)
_j0, _t0 = len(jurnal()), len(_TG)
_r = req(MEN, "post", "/api/finished/sell-batch", json={"items": [
    {"finished_product_id": FP1, "quantity": 1, "unit_price": 1100},
    {"finished_product_id": FP3, "quantity": 3, "unit_price": 600}], "payment_method": "naqd"})
check("B9 savatchada bitta past + bitta yaxshi — jurnalda FAQAT past qator, bitta Telegram xabari bitta qator bilan",
      _r.status_code == 200 and len(jurnal()) == _j0 + 1 and jurnal()[-1][0] == "B Profil savatcha" and len(_TG) == _t0 + 1
      and "B Ikkinchi mahsulot" not in _TG[-1][0], (_r.status_code, jurnal()[-2:], _TG[-1:]))
_d = SessionLocal()
try:
    with contextlib.redirect_stdout(io.StringIO()):
        import schemas as _sch
        _nat = crud.sell_finished_product(_d, _sch.FinishedProductSaleCreate(finished_product_id=FP1, quantity=1, unit_price=10),
                                          created_by="t", company_id=1)
finally:
    _d.close()
check("B10 crud ni to'g'ridan chaqirish (standart — tannarx ko'rinadi) — avvalgidek ogohlantirish",
      _nat.get("success") is False and _nat.get("type") == "below_cost_warning", _nat)
_c = SessionLocal().query(ActivityLog).filter(ActivityLog.action == "tannarxdan_past_sotuv").count()
check("B11 jurnal amali nomi ro'yxatda (`crud.AUDIT_AMALLARI`)", "tannarxdan_past_sotuv" in getattr(crud, "AUDIT_AMALLARI", {})
      and _c >= 4, _c)

# ══════════════════════════════════════════════════════════════
section("C. Hodim QR sahifasi — faqat o'z sayti (A-X06)")
# ══════════════════════════════════════════════════════════════
_r = req(ADM, "get", "/users/hodim-qr?manzil=https://evil.example")
check("C1 manzil=evil.example — sahifada begona xost YO'Q, o'z sayti bor (asl: evil.example/hodim?k=HIMA)",
      _r.status_code == 200 and "evil.example" not in (_r.text or "") and "https://testserver/hodim?k=HIMA" in (_r.text or ""),
      (_r.status_code, "evil.example" in (_r.text or "")))
_r = req(ADM, "get", "/users/hodim-qr?manzil=https://testserver")
check("C2 manzil = o'z sayti — olinadi", "https://testserver/hodim?k=HIMA" in (_r.text or ""), _r.status_code)
_r = req(ADM, "get", "/users/hodim-qr?manzil=https://testserver.evil.example")
check("C3 o'z nomi bilan boshlanadigan begona xost — olinmaydi", "evil" not in (_r.text or ""), _r.status_code)
_s1 = req(ADM, "get", "/api/hodim-qr.svg?manzil=https://evil.example").text
_s2 = req(ADM, "get", "/api/hodim-qr.svg?manzil=https://testserver").text
_s3 = req(ADM, "get", "/api/hodim-qr.svg").text
check("C4 QR rasmi (svg) begona manzil bilan = o'z sayti QR i (ichida evil yo'q)", _s1 == _s2 == _s3 and "<svg" in _s1,
      (len(_s1), len(_s2), len(_s3)))
from starlette.requests import Request as _SR    # noqa: E402


def qr_manzil(sarlavhalar, manzil=""):
    """`main._hodim_kirish_manzili` — Railway dagi kabi so'rov: ilova http ko'radi (uvicorn proksi sarlavhalariga ishonmaydi),
    `Host` — ommaviy domen (jonli o'lchov 13.10)."""
    scope = {"type": "http", "method": "GET", "path": "/users/hodim-qr", "query_string": b"", "scheme": "http",
             "server": ("10.0.0.5", 8080), "client": ("100.64.0.2", 5555),
             "headers": [(k.lower().encode("latin1"), v.encode("latin1")) for k, v in sarlavhalar.items()]}
    try:
        return main._hodim_kirish_manzili(_SR(scope), manzil, "KOD")
    except Exception as e:                 # noqa: BLE001
        return f"ISTISNO {type(e).__name__}: {e}"


_RW = {"host": "web-sinov.up.railway.app"}
check("C5 Railway: manzilsiz, X-Forwarded-Proto https — https://web-sinov.up.railway.app/hodim?k=KOD",
      qr_manzil({**_RW, "x-forwarded-proto": "https"}) == "https://web-sinov.up.railway.app/hodim?k=KOD",
      qr_manzil({**_RW, "x-forwarded-proto": "https"}))
check("C6 Railway: brauzer manzili (o'z domeni, https) — olinadi",
      qr_manzil(_RW, "https://web-sinov.up.railway.app") == "https://web-sinov.up.railway.app/hodim?k=KOD",
      qr_manzil(_RW, "https://web-sinov.up.railway.app"))
check("C7 Railway: begona manzil — o'z domeni bilan almashadi (asl: https://evil.example/hodim?k=KOD)",
      qr_manzil({**_RW, "x-forwarded-proto": "https"}, "https://evil.example") == "https://web-sinov.up.railway.app/hodim?k=KOD",
      qr_manzil({**_RW, "x-forwarded-proto": "https"}, "https://evil.example"))
check("C8 proksi sarlavhasisiz — so'rov sxemasi (http)", qr_manzil(_RW) == "http://web-sinov.up.railway.app/hodim?k=KOD",
      qr_manzil(_RW))

# ══════════════════════════════════════════════════════════════
section("D. Kirish cheklovi — hujumchi boshqalarni yopa olmaydi (A-X08)")
# ══════════════════════════════════════════════════════════════
HUJ = "198.18.0.66"
for _ in range(5):
    kir(mijoz(HUJ), "h_egasi", "xato-parol")
_r = kir(mijoz("203.0.113.77"), "h_egasi")
check("D1 hujumchi IP dan 5 xato — platforma egasi BOSHQA IP dan to'g'ri parol bilan KIRADI (asl: «Juda ko'p…», 15 daqiqa)",
      kirdimi(_r), (_r.status_code, (_r.text or "")[:150]))
_r = kir(mijoz(HUJ), "h_egasi")
check("D2 hujumchi IP sining o'zidan — to'g'ri parol bilan ham bloklangan (parol terish to'xtaydi)", not kirdimi(_r)
      and "Juda ko" in (_r.text or ""), (_r.status_code, (_r.text or "")[:150]))
RIP = "198.18.0.20"
for i in range(19):
    kir(mijoz(RIP), f"yoq_login_{i}", "xato")
_r = kir(mijoz(RIP), "h_ip_a")
check("D3 bir IP dan 19 xato (turli hisoblar) — o'sha IP dagi boshqa xodim kiradi", kirdimi(_r), _r.status_code)
kir(mijoz(RIP), "yoq_login_x", "xato")
_r = kir(mijoz(RIP), "h_ip_b")
check("D4 20 xato — o'sha IP dan kirish bloklanadi (avvalgidek)", not kirdimi(_r) and "Juda ko" in (_r.text or ""), _r.status_code)
_r = kir(mijoz(), "h_ip_b")
check("D4b boshqa IP dan — kiradi", kirdimi(_r), _r.status_code)
TANISH = "203.0.113.200"
check("D5a «h_tanish» o'z IP sidan kirgan (tanish manzil)", kirdimi(kir(mijoz(TANISH), "h_tanish")))
for k in range(6):
    _ip = f"198.18.1.{10 + k}"
    for _ in range(5):
        kir(mijoz(_ip), "h_tanish", "xato")
_r = kir(mijoz("203.0.113.201"), "h_tanish")
check("D5b tarqoq hujum (6 IP × 5 = 30 xato) — YANGI IP dan to'g'ri parol bilan ham bloklanadi", not kirdimi(_r)
      and "Juda ko" in (_r.text or ""), _r.status_code)
_r = kir(mijoz(TANISH), "h_tanish")
check("D5c o'sha paytda tanish IP dan (oxirgi 30 kunda kirgan) — KIRADI", kirdimi(_r), (_r.status_code, (_r.text or "")[:150]))
for k in range(6):
    _ip = f"198.18.2.{10 + k}"
    for _ in range(5):
        kir(mijoz(_ip), "h_qurbon", "xato")
_d = SessionLocal()
try:
    _d.add(LoginHistory(company_id=1, username="h_qurbon", success=True, ip_address="203.0.113.210",
                        created_at=datetime.utcnow() - timedelta(days=31)))
    _d.commit()
finally:
    _d.close()
_r = kir(mijoz("203.0.113.210"), "h_qurbon")
check("D5d 31 kun oldingi muvaffaqiyat — tanish EMAS (bloklanadi)", not kirdimi(_r), _r.status_code)
_d = SessionLocal()
try:
    _d.query(LoginHistory).filter(LoginHistory.username == "h_qurbon", LoginHistory.success == False).update(   # noqa: E712
        {LoginHistory.created_at: datetime.utcnow() - timedelta(minutes=16)}, synchronize_session=False)
    _d.commit()
finally:
    _d.close()
_r = kir(mijoz("203.0.113.211"), "h_qurbon")
check("D6 15 daqiqadan eski xatolar hisoblanmaydi — kiradi", kirdimi(_r), _r.status_code)
_rl = crud.check_login_rate_limit
_d = SessionLocal()
try:
    for _ in range(5):
        crud.log_login_attempt(_d, "h_none", success=False, ip_address=None)
    _n = _rl(_d, "h_none", None)
    _n2 = _rl(_d, "h_none", "203.0.113.212")
finally:
    _d.close()
check("D7 IP noma'lum — eski qoida (login bo'yicha 5): bloklangan; IP ma'lum bo'lsa — juftlik hisobi (bloklanmagan)",
      _n.get("blocked") is True and _n2.get("blocked") is False, (_n, _n2))
_d = SessionLocal()
try:
    for _k in range(5):
        crud.log_login_attempt(_d, "h_none_b", success=False, ip_address=f"203.0.113.{220 + _k}")
    _n3 = _rl(_d, "h_none_b", None)
finally:
    _d.close()
check("D7b IP noma'lum, xatolar turli IP lardan (5) — eski qoida bo'yicha bloklangan (`ip_address IS NULL` juftligi emas)",
      _n3.get("blocked") is True, _n3)
# hodim telefoni
_d = SessionLocal()
try:
    _e = Employee(company_id=1, name="D Hodim", position="Kesuvchi")
    _d.add(_e)
    _d.commit()
    EMP_ID = _e.id
finally:
    _d.close()
_r = req(ADM, "post", f"/api/employees/{EMP_ID}/set-login", data={"phone": "+998901430143", "pin": "4826"})
check("D8a hodimga telefon + PIN", _r.status_code == 200, (_r.status_code, js(_r)))
HJ = "198.18.3.77"
for i in range(5):
    req(mijoz(HJ), "post", "/hodim/login", data={"phone": "+998 90 143 01 43", "pin": f"11{i}9", "korxona": "HIMA"},
        follow_redirects=False)
_r = req(mijoz("203.0.113.13"), "post", "/hodim/login", data={"phone": "+998901430143", "pin": "4826", "korxona": "HIMA"},
         follow_redirects=False)
check("D8b hujumchi 5 xato PIN — hodim BOSHQA IP dan to'g'ri PIN bilan kiradi (asl: «Juda ko'p…»)",
      _r.status_code in (302, 303), (_r.status_code, (_r.text or "")[:150]))
_r = req(mijoz(HJ), "post", "/hodim/login", data={"phone": "+998901430143", "pin": "4826", "korxona": "HIMA"},
         follow_redirects=False)
check("D8c hujumchi IP sidan — to'g'ri PIN bilan ham bloklangan", _r.status_code == 200 and "Juda ko" in (_r.text or ""),
      _r.status_code)

# ══════════════════════════════════════════════════════════════
section("E. CRON siri, sessiya tokeni xeshi, eski parol xeshlari (A-X09)")
# ══════════════════════════════════════════════════════════════
C = mijoz()
check("E1a cron — to'g'ri sir manzilda (avvalgidek) — 200", req(C, "get", "/api/cron/cleanup-sessions?secret=himoya-cron-143")
      .status_code == 200)
check("E1b cron — noto'g'ri sir — 403", req(C, "get", "/api/cron/cleanup-sessions?secret=xato").status_code == 403)
check("E1c cron — sir `X-Cron-Secret` sarlavhasida — 200 (asl: 403)", req(C, "get", "/api/cron/cleanup-sessions",
      headers={"X-Cron-Secret": "himoya-cron-143"}).status_code == 200)
check("E1d cron — sarlavha noto'g'ri (manzildagi to'g'ri) — 403 (sarlavha ustun)", req(C, "get",
      "/api/cron/cleanup-sessions?secret=himoya-cron-143", headers={"X-Cron-Secret": "xato"}).status_code == 403)
check("E1e low-stock-check ham sarlavha bilan — 200", req(C, "get", "/api/cron/low-stock-check",
      headers={"X-Cron-Secret": "himoya-cron-143"}).status_code == 200)
_eski_cs = main.CRON_SECRET
main.CRON_SECRET = ""
check("E1f sir o'rnatilmagan — 503 (avvalgidek)", req(C, "get", "/api/cron/cleanup-sessions?secret=").status_code == 503)
main.CRON_SECRET = _eski_cs
_tx = getattr(auth, "token_xesh", lambda t: hashlib.sha256(str(t).encode()).hexdigest())
S = mijoz()
kir(S, "h_admin")
_tok = S.cookies.get("session_token")
_d = SessionLocal()
try:
    _xom = _d.query(UserSession).filter(UserSession.token == _tok).count()
    _xs = _d.query(UserSession).filter(UserSession.token == _tx(_tok)).count()
finally:
    _d.close()
check("E2 bazada sessiya tokenining XESHI (cookie dagi xom qiymat bazada yo'q) — cookie ishlaydi (asl: xom)",
      _xom == 0 and _xs == 1 and ishlaydimi(S) == 200, (_xom, _xs))
_o = mijoz()
_o.cookies.set("session_token", _tx(_tok), domain="testserver.local")
check("E3 bazadagi xesh qiymati cookie sifatida — kirmaydi (401)", ishlaydimi(_o) == 401, ishlaydimi(_o))
req(S, "get", "/logout", follow_redirects=False)
_d = SessionLocal()
try:
    _q = _d.query(UserSession).filter(UserSession.token == _tx(_tok)).count()
finally:
    _d.close()
check("E4 chiqish — sessiya (xesh bo'yicha) o'chdi", _q == 0 and ishlaydimi(S) == 401, _q)
P1, P2 = mijoz(), mijoz()
kir(P1, "h_parol")
kir(P2, "h_parol")
_uid = SessionLocal().query(User.id).filter(User.username == "h_parol").scalar()
_r = req(P1, "post", f"/api/users/{_uid}/password", json={"new_password": "Yangi456!", "current_password": PAROL})
check("E5 o'z parolini almashtirish — joriy sessiya qoladi, boshqa qurilma chiqadi (xeshli tokenda ham)",
      _r.status_code == 200 and ishlaydimi(P1) == 200 and ishlaydimi(P2) == 401, (_r.status_code, ishlaydimi(P1), ishlaydimi(P2)))
_d = SessionLocal()
try:
    _et = auth.create_employee_session(_d, EMP_ID, qurilma_hash="q" * 64)
    _et2 = auth.create_employee_session(_d, EMP_ID, qurilma_hash="q" * 64)
    _ex = _d.query(EmployeeSession).filter(EmployeeSession.token == _et).count()
    _eh = _d.query(EmployeeSession).filter(EmployeeSession.token == _tx(_et)).count()
    _eg = auth.get_employee_session(_d, _et)
    _emp = _d.get(Employee, EMP_ID)
    crud._hodim_sessiyalarini_yop(_d, _emp, qoldir_token=_et)
    _d.commit()
    _qoldi = (auth.get_employee_session(_d, _et) is not None, auth.get_employee_session(_d, _et2) is not None)
    auth.delete_employee_session(_d, _et)
    _och = auth.get_employee_session(_d, _et) is None
finally:
    _d.close()
check("E6 hodim sessiyasi: bazada xesh, xom tokenda topiladi; «shu sessiyadan tashqari yopish» — o'zi qoladi; chiqish o'chiradi",
      _ex == 0 and _eh == 1 and _eg and _eg.get("employee_id") == EMP_ID and _qoldi == (True, False) and _och,
      (_ex, _eh, _eg, _qoldi, _och))
# eski XOM tokenlar (zip 170 bazasi) — ishga tushish migratsiyasi
import secrets as _sec                             # noqa: E402
_xom_u, _xom_e = _sec.token_urlsafe(32), _sec.token_urlsafe(32)
_d = SessionLocal()
try:
    _hid = _d.query(User.id).filter(User.username == "h_admin").scalar()
    _d.add(UserSession(token=_xom_u, user_id=_hid, expires_at=datetime.utcnow() + timedelta(hours=8)))
    _d.add(EmployeeSession(token=_xom_e, employee_id=EMP_ID, expires_at=datetime.utcnow() + timedelta(days=1),
                           qurilma_hash="q" * 64))
    _d.commit()
finally:
    _d.close()
_mig = getattr(main, "_migrate_himoya143", None)
_m1 = xav(lambda: _mig(), {}) if _mig else "YO'Q (asl kod)"
_d = SessionLocal()
try:
    _hol = (_d.query(UserSession).filter(UserSession.token == _xom_u).count(),
            _d.query(UserSession).filter(UserSession.token == _tx(_xom_u)).count(),
            _d.query(EmployeeSession).filter(EmployeeSession.token == _tx(_xom_e)).count())
    _uzun = sorted({len(t) for (t,) in _d.query(UserSession.token).all()} | {len(t) for (t,) in _d.query(EmployeeSession.token).all()})
finally:
    _d.close()
_m = mijoz()
_m.cookies.set("session_token", _xom_u, domain="testserver.local")
check("E7a migratsiya: eski xom tokenlar xeshga o'tdi (foydalanuvchi va hodim), bazada faqat 64 belgili tokenlar",
      _hol == (0, 1, 1) and _uzun == [64], (_m1, _hol, _uzun))
check("E7b migratsiyadan keyin eski cookie ISHLAYVERADI (hech kim chiqib ketmaydi)", ishlaydimi(_m) == 200, ishlaydimi(_m))
check("E7d migratsiya allaqachon xeshlangan tokenlarga tegmaydi — avval ochilgan admin sessiyasi ishlaydi", ishlaydimi(ADM) == 200,
      ishlaydimi(ADM))
_m2 = xav(lambda: _mig(), {}) if _mig else "YO'Q"
check("E7c migratsiya takror — o'zgarish yo'q", isinstance(_m2, dict) and _m2.get("sessiya") == {"user_sessions": 0,
      "employee_sessions": 0}, _m2)
# eski SHA-256 parol / PIN
_d = SessionLocal()
try:
    _d.query(User).filter(User.username == "h_eski").update({User.password_hash: hashlib.sha256(b"EskiParol1").hexdigest()})
    _d.query(Employee).filter(Employee.id == EMP_ID).update({Employee.pin_hash: hashlib.sha256(b"5937").hexdigest()})
    _d.commit()
finally:
    _d.close()
_m3 = xav(lambda: _mig(), {}) if _mig else "YO'Q"
_d = SessionLocal()
try:
    _ph = _d.query(User.password_hash).filter(User.username == "h_eski").scalar()
    _pin = _d.query(Employee.pin_hash).filter(Employee.id == EMP_ID).scalar()
    _qolgan = [u for (u,) in _d.query(User.password_hash).all() if auth.eski_sha256mi(u)] if hasattr(auth, "eski_sha256mi") else ["?"]
finally:
    _d.close()
check("E8a ishga tushish: eski SHA-256 parol va PIN xeshi bcrypt bilan O'RALDI (bazada tuzsiz xesh qolmadi) (asl: qolardi)",
      str(_ph).startswith(getattr(auth, "ORALGAN_SHA256", "?") + "$2") and str(_pin).startswith(getattr(auth, "ORALGAN_SHA256", "?") + "$2")
      and len(str(_pin)) <= 64 and not _qolgan
      and isinstance(_m3, dict) and _m3.get("xesh") == {"users": 1, "employees": 1}, (_m3, str(_ph)[:12], str(_pin)[:12]))
_r = kir(mijoz(), "h_eski", "XatoParol1")
check("E8b o'ralgan xesh — noto'g'ri parol bilan kirmaydi", not kirdimi(_r), _r.status_code)
_r = kir(mijoz(), "h_eski", "EskiParol1")
_ph2 = SessionLocal().query(User.password_hash).filter(User.username == "h_eski").scalar()
check("E8c o'ralgan xesh — ESKI parol bilan kiradi va xesh oddiy bcrypt ga o'tadi", kirdimi(_r) and str(_ph2).startswith("$2"),
      (_r.status_code, str(_ph2)[:8]))
_d = SessionLocal()
try:
    _ae = crud.authenticate_employee(_d, "+998901430143", "5937", company_id=1)
    _pin2 = _d.query(Employee.pin_hash).filter(Employee.id == EMP_ID).scalar()
    _ae_x = crud.authenticate_employee(_d, "+998901430143", "0000", company_id=1)
finally:
    _d.close()
check("E8d o'ralgan PIN — hodim eski PIN bilan topiladi, PIN bcrypt ga o'tadi; noto'g'ri PIN — yo'q",
      _ae is not None and str(_pin2).startswith("$2") and _ae_x is None, (_ae, str(_pin2)[:8], _ae_x))
_m4 = xav(lambda: _mig(), {}) if _mig else "YO'Q"
check("E8e takror ishga tushish — o'raladigan xesh yo'q", isinstance(_m4, dict) and _m4.get("xesh") == {"users": 0, "employees": 0},
      _m4)
_vp = auth.verify_password
_eski = hashlib.sha256(b"Mos1").hexdigest()
check("E9 `verify_password`: eski xom SHA-256 (orqaga moslik), o'ralgan, bo'sh xesh, buzilgan o'ram",
      _vp("Mos1", _eski) and not _vp("Mos2", _eski) and not _vp("Mos1", "")
      and (not hasattr(auth, "eski_xeshni_ora") or (_vp("Mos1", auth.eski_xeshni_ora(_eski))
                                                     and not _vp("Mos2", auth.eski_xeshni_ora(_eski))))
      and not _vp("Mos1", "s$buzuq") and not _vp("Mos1", "sha256$buzuq"))

# ══════════════════════════════════════════════════════════════
section("F. Material nomi — harf / bo'shliq / apostrof farqi bitta nom (N1)")
# ══════════════════════════════════════════════════════════════
_k = getattr(crud, "material_nomi_kaliti", None)
check("F1 nom kaliti: katta-kichik harf, bo'shliqlar, apostrof turlari, kirill",
      _k is not None and _k("F Oq Mel") == _k("f  oq   MEL ") == _k("\tF OQ mel") and _k("Bo'yoq") == _k("Boʻyoq") == _k("Bo‘yoq")
      == _k("Bo’yoq") == _k("Bo`yoq") and _k("МЕЛ") == _k("мел") and _k("Oq mel") != _k("Oq mel 2"))


def nomi(i):
    """Material nomi bazadan (yo'q / id bo'sh — None; sinov qulamasin)."""
    if not i:
        return None
    d = SessionLocal()
    try:
        x = d.get(Inventory, i)
        return x.item_name if x is not None else None
    finally:
        d.close()


def mat(nom, birlik="kg", **q):
    return req(ADM, "post", "/api/inventory", json={"item_name": nom, "unit": birlik, "min_stock": 0, **q})


def kalitli(nom):
    d = SessionLocal()
    try:
        _kk = (_k or (lambda x: x))(nom)
        return [(m.id, m.item_name, m.is_deleted) for m in d.query(Inventory).filter(Inventory.company_id == 1).all()
                if (_k or (lambda x: x))(m.item_name) == _kk]
    finally:
        d.close()


_r = mat("F Oq Mel")
F_ID = js(_r).get("id")
check("F2a «F Oq Mel» yaratildi", _r.status_code == 200 and F_ID, (_r.status_code, js(_r)))
for nom, birlik in (("f oq mel", "litr"), ("F  Oq   Mel", "kg"), (" F OQ MEL ", "kg")):
    _r = mat(nom, birlik)
    check(f"F2b «{nom}» ({birlik}) — 409 material_nomi_band, mavjud material id si bilan (asl: 200 — alohida material)",
          _r.status_code == 409 and (js(_r).get("detail") or {}).get("id") == F_ID
          and (js(_r).get("detail") or {}).get("item_name") == "F Oq Mel", (_r.status_code, js(_r)))
check("F2c korxonada shu kalitli material BITTA", len(kalitli("F Oq Mel")) == 1, kalitli("F Oq Mel"))
_r1, _r2 = mat("F Bo'yoq"), mat("F Boʻyoq")
check("F3 «Bo'yoq» / «Boʻyoq» — ikkinchisi 409", _r1.status_code == 200 and _r2.status_code == 409, (_r1.status_code, _r2.status_code))
_r1, _r2 = mat("F МЕЛ"), mat("F мел")
check("F4 kirill «МЕЛ» / «мел» — ikkinchisi 409 (SQLite `lower` lotindan tashqarini bilmaydi — Python `casefold`)",
      _r1.status_code == 200 and _r2.status_code == 409, (_r1.status_code, _r2.status_code))
_r = mat("F Oq Mel 2")
F2_ID = js(_r).get("id")
check("F5 boshqa nom («F Oq Mel 2») — 200", _r.status_code == 200, _r.status_code)
_r = req(ADM, "put", f"/api/inventory/{F2_ID}", json={"item_name": "f OQ mel"})
check("F6 boshqa materialni «f OQ mel» ga qayta nomlash — 400, xabarda mavjud nom; nomi o'zgarmadi (asl: 200)",
      _r.status_code == 400 and "F Oq Mel" in str(js(_r).get("detail")) and
      nomi(F2_ID) == "F Oq Mel 2", (_r.status_code, js(_r)))
_r = req(ADM, "put", f"/api/inventory/{F_ID}", json={"item_name": "F OQ MEL"})
check("F7 o'z nomining yozilishini o'zgartirish («F Oq Mel» → «F OQ MEL») — 200, saqlandi",
      _r.status_code == 200 and nomi(F_ID) == "F OQ MEL", (_r.status_code, js(_r)))
def yashir(nom):
    """Yashirin (o'chirilgan) material: qoldig'i 0, `is_deleted` — PG da harakatli material o'chirilganda shunday bo'ladi (FK);
    SQLite da FK yo'q — qattiq o'chirilardi, shuning uchun holat bazada to'g'ridan-to'g'ri yasaladi (ikkala rejimda bir xil)."""
    _i = js(mat(nom, stock_quantity=0)).get("id")
    _d = SessionLocal()
    try:
        _d.query(Inventory).filter(Inventory.id == _i).update({Inventory.is_deleted: True}, synchronize_session=False)
        _d.commit()
    finally:
        _d.close()
    return _i, type("R", (), {"status_code": 200})()


K_ID, _rd = yashir("F Kley")
_r = mat("f  kley", stock_quantity=3, price_per_unit=1000)
_kd = SessionLocal().get(Inventory, K_ID) if K_ID else None
check("F8 yashirin «F Kley» (kg) — «f  kley» (kg) bilan yaratish O'SHA materialni tiklaydi (nomi saqlanadi, qoldiq 3, harakat)",
      lambda: _rd.status_code == 200 and _r.status_code == 200 and js(_r).get("id") == K_ID and _kd.is_deleted is False
      and _kd.item_name == "F Kley" and float(_kd.stock_quantity) == 3.0 and len(kalitli("F Kley")) == 1,
      (_rd.status_code, _r.status_code, js(_r), getattr(_kd, "item_name", None), getattr(_kd, "stock_quantity", None)))
B_ID, _ = yashir("F Bor")
_r = mat("f bor", "litr")
check("F9 yashirin «F Bor» (kg) — «f bor» (litr) — 409 material_nomi_yashirin, yangi material yo'q",
      _r.status_code == 409 and (js(_r).get("detail") or {}).get("type") == "material_nomi_yashirin" and len(kalitli("F Bor")) == 1,
      (_r.status_code, js(_r), kalitli("F Bor")))
_r = req(ADM, "put", f"/api/inventory/{F2_ID}", json={"item_name": "F BOR"})
check("F10 yashirin nomga (harf farqi bilan) qayta nomlash — 400 «o'chirilgan»", _r.status_code == 400
      and "o'chirilgan" in str(js(_r).get("detail")), (_r.status_code, js(_r)))
# bazadagi ESKI takrorlar (zip 170 gacha yaratilgan): faol + yashirin, ikki yashirin (boshqa birliklar)
_d = SessionLocal()
try:
    _d.add_all([Inventory(company_id=1, item_name="F Dup", unit="kg", stock_quantity=0, is_deleted=True),
                Inventory(company_id=1, item_name="f dup", unit="kg", stock_quantity=2, is_deleted=False),
                Inventory(company_id=1, item_name="F Ikki", unit="kg", stock_quantity=0, is_deleted=True),
                Inventory(company_id=1, item_name="f ikki", unit="litr", stock_quantity=0, is_deleted=True)])
    _d.commit()
    _dup_faol = _d.query(Inventory.id).filter(Inventory.item_name == "f dup").scalar()
    _ikki_l = _d.query(Inventory.id).filter(Inventory.item_name == "f ikki").scalar()
finally:
    _d.close()
_r = mat("F DUP")
check("F11 eski takror (yashirin + faol) — 409, FAOL material bilan", _r.status_code == 409
      and (js(_r).get("detail") or {}).get("id") == _dup_faol, (_r.status_code, js(_r)))
_r = mat("F IKKI", "litr")
check("F12 eski ikki yashirin takror — birligi MOS kelgani (litr) tiklanadi", _r.status_code == 200 and js(_r).get("id") == _ikki_l,
      (_r.status_code, js(_r), _ikki_l))
if PG_URL:
    _nat = []

    def _yarat(nom):
        c = mijoz("203.0.113.1")
        kir(c, "h_admin")
        _nat.append(req(c, "post", "/api/inventory", json={"item_name": nom, "unit": "kg", "min_stock": 0}).status_code)

    # kech134 naqshi: tekshiruvdan KEYIN kechikish (nomdosh qidiruvi → 0,5 s) — qulfsiz kodda uchala so'rov ham «yo'q» ko'rib yozardi
    _asl_nd = getattr(crud, "nomdosh_materiallar", None)      # asl kodda yo'q — kechikishsiz

    def _sekin_nd(*a, **k):
        _r0 = _asl_nd(*a, **k)
        time.sleep(0.5)
        return _r0

    if _asl_nd is not None:
        crud.nomdosh_materiallar = _sekin_nd
    try:
        _th = [threading.Thread(target=_yarat, args=(n,)) for n in ("F Para", "f para", "F  PARA")]
        for t in _th:
            t.start()
        for t in _th:
            t.join(timeout=60)
    finally:
        if _asl_nd is not None:
            crud.nomdosh_materiallar = _asl_nd
    check("F13 [PG] bir vaqtda «F Para» / «f para» / «F  PARA» — bittasi 200, qolgani 409; material bitta",
          sorted(_nat) == [200, 409, 409] and len(kalitli("F Para")) == 1, (_nat, kalitli("F Para")))
else:
    check("F13 (SQLite) — nom poygasi faqat PG da tekshiriladi", True)

# ══════════════════════════════════════════════════════════════
section("X. Xatolar")
# ══════════════════════════════════════════════════════════════
_5xx = [x for x in HOLATLAR if x[1] >= 500 and not (x[1] == 503 and x[0] in ("POST /telegram/webhook",
                                                                              "GET /api/cron/cleanup-sessions"))]
check("X1 API 5xx yo'q (webhook / cron 503 — sir o'rnatilmagan, kutilgan)", not _5xx, _5xx[:8])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
