#!/usr/bin/env python3
"""
test_yuk_xati_oylik.py — kech123 (zip 143): qoplamachi bonusi va «har birlik uchun» (blok / metr / dona) hodim haqi YUK XATLARI bo'yicha.

NIMA UCHUN KERAK (egasi, 2026-10-06 — ishxonadagi `main` da oy oxirida)
--------------------------------------------------------------------
Qoplamachiga har qoplamali metr / dona uchun 1 000 so'm. 90 % topshirilgan, lekin «Tayyor» qilinmagan buyurtma oylikka UMUMAN
tushmadi — egasi qo'lda hisobladi. O'LCHANDI (kod): `main` (ca08573) va staging — BIR XIL: `services.get_monthly_report` qoplamachi
birliklarini va kesilgan blokni faqat READY + `completed_at` shu oyda bo'lgan buyurtmalardan oladi; yuk xatlari hisobga olinmaydi.

EGASI QARORLARI (AskUserQuestion, 06.10): (1) har yuk xatidagi qism — yuk xati OYIGA; (2) «Tayyor» qilinganda yuk xatisiz qolgan qism —
yopilgan oyga (jami 100 %); (3) qaytarish kamaytirmaydi; (4) 1-oktabr 2026 gacha topshirilgan qismlar egasi tomonidan qo'lda to'langan —
qayta hisoblanmaydi; kesilgan blok — xuddi shunday (boshqa korxonalar uchun). Undan oldingi oylar — eski qoida, O'ZGARMAYDI.

BO'LIMLAR
---------
  S  statik: chegara oyi (2026, 10), `DeliveryItem.ulush`, yuk xati yozilishida ulush, hisobotda yangi yo'l;
  A  egasining misoli: 100 m qoplamali karniz, 60 m noyabrda, 40 m dekabrda — oylar bo'yicha (qoplamachi, blok, metr), «Tayyor»
     dekabrda — noyabr O'ZGARMAYDI; egasi ko'radigan «Moliya» hisoboti (`/api/finance/report`) ham AYNAN;
  B  1-oktabrgacha topshirilgan (qo'lda to'langan) qism qayta hisoblanmaydi: 90 m sentabrda, 10 m oktabrda, oktabrda yopildi — oktabr
     faqat 10 m; qisman yopilgan (miqdor topshirilganga qisqargan) — qo'shimcha 0;
  C  yuk xatisiz «Tayyor» (avtomatik yuk xati) — yopilgan oyga 100 %; avtomatik yuk vaqti yopilishdan keyin bo'lsa ham AYNAN;
  D  qaytarish haqni kamaytirmaydi;
  E  yopilgandan KEYINGI yuk xati hisoblanmaydi (yopilganda qolgani yozilgan);
  F  ichki qo'shimcha detal — yuk PAYTIDAGI ulush bilan; qisman yopilgandan keyin ham o'tgan oy O'ZGARMAYDI;
  G  qoplamasiz detal — qoplamachiga yo'q, blokka bor;
  H  begona korxona yuk xatlari kirmaydi;
  I  sentabr (chegaradan oldingi oy) — eski qoida: READY bo'lsa 100 %, yuk xati hisobga olinmaydi;
  N  so'rovlar soni buyurtmalar soniga bog'liq emas (hisobot keshi bilan);
  M  yangilanish: `ulush` ustunisiz baza (zip 142) — ustun qo'shiladi, ochiq buyurtmalarning eski yuk xatlari hozirgi miqdordan
     to'ldiriladi (`main._migrate_yuk_xati_ulush`, IDEMPOTENT) — keyin qisman «Tayyor» o'tgan oyni o'zgartirmaydi;
  U  «Hodimlar» oynasi (brauzer, 1440 va 390): «Har birlik uchun» va «qoplama qo'shimchasi» izohida yuk xati qoidasi.

REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 142) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_yuk_xati_oylik.py
"""
import os
import io
import sys
import inspect
import tempfile
import contextlib
import re
import glob
import time
import socket
import threading
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = os.environ.get("YX_PG_BAZA", "yuk_xati_oylik_test")
_T = tempfile.mkdtemp(prefix="yxo_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'yuk_xati_oylik.db')}"

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import (UserRole, Inventory, Order, OrderStatus, Delivery, DeliveryItem, OrderItem, Employee, PayType)   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import event                       # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def yaqin(a, b, eps=0.51):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


def js(r):
    try:
        return r.json()
    except Exception:                              # noqa: BLE001
        return None


# ── S. Statik ────────────────────────────────────────────────────────────────────────────────────────────────────
section("S. Statik — chegara oyi, yuk paytidagi ulush, hisobotda yangi yo'l")
check("S1 chegara oyi — (2026, 10): undan oldingi oylar eski qoida bilan (egasi qo'lda to'lagan qismlar qayta hisoblanmaydi)",
      getattr(services, "YUK_XATI_HISOBI_BOSHI", None) == (2026, 10), getattr(services, "YUK_XATI_HISOBI_BOSHI", None))
check("S2 `DeliveryItem.ulush` ustuni (Float, NULL bo'lishi mumkin, standart qiymatsiz — eski yozuvlar NULL)",
      "ulush" in DeliveryItem.__table__.columns and DeliveryItem.__table__.columns["ulush"].nullable
      and DeliveryItem.__table__.columns["ulush"].default is None,
      [c.name for c in DeliveryItem.__table__.columns])
_src_cd = inspect.getsource(crud.create_delivery)
check("S3 yuk xati yozilganda ulush = berilgan ÷ detalning yuk paytidagi miqdori (`order_qty_normalized`)",
      "ulush=" in _src_cd and "order_qty_normalized" in _src_cd, "")
_src_rep = inspect.getsource(services.get_monthly_report)
check("S4 oylik hisobot chegaradan boshlab yuk xatlari bo'yicha (`_yuk_xati_ulushlari`), eski tsikl — faqat oldingi oylarga",
      "_yuk_xati_ulushlari" in _src_rep and "YUK_XATI_HISOBI_BOSHI" in _src_rep
      and "for order in ([] if _yuk_xati_hisobi else orders_this_month)" in _src_rep, "")

# ── Tayyorgarlik ─────────────────────────────────────────────────────────────────────────────────────────────────
db = SessionLocal()
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="YX Begona korxona"))
    db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "yx_admin", "Parol123!", UserRole.ADMIN, "YX Admin", company_id=1)
    auth.create_user(db, "yx_begona", "Parol123!", UserRole.ADMIN, "YX Begona", company_id=2)
