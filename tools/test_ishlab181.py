#!/usr/bin/env python3
"""
test_ishlab181.py — kech144 (zip 181, AUDIT 2-to'lqin — «Ishlab chiqarish»; `work/k180_tayyorgarlik/agentlar/ishlab/HISOBOT.md`):
takror so'rov ikkinchi tur / tarkib / ishlab chiqarish yaratmaydi, kech javob boshqa oynaga tushmaydi, ruxsatsiz tugmalar yo'q, narx
siri, yuklovchilar sababni ko'rsatadi. SERVER (TestClient) + HAQIQIY Chromium, HAQIQIY lokal server.

NIMA UCHUN KERAK (asl kod = zip 180):
  A1  «Yangi mahsulot turi» / «Mahsulot tarkibi» — ikki marta bosish ikki yozuv (PostgreSQL da parallel nom tekshiruvi ham o'tardi).
  A2  Yangi ishlab chiqarish — 502 dan keyin qayta bosish №42; «Boshlash» 502 — «boshlanmadi: xomashyo yetmadi» (yolg'on) va qayta bosish 409.
  B1  «Tahrirlash» ikki marta — 8 qator (saqlansa har xomashyo ikki baravar); boshqa turning «+ Tarkib» i ustiga eski tarkib.
  B2  Miqdor «3.0999999999999996».   C1  Kech kelgan №5 rejasi №7 oynasiga tushib, «Yakunlash» №5 ni yakunlardi.
  C2  Ko'rish roli «Boshlash» / «Yakunlash» / bekor qilish / «+ Tarkib» / tarkib «Tahrirlash» / 🗑 / «Yo'nalish» ni ko'rardi (403).
  C3  Narx ruxsati yo'q rol xomashyo narxini ko'rardi (retsept / reja `narx`, surat `unit_price_at_time`).
  C4  Yuklovchilar: turlar 502 — bo'sh korxonaning «4 qadam» oynasi; detallar — «kutilayotgan buyurtma yo'q»; ro'yxat xatosida «0 ta».
  C6  Taxminiy tannarx xatosi — xabarsiz.   C7  Ixtiyoriy tarkib belgisi jimgina olinardi.
  D1 / D2  Tarmoq / 5xx — jim yoki «saqlanmadi» (yolg'on).   D3  «'quantity' juda katta».   D4  «1 m2 tannarxi».
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (A1 parallel nom — faqat PG). Asl kodga (zip 180) qarshi QULAMAYDI —
yiqiladi. TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_ishlab181.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "ishlab181_test"
_T = tempfile.mkdtemp(prefix="is181_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'is181.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol             # noqa: E402
from production_models import ProductType, BOM, ProductionOrder   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


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


def rol_qoy(login, ruxsat, nom):
    def f(s):
        u = s.query(User).filter(User.username == login).first()
        r = Rol(company_id=u.company_id, nom=nom, kod=None, ruxsatlar=json.dumps(ruxsat), tavsif="")
        s.add(r)
        s.flush()
        u.rol_id = r.id
        return r.id
    return db_ishi(f)


def soni(model, **f):
    return db_ishi(lambda s: s.query(model).filter_by(**f).count())


def holat(pid):
    return db_ishi(lambda s: (s.get(ProductionOrder, pid).status.value if hasattr(s.get(ProductionOrder, pid).status, "value")
                              else str(s.get(ProductionOrder, pid).status)) if s.get(ProductionOrder, pid) else None)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "i181_admin", PAROL, UserRole.ADMIN, "I181 Admin", company_id=1)
    for _u in ("i181_kor", "i181_nar"):
        auth.create_user(s, _u, PAROL, UserRole.MANAGER, _u.upper(), company_id=1)
s.close()
# «Ko'rish» roli (C2) va narx ruxsatisiz ishlab chiqaruvchi (C3: tur va ishlab chiqarish — hammasi, «Xomashyo narxlari» / «Tannarx» — yo'q)
rol_qoy("i181_kor", {"mahsulot_turi": ["korish"], "ishlab_buyurtma": ["korish"], "material": ["korish"]}, "I181 Ko'ruvchi")
rol_qoy("i181_nar", {"mahsulot_turi": ["korish", "yaratish", "tahrirlash"], "ishlab_buyurtma": ["korish", "yaratish", "tahrirlash"],
                     "material": ["korish"]}, "I181 Narxsiz")


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


C = mijoz("i181_admin")
CN = mijoz("i181_nar")


def mat(nom, unit, stock, price):
    r = C.post("/api/inventory", json={"item_name": nom, "unit": unit, "category": "Kimyoviy qo'shimchalar", "stock_quantity": stock,
                                       "price_per_unit": price, "min_stock": 0})
    assert r.status_code == 200, r.text
    return js(r)["id"]


def tur(nom, unit="m²", kalit=None, c=None):
    return (c or C).post("/api/production/product-types", json={"name": nom, "unit": unit, "input_template": "quantity_only",
                                                                 "pricing_formula": "unit_based"},
                         headers={"X-Amal-Kaliti": kalit} if kalit else {})


def tarkib(pt, qatorlar, nom="Standart", kalit=None, c=None):
    return (c or C).post("/api/production/boms", json={"product_type_id": pt, "variant_name": nom, "batch_quantity": 1,
                                                       "items": qatorlar}, headers={"X-Amal-Kaliti": kalit} if kalit else {})


def ishlab(pt, bom, miqdor, kalit=None, c=None):
    return (c or C).post("/api/production/orders", json={"product_type_id": pt, "bom_id": bom, "quantity": miqdor,
                                                         "source_type": "warehouse_stock"},
                         headers={"X-Amal-Kaliti": kalit} if kalit else {})


def amal(pid, nima, kalit=None, c=None):
    return (c or C).post(f"/api/production/orders/{pid}/{nima}", headers={"X-Amal-Kaliti": kalit} if kalit else {})


M_QUM, M_KLEY, M_BOYOQ = mat("I181 Qum", "kg", 1000, 820), mat("I181 Kley", "kg", 500, 3150), mat("I181 Bo'yoq", "kg", 200, 24000)
PT_A = js(tur("I181 Travertin", unit="m2"))["id"]          # «m2» — sahifa «m²» deb ko'rsatishi kerak (D4)
B_A = js(tarkib(PT_A, [{"inventory_id": M_QUM, "quantity": 5}, {"inventory_id": M_KLEY, "quantity": 1, "scrap_factor_percent": 10},
                       {"inventory_id": M_BOYOQ, "quantity": 0.15, "is_optional": True}]))["id"]
PT_B = js(tur("I181 Dekor", unit="dona"))["id"]

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Server — amal kaliti, narx siri, maydon nomlari (A1, A2, C3, D3)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_n0 = soni(ProductType, name="I181 Ikki")
_r1, _r1b = tur("I181 Ikki", kalit="i181turkalit00001"), tur("I181 Ikki", kalit="i181turkalit00001")
check("S1 (A1) mahsulot turi — o'sha kalit: ikkinchisi 200 (`X-Takror: 1`, o'sha id), tur BITTA (ilgari ikkinchisi 400 «allaqachon bor»)",
      _r1.status_code == 200 and _r1b.status_code == 200 and _r1b.headers.get("x-takror") == "1"
      and js(_r1b).get("id") == js(_r1).get("id") and soni(ProductType, name="I181 Ikki") == _n0 + 1,
      (_r1.status_code, _r1b.status_code, js(_r1b), dict(_r1b.headers)))
_n0 = soni(BOM, product_type_id=PT_B)
_r2 = tarkib(PT_B, [{"inventory_id": M_QUM, "quantity": 2}], kalit="i181bomkalit00001")
_r2b = tarkib(PT_B, [{"inventory_id": M_QUM, "quantity": 2}], kalit="i181bomkalit00001")
check("S2 (A1) tarkib — o'sha kalit: tarkib BITTA, ikkinchi javob — o'sha id",
      _r2.status_code == 200 and _r2b.status_code == 200 and js(_r2b).get("id") == js(_r2).get("id")
      and soni(BOM, product_type_id=PT_B) == _n0 + 1, (_r2.status_code, _r2b.status_code, js(_r2b)))
B_B = js(_r2).get("id")
_n0 = soni(ProductionOrder, product_type_id=PT_A)
_r3 = ishlab(PT_A, B_A, 2, kalit="i181pokalit000001")
_r3b = ishlab(PT_A, B_A, 2, kalit="i181pokalit000001")
P3 = (js(_r3).get("production_order") or {}).get("id")
check("S3 (A2) yangi ishlab chiqarish — o'sha kalit: BITTA, ikkinchi javob `takror`, o'sha №",
      _r3.status_code == 200 and js(_r3b).get("takror") is True and (js(_r3b).get("production_order") or {}).get("id") == P3
      and soni(ProductionOrder, product_type_id=PT_A) == _n0 + 1, (js(_r3b), soni(ProductionOrder, product_type_id=PT_A) - _n0))
_r4, _r4b = amal(P3, "start", "i181boshkalit0001"), amal(P3, "start", "i181boshkalit0001")
check("S4 (A2) «Boshlash» — o'sha kalit bilan qayta: 200 `takror` (ilgari 409 «allaqachon boshlangan»)",
      _r4.status_code == 200 and _r4b.status_code == 200 and js(_r4b).get("takror") is True and holat(P3) == "in_progress",
      (_r4.status_code, _r4b.status_code, js(_r4b), holat(P3)))
_r5, _r5b = amal(P3, "complete", "i181yakunkalit001"), amal(P3, "complete", "i181yakunkalit001")
check("S5 (A2) «Yakunlash» — o'sha kalit bilan qayta: 200 `takror`, yakunlangan",
      _r5.status_code == 200 and _r5b.status_code == 200 and js(_r5b).get("takror") is True and holat(P3) == "completed",
      (_r5.status_code, _r5b.status_code, js(_r5b)))
P6 = (js(ishlab(PT_A, B_A, 1)).get("production_order") or {}).get("id")
_r6, _r6b = amal(P6, "cancel", "i181bekorkalit001"), amal(P6, "cancel", "i181bekorkalit001")
check("S6 (A2) «Bekor qilish» — o'sha kalit bilan qayta: 200 `takror`",
      _r6.status_code == 200 and _r6b.status_code == 200 and js(_r6b).get("takror") is True and holat(P6) == "cancelled",
      (_r6.status_code, _r6b.status_code, js(_r6b)))
_r6c = amal(P6, "cancel")
check("S6b NAZORAT: kalitsiz qayta bekor qilish — 409 (holat tekshiruvi o'zgarmagan)", _r6c.status_code == 409, _r6c.status_code)

_tana = {"product_type_id": PT_A, "variant_name": "Hisob", "batch_quantity": 1, "notes": None,
         "items": [{"inventory_id": M_QUM, "quantity": 5}]}
_p7a, _p7n = js(C.post("/api/production/boms/preview", json=_tana)), js(CN.post("/api/production/boms/preview", json=_tana))
check("S7 (C3) retsept hisobi: admin — narx bor (NAZORAT); narx ruxsatisiz — `qatorlar[].narx` null",
      ((_p7a.get("qatorlar") or [{}])[0]).get("narx") not in (None, 0) and "narx" in ((_p7n.get("qatorlar") or [{}])[0])
      and ((_p7n.get("qatorlar") or [{}])[0]).get("narx") is None, (_p7a.get("qatorlar"), _p7n.get("qatorlar")))
_qs = {"product_type_id": PT_A, "bom_id": B_A, "quantity": 2, "source_type": "warehouse_stock"}
_p8n = js(CN.get("/api/production/orders/preview", params=_qs))
P8 = (js(ishlab(PT_A, B_A, 1)).get("production_order") or {}).get("id")
_p8e = js(CN.get(f"/api/production/orders/{P8}/preview"))
check("S8 (C3) reja (yangi va mavjud ishlab chiqarish): narx ruxsatisiz — `qatorlar[].narx` null",
      all("narx" in q and q.get("narx") is None for q in (_p8n.get("qatorlar") or [])) and (_p8n.get("qatorlar") or [])
      and all(q.get("narx") is None for q in (_p8e.get("qatorlar") or [])), (_p8n.get("qatorlar"), _p8e.get("qatorlar")))
_l9 = [p for p in (js(CN.get("/api/production/orders", params={"oy": "hammasi"})) or []) if p.get("id") == P3]
_s9 = (_l9[0].get("recipe_snapshot") if _l9 else None) or []
_l9a = [p for p in (js(C.get("/api/production/orders", params={"oy": "hammasi"})) or []) if p.get("id") == P3]
check("S9 (C3) ro'yxat: narx ruxsatisiz — tarkib suratidagi «Narx (o'sha kuni)» null; admin — bor (NAZORAT)",
      _s9 and all(x.get("unit_price_at_time") is None for x in _s9)
      and any(x.get("unit_price_at_time") for x in ((_l9a[0].get("recipe_snapshot") if _l9a else None) or [])), (_s9[:2], _l9a[:1]))
_r10 = ishlab(PT_A, B_A, 1, c=CN)
_p10 = (js(_r10).get("production_order") or {}).get("id")
_r10s = amal(_p10, "start", c=CN)
check("S10 (C3) yaratish / boshlash javobi: narx ruxsatisiz — surat narxi null",
      _r10.status_code == 200 and _r10s.status_code == 200
      and all(x.get("unit_price_at_time") is None for x in ((js(_r10s).get("production_order") or {}).get("recipe_snapshot") or [{}])),
      (js(_r10s).get("production_order") or {}).get("recipe_snapshot"))
amal(_p10, "cancel")
_d11 = str(js(C.post("/api/production/product-types", json={"name": "I181 Katta", "unit": "kg", "input_template": "quantity_only",
                                                            "pricing_formula": "fixed_price", "fixed_unit_price": 1e20})).get("detail"))
_d11b = str(js(tarkib(PT_A, [{"inventory_id": M_QUM, "quantity": 1}, {"inventory_id": 999999, "quantity": 1}], nom="I181 Begona")).get("detail"))
check("S11 (D3) server xabari — maydon nomi o'zbekcha («Qat'iy narx», «Tarkib 2-qator»; ilgari «'fixed_unit_price'», «'items'»)",
      "Qat'iy narx" in _d11 and "'fixed_unit_price'" not in _d11 and _d11b == "Tarkib 2-qator: material topilmadi", (_d11, _d11b))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Egasi qarori 14.10 — tannarx: «Yakunlash narxi + farq»")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
M_TK = mat("I181 Kley T", "kg", 100, 1000)
PT_T = js(tur("I181 Kley mahsulot", unit="qop"))["id"]
B_T = js(tarkib(PT_T, [{"inventory_id": M_TK, "quantity": 1}]))["id"]


def _pul(x):
    return None if x is None else round(float(x), 2)


P_T = (js(ishlab(PT_T, B_T, 30)).get("production_order") or {}).get("id")
amal(P_T, "start")
_rk = C.post(f"/api/inventory/{M_TK}/purchase", json={"quantity": 100, "price_per_unit": 2000, "paid_now": 0, "notes": "I181 qimmat"})
_rt = js(C.get(f"/api/production/orders/{P_T}/preview"))
check("T1 «Yakunlash» rejasi — BUGUNGI narx (o'rtacha 1 500): tannarx 45 000, Boshlashdagi taxmin 30 000, farq +15 000",
      _rk.status_code == 200 and _pul(_rt.get("tannarx")) == 45000 and _pul(_rt.get("boshlash_tannarx")) == 30000
      and _pul(_rt.get("tannarx_farqi")) == 15000 and _pul((_rt.get("qatorlar") or [{}])[0].get("narx")) == 1500
      and _pul((_rt.get("qatorlar") or [{}])[0].get("boshlash_narxi")) == 1000, (_rk.status_code, {k: _rt.get(k) for k in (
          "tannarx", "boshlash_tannarx", "tannarx_farqi")}, (_rt.get("qatorlar") or [{}])[0]))
_rtn = js(CN.get(f"/api/production/orders/{P_T}/preview"))
check("T2 narx / tannarx ruxsatisiz — Boshlashdagi narx, taxmin va farq ham yashirin (null)",
      _rtn.get("boshlash_tannarx") is None and _rtn.get("tannarx_farqi") is None
      and all(q.get("boshlash_narxi") is None for q in (_rtn.get("qatorlar") or [{}])), {k: _rtn.get(k) for k in (
          "boshlash_tannarx", "tannarx_farqi", "tannarx")})
_l3 = [p for p in (js(C.get("/api/production/orders", params={"oy": "hammasi"})) or []) if p.get("id") == P_T]
check("T3 ro'yxatdagi «≈» (jarayondagi) — bugungi narx bilan (45 000)", _l3 and _pul(_l3[0].get("taxminiy_tannarx")) == 45000,
      _l3[0].get("taxminiy_tannarx") if _l3 else None)
_rc = amal(P_T, "complete")
_po = (js(_rc).get("production_order") or {})
_sn = (_po.get("recipe_snapshot") or [{}])[0]
check("T4 «Yakunlash» — tannarx 45 000 (yakunlash kunidagi narx; ilgari 30 000 — ombor qiymati 45 000 kamayib, 15 000 hech qayerda yo'q edi)",
      _rc.status_code == 200 and _pul(_po.get("total_material_cost")) == 45000 and _pul(_po.get("total_cost")) == 45000
      and _pul(_sn.get("unit_price_at_time")) == 1500 and _pul(_sn.get("boshlash_narxi")) == 1000 and _pul(_sn.get("boshlash_summa")) == 30000,
      (_rc.status_code, _po.get("total_cost"), _sn))
from models import ActivityLog as _AL181                  # noqa: E402
_jr = db_ishi(lambda d: [a.new_value for a in d.query(_AL181).filter(_AL181.action == "produced").order_by(_AL181.id.desc()).limit(3).all()])
check("T5 jurnal — «Boshlashdagi taxmin 30 000 so'm, farq +15 000 so'm»",
      any("Boshlashdagi taxmin 30 000" in (x or "") and "+15 000" in (x or "") for x in _jr), _jr)
P_T2 = (js(ishlab(PT_T, B_T, 10)).get("production_order") or {}).get("id")
amal(P_T2, "start")
_rc2 = amal(P_T2, "complete")
check("T6 NAZORAT: narx o'zgarmagan — tannarx Boshlashdagidek (10 × 1 500 = 15 000), farq yozilmaydi",
      _rc2.status_code == 200 and _pul((js(_rc2).get("production_order") or {}).get("total_cost")) == 15000, js(_rc2).get("production_order"))
P_TJ = (js(ishlab(PT_T, B_T, 10)).get("production_order") or {}).get("id")
amal(P_TJ, "start")
C.post(f"/api/inventory/{M_TK}/purchase", json={"quantity": 135, "price_per_unit": 3000, "paid_now": 0, "notes": "I181 yana qimmat"})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L. Egasi qarori 14.10 — savatdan loyiha tiklanganda buyurtmalari: «So'rasin»")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from models import Project as _Prj, Order as _Ord, Inventory as _Inv     # noqa: E402


def _loyiha_savatda(nom, n_buyurtma):
    """Loyiha + `n_buyurtma` ta qisman topshirilgan buyurtma (savatga tushadi — ish izi bor), so'ng hammasi savatga."""
    def _f(d):
        p = _Prj(company_id=1, client_name="I181 Mijoz", project_name=nom, total_budget=0, total_paid=0)
        d.add(p)
        d.flush()
        return p.id
    pid = db_ishi(_f)
    pen = db_ishi(lambda d: (lambda i: (d.add(i), d.flush(), i.id)[2])(_Inv(
        company_id=1, item_name=f"{nom} PENO", unit="blok", stock_quantity=100, min_stock=0, is_penoplast=True, volume_per_unit=1,
        price_per_unit=500000)))
    oidlar = []
    for i in range(n_buyurtma):
        r = C.post("/api/orders", json={"project_id": pid, "order_type": "product", "loy_kg": 0, "items": [
            {"name": f"{nom} detal {i}", "category": "panel", "width": 100, "thickness": 10, "quantity": 10, "unit_price": 1000,
             "is_coated": False, "penoplast_id": pen}]})
        o = js(r)
        oidlar.append(o.get("id"))
        C.post("/api/deliveries", json={"order_id": o.get("id"), "items": [{"order_item_id": (o.get("items") or [{}])[0].get("id"),
                                                                         "quantity": 2}], "received_by": None, "notes": None,
                                        "transport_carrier": None, "transport_cost": 0, "transport_payer": "none",
                                        "payment_amount": None, "payment_method": "naqd"})
    for o in oidlar:
        C.delete(f"/api/orders/{o}")
    C.delete(f"/api/projects/{pid}")
    return pid, oidlar


