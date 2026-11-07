#!/usr/bin/env python3
"""
test_cron_sarlavha268.py — kech204 (zip 268): xavfsizlik REJA263 18-band (Fable F14) — cron maxfiy kaliti FAQAT `X-Cron-Secret`
sarlavhasida.

NIMA UCHUN KERAK (zip 267 gacha — O'LCHANDI shu testning B bo'limida, asl kodda yiqiladi):
  `GET /api/cron/low-stock-check` va `GET /api/cron/cleanup-sessions` kalitni manzil ichida ham (`?secret=…`) qabul qilardi —
  manzil proksi, Railway va cron-job.org jurnallarida qoladi, ya'ni kalit begona jurnalga yozilardi. Egasi 07.11 14:07 da
  cron-job.org dagi ikkala vazifani sarlavhaga o'tkazdi (Test run — 200). Endi:
  * kalit faqat `X-Cron-Secret` sarlavhasida;
  * manzilda `secret` parametri bo'lsa (qiymati to'g'ri bo'lsa ham, sarlavha to'g'ri bo'lsa ham, bo'sh bo'lsa ham) — 403 va aniq
    sabab (`main.CRON_MANZIL_SIR_MATNI`); hech qanday ish (Telegram xabari, sessiya o'chirish) BAJARILMAYDI;
  * kalit o'rnatilmagan — 503 (avvalgidek).
BO'LIMLAR: A — sarlavha bilan ishlash; B — manzildagi kalit rad etiladi (asl kodda yiqiladi); C — rad etilganda ish bajarilmaydi
           (asl kodda yiqiladi); D — kalit o'rnatilmagan (503); E — marshrut ta'rifi (OpenAPI da `secret` parametri yo'q).
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (c93eec0 — zip 267b) qarshi YIQILADI, QULAMAYDI.
ISHLATISH: python3 tools/test_cron_sarlavha268.py
"""
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "cron268_test"
_T = tempfile.mkdtemp(prefix="cron268_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'cron268_test.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "ADMIN_PASSWORD", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)
SIR = "Cron-Sinov-268-" + uuid.uuid4().hex
os.environ["CRON_SECRET"] = SIR

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import tenant_context                              # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, UserSession, Inventory   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def detail(r):
    return str(js(r).get("detail", ""))


main.CRON_SECRET = SIR          # modul import paytida o'qiladi — aniq bo'lishi uchun yana qo'yiladi
YANGI_KOD = hasattr(main, "CRON_MANZIL_SIR_MATNI")
MANZIL_MATNI = getattr(main, "CRON_MANZIL_SIR_MATNI", "Maxfiy kalit manzilda qabul qilinmaydi")
LS = "/api/cron/low-stock-check"
CS = "/api/cron/cleanup-sessions"
YOLLAR = (LS, CS)
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
H_TOGRI = {"X-Cron-Secret": SIR}

TG = []
_asl_tg = main._send_telegram
main._send_telegram = lambda matn, company_id=None: TG.append((company_id, matn))

# Tayyorlov: foydalanuvchi (eskirgan sessiya uchun), kam qolgan material (Telegram xabari uchun)
PAROL = "Kuchli-Sinov-Parol-268"
s = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "cron268_menejer", PAROL, UserRole.MANAGER, "Cron Menejer", company_id=1)
s.close()
d = SessionLocal()
with tenant_context.system_context(d):
    UID = d.query(User.id).execution_options(skip_tenant_filter=True).filter(User.username == "cron268_menejer").scalar()
    KAM_NOM = f"Cron268 kam material {uuid.uuid4().hex[:6]}"
    d.add(Inventory(company_id=1, item_name=KAM_NOM, unit="kg", stock_quantity=1, min_stock=10))
    d.commit()
d.close()


def eski_sessiya_qosh():
    """Muddati o'tgan sessiya — `cleanup-sessions` uni o'chirishi kerak. Token (xesh shaklida, 64 belgi) qaytariladi."""
    tok = uuid.uuid4().hex + uuid.uuid4().hex
    db = SessionLocal()
    with tenant_context.system_context(db):
        db.add(UserSession(token=tok, user_id=UID, expires_at=datetime.utcnow() - timedelta(days=3)))
        db.commit()
    db.close()
    return tok


def sessiya_bormi(tok):
    db = SessionLocal()
    try:
        with tenant_context.system_context(db):
            return db.query(UserSession).execution_options(skip_tenant_filter=True).filter(UserSession.token == tok).first() is not None
    finally:
        db.close()


def kam_xabar_bormi():
    return any(KAM_NOM in matn for _cid, matn in TG)


