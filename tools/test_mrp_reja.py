#!/usr/bin/env python3
"""
test_mrp_reja.py — kech113 darvozasi: Ishlab chiqarish (MRP) sahifasi dizayni — egasi qarori "MRP asosiy: 1–4",
variant "A — Jadval + oynalar" (server qismi) va K113-1 / K113-2.

NIMA UCHUN KERAK
  Sahifa endi hisobni OLDINDAN ko'rsatadi: retsept oynasida har qator narxi va 1 birlik taxminiy tannarxi
  (`POST /api/production/boms/preview`), «Yangi ishlab chiqarish» oynasida xomashyo yetadimi / qanchasi yetmaydi / eng
  ko'pi qancha chiqadi va taxminiy tannarx (`GET /api/production/orders/preview`), «Boshlash» / «Yakunlash» oynasida —
  mavjud ishlab chiqarish rejasi (`GET /api/production/orders/{id}/preview`), ro'yxatda — mahsulot nomi, birlik, mijoz
  buyurtmasi raqami va mijoz, qoralama uchun xomashyo holati, davr (Toshkent oyi) bo'yicha saralash
  (`GET /api/production/orders?oy=YYYY-MM`). Oldindan ko'rsatilgan narsa HAQIQIY amal bilan AYNAN bir xil bo'lishi SHART
  (aks holda oyna "yetadi" deydi-yu, «Boshlash» rad etadi) — shu test buni o'lchaydi: reja «mumkin» ⇔ boshlash /
  yakunlash o'tadi, reja tannarxi = yakunlangandagi tannarx, reja xatosi = yaratish / boshlash xabari (AYNAN matn).
  K113-1 (O'LCHANGAN — `work/k113/probe_float.py`, asl `df465d8`, SQLite = PG): 1 kg + 10 % isrof × 3 m² =
    3.3000000000000003; omborda AYNAN 3.3 kg — «Boshlash» ham «Yakunlash» ham 409 berardi.
  K113-2 (O'LCHANGAN — `work/k113/probe_ikki_qator.py`, asl `df465d8`, SQLite = PG): bir material retseptda ikki
    qatorda (5 + 3 kg), omborda 6 kg — «Boshlash» 200 (har qator alohida), «Yakunlash» 409 ("bor: 1").

BO'LIMLAR: R — retsept tannarxi; Y — yangi ishlab chiqarish rejasi; G — reja ⇔ boshlash (chegarada); K — K113-1 / K113-2;
  B — jarayondagilar bilan raqobat; M — mavjud ishlab chiqarish rejasi; L — ro'yxat; Q — so'rovlar soni; X — xabarlar;
  N — reja hech narsa yozmaydi; P — sahifa; S — statik.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
    python3 tools/test_mrp_reja.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_mrp_reja.py
Asl kodga qarshi QULAMAYDI (HTTP istisno → 599, yangi nomlar `getattr`, shartlar lambda ichida). Chiqish kodi 0 — hammasi o'tdi.
"""
import os
import sys
import json
import inspect
import tempfile
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "mrp_reja_test"
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
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'mrp_reja_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import production_service                      # noqa: E402
    import production_routes                       # noqa: E402
    import database                                # noqa: E402

from sqlalchemy import event, text                 # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import UserRole, Inventory             # noqa: E402
from production_models import Company, ProductionOrder  # noqa: E402
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
        print(f"  ✗ {label}   {str(detail)[:600]}")


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


def detail(r):
    d = (js(r) or {}).get("detail") if isinstance(js(r), dict) else None
    if isinstance(d, dict):
        return d.get("message") or d.get("error") or json.dumps(d, ensure_ascii=False)
    return d


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def yaqin(a, b, eps=0.006):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


XATO5 = []


def so(c, metod, url, **k):
    r = req(c, metod, url, **k)
    if r.status_code >= 500:
        XATO5.append((metod, url, r.status_code, getattr(r, "text", "")[:200]))
    return r


SANOQ = [0]


@event.listens_for(engine, "before_cursor_execute")
def _sanoq(conn, cursor, statement, parameters, context, executemany):   # noqa: ARG001
    SANOQ[0] += 1


def sql(q, **p):
    try:
        with engine.connect() as c:
            r = c.execute(text(q), p)
            v = [tuple(x) for x in r.fetchall()] if r.returns_rows else None
            c.commit()
            return v
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {str(e)[:200]}")


# ══════════════════════════════════════════════════════════════
# 0. Fikstura: A (1) va B (2) korxonalari
# ══════════════════════════════════════════════════════════════
section("0. Fikstura")
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="MRJ B korxona"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "MRJ_A", "Parol123!", UserRole.ADMIN, "MRJ Admin", company_id=1)
    auth.create_user(_db, "MRJ_M", "Parol123!", UserRole.MANAGER, "MRJ Menejer", company_id=1)
    auth.create_user(_db, "MRJ_B", "Parol123!", UserRole.ADMIN, "MRJ B Admin", company_id=2)
_db.close()


