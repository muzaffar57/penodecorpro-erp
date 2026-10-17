#!/usr/bin/env python3
"""
test_audit_pul.py — kech140 (zip 168): AUDIT 1-to'lqini — PUL topilmalari (1-qism).

NIMA UCHUN KERAK (har biri O'LCHANGAN — asl kod zip 167, `work/audit/tasdiq/pul/probe_p0N.py`, loglar `p0N.log`):
  A-P09 avans / «oylikni yopish»: bir xil so'rov ikki marta (ikki bosish, ikki tab, parallel) — IKKI yozuv; oylikdan ko'p summa
        (oylik 3 000 000 — avans 10 000 000) jimgina yozilardi, «qolgan» manfiy, hodim qarzi hech qayerda ko'rinmasdi.
        Egasi QARORLARI (11.10): «Ogohlantirib so'rasin» (409 → tasdiq); «Keyingi oydan ushlansin» (ortig'i keyingi oy oyligidan);
        ungacha «Hodim qarzdor» ko'rinadi.
  A-P08 to'lovni o'chirish, kelishilgan summa tahriri, savatdan tiklash — buyurtma pul qulfisiz (101); savatda bo'lmagan buyurtmani
        «tiklash» 200 qaytarib jurnalga soxta «tiklandi» yozardi (ikki parallel tiklash xomashyoni ikki marta yechardi).
  A-P03 bot «Bonuslarim» — sovg'a davri ichidagi buyurtmalarni HAMMA ustadan chiqarardi (qatnashmagan usta: bot 95 000, KPI
        sahifasi 190 000). Egasi QARORI (11.10 «Bot to'g'ri»): ishtirokchining davr sotuvi keshbekka KIRMAYDI — KPI sahifasi,
        KPI tafsiloti va oylik hisobot ham; davr yopilganda olinmagan qismi keshbekka o'tadi (o'tkazilgan oyga).
  A-P04 oylik usta KPI har oy 0 dan pastga tushmasdi (keyingi oydagi qaytarish KPI ni kamaytirmasdi): oylar yig'indisi 255 000,
        KPI sahifasi (yil) 225 000.
  A-P02 (usta qismi) faolsizlantirilgan usta O'TGAN oylar hisobotidan yo'qolardi (KPI 95 000 → 0, sof foyda oshardi).
  A-P06 bitta loyiha qarzi uch xil: Buyurtmalar sarlavhasi 830 000 («Hammasi» — 1 030 000), Loyihalar va Qarzdorlar 750 000.
  A-P01 savatdan tiklash kelishilgan summani o'chirish paytidagi qiymatga qaytarardi — savatdagi pul o'zgarishlari yo'qolardi
        (qarz 800 000, nazorat 900 000; soxta «Ustama»).
TALAB (bo'limlar): V — avans; Q — qulf / tiklash; S — sovg'a davri; K — KPI oylar = yil, faolsiz usta; L — loyiha qarzi;
  T — savatdan tiklash.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (har ishga yangi baza; parallel tekshiruvlar faqat PG da ma'noli).
ISHLATISH: python3 tools/test_audit_pul.py
"""
import os
import re
import sys
import inspect
import tempfile
import threading
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "audit_pul_test"
_T = tempfile.mkdtemp(prefix="audit_pul_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'audit_pul_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, Project, Order, OrderItem, Inventory, Master, Employee, EmployeeAdvance,  # noqa: E402
                    ActivityLog, ReturnItem, Payment, AdvanceRequest, AdvanceRequestStatus)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


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
    auth.create_user(db, "pul_admin", PAROL, UserRole.ADMIN, "Pul Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="AP Penoplast", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
db.add(PENO)
db.commit()
PENO_ID = PENO.id
db.close()


def kirish():
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": "pul_admin", "password": PAROL}, follow_redirects=False)
    assert r.status_code == 302, (r.status_code, r.text[:200])
    return c


C = kirish()
HOZIR_T = tashkent_date()
Y, M = HOZIR_T.year, HOZIR_T.month


def oy_oldin(y, m, n=1):
    k = y * 12 + (m - 1) - n
    return k // 12, k % 12 + 1


N = [0]


def nom(p):
    N[0] += 1
    return f"{p} {N[0]}"


def loyiha(mijoz=None):
    s = SessionLocal()
    p = Project(company_id=1, client_name=mijoz or nom("AP Mijoz"), project_name=nom("AP loyiha"), total_budget=0,
                total_paid=0)
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    return pid


def buyurtma(pid=None, master_id=None, narx=100_000, draft=False):
    r = C.post("/api/orders", params={"confirm_shortage": "true"}, json={
        "project_id": pid or loyiha(), "order_type": "product", "loy_kg": 0, "master_id": master_id, "is_draft": draft,
        "items": [{"name": nom("D"), "category": "profil", "width": 20, "thickness": 10, "length": 10,
                   "quantity": 10, "unit_price": narx, "is_coated": False, "penoplast_id": PENO_ID}]})
    assert r.status_code == 200, (r.status_code, r.text[:300])
    oid = r.json()["id"]
    s = SessionLocal()
    iid = s.query(OrderItem.id).filter(OrderItem.order_id == oid).first()[0]
    s.close()
    return oid, iid


def tolov(oid, summa, write_off=False):
    r = C.post("/api/payments", params={"write_off_remainder": "true"} if write_off else None,
               json={"order_id": oid, "amount": summa, "payment_type": "partial", "payment_method": "naqd",
                     "notes": nom("tolov")})
    return r.status_code


def yuk(oid, iid, m):
    return C.post("/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": iid, "quantity": m}],
                                           "notes": nom("yuk"), "transport_cost": 0, "transport_payer": "none",
                                           "payment_method": "naqd"}).status_code