# ══════════════════════════════════════════════════════════════
section("A. Kalit `X-Cron-Secret` sarlavhasida — ishlaydi (avvalgidek)")
# ══════════════════════════════════════════════════════════════
TG.clear()
r = C.get(LS, headers=H_TOGRI)
check("A1 low-stock-check — to'g'ri sarlavha — 200, sent: true, kam material xabarda", r.status_code == 200
      and js(r).get("sent") is True and kam_xabar_bormi(), (r.status_code, r.text[:200], TG[:2]))
_tok = eski_sessiya_qosh()
r = C.get(CS, headers=H_TOGRI)
check("A2 cleanup-sessions — to'g'ri sarlavha — 200, cleaned: true, eskirgan sessiya o'chdi", r.status_code == 200
      and js(r).get("cleaned") is True and not sessiya_bormi(_tok), (r.status_code, r.text[:200]))
r = C.get(CS, headers={"x-cron-secret": SIR})
check("A3 sarlavha nomi kichik harfda — 200 (HTTP sarlavha nomi katta-kichik harf farqisiz)", r.status_code == 200,
      (r.status_code, r.text[:160]))
for _y in YOLLAR:
    r = C.get(_y, headers={"X-Cron-Secret": "xato"})
    check(f"A4 {_y} — noto'g'ri sarlavha — 403 «Noto'g'ri maxfiy kalit»", r.status_code == 403
          and detail(r) == "Noto'g'ri maxfiy kalit", (r.status_code, r.text[:160]))
    r = C.get(_y)
    check(f"A5 {_y} — sarlavha ham, manzil ham yo'q — 403", r.status_code == 403
          and detail(r) == "Noto'g'ri maxfiy kalit", (r.status_code, r.text[:160]))
    r = C.get(_y, headers={"X-Cron-Secret": SIR + "x"})
    check(f"A6 {_y} — kalit + ortiqcha belgi — 403", r.status_code == 403, (r.status_code, r.text[:160]))
    r = C.get(_y, headers={"X-Cron-Secret": SIR[:-1]})
    check(f"A7 {_y} — kalitning bir qismi — 403", r.status_code == 403, (r.status_code, r.text[:160]))
    r = C.get(_y, headers={"X-Cron-Secret": SIR.upper()})
    check(f"A8 {_y} — kalit katta harflarda (qiymat katta-kichik harfga sezgir) — 403", r.status_code == 403,
          (r.status_code, r.text[:160]))
r = C.get(CS, headers=H_TOGRI, params={"boshqa": "1"})
check("A9 boshqa so'rov parametri xalaqit bermaydi — to'g'ri sarlavha bilan 200", r.status_code == 200, (r.status_code, r.text[:160]))
r = C.post(CS, headers=H_TOGRI)
check("A10 POST qabul qilinmaydi (faqat GET) — 405", r.status_code == 405, (r.status_code, r.text[:160]))

# ══════════════════════════════════════════════════════════════
section("B. Kalit manzilda (`?secret=`) — RAD (asl kodda 200)")
# ══════════════════════════════════════════════════════════════
for _y in YOLLAR:
    r = C.get(f"{_y}?secret={SIR}")
    check(f"B1 {_y} — to'g'ri kalit FAQAT manzilda — 403 + aniq sabab (asl: 200)", r.status_code == 403
          and detail(r) == MANZIL_MATNI and YANGI_KOD, (r.status_code, r.text[:200]))
    r = C.get(f"{_y}?secret={SIR}", headers=H_TOGRI)
    check(f"B2 {_y} — to'g'ri sarlavha + manzilda ham kalit — 403 (kalit manzilda qolmasin; asl: 200)", r.status_code == 403
          and detail(r) == MANZIL_MATNI and YANGI_KOD, (r.status_code, r.text[:200]))
    r = C.get(f"{_y}?secret=", headers=H_TOGRI)
    check(f"B3 {_y} — manzilda bo'sh `secret=` + to'g'ri sarlavha — 403 (asl: 200)", r.status_code == 403
          and detail(r) == MANZIL_MATNI and YANGI_KOD, (r.status_code, r.text[:200]))
    r = C.get(_y, params={"secret": "xato"})
    check(f"B4 {_y} — manzilda noto'g'ri kalit — 403 manzil sababi bilan (kalit tekshirilmaydi ham)", r.status_code == 403
          and detail(r) == MANZIL_MATNI and YANGI_KOD, (r.status_code, r.text[:200]))
    r = C.get(f"{_y}?boshqa=1&secret={SIR}", headers=H_TOGRI)
    check(f"B5 {_y} — `secret` boshqa parametrlardan keyin ham — 403 (asl: 200)", r.status_code == 403
          and detail(r) == MANZIL_MATNI and YANGI_KOD, (r.status_code, r.text[:200]))
    r = C.get(f"{_y}?secret={SIR}")
    check(f"B6 {_y} — rad javobida kalitning o'zi YO'Q", SIR not in r.text, r.text[:200])