for _cid in (1, 2):
    db.add(Inventory(company_id=_cid, item_name=f"YX Penoplast {_cid}", category="Penoplast", unit="blok", stock_quantity=100000.0,
                     min_stock=0, price_per_unit=600000, volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True))
    db.add(Inventory(company_id=_cid, item_name=f"YX Kley {_cid}", category="Kimyoviy qo'shimchalar", unit="kg",
                     stock_quantity=1000000.0, min_stock=0, price_per_unit=3000, volume_per_unit=1.0))
    db.add(Inventory(company_id=_cid, item_name=f"YX Qum {_cid}", category="Qattiq qotishmalar", unit="kg",
                     stock_quantity=1000000.0, min_stock=0, price_per_unit=800, volume_per_unit=1.0))
_ishga = datetime(2026, 1, 1)
for _nom, _pt, _rate, _ut in (("YX Qoplamachi", PayType.FIXED_PLUS_COATING, 1000, "metr"), ("YX Kesuvchi", PayType.PER_UNIT, 20000, "blok"),
                              ("YX Metrchi", PayType.PER_UNIT, 500, "metr"), ("YX Donachi", PayType.PER_UNIT, 300, "dona")):
    db.add(Employee(company_id=1, name=_nom, position="Sinov", pay_type=_pt, fixed_amount=0, per_unit_rate=_rate, per_unit_type=_ut,
                    hire_date=_ishga, is_active=True))
db.add(Employee(company_id=2, name="YX Begona qoplamachi", position="Sinov", pay_type=PayType.FIXED_PLUS_COATING, fixed_amount=0,
                per_unit_rate=1000, per_unit_type="metr", hire_date=_ishga, is_active=True))
db.commit()
PENO = {c: db.query(Inventory).filter(Inventory.company_id == c, Inventory.is_penoplast.is_(True)).first().id for c in (1, 2)}
KLEY = {c: db.query(Inventory).filter(Inventory.company_id == c, Inventory.item_name.like("YX Kley%")).first().id for c in (1, 2)}
QUM = {c: db.query(Inventory).filter(Inventory.company_id == c, Inventory.item_name.like("YX Qum%")).first().id for c in (1, 2)}
db.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c


C1, C2 = mijoz("yx_admin"), mijoz("yx_begona")
TAYYOR = {}
for _cid, _c in ((1, C1), (2, C2)):
    _r = _c.post("/api/recipes", json={"name": f"YX Qoplama {_cid}", "batch_size_kg": 100, "notes": "",
                                       "ingredients": [{"inventory_id": KLEY[_cid], "quantity_kg": 30},
                                                       {"inventory_id": QUM[_cid], "quantity_kg": 70}]})
    _rc = (js(_r) or {}).get("id")
    _m = _c.post("/api/masters", json={"name": f"YX Usta {_cid}", "phone": f"+99890000{_cid}201", "cashback_percent": 5,
                                       "kpi_percent": 0, "region": "Andijon", "notes": ""})
    _p = _c.post("/api/projects", json={"project_name": f"YX Loyiha {_cid}", "client_name": f"YX Mijoz {_cid}",
                                        "client_phone": f"+99890000{_cid}202", "client_address": "Andijon", "description": "",
                                        "notes": ""})
    TAYYOR[_cid] = {"retsept": _rc, "usta": (js(_m) or {}).get("id"), "loyiha": (js(_p) or {}).get("id")}
check("D0 tayyorgarlik: ikki korxonada retsept, usta, loyiha (API)",
      all(TAYYOR[c][k] for c in (1, 2) for k in ("retsept", "usta", "loyiha")), TAYYOR)


def detal(nom, kat, *, w=0, t=0, l=0, q=1, narx=10000, qop=True, cid=1, ichki=None):
    d = {"name": nom, "category": kat, "width": w, "thickness": t, "length": l, "quantity": q, "unit_price": narx,
         "is_coated": qop, "penoplast_id": PENO[cid], "price_per_m3": None, "finished_product_id": None}
    d["sub_details"] = ichki or []
    return d


def buyurtma(detallar, cid=1):
    c = C1 if cid == 1 else C2
    _qop = any(d["is_coated"] or any(s.get("is_coated") for s in d.get("sub_details") or []) for d in detallar)
    tana = {"project_id": TAYYOR[cid]["loyiha"], "order_type": "product", "recipe_id": TAYYOR[cid]["retsept"],
            "master_id": TAYYOR[cid]["usta"], "deadline": None, "is_draft": False, "base_price": 600000,
            "loy_kg": 10 if _qop else 0, "items": detallar}
    r = c.post("/api/orders", json=tana)
    if r.status_code == 409:
        r = c.post("/api/orders?confirm_shortage=true", json=tana)
    j = js(r) or {}
    items = sorted((j.get("items") or []), key=lambda x: x["id"])
    return j.get("id"), [x["id"] for x in items], r.status_code


def yuk(oid, qatorlar, cid=1):
    c = C1 if cid == 1 else C2
    r = c.post("/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": i, "quantity": q} for i, q in qatorlar],
                                        "received_by": "YX Qabul", "notes": "YX"})
    j = js(r) or {}
    return j.get("delivery_id") or j.get("id"), r.status_code