TAYYOR_JAVOB = {}


def tayyor(master_id, pid=None, completed_at=None):
    oid, iid = buyurtma(pid=pid, master_id=master_id)
    tolov(oid, 1_000_000)
    yuk(oid, iid, 10)
    _rd = C.post(f"/api/orders/{oid}/ready")
    st = _rd.status_code
    TAYYOR_JAVOB[oid] = js(_rd)
    if completed_at is not None:
        s = SessionLocal()
        s.get(Order, oid).completed_at = completed_at
        s.commit()
        s.close()
    return oid, iid, st


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        return {"agreed": float(o.agreed_amount) if o.agreed_amount is not None else None, "debt": float(o.debt_amount or 0),
                "deleted": bool(o.is_deleted), "status": o.status.value, "total": float(o.total_amount or 0),
                "kechirilgan": float(o.kechirilgan_qarz or 0), "paid": float(o.paid_amount or 0)}
    finally:
        s.close()


def hodim(ism, oylik=3_000_000, ishga=None):
    r = C.post("/api/employees", json={"name": ism, "pay_type": "fixed", "fixed_amount": oylik})
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    s = SessionLocal()
    s.get(Employee, eid).hire_date = ishga or datetime(Y - 1, 1, 1, 4, 0)
    s.commit()
    s.close()
    return eid


def avanslar(eid):
    s = SessionLocal()
    try:
        return [(a.id, float(a.amount), float(getattr(a, "keyingi_oyga", None) or 0), a.notes)
                for a in s.query(EmployeeAdvance).filter(EmployeeAdvance.employee_id == eid).order_by(EmployeeAdvance.id)]
    finally:
        s.close()


def oylik_qatori(eid, y, m):
    d = js(C.get("/api/finance/report", params={"year": y, "month": m}))
    return next((e for e in (d.get("hodimlar_breakdown") or []) if e.get("employee_id") == eid), None)


def kpi_sahifa(y, inactive=True):
    return js(C.get("/api/masters/kpi-report", params={"year": y, "include_inactive": "true" if inactive else "false"}))


def usta_oylik_kpi(y, ism):
    jami = 0.0
    for mm in range(1, 13):
        d = js(C.get("/api/finance/report", params={"year": y, "month": mm}))
        jami += sum(float(b["kpi_amount"]) for b in (d.get("usta_kpi_breakdown") or []) if b.get("master_name") == ism)
    return jami


def bot_bonus(mid, y):
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return crud.get_master_yearly_cashback(s, mid, y, company_id=1)
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("V — avans / «oylikni yopish»: takror, oylikdan ko'p (409 → tasdiq), keyingi oyga o'tish, «Hodim qarzdor»")
E1 = hodim("AP Hodim 1")
_url = f"/api/employees/{E1}/advance?amount=500000&notes=avans&adv_date={HOZIR_T.isoformat()}"
r1, r2 = C.post(_url), C.post(_url)
check("V1 bir xil avans ikki marta (8 s ichida) — bitta yozuv, ikkinchi javob `duplicate: true` va o'sha id",
      r1.status_code == 200 and r2.status_code == 200 and js(r2).get("duplicate") is True
      and js(r1).get("id") == js(r2).get("id") and len(avanslar(E1)) == 1, [r1.text[:200], r2.text[:200], avanslar(E1)])
_n0 = len(avanslar(E1))
_r3 = C.post(f"/api/employees/{E1}/advance?amount=500000&notes=avans%202&adv_date={HOZIR_T.isoformat()}")
check("V2 boshqa izohli avans — yangi yozuv (himoya faqat AYNAN takrorga)", _r3.status_code == 200 and len(avanslar(E1)) == _n0 + 1,
      [_r3.text[:200], avanslar(E1)])
_r4 = C.post(f"/api/employees/{E1}/advance?amount=10000000&notes=katta&adv_date={HOZIR_T.isoformat()}")
_d4 = (js(_r4).get("detail") or {}) if _r4.status_code == 409 else {}
check("V3 oylikdan ko'p avans (qolgan 2 000 000, avans 10 000 000) — 409 `avans_oylikdan_ortiq`, yozuv YO'Q",
      _r4.status_code == 409 and _d4.get("type") == "avans_oylikdan_ortiq" and round(_d4.get("excess", 0)) == 8_000_000
      and len(avanslar(E1)) == _n0 + 1, [_r4.status_code, _r4.text[:300], avanslar(E1)])
check("V3b xabar — qancha ko'p va keyingi oy oyligidan ushlanishi",
      ("8\u00a0000\u00a0000" if hasattr(crud, "xabar_son") else "8 000 000") in str(_d4.get("message"))   # kech151 (zip 192, MOSLANDI)
      and "keyingi oy" in str(_d4.get("message")), _d4.get("message"))
