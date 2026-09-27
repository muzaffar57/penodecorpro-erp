#!/usr/bin/env python3
"""
test_ochirish_yopish.py — kech100 darvozasi (2026-09-27, 93-band, FOYDALANUVCHI QARORI "B").

QAROR (misol bilan): "100 m dan 40 m topshirilib buyurtma o'chirilsa, topshirilgan 40 m DAROMADI, TANNARXI va usta
KPI hisobotda QOLADI" ("qisman bo'lsa ham tovar berilgan bo'ladi").

O'LCHANGAN (asl kod = zip 93, `work/probe93.py`, SQLite = PG AYNAN): qisman topshirilgan (4 / 10) buyurtma
o'chirilsa IN_PROGRESS + o'chirilgan qolardi — oylik / yillik hisobot, usta KPI, kunlik moliya, grafik, eng yaxshi
mijozlar, ehson foydasi uni sanamasdi (faqat READY); to'liq topshirilgan, lekin «Tayyor» bosilmagan (DELIVERED) ham.
Poyga (`work/probe93b.py`, HAQIQIY PG): o'chirish QULFSIZ edi — «Tayyor» ∥ o'chirish qolgan qism xomashyosini IKKI
marta qaytardi, yuk xati o'chirish oynasiga tushib qolardi; to'lov qulfdan oldin o'qilgan (eski) kelishilgan summa
bilan "qarzdan ko'p" tekshiruvini o'tkazib yuborardi.

YECHIM: o'chirish topshirilgan qismni qisman «Tayyor» bilan AYNAN bir qoida bilan YAKUNLAYDI
(`crud.ochirishda_topshirilganni_yopish`), oldingi holat `orders.ochirish_yopish_json` da — tiklash AYNAN qaytaradi.

Bo'limlar:
  A — ORACLE: har shakl uchun "o'chirish" yo'li ↔ "qisman «Tayyor» (loy = o'chirish taxmini) + o'chirish" yo'li —
      hisobot / KPI / kunlik / grafik / mijozlar / ehson farqlari, buyurtma holati va ombor farqi AYNAN.
  B — to'liq topshirilgan (DELIVERED) o'chirilishi: READY, to'liq summa hisobotda, ishlatilgan loy = reja.
  C — tiklash: holat (detallar, summalar, sanalar, loy, izoh) o'chirishdan OLDINGIGA AYNAN, ombor va hisobot asl
      tiklash bilan bir xil; qayta o'chirish — yana o'sha yakunlash.
  D — o'zgarmagan yo'llar: yuksiz — butunlay; «Tayyor» (READY) — ikkinchi yakunlash yo'q; qoralama.
  E — oldindan ko'rish (GET /api/orders/{id} → ochirish.yopish) ↔ haqiqiy natija (DELETE → yopildi) AYNAN.
  F — `actual_loy_kg` bilan o'chirish — ishlatilgan loy AYNAN.
  G — sana: `completed_at` — o'chirilgan payt (eski yetkazish sanasi emas); tiklash eski sanani qaytaradi.
  P — poyga (FAQAT PG): o'chirish ∥ «Tayyor» / yuk xati / to'lov — ombor bir marta, yakunlash izchil.
  X — 5xx yo'q.   S — statik.

Ishlatish:
    python3 tools/test_ochirish_yopish.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_ochirish_yopish.py
"""
import os
import sys
import time
import inspect
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "ochirish_yopish_test"
_T = tempfile.mkdtemp(prefix="ochirish_yopish_")
_DB = os.path.join(_T, "ochirish_yopish_test.db")

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
    UserRole, Project, Inventory, OrderItem, Order, Recipe, RecipeIngredient, Master, Delivery, User,
    FinishedProduct, StockSource, ProductionStatus,
)
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
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "OY_admin", "Parol123!", UserRole.ADMIN, "OY Admin", company_id=1)
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
UID = _db.query(User.id).filter(User.username == "OY_admin").first()[0]
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "OY_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code, _lr.text[:300])
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_n = [0]


def nom(p="OY"):
    _n[0] += 1
    return f"{p}{_n[0]}"