def kir(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


A, _la = kir("MRJ_A")
MN, _lm = kir("MRJ_M")
B, _lb = kir("MRJ_B")
check("F0 uch foydalanuvchi tizimga kirdi (A admin, A menejer, B admin)", (_la, _lm, _lb) == (302, 302, 302), (_la, _lm, _lb))

ID = {}


def mat(c, nom, unit, stock, price, **k):
    return (js(so(c, "post", "/api/inventory", json=dict({"item_name": nom, "unit": unit, "stock_quantity": stock,
                                                          "price_per_unit": price}, **k))) or {}).get("id")


def tur(c, nom, unit, qoplama=False):
    t = {"name": nom, "unit": unit, "input_template": "quantity_only", "pricing_formula": "unit_based",
         "supports_coating": qoplama}
    if qoplama:
        t["coating_price_multiplier"] = 2
    return (js(so(c, "post", "/api/production/product-types", json=t)) or {}).get("id")


def retsept(c, pt, nom, partiya, items):
    return js(so(c, "post", "/api/production/boms", json={"product_type_id": pt, "variant_name": nom,
                                                           "batch_quantity": partiya, "items": items})) or {}


ID["qum"] = mat(A, "MRJ Qum", "kg", 480, 820)
ID["kley"] = mat(A, "MRJ Kley", "kg", 36, 3150)
ID["setka"] = mat(A, "MRJ Setka", "m²", 120, 2600)
ID["boyoq"] = mat(A, "MRJ Bo'yoq", "kg", 18, 24000)
ID["sement"] = mat(A, "MRJ Sement", "qop", 10, 60000, base_unit="kg", conversion_factor=50)
ID["kley2"] = mat(A, "MRJ Kley K1", "kg", 3.3, 3150)
ID["boyoq2"] = mat(A, "MRJ Bo'yoq K2", "kg", 6, 1000)
ID["narxsiz"] = mat(A, "MRJ Narxsiz", "kg", 100, 0)
ID["trav"] = tur(A, "MRJ Travertin", "m²", qoplama=True)
TRAV_ITEMS = [{"inventory_id": ID["qum"], "quantity": 5},
              {"inventory_id": ID["kley"], "quantity": 1, "scrap_factor_percent": 10},
              {"inventory_id": ID["setka"], "quantity": 1, "scrap_factor_percent": 5},
              {"inventory_id": ID["boyoq"], "quantity": 0.15, "is_optional": True, "is_coating": True,
               "fixed_cost_per_unit": 800}]
_b = retsept(A, ID["trav"], "Standart", 1, TRAV_ITEMS)
ID["trav_b"] = _b.get("id")
ID["trav_qopl"] = next((x.get("id") for x in (_b.get("items") or []) if x.get("is_coating")), None)
ID["kqop"] = tur(A, "MRJ Kafel kley", "qop")
KQOP_ITEMS = [{"inventory_id": ID["sement"], "quantity": 7},
              {"inventory_id": ID["qum"], "quantity": 17.5, "percentage_cost": 10}]
ID["kqop_b"] = retsept(A, ID["kqop"], "25 kg qop", 1, KQOP_ITEMS).get("id")
ID["t3"] = tur(A, "MRJ K1 Travertin", "m²")
ID["t3_b"] = retsept(A, ID["t3"], "Standart", 1, [{"inventory_id": ID["kley2"], "quantity": 1,
                                                   "scrap_factor_percent": 10}]).get("id")
ID["dubl"] = tur(A, "MRJ K2 Dekor", "dona", qoplama=True)
_b = retsept(A, ID["dubl"], "Standart", 1, [{"inventory_id": ID["boyoq2"], "quantity": 5},
                                            {"inventory_id": ID["boyoq2"], "quantity": 3, "is_optional": True,
                                             "is_coating": True}])
ID["dubl_b"] = _b.get("id")
ID["dubl_qopl"] = next((x.get("id") for x in (_b.get("items") or []) if x.get("is_coating")), None)
ID["loyiha"] = (js(so(A, "post", "/api/projects", json={"project_name": "MRJ Loyiha", "client_name": "MRJ Mijoz"})) or {}).get("id")
_o = js(so(A, "post", "/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": ID["loyiha"], "order_type": "product", "deadline": "2026-12-10", "is_draft": False,
    "items": [{"name": "MRJ Travertin Q", "category": "mrp_product", "quantity": 10, "unit_price": 50000, "is_coated": True,
               "product_type_id": ID["trav"]},
              {"name": "MRJ Travertin", "category": "mrp_product", "quantity": 5, "unit_price": 25000, "is_coated": False,
               "product_type_id": ID["trav"]}]})) or {}
ID["o"] = _o.get("id")
ORD_RAQAM = _o.get("order_number")
_it = sorted(_o.get("items") or [], key=lambda x: x.get("id", 0))
ID["d_q"], ID["d_oddiy"] = (_it[0]["id"], _it[1]["id"]) if len(_it) == 2 else (None, None)
# B korxonasi
ID["b_mat"] = mat(B, "MRJ B Tosh", "kg", 1000, 500)
ID["b_pt"] = tur(B, "MRJ B Travertin", "m²")
ID["b_bom"] = retsept(B, ID["b_pt"], "Oddiy", 1, [{"inventory_id": ID["b_mat"], "quantity": 2}]).get("id")
ID["b_po"] = ((js(so(B, "post", "/api/production/orders", json={
    "product_type_id": ID["b_pt"], "bom_id": ID["b_bom"], "quantity": 3, "source_type": "warehouse_stock"})) or {})
    .get("production_order") or {}).get("id")
check("F1 fikstura: 8 material, 4 mahsulot turi va retsept, mijoz buyurtmasi (2 MRP detal), B korxona",
      all(v is not None for v in ID.values()) and ORD_RAQAM, ID)


def po_yarat(c, tana):
    r = so(c, "post", "/api/production/orders", json=tana)
    return ((js(r) or {}).get("production_order") or {}).get("id"), r


def reja(c, **p):
    return so(c, "get", "/api/production/orders/preview", params=p)


def mreja(c, pid):
    return so(c, "get", f"/api/production/orders/{pid}/preview")


def qator(rj, inv_id, nechanchi=0):
    qs = [x for x in (rj or {}).get("qatorlar") or [] if x.get("inventory_id") == inv_id]
    return qs[nechanchi] if len(qs) > nechanchi else {}


def ombor(inv_id):
    s = SessionLocal()
    try:
        i = s.get(Inventory, inv_id)
        return float(i.stock_quantity) if i is not None else None
    finally:
        s.close()


def ombor_qoy(inv_id, miq):
    s = SessionLocal()
    try:
        i = s.get(Inventory, inv_id)
        i.stock_quantity = miq
        s.commit()
    finally:
        s.close()


def royxat(c, **p):
    return js(so(c, "get", "/api/production/orders", params=p)) or []


def royxatda(c, pid, **p):
    return next((x for x in royxat(c, **p) if isinstance(x, dict) and x.get("id") == pid), {})


# ══════════════════════════════════════════════════════════════
section("R. Retsept oynasi — saqlanmagan retseptning tannarxi (POST /api/production/boms/preview)")
# ══════════════════════════════════════════════════════════════
BOM_TANA = {"product_type_id": ID["trav"], "variant_name": "Hisob", "batch_quantity": 1, "notes": None, "items": TRAV_ITEMS}
_r = so(A, "post", "/api/production/boms/preview", json=BOM_TANA)
R1 = js(_r) or {}
check("R1 200; 1 m²: xomashyo 4 100 + 3 465 + 2 730 = 10 295; qoplamali 10 295 + 3 600 + 800 = 14 695",
      lambda: _r.status_code == 200 and yaqin(R1["doim"]["jami"], 10295) and yaqin(R1["qoplamali"]["jami"], 14695)
      and yaqin(R1["hammasi"]["jami"], 14695) and yaqin(R1["qoplamali"]["qoshimcha"], 800), (_r.status_code, R1))
check("R2 qatorlar: kley samarali 1,1 kg (1 + 10 %), summa 3 465; qoplama qatori — ixtiyoriy / qoplama; narxsiz yo'q",
      lambda: yaqin(R1["qatorlar"][1]["samarali"], 1.1, 1e-9) and yaqin(R1["qatorlar"][1]["summa"], 3465)
      and R1["qatorlar"][3]["is_coating"] is True and R1["qoplama_bor"] is True and R1["ixtiyoriy_bor"] is False
      and R1["narxsiz"] == [] and R1["birlik"] == "m²" and [q["tartib"] for q in R1["qatorlar"]] == [0, 1, 2, 3],
      R1.get("qatorlar"))
_r = so(A, "post", "/api/production/boms/preview", json=dict(BOM_TANA, batch_quantity=10, items=[
    dict(it, quantity=it["quantity"] * 10) for it in TRAV_ITEMS]))
check("R3 retsept 10 m² uchun yozilsa ham — 1 m² tannarxi o'zgarmaydi (10 295 / 14 695)",
      lambda: yaqin((js(_r) or {})["doim"]["jami"], 10295) and yaqin((js(_r) or {})["qoplamali"]["jami"], 14695),
      js(_r))
_r = so(A, "post", "/api/production/boms/preview", json={"product_type_id": ID["kqop"], "variant_name": "Hisob",
                                                         "batch_quantity": 1, "notes": None, "items": KQOP_ITEMS})
