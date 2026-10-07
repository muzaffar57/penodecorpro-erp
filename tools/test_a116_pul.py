#!/usr/bin/env python3
"""
test_a116_pul.py — kech116, A bosqich 2-qism: G1-03 («Pul oqimi» — HAQIQIY pul, egasi QARORI kech114) va G1-02
(«Xarajat» — BITTA ta'rif, «Tannarx» alohida). Server qismi: `services.get_pul_oqimi` / `_pul_oqimi_oraliq` /
`_kassa_qismlari`, `/api/finance/pul-oqimi`, «Korxona sog'ligi» pul oqimi bahosi, `get_monthly_report` →
`xarajat_tarkibi` / `tannarx_jami`.

NIMA UCHUN KERAK (audit kech114 — O'LCHANGAN, asl kod = `staging` 44c40ee)
  G1-03  «Pul oqimi» uch sahifada uch formula: Hisobotlar = daromad − jami xarajat (−1.6 mln), Dashboard = daromad −
         (xarajat + naqd xarid − transport) (−26.8 mln), Moliya = bugungi savdo − xarajat; hech biri mijoz haqiqatda
         to'lagan pul emas (13.4 mln tushgan kuni «Pul oqimi 0 so'm, Yaxshi»).
  G1-02  «Xarajat» Hisobotlar kartasida 3.3 mln, doirada 3.1 mln (transport, brak yo'q), Dashboard'da 4.3 mln (tannarx
         qo'shilgan); tannarx Hisobotlarda ko'rinmasdi (1.7 − 3.3 ≠ −2.6).
TALAB: pul oqimi = davrda olingan pul (mijoz to'lovlari − qaytarilgan pul + tayyor mahsulot sotuvi) − haqiqatda to'langan
  pul (naqd xarid, ta'minotchiga, hodimlarga, xarajatlar, transport, yetkazish ulushi, kassadan KPI / Ehson); nasiya xarid,
  boshlang'ich ombor va boshlang'ich balans — harakat EMAS; Toshkent kun / oy chegaralari; kassa bilan BITTA qoida (butun
  davr oqimi + boshlang'ich = kassa balansi; oy = kunlar yig'indisi); korxona chegarasi. Xarajat tarkibi yig'indisi =
  `jami_xarajat`; daromad − tannarx_jami − jami_xarajat = sof foyda.
BO'LIMLAR: P — pul oqimi (server, API); K — kassa bilan bir qoida; S — «Korxona sog'ligi»; X — xarajat ta'rifi; Z — xatolar.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI (yangi nomlar — `getattr`).
ISHLATISH: python3 tools/test_a116_pul.py
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "a116_pul_test"
_T = tempfile.mkdtemp(prefix="a116pul_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'a116_pul_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import services                                    # noqa: E402
from database import SessionLocal, tashkent_date, tashkent_oy_oraligi, tashkent_kun_oraligi   # noqa: E402
from models import (UserRole, Inventory, Project, Order, OrderType, Payment, FinishedProductSale,   # noqa: E402
                    InventoryPurchase, Supplier, SupplierPayment, ExpenseTransaction, TransportExpense, Delivery,
                    Employee, EmployeeAdvance, CashTransaction, MonthlyExpense, FinishedProductLoss)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HOLATLAR = []


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
        print(f"  ✗ {label}   {str(detail)[:700]}")


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
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    HOLATLAR.append((metod.upper() + " " + url.split("?")[0], r.status_code))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def xavfsiz(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return {"XATO": f"{type(e).__name__}: {e}"}


def teng(a, b, eps=0.005):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — davrlar (UTC, naive) va harakatlar ro'yxati
# ══════════════════════════════════════════════════════════════
BUGUN = tashkent_date()
OY_BOSHI, OY_OXIRI = tashkent_oy_oraligi(BUGUN.year, BUGUN.month)
KUN_BOSHI, KUN_OXIRI = tashkent_kun_oraligi(BUGUN)
T_BUGUN = datetime.utcnow()
T_OY = OY_BOSHI + timedelta(hours=1)             # oyning 1-kuni 01:00 (Toshkent)
T_CHEGARA = OY_BOSHI                             # oyning 1-kuni 00:00 (Toshkent) — shu oy
T_OTGAN = OY_BOSHI - timedelta(minutes=1)        # o'tgan oyning oxirgi kuni 23:59 (Toshkent)

s = SessionLocal()
s.add(Company(id=2, name="Pul116 B korxona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "pul116_admin", "Parol123!", UserRole.ADMIN, "Pul116 Admin", company_id=1)
    auth.create_user(s, "pul116_b", "Parol123!", UserRole.ADMIN, "Pul116 B", company_id=2)
PRJ = Project(company_id=1, client_name="Pul116 Mijoz", project_name="Pul116 loyiha", total_budget=0, total_paid=0)
PRJ2 = Project(company_id=2, client_name="Pul116 B mijoz", project_name="Pul116 B loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="Pul116 Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
MAT = Inventory(company_id=1, item_name="Pul116 Kley", unit="kg", stock_quantity=100, price_per_unit=10000,
                is_penoplast=False, category="Kimyoviy qo'shimchalar")
SUP = Supplier(company_id=1, name="Pul116 Ta'minotchi")
EMP = Employee(company_id=1, name="Pul116 Hodim", position="Kesuvchi")
s.add_all([PRJ, PRJ2, PENO, MAT, SUP, EMP])
s.commit()
ID = {"PRJ": PRJ.id, "PRJ2": PRJ2.id, "PENO": PENO.id, "MAT": MAT.id, "SUP": SUP.id, "EMP": EMP.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "pul116_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login (A)", _lr.status_code in (200, 302, 303), _lr.status_code)
C2 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr2 = req(C2, "post", "/login", data={"username": "pul116_b", "password": "Parol123!"}, follow_redirects=False)
check("0 login (B korxona)", _lr2.status_code in (200, 302, 303), _lr2.status_code)

_ro = req(C, "post", "/api/orders", json={
    "project_id": ID["PRJ"], "order_type": "product", "items": [
        {"name": "Pul116 D1", "category": "profil", "width": 20, "thickness": 10, "length": 100, "quantity": 10,
         "unit_price": 100000, "is_coated": False, "penoplast_id": ID["PENO"]}]})
OID = (js(_ro) or {}).get("id")
check("0 buyurtma (A) yaratildi", _ro.status_code == 200 and OID, (_ro.status_code, getattr(_ro, "text", "")[:200]))

# Harakatlar: (tur, summa — kassa ta'siri ishorasi bilan: + kirim, − chiqim, vaqt, izoh). `oqimga` — pul oqimiga kiradimi.
HARAKAT = []


def h(tur, tasir, vaqt, oqimga=True):
    HARAKAT.append({"tur": tur, "tasir": tasir, "vaqt": vaqt, "oqimga": oqimga})


s = SessionLocal()
o2 = Order(company_id=2, project_id=ID["PRJ2"], order_type=OrderType.PRODUCT, order_number="PUL116-B-1",
           total_amount=5000000, agreed_amount=5000000)
s.add(o2)
s.commit()
OID2 = o2.id
# ── kirim ──
for summa, vaqt in ((500000, T_BUGUN), (300000, T_OY), (-50000, T_BUGUN), (700000, T_OTGAN), (40000, T_CHEGARA)):
    s.add(Payment(order_id=OID, amount=summa, paid_at=vaqt))
    h("mijoz_tolovi", summa, vaqt)
s.add(FinishedProductSale(company_id=1, product_name="Pul116 TM", quantity=2, unit="dona", unit_price=60000,
                          total_amount=120000, cost_amount=40000, sold_at=T_BUGUN))
h("tayyor_sotuv", 120000, T_BUGUN)
# ── chiqim ──
s.add(InventoryPurchase(inventory_id=ID["MAT"], item_name="Pul116 Kley", quantity=20, unit="kg", price_per_unit=10000,
                        total_amount=200000, purchased_at=T_BUGUN, is_credit=False, supplier_id=ID["SUP"]))
h("xarid_naqd", -200000, T_BUGUN)
s.add(InventoryPurchase(inventory_id=ID["MAT"], item_name="Pul116 Kley", quantity=99.9, unit="kg", price_per_unit=10000,
                        total_amount=999000, purchased_at=T_BUGUN, is_credit=True, supplier_id=ID["SUP"]))
h("xarid_nasiya", -999000, T_BUGUN, oqimga=False)
s.add(InventoryPurchase(inventory_id=ID["MAT"], item_name="Pul116 Kley", quantity=88.8, unit="kg", price_per_unit=10000,
                        total_amount=888000, purchased_at=T_OY, is_credit=False, is_opening_stock=True))
h("boshlangich_ombor", -888000, T_OY, oqimga=False)
s.add(InventoryPurchase(inventory_id=ID["MAT"], item_name="Pul116 Kley", quantity=11.1, unit="kg", price_per_unit=10000,
                        total_amount=111000, purchased_at=T_OTGAN, is_credit=False))
h("xarid_naqd", -111000, T_OTGAN)
s.add(SupplierPayment(supplier_id=ID["SUP"], amount=150000, paid_at=T_OY))
h("taminotchiga", -150000, T_OY)
s.add(ExpenseTransaction(company_id=1, date=T_BUGUN, category="arenda", amount=400000, created_by="t116"))
h("xarajat", -400000, T_BUGUN)
s.add(ExpenseTransaction(company_id=1, date=T_OY, category="boshqa", amount=25000.55, created_by="t116"))
h("xarajat", -25000.55, T_OY)
s.add(TransportExpense(company_id=1, amount=60000, expense_date=T_BUGUN))
h("transport", -60000, T_BUGUN)
s.add(Delivery(order_id=OID, delivery_number="PUL116-Y1", delivered_at=T_BUGUN, transport_cost=80000,
               transport_payer="company"))
h("yetkazish", -80000, T_BUGUN)
s.add(Delivery(order_id=OID, delivery_number="PUL116-Y2", delivered_at=T_OY, transport_cost=30000, transport_payer="split"))
h("yetkazish", -15000, T_OY)
s.add(Delivery(order_id=OID, delivery_number="PUL116-Y3", delivered_at=T_BUGUN, transport_cost=45000, transport_payer="client"))
s.add(EmployeeAdvance(employee_id=ID["EMP"], amount=90000, date=T_BUGUN))
h("hodimga", -90000, T_BUGUN)
s.add(CashTransaction(company_id=1, category="usta_kpi", amount=-70000, created_at=T_BUGUN))
h("kassadan_qolda", -70000, T_BUGUN)
s.add(CashTransaction(company_id=1, category="boshlangich", amount=5000000, created_at=T_OY))
h("boshlangich_balans", 5000000, T_OY, oqimga=False)
# eski oylik shakl: shu oy — arenda (tranzaksiyasi bor — SANALMAYDI) va elektr (tranzaksiyasi yo'q — oyning 1-kuniga)
s.add(MonthlyExpense(company_id=1, year=BUGUN.year, month=BUGUN.month, arenda=999999, elektr=33000, tushlik=0, soliqlar=0))
h("eski_oylik", -33000, OY_BOSHI)
s.add(FinishedProductLoss(company_id=1, product_name="Pul116 TM", quantity=1, unit="dona", cost_amount=12000,
                          reason="Omborda sindi", lost_at=T_BUGUN))
# ── B korxona — A ning pul oqimiga KIRMASLIGI kerak ──
s.add(Payment(order_id=OID2, amount=1000000, paid_at=T_BUGUN))
s.add(ExpenseTransaction(company_id=2, date=T_BUGUN, category="boshqa", amount=777000, created_by="t116"))
s.add(CashTransaction(company_id=2, category="usta_kpi", amount=-66000, created_at=T_BUGUN))
s.commit()
s.close()


def kutilgan(boshi, oxiri):
    """Harakatlar ro'yxatidan mustaqil hisob: davrdagi kirim / chiqim (faqat pul oqimiga kiradiganlar)."""
    kirim = chiqim = 0.0
    for x in HARAKAT:
        if not x["oqimga"]:
            continue
        if (boshi is None or x["vaqt"] >= boshi) and (oxiri is None or x["vaqt"] < oxiri):
            if x["tasir"] >= 0 or x["tur"] == "mijoz_tolovi":
                kirim += x["tasir"]          # qaytarilgan pul (manfiy to'lov) kirimni kamaytiradi
            else:
                chiqim += -x["tasir"]
    return round(kirim, 2), round(chiqim, 2)


