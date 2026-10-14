#!/usr/bin/env python3
"""
test_hodim_tg_pdf178.py — kech144 (zip 178, AUDIT 2-to'lqin): Telegram, PDF va hodim paneli. TestClient + HAQIQIY lokal server
(uvicorn — bir vaqtdagi so'rovlar, fon vazifalari) + HAQIQIY Chromium (hodim paneli, ruxsat kutish sahifasi). Telegram tarmog'iga hech
narsa ketmaydi (`main._tg_post_message`, `main._send_telegram_document` — yozib oluvchi almashtirishlar).

NIMA UCHUN KERAK (asl kod = zip 177; audit `work/k173_tayyorgarlik/agentlar/hodim_tg_pdf/HISOBOT.md`)
  T1  Usta boti webhooki (`async`) sinxron Telegram / baza bilan BUTUN serverni to'xtatardi — Telegram 1,5 s kechiksa `/api/health`
      ham 1,5 s kutardi.
  T2  4096 belgidan uzun xabar (160 materialli «Ombor hisoboti») rad etilib yo'qolardi — `_send_telegram` False.
  T3  Obuna eslatmasi Telegram yuborilmasa ham «yuborildi» deb belgilanardi (keyin umuman yuborilmasdi).
  T4  Kunlik zaxira Telegramga yuborilmasa — hech qayerda iz yo'q.
  T5  Yuk xati / «Tayyor» Telegram xabarlari JAVOBDAN OLDIN (javob 5 … 75 s kechikardi).
  T7  Botning /start shoxida baza xatosi — 500 (Telegram qayta-qayta yuboradi).
  P1  Yuk xatidagi uzun izoh (bo'shliqsiz 9 000 / bosh harfli 8 000 belgi) — PDF 500.
  P2  PDF havolasi xatoda xom JSON (401 / 404 / 500 — inglizcha Python xatosi bilan).
  P3  Moliya oylik PDF `month=13` — 500.
  H1  Hodim paneli: xatoda faqat «Yuklashda xato» (sessiya tugaganda ham — qayta yuklash abadiy yiqilardi).
  H2  Javobdan keyin ro'yxat yangilanmasa — «Hamma to'lovlarga javob berdingiz», qolgan to'lov tugmalari yo'qolardi.
  H3  Ruxsat kutish sahifasi 5xx da ham «Internet aloqasi yo'q».
  H4  `/login`, `/hodim/login` — `async def` ichida bcrypt (har urinish serverni to'xtatardi).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 177) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_hodim_tg_pdf178.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import socket
import inspect
import tempfile
import threading
import contextlib
import urllib.request
import urllib.error
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hodim_tg_pdf178_test"
_T = tempfile.mkdtemp(prefix="htp178_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'htp178.db')}"
for _k in ("TENANT_FILTER", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT"):
    os.environ.pop(_k, None)
# Telegram — FAQAT soxta qiymatlar (tarmoqqa hech narsa ketmaydi — yuboruvchilar almashtiriladi)
os.environ["TELEGRAM_BOT_TOKEN"] = "178178:SINOV"
os.environ["BACKUP_TELEGRAM_CHAT_ID"] = "-100178"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "sinov178sir"

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import obuna                                   # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Employee, ErrorLog, Project   # noqa: E402
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


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Telegram yozib oluvchilari (tarmoqsiz)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TG = []          # (chat_id, matn, reply_markup)
TG_DOC = []      # (chat_id, filename)
TG_DOC_NATIJA = [True]


class _TgRad(Exception):
    pass


def _soxta_post(token, chat_id, text, reply_markup=None):
    """Telegram kabi: 4096 belgidan uzun matn — 400 (rad)."""
    if len(str(text)) > 4096:
        raise _TgRad("HTTP Error 400: Bad Request: message is too long")
    TG.append((str(chat_id), str(text), reply_markup))
    return None


def _soxta_doc(chat_id, file_bytes, filename, caption="", content_type="application/json", company_id=None):
    TG_DOC.append((str(chat_id), filename))
    return TG_DOC_NATIJA[0]


main._tg_post_message = _soxta_post
main._send_telegram_document = _soxta_doc

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t178_admin", PAROL, UserRole.ADMIN, "T178 Admin", company_id=1)
PRJ = Project(company_id=1, client_name="T178 Mijoz", project_name="T178 loyiha", total_budget=0, total_paid=0)
s.add(PRJ)
s.commit()
ID = {"PRJ": PRJ.id}
s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert C.post("/login", data={"username": "t178_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)


def buyurtma(nom, narx, n, topshir=True, izoh=None):
    r = C.post("/api/orders?confirm_shortage=true", json={"project_id": ID["PRJ"], "order_type": "product", "items": [
        {"name": nom, "category": "panel", "width": 50, "thickness": 5, "quantity": n, "unit_price": narx, "is_coated": False}]})
    assert r.status_code == 200, r.text
    oid, oi = js(r)["id"], js(r)["items"][0]["id"]
    did = None
    if topshir:
        rd = C.post("/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": oi, "quantity": n}], "received_by": None,
                                             "notes": izoh, "transport_carrier": None, "transport_cost": 0, "transport_payer": "none",
                                             "payment_amount": None, "payment_method": "naqd"})
        assert rd.status_code == 200, rd.text
        did = js(rd).get("delivery_id")
    return oid, oi, did


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T2. Uzun Telegram xabari — bo'laklab (≤ 4000 belgi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_uzun = "\n".join(f"• Material {i:03d} — qoldiq {i * 7} kg (kam: {i} kg) ⚠️" for i in range(160))
_bol = main._tg_bolaklar(_uzun) if hasattr(main, "_tg_bolaklar") else None
check("T2a `_tg_bolaklar`: 7 000+ belgili matn — hammasi ≤ 4000, birlashtirilsa AYNAN asl matn",
      bool(_bol) and len(_uzun) > 7000 and len(_bol) >= 2 and all(len(b) <= 4000 for b in _bol) and "\n".join(_bol) == _uzun,
      (len(_uzun), [len(b) for b in (_bol or [])]))
_bir = main._tg_bolaklar("x" * 9000) if hasattr(main, "_tg_bolaklar") else None
check("T2b bitta qator 9 000 belgi — 4000 / 4000 / 1000; qisqa matn — o'zi",
      _bir is not None and [len(b) for b in _bir] == [4000, 4000, 1000] and main._tg_bolaklar("salom") == ["salom"],
      [len(b) for b in (_bir or [])])
TG.clear()
_nat = main._send_telegram(_uzun, company_id=1)
check("T2c `_send_telegram` (7 000+ belgi) — YUBORILDI (True), Telegramga ≥ 2 ta ≤ 4000 belgili xabar (ilgari 400 — False, yo'qolardi)",
      _nat is True and len(TG) >= 2 and all(len(t[1]) <= 4000 for t in TG), (_nat, [len(t[1]) for t in TG]))
TG.clear()
main._send_telegram_to("777", _uzun, company_id=1)
check("T2d `_send_telegram_to` (mijoz / usta) — ham bo'laklab", len(TG) >= 2 and all(t[0] == "777" for t in TG), [len(t[1]) for t in TG])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T3. Obuna eslatmasi — yuborilmasa «yuborildi» deb belgilanmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from production_models import Company      # noqa: E402

KID = db_ishi(lambda d: (lambda c: (d.add(c), d.flush(), c.id)[2])(
    Company(name="T178 Mijoz korxona", obuna_tugash=obuna.bugun() + timedelta(days=5))))
_asl_send = main._send_telegram
main._send_telegram = lambda text, company_id=None: False
try:
    with contextlib.redirect_stdout(io.StringIO()):
        main.obuna_kunlik_ish()
finally:
    main._send_telegram = _asl_send
_h1 = db_ishi(lambda d: d.get(Company, KID).eslatma_holati)
check("T3a Telegram yubora olmadi — `eslatma_holati` YOZILMAYDI (ertaga qayta uriniladi; ilgari «7» deb belgilanardi)", _h1 is None, _h1)
_yuborilgan = []
main._send_telegram = lambda text, company_id=None: (_yuborilgan.append(text), True)[1]
try:
    with contextlib.redirect_stdout(io.StringIO()):
        main.obuna_kunlik_ish()
finally:
    main._send_telegram = _asl_send
_h2 = db_ishi(lambda d: d.get(Company, KID).eslatma_holati)
check("T3b keyingi urinishda yuborildi — endi belgilanadi («…:7»), xabar egasiga ketdi",
      bool(_h2) and str(_h2).endswith(":7") and any("T178 Mijoz korxona" in x for x in _yuborilgan), (_h2, _yuborilgan[:1]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T4. Kunlik zaxira yuborilmasa — «Xatoliklar» jurnalida")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TG_DOC_NATIJA[0] = False
_e0 = db_ishi(lambda d: d.query(ErrorLog).filter(ErrorLog.error_message.like("%Kunlik zaxira%")).count())
with contextlib.redirect_stdout(io.StringIO()):
    main.run_daily_backup()
_e1 = db_ishi(lambda d: [x.error_message for x in d.query(ErrorLog).filter(ErrorLog.error_message.like("%Kunlik zaxira%")).all()])
check("T4 zaxira fayli Telegramga ketmadi — jurnalda «Kunlik zaxira Telegramga yuborilmadi (-100178)» (ilgari faqat konsolda)",
      len(_e1) == _e0 + 1 and "Telegramga yuborilmadi (-100178)" in _e1[-1] and TG_DOC and TG_DOC[-1][0] == "-100178", (_e0, _e1, TG_DOC))
TG_DOC_NATIJA[0] = True

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T7. Usta boti /start — baza xatosi 500 emas")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_asl_ustasi = main._bot_ustasi


def _yiqil(*a, **k):
    raise RuntimeError("baza uzildi (sinov)")


main._bot_ustasi = _yiqil
TG.clear()
try:
    _r = C.post("/telegram/webhook", json={"message": {"chat": {"id": 8178}, "text": "/start"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "sinov178sir"})
finally:
    main._bot_ustasi = _asl_ustasi
check("T7 /start da baza xatosi — javob 200 {ok: true} (Telegram qayta yubormaydi), ustaga «⚠️ Xatolik yuz berdi …» (ilgari 500)",
      _r.status_code == 200 and js(_r).get("ok") is True and any(t[0] == "8178" and "Xatolik" in t[1] for t in TG), (_r.status_code, _r.text[:150], TG))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P1 / P2 / P3. PDF")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_o1, _i1, D1 = buyurtma("T178 izoh detali A", 10000, 2, izoh="Q" * 9000)
_o2, _i2, D2 = buyurtma("T178 izoh detali B", 10000, 2, izoh=("DIQQAT YUK EHTIYOT BILAN TASHILSIN " * 240)[:8400])
_p1, _p2 = C.get(f"/api/deliveries/{D1}/pdf"), C.get(f"/api/deliveries/{D2}/pdf")
check("P1 yuk xati — bo'shliqsiz 9 000 va bosh harfli 8 400 belgili izoh: PDF 200 (ilgari 500 «Flowable too large»)",
      _p1.status_code == 200 and _p1.content[:4] == b"%PDF" and _p2.status_code == 200 and _p2.content[:4] == b"%PDF",
      (_p1.status_code, _p1.text[:120] if _p1.status_code != 200 else "", _p2.status_code))
HTML = {"Accept": "text/html,application/xhtml+xml"}
_r = C.get("/api/deliveries/987654/pdf", headers=HTML)
check("P2a yo'q hujjat havolasi (brauzer) — 404, o'zbekcha sahifa «Hujjat topilmadi» (ilgari xom JSON)",
      _r.status_code == 404 and "text/html" in _r.headers.get("content-type", "") and "Hujjat topilmadi" in _r.text, (_r.status_code, _r.text[:150]))
_r = C.get("/api/deliveries/987654/pdf", headers={"Accept": "*/*"})
check("P2b sahifa ichidagi so'rov (Accept */*) — avvalgidek JSON 404", _r.status_code == 404 and "application/json" in _r.headers.get("content-type", ""),
      (_r.status_code, _r.headers.get("content-type")))
_bosh = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r = _bosh.get(f"/api/deliveries/{D1}/pdf", headers=HTML, follow_redirects=False)
check("P2c sessiya yo'q — PDF havolasi kirish sahifasiga (302 → /login; ilgari {\"detail\": \"Iltimos, tizimga kiring\"})",
      _r.status_code in (302, 303, 307) and _r.headers.get("location", "").endswith("/login"), (_r.status_code, _r.headers.get("location")))
import delivery_pdf as _dp      # noqa: E402

_asl_gen = _dp.generate_delivery_pdf


def _pdf_yiqil(*a, **k):
    raise ValueError("Flowable <Table@0x7f> too large on page 2 (sinov)")


_dp.generate_delivery_pdf = _pdf_yiqil
try:
    _r1 = C.get(f"/api/deliveries/{D1}/pdf", headers=HTML)
    _r2 = C.get(f"/api/deliveries/{D1}/pdf", headers={"Accept": "*/*"})
finally:
    _dp.generate_delivery_pdf = _asl_gen
_jl = db_ishi(lambda d: [(x.error_message, x.company_id) for x in d.query(ErrorLog).filter(ErrorLog.error_message.like("%Flowable%")).all()])
check("P2d PDF tayyorlanmadi — brauzerda 500 o'zbekcha sahifa «Hujjat tayyorlanmadi», Python xatosi KO'RINMAYDI; JSON — o'zbekcha matn",
      _r1.status_code == 500 and "Hujjat tayyorlanmadi" in _r1.text and "Flowable" not in _r1.text
      and _r2.status_code == 500 and "Flowable" not in _r2.text and "Xatoliklar" in str(js(_r2).get("detail")),
      (_r1.status_code, _r1.text[:120], _r2.text[:200]))
check("P2e sabab «Xatoliklar» jurnalida (korxonaga bog'langan — admin ko'radi)",
      any("PDF tayyorlanmadi" in m and "Flowable" in m and cid == 1 for m, cid in _jl), _jl)
_r = C.get("/api/finance/report-pdf?year=2026&month=13")
check("P3 Moliya oylik PDF `month=13` — 400 va sabab (ilgari 500)", _r.status_code == 400 and bool(js(_r).get("detail")), (_r.status_code, _r.text[:150]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H4. Kirish — `def` (bcrypt server oqimini to'xtatmaydi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("H4 `/login` va `/hodim/login` (POST) — `async def` emas; kirish ishlaydi",
      not inspect.iscoroutinefunction(main.login_submit) and not inspect.iscoroutinefunction(main.hodim_login_submit)
      and TestClient(main.app, base_url="https://testserver").post("/login", data={"username": "t178_admin", "password": PAROL},
                                                                   follow_redirects=False).status_code in (302, 303),
      (inspect.iscoroutinefunction(main.login_submit), inspect.iscoroutinefunction(main.hodim_login_submit)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Lokal server (bir vaqtdagi so'rovlar, fon vazifalari) va Chromium
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
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
check("L0 lokal server ishga tushdi", server.started)
SESS = C.cookies.get("session_token")


def sorov(usul, yol, tana=None, sarlavha=None, cookie=True):
    h = dict(sarlavha or {})
    if cookie and SESS:
        h["Cookie"] = f"session_token={SESS}"
    data = None
    if tana is not None:
        data = json.dumps(tana).encode("utf-8")
        h["Content-Type"] = "application/json"
    q = urllib.request.Request(B + yol, data=data, method=usul, headers=h)
    b = time.time()
    try:
        with urllib.request.urlopen(q, timeout=30) as r:
            return r.status, r.read(), time.time() - b
    except urllib.error.HTTPError as e:
        return e.code, e.read(), time.time() - b


section("T1. Usta boti webhooki serverni to'xtatmaydi")
_asl_javob = main._usta_boti_javobi


def _sekin_javob(data, token, korxona_id=None):
    time.sleep(1.5)
    return {"ok": True}


main._usta_boti_javobi = _sekin_javob
try:
    for _yol, _sir, _nom in (("/telegram/webhook", "sinov178sir", "umumiy bot"), ("/telegram/webhook/1", "korxona178sir", "korxona boti")):
        if _yol.endswith("/1"):
            db_ishi(lambda d: (crud.set_setting(d, "telegram_bot_token", "178178:KORXONA", company_id=1),
                               crud.set_setting(d, main.TG_KORXONA_SIR, "korxona178sir", company_id=1)))
        _w = {}

        def _wh():
            _w["n"] = sorov("POST", _yol, {"message": {"chat": {"id": 1}, "text": "/start"}},
                            {"X-Telegram-Bot-Api-Secret-Token": _sir}, cookie=False)
        _t = threading.Thread(target=_wh)
        _t.start()
        time.sleep(0.3)
        _hl = sorov("GET", "/api/health", cookie=False)
        _t.join(10)
        check(f"T1 {_nom}: Telegram 1,5 s kechikkan paytda `/api/health` kutmaydi (< 0,6 s; ilgari ~1,2 s), webhook 200",
              _hl[0] == 200 and _hl[2] < 0.6 and _w.get("n", (0,))[0] == 200, (_hl[0], round(_hl[2], 2), _w.get("n", (None,))[0]))
finally:
    main._usta_boti_javobi = _asl_javob

section("T5. Yuk xati / «Tayyor» Telegram xabarlari — javobdan KEYIN (fon vazifasi)")
_asl_pdf_m = main._send_delivery_pdf_to_customer
_asl_send_to = main._send_telegram_to
FON = []


def _sekin_tg(text, company_id=None):
    time.sleep(1.0)
    FON.append(("tg", time.time()))
    return True


def _sekin_pdf(db, delivery_id):
    time.sleep(0.5)
    try:
        _dn = crud.get_delivery(db, delivery_id).delivery_number
    except Exception as e:                 # noqa: BLE001
        _dn = f"XATO {type(e).__name__}"
    FON.append(("pdf", time.time(), _dn))


main._send_telegram = _sekin_tg
main._send_delivery_pdf_to_customer = _sekin_pdf
try:
    _r = C.post("/api/orders?confirm_shortage=true", json={"project_id": ID["PRJ"], "order_type": "product", "items": [
        {"name": "T178 fon detali", "category": "panel", "width": 50, "thickness": 5, "quantity": 3, "unit_price": 10000, "is_coated": False}]})
    _oid, _oi = js(_r)["id"], js(_r)["items"][0]["id"]
    FON.clear()
    _d = sorov("POST", "/api/deliveries", {"order_id": _oid, "items": [{"order_item_id": _oi, "quantity": 1}], "received_by": None,
                                         "notes": None, "transport_carrier": None, "transport_cost": 0, "transport_payer": "none",
                                         "payment_amount": None, "payment_method": "naqd"})
    _javob_vaqti = time.time()
    time.sleep(2.5)
    _fon = list(FON)
    check("T5a yuk xati: javob Telegramni KUTMAYDI (< 0,8 s; ilgari ≥ 1,5 s), xabar va PDF javobdan KEYIN yuborildi",
          _d[0] == 200 and _d[2] < 0.8 and len(_fon) == 2 and all(x[1] >= _javob_vaqti - 0.05 for x in _fon), (_d[0], round(_d[2], 2), _fon))
    check("T5b fon vazifasidagi PDF — o'z sessiyasi bilan (yetkazish raqami o'qildi)",
          any(x[0] == "pdf" and x[2] and not str(x[2]).startswith("XATO") for x in _fon), _fon)
    _r = C.post("/api/orders?confirm_shortage=true", json={"project_id": ID["PRJ"], "order_type": "product", "items": [
        {"name": "T178 tayyor detali", "category": "panel", "width": 50, "thickness": 5, "quantity": 2, "unit_price": 10000, "is_coated": False}]})
    _oid2 = js(_r)["id"]
    # mijoz Telegram ID si (loyiha izohida) — «Tayyor» da mijozga xabar (`_send_telegram_to`) ham ketadi
    db_ishi(lambda d: setattr(d.get(Project, ID["PRJ"]), "notes", "tg_id=999178"))
    main._send_telegram_to = lambda chat_id, text, company_id=None: (time.sleep(1.0), FON.append(("mijoz", time.time())))
    FON.clear()
    _t = sorov("POST", f"/api/orders/{_oid2}/ready")
    _javob_vaqti = time.time()
    time.sleep(2.5)
    _fon = list(FON)
    check("T5c «Tayyor»: javob mijoz Telegramini kutmaydi (< 0,8 s; ilgari ≥ 1 s), mijozga xabar javobdan KEYIN",
          _t[0] == 200 and _t[2] < 0.8 and any(x[0] == "mijoz" and x[1] >= _javob_vaqti - 0.05 for x in _fon),
          (_t[0], _t[1][:160], round(_t[2], 2), _fon))
finally:
    main._send_telegram = _asl_send
    main._send_telegram_to = _asl_send_to
    main._send_delivery_pdf_to_customer = _asl_pdf_m
    db_ishi(lambda d: setattr(d.get(Project, ID["PRJ"]), "notes", None))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H1 / H2 / H3. Hodim paneli va ruxsat kutish sahifasi (Chromium)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"


def hodim(nom, tel, holat):
    eid = js(C.post("/api/employees", json={"name": nom, "position": "Kesuvchi", "pay_type": "fixed", "fixed_amount": 5_000_000})).get("id")
    C.post(f"/api/employees/{eid}/set-login", data={"phone": tel, "pin": "4321"})
    kalit = (nom.replace(" ", "") + "K" * 43)[:43]
    qh = auth.qurilma_hash_ol(kalit)

    def f(d):
        e = d.get(Employee, eid)
        e.hire_date = datetime(2024, 1, 1)
        e.pin_vaqtinchalik = False
        if holat == "tayyor":
            e.qurilma_hash = qh
        else:
            e.qurilma_hash = None
            e.qurilma_sorov_hash = qh
    db_ishi(f)
    tok = db_ishi(lambda d: auth.create_employee_session(d, eid, qh))
    return eid, tok, kalit


EH, EH_TOK, EH_KALIT = hodim("T178 Hodim", "+998901781781", "tayyor")
EK, EK_TOK, EK_KALIT = hodim("T178 Kutuvchi", "+998901781782", "kutish")
_kun = datetime.utcnow().strftime("%Y-%m-%d")
AV1 = js(C.post(f"/api/employees/{EH}/advance?amount=205000&notes=karta&adv_date={_kun}")).get("id")
AV2 = js(C.post(f"/api/employees/{EH}/advance?amount=50000&adv_date={_kun}")).get("id")
JS_XATO = []
SAHIFA_502 = {"status": 502, "content_type": "text/html", "body": "<html><body><h1>502 Bad Gateway</h1></body></html>"}

if PW_BOR and server.started:
    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def hkontekst(tok, kalit):
            ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ")
            ctx.set_default_timeout(15000)
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
            ctx.add_cookies([{"name": "emp_session_token", "value": tok, "domain": "127.0.0.1", "path": "/"},
                             {"name": auth.QURILMA_COOKIE, "value": kalit, "domain": "127.0.0.1", "path": "/"}])
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
            return ctx, pg

        def matn(pg, sel):
            try:
                return pg.evaluate(f"() => {{ const e = document.querySelector({json.dumps(sel)}); return e ? e.innerText : null; }}")
            except Exception:              # noqa: BLE001
                return None

        ctx, pg = hkontekst(EH_TOK, EH_KALIT)
        try:
            pg.route("**/api/hodim/my-requests", lambda r: r.fulfill(**SAHIFA_502))
            pg.goto(B + "/hodim", wait_until="networkidle")
            pg.wait_for_timeout(500)
            _rl = matn(pg, "#req-list") or ""
            check("H1a «So'rovlarim» 502 — «Yuklanmadi — server javob bermadi (502)» + «🔄 Qayta yuklash» (ilgari «Yuklashda xato»)",
                  "server javob bermadi (502)" in _rl and "Qayta yuklash" in _rl, _rl[:200])
            pg.unroute("**/api/hodim/my-requests")
            pg.route("**/api/hodim/my-requests", lambda r: r.fulfill(status=403, content_type="application/json",
                                                                      body=json.dumps({"detail": "Korxona vaqtincha bloklangan (sinov)"})))
            pg.evaluate("() => { loadMyRequests(); }")
            pg.wait_for_timeout(700)
            _rl = matn(pg, "#req-list") or ""
            check("H1b 403 — serverning sababi ko'rinadi («Korxona vaqtincha bloklangan»), sahifa almashmaydi",
                  "Korxona vaqtincha bloklangan" in _rl and pg.url.rstrip("/").endswith("/hodim"), (_rl[:200], pg.url))
            pg.unroute("**/api/hodim/my-requests")
            pg.route("**/api/hodim/oylik", lambda r: r.abort())
            pg.evaluate("() => { loadOylik(); }")
            pg.wait_for_timeout(700)
            _ol = matn(pg, "#oylik-list") or ""
            check("H1c «Oyligim» internet uzilsa — «Yuklanmadi — internet aloqasi yo'q» + «🔄»", "internet aloqasi yo'q" in _ol
                  and "Qayta yuklash" in _ol, _ol[:200])
            pg.unroute("**/api/hodim/oylik")
            pg.evaluate("() => { loadOylik(); }")
            pg.wait_for_timeout(900)

            # H2 — javob saqlandi, ro'yxat yangilanmadi
            pg.route("**/api/hodim/oylik", lambda r: r.fulfill(**SAHIFA_502))
            pg.evaluate(f"""() => {{ const b = document.querySelector('#javob-list .javob-blok[data-id="{AV1}"]');
                window.__h2 = !!b; if (b) javobYubor(b, 'oldim'); }}""")
            pg.wait_for_timeout(1200)
            _jl, _jm = matn(pg, "#javob-list") or "", matn(pg, "#javob-msg") or ""
            check("H2 javob saqlandi, ro'yxat yangilanmadi (502) — «Rahmat …» xabari qoladi, ro'yxat o'rnida «Ro'yxat yangilanmadi — sabab» "
                  "(ilgari «Hamma to'lovlarga javob berdingiz» — qolgan to'lov tugmalari yo'qolardi)",
                  pg.evaluate("() => window.__h2") and "Rahmat" in _jm and "Ro'yxat yangilanmadi" in _jl and "server javob bermadi" in _jl
                  and "Hamma to'lovlarga javob berdingiz" not in _jl, (_jm, _jl[:200]))
            pg.unroute("**/api/hodim/oylik")

            # H1 — sessiya tugagan (401) → `/hodim`
            _nav = []
            pg.on("framenavigated", lambda f: _nav.append(f.url) if f == pg.main_frame else None)
            _bir = {"n": 0}

            def _bir_marta_401(r):
                _bir["n"] += 1
                if _bir["n"] == 1:
                    r.fulfill(status=401, content_type="application/json", body=json.dumps({"detail": "Iltimos, tizimga kiring"}))
                else:
                    r.continue_()
            pg.route("**/api/hodim/my-requests", _bir_marta_401)
            pg.evaluate("() => { loadMyRequests(); }")
            pg.wait_for_timeout(2000)
            check("H1d sessiya tugagan (401) — `/hodim` ga o'tadi (server kirish / PIN / kutish sahifasini tanlaydi; ilgari «Yuklashda xato» "
                  "va qayta yuklash abadiy yiqilardi)", any(u.rstrip("/").endswith("/hodim") for u in _nav), _nav)
            pg.unroute("**/api/hodim/my-requests")
        except Exception as _x:           # noqa: BLE001 — asl kodda yo'q funksiya: bo'lim yiqiladi, sinov QULAMAYDI
            check("H1 / H2 bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
        finally:
            ctx.close()

        ctx, pg = hkontekst(EK_TOK, EK_KALIT)
        try:
            pg.route("**/api/hodim/qurilma-holati", lambda r: r.fulfill(**SAHIFA_502))
            pg.goto(B + "/hodim", wait_until="networkidle")
            pg.wait_for_timeout(5200)
            _kh = matn(pg, "#kutishHolat") or ""
            check("H3 ruxsat kutish sahifasi 502 — «Server javob bermadi (502)» (ilgari «Internet aloqasi yo'q»)",
                  "Server javob bermadi (502)" in _kh, _kh)
            pg.unroute("**/api/hodim/qurilma-holati")
            pg.route("**/api/hodim/qurilma-holati", lambda r: r.abort())
            pg.wait_for_timeout(4500)
            _kh = matn(pg, "#kutishHolat") or ""
            check("H3b internet uzilsa — avvalgidek «Internet aloqasi yo'q»", "Internet aloqasi yo'q" in _kh, _kh)
        except Exception as _x:           # noqa: BLE001
            check("H3 bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
        finally:
            ctx.close()
        br.close()
else:
    check("H0 Chromium bor", False, _pw_x)

section("Z. Sahifa xatolari")
check("Z1 hodim sahifalarida ushlanmagan JS xatosi yo'q", not JS_XATO, JS_XATO[:5])
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