R4 = js(_r) or {}
check("R4 birlik o'girish: sement 7 kg = 0,14 qop × 60 000 = 8 400; qum 14 350; foizli xarajat 10 % → 25 025 / qop",
      lambda: R4["qatorlar"][0]["unit"] == "kg" and R4["qatorlar"][0]["stock_unit"] == "qop"
      and yaqin(R4["qatorlar"][0]["ombor_miqdor"], 0.14, 1e-9) and yaqin(R4["qatorlar"][0]["summa"], 8400)
      and yaqin(R4["doim"]["xomashyo"], 22750) and yaqin(R4["doim"]["qoshimcha"], 2275) and yaqin(R4["doim"]["jami"], 25025),
      R4)
_r = so(A, "post", "/api/production/boms/preview", json=dict(BOM_TANA, items=TRAV_ITEMS[:1] + [
    {"inventory_id": ID["narxsiz"], "quantity": 1}]))
check("R5 narxi kiritilmagan material — `narxsiz` ro'yxatida", lambda: (js(_r) or {})["narxsiz"] == ["MRJ Narxsiz"], js(_r))
# Tana tekshiruvi — retsept YARATISH bilan AYNAN
for _izoh, _tana in [("isrof 150 %", dict(BOM_TANA, items=[dict(TRAV_ITEMS[0], scrap_factor_percent=150)])),
                     ("B korxona materiali", dict(BOM_TANA, items=[{"inventory_id": ID["b_mat"], "quantity": 1}])),
                     ("noma'lum maydon", dict(BOM_TANA, foo=1)),
                     ("miqdor 0", dict(BOM_TANA, items=[dict(TRAV_ITEMS[0], quantity=0)]))]:
    _p = so(A, "post", "/api/production/boms/preview", json=_tana)
    _y = so(A, "post", "/api/production/boms", json=dict(_tana, variant_name="MRJ rad " + _izoh))
    check(f"R6 {_izoh}: reja ham, yaratish ham 400, sabab AYNAN", lambda: _p.status_code == 400 and _y.status_code == 400
          and detail(_p) == detail(_y) and detail(_p), (_p.status_code, detail(_p), _y.status_code, detail(_y)))
_r = so(A, "post", "/api/production/boms/preview", json=dict(BOM_TANA, product_type_id=ID["b_pt"]))
check("R7 B korxonaning mahsulot turi — 404 «Mahsulot turi topilmadi»", _r.status_code == 404
      and detail(_r) == "Mahsulot turi topilmadi", (_r.status_code, detail(_r)))
_r = so(MN, "post", "/api/production/boms/preview", json=BOM_TANA)
check("R8 menejer — 403 (retsept yaratish kabi: admin / omborchi)", _r.status_code == 403, _r.status_code)

# ══════════════════════════════════════════════════════════════
section("Y. «Yangi ishlab chiqarish» rejasi (GET /api/production/orders/preview)")
# ══════════════════════════════════════════════════════════════
_r = reja(A, product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=40, source_type="warehouse_stock")
Y1 = js(_r) or {}
check("Y1 40 m² omborga: qum 200 / 480 yetadi, kley 44 / 36 — 8 kg yetmaydi, setka 42 / 120 yetadi, qoplama kiritilmagan",
      lambda: _r.status_code == 200 and qator(Y1, ID["qum"])["holat"] == "yetadi" and yaqin(qator(Y1, ID["qum"])["kerak"], 200)
      and qator(Y1, ID["kley"])["holat"] == "yetmaydi" and yaqin(qator(Y1, ID["kley"])["yetmaydi"], 8, 1e-6)
      and yaqin(qator(Y1, ID["kley"])["omborda"], 36) and qator(Y1, ID["setka"])["holat"] == "yetadi"
      and qator(Y1, ID["boyoq"])["holat"] == "kiritilmagan", (_r.status_code, Y1))
check("Y2 40 m²: mumkin EMAS, yetmaydi = [kley], eng ko'pi 36 / 1,1 = 32,72 m², tannarx 411 800 (1 m² — 10 295)",
      lambda: Y1["mumkin"] is False and Y1["yetmaydi"] == ["MRJ Kley"] and yaqin(Y1["maks_bosh"], 36 / 1.1, 1e-9)
      and yaqin(Y1["maks_ombor"], 36 / 1.1, 1e-9) and yaqin(Y1["tannarx"], 411800, 0.01) and yaqin(Y1["bir_birlik"], 10295)
      and Y1["mahsulot"] == "MRJ Travertin" and Y1["birlik"] == "m²" and Y1["retsept"] == "Standart" and Y1["xatolar"] == [],
      {k: Y1.get(k) for k in ("mumkin", "yetmaydi", "maks_bosh", "tannarx", "bir_birlik", "xatolar")})
_r = reja(A, product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=10, source_type="warehouse_stock",
          selected_optional_bom_item_ids=[ID["trav_qopl"]])
check("Y3 10 m² omborga, qoplama TANLANGAN: mumkin, bo'yoq 1,5 kg kiritilgan, tannarx 146 950 (retsept oynasidagi 14 695 × 10)",
      lambda: (js(_r) or {})["mumkin"] is True and qator(js(_r), ID["boyoq"])["included"] is True
      and yaqin(qator(js(_r), ID["boyoq"])["kerak"], 1.5, 1e-9) and yaqin((js(_r) or {})["tannarx"], 10 * R1["qoplamali"]["jami"], 0.01)
      and (js(_r) or {})["tanlangan_ixtiyoriy"] == [ID["trav_qopl"]], js(_r))
_r = reja(A, product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=4, source_type="customer_order",
          source_order_item_id=ID["d_q"])
check("Y4 qoplamali detal uchun — qoplama qatori O'ZI tanlanadi (tanlanmagan bo'lsa ham), qolgan 10, tannarx 4 × 14 695",
      lambda: (js(_r) or {})["tanlangan_ixtiyoriy"] == [ID["trav_qopl"]] and qator(js(_r), ID["boyoq"])["included"] is True
      and yaqin((js(_r) or {})["qolgan"], 10) and yaqin((js(_r) or {})["tannarx"], 4 * 14695, 0.01) and (js(_r) or {})["mumkin"] is True,
      js(_r))
_r = reja(A, product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=4, source_type="customer_order",
          source_order_item_id=ID["d_oddiy"], selected_optional_bom_item_ids=[ID["trav_qopl"]])
check("Y5 qoplamasiz detal uchun — qoplama qatori OLIB TASHLANADI (tanlangan bo'lsa ham), tannarx 4 × 10 295",
      lambda: (js(_r) or {})["tanlangan_ixtiyoriy"] == [] and qator(js(_r), ID["boyoq"])["included"] is False
      and yaqin((js(_r) or {})["tannarx"], 4 * 10295, 0.01), js(_r))