_r5 = C.post(f"/api/employees/{E1}/advance?amount=10000000&notes=katta&adv_date={HOZIR_T.isoformat()}&confirm_excess=true")
_av5 = [a for a in avanslar(E1) if a[3] == "katta"]
check("V4 tasdiq bilan — yozildi, `keyingi_oyga` = 8 000 000 (ortiqchasi keyingi oy hisobiga)",
      _r5.status_code == 200 and len(_av5) == 1 and round(_av5[0][2]) == 8_000_000 and js(_r5).get("keyingi_oyga") == 8_000_000,
      [_r5.text[:200], _av5])
_q = oylik_qatori(E1, Y, M) or {}
check("V5 shu oy: hisoblangan 3 000 000, shu oy hisobidagi avans 3 000 000, qolgan 0 (ortig'i shu oyni manfiy qilmaydi)",
      _q.get("amount") == 3_000_000 and _q.get("avans") == 3_000_000 and _q.get("qolgan") == 0
      and _q.get("keyingi_oyga") == 8_000_000 and _q.get("avans_jami") == 11_000_000, _q)
_ky, _km = (Y + 1, 1) if M == 12 else (Y, M + 1)
_qk = oylik_qatori(E1, _ky, _km) or {}
check("V6 keyingi oy: o'tgan oydan 8 000 000 ushlanadi — qolgan 3 000 000 − 8 000 000 = −5 000 000 (hodim qarzdor)",
      _qk.get("oldingi_oydan") == 8_000_000 and _qk.get("avans") == 8_000_000 and _qk.get("qolgan") == -5_000_000, _qk)

# O'tgan oyda oylikdan ko'p (tasdiq bilan) — joriy oyda ushlanadi va yetmasa «Hodim qarzdor»
E2 = hodim("AP Hodim 2")
_py, _pm = oy_oldin(Y, M)
_url2 = f"/api/employees/{E2}/advance?amount=8000000&notes=otgan&adv_date={_py:04d}-{_pm:02d}-10"
_r6 = C.post(_url2)
_r7 = C.post(_url2 + "&confirm_excess=true")
check("V7 o'tgan oyda 8 000 000 (oylik 3 000 000): avval 409, tasdiq bilan — `keyingi_oyga` 5 000 000",
      _r6.status_code == 409 and _r7.status_code == 200 and [round(a[2]) for a in avanslar(E2)] == [5_000_000],
      [_r6.status_code, _r7.text[:200], avanslar(E2)])
_qp, _qj = oylik_qatori(E2, _py, _pm) or {}, oylik_qatori(E2, Y, M) or {}
check("V8 o'tgan oy qolgan 0; joriy oy: o'tgan oydan 5 000 000, qolgan −2 000 000",
      _qp.get("qolgan") == 0 and _qj.get("oldingi_oydan") == 5_000_000 and _qj.get("qolgan") == -2_000_000, [_qp, _qj])
_ob = js(C.get("/api/obligations/status", params={"year": Y, "month": M}))
_ov = [e for e in (_ob.get("employees_overdrawn") or []) if e.get("employee_id") == E2]
check("V9 Qarzdorlar (majburiyatlar): «Hodimlar bizga qarzdor» — joriy oy, 2 000 000; joriy oy «Hodimlarga qarzimiz» da YO'Q",
      len(_ov) == 1 and round(_ov[0]["qarz"]) == 2_000_000 and (_ov[0]["year"], _ov[0]["month"]) == (Y, M)
      and not [e for e in (_ob.get("employees") or []) if e.get("employee_id") == E2 and (e["year"], e["month"]) in ((Y, M), (_py, _pm))],
      [_ov, _ob.get("employees")])
_ds = js(C.get("/api/finance/debt-summary", params={"year": Y, "month": M}))
check("V10 Moliya qarz xulosasi: `employee_overdrawn` ≥ 2 000 000 (sof pozitsiya formulasi o'zgarmagan)",
      _ds.get("employee_overdrawn", 0) >= 2_000_000 and "net_position" in _ds, _ds)
_hd = C.get("/debts").text
check("V11 /debts sahifasida «Hodimlar bizga qarzdor» bloki va hodim nomi", 'id="hodim-qarzdor"' in _hd and "AP Hodim 2" in
      _hd[_hd.find('id="hodim-qarzdor"'):_hd.find('id="hodim-qarzdor"') + 6000], "")
_s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    _px = services.hodim_oylik_xulosa(_s, E2, 1)
_s.close()
_jo = next((o for o in _px.get("oylar", []) if o.get("joriy")), {})
_ot = next((o for o in _px.get("oylar", []) if not o.get("joriy")), {})
check("V12 hodim paneli «Oyligim»: joriy oy — o'tgan oydan 5 000 000, qolgan −2 000 000; o'tgan oy — keyingi oyga 5 000 000, qolgan 0",
      _jo.get("oldingi_oydan") == 5_000_000 and _jo.get("qolgan") == -2_000_000 and _ot.get("keyingi_oyga") == 5_000_000
      and _ot.get("qolgan") == 0,
      [_jo, _ot])