def tayyor(oid, cid=1):
    c = C1 if cid == 1 else C2
    r = c.post(f"/api/orders/{oid}/ready")
    return r.status_code, js(r)


def sana_yuk(did, dt):
    s = SessionLocal()
    s.query(Delivery).filter(Delivery.id == did).update({Delivery.delivered_at: dt}, synchronize_session=False)
    s.commit()
    s.close()


def sana_yopish(oid, dt):
    s = SessionLocal()
    s.query(Order).filter(Order.id == oid).update({Order.completed_at: dt}, synchronize_session=False)
    s.commit()
    s.close()


def buyurtma_yuklari(oid):
    s = SessionLocal()
    r = [d.id for d in s.query(Delivery).filter(Delivery.order_id == oid).order_by(Delivery.id).all()]
    s.close()
    return r


def hisob(y, m, cid=1):
    """Oylik hisobot (xotirasiz) — hodimlar haqi va qoplamachi / blok jamlari."""
    try:
        services.hisobot_xotirasini_tozala()
    except Exception:                              # noqa: BLE001 — asl kodda ham bor
        pass
    s = SessionLocal()
    try:
        rep = services.get_monthly_report(s, y, m, company_id=cid)
    except Exception as e:                         # noqa: BLE001 — asl / buzilgan kodda qulamasin
        s.close()
        return {"xato": f"{type(e).__name__}: {e}"}
    s.close()
    pay = {r["name"]: float(r["amount"]) for r in rep.get("hodimlar_moslashuvchan_breakdown") or []}
    return {"qop": pay.get("YX Qoplamachi", 0.0), "kes": pay.get("YX Kesuvchi", 0.0), "met": pay.get("YX Metrchi", 0.0),
            "don": pay.get("YX Donachi", 0.0), "begona": pay.get("YX Begona qoplamachi", 0.0),
            "bonus": float(rep.get("qoplamachi_bonus_avtomatik") or 0), "blok": float(rep.get("jami_blok") or 0)}


def toza_hisob(cid=1):
    """Barcha sinov oylari — keyingi bo'limlar faqat O'Z buyurtmalari ta'sirini (farqni) o'lchaydi."""
    return {ym: hisob(*ym, cid=cid) for ym in ((2026, 8), (2026, 9), (2026, 10), (2026, 11), (2026, 12), (2027, 1))}


def farq(oldin, keyin, ym, k):
    a, b = oldin.get(ym) or {}, keyin.get(ym) or {}
    if "xato" in a or "xato" in b:
        return None
    return round(float(b.get(k, 0)) - float(a.get(k, 0)), 4)


def kun(y, m, d, soat=7):
    return datetime(y, m, d, soat, 0, 0)          # UTC — Toshkent 12:00 (oy chegarasidan uzoq)


# ── A. Egasining misoli ──────────────────────────────────────────────────────────────────────────────────────────
section("A. 100 m qoplamali karniz: 60 m noyabrda, 40 m dekabrda — har yuk xati o'z oyiga; «Tayyor» dekabrda — noyabr o'zgarmaydi")
H0 = toza_hisob()
oA, iA, stA = buyurtma([detal("YX Karniz A", "profil", w=20, t=15, l=100, q=1, narx=400000)])
yA1, _s1 = yuk(oA, [(iA[0], 60)]) if oA else (None, 0)
yA2, _s2 = yuk(oA, [(iA[0], 40)]) if oA else (None, 0)
check("A0 buyurtma (200) va ikki yuk xati (60 m, 40 m — 200)", oA and stA == 200 and _s1 == 200 and _s2 == 200 and yA1 and yA2,
      (stA, _s1, _s2))
if yA1 and yA2:
    sana_yuk(yA1, kun(2026, 11, 25))
    sana_yuk(yA2, kun(2026, 12, 5))
_s = SessionLocal()
_ul = [getattr(x, "ulush", "ustun yo'q") for x in _s.query(DeliveryItem).join(Delivery, Delivery.id == DeliveryItem.delivery_id).filter(
    Delivery.order_id == oA).order_by(DeliveryItem.id).all()] if oA else []
_s.close()
check("A1 yuk paytidagi ulush yozildi: 60 / 100 = 0,6 va 40 / 100 = 0,4", len(_ul) == 2 and yaqin(_ul[0], 0.6, 1e-9)
      and yaqin(_ul[1], 0.4, 1e-9), _ul)
H1 = toza_hisob()
_hajm_blok = 0.20 * 0.15 / 2 * 100               # profil hajmi (m³), 1 blok = 1 m³
check("A2 noyabr: qoplamachi 60 m × 1 000 = 60 000; metrchi 60 × 500 = 30 000; kesuvchi 0,9 blok × 20 000 = 18 000 "
      "(buyurtma hali «Tayyor» EMAS)",
      yaqin(farq(H0, H1, (2026, 11), "qop"), 60000) and yaqin(farq(H0, H1, (2026, 11), "met"), 30000)
      and yaqin(farq(H0, H1, (2026, 11), "kes"), round(_hajm_blok * 0.6 * 20000)),
      {k: farq(H0, H1, (2026, 11), k) for k in ("qop", "met", "kes", "blok")})
check("A3 dekabr: qoplamachi 40 000; metrchi 20 000; kesuvchi 0,6 blok × 20 000 = 12 000",
      yaqin(farq(H0, H1, (2026, 12), "qop"), 40000) and yaqin(farq(H0, H1, (2026, 12), "met"), 20000)
      and yaqin(farq(H0, H1, (2026, 12), "kes"), round(_hajm_blok * 0.4 * 20000)),
      {k: farq(H0, H1, (2026, 12), k) for k in ("qop", "met", "kes", "blok")})
