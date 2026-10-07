#!/usr/bin/env python3
"""
test_mrp_band_korxona.py — kech109 darvozasi: MRP bandi va ishlab chiqarish bog'lamlari — korxona chegarasi (10b E-1)
va buyurtma tahririda ishlab chiqarishga bog'langan detal (K109-2).

NIMA UCHUN KERAK (O'LCHANGAN — `work/probe109e1.py`, asl kod `bd0b48c`: SQLite, PG 16, PG + TENANT_FILTER=1)
---------------------------------------------------------------------------------------------------------
E-1. A (1-korxona) tayyor mahsuloti B (2-korxona) detaliga band bo'lsa (K93-1 dan oldingi eski ma'lumot shakli):
  * B buyurtmasini / detalini o'chirsa — A bandi 5 → 0 va A jurnaliga B foydalanuvchisi nomi bilan yozuv;
  * TENANT_FILTER=1 da B o'z buyurtmasini / detalini o'chira olmasdi — 500 (FK: A mahsuloti ko'rinmaydi, uzilmaydi);
  * B detalining "kerak" miqdori A mahsuloti hisobiga 10 → 5 (B kam ishlab chiqarardi);
  * ORM qo'riqchisi begona bandni (FinishedProduct) va begona manbani (ProductionOrder) QABUL qilardi;
  * B korxonasini tozalash — PG da 500 (begona ishoralar uzilmasdi).
K109-2. Buyurtma TAHRIRIDA MRP detali olib tashlansa yoki NOMI o'zgartirilsa (moslash nom + tur bo'yicha — eski detal
  o'chadi) va unga ishlab chiqarish bog'langan bo'lsa — PG da 500 "Serverda kutilmagan xato" (FK); SQLite da jim —
  band va manba YO'Q detalga ishora qilib qolardi.

YECHIM (texnik — Claude): `_TENANT_REFS` (FinishedProduct.reserved_for_order_item_id, ProductionOrder manbalari);
`crud._auto_release_mrp_reservations` — o'z TM lari ozod + jurnal, BEGONA TM larda faqat FK bog'lami; `mrp_detal_kerak` —
band faqat detal korxonasidan; `factory_reset_all_data` — begona ishoralar uziladi; `update_order_full` — FAOL bog'lam
(band TM, qoralama / jarayondagi buyurtma) — 400 aniq sabab bilan, tarixiy bog'lam — uziladi.

REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi. `TENANT_FILTER=1` bilan ham (etalon tf1).
    python3 tools/test_mrp_band_korxona.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_band_korxona.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_band_korxona_test"
_DB = os.path.join(tempfile.gettempdir(), "mrp_band_korxona_test.db")
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

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import production_service                      # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import UserRole, Project, Inventory, FinishedProduct, OrderItem  # noqa: E402
from production_models import Company, ProductionOrder  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:400]}")


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


def sql(q, **p):
    """Xom SQL: qatorlar ro'yxati (yoki None); xato -> ('XATO', matn)."""
    try:
        with engine.connect() as c:
            r = c.execute(text(q), p)
            v = [tuple(x) for x in r.fetchall()] if r.returns_rows else None
            c.commit()
            return v
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {str(e)[:200]}")


def bir(q, **p):
    r = sql(q, **p)
    return r[0] if isinstance(r, list) and r else r


# ══════════════════════════════════════════════════════════════
# 0. Fikstura: A (1) va B (2) korxonalari — har birida loyiha, xomashyo, mahsulot turi, retsept
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="MBK B korxona"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "MBK_A", "Parol123!", UserRole.ADMIN, "MBK A", company_id=1)
    auth.create_user(_db, "MBK_B", "Parol123!", UserRole.ADMIN, "MBK B", company_id=2)
ID = {}
for _cid, _h in ((1, "A"), (2, "B")):
    _p = Project(company_id=_cid, client_name=f"MBK {_h} mijoz", project_name=f"MBK {_h} loyiha", total_budget=0,
                 total_paid=0)
    _t = Inventory(company_id=_cid, item_name=f"MBK {_h} Tosh", unit="kg", stock_quantity=1_000_000,
                   price_per_unit=1_000, category="Kimyo")
    _db.add_all([_p, _t])
    _db.commit()
    ID[f"PRJ_{_h}"], ID[f"TOSH_{_h}"] = _p.id, _t.id
_db.close()

