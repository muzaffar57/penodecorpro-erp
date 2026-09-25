#!/usr/bin/env python3
"""
test_hisobot_korxona.py — kech79 darvozasi (2026-09-25, 101-band): Hisobotlar "Oyma-oy solishtirish"
(`/api/reports/comparison`, `services.get_monthly_comparison`) va "Bashorat" (`/api/reports/forecast`,
`services.get_simple_forecast`) KORXONA bilan cheklanadi — global `TENANT_FILTER` ga tayanmasdan.
Qo'shimcha: UMUMIY SIZISH DARVOZASI (S) — A korxona adminining HAMMA parametrsiz GET javoblari B korxona
ma'lumoti qo'shilishidan OLDIN va KEYIN bayt-baytga bir xil bo'lishi SHART.

O'LCHANGAN (asl kod, `work/probe101.py`, kech79): ikkala funksiyada `company_id` yo'q edi, `get_monthly_report`
korxonasiz chaqirilardi — `TENANT_FILTER` o'chiq bo'lsa A korxona admini HAMMA korxonalarning oylik daromadi /
xarajati / sof foydasini ko'rardi. Umumiy tekshiruv 104 ta GET yo'lidan FAQAT shu ikkitasini topdi; zip 73
kodida (98-band tuzatishidan OLDIN) `/api/dashboard/top-finished-products` ni ham topdi — sezgirlik isboti.
`tenant_lint` bunday so'rovlarni ko'rmaydi (funksiya ichida so'rov yo'q, faqat korxona uzatilmaydi).

Bo'limlar: A — HTTP solishtirish; B — HTTP bashorat; C — funksiya to'g'ridan (1 / 2 / None — orqaga moslik);
S — umumiy sizish darvozasi; H — statik.

Ishlatish:
    python3 tools/test_hisobot_korxona.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_hisobot_korxona.py
"""
import os
import sys
import re
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hisobot_korxona_test"
_T = tempfile.mkdtemp(prefix="hisobot_korxona_")
_DB = os.path.join(_T, "hisobot_korxona_test.db")

if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
               isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime, date                # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402

import models as M                                 # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from fastapi.routing import APIRoute               # noqa: E402
from reportlab import rl_config                    # noqa: E402

rl_config.invariant = 1   # PDF javoblari bayt-baytga takrorlanadi (sana / ID doimiy) — S bo'limi uchun

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
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


