#!/usr/bin/env python3
"""
test_qaytarish_moliya.py — kech102 darvozasi (2026-09-27, 144-band + K102-1).

FOYDALANUVCHI QARORI (kech102): qaytarish hisobotda "Qaytarish oyida" (o'tgan oylar O'ZGARMAYDI, qaytarish bo'lgan oyda
alohida qator: daromad −qaytarilgan pul, tannarx −omborga qaytgan mahsulot tannarxi); usta KPI — "Ha, yo'qotilgan
foydaga" (qaytarilgan pul − omborga qaytgan tannarx).

O'LCHANGAN (asl kod `c89a22e`, SQLite = PG, `work/probe144.py`): mijoz topshirilgan mahsulotni omborga qaytarsa uning
tannarxi IKKI marta hisoblanardi (buyurtma tannarxida ham, qayta sotilganda ham — profil +21 000, panel +41 100,
tayyor mahsulotdan +18 000, MRP +9 000; topshirilmagan "Ortiqcha" — profil +28 000, panel +54 800, MRP +12 000 —
K102-1); "Pul qaytdi" daromadni BUYURTMA yakunlangan (o'tgan) oyda kamaytirardi; usta KPI qaytgan mahsulot tannarxini
ham ustaga yuklardi.

Bo'limlar:
  A — shakl (profil / panel / tayyor mahsulotdan / MRP) × qaytarish (A omborga + pul + qayta sotuv, B omborga emas + pul,
      C brak, D omborga pulsiz + qayta sotuv): buyurtma foydasi (hozirgi holat), oylik hisobot (buyurtma qatori +
      "qaytarish" qatori), hisobotdagi jami tannarx = HAQIQIY sarf (korxonadan chiqib ketgan tovar qiymati), usta KPI
      (oylik, yillik, tafsilot), ehson, kunlik, bugun, loyihalar, bo'lingan hisobot, buyurtma foyda oynasi.
  R — oy chegarasi: buyurtma O'TGAN oyda yakunlangan, qaytarish shu oyda — o'tgan oy AYNAN, shu oy alohida qator; usta
      KPI (oylik / yillik / tafsilot / keshbek / sovg'a davri), ehson, kunlik.
  E — qaytarish «Tayyor» dan OLDIN — buyurtmaning o'z qatorida (qaytarish qatori yo'q).
  O — "Ortiqcha" (topshirilmagan) qaytarish: MRP (K102-1) va profil — tannarx = haqiqiy sarf; NAZORAT buyurtma bilan.
  D — qaytarishni o'chirish (22-band) — hammasi qaytarishdan OLDINGI holatga AYNAN.
  K — korxona: begona korxona yozuvi (Core — buyurtma korxonasi boshqa) hisobga olinmaydi; B korxonasi qaytarishi A da yo'q.
  U — `finance.html` "Qaytarishlar" guruhi (node).
  X — 5xx yo'q.   S — statik.

Ishlatish:
    python3 tools/test_qaytarish_moliya.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_qaytarish_moliya.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qaytarish_moliya_test"
_T = tempfile.mkdtemp(prefix="qaytarish_moliya_")
_DB = os.path.join(_T, "qaytarish_moliya_test.db")

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
from datetime import datetime, timedelta           # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
    import crud                                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, OrderItem, Order, Recipe, RecipeIngredient, Master, User,
    FinishedProduct, StockSource, ProductionStatus, ReturnItem, ReturnReason, OrderStatus, OrderType,
)
from production_models import Company               # noqa: E402
from models import GiftPeriod                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

crud.PUL_TAKROR_SONIYA = 0      # bir xil summali to'lovlar (turli buyurtmalarda) takror deb yutilmasin

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
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


XATOLAR_5XX = []


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    if r.status_code >= 500:
        XATOLAR_5XX.append((metod, url, r.status_code, str(getattr(r, "text", ""))[:200]))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def taxminan(a, b, eps=1e-6):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def tartibda(src, *qismlar):
    """Qismlar src ichida AYNAN shu tartibda uchraydimi (find — topilmasa False)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
_db.add(Company(id=2, name="QM Korxona B"))          # PG: users / orders company_id FK — B korxonasi oldin
_db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "QM_admin", "Parol123!", UserRole.ADMIN, "QM Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="OY Penoplast", unit="blok", stock_quantity=100_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="OY Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000,
                 category="Kimyo")
QUM = Inventory(company_id=1, item_name="OY Qum", unit="kg", stock_quantity=100_000, price_per_unit=1_000,
                category="Kimyo")
_db.add_all([PENO, KLEY, QUM])
_db.flush()
REC = Recipe(company_id=1, name="OY retsept", batch_size_kg=100.0)
RLOY = Recipe(company_id=1, name="OY loy sotish", batch_size_kg=100.0)
_db.add_all([REC, RLOY])
_db.flush()
_db.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
_db.add(RecipeIngredient(recipe_id=RLOY.id, inventory_id=QUM.id, quantity_kg=100.0))
# Tayyor mahsulot (ombordagi zaxira) — buyurtma detali shundan olinadi (S8)
TMP = FinishedProduct(company_id=1, name="OY TM profil", category="profil", width=20, thickness=10, is_coated=True,
                      quantity=1_000, produced_quantity=1_000, unit="metr", unit_price=0, cost_price=3_000_000,
                      source=StockSource.PRODUCED, penoplast_id=PENO.id, recipe_id=REC.id, unit_volume_m3=0.01,
                      unit_loy_kg=0.5, production_status=ProductionStatus.READY)
_db.add(TMP)
_db.commit()
ID = {"PENO": PENO.id, "KLEY": KLEY.id, "QUM": QUM.id, "REC": REC.id, "RLOY": RLOY.id, "TMP": TMP.id}
UID = _db.query(User.id).filter(User.username == "QM_admin").first()[0]
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "QM_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom(p="OY"):
    _n[0] += 1
    return f"{p}{_n[0]}"




def _asosiy_yonalish_id():
    """kech117 (A2): korxonaning asosiy yo'nalishi («Penoplast»). Asl kodda (yo'nalishlar yo'q) — None."""
    _f117 = getattr(crud, "standart_yonalish", None)
    if _f117 is None:
        return None
    _d117 = SessionLocal()
    try:
        _y117 = _f117(_d117, 1)
        _d117.commit()
        return _y117.id if _y117 is not None else None
    finally:
        _d117.close()


YON_ASOSIY = _asosiy_yonalish_id()
# kech117 (A2): MRP turi ham asosiy yo'nalishga (ilgari «Penoplast va boshqa» turi) — shunda 4 shaklning hammasida
# asosiy yo'nalish daromadi / tannarxi o'zgarishi hisobot bilan bir xil bo'lishi kerak
PT = (js(req(C, "post", "/api/production/product-types", json=dict({
    "name": "OY Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"}, **({"yonalish_id": YON_ASOSIY} if YON_ASOSIY else {})))) or {}).get("id")