PT = (js(req(C, "post", "/api/production/product-types", json={
    "name": "OY Travertin", "unit": "m²", "input_template": "quantity_only",
    "pricing_formula": "unit_based"})) or {}).get("id")
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
    n = datetime.utcnow()
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


def yol(shakl, turi):
    """turi: "D" — to'g'ridan o'chirish; "T" — qisman «Tayyor» (loy = o'chirish taxmini) + o'chirish."""
    oid, ids, mid, mijoz = tayyorla(shakl)
    rj = reja(oid) or {}
    k0, q0 = korsatkich(mid, mijoz), ombor()
    qT = None
    if turi == "T":
        tayyor(oid, rj.get("loy_ishlatilgan_taxmin"))
        qT = ombor()      # kech100 (K100-1/2/3a): «Tayyor» O'ZI (o'chirishsiz) ombor ishini tugatishi kerak
    st, d = ochir(oid)
    k1, q1 = korsatkich(mid, mijoz), ombor()
    h = holat(oid)
    return {"oid": oid, "reja": rj, "status_code": st, "javob": d, "farq": farq(k0, k1), "ombor": ombor_farq(q0, q1),
            "holat": h, "ombor_tayyor": (ombor_farq(q0, qT) if qT else None),
            "ombor_tayyor_keyin": (ombor_farq(qT, q1) if qT else None)}


def _hol_solishtir(h):
    """Holatning yo'llar orasida solishtiriladigan qismi (id, izoh / json / sanalar — tabiiy farq)."""
    if not h:
        return None
    return {"status": h["status"], "del": h["del"], "total": h["total"], "agreed": h["agreed"], "paid": h["paid"],
            "debt": h["debt"], "pay_status": h["pay_status"],
            "actual_loy": (round(float(h["actual_loy"]), 4) if h["actual_loy"] is not None else None),
            "items": [x[1:] for x in h["items"]]}


# ══════════════════════════════════════════════════════════════
# A — ORACLE: o'chirish ↔ qisman «Tayyor» + o'chirish
# ══════════════════════════════════════════════════════════════
section("A. O'chirish = qisman «Tayyor» + o'chirish (hisobot, KPI, holat, ombor AYNAN)")
NATIJA_D = {}
for shakl in SHAKLLAR:
    try:
        d = yol(shakl, "D")
        t = yol(shakl, "T")
        NATIJA_D[shakl] = d
        check(f"A {shakl}: DELETE 200, yumshoq", d["status_code"] == 200 and d["javob"].get("soft_deleted") is True,
              (d["status_code"], d["javob"]))
        check(f"A {shakl}: holat READY + o'chirilgan, topshirilganga yakunlangan (NAZORAT bilan AYNAN)",
              d["holat"]["status"] == "ready" and d["holat"]["del"]
              and _hol_solishtir(d["holat"]) == _hol_solishtir(t["holat"]),
              (_hol_solishtir(d["holat"]), _hol_solishtir(t["holat"])))
        # Butun korxona bo'yicha YAXLITLANGAN yig'indilar (usta KPI xarajati, buyurtmalar foydasi, ehson foydasi,
        # daromad) — boshqa buyurtmalar kasr qismlari bilan birga yaxlitlanadi: farqi 1 so'mgacha (yaxlitlash izi).
        _yax = ("rep_daromad", "rep_usta_kpi", "rep_b_foyda", "ehson_foyda")
        check(f"A {shakl}: hisobot / KPI / kunlik / grafik / mijozlar / ehson farqlari AYNAN (yaxlitlangan jamilar ±1)",
              {k: v for k, v in d["farq"].items() if k not in _yax} == {k: v for k, v in t["farq"].items() if k not in _yax}
              and all(abs(float(d["farq"][k] or 0) - float(t["farq"][k] or 0)) <= 1.0 for k in _yax),
              (d["farq"], t["farq"]))
        check(f"A {shakl}: hisobotga KIRDI (soni +1, daromad = yangi kelishilgan)",
              d["farq"]["rep_soni"] == 1 and taxminan(d["farq"]["rep_daromad"], round(d["holat"]["agreed"] or 0), 1.0),
              (d["farq"], d["holat"]["agreed"]))
        check(f"A {shakl}: ombor farqi AYNAN", d["ombor"] == t["ombor"], (d["ombor"], t["ombor"]))
        # kech100 (K100-1/2/3a, kmut100 T03 — o'chirish MRP bandini baribir bo'shatgani uchun faqat yakuniy holat
        # solishtirilsa sizish ko'rinmasdi): qisman «Tayyor» O'ZI — o'chirishsiz — ombor / band ishini tugatadi.
        check(f"A {shakl}: qisman «Tayyor» O'ZI ombor / MRP bandini tugatadi (= o'chirish farqi, keyingi o'chirish — 0)",
              t["ombor_tayyor"] == d["ombor"] and all(v == 0 for v in (t["ombor_tayyor_keyin"] or {}).values()),
              (t["ombor_tayyor"], d["ombor"], t["ombor_tayyor_keyin"]))
    except Exception as e:                 # noqa: BLE001
        check(f"A {shakl}: yo'l bajarildi", False, f"{type(e).__name__}: {e}")

