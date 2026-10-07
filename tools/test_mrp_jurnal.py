#!/usr/bin/env python3
"""
test_mrp_jurnal.py — kech110 darvozasi: 5.2d «Keyingi chat tartibi» 2 (c) — MRP amallari Faoliyat jurnalida.

NIMA UCHUN KERAK (2026-09-18 MRP auditi, 3-faza — `grep` bilan TASDIQLANGAN; asl kod `ba6935c` da shu test bilan
O'LCHANDI): mahsulot turi va retsept (BOM) yaratish / o'zgartirish / nofaol qilish, ishlab chiqarish buyurtmasini
yaratish, boshlash, yakunlash (xomashyo yechiladi, tannarx yoziladi), bekor qilish va «manfiy qoldiq bilan ishlab
chiqarish» sozlamasi — `/logs` «Audit jurnali» (`ActivityLog`) ga UMUMAN yozilmasdi. Buyurtma, loyiha, hodim,
tayyor mahsulot amallari yoziladi — MRP ularning yagona ko'r nuqtasi edi (kim, qachon, nima qilgani noma'lum).

YECHIM (texnik — Claude): `crud.log_activity(commit=False)` — yozuv amal bilan BITTA tranzaksiyada (amal rad
etilsa / yiqilsa — yozuv yo'q); `production_service._po_jurnal` (yaratildi / jarayonga olindi / ishlab chiqarildi /
bekor qilindi), `production_routes` (mahsulot turi, retsept — eski → yangi, nofaol qilish, sozlama). Korxona —
amal korxonasi (B ning yozuvi A jurnalida ko'rinmaydi). `/logs` da «⛔ … bekor qilindi».

BO'LIMLAR: J — har amal jurnali (matn, kim, korxona); T — atomiklik (rad etilgan boshlash / yakunlash — yozuv yo'q);
K — korxona chegarasi va `/logs` sahifasi; S — statik.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
    python3 tools/test_mrp_jurnal.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_jurnal.py
Asl kodga qarshi QULAMAYDI (HTTP istisno → 599, yangi nomlar `getattr`). Chiqish kodi 0 — hammasi o'tdi.
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_jurnal_test"
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
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'mrp_jurnal_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import production_service                      # noqa: E402
    import production_routes                       # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import UserRole, Project, Inventory, ActivityLog   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond)
    except Exception:                      # noqa: BLE001
        cond = False
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


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Fikstura: A (1) va B (2) korxonalari
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="MJ B korxona"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "MJ_A", "Parol123!", UserRole.ADMIN, "Aziz Operator", company_id=1)
    auth.create_user(_db, "MJ_B", "Parol123!", UserRole.ADMIN, "Bobur Operator", company_id=2)
ID = {}
for _cid, _h in ((1, "A"), (2, "B")):
    _p = Project(company_id=_cid, client_name=f"MJ {_h} mijoz", project_name=f"MJ {_h} loyiha", total_budget=0,
                 total_paid=0)
    _t = Inventory(company_id=_cid, item_name=f"MJ {_h} Tosh", unit="kg", stock_quantity=1_000,
                   price_per_unit=1_000, category="Kimyo")
    _k = Inventory(company_id=_cid, item_name=f"MJ {_h} Kley", unit="kg", stock_quantity=1_000,
                   price_per_unit=5_000, category="Kimyo")
    _db.add_all([_p, _t, _k])
    _db.commit()
    ID[f"PRJ_{_h}"], ID[f"TOSH_{_h}"], ID[f"KLEY_{_h}"] = _p.id, _t.id, _k.id
_db.close()

C = {}
for _h in ("A", "B"):
    _c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    _lr = req(_c, "post", "/login", data={"username": f"MJ_{_h}", "password": "Parol123!"}, follow_redirects=False)
    C[_h] = _c
    ID[f"login_{_h}"] = _lr.status_code

XATO5 = []


def so(h, metod, url, **k):
    r = req(C[h], metod, url, **k)
    if r.status_code >= 500:
        XATO5.append((h, metod, url, r.status_code, getattr(r, "text", "")[:200]))
    return r


def jurnal(cid=None, entity=None, eid=None):
    s = SessionLocal()
    try:
        q = s.query(ActivityLog)
        if cid is not None:
            q = q.filter(ActivityLog.company_id == cid)
        if entity is not None:
            q = q.filter(ActivityLog.entity_type == entity)
        if eid is not None:
            q = q.filter(ActivityLog.entity_id == eid)
        return [{"action": a.action, "entity": a.entity_type, "id": a.entity_id, "label": a.entity_label,
                 "kim": a.performed_by, "old": a.old_value, "new": a.new_value, "cid": a.company_id}
                for a in q.order_by(ActivityLog.id).all()]
    finally:
        s.close()


def oxirgi(cid, entity, eid):
    j = jurnal(cid, entity, eid)
    return j[-1] if j else {}


check("F0 A va B tizimga kirdi", ID["login_A"] == 302 and ID["login_B"] == 302, (ID["login_A"], ID["login_B"]))

# ══════════════════════════════════════════════════════════════
# J. Har amal jurnali (A korxona)
# ══════════════════════════════════════════════════════════════
section("J. Mahsulot turi va retsept")
r = so("A", "post", "/api/production/product-types", json={"name": "MJ Travertin", "unit": "m²",
                                                             "input_template": "quantity_only", "pricing_formula": "unit_based"})
PT = (js(r) or {}).get("id")
j = oxirgi(1, "product_type", PT)
check("J1 mahsulot turi yaratildi — «created», «Mahsulot turi «MJ Travertin»», birlik m², kim — to'liq ism, A korxona",
      r.status_code == 200 and j.get("action") == "created" and j.get("label") == "Mahsulot turi «MJ Travertin»"
      and "m²" in (j.get("new") or "") and j.get("kim") == "Aziz Operator" and j.get("cid") == 1, (r.status_code, j))

r = so("A", "post", "/api/production/boms", json={"product_type_id": PT, "variant_name": "Oddiy", "batch_quantity": 10,
                                                   "items": [{"inventory_id": ID["TOSH_A"], "quantity": 3}]})
BOM = (js(r) or {}).get("id")
j = oxirgi(1, "bom", BOM)
check("J2 retsept yaratildi — «created», «Retsept «Oddiy» — MJ Travertin», partiya 10 m², 1 ta material",
      r.status_code == 200 and j.get("action") == "created" and j.get("label") == "Retsept «Oddiy» — MJ Travertin"
      and "partiya 10 m²" in (j.get("new") or "") and "1 ta material" in (j.get("new") or ""), (r.status_code, j))

r = so("A", "put", f"/api/production/boms/{BOM}", json={
    "product_type_id": PT, "variant_name": "Kuchli", "batch_quantity": 20,
    "items": [{"inventory_id": ID["TOSH_A"], "quantity": 4}, {"inventory_id": ID["KLEY_A"], "quantity": 1}]})
j = oxirgi(1, "bom", BOM)
check("J3 retsept o'zgartirildi — «updated», eski «Oddiy» (10, 1 ta) → yangi «Kuchli» (20, 2 ta)",
      r.status_code == 200 and j.get("action") == "updated" and "«Oddiy»" in (j.get("old") or "")
      and "partiya 10" in (j.get("old") or "") and "1 ta material" in (j.get("old") or "")
      and "«Kuchli»" in (j.get("new") or "") and "partiya 20" in (j.get("new") or "") and "2 ta material" in (j.get("new") or "")
      and j.get("label") == "Retsept «Kuchli» — MJ Travertin", (r.status_code, j))

section("J'. Ishlab chiqarish buyurtmasi: yaratish → boshlash → yakunlash; bekor qilish")
r = so("A", "post", "/api/production/orders", json={"product_type_id": PT, "bom_id": BOM, "quantity": 20,
                                                     "source_type": "warehouse_stock"})
PO1 = ((js(r) or {}).get("production_order") or {}).get("id")
j = oxirgi(1, "production_order", PO1)
check("J4 yaratildi — «created», «Ishlab chiqarish #N — MJ Travertin», 20 m², retsept «Kuchli», omborga",
      r.status_code == 200 and j.get("action") == "created" and j.get("label") == f"Ishlab chiqarish #{PO1} — MJ Travertin"
      and all(x in (j.get("new") or "") for x in ("20 m²", "«Kuchli»", "omborga")), (r.status_code, j))
r = so("A", "post", f"/api/production/orders/{PO1}/start")
j = oxirgi(1, "production_order", PO1)
check("J5 boshlandi — «activated» (jarayonga olindi), 2 ta xomashyo qatori, tayyor mahsulot «ishlab chiqarilmoqda»",
      r.status_code == 200 and j.get("action") == "activated" and "2 ta xomashyo qatori" in (j.get("new") or "")
      and "ishlab chiqarilmoqda" in (j.get("new") or ""), (r.status_code, j))
r = so("A", "post", f"/api/production/orders/{PO1}/complete")
j = oxirgi(1, "production_order", PO1)
# 20 m² / partiya 20: tosh 4 kg × 1 000 + kley 1 kg × 5 000 = 9 000 so'm
check("J6 yakunlandi — «produced» (ishlab chiqarildi), tannarx 9 000 so'm (xomashyo 9 000, qo'shimcha 0)",
      r.status_code == 200 and j.get("action") == "produced" and "tannarx 9 000 so'm" in (j.get("new") or "")
      and "xomashyo 9 000" in (j.get("new") or ""), (r.status_code, j))
check("J7 bitta ishlab chiqarish — 3 yozuv (created, activated, produced), hammasi A korxona, kim — Aziz Operator",
      [x["action"] for x in jurnal(1, "production_order", PO1)] == ["created", "activated", "produced"]
      and all(x["cid"] == 1 and x["kim"] == "Aziz Operator" for x in jurnal(1, "production_order", PO1)),
      jurnal(1, "production_order", PO1))

r = so("A", "post", "/api/production/orders", json={"product_type_id": PT, "bom_id": BOM, "quantity": 20,
                                                     "source_type": "warehouse_stock"})
PO2 = ((js(r) or {}).get("production_order") or {}).get("id")
so("A", "post", f"/api/production/orders/{PO2}/start")
r = so("A", "post", f"/api/production/orders/{PO2}/cancel")
j = oxirgi(1, "production_order", PO2)
check("J8 jarayondagi bekor qilindi — «cancelled», «Holat: jarayonda → bekor qilindi; … tayyor mahsulot yozuvi o'chirildi»",
      r.status_code == 200 and j.get("action") == "cancelled" and "jarayonda → bekor qilindi" in (j.get("new") or "")
      and "tayyor mahsulot yozuvi o'chirildi" in (j.get("new") or ""), (r.status_code, j))
r = so("A", "post", "/api/production/orders", json={"product_type_id": PT, "bom_id": BOM, "quantity": 5,
                                                     "source_type": "warehouse_stock"})
PO3 = ((js(r) or {}).get("production_order") or {}).get("id")
r = so("A", "post", f"/api/production/orders/{PO3}/cancel")
j = oxirgi(1, "production_order", PO3)
check("J9 qoralama bekor qilindi — «Holat: qoralama → bekor qilindi» (tayyor mahsulot eslatmasisiz)",
      r.status_code == 200 and j.get("action") == "cancelled" and j.get("new") == "Holat: qoralama → bekor qilindi", (r.status_code, j))

section("J''. Mijoz buyurtmasi asosida; nofaol qilish; sozlama")
r = so("A", "post", "/api/orders", json={"project_id": ID["PRJ_A"], "order_type": "product", "loy_kg": 0, "items": [
    {"name": "MJ detal", "category": "mrp_product", "quantity": 10, "unit_price": 100_000, "is_coated": False,
     "penoplast_id": None, "product_type_id": PT}]}, params={"confirm_shortage": "true"})
_o = js(r) or {}
_oid = _o.get("id")
_s = SessionLocal()
try:
    from models import Order, OrderItem   # noqa: E402
    _on = (_s.get(Order, _oid).order_number if _oid else None)
    _iid = (_s.query(OrderItem.id).filter(OrderItem.order_id == _oid).first() or [None])[0]
finally:
    _s.close()
r = so("A", "post", "/api/production/orders", json={"product_type_id": PT, "bom_id": BOM, "quantity": 10,
                                                     "source_type": "customer_order", "source_order_item_id": _iid})
PO4 = ((js(r) or {}).get("production_order") or {}).get("id")
j = oxirgi(1, "production_order", PO4)
check("J10 mijoz buyurtmasi asosida — yozuvda buyurtma raqami", r.status_code == 200 and bool(_on)
      and f"mijoz buyurtmasi {_on}" in (j.get("new") or ""), (r.status_code, _on, j))
r = so("A", "put", "/api/production/company-settings", params={"allow_negative_stock": "true"})
j = oxirgi(1, "company_settings", 1)
check("J11 «manfiy qoldiq bilan ishlab chiqarish» yoqildi — «updated», yo'q → ha",
      r.status_code == 200 and j.get("action") == "updated" and j.get("old") == "yo'q" and j.get("new") == "ha", (r.status_code, j))
_n0 = len(jurnal(1, "company_settings"))
r = so("A", "put", "/api/production/company-settings", params={"allow_negative_stock": "true"})
check("J12 xuddi shu qiymat qayta yuborildi — yangi yozuv YO'Q", r.status_code == 200 and len(jurnal(1, "company_settings")) == _n0,
      jurnal(1, "company_settings"))
so("A", "put", "/api/production/company-settings", params={"allow_negative_stock": "false"})
r = so("A", "delete", f"/api/production/boms/{BOM}")
j = oxirgi(1, "bom", BOM)
check("J13 retsept nofaol qilindi — «deleted», «nofaol qilindi …»", r.status_code == 200 and j.get("action") == "deleted"
      and "nofaol qilindi" in (j.get("new") or ""), (r.status_code, j))
# kech120 (zip 133 — G5-06, MOSLANDI): ochiq (qoralama) ishlab chiqarishi bor tur nofaol qilinmaydi — 409, jurnalga YOZILMAYDI;
# qoralama (PO4) bekor qilingach — nofaol qilinadi
_n14 = len(jurnal(1, "product_type"))
r = so("A", "delete", f"/api/production/product-types/{PT}")
check("J14a ochiq ishlab chiqarishli tur — 409 (sababi bilan), jurnalda yangi yozuv YO'Q", r.status_code == 409
      and "ochiq" in str(js(r)) and len(jurnal(1, "product_type")) == _n14, (r.status_code, js(r)))
so("A", "post", f"/api/production/orders/{PO4}/cancel")
r = so("A", "delete", f"/api/production/product-types/{PT}")
j = oxirgi(1, "product_type", PT)
check("J14 mahsulot turi nofaol qilindi — «deleted»", r.status_code == 200 and j.get("action") == "deleted"
      and "nofaol qilindi" in (j.get("new") or ""), (r.status_code, j))

# ══════════════════════════════════════════════════════════════
# T. Atomiklik — rad etilgan amal jurnalga yozilmaydi
# ══════════════════════════════════════════════════════════════
section("T. Atomiklik — rad etilgan / yiqilgan amal yozilmaydi")
r = so("A", "post", "/api/production/product-types", json={"name": "MJ Blok", "unit": "dona",
                                                             "input_template": "quantity_only", "pricing_formula": "unit_based"})
PT2 = (js(r) or {}).get("id")
r = so("A", "post", "/api/production/boms", json={"product_type_id": PT2, "variant_name": "Og'ir", "batch_quantity": 1,
                                                   "items": [{"inventory_id": ID["TOSH_A"], "quantity": 100}]})
BOM2 = (js(r) or {}).get("id")
r = so("A", "post", "/api/production/orders", json={"product_type_id": PT2, "bom_id": BOM2, "quantity": 50,
                                                     "source_type": "warehouse_stock"})
PO5 = ((js(r) or {}).get("production_order") or {}).get("id")
r = so("A", "post", f"/api/production/orders/{PO5}/start")
check("T1 xomashyo yetmaydi (5 000 kg kerak) — boshlash 409, jurnalda faqat «created» (activated YO'Q)",
      r.status_code == 409 and [x["action"] for x in jurnal(1, "production_order", PO5)] == ["created"],
      (r.status_code, jurnal(1, "production_order", PO5)))
r = so("A", "post", "/api/production/orders", json={"product_type_id": PT2, "bom_id": BOM2, "quantity": 5,
                                                     "source_type": "warehouse_stock"})
PO6 = ((js(r) or {}).get("production_order") or {}).get("id")
r1 = so("A", "post", f"/api/production/orders/{PO6}/start")
_s = SessionLocal()
try:
    _inv = _s.get(Inventory, ID["TOSH_A"])
    _eski_qoldiq = float(_inv.stock_quantity)
    _inv.stock_quantity = 10
    _s.commit()
finally:
    _s.close()
r2 = so("A", "post", f"/api/production/orders/{PO6}/complete")
check("T2 boshlangach xomashyo kamaydi — yakunlash 409, jurnalda «produced» YO'Q (created, activated)",
      r1.status_code == 200 and r2.status_code == 409
      and [x["action"] for x in jurnal(1, "production_order", PO6)] == ["created", "activated"],
      (r1.status_code, r2.status_code, jurnal(1, "production_order", PO6)))
_s = SessionLocal()
try:
    _s.get(Inventory, ID["TOSH_A"]).stock_quantity = _eski_qoldiq
    _s.commit()
finally:
    _s.close()
r = so("A", "post", "/api/production/boms", json={"product_type_id": PT2, "variant_name": "Og'ir", "batch_quantity": 1,
                                                   "items": [{"inventory_id": ID["TOSH_A"], "quantity": 1}]})
check("T3 takror nomli retsept — 400, yangi retsept yozuvi YO'Q", r.status_code == 400
      and len([x for x in jurnal(1, "bom") if x["label"] == "Retsept «Og'ir» — MJ Blok"]) == 1, (r.status_code, jurnal(1, "bom")))
r = so("A", "post", f"/api/production/orders/{PO1}/cancel")
check("T4 yakunlanganni bekor qilish — 409, «cancelled» yozuvi YO'Q", r.status_code == 409
      and "cancelled" not in [x["action"] for x in jurnal(1, "production_order", PO1)], (r.status_code, jurnal(1, "production_order", PO1)))

# ══════════════════════════════════════════════════════════════
# K. Korxona chegarasi va /logs sahifasi
# ══════════════════════════════════════════════════════════════
section("K. Korxona chegarasi va `/logs` sahifasi")
r = so("B", "post", "/api/production/product-types", json={"name": "MJ B Gips", "unit": "kg",
                                                             "input_template": "quantity_only", "pricing_formula": "unit_based"})
PTB = (js(r) or {}).get("id")
r = so("B", "post", "/api/production/boms", json={"product_type_id": PTB, "variant_name": "B retsept", "batch_quantity": 1,
                                                   "items": [{"inventory_id": ID["TOSH_B"], "quantity": 1}]})
BOMB = (js(r) or {}).get("id")
r = so("B", "post", "/api/production/orders", json={"product_type_id": PTB, "bom_id": BOMB, "quantity": 2,
                                                     "source_type": "warehouse_stock"})
POB = ((js(r) or {}).get("production_order") or {}).get("id")
so("B", "post", f"/api/production/orders/{POB}/start")
so("B", "post", f"/api/production/orders/{POB}/complete")
_jb = jurnal(2)
check("K1 B amallari — B korxona jurnalida (5 yozuv), kim — Bobur Operator",
      [x["action"] for x in _jb] == ["created", "created", "created", "activated", "produced"]
      and all(x["kim"] == "Bobur Operator" for x in _jb), _jb)
_begona = [x for x in jurnal(1) if "MJ B Gips" in (x["label"] or "") or "B retsept" in (x["label"] or "")
           or x["kim"] == "Bobur Operator"]
check("K2 A jurnalida B yozuvi YO'Q", not _begona and len(jurnal(1)) > 0, _begona)
_ha = req(C["A"], "get", "/logs")
_hb = req(C["B"], "get", "/logs")
_ta, _tb = getattr(_ha, "text", ""), getattr(_hb, "text", "")
check("K3 A `/logs`: «Ishlab chiqarish #N — MJ Travertin» … «ishlab chiqarildi», «bekor qilindi» (⛔), retsept yozuvlari",
      _ha.status_code == 200 and f"Ishlab chiqarish #{PO1} — MJ Travertin" in _ta and "ishlab chiqarildi" in _ta
      and "bekor qilindi" in _ta and "⛔" in _ta and "Retsept «Kuchli» — MJ Travertin" in _ta, _ha.status_code)
check("K4 B `/logs`: o'z yozuvi bor, A ning yozuvi YO'Q", _hb.status_code == 200 and "MJ B Gips" in _tb
      and "MJ Travertin" not in _tb, _hb.status_code)

section("X. 5xx yo'q")
check("X1 hech bir so'rov 5xx bermadi", not XATO5, XATO5[:5])

# ══════════════════════════════════════════════════════════════
# S. Statik
# ══════════════════════════════════════════════════════════════
section("S. Statik")
_la = manba(crud, "log_activity")
check("S1 `crud.log_activity(commit=…)` — commit=False da faqat `db.add` (chaqiruvchi tranzaksiyasi)",
      "commit: bool = True" in _la and tartibda(_la, "db.add(entry)", "if commit:", "db.commit()"))
for _i, _f in enumerate(("create_production_order", "start_production_order", "complete_production_order",
                         "cancel_production_order"), 2):
    _m = manba(production_service, _f)
    check(f"S{_i} `{_f}` — `_po_jurnal(...)` yakuniy `db.commit()` dan OLDIN",
          tartibda(_m, "_po_jurnal(db, po,", "db.commit()"), _f)
_pj = manba(production_service, "_po_jurnal")
# kod QATORI tekshiriladi (izohda ham "commit=False" bor — statik tuzoq, kmut110 J7)
check("S6 `_po_jurnal` — `commit=False`, korxona — buyurtmaniki",
      "new_value=new_value, company_id=po.company_id, commit=False)" in _pj)
for _i, _f in enumerate(("create_product_type", "deactivate_product_type", "create_bom", "update_bom", "deactivate_bom",
                         "update_company_settings"), 7):
    _m = manba(production_routes, _f)
    check(f"S{_i} marshrut `{_f}` — `crud.log_activity(..., commit=False)` va keyin `db.commit()`",
          tartibda(_m, "crud.log_activity(", "commit=False", "db.commit()"), _f)
try:
    _lg = open(os.path.join(ROOT, "templates", "logs.html"), encoding="utf-8").read()
except Exception:                          # noqa: BLE001
    _lg = ""
# kech120 (zip 129 — G6-23): amal nomlari shablondagi `if` zanjiridan bitta ro'yxatga (`crud.AUDIT_AMALLARI`) ko'chdi —
# shablon `amal_nomi(a.action)` ni chizadi. Tekshiruv mazmuni o'sha: «cancelled» → ⛔ va «bekor qilindi».
check("S13 logs.html — «cancelled» → ⛔ va «bekor qilindi»",
      ("a.action == 'cancelled' %}⛔" in _lg and "a.action == 'cancelled' %}bekor qilindi" in _lg)
      or ("{% set _am = amal_nomi(a.action) %}" in _lg and "{{ _am[0] }}" in _lg and "{{ _am[1] }}" in _lg
          and getattr(crud, "AUDIT_AMALLARI", {}).get("cancelled", ("", ""))[:2] == ("⛔", "bekor qilindi")))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
