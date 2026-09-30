#!/usr/bin/env python3
"""
test_toshkent_vaqt.py — kech105, 9 + 50-band darvozasi. FOYDALANUVCHI QARORI (2026-09-28): "Toshkent vaqti bo'yicha
(Tavsiya)" — hisobotlarning kun / oy / yil chegaralari TOSHKENT kalendari bo'yicha, kun 00:00 da almashadi; hamma
hisobot va bosh sahifadagi "Bugun" oynasi bir xil.

NIMA UCHUN (asl kod staging `77ef78a` da O'LCHANGAN — `work/probe105v.py`, SQLite = PG)
---------------------------------------------------------------------------------------
Baza vaqtni UTC da saqlaydi. Hisobotlar oy / kunni UTC `extract` bilan olardi — Toshkent vaqti bilan kun 05:00 da
almashardi: 1-oktyabr 01:30 (UTC 30.09 20:30) va 04:59 da «Tayyor» bo'lgan buyurtmalar, to'lov va xarajatlar SENTYABR
oylik hisobotiga (3 buyurtma 700 000; usta KPI 68 500) va 30-sentabr kunlik hisobotiga tushardi; "Bugun" oynasi
(`get_today_stats` — Toshkent kuni) ularni 1-oktyabr derdi, yonidagi ogohlantirish esa (`get_business_alerts` —
UTC kun) "Bugun 1 ta buyurtma yakunlandi" (aslida 3). Kodda: `get_production_period_stats` hafta boshi Seshanba
00:00 dan, oy boshi 2-kun 00:00 dan (UTC ga siljigan sanadan); `get_chart_data` 6 oyni 30 kunlik qadam bilan olardi.

BO'LIMLAR (hodisalar Toshkent vaqti bilan: T1 30.09 23:30, T2 01.10 01:30, T3 01.10 04:59, T4 01.10 05:30)
  A — oylik hisobot (buyurtmalar, daromad, usta KPI, xarajatlar), sentyabr / oktyabr
  B — kunlik hisobot (30.09 / 01.10)
  C — xarajatlar ro'yxati (oy, kun, yilsiz oy — 400) va FAQAT SANA kiritilgan xarajat (yarim tun) o'z kunida
  D — yil chegarasi: 01.01 01:00 dagi «Tayyor» — yangi yil (usta KPI hisoboti, keshbek)
  E — "hozir" simulyatsiyasi: "Bugun" oynasi = ogohlantirish; ishlab chiqarish hafta / oy boshi; kunlik hisobot va
      KPI yili standartlari; grafik oylari; qaytarishlar / loyihalar "shu oy"; brak tahlili standart oyi (E12);
      majburiyat / hodim "yaratilgan / ishga kirgan oy" (E13–E15)
  F — statik: hisobot kodida UTC `extract('year' | 'month' | 'day')` yo'q; `utcnow().year|month|day|date()` yo'q;
      `x = datetime.utcnow()` dan keyin `x.year | month …` yo'q (F7 — kech105 vaqt sayohati o'lchovi topgan shakl);
      yordamchilar bor

VAQT SAYOHATI (kech105 o'lchovi, repoga kirmaydi — `run/h106vaqt.sh`, `time-machine`): butun py to'plami Toshkent
01.10 02:00 (UTC 30.09 21:00), 16.10 01:00 va 01.01.2027 01:00 da, TZ=UTC va TZ=Asia/Tashkent — 0 yiqilish kerak.

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_toshkent_vaqt.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_toshkent_vaqt.py
"""
import os
import re
import sys
import tempfile
from datetime import datetime, date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "toshkent_vaqt_test"
_DB = os.path.join(tempfile.gettempdir(), "toshkent_vaqt_test.db")
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
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth, services, crud, database          # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Project, Inventory, Master, FinishedProduct, StockSource   # noqa: E402
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
        print(f"  ✗ {label}   {str(detail)[:400]}")


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


def xavfsiz(fn, *a, **k):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {str(e)[:200]}")


class _Soat:
    """"Hozir" ni simulyatsiya qiladi: `database.datetime.utcnow()` (Toshkent yordamchilari shuni o'qiydi)."""

    def __init__(self, utc):
        self.utc = utc

    def __enter__(self):
        utc = self.utc

        class _D(datetime):
            @classmethod
            def utcnow(cls):
                return utc
        self._asl = database.datetime
        database.datetime = _D
        return self

    def __exit__(self, *a):
        database.datetime = self._asl


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