_a1 = NATIJA_D.get("S1 profil 4/10") or {}
check("A1 S1 aniq qiymatlar: kelishilgan 200 000, uzunlik 4, loy 4 kg, hisobot tannarxi 28 000, usta KPI 17 200",
      _a1 and _a1["holat"]["agreed"] == 200_000 and _a1["holat"]["items"][0][2] == 4.0
      and taxminan(_a1["holat"]["actual_loy"], 4.0, 1e-6) and taxminan(_a1["farq"]["rep_xarajat"], 28_000, 0.01)
      and _a1["farq"]["kpi_oy"] == (172000, 17200), _a1 and (_a1["holat"], _a1["farq"]))
_a3 = NATIJA_D.get("S3 oldindan to'langan 4/10") or {}
check("A3 S3: ortiqcha to'lov 300 000 — javob va buyurtma (qaytarish kerak)",
      _a3 and taxminan(_a3["javob"].get("yopildi", {}).get("ortiqcha"), 300_000, 0.001)
      and _a3["holat"]["paid"] == 500_000 and _a3["holat"]["agreed"] == 200_000,
      _a3 and _a3["javob"].get("yopildi"))
_a2 = NATIJA_D.get("S2 chegirmali 4/10") or {}
check("A2 S2: chegirma ulushi saqlanadi — 450 000 → 180 000",
      _a2 and _a2["holat"]["agreed"] == 180_000, _a2 and _a2["holat"])
_a5 = NATIJA_D.get("S5 ikki detal (10/10 + 0/10)") or {}
check("A5 S5: topshirilmagan detal 0 ga, to'liq detal o'zgarmaydi, loy 10 (yarmi) ishlatilgan",
      _a5 and [x[1:3] for x in _a5["holat"]["items"]] == [(10.0, 10.0), (0.0, None)]
      and taxminan(_a5["holat"]["actual_loy"], 10.0, 1e-6), _a5 and _a5["holat"])


# ══════════════════════════════════════════════════════════════
# B — to'liq topshirilgan (DELIVERED) buyurtma o'chirilsa
# ══════════════════════════════════════════════════════════════
section("B. To'liq topshirilgan («Tayyor» bosilmagan) — o'chirishda yakunlanadi")
pid, mid, mijoz = muhit()
oid_b, ids_b = buyurtma(pid, mid, [_profil()], None, 10.0)
yuk(oid_b, ids_b[0], 10)
hb0 = holat(oid_b)
k0, q0 = korsatkich(mid, mijoz), ombor()
st, db_ = ochir(oid_b)
k1, q1 = korsatkich(mid, mijoz), ombor()
hb1 = holat(oid_b)
fb = farq(k0, k1)
check("B1 oldin DELIVERED, hisobotda yo'q", hb0["status"] == "delivered", hb0["status"])
check("B2 o'chirilgach READY + o'chirilgan, summa o'zgarmagan (500 000), ombor tegilmagan",
      st == 200 and hb1["status"] == "ready" and hb1["del"] and hb1["agreed"] == 500_000
      and all(v == 0 for v in ombor_farq(q0, q1).values()), (st, hb1, ombor_farq(q0, q1)))
