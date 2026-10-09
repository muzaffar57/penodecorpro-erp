#!/usr/bin/env python3
"""
test_hodim_avans_tasdiq.py — kech134 (zip 160): hodim avanslari — manba belgisi, admin yozgan avansga hodim javobi («✅ Ha, oldim /
❌ Olmaganman»), «Olmaganman» nizosi (admin ogohlantirishi, «✔ Ko'rib chiqdim», o'chirish), «Mening so'rovlarim» — 12 oy, tasdiq
poygasi, bir martalik migratsiya — SERVER va SHABLONLAR (statik).

NIMA UCHUN KERAK (egasi 09.10 14:50 va QARORLARI, tugmali)
-------------------------------------------------------------------------------------------------------------------
  O'LCHANGAN (zip 159 kodi): `EmployeeAdvance` da manba yo'q — hodim panelidagi «Oyligim» da admin yozgan va hodim o'zi so'ragan
  to'lov farqlanmaydi (Ulug'bek: so'rovlari 980 000, «Olingan» 1 185 000 — farq 205 000 admin yozgan); `get_employee_own_requests`
  oxirgi 20 ta (eskilari umuman chiqmasdi); tasdiqlangan so'rov avansi o'chirilsa so'rov «✅ Tasdiqlandi» bo'lib qolardi;
  `confirm_advance_request` / `reject` qatorni qulflamasdi — HAQIQIY PG da parallel ikki tasdiq IKKI avans yozdi, tasdiq + rad —
  ikkalasi «bajarildi» (`work/k160/poyga_tasdiq.py`).
  EGASI QARORLARI: «Mening so'rovlarim» — joriy oy ochiq, o'tgan oylar yopiq, 12 oy, kutilayotgan — doim birinchi; avans manbasi —
  «C — hodim tasdig'i bilan»: belgilar («📱 O'zingiz» / «🧑‍💼 Admin»), admin yozgan avansga hodim «Ha, oldim / Olmaganman»,
  «Olmaganman» — adminga ogohlantirish (Bosh sahifa / KPI), avans hisobda DARHOL turadi; zip 160 dan oldingi admin avanslari —
  «Faqat joriy oy» tasdiqqa chiqadi.

BO'LIMLAR
  A — manba va savol: admin KPI avansi (panelga kira oladigan / kira olmaydigan hodim), Qarzdorlar «oylikni yopish», hodim so'rovi
      tasdig'i (so'rovga avans bog'lanadi); hodim «Oyligim» — belgi, kim, izoh (tizim qo'shimchasisiz), javob; «🔔» ro'yxati;
  B — hodim javobi: oldim / olmadim (Telegram, jurnal), takror / ruxsatsiz o'tishlar 409, «olmadim» → «oldim», so'ralmagan, boshqa
      hodimniki 404, noto'g'ri tana 400, sessiyasiz 401, vaqtinchalik PIN 403; avans hisobda o'zgarmaydi;
  C — admin: nizolar ro'yxati, `/api/employees` holati, «Ko'rib chiqdim» (takror 409), ruxsat, boshqa korxona, o'chirish (jurnal),
      o'chirilgan hodim;
  D — «Mening so'rovlarim»: 20 tadan ko'p, 12 oy oynasi, eski KUTILAYOTGAN, `oy`, avansi o'chirilgan so'rov, boshqa hodim, tartib;
  E — migratsiya (`main._migrate_avans_manba`): eski yozuvlar manbasi, faqat joriy oy va panelga kira oladigan hodim, so'rov ↔ avans
      bog'lash (juftlash, o'chirilgan), takror ishga tushish, eski bazada ustunlar (`sync_missing_columns`);
  F — PG poyga (faqat PG): parallel ikki tasdiq — bitta avans; tasdiq + rad — faqat bittasi;
  G — shablonlar (statik): hodim paneli, umumiy hodim oynalari (Bosh sahifa va Dashboard), KPI.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 159) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_hodim_avans_tasdiq.py
"""
import os
import re
import sys
import tempfile
import threading
import time

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hodim_avans_tasdiq160_test"
_DB = os.path.join(tempfile.gettempdir(), "hodim_avans_tasdiq160_test.db")
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
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime, timedelta           # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402
    import database                                # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, Employee, EmployeeAdvance, AdvanceRequest, AdvanceRequestStatus,   # noqa: E402
                    ActivityLog)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import text as sql_text            # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
QOSHIMCHA = " (xodim o'zi yozgan, admin tasdiqladi)"


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
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def royxat(r):
    """Javob ro'yxat bo'lsa — o'zi, aks holda (asl kodda 404 `{"detail": …}`) — bo'sh ro'yxat (sinov QULAMASIN)."""
    d = js(r)
    return d if isinstance(d, list) else []


def oqi(f):
    try:
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


BUGUN = tashkent_date()


def oy_oldin(n):
    """Bugungi (Toshkent) oydan n oy oldingi (yil, oy) — sinovning O'Z hisobi."""
    k = BUGUN.year * 12 + (BUGUN.month - 1) - n
    return k // 12, k % 12 + 1


def sana(n, kun=10, soat=7):
    """n oy oldingi oyning `kun` kuni (UTC, naive; Toshkent soat+5) — kun oy uzunligidan oshmaydi."""
    y, m = oy_oldin(n)
    return datetime(y, m, min(kun, 28), soat, 0)


def oy_kalit(n):
    y, m = oy_oldin(n)
    return f"{y:04d}-{m:02d}"


_IP = {"n": 30}


def mijoz():
    _IP["n"] += 1
    try:
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False,
                       client=(f"203.0.113.{_IP['n']}", 50000))
    except TypeError:
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.headers["user-agent"] = ("Mozilla/5.0 (Linux; Android 13; SM-A525F) AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0.0.0 Mobile Safari/537.36")
    return c


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def avans_ol(aid):
    def f(s):
        a = s.query(EmployeeAdvance).filter(EmployeeAdvance.id == aid).first()
        if a is None:
            return None
        return {k: getattr(a, k, "YO'Q") for k in ("employee_id", "amount", "notes", "given_by", "avans_manba", "hodim_javobi",
                                                     "hodim_javob_vaqti", "nizo_korildi_vaqti", "nizo_korgan", "date")}
    return db_ishi(f)


def sorov_ol(rid):
    def f(s):
        r = s.query(AdvanceRequest).filter(AdvanceRequest.id == rid).first()
        if r is None:
            return None
        return {k: getattr(r, k, "YO'Q") for k in ("status", "avans_id", "avans_ochirildi_vaqti", "avans_ochirgan")}
    return db_ishi(f)