# ── fikstura ────────────────────────────────────────────────────────────────────────────────────────────────
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "tv_admin", "Parol123!", UserRole.ADMIN, "TV admin", company_id=1)
PRJ = Project(company_id=1, client_name="TV Mijoz", project_name="TV loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="TV Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
USTA = Master(company_id=1, name="TV Usta", phone="+998900001051", kpi_percent=10)
s.add_all([PRJ, PENO, USTA])
s.commit()
PRJ_ID, PENO_ID, USTA_ID = PRJ.id, PENO.id, USTA.id
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "tv_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

# Toshkent vaqti → UTC: T − 5 soat
LAHZA = {"T1": datetime(2026, 9, 30, 18, 30), "T2": datetime(2026, 9, 30, 20, 30),
         "T3": datetime(2026, 9, 30, 23, 59), "T4": datetime(2026, 10, 1, 0, 30),
         "Y1": datetime(2025, 12, 31, 20, 0)}          # Y1 = Toshkent 01.01.2026 01:00
NARX = {"T1": 100_000, "T2": 200_000, "T3": 400_000, "T4": 800_000, "Y1": 1_600_000}
ID = {}
for k in LAHZA:
    tana = {"project_id": PRJ_ID, "order_type": "product", "master_id": USTA_ID,
            "items": [{"name": f"TV {k}", "category": "profil", "width": 20, "thickness": 10, "length": 1,
                       "quantity": 1, "unit_price": NARX[k], "is_coated": False, "penoplast_id": PENO_ID}]}
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id") if r.status_code == 200 else None
    rt = req(C, "post", f"/api/orders/{oid}/ready")
    rp = req(C, "post", "/api/payments", json={"order_id": oid, "amount": NARX[k] / 10, "payment_method": "naqd"})
    rx = req(C, "post", "/api/finance/transactions", json={"category": f"TV xarajat {k}", "amount": NARX[k] / 100,
                                                           "production_type": "penoplast"})
    ID[k] = {"order": oid, "holat": [r.status_code, rt.status_code, rp.status_code, rx.status_code]}
# faqat SANA kiritilgan xarajatlar (forma: YYYY-MM-DD → yarim tun)
for k, sana in (("D29", "2026-09-29"), ("D30", "2026-09-30"), ("D01", "2026-10-01"), ("D02", "2026-10-02")):
    rx = req(C, "post", "/api/finance/transactions", json={"category": f"TV sana {k}", "amount": 500, "date": sana,
                                                           "production_type": "penoplast"})
    ID[k] = {"holat": [rx.status_code]}
s = SessionLocal()
try:
    for k, t in LAHZA.items():
        s.execute(text("UPDATE orders SET completed_at = :d, created_at = :d WHERE id = :i"), {"d": t, "i": ID[k]["order"]})
        s.execute(text("UPDATE payments SET paid_at = :d WHERE order_id = :i"), {"d": t, "i": ID[k]["order"]})
        s.execute(text("UPDATE expense_transactions SET date = :d, created_at = :d WHERE category = :c"),
                  {"d": t, "c": f"TV xarajat {k}"})
    s.execute(text("UPDATE orders SET created_at = :d WHERE id = :i"), {"d": datetime(2026, 9, 15, 7, 0),
                                                                        "i": ID["T2"]["order"]})
    s.commit()
finally:
    s.close()


def kimlar(summa, bolinuvchi=1):
    """Summa qaysi hodisalardan tuzilgan (NARX / bolinuvchi — ikkining darajalari, yagona yechim)."""
    out, qoldiq = [], round(float(summa or 0))
    for k in ("Y1", "T4", "T3", "T2", "T1"):
        v = round(NARX[k] / bolinuvchi)
        if qoldiq >= v and v > 0:
            out.append(k)
            qoldiq -= v
    return sorted(out) if qoldiq == 0 else f"aniqlanmadi ({summa})"


section("0. Tayyorgarlik")
check("0.1 hodisalar yaratildi (buyurtma / «Tayyor» / to'lov / xarajat — 200)",
      all(v["holat"] == [200, 200, 200, 200] for k, v in ID.items() if k in LAHZA)
      and all(ID[k]["holat"] == [200] for k in ("D29", "D30", "D01", "D02")), ID)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Oylik hisobot — Toshkent oyi")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
OY = {}
for oy in (9, 10):
    r = req(C, "get", "/api/finance/report", params={"year": 2026, "month": oy})
    OY[oy] = js(r) if r.status_code == 200 else {}
check("A1 sentyabr: faqat T1 (30.09 23:30) — 1 buyurtma, daromad 100 000 (asl: T1+T2+T3 — 3 / 700 000)",
      OY[9].get("buyurtmalar_soni") == 1 and kimlar(OY[9].get("daromad_buyurtmalardan")) == ["T1"],
      [OY[9].get("buyurtmalar_soni"), OY[9].get("daromad_buyurtmalardan")])
check("A2 oktyabr: T2 + T3 + T4 — 3 buyurtma, daromad 1 400 000 (asl: faqat T4 — 1 / 800 000)",
      OY[10].get("buyurtmalar_soni") == 3 and kimlar(OY[10].get("daromad_buyurtmalardan")) == ["T2", "T3", "T4"],
      [OY[10].get("buyurtmalar_soni"), OY[10].get("daromad_buyurtmalardan")])
_kpi9, _kpi10 = OY[9].get("usta_kpi_xarajat"), OY[10].get("usta_kpi_xarajat")
check("A3 usta KPI: sentyabr faqat T1 ulushi, oktyabr T2+T3+T4 ulushi (10 % foydadan; asl: 68 500 / 79 500)",
      isinstance(_kpi9, (int, float)) and isinstance(_kpi10, (int, float)) and 0 < _kpi9 <= 10_000
      and 100_000 < _kpi10 <= 140_000, [_kpi9, _kpi10])
_x9 = sorted(k for k in (OY[9].get("qoshimcha_xarajatlar") or {}) if str(k).startswith("TV "))
_x10 = sorted(k for k in (OY[10].get("qoshimcha_xarajatlar") or {}) if str(k).startswith("TV "))
check("A4 xarajatlar: sentyabr — T1 va 29 / 30.09 sanali; oktyabr — T2, T3, T4 va 01 / 02.10 sanali",
      _x9 == ["TV sana D29", "TV sana D30", "TV xarajat T1"]
      and _x10 == ["TV sana D01", "TV sana D02", "TV xarajat T2", "TV xarajat T3", "TV xarajat T4"], [_x9, _x10])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Kunlik hisobot — Toshkent kuni")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
KUN = {}
for kun in ("2026-09-30", "2026-10-01"):
    r = req(C, "get", "/api/finance/daily", params={"target_date": kun})
    KUN[kun] = js(r) if r.status_code == 200 else {}
_s30, _s01 = (KUN["2026-09-30"].get("sales") or {}), (KUN["2026-10-01"].get("sales") or {})
check("B1 30.09 — faqat T1 (asl: T1+T2+T3)", _s30.get("orders_count") == 1 and kimlar(_s30.get("total")) == ["T1"],
      _s30)
check("B2 01.10 — T2 + T3 + T4 (asl: faqat T4)", _s01.get("orders_count") == 3
      and kimlar(_s01.get("total")) == ["T2", "T3", "T4"], _s01)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Xarajatlar ro'yxati; faqat sana kiritilgan xarajat")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════


def xarajat_nomlari(**p):
    r = req(C, "get", "/api/finance/transactions", params=p)
    j = js(r)
    return r.status_code, sorted(x.get("category") for x in (j if isinstance(j, list) else [])
                                 if str(x.get("category", "")).startswith("TV "))


_st, _n9 = xarajat_nomlari(year=2026, month=9)
check("C1 oy 9 — T1, D29, D30 (asl: + T2, T3)", _st == 200 and _n9 == ["TV sana D29", "TV sana D30", "TV xarajat T1"],
      _n9)
_st, _n10 = xarajat_nomlari(year=2026, month=10)
check("C2 oy 10 — T2, T3, T4, D01, D02", _st == 200
      and _n10 == ["TV sana D01", "TV sana D02", "TV xarajat T2", "TV xarajat T3", "TV xarajat T4"], _n10)
_st, _d01 = xarajat_nomlari(year=2026, month=10, day=1)
check("C3 kun 01.10 — T2, T3, T4 va D01 (02.10 dagi D02 EMAS; asl: T4 va D01)", _st == 200
      and _d01 == ["TV sana D01", "TV xarajat T2", "TV xarajat T3", "TV xarajat T4"], _d01)
_st, _d30 = xarajat_nomlari(year=2026, month=9, day=30)
check("C4 kun 30.09 — T1 va D30 (29.09 dagi D29 EMAS; faqat sana — yarim tun o'z kunida)", _st == 200
      and _d30 == ["TV sana D30", "TV xarajat T1"], _d30)
_st, _y = xarajat_nomlari(year=2026)
check("C5 yil 2026 — 9 ta (T1–T4, to'rt sanali, Y1 = Toshkent 01.01.2026 01:00 ham 2026 da; asl: Y1 2025 da)",
      _st == 200 and len(_y) == 9 and "TV xarajat Y1" in _y, _y)
_r = req(C, "get", "/api/finance/transactions", params={"month": 10})
check("C6 yilsiz oy filtri — 400 aniq xabar (asl: har yilning 10-oyi, UTC)", _r.status_code == 400
      and "yil" in str((js(_r) or {}).get("detail", "")), [_r.status_code, getattr(_r, "text", "")[:120]])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Yil chegarasi — Toshkent 01.01.2026 01:00 dagi «Tayyor»")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r25 = js(req(C, "get", "/api/masters/kpi-report", params={"year": 2025})) or {}
_r26 = js(req(C, "get", "/api/masters/kpi-report", params={"year": 2026})) or {}


def _usta(r):
    for m in (r.get("masters") or []):
        if m.get("name") == "TV Usta":
            return m
    return {}


check("D1 usta KPI hisoboti 2025 — Y1 YO'Q (asl: Y1 2025 da)", _usta(_r25).get("orders_count", 0) == 0,
      _usta(_r25))
check("D2 usta KPI hisoboti 2026 — 5 buyurtma (T1–T4 + Y1), savdo 3 100 000", _usta(_r26).get("orders_count") == 5
      and round(float(_usta(_r26).get("yearly_sales") or 0)) == 3_100_000, _usta(_r26))
_s = SessionLocal()
try:
    _kb25 = xavfsiz(crud.get_master_yearly_cashback, _s, USTA_ID, 2025, company_id=1)
    _kb26 = xavfsiz(crud.get_master_yearly_cashback, _s, USTA_ID, 2026, company_id=1)
finally:
    _s.close()
check("D3 keshbek: 2025 — 0 buyurtma; 2026 — 5 buyurtma (asl: Y1 2025 da)",
      isinstance(_kb25, dict) and isinstance(_kb26, dict) and len(_kb25.get("orders") or []) == 0
      and len(_kb26.get("orders") or []) == 5, [str(_kb25)[:200], str(_kb26)[:200]])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. \"Hozir\" simulyatsiyasi")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