def pul_oqimi(**k):
    fn = getattr(services, "get_pul_oqimi", None)
    if fn is None:
        return {"XATO": "services.get_pul_oqimi yo'q (asl kod)"}
    d = SessionLocal()
    try:
        return xavfsiz(fn, d, company_id=k.pop("company_id", 1), **k)
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════
section("P. Pul oqimi — haqiqiy pul (server)")
# ══════════════════════════════════════════════════════════════
kO, cO = kutilgan(OY_BOSHI, OY_OXIRI)
po = pul_oqimi(year=BUGUN.year, month=BUGUN.month)
check(f"P1 shu oy: kirim {kO:,.2f}, chiqim {cO:,.2f} — mustaqil hisob bilan AYNAN (qaytarilgan pul ayrilgan; nasiya xarid, "
      f"boshlang'ich ombor, boshlang'ich balans, mijoz to'lagan transport, B korxona — YO'Q; tiyin)",
      teng(po.get("kirim"), kO) and teng(po.get("chiqim"), cO) and teng(po.get("balans"), round(kO - cO, 2)), (po, kO, cO))
_qk = {q.get("kalit"): q.get("summa") for q in (po.get("kirim_qatorlar") or []) + (po.get("chiqim_qatorlar") or [])}
_kt = {}
for x in HARAKAT:
    if x["oqimga"] and OY_BOSHI <= x["vaqt"] < OY_OXIRI:
        _kt[x["tur"]] = _kt.get(x["tur"], 0) + x["tasir"]