C = {}
for _h in ("A", "B"):
    _c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    _lr = req(_c, "post", "/login", data={"username": f"MBK_{_h}", "password": "Parol123!"}, follow_redirects=False)
    C[_h] = _c
    ID[f"PT_{_h}"] = (js(req(_c, "post", "/api/production/product-types", json={
        "name": f"MBK {_h} Travertin", "unit": "m²", "input_template": "quantity_only",
        "pricing_formula": "unit_based"})) or {}).get("id")
    ID[f"BOM_{_h}"] = (js(req(_c, "post", "/api/production/boms", json={
        "product_type_id": ID[f"PT_{_h}"], "variant_name": "Oddiy", "batch_quantity": 1,
        "items": [{"inventory_id": ID[f"TOSH_{_h}"], "quantity": 3}]})) or {}).get("id")
    ID[f"login_{_h}"] = _lr.status_code

_n = [0]


def buyurtma(h, detallar=1, soni=10):
    """MRP detalli buyurtma -> (order_id, [detal id lar]); xato -> (None, [])."""
    its = []
    for _ in range(detallar):
        _n[0] += 1
        its.append({"name": f"MBK_{h}_D{_n[0]}", "category": "mrp_product", "quantity": soni, "unit_price": 100_000,
                    "is_coated": False, "penoplast_id": None, "product_type_id": ID[f"PT_{h}"]})
    r = req(C[h], "post", "/api/orders", json={"project_id": ID[f"PRJ_{h}"], "order_type": "product", "loy_kg": 0,
                                               "items": its}, params={"confirm_shortage": "true"})
    oid = (js(r) or {}).get("id")
    if not oid:
        return None, []
    s = SessionLocal()
    try:
        return oid, [x[0] for x in s.query(OrderItem.id).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()]
    finally:
        s.close()


def po_draft(h, miqdor, oid=None, iid=None):
    tana = {"product_type_id": ID[f"PT_{h}"], "bom_id": ID[f"BOM_{h}"], "quantity": miqdor,
            "source_type": "customer_order" if iid else "warehouse_stock"}
    if iid:
        tana.update({"source_order_id": oid, "source_order_item_id": iid})
    return ((js(req(C[h], "post", "/api/production/orders", json=tana)) or {}).get("production_order") or {}).get("id")


def po(h, miqdor, oid=None, iid=None):
    """Yaratib, boshlab, yakunlaydi -> (tayyor mahsulot id, PO id); xato -> (None, None)."""
    pid = po_draft(h, miqdor, oid, iid)
    if not pid:
        return None, None
    for q in ("start", "complete"):
        if req(C[h], "post", f"/api/production/orders/{pid}/{q}").status_code != 200:
            return None, pid
    s = SessionLocal()
    try:
        return s.get(ProductionOrder, pid).finished_product_id, pid
    finally:
        s.close()


def fp(fid):
    """(korxona, band, band detali)."""
    r = bir("SELECT company_id, reserved_quantity, reserved_for_order_item_id FROM finished_products WHERE id=:i", i=fid)
    return (r[0], round(float(r[1] or 0), 6), r[2]) if isinstance(r, tuple) and len(r) == 3 else r


def jurnal(fid):
    return sql("SELECT action, performed_by, company_id FROM activity_logs WHERE entity_type='finished_product' "
               "AND entity_id=:i AND action='auto_release_reservation' ORDER BY id", i=fid)


def begona_band(fid, iid, miqdor=5):
    """Eski ma'lumot taqlidi — XOM SQL (qo'riqchidan tashqari)."""
    return sql("UPDATE finished_products SET reserved_quantity=:mq, reserved_for_order_item_id=:o WHERE id=:i",
               mq=miqdor, o=iid, i=fid)


def kerak(iid):
    s = SessionLocal()
    try:
        return production_service.mrp_detal_kerak(s, s.get(OrderItem, iid))
    except Exception as e:                 # noqa: BLE001
        return {"XATO": f"{type(e).__name__}: {e}"}
    finally:
        s.close()


def royxat(h, iid):
    L = js(req(C[h], "get", "/api/production/mrp-order-items", params={"product_type_id": ID[f"PT_{h}"]})) or []
    return next((x for x in L if isinstance(x, dict) and x.get("order_item_id") == iid), None) \
        if isinstance(L, list) else ("XATO", L)


def detallar(oid):
    return sql("SELECT id, name FROM order_items WHERE order_id=:o ORDER BY id", o=oid)


