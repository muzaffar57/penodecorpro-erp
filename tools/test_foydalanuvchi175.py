#!/usr/bin/env python3
"""
test_foydalanuvchi175.py — kech144 (zip 175, audit 2-to'lqin): «Foydalanuvchilar», «Sozlamalar», «O'chirilganlar» — SERVER tomoni.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k175/fy_probe1.py`, `fy_probe2.py`, asl kod = zip 174):
  U1  Foydalanuvchini yoqish / o'chirish holatni faqat ALMASHTIRARDI: boshqa admin (yoki boshqa oyna) allaqachon o'chirgan
      foydalanuvchini eski sahifadagi «O'chir» QAYTA YOQARDI; admin o'zini API orqali o'chira olardi; ikki admin bir-birini bir vaqtda
      o'chirsa korxona Adminsiz qolardi.
  X2  Foydalanuvchi yaratish, yoqish / o'chirish, parol tiklash / o'zgartirish «Audit jurnali» da 0 qator edi (admin birovning parolini
      tiklab, uning nomidan kirsa — iz yo'q).
  U4  Foydalanuvchi yaratish: javob yo'qolib (502) qayta bosilsa — «Bu username band» (yaratilgan bo'lsa ham). Endi amal kaliti.
  T2  Savatda bo'lmagan loyihani «tiklash» — 200 va har safar soxta «tiklandi» yozuvi. Endi 409, yozuv yo'q.
  T3 / T4  Buyurtma / loyihani butunlay o'chirish tiklash bilan bir qulfda emas edi (ikki oynada bir vaqtda — endigina tiklangan
      buyurtma o'chib ketardi, ombor kamayib qolardi). PG da qulf kutilishi o'lchanadi.
  C1  «Mahsulot turlari» ro'yxati yuklanmagan sahifada «Saqlash» `codes=''` yuborib Loy sotish va Blokni O'CHIRARDI. Endi bo'sh ro'yxat
      faqat `bosh=1` bilan.
  C8 / T1  «Sozlamalar» (faqat «Tizim jurnallari: Ko'rish» bilan ochiladi) va «O'chirilganlar» — ruxsatsiz tugmalar chizilardi
      (bosilsa 403); hodim tugmalari «Hodimlar» ruxsati bilan (server qoidasi).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (qulf va parallel bo'limlar — faqat PG); `TENANT_FILTER=1`.
Asl kodga (zip 174) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_foydalanuvchi175.py
"""
import os
import re
import io
import sys
import json
import time
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "foydalanuvchi175_test"
_T = tempfile.mkdtemp(prefix="fy175_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'fy175.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import UserRole, User, Rol, ActivityLog, Project, Order, Employee   # noqa: E402
from production_models import Company             # noqa: E402
from fastapi import HTTPException                  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
HAMMA = ["korish", "yaratish", "tahrirlash", "ochirish"]


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


def detail(r):
    d = js(r)
    return d.get("detail") if isinstance(d, dict) else None


def matn(r):
    d = detail(r)
    if isinstance(d, dict):
        return str(d.get("message") or d)
    return str(d or "")


_IP = {"n": 70}


def mijoz():
    _IP["n"] += 1
    try:
        return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False,
                          client=(f"203.0.113.{_IP['n']}", 50000))
    except TypeError:
        return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)


def kirish(login, parol=PAROL):
    c = mijoz()
    c.post("/login", data={"username": login, "password": parol}, follow_redirects=False)
    return c


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def uid(login):
    return db_ishi(lambda s: (s.query(User).filter(User.username == login).first() or User(id=None)).id)


def faolmi(login):
    return db_ishi(lambda s: bool(s.query(User).filter(User.username == login).first().is_active))


def jurnal(action, entity_type="user", entity_id=None):
    def f(s):
        q = s.query(ActivityLog).filter(ActivityLog.action == action, ActivityLog.entity_type == entity_type)
        if entity_id is not None:
            q = q.filter(ActivityLog.entity_id == entity_id)
        return q.count()
    return db_ishi(f)


