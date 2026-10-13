#!/usr/bin/env python3
"""
test_audit_pul2.py — kech141 (zip 169): AUDIT — PUL topilmalari (2-qism).

NIMA UCHUN KERAK (har biri O'LCHANGAN — asl kod zip 168, `work/k169/probe_p02.py`, `work/k169_tayyorgarlik/`):
  A-P02 o'chirilgan / faolsizlantirilgan HODIM o'tgan oylar hisobotidan ham yo'qolardi (oyligi va avanslari tushib, sof foyda
        oshardi); «❌ Butunlay o'chirish» hodimni avanslari bilan bazadan o'chirardi; o'chirilmagan hodimni «tiklash» 200 va jurnalda
        soxta «tiklandi». Egasi QARORLARI: ketgan oy oyligi KETGAN KUNGACHA (kunlarga mutanosib), ketgan sanani admin TANLAYDI
        (oldindan bugun), o'tgan oylar o'zgarmaydi (11.10); oy o'rtasida kirgan hodim — «Kirgan kundan» (qo'shish oynasida «Ishga
        kirgan sana»), hozirgi hodimlarning o'tgan oylari o'zgarmaydi; «Butunlay o'chirish» — «Hisobotda qolsin» (12.10).
  A-P05 «Tayyor» buyurtmaning kelishilgan summasi keyin o'zgarsa (✏️ yoki to'lovda qarz qoldig'ini kechirish) YOPILGAN oy daromadi,
        foydasi va usta KPI si jimgina qayta yozilardi; «Tayyor» detal narxi `PUT /api/order-items/{id}` bilan o'zgarardi.
        Egasi QARORI (11.10 «O'zgargan oyga»): farq o'zi bo'lgan oyda alohida qator, yopilgan oy o'zgarmaydi; kamaytirishda
        ortiqcha to'lov — «Mijozga qaytarish».
  A-P07 Dashboard grafigi daromadi — JORIY kelishilgan summa: «Tayyor» dan keyingi o'zgarish grafikda yakunlangan oyni o'zgartirardi
        (oylik hisobot bilan bir oy uchun ikki xil son).
TALAB (bo'limlar): D — hodim ish davrlari (ketish / qaytish / butunlay o'chirish / migratsiya); Y — yangi hodim «Ishga kirgan sana»;
  T — «Tayyor» summasi tuzatishlari; G — Dashboard grafigi = oylik hisobot; Z — zaxira (yangi jadvallar, eski zaxira).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (har ishga yangi baza; parallel tekshiruv faqat PG da ma'noli).
ISHLATISH: python3 tools/test_audit_pul2.py
"""
import os
import sys
import calendar
import tempfile
import threading
from datetime import datetime, timedelta, date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "audit_pul2_test"
_T = tempfile.mkdtemp(prefix="audit_pul2_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'audit_pul2_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, Project, Order, OrderItem, Inventory, Master, Employee, EmployeeAdvance,  # noqa: E402
                    ActivityLog, PayType)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HodimIshDavri = getattr(models, "HodimIshDavri", None)
BuyurtmaTuzatish = getattr(models, "BuyurtmaTuzatish", None)


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


def xav(fn, standart=None):
    """Bitta qadam yiqilsa butun test qulamasin (keyingi tekshiruvlar o'z holatini o'zi yaratadi)."""
    try:
        return fn()
    except Exception as e:                 # noqa: BLE001
        print(f"    (qadam yiqildi: {type(e).__name__}: {str(e)[:300]})")
        return standart


PAROL = "Parol123!"
with TestClient(main.app, base_url="https://testserver") as _c0:      # startup (jadvallar, migratsiyalar, standart admin)
    _c0.get("/login")

db = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(db, "pul2_admin", PAROL, UserRole.ADMIN, "Pul2 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="PD Penoplast", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
db.add(PENO)
db.commit()
PENO_ID = PENO.id
db.close()


def kirish():
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": "pul2_admin", "password": PAROL}, follow_redirects=False)
    assert r.status_code == 302, (r.status_code, r.text[:200])
    return c


C = kirish()
BUGUN = tashkent_date()
Y, M = BUGUN.year, BUGUN.month


def oy_oldin(y, m, n=1):
    k = y * 12 + (m - 1) - n
    return k // 12, k % 12 + 1


def oy_kun(y, m):
    return calendar.monthrange(y, m)[1]


Y0, M0 = oy_oldin(Y, M, 1)
Y2, M2 = oy_oldin(Y, M, 2)
D0, DM = oy_kun(Y0, M0), oy_kun(Y, M)
OYLIK = 3_100_000
N = [0]


def nom(p):
    N[0] += 1
    return f"{p} {N[0]}"


def sana(d):
    return d.isoformat()


def hodim(ism, oylik=OYLIK, ishga=None):
    r = C.post("/api/employees", json={"name": ism, "pay_type": "fixed", "fixed_amount": oylik})
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    s = SessionLocal()
    s.get(Employee, eid).hire_date = ishga or datetime(Y - 1, 1, 1, 4, 0)
    s.commit()
    s.close()
    return eid


def hisobot(y, m):
    return js(C.get("/api/finance/report", params={"year": y, "month": m}))


def oylik_qatori(eid, y, m):
    return next((e for e in (hisobot(y, m).get("hodimlar_breakdown") or []) if e.get("employee_id") == eid), None)


def summa(eid, y, m):
    q = oylik_qatori(eid, y, m)
    return None if q is None else q.get("amount")


def kutilgan(kun, oy_kunlari, oylik=OYLIK):
    return round(oylik * kun / oy_kunlari)


def davrlar(eid):
    if HodimIshDavri is None:
        return []
    s = SessionLocal()
    try:
        return [(d.boshlangan, d.tugagan) for d in s.query(HodimIshDavri).filter(HodimIshDavri.employee_id == eid)
                .order_by(HodimIshDavri.id)]
    finally:
        s.close()


def hodim_holati(eid):
    s = SessionLocal()
    try:
        e = s.get(Employee, eid)
        return {"deleted": bool(e.is_deleted), "active": bool(e.is_active), "phone": e.phone, "pin": e.pin_hash,
                "butunlay": bool(getattr(e, "butunlay_ochirilgan", False))} if e is not None else None
    finally:
        s.close()


def avans_soni(eid):
    s = SessionLocal()
    try:
        return s.query(EmployeeAdvance).filter(EmployeeAdvance.employee_id == eid).count()
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — hodim ishdan ketdi: o'tgan oylarda QOLADI, ketgan oy — ketgan kungacha (admin tanlagan sana)")
E1 = hodim("PD Ketgan")
_k1 = date(Y0, M0, 15)
_r = C.delete(f"/api/employees/{E1}", params={"ketgan_sana": sana(_k1)})
check("D0 o'chirish (ketgan sana bilan) — 200", _r.status_code == 200, _r.text[:200])
_q1 = oylik_qatori(E1, Y0, M0)
check(f"D1 ketgan oyda ({M0:02d}.{Y0}) oylik 15/{D0} kun (ilgari hodim o'tgan oydan ham yo'qolardi)",
      _q1 is not None and _q1.get("amount") == kutilgan(15, D0) and f"15/{D0}" in (_q1.get("detail") or "")
      and f"ishdan ketgan {_k1.strftime('%d.%m.%Y')}" in (_q1.get("detail") or ""), _q1)
check("D2 undan oldingi oy — TO'LIQ oylik (o'tgan oylar o'zgarmaydi)", summa(E1, Y2, M2) == OYLIK, summa(E1, Y2, M2))
check("D3 ketgandan keyingi (joriy) oy — hodim yo'q (avansi ham yo'q)", oylik_qatori(E1, Y, M) is None, oylik_qatori(E1, Y, M))
check("D4 hisobot qatorida `ishda` = False, `ketgan_sana` = tanlangan kun, ish kunlari",
      _q1 is not None and _q1.get("ishda") is False and _q1.get("ketgan_sana") == sana(_k1) and _q1.get("ish_kuni") == 15
      and _q1.get("oy_kuni") == D0, _q1)

E2 = hodim("PD Sana")
_r_kel = C.delete(f"/api/employees/{E2}", params={"ketgan_sana": sana(BUGUN + timedelta(days=1))})
_h2a = hodim_holati(E2)
_r_old = C.delete(f"/api/employees/{E2}", params={"ketgan_sana": sana(date(Y - 2, 6, 1))})
_h2b = hodim_holati(E2)
_r_buz = C.delete(f"/api/employees/{E2}", params={"ketgan_sana": f"{Y}-02-30"})
_h2c = hodim_holati(E2)
check("D5 kelajakdagi / ishga kirgandan oldingi / buzuq sana — 400 sababi bilan, hodim O'CHIRILMAYDI",
      _r_kel.status_code == 400 and "kelajak" in _r_kel.text and _r_old.status_code == 400 and "ishga kirgan" in _r_old.text
      and _r_buz.status_code == 400 and not _h2a["deleted"] and not _h2b["deleted"] and not _h2c["deleted"],
      [_r_kel.status_code, _r_kel.text[:150], _r_old.status_code, _r_old.text[:150], _r_buz.status_code, _h2a, _h2b, _h2c])
_r_t = C.post(f"/api/employees/{E2}/restore")
check("D6 o'chirilmagan hodimni «tiklash» — 409 (ilgari 200 + jurnalda soxta «tiklandi»)",
      _r_t.status_code == 409 and "allaqachon" in _r_t.text, [_r_t.status_code, _r_t.text[:200]])

section("D — tiklash = ishga qaytish (qaytgan sana) yoki «xato o'chirilgan edi» (ish uzilmagan)")
E3 = hodim("PD Qaytdi")
C.delete(f"/api/employees/{E3}", params={"ketgan_sana": sana(date(Y0, M0, 10))})
_r3 = C.post(f"/api/employees/{E3}/restore", params={"qaytgan_sana": sana(date(Y, M, 1))})
check("D7 qaytgan sana (joriy oy 1-kuni) — 200; o'tgan oy 10 kun, joriy oy to'liq, ikki davr",
      _r3.status_code == 200 and summa(E3, Y0, M0) == kutilgan(10, D0) and summa(E3, Y, M) == OYLIK
      and davrlar(E3) == [(None, date(Y0, M0, 10)), (date(Y, M, 1), None)],
      [_r3.text[:150], summa(E3, Y0, M0), summa(E3, Y, M), davrlar(E3)])
E4 = hodim("PD Xato")
C.delete(f"/api/employees/{E4}", params={"ketgan_sana": sana(date(Y0, M0, 10))})
_s4a = summa(E4, Y0, M0)
_r4 = C.post(f"/api/employees/{E4}/restore", params={"qaytgan_sana": sana(date(Y0, M0, 10))})
check("D8 «xato o'chirilgan» (qaytgan = ketgan kun) — ish uzilmagan: o'tgan oy yana to'liq, bitta ochiq davr",
      _s4a == kutilgan(10, D0) and _r4.status_code == 200 and summa(E4, Y0, M0) == OYLIK and davrlar(E4) == [(None, None)],
      [_s4a, _r4.text[:150], summa(E4, Y0, M0), davrlar(E4)])
E5 = hodim("PD Tiklash sana")
_k5 = date(Y0, M0, 20)
C.delete(f"/api/employees/{E5}", params={"ketgan_sana": sana(_k5)})
_r5a = C.post(f"/api/employees/{E5}/restore", params={"qaytgan_sana": sana(date(Y0, M0, 19))})
_r5b = C.post(f"/api/employees/{E5}/restore", params={"qaytgan_sana": sana(BUGUN + timedelta(days=2))})
check("D9 qaytgan sana ketgan kundan oldin / kelajakda — 400, hodim savatda qoladi",
      _r5a.status_code == 400 and "ishdan ketgan" in _r5a.text and _r5b.status_code == 400
      and (hodim_holati(E5) or {}).get("deleted") is True, [_r5a.status_code, _r5a.text[:150], _r5b.status_code, hodim_holati(E5)])
_tr = C.get("/trash").text
check("D10 «O'chirilganlar»: ishdan ketgan sana ko'rinadi, tiklash tugmasida `data-ketgan` (oyna uchun)",
      f'data-ketgan="{sana(_k5)}"' in _tr and f"ishdan ketgan {_k5.strftime('%d.%m.%Y')}" in _tr
      and "hodimTiklash(" in _tr, "")

section("D — faolsizlantirish / qayta faollashtirish (API) — xuddi o'chirish / tiklash kabi")
E6 = hodim("PD Faolsiz")
_r6a = C.put(f"/api/employees/{E6}", json={"is_active": False, "ketgan_sana": sana(date(Y0, M0, 5))})
_s6a = summa(E6, Y0, M0)
_r6b = C.put(f"/api/employees/{E6}", json={"is_active": True, "qaytgan_sana": sana(date(Y0, M0, 25))})
_s6b = summa(E6, Y0, M0)
check("D11 faolsizlantirish 5-kuni — 5 kun; 25-kuni qaytdi — 5 + oy oxirigacha kunlar",
      _r6a.status_code == 200 and _r6b.status_code == 200 and _s6a == kutilgan(5, D0) and _s6b == kutilgan(5 + D0 - 24, D0),
      [_r6a.text[:150], _r6b.text[:150], _s6a, _s6b, davrlar(E6)])

section("D — «❌ Butunlay o'chirish»: savatdan yo'qoladi, o'tgan oylar hisobotida (oylik va avanslar bilan) QOLADI")
E7 = hodim("PD Butunlay")
_av7 = C.post(f"/api/employees/{E7}/advance", params={"amount": "500000", "adv_date": sana(date(Y0, M0, 5)), "notes": "PD avans"})
_sl7 = C.post(f"/api/employees/{E7}/set-login", data={"phone": "+998901690007", "pin": "4826"})
C.delete(f"/api/employees/{E7}", params={"ketgan_sana": sana(date(Y0, M0, 20))})
_q7a = oylik_qatori(E7, Y0, M0)
_p7 = C.delete(f"/api/employees/{E7}/permanent")
_q7b = oylik_qatori(E7, Y0, M0)
check("D12 butunlay o'chirish — 200; o'tgan oy qatori (oylik 20 kun, avans 500 000) O'ZGARMADI (ilgari qator yo'qolardi)",
      _av7.status_code == 200 and _p7.status_code == 200 and _q7a is not None and _q7b is not None
      and _q7b.get("amount") == kutilgan(20, D0) == _q7a.get("amount") and _q7b.get("avans") == 500_000,
      [_av7.status_code, _p7.status_code, _q7a, _q7b])
_h7 = hodim_holati(E7)
check("D13 avans yozuvi qoladi; telefon / PIN o'chdi; belgi `butunlay_ochirilgan`",
      avans_soni(E7) == 1 and _h7 is not None and _h7["phone"] is None and _h7["pin"] is None and _h7["butunlay"],
      [_sl7.status_code, avans_soni(E7), _h7])
_tr7 = C.get("/trash").text
_rt7 = C.post(f"/api/employees/{E7}/restore")
_p7b = C.delete(f"/api/employees/{E7}/permanent")
check("D14 «O'chirilganlar» ro'yxatida YO'Q, tiklash — 409, ikkinchi marta butunlay o'chirish — 404",
      f"row-employee-{E7}\"" not in _tr7 and _rt7.status_code == 409 and _p7b.status_code == 404,
      [f"row-employee-{E7}\"" in _tr7, _rt7.status_code, _rt7.text[:150], _p7b.status_code])

section("D — Qarzdorlar: ishdan ketgan hodimning to'lanmagan oyligi «Kimga qarzmiz» da, belgi bilan")
_ob = js(C.get("/api/obligations/status", params={"year": Y, "month": M}))
_ob1 = [e for e in (_ob.get("employees") or []) if e.get("employee_id") == E1 and e.get("month") == M0]
check("D15 ketgan hodim (ketgan oy oyligi to'lanmagan) — ro'yxatda, `ishda` False",
      len(_ob1) == 1 and _ob1[0].get("qolgan") == kutilgan(15, D0) and _ob1[0].get("ishda") is False, _ob1)
check("D16 Qarzdorlar sahifasida «ishdan ketgan» belgisi", "hodim-ketgan-belgi" in C.get("/debts").text, "")

section("D — migratsiya: zip 169 dan oldin o'chirilgan hodim — davri jurnaldan («deleted» / «restored»)")
_s = SessionLocal()
_ee = Employee(company_id=1, name="PD Eski o'chirilgan", pay_type=PayType.FIXED, fixed_amount=OYLIK, is_active=True,
               is_deleted=True, hire_date=datetime(Y - 1, 1, 1, 4, 0))
_ej = Employee(company_id=1, name="PD Jurnalsiz", pay_type=PayType.FIXED, fixed_amount=OYLIK, is_active=True,
               is_deleted=True, hire_date=datetime(Y - 1, 1, 1, 4, 0))
_ef = Employee(company_id=1, name="PD Faolsiz eski", pay_type=PayType.FIXED, fixed_amount=OYLIK, is_active=False,
               is_deleted=True, hire_date=datetime(Y - 1, 1, 1, 4, 0))
_s.add_all([_ee, _ej, _ef])
_s.commit()
EE, EJ, EF = _ee.id, _ej.id, _ef.id
for _eid in (EE, EF):
    _s.add(ActivityLog(company_id=1, action="deleted", entity_type="employee", entity_id=_eid, entity_label="x",
                       created_at=datetime(Y2, M2, 3, 7, 0)))
    _s.add(ActivityLog(company_id=1, action="restored", entity_type="employee", entity_id=_eid, entity_label="x",
                       created_at=datetime(Y2, M2, 20, 7, 0)))
    _s.add(ActivityLog(company_id=1, action="deleted", entity_type="employee", entity_id=_eid, entity_label="x",
                       created_at=datetime(Y0, M0, 12, 7, 0)))
_s.commit()
_s.close()
_m0 = [summa(EE, Y0, M0), summa(EJ, Y0, M0)]
_fn = getattr(crud, "ish_davrlarini_tola", None)
_s = SessionLocal()
_tiklandi = xav(lambda: _fn(_s, company_id=1)) if _fn else None
xav(_s.commit)
_s.close()
_m1 = [summa(EE, Y0, M0), summa(EE, Y2, M2), summa(EJ, Y0, M0), summa(EF, Y0, M0)]
check("D17 jurnalli eski o'chirilgan hodim o'tgan oylarga QAYTDI: ketgan oy 12 kun, oradagi uzilish (3 → 20) hisoblanmaydi",
      _m0 == [None, None] and _tiklandi == 1 and _m1[0] == kutilgan(12, D0)
      and _m1[1] == kutilgan(3 + oy_kun(Y2, M2) - 19, oy_kun(Y2, M2)),
      [_m0, _tiklandi, _m1, davrlar(EE)])
check("D18 jurnalsiz o'chirilgan va faolsiz eski hodim — ilgarigidek hech bir oyda yo'q (taxmin qilinmaydi)",
      _m1[2] is None and _m1[3] is None and davrlar(EJ) == [] and davrlar(EF) == [], [_m1, davrlar(EJ), davrlar(EF)])
_s = SessionLocal()
_ikkinchi = xav(lambda: _fn(_s, company_id=1)) if _fn else None
xav(_s.commit)
_s.close()
check("D19 migratsiya qayta ishlasa — hech narsa (idempotent)", _ikkinchi == 0 and len(davrlar(EE)) == 2, [_ikkinchi, davrlar(EE)])

section("D — parallel o'chirish (ikki tab / ikki bosish) — bitta davr, 500 yo'q")
E8 = hodim("PD Parallel")
_nat = {}
_to = threading.Barrier(2)


def _ochir(i):
    _kl = kirish()
    try:
        _to.wait(timeout=10)
    except Exception:                      # noqa: BLE001
        pass
    _nat[i] = _kl.delete(f"/api/employees/{E8}", params={"ketgan_sana": sana(date(Y0, M0, 10 + i))}).status_code


_th = [threading.Thread(target=_ochir, args=(i,)) for i in range(2)]
[t.start() for t in _th]
[t.join(60) for t in _th]
_dv8 = davrlar(E8)
if PG_URL:      # haqiqiy poyga — PostgreSQL (hodim qulfi 107); SQLite da qulf yo'q — faqat «500 yo'q»
    check("D20 ikki parallel o'chirish — ikkalasi 200 (ikkinchisi o'zgarishsiz), BITTA yopiq davr",
          sorted(_nat.values()) == [200, 200] and len(_dv8) == 1 and _dv8[0][1] in (date(Y0, M0, 10), date(Y0, M0, 11)),
          [_nat, _dv8])
else:
    check("D20 (SQLite) ikki parallel o'chirish — 500 yo'q, hodim o'chirilgan",
          sorted(_nat.values()) == [200, 200] and (hodim_holati(E8) or {}).get("deleted") is True, [_nat, _dv8])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Y — yangi hodim «Ishga kirgan sana» (egasi QARORI «Kirgan kundan»): kirgan oy oyligi shu kundan")
_ry = C.post("/api/employees", json={"name": "PD Yangi", "pay_type": "fixed", "fixed_amount": OYLIK,
                                     "ishga_kirgan_sana": sana(date(Y0, M0, 11))})
EY = js(_ry).get("id")
_qy = oylik_qatori(EY, Y0, M0) if EY else None
check(f"Y1 {M0:02d}.{Y0} 11-kuni kirgan: shu oy {D0 - 10}/{D0} kun, izohda «ishga kirgan»",
      _ry.status_code == 200 and _qy is not None and _qy.get("amount") == kutilgan(D0 - 10, D0)
      and f"ishga kirgan 11.{M0:02d}.{Y0}" in (_qy.get("detail") or ""), [_ry.status_code, _ry.text[:150], _qy])
check("Y2 keyingi oy to'liq, oldingi oy — yo'q", EY and summa(EY, Y, M) == OYLIK and summa(EY, Y2, M2) is None,
      [EY and summa(EY, Y, M), EY and summa(EY, Y2, M2)])
_le = js(C.get("/api/employees"))
_ly = next((e for e in (_le if isinstance(_le, list) else []) if e.get("id") == EY), {})
check("Y3 hodimlar ro'yxatida `ishga_kirgan_sana` (o'chirish oynasi — undan oldingi sana tanlanmaydi)",
      _ly.get("ishga_kirgan_sana") == sana(date(Y0, M0, 11)), _ly)
_ry2 = C.post("/api/employees", json={"name": "PD Kelajak", "pay_type": "fixed", "fixed_amount": OYLIK,
                                      "ishga_kirgan_sana": sana(BUGUN + timedelta(days=1))})
check("Y4 kelajakdagi ishga kirgan sana — 400 sababi bilan, hodim YARATILMAYDI",
      _ry2.status_code == 400 and "kelajak" in _ry2.text
      and not [e for e in (_le if isinstance(_le, list) else []) + (js(C.get("/api/employees")) or []) if e.get("name") == "PD Kelajak"],
      [_ry2.status_code, _ry2.text[:150]])
_ry3 = C.post("/api/employees", json={"name": "PD Bugun", "pay_type": "fixed", "fixed_amount": OYLIK})
_eb = js(_ry3).get("id")
check("Y5 sanasiz (bugun) kirgan — joriy oy bugundan (1-kunida — to'liq)",
      _eb and summa(_eb, Y, M) == kutilgan(DM - BUGUN.day + 1, DM), [_eb and summa(_eb, Y, M), kutilgan(DM - BUGUN.day + 1, DM)])
_s = SessionLocal()
_eo = Employee(company_id=1, name="PD Oy o'rtasi eski", pay_type=PayType.FIXED, fixed_amount=OYLIK, is_active=True,
               hire_date=datetime(Y0, M0, 20, 7, 0))
_s.add(_eo)
_s.commit()
EO = _eo.id
_s.close()
check("Y6 zip 169 dan oldingi hodim (oy o'rtasida qo'shilgan) — kirgan oyi ilgarigidek TO'LIQ (o'tgan oylar o'zgarmaydi)",
      summa(EO, Y0, M0) == OYLIK and summa(EO, Y2, M2) is None, [summa(EO, Y0, M0), summa(EO, Y2, M2)])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T — «Tayyor» buyurtma summasi keyin o'zgarsa: farq O'ZGARGAN oyga, yakunlangan oy o'zgarmaydi")


def loyiha(mijoz=None):
    s = SessionLocal()
    p = Project(company_id=1, client_name=mijoz or nom("PD Mijoz"), project_name=nom("PD loyiha"), total_budget=0, total_paid=0)
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    return pid


def buyurtma(pid=None, master_id=None, narx=100_000):
    r = C.post("/api/orders", params={"confirm_shortage": "true"}, json={
        "project_id": pid or loyiha(), "order_type": "product", "loy_kg": 0, "master_id": master_id, "is_draft": False,
        "items": [{"name": nom("D"), "category": "profil", "width": 20, "thickness": 10, "length": 10,
                   "quantity": 10, "unit_price": narx, "is_coated": False, "penoplast_id": PENO_ID}]})
    assert r.status_code == 200, (r.status_code, r.text[:300])
    oid = r.json()["id"]
    s = SessionLocal()
    iid = s.query(OrderItem.id).filter(OrderItem.order_id == oid).first()[0]
    s.close()
    return oid, iid


def _kechirish173(oid, summa):
    """kech144 (zip 173, egasi QARORI 13.10 «Faqat ko'rsatilgani»): oynada ko'rsatiladigan kechiriladigan summa — joriy qarz −
    to'lov (butun tiyinlarda; 0,5 so'mdan kichigi — 0), `debts.html` `payKechiriladi` / `orders.html` `savePayment` bilan AYNAN."""
    d = C.get(f"/api/orders/{oid}").json()
    q = (round(float(d.get("debt_amount") or 0) * 100) - round(float(summa) * 100)) / 100
    return q if q > 0.5 else 0


def tolov(oid, summa_, write_off=False):
    r = C.post("/api/payments", params={"write_off_remainder": "true", "kechirish": str(_kechirish173(oid, summa_))} if write_off else None,
               json={"order_id": oid, "amount": summa_, "payment_type": "partial", "payment_method": "naqd", "notes": nom("tolov")})
    return r


def tayyor(master_id, completed_at, tolanadi=1_000_000):
    oid, iid = buyurtma(master_id=master_id)
    if tolanadi:
        tolov(oid, tolanadi)
    C.post("/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": iid, "quantity": 10}], "notes": nom("yuk"),
                                    "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    _rd = C.post(f"/api/orders/{oid}/ready")
    s = SessionLocal()
    s.get(Order, oid).completed_at = completed_at
    s.commit()
    s.close()
    return oid, iid, _rd.status_code


