#!/usr/bin/env python3
"""
test_hisoblar210.py — kech155 (zip 210 «Naqd / Bank / Karta» — egasi so'rovi 23.10 15:56, ko'rinish tasdig'i 16:1x).

NIMA UCHUN KERAK
  «Kassa + bank» bitta umumiy summa edi; kirgan pulning usuli bor edi (mijoz to'lovi, tayyor sotuv), chiqgan pulning — yo'q (xarid,
  ta'minotchiga to'lov, xarajat, transport, avans / oylik, Usta KPI / Ehson). Endi har pul yozuvi qaysi PUL HISOBIDAN (Naqd pul / Bank /
  Karta), hisob qoldig'i = egasi kiritgan HAQIQIY qoldiq + undan keyingi harakatlar, hisoblar orasida o'tkazish, har hisob tarixi.
BO'LIMLAR
  H — hisoblar va qoldiq: standart uchtasi (korxona bo'yicha), qoldiqsiz — avvalgi umumiy hisob, birinchi marta — hamma hisob birga,
      tana qat'iy (noma'lum maydon / bool / manfiy / takror / begona hisob — 400), qoldiqdan keyin «Kassa + bank» = yig'indi, jurnal.
  P — har pul yo'li o'z hisobiga va o'z ishorasi bilan: mijoz to'lovi (naqd / plastik / o'tkazma → Naqd pul / Karta / Bank),
      ortiqcha qaytarish, tayyor sotuv (yakka / guruh), yuk xati (to'lov + kompaniya transporti `transport_hisob`, 50/50 — yarmi),
      yakka xarid (naqd xarid / hoziroq to'lov / o'z hisobimdan transport), kirim hujjati (hoziroq to'lov + qo'shimcha xarajatlar),
      ta'minotchiga to'lov, xarajat (yaratish / tahrirda hisobni almashtirish / hisobsiz — Naqd), kirish transporti API, hodimga avans,
      «oylikni yopish», hodim so'rovini tasdiqlash, Usta KPI / Ehson, qaytarish «pul qaytdi» (usul bilan); noto'g'ri hisob — 400, yozuvsiz.
  T — o'tkazish: ikkala hisob o'zgaradi, jami — yo'q; takror — `duplicate`, bitta yozuv; bir hisob / begona / 0 — 400; o'chirish qaytaradi.
  R — qayta sanash: yangi qoldiq ustun, `dastur_summa` va farq jurnalda; o'chirilsa — oldingisiga; o'tgan kunli xarajat (qoldiqdan keyin
      yozilgan) — sanalmaydi; qoldiq kuni faqat sanali xarajat — yozilgan vaqti bo'yicha sanaladi.
  I — izchillik: qoldiqdan keyingi hisoblar o'zgarishi yig'indisi = bugungi «Pul oqimi» (hammasi bugun); tarix — qoldiq + harakatlar = balans,
      yangisi tepada; zaxira → tiklash (replace) — hisoblar va qoldiqlar AYNAN.
  X — korxonalar: B ning hisoblari alohida, A ning harakati B ga ta'sir qilmaydi; A ning hisob id si B dan — 400 / 404.
  U — HAQIQIY brauzer (Playwright): Moliya kartasi (qoldiqsiz — ogohlantirish; qoldiq oynasi → 3 karta, jami = yig'indi), o'tkazish oynasi,
      hisob tarixi oynasi, Usta KPI oynasidagi tanlov (qoldiq bilan) va saqlash, xarajat oynasi tanlovi; boshqa sahifalarda tanlov bor
      (Ta'minotchilar, Kirim qilish, Kunlik xarajat, Ustalar KPI, Buyurtmalar yuk xati); telefon (390 px) — gorizontal toshish yo'q; tungi rejim.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (U bo'limi faqat SQLite / TF1 da).
Asl kodga (zip 209) qarshi QULAMAYDI — yiqiladi (hisoblar API yo'q).
ISHLATISH: python3 tools/test_hisoblar210.py
"""
import os
import io
import sys
import json
import time
import tempfile
import datetime
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hisoblar210_test"
_T = tempfile.mkdtemp(prefix="k210_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k210.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


_MIG = io.StringIO()
with contextlib.redirect_stdout(_MIG):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, Project, Master, Supplier, Employee, FinishedProduct, StockSource, ProductionStatus, PayType,  # noqa: E402
                    ActivityLog, AdvanceRequest, AdvanceRequestStatus, Payment, ExpenseTransaction, PaymentType, PaymentMethod)
try:                                               # asl kodda (zip 209) yo'q — sinov qulamasin, yiqilsin
    from models import PulHisobi, PulHisobiQoldiq, PulOtkazmasi   # noqa: E402
except ImportError:
    PulHisobi = PulHisobiQoldiq = PulOtkazmasi = None
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="K210 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k210_a", PAROL, UserRole.ADMIN, "K210 Admin", company_id=1)
    auth.create_user(s, "k210_b", PAROL, UserRole.ADMIN, "K210 B Admin", company_id=2)
PENO = Inventory(company_id=1, item_name="K210 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
MAT = Inventory(company_id=1, item_name="K210 Kley", unit="kg", stock_quantity=0, price_per_unit=1_000, category="Xomashyo")
P1 = Project(company_id=1, client_name="Sardor K210", project_name="Andijon K210", client_phone="+998901112210", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K210 Usta", phone="+998900002100")
SUP = Supplier(company_id=1, name="K210 Ta'minotchi")
EMP = Employee(company_id=1, name="K210 Hodim", position="Kesuvchi", pay_type=PayType.FIXED, fixed_amount=5_000_000, is_active=True)
s.add_all([PENO, MAT, P1, US, SUP, EMP])
s.flush()
FP1 = FinishedProduct(company_id=1, name="K210 TM profil", category="profil", quantity=50, produced_quantity=50, unit="metr",
                      unit_price=50000, cost_price=10000, source=StockSource.PRODUCED,
                      production_status=ProductionStatus.READY, is_coated=False)
s.add(FP1)
s.commit()
ID = {"PENO": PENO.id, "MAT": MAT.id, "P1": P1.id, "US": US.id, "SUP": SUP.id, "EMP": EMP.id, "FP1": FP1.id}
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "k210_a", "password": PAROL}, follow_redirects=False)
B = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
B.post("/login", data={"username": "k210_b", "password": PAROL}, follow_redirects=False)
TK = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).date()


def js(r):
    try:
        return r.json()
    except Exception:                   # noqa: BLE001
        return {}


def holat(c=A):
    return js(c.get("/api/finance/hisoblar"))


def bal(c=A):
    b = {"naqd": None, "bank": None, "karta": None}
    b.update({h["turi"]: h["balans"] for h in (holat(c).get("hisoblar") or [])})
    return b


def bosh(x):
    """Bo'shliqlarsiz (oddiy, U+00A0, U+202F) — sahifa matnini solishtirish uchun."""
    return "".join(str(x).replace("\u00a0", " ").replace("\u202f", " ").split())


def farq(oldin, keyin):
    return {k: round((keyin.get(k) or 0) - (oldin.get(k) or 0), 2) for k in ("naqd", "bank", "karta")}


def teng(a, b):
    return all(abs((a.get(k) or 0) - (b.get(k) or 0)) < 0.011 for k in ("naqd", "bank", "karta"))


def jurnal(entity_type, company_id=1):
    _s = SessionLocal()
    try:
        return [(r.action, r.entity_label, r.new_value, r.old_value) for r in
                _s.query(ActivityLog).filter(ActivityLog.entity_type == entity_type, ActivityLog.company_id == company_id)
                .order_by(ActivityLog.id).all()]
    finally:
        _s.close()


def soni(model, **f):
    if model is None:
        return -1
    _s = SessionLocal()
    try:
        q = _s.query(model)
        for k, v in f.items():
            q = q.filter(getattr(model, k) == v)
        return q.count()
    finally:
        _s.close()


def buyurtma(summa=500_000):
    tana = {"project_id": ID["P1"], "order_type": "product", "recipe_id": None, "master_id": ID["US"],
            "deadline": (TK + datetime.timedelta(days=5)).isoformat(), "is_draft": False, "base_price": 600000, "loy_kg": None,
            "items": [{"name": "K210 panel", "category": "panel", "width": 50, "thickness": 5, "length": 10, "quantity": 1,
                       "unit_price": summa, "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None,
                       "finished_product_id": None}]}
    r = A.post("/api/orders?confirm_shortage=true", json=tana)
    return js(r) if r.status_code == 200 else {"_xato": (r.status_code, r.text[:300])}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Hisoblar va qoldiq")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
H0 = holat()
HB = holat(B)
import collections                                # noqa: E402
HID = collections.defaultdict(lambda: 999_991, {h["turi"]: h["id"] for h in H0.get("hisoblar") or []})
HIDB = collections.defaultdict(lambda: 999_992, {h["turi"]: h["id"] for h in HB.get("hisoblar") or []})
check("H1 har korxonada standart uchta hisob: «Naqd pul» / «Bank» / «Karta» (turi naqd / bank / karta), korxonalar alohida (id lar har xil)",
      [(h["nomi"], h["turi"]) for h in H0.get("hisoblar") or []] == [("Naqd pul", "naqd"), ("Bank", "bank"), ("Karta", "karta")]
      and [(h["nomi"], h["turi"]) for h in HB.get("hisoblar") or []] == [("Naqd pul", "naqd"), ("Bank", "bank"), ("Karta", "karta")]
      and not (set(HID.values()) & set(HIDB.values())), (H0, HB))