def jurnal_qatorlari(entity_type, entity_id):
    def f(s):
        return [(x.action, x.old_value or "", x.new_value or "", x.performed_by or "", x.company_id)
                for x in s.query(ActivityLog).filter(ActivityLog.entity_type == entity_type, ActivityLog.entity_id == entity_id)
                .order_by(ActivityLog.id).all()]
    return db_ishi(f)


def rol_qoy(login, ruxsat):
    def f(s):
        u = s.query(User).filter(User.username == login).first()
        r = Rol(company_id=u.company_id, nom="FY175 " + login, kod=None, ruxsatlar=json.dumps(ruxsat), tavsif="")
        s.add(r)
        s.flush()
        u.rol_id = r.id
        return r.id
    return db_ishi(f)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ikkinchi Korxona 175", code="IKKINCHI-175"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "fy_admin", PAROL, UserRole.ADMIN, "FY Admin", company_id=1)
    auth.create_user(s, "fy_admin2", PAROL, UserRole.ADMIN, "FY Admin 2", company_id=1)
    for _u in ("fy_ishchi", "fy_jur", "fy_soz", "fy_soz2", "fy_sav", "fy_sav2", "fy_parol"):
        auth.create_user(s, _u, PAROL, UserRole.MANAGER, _u.upper(), company_id=1)
    auth.create_user(s, "fy_boshqa", PAROL, UserRole.MANAGER, "Boshqa korxona", company_id=2)
s.commit()
s.close()
rol_qoy("fy_jur", {"jurnal": ["korish"]})
rol_qoy("fy_soz", {"jurnal": ["korish"], "sozlama": ["tahrirlash"]})                       # Ko'rishsiz tahrirlash (S1)
rol_qoy("fy_soz2", {"jurnal": ["korish"], "sozlama": ["korish", "tahrirlash"]})            # yaratish / o'chirishsiz
rol_qoy("fy_sav", {"savat": ["korish"]})
rol_qoy("fy_sav2", {"savat": ["korish", "tahrirlash", "ochirish"]})

A = kirish("fy_admin")
check("T0 admin kirdi (/users 200)", A.get("/users").status_code == 200)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Yoqish / o'chirish — maqsad holat, o'zini va oxirgi Adminni o'chirmaslik, jurnal (U1, X2)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ISH = uid("fy_ishchi")
r = A.post(f"/api/users/{ISH}/toggle?faol=false")
check("A1 faol=false — 200, foydalanuvchi o'chdi", r.status_code == 200 and js(r).get("is_active") is False and not faolmi("fy_ishchi"),
      (r.status_code, r.text[:200]))
check("A2 jurnalda «faolsizlantirildi» — 1 qator (ilgari 0)", jurnal("faolsizlantirildi", entity_id=ISH) == 1,
      jurnal_qatorlari("user", ISH))
r = A.post(f"/api/users/{ISH}/toggle?faol=false")       # eski sahifa yana «O'chir» bosdi
check("A3 eski sahifa yana «O'chir» (faol=false) — 409, foydalanuvchi QAYTA YOQILMADI (ilgari yoqardi)",
      r.status_code == 409 and not faolmi("fy_ishchi"), (r.status_code, r.text[:300]))
check("A4 409 javobi: `type` = holat_ozgargan, `is_active` = false, sabab «allaqachon o'chirilgan … sahifani yangilang»",
      isinstance(detail(r), dict) and detail(r).get("type") == "holat_ozgargan" and detail(r).get("is_active") is False
      and "allaqachon o'chirilgan" in matn(r) and "sahifani yangilang" in matn(r), detail(r))
check("A5 409 da jurnalga yangi qator yozilmadi", jurnal("faolsizlantirildi", entity_id=ISH) == 1 and jurnal("faollashtirildi", entity_id=ISH) == 0,
      jurnal_qatorlari("user", ISH))
r = A.post(f"/api/users/{ISH}/toggle?faol=true")
check("A6 faol=true — 200, yoqildi; jurnalda «faollashtirildi»",
      r.status_code == 200 and js(r).get("is_active") is True and faolmi("fy_ishchi") and jurnal("faollashtirildi", entity_id=ISH) == 1,
      (r.status_code, r.text[:200], jurnal_qatorlari("user", ISH)))
