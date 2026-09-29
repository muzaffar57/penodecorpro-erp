#!/usr/bin/env python3
"""
test_tayyor_guruh.py — kech114 darvozasi (2026-09-29): «Tayyor mahsulotlar» guruhlash (egasi QARORI «7A»), ombor qiymati
(QAROR — MRP sotuv narxi «Hozirgidek qo'lda»: narxsiz partiya TANNARX bo'yicha), mahsulot turlari jadvali («5B») va
K114-1 (jarayondagi MRP mahsuloti «Ishlab chiqarish» bo'limini chetlab o'tmaydi).

NIMA UCHUN KERAK (asl kod `592a2e3` da O'LCHANGAN — `work/k114/probe_mrp_tm.py`, SQLite = PG)
------------------------------------------------------------------------------------------------
K114-1: «Tayyor mahsulotlar» sahifasida JARAYONDAGI MRP mahsuloti qatorida «✓ Sotuvga tayyor» va «✕ Bekor qilish» bor edi.
  * `POST /api/finished/{id}/complete` → 200: TM «tayyor», tannarx 0, xomashyo YECHILMAGAN, ishlab chiqarish «jarayonda»;
    5 qop × 40 000 sotildi — sotuv tannarxi 0, foyda 200 000 (aslida 168 500); keyin «Yakunlash» 63 000 tannarxni qolgan
    5 qopga yozdi (1 qop 12 600 — 2 barobar), TM foydasi −63 000.
  * `DELETE /api/finished/{id}` → 200: TM o'chdi, ishlab chiqarish «jarayonda» qoldi; «Yakunlash» 200 — 20 kg kley
    (63 000) yechildi, omborga HECH NARSA kirmadi.
  Endi: MRP mahsuloti (`category == "dynamic_bom"`) holati faqat «Ishlab chiqarish» bo'limida o'zgaradi (400 + qayerda
  qilinishi), jarayonda sotish / kamaytirish xabari ham o'sha yerga yo'llaydi; tayyor mahsuloti yo'q (eski / chetlab
  o'tilgan) ishlab chiqarish yakunlanmaydi — 409, reja oynasi ham shuni aytadi (`production_service._yakunlash_tm_xatosi`).
Ombor qiymati: MRP partiyasining sotuv narxi 0 (sotishda yoziladi) — «Ombor qiymati» uni 0 deb olardi; «Jami miqdor» qop,
  m, m² ni bitta songa qo'shardi («134 birlik»). Endi narxsiz partiya — qoldiq tannarxi, miqdor — birliklar bo'yicha.
Turlar jadvali: `GET /api/production/product-types/xulosa` — omborda / band / jarayonda va har retseptning 1 birlik
  taxminiy tannarxi retsept oynasidagi (`POST /boms/preview`) AYNAN hisob bilan; so'rovlar soni tur soniga bog'liq emas.

BO'LIMLAR: K — K114-1; T — tayyor mahsuloti yo'q ishlab chiqarish; S — `/api/finished/stats`; P — `/api/finished`
maydonlari; X — turlar jadvali; I — korxonalar ajratilgan; Z — statik.
REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi. Asl kodga qarshi QULAMAYDI (yangi yordamchilar `getattr`
bilan, HTTP istisno — 599).
    python3 tools/test_tayyor_guruh.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tayyor_guruh.py
"""
import os
import sys
import json
import tempfile
import io
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tayyor_guruh_test"
_T = tempfile.mkdtemp()
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tayyor_guruh_test.db')}"

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
import production_service                          # noqa: E402

from sqlalchemy import event, text                 # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import UserRole, Inventory, FinishedProduct, ProductionStatus   # noqa: E402
from production_models import ProductionOrder, Company                       # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        detail = f"{detail} [{type(e).__name__}: {e}]"
        cond = False
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


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
    j = js(r)
    if isinstance(j, dict):
        d = j.get("detail", j)
        if isinstance(d, dict):
            return str(d.get("message") or d)
        return str(d)
    return str(getattr(r, "text", ""))[:300]


def yaqin(a, b, eps=1e-6):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


MRP_X = getattr(crud, "_MRP_JARAYON_XABAR", "«Ishlab chiqarish» bo'limida ishlab chiqarilmoqda")
TM_YOQ = getattr(production_service, "TM_YOQ_XABARI", "Tayyor mahsulotlar»dagi yozuvi o'chirilgan")

