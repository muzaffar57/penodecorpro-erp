#!/usr/bin/env python3
"""
test_qaytarish_query.py — 17g-band: qaytarish (`POST /api/returns`), yetkazish
(`POST /api/deliveries`), xarid narxi va jamisining yaxlitlanishi (3 xonali
narx), ta'minotchi to'lovining xarid bilan birga yozilishi.

NIMA UCHUN KERAK (2026-09-22)
-----------------------------
Hammasi HAQIQIY PostgreSQL 16 da O'LCHANGAN (asl kod = 17f). SQLite
`Numeric(12,2)` ni yaxlitlamaydi va sig'im oshishini sezmaydi.

1) QAYTARISH: miqdor manfiy / 0 / `1e20` / buyurtmadagidan ko'p — 200 bilan
   saqlanardi; `Infinity` / `NaN` — SAQLANIB tayyor mahsulot qoldig'ini
   cheksiz / "son emas" qilardi (keyin 500); summa `NaN` bazaga "NaN" bo'lib
   yozilardi, `Infinity` / `1e20` — 500, `0.001` → 0.00, manfiy — jimgina avto
   hisob; noma'lum sabab jimgina "Brak" (xomashyo yechilardi); uzun nom /
   birlik — 500; `true` / `"2"` — qabul; 1 000 000 lik buyurtmaga 9e9 so'm
   qaytarish saqlanardi. Buyurtmada YO'Q detal nomi bilan (detal ID siz) istalgan
   miqdor saqlanardi (kech25 da o'lchangan).
2) YETKAZISH: to'lov / transport `Infinity` / `1e20` — 500; to'lov `0.001` →
   0 so'mlik to'lov; `true` → 1 so'm, `"7"`; noma'lum to'lovchi saqlanib
   transport Moliyadan tushib qolardi; noma'lum usul jimgina naqd; uzun
   matnlar — 500; to'lov qo'lda to'lov chegaralarini (3 baravar, ortiqcha to'lov
   tasdig'i) chetlab o'tardi. Bitta yetkazishda BIR detal ikki qatorda
   berilsa — buyurtmadagidan ko'p topshirilardi (10 dan 12, kech25).
   17g WIP da qo'yilgan 500 qatorlik chegara 500 dan ko'p detalli buyurtmaning
   "Tayyor" belgisini 500 ga, "bir yo'la to'liq topshirish" ni 400 ga
   tushirardi (kech25 da o'lchangan, 17f da ishlardi).
3) 3 XONALI NARX: narx va jami ALOHIDA yaxlitlanardi — 333 × 10.335 → narx
   10.34, jami 3441.56 (to'g'risi 3443.22); xarid marshruti jamini butun so'mga
   yaxlitlab "nasiya/to'langan" qarorini boshqa summaga tayanardi.
4) TA'MINOTCHI: 8 s ichida shu summada qo'lda to'lov bo'lsa xarid to'lovi
   YARATILMASDI; avansli ta'minotchi yoki kasr so'mli xarid qisman to'langanda
   xarid saqlanib, keyin 500 (yarim saqlanish).
6) TAKROR / PARALLEL YETKAZISH (kech27, HAQIQIY PG 16 da O'LCHANGAN, asl kod =
   17g `3319f4a`, har holat 12 urinishdan 12 tasida): bir xil qisman yetkazish
   (+ to'lov) ketma-ket ikki marta → 2 yetkazish, 2 to'lov; ikki foydalanuvchi
   bir vaqtda 20 + 19 (qoldiq 30) → IKKALASI saqlanib 39 topshirilardi,
   to'lovsiz holatda ikkala raqam ham bir xil "/Y-1" (qoldiq tekshiruvi qulfsiz,
   qulf faqat to'lovda va tekshiruvdan KEYIN olinardi).
5) QAYTARISH SUMMASI CHEGARASI UI ni to'smasin: `returns.html` summani 1 birlik
   narxini BUTUN so'mga yaxlitlab hisoblaydi va chegirmali buyurtmada
   chegirmasiz narxdan oladi — bu qiymatlar 400 bilan rad etilmasligi SHART
   (hodimda summa maydoni yashirin — tuzatib bo'lmaydi; kech25 da o'lchangan).

QAMROV
------
R. Qaytarish: yomon tanalar 400 (sabab), holat o'zgarmagan; `returns.html`
   `saveReturn` va `saveBrakBatch` tanalari AYNAN 200 va aniq qiymatlar;
   chegirmali / yaxlitlangan narxli buyurtmada UI summasi 200; begona — 404
D. Yetkazish: yomon tanalar 400, holat o'zgarmagan; 0.005 → 0.01; 409 → hech
   narsa yozilmagan, `confirm_overpay` bilan 200; 3 baravar → 400; bir detal
   ikki qatorda → 400; `orders.html` ikkala tanasi AYNAN 200; "Tayyor"
   belgisidagi avtomatik yetkazish (501 detal bilan ham)
N. 3 xonali narx: xarid / kirim hujjati / tahrir / boshlang'ich qoldiq —
   jami == narx × miqdor (HALF_UP); sig'im 2 × 4 999 999 999.995 → 400
S. Ta'minotchi to'lovi xarid bilan: takror-himoya, avans, kasr so'm
F. Ildiz: `create_delivery`, `create_return_item`, `_tolov_chegarasi`,
   `_xarid_narx_jami`, `_pul2` — bazaga tegmasdan rad
T. Takror / parallel yetkazish (kech27): bir xil so'rov → `duplicate`, o'sha
   yetkazish, hech narsa qo'shilmaydi, Telegram / nakladnoy qayta ketmaydi;
   har maydon farqi → yangi yetkazish; oyna 6 s ichida takror, 10 s da yangi;
   to'liq yetkazish + to'liq to'lov takrori 200 (400 / 409 EMAS); begona
   korxona — 400; eskirgan sessiya (qulfdan oldin o'qilgan qoldiq) va
   chaqiruvchining yozilmagan o'zgarishi; PG da ikki oqim bir vaqtda
   (bir xil / farqli, to'lovli / to'lovsiz); statik — qulf va imzo tartibi
G. Statik: tekshiruv TARTIBI, marshrut turlari, qoidalar, sxemalar, UI
H. 422 qoladi (tana lug'at emas / buzilgan JSON)
K. KUMULYATIV: sahifalar 200; hech bir javob 5xx emas
P. PostgreSQL (`PG_URL` bo'lsa): skript o'zini `QAYTARISH_PG_REJIM=1` bilan
   YANGI bazada qayta ishga tushiradi (R, D, N, S, F, T, H, K), saqlangan pul
   matni AYNAN kutilgan (masalan "3443.22").

ISHLATISH
---------
    python tools/test_qaytarish_query.py
    TENANT_FILTER=1 python tools/test_qaytarish_query.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python tools/test_qaytarish_query.py

Asl kodga qarshi ham QULAMAYDI (mutatsiya uchun): yangi yordamchilarga
murojaat `getattr` bilan, ildiz chaqiruvlari `try/except` bilan, HTTP
istisnolar 599 ga aylantiriladi, statik tartib `tartibda()` (`find`) bilan.

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import json
import math
import shutil
import inspect
import tempfile
import subprocess
import threading
from types import SimpleNamespace
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_REJIM = os.environ.get("QAYTARISH_PG_REJIM") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qaytarish_query_test"

_DB = os.path.join(tempfile.gettempdir(), "qaytarish_query_test.db")
_SNAP = _DB + ".nusxa"

if PG_REJIM:
    # Har ishga YANGI PostgreSQL bazasi (izolyatsiya qoidasi).
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
               isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    for _f in (_DB, _SNAP):
        if os.path.exists(_f):
            os.remove(_f)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, schemas                     # noqa: E402

from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Delivery, DeliveryItem, Payment, ReturnItem,
    ReturnReason, FinishedProduct, Inventory, InventoryPurchase, Supplier,
    SupplierPayment, ExpenseTransaction, TransportExpense,
)
from fastapi.testclient import TestClient          # noqa: E402

OK = FAIL = 0
FAILED = []
KODLAR = []          # barcha HTTP javob kodlari (K: 5xx yo'qligi)
YORLIQ = "[PG] " if PG_REJIM else ""


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:300]}")


def section(t):
    print(f"\n--- {YORLIQ}{t} ---")


def yaqin(a, b, eps=1e-6):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


def pul_ok(v, kutilgan):
    """Saqlangan pul qiymati AYNAN `kutilgan` (2 xonali). SQLite yaxlitlamaydi
    — 2 xonaga yaxlitlanmagan qiymat saqlangan bo'lsa ham shu yerda
    ushlanadi (float taqqoslash, 1e-9 aniqlikda); PostgreSQL da saqlangan
    MATN aynan `kutilgan` bo'lishi SHART."""
    if v is None:
        return False
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    if abs(f - kutilgan) > 1e-9:
        return False
    if PG_REJIM:
        return str(v) == f"{kutilgan:.2f}"
    return True


def js_round(x):
    """JavaScript `Math.round` (0.5 — yuqoriga)."""
    return math.floor(x + 0.5)


def tartibda(src, *qismlar):
    """`qismlar` `src` ichida AYNAN shu tartibda uchraydimi. Birortasi yo'q
    bo'lsa — False (asl kodga qarshi `ValueError` bilan QULAMASLIK uchun)."""
    joy = -1
    for q in qismlar:
        i = src.find(q, joy + 1)
        if i < 0:
            return False
        joy = i
    return True


def manba(obj):
    try:
        return inspect.getsource(obj)
    except Exception:
        return ""