def _ochirilgan(model, i):
    return db_ishi(lambda d: (bool(d.get(model, i).is_deleted) if d.get(model, i) is not None else "yo'q"))


LA, LA_O = _loyiha_savatda("I181 Loyiha A", 2)
_rl = C.post(f"/api/projects/{LA}/restore")
_dl = js(_rl).get("detail") or {}
_raq = db_ishi(lambda d: [d.get(_Ord, o).order_number for o in LA_O])
check("L1 (So'rasin) loyiha savatda, 2 ta buyurtmasi ham — tanlovsiz 409 `project_has_deleted_orders` (raqamlari bilan), HECH NARSA tiklanmadi",
      _ochirilgan(_Prj, LA) is True and all(_ochirilgan(_Ord, o) is True for o in LA_O) and _rl.status_code == 409
      and isinstance(_dl, dict) and _dl.get("type") == "project_has_deleted_orders" and _dl.get("soni") == 2
      and all(r in str(_dl.get("message")) for r in _raq), (_rl.status_code, _dl, _raq))
_rl2 = C.post(f"/api/projects/{LA}/restore?buyurtmalar=yoq")
check("L2 `buyurtmalar=yoq` — faqat loyiha tiklandi, buyurtmalar savatda qoldi",
      _rl2.status_code == 200 and _ochirilgan(_Prj, LA) is False and all(_ochirilgan(_Ord, o) is True for o in LA_O), js(_rl2))