def po_holat(pid):
    return bir("SELECT status, source_order_id, source_order_item_id FROM production_orders WHERE id=:p", p=pid)


def tahrir(h, oid, qatorlar):
    tana = {"project_id": ID[f"PRJ_{h}"], "order_type": "product", "loy_kg": 0,
            "items": [{"name": q[0], "category": "mrp_product", "quantity": q[1], "unit_price": 100_000,
                       "is_coated": False, "penoplast_id": None, "product_type_id": ID[f"PT_{h}"]} for q in qatorlar]}
    r = req(C[h], "put", f"/api/orders/{oid}", json=tana, params={"confirm_shortage": "true"})
    d = js(r) or {}
    det = d.get("detail") if isinstance(d, dict) else None
    return r.status_code, (det if isinstance(det, dict) else {"raw": str(det or getattr(r, "text", ""))[:300]})


def orm_yoz(fn):
    """ORM yozuvi -> 'QABUL' / 'RAD <istisno>'."""
    s = SessionLocal()
    try:
        fn(s)
        s.commit()
        return "QABUL"
    except Exception as e:                 # noqa: BLE001
        s.rollback()
        return f"RAD {type(e).__name__}"
    finally:
        s.close()


section("0. Fikstura")
FA = []
for _ in range(9):
    FA.append(po("A", 20)[0])
check("A / B kirish 302, mahsulot turlari va retseptlar, A da 9 ta umumiy omborga TM",
      ID["login_A"] == 302 and ID["login_B"] == 302 and all(ID.get(k) for k in ("PT_A", "PT_B", "BOM_A", "BOM_B"))
      and all(FA) and len(FA) == 9, (ID, FA))

# ══════════════════════════════════════════════════════════════
# 1. E-1 — begona korxona TM i B detaliga band (eski ma'lumot)
# ══════════════════════════════════════════════════════════════
section("1. E-1 — o'chirish, kerak miqdori, jurnal")
O1, I1 = buyurtma("B", 1)
begona_band(FA[0], I1[0])
_k = kerak(I1[0])
check("1.1 B detali 'kerak' = 10 (asl: A mahsuloti hisobiga band 5 → kerak 5)",
      isinstance(_k, dict) and _k.get("band") == 0.0 and _k.get("kerak") == 10.0, _k)
_r = royxat("B", I1[0])
check("1.2 'Mijoz buyurtmasi asosida' ro'yxatida band 0, qolgan 10 (tekshiruv bilan bir xil)",
      isinstance(_r, dict) and _r.get("already_reserved") == 0.0 and _r.get("remaining_quantity") == 10.0, _r)
FB1, _ = po("B", 3, O1, I1[0])
check("1.3 B o'z detaliga 3 ishlab chiqardi — B TM band 3", fp(FB1) == (2, 3.0, I1[0]), fp(FB1))
r = req(C["B"], "delete", f"/api/orders/{O1}")
check("1.4 B buyurtmasini o'chirish — 200 (asl TF1: 500 — begona TM uzilmasdi)", r.status_code == 200,
      f"{r.status_code} {getattr(r, 'text', '')[:200]}")
check("1.5 A TM: band miqdori O'ZGARMADI (5), faqat bog'lam uzildi (asl: 5 → 0)", fp(FA[0]) == (1, 5.0, None),
      fp(FA[0]))
check("1.6 A jurnalida B amalidan yozuv YO'Q (asl: 'auto_release_reservation' — B foydalanuvchisi nomi bilan)",
      jurnal(FA[0]) == [], jurnal(FA[0]))
check("1.7 B o'z TM i — avvalgidek ozod (0, bog'lamsiz) va B jurnalida yozuv", fp(FB1) == (2, 0.0, None)
      and isinstance(jurnal(FB1), list) and len(jurnal(FB1)) == 1 and jurnal(FB1)[0][2] == 2, (fp(FB1), jurnal(FB1)))

O2, I2 = buyurtma("B", 2)
begona_band(FA[1], I2[1])
r = req(C["B"], "delete", f"/api/order-items/{I2[1]}")
check("1.8 B detalini o'chirish — 200 (asl TF1: 500)", r.status_code == 200,
      f"{r.status_code} {getattr(r, 'text', '')[:200]}")