def faoliyat(eid, amal):
    return db_ishi(lambda s: s.query(ActivityLog).filter(ActivityLog.entity_type == "employee", ActivityLog.entity_id == eid,
                                                         ActivityLog.action == amal).count())


def avanslar(eid):
    return db_ishi(lambda s: [a.id for a in s.query(EmployeeAdvance).filter(EmployeeAdvance.employee_id == eid)
                              .order_by(EmployeeAdvance.id).all()])


# ══════════════════════════════════════════════════════════════
# Fikstura: 1-korxona admini (A), «Hodimlar: Ko'rish» xolos roli foydalanuvchisi (K), 2-korxona admini (B);
# hodimlar: U (panelga kiradi), Q (panelga kiradi), N (telefon / PIN yo'q), P (vaqtinchalik PIN — 403), X (2-korxona)
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ikkinchi Korxona", code="IKKINCHI-160"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "ha_admin", "Parol123!", UserRole.ADMIN, "HA admin", company_id=1)
    auth.create_user(s, "ha_kor", "Parol123!", UserRole.MANAGER, "HA ko'ruvchi", company_id=1)
    auth.create_user(s, "ha_b", "Parol123!", UserRole.ADMIN, "B admin", company_id=2)
s.commit()
KOD1 = (s.query(Company).filter(Company.id == 1).first().code or "")
KOD2 = (s.query(Company).filter(Company.id == 2).first().code or "")
s.close()
A, K, B = mijoz(), mijoz(), mijoz()
_la = [c.post("/login", data={"username": u, "password": "Parol123!"}, follow_redirects=False).status_code
       for c, u in ((A, "ha_admin"), (K, "ha_kor"), (B, "ha_b"))]
# K — «Ko'ruvchi» roli: Ustalar KPI va Hodimlar — faqat Ko'rish (Tahrirlash yo'q)
_rr = A.post("/api/rollar", json={"nom": "Hodim ko'ruvchi", "ruxsatlar": {"kpi": ["korish"], "hodim": ["korish"],
                                                                          "dashboard": ["korish"]}})
_rol_id = js(_rr).get("id")


def _k_rol(s):
    from models import User as _U
    u = s.query(_U).filter(_U.username == "ha_kor").first()
    u.rol_id = _rol_id
    return u.id


try:
    db_ishi(_k_rol)
except Exception as _e:                   # noqa: BLE001
    print("  (K roli qo'yilmadi:", _e, ")")
K = mijoz()
K.post("/login", data={"username": "ha_kor", "password": "Parol123!"}, follow_redirects=False)


def hodim(nom, tel=None, pin=None, klient=None, kod=None, oz_pin=True):
    """Hodim yaratiladi; `tel` berilsa — login, kirish, admin telefonga ruxsat beradi, `oz_pin` — hodim o'z PIN ini qo'yadi."""
    k = klient or A
    r = k.post("/api/employees", json={"name": nom, "position": "Kesuvchi", "pay_type": "fixed", "fixed_amount": 6_000_000})
    eid = js(r).get("id")
    db_ishi(lambda s: s.query(Employee).filter(Employee.id == eid).update({"hire_date": datetime(2024, 1, 1)}))
    if not tel:
        return eid, None
    k.post(f"/api/employees/{eid}/set-login", data={"phone": tel, "pin": pin})
    h = mijoz()
    h.post("/hodim/login", data={"phone": tel, "pin": pin, "korxona": kod or KOD1}, follow_redirects=False)
    _q = js(k.get("/api/admin/qurilma-sorovlari"))
    _kal = next((x.get("kalit") for x in (_q if isinstance(_q, list) else []) if x.get("employee_id") == eid), None)
    if _kal:
        k.post(f"/api/employees/{eid}/qurilma/ruxsat", json={"kalit": _kal})
        if oz_pin:
            h.post("/api/hodim/pin", json={"yangi": "5937", "takror": "5937"})
    return eid, h


EU, HU = hodim("Ulug'bek", "+998901120001", "4321")
EQ, HQ = hodim("Qodir", "+998901120002", "4322")
EN, _ = hodim("Nodir (panelsiz)")
EP, HP = hodim("Po'lat (vaqtinchalik PIN)", "+998901120004", "4324", oz_pin=False)
EX, HX = hodim("Xorijiy", "+998901120005", "4325", klient=B, kod=KOD2)
check("0 adminlar kirdi; hodimlar paneli ochiq (U, Q — 200; P — vaqtinchalik PIN 403; X — 2-korxona 200)",
      _la == [302, 302, 302] and HU.get("/api/hodim/oylik").status_code == 200 and HQ.get("/api/hodim/oylik").status_code == 200
      and HP.get("/api/hodim/oylik").status_code == 403 and HX.get("/api/hodim/oylik").status_code == 200,
      (_la, HU.get("/api/hodim/oylik").status_code, HP.get("/api/hodim/oylik").status_code))

_tg = []
_asl_tg = main._send_telegram
main._send_telegram = lambda text, company_id=None: _tg.append((text, company_id))

# ══════════════════════════════════════════════════════════════
section("A. Manba va savol — kim yozgani, hodimdan javob so'raladimi")
# ══════════════════════════════════════════════════════════════
_t1 = (BUGUN - timedelta(days=min(BUGUN.day - 1, 3))).isoformat()
_r1 = A.post(f"/api/employees/{EU}/advance?amount=205000&notes=Uzumga%20toladim&adv_date={_t1}")
AV1 = js(_r1).get("id")
_a1 = avans_ol(AV1) or {}
check("A1 admin KPI avansi (hodim panelga kira oladi) — manba «admin», javob «kutilmoqda», yozgan — admin",
      _r1.status_code == 200 and _a1.get("avans_manba") == "admin" and _a1.get("hodim_javobi") == "kutilmoqda"
      and _a1.get("given_by") == "HA admin", (_r1.status_code, _a1))
_rn = A.post(f"/api/employees/{EN}/advance?amount=50000&notes=naqd&adv_date={BUGUN.isoformat()}")
_an = avans_ol(js(_rn).get("id")) or {}
check("A2 panelga kira OLMAYDIGAN hodim (telefon / PIN yo'q) — manba «admin», javob SO'RALMAYDI (null)",
      _rn.status_code == 200 and _an.get("avans_manba") == "admin" and _an.get("hodim_javobi") is None, _an)