_st, _ = tayyor(oA) if oA else (0, None)
if oA:
    sana_yopish(oA, kun(2026, 12, 20))
H2 = toza_hisob()
check("A4 «Tayyor» (200) dekabrda — to'liq topshirilgan: qo'shimcha 0; noyabr va dekabr AYNAN avvalgidek (jami 100 000)",
      _st == 200 and all(yaqin(farq(H1, H2, ym, k), 0, 0.01) for ym in ((2026, 11), (2026, 12)) for k in ("qop", "kes", "met"))
      and yaqin(farq(H0, H2, (2026, 11), "qop") + farq(H0, H2, (2026, 12), "qop"), 100000),
      (_st, {ym: {k: farq(H0, H2, ym, k) for k in ("qop", "kes")} for ym in ((2026, 11), (2026, 12))}))
check("A5 boshqa oylarga ta'sir yo'q (oktabr, yanvar)",
      all(yaqin(farq(H0, H2, ym, k), 0, 0.01) for ym in ((2026, 10), (2027, 1)) for k in ("qop", "kes", "met", "don")),
      {ym: farq(H0, H2, ym, "qop") for ym in ((2026, 10), (2027, 1))})
_api = {}
for _ym in ((2026, 11), (2026, 12)):
    _ra = C1.get(f"/api/finance/report?year={_ym[0]}&month={_ym[1]}")
    _ja = js(_ra) or {}
    _api[_ym] = (_ra.status_code, {r.get("name"): round(float(r.get("amount") or 0)) for r in _ja.get("hodimlar_moslashuvchan_breakdown") or []
                                   if str(r.get("name") or "").startswith("YX ")})
check("A6 egasi ko'radigan yo'l — «Moliya» hisoboti (`/api/finance/report`, 200): noyabr / dekabr qoplamachi, kesuvchi, metrchi AYNAN "
      "hisob bilan (0 so'mlik hodim ro'yxatda bo'lmasa — 0)",
      all(_api[ym][0] == 200 and all(yaqin(_api[ym][1].get(n, 0), (H2.get(ym) or {}).get(k), 1.0)
                                    for n, k in (("YX Qoplamachi", "qop"), ("YX Kesuvchi", "kes"), ("YX Metrchi", "met")))
          for ym in _api),
      (_api, {ym: H2.get(ym) for ym in _api}))

# ── B. 1-oktabrgacha topshirilgan qism ───────────────────────────────────────────────────────────────────────────
section("B. Oktabrgacha topshirilgan (qo'lda to'langan) qism qayta hisoblanmaydi")
H0 = toza_hisob()
oB, iB, stB = buyurtma([detal("YX Panel B", "panel", w=60, t=5, l=0, q=100, narx=20000)])
yB1, _ = yuk(oB, [(iB[0], 90)]) if oB else (None, 0)
yB2, _ = yuk(oB, [(iB[0], 10)]) if oB else (None, 0)
if yB1 and yB2:
    sana_yuk(yB1, kun(2026, 9, 20))
    sana_yuk(yB2, kun(2026, 10, 12))
_stB, _ = tayyor(oB) if oB else (0, None)
if oB:
    sana_yopish(oB, kun(2026, 10, 15))
oB2, iB2, _ = buyurtma([detal("YX Dona B2", "dona", w=10, t=10, l=2, q=50, narx=5000)])
yB3, _ = yuk(oB2, [(iB2[0], 30)]) if oB2 else (None, 0)
if yB3:
    sana_yuk(yB3, kun(2026, 9, 25))
_stB2, _jB2 = tayyor(oB2) if oB2 else (0, None)
if oB2:
    sana_yopish(oB2, kun(2026, 10, 20))
H1 = toza_hisob()
check("B1 panel 100 m: 90 m sentabrda, 10 m oktabrda, oktabrda «Tayyor» — oktabr FAQAT 10 m (10 000), sentabr 0 (eski qoida — "
      "buyurtma sentabrda tayyor emas)",
      _stB == 200 and yaqin(farq(H0, H1, (2026, 10), "qop"), 10000) and yaqin(farq(H0, H1, (2026, 10), "met"), 5000)
      and yaqin(farq(H0, H1, (2026, 9), "qop"), 0, 0.01), {ym: farq(H0, H1, ym, "qop") for ym in ((2026, 9), (2026, 10))})
_s = SessionLocal()
_qB2 = _s.query(OrderItem.quantity).filter(OrderItem.id == (iB2[0] if iB2 else -1)).scalar()
_s.close()
check("B2 dona 50 dan 30 tasi sentabrda, oktabrda qisman «Tayyor» — miqdor 30 ga qisqardi (mijoz faqat olganiga to'laydi), qolgan "
      "qism yo'q: oktabrga qo'shimcha 0 (B1 dagi 10 000 dan tashqari); donachi 0",
      _stB2 == 200 and yaqin(_qB2, 30, 1e-9) and yaqin(farq(H0, H1, (2026, 10), "qop"), 10000)
      and yaqin(farq(H0, H1, (2026, 10), "don"), 0, 0.01),
      (_stB2, _qB2, {k: farq(H0, H1, (2026, 10), k) for k in ("qop", "don")}))

# ── C. Yuk xatisiz «Tayyor» ─────────────────────────────────────────────────────────────────────────────────────
section("C. Yuk xatisiz «Tayyor» (avtomatik yuk xati) — yopilgan oyga 100 %")
H0 = toza_hisob()
oC, iC, _ = buyurtma([detal("YX Karniz C", "profil", w=20, t=15, l=30, q=1, narx=120000)])
_stC, _ = tayyor(oC) if oC else (0, None)
_yC = buyurtma_yuklari(oC) if oC else []
if oC and _yC:
    sana_yopish(oC, kun(2026, 11, 15, 8))
    sana_yuk(_yC[0], kun(2026, 11, 15, 7))
