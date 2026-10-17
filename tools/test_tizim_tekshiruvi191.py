#!/usr/bin/env python3
"""
test_tizim_tekshiruvi191.py — kech150 (zip 191): «Sozlamalar → Tizim salomatligi» moliyaviy izchillik tekshiruvi ANIQ va TUSHUNARLI;
sahifa ochilayotganda kutilmagan xato — o'zbekcha sahifa (xom JSON emas).

NIMA UCHUN KERAK (egasi tanlovi 17.10 «Tizim tekshiruvi»; O'LCHANGAN — `work/k191/probe191.py`, zip 190 kodi, SQLite va PG):
  F1 savatdagi (o'chirilgan) buyurtma detali «Takroriy texnik belgi» va «Ortiqcha topshirilgan» da chiqardi — egasi u buyurtmani ro'yxatda
     topa olmaydi (1, 2, 8-tekshiruvlar esa savatsiz edi). Endi 5 va 6 ham faqat savatda BO'LMAGAN buyurtmalar (tiklansa — yana ko'rinadi).
  F2 yorliq — ichki id «(buyurtma #2)»; endi buyurtma RAQAMI «(ORD-001-2)». Tartib — detal id (birlashtirilgan so'rovda baza tartibi
     kafolatlanmaydi).
  F3 «3,703,701 so'm» (vergul — ming ajratgich), «-13.00 kg», «3.00 / 5.00» — endi YAGONA son qoidasi (`services.son_korinish`: bo'linmas
     bo'shliq, kasr — vergul, ortiqcha nolsiz) va birlik («-13 kg», «3 m … 5,25 m»).
  F4 «Egasiz to'lov / yetkazish» — sahifa (korxona bo'yicha) so'rovida hech qachon ishlamasdi (to'lov / yetkazish korxonaga faqat buyurtma
     orqali bog'lanadi), PG da egasiz yozuvni FK o'zi rad etadi — olib tashlandi (tekshiruvda ham, «Tizim jurnallari» yorliqlarida ham).
  N4 brauzer SAHIFA so'roviga (GET / HEAD, Accept: text/html, `/api/` emas) kutilmagan xato — 500 xom JSON «{"detail": …}» edi; endi
     o'zbekcha sahifa («Sahifa ochilmadi», holat kodi 500, Python xatosi KO'RSATILMAYDI, xato jurnalga avvalgidek yoziladi). API / POST /
     boshqa mijoz — avvalgidek JSON; sahifani chizishning o'zi xato bersa — JSON.
BO'LIMLAR: S — manba (statik); D — dinamik (ilovaning O'Z API si + tekshiruv funksiyasi, ikki korxona); N — xato sahifasi (TestClient).
REJIM: SQLite (standart), `TENANT_FILTER=1` ham; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (egasiz yozuv sinovi
PG da FK rad etishi bilan tasdiqlanadi). Asl kodga (zip 190) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_tizim_tekshiruvi191.py
"""
import os
import re
import io
import sys
import json
import inspect
import tempfile
import contextlib
from datetime import datetime

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tizim_tekshiruvi191_test"
_T = tempfile.mkdtemp(prefix="tizim191_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tizim191.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import (UserRole, Inventory, InventoryPurchase, Project, Order, Delivery, DeliveryItem, Payment,   # noqa: E402
                    PaymentType, PaymentMethod, ErrorLog)
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
NB = " "


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


def oqi(yol):
    return open(os.path.join(ROOT, yol), encoding="utf-8").read()


def _src(f):
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ── S. Manba ──────────────────────────────────────────────────────────────────────────────────────────────────
section("S: izchillik tekshiruvi va xato sahifasi — manba")
FC = _src(crud.check_financial_consistency)
_FC_KOD = "\n".join(re.sub(r"(?:^|\s)#(?:\s.*)?$", "", q) for q in FC.splitlines())   # izohlarsiz (matndagi «(#{…})» qoladi)
check("S1 izchillik matnlarida vergulli / nuqtali format YO'Q (`:,.0f`, `:,.2f`, `:.2f`)",
      FC and not re.search(r"\{[^{}]*:,?\.\d+f\}", _FC_KOD), re.findall(r"\{[^{}]*:,?\.\d+f\}", _FC_KOD))