# Reja xatosi = yaratish xabari (AYNAN)
for _izoh, _p in [("detal uchun ortiqcha (12 > 10)", dict(product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=12,
                                                          source_type="customer_order", source_order_item_id=ID["d_q"])),
                  ("omborga + detal", dict(product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=1,
                                           source_type="warehouse_stock", source_order_item_id=ID["d_q"])),
                  ("mijoz buyurtmasiga, detal yo'q", dict(product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=1,
                                                          source_type="customer_order")),
                  ("boshqa turning detali", dict(product_type_id=ID["kqop"], bom_id=ID["kqop_b"], quantity=1,
                                                 source_type="customer_order", source_order_item_id=ID["d_q"]))]:
    _pr = reja(A, **_p)
    _pid, _y = po_yarat(A, {k: v for k, v in _p.items()})
    check(f"Y6 {_izoh}: reja 200, mumkin EMAS, xato = yaratish 400 sababi (AYNAN)",
          lambda: _pr.status_code == 200 and (js(_pr) or {})["mumkin"] is False and _y.status_code == 400 and _pid is None
          and (js(_pr) or {})["xatolar"] == [detail(_y)], (_pr.status_code, (js(_pr) or {}).get("xatolar"), _y.status_code, detail(_y)))
for _izoh, _p in [("miqdor 0", dict(product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=0, source_type="warehouse_stock")),
                  ("manba turi noto'g'ri", dict(product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=1, source_type="boshqa")),
                  ("miqdor juda katta", dict(product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=1e15,
                                             source_type="warehouse_stock")),
                  ("noma'lum mahsulot turi", dict(product_type_id=999999, bom_id=ID["trav_b"], quantity=1,
                                                  source_type="warehouse_stock")),
                  ("B korxonaning mahsulot turi", dict(product_type_id=ID["b_pt"], bom_id=ID["b_bom"], quantity=1,
                                                       source_type="warehouse_stock")),
                  ("yashirilmagan, lekin boshqa turning retsepti", dict(product_type_id=ID["trav"], bom_id=ID["kqop_b"],
                                                                         quantity=1, source_type="warehouse_stock"))]:
    _pr = reja(A, **_p)
    _pid, _y = po_yarat(A, _p)
    check(f"Y7 {_izoh}: reja ham, yaratish ham 400, sabab AYNAN", lambda: _pr.status_code == 400 and _y.status_code == 400
          and detail(_pr) == detail(_y) and detail(_pr), (_pr.status_code, detail(_pr), _y.status_code, detail(_y)))
_r = reja(MN, product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=1, source_type="warehouse_stock")
check("Y8 menejer ham rejani ko'radi (ishlab chiqarish yaratish huquqi bilan bir xil) — 200", _r.status_code == 200, _r.status_code)

# ══════════════════════════════════════════════════════════════
section("G. Reja «mumkin» ⇔ «Boshlash» o'tadi (chegarada: kley 36 kg, 1,1 kg / m²)")
# ══════════════════════════════════════════════════════════════
for _miq in (32, 32.72, 32.7272, 33, 40):
    _pid, _y = po_yarat(A, {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": _miq,
                            "source_type": "warehouse_stock"})
    _yr = js(reja(A, product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=_miq, source_type="warehouse_stock")) or {}
    _mr = js(mreja(A, _pid)) or {}
    _st = so(A, "post", f"/api/production/orders/{_pid}/start")
    _kutish = "o'tadi" if _miq * 1.1 <= 36 else "rad"
    check(f"G1 {_miq} m²: yangi reja = mavjud reja = boshlash natijasi ({_kutish})",
          lambda: _yr.get("mumkin") == _mr.get("mumkin") == (_st.status_code == 200) == (_miq * 1.1 <= 36 + 1e-9),
          (_miq, _yr.get("mumkin"), _mr.get("mumkin"), _st.status_code, detail(_st)))
    so(A, "post", f"/api/production/orders/{_pid}/cancel")

# ══════════════════════════════════════════════════════════════
section("K. K113-1 (float shovqini) va K113-2 (bir material ikki qatorda)")
# ══════════════════════════════════════════════════════════════
_yr = js(reja(A, product_type_id=ID["t3"], bom_id=ID["t3_b"], quantity=3, source_type="warehouse_stock")) or {}
_pid, _ = po_yarat(A, {"product_type_id": ID["t3"], "bom_id": ID["t3_b"], "quantity": 3, "source_type": "warehouse_stock"})
_st = so(A, "post", f"/api/production/orders/{_pid}/start")
check("K1 1 kg + 10 % × 3 m² = 3,3000000000000003; omborda AYNAN 3,3 kg → reja «yetadi», «Boshlash» 200 (asl kodda 409)",
      lambda: _yr["mumkin"] is True and qator(_yr, ID["kley2"])["holat"] == "yetadi" and _st.status_code == 200,
      (_yr.get("mumkin"), qator(_yr, ID["kley2"]), _st.status_code, detail(_st)))
_mr = js(mreja(A, _pid)) or {}
_cm = so(A, "post", f"/api/production/orders/{_pid}/complete")
check("K2 «Yakunlash» rejasi mumkin va yakunlash 200; qoldiq AYNAN 0 (−4,4e-16 emas)",
      lambda: _mr["mumkin"] is True and _mr["rejim"] == "yakunlash" and _cm.status_code == 200 and ombor(ID["kley2"]) == 0.0,
      (_mr.get("mumkin"), _cm.status_code, detail(_cm), repr(ombor(ID["kley2"]))))
_p = dict(product_type_id=ID["dubl"], bom_id=ID["dubl_b"], quantity=1, source_type="warehouse_stock",
          selected_optional_bom_item_ids=[ID["dubl_qopl"]])
_yr = js(reja(A, **_p)) or {}
_pid, _ = po_yarat(A, _p)
_st = so(A, "post", f"/api/production/orders/{_pid}/start")
check("K3 bo'yoq 5 + 3 kg (ikki qator), omborda 6: reja — 2-qator «yetmaydi 2 kg», mumkin EMAS; «Boshlash» 409 (asl kodda 200)",
      lambda: _yr["mumkin"] is False and qator(_yr, ID["boyoq2"], 0)["holat"] == "yetadi"
      and qator(_yr, ID["boyoq2"], 1)["holat"] == "yetmaydi" and yaqin(qator(_yr, ID["boyoq2"], 1)["yetmaydi"], 2, 1e-9)
      and yaqin(qator(_yr, ID["boyoq2"], 1)["oldingi"], 5, 1e-9) and _yr["yetmaydi"] == ["MRJ Bo'yoq K2"]
      and _st.status_code == 409, (_yr.get("mumkin"), _yr.get("qatorlar"), _st.status_code))
check("K4 boshlash xabari — jami kerak va ombordagi qoldiq: «kerak: 8 kg — retseptning bir necha qatorida, bor: 6 kg»",
      lambda: detail(_st) == "Omborda yetarli 'MRJ Bo'yoq K2' yo'q (kerak: 8 kg — retseptning bir necha qatorida, bor: 6 kg)",
      detail(_st))
ombor_qoy(ID["boyoq2"], 8)
_yr = js(reja(A, **_p)) or {}
_st = so(A, "post", f"/api/production/orders/{_pid}/start")
_cm = so(A, "post", f"/api/production/orders/{_pid}/complete")
check("K5 omborda 8 kg: reja mumkin, boshlash 200, yakunlash 200, qoldiq 0; eng ko'pi = 8 / 8 = 1 dona",
      lambda: _yr["mumkin"] is True and yaqin(_yr["maks_ombor"], 1, 1e-9) and _st.status_code == 200 and _cm.status_code == 200
      and ombor(ID["boyoq2"]) == 0.0, (_yr.get("mumkin"), _yr.get("maks_ombor"), _st.status_code, _cm.status_code, ombor(ID["boyoq2"])))
