#!/usr/bin/env python3
"""
test_yetkazish_detal_tolov.py — 5-bo'lim 6-band va 13-band darvozasi
(kech38, 2026-09-23).

NIMA UCHUN KERAK (asl kod `c7a11f3` da O'LCHANGAN — SQLite va HAQIQIY
PostgreSQL 16, `work/probe38.py`)
--------------------------------------------------------------------
6-band — `POST /api/deliveries`:
  * [o'z detali 2, BOSHQA buyurtma detali 3] → 200, faqat o'z detali yozilardi;
  * [mavjud bo'lmagan id, o'z detali] → 200, xuddi shunday;
  * faqat begona / yo'q qator → 400 "Yetkazish uchun miqdor kiritilmagan"
    (sabab noto'g'ri — miqdor kiritilgan edi).
  `crud.create_delivery` siklida `if not oi: continue` — qator JIM tashlanardi.
  Haqiqiy holat: yetkazish oynasi ochiq turganda boshqa xodim detalni o'chirsa,
  foydalanuvchi "saqlandi" ko'rardi, bir qator izsiz yo'qolardi.
13-band — `POST /api/payments`:
  * yuk bilan 50 000 naqd to'lov yozilgach 8 s ichida qo'lda 50 000 naqd →
    200 `duplicate: true`, YANGI YOZUV YO'Q (`orders.html` `duplicate` ni
    o'qimaydi — foydalanuvchi "saqlandi" ko'radi);
  * teskari tartibda (avval qo'lda, keyin yuk bilan) — ikkalasi yoziladi.
  Takror-himoya (`create_payment`, 8 s) yuk to'lovini ham ko'rardi.

12-band — `DELETE /api/deliveries/{id}` (to'lov bog'langan yuk xati):
  * HAQIQIY PostgreSQL da (jonli sinov saytida ham) → 500
    (`payments_delivery_id_fkey`), hech narsa o'zgarmasdi; `orders.html`
    `deleteDelivery` `!res.ok` da HECH QANDAY xabar ko'rsatmasdi;
  * SQLite da yuk o'chardi, to'lov mavjud bo'lmagan yukka ishora qilib qolardi.
  FOYDALANUVCHI QARORI (kech38): "Har safar so'rasin".

Tuzatish (kech38):
  * `crud.delete_delivery` / marshrut: to'lov bog'langan va `tolov` yo'q → 409
    (`delivery_has_payment`, hech narsa o'zgarmaydi); `?tolov=ochir` — to'lov
    ham o'chadi (audit izi), `?tolov=qoldir` — to'lov oddiy to'lov bo'lib qoladi
    (`delivery_id = NULL`, izoh, audit izi); boshqa qiymat — 400. Qulf (101,
    buyurtma) + qulf ostida qayta o'qish; hammasi bitta tranzaksiyada.
  * `crud.create_delivery`: har qator shu buyurtma detali bo'lishi SHART —
    aks holda butun so'rov rad ("'items' N-qator: bu detal shu buyurtmada
    topilmadi …"); tekshiruv imzo va qoldiqdan OLDIN.
  * `crud.create_payment`: takror-himoya faqat `delivery_id IS NULL` to'lovlar
    orasida.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_yetkazish_detal_tolov.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_yetkazish_detal_tolov.py
"""
import os
import sys
import inspect
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "yetkazish_detal_tolov_test"
_DB = os.path.join(tempfile.gettempdir(), "yetkazish_detal_tolov_test.db")

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
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, schemas                     # noqa: E402

from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, Delivery, DeliveryItem, Payment,
    ActivityLog, PaymentType, PaymentMethod,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


