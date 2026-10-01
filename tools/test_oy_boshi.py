#!/usr/bin/env python3
"""
test_oy_boshi.py — kech119 darvozasi (2026-10-01): Hisobotlar «oy boshi» xatolari va «Foyda tahlili» matnlari.

O'LCHANGAN (sinov sayti, 01.10.2026 — oyning 1-kuni, asl kod staging 6e1c6be):
  K119-1 «Oy oxirigacha taxmin» — «Taxminiy sof foyda −573 500 000 so'm»: oyning boshida butun oylik (18,5 mln — doimiy
         oylik) yozilgan, `services.get_simple_forecast` uni ham kunlik o'rtachaga qo'shib oy kunlariga ko'paytirardi
         (−18,5 mln ÷ 1 × 31). Oy davomida ham noto'g'ri: 10-kuni sof foyda −8,5 mln bo'lsa taxmin −26,35 mln (to'g'risi
         (−8,5 + 18,5) ÷ 10 × 31 − 18,5 = +12,5 mln).
  K119-2 «O'tgan oy bilan taqqoslash» / «Oy xulosasi» — «Daromad o'tgan oyga nisbatan 100% kamaydi»: 1 kunlik oktabr
         butun sentabr bilan solishtirilardi. Egasi QARORI (01.10, tugmali savol): «Shu kunlar bilan» — 1–N oktabr ↔
         1–N sentabr (`database.tashkent_oy_kesimi`; Moliya «Yo'nalishlar» solishtirishi ham — bir qoida).
  G2-15  «Foyda tahlili» tafsilotida server matni «572,947 so'm/m³» (vergul — ming ajratgich, aslida 572 947), «0.02 m³»,
         «200.0 kg» (nuqtali kasr); B bosqichi U-05 qoidasi serverdagi matnga ham — `services.son_korinish` (= Jinja
         `|son` = brauzer `sonKor`).

BO'LIMLAR: K — oy kesimi (`database`); S — solishtirish (`get_monthly_comparison`); B — bashorat
(`get_simple_forecast`); Y — Moliya yo'nalishlari solishtirishi (`calculate_split_profit_report`); H — HTTP; F — foyda
tafsiloti matni; T — statik. Sahifa (JS) — `tools/test_oy_boshi_ui.js`.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16.
ASL kodga qarshi (staging 6e1c6be) — yiqiladi, QULAMAYDI (yangi nomlar `getattr`, HTTP xatosi → 599).
ISHLATISH: python3 tools/test_oy_boshi.py   |   PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_oy_boshi.py
"""
import os
import re
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "oy_boshi_test"
_T = tempfile.mkdtemp(prefix="oy_boshi_")
_DB = os.path.join(_T, "oy_boshi_test.db")

if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
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

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
    import database                                # noqa: E402

import models as M                                 # noqa: E402
from database import SessionLocal                  # noqa: E402
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
        print(f"  ✗ {label}   {str(detail)[:600]}")


def section(t):
    print(f"\n=== {t} ===")


class _Xato:
    status_code = 599

    def __init__(self, e):
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return None


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


