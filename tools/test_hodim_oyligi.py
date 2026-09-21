#!/usr/bin/env python3
"""
test_hodim_oyligi.py — Moslashuvchan hodim oyligi hisobi.

NEGA BU TEST BOR
----------------
2026-09-20 da (11.2b, 5-qadam — `Employee.gul_rate` ni olib tashlash)
aniqlandi: `services.calculate_monthly_employee_pay` ni — ya'ni HODIMGA
HAQIQATDAN TO'LANADIGAN PULNI hisoblaydigan funksiyani — birorta ham
test qamramas ekan. `gul_rate` ni qidirganda butun `tools/` papkasida
bitta ham mos so'z topilmadi.

Shuning uchun `gul_rate` olib tashlanishidan OLDIN shu qulf yozildi:
u to'lov turlarining har birini raqam bilan qulflaydi va gipsga tegishli
to'lov yo'llari (gips birliklari, qoliplik gul) QAYTIB KELMASLIGINI
kafolatlaydi.

MUHIM QOIDA — DB USTUNI QOLADI
------------------------------
`employees.gul_rate` va `employee_compensation_history.gul_rate` DB
ustunlari ATAYLAB o'chirilmadi (eski yozuvlar buzilmasin uchun), faqat
model/schema e'lonlari olib tashlandi. C bo'limi shu ikkala holatni ham
tekshiradi: ustun BOR bo'lgan bazada ham kod xatosiz ishlashi va eski
qiymat hodim puliga TA'SIR QILMASLIGI shart.

NIMA TEKSHIRILADI
-----------------
  A. To'lov turlari — fixed / sotuvdan% / foydadan% / birlik / qoplama
  B. GIPS BIRLIK QULFI — gips_metr / gips_qop / gips_kg endi 0 beradi
  C. GUL QULFI — gul_rate na modelda, na schemada, na hisobda;
     eski DB ustuni va undagi eski qiymat pulni o'zgartirmaydi
  D. TO'LOV TARIXI — o'tgan oy o'sha paytdagi stavka bilan hisoblanadi
  E. TENANT — boshqa korxona hodimi hisobga qo'shilmaydi

ISHLATISH
---------
    python tools/test_hodim_oyligi.py
"""
import os
import sys
import inspect
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "hodim_oyligi_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import main  # noqa: E402,F401  (jadvallarni yaratadi)
from sqlalchemy import text  # noqa: E402
from database import SessionLocal, engine  # noqa: E402

import crud  # noqa: E402
import services  # noqa: E402
import schemas  # noqa: E402
from production_models import Company  # noqa: E402
from models import Employee, EmployeeCompensationHistory, PayType  # noqa: E402

db = SessionLocal()
A_CID, B_CID = 1, 2
YIL, OY = 2026, 5

OK = FAIL = 0
FAILED = []


def check(label, olingan, kutilgan, atol=0.0001):
    global OK, FAIL
    if isinstance(kutilgan, (int, float)) and not isinstance(kutilgan, bool) \
            and isinstance(olingan, (int, float)) and not isinstance(olingan, bool):
        mos = abs(float(olingan) - float(kutilgan)) <= atol
    else:
        mos = olingan == kutilgan
    if mos:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}  olingan={olingan}  KUTILGAN={kutilgan}")


def check_true(label, cond):
    check(label, bool(cond), True)


def bolim(t):
    print(f"\n{'=' * 62}\n{t}\n{'=' * 62}")


# ── Baza ────────────────────────────────────────────────────────
for cid, nom in ((A_CID, "A_KORXONA"), (B_CID, "B_KORXONA")):
    if not db.query(Company).filter(Company.id == cid).first():
        db.add(Company(id=cid, name=nom))
db.commit()

# ESKI BAZANI TAQLID QILISH — `gul_rate` ustuni HALI BOR bo'lgan holat.
# (Model e'loni olib tashlangani uchun `create_all` bu ustunni endi
# yaratmaydi; jonli bazada esa u turaveradi.)
def _ustun_qosh(jadval):
    """MUHIM: agar modelga `gul_rate` QAYTIB QO'YILSA, `create_all` ustunni
    o'zi yaratadi va `ALTER` "duplicate column" bilan yiqilardi — test esa
    C bo'limiga YETIB BORMASDAN qulab tushardi (ya'ni aniq xabar o'rniga
    tushunarsiz xato). Shuning uchun ustun bor-yo'qligi avval tekshiriladi."""
    import sqlalchemy as _sa
    bor = [c["name"] for c in _sa.inspect(engine).get_columns(jadval)]
    if "gul_rate" not in bor:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {jadval} ADD COLUMN gul_rate NUMERIC(12,2)"))