# «Oylikni yopish» — takror va ortiqcha
E3 = hodim("AP Hodim 3")
_uc = f"/api/obligations/employee/{E3}/close?year={Y}&month={M}&amount=3000000"
_c1, _c2 = C.post(_uc), C.post(_uc)
check("V13 «oylikni yopish» ikki marta — bitta yozuv, ikkinchisi `duplicate: true`",
      _c1.status_code == 200 and _c2.status_code == 200 and js(_c2).get("duplicate") is True and len(avanslar(E3)) == 1,
      [_c1.text[:150], _c2.text[:150], avanslar(E3)])
_c3 = C.post(f"/api/obligations/employee/{E3}/close?year={Y}&month={M}&amount=50000000")
check("V14 «oylikni yopish» qolgandan ko'p (50 000 000) — 409, yozuv yo'q",
      _c3.status_code == 409 and (js(_c3).get("detail") or {}).get("type") == "avans_oylikdan_ortiq" and len(avanslar(E3)) == 1,
      [_c3.status_code, _c3.text[:200]])

# Hodim so'rovini admin tasdiqlashi
E4 = hodim("AP Hodim 4")
_s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    _req = crud.create_advance_request(_s, E4, 4_000_000, datetime(Y, M, HOZIR_T.day), "so'rov", company_id=1)
_RID = _req.id
_s.close()
_a1 = C.post(f"/api/admin/advance-requests/{_RID}/confirm")
_s = SessionLocal()
_rq = _s.get(AdvanceRequest, _RID).status
_s.close()
check("V15 hodim so'rovi oylikdan ko'p (4 000 000 / 3 000 000) — tasdiqlashda 409, so'rov KUTILMOQDA, avans yo'q",
      _a1.status_code == 409 and (js(_a1).get("detail") or {}).get("type") == "avans_oylikdan_ortiq"
      and _rq == AdvanceRequestStatus.PENDING and not avanslar(E4), [_a1.status_code, _a1.text[:200], _rq])
_a2 = C.post(f"/api/admin/advance-requests/{_RID}/confirm?confirm_excess=true")
check("V16 «Ha» bilan — avans yozildi, `keyingi_oyga` 1 000 000",
      _a2.status_code == 200 and [round(a[2]) for a in avanslar(E4)] == [1_000_000], [_a2.text[:200], avanslar(E4)])

# Parallel (PG da haqiqiy poyga): ikki bir xil avans bir vaqtda
E5 = hodim("AP Hodim 5")
_url5 = f"/api/employees/{E5}/advance?amount=100000&notes=parallel&adv_date={HOZIR_T.isoformat()}"
_kl = [kirish(), kirish()]
_nat = {}
_to = threading.Barrier(2)


def _yubor(i):
    try:
        _to.wait(timeout=10)
    except Exception:                      # noqa: BLE001
        pass
    _nat[i] = _kl[i].post(_url5).status_code


_th = [threading.Thread(target=_yubor, args=(i,)) for i in range(2)]
[t.start() for t in _th]
[t.join(60) for t in _th]
if PG_URL:      # SQLite da qulf yo'q (bitta yozuvchi) — haqiqiy poyga faqat PostgreSQL da o'lchanadi
    check("V17 bir xil avans PARALLEL ikki so'rov — ikkalasi 200, bazada BITTA yozuv (hodim qulfi 107)",
          sorted(_nat.values()) == [200, 200] and len(avanslar(E5)) == 1, [_nat, avanslar(E5)])
else:
    check("V17 (SQLite) parallel ikki so'rov — 500 yo'q", all(v == 200 for v in _nat.values()) and len(_nat) == 2, _nat)
check("V18 `EmployeeAdvance` da `created_at` va `keyingi_oyga` ustunlari (takror imzosi / keyingi oy qismi)",
      hasattr(EmployeeAdvance, "created_at") and hasattr(EmployeeAdvance, "keyingi_oyga"), "")
# Oyligi 0 (foizli, sotuv yo'q) hodim avans oldi — keyingi oyda ushlanadi; oylik 0 bo'lsa ham ro'yxatda, qarzi ko'rinadi
_r6 = C.post("/api/employees", json={"name": "AP Hodim 6", "pay_type": "percent_sales", "percent_value": 0.0001})
E6 = js(_r6).get("id")
if E6:
    _s = SessionLocal()
    _s.get(Employee, E6).hire_date = datetime(Y - 1, 1, 1, 4, 0)
    _s.commit()
    _s.close()
_r61 = C.post(f"/api/employees/{E6}/advance?amount=100000&notes=foizli&adv_date={HOZIR_T.isoformat()}&confirm_excess=true")
_q6 = oylik_qatori(E6, _ky, _km) or {}
check("V19 oyligi ~0 hodim: avans 100 000 (tasdiq bilan) — keyingi oyda ro'yxatda, qolgan ≈ −100 000 (hodim qarzdor)",
      _r61.status_code == 200 and _q6.get("oldingi_oydan") == 100_000 and (_q6.get("qolgan") or 0) <= -99_000, [_r6.text[:150], _r61.text[:150], _q6])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q — buyurtma pul qulfi (101) va savatdan tiklash")