def chaqir(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return {"__xato__": f"{type(e).__name__}: {e}"}


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


def taxminan(a, b, eps=0.51):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


# «Bugun» (Toshkent) — `services._tashkent_date` almashtiriladi (solishtirish va bashorat shundan o'qiydi)
_ASL_BUGUN = services._tashkent_date


def bugun(d):
    services._tashkent_date = (lambda: d)


# ══════════════════════════════════════════════════════════════
# Fikstura (korxona 1): sentabr va oktabr 2026
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k119_admin", "Parol123!", M.UserRole.ADMIN, "K119 Admin", company_id=1)
PRJ = M.Project(company_id=1, client_name="K119 Mijoz", project_name="K119 loyiha", total_budget=0, total_paid=0)
s.add(PRJ)
s.commit()


def buyurtma(raqam, summa, qachon):
    o = M.Order(company_id=1, project_id=PRJ.id, order_number=f"K119-{raqam}", order_type=M.OrderType.PRODUCT,
                status=M.OrderStatus.READY, total_amount=summa, agreed_amount=summa, completed_at=qachon,
                created_at=qachon)
    s.add(o)
    s.commit()
    return o


# UTC vaqtlar: 06:00 UTC = 11:00 Toshkent. 10-sentabr 18:30 UTC = 23:30 Toshkent (10-kun ICHIDA);
# 10-sentabr 19:30 UTC = 11-sentabr 00:30 Toshkent (10-kundan TASHQARI) — kesim chegarasi.
buyurtma(1, 1_000_000, datetime(2026, 9, 5, 6, 0))
buyurtma(2, 200_000, datetime(2026, 9, 10, 18, 30))
buyurtma(3, 70_000, datetime(2026, 9, 10, 19, 30))
buyurtma(4, 3_000_000, datetime(2026, 9, 20, 6, 0))
buyurtma(5, 500_000, datetime(2026, 10, 3, 6, 0))
# Xarajatlar (faqat sana — 00:00): sentabr «boshqa» 4-kun (ichida) va 25-kun (tashqarida); oktabr arenda (oylik), tushlik (kunlik)
for _kat, _summa, _sana in (("boshqa", 100_000, datetime(2026, 9, 4)), ("boshqa", 300_000, datetime(2026, 9, 25)),
                            ("arenda", 2_000_000, datetime(2026, 10, 1)), ("tushlik", 50_000, datetime(2026, 10, 2))):
    s.add(M.ExpenseTransaction(company_id=1, category=_kat, amount=_summa, date=_sana))
# Hodimlar: doimiy 1 000 000; sotuvdan 10 % (o'zgaruvchan); doimiy + qoplama 500 000 (qoplama bonusi — o'zgaruvchan);
# doimiy 400 000 — 15-sentabrda ishga kirgan (1–10-sentabrda YO'Q)
for _ism, _tur, _kw, _kirgan in (
        ("K119 Doimiy", M.PayType.FIXED, {"fixed_amount": 1_000_000}, datetime(2026, 1, 1)),
        ("K119 Sotuvdan", M.PayType.PERCENT_SALES, {"percent_value": 10.0}, datetime(2026, 1, 1)),
        ("K119 Qoplamachi", M.PayType.FIXED_PLUS_COATING, {"fixed_amount": 500_000, "per_unit_rate": 1000},
         datetime(2026, 1, 1)),
        ("K119 Yangi", M.PayType.FIXED, {"fixed_amount": 400_000}, datetime(2026, 9, 15, 6, 0))):
    s.add(M.Employee(company_id=1, name=_ism, pay_type=_tur, hire_date=_kirgan, **_kw))
s.commit()

# Kutilgan (qo'lda hisoblangan):
#   1–10-sentabr: daromad 1 000 000 + 200 000 = 1 200 000; xarajat = 1 000 000 + 10 % × 1 200 000 + 500 000 + 100 000
#                 = 1 720 000 («K119 Yangi» hali ishga kirmagan, 25-sentabr xarajati — tashqarida)
#   butun sentabr: daromad 4 270 000; xarajat = 1 000 000 + 427 000 + 500 000 + 400 000 + 400 000 = 2 727 000
#   oktabr (10-kun, butun oy hisoboti): daromad 500 000; xarajat = 2 000 000 + 50 000 + 1 000 000 + 50 000 + 500 000
#                 + 400 000 = 4 000 000; sof foyda −3 500 000
SEN_10 = {"daromad": 1_200_000, "jami_xarajat": 1_720_000}
SEN_TOLIQ = {"daromad": 4_270_000, "jami_xarajat": 2_727_000}
OKT = {"daromad": 500_000, "jami_xarajat": 4_000_000, "sof_foyda": -3_500_000}

_kesim = getattr(database, "tashkent_oy_kesimi", None)
TSHKENT_SEP = database.tashkent_oy_oraligi(2026, 9)

# ══════════════════════════════════════════════════════════════
section("K — oy kesimi (database.tashkent_oy_kesimi)")
# ══════════════════════════════════════════════════════════════
check("K0 `database.tashkent_oy_kesimi` bor", callable(_kesim), _kesim)
check("K1 kesimsiz: sentabr = [31.08 19:00, 30.09 19:00) UTC",
      TSHKENT_SEP == (datetime(2026, 8, 31, 19, 0), datetime(2026, 9, 30, 19, 0)), TSHKENT_SEP)
if callable(_kesim):
    with _kesim(2026, 9, 10):
        _k_ich = database.tashkent_oy_oraligi(2026, 9)
        _k_okt = database.tashkent_oy_oraligi(2026, 10)
    check("K2 kesim (10-kun): sentabr oxiri — 10-sentabr 24:00 Toshkent (19:00 UTC)",
          _k_ich == (datetime(2026, 8, 31, 19, 0), datetime(2026, 9, 10, 19, 0)), _k_ich)
    check("K3 kesim FAQAT o'sha oyga: oktabr — to'liq", _k_okt == database.tashkent_oy_oraligi(2026, 10), _k_okt)
    with _kesim(2026, 9, 10):
        _k_2025 = database.tashkent_oy_oraligi(2025, 9)
    check("K3b kesim FAQAT o'sha YILga: 2025-sentabr — to'liq", _k_2025 == (datetime(2025, 8, 31, 19, 0), datetime(2025, 9, 30, 19, 0)),
          _k_2025)
    check("K4 blokdan keyin — to'liq oy (qiymat tiklandi)", database.tashkent_oy_oraligi(2026, 9) == TSHKENT_SEP)
    with _kesim(2026, 9, 30):
        _k30 = database.tashkent_oy_oraligi(2026, 9)
    with _kesim(2026, 9, 31):
        _k31 = database.tashkent_oy_oraligi(2026, 9)
    check("K5 kun ≥ oy uzunligi — butun oy (oy oxiridan oshmaydi)", _k30 == TSHKENT_SEP and _k31 == TSHKENT_SEP,
          (_k30, _k31))
    with _kesim(2026, 9, 0):
        _k0 = database.tashkent_oy_oraligi(2026, 9)
    check("K6 kun 0 — bo'sh davr (boshi = oxiri)", _k0[0] == _k0[1] == datetime(2026, 8, 31, 19, 0), _k0)
    try:
        with _kesim(2026, 9, 5):
            raise RuntimeError("sinov")
    except RuntimeError:
        pass
    check("K7 blok ichida xato bo'lsa ham — qiymat tiklanadi", database.tashkent_oy_oraligi(2026, 9) == TSHKENT_SEP)
    with _kesim(2026, 9, 10):
        with _kesim(2026, 8, 3):
            _ichki_sep = database.tashkent_oy_oraligi(2026, 9)
        _tashqi_sep = database.tashkent_oy_oraligi(2026, 9)
    check("K8 ichma-ich: ichki blok (avgust) — sentabr to'liq; chiqqach tashqi kesim qaytadi",
          _ichki_sep == TSHKENT_SEP and _tashqi_sep[1] == datetime(2026, 9, 10, 19, 0), (_ichki_sep, _tashqi_sep))
    _sq = s.query(M.Order).filter(database.tashkent_oyida(M.Order.completed_at, 2026, 9))
    _hamma = sorted(o.order_number for o in _sq.all())
    with _kesim(2026, 9, 10):
        _kesimli = sorted(o.order_number for o in
                          s.query(M.Order).filter(database.tashkent_oyida(M.Order.completed_at, 2026, 9)).all())
    check("K9 `tashkent_oyida` ham kesimga bo'ysunadi: 23:30 dagi (10-kun) ichida, 00:30 dagi (11-kun) tashqarida",
          _kesimli == ["K119-1", "K119-2"] and _hamma == ["K119-1", "K119-2", "K119-3", "K119-4"], (_kesimli, _hamma))
else:
    for _n in range(2, 10):
        check(f"K{_n} (kesim yo'q — asl kod)", False, "tashkent_oy_kesimi yo'q")

# ══════════════════════════════════════════════════════════════
section("S — solishtirish (services.get_monthly_comparison) — egasi QARORI «Shu kunlar bilan»")
# ══════════════════════════════════════════════════════════════
_rep_okt = services.get_monthly_report(s, 2026, 10, company_id=1)
_rep_sep = services.get_monthly_report(s, 2026, 9, company_id=1)
check("S0 fikstura: oktabr hisoboti = qo'lda hisoblangan (daromad 500 000, xarajat 4 000 000, sof −3 500 000)",
      all(taxminan(_rep_okt[k], v) for k, v in OKT.items()), {k: _rep_okt.get(k) for k in OKT})
check("S0b fikstura: butun sentabr = qo'lda hisoblangan (daromad 4 270 000, xarajat 2 727 000)",
      all(taxminan(_rep_sep[k], v) for k, v in SEN_TOLIQ.items()), {k: _rep_sep.get(k) for k in SEN_TOLIQ})

bugun(date(2026, 10, 10))
_c = chaqir(services.get_monthly_comparison, s, 2026, 10, company_id=1)
_d = (_c or {}).get("davr") or {}
check("S1 10-oktabr: o'tgan oy — 1–10-sentabr (daromad 1 200 000: 23:30 dagi kiradi, 00:30 dagi va 20-sentabr — yo'q)",
      taxminan((_c.get("daromad") or {}).get("previous"), SEN_10["daromad"]), _c.get("daromad"))
check("S2 o'tgan oy xarajati — 1–10-sentabr: 1 720 000 (keyin ishga kirgan hodim va 25-sentabr xarajati — yo'q)",
      taxminan((_c.get("jami_xarajat") or {}).get("previous"), SEN_10["jami_xarajat"]), _c.get("jami_xarajat"))
check("S3 joriy oy — oktabr hisobotining O'ZI (kartadagi raqam bilan AYNAN)",
      all(taxminan((_c.get(k) or {}).get("current"), _rep_okt[k]) for k in ("daromad", "jami_xarajat", "sof_foyda")),
      {k: (_c.get(k) or {}).get("current") for k in ("daromad", "jami_xarajat", "sof_foyda")})
check("S4 o'zgarish foizi shu kunlar bo'yicha: daromad 500 000 ↔ 1 200 000 = −58,3 %, «kamaydi»",
      (_c.get("daromad") or {}).get("change_pct") == -58.3 and (_c.get("daromad") or {}).get("holat") == "kamaydi",
      _c.get("daromad"))
check("S5 davr: kun_gacha 10, toliq_oy False, «1–10-oktabr» ↔ «1–10-sentabr»",
      _d.get("kun_gacha") == 10 and _d.get("toliq_oy") is False and _d.get("joriy_nom") == "1–10-oktabr"
      and _d.get("oldingi_nom") == "1–10-sentabr" and _d.get("oldingi_oy") == 9 and _d.get("oldingi_yil") == 2026, _d)
check("S6 hisobotdan keyin kesim QOLMAYDI (sentabr — to'liq oy)", database.tashkent_oy_oraligi(2026, 9) == TSHKENT_SEP)
_rep_sep2 = services.get_monthly_report(s, 2026, 9, company_id=1)
check("S6b keyingi oddiy sentabr hisoboti — to'liq (daromad 4 270 000)", taxminan(_rep_sep2["daromad"], 4_270_000),
      _rep_sep2["daromad"])

bugun(date(2026, 10, 1))
_c1 = chaqir(services.get_monthly_comparison, s, 2026, 10, company_id=1)
_d1 = (_c1 or {}).get("davr") or {}
check("S7 1-oktabr (sinov saytidagi holat): o'tgan oy — faqat 1-sentabr (daromad 0 → foiz yo'q, «100% kamaydi» EMAS)",
      taxminan((_c1.get("daromad") or {}).get("previous"), 0) and (_c1.get("daromad") or {}).get("change_pct") is None
      and _d1.get("kun_gacha") == 1 and _d1.get("oldingi_nom") == "1-sentabr", (_c1.get("daromad"), _d1))

bugun(date(2026, 10, 31))
_c31 = chaqir(services.get_monthly_comparison, s, 2026, 10, company_id=1)
_d31 = (_c31 or {}).get("davr") or {}
check("S8 31-oktabr: sentabr 30 kunlik — butun sentabr (kesim yo'q), davr «oktabr» ↔ «sentabr»",
      taxminan((_c31.get("daromad") or {}).get("previous"), 4_270_000) and _d31.get("kun_gacha") is None
      and _d31.get("toliq_oy") is True and _d31.get("oldingi_nom") == "sentabr" and _d31.get("joriy_nom") == "oktabr",
      (_c31.get("daromad"), _d31))

bugun(date(2026, 10, 30))
_c30 = chaqir(services.get_monthly_comparison, s, 2026, 10, company_id=1)
check("S8b 30-oktabr: sentabr 30 kunlik — 30 kun = butun oy (kesim yo'q, «o'tgan oyga nisbatan»)",
      ((_c30.get("davr") or {}).get("kun_gacha") is None) and ((_c30.get("davr") or {}).get("toliq_oy") is True),
      _c30.get("davr"))

bugun(date(2026, 10, 29))
_c29 = chaqir(services.get_monthly_comparison, s, 2026, 10, company_id=1)
check("S9 29-oktabr: 1–29-sentabr (hamma sentabr buyurtmalari — 4 270 000; 30-sentabrda yozuv yo'q)",
      taxminan((_c29.get("daromad") or {}).get("previous"), 4_270_000)
      and ((_c29.get("davr") or {}).get("kun_gacha") == 29), (_c29.get("daromad"), _c29.get("davr")))

bugun(date(2026, 10, 10))
_cp = chaqir(services.get_monthly_comparison, s, 2026, 9, company_id=1)
_dp = (_cp or {}).get("davr") or {}
check("S10 o'tgan oy so'ralsa (sentabr, bugun 10-oktabr) — tugagan oy: avgust to'liq, kesimsiz",
      _dp.get("kun_gacha") is None and _dp.get("toliq_oy") is True and _dp.get("oldingi_oy") == 8
      and taxminan((_cp.get("daromad") or {}).get("current"), 4_270_000), (_dp, _cp.get("daromad")))

bugun(date(2026, 9, 30))
_cs = chaqir(services.get_monthly_comparison, s, 2026, 9, company_id=1)
check("S11 30-sentabr ↔ avgust (31 kun): 1–30-avgust (kesim 30)",
      ((_cs.get("davr") or {}).get("kun_gacha") == 30) and ((_cs.get("davr") or {}).get("oldingi_nom") == "1–30-avgust"),
      _cs.get("davr"))

bugun(date(2026, 10, 10))
_cn = chaqir(services.get_monthly_comparison, s, 2026, 10)
check("S12 korxonasiz (eski imzo) chaqiruv — ishlaydi (hamma korxonalar), davr bor",
      isinstance(_cn, dict) and "__xato__" not in _cn and (_cn.get("davr") or {}).get("kun_gacha") == 10, _cn)

# ══════════════════════════════════════════════════════════════
section("B — bashorat (services.get_simple_forecast) — K119-1")
# ══════════════════════════════════════════════════════════════
bugun(date(2026, 10, 10))
_f = chaqir(services.get_simple_forecast, s, 2026, 10, company_id=1)
# oylik (bir marta): arenda 2 000 000 + doimiy 1 000 000 + qoplamachi asosi 500 000 + yangi 400 000 = 3 900 000;
# o'zgaruvchan: daromad, tushlik 50 000, sotuvdan 10 % = 50 000 → sof −3 500 000 + 3 900 000 = 400 000 / 10 kun
_kut = round((OKT["sof_foyda"] + 3_900_000) / 10 * 31 - 3_900_000)
check("B1 oylik xarajat BIR MARTA: doimiy_xarajat = arenda + doimiy oyliklar = 3 900 000 (tushlik, foizli — yo'q)",
      (_f or {}).get("doimiy_xarajat") == 3_900_000, _f)
check(f"B2 taxminiy sof foyda = (sof + oylik) ÷ 10 × 31 − oylik = {_kut} (asl kod: sof ÷ 10 × 31 = "
      f"{round(OKT['sof_foyda'] / 10 * 31)})", (_f or {}).get("forecast_foyda") == _kut, _f)
check("B3 taxminiy daromad — avvalgidek (500 000 ÷ 10 × 31 = 1 550 000); current_* — hisobotning o'zi",
      (_f or {}).get("forecast_daromad") == 1_550_000 and (_f or {}).get("current_foyda") == OKT["sof_foyda"]
      and (_f or {}).get("current_daromad") == OKT["daromad"], _f)

bugun(date(2026, 10, 1))
s2 = SessionLocal()
_f1 = chaqir(services.get_simple_forecast, s2, 2026, 10, company_id=1)
s2.close()
_kut1 = round((OKT["sof_foyda"] + 3_900_000) / 1 * 31 - 3_900_000)
check(f"B4 oyning 1-kuni (sinov saytidagi holat): taxmin = (sof + oylik) × 31 − oylik = {_kut1}, «× 31» "
      f"(asl: {round(OKT['sof_foyda'] * 31)}) EMAS", (_f1 or {}).get("forecast_foyda") == _kut1, _f1)

bugun(date(2026, 10, 10))
_fs = chaqir(services.get_simple_forecast, s, 2026, 9, company_id=1)
check("B5 tugagan oy (sentabr): taxmin = haqiqiy sof foyda (AYNAN)",
      (_fs or {}).get("forecast_foyda") == round(float(_rep_sep["sof_foyda"])) and (_fs or {}).get("days_passed") == 30,
      (_fs, _rep_sep["sof_foyda"]))
_fk = chaqir(services.get_simple_forecast, s, 2026, 11, company_id=1)
check("B6 kelajak oy — «hali ma'lumot yo'q» (avvalgidek)", (_fk or {}).get("available") is False, _fk)
_emp0 = services.calculate_monthly_employee_pay(s, 2026, 10, 0.0, 0.0, 0.0, 0.0, 0.0, jami_qoplama_birlik=0.0,
                                                company_id=1)
_emp1 = services.calculate_monthly_employee_pay(s, 2026, 10, 9_000_000.0, 0.0, 0.0, 0.0, 0.0,
                                                jami_qoplama_birlik=100.0, company_id=1)
check("B7 faoliyatsiz hodim to'lovi = doimiy qism (1 900 000); faoliyat bilan — ko'p (sotuvdan 900 000, qoplama 100 000)",
      _emp0["total"] == 1_900_000 and _emp1["total"] == 1_900_000 + 900_000 + 100_000, (_emp0["total"], _emp1["total"]))

# ══════════════════════════════════════════════════════════════
section("Y — Moliya «Yo'nalishlar» solishtirishi (calculate_split_profit_report) — bir qoida")
# ══════════════════════════════════════════════════════════════
bugun(date(2026, 10, 10))
_y = chaqir(services.calculate_split_profit_report, s, 2026, 10, company_id=1, solishtirish=True)
_yo = (_y or {}).get("oldingi") or {}
check("Y1 10-oktabr, davr oktabr: oldingi — 1–10-sentabr (daromad 1 200 000), nomi «1–10-sentabr 2026»",
      taxminan(_yo.get("daromad"), 1_200_000) and (_yo.get("davr") or {}).get("nom") == "1–10-sentabr 2026"
      and (_yo.get("davr") or {}).get("kun_gacha") == 10, _yo)
_y3 = chaqir(services.calculate_split_profit_report, s, 2026, 8, company_id=1, gacha_yil=2026, gacha_oy=10,
             solishtirish=True)
check("Y2 davr avgust – oktabr: oldingi may – iyul, iyul — 1–10-kun (nomi «May – Iyul 2026 (iyul — 1–10-kun)»)",
      ((_y3 or {}).get("oldingi") or {}).get("davr", {}).get("nom") == "May – Iyul 2026 (iyul — 1–10-kun)",
      ((_y3 or {}).get("oldingi") or {}).get("davr"))
bugun(date(2026, 10, 31))
_y31 = chaqir(services.calculate_split_profit_report, s, 2026, 10, company_id=1, solishtirish=True)
_yo31 = (_y31 or {}).get("oldingi") or {}
check("Y3 31-oktabr: oldingi — butun sentabr (4 270 000), nomi «Sentabr 2026»",
      taxminan(_yo31.get("daromad"), 4_270_000) and (_yo31.get("davr") or {}).get("nom") == "Sentabr 2026", _yo31)
bugun(date(2026, 10, 30))
_y30 = chaqir(services.calculate_split_profit_report, s, 2026, 10, company_id=1, solishtirish=True)
check("Y3b 30-oktabr: 30 kun = butun sentabr — nomi «Sentabr 2026», kun_gacha yo'q",
      (((_y30 or {}).get("oldingi") or {}).get("davr") or {}).get("nom") == "Sentabr 2026"
      and (((_y30 or {}).get("oldingi") or {}).get("davr") or {}).get("kun_gacha") is None, ((_y30 or {}).get("oldingi")))
bugun(date(2026, 10, 10))
_ys = chaqir(services.calculate_split_profit_report, s, 2026, 9, company_id=1, solishtirish=True)
check("Y4 tugagan oy (sentabr) — oldingi avgust to'liq (nomi «Avgust 2026»)",
      ((_ys or {}).get("oldingi") or {}).get("davr", {}).get("nom") == "Avgust 2026", ((_ys or {}).get("oldingi")))
check("Y5 yo'nalishlardan keyin kesim qolmaydi", database.tashkent_oy_oraligi(2026, 9) == TSHKENT_SEP)

# ══════════════════════════════════════════════════════════════
section("H — HTTP")
# ══════════════════════════════════════════════════════════════
bugun(date(2026, 10, 10))
CL = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
req(CL, "post", "/login", data={"username": "k119_admin", "password": "Parol123!"}, follow_redirects=False)
_r = req(CL, "get", "/api/reports/comparison", params={"year": 2026, "month": 10})
_rj = js(_r) or {}
check("H1 /api/reports/comparison — 200, `davr` (1–10-sentabr) va o'tgan oy 1 200 000",
      _r.status_code == 200 and (_rj.get("davr") or {}).get("oldingi_nom") == "1–10-sentabr"
      and taxminan((_rj.get("daromad") or {}).get("previous"), 1_200_000), (_r.status_code, _rj))
_r = req(CL, "get", "/api/reports/forecast", params={"year": 2026, "month": 10})
_rj = js(_r) or {}
check("H2 /api/reports/forecast — 200, doimiy_xarajat 3 900 000, forecast_foyda — yangi qoida",
      _r.status_code == 200 and _rj.get("doimiy_xarajat") == 3_900_000 and _rj.get("forecast_foyda") == _kut,
      (_r.status_code, _rj))
_r = req(CL, "get", "/api/finance/yonalishlar", params={"year": 2026, "month": 10, "solishtirish": "true"})
_rj = js(_r) or {}
check("H3 /api/finance/yonalishlar (solishtirish) — oldingi davr nomi «1–10-sentabr 2026»",
      _r.status_code == 200 and ((_rj.get("oldingi") or {}).get("davr") or {}).get("nom") == "1–10-sentabr 2026",
      (_r.status_code, (_rj.get("oldingi") if isinstance(_rj, dict) else _rj)))

# ══════════════════════════════════════════════════════════════
section("F — «Foyda tahlili» tafsiloti matni (G2-15, U-05)")
# ══════════════════════════════════════════════════════════════
_sk = getattr(services, "son_korinish", None)
_sf = getattr(main, "_son_filtri", None)
_QIY = [(572947.0, 0), (0.02, 2), (0.5, 2), (200.0, 1), (5.26, 1), (2346.4, 0), (1234.5, 2), (-647684.215, 0), (7.5, 1),
        (10.0, 1), (0, 2), (-0.004, 2), (1e6, 0), (None, 2), ("abc", 2), (float("nan"), 2)]
check("F0 `services.son_korinish` bor", callable(_sk), _sk)
check("F1 son_korinish = Jinja `|son` (main._son_filtri) — 16 qiymatda AYNAN (bitta qoida)",
      callable(_sk) and callable(_sf) and all(_sk(x, k) == _sf(x, k) for x, k in _QIY),
      [(x, k, _sk(x, k) if callable(_sk) else None, _sf(x, k)) for x, k in _QIY])
check("F2 namunalar: «572 947», «0,02», «200», «7,5», «-647 685»",
      callable(_sk) and _sk(572947, 0) == "572\u00a0947" and _sk(0.02, 2) == "0,02" and _sk(200.0, 1) == "200"
      and _sk(7.5, 1) == "7,5" and _sk(-647684.6, 0) == "-647\u00a0685", [(_sk(x, k) if callable(_sk) else None)
                                                                           for x, k in ((572947, 0), (0.02, 2))])
# Haqiqiy buyurtma: penoplast (1 m³ — 572 947 so'm), profil 20 × 10 × 1 m (0,01 m³), usta 7,5 % foydadan
PENO = M.Inventory(company_id=1, item_name="K119 Penoplast", unit="blok", stock_quantity=100, price_per_unit=572947,
                   volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
USTA = M.Master(company_id=1, name="K119 Usta", phone="+998900000119", cashback_percent=7.5)
s.add_all([PENO, USTA])
s.commit()
OF = M.Order(company_id=1, project_id=PRJ.id, order_number="K119-F", order_type=M.OrderType.PRODUCT,
             status=M.OrderStatus.IN_PROGRESS, total_amount=100_000, agreed_amount=100_000, master_id=USTA.id)
s.add(OF)
s.commit()
s.add(M.OrderItem(company_id=1, order_id=OF.id, name="K119 profil", category="profil", width=20, thickness=10, length=1,
                  quantity=1, unit_price=100_000, total_price=100_000, is_coated=False, penoplast_id=PENO.id))
s.commit()
_p = chaqir(services.calculate_order_profit, s, OF.id)
_nomlar = [b.get("nomi") for b in ((_p or {}).get("breakdown") or [])]
print("    tafsilot:", _nomlar)
check("F3 penoplast qatori: «K119 Penoplast (0,01 m³ × 572 947 so'm/m³)» (ilgari «0.01 m³ × 572,947»)",
      "K119 Penoplast (0,01 m³ × 572\u00a0947 so'm/m³)" in _nomlar, _nomlar)
check("F4 usta qatori: «Usta haqi (K119 Usta, 7,5% foydadan)» (ilgari «7.5%»)",
      "Usta haqi (K119 Usta, 7,5% foydadan)" in _nomlar, _nomlar)
check("F5 hech bir tafsilot matnida ming ajratgich-vergul («572,947») yoki nuqtali kasr («0.01») yo'q",
      _nomlar and not any(re.search(r"\d,\d{3}\b|\d\.\d", n or "") for n in _nomlar), _nomlar)

# ══════════════════════════════════════════════════════════════
section("T — statik")
# ══════════════════════════════════════════════════════════════
_cop = manba(services, "calculate_order_profit")
check("T1 calculate_order_profit: tafsilot matnlarida `:,.0f` / `:.1f} kg` / `:.2f} m³` qolmagan",
      _cop and ":,.0f}" not in _cop and ":.1f} kg" not in _cop and ":.2f} m³" not in _cop, "")
_fcs = manba(services, "get_simple_forecast")
check("T2 get_simple_forecast: oylik xarajat (FORECAST_OYLIK_TOIFALAR + faoliyatsiz hodim to'lovi) bir marta ayriladi",
      "FORECAST_OYLIK_TOIFALAR" in _fcs and "calculate_monthly_employee_pay" in _fcs and "- doimiy_xarajat" in _fcs, "")
check("T3 FORECAST_OYLIK_TOIFALAR = arenda, elektr, soliqlar (tushlik — kunlik)",
      tuple(getattr(services, "FORECAST_OYLIK_TOIFALAR", ())) == ("arenda", "elektr", "soliqlar"),
      getattr(services, "FORECAST_OYLIK_TOIFALAR", None))
_gmc = manba(services, "get_monthly_comparison")
check("T4 get_monthly_comparison: o'tgan oy — `tashkent_oy_kesimi` bloki ichida, `davr` qaytadi",
      "tashkent_oy_kesimi" in _gmc and '"davr"' in _gmc, "")
_dbs = inspect.getsource(database)
check("T5 database: kesim — FAQAT `tashkent_oy_oraligi` ichida (tashkent_oyida undan foydalanadi)",
      "_OY_KESIMI.get()" in (manba(database, "tashkent_oy_oraligi") or "")
      and "tashkent_oy_oraligi(yil, oy)" in (manba(database, "tashkent_oyida") or ""), "")

services._tashkent_date = _ASL_BUGUN
s.close()
print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
sys.exit(1 if FAIL else 0)