with _Soat(datetime(2026, 10, 1, 1, 0)):          # Toshkent 01.10 06:00
    _s = SessionLocal()
    try:
        _bugun = xavfsiz(services.get_today_stats, _s, company_id=1)
        _ogoh = xavfsiz(services.get_business_alerts, _s, company_id=1)
    finally:
        _s.close()
    _rd = req(C, "get", "/api/finance/daily")
_ogoh_txt = [a.get("text") for a in (_ogoh if isinstance(_ogoh, list) else []) if "Bugun" in str(a.get("text"))]
# kech117 (A2): bugungi daromad yo'nalishlar bo'yicha (`today_yonalishlar`; eski `today_penoplast_revenue` yo'q) —
# profil buyurtmalari asosiy yo'nalishga (Penoplast)
_bugun_yon = {y.get("nom"): y.get("daromad") for y in ((_bugun or {}).get("today_yonalishlar") or [])} \
    if isinstance(_bugun, dict) else {}
check("E1 'Bugun' oynasi (01.10 06:00) — T2 + T3 + T4 savdosi 1 400 000 (asosiy yo'nalish — Penoplast)",
      isinstance(_bugun, dict) and round(float(_bugun_yon.get("Penoplast") or 0)) == 1_400_000
      and round(sum(float(v or 0) for v in _bugun_yon.values())) == 1_400_000, _bugun)