_rc = A.post(f"/api/obligations/employee/{EU}/close?year={BUGUN.year}&month={BUGUN.month}&amount=300000")
AV3 = next((a for a in avanslar(EU) if a not in (AV1,)), None)
_a3 = avans_ol(AV3) or {}
check("A3 Qarzdorlar «oylikni yopish» to'lovi — admin yozgan: manba «admin», javob «kutilmoqda»",
      _rc.status_code == 200 and _a3.get("avans_manba") == "admin" and _a3.get("hodim_javobi") == "kutilmoqda"
      and _a3.get("notes") == "Oy oxiri — qolgan oylik to'landi", (_rc.status_code, _a3))
_rs = HU.post("/api/hodim/advance-request", data={"amount": "120000", "requested_date": BUGUN.isoformat(), "notes": "ustadan"})
RQ1 = js(_rs).get("id")
_rt = A.post(f"/api/admin/advance-requests/{RQ1}/confirm")
AV4 = js(_rt).get("advance_id")
_a4 = avans_ol(AV4) or {}
_s4 = sorov_ol(RQ1) or {}
check("A4 hodim so'rovi tasdiqlandi — avans manbasi «hodim», javob so'ralmaydi, so'rovga avans bog'landi (`avans_id`)",
      _rt.status_code == 200 and _a4.get("avans_manba") == "hodim" and _a4.get("hodim_javobi") is None
      and _a4.get("notes") == "ustadan" + QOSHIMCHA and _s4.get("avans_id") == AV4, (_rt.status_code, _a4, _s4))
_ka = js(A.get(f"/api/employees/{EU}/advances?year={BUGUN.year}&month={BUGUN.month}"))
_kav = {a.get("id"): a for a in (_ka.get("advances") or [])}
check("A5 admin KPI ro'yxatida har avansda manba va hodim javobi (`manba`, `javob`, `given_by`)",
      _kav.get(AV1, {}).get("manba") == "admin" and _kav.get(AV1, {}).get("javob") == "kutilmoqda"
      and _kav.get(AV4, {}).get("manba") == "hodim" and _kav.get(AV4, {}).get("javob") is None
      and _kav.get(AV1, {}).get("given_by") == "HA admin" and "nizo_korildi_vaqti" in _kav.get(AV1, {}), list(_kav.values())[:3])
_ho = js(HU.get("/api/hodim/oylik"))
_jor = next((o for o in (_ho.get("oylar") or []) if o.get("joriy")), {})
_tl = {t.get("id"): t for t in (_jor.get("tolovlar") or [])}
check("A6 hodim «Oyligim» to'lovlarida: id, manba, kim (faqat admin yozganida), izoh (tizim qo'shimchasisiz), javob",
      _tl.get(AV1, {}).get("manba") == "admin" and _tl.get(AV1, {}).get("kim") == "HA admin"
      and _tl.get(AV1, {}).get("izoh") == "Uzumga toladim" and _tl.get(AV1, {}).get("javob") == "kutilmoqda"
      and _tl.get(AV4, {}).get("manba") == "hodim" and _tl.get(AV4, {}).get("kim") is None
      and _tl.get(AV4, {}).get("izoh") == "ustadan" and _tl.get(AV4, {}).get("summa") == 120000, _tl)
_jk = _ho.get("javob_kutilmoqda")
check("A7 «🔔» ro'yxati (`javob_kutilmoqda`): faqat shu hodimning javobi kutilayotgan admin avanslari (A1, A3), eng eskisi birinchi",
      isinstance(_jk, list) and [x.get("id") for x in _jk] == sorted([AV1, AV3], key=lambda i: (avans_ol(i)["date"], i))
      and all(x.get("manba") == "admin" and x.get("javob") == "kutilmoqda" for x in _jk)
      and _jk[0].get("notes") in ("Uzumga toladim", "Oy oxiri — qolgan oylik to'landi") if isinstance(_jk, list) and _jk else False,
      _jk)
check("A8 boshqa hodim (Q) ro'yxati bo'sh — U ning avanslari ko'rinmaydi",
      js(HQ.get("/api/hodim/oylik")).get("javob_kutilmoqda") == [], js(HQ.get("/api/hodim/oylik")).get("javob_kutilmoqda"))

# ══════════════════════════════════════════════════════════════
section("B. Hodim javobi — «Ha, oldim» / «Olmaganman»")
# ══════════════════════════════════════════════════════════════
def hisobot_avans(eid):
    s2 = SessionLocal()
    try:
        rep = services.get_monthly_report(s2, BUGUN.year, BUGUN.month, company_id=1)
        e = next((r for r in rep.get("hodimlar_moslashuvchan_breakdown", []) if r.get("employee_id") == eid), {})
        return e.get("avans")
    finally:
        s2.close()


_hav0 = hisobot_avans(EU)
_b1 = HU.post(f"/api/hodim/avans/{AV1}/javob", json={"javob": "oldim"})
_a = avans_ol(AV1) or {}
check("B1 «oldim» — 200, javob saqlandi (vaqti bilan), jurnalda «avans_oldim»",
      _b1.status_code == 200 and js(_b1).get("javob") == "oldim" and _a.get("hodim_javobi") == "oldim"
      and isinstance(_a.get("hodim_javob_vaqti"), datetime) and faoliyat(EU, "avans_oldim") == 1,
      (_b1.status_code, js(_b1), _a))
_b2a = HU.post(f"/api/hodim/avans/{AV1}/javob", json={"javob": "oldim"})
_b2b = HU.post(f"/api/hodim/avans/{AV1}/javob", json={"javob": "olmadim"})
check("B2 «oldim» dan keyin takror «oldim» yoki «olmadim» — 409 (o'zgartirib bo'lmaydi), javob o'zgarmaydi",
      _b2a.status_code == 409 and _b2b.status_code == 409 and "o'zgartirib bo'lmaydi" in js(_b2b).get("detail", "")
      and (avans_ol(AV1) or {}).get("hodim_javobi") == "oldim", (_b2a.status_code, _b2b.status_code, js(_b2b)))
_tg.clear()
_b3 = HU.post(f"/api/hodim/avans/{AV3}/javob", json={"javob": "olmadim"})
_a = avans_ol(AV3) or {}
check("B3 «olmadim» — 200; adminga Telegram xabari (ism, summa, yozgan — 1-korxona chatiga); jurnalda «avans_olmadim»",
      _b3.status_code == 200 and _a.get("hodim_javobi") == "olmadim" and "ogohlantirish" not in js(_b3)
      and len(_tg) == 1 and "Ulug'bek" in _tg[0][0] and "300 000" in _tg[0][0] and "HA admin" in _tg[0][0]
      and _tg[0][1] == 1 and faoliyat(EU, "avans_olmadim") == 1, (_b3.status_code, js(_b3), _tg))