BOM = (js(req(C, "post", "/api/production/boms", json={
    "product_type_id": PT, "variant_name": "Asosiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["QUM"], "quantity": 3}]})) or {}).get("id")


def ishlab(oid, iid, miqdor):
    """MRP detali uchun ishlab chiqarish (boshlash + yakunlash) — mahsulot shu detalga band."""
    r = req(C, "post", "/api/production/orders", json={
        "product_type_id": PT, "bom_id": BOM, "quantity": miqdor, "source_type": "customer_order",
        "source_order_id": oid, "source_order_item_id": iid})
    po = ((js(r) or {}).get("production_order") or {}).get("id") if isinstance(js(r), dict) else None
    if not po:
        return None
    for q in ("start", "complete"):
        if req(C, "post", f"/api/production/orders/{po}/{q}").status_code != 200:
            return None
    return po


def tm_qoldiq():
    s = SessionLocal()
    try:
        return round(float(s.get(FinishedProduct, ID["TMP"]).quantity or 0), 6)
    finally:
        s.close()


def muhit():
    """Har yo'l — alohida loyiha (mijoz) va usta (KPI 10 %)."""
    n = nom("M")
    s = SessionLocal()
    try:
        p = Project(company_id=1, client_name=f"{n} Mijoz", project_name=f"{n} loyiha", total_budget=0, total_paid=0)
        m = Master(company_id=1, name=f"{n} Usta", phone="+99891" + str(1_000_000 + _n[0]).zfill(7),
                   kpi_percent=10.0, is_active=True)
        s.add_all([p, m])
        s.commit()
        return p.id, m.id, f"{n} Mijoz"
    finally:
        s.close()


# Shakllar: (detallar, yetkaziladi {detal indeksi: miqdor}, kelishilgan, oldindan to'lov, loy reja)
def _profil(n=10.0, narx=50_000):
    return {"category": "profil", "width": 20, "thickness": 10, "length": n, "quantity": 10, "unit_price": narx,
            "is_coated": True, "penoplast_id": ID["PENO"], "recipe_id": ID["REC"]}


def _panel(n=10.0, narx=30_000):
    return {"category": "panel", "width": 50, "thickness": 5, "quantity": n, "unit_price": narx,
            "is_coated": True, "penoplast_id": ID["PENO"], "recipe_id": ID["REC"]}


def _tm_profil(n=10.0, narx=40_000):
    return {"category": "profil", "width": 20, "thickness": 10, "length": n, "quantity": 1, "unit_price": narx,
            "is_coated": True, "penoplast_id": ID["PENO"], "finished_product_id": ID["TMP"]}


def _mrp(n=10.0, narx=100_000):
    return {"category": "mrp_product", "quantity": n, "unit_price": narx, "is_coated": False, "penoplast_id": None,
            "product_type_id": PT}


def _loy_sotish(kg=20.0, narx=5_000):
    return {"category": "loy_sotish", "quantity": kg, "unit_price": narx, "is_coated": False,
            "penoplast_id": None, "recipe_id": ID["RLOY"]}


SHAKLLAR = {
    "S1 profil 4/10": ([_profil()], {0: 4}, None, None, 10.0),
    "S2 chegirmali 4/10": ([_profil()], {0: 4}, 450_000, None, 10.0),
    "S3 oldindan to'langan 4/10": ([_profil()], {0: 4}, None, 500_000, 10.0),
    "S4 panel 3/10": ([_panel()], {0: 3}, None, None, 6.0),
    "S5 ikki detal (10/10 + 0/10)": ([_profil(), _panel()], {0: 10}, None, 100_000, 20.0),
    "S6 loy sotish 8/20": ([_loy_sotish()], {0: 8}, None, None, 0.0),
    "S7 tiyinli 3/7": ([_profil(7.0, 33_333.33)], {0: 3}, None, 150_000.55, 7.0),
    "S8 tayyor mahsulotdan 4/10": ([_tm_profil()], {0: 4}, None, None, 0.0),
    "S9 MRP 4/10": ([_mrp()], {0: 4}, None, None, 0.0),
}


def buyurtma(pid, mid, detallar, agreed, loy):
    items = []
    for d in detallar:
        x = dict(d)
        x["name"] = nom("D")
        items.append(x)
    tana = {"project_id": pid, "order_type": "product", "loy_kg": loy, "recipe_id": ID["REC"], "master_id": mid,
            "items": items}
    if agreed is not None:
        tana["agreed_amount"] = agreed
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    d = js(r) or {}
    oid = d.get("id") if isinstance(d, dict) else None
    s = SessionLocal()
    try:
        ids = [x[0] for x in s.query(OrderItem.id).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        s.close()
    return oid, ids


def yuk(oid, iid, miqdor):
    r = req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": nom("yuk"),
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
    return r.status_code


def tolov(oid, summa):
    r = req(C, "post", "/api/payments", json={"order_id": oid, "amount": summa, "payment_type": "partial",
                                               "payment_method": "naqd", "notes": nom("tolov")})
    return r.status_code


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if not o:
            return None
        return {"status": o.status.value, "del": bool(o.is_deleted), "total": round(float(o.total_amount or 0), 2),
                "agreed": (round(float(o.agreed_amount), 2) if o.agreed_amount is not None else None),
                "paid": round(float(o.paid_amount or 0), 2), "debt": round(float(o.debt_amount or 0), 2),
                "pay_status": o.payment_status.value if o.payment_status else None, "archived": bool(o.is_archived),
                "closed_at": o.closed_at, "completed_at": o.completed_at, "notes": o.notes,
                "actual_loy": o.actual_loy_kg, "stock_returned": bool(o.stock_returned),
                "json": getattr(o, "ochirish_yopish_json", None),
                "items": [(i.id, i.quantity, i.length, round(float(i.unit_price or 0), 2), round(float(i.total_price or 0), 2))
                          for i in o.items]}
    finally:
        s.close()


def ombor():
    """Xomashyo qoldiqlari va tayyor mahsulot (erkin / band) — MRP mahsulotlari ham (OY Travertin)."""
    s = SessionLocal()
    try:
        d = {k: round(float(s.get(Inventory, ID[k]).stock_quantity), 6) for k in ("PENO", "KLEY", "QUM")}
        d["TMP"] = round(float(s.get(FinishedProduct, ID["TMP"]).quantity or 0), 6)
        _mrp_tm = s.query(FinishedProduct).filter(FinishedProduct.product_type_id == PT).all() if PT else []
        d["MRP_TM"] = round(sum(float(f.quantity or 0) for f in _mrp_tm), 6)
        d["MRP_BAND"] = round(sum(float(f.reserved_quantity or 0) for f in _mrp_tm), 6)
        return d
    finally:
        s.close()


def ombor_farq(a, b):
    return {k: round(b[k] - a[k], 6) for k in a}


def korsatkich(mid, mijoz):
    s = SessionLocal()
    n = datetime.utcnow() + timedelta(hours=5)      # kech105: hisobot yil / oy / kuni — Toshkent devor soati
    try:
        with contextlib.redirect_stdout(_quiet):
            rep = services.get_monthly_report(s, n.year, n.month, company_id=1)
            kpi = services.calculate_monthly_master_kpi(s, n.year, n.month, company_id=1)
            yil = crud.get_masters_kpi_report(s, n.year, include_inactive=True, company_id=1)
            kun = services.get_daily_finance_summary(s, n.date(), company_id=1)
            ch = services.get_chart_data(s, company_id=1)
            top = services.get_top_customers_report(s, days=90, limit=500, company_id=1)
            ehs = services.calculate_monthly_ehson(s, n.year, n.month, company_id=1)
        _usta = mijoz.split()[0] + " Usta"
        uk = [b for b in (kpi.get("breakdown") or []) if b.get("master_name") == _usta]
        uy = [r for r in (yil.get("masters") or []) if r.get("name") == _usta]
        tm = [t for t in top if (t.get("client_name") or t.get("name")) == mijoz]
        sav = kun.get("savdo") or kun.get("sales") or {}
        return {
            "rep_soni": rep.get("buyurtmalar_soni"), "rep_daromad": rep.get("daromad_buyurtmalardan"),
            "rep_xarajat": round(float(rep.get("ishlab_chiqarish_xarajat") or 0), 2),
            "rep_metr": rep.get("jami_metr"), "rep_m2": rep.get("jami_m2"), "rep_dona": rep.get("jami_dona"),
            "rep_bonus": rep.get("qoplamachi_bonus_avtomatik"), "rep_usta_kpi": rep.get("usta_kpi_xarajat"),
            "rep_b_foyda": rep.get("buyurtmalar_foydasi"),
            "kpi_oy": (uk[0].get("monthly_profit"), uk[0].get("kpi_amount")) if uk else None,
            "kpi_yil": ((uy[0].get("yearly_sales"), uy[0].get("yearly_profit"), uy[0].get("gift_amount"),
                         uy[0].get("orders_count")) if uy else None),
            "kun": (sav.get("orders_count"), round(float(sav.get("total") or 0), 2)),
            "ch_revenue": round(float(ch["finance"]["total_revenue"]), 2),
            "ch_budget": round(float(ch["finance"]["total_budget"]), 2),
            "top_mijoz": (round(float(tm[0].get("revenue") or 0), 2), tm[0].get("orders_count")) if tm else None,
            "ehson_foyda": ehs.get("monthly_profit"),
        }
    finally:
        s.close()


def farq(a, b):
    """Umumiy (korxona bo'yicha) ko'rsatkichlar — son farqi; usta / mijoz ko'rsatkichlari — keyingi qiymat."""
    o = {}
    for k in a:
        if k in ("kpi_oy", "kpi_yil", "top_mijoz"):
            o[k] = b[k]
        elif isinstance(a[k], tuple):
            o[k] = tuple(round((y or 0) - (x or 0), 2) for x, y in zip(a[k], b[k]))
        else:
            o[k] = round(float(b[k] or 0) - float(a[k] or 0), 2)
    return o


def reja(oid):
    d = js(req(C, "get", f"/api/orders/{oid}")) or {}
    return d.get("ochirish") if isinstance(d, dict) else None


def ochir(oid, actual=None):
    url = f"/api/orders/{oid}" + (f"?actual_loy_kg={actual}" if actual is not None else "")
    r = req(C, "delete", url)
    return r.status_code, (js(r) or {})


def tiklash(oid):
    return req(C, "post", f"/api/orders/{oid}/restore").status_code


def tayyor(oid, loy):
    r = req(C, "post", f"/api/orders/{oid}/ready", params=({"loy_kg": str(loy)} if loy else None))
    return r.status_code, (js(r) or {})


def tayyorla(shakl):
    detallar, yetkaz, agreed, oldindan, loy = SHAKLLAR[shakl]
    pid, mid, mijoz = muhit()
    oid, ids = buyurtma(pid, mid, detallar, agreed, loy)
    for idx, d in enumerate(detallar):
        if d.get("category") == "mrp_product":
            ishlab(oid, ids[idx], d["quantity"])
    if oldindan:
        tolov(oid, oldindan)
    for idx, miq in yetkaz.items():
        yuk(oid, ids[idx], miq)
    return oid, ids, mid, mijoz


# ══════════════════════════════════════════════════════════════
# 144-band (kech102) — qaytarish: daromad / tannarx / KPI qaysi davrda
# ══════════════════════════════════════════════════════════════
import json                                        # noqa: E402
import subprocess                                  # noqa: E402

# kech105 (9 + 50-band, "Toshkent vaqti bo'yicha"): hisobot davri — Toshkent devor soati (UTC + 5), server kabi
HOZIR = datetime.utcnow() + timedelta(hours=5)
Y, M = HOZIR.year, HOZIR.month
OY0 = (Y - 1, 12) if M == 1 else (Y, M - 1)
NARX = {"PENO": 500_000.0, "KLEY": 2_000.0, "QUM": 1_000.0}
_DAVR = getattr(services, "davr_qaytarishlari", None)

SHAKL = {
    "profil": (lambda: dict(_profil(10.0, 500_000), quantity=1), 10.0, "m", 50_000.0),
    "panel": (lambda: _panel(10.0, 30_000), 6.0, "m²", 30_000.0),
    "tm": (lambda: _tm_profil(10.0, 100_000), 0.0, "m", 10_000.0),
    "mrp": (lambda: _mrp(10.0, 100_000), 0.0, "dona", 100_000.0),
}


def hisobot(y=Y, m=M, cid=1):
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            r = services.get_monthly_report(s, y, m, company_id=cid)
        # kech117 (A2): «turlar bo'yicha» o'rniga — yo'nalishlar bo'yicha daromad (asosiy yo'nalish)
        _yd = {y.get("kalit"): y.get("daromad") for y in (r.get("yonalishlar_daromadi") or [])}
        return {"daromad_b": float(r.get("daromad_buyurtmalardan") or 0),
                "ishlab": round(float(r.get("ishlab_chiqarish_xarajat") or 0), 2),
                "fp_daromad": float(r.get("fp_sales_daromad") or 0),
                "fp_tannarx": float(r.get("fp_sales_daromad") or 0) - float(r.get("fp_sales_foyda") or 0),
                "brak": float(r.get("brak_xarajat") or 0),
                "sof": round(float(r.get("sof_foyda") or 0), 2),
                "daromad": float(r.get("daromad") or 0),
                "q_daromad": float(r.get("qaytarish_daromad") or 0),
                "q_tannarx": float(r.get("qaytarish_tannarx") or 0),
                "q_soni": int(r.get("qaytarish_soni") or 0),
                "tur_peno": float(_yd.get(f"y{YON_ASOSIY}") or 0),
                "usta_kpi": float(r.get("usta_kpi_xarajat") or 0),
                "ehson": float(r.get("ehson_xarajat") or 0),
                "hodim": float(r.get("hodimlar_moslashuvchan_xarajat") or 0)}
    finally:
        s.close()


def usta(mid, y=Y, m=M):
    s = SessionLocal()
    try:
        _m = s.get(Master, mid)
        with contextlib.redirect_stdout(_quiet):
            k = services.calculate_monthly_master_kpi(s, y, m, company_id=1)
            yil = crud.get_masters_kpi_report(s, y, include_inactive=True, company_id=1)
            det = crud.get_master_kpi_detail(s, mid, y, company_id=1)
            kb = crud.get_master_yearly_cashback(s, mid, y, company_id=1)
        oy = [b for b in (k.get("breakdown") or []) if b.get("master_name") == _m.name]
        yl = [r for r in (yil.get("masters") or []) if r.get("id") == mid]
        return {"oy_foyda": float(oy[0]["monthly_profit"]) if oy else 0.0,
                "oy_kpi": float(oy[0]["kpi_amount"]) if oy else 0.0,
                "yil_foyda": float(yl[0]["yearly_profit"]) if yl else 0.0,
                "tafsilot": float(sum(float(x.get("profit") or 0) for x in det)),
                "tafsilot_qator": [(x.get("order_number"), x.get("profit")) for x in det],
                "keshbek": round(float(kb.get("yearly_profit") or 0), 2)}
    finally:
        s.close()


def umumiy():
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            kassa = float(services.get_cash_balance(s, company_id=1).get("balance") or 0)
            ehs = float(services.calculate_monthly_ehson(s, Y, M, company_id=1).get("monthly_profit") or 0)
            kun = services.get_daily_finance_summary(s, (datetime.utcnow() + timedelta(hours=5)).date(),
                                                    company_id=1).get("sales") or {}      # kech105: Toshkent "bugun"i
            bugun = float(services.get_today_stats(s, company_id=1).get("today_profit") or 0)
            split = services.calculate_split_profit_report(s, Y, M, company_id=1)
            pd = float(crud.get_projects_dashboard_stats(s, company_id=1).get("total_profit") or 0)
        # kech117 (A2): yo'nalishlar hisoboti — asosiy yo'nalish ustuni (tannarx — tiyin aniqligida)
        _asos = [y for y in (split.get("yonalishlar") or []) if y.get("asosiy")]
        return {"kassa": kassa, "ehson_foyda": ehs, "kun_total": float(kun.get("total") or 0),
                "kun_cost": float(kun.get("cost") or 0), "kun_q_soni": int(kun.get("qaytarish_soni") or 0),
                "bugun": round(bugun, 2), "split_peno": float(((_asos[0].get("aniq") or {}).get("tannarx") or 0) if _asos else 0),
                "loyihalar": pd}
    finally:
        s.close()


def tovar_qiymati():
    """Korxonada turgan tovar qiymati: xomashyo qoldig'i × narx + barcha TM qoldig'i × tizimning birlik tannarxi."""
    s = SessionLocal()
    try:
        jami = sum(float(s.get(Inventory, ID[k]).stock_quantity) * NARX[k] for k in NARX)
        for f in s.query(FinishedProduct).filter(FinishedProduct.company_id == 1).all():
            q = float(f.quantity or 0)
            if q > 1e-9:
                jami += q * float(crud._fp_stable_unit_cost(s, f) or 0)
        return round(jami, 2)
    finally:
        s.close()


def foyda(oid):
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            r = services.calculate_order_profit(s, oid, company_id=1)
        return {"sotuv": round(float(r.get("sotuv_narxi") or 0), 2), "tan": round(float(r.get("tan_narxi") or 0), 2),
                "foyda": round(float(r.get("foyda") or 0), 2), "breakdown": r.get("breakdown") or []}
    finally:
        s.close()


def yozuv(rid):
    s = SessionLocal()
    try:
        r = s.get(ReturnItem, rid) if rid else None
        if r is None:
            return {"delta": 0.0, "stock": 0.0, "fp": None, "stock_qty": 0.0}
        return {"delta": float(r.refund_agreed_delta or 0) if r.refunded_at is not None else 0.0,
                "stock": float(r.stock_cost or 0) if r.finished_product_id else 0.0,
                "fp": r.finished_product_id, "stock_qty": float(r.stock_qty or 0)}
    finally:
        s.close()


def qaytar(oid, iid, miqdor, sabab, to_stock=True, birlik="m"):
    r = req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": iid, "item_name": "x", "quantity": miqdor,
                                             "unit": birlik, "reason": sabab, **({"brak_sabab": "boshqa"} if sabab == "Brak" else {}), "refund_amount": 0, "to_stock": to_stock})
    d = js(r) or {}
    return r.status_code, (d.get("id") if isinstance(d, dict) else None)


def pul(rid):
    return req(C, "post", f"/api/returns/{rid}/refund").status_code


def qayta_sot(fp_id, miqdor, narx):
    r = req(C, "post", "/api/finished/sell", json={"finished_product_id": fp_id, "quantity": miqdor, "unit_price": narx,
                                                   "buyer_name": nom("xar"), "confirm_below_cost": True})
    d = js(r) or {}
    if r.status_code != 200 or not isinstance(d, dict):
        return r.status_code, 0.0, 0.0
    _t = float(d.get("total_amount") or 0)
    return r.status_code, round(_t - float(d.get("profit") or 0), 2), round(_t, 2)


def buyurtma_tayyor(shakl, pid, mid, yetk=10.0, tolash=True):
    detal, loy, birlik, narx = SHAKL[shakl]
    oid, ids = buyurtma(pid, mid, [detal()], None, loy)
    iid = ids[0] if ids else None
    if shakl == "mrp":
        ishlab(oid, iid, 10.0)
    h = holat(oid) or {}
    if tolash:
        tolov(oid, h.get("total") or 0)
    if yetk > 0:
        yuk(oid, iid, yetk)
    return oid, iid, float(h.get("total") or 0)


def tayyor_qil(oid, shakl):
    loy = SHAKL[shakl][1]
    return tayyor(oid, loy if loy else None)[0]


def ayir(a, b, k):
    return round(float(b[k]) - float(a[k]), 2)


def teng(a, b, eps=0.51):
    return taxminan(a, b, eps)


# NAZORAT — har shaklning qaytarishsiz (to'liq) tannarxi
NAZORAT = {}
section("0. NAZORAT buyurtmalar (qaytarishsiz)")
for _sh in SHAKL:
    _pid, _mid, _mj = muhit()
    _o, _i, _tot = buyurtma_tayyor(_sh, _pid, _mid)
    check(f"0 {_sh} «Tayyor» 200", tayyor_qil(_o, _sh) == 200)
    NAZORAT[_sh] = foyda(_o)
    check(f"0 {_sh} NAZORAT tannarx musbat", NAZORAT[_sh]["tan"] > 0, NAZORAT[_sh])

# ══════════════════════════════════════════════════════════════
section("A. Shakl × qaytarish (hammasi SHU oyda): A omborga + pul + qayta sotuv, B omborga emas + pul, C brak, D omborga pulsiz")
KUTILGAN_HODISA = {"A": 2, "B": 1, "C": 0, "D": 1}
for sh in ("profil", "panel", "tm", "mrp"):
    birlik, narx = SHAKL[sh][2], SHAKL[sh][3]
    for v in ("A", "B", "C", "D"):
        t = f"A {sh}-{v}"
        pid, mid, mijoz = muhit()
        h0, g0, t0 = hisobot(), umumiy(), tovar_qiymati()
        oid, iid, total = buyurtma_tayyor(sh, pid, mid)
        check(f"{t} «Tayyor» 200", tayyor_qil(oid, sh) == 200)
        h1, g1, f1 = hisobot(), umumiy(), foyda(oid)
        C10 = f1["tan"]
        check(f"{t} tannarx (qaytarishgacha) = NAZORAT", teng(C10, NAZORAT[sh]["tan"], 0.01), (C10, NAZORAT[sh]["tan"]))
        if v == "A":
            st, rid = qaytar(oid, iid, 3.0, "Mijoz iltimosi", True, birlik)
            ps = pul(rid) if rid else None
        elif v == "B":
            st, rid = qaytar(oid, iid, 3.0, "Mijoz iltimosi", False, birlik)
            ps = pul(rid) if rid else None
        elif v == "C":
            st, rid = qaytar(oid, iid, 3.0, "Brak", True, birlik)
            ps = None
        else:
            st, rid = qaytar(oid, iid, 3.0, "Mijoz iltimosi", True, birlik)
            ps = None
        check(f"{t} qaytarish 200", st == 200 and rid, (st, rid))
        if ps is not None:
            check(f"{t} pul qaytdi 200", ps == 200, ps)
        yz = yozuv(rid)
        delta, stock = yz["delta"], yz["stock"]
        if v in ("A", "B"):
            check(f"{t} pul qaytarildi (kelishilgan kamaydi)", delta > 0, yz)
        if v in ("A", "D"):
            check(f"{t} omborga qaytdi (tannarx yozildi)", stock > 0 and yz["fp"], yz)
        if v in ("B", "C"):
            check(f"{t} omborga tushmadi", stock == 0, yz)
        k_sotuv = total - delta
        k_tan = C10 - stock
        k_foyda = k_sotuv - k_tan
        h2, g2, f2, u2 = hisobot(), umumiy(), foyda(oid), usta(mid)
        api = js(req(C, "get", f"/api/orders/{oid}/profit")) or {}
        # buyurtma foydasi — hozirgi holat (hamma qaytarish bilan)
        check(f"{t} buyurtma sotuvi = jami − qaytarilgan pul", teng(f2["sotuv"], k_sotuv, 0.01), (f2["sotuv"], k_sotuv))
        check(f"{t} buyurtma tannarxi = to'liq − omborga qaytgan", teng(f2["tan"], k_tan, 0.01), (f2["tan"], k_tan, C10, stock))
        _qator = [b for b in (api.get("breakdown") or []) if "↩️" in str(b.get("nomi"))]
        if stock > 0:
            check(f"{t} foyda oynasi: '↩️ Omborga qaytgan' qatori = −tannarx", _qator and teng(_qator[0].get("summa"), -stock, 0.01), _qator)
            check(f"{t} foyda oynasi tan_narxi", teng(api.get("tan_narxi"), k_tan, 0.01), api.get("tan_narxi"))
        else:
            check(f"{t} foyda oynasi: qaytgan qator YO'Q", not _qator, _qator)
        # oylik hisobot — buyurtma + shu oydagi qaytarish qatori
        check(f"{t} hisobot daromadi Δ = jami − pul", teng(ayir(h0, h2, "daromad_b"), k_sotuv), (ayir(h0, h2, "daromad_b"), k_sotuv))
        check(f"{t} hisobot ishlab chiqarish Δ = tannarx − omborga qaytgan", teng(ayir(h0, h2, "ishlab"), k_tan, 0.02),
              (ayir(h0, h2, "ishlab"), k_tan))
        check(f"{t} qaytarish qatori: daromad = −pul", teng(ayir(h1, h2, "q_daromad"), -delta), (ayir(h1, h2, "q_daromad"), delta))
        check(f"{t} qaytarish qatori: tannarx = −omborga qaytgan", teng(ayir(h1, h2, "q_tannarx"), -stock), (ayir(h1, h2, "q_tannarx"), stock))
        check(f"{t} qaytarish qatori: hodisalar soni {KUTILGAN_HODISA[v]}", h2["q_soni"] - h1["q_soni"] == KUTILGAN_HODISA[v],
              (h1["q_soni"], h2["q_soni"]))
        check(f"{t} asosiy yo'nalish (Penoplast) daromadi Δ = hisobot daromadi Δ", teng(ayir(h0, h2, "tur_peno"), ayir(h0, h2, "daromad_b")),
              (ayir(h0, h2, "tur_peno"), ayir(h0, h2, "daromad_b")))
        # usta KPI (buyurtma — shu oy)
        check(f"{t} usta oylik foydasi = yo'qotilgan foyda bilan", teng(u2["oy_foyda"], k_foyda), (u2["oy_foyda"], k_foyda))
        check(f"{t} usta oylik KPI (10 %)", teng(u2["oy_kpi"], k_foyda * 0.10), (u2["oy_kpi"], k_foyda))
        check(f"{t} usta yillik foydasi", teng(u2["yil_foyda"], k_foyda), (u2["yil_foyda"], k_foyda))
        check(f"{t} usta KPI tafsiloti jami", teng(u2["tafsilot"], k_foyda, 1.01), u2["tafsilot_qator"])
        check(f"{t} keshbek (yillik) foydasi", teng(u2["keshbek"], k_foyda), (u2["keshbek"], k_foyda))
        check(f"{t} bugun foydasi Δ (qaytarishda) = −pul + omborga qaytgan", teng(ayir(g1, g2, "bugun"), -delta + stock),
              (ayir(g1, g2, "bugun"), delta, stock))
        check(f"{t} loyihalar foydasi Δ (qaytarishda)", teng(ayir(g1, g2, "loyihalar"), -delta + stock, 1.01),
              (ayir(g1, g2, "loyihalar"), delta, stock))
        _ds = js(req(C, "get", f"/api/projects/{pid}/detail-stats")) or {}
        check(f"{t} loyiha detali foydasi", teng(_ds.get("total_profit"), k_foyda, 1.01), (_ds.get("total_profit"), k_foyda))
        check(f"{t} yo'nalishlar hisoboti: asosiy yo'nalish tannarxi Δ", teng(ayir(g0, g2, "split_peno"), k_tan, 1.01),
              (ayir(g0, g2, "split_peno"), k_tan))
        # qayta sotuv
        sot = (None, 0.0, 0.0)
        if v in ("A", "D") and yz["fp"]:
            sot = qayta_sot(yz["fp"], yz["stock_qty"] or 3.0, narx)
            check(f"{t} qayta sotuv 200", sot[0] == 200, sot)
            check(f"{t} qayta sotuv tannarxi = omborga qaytgan tannarx", teng(sot[1], stock, 0.02), (sot, stock))
        h3, g3, t3 = hisobot(), umumiy(), tovar_qiymati()
        sarf = round(t0 - t3, 2)
        jami_tannarx = round(ayir(h0, h3, "ishlab") + ayir(h0, h3, "fp_tannarx") + ayir(h0, h3, "brak"), 2)
        check(f"{t} hisobotdagi jami tannarx = HAQIQIY sarf (ikki marta EMAS)", teng(jami_tannarx, sarf, 0.05), (jami_tannarx, sarf))
        check(f"{t} hisobot jami daromad Δ = kassa Δ (to'liq to'langan)", teng(ayir(h0, h3, "daromad"), ayir(g0, g3, "kassa")),
              (ayir(h0, h3, "daromad"), ayir(g0, g3, "kassa")))
        check(f"{t} ehson foydasi Δ = buyurtma + qayta sotuv foydasi", teng(ayir(g0, g3, "ehson_foyda"), k_foyda + sot[2] - sot[1], 1.01),
              (ayir(g0, g3, "ehson_foyda"), k_foyda, sot))
        check(f"{t} kunlik sotuv Δ", teng(ayir(g0, g3, "kun_total"), k_sotuv + sot[2], 1.01), (ayir(g0, g3, "kun_total"), k_sotuv, sot))
        check(f"{t} kunlik tannarx Δ", teng(ayir(g0, g3, "kun_cost"), k_tan + sot[1], 1.01), (ayir(g0, g3, "kun_cost"), k_tan, sot))

# ══════════════════════════════════════════════════════════════
section("R. Oy chegarasi: buyurtma O'TGAN oyda yakunlangan, qaytarish SHU oyda (QAROR \"Qaytarish oyida\")")
pid, mid, mijoz = muhit()
oidX, iidX, totX = buyurtma_tayyor("profil", pid, mid)
check("R ikkinchi (shu oy) buyurtma «Tayyor» 200", tayyor_qil(oidX, "profil") == 200)
oid, iid, total = buyurtma_tayyor("profil", pid, mid)
check("R buyurtma «Tayyor» 200", tayyor_qil(oid, "profil") == 200)
_s0 = SessionLocal()
try:
    _o0 = _s0.get(Order, oid)
    _o0.completed_at = datetime(OY0[0], OY0[1], 15, 10, 0, 0)
    _s0.commit()
finally:
    _s0.close()
C10 = foyda(oid)["tan"]
p1, h1, u1, u1o, g1 = hisobot(*OY0), hisobot(), usta(mid), usta(mid, *OY0), umumiy()
_gs = SessionLocal()
try:
    _goyna = (datetime.utcnow() - timedelta(days=1), datetime.utcnow() + timedelta(days=1))
    with contextlib.redirect_stdout(_quiet):
        gift1 = float(crud._gift_period_profit_since(_gs, mid, _goyna[0], _goyna[1], company_id=1))
finally:
    _gs.close()
_r_oldin = datetime.utcnow()
st, rid = qaytar(oid, iid, 3.0, "Mijoz iltimosi", True, "m")
check("R qaytarish 200", st == 200 and rid, (st, rid))
check("R pul qaytdi 200", pul(rid) == 200)
yz = yozuv(rid)
delta, stock = yz["delta"], yz["stock"]
check("R pul va ombor yozildi", delta > 0 and stock > 0, yz)
p2, h2, u2, u2o, g2 = hisobot(*OY0), hisobot(), usta(mid), usta(mid, *OY0), umumiy()
_gs = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        gift2 = float(crud._gift_period_profit_since(_gs, mid, _goyna[0], _goyna[1], company_id=1))
finally:
    _gs.close()
for _k in ("daromad_b", "ishlab", "sof", "q_daromad", "q_tannarx", "q_soni", "usta_kpi"):
    check(f"R o'tgan oy hisoboti O'ZGARMADI: {_k}", teng(p1[_k], p2[_k], 0.001), (p1[_k], p2[_k]))
check("R o'tgan oy usta foydasi O'ZGARMADI", teng(u1o["oy_foyda"], u2o["oy_foyda"], 0.001), (u1o["oy_foyda"], u2o["oy_foyda"]))
check("R shu oy: qaytarish qatori daromad = −pul", teng(ayir(h1, h2, "q_daromad"), -delta), (ayir(h1, h2, "q_daromad"), delta))
check("R shu oy: qaytarish qatori tannarx = −omborga qaytgan", teng(ayir(h1, h2, "q_tannarx"), -stock), (ayir(h1, h2, "q_tannarx"), stock))
check("R shu oy: qaytarish hodisalari 2", h2["q_soni"] - h1["q_soni"] == 2, (h1["q_soni"], h2["q_soni"]))
check("R shu oy daromadi Δ = −pul", teng(ayir(h1, h2, "daromad_b"), -delta), (ayir(h1, h2, "daromad_b"), delta))
check("R shu oy ishlab chiqarish Δ = −omborga qaytgan", teng(ayir(h1, h2, "ishlab"), -stock, 0.02), (ayir(h1, h2, "ishlab"), stock))
check("R shu oy sof foyda Δ = −(pul − ombor) − KPI / ehson / hodim Δ",
      teng(ayir(h1, h2, "sof"), -delta + stock - ayir(h1, h2, "usta_kpi") - ayir(h1, h2, "ehson") - ayir(h1, h2, "hodim"), 1.01),
      (ayir(h1, h2, "sof"), delta, stock, ayir(h1, h2, "usta_kpi")))
check("R usta oylik foydasi (shu oy) Δ = yo'qotilgan foyda", teng(u2["oy_foyda"] - u1["oy_foyda"], -delta + stock),
      (u1["oy_foyda"], u2["oy_foyda"], delta, stock))
check("R usta yillik foydasi Δ", teng(u2["yil_foyda"] - u1["yil_foyda"], (-delta + stock) if OY0[0] == Y else (-delta + stock)),
      (u1["yil_foyda"], u2["yil_foyda"]))
_rq = [q for q in u2["tafsilot_qator"] if "↩️" in str(q[0])]
check("R usta KPI tafsilotida qaytarish qatorlari (har hodisa — alohida), jami = yo'qotilgan foyda",
      len(_rq) == 2 and teng(sum(float(q[1]) for q in _rq), -delta + stock, 1.01), u2["tafsilot_qator"])
check("R tafsilot qatorlari nomi: pul / ombor", any("mijozga pul qaytarildi" in str(q[0]) and teng(q[1], -delta, 1.01) for q in _rq)
      and any("mahsulot omborga qaytdi" in str(q[0]) and teng(q[1], stock, 1.01) for q in _rq), _rq)
check("R keshbek foydasi Δ", teng(u2["keshbek"] - u1["keshbek"], -delta + stock), (u1["keshbek"], u2["keshbek"]))
check("R sovg'a davri foydasi Δ", teng(gift2 - gift1, -delta + stock), (gift1, gift2))
# sovg'a davri oralig'i (boshi, oxiri] — buyurtmalar bilan bir qoida: aynan BOSHIDAGI hodisa kirmaydi, OXIRIDAGI kiradi
_s = SessionLocal()
try:
    _ri = _s.get(ReturnItem, rid)
    _t_ombor, _t_pul = _ri.returned_at, _ri.refunded_at
    with contextlib.redirect_stdout(_quiet):
        gift_ch = float(crud._gift_period_profit_since(_s, mid, _t_ombor, _t_pul, company_id=1))
finally:
    _s.close()
check("R sovg'a davri chegarasi (ombor, pul]: faqat pul hodisasi (−pul)", _t_ombor < _t_pul and teng(gift_ch, -delta),
      (gift_ch, delta, stock, _t_ombor, _t_pul))
# sovg'a davri qaytarish PAYTINI qamrasa — qaytarish keshbekka KIRMAYDI (u davr hisobida)
_s = SessionLocal()
try:
    _gp = GiftPeriod(company_id=1, is_active=False, started_at=_r_oldin, closed_at=datetime.utcnow())
    _s.add(_gp)
    _s.commit()
    _gp_id = _gp.id
finally:
    _s.close()
u3 = usta(mid)
check("R keshbek: qaytarish sovg'a davri ichida — keshbekka kirmaydi", teng(u3["keshbek"], u1["keshbek"]), (u1["keshbek"], u3["keshbek"]))
_s = SessionLocal()
try:
    _s.delete(_s.get(GiftPeriod, _gp_id))
    _s.commit()
finally:
    _s.close()
check("R ehson foydasi (shu oy) Δ", teng(ayir(g1, g2, "ehson_foyda"), -delta + stock, 1.01), (ayir(g1, g2, "ehson_foyda"), delta, stock))
check("R kunlik sotuv Δ = −pul", teng(ayir(g1, g2, "kun_total"), -delta, 1.01), (ayir(g1, g2, "kun_total"), delta))
check("R kunlik tannarx Δ = −omborga qaytgan", teng(ayir(g1, g2, "kun_cost"), -stock, 1.01), (ayir(g1, g2, "kun_cost"), stock))
check("R kunlik qaytarishlar soni 2", g2["kun_q_soni"] - g1["kun_q_soni"] == 2, (g1["kun_q_soni"], g2["kun_q_soni"]))
check("R bugun foydasi Δ", teng(ayir(g1, g2, "bugun"), -delta + stock), (ayir(g1, g2, "bugun"), delta, stock))
_fR = foyda(oid)
check("R buyurtma foydasi (hozirgi holat): sotuv", teng(_fR["sotuv"], total - delta, 0.01), (_fR, total, delta))
check("R buyurtma foydasi (hozirgi holat): tannarx", teng(_fR["tan"], C10 - stock, 0.01), (_fR, C10, stock))
if _DAVR is not None:
    _ss = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            # kech105: davr chegaralari — Toshkent oyi UTC ko'rinishida (server hisobotlari kabi: − 5 soat)
            _T5 = timedelta(hours=5)
            _dq = _DAVR(_ss, datetime(Y, M, 1) - _T5, (datetime(Y + 1, 1, 1) if M == 12 else datetime(Y, M + 1, 1)) - _T5,
                        company_id=1)
            _dq0 = _DAVR(_ss, datetime(OY0[0], OY0[1], 1) - _T5, datetime(Y, M, 1) - _T5, company_id=1)
        _bu = [h for h in _dq if h["order_id"] == oid]
        check("R davr_qaytarishlari (shu oy): 2 hodisa, jami", len(_bu) == 2 and teng(sum(h["daromad"] for h in _bu), -delta, 0.01)
              and teng(sum(h["tannarx"] for h in _bu), -stock, 0.01), _bu)
        check("R davr_qaytarishlari (o'tgan oy): bu buyurtma yo'q", not [h for h in _dq0 if h["order_id"] == oid], _dq0)
    finally:
        _ss.close()
else:
    check("R davr_qaytarishlari mavjud", False, "services.davr_qaytarishlari yo'q")

# ══════════════════════════════════════════════════════════════
section("E. Qaytarish «Tayyor» dan OLDIN — buyurtmaning o'z qatorida")
for sh in ("profil", "mrp"):
    birlik = SHAKL[sh][2]
    pid, mid, mijoz = muhit()
    h0, t0 = hisobot(), tovar_qiymati()
    oid, iid, total = buyurtma_tayyor(sh, pid, mid)
    st, rid = qaytar(oid, iid, 3.0, "Mijoz iltimosi", True, birlik)
    check(f"E {sh} qaytarish 200", st == 200 and rid, (st, rid))
    check(f"E {sh} pul qaytdi 200", pul(rid) == 200)
    check(f"E {sh} «Tayyor» 200", tayyor_qil(oid, sh) == 200)
    yz = yozuv(rid)
    delta, stock = yz["delta"], yz["stock"]
    h1, u1 = hisobot(), usta(mid)
    k_tan = NAZORAT[sh]["tan"] - stock
    check(f"E {sh} qaytarish qatori YO'Q (hodisa yakunlanishdan oldin)", h1["q_soni"] == h0["q_soni"], (h0["q_soni"], h1["q_soni"]))
    check(f"E {sh} hisobot daromadi Δ = jami − pul", teng(ayir(h0, h1, "daromad_b"), total - delta), (ayir(h0, h1, "daromad_b"), total, delta))
    check(f"E {sh} hisobot ishlab chiqarish Δ = NAZORAT − omborga qaytgan", teng(ayir(h0, h1, "ishlab"), k_tan, 0.02),
          (ayir(h0, h1, "ishlab"), k_tan))
    check(f"E {sh} usta oylik foydasi", teng(u1["oy_foyda"], (total - delta) - k_tan), (u1["oy_foyda"], total, delta, k_tan))
    sot = qayta_sot(yz["fp"], yz["stock_qty"] or 3.0, SHAKL[sh][3]) if yz["fp"] else (None, 0.0, 0.0)
    h2, t2 = hisobot(), tovar_qiymati()
    check(f"E {sh} jami tannarx = HAQIQIY sarf", teng(ayir(h0, h2, "ishlab") + ayir(h0, h2, "fp_tannarx"), round(t0 - t2, 2), 0.05),
          (ayir(h0, h2, "ishlab"), ayir(h0, h2, "fp_tannarx"), t0 - t2, sot))

# ══════════════════════════════════════════════════════════════
section("O. \"Ortiqcha\" (topshirilmagan) qaytarish — tannarx = haqiqiy sarf (K102-1: MRP)")
for sh in ("mrp", "profil"):
    birlik = SHAKL[sh][2]
    pid, mid, mijoz = muhit()
    h0, t0 = hisobot(), tovar_qiymati()
    oid, iid, total = buyurtma_tayyor(sh, pid, mid, yetk=0.0)
    st, rid = qaytar(oid, iid, 4.0, "Ortiqcha", True, birlik)
    check(f"O {sh} ortiqcha qaytarish 200", st == 200 and rid, (st, rid))
    check(f"O {sh} pul qaytdi 200", pul(rid) == 200)
    check(f"O {sh} «Tayyor» 200 (qolgan 6 avto-yetkaziladi)", tayyor_qil(oid, sh) == 200)
    yz = yozuv(rid)
    f1 = foyda(oid)
    if sh == "mrp":
        check("O mrp buyurtma tannarxi = ishlatilgan 6 dona (NAZORAT × 0.6)", teng(f1["tan"], NAZORAT["mrp"]["tan"] * 0.6, 0.01),
              (f1["tan"], NAZORAT["mrp"]["tan"]))
    else:
        check("O profil buyurtma tannarxi = NAZORAT − omborga qaytgan", teng(f1["tan"], NAZORAT["profil"]["tan"] - yz["stock"], 0.01),
              (f1["tan"], NAZORAT["profil"]["tan"], yz))
    h1, t1 = hisobot(), tovar_qiymati()
    check(f"O {sh} hisobot tannarxi = HAQIQIY sarf (qaytgan mahsulot omborda)", teng(ayir(h0, h1, "ishlab"), round(t0 - t1, 2), 0.05),
          (ayir(h0, h1, "ishlab"), t0 - t1))

# ══════════════════════════════════════════════════════════════
section("D. Qaytarishni o'chirish (22-band) — hammasi qaytarishdan OLDINGI holatga AYNAN")
pid, mid, mijoz = muhit()
oid, iid, total = buyurtma_tayyor("profil", pid, mid)
check("D «Tayyor» 200", tayyor_qil(oid, "profil") == 200)
h1, g1, u1, f1 = hisobot(), umumiy(), usta(mid), foyda(oid)
st, rid = qaytar(oid, iid, 3.0, "Mijoz iltimosi", True, "m")
check("D qaytarish + pul 200", st == 200 and rid and pul(rid) == 200, (st, rid))
h2 = hisobot()
check("D qaytarish qatori bor", h2["q_soni"] - h1["q_soni"] == 2, (h1["q_soni"], h2["q_soni"]))
check("D qaytarishni o'chirish 200", req(C, "delete", f"/api/returns/{rid}").status_code == 200)
h3, g3, u3, f3 = hisobot(), umumiy(), usta(mid), foyda(oid)
for _k in ("daromad_b", "ishlab", "sof", "q_daromad", "q_tannarx", "q_soni", "daromad"):
    check(f"D hisobot AYNAN: {_k}", teng(h1[_k], h3[_k], 0.001), (h1[_k], h3[_k]))
for _k in ("kassa", "ehson_foyda", "kun_total", "kun_cost", "bugun", "loyihalar"):
    check(f"D umumiy AYNAN: {_k}", teng(g1[_k], g3[_k], 0.001), (g1[_k], g3[_k]))
for _k in ("oy_foyda", "yil_foyda", "keshbek"):
    check(f"D usta AYNAN: {_k}", teng(u1[_k], u3[_k], 0.001), (u1[_k], u3[_k]))
check("D buyurtma foydasi AYNAN", f1["sotuv"] == f3["sotuv"] and f1["tan"] == f3["tan"], (f1, f3))

# ══════════════════════════════════════════════════════════════
section("K. Korxona: begona korxona yozuvi hisobga olinmaydi; B korxonasi qaytarishi A da yo'q")
hK0, fK0 = hisobot(), foyda(oid)
_s = SessionLocal()
try:
    _hozir = datetime.utcnow()
    _s.execute(ReturnItem.__table__.insert().values(
        company_id=2, order_id=oid, item_name="begona", quantity=1.0, unit="m", reason=ReturnReason.CUSTOMER_REQUEST,
        refund_amount=99_999, is_refunded=True, refunded_at=_hozir, refund_agreed_delta=99_999,
        finished_product_id=ID["TMP"], stock_cost=77_777, returned_at=_hozir))
    _s.commit()
finally:
    _s.close()
hK1, fK1 = hisobot(), foyda(oid)
for _k in ("daromad_b", "ishlab", "q_daromad", "q_tannarx", "q_soni"):
    check(f"K1 begona korxona yozuvi (A buyurtmasida) hisobotga tushmadi: {_k}", teng(hK0[_k], hK1[_k], 0.001), (hK0[_k], hK1[_k]))
check("K1 buyurtma foydasi o'zgarmadi", fK0["sotuv"] == fK1["sotuv"] and fK0["tan"] == fK1["tan"], (fK0, fK1))
_s = SessionLocal()
try:
    _pB = Project(company_id=2, client_name="QMB Mijoz", project_name="QMB loyiha", total_budget=0, total_paid=0)
    _s.add(_pB)
    _s.flush()
    _oB = Order(company_id=2, project_id=_pB.id, order_number="QMB-1", status=OrderStatus.READY, order_type=OrderType.PRODUCT,
                completed_at=datetime.utcnow() - timedelta(hours=1), total_amount=1_000_000, agreed_amount=900_000)
    _fB = FinishedProduct(company_id=2, name="QMB TM", category="profil", quantity=1, produced_quantity=1, unit="metr",
                          unit_price=0, cost_price=50_000, source=StockSource.RETURNED, production_status=ProductionStatus.READY)
    _s.add_all([_oB, _fB])
    _s.flush()
    _s.add(ReturnItem(company_id=2, order_id=_oB.id, item_name="B qaytarish", quantity=1.0, unit="m",
                      reason=ReturnReason.CUSTOMER_REQUEST, refund_amount=100_000, is_refunded=True,
                      refunded_at=datetime.utcnow(), refund_agreed_delta=100_000, finished_product_id=_fB.id,
                      stock_cost=50_000, returned_at=datetime.utcnow() - timedelta(minutes=1)))
    _s.commit()
    _oBid = _oB.id
finally:
    _s.close()
hK2 = hisobot()
for _k in ("daromad_b", "ishlab", "q_daromad", "q_tannarx", "q_soni"):
    check(f"K2 B korxonasi qaytarishi A hisobotida yo'q: {_k}", teng(hK1[_k], hK2[_k], 0.001), (hK1[_k], hK2[_k]))
hB = hisobot(cid=2)
check("K2 B hisobotida qaytarish qatori: daromad −100 000", teng(hB["q_daromad"], -100_000), hB)
check("K2 B hisobotida qaytarish qatori: tannarx −50 000", teng(hB["q_tannarx"], -50_000), hB)
check("K2 B hisobotida qaytarish hodisalari 2", hB["q_soni"] == 2, hB)
if _DAVR is not None:
    _ss = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            _T5 = timedelta(hours=5)      # kech105: Toshkent oyi chegaralari (UTC ko'rinishida)
            _dA = _DAVR(_ss, datetime(Y, M, 1) - _T5, (datetime(Y + 1, 1, 1) if M == 12 else datetime(Y, M + 1, 1)) - _T5,
                        company_id=1)
            _dB = _DAVR(_ss, datetime(Y, M, 1) - _T5, (datetime(Y + 1, 1, 1) if M == 12 else datetime(Y, M + 1, 1)) - _T5,
                        company_id=2)
        check("K3 A davrida B buyurtmasi yo'q", not [h for h in _dA if h["order_id"] == _oBid], _dA)
        check("K3 B davrida faqat B buyurtmasi", _dB and all(h["order_id"] == _oBid for h in _dB), _dB)
    finally:
        _ss.close()
else:
    check("K3 davr_qaytarishlari mavjud", False, "yo'q")

# ══════════════════════════════════════════════════════════════
section("U. finance.html — \"Qaytarishlar\" guruhi (node)")


def js_funksiya(src, nom_):
    i = src.find(f"\nfunction {nom_}(")
    if i < 0:
        return None
    j = src.find("\n}\n", i)
    return src[i + 1:j + 2] if j > 0 else None


_fin = open(os.path.join(ROOT, "templates", "finance.html"), encoding="utf-8").read()
_fn = js_funksiya(_fin, "buildExpDetail")
check("U buildExpDetail topildi", _fn is not None)
# kech118 (B — U-05 / U-03, MOSLANDI): buildExpDetail endi base.html `foizKor` / `matnRangi` ni chaqiradi — kontekstga qo'shiladi
_base = open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8").read()
_yordam = "\n".join(filter(None, (js_funksiya(_base, _n) for _n in ("sonKor", "foizKor", "birlikKor", "matnRangi"))))
_JS = r"""
const elementlar = {};
const document = {getElementById: (id) => (elementlar[id] = elementlar[id] || {style: {}, textContent: '', innerHTML: ''})};
function fmtFull(n){return Number(Math.round(n||0)).toLocaleString('ru-RU');}
function fmt(n){return String(Math.round(n||0));}
function escapeHtml(s){return String(s);}
function buildRevDonut(){}
__FN__
const holatlar = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const natija = holatlar.map(d => { buildExpDetail(d); return elementlar['expDetail'].innerHTML; });
process.stdout.write(JSON.stringify(natija));
"""
_asos = {"xarajatlar": {"arenda": 100_000, "elektr": 0, "tushlik": 0, "soliqlar": 0}, "qoshimcha_xarajatlar": {},
         "usta_kpi_breakdown": [], "hodimlar_moslashuvchan_breakdown": [], "turlar_boyicha": None, "fp_sales_daromad": 0,
         "ishlab_chiqarish_xarajat": 49_000, "ehson_xarajat": 0, "brak_xarajat": 0, "transport_xarajat": 0,
         "jami_xarajat": 100_000, "daromad": 350_000, "sof_foyda": 201_000, "foyda_foiz": 57.4}
_holatlar = [dict(_asos, qaytarish_soni=2, qaytarish_daromad=-150_000, qaytarish_tannarx=-21_000),
             dict(_asos, qaytarish_soni=0, qaytarish_daromad=0, qaytarish_tannarx=0),
             dict(_asos, xarajatlar={"arenda": 0, "elektr": 0, "tushlik": 0, "soliqlar": 0}, qaytarish_soni=1,
                  qaytarish_daromad=-90_000, qaytarish_tannarx=0)]
_u = None
if _fn:
    try:
        _p = subprocess.run(["node", "-e", _JS.replace("__FN__", _yordam + "\n" + _fn)], input=json.dumps(_holatlar), capture_output=True,
                            text=True, timeout=60)
        _u = json.loads(_p.stdout) if _p.returncode == 0 else None
        if _u is None:
            print("   node:", _p.stderr[:400])
    except Exception as e:          # noqa: BLE001
        print("   node ishlamadi:", e)
check("U node ishladi", _u is not None and len(_u) == 3)
if _u:
    check("U1 qaytarishli oy: guruh sarlavhasi", "Qaytarishlar (2 ta, shu oyda)" in _u[0], _u[0][:300])
    check("U1 pul qatori −150 000", "Mijozga qaytarilgan pul" in _u[0] and "-150" in _u[0].replace(" ", " ").replace(" ", ""), _u[0][:600])
    check("U1 ombor qatori −21 000", "Omborga qaytgan mahsulot" in _u[0] and "-21" in _u[0].replace(" ", " ").replace(" ", ""), _u[0][:600])
    check("U1 guruh jami = sof foydaga ta'siri −129 000", "-129" in _u[0].replace(" ", " ").replace(" ", ""), _u[0][:600])
    check("U2 qaytarishsiz oy: guruh YO'Q", "Qaytarishlar" not in _u[1], _u[1][:300])
    check("U3 faqat qaytarish (boshqa xarajat yo'q): guruh ko'rinadi", "Qaytarishlar (1 ta, shu oyda)" in _u[2], _u[2][:300])

# ══════════════════════════════════════════════════════════════
section("X. 5xx yo'q")
check("X 5xx javob yo'q", not XATOLAR_5XX, XATOLAR_5XX[:5])

section("S. Statik")
_cop = manba(services, "calculate_order_profit")
check("S1 calculate_order_profit(holat_vaqti)", "holat_vaqti" in _cop.split(")")[0], _cop[:200])
check("S2 foyda: omborga qaytgan tannarx ayriladi (usta haqidan OLDIN)",
      tartibda(_cop, "_qaytarish_hodisalari(db, order)", "tan_narxi_jami -= _omborga_qaytgan", "# ── 3. USTA HAQI"))
check("S3 _hk_tayyorla — Order.returns oldindan", "_sil_hk(Order.returns)" in manba(services, "_hk_tayyorla"))
_rep = manba(services, "get_monthly_report")
check("S4 oylik hisobot — yakunlangan paytdagi daromad", "daromad = sum(yakun_daromadi(db, o) for o in ready_orders)" in _rep
      and "daromad = sum(o.kelishilgan_summa for o in ready_orders)" not in _rep)
check("S5 oylik hisobot — qaytarish qatori kalitlari", all(k in _rep for k in ('"qaytarish_daromad"', '"qaytarish_tannarx"', '"qaytarish_soni"')))
check("S6 MRP tannarxi — ortiqchasiz miqdor (K102-1)", 'getattr(item, "ortiqcha_qty", 0)' in manba(services, "_mrp_detal_tannarxi"))
check("S6b davr_qaytarishlari — hisobot keshida eslab qolinadi (bir hisobotda bitta so'rov)",
      tartibda(manba(services, "davr_qaytarishlari"), '_x = _hk_ol(db, "qaytarish_davr", _kalit)', "if _x is not _HK_YOQ:", "return _x",
               '_hk_qoy(db, "qaytarish_davr", _kalit, natija)'))
check("S7 finance.html — qaytarish guruhi", "Qaytarishlar (${d.qaytarish_soni} ta, shu oyda)" in _fin)
for _nm in ("calculate_monthly_master_kpi", "calculate_monthly_ehson", "get_daily_finance_summary", "get_today_stats"):
    check(f"S8 {_nm} — davr_qaytarishlari", "davr_qaytarishlari(" in manba(services, _nm))
# kech118 (yo'nalishlar — egasi qarori 15:23, MOSLANDI): hisobot davr oylarini `_yon_oy_aniq` da yig'adi; qaytarishlar —
# oylik `_yon_oy_aniq` da (`_yon_davr_jami` — faqat oldingi davr solishtiruvi, oylik hisobotdan)
check("S8 calculate_split_profit_report — davr_qaytarishlari (_yon_oy_aniq orqali)",
      "davr_qaytarishlari(" in manba(services, "_yon_oy_aniq") and "_yon_oy_aniq(" in manba(services, "calculate_split_profit_report"))
for _nm in ("get_master_kpi_detail", "get_masters_kpi_report", "_gift_period_profit_since", "get_master_yearly_cashback"):
    check(f"S9 crud.{_nm} — yakun_foydasi + davr_qaytarishlari",
          "services.yakun_foydasi(db, o)" in manba(crud, _nm) and "services.davr_qaytarishlari(" in manba(crud, _nm))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