check("E2 ogohlantirish oyna bilan BIR XIL: 'Bugun 3 ta buyurtma yakunlandi' (asl: 1 ta)",
      _ogoh_txt == ["Bugun 3 ta buyurtma yakunlandi"], _ogoh_txt)
check("E3 /api/finance/daily sanasiz — Toshkent 'bugun' (2026-10-01), 3 buyurtma",
      _rd.status_code == 200 and str((js(_rd) or {}).get("date", ""))[:10] == "2026-10-01"
      and ((js(_rd) or {}).get("sales") or {}).get("orders_count") == 3, getattr(_rd, "text", "")[:200])

# ishlab chiqarish — hafta / oy boshi (hozir = Toshkent Dushanba 28.09 10:00 = UTC 05:00)
_s = SessionLocal()
try:
    for nom, t, miqdor in (("TV TM dushanba", datetime(2026, 9, 27, 19, 30), 1),      # Dush. 28.09 00:30
                           ("TV TM yakshanba", datetime(2026, 9, 27, 18, 30), 10),    # Yak. 27.09 23:30
                           ("TV TM seshanba", datetime(2026, 9, 21, 19, 30), 100),    # Sesh. 22.09 00:30
                           ("TV TM oy1", datetime(2026, 8, 31, 19, 30), 1000),        # 01.09 00:30
                           ("TV TM avgust", datetime(2026, 8, 31, 18, 30), 10000)):   # 31.08 23:30
        _s.add(FinishedProduct(company_id=1, name=nom, category="profil", quantity=miqdor, produced_quantity=miqdor,
                               unit="metr", source=StockSource.PRODUCED, created_at=t))
    _s.commit()
    with _Soat(datetime(2026, 9, 28, 5, 0)):
        _pp = xavfsiz(services.get_production_period_stats, _s, company_id=1)