ombor_qoy(ID["boyoq2"], 6)
_pid2, _ = po_yarat(A, _p)
ombor_qoy(ID["boyoq2"], 20)
so(A, "post", f"/api/production/orders/{_pid2}/start")
ombor_qoy(ID["boyoq2"], 6)
_mr = js(mreja(A, _pid2)) or {}
_cm = so(A, "post", f"/api/production/orders/{_pid2}/complete")
check("K6 jarayonda, omborda 6 (8 kerak): «Yakunlash» rejasi mumkin EMAS (2-qator) = yakunlash 409, ombor o'zgarmadi",
      lambda: _mr["mumkin"] is False and qator(_mr, ID["boyoq2"], 1)["holat"] == "yetmaydi" and _cm.status_code == 409
      and ombor(ID["boyoq2"]) == 6.0, (_mr.get("mumkin"), _cm.status_code, ombor(ID["boyoq2"])))
so(A, "post", f"/api/production/orders/{_pid2}/cancel")

# ══════════════════════════════════════════════════════════════
section("B. Jarayondagi ishlab chiqarishlar bilan raqobat (xomashyo ombordan faqat «Yakunlash» da yechiladi)")
# ══════════════════════════════════════════════════════════════
_t20 = {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 20, "source_type": "warehouse_stock"}
PO1, _ = po_yarat(A, _t20)
_st1 = so(A, "post", f"/api/production/orders/{PO1}/start")
_yr = js(reja(A, **_t20)) or {}
check("B1 №1 (20 m², kley 22 kg) jarayonda; yangi 20 m² rejasi: kley «jarayondagilar bilan yetmaydi», lekin mumkin (boshlash "
      "faqat qoldiqni tekshiradi), eng ko'pi (36 − 22) / 1,1 = 12,72",
      lambda: _st1.status_code == 200 and _yr["mumkin"] is True and qator(_yr, ID["kley"])["holat"] == "band_bilan_yetmaydi"
      and yaqin(qator(_yr, ID["kley"])["band"], 22, 1e-9) and qator(_yr, ID["kley"])["band_po"] == [PO1]
      and _yr["ogohlantirish"] == ["MRJ Kley"] and yaqin(_yr["maks_bosh"], 14 / 1.1, 1e-9) and yaqin(_yr["maks_ombor"], 36 / 1.1, 1e-9),
      (_st1.status_code, _yr.get("mumkin"), qator(_yr, ID["kley"]), _yr.get("maks_bosh")))
PO2, _ = po_yarat(A, _t20)
_l2 = royxatda(A, PO2, oy="hammasi")
check("B2 ro'yxatda №2 qoralama: xomashyo holati «band_bilan_yetmaydi», taxminiy tannarx = reja tannarxi",
      lambda: _l2["xomashyo_holati"] == "band_bilan_yetmaydi" and yaqin(_l2["taxminiy_tannarx"], _yr["tannarx"], 1e-6)
      and _l2["yetmaydi"] == [], _l2)
_st2 = so(A, "post", f"/api/production/orders/{PO2}/start")
_mr2 = js(mreja(A, PO2)) or {}
check("B3 №2 boshlandi (reja «mumkin» bilan bir xil); «Yakunlash» rejasi — №1 bilan raqobat ogohlantirishi",
      lambda: _st2.status_code == 200 and _mr2["mumkin"] is True and qator(_mr2, ID["kley"])["holat"] == "band_bilan_yetmaydi"
      and qator(_mr2, ID["kley"])["band_po"] == [PO1], (_st2.status_code, _mr2.get("mumkin"), qator(_mr2, ID["kley"])))
_cm1 = so(A, "post", f"/api/production/orders/{PO1}/complete")
_mr2 = js(mreja(A, PO2)) or {}
_cm2 = so(A, "post", f"/api/production/orders/{PO2}/complete")
check("B4 №1 yakunlandi (kley 36 → 14); №2 «Yakunlash» rejasi: kley 8 kg yetmaydi, mumkin EMAS = yakunlash 409",
      lambda: _cm1.status_code == 200 and yaqin(ombor(ID["kley"]), 14, 1e-9) and _mr2["mumkin"] is False
      and qator(_mr2, ID["kley"])["holat"] == "yetmaydi" and yaqin(qator(_mr2, ID["kley"])["yetmaydi"], 8, 1e-9)
      and _cm2.status_code == 409, (_cm1.status_code, ombor(ID["kley"]), _mr2.get("mumkin"), _cm2.status_code))
so(A, "post", f"/api/production/orders/{PO2}/cancel")
so(A, "put", "/api/production/company-settings", params={"allow_negative_stock": "true"})
_yr = js(reja(A, **_t20)) or {}
_pid, _ = po_yarat(A, _t20)
_st = so(A, "post", f"/api/production/orders/{_pid}/start")
check("B5 korxona «manfiy qoldiq»ka ruxsat bergan: reja mumkin (ogohlantirish bilan), boshlash 200 va ogohlantirish qaytaradi",
      lambda: _yr["mumkin"] is True and _yr["manfiy_ruxsat"] is True and _yr["yetmaydi"] == ["MRJ Kley"]
      and _st.status_code == 200 and len((js(_st) or {}).get("stock_warnings") or []) == 1,
      (_yr.get("mumkin"), _yr.get("manfiy_ruxsat"), _st.status_code))
so(A, "post", f"/api/production/orders/{_pid}/cancel")
so(A, "put", "/api/production/company-settings", params={"allow_negative_stock": "false"})

# ══════════════════════════════════════════════════════════════
section("M. Mavjud ishlab chiqarish rejasi = haqiqiy boshlash / yakunlash (GET /orders/{id}/preview)")
# ══════════════════════════════════════════════════════════════
ombor_qoy(ID["kley"], 36)
_pq = {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 2, "source_type": "warehouse_stock",
       "selected_optional_bom_item_ids": [ID["trav_qopl"]]}
PM, _ = po_yarat(A, _pq)
_d = js(mreja(A, PM)) or {}
_st = so(A, "post", f"/api/production/orders/{PM}/start")
_surat = ((js(_st) or {}).get("production_order") or {}).get("recipe_snapshot") or []
check("M1 qoralama rejasi qatorlari = boshlash surati (har kiritilgan qator: kerak, summa — bom_item_id bo'yicha)",
      lambda: _d["rejim"] == "boshlash" and _st.status_code == 200 and len(_surat) == 4 and all(
          yaqin(next(q for q in _d["qatorlar"] if q["bom_item_id"] == s["bom_item_id"])["kerak"],
                s["total_quantity_needed_stock_unit"], 1e-12)
          and yaqin(next(q for q in _d["qatorlar"] if q["bom_item_id"] == s["bom_item_id"])["summa"], s["line_cost"], 1e-9)
          and next(q for q in _d["qatorlar"] if q["bom_item_id"] == s["bom_item_id"])["included"] == s["included"]
          for s in _surat), (_d.get("qatorlar"), _surat))