check("H1b ishga tushishda (migratsiya) standart hisoblar yaratildi — xabar",
      "standart pul hisoblari" in _MIG.getvalue() or soni(PulHisobi, company_id=1) == 3, _MIG.getvalue()[-400:])
_cb0 = js(A.get("/api/finance/cash-balance"))
check("H2 qoldiqsiz: `boshlangan` False, balanslar yo'q; «Kassa + bank» — avvalgi umumiy hisob (`balance` = `eski_balans`), hisoblar ro'yxati bor",
      H0.get("boshlangan") is False and all(h["balans"] is None for h in H0["hisoblar"]) and _cb0.get("hisoblar_boshlangan") is False
      and _cb0.get("balance") == _cb0.get("eski_balans") and len(_cb0.get("hisoblar") or []) == 3, (H0, _cb0))
_r = A.post("/api/finance/hisoblar/qoldiq", json={"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": 1_000_000}]})
check("H3 birinchi marta faqat bitta hisob — 400 (qolganlari nomi bilan), hech narsa yozilmaydi",
      _r.status_code == 400 and "Bank" in js(_r).get("detail", "") and "Karta" in js(_r).get("detail", "")
      and soni(PulHisobiQoldiq, company_id=1) == 0, (_r.status_code, _r.text[:300]))
_yomon = [
    ({"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": 1}], "sana": "2026-10-01"}, "noma'lum maydon"),
    ({"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": True}]}, "bool summa"),
    ({"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": -5}, {"hisob_id": HID["bank"], "summa": 0}, {"hisob_id": HID["karta"], "summa": 0}]}, "manfiy"),
    ({"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": 1}, {"hisob_id": HID["naqd"], "summa": 2}, {"hisob_id": HID["bank"], "summa": 0},
                    {"hisob_id": HID["karta"], "summa": 0}]}, "takror hisob"),
    ({"qoldiqlar": [{"hisob_id": str(HID["naqd"]), "summa": 1}]}, "id matn"),
    ({"qoldiqlar": [{"hisob_id": HIDB["naqd"], "summa": 1}, {"hisob_id": HID["bank"], "summa": 0}, {"hisob_id": HID["karta"], "summa": 0}]}, "begona hisob"),
    ({"qoldiqlar": []}, "bo'sh"),
    ({"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": 1.005}, {"hisob_id": HID["bank"], "summa": 0}, {"hisob_id": HID["karta"], "summa": 0}]}, "3 xona"),
    ({"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": 1e15}, {"hisob_id": HID["bank"], "summa": 0}, {"hisob_id": HID["karta"], "summa": 0}]}, "juda katta"),
]
_kodlar = [(n, A.post("/api/finance/hisoblar/qoldiq", json=t).status_code) for t, n in _yomon]
check("H3b qoldiq tanasi qat'iy — har biri 400, hech narsa yozilmaydi: " + ", ".join(n for _t, n in _yomon),
      all(k == 400 for _n, k in _kodlar) and soni(PulHisobiQoldiq, company_id=1) == 0, _kodlar)
_r = A.post("/api/finance/hisoblar/qoldiq", json={"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": 1_000_000},
                                                                 {"hisob_id": HID["bank"], "summa": 2_000_000.5},
                                                                 {"hisob_id": HID["karta"], "summa": 500_000}], "izoh": "K210 sanaldi"})
B0 = bal()
_cb1 = js(A.get("/api/finance/cash-balance"))
check("H4 qoldiq kiritildi: hisoblar 1 000 000 / 2 000 000,50 / 500 000; `boshlangan`; «Kassa + bank» = yig'indi TIYIN bilan (3 500 000,50; "
      "review210 №5 — ilgari butun so'mga yaxlitlanardi)",
      _r.status_code == 200 and js(_r).get("boshlangan") is True and teng(B0, {"naqd": 1_000_000, "bank": 2_000_000.5, "karta": 500_000})
      and _cb1.get("hisoblar_boshlangan") is True and abs((_cb1.get("balance") or 0) - 3_500_000.5) < 0.001
      and _cb1.get("boshlangich_kiritilgan") is True and js(_r).get("duplicate") is False,
      (_r.status_code, _r.text[:300], B0, _cb1.get("balance")))
_j = jurnal("pul_hisobi")
check("H5 jurnal: har hisobga «boshlang'ich qoldiq: … so'm · izoh: K210 sanaldi» (3 ta)",
      len(_j) == 3 and all("boshlang'ich qoldiq" in (x[2] or "") and "K210 sanaldi" in (x[2] or "") for x in _j)
      and any("Naqd pul" in (x[1] or "") for x in _j), _j)
_r = A.post("/api/finance/cash-transaction", data={"category": "boshlangich", "amount": 5000})
check("H6 qoldiq kiritilgach eski «boshlang'ich balans» — 400 (endi hisoblar qoldig'i)", _r.status_code == 400, (_r.status_code, _r.text[:200]))
# review210 №6: o'sha qoldiq takror yuborildi (ikki oyna / ikki bosish / tarmoq qaytarishi) — 8 s ichida
_r7 = A.post("/api/finance/hisoblar/qoldiq", json={"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": 1_000_000},
                                                                  {"hisob_id": HID["bank"], "summa": 2_000_000.5},
                                                                  {"hisob_id": HID["karta"], "summa": 500_000}], "izoh": "K210 sanaldi"})