_tg.clear()
_b4 = HU.post(f"/api/hodim/avans/{AV3}/javob", json={"javob": "olmadim"})
check("B4 takror «olmadim» — 409, Telegram takror ketmaydi",
      _b4.status_code == 409 and not _tg, (_b4.status_code, js(_b4), _tg))
_b5 = HU.post(f"/api/hodim/avans/{AV4}/javob", json={"javob": "oldim"})
check("B5 hodim o'zi so'ragan avansga javob — 409 «so'ralmagan»",
      _b5.status_code == 409 and "so'ralmagan" in js(_b5).get("detail", ""), (_b5.status_code, js(_b5)))
_b6a = HQ.post(f"/api/hodim/avans/{AV3}/javob", json={"javob": "oldim"})
_b6b = HU.post("/api/hodim/avans/987654/javob", json={"javob": "oldim"})
_b6c = HX.post(f"/api/hodim/avans/{AV1}/javob", json={"javob": "oldim"})
check("B6 boshqa hodimning avansi (Q → U), yo'q avans, boshqa korxona hodimi — 404; U ning javobi o'zgarmaydi",
      (_b6a.status_code, _b6b.status_code, _b6c.status_code) == (404, 404, 404)
      and (avans_ol(AV3) or {}).get("hodim_javobi") == "olmadim", (_b6a.status_code, _b6b.status_code, _b6c.status_code))
_hav1 = hisobot_avans(EU)            # B1…B6 — faqat javoblar (yangi avans yo'q)
_av_x = A.post(f"/api/employees/{EU}/advance?amount=10000&adv_date={BUGUN.isoformat()}")
AV5 = js(_av_x).get("id")
_bad = [HU.post(f"/api/hodim/avans/{AV5}/javob", json=t).status_code for t in ({}, {"javob": "ha"}, {"javob": 1},
                                                                               {"javob": "oldim", "x": 1})]
_bad.append(HU.post(f"/api/hodim/avans/{AV5}/javob", content=b"oldim", headers={"Content-Type": "text/plain"}).status_code)
_bad.append(HU.post(f"/api/hodim/avans/{AV5}/javob", json=["oldim"]).status_code)
check("B7 noto'g'ri tana ({} / «ha» / son / ortiqcha kalit / matn / ro'yxat) — 400 yoki 422, javob o'zgarmaydi («kutilmoqda»)",
      all(c in (400, 422) for c in _bad) and (avans_ol(AV5) or {}).get("hodim_javobi") == "kutilmoqda", _bad)
_b8a = mijoz().post(f"/api/hodim/avans/{AV5}/javob", json={"javob": "oldim"})
_b8b = HP.post(f"/api/hodim/avans/{AV5}/javob", json={"javob": "oldim"})
_b8c = A.post(f"/api/hodim/avans/{AV5}/javob", json={"javob": "oldim"})
check("B8 sessiyasiz — 401; vaqtinchalik PIN bilan — 403; admin sessiyasi (hodim emas) — 401; javob o'zgarmaydi",
      (_b8a.status_code, _b8b.status_code, _b8c.status_code) == (401, 403, 401)
      and (avans_ol(AV5) or {}).get("hodim_javobi") == "kutilmoqda", (_b8a.status_code, _b8b.status_code, _b8c.status_code))
_hav2 = hisobot_avans(EU)
_b9 = HU.post(f"/api/hodim/avans/{AV3}/javob", json={"javob": "oldim"})
check("B9 «olmadim» → «oldim» (keyin olgan / adashgan) — 200",
      _b9.status_code == 200 and (avans_ol(AV3) or {}).get("hodim_javobi") == "oldim", (_b9.status_code, js(_b9)))
check("B10 avans hisobda javobdan QAT'I NAZAR turadi — oylik hisobotidagi «avans» javoblardan oldin va keyin bir xil "
      "(«oldim», «olmadim», «olmadim» → «oldim»)",
      _hav0 is not None and _hav0 == _hav1 and _hav2 == hisobot_avans(EU) and _hav2 == _hav0 + 10000,
      (_hav0, _hav1, _hav2, hisobot_avans(EU)))

# ══════════════════════════════════════════════════════════════
section("C. Admin — «Olmaganman» ogohlantirishi, «Ko'rib chiqdim», o'chirish")
# ══════════════════════════════════════════════════════════════
_c0 = HU.post(f"/api/hodim/avans/{AV5}/javob", json={"javob": "olmadim"})
_rl = A.get("/api/admin/avans-nizolar")
_nl = js(_rl)
check("C1 nizolar ro'yxati: faqat ko'rib chiqilmagan «Olmaganman» (AV5), hodim nomi, summa, yozgan, javob vaqti",
      _c0.status_code == 200 and _rl.status_code == 200 and isinstance(_nl, list) and [x.get("id") for x in _nl] == [AV5]
      and _nl[0].get("employee_name") == "Ulug'bek" and _nl[0].get("amount") == 10000 and _nl[0].get("given_by") == "HA admin"
      and _nl[0].get("javob_vaqti"), (_rl.status_code, _nl))
_eq = next((x for x in royxat(A.get("/api/employees")) if isinstance(x, dict) and x.get("id") == EU), {})
check("C2 `/api/employees` qatorida avans holati: «Olmaganman» soni / summasi, javob kutilayotganlar soni",
      _eq.get("avans_holat") == {"nizo_soni": 1, "nizo_summa": 10000.0, "kutilmoqda_soni": 0}, _eq.get("avans_holat"))
_rk = K.get("/api/admin/avans-nizolar")
_rk2 = K.post(f"/api/employees/advance/{AV5}/nizo-korildi")
_rb = B.get("/api/admin/avans-nizolar")
_rb2 = B.post(f"/api/employees/advance/{AV5}/nizo-korildi")
check("C3 «Hodimlar: Tahrirlash» siz — 403 (ro'yxat ham, amal ham); 2-korxona admini — ro'yxat bo'sh, amal 404",
      (_rk.status_code, _rk2.status_code) == (403, 403) and _rb.status_code == 200 and js(_rb) == [] and _rb2.status_code == 404
      and (avans_ol(AV5) or {}).get("nizo_korildi_vaqti") is None, (_rk.status_code, _rk2.status_code, _rb.status_code, js(_rb)))
