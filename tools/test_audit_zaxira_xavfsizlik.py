#!/usr/bin/env python3
"""
test_audit_zaxira_xavfsizlik.py — kech139 (zip 167): AUDIT 1-to'lqin — zaxiradan tiklash va foydalanuvchi boshqaruvi.

NIMA UCHUN KERAK (har biri O'LCHANGAN — asl kod zip 166):
  A-T01 (production zaxirasi bilan, `work/audit/tiklash_tajriba.py`): zaxirani BO'SH yangi bazaga tiklash (falokatdan keyingi
        asosiy holat) YIQILARDI — `import_full_backup` tozalashni faqat `replace and mavjud` da qilardi; startup migratsiyalari
        yaratgan `company_settings` qatorlari bilan «duplicate key company_settings_pkey».
  A-X07: fayldagi bog'lanishlar tekshirilmasdi — `company_id` ustuni yo'q jadval qatori (to'lov) BOSHQA korxona buyurtmasiga
        ishora qilsa ham qo'shilardi (B buyurtmasi qarzi kamayardi); `employee_sessions` ham tiklanardi.
  A-X01: platforma egasi — 1-korxonaning oddiy foydalanuvchisi; foydalanuvchi boshqaruvi (parol / faollik / rol) faqat «Admin»
        rolini tekshirardi — o'sha korxonaga qo'shilgan BOSHQA Admin platforma egasi hisobini o'zgartira olardi.
  A-X02: platforma «admin parolini tiklash» eski kirishlarni (sessiya) yopmasdi.
  A-X03: foydalanuvchi o'chirilganda sessiyalari qolardi — qayta faollashtirilsa ESKI cookie yana ishlardi.
TALAB:
  Z  tiklash: bo'sh korxonaga (startup qatorlari bor) — muvaffaqiyatli, ma'lumot AYNAN; ma'lumotli korxonaga replace bilan — 2 marta;
     boshqa korxona yozuviga ishora qiluvchi fayl — rad, HECH NARSA o'zgarmaydi (A ham, B ham); sessiya jadvali — tiklanmaydi;
     HTTP `POST /api/system/restore` (platforma egasi, bo'sh korxona) — 200.
  X  boshqa Admin → platforma egasi: parol / faollik / rol — 403 va bazada o'zgarish yo'q; oddiy foydalanuvchiga — 200 (avvalgidek);
     platforma egasi o'z parolini almashtiradi; sahifalarda platforma egasi qatorida tugma / rol tanlovi yo'q («🏛 Platforma egasi»).
  S  platforma «admin parolini tiklash» — o'sha foydalanuvchining hamma sessiyasi o'chadi (eski cookie — 401); foydalanuvchi
     o'chirilganda sessiyalari o'chadi, qayta faollashtirilganda eski cookie — 401.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (har ishga yangi baza).
ISHLATISH: python3 tools/test_audit_zaxira_xavfsizlik.py
"""
import os
import re
import sys
import json
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "audit_zaxira_xav_test"
_T = tempfile.mkdtemp(prefix="audit_zx_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'audit_zx_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (User, UserRole, UserSession, Project, ProjectStatus, Order, OrderStatus, OrderType, PaymentStatus,  # noqa: E402
                    Payment, PaymentType, PaymentMethod, Master, CompanySetting, Rol, EmployeeSession)
from production_models import Company              # noqa: E402
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


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


PAROL = "Parol123!"


def kirish(login, parol=PAROL):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": parol}, follow_redirects=False)
    return c, r.status_code


with TestClient(main.app, base_url="https://testserver") as _c0:      # startup (jadvallar, migratsiyalar, standart admin)
    _c0.get("/login")

# ── Fikstura: 1-korxona (platforma egasi + boshqa Admin + oddiy foydalanuvchi), 2-korxona (admin), ma'lumot ──────────────
db = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    if not db.query(Company).filter(Company.id == 2).first():
        db.add(Company(id=2, name="Audit B korxona"))
        db.commit()
    P = auth.create_user(db, "az_egasi", PAROL, UserRole.ADMIN, "Platforma egasi", company_id=1)
    X = auth.create_user(db, "az_admin2", PAROL, UserRole.ADMIN, "Ikkinchi admin", company_id=1)
    U = auth.create_user(db, "az_oddiy", PAROL, UserRole.MANAGER, "Oddiy menejer", company_id=1)
    BA = auth.create_user(db, "az_b_admin", PAROL, UserRole.ADMIN, "B admin", company_id=2)
db.query(User).filter(User.is_platform_admin == True).update({User.is_platform_admin: False})   # noqa: E712
db.query(User).filter(User.id == P.id).update({User.is_platform_admin: True})
db.commit()
P_ID, X_ID, U_ID, BA_ID = P.id, X.id, U.id, BA.id