check("H7 o'sha qoldiq takror yuborildi (8 s ichida) — 200 `duplicate: true`, yangi qator ham, jurnal yozuvi ham YO'Q (3 / 3), balans o'sha",
      _r7.status_code == 200 and js(_r7).get("duplicate") is True and soni(PulHisobiQoldiq, company_id=1) == 3
      and len(jurnal("pul_hisobi")) == 3 and teng(bal(), B0), (_r7.status_code, _r7.text[:300], soni(PulHisobiQoldiq, company_id=1)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. Pul yo'llari — har biri o'z hisobiga")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
O1 = buyurtma(900_000)
OID = O1.get("id")
oldin = bal()
_rr = [A.post("/api/payments", json={"order_id": OID, "amount": a, "payment_type": "partial", "payment_method": u, "notes": f"K210 {u}"})
       for a, u in ((100_000, "naqd"), (200_000, "plastik"), (300_000, "o'tkazma"))]
check("P1 mijoz to'lovi usuldan: naqd +100 000 → Naqd pul, plastik +200 000 → Karta, o'tkazma +300 000 → Bank",
      all(r.status_code == 200 for r in _rr) and teng(farq(oldin, bal()), {"naqd": 100_000, "karta": 200_000, "bank": 300_000}),
      ([r.status_code for r in _rr], farq(oldin, bal())))
_s = SessionLocal()
_pm = {p.payment_method.value: getattr(p, "hisob_id", None) for p in _s.query(Payment).filter(Payment.order_id == OID).all()}
_s.close()
check("P1b yozuvda `hisob_id` (usuldan) saqlanadi", _pm == {"naqd": HID["naqd"], "plastik": HID["karta"], "o'tkazma": HID["bank"]}, _pm)
# ortiqcha to'lov → mijozga qaytarish (karta)
oldin = bal()
_r = A.post("/api/payments", json={"order_id": OID, "amount": 400_000, "payment_type": "partial", "payment_method": "naqd", "notes": "K210 ortiq"},
            params={"confirm_overpay": "true"})
_r2 = A.post("/api/payments?confirm_overpay=true", json={"order_id": OID, "amount": 400_000, "payment_type": "partial",
                                                          "payment_method": "naqd", "notes": "K210 ortiq", "confirm_overpay": True})
_rq = A.post(f"/api/orders/{OID}/refund-overpayment", json={"amount": 50_000, "payment_method": "plastik", "notes": "K210 qaytdi"})
_f = farq(oldin, bal())
check("P2 ortiqcha to'lov qaytarildi (plastik) — Karta −50 000; to'lov naqd — Naqd pul +400 000",
      _rq.status_code == 200 and abs(_f["karta"] + 50_000) < 0.01 and abs(_f["naqd"] - 400_000) < 0.01 and abs(_f["bank"]) < 0.01,
      (_r.status_code, _r2.status_code, _r2.text[:200], _rq.status_code, _rq.text[:200], _f))
# tayyor sotuv (yakka / guruh)
oldin = bal()
_s1 = A.post("/api/finished/sell", json={"finished_product_id": ID["FP1"], "quantity": 2, "unit_price": 60000, "buyer_name": "K210 xaridor",
                                         "payment_method": "karta", "master_id": None, "confirm_below_cost": True})
_s2 = A.post("/api/finished/sell-batch", json={"items": [{"finished_product_id": ID["FP1"], "quantity": 1, "unit_price": 70000}],
                                               "buyer_name": "K210 guruh", "payment_method": "bank"})
check("P3 tayyor sotuv: yakka karta +120 000 → Karta; guruh bank +70 000 → Bank",
      _s1.status_code == 200 and _s2.status_code == 200 and teng(farq(oldin, bal()), {"karta": 120_000, "bank": 70_000}),
      (_s1.status_code, _s1.text[:200], _s2.status_code, _s2.text[:200], farq(oldin, bal())))
# yuk xati: to'lov (o'tkazma) + kompaniya transporti (karta), 50/50 (bank — yarmi)
_o = A.get(f"/api/orders/{OID}")
_oi = ((js(_o).get("items") or [{}])[0]).get("id")
oldin = bal()
_d1 = A.post("/api/deliveries", json={"order_id": OID, "items": [{"order_item_id": _oi, "quantity": 0.5}], "received_by": "K210 qabul",
                                      "notes": None, "transport_carrier": "K210 haydovchi", "transport_cost": 100_000,
                                      "transport_payer": "company", "transport_hisob": "karta", "payment_amount": None, "payment_method": "naqd"})
_d2 = A.post("/api/deliveries", json={"order_id": OID, "items": [{"order_item_id": _oi, "quantity": 0.25}], "received_by": None,
                                      "notes": None, "transport_carrier": None, "transport_cost": 30_000, "transport_payer": "split",
                                      "transport_hisob": "bank", "payment_amount": None, "payment_method": "naqd"})
_d3 = A.post("/api/deliveries", json={"order_id": OID, "items": [{"order_item_id": _oi, "quantity": 0.1}], "received_by": None,
                                      "notes": None, "transport_carrier": None, "transport_cost": 30_000, "transport_payer": "split",
                                      "transport_hisob": "xato", "payment_amount": None, "payment_method": "naqd"})
check("P4 yuk xati: kompaniya transporti 100 000 «karta» → Karta −100 000; 50/50 30 000 «bank» → Bank −15 000; noto'g'ri hisob — 400",
      _d1.status_code == 200 and _d2.status_code == 200 and _d3.status_code == 400
      and teng(farq(oldin, bal()), {"karta": -100_000, "bank": -15_000}),
      (_d1.status_code, _d1.text[:200], _d2.status_code, _d2.text[:200], _d3.status_code, farq(oldin, bal())))
# yakka xarid: ta'minotchisiz (naqd xarid — bank), ta'minotchi + qisman to'lov (karta) + o'z hisobimdan transport (karta)
oldin = bal()
_x1 = A.post(f"/api/inventory/{ID['MAT']}/purchase", json={"quantity": 10, "price_per_unit": 1_000, "notes": "K210 naqd xarid", "hisob": "bank"})
_x2 = A.post(f"/api/inventory/{ID['MAT']}/purchase", json={"quantity": 20, "price_per_unit": 1_000, "supplier_id": ID["SUP"], "paid_now": 5_000,
                                                          "transport_payer": "self", "transport_cost": 3_000, "hisob": "karta"})
_x3 = A.post(f"/api/inventory/{ID['MAT']}/purchase", json={"quantity": 1, "price_per_unit": 1_000, "hisob": "dollar"})
check("P5 yakka xarid: naqd xarid 10 000 «bank» → Bank −10 000; hoziroq to'lov 5 000 + transport 3 000 «karta» → Karta −8 000; "
      "noto'g'ri hisob — 400",
      _x1.status_code == 200 and _x2.status_code == 200 and _x3.status_code == 400
      and teng(farq(oldin, bal()), {"bank": -10_000, "karta": -8_000}),
      (_x1.status_code, _x1.text[:200], _x2.status_code, _x2.text[:200], _x3.status_code, farq(oldin, bal())))
# kirim hujjati
oldin = bal()
_k1 = A.post("/api/inventory/receipt", json={"items": [{"inventory_id": ID["MAT"], "quantity": 5, "price_per_unit": 2_000}],
                                             "supplier_id": ID["SUP"], "paid_now": 4_000, "transport_cost": 1_500, "tushirish_cost": 500,
                                             "hisob": "bank"})
check("P6 kirim hujjati «bank»: hoziroq to'lov 4 000 + qo'shimcha xarajatlar 2 000 → Bank −6 000",
      _k1.status_code == 200 and teng(farq(oldin, bal()), {"bank": -6_000}), (_k1.status_code, _k1.text[:300], farq(oldin, bal())))
# ta'minotchiga to'lov
oldin = bal()
_t1 = A.post(f"/api/suppliers/{ID['SUP']}/payment", json={"supplier_id": ID["SUP"], "amount": 7_000, "hisob": "karta"})
_t2 = A.post(f"/api/suppliers/{ID['SUP']}/payment", json={"supplier_id": ID["SUP"], "amount": 1_000, "hisob": "kassa"})
check("P7 ta'minotchiga to'lov «karta» → Karta −7 000; noto'g'ri hisob — 400",
      _t1.status_code == 200 and _t2.status_code == 400 and teng(farq(oldin, bal()), {"karta": -7_000}),
      (_t1.status_code, _t1.text[:200], _t2.status_code, farq(oldin, bal())))
# xarajat: yaratish (bank), hisobsiz (naqd), tahrirda karta ga
oldin = bal()
_e1 = A.post("/api/finance/transactions", json={"date": TK.isoformat() + "T00:00:00", "category": "elektr", "amount": 11_000, "hisob": "bank"})
_e2 = A.post("/api/finance/transactions", json={"date": TK.isoformat() + "T00:00:00", "category": "tushlik", "amount": 2_000})
_e3 = A.post("/api/finance/transactions", json={"date": TK.isoformat() + "T00:00:00", "category": "tushlik", "amount": 2_000, "hisob": 5})
_f1 = farq(oldin, bal())
_e4 = A.put(f"/api/finance/transactions/{js(_e1).get('id')}", json={"date": TK.isoformat() + "T00:00:00", "category": "elektr",
                                                                    "amount": 11_000, "hisob": "karta"})
_f2 = farq(oldin, bal())
_lst = js(A.get("/api/finance/transactions", params={"year": TK.year, "month": TK.month}))
_ht = {x.get("id"): x.get("hisob_turi") for x in (_lst if isinstance(_lst, list) else [])}
check("P8 xarajat: elektr 11 000 «bank» → Bank, tushlik 2 000 (hisobsiz) → Naqd pul; noto'g'ri — 400; tahrirda «karta» — Bank dan Karta ga "
      "ko'chdi; ro'yxatda `hisob_turi`",
      _e1.status_code == 200 and _e2.status_code == 200 and _e3.status_code == 400 and _e4.status_code == 200
      and teng(_f1, {"bank": -11_000, "naqd": -2_000}) and teng(_f2, {"karta": -11_000, "naqd": -2_000})
      and _ht.get(js(_e1).get("id")) == "karta" and _ht.get(js(_e2).get("id")) == "naqd",
      (_e1.status_code, _e2.status_code, _e3.status_code, _e4.status_code, _e4.text[:200], _f1, _f2, _ht))
# kirish transporti API
oldin = bal()
_tr = A.post("/api/transport-expenses", json={"amount": 9_000, "materials_note": "K210", "hisob": "bank"})
check("P9 kirish transporti API «bank» → Bank −9 000", _tr.status_code == 200 and teng(farq(oldin, bal()), {"bank": -9_000}),
      (_tr.status_code, _tr.text[:200], farq(oldin, bal())))
# hodimga avans / oylik / so'rovni tasdiqlash
oldin = bal()
_a1 = A.post(f"/api/employees/{ID['EMP']}/advance", params={"amount": "100000", "notes": "K210 avans", "hisob": "karta", "confirm_excess": "true"})
_a2 = A.post(f"/api/employees/{ID['EMP']}/advance", params={"amount": "100", "notes": "K210 xato", "hisob": "valyuta", "confirm_excess": "true"})
_c1 = A.post(f"/api/obligations/employee/{ID['EMP']}/close", params={"year": TK.year, "month": TK.month, "amount": "200000",
                                                                      "hisob": "bank", "confirm_excess": "true"})
_s = SessionLocal()
_rq = AdvanceRequest(employee_id=ID["EMP"], amount=50_000, requested_date=datetime.datetime(TK.year, TK.month, TK.day),
                     notes="K210 so'rov", status=AdvanceRequestStatus.PENDING)
_s.add(_rq)
_s.commit()
_rqid = _rq.id
_s.close()
_c2 = A.post(f"/api/admin/advance-requests/{_rqid}/confirm", params={"hisob": "xato"})
_c3 = A.post(f"/api/admin/advance-requests/{_rqid}/confirm", params={"hisob": "bank", "confirm_excess": "true"})
check("P10 avans «karta» −100 000 → Karta; «oylikni yopish» «bank» −200 000; so'rov tasdig'i «bank» −50 000 (noto'g'ri hisob — 400, "
      "so'rov kutilmoqda qoladi)",
      _a1.status_code == 200 and _a2.status_code == 400 and _c1.status_code == 200 and _c2.status_code == 400 and _c3.status_code == 200
      and teng(farq(oldin, bal()), {"karta": -100_000, "bank": -250_000}),
      (_a1.status_code, _a1.text[:200], _a2.status_code, _c1.status_code, _c1.text[:200], _c2.status_code, _c2.text[:150],
       _c3.status_code, _c3.text[:200], farq(oldin, bal())))
# Usta KPI / Ehson
oldin = bal()
_u1 = A.post("/api/finance/cash-transaction", data={"category": "usta_kpi", "amount": -1359, "notes": "Tojiddin aka", "hisob": "bank"})
_u2 = A.post("/api/finance/cash-transaction", data={"category": "ehson", "amount": -5000})
_ct = js(A.get("/api/finance/cash-transactions"))
check("P11 «Usta KPI to'landi» «bank» → Bank −1 359; «Ehson to'landi» (hisobsiz) → Naqd pul −5 000; ro'yxatda `hisob_id`",
      _u1.status_code == 200 and _u2.status_code == 200 and teng(farq(oldin, bal()), {"bank": -1359, "naqd": -5000})
      and any(x.get("hisob_id") == HID["bank"] and x.get("category") == "usta_kpi" for x in _ct),
      (_u1.status_code, _u2.status_code, farq(oldin, bal()), _ct[:3] if isinstance(_ct, list) else _ct))
oldin = bal()
_u3 = A.post("/api/finance/cash-transaction", data={"category": "usta_kpi", "amount": 5000, "hisob": "bank"})
_u4 = A.post("/api/finance/cash-transaction", data={"category": "ehson", "amount": 0})
check("P11b «Usta KPI / Ehson» — chiqim: musbat yoki 0 summa — 400, hisob o'zgarmaydi (review210 №7 — ilgari Bank +5 000 bo'lardi)",
      _u3.status_code == 400 and _u4.status_code == 400 and teng(farq(oldin, bal()), {}), (_u3.status_code, _u3.text[:200], _u4.status_code))
# sinov saytida JONLI TOPILGAN (23.10 20:22): bitta bosishdan ikki yozuv (javob kechikkanda so'rov serverga ikkinchi marta yetgan)
oldin = bal()
_u5 = A.post("/api/finance/cash-transaction", data={"category": "usta_kpi", "amount": -777, "notes": "K210 takror", "hisob": "karta"})
_u6 = A.post("/api/finance/cash-transaction", data={"category": "usta_kpi", "amount": -777, "notes": "K210 takror", "hisob": "karta"})
_ct2 = js(A.get("/api/finance/cash-transactions"))
check("P11c «Usta KPI to'landi» takror yuborildi (8 s ichida, o'sha summa / hisob / izoh) — ikkinchisi `duplicate: true`, yozuv BITTA, "
      "Karta −777 (bir marta)",
      _u5.status_code == 200 and _u6.status_code == 200 and js(_u5).get("duplicate") is False and js(_u6).get("duplicate") is True
      and js(_u5).get("transaction_id") == js(_u6).get("transaction_id")
      and sum(1 for x in (_ct2 if isinstance(_ct2, list) else []) if x.get("notes") == "K210 takror") == 1
      and teng(farq(oldin, bal()), {"karta": -777}), (_u5.text[:150], _u6.text[:150], farq(oldin, bal())))
# qaytarish «pul qaytdi» (usul) — ortiqcha to'langan buyurtma
O2 = buyurtma(100_000)
O2ID = O2.get("id")
_o2 = js(A.get(f"/api/orders/{O2ID}"))
_o2i = ((_o2.get("items") or [{}])[0]).get("id")
A.post("/api/deliveries", json={"order_id": O2ID, "items": [{"order_item_id": _o2i, "quantity": 1}], "received_by": None, "notes": None,
                                "transport_carrier": None, "transport_cost": 0, "transport_payer": "none", "payment_amount": None,
                                "payment_method": "naqd"})
A.post("/api/payments", json={"order_id": O2ID, "amount": 100_000, "payment_type": "partial", "payment_method": "naqd", "notes": "K210 to'liq"})
_qt = A.post("/api/returns", json={"order_id": O2ID, "order_item_id": _o2i, "item_name": "K210 panel", "quantity": 1, "unit": "dona",
                                   "reason": "Ortiqcha", "refund_amount": 100_000, "to_stock": False, "notes": None, "coating_applied": False})
_qid = js(_qt).get("id")
_q0 = A.post(f"/api/returns/{_qid}/refund", params={"payment_method": "valyuta"})
oldin = bal()
_q1 = A.post(f"/api/returns/{_qid}/refund", params={"payment_method": "o'tkazma"})
_qf = farq(oldin, bal())
check("P12 qaytarish «pul qaytdi» o'tkazma bilan — naqd qaytgan qismi Bank dan (manfiy); noto'g'ri usul — 400",
      _qt.status_code == 200 and _q0.status_code == 400 and _q1.status_code == 200 and _qf["bank"] < 0 and abs(_qf["naqd"]) < 0.01
      and abs(_qf["karta"]) < 0.01,
      (_qt.status_code, _qt.text[:200], _q0.status_code, _q1.status_code, _q1.text[:200], _qf))

# zip 210 dan oldingi yozuv (hisob_id NULL) — usulidan
oldin = bal()
_s = SessionLocal()
_s.add(Payment(order_id=OID, amount=12_345, payment_type=PaymentType.PARTIAL, payment_method=PaymentMethod.CARD, notes="K210 eski yozuv"))
_s.add(ExpenseTransaction(company_id=1, category="boshqa", amount=2_222, notes="K210 eski xarajat",
                          date=datetime.datetime.utcnow(), created_at=datetime.datetime.utcnow()))
_s.commit()
_s.close()
check("P13 eski yozuvlar (`hisob_id` NULL): plastik to'lov 12 345 — usulidan Karta ga; xarajat 2 222 — «Naqd pul» dan",
      teng(farq(oldin, bal()), {"karta": 12_345, "naqd": -2_222}), farq(oldin, bal()))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Hisoblar orasida o'tkazish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
oldin = bal()
_j0 = js(A.get("/api/finance/hisoblar")).get("jami")
_o1 = A.post("/api/finance/hisoblar/otkazma", json={"dan_hisob_id": HID["bank"], "ga_hisob_id": HID["naqd"], "summa": 300_000, "izoh": "K210 yechildi"})
_o2 = A.post("/api/finance/hisoblar/otkazma", json={"dan_hisob_id": HID["bank"], "ga_hisob_id": HID["naqd"], "summa": 300_000, "izoh": "K210 yechildi"})
_f = farq(oldin, bal())
check("T1 Bank → Naqd pul 300 000: Bank −300 000, Naqd +300 000, jami o'zgarmaydi; takror (8 s) — `duplicate`, yozuv BITTA",
      _o1.status_code == 200 and _o2.status_code == 200 and js(_o2).get("duplicate") is True and js(_o1).get("duplicate") is False
      and teng(_f, {"bank": -300_000, "naqd": 300_000}) and abs(js(A.get("/api/finance/hisoblar")).get("jami") - _j0) < 0.01
      and soni(PulOtkazmasi, company_id=1) == 1, (_o1.status_code, _o1.text[:200], _o2.text[:200], _f))
_yomon = [({"dan_hisob_id": HID["bank"], "ga_hisob_id": HID["bank"], "summa": 1}, "bir hisob"),
          ({"dan_hisob_id": HIDB["bank"], "ga_hisob_id": HID["naqd"], "summa": 1}, "begona hisob"),
          ({"dan_hisob_id": HID["bank"], "ga_hisob_id": HID["naqd"], "summa": 0}, "0"),
          ({"dan_hisob_id": HID["bank"], "ga_hisob_id": HID["naqd"], "summa": -5}, "manfiy"),
          ({"dan_hisob_id": HID["bank"], "ga_hisob_id": HID["naqd"], "summa": "5"}, "matn summa"),
          ({"dan_hisob_id": HID["bank"], "ga_hisob_id": HID["naqd"], "summa": 5, "x": 1}, "noma'lum maydon"),
          ({"dan_hisob_id": 999999, "ga_hisob_id": HID["naqd"], "summa": 5}, "yo'q hisob")]
_kodlar = [(n, A.post("/api/finance/hisoblar/otkazma", json=t).status_code) for t, n in _yomon]
check("T2 o'tkazish tanasi qat'iy — har biri 400: " + ", ".join(n for _t, n in _yomon),
      all(k == 400 for _n, k in _kodlar) and soni(PulOtkazmasi, company_id=1) == 1, _kodlar)
oldin = bal()
_od = A.delete(f"/api/finance/hisoblar/otkazma/{js(_o1).get('id')}")
_odB = B.delete(f"/api/finance/hisoblar/otkazma/{js(_o1).get('id')}")
check("T3 o'tkazish o'chirildi — Bank +300 000, Naqd −300 000 (qaytdi); B korxonadan — 404; jurnalda «O'tkazish: Bank → Naqd pul»",
      _od.status_code == 200 and _odB.status_code == 404 and teng(farq(oldin, bal()), {"bank": 300_000, "naqd": -300_000})
      and [x[0] for x in jurnal("pul_otkazmasi")] == ["created", "deleted"]
      and all("Bank → Naqd pul" in (x[1] or "") for x in jurnal("pul_otkazmasi")),
      (_od.status_code, _odB.status_code, farq(oldin, bal()), jurnal("pul_otkazmasi")))
_o3 = A.post("/api/finance/hisoblar/otkazma", json={"dan_hisob_id": HID["naqd"], "ga_hisob_id": HID["karta"], "summa": 25_000})
check("T4 Naqd pul → Karta 25 000 (keyingi tekshiruvlar uchun) — 200", _o3.status_code == 200, _o3.text[:200])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("I. Izchillik va tarix")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bq = js(A.get("/api/finance/hisoblar"))
_oq = js(A.get("/api/finance/pul-oqimi", params={"sana": TK.isoformat()}))
_boshlang = 1_000_000 + 2_000_000.5 + 500_000
check("I1 qoldiqdan keyingi hisoblar o'zgarishi yig'indisi = bugungi «Pul oqimi» balansi (hammasi bugun; o'tkazish — kirmaydi)",
      lambda: abs((_bq.get("jami") - _boshlang) - float(_oq.get("balans"))) < 0.02, (_bq.get("jami"), _oq.get("balans"), _oq.get("kirim"), _oq.get("chiqim")))
_cb = js(A.get("/api/finance/cash-balance"))
check("I2 «Kassa + bank» (`balance`) = hisoblar yig'indisi AYNAN (tiyin bilan); `eski_balans` — umumiy formula (boshlang'ich balanssiz)",
      lambda: abs(_cb.get("balance") - _bq.get("jami")) < 0.011 and isinstance(_cb.get("eski_balans"), (int, float)),
      (_cb.get("balance"), _bq.get("jami"), _cb.get("eski_balans")))
_tn = js(A.get(f"/api/finance/hisoblar/{HID['naqd']}/tarix"))
_hr = _tn.get("harakatlar") or []
_ok_qoldiq = True
for _i in range(len(_hr) - 1):
    if abs(_hr[_i]["qoldiq"] - (_hr[_i + 1]["qoldiq"] + _hr[_i]["summa"])) > 0.011:
        _ok_qoldiq = False
check("I3 «Naqd pul» tarixi: oxirgi qatordagi qoldiq = balans, har qator qoldig'i = oldingisi + summa, eng eskisi = qoldiq + summa; "
      "yangisi tepada; matnlar (mijoz to'lovi, xarajat, Ehson, o'tkazish)",
      lambda: _tn.get("boshlangan") is True and _hr and abs(_hr[0]["qoldiq"] - _tn.get("balans")) < 0.011 and _ok_qoldiq
      and abs(_hr[-1]["qoldiq"] - (1_000_000 + _hr[-1]["summa"])) < 0.011
      and abs(_tn.get("balans") - (bal()["naqd"] or 0)) < 0.011
      and any("Mijoz to'lovi" in r["matn"] for r in _hr) and any(r["matn"].startswith("Xarajat — Tushlik") for r in _hr)
      and any("Ehson to'landi" in r["matn"] for r in _hr) and any("O'tkazish: Naqd pul → Karta" in r["matn"] for r in _hr)
      and _hr[0]["vaqt"] >= _hr[-1]["vaqt"],
      (_tn.get("balans"), _hr[:3], len(_hr)))
_tb = B.get(f"/api/finance/hisoblar/{HID['naqd']}/tarix")
_t9 = A.get("/api/finance/hisoblar/999999/tarix")
check("I4 begona / yo'q hisob tarixi — 404", _tb.status_code == 404 and _t9.status_code == 404, (_tb.status_code, _t9.status_code))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Qayta sanash, o'chirish, faqat sanali yozuvlar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_n0 = bal()["naqd"]
_rs = A.post("/api/finance/hisoblar/qoldiq", json={"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": 777_000}], "izoh": "K210 qayta"})
_b1 = bal()
_j = jurnal("pul_hisobi")
check("R1 «Naqd pul» qayta sanaldi 777 000 — balans 777 000, boshqalari o'zgarmadi; jurnal «qoldiq sanaldi … dasturda … farq …»",
      lambda: _rs.status_code == 200 and abs(_b1["naqd"] - 777_000) < 0.01 and "qoldiq sanaldi: 777 000" in (_j[-1][2] or "")
      and "dasturda:" in (_j[-1][2] or "") and "farq:" in (_j[-1][2] or ""), (_rs.status_code, _rs.text[:200], _b1, _j[-1:]))