def fayl(nom):
    try:
        with open(os.path.join(ROOT, nom), encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def js_funksiya(src, nom):
    """HTML dan `function nom(` tanasini (qavslar bo'yicha) ajratib oladi."""
    for bosh in (f"async function {nom}(", f"function {nom}("):
        i = src.find(bosh)
        if i >= 0:
            j = src.find("{", i)
            d = 0
            for k in range(j, len(src)):
                if src[k] == "{":
                    d += 1
                elif src[k] == "}":
                    d -= 1
                    if d == 0:
                        return src[i:k + 1]
    return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="Test Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "QY_admin", "Parol123!", UserRole.ADMIN, "QY Admin", company_id=1)
    auth.create_user(_db, "QY_admin_b", "Parol123!", UserRole.ADMIN, "QY Admin B", company_id=2)

PRJ = Project(company_id=1, client_name="QY Mijoz", project_name="QY loyiha",
              total_budget=0, total_paid=0)
PRJ_B = Project(company_id=2, client_name="QY Mijoz B", project_name="QY loyiha B",
                total_budget=0, total_paid=0)
MAT = Inventory(company_id=1, item_name="QY_SEMENT", unit="kg",
                stock_quantity=100.0, price_per_unit=1000, min_stock=0)
SUP = Supplier(company_id=1, name="QY_TAMIN", phone="+998900008801")
SUP_T = Supplier(company_id=1, name="QY_TAMIN_TAKROR", phone="+998900008802")
SUP_AV = Supplier(company_id=1, name="QY_TAMIN_AVANS", phone="+998900008803")
SUP_K = Supplier(company_id=1, name="QY_TAMIN_KASR", phone="+998900008804")
SUP_N = Supplier(company_id=1, name="QY_TAMIN_NARX", phone="+998900008805")
_db.add_all([PRJ, PRJ_B, MAT, SUP, SUP_T, SUP_AV, SUP_K, SUP_N])
_db.commit()
PRJ_ID, PRJB_ID, M_ID = PRJ.id, PRJ_B.id, MAT.id
S_ID, ST_ID, SAV_ID, SK_ID, SN_ID = SUP.id, SUP_T.id, SUP_AV.id, SUP_K.id, SUP_N.id
_db.close()

_n = [0]


def yangi_buyurtma(miqdor=10, narx=100_000, soni_=1, kelishilgan=None, cid=1, prj=None):
    """YANGI buyurtma (panel, penoplastsiz — ombor kerak emas) →
    (order_id, [detal_id], [detal_nomi]). `kelishilgan` — chegirmali summa."""
    _n[0] += 1
    d = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            o = crud.create_order(d, schemas.OrderCreate(
                project_id=prj or PRJ_ID, order_type="product",
                items=[schemas.OrderItemCreate(
                    name=f"QY_D{_n[0]}_{i}", category="panel", width=100, thickness=10,
                    length=100, quantity=miqdor, unit_price=narx, is_coated=False)
                    for i in range(soni_)]), performed_by="QY")
        oid = o.id
        o2 = d.get(Order, oid)
        if o2.company_id != cid:
            o2.company_id = cid
        if kelishilgan is not None:
            o2.agreed_amount = kelishilgan
        items = d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()
        for it in items:
            if getattr(it, "company_id", cid) != cid:
                it.company_id = cid
        d.commit()
        return oid, [x.id for x in items], [x.name for x in items]
    finally:
        d.close()


# Yomon tana problari uchun buyurtmalar (fiksturada — ular o'zgarmaydi)
OR_ID, (OR_I,), (OR_NOM,) = yangi_buyurtma()                 # qaytarish
OD_ID, (OD_I,), (OD_NOM,) = yangi_buyurtma()                 # yetkazish
OB_ID, (OB_I,), (OB_NOM,) = yangi_buyurtma(cid=2, prj=PRJB_ID)  # begona korxona


def login(user):
    c = TestClient(main.app, base_url="https://testserver",
                   raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": "Parol123!"},
               follow_redirects=False)
    assert r.status_code == 302, f"{user} login bo'lmadi: {r.status_code}"
    return c


class _R599:
    status_code = 599

    def __init__(self, e):
        self.text = f"ISTISNO: {type(e).__name__}: {e}"

    def json(self):
        return {}


def req(client, method, url, **kw):
    """Server istisnosi skriptni qulatmasin (asl kodga qarshi mutatsiya)."""
    try:
        r = getattr(client, method)(url, **kw)
    except Exception as e:          # pragma: no cover — himoya qatlami
        r = _R599(e)
    KODLAR.append((r.status_code, method, url))
    return r


def xom(client, method, url, raw):
    return req(client, method, url, content=raw,
               headers={"Content-Type": "application/json"})


def jsn(r):
    try:
        return r.json()
    except Exception:
        return None


def matn(r):
    return getattr(r, "text", "") or ""


C = login("QY_admin")
CB = login("QY_admin_b")

# Tahrir uchun xarid — API orqali (maydonlari haqiqiy oqimdagidek)
req(C, "post", f"/api/inventory/{M_ID}/purchase",
    json={"quantity": 5, "price_per_unit": 1000, "supplier_id": S_ID})
_d = SessionLocal()
P_ID = _d.query(InventoryPurchase).order_by(InventoryPurchase.id.desc()).first().id
_d.close()

# IZOLYATSIYA: har prob oldidan fikstura bazasi tiklanadi (faqat SQLite;
# PostgreSQL rejimida har tekshiruv o'z oldingi holatiga nisbatan).
if not PG_REJIM:
    engine.dispose()
    shutil.copy(_DB, _SNAP)


def tikla():
    if PG_REJIM:
        return
    engine.dispose()
    shutil.copy(_SNAP, _DB)


def holat():
    """17g tegadigan hamma jadvallar."""
    d = SessionLocal()
    try:
        def q(model, *ustunlar):
            return [tuple(str(getattr(x, u)) for u in ustunlar)
                    for x in d.query(model).order_by(model.id)]
        return {
            "ri": q(ReturnItem, "id", "order_id", "item_name", "quantity", "unit", "reason",
                    "refund_amount", "is_refunded"),
            "dl": q(Delivery, "id", "order_id", "transport_cost", "transport_payer",
                    "received_by", "transport_carrier"),
            "di": q(DeliveryItem, "id", "delivery_id", "order_item_id", "quantity"),
            "pay": q(Payment, "id", "order_id", "amount", "payment_method", "delivery_id"),
            "or": q(Order, "id", "status", "agreed_amount", "payment_status", "is_archived"),
            "prj": q(Project, "id", "total_paid"),
            "fp": q(FinishedProduct, "id", "quantity"),
            "inv": q(Inventory, "id", "stock_quantity", "price_per_unit"),
            "ip": q(InventoryPurchase, "id", "quantity", "price_per_unit", "total_amount",
                    "is_credit"),
            "sp": q(SupplierPayment, "id", "supplier_id", "amount"),
            "et": q(ExpenseTransaction, "id", "amount", "category"),
            "te": q(TransportExpense, "id", "amount"),
        }
    finally:
        d.close()


def oxirgi(model, **flt):
    d = SessionLocal()
    try:
        q = d.query(model)
        for k, v in flt.items():
            q = q.filter(getattr(model, k) == v)
        return q.order_by(model.id.desc()).first()
    finally:
        d.close()


def soni(model, **flt):
    d = SessionLocal()
    try:
        q = d.query(model)
        for k, v in flt.items():
            q = q.filter(getattr(model, k) == v)
        return q.count()
    finally:
        d.close()


def fp_jami():
    d = SessionLocal()
    try:
        return round(sum(float(x.quantity or 0) for x in d.query(FinishedProduct).all()), 6)
    finally:
        d.close()


def buyurtma(oid):
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        if o is None:
            return None
        return SimpleNamespace(status=getattr(o.status, "value", o.status),
                               agreed=float(o.agreed_amount or 0), debt=float(o.debt_amount),
                               payment_status=getattr(o.payment_status, "value", o.payment_status),
                               delivered=[float(i.delivered_qty) for i in o.items])
    finally:
        d.close()


SAHIFALAR = ["/returns", "/orders", "/api/returns", "/api/returns/stats", "/api/orders",
             f"/api/orders/{OD_ID}", f"/api/orders/{OD_ID}/delivery-status", "/api/payments",
             "/api/projects", "/api/finance/history", "/api/finance/transactions",
             "/api/inventory", "/api/transport-expenses", "/debts", "/finance"]


def sahifalar_yiqilgan(c, royxat=None):
    yomon = []
    for u in (SAHIFALAR if royxat is None else royxat):
        r = req(c, "get", u)
        if r.status_code != 200:
            yomon.append((u, r.status_code))
    return yomon


def yomon_tekshir(harf, url, asos, holatlar):
    """`holatlar`: (nom, o'zgarish, kutilgan_sabab). O'zgarish — lug'at
    (asos ustiga; qiymati `KALIT_YOQ` bo'lsa kalit olib tashlanadi) yoki
    funksiya (asos nusxasini oladi va o'zgartiradi)."""
    for nom, ozg, sabab in holatlar:
        tikla()
        tana = json.loads(json.dumps(asos))
        if callable(ozg):
            ozg(tana)
        else:
            for k, v in ozg.items():
                if v is KALIT_YOQ:
                    tana.pop(k, None)
                else:
                    tana[k] = v
        h0 = holat()
        r = xom(C, "post", url, json.dumps(tana))
        check(f"{harf} {nom} → 400 ('{sabab}'), holat o'zgarmagan",
              r.status_code == 400 and sabab in matn(r) and holat() == h0,
              f"{r.status_code} {matn(r)[:180]}")


KALIT_YOQ = object()
INF, NAN = float("inf"), float("nan")


# ══════════════════════════════════════════════════════════════
# R. Qaytarish
# ══════════════════════════════════════════════════════════════
def r_bolimi():
    section("R. Qaytarish — yomon tana 400, holat o'zgarmagan")
    asos = {"order_id": OR_ID, "order_item_id": OR_I, "item_name": OR_NOM, "quantity": 2,
            "unit": "metr", "reason": "Ortiqcha", "refund_amount": 0, "to_stock": True,
            "notes": None, "coating_applied": False}

    def qator(**kw):
        return kw

    yomon_tekshir("R", "/api/returns", asos, [
        ("miqdor -5", qator(quantity=-5), "'quantity'"),
        ("miqdor 0", qator(quantity=0), "'quantity'"),
        ("miqdor 1e20", qator(quantity=1e20), "'quantity'"),
        ("miqdor Infinity", qator(quantity=INF), "'quantity'"),
        ("miqdor NaN", qator(quantity=NAN), "'quantity'"),
        ("miqdor true", qator(quantity=True), "'quantity'"),
        ("miqdor \"2\"", qator(quantity="2"), "'quantity'"),
        ("miqdor buyurtmadagidan ko'p (10.01 > 10)", qator(quantity=10.01), "Buyurtmada"),
        ("summa NaN", qator(refund_amount=NAN), "'refund_amount'"),
        ("summa Infinity", qator(refund_amount=INF), "'refund_amount'"),
        ("summa 1e20", qator(refund_amount=1e20), "'refund_amount'"),
        ("summa 0.001", qator(refund_amount=0.001), "'refund_amount'"),
        ("summa 0.004", qator(refund_amount=0.004), "'refund_amount'"),
        ("summa -100", qator(refund_amount=-100), "'refund_amount'"),
        ("summa \"5\"", qator(refund_amount="5"), "'refund_amount'"),
        ("summa true", qator(refund_amount=True), "'refund_amount'"),
        ("summa 9e9 (buyurtma 1 000 000)", qator(refund_amount=9e9), "Qaytariladigan summa"),
        ("summa chegaradan 1 so'm ko'p (1 000 000 + 0.5×2 + 0.5 + 1)",
         qator(refund_amount=1_000_002.6), "Qaytariladigan summa"),
        ("sabab \"xyz\"", qator(reason="xyz"), "'reason'"),
        ("sabab yo'q", qator(reason=KALIT_YOQ), "'reason'"),
        ("sabab null", qator(reason=None), "'reason'"),
        ("nom 151 belgi", qator(item_name="n" * 151), "'item_name'"),
        ("nom bo'sh", qator(item_name="   "), "'item_name'"),
        ("birlik 21 belgi", qator(unit="u" * 21), "'unit'"),
        ("noma'lum kalit", qator(foo=1), "Noma'lum maydon"),
        ("order_id yo'q", qator(order_id=KALIT_YOQ), "'order_id'"),
        ("order_id \"5\"", qator(order_id=str(OR_ID)), "'order_id'"),
        ("order_id true", qator(order_id=True), "'order_id'"),
        ("order_item_id \"3\"", qator(order_item_id=str(OR_I)), "'order_item_id'"),
        ("to_stock \"yes\"", qator(to_stock="yes"), "'to_stock'"),
        ("to_stock null", qator(to_stock=None), "'to_stock'"),
        ("coating_applied 1", qator(coating_applied=1), "'coating_applied'"),
        ("gips_kg_used -1", qator(gips_kg_used=-1), "'gips_kg_used'"),
        ("izoh 10 001 belgi", qator(notes="z" * 10_001), "'notes'"),
        ("buyurtmada YO'Q detal nomi (detal ID siz)",
         qator(order_item_id=KALIT_YOQ, item_name="QY_BOSHQA_NOM", quantity=999_999),
         "detali topilmadi"),
    ])

    tikla()
    h0 = holat()
    r = req(C, "post", "/api/returns", json={**asos, "order_id": OB_ID, "order_item_id": OB_I,
                                             "item_name": OB_NOM})
    check("R begona korxona buyurtmasi → 404, holat o'zgarmagan",
          r.status_code == 404 and holat() == h0, f"{r.status_code} {matn(r)[:120]}")
    r = req(C, "post", "/api/returns", json={**asos, "order_item_id": OB_I})
    check("R o'z buyurtmasi + begona detal → 404, holat o'zgarmagan",
          r.status_code == 404 and holat() == h0, f"{r.status_code} {matn(r)[:120]}")
    r = req(C, "post", "/api/returns", json={**asos, "order_id": 2_000_000_000})
    check("R mavjud bo'lmagan buyurtma → 404", r.status_code == 404 and holat() == h0,
          f"{r.status_code} {matn(r)[:120]}")

    section("R. Qaytarish — to'g'ri tanalar va UI (`returns.html`) tanalari")
    # asos (nazorat) — shu tananing o'zi 200 (yomon problar faqat o'zgargan maydon tufayli)
    tikla()
    n0 = soni(ReturnItem)
    r = req(C, "post", "/api/returns", json=asos)
    ri = oxirgi(ReturnItem)
    check("R nazorat: asos tana → 200, bitta qaytarish yozildi",
          r.status_code == 200 and soni(ReturnItem) == n0 + 1 and ri is not None
          and yaqin(ri.quantity, 2), f"{r.status_code} {matn(r)[:160]}")
    tikla()
    r = req(C, "post", "/api/returns", json={**asos, "quantity": 10})
    check("R butun buyurtma miqdori (10 dan 10) → 200", r.status_code == 200,
          f"{r.status_code} {matn(r)[:160]}")

    # saveReturn — "Ortiqcha", miqdor 2.5, summa = Math.round(2.5 × price_per_unit_final)
    tikla()
    oid, (iid,), (nom,) = yangi_buyurtma()
    o = jsn(req(C, "get", f"/api/orders/{oid}")) or {}
    it = next((x for x in (o.get("items") or []) if x.get("id") == iid), {})
    narx1 = it.get("price_per_unit_final") or 0
    birlik = it.get("delivery_unit")
    summa = js_round(2.5 * narx1)
    fp0, n0 = fp_jami(), soni(ReturnItem)
    tana = {"order_id": int(str(oid)), "order_item_id": iid, "item_name": it.get("name"),
            "quantity": 2.5, "unit": birlik, "reason": "Ortiqcha",
            "refund_amount": float(summa) or 0, "to_stock": True, "notes": None,
            "coating_applied": False}
    r = xom(C, "post", "/api/returns", json.dumps(tana))
    ri = oxirgi(ReturnItem)
    check("R saveReturn (Ortiqcha, 2.5 metr, UI summasi) → 200, aniq qiymatlar, omborga +2.5",
          r.status_code == 200 and soni(ReturnItem) == n0 + 1 and ri is not None
          and yaqin(ri.quantity, 2.5) and ri.unit == "metr"
          and getattr(ri.reason, "value", ri.reason) == "Ortiqcha"
          and pul_ok(ri.refund_amount, 250_000.0) and yaqin(fp_jami(), fp0 + 2.5)
          and ri.item_name == nom,
          f"{r.status_code} {matn(r)[:160]} narx1={narx1} birlik={birlik} "
          f"{ri and (ri.quantity, ri.unit, ri.refund_amount)} fp {fp0}->{fp_jami()}")
    # saveReturn — butun son miqdor (JSON `2`), summa maydoni bo'sh (0) → server hisoblaydi
    r = xom(C, "post", "/api/returns", json.dumps({**tana, "quantity": 2, "refund_amount": 0,
                                                     "notes": "QY izoh"}))
    ri = oxirgi(ReturnItem)
    check("R saveReturn (miqdor butun son 2, summa 0) → 200, server hisobi 200 000",
          r.status_code == 200 and ri is not None and yaqin(ri.quantity, 2)
          and pul_ok(ri.refund_amount, 200_000.0) and ri.notes == "QY izoh",
          f"{r.status_code} {matn(r)[:160]} {ri and ri.refund_amount}")
    # saveReturn — "Brak" (to_stock true, lekin brak omborga qaytmaydi)
    fp0 = fp_jami()
    r = xom(C, "post", "/api/returns", json.dumps({**tana, "quantity": 1, "reason": "Brak",
                                                     "refund_amount": 0,
                                                     "coating_applied": True}))
    ri = oxirgi(ReturnItem)
    check("R saveReturn (Brak) → 200, sabab Brak, omborga QO'SHILMADI",
          r.status_code == 200 and ri is not None
          and getattr(ri.reason, "value", ri.reason) == "Brak" and yaqin(fp_jami(), fp0),
          f"{r.status_code} {matn(r)[:160]}")

    # saveBrakBatch — `/api/projects/{id}/items` dan AYNAN UI kabi
    tikla()
    oid, (iid,), (nom,) = yangi_buyurtma()
    pj = jsn(req(C, "get", f"/api/projects/{PRJ_ID}/items")) or {}
    b = next((x for x in (pj.get("items") or []) if x.get("item_id") == iid), None)
    check("R `/api/projects/{id}/items`: order_id / item_id — butun son, birlik matn",
          b is not None and type(b.get("order_id")) is int and type(b.get("item_id")) is int
          and isinstance(b.get("delivery_unit"), str), str(b)[:200])
    b = b or {}
    fp0, n0 = fp_jami(), soni(ReturnItem)
    tana_b = {"order_id": b.get("order_id"), "order_item_id": b.get("item_id"),
              "item_name": b.get("name"), "quantity": 1.5, "unit": b.get("delivery_unit"),
              "reason": "Brak", "refund_amount": 0, "to_stock": False, "notes": None,
              "coating_applied": False}
    r = xom(C, "post", "/api/returns", json.dumps(tana_b))
    ri = oxirgi(ReturnItem)
    check("R saveBrakBatch tanasi → 200, Brak 1.5, omborga qo'shilmadi",
          r.status_code == 200 and soni(ReturnItem) == n0 + 1 and ri is not None
          and yaqin(ri.quantity, 1.5) and yaqin(fp_jami(), fp0), f"{r.status_code} {matn(r)[:160]}")
    r = xom(C, "post", "/api/returns", json.dumps({**tana_b, "quantity": 10, "notes": "takror"}))
    check("R takroriy brak (yig'indi buyurtmadan ko'p) — RUXSAT (haqiqatda bo'ladi) → 200",
          r.status_code == 200, f"{r.status_code} {matn(r)[:160]}")

    # Chegirmali buyurtma: UI summasi chegirmasiz narxdan (1 000 000 > kelishilgan 900 000)
    tikla()
    oid, (iid,), (nom,) = yangi_buyurtma(kelishilgan=900_000)
    o = jsn(req(C, "get", f"/api/orders/{oid}")) or {}
    it = next((x for x in (o.get("items") or []) if x.get("id") == iid), {})
    summa = js_round(10 * (it.get("price_per_unit_final") or 0))
    r = req(C, "post", "/api/returns", json={
        "order_id": oid, "order_item_id": iid, "item_name": nom, "quantity": 10, "unit": "metr",
        "reason": "Ortiqcha", "refund_amount": summa, "to_stock": True, "notes": None,
        "coating_applied": False})
    check(f"R chegirmali buyurtma, butun qaytarish, UI summasi {summa} → 200 (UI rad etilmaydi)",
          r.status_code == 200, f"{r.status_code} {matn(r)[:180]}")
    # Yaxlitlangan 1 birlik narxi: 6 × 166 666.67 — UI 6 × 166 667 = 1 000 002
    tikla()
    oid, (iid,), (nom,) = yangi_buyurtma(miqdor=6, narx=166_666.67)
    o = jsn(req(C, "get", f"/api/orders/{oid}")) or {}
    it = next((x for x in (o.get("items") or []) if x.get("id") == iid), {})
    summa = js_round(6 * (it.get("price_per_unit_final") or 0))
    r = req(C, "post", "/api/returns", json={
        "order_id": oid, "order_item_id": iid, "item_name": nom, "quantity": 6, "unit": "metr",
        "reason": "Ortiqcha", "refund_amount": summa, "to_stock": True, "notes": None,
        "coating_applied": False})
    check(f"R yaxlitlangan birlik narxi (jami {o.get('total_amount')}), UI summasi {summa} → 200",
          r.status_code == 200, f"{r.status_code} {matn(r)[:180]}")


# ══════════════════════════════════════════════════════════════
# D. Yetkazish
# ══════════════════════════════════════════════════════════════
def d_bolimi():
    section("D. Yetkazish — yomon tana 400, holat o'zgarmagan")
    asos = {"order_id": OD_ID, "items": [{"order_item_id": OD_I, "quantity": 2}],
            "received_by": None, "notes": None, "payment_amount": None, "payment_method": "naqd",
            "transport_carrier": None, "transport_cost": 0, "transport_payer": "none"}

    def q(**kw):
        return kw

    def qator(**kw):
        def f(t):
            t["items"][0].update(kw)
        return f

    yomon_tekshir("D", "/api/deliveries", asos, [
        ("to'lov Infinity", q(payment_amount=INF), "'payment_amount'"),
        ("to'lov 1e20", q(payment_amount=1e20), "'payment_amount'"),
        ("to'lov NaN", q(payment_amount=NAN), "'payment_amount'"),
        ("to'lov true", q(payment_amount=True), "'payment_amount'"),
        ("to'lov \"7\"", q(payment_amount="7"), "'payment_amount'"),
        ("to'lov 0.001", q(payment_amount=0.001), "'payment_amount'"),
        ("to'lov 0.004", q(payment_amount=0.004), "'payment_amount'"),
        ("to'lov -5", q(payment_amount=-5), "'payment_amount'"),
        ("to'lov 3 000 001 (3 baravardan ko'p)", q(payment_amount=3_000_001), "juda katta"),
        ("transport Infinity", q(transport_cost=INF), "'transport_cost'"),
        ("transport 1e20", q(transport_cost=1e20), "'transport_cost'"),
        ("transport 0.001", q(transport_cost=0.001), "'transport_cost'"),
        ("transport -1", q(transport_cost=-1), "'transport_cost'"),
        ("transport \"5\"", q(transport_cost="5"), "'transport_cost'"),
        ("to'lovchi \"xyz\"", q(transport_payer="xyz"), "'transport_payer'"),
        ("to'lovchi 21 belgi", q(transport_payer="p" * 21), "'transport_payer'"),
        ("usul \"xyz\"", q(payment_method="xyz"), "'payment_method'"),
        ("qabul qiluvchi 101 belgi", q(received_by="r" * 101), "'received_by'"),
        ("tashuvchi 151 belgi", q(transport_carrier="c" * 151), "'transport_carrier'"),
        ("izoh 10 001 belgi", q(notes="z" * 10_001), "'notes'"),
        ("items bo'sh ro'yxat", q(items=[]), "'items'"),
        ("items yo'q", q(items=KALIT_YOQ), "'items'"),
        ("items matn", q(items="abc"), "'items'"),
        ("qator miqdor 0", qator(quantity=0), "'quantity'"),
        ("qator miqdor -1", qator(quantity=-1), "'quantity'"),
        ("qator miqdor Infinity", qator(quantity=INF), "'quantity'"),
        ("qator miqdor \"2\"", qator(quantity="2"), "'quantity'"),
        ("qator miqdor true", qator(quantity=True), "'quantity'"),
        ("qator order_item_id \"3\"", qator(order_item_id=str(OD_I)), "'order_item_id'"),
        ("qator order_item_id true", qator(order_item_id=True), "'order_item_id'"),
        ("qator noma'lum kalit", qator(foo=1), "Noma'lum maydon"),
        ("noma'lum kalit", q(foo=1), "Noma'lum maydon"),
        ("order_id \"5\"", q(order_id=str(OD_ID)), "'order_id'"),
        ("order_id true", q(order_id=True), "'order_id'"),
        ("order_id yo'q", q(order_id=KALIT_YOQ), "'order_id'"),
        ("confirm_overpay \"yes\"", q(confirm_overpay="yes"), "'confirm_overpay'"),
        ("confirm_overpay null", q(confirm_overpay=None), "'confirm_overpay'"),
        ("bir detal ikki qatorda (6 + 6, buyurtmada 10)",
         q(items=[{"order_item_id": OD_I, "quantity": 6}, {"order_item_id": OD_I, "quantity": 6}]),
         "allaqachon"),
        ("100 001 qator (chegara)",
         q(items=[{"order_item_id": 1_000_000 + i, "quantity": 1} for i in range(100_001)]),
         "'items'"),
    ])

    tikla()
    h0 = holat()
    r = req(C, "post", "/api/deliveries", json={**asos, "order_id": OB_ID,
                                                "items": [{"order_item_id": OB_I, "quantity": 1}]})
    check("D begona korxona buyurtmasi → 400/404, holat o'zgarmagan",
          r.status_code in (400, 404) and holat() == h0, f"{r.status_code} {matn(r)[:120]}")

    section("D. Yetkazish — to'lov chegaralari (qo'lda to'lov bilan bir xil)")
    tikla()
    oid, (iid,), _ = yangi_buyurtma()
    tana = {**asos, "order_id": oid, "items": [{"order_item_id": iid, "quantity": 2}],
            "payment_amount": 1_500_000}
    h0 = holat()
    r = req(C, "post", "/api/deliveries", json=tana)
    dt = (jsn(r) or {}).get("detail") if isinstance(jsn(r), dict) else None
    check("D qarzdan ko'p to'lov (1 500 000 > 1 000 000) → 409 overpayment_warning, "
          "HECH NARSA yozilmagan",
          r.status_code == 409 and isinstance(dt, dict) and dt.get("type") == "overpayment_warning"
          and holat() == h0, f"{r.status_code} {matn(r)[:180]}")
    # xabar `/api/payments` dagi bilan AYNAN bir xil (shu qarz va summa uchun)
    oid2, _, _ = yangi_buyurtma()
    r2 = req(C, "post", "/api/payments", json={"order_id": oid2, "amount": 1_500_000})
    d2 = (jsn(r2) or {}).get("detail") if isinstance(jsn(r2), dict) else None
    check("D 409 xabari `/api/payments` 409 xabari bilan AYNAN bir xil",
          isinstance(dt, dict) and isinstance(d2, dict) and dt.get("message")
          and dt.get("message") == d2.get("message")
          and dt.get("amount") == d2.get("amount") and dt.get("debt") == d2.get("debt"),
          f"{dt} | {d2}")
    n_d, n_p = soni(Delivery, order_id=oid), soni(Payment, order_id=oid)
    r = req(C, "post", "/api/deliveries", json={**tana, "confirm_overpay": True})
    pay = oxirgi(Payment, order_id=oid)
    b = buyurtma(oid)
    check("D tasdiq bilan (`confirm_overpay: true`) → 200, yetkazish + 1 500 000 to'lov, "
          "to'lov holati yangilandi",
          r.status_code == 200 and soni(Delivery, order_id=oid) == n_d + 1
          and soni(Payment, order_id=oid) == n_p + 1 and pay is not None
          and pul_ok(pay.amount, 1_500_000.0) and b is not None and b.payment_status == "paid",
          f"{r.status_code} {matn(r)[:160]} {b}")
    # to'lov qarzga teng — 409 yo'q
    tikla()
    oid, (iid,), _ = yangi_buyurtma()
    r = req(C, "post", "/api/deliveries", json={**asos, "order_id": oid,
                                                "items": [{"order_item_id": iid, "quantity": 1}],
                                                "payment_amount": 1_000_000})
    check("D to'lov qarzga teng (1 000 000) → 200 (tasdiq so'ralmaydi)", r.status_code == 200,
          f"{r.status_code} {matn(r)[:160]}")

    section("D. Yetkazish — tiyin, 0, UI (`orders.html`) tanalari")
    tikla()
    oid, (iid,), _ = yangi_buyurtma()
    n_p = soni(Payment, order_id=oid)
    r = req(C, "post", "/api/deliveries", json={**asos, "order_id": oid,
                                                "items": [{"order_item_id": iid, "quantity": 1}],
                                                "payment_amount": 0.005, "transport_cost": 0.005,
                                                "transport_payer": "company"})
    pay, dl = oxirgi(Payment, order_id=oid), oxirgi(Delivery, order_id=oid)
    check("D to'lov 0.005 va transport 0.005 → 200, ikkalasi 0.01 (0.00 EMAS)",
          r.status_code == 200 and soni(Payment, order_id=oid) == n_p + 1 and pay is not None
          and pul_ok(pay.amount, 0.01) and dl is not None and pul_ok(dl.transport_cost, 0.01),
          f"{r.status_code} {matn(r)[:160]} {pay and pay.amount} {dl and dl.transport_cost}")
    n_p = soni(Payment, order_id=oid)
    r = req(C, "post", "/api/deliveries", json={**asos, "order_id": oid,
                                                "items": [{"order_item_id": iid, "quantity": 1}],
                                                "payment_amount": 0})
    check("D to'lov 0 → 200, to'lov yozuvi YO'Q", r.status_code == 200
          and soni(Payment, order_id=oid) == n_p, f"{r.status_code} {matn(r)[:160]}")

    # saveDelivery — minimal tana (bo'sh maydonlar: null / parseNum('') = 0)
    tikla()
    oid, (iid,), _ = yangi_buyurtma()
    ui_min = {"order_id": oid, "items": [{"order_item_id": iid, "quantity": 2.5}],
              "received_by": None, "notes": None, "payment_amount": None, "payment_method": "naqd",
              "transport_carrier": None, "transport_cost": 0, "transport_payer": "none"}
    r = xom(C, "post", "/api/deliveries", json.dumps(ui_min))
    b = buyurtma(oid)
    check("D saveDelivery (minimal) → 200, 2.5 metr topshirildi, to'lov yo'q",
          r.status_code == 200 and b is not None and yaqin(b.delivered[0], 2.5)
          and soni(Payment, order_id=oid) == 0, f"{r.status_code} {matn(r)[:160]} {b}")
    # saveDelivery — to'liq tana
    ui_toliq = {"order_id": oid, "items": [{"order_item_id": iid, "quantity": 3}],
                "received_by": "Vali", "notes": "QY izoh", "payment_amount": 100_000,
                "payment_method": "plastik", "transport_carrier": "Ali", "transport_cost": 50_000,
                "transport_payer": "split"}
    r = xom(C, "post", "/api/deliveries", json.dumps(ui_toliq))
    dl, pay = oxirgi(Delivery, order_id=oid), oxirgi(Payment, order_id=oid)
    check("D saveDelivery (to'liq: to'lov plastik, transport split) → 200, aniq qiymatlar",
          r.status_code == 200 and dl is not None and dl.received_by == "Vali"
          and dl.transport_carrier == "Ali" and dl.transport_payer == "split"
          and pul_ok(dl.transport_cost, 50_000.0) and pay is not None
          and pul_ok(pay.amount, 100_000.0)
          and getattr(pay.payment_method, "value", str(pay.payment_method)) in ("plastik", "card", "CARD")
          and pay.delivery_id == dl.id,
          f"{r.status_code} {matn(r)[:160]} {pay and pay.payment_method}")
    # submitFullDlvModal — `delivery-status` dan AYNAN UI kabi
    st = jsn(req(C, "get", f"/api/orders/{oid}/delivery-status")) or {}
    pending = [i for i in (st.get("items") or []) if not i.get("is_done") and i.get("remaining", 0) > 0]
    ui_full = {"order_id": oid, "items": [{"order_item_id": i.get("id"), "quantity": i.get("remaining")}
                                          for i in pending],
               "received_by": None, "notes": None, "transport_carrier": None, "transport_cost": 0,
               "transport_payer": "none", "payment_amount": None, "payment_method": "naqd"}
    r = xom(C, "post", "/api/deliveries", json.dumps(ui_full))
    b = buyurtma(oid)
    check("D submitFullDlvModal (qolgan 4.5) → 200, detal to'liq topshirildi",
          len(pending) == 1 and r.status_code == 200 and b is not None and yaqin(b.delivered[0], 10),
          f"{len(pending)} {r.status_code} {matn(r)[:160]} {b}")

    section("D. \"Tayyor\" belgisidagi avtomatik yetkazish (services.complete_order)")
    tikla()
    oid, (iid,), _ = yangi_buyurtma()
    n_d = soni(Delivery, order_id=oid)
    r = req(C, "post", f"/api/orders/{oid}/ready")
    b = buyurtma(oid)
    check("D Tayyor → 200, avtomatik yetkazish yozildi (10 metr to'liq)",
          r.status_code == 200 and soni(Delivery, order_id=oid) == n_d + 1 and b is not None
          and yaqin(b.delivered[0], 10) and "auto_delivery" in matn(r),
          f"{r.status_code} {matn(r)[:200]} {b}")
    tikla()
    oid, iids, _ = yangi_buyurtma(miqdor=1, narx=1000, soni_=501)
    r = req(C, "post", f"/api/orders/{oid}/ready")
    b = buyurtma(oid)
    check("D Tayyor, 501 detalli buyurtma → 200, avtomatik yetkazish yozildi (500 EMAS)",
          r.status_code == 200 and soni(Delivery, order_id=oid) == 1 and b is not None
          and all(yaqin(x, 1) for x in b.delivered), f"{r.status_code} {matn(r)[:200]}")
    tikla()
    oid, iids, _ = yangi_buyurtma(miqdor=1, narx=1000, soni_=501)
    r = req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": i, "quantity": 1} for i in iids],
        "received_by": None, "notes": None, "transport_carrier": None, "transport_cost": 0,
        "transport_payer": "none", "payment_amount": None, "payment_method": "naqd"})
    check("D bir yo'la to'liq topshirish, 501 detal → 200",
          r.status_code == 200 and soni(Delivery, order_id=oid) == 1,
          f"{r.status_code} {matn(r)[:200]}")