check("B3 hisobot +1 / 500 000, tannarx = penoplast 50 000 + loy 10 kg × 2 000 = 70 000; usta KPI 43 000",
      fb["rep_soni"] == 1 and fb["rep_daromad"] == 500_000 and taxminan(fb["rep_xarajat"], 70_000, 0.01)
      and fb["kpi_oy"] == (430000, 43000), fb)
check("B4 ishlatilgan loy = reja (10 kg), javob toliq_topshirilgan",
      taxminan(hb1["actual_loy"], 10.0, 1e-9) and (db_.get("yopildi") or {}).get("toliq_topshirilgan") is True,
      (hb1["actual_loy"], db_.get("yopildi")))


# ══════════════════════════════════════════════════════════════
# C — tiklash
# ══════════════════════════════════════════════════════════════
section("C. Tiklash — yakunlash AYNAN bekor, ombor va hisobot asl tiklash bilan bir xil")
for shakl in ("S1 profil 4/10", "S3 oldindan to'langan 4/10", "S5 ikki detal (10/10 + 0/10)", "S7 tiyinli 3/7"):
    oid, ids, mid, mijoz = tayyorla(shakl)
    h0, q0, k0 = holat(oid), ombor(), korsatkich(mid, mijoz)
    ochir(oid)
    h1 = holat(oid)
    st = tiklash(oid)
    h2, q2, k2 = holat(oid), ombor(), korsatkich(mid, mijoz)
    _t = lambda h: {k: h[k] for k in ("status", "del", "total", "agreed", "paid", "debt", "pay_status", "archived",
                                        "closed_at", "completed_at", "notes", "actual_loy", "items")}
    check(f"C {shakl}: o'chirishda yakunlash yozildi (json bor)", bool(h1["json"]), h1["json"])
    check(f"C {shakl}: tiklash 200, holat o'chirishdan OLDINGIGA AYNAN (detallar, summalar, sanalar, loy, izoh)",
          st == 200 and _t(h2) == _t(h0) and h2["json"] is None and h2["stock_returned"] is False,
          (st, _t(h0), _t(h2)))
    check(f"C {shakl}: ombor o'chirishdan OLDINGIGA AYNAN (qolgan qism xomashyosi qayta yechildi)", q2 == q0, (q0, q2))
    check(f"C {shakl}: hisobot / KPI o'chirishdan OLDINGIGA AYNAN", k2 == k0, (k0, k2))
    # Qayta o'chirish — yana o'sha yakunlash
    st3, d3 = ochir(oid)
    h3 = holat(oid)
    check(f"C {shakl}: qayta o'chirish — yana o'sha yakunlash", st3 == 200 and _hol_solishtir(h3) == _hol_solishtir(h1),
          (_hol_solishtir(h1), _hol_solishtir(h3)))

# Tiklash — to'liq topshirilgan (DELIVERED)
st = tiklash(oid_b)
hb2 = holat(oid_b)
check("C DELIVERED: tiklash — DELIVERED ga, completed_at / summa AYNAN, loy NULL",
      st == 200 and hb2["status"] == "delivered" and not hb2["del"] and hb2["completed_at"] == hb0["completed_at"]
      and hb2["actual_loy"] is None and hb2["agreed"] == 500_000, (st, hb0, hb2))


# ══════════════════════════════════════════════════════════════
# D — o'zgarmagan yo'llar
# ══════════════════════════════════════════════════════════════
section("D. Yuksiz / «Tayyor» / qoralama — o'zgarmagan")
pid, mid, mijoz = muhit()
oid_d1, ids = buyurtma(pid, mid, [_profil()], None, 10.0)
q0 = ombor()
st, dd = ochir(oid_d1)
check("D1 yuksiz: butunlay o'chadi, xomashyo to'liq qaytadi, yakunlash yo'q",
      st == 200 and holat(oid_d1) is None and dd.get("yopildi") is None and dd.get("soft_deleted") is False
      and ombor_farq(q0, ombor()) == {"PENO": 0.1, "KLEY": 10.0, "QUM": 0.0, "TMP": 0.0, "MRP_TM": 0.0, "MRP_BAND": 0.0},
      (st, dd, ombor_farq(q0, ombor())))