_s = SessionLocal()
try:
    _qn = _s.query(PulHisobiQoldiq).filter(PulHisobiQoldiq.company_id == 1, PulHisobiQoldiq.hisob_id == HID["naqd"]).order_by(PulHisobiQoldiq.id.desc()).first()
    _qid_n, _ds = _qn.id, float(_qn.dastur_summa)
except Exception:                       # noqa: BLE001
    _qid_n, _ds = 999_993, -1.0
_s.close()
check("R1b `dastur_summa` — sanash paytidagi dastur qoldig'i", lambda: abs(_ds - _n0) < 0.011, (_ds, _n0))
_kecha = TK - datetime.timedelta(days=1)
oldin = bal()
_e5 = A.post("/api/finance/transactions", json={"date": _kecha.isoformat() + "T00:00:00", "category": "boshqa", "amount": 4_000, "hisob": "naqd"})
_e6 = A.post("/api/finance/transactions", json={"date": TK.isoformat() + "T00:00:00", "category": "boshqa", "amount": 6_000, "hisob": "naqd"})
check("R2 qoldiqdan KEYIN yozilgan: kechagi sanali xarajat 4 000 — sanalmaydi (pul sanashdan oldin ketgan); bugungi faqat sanali 6 000 — "
      "sanaladi (yozilgan vaqti qoldiqdan keyin)",
      _e5.status_code == 200 and _e6.status_code == 200 and teng(farq(oldin, bal()), {"naqd": -6_000}),
      (_e5.status_code, _e6.status_code, farq(oldin, bal())))