# ══════════════════════════════════════════════════════════════
section("0. Fikstura")
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    if not _db.query(Company).filter(Company.id == 2).first():
        _db.add(Company(id=2, name="TG Korxona B"))
        _db.commit()
    auth.create_user(_db, "TG_A", "Parol123!", UserRole.ADMIN, "TG Admin A", company_id=1)
    auth.create_user(_db, "TG_B", "Parol123!", UserRole.ADMIN, "TG Admin B", company_id=2)
_db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
check("login A", req(C, "post", "/login", data={"username": "TG_A", "password": "Parol123!"},
                     follow_redirects=False).status_code in (302, 303))
check("login B", req(CB, "post", "/login", data={"username": "TG_B", "password": "Parol123!"},
                     follow_redirects=False).status_code in (302, 303))
ID = {}


def mat(c, nom, unit, stock, price, **k):
    r = req(c, "post", "/api/inventory", json=dict({"item_name": nom, "unit": unit, "stock_quantity": stock,
                                                    "price_per_unit": price}, **k))
    return (js(r) or {}).get("id")


def tur(c, nom, unit, shablon, formula, qoplama=False):
    t = {"name": nom, "unit": unit, "input_template": shablon, "pricing_formula": formula, "supports_coating": qoplama}
    if qoplama:
        t["coating_price_multiplier"] = 2
    return (js(req(c, "post", "/api/production/product-types", json=t)) or {}).get("id")


def retsept(c, pt, nom, items, partiya=1):
    return (js(req(c, "post", "/api/production/boms", json={"product_type_id": pt, "variant_name": nom,
                                                             "batch_quantity": partiya, "items": items})) or {}).get("id")


def po(c, pt, bom, miq, *amallar):
    r = req(c, "post", "/api/production/orders", json={"product_type_id": pt, "bom_id": bom, "quantity": miq,
                                                       "source_type": "warehouse_stock"})
    pid = ((js(r) or {}).get("production_order") or {}).get("id")
    for a in amallar:
        req(c, "post", f"/api/production/orders/{pid}/{a}")
    return pid


def po_holat(pid):
    s = SessionLocal()
    try:
        p = s.get(ProductionOrder, pid)
        return (p.status, p.finished_product_id) if p else (None, None)
    finally:
        s.close()


def fp_holat(fid):
    s = SessionLocal()
    try:
        f = s.get(FinishedProduct, fid) if fid else None
        if f is None:
            return None
        return {"holat": f.production_status.value if f.production_status else None, "miq": float(f.quantity or 0),
                "tannarx": float(f.cost_price or 0), "narx": float(f.unit_price or 0)}
    finally:
        s.close()


def ombor(iid):
    s = SessionLocal()
    try:
        i = s.get(Inventory, iid)
        return round(float(i.stock_quantity), 6) if i else None
    finally:
        s.close()


ID["kley"] = mat(C, "TG Kley", "kg", 200, 3150)
ID["qum"] = mat(C, "TG Qum", "kg", 1000, 820)
ID["boyoq"] = mat(C, "TG Boyoq", "kg", 50, 24000)
ID["setka"] = mat(C, "TG Setka", "m²", 100, 0)
ID["kafel"] = tur(C, "TG Kafel kley", "qop", "weight_volume", "unit_based")
ID["trav"] = tur(C, "TG Travertin", "m²", "quantity_only", "unit_based", True)
ID["kafel_b"] = retsept(C, ID["kafel"], "25 kg", [{"inventory_id": ID["kley"], "quantity": 2}])
ID["kafel_n"] = retsept(C, ID["kafel"], "Setkali", [{"inventory_id": ID["kley"], "quantity": 2},
                                                    {"inventory_id": ID["setka"], "quantity": 1}])
TRAV_ITEMS = [{"inventory_id": ID["qum"], "quantity": 5},
              {"inventory_id": ID["kley"], "quantity": 1, "scrap_factor_percent": 10},
              {"inventory_id": ID["boyoq"], "quantity": 0.15, "is_optional": True, "is_coating": True,
               "fixed_cost_per_unit": 800}]