check("P2 tarkib qatorlari: mijoz to'lovlari, TM sotuvi, naqd xarid, ta'minotchiga, hodimlarga, xarajatlar (eski oylik "
      "shakl bilan), transport, yetkazish ulushi, kassadan (KPI / Ehson)",
      teng(_qk.get("mijoz_tolovlari"), _kt.get("mijoz_tolovi", 0)) and teng(_qk.get("tayyor_sotuv"), _kt.get("tayyor_sotuv", 0))
      and teng(_qk.get("xomashyo_naqd"), -_kt.get("xarid_naqd", 0)) and teng(_qk.get("taminotchiga"), -_kt.get("taminotchiga", 0))
      and teng(_qk.get("hodimlarga"), -_kt.get("hodimga", 0))
      and teng(_qk.get("xarajatlar"), -_kt.get("xarajat", 0) - _kt.get("eski_oylik", 0))
      and teng(_qk.get("transport"), -_kt.get("transport", 0)) and teng(_qk.get("yetkazish_transport"), -_kt.get("yetkazish", 0))
      and teng(_qk.get("kassadan_qolda"), -_kt.get("kassadan_qolda", 0)), (_qk, _kt))
kK, cK = kutilgan(KUN_BOSHI, KUN_OXIRI)
pk = pul_oqimi(sana=BUGUN)
check(f"P3 bugun (Toshkent kuni): kirim {kK:,.2f}, chiqim {cK:,.2f}", teng(pk.get("kirim"), kK) and teng(pk.get("chiqim"), cK)
      and (pk.get("davr") or {}).get("tur") == "kun", (pk, kK, cK))