check("Q1 `delete_payment`, `update_order_agreed_amount`, `restore_order` — buyurtma pul qulfi (101) ostida",
      all("_pul_qulfi(db, 101" in inspect.getsource(f) for f in (crud.delete_payment, crud.update_order_agreed_amount,
                                                                     crud.restore_order)), "")
_oq, _iq = buyurtma()
_s = SessionLocal()
_log0 = _s.query(ActivityLog).filter(ActivityLog.entity_type == "order", ActivityLog.entity_id == _oq,
                                     ActivityLog.action == "restored").count()
_s.close()
_rr = C.post(f"/api/orders/{_oq}/restore")
_s = SessionLocal()
_log1 = _s.query(ActivityLog).filter(ActivityLog.entity_type == "order", ActivityLog.entity_id == _oq,
                                     ActivityLog.action == "restored").count()
_s.close()
check("Q2 savatda bo'lmagan buyurtmani «tiklash» — 409 (sababi bilan), jurnalda soxta «tiklandi» YO'Q",
      _rr.status_code == 409 and "savatda emas" in _rr.text and _log1 == _log0, [_rr.status_code, _rr.text[:200], _log0, _log1])
tolov(_oq, 200_000)
yuk(_oq, _iq, 4)        # qisman topshirilgan — o'chirish yumshoq (savatga), topshirilgani bilan yakunlanadi
C.delete(f"/api/orders/{_oq}")
_rr1 = C.post(f"/api/orders/{_oq}/restore")
_rr2 = C.post(f"/api/orders/{_oq}/restore")
check("Q3 savatdagi buyurtma: 1-tiklash 200, 2-tiklash 409 (qayta yechish yo'q)", _rr1.status_code == 200 and _rr2.status_code == 409,
      [_rr1.status_code, _rr2.status_code, _rr2.text[:200]])
C.delete(f"/api/orders/{_oq}")
_ag0 = xav(lambda: holat(_oq), {})
_ag = C.put(f"/api/orders/{_oq}/agreed-amount", json={"agreed_amount": 300_000})
_ag1 = xav(lambda: holat(_oq), {})
check("Q4 savatdagi buyurtmaning kelishilgan summasini o'zgartirish — 400 «avval tiklang», summa o'zgarmadi",
      _ag.status_code == 400 and "tiklang" in _ag.text and _ag0.get("deleted") and _ag0.get("agreed") == _ag1.get("agreed"),
      [_ag.status_code, _ag.text[:200], _ag0, _ag1])
_op, _ip = buyurtma()
tolov(_op, 300_000)
_s = SessionLocal()
_PAY = _s.query(Payment.id).filter(Payment.order_id == _op).first()[0]
_s.close()
_kl2 = [kirish(), kirish()]
_nat2 = {}
_to2 = threading.Barrier(2)


def _ochir(i):
    try:
        _to2.wait(timeout=10)
    except Exception:                      # noqa: BLE001
        pass
    _nat2[i] = _kl2[i].delete(f"/api/payments/{_PAY}").status_code


_th = [threading.Thread(target=_ochir, args=(i,)) for i in range(2)]
[t.start() for t in _th]
[t.join(60) for t in _th]
if PG_URL:      # haqiqiy poyga — PostgreSQL (asl kodda: ikkinchisi StaleDataError — 500)
    check("Q5 bitta to'lovni PARALLEL ikki o'chirish — biri 200, ikkinchisi 404 (500 yo'q), qarz to'g'ri",
          sorted(_nat2.values()) == [200, 404] and holat(_op)["paid"] == 0 and holat(_op)["debt"] == 1_000_000, [_nat2, holat(_op)])
else:
    check("Q5 (SQLite) parallel ikki o'chirish — 500 yo'q, to'lov o'chdi, qarz to'g'ri",
          all(v in (200, 404) for v in _nat2.values()) and holat(_op)["paid"] == 0 and holat(_op)["debt"] == 1_000_000,
          [_nat2, holat(_op)])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — sovg'a davri: faqat ISHTIROKCHI; bot = KPI sahifasi = KPI tafsiloti = oylik hisobot; yopilganda o'tkazma")
_s = SessionLocal()
_SM1 = Master(company_id=1, name="AP S Ishtirokchi", phone="+998901170001", kpi_percent=10.0, is_active=True)
_SM2 = Master(company_id=1, name="AP S Qatnashmagan", phone="+998901170002", kpi_percent=10.0, is_active=True)
_SM3 = Master(company_id=1, name="AP S Faolsizlanadi", phone="+998901170003", kpi_percent=10.0, is_active=True)
_s.add_all([_SM1, _SM2, _SM3])
_s.commit()
SM1, SM2, SM3 = _SM1.id, _SM2.id, _SM3.id
_s.close()
_SP = loyiha()
_o0, _, _ = tayyor(SM2, pid=_SP, completed_at=datetime.utcnow() - timedelta(hours=1))
_gp = C.post("/api/gift-period/open", json={"tiers": [{"gift_name": "Telefon", "threshold_amount": 50_000_000}],
                                           "master_ids": [SM1, SM3]})