check("S2 izchillik — yagona son qoidasi `services.son_korinish` va `birlik_korinish`",
      "son_korinish" in _FC_KOD and _FC_KOD.count("_son(") >= 9 and _FC_KOD.count("birlik_korinish(") >= 2,
      (_FC_KOD.count("_son("), _FC_KOD.count("birlik_korinish(")))
check("S3 «Egasiz to'lov / yetkazish» (orphaned_*) tekshiruvi YO'Q",
      "orphaned_payment" not in _FC_KOD and "orphaned_delivery" not in _FC_KOD and "order_ids_set" not in _FC_KOD)
_s56 = re.findall(r"for it in _oic\(db\.query\(OrderItem\)\)[^\n]*\n[^\n]*", _FC_KOD)
check("S4 5 / 6-tekshiruv so'rovi — savatdagi buyurtma chiqarib tashlanadi (Order.is_deleted False), tartib — detal id",
      len(_s56) == 2 and all("Order.is_deleted.is_(False)" in q and "order_by(OrderItem.id)" in q for q in _s56), _s56)
check("S5 5 / 6-tekshiruv yorlig'i — buyurtma RAQAMI (ichki id «#» EMAS)",
      "(buyurtma #{it.order_id})" not in _FC_KOD and _FC_KOD.count("({it.order.order_number})") == 2)
_LOGS = oqi("templates/logs.html")
_tl = re.search(r"const TYPE_LABEL = \{(.*?)\};", _LOGS, re.S)
check("S6 «Tizim jurnallari» yorliqlari: 7 tur bor, orphaned_* YO'Q",
      _tl and "orphaned" not in _tl.group(1) and all(k in _tl.group(1) for k in (
          "order_total_mismatch", "debt_mismatch", "negative_stock", "purchase_total_mismatch", "duplicate_note_marker",
          "over_delivery", "zero_price_item")) and "orphaned" not in _LOGS, _tl and _tl.group(1))
_XS = _src(main._xato_sahifasi)
check("S7 `_xato_sahifasi` — 500 uchun o'z matni («Sahifa ochilmadi»)", "kod >= 500" in _XS and "Sahifa ochilmadi" in _XS)
_GE = _src(main.global_error_logger)
_i_html, _i_json = _GE.find("_html_sahifa_sorovimi(request)"), _GE.rfind("JSONResponse(status_code=500")
check("S8 kutilmagan xato: SAHIFA so'rovi — `_xato_sahifasi(request, 500)` JSON dan OLDIN, chizish xatosida — JSON",
      0 < _i_html < _i_json and "_xato_sahifasi(request, 500)" in _GE[_i_html:_i_json] and "except Exception" in _GE[_i_html:_i_json],
      (_i_html, _i_json))
_i_log = _GE.find("crud.log_error(")
check("S9 xato jurnalga sahifa qaytarilishidan OLDIN yoziladi", 0 < _i_log < _i_html, (_i_log, _i_html))

# ── D. Dinamik — ikki korxona, savatdagi buyurtma, katta / kasrli son ─────────────────────────────────────────────
section("D: moliyaviy izchillik — savat, yorliq, son qoidasi, korxona")
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="T191 Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "t191_a", "Parol123!", UserRole.ADMIN, "T191 A", company_id=1)
    auth.create_user(_db, "t191_b", "Parol123!", UserRole.ADMIN, "T191 B", company_id=2)
