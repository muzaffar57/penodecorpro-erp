#!/usr/bin/env python3
"""
test_ord066_tuzatish.py — kech127 (zip 150): `main` (production) dagi ORD-066-1 LOY XATOSINING bir martalik tuzatishi
(`main._migrate_ord066_loy_xatosi`; egasi QARORI 07.10, tugmali: loy 500 kg, qoldiq — ombor yozuvlari bo'yicha, «Toza tuzatish»).

NIMA UCHUN KERAK
  Xodim ORD-066-1 loy rejasiga 500 o'rniga 500 000 kg yozgan («omborda yetishmaydi» oynasini tasdiqlab). Eski `main` kodi loy
  xomashyosini 0 da QIRQARDI, harakatlar esa to'liq miqdor bilan yozilgan (Kroshka extra 261 905 kg …): qoldiq 0, «tugash
  bashorati» va «eng ko'p ishlatilgan xomashyo» yolg'on. Ilova ichidan tuzatish (loy 500 + «Qoldiqni tuzatish») katta
  «qaytarildi» / «tuzatish» yozuvlarini qoldirardi (O'LCHANGAN — `work/natija/k126/z1924/fix.txt`). Shuning uchun — bir martalik,
  qat'iy shartli ma'lumot tuzatishi.
TALAB (har biri o'lchanadi):
  T  tuzatish: shu buyurtmaning har loy harakati miqdori × yangi / eski (narxi saqlanadi); reja `yangi_kg` (ustun va eski izoh
     belgisi); harakatlari bor materiallar qoldig'i = ombor yozuvlari balansi (eski kod qirqib yo'qotgan qism tiklanadi) va
     mustaqil hisoblangan kutilgan qiymatga teng; boshqa material, boshqa buyurtma harakatlari, shu buyurtmaning penoplast
     harakati (loy emas), boshqa korxona — TEGILMAYDI;
     Faoliyat jurnalida yozuv; natija `tuzatildi`.
  I  ikkinchi chaqiruv — hech narsa o'zgarmaydi (`reja_boshqa`), hamma jadval AYNAN.
  G  SHARTLAR (har biri alohida buyurtmada, hech narsa o'zgarmaydi): reja boshqa; «Tayyor»; haqiqiy loy kiritilgan; o'chirilgan;
     shu buyurtmada boshqa loy harakati (qaytarish); loy harakati kirim; loy harakati yo'q; buyurtma yo'q; boshqa korxona.
  S  standart parametrlar `ORD066_TUZATISH` (korxona 1, ORD-066-1, 500 000 → 500) — egasi qarori; ishga tushishda chaqiriladi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16.
ISHLATISH: python3 tools/test_ord066_tuzatish.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "ord066_test"
_T = tempfile.mkdtemp(prefix="ord066_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'ord066_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime, timedelta           # noqa: E402

_import_chiqish = io.StringIO()
with contextlib.redirect_stdout(_import_chiqish):
    import main                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (Order, OrderStatus, OrderType, Project, Inventory, InventoryMovement,   # noqa: E402
                    ActivityLog)
from production_models import Company              # noqa: E402

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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


FN = getattr(main, "_migrate_ord066_loy_xatosi", None)
PARAM = getattr(main, "ORD066_TUZATISH", None)


def tuzat(**kw):
    """Asl kodda (funksiya yo'q) — None (test yiqiladi, qulamaydi)."""
    if FN is None:
        return None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return FN(**kw)
    except Exception as e:                 # noqa: BLE001
        return {"holat": "istisno", "xato": repr(e)}


def holat_ol(cid=None):
    """Taqqoslash uchun to'liq holat: materiallar qoldig'i, harakatlar, buyurtmalar (reja, izoh), jurnal soni."""
    s = SessionLocal()
    try:
        qi = s.query(Inventory)
        qm = s.query(InventoryMovement)
        qo = s.query(Order)
        if cid is not None:
            qi = qi.filter(Inventory.company_id == cid)
            qm = qm.filter(InventoryMovement.company_id == cid)
            qo = qo.filter(Order.company_id == cid)
        return {
            "inv": sorted((i.id, round(float(i.stock_quantity or 0), 9)) for i in qi.all()),
            "mov": sorted((m.id, m.movement_type, round(float(m.quantity or 0), 9), m.reason, m.order_id,
                           None if m.unit_cost is None else round(float(m.unit_cost), 4)) for m in qm.all()),
            "ord": sorted((o.id, None if o.planned_loy_kg is None else float(o.planned_loy_kg), o.notes or "",
                           o.status.value, o.actual_loy_kg) for o in qo.all()),
            "log": (s.query(ActivityLog).filter(ActivityLog.company_id == cid) if cid is not None
                    else s.query(ActivityLog)).count(),
        }
    finally:
        s.close()


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
# FIKSTURA — production holati shaklida: 3 loy xomashyosi (A, B, C) + bog'liq bo'lmagan material W; kirimlar; ORD-066-1
# (reja 500 000, harakatlar to'liq miqdor, qoldiq eski kod kabi 0 da qirqilgan); keyin boshqa buyurtma loyi (qirqilgan) va
# kirim; boshqa korxonada ham shu raqamli buyurtma.
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ord066 boshqa korxona"))
    s.commit()
T0 = datetime(2026, 10, 1, 8, 0, 0)


def material(cid, nom, narx):
    m = Inventory(company_id=cid, item_name=nom, unit="kg", stock_quantity=0.0, price_per_unit=narx, min_stock=0,
                  category="Kimyoviy qo'shimchalar")
    s.add(m)
    s.flush()
    return m


def harakat(cid, inv, tur, miqdor, sabab, order_id=None, narx=None, vaqt=None):
    h = InventoryMovement(company_id=cid, inventory_id=inv.id, item_name=inv.item_name, movement_type=tur,
                          quantity=miqdor, unit=inv.unit, reason=sabab, order_id=order_id, unit_cost=narx,
                          created_at=vaqt or T0)
    s.add(h)
    s.flush()
    return h


def buyurtma(cid, raqam, reja, holat=OrderStatus.IN_PROGRESS, haqiqiy=None, ochirilgan=False):
    p = Project(company_id=cid, client_name=f"Mijoz {raqam}", project_name=f"Loyiha {raqam}")
    s.add(p)
    s.flush()
    o = Order(company_id=cid, project_id=p.id, order_number=raqam, order_type=OrderType.SERVICE, status=holat,
              planned_loy_kg=reja, notes=f"planned_loy={reja}", actual_loy_kg=haqiqiy, is_deleted=ochirilgan,
              total_amount=1000000, agreed_amount=1000000)
    s.add(o)
    s.flush()
    return o


A = material(1, "Ord066 Akril", 19000)
B = material(1, "Ord066 Kroshka", 645)
C = material(1, "Ord066 Mel", 522)
W = material(1, "Ord066 Boshqa", 1000)
# kirimlar: A 300, B 2500, C 200, W 50
for m, q in ((A, 300.0), (B, 2500.0), (C, 200.0), (W, 50.0)):
    harakat(1, m, "in", q, "Yetkazib beruvchi: sinov", narx=m.price_per_unit, vaqt=T0)
# boshqa buyurtma loyi (oddiy, qirqilmagan): A 30, B 200, C 20
O1 = buyurtma(1, "ORD-060-1", 300.0)
for m, q in ((A, 30.0), (B, 200.0), (C, 20.0)):
    harakat(1, m, "out", q, "Buyurtma ORD-060-1 (loy)", order_id=O1.id, narx=m.price_per_unit, vaqt=T0 + timedelta(days=1))
# ORD-066-1 — reja 500 000: A 42 857.142857…, B 261 904.761904…, C 23 809.523809… (eski kod qirqgan — qoldiq 0)
O66 = buyurtma(1, "ORD-066-1", 500000.0)
X66 = {A.id: 42857.142857142855, B.id: 261904.76190476192, C.id: 23809.52380952381}
H66 = [harakat(1, m, "out", X66[m.id], "Buyurtma ORD-066-1 (loy)", order_id=O66.id, narx=m.price_per_unit,
               vaqt=T0 + timedelta(days=4)) for m in (A, B, C)]
# shu buyurtmaning PENOPLAST harakati (loy EMAS — production da ham bor: «Buyurtma ORD-066-1 — Penoplast», 2.892… dona) — tegilmaydi
P = material(1, "Ord066 Penoplast 14P", 400000)
harakat(1, P, "in", 10.0, "Yetkazib beruvchi: sinov", narx=400000, vaqt=T0)
HP = harakat(1, P, "out", 2.892083571428571, "Buyurtma ORD-066-1 — Penoplast", order_id=O66.id, narx=400000,
             vaqt=T0 + timedelta(days=4))
P.stock_quantity = 10.0 - 2.892083571428571
# keyin yana bir buyurtma loyi (qoldiq 0 da — eski kod qirqgan): A 34.2857, B 209.5238, C 19.0476
O2 = buyurtma(1, "ORD-045-2", 400.0)
X2 = {A.id: 34.285714285714285, B.id: 209.52380952380952, C.id: 19.047619047619047}
for m in (A, B, C):
    harakat(1, m, "out", X2[m.id], "Buyurtma ORD-045-2 (loy)", order_id=O2.id, narx=m.price_per_unit,
            vaqt=T0 + timedelta(days=5))
# so'ng A ga kirim 165
harakat(1, A, "in", 165.0, "Yetkazib beruvchi: sinov", narx=19000, vaqt=T0 + timedelta(days=6))
# eski kod qoldig'i (qirqilgan): A 165 (0 → 0 → +165), B 0, C 0; W 50
A.stock_quantity, B.stock_quantity, C.stock_quantity, W.stock_quantity = 165.0, 0.0, 0.0, 50.0
# boshqa korxona — xuddi shu raqam va reja (tegilmasligi kerak)
A2 = material(2, "Ord066 Akril (B)", 19000)
harakat(2, A2, "in", 100.0, "Yetkazib beruvchi: sinov", narx=19000)
O66b = buyurtma(2, "ORD-066-1", 500000.0)
harakat(2, A2, "out", 42857.142857142855, "Buyurtma ORD-066-1 (loy)", order_id=O66b.id, narx=19000)
A2.stock_quantity = 0.0
s.commit()
ID = {"A": A.id, "B": B.id, "C": C.id, "W": W.id, "P": P.id, "A2": A2.id, "O66": O66.id, "O66b": O66b.id, "HP": HP.id}
H66_ID = [h.id for h in H66]
s.close()

K = 500.0 / 500000.0
KUT = {  # mustaqil hisob: kirim − boshqa buyurtmalar − ORD-066-1 × 1/1000 (+ keyingi kirim)
    "A": 300.0 - 30.0 - X66[ID["A"]] * K - X2[ID["A"]] + 165.0,
    "B": 2500.0 - 200.0 - X66[ID["B"]] * K - X2[ID["B"]],
    "C": 200.0 - 20.0 - X66[ID["C"]] * K - X2[ID["C"]],
}

section("S. Standart parametrlar va ishga tushish")
check("S1 `main.ORD066_TUZATISH` — korxona 1, ORD-066-1, 500 000 → 500 (egasi qarori)",
      PARAM == {"company_id": 1, "raqam": "ORD-066-1", "eski_kg": 500000.0, "yangi_kg": 500.0}, PARAM)
check("S2 `main._migrate_ord066_loy_xatosi` mavjud va ishga tushishda chaqiriladi (bo'sh bazada — buyurtma yo'q)",
      FN is not None and "_migrate_ord066_loy_xatosi()" in open(os.path.join(ROOT, "main.py"), encoding="utf-8").read(),
      FN)

section("T. Tuzatish (korxona 1, ORD-066-1)")
oldin2 = holat_ol(2)
oldin1 = holat_ol(1)
nat = tuzat()
check("T1 natija `tuzatildi`, 3 harakat", isinstance(nat, dict) and nat.get("holat") == "tuzatildi"
      and nat.get("harakatlar") == 3, nat)
s = SessionLocal()
try:
    hh = {h.id: h for h in s.query(InventoryMovement).filter(InventoryMovement.id.in_(H66_ID)).all()}
    t2 = [(i, float(hh[i].quantity), X66[hh[i].inventory_id] * K) for i in H66_ID if i in hh]
    check("T2 ORD-066-1 loy harakatlari × 1/1000 (A 42.857…, B 261.904…, C 23.809…)",
          len(t2) == 3 and all(abs(a - b) < 1e-9 for _, a, b in t2), t2)
    check("T3 harakat narxi (unit_cost) va turi o'zgarmadi",
          all(hh[i].movement_type == "out" and float(hh[i].unit_cost) in (19000.0, 645.0, 522.0) for i in H66_ID), "")
    o = s.query(Order).filter(Order.id == ID["O66"]).first()
    check("T4 reja 500 kg (ustun), izoh belgisi «planned_loy=500.0», 500000 izi yo'q",
          float(o.planned_loy_kg) == 500.0 and "planned_loy=500.0" in (o.notes or "") and "500000" not in (o.notes or ""),
          (o.planned_loy_kg, o.notes))
    inv = {k: float(s.query(Inventory).filter(Inventory.id == ID[k]).first().stock_quantity) for k in ("A", "B", "C", "W")}
    check(f"T5 qoldiq — mustaqil hisob bilan teng (A ≈ {KUT['A']:.2f}, B ≈ {KUT['B']:.2f}, C ≈ {KUT['C']:.2f})",
          all(abs(inv[k] - KUT[k]) < 1e-6 for k in ("A", "B", "C")), (inv, KUT))
    from sqlalchemy import func, case
    bal = {}
    for k in ("A", "B", "C", "W"):
        bal[k] = float(s.query(func.coalesce(func.sum(case((InventoryMovement.movement_type == "in", InventoryMovement.quantity),
                                                            else_=-InventoryMovement.quantity)), 0.0))
                       .filter(InventoryMovement.inventory_id == ID[k]).scalar())
    check("T6 qoldiq = ombor yozuvlari balansi (A, B, C)", all(abs(inv[k] - bal[k]) < 1e-6 for k in ("A", "B", "C")),
          (inv, bal))
    check("T7 bog'liq bo'lmagan material W — qoldiq 50, harakatlari o'zgarmadi", inv["W"] == 50.0, inv["W"])
    _hp = s.query(InventoryMovement).filter(InventoryMovement.id == ID["HP"]).first()
    _pq = float(s.query(Inventory).filter(Inventory.id == ID["P"]).first().stock_quantity)
    check("T11 shu buyurtmaning PENOPLAST harakati (loy emas) — miqdor 2.892…, penoplast qoldig'i 7.107… — o'zgarmadi",
          abs(float(_hp.quantity) - 2.892083571428571) < 1e-12 and abs(_pq - (10.0 - 2.892083571428571)) < 1e-12,
          (float(_hp.quantity), _pq))
    jur = (s.query(ActivityLog).filter(ActivityLog.company_id == 1, ActivityLog.action == "loy_tuzatish",
                                       ActivityLog.entity_type == "order", ActivityLog.entity_id == ID["O66"]).all())
    check("T8 Faoliyat jurnali: «loy_tuzatish» (ORD-066-1, 500 000 → 500 kg, material qoldiqlari)",
          len(jur) == 1 and "500 000" in (jur[0].old_value or "") and "500 kg" in (jur[0].new_value or "")
          and "Ord066 Kroshka" in (jur[0].new_value or ""), [(j.old_value, j.new_value) for j in jur])
finally:
    s.close()
keyin1 = holat_ol(1)
_boshqa_mov = [m for m in oldin1["mov"] if m[0] not in H66_ID]
check("T9 boshqa buyurtmalar harakatlari (ORD-060-1, ORD-045-2, kirimlar) — AYNAN",
      [m for m in keyin1["mov"] if m[0] not in H66_ID] == _boshqa_mov, "")
check("T10 boshqa korxona (2) — ORD-066-1, qoldiq, harakatlar AYNAN (reja 500 000 qoldi)", holat_ol(2) == oldin2, "")

section("I. Ikkinchi chaqiruv — hech narsa o'zgarmaydi")
oldin_i = holat_ol()
nat2 = tuzat()
check("I1 natija `reja_boshqa`", isinstance(nat2, dict) and nat2.get("holat") == "reja_boshqa", nat2)
check("I2 hamma jadval AYNAN (jurnal yozuvi ham qo'shilmadi)", holat_ol() == oldin_i, "")

section("G. Shartlar — mos kelmasa hech narsa o'zgarmaydi")


def shart_fiksturasi(raqam, reja=500000.0, holat=OrderStatus.IN_PROGRESS, haqiqiy=None, ochirilgan=False, harakatlar="oddiy"):
    ss = SessionLocal()
    try:
        global s
        s = ss
        m = material(1, f"G {raqam}", 1000)
        harakat(1, m, "in", 100.0, "Yetkazib beruvchi: sinov", narx=1000)
        o = buyurtma(1, raqam, reja, holat=holat, haqiqiy=haqiqiy, ochirilgan=ochirilgan)
        if harakatlar in ("oddiy", "qaytarish"):
            harakat(1, m, "out", 50000.0, f"Buyurtma {raqam} (loy)", order_id=o.id, narx=1000)
        if harakatlar == "qaytarish":
            harakat(1, m, "in", 49950.0, f"Buyurtma {raqam} bekor qilindi (loy qaytarildi)", order_id=o.id, narx=1000)
        if harakatlar == "kirim":
            harakat(1, m, "in", 50000.0, f"Buyurtma {raqam} (loy)", order_id=o.id, narx=1000)
        m.stock_quantity = 0.0
        ss.commit()
    finally:
        ss.close()


SHARTLAR = (
    ("G1 reja 400 000 (boshqa)", "ORD-G1-1", dict(reja=400000.0), "reja_boshqa"),
    ("G2 «Tayyor»", "ORD-G2-1", dict(holat=OrderStatus.READY), "holat_ozgargan"),
    ("G3 haqiqiy loy kiritilgan", "ORD-G3-1", dict(haqiqiy=480.0), "holat_ozgargan"),
    ("G4 o'chirilgan", "ORD-G4-1", dict(ochirilgan=True), "holat_ozgargan"),
    ("G5 shu buyurtmada loy qaytarish harakati bor", "ORD-G5-1", dict(harakatlar="qaytarish"), "harakat_boshqa"),
    ("G6 loy harakati — kirim", "ORD-G6-1", dict(harakatlar="kirim"), "harakat_boshqa"),
    ("G7 loy harakati yo'q", "ORD-G7-1", dict(harakatlar="yoq"), "harakat_boshqa"),
)
for nom, raqam, kw, kut in SHARTLAR:
    shart_fiksturasi(raqam, **kw)
    oldin_g = holat_ol()
    ng = tuzat(raqam=raqam)
    check(f"{nom} → `{kut}`, hech narsa o'zgarmadi", isinstance(ng, dict) and ng.get("holat") == kut
          and holat_ol() == oldin_g, (ng, holat_ol() == oldin_g))
oldin_g = holat_ol()
ng = tuzat(raqam="ORD-YOQ-1")
check("G8 buyurtma yo'q → `yoq`, hech narsa o'zgarmadi", isinstance(ng, dict) and ng.get("holat") == "yoq"
      and holat_ol() == oldin_g, ng)
ng = tuzat(korxona_id=3, raqam="ORD-066-1")
check("G9 boshqa korxona (3 — bunday buyurtma yo'q) → `yoq`", isinstance(ng, dict) and ng.get("holat") == "yoq", ng)

section("K. Boshqa korxonada (parametr bilan) — faqat o'sha korxona")
oldin1k = holat_ol(1)
nk = tuzat(korxona_id=2)
s = SessionLocal()
try:
    a2 = float(s.query(Inventory).filter(Inventory.id == ID["A2"]).first().stock_quantity)
    o2 = s.query(Order).filter(Order.id == ID["O66b"]).first()
finally:
    s.close()
check("K1 korxona 2: tuzatildi, A2 qoldig'i = 100 − 42.857… = 57.142…, reja 500",
      isinstance(nk, dict) and nk.get("holat") == "tuzatildi" and abs(a2 - (100.0 - 42.857142857142855)) < 1e-6
      and float(o2.planned_loy_kg) == 500.0, (nk, a2))
check("K2 korxona 1 — AYNAN", holat_ol(1) == oldin1k, "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  - " + f)
sys.exit(1 if FAIL else 0)
