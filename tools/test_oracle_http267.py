#!/usr/bin/env python3
"""
test_oracle_http267.py — kech203 (zip 267): review265 INFO-7 — «mavjudlik oracle'i» 19 + 4 yozish yo'lida DOIMIY darvoza.

NIMA UCHUN KERAK:
  zip 265 (REJA 14-band, Fable F6) da begona korxona id si ↔ umuman yo'q id — bir xil javob qilindi. `test_oracle265` HTTP qismida faqat
  buyurtmaning `master_id` / `recipe_id` sinaladi. Mustaqil tekshiruv review265 ning `probes/probe_oracle_http.py` (19 yo'l) bir martalik
  o'lchov edi — keyingi marshrut o'zgarishlarida oracle jimgina qaytishi mumkin. Shu test o'sha 19 yo'lni (+ 4 tahrir / to'lov yo'li)
  doimiy qiladi.
QOIDA (har yo'l uchun): B korxonasi admini so'rovida A korxonasining id si (BEGONA) va hech qayerda yo'q id (YO'Q) yuboriladi:
  1) javob holati AYNAN bir xil, 500 emas;
  2) javob matni AYNAN bir xil (mijozning O'Z yuborgan id raqami «<ID>» bilan almashtirilgandan keyin — o'z raqamini qaytarish oracle emas);
     2xx bo'lsa (server maydonni qabul qilmaydi) — faqat holat;
  3) javobda ichki sabab yo'q («boshqa korxona…» kabi eski 409 matni, «IntegrityError», «ForeignKey»);
  4) xatolar jurnali (ErrorLog) to'lmaydi;
  5) rad etilgan so'rov B korxonasida hech narsa yozmaydi (yarim yozuv yo'q), A korxonasining ma'lumoti HECH QACHON o'zgarmaydi.
BO'LIMLAR: A — 23 yo'l (begona ↔ yo'q); B — A korxonasi ma'lumoti butun sinov davomida o'zgarmagan; C — o'z (B) id lari bilan oddiy
           so'rovlar ishlaydi (test yolg'on yashil bo'lmasligi uchun — rad etish id ga bog'liq, yo'lning o'zi yopiq emas).
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (26fc68d — zip 264, zip 265 dan oldin) qarshi YIQILADI (buyurtma usta / retsept / penoplast — 409 ↔ 200 / 500), QULAMAYDI.
ISHLATISH: python3 tools/test_oracle_http267.py
"""
import os
import sys
import json
import re
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "oracle_http267_test"
_T = tempfile.mkdtemp(prefix="oracle_http267_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'oracle_http267_test.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "ADMIN_PASSWORD", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas                                 # noqa: E402
import models                                      # noqa: E402
import tenant_context                              # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, FinishedProduct, Inventory, Supplier, Master, Employee, ErrorLog   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import text as _sql, inspect as _insp   # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


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


def matn(r):
    """Javob tanasi — JSON bo'lsa tartiblangan matn, bo'lmasa xom matn."""
    try:
        return json.dumps(r.json(), ensure_ascii=False, sort_keys=True)
    except Exception:                      # noqa: BLE001
        return r.text


PAROL = "Kuchli-Sinov-Parol-267x"
YOQ = 987654                               # hech qaysi korxonada yo'q id
ICHKI_SABAB = ("boshqa korxona", "Boshqa korxona", "IntegrityError", "ForeignKey", "foreign key", "violates", "Traceback",
               "TenantMismatchError")

with TestClient(main.app, base_url="https://testserver") as _c0:
    _c0.get("/login")

ID = {}
s = SessionLocal()
with tenant_context.system_context(s):
    if not s.query(Company).filter(Company.id == 2).first():
        s.add(Company(id=2, name="Oracle267 B korxona", code="OR267-B"))
        s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "or267_a", PAROL, UserRole.ADMIN, "A Admin", company_id=1)
    auth.create_user(s, "or267_b", PAROL, UserRole.ADMIN, "B Admin", company_id=2)
    with tenant_context.system_context(s):
        for cid, k in ((1, "A"), (2, "B")):
            ID["M" + k] = crud.create_master(s, schemas.MasterCreate(name=f"OR267_{k}_Usta", phone=f"+99890{cid}000267"),
                                             company_id=cid).id
            ID["I" + k] = crud.add_item(s, schemas.InventoryCreate(item_name=f"OR267_{k}_Mat", unit="kg", stock_quantity=50,
                                                                   price_per_unit=1000), company_id=cid).id
            ID["R" + k] = crud.create_recipe(s, schemas.RecipeCreate(name=f"OR267_{k}_Ret", batch_size_kg=10, ingredients=[
                schemas.RecipeIngredientCreate(inventory_id=ID["I" + k], quantity_kg=1)]), company_id=cid).id
            ID["Y" + k] = crud.standart_yonalish(s, cid).id
            s.commit()
            ID["E" + k] = crud.create_employee(s, schemas.EmployeeCreate(name=f"OR267 {k} Hodim", pay_type="fixed"),
                                               company_id=cid).id
            ID["S" + k] = crud.create_supplier(s, schemas.SupplierCreate(name=f"OR267 {k} Taminot"), company_id=cid).id
            fp = FinishedProduct(company_id=cid, name=f"OR267 {k} TM", category="dona", unit="dona", quantity=10,
                                 cost_price=100, production_status=models.ProductionStatus.READY)
            s.add(fp)
            s.commit()
            ID["F" + k] = fp.id
            ID["P" + k] = crud.create_project(s, schemas.ProjectCreate(project_name=f"OR267 {k} Loyiha", client_name="OR267",
                                                                       client_phone=f"+99890{cid}111267"), company_id=cid).id