r = A.post(f"/api/users/{ISH}/toggle?faol=true")
check("A7 yoqilgan foydalanuvchini yana «Faollashtir» — 409 «allaqachon faol»", r.status_code == 409 and "allaqachon faol" in matn(r),
      (r.status_code, r.text[:200]))
r = A.post(f"/api/users/{ISH}/toggle")                  # eski mijoz (maqsadsiz) — almashtirish
check("A8 maqsadsiz so'rov (eski sahifa keshi) — avvalgidek almashtiradi", r.status_code == 200 and js(r).get("is_active") is False,
      (r.status_code, r.text[:200]))
A.post(f"/api/users/{ISH}/toggle?faol=true")
r = A.post(f"/api/users/{uid('fy_admin')}/toggle?faol=false")
check("A9 admin O'ZINI o'chira olmaydi (API orqali ham) — 400, faol qoldi (ilgari 200)",
      r.status_code == 400 and "O'zingizni" in matn(r) and faolmi("fy_admin"), (r.status_code, r.text[:200]))
r = A.post(f"/api/users/{uid('fy_boshqa')}/toggle?faol=false")
check("A10 boshqa korxona foydalanuvchisi — 404 (o'zgarmadi)", r.status_code == 404 and faolmi("fy_boshqa"), (r.status_code, r.text[:200]))
# A11: oxirgi faol Admin (ikki admin bir-birini o'chirish poygasining ikkinchi yarmi — bajaruvchi allaqachon o'chirilgan). Korxonaning
# boshqa (ishga tushishda yaratilgan) adminlari vaqtincha o'chiriladi — faqat fy_admin / fy_admin2 qolsin.


def boshqa_adminlar(faol, idlar=None):
    def f(s):
        q = s.query(User).filter(User.company_id == 1, User.role == UserRole.ADMIN,
                                 ~User.username.in_(["fy_admin", "fy_admin2"]))
        if idlar is not None:
            q = q.filter(User.id.in_(idlar))
        else:
            q = q.filter(User.is_active == True)   # noqa: E712
        r = [u.id for u in q.all()]
        for u in q.all():
            u.is_active = faol
        return r
    return db_ishi(f)


_boshqa = boshqa_adminlar(False)
A.post(f"/api/users/{uid('fy_admin2')}/toggle?faol=false")


def _oxirgi(s):
    q = s.query(User).filter(User.username == "fy_admin2").first()
    try:
        auth.toggle_user_active(s, uid("fy_admin"), company_id=1, bajaruvchi=q, faol=False)
        return "o'chirdi"
    except HTTPException as e:
        s.rollback()
        return (e.status_code, e.detail)
    except TypeError as e:                 # asl kod: `faol` argumenti yo'q
        s.rollback()
        return f"TypeError: {e}"


_x = db_ishi(_oxirgi)
check("A11 korxonadagi oxirgi faol Adminni o'chirib bo'lmaydi — 400 «kamida bitta faol Admin»",
      isinstance(_x, tuple) and _x[0] == 400 and "kamida bitta faol Admin" in str(_x[1]) and faolmi("fy_admin"), _x)
if not faolmi("fy_admin"):                 # asl kod o'chirib qo'ydi — keyingi bo'limlar uchun qaytariladi
    db_ishi(lambda s: setattr(s.query(User).filter(User.username == "fy_admin").first(), "is_active", True))
    A = kirish("fy_admin")
A.post(f"/api/users/{uid('fy_admin2')}/toggle?faol=true")
check("A12 jurnal qatori: kim bajargani (performed_by) va korxona yozilgan",
      any(q[0] == "faolsizlantirildi" and q[3] == "FY Admin" and q[4] == 1 for q in jurnal_qatorlari("user", ISH)),
      jurnal_qatorlari("user", ISH))