_ustun_qosh("employees")
_ustun_qosh("employee_compensation_history")

# Hisob uchun kirish qiymatlari — barcha testlarda BIR XIL
DAROMAD = 45_000_000.0
SOF_FOYDA = 20_000_000.0
JAMI_METR = 250.0
JAMI_DONA = 40.0
JAMI_BLOK = 12.0
JAMI_QOPLAMA = 290.0


def hodim(nom, pay_type, cid=A_CID, **kw):
    """Hodim + uning boshlang'ich to'lov tarixi yozuvi 2024-01 ga suriladi.

    MUHIM: `create_employee` tarix yozuvini `hire_date` (standart — BUGUN)
    bo'yicha ochadi. Agar faqat `hire_date` o'zgartirilsa, tarix yozuvi
    2026-09 da qolib ketadi va (2026, 5) so'ralganda
    `get_employee_compensation_for_month` TARIX SHOXIGA umuman kirmasdan
    ZAXIRA yo'lga tushadi — ya'ni testlar jonli tizim ishlatadigan yo'lni
    emas, zaxira yo'lni tekshirgan bo'lardi (2026-09-20 da aynan shu
    kamchilik topildi)."""
    e = crud.create_employee(db, schemas.EmployeeCreate(
        name=nom, pay_type=pay_type, **kw), company_id=cid)
    e.hire_date = datetime(2024, 1, 1)
    for h in db.query(EmployeeCompensationHistory).filter(
            EmployeeCompensationHistory.employee_id == e.id).all():
        h.effective_year, h.effective_month = 2024, 1
    db.commit()
    return e


def oylik(company_id=A_CID, **kw):
    p = dict(daromad=DAROMAD, sof_foyda_before=SOF_FOYDA,
             jami_metr=JAMI_METR, jami_dona=JAMI_DONA, jami_blok=JAMI_BLOK,
             jami_qoplama_birlik=JAMI_QOPLAMA)
    p.update(kw)
    return services.calculate_monthly_employee_pay(
        db, YIL, OY, p["daromad"], p["sof_foyda_before"],
        p["jami_metr"], p["jami_dona"], p["jami_blok"],
        jami_qoplama_birlik=p["jami_qoplama_birlik"], company_id=company_id)


def summa(res, nom):
    for r in res["breakdown"]:
        if r["name"] == nom:
            return r["amount"]
    return None


# ════════════════════════════════════════════════════════════════
bolim("A. TO'LOV TURLARI — har biri raqam bilan qulflanadi")

hodim("A1_Doimiy", "fixed", fixed_amount=3_000_000)
hodim("A2_Sotuvdan", "percent_sales", percent_value=10)
hodim("A3_Foydadan", "percent_profit", percent_value=5)
hodim("A4_Blok", "per_unit", per_unit_rate=50_000, per_unit_type="blok")
hodim("A5_Metr", "per_unit", per_unit_rate=3_000, per_unit_type="metr")
hodim("A6_Dona", "per_unit", per_unit_rate=7_000, per_unit_type="dona")
hodim("A7_Qoplama", "fixed_plus_coating", fixed_amount=2_000_000,
      per_unit_rate=1_000)
hodim("A8_Qoshimcha", "per_unit", per_unit_rate=50_000, per_unit_type="blok",
      extra_monthly=500_000)

r = oylik()
check("A1: doimiy oylik", summa(r, "A1_Doimiy"), 3_000_000)
check("A2: sotuvdan 10% (45 000 000)", summa(r, "A2_Sotuvdan"), 4_500_000)
check("A3: foydadan 5% (20 000 000)", summa(r, "A3_Foydadan"), 1_000_000)
check("A4: 12 blok × 50 000", summa(r, "A4_Blok"), 600_000)
check("A5: 250 metr × 3 000", summa(r, "A5_Metr"), 750_000)
check("A6: 40 dona × 7 000", summa(r, "A6_Dona"), 280_000)
check("A7: 2 000 000 + 290 × 1 000", summa(r, "A7_Qoplama"), 2_290_000)
check("A8: 600 000 + qo'shimcha 500 000", summa(r, "A8_Qoshimcha"), 1_100_000)
check("A9: jami (8 ta hodim)", r["total"], 13_520_000)
check("A10: breakdown'da 8 ta hodim", len(r["breakdown"]), 8)