finally:
    _s.close()
check("E4 ishlab chiqarish 'bugun' — faqat dushanba 00:30 (1)", isinstance(_pp, dict) and _pp.get("today") == 1, _pp)
check("E5 'hafta' — Dushanba 00:00 dan: faqat 1 (asl: Seshanba 22.09 dan — 111)", isinstance(_pp, dict)
      and _pp.get("week") == 1, _pp)
check("E6 'oy' — 1-sentyabr 00:00 dan: 1 + 10 + 100 + 1000 = 1111 (asl: 2-kundan — 111)", isinstance(_pp, dict)
      and _pp.get("month") == 1111, _pp)

# KPI yili standarti (hozir = Toshkent 01.01.2027 01:00 = UTC 31.12.2026 20:00)
with _Soat(datetime(2026, 12, 31, 20, 0)):
    _rk = req(C, "get", "/api/masters/kpi-report")
check("E7 KPI hisoboti yilsiz — Toshkent yili 2027 (asl: 2026)", _rk.status_code == 200
      and (js(_rk) or {}).get("year") == 2027, getattr(_rk, "text", "")[:160])

# brak tahlili — oy berilmasa joriy oy (hozir = Toshkent 01.10.2026 02:00 = UTC 30.09 21:00: UTC oyi 9, Toshkent oyi 10).
# kech105 vaqt sayohati o'lchovi topgan: `_hozir = datetime.utcnow()` o'zgaruvchi orqali — F5 naqshiga tushmagan (F7).
with _Soat(datetime(2026, 9, 30, 21, 0)):
    _rb = req(C, "get", "/api/reports/brak-tahlil")
check("E12 brak tahlili parametrsiz — Toshkent oyi (2026, 10) (asl: `datetime.utcnow()` — UTC / haqiqiy soat oyi)",
      _rb.status_code == 200 and ((js(_rb) or {}).get("yil"), (js(_rb) or {}).get("oy")) == (2026, 10),
      getattr(_rb, "text", "")[:160])

# grafik — oxirgi 6 oy (hozir = Toshkent 01.10.2026 06:00): oktyabr ustuni T2+T3+T4, sentyabr — T1
with _Soat(datetime(2026, 10, 1, 1, 0)):
    _s = SessionLocal()
    try:
        _ch = xavfsiz(services.get_chart_data, _s, company_id=1)
    finally:
        _s.close()