check("1.9 A TM: band 5 qoldi, bog'lam uzildi, A jurnalida yozuv yo'q",
      fp(FA[1]) == (1, 5.0, None) and jurnal(FA[1]) == [], (fp(FA[1]), jurnal(FA[1])))

O3, I3 = buyurtma("B", 1)
begona_band(FA[2], I3[0])
_s = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        _soft = crud.delete_order(_s, O3, soft=True, performed_by="MBK_B")
except Exception as e:                     # noqa: BLE001
    _soft = f"XATO {type(e).__name__}: {e}"
finally:
    _s.close()
check("1.10 yumshoq o'chirish (funksiya) — A TM band 5, bog'lam uzildi, jurnal yo'q",
      _soft is True and fp(FA[2]) == (1, 5.0, None) and jurnal(FA[2]) == [], (_soft, fp(FA[2]), jurnal(FA[2])))

r = req(C["A"], "post", f"/api/finished/{FA[0]}/release-reservation")
check("1.11 A egasi o'z (bog'lamsiz qolgan) bandini o'zi ozod qiladi — 200, band 0",
      r.status_code == 200 and fp(FA[0]) == (1, 0.0, None), f"{r.status_code} {fp(FA[0])}")

section("2. E-1 — ORM qo'riqchisi (yozishda rad)")
O4, I4 = buyurtma("B", 1)
OA, IA = buyurtma("A", 1)
check("2.0 fikstura: A va B buyurtmalari", O4 and I4 and OA and IA, (O4, I4, OA, IA))


def _band(fid, iid):
    def f(s):
        x = s.get(FinishedProduct, fid)
        x.reserved_for_order_item_id = iid
        x.reserved_quantity = 1
    return f


check("2.1 A TM ni B detaliga ORM bilan band qilish — RAD (asl: QABUL)",
      orm_yoz(_band(FA[3], I4[0])).startswith("RAD TenantMismatch"), fp(FA[3]))
check("2.2 A TM ni A detaliga — QABUL (nazorat)", orm_yoz(_band(FA[4], IA[0])) == "QABUL", fp(FA[4]))
FB4, _pb4 = po("B", 2)


def _po(**k):
    def f(s):
        d = {"company_id": 1, "product_type_id": ID["PT_A"], "bom_id": ID["BOM_A"], "source_type": "warehouse_stock",
             "quantity": 1, "status": "draft", "created_by": "t"}
        d.update(k)
        s.add(ProductionOrder(**d))
    return f


check("2.3 A ishlab chiqarish buyurtmasi, manba detali B niki — RAD",
      orm_yoz(_po(source_type="customer_order", source_order_id=OA, source_order_item_id=I4[0])).startswith("RAD"))
check("2.4 A ishlab chiqarish buyurtmasi, manba buyurtmasi B niki — RAD",
      orm_yoz(_po(source_type="customer_order", source_order_id=O4, source_order_item_id=IA[0])).startswith("RAD"))
check("2.5 A ishlab chiqarish buyurtmasi, tayyor mahsuloti B niki — RAD",
      orm_yoz(_po(finished_product_id=FB4)).startswith("RAD"))
check("2.6 A ishlab chiqarish buyurtmasi, mahsulot turi B niki — RAD",
      orm_yoz(_po(product_type_id=ID["PT_B"])).startswith("RAD"))
check("2.7 A ishlab chiqarish buyurtmasi, retsepti B niki — RAD", orm_yoz(_po(bom_id=ID["BOM_B"])).startswith("RAD"))
check("2.8 A ishlab chiqarish buyurtmasi, hammasi A niki — QABUL (nazorat)",
      orm_yoz(_po(source_type="customer_order", source_order_id=OA, source_order_item_id=IA[0])) == "QABUL")

# ══════════════════════════════════════════════════════════════
# 3. K109-2 — tahrirda ishlab chiqarishga bog'langan detal
# ══════════════════════════════════════════════════════════════
section("3. K109-2 — buyurtma tahriri")
O5, I5 = buyurtma("B", 2)
_d5 = detallar(O5)
F5, P5 = po("B", 3, O5, I5[1])
_st, _dt = tahrir("B", O5, [(_d5[0][1], 10)])
_sh = " | ".join(_dt.get("shortages") or [])
check("3.1 band TM li (yakunlangan) detal olib tashlandi — 400 (asl PG: 500, SQLite: jim o'chardi)", _st == 400,
      (_st, _dt))