check("S0 sovg'a davri ochildi (ishtirokchilar: 2 usta)", _gp.status_code == 200, _gp.text[:200])
_o2, _, _ = tayyor(SM2, pid=_SP)
_o1, _, _ = tayyor(SM1, pid=_SP)
tayyor(SM3, pid=_SP)
_mk1, _mk2 = (TAYYOR_JAVOB.get(_o1) or {}).get("master_kpi") or {}, (TAYYOR_JAVOB.get(_o2) or {}).get("master_kpi") or {}
check("S0b «Tayyor» oynasi: ishtirokchi — KPI 0 va `sovga_davrida`; qatnashmagan — KPI 95 000",
      _mk1.get("total_kpi") == 0 and _mk1.get("sovga_davrida") is True and _mk2.get("total_kpi") == 95_000
      and not _mk2.get("sovga_davrida"), [_mk1, _mk2])


def _kpi_qator(mid, y=Y):
    return next((m for m in (kpi_sahifa(y).get("masters") or []) if m["id"] == mid), {})


_b2, _k2 = bot_bonus(SM2, Y), _kpi_qator(SM2)
check("S1 qatnashmagan usta (davrdan oldin + davr ichida 2 buyurtma): bot = KPI sahifasi = 190 000 (ilgari bot 95 000)",
      round(_b2["jami_bonus"]) == 190_000 and _k2.get("gift_amount") == 190_000, [_b2["jami_bonus"], _k2])
_b1, _k1 = bot_bonus(SM1, Y), _kpi_qator(SM1)
check("S2 ishtirokchining davr ichidagi buyurtmasi — bot 0, KPI sahifasi 0 (ilgari KPI sahifasi 95 000 — keshbek HAM, sovg'a HAM)",
      round(_b1["jami_bonus"]) == 0 and _k1.get("gift_amount") == 0 and _k1.get("yearly_sales") == 1_000_000, [_b1, _k1])
_s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    _det1 = crud.get_master_kpi_detail(_s, SM1, Y, company_id=1)
_s.close()
check("S3 KPI tafsiloti: ishtirokchi buyurtmasi qatori «🎁 sovg'a davrida», KPI 0",
      len(_det1) == 1 and "sovg'a davrida" in _det1[0]["order_number"] and _det1[0]["kpi_amount"] == 0, _det1)
check("S4 oylik hisobot (yil bo'yicha): ishtirokchi KPI 0, qatnashmagan 190 000",
      usta_oylik_kpi(Y, "AP S Ishtirokchi") == 0 and usta_oylik_kpi(Y, "AP S Qatnashmagan") == 190_000, "")
C.delete(f"/api/masters/{SM3}")
_cl = C.post("/api/gift-period/close", json={"force": True})
check("S5 davr yopildi (majburiy)", _cl.status_code == 200 and js(_cl).get("success") is True, _cl.text[:200])
_b1c, _k1c = bot_bonus(SM1, Y), _kpi_qator(SM1)
check("S6 yopilgandan keyin ishtirokchi: o'tkazma 95 000 — bot = KPI sahifasi = 95 000",
      round(_b1c["gift_period_conversion"]) == 95_000 and round(_b1c["jami_bonus"]) == 95_000
      and _k1c.get("gift_amount") == 95_000 and _k1c.get("sovga_otkazma") == 95_000, [_b1c, _k1c])
check("S7 oylik hisobot: o'tkazma o'tkazilgan oyga — ishtirokchi yil bo'yicha 95 000", usta_oylik_kpi(Y, "AP S Ishtirokchi") == 95_000,
      usta_oylik_kpi(Y, "AP S Ishtirokchi"))
_s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    _det1c = crud.get_master_kpi_detail(_s, SM1, Y, company_id=1)
_s.close()
check("S8 KPI tafsiloti: o'tkazma alohida qator (foyda «—»), qatorlar yig'indisi = KPI sahifasi",
      any("keshbekka o'tkazildi" in r["order_number"] and r["profit"] is None and r["kpi_amount"] == 95_000 for r in _det1c)
      and sum(r["kpi_amount"] for r in _det1c) == _k1c.get("gift_amount"), _det1c)
_b3 = bot_bonus(SM3, Y)
check("S9 yopishdan oldin faolsizlantirilgan ishtirokchi ham o'tkazma oldi (95 000 — ilgari yo'qolardi)",
      round(_b3["gift_period_conversion"]) == 95_000, _b3)
_b2c = bot_bonus(SM2, Y)
check("S10 qatnashmagan usta yopilgandan keyin ham 190 000, o'tkazmasi yo'q", round(_b2c["jami_bonus"]) == 190_000
      and round(_b2c["gift_period_conversion"]) == 0, _b2c)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K — KPI: oylar yig'indisi = yil (keyingi oydagi qaytarish), faolsizlantirilgan usta o'tgan oylarda qoladi")
if M >= 2:
    (_ay, _am), (_by, _bm) = (Y, M - 1), (Y, M)
else:
    (_ay, _am), (_by, _bm) = (Y - 1, 11), (Y - 1, 12)