kP, cP = kutilgan(*tashkent_oy_oraligi(*((BUGUN.year, BUGUN.month - 1) if BUGUN.month > 1 else (BUGUN.year - 1, 12))))
_py, _pm = ((BUGUN.year, BUGUN.month - 1) if BUGUN.month > 1 else (BUGUN.year - 1, 12))
pp = pul_oqimi(year=_py, month=_pm)
check(f"P4 Toshkent oy chegarasi: o'tgan oy 23:59 dagi to'lov (700 000) va xarid — o'tgan oyda; 1-kun 00:00 dagi to'lov "
      f"(40 000) — shu oyda (o'tgan oy: kirim {kP:,.0f}, chiqim {cP:,.0f})",
      teng(pp.get("kirim"), kP) and teng(pp.get("chiqim"), cP) and kP == 700000 and cP == 111000, (pp, kP, cP))
# kunlar yig'indisi = oy
_kun, _jk, _jc, _xato = OY_BOSHI, 0.0, 0.0, None
_d0 = datetime(BUGUN.year, BUGUN.month, 1).date()
_sana = _d0
while _sana.month == BUGUN.month:
    _r = pul_oqimi(sana=_sana)
    if "XATO" in _r:
        _xato = _r
        break
    _jk += float(_r.get("kirim") or 0)
    _jc += float(_r.get("chiqim") or 0)
    _sana = _sana + timedelta(days=1)