def chaqir(fn, *a, **k):
    """Funksiya chaqiruvi — asl kodda (company_id parametri yo'q) TypeError -> None (test QULAMAYDI)."""
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return {"__xato__": f"{type(e).__name__}: {e}"}


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — ikki korxona; A ma'lumoti -> A surati -> B ma'lumoti -> A surati
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if _db.get(Company, 2) is None:
    _db.add(Company(id=2, name="HK Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "HK_A", "Parol123!", M.UserRole.ADMIN, "HK A", company_id=1)
    auth.create_user(_db, "HK_B", "Parol123!", M.UserRole.ADMIN, "HK B", company_id=2)
_db.close()
EKISH_XATO = []


def ekish(cid, harf, k):
    """Korxona ma'lumoti (k — summalar ko'paytmasi: A = 1, B = 3). Har yozuv alohida commit."""
    s = SessionLocal()

    def qosh(cls, **kw):
        kol = set(cls.__table__.columns.keys())
        obj = cls(**{a: b for a, b in kw.items() if a in kol})
        try:
            s.add(obj)
            s.commit()
            return obj
        except Exception as e:             # noqa: BLE001
            s.rollback()
            EKISH_XATO.append(f"{harf} {cls.__name__}: {str(e)[:160]}")
            return None
    now = datetime.utcnow()
    prj = qosh(M.Project, company_id=cid, client_name=f"HK mijoz {harf}", project_name=f"HK {harf}",
               total_budget=0, total_paid=0)
    mas = qosh(M.Master, company_id=cid, name=f"HK usta {harf}", phone=f"+99890111{k}{k}{k}{k}", kpi_percent=5)
    fp = qosh(M.FinishedProduct, company_id=cid, name=f"HK_TM_{harf}", quantity=7 * k, unit_price=1000 * k)
    inv = qosh(M.Inventory, company_id=cid, item_name=f"HK material {harf}", unit="kg",
               stock_quantity=11 * k, price_per_unit=2000 * k, min_stock=50 * k)
    sup = qosh(M.Supplier, company_id=cid, name=f"HK taminotchi {harf}")
    emp = qosh(M.Employee, company_id=cid, name=f"HK hodim {harf}")
    for status, summa in ((M.OrderStatus.READY, 700_000 * k), (M.OrderStatus.IN_PROGRESS, 300_000 * k),
                          (M.OrderStatus.DELIVERED, 200_000 * k)):
        o = qosh(M.Order, company_id=cid, project_id=getattr(prj, "id", None),
                 order_number=f"ORD-HK{harf}-{status.value}", order_type=M.OrderType.PRODUCT, status=status,
                 completed_at=now, total_amount=summa, agreed_amount=summa, master_id=getattr(mas, "id", None))
        if o is None:
            continue
        qosh(M.OrderItem, company_id=cid, order_id=o.id, name=f"HK detal {harf} {status.value}", category="profil",
             quantity=5, unit_price=summa / 5, total_price=summa,
             finished_product_id=getattr(fp, "id", None) if status == M.OrderStatus.READY else None)
        qosh(M.Payment, order_id=o.id, amount=100_000 * k)
    qosh(M.ExpenseTransaction, company_id=cid, amount=50_000 * k, category="boshqa", date=now)
    qosh(M.ExpenseTransaction, company_id=cid, amount=40_000 * k, category="boshqa", date=now,
         production_type="penoplast")
    qosh(M.TransportExpense, company_id=cid, amount=30_000 * k, expense_date=now, production_type="penoplast")
    if sup is not None:
        qosh(M.SupplierPayment, supplier_id=sup.id, amount=20_000 * k)
    if inv is not None:
        qosh(M.InventoryMovement, company_id=cid, inventory_id=inv.id, item_name=f"HK material {harf}",
             movement_type="in", quantity=3 * k, reason="HK")
    if emp is not None:
        qosh(M.EmployeeAdvance, employee_id=emp.id, amount=10_000 * k, date=now)
    s.close()


def mijoz(harf):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    req(c, "post", "/login", data={"username": f"HK_{harf}", "password": "Parol123!"}, follow_redirects=False)
    return c


BUGUN = date.today().isoformat()
QIYMAT = {"year": 2026, "month": 9, "days": 365, "limit": 500, "target_date": BUGUN, "date": BUGUN,
          "sana": BUGUN, "start_date": "2026-01-01", "end_date": "2026-12-31", "start": "2026-01-01",
          "end": "2026-12-31", "oylar": 12, "category": "arenda", "period": "month", "q": "HK", "show_all": True}
# Sessiya / tizim yo'llari: chiqish sessiyani yopadi; zaxira — faqat platforma admini; cron — maxfiy kalit;
# health-check — jarayon bo'yicha filtr hisoblagichlari (ma'lumot emas).
CHETLAB = {"/logout", "/api/system/backup", "/api/cron/find-chat-id", "/api/system/health-check"}
YOLLAR = []
for _r in main.app.routes:
    if isinstance(_r, APIRoute) and "GET" in _r.methods and "{" not in _r.path and _r.path not in CHETLAB:
        _par, _ok = {}, True
        for _qp in _r.dependant.query_params:
            if _qp.name in QIYMAT:
                _par[_qp.name] = QIYMAT[_qp.name]
            elif (_qp.field_info.is_required() if hasattr(_qp, "field_info") else getattr(_qp, "required", False)):
                _ok = False
        if _ok:
            YOLLAR.append((_r.path, _par))
SHOVQIN = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?|\d\d:\d\d:\d\d")


def surat(c):
    out = {}
    for p, par in YOLLAR:
        r = req(c, "get", p, params=par, follow_redirects=False)
        out[p] = f"{r.status_code}|" + SHOVQIN.sub("T", str(getattr(r, "text", "")))
    return out


ekish(1, "A", 1)
CA = mijoz("A")
OLDIN = surat(CA)
ekish(2, "B", 3)
KEYIN = surat(CA)
CB = mijoz("B")
B_SURAT = surat(CB)

YIL, OY = datetime.utcnow().year, datetime.utcnow().month
_OY_OLDIN = (YIL, OY - 1) if OY > 1 else (YIL - 1, 12)


def kutilgan_solishtirish(cid):
    """Solishtirishning kutilgan qiymati — AYNAN o'sha korxonaning oylik hisobotidan."""
    s = SessionLocal()
    try:
        cur = services.get_monthly_report(s, YIL, OY, company_id=cid)
        prev = services.get_monthly_report(s, _OY_OLDIN[0], _OY_OLDIN[1], company_id=cid)
    finally:
        s.close()
    return {m: (float(cur.get(m, 0) or 0), float(prev.get(m, 0) or 0))
            for m in ("daromad", "jami_xarajat", "sof_foyda", "foyda_foiz")}


def solish_qiymat(d):
    if not isinstance(d, dict) or "__xato__" in d:
        return d
    try:
        return {m: (float(d[m]["current"]), float(d[m]["previous"]))
                for m in ("daromad", "jami_xarajat", "sof_foyda", "foyda_foiz")}
    except Exception as e:                 # noqa: BLE001
        return {"__xato__": f"{type(e).__name__}: {e}"}


K_A, K_B, K_HAMMA = kutilgan_solishtirish(1), kutilgan_solishtirish(2), kutilgan_solishtirish(None)
print("Kutilgan sof_foyda (joriy oy): A", K_A["sof_foyda"][0], " B", K_B["sof_foyda"][0], " hamma", K_HAMMA["sof_foyda"][0])
print("Kutilgan jami_xarajat: A", K_A["jami_xarajat"][0], " B", K_B["jami_xarajat"][0])
if EKISH_XATO:
    print("EKISH XATOLARI:", EKISH_XATO)

section("0 — fikstura sezgirligi")
check("01 A va B ning oylik xarajati FARQLI (fikstura korxonalarni ajrata oladi)",
      K_A["jami_xarajat"][0] > 0 and K_B["jami_xarajat"][0] > K_A["jami_xarajat"][0], (K_A, K_B))
check("02 korxonasiz hisobot = A + B (orqaga moslik — hamma korxonalar)",
      abs(K_HAMMA["jami_xarajat"][0] - K_A["jami_xarajat"][0] - K_B["jami_xarajat"][0]) < 0.01, K_HAMMA)
check("03 ekish xatosiz", not EKISH_XATO, EKISH_XATO)
check("04 A va B ning oylik DAROMADI ham farqli va musbat (READY buyurtma)",
      0 < K_A["daromad"][0] < K_B["daromad"][0], (K_A["daromad"], K_B["daromad"]))

section("A — HTTP /api/reports/comparison")
for _h, _cl, _k in (("A", CA, K_A), ("B", CB, K_B)):
    _r = req(_cl, "get", "/api/reports/comparison", params={"year": YIL, "month": OY})
    _v = solish_qiymat(js(_r))
    check(f"A1{_h} {_h} admini faqat O'Z korxonasi solishtirishini oladi (joriy va o'tgan oy)",
          _r.status_code == 200 and _v == _k, (_r.status_code, _v, _k))
    check(f"A2{_h} {_h} javobi hamma korxonalar yig'indisi EMAS",
          _v != K_HAMMA, _v)

section("B — HTTP /api/reports/forecast")
for _h, _cl, _k in (("A", CA, K_A), ("B", CB, K_B)):
    _r = req(_cl, "get", "/api/reports/forecast", params={"year": YIL, "month": OY})
    _d = js(_r) or {}
    check(f"B1{_h} {_h} bashorati o'z korxonasi sof foydasidan (current_foyda)",
          _r.status_code == 200 and _d.get("current_foyda") == round(_k["sof_foyda"][0]), (_r.status_code, _d, _k["sof_foyda"]))
    check(f"B2{_h} {_h} current_daromad o'z korxonasidan",
          _d.get("current_daromad") == round(_k["daromad"][0]), (_d, _k["daromad"]))
    check(f"B3{_h} {_h} bashorati hamma korxonalarniki EMAS",
          _d.get("current_foyda") != round(K_HAMMA["sof_foyda"][0]), _d)

section("C — funksiya to'g'ridan (company_id = 1 / 2 / None)")
_s = SessionLocal()
for _cid, _k in ((1, K_A), (2, K_B), (None, K_HAMMA)):
    _v = solish_qiymat(chaqir(services.get_monthly_comparison, _s, YIL, OY, company_id=_cid))
    check(f"C1 get_monthly_comparison(company_id={_cid}) == shu korxona hisoboti", _v == _k, (_v, _k))
    _f = chaqir(services.get_simple_forecast, _s, YIL, OY, company_id=_cid)
    check(f"C2 get_simple_forecast(company_id={_cid}) current_foyda", isinstance(_f, dict)
          and _f.get("current_foyda") == round(_k["sof_foyda"][0]), (_f, _k["sof_foyda"]))
_v0 = solish_qiymat(chaqir(services.get_monthly_comparison, _s, YIL, OY))
check("C3 korxonasiz (eski imzo) chaqiruv — hamma korxonalar (orqaga moslik)", _v0 == K_HAMMA, _v0)
_s.close()

section("S — umumiy sizish darvozasi (A ning HAMMA parametrsiz GET javoblari)")
_ozgargan = sorted(p for p in OLDIN if OLDIN[p] != KEYIN.get(p))
print(f"  yo'llar: {len(YOLLAR)}   o'zgargan: {_ozgargan}")
check("S1 B korxona ma'lumoti qo'shilgach A ning birorta GET javobi O'ZGARMADI", not _ozgargan, _ozgargan)
check(f"S2 yo'llar soni yetarli (>= 90; hozir {len(YOLLAR)})", len(YOLLAR) >= 90, len(YOLLAR))
_b_ozi = sorted(p for p, v in B_SURAT.items() if "HK mijoz B" in v or "HK detal B" in v or "HK material B" in v)
check(f"S3 sezgirlik: B o'z ma'lumotini kamida 5 yo'lda ko'radi (hozir {len(_b_ozi)})", len(_b_ozi) >= 5, _b_ozi)
_a_ozi = [p for p, v in KEYIN.items() if "HK mijoz A" in v or "HK detal A" in v or "HK material A" in v]
check("S4 A o'z ma'lumotini ko'radi, B nomini hech qayerda ko'rmaydi",
      len(_a_ozi) >= 5 and not [p for p, v in KEYIN.items() if "HK mijoz B" in v or "HK detal B" in v
                                 or "HK material B" in v or "HK_TM_B" in v or "HK usta B" in v], _a_ozi)
# cron yo'llari maxfiy kalit sozlanmagan muhitda ATAYLAB 503 qaytaradi (main: "CRON_SECRET ... o'rnatilmagan").
_xato5 = sorted(p for p, v in KEYIN.items() if v.startswith("5") and "CRON_SECRET" not in v)
check("S5 A ning GET javoblarida 5xx yo'q (cron 503 — dizayn)", not _xato5, _xato5)

section("H — statik")
_fc = manba(services, "get_monthly_comparison")
_ff = manba(services, "get_simple_forecast")
_rc = manba(main, "api_reports_comparison")
_rf = manba(main, "api_reports_forecast")
check("H1 solishtirishda company_id parametri", "company_id: int = None" in _fc.split(":\n")[0] + ":", _fc[:120])
check("H2 joriy oy hisobotiga korxona uzatiladi",
      "get_monthly_report(db, year, month, company_id=company_id)" in _fc)
check("H3 o'tgan oy hisobotiga korxona uzatiladi",
      "get_monthly_report(db, prev_year, prev_month, company_id=company_id)" in _fc)
check("H4 bashoratda company_id parametri va uzatish",
      "company_id: int = None" in _ff.split(":\n")[0] + ":" and
      "get_monthly_report(db, year, month, company_id=company_id)" in _ff)
check("H5 solishtirish marshruti korxonani uzatadi", "company_id=auth.company_id_of(current_user)" in _rc, _rc[-160:])
check("H6 bashorat marshruti korxonani uzatadi", "company_id=auth.company_id_of(current_user)" in _rf, _rf[-160:])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