_s = SessionLocal()
_KA = Master(company_id=1, name="AP K Usta A", phone="+998901180001", kpi_percent=10.0, is_active=True)
_KB = Master(company_id=1, name="AP K Usta B", phone="+998901180002", kpi_percent=10.0, is_active=True)
_s.add_all([_KA, _KB])
_s.commit()
KA, KB = _KA.id, _KB.id
_s.close()
_ka_o, _ka_i, _ = tayyor(KA, completed_at=datetime(_ay, _am, 15, 7, 0))
tayyor(KB, completed_at=datetime(_ay, _am, 15, 7, 0))
_rt = C.post("/api/returns", json={"order_id": _ka_o, "order_item_id": _ka_i, "item_name": "x", "quantity": 3, "unit": "m",
                                   "reason": "Mijoz iltimosi", "refund_amount": 0, "to_stock": False})
_rid = js(_rt).get("id")
_rf = C.post(f"/api/returns/{_rid}/refund")
_s = SessionLocal()
_ri = _s.get(ReturnItem, _rid)
if _ri is not None:
    _ri.created_at = datetime(_by, _bm, 10, 7, 0)
    _ri.refunded_at = datetime(_by, _bm, 10, 7, 0)
    _s.commit()
_s.close()
check("K0 qaytarish va «Pul qaytdi» (keyingi oyda)", _rt.status_code == 200 and _rf.status_code == 200, [_rt.text[:200], _rf.text[:200]])
_oyma = {}
for _mm in (_am, _bm):
    _d = js(C.get("/api/finance/report", params={"year": _ay if _mm == _am else _by, "month": _mm}))
    _oyma[_mm] = next((b["kpi_amount"] for b in (_d.get("usta_kpi_breakdown") or []) if b["master_name"] == "AP K Usta A"), None)
check("K1 qaytarish oyida usta KPI MANFIY (−30 000) — ilgari o'sha oy tashlanardi",
      _oyma.get(_am) == 95_000 and _oyma.get(_bm) == -30_000, _oyma)
_ka_y = usta_oylik_kpi(_ay, "AP K Usta A")
check("K2 Usta A: oylar yig'indisi = KPI sahifasi (yil) = bot (65 000)",
      _ka_y == 65_000 == _kpi_qator(KA, _ay).get("gift_amount") and round(bot_bonus(KA, _ay)["jami_bonus"]) == 65_000,
      [_ka_y, _kpi_qator(KA, _ay), bot_bonus(KA, _ay)["jami_bonus"]])
_rep_a0 = js(C.get("/api/finance/report", params={"year": _ay, "month": _am}))
_kb0 = next((b["kpi_amount"] for b in (_rep_a0.get("usta_kpi_breakdown") or []) if b["master_name"] == "AP K Usta B"), None)
_tg0 = kpi_sahifa(_ay, inactive=False).get("total_gift")
C.delete(f"/api/masters/{KB}")
_rep_a1 = js(C.get("/api/finance/report", params={"year": _ay, "month": _am}))
_kb1 = next((b["kpi_amount"] for b in (_rep_a1.get("usta_kpi_breakdown") or []) if b["master_name"] == "AP K Usta B"), None)
check("K3 faolsizlantirilgan usta — o'tgan oy hisobotidagi KPI va sof foyda O'ZGARMADI (ilgari KPI 95 000 → 0)",
      _kb0 == 95_000 and _kb1 == 95_000 and _rep_a0.get("sof_foyda") == _rep_a1.get("sof_foyda"),
      [_kb0, _kb1, _rep_a0.get("sof_foyda"), _rep_a1.get("sof_foyda")])
_kp1 = kpi_sahifa(_ay, inactive=False)
check("K4 KPI sahifasi: «Jami» faolsizlantirilgan usta bilan (o'zgarmadi), ro'yxatda u yo'q, `nofaol_gift` ≥ 95 000",
      _kp1.get("total_gift") == _tg0 and not [m for m in _kp1.get("masters", []) if m["id"] == KB]
      and (_kp1.get("nofaol_gift") or 0) >= 95_000, [_tg0, _kp1.get("total_gift"), _kp1.get("nofaol_gift")])
_jami_oy = 0.0
for _mm in range(1, 13):
    _jami_oy += float(js(C.get("/api/finance/report", params={"year": _ay, "month": _mm})).get("usta_kpi_xarajat") or 0)
check("K5 korxona: 12 oy «Usta bonusi (KPI)» yig'indisi = KPI sahifasi «Jami» (±12 so'm yaxlitlash)",
      abs(_jami_oy - float(_kp1.get("total_gift") or 0)) <= 12, [_jami_oy, _kp1.get("total_gift")])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L — loyiha qarzi: Buyurtmalar sarlavhasi = Loyihalar = Qarzdorlar (bitta qoida)")
_KL = "AP L Mijoz"
_LP = loyiha(_KL)
_la, _ = buyurtma(pid=_LP, narx=50_000)
tolov(_la, 100_000)
_lb, _ = buyurtma(pid=_LP, narx=50_000, draft=True)
tolov(_lb, 70_000)
_lc, _lci = buyurtma(pid=_LP, narx=50_000)
tolov(_lc, 300_000)
yuk(_lc, _lci, 10)
C.post(f"/api/orders/{_lc}/ready")
_ld, _ldi = buyurtma(pid=_LP, narx=50_000)
tolov(_ld, 50_000)
yuk(_ld, _ldi, 4)
C.delete(f"/api/orders/{_ld}")
_s = SessionLocal()
_s.get(Order, _lc).created_at = datetime.utcnow() - timedelta(days=120)
_s.get(Order, _lc).completed_at = datetime.utcnow() - timedelta(days=100)
_s.commit()
_s.close()