s.close()
assert len(set(ID.values())) > 1, ID


def kirgan(login, ip):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False, client=(ip, 50000))
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), f"{login} kirmadi: {r.status_code} {r.text[-200:]}"
    return c


CB = kirgan("or267_b", "203.0.113.67")

# B korxonasining o'z buyurtmasi — tahrir (PUT) yo'llari uchun
_r0 = CB.post("/api/orders", json={"project_id": ID["PB"], "order_type": "product", "notes": "OR267 asos",
                                   "items": [{"name": "OR267 asos detal", "category": "panel", "quantity": 1, "unit_price": 1000}]})
assert _r0.status_code == 200, (_r0.status_code, _r0.text[:300])
ID["OB"] = _r0.json()["id"]


def xato_soni():
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            return d.query(ErrorLog).count()
    finally:
        d.close()


_KJ = sorted(t for t in _insp(engine).get_table_names()
             if any(c["name"] == "company_id" for c in _insp(engine).get_columns(t)) and t != "error_logs")


def korxona_holati(cid):
    """`company_id` ustunli HAR jadval bo'yicha shu korxonaning qatorlari soni (xatolar jurnalidan tashqari)."""
    with engine.connect() as c:
        return {t: c.execute(_sql(f'SELECT COUNT(*) FROM "{t}" WHERE company_id = :c'), {"c": cid}).scalar() for t in _KJ}


def a_qiymatlari():
    """A korxonasi obyektlarining o'zgarishi mumkin bo'lgan maydonlari."""
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            fp = d.query(FinishedProduct).filter(FinishedProduct.id == ID["FA"]).one()
            inv = d.query(Inventory).filter(Inventory.id == ID["IA"]).one()
            sup = d.query(Supplier).filter(Supplier.id == ID["SA"]).one()
            us = d.query(Master).filter(Master.id == ID["MA"]).one()
            hd = d.query(Employee).filter(Employee.id == ID["EA"]).one()
            return {"fp_soni": float(fp.quantity or 0), "fp_holat": str(fp.production_status),
                    "inv_qoldiq": float(inv.stock_quantity or 0),
                    "sup": {k: str(getattr(sup, k)) for k in sup.__table__.columns.keys() if k != "updated_at"},
                    "usta": {k: str(getattr(us, k)) for k in us.__table__.columns.keys() if k != "updated_at"},
                    "hodim": {k: str(getattr(hd, k)) for k in hd.__table__.columns.keys() if k != "updated_at"}}
    finally:
        d.close()