H1 = toza_hisob()
check("C1 «Tayyor» (200) avtomatik yuk xati bilan; yuk yopilishdan oldin — noyabr +30 m (30 000), boshqa oylar 0",
      _stC == 200 and len(_yC) == 1 and yaqin(farq(H0, H1, (2026, 11), "qop"), 30000)
      and all(yaqin(farq(H0, H1, ym, "qop"), 0, 0.01) for ym in ((2026, 10), (2026, 12))),
      (_stC, _yC, {ym: farq(H0, H1, ym, "qop") for ym in ((2026, 10), (2026, 11), (2026, 12))}))
if _yC:
    sana_yuk(_yC[0], kun(2026, 11, 15, 9))
H2 = toza_hisob()
check("C2 avtomatik yuk vaqti yopilishdan KEYIN bo'lsa ham AYNAN: yuk xati hisoblanmaydi, yopilganda qolgani (100 %) — noyabr 30 000",
      yaqin(farq(H0, H2, (2026, 11), "qop"), 30000) and yaqin(farq(H1, H2, (2026, 11), "kes"), 0, 0.01),
      {k: farq(H0, H2, (2026, 11), k) for k in ("qop", "kes")})

# ── D. Qaytarish ─────────────────────────────────────────────────────────────────────────────────────────────────
section("D. Qaytarish haqni kamaytirmaydi")
H0 = toza_hisob()
oD, iD, _ = buyurtma([detal("YX Karniz D", "profil", w=20, t=15, l=20, q=1, narx=80000)])
yD, _ = yuk(oD, [(iD[0], 20)]) if oD else (None, 0)
if yD:
    sana_yuk(yD, kun(2026, 11, 20))
H1 = toza_hisob()
_rD = C1.post("/api/returns", json={"order_id": oD, "order_item_id": iD[0] if iD else 0, "item_name": "YX Karniz D", "quantity": 5,
                                     "unit": "metr", "reason": "Mijoz iltimosi", "refund_amount": 0, "to_stock": True}) if oD else None
H2 = toza_hisob()
check("D1 20 m topshirildi (noyabr +20 000); 5 m qaytarildi (200) — noyabr ham, keyingi oylar ham O'ZGARMAYDI",
      yaqin(farq(H0, H1, (2026, 11), "qop"), 20000) and _rD is not None and _rD.status_code in (200, 201)
      and all(yaqin(farq(H1, H2, ym, k), 0, 0.01) for ym in ((2026, 10), (2026, 11), (2026, 12)) for k in ("qop", "kes", "met")),
      (farq(H0, H1, (2026, 11), "qop"), _rD.status_code if _rD is not None else None, (_rD.text[:200] if _rD is not None else ""),
       {ym: farq(H1, H2, ym, "qop") for ym in ((2026, 10), (2026, 11), (2026, 12))}))

# ── E. Yopilgandan keyingi yuk xati ─────────────────────────────────────────────────────────────────────────────
section("E. Yopilgandan KEYINGI yuk xati hisoblanmaydi (yopilganda qolgani yozilgan)")
H0 = toza_hisob()
oE, iE, _ = buyurtma([detal("YX Karniz E", "profil", w=20, t=15, l=50, q=1, narx=200000)])
yE1, _ = yuk(oE, [(iE[0], 30)]) if oE else (None, 0)
yE2, _ = yuk(oE, [(iE[0], 20)]) if oE else (None, 0)
_stE, _ = tayyor(oE) if oE else (0, None)
if yE1 and yE2:
    sana_yuk(yE1, kun(2026, 10, 3))
    sana_yuk(yE2, kun(2026, 11, 5))
    sana_yopish(oE, kun(2026, 10, 10))
H1 = toza_hisob()
check("E1 30 m 3-oktabrda, «Tayyor» 10-oktabrda, 20 m 5-noyabrda (yopilgandan keyin): oktabr 30 + qolgan 20 = 50 000, noyabr 0",
      _stE == 200 and yaqin(farq(H0, H1, (2026, 10), "qop"), 50000) and yaqin(farq(H0, H1, (2026, 11), "qop"), 0, 0.01),
      (_stE, {ym: farq(H0, H1, ym, "qop") for ym in ((2026, 10), (2026, 11))}))

# ── F. Ichki qo'shimcha detal ───────────────────────────────────────────────────────────────────────────────────
section("F. Ichki qo'shimcha detal — yuk PAYTIDAGI ulush; qisman yopilgandan keyin o'tgan oy O'ZGARMAYDI")
H0 = toza_hisob()
oF, iF, stF = buyurtma([detal("YX Karniz F", "profil", w=20, t=15, l=100, q=1, narx=400000,
                              ichki=[{"name": "YX ichki", "category": "profil", "width": 5, "thickness": 5, "length": 2,
                                      "quantity": 10, "is_coated": True}])])
yF, _ = yuk(oF, [(iF[0], 60)]) if oF else (None, 0)
if yF:
    sana_yuk(yF, kun(2026, 11, 10))
H1 = toza_hisob()
check("F1 asosiy 60 m + ichki (2 m × 10 = 20 m) × 0,6 = 12 m — noyabr 72 000 (buyurtma ochiq)",
      stF == 200 and yaqin(farq(H0, H1, (2026, 11), "qop"), 72000), (stF, farq(H0, H1, (2026, 11), "qop")))
_stF, _ = tayyor(oF) if oF else (0, None)
if oF:
    sana_yopish(oF, kun(2026, 12, 15))