LB, LB_O = _loyiha_savatda("I181 Loyiha B", 2)
_rl3 = C.post(f"/api/projects/{LB}/restore?buyurtmalar=ha")
check("L3 `buyurtmalar=ha` — loyiha va 2 ta buyurtmasi tiklandi (javobda soni)",
      _rl3.status_code == 200 and js(_rl3).get("tiklangan_buyurtmalar") == 2 and _ochirilgan(_Prj, LB) is False
      and all(_ochirilgan(_Ord, o) is False for o in LB_O), (_rl3.status_code, js(_rl3), [_ochirilgan(_Ord, o) for o in LB_O]))
LC, _ = _loyiha_savatda("I181 Loyiha C", 0)
check("L4 noto'g'ri tanlov — 400; NAZORAT: savatda buyurtmasi yo'q loyiha — so'ralmaydi (200)",
      C.post(f"/api/projects/{LC}/restore?buyurtmalar=balki").status_code == 400
      and C.post(f"/api/projects/{LC}/restore").status_code == 200 and _ochirilgan(_Prj, LC) is False)
LD, LD_O = _loyiha_savatda("I181 Loyiha D", 1)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. kech146 — mustaqil tekshiruv (review181): sahifa izohlari, tiklangan buyurtmalar soni")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ph146 = re.sub(r"<!--.*?-->", "", open(os.path.join(ROOT, "templates", "production.html"), encoding="utf-8").read(), flags=re.S)
check("G1 (F1) «Ishlab chiqarish» oynalari izohi — narx «Yakunlash» kunidagi (egasi qarori 14.10); eski «narx Boshlash kunida qotadi» / "
      "«boshlangan ishlab chiqarishlar eski narxda qoladi» YO'Q",
      "tarkib narxi shu kunda qotadi" not in _ph146 and "ishlab chiqarishlar eski narxda qoladi" not in _ph146
      and "Ombordan yechish va tannarx — «Yakunlash» da" in _ph146 and "narx — yakunlash kunidagi" in _ph146,
      [x for x in ("tarkib narxi shu kunda qotadi", "ishlab chiqarishlar eski narxda qoladi") if x in _ph146])