_j = js(mreja(A, PM)) or {}
_cm = so(A, "post", f"/api/production/orders/{PM}/complete")
_po = (js(_cm) or {}).get("production_order") or {}
check("M2 jarayondagi reja tannarxi = yakunlangandagi tannarx (xomashyo, qo'shimcha, jami) = retsept oynasidagi 2 × 14 695",
      lambda: _j["rejim"] == "yakunlash" and _cm.status_code == 200 and yaqin(round(_j["tannarx"], 2), _po["total_cost"])
      and yaqin(round(_j["xomashyo"], 2), _po["total_material_cost"]) and yaqin(round(_j["qoshimcha"], 2), _po["total_extra_cost"])
      and yaqin(_po["total_cost"], 2 * R1["qoplamali"]["jami"], 0.01) and yaqin(_d["tannarx"], _j["tannarx"], 1e-6),
      (_j.get("tannarx"), _po.get("total_cost"), _d.get("tannarx")))
PK, _ = po_yarat(A, {"product_type_id": ID["kqop"], "bom_id": ID["kqop_b"], "quantity": 2, "source_type": "warehouse_stock"})
_d = js(mreja(A, PK)) or {}
so(A, "post", f"/api/production/orders/{PK}/start")
_cm = so(A, "post", f"/api/production/orders/{PK}/complete")
check("M3 kafel kley 2 qop: reja tannarxi = yakunlangandagi = retsept oynasi 2 × 25 025 (birlik o'girish, foizli xarajat)",
      lambda: yaqin(((js(_cm) or {}).get("production_order") or {})["total_cost"], 2 * R4["doim"]["jami"], 0.01)
      and yaqin(round(_d["tannarx"], 2), ((js(_cm) or {}).get("production_order") or {})["total_cost"]), (_d.get("tannarx"), js(_cm)))
_r1, _r2, _r3 = mreja(A, PM), mreja(A, 99999999), mreja(A, ID["b_po"])
check("M4 yakunlangan — 409 (reja yo'q), yo'q id — 404, B korxonaniki — 404 (A uchun yo'q)",
      _r1.status_code == 409 and _r2.status_code == 404 and _r3.status_code == 404 and "yakunlangan" in str(detail(_r1)),
      (_r1.status_code, detail(_r1), _r2.status_code, _r3.status_code))
_r = so(B, "get", f"/api/production/orders/{PM}/preview")
check("M5 B korxona A ning ishlab chiqarishini ko'rmaydi — 404", _r.status_code == 404, _r.status_code)
# Bog'langan detal "kerak" miqdori kamaygan qoralama: reja xatosi = boshlash xabari (AYNAN)
PA, _ = po_yarat(A, {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 10, "source_type": "customer_order",
                     "source_order_item_id": ID["d_q"]})
PB, _ = po_yarat(A, {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 6, "source_type": "customer_order",
                     "source_order_item_id": ID["d_q"]})
_stb = so(A, "post", f"/api/production/orders/{PB}/start")
_ra = js(mreja(A, PA)) or {}
_sta = so(A, "post", f"/api/production/orders/{PA}/start")
check("M6 detal 10 dan 6 tasi boshqa ishlab chiqarishga band: qoralama rejasi mumkin EMAS, xato = boshlash 409 sababi (AYNAN)",
      lambda: _stb.status_code == 200 and _ra["mumkin"] is False and _sta.status_code == 409 and _ra["xatolar"] == [detail(_sta)],
      (_stb.status_code, _ra.get("xatolar"), _sta.status_code, detail(_sta)))

# ══════════════════════════════════════════════════════════════
section("L. Ro'yxat (GET /api/production/orders) — qo'shimcha maydonlar, davr, tartib, korxona")
# ══════════════════════════════════════════════════════════════
_la = royxatda(A, PA, oy="hammasi")
check("L1 mijoz buyurtmasi qatori: mahsulot nomi, birlik, retsept, buyurtma raqami, mijoz, detal, qoplamali",
      lambda: _la["mahsulot_nomi"] == "MRJ Travertin" and _la["birlik"] == "m²" and _la["retsept_nomi"] == "Standart"
      and _la["manba_buyurtma_raqami"] == ORD_RAQAM and _la["manba_mijoz"] == "MRJ Mijoz"
      and _la["manba_detal"] == "MRJ Travertin Q" and _la["manba_qoplamali"] is True
      and _la["ixtiyoriy_idlar"] == [ID["trav_qopl"]], _la)
check("L2 qoralama: taxminiy tannarx = reja tannarxi, xomashyo holati bor",
      lambda: yaqin(_la["taxminiy_tannarx"], _ra["tannarx"], 1e-6) and _la["xomashyo_holati"] in ("yetadi", "band_bilan_yetmaydi"),
      (_la.get("taxminiy_tannarx"), _ra.get("tannarx"), _la.get("xomashyo_holati")))
_lb = royxatda(A, PB, oy="hammasi")
_jb = js(mreja(A, PB)) or {}
_cmb = so(A, "post", f"/api/production/orders/{PB}/complete")
check("L3 jarayondagi: taxminiy tannarx = «Yakunlash» rejasi = yakunlangandagi tannarx; tayyor mahsulot id si bor",
      lambda: yaqin(_lb["taxminiy_tannarx"], _jb["tannarx"], 1e-6) and _lb["finished_product_id"]
      and yaqin(round(_lb["taxminiy_tannarx"], 2), ((js(_cmb) or {}).get("production_order") or {})["total_cost"]),
      (_lb.get("taxminiy_tannarx"), _jb.get("tannarx"), (js(_cmb) or {}).get("production_order", {}).get("total_cost")))
_lb = royxatda(A, PB, oy="hammasi")
check("L4 yakunlangan: tannarx bor, taxminiy yo'q, xomashyo holati yo'q", lambda: _lb["status"] == "completed"
      and _lb["total_cost"] and _lb["taxminiy_tannarx"] is None and _lb["xomashyo_holati"] is None, _lb)
PY, _ = po_yarat(A, {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 40, "source_type": "warehouse_stock"})
_ly = royxatda(A, PY, oy="hammasi")
check("L5 qoralama 40 m² (kley yetmaydi): holat «yetmaydi», yetmaydi = [kley], eng ko'pi = reja bilan bir xil",
      lambda: _ly["xomashyo_holati"] == "yetmaydi" and _ly["yetmaydi"] == ["MRJ Kley"]
      and yaqin(_ly["maks_bosh"], (js(mreja(A, PY)) or {})["maks_bosh"], 1e-9), _ly)
# Davr: Toshkent oyi chegarasi (UTC+5). Sanalar ORM orqali qo'yiladi (ilovadagi kabi — SQLite da matn shakli ham bir xil
# bo'lsin); o'tgan yil — boshqa yozuvlarga aralashmaydi.
DAVR = {}
for _k, _holat, _ustun, _vaqt in [("sen1", "completed", "completed_at", datetime.datetime(2025, 2, 28, 19, 30)),   # 01.03 00:30
                                  ("fev", "completed", "completed_at", datetime.datetime(2025, 2, 28, 18, 59)),    # 28.02 23:59
                                  ("sen2", "cancelled", "cancelled_at", datetime.datetime(2025, 3, 31, 18, 59, 59)),  # 31.03 23:59:59
                                  ("apr", "cancelled", "cancelled_at", datetime.datetime(2025, 3, 31, 19, 0))]:     # 01.04 00:00
    _pid, _ = po_yarat(A, {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 1, "source_type": "warehouse_stock"})
    _s = SessionLocal()
    try:
        _po = _s.get(ProductionOrder, _pid)
        _po.status = _holat
        setattr(_po, _ustun, _vaqt)
        _s.commit()
    finally:
        _s.close()
    DAVR[_k] = _pid