def usta_kpi(y, m, ism):
    return next((b["kpi_amount"] for b in (hisobot(y, m).get("usta_kpi_breakdown") or []) if b.get("master_name") == ism), None)


_s = SessionLocal()
_TU = Master(company_id=1, name="PD T Usta", phone="+998901690101", kpi_percent=10.0, is_active=True)
_s.add(_TU)
_s.commit()
TU = _TU.id
_s.close()
_t_oid, _t_iid, _t_st = tayyor(TU, datetime(Y0, M0, 15, 7, 0))
_h0_a, _hM_a = hisobot(Y0, M0), hisobot(Y, M)
_k0_a = usta_kpi(Y0, M0, "PD T Usta")
_rt = C.put(f"/api/orders/{_t_oid}/agreed-amount", json={"agreed_amount": 900_000})
_h0_b, _hM_b = hisobot(Y0, M0), hisobot(Y, M)
check("T0 «Tayyor» (o'tgan oy) buyurtmasi, ✏️ 1 000 000 → 900 000 — 200", _t_st == 200 and _rt.status_code == 200,
      [_t_st, _rt.status_code, _rt.text[:200]])
check("T1 yakunlangan (o'tgan) oy daromadi va sof foydasi O'ZGARMADI (ilgari −100 000)",
      _h0_a.get("daromad") == _h0_b.get("daromad") and _h0_a.get("sof_foyda") == _h0_b.get("sof_foyda"),
      [_h0_a.get("daromad"), _h0_b.get("daromad"), _h0_a.get("sof_foyda"), _h0_b.get("sof_foyda")])