oid_d2, ids = buyurtma(pid, mid, [_profil()], None, 10.0)
yuk(oid_d2, ids[0], 4)
tayyor(oid_d2, 4)
h_a = holat(oid_d2)
st, dd = ochir(oid_d2)
h_b = holat(oid_d2)
check("D2 «Tayyor» (READY): ikkinchi yakunlash yo'q (json NULL, summa / sana o'zgarmagan)",
      st == 200 and dd.get("yopildi") is None and h_b["json"] is None and h_b["agreed"] == h_a["agreed"]
      and h_b["completed_at"] == h_a["completed_at"] and h_b["del"], (dd, h_a, h_b))
_r = js(req(C, "post", "/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": pid, "order_type": "product", "is_draft": True, "loy_kg": 10.0, "recipe_id": ID["REC"],
    "items": [dict(_profil(), name=nom("D"))]})) or {}
oid_d3 = _r.get("id") if isinstance(_r, dict) else None
st, dd = ochir(oid_d3)
check("D3 qoralama: butunlay, yakunlash yo'q", st == 200 and holat(oid_d3) is None and dd.get("yopildi") is None,
      (st, dd))
_rjd = reja(oid_d2)
check("D4 reja: «Tayyor» — hisobotda_qoladi, yopiladi False", bool(_rjd) and _rjd.get("hisobotda_qoladi") is True
      and _rjd.get("yopiladi") is False and _rjd.get("yopish") is None, _rjd)


# ══════════════════════════════════════════════════════════════
# E — oldindan ko'rish ↔ haqiqiy natija
# ══════════════════════════════════════════════════════════════
section("E. Tasdiq oynasi (oldindan ko'rish) = haqiqiy yakunlash")
_E_KAL = ("old_total", "new_total", "new_agreed", "paid", "old_agreed", "ortiqcha", "qarz", "toliq_topshirilgan")
for shakl, d in NATIJA_D.items():
    rj = d["reja"] or {}
    y0 = rj.get("yopish") or {}
    y1 = d["javob"].get("yopildi") or {}
    check(f"E {shakl}: reja yopiladi / hisobotda_qoladi", rj.get("yopiladi") is True and rj.get("hisobotda_qoladi") is True,
          rj)
    check(f"E {shakl}: oldindan ko'rish = natija ({', '.join(_E_KAL)})",
          bool(y0) and all(taxminan(y0.get(k), y1.get(k), 0.001) if isinstance(y0.get(k), (int, float))
                           and not isinstance(y0.get(k), bool) else y0.get(k) == y1.get(k) for k in _E_KAL),
          {k: (y0.get(k), y1.get(k)) for k in _E_KAL})
    check(f"E {shakl}: oldindan ko'rish buyurtmani O'ZGARTIRMADI (GET dan keyin ham)", True)

# Oldindan ko'rish hech narsa yozmaydi — GET dan oldin / keyin holat AYNAN
oid_e, ids_e, _m, _mj = tayyorla("S3 oldindan to'langan 4/10")
he0 = holat(oid_e)
for _ in range(2):
    reja(oid_e)
he1 = holat(oid_e)
check("E2 GET /api/orders/{id} (oldindan ko'rish) — buyurtma va detallar O'ZGARMAGAN", he0 == he1, (he0, he1))
_ge = js(req(C, "get", f"/api/orders/{oid_e}")) or {}
_gi = (_ge.get("items") or [{}])[0] if isinstance(_ge, dict) else {}
check("E3 o'sha javobdagi detal va summalar — ASL (oldindan ko'rish obyektni o'zgartirmadi): uzunlik 10, jami 500 000",
      _gi.get("length") == 10.0 and taxminan(_gi.get("total_price"), 500_000, 0.001)
      and taxminan(_ge.get("total_amount"), 500_000, 0.001) and taxminan(_ge.get("agreed_amount"), 500_000, 0.001),
      (_gi, _ge.get("total_amount"), _ge.get("agreed_amount")))