LG, LG_O = _loyiha_savatda("I181 Loyiha G", 2)
_asl_ro = crud.restore_order


def _ro_bittasi_yoq(db, oid, *a, **k):
    if oid == LG_O[0]:
        return False                       # shu orada butunlay o'chirilgan buyurtma (topilmadi)
    return _asl_ro(db, oid, *a, **k)
crud.restore_order = _ro_bittasi_yoq
try:
    _rg = C.post(f"/api/projects/{LG}/restore?buyurtmalar=ha")
finally:
    crud.restore_order = _asl_ro
check("G2 (N1) loyiha tiklandi, 2 buyurtmadan biri shu orada yo'qolgan — `tiklangan_buyurtmalar` = 1 (ilgari ro'yxat uzunligi — 2)",
      _rg.status_code == 200 and js(_rg).get("tiklangan_buyurtmalar") == 1 and _ochirilgan(_Ord, LG_O[1]) is False,
      (_rg.status_code, js(_rg), _ochirilgan(_Ord, LG_O[1])))

if PG_URL:
    section("P. PostgreSQL — bir xil nomli tur parallel (A1)")
    _asl_log = crud.log_activity
    _hol = {"n": 0}
    _ql = threading.Lock()

    def _sekin_log(*a, **k):
        with _ql:
            _hol["n"] += 1
            birinchi = _hol["n"] == 1
        if birinchi:
            time.sleep(1.2)
        return _asl_log(*a, **k)
    C1, C2 = mijoz("i181_admin"), mijoz("i181_admin")
    _nat = [None, None]

    def _ish(i, c):
        try:
            _nat[i] = tur("I181 Parallel", c=c)
        except Exception as e:             # noqa: BLE001
            _nat[i] = e
    crud.log_activity = _sekin_log
    try:
        _t1 = threading.Thread(target=_ish, args=(0, C1))
        _t2 = threading.Thread(target=_ish, args=(1, C2))
        _t1.start()
        time.sleep(0.35)
        _t2.start()
        _t1.join(30)
        _t2.join(30)
    finally:
        crud.log_activity = _asl_log
    _k = sorted(getattr(x, "status_code", 0) for x in _nat)
    check("P1 (A1) ikki foydalanuvchi bir vaqtda «I181 Parallel»: biri 200, ikkinchisi 400 «allaqachon bor» (ilgari ikkalasi yozilardi)",
          _k == [200, 400] and soni(ProductType, name="I181 Parallel") == 1, (_k, soni(ProductType, name="I181 Parallel")))

    # kech146 (review181 F2): loyiha + buyurtmalari tiklash ∥ o'sha buyurtmani alohida tiklash — qulf tartibi bir (101 → loyiha)
    def _ikki(f1, f2):
        nat = [None, None]

        def ish(i, f):
            try:
                nat[i] = f()
            except Exception as e:         # noqa: BLE001
                nat[i] = e
        t1 = threading.Thread(target=ish, args=(0, f1))
        t2 = threading.Thread(target=ish, args=(1, f2))
        t1.start()
        time.sleep(0.35)
        t2.start()
        t1.join(40)
        t2.join(40)
        return [getattr(x, "status_code", f"{type(x).__name__}") for x in nat]
    LP2, LP2_O = _loyiha_savatda("I181 Loyiha P2", 2)
    _asl_pq = crud._pul_qulfi
    _hol2 = {"n": 0}

    def _sekin_101(db, ns, kalit):
        _asl_pq(db, ns, kalit)
        if ns == 101:
            with _ql:
                _hol2["n"] += 1
                birinchi = _hol2["n"] == 1
            if birinchi:
                time.sleep(1.5)
    crud._pul_qulfi = _sekin_101
    try:
        _k2 = _ikki(lambda: C1.post(f"/api/orders/{LP2_O[0]}/restore"),
                    lambda: C2.post(f"/api/projects/{LP2}/restore?buyurtmalar=ha"))
    finally:
        crud._pul_qulfi = _asl_pq
    check("P2 (F2) buyurtmani alohida tiklash (sekin) ∥ loyihani buyurtmalari bilan tiklash — 500 YO'Q (ilgari qulflar teskari tartibda: "
          "deadlock 40P01, biri «Serverda kutilmagan xato»); loyiha va o'sha buyurtma tiklangan",
          500 not in _k2 and 200 in _k2 and all(isinstance(x, int) for x in _k2) and _ochirilgan(_Prj, LP2) is False
          and _ochirilgan(_Ord, LP2_O[0]) is False, (_k2, _ochirilgan(_Prj, LP2), [_ochirilgan(_Ord, o) for o in LP2_O]))

    # kech146 (review181 F4): nomini o'zgartirish ∥ shu nom bilan yaratish — tahrir ham nom qulfi ostida
    _hol["n"] = 0
    _y3 = js(tur("I181 Eski nom", c=C1))["id"]
    crud.log_activity = _sekin_log
    try:
        _k3 = _ikki(lambda: tur("I181 RV X", c=C1),
                    lambda: C2.put(f"/api/production/product-types/{_y3}", json={"name": "I181 RV X", "unit": "m²",
                                                                                "input_template": "quantity_only",
                                                                                "pricing_formula": "unit_based"}))
    finally:
        crud.log_activity = _asl_log
    _faol3 = db_ishi(lambda d: d.query(ProductType).filter(ProductType.name == "I181 RV X", ProductType.is_active == True).count())  # noqa: E712
    check("P3 (F4) «I181 RV X» yaratish (sekin) ∥ boshqa turni «I181 RV X» ga o'zgartirish — biri 400 «allaqachon bor», faol «I181 RV X» — "
          "BITTA (ilgari ikkalasi 200 — ikkita bir xil nom)",
          sorted(_k3) == [200, 400] and _faol3 == 1, (_k3, _faol3))

    _hol["n"] = 0
    _y4 = js(tur("I181 Tarkib turi", c=C1))["id"]
    _b4 = js(tarkib(_y4, [{"inventory_id": M_QUM, "quantity": 1}], nom="Boshqa", c=C1))["id"]
    crud.log_activity = _sekin_log
    try:
        _k4 = _ikki(lambda: tarkib(_y4, [{"inventory_id": M_QUM, "quantity": 2}], nom="Standart", c=C1),
                    lambda: C2.put(f"/api/production/boms/{_b4}", json={"product_type_id": _y4, "variant_name": "Standart",
                                                                        "batch_quantity": 1,
                                                                        "items": [{"inventory_id": M_QUM, "quantity": 1}]}))
    finally:
        crud.log_activity = _asl_log
    _faol4 = db_ishi(lambda d: d.query(BOM).filter(BOM.product_type_id == _y4, BOM.variant_name == "Standart",
                                                   BOM.is_active == True).count())  # noqa: E712
    check("P4 (F4) «Standart» tarkib yaratish (sekin) ∥ «Boshqa» ni «Standart» ga o'zgartirish — biri 400, faol «Standart» — BITTA "
          "(ilgari ikkita «Standart»)",
          sorted(_k4) == [200, 400] and _faol4 == 1, (_k4, _faol4))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Brauzer
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


