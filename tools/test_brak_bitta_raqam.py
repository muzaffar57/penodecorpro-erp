#!/usr/bin/env python3
"""
test_brak_bitta_raqam.py — kech107, 49-band darvozasi: BRAK SUMMASI — "BITTA RAQAM" (egasi qarori, QAYTA SO'RALMAYDI).

O'LCHANGAN (asl = staging `061e082`, `work/probe107b.py`, SQLite = PG): bir oyda buyurtma braki R1 (haqiqiy xomashyo
27 600), eski yozuv taqlidi R2 (haqiqiy 16 560, yozuvdagi taxminiy summa 28 905), ishlab chiqarish braki (30 400) va omborda
tayyor turgan mahsulot yo'qotishi (50 000) bo'lganda UCH xil "brak": karta / bosh sahifa 86 905, Moliya "Brak" 124 560,
tahlil 136 905 (haqiqiy xomashyo — 74 560).
QAROR: karta, bosh sahifa, tahlil va Moliya "Brak" qatori — BITTA haqiqiy xomashyo narxi (brak chiqim harakatlari,
chiqim paytidagi muzlatilgan narx); omborda tayyor turgan mahsulot shikastlanishi — Moliyada ALOHIDA qator
(`fp_loss_xarajat`, "Tayyor mahsulot yo'qotishi (omborda)"); jami xarajat va sof foyda O'ZGARMAYDI; yozuvdagi saqlangan
summa (`refund_amount`) TEGILMAYDI.

BO'LIMLAR
  A — bitta raqam: karta = Moliya "Brak" = tahlil (Moliya ham, yozuvlar jami ham) = test o'zi hisoblagan harakatlar
  B — bog'lanmagan eski brak harakati: hammasida bor, tahlilda `boglanmagan_qiymat`
  C — oy chegarasi: aynan keyingi oy boshidagi harakat — faqat keyingi oyda (asl: ikkala oyda)
  D — izolyatsiya (B korxona)
  E — PDF: "Tayyor mahsulot yo'qotishi (omborda)" qatori, qatorlar yig'indisi = JAMI
  F — statik

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_brak_bitta_raqam.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_brak_bitta_raqam.py
Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import re
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "brak_bitta_raqam_test"
_DB = os.path.join(tempfile.gettempdir(), "brak_bitta_raqam_test.db")

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
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, services                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, OrderItem, Inventory, InventoryMovement, Recipe, RecipeIngredient,
    ReturnItem, FinishedProduct, FinishedProductLoss, StockSource, ProductionStatus, Employee,
)
from fastapi.testclient import TestClient          # noqa: E402

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
        print(f"  ✗ {label}   {str(detail)[:500]}")


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


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


def taxminan(a, b, eps=0.01):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="BR Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "BR_admin", "Parol123!", UserRole.ADMIN, "BR Admin", company_id=1)
    auth.create_user(_db, "BR_admin_b", "Parol123!", UserRole.ADMIN, "BR Admin B", company_id=2)
PRJ = Project(company_id=1, client_name="BR Mijoz", project_name="BR loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="BR Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="BR Kley", unit="kg", stock_quantity=100_000, price_per_unit=2_000, category="Kimyo")
AKR = Inventory(company_id=1, item_name="BR Akril", unit="kg", stock_quantity=100_000, price_per_unit=10_000, category="Kimyo")
PENO_B = Inventory(company_id=2, item_name="BR B Penoplast", unit="blok", stock_quantity=100, price_per_unit=400_000,
                   volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
H1 = Employee(company_id=1, name="BR Kesuvchi", position="Kesuvchi", is_active=True, is_deleted=False)
_db.add_all([PRJ, PENO, KLEY, AKR, PENO_B, H1])
_db.commit()
R1 = Recipe(company_id=1, name="BR R1", batch_size_kg=100.0)
_db.add(R1)
_db.commit()
_db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=KLEY.id, quantity_kg=60.0),
             RecipeIngredient(recipe_id=R1.id, inventory_id=AKR.id, quantity_kg=40.0)])
_db.commit()
PRJ_ID, PENO_ID, KLEY_ID, AKR_ID, R1_ID, H1_ID, PENO_B_ID = PRJ.id, PENO.id, KLEY.id, AKR.id, R1.id, H1.id, PENO_B.id
with contextlib.redirect_stdout(_quiet):
    _loy = services.get_or_create_loy_stock(_db, _db.get(Recipe, R1_ID))
_loy.stock_quantity = 0.0
_db.commit()
_db.close()


def _kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C, _s1 = _kir("BR_admin")
CB, _s2 = _kir("BR_admin_b")
if (_s1, _s2) != (302, 302):
    print(f"LOGIN BO'LMADI: {(_s1, _s2)}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

# Hisobot davri — Toshkent devor soati (UTC + 5), server kabi.
_BU = datetime.utcnow() + timedelta(hours=5)
YIL, OY = _BU.year, _BU.month
K_YIL, K_OY = (YIL + 1, 1) if OY == 12 else (YIL, OY + 1)
OY_BOSHI = datetime(YIL, OY, 1) - timedelta(hours=5)          # UTC (naive)
OY_OXIRI = datetime(K_YIL, K_OY, 1) - timedelta(hours=5)      # UTC (naive), KIRMAYDI

_n = [0]


def profil(uzunlik, qoplama=False):
    _n[0] += 1
    return {"name": f"BR_D{_n[0]}", "category": "profil", "width": 20, "thickness": 10,
            "length": uzunlik, "quantity": 10, "unit_price": 50_000, "is_coated": bool(qoplama),
            "penoplast_id": PENO_ID, **({"recipe_id": R1_ID} if qoplama else {})}


def yarat(items, recipe_id=None, loy_kg=None):
    tana = {"project_id": PRJ_ID, "order_type": "product", "items": items}
    if recipe_id:
        tana["recipe_id"] = recipe_id
    if loy_kg is not None:
        tana["loy_kg"] = loy_kg
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    d = js(r)
    oid = d.get("id") if isinstance(d, dict) else None
    if not oid:
        raise RuntimeError(f"buyurtma yaratilmadi: {r.status_code} {r.text[:300]}")
    return oid


def brak_tana(oid, miqdor=10, qoplama=False, **qoshimcha):
    d = SessionLocal()
    try:
        it = d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).first()
        iid, nom = it.id, it.name
    finally:
        d.close()
    t = {"order_id": oid, "order_item_id": iid, "item_name": nom, "quantity": miqdor, "unit": "metr",
         "brak_sabab": "boshqa", "reason": "Brak", "refund_amount": 0, "to_stock": False, "coating_applied": bool(qoplama)}
    t.update(qoshimcha)
    return t


def fp_yarat(nom, tayyor=True):
    d = SessionLocal()
    try:
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=True, quantity=100,
                             produced_quantity=100, unit="metr", unit_price=0, cost_price=1_000_000,
                             source=StockSource.PRODUCED, penoplast_id=PENO_ID, recipe_id=R1_ID,
                             unit_volume_m3=0.01, unit_loy_kg=0.5,
                             production_status=(ProductionStatus.READY if tayyor else ProductionStatus.IN_PROGRESS))
        d.add(fp)
        d.commit()
        return fp.id
    finally:
        d.close()


def harakatlar_qiymati(korxona=1, boshi=None, oxiri=None, return_item_id="HAMMA"):
    """Test O'ZI hisoblaydi (serverdan mustaqil): brak chiqim harakatlari — belgi `is_brak`, belgisiz (NULL) eski harakat —
    yozuvga bog'langan YOKI sabab "Brak…"; qiymat — miqdor × chiqim paytidagi narx (u yo'q — material narxi)."""
    d = SessionLocal()
    try:
        jami = 0.0
        for m in d.query(InventoryMovement).filter(InventoryMovement.company_id == korxona,
                                                   InventoryMovement.movement_type == "out").all():
            brak = (m.is_brak is True) or (m.is_brak is None and (m.return_item_id is not None
                                                                   or (m.reason or "").startswith("Brak")))
            if not brak:
                continue
            if boshi is not None and not (boshi <= m.created_at < oxiri):
                continue
            if return_item_id != "HAMMA" and m.return_item_id != return_item_id:
                continue
            narx = m.unit_cost if m.unit_cost is not None else (
                float(d.get(Inventory, m.inventory_id).price_per_unit or 0) if m.inventory_id else 0.0)
            jami += float(m.quantity or 0) * float(narx)
        return round(jami, 2)
    finally:
        d.close()


def karta(c=None):
    return js(req(c or C, "get", "/api/returns/stats")) or {}


def moliya(yil=YIL, oy=OY, c=None):
    return js(req(c or C, "get", f"/api/finance/report?year={yil}&month={oy}")) or {}


def tahlil(yil=YIL, oy=OY, c=None):
    return js(req(c or C, "get", "/api/reports/brak-tahlil", params={"year": yil, "month": oy, "oylar": 1})) or {}


# ══════════════════════════════════════════════════════════════
section("A — bitta raqam: karta = Moliya «Brak» = tahlil = haqiqiy xomashyo")
o1 = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=10)
o2 = yarat([profil(100, qoplama=True)], recipe_id=R1_ID, loy_kg=10)
o3 = yarat([profil(40)])
r1 = req(C, "post", "/api/returns", json=brak_tana(o1, miqdor=5, qoplama=True, brak_bosqich="kesish"))
r2 = req(C, "post", "/api/returns", json=brak_tana(o2, miqdor=3, qoplama=True, brak_sabab="ishchi", brak_javobgar_id=H1_ID))
rx = req(C, "post", "/api/returns", json=dict(brak_tana(o3, miqdor=1), reason="Ortiqcha", brak_sabab=None, to_stock=False,
                                              coating_applied=False))
ID1, ID2 = (js(r1) or {}).get("id"), (js(r2) or {}).get("id")
F1 = fp_yarat("BR tayyor 1")
F3 = fp_yarat("BR jarayon 1", tayyor=False)
l2 = req(C, "post", "/api/finished/loss", json={"brak_sabab": "boshqa", "finished_product_id": F1, "quantity": 5, "reason": "tashishda sindi",
                                                 "brak_bosqich": "saqlash_tashish"})
l1 = req(C, "post", "/api/finished/production-brak", json={"brak_sabab": "boshqa", "finished_product_id": F3, "brak_qty": 4, "brak_bosqich": "qoplash"})
check("A0 fikstura: 2 brak, 1 boshqa qaytarish, tayyor turgan yo'qotish, ishlab chiqarish braki — hammasi 200",
      [x.status_code for x in (r1, r2, rx, l2, l1)] == [200] * 5 and ID1 and ID2,
      [(x.status_code, x.text[:120]) for x in (r1, r2, rx, l2, l1)])
_d = SessionLocal()
try:
    V1 = harakatlar_qiymati(return_item_id=ID1)
    V2 = harakatlar_qiymati(return_item_id=ID2)
    _r2 = _d.get(ReturnItem, ID2)
    REFUND2 = round(float(_r2.refund_amount or 0) + 12345, 2)
    _r2.refund_amount = REFUND2                    # zip 54 dan oldingi yozuv taqlidi — taxminiy summa
    _d.commit()
    _yoq = {("ish" if (l.reason or "").startswith(crud._ISH_BRAK_BELGI) else "tayyor"): round(float(l.cost_amount or 0), 2)
            for l in _d.query(FinishedProductLoss).all()}
finally:
    _d.close()
# Brakdan KEYIN material narxlari o'zgaradi (yangi kirim) — brak qiymati o'zgarmasligi SHART (chiqim paytidagi narx).
_d = SessionLocal()
try:
    _d.get(Inventory, PENO_ID).price_per_unit = 777_777
    _d.get(Inventory, AKR_ID).price_per_unit = 55_555
    _d.get(Inventory, KLEY_ID).price_per_unit = 3_333
    _d.commit()
finally:
    _d.close()
check("A0c narx keyin o'zgardi — yozuvlar qiymati (chiqim paytidagi narx) o'zgarmadi",
      harakatlar_qiymati(return_item_id=ID1) == V1 and harakatlar_qiymati(return_item_id=ID2) == V2, (V1, V2))
HAQIQIY = harakatlar_qiymati(boshi=OY_BOSHI, oxiri=OY_OXIRI)
check("A0b haqiqiy xomashyo (test hisobi) = R1 + R2 + ishlab chiqarish braki; R2 yozuvida taxminiy summa BOSHQA",
      V1 > 0 and V2 > 0 and _yoq.get("ish", 0) > 0 and taxminan(HAQIQIY, V1 + V2 + _yoq.get("ish", 0))
      and abs(REFUND2 - V2) > 1, (HAQIQIY, V1, V2, _yoq, REFUND2))
KA, MO, TA = karta(), moliya(), tahlil()
check("A1 karta «Brak qiymati (bu oy)» = haqiqiy xomashyo (asl: yozuvlardagi summa — 86 905 kabi)",
      taxminan(KA.get("brak_month_value"), round(HAQIQIY), 0.5), (KA.get("brak_month_value"), HAQIQIY))
check("A2 Moliya «Brak» = haqiqiy xomashyo (asl: + tayyor turgan yo'qotish — 124 560 kabi)",
      taxminan(MO.get("brak_xarajat"), round(HAQIQIY), 0.5), (MO.get("brak_xarajat"), HAQIQIY))
check("A3 tahlil: Moliya ham, yozuvlar jami ham — AYNAN shu raqam (asl: yozuvlar + HAMMA yo'qotishlar — 136 905 kabi)",
      TA.get("brak_xarajat") == MO.get("brak_xarajat") and taxminan(TA.get("yozuvlar_qiymati"), HAQIQIY)
      and TA.get("boglanmagan_qiymat") == 0, {k: TA.get(k) for k in ("brak_xarajat", "yozuvlar_qiymati", "boglanmagan_qiymat")})
check("A4 karta = Moliya = tahlil — bitta raqam", KA.get("brak_month_value") == MO.get("brak_xarajat") == TA.get("brak_xarajat"),
      (KA.get("brak_month_value"), MO.get("brak_xarajat"), TA.get("brak_xarajat")))
check("A5 tayyor turgan yo'qotish — Moliyada ALOHIDA qator (`fp_loss_xarajat`), tahlilda `tayyor_yoqotish_qiymati`",
      taxminan(MO.get("fp_loss_xarajat"), _yoq.get("tayyor"), 0.5) and taxminan(TA.get("tayyor_yoqotish_qiymati"), _yoq.get("tayyor")),
      (MO.get("fp_loss_xarajat"), TA.get("tayyor_yoqotish_qiymati"), _yoq))
check("A6 jami xarajat O'ZGARMADI: = Brak + tayyor turgan yo'qotish (bu oyda boshqa xarajat yo'q), sof foyda = −jami",
      taxminan(MO.get("jami_xarajat"), (MO.get("brak_xarajat") or 0) + (MO.get("fp_loss_xarajat") or 0), 1)
      and taxminan(MO.get("sof_foyda"), -(MO.get("jami_xarajat") or 0), 1),
      {k: MO.get(k) for k in ("jami_xarajat", "brak_xarajat", "fp_loss_xarajat", "sof_foyda")})
_sab = {x.get("kod"): x.get("qiymat") for x in (TA.get("sabablar") or [])}
_bos = {x.get("kod"): (x.get("soni"), x.get("qiymat")) for x in (TA.get("bosqichlar") or [])}
check("A7 taqsimot: 3 yozuv (R1, R2, ishlab chiqarish braki); R2 (sabab 'ishchi') — HAQIQIY xomashyo, yozuvdagi summa emas",
      TA.get("yozuvlar_soni") == 3 and taxminan(_sab.get("ishchi"), V2) and not taxminan(_sab.get("ishchi"), REFUND2),
      (TA.get("yozuvlar_soni"), _sab, V2, REFUND2))
check("A8 tayyor turgan yo'qotish taqsimotga KIRMAYDI (bosqich 'saqlash_tashish' yo'q), ro'yxatda turi bilan QOLADI",
      "saqlash_tashish" not in _bos and sorted(x.get("turi") for x in (TA.get("yoqotishlar") or []))
      == ["Ishlab chiqarish braki", "Yo'qotish (tayyor turgan)"], (_bos, TA.get("yoqotishlar")))
_ul = sum(float(x.get("ulush") or 0) for x in (TA.get("bosqichlar") or []))
check("A9 ulushlar yig'indisi ~100 % (faqat brak yozuvlari)", abs(_ul - 100.0) <= 0.5, _ul)
check("A10 karta: soni — brak yozuvlari (2 buyurtma braki + 1 ishlab chiqarish braki); jami (hamma vaqt) = shu oy",
      KA.get("brak_month_count") == 3 and KA.get("brak_total_value") == KA.get("brak_month_value"),
      {k: KA.get(k) for k in ("brak_month_count", "brak_total_count", "brak_total_value", "brak_month_value")})
_d = SessionLocal()
try:
    _r2b = round(float(_d.get(ReturnItem, ID2).refund_amount or 0), 2)
finally:
    _d.close()
check("A11 yozuvdagi saqlangan summa TEGILMADI (42-band)", _r2b == REFUND2, (_r2b, REFUND2))
_q = crud.brak_yozuv_qiymatlari(SessionLocal(), [ID1, ID2, 999999], company_id=1) if hasattr(crud, "brak_yozuv_qiymatlari") else None
check("A12 `crud.brak_yozuv_qiymatlari`: har yozuv — bog'langan harakatlar; harakatsiz / noma'lum — 0",
      isinstance(_q, dict) and taxminan(_q.get(ID1), V1) and taxminan(_q.get(ID2), V2) and _q.get(999999) == 0, _q)

# ══════════════════════════════════════════════════════════════
section("B — yozuvga bog'lanmagan eski brak harakati (bog'lamdan oldingi yozuv)")
_d = SessionLocal()
try:
    _d.add(InventoryMovement(company_id=1, inventory_id=AKR_ID, item_name="BR Akril", movement_type="out", quantity=3,
                             unit="kg", reason="Brak (eski) — BR buyurtma", unit_cost=1000, is_brak=None,
                             return_item_id=None))
    # Yozuvga bog'langan, lekin brak EMAS (belgi False) chiqim — hech qayerga kirmasligi SHART (brak sharti yagona).
    _d.add(InventoryMovement(company_id=1, inventory_id=AKR_ID, item_name="BR Akril", movement_type="out", quantity=1,
                             unit="kg", reason="BR tuzatish (brak emas)", unit_cost=5000, is_brak=False,
                             return_item_id=ID1))
    _d.commit()
finally:
    _d.close()
HAQIQIY_B = harakatlar_qiymati(boshi=OY_BOSHI, oxiri=OY_OXIRI)
KB_, MB_, TB_ = karta(), moliya(), tahlil()
check("B1 eski harakat (3 000) — karta, Moliya, tahlil (Moliya) — hammasida bir xil qo'shildi",
      taxminan(HAQIQIY_B - HAQIQIY, 3000) and KB_.get("brak_month_value") == MB_.get("brak_xarajat") == TB_.get("brak_xarajat")
      == round(HAQIQIY_B), (HAQIQIY_B, KB_.get("brak_month_value"), MB_.get("brak_xarajat"), TB_.get("brak_xarajat")))
check("B2 tahlilda yozuvlar o'zgarmadi, farq — `boglanmagan_qiymat` 3 000 (Moliya = yozuvlar + bog'lanmagan)",
      TB_.get("yozuvlar_soni") == 3 and taxminan(TB_.get("yozuvlar_qiymati"), HAQIQIY) and taxminan(TB_.get("boglanmagan_qiymat"), 3000)
      and taxminan((TB_.get("yozuvlar_qiymati") or 0) + (TB_.get("boglanmagan_qiymat") or 0), HAQIQIY_B),
      {k: TB_.get(k) for k in ("yozuvlar_soni", "yozuvlar_qiymati", "boglanmagan_qiymat")})

# ══════════════════════════════════════════════════════════════
section("C — oy chegarasi (oxiri KIRMAYDI)")
_d = SessionLocal()
try:
    _d.add(InventoryMovement(company_id=1, inventory_id=AKR_ID, item_name="BR Akril", movement_type="out", quantity=2,
                             unit="kg", reason="Brak — BR chegara", unit_cost=1000, is_brak=True, created_at=OY_OXIRI))
    _d.add(InventoryMovement(company_id=1, inventory_id=AKR_ID, item_name="BR Akril", movement_type="out", quantity=1,
                             unit="kg", reason="Brak — BR boshi", unit_cost=500, is_brak=True, created_at=OY_BOSHI))
    _d.commit()
finally:
    _d.close()
_bm_joriy = crud.get_brak_material_summary(SessionLocal(), start_date=OY_BOSHI, end_date=OY_OXIRI, company_id=1)
_bm_kel = crud.get_brak_material_summary(SessionLocal(), start_date=OY_OXIRI,
                                          end_date=datetime(K_YIL + (1 if K_OY == 12 else 0), 1 if K_OY == 12 else K_OY + 1, 1)
                                          - timedelta(hours=5), company_id=1)
check("C1 keyingi oy boshidagi (aynan 00:00 Toshkent) harakat shu oyda YO'Q (asl: `<=` bilan ikkala oyda), oy boshidagisi — BOR",
      taxminan(_bm_joriy.get("total_value"), HAQIQIY_B + 500) and taxminan(_bm_kel.get("total_value"), 2000),
      (_bm_joriy.get("total_value"), HAQIQIY_B + 500, _bm_kel.get("total_value")))
MC_, KC_ = moliya(), karta()
check("C2 Moliya va karta ham shu qoida bilan (chegara harakati keyingi oyda; «hamma vaqt» da — bir marta)",
      MC_.get("brak_xarajat") == KC_.get("brak_month_value") == round(HAQIQIY_B + 500)
      and taxminan(KC_.get("brak_total_value"), round(HAQIQIY_B + 500 + 2000), 0.5),
      (MC_.get("brak_xarajat"), KC_.get("brak_month_value"), KC_.get("brak_total_value"), HAQIQIY_B))

# ══════════════════════════════════════════════════════════════
section("D — izolyatsiya (B korxona)")
_d = SessionLocal()
try:
    _d.add(InventoryMovement(company_id=2, inventory_id=PENO_B_ID, item_name="BR B Penoplast", movement_type="out",
                             quantity=1, unit="blok", reason="Brak — B korxona", unit_cost=400_000, is_brak=True))
    _d.commit()
    # Buzilgan bog'lam (ORM qo'riqchisini chetlab, xom SQL): B korxona harakati A yozuviga bog'langan — A hisobiga KIRMASIN.
    from sqlalchemy import text as _t107
    _d.execute(_t107("INSERT INTO inventory_movements (company_id, inventory_id, item_name, movement_type, quantity, unit, "
                     "reason, return_item_id, unit_cost, is_brak, created_at) VALUES (2, :inv, 'BR B buzuq', 'out', 1, 'blok', "
                     "'Brak — buzilgan bog''lam', :rid, 7777, :b, :t)"),
               {"inv": PENO_B_ID, "rid": ID1, "b": True, "t": datetime.utcnow()})
    _d.commit()
finally:
    _d.close()
KD_, MD_, TD_ = karta(), moliya(), tahlil()
KDB, MDB = karta(CB), moliya(c=CB)
check("D1 B korxona braki A ning karta (oy va hamma vaqt) / Moliya / tahlilida (bog'lanmagan ham) YO'Q",
      KD_.get("brak_month_value") == MD_.get("brak_xarajat") == TD_.get("brak_xarajat") == round(HAQIQIY_B + 500)
      and taxminan(KD_.get("brak_total_value"), round(HAQIQIY_B + 500 + 2000), 0.5)
      and taxminan(TD_.get("boglanmagan_qiymat"), 3500) and taxminan(TD_.get("yozuvlar_qiymati"), HAQIQIY),
      (KD_.get("brak_month_value"), MD_.get("brak_xarajat"), TD_.get("brak_xarajat"), KD_.get("brak_total_value"),
       TD_.get("boglanmagan_qiymat"), TD_.get("yozuvlar_qiymati"), HAQIQIY))
check("D2 B korxonada — faqat o'ziniki (400 000 + buzilgan bog'lamli 7 777), karta = Moliya",
      KDB.get("brak_month_value") == MDB.get("brak_xarajat") == 407777, (KDB.get("brak_month_value"), MDB.get("brak_xarajat")))

# ══════════════════════════════════════════════════════════════
section("E — Moliya PDF: alohida qator va JAMI")
import finance_pdf as _fpdf                        # noqa: E402
_matnlar = []
_asl_P = _fpdf.Paragraph


def _P(text, *a, **k):
    _matnlar.append(str(text))
    return _asl_P(text, *a, **k)


_s = SessionLocal()
try:
    _rep = services.get_monthly_report(_s, YIL, OY, company_id=1)
    _bm = crud.get_brak_material_summary(_s, start_date=OY_BOSHI, end_date=OY_OXIRI, company_id=1)
    _fpdf.Paragraph = _P
    try:
        _pdf = _fpdf.generate_finance_report_pdf(_rep, [], _bm.get("by_material", []), YIL, OY, None, db=_s, company_id=1)
    except Exception as e:                 # noqa: BLE001
        _pdf = f"{type(e).__name__}: {e}"
    finally:
        _fpdf.Paragraph = _asl_P
finally:
    _s.close()


def _pdf_qatorlar(m):
    """"Xarajatlar tafsiloti" jadvali: [(nom, summa)] — nom va "N so'm" ketma-ket Paragraph lar."""
    try:
        i = m.index("Xarajatlar tafsiloti (nomma-nom)")
    except ValueError:
        return []
    q, k = [], i + 1
    while k + 1 < len(m):
        if "JAMI XARAJAT" in m[k]:          # jadval oxiri (jami qatori) — undan keyingilar (sof foyda) jadvalga kirmaydi
            break
        s2 = re.fullmatch(r"(-?[\d  ]+) so'm", m[k + 1].replace(" ", " ").replace(" ", " "))
        if s2 and m[k] not in ("Xarajat nomi", "Summa"):
            q.append((m[k], int(re.sub(r"\D", "", s2.group(1)) or 0) * (-1 if s2.group(1).strip().startswith("-") else 1)))
            k += 2
        else:
            k += 1
    return q


_qat = _pdf_qatorlar(_matnlar)
_jami_kut = float(_rep.get("jami_xarajat") or 0) + float(_rep.get("ishlab_chiqarish_xarajat") or 0)
check("E1 PDF yaratildi; \"Tayyor mahsulot yo'qotishi (omborda)\" qatori — tayyor turgan yo'qotish summasi bilan",
      isinstance(_pdf, (bytes, bytearray))
      and any(n == "Tayyor mahsulot yo'qotishi (omborda)" and taxminan(v, round(_yoq.get("tayyor", 0)), 1) for n, v in _qat),
      (_qat, str(_pdf)[:100]))
check("E2 PDF qatorlari yig'indisi = JAMI (jami xarajat + ishlab chiqarish), ±1 so'm har qatorga (asl: tayyor turgan yo'qotish qatori YO'Q)",
      _qat and abs(sum(v for _, v in _qat) - _jami_kut) <= len(_qat), (sum(v for _, v in _qat), _jami_kut, _qat))

# ══════════════════════════════════════════════════════════════
section("F — statik")
_c = fayl("crud.py")
_i = _c.find("def get_return_stats(")
_fn = _c[_i:_c.find("\ndef ", _i + 10)] if _i != -1 else ""
check("F1 karta qiymati — Moliya bilan BIR funksiya (`get_brak_material_summary`, Toshkent oyi); `refund_amount` yig'indisi YO'Q",
      "get_brak_material_summary(db, start_date=_oy_boshi, end_date=_oy_oxiri" in _fn and "refund_amount or 0) for r in month_brak" not in _fn
      and "_tashkent_oy_oraligi(now.year, now.month)" in _fn, "")
_sv = fayl("services.py")
check("F2 Moliya: tayyor turgan yo'qotish `brak_xarajat` ga QO'SHILMAYDI, jami xarajatga alohida qo'shiladi",
      "brak_xarajat += fp_loss_xarajat" not in _sv and "        fp_loss_xarajat +" in _sv, "")
check("F3 brak harakati narxi — YAGONA qoida (`_brak_harakat_narxi`), oy oxiri KIRMAYDI (`<`)",
      "return _brak_harakat_narxi(harakat, inv)" in _c and "InventoryMovement.created_at < end_date" in _c
      and "InventoryMovement.created_at <= end_date" not in _c, "")
check("F4 finance.html / finance_pdf.py / returns.html / finished.html / dashboard.html — yangi qator va matnlar",
      "d.fp_loss_xarajat" in fayl("templates/finance.html")
      and "Tayyor mahsulot yo'qotishi (omborda)" in fayl("finance_pdf.py")
      and "d.boglanmagan_qiymat" in fayl("templates/returns.html") and "d.tayyor_yoqotish_qiymati" in fayl("templates/returns.html")
      and "Moliyada Brak xarajatiga" not in fayl("templates/finished.html")
      and "Brak qiymati (bu oy, xomashyo)" in fayl("templates/dashboard.html"), "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   - " + f)
sys.exit(0 if FAIL == 0 else 1)