if PG_URL:
    # A13: HAQIQIY poyga — ikki admin bir vaqtda bir-birini o'chiradi (`_pul_qulfi` 109): bittasi o'tadi, ikkinchisi 400, kamida bitta faol
    A2 = kirish("fy_admin2")
    to_siq = threading.Barrier(2)
    nat = {}
    # Poyga oynasi kafolatli bo'lsin: o'qishdan OLDIN 0.6 s kutish (qulf bo'lsa — ikkinchisi birinchisi tugashini kutadi va
    # o'zgargan holatni o'qiydi; qulfsiz — ikkalasi ham «ikkinchi Admin faol» deb o'qib, ikkalasi o'chadi)
    _asl_toggle = auth.toggle_user_active

    def _sekin_toggle(*a, **k):
        time.sleep(0.6)
        return _asl_toggle(*a, **k)
    auth.toggle_user_active = _sekin_toggle

    def _poyga(nom, c, nishon):
        to_siq.wait()
        nat[nom] = c.post(f"/api/users/{nishon}/toggle?faol=false").status_code

    _t = [threading.Thread(target=_poyga, args=("a", A, uid("fy_admin2"))),
          threading.Thread(target=_poyga, args=("b", A2, uid("fy_admin")))]
    [x.start() for x in _t]
    [x.join(30) for x in _t]
    auth.toggle_user_active = _asl_toggle
    _f = db_ishi(lambda s: s.query(User).filter(User.company_id == 1, User.role == UserRole.ADMIN, User.is_active == True).count())  # noqa: E712
    check("A13 [poyga] ikki admin bir-birini bir vaqtda o'chirdi — korxonada kamida bitta faol Admin qoldi (bittasi 400 / 401)",
          _f >= 1 and sorted(nat.values()) != [200, 200], (nat, _f))
    # tiklash: kim faol bo'lsa o'sha qolgan admin(lar)ni yoqadi
    for _l in ("fy_admin", "fy_admin2"):
        db_ishi(lambda s, _l=_l: setattr(s.query(User).filter(User.username == _l).first(), "is_active", True))
    A = kirish("fy_admin")
else:
    print("  · A13 (ikki admin poygasi) — faqat PG rejimida")
boshqa_adminlar(True, _boshqa)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Foydalanuvchi yaratish — amal kaliti, jurnal (U4, X2)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_tana = {"username": "fy_yangi1", "password": PAROL, "role": "manager", "full_name": "Yangi Bir"}
K1 = "fy175kalit0001abcd"
r1 = A.post("/api/users", json=_tana, headers={"X-Amal-Kaliti": K1})
check("B1 yaratildi (kalit bilan) — 200", r1.status_code == 200 and js(r1).get("username") == "fy_yangi1", (r1.status_code, r1.text[:200]))
_yid = js(r1).get("id")
check("B2 jurnalda «created» (user) — 1 qator; parol yozilmagan",
      jurnal("created", entity_id=_yid) == 1 and not any(PAROL in (q[1] + q[2]) for q in jurnal_qatorlari("user", _yid)),
      jurnal_qatorlari("user", _yid))
r2 = A.post("/api/users", json=_tana, headers={"X-Amal-Kaliti": K1})   # javob yo'qolgan, qayta bosildi
check("B3 o'sha kalit bilan qayta — 200 (birinchi javob), «Bu username band» EMAS; `takror` va `X-Takror: 1`",
      r2.status_code == 200 and js(r2).get("id") == _yid and js(r2).get("takror") is True and r2.headers.get("X-Takror") == "1",
      (r2.status_code, r2.text[:200], dict(r2.headers)))
check("B4 bazada bitta foydalanuvchi, jurnalda bitta «created»",
      db_ishi(lambda s: s.query(User).filter(User.username == "fy_yangi1").count()) == 1 and jurnal("created", entity_id=_yid) == 1)
r3 = A.post("/api/users", json=_tana, headers={"X-Amal-Kaliti": "fy175kalit0002abcd"})
check("B5 YANGI kalit, band login — 400 (sabab bilan), ikkinchi foydalanuvchi yo'q",
      r3.status_code == 400 and db_ishi(lambda s: s.query(User).filter(User.username == "fy_yangi1").count()) == 1,
      (r3.status_code, r3.text[:200]))
r4 = A.post("/api/users", json={**_tana, "username": "fy_yangi2"}, headers={"X-Amal-Kaliti": "x"})
check("B6 noto'g'ri kalit — 400, foydalanuvchi yaratilmadi",
      r4.status_code == 400 and db_ishi(lambda s: s.query(User).filter(User.username == "fy_yangi2").count()) == 0, (r4.status_code, r4.text[:200]))