port = _port()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
B = f"http://127.0.0.1:{port}"
pw_ctx = br = None
if PW_BOR and server.started:
    pw_ctx = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                              "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        br = None
        _pw_x = f"{type(_e).__name__}: {_e}"
check("T0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO, SOROV = [], []


def kontekst(user="i181_admin", oldin=None):
    """`oldin` — sahifa ochilishidan OLDIN qo'yiladigan `route` lar: [(naqsh, ishlovchi), ...]."""
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""), q.headers.get("x-amal-kaliti")))
          if "/api/" in q.url else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    for naqsh, h in (oldin or []):
        ctx.route(naqsh, h)
    return ctx, pg


ILGAK = """() => { window.__msg = []; window.__ha = true;
  window.showMsg = (t, ty) => { window.__msg.push([String(t), ty || '']); };
  window.alert = (t) => { window.__msg.push([String(t), 'alert']); };
  window.xabarOyna = async (t) => { window.__msg.push([String(t), 'oyna']); };
  window.customConfirm = async () => window.__ha;
  window.open = () => null; }"""
SAHIFA_502 = {"status": 502, "content_type": "text/html", "body": "<html><body><h1>502 Bad Gateway</h1></body></html>"}
NOMALUM = "natijasi noma'lum"
TAKROR = "ikkinchi marta yozilmadi"
SERVER = "server javob bermadi"
UZILISH = "internet aloqasi yo'q"


def jsn(status, tana):
    return {"status": status, "content_type": "application/json", "body": json.dumps(tana)}


def ochiq(pg, yol, ilgak=True):
    pg.goto(B + yol, wait_until="networkidle")
    pg.wait_for_timeout(400)
    if ilgak:
        pg.evaluate(ILGAK)


def msg_matn(pg):
    try:
        return " || ".join(m[0] for m in (pg.evaluate("() => window.__msg || []") or []))
    except Exception:                      # noqa: BLE001
        return ""


def msg_tozala(pg):
    pg.evaluate("() => { window.__msg = []; }")


def matn(pg, sel):
    try:
        return pg.evaluate(f"() => {{ const e = document.querySelector({json.dumps(sel)}); return e ? e.textContent : null; }}")
    except Exception:                      # noqa: BLE001
        return None


def baj(pg, ifoda, arg=None, kutish=700):
    x = None
    try:
        x = pg.evaluate(ifoda, arg) if arg is not None else pg.evaluate(ifoda)
    except Exception as e:                 # noqa: BLE001
        x = "XATO: " + str(e)[:160]
    pg.wait_for_timeout(kutish)
    return x


def sorovlar(nima, usul="POST"):
    return [x for x in SOROV if nima in x[1] and x[0] == usul]


def korinadi(pg, sel):
    try:
        return pg.evaluate("""(s) => { const els = [...document.querySelectorAll(s)];
          els.forEach(e => { if (e.style && e.style.display === 'none') e.style.display = ''; });
          return els.filter(e => getComputedStyle(e).display !== 'none').length; }""", sel)
    except Exception:                      # noqa: BLE001
        return None


class Bajar502:
    """So'rov serverga YETADI va bajariladi (`route.fetch`), lekin brauzerga 502 HTML qaytadi (deploy almashinuvi)."""

    def __init__(self, faqat=None):
        self.holat = []
        self.faqat = faqat

    def __call__(self, route):
        if self.faqat and route.request.method != self.faqat:
            route.continue_()
            return
        try:
            j = route.fetch()
            self.holat.append(j.status)
        except Exception as e:             # noqa: BLE001
            self.holat.append(f"{type(e).__name__}")
        route.fulfill(**SAHIFA_502)


class Ushla:
    """Birinchi mos so'rov ushlab turiladi; `qoyib_yubor()` — serverning HAQIQIY javobi bilan (kech), qolganlari o'tadi."""

    def __init__(self):
        self.ushlangan = []

    def __call__(self, route):
        if not self.ushlangan:
            self.ushlangan.append(route)
            return
        route.continue_()

    def qoyib_yubor(self):
        for r in self.ushlangan:
            try:
                r.fulfill(response=r.fetch())
            except Exception:              # noqa: BLE001
                pass