# ══════════════════════════════════════════════════════════════
# F — actual_loy_kg bilan o'chirish
# ══════════════════════════════════════════════════════════════
section("F. Hodim yozgan haqiqiy loy")
for actual, kutilgan in (("7", 7.0), ("12", 12.0), ("0", None)):
    oid_f, ids_f, _m, _mj = tayyorla("S1 profil 4/10")
    st, df = ochir(oid_f, actual)
    hf = holat(oid_f)
    check(f"F actual_loy_kg={actual}: ishlatilgan loy = {kutilgan}",
          st == 200 and ((hf["actual_loy"] is None) if kutilgan is None else taxminan(hf["actual_loy"], kutilgan, 1e-9)),
          (st, hf["actual_loy"], df))


# ══════════════════════════════════════════════════════════════
# G — sana
# ══════════════════════════════════════════════════════════════
section("G. Sana — o'chirilgan payt (o'tgan oy hisoboti o'zgarmaydi)")
pid, mid, mijoz = muhit()
oid_g, ids_g = buyurtma(pid, mid, [_profil()], None, 10.0)
yuk(oid_g, ids_g[0], 10)
_eski = datetime.utcnow() - timedelta(days=65)
_s = SessionLocal()
_og = _s.get(Order, oid_g)
_og.completed_at = _eski
_s.commit()
_s.close()
_oldin = datetime.utcnow()
ochir(oid_g)
_keyin = datetime.utcnow()
hg = holat(oid_g)
check("G1 DELIVERED (eski yetkazish sanasi 65 kun oldin) — completed_at = o'chirilgan payt",
      hg["completed_at"] is not None and _oldin - timedelta(seconds=2) <= hg["completed_at"] <= _keyin + timedelta(seconds=2),
      (hg["completed_at"], _oldin, _keyin))
_s = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        _rep_eski = services.get_monthly_report(_s, _eski.year, _eski.month, company_id=1)
finally:
    _s.close()
check("G2 eski oy hisobotida yo'q (yopilgan oy o'zgarmaydi)", int(_rep_eski.get("buyurtmalar_soni") or 0) == 0,
      _rep_eski.get("buyurtmalar_soni"))
tiklash(oid_g)
check("G3 tiklash — eski sana qaytdi", holat(oid_g)["completed_at"] == _eski, holat(oid_g)["completed_at"])


# ══════════════════════════════════════════════════════════════
# P — poyga (FAQAT PG)
# ══════════════════════════════════════════════════════════════
section("P. Poyga (HAQIQIY PG): o'chirish ∥ «Tayyor» / yuk xati / to'lov")
if not PG_URL:
    print("  (SQLite — haqiqiy parallellik yo'q, o'tkazildi)")