r5 = A.post("/api/users", json={**_tana, "username": "fy_yangi3"})
check("B7 kalitsiz (eski sahifa) — avvalgidek 200, jurnalda «created»",
      r5.status_code == 200 and jurnal("created", entity_id=js(r5).get("id")) == 1, (r5.status_code, r5.text[:200]))
r6 = A.post("/api/users", json={**_tana, "username": "fy_yangi4", "password": "1"}, headers={"X-Amal-Kaliti": "fy175kalit0003abcd"})
r7 = A.post("/api/users", json={**_tana, "username": "fy_yangi4"}, headers={"X-Amal-Kaliti": "fy175kalit0003abcd"})
check("B8 rad etilgan so'rov kaliti saqlanmaydi: o'sha kalit bilan to'g'rilangan so'rov — yaratadi (takror emas)",
      r6.status_code == 400 and r7.status_code == 200 and js(r7).get("takror") is not True
      and db_ishi(lambda s: s.query(User).filter(User.username == "fy_yangi4").count()) == 1, (r6.status_code, r7.status_code, r7.text[:200]))
_k = db_ishi(lambda s: s.execute(__import__("sqlalchemy").text(
    "SELECT COUNT(*) FROM amal_kalitlari WHERE amal_turi = 'foydalanuvchi_yaratish'")).scalar())
check("B9 amal kaliti qatorlari: `foydalanuvchi_yaratish` turi bilan (2 ta: B1, B8)", _k == 2, _k)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Parol — jurnal (X2); parolning o'zi yozilmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PID = uid("fy_parol")
r = A.post(f"/api/users/{PID}/password", json={"new_password": "YangiParol777"})
check("C1 admin boshqa foydalanuvchi parolini tikladi — 200; jurnalda «password_reset» (ilgari 0 qator)",
      r.status_code == 200 and jurnal("password_reset", entity_id=PID) == 1, (r.status_code, r.text[:200], jurnal_qatorlari("user", PID)))
check("C2 jurnal qatorida yangi parol YO'Q", not any("YangiParol777" in (q[1] + q[2]) for q in jurnal_qatorlari("user", PID)),
      jurnal_qatorlari("user", PID))
AID = uid("fy_admin")
r = A.post(f"/api/users/{AID}/password", json={"new_password": "AdminYangi888", "current_password": PAROL})
check("C3 admin O'Z parolini o'zgartirdi — 200; jurnalda «parol_ozgartirildi»",
      r.status_code == 200 and jurnal("parol_ozgartirildi", entity_id=AID) == 1, (r.status_code, r.text[:200], jurnal_qatorlari("user", AID)))
r = A.post(f"/api/users/{AID}/password", json={"new_password": "Boshqa999", "current_password": "notogri"})
check("C4 joriy parol noto'g'ri — 400, jurnalga yozilmadi", r.status_code == 400 and jurnal("parol_ozgartirildi", entity_id=AID) == 1,
      (r.status_code, r.text[:200]))
A.post(f"/api/users/{AID}/password", json={"new_password": PAROL, "current_password": "AdminYangi888"})


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Loyihani tiklash — savatda bo'lmasa 409, soxta yozuv yo'q (T2)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def loyiha(raqam, ochirilgan):
    def f(s):
        p = Project(company_id=1, project_number=raqam, project_name="FY " + raqam, client_name="Mijoz", is_deleted=ochirilgan)
        s.add(p)
        s.flush()
        return p.id
    return db_ishi(f)


P1 = loyiha("FY-P1", False)
r = A.post(f"/api/projects/{P1}/restore")
check("D1 savatda BO'LMAGAN loyiha — 409 «savatda emas … allaqachon tiklangan» (ilgari 200)",
      r.status_code == 409 and "savatda emas" in matn(r), (r.status_code, r.text[:200]))