def buyurtma(cid, nom, summa, tolov):
    pr = Project(company_id=cid, client_name=f"{nom} mijoz", project_name=f"{nom} loyiha", status=ProjectStatus.ACTIVE)
    db.add(pr)
    db.flush()
    o = Order(company_id=cid, project_id=pr.id, order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS,
              payment_status=PaymentStatus.PARTIAL if tolov else PaymentStatus.UNPAID, order_number=f"{nom}-1",
              total_amount=summa, agreed_amount=summa)
    db.add(o)
    db.flush()
    if tolov:
        db.add(Payment(order_id=o.id, amount=tolov, payment_type=PaymentType.PARTIAL, payment_method=PaymentMethod.CASH))
    db.add(Master(company_id=cid, name=f"{nom} usta", phone=f"+99890{abs(hash(nom)) % 10000000:07d}"))
    db.commit()
    return pr.id, o.id


A_PR, A_ORD = buyurtma(1, "AZA", 1_000_000, 300_000)
B_PR, B_ORD = buyurtma(2, "AZB", 2_000_000, 500_000)
db.close()


def korxona_holati(cid):
    s = SessionLocal()
    try:
        _o = s.query(Order).filter(Order.company_id == cid).order_by(Order.id).all()
        return {"buyurtma": [(o.id, o.order_number, float(o.agreed_amount or 0)) for o in _o],
                "tolov": sorted((p.order_id, float(p.amount)) for p in s.query(Payment).join(Order, Payment.order_id == Order.id)
                                .filter(Order.company_id == cid).all()),
                "usta": s.query(Master).filter(Master.company_id == cid).count(),
                "loyiha": s.query(Project).filter(Project.company_id == cid).count()}
    finally:
        s.close()


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxiradan tiklash (A-T01, A-X07)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
ZAXIRA = json.loads(json.dumps(crud.export_full_backup(s, company_id=1), default=str))
s.close()
A0, B0 = korxona_holati(1), korxona_holati(2)
_sozlama = [(r.get("key"), r.get("value")) for r in (ZAXIRA["tables"].get("company_settings") or [])]
check("Z0 eksport: A ma'lumoti va startup sozlamalari zaxirada (buyurtma 1, to'lov 1, sozlama ≥ 1)",
      len(ZAXIRA["tables"].get("orders") or []) == 1 and len(ZAXIRA["tables"].get("payments") or []) == 1 and _sozlama,
      [len(ZAXIRA["tables"].get("orders") or []), _sozlama])

# «Yangi o'rnatish»: A tozalanadi, so'ng startup yaratadigan sozlama qatorlari (zaxiradagi kalitlar) qaytadan yoziladi
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    crud.factory_reset_all_data(s, company_id=1)
for k, v in _sozlama:
    s.add(CompanySetting(company_id=1, key=k, value=v))
s.commit()
_bosh = korxona_holati(1)
r1 = crud.import_full_backup(s, json.loads(json.dumps(ZAXIRA)), company_id=1, replace=False)
s.close()
check("Z1 BO'SH korxonaga (startup sozlama qatorlari bor) tiklash — muvaffaqiyatli (asl kod: duplicate key company_settings)",
      _bosh["buyurtma"] == [] and isinstance(r1, dict) and r1.get("success") is True, (r1.get("message") if isinstance(r1, dict) else r1))
check("Z2 tiklangan A ma'lumoti AYNAN (buyurtma, to'lov, usta, loyiha); B ga tegilmadi",
      korxona_holati(1) == A0 and korxona_holati(2) == B0, (korxona_holati(1), A0, korxona_holati(2), B0))
s = SessionLocal()
r2 = crud.import_full_backup(s, json.loads(json.dumps(ZAXIRA)), company_id=1, replace=True)
r3 = crud.import_full_backup(s, json.loads(json.dumps(ZAXIRA)), company_id=1, replace=True)
_rad = crud.import_full_backup(s, json.loads(json.dumps(ZAXIRA)), company_id=1, replace=False)
s.close()
check("Z3 ma'lumotli korxonaga replace=True bilan 2 marta — muvaffaqiyatli, AYNAN; replace siz — rad (avvalgidek)",
      r2.get("success") is True and r3.get("success") is True and korxona_holati(1) == A0 and _rad.get("success") is False,
      [r2.get("message"), r3.get("message"), _rad.get("message")])