ID["trav_b"] = retsept(C, ID["trav"], "Standart", TRAV_ITEMS)
ID["trav_eski"] = retsept(C, ID["trav"], "Eski", [{"inventory_id": ID["qum"], "quantity": 9}])
req(C, "delete", f"/api/production/boms/{ID['trav_eski']}")
ID["nofaol"] = tur(C, "TG Nofaol tur", "dona", "quantity_only", "unit_based")
req(C, "delete", f"/api/production/product-types/{ID['nofaol']}")
check("fikstura: 4 material, 3 tur, 4 retsept", all(ID.get(k) for k in (
    "kley", "qum", "boyoq", "setka", "kafel", "trav", "kafel_b", "kafel_n", "trav_b", "trav_eski", "nofaol")), ID)

# Penoplast (eski yo'l) — «Sotuvga tayyor» unda o'zgarmagan bo'lishi SHART
_s = SessionLocal()
import schemas                                     # noqa: E402
with contextlib.redirect_stdout(_quiet):
    _pen = crud.add_item(_s, schemas.InventoryCreate(item_name="TG Penoplast", unit="blok", stock_quantity=100,
                                                     price_per_unit=500000, is_penoplast=True, volume_per_unit=1.0),
                         company_id=1)
ID["pen"] = _pen.id
_s.close()


def penoplast_tm(nom, narx):
    r = req(C, "post", "/api/finished/produce", json={
        "name": nom, "category": "profil", "is_coated": False, "penoplast_id": ID["pen"], "price_per_m3": None,
        "unit_price": narx, "recipe_id": None, "notes": None, "width": 10, "thickness": 10, "length": 10,
        "quantity": 5})
    j = js(r) or {}
    return j.get("id") or j.get("product_id") or (j.get("product") or {}).get("id")


# ══════════════════════════════════════════════════════════════
section("K. K114-1 — jarayondagi MRP mahsuloti «Ishlab chiqarish»ni chetlab o'tmaydi")
# ══════════════════════════════════════════════════════════════
ID["po_k"] = po(C, ID["kafel"], ID["kafel_b"], 6, "start")
_st, ID["fp_k"] = po_holat(ID["po_k"])
kley0 = ombor(ID["kley"])
check("K0 ishlab chiqarish boshlandi, TM «ishlab chiqarilmoqda»", _st == "in_progress" and
      (fp_holat(ID["fp_k"]) or {}).get("holat") == "in_progress", (_st, fp_holat(ID["fp_k"])))
r = req(C, "post", f"/api/finished/{ID['fp_k']}/complete")
check("K1 «Sotuvga tayyor» (POST /api/finished/{id}/complete) → 400, xabar «Ishlab chiqarish» bo'limiga",
      r.status_code == 400 and "«Ishlab chiqarish» bo'limida" in xabar(r), (r.status_code, xabar(r)))
check("K2 … hech narsa o'zgarmadi: TM jarayonda, tannarx 0, ishlab chiqarish jarayonda, kley o'zgarmagan",
      lambda: fp_holat(ID["fp_k"])["holat"] == "in_progress" and po_holat(ID["po_k"])[0] == "in_progress"
      and ombor(ID["kley"]) == kley0, (fp_holat(ID["fp_k"]), po_holat(ID["po_k"]), ombor(ID["kley"]), kley0))
r = req(C, "post", "/api/finished/sell", json={"finished_product_id": ID["fp_k"], "quantity": 1, "unit_price": 40000,
                                               "payment_method": "naqd", "master_id": None, "confirm_below_cost": True})
check("K3 jarayonda sotuv → 400, xabar «Ishlab chiqarish» bo'limiga (ilgari «avval Tayyor deb belgilang»)",
      r.status_code == 400 and "«Ishlab chiqarish» bo'limida" in xabar(r) and "Tayyor\" deb belgilang" not in xabar(r),
      (r.status_code, xabar(r)))
r = req(C, "post", "/api/finished/loss", json={"finished_product_id": ID["fp_k"], "quantity": 1, "reason": "sinov"})
check("K4 jarayonda kamaytirish → 400, xabar «Ishlab chiqarish» bo'limiga", r.status_code == 400
      and "«Ishlab chiqarish» bo'limida" in xabar(r), (r.status_code, xabar(r)))
r = req(C, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": ID["fp_k"], "quantity": 1,
                                                                "unit_price": 40000}],
                                                     "payment_method": "naqd", "master_id": None,
                                                     "confirm_below_cost": True})
check("K5 savatcha sotuv (jarayondagi MRP) → 4xx, xabar «Ishlab chiqarish» bo'limiga",
      400 <= r.status_code < 500 and "«Ishlab chiqarish» bo'limida" in xabar(r), (r.status_code, xabar(r)))