check("P5 oyning har kuni pul oqimi yig'indisi = oy pul oqimi (eski oylik shakl — 1-kunda; hech narsa ikki marta / tushib "
      "qolmaydi)", _xato is None and teng(_jk, po.get("kirim")) and teng(_jc, po.get("chiqim")), (_xato, _jk, _jc, po.get("kirim"),
                                                                                                   po.get("chiqim")))
pB = pul_oqimi(year=BUGUN.year, month=BUGUN.month, company_id=2)
check("P6 B korxona: faqat o'zi (to'lov 1 000 000, xarajat 777 000, KPI 66 000)",
      teng(pB.get("kirim"), 1000000) and teng(pB.get("chiqim"), 843000), pB)
_bo = pul_oqimi(year=2020, month=1)
check("P7 harakatsiz davr: 0 / 0, `harakat_bor` = False", teng(_bo.get("kirim"), 0) and teng(_bo.get("chiqim"), 0)
      and _bo.get("harakat_bor") is False, _bo)

section("P'. API — /api/finance/pul-oqimi")
r = req(C, "get", f"/api/finance/pul-oqimi?year={BUGUN.year}&month={BUGUN.month}")
check("P8 API oy — server funksiyasi bilan AYNAN", r.status_code == 200 and teng(js(r).get("balans"), po.get("balans"))
      and teng(js(r).get("kirim"), po.get("kirim")), (r.status_code, js(r)))
r0 = req(C, "get", "/api/finance/pul-oqimi")
check("P9 API parametrsiz — joriy (Toshkent) oy", r0.status_code == 200 and teng(js(r0).get("balans"), po.get("balans"))
      and (js(r0).get("davr") or {}).get("month") == BUGUN.month, (r0.status_code, js(r0).get("davr")))
rk = req(C, "get", f"/api/finance/pul-oqimi?sana={BUGUN.isoformat()}")
check("P10 API kun (sana=)", rk.status_code == 200 and teng(js(rk).get("balans"), pk.get("balans")), (rk.status_code, js(rk)))
_yom = [req(C, "get", "/api/finance/pul-oqimi?year=2026&month=13").status_code,
        req(C, "get", "/api/finance/pul-oqimi?year=abc&month=9").status_code,
        req(C, "get", "/api/finance/pul-oqimi?year=2026").status_code,
        req(C, "get", "/api/finance/pul-oqimi?sana=2026-13-40").status_code,
        req(C, "get", "/api/finance/pul-oqimi?sana=1900-01-01").status_code]
check("P11 noto'g'ri davr — 400 (oy 13, harf, oysiz yil, noto'g'ri sana, chegaradan tashqari yil)", _yom == [400] * 5, _yom)
rB = req(C2, "get", f"/api/finance/pul-oqimi?year={BUGUN.year}&month={BUGUN.month}")
check("P12 API B korxona — faqat o'z pul oqimi", rB.status_code == 200 and teng(js(rB).get("kirim"), 1000000), js(rB))
C3 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
check("P13 API kirishsiz — 401", req(C3, "get", "/api/finance/pul-oqimi").status_code == 401)

# ══════════════════════════════════════════════════════════════
section("K. Kassa bilan BITTA qoida")
# ══════════════════════════════════════════════════════════════
_kas = js(req(C, "get", "/api/finance/cash-balance"))
_hammasi = sum(x["tasir"] for x in HARAKAT if x["oqimga"] or x["tur"] == "boshlangich_balans")
check(f"K1 kassa balansi — mustaqil hisob bilan AYNAN ({round(_hammasi):,}; refaktordan keyin o'zgarmadi)",
      _kas.get("balance") == round(_hammasi), (_kas, _hammasi))
_or = getattr(services, "_pul_oqimi_oraliq", None)
_d = SessionLocal()
_butun = xavfsiz(_or, _d, None, None, company_id=1) if _or else {"XATO": "yo'q"}
_d.close()
check("K2 butun davr pul oqimi + boshlang'ich balans = kassa balansi", "XATO" not in _butun
      and round(float(_butun.get("balans") or 0) + 5000000) == _kas.get("balance"), (_butun.get("balans"), _kas.get("balance")))