H2 = toza_hisob()
_s = SessionLocal()
_lF = _s.query(OrderItem.length).filter(OrderItem.id == (iF[0] if iF else -1)).scalar()
_s.close()
check("F2 dekabrda qisman «Tayyor» (asosiy uzunlik 100 → 60): noyabr AYNAN 72 000 (o'zgarmadi); dekabr — ichki detal qolgani 0,4 × 20 = "
      "8 m (8 000); jami asosiy 60 + ichki 20",
      _stF == 200 and yaqin(_lF, 60, 1e-9) and yaqin(farq(H0, H2, (2026, 11), "qop"), 72000)
      and yaqin(farq(H0, H2, (2026, 12), "qop"), 8000),
      (_stF, _lF, {ym: farq(H0, H2, ym, "qop") for ym in ((2026, 11), (2026, 12))}))
_s = SessionLocal()
_itF = _s.query(OrderItem).filter(OrderItem.id == (iF[0] if iF else -1)).first()
_vF_ichki = services._sub_details_volume_m3(_itF) if _itF is not None else 0
_vF = 0.20 * 0.15 / 2 * 60
_s.close()
check("F3 kesuvchi: noyabr (asosiy 60 m hajmi + ichki hajm × 0,6) × 20 000, dekabr — ichki hajm × 0,4 × 20 000",
      yaqin(farq(H0, H2, (2026, 11), "kes"), round((_vF + _vF_ichki * 0.6) * 20000), 1.01)
      and yaqin(farq(H0, H2, (2026, 12), "kes"), round(_vF_ichki * 0.4 * 20000), 1.01),
      ({ym: farq(H0, H2, ym, "kes") for ym in ((2026, 11), (2026, 12))}, _vF, _vF_ichki))

# ── G. Qoplamasiz detal ─────────────────────────────────────────────────────────────────────────────────────────
section("G. Qoplamasiz detal — qoplamachiga yo'q, kesilgan blokka bor")
H0 = toza_hisob()
oG, iG, _ = buyurtma([detal("YX Panel G", "panel", w=60, t=5, l=0, q=40, narx=15000, qop=False)])
yG, _ = yuk(oG, [(iG[0], 40)]) if oG else (None, 0)
if yG:
    sana_yuk(yG, kun(2026, 11, 12))
H1 = toza_hisob()
check("G1 qoplamasiz panel 40 m noyabrda: qoplamachi / metrchi 0, kesuvchi 0,6 × 0,05 × 40 = 1,2 blok × 20 000 = 24 000",
      yaqin(farq(H0, H1, (2026, 11), "qop"), 0, 0.01) and yaqin(farq(H0, H1, (2026, 11), "met"), 0, 0.01)
      and yaqin(farq(H0, H1, (2026, 11), "kes"), 24000), {k: farq(H0, H1, (2026, 11), k) for k in ("qop", "met", "kes")})

# ── H. Begona korxona ────────────────────────────────────────────────────────────────────────────────────────────
section("H. Begona korxona yuk xatlari kirmaydi")
H0 = toza_hisob(1)
H0b = toza_hisob(2)
oH, iH, stH = buyurtma([detal("YX Begona karniz", "profil", w=20, t=15, l=40, q=1, narx=160000, cid=2)], cid=2)
yH, _ = yuk(oH, [(iH[0], 40)], cid=2) if oH else (None, 0)
if yH:
    sana_yuk(yH, kun(2026, 11, 18))
H1 = toza_hisob(1)
H1b = toza_hisob(2)
check("H1 B korxonada 40 m noyabrda: B ning qoplamachisi +40 000, A korxona hisobotiga ta'sir yo'q",
      stH == 200 and yaqin(farq(H0b, H1b, (2026, 11), "begona"), 40000)
      and all(yaqin(farq(H0, H1, (2026, 11), k), 0, 0.01) for k in ("qop", "kes", "met", "don", "begona")),
      (stH, farq(H0b, H1b, (2026, 11), "begona"), {k: farq(H0, H1, (2026, 11), k) for k in ("qop", "kes", "begona")}))

# ── I. Chegaradan oldingi oy — eski qoida ───────────────────────────────────────────────────────────────────────
section("I. Sentabr (chegaradan oldingi oy) — eski qoida")
H0 = toza_hisob()
oI, iI, _ = buyurtma([detal("YX Karniz I", "profil", w=20, t=15, l=25, q=1, narx=100000)])
yI, _ = yuk(oI, [(iI[0], 25)]) if oI else (None, 0)
_stI, _ = tayyor(oI) if oI else (0, None)
if oI and yI:
    sana_yuk(yI, kun(2026, 8, 20))
    sana_yopish(oI, kun(2026, 9, 10))
H1 = toza_hisob()
check("I1 yuk xati avgustda, «Tayyor» sentabrda: avgust 0, sentabr 25 000 (100 % — eski qoida: yopilgan oyga), oktabr 0",
      _stI == 200 and yaqin(farq(H0, H1, (2026, 8), "qop"), 0, 0.01) and yaqin(farq(H0, H1, (2026, 9), "qop"), 25000)
      and yaqin(farq(H0, H1, (2026, 10), "qop"), 0, 0.01),
      (_stI, {ym: farq(H0, H1, ym, "qop") for ym in ((2026, 8), (2026, 9), (2026, 10))}))

# ── N. So'rovlar soni ───────────────────────────────────────────────────────────────────────────────────────────
section("N. So'rovlar soni buyurtmalar soniga bog'liq emas (hisobot keshi bilan)")
_SANOQ = [0]


@event.listens_for(engine, "before_cursor_execute")
def _sanoq(conn, cursor, statement, parameters, context, executemany):   # noqa: ARG001
    _SANOQ[0] += 1
    if os.environ.get("YX_TASHXIS"):
        _MATN.append(" ".join(statement.split())[:160])


_MATN = []


def sorovlar(y, m):
    try:
        services.hisobot_xotirasini_tozala()
    except Exception:                              # noqa: BLE001
        pass
    s = SessionLocal()
    _SANOQ[0] = 0
    try:
        with services.hisobot_keshi(s) if hasattr(services, "hisobot_keshi") else contextlib.nullcontext():
            services.get_monthly_report(s, y, m, company_id=1)
    except Exception:                              # noqa: BLE001
        pass
    n = _SANOQ[0]
    s.close()
    return n