r = req(C, "delete", f"/api/finished/{ID['fp_k']}?return_to_stock=true")
check("K6 «✕ Bekor qilish» (DELETE /api/finished/{id}) → 400, aniq xabar; TM joyida, bog'lam uzilmagan",
      lambda: r.status_code == 400 and xabar(r) == MRP_X and fp_holat(ID["fp_k"]) is not None
      and po_holat(ID["po_k"])[1] == ID["fp_k"], (r.status_code, xabar(r), fp_holat(ID["fp_k"]), po_holat(ID["po_k"])))
_s = SessionLocal()
try:
    _d = crud.delete_finished_product(_s, ID["fp_k"], company_id=1)
    _s.rollback()
except Exception as e:                     # noqa: BLE001
    _d = f"istisno: {e}"
    _s.rollback()
finally:
    _s.close()
check("K7 ikkinchi to'siq: `crud.delete_finished_product` jarayondagi MRP TM ni o'chirmaydi (False)",
      lambda: _d is False and fp_holat(ID["fp_k"]) is not None, _d)
r = req(C, "post", f"/api/production/orders/{ID['po_k']}/complete")
check("K8 «Ishlab chiqarish»da «Yakunlash» → 200: TM tayyor, tannarx 6 × 6 300 = 37 800, kley −12",
      lambda: r.status_code == 200 and fp_holat(ID["fp_k"])["holat"] == "ready"
      and yaqin(fp_holat(ID["fp_k"])["tannarx"], 37800) and yaqin(ombor(ID["kley"]), kley0 - 12),
      (r.status_code, fp_holat(ID["fp_k"]), ombor(ID["kley"])))
r = req(C, "post", f"/api/finished/{ID['fp_k']}/complete")
check("K9 tayyor MRP TM «Sotuvga tayyor» → 400 «allaqachon tayyor»", r.status_code == 400
      and "allaqachon tayyor" in xabar(r), (r.status_code, xabar(r)))
ID["pen1"] = penoplast_tm("TG Karniz", 100000)
r = req(C, "post", f"/api/finished/{ID['pen1']}/complete")
check("K10 penoplast (eski yo'l) jarayondagi TM — «Sotuvga tayyor» 200 (o'zgarmagan)",
      lambda: ID["pen1"] and r.status_code == 200 and fp_holat(ID["pen1"])["holat"] == "ready",
      (ID.get("pen1"), r.status_code, getattr(r, "text", "")[:200]))
ID["pen2"] = penoplast_tm("TG Panel xato", 90000)
r = req(C, "delete", f"/api/finished/{ID['pen2']}")
check("K11 penoplast jarayondagi TM — o'chirish 200 (xato tuzatish, o'zgarmagan)",
      lambda: ID["pen2"] and r.status_code == 200 and fp_holat(ID["pen2"]) is None, (ID.get("pen2"), r.status_code))

# ══════════════════════════════════════════════════════════════
section("T. Tayyor mahsuloti yo'q (eski / chetlab o'tilgan) ishlab chiqarish yakunlanmaydi")
# ══════════════════════════════════════════════════════════════
ID["po_t"] = po(C, ID["kafel"], ID["kafel_b"], 2, "start")
_st, ID["fp_t"] = po_holat(ID["po_t"])
_s = SessionLocal()
_s.execute(text("UPDATE production_orders SET finished_product_id = NULL WHERE id = :i"), {"i": ID["po_t"]})
_s.execute(text("DELETE FROM finished_products WHERE id = :i"), {"i": ID["fp_t"]})
_s.commit()
_s.close()
kley1 = ombor(ID["kley"])
r = req(C, "get", f"/api/production/orders/{ID['po_t']}/preview")
_p = js(r) or {}
check("T1 «Yakunlash» oynasi rejasi: mumkin emas, sababi — tayyor mahsulot yozuvi o'chirilgan",
      r.status_code == 200 and _p.get("mumkin") is False and TM_YOQ in (_p.get("xatolar") or []),
      (r.status_code, _p.get("mumkin"), _p.get("xatolar")))
r = req(C, "post", f"/api/production/orders/{ID['po_t']}/complete")
check("T2 «Yakunlash» → 409 (xabar AYNAN), xomashyo yechilmadi, ishlab chiqarish jarayonda",
      lambda: r.status_code == 409 and xabar(r) == TM_YOQ and ombor(ID["kley"]) == kley1
      and po_holat(ID["po_t"])[0] == "in_progress", (r.status_code, xabar(r), ombor(ID["kley"]), po_holat(ID["po_t"])))