oldin = bal()
_rd = A.delete(f"/api/finance/hisoblar/qoldiq/{_qid_n}")
_rdB = B.delete(f"/api/finance/hisoblar/qoldiq/{_qid_n}")
_b2 = bal()
check("R3 sanash o'chirildi — «Naqd pul» birinchi qoldiqqa qaytdi (777 000 dan farqli), B dan — 404; jurnal «deleted» (o'zbekcha nomli tur)",
      lambda: _rd.status_code == 200 and _rdB.status_code == 404 and abs(_b2["naqd"] - 777_000) > 1 and jurnal("pul_hisobi")[-1][0] == "deleted",
      (_rd.status_code, _rdB.status_code, _b2))
# review210 №1 (YUQORI): o'tgan oy oyligini yopish / o'tgan oy majburiyatini to'lash — sana hisobot oyi (28-kun), pul HOZIR
_ot = TK.replace(day=1) - datetime.timedelta(days=1)            # o'tgan oyning oxirgi kuni
oldin = bal()
_c4 = A.post(f"/api/obligations/employee/{ID['EMP']}/close", params={"year": _ot.year, "month": _ot.month, "amount": "200000",
                                                                      "hisob": "bank", "confirm_excess": "true"})
from models import EmployeeAdvance as _EA210      # noqa: E402
_s = SessionLocal()
_ea = _s.query(_EA210).filter(_EA210.employee_id == ID["EMP"]).order_by(_EA210.id.desc()).first()
_ea_sana, _ea_pul = (_ea.date, getattr(_ea, "pul_vaqti", None)) if _ea else (None, None)
_s.close()
check("R4 «oylikni yopish» O'TGAN oy uchun (sana — o'sha oyning 28-kuni) qoldiqdan keyin — Bank −200 000 (pul HOZIR berildi; "
      "ilgari 0 — review210 №1); yozuvda sana 28-kun, `pul_vaqti` — hozir",
      _c4.status_code == 200 and teng(farq(oldin, bal()), {"bank": -200_000}) and _ea_sana is not None
      and (_ea_sana.year, _ea_sana.month, _ea_sana.day) == (_ot.year, _ot.month, 28) and _ea_pul is not None,
      (_c4.status_code, _c4.text[:200], farq(oldin, bal()), _ea_sana, _ea_pul))
oldin = bal()
_m28 = f"{_ot.year}-{_ot.month:02d}-28T00:00:00"
_e7 = A.post("/api/finance/transactions", json={"date": _m28, "category": "arenda", "amount": 300_000, "hisob": "bank", "pul_hozir": True,
                                                 "notes": "To'lov (Qarzdorlar sahifasidan)"})
_e8 = A.post("/api/finance/transactions", json={"date": _m28, "category": "boshqa", "amount": 1_111, "hisob": "bank"})
_e9 = A.post("/api/finance/transactions", json={"date": _m28, "category": "boshqa", "amount": 1, "hisob": "bank", "pul_hozir": "ha"})
check("R5 Qarzdorlar «To'lov qo'shish» — o'tgan oy arendasi (sana 28-kun, `pul_hozir`) qoldiqdan keyin — Bank −300 000 (ilgari 0); "
      "o'tgan oyga sanali ODDIY xarajat 1 111 — sanalmaydi (pul sanashdan oldin ketgan); `pul_hozir` bool emas — 400",
      _e7.status_code == 200 and _e8.status_code == 200 and _e9.status_code == 400 and teng(farq(oldin, bal()), {"bank": -300_000}),
      (_e7.status_code, _e7.text[:200], _e8.status_code, _e9.status_code, farq(oldin, bal())))
_r5 = js(A.get(f"/api/finance/hisoblar/{HID['bank']}/tarix"))
check("R5b «Bank» tarixida o'tgan oy arendasi — pul to'langan payt (bugun, aniq vaqt) bilan",
      any("Arenda" in h["matn"] and abs(h["summa"] + 300_000) < 0.01 and not h.get("faqat_sana")
          and str(h["vaqt"])[:10] >= (TK - datetime.timedelta(days=1)).isoformat() for h in (_r5.get("harakatlar") or [])),
      (_r5.get("harakatlar") or [])[:4])
# review210 №2: hodim so'rovidan avans — hodim pulni olib, sanashdan OLDIN yozgan, admin keyin tasdiqlagan
_s = SessionLocal()
_tq = (_s.query(PulHisobiQoldiq).filter(PulHisobiQoldiq.company_id == 1, PulHisobiQoldiq.hisob_id == HID["naqd"])
       .order_by(PulHisobiQoldiq.vaqt.desc(), PulHisobiQoldiq.id.desc()).first() if PulHisobiQoldiq is not None else None)