check("T2 joriy oy: daromad −100 000, alohida qator `tuzatish_daromad` −100 000 (1 ta), «Qaytarishlar» ga aralashmadi",
      (_hM_b.get("daromad") or 0) - (_hM_a.get("daromad") or 0) == -100_000 and _hM_b.get("tuzatish_daromad") == -100_000
      and _hM_b.get("tuzatish_soni") == 1 and (_hM_b.get("qaytarish_soni") or 0) == (_hM_a.get("qaytarish_soni") or 0),
      [_hM_a.get("daromad"), _hM_b.get("daromad"), _hM_b.get("tuzatish_daromad"), _hM_b.get("tuzatish_soni"),
       _hM_b.get("qaytarish_soni")])
_jt = js(_rt)
check("T3 javobda — qaysi oyga yozilgani va «Mijozga qaytarish» (to'langan 1 000 000 > 900 000)",
      (_jt.get("tuzatish") or {}).get("farq") == -100_000 and (_jt.get("tuzatish") or {}).get("oy") == M
      and round(_jt.get("ortiqcha_tolov") or 0) == 100_000, _jt)
_k0_b, _kM_b = usta_kpi(Y0, M0, "PD T Usta"), usta_kpi(Y, M, "PD T Usta")
check("T4 usta KPI: yakunlangan oy o'zgarmadi, joriy oyda −10 000 (10 % × −100 000)",
      _k0_a is not None and _k0_a == _k0_b and _kM_b == -10_000, [_k0_a, _k0_b, _kM_b])