_mar = [x.get("id") for x in royxat(A, oy="2025-03")]
_fevr = [x.get("id") for x in royxat(A, oy="2025-02")]
_ochiq = [x.get("id") for x in royxat(A, oy="hammasi") if x.get("status") in ("draft", "in_progress")]
check("L6 ?oy=2025-03: 01.03 00:30 da yakunlangan va 31.03 23:59:59 da bekor qilingan BOR; 28.02 23:59 va 01.04 00:00 YO'Q",
      lambda: DAVR["sen1"] in _mar and DAVR["sen2"] in _mar and DAVR["fev"] not in _mar and DAVR["apr"] not in _mar, (DAVR, _mar))
check("L7 ?oy=2025-02: faqat 28.02 23:59 dagisi; ochiq (qoralama / jarayondagi) ishlab chiqarishlar HAR oyda ko'rinadi",
      lambda: DAVR["fev"] in _fevr and DAVR["sen1"] not in _fevr and _ochiq and set(_ochiq) <= set(_fevr) and set(_ochiq) <= set(_mar),
      (_fevr, _ochiq))
_hammasi = royxat(A, oy="hammasi")
_param_siz = royxat(A)
check("L8 ?oy=hammasi va parametrsiz — hammasi (avvalgidek), bir xil", lambda: [x["id"] for x in _hammasi] == [x["id"] for x in _param_siz]
      and all(v in [x["id"] for x in _hammasi] for v in DAVR.values()), len(_hammasi))
_r1, _r2 = so(A, "get", "/api/production/orders", params={"oy": "2025-13"}), so(A, "get", "/api/production/orders", params={"oy": "mart"})
check("L9 noto'g'ri davr — 400, o'zbekcha sabab", _r1.status_code == 400 and _r2.status_code == 400
      and "YYYY-MM" in str(detail(_r1)), (_r1.status_code, detail(_r1), _r2.status_code))


def _vaqt(x):
    return datetime.datetime.fromisoformat(str(x.get("created_at")).replace("Z", ""))


check("L10 tartib: yaratilgan vaqti bo'yicha kamayuvchi (teng bo'lsa id kamayuvchi)",
      lambda: [x["id"] for x in _hammasi] == [x["id"] for x in sorted(_hammasi, key=lambda x: (_vaqt(x), x["id"]), reverse=True)],
      [(x["id"], x["created_at"]) for x in _hammasi][:6])
_dr = royxat(A, status="draft", oy="hammasi")
check("L11 ?status=draft — faqat qoralamalar", lambda: _dr and all(x["status"] == "draft" for x in _dr), [x.get("status") for x in _dr])
_bl = royxat(B, oy="hammasi")
check("L12 B korxona ro'yxati — faqat o'ziniki (A ning birorta ishlab chiqarishi yo'q), qo'shimcha maydonlari to'g'ri",
      lambda: [x["id"] for x in _bl] == [ID["b_po"]] and _bl[0]["mahsulot_nomi"] == "MRJ B Travertin"
      and _bl[0]["xomashyo_holati"] == "yetadi" and yaqin(_bl[0]["taxminiy_tannarx"], 3 * 2 * 500), _bl)
check("L13 menejer ro'yxatni ko'radi (200)", so(MN, "get", "/api/production/orders").status_code == 200)

# ══════════════════════════════════════════════════════════════
section("Q. So'rovlar soni ro'yxat uzunligiga bog'liq emas")
# ══════════════════════════════════════════════════════════════


def sorov_soni():
    SANOQ[0] = 0
    r = so(A, "get", "/api/production/orders", params={"oy": "hammasi"})
    return SANOQ[0], len(js(r) or [])


_n1, _q1 = sorov_soni()
# +12 ta: qoralama (3 xil retsept, detal bilan ham), jarayondagi (yangi va ESKI surat — xarajat kalitlarisiz), yakunlangan
_yangi = []
for _i in range(3):
    _yangi.append(po_yarat(A, {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 1 + _i,
                               "source_type": "warehouse_stock"})[0])
    _yangi.append(po_yarat(A, {"product_type_id": ID["kqop"], "bom_id": ID["kqop_b"], "quantity": 1,
                               "source_type": "warehouse_stock"})[0])
    _yangi.append(po_yarat(A, {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 1,
                               "source_type": "customer_order", "source_order_item_id": ID["d_oddiy"]})[0])
for _pid in _yangi[3:9]:
    so(A, "post", f"/api/production/orders/{_pid}/start")
_s = SessionLocal()
try:
    for _pid in _yangi[3:6]:
        _po = _s.get(ProductionOrder, _pid)
        _sur = json.loads(_po.recipe_snapshot_json or "[]")
        for _l in _sur:
            _l.pop("fixed_cost_per_unit", None)
            _l.pop("percentage_cost", None)
        _po.recipe_snapshot_json = json.dumps(_sur)
    _s.commit()
finally:
    _s.close()
_n2, _q2 = sorov_soni()
check(f"Q1 {_q1} → {_q2} qator: so'rovlar soni o'zgarmadi ({_n1} = {_n2})", _q2 >= _q1 + 9 and _n1 == _n2, (_n1, _n2, _q1, _q2))
_eski = royxatda(A, _yangi[3], oy="hammasi")
_eski_r = js(mreja(A, _yangi[3])) or {}
check("Q2 eski surat (xarajat kalitlarisiz) — taxminiy tannarx joriy retsept xarajati bilan (yakunlash rejasi bilan bir xil)",
      lambda: yaqin(_eski["taxminiy_tannarx"], _eski_r["tannarx"], 1e-6), (_eski.get("taxminiy_tannarx"), _eski_r.get("tannarx")))

# ══════════════════════════════════════════════════════════════
section("X. Xabarlar — o'zbekcha holat nomlari (inglizcha texnik so'z yo'q)")
# ══════════════════════════════════════════════════════════════
_r = so(A, "post", f"/api/production/orders/{PM}/start")
check("X1 yakunlanganni boshlash — «Faqat qoralamani boshlash mumkin — bu ishlab chiqarish yakunlangan»",
      detail(_r) == "Faqat qoralamani boshlash mumkin — bu ishlab chiqarish yakunlangan", detail(_r))
_r = so(A, "post", f"/api/production/orders/{PY}/complete")
check("X2 qoralamani yakunlash — «Faqat jarayondagi ishlab chiqarishni yakunlash mumkin — bu ishlab chiqarish qoralama»",
      detail(_r) == "Faqat jarayondagi ishlab chiqarishni yakunlash mumkin — bu ishlab chiqarish qoralama", detail(_r))
_r = so(A, "post", f"/api/production/orders/{PM}/cancel")
check("X3 yakunlanganni bekor qilish — «Bu ishlab chiqarish yakunlangan — uni bekor qilib bo'lmaydi»",
      detail(_r) == "Bu ishlab chiqarish yakunlangan — uni bekor qilib bo'lmaydi", detail(_r))