# ══════════════════════════════════════════════════════════════
# N. 3 xonali narx — narx va jami bazadagidek (HALF_UP)
# ══════════════════════════════════════════════════════════════
NARX_HOLATLAR = [(3, 1234.567, 1234.57, 3703.71), (333, 10.335, 10.34, 3443.22),
                 (7, 0.125, 0.13, 0.91)]


def b_asl():
    """Tahrir qilinadigan xarid ASL holatda (5 × 1000)."""
    tikla()
    if PG_REJIM:
        xom(C, "put", f"/api/inventory/purchases/{P_ID}",
            json.dumps({"quantity": 5, "price_per_unit": 1000}))


def n_bolimi():
    section("N. 3 xonali narx — xarid / kirim / tahrir / boshlang'ich qoldiq")
    for miq, narx, k_narx, k_jami in NARX_HOLATLAR:
        tikla()
        r = req(C, "post", f"/api/inventory/{M_ID}/purchase",
                json={"quantity": miq, "price_per_unit": narx})
        p = oxirgi(InventoryPurchase, inventory_id=M_ID)
        check(f"N xarid {miq} × {narx} → 200, narx {k_narx}, jami {k_jami}",
              r.status_code == 200 and p is not None and pul_ok(p.price_per_unit, k_narx)
              and pul_ok(p.total_amount, k_jami),
              f"{r.status_code} {matn(r)[:120]} {p and (p.price_per_unit, p.total_amount)}")
        tikla()
        r = req(C, "post", "/api/inventory/receipt",
                json={"supplier_id": S_ID, "items": [{"inventory_id": M_ID, "quantity": miq,
                                                      "price_per_unit": narx}]})
        p = oxirgi(InventoryPurchase, inventory_id=M_ID)
        check(f"N kirim hujjati {miq} × {narx} → 200, narx {k_narx}, jami {k_jami}",
              r.status_code == 200 and p is not None and p.receipt_id is not None
              and pul_ok(p.price_per_unit, k_narx) and pul_ok(p.total_amount, k_jami),
              f"{r.status_code} {matn(r)[:120]} {p and (p.price_per_unit, p.total_amount)}")
        b_asl()
        r = xom(C, "put", f"/api/inventory/purchases/{P_ID}",
                json.dumps({"quantity": miq, "price_per_unit": narx}))
        p = oxirgi(InventoryPurchase, id=P_ID)
        check(f"N tahrir {miq} × {narx} → 200, narx {k_narx}, jami {k_jami}",
              r.status_code == 200 and p is not None and pul_ok(p.price_per_unit, k_narx)
              and pul_ok(p.total_amount, k_jami),
              f"{r.status_code} {matn(r)[:120]} {p and (p.price_per_unit, p.total_amount)}")
        tikla()
        nom = f"QY_BOSH_{miq}_{str(narx).replace('.', '_')}"
        r = req(C, "post", "/api/inventory", json={"item_name": nom, "stock_quantity": miq,
                                                   "unit": "kg", "price_per_unit": narx})
        inv_id = (jsn(r) or {}).get("id") if isinstance(jsn(r), dict) else None
        p = oxirgi(InventoryPurchase, inventory_id=inv_id) if inv_id else None
        check(f"N boshlang'ich qoldiq {miq} × {narx} → narx {k_narx}, jami {k_jami}",
              r.status_code == 200 and p is not None and pul_ok(p.price_per_unit, k_narx)
              and pul_ok(p.total_amount, k_jami),
              f"{r.status_code} {matn(r)[:120]} {p and (p.price_per_unit, p.total_amount)}")
    b_asl()

    # Xarid marshruti: "to'liq to'langan" qarori bazadagi jamiga tayanadi
    tikla()
    s0 = soni(SupplierPayment, supplier_id=SN_ID)
    r = req(C, "post", f"/api/inventory/{M_ID}/purchase",
            json={"quantity": 3, "price_per_unit": 1234.567, "supplier_id": SN_ID,
                  "paid_now": 3703.71})
    p = oxirgi(InventoryPurchase, inventory_id=M_ID)
    check("N xarid 3 × 1234.567, hoziroq 3703.71 (= jami) → to'liq to'langan (nasiya EMAS, "
          "ta'minotchi to'lovi yo'q)",
          r.status_code == 200 and p is not None and not p.is_credit
          and pul_ok(p.total_amount, 3703.71) and soni(SupplierPayment, supplier_id=SN_ID) == s0,
          f"{r.status_code} {matn(r)[:120]} {p and (p.is_credit, p.total_amount)}")

    section("N. Sig'im — yaxlitlangan narx bilan jami sig'imdan oshsa 400")
    katta = {"quantity": 2, "price_per_unit": 4_999_999_999.995}
    for nom, yo, url, tana in [
            ("xarid", "post", f"/api/inventory/{M_ID}/purchase", katta),
            ("kirim hujjati", "post", "/api/inventory/receipt",
             {"supplier_id": S_ID, "items": [{"inventory_id": M_ID, **katta}]}),
            ("tahrir", "put", f"/api/inventory/purchases/{P_ID}", katta)]:
        b_asl()
        h0 = holat()
        r = xom(C, yo, url, json.dumps(tana))
        check(f"N {nom} 2 × 4 999 999 999.995 → 400 (jami sig'imdan oshdi), holat o'zgarmagan",
              r.status_code == 400 and "juda katta" in matn(r) and holat() == h0,
              f"{r.status_code} {matn(r)[:160]}")
    b_asl()