if br:
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("U. «Ishlab chiqarish» sahifasi — yuklovchilar, tur va tarkib (A1, B1, C4, C6)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst(oldin=[("**/api/production/product-types/xulosa", lambda r: r.fulfill(**SAHIFA_502))])
    try:
        ochiq(pg, "/production")
        _l = matn(pg, "#pt-list") or ""
        baj(pg, "() => { openProductionOrderModal(); }", kutish=300)
        _m = msg_matn(pg)
        check("U1 (C4) mahsulot turlari 502 — sabab ro'yxat o'rnida (ilgari bo'sh korxonaning «4 qadam» oynasi)",
              "Mahsulot turlari yuklanmadi" in _l and SERVER in _l and "4 qadam" not in _l, _l[:300])
        check("U1b (C4) «Yangi ishlab chiqarish» — sabab (ilgari «Avval mahsulot turini qo'shing» — tur bor edi)",
              "Mahsulot turlari yuklanmadi" in _m and "Avval mahsulot turini" not in _m, _m)
    except Exception as _x:               # noqa: BLE001
        check("U1 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    ctx, pg = kontekst()
    try:
        ochiq(pg, "/production")
        _n0, _p0 = soni(ProductType, name="I181 Dubl"), len(sorovlar("/api/production/product-types"))
        baj(pg, """() => { openProductTypeModal(); document.getElementById('pt-f-name').value = 'I181 Dubl';
                           document.getElementById('pt-f-unit').value = 'kg';
                           const y = document.getElementById('pt-f-yonalish'); if (y && y.options.length > 1) y.value = y.options[1].value; }""",
            kutish=200)
        _yon = baj(pg, "() => document.getElementById('pt-f-yonalish').value", kutish=50)
        pg.dblclick("#pt-saqla-btn")
        pg.wait_for_timeout(1500)
        _yangi = [x for x in sorovlar("/api/production/product-types")[_p0:] if x[1].endswith("/product-types")]
        check("U2 (A1) «Saqlash» ikki marta bosildi — BITTA so'rov (kalit bilan), bitta tur",
              len(_yangi) == 1 and bool(_yangi[0][2]) and soni(ProductType, name="I181 Dubl") == _n0 + 1, (_yangi, _yon))

        _b = Bajar502(faqat="POST")
        pg.route(re.compile(r".*/api/production/product-types$"), _b)
        msg_tozala(pg)
        baj(pg, """() => { openProductTypeModal(); document.getElementById('pt-f-name').value = 'I181 Uzilgan';
                           document.getElementById('pt-f-unit').value = 'kg';
                           const y = document.getElementById('pt-f-yonalish'); if (y && y.options.length > 1) y.value = y.options[1].value;
                           return saveProductType(); }""", kutish=1000)
        _x1 = matn(pg, "#pt-xato") or ""
        pg.unroute(re.compile(r".*/api/production/product-types$"))
        msg_tozala(pg)
        baj(pg, "() => saveProductType()", kutish=1200)
        _m3 = (msg_matn(pg) or "") + " " + (matn(pg, "#pt-xato") or "")
        check("U3 (A1 / D2) yangi tur 502 — «natijasi noma'lum» (ilgari «Mahsulot turi saqlanmadi»); qayta — o'sha kalit, BITTA tur, "
              "«avvalroq bajarilgan» (server kaliti — nom tekshiruvining «allaqachon bor» i emas)",
              NOMALUM in _x1 and _b.holat == [200] and soni(ProductType, name="I181 Uzilgan") == 1
              and "avvalroq" in _m3 and "allaqachon" not in _m3,
              (_x1, _m3, _b.holat, soni(ProductType, name="I181 Uzilgan")))

        ochiq(pg, "/production")
        baj(pg, "(a) => { openBomModal(a[0], a[1]); openBomModal(a[0], a[1]); }", [PT_A, B_A], kutish=1500)
        _q = baj(pg, "() => document.getElementById('bom-items-wrap').children.length", kutish=50)
        check("U4 (B1) tarkib «Tahrirlash» ikki marta — qatorlar 3 ta (ilgari 6 — saqlansa har xomashyo ikki baravar)", _q == 3, _q)
        baj(pg, "() => closeModal('bom-modal')", kutish=100)

        _u = Ushla()
        pg.route(re.compile(rf".*/api/production/product-types/{PT_A}/boms.*"), _u)
        baj(pg, "(a) => { openBomModal(a[0], a[1]); }", [PT_A, B_A], kutish=400)
        baj(pg, "(a) => { openBomModal(a); }", PT_B, kutish=600)
        _u.qoyib_yubor()
        pg.wait_for_timeout(1200)
        _st = baj(pg, """() => [document.getElementById('bom-f-product-type-id').value, document.getElementById('bom-f-editing-id').value,
                               document.getElementById('bom-items-wrap').children.length, document.getElementById('bom-modal-title').textContent]""",
                  kutish=50)
        pg.unroute(re.compile(rf".*/api/production/product-types/{PT_A}/boms.*"))
        check("U5 (B1) Travertin tarkibi «Tahrirlash», so'ng Dekor «+ Tarkib», Travertin javobi KECH — oyna Dekorniki (yangi, 1 qator)",
              isinstance(_st, list) and _st[0] == str(PT_B) and _st[1] == "" and _st[2] == 1 and "Dekor" in (_st[3] or ""), _st)
        baj(pg, "() => closeModal('bom-modal')", kutish=100)

        pg.route("**/api/production/boms/preview", lambda r: r.fulfill(**jsn(400, {"detail": "Tarkib 1-qator: material topilmadi"})))
        baj(pg, "(a) => { openBomModal(a[0], a[1]); }", [PT_A, B_A], kutish=900)
        baj(pg, "() => retseptHisobi()", kutish=900)
        _og = matn(pg, "#bom-ogoh") or ""
        pg.unroute("**/api/production/boms/preview")
        check("U6 (C6) taxminiy tannarx rad etildi — sabab oynada (ilgari hamma narx «—», xabarsiz)",
              "Taxminiy tannarx hisoblanmadi" in _og and "material topilmadi" in _og, _og)
        baj(pg, "() => closeModal('bom-modal')", kutish=100)
    except Exception as _x:               # noqa: BLE001
        check("U2–U6 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("Y. Yangi ishlab chiqarish va oynalar (A2, B2, C1, C4, C7, D1, D4)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/production")
        _n0 = soni(ProductionOrder, product_type_id=PT_A)
        _b = Bajar502()
        pg.route(re.compile(r".*/api/production/orders$"), _b)
        baj(pg, """(a) => { openProductionOrderModal(); document.getElementById('po-f-product-type').value = String(a[0]);
                           return onProductTypeChangeForPO(); }""", [PT_A], kutish=900)
        baj(pg, "() => { document.getElementById('po-f-quantity').value = '3'; }", kutish=100)
        msg_tozala(pg)
        baj(pg, "() => poQoralamaSaqla()", kutish=1200)
        _m1 = msg_matn(pg)
        pg.unroute(re.compile(r".*/api/production/orders$"))
        msg_tozala(pg)
        baj(pg, "() => poQoralamaSaqla()", kutish=1500)
        _m2 = msg_matn(pg)
        check("Y1 (A2 / D2) yangi ishlab chiqarish 502 — «natijasi noma'lum» (ilgari «saqlanmadi»); qayta — o'sha kalit, BITTA",
              NOMALUM in _m1 and "Qoralama saqlandi" in _m2 and _b.holat == [200] and soni(ProductionOrder, product_type_id=PT_A) == _n0 + 1,
              (_m1, _m2, _b.holat, soni(ProductionOrder, product_type_id=PT_A) - _n0))

        ochiq(pg, "/production")
        _n0 = soni(ProductionOrder, product_type_id=PT_A)
        _b = Bajar502()
        pg.route(re.compile(r".*/api/production/orders/\d+/start$"), _b)
        baj(pg, """(a) => { openProductionOrderModal(); document.getElementById('po-f-product-type').value = String(a[0]);
                           return onProductTypeChangeForPO(); }""", [PT_A], kutish=900)
        baj(pg, "() => { document.getElementById('po-f-quantity').value = '2'; poRejaYukla(); }", kutish=900)
        msg_tozala(pg)
        baj(pg, "() => poYaratibBoshla()", kutish=2000)
        _m = msg_matn(pg)
        pg.unroute(re.compile(r".*/api/production/orders/\d+/start$"))
        _yangi = db_ishi(lambda d: [p.id for p in d.query(ProductionOrder).filter_by(product_type_id=PT_A).order_by(ProductionOrder.id).all()])
        check("Y2 (A2 / D2) «Boshlash» 502 — «Boshlash natijasi noma'lum» (ilgari «boshlanmadi: xomashyo yetmadi» — boshlangan edi)",
              NOMALUM in _m and "xomashyo yetmadi" not in _m and _b.holat == [200] and len(_yangi) == _n0 + 1
              and holat(_yangi[-1]) == "in_progress", (_m, _b.holat, len(_yangi) - _n0, holat(_yangi[-1]) if _yangi else None))
        P_JAR = _yangi[-1] if _yangi else None

        pg.route("**/api/production/mrp-order-items*", lambda r: r.fulfill(**jsn(200, [
            {"order_item_id": 99901, "order_id": 1, "order_number": "B-181", "client_name": "Mijoz", "remaining_quantity": 3.0999999999999996,
             "is_coated": False}])))
        baj(pg, """(a) => { openProductionOrderModal(); document.getElementById('po-f-product-type').value = String(a[0]);
                           return onProductTypeChangeForPO(); }""", [PT_A], kutish=900)
        baj(pg, "() => { poManbaTanla('customer_order'); }", kutish=900)
        baj(pg, """() => { const s = document.getElementById('po-f-source-order-item'); s.value = '99901';
                           s.dispatchEvent(new Event('change')); }""", kutish=300)
        _qv = baj(pg, "() => document.getElementById('po-f-quantity').value", kutish=50)
        check("Y3 (B2) qolgan miqdor 10.2 − 7.1 — maydonda «3.1» (ilgari «3.0999999999999996»)", _qv == "3.1", _qv)
        pg.unroute("**/api/production/mrp-order-items*")
        pg.route("**/api/production/mrp-order-items*", lambda r: r.fulfill(**jsn(500, {"detail": "Internal Server Error"})))
        baj(pg, "() => loadEligibleOrderItemsForPO()", kutish=800)
        _op = matn(pg, "#po-f-source-order-item option") or ""
        pg.unroute("**/api/production/mrp-order-items*")
        check("Y4 (C4) buyurtma detallari 500 — sabab (ilgari «Bu mahsulot uchun kutilayotgan buyurtma yo'q»)",
              "Buyurtma detallari yuklanmadi" in _op and "kutilayotgan" not in _op, _op)

        baj(pg, "() => { poManbaTanla('warehouse_stock'); }", kutish=500)
        baj(pg, """() => { const c = document.querySelector('#po-optional-list .po-opt'); if (c) { c.checked = true; } }""", kutish=100)
        baj(pg, "() => { poManbaTanla('customer_order'); }", kutish=600)
        _bel = baj(pg, "() => [...document.querySelectorAll('#po-optional-list .po-opt')].map(c => c.checked)", kutish=50)
        check("Y5 (C7) ixtiyoriy tarkib (bo'yoq) belgilandi, manba almashtirildi — belgi QOLDI (ilgari jimgina olinardi)", _bel == [True], _bel)
        baj(pg, "() => closeModal('po-modal')", kutish=100)

        ochiq(pg, "/production")
        baj(pg, "() => switchProdTab('orders')", kutish=1200)
        P_QOR = (js(ishlab(PT_A, B_A, 1)).get("production_order") or {}).get("id")
        baj(pg, "() => loadProductionOrders()", kutish=1200)
        _u = Ushla()
        pg.route(re.compile(rf".*/api/production/orders/{P_QOR}/preview.*"), _u)
        baj(pg, "(id) => { poOyna(id, 'boshlash'); }", P_QOR, kutish=500)
        baj(pg, "(id) => { poOyna(id, 'yakunlash'); }", P_JAR, kutish=1500)
        _u.qoyib_yubor()
        pg.wait_for_timeout(1200)
        _t = matn(pg, "#snapshot-modal-title") or ""
        _oc = baj(pg, "() => { const b = document.getElementById('po-oyna-amal'); return b ? b.getAttribute('onclick') : null; }", kutish=50)
        pg.unroute(re.compile(rf".*/api/production/orders/{P_QOR}/preview.*"))
        check("Y6 (C1) №qoralama «Boshlash» rejasi KECH keldi, oyna allaqachon №jarayon «Yakunlash» — tugma №jarayon niki",
              f"№{P_JAR}" in _t and _oc == f"poYakunlashTasdiq({P_JAR})", (_t, _oc, P_QOR, P_JAR))

        pg.route(re.compile(rf".*/api/production/orders/{P_JAR}/complete$"), lambda r: r.abort())
        msg_tozala(pg)
        baj(pg, "(id) => poYakunlashTasdiq(id)", P_JAR, kutish=1500)
        _m = msg_matn(pg)
        pg.unroute(re.compile(rf".*/api/production/orders/{P_JAR}/complete$"))
        check("Y7 (D1) «Yakunlash» — internet uzildi: «Yakunlash natijasi noma'lum: internet aloqasi yo'q» (ilgari jim, tugma berk)",
              NOMALUM in _m and UZILISH in _m and holat(P_JAR) == "in_progress", (_m, holat(P_JAR)))

        baj(pg, "(id) => poYakunlashTasdiq(id)", P_JAR, kutish=1500)
        baj(pg, "() => loadProductionOrders()", kutish=1000)
        baj(pg, "(id) => { const p = poRoyxat.find(x => x.id === id); showSnapshot(p.recipe_snapshot, p.status, id); }", P_JAR, kutish=400)
        _sl = matn(pg, "#snapshot-list") or ""
        check("Y8 (D4) yakunlangan surat — «1 m² tannarxi» (ilgari «1 m2»)", "1 m² tannarxi" in _sl and "1 m2 tannarxi" not in _sl, _sl[-300:])
        baj(pg, "() => closeModal('snapshot-modal')", kutish=100)

        pg.route(re.compile(r".*/api/production/orders\?oy=.*"), lambda r: r.fulfill(**jsn(500, {"detail": "Internal Server Error"})))
        baj(pg, "() => loadProductionOrders()", kutish=900)
        _xu = matn(pg, "#po-xulosa") or ""
        _ch = matn(pg, "#po-holat-chiplar") or ""
        pg.unroute(re.compile(r".*/api/production/orders\?oy=.*"))
        check("Y9 (C4) ro'yxat 500 — xulosa «—» (ilgari «0 ta yakunlandi — jami tannarx 0 so'm»), chiplarda «· —»",
              "0 ta yakunlandi" not in _xu and "—" in _xu and "· 0" not in _ch, (_xu, _ch))

        # kech146 (review181 F3): kalit o'rni — so'rov TANASI bilan
        ochiq(pg, "/production")
        _ng0 = soni(ProductionOrder, product_type_id=PT_A)
        _b = Bajar502()
        pg.route(re.compile(r".*/api/production/orders$"), _b)
        baj(pg, """(a) => { openProductionOrderModal(); document.getElementById('po-f-product-type').value = String(a[0]);
                           return onProductTypeChangeForPO(); }""", [PT_A], kutish=900)
        baj(pg, "() => { document.getElementById('po-f-quantity').value = '4'; }", kutish=100)
        msg_tozala(pg)
        baj(pg, "() => poQoralamaSaqla()", kutish=1200)
        _mg1 = msg_matn(pg)
        pg.unroute(re.compile(r".*/api/production/orders$"))
        baj(pg, "() => { document.getElementById('po-f-quantity').value = '6'; }", kutish=100)
        msg_tozala(pg)
        baj(pg, "() => poQoralamaSaqla()", kutish=1500)
        _mg2 = msg_matn(pg)
        _mq = db_ishi(lambda d: sorted(float(p.quantity) for p in d.query(ProductionOrder).filter_by(product_type_id=PT_A).all()))
        check("YG1 (F3) yangi ishlab chiqarish (4) — 502 «natijasi noma'lum»; so'ng BOSHQASI (6) — yangi kalit: 6 ham yaratildi, «avvalroq "
              "bajarilgan» izohi YO'Q (ilgari server 4 ni qaytarib, 6 yaratilmasdi)",
              NOMALUM in _mg1 and _b.holat == [200] and soni(ProductionOrder, product_type_id=PT_A) == _ng0 + 2
              and 6.0 in _mq and "avvalroq" not in _mg2, (_mg1, _mg2, _b.holat, soni(ProductionOrder, product_type_id=PT_A) - _ng0))
    except Exception as _x:               # noqa: BLE001
        check("Y1–Y9 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("R. Ruxsatsiz tugmalar va narx (C2, C3)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    SEL_T = {"«+ Tarkib»": '[onclick^="openBomModal("][onclick$=")"]:not([onclick*=","])', "tarkib «Tahrirlash»": '[onclick*="openBomModal("][onclick*=","]',
             "tarkib 🗑": '[onclick^="deactivateBom("]', "«Yo'nalish»": '[onclick^="openTurYonalish("]'}
    SEL_P = {"«Boshlash» (qator)": '[onclick^="doStart("]', "«Yakunlash» (qator)": '[onclick^="doComplete("]'}
    SEL_O = {"oyna «Boshlash» / «Yakunlash»": "#po-oyna-amal", "«Ishlab chiqarishni bekor qilish»": ".po-bekor-tugma"}

    def korinish(user):
        ctx, pg = kontekst(user)
        try:
            ochiq(pg, "/production")
            n = {k: korinadi(pg, v) for k, v in SEL_T.items()}
            baj(pg, "() => switchProdTab('orders')", kutish=1200)
            n.update({k: korinadi(pg, v) for k, v in SEL_P.items()})
            baj(pg, "(id) => { poOyna(id, 'boshlash'); }", P_QOR, kutish=1200)
            n.update({k: korinadi(pg, v) for k, v in SEL_O.items()})
            return n
        finally:
            ctx.close()
    try:
        P_JAR2 = (js(ishlab(PT_A, B_A, 1)).get("production_order") or {}).get("id")
        amal(P_JAR2, "start")
        _a = korinish("i181_admin")
        check("R1 NAZORAT: admin — hamma tugma ko'rinadi", all((v or 0) > 0 for v in _a.values()), _a)
        _k = korinish("i181_kor")
        check("R2 (C2) «Ko'rish» roli — «+ Tarkib», tarkib «Tahrirlash» / 🗑, «Yo'nalish», «Boshlash» / «Yakunlash», bekor qilish YO'Q",
              all((v or 0) == 0 for v in _k.values()), _k)
    except Exception as _x:               # noqa: BLE001
        check("R1–R2 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")

    ctx, pg = kontekst("i181_nar")
    try:
        ochiq(pg, "/production")
        baj(pg, "(a) => { openBomModal(a[0], a[1]); }", [PT_A, B_A], kutish=900)
        baj(pg, "() => retseptHisobi()", kutish=1200)
        _iz = baj(pg, "() => [...document.querySelectorAll('#bom-items-wrap .bi-narx-izoh')].map(e => e.textContent)", kutish=50)
        check("R3 (C3) narx ruxsatisiz — tarkib qatorida miqdor, «narxi kiritilmagan» EMAS (narx yashirin, kiritilmagan emas)",
              isinstance(_iz, list) and _iz and not any("narxi kiritilmagan" in (x or "") for x in _iz) and not any("×" in (x or "") for x in _iz),
              _iz)
        baj(pg, "() => closeModal('bom-modal')", kutish=100)
        baj(pg, "() => switchProdTab('orders')", kutish=1200)
        baj(pg, "(id) => { const p = poRoyxat.find(x => x.id === id); showSnapshot(p.recipe_snapshot, p.status, id); }", P3, kutish=400)
        _nr = baj(pg, """() => [...document.querySelectorAll('#snapshot-list td')].filter(t => t.dataset.yorliq === "Narx (o'sha kuni)")
                                 .map(t => t.textContent.trim())""", kutish=50)
        check("R4 (C3) narx ruxsatisiz — surat «Narx (o'sha kuni)» «—» (ilgari «— / kg» yoki raqam)",
              isinstance(_nr, list) and _nr and all(x == "—" for x in _nr), _nr)
    except Exception as _x:               # noqa: BLE001
        check("R3–R4 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("TU. Tannarx farqi — sahifada")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/production")
        baj(pg, "() => switchProdTab('orders')", kutish=1200)
        baj(pg, "(id) => { poOyna(id, 'yakunlash'); }", P_TJ, kutish=1500)
        _sl = matn(pg, "#snapshot-list") or ""
        check("TU1 «Yakunlash» oynasi — «Tannarx (bugungi — yakunlash kunidagi narx bilan)» va «Boshlashdagi taxmin … qimmat»",
              "yakunlash kunidagi narx bilan" in _sl and "Boshlashdagi taxmin" in _sl and "qimmat" in _sl, _sl[-400:])
        baj(pg, "() => closeModal('snapshot-modal')", kutish=100)
        baj(pg, "(id) => { const p = poRoyxat.find(x => x.id === id); showSnapshot(p.recipe_snapshot, p.status, id); }", P_T, kutish=400)
        _sl = matn(pg, "#snapshot-list") or ""
        check("TU2 yakunlangan «Batafsil» — «Xomashyo — Boshlashdagi taxmin 30 000 so'm (+15 000 so'm)», «Narx (o'sha kuni)» 1 500",
              "Boshlashdagi taxmin" in _sl and "+15" in _sl and "1 500 so'm / kg" in _sl.replace(" ", " "), (_sl[-500:], baj(pg, "(id) => JSON.stringify((poRoyxat.find(x => x.id === id) || {}).recipe_snapshot)", P_T, kutish=10),
               baj(pg, "() => document.getElementById('snapshot-list').innerHTML.length", kutish=10)))
    except Exception as _x:               # noqa: BLE001
        check("TU1–TU2 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("LU. Savat — loyiha tiklash oynasi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/trash")
        _n0 = len(sorovlar(f"/api/projects/{LD}/restore"))
        baj(pg, """(id) => { window.__javob = ['alt']; window.__savol = []; window.setTimeout = () => 0;
                             window.customConfirm = async (a, b) => { window.__savol.push(String(typeof b === 'string' ? b : a));
                                                                      return window.__javob.length ? window.__javob.shift() : true; };
                             const b = document.querySelector(`#row-project-${id} button`) || document.createElement('button');
                             return restoreItem('project', id, b); }""", LD, kutish=1500)
        _so = [x[1] for x in sorovlar(f"/api/projects/{LD}/restore")[_n0:]]
        _sv = baj(pg, "() => window.__savol", kutish=50)
        check("LU1 «↩️ Tiklash» (loyiha) — «Savatda shu loyihaning 1 ta buyurtmasi bor … tiklansinmi?», «Faqat loyiha» → `?buyurtmalar=yoq`",
              _so == [f"/api/projects/{LD}/restore", f"/api/projects/{LD}/restore?buyurtmalar=yoq"]
              and any("1 ta buyurtmasi bor" in (x or "") for x in (_sv or [])) and _ochirilgan(_Prj, LD) is False
              and _ochirilgan(_Ord, LD_O[0]) is True, (_so, _sv))
    except Exception as _x:               # noqa: BLE001
        check("LU1 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    check("Z1 sahifalarda JS xatosi yo'q", not JS_XATO, JS_XATO[:5])

if br:
    try:
        br.close()
    except Exception:                      # noqa: BLE001
        pass
if pw_ctx:
    try:
        pw_ctx.stop()
    except Exception:                      # noqa: BLE001
        pass
server.should_exit = True

print(f"\n{'=' * 66}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print("=" * 66)
if FAILED:
    print("Yiqilganlar:")
    for x in FAILED:
        print("  - " + x)
sys.exit(0 if FAIL == 0 else 1)
