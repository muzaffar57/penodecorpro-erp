#!/usr/bin/env python3
"""
test_buyurtma_himoya173.py — kech144 (zip 173): «Buyurtmalar» / «Qarzdorlar» — server himoyalari (audit 2-to'lqin va egasi QARORLARI 13.10).

NIMA UCHUN KERAK (O'LCHANGAN — `work/k173/probe_buyurtma.py`, asl kod = zip 172)
  K  «Qolganini chegirma qilish» (to'lovda qarz kechirish) — server to'lovdan keyin qolgan BUTUN qarzni kechirardi (`main.
     _tolov_qoldigini_chegirmaga`, chegarasiz): to'lov paneli boshqa buyurtma qarzini ko'rsatsa (probe V1 / V1b) yoki shu orada qarz
     o'zgarsa, oynada 100 000 tasdiqlanib 4 100 000 kechirilishi mumkin edi. Egasi QARORI «Faqat ko'rsatilgani»: so'rovda oynada
     tasdiqlangan summa (`kechirish`) SHART; to'lovdan keyin qoladigan qarz undan 0,5 so'mdan ko'p farq qilsa — 409
     `kechirish_ozgardi`, HECH NARSA saqlanmaydi.
  Y  Yangi buyurtma: server saqlab, javob yo'qolsa (502 — deploy almashinuvi) sahifa «saqlanmadi» derdi, 8 s dan keyin qayta bosish
     IKKINCHI buyurtma (va ikkinchi ombor chiqimi) yaratardi (probe V4: 6 → 7 → 8). Endi forma kaliti (`yaratish_kaliti`): shu kalit
     bilan buyurtma bor bo'lsa — o'zi qaytariladi (vaqtdan qat'i nazar, javobda `X-Takror: 1`), ombor qayta yechilmaydi.
  R  `GET /api/production/product-types` faqat «Mahsulot turlari: ko'rish» bilan edi — tayyor «Menejer» rolida 403: «MRP mahsuloti»
     tanlanmas, MRP buyurtmasini tahrirlash detal turini / qoplamasini / o'lchamlarini o'chirib saqlardi. Endi buyurtma yaratish /
     tahrirlash ruxsati ham yetadi (sotuv narxi qoidasi — buyurtma uchun kerak; tannarx `/xulosa` — avvalgidek yopiq).
  S  Sxema: `orders.yaratish_kaliti` (VARCHAR 64) va uning indeksi — eski bazaga ham qo'shiladi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (Y — parallel so'rovlar ham). Asl kodga (zip 172) qarshi QULAMAYDI —
yiqiladi.
ISHLATISH: python3 tools/test_buyurtma_himoya173.py      |      PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/...
"""
import os
import io
import sys
import tempfile
import threading
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "himoya173_test"
_T = tempfile.mkdtemp(prefix="himoya173_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'himoya173.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import database                                    # noqa: E402
from sqlalchemy import inspect as _sa_inspect, text as _sa_text   # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import UserRole, Inventory, Project, Order, Payment   # noqa: E402
from production_models import ProductType, Company   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: 1-korxona (admin, menejer, omborchi, «faqat ko'rish» roli), 2-korxona (admin); penoplast, loyihalar, MRP turi
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Himoya173 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "h173_admin", PAROL, UserRole.ADMIN, "H173 Admin", company_id=1)
    auth.create_user(s, "h173_men", PAROL, UserRole.MANAGER, "H173 Menejer", company_id=1)
    auth.create_user(s, "h173_omb", PAROL, UserRole.WAREHOUSE, "H173 Omborchi", company_id=1)
    auth.create_user(s, "h173_kor", PAROL, UserRole.MANAGER, "H173 Faqat ko'rish", company_id=1)
    auth.create_user(s, "h173_B_admin", PAROL, UserRole.ADMIN, "H173 B Admin", company_id=2)
PENO = Inventory(company_id=1, item_name="H173 Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
PENO_B = Inventory(company_id=2, item_name="H173 B Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500000,
                   volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
PRJ = Project(company_id=1, client_name="H173 Mijoz", project_name="H173 loyiha", total_budget=0, total_paid=0)
PRJ_B = Project(company_id=2, client_name="H173 B Mijoz", project_name="H173 B loyiha", total_budget=0, total_paid=0)
PT = ProductType(company_id=1, name="H173 Travertin", unit="m²", input_template="area_2d", pricing_formula="per_area",
                 supports_coating=True, coating_price_multiplier=2, is_active=True)
PT_B = ProductType(company_id=2, name="H173 B Kley", unit="kg", input_template="quantity_only", pricing_formula="fixed_price",
                   fixed_unit_price=1000, is_active=True)
s.add_all([PENO, PENO_B, PRJ, PRJ_B, PT, PT_B])
s.commit()
PENO_ID, PENO_B_ID, PID, PID_B, PT_ID, PT_B_ID = PENO.id, PENO_B.id, PRJ.id, PRJ_B.id, PT.id, PT_B.id
s.close()


def kirish(user):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (user, r.status_code, r.text[:200])
    return c


A = kirish("h173_admin")
AB = kirish("h173_B_admin")

# «Faqat ko'rish» roli: Buyurtmalar — faqat ko'rish (yaratish / tahrirlash yo'q)
_rol = js(A.post("/api/rollar", json={"nom": "H173 Faqat ko'rish", "ruxsatlar": {"buyurtma": ["korish"]}}))
_s = SessionLocal()
from models import User                            # noqa: E402
_kor_id = _s.query(User.id).filter(User.username == "h173_kor").scalar()
_s.close()
_rr = A.put(f"/api/users/{_kor_id}/rol", json={"rol_id": _rol.get("id")})
check("T0 tayyorgarlik: «faqat ko'rish» roli yaratildi va biriktirildi", bool(_rol.get("id")) and _rr.status_code == 200,
      (_rol, _rr.status_code, _rr.text[:200]))
MEN = kirish("h173_men")
OMB = kirish("h173_omb")
KOR = kirish("h173_kor")

_N = [0]


def buyurtma(narx, pid=None, c=None, **k):
    """Bitta panel detal (miqdor 1) — jami `narx`; `k` — tanaga qo'shimcha (yaratish_kaliti, notes …)."""
    _N[0] += 1
    t = {"project_id": pid or PID, "order_type": "product",
         "items": [{"name": f"H173 detal {_N[0]}", "category": "panel", "width": 50, "thickness": 5, "length": 1,
                    "quantity": 1, "unit_price": narx, "is_coated": False}]}
    t.update(k)
    return (c or A).post("/api/orders?confirm_shortage=true", json=t)


def holat(oid):
    d = SessionLocal()
    try:
        o = d.query(Order).filter(Order.id == oid).first()
        tl = [float(p.amount) for p in d.query(Payment).filter(Payment.order_id == oid).order_by(Payment.id).all()]
        return {"kelishilgan": float(o.agreed_amount or 0), "qarz": round(float(o.debt_amount or 0), 2), "izoh": o.notes or "",
                "tolovlar": tl}
    finally:
        d.close()


def tolov(oid, summa, write_off=None, kechirish=None, c=None, **tana):
    p = {}
    if write_off is not None:
        p["write_off_remainder"] = "true" if write_off else "false"
    if kechirish is not None:
        p["kechirish"] = str(kechirish)
    t = {"order_id": oid, "amount": summa, "payment_type": "partial", "payment_method": "naqd"}
    t.update(tana)
    return (c or A).post("/api/payments", params=p or None, json=t)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. To'lovda qarz kechirish — faqat oynada tasdiqlangan summa (egasi QARORI 13.10 «Faqat ko'rsatilgani»)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = buyurtma(100_000)
o1 = js(r).get("id")
check("K0 fikstura: 100 000 lik buyurtma", r.status_code == 200 and o1 and holat(o1)["qarz"] == 100_000, (r.status_code, r.text[:200]))

r = tolov(o1, 30_000, write_off=True)
h = holat(o1)
check("K1 belgi bor, `kechirish` YO'Q → 400 «Kechiriladigan summa ko'rsatilmagan …», hech narsa saqlanmadi",
      r.status_code == 400 and "Kechiriladigan summa ko'rsatilmagan" in str(js(r).get("detail"))
      and h["tolovlar"] == [] and h["kelishilgan"] == 100_000 and "[WRITEOFF:" not in h["izoh"], (r.status_code, r.text[:300], h))

_yomon = {}
for q in ("abc", "-5", "inf", "nan", "1e20", "5;6", "  "):
    rr = tolov(o1, 30_000, write_off=True, kechirish=q)
    _yomon[q] = (rr.status_code, str(js(rr).get("detail"))[:80])
h = holat(o1)
check("K2 noto'g'ri `kechirish` (matn / manfiy / inf / nan / 1e20 / bo'sh) → 400, to'lov YO'Q",
      all(v[0] == 400 for v in _yomon.values()) and h["tolovlar"] == [], (_yomon, h))

r = tolov(o1, 30_000, write_off=True, kechirish=50_000)
d = js(r).get("detail") or {}
h = holat(o1)
check("K3 oynada 50 000, aslida 70 000 qoladi → 409 `kechirish_ozgardi` (qoladi 70 000, kutilgan 50 000), HECH NARSA saqlanmadi",
      r.status_code == 409 and isinstance(d, dict) and d.get("type") == "kechirish_ozgardi"
      and abs(float(d.get("qoladi", 0)) - 70_000) < 0.01 and abs(float(d.get("kutilgan", 0)) - 50_000) < 0.01
      and h["tolovlar"] == [] and h["kelishilgan"] == 100_000 and "[WRITEOFF:" not in h["izoh"], (r.status_code, r.text[:400], h))
check("K3b xabar oddiy gap: ikkala summa ajratgich bilan, «Hech narsa saqlanmadi»",
      isinstance(d, dict) and "70 000" in str(d.get("message")) and "50 000" in str(d.get("message"))
      and "Hech narsa saqlanmadi" in str(d.get("message")), d)

r = tolov(o1, 30_000, write_off=True, kechirish="70000.3")
h = holat(o1)
wo = js(r).get("write_off") or {}
check("K4 0,5 so'm ichida (70 000.3 ~ 70 000) → 200: to'lov 30 000, kechirilgan 70 000, qarz 0, kelishilgan 30 000",
      r.status_code == 200 and abs(float(wo.get("amount") or 0) - 70_000) < 0.01 and h["tolovlar"] == [30_000.0]
      and h["qarz"] == 0 and abs(h["kelishilgan"] - 30_000) < 0.01 and "[WRITEOFF:" in h["izoh"], (r.status_code, r.text[:300], h))

# K5 — sahifa qarzni 100 000 deb ko'rsatgan (kechirish = 100 000 − 40 000 = 60 000); shu orada boshqa to'lov 20 000 yozilgan
o2 = js(buyurtma(100_000)).get("id")
r0 = tolov(o2, 20_000)
r = tolov(o2, 40_000, write_off=True, kechirish=60_000)
h = holat(o2)
check("K5 shu orada boshqa to'lov (20 000) yozilgan: oynada 60 000, aslida 40 000 qoladi → 409, ikkinchi to'lov YO'Q, kechirish YO'Q",
      r0.status_code == 200 and r.status_code == 409 and (js(r).get("detail") or {}).get("type") == "kechirish_ozgardi"
      and h["tolovlar"] == [20_000.0] and h["kelishilgan"] == 100_000, (r0.status_code, r.status_code, r.text[:300], h))
r = tolov(o2, 40_000, write_off=True, kechirish=40_000)
h = holat(o2)
check("K5b yangilangan qarz bilan (40 000) → 200: kechirilgan 40 000, qarz 0",
      r.status_code == 200 and abs(float((js(r).get("write_off") or {}).get("amount") or 0) - 40_000) < 0.01 and h["qarz"] == 0,
      (r.status_code, r.text[:300], h))

o3 = js(buyurtma(50_000)).get("id")
r = tolov(o3, 50_000, write_off=True, kechirish=0)
h = holat(o3)
check("K6 to'lov qarzni to'liq yopadi, kechirish 0 → 200, kechirish yo'q, qarz 0",
      r.status_code == 200 and not (js(r).get("write_off") or {}).get("amount") and h["qarz"] == 0 and h["kelishilgan"] == 50_000,
      (r.status_code, r.text[:300], h))

o4 = js(buyurtma(50_000)).get("id")
r = tolov(o4, 40_000, write_off=True, kechirish=0)
h = holat(o4)
check("K7 kechirish 0 tasdiqlangan, lekin 10 000 qoladi → 409 (jim kechirilmaydi), to'lov YO'Q",
      r.status_code == 409 and (js(r).get("detail") or {}).get("type") == "kechirish_ozgardi" and h["tolovlar"] == [],
      (r.status_code, r.text[:300], h))

o5 = js(buyurtma(100_000.4)).get("id")
r = tolov(o5, 100_000, write_off=True, kechirish=0)
h = holat(o5)
check("K8 tiyin qoldig'i 0.40 (qarz emas — 0,5 bardosh), kechirish 0 → 200",
      r.status_code == 200 and h["tolovlar"] == [100_000.0], (r.status_code, r.text[:300], h))

o6 = js(buyurtma(80_000)).get("id")
r = tolov(o6, 30_000, write_off=False, kechirish=999)
h = holat(o6)
check("K9 belgisiz (`write_off_remainder=false`) — `kechirish` e'tiborsiz: oddiy to'lov, kechirish YO'Q",
      r.status_code == 200 and h["tolovlar"] == [30_000.0] and h["qarz"] == 50_000 and "[WRITEOFF:" not in h["izoh"],
      (r.status_code, r.text[:300], h))

o7 = js(buyurtma(90_000)).get("id")
r1 = tolov(o7, 60_000, write_off=True, kechirish=30_000)
r2 = tolov(o7, 60_000, write_off=True, kechirish=30_000)
h = holat(o7)
check("K10 ikki marta yuborish (8 s ichida, javob yo'qolgan): ikkinchisi takror (`duplicate`), 409 EMAS, BITTA to'lov, bitta kechirish",
      r1.status_code == 200 and r2.status_code == 200 and js(r2).get("duplicate") is True and h["tolovlar"] == [60_000.0]
      and h["qarz"] == 0 and h["izoh"].count("[WRITEOFF:") == 1, (r1.status_code, r2.status_code, r2.text[:300], h))

o8 = js(buyurtma(50_000)).get("id")
r = tolov(o8, 60_000, write_off=True, kechirish=0)
d = js(r).get("detail") or {}
check("K11 qarzdan ko'p + belgi: avval 409 `overpayment_warning` (kechirish xatosi EMAS)",
      r.status_code == 409 and isinstance(d, dict) and d.get("type") == "overpayment_warning", (r.status_code, r.text[:300]))
r = tolov(o8, 60_000, write_off=True, kechirish=0, confirm_overpay=True)
h = holat(o8)
check("K11b tasdiqlangan ortiqcha to'lov + kechirish 0 → 200 (kechiriladigan qarz yo'q)",
      r.status_code == 200 and h["tolovlar"] == [60_000.0] and "[WRITEOFF:" not in h["izoh"], (r.status_code, r.text[:300], h))

r = tolov(o1 + 100_000, 10_000, write_off=True, kechirish=0)
check("K12 yo'q buyurtma → 404 (kechirish tekshiruvi buyurtma topilgandan keyin)", r.status_code == 404, (r.status_code, r.text[:200]))

o9 = js(buyurtma(70_000, pid=PID_B, c=AB)).get("id")
r = tolov(o9, 10_000, write_off=True, kechirish=60_000, c=A)
h = holat(o9)
check("K13 boshqa korxona buyurtmasi → 404, hech narsa yozilmadi", r.status_code == 404 and h["tolovlar"] == [], (r.status_code, h))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Y. Yangi buyurtma — forma kaliti (`yaratish_kaliti`): javob yo'qolib qayta yuborilsa takror yaratilmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def soni(cid=1):
    d = SessionLocal()
    try:
        return d.query(Order).filter(Order.company_id == cid).count()
    finally:
        d.close()


def zaxira(iid):
    d = SessionLocal()
    try:
        return float(d.query(Inventory.stock_quantity).filter(Inventory.id == iid).scalar())
    finally:
        d.close()


K1 = "h173Kalit_0001-abcdef"
n0, z0 = soni(), zaxira(PENO_ID)
r1 = buyurtma(120_000, yaratish_kaliti=K1)
n1, z1 = soni(), zaxira(PENO_ID)
id1 = js(r1).get("id")
check("Y1 kalit bilan yaratish → 200, sarlavhada `X-Takror` YO'Q, bitta buyurtma, penoplast yechildi",
      r1.status_code == 200 and id1 and r1.headers.get("X-Takror") is None and n1 == n0 + 1 and z1 < z0, (r1.status_code, r1.text[:200], n0, n1, z0, z1))
d = SessionLocal()
_kal = (d.query(Order.yaratish_kaliti).filter(Order.id == id1).scalar()
        if hasattr(Order, "yaratish_kaliti") else None)       # asl kodda ustun yo'q — yiqiladi (qulamaydi)
d.close()
check("Y1b kalit bazada saqlandi", _kal == K1, _kal)

r2 = buyurtma(999_000, yaratish_kaliti=K1, notes="boshqa tana — o'sha forma")
n2, z2 = soni(), zaxira(PENO_ID)
check("Y2 o'sha kalit (tana boshqa ham) → 200, O'SHA buyurtma, `X-Takror: 1`, yangi buyurtma YO'Q, ombor qayta yechilmadi",
      r2.status_code == 200 and js(r2).get("id") == id1 and r2.headers.get("X-Takror") == "1" and n2 == n1
      and abs(z2 - z1) < 1e-9, (r2.status_code, js(r2).get("id"), id1, r2.headers.get("X-Takror"), n1, n2, z1, z2))
d = SessionLocal()
_o1 = d.query(Order).filter(Order.id == id1).first()
_jami1 = float(_o1.total_amount or 0)
d.close()
check("Y2b mavjud buyurtma o'zgarmadi (jami 120 000 — ikkinchi tana yozilmadi)", abs(_jami1 - 120_000) < 0.01, _jami1)

nb0, zb0 = soni(2), zaxira(PENO_B_ID)
r3 = buyurtma(120_000, pid=PID_B, c=AB, yaratish_kaliti=K1)
check("Y3 boshqa korxonada o'sha kalit → YANGI buyurtma (kalit korxona ichida), `X-Takror` yo'q",
      r3.status_code == 200 and js(r3).get("id") not in (None, id1) and r3.headers.get("X-Takror") is None and soni(2) == nb0 + 1
      and zaxira(PENO_B_ID) < zb0, (r3.status_code, r3.text[:200]))

n3 = soni()
r4 = buyurtma(130_000)
r5 = buyurtma(140_000)
check("Y4 kalitsiz (eski mijozlar / API) — avvalgidek: ikki xil tana → ikki buyurtma",
      r4.status_code == 200 and r5.status_code == 200 and js(r4).get("id") != js(r5).get("id") and soni() == n3 + 2,
      (r4.status_code, r5.status_code))

_yk = {}
for k in ("qisqa7x", "a b c d e f g h", "x" * 65, "kalit/../../etc", "калит12345", "kalit'or'1=1"):
    rr = buyurtma(10_000, yaratish_kaliti=k)
    _yk[k[:20]] = rr.status_code
check("Y5 noto'g'ri kalit (8 dan qisqa, bo'shliq, 64 dan uzun, belgilar, kirill) → 422, buyurtma YO'Q",
      all(v == 422 for v in _yk.values()) and soni() == n3 + 2, (_yk, soni(), n3 + 2))

K6 = "h173Kalit_0006"
r6 = buyurtma(60_000, yaratish_kaliti=K6)
id6 = js(r6).get("id")
d = SessionLocal()
d.query(Order).filter(Order.id == id6).update({"is_deleted": True})
d.commit()
d.close()
r7 = buyurtma(60_000, yaratish_kaliti=K6, notes="o'chirilgandan keyin")
check("Y6 kalitli buyurtma O'CHIRILGAN bo'lsa — o'sha kalit bilan YANGI buyurtma (o'chirilgani qaytarilmaydi)",
      r6.status_code == 200 and r7.status_code == 200 and js(r7).get("id") not in (None, id6) and r7.headers.get("X-Takror") is None,
      (r6.status_code, r7.status_code, js(r7).get("id"), id6))

K8 = "h173Kalit_0008"
r8 = buyurtma(70_000, yaratish_kaliti=K8, is_draft=True)
r9 = buyurtma(70_000, yaratish_kaliti=K8, is_draft=True)
check("Y7 qoralama ham: o'sha kalit → o'sha qoralama, `X-Takror: 1`",
      r8.status_code == 200 and r9.status_code == 200 and js(r9).get("id") == js(r8).get("id") and r9.headers.get("X-Takror") == "1",
      (r8.status_code, r9.status_code))

if PG_URL:
    K9 = "h173Kalit_0009_parallel"
    n9 = soni()
    natija = []

    def _ish():
        c = kirish("h173_admin")
        rr = buyurtma(77_000, c=c, yaratish_kaliti=K9)
        natija.append((rr.status_code, js(rr).get("id"), rr.headers.get("X-Takror")))

    _ip = [threading.Thread(target=_ish) for _ in range(3)]
    for t in _ip:
        t.start()
    for t in _ip:
        t.join(60)
    check("Y8 [parallel] o'sha kalit bilan 3 ta bir vaqtdagi so'rov → BITTA buyurtma, hammasi o'sha id",
          len(natija) == 3 and all(x[0] == 200 for x in natija) and len({x[1] for x in natija}) == 1 and soni() == n9 + 1,
          (natija, soni(), n9))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. MRP mahsulot turlari ro'yxati — buyurtma yaratish / tahrirlash ruxsati ham yetadi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = MEN.get("/api/production/product-types")
check("R1 Menejer (Buyurtmalar: yaratish / tahrirlash) → 200, korxona turi ro'yxatda (asl: 403 — «MRP mahsuloti» tanlanmasdi)",
      r.status_code == 200 and any(x.get("id") == PT_ID for x in js(r) or []), (r.status_code, r.text[:200]))
check("R1b javobda sotuv qoidasi (kiritish shakli, qoplama koeffitsiyenti) bor — tahrirda tiklash uchun",
      r.status_code == 200 and any(x.get("id") == PT_ID and x.get("input_template") == "area_2d" and x.get("supports_coating") is True
                                   for x in js(r) or []), r.text[:300])
r = OMB.get("/api/production/product-types")
check("R2 Omborchi (Mahsulot turlari: ko'rish) → 200 (avvalgidek)", r.status_code == 200, r.status_code)
r = KOR.get("/api/production/product-types")
check("R3 faqat «Buyurtmalar: ko'rish» → 403 (yaratish / tahrirlash yo'q)", r.status_code == 403, (r.status_code, r.text[:200]))
r = MEN.get("/api/production/product-types/xulosa")
check("R4 Menejer — tannarx xulosasi (`/xulosa`) avvalgidek YOPIQ → 403", r.status_code == 403, r.status_code)
r = AB.get("/api/production/product-types")
check("R5 boshqa korxona faqat o'z turlarini ko'radi", r.status_code == 200 and {x.get("id") for x in js(r)} == {PT_B_ID},
      (r.status_code, r.text[:200]))
r = MEN.post("/api/production/product-types", json={"name": "H173 menejer turi", "unit": "dona", "input_template": "quantity_only",
                                                     "pricing_formula": "fixed_price", "fixed_unit_price": 1})
check("R6 Menejer tur YARATA olmaydi (faqat o'qish kengaydi) → 403", r.status_code == 403, (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Sxema — orders.yaratish_kaliti (eski bazaga ham)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ins = _sa_inspect(engine)
_ust = {c["name"]: c for c in _ins.get_columns("orders")}
check("S1 `orders.yaratish_kaliti` ustuni bor (64 belgigacha, NULL mumkin)",
      "yaratish_kaliti" in _ust and _ust["yaratish_kaliti"].get("nullable") is True
      and getattr(_ust["yaratish_kaliti"]["type"], "length", 64) in (64, None), _ust.get("yaratish_kaliti"))
_idx = [i for i in _ins.get_indexes("orders") if i.get("column_names") == ["yaratish_kaliti"]]
check("S2 `yaratish_kaliti` bo'yicha indeks bor", bool(_idx), _ins.get_indexes("orders"))
# eski baza: ustun va indeks yo'q → `sync_missing_columns` + `add_missing_indexes` qo'shadi
try:
    with engine.begin() as _c:
        for _i in _idx:
            _c.execute(_sa_text(f"DROP INDEX IF EXISTS {_i['name']}"))
        _c.execute(_sa_text("ALTER TABLE orders DROP COLUMN yaratish_kaliti"))
except Exception as _e:                    # noqa: BLE001 — asl kodda ustun yo'q (S1 allaqachon yiqilgan)
    print(f"  (ustunni o'chirib bo'lmadi: {type(_e).__name__})")
with contextlib.redirect_stdout(io.StringIO()):
    database.sync_missing_columns()
    database.add_missing_indexes()
_ins = _sa_inspect(engine)
_ust2 = {c["name"] for c in _ins.get_columns("orders")}
_idx2 = [i for i in _ins.get_indexes("orders") if i.get("column_names") == ["yaratish_kaliti"]]
check("S3 eski baza (ustun va indeks yo'q) — ishga tushishda qo'shiladi", "yaratish_kaliti" in _ust2 and bool(_idx2),
      (sorted(_ust2)[:5], _idx2))
r = buyurtma(15_000, yaratish_kaliti="h173Kalit_0010")
r2 = buyurtma(15_000, yaratish_kaliti="h173Kalit_0010")
check("S4 qo'shilgan ustun bilan kalit ishlaydi", r.status_code == 200 and js(r2).get("id") == js(r).get("id")
      and r2.headers.get("X-Takror") == "1", (r.status_code, r2.status_code))
if PG_URL:
    _sx = database.sxema_farqlari()
    check("S5 [PG] baza tuzilishi kod bilan mos (zip 172 sxema tekshiruvi — farq 0)", not (_sx or {}).get("farqlar"), _sx)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