_oylar = (_ch or {}).get("months") if isinstance(_ch, dict) else None
_oylar = _oylar if isinstance(_oylar, list) else []
_rev = [round(float(m.get("revenue") or 0)) for m in _oylar]
check("E8 grafik: 6 oy, oxirgisi 'Oct 2026' — daromad T2+T3+T4 = 1 400 000 («Tayyor» oyi — T2 15.09 da yaratilgan), "
      "'Sep 2026' — T1 = 100 000 (asl: UTC 30 kunlik, yaratilgan oyi)",
      len(_oylar) == 6 and _rev[-1] == 1_400_000 and _rev[-2] == 100_000
      and [m.get("label") for m in _oylar[-2:]] == ["Sep 2026", "Oct 2026"], [_oylar[-2:] if _oylar else _ch])

# qaytarishlar / loyihalar "shu oy" (hozir = Toshkent 01.10 06:00): 30.09 20:30 UTC dagi brak — oktyabr
_s = SessionLocal()
try:
    _s.execute(text("UPDATE projects SET start_date = :d WHERE id = :i"), {"d": datetime(2026, 9, 30, 20, 30),
                                                                           "i": PRJ_ID})
    _s.commit()
    with _Soat(datetime(2026, 10, 1, 1, 0)):
        _pd = xavfsiz(crud.get_projects_dashboard_stats, _s, company_id=1)
finally:
    _s.close()
check("E9 loyihalar paneli 'shu oy boshlangan' — 01.10 01:30 (Toshkent) dagi loyiha oktyabrda (asl: 0)",
      isinstance(_pd, dict) and _pd.get("started_this_month") == 1, _pd if isinstance(_pd, dict) else _pd)

# kirim statistikasi / moliya tarixi — joriy oy standarti (hozir = Toshkent 01.10 06:00)
_rk = req(C, "post", f"/api/inventory/{PENO_ID}/purchase", json={"quantity": 2, "price_per_unit": 1000,
                                                                   "notes": "TV kirim"})
_s = SessionLocal()
try:
    _s.execute(text("UPDATE inventory_purchases SET purchased_at = :d WHERE notes = 'TV kirim'"),
               {"d": datetime(2026, 9, 30, 20, 30)})
    _s.commit()
    with _Soat(datetime(2026, 10, 1, 1, 0)):
        _ps = xavfsiz(crud.get_purchase_stats, _s, company_id=1)
        _fh = xavfsiz(services.get_finance_history, _s, 2, company_id=1)
finally:
    _s.close()
check("E10 kirim statistikasi (oy berilmagan) — Toshkent oktyabri: 01.10 01:30 dagi 2 000 so'mlik kirim BOR (asl: sentyabr)",
      _rk.status_code == 200 and isinstance(_ps, dict) and _ps.get("month") == 10
      and round(float(_ps.get("total_amount") or 0)) == 2000, [_rk.status_code, str(_ps)[:300]])
check("E11 moliya tarixi (eskidan yangiga) — sentyabr, so'ng Toshkent joriy oyi oktyabr (asl: avgust, sentyabr)",
      isinstance(_fh, list) and len(_fh) == 2 and [(_x.get("year"), _x.get("month")) for _x in _fh]
      == [(2026, 9), (2026, 10)], [(_x.get("year"), _x.get("month")) for _x in _fh] if isinstance(_fh, list) else _fh)