_c4 = A.post(f"/api/employees/advance/{AV5}/nizo-korildi")
_a = avans_ol(AV5) or {}
_eq4 = next((x for x in royxat(A.get("/api/employees")) if isinstance(x, dict) and x.get("id") == EU), {})
check("C4 «Ko'rib chiqdim» — 200; ogohlantirish yopildi (ro'yxat bo'sh, KPI qatorida nizo 0), kim / qachon yozildi; hodim javobi "
      "O'ZGARMAYDI; jurnal",
      _c4.status_code == 200 and js(A.get("/api/admin/avans-nizolar")) == [] and _a.get("nizo_korgan") == "HA admin"
      and (_eq4.get("avans_holat") or {}).get("nizo_soni") == 0
      and isinstance(_a.get("nizo_korildi_vaqti"), datetime) and _a.get("hodim_javobi") == "olmadim"
      and faoliyat(EU, "avans_nizo_korildi") == 1, (_c4.status_code, js(_c4), _a))
_c5a = A.post(f"/api/employees/advance/{AV5}/nizo-korildi")
_c5b = A.post(f"/api/employees/advance/{AV1}/nizo-korildi")
_c5c = A.post("/api/employees/advance/987654/nizo-korildi")
check("C5 takror «Ko'rib chiqdim» — 409 (kim ko'rib chiqqani bilan); «Olmaganman» emas — 409; yo'q avans — 404",
      _c5a.status_code == 409 and "HA admin" in js(_c5a).get("detail", "") and _c5b.status_code == 409
      and _c5c.status_code == 404, (_c5a.status_code, js(_c5a), _c5b.status_code, _c5c.status_code))
_c6 = HU.post(f"/api/hodim/avans/{AV5}/javob", json={"javob": "olmadim"})
check("C6 ko'rib chiqilgandan keyin takror «olmadim» — 409 (ogohlantirish qayta ochilmaydi)",
      _c6.status_code == 409 and js(A.get("/api/admin/avans-nizolar")) == [], (_c6.status_code, js(_c6)))
# yangi nizo → o'chirish
_av6 = A.post(f"/api/employees/{EQ}/advance?amount=77000&notes=karta&adv_date={BUGUN.isoformat()}")
AV6 = js(_av6).get("id")
HQ.post(f"/api/hodim/avans/{AV6}/javob", json={"javob": "olmadim"})
_n0 = [x.get("id") for x in royxat(A.get("/api/admin/avans-nizolar"))]
_c7 = A.delete(f"/api/employees/advance/{AV6}")
_c7b = A.delete(f"/api/employees/advance/{AV6}")
check("C7 nizodagi avansni o'chirish — 200, ro'yxatdan ketadi, jurnalda «avans_ochirildi» (izohi bilan); takror — 404",
      _n0 == [AV6] and _c7.status_code == 200 and js(A.get("/api/admin/avans-nizolar")) == [] and avans_ol(AV6) is None
      and faoliyat(EQ, "avans_ochirildi") == 1 and _c7b.status_code == 404, (_n0, _c7.status_code, _c7b.status_code))
_av7 = A.post(f"/api/employees/{EQ}/advance?amount=33000&adv_date={BUGUN.isoformat()}")
AV7 = js(_av7).get("id")
HQ.post(f"/api/hodim/avans/{AV7}/javob", json={"javob": "olmadim"})
_n1 = [x.get("id") for x in royxat(A.get("/api/admin/avans-nizolar"))]
_n1e = [x.get("id") for x in royxat(A.get(f"/api/admin/avans-nizolar?employee_id={EU}"))]
A.delete(f"/api/employees/{EQ}")
_n2 = [x.get("id") for x in royxat(A.get("/api/admin/avans-nizolar"))]
A.post(f"/api/employees/{EQ}/restore")
_n3 = [x.get("id") for x in royxat(A.get("/api/admin/avans-nizolar"))]
check("C8 `employee_id` filtri (boshqa hodimniki chiqmaydi); o'chirilgan hodimning nizosi chiqmaydi, tiklansa — qaytadi",
      _n1 == [AV7] and _n1e == [] and _n2 == [] and _n3 == [AV7], (_n1, _n1e, _n2, _n3))

# ══════════════════════════════════════════════════════════════
section("D. «Mening so'rovlarim» — 12 oy, kutilayotganlar, avansi o'chirilgan")
# ══════════════════════════════════════════════════════════════
EM, HM = hodim("Mirzo (so'rovlar)", "+998901120006", "4326")


def sorov_qosh(eid, summa, sana_dt, holat=AdvanceRequestStatus.CONFIRMED, notes=None, sub=None):
    def f(s):
        r = AdvanceRequest(employee_id=eid, amount=summa, requested_date=sana_dt, notes=notes, status=holat,
                           submitted_at=sub or (sana_dt + timedelta(hours=1)))
        s.add(r)
        s.flush()
        return r.id
    return db_ishi(f)


_kunlar = list(range(1, 26))
for _i in _kunlar:
    sorov_qosh(EM, 1000 * _i, datetime(BUGUN.year, BUGUN.month, 1, 0, 0), sub=datetime(BUGUN.year, BUGUN.month, 1, 1, 0) + timedelta(minutes=_i))
_r11 = sorov_qosh(EM, 111_000, sana(11, 5))
# Toshkent oyi chegarasi: joriy oyning 1-kuni Toshkent 02:00 = UTC bo'yicha O'TGAN oyning oxirgi kuni 21:00
_rch = sorov_qosh(EM, 7_000, datetime(BUGUN.year, BUGUN.month, 1) - timedelta(hours=3))
_r12 = sorov_qosh(EM, 112_000, sana(12, 20))
_rp14 = sorov_qosh(EM, 114_000, sana(14, 3), holat=AdvanceRequestStatus.PENDING)
_rx = sorov_qosh(EQ, 99_000, sana(1, 3))
_dl = js(HM.get("/api/hodim/my-requests"))
_ids = [r.get("id") for r in (_dl if isinstance(_dl, list) else [])]
check("D1 20 tadan ko'p so'rov — HAMMASI (joriy oyda 26 ta; ilgari faqat oxirgi 20 ta chiqardi)",
      isinstance(_dl, list) and sum(1 for r in _dl if r.get("oy") == oy_kalit(0)) == 26, len(_ids))
check("D2 12 oy oynasi: 11 oy oldingi so'rov — BOR; 12 oy oldingi — YO'Q; 14 oy oldingi KUTILAYOTGAN — BOR (doim)",
      _r11 in _ids and _r12 not in _ids and _rp14 in _ids, (_r11 in _ids, _r12 in _ids, _rp14 in _ids))
_d11 = next((r for r in _dl if r.get("id") == _r11), {}) if isinstance(_dl, list) else {}
_dp = next((r for r in _dl if r.get("id") == _rp14), {}) if isinstance(_dl, list) else {}
_dch = next((r for r in _dl if r.get("id") == _rch), {}) if isinstance(_dl, list) else {}
check("D3 `oy` — so'rov sanasining TOSHKENT oyi ('YYYY-MM'; oy chegarasida — UTC emas); kutilayotganniki ham",
      _d11.get("oy") == oy_kalit(11) and _dp.get("oy") == oy_kalit(14) and _dp.get("status") == "pending"
      and _dch.get("oy") == oy_kalit(0), (_d11, _dp, _dch))