r = req(C, "post", f"/api/production/orders/{ID['po_t']}/cancel")
check("T3 «Bekor qilish» — 200 (chiqish yo'li bor)", lambda: r.status_code == 200
      and po_holat(ID["po_t"])[0] == "cancelled", (r.status_code, po_holat(ID["po_t"])))
# T5: bog'lam BOSHQA korxonaning TM iga (buzilgan / qo'lda o'zgartirilgan yozuv) — «TM bor» deb sanalmaydi
_s = SessionLocal()
_fb = FinishedProduct(company_id=2, name="TG B tovar", category="dynamic_bom", quantity=1, produced_quantity=1, unit="qop",
                      unit_price=0, cost_price=0)
_s.add(_fb)
_s.commit()
ID["fp_b"] = _fb.id
_s.close()
ID["po_t5"] = po(C, ID["kafel"], ID["kafel_b"], 1, "start")
_st5, ID["fp_t5"] = po_holat(ID["po_t5"])
_s = SessionLocal()
_s.execute(text("UPDATE production_orders SET finished_product_id = :b WHERE id = :i"), {"b": ID["fp_b"], "i": ID["po_t5"]})
_s.commit()
_s.close()
kley5 = ombor(ID["kley"])
r = req(C, "post", f"/api/production/orders/{ID['po_t5']}/complete")
check("T5 bog'lam boshqa korxonaning TM iga — yakunlash 409, xomashyo yechilmadi (korxona tekshiruvi)",
      lambda: r.status_code == 409 and xabar(r) == TM_YOQ and ombor(ID["kley"]) == kley5, (r.status_code, xabar(r)))
_s = SessionLocal()
_s.execute(text("UPDATE production_orders SET finished_product_id = :f WHERE id = :i"), {"f": ID["fp_t5"], "i": ID["po_t5"]})
_s.commit()
_s.close()
req(C, "post", f"/api/production/orders/{ID['po_t5']}/cancel")
_s = SessionLocal()
_pt = _s.get(ProductionOrder, ID["po_k"])
check("T4 `_yakunlash_tm_xatosi` — TM bor ishlab chiqarish uchun None",
      lambda: getattr(production_service, "_yakunlash_tm_xatosi")(_s, _pt, 1) is None)
_s.close()

# ══════════════════════════════════════════════════════════════
section("S. `/api/finished/stats` — ombor qiymati (narxsiz — tannarx) va miqdor birliklar bo'yicha")
# ══════════════════════════════════════════════════════════════
ID["po_t2"] = po(C, ID["trav"], ID["trav_b"], 4, "start", "complete")
ID["po_j"] = po(C, ID["kafel"], ID["kafel_b"], 3, "start")
_st, ID["fp_j"] = po_holat(ID["po_j"])
_s = SessionLocal()
_tm = [f for f in _s.query(FinishedProduct).filter(FinishedProduct.company_id == 1, FinishedProduct.quantity > 0).all()]
_kutilgan_jami = sum((float(f.quantity) * float(f.unit_price)) if float(f.unit_price or 0) > 0 else float(f.cost_price or 0)
                     for f in _tm)
_narxli = sum(float(f.quantity) * float(f.unit_price) for f in _tm if float(f.unit_price or 0) > 0)
_narxsiz = sum(float(f.cost_price or 0) for f in _tm if not float(f.unit_price or 0) > 0)
_tayyor_narxsiz = [f for f in _tm if not float(f.unit_price or 0) > 0 and f.production_status == ProductionStatus.READY]
_s.close()
S = js(req(C, "get", "/api/finished/stats")) or {}
check("S1 fikstura: 2 tayyor narxsiz MRP partiya (kafel 6 — 37 800, travertin 4 — 30 260), penoplast 10 m × 100 000, "
      "jarayondagi kafel 3", len(_tayyor_narxsiz) == 2 and yaqin(_narxli, 1000000) and yaqin(_narxsiz, 37800 + 30260),
      (len(_tayyor_narxsiz), _narxli, _narxsiz))
check("S2 total_value = narxli + narxsiz tannarx = 1 068 060 (ilgari narxsiz 0 deb olinardi — 1 000 000)",
      S.get("total_value") == round(_kutilgan_jami) == 1068060, (S.get("total_value"), _kutilgan_jami))