ombor_qoy(ID["kley"], 36)
_pid, _ = po_yarat(A, {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 40, "source_type": "warehouse_stock"})
_r = so(A, "post", f"/api/production/orders/{_pid}/start")
check("X4 ombor yetmaydi — miqdorlar o'qiladigan shaklda: «kerak: 44 kg, bor: 36 kg»",
      detail(_r) == "Omborda yetarli 'MRJ Kley' yo'q (kerak: 44 kg, bor: 36 kg)", detail(_r))
so(A, "delete", f"/api/production/boms/{ID['kqop_b']}")
_, _r = po_yarat(A, {"product_type_id": ID["kqop"], "bom_id": ID["kqop_b"], "quantity": 1, "source_type": "warehouse_stock"})
check("X5 yashirilgan retsept — «Tanlangan retsept topilmadi yoki yashirilgan»",
      detail(_r) == "Tanlangan retsept topilmadi yoki yashirilgan", detail(_r))
_, _r = po_yarat(A, {"product_type_id": ID["trav"], "bom_id": ID["trav_b"], "quantity": 1, "source_type": "customer_order"})
check("X6 mijoz buyurtmasiga, detal tanlanmagan — «… buyurtma detalini tanlang»",
      detail(_r) == "Mijoz buyurtmasi asosida ishlab chiqarish uchun buyurtma detalini tanlang", detail(_r))
_fn = getattr(production_service, "_miqdor_matn", None)
check("X7 miqdor ko'rinishi: 44.00000000000001 → 44, 1234.5 → 1 234,5, 0.0125 → 0,0125, 3.3000000000000003 → 3,3",
      lambda: [_fn(x) for x in (44.00000000000001, 1234.5, 0.0125, 3.3000000000000003, -2.5)] == ["44", "1 234,5", "0,0125", "3,3", "-2,5"],
      [_fn(x) for x in (44.00000000000001, 1234.5, 0.0125)] if _fn else None)

# ══════════════════════════════════════════════════════════════
section("N. Reja va retsept hisobi HECH NARSA yozmaydi")
# ══════════════════════════════════════════════════════════════
_JADVALLAR = ["production_orders", "boms", "bom_items", "finished_products", "inventory_movements", "activity_logs"]


def holat_surati():
    natija = {}
    for t in _JADVALLAR:
        v = sql(f"SELECT COUNT(*) FROM {t}")
        natija[t] = v[0][0] if isinstance(v, list) and v else v
    v = sql("SELECT SUM(stock_quantity) FROM inventory")
    natija["ombor"] = round(float(v[0][0] or 0), 9) if isinstance(v, list) and v else v
    return natija


_oldin = holat_surati()
for _ in range(2):
    so(A, "post", "/api/production/boms/preview", json=BOM_TANA)
    reja(A, product_type_id=ID["trav"], bom_id=ID["trav_b"], quantity=5, source_type="customer_order", source_order_item_id=ID["d_q"])
    mreja(A, PY)
    mreja(A, _yangi[4])
    royxat(A, oy="hammasi")
_keyin = holat_surati()
check("N1 retsept hisobi, yangi / mavjud reja, ro'yxat — jadvallar (ishlab chiqarish, retsept, tayyor mahsulot, harakat, "
      "jurnal) va ombor qoldig'i o'zgarmadi", _oldin == _keyin and "XATO" not in str(_oldin), (_oldin, _keyin))

# ══════════════════════════════════════════════════════════════
section("P. Sahifa")
# ══════════════════════════════════════════════════════════════
_r = so(A, "get", "/production")
_bugun = database.tashkent_date()
check("P1 /production — davr tanlovining standart oyi SERVER Toshkent oyidan (data-joriy-oy)",
      _r.status_code == 200 and f'data-joriy-oy="{_bugun.year:04d}-{_bugun.month:02d}"' in getattr(_r, "text", ""), _r.status_code)
_html = open(os.path.join(ROOT, "templates", "production.html"), encoding="utf-8").read()
check("P2 holat nomlari o'zbekcha (Qoralama / Jarayonda / Yakunlandi / Bekor qilindi) va ro'yxatda holat kodi matn bo'lib chiqmaydi",
      "const HOLAT_NOMI = {draft: 'Qoralama', in_progress: 'Jarayonda', completed: 'Yakunlandi', cancelled: 'Bekor qilindi'};" in _html
      and "${po.status}</span>" not in _html and "${escapeHtml(po.status)}</span>" not in _html)
check("P3 inglizcha texnik yorliqlar yo'q (BOM, Komponent, Manba, Versiya, buyurtma-detali ro'yxat sarlavhasida)",
      all(x not in _html for x in (">Retsept versiyasi<", "Retsept (BOM)", "+ Komponent", ">Manba<", "Versiya nomi",
                                   "Ishlab chiqarish boshlandi — band qilingan xomashyo")))

# ══════════════════════════════════════════════════════════════
section("S. Statik — bitta qoida (reja va amal bir funksiyalardan)")
# ══════════════════════════════════════════════════════════════
_st = manba(production_service, "start_production_order")
_cm = manba(production_service, "complete_production_order")
_rh = manba(production_service, "_reja_hisobi")
check("S1 boshlash: surat `_surat_qatorlari`, solishtirish `_yetmaydimi`, ketma-ket qoldiq `_qoldiq_keyin` (K113-2)",
      tartibda(_st, "_surat_qatorlari(bom, po.quantity, selected_optional_ids)", "available = _qoldiq_k113.get(inv.id, _ombor)",
               "if _yetmaydimi(available, needed):", "_qoldiq_k113[inv.id] = _qoldiq_keyin(available, needed)"))
check("S2 yakunlash: `_yetmaydimi` va `_qoldiq_keyin` (K113-1 — aniq 0)",
      "_yetmaydimi(available, needed) and not allow_negative" in _cm and "inv.stock_quantity = _qoldiq_keyin(available, needed)" in _cm)
check("S3 reja: `_yetmaydimi`, `_qoldiq_keyin`, `_qoshimcha_xarajat`, `_tannarx_sigimi_xatosi` — amal bilan bir funksiyalar",
      all(x in _rh for x in ("_yetmaydimi(bu_qatorga, kerak)", "_qoldiq_keyin(bu_qatorga, kerak)", "_qoshimcha_xarajat(",
                             "_tannarx_sigimi_xatosi(")))
check("S4 yaratish va yangi reja — `_yaratish_tekshiruvi`; yangi reja tanasi — yaratish tanasi kabi (`_tana(\"ProductionOrder\"`)",
      "_yaratish_tekshiruvi(" in manba(production_service, "create_production_order")
      and "_yaratish_tekshiruvi(" in manba(production_service, "ishlab_chiqarish_rejasi")
      and '_tana("ProductionOrder"' in manba(production_routes, "preview_production_order"))
check("S5 retsept hisobi — `_compute_bom_line` va `_qoshimcha_xarajat` (ishlab chiqarish suratidagi hisob)",
      "_compute_bom_line(" in manba(production_service, "retsept_tannarxi")
      and "_qoshimcha_xarajat(" in manba(production_service, "retsept_tannarxi"))
check("S6 hech bir so'rov 500 bermadi", not XATO5, XATO5)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