_s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    _det = xav(lambda: crud.get_master_kpi_detail(_s, TU, Y, company_id=1), [])
_s.close()
check("T5 KPI tafsiloti (joriy yil): «✏️ … (narx tuzatildi)» qatori, foyda −100 000",
      any("✏️" in (r.get("order_number") or "") and "narx tuzatildi" in (r.get("order_number") or "")
          and r.get("profit") == -100_000 for r in (_det or [])), _det)
_tz = []
if BuyurtmaTuzatish is not None:
    _s = SessionLocal()
    _tz = [(t.tur, float(t.eski_kelishilgan), float(t.yangi_kelishilgan), float(t.farq), t.company_id)
           for t in _s.query(BuyurtmaTuzatish).filter(BuyurtmaTuzatish.order_id == _t_oid)]
    _s.close()
check("T6 hodisa yozuvi: «kelishilgan», 1 000 000 → 900 000, farq −100 000, korxona 1",
      _tz == [("kelishilgan", 1_000_000.0, 900_000.0, -100_000.0, 1)], _tz)
_rt2 = C.put(f"/api/orders/{_t_oid}/agreed-amount", json={"agreed_amount": 1_150_000})
_hM_c = hisobot(Y, M)
check("T7 oshirish (900 000 → 1 150 000): joriy oy +250 000 (jami tuzatish +150 000), o'tgan oy hamon o'zgarmagan",
      _rt2.status_code == 200 and _hM_c.get("tuzatish_daromad") == 150_000 and _hM_c.get("tuzatish_soni") == 2
      and hisobot(Y0, M0).get("daromad") == _h0_a.get("daromad"), [_rt2.text[:150], _hM_c.get("tuzatish_daromad")])