check("D2 soxta «restored» yozuvi yo'q (ilgari har bosishda bittadan)", jurnal("restored", "project", P1) == 0, jurnal_qatorlari("project", P1))
P2 = loyiha("FY-P2", True)
ra, rb = A.post(f"/api/projects/{P2}/restore"), A.post(f"/api/projects/{P2}/restore")
check("D3 savatdagi loyiha: 1-tiklash 200, 2-si (ikkinchi oyna) 409; jurnalda BITTA «restored»",
      ra.status_code == 200 and rb.status_code == 409 and jurnal("restored", "project", P2) == 1
      and db_ishi(lambda s: s.get(Project, P2).is_deleted) is False, (ra.status_code, rb.status_code, jurnal_qatorlari("project", P2)))
P3 = loyiha("FY-P3", True)
ra, rb = A.delete(f"/api/projects/{P3}/permanent"), A.delete(f"/api/projects/{P3}/permanent")
check("D4 butunlay o'chirish: 1-si 200, 2-si 404 (loyiha yo'q)", ra.status_code == 200 and rb.status_code in (400, 404),
      (ra.status_code, rb.status_code, rb.text[:200]))
r = A.post("/api/projects/999999/restore")
check("D5 yo'q loyiha — 404", r.status_code == 404, (r.status_code, r.text[:200]))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Qulf: butunlay o'chirish tiklash bilan BIR qulfda (T3, T4) — faqat PG")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
OID = None
if PG_URL:
    from sqlalchemy import text as _sql

    def qulf_poygasi(ns, kalit, url, usul, tiklash_sql):
        """Boshqa ulanish `pg_advisory_xact_lock(ns, kalit)` ni ushlab turadi (tiklash ketmoqda); `url` ga so'rov — qulfni kutishi kerak.
        Ushlovchi tranzaksiya obyektni TIKLAYDI va yakunlaydi; natija: (kutildi_mi, so'rov holati)."""
        natija = {}
        con = engine.connect()
        trx = con.begin()
        con.execute(_sql("SELECT pg_advisory_xact_lock(:a, :b)"), {"a": ns, "b": kalit})

        def _sorov():
            t0 = time.time()
            rr = getattr(A, usul)(url)
            natija["holat"], natija["vaqt"], natija["matn"] = rr.status_code, time.time() - t0, rr.text[:200]

        th = threading.Thread(target=_sorov)
        th.start()
        th.join(1.2)
        natija["kutdi"] = th.is_alive()
        con.execute(_sql(tiklash_sql), {"i": kalit})
        trx.commit()
        con.close()
        th.join(30)
        return natija

    # T3: buyurtma — savatda; boshqa tranzaksiya uni tiklamoqda (101 qulfi), shu payt «Butunlay o'chirish»
    _prj = loyiha("FY-PO", False)
    _o = A.post("/api/orders?confirm_shortage=true", json={"project_id": _prj, "order_type": "product", "items": [
        {"name": "FY detal", "category": "panel", "width": 50, "thickness": 5, "quantity": 1, "unit_price": 1000, "is_coated": False}]})
    OID = js(_o).get("id")
    check("E0 sinov buyurtmasi yaratildi", bool(OID), _o.text[:300])
    if OID:
        db_ishi(lambda s: setattr(s.get(Order, OID), "is_deleted", True))
        n = qulf_poygasi(101, OID, f"/api/orders/{OID}/permanent", "delete", "UPDATE orders SET is_deleted = false WHERE id = :i")
        check("E1 buyurtmani butunlay o'chirish tiklash qulfini KUTDI (ilgari kutmasdi — endigina tiklangan buyurtmani o'chirardi)",
              n.get("kutdi") is True, n)
        check("E2 qulfdan keyin qayta o'qildi: buyurtma tiklangan — o'chirilmadi (404), buyurtma bazada, savatda emas",
              n.get("holat") == 404 and db_ishi(lambda s: (s.get(Order, OID) is not None) and s.get(Order, OID).is_deleted is False), n)
    # T4: loyiha
    P4 = loyiha("FY-P4", True)
    n = qulf_poygasi(108, P4, f"/api/projects/{P4}/permanent", "delete", "UPDATE projects SET is_deleted = false WHERE id = :i")
    check("E3 loyihani butunlay o'chirish tiklash qulfini KUTDI", n.get("kutdi") is True, n)
    check("E4 qulfdan keyin: loyiha tiklangan — o'chirilmadi (400 «topilmadi»), loyiha bazada",
          n.get("holat") in (400, 404) and db_ishi(lambda s: s.get(Project, P4) is not None and s.get(Project, P4).is_deleted is False), n)
    P5 = loyiha("FY-P5", True)
    n = qulf_poygasi(108, P5, f"/api/projects/{P5}/restore", "post", "UPDATE projects SET is_deleted = false WHERE id = :i")
    check("E5 ikki oynada bir vaqtda «Tiklash»: ikkinchisi qulfni kutdi va 409 (soxta ikkinchi «tiklandi» yo'q)",
          n.get("kutdi") is True and n.get("holat") == 409 and jurnal("restored", "project", P5) == 0, n)