# "yaratilgan / ishga kirgan oy" — Toshkent kalendari (kech105 vaqt sayohati o'lchovining 2-bosqichi topgan): Toshkent
# 01.10 01:30 (UTC 30.09 20:30) da qo'shilgan majburiyat va hodim SENTYABRGA tushmaydi (asl: tushardi — oy oxiri UTC
# 23:59:59, to'lov tarixi oyi — UTC `hire.month`).
from models import RecurringObligation, Employee, EmployeeCompensationHistory, PayType   # noqa: E402
_s = SessionLocal()
try:
    _s.add(RecurringObligation(company_id=1, category="tv_ob", label="TV majburiyat", icon="📦", monthly_target=10_000,
                               due_day=5, is_active=True, created_at=datetime(2026, 9, 30, 20, 30)))
    _hod = Employee(company_id=1, name="TV hodim", pay_type=PayType.FIXED, fixed_amount=1_000_000, is_active=True,
                    hire_date=datetime(2026, 9, 30, 20, 30))
    _s.add(_hod)
    _s.commit()
    _HOD_ID = _hod.id
    with _Soat(datetime(2026, 10, 1, 1, 0)):
        _obs = xavfsiz(services.get_company_obligations_status, _s, 2026, 10, company_id=1)
        _bf = xavfsiz(crud.backfill_employee_compensation_history, _s, company_id=1)
    _tarix = [(h.effective_year, h.effective_month) for h in _s.query(EmployeeCompensationHistory).filter(
        EmployeeCompensationHistory.employee_id == _HOD_ID).all()]
    _pay9 = xavfsiz(services.calculate_monthly_employee_pay, _s, 2026, 9, 0, 0, 0, 0, 0, company_id=1)
    _pay10 = xavfsiz(services.calculate_monthly_employee_pay, _s, 2026, 10, 0, 0, 0, 0, 0, company_id=1)
finally:
    _s.close()
_ob_oylar = sorted((r.get("year"), r.get("month")) for r in ((_obs.get("recurring") or []) if isinstance(_obs, dict) else [])
                   if r.get("category") == "tv_ob")
check("E13 majburiyat (Toshkent 01.10 01:30 da yaratilgan) — qarz faqat oktyabrda (asl: sentyabrda ham)",
      _ob_oylar == [(2026, 10)], [_ob_oylar, str(_obs)[:200]])
check("E14 hodim to'lov tarixi (avtomatik to'ldirish) boshlanish oyi — (2026, 10) (asl: (2026, 9) — UTC oyi)",
      _tarix == [(2026, 10)], [_tarix, _bf])
_nomlar9 = [b.get("name") for b in (_pay9.get("breakdown") or [])] if isinstance(_pay9, dict) else _pay9
_nomlar10 = [b.get("name") for b in (_pay10.get("breakdown") or [])] if isinstance(_pay10, dict) else _pay10
check("E15 hodim oyligi: sentyabrda YO'Q, oktyabrda BOR (asl: sentyabrda ham — UTC 23:59:59 oy oxiri)",
      isinstance(_nomlar9, list) and "TV hodim" not in _nomlar9 and isinstance(_nomlar10, list)
      and "TV hodim" in _nomlar10, [_nomlar9, _nomlar10])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. Statik")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
for nom in ("services.py", "crud.py", "main.py"):
    _kod = "\n".join(q for q in fayl(nom).split("\n") if not q.strip().startswith("#"))
    _qoldiq = re.findall(r"[\w\.]*extract[\w]*\('(?:year|month|day)'", _kod)
    check(f"F1 {nom}: UTC `extract('year' | 'month' | 'day')` YO'Q (hisobot oy / kuni Toshkent oralig'i bilan)",
          len(_kod) > 1000 and not _qoldiq, _qoldiq[:5])
for nom in ("services.py", "crud.py", "main.py"):
    _kod = "\n".join(q for q in fayl(nom).split("\n") if not q.strip().startswith("#"))
    _utc_std = re.findall(r"utcnow\(\)\.(?:year|month|day|date\(\))", _kod)
    check(f"F5 {nom}: 'joriy yil / oy / kun' UTC dan olinmaydi (`utcnow().year|month|day|date()` YO'Q)",
          len(_kod) > 1000 and not _utc_std, _utc_std[:5])
    _py_oy = re.findall(r"\.month == (?:now|_hozir|today)\.month", _kod)
    check(f"F6 {nom}: Python 'shu oy' taqqoslashi xom UTC vaqt bilan emas (`x.month == now.month` YO'Q)",
          len(_kod) > 1000 and not _py_oy, _py_oy[:5])