# ══════════════════════════════════════════════════════════════
# S. Ta'minotchi to'lovi xarid bilan birga
# ══════════════════════════════════════════════════════════════
def s_bolimi():
    section("S. Ta'minotchi to'lovi xarid bilan birga")
    # 1) 8 s ichida shu summada qo'lda to'lov — xarid to'lovi baribir yaratiladi
    tikla()
    r0 = req(C, "post", f"/api/inventory/{M_ID}/purchase",
             json={"quantity": 10, "price_per_unit": 10_000, "supplier_id": ST_ID, "paid_now": 0})
    s0 = soni(SupplierPayment, supplier_id=ST_ID)
    r1 = req(C, "post", f"/api/suppliers/{ST_ID}/payment", json={"amount": 30_000})
    r2 = req(C, "post", f"/api/inventory/{M_ID}/purchase",
             json={"quantity": 10, "price_per_unit": 5_000, "supplier_id": ST_ID,
                   "paid_now": 30_000})
    sp = oxirgi(SupplierPayment, supplier_id=ST_ID)
    check("S qo'lda to'lov 30 000 + 8 s ichida xarid (hoziroq 30 000) → xarid to'lovi YARATILDI",
          r0.status_code == 200 and r1.status_code == 200 and r2.status_code == 200
          and soni(SupplierPayment, supplier_id=ST_ID) == s0 + 2 and sp is not None
          and pul_ok(sp.amount, 30_000.0),
          f"{r0.status_code} {r1.status_code} {r2.status_code} {matn(r2)[:120]} "
          f"{s0}->{soni(SupplierPayment, supplier_id=ST_ID)}")
    # 2) Avansli ta'minotchi (qarz 0) — qisman to'langan xarid 500 EMAS
    tikla()
    r1 = req(C, "post", f"/api/suppliers/{SAV_ID}/payment",
             json={"amount": 1_000_000, "confirm_overpay": True})
    s0 = soni(SupplierPayment, supplier_id=SAV_ID)
    n0 = soni(InventoryPurchase, supplier_id=SAV_ID)
    r2 = req(C, "post", f"/api/inventory/{M_ID}/purchase",
             json={"quantity": 10, "price_per_unit": 20_000, "supplier_id": SAV_ID,
                   "paid_now": 50_000})
    sp = oxirgi(SupplierPayment, supplier_id=SAV_ID)
    check("S avansli ta'minotchi, xarid 200 000, hoziroq 50 000 → 200, xarid va to'lov yozildi",
          r1.status_code == 200 and r2.status_code == 200
          and soni(InventoryPurchase, supplier_id=SAV_ID) == n0 + 1
          and soni(SupplierPayment, supplier_id=SAV_ID) == s0 + 1 and sp is not None
          and pul_ok(sp.amount, 50_000.0), f"{r1.status_code} {r2.status_code} {matn(r2)[:160]}")
    # 3) Kasr so'mli xarid qisman to'lov (qarz butun so'mga yaxlitlanadi: 1000.4 → 1000)
    tikla()
    s0 = soni(SupplierPayment, supplier_id=SK_ID)
    r2 = req(C, "post", f"/api/inventory/{M_ID}/purchase",
             json={"quantity": 1, "price_per_unit": 1000.4, "supplier_id": SK_ID,
                   "paid_now": 1000.3})
    sp = oxirgi(SupplierPayment, supplier_id=SK_ID)
    p = oxirgi(InventoryPurchase, supplier_id=SK_ID)
    check("S kasr so'mli xarid 1000.40, hoziroq 1000.30 → 200, nasiya, to'lov 1000.30",
          r2.status_code == 200 and soni(SupplierPayment, supplier_id=SK_ID) == s0 + 1
          and sp is not None and pul_ok(sp.amount, 1000.3) and p is not None and p.is_credit,
          f"{r2.status_code} {matn(r2)[:160]}")
    # Qo'lda to'lov yo'lining himoyalari O'Z KUCHIDA (ichki=True faqat xarid marshrutida)
    tikla()
    r1 = req(C, "post", f"/api/suppliers/{SK_ID}/payment", json={"amount": 777})
    check("S qo'lda to'lov, qarz 0 → 409 (ortiqcha to'lov tasdig'i hali ishlaydi)",
          r1.status_code == 409, f"{r1.status_code} {matn(r1)[:120]}")