check("3.2 sabab: detal nomi va '3 m² tayyor mahsulot band'", _d5[1][1] in _sh and "3 m² tayyor mahsulot band" in _sh,
      _sh)
check("3.3 hech narsa o'zgarmadi: 2 detal, TM band 3, PO manbasi joyida",
      detallar(O5) == _d5 and fp(F5) == (2, 3.0, I5[1]) and po_holat(P5) == ("completed", O5, I5[1]),
      (detallar(O5), fp(F5), po_holat(P5)))

O6, I6 = buyurtma("B", 2)
_d6 = detallar(O6)
P6 = po_draft("B", 2, O6, I6[1])
_st, _dt = tahrir("B", O6, [(_d6[0][1], 10)])
_sh = " | ".join(_dt.get("shortages") or [])
check("3.4 qoralama ishlab chiqarish buyurtmali detal olib tashlandi — 400, sababda '#N (qoralama)'",
      _st == 400 and f"#{P6} (qoralama)" in _sh, (_st, _dt))
check("3.5 o'zgarmadi: 2 detal, PO manbasi joyida", detallar(O6) == _d6 and po_holat(P6) == ("draft", O6, I6[1]),
      (detallar(O6), po_holat(P6)))
_rs = req(C["B"], "post", f"/api/production/orders/{P6}/start")
_st, _dt = tahrir("B", O6, [(_d6[0][1], 10)])
check("3.6 jarayondagi buyurtma — 400, sababda '(jarayonda)'",
      _rs.status_code == 200 and _st == 400 and f"#{P6} (jarayonda)" in " | ".join(_dt.get("shortages") or []),
      (_rs.status_code, _st, _dt))

O7, I7 = buyurtma("B", 1)
_d7 = detallar(O7)
F7, P7 = po("B", 3, O7, I7[0])
_st, _dt = tahrir("B", O7, [(_d7[0][1] + " (tuzatildi)", 10)])
check("3.7 band TM li detal NOMI o'zgartirildi — 400 (band jimgina bo'shamaydi)", _st == 400, (_st, _dt))
check("3.8 o'zgarmadi: eski nom, TM band 3", detallar(O7) == _d7 and fp(F7) == (2, 3.0, I7[0]),
      (detallar(O7), fp(F7)))
_st, _dt = tahrir("B", O7, [(_d7[0][1], 12)])
check("3.9 nomi o'sha, miqdor oshdi — 200 (nazorat: oddiy tahrir buzilmagan), TM band joyida",
      _st == 200 and fp(F7) == (2, 3.0, I7[0]), (_st, _dt, fp(F7)))

O8, I8 = buyurtma("B", 2)
_d8 = detallar(O8)
F8, P8 = po("B", 3, O8, I8[1])
_rr = req(C["B"], "post", f"/api/finished/{F8}/release-reservation")
_st, _dt = tahrir("B", O8, [(_d8[0][1], 10)])
check("3.10 TARIXIY bog'lam (yakunlangan PO, band bo'shatilgan) — olib tashlash 200",
      _rr.status_code == 200 and _st == 200, (_rr.status_code, _st, _dt))
check("3.11 detal o'chdi, PO holati 'completed', manba detali uzildi, TM bog'lamsiz",
      [x[0] for x in (detallar(O8) or [])] == [I8[0]] and po_holat(P8) == ("completed", O8, None)
      and fp(F8) == (2, 0.0, None), (detallar(O8), po_holat(P8), fp(F8)))

O9, I9 = buyurtma("B", 2)
_d9 = detallar(O9)
P9 = po_draft("B", 2, O9, I9[1])
_rc = req(C["B"], "post", f"/api/production/orders/{P9}/cancel")
_st, _dt = tahrir("B", O9, [(_d9[0][1], 10)])
check("3.12 bekor qilingan PO li detal — 200, PO manba detali uzildi",
      _rc.status_code == 200 and _st == 200 and (po_holat(P9) or ("",))[0] == "cancelled"
      and (po_holat(P9) or (None, None, 0))[2] is None, (_rc.status_code, _st, _dt, po_holat(P9)))

O10, I10 = buyurtma("B", 2)
_d10 = detallar(O10)
begona_band(FA[5], I10[1])
_st, _dt = tahrir("B", O10, [(_d10[0][1], 10)])
check("3.13 BEGONA (A) TM band detal — B tahririni to'smaydi: 200; A TM band 5 qoldi, bog'lam uzildi",
      _st == 200 and fp(FA[5]) == (1, 5.0, None), (_st, _dt, fp(FA[5])))