check("D4 boshqa hodimning so'rovi ko'rinmaydi; tartib — eng yangi yuborilgan birinchi",
      _rx not in _ids and isinstance(_dl, list) and len(_dl) > 2
      and [r.get("submitted_at") for r in _dl] == sorted([r.get("submitted_at") for r in _dl], reverse=True), _ids[:5])
# avansi o'chirilgan tasdiqlangan so'rov
_rs2 = HM.post("/api/hodim/advance-request", data={"amount": "45000", "requested_date": BUGUN.isoformat(), "notes": "o'chadi"})
RQ2 = js(_rs2).get("id")
AV8 = js(A.post(f"/api/admin/advance-requests/{RQ2}/confirm")).get("advance_id")
_o1 = next((t for o in (js(HM.get("/api/hodim/oylik")).get("oylar") or []) for t in (o.get("tolovlar") or [])
            if t.get("id") == AV8), None)
_d5 = A.delete(f"/api/employees/advance/{AV8}")
_q5 = next((r for r in (js(HM.get("/api/hodim/my-requests")) or []) if isinstance(r, dict) and r.get("id") == RQ2), {})
_o2 = next((t for o in (js(HM.get("/api/hodim/oylik")).get("oylar") or []) for t in (o.get("tolovlar") or [])
            if t.get("id") == AV8), None)
check("D5 tasdiqlangan so'rov avansi admin tomonidan o'chirildi — so'rovda `avans_ochirildi`, kim va qachon; «Oyligim» da yo'q",
      _o1 is not None and _d5.status_code == 200 and _q5.get("status") == "confirmed" and _q5.get("avans_ochirildi") is True
      and _q5.get("avans_ochirgan") == "HA admin" and bool(_q5.get("avans_ochirildi_vaqti")) and _o2 is None,
      (_o1, _d5.status_code, _q5, _o2))
_q6 = next((r for r in (js(HM.get("/api/hodim/my-requests")) or []) if isinstance(r, dict) and r.get("id") == _r11), {})
check("D6 avansi joyida tasdiqlangan so'rov — `avans_ochirildi` False (yolg'on belgi yo'q)",
      _q6.get("avans_ochirildi") is False and _q6.get("avans_ochirildi_vaqti") is None, _q6)
_dx = HX.get("/api/hodim/my-requests")
check("D7 2-korxona hodimi — o'z (bo'sh) ro'yxati; 1-korxona so'rovlari ko'rinmaydi",
      _dx.status_code == 200 and js(_dx) == [], (_dx.status_code, js(_dx)))

# ══════════════════════════════════════════════════════════════
section("E. Migratsiya — zip 160 dan oldingi yozuvlar")
# ══════════════════════════════════════════════════════════════
_mig = getattr(main, "_migrate_avans_manba", None)
EO, HO = hodim("Oybek (migratsiya)", "+998901120007", "4327")
ENO, _ = hodim("Nurbek (migratsiya, panelsiz)")


def eski_avans(eid, summa, dt, notes=None, given_by="Eski admin"):
    def f(s):
        a = EmployeeAdvance(employee_id=eid, amount=summa, date=dt, notes=notes, given_by=given_by)
        s.add(a)
        s.flush()
        return a.id
    return db_ishi(f)


_joriy_dt = datetime(BUGUN.year, BUGUN.month, 1, 4, 0)            # Toshkent 1-kun 09:00
_o_a = eski_avans(EO, 205_000, _joriy_dt, "Uzumga toladim")
_o_b = eski_avans(EO, 90_000, sana(1, 15), "naqd")
_o_c = eski_avans(EO, 70_000, _joriy_dt, "kecha oldim" + QOSHIMCHA, given_by="Tasdiqchi")
_o_d = eski_avans(ENO, 40_000, _joriy_dt, "naqd")
_o_e = eski_avans(EO, 60_000, _joriy_dt, None)
# eski tasdiqlangan so'rovlar: (1) avansi bor, (2) avansi o'chirilgan, (3)+(4) bir xil ikki so'rov va ikki avans,
# (5)+(6) bir xil ikki so'rov va BITTA avans
_rd1 = sana(0, 1)
_s_1 = sorov_qosh(EO, 70_000, _joriy_dt, notes="kecha oldim")
db_ishi(lambda s: s.query(AdvanceRequest).filter(AdvanceRequest.id == _s_1).update({"confirmed_by": "Tasdiqchi"}))
_s_2 = sorov_qosh(EO, 55_000, sana(2, 9), notes="o'chirilgan")
db_ishi(lambda s: s.query(AdvanceRequest).filter(AdvanceRequest.id == _s_2).update({"confirmed_by": "Tasdiqchi"}))
_tw = sana(3, 4)
_s_3 = sorov_qosh(EO, 30_000, _tw, notes="egizak")
_s_4 = sorov_qosh(EO, 30_000, _tw, notes="egizak")
_s_5 = sorov_qosh(EO, 20_000, sana(4, 4), notes="yolg'iz")
_s_6 = sorov_qosh(EO, 20_000, sana(4, 4), notes="yolg'iz")
db_ishi(lambda s: s.query(AdvanceRequest).filter(AdvanceRequest.id.in_([_s_3, _s_4, _s_5, _s_6])).update(
    {"confirmed_by": "Tasdiqchi"}, synchronize_session=False))
_e_3 = eski_avans(EO, 30_000, _tw, "egizak" + QOSHIMCHA, given_by="Tasdiqchi")
_e_4 = eski_avans(EO, 30_000, _tw, "egizak" + QOSHIMCHA, given_by="Tasdiqchi")
_e_5 = eski_avans(EO, 20_000, sana(4, 4), "yolg'iz" + QOSHIMCHA, given_by="Tasdiqchi")
# (7)+(8): bir xil hodim / summa / sana / tasdiqlovchi, izohi boshqa — avans faqat (8) niki (izoh AYNAN solishtiriladi)
_s_7 = sorov_qosh(EO, 12_000, sana(5, 4), notes="birinchi")
_s_8 = sorov_qosh(EO, 12_000, sana(5, 4), notes="ikkinchi")
db_ishi(lambda s: s.query(AdvanceRequest).filter(AdvanceRequest.id.in_([_s_7, _s_8])).update(
    {"confirmed_by": "Tasdiqchi"}, synchronize_session=False))