# ══════════════════════════════════════════════════════════════
# F. Ildiz (crud) — bazaga tegmasdan rad
# ══════════════════════════════════════════════════════════════
def urin(fn):
    """(natija, istisno_nomi) — asl kodga qarshi qulamaslik uchun."""
    try:
        return fn(), None
    except Exception as e:
        return None, type(e).__name__


def f_bolimi():
    section("F. Ildiz (crud) — ValueError, hech narsa yozilmaydi")

    def yet(**kw):
        a = dict(order_id=OD_ID, items=[SimpleNamespace(order_item_id=OD_I, quantity=2)],
                 received_by=None, notes=None, transport_carrier=None, transport_cost=0,
                 transport_payer="none", payment_amount=None, payment_method="naqd",
                 confirm_overpay=False)
        a.update(kw)
        return SimpleNamespace(**a)

    for nom, obj in [
            ("qator miqdor Infinity", yet(items=[SimpleNamespace(order_item_id=OD_I, quantity=INF)])),
            ("to'lov 0.001", yet(payment_amount=0.001)),
            ("to'lov Infinity", yet(payment_amount=INF)),
            ("to'lovchi \"xyz\"", yet(transport_payer="xyz")),
            ("usul \"xyz\"", yet(payment_method="xyz")),
            ("qabul qiluvchi 101", yet(received_by="r" * 101)),
            ("bir detal ikki qatorda", yet(items=[SimpleNamespace(order_item_id=OD_I, quantity=6),
                                                  SimpleNamespace(order_item_id=OD_I, quantity=6)]))]:
        tikla()
        h0 = holat()
        d = SessionLocal()
        try:
            _, ist = urin(lambda: crud.create_delivery(d, obj, delivered_by="F", company_id=1))
            d.rollback()
        finally:
            d.close()
        check(f"F create_delivery {nom} → ValueError, holat o'zgarmagan",
              ist == "ValueError" and holat() == h0, ist)

    tikla()
    h0 = holat()
    d = SessionLocal()
    try:
        _, ist = urin(lambda: crud.create_delivery(d, yet(payment_amount=1_500_000),
                                                   delivered_by="F", company_id=1))
        d.rollback()
    finally:
        d.close()
    check("F create_delivery qarzdan ko'p to'lov → OverpaymentWarning, holat o'zgarmagan",
          ist == "OverpaymentWarning" and holat() == h0, ist)

    def qay(**kw):
        a = dict(order_id=OR_ID, order_item_id=OR_I, item_name=OR_NOM, quantity=2, unit="metr",
                 reason="Ortiqcha", refund_amount=0, to_stock=True, notes=None,
                 coating_applied=False, gips_kg_used=None)
        a.update(kw)
        return SimpleNamespace(**a)

    for nom, obj, cid in [
            ("miqdor NaN", qay(quantity=NAN), 1),
            ("miqdor Infinity", qay(quantity=INF), 1),
            ("summa NaN", qay(refund_amount=NAN), 1),
            ("sabab \"xyz\"", qay(reason="xyz"), 1),
            ("nom 151", qay(item_name="n" * 151), 1),
            ("miqdor buyurtmadan ko'p", qay(quantity=10.01), 1),
            ("summa 9e9", qay(refund_amount=9e9), 1),
            ("begona korxona buyurtmasi", qay(order_id=OB_ID, order_item_id=OB_I,
                                              item_name=OB_NOM), 1),
            ("buyurtmada yo'q detal nomi", qay(order_item_id=None, item_name="QY_YOQ"), 1)]:
        tikla()
        h0 = holat()
        d = SessionLocal()
        try:
            _, ist = urin(lambda: crud.create_return_item(d, obj, company_id=cid))
            d.rollback()
        finally:
            d.close()
        check(f"F create_return_item {nom} → ValueError, holat o'zgarmagan",
              ist == "ValueError" and holat() == h0, ist)

    tikla()
    fn = getattr(crud, "_tolov_chegarasi", None)
    ow = getattr(crud, "OverpaymentWarning", None)
    d = SessionLocal()
    try:
        o = d.get(Order, OD_ID)
        natijalar = {}
        for nom, summa, tasdiq in [("3 000 001", 3_000_001, False), ("3 000 001 tasdiq", 3_000_001, True),
                                   ("1 000 001", 1_000_001, False), ("1 000 001 tasdiq", 1_000_001, True),
                                   ("500", 500, False)]:
            if fn is None:
                natijalar[nom] = "YOQ"
            else:
                _, ist = urin(lambda: fn(o, summa, tasdiq))
                natijalar[nom] = ist
    finally:
        d.close()
    check("F _tolov_chegarasi: 3 baravar → ValueError (tasdiq bilan ham), qarzdan ko'p → "
          "OverpaymentWarning, tasdiq bilan / qarz ichida — None",
          fn is not None and ow is not None and natijalar == {
              "3 000 001": "ValueError", "3 000 001 tasdiq": "ValueError",
              "1 000 001": "OverpaymentWarning", "1 000 001 tasdiq": None, "500": None},
          natijalar)

    xnj = getattr(crud, "_xarid_narx_jami", None)
    p2 = getattr(crud, "_pul2", None)
    kut = {(3, 1234.567): (1234.57, 3703.71), (333, 10.335): (10.34, 3443.22),
           (7, 0.125): (0.13, 0.91), (2, 4_999_999_999.995): (5_000_000_000.0, 10_000_000_000.0),
           (1.5, 0.005): (0.01, 0.02)}
    olingan = {k: (urin(lambda: xnj(*k))[0] if xnj else None) for k in kut}
    check("F _xarid_narx_jami — narx HALF_UP, jami shu narxdan", xnj is not None and olingan == kut,
          olingan)
    pk = {10.335: 10.34, 1000.005: 1000.01, 0.125: 0.13, 2.675: 2.68, 0.004: 0.0, 1.0: 1.0}
    olingan = {k: (urin(lambda: p2(k))[0] if p2 else None) for k in pk}
    check("F _pul2 — PostgreSQL bilan bir xil (2.675 → 2.68, Python round 2.67 bergan bo'lardi)",
          p2 is not None and olingan == pk, olingan)
    try:
        imzo = inspect.signature(crud.create_supplier_payment).parameters
    except Exception:
        imzo = {}
    check("F create_supplier_payment(ichki=False) — parametr bor, standart False",
          "ichki" in imzo and imzo["ichki"].default is False, list(imzo))

    # Sxema — ikkinchi to'siq
    xatolar = {}
    for nom, fn2 in [
            ("DeliveryItemCreate miqdor inf",
             lambda: schemas.DeliveryItemCreate(order_item_id=1, quantity=INF)),
            ("DeliveryItemCreate miqdor true",
             lambda: schemas.DeliveryItemCreate(order_item_id=1, quantity=True)),
            ("DeliveryCreate usul xyz",
             lambda: schemas.DeliveryCreate(order_id=1, payment_method="xyz")),
            ("DeliveryCreate to'lovchi xyz",
             lambda: schemas.DeliveryCreate(order_id=1, transport_payer="xyz")),
            ("DeliveryCreate to'lov 1e20", lambda: schemas.DeliveryCreate(order_id=1, payment_amount=1e20)),
            ("ReturnItemCreate miqdor nan",
             lambda: schemas.ReturnItemCreate(order_id=1, item_name="x", quantity=NAN, reason="Brak")),
            ("ReturnItemCreate sabab xyz",
             lambda: schemas.ReturnItemCreate(order_id=1, item_name="x", quantity=1, reason="xyz")),
            ("ReturnItemCreate birlik 21",
             lambda: schemas.ReturnItemCreate(order_id=1, item_name="x", quantity=1, reason="Brak",
                                              unit="u" * 21))]:
        _, ist = urin(fn2)
        xatolar[nom] = ist
    check("F sxemalar (ikkinchi to'siq) — har yomon qiymat ValidationError",
          all(v == "ValidationError" for v in xatolar.values()), xatolar)
    _, ist = urin(lambda: schemas.DeliveryCreate(
        order_id=1, items=[schemas.DeliveryItemCreate(order_item_id=i + 1, quantity=1)
                           for i in range(501)]))
    check("F DeliveryCreate 501 qator — sxema qabul qiladi (servis avtomatik yetkazishi uchun)",
          ist is None, ist)
    _, ist = urin(lambda: schemas.DeliveryItemCreate(order_item_id=1, quantity=3))
    check("F DeliveryItemCreate miqdor butun son (servis `remaining` int bo'lsa) — qabul",
          ist is None, ist)


