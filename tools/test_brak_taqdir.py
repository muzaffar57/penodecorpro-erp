#!/usr/bin/env python3
"""
test_brak_taqdir.py — kech125 (zip 146) darvozasi: BRAK TAQDIRI (EGASI QARORLARI 07.10, QAYTA SO'RALMAYDI).

QARORLAR: brak mahsulotning taqdiri — Tashlandi (standart) / Tuzatildi (o'sha joyiga yoki omborga) / Kesildi / 2-nav; brak
yozilganda tanlanadi, keyin o'zgartirish mumkin; Tuzatildi — zarar FAQAT tuzatish xomashyosi (0,4 kg loy ≈ 6 000); Kesildi —
Tayyor mahsulotga ULUSH tannarx bilan (30 000 lik 3 m dan 2 m → 20 000, zarar 10 000); 2-nav — Tayyor mahsulotga TO'LIQ
tannarx bilan, brak zarari yo'q, arzon sotilganda farq (15 000 − 12 000 = 3 000) SOTUV oyida. Q1: 2-nav narxi brak yozilganda;
Q2: 2-nav sotuvida «narx juda past» so'ralmaydi; Q3: «Tuzatildi — omborga» — asl narx; Q4: keyingi oyda o'zgartirilsa — pul
ta'siri O'ZGARTIRILGAN oyda (o'tgan oy o'zgarmaydi).

BO'LIMLAR
  A — egasining uch misoli AYNAN (6 000 / 10 000 / 3 000), Tashlandi — avvalgidek (taqdir qatori yo'q)
  B — uch yo'l (buyurtma detali / omborda turgan / ishlab chiqarish) × taqdirlar: Moliya «Brak» va «TM yo'qotishi» o'zgarishi,
      ombor, Tayyor mahsulot partiyasi
  C — taqdirni o'zgartirish: eskisi AYNAN qaytadi (ombor, TM, jurnal), Faoliyat jurnali
  D — hodisa vaqti (Q4): o'tgan oy hisoboti o'zgarmaydi, o'zgarish joriy oyda; tahlil = Moliya
  E — rad etishlar (400, HECH NARSA o'zgarmaydi): sotilgan TM, noto'g'ri tana, begona / yetmagan xomashyo, eski bog'lamsiz yozuv
  F — brak yozuvini o'chirish: taqdir ham «bo'lmagandek» (ombor, TM, jurnal qatorlari)
  G — korxona izolyatsiyasi; H — ruxsatlar; I — 2-nav sotuvida ogohlantirish yo'q (oddiysida bor); J — birlashtirilmaydi
  K — bitta raqam: karta = Moliya = tahlil; tahlil «Taqdir bo'yicha», yo'qotishlar taqdiri; sahifa va ro'yxat maydonlari
  L — zaxira: eksport → tiklash (taqdir qatorlari va bog'langan harakatlar bilan; PG FK tartibi)
  P — PG parallel: bir yozuvga bir vaqtda ikki taqdir — bitta faol qator, ombor / TM izchil

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi; `TENANT_FILTER=1` bilan ham (yorliq «[TF]»).
  D bo'limida yana: D4 — faqat yozuv sanasi o'tgan oyda (o'z qiymati yozuv oyiga, taqdir — hodisa oyiga), D5 — migratsiya
  belgilagan taqdirsiz eski «Brak…» kirimi brak qiymatiga kirmaydi (o'tgan oylar o'zgarmaydi).
    python3 tools/test_brak_taqdir.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_brak_taqdir.py
    TENANT_FILTER=1 python3 tools/test_brak_taqdir.py
Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import time
import tempfile
import threading
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "brak_taqdir_test"
_DB = os.path.join(tempfile.gettempdir(), "brak_taqdir_test.db")

if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
# `TENANT_FILTER=1` bilan ham yuradi (yangi so'rovlar korxona filtri himoyasidan o'tadi) — o'chirilmaydi

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, services, models            # noqa: E402

from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, OrderItem, Inventory, InventoryMovement, Recipe, RecipeIngredient, ReturnItem, FinishedProduct,
    FinishedProductLoss, FinishedProductSale, StockSource, ProductionStatus, ActivityLog,
)
from fastapi.testclient import TestClient          # noqa: E402

BrakTaqdir = getattr(models, "BrakTaqdir", None)   # asl kodda yo'q — test QULAMAYDI, tekshiruvlar yiqiladi

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF] " if os.environ.get("TENANT_FILTER") else "")
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
        self.content = b""

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


def xavfsiz(fn, standart=None):
    try:
        return fn()
    except Exception:                      # noqa: BLE001
        return standart


def teng(a, b, eps=0.01):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
#   Penoplast: 1 blok (1 m³) = 1 000 000 → profil 20×10, 1 m = 0,01 blok = 10 000 (3 m = 30 000, 1,5 m = 15 000)
#   Loy retsepti: 100 kg = 50 kg Akril (10 000) + 50 kg Kley (20 000) → 1 kg = 15 000 (0,4 kg = 6 000)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="BT Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "BT_admin", "Parol123!", UserRole.ADMIN, "BT Admin", company_id=1)
    auth.create_user(_db, "BT_admin_b", "Parol123!", UserRole.ADMIN, "BT Admin B", company_id=2)
    auth.create_user(_db, "BT_moliya", "Parol123!", UserRole.ACCOUNTANT, "BT Moliyachi", company_id=1)
    auth.create_user(_db, "BT_menejer", "Parol123!", UserRole.MANAGER, "BT Menejer", company_id=1)
PRJ = Project(company_id=1, client_name="BT Mijoz", project_name="BT loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="BT Penoplast", unit="blok", stock_quantity=1000, price_per_unit=1_000_000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
AKR = Inventory(company_id=1, item_name="BT Akril", unit="kg", stock_quantity=10_000, price_per_unit=10_000, category="Kimyo")
KLEY = Inventory(company_id=1, item_name="BT Kley", unit="kg", stock_quantity=10_000, price_per_unit=20_000, category="Kimyo")
SETKA = Inventory(company_id=1, item_name="BT Setka", unit="m", stock_quantity=0.5, price_per_unit=3_000, category="Boshqa")
PENO_B = Inventory(company_id=2, item_name="BT B Penoplast", unit="blok", stock_quantity=100, price_per_unit=400_000,
                   volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY_B = Inventory(company_id=2, item_name="BT B Kley", unit="kg", stock_quantity=100, price_per_unit=1_000, category="Kimyo")
PRJ_B = Project(company_id=2, client_name="BT B Mijoz", project_name="BT B loyiha", total_budget=0, total_paid=0)
_db.add_all([PRJ, PENO, AKR, KLEY, SETKA, PENO_B, KLEY_B, PRJ_B])
_db.commit()
R1 = Recipe(company_id=1, name="BT loy", batch_size_kg=100.0)
_db.add(R1)
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=50.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=50.0)])
_db.commit()
ID = dict(prj=PRJ.id, peno=PENO.id, akr=AKR.id, kley=KLEY.id, setka=SETKA.id, peno_b=PENO_B.id, kley_b=KLEY_B.id,
          r1=R1.id, prj_b=PRJ_B.id)
with contextlib.redirect_stdout(_quiet):
    _loy = services.get_or_create_loy_stock(_db, _db.get(Recipe, ID["r1"]))
_loy.stock_quantity = 0.0
ID["tayyor_loy"] = _loy.id
_db.commit()
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("BT_admin")
CB, _s2 = _kir("BT_admin_b")
CM, _s3 = _kir("BT_moliya")
CN, _s4 = _kir("BT_menejer")
if (_s1, _s2, _s3, _s4) != (302, 302, 302, 302):
    print(f"LOGIN BO'LMADI: {(_s1, _s2, _s3, _s4)}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_BU = datetime.utcnow() + timedelta(hours=5)          # noqa: DTZ003 — Toshkent devor soati (server kabi naive UTC)
YIL, OY = _BU.year, _BU.month
O_YIL, O_OY = (YIL - 1, 12) if OY == 1 else (YIL, OY - 1)     # o'tgan oy
K_YIL, K_OY = (YIL + 1, 1) if OY == 12 else (YIL, OY + 1)     # keyingi oy

_n = [0]


def buyurtma(uzunlik=10, narx=50_000, c=None, prj=None, peno=None):
    _n[0] += 1
    nom = f"BT Karniz {_n[0]}"
    tana = {"project_id": prj or ID["prj"], "order_type": "product", "items": [
        {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": uzunlik, "quantity": 1,
         "unit_price": narx, "is_coated": False, "penoplast_id": peno or ID["peno"]}]}
    r = req(c or C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    d = js(r) or {}
    oid = d.get("id") if isinstance(d, dict) else None
    if not oid:
        raise RuntimeError(f"buyurtma yaratilmadi: {r.status_code} {r.text[:300]}")
    s = SessionLocal()
    try:
        it = s.query(OrderItem).filter(OrderItem.order_id == oid).first()
        return oid, it.id, it.name
    finally:
        s.close()


def brak_tana(b, miqdor, taqdir=None, **qosh):
    oid, iid, nom = b
    t = {"order_id": oid, "order_item_id": iid, "item_name": nom, "quantity": miqdor, "unit": "metr",
         "brak_sabab": "boshqa", "reason": "Brak", "refund_amount": 0, "to_stock": False, "coating_applied": False}
    if taqdir is not None:
        t["taqdir"] = taqdir
    t.update(qosh)
    return t


def brak(b, miqdor, taqdir=None, c=None, **qosh):
    r = req(c or C, "post", "/api/returns", json=brak_tana(b, miqdor, taqdir, **qosh))
    d = js(r)
    return r, (d.get("id") if isinstance(d, dict) else None)


def tm_yarat(nom, miqdor=100, tannarx=1_000_000, narx=20_000, birlik_hajm=None, korxona=1, peno=None):
    s = SessionLocal()
    try:
        fp = FinishedProduct(company_id=korxona, name=nom, category="profil", is_coated=False, quantity=miqdor,
                             produced_quantity=miqdor, unit="metr", unit_price=narx, cost_price=tannarx,
                             source=StockSource.PRODUCED, penoplast_id=peno or (ID["peno"] if korxona == 1 else ID["peno_b"]),
                             unit_volume_m3=birlik_hajm, production_status=ProductionStatus.READY)
        s.add(fp)
        s.commit()
        return fp.id
    finally:
        s.close()


def taqdir_ozgar(turi, yid, tana, c=None):
    url = f"/api/returns/{yid}/taqdir" if turi == "qaytarish" else f"/api/finished/loss/{yid}/taqdir"
    return req(c or C, "post", url, json=tana)


def moliya(yil=YIL, oy=OY, c=None):
    d = js(req(c or C, "get", "/api/finance/report", params={"year": yil, "month": oy})) or {}
    return d if isinstance(d, dict) else {}


def mb(yil=YIL, oy=OY):
    """(Moliya «Brak», «TM yo'qotishi») — yaxlitlangan so'm."""
    m = moliya(yil, oy)
    return (float(m.get("brak_xarajat") or 0), float(m.get("fp_loss_xarajat") or 0))


def tahlil(yil=YIL, oy=OY, c=None):
    d = js(req(c or C, "get", "/api/reports/brak-tahlil", params={"year": yil, "month": oy, "oylar": 1})) or {}
    return d if isinstance(d, dict) else {}


def zaxira(*nomlar):
    s = SessionLocal()
    try:
        return tuple(round(float(s.get(Inventory, ID[n]).stock_quantity or 0), 6) for n in nomlar)
    finally:
        s.close()


def tm(fid):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid) if fid else None
        if f is None:
            return None
        return {"nomi": f.name, "miqdor": round(float(f.quantity or 0), 6), "birlik": f.unit,
                "tannarx": round(float(f.cost_price or 0), 2), "narx": round(float(f.unit_price or 0), 2),
                "ucs": (round(float(f.unit_cost_stable), 4) if f.unit_cost_stable is not None else None),
                "taqdir": getattr(f, "brak_taqdir", None), "manba": getattr(f.source, "value", f.source),
                "holat": getattr(f.production_status, "value", f.production_status)}
    finally:
        s.close()


def qatorlar(ri=None, fpl=None):
    """Taqdir qatorlari — [(taqdir, joy, faolmi, tm_id, tm_miqdor, tm_tannarx)] (id tartibida)."""
    if BrakTaqdir is None:
        return []
    s = SessionLocal()
    try:
        q = s.query(BrakTaqdir)
        q = q.filter(BrakTaqdir.return_item_id == ri) if ri is not None else q.filter(BrakTaqdir.fp_loss_id == fpl)
        return [(t.taqdir, t.joy, t.bekor_vaqti is None, t.tm_id, t.tm_miqdor,
                 float(t.tm_tannarx) if t.tm_tannarx is not None else None) for t in q.order_by(BrakTaqdir.id).all()]
    finally:
        s.close()


def faol(ri=None, fpl=None):
    f = [q for q in qatorlar(ri, fpl) if q[2]]
    return f[-1] if f else None


def yozuv_qiymati(turi, yid, yil=YIL, oy=OY):
    """Tahlildagi shu oy qiymati: buyurtma detali braki — `crud.brak_yozuv_qiymatlari` (Toshkent oyi), tayyor mahsulot braki —
    `crud.brak_davr_yozuvlari`. Asl kodda — None (test qulamaydi)."""
    s = SessionLocal()
    try:
        boshi, oxiri = crud._tashkent_oy_oraligi(yil, oy)
        if turi == "qaytarish":
            return round(crud.brak_yozuv_qiymatlari(s, [yid], company_id=1, start_date=boshi, end_date=oxiri)[yid], 2)
        d = crud.brak_davr_yozuvlari(s, start_date=boshi, end_date=oxiri, company_id=1)
        if yid in d["ishlab"]:
            return round(d["ishlab"][yid], 2)
        return (round(d["ombor_brak"].get(yid, 0.0), 2), round(d["ombor_tm"].get(yid, 0.0), 2))
    except Exception as e:                 # noqa: BLE001
        return f"ISTISNO {type(e).__name__}: {e}"
    finally:
        s.close()


def sanoq():
    s = SessionLocal()
    try:
        return (s.query(ReturnItem).count(), s.query(FinishedProductLoss).count(), s.query(FinishedProduct).count(),
                s.query(InventoryMovement).count(), (s.query(BrakTaqdir).count() if BrakTaqdir is not None else -1))
    finally:
        s.close()


def tm_idi(ri=None, fpl=None):
    f = faol(ri, fpl)
    return f[3] if f else None


# ══════════════════════════════════════════════════════════════
section("A — egasining uch misoli AYNAN; Tashlandi — avvalgidek")
# A0 — taqdirsiz brak: qator yo'q, zarar = xomashyo (avvalgidek)
b0 = buyurtma()
m0 = mb()
r, A0 = brak(b0, 1)
check("A0 taqdirsiz brak — 200, taqdir qatori YO'Q (Tashlandi), Moliya «Brak» +10 000 (1 m penoplasti)",
      r.status_code == 200 and BrakTaqdir is not None and qatorlar(ri=A0) == [] and teng(mb()[0] - m0[0], 10_000),
      (r.status_code, r.text[:200], qatorlar(ri=A0), mb(), m0))

# A1 — Tuzatildi (o'sha joyiga): 1 m brak, 0,4 kg loy → zarar = 6 000; penoplast qaytadi
b1 = buyurtma()
z0 = zaxira("peno", "akr", "kley")
m0 = mb()
r, A1 = brak(b1, 1, {"taqdir": "tuzatildi", "joy": "joyiga", "materiallar": [{"retsept_id": ID["r1"], "miqdor": 0.4}]})
z1 = zaxira("peno", "akr", "kley")
check("A1 Tuzatildi (o'sha joyiga, 0,4 kg loy): 200; zarar = FAQAT tuzatish loyi = 6 000 (Moliya «Brak» +6 000)",
      r.status_code == 200 and teng(mb()[0] - m0[0], 6_000) and yozuv_qiymati("qaytarish", A1) == 6_000,
      (r.status_code, r.text[:300], mb(), m0, yozuv_qiymati("qaytarish", A1) if A1 else None))
check("A1b detal ishlatildi — penoplast QAYTDI (o'zgarmadi), loy xomashyosi: Akril −0,2, Kley −0,2",
      teng(z1[0], z0[0], 1e-6) and teng(z0[1] - z1[1], 0.2, 1e-6) and teng(z0[2] - z1[2], 0.2, 1e-6), (z0, z1))
check("A1c taqdir qatori: Tuzatildi, o'sha joyiga, faol; Tayyor mahsulotga hech narsa o'tmagan",
      qatorlar(ri=A1) == [("tuzatildi", "joyiga", True, None, None, None)], qatorlar(ri=A1))

# A2 — Kesildi: 3 m (30 000) dan 2 m ishlatildi → TM 20 000, zarar 10 000
b2 = buyurtma()
m0 = mb()
r, A2 = brak(b2, 3, {"taqdir": "kesildi", "ishlatildi": 2, "nomi": "BT Karniz 1 m", "miqdor": 2, "birlik": "dona",
                     "narx": 25_000})
T2 = tm_idi(ri=A2)
check("A2 Kesildi (3 m = 30 000, 2 m ishlatildi): 200; zarar 10 000 (Moliya «Brak» +10 000)",
      r.status_code == 200 and teng(mb()[0] - m0[0], 10_000) and yozuv_qiymati("qaytarish", A2) == 10_000,
      (r.status_code, r.text[:300], mb(), m0))
check("A2b Tayyor mahsulot: «BT Karniz 1 m» 2 dona, tannarx 20 000 (1 dona 10 000), narx 25 000, belgi «kesildi», qaytgan, tayyor",
      tm(T2) == {"nomi": "BT Karniz 1 m", "miqdor": 2.0, "birlik": "dona", "tannarx": 20_000.0, "narx": 25_000.0,
                 "ucs": 10_000.0, "taqdir": "kesildi", "manba": "returned", "holat": "ready"}, tm(T2))

# A3 — 2-nav: 1,5 m (15 000), narx 8 000 → brak zarari 0; sotuv 12 000 → farq 3 000 SOTUV oyida
b3 = buyurtma()
m0 = mb()
r, A3 = brak(b3, 1.5, {"taqdir": "ikkinchi_nav", "narx": 8_000})
T3 = tm_idi(ri=A3)
check("A3 2-nav (1,5 m = 15 000, narx 8 000): 200; brak zarari YO'Q (Moliya «Brak» o'zgarmadi)",
      r.status_code == 200 and teng(mb()[0], m0[0]) and yozuv_qiymati("qaytarish", A3) == 0,
      (r.status_code, r.text[:300], mb(), m0))
check("A3b Tayyor mahsulot: 1,5 m, tannarx 15 000 (TO'LIQ), sotuv narxi 8 000, belgi «ikkinchi_nav»",
      (tm(T3) or {}).get("miqdor") == 1.5 and (tm(T3) or {}).get("tannarx") == 15_000 and (tm(T3) or {}).get("narx") == 8_000
      and (tm(T3) or {}).get("taqdir") == "ikkinchi_nav" and (tm(T3) or {}).get("birlik") == "metr", tm(T3))
_mk0 = moliya(K_YIL, K_OY)
r = req(C, "post", "/api/finished/sell", json={"finished_product_id": T3, "quantity": 1.5, "unit_price": 8_000,
                                                "payment_method": "naqd", "buyer_name": "BT xaridor"})
d = js(r) or {}
check("A3c 2-nav sotuvi 1,5 m × 8 000 = 12 000 — «narx juda past» SO'RALMADI (Q2), foyda −3 000",
      r.status_code == 200 and teng(d.get("total_amount"), 12_000) and teng(d.get("profit"), -3_000), (r.status_code, r.text[:300]))
_s = SessionLocal()
try:
    _sv = _s.query(FinishedProductSale).filter(FinishedProductSale.finished_product_id == T3).first()
    if _sv is not None:
        _sv.sold_at = (_sv.sold_at or datetime.utcnow()) + timedelta(days=32)     # sotuv — keyingi oyda
        _s.commit()
finally:
    _s.close()
_mk1 = moliya(K_YIL, K_OY)
check("A3d farq 3 000 — SOTUV oyida zarar (keyingi oy «TM sotuvi foydasi» −3 000), brak oyi «Brak» qatori o'zgarmadi",
      teng(float(_mk1.get("fp_sales_foyda") or 0) - float(_mk0.get("fp_sales_foyda") or 0), -3_000) and teng(mb()[0], m0[0]),
      (_mk0.get("fp_sales_foyda"), _mk1.get("fp_sales_foyda"), mb(), m0))

# ══════════════════════════════════════════════════════════════
section("B — uch yo'l × taqdirlar: Moliya qatorlari, ombor, tayyor mahsulot")
# B1 — omborda turgan TM: 5 m yo'qotish (50 000) → Tuzatildi (Setka emas — Akril 0,3 kg = 3 000) → TM tiklanadi
F1 = tm_yarat("BT tayyor F1")
m0, z0 = mb(), zaxira("akr")
r = req(C, "post", "/api/finished/loss", json={"finished_product_id": F1, "quantity": 5, "brak_sabab": "boshqa",
                                                "taqdir": {"taqdir": "tuzatildi", "materiallar": [{"inventory_id": ID["akr"], "miqdor": 0.3}]}})
B1 = (js(r) or {}).get("loss_id")
check("B1 omborda turgan (5 m = 50 000) Tuzatildi: 200; mahsulot o'sha partiyaga qaytdi (100 m, tannarx 1 000 000)",
      r.status_code == 200 and (tm(F1) or {}).get("miqdor") == 100 and (tm(F1) or {}).get("tannarx") == 1_000_000,
      (r.status_code, r.text[:300], tm(F1)))
check("B1b «TM yo'qotishi» o'zgarmadi; tuzatish xomashyosi (Akril 0,3 kg = 3 000) — «Brak» qatorida; Akril −0,3",
      teng(mb()[1], m0[1]) and teng(mb()[0] - m0[0], 3_000) and teng(z0[0] - zaxira("akr")[0], 0.3, 1e-6)
      and yozuv_qiymati("yoqotish", B1) == (3_000.0, 0.0), (mb(), m0, yozuv_qiymati("yoqotish", B1) if B1 else None))
# B2 — omborda turgan: 5 m Kesildi (4 m ishlatildi) → TM 40 000, zarar 10 000 («TM yo'qotishi»)
m0 = mb()
r = req(C, "post", "/api/finished/loss", json={"finished_product_id": F1, "quantity": 5, "brak_sabab": "boshqa",
                                                "taqdir": {"taqdir": "kesildi", "ishlatildi": 4, "nomi": "BT F1 bo'lak",
                                                           "miqdor": 8, "birlik": "dona"}})
B2 = (js(r) or {}).get("loss_id")
check("B2 omborda turgan Kesildi (5 m = 50 000, 4 m ishlatildi): TM 40 000 (8 dona), «TM yo'qotishi» +10 000",
      r.status_code == 200 and (tm(tm_idi(fpl=B2)) or {}).get("tannarx") == 40_000
      and (tm(tm_idi(fpl=B2)) or {}).get("miqdor") == 8 and teng(mb()[1] - m0[1], 10_000) and teng(mb()[0], m0[0]),
      (r.status_code, r.text[:300], tm(tm_idi(fpl=B2)) if B2 else None, mb(), m0))
# B3 — omborda turgan: 2 m 2-nav → TM 20 000, zarar 0
m0 = mb()
r = req(C, "post", "/api/finished/loss", json={"finished_product_id": F1, "quantity": 2, "brak_sabab": "boshqa",
                                                "taqdir": {"taqdir": "ikkinchi_nav", "narx": 9_000}})
B3 = (js(r) or {}).get("loss_id")
check("B3 omborda turgan 2-nav (2 m = 20 000): TM 20 000 (2 m, 9 000), «TM yo'qotishi» o'zgarmadi",
      r.status_code == 200 and (tm(tm_idi(fpl=B3)) or {}).get("tannarx") == 20_000
      and (tm(tm_idi(fpl=B3)) or {}).get("narx") == 9_000 and teng(mb()[1], m0[1]), (r.status_code, r.text[:300], mb(), m0))
# C yo'li — ishlab chiqarish braki: F2 (1 m = 0,01 m³ → 10 000)
F2 = tm_yarat("BT tayyor F2", narx=18_000, birlik_hajm=0.01)
m0, z0 = mb(), zaxira("peno")
r = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F2, "brak_qty": 2, "brak_sabab": "boshqa",
                                                           "taqdir": {"taqdir": "tuzatildi", "joy": "joyiga"}})
C1 = (js(r) or {}).get("loss_id")
check("B4 ishlab chiqarish braki (2 m = 20 000) Tuzatildi — o'sha mahsulotga: 200; penoplast QAYTDI, zarar 0",
      r.status_code == 200 and teng(zaxira("peno")[0], z0[0], 1e-6) and teng(mb()[0], m0[0])
      and yozuv_qiymati("yoqotish", C1) == 0, (r.status_code, r.text[:300], zaxira("peno"), z0, mb(), m0))
s_ = SessionLocal()
try:
    _bog = s_.query(InventoryMovement).filter(InventoryMovement.fp_loss_id == C1).count() if C1 and hasattr(InventoryMovement, "fp_loss_id") else 0
finally:
    s_.close()
check("B4b ishlab chiqarish brakining xomashyo harakati yozuvga bog'langan (`fp_loss_id`) — chiqim va qaytish (2 ta)",
      _bog == 2, _bog)
m0 = mb()
r = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F2, "brak_qty": 2, "brak_sabab": "boshqa",
                                                           "taqdir": {"taqdir": "tuzatildi", "joy": "omborga"}})
C2 = (js(r) or {}).get("loss_id")
check("B5 ishlab chiqarish braki Tuzatildi — omborga: TM 2 m, tannarx 20 000, ASL narx 18 000 (Q3), zarar 0",
      r.status_code == 200 and (tm(tm_idi(fpl=C2)) or {}).get("tannarx") == 20_000
      and (tm(tm_idi(fpl=C2)) or {}).get("narx") == 18_000 and (tm(tm_idi(fpl=C2)) or {}).get("taqdir") == "tuzatildi"
      and teng(mb()[0], m0[0]), (r.status_code, r.text[:300], tm(tm_idi(fpl=C2)) if C2 else None, mb(), m0))
m0 = mb()
r = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F2, "brak_qty": 2, "brak_sabab": "boshqa",
                                                           "taqdir": {"taqdir": "kesildi", "ishlatildi": 1, "nomi": "BT F2 bo'lak",
                                                                      "miqdor": 3, "birlik": "dona"}})
C3 = (js(r) or {}).get("loss_id")
check("B6 ishlab chiqarish braki Kesildi (1 m ishlatildi): TM 10 000, «Brak» +10 000",
      r.status_code == 200 and (tm(tm_idi(fpl=C3)) or {}).get("tannarx") == 10_000 and teng(mb()[0] - m0[0], 10_000),
      (r.status_code, r.text[:300], mb(), m0))
m0 = mb()
r = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F2, "brak_qty": 1, "brak_sabab": "boshqa",
                                                           "taqdir": {"taqdir": "ikkinchi_nav", "narx": 7_000}})
C4 = (js(r) or {}).get("loss_id")
check("B7 ishlab chiqarish braki 2-nav (1 m = 10 000): TM 10 000, «Brak» o'zgarmadi; mahsulot soni o'zgarmadi (100 m)",
      r.status_code == 200 and (tm(tm_idi(fpl=C4)) or {}).get("tannarx") == 10_000 and teng(mb()[0], m0[0])
      and (tm(F2) or {}).get("miqdor") == 100, (r.status_code, r.text[:300], mb(), m0, tm(F2)))

# ══════════════════════════════════════════════════════════════
section("C — taqdirni o'zgartirish: eskisi AYNAN qaytadi")
m0 = mb()
r = taqdir_ozgar("qaytarish", A2, {"taqdir": "ikkinchi_nav", "narx": 9_000})
T2b = tm_idi(ri=A2)
check("C1 Kesildi → 2-nav: 200; kesilgan partiya (sotilmagan) O'CHDI, 2-nav partiya 3 m tannarx 30 000; «Brak» −10 000 (zarar 0)",
      r.status_code == 200 and tm(T2) is None and (tm(T2b) or {}).get("tannarx") == 30_000
      and (tm(T2b) or {}).get("miqdor") == 3 and teng(mb()[0] - m0[0], -10_000) and yozuv_qiymati("qaytarish", A2) == 0,
      (r.status_code, r.text[:300], tm(T2), tm(T2b), mb(), m0))
check("C1b jurnal: eski qator bekor qilingan (saqlangan), yangisi faol",
      [(q[0], q[2]) for q in qatorlar(ri=A2)] == [("kesildi", False), ("ikkinchi_nav", True)], qatorlar(ri=A2))
m0, z0 = mb(), zaxira("peno", "akr", "kley")
r = taqdir_ozgar("qaytarish", A1, {"taqdir": "tashlandi"})
z1 = zaxira("peno", "akr", "kley")
check("C2 Tuzatildi → Tashlandi: tuzatish loyi omborga qaytdi (+0,2 / +0,2), brak penoplasti qayta yechildi (−0,01 blok); «Brak» +4 000",
      r.status_code == 200 and teng(z1[0] - z0[0], -0.01, 1e-6) and teng(z1[1] - z0[1], 0.2, 1e-6)
      and teng(z1[2] - z0[2], 0.2, 1e-6) and teng(mb()[0] - m0[0], 4_000) and faol(ri=A1) is None
      and yozuv_qiymati("qaytarish", A1) == 10_000, (r.status_code, r.text[:300], z0, z1, mb(), m0))
m0, z0 = mb(), zaxira("akr")
r = taqdir_ozgar("yoqotish", B1, {"taqdir": "tashlandi"})
check("C3 omborda turgan Tuzatildi → Tashlandi: partiyadan 5 m olindi (95 m), Akril +0,3; «TM yo'qotishi» +50 000, «Brak» −3 000",
      r.status_code == 200 and (tm(F1) or {}).get("miqdor") == 88 and teng(mb()[1] - m0[1], 50_000)
      and teng(mb()[0] - m0[0], -3_000) and teng(zaxira("akr")[0] - z0[0], 0.3, 1e-6),
      (r.status_code, r.text[:300], tm(F1), mb(), m0))
_s = SessionLocal()
try:
    _al = _s.query(ActivityLog).filter(ActivityLog.action == "brak_taqdir", ActivityLog.entity_type == "return",
                                       ActivityLog.entity_id == (A2 or -1)).order_by(ActivityLog.id).all()
    _al = [(a.old_value, (a.new_value or "")[:40]) for a in _al]
finally:
    _s.close()
check("C4 Faoliyat jurnali: brak yozilganda (eski qiymatsiz) va o'zgarganda (Kesildi → 2-nav)",
      len(_al) == 2 and _al[0][0] is None and _al[0][1].startswith("Kesildi") and _al[1][0] == "Kesildi"
      and _al[1][1].startswith("2-nav") and "brak_taqdir" in crud.AUDIT_AMALLARI, _al)
n0 = sanoq()
r = taqdir_ozgar("qaytarish", A0, {"taqdir": "tashlandi"})
check("C5 taqdirsiz yozuvga «Tashlandi» — o'zgarish yo'q (200, ozgardi=false), hech narsa yozilmadi",
      r.status_code == 200 and (js(r) or {}).get("ozgardi") is False and sanoq() == n0, (r.status_code, r.text[:200], n0, sanoq()))

# ══════════════════════════════════════════════════════════════
section("D — hodisa vaqti (Q4): o'tgan oy o'zgarmaydi")
bD = buyurtma()
r, AD = brak(bD, 2)
_s = SessionLocal()
try:
    _ri = _s.get(ReturnItem, AD)
    _ri.returned_at = _ri.returned_at - timedelta(days=35)
    for h in _s.query(InventoryMovement).filter(InventoryMovement.return_item_id == AD).all():
        h.created_at = h.created_at - timedelta(days=35)
    _s.commit()
    _o_oy = crud._tashkent_date(_ri.returned_at)
finally:
    _s.close()
OY_ = (_o_oy.year, _o_oy.month)
mo0, mj0 = mb(*OY_), mb()
r = taqdir_ozgar("qaytarish", AD, {"taqdir": "ikkinchi_nav", "narx": 5_000})
check("D1 o'tgan oy brakini joriy oyda 2-nav qilish: o'tgan oy «Brak» O'ZGARMADI, joriy oy −20 000",
      r.status_code == 200 and teng(mb(*OY_)[0], mo0[0]) and teng(mb()[0] - mj0[0], -20_000),
      (r.status_code, r.text[:200], OY_, mb(*OY_), mo0, mb(), mj0))
TA = tahlil()
check("D2 joriy oy tahlili: o'sha yozuv −20 000 bilan; tahlil yozuvlari = Moliya «Brak», bog'lanmagan 0",
      TA.get("brak_xarajat") == round(mb()[0]) and teng(TA.get("yozuvlar_qiymati"), mb()[0])
      and TA.get("boglanmagan_qiymat") == 0 and yozuv_qiymati("qaytarish", AD) == -20_000,
      ({k: TA.get(k) for k in ("brak_xarajat", "yozuvlar_qiymati", "boglanmagan_qiymat")}, mb(), yozuv_qiymati("qaytarish", AD) if AD else None))
TO = tahlil(*OY_)
check("D3 o'tgan oy tahlili: yozuv qiymati 20 000 (o'zgarmagan), = o'tgan oy Moliyasi",
      yozuv_qiymati("qaytarish", AD, *OY_) == 20_000 and TO.get("brak_xarajat") == round(mb(*OY_)[0])
      and TO.get("boglanmagan_qiymat") == 0, (yozuv_qiymati("qaytarish", AD, *OY_) if AD else None, TO.get("brak_xarajat"), mb(*OY_)))
# D4 — faqat yozuv SANASI o'tgan oyga surilgan (harakatlari joriy oyda): brakning O'Z qiymati yozuv oyiga (avvalgi qoida —
# tools/test_brak_tahlil E), taqdir qiymati — hodisa oyiga (Q4).
bD4 = buyurtma()
r, AD4 = brak(bD4, 1)
_s = SessionLocal()
try:
    _ri = _s.get(ReturnItem, AD4)
    _ri.returned_at = _ri.returned_at - timedelta(days=35)
    _s.commit()
    _o4 = crud._tashkent_date(_ri.returned_at)
finally:
    _s.close()
OY4 = (_o4.year, _o4.month)
_d4a = (yozuv_qiymati("qaytarish", AD4, *OY4), yozuv_qiymati("qaytarish", AD4))
r = taqdir_ozgar("qaytarish", AD4, {"taqdir": "ikkinchi_nav", "narx": 5_000})
_d4b = (yozuv_qiymati("qaytarish", AD4, *OY4), yozuv_qiymati("qaytarish", AD4))
check("D4 faqat yozuv sanasi o'tgan oyda: o'z qiymati (10 000) o'sha oyga, joriy oyda 0; joriy oyda 2-nav — joriy oy −10 000, "
      "o'tgan oy 10 000 qoldi",
      r.status_code == 200 and _d4a == (10_000, 0) and _d4b == (10_000, -10_000), (r.status_code, r.text[:200], _d4a, _d4b))
r = req(C, "delete", f"/api/returns/{AD4}")
check("D4b o'sha yozuv o'chirildi (keyingi «bitta raqam» tekshiruvlariga ta'sir qilmasin)", r.status_code == 200,
      (r.status_code, r.text[:200]))
# D5 — eski «Brak…» sababli KIRIM (migratsiya `is_brak` ni TRUE qilgan, taqdirsiz) brak qiymatiga KIRMAYDI: o'tgan va joriy
# oy raqami o'zgarmaydi (tools/test_brak_belgisi D2d bilan bir qoida).
mj5, mo5 = mb(), mb(*OY_)
_s = SessionLocal()
try:
    _s.add(InventoryMovement(company_id=1, inventory_id=ID["peno"], item_name="BT Penoplast", movement_type="in", quantity=0.5,
                             unit="blok", reason="Brak — eski kirim (migratsiya belgilagan)", unit_cost=500_000, is_brak=True))
    _s.add(InventoryMovement(company_id=1, inventory_id=ID["peno"], item_name="BT Penoplast", movement_type="in", quantity=0.5,
                             unit="blok", reason="Brak — eski kirim (o'tgan oy)", unit_cost=500_000, is_brak=True,
                             created_at=datetime.utcnow() - timedelta(days=35)))       # noqa: DTZ003
    _s.commit()
finally:
    _s.close()
TA5 = tahlil()
check("D5 taqdirsiz eski brak kirimi (is_brak TRUE) Moliya «Brak» ni O'ZGARTIRMADI (joriy va o'tgan oy), tahlil bog'lanmagan 0",
      mb() == mj5 and mb(*OY_) == mo5 and TA5.get("boglanmagan_qiymat") == 0,
      (mb(), mj5, mb(*OY_), mo5, TA5.get("boglanmagan_qiymat")))

# ══════════════════════════════════════════════════════════════
section("E — rad etishlar: 400 va HECH NARSA o'zgarmaydi")
n0, z0, f0 = sanoq(), zaxira("peno", "akr", "kley"), faol(ri=A3)
r = taqdir_ozgar("qaytarish", A3, {"taqdir": "tashlandi"})
check("E1 2-nav partiyasi SOTILGAN — taqdirni o'zgartirish 400 (sabab: sotilgan), hech narsa o'zgarmadi",
      r.status_code == 400 and "sotil" in (r.text or "") and sanoq() == n0 and faol(ri=A3) == f0 and zaxira("peno", "akr", "kley") == z0,
      (r.status_code, r.text[:300]))
r = req(C, "delete", f"/api/returns/{A3}")
# kech125 (zip 147): o'chirishda xabar — «brak yozuvini o'chirib bo'lmaydi» (ilgari «taqdirni o'zgartirib bo'lmaydi» derdi)
check("E2 shu brak yozuvini o'chirish ham 400 (TM sotilgan; xabar — «brak yozuvini o'chirib bo'lmaydi»), hech narsa o'zgarmadi",
      r.status_code == 400 and "brak yozuvini o'chirib bo'lmaydi" in (r.text or "") and "o'zgartirib" not in (r.text or "")
      and sanoq() == n0 and zaxira("peno", "akr", "kley") == z0, (r.status_code, r.text[:300]))
bE = buyurtma()
_rad = [
    ("E3a taqdir «Ortiqcha» qaytarishga", dict(brak_tana(bE, 1, {"taqdir": "ikkinchi_nav", "narx": 1000}), reason="Ortiqcha",
                                                 brak_sabab=None, to_stock=True)),
    ("E3b Kesildi: ishlatilgan > brak", brak_tana(bE, 1, {"taqdir": "kesildi", "ishlatildi": 2, "nomi": "x", "miqdor": 1, "birlik": "dona"})),
    ("E3c Kesildi: nomsiz", brak_tana(bE, 1, {"taqdir": "kesildi", "ishlatildi": 1, "nomi": " ", "miqdor": 1, "birlik": "dona"})),
    ("E3d Kesildi: miqdorsiz", brak_tana(bE, 1, {"taqdir": "kesildi", "ishlatildi": 1, "nomi": "x", "birlik": "dona"})),
    ("E3e Kesildi: noto'g'ri birlik", brak_tana(bE, 1, {"taqdir": "kesildi", "ishlatildi": 1, "nomi": "x", "miqdor": 1, "birlik": "litr"})),
    ("E3f 2-nav: narxsiz", brak_tana(bE, 1, {"taqdir": "ikkinchi_nav"})),
    ("E3g 2-nav: narx 0", brak_tana(bE, 1, {"taqdir": "ikkinchi_nav", "narx": 0})),
    ("E3h Tashlandi + ortiqcha maydon", brak_tana(bE, 1, {"taqdir": "tashlandi", "narx": 5})),
    ("E3i Tuzatildi: joy tanlanmagan", brak_tana(bE, 1, {"taqdir": "tuzatildi"})),
    ("E3j Tuzatildi: begona korxona materiali", brak_tana(bE, 1, {"taqdir": "tuzatildi", "joy": "joyiga",
                                                                  "materiallar": [{"inventory_id": ID["kley_b"], "miqdor": 1}]})),
    ("E3k Tuzatildi: bir xomashyo ikki marta", brak_tana(bE, 1, {"taqdir": "tuzatildi", "joy": "joyiga", "materiallar": [
        {"inventory_id": ID["akr"], "miqdor": 1}, {"inventory_id": ID["akr"], "miqdor": 2}]})),
    ("E3l Tuzatildi: material va retsept birga", brak_tana(bE, 1, {"taqdir": "tuzatildi", "joy": "joyiga", "materiallar": [
        {"inventory_id": ID["akr"], "retsept_id": ID["r1"], "miqdor": 1}]})),
    ("E3m Tuzatildi: tayyor loy pozitsiyasi material sifatida", brak_tana(bE, 1, {"taqdir": "tuzatildi", "joy": "joyiga",
                                                                                  "materiallar": [{"inventory_id": ID["tayyor_loy"], "miqdor": 1}]})),
    ("E3n Tuzatildi: xomashyo yetmaydi (Setka 0,5 m, kerak 1)", brak_tana(bE, 1, {"taqdir": "tuzatildi", "joy": "joyiga",
                                                                                   "materiallar": [{"inventory_id": ID["setka"], "miqdor": 1}]})),
    ("E3o noma'lum taqdir", brak_tana(bE, 1, {"taqdir": "sotildi"})),
    ("E3p noma'lum kalit", brak_tana(bE, 1, {"taqdir": "ikkinchi_nav", "narx": 1000, "xyz": 1})),
    ("E3q taqdir — matn", brak_tana(bE, 1, "ikkinchi_nav")),
    ("E3r manfiy narx", brak_tana(bE, 1, {"taqdir": "ikkinchi_nav", "narx": -5})),
]
n0, z0 = sanoq(), zaxira("peno", "akr", "kley", "setka")
for nom, tana in _rad:
    r = req(C, "post", "/api/returns", json=tana)
    check(f"{nom} — 400 (brak ham yozilmadi)", r.status_code == 400 and sanoq() == n0
          and zaxira("peno", "akr", "kley", "setka") == z0, (r.status_code, r.text[:300], n0, sanoq()))
F3 = tm_yarat("BT tayyor F3")
n0 = sanoq()
r = req(C, "post", "/api/finished/loss", json={"finished_product_id": F3, "quantity": 1, "brak_sabab": "boshqa",
                                                "taqdir": {"taqdir": "tuzatildi", "joy": "omborga"}})
check("E4 omborda turgan mahsulot «Tuzatildi — omborga» — 400 (o'sha partiyaga qaytadi), hech narsa yozilmadi",
      r.status_code == 400 and sanoq() == n0 and (tm(F3) or {}).get("miqdor") == 100, (r.status_code, r.text[:300]))
r = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F2, "brak_qty": 1, "brak_sabab": "boshqa",
                                                           "taqdir": {"taqdir": "kesildi", "ishlatildi": 2, "nomi": "x", "miqdor": 1,
                                                                      "birlik": "dona"}})
check("E5 ishlab chiqarish braki: Kesildi ishlatilgan > brak — 400, xomashyo yechilmadi",
      r.status_code == 400 and sanoq() == n0, (r.status_code, r.text[:300]))
# E6 — eski (bog'lamsiz) ishlab chiqarish braki: «o'sha joyiga» — rad, 2-nav — `cost_amount` bilan
r = req(C, "post", "/api/finished/production-brak", json={"finished_product_id": F2, "brak_qty": 1, "brak_sabab": "boshqa"})
CE = (js(r) or {}).get("loss_id")
_s = SessionLocal()
try:
    if hasattr(InventoryMovement, "fp_loss_id"):
        for h in _s.query(InventoryMovement).filter(InventoryMovement.fp_loss_id == CE).all():
            h.fp_loss_id = None                      # eski yozuv taqlidi — harakat bog'lanmagan
    _s.commit()
finally:
    _s.close()
n0, m0 = sanoq(), mb()
r = taqdir_ozgar("yoqotish", CE, {"taqdir": "tuzatildi", "joy": "joyiga"})
check("E6 eski bog'lamsiz ishlab chiqarish braki «O'sha joyiga» — 400 (eski yozuv), hech narsa o'zgarmadi",
      r.status_code == 400 and "eski" in (r.text or "") and sanoq() == n0, (r.status_code, r.text[:300]))
r = taqdir_ozgar("yoqotish", CE, {"taqdir": "ikkinchi_nav", "narx": 6_000})
check("E6b eski yozuv 2-nav — `cost_amount` (10 000) bilan TM ga; «Brak» −10 000",
      r.status_code == 200 and (tm(tm_idi(fpl=CE)) or {}).get("tannarx") == 10_000 and teng(mb()[0] - m0[0], -10_000),
      (r.status_code, r.text[:300], mb(), m0))
# E7 — qisman sotilgan (kesilgan) partiya
bE7 = buyurtma()
r, AE7 = brak(bE7, 2, {"taqdir": "kesildi", "ishlatildi": 2, "nomi": "BT E7 bo'lak", "miqdor": 4, "birlik": "dona"})
TE7 = tm_idi(ri=AE7)
r = req(C, "post", "/api/finished/sell", json={"finished_product_id": TE7, "quantity": 1, "unit_price": 6_000,
                                                "payment_method": "naqd", "confirm_below_cost": True})
n0 = sanoq()
r2 = taqdir_ozgar("qaytarish", AE7, {"taqdir": "tashlandi"})
check("E7 kesilgan partiyadan 1 dona sotilgan — taqdirni o'zgartirish 400, partiya 3 dona qoldi",
      r.status_code == 200 and r2.status_code == 400 and sanoq() == n0 and (tm(TE7) or {}).get("miqdor") == 3,
      (r.status_code, r2.status_code, r2.text[:300], tm(TE7)))

# ══════════════════════════════════════════════════════════════
section("F — brak yozuvini o'chirish: taqdir ham «bo'lmagandek»")
bF = buyurtma()
z0, m0, n0 = zaxira("peno", "akr", "kley"), mb(), sanoq()
r, AF = brak(bF, 2, {"taqdir": "tuzatildi", "joy": "omborga", "materiallar": [{"retsept_id": ID["r1"], "miqdor": 1},
                                                                                 {"inventory_id": ID["akr"], "miqdor": 0.5}]})
TF = tm_idi(ri=AF)
r2 = taqdir_ozgar("qaytarish", AF, {"taqdir": "kesildi", "ishlatildi": 1, "nomi": "BT F bo'lak", "miqdor": 1, "birlik": "dona"})
TF2 = tm_idi(ri=AF)
r3 = req(C, "delete", f"/api/returns/{AF}")
check("F1 Tuzatildi (omborga) → Kesildi → O'CHIRISH: ombor AYNAN boshidagidek, TM partiyalar yo'q, jurnal qatorlari yo'q, Moliya — avvalgidek",
      r.status_code == 200 and r2.status_code == 200 and r3.status_code == 200 and zaxira("peno", "akr", "kley") == z0
      and tm(TF) is None and tm(TF2) is None and qatorlar(ri=AF) == [] and teng(mb()[0], m0[0]) and sanoq() == n0,
      (r.status_code, r2.status_code, r3.status_code, r3.text[:300], z0, zaxira("peno", "akr", "kley"), tm(TF), tm(TF2),
       mb(), m0, n0, sanoq()))
# F1b — FAOL taqdir bilan to'g'ridan-to'g'ri o'chirish: taqdir harakatlari qoldig'i ham qaytadi (bekor qilinmagan holat)
bF1 = buyurtma()
z0, n0 = zaxira("peno", "akr", "kley"), sanoq()
r, AF1 = brak(bF1, 2, {"taqdir": "tuzatildi", "joy": "joyiga", "materiallar": [{"inventory_id": ID["akr"], "miqdor": 0.5}]})
_zf1 = zaxira("peno", "akr", "kley")
r3 = req(C, "delete", f"/api/returns/{AF1}")
check("F1b faol Tuzatildi (o'sha joyiga, akril 0,5) bilan brakni O'CHIRISH: ombor AYNAN boshidagidek (asl chiqim, «joyiga» kirimi, "
      "tuzatish xomashyosi — hammasi qaytdi), harakat va jurnal qatori yo'q",
      r.status_code == 200 and r3.status_code == 200 and _zf1 != z0 and zaxira("peno", "akr", "kley") == z0
      and qatorlar(ri=AF1) == [] and sanoq() == n0,
      (r.status_code, r3.status_code, r3.text[:300], z0, _zf1, zaxira("peno", "akr", "kley"), n0, sanoq()))
F4 = tm_yarat("BT tayyor F4")
m0, n0 = mb(), sanoq()
r = req(C, "post", "/api/finished/loss", json={"finished_product_id": F4, "quantity": 10, "brak_sabab": "boshqa",
                                                "taqdir": {"taqdir": "ikkinchi_nav", "narx": 4_000}})
BF = (js(r) or {}).get("loss_id")
T4 = tm_idi(fpl=BF)
r2 = req(C, "delete", f"/api/finished/loss/{BF}")
check("F2 omborda turgan 2-nav → O'CHIRISH: 2-nav partiya yo'q, asl partiya 100 m / 1 000 000, jurnal qatorlari yo'q, Moliya — avvalgidek",
      r.status_code == 200 and r2.status_code == 200 and tm(T4) is None and (tm(F4) or {}).get("miqdor") == 100
      and (tm(F4) or {}).get("tannarx") == 1_000_000 and qatorlar(fpl=BF) == [] and mb() == m0 and sanoq() == n0,
      (r.status_code, r2.status_code, r2.text[:300], tm(T4), tm(F4), mb(), m0, n0, sanoq()))
r = req(C, "post", "/api/finished/loss", json={"finished_product_id": F4, "quantity": 10, "brak_sabab": "boshqa",
                                                "taqdir": {"taqdir": "ikkinchi_nav", "narx": 4_000}})
BF2 = (js(r) or {}).get("loss_id")
req(C, "post", "/api/finished/sell", json={"finished_product_id": tm_idi(fpl=BF2), "quantity": 1, "unit_price": 4_000,
                                           "payment_method": "naqd"})
n0 = sanoq()
r2 = req(C, "delete", f"/api/finished/loss/{BF2}")
check("F3 2-nav partiyasidan sotilgan — omborda turgan yo'qotishni o'chirish 400 (xabar — «brak yozuvini o'chirib bo'lmaydi»), "
      "hech narsa o'zgarmadi",
      r2.status_code == 400 and "brak yozuvini o'chirib bo'lmaydi" in (r2.text or "") and sanoq() == n0
      and (tm(F4) or {}).get("miqdor") == 90, (r2.status_code, r2.text[:300], tm(F4)))
# F4 — kech125 (zip 147, staging jonli sinovida topilgan): omborda turgan mahsulot «Tuzatildi» (o'sha partiyaga), partiya TO'LIQ BAND —
# yozuvni o'chirish o'sha miqdorni o'sha partiyaga qaytaradi (jami o'zgarish 0), «band» rad sababi EMAS
FB = tm_yarat("BT F4 band partiya", miqdor=10, tannarx=100_000)
_s = SessionLocal()
try:
    _s.get(FinishedProduct, FB).reserved_quantity = 10.0
    _s.commit()
finally:
    _s.close()
z0, m0 = zaxira("peno", "akr", "kley"), mb()
r = req(C, "post", "/api/finished/loss", json={"finished_product_id": FB, "quantity": 2, "brak_sabab": "boshqa",
                                                "taqdir": {"taqdir": "tuzatildi", "materiallar": [{"inventory_id": ID["akr"], "miqdor": 0.1}]}})
BFB = (js(r) or {}).get("loss_id")
_tb0 = tm(FB)
n0 = sanoq()
r2 = req(C, "delete", f"/api/finished/loss/{BFB}")
_s = SessionLocal()
try:
    _band = float(_s.get(FinishedProduct, FB).reserved_quantity or 0)
finally:
    _s.close()
check("F4 omborda turgan «Tuzatildi» (o'sha partiyaga), partiya to'liq band — o'chirish 200: partiya 10 m / 100 000 (band 10), "
      "tuzatish akrili omborga qaytdi, jurnal qatorlari yo'q, Moliya — avvalgidek",
      r.status_code == 200 and r2.status_code == 200 and (_tb0 or {}).get("miqdor") == 10
      and (tm(FB) or {}).get("miqdor") == 10 and (tm(FB) or {}).get("tannarx") == 100_000 and _band == 10
      and zaxira("peno", "akr", "kley") == z0 and qatorlar(fpl=BFB) == [] and mb() == m0,
      (r.status_code, r.text[:200], r2.status_code, r2.text[:300], _tb0, tm(FB), _band, z0, zaxira("peno", "akr", "kley"), m0, mb()))
# F5 — o'sha holat, partiyaning ko'p qismi SOTILGAN (10 → yo'qotish 4 → tuzatildi 10 → sotuv 8 → 2): o'chirish «bo'lmagandek» — 2 m
# qoladi (oraliq qiymat 0 ga qisqartirilsa 4 bo'lib qolardi)
FS = tm_yarat("BT F5 sotilgan partiya", miqdor=10, tannarx=100_000, narx=20_000)
r = req(C, "post", "/api/finished/loss", json={"finished_product_id": FS, "quantity": 4, "brak_sabab": "boshqa",
                                                "taqdir": {"taqdir": "tuzatildi"}})
BFS = (js(r) or {}).get("loss_id")
rs = req(C, "post", "/api/finished/sell", json={"finished_product_id": FS, "quantity": 8, "unit_price": 20_000, "payment_method": "naqd"})
_ts0 = tm(FS)
r2 = req(C, "delete", f"/api/finished/loss/{BFS}")
check("F5 o'sha partiyadan 8 m sotilgan (2 m qolgan) — o'chirish 200, partiyada AYNAN 2 m, tannarx o'chirishdan oldingidek, qatorlar yo'q",
      r.status_code == 200 and rs.status_code == 200 and r2.status_code == 200 and (_ts0 or {}).get("miqdor") == 2
      and (tm(FS) or {}).get("miqdor") == 2 and teng((tm(FS) or {}).get("tannarx"), (_ts0 or {}).get("tannarx"))
      and qatorlar(fpl=BFS) == [],
      (r.status_code, rs.status_code, rs.text[:200], r2.status_code, r2.text[:300], _ts0, tm(FS)))

# ══════════════════════════════════════════════════════════════
section("G — korxona izolyatsiyasi; H — ruxsatlar")
n0 = sanoq()
r1 = taqdir_ozgar("qaytarish", A0, {"taqdir": "ikkinchi_nav", "narx": 1000}, c=CB)
r2 = taqdir_ozgar("yoqotish", B2, {"taqdir": "tashlandi"}, c=CB)
check("G1 begona korxona: buyurtma detali braki va tayyor mahsulot braki taqdiri — 404, hech narsa o'zgarmadi",
      r1.status_code == 404 and r2.status_code == 404 and sanoq() == n0, (r1.status_code, r2.status_code))
mat_b = js(req(CB, "get", "/api/brak/tuzatish-materiallari")) or {}
mat_a = js(req(C, "get", "/api/brak/tuzatish-materiallari")) or {}
_nom_b = {m.get("nomi") for m in mat_b.get("materiallar", [])}
_nom_a = {m.get("nomi") for m in mat_a.get("materiallar", [])}
check("G2 tuzatish xomashyosi ro'yxati — faqat o'z korxonasi; tayyor loy pozitsiyasi yo'q (retsept orqali); narx yo'q",
      "BT B Kley" in _nom_b and "BT Akril" not in _nom_b and "BT Akril" in _nom_a and "BT B Kley" not in _nom_a
      and not any(str(n or "").startswith("Tayyor loy (") for n in _nom_a)
      and any(x.get("id") == ID["r1"] for x in mat_a.get("retseptlar", []))
      and not any("price" in str(k) or "narx" in str(k) for m in mat_a.get("materiallar", []) for k in m), (mat_a, mat_b))
bB = buyurtma(c=CB, prj=ID["prj_b"], peno=ID["peno_b"])
n0 = sanoq()
r, _x = brak(bB, 1, {"taqdir": "tuzatildi", "joy": "joyiga", "materiallar": [{"inventory_id": ID["akr"], "miqdor": 0.1}]}, c=CB)
check("G3 B korxona brakiga A korxona materiali — 400, hech narsa yozilmadi", r.status_code == 400 and sanoq() == n0,
      (r.status_code, r.text[:200]))
r1 = taqdir_ozgar("qaytarish", A0, {"taqdir": "ikkinchi_nav", "narx": 1000}, c=CM)
r2 = taqdir_ozgar("yoqotish", B2, {"taqdir": "tashlandi"}, c=CM)
r3 = req(CM, "get", "/api/brak/tuzatish-materiallari")
check("H1 Moliyachi (brak / qaytarish yaratish ruxsati yo'q) — 403 (uchala marshrut), hech narsa o'zgarmadi",
      (r1.status_code, r2.status_code, r3.status_code) == (403, 403, 403) and sanoq() == n0,
      (r1.status_code, r2.status_code, r3.status_code))
r = taqdir_ozgar("qaytarish", A0, {"taqdir": "ikkinchi_nav", "narx": 1000}, c=CN)
check("H2 Menejer (Qaytarishlar: Yaratish) — buyurtma detali braki taqdirini o'zgartira oladi (200)",
      r.status_code == 200 and (faol(ri=A0) or ("",))[0] == "ikkinchi_nav", (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════
section("I — 2-nav sotuvida ogohlantirish yo'q, oddiy mahsulotda bor; J — birlashtirilmaydi")
F5 = tm_yarat("BT tayyor F5")
r = req(C, "post", "/api/finished/sell", json={"finished_product_id": F5, "quantity": 1, "unit_price": 5_000, "payment_method": "naqd"})
check("I1 oddiy mahsulot tannarxdan (10 000) arzon (5 000) — «narx juda past» so'raladi (400, below_cost_warning)",
      r.status_code == 400 and "below_cost_warning" in (r.text or ""), (r.status_code, r.text[:200]))
T0 = tm_idi(ri=A0)
r = req(C, "post", "/api/finished/sell", json={"finished_product_id": T0, "quantity": 0.5, "unit_price": 1_000, "payment_method": "naqd"})
check("I2 2-nav mahsulot (tannarx 10 000/m) 1 000 dan — so'ralmaydi (200), foyda manfiy",
      r.status_code == 200 and float((js(r) or {}).get("profit") or 0) < 0, (r.status_code, r.text[:200]))
# I3 — to'plam sotuvi (savatcha, bitta yuk xati): 2-nav qatori so'ralmaydi; oddiy mahsulot qatori bilan birga — oddiysi so'raladi
r, AI3 = brak(buyurtma(), 1, {"taqdir": "ikkinchi_nav", "narx": 2_000})
TI3 = tm_idi(ri=AI3)
r1 = req(C, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": F5, "quantity": 1, "unit_price": 5_000},
                                                                {"finished_product_id": TI3, "quantity": 0.5, "unit_price": 500}],
                                                      "payment_method": "naqd"})
_ti3 = tm(TI3)
r2 = req(C, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": TI3, "quantity": 0.5, "unit_price": 500}],
                                                      "payment_method": "naqd"})
check("I3 to'plam sotuvi: oddiy mahsulot qatori tannarxdan arzon — so'raladi (400, hech narsa sotilmadi); faqat 2-nav qatori "
      "(tannarx 10 000/m, 500 dan) — so'ralmaydi (200)",
      r1.status_code == 400 and "below_cost_warning" in (r1.text or "") and (_ti3 or {}).get("miqdor") == 1.0
      and r2.status_code == 200 and (tm(TI3) or {}).get("miqdor") == 0.5,
      (r1.status_code, r1.text[:200], _ti3, r2.status_code, r2.text[:200], tm(TI3)))
bJ = buyurtma(narx=50_000)
_s = SessionLocal()
try:
    _oi = _s.get(OrderItem, bJ[1])
    ASL_NARX = round(float(_oi.total_price or 0) / float(_oi.order_qty_normalized or 1), 2)     # 50 000 / 10 m = 5 000
finally:
    _s.close()
r, AJ = brak(bJ, 1, {"taqdir": "tuzatildi", "joy": "omborga"})
TJ = tm_idi(ri=AJ)
_tj0 = tm(TJ)
r2 = req(C, "post", "/api/returns", json=dict(brak_tana(bJ, 1), reason="Ortiqcha", brak_sabab=None, to_stock=True))
check("J1 «Tuzatildi — omborga» partiyasi (1 m, ASL narx — detal jami / miqdor = 5 000, Q3) — keyingi butun qaytarish (nomi, "
      "narxi bir xil) UNGA QO'SHILMAYDI (alohida partiya)",
      r.status_code == 200 and r2.status_code == 200 and ASL_NARX == 5_000 and (_tj0 or {}).get("narx") == ASL_NARX
      and tm(TJ) == _tj0, (r.status_code, r2.status_code, r2.text[:200], ASL_NARX, _tj0, tm(TJ)))

# ══════════════════════════════════════════════════════════════
section("K — bitta raqam, tahlil, sahifa va ro'yxat maydonlari")
MO = moliya()
KA = js(req(C, "get", "/api/returns/stats")) or {}
TA = tahlil()
check("K1 karta «Brak qiymati — bu oy» = Moliya «Brak» = tahlil (Moliya ham, yozuvlar jami ham); bog'lanmagan 0",
      KA.get("brak_month_value") == MO.get("brak_xarajat") == TA.get("brak_xarajat")
      and teng(TA.get("yozuvlar_qiymati"), MO.get("brak_xarajat"), 0.6) and TA.get("boglanmagan_qiymat") == 0,
      (KA.get("brak_month_value"), MO.get("brak_xarajat"), {k: TA.get(k) for k in ("brak_xarajat", "yozuvlar_qiymati", "boglanmagan_qiymat")}))
check("K2 tahlil «tayyor turgan yo'qotish» = Moliya «TM yo'qotishi»; xarajat tarkibida ikkala qator",
      teng(TA.get("tayyor_yoqotish_qiymati"), MO.get("fp_loss_xarajat"), 0.6)
      and {"brak", "tm_yoqotish"} <= {x.get("kalit") for x in MO.get("xarajat_tarkibi", [])},
      (TA.get("tayyor_yoqotish_qiymati"), MO.get("fp_loss_xarajat")))
_tq = {x.get("kod"): x for x in TA.get("taqdirlar") or []}
check("K3 tahlil «Taqdir bo'yicha»: Tashlandi / Tuzatildi / Kesildi / 2-nav guruhlari (nomlari o'zbekcha), jami = yozuvlar jami",
      {"tashlandi", "tuzatildi", "kesildi", "ikkinchi_nav"} <= set(_tq) and _tq.get("ikkinchi_nav", {}).get("nomi") == "2-nav"
      and teng(sum(float(x.get("qiymat") or 0) for x in _tq.values()), TA.get("yozuvlar_qiymati"), 0.6), TA.get("taqdirlar"))
_yq = {x.get("id"): x for x in TA.get("yoqotishlar") or []}
check("K4 tahlil yo'qotishlari: yo'l (ombor / ishlab) va taqdir (yorliq, tafsilot — tannarxsiz) bor",
      (_yq.get(B2) or {}).get("taqdir") == "kesildi" and (_yq.get(B2) or {}).get("manba") == "ombor"
      and (_yq.get(C4) or {}).get("taqdir_yorliq") == "2-nav" and (_yq.get(C4) or {}).get("manba") == "ishlab"
      and "tm_tannarx" not in str(_yq.get(B2)), (_yq.get(B2), _yq.get(C4)))
_fpl = js(req(C, "get", "/api/finished")) or []
_fpm = {x.get("id"): x for x in _fpl if isinstance(x, dict)}
check("K5 /api/finished — `brak_taqdir` maydoni (2-nav / kesildi / tuzatildi; oddiyda null)",
      (_fpm.get(T0) or {}).get("brak_taqdir") == "ikkinchi_nav" and (_fpm.get(TJ) or {}).get("brak_taqdir") == "tuzatildi"
      and (_fpm.get(F5) or {}).get("brak_taqdir", "yoq") is None, (_fpm.get(T0), _fpm.get(TJ)))
_html = req(C, "get", "/returns").text or ""
check("K6 Qaytarishlar sahifasi: brak qatorida taqdir belgisi va «🧩» tugmasi (data-joriy), taqdir oynasi va formasi",
      'data-turi="qaytarish"' in _html and "2-nav — omborda" in _html and 'id="taqdirModal"' in _html
      and "function taqdirTanaOl" in _html and "Kesildi →" in _html, len(_html))
_bm = js(req(C, "get", "/api/reports/brak-materials")) or {}
check("K7 brak xomashyo xulosasi: «Tayyor mahsulotga o'tdi» qatori (taqdir: true, manfiy), jami = qatorlar yig'indisi",
      any(x.get("taqdir") and float(x.get("value") or 0) < 0 for x in _bm.get("by_material", []))
      and teng(sum(float(x.get("value") or 0) for x in _bm.get("by_material", [])), _bm.get("total_value"), 2),
      _bm.get("by_material"))
_hm = req(CM, "get", "/returns")
check("K8 «Tannarx»siz rolga (Moliyachi emas — tannarx ko'radi) sahifa ochiladi; ruxsatsizga «🧩» tugmasi yo'q",
      _hm.status_code in (200, 403) and ('data-turi="qaytarish"' not in (_hm.text or "")), (_hm.status_code,))
# K9 — kech125 (zip 147, staging jonli sinovida topilgan): taqdir xaritasida partiyaning birligi va o'lchami («🧩» oynasi Kesildi ni qayta
# ochganda shular tanlangan turadi)
bK = buyurtma()
r, AK = brak(bK, 2, {"taqdir": "kesildi", "ishlatildi": 1, "nomi": "BT K9 bo'lak", "miqdor": 3, "birlik": "dona",
                     "eni": 12.5, "qalinligi": 3})
_s = SessionLocal()
try:
    _xk = (getattr(crud, "brak_taqdir_xaritasi", lambda *a, **k: {})(_s, "qaytarish", [AK], company_id=1) or {}).get(AK) or {}
    _xb = (getattr(crud, "brak_taqdir_xaritasi", lambda *a, **k: {})(_s, "yoqotish", [B2], company_id=1) or {}).get(B2) or {}
except Exception as _e:                     # noqa: BLE001
    _xk, _xb = {"xato": str(_e)[:200]}, {}
finally:
    _s.close()
_h9 = req(C, "get", "/returns").text or ""
check("K9 taqdir xaritasi: Kesildi partiyasining birligi (dona), eni 12,5, qalinligi 3; omborda turgan Kesildi — birlik dona, o'lcham yo'q; "
      "sahifadagi data-joriy da ham",
      r.status_code == 200 and _xk.get("birlik") == "dona" and _xk.get("eni") == 12.5 and _xk.get("qalinligi") == 3.0
      and _xb.get("birlik") == "dona" and _xb.get("eni") is None and '"eni": 12.5' in _h9 and "tm_tannarx" not in str(_xk),
      (r.status_code, _xk, _xb))

# ══════════════════════════════════════════════════════════════
section("L — zaxira: eksport → tiklash (taqdir jadvali va bog'langan harakatlar)")
_s = SessionLocal()
try:
    eksport = crud.export_full_backup(_s, company_id=1)
    _q0 = len(eksport.get("tables", {}).get("brak_taqdirlari", []))
    _h0 = sum(1 for h in eksport.get("tables", {}).get("inventory_movements", []) if h.get("brak_taqdir_id"))
    _m0 = mb()
    with contextlib.redirect_stdout(_quiet):
        nat = crud.import_full_backup(_s, eksport, company_id=1, replace=True)
finally:
    _s.close()
check("L1 eksportda taqdir jadvali va harakat bog'lamlari bor; tiklash muvaffaqiyatli (PG — FK tartibi)",
      _q0 > 0 and _h0 > 0 and isinstance(nat, dict) and nat.get("success") is True,
      (_q0, _h0, {k: nat.get(k) for k in ("success", "message")} if isinstance(nat, dict) else nat))
_s = SessionLocal()
try:
    _q1 = _s.query(BrakTaqdir).filter(BrakTaqdir.company_id == 1).count() if BrakTaqdir is not None else -1
finally:
    _s.close()
check("L2 tiklangandan keyin taqdir qatorlari soni va Moliya qatorlari AYNAN", _q1 == _q0 and mb() == _m0, (_q0, _q1, _m0, mb()))


def _korxona_holati():
    _s3 = SessionLocal()
    try:
        return (_s3.query(Project).filter(Project.company_id == 1).count(),
                _s3.query(ReturnItem).filter(ReturnItem.company_id == 1).count(),
                _s3.query(FinishedProduct).filter(FinishedProduct.company_id == 1).count(),
                _s3.query(InventoryMovement).filter(InventoryMovement.company_id == 1).count(),
                (_s3.query(BrakTaqdir).filter(BrakTaqdir.company_id == 1).count() if BrakTaqdir is not None else -1))
    finally:
        _s3.close()


# L3 — TOPILGAN ESKI NUQSON: tiklash qo'shishda yiqilsa (buzilgan fayl — bir qator ikki marta), `replace=True` tozalashi ham
# QAYTISHI kerak (bitta tranzaksiya); asl kodda tozalash oldindan saqlanardi — korxona ma'lumoti o'chib qolardi.
_hol0, _m3 = _korxona_holati(), mb()
_buzuq = {"tables": {k: list(v) for k, v in (eksport.get("tables") or {}).items()},
          **{k: v for k, v in eksport.items() if k != "tables"}}
_bt_q = _buzuq["tables"].get("return_items") or []
if _bt_q:
    _bt_q.append(dict(_bt_q[-1]))
_s = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        nat3 = crud.import_full_backup(_s, _buzuq, company_id=1, replace=True)
finally:
    _s.close()
check("L3 buzilgan zaxira (bir qator ikki marta) — tiklash rad etildi VA korxona ma'lumoti O'ZGARMADI (tozalash ham qaytdi)",
      bool(_bt_q) and isinstance(nat3, dict) and nat3.get("success") is False and _korxona_holati() == _hol0 and mb() == _m3,
      ({k: str(nat3.get(k))[:200] for k in ("success", "message")} if isinstance(nat3, dict) else nat3, _hol0, _korxona_holati(),
       _m3, mb()))

# ══════════════════════════════════════════════════════════════
section("P — PG parallel: bir yozuvga bir vaqtda ikki taqdir")


def _sekin(s):
    asl = s.commit

    def f():
        time.sleep(0.4)
        asl()
    s.commit = f


def poyga(birinchi, ikkinchi):
    nat = [None, None]
    bar = threading.Barrier(2)

    def t(k, fn, kech):
        s = SessionLocal()
        if kech:
            _sekin(s)
        try:
            try:
                bar.wait(timeout=30)
            except Exception:                   # noqa: BLE001
                pass
            if not kech:
                time.sleep(0.15)
            try:
                nat[k] = fn(s)
                s.commit()
            except Exception as e:              # noqa: BLE001
                try:
                    s.rollback()
                except Exception:               # noqa: BLE001
                    pass
                nat[k] = f"ISTISNO {type(e).__name__}: {str(e)[:200]}"
        finally:
            s.close()
    ts = [threading.Thread(target=t, args=(0, birinchi, True)), threading.Thread(target=t, args=(1, ikkinchi, False))]
    for x in ts:
        x.start()
    for x in ts:
        x.join(timeout=120)
    return nat


if not PG_URL:
    print("  (faqat PG rejimida)")
else:
    yomon = []
    for k in range(3):
        try:
            bP = buyurtma()
        except Exception as _e:                # noqa: BLE001 — asl kodda (tiklash ma'lumotni o'chirgan) qulamasin
            yomon.append(("buyurtma yaratilmadi", str(_e)[:200]))
            continue
        r, AP = brak(bP, 2)
        fn = getattr(crud, "brak_taqdir_belgila", None)
        if fn is None or not AP:
            yomon.append(("funksiya yo'q", AP))
            continue
        n = poyga(lambda s, _a=AP: fn(s, "qaytarish", _a, {"taqdir": "ikkinchi_nav", "narx": 3000}, company_id=1, performed_by="P1"),
                  lambda s, _a=AP: fn(s, "qaytarish", _a, {"taqdir": "kesildi", "ishlatildi": 1, "nomi": "P bo'lak", "miqdor": 1,
                                                           "birlik": "dona"}, company_id=1, performed_by="P2"))
        _fq = [q for q in qatorlar(ri=AP) if q[2]]
        _s = SessionLocal()
        try:
            _tm = _s.query(FinishedProduct).filter(FinishedProduct.from_order_id == bP[0],
                                                   FinishedProduct.brak_taqdir.isnot(None)).count()
        finally:
            _s.close()
        if not (len(_fq) == 1 and _tm == 1 and len(qatorlar(ri=AP)) == 2 and faol(ri=AP)[0] == "kesildi"):
            yomon.append((n, qatorlar(ri=AP), _tm))
    check("P1 ikki taqdir bir vaqtda (3 urinish) — navbat bilan: bitta faol qator (keyingisi), bitta TM partiya, birinchisi bekor",
          not yomon, yomon)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  - " + f)
sys.exit(0 if FAIL == 0 else 1)