_e_8 = eski_avans(EO, 12_000, sana(5, 4), "ikkinchi" + QOSHIMCHA, given_by="Tasdiqchi")
_m1 = _mig() if callable(_mig) else None
_ma = {i: avans_ol(i) or {} for i in (_o_a, _o_b, _o_c, _o_d, _o_e)}
check("E1 eski admin avansi JORIY oyda, hodim panelga kira oladi — manba «admin», javob «kutilmoqda»",
      _ma[_o_a].get("avans_manba") == "admin" and _ma[_o_a].get("hodim_javobi") == "kutilmoqda"
      and _ma[_o_e].get("hodim_javobi") == "kutilmoqda", (_m1, _ma[_o_a], _ma[_o_e]))
check("E2 eski admin avansi o'tgan oyda — manba «admin», javob SO'RALMAYDI (egasi tanlovi «Faqat joriy oy»); panelsiz hodim — so'ralmaydi",
      _ma[_o_b].get("avans_manba") == "admin" and _ma[_o_b].get("hodim_javobi") is None
      and _ma[_o_d].get("avans_manba") == "admin" and _ma[_o_d].get("hodim_javobi") is None, (_ma[_o_b], _ma[_o_d]))
check("E3 eski hodim so'rovi avansi (izohda « (xodim o'zi yozgan, admin tasdiqladi)») — manba «hodim», javob so'ralmaydi",
      _ma[_o_c].get("avans_manba") == "hodim" and _ma[_o_c].get("hodim_javobi") is None, _ma[_o_c])
_sm = {i: sorov_ol(i) or {} for i in (_s_1, _s_2, _s_3, _s_4, _s_5, _s_6)}
check("E4 eski tasdiqlangan so'rov avansga bog'landi (5 maydon AYNAN); avansi yo'q so'rov — o'chirilgan (kim / qachon noma'lum)",
      _sm[_s_1].get("avans_id") == _o_c and _sm[_s_1].get("avans_ochirildi_vaqti") is None
      and _sm[_s_2].get("avans_id") is None and isinstance(_sm[_s_2].get("avans_ochirildi_vaqti"), datetime)
      and _sm[_s_2].get("avans_ochirgan") is None, (_sm[_s_1], _sm[_s_2]))
check("E5 bir xil ikki so'rov + ikki avans — har biri o'z avansiga; bir xil ikki so'rov + bitta avans — biri bog'landi, biri o'chirilgan",
      {_sm[_s_3].get("avans_id"), _sm[_s_4].get("avans_id")} == {_e_3, _e_4}
      and sorted([_sm[_s_5].get("avans_id") is not None, _sm[_s_6].get("avans_id") is not None]) == [False, True]
      and (_sm[_s_5].get("avans_id") or _sm[_s_6].get("avans_id")) == _e_5
      and sum(1 for x in (_s_5, _s_6) if isinstance(_sm[x].get("avans_ochirildi_vaqti"), datetime)) == 1, _sm)
_s7m, _s8m = sorov_ol(_s_7) or {}, sorov_ol(_s_8) or {}
check("E5b izohi boshqa (qolgan maydonlari bir xil) so'rovlar — avans izohi AYNAN mos so'rovga; boshqasi — o'chirilgan",
      _s8m.get("avans_id") == _e_8 and _s7m.get("avans_id") is None and isinstance(_s7m.get("avans_ochirildi_vaqti"), datetime),
      (_s7m, _s8m, _e_8))
_q2 = next((r for r in (js(HO.get("/api/hodim/my-requests")) or []) if isinstance(r, dict) and r.get("id") == _s_2), {})
check("E6 hodim panelida eski «o'chirilgan» so'rov — `avans_ochirildi` True, vaqti va kim — null (noma'lum, yolg'on sana yo'q)",
      _q2.get("avans_ochirildi") is True and _q2.get("avans_ochirildi_vaqti") is None and _q2.get("avans_ochirgan") is None, _q2)
HO.post(f"/api/hodim/avans/{_o_a}/javob", json={"javob": "oldim"})
_m2 = _mig() if callable(_mig) else None
check("E7 takror ishga tushish — hech narsa topilmaydi (hammasi 0), hodim javobi va bog'lamlar o'zgarmaydi",
      _m2 == {"avans": 0, "kutilmoqda": 0, "boglandi": 0, "ochirilgan": 0}
      and (avans_ol(_o_a) or {}).get("hodim_javobi") == "oldim" and (sorov_ol(_s_1) or {}).get("avans_id") == _o_c, _m2)
_hk = js(HO.get("/api/hodim/oylik")).get("javob_kutilmoqda") or []
check("E8 eski joriy oy admin avansi hodimning «🔔» ro'yxatida (javob berilmagani — `_o_e`)",
      [x.get("id") for x in _hk] == [_o_e], _hk)
# eski baza: yangi ustunlarsiz — sync_missing_columns qo'shadi (NULL), migratsiya to'ldiradi
_yangi = (("employee_advances", ("avans_manba", "hodim_javobi", "hodim_javob_vaqti", "nizo_korildi_vaqti", "nizo_korgan")),
          ("advance_requests", ("avans_id", "avans_ochirildi_vaqti", "avans_ochirgan")))
_e9 = []
try:
    with database.engine.connect() as _cn:
        _cn.execute(sql_text("DROP INDEX IF EXISTS ix_advance_requests_avans_id"))
        for _j, _us in _yangi:
            for _u in _us:
                _cn.execute(sql_text(f"ALTER TABLE {_j} DROP COLUMN {_u}"))
        _cn.commit()
    with contextlib.redirect_stdout(_quiet):
        database.sync_missing_columns()
    from sqlalchemy import inspect as _insp
    _ins = _insp(database.engine)
    _bor = {j: {c["name"] for c in _ins.get_columns(j)} for j, _ in _yangi}
    _e9.append(all(u in _bor[j] for j, us in _yangi for u in us))
    _m3 = _mig() if callable(_mig) else None
    _e9.append(_m3 is not None and _m3["avans"] > 0)
    _e9.append((avans_ol(_o_c) or {}).get("avans_manba") == "hodim" and (avans_ol(_o_b) or {}).get("hodim_javobi") is None)
except Exception as _ex:                  # noqa: BLE001
    _e9.append(f"{type(_ex).__name__}: {_ex}")
check("E9 eski baza (yangi ustunlarsiz): `sync_missing_columns` ustunlarni qo'shadi, migratsiya qayta to'ldiradi", _e9 == [True] * 3,
      _e9)