def _n_buyurtma(k):
    _o, _i, _ = buyurtma([detal(f"YX N{k}", "profil", w=20, t=15, l=10, q=1, narx=40000,
                                ichki=[{"name": "n", "category": "panel", "width": 5, "thickness": 5, "length": 0, "quantity": 3,
                                        "is_coated": True}])])
    _y, _ = yuk(_o, [(_i[0], 4)]) if _o else (None, 0)
    if _y:
        sana_yuk(_y, kun(2027, 1, 10 + k))


_n_buyurtma(0)
_n1 = sorovlar(2027, 1)
for _k in range(1, 5):
    _n_buyurtma(_k)
_MATN.clear()
_n5 = sorovlar(2027, 1)
if os.environ.get("YX_TASHXIS"):
    from collections import Counter as _Ct
    for _q, _c in _Ct(_MATN).most_common(40):
        print("   ", _c, _q)
_h = hisob(2027, 1)
check("N1 yanvarda 1 → 5 ta yuk xatili buyurtma — hisobot so'rovlari soni O'ZGARMAYDI (bo'laklab o'qiladi); natija: "
      "5 × (4 m + ichki 0,4 × 3 m) = 26 m → 26 000",
      _n5 == _n1 and yaqin(_h.get("qop"), 26000) and yaqin(_h.get("bonus"), 26000, 1.0), (_n1, _n5, _h))

# ── M. Yangilanish: shu kodgacha yozilgan yuk xatlari ────────────────────────────────────────────────────────────
section("M. Yangilanish — `ulush` ustunisiz baza (zip 142) → ustun qo'shiladi, ochiq buyurtmalar yuklari to'ldiriladi")
oM, iM, stM = buyurtma([detal("YX Karniz M", "profil", w=20, t=15, l=100, q=1, narx=400000,
                              ichki=[{"name": "YX ichki M", "category": "profil", "width": 5, "thickness": 5, "length": 2,
                                      "quantity": 10, "is_coated": True}])])
yM, _ = yuk(oM, [(iM[0], 60)]) if oM else (None, 0)
if yM:
    sana_yuk(yM, kun(2026, 11, 8))


def _ulushlar():
    s = SessionLocal()
    try:
        return {r[0]: (r[1], r[2]) for r in s.query(DeliveryItem.id, DeliveryItem.ulush, Order.status).join(
            Delivery, Delivery.id == DeliveryItem.delivery_id).join(Order, Order.id == Delivery.order_id).all()}
    except Exception as ex:                        # noqa: BLE001 — ustun yo'q / asl kod
        s.rollback()
        return {"xato": f"{type(ex).__name__}: {str(ex)[:200]}"}
    finally:
        s.close()


_U0 = _ulushlar()
_mig_x = ""
_n1 = _n2 = None
try:
    from sqlalchemy import text as _tx143, inspect as _in143
    import database as _dbm143
    with engine.connect() as _cn:
        _cn.execute(_tx143("ALTER TABLE delivery_items DROP COLUMN ulush"))
        _cn.commit()
    _yoq = "ulush" not in {c["name"] for c in _in143(engine).get_columns("delivery_items")}
    with contextlib.redirect_stdout(_quiet):
        _dbm143.sync_missing_columns()
        _n1 = main._migrate_yuk_xati_ulush()
        _n2 = main._migrate_yuk_xati_ulush()
    _bor = "ulush" in {c["name"] for c in _in143(engine).get_columns("delivery_items")}
except Exception as _e:                            # noqa: BLE001 — asl kodda migratsiya yo'q
    _yoq = _bor = False
    _mig_x = f"{type(_e).__name__}: {str(_e)[:300]}"
_U1 = _ulushlar()
_ochiq = {k: v for k, v in _U0.items() if k != "xato" and v[1] != OrderStatus.READY}
_yopiq = {k: v for k, v in _U0.items() if k != "xato" and v[1] == OrderStatus.READY}
check("M1 ustun o'chirildi → ishga tushish (`sync_missing_columns` + `_migrate_yuk_xati_ulush`): ustun qaytdi; ochiq buyurtmalar "
      "yuklari AYNAN avvalgi ulush bilan (shu jumladan M: 0,6), «Tayyor» buyurtmalarniki NULL",
      _yoq and _bor and "xato" not in _U1 and len(_ochiq) >= 3 and _n1 == len([v for v in _ochiq.values() if v[0] is not None])
      and all(_U1.get(k, (None,))[0] is not None and yaqin(_U1[k][0], v[0], 1e-9) for k, v in _ochiq.items() if v[0] is not None)
      and all(_U1.get(k, (0,))[0] is None for k in _yopiq),
      (_mig_x, _yoq, _bor, _n1, len(_ochiq), len(_yopiq), [(k, v[0], _U1.get(k)) for k, v in list(_ochiq.items())[:6]]))
check("M2 migratsiya qayta ishga tushsa — 0 qator (IDEMPOTENT)", _n2 == 0, _n2)
H0 = toza_hisob()
_stM, _ = tayyor(oM) if oM else (0, None)
if oM:
    sana_yopish(oM, kun(2026, 12, 10))
H1 = toza_hisob()
check("M3 eski (to'ldirilgan) yuk xatli buyurtma dekabrda qisman «Tayyor»: noyabr O'ZGARMAYDI, dekabr — ichki qolgani 0,4 × 20 = 8 000",
      _stM == 200 and yaqin(farq(H0, H1, (2026, 11), "qop"), 0, 0.01) and yaqin(farq(H0, H1, (2026, 12), "qop"), 8000),
      (_stM, {ym: farq(H0, H1, ym, "qop") for ym in ((2026, 11), (2026, 12))}))