# Buzilgan fayl: A to'lovi B buyurtmasiga ishora qiladi
_buzuq = json.loads(json.dumps(ZAXIRA))
_buzuq["tables"]["payments"].append({**_buzuq["tables"]["payments"][0], "id": 900001, "order_id": B_ORD, "amount": 1_500_000.0})
s = SessionLocal()
r4 = crud.import_full_backup(s, _buzuq, company_id=1, replace=True)
s.close()
check("Z4 boshqa korxona buyurtmasiga ishora qiluvchi to'lov — tiklash RAD (sabab: jadval.ustun), A va B o'zgarmadi",
      r4.get("success") is False and "payments.order_id" in (r4.get("message") or "") and korxona_holati(1) == A0
      and korxona_holati(2) == B0, [r4, korxona_holati(1), korxona_holati(2)])
_buzuq2 = json.loads(json.dumps(ZAXIRA))
_buzuq2["tables"]["orders"][0]["project_id"] = B_PR
s = SessionLocal()
r5 = crud.import_full_backup(s, _buzuq2, company_id=1, replace=True)
s.close()
check("Z5 `company_id` li jadval ham: A buyurtmasi B loyihasiga ishora qilsa — rad, o'zgarish yo'q",
      r5.get("success") is False and "orders.project_id" in (r5.get("message") or "") and korxona_holati(1) == A0
      and korxona_holati(2) == B0, r5)
_sess = json.loads(json.dumps(ZAXIRA))
_sess["tables"]["employee_sessions"] = [{"id": 900002, "employee_id": 1, "token": "SOXTA_TOKEN_AZ", "expires_at": "2099-01-01T00:00:00"}]
s = SessionLocal()
r6 = crud.import_full_backup(s, _sess, company_id=1, replace=True)
_es = s.query(EmployeeSession).filter(EmployeeSession.token == "SOXTA_TOKEN_AZ").count()
s.close()
check("Z6 faylda `employee_sessions` — tiklanmaydi (o'tkazib yuboriladi), qolgani tiklanadi",
      r6.get("success") is True and _es == 0 and "employee_sessions" in (r6.get("skipped_tables") or [])
      and korxona_holati(1) == A0, [r6.get("message"), r6.get("skipped_tables"), _es])

# HTTP marshrut: platforma egasi, bo'sh korxona (startup sozlamalari bilan)
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    crud.factory_reset_all_data(s, company_id=1)
for k, v in _sozlama:
    s.add(CompanySetting(company_id=1, key=k, value=v))