check("S3 narxli_qiymat 1 000 000, narxsiz_tannarx_qiymati 68 060, narxsiz_soni 2 (jarayondagi sanalmaydi)",
      S.get("narxli_qiymat") == 1000000 and S.get("narxsiz_tannarx_qiymati") == 68060 and S.get("narxsiz_soni") == 2,
      {k: S.get(k) for k in ("narxli_qiymat", "narxsiz_tannarx_qiymati", "narxsiz_soni")})
_mq = {m["birlik"]: m["miqdor"] for m in S.get("miqdorlar") or []}
check("S4 miqdorlar — birliklar bo'yicha, jarayondagisiz: metr 10, qop 6, m² 4 (ilgari bitta «birlik» yig'indisi)",
      _mq == {"qop": 6.0, "m²": 4.0, "metr": 10.0}, S.get("miqdorlar"))
check("S5 jarayonda_miqdorlar — [qop 3]", [(m["birlik"], m["miqdor"]) for m in S.get("jarayonda_miqdorlar") or []]
      == [("qop", 3)], S.get("jarayonda_miqdorlar"))
check("S6 produced_value ham shu qoida bilan (narxsiz — tannarx) = 1 068 060; returned 0",
      S.get("produced_value") == 1068060 and S.get("returned_value") == 0, S)
check("S7 miqdorlar tartibi — katta miqdordan kichikka", [m["miqdor"] for m in S.get("miqdorlar") or []]
      == sorted([m["miqdor"] for m in S.get("miqdorlar") or []], reverse=True), S.get("miqdorlar"))
r = req(C, "get", "/dashboard")
check("S8 /dashboard va /finished sahifalari 200", r.status_code == 200 and req(C, "get", "/finished").status_code == 200)

# ══════════════════════════════════════════════════════════════
section("P. `/api/finished` — ombor_qiymati, ishlab_chiqarish_id")
# ══════════════════════════════════════════════════════════════
F = {x["id"]: x for x in (js(req(C, "get", "/api/finished")) or []) if isinstance(x, dict)}
check("P1 MRP TM: ishlab_chiqarish_id = shu ishlab chiqarish, ombor_qiymati = qoldiq tannarxi (37 800)",
      lambda: F[ID["fp_k"]]["ishlab_chiqarish_id"] == ID["po_k"] and yaqin(F[ID["fp_k"]]["ombor_qiymati"], 37800),
      F.get(ID["fp_k"]))
check("P2 jarayondagi MRP TM: ishlab_chiqarish_id bor, ombor_qiymati 0",
      lambda: F[ID["fp_j"]]["ishlab_chiqarish_id"] == ID["po_j"] and yaqin(F[ID["fp_j"]]["ombor_qiymati"], 0),
      F.get(ID["fp_j"]))
check("P3 penoplast TM: ishlab_chiqarish_id None, ombor_qiymati = qoldiq × narx (1 000 000), total_value o'zgarmagan",
      lambda: F[ID["pen1"]]["ishlab_chiqarish_id"] is None and yaqin(F[ID["pen1"]]["ombor_qiymati"], 1000000)
      and F[ID["pen1"]]["total_value"] == 1000000, F.get(ID["pen1"]))
_sorov = []


def _sanagich(conn, cursor, statement, params, context, executemany):
    _sorov.append(statement)


_s = SessionLocal()
_f = getattr(crud, "fp_ishlab_chiqarish_raqamlari", None)
event.listen(engine, "before_cursor_execute", _sanagich)
try:
    del _sorov[:]
    _x1 = _f(_s, [ID["fp_k"]], company_id=1) if _f else None
    _n1 = len(_sorov)
    del _sorov[:]
    _x2 = _f(_s, list(F.keys()) + [999999], company_id=1) if _f else None
    _n2 = len(_sorov)
finally:
    event.remove(engine, "before_cursor_execute", _sanagich)
    _s.close()
check("P4 raqamlar xaritasi — BITTA so'rov (1 ta ham, hammasi ham)", _f is not None and _n1 == 1 and _n2 == 1
      and (_x2 or {}).get(ID["fp_j"]) == ID["po_j"], (_n1, _n2, _x2))
_s5 = SessionLocal()
check("P5 begona korxona filtri: B korxonasi uchun A ning TM lari — bo'sh xarita",
      lambda: _f(_s5, list(F.keys()), company_id=2) == {})