else:
    print("  · E (qulf) — faqat PG rejimida (SQLite da `_pul_qulfi` yo'q)")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. «Mahsulot turlari» — bo'sh ro'yxat faqat `bosh=1` bilan (C1)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def yoqilgan():
    return {c["code"]: c["enabled"] for c in (js(A.get("/api/settings/categories")).get("categories") or [])}


_hammasi = ",".join(yoqilgan())
A.put("/api/settings/categories", data={"codes": _hammasi})
_oldin = yoqilgan()
check("F0 boshlang'ich: hamma ixtiyoriy turlar yoqilgan", _oldin and all(_oldin.values()), _oldin)
SZ = kirish("fy_soz")
r = SZ.put("/api/settings/categories", data={"codes": ""})
check("F1 «Ko'rish» siz «Tahrirlash» roli, ro'yxat yuklanmagan sahifa (`codes=''`) — 400, hech narsa o'chmadi (ilgari 200 va Loy / Blok O'CHARDI)",
      r.status_code == 400 and yoqilgan() == _oldin, (r.status_code, r.text[:200], yoqilgan()))
check("F2 400 sababi — «ro'yxati yuklanmagan … hech narsa saqlanmadi»", "yuklanmagan" in matn(r) and "saqlanmadi" in matn(r), matn(r))
r = A.put("/api/settings/categories", data={"codes": ""})
check("F3 admin ham `bosh` siz bo'sh ro'yxat — 400", r.status_code == 400 and yoqilgan() == _oldin, (r.status_code, r.text[:200]))
r = A.put("/api/settings/categories", data={"codes": "", "bosh": "1"})
check("F4 `bosh=1` — hammasi ataylab o'chirildi (200)", r.status_code == 200 and not any(yoqilgan().values()), (r.status_code, yoqilgan()))
r = A.put("/api/settings/categories", data={"codes": "noma_lum_tur", "bosh": "0"})
check("F5 faqat noma'lum kodlar (`bosh` yo'q) — 400 (bo'sh ro'yxat deb olinmaydi)", r.status_code == 400, (r.status_code, r.text[:200]))
r = A.put("/api/settings/categories", data={"codes": _hammasi})
check("F6 oddiy saqlash — 200, qaytdi", r.status_code == 200 and all(yoqilgan().values()), (r.status_code, yoqilgan()))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. Sahifalar (server chizgan): tugmalar — ruxsat bilan (C8, C1, C2, T1)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_h = kirish("fy_jur").get("/sozlamalar").text
check("G1 «Tizim jurnallari: Ko'rish» — «Sozlamalar» ochiladi, lekin Saqlash / Logotip / Tozalash / Ulash / Qo'shish tugmalari YO'Q",
      'id="co-save-btn"' not in _h and 'id="cat-save-btn"' not in _h and 'id="tg-save-btn"' not in _h and 'id="tg-clear-btn"' not in _h
      and 'id="co-logo-btn"' not in _h and 'id="tg-ulash-btn"' not in _h and 'id="yon-qosh-btn"' not in _h and "Ko'rish rejimi" in _h,
      [x for x in ('co-save-btn', 'cat-save-btn', 'tg-save-btn', 'tg-clear-btn', 'yon-qosh-btn', "Ko'rish rejimi") if x in _h])
check("G2 … yo'nalish qatorlari tugmasiz (`YON_TAHRIR = false`, `YON_OCHIR = false`)",
      "const YON_TAHRIR = false;" in _h and "const YON_OCHIR = false;" in _h)