INV = {}
for _cid in (1, 2):
    _p = Inventory(company_id=_cid, item_name=f"T191 Penoplast {_cid}", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                   volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
    _m1 = Inventory(company_id=_cid, item_name=f"T191 Akril {_cid}", unit="kg", stock_quantity=-13.0, price_per_unit=25_000,
                    category="Boshqa")
    _m2 = Inventory(company_id=_cid, item_name=f"T191 Profil xom {_cid}", unit="metr", stock_quantity=-1234.5, price_per_unit=9_000,
                    category="Boshqa")
    _db.add_all([_p, _m1, _m2])
    _db.commit()
    INV[_cid] = _p.id
    _db.add(InventoryPurchase(inventory_id=_m1.id, item_name=f"T191 Akril {_cid}", quantity=2.5, unit="kg",
                              price_per_unit=1_000_000, total_amount=1, purchased_by="T191"))
    _db.commit()
PRJ = {}
for _cid in (1, 2):
    _pr = Project(company_id=_cid, client_name=f"T191 Mijoz {_cid}", project_name=f"T191 Loyiha {_cid}", total_budget=0, total_paid=0)
    _db.add(_pr)
    _db.commit()
    PRJ[_cid] = _pr.id
_db.close()

CL = {}
for _cid, _u in ((1, "t191_a"), (2, "t191_b")):
    CL[_cid] = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    CL[_cid].post("/login", data={"username": _u, "password": "Parol123!"}, follow_redirects=False)


def buyurtma(cid, nom):
    t = {"project_id": PRJ[cid], "order_type": "product", "loy_kg": 0, "items": [
        {"name": f"T191 panel {nom}", "category": "panel", "width": 30, "thickness": 5, "quantity": 3, "unit_price": 1_234_567,
         "is_coated": False, "penoplast_id": INV[cid]}]}
    r = CL[cid].post("/api/orders", json=t, params={"confirm_shortage": "true"})
    assert r.status_code == 200, (r.status_code, r.text[:300])
    oid = r.json()["id"]
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        it = o.items[0]
        d = Delivery(order_id=oid, delivery_number=f"T191-Y{oid}", delivered_at=datetime.utcnow(), delivered_by="T191")
        s.add(d)
        s.flush()
        s.add(DeliveryItem(delivery_id=d.id, order_item_id=it.id, quantity=5.25, unit="metr"))   # 3 buyurtma — 5,25 topshirilgan
        it.notes = "[GISHT:1][GISHT:2]"
        o.total_amount = 1                                    # «Buyurtma summasi mos emas»
        s.commit()
        return oid, o.order_number, it.id
    finally:
        s.close()


TIRIK, NOM_T, IT_T = buyurtma(1, "tirik")
SAVAT, NOM_S, IT_S = buyurtma(1, "savat")
TIRIK2, NOM_T2, IT_T2 = buyurtma(1, "tirik2")
BEGONA, NOM_B, IT_B = buyurtma(2, "begona")
_r = CL[1].delete(f"/api/orders/{SAVAT}")
_s = SessionLocal()
check("D0 tayyorgarlik: buyurtma savatga tushdi (DELETE /api/orders)", _r.status_code == 200 and _s.get(Order, SAVAT).is_deleted,
      (_r.status_code, _r.text[:200]))
_s.close()


def tekshiruv(cid):
    r = CL[cid].get("/api/system/health-check")
    return r.status_code, ((r.json() if r.status_code == 200 else {}).get("financial") or {}).get("issues", [])


def tur(iss, t):
    return [x for x in iss if x["type"] == t]


_st, ISS = tekshiruv(1)
check("D1 /api/system/health-check — 200, moliyaviy natija bor", _st == 200 and len(ISS) > 0, (_st, len(ISS)))
_dup = tur(ISS, "duplicate_note_marker")
_ovr = tur(ISS, "over_delivery")
check("D2 «Takroriy texnik belgi»: faqat TIRIK buyurtmalar (savatdagi va begona korxona YO'Q), yorliqda buyurtma RAQAMI",
      [x["label"] for x in _dup] == [f"T191 panel tirik ({NOM_T})", f"T191 panel tirik2 ({NOM_T2})"], [x["label"] for x in _dup])
check("D3 «Ortiqcha topshirilgan»: faqat TIRIK buyurtmalar, detal id tartibida, yorliqda buyurtma RAQAMI",
      [x["label"] for x in _ovr] == [f"T191 panel tirik ({NOM_T})", f"T191 panel tirik2 ({NOM_T2})"], [x["label"] for x in _ovr])
check("D4 «Ortiqcha topshirilgan» matni — son qoidasi va birlik: «Buyurtma qilingan: 3 m, lekin topshirilgan: 5,25 m», farq 2,25",
      _ovr and all(x["detail"] == "Buyurtma qilingan: 3 m, lekin topshirilgan: 5,25 m" and abs(x["diff"] - 2.25) < 1e-9 for x in _ovr),
      [(x["detail"], x["diff"]) for x in _ovr])
_otm = {x["label"]: x["detail"] for x in tur(ISS, "order_total_mismatch")}
check("D5 «Buyurtma summasi mos emas» — «Jami summa: 1 so'm, lekin detallar yig'indisi: 3 703 701 so'm» (bo'linmas bo'shliq)",
      _otm.get(f"Buyurtma {NOM_T}") == f"Jami summa: 1 so'm, lekin detallar yig'indisi: 3{NB}703{NB}701 so'm"
      and f"Buyurtma {NOM_S}" not in _otm, _otm)
_neg = {x["label"]: x["detail"] for x in tur(ISS, "negative_stock")}
check("D6 «Manfiy ombor qoldig'i» — «-13 kg», «-1 234,5 m» (ortiqcha nolsiz, kasr — vergul, birlik ko'rinishi)",
      _neg.get("T191 Akril 1") == "Ombor qoldig'i manfiy: -13 kg"
      and _neg.get("T191 Profil xom 1") == f"Ombor qoldig'i manfiy: -1{NB}234,5 m", _neg)
_ptm = {x["label"]: x["detail"] for x in tur(ISS, "purchase_total_mismatch")}
check("D7 «Xarid summasi mos emas» — «Yozilgan summa: 1 so'm, lekin miqdor×narx: 2 500 000 so'm»",
      _ptm.get("T191 Akril 1") == f"Yozilgan summa: 1 so'm, lekin miqdor×narx: 2{NB}500{NB}000 so'm", _ptm)
_yomon = [x["detail"] for x in ISS if re.search(r"\d,\d{3}(?!\d)|\d\.\d", x["detail"]) or re.search(r"\d \d{3}", x["detail"])]
check("D8 HECH bir matnda vergulli ming ajratgich / nuqtali kasr / oddiy bo'shliqli guruh YO'Q", ISS and not _yomon, _yomon)
check("D9 HECH bir yorliqda ichki id («#57») YO'Q, «Egasiz …» turi YO'Q",
      not [x for x in ISS if "#" in x["label"]] and not [x for x in ISS if x["type"].startswith("orphaned")],
      [x["label"] for x in ISS if "#" in x["label"]])
_hamma = [json.dumps(x, ensure_ascii=False) for x in ISS]
check("D10 begona korxona (B) ma'lumoti A natijasida YO'Q (buyurtma raqami, detal, material)",
      not [h for h in _hamma if "T191 panel begona" in h or "Akril 2" in h or "Profil xom 2" in h], _hamma[:6])
_st_b, ISS_B = tekshiruv(2)
check("D11 B korxonasi o'z tekshiruvida O'Z buyurtmasini ko'radi (raqami bilan), A niki YO'Q",
      _st_b == 200 and [x["label"] for x in tur(ISS_B, "over_delivery")] == [f"T191 panel begona ({NOM_B})"]
      and not [x for x in ISS_B if "T191 panel tirik" in x["label"]], [(x["type"], x["label"]) for x in ISS_B])
_s = SessionLocal()
try:
    _plat = crud.check_financial_consistency(_s, company_id=None)["issues"]
finally:
    _s.close()
check("D12 platforma (korxonasiz) chaqiruvi: ikki korxonaning TIRIK detallari, savatdagi YO'Q, «Egasiz …» YO'Q",
      [x["label"] for x in tur(_plat, "over_delivery")] == [f"T191 panel tirik ({NOM_T})", f"T191 panel tirik2 ({NOM_T2})",
                                                           f"T191 panel begona ({NOM_B})"]
      and not [x for x in _plat if x["type"].startswith("orphaned")], [(x["type"], x["label"]) for x in _plat])
_r = CL[1].post(f"/api/orders/{SAVAT}/restore")
_st2, ISS2 = tekshiruv(1)
check("D13 savatdan TIKLANGAN buyurtma — yana ko'rinadi (sabab — savat, o'chirish emas), tartib detal id bo'yicha",
      _r.status_code == 200 and [x["label"] for x in tur(ISS2, "over_delivery")] == [
          f"T191 panel tirik ({NOM_T})", f"T191 panel savat ({NOM_S})", f"T191 panel tirik2 ({NOM_T2})"]
      and [x["label"] for x in tur(ISS2, "duplicate_note_marker")] == [
          f"T191 panel tirik ({NOM_T})", f"T191 panel savat ({NOM_S})", f"T191 panel tirik2 ({NOM_T2})"],
      (_r.status_code, _r.text[:150], [(x["type"], x["label"]) for x in ISS2]))
CL[1].delete(f"/api/orders/{SAVAT}")
if PG_URL:
    _s = SessionLocal()
    try:
        _s.add(Payment(order_id=999_999, amount=777_777, payment_type=PaymentType.PARTIAL, payment_method=PaymentMethod.CASH))
        _s.commit()
        _rad = False
    except Exception:                      # noqa: BLE001
        _s.rollback()
        _rad = True
    finally:
        _s.close()
    check("D14 [PG] mavjud bo'lmagan buyurtmaga to'lov — bazaning o'zi (FK) rad etadi (olib tashlangan 9-tekshiruv kerak emas)", _rad)
_html = CL[1].get("/logs?tab=health", headers={"Accept": "text/html"})
check("D15 «Tizim jurnallari» sahifasi ochiladi (200), «Egasiz to'lov / yetkazish» yorlig'i YO'Q",
      _html.status_code == 200 and "Egasiz to'lov" not in _html.text and "Egasiz yetkazish" not in _html.text
      and "Ortiqcha topshirilgan" in _html.text, _html.status_code)

# ── N. Kutilmagan xato — sahifa ───────────────────────────────────────────────────────────────────────────────
section("N: sahifa ochilayotganda kutilmagan xato — o'zbekcha sahifa")


@main.app.get("/t191-xato")
def _t191_xato():
    raise RuntimeError("t191 maxfiy ichki xato matni")


@main.app.head("/t191-xato")
def _t191_xato_head():
    raise RuntimeError("t191 maxfiy ichki xato matni (HEAD)")


@main.app.post("/t191-xato")
def _t191_xato_post():
    raise RuntimeError("t191 maxfiy ichki xato matni (POST)")


@main.app.get("/hodim/t191-xato")
def _t191_xato_hodim():
    raise RuntimeError("t191 maxfiy ichki xato matni (hodim)")


@main.app.get("/api/t191-xato")
def _t191_xato_api():
    raise RuntimeError("t191 maxfiy ichki xato matni (api)")


_HTML = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
_s = SessionLocal()
_el0 = _s.query(ErrorLog).filter(ErrorLog.endpoint == "/t191-xato").count()
_s.close()
r = CL[1].get("/t191-xato", headers=_HTML)
check("N1 brauzer sahifa so'rovi: 500, text/html, «Sahifa ochilmadi» va tushuntirish",
      r.status_code == 500 and "text/html" in (r.headers.get("content-type") or "") and "Sahifa ochilmadi" in r.text
      and "Serverda kutilmagan xato yuz berdi" in r.text and "administratorga ayting" in r.text,
      (r.status_code, r.headers.get("content-type"), r.text[:200]))
check("N2 sahifada Python xatosi / ichki matn YO'Q", r.status_code == 500 and "RuntimeError" not in r.text
      and "t191 maxfiy" not in r.text and "Traceback" not in r.text and '"detail"' not in r.text, r.text[:300])
check("N3 sahifada «Bosh sahifaga» (/) va «Orqaga» tugmalari, kod 500",
      'id="xsBosh" href="/"' in r.text and 'id="xsOrqaga"' in r.text and '<div class="xs-kod">500</div>' in r.text, r.text[:200])
_s = SessionLocal()
_el = _s.query(ErrorLog).filter(ErrorLog.endpoint == "/t191-xato").order_by(ErrorLog.id.desc()).all()
_s.close()
check("N4 xato «Tizim jurnallari → Xatoliklar» ga AVVALGIDEK yozildi (xabar, korxona, kim)",
      len(_el) == _el0 + 1 and "t191 maxfiy ichki xato matni" in (_el[0].error_message or "") and _el[0].company_id == 1
      and (_el[0].performed_by or "") == "T191 A", [(e.error_message, e.company_id, e.performed_by) for e in _el[:2]])
r = CL[1].get("/hodim/t191-xato", headers=_HTML)
check("N5 hodim paneli yo'li: o'sha sahifa, «Bosh sahifaga» — /hodim",
      r.status_code == 500 and "Sahifa ochilmadi" in r.text and 'id="xsBosh" href="/hodim"' in r.text, (r.status_code, r.text[:200]))
r = CL[1].get("/t191-xato", headers={"Accept": "*/*"})
check("N6 boshqa mijoz (Accept */*): avvalgidek JSON", lambda: r.status_code == 500 and r.json() == {"detail": "Serverda kutilmagan xato yuz berdi"},
      (r.status_code, r.text[:200]))
r = CL[1].get("/api/t191-xato", headers=_HTML)
check("N7 /api/ yo'li (brauzer Accept bilan ham): JSON", lambda: r.status_code == 500 and r.json() == {"detail": "Serverda kutilmagan xato yuz berdi"},
      (r.status_code, r.text[:200]))
r = CL[1].post("/t191-xato", headers=_HTML)
check("N8 POST (forma / fetch): JSON", lambda: r.status_code == 500 and r.json() == {"detail": "Serverda kutilmagan xato yuz berdi"},
      (r.status_code, r.text[:200]))
r = CL[1].head("/t191-xato", headers=_HTML)
check("N9 HEAD (sahifa): 500, text/html", r.status_code == 500 and "text/html" in (r.headers.get("content-type") or ""),
      (r.status_code, r.headers.get("content-type")))
_asl_xs = main._xato_sahifasi


def _buzuq_xs(request, kod, izoh=None):
    raise RuntimeError("t191 sahifa chizilmadi")


main._xato_sahifasi = _buzuq_xs
try:
    r = CL[1].get("/t191-xato", headers=_HTML)
finally:
    main._xato_sahifasi = _asl_xs
check("N10 sahifani chizishning o'zi xato bersa — JSON (sahifa so'rovi ham javobsiz qolmaydi)",
      lambda: r.status_code == 500 and r.json() == {"detail": "Serverda kutilmagan xato yuz berdi"}, (r.status_code, r.text[:200]))
r = CL[1].get("/t191-yoq-sahifa", headers=_HTML)
check("N11 yo'q sahifa (404) — o'zgarmagan: «Bunday sahifa yo'q»", r.status_code == 404 and "Bunday sahifa yo" in r.text
      and "Sahifa ochilmadi" not in r.text, (r.status_code, r.text[:200]))
_anon = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
r = _anon.get("/t191-xato", headers=_HTML)
check("N12 tizimga kirmagan foydalanuvchi ham — o'zbekcha sahifa (base.html siz shablon)",
      r.status_code == 500 and "Sahifa ochilmadi" in r.text and "t191 maxfiy" not in r.text, (r.status_code, r.text[:200]))

print(f"\n{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