_tqv = _tq.vaqt if _tq else datetime.datetime.utcnow()
_rq1 = AdvanceRequest(employee_id=ID["EMP"], amount=40_000, requested_date=datetime.datetime(TK.year, TK.month, TK.day),
                      notes="K210 oldin olgan", status=AdvanceRequestStatus.PENDING, submitted_at=_tqv - datetime.timedelta(minutes=1))
_rq2 = AdvanceRequest(employee_id=ID["EMP"], amount=30_000, requested_date=datetime.datetime(TK.year, TK.month, TK.day),
                      notes="K210 keyin olgan", status=AdvanceRequestStatus.PENDING)
_s.add_all([_rq1, _rq2])
_s.commit()
_rq1id, _rq2id = _rq1.id, _rq2.id
_s.close()
oldin = bal()
_c5 = A.post(f"/api/admin/advance-requests/{_rq1id}/confirm", params={"hisob": "naqd", "confirm_excess": "true"})
_f5 = farq(oldin, bal())
_c6 = A.post(f"/api/admin/advance-requests/{_rq2id}/confirm", params={"hisob": "naqd", "confirm_excess": "true"})
check("R6 hodim so'rovi: pulni sanashdan OLDIN olib yozgan (so'rov qoldiqdan oldin), tasdiq KEYIN — Naqd o'zgarmaydi (pul sanalgan pulda "
      "yo'q edi; ilgari −40 000 — review210 №2); sanashdan keyin yozgan — Naqd −30 000",
      _c5.status_code == 200 and _c6.status_code == 200 and teng(_f5, {}) and teng(farq(oldin, bal()), {"naqd": -30_000}),
      (_c5.status_code, _c5.text[:200], _f5, _c6.status_code, farq(oldin, bal())))
# review210 №3: faqat sanali, yozilgan payti yo'q yozuv qoldiq kunida — doim KEYIN (qoldiq soatiga bog'liq emas)
import services as _sv210t                        # noqa: E402


def _pk(x, t):
    """`services._pul_keyin` (asl kodda yo'q — sinov qulamasin: xato nomi qaytadi)."""
    try:
        return _sv210t._pul_keyin(x, t)
    except Exception as e:              # noqa: BLE001
        return type(e).__name__