_N = [0]


def ord_body(**kw):
    _N[0] += 1
    kw.setdefault("notes", f"OR267 izoh {_N[0]}")
    item = {"name": f"OR267 detal {_N[0]}", "category": "panel", "quantity": 1, "unit_price": 1000}
    item.update(kw.pop("item", {}))
    t = {"project_id": ID["PB"], "order_type": "product", "items": [item]}
    t.update(kw)
    return t


# (nom, usul, url | None (url tanadan), tana(v), begona id)
YOLLAR = [
    ("A01 POST /api/employees yonalish_id", "post", "/api/employees",
     lambda v: {"name": "OR267 yangi hodim", "pay_type": "fixed", "yonalish_id": v}, ID["YA"]),
    ("A02 POST /api/transport-expenses yonalish_id", "post", "/api/transport-expenses",
     lambda v: {"amount": 1000.0, "yonalish_id": v}, ID["YA"]),
    ("A03 POST /api/recipes ingredients.inventory_id", "post", "/api/recipes",
     lambda v: {"name": f"OR267 ret {v}", "batch_size_kg": 10, "ingredients": [{"inventory_id": v, "quantity_kg": 1}]},
     ID["IA"]),
    ("A04 POST /api/finished/loss finished_product_id", "post", "/api/finished/loss",
     lambda v: {"finished_product_id": v, "quantity": 1, "brak_sabab": "boshqa"}, ID["FA"]),
    ("A05 POST /api/finished/loss brak_javobgar_id", "post", "/api/finished/loss",
     lambda v: {"finished_product_id": ID["FB"], "quantity": 1, "brak_sabab": "ishchi", "brak_javobgar_id": v}, ID["EA"]),
    ("A06 POST /api/orders items.penoplast_id", "post", "/api/orders",
     lambda v: ord_body(item={"penoplast_id": v}), ID["IA"]),
    ("A07 POST /api/orders items.finished_product_id", "post", "/api/orders",
     lambda v: ord_body(item={"finished_product_id": v, "category": "dona"}), ID["FA"]),
    ("A08 POST /api/orders qoplama_retsept_id", "post", "/api/orders",
     lambda v: ord_body(qoplama_retsept_id=v), ID["RA"]),
    ("A09 POST /api/orders qoplama_retsept_id + qoplamali detal", "post", "/api/orders",
     lambda v: ord_body(qoplama_retsept_id=v, item={"is_coated": True}), ID["RA"]),
    ("A10 POST /api/orders master_id", "post", "/api/orders",
     lambda v: ord_body(master_id=v), ID["MA"]),
    ("A11 POST /api/orders recipe_id", "post", "/api/orders",
     lambda v: ord_body(recipe_id=v), ID["RA"]),
    ("A12 POST /api/orders project_id", "post", "/api/orders",
     lambda v: ord_body(project_id=v), ID["PA"]),
    ("A13 POST /api/inventory/receipt supplier_id", "post", "/api/inventory/receipt",
     lambda v: {"items": [{"inventory_id": ID["IB"], "quantity": 1, "price_per_unit": 10}], "supplier_id": v}, ID["SA"]),
    ("A14 POST /api/inventory/receipt items.inventory_id", "post", "/api/inventory/receipt",
     lambda v: {"items": [{"inventory_id": v, "quantity": 1, "price_per_unit": 10}]}, ID["IA"]),
    ("A15 POST /api/production/product-types yonalish_id", "post", "/api/production/product-types",
     lambda v: {"name": f"OR267 tur {v}", "unit": "dona", "input_template": "quantity_only",
                "pricing_formula": "fixed_price", "fixed_unit_price": 100, "yonalish_id": v}, ID["YA"]),
    ("A16 POST /api/finished/sell master_id", "post", "/api/finished/sell",
     lambda v: {"finished_product_id": ID["FB"], "quantity": 1, "unit_price": 1000, "master_id": v}, ID["MA"]),
    ("A17 POST /api/finished/sell finished_product_id", "post", "/api/finished/sell",
     lambda v: {"finished_product_id": v, "quantity": 1, "unit_price": 1000}, ID["FA"]),
    ("A18 POST /api/suppliers/{id}/payment (yo'l)", "post", None,
     lambda v: (f"/api/suppliers/{v}/payment", {"amount": 10}), ID["SA"]),
    ("A19 PUT /api/employees/{EB} yonalish_id", "put", "EB",
     lambda v: {"yonalish_id": v}, ID["YA"]),
    # ── zip 267 qo'shimcha: tahrir va bog'lash yo'llari ──
    ("A20 PUT /api/orders/{OB} master_id (to'liq tana — OrderCreate)", "put", "OB",
     lambda v: ord_body(master_id=v), ID["MA"]),
    ("A21 PUT /api/orders/{OB} recipe_id (to'liq tana)", "put", "OB",
     lambda v: ord_body(recipe_id=v), ID["RA"]),
    ("A22 PUT /api/orders/{id} (yo'l — begona buyurtma, to'liq tana)", "put", None,
     lambda v: (f"/api/orders/{v}", ord_body()), "OA"),
    ("A23 POST /api/orders/{id}/payments (yo'l — begona buyurtma)", "post", None,
     lambda v: (f"/api/orders/{v}/payments", {"amount": 10, "payment_method": "cash"}), "OA"),
]