def tartibda(src, *qismlar):
    """Qismlar matnda AYNAN shu tartibda (`find`, topilmasa False — qulamaydi)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


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


def xabar(r):
    """400 javobidagi sabab matni (`detail.message` yoki `detail` matn)."""
    d = js(r)
    if isinstance(d, dict):
        det = d.get("detail")
        if isinstance(det, dict):
            return str(det.get("message") or "")
        return str(det or "")
    return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="YD Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "YD_admin", "Parol123!", UserRole.ADMIN, "YD Admin", company_id=1)
PRJ = Project(company_id=1, client_name="YD Mijoz", project_name="YD loyiha",
              total_budget=0, total_paid=0)
PRJ_B = Project(company_id=2, client_name="YD Mijoz B", project_name="YD loyiha B",
                total_budget=0, total_paid=0)
_db.add_all([PRJ, PRJ_B])
_db.commit()
PRJ_ID, PRJB_ID = PRJ.id, PRJ_B.id
_db.close()

_n = [0]


def yangi_buyurtma(miqdor=10, narx=100_000, soni_=1, cid=1, prj=None):
    """YANGI buyurtma (panel, penoplastsiz) → (order_id, [detal_id])."""
    _n[0] += 1
    d = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            o = crud.create_order(d, schemas.OrderCreate(
                project_id=prj or PRJ_ID, order_type="product",
                items=[schemas.OrderItemCreate(
                    name=f"YD_D{_n[0]}_{i}", category="panel", width=100, thickness=10,
                    length=100, quantity=miqdor, unit_price=narx, is_coated=False)
                    for i in range(soni_)]), performed_by="YD")
        oid = o.id
        o2 = d.get(Order, oid)
        if o2.company_id != cid:
            o2.company_id = cid
        items = d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()
        for it in items:
            if getattr(it, "company_id", cid) != cid:
                it.company_id = cid
        d.commit()
        return oid, [x.id for x in items]
    finally:
        d.close()


def holat(oid):
    """Buyurtma holati: yetkazishlar soni, detal bo'yicha berilgan miqdor,
    to'lovlar (summa, yuk bog'liqmi), to'langan summa."""
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        dl = d.query(Delivery).filter(Delivery.order_id == oid).count()
        di = {}
        for it in d.query(OrderItem).filter(OrderItem.order_id == oid).all():
            di[it.id] = round(sum(float(x.quantity) for x in d.query(DeliveryItem).filter(
                DeliveryItem.order_item_id == it.id).all()), 6)
        py = sorted((float(p.amount), p.delivery_id is not None)
                    for p in d.query(Payment).filter(Payment.order_id == oid).all())
        return {"yetkazish": dl, "detal": di, "tolov": py,
                "tolangan": round(float(o.paid_amount or 0), 2),
                "holat": o.status.value, "tolov_holati": o.payment_status.value}
    finally:
        d.close()


C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "YD_admin", "password": "Parol123!"},
          follow_redirects=False)