# ══════════════════════════════════════════════════════════════
# G. Statik
# ══════════════════════════════════════════════════════════════
def g_bolimi():
    section("G. Statik — tekshiruv tartibi, marshrutlar, qoidalar, UI")
    cd = manba(crud.create_delivery)
    check("G create_delivery: `_clean_val(\"Delivery\"` Delivery yozilishidan OLDIN",
          tartibda(cd, '_clean_val("Delivery"', "db_delivery = Delivery("), "")
    check("G create_delivery: `_tolov_chegarasi` Delivery yozilishidan OLDIN",
          tartibda(cd, "_tolov_chegarasi(", "db_delivery = Delivery("), "")
    check("G create_delivery: to'lov yozuvi atomar (payment_warning / try-except yo'q)",
          "payment_warning =" not in cd and "create_delivery:payment_write" not in cd, "")
    cr = manba(crud.create_return_item)
    check("G create_return_item: `_clean_val(\"Return\"` ReturnItem yozilishidan OLDIN",
          tartibda(cr, '_clean_val("Return"', "item = ReturnItem("), "")
    check("G create_return_item: noma'lum sabab jimgina Brak EMAS",
          "reason_enum = ReturnReason.DEFECT" not in cr, "")
    check("G create_return_item: detal topilmasa rad (nom bo'yicha qidiruvdan KEYIN)",
          tartibda(cr, "OrderItem.name == data.item_name", "if order_item is None:",
                   "Buyurtma detali topilmadi", "item = ReturnItem("), "")
    check("G create_payment `_tolov_chegarasi` ni chaqiradi",
          "_tolov_chegarasi(" in manba(crud.create_payment), "")
    mr = manba(main.api_create_return)
    check("G POST /api/returns: xom `dict = Body(...)`, `_clean_val` crud dan OLDIN",
          "data: dict = Body(...)" in mr and tartibda(mr, '_clean_val("Return"',
                                                      "crud.create_return_item("), "")
    md = manba(main.api_create_delivery)
    check("G POST /api/deliveries: xom `dict = Body(...)`, `_clean_val` crud dan OLDIN, 409, rollback",
          "data: dict = Body(...)" in md and tartibda(md, '_clean_val("Delivery"',
                                                      "crud.create_delivery(")
          and "status_code=409" in md and "overpayment_warning" in md
          and md.count("db.rollback()") >= 2, "")
    mp = manba(main.api_purchase_stock)
    check("G xarid marshruti: jami `_xarid_narx_jami`, ta'minotchi to'lovi `ichki=True`",
          "crud._xarid_narx_jami(" in mp and "ichki=True" in mp
          and "total_amount = round(data.quantity * data.price_per_unit)" not in mp, "")
    ps = manba(getattr(crud, "_purchase_stock_no_commit", None))
    check("G _purchase_stock_no_commit: `_xarid_narx_jami`, xom ko'paytma yozilmaydi",
          "_xarid_narx_jami(" in ps and "total_amount=quantity * price_per_unit" not in ps, "")
    up = manba(crud.update_purchase)
    check("G update_purchase: `_xarid_narx_jami`, xom ko'paytma yozilmaydi",
          "_xarid_narx_jami(" in up
          and "p.total_amount = float(p.quantity) * float(p.price_per_unit)" not in up, "")
    check("G add_item: boshlang'ich qoldiqning IKKALA yo'li `_xarid_narx_jami`",
          manba(crud.add_item).count("_xarid_narx_jami(") >= 4, "")
    nt = getattr(crud, "_NOL_YOKI_TIYIN", {})
    check("G _NOL_YOKI_TIYIN: Delivery (to'lov, transport), Return (summa)",
          set(nt.get("Delivery", ())) == {"payment_amount", "transport_cost"}
          and set(nt.get("Return", ())) == {"refund_amount"}, nt)
    try:
        qr = crud._val_rules()
    except Exception:
        qr = {}
    check("G qaytarish sababi = models.ReturnReason qiymatlari",
          set(getattr(crud, "_QAYTARISH_SABABI", {})) == {x.value for x in ReturnReason}
          and qr.get("Return", {}).get("reason", (None, None, {}))[2] == getattr(
              crud, "_QAYTARISH_SABABI", None), "")
    orders = fayl("templates/orders.html")

    def select_qiymatlari(sid):
        i = orders.find(f'id="{sid}"')
        j = orders.find("</select>", i)
        import re
        return set(re.findall(r'value="([^"]*)"', orders[i:j])) if i >= 0 and j > i else set()

    check("G to'lovchi ro'yxati = orders.html `dlv-transport-payer` qiymatlari",
          set(getattr(crud, "_YETKAZISH_TOLOVCHI", {})) == select_qiymatlari("dlv-transport-payer")
          and len(select_qiymatlari("dlv-transport-payer")) == 4, select_qiymatlari("dlv-transport-payer"))
    check("G usul ro'yxati = orders.html `dlv-payment-method` qiymatlari",
          set(getattr(crud, "_TOLOV_USULI_MIJOZ", {})) == select_qiymatlari("dlv-payment-method")
          and len(select_qiymatlari("dlv-payment-method")) == 3, select_qiymatlari("dlv-payment-method"))
    di = qr.get("Delivery", {}).get("items", ())
    check("G yetkazish qatorlari chegarasi ≥ 100 000 (500 dan ko'p detalli buyurtma uchun)",
          len(di) >= 4 and di[3] >= 100_000, di)
    yy = js_funksiya(orders, "yetkazishYubor")
    check("G orders.html yetkazishYubor: 409 overpayment_warning → showConfirmModal, "
          "confirm_overpay = true bilan qayta, Bekor → null",
          "res.status === 409" in yy and "overpayment_warning" in yy and "showConfirmModal(" in yy
          and "data.confirm_overpay = true" in yy and "return null" in yy, "")
    sd, sf = js_funksiya(orders, "saveDelivery"), js_funksiya(orders, "submitFullDlvModal")
    check("G saveDelivery va submitFullDlvModal yetkazishYubor orqali, `null` holati bor",
          "yetkazishYubor(data)" in sd and "if (!res) return;" in sd
          and "yetkazishYubor(data)" in sf and "if (!res)" in sf
          and "fetch('/api/deliveries'" not in sd and "fetch('/api/deliveries'" not in sf, "")
    check("G orders.html: `/api/deliveries` ga to'g'ridan fetch faqat yetkazishYubor ichida (1 ta)",
          orders.count("fetch('/api/deliveries'") == 1 and "fetch('/api/deliveries'" in yy, "")
    ret = fayl("templates/returns.html")
    sb = js_funksiya(ret, "saveBrakBatch")
    check("G returns.html saveBrakBatch: rad etilgan qator server SABABI bilan, jim tashlanmaydi",
          "brakServerSababi(res)" in sb and "if (res.ok) okCount++;" not in sb
          and "xatolar.length" in sb, "")
    check("G returns.html closeBrakModal: qisman saqlangan bo'lsa sahifa yangilanadi",
          "brakSaqlanganBor" in js_funksiya(ret, "closeBrakModal")
          and "location.reload()" in js_funksiya(ret, "closeBrakModal"), "")
    sr = js_funksiya(ret, "saveReturn")
    check("G returns.html saveReturn: server sababi (`e.detail?.message || e.detail`)",
          "e.detail?.message || e.detail" in sr, "")


