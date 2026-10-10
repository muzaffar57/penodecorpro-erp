#!/usr/bin/env python3
"""
test_g_qaror.py — kech121, EGASI QARORLARI 02.10 (zip 138): G1-08, G3-24, G4-13, G5-05, G5-23, G6-13 (+ .webp turi).

NIMA UCHUN KERAK (egasi qarorlari — AskUserQuestion 02.10 05:3x; audit kech114):
  G1-08  Dashboard «Jami daromad» — butun vaqt, faqat tayyor buyurtmalar (Hisobotlardagi oylik daromaddan ham kam) → «Shu oy daromadi»
         (Hisobotlar bilan bir raqam); «Qarz» (= «Jami qarzdorlik») va «Bugungi to'lovlar» (≈ «Bugungi tushum») takror kartalari olinadi.
  G3-24  Menejer «Xarajat qo'shish» da xato kiritsa tuzata olmasdi → o'zi BUGUN kiritganini o'chira oladi.
  G4-13  Sanoqda ortiqcha chiqqan material — faqat narxli kirim edi → narxsiz «Kirim (tuzatish)» (sabab bilan).
  G5-05  Butun qaytarishda pul masalasi keyin, ro'yxatdagi tugma bilan → qaytarish oynasining O'ZIDA so'raladi.
  G5-23  Brak foizi asosi — faqat tayyor buyurtmalar tannarxi → HAMMA ishlab chiqarish (omborga ishlab chiqarilgani ham).
  G6-13  Korxona to'lagan transport narxi mijozga beriladigan yuk xatida → ko'rsatilmaydi (faqat tashuvchi).
BO'LIMLAR: S — statik; A — API / hisob; P — PDF matni; R — server chizgan sahifa; B — HAQIQIY Chromium.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 137) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_g_qaror.py
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
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "g_qaror_test"
_T = tempfile.mkdtemp(prefix="gqar_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'g_qaror_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Delivery, DeliveryItem, ExpenseTransaction, ActivityLog, Inventory, InventoryMovement,  # noqa: E402
                    ReturnItem)
from production_models import Company, ProductionOrder              # noqa: E402
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
    return re.sub(r"[ \t]+", " ", str(s or "").replace("\xa0", " ").replace(" ", " "))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAIN = oqi("main.py")
SRV = oqi("services.py")
DASH = oqi("templates/dashboard.html")
KX = oqi("templates/kunlik_xarajat.html")
INV = oqi("templates/inventory.html")
RET = oqi("templates/returns.html")
DPDF = oqi("delivery_pdf.py")
RX = oqi("ruxsatlar.py")
check("S1 Dashboard: «Shu oy daromadi» (`/api/finance/history?months=1`), «Qarz» / «Bugungi to'lovlar» takror kartalari yo'q, tushum "
      "tarkibi; server: `today_payments` / `today_sales`", ">Shu oy daromadi<" in DASH and ">Jami daromad<" not in DASH
      # kech137 (zip 163, MOSLANDI): so'rov endi `dashBlok('daromad', '/api/finance/history?months=1', …)` orqali — manzil izlanadi
      and 'id="f-debt"' not in DASH and 'id="d-today"' not in DASH and "'/api/finance/history?months=1'" in DASH
      and 'id="t-revenue-sub"' in DASH and '"today_payments": float(today_payments)' in SRV and '"today_sales": float(today_sales)' in SRV)
check("S2 «Xarajat qo'shish»: «Bugun siz kiritganlar», o'z xarajatini o'chirish; server — `bugungi-ozim`, `…/ozim` (yaratish ruxsati, "
      "o'ziniki, bugun, qo'lda)", 'id="kx-bugun-list"' in KX and "function kxOchir(id)" in KX
      and '@app.get("/api/finance/transactions/bugungi-ozim")' in MAIN and '@app.delete("/api/finance/transactions/{tx_id}/ozim")' in MAIN
      and '_ET138.created_by == (current_user.full_name or current_user.username)' in MAIN)
check("S3 Omborxona «Kirim (tuzatish)» (+, sabab majburiy); Qaytarish oynasida pul savoli; brak asosi — omborga ishlab chiqarish ham; "
      "yuk xatida korxona to'lagan narx yo'q; .webp turi", 'onclick="openTuzKirimModal(' in INV and "async function saveTuzKirim()" in INV
      and 'name="f-pul" value="hozir"' in RET and "pulTanlov === 'hozir'" in RET and "def omborga_ishlab_chiqarish_tannarxi(" in SRV
      and '"omborga_ishlab_tannarxi"' in RX and '_korxona_tolaydi = t_payer == "company"' in DPDF
      and '"company": "Kompaniya to\'laydi"' not in DPDF and 'mimetypes.add_type("image/webp", ".webp")' in MAIN)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Ma'lumot")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PAROL = "Parol123!"
_n = uuid.uuid4().hex[:4]
F = {"admin": (f"gq_adm_{_n}", UserRole.ADMIN, 1), "menejer": (f"gq_men_{_n}", UserRole.MANAGER, 1),
     "moliyachi": (f"gq_mol_{_n}", UserRole.ACCOUNTANT, 1), "b": (f"gq_b_{_n}", UserRole.ADMIN, 2),
     "b2": (f"gq_b2_{_n}", UserRole.MANAGER, 2)}
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="GQ B korxona", code="GQ-B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    for _k, (_u, _r, _cid) in F.items():
        # «b2» — B korxonada Menejer bilan AYNAN bir xil to'liq ismli hodim (korxonalar orasida ismlar takrorlanadi)
        auth.create_user(_db, _u, PAROL, _r, f"GQ {'menejer' if _k == 'b2' else _k} {_n}", company_id=_cid)
_db.close()


def mijoz(rol):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    return c, c.post("/login", data={"username": F[rol][0], "password": PAROL}, follow_redirects=False).status_code


CA, _la = mijoz("admin")
CM, _lm = mijoz("menejer")
CF, _lf = mijoz("moliyachi")
CB, _lb = mijoz("b")
CB2, _lb2 = mijoz("b2")
ID = {}


def mat(nom, unit, stock, price, c=CA):
    return (js(c.post("/api/inventory", json={"item_name": nom, "unit": unit, "stock_quantity": stock, "price_per_unit": price})) or {}).get("id")


ID["qum"] = mat(f"GQ Qum {_n}", "kg", 500, 800)
ID["sement"] = mat(f"GQ Sement {_n}", "kg", 500, 1500)
ID["tur"] = (js(CA.post("/api/production/product-types", json={
    "name": f"GQ Kley {_n}", "unit": "qop", "input_template": "quantity_only", "pricing_formula": "unit_based"})) or {}).get("id")
ID["bom"] = (js(CA.post("/api/production/boms", json={
    "product_type_id": ID["tur"], "variant_name": "Standart", "batch_quantity": 1,
    "items": [{"inventory_id": ID["qum"], "quantity": 20}, {"inventory_id": ID["sement"], "quantity": 5}]})) or {}).get("id")


def po(miqdor, *amallar):
    r = CA.post("/api/production/orders", json={"product_type_id": ID["tur"], "bom_id": ID["bom"], "quantity": miqdor,
                                                "source_type": "warehouse_stock"})
    pid = ((js(r) or {}).get("production_order") or {}).get("id")
    for a in amallar:
        CA.post(f"/api/production/orders/{pid}/{a}")
    return pid


ID["po1"] = po(4, "start", "complete")      # shu oy, omborga — KIRADI
ID["po2"] = po(2, "start", "complete")      # shu oy, omborga — KIRADI
ID["po3"] = po(1, "start", "complete")      # o'tgan oyga suriladi — KIRMAYDI
ID["po4"] = po(3, "start", "complete")      # buyurtma uchun deb belgilanadi — KIRMAYDI (buyurtma tannarxida)
ID["po5"] = po(2, "start", "cancel")        # bekor — KIRMAYDI
_s = SessionLocal()
_o3 = _s.get(ProductionOrder, ID["po3"])
_o3.completed_at = (_o3.completed_at or datetime.utcnow()) - timedelta(days=40)
_s.get(ProductionOrder, ID["po4"]).source_type = "customer_order"
# bekor qilingan, lekin `completed_at` bor (eski / qo'lda tuzatilgan yozuv) — holat sharti bo'lmasa kirib qolardi
_o5 = _s.get(ProductionOrder, ID["po5"])
_o5.completed_at = datetime.utcnow()
if not float(_o5.total_cost or 0):
    _o5.total_cost = 11111
_s.commit()
TC = {k: float(_s.get(ProductionOrder, ID[k]).total_cost or 0) for k in ("po1", "po2", "po3", "po4", "po5")}
_s.close()
# brak — qo'lda chiqim «Brak …» (2 kg qum, 800 so'm)
_br = CA.post(f"/api/inventory/{ID['qum']}/stock", json={"quantity_change": -2, "reason": "Brak sinov"})
ID["loyiha"] = (js(CA.post("/api/projects", json={"project_name": f"GQ Loyiha {_n}", "client_name": "Aziz Karimov"})) or {}).get("id")
_o = js(CA.post("/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": ID["loyiha"], "order_type": "product", "deadline": "2026-12-10", "is_draft": False,
    "items": [{"name": f"GQ Vaza {_n}", "category": "dona", "quantity": 5, "unit_price": 100000, "is_coated": False}]})) or {}
ID["order"] = _o.get("id")
ID["oi"] = ((_o.get("items") or [{}])[0]).get("id")
_pay = CA.post("/api/payments", json={"order_id": ID["order"], "amount": 150000, "payment_method": "naqd"})
# omborga ishlab chiqarilgan «GQ Kley» dan bugun 1 qop sotuv (40 000) — bugungi tushumning ikkinchi qismi
_fpl = js(CA.get("/api/finished"))
_fpl = _fpl if isinstance(_fpl, list) else ((_fpl or {}).get("items") or [])
ID["fp"] = next((x.get("id") for x in _fpl if f"GQ Kley {_n}" in str(x.get("name") or x.get("product_name") or "")), None)
_sot = CA.post("/api/finished/sell", json={"finished_product_id": ID["fp"], "quantity": 1, "unit_price": 40000, "payment_method": "naqd",
                                           "confirm_below_cost": True})
check("D0 kirdi (admin, Menejer, Moliyachi, B korxona); 2 material, mahsulot turi, 5 ishlab chiqarish (2 shu oy omborga, 1 o'tgan oy, 1 "
      "buyurtmaga, 1 bekor), brak chiqimi, buyurtma (5 dona), to'lov 150 000, tayyor mahsulot sotuvi 40 000",
      _la == _lm == _lf == _lb == 302 and all(ID.values()) and TC["po1"] > 0 and _br.status_code == 200 and _pay.status_code == 200
      and _sot.status_code == 200, (_la, _lm, _lf, _lb, ID, TC, _br.status_code, _pay.status_code, js(_pay), _sot.status_code, js(_sot),
                                    [(x.get("id"), x.get("name") or x.get("product_name")) for x in _fpl][:6]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API va hisob")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_t = js(CA.get("/api/dashboard/today")) or {}
check("A1 G1-08: bugungi tushum (190 000) = to'lovlar (`today_payments` 150 000) + tayyor mahsulot sotuvi (`today_sales` 40 000)",
      _t.get("today_payments") == 150000 and _t.get("today_sales") == 40000 and _t.get("today_revenue") == 190000, _t)
_bt = js(CA.get("/api/reports/brak-tahlil?oylar=1")) or {}
_kut_ombor = round(TC["po1"] + TC["po2"])
check("A2 G5-23: brak foizi asosi = tayyor buyurtmalar + shu oy OMBORGA ishlab chiqarilgan (o'tgan oy, buyurtmaga, bekor — kirmaydi)",
      _bt.get("omborga_ishlab_tannarxi") == _kut_ombor
      and _bt.get("ishlab_chiqarish_xarajat") == _bt.get("buyurtmalar_tannarxi", -1) + _kut_ombor
      and _bt.get("brak_xarajat") == 1600 and _bt.get("brak_foizi") == round(1600 / _bt["ishlab_chiqarish_xarajat"] * 100, 2),
      (_bt.get("omborga_ishlab_tannarxi"), _kut_ombor, _bt.get("buyurtmalar_tannarxi"), _bt.get("ishlab_chiqarish_xarajat"),
       _bt.get("brak_xarajat"), _bt.get("brak_foizi"), TC))
_btb = js(CB.get("/api/reports/brak-tahlil?oylar=1")) or {}
check("A3 G5-23: boshqa korxonada A ning ishlab chiqarishi sanalmaydi (0)", _btb.get("omborga_ishlab_tannarxi") == 0, _btb)
# «Hisobotlar: Ko'rish» bor, «Tannarx va foyda» yo'q (maxsus rol) — asos tarkibi ham yashirin (TANNARX_KALITLAR)
_rid = (js(CA.post("/api/rollar", json={"nom": f"GQ Hisobotchi {_n}", "ruxsatlar": {"hisobot": ["korish"]}})) or {}).get("id")
_s = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_s, f"gq_his_{_n}", PAROL, UserRole.MANAGER, f"GQ hisobotchi {_n}", company_id=1, rol_id=_rid)
_s.commit()
_s.close()
CH = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lh = CH.post("/login", data={"username": f"gq_his_{_n}", "password": PAROL}, follow_redirects=False).status_code
_bth = js(CH.get("/api/reports/brak-tahlil?oylar=1")) or {}
check("A3b G5-23: «Tannarx va foyda» ruxsatisiz (faqat «Hisobotlar: Ko'rish») — asos tarkibi (`buyurtmalar_tannarxi`, "
      "`omborga_ishlab_tannarxi`) null, trendda ham; foiz — ko'rinadi", _lh == 302 and _rid and "omborga_ishlab_tannarxi" in _bth
      and _bth.get("omborga_ishlab_tannarxi") is None and _bth.get("buyurtmalar_tannarxi") is None
      and all(t.get("omborga_ishlab_tannarxi") is None and t.get("buyurtmalar_tannarxi") is None for t in (_bth.get("trend") or [{}]))
      and _bth.get("brak_foizi") == _bt.get("brak_foizi"),
      (_lh, _rid, {k: _bth.get(k) for k in ("omborga_ishlab_tannarxi", "buyurtmalar_tannarxi", "brak_foizi", "ishlab_chiqarish_xarajat")},
       (_bth.get("trend") or [{}])[-1]))
_bug = (datetime.utcnow() + timedelta(hours=5)).strftime("%Y-%m-%dT00:00:00")
_x1 = js(CM.post("/api/finance/transactions", json={"date": _bug, "category": "tushlik", "amount": 50000, "notes": "GQ m1"})) or {}
_x2 = js(CM.post("/api/finance/transactions", json={"date": _bug, "category": "boshqa", "amount": 7000, "notes": "GQ m2"})) or {}
_x3 = js(CM.post("/api/finance/transactions", json={"date": _bug, "category": "reklama", "amount": 9000, "notes": "GQ kecha"})) or {}
_xf = js(CF.post("/api/finance/transactions", json={"date": _bug, "category": "tushlik", "amount": 33000, "notes": "GQ mol"})) or {}
_s = SessionLocal()
_kecha = _s.get(ExpenseTransaction, _x3.get("id"))
_kecha.created_at = _kecha.created_at - timedelta(days=1)
_s.commit()
_s.close()
_lst = js(CM.get("/api/finance/transactions/bugungi-ozim"))
check("A4 G3-24: Menejer «bugungi-ozim» — faqat o'zi BUGUN kiritgan 2 ta (kechagisi, Moliyachiniki — yo'q), yangisi birinchi",
      isinstance(_lst, list) and [x["id"] for x in _lst] == [_x2.get("id"), _x1.get("id")] and _lst[0]["amount"] == 7000, _lst)
_d_beg = CM.delete(f"/api/finance/transactions/{_xf.get('id')}/ozim")
_d_kech = CM.delete(f"/api/finance/transactions/{_x3.get('id')}/ozim")
_d_umm = CM.delete(f"/api/finance/transactions/{_x1.get('id')}")
_d_b = CB.delete(f"/api/finance/transactions/{_x1.get('id')}/ozim")
_d_b2 = CB2.delete(f"/api/finance/transactions/{_x1.get('id')}/ozim")
_l_b2 = js(CB2.get("/api/finance/transactions/bugungi-ozim"))
check("A5 G3-24: Moliyachiniki / kechagisi / B korxonadan (admin ham, Menejer bilan bir ismli hodim ham) — 404 sababi bilan, B dagi "
      "hodim ro'yxatida A niki yo'q; umumiy o'chirish Menejerga — 403 (avvalgidek)",
      _d_beg.status_code == 404 and "faqat o'zingiz BUGUN kiritgan" in str(js(_d_beg)) and _d_kech.status_code == 404
      and _d_umm.status_code == 403 and _d_b.status_code == 404 and _lb2 == 302 and _d_b2.status_code == 404 and _l_b2 == [],
      (_d_beg.status_code, js(_d_beg), _d_kech.status_code, _d_umm.status_code, _d_b.status_code, _lb2, _d_b2.status_code, _l_b2))
_d_ok = CM.delete(f"/api/finance/transactions/{_x1.get('id')}/ozim")
_s = SessionLocal()
_qoldi = _s.get(ExpenseTransaction, _x1.get("id"))
_aud = _s.query(ActivityLog).filter(ActivityLog.entity_type == "xarajat", ActivityLog.entity_id == _x1.get("id"),
                                    ActivityLog.action == "deleted").first()
_s.close()
check("A6 G3-24: o'zi bugun kiritgani — 200, bazadan o'chdi, audit yozuvi («xarajat», kim)", _d_ok.status_code == 200 and _qoldi is None
      and _aud is not None and _aud.company_id == 1 and _aud.performed_by == f"GQ menejer {_n}",
      (_d_ok.status_code, js(_d_ok), _qoldi, _aud and (_aud.performed_by, _aud.entity_label)))
_s = SessionLocal()
_i0 = _s.get(Inventory, ID["sement"])
_q0, _p0 = float(_i0.stock_quantity), float(_i0.price_per_unit or 0)
_et0 = _s.query(ExpenseTransaction).filter(ExpenseTransaction.company_id == 1).count()
_s.close()
_tk = CA.post(f"/api/inventory/{ID['sement']}/stock", json={"quantity_change": 5, "reason": "Kirim (tuzatish): sanoq"})
_s = SessionLocal()
_i1 = _s.get(Inventory, ID["sement"])
_mv = _s.query(InventoryMovement).filter(InventoryMovement.inventory_id == ID["sement"]).order_by(InventoryMovement.id.desc()).first()
_et1 = _s.query(ExpenseTransaction).filter(ExpenseTransaction.company_id == 1).count()
_s.close()
check("A7 G4-13: narxsiz kirim (+5) — qoldiq +5, o'rtacha narx o'zgarmadi, xarajat yozilmadi, harakat «in» sababi bilan",
      _tk.status_code == 200 and abs(float(_i1.stock_quantity) - _q0 - 5) < 1e-9 and float(_i1.price_per_unit or 0) == _p0 and _et1 == _et0
      and _mv.movement_type == "in" and _mv.reason == "Kirim (tuzatish): sanoq",
      (_tk.status_code, _q0, float(_i1.stock_quantity), _p0, float(_i1.price_per_unit or 0), _et0, _et1, _mv and (_mv.movement_type, _mv.reason)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. Yuk xati (PDF)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from pypdf import PdfReader                        # noqa: E402
_s = SessionLocal()
_dv = {}
for _teg, _tol in (("k", "company"), ("m", "client"), ("s", "split")):
    _d = Delivery(order_id=ID["order"], delivery_number=f"GQ-{_n}/Y-{_teg}", transport_carrier=f"GQ Trans {_teg}",
                  transport_cost=60000, transport_payer=_tol)
    if hasattr(Delivery, "company_id"):
        _d.company_id = 1
    _s.add(_d)
    _s.commit()
    _di = DeliveryItem(delivery_id=_d.id, order_item_id=ID["oi"], quantity=1, unit="dona")
    if hasattr(DeliveryItem, "company_id"):
        _di.company_id = 1
    _s.add(_di)
    _s.commit()
    _dv[_teg] = _d.id
_s.close()


def pdf_matn(url):
    r = CA.get(url)
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        return f"KOD {r.status_code}"
    return nb("\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages))


_pk, _pm, _ps = (pdf_matn(f"/api/deliveries/{_dv[t]}/pdf") for t in ("k", "m", "s"))


def transport_qatori(m):
    i = m.find("Transport:")
    return m[i:i + 90].split("\n")[0] if i >= 0 else None


check("P1 G6-13: korxona to'lagan transport — mijoz nusxasida faqat tashuvchi («GQ Trans k»), narx va «Kompaniya to'laydi» YO'Q",
      (transport_qatori(_pk) or "").startswith("Transport: GQ Trans k") and "60 000" not in (transport_qatori(_pk) or "")
      and "Kompaniya" not in _pk, transport_qatori(_pk))
check("P2 G6-13: mijoz to'laydigan / teng bo'lingan — avvalgidek (narx va kim to'laydi)",
      "60 000" in (transport_qatori(_pm) or "") and "Mijoz to'laydi" in (transport_qatori(_pm) or "")
      and "60 000" in (transport_qatori(_ps) or "") and "Teng bo'lingan" in (transport_qatori(_ps) or ""),
      (transport_qatori(_pm), transport_qatori(_ps)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Server chizgan sahifa")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_dh = CA.get("/dashboard").text
check("R1 Dashboard: «Shu oy daromadi», «To'langan» / «Jami byudjet» — «butun vaqt»; «Qarz» va «Bugungi to'lovlar» kartalari yo'q",
      "Shu oy daromadi" in _dh and 'id="f-debt"' not in _dh and 'id="d-today"' not in _dh and "Bugungi to'lovlar" not in _dh
      and _dh.count("butun vaqt") >= 2, None)
_rh_a, _rh_m = CA.get("/returns").text, CM.get("/returns").text
check("R3 G5-05: «Yangi qaytarish» pul savoli — ro'yxatdagi «💰 Hisob-kitob qilish» bilan bir qoida: admin — bor; Menejer (summa ko'rinmaydi) — "
      "yo'q (avvalgidek keyin)", 'id="f-pul-bolim"' in _rh_a and 'id="f-pul-bolim"' not in _rh_m and 'type="radio" name="f-pul"' not in _rh_m
      and "data-summa=" not in _rh_m, ('id="f-pul-bolim"' in _rh_a, 'id="f-pul-bolim"' in _rh_m))
_wr = CA.get("/static/login-bg.webp")
check("R4 .webp — `image/webp` (ilgari `application/octet-stream` + nosniff)", _wr.status_code == 200
      and _wr.headers.get("content-type", "").startswith("image/webp"), (_wr.status_code, _wr.headers.get("content-type")))

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
CHART_SOXTA = """window.Chart = function Chart() { this.data = {datasets: []}; }; window.Chart.prototype.destroy = function () {};
  window.Chart.prototype.update = function () {}; window.Chart.register = function () {};
  window.Chart.defaults = {font: {}, color: '', plugins: {legend: {labels: {}}, tooltip: {}}};"""


def kontekst(rol="admin", w=1440, h=900):
    ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    ctx.route(re.compile(r".*chart\.umd(\.min)?\.js.*"), lambda route: route.fulfill(status=200, content_type="text/javascript", body=CHART_SOXTA))
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""), q.post_data)) if "/api/" in q.url else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", F[rol][0])
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


def tasdiq(pg):
    pg.wait_for_function("() => getComputedStyle(document.getElementById('ccModal')).display !== 'none'")
    return pg.evaluate("() => ({matn: document.getElementById('ccModal').innerText})")


def tasdiqla(pg, ha=True):
    pg.evaluate("(ha) => { const b = ha ? document.getElementById('ccModalOk') : document.getElementById('ccModalCancel'); b.click(); }", ha)


if br:
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/dashboard", wait_until="networkidle")
        pg.wait_for_timeout(800)
        _db1 = pg.evaluate("""() => ({rev: document.getElementById('f-revenue').textContent, sub: document.getElementById('f-revenue-sub').textContent,
            tsub: document.getElementById('t-revenue-sub').textContent, kut: `to'lovlar ${fmt(150000)} · sotuv ${fmt(40000)}`,
            rev2: document.getElementById('t-revenue').textContent, rev2kut: fmt(190000) + " so'm"})""")
        _hist = (js(CA.get("/api/finance/history?months=1")) or [{}])[-1]
        _kut = pg.evaluate("(d) => fmt(d) + \" so'm\"", _hist.get("daromad") or 0)
        check("B1 Dashboard: «Shu oy daromadi» = Hisobotlar «Daromad» (history; shu oy sotuvi bilan — 0 emas), izohda oy; «Bugungi tushum» "
              "190 ming, ostida «to'lovlar 150 ming · sotuv 40 ming» (kartaning o'z ko'rinishi)",
              (_hist.get("daromad") or 0) >= 40000 and nb(_db1["rev"]) == nb(_kut) and "Hisobotlar bilan bir xil" in _db1["sub"]
              and re.match(r"^[A-Z][a-z]+ \d{4} · ", _db1["sub"]) and nb(_db1["tsub"]) == nb(_db1["kut"]) and "150" in _db1["tsub"] and "40" in _db1["tsub"]
              and nb(_db1["rev2"]) == nb(_db1["rev2kut"]), (_db1, _kut, _hist))
        # Omborxona — «Kirim (tuzatish)»
        pg.goto(B + "/inventory", wait_until="networkidle")
        pg.wait_for_timeout(400)
        pg.evaluate(f"""() => {{ const b = [...document.querySelectorAll('.act-btn.in')].find(x => x.getAttribute('onclick').includes('({ID['qum']},')); b.click(); }}""")
        pg.fill("#tk-qty", "3")
        del SOROV[:]
        pg.evaluate("() => saveTuzKirim()")
        pg.wait_for_timeout(300)
        _tx = pg.evaluate("() => document.getElementById('tk-xato').textContent")
        _p0 = [x for x in SOROV if x[0] == "POST" and "/stock" in x[1]]
        pg.fill("#tk-notes", "sanoqda 3 kg ortiq")
        with pg.expect_navigation():
            pg.evaluate("() => saveTuzKirim()")
        _p1 = [json.loads(x[2] or "{}") for x in SOROV if x[0] == "POST" and "/stock" in x[1]]
        check("B2 Omborxona «+» — «Kirim (tuzatish)»: sababsiz — oynada xato, so'rov yo'q; sabab bilan — +3 narxsiz yuboriladi, sahifa yangilanadi",
              "Sababini yozing" in _tx and not _p0 and _p1 == [{"quantity_change": 3, "reason": "Kirim (tuzatish): sanoqda 3 kg ortiq"}],
              (_tx, _p0, _p1))
        # Qaytarish — pul savoli
        pg.goto(B + "/returns", wait_until="networkidle")
        pg.wait_for_timeout(400)
        pg.evaluate("() => showAddModal()")
        pg.check('input[name="f-pul"][value="keyin"]')
        pg.evaluate("() => { closeModal(); showAddModal(); }")
        _qayta = pg.evaluate("() => document.querySelectorAll('input[name=\"f-pul\"]:checked').length")
        check("B2b «Yangi qaytarish» qayta ochilganda pul tanlovi tozalanadi (har safar so'raladi)", _qayta == 0, _qayta)
        pg.evaluate("() => qaytarishBuyurtmalariniYukla()")
        pg.wait_for_function(f"() => [...document.getElementById('f-order').options].some(o => o.value === '{ID['order']}')")
        pg.select_option("#f-order", str(ID["order"]))
        pg.wait_for_function("() => !document.getElementById('f-item').disabled")
        pg.select_option("#f-item", str(ID["oi"]))
        pg.fill("#f-qty", "1")
        pg.dispatch_event("#f-qty", "input")
        del SOROV[:]
        pg.evaluate("() => saveReturn()")
        pg.wait_for_timeout(300)
        _rx = pg.evaluate("() => document.getElementById('add-error').textContent")
        _rp0 = [x for x in SOROV if x[0] == "POST"]
        check("B3 «Yangi qaytarish»: pul masalasi tanlanmasa — saqlanmaydi, «Pul masalasini tanlang …» (ikki variant ko'rinadi)",
              "Pul masalasini tanlang" in _rx and not _rp0 and pg.evaluate("() => document.querySelectorAll('input[name=\"f-pul\"]').length") == 2,
              (_rx, _rp0))
        pg.check('input[name="f-pul"][value="hozir"]')
        pg.evaluate("() => { window.__xabar = []; window.xabarOyna = async (m) => { window.__xabar.push(String(m)); }; }")
        with pg.expect_navigation():
            pg.evaluate("() => saveReturn()")
        _rp1 = [(m, u) for m, u, _ in SOROV if m == "POST"]
        _s = SessionLocal()
        _ri = _s.query(ReturnItem).filter(ReturnItem.order_id == ID["order"]).order_by(ReturnItem.id.desc()).first()
        _s.close()
        check("B4 «Hozir hisob-kitob qilinsin» — qaytarish saqlanadi va DARHOL hisob-kitob (`…/refund`), yozuv «hisob-kitob qilingan»",
              [u for _, u in _rp1][:1] == ["/api/returns"] and any(u == f"/api/returns/{_ri.id}/refund" for _, u in _rp1)
              and _ri.is_refunded is True, (_rp1, _ri and (_ri.id, _ri.is_refunded, _ri.refund_amount)))
        pg.evaluate("() => toggleBrakTahlil()")
        pg.wait_for_function("() => document.querySelector('.brak-asos')")
        _ba = pg.evaluate("() => document.querySelector('.brak-asos').textContent")
        check("B5 brak tahlili: asos tarkibi «buyurtmalar … + omborga …»", nb(_ba).startswith("buyurtmalar ")
              and f"+ omborga {_kut_ombor:,}".replace(",", " ") in nb(_ba), (_ba, _kut_ombor))
    except Exception as _e:                # noqa: BLE001
        check("B! admin ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    ctx, pg = kontekst("menejer", w=390, h=844)
    try:
        pg.goto(B + "/kunlik-xarajat", wait_until="networkidle")
        pg.wait_for_timeout(500)
        _q0 = pg.evaluate("() => [...document.querySelectorAll('.kx-qator')].map(q => q.innerText.split('\\n')[0])")
        pg.fill("#kx-amount", "12000")
        pg.evaluate("() => kxSave()")
        pg.wait_for_function("() => document.querySelectorAll('.kx-qator').length === 2")
        _q1 = pg.evaluate("() => [...document.querySelectorAll('.kx-qator')].map(q => q.innerText.split('\\n')[0])")
        _yangi = pg.evaluate("() => Number(document.querySelector('.kx-qator').dataset.id)")
        del SOROV[:]
        pg.evaluate(f"() => {{ window.__o = kxOchir({_yangi}); }}")
        _tq = tasdiq(pg)
        tasdiqla(pg, True)
        pg.wait_for_function("() => document.querySelectorAll('.kx-qator').length === 1")
        _q2 = pg.evaluate("() => [...document.querySelectorAll('.kx-qator')].map(q => q.innerText.split('\\n')[0])")
        _dl = [u for m, u, _ in SOROV if m == "DELETE"]
        check("B6 Menejer (390 px) «Xarajat qo'shish»: «Bugun siz kiritganlar» — 7 000; yangisi (12 000) ro'yxatga tushadi; «O'chirish» — tasdiq "
              "(summa bilan), o'chadi", [nb(x) for x in _q0] == ["7 000 so'm · Boshqa"] and nb(_q1[0]) == "12 000 so'm · Tushlik"
              and "12 000 so'm" in nb(_tq["matn"]) and _dl == [f"/api/finance/transactions/{_yangi}/ozim"] and [nb(x) for x in _q2] == ["7 000 so'm · Boshqa"],
              (_q0, _q1, _tq, _dl, _q2))
    except Exception as _e:                # noqa: BLE001
        check("B! Menejer ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # Omborxona telefonda (390 px): «+» qo'shilgach ham amal tugmalari ekran ichida, ≥ 32 px, sahifa yonga surilmaydi; oyna sig'adi
    ctx, pg = kontekst("admin", w=390, h=844)
    try:
        pg.goto(B + "/inventory", wait_until="networkidle")
        pg.wait_for_timeout(400)
        _tel = pg.evaluate("""() => { const vw = document.documentElement.clientWidth;
            const r = [...document.querySelectorAll('.act-btn.in')].find(b => b.offsetParent !== null);
            const q = r ? r.closest('.mat-actions') : null;
            const t = q ? [...q.querySelectorAll('.act-btn')].filter(b => b.offsetParent !== null).map(b => { const x = b.getBoundingClientRect();
              return {l: Math.round(x.left), r: Math.round(x.right), w: Math.round(x.width), h: Math.round(x.height)}; }) : [];
            return {vw, sw: document.documentElement.scrollWidth, t}; }""")
        pg.evaluate(f"() => {{ const b = [...document.querySelectorAll('.act-btn.in')].find(x => x.getAttribute('onclick').includes('({ID['qum']},')); b.click(); }}")
        _oy = pg.evaluate("""() => { const m = document.querySelector('#tuzKirimModal > div').getBoundingClientRect();
            return {l: Math.round(m.left), r: Math.round(m.right), vw: document.documentElement.clientWidth}; }""")
        check("B8 Omborxona 390 px: «+», «−», «Tarix» — ekran ichida, ≥ 32 px; sahifa yonga surilmaydi; «Kirim (tuzatish)» oynasi sig'adi",
              len(_tel["t"]) >= 3 and all(x["l"] >= 0 and x["r"] <= _tel["vw"] and x["w"] >= 32 and x["h"] >= 32 for x in _tel["t"])
              and _tel["sw"] <= _tel["vw"] and _oy["l"] >= 0 and _oy["r"] <= _oy["vw"], (_tel, _oy))
    except Exception as _e:                # noqa: BLE001
        check("B! Omborxona telefon", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    check("B7 JS xatosi yo'q", not JS_XATO, JS_XATO)
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