s.commit()
s.close()
CP, _st = kirish("az_egasi")
rh = CP.post("/api/system/restore", files={"file": ("zaxira.json", json.dumps(ZAXIRA).encode("utf-8"), "application/json")})
check("Z7 HTTP POST /api/system/restore (platforma egasi, bo'sh korxona) — 200, ma'lumot AYNAN",
      _st == 302 and rh.status_code == 200 and js(rh).get("success") is True and korxona_holati(1) == A0,
      [_st, rh.status_code, rh.text[:300]])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("X. Platforma egasi hisobi (A-X01)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════


def foydalanuvchi(uid):
    s = SessionLocal()
    try:
        u = s.query(User).filter(User.id == uid).first()
        return (u.password_hash, bool(u.is_active), u.rol_id, u.role.value)
    finally:
        s.close()


CX, _stx = kirish("az_admin2")
P0 = foydalanuvchi(P_ID)
_s = SessionLocal()
_men_rol = [r for r in _s.query(Rol).filter(Rol.company_id == 1).all() if (r.kod or "") == "menejer"][0].id
_s.close()
rp = CX.post(f"/api/users/{P_ID}/password", json={"new_password": "YangiParol99"})
rt = CX.post(f"/api/users/{P_ID}/toggle")
rr = CX.put(f"/api/users/{P_ID}/rol", json={"rol_id": _men_rol})
check("X1 boshqa Admin → platforma egasi: parol / faollik / rol — 403 (asl kod: 200, 200, 200)",
      _stx == 302 and (rp.status_code, rt.status_code, rr.status_code) == (403, 403, 403),
      [_stx, rp.status_code, rt.status_code, rr.status_code, rp.text[:200]])
check("X2 platforma egasi hisobi bazada O'ZGARMADI (parol xeshi, faol, rol)", foydalanuvchi(P_ID) == P0, [foydalanuvchi(P_ID), P0])
_, _stp_eski = kirish("az_egasi")
_, _stp_yangi = kirish("az_egasi", "YangiParol99")
check("X3 platforma egasi eski paroli bilan kiradi, «yangi» parol ishlamaydi", _stp_eski == 302 and _stp_yangi != 302,
      [_stp_eski, _stp_yangi])
U0 = foydalanuvchi(U_ID)
rpu = CX.post(f"/api/users/{U_ID}/password", json={"new_password": "OddiyYangi77"})
rtu = CX.post(f"/api/users/{U_ID}/toggle")
rtu2 = CX.post(f"/api/users/{U_ID}/toggle")
check("X4 boshqa Admin ODDIY foydalanuvchini avvalgidek boshqaradi (parol 200, o'chirish / yoqish 200)",
      (rpu.status_code, rtu.status_code, rtu2.status_code) == (200, 200, 200) and foydalanuvchi(U_ID)[0] != U0[0]
      and foydalanuvchi(U_ID)[1] is True, [rpu.status_code, rtu.status_code, rtu2.status_code])
CP, _ = kirish("az_egasi")
rpo = CP.post(f"/api/users/{P_ID}/password", json={"new_password": "EgaYangi55", "current_password": PAROL})
_, _st_ega = kirish("az_egasi", "EgaYangi55")
check("X5 platforma egasi O'Z parolini almashtiradi (joriy parol bilan) — 200, yangi parol bilan kiradi",
      rpo.status_code == 200 and _st_ega == 302, [rpo.status_code, rpo.text[:200], _st_ega])
CX, _ = kirish("az_admin2")
_html = CX.get("/users").text
_qator = re.search(r'<tr id="urow-%d">(.*?)</tr>' % P_ID, _html, re.S)
_q = _qator.group(1) if _qator else ""
check("X6 «Foydalanuvchilar» sahifasi (boshqa Admin): platforma egasi qatorida «🏛 Platforma egasi», tugma / rol tanlovi YO'Q;"
      " oddiy foydalanuvchida — bor",
      _qator and "Platforma egasi" in _q and "toggleUser(" not in _q and "changePass(" not in _q and "u-rol-tanlov" not in _q
      and re.search(r'<tr id="urow-%d">.*?toggleUser\(' % U_ID, _html, re.S), _q[:400])
_ar = js(CX.get("/api/rollar"))
_fp = {u["id"]: u.get("platforma_egasi") for u in _ar.get("foydalanuvchilar", [])}
_rl = open(os.path.join(ROOT, "templates", "rollar.html"), encoding="utf-8").read()
check("X7 /api/rollar: platforma egasi belgilangan (`platforma_egasi`), boshqalar — yo'q; «Rollar» sahifasi unga tanlov chizmaydi",
      _fp.get(P_ID) is True and _fp.get(U_ID) is False and _fp.get(X_ID) is False
      and "u.platforma_egasi ? '<span class=\"rl-belgi\">🏛 Platforma egasi</span>'" in _rl, _fp)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Sessiyalar (A-X02, A-X03)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
CB, _stb = kirish("az_b_admin")
_b_oldin = CB.get("/api/dashboard/today-tasks").status_code
CP, _ = kirish("az_egasi", "EgaYangi55")
rres = CP.post("/api/platform/companies/2/reset-admin-password", data={"username": "az_b_admin"})
_b_keyin = CB.get("/api/dashboard/today-tasks").status_code
s = SessionLocal()
_b_sess = s.query(UserSession).filter(UserSession.user_id == BA_ID).count()
s.close()
check("S1 platforma «admin parolini tiklash» — B adminining eski kirishi yopildi (oldin 200 → keyin 401), sessiya 0"
      " (asl kod: 200, sessiya qolardi)",
      _stb == 302 and _b_oldin == 200 and rres.status_code == 200 and _b_keyin == 401 and _b_sess == 0,
      [_stb, _b_oldin, rres.status_code, _b_keyin, _b_sess])
CU, _stu = kirish("az_oddiy", "OddiyYangi77")
_u_oldin = CU.get("/api/dashboard/today-tasks").status_code
CX, _ = kirish("az_admin2")
ro = CX.post(f"/api/users/{U_ID}/toggle")
s = SessionLocal()
_u_sess = s.query(UserSession).filter(UserSession.user_id == U_ID).count()
s.close()
ry = CX.post(f"/api/users/{U_ID}/toggle")
_u_keyin = CU.get("/api/dashboard/today-tasks").status_code
_, _stu2 = kirish("az_oddiy", "OddiyYangi77")
check("S2 foydalanuvchi o'chirildi — sessiyalari 0; qayta yoqilgach ESKI cookie — 401 (asl kod: 200), yangidan kira oladi",
      _stu == 302 and _u_oldin == 200 and js(ro).get("is_active") is False and _u_sess == 0 and js(ry).get("is_active") is True
      and _u_keyin == 401 and _stu2 == 302, [_stu, _u_oldin, js(ro), _u_sess, js(ry), _u_keyin, _stu2])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