# ══════════════════════════════════════════════════════════════
section("F. PG poyga — so'rovni parallel tasdiqlash / rad etish")
# ══════════════════════════════════════════════════════════════
if PG_URL:
    def poyga(amallar):
        rid = sorov_qosh(EU, 100_000, datetime(BUGUN.year, BUGUN.month, 1), holat=AdvanceRequestStatus.PENDING,
                         notes=f"poyga {'+'.join(amallar)} {time.time()}")
        asl = crud._advance_request_of_company

        def sekin(db, r_id, cid=None, *a, **kw):
            x = asl(db, r_id, cid, *a, **kw)
            time.sleep(0.4)
            return x
        crud._advance_request_of_company = sekin
        bar = threading.Barrier(len(amallar))
        javob = []

        def ish(amal):
            ss = SessionLocal()
            bar.wait()
            try:
                if amal == "tasdiq":
                    javob.append(("tasdiq", bool(crud.confirm_advance_request(ss, rid, "A", company_id=1))))
                else:
                    javob.append(("rad", bool(crud.reject_advance_request(ss, rid, "B", company_id=1, rad_sababi="yo'q"))))
            except Exception as ex:       # noqa: BLE001
                javob.append((amal, f"XATO {type(ex).__name__}"))
                ss.rollback()
            finally:
                ss.close()
        t = [threading.Thread(target=ish, args=(a,)) for a in amallar]
        [x.start() for x in t]
        [x.join() for x in t]
        crud._advance_request_of_company = asl
        n = db_ishi(lambda s: s.query(EmployeeAdvance).filter(EmployeeAdvance.employee_id == EU,
                                                              EmployeeAdvance.notes.like("poyga%")).count())
        db_ishi(lambda s: s.query(EmployeeAdvance).filter(EmployeeAdvance.notes.like("poyga%")).delete(
            synchronize_session=False))
        return javob, n, (sorov_ol(rid) or {}).get("status")
    _j1, _n1p, _h1 = poyga(("tasdiq", "tasdiq"))
    check("F1 parallel ikki tasdiq — faqat BITTASI muvaffaqiyat, avans BITTA (ilgari ikkalasi — ikki avans)",
          sorted(x[1] for x in _j1) == [False, True] and _n1p == 1 and _h1 == AdvanceRequestStatus.CONFIRMED, (_j1, _n1p, _h1))
    _j2, _n2p, _h2 = poyga(("tasdiq", "rad"))
    _ok2 = [x for x in _j2 if x[1] is True]
    check("F2 parallel tasdiq + rad — faqat bittasi bajariladi; natija izchil (tasdiq — 1 avans, rad — 0)",
          len(_ok2) == 1 and ((_ok2[0][0] == "tasdiq" and _n2p == 1 and _h2 == AdvanceRequestStatus.CONFIRMED)
                              or (_ok2[0][0] == "rad" and _n2p == 0 and _h2 == AdvanceRequestStatus.REJECTED)),
          (_j2, _n2p, _h2))
else:
    print("  (SQLite — o'tkazildi: haqiqiy parallellik yo'q)")

# ══════════════════════════════════════════════════════════════
section("G. Shablonlar (statik)")
# ══════════════════════════════════════════════════════════════
HP_ = oqi("templates/hodim_panel.html")
OY_ = oqi("templates/_hodim_oynalari.html")
HOME = oqi("templates/home.html")
DASH = oqi("templates/dashboard.html")
KPI = oqi("templates/kpi.html")
check("G1 hodim paneli: «🔔 Admin yozgan to'lovlar» kartasi, javob — `/api/hodim/avans/{id}/javob`, «Ha, oldim» avval so'raladi "
      "(«Keyin o'zgartirib bo'lmaydi»), belgilar «📱 O'zingiz» / «🧑‍💼 Admin»",
      'id="javob-karta"' in HP_ and "'/api/hodim/avans/' + encodeURIComponent(blok.dataset.id) + '/javob'" in HP_
      and "Keyin o'zgartirib bo'lmaydi" in HP_ and "📱 O'zingiz" in HP_ and "🧑‍💼 Admin" in HP_
      and "✅ Endi oldim" in HP_, "")
check("G2 hodim paneli «Mening so'rovlarim»: kutilayotganlar birinchi, joriy oy ochiq, o'tgan oylar yopiq (`<details>`, «N ta so'rov · "
      "X so'm tasdiqlangan»), avansi o'chirilgan so'rov belgisi",
      "⏳ Admin tasdiqlashi kutilmoqda" in HP_ and "ta so'rov · ${fmt(tasdiq)} so'm tasdiqlangan" in HP_
      and 'class="oy-yopiq sorov-oy"' in HP_ and "keyin admin o'chirgan" in HP_ and "k >= joriy" in HP_, "")
_hn = [m.start() for m in re.finditer(r"\{% include \"_hodim_oynalari\.html\" %\}", HOME + "\n" + DASH)]
check("G3 umumiy hodim oynalari Bosh sahifa VA Dashboard da (bitta fayl), ikkalasi ham `checkQurilmaSorovlari()` ni chaqiradi",
      len(_hn) == 2 and "checkQurilmaSorovlari();" in HOME and "checkQurilmaSorovlari();" in DASH
      and "async function checkQurilmaSorovlari" in OY_ and "async function checkQurilmaSorovlari" not in DASH, len(_hn))
_i1, _i2 = OY_.find("function checkQurilmaSorovlari"), OY_.find("async function checkAvansNizolar")
check("G4 navbat: telefon oynasi → «Olmaganman» oynasi → avans so'rovlari (oyna yopilsa / ro'yxat bo'sh bo'lsa keyingisi)",
      _i1 >= 0 and _i2 >= 0 and "if (!Array.isArray(rows) || !rows.length) { checkAvansNizolar(); return; }" in OY_
      and "if (ochiq) checkAvansNizolar();" in OY_ and "if (ochiq) checkPendingAdvanceRequests();" in OY_
      and "if (!Array.isArray(rows) || !rows.length) { checkPendingAdvanceRequests(); return; }" in OY_
      and 'id="avansNizoModal"' in OY_ and "/api/admin/avans-nizolar" in OY_, (_i1, _i2))
check("G5 KPI: qatorda «Olmaganman» ogohlantirishi (bosilsa — avans oynasi), oynada nizo bo'limi va amallar, avans belgisi",
      "function avansHolatQatori(e)" in KPI and "${avansHolatQatori(e)}" in KPI and "function avansManbaHtml(a)" in KPI
      and 'id="adv-nizo"' in KPI and "/nizo-korildi" in KPI and KPI.count("${avansManbaHtml(a)}") == 2, "")

main._send_telegram = _asl_tg
print("\n" + "=" * 70)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
