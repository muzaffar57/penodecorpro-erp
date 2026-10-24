#!/usr/bin/env python3
"""
test_oylik_tafsilot188.py — kech147 (zip 188): hodim oyligi TAFSILOTI matni (KPI → «Oylik hisob-kitob», Qarzdorlar → «Hodimlarga qarzimiz»).

NIMA UCHUN KERAK (egasining PRODUCTION skrinshoti 16.10 21:57 — qoplamachi Jurabek kartasi):
  «Oylik 1 500 000 + 1081.02 metr/dona × 1 000 = 1 081 020»
  (1) miqdor nuqtali kasr va ming ajratgichsiz — dasturning yagona son ko'rinishi (U-05, `services.son_korinish` / brauzerda `sonKor`):
      «1 081,02»;
  (2) «= 1 081 020» butun oylikka o'xshardi — aslida qoplama qismi (jami «Asosiy hisob» ustunida): endi qoplama qismi QAVSDA;
  (3) raqam qator oxirida «1 | 081 020» bo'linardi — ming ajratgich oddiy bo'shliq edi; endi bo'linmas bo'shliq (U+00A0).
«Birlik uchun» (per_unit) tafsiloti ham: «1234.5 blok × 12 500» → «1 234,5 blok × 12 500»; kasrli stavka yaxlitlanmaydi («3 000,5»).
Tafsilotdagi HAMMA son bir qoidada (sotuv / foyda foizi, qo'shimcha oylik, kamaytirish, bonus); Qarzdorlar «Hodimlarga qarzimiz»
qatoridagi «— jami …, avans …» — `|son(0)`; endi ishlatilmaydigan `services.fmt_num` (oddiy bo'shliq) olib tashlangan.
Hisoblangan SUMMA o'zgarmaydi (faqat matn) — har holatda summa ham tekshiriladi.
Asl kodga (zip 187) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_oylik_tafsilot188.py
"""
import os
import re
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_T = tempfile.mkdtemp(prefix="tafsilot188_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tafsilot188.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402
with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402,F401  (jadvallarni yaratadi)
import crud                                        # noqa: E402
import services                                    # noqa: E402
import schemas                                     # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import EmployeeCompensationHistory, EmployeeMonthlyAdjustment     # noqa: E402

OK = FAIL = 0
FAILED = []
NB = "\u00a0"
CID, YIL, OY = 1, 2026, 5


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:600]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    return open(os.path.join(ROOT, yol), encoding="utf-8").read()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik: tafsilot `son_korinish` bilan, qoplama qismi qavsda")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_S = oqi("services.py")
check("S1 «Oylik + qoplama»: oylik / miqdor / stavka / natija — `son_korinish` (pul — butun so'm), qoplama qismi qavsda (`{jami_qoplama_birlik:g}` yo'q)",
      'detail = f"Oylik {son_korinish(base, 0)} + ({son_korinish(jami_qoplama_birlik)} metr/dona × {son_korinish(rate)} = {son_korinish(bonus, 0)})"' in _S
      and "{jami_qoplama_birlik:g}" not in _S)
check("S2 «Birlik uchun»: miqdor va stavka — `son_korinish` (`{qty:g}` yo'q)",
      # kech155 (zip 211c, MOSLANDI): kesilgan blok aniq — miqdor 3 xonagacha («1,125 blok × 100 000»)
      'detail = f"{son_korinish(qty, 3)} {c_unit_type} × {son_korinish(c_unit_rate)}"' in _S and 'f"{qty:g} {c_unit_type}' not in _S)
check("S3 sotuv / foyda foizi: summa — `son_korinish(…, 0)`, foiz — `son_korinish` («2.0%» emas)",
      'detail = f"Sotuv {son_korinish(daromad, 0)} × {son_korinish(c_percent)}%"' in _S
      and 'detail = f"Foyda {son_korinish(sof_foyda_before, 0)} × {son_korinish(c_percent)}%"' in _S)
check("S4 qo'shimcha oylik, kamaytirish, bonus — `son_korinish(…, 0)`",
      'extra_txt = f"qo\'shimcha oylik {son_korinish(c_extra_monthly, 0)}"' in _S
      and 'adj_txt = f"− {son_korinish(adjustment, 0)} (kamaytirish' in _S and 'bonus_txt = f"+ {son_korinish(bonus, 0)} (bonus' in _S)