# A korxonasining buyurtmasi (A22 / A23 begona id si)
CA = kirgan("or267_a", "203.0.113.68")
_ra = CA.post("/api/orders", json={"project_id": ID["PA"], "order_type": "product", "notes": "OR267 A asos",
                                   "items": [{"name": "OR267 A detal", "category": "panel", "quantity": 1, "unit_price": 1000}]})
assert _ra.status_code == 200, (_ra.status_code, _ra.text[:300])
ID["OA"] = _ra.json()["id"]

_URL = {"EB": lambda: f"/api/employees/{ID['EB']}", "OB": lambda: f"/api/orders/{ID['OB']}"}

A0_HOLAT = korxona_holati(1)
A0_QIYMAT = a_qiymatlari()

section("A — begona id ↔ yo'q id: bir xil javob, ichki sabab yo'q, jurnal to'lmaydi, yarim yozuv yo'q")
for nom, met, url, tana, beg in YOLLAR:
    if isinstance(beg, str):
        beg = ID[beg]
    natija = []
    for v in (beg, YOQ):
        b0 = korxona_holati(2)
        x0 = xato_soni()
        b = tana(v)
        if url is None:
            u, b = b
        elif url in _URL:
            u = _URL[url]()
        else:
            u = url
        r = getattr(CB, met)(u, json=b)
        natija.append({"holat": r.status_code, "matn": re.sub(rf"(?<![0-9]){v}(?![0-9])", "<ID>", matn(r)), "xom": matn(r),
                       "jurnal": xato_soni() - x0, "b_farq": {t: (b0[t], n) for t, n in korxona_holati(2).items() if n != b0[t]}})
    bg, yq = natija
    check(f"{nom}: so'rov tanasi sxemadan o'tdi (422 emas — sinov haqiqatan bog'lanish tekshiruviga yetdi)",
          bg["holat"] != 422 and yq["holat"] != 422, (bg["xom"][:300], yq["xom"][:300]))
    check(f"{nom}: holat bir xil ({bg['holat']} ↔ {yq['holat']}), 500 emas",
          bg["holat"] == yq["holat"] and bg["holat"] < 500, (bg["xom"][:300], yq["xom"][:300]))
    if 200 <= bg["holat"] < 300:
        check(f"{nom}: 2xx — server maydonni o'zi hal qiladi (matn solishtirilmaydi)", yq["holat"] == bg["holat"])
    else:
        check(f"{nom}: matn bir xil (o'z id raqami «<ID>»)", bg["matn"] == yq["matn"], (bg["xom"][:400], yq["xom"][:400]))
        check(f"{nom}: rad etilgan so'rov B korxonasida hech narsa yozmadi",
              not bg["b_farq"] and not yq["b_farq"], (bg["b_farq"], yq["b_farq"]))
    check(f"{nom}: javobda ichki sabab yo'q", not any(w in bg["xom"] or w in yq["xom"] for w in ICHKI_SABAB),
          (bg["xom"][:300], yq["xom"][:300]))
    check(f"{nom}: xatolar jurnali to'lmadi", bg["jurnal"] == 0 and yq["jurnal"] == 0, (bg["jurnal"], yq["jurnal"]))