check("B7 sabab matni — o'zbekcha, sarlavha nomini aytadi (`X-Cron-Secret`), manzildan olib tashlashni aytadi",
      "X-Cron-Secret" in MANZIL_MATNI and "manzil" in MANZIL_MATNI and YANGI_KOD, MANZIL_MATNI)

# ══════════════════════════════════════════════════════════════
section("C. Manzildagi kalit bilan ISH BAJARILMAYDI (asl kodda bajarilardi)")
# ══════════════════════════════════════════════════════════════
TG.clear()
r = C.get(f"{LS}?secret={SIR}")
check("C1 low-stock-check ?secret= — Telegram xabari YUBORILMADI", r.status_code == 403 and not TG, (r.status_code, TG[:2]))
r = C.get(f"{LS}?secret={SIR}", headers=H_TOGRI)
check("C2 low-stock-check ?secret= + to'g'ri sarlavha — Telegram xabari YUBORILMADI", r.status_code == 403 and not TG,
      (r.status_code, TG[:2]))
_tok = eski_sessiya_qosh()
r = C.get(f"{CS}?secret={SIR}")
check("C3 cleanup-sessions ?secret= — eskirgan sessiya O'CHIRILMADI", r.status_code == 403 and sessiya_bormi(_tok),
      (r.status_code, r.text[:160]))
r = C.get(f"{CS}?secret={SIR}", headers=H_TOGRI)
check("C4 cleanup-sessions ?secret= + to'g'ri sarlavha — eskirgan sessiya O'CHIRILMADI", r.status_code == 403
      and sessiya_bormi(_tok), (r.status_code, r.text[:160]))
r = C.get(CS, headers={"X-Cron-Secret": "xato"})
check("C5 noto'g'ri sarlavha — sessiya O'CHIRILMADI", r.status_code == 403 and sessiya_bormi(_tok), (r.status_code, r.text[:160]))
r = C.get(CS, headers=H_TOGRI)
check("C6 nazorat: keyin to'g'ri sarlavha bilan — 200, sessiya o'chdi", r.status_code == 200 and not sessiya_bormi(_tok),
      (r.status_code, r.text[:160]))
TG.clear()
r = C.get(LS, headers=H_TOGRI)
check("C7 nazorat: low-stock-check to'g'ri sarlavha — xabar ketdi", r.status_code == 200 and kam_xabar_bormi(),
      (r.status_code, TG[:2]))

# ══════════════════════════════════════════════════════════════
section("D. Kalit o'rnatilmagan — 503 (avvalgidek), manzil / sarlavhadan qat'i nazar")
# ══════════════════════════════════════════════════════════════
main.CRON_SECRET = ""
TG.clear()
for _y in YOLLAR:
    r = C.get(_y)
    check(f"D1 {_y} — hech narsasiz — 503", r.status_code == 503 and "CRON_SECRET" in detail(r), (r.status_code, r.text[:160]))
    r = C.get(_y, headers={"X-Cron-Secret": ""})
    check(f"D2 {_y} — bo'sh sarlavha (bo'sh kalit bilan «teng» emas) — 503", r.status_code == 503, (r.status_code, r.text[:160]))
    r = C.get(f"{_y}?secret=", headers=H_TOGRI)
    check(f"D3 {_y} — manzilda kalit + sarlavha — 503 (avval sozlama tekshiriladi)", r.status_code == 503,
          (r.status_code, r.text[:160]))
check("D4 kalit o'rnatilmagan — Telegram xabari yo'q", not TG, TG[:2])
main.CRON_SECRET = SIR

# ══════════════════════════════════════════════════════════════
section("E. Marshrut ta'rifi")
# ══════════════════════════════════════════════════════════════
_oa = main.app.openapi()
for _y in YOLLAR:
    _par = [p.get("name") for p in ((_oa.get("paths", {}).get(_y, {}) or {}).get("get", {}) or {}).get("parameters", [])]
    check(f"E1 {_y} — OpenAPI da `secret` so'rov parametri YO'Q (asl: bor)", _y in _oa.get("paths", {}) and "secret" not in _par,
          _par)
import inspect as _ins                             # noqa: E402
_imzo = _ins.signature(main._cron_sirini_tekshir)
check("E2 `_cron_sirini_tekshir` faqat `request` oladi (manzildagi kalit uzatilmaydi)", list(_imzo.parameters) == ["request"],
      list(_imzo.parameters))
_manba = _ins.getsource(main._cron_sirini_tekshir)
check("E3 solishtiruv doimiy vaqtli (`compare_digest`) qoldi", "compare_digest" in _manba, _manba[-400:])

main._send_telegram = _asl_tg
print(f"\nNATIJA: o'tdi = {OK}, yiqildi = {FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