# ══════════════════════════════════════════════════════════════
section("S. «Korxona sog'ligi» — pul oqimi bahosi haqiqiy puldan")
# ══════════════════════════════════════════════════════════════


def sogliq(cid=1):
    d = SessionLocal()
    try:
        return services.get_business_health(d, company_id=cid)
    except Exception as e:                 # noqa: BLE001
        return {"XATO": repr(e)}
    finally:
        d.close()


hs = sogliq(1)
_ps = (hs.get("sabablar") or {}).get("pul_oqimi", "")
_farq = f"{abs(float(po.get('balans') or 0)):,.0f}".replace(",", " ")
check(f"S1 shu oy chiqim kirimdan ko'p, kassada pul bor → «orange», sabab «… {_farq} so'm ko'p (kassada pul bor)» "
      f"(asl: sof foyda ishorasi)", float(po.get("balans") or 0) < 0 and hs.get("pul_oqimi") == "orange"
      and _ps == f"Bu oy chiqim kirimdan {_farq} so'm ko'p (kassada pul bor)", (hs.get("pul_oqimi"), _ps, po.get("balans")))
_asl_po, _asl_kas = getattr(services, "get_pul_oqimi", None), services.get_cash_balance


def sogliq_soxta(balans, kassa, harakat=True):
    services.get_pul_oqimi = lambda db, y=None, m=None, sana=None, company_id=None: {
        "kirim": max(balans, 0), "chiqim": max(-balans, 0), "balans": balans, "harakat_bor": harakat}
    services.get_cash_balance = lambda db, company_id=None: {"balance": kassa}
    try:
        return sogliq(1)
    finally:
        if _asl_po is not None:
            services.get_pul_oqimi = _asl_po
        else:
            delattr(services, "get_pul_oqimi")
        services.get_cash_balance = _asl_kas


_hl = [sogliq_soxta(13400000, 0), sogliq_soxta(0, -5), sogliq_soxta(-1000, -1), sogliq_soxta(0, 0, harakat=False)]
check("S2 kirim ≥ chiqim — «green» («Bu oy kirim chiqimdan 13 400 000 so'm ko'p»); 0 — ham yashil; chiqim ko'p va kassa "
      "manfiy — «red»; harakat yo'q — «gray» («Bu oy pul harakati hali yo'q»)",
      [x.get("pul_oqimi") for x in _hl] == ["green", "green", "red", "gray"]
      and (_hl[0].get("sabablar") or {}).get("pul_oqimi") == "Bu oy kirim chiqimdan 13 400 000 so'm ko'p"
      and (_hl[2].get("sabablar") or {}).get("pul_oqimi") == "Bu oy chiqim kirimdan 1 000 so'm ko'p, kassa ham manfiy"
      and (_hl[3].get("sabablar") or {}).get("pul_oqimi") == "Bu oy pul harakati hali yo'q",
      [(x.get("pul_oqimi"), (x.get("sabablar") or {}).get("pul_oqimi")) for x in _hl])
check("S3 bo'sh korxona (3) — «gray» (harakat yo'q)", sogliq(3).get("pul_oqimi") == "gray"
      and (sogliq(3).get("sabablar") or {}).get("pul_oqimi") == "Bu oy pul harakati hali yo'q", sogliq(3))

# ══════════════════════════════════════════════════════════════
section("X. «Xarajat» — BITTA ta'rif, «Tannarx» alohida")
# ══════════════════════════════════════════════════════════════
# alohida buyurtma (yuqoridagisida soxta yuk xatlari bor — «Tayyor» uni qisman yakunlaydi)
_ro2 = req(C, "post", "/api/orders", json={
    "project_id": ID["PRJ"], "order_type": "product", "items": [
        {"name": "Pul116 D2", "category": "profil", "width": 20, "thickness": 10, "length": 100, "quantity": 12,
         "unit_price": 90000, "is_coated": False, "penoplast_id": ID["PENO"]}]})
