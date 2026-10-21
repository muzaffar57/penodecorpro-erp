#!/usr/bin/env python3
"""
test_tm_minus_bekor197.py — kech153 (zip 197 «Minusni yopgan hodisani bekor qilish»; EGASI QARORI 21.10 03:3x «Ruxsat, hisob to'g'ri»,
QAYTA SO'RALMAYDI): minusni yopgan hodisa (brak taqdiri «Tuzatildi — o'sha joyiga» / brakdan yangi partiya, mijozdan qaytgan mahsulot, MRP
bandidan bo'shagan qoldiq) keyin bekor qilinsa (taqdir o'zgartirildi, qaytarish yozuvi o'chirildi) — qarzdor buyurtmaning o'sha qismi omborda
bor mahsulot bilan (o'sha narxda) qoplanadi; yetmasa — buyurtma yana qarzga qaytadi (keyingi mahsulot yopadi); «Tayyor» buyurtma o'zgarmaydi.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k197/probe197.py`, zip 196 kodi):
  P1 «Tuzatildi — joyiga» minusni yopdi, keyin arzon qo'shildi, taqdir → «Tashlandi»: partiyadan to'liq tannarx ayirilib 0 ga qirqildi,
  buyurtma tannarxi eski — saqlanish +3 000; P5 keyin qo'shilmagan — «mahsulot sotilgan …» degan noto'g'ri sabab bilan rad; P2 qaytgan
  mahsulot minusdagi partiyaga birlashib qarzni yopdi, birinchi qaytarish o'chirildi — +3 400; P3 qaytish yangi partiya bo'lib guruhdosh
  minusini KO'CHIRIB yopdi — +4 200.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1`.
Asl kodga (zip 196) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_tm_minus_bekor197.py
"""
import os
import io
import sys
import time
import json
import tempfile
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tm_minus_bekor197_test"
_T = tempfile.mkdtemp(prefix="tm197_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tm197.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Inventory, FinishedProduct, OrderItem, StockSource, ProductionStatus,   # noqa: E402
                    ReturnItem, BrakTaqdir, ActivityLog)
from production_models import ProductionOrder      # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def teng(a, b, eps=0.02):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


main._send_telegram = lambda *a, **k: True

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "tm197_admin", PAROL, UserRole.ADMIN, "TM197 Admin", company_id=1)
PRJ = Project(company_id=1, client_name="TM197 Mijoz", project_name="TM197 loyiha", total_budget=0, total_paid=0)
# penoplast: 1 blok = 1 m³; profil 1 m = 0,01 m³ → «Yana ishlab chiqarish» 1 m = narx / 100 (120 000 → 1 200; 20 000 → 200)
PENO = Inventory(company_id=1, item_name="TM197 PENO", unit="blok", stock_quantity=100000, min_stock=0, is_penoplast=True,
                 volume_per_unit=1, price_per_unit=120000, category="Penoplast")
s.add_all([PRJ, PENO])
s.commit()
PRJ_ID, PENO_ID = PRJ.id, PENO.id
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert A.post("/login", data={"username": "tm197_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)
_n = {"d": 0}


def narx(n):
    db_ishi(lambda s: setattr(s.get(Inventory, PENO_ID), "price_per_unit", n))


def yangi_tm(miqdor, nom, birlik, holat=ProductionStatus.READY, manba=StockSource.PRODUCED, sotuv=0.0):
    def f(s):
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=False, width=20, thickness=10,
                             quantity=miqdor, produced_quantity=max(miqdor, 0), unit="metr", unit_price=sotuv,
                             cost_price=max(miqdor, 0) * birlik, unit_cost_stable=birlik, source=manba,
                             penoplast_id=PENO_ID, unit_volume_m3=0.01, volume_m3=0.01 * max(miqdor, 0), production_status=holat,
                             reserved_quantity=0)
        s.add(fp)
        s.flush()
        return fp.id
    return db_ishi(f)


def detal(uz, fid, nom=None, narxi=20000):
    _n["d"] += 1                           # 8 s «takroriy yuborish» imzosi (nom, tur, soni) — har detal nomi noyob (nom berilmasa)
    return {"name": nom or f"TM197 detal {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": uz,
            "quantity": 1, "unit_price": narxi, "is_coated": False, "penoplast_id": PENO_ID, "finished_product_id": fid}


def buyurtma(*d):
    r = A.post("/api/orders?confirm_shortage=true", json={"project_id": PRJ_ID, "order_type": "product", "loy_kg": 0, "items": list(d)})
    return js(r).get("id")


def tm(fid):
    def f(s):
        x = s.get(FinishedProduct, fid) if fid else None
        return None if x is None else (round(float(x.quantity), 4), round(float(x.cost_price or 0), 2),
                                       round(float(x.unit_cost_stable or 0), 4))
    return db_ishi(f)


def band(fid):
    return db_ishi(lambda s: round(float(s.get(FinishedProduct, fid).reserved_quantity or 0), 4))


def detallar(oid):
    """[(id, tm, miqdor, birlik, qarz)] — id tartibida."""
    def f(s):
        return [(x.id, x.finished_product_id, float(x.length if (x.category or '') == 'profil' else x.quantity or 0),
                 round(float(x.fp_unit_cost or 0), 4), round(float(getattr(x, 'fp_qarz', None) or 0), 4))
                for x in s.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id)]
    return db_ishi(f)


def detal_id(oid):
    return detallar(oid)[0][0]


def qarz(oid):
    return round(sum(d[4] for d in detallar(oid)), 4)


def btannarx(oid):
    """Buyurtmaning tayyor mahsulot tannarxi: Σ detal birligi × miqdor (`calculate_order_profit` bilan bir qoida)."""
    return round(sum(d[2] * d[3] for d in detallar(oid) if d[3] and d[1]), 2)


def foyda_tannarxi(oid):
    import services
    p = db_ishi(lambda s: services.calculate_order_profit(s, oid, company_id=1))
    return round(float(p.get("tan_narxi") or 0), 2)