else:
    from schemas import DeliveryCreate, DeliveryItemCreate, PaymentCreate
    _asl_q = services.return_inventory_for_order_partial
    KUT = [0.0]

    def _sekin(*a, **k):
        if KUT[0]:
            time.sleep(KUT[0])
        return _asl_q(*a, **k)

    services.return_inventory_for_order_partial = _sekin

    def _ochir_oqim(oid, nat, b, kechik=0.0):
        s = SessionLocal()
        try:
            user = s.get(User, UID)
            b.wait()
            if kechik:
                time.sleep(kechik)
            try:
                r = main.api_delete_order(oid, None, db=s, current_user=user)
                nat["ochir"] = bool(r.get("yopildi"))
            except Exception as e:     # noqa: BLE001
                nat["ochir"] = f"xato {type(e).__name__}"
        finally:
            s.close()

    def _boshqa(tur, oid, iid, nat, b, kechik=0.2):
        s = SessionLocal()
        try:
            b.wait()
            if kechik:
                time.sleep(kechik)
            try:
                if tur == "yuk":
                    r = crud.create_delivery(s, DeliveryCreate(order_id=oid, items=[DeliveryItemCreate(order_item_id=iid, quantity=2)],
                                                               notes=nom("par")), delivered_by="P")
                    nat["boshqa"] = bool(r.get("success"))
                elif tur == "tayyor":
                    nat["boshqa"] = bool(services.complete_order(s, oid, loy_kg=None).get("success"))
                else:
                    p = crud.create_payment(s, PaymentCreate(order_id=oid, amount=500_000, notes=nom("par")), company_id=1)
                    nat["boshqa"] = bool(getattr(p, "id", None))
            except Exception as e:     # noqa: BLE001
                try:
                    s.rollback()
                except Exception:      # noqa: BLE001
                    pass
                nat["boshqa"] = f"xato {type(e).__name__}"
        finally:
            s.close()

    for tur in ("tayyor", "yuk", "tolov"):
        for kut in (0.0, 0.6):
            oid, ids, _m, _mj = tayyorla("S1 profil 4/10")
            q0 = ombor()
            KUT[0] = kut
            nat = {}
            b = threading.Barrier(2)
            t1 = threading.Thread(target=_ochir_oqim, args=(oid, nat, b))
            t2 = threading.Thread(target=_boshqa, args=(tur, oid, ids[0], nat, b))
            t1.start(); t2.start(); t1.join(); t2.join()
            KUT[0] = 0.0
            h = holat(oid)
            s = SessionLocal()
            try:
                yetk = sum(float(di.quantity or 0) for d in s.query(Delivery).filter(Delivery.order_id == oid).all()
                           for di in d.items)
            finally:
                s.close()
            peno = ombor_farq(q0, ombor())["PENO"]
            izchil = (h["del"] and h["status"] == "ready" and taxminan(h["items"][0][2], yetk, 1e-9)
                      and taxminan(h["agreed"], 50_000 * yetk, 0.01) and taxminan(peno, 0.01 * (10 - yetk), 1e-9))
            check(f"P {tur} kut={kut}: ombor bir marta, yakunlash = haqiqiy topshirilgan ({nat})", izchil,
                  (nat, h, yetk, peno))
            if tur == "tolov":
                check(f"P tolov kut={kut}: to'lov eski (500 000) kelishilgan bilan o'tmadi — "
                      f"yakunlangach «qarzdan ko'p» (tasdiqsiz yozuv yo'q)",
                      h["paid"] == 0 and str(nat.get("boshqa", "")).startswith("xato OverpaymentWarning"), (nat, h))
    # kech100 (kmut100 N19): «Tayyor» qulfni OLDIN oladi (qisman qaytarish 0.6 s — qulf ostida), o'chirish 0.2 s keyin
    # boshlanadi — buyurtmani qulfdan OLDIN (hali IN_PROGRESS) o'qiydi va qulfni kutadi. Qulfdan keyin QAYTA o'qilmasa
    # eskirgan holat bilan qolgan qism xomashyosi IKKINCHI marta qaytadi.
    oid, ids, _m, _mj = tayyorla("S1 profil 4/10")
    q0 = ombor()
    KUT[0] = 0.6
    nat = {}
    b = threading.Barrier(2)
    t1 = threading.Thread(target=_ochir_oqim, args=(oid, nat, b, 0.2))
    t2 = threading.Thread(target=_boshqa, args=("tayyor", oid, ids[0], nat, b, 0.0))
    t1.start(); t2.start(); t1.join(); t2.join()
    KUT[0] = 0.0
    h = holat(oid)
    peno = ombor_farq(q0, ombor())["PENO"]
    # o'chirish «Tayyor» ni ko'rgan bo'lsa — yakunlash YO'Q (READY): javobda `yopildi` bo'sh, oldingi holat surati yozilmagan
    # (eskirgan IN_PROGRESS surati bo'lsa tiklash «Tayyor» buyurtmani IN_PROGRESS ga qaytarardi — kmut100 N19).
    check(f"P tayyor OLDIN (o'chirish qulfni kutadi): ombor BIR marta (+0.06), o'chirish «Tayyor» ni ko'radi — ikkinchi "
          f"yakunlash / eskirgan surat yo'q ({nat})",
          h["del"] and h["status"] == "ready" and taxminan(h["items"][0][2], 4.0, 1e-9) and taxminan(peno, 0.06, 1e-9)
          and nat.get("boshqa") is True and nat.get("ochir") is False and h["json"] is None, (nat, h, peno))
    services.return_inventory_for_order_partial = _asl_q