OID_R = (js(_ro2) or {}).get("id")
_rdy = req(C, "post", f"/api/orders/{OID_R}/ready") if OID_R else _Xato(RuntimeError("buyurtma yo'q"))
check("X0 buyurtma «Tayyor» (daromad va tannarx)", _rdy.status_code == 200, (_rdy.status_code, getattr(_rdy, "text", "")[:200]))
rep = js(req(C, "get", f"/api/finance/report?year={BUGUN.year}&month={BUGUN.month}"))
tark = rep.get("xarajat_tarkibi")
_tk = {t.get("kalit"): float(t.get("summa") or 0) for t in (tark or [])}
_x = rep.get("xarajatlar") or {}
_q = rep.get("qoshimcha_xarajatlar") or {}
check("X1 `xarajat_tarkibi` — 8 guruh (doimiy, qo'shimcha, transport, brak, TM yo'qotishi, usta KPI, ehson, hodimlar)",
      isinstance(tark, list) and list(_tk) == ["doimiy", "qoshimcha", "transport", "brak", "tm_yoqotish", "usta_kpi", "ehson",
                                                 "hodimlar"], tark)
check("X2 har guruh hisobot maydoni bilan AYNAN (transport 60 000 + 80 000 + 15 000; TM yo'qotishi 12 000; eski oylik "
      "elektr 33 000 doimiyda)",
      teng(_tk.get("doimiy"), float(_x.get("arenda", 0)) + float(_x.get("elektr", 0)) + float(_x.get("tushlik", 0))
           + float(_x.get("soliqlar", 0)), 0.011)
      and teng(_tk.get("qoshimcha"), sum(float(v or 0) for v in _q.values()), 0.011)
      and teng(_tk.get("transport"), rep.get("transport_xarajat"), 0.011) and teng(_tk.get("transport"), 155000)
      and teng(_tk.get("brak"), rep.get("brak_xarajat"), 0.5) and teng(_tk.get("tm_yoqotish"), 12000)
      and teng(_tk.get("usta_kpi"), rep.get("usta_kpi_xarajat"), 0.011) and teng(_tk.get("ehson"), rep.get("ehson_xarajat"), 0.011)
      and teng(_tk.get("hodimlar"), rep.get("hodimlar_moslashuvchan_xarajat"), 0.011) and teng(_x.get("elektr"), 33000), (_tk, rep.get("transport_xarajat")))
check("X3 tarkib yig'indisi = «Xarajat» (`jami_xarajat`)", _tk and teng(sum(_tk.values()), rep.get("jami_xarajat"), 0.05),
      (sum(_tk.values()), rep.get("jami_xarajat")))
_tn = rep.get("tannarx_jami")
check("X4 `tannarx_jami` = buyurtmalar tannarxi + tayyor mahsulot sotuvi tannarxi (40 000)",
      _tn is not None and teng(_tn, float(rep.get("ishlab_chiqarish_xarajat") or 0) + 40000, 0.011)
      and float(rep.get("ishlab_chiqarish_xarajat") or 0) > 0, (_tn, rep.get("ishlab_chiqarish_xarajat")))
check("X5 Daromad − Tannarx − Xarajat = Sof foyda (1 so'm ichida)", _tn is not None
      and abs(float(rep.get("daromad") or 0) - float(_tn) - float(rep.get("jami_xarajat") or 0)
              - float(rep.get("sof_foyda") or 0)) <= 1.0,
      (rep.get("daromad"), _tn, rep.get("jami_xarajat"), rep.get("sof_foyda")))
_hist = js(req(C, "get", "/api/finance/history?months=1"))
_cur = _hist[-1] if isinstance(_hist, list) and _hist else {}
check("X6 `/api/finance/history` joriy oyda ham `xarajat_tarkibi` / `tannarx_jami` (Hisobotlar sahifasi manbasi)",
      isinstance(_cur.get("xarajat_tarkibi"), list) and teng(_cur.get("tannarx_jami"), _tn, 0.011), _cur.get("tannarx_jami"))
_repB = js(req(C2, "get", f"/api/finance/report?year={BUGUN.year}&month={BUGUN.month}"))
check("X7 B korxona: xarajat tarkibi faqat o'ziniki (qo'shimcha 777 000)",
      teng({t.get("kalit"): t.get("summa") for t in (_repB.get("xarajat_tarkibi") or [])}.get("qoshimcha"), 777000),
      _repB.get("xarajat_tarkibi"))

# ══════════════════════════════════════════════════════════════
section("Z. Xatolar")
# ══════════════════════════════════════════════════════════════
_5xx = [x for x in HOLATLAR if x[1] >= 500]
check("Z1 API 5xx yo'q", not _5xx, _5xx[:5])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