def qiymat(*ids):
    return round(sum((tm(i) or (0, 0, 0))[1] for i in ids), 2)


def brak(fid, q):
    r = A.post("/api/finished/loss", json={"finished_product_id": fid, "quantity": q, "reason": "x", "brak_sabab": "boshqa"})
    return r, js(r).get("loss_id")


def taqdir(lid, t, **kv):
    return A.post(f"/api/finished/loss/{lid}/taqdir", json={"taqdir": t, **kv})


def qaytar(oid, q, nom):
    r = A.post("/api/returns", json={"order_id": oid, "order_item_id": detal_id(oid), "item_name": nom, "quantity": q, "unit": "m",
                                     "reason": "Ortiqcha", "refund_amount": 0, "to_stock": True})
    return r, js(r).get("id")


def _yozuv(matn):
    """`minus_yopdi` JSON → yopilish qatorlari (birinchi 7 maydon: nishon, donor, detal, miqdor, yopgan / qarz birligi, tuzatma)."""
    if not matn:
        return []
    d = json.loads(matn)
    return [e[:7] for e in (d.get("y") or [])] if isinstance(d, dict) else None


def taqdir_yozuvi(lid, xom=False):
    """Faol (bekor qilinmagan) taqdir qatorining `minus_yopdi`."""
    def f(s):
        q = s.query(BrakTaqdir).filter(BrakTaqdir.fp_loss_id == lid, BrakTaqdir.bekor_vaqti.is_(None)).first()
        _m = getattr(q, 'minus_yopdi', None) if q is not None else None
        return None if q is None else (json.loads(_m) if (xom and _m) else _yozuv(_m))
    return db_ishi(f)


def qaytarish_yozuvi(rid, xom=False):
    def f(s):
        q = s.get(ReturnItem, rid)
        _m = getattr(q, 'minus_yopdi', None) if q is not None else None
        return None if q is None else (json.loads(_m) if (xom and _m) else _yozuv(_m))
    return db_ishi(f)


def chiqim(fid):
    return db_ishi(lambda s: round(float(getattr(s.get(FinishedProduct, fid), 'chiqim_jami', None) or 0), 4))


