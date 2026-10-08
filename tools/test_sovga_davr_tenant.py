#!/usr/bin/env python3
"""
test_sovga_davr_tenant.py — kech108, K107-1 darvozasi: Telegram usta boti «🎁 Sovg'alar» ikki korxonada.

NIMA UCHUN KERAK (O'LCHANGAN — shu test ASL kodga qarshi): `/telegram/webhook` "/sovgalar" shoxi
`crud.get_master_gift_period_progress(db, master.id)` ni korxonasiz chaqirardi → `get_active_gift_period(db, None)` butun
tizimdagi BIRINCHI faol davrni olardi. Ikkala korxonada faol davr bo'lsa, ikkinchi korxona ustasi (o'z davrida ishtirok
etsa ham) "🎁 Hozircha faol sovg'a davri yo'q" olardi.

  1 — webhook (HAQIQIY marshrut, Telegram yuborish yozib olinadi): A ustasi — A davri bosqichlari (A_SOVGA), B ustasi —
      B davri bosqichlari (B_SOVGA), "faol davr yo'q" YO'Q; hech biri boshqa korxona sovg'a nomini ko'rmaydi.
      kech130 (zip 154, MOSLANDI — egasi QARORI 08.10 «@Penoustabot faqat men uchun»): umumiy bot (`/telegram/webhook`) endi
      FAQAT platforma korxonasi ustalariga; B ustasi o'z korxonasi botidan (`/telegram/webhook/2`, B siri) yozadi va javob
      B tokeni bilan keladi; umumiy botda B ustasi — noma'lum (B_SOVGA YO'Q).
  2 — funksiya: korxona bilan — o'z davri; korxonasiz — `active: False` (begona davr taxmin qilinmaydi).
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "sovga_davr_tenant_test"
_DB = os.path.join(tempfile.gettempdir(), "sovga_davr_tenant_test.db")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "SOVGA_SECRET"
os.environ["TELEGRAM_BOT_TOKEN"] = "SOVGA_BOT"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import Master                          # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond)
    except Exception:                      # noqa: BLE001
        cond = False
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:300]}")


def section(t):
    print(f"\n--- {t} ---")


YUBORILGAN = []


TOKENLAR = []      # kech130: har javob qaysi bot tokeni bilan ketdi (YUBORILGAN bilan parallel)


def _yoz(*a, **k):
    # _tg_post_message(token, chat_id, text, reply_markup=…) / _send_telegram_to(chat_id, text, company_id=…)
    matn = k.get("text")
    if matn is None:
        matn = a[2] if len(a) >= 3 else (a[1] if len(a) >= 2 else "")
    chat = a[1] if len(a) >= 3 else (a[0] if a else None)
    YUBORILGAN.append((str(chat), str(matn)))
    TOKENLAR.append(str(a[0]) if len(a) >= 3 else None)
    return True


main._tg_post_message = _yoz
main._send_telegram_to = _yoz
main._send_telegram = lambda *a, **k: None

db = SessionLocal()
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="Sovga B korxona"))
    db.commit()
MA = Master(company_id=1, name="SOVGA_A_USTA", phone="+998900000801", telegram_id="880001", is_active=True)
MB = Master(company_id=2, name="SOVGA_B_USTA", phone="+998900000802", telegram_id="880002", is_active=True)
db.add_all([MA, MB])
db.commit()
# kech130: B korxonaning o'z boti ULANGAN (ulash natijasi — sozlamada token, sir, manzil)
crud.set_setting(db, "telegram_bot_token", "SOVGA_B_BOT", company_id=2)
crud.set_setting(db, "telegram_webhook_secret", "SOVGA_B_SIR", company_id=2)
crud.set_setting(db, "telegram_webhook_url", "https://testserver/telegram/webhook/2", company_id=2)
MA_ID, MB_ID = MA.id, MB.id
_xato = None
try:
    with contextlib.redirect_stdout(_quiet):
        # A davri AVVAL ochiladi — korxonasiz so'rovda "birinchi faol davr" aynan A niki bo'ladi
        crud.open_gift_period(db, [{"gift_name": "A_SOVGA_1", "threshold_amount": 1000000}], master_ids=[MA_ID],
                              performed_by="t", company_id=1)
        crud.open_gift_period(db, [{"gift_name": "B_SOVGA_1", "threshold_amount": 2000000}], master_ids=[MB_ID],
                              performed_by="t", company_id=2)
except Exception as e:                     # noqa: BLE001
    _xato = f"{type(e).__name__}: {e}"
db.close()

section("0. Fikstura")
s = SessionLocal()
try:
    _pa = crud.get_active_gift_period(s, 1)
    _pb = crud.get_active_gift_period(s, 2)
finally:
    s.close()
check("ikkala korxonada faol davr (A — avval ochilgan), ustalar ishtirokchi", _xato is None and _pa is not None and _pb is not None,
      _xato)

WH = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)


def wh(chat, text, yol="/telegram/webhook", sir="SOVGA_SECRET"):
    YUBORILGAN.clear()
    TOKENLAR.clear()
    with contextlib.redirect_stdout(_quiet):
        r = WH.post(yol, json={"message": {"chat": {"id": int(chat)}, "text": text}},
                    headers={"X-Telegram-Bot-Api-Secret-Token": sir})
    return r.status_code, [t for ch, t in YUBORILGAN if ch == str(chat)]


section("1. Webhook /sovgalar")
st, t = wh("880002", "/sovgalar", yol="/telegram/webhook/2", sir="SOVGA_B_SIR")
_b = " | ".join(t)
_bt = list(TOKENLAR)
check("1.1 B ustasi (o'z korxonasi boti) → 200, javob bor", st == 200 and len(t) >= 1, (st, t))
check("1.2 B ustasi — o'z davri (B_SOVGA_1), 'faol sovg'a davri yo'q' YO'Q (asl: YO'Q deb javob)",
      "B_SOVGA_1" in _b and "faol sovg'a davri yo'q" not in _b, _b[:300])
check("1.3 B ustasi A korxona sovg'asini ko'rmaydi (A_SOVGA_1 YO'Q)", "A_SOVGA_1" not in _b, _b[:300])
check("1.3b kech130: javob B ning O'Z boti tokeni bilan (SOVGA_B_BOT), umumiy bot tokeni bilan EMAS",
      _bt and all(x == "SOVGA_B_BOT" for x in _bt), _bt)
st, t = wh("880001", "/sovgalar")
_a = " | ".join(t)
check("1.4 A ustasi — o'z davri (A_SOVGA_1), B_SOVGA_1 YO'Q", st == 200 and "A_SOVGA_1" in _a and "B_SOVGA_1" not in _a, _a[:300])
st, t = wh("880002", "/sovgalar")
_bu = " | ".join(t)
check("1.5 kech130 (egasi QARORI): B ustasi UMUMIY botda — noma'lum ('topilmadingiz'), B_SOVGA_1 va B usta ismi YO'Q",
      st == 200 and "topilmadingiz" in _bu and "B_SOVGA_1" not in _bu and "SOVGA_B_USTA" not in _bu, _bu[:300])

section("2. Funksiya")
s = SessionLocal()
try:
    pb = crud.get_master_gift_period_progress(s, MB_ID, company_id=2)
    pa = crud.get_master_gift_period_progress(s, MA_ID, company_id=1)
    px = crud.get_master_gift_period_progress(s, MB_ID, company_id=1)
    pn = crud.get_master_gift_period_progress(s, MB_ID)
    pna = crud.get_master_gift_period_progress(s, MA_ID)
finally:
    s.close()
check("2.1 B ustasi, korxona 2 — active, B davri", pb.get("active") is True and pb.get("period_id") == getattr(_pb, "id", -1), pb)
check("2.2 A ustasi, korxona 1 — active, A davri", pa.get("active") is True and pa.get("period_id") == getattr(_pa, "id", -1), pa)
check("2.3 B ustasi, begona korxona 1 — active: False", px.get("active") is False, px)
check("2.4 korxonasiz chaqiruv — active: False (begona / birinchi davr taxmin qilinmaydi)", pn.get("active") is False, pn)
check("2.5 korxonasiz chaqiruv A ustasi uchun ham — active: False (asl: tizimdagi birinchi davr A niki → active True)",
      pna.get("active") is False, pna)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