# ════════════════════════════════════════════════════════════════
bolim("B. GIPS BIRLIK QULFI — 11.2b 4-qadam (gips_metr/qop/kg ketgan)")

# 2026-09-21 (15-band): `create_employee` endi faqat blok/metr/dona ni qabul
# qiladi (noto'g'ri birlik → ValueError / 400). Gips birliklari — faqat
# ESKI yozuvlarda (ilgari yaratilgan) uchraydi, shuning uchun ular aynan
# shunday taqlid qilinadi: hodim to'g'ri birlik bilan yaratilib, keyin
# bazadagi qiymat (hodim + tarix yozuvi) to'g'ridan-to'g'ri eski birlikka
# almashtiriladi. Tekshirilayotgan narsa o'zgarmadi: bunday eski yozuv
# oylik hisobiga UMUMAN kirmasligi.
for kod in ("gips_metr", "gips_qop", "gips_kg"):
    e = hodim(f"B_{kod}", "per_unit", per_unit_rate=9_999, per_unit_type="blok")
    e.per_unit_type = kod
    for h in db.query(EmployeeCompensationHistory).filter(
            EmployeeCompensationHistory.employee_id == e.id).all():
        h.per_unit_type = kod
    db.commit()
_eski = db.query(Employee).filter(Employee.name.like("B_gips_%")).all()
check("B0: 3 ta eski gips birlikli hodim bazada (taqlid to'g'ri)",
      sorted(x.per_unit_type for x in _eski), ["gips_kg", "gips_metr", "gips_qop"])
try:
    crud.create_employee(db, schemas.EmployeeCreate(
        name="B_gips_yangi", pay_type="per_unit", per_unit_rate=1, per_unit_type="gips_metr"),
        company_id=A_CID)
    _rad = False
except ValueError:
    db.rollback()
    _rad = True
check("B0b: yangi hodimni gips birligi bilan yaratish endi rad etiladi", _rad, True)
r = oylik()
for kod in ("gips_metr", "gips_qop", "gips_kg"):
    check(f"B: per_unit_type='{kod}' → hisobga umuman kirmaydi",
          summa(r, f"B_{kod}"), None)
check("B4: jami o'zgarmadi (gips birliklari 0 beradi)", r["total"], 13_520_000)

# ════════════════════════════════════════════════════════════════
bolim("C. GUL QULFI — gul_rate butunlay ketdi, DB ustuni esa QOLDI")

check("C1: Employee modelida `gul_rate` yo'q",
      hasattr(Employee, "gul_rate"), False)
check("C2: EmployeeCompensationHistory'da `gul_rate` yo'q",
      hasattr(EmployeeCompensationHistory, "gul_rate"), False)
check("C3: EmployeeCreate schemasida `gul_rate` yo'q",
      "gul_rate" in schemas.EmployeeCreate.model_fields, False)
check("C4: EmployeeUpdate schemasida `gul_rate` yo'q",
      "gul_rate" in schemas.EmployeeUpdate.model_fields, False)

_sig = inspect.signature(services.calculate_monthly_employee_pay).parameters
check("C5: calculate_monthly_employee_pay'da `jami_gips_gul` parametri yo'q",
      "jami_gips_gul" in _sig, False)

_e1 = db.query(Employee).filter(Employee.name == "A1_Doimiy").first()
comp = crud.get_employee_compensation_for_month(db, _e1.id, YIL, OY)
check("C6: comp lug'atida (tarixdan) `gul_rate` kaliti yo'q",
      "gul_rate" in comp, False)
check("C6b: comp lug'ati boshqa maydonlarni beraveradi",
      float(comp["fixed_amount"]), 3_000_000)

# Tarixi YO'Q hodim — zaxira yo'l (Employee jadvalidan o'qish)
_hist = db.query(EmployeeCompensationHistory).filter(
    EmployeeCompensationHistory.employee_id == _e1.id).all()
for h in _hist:
    db.delete(h)