_k_oid, _, _k_st = tayyor(TU, datetime(Y0, M0, 16, 7, 0), tolanadi=400_000)
_h0_k, _hM_k = hisobot(Y0, M0), hisobot(Y, M)
_rk = tolov(_k_oid, 500_000, write_off=True)
_h0_k2, _hM_k2 = hisobot(Y0, M0), hisobot(Y, M)
check("T8 to'lovda qarz qoldig'ini kechirish (100 000) — kechirilgan oyda −100 000, yakunlangan oy o'zgarmadi",
      _k_st == 200 and _rk.status_code == 200 and _h0_k.get("daromad") == _h0_k2.get("daromad")
      and (_hM_k2.get("tuzatish_daromad") or 0) - (_hM_k.get("tuzatish_daromad") or 0) == -100_000,
      [_k_st, _rk.status_code, _rk.text[:150], _h0_k.get("daromad"), _h0_k2.get("daromad"), _hM_k.get("tuzatish_daromad"),
       _hM_k2.get("tuzatish_daromad")])

_p_oid, _ = buyurtma(master_id=TU)
_rp = C.put(f"/api/orders/{_p_oid}/agreed-amount", json={"agreed_amount": 800_000})
_tzp = 0
if BuyurtmaTuzatish is not None:
    _s = SessionLocal()
    _tzp = _s.query(BuyurtmaTuzatish).filter(BuyurtmaTuzatish.order_id == _p_oid).count()
    _s.close()