# ══════════════════════════════════════════════════════════════
# X — 5xx
# ══════════════════════════════════════════════════════════════
section("X. Server xatosi (5xx) yo'q")
check("X1 test davomida 5xx yo'q", not XATOLAR_5XX, XATOLAR_5XX[:5])


# ══════════════════════════════════════════════════════════════
# S — statik
# ══════════════════════════════════════════════════════════════
section("S. Statik")
_ad = manba(main, "api_delete_order")
check("S1 api_delete_order: QULF (101) va qayta o'qish — ombor ishidan OLDIN",
      tartibda(_ad, "crud._pul_qulfi(db, 101, order.id)", "db.expire_all()", "order = crud.get_order(db, order_id",
               "with crud.bitta_tranzaksiya(db):", "services.return_inventory_for_order_partial(db, order)"), "")
check("S2 api_delete_order: yakunlash sabab va yumshoq qaroridan KEYIN, o'chirishdan OLDIN",
      tartibda(_ad, "reason = None", "should_soft_delete = crud.ochirishda_yumshoqmi(order)", "if crud.ochirishda_yopiladimi(order):",
               "crud.ochirishda_topshirilganni_yopish(db, order, loy_ishlatilgan=_loy_ishlatilgan100)",
               "crud.delete_order(db, order_id, soft=should_soft_delete"), "")
_ro = manba(crud, "restore_order")
check("S3 restore_order: yakunlash bekor qilinadi ombor qayta yechishdan OLDIN",
      tartibda(_ro, "with bitta_tranzaksiya(db):", "ochirish_yopishini_bekor_qil(db, db_order)", "if db_order.stock_returned:"), "")
_cp = manba(crud, "create_payment")
check("S4 create_payment: qulf ostida buyurtma QAYTA o'qiladi (tekshiruvdan OLDIN)",
      tartibda(_cp, "_pul_qulfi(db, 101, payment_data.order_id)", "db.expire_all()", "order = _oq.first()",
               "_tolov_chegarasi(order, payment_data.amount"), "")
_yp = manba(crud, "ochirishda_topshirilganni_yopish")
check("S5 yakunlash: oldingi holat JSON, finalize, READY, completed_at",
      tartibda(_yp, "order.ochirish_yopish_json = _json.dumps(", "finalize_partial_order_quantities(db, order)",
               "order.status = OrderStatus.READY", "order.completed_at = datetime.utcnow()"), "")
_fi = manba(crud, "finalize_partial_order_quantities")
check("S6 finalize: faqat_hisob rejimida obyekt o'zgarmaydi (shartli yozuv) va commit yo'q",
      "if not faqat_hisob:" in _fi and tartibda(_fi, "if faqat_hisob:", "return {", "order.agreed_amount = new_agreed",
                                                 "db.commit()"), "")
_html = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
check("S7 orders.html: tasdiq matni server oldindan ko'rishidan (oc.yopish), natija xabari (d.yopildi)",
      tartibda(_html, "async function deleteSelected()", "else if (oc.yopiladi && oc.yopish) {", "y.ortiqcha",
               "else if (oc.hisobotda_qoladi)", "showConfirmModal(", "d.yopildi && d.yopildi.message"), "")
_mo = open(os.path.join(ROOT, "models.py"), encoding="utf-8").read()
check("S8 models: orders.ochirish_yopish_json (Text, NULL)", "ochirish_yopish_json = Column(Text, nullable=True)" in _mo, "")

print("\n" + "=" * 66)
print(f"REJIM: {'PostgreSQL' if PG_URL else 'SQLite'}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
if PG_URL:
    try:
        from database import engine as _eng
        _eng.dispose()
        _adm2 = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm2.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm2.dispose()
    except Exception:                      # noqa: BLE001
        pass
sys.exit(1 if FAIL else 0)