section("B — A korxonasi ma'lumoti o'zgarmagan")
_a1 = korxona_holati(1)
check("B1 A korxonasining HAR jadvaldagi qatorlari soni o'zgarmagan",
      _a1 == A0_HOLAT, {t: (A0_HOLAT[t], _a1[t]) for t in _KJ if A0_HOLAT[t] != _a1[t]})
_q1 = a_qiymatlari()
check("B2 A tayyor mahsuloti (soni, holati), materiali qoldig'i, ta'minotchisi, ustasi, hodimi — AYNAN",
      _q1 == A0_QIYMAT, (A0_QIYMAT, _q1))
check("B3 jadvallar ro'yxati bo'sh emas (sanoq haqiqatan ishlaydi)", len(_KJ) > 20 and A0_HOLAT.get("orders", 0) >= 1,
      (len(_KJ), A0_HOLAT.get("orders")))

section("C — o'z (B) id lari bilan oddiy so'rovlar ishlaydi")
r = CB.post("/api/orders", json=ord_body(master_id=ID["MB"], recipe_id=ID["RB"]))
check("C1 buyurtma o'z ustasi + retsepti bilan — 200", r.status_code == 200, (r.status_code, r.text[:300]))
r = CB.post("/api/inventory/receipt", json={"items": [{"inventory_id": ID["IB"], "quantity": 1, "price_per_unit": 10}],
                                             "supplier_id": ID["SB"]})
check("C2 kirim o'z ta'minotchisi + materiali bilan — 200", r.status_code == 200, (r.status_code, r.text[:300]))
r = CB.post("/api/finished/sell", json={"finished_product_id": ID["FB"], "quantity": 1, "unit_price": 1000, "master_id": ID["MB"]})
check("C3 o'z tayyor mahsulotini o'z ustasiga sotish — 200", r.status_code == 200, (r.status_code, r.text[:300]))
r = CB.put(f"/api/orders/{ID['OB']}", json=ord_body(master_id=ID["MB"]))
check("C4 o'z buyurtmasiga o'z ustasi — 200", r.status_code == 200, (r.status_code, r.text[:300]))
r = CB.put(f"/api/employees/{ID['EB']}", json={"yonalish_id": ID["YB"]})
check("C5 o'z hodimiga o'z yo'nalishi — 200", r.status_code == 200, (r.status_code, r.text[:300]))
r = CB.post(f"/api/suppliers/{ID['SB']}/payment", json={"amount": 10})
check("C6 o'z ta'minotchisiga to'lov — 2xx yoki biznes qoidasi (4xx), 500 emas; begona bilan farqi — 404 emas",
      r.status_code < 500 and r.status_code != 404, (r.status_code, r.text[:300]))

print(f"\nNATIJA: {OK} / {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(1 if FAIL else 0)