check("S5 `fmt_num` (oddiy bo'shliqli ko'rinish) olib tashlangan — hech qayerda yo'q (services.py, shablonlar)",
      "fmt_num" not in _S and not any("fmt_num" in oqi(os.path.join("templates", f)) for f in os.listdir(os.path.join(ROOT, "templates"))
                                     if f.endswith(".html")))
_DB = oqi("templates/debts.html")
check("S6 Qarzdorlar «Hodimlarga qarzimiz»: «— jami …, avans …» — `|son(0)` (bo'linmas bo'shliq)",
      "— jami {{ e.amount|son(0) }}, avans {{ e.avans|son(0) }}</div>" in _DB
      and '— jami {{ "{:,.0f}".format(e.amount).replace(",", " ") }}' not in _DB)
check("S7 `|son(0)` filtri: 2 581 020,4 → «2 581 020» (bo'linmas bo'shliq), 0 → «0»",
      main.templates.env.filters["son"](2_581_020.4, 0) == f"2{NB}581{NB}020" and main.templates.env.filters["son"](0, 0) == "0")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Tafsilot matni va summa (`services.calculate_monthly_employee_pay`)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
db = SessionLocal()
if not db.query(Company).filter(Company.id == CID).first():
    db.add(Company(id=CID, name="Andijon Fasad Dekor Elementlari"))
    db.commit()


def hodim(nom, pay_type, **kw):
    """Hodim va uning to'lov tarixi yozuvi 2024-01 dan (test_hodim_oyligi.py bilan bir usul — tarix shoxi tekshiriladi)."""
    e = crud.create_employee(db, schemas.EmployeeCreate(name=nom, pay_type=pay_type, **kw), company_id=CID)
    e.hire_date = datetime(2024, 1, 1)
    for h in db.query(EmployeeCompensationHistory).filter(EmployeeCompensationHistory.employee_id == e.id).all():
        h.effective_year, h.effective_month = 2024, 1
    db.commit()
    return e


with contextlib.redirect_stdout(io.StringIO()):
    hodim("Q_Jurabek", "fixed_plus_coating", fixed_amount=1_500_000, per_unit_rate=1_000)
    hodim("B_Kesuvchi", "per_unit", per_unit_rate=12_500, per_unit_type="blok")
    hodim("M_Metrchi", "per_unit", per_unit_rate=3_000.5, per_unit_type="metr")
    hodim("D_Donachi", "per_unit", per_unit_rate=7_000, per_unit_type="dona", extra_monthly=500_000)
    hodim("K_Kichik", "fixed_plus_coating", fixed_amount=900_000, per_unit_rate=1_000)
    hodim("P_Sotuvdan", "percent_sales", percent_value=2)
    hodim("F_Foydadan", "percent_profit", percent_value=5)
    _t = hodim("T_Tuzatishli", "fixed", fixed_amount=3_000_000)
    db.add(EmployeeMonthlyAdjustment(employee_id=_t.id, year=YIL, month=OY, reduction_amount=250_000, reason="kelmagan 2 kun",
                                     bonus_amount=1_234_567, bonus_reason="yaxshi ish"))
    db.commit()
    r = services.calculate_monthly_employee_pay(db, YIL, OY, 45_000_000.0, 20_000_000.0, 250.0, 40.0, 1_234.5,
                                                jami_qoplama_birlik=1_081.02, company_id=CID)
B = {x["name"]: x for x in r["breakdown"]}


def tafsilot(nom):
    return (B.get(nom) or {}).get("detail")


def summa(nom):
    return (B.get(nom) or {}).get("amount")


_J = tafsilot("Q_Jurabek")
check("T1 «Oylik + qoplama» (production dagi holat): «Oylik 1 500 000 + (1 081,02 metr/dona × 1 000 = 1 081 020)» — bo'linmas bo'shliq bilan",
      _J == f"Oylik 1{NB}500{NB}000 + (1{NB}081,02 metr/dona × 1{NB}000 = 1{NB}081{NB}020)", repr(_J))