check("T9 yakunlanmagan buyurtmada ✏️ — hodisa YOZILMAYDI (daromad hali hisobotda emas)",
      _rp.status_code == 200 and _tzp == 0 and js(_rp).get("tuzatish") is None, [_rp.text[:150], _tzp])
_s = SessionLocal()
_ti_narx0 = float(_s.get(OrderItem, _t_iid).unit_price)
_s.close()
_ri = C.put(f"/api/order-items/{_t_iid}", json={"unit_price": 50_000})
_rd = C.delete(f"/api/order-items/{_t_iid}")
_s = SessionLocal()
_ti_narx1 = float(_s.get(OrderItem, _t_iid).unit_price) if _s.get(OrderItem, _t_iid) is not None else None
_s.close()
check("T10 «Tayyor» buyurtma detali: narx tahriri va o'chirish — 400 (ilgari yopilgan oy daromadi hodisasiz o'zgarardi)",
      _ri.status_code == 400 and "Tayyor" in _ri.text and _rd.status_code == 400 and _ti_narx0 == _ti_narx1,
      [_ri.status_code, _ri.text[:150], _rd.status_code, _rd.text[:150], _ti_narx0, _ti_narx1])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G — Dashboard grafigi daromadi = oylik hisobot (A-P07)")
_g_oid, _g_iid, _ = tayyor(TU, datetime(Y0, M0, 17, 7, 0))
_grt = C.post("/api/returns", json={"order_id": _g_oid, "order_item_id": _g_iid, "item_name": "x", "quantity": 3, "unit": "m",
                                    "reason": "Mijoz iltimosi", "refund_amount": 0, "to_stock": False})
