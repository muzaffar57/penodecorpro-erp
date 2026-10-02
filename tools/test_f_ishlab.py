#!/usr/bin/env python3
"""
test_f_ishlab.py — kech120, F BOSQICH 3-qism (TAYYOR MAHSULOTLAR, QAYTARISHLAR, ISHLAB CHIQARISH — audit G5 qolgan bandlari).

NIMA UCHUN KERAK (audit kech114; 2026-10-01 da JORIY kodda qayta tekshirildi — work/f/tekshiruv_kech120.md; O'LCHANGAN work/f3/probe_qayt.py):
  G5-07  Birlik yozilishi aralash: bir mahsulot Ishlab chiqarishda «4 m2» / «8 dona», Tayyor mahsulotlarda «4 m²» / «8 ta», sotish
         oynasida «8 metr».
  G5-08  Qaytarishda qop / litr — «dona» («Miqdor (dona)»), ro'yxatda «2.0 metr»; buyurtma PDF ida yangi mahsulot birligi «TA».
  G5-17  Qaytarishlar — har buyurtma yopiq guruh (1 ta yozuv bilan ham), sarlavhada faqat raqam, qidiruv guruhni ochmaydi,
         buyurtma raqami sarlavhaga escape siz yozilardi.
  G5-18  Kartalar sonlari mos emas (brak soniga ro'yxatda yo'q ishlab chiqarish braki qo'shiladi, «Jami» — hamma vaqt); bo'sh holat
         «yuqoridagi bo'limda» deydi (u bo'lim faqat «Hisobotlar» ruxsatida).
  G5-15  Qaytarishlar telefonda: 5 karta va yig'iq bo'limlar birinchi ekranni egallardi (admin: birinchi guruh 710 px da).
  G5-05  «Pul kutilmoqda» — bosiladigan yozuv; «Qiymati» — type=number, ajratgichsiz, «so'm» siz.
  G5-02  Tayyor mahsulot qatorida «[pul] − [1] +» — miqdor sanagichga o'xshaydi; «…» ichida yozuvsiz belgilar; telefonda 36 px.
  G5-09  Menejer «Ishlab chiqarishda ochish» bossa — ruxsat yo'q sahifasi.
  G5-13  Sotish / brakdan keyin 1,5 s da sahifa qayta yuklanardi — xabar o'qilmasdi.
  G5-14  Narxsiz mahsulot: «Joriy qiymati: 0 so'm», foyda oynasida minus foyda; jarayondagi partiya «tan: 0»; «Tarix» — tarix emas.
  G5-06  Mahsulot turini tahrirlab ham, o'chirib ham bo'lmaydi; birlik — erkin matn; tanlovlar izohsiz; xato ekran tepasida.
  G5-21  «Bekor qilish» ikki ma'noda (ishlab chiqarishni bekor qilish «Yopish» yonida).
  G5-22  Bo'sh korxonada qayerdan boshlash ko'rsatilmaydi; tur yo'q bo'lsa «Yangi ishlab chiqarish» bo'sh ro'yxat bilan ochiladi.
BO'LIMLAR: S — statik; J — birlik qoidasi: Python (`services.birlik_korinish`, Jinja `|birlik`) = brauzer (`birlikQisqa`, `unitLabel`);
  A — API (tur tahrirlash / o'chirish, ishlatilishi, qaytarish kartalari, jarayondagi partiya taxminiy tannarxi, buyurtma PDF birligi);
  R — server chizgan Qaytarishlar sahifasi; B — HAQIQIY Chromium (Qaytarishlar, Tayyor mahsulotlar, Ishlab chiqarish — Admin,
  Menejer, bo'sh korxona, telefon 390 px).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 132) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium (B bo'limi), Node (J bo'limi).
ISHLATISH: python3 tools/test_f_ishlab.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import uuid
import socket
import tempfile
import threading
import contextlib
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "f_ishlab_test"
_T = tempfile.mkdtemp(prefix="fish_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'f_ishlab_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, Project, Order, OrderItem, OrderType, OrderStatus, ReturnItem, ReturnReason,   # noqa: E402
                    FinishedProduct, FinishedProductLoss, StockSource, ProductionStatus, ActivityLog)
from production_models import Company, ProductType  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


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


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return r.text[:300]


def nb(s):
    return str(s or "").replace("\xa0", " ").replace(" ", " ")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAIN = oqi("main.py")
BASE = oqi("templates/base.html")
RET = oqi("templates/returns.html")
FIN = oqi("templates/finished.html")
PROD = oqi("templates/production.html")
BRAK = oqi("templates/_brak_oyna.html")
PR = oqi("production_routes.py")
PDF = oqi("pdf_service.py")
check("S1 birlik qoidasi BITTA: `services.birlik_korinish` (Jinja `|birlik`), `birlikQisqa` (base.html); Qaytarishlar `unitShortLabel`, "
      "Tayyor mahsulotlar `unitLabel`, Ishlab chiqarish `birlikYoz`, brak oynasi — shu qoida; PDF — yangi mahsulotga o'z birligi",
      'templates.env.filters["birlik"] = services.birlik_korinish' in MAIN and "function birlikQisqa(u)" in BASE
      and "  return birlikQisqa(unit);" in RET and "if (typeof birlikQisqa === 'function') return birlikQisqa(u);" in FIN
      and "function birlikYoz(birlik)" in PROD and "typeof birlikQisqa === 'function') ? birlikQisqa(u)" in BRAK
      and "elif cat == 'mrp_product':" in PDF and "{{ r.quantity|son(3) }} {{ r.unit|birlik }}" in RET
      and "LEGACY = { metr: 'm', kvadrat: 'm²', dona: 'ta'" not in FIN)
check("S2 Qaytarishlar: bitta yozuvli buyurtma guruhlanmaydi, sarlavha escape, qidiruvda o'zi ochiladi; «Hisob-kitob qilish» TUGMA; "
      "«Qiymati» — umumiy pul qoidasi; telefon tasmasi; bo'sh holat — rolga qarab",
      "if (groupRows.length < 2) return;" in RET and "${escapeHtml(orderKey)}" in RET and "h._ochYop(true)" in RET
      and "💰 Hisob-kitob qilish" in RET and 'else "Pul kutilmoqda"' not in RET and 'oninput="formatPriceInput(this)"' in RET
      and 'id="f-value" placeholder="0" min="0"' not in RET and "ret-stat-tasma" in RET
      and "<span style=\"font-size:12.5px\">(Brak yozuvlari yuqoridagi bo'limda ko'rinadi)</span>" not in RET)
check("S3 Tayyor mahsulotlar: «Sotish» / «Brak» / «Yana ishlab chiqarish» so'z bilan, «1» maydoni yo'q; «…» — nomli; Menejerga havola "
      "o'rniga yozuv; sotish / brakdan keyin sahifa qayta yuklanmaydi; «Ma'lumot»; jarayondagi partiya — taxminiy tannarx",
      "<span>Sotish</span>" in FIN and "<span>Brak</span>" in FIN and "<span>Yana ishlab chiqarish</span>" in FIN
      and 'id="fq-${i.id}"' not in FIN and "<span>Foyda hisobi</span>" in FIN and "ISHLAB_KORADI" in FIN
      and "setTimeout(() => location.reload(), 1500)" not in FIN and "' — tarix'" not in FIN and "i.taxminiy_tannarx" in FIN
      and "if (typeof loadFp === 'function') loadFp(); else setTimeout(() => location.reload(), 1500);" in BRAK)
check("S4 Ishlab chiqarish: tur tahrirlash (PUT) va o'chirish tugmalari, birlik — ro'yxatdan, tanlov izohlari, oynadagi xato, "
      "«Ishlab chiqarishni bekor qilish», bo'sh korxona yo'riqnomasi",
      '@router.put("/product-types/{pt_id}"' in PR and '"type": "product_type_used"' in PR and '"type": "product_type_in_production"' in PR
      and "function openProductTypeEdit(id)" in PROD and "function deleteProductType(id)" in PROD and 'id="pt-f-unit-tanlov"' in PROD
      and "const KIRITISH_MISOL" in PROD and 'id="pt-xato"' in PROD and ">Ishlab chiqarishni bekor qilish</button>" in PROD
      and "Ishlab chiqarishni boshlash — 4 qadam" in PROD and ">Bekor qilish</button>`;" not in PROD)

ORDH = oqi("templates/orders.html")
check("S5 Buyurtmalar: «Tayyor mahsulotdan» belgisi birligi — umumiy qoida (qop / kg ham, ilgari hammasi «ta»), HTML ga escape bilan",
      "function fpUnitLabel(u) { return (typeof birlikQisqa === 'function') ? birlikQisqa(u)" in ORDH
      and "${fp.quantity} ${escapeHtml(fpUnitLabel(fp.unit))} bor" in ORDH and "${fp.quantity} ${fpUnitLabel(fp.unit)} bor\n" not in ORDH)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. Birlik qoidasi — Python = brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
NAMUNA = [None, "", "  ", "ta", "Ta", "dona", "DONA", "metr", "Metr", "kvadrat", "m2", "M2", "m3", "sm2", "mm3", "m²", "m³", "kg",
          "qop", "litr", "  qop ", "to'plam", "metr2", "m22", "<b>x</b>", "Kg", "Qop"]


def js_funksiya(matn, nom_):
    for bosh in ("async function " + nom_ + "(", "function " + nom_ + "("):
        i = matn.find(bosh)
        if i >= 0:
            k = matn.find("\n}", i)
            return matn[i:k + 2] if k >= 0 else ""
    return ""


_jkod = {"birlikKor": js_funksiya(BASE, "birlikKor"), "birlikQisqa": js_funksiya(BASE, "birlikQisqa"),
         "unitLabel": js_funksiya(FIN, "unitLabel"), "birlikYoz": js_funksiya(PROD, "birlikYoz")}
# asl kodda (zip 132) funksiya / filtr yo'q — o'zgarishsiz qiymat (tekshiruvlar yiqiladi, sinov qulamaydi)
_py = [(getattr(services, "birlik_korinish", None) or (lambda x: x))(x) for x in NAMUNA]
_jinja = [(main.templates.env.filters.get("birlik") or (lambda x: x))(x) for x in NAMUNA]
_skr = ("const vm = require('vm'); const K = JSON.parse(process.argv[1]); const N = JSON.parse(process.argv[2]);\n"
        "const a = vm.createContext({}); vm.runInContext(K.birlikKor + '\\n' + K.birlikQisqa + '\\n' + K.birlikYoz, a);\n"
        "const b = vm.createContext({}); vm.runInContext(K.unitLabel, b);\n"
        "const c = vm.createContext({}); vm.runInContext(K.birlikKor + '\\n' + K.birlikQisqa + '\\n' + K.unitLabel, c);\n"
        "const r = {qisqa: N.map(x => a.birlikQisqa(x)), yoz: N.map(x => a.birlikYoz(x)), unitYolgiz: N.map(x => b.unitLabel(x)),\n"
        "           unitBase: N.map(x => c.unitLabel(x))};\n"
        "console.log(JSON.stringify(r));")
try:
    _jn = json.loads(subprocess.run(["node", "-e", _skr, json.dumps(_jkod), json.dumps(NAMUNA)], capture_output=True, text=True,
                                    timeout=60).stdout or "{}")
except Exception as _e:                    # noqa: BLE001
    _jn = {"xato": str(_e)}
_yoz_kut = [(x if x else "") for x in _py]
check("J1 funksiyalar topildi (birlikKor, birlikQisqa, unitLabel, birlikYoz)", all(_jkod.values()), [k for k, v in _jkod.items() if not v])
check("J2 Python `birlik_korinish` = Jinja `|birlik` = brauzer `birlikQisqa` (27 namuna: «ta» → dona, metr → m, m2 → m², qop — qop, "
      "«Kg» → kg)", _py == _jinja == _jn.get("qisqa") and _py[3] == "dona" and _py[7] == "m" and _py[10] == "m²" and _py[18] == "qop"
      and _py[1] == "dona" and _py[25] == "kg" and _py[26] == "qop", {"py": _py, "js": _jn})
check("J3 Tayyor mahsulotlar `unitLabel` — base.html bilan ham, usiz (sinov qum-qutisi) ham — AYNAN shu natija",
      _jn.get("unitYolgiz") == _py and _jn.get("unitBase") == _py, _jn)
check("J4 Ishlab chiqarish `birlikYoz` — shu qoida", _jn.get("yoz") == _py, _jn.get("yoz"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Ma'lumot")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, MENEJER, OMBORCHI, BOSH, PAROL = "fish_admin", "fish_menejer", "fish_omborchi", "fish_bosh", "Parol123!"
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="FI B korxona", code="FI-B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, ADMIN, PAROL, UserRole.ADMIN, "FI Admin", company_id=1)
    auth.create_user(_db, MENEJER, PAROL, UserRole.MANAGER, "FI Menejer", company_id=1)
    auth.create_user(_db, OMBORCHI, PAROL, UserRole.WAREHOUSE, "FI Omborchi", company_id=1)
    auth.create_user(_db, BOSH, PAROL, UserRole.ADMIN, "FI Bo'sh", company_id=2)
_db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_l = C.post("/login", data={"username": ADMIN, "password": PAROL}, follow_redirects=False).status_code
CM = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CM.post("/login", data={"username": MENEJER, "password": PAROL}, follow_redirects=False)
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB.post("/login", data={"username": BOSH, "password": PAROL}, follow_redirects=False)
_n = uuid.uuid4().hex[:4]
ID = {}


def mat(nom, unit, stock, price):
    return (js(C.post("/api/inventory", json={"item_name": nom, "unit": unit, "stock_quantity": stock, "price_per_unit": price})) or {}).get("id")


ID["qum"] = mat(f"FI Qum {_n}", "kg", 500, 800)
ID["sement"] = mat(f"FI Sement {_n}", "kg", 500, 1500)
ID["kley"] = (js(C.post("/api/production/product-types", json={
    "name": f"FI Kafel kley {_n}", "unit": "qop", "input_template": "quantity_only", "pricing_formula": "unit_based"})) or {}).get("id")
ID["kley_b"] = (js(C.post("/api/production/boms", json={
    "product_type_id": ID["kley"], "variant_name": "Standart", "batch_quantity": 1,
    "items": [{"inventory_id": ID["qum"], "quantity": 20}, {"inventory_id": ID["sement"], "quantity": 5}]})) or {}).get("id")
ID["bosh_tur"] = (js(C.post("/api/production/product-types", json={
    "name": f"FI Bo'sh tur {_n}", "unit": "m2", "input_template": "area_2d", "pricing_formula": "area_based"})) or {}).get("id")
ID["qoralama_tur"] = (js(C.post("/api/production/product-types", json={
    "name": f"FI Qoralama tur {_n}", "unit": "dona", "input_template": "quantity_only", "pricing_formula": "unit_based"})) or {}).get("id")
ID["qoralama_b"] = (js(C.post("/api/production/boms", json={
    "product_type_id": ID["qoralama_tur"], "variant_name": "Oddiy", "batch_quantity": 1,
    "items": [{"inventory_id": ID["qum"], "quantity": 1}]})) or {}).get("id")


def po(pt, bom, miqdor, *amallar):
    r = C.post("/api/production/orders", json={"product_type_id": pt, "bom_id": bom, "quantity": miqdor, "source_type": "warehouse_stock"})
    pid = ((js(r) or {}).get("production_order") or {}).get("id")
    for a in amallar:
        C.post(f"/api/production/orders/{pid}/{a}")
    return pid


ID["p_tayyor"] = po(ID["kley"], ID["kley_b"], 4, "start", "complete")      # narxsiz tayyor mahsulot (tannarx bor)
ID["p_jarayon"] = po(ID["kley"], ID["kley_b"], 2, "start")                  # jarayondagi partiya
ID["p_qoralama"] = po(ID["qoralama_tur"], ID["qoralama_b"], 3)              # ochiq (qoralama) — turni o'chirib bo'lmaydi
ID["loyiha"] = (js(C.post("/api/projects", json={"project_name": f"FI Loyiha {_n}", "client_name": "Aziz Karimov"})) or {}).get("id")
_o = js(C.post("/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": ID["loyiha"], "order_type": "product", "deadline": "2026-12-10", "is_draft": False,
    "items": [{"name": "FI Kafel kley", "category": "mrp_product", "quantity": 20, "unit_price": 30000, "product_type_id": ID["kley"]}]})) or {}
ID["o_kley"] = _o.get("id")
ID["oi_kley"] = ((_o.get("items") or [{}])[0]).get("id")
_s = SessionLocal()
_pr = _s.get(Project, ID["loyiha"])
XSS_RAQAM = f'FI-<b>{_n}</b>'
_ok = [Order(company_id=1, project_id=_pr.id, order_number=f"FI-{_n}-1", order_type=OrderType.PRODUCT, status=OrderStatus.DELIVERED),
       Order(company_id=1, project_id=_pr.id, order_number=f"FI-{_n}-3", order_type=OrderType.PRODUCT, status=OrderStatus.DELIVERED),
       Order(company_id=1, project_id=_pr.id, order_number=XSS_RAQAM, order_type=OrderType.PRODUCT, status=OrderStatus.DELIVERED)]
_s.add_all(_ok)
_s.commit()
_i1 = OrderItem(company_id=1, order_id=_ok[0].id, name="Karniz K-12", category="profil", length=20, quantity=1)
_i3 = OrderItem(company_id=1, order_id=_ok[1].id, name="Panel P-3", category="panel", quantity=12)
_ix = OrderItem(company_id=1, order_id=_ok[2].id, name="Vaza", category="dona", quantity=5)
_s.add_all([_i1, _i3, _ix])
_s.commit()
_fpk = FinishedProduct(company_id=1, name=f"FI Karniz {_n}", category="profil", unit="metr", quantity=5, unit_price=10000, cost_price=30000,
                       source=StockSource.PRODUCED, production_status=ProductionStatus.READY, width=12, thickness=8)
_fpd = FinishedProduct(company_id=1, name=f"FI Vaza {_n}", category="dona", unit="dona", quantity=8, unit_price=50000, cost_price=160000,
                       source=StockSource.PRODUCED, production_status=ProductionStatus.READY, width=10, thickness=10)
_s.add_all([_fpk, _fpd])
_s.commit()
_s.add_all([
    ReturnItem(company_id=1, order_id=_ok[0].id, order_item_id=_i1.id, item_name="Karniz K-12", quantity=2.0, unit="metr",
               reason=ReturnReason.EXCESS, refund_amount=150000),
    ReturnItem(company_id=1, order_id=_ok[0].id, order_item_id=_i1.id, item_name="Karniz K-12", quantity=1.5, unit="metr",
               reason=ReturnReason.DEFECT, refund_amount=30000),
    ReturnItem(company_id=1, order_id=_ok[0].id, order_item_id=_i1.id, item_name="Karniz K-12", quantity=0.25, unit="metr",
               reason=ReturnReason.EXCESS, refund_amount=20000),
    ReturnItem(company_id=1, order_id=ID["o_kley"], order_item_id=ID["oi_kley"], item_name="FI Kafel kley", quantity=3, unit="qop",
               reason=ReturnReason.EXCESS, refund_amount=90000),
    ReturnItem(company_id=1, order_id=_ok[1].id, order_item_id=_i3.id, item_name="Panel P-3", quantity=2, unit="metr",
               reason=ReturnReason.DEFECT, refund_amount=0),
    ReturnItem(company_id=1, order_id=_ok[2].id, order_item_id=_ix.id, item_name="Vaza", quantity=1, unit="dona",
               reason=ReturnReason.EXCESS, refund_amount=10000),
    ReturnItem(company_id=1, order_id=_ok[2].id, order_item_id=_ix.id, item_name="Vaza", quantity=1, unit="dona",
               reason=ReturnReason.EXCESS, refund_amount=10000, is_refunded=True),
    FinishedProductLoss(company_id=1, finished_product_id=_fpk.id, product_name=_fpk.name, category="profil", quantity=1, unit="metr",
                        cost_amount=5000, reason=crud._ISH_BRAK_BELGI + " — FI"),
])
_s.commit()
ID.update({"o1": _ok[0].id, "o3": _ok[1].id, "ox": _ok[2].id, "fpk": _fpk.id, "fpd": _fpd.id})
_fp_t = _s.query(FinishedProduct).filter(FinishedProduct.company_id == 1, FinishedProduct.product_type_id == ID["kley"]).all()
ID["fp_tayyor"] = next((f.id for f in _fp_t if f.production_status == ProductionStatus.READY), None)
ID["fp_jarayon"] = next((f.id for f in _fp_t if f.production_status == ProductionStatus.IN_PROGRESS), None)
_men = _s.query(User).filter(User.username == MENEJER).first()
MEN_TANNARX = bool(_men.ruxsat("tannarx", "korish"))
MEN_ISHLAB = bool(_men.ruxsat("mahsulot_turi", "korish"))
MEN_QAYT_TAHRIR = bool(_men.ruxsat("qaytarish", "tahrirlash"))
_s.close()
check("D0 kirdi; 3 mahsulot turi (qop — retsept, buyurtma, tayyor va jarayondagi partiya; m2 — ishlatilmagan; qoralama ishlab chiqarishli), "
      "7 qaytarish (bittasi HTML raqamli buyurtmada), ishlab chiqarish braki, 2 penoplast mahsulot",
      _l == 302 and all(v is not None for v in ID.values()), ID)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_xl = js(C.get("/api/production/product-types/xulosa")) or []
_xk = {t.get("id"): t for t in _xl if isinstance(t, dict)}
check("A1 turlar jadvali — ishlatilishi: qop turi (retsept, buyurtma, ishlab chiqarish, tayyor mahsulot) va matni; m2 turi — ishlatilmagan",
      (_xk.get(ID["kley"]) or {}).get("ishlatilishi", {}).get("retsept") == 1
      and (_xk.get(ID["kley"]) or {}).get("ishlatilishi", {}).get("buyurtma") == 1
      and (_xk.get(ID["kley"]) or {}).get("ishlatilishi", {}).get("ishlab") == 2
      and "1 ta retseptda" in (_xk.get(ID["kley"]) or {}).get("ishlatilishi_matni", "")
      and (_xk.get(ID["bosh_tur"]) or {}).get("ishlatilishi_matni") == "", {k: (v.get("ishlatilishi"), v.get("ishlatilishi_matni")) for k, v in _xk.items()})


def tur_tana(pt, **k):
    t = {"name": pt["name"], "unit": pt["unit"], "input_template": pt["input_template"], "pricing_formula": pt["pricing_formula"],
         "fixed_unit_price": pt.get("fixed_unit_price"), "supports_coating": pt.get("supports_coating", False),
         "coating_price_multiplier": pt.get("coating_price_multiplier"), "notes": pt.get("notes")}
    t.update(k)
    return t


_kt = _xk.get(ID["kley"]) or {}
_bt = _xk.get(ID["bosh_tur"]) or {}
_r1 = C.put(f"/api/production/product-types/{ID['kley']}", json=tur_tana(_kt, unit="kg"))
_r2 = C.put(f"/api/production/product-types/{ID['kley']}", json=tur_tana(_kt, input_template="area_2d"))
_s = SessionLocal()
_pt_k = _s.get(ProductType, ID["kley"])
_k_oldin = (_pt_k.unit, _pt_k.input_template)
_s.close()
check("A2 ishlatilgan tur: birlik (qop → kg) yoki kiritish shakli — 409 `product_type_used`, sababi (qayerda ishlatilgani) bilan; o'zgarmadi",
      lambda: _r1.status_code == 409 and (js(_r1).get("detail") or {}).get("type") == "product_type_used"
      and "o'lchov birligi o'zgartirilmaydi" in (js(_r1).get("detail") or {}).get("message", "")
      and "1 ta retseptda" in (js(_r1).get("detail") or {}).get("message", "")
      and _r2.status_code == 409 and "kiritish shakli" in (js(_r2).get("detail") or {}).get("message", "") and _k_oldin == ("qop", "quantity_only"),
      (_r1.status_code, js(_r1), _r2.status_code, _k_oldin))
_r3 = C.put(f"/api/production/product-types/{ID['kley']}",
            json=tur_tana(_kt, name=f"FI Kafel kley Pro {_n}", pricing_formula="fixed_price", fixed_unit_price=85000, notes="izoh"))
_s = SessionLocal()
_pt_k = _s.get(ProductType, ID["kley"])
_k3 = (_pt_k.name, _pt_k.unit, float(_pt_k.fixed_unit_price or 0), _pt_k.pricing_formula)
_log = _s.query(ActivityLog).filter(ActivityLog.entity_type == "product_type", ActivityLog.entity_id == ID["kley"],
                                    ActivityLog.action == "updated").order_by(ActivityLog.id.desc()).first()
_log3 = (_log.old_value, _log.new_value) if _log else None
_s.close()
check("A3 ishlatilgan turda nom, narx usuli, qat'iy narx, izoh — 200; jurnalda eski → yangi (nomi, narx usuli, qat'iy narx, izoh)",
      _r3.status_code == 200 and _k3 == (f"FI Kafel kley Pro {_n}", "qop", 85000.0, "fixed_price") and _log3
      and f"nomi: FI Kafel kley {_n}" in _log3[0] and f"nomi: FI Kafel kley Pro {_n}" in _log3[1] and "qat'iy narx: 85" in nb(_log3[1])
      and "izoh: bor" in _log3[1], (_r3.status_code, js(_r3), _k3, _log3))
_r4 = C.put(f"/api/production/product-types/{ID['bosh_tur']}", json=tur_tana(_bt, name=f"FI Plitka {_n}", unit="m²",
                                                                            input_template="quantity_only", pricing_formula="unit_based"))
_r5 = C.put(f"/api/production/product-types/{ID['bosh_tur']}", json=tur_tana(_bt, name=f"FI Plitka {_n}", unit="kg",
                                                                            input_template="weight_volume", pricing_formula="unit_based"))
_s = SessionLocal()
_pt_b = _s.get(ProductType, ID["bosh_tur"])
_b5 = (_pt_b.name, _pt_b.unit, _pt_b.input_template)
_s.close()
check("A4 ishlatilmagan tur: birlik va kiritish shakli ham o'zgaradi (m2 → m² → kg, maydon → og'irlik)", _r4.status_code == 200
      and _r5.status_code == 200 and _b5 == (f"FI Plitka {_n}", "kg", "weight_volume"), (_r4.status_code, _r5.status_code, js(_r5), _b5))
_r6 = C.put(f"/api/production/product-types/{ID['kley']}", json=tur_tana(_kt, name=f"FI Plitka {_n}"))
_r7 = CB.put(f"/api/production/product-types/{ID['kley']}", json=tur_tana(_kt))
_r8 = CM.put(f"/api/production/product-types/{ID['kley']}", json=tur_tana(_kt))
_r8b = C.put(f"/api/production/product-types/{ID['kley']}", json=dict(tur_tana(_kt), boshqa=1))
check("A5 takror nom — 400 (sababi bilan); boshqa korxona — 404; Menejer (tahrirlash ruxsati yo'q) — 403; ortiqcha kalit — 400",
      _r6.status_code == 400 and "allaqachon bor" in str(js(_r6)) and _r7.status_code == 404 and _r8.status_code == 403
      and _r8b.status_code == 400, (_r6.status_code, _r7.status_code, _r8.status_code, _r8b.status_code))
# ko'rinishi bir xil birlik — ishlatilgan turda ham ruxsat («qop» → «Qop» emas; m2/m² — alohida tur bilan)
ID["m2_tur"] = (js(C.post("/api/production/product-types", json={
    "name": f"FI Panel m2 {_n}", "unit": "m2", "input_template": "quantity_only", "pricing_formula": "unit_based"})) or {}).get("id")
C.post("/api/production/boms", json={"product_type_id": ID["m2_tur"], "variant_name": "V", "batch_quantity": 1,
                                     "items": [{"inventory_id": ID["qum"], "quantity": 1}]})
_m2 = ([t for t in (js(C.get("/api/production/product-types/xulosa")) or []) if t.get("id") == ID["m2_tur"]] or [{}])[0]
_r9 = C.put(f"/api/production/product-types/{ID['m2_tur']}", json=tur_tana(dict({"name": "", "unit": "", "input_template": "",
                                                                                     "pricing_formula": ""}, **_m2), unit="m²"))
check("A6 ishlatilgan turda KO'RINISHI bir xil birlik («m2» → «m²») — 200", _r9.status_code == 200 and (js(_r9) or {}).get("unit") == "m²",
      (_r9.status_code, js(_r9)))
_d1 = C.delete(f"/api/production/product-types/{ID['qoralama_tur']}")
C.post(f"/api/production/orders/{ID['p_qoralama']}/cancel")
_d2 = C.delete(f"/api/production/product-types/{ID['qoralama_tur']}")
_s = SessionLocal()
_qa = _s.get(ProductType, ID["qoralama_tur"]).is_active
_s.close()
check("A7 ochiq (qoralama) ishlab chiqarishi bor turni o'chirish — 409 (sababi: avval yakunlang yoki bekor qiling); bekor qilingach — "
      "200, tur nofaol", lambda: _d1.status_code == 409 and (js(_d1).get("detail") or {}).get("type") == "product_type_in_production"
      and "1 ta ishlab chiqarish hali ochiq" in (js(_d1).get("detail") or {}).get("message", "") and _d2.status_code == 200 and _qa is False,
      (_d1.status_code, js(_d1), _d2.status_code, _qa))
_st = js(C.get("/api/returns/stats")) or {}
check("A8 qaytarish kartalari: bu oy brak = ro'yxatdagi brak (2) + ishlab chiqarish braki (1); hamma vaqt = butun (5) + brak (2)",
      _st.get("brak_month_count") == 3 and _st.get("brak_month_yozuv_count") == 2 and _st.get("brak_month_prod_count") == 1
      and _st.get("total_count") == 7 and _st.get("total_whole_count") == 5 and _st.get("total_brak_yozuv_count") == 2
      and _st.get("whole_month_count") == 5, _st)
_fl = {x.get("id"): x for x in (js(C.get("/api/finished")) or []) if isinstance(x, dict)}
_pl = {x.get("id"): x for x in (js(C.get("/api/production/orders")) or []) if isinstance(x, dict)}
_tax = (_fl.get(ID["fp_jarayon"]) or {}).get("taxminiy_tannarx")
_tax_po = (_pl.get(ID["p_jarayon"]) or {}).get("taxminiy_tannarx")
_flm = {x.get("id"): x for x in (js(CM.get("/api/finished")) or []) if isinstance(x, dict)}
check("A9 jarayondagi partiya — `taxminiy_tannarx` (Ishlab chiqarish ro'yxatidagi bilan AYNAN, > 0); tayyor mahsulotda — null; "
      "«Tannarx va foyda» ruxsatisiz (Menejer) — null",
      _tax is not None and _tax > 0 and abs(_tax - float(_tax_po or 0)) < 0.01 and (_fl.get(ID["fp_tayyor"]) or {}).get("taxminiy_tannarx") is None
      and (MEN_TANNARX or (_flm.get(ID["fp_jarayon"]) or {}).get("taxminiy_tannarx") is None),
      (_tax, _tax_po, (_flm.get(ID["fp_jarayon"]) or {}).get("taxminiy_tannarx"), MEN_TANNARX))
_pdf = C.get(f"/api/orders/{ID['o_kley']}/pdf")
_pdf_m = ""
try:
    from pypdf import PdfReader as _PR
    _pdf_m = " ".join((p.extract_text() or "") for p in _PR(io.BytesIO(_pdf.content)).pages)
except Exception as _e:                    # noqa: BLE001
    _pdf_m = f"XATO {type(_e).__name__}: {_e}"
# kech120 (zip 136 — G6-12, MOSLANDI): buyurtma PDF birligi — umumiy qoida, kichik harfda («qop»; zip 133 da «QOP»)
check("A10 buyurtma PDF: yangi (MRP) mahsulot birligi — o'z turiniki («qop»), «TA» emas", _pdf.status_code == 200
      and re.search(r"\bqop\b", _pdf_m) and not re.search(r"\bTA\b", _pdf_m),
      (_pdf.status_code, _pdf_m[:400]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Server chizgan Qaytarishlar sahifasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_h = C.get("/returns").text
_miq = [nb(re.sub(r"\s+", " ", m)).strip() for m in re.findall(r'<div class="ret-qty"[^>]*>\s*(?:\{#.*?#\}\s*)?<div[^>]*>(.*?)</div>', _h, re.S)]
check("R1 qator miqdori — son va birlik qoidasi: «2 m», «1,5 m», «0,25 m», «3 qop», «1 dona» (ilgari «2.0 metr»)",
      {"2 m", "1,5 m", "0,25 m", "3 qop", "1 dona"} <= set(_miq) and not any("metr" in m or "." in m for m in _miq), _miq)
check("R2 qatorda mijoz, sana (guruh sarlavhasi uchun); summa — faqat «Tannarx va foyda» ruxsatida (admin — bor)",
      'data-mijoz="Aziz Karimov"' in _h and re.search(r'data-sana="\d\d\.\d\d\.\d{4}"', _h) and 'data-summa="150000.0"' in _h, None)
_hm = CM.get("/returns").text
check("R3 Menejer: summa yo'q (`data-summa`); «Hisob-kitob qilish» — summa ustuni («Tannarx va foyda») va «qaytarish: tahrirlash» ruxsatida",
      ("data-summa=" in _hm) == MEN_TANNARX and (("💰 Hisob-kitob qilish" in _hm) == (MEN_TANNARX and MEN_QAYT_TAHRIR)),
      (MEN_TANNARX, MEN_QAYT_TAHRIR))
_hb = CB.get("/returns").text
check("R4 bo'sh korxona: «So'nggi 90 kunda qaytarish yoki brak yozilmagan» va nima qilish («Yangi qaytarish», «Brak yozish»)",
      "So'nggi 90 kunda qaytarish yoki brak yozilmagan" in _hb and "«Yangi qaytarish», buzilgan mahsulot — «Brak yozish»" in _hb
      and "yuqoridagi bo'limda" not in _hb, None)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Brauzer (HAQIQIY Chromium)")
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
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*", "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        br = None
        _pw_x = f"{type(_e).__name__}: {_e}"
check("B0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO, SOROV = [], []


def kontekst(user=ADMIN, w=1440, h=900, tel=False):
    ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""), q.post_data)) if "/api/" in q.url else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


def tasdiq(pg):
    pg.wait_for_function("() => { const m = document.getElementById('ccModal'); return m && getComputedStyle(m).display !== 'none'; }")
    return pg.evaluate("""() => ({matn: document.getElementById('ccModalMessage').textContent,
                                   ok: document.getElementById('ccModalOk').textContent, bekor: document.getElementById('ccModalCancel').textContent})""")


def tasdiqla(pg, ha=True):
    pg.click("#ccModalOk" if ha else "#ccModalCancel")
    pg.wait_for_timeout(200)


if br:
    # ── Qaytarishlar (admin, 1440) ──
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/returns", wait_until="networkidle")
        pg.wait_for_timeout(500)
        _g = pg.evaluate("""() => ({sarlavha: [...document.querySelectorAll('.ret-group-header')].map(h => ({m: h.innerText.replace(/\\s+/g, ' '),
                                                                                 b: !!h.querySelector('b'), ochiq: h.classList.contains('open')})),
            yakka: [...document.querySelectorAll('#retList > .ret-row')].map(r => r.dataset.order),
            kart: [...document.querySelectorAll('#kpiRow .stat-card')].map(c => c.innerText.replace(/\\s+/g, ' '))})""")
        _sar = {x["m"].split(" ")[0]: x for x in _g["sarlavha"]}
        _g1 = next((x for x in _g["sarlavha"] if x["m"].startswith(f"FI-{_n}-1 ")), {})
        _gx = next((x for x in _g["sarlavha"] if "FI-<b>" in x["m"]), {})
        check("B1 bitta yozuvli buyurtmalar guruhlanmaydi (qator darhol ko'rinadi); 2+ yozuvli — guruh: mijoz, «2 butun · 1 brak», summa, "
              "sana, «3 ta»", len(_g["sarlavha"]) == 2 and set(_g["yakka"]) == {f"FI-{_n}-3", _o.get("order_number")}
              and "Aziz Karimov" in _g1.get("m", "") and "🟢 2 butun · 🔴 1 brak" in _g1.get("m", "") and "200 000 so'm" in nb(_g1.get("m", ""))
              and re.search(r"\d\d\.\d\d\.\d{4}", _g1.get("m", "")) and _g1.get("m", "").endswith("3 ta") and not _g1.get("ochiq"), _g)
        check("B2 HTML belgili buyurtma raqami sarlavhada MATN bo'lib chiqadi (`<b>` teg yasalmaydi)", _gx and not _gx["b"]
              and f"FI-<b>{_n}</b>" in _gx["m"], _gx)
        check("B3 kartalar: «Brak — bu oy 3 ta ro'yxatda 2 · ishlab chiqarishda 1», «Butun qaytgan — bu oy 5 ta», «… hamma vaqt 7 ta butun 5 · brak 2»",
              any(k.startswith("Brak — bu oy 3 ta ro'yxatda 2 · ishlab chiqarishda 1") for k in _g["kart"])
              and any(k.startswith("Butun qaytgan — bu oy 5 ta") for k in _g["kart"])
              and any("hamma vaqt 7 ta butun 5 · brak 2" in k for k in _g["kart"]), _g["kart"])
        pg.fill("#ret-search", "Karniz")
        pg.wait_for_timeout(200)
        _q1 = pg.evaluate("""() => [...document.querySelectorAll('.ret-group-header')].filter(h => h.style.display !== 'none')
                                 .map(h => [h.querySelector('.g-title').textContent, h.classList.contains('open'), h.getAttribute('aria-expanded')])""")
        _q1r = pg.evaluate("() => [...document.querySelectorAll('.ret-row')].filter(r => r.offsetParent).length")
        pg.fill("#ret-search", "")
        pg.wait_for_timeout(200)
        _q2 = pg.evaluate("() => [...document.querySelectorAll('.ret-group-header')].map(h => h.classList.contains('open'))")
        check("B4 qidiruv «Karniz» — topilgan guruh O'ZI ochiladi (3 qator ko'rinadi); tozalansa — yana yopiladi",
              [x[0] for x in _q1] == [f"FI-{_n}-1"] and _q1[0][1] is True and _q1[0][2] == "true" and _q1r == 3 and _q2 == [False, False],
              (_q1, _q1r, _q2))
        pg.evaluate(f"() => {{ const h = [...document.querySelectorAll('.ret-group-header')].find(x => x.innerText.startsWith('FI-{_n}-1')); h.focus(); }}")
        pg.keyboard.press("Enter")
        _kb = pg.evaluate(f"() => [...document.querySelectorAll('.ret-group-header')].find(x => x.innerText.startsWith('FI-{_n}-1')).classList.contains('open')")
        check("B5 guruh sarlavhasi klaviatura bilan ochiladi (Enter)", _kb is True, _kb)
        _rb = pg.evaluate("""() => ({tugma: [...document.querySelectorAll('.refund-btn')].map(b => b.textContent.trim()),
                                     qilingan: [...document.querySelectorAll('.refund-yes')].map(b => b.textContent.trim()),
                                     eski: document.body.innerText.includes('Pul kutilmoqda')})""")
        check("B6 «💰 Hisob-kitob qilish» — tugma (button), qilingani — «✓ Hisob-kitob qilingan»; «Pul kutilmoqda» yozuvi yo'q",
              "💰 Hisob-kitob qilish" in _rb["tugma"] and "✓ Hisob-kitob qilingan" in _rb["qilingan"] and not _rb["eski"], _rb)
        del SOROV[:]
        pg.evaluate("""() => { const b = [...document.querySelectorAll('.refund-btn')][0]; b.closest('.ret-group-body') && b.closest('.ret-group-body').classList.add('open'); b.click(); }""")
        _t = tasdiq(pg)
        tasdiqla(pg, False)
        check("B7 hisob-kitob tasdig'ida buyurtma va summa; tugmalar «Ha, hisob-kitob qilinsin» / «Yopish»; «Yopish» — so'rov yo'q",
              "so'm — qaytgan mahsulot summasi buyurtmaning kelishilgan summasidan chegiriladi" in nb(_t["matn"]) and _t["ok"] == "Ha, hisob-kitob qilinsin"
              and _t["bekor"] == "Yopish" and not any(x[0] == "POST" and "/refund" in x[1] for x in SOROV), (_t, SOROV))
        # «Yangi qaytarish» oynasi — qop
        pg.evaluate("() => showAddModal()")
        pg.evaluate("() => qaytarishBuyurtmalariniYukla()")
        pg.wait_for_function(f"() => [...document.getElementById('f-order').options].some(o => o.value === '{ID['o_kley']}')")
        pg.select_option("#f-order", str(ID["o_kley"]))
        pg.wait_for_function("() => !document.getElementById('f-item').disabled")
        _opt = pg.evaluate("() => [...document.getElementById('f-item').options].map(o => o.textContent)")
        pg.select_option("#f-item", str(ID["oi_kley"]))
        pg.fill("#f-qty", "2")
        pg.dispatch_event("#f-qty", "input")
        _md = pg.evaluate("() => ({birlik: document.getElementById('f-unit-label').textContent, qiymat: document.getElementById('f-value').value, tur: document.getElementById('f-value').type})")
        pg.fill("#f-value", "")
        pg.type("#f-value", "55000.5")
        _yoz = pg.evaluate("() => document.getElementById('f-value').value")
        del SOROV[:]
        pg.evaluate("() => saveReturn()")
        pg.wait_for_load_state("load")
        pg.wait_for_timeout(500)
        _post = next((json.loads(x[2] or "{}") for x in SOROV if x[0] == "POST" and x[1] == "/api/returns"), {})
        check("B8 «Yangi qaytarish»: detal «FI Kafel kley (20 qop)», miqdor birligi «qop» (ilgari «dona»), qiymat «60 000» (so'm, ajratgich bilan), "
              "harflab «55 000.5» → 55 000,5 so'm yuboriladi", any(nb(o) == "FI Kafel kley (20 qop)" for o in _opt) and _md["birlik"] == "qop"
              and nb(_md["qiymat"]) == "60 000" and _md["tur"] == "text" and nb(_yoz) == "55 000.5" and _post.get("refund_amount") == 55000.5
              and _post.get("unit") == "qop", (_opt, _md, _yoz, _post))
    except Exception as _e:                # noqa: BLE001
        check("B! Qaytarishlar ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── Qaytarishlar — telefon ──
    ctx, pg = kontekst(w=390, h=844, tel=True)
    try:
        pg.goto(B + "/returns", wait_until="networkidle")
        pg.wait_for_timeout(500)
        _ph = pg.evaluate("""() => { const f = [...document.querySelectorAll('#retList > .ret-row, #retList > .ret-group-header')].filter(x => x.offsetParent)[0];
            const k = document.getElementById('kpiRow').getBoundingClientRect();
            return {birinchi: f ? Math.round(f.getBoundingClientRect().top) : null, kpi: Math.round(k.height), kenglik: document.documentElement.scrollWidth,
                    surish: getComputedStyle(document.getElementById('kpiRow')).overflowX}; }""")
        check("B9 telefon (390 × 844, admin): kartalar bitta tasmada (yon tomonga suriladi, ~120 px), ro'yxat BIRINCHI ekranda (ilgari 710 px da "
              "guruh sarlavhasi), gorizontal toshish yo'q", _ph["kpi"] < 140 and _ph["surish"] == "auto" and _ph["birinchi"] is not None
              and _ph["birinchi"] < 650 and _ph["kenglik"] <= 390, _ph)
    except Exception as _e:                # noqa: BLE001
        check("B! Qaytarishlar telefon", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── Tayyor mahsulotlar (admin) ──
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/finished", wait_until="networkidle")
        pg.wait_for_timeout(700)
        _fk = pg.evaluate(f"""() => {{ const r = [...document.querySelectorAll('.fp-row')].find(x => x.dataset.name === {json.dumps(f"fi karniz {_n}")});
            return r ? {{tugma: [...r.querySelectorAll('.fp-actions-wrap > .fp-amal')].map(b => b.innerText.trim()), inp: !!r.querySelector('.fp-inp'),
                        menyu: [...r.querySelectorAll('.fp-more .fp-more-band')].map(b => b.innerText.trim()), miq: r.querySelector('.fp-qty').innerText}} : null; }}""")
        check("B10 penoplast mahsulot qatori: «Sotish», «Brak», «Yana ishlab chiqarish» (so'z bilan); «1» maydoni yo'q; «…» — nomli "
              "amallar; miqdor «5 m» (ilgari «metr» / «ta» aralash)", _fk and _fk["tugma"] == ["Sotish", "Brak", "Yana ishlab chiqarish"]
              and not _fk["inp"] and {"Narxni o'zgartirish", "Ma'lumot", "Foyda hisobi", "O'chirish"} <= set(_fk["menyu"])
              and nb(_fk["miq"]) == "5 m", _fk)
        _fd = pg.evaluate(f"""() => {{ const r = [...document.querySelectorAll('.fp-row')].find(x => x.dataset.name === {json.dumps(f"fi vaza {_n}")});
            return r ? r.querySelector('.fp-qty').innerText : null; }}""")
        check("B11 donali mahsulot — «8 dona» (ilgari «8 ta»)", nb(_fd) == "8 dona", _fd)
        del SOROV[:]
        pg.evaluate(f"() => {{ window.__yana = yanaIshlabChiqarish({ID['fpk']}); }}")
        pg.wait_for_function("() => { const m = document.getElementById('kiModal'); return m && getComputedStyle(m).display !== 'none'; }")
        _ki = pg.evaluate("() => ({s: document.getElementById('kiSarlavha').textContent, i: document.getElementById('kiIzoh').textContent, v: document.getElementById('kiMaydon').value})")
        pg.fill("#kiMaydon", "2,5")
        pg.click("#kiOk")
        _t = tasdiq(pg)
        tasdiqla(pg, False)
        pg.wait_for_timeout(200)
        check("B12 «Yana ishlab chiqarish» — miqdor ALOHIDA oynada («yana necha m», omborda 5 m), so'ng tasdiq «yana 2,5 m qo'shilsinmi»; "
              "«Bekor» — so'rov yo'q", f"FI Karniz {_n} — yana necha m ishlab chiqarilsin?" == _ki["s"] and "Omborda: 5 m" in nb(_ki["i"])
              and _ki["v"] == "1" and "yana 2,5 m qo'shilsinmi" in nb(_t["matn"]) and not any(x[0] == "POST" for x in SOROV), (_ki, _t, SOROV))
        # sotish — sahifa qayta yuklanmaydi, xabar o'qiladi
        pg.evaluate("() => { window.__belgi = 'shu-sahifa'; }")
        pg.evaluate(f"() => openSellModal({ID['fpd']}, 'FI Vaza', 8, 'dona', 50000)")
        _si = pg.evaluate("() => document.getElementById('sell-stock-info').textContent")
        pg.fill("#sell-qty", "1")
        pg.select_option("#sell-master", "none")
        with ctx.expect_page() as _pdf_oyna:
            pg.evaluate("() => submitSell(false)")
        _pdf_oyna.value.close()
        pg.wait_for_timeout(2500)
        _sx = pg.evaluate("""() => ({belgi: window.__belgi || null, xabar: [...document.querySelectorAll('body > div')].map(d => d.textContent).filter(t => t.startsWith('✓ Sotildi')),
            qoldiq: (() => { const r = [...document.querySelectorAll('.fp-row')].find(x => x.dataset.name.startsWith('fi vaza')); return r ? r.querySelector('.fp-qty').innerText : null; })()})""")
        check("B13 sotish: «Omborda: 8 dona»; sotilgach sahifa QAYTA YUKLANMAYDI (2,5 s dan keyin ham xabar turibdi), ro'yxat yangilandi (7 dona)",
              nb(_si) == "Omborda: 8 dona" and _sx["belgi"] == "shu-sahifa" and _sx["xabar"] and nb(_sx["qoldiq"]) == "7 dona", (_si, _sx))
        # brak oynasi (_brak_oyna.html) — ikkala yo'l: «Ombordagi mahsulot» (haqiqiy server) va «Ishlab chiqarishda» (javob soxta —
        # faqat sahifa xatti-harakati o'lchanadi): muvaffaqiyatdan keyin sahifa QAYTA YUKLANMAYDI, ro'yxat yangilanadi
        _sabab_js = "() => { const s = document.getElementById('brak-cause'); const o = [...s.options].find(x => x.value); s.value = o ? o.value : ''; return s.value; }"
        pg.evaluate("() => { window.__belgi = 'shu-sahifa-brak'; }")
        pg.evaluate(f"() => openLossModal({ID['fpd']}, 'FI Vaza', 7, 'dona', 'dona')")
        pg.fill("#loss-qty", "1")
        _sb1 = pg.evaluate(_sabab_js)
        pg.evaluate("() => submitLoss()")
        pg.wait_for_timeout(2500)
        _bx = pg.evaluate("""() => ({belgi: window.__belgi || null, xabar: [...document.querySelectorAll('body > div')].map(d => d.textContent).filter(t => t.startsWith('✓ Kamaytirildi')),
            oyna: document.getElementById('brakModal').style.display,
            qoldiq: (() => { const r = [...document.querySelectorAll('.fp-row')].find(x => x.dataset.name.startsWith('fi vaza')); return r ? r.querySelector('.fp-qty').innerText : null; })()})""")
        check("B13b brak «Ombordagi mahsulot» (kamaytirish): saqlangach sahifa QAYTA YUKLANMAYDI (2,5 s dan keyin ham xabar turibdi), oyna "
              "yopildi, ro'yxat yangilandi (6 dona)", _sb1 and _bx["belgi"] == "shu-sahifa-brak" and _bx["xabar"] and _bx["oyna"] == "none"
              and nb(_bx["qoldiq"]) == "6 dona", (_sb1, _bx))
        pg.route("**/api/finished/production-brak", lambda r: r.fulfill(status=200, content_type="application/json",
                                                                         body=json.dumps({"success": True, "cost_amount": None})))
        pg.evaluate("() => { window.__belgi = 'shu-sahifa-ishlab'; }")
        pg.evaluate(f"() => openLossModal({ID['fpd']}, 'FI Vaza', 6, 'dona', 'dona')")
        pg.evaluate("() => setLossMode('production')")
        pg.fill("#loss-qty", "1")
        _sb2 = pg.evaluate(_sabab_js)
        pg.evaluate("() => submitLoss()")
        pg.wait_for_timeout(2500)
        _bi = pg.evaluate("""() => ({belgi: window.__belgi || null, xabar: [...document.querySelectorAll('body > div')].map(d => d.textContent).filter(t => t.startsWith('✓ Xomashyo ayirildi')),
            oyna: document.getElementById('brakModal').style.display})""")
        pg.unroute("**/api/finished/production-brak")
        check("B13c brak «Ishlab chiqarishda» (xomashyo ayirish): saqlangach sahifa QAYTA YUKLANMAYDI, xabar turibdi, oyna yopildi",
              _sb2 and _bi["belgi"] == "shu-sahifa-ishlab" and _bi["xabar"] and _bi["oyna"] == "none", (_sb2, _bi))
        _jr = pg.evaluate(f"""() => {{ const r = [...document.querySelectorAll('.fp-row')].find(x => x.querySelector('.fp-mrp-havola, .fp-mrp-yozuv') && x.innerHTML.includes('/production?po={ID['p_jarayon']}'));
            return r ? {{tan: (r.querySelector('.fp-taxminiy') || {{}}).innerText || '', jami: r.querySelector('.fp-total-col').innerText.replace(/\\s+/g, ' ')}} : null; }}""")
        check("B14 jarayondagi partiya: «tan: ≈ …» (1 qop) va «≈ … taxminiy tannarx» (ilgari «tan: 0», «0 tannarx bo'yicha»)",
              _jr and _jr["tan"].startswith("tan: ≈") and "taxminiy tannarx" in _jr["jami"] and "≈" in _jr["jami"]
              and nb(_jr["jami"]).split(" taxminiy")[0].replace("≈ ", "").replace(" ", "") == str(round(_tax)), (_jr, _tax))
        pg.evaluate(f"() => openHistoryModal({ID['fp_tayyor']})")
        _hi = pg.evaluate("() => ({t: document.getElementById('hist-title').textContent, b: document.getElementById('hist-body').innerText})")
        pg.evaluate("() => closeHistoryModal()")
        check("B15 narxsiz mahsulot «Ma'lumot» oynasi: nomi «… — ma'lumot», «Sotuv narxi: sotishda yoziladi», qiymat TANNARX bo'yicha (0 emas), "
              "penoplast qatori yo'q", _hi["t"].endswith("— ma'lumot") and "sotishda yoziladi" in _hi["b"]
              and re.search(r"Joriy qiymati \(tannarx bo'yicha\)\s+[1-9][\d  ]* so'm", nb(_hi["b"])) and "penoplast" not in _hi["b"].lower(), _hi)
        pg.evaluate(f"() => openProfitModal({ID['fp_tayyor']})")
        pg.wait_for_timeout(600)
        _pm = pg.evaluate("() => document.getElementById('pm-body').innerText")
        check("B16 narxsiz mahsulot «Foyda hisobi»: minus foyda o'rniga «narx sotishda yoziladi, foyda sotilganda hisoblanadi»",
              "foyda sotilganda hisoblanadi" in _pm and "FOYDA" not in _pm and "Rentabellik" not in _pm, _pm)
    except Exception as _e:                # noqa: BLE001
        check("B! Tayyor mahsulotlar ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── Tayyor mahsulotlar — Menejer ──
    ctx, pg = kontekst(MENEJER)
    try:
        pg.goto(B + "/finished", wait_until="networkidle")
        pg.wait_for_timeout(700)
        _mj = pg.evaluate("""() => ({havola: document.querySelectorAll('.fp-mrp-havola').length, yozuv: [...document.querySelectorAll('.fp-mrp-yozuv')].map(x => x.innerText.trim()),
                                     tax: document.querySelectorAll('.fp-taxminiy').length})""")
        check("B17 Menejer: jarayondagi partiyada havola o'rniga «Ishlab chiqarilmoqda — «Ishlab chiqarish» bo'limida yakunlanadi» (ruxsati yo'q "
              "sahifaga yo'l yo'q); taxminiy tannarx ko'rinmaydi", (MEN_ISHLAB and _mj["havola"] >= 1) or (not MEN_ISHLAB and _mj["havola"] == 0
              and _mj["yozuv"] == ["Ishlab chiqarilmoqda — «Ishlab chiqarish» bo'limida yakunlanadi"]) and (MEN_TANNARX or _mj["tax"] == 0),
              (_mj, MEN_ISHLAB, MEN_TANNARX))
    except Exception as _e:                # noqa: BLE001
        check("B! Menejer ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── Tayyor mahsulotlar — telefon ──
    ctx, pg = kontekst(w=390, h=844, tel=True)
    try:
        pg.goto(B + "/finished", wait_until="networkidle")
        pg.wait_for_timeout(700)
        _tt = pg.evaluate("""() => [...document.querySelectorAll('.fp-row .fp-amal, .fp-row .fp-yana')].filter(b => b.offsetParent)
                                   .map(b => Math.round(b.getBoundingClientRect().height))""")
        check("B18 telefon: qator tugmalari kamida 40 px (ilgari 36)", _tt and min(_tt) >= 40, _tt)
    except Exception as _e:                # noqa: BLE001
        check("B! Tayyor mahsulotlar telefon", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── Ishlab chiqarish (admin) ──
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/production", wait_until="networkidle")
        pg.wait_for_timeout(700)
        pg.evaluate(f"() => openProductTypeEdit({ID['kley']})")
        _ed = pg.evaluate("""() => ({sar: document.getElementById('pt-modal-title').textContent, nom: document.getElementById('pt-f-name').value,
            tanlov: document.getElementById('pt-f-unit-tanlov').value, yopiq: document.getElementById('pt-f-unit-tanlov').disabled,
            shakl: document.getElementById('pt-f-input-template').disabled, izoh: document.getElementById('pt-unit-izoh').textContent,
            kiz: document.getElementById('pt-kiritish-izoh').textContent, niz: document.getElementById('pt-narx-izoh').textContent,
            narx: document.getElementById('pt-f-fixed-price').value})""")
        check("B19 ishlatilgan turni tahrirlash oynasi: maydonlar to'lgan (nom, qop, 85 000), birlik va kiritish shakli YOPIQ (sababi bilan), "
              "har tanlov ostida misol", _ed["sar"].startswith("Mahsulot turini tahrirlash") and _ed["nom"] == f"FI Kafel kley Pro {_n}"
              and _ed["tanlov"] == "qop" and _ed["yopiq"] and _ed["shakl"] and "birlik va kiritish shakli o'zgarmaydi" in _ed["izoh"]
              and _ed["kiz"].startswith("Buyurtmada faqat miqdor") and "qat'iy narx" in _ed["niz"] and nb(_ed["narx"]) == "85 000", _ed)
        pg.fill("#pt-f-name", f"FI Kafel kley Gold {_n}")
        _yo = pg.evaluate("() => [...document.getElementById('pt-f-yonalish').options].map(o => o.value).find(Boolean) || ''")
        if _yo:
            pg.select_option("#pt-f-yonalish", _yo)
        del SOROV[:]
        pg.evaluate("() => saveProductType()")
        pg.wait_for_timeout(800)
        _put = [x for x in SOROV if x[0] == "PUT" and x[1] == f"/api/production/product-types/{ID['kley']}"]
        _jad = pg.evaluate("() => [...document.querySelectorAll('.pt-tur-nomi')].map(x => x.textContent)")
        check("B20 nomni o'zgartirib saqlash — PUT (birlik o'sha «qop»), jadvalda yangi nom", _put and json.loads(_put[0][2]).get("unit") == "qop"
              and f"FI Kafel kley Gold {_n}" in _jad, (_put, _jad))
        pg.evaluate("() => openProductTypeModal()")
        del SOROV[:]
        pg.evaluate("() => saveProductType()")
        pg.wait_for_timeout(300)
        _bx = pg.evaluate("""() => ({x: document.getElementById('pt-xato').textContent, kor: getComputedStyle(document.getElementById('pt-xato')).display,
            maydon: document.getElementById('pt-f-name').closest('.mf-group').classList.contains('xato'), fokus: document.activeElement && document.activeElement.id,
            ochiq: document.getElementById('pt-modal').classList.contains('open')})""")
        check("B21 bo'sh nom bilan saqlash — xato OYNA ICHIDA (maydon belgilangan, fokusda), so'rov yo'q (ilgari telefonda ekran tepasida)",
              _bx["x"] == "Mahsulot turi nomini kiriting" and _bx["kor"] == "block" and _bx["maydon"] and _bx["fokus"] == "pt-f-name"
              and _bx["ochiq"] and not any(x[0] in ("POST", "PUT") for x in SOROV), _bx)
        pg.select_option("#pt-f-unit-tanlov", "__boshqa")
        _bo = pg.evaluate("() => ({kor: getComputedStyle(document.getElementById('pt-f-unit')).display, v: document.getElementById('pt-f-unit').value})")
        pg.select_option("#pt-f-unit-tanlov", "litr")
        _li = pg.evaluate("() => ({kor: getComputedStyle(document.getElementById('pt-f-unit')).display, v: document.getElementById('pt-f-unit').value})")
        pg.select_option("#pt-f-unit-tanlov", "__boshqa")
        pg.fill("#pt-f-unit", "to'plam")
        pg.click("#pt-f-name")
        _tp = pg.evaluate("() => document.getElementById('pt-f-unit').value")
        check("B22 birlik ro'yxatdan; «Boshqa…» — matn maydoni ochiladi, «litr» — yoziladi va maydon yashirinadi; qo'lda yozilgan birlik "
              "maydondan chiqqanda «To'plam» bo'lib qolmaydi (umumiy «birinchi harf katta» qoidasi bu maydonga tegmaydi)",
              _bo["kor"] != "none" and _bo["v"] == "" and _li == {"kor": "none", "v": "litr"} and _tp == "to'plam", (_bo, _li, _tp))
        pg.evaluate("() => closeModal('pt-modal')")
        # o'chirish
        del SOROV[:]
        pg.evaluate(f"() => {{ window.__och = deleteProductType({ID['bosh_tur']}); }}")
        _dt = tasdiq(pg)
        tasdiqla(pg, True)
        pg.wait_for_timeout(800)
        _jad2 = pg.evaluate("() => [...document.querySelectorAll('.pt-tur-nomi')].map(x => x.textContent)")
        check("B23 turni o'chirish: tasdiq («… mahsulot turini o'chirasizmi?», «Ha, o'chirilsin»), DELETE, jadvaldan yo'qoladi",
              f"«FI Plitka {_n}» mahsulot turini o'chirasizmi?" in _dt["matn"] and _dt["ok"] == "Ha, o'chirilsin"
              and any(x[0] == "DELETE" and x[1] == f"/api/production/product-types/{ID['bosh_tur']}" for x in SOROV)
              and f"FI Plitka {_n}" not in _jad2, (_dt, SOROV, _jad2))
        _tk = pg.evaluate("() => [...document.querySelectorAll('.pt-amallar')].map(a => [...a.querySelectorAll('button')].map(b => b.innerText.trim() || b.getAttribute('aria-label')))[0]")
        check("B24 jadval qatorida «Turni tahrirlash» va o'chirish tugmalari", _tk and "Turni tahrirlash" in _tk and "Turni o'chirish" in _tk, _tk)
        # ishlab chiqarishni bekor qilish oynasi
        _pq = po(ID["kley"], ID["kley_b"], 1)
        pg.evaluate("() => loadProductionOrders()")
        pg.wait_for_timeout(600)
        pg.evaluate(f"() => poBatafsil({_pq})")
        pg.wait_for_function("() => document.getElementById('snapshot-tugmalar').innerText.length > 0")
        pg.wait_for_timeout(300)
        _bt2 = pg.evaluate("() => [...document.querySelectorAll('#snapshot-tugmalar button')].map(b => b.innerText.trim())")
        pg.evaluate(f"() => {{ window.__bek = doCancel({_pq}); }}")
        _bc = tasdiq(pg)
        tasdiqla(pg, False)
        check("B25 «Batafsil» (qoralama): «Ishlab chiqarishni bekor qilish» (chetda), «Yopish», «Boshlash»; tasdiqda nomi, «Ha, bekor qilinsin» / "
              "«Yo'q, qaytish»", _bt2 == ["Ishlab chiqarishni bekor qilish", "Yopish", "Boshlash"] and f"№{_pq} — FI Kafel kley Gold {_n}" in _bc["matn"]
              and _bc["ok"] == "Ha, bekor qilinsin" and _bc["bekor"] == "Yo'q, qaytish", (_bt2, _bc))
    except Exception as _e:                # noqa: BLE001
        check("B! Ishlab chiqarish ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── Ishlab chiqarish — bo'sh korxona ──
    ctx, pg = kontekst(BOSH)
    try:
        pg.goto(B + "/production", wait_until="networkidle")
        pg.wait_for_timeout(600)
        _eb = pg.evaluate("() => ({m: (document.querySelector('.pt-bosh') || {}).innerText || '', t: !!document.querySelector('.pt-bosh button')})")
        pg.evaluate("() => openProductionOrderModal()")
        pg.wait_for_timeout(300)
        _ex = pg.evaluate("() => ({oyna: document.getElementById('po-modal').classList.contains('open'), xabar: document.body.innerText.includes('Avval mahsulot turini qo\\'shing')})")
        check("B26 bo'sh korxona: «Ishlab chiqarishni boshlash — 4 qadam» (Omborxona → Mahsulot turi → tarkib → ishlab chiqarish) va "
              "«Mahsulot turi qo'shish»; «Yangi ishlab chiqarish» — oyna ochilmaydi, «Avval mahsulot turini qo'shing»",
              all(x in _eb["m"] for x in ("4 qadam", "Omborxona", "Mahsulot turi", "Mahsulot tarkibi", "Yangi ishlab chiqarish")) and _eb["t"]
              and _ex == {"oyna": False, "xabar": True}, (_eb, _ex))
    except Exception as _e:                # noqa: BLE001
        check("B! bo'sh korxona ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    check("B27 JS xatosi yo'q", not JS_XATO, JS_XATO)
if br:
    br.close()
if pw_ctx:
    pw_ctx.stop()
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