# ══════════════════════════════════════════════════════════════
# H. 422 qoladi
# ══════════════════════════════════════════════════════════════
def h_bolimi():
    section("H. Tana lug'at emas / buzilgan JSON → 422 (500 emas)")
    for url in ("/api/returns", "/api/deliveries"):
        tikla()
        h0 = holat()
        r1 = xom(C, "post", url, json.dumps([1, 2]))
        r2 = xom(C, "post", url, "{buzilgan")
        check(f"H {url}: ro'yxat → {r1.status_code}, buzilgan → {r2.status_code} (422), holat o'zgarmagan",
              r1.status_code == 422 and r2.status_code == 422 and holat() == h0,
              f"{matn(r1)[:80]} | {matn(r2)[:80]}")


# ══════════════════════════════════════════════════════════════
# K. Kumulyativ
# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
# T. Takror / parallel yetkazish (kech27)
# ══════════════════════════════════════════════════════════════
_T_N = [0]


def _t_tana(oid, iid, miqdor=2, **ozg):
    """`orders.html` `saveDelivery` shaklidagi to'liq tana (hamma maydon)."""
    _T_N[0] += 1
    tana = {
        "order_id": oid,
        "items": [{"order_item_id": iid, "quantity": miqdor}],
        "received_by": "T Qabul",
        "notes": "T izoh",
        "payment_amount": 50000,
        "payment_method": "naqd",
        "transport_carrier": "T Tashuvchi",
        "transport_cost": 15000,
        "transport_payer": "company",
    }
    tana.update(ozg)
    return tana


def _t_yetkazishlar(oid):
    d = SessionLocal()
    try:
        dl = d.query(Delivery).filter(Delivery.order_id == oid).order_by(Delivery.id).all()
        py = d.query(Payment).filter(Payment.order_id == oid).count()
        jami = sum(float(x.quantity) for x in d.query(DeliveryItem).join(
            Delivery, Delivery.id == DeliveryItem.delivery_id).filter(
            Delivery.order_id == oid).all())
        return SimpleNamespace(soni=len(dl), tolov=py, jami=round(jami, 6),
                               idlar=[x.id for x in dl],
                               raqamlar=[x.delivery_number for x in dl])
    finally:
        d.close()


def _t_eskirt(delivery_id, soniya):
    d = SessionLocal()
    try:
        d.query(Delivery).filter(Delivery.id == delivery_id).update(
            {"delivered_at": datetime.utcnow() - timedelta(seconds=soniya)},
            synchronize_session=False)
        d.commit()
    finally:
        d.close()


def _t_ildiz(sessiya, oid, iid, miqdor, tolov=None):
    """`crud.create_delivery` to'g'ridan (asl kodga qarshi ham qulamaydi)."""
    try:
        data = schemas.DeliveryCreate(
            order_id=oid, items=[schemas.DeliveryItemCreate(order_item_id=iid, quantity=miqdor)],
            payment_amount=tolov)
        r = crud.create_delivery(sessiya, data, delivered_by="T", company_id=1)
        return r if isinstance(r, dict) else {"success": False, "message": repr(r)}
    except Exception as e:
        try:
            sessiya.rollback()
        except Exception:
            pass
        return {"success": False, "message": f"ISTISNO {type(e).__name__}: {e}"}


def t_bolimi():
    section("T. Takror / parallel yetkazish (kech27)")
    sanoq = {"tg": 0, "pdf": 0}
    asl_tg = getattr(main, "_send_telegram", None)
    asl_pdf = getattr(main, "_send_delivery_pdf_to_customer", None)

    def _tg(*a, **k):
        sanoq["tg"] += 1

    def _pdf(*a, **k):
        sanoq["pdf"] += 1

    main._send_telegram = _tg
    main._send_delivery_pdf_to_customer = _pdf
    try:
        _t_ketma_ket(sanoq)
        _t_toliq_takror()
        _t_begona()
        _t_eskirgan_sessiya()
        _t_parallel()
    finally:
        if asl_tg is not None:
            main._send_telegram = asl_tg
        if asl_pdf is not None:
            main._send_delivery_pdf_to_customer = asl_pdf
    if not PG_REJIM:
        _t_statik()


def _t_ketma_ket(sanoq):
    # T1 — ketma-ket bir xil so'rov
    tikla()
    oid, (iid,), _ = yangi_buyurtma(miqdor=30)
    tana = _t_tana(oid, iid)
    r1 = req(C, "post", "/api/deliveries", json=tana)
    j1 = jsn(r1) or {}
    y1 = _t_yetkazishlar(oid)
    tg1, pdf1 = sanoq["tg"], sanoq["pdf"]
    check("T1 birinchi so'rov → 200, yangi yetkazish (duplicate yo'q), Telegram + nakladnoy 1 martadan",
          r1.status_code == 200 and j1.get("success") is True and not j1.get("duplicate")
          and y1.soni == 1 and y1.tolov == 1 and y1.jami == 2 and tg1 == 1 and pdf1 == 1,
          f"{r1.status_code} {matn(r1)[:160]} {vars(y1)} tg={tg1} pdf={pdf1}")
    h0 = holat()
    r2 = req(C, "post", "/api/deliveries", json=tana)
    j2 = jsn(r2) or {}
    y2 = _t_yetkazishlar(oid)
    check("T1 AYNAN takror → 200, duplicate=true, o'sha delivery_id va raqam",
          r2.status_code == 200 and j2.get("success") is True and j2.get("duplicate") is True
          and j2.get("delivery_id") == j1.get("delivery_id")
          and j2.get("delivery_number") == j1.get("delivery_number"),
          f"{r2.status_code} {matn(r2)[:200]}")
    check("T1 takrordan keyin baza AYNAN o'zgarmagan (1 yetkazish, 1 to'lov, 2 metr)",
          holat() == h0 and y2.soni == 1 and y2.tolov == 1 and y2.jami == 2, vars(y2))
    check("T1 takrorda Telegram va nakladnoy QAYTA yuborilmagan",
          sanoq["tg"] == tg1 and sanoq["pdf"] == pdf1, dict(sanoq))
    check("T1 takror javobi xabari aniq ('takroriy so'rov, qayta yozilmadi')",
          "takroriy so'rov, qayta yozilmadi" in str(j2.get("message", "")), j2.get("message"))

    # T2 — har bir maydon farqi → YANGI yetkazish (haqiqiy alohida harakat)
    farqlar = [
        ("miqdor 3", {"items": [{"order_item_id": iid, "quantity": 3}]}),
        ("to'lov 60 000", {"payment_amount": 60000}),
        ("to'lov usuli plastik", {"payment_method": "plastik"}),
        ("to'lovsiz", {"payment_amount": None}),
        ("transport 16 000", {"transport_cost": 16000}),
        ("to'lovchi mijoz", {"transport_payer": "client"}),
        ("tashuvchi boshqa", {"transport_carrier": "T Boshqa"}),
        ("qabul qiluvchi boshqa", {"received_by": "T Boshqa"}),
        ("izoh boshqa", {"notes": "T boshqa izoh"}),
    ]
    for nom, ozg in farqlar:
        oldin = _t_yetkazishlar(oid)
        t = dict(tana)
        t.update(ozg)
        r = req(C, "post", "/api/deliveries", json=t)
        j = jsn(r) or {}
        keyin = _t_yetkazishlar(oid)
        check(f"T2 farq '{nom}' → 200, YANGI yetkazish (duplicate yo'q)",
              r.status_code == 200 and j.get("success") is True and not j.get("duplicate")
              and keyin.soni == oldin.soni + 1 and j.get("delivery_id") not in oldin.idlar,
              f"{r.status_code} {matn(r)[:160]} {oldin.soni}->{keyin.soni}")

    # T3 — oyna: 6 s oldingi AYNAN shunday yetkazish → takror; 10 s → yangi
    t3 = dict(tana)
    t3["notes"] = "T3 oyna"
    r = req(C, "post", "/api/deliveries", json=t3)
    j = jsn(r) or {}
    did = j.get("delivery_id")
    _t_eskirt(did, 6) if did else None
    oldin = _t_yetkazishlar(oid)
    r = req(C, "post", "/api/deliveries", json=t3)
    j6 = jsn(r) or {}
    check("T3 6 soniya oldingi AYNAN shunday yetkazish → takror (yangi yozuv yo'q)",
          r.status_code == 200 and j6.get("duplicate") is True and j6.get("delivery_id") == did
          and _t_yetkazishlar(oid).soni == oldin.soni,
          f"{r.status_code} {matn(r)[:160]}")
    _t_eskirt(did, 10) if did else None
    oldin = _t_yetkazishlar(oid)
    r = req(C, "post", "/api/deliveries", json=t3)
    j10 = jsn(r) or {}
    check("T3 10 soniya oldingi → oyna o'tgan, YANGI yetkazish (haqiqiy takroriy topshirish)",
          r.status_code == 200 and j10.get("success") is True and not j10.get("duplicate")
          and _t_yetkazishlar(oid).soni == oldin.soni + 1,
          f"{r.status_code} {matn(r)[:160]}")
    yk = _t_yetkazishlar(oid)
    check("T1–T3 yetkazish raqamlari takrorlanmagan",
          len(yk.raqamlar) == len(set(yk.raqamlar)), yk.raqamlar)