O16, I16 = buyurtma("B", 2)
_d16 = detallar(O16)
_pa16 = po_draft("A", 1)
sql("UPDATE production_orders SET source_type='customer_order', source_order_id=:o, source_order_item_id=:i WHERE id=:p",
    o=O16, i=I16[1], p=_pa16)
_st, _dt = tahrir("B", O16, [(_d16[0][1], 10)])
check("3.16 BEGONA (A) qoralama ishlab chiqarish buyurtmasi B detaliga — B tahririni to'smaydi: 200; A buyurtmasi saqlangan, "
      "manba detali uzildi",
      _st == 200 and bir("SELECT status, source_order_item_id FROM production_orders WHERE id=:p", p=_pa16) == ("draft", None),
      (_st, _dt, bir("SELECT status, source_order_item_id FROM production_orders WHERE id=:p", p=_pa16)))

O11, I11 = buyurtma("B", 2)
_d11 = detallar(O11)
_st, _dt = tahrir("B", O11, [(_d11[0][1], 10)])
check("3.14 bog'lamsiz MRP detal olib tashlandi — 200 (nazorat)",
      _st == 200 and [x[0] for x in (detallar(O11) or [])] == [I11[0]], (_st, _dt, detallar(O11)))
_f = getattr(crud, "_mrp_faol_boglamlar", None)
check("3.15 yagona yordamchi `crud._mrp_faol_boglamlar` mavjud", callable(_f))

# ══════════════════════════════════════════════════════════════
# 4. E-1 — B korxonasini tozalash (platforma amali), begona ishoralar bilan
# ══════════════════════════════════════════════════════════════
section("4. B korxonasini tozalash — begona ishoralar")
O12, I12 = buyurtma("B", 1)
FB12, _p12 = po("B", 2)
begona_band(FA[6], I12[0])
_pa = po_draft("A", 1)
sql("UPDATE production_orders SET source_type='customer_order', source_order_id=:o, source_order_item_id=:i, "
    "finished_product_id=:f WHERE id=:p", o=O12, i=I12[0], f=FB12, p=_pa)
OA2, IA2 = buyurtma("A", 1)
sql("UPDATE order_items SET finished_product_id=:f WHERE id=:i", f=FB12, i=IA2[0])
_a_oldin = bir("SELECT COUNT(*) FROM orders WHERE company_id=1")
_s = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        crud.factory_reset_all_data(_s, company_id=2)
    _res = "OK"
except Exception as e:                     # noqa: BLE001
    _s.rollback()
    _res = f"XATO {type(e).__name__}: {str(e)[:200]}"
finally:
    _s.close()
check("4.1 tozalash muvaffaqiyatli (asl PG: 500 — FK)", _res == "OK", _res)
check("4.2 B buyurtmalari 0, A buyurtmalari o'zgarmadi (tozalashdan oldingi son)",
      bir("SELECT COUNT(*) FROM orders WHERE company_id=2") == (0,) and isinstance(_a_oldin, tuple) and _a_oldin[0] >= 2
      and bir("SELECT COUNT(*) FROM orders WHERE company_id=1") == _a_oldin,
      (bir("SELECT COUNT(*) FROM orders WHERE company_id=2"), _a_oldin,
       bir("SELECT COUNT(*) FROM orders WHERE company_id=1")))
check("4.3 A TM: band 5 qoldi, faqat bog'lam uzildi", fp(FA[6]) == (1, 5.0, None), fp(FA[6]))
check("4.4 A ishlab chiqarish buyurtmasi saqlangan, manba va TM ishorasi uzildi, holati o'zgarmadi",
      bir("SELECT status, source_order_id, source_order_item_id, finished_product_id FROM production_orders "
          "WHERE id=:p", p=_pa) == ("draft", None, None, None),
      bir("SELECT status, source_order_id, source_order_item_id, finished_product_id FROM production_orders "
          "WHERE id=:p", p=_pa))
check("4.5 A detali saqlangan, B TM ishorasi uzildi",
      bir("SELECT finished_product_id, name FROM order_items WHERE id=:i", i=IA2[0]) == (None, detallar(OA2)[0][1]),
      bir("SELECT finished_product_id, name FROM order_items WHERE id=:i", i=IA2[0]))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