check("T2 summa o'zgarmadi: 1 500 000 + 1 081,02 × 1 000 = 2 581 020", abs((summa("Q_Jurabek") or 0) - 2_581_020) < 0.01, summa("Q_Jurabek"))
_B = tafsilot("B_Kesuvchi")
check("T3 «Birlik uchun» (blok): «1 234,5 blok × 12 500»", _B == f"1{NB}234,5 blok × 12{NB}500", repr(_B))
check("T4 summa o'zgarmadi: 1 234,5 × 12 500 = 15 431 250", abs((summa("B_Kesuvchi") or 0) - 15_431_250) < 0.01, summa("B_Kesuvchi"))
_M = tafsilot("M_Metrchi")
check("T5 «Birlik uchun» (metr, kasrli stavka): «250 metr × 3 000,5» (ilgari stavka «3 000» — yaxlitlangan ko'rinardi)",
      _M == f"250 metr × 3{NB}000,5", repr(_M))
check("T6 summa: 250 × 3 000,5 = 750 125", abs((summa("M_Metrchi") or 0) - 750_125) < 0.01, summa("M_Metrchi"))
_D = tafsilot("D_Donachi")
check("T7 qo'shimcha oylikli «Birlik uchun» (dona): «40 dona × 7 000 + qo'shimcha oylik 500 000»",
      _D == f"40 dona × 7{NB}000 + qo'shimcha oylik 500{NB}000", repr(_D))
check("T8 summa: 40 × 7 000 + 500 000 = 780 000", abs((summa("D_Donachi") or 0) - 780_000) < 0.01, summa("D_Donachi"))
_K = tafsilot("K_Kichik")
check("T9 kichik oylik: «Oylik 900 000 + (1 081,02 metr/dona × 1 000 = 1 081 020)»",
      _K == f"Oylik 900{NB}000 + (1{NB}081,02 metr/dona × 1{NB}000 = 1{NB}081{NB}020)", repr(_K))
_P = tafsilot("P_Sotuvdan")
check("T10 «Sotuvdan foiz»: «Sotuv 45 000 000 × 2%» (ilgari «… × 2.0%», oddiy bo'shliq)", _P == f"Sotuv 45{NB}000{NB}000 × 2%", repr(_P))
check("T11 summa: 45 000 000 × 2 % = 900 000", abs((summa("P_Sotuvdan") or 0) - 900_000) < 0.01, summa("P_Sotuvdan"))
_F = tafsilot("F_Foydadan")
check("T12 «Foydadan foiz»: «Foyda 20 000 000 × 5%»", _F == f"Foyda 20{NB}000{NB}000 × 5%", repr(_F))
check("T13 summa: 20 000 000 × 5 % = 1 000 000", abs((summa("F_Foydadan") or 0) - 1_000_000) < 0.01, summa("F_Foydadan"))
import ruxsatlar                                   # noqa: E402
check("T14 tannarx ruxsatisiz ko'rinish (`foyda_yashir`) yangi matnda ham ishlaydi: «Foyda — × 5%»; Jinja filtri ham",
      main.templates.env.filters["foyda_yashir"](_F) == "Foyda — × 5%" and ruxsatlar.foyda_matni_yashir(_F) == "Foyda — × 5%",
      main.templates.env.filters["foyda_yashir"](_F))
_U = tafsilot("T_Tuzatishli")
check("T15 kamaytirish va bonus: «Doimiy oylik − 250 000 (kamaytirish: kelmagan 2 kun) + 1 234 567 (bonus: yaxshi ish)»",
      _U == f"Doimiy oylik − 250{NB}000 (kamaytirish: kelmagan 2 kun) + 1{NB}234{NB}567 (bonus: yaxshi ish)", repr(_U))
check("T16 summa: 3 000 000 − 250 000 + 1 234 567 = 3 984 567", abs((summa("T_Tuzatishli") or 0) - 3_984_567) < 0.01, summa("T_Tuzatishli"))
_hamma = [t for t in (_J, _B, _M, _D, _K, _P, _F, _U) if t]
check("T17 tafsilotlarda raqam ichida oddiy bo'shliq yo'q (qator oxirida «1 | 081 020» bo'linmaydi), nuqtali kasr yo'q",
      len(_hamma) == 8 and not any(re.search(r"\d \d", t) or re.search(r"\d\.\d", t) for t in _hamma), _hamma)
db.close()

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