_grf = C.post(f"/api/returns/{js(_grt).get('id')}/refund")
check("G0 o'tgan oyda «Tayyor» buyurtmaga joriy oyda qaytarish va «Pul qaytdi»", _grt.status_code == 200 and _grf.status_code == 200,
      [_grt.text[:200], _grf.text[:200]])
_ch = js(C.get("/api/dashboard/charts"))
_md = _ch.get("months") or []
_g = [round(float(_md[-2]["revenue"])) if len(_md) >= 2 else None, round(float(_md[-1]["revenue"])) if _md else None]
_hh = [hisobot(Y0, M0).get("daromad"), hisobot(Y, M).get("daromad")]
check("G1 o'tgan va joriy oy: grafik daromadi = hisobot daromadi (ilgari grafik «Pul qaytdi» va tuzatishni yakunlangan oyda ko'rsatardi)",
      _g == _hh and None not in _g, [_g, _hh])
_yg = [sum((_md[-2].get("yonalishlar") or {}).values()) if len(_md) >= 2 else None,
       sum((_md[-1].get("yonalishlar") or {}).values()) if _md else None]
check("G2 grafikning yo'nalishlar yig'indisi = o'sha oy daromadi (±2 so'm yaxlitlash)",
      None not in _yg and all(abs(a - b) <= 2 for a, b in zip(_yg, _g)), [_yg, _g])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z — zaxira: yangi jadvallar (ish davrlari, tuzatishlar) saqlanadi; eski zaxira (davrlarsiz) — jurnaldan")
_s = SessionLocal()
_bk = xav(lambda: crud.export_full_backup(_s, company_id=1), {}) or {}
_s.close()
_tb = _bk.get("tables") or {}
check("Z1 zaxirada `hodim_ish_davrlari` va `buyurtma_tuzatishlari` qatorlari bor",
      len(_tb.get("hodim_ish_davrlari") or []) >= 8 and len(_tb.get("buyurtma_tuzatishlari") or []) >= 3,
      [len(_tb.get("hodim_ish_davrlari") or []), len(_tb.get("buyurtma_tuzatishlari") or [])])
_oldin = [hisobot(Y2, M2).get("hodimlar_moslashuvchan_xarajat"), hisobot(Y0, M0).get("hodimlar_moslashuvchan_xarajat"),
          hisobot(Y0, M0).get("daromad"), hisobot(Y, M).get("daromad"), hisobot(Y, M).get("tuzatish_daromad")]
_s = SessionLocal()
_im = xav(lambda: crud.import_full_backup(_s, _bk, company_id=1, replace=True), {}) or {}
_s.close()
C = kirish()
_keyin = [hisobot(Y2, M2).get("hodimlar_moslashuvchan_xarajat"), hisobot(Y0, M0).get("hodimlar_moslashuvchan_xarajat"),
          hisobot(Y0, M0).get("daromad"), hisobot(Y, M).get("daromad"), hisobot(Y, M).get("tuzatish_daromad")]
check("Z2 zaxiradan tiklash: hodimlar xarajati (2 oy), daromad va tuzatishlar AYNAN",
      _im.get("success") is True and _oldin == _keyin, [_im.get("success"), (_im.get("message") or "")[:300], _oldin, _keyin])
_eski = {"company_id": _bk.get("company_id"), "tables": {k: v for k, v in _tb.items()
                                                         if k not in ("hodim_ish_davrlari", "buyurtma_tuzatishlari")}}
_s = SessionLocal()
_im2 = xav(lambda: crud.import_full_backup(_s, _eski, company_id=1, replace=True), {}) or {}
_s.close()
C = kirish()
check("Z3 eski zaxira (ish davrlarisiz): o'chirilgan hodim o'tgan oyda QOLADI (davri jurnaldan — o'chirilgan kungacha)",
      _im2.get("success") is True and summa(E1, Y0, M0) == OYLIK and summa(EE, Y0, M0) == kutilgan(12, D0),
      [_im2.get("success"), (_im2.get("message") or "")[:200], summa(E1, Y0, M0), summa(EE, Y0, M0)])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