db.commit()
comp2 = crud.get_employee_compensation_for_month(db, _e1.id, YIL, OY)
check("C7: zaxira yo'lda ham `gul_rate` kaliti yo'q", "gul_rate" in comp2, False)
check("C7b: zaxira yo'l to'g'ri qiymat beradi",
      float(comp2["fixed_amount"]), 3_000_000)

# `gul_rate` bilan chaqirish — endi TypeError bo'lishi kerak
try:
    services.calculate_monthly_employee_pay(
        db, YIL, OY, DAROMAD, SOF_FOYDA, JAMI_METR, JAMI_DONA, JAMI_BLOK,
        jami_gips_gul=100.0, company_id=A_CID)
    check("C8: `jami_gips_gul=` bilan chaqirish rad etiladi", False, True)
except TypeError:
    check("C8: `jami_gips_gul=` bilan chaqirish rad etiladi", True, True)

# DB ustuni HALI BOR — ORM uni o'qimaydi ham, yozmaydi ham
_cols = [c["name"] for c in __import__("sqlalchemy").inspect(engine).get_columns("employees")]
check("C9: DB ustuni `employees.gul_rate` ATAYLAB saqlanib qoldi",
      "gul_rate" in _cols, True)

_yangi = hodim("C_Yangi", "fixed", fixed_amount=1_000_000)
check("C10: ustun bor bazada ham hodim xatosiz yaratiladi", _yangi.id is not None, True)
with engine.begin() as conn:
    _v = conn.execute(text("SELECT gul_rate FROM employees WHERE id=:i"),
                      {"i": _yangi.id}).scalar()
check("C11: yangi yozuvda `gul_rate` bo'sh (ORM yozmaydi)", _v, None)

# ESKI yozuvda qiymat BOR bo'lsa ham — pul o'zgarmasligi SHART
with engine.begin() as conn:
    conn.execute(text("UPDATE employees SET gul_rate=99999 WHERE name='A6_Dona'"))
db.expire_all()
r = oylik()
check("C12: eski `gul_rate=99999` qiymati donali hodim puliga TA'SIR QILMAYDI",
      summa(r, "A6_Dona"), 280_000)
check("C13: eski `gul_rate` qiymati jamiga ham ta'sir qilmaydi",
      r["total"], 13_520_000 + 1_000_000)

# To'lov tarixi yozuvida ham
with engine.begin() as conn:
    conn.execute(text("UPDATE employee_compensation_history SET gul_rate=77777"))
db.expire_all()
r = oylik()
check("C14: tarixdagi `gul_rate` ham pulni o'zgartirmaydi",
      r["total"], 14_520_000)

# Kodda gul qolmaganini to'g'ridan-to'g'ri tekshirish
_kod = ""
for f in ("services.py", "crud.py", "main.py", "schemas.py"):
    with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
        for satr in fh:
            s = satr.strip()
            if s.startswith("#"):
                continue          # izohlar hisobga olinmaydi
            _kod += s + "\n"
check("C15: services/crud/main/schemas kodida `gul_rate` qolmadi",
      "gul_rate" in _kod, False)
check("C16: kodda `jami_gips_gul` qolmadi", "jami_gips_gul" in _kod, False)

with open(os.path.join(ROOT, "templates", "kpi.html"), encoding="utf-8") as fh:
    _kpi = fh.read()
check("C17: kpi.html da `gul_rate` qolmadi", "gul_rate" in _kpi, False)
check("C18: kpi.html da `e-gulrate` maydoni qolmadi", "e-gulrate" in _kpi, False)

# ════════════════════════════════════════════════════════════════
bolim("D. TO'LOV TARIXI — o'tgan oy o'sha paytdagi stavka bilan")

_a1 = db.query(Employee).filter(Employee.name == "A1_Doimiy").first()
db.add(EmployeeCompensationHistory(
    employee_id=_a1.id, effective_year=2024, effective_month=1,
    pay_type=PayType.FIXED, fixed_amount=1_500_000))
db.add(EmployeeCompensationHistory(
    employee_id=_a1.id, effective_year=YIL, effective_month=OY,
    pay_type=PayType.FIXED, fixed_amount=3_000_000))
db.commit()

r_eski = oylik()
check("D1: joriy oyda yangi stavka (3 000 000)", summa(r_eski, "A1_Doimiy"), 3_000_000)

r_old = services.calculate_monthly_employee_pay(
    db, YIL, OY - 1, DAROMAD, SOF_FOYDA, JAMI_METR, JAMI_DONA, JAMI_BLOK,
    jami_qoplama_birlik=JAMI_QOPLAMA, company_id=A_CID)