_s5.close()

# ══════════════════════════════════════════════════════════════
section("X. Mahsulot turlari jadvali — GET /api/production/product-types/xulosa")
# ══════════════════════════════════════════════════════════════
r = req(C, "get", "/api/production/product-types/xulosa")
XU = js(r) if r.status_code == 200 else []
XU = XU if isinstance(XU, list) else []
XT = {t.get("id"): t for t in XU if isinstance(t, dict)}
check("X1 200; faqat FAOL turlar (nofaol tur yo'q), nomi bo'yicha tartib",
      r.status_code == 200 and set(XT) == {ID["kafel"], ID["trav"]} and [t["name"] for t in XU]
      == sorted(t["name"] for t in XU), (r.status_code, [t.get("name") for t in XU]))
check("X2 tur maydonlari — `ProductTypeRead` bilan bir xil (sahifa oynalari ishlatadi)",
      lambda: all(k in XT[ID["trav"]] for k in ("id", "company_id", "name", "unit", "input_template", "pricing_formula",
                                                 "fixed_unit_price", "supports_coating", "coating_price_multiplier",
                                                 "is_active", "created_at", "notes"))
      and XT[ID["trav"]]["supports_coating"] is True and yaqin(XT[ID["trav"]]["coating_price_multiplier"], 2),
      XT.get(ID["trav"]))
check("X3 Kafel: omborda 6 qop (tayyor), jarayonda 3 (bekor qilingan 2 va yakunlangan sanalmaydi), band 0",
      lambda: yaqin(XT[ID["kafel"]]["omborda"], 6) and yaqin(XT[ID["kafel"]]["jarayonda"], 3)
      and yaqin(XT[ID["kafel"]]["band"], 0), XT.get(ID["kafel"]))
check("X4 Travertin: omborda 4, jarayonda 0; faqat FAOL retsept («Eski» yashirilgan — yo'q)",
      lambda: yaqin(XT[ID["trav"]]["omborda"], 4) and yaqin(XT[ID["trav"]]["jarayonda"], 0)
      and [b["variant_name"] for b in XT[ID["trav"]]["retseptlar"]] == ["Standart"], XT.get(ID["trav"]))
_tb = next((b for b in (XT.get(ID["trav"]) or {}).get("retseptlar", []) if b["id"] == ID["trav_b"]), {})
_pv = js(req(C, "post", "/api/production/boms/preview", json={"product_type_id": ID["trav"], "variant_name": "Standart",
                                                               "batch_quantity": 1, "items": TRAV_ITEMS})) or {}
check("X5 1 m² tannarxi — retsept oynasi (`POST /boms/preview`) bilan AYNAN: doim 7 565, qoplamali 11 965",
      lambda: yaqin(_tb["tannarx"]["doim"], _pv["doim"]["jami"], 1e-9) and yaqin(_tb["tannarx"]["qoplamali"],
                                                                                _pv["qoplamali"]["jami"], 1e-9)
      and yaqin(_tb["tannarx"]["doim"], 7565) and yaqin(_tb["tannarx"]["qoplamali"], 11965)
      and _tb["qoplama_bor"] is True and _tb["materiallar"] == 3, (_tb, _pv.get("doim"), _pv.get("qoplamali")))
_kb = {b["variant_name"]: b for b in (XT.get(ID["kafel"]) or {}).get("retseptlar", [])}
check("X6 Kafel «25 kg» 1 qop ≈ 6 300, qoplama yo'q; «Setkali» — narxi yo'q material ro'yxatda (TG Setka)",
      lambda: yaqin(_kb["25 kg"]["tannarx"]["doim"], 6300) and _kb["25 kg"]["qoplama_bor"] is False
      and _kb["Setkali"]["narxsiz"] == ["TG Setka"] and _kb["25 kg"]["narxsiz"] == [], _kb)
_s = SessionLocal()
_s.execute(text("UPDATE finished_products SET reserved_quantity = 2 WHERE id = :i"), {"i": ID["fp_k"]})
_s.commit()
_s.close()
_xt2 = js(req(C, "get", "/api/production/product-types/xulosa"))
XT2 = {t.get("id"): t for t in (_xt2 if isinstance(_xt2, list) else []) if isinstance(t, dict)}
check("X7 band — tayyor qoldiqning band qismi (2 qop)", lambda: yaqin(XT2[ID["kafel"]]["band"], 2), XT2.get(ID["kafel"]))
_sorov2 = []