def _sarlavha_qarz(html):
    b = html.find(f'data-project-id="{_LP}"')
    blk = html[b:html.find('class="proj-body"', b)] if b >= 0 else ""
    m = re.search(r'title="Loyiha qarzi \(barcha buyurtmalari\): ([^"]+) so\'m"', blk)
    return float(re.sub(r"[^0-9.\-]", "", m.group(1).replace(",", ".")) or 0) if m else None


_h1 = _sarlavha_qarz(C.get("/orders").text)
_h2 = _sarlavha_qarz(C.get("/orders", params={"show_all": "true"}).text)
_hp = C.get("/projects").text
_bp = _hp.find(f'data-id="{_LP}"')
_mp = re.search(r'data-qarz="([^"]+)"', _hp[_bp:_bp + 3000]) if _bp >= 0 else None
_lq = float(_mp.group(1)) if _mp else None
check("L1 Buyurtmalar sarlavhasi «Qarz» (odatiy 90 kun va «Hammasi») = Loyihalar = 750 000 (qoralama zaklati kirmaydi, 90 kundan "
      "eski va savatdagi yakunlangan — kiradi)", _h1 == 750_000 and _h2 == 750_000 and _lq == 750_000, [_h1, _h2, _lq])
_s = SessionLocal()
_qarzdor = sum(float(o.debt_amount or 0) for o in _s.query(Order).filter(Order.project_id == _LP,
                                                                         crud.qarz_hisobidagi_buyurtma_sharti()).all()
               if o.status.value != "draft")
_s.close()
check("L2 Qarzdorlar sharti bilan bir xil (750 000)", round(_qarzdor) == 750_000, _qarzdor)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T — savatdan tiklash: kelishilgan summa JORIY pul holatidan (savatdagi o'zgarishlar yo'qolmaydi)")
# T1: savatda turganda qolgan qarz chegirmaga yozildi (kechirildi)
_t1, _t1i = buyurtma()
tolov(_t1, 100_000)
yuk(_t1, _t1i, 4)
C.delete(f"/api/orders/{_t1}")
tolov(_t1, 250_000, write_off=True)
C.post(f"/api/orders/{_t1}/restore")
_h = holat(_t1)
check("T1 savatda kechirilgan qarz — tiklangach qarz = jami − kechirilgan − to'langan (soxta «Ustama» yo'q)",
      round(_h["debt"]) == round(_h["total"] - _h["kechirilgan"] - _h["paid"]) and round(_h["agreed"]) == round(_h["total"] - _h["kechirilgan"]),
      _h)


def _qaytar(oid, iid, m):
    r = C.post("/api/returns", json={"order_id": oid, "order_item_id": iid, "item_name": "x", "quantity": m, "unit": "m",
                                     "reason": "Mijoz iltimosi", "refund_amount": 0, "to_stock": True})
    return js(r).get("id")


_nat3 = {}
for _nomi, _ochir in (("nazorat", False), ("savat", True)):
    _o, _i = buyurtma()
    tolov(_o, 100_000)
    yuk(_o, _i, 4)
    _rid = _qaytar(_o, _i, 1)
    if _ochir:
        C.delete(f"/api/orders/{_o}")
    C.post(f"/api/returns/{_rid}/refund")
    if _ochir:
        C.post(f"/api/orders/{_o}/restore")
    _nat3[_nomi] = holat(_o)
check("T2 savatda «Pul qaytdi» — tiklangach kelishilgan / qarz nazorat bilan AYNAN (900 000 / 800 000)",
      (_nat3["savat"]["agreed"], _nat3["savat"]["debt"]) == (_nat3["nazorat"]["agreed"], _nat3["nazorat"]["debt"]) == (900_000, 800_000),
      _nat3)
_nat4 = {}
for _nomi, _ochir in (("nazorat", False), ("savat", True)):
    _o, _i = buyurtma()
    tolov(_o, 100_000)
    yuk(_o, _i, 4)
    _rid = _qaytar(_o, _i, 1)
    C.post(f"/api/returns/{_rid}/refund")
    if _ochir:
        C.delete(f"/api/orders/{_o}")
    C.delete(f"/api/returns/{_rid}")
    if _ochir:
        C.post(f"/api/orders/{_o}/restore")
    _nat4[_nomi] = holat(_o)
check("T3 savatda pul qaytarilgan qaytarish o'chirildi — tiklangach nazorat bilan AYNAN (1 000 000 / 900 000; ilgari 900 000 / 800 000)",
      (_nat4["savat"]["agreed"], _nat4["savat"]["debt"]) == (_nat4["nazorat"]["agreed"], _nat4["nazorat"]["debt"]) == (1_000_000, 900_000),
      _nat4)

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:\n  " + "\n  ".join(FAILED))
sys.exit(1 if FAIL else 0)