check("D2: o'tgan oyda ESKI stavka (1 500 000)", summa(r_old, "A1_Doimiy"), 1_500_000)

_a1.hire_date = datetime(YIL, OY, 1)
db.commit()
r_h = services.calculate_monthly_employee_pay(
    db, YIL, OY - 1, DAROMAD, SOF_FOYDA, JAMI_METR, JAMI_DONA, JAMI_BLOK,
    jami_qoplama_birlik=JAMI_QOPLAMA, company_id=A_CID)
check("D3: ishga kirishdan OLDINGI oy uchun hisoblanmaydi",
      summa(r_h, "A1_Doimiy"), None)
_a1.hire_date = datetime(2024, 1, 1)
db.commit()

# ════════════════════════════════════════════════════════════════
bolim("E. TENANT — boshqa korxona hodimi qo'shilmaydi")

hodim("E1_B_korxona", "fixed", cid=B_CID, fixed_amount=9_000_000)
r_a = oylik(company_id=A_CID)
check("E1: B korxona hodimi A ning hisobida YO'Q",
      summa(r_a, "E1_B_korxona"), None)
check("E2: A ning jamisi o'zgarmadi", r_a["total"], 14_520_000)
r_b = oylik(company_id=B_CID)
check("E3: B korxona o'z hodimini ko'radi",
      summa(r_b, "E1_B_korxona"), 9_000_000)
check("E4: B ning hisobida A ning hodimlari yo'q", len(r_b["breakdown"]), 1)

# ════════════════════════════════════════════════════════════════
bolim("F. ISHLAB CHIQARILGAN GIPS — hodim oyligiga HECH QANDAY yo'l bilan kirmaydi")

# 11.2b 5-qadamida qabul qilingan qaror: `get_monthly_report` ichidagi
# `direct_produced` tsiklida `if cat == "gips": continue` SAQLANDI.
# Sabab: gul yig'ish olib tashlangach, `continue` ham o'chirilsa, eski
# `category='gips'` mahsulotlar endi QOPLAMACHI bonusiga tushib ketardi —
# ya'ni gipsni olib tashlash hodim puliga JIM qo'shimcha qo'shib yuborardi.
# Gipsda "qoplama" tushunchasi yo'q. F2 — nazorat testi: xuddi shu
# mahsulot oddiy turkumda bo'lsa, bonus QO'SHILADI (demak test haqiqatan
# ishlayapti, doim 0 qaytarayotgani uchun emas).
from models import FinishedProduct, StockSource  # noqa: E402

_qop = hodim("F_Qoplamachi", "fixed_plus_coating", cid=B_CID,
             fixed_amount=1_000_000, per_unit_rate=1_000)


def _mahsulot(cat):
    fp = FinishedProduct(company_id=B_CID, name=f"F_{cat}", category=cat,
                         unit="dona", quantity=100, produced_quantity=100,
                         source=StockSource.PRODUCED, is_coated=True,
                         created_at=datetime(YIL, OY, 10))
    db.add(fp)
    db.commit()
    rep = services.get_monthly_report(db, YIL, OY, company_id=B_CID)
    xar = rep["hodimlar_moslashuvchan_xarajat"]
    det = [b for b in rep["hodimlar_moslashuvchan_breakdown"]
           if b["name"] == "F_Qoplamachi"]
    db.delete(fp)
    db.commit()
    return xar, (det[0]["amount"] if det else None)


_x_gips, _a_gips = _mahsulot("gips")
check("F1: gips mahsuloti — qoplamachi bonusi 0 (faqat oylik)",
      _a_gips, 1_000_000)
_x_dona, _a_dona = _mahsulot("dona")
check("F2: NAZORAT — oddiy 'dona' mahsulot bonusni QO'SHADI (100 × 1 000)",
      _a_dona, 1_100_000)
check("F3: gips mahsuloti jami hodim xarajatini oshirmaydi",
      _x_gips, _x_dona - 100_000)

# ════════════════════════════════════════════════════════════════
print(f"\n{'=' * 62}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print(f"{'=' * 62}\nYIQILGANLAR:")
    for f in FAILED:
        print(f"  - {f}")
print(f"{'=' * 62}")
sys.exit(1 if FAIL else 0)