def tahrir_detal(oid, **ozgar):
    """Buyurtmaning yagona detalini tahrirlash (`PUT /api/orders/{id}`) — `ozgar` maydonlari almashtiriladi."""
    o = js(A.get(f"/api/orders/{oid}"))
    it = (o.get("items") or [])[0]
    d = {"id": it.get("id"), "name": it.get("name"), "category": "profil", "width": 20, "thickness": 10, "length": it.get("length"),
         "quantity": 1, "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID, "finished_product_id": it.get("finished_product_id")}
    d.update(ozgar)
    return A.put(f"/api/orders/{oid}?confirm_shortage=true", json={"project_id": PRJ_ID, "order_type": "product", "loy_kg": 0,
                                                                    "items": [d], "notes": o.get("notes")})


def tugat(nom, miqdor, birlik):
    """Yangi (jarayondagi) partiya — «Sotuvga tayyor» (minusni yopadi)."""
    n = yangi_tm(miqdor, nom, birlik, holat=ProductionStatus.IN_PROGRESS)
    return n, A.post(f"/api/finished/{n}/complete")


def a_holati(nom, keyin_qosh=None, kutish=0.0):
    """A naqshi: T 10 m × 1 000 → brak 10 (T 0) → «+» 5 m × 1 200 (T 5 / 6 000) → buyurtma 10 m (5 bor + 5 QARZ, birligi 1 200 — O 12 000)
    → taqdir «Tuzatildi — joyiga» (+10 × 1 000: 5 qarzni yopdi — O 11 000, T 5 / 5 000) → [«+» keyin_qosh m × 200]."""
    narx(120000)
    T = yangi_tm(10, nom, 1000)
    _, L = brak(T, 10)
    A.post(f"/api/finished/{T}/add", json={"quantity": 5})
    if kutish:
        time.sleep(kutish)
    O = buyurtma(detal(10, T))
    rt = taqdir(L, "tuzatildi", joy="joyiga")
    holat = (rt.status_code, tm(T), btannarx(O), qarz(O))
    if keyin_qosh:
        narx(20000)
        A.post(f"/api/finished/{T}/add", json={"quantity": keyin_qosh})
    return T, L, O, holat


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Ustunlar va yopilish yozuvi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("K1 `brak_taqdirlari.minus_yopdi` va `return_items.minus_yopdi` ustunlari (modelda)",
      hasattr(BrakTaqdir, "minus_yopdi") and hasattr(ReturnItem, "minus_yopdi"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Brak taqdiri «Tuzatildi — o'sha joyiga» minusni yopgan — taqdir bekor qilinadi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
T1, L1, O1, h1 = a_holati("TM197 A1 Karniz", keyin_qosh=10)
check("A0 taqdir minusni yopdi: O 11 000 (5 × 1 200 + 5 × 1 000), T 5 / 5 000, qarz 0",
      h1[0] == 200 and h1[1][:2] == (5.0, 5000.0) and teng(h1[2], 11000) and h1[3] == 0.0, h1)
_y1 = taqdir_yozuvi(L1)
check("K2 taqdir yozuvi: [T, donorsiz, detal, 5 m, yopgan 1 000, qarz birligi 1 200, detal tuzatmasi −1 000]",
      _y1 == [[T1, None, detal_id(O1), 5.0, 1000.0, 1200.0, -1000.0]], _y1)
r = taqdir(L1, "tashlandi")
check("A1 keyin arzon (10 m × 200) qo'shilgan — «Tashlandi»: buyurtmaning 5 m i bor qoldiqdan (200) qoplandi — O 6 000 + 1 000 = 7 000, "
      "T 5 m / 1 000 (birlik 200); saqlanish 0 (ilgari T 5 / 0, O 11 000 — +3 000)",
      r.status_code == 200 and tm(T1) == (5.0, 1000.0, 200.0) and teng(btannarx(O1), 7000) and qarz(O1) == 0.0
      and teng(qiymat(T1) + btannarx(O1) - (10 * 1000 - 10000 + 5 * 1200 + 10 * 200), 0),
      (r.status_code, r.text[:300], tm(T1), detallar(O1)))
check("A1b foyda hisobi ham 7 000; jurnalda «qarzdorlarga qaytdi»",
      teng(foyda_tannarxi(O1), 7000) and "qarzdorlarga qaytdi" in " ".join(js(r).get("jurnal") or []), (foyda_tannarxi(O1), js(r)))

T2, L2, O2, h2 = a_holati("TM197 A2 Karniz")
r = taqdir(L2, "tashlandi")
check("A2 keyin qo'shilmagan — «Tashlandi» ENDI RUXSAT (ilgari «mahsulot sotilgan …» deb rad): AYNAN taqdirdan oldingi holat — T −5 / 0 "
      "(birlik 1 200), O 12 000, qarz 5",
      r.status_code == 200 and tm(T2) == (-5.0, 0.0, 1200.0) and teng(btannarx(O2), 12000) and qarz(O2) == 5.0,
      (r.status_code, r.text[:300], tm(T2), detallar(O2)))
N2, rc2 = tugat("TM197 A2 Karniz", 5, 1300)
check("A3 qarzga qaytgan buyurtma — keyingi partiya (5 m × 1 300) yopdi: O 6 000 + 5 × 1 300 = 12 500, T 0, qarz 0",
      rc2.status_code == 200 and teng(btannarx(O2), 12500) and tm(T2)[0] == 0.0 and qarz(O2) == 0.0, (rc2.status_code, tm(T2), tm(N2), detallar(O2)))

T4, L4, O4, h4 = a_holati("TM197 A4 Karniz", keyin_qosh=3)
r = taqdir(L4, "tashlandi")
check("A4 keyin 3 m (200) qo'shilgan: 3 m qoplandi, 2 m yana qarzga — T −2 / 0 (birlik 1 200), O 12 000 − 3 × 1 000 = 9 000, qarz 2",
      r.status_code == 200 and tm(T4) == (-2.0, 0.0, 1200.0) and teng(btannarx(O4), 9000) and qarz(O4) == 2.0,
      (r.status_code, r.text[:300], tm(T4), detallar(O4)))

T5, L5, O5, h5 = a_holati("TM197 A5 Karniz")
r5r = A.post(f"/api/orders/{O5}/ready")
narx(20000)
A.post(f"/api/finished/{T5}/add", json={"quantity": 10})
r = taqdir(L5, "tashlandi")
check("A5 qarzdor buyurtma «Tayyor» bo'lib bo'lgan — tannarxi O'ZGARMAYDI (11 000, egasi qarori); uning 5 m i bor qoldiqdan qoplandi — "
      "T 5 m / 1 000",
      r5r.status_code == 200 and r.status_code == 200 and tm(T5) == (5.0, 1000.0, 200.0) and teng(btannarx(O5), 11000) and qarz(O5) == 0.0,
      (r5r.status_code, r.status_code, r.text[:300], tm(T5), detallar(O5)))

T6, L6, O6, h6 = a_holati("TM197 A6 Karniz")
rd6 = A.delete(f"/api/orders/{O6}")
narx(20000)
A.post(f"/api/finished/{T6}/add", json={"quantity": 10})
r = taqdir(L6, "tashlandi")
check("A6 qarzdor buyurtma o'chirilgan (mahsulot partiyaga qaytgan) — qarzga qaytadigan yo'q: T 15 m / 8 000 (taqdirsiz o'ynash bilan AYNAN: "
      "−5 → o'chirish 5 + 5 × 1 200 → +10 × 200)",
      rd6.status_code == 200 and r.status_code == 200 and tm(T6)[:2] == (15.0, 8000.0) and teng(tm(T6)[2], 8000 / 15, 0.001),
      (rd6.status_code, r.status_code, r.text[:300], tm(T6)))

T7, L7, O7, h7 = a_holati("TM197 A7 Karniz", keyin_qosh=10)
db_ishi(lambda s: s.query(BrakTaqdir).filter(BrakTaqdir.fp_loss_id == L7).update({"minus_yopdi": None}, synchronize_session=False)
        if hasattr(BrakTaqdir, "minus_yopdi") else None)
r = taqdir(L7, "tashlandi")
check("A7 yozuvi YO'Q (deploydan oldingi) taqdir — avvalgidek: T 5 / 0, O 11 000 (eski qoida o'zgarmadi)",
      r.status_code == 200 and tm(T7)[:2] == (5.0, 0.0) and teng(btannarx(O7), 11000), (r.status_code, tm(T7), detallar(O7)))

T8, L8, O8, h8 = a_holati("TM197 A8 Karniz", keyin_qosh=10)
_c8 = chiqim(T8)
r = A.delete(f"/api/finished/loss/{L8}")
check("A8 brak yozuvi BUTUNLAY o'chirildi (o'sha miqdor o'sha partiyaga qaytadi) — avvalgidek: T 15 / 7 000, O 11 000, saqlanish 0",
      r.status_code == 200 and tm(T8)[:2] == (15.0, 7000.0) and teng(btannarx(O8), 11000)
      and teng(qiymat(T8) + btannarx(O8) - (10 * 1000 + 5 * 1200 + 10 * 200), 0), (r.status_code, r.text[:300], tm(T8), detallar(O8)))
check("K5 chiqim hisoblagichi: brak 10 + buyurtma 10 m (5 bor + 5 qarz) = 20 (sof kamayish; qo'shishlar — yo'q); bir tranzaksiyada "
      "olib-qaytarilgan (brak yozuvi o'chirildi: −10 +10) — o'zgarmadi",
      _c8 == 20.0 and chiqim(T8) == 20.0, (_c8, chiqim(T8)))

T9 = yangi_tm(10, "TM197 A9 Karniz", 1000)
_, L9 = brak(T9, 4)
r9a = taqdir(L9, "tuzatildi", joy="joyiga")
_y9 = taqdir_yozuvi(L9)
r9b = taqdir(L9, "tashlandi")
check("A9 minussiz taqdir — yozuv bo'sh, bekori avvalgidek: T 6 / 6 000",
      r9a.status_code == 200 and _y9 == [] and r9b.status_code == 200 and tm(T9)[:2] == (6.0, 6000.0), (r9a.status_code, _y9, r9b.status_code, tm(T9)))

T10, L10, O10, h10 = a_holati("TM197 A10 Karniz", keyin_qosh=10)
r = taqdir(L10, "ikkinchi_nav", narx=500)
_y10 = db_ishi(lambda s: [(x.id, round(float(x.quantity), 4), round(float(x.cost_price or 0), 2)) for x in s.query(FinishedProduct).filter(
    FinishedProduct.name == "TM197 A10 Karniz", FinishedProduct.brak_taqdir == "ikkinchi_nav")])
check("A10 taqdir «Tuzatildi» → «2-nav»: eski bekor (O 7 000, T 5 / 1 000), 2-nav partiya 10 m / 10 000; saqlanish 0 (brak zarari 0)",
      r.status_code == 200 and tm(T10)[:2] == (5.0, 1000.0) and teng(btannarx(O10), 7000) and len(_y10) == 1 and _y10[0][1:] == (10.0, 10000.0)
      and teng(qiymat(T10, _y10[0][0]) + btannarx(O10) - (10 * 1000 + 5 * 1200 + 10 * 200), 0),
      (r.status_code, r.text[:300], tm(T10), _y10, detallar(O10)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Brakdan YANGI partiya (2-nav) guruhdosh minusini KO'CHIRIB yopgan — taqdir bekor qilinadi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TB = yangi_tm(20, "TM197 B Karniz", 1000)
_, LB1 = brak(TB, 10)                              # TB 10 / 10 000
rb1 = taqdir(LB1, "ikkinchi_nav", narx=500)        # Y — 2-nav 10 m / 10 000
YB = js(rb1).get("tm_id")
OB = buyurtma(detal(15, YB))                       # Y −5 (qarz 5 × 1 000) — O 15 000
db_ishi(lambda s: setattr(s.get(FinishedProduct, TB), "cost_price", 14000.0))   # TB 10 m / 14 000 (o'rtacha 1 400)
_, LB2 = brak(TB, 5)                               # 5 × 1 400 = 7 000
rb2 = taqdir(LB2, "ikkinchi_nav", narx=500)        # Z — 2-nav 5 m / 7 000 → Y minusini ko'chirib yopdi
ZB = js(rb2).get("tm_id")
_yb = taqdir_yozuvi(LB2)
check("B1 yangi 2-nav partiya (5 m × 1 400) guruhdosh minusini ko'chirib yopdi: O 15 000 + 5 × 400 = 17 000, Y 0, Z 0; yozuvda donor — Z",
      rb2.status_code == 200 and teng(btannarx(OB), 17000) and tm(YB)[0] == 0.0 and tm(ZB)[0] == 0.0
      and _yb == [[YB, ZB, detal_id(OB), 5.0, 1400.0, 1000.0, 2000.0]], (rb2.status_code, tm(YB), tm(ZB), detallar(OB), _yb))
r = taqdir(LB2, "tashlandi")
check("B2 «Tashlandi» ENDI RUXSAT (ilgari Z bo'sh — rad): AYNAN oldingi holat — Y −5 / 0 (birlik 1 000), O 15 000, qarz 5; bo'sh Z o'chdi",
      r.status_code == 200 and tm(YB) == (-5.0, 0.0, 1000.0) and teng(btannarx(OB), 15000) and qarz(OB) == 5.0 and tm(ZB) is None,
      (r.status_code, r.text[:300], tm(YB), tm(ZB), detallar(OB)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Mijozdan qaytgan mahsulot minusni yopgan — qaytarish yozuvi o'chiriladi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# profil sotuv narxi — detal JAMI (narx × soni) ÷ metr; qaytgan partiyaga birlashish sharti — shu narx teng
R1 = yangi_tm(10, "TM197 Q1 Qaytgan", 1000, manba=StockSource.RETURNED, sotuv=2000)
Oa1 = buyurtma(detal(15, R1))                      # R −5
P1 = yangi_tm(10, "TM197 Q1 Ishlab", 1300)
Ob1 = buyurtma(detal(4, P1, nom="TM197 Q1 Qaytgan", narxi=8000))      # 4 m × 1 300 (1 m = 2 000)
Q1 = yangi_tm(10, "TM197 Q1 Arzon", 200)
time.sleep(8.5)                                    # 8 s «takroriy yuborish» imzosi (nom bir xil)
Oc1 = buyurtma(detal(10, Q1, nom="TM197 Q1 Qaytgan", narxi=20000))    # 10 m × 200
ra1, RA1 = qaytar(Ob1, 4, "TM197 Q1 Qaytgan")
_yq1 = qaytarish_yozuvi(RA1) if RA1 else None
check("K3 qaytish (4 m × 1 300) minusdagi qaytgan partiyaga birlashib qarzdan 4 m yopdi: Oa 16 200; yozuv [R, donorsiz, detal, 4, 1 300, "
      "1 000, 1 200]",
      ra1.status_code == 200 and teng(btannarx(Oa1), 16200) and tm(R1)[:2] == (-1.0, 0.0)
      and _yq1 == [[R1, None, detal_id(Oa1), 4.0, 1300.0, 1000.0, 1200.0]], (ra1.status_code, ra1.text[:200], tm(R1), _yq1))
rb_, RB1 = qaytar(Oc1, 10, "TM197 Q1 Qaytgan")
rd = A.delete(f"/api/returns/{RA1}")
check("Q1 keyin arzon qaytish (10 m × 200), birinchi qaytarish o'chirildi: R 5 m / 1 000 (birlik 200), Oa 11 000, Ob 5 200 (qaytmagandek), "
      "Oc 0; saqlanish 0 (ilgari R 5 / 0, Oa 15 400 — +3 400)",
      rb_.status_code == 200 and rd.status_code == 200 and tm(R1) == (5.0, 1000.0, 200.0) and teng(foyda_tannarxi(Oa1), 11000)
      and teng(foyda_tannarxi(Ob1), 5200) and teng(foyda_tannarxi(Oc1), 0)
      and teng(qiymat(R1, P1, Q1) + foyda_tannarxi(Oa1) + foyda_tannarxi(Ob1) + foyda_tannarxi(Oc1) - (10000 + 13000 + 2000), 0),
      (rb_.status_code, rd.status_code, rd.text[:300], tm(R1), foyda_tannarxi(Oa1), foyda_tannarxi(Ob1), foyda_tannarxi(Oc1)))

_j1 = db_ishi(lambda s: [x.new_value or "" for x in s.query(ActivityLog).filter(ActivityLog.entity_type == "return",
                                                                                ActivityLog.action == "deleted", ActivityLog.entity_id == RA1)])
check("Q1b «Faoliyat jurnali»: qaytarish o'chirilishida «minusni yopgan 4 metr qarzdorlarga qaytdi» va «o'z qoldig'idan qoplandi»",
      len(_j1) == 1 and "minusni yopgan 4 metr qarzdorlarga qaytdi" in _j1[0] and "o'z qoldig'idan qoplandi" in _j1[0], _j1)

R2 = yangi_tm(10, "TM197 Q2 Qaytgan", 1000, manba=StockSource.RETURNED, sotuv=2000)
Oa2 = buyurtma(detal(15, R2))                      # R −5
P2 = yangi_tm(10, "TM197 Q2 Ishlab", 1300)
Ob2 = buyurtma(detal(4, P2, nom="TM197 Q2 Qaytgan", narxi=25000))     # 1 m = 6 250 — R bilan birlashmaydi (yangi partiya)
Q2 = yangi_tm(10, "TM197 Q2 Arzon", 200)
time.sleep(8.5)
Oc2 = buyurtma(detal(6, Q2, nom="TM197 Q2 Qaytgan", narxi=37500))     # 1 m = 6 250 — X bilan birlashadi
ra2, RA2 = qaytar(Ob2, 4, "TM197 Q2 Qaytgan")
X2 = db_ishi(lambda s: s.get(ReturnItem, RA2).finished_product_id) if RA2 else None
_yq2 = qaytarish_yozuvi(RA2) if RA2 else None
check("K4 qaytish yangi partiya (X, 4 m × 1 300) bo'lib guruhdosh minusini ko'chirib yopdi: yozuvda donor — X",
      ra2.status_code == 200 and tm(X2)[0] == 0.0 and _yq2 == [[R2, X2, detal_id(Oa2), 4.0, 1300.0, 1000.0, 1200.0]],
      (ra2.status_code, tm(X2), _yq2))
rb2_, RB2 = qaytar(Oc2, 6, "TM197 Q2 Qaytgan")
rd2 = A.delete(f"/api/returns/{RA2}")
check("Q2 X ga arzon qaytish (6 m × 200) birlashdi, birinchi qaytarish o'chirildi: X 1 m / 200, R 0, Oa 11 000, Ob 5 200; saqlanish 0 "
      "(ilgari X 1 / 0, Oa 15 400 — +4 200)",
      rb2_.status_code == 200 and rd2.status_code == 200 and tm(X2) == (1.0, 200.0, 200.0) and tm(R2)[0] == 0.0
      and teng(foyda_tannarxi(Oa2), 11000) and teng(foyda_tannarxi(Ob2), 5200)
      and teng(qiymat(R2, P2, Q2, X2) + foyda_tannarxi(Oa2) + foyda_tannarxi(Ob2) + foyda_tannarxi(Oc2) - (10000 + 13000 + 2000), 0),
      (rb2_.status_code, rd2.status_code, rd2.text[:300], tm(R2), tm(X2), foyda_tannarxi(Oa2), foyda_tannarxi(Ob2), foyda_tannarxi(Oc2)))

R3 = yangi_tm(10, "TM197 Q3 Qaytgan", 1000, manba=StockSource.RETURNED, sotuv=2000)
Oa3 = buyurtma(detal(15, R3))                      # R −5
P3 = yangi_tm(10, "TM197 Q3 Ishlab", 1300)
Ob3 = buyurtma(detal(4, P3, nom="TM197 Q3 Qaytgan", narxi=25000))
ra3, RA3 = qaytar(Ob3, 4, "TM197 Q3 Qaytgan")      # yangi X 4 → R ga ko'chdi (R −1), Oa 16 200
X3 = db_ishi(lambda s: s.get(ReturnItem, RA3).finished_product_id) if RA3 else None
rd3 = A.delete(f"/api/returns/{RA3}")
check("Q3 keyin hech narsa qaytmagan — qaytarishni o'chirish ENDI RUXSAT (ilgari X bo'sh — rad): AYNAN oldingi holat — R −5 / 0, Oa 15 000, "
      "qarz 5; bo'sh X o'chdi; Ob 5 200",
      ra3.status_code == 200 and rd3.status_code == 200 and tm(R3) == (-5.0, 0.0, 1000.0) and teng(btannarx(Oa3), 15000) and qarz(Oa3) == 5.0
      and tm(X3) is None and teng(foyda_tannarxi(Ob3), 5200), (ra3.status_code, rd3.status_code, rd3.text[:300], tm(R3), tm(X3), detallar(Oa3)))

R4 = yangi_tm(10, "TM197 Q4 Qaytgan", 1000, manba=StockSource.RETURNED, sotuv=2000)
Oa4 = buyurtma(detal(15, R4))                      # R −5
P4 = yangi_tm(10, "TM197 Q4 Ishlab", 1300)
Ob4 = buyurtma(detal(4, P4, nom="TM197 Q4 Qaytgan", narxi=8000))      # R ga birlashadi — to'g'ridan yopadi (R −1)
ra4, RA4 = qaytar(Ob4, 4, "TM197 Q4 Qaytgan")
rd4 = A.delete(f"/api/returns/{RA4}")
check("Q4 to'g'ridan yopgan qaytish o'chirildi, keyin hech narsa qaytmagan — ENDI RUXSAT (ilgari R bo'sh qoldig'i −1 — rad): R −5 / 0, "
      "Oa 15 000, qarz 5; Ob 5 200",
      ra4.status_code == 200 and rd4.status_code == 200 and tm(R4) == (-5.0, 0.0, 1000.0) and teng(btannarx(Oa4), 15000) and qarz(Oa4) == 5.0
      and teng(foyda_tannarxi(Ob4), 5200), (ra4.status_code, rd4.status_code, rd4.text[:300], tm(R4), detallar(Oa4)))

R5 = yangi_tm(10, "TM197 Q5 Qaytgan", 1000, manba=StockSource.RETURNED, sotuv=2000)
Oa5 = buyurtma(detal(15, R5))                      # R −5
P5 = yangi_tm(10, "TM197 Q5 Ishlab", 1300)
Ob5 = buyurtma(detal(4, P5, nom="TM197 Q5 Qaytgan", narxi=25000))     # yangi X — R ga ko'chib yopadi (R −1)
ra5, RA5 = qaytar(Ob5, 4, "TM197 Q5 Qaytgan")
X5 = db_ishi(lambda s: s.get(ReturnItem, RA5).finished_product_id) if RA5 else None
rdo5 = A.delete(f"/api/orders/{Oa5}")             # qarzdor o'chdi: 1 m qarz + 14 m (10 × 1 000 + 4 × 1 300) R ga qaytdi — R 14 / 15 200
_r5 = tm(R5)
rd5 = A.delete(f"/api/returns/{RA5}")
check("Q5 ko'chib yopilgan qarzdor o'chirilgan (mahsulot R ga qaytgan), so'ng qaytarish o'chirildi: R dan 4 m YOPGAN narxda (1 300) "
      "donorga — R 10 m / 10 000 (qaytishsiz o'ynash bilan AYNAN), X o'chdi, Ob 5 200",
      rdo5.status_code == 200 and _r5[:2] == (14.0, 15200.0) and rd5.status_code == 200 and tm(R5)[:2] == (10.0, 10000.0) and tm(X5) is None
      and teng(foyda_tannarxi(Ob5), 5200), (rdo5.status_code, _r5, rd5.status_code, rd5.text[:300], tm(R5), tm(X5)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. MRP bandidan bo'shagan qoldiq (Ortiqcha qaytish) guruhdosh minusini yopgan — qaytarish o'chiriladi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_mat = js(A.post("/api/inventory", json={"item_name": "TM197 Qum", "unit": "kg", "category": "Kimyoviy qo'shimchalar",
                                         "stock_quantity": 1000, "price_per_unit": 100, "min_stock": 0}))
_pt = js(A.post("/api/production/product-types", json={"name": "TM197 Travertin", "unit": "m2", "input_template": "quantity_only",
                                                       "pricing_formula": "unit_based"}))
_bom = js(A.post("/api/production/boms", json={"product_type_id": _pt.get("id"), "variant_name": "Standart", "batch_quantity": 1,
                                               "items": [{"inventory_id": _mat.get("id"), "quantity": 2}]}))


def mrp_tm(pid):
    return db_ishi(lambda s: s.get(ProductionOrder, pid).finished_product_id if pid else None)


_p1 = js(A.post("/api/production/orders", json={"product_type_id": _pt.get("id"), "bom_id": _bom.get("id"), "quantity": 10,
                                               "source_type": "warehouse_stock"}))
_p1 = (_p1.get("production_order") or _p1).get("id")
A.post(f"/api/production/orders/{_p1}/start")
_rm1 = A.post(f"/api/production/orders/{_p1}/complete")
FMA = mrp_tm(_p1)
db_ishi(lambda s: setattr(s.get(FinishedProduct, FMA), "quantity", -3.0) or setattr(s.get(FinishedProduct, FMA), "cost_price", 0.0))
_om = js(A.post("/api/orders?confirm_shortage=true", json={"project_id": PRJ_ID, "order_type": "product", "loy_kg": 0, "items": [
    {"name": "TM197 MRP detal", "category": "mrp_product", "quantity": 10, "unit_price": 100000, "is_coated": False,
     "penoplast_id": None, "product_type_id": _pt.get("id")}]}))
_om_id = _om.get("id")
_om_iid = detal_id(_om_id) if _om_id else None
_po = js(A.post("/api/production/orders", json={"product_type_id": _pt.get("id"), "bom_id": _bom.get("id"), "quantity": 10,
                                              "source_type": "customer_order", "source_order_id": _om_id, "source_order_item_id": _om_iid}))
_po_id = (_po.get("production_order") or _po).get("id") if isinstance(_po, dict) else None
A.post(f"/api/production/orders/{_po_id}/start")
_rc = A.post(f"/api/production/orders/{_po_id}/complete")
FMR = mrp_tm(_po_id)
_fmr0 = tm(FMR)
_rq = A.post("/api/returns", json={"order_id": _om_id, "order_item_id": _om_iid, "item_name": "x", "quantity": 4, "unit": "m²",
                                   "reason": "Ortiqcha", "refund_amount": 0, "to_stock": True})
_rqid = js(_rq).get("id")
_ym = qaytarish_yozuvi(_rqid) if _rqid else None
check("M1 MRP detali (band 10) dan «Ortiqcha» 4 m² — bo'shagan qoldiq guruhdosh −3 ni yopdi: FMA 0, FMR 7 / band 6; yozuvda donor FMR "
      "(qarz yozuvisiz qism)",
      _rm1.status_code == 200 and _rc.status_code == 200 and _rq.status_code == 200 and tm(FMA)[0] == 0.0 and tm(FMR)[0] == 7.0
      and band(FMR) == 6.0 and _ym and len(_ym) == 1 and _ym[0][:4] == [FMA, FMR, None, 3.0],
      (_rm1.status_code, _rc.status_code, _rq.status_code, _rq.text[:200], tm(FMA), tm(FMR), _ym))
_rqd = A.delete(f"/api/returns/{_rqid}") if _rqid else None
check("M2 qaytarish o'chirildi — ENDI RUXSAT (ilgari bo'sh qoldiq 1 < 4 — rad): FMA yana −3, FMR 10 m² / band 10 / tannarxi AYNAN oldingi",
      _rqd is not None and _rqd.status_code == 200 and tm(FMA)[0] == -3.0 and tm(FMR)[0] == 10.0 and band(FMR) == 10.0
      and teng(tm(FMR)[1], _fmr0[1]), (_rqd.status_code if _rqd is not None else None, _rqd.text[:300] if _rqd is not None else "",
                                       tm(FMA), tm(FMR), _fmr0, band(FMR)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. Mustaqil tekshiruv (work/k197/review197/HISOBOT.md) — hodisadan keyin partiyadan chiqim, detal kamaygan, band, qulf tartibi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TF1, LF1, OF1, _ = a_holati("TM197 F1 Karniz")
OF2 = buyurtma(detal(8, TF1))                      # taqdirdan keyin boshqa buyurtma 8 m: 5 bor (taqdir bilan kelgan) + 3 qarz
narx(20000)
A.post(f"/api/finished/{TF1}/add", json={"quantity": 10})       # arzon: OF2 qarzini yopdi, TF1 7 / 1 400
_f1 = (tm(TF1), btannarx(OF1), btannarx(OF2))
r = taqdir(LF1, "tashlandi")
check("F1 taqdirdan keyin partiyadan boshqa buyurtma olgan (taqdir bilan kelgan mahsulot unga ketgan bo'lishi mumkin) — «Tashlandi» RAD, "
      "sabab «chiqim bo'lgan»; hech narsa o'zgarmadi (ilgari ruxsat: +6 000)",
      r.status_code == 400 and "chiqim bo'lgan" in r.text and (tm(TF1), btannarx(OF1), btannarx(OF2)) == _f1 and _f1[0][:2] == (7.0, 1400.0),
      (r.status_code, r.text[:300], _f1, tm(TF1), btannarx(OF1), btannarx(OF2)))

TF2, LF2, OF3, _ = a_holati("TM197 F2 Karniz")
rF2 = tahrir_detal(OF3, length=14)                 # qarzdorning O'ZI ko'paydi: taqdir bilan kelgan 4 m ni oldi
narx(20000)
A.post(f"/api/finished/{TF2}/add", json={"quantity": 10})
r = taqdir(LF2, "tashlandi")
check("F2 qarzdor detalning o'zi keyin ko'paydi (10 → 14) — «Tashlandi» RAD (ilgari +8 000)",
      rF2.status_code == 200 and r.status_code == 400 and "chiqim bo'lgan" in r.text, (rF2.status_code, r.status_code, r.text[:300]))

TF3, LF3, OF4, _ = a_holati("TM197 F3 Karniz")
rF3 = tahrir_detal(OF4, length=6)                  # qarzdor kamaydi: 4 m qaytdi (detal haqiqiy birligida — 1 100)
narx(20000)
A.post(f"/api/finished/{TF3}/add", json={"quantity": 10})
r = taqdir(LF3, "tashlandi")
check("F3 qarzdor detal keyin KAMAYGAN (10 → 6): yopilgan birliklar avval qaytgan deb — hodisasiz o'ynash bilan AYNAN: O 6 200 "
      "(5 × 1 200 + 1 × 200), T 9 m / 1 800 (ilgari NEW 3 885,71 / 4 114,29)",
      rF3.status_code == 200 and r.status_code == 200 and teng(btannarx(OF4), 6200) and tm(TF3)[:2] == (9.0, 1800.0) and qarz(OF4) == 0.0,
      (rF3.status_code, r.status_code, r.text[:300], tm(TF3), detallar(OF4)))

TF4, LF4, OF5, _ = a_holati("TM197 F4 Karniz")
narx(20000)
A.post(f"/api/finished/{TF4}/add", json={"quantity": 5})        # T 10 / 6 000
db_ishi(lambda s: setattr(s.get(FinishedProduct, TF4), "reserved_quantity", 4.0))
_f4 = (tm(TF4), btannarx(OF5), qarz(OF5))
r = taqdir(LF4, "tashlandi")
check("F4 qoplash uchun kerakli qoldiq BAND — rad, sabab «band»; hech narsa o'zgarmadi (ilgari eskirgan qarz qolardi: +4 800)",
      r.status_code == 400 and "band" in r.text and (tm(TF4), btannarx(OF5), qarz(OF5)) == _f4, (r.status_code, r.text[:300], _f4, tm(TF4)))
db_ishi(lambda s: setattr(s.get(FinishedProduct, TF4), "reserved_quantity", 0.0))

RF5 = yangi_tm(10, "TM197 F5 Qaytgan", 1000, manba=StockSource.RETURNED, sotuv=2000)
OaF5 = buyurtma(detal(15, RF5))                    # R −5
PF5 = yangi_tm(10, "TM197 F5 Ishlab", 1300)
ObF5 = buyurtma(detal(8, PF5, nom="TM197 F5 Qaytgan", narxi=16000))   # 8 m × 1 300 (1 m = 2 000)
raF5, RAF5 = qaytar(ObF5, 8, "TM197 F5 Qaytgan")   # R ga 8: 5 qarzni yopdi, R 3 / 3 900
OcF5 = buyurtma(detal(3, RF5))                     # boshqa buyurtma qaytgan mahsulotni oldi — R 0
_f5 = (tm(RF5), btannarx(OaF5), btannarx(OcF5))
rdF5 = A.delete(f"/api/returns/{RAF5}")
check("F5 qaytgan mahsulotni keyin boshqa buyurtma olgan — qaytarishni o'chirish RAD («chiqim bo'lgan»), hech narsa o'zgarmadi (ilgari "
      "ruxsat: +5 700)",
      raF5.status_code == 200 and rdF5.status_code == 400 and "chiqim bo'lgan" in rdF5.text
      and (tm(RF5), btannarx(OaF5), btannarx(OcF5)) == _f5, (raF5.status_code, rdF5.status_code, rdF5.text[:300], _f5, tm(RF5)))

if PG_URL and hasattr(crud, "_tm_yopish_reja"):
    import threading
    _asl197 = crud._tm_qarz_yopildi
    _kim197 = threading.local()

    def _sekin197(*a, **k):
        if getattr(_kim197, "nom", None) == "B":
            time.sleep(1.5)                        # B partiya qulfini ushlab turadi — tartib teskari bo'lsa 40P01
        return _asl197(*a, **k)
    crud._tm_qarz_yopildi = _sekin197

    def _ish197(nom, lid, tana, kut, natija):
        _kim197.nom = nom
        time.sleep(kut)
        s = SessionLocal()
        try:
            with crud.bitta_tranzaksiya(s):
                crud.brak_taqdir_belgila(s, "yoqotish", lid, tana, company_id=1, performed_by=nom)
            natija[nom] = "ok"
        except Exception as e:             # noqa: BLE001
            s.rollback()
            natija[nom] = f"{type(e).__name__}: {str(e).splitlines()[0][:160]}"
        finally:
            s.close()
    _qulf = []
    for _u in range(2):
        narx(120000)
        GQ = yangi_tm(0, f"TM197 Q Qulf {_u}", 1000)          # kichik id, o'sha guruh, bo'sh
        TQ = yangi_tm(20, f"TM197 Q Qulf {_u}", 1000)
        _, LQ1 = brak(TQ, 10)
        _, LQ2 = brak(TQ, 3)                                  # TQ 7
        OQ = buyurtma(detal(22, TQ))                          # TQ −15
        taqdir(LQ1, "tuzatildi", joy="joyiga")                # +10: 10 qarz yopildi, TQ −5
        _nat = {}
        tb = threading.Thread(target=_ish197, args=("B", LQ2, {"taqdir": "tuzatildi", "joy": "joyiga"}, 0.0, _nat))
        ta = threading.Thread(target=_ish197, args=("A", LQ1, {"taqdir": "tashlandi"}, 0.5, _nat))
        tb.start()
        ta.start()
        tb.join(60)
        ta.join(60)
        _qulf.append((_nat.get("A"), _nat.get("B"), tm(TQ), qarz(OQ)))
    check("P1 [PG] bir guruhda bir vaqtda: taqdir bekori (guruh avval) ∥ «Tuzatildi — joyiga» (minusda — endi ham guruh avval): 40P01 yo'q, "
          "ikkalasi ok; natija TQ −12, qarz 12 (ilgari 3 / 3 urinishda deadlock)",
          all(a == "ok" and b == "ok" and t[0] == -12.0 and q == 12.0 for a, b, t, q in _qulf), _qulf)
    import schemas as _sch197

    def _qaytish197(nom, oid, iid, q, ism, kut, natija):
        _kim197.nom = nom
        time.sleep(kut)
        s = SessionLocal()
        try:
            crud.create_return_item(s, _sch197.ReturnItemCreate(order_id=oid, order_item_id=iid, item_name=ism, quantity=float(q),
                                                                unit="m", reason="Ortiqcha", refund_amount=0.0, to_stock=True),
                                    company_id=1, performed_by=nom)
            natija[nom] = "ok"
        except Exception as e:             # noqa: BLE001
            s.rollback()
            natija[nom] = f"{type(e).__name__}: {str(e).splitlines()[0][:160]}"
        finally:
            s.close()

    def _ochir197(nom, rid, kut, natija):
        _kim197.nom = nom
        time.sleep(kut)
        s = SessionLocal()
        try:
            crud.delete_return_item(s, rid, company_id=1, performed_by=nom)
            natija[nom] = "ok"
        except Exception as e:             # noqa: BLE001
            s.rollback()
            natija[nom] = f"{type(e).__name__}: {str(e).splitlines()[0][:160]}"
        finally:
            s.close()
    _qulf2 = []
    for _u in range(2):
        _nm = f"TM197 QR Qulf {_u}"
        GR = yangi_tm(0, _nm, 1000, manba=StockSource.RETURNED, sotuv=2000)   # kichik id, o'sha guruh, bo'sh
        RR = yangi_tm(10, _nm, 1000, manba=StockSource.RETURNED, sotuv=2000)
        OaR = buyurtma(detal(25, RR))                                           # RR −15
        PR = yangi_tm(30, _nm + " Ishlab", 1300)
        ObR = buyurtma(detal(10, PR, nom=_nm, narxi=20000))                     # 1 m = 2 000
        time.sleep(8.5)
        OcR = buyurtma(detal(5, PR, nom=_nm, narxi=10000))
        _, RAR = qaytar(ObR, 10, _nm)                                           # RR ga birlashdi: 10 qarz yopildi, RR −5
        _nat = {}
        tb = threading.Thread(target=_qaytish197, args=("B", OcR, detal_id(OcR), 3, _nm, 0.0, _nat))   # RR −5 → −2 (minus qoladi — guruh)
        ta = threading.Thread(target=_ochir197, args=("A", RAR, 0.5, _nat))
        tb.start()
        ta.start()
        tb.join(60)
        ta.join(60)
        _qulf2.append((_nat.get("A"), _nat.get("B"), tm(RR), qarz(OaR)))
    crud._tm_qarz_yopildi = _asl197
    check("P2 [PG] bir guruhda bir vaqtda: qaytarishni o'chirish (guruh avval) ∥ yangi qaytish minusdagi partiyaga birlashadi, minus qoladi "
          "(endi ham guruh avval): 40P01 yo'q, ikkalasi ok; RR −12, qarz 12",
          all(a == "ok" and b == "ok" and t[0] == -12.0 and q == 12.0 for a, b, t, q in _qulf2), _qulf2)

print(f"\n{'=' * 70}\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