_kun = datetime.datetime(TK.year, TK.month, TK.day)
_q03 = _kun - datetime.timedelta(hours=2)          # Toshkent 03:00 (UTC 22:00 oldingi kun)
_q09 = _kun + datetime.timedelta(hours=4)          # Toshkent 09:00
_qator = {"faqat_sana": True, "vaqt": _kun, "yozilgan": None}
_qator2 = {"faqat_sana": True, "vaqt": _kun, "yozilgan": _q09 - datetime.timedelta(hours=1)}
_qator3 = {"faqat_sana": True, "vaqt": _kun - datetime.timedelta(days=1), "yozilgan": _q09 + datetime.timedelta(hours=1)}
_qator4 = {"faqat_sana": False, "vaqt": _q09 + datetime.timedelta(seconds=1), "yozilgan": None}
check("R7 `_pul_keyin`: qoldiq kunidagi faqat sanali, yozilgan payti yo'q qator — qoldiq Toshkent 03:00 da ham, 09:00 da ham KEYIN "
      "(ilgari 03:00 — keyin, 09:00 — oldin); yozilgan payti qoldiqdan oldin — OLDIN; kechagi sanali (bugun yozilgan) — OLDIN; aniq vaqt — o'z vaqti",
      lambda: _pk(_qator, _q03) is True and _pk(_qator, _q09) is True and _pk(_qator2, _q09) is False and _pk(_qator3, _q09) is False
      and _pk(_qator4, _q09) is True,
      [_pk(x, t) for x, t in ((_qator, _q03), (_qator, _q09), (_qator2, _q09), (_qator3, _q09), (_qator4, _q09))])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("X. Korxonalar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bx = bal()                                         # A — X bo'limi boshida
check("X1 B korxona: qoldiqsiz, A ning harakatlari ta'sir qilmaydi", holat(B).get("boshlangan") is False, holat(B))
_rb = B.post("/api/finance/hisoblar/qoldiq", json={"qoldiqlar": [{"hisob_id": HIDB["naqd"], "summa": 10}, {"hisob_id": HIDB["bank"], "summa": 20},
                                                                 {"hisob_id": HIDB["karta"], "summa": 30}]})
_rbA = B.post("/api/finance/hisoblar/qoldiq", json={"qoldiqlar": [{"hisob_id": HID["naqd"], "summa": 10}]})
_xa = bal()
check("X2 B qoldiq kiritdi (10 / 20 / 30) — A o'zgarmadi; B dan A ning hisobi — 400",
      _rb.status_code == 200 and teng(bal(B), {"naqd": 10, "bank": 20, "karta": 30}) and _rbA.status_code == 400 and teng(_xa, _bx),
      (_rb.status_code, _rb.text[:200], bal(B), _rbA.status_code))
_s = SessionLocal()
_xato = None
try:
    _e = ExpenseTransaction(company_id=2, category="boshqa", amount=1, hisob_id=HID["naqd"])
    _s.add(_e)
    _s.flush()
except Exception as e:                  # noqa: BLE001
    _xato = type(e).__name__
_s.rollback()
_s.close()
check("X3 model qo'riqchisi: B xarajatiga A ning hisobi — rad (TenantMismatchError)", _xato == "TenantMismatchError", _xato)
# review210 №3: B ning qoldig'i KECHA kiritilgan; kechagi sanali kirim hujjati (hoziroq to'lov + qo'shimcha xarajatlar) BUGUN kiritildi —
# hujjatning HAMMA qismi bitta hukm (ilgari: xarid qatori va to'lov — chiqmasdi, qo'shimcha xarajatlar — ayirilardi)
_s = SessionLocal()
for _q in (_s.query(PulHisobiQoldiq).filter(PulHisobiQoldiq.company_id == 2).all() if PulHisobiQoldiq is not None else []):
    _q.vaqt = _q.vaqt - datetime.timedelta(days=1)
_bsup = Supplier(company_id=2, name="K210 B Ta'minotchi")
_bmat = Inventory(company_id=2, item_name="K210 B Kley", unit="kg", stock_quantity=0, price_per_unit=1_000, category="Xomashyo")
_s.add_all([_bsup, _bmat])
_s.commit()
_bsid, _bmid = _bsup.id, _bmat.id
_s.close()
_kecha = TK - datetime.timedelta(days=1)
_ikki = TK - datetime.timedelta(days=2)
oldin = bal(B)
_kb1 = B.post("/api/inventory/receipt", json={"items": [{"inventory_id": _bmid, "quantity": 5, "price_per_unit": 2_000}],
                                              "supplier_id": _bsid, "paid_now": 4_000, "transport_cost": 1_500, "tushirish_cost": 500,
                                              "hisob": "bank", "receipt_date": _kecha.isoformat()})
_fx1 = farq(oldin, bal(B))
oldin = bal(B)
_kb2 = B.post("/api/inventory/receipt", json={"items": [{"inventory_id": _bmid, "quantity": 3, "price_per_unit": 1_000}],
                                              "transport_cost": 700, "hisob": "karta", "receipt_date": _kecha.isoformat()})
_fx2 = farq(oldin, bal(B))
oldin = bal(B)
_kb3 = B.post("/api/inventory/receipt", json={"items": [{"inventory_id": _bmid, "quantity": 2, "price_per_unit": 1_000}],
                                              "supplier_id": _bsid, "paid_now": 900, "transport_cost": 100, "hisob": "bank",
                                              "receipt_date": _ikki.isoformat()})
_fx3 = farq(oldin, bal(B))
check("X4 B qoldig'i KECHA; kechagi sanali kirim hujjati BUGUN kiritildi — butun hujjat ayiriladi: to'lov 4 000 + qo'shimcha 2 000 → "
      "Bank −6 000 (ilgari −2 000); ta'minotchisiz naqd xarid 3 000 + transport 700 → Karta −3 700 (ilgari −700); qoldiqdan OLDINGI kunga "
      "sanali hujjat — o'zgarmaydi",
      _kb1.status_code == 200 and _kb2.status_code == 200 and _kb3.status_code == 200 and teng(_fx1, {"bank": -6_000})
      and teng(_fx2, {"karta": -3_700}) and teng(_fx3, {}),
      (_kb1.status_code, _kb1.text[:200], _fx1, _kb2.status_code, _kb2.text[:200], _fx2, _kb3.status_code, _fx3))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira → tiklash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_s = SessionLocal()
_bz0 = bal()
_zax = crud.export_full_backup(_s, company_id=1)
_tab = _zax.get("tables") or {}
_zax = json.loads(json.dumps(_zax, default=str))
_s.close()
check("Z1 zaxirada `pul_hisoblari`, `pul_hisobi_qoldiqlari`, `pul_otkazmalari` va yozuvlardagi `hisob_id`",
      len(_tab.get("pul_hisoblari") or []) == 3 and len(_tab.get("pul_hisobi_qoldiqlari") or []) >= 3
      and len(_tab.get("pul_otkazmalari") or []) == 1 and any(r.get("hisob_id") for r in (_tab.get("payments") or [])),
      {k: len(v or []) for k, v in _tab.items() if k.startswith("pul_")})
_s = SessionLocal()
try:
    _nat = crud.import_full_backup(_s, _zax, company_id=1, replace=True)
except Exception as e:                  # noqa: BLE001
    _nat = {"success": False, "message": f"{type(e).__name__}: {e}"}
_s.close()
check("Z2 tiklash (replace) — muvaffaqiyatli, hisoblar qoldig'i AYNAN", _nat.get("success") is True and teng(bal(), _bz0),
      (str(_nat)[:400], bal(), _bz0))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
    import glob
    import socket
    import threading
    import uvicorn
    from playwright.sync_api import sync_playwright
    # yangi korxona (C) — qoldiqsiz holatdan boshlab
    _s = SessionLocal()
    if not _s.get(Company, 3):
        _s.add(Company(id=3, name="K210 C korxona"))
        _s.commit()
    with contextlib.redirect_stdout(io.StringIO()):
        auth.create_user(_s, "k210_c", PAROL, UserRole.ADMIN, "K210 C Admin", company_id=3)
    _s.add(Supplier(company_id=3, name="K210 C Ta'minotchi"))
    _s.add(Employee(company_id=3, name="K210 C Hodim", position="Kesuvchi", pay_type=PayType.FIXED, fixed_amount=1_000_000, is_active=True))
    _s.commit()
    _s.close()
    _sk = socket.socket()
    _sk.bind(("127.0.0.1", 0))
    PORT = _sk.getsockname()[1]
    _sk.close()
    _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error", lifespan="off"))
    threading.Thread(target=_srv.run, daemon=True).start()
    while not _srv.started:
        time.sleep(0.1)
    BASE = f"http://127.0.0.1:{PORT}"
    _exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    XATOLAR = []

    def _ui():
      with sync_playwright() as pw:
          br = pw.chromium.launch(executable_path=_exe[-1] if _exe else None)
          ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent")
          ctx.route("**/*", lambda r: r.fulfill(status=204, body="") if not r.request.url.startswith(BASE) else r.continue_())
          pg = ctx.new_page()
          pg.set_default_timeout(10000)
          pg.on("pageerror", lambda e: XATOLAR.append(str(e)[:200]))
          pg.on("dialog", lambda d: d.accept())
          pg.goto(BASE + "/login")
          pg.fill("input[name=username]", "k210_c")
          pg.fill("input[name=password]", PAROL)
          pg.press("input[name=password]", "Enter")
          pg.wait_for_load_state("networkidle")

          def tasdiq():
              # dastur tasdiq oynasi (customConfirm) — «Ha» tugmasi
              pg.wait_for_timeout(250)
              return pg.evaluate("""() => { const b = [...document.querySelectorAll('button')].filter(x => x.offsetParent !== null &&
                  /^(Ha, |Ha$|OK$|Tasdiqlash$)/.test(x.textContent.trim())); if (b.length) { b[b.length - 1].click(); return true; } return false; }""")

          pg.goto(BASE + "/finance", wait_until="networkidle")
          pg.wait_for_timeout(600)
          u1 = pg.evaluate("""() => ({ogoh: !document.getElementById('cash-boshlangich-yoq').hidden,
              kartalar: document.getElementById('hisob-kartalari').hidden, otk: document.getElementById('otkazma-btn').hidden,
              tugmalar: [...document.querySelectorAll('.hb-tugmalar .btn')].map(b => b.textContent.trim())})""")
          check("U1 qoldiqsiz: ogohlantirish ko'rinadi («Boshlang'ich qoldiqni kiritish»), hisob kartalari va «O'tkazish» yashirin; tugmalar",
                u1["ogoh"] and u1["kartalar"] and u1["otk"] and "+ Boshlang'ich qoldiq" in u1["tugmalar"] and "− Usta KPI to'landi" in u1["tugmalar"],
                u1)
          pg.click("text=+ Boshlang'ich qoldiq")
          pg.wait_for_timeout(300)
          _inp = pg.evaluate("() => [...document.querySelectorAll('#qoldiqQatorlar input')].map(i => i.id)")
          for _i, _v in zip(_inp, ("8450000", "12620000", "2449998")):
              pg.fill("#" + _i, _v)
          pg.wait_for_timeout(150)
          _old = pg.evaluate("() => document.getElementById('qoldiqOldindan').textContent")
          pg.click("#qoldiq-saqla")
          tasdiq()
          pg.wait_for_timeout(900)
          u2 = pg.evaluate("""() => ({jami: document.getElementById('cash-balance-val').textContent.replace(/[\\s\\u00a0\\u202f]/g, ''),
              kartalar: [...document.querySelectorAll('#hisob-kartalari .hb-hisob')].map(k => k.textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').trim()),
              ogoh: !document.getElementById('cash-boshlangich-yoq').hidden, otk: !document.getElementById('otkazma-btn').hidden,
              modal: document.getElementById('qoldiqModal').style.display})""")
          check("U2 qoldiq oynasi: 3 maydon, oldindan ko'rish «Siz kiritgan jami: 23 519 998»; saqlangach — 3 karta (Naqd pul 8 450 000, Bank "
                "12 620 000, Karta 2 449 998), jami 23 519 998, ogohlantirish yo'q, «O'tkazish» ko'rinadi",
                len(_inp) == 3 and "Sizkiritganjami:23519998" in bosh(_old) and u2["jami"].startswith("23519998") and len(u2["kartalar"]) == 3
                and bosh(u2["kartalar"][0]) == "Naqdpul8450000so'm" and bosh(u2["kartalar"][1]) == "Bank12620000so'm"
                and bosh(u2["kartalar"][2]) == "Karta2449998so'm" and not u2["ogoh"] and u2["otk"] and u2["modal"] == "none", (u2, _old))
          # o'tkazish
          pg.click("#otkazma-btn")
          pg.wait_for_timeout(300)
          pg.fill("#otk-summa", "5000000")
          pg.wait_for_timeout(150)
          _ol = pg.evaluate("() => document.getElementById('otkOldindan').textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ')")
          pg.click("#otk-saqla")
          tasdiq()
          pg.wait_for_timeout(900)
          u3 = pg.evaluate("""() => [...document.querySelectorAll('#hisob-kartalari .hb-hisob')].map(k => k.textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').trim())""")
          check("U3 o'tkazish oynasi (Bank → Naqd pul 5 000 000): oldindan ko'rish «12 620 000 → 7 620 000», «8 450 000 → 13 450 000», jami "
                "o'zgarmaydi; saqlangach kartalar Naqd 13 450 000 / Bank 7 620 000",
                "12620000→7620000" in bosh(_ol) and "8450000→13450000" in bosh(_ol) and "o'zgarmaydi" in _ol
                and bosh(u3[0]) == "Naqdpul13450000so'm" and bosh(u3[1]) == "Bank7620000so'm",
                (_ol, u3))
          # hisob tarixi
          pg.click("#hisob-kartalari .hb-hisob >> nth=0")
          pg.wait_for_timeout(700)
          u4 = pg.evaluate("""() => ({sar: document.getElementById('htSarlavha').textContent, xul: document.getElementById('htXulosa').textContent,
              qator: [...document.querySelectorAll('#htRoyxat .hb-tarix-q')].map(q => q.textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').trim())})""")
          pg.click("#hisobTarixModal button[aria-label='Yopish']")
          check("U4 «Naqd pul» kartasi bosildi — tarix oynasi: «Naqd pul — tarix», hozir 13 450 000, qator «O'tkazish: Bank → Naqd pul +5 000 000»",
                u4["sar"] == "Naqd pul — tarix" and "13 450 000" in u4["xul"].replace(" ", " ").replace(" ", " ")
                and any("O'tkazish: Bank → Naqd pul" in q and "+5 000 000" in q for q in u4["qator"]), u4)
          # Usta KPI — Karta dan
          pg.click("text=− Usta KPI to'landi")
          pg.wait_for_timeout(300)
          u5a = pg.evaluate("""() => ({tug: [...document.querySelectorAll('#cashtx-hisob button')].map(b => b.textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').trim()),
              on: document.querySelector('#cashtx-hisob button.on')?.dataset.turi,
              qoldiq: (document.querySelector('#cashtx-hisob .hisob-seg-qoldiq') || {}).textContent || '',
              seg: (() => { const g = document.querySelector('#cashtx-hisob .hisob-seg'); const r = g.getBoundingClientRect();
                            return {h: Math.round(r.height * 10) / 10, rad: getComputedStyle(g).borderTopLeftRadius}; })()})""")
          pg.click("#cashtx-hisob button[data-turi='karta']")
          u5b = pg.evaluate("() => (document.querySelector('#cashtx-hisob .hisob-seg-qoldiq') || {}).textContent || ''")
          pg.fill("#cashtx-amount", "1359")
          pg.click("#cashTxModal >> text=Saqlash")
          tasdiq()
          pg.wait_for_timeout(900)
          u5 = pg.evaluate("""() => [...document.querySelectorAll('#hisob-kartalari .hb-hisob')].map(k => k.textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').trim())""")
          check("U5 Usta KPI oynasi: «Qaysi hisobdan» — bo'lakli tanlov (40 px, burchak 8 px — U-13) Naqd pul / Bank / Karta (standart Naqd), "
                "ostida tanlangan hisob qoldig'i («Naqd pul qoldig'i: 13 450 000 so'm» → «Karta» tanlansa — «Karta qoldig'i: 2 449 998 so'm»); "
                "1 359 — Karta 2 449 998 − 1 359 = 2 448 639",
                len(u5a["tug"]) == 3 and [bosh(x) for x in u5a["tug"]] == ["Naqdpul", "Bank", "Karta"] and u5a["on"] == "naqd"
                and bosh(u5a["qoldiq"]) == "Naqdpulqoldig'i:13450000so'm" and bosh(u5b) == "Kartaqoldig'i:2449998so'm"
                and u5a["seg"]["h"] == 40 and u5a["seg"]["rad"] == "8px" and bosh(u5[2]) == "Karta2448639so'm", (u5a, u5b, u5))
          # xarajat oynasi — tanlov
          pg.evaluate("() => openTxModal()")
          pg.wait_for_timeout(300)
          u6 = pg.evaluate("""() => ({n: document.querySelectorAll('#tx-f-hisob button').length, on: document.querySelector('#tx-f-hisob button.on')?.dataset.turi})""")
          pg.evaluate("() => closeTxModal()")
          check("U6 xarajat oynasida «Qaysi hisobdan to'landi» — 3 tugma, standart Naqd", u6 == {"n": 3, "on": "naqd"}, u6)
          # qo'lda kiritilganlar tarixi
          pg.click("#kassa-tarix-btn")
          pg.wait_for_timeout(700)
          u7 = pg.evaluate("() => [...document.querySelectorAll('#cashTxHistoryList .hb-tarix-q')].map(q => q.textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').trim())")
          check("U7 «Qo'lda kiritilganlar tarixi»: qoldiqlar (3), o'tkazish, Usta KPI (hisobi bilan — Karta)",
                sum(1 for q in u7 if q.startswith("Qoldiq —")) == 3 and any(q.startswith("O'tkazish: Bank → Naqd pul") for q in u7)
                and any(q.startswith("Usta KPI to'landi") and "Karta" in q for q in u7), u7)
          # boshqa sahifalarda tanlov
          _sah = {}
          for _yol, _sel in (("/suppliers", "#ap-hisob, #pay-hisob"), ("/suppliers/receive", "#ap-hisob"), ("/kunlik-xarajat", "#kx-hisob"),
                             ("/kpi", "#adv-hisob"), ("/orders", "#dlv-transport-hisob")):
              pg.goto(BASE + _yol, wait_until="networkidle")
              pg.wait_for_timeout(400)
              _sah[_yol] = pg.evaluate(f"""() => [...document.querySelectorAll({json.dumps(_sel)})].map(e => (hisobQiymat(e), e.querySelectorAll('button').length))""")
          check("U8 boshqa sahifalarda «Qaysi hisobdan» tanlovi (3 tugma): Ta'minotchilar (xarid, to'lov), Kirim qilish, Kunlik xarajat, "
                "Ustalar KPI (avans), Buyurtmalar (yuk xati transporti)",
                all(v and all(n == 3 for n in v) for v in _sah.values()) and len(_sah["/suppliers"]) == 2, _sah)
          _hs = pg.evaluate("""async () => { const p = hisobSora('K210 sinov', {okText: 'OK'}); await new Promise(r => setTimeout(r, 100));
              const kor = getComputedStyle(document.getElementById('ccModalHisob')).display !== 'none';
              document.querySelector('#ccModalHisobTanlov button[data-turi="bank"]').click(); document.getElementById('ccModalOk').click();
              const t1 = await p;
              const p2 = hisobSora('K210 bekor'); await new Promise(r => setTimeout(r, 100)); document.getElementById('ccModalCancel').click();
              const t2 = await p2;
              const p3 = customConfirm('K210 oddiy'); await new Promise(r => setTimeout(r, 100));
              const kor3 = getComputedStyle(document.getElementById('ccModalHisob')).display !== 'none'; document.getElementById('ccModalOk').click();
              await p3; return [kor, t1, t2, kor3]; }""")
          check("U9 `hisobSora` — dasturning tasdiq oynasida «Qaysi hisobdan» tanlovi: «Bank» tanlab «OK» — 'bank'; «Bekor» — null; oddiy "
                "`customConfirm` da tanlov ko'rinmaydi", _hs == [True, "bank", None, False], _hs)
          ctx.close()
          # telefon va tungi rejim
          for _tungi in (False, True):
              ctx2 = br.new_context(viewport={"width": 390, "height": 844}, timezone_id="Asia/Tashkent", is_mobile=True, has_touch=True)
              ctx2.route("**/*", lambda r: r.fulfill(status=204, body="") if not r.request.url.startswith(BASE) else r.continue_())
              p2 = ctx2.new_page()
              p2.set_default_timeout(10000)
              p2.on("pageerror", lambda e: XATOLAR.append(str(e)[:200]))
              p2.goto(BASE + "/login")
              p2.fill("input[name=username]", "k210_c")
              p2.fill("input[name=password]", PAROL)
              p2.press("input[name=password]", "Enter")
              p2.wait_for_load_state("networkidle")
              if _tungi:
                  p2.evaluate("() => { try { localStorage.setItem('theme', 'dark'); } catch (e) {} }")
              p2.goto(BASE + "/finance", wait_until="networkidle")
              p2.wait_for_timeout(700)
              _m = p2.evaluate("""() => { const k = document.getElementById('kassa-karta').getBoundingClientRect();
                  const h = [...document.querySelectorAll('#hisob-kartalari .hb-hisob')].map(x => x.getBoundingClientRect());
                  const s = getComputedStyle(document.querySelector('#hisob-kartalari .hb-hs'));
                  return {toshish: document.documentElement.scrollWidth - document.documentElement.clientWidth, kenglik: Math.round(k.width),
                          kartalar: h.length, ichida: h.every(r => r.left >= k.left - 1 && r.right <= k.right + 1), rang: s.color,
                          tema: document.documentElement.getAttribute('data-theme')}; }""")
              check(f"U10{'b' if _tungi else ''} telefon 390 px{' (tungi rejim)' if _tungi else ''}: gorizontal toshish 0, 3 hisob kartasi karta ichida, "
                    "summa oq rangda (qorong'i kartada o'qiladi)",
                    _m["toshish"] <= 0 and _m["kartalar"] == 3 and _m["ichida"] and _m["rang"] == "rgb(255, 255, 255)"
                    and (_m["tema"] == "dark") == _tungi, _m)
              ctx2.close()
          # review210 №4 / №5: tor telefon (320 / 360 / 375 px) — qoldiq oynasi gorizontal surilmaydi; tiyinli qoldiq kartada tiyin bilan
          _tor = {}
          for _w in (320, 360, 375):
              ctx3 = br.new_context(viewport={"width": _w, "height": 740}, timezone_id="Asia/Tashkent", is_mobile=True, has_touch=True)
              ctx3.route("**/*", lambda r: r.fulfill(status=204, body="") if not r.request.url.startswith(BASE) else r.continue_())
              p3 = ctx3.new_page()
              p3.set_default_timeout(10000)
              p3.on("pageerror", lambda e: XATOLAR.append(str(e)[:200]))
              p3.on("dialog", lambda d: d.accept())
              p3.goto(BASE + "/login")
              p3.fill("input[name=username]", "k210_c")
              p3.fill("input[name=password]", PAROL)
              p3.press("input[name=password]", "Enter")
              p3.wait_for_load_state("networkidle")
              p3.goto(BASE + "/finance", wait_until="networkidle")
              p3.wait_for_timeout(600)
              p3.evaluate("() => openQoldiqModal()")
              p3.wait_for_timeout(300)
              _tor[_w] = p3.evaluate("""() => { const b = document.querySelector('#qoldiqModal > div');
                  const t = [...b.querySelectorAll('button')].find(x => x.id === 'qoldiq-saqla');
                  const r = t.getBoundingClientRect(), k = b.getBoundingClientRect();
                  return {surish: b.scrollWidth - b.clientWidth, tugma_ichida: r.left >= k.left - 1 && r.right <= k.right + 1}; }""")
              if _w == 360:
                  _inp3 = p3.evaluate("() => [...document.querySelectorAll('#qoldiqQatorlar input')].map(i => i.id)")
                  p3.fill("#" + _inp3[2], "2448639.5")
                  p3.wait_for_timeout(150)
                  p3.click("#qoldiq-saqla")
                  p3.wait_for_timeout(250)
                  p3.evaluate("""() => { const b = [...document.querySelectorAll('button')].filter(x => x.offsetParent !== null &&
                      /^(Ha, |Ha$|OK$|Tasdiqlash$)/.test(x.textContent.trim())); if (b.length) b[b.length - 1].click(); }""")
                  p3.wait_for_timeout(900)
                  _tor["tiyin"] = p3.evaluate("""() => ({k: [...document.querySelectorAll('#hisob-kartalari .hb-hisob')].map(k => k.textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').trim()),
                      j: document.getElementById('cash-balance-val').textContent.replace(/[\\s\\u00a0\\u202f]/g, '')})""")
              ctx3.close()
          check("U12 tor telefon 320 / 360 / 375 px: qoldiq oynasi gorizontal surilmaydi, «Saqlash» oyna ichida (review210 №4); Karta "
                "2 448 639,5 sanaldi — kartada «2 448 639,5», jami tiyin bilan (review210 №5)",
                all(_tor[w]["surish"] <= 0 and _tor[w]["tugma_ichida"] for w in (320, 360, 375))
                and bosh((_tor.get("tiyin") or {}).get("k", ["", "", ""])[2]) == "Karta2448639,5so'm"
                and ((_tor.get("tiyin") or {}).get("j") or "").endswith(",5so'm"), _tor)
          br.close()
    try:
        _ui()
    except Exception as _e:                 # noqa: BLE001
        check("U0 brauzer bo'limi xatosiz yakunlandi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    check("U11 sahifa JS xatosi yo'q", not XATOLAR, XATOLAR[:5])
    _srv.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