def _sanagich2(conn, cursor, statement, params, context, executemany):
    _sorov2.append(statement)


def _xulosa_sorovlari():
    s = SessionLocal()
    event.listen(engine, "before_cursor_execute", _sanagich2)
    try:
        del _sorov2[:]
        _fn = getattr(production_service, "turlar_xulosasi", None)
        if _fn is None:
            return -1
        try:
            _fn(s, 1)
        except Exception:                  # noqa: BLE001
            return -2
        return len(_sorov2)
    finally:
        event.remove(engine, "before_cursor_execute", _sanagich2)
        s.close()


_x_n1 = _xulosa_sorovlari()
for k in range(3):
    _t = tur(C, f"TG Qo'shimcha {k}", "kg", "weight_volume", "unit_based")
    retsept(C, _t, "A", [{"inventory_id": ID["qum"], "quantity": 1}])
    retsept(C, _t, "B", [{"inventory_id": ID["kley"], "quantity": 1}, {"inventory_id": ID["boyoq"], "quantity": 1}])
_x_n2 = _xulosa_sorovlari()
check(f"X8 so'rovlar soni tur / retsept soniga bog'liq emas ({_x_n1} = {_x_n2}; 2 → 5 tur, 3 → 9 retsept)",
      0 < _x_n1 == _x_n2 and _x_n1 <= 8, (_x_n1, _x_n2))
r = req(C, "get", "/api/production/product-types/xulosa")
check("X9 hech narsa yozilmaydi (GET) — ikkinchi chaqiruv natijasi birinchisi bilan bir xil",
      lambda: json.dumps(js(r), sort_keys=True) == json.dumps(js(req(C, "get", "/api/production/product-types/xulosa")),
                                                              sort_keys=True))

# ══════════════════════════════════════════════════════════════
section("I. Korxonalar ajratilgan")
# ══════════════════════════════════════════════════════════════
rb = req(CB, "get", "/api/production/product-types/xulosa")
check("I1 B korxonasi — A ning turlari yo'q (bo'sh ro'yxat)", rb.status_code == 200 and js(rb) == [], (rb.status_code, js(rb)))
SB = js(req(CB, "get", "/api/finished/stats")) or {}
check("I2 B statistikasi — A ning qiymati / miqdori yo'q", SB.get("total_value") == 0 and SB.get("miqdorlar") == []
      and SB.get("narxsiz_soni") == 0, SB)
r = req(CB, "delete", f"/api/finished/{ID['fp_j']}")
check("I3 B → A ning jarayondagi MRP TM ini o'chirish — 404 (korxona tekshiruvi birinchi)", r.status_code == 404, r.status_code)
r = req(CB, "post", f"/api/finished/{ID['fp_j']}/complete")
check("I4 B → A ning TM ini «Sotuvga tayyor» — 400 «Topilmadi» (MRP xabari oracle bermaydi)",
      r.status_code == 400 and "Topilmadi" in xabar(r) and "Ishlab chiqarish" not in xabar(r), (r.status_code, xabar(r)))

# ══════════════════════════════════════════════════════════════
section("Z. Statik")
# ══════════════════════════════════════════════════════════════
_src_crud = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
_src_main = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
_src_ps = open(os.path.join(ROOT, "production_service.py"), encoding="utf-8").read()
check("Z1 `_FP_JARAYONDA_XABAR` to'g'ridan-to'g'ri qaytarilmaydi — hamma joy `_jarayonda_xabari(fp)` orqali",
      '"message": _FP_JARAYONDA_XABAR}' not in _src_crud and _src_crud.count("_jarayonda_xabari(fp)") >= 4)
check("Z2 `retsept_tannarxi` va `turlar_xulosasi` — bitta hisob (`_retsept_satri` + `_retsept_holatlari`)",
      _src_ps.count("_retsept_holatlari(db, company_id,") >= 2 and _src_ps.count("_retsept_satri(") >= 3)
check("Z3 o'chirish marshruti MRP qoidasini tranzaksiyadan OLDIN tekshiradi",
      0 < _src_main.find("crud._mrp_tm_mi(fp) and not crud._fp_tayyormi(fp)")
      < _src_main.find("if not crud.delete_finished_product(db, fp_id, company_id=_cid)"))

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