_h = A.get("/sozlamalar").text
check("G3 Admin — tugmalar bor; «Saqlash» (korxona, mahsulot turlari) ma'lumot yuklanmaguncha YOPIQ (`disabled`)",
      re.search(r'<button[^>]*id="co-save-btn"[^>]*disabled', _h) and re.search(r'<button[^>]*id="cat-save-btn"[^>]*disabled', _h)
      and 'id="tg-save-btn"' in _h and 'id="yon-qosh-btn"' in _h and "Ko'rish rejimi" not in _h
      and "const YON_TAHRIR = true;" in _h and "const YON_OCHIR = true;" in _h)
_h = kirish("fy_soz2").get("/sozlamalar").text
check("G4 «Sozlamalar: Ko'rish + Tahrirlash» (yaratish / o'chirishsiz) — Saqlash bor, yo'nalish qo'shish YO'Q, `YON_OCHIR = false`",
      'id="co-save-btn"' in _h and 'id="yon-qosh-btn"' not in _h and "const YON_TAHRIR = true;" in _h and "const YON_OCHIR = false;" in _h)


def trash_tugmalari(c):
    h = c.get("/trash").text
    return {"loyiha_t": "restoreItem('project'" in h, "loyiha_o": "permanentDelete('project'" in h,
            "buyurtma_t": "restoreItem('order'" in h, "buyurtma_o": "permanentDelete('order'" in h,
            "hodim_t": "hodimTiklash(" in h and 'onclick="hodimTiklash(' in h, "hodim_o": "permanentDelete('employee'" in h,
            "hodim_kor": "FY175 Hodim" in h}


loyiha("FY-PT", True)
if OID and db_ishi(lambda s: s.get(Order, OID) is not None):       # asl kodda (qulfsiz) E bo'limi buyurtmani o'chirib yuborgan bo'ladi
    db_ishi(lambda s: setattr(s.get(Order, OID), "is_deleted", True))
else:
    _po = A.post("/api/orders?confirm_shortage=true", json={"project_id": loyiha("FY-PO2", False), "order_type": "product", "items": [
        {"name": "FY detal 2", "category": "panel", "width": 50, "thickness": 5, "quantity": 1, "unit_price": 1000, "is_coated": False}]})
    OID = js(_po).get("id")
    if OID:
        db_ishi(lambda s: setattr(s.get(Order, OID), "is_deleted", True))
db_ishi(lambda s: s.add(Employee(company_id=1, name="FY175 Hodim", is_deleted=True)))
_v = trash_tugmalari(kirish("fy_sav"))
check("G5 «O'chirilganlar: Ko'rish» — ro'yxat bor, Tiklash / Butunlay o'chirish tugmalari YO'Q (ilgari bor edi, bosilsa 403)",
      _v["hodim_kor"] and not any(_v[k] for k in ("loyiha_t", "loyiha_o", "buyurtma_t", "buyurtma_o", "hodim_t", "hodim_o")), _v)
_v = trash_tugmalari(kirish("fy_sav2"))
check("G6 «O'chirilganlar» to'liq, «Hodimlar» yo'q — loyiha / buyurtma tugmalari bor, HODIM tugmalari yo'q (server «Hodimlar» so'raydi)",
      _v["loyiha_t"] and _v["loyiha_o"] and _v["buyurtma_t"] and _v["buyurtma_o"] and not _v["hodim_t"] and not _v["hodim_o"], _v)
_v = trash_tugmalari(A)
check("G7 Admin — hamma tugmalar", all(_v.values()), _v)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. «Audit jurnali»: yangi amallar nomi bilan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("H1 AUDIT_AMALLARI: faollashtirildi, faolsizlantirildi, parol_ozgartirildi",
      all(k in crud.AUDIT_AMALLARI for k in ("faollashtirildi", "faolsizlantirildi", "parol_ozgartirildi")))
_h = A.get("/logs?tab=audit").text
check("H2 /logs (audit) — «o'chirildi (kira olmaydi)» va «paroli tiklandi» yozuvlari ko'rinadi",
      "o'chirildi (kira olmaydi)" in _h.replace("&#39;", "'") and "paroli tiklandi" in _h, len(_h))


print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