if _lr.status_code != 302:
    print(f"LOGIN BO'LMADI: {_lr.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)


def dlv(oid, qatorlar, **kw):
    tana = {"order_id": oid, "items": [{"order_item_id": a, "quantity": b} for a, b in qatorlar]}
    tana.update(kw)
    return req(C, "post", "/api/deliveries", json=tana)


def tolov(oid, summa, usul="naqd"):
    return req(C, "post", "/api/payments",
               json={"order_id": oid, "amount": summa, "payment_type": "partial",
                     "payment_method": usul})


# ══════════════════════════════════════════════════════════════
# 6-band — begona / mavjud bo'lmagan detal qatori
# ══════════════════════════════════════════════════════════════
def bolim_6():
    section("6. Yetkazish: buyurtmaga tegishli bo'lmagan detal qatori — butun so'rov rad")
    A, (a1, a2) = yangi_buyurtma(soni_=2)
    B, (b1,) = yangi_buyurtma()
    X, (x1,) = yangi_buyurtma(cid=2, prj=PRJB_ID)
    a0, b0, x0 = holat(A), holat(B), holat(X)

    # 6a — o'z detali + BOSHQA buyurtma detali (bir korxona)
    r = dlv(A, [(a1, 2), (b1, 3)])
    check("6a [o'z, boshqa buyurtma detali] → 400", r.status_code == 400, (r.status_code, r.text[:200]))
    m = xabar(r)
    check("6a sabab: 2-qator, detal topilmadi, sahifani yangilash",
          "'items' 2-qator" in m and "topilmadi" in m and "yangilab" in m, m)
    check("6a hech narsa yozilmadi (A va B o'zgarmagan)",
          holat(A) == a0 and holat(B) == b0, (holat(A), holat(B)))

    # 6b — mavjud bo'lmagan id birinchi qatorda
    r = dlv(A, [(999999, 1), (a2, 1)])
    check("6b [yo'q id, o'z detali] → 400", r.status_code == 400, (r.status_code, r.text[:200]))
    check("6b sabab: 1-qator", "'items' 1-qator" in xabar(r) and "topilmadi" in xabar(r), xabar(r))
    check("6b hech narsa yozilmadi", holat(A) == a0, holat(A))

    # 6c — faqat begona qator: sabab aniq (ilgari "miqdor kiritilmagan")
    r = dlv(A, [(b1, 1)])
    check("6c faqat boshqa buyurtma detali → 400, sabab \"topilmadi\" (\"miqdor kiritilmagan\" EMAS)",
          r.status_code == 400 and "topilmadi" in xabar(r)
          and "miqdor kiritilmagan" not in xabar(r), (r.status_code, xabar(r)))

    # 6d — BEGONA KORXONA buyurtmasining detali
    r = dlv(A, [(a1, 1), (x1, 1)])
    check("6d [o'z, begona korxona detali] → 400, hech narsa yozilmadi",
          r.status_code == 400 and "topilmadi" in xabar(r)
          and holat(A) == a0 and holat(X) == x0, (r.status_code, xabar(r), holat(A), holat(X)))

    # 6e — to'lov bilan: to'lov ham yozilmaydi
    r = dlv(A, [(a1, 2), (b1, 1)], payment_amount=50000, payment_method="naqd")
    check("6e to'lov bilan [o'z, begona] → 400, yetkazish ham to'lov ham YO'Q",
          r.status_code == 400 and holat(A) == a0, (r.status_code, holat(A)))

    # 6f — IJOBIY: to'g'ri qatorlar saqlanadi
    r = dlv(A, [(a1, 2), (a2, 1)])
    h = holat(A)
    check("6f IJOBIY: ikkala o'z detali → 200, 2 va 1 berildi",
          r.status_code == 200 and h["yetkazish"] == 1 and h["detal"] == {a1: 2.0, a2: 1.0},
          (r.status_code, h))

    # 6g — takror imzo bilan: 6f dan keyin 8 s ichida [a1:2, a2:1, begona] —
    # ilgari begona qator imzodan tushib, "takroriy" (200 duplicate) deb qabul
    # qilinardi; endi noto'g'ri so'rov sifatida rad.
    r = dlv(A, [(a1, 2), (a2, 1), (b1, 1)])
    d = js(r) if isinstance(js(r), dict) else {}
    check("6g takror oynasida [6f qatorlari + begona] → 400 (takroriy deb yutilmaydi)",
          r.status_code == 400 and not d.get("duplicate") and "'items' 3-qator" in xabar(r),
          (r.status_code, r.text[:200]))
    check("6g yetkazishlar soni o'zgarmadi (1)", holat(A)["yetkazish"] == 1, holat(A))
    # AYNAN 6f takrori esa hamon takroriy
    r = dlv(A, [(a1, 2), (a2, 1)])
    d = js(r) if isinstance(js(r), dict) else {}
    check("6g AYNAN takror → 200 duplicate (himoya buzilmagan)",
          r.status_code == 200 and d.get("duplicate") is True and holat(A)["yetkazish"] == 1,
          (r.status_code, d))

    # 6h — ILDIZ (crud to'g'ridan, marshrutsiz)
    s = SessionLocal()
    try:
        try:
            res = crud.create_delivery(s, schemas.DeliveryCreate(
                order_id=B, items=[schemas.DeliveryItemCreate(order_item_id=b1, quantity=1),
                                   schemas.DeliveryItemCreate(order_item_id=a1, quantity=1)]),
                delivered_by="YD", company_id=1)
        except Exception as e:                 # noqa: BLE001
            s.rollback()
            res = {"success": None, "message": f"ISTISNO {type(e).__name__}: {e}"}
    finally:
        s.close()
    check("6h crud.create_delivery (ildiz): [o'z, begona] → success False, 2-qator",
          isinstance(res, dict) and res.get("success") is False
          and "'items' 2-qator" in str(res.get("message")), res)
    check("6h ildizda hech narsa yozilmadi", holat(B) == b0, holat(B))

    # 6i — STATIK tartib: detal tekshiruvi imzodan va qoldiq siklidan OLDIN
    try:
        src = inspect.getsource(crud.create_delivery)
    except Exception as e:                     # noqa: BLE001
        src = f"ISTISNO {e}"
    check("6i statik: bo'sh ro'yxat → detal tegishliligi → imzo → qoldiq sikli",
          tartibda(src, "if not data.items:", "_detal_idlari = {oi.id for oi in order.items}",
                   "not in _detal_idlari", "_yetkazish_imzo_sorov(data, _detal_idlari)",
                   "for di in data.items:"), "tartib buzilgan")


# ══════════════════════════════════════════════════════════════
# 13-band — qo'lda to'lov takror-himoyasi faqat qo'lda to'lovlar orasida
# ══════════════════════════════════════════════════════════════
def bolim_13():
    section("13. Qo'lda to'lov takror-himoyasi yuk to'lovini ko'rmaydi")
    # 13a — yuk bilan 50 000 → darhol qo'lda 50 000 (ikkalasi yoziladi)
    E, (e1,) = yangi_buyurtma()
    r = dlv(E, [(e1, 2)], payment_amount=50000, payment_method="naqd")
    check("13a yuk bilan 50 000 naqd → 200", r.status_code == 200, (r.status_code, r.text[:200]))
    r = tolov(E, 50000)
    d = js(r) if isinstance(js(r), dict) else {}
    check("13a 8 s ichida qo'lda 50 000 naqd → 200, duplicate False",
          r.status_code == 200 and d.get("duplicate") is False, (r.status_code, d))
    h = holat(E)
    check("13a ikkala to'lov yozildi (yuk + qo'lda), to'langan 100 000",
          h["tolov"] == [(50000.0, False), (50000.0, True)] and h["tolangan"] == 100000.0, h)
    # 13b — o'sha zahoti qo'lda 50 000 YANA → endi haqiqiy takror (qo'lda) → yutiladi
    r = tolov(E, 50000)
    d = js(r) if isinstance(js(r), dict) else {}
    check("13b qo'lda to'lov AYNAN takrori → duplicate True, yangi yozuv yo'q",
          r.status_code == 200 and d.get("duplicate") is True and len(holat(E)["tolov"]) == 2,
          (r.status_code, d, holat(E)))

    # 13c — faqat qo'lda ikki marta (asl himoya saqlangan)
    G, _ = yangi_buyurtma()
    r1, r2 = tolov(G, 80000), tolov(G, 80000)
    d1 = js(r1) if isinstance(js(r1), dict) else {}
    d2 = js(r2) if isinstance(js(r2), dict) else {}
    check("13c qo'lda 80 000 ikki marta → 1-si yangi, 2-si duplicate, bitta yozuv",
          d1.get("duplicate") is False and d2.get("duplicate") is True
          and d1.get("payment_id") == d2.get("payment_id") and holat(G)["tolov"] == [(80000.0, False)],
          (d1, d2, holat(G)))

    # 13d — teskari tartib (avval qo'lda, keyin yuk bilan) — ikkalasi (o'zgarmagan)
    F, (f1,) = yangi_buyurtma()
    tolov(F, 70000)
    r = dlv(F, [(f1, 2)], payment_amount=70000, payment_method="naqd")
    check("13d qo'lda 70 000 → yuk bilan 70 000: ikkalasi yozildi",
          r.status_code == 200 and holat(F)["tolov"] == [(70000.0, False), (70000.0, True)], holat(F))

    # 13e — yuk to'lovi boshqa usulda (plastik) — qo'lda naqd bir xil summa → yangi
    H, (h1,) = yangi_buyurtma()
    dlv(H, [(h1, 1)], payment_amount=40000, payment_method="plastik")
    r = tolov(H, 40000, "plastik")
    d = js(r) if isinstance(js(r), dict) else {}
    check("13e yuk bilan 40 000 plastik → qo'lda 40 000 plastik: yangi yozuv",
          d.get("duplicate") is False and len(holat(H)["tolov"]) == 2, (d, holat(H)))

    # 13f — ILDIZ (crud.create_payment to'g'ridan)
    K, (k1,) = yangi_buyurtma()
    dlv(K, [(k1, 1)], payment_amount=30000, payment_method="naqd")
    s = SessionLocal()
    try:
        try:
            p = crud.create_payment(s, schemas.PaymentCreate(
                order_id=K, amount=30000, payment_type="partial", payment_method="naqd"),
                company_id=1)
            dup = bool(getattr(p, "_is_duplicate_submit", False))
            s.commit()
        except Exception as e:                 # noqa: BLE001
            s.rollback()
            dup = f"ISTISNO {type(e).__name__}: {e}"
    finally:
        s.close()
    check("13f crud.create_payment (ildiz): yuk to'lovidan keyin → takror EMAS, yozildi",
          dup is False and len(holat(K)["tolov"]) == 2, (dup, holat(K)))

    # 13g — STATIK: takror so'rovida delivery_id IS NULL
    try:
        src = inspect.getsource(crud.create_payment)
    except Exception as e:                     # noqa: BLE001
        src = f"ISTISNO {e}"
    check("13g statik: `_oldingi` so'rovida `Payment.delivery_id.is_(None)`",
          tartibda(src, "_oldingi = db.query(Payment).filter(", "Payment.delivery_id.is_(None),",
                   "Payment.paid_at >=", ").order_by("), "filtr yo'q")


# ══════════════════════════════════════════════════════════════
# 12-band — to'lov bog'langan yuk xatini o'chirish ("Har safar so'rasin")
# ══════════════════════════════════════════════════════════════
def _yuk_tolov_bilan(summa=50000, miqdor=3, detal_miqdor=10):
    O, (i1,) = yangi_buyurtma(miqdor=detal_miqdor)
    r = dlv(O, [(i1, miqdor)], payment_amount=summa, payment_method="naqd")
    d = js(r) if isinstance(js(r), dict) else {}
    return O, i1, d.get("delivery_id"), d.get("delivery_number")


def _yuk_bormi(did):
    d = SessionLocal()
    try:
        return d.query(Delivery).filter(Delivery.id == did).count() == 1
    finally:
        d.close()


def _audit(pid, amal):
    d = SessionLocal()
    try:
        return [(a.new_value or "", a.old_value or "", a.company_id) for a in d.query(ActivityLog).filter(
            ActivityLog.entity_type == "payment", ActivityLog.entity_id == pid,
            ActivityLog.action == amal).all()]
    finally:
        d.close()


def _tolov(pid):
    d = SessionLocal()
    try:
        p = d.get(Payment, pid)
        return None if p is None else (float(p.amount), p.delivery_id, p.notes or "")
    finally:
        d.close()


def _loyiha_tolangan():
    d = SessionLocal()
    try:
        return round(float(d.get(Project, PRJ_ID).total_paid or 0), 2)
    finally:
        d.close()


def _yuk_tolov_idlari(did):
    d = SessionLocal()
    try:
        return [p.id for p in d.query(Payment).filter(Payment.delivery_id == did).order_by(Payment.id).all()]
    finally:
        d.close()


def _yetim_tolovlar():
    """Mavjud bo'lmagan yukka ishora qiluvchi to'lovlar soni (SQLite da FK yo'q)."""
    d = SessionLocal()
    try:
        return sum(1 for p in d.query(Payment).filter(Payment.delivery_id.isnot(None)).all()
                   if d.get(Delivery, p.delivery_id) is None)
    finally:
        d.close()


def bolim_12():
    section("12. To'lov bog'langan yuk xatini o'chirish — har safar so'raladi")
    # 12a — so'rovsiz o'chirish → 409, hech narsa o'zgarmaydi
    O, i1, did, raqam = _yuk_tolov_bilan(summa=50000)
    ids = _yuk_tolov_idlari(did)
    pid = ids[0] if ids else None
    check("12a tayyorgarlik: yukka AYNAN 1 ta to'lov bog'langan", len(ids) == 1, ids)
    h0, lp0 = holat(O), _loyiha_tolangan()
    r = req(C, "delete", f"/api/deliveries/{did}")
    det = (js(r) or {}).get("detail") if isinstance(js(r), dict) else None
    det = det if isinstance(det, dict) else {}
    check("12a to'lovli yuk, `tolov` yo'q → 409 (500 EMAS)", r.status_code == 409, (r.status_code, r.text[:200]))
    check("12a detail: type delivery_has_payment, to'lov ro'yxati va jami",
          det.get("type") == "delivery_has_payment" and det.get("total") == 50000
          and det.get("payments") == [{"id": pid, "amount": 50000.0}]
          and det.get("delivery_number") == raqam, det)
    m = str(det.get("message") or "")
    check("12a xabar: yuk raqami, summa, ikkala tugma nomi",
          raqam and raqam in m and "50,000 so'm" in m and "To'lovni ham o'chirish" in m
          and "To'lovni saqlab qolish" in m, m)
    check("12a hech narsa o'zgarmadi (yuk, to'lov, qarz, loyiha)",
          holat(O) == h0 and _yuk_bormi(did) and _tolov(pid) is not None
          and _loyiha_tolangan() == lp0, (holat(O), _tolov(pid)))

    # 12b — ?tolov=ochir → yuk ham, to'lov ham o'chadi
    r = req(C, "delete", f"/api/deliveries/{did}?tolov=ochir")
    jj = js(r) if isinstance(js(r), dict) else {}
    h = holat(O)
    check("12b ?tolov=ochir → 200, javobda 1 ta to'lov o'chirildi",
          r.status_code == 200 and jj.get("tolov_ochirildi") == 1 and jj.get("tolov_saqlandi") == 0,
          (r.status_code, r.text[:200]))
    check("12b yuk va to'lov YO'Q, detal qoldiqqa qaytdi, to'langan 0, holat 'unpaid'",
          not _yuk_bormi(did) and _tolov(pid) is None and h["detal"] == {i1: 0}
          and h["tolov"] == [] and h["tolangan"] == 0 and h["tolov_holati"] == "unpaid", h)
    check("12b loyiha \"To'langan\" 50 000 ga kamaydi", _loyiha_tolangan() == round(lp0 - 50000, 2),
          (lp0, _loyiha_tolangan()))
    au = _audit(pid, "deleted")
    check("12b audit izi: to'lov o'chirilgani (summa, yuk raqami, korxona 1)",
          len(au) == 1 and "50,000 so'm" in au[0][0] and raqam in au[0][0] and au[0][2] == 1, au)

    # 12c — ?tolov=qoldir → yuk o'chadi, to'lov oddiy to'lov bo'lib qoladi
    O, i1, did, raqam = _yuk_tolov_bilan(summa=60000)
    ids = _yuk_tolov_idlari(did)
    pid = ids[0] if ids else None
    lp0 = _loyiha_tolangan()
    r = req(C, "delete", f"/api/deliveries/{did}?tolov=qoldir")
    jj = js(r) if isinstance(js(r), dict) else {}
    h = holat(O)
    tp = _tolov(pid)
    check("12c ?tolov=qoldir → 200, javobda 1 ta to'lov saqlandi",
          r.status_code == 200 and jj.get("tolov_saqlandi") == 1 and jj.get("tolov_ochirildi") == 0,
          (r.status_code, r.text[:200]))
    check("12c yuk YO'Q, to'lov QOLDI (delivery_id NULL), to'langan 60 000, holat 'partial'",
          not _yuk_bormi(did) and tp is not None and tp[1] is None and tp[0] == 60000.0
          and h["tolov"] == [(60000.0, False)] and h["tolangan"] == 60000.0
          and h["tolov_holati"] == "partial" and h["detal"] == {i1: 0}, (tp, h))
    check("12c to'lov izohida yuk o'chirilgani yozildi", tp is not None and raqam in tp[2]
          and "o'chirilgan" in tp[2] and "saqlab qolingan" in tp[2], tp)
    check("12c loyiha \"To'langan\" o'zgarmadi", _loyiha_tolangan() == lp0, (lp0, _loyiha_tolangan()))
    au = _audit(pid, "updated")
    check("12c audit izi: to'lov saqlab qolindi", len(au) == 1 and "saqlab qolindi" in au[0][0]
          and raqam in au[0][1], au)

    # 12d — noto'g'ri `tolov` → 400, hech narsa o'zgarmaydi
    O, i1, did, raqam = _yuk_tolov_bilan(summa=70000)
    h0 = holat(O)
    for qiymat in ("xyz", "", "OCHIR"):
        r = req(C, "delete", f"/api/deliveries/{did}?tolov={qiymat}")
        check(f"12d ?tolov={qiymat!r} → 400, sabab aniq, hech narsa o'zgarmadi",
              r.status_code == 400 and "'tolov' noto'g'ri qiymat" in xabar(r)
              and holat(O) == h0 and _yuk_bormi(did), (r.status_code, xabar(r), holat(O)))

    # 12e — to'lovsiz yuk: avvalgidek darhol o'chadi; `tolov` e'tiborsiz
    for qiymat in (None, "ochir"):
        O, (i1,) = yangi_buyurtma()
        r = dlv(O, [(i1, 2)])
        did = (js(r) or {}).get("delivery_id") if isinstance(js(r), dict) else None
        url = f"/api/deliveries/{did}" + (f"?tolov={qiymat}" if qiymat else "")
        r = req(C, "delete", url)
        check(f"12e to'lovsiz yuk ({'tolovsiz so`rov' if not qiymat else '?tolov=ochir'}) → 200, yuk o'chdi",
              r.status_code == 200 and not _yuk_bormi(did) and holat(O)["detal"] == {i1: 0},
              (r.status_code, r.text[:150]))

    # 12f — to'liq topshirilgan (Yetkazildi) → o'chirilsa "Jarayonda", to'lov holati qayta hisoblanadi.
    # kech75 (92-band, FOYDALANUVCHI QARORI B): ilgari "Tayyor" (ready) bo'lardi — hech kim "Tayyor"
    # bosmagan buyurtma oylik hisobotga kirardi. Endi `update_order_full` bilan bir xil — in_progress.
    O, i1, did, raqam = _yuk_tolov_bilan(summa=100000, miqdor=10, detal_miqdor=10)
    h_old = holat(O)
    r = req(C, "delete", f"/api/deliveries/{did}?tolov=ochir")
    h = holat(O)
    check("12f to'liq topshirilgan buyurtma: 'delivered' → o'chirilgach 'in_progress', 'unpaid'",
          h_old["holat"] == "delivered" and r.status_code == 200 and h["holat"] == "in_progress"
          and h["tolov_holati"] == "unpaid" and h["tolangan"] == 0, (h_old, h))

    # 12g — bir yukka IKKI to'lov (eski ma'lumot) — ikkalasi ko'rsatiladi va o'chadi
    O, i1, did, raqam = _yuk_tolov_bilan(summa=30000)
    d = SessionLocal()
    try:
        d.add(Payment(order_id=O, delivery_id=did, amount=20000, payment_type=PaymentType.PARTIAL,
                      payment_method=PaymentMethod.CASH, notes="eski ma'lumot"))
        d.commit()
    finally:
        d.close()
    ids = _yuk_tolov_idlari(did)
    r = req(C, "delete", f"/api/deliveries/{did}")
    det = (js(r) or {}).get("detail") if isinstance(js(r), dict) else None
    det = det if isinstance(det, dict) else {}
    check("12g ikki to'lov → 409, ikkalasi ro'yxatda, jami 50 000, xabarda \"2 ta to'lov\"",
          r.status_code == 409 and [x.get("id") for x in det.get("payments") or []] == ids
          and det.get("total") == 50000 and "2 ta to'lov (jami 50,000 so'm)" in str(det.get("message")),
          (r.status_code, det))
    r = req(C, "delete", f"/api/deliveries/{did}?tolov=ochir")
    check("12g ?tolov=ochir → ikkala to'lov ham o'chdi",
          r.status_code == 200 and all(_tolov(x) is None for x in ids) and holat(O)["tolov"] == [],
          (r.status_code, holat(O)))

    # 12h — ILDIZ: boshqa korxona nomidan → topilmaydi, hech narsa o'zgarmaydi
    O, i1, did, raqam = _yuk_tolov_bilan(summa=40000)
    h0 = holat(O)
    s = SessionLocal()
    try:
        try:
            res = crud.delete_delivery(s, did, company_id=2, tolov="ochir")
        except TypeError as e:                  # asl kodda `company_id` / `tolov` yo'q
            s.rollback()
            res = f"ISTISNO TypeError: {e}"
        except Exception as e:                  # noqa: BLE001
            s.rollback()
            res = f"ISTISNO {type(e).__name__}: {e}"
    finally:
        s.close()
    check("12h crud.delete_delivery(company_id=2) begona yuk → False, hech narsa o'zgarmadi",
          res is False and holat(O) == h0 and _yuk_bormi(did), (res, holat(O)))

    # 12i — ILDIZ: `tolov` siz → YukToloviBor, hech narsa o'zgarmaydi
    s = SessionLocal()
    try:
        try:
            res = crud.delete_delivery(s, did)
            res = f"ISTISNO YO'Q: {res!r}"
        except Exception as e:                  # noqa: BLE001
            s.rollback()
            res = type(e).__name__
    finally:
        s.close()
    check("12i crud.delete_delivery (ildiz) `tolov` siz → YukToloviBor, hech narsa o'zgarmadi",
          res == "YukToloviBor" and holat(O) == h0 and _yuk_bormi(did), (res, holat(O)))

    # 12j — yetim to'lov yo'q (SQLite da FK tekshirilmaydi — asl kodda qolardi)
    check("12j bazada mavjud bo'lmagan yukka ishora qiluvchi to'lov YO'Q", _yetim_tolovlar() == 0,
          _yetim_tolovlar())

    # 12k / 12l — STATIK: qulf va tranzaksiya
    try:
        src = inspect.getsource(crud.delete_delivery)
    except Exception as e:                      # noqa: BLE001
        src = f"ISTISNO {e}"
    check("12k statik: flush → qulf (101, buyurtma) → expire_all → qayta o'qish → to'lovlar → 409 → yuk o'chirish",
          tartibda(src, "db.flush()", "_pul_qulfi(db, 101, order.id)", "db.expire_all()",
                   "d = db.query(Delivery)", "Payment.delivery_id == d.id", "raise YukToloviBor(",
                   "db.delete(d)", "db.commit()"), "tartib buzilgan")
    check("12l statik: `log_activity(` ISHLATILMAYDI (u commit qiladi — qulf bo'shaydi, yarim holat)",
          "log_activity(" not in src and src.count("db.commit()") == 1, src.count("db.commit()"))


def bolim_12_parallel():
    # 12m — PARALLEL: yukni o'chirish + yangi yuk (faqat HAQIQIY PG).
    # Qulfsiz: yangi yuk eski yukni ko'rib "to'liq" deb 'delivered' qo'yadi,
    # o'chirish esa yangi yukni ko'rmaydi → yarim topshirilgan buyurtma
    # 'delivered' bo'lib qolardi. Oynani ANIQ ochish uchun o'chirish
    # sessiyasining `commit` i 0.4 s kechiktiriladi (o'chirish yozilgan, lekin
    # tasdiqlanmagan), yangi yuk 0.15 s keyin boshlanadi. Qulf bo'lsa yangi yuk
    # o'chirish tugashini kutadi va to'g'ri holatni ko'radi.
    if not PG_URL:
        print("  (12m parallel — faqat PG rejimida)")
        return
    yomon = []
    for k in range(4):
        O, (i1,) = yangi_buyurtma(miqdor=10)
        r = dlv(O, [(i1, 5)])
        did = (js(r) or {}).get("delivery_id") if isinstance(js(r), dict) else None
        natija = [None, None]
        bar = threading.Barrier(2)

        def ochir(k2=0):
            s = SessionLocal()
            _asl_commit = s.commit

            def _sekin_commit():
                time.sleep(0.4)
                _asl_commit()
            s.commit = _sekin_commit
            try:
                try:
                    bar.wait(timeout=30)
                except Exception:               # noqa: BLE001
                    pass
                try:
                    natija[0] = crud.delete_delivery(s, did)
                except Exception as e:          # noqa: BLE001
                    s.rollback()
                    natija[0] = f"ISTISNO {type(e).__name__}: {e}"
            finally:
                s.close()

        def yarat():
            s = SessionLocal()
            try:
                try:
                    bar.wait(timeout=30)
                except Exception:               # noqa: BLE001
                    pass
                time.sleep(0.15)
                try:
                    natija[1] = crud.create_delivery(s, schemas.DeliveryCreate(
                        order_id=O, items=[schemas.DeliveryItemCreate(order_item_id=i1, quantity=5)],
                        notes="YD parallel yangi yuk"),   # izoh farqli — takror-imzoga tushmasin
                        delivered_by="YD", company_id=1)
                except Exception as e:          # noqa: BLE001
                    s.rollback()
                    natija[1] = f"ISTISNO {type(e).__name__}: {e}"
            finally:
                s.close()
        ts = [threading.Thread(target=ochir), threading.Thread(target=yarat)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(timeout=120)
        h = holat(O)
        berilgan = h["detal"].get(i1)
        if not (berilgan == 5.0 and h["holat"] != "delivered" and h["yetkazish"] == 1):
            yomon.append((natija, h))
    check("12m parallel o'chirish + yangi yuk (4 urinish): 5/10 topshirilgan buyurtma 'delivered' EMAS",
          not yomon, str(yomon[:1])[:400])


def kumulyativ():
    section("K. 5xx yo'q")
    r = req(C, "get", "/api/payments")
    check("K /api/payments 200", r.status_code == 200, r.status_code)
    r = req(C, "get", "/orders")
    check("K /orders 200", r.status_code == 200, r.status_code)


for _fn in (bolim_6, bolim_13, bolim_12, bolim_12_parallel, kumulyativ):
    try:
        _fn()
    except Exception as _e:                    # noqa: BLE001
        check(f"{_fn.__name__}: kutilmagan istisno", False, f"{type(_e).__name__}: {_e}")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