# ── U. «Hodimlar» oynasi (brauzer) ───────────────────────────────────────────────────────────────────────────────
section("U. «Hodimlar» oynasi — «Har birlik uchun» va «qoplama qo'shimchasi» izohi (brauzer, kompyuter va telefon)")
try:
    from playwright.sync_api import sync_playwright
    _pw_bor, _pw_x = True, ""
except Exception as _e:                            # noqa: BLE001
    _pw_bor, _pw_x = False, f"{type(_e).__name__}: {_e}"
import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


_srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=_port(), log_level="critical", lifespan="off"))
threading.Thread(target=_srv.run, daemon=True).start()
for _ in range(150):
    if _srv.started:
        break
    time.sleep(0.1)
_pw = _br = None
if _pw_bor and _srv.started:
    _pw = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                              "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        _br = _pw.chromium.launch(executable_path=_exe) if _exe else _pw.chromium.launch()
    except Exception as _e:                        # noqa: BLE001
        _br, _pw_x = None, f"{type(_e).__name__}: {_e}"
check("U0 lokal server va Chromium", bool(_srv.started and _br), _pw_x)
_JS_XATO = []
_UI = {}
_IZOH_JS = """() => {
  const ko = id => { const e = document.getElementById(id); if (!e) return null; const r = e.getBoundingClientRect();
    return {k: r.width > 0 && r.height > 0 && getComputedStyle(e).display !== 'none', m: (e.innerText || '').trim(),
            fs: parseFloat(getComputedStyle(e).fontSize), o: r.right <= innerWidth + 1}; };
  const coat = document.querySelector('#e-coating-wrap');
  const coatIzoh = coat ? [...coat.querySelectorAll('div')].map(d => (d.innerText || '').trim()).filter(t => /yuk xatida/.test(t)) : [];
  return {izoh: ko('e-unit-izoh'), birlik: ko('e-unit-wrap'), qop: ko('e-coating-wrap'), qop_izoh: coatIzoh,
          yon: document.documentElement.scrollWidth <= innerWidth + 1};
}"""
if _br:
    for _w, _h, _tel in ((1440, 900, False), (390, 844, True)):
        _ctx = _br.new_context(viewport={"width": _w, "height": _h}, device_scale_factor=1, is_mobile=_tel, has_touch=_tel,
                               timezone_id="Asia/Tashkent", locale="uz-UZ")
        _ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                              r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), lambda route: route.fulfill(status=204, body=""))
        _pg = _ctx.new_page()
        _pg.set_default_timeout(8000)
        _pg.on("pageerror", lambda e, w=_w: _JS_XATO.append((w, str(e)[:200])))
        try:
            _B = f"http://127.0.0.1:{_srv.config.port}"
            _pg.goto(_B + "/login")
            _pg.fill("input[name=username]", "yx_admin")
            _pg.fill("input[name=password]", "Parol123!")
            _pg.press("input[name=password]", "Enter")
            _pg.wait_for_load_state("networkidle")
            _pg.goto(_B + "/kpi", wait_until="networkidle")
            _pg.evaluate("() => openEmpModal()")
            _pg.wait_for_selector("#empModal", state="visible")
            for _tur in ("fixed", "per_unit", "fixed_plus_coating"):
                _pg.select_option("#e-paytype", _tur)
                _pg.wait_for_timeout(150)
                _UI[(_w, _tur)] = _pg.evaluate(_IZOH_JS)
        except Exception as _e:                    # noqa: BLE001
            _UI[(_w, "xato")] = f"{type(_e).__name__}: {str(_e)[:300]}"
        _ctx.close()


def _ui(w, tur):
    v = _UI.get((w, tur))
    return v if isinstance(v, dict) else {}


for _w in (1440, 390):
    _pu, _fx, _fc = _ui(_w, "per_unit"), _ui(_w, "fixed"), _ui(_w, "fixed_plus_coating")
    _iz = _pu.get("izoh") or {}
    check(f"U1 [{_w}] «Har birlik uchun» tanlanganda izoh KO'RINADI (yuk xati oyiga, «Tayyor» — yopilgan oyga; 12 px, ekrandan "
          f"chiqmaydi); «Doimiy oylik» va «qoplama» da — yashirin",
          bool(_iz.get("k")) and "yuk xatida" in (_iz.get("m") or "") and "yopilgan oyga" in (_iz.get("m") or "")
          and _iz.get("fs") == 12 and _iz.get("o") and _pu.get("yon")
          and not ((_fx.get("izoh") or {}).get("k")) and not ((_fc.get("izoh") or {}).get("k")),
          (_UI.get((_w, "xato")), _iz, (_fx.get("izoh") or {}).get("k"), (_fc.get("izoh") or {}).get("k")))
    check(f"U2 [{_w}] «Doimiy oylik + qoplama qo'shimchasi» izohida yuk xati qoidasi bor", bool((_fc.get("qop") or {}).get("k"))
          and any("yopilgan oyga" in t for t in _fc.get("qop_izoh") or []), (_fc.get("qop"), _fc.get("qop_izoh")))
check("U3 sahifada JS xatosi yo'q", bool(_UI) and not _JS_XATO, _JS_XATO[:5])
try:
    if _br:
        _br.close()
    if _pw:
        _pw.stop()
except Exception:                                  # noqa: BLE001
    pass
_srv.should_exit = True

# ── X. Xatolar ───────────────────────────────────────────────────────────────────────────────────────────────────
section("X. Hisobot xatosiz (har oy, ikki korxona)")
_x = [(c, ym, h.get("xato")) for c in (1, 2) for ym, h in toza_hisob(c).items() if "xato" in h]
check("X1 hisobot 2026-08 … 2027-01 — xatosiz", not _x, _x)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