def utc_ozgaruvchi_kalendar(kod):
    """`x = datetime.utcnow()` (yoki `_dt` / `dt`) dan keyin SHU funksiya ichida `x.year | x.month | x.day | x.date() |
    x.replace(day=…) | x.weekday()` — joriy yil / oy / kun UTC dan (F5 ushlamaydigan shakl; kech105 vaqt sayohati
    o'lchovi `main.api_brak_tahlil` da topgan)."""
    qatorlar = [q.split("#", 1)[0] for q in kod.split("\n")]
    topildi = []
    for i, q in enumerate(qatorlar):
        m = re.match(r"^(\s*)([A-Za-z_]\w*)\s*=\s*(?:datetime|_dt|dt)\.utcnow\(\)\s*$", q)
        if not m:
            continue
        chuqurlik, nom = len(m.group(1)), m.group(2)
        for q2 in qatorlar[i + 1:i + 150]:
            if q2.strip() and len(q2) - len(q2.lstrip()) < chuqurlik and re.match(r"\s*(def |class |@)", q2):
                break
            if re.search(r"\b" + re.escape(nom) + r"\.(?:year|month|day\b|date\(\)|replace\(\s*day|weekday\(\))", q2):
                topildi.append(f"{nom} = utcnow(): {q2.strip()[:90]}")
                break
    return topildi


for nom in ("services.py", "crud.py", "main.py", "production_service.py", "production_routes.py"):
    _kod = fayl(nom)
    _q7 = utc_ozgaruvchi_kalendar(_kod)
    check(f"F7 {nom}: `x = datetime.utcnow()` dan keyin `x.year | month | day | date()` (joriy davr UTC dan) YO'Q",
          len(_kod) > 1000 and not _q7, _q7[:5])
for nom in ("services.py", "crud.py", "main.py"):
    _kod = "\n".join(q.split("#", 1)[0] for q in fayl(nom).split("\n"))
    _q8 = re.findall(r"(?:datetime|_dt\w*)\([^()]*23,\s*59,\s*59\)", _kod)
    check(f"F8 {nom}: oy oxiri UTC `datetime(yil, oy, oxirgi_kun, 23, 59, 59)` bilan YASALMAYDI (Toshkent oralig'i oxiri)",
          len(_kod) > 1000 and not _q8, _q8[:5])
_crud_kod = "\n".join(q.split("#", 1)[0] for q in fayl("crud.py").split("\n"))
_q9 = re.findall(r"effective_year=hire\.year|effective_month=hire\.month", _crud_kod)
check("F9 crud.py: hodim to'lov tarixi boshlanish oyi `hire.year` / `hire.month` (UTC) dan EMAS — `_tashkent_date(hire)` "
      "(create_employee va backfill ikkalasida)", not _q9 and _crud_kod.count("_hire_t = _tashkent_date(hire)") == 2, _q9)
_q7n = utc_ozgaruvchi_kalendar("def f():\n    _h = datetime.utcnow()\n    y = _h.year\n\n\ndef g():\n    n = datetime.utcnow()\n"
                               "    return n - timedelta(days=3)\n")
check("F7n nazorat: o'quvchi o'zgaruvchi orqali UTC davrni topadi (`_h.year`), oddiy vaqt amalini (`n - 3 kun`) EMAS",
      _q7n == ["_h = utcnow(): y = _h.year"], _q7n)
_DB_SRC = fayl("database.py")
check("F2 database.py: Toshkent kun / oy / yil oraliqlari va shartlari bor",
      all(f"def {n}(" in _DB_SRC for n in ("tashkent_kun_oraligi", "tashkent_oy_oraligi", "tashkent_yil_oraligi",
                                           "tashkent_kunida", "tashkent_oyida", "tashkent_yilida")))
_b, _e = (getattr(database, "tashkent_oy_oraligi", lambda *a: (None, None)))(2026, 12)
check("F3 dekabr oralig'i: [30.11 19:00, 31.12 19:00) UTC", (_b, _e) == (datetime(2026, 11, 30, 19, 0),
                                                                     datetime(2026, 12, 31, 19, 0)), [_b, _e])
_kb, _ke = (getattr(database, "tashkent_kun_oraligi", lambda *a: (None, None)))(date(2026, 10, 1))
check("F4 01.10 kuni: [30.09 19:00, 01.10 19:00) UTC", (_kb, _ke) == (datetime(2026, 9, 30, 19, 0),
                                                                  datetime(2026, 10, 1, 19, 0)), [_kb, _ke])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   -", f)
try:
    database.engine.dispose()
except Exception:                          # noqa: BLE001
    pass
if PG_URL:
    try:
        _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass
else:
    try:
        os.remove(_DB)
    except OSError:
        pass
sys.exit(1 if FAIL else 0)