def _t_toliq_takror():
    # T4 — to'liq yetkazish + to'liq to'lov takrori: qoldiq 0 va qarz 0 bo'lgach
    # ham takror 200 (400 "Qoldiqdan ko'p" yoki 409 "ortiqcha to'lov" EMAS)
    tikla()
    oid, (iid,), _ = yangi_buyurtma(miqdor=10)
    b0 = buyurtma(oid)
    qarz = round(b0.debt) if b0 else 0
    tana = _t_tana(oid, iid, miqdor=10, payment_amount=qarz, transport_cost=0,
                   transport_payer="none", transport_carrier=None)
    r1 = req(C, "post", "/api/deliveries", json=tana)
    b1 = buyurtma(oid)
    check("T4 to'liq yetkazish + to'liq to'lov → 200, qarz 0, 10 topshirilgan",
          r1.status_code == 200 and b1 is not None and abs(b1.debt) < 0.01
          and b1.delivered == [10.0], f"{r1.status_code} {matn(r1)[:160]} {vars(b1) if b1 else None}")
    h0 = holat()
    r2 = req(C, "post", "/api/deliveries", json=tana)
    j2 = jsn(r2) or {}
    check("T4 takror → 200 duplicate (400 'Qoldiqdan ko'p' / 409 EMAS), baza o'zgarmagan",
          r2.status_code == 200 and j2.get("duplicate") is True
          and j2.get("delivery_id") == (jsn(r1) or {}).get("delivery_id") and holat() == h0,
          f"{r2.status_code} {matn(r2)[:200]}")
    check("T4 takror javobida buyurtma holati haqiqiy (to'liq topshirilgan)",
          j2.get("is_fully_delivered") is True and j2.get("delivery_percent") == 100,
          {k: j2.get(k) for k in ("is_fully_delivered", "delivery_percent", "order_status")})


def _t_begona():
    # T5 — begona korxona AYNAN shu tanani yuborsa: 400, A ning yetkazishi qaytmaydi
    tikla()
    oid, (iid,), _ = yangi_buyurtma(miqdor=30)
    tana = _t_tana(oid, iid)
    r1 = req(C, "post", "/api/deliveries", json=tana)
    j1 = jsn(r1) or {}
    h0 = holat()
    r2 = req(CB, "post", "/api/deliveries", json=tana)
    m = matn(r2)
    check("T5 begona korxona AYNAN shu tana → 400 'Buyurtma topilmadi', A ning yetkazishi qaytmagan",
          r1.status_code == 200 and r2.status_code == 400 and "Buyurtma topilmadi" in m
          and str(j1.get("delivery_number")) not in m and holat() == h0,
          f"{r2.status_code} {m[:200]}")


def _t_eskirgan_sessiya():
    # T6 — sessiya qoldiqni qulfdan OLDIN o'qigan (masalan `services` "Tayyor"
    # oqimi buyurtmani oldindan yuklaydi), orada boshqa so'rov 20 topshirgan:
    # 19 lik yetkazish qulf ostida qayta o'qilgan qoldiq (10) bilan RAD etilishi
    # SHART (aks holda 39 topshirilardi)
    tikla()
    oid, (iid,), _ = yangi_buyurtma(miqdor=30)
    s1 = SessionLocal()
    try:
        o = s1.get(Order, oid)
        _ = [i.remaining_qty for i in o.items]
        _ = o.status, o.debt_amount
        s2 = SessionLocal()
        try:
            r2 = _t_ildiz(s2, oid, iid, 20)
        finally:
            s2.close()
        r1 = _t_ildiz(s1, oid, iid, 19)
    finally:
        s1.close()
    y = _t_yetkazishlar(oid)
    check("T6 eskirgan sessiya: 20 saqlandi, keyingi 19 'Qoldiqdan ko'p' bilan rad, jami 20",
          r2.get("success") is True and r1.get("success") is False
          and "Qoldiqdan ko'p" in str(r1.get("message")) and y.jami == 20 and y.soni == 1,
          f"r2={r2} r1={r1} {vars(y)}")

    # T7 — chaqiruvchining hali yozilmagan (flush qilinmagan) o'zgarishi
    # yetkazish ichidagi qayta o'qishda YO'QOLMASLIGI shart (sessiya autoflush=False)
    tikla()
    oid, (iid,), _ = yangi_buyurtma(miqdor=30)
    s1 = SessionLocal()
    try:
        o = s1.get(Order, oid)
        o.notes = "T7_YOZILMAGAN_OZGARISH"
        r = _t_ildiz(s1, oid, iid, 5)
    finally:
        s1.close()
    d = SessionLocal()
    try:
        izoh = d.get(Order, oid).notes
    finally:
        d.close()
    check("T7 chaqiruvchining yozilmagan o'zgarishi saqlangan (yetkazish bilan birga)",
          r.get("success") is True and izoh == "T7_YOZILMAGAN_OZGARISH", f"{r} notes={izoh!r}")


def _t_parallel():
    # T8 — ikki oqim BIR VAQTDA (faqat HAQIQIY PostgreSQL; SQLite da haqiqiy
    # parallellik yo'q). Har urinish YANGI buyurtmada.
    if not PG_REJIM:
        print("  (T8 parallel — faqat PG rejimida)")
        return

    def ikki(oid, iid, miqdorlar, tolovlar):
        natija = [None, None]
        bar = threading.Barrier(2)

        def ish(k):
            s = SessionLocal()
            try:
                try:
                    bar.wait(timeout=30)
                except Exception:
                    pass
                natija[k] = _t_ildiz(s, oid, iid, miqdorlar[k], tolovlar[k])
            finally:
                s.close()
        ts = [threading.Thread(target=ish, args=(k,)) for k in range(2)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(timeout=120)
        return natija

    for nom, miqdorlar, tolovlar, kutish in (
            ("bir xil 5 + 5, to'lov bilan", (5, 5), (70000, 70000), "takror"),
            ("farqli 20 + 19 (qoldiq 30), to'lovsiz", (20, 19), (None, None), "rad"),
            ("farqli 20 + 19 (qoldiq 30), to'lov bilan", (20, 19), (80000, 90000), "rad")):
        yomon = []
        for k in range(3):
            oid, (iid,), _ = yangi_buyurtma(miqdor=30)
            tl = tuple(None if x is None else x + k for x in tolovlar)
            nat = ikki(oid, iid, miqdorlar, tl)
            y = _t_yetkazishlar(oid)
            muvaffaq = [x for x in nat if x and x.get("success")]
            if kutish == "takror":
                ok = (y.soni == 1 and y.tolov == 1 and y.jami == 5 and len(muvaffaq) == 2
                      and sum(1 for x in muvaffaq if x.get("duplicate") is True) == 1)
            else:
                rad = [x for x in nat if x and not x.get("success")]
                ok = (y.soni == 1 and y.jami <= 30 and len(rad) == 1
                      and "Qoldiqdan ko'p" in str(rad[0].get("message"))
                      and y.tolov == (1 if tolovlar[0] else 0))
            ok = ok and len(y.raqamlar) == len(set(y.raqamlar))
            if not ok:
                yomon.append((nat, vars(y)))
        check(f"T8 parallel {nom}: 3 urinishda ham bitta yetkazish, oshib ketish yo'q",
              not yomon, str(yomon[:1])[:400])


def _t_statik():
    # T9 — statik tartib (SQLite rejimida qulf/parallellik sinalmaydi)
    try:
        src = inspect.getsource(crud.create_delivery)
    except Exception as e:
        src = f"ISTISNO {e}"
    check("T9 create_delivery: qulf → qayta o'qish → holat tekshiruvi → imzo → qoldiq → to'lov chegarasi",
          tartibda(src, "_pul_qulfi(db, 101, order.id)", "db.expire_all()",
                   "if order.is_deleted", "_yetkazish_imzo_sorov(", "for di in data.items:",
                   "_tolov_chegarasi("), "tartib buzilgan")
    check("T9 create_delivery: qulfdan OLDIN flush (chaqiruvchi o'zgarishi saqlansin)",
          tartibda(src, "order = _oq.first()", "db.flush()", "_pul_qulfi(db, 101, order.id)"),
          "flush yo'q yoki joyi noto'g'ri")
    check("T9 create_delivery: qulf funksiyada BIR marta (to'lov blokida takror emas)",
          src.count("_pul_qulfi(") == 1, src.count("_pul_qulfi("))
    try:
        rsrc = inspect.getsource(main.api_create_delivery)
    except Exception as e:
        rsrc = f"ISTISNO {e}"
    check("T9 marshrut: takror javob Telegram / nakladnoy yuborishdan OLDIN qaytadi",
          tartibda(rsrc, 'if not result["success"]', 'if result.get("duplicate"):',
                   "return result", "_send_telegram("), "tartib buzilgan")
    usul = getattr(crud, "_YETKAZISH_USULI", None)
    check("T9 to'lov usuli jadvali yagona (yozuv va imzo bir xil)",
          isinstance(usul, dict) and set(usul) == {"naqd", "plastik", "o'tkazma"}
          and "_yetkazish_usuli(" in src and "method_map" not in src, usul)


def k_bolimi():
    section("K. Kumulyativ — sahifalar 200, hech bir javob 5xx emas")
    yomon = sahifalar_yiqilgan(C)
    check("K barcha sahifa va API ro'yxatlari 200", not yomon, yomon)
    besh = [k for k in KODLAR if k[0] >= 500]
    check("K butun ish davomida birorta ham 5xx javob yo'q", not besh, besh[:5])


# ══════════════════════════════════════════════════════════════
# Ishga tushirish
# ══════════════════════════════════════════════════════════════
r_bolimi()
d_bolimi()
n_bolimi()
s_bolimi()
f_bolimi()
t_bolimi()
if not PG_REJIM:
    g_bolimi()
h_bolimi()
k_bolimi()

if not PG_REJIM:
    section("P. PostgreSQL rejimi")
    if not PG_URL:
        print("  (o'tkazib yuborildi — PG_URL muhitda yo'q; masalan "
              "PG_URL=postgresql://postgres@127.0.0.1:5432)")
    else:
        env = dict(os.environ, QAYTARISH_PG_REJIM="1")
        try:
            pr = subprocess.run([sys.executable, os.path.abspath(__file__)], env=env,
                                capture_output=True, text=True, timeout=800)
            chiq = pr.stdout + ("\n" + pr.stderr[-2000:] if pr.returncode not in (0, 1) else "")
            rc = pr.returncode
        except Exception as e:
            chiq, rc = f"ISTISNO {type(e).__name__}: {e}", 99
        p_ok = p_fail = None
        for q in chiq.splitlines():
            if q.startswith("NATIJA:"):
                try:
                    p_ok = int(q.split("o'tdi =")[1].split()[0])
                    p_fail = int(q.split("yiqildi =")[1].split()[0])
                except Exception:
                    pass
                print("  [PG] P-" + q)
            elif "✗" in q or q.startswith("---") or q.startswith("  ✓"):
                print(q)
        if p_ok is None:
            check("P PostgreSQL rejimi ishga tushdi va natija berdi", False, chiq[-600:])
        else:
            OK += p_ok
            FAIL += p_fail
            if p_fail:
                FAILED.append(f"[PG] ichki yiqilganlar: {p_fail} ta (yuqorida ✗ bilan)")
            check("P PostgreSQL rejimi yakunlandi (chiqish kodi 0 yoki 1)", rc in (0, 1), rc)

print("\n" + "=" * 66)
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
sys.exit(0 if FAIL == 0 else 1)
