#!/usr/bin/env python3
"""
test_taminot180.py — kech144 (zip 180, AUDIT 2-to'lqin — «Ta'minotchilar» + «Xomashyo kirimi»;
`work/k180_tayyorgarlik/agentlar/taminot/HISOBOT.md`): takror so'rov ikkinchi yozuv yaratmaydi, yuklovchilar sababni ko'rsatadi,
ruxsatsiz tugmalar ko'rinmaydi, qoralama boshqa ta'minotchiga ko'chmaydi. SERVER (TestClient) + HAQIQIY Chromium, HAQIQIY lokal server.

NIMA UCHUN KERAK (asl kod = zip 179):
  A1  «Kirimni tasdiqlash» — 502 / javob yo'qolsa «❌ Xato: Kirim saqlanmadi» (server saqlagan bo'lishi mumkin), savat turgani uchun qayta
      bosish IKKINCHI kirim yozardi (ombor ikki baravar, qarz va kassa ikki marta).
  A2  «+ Xarid qo'shish» savati — har qator alohida, kalitsiz: biri yo'qolsa savat tozalanardi, qayta kiritish saqlanganlarini ikki marta yozardi.
  A3  Ta'minotchiga to'lov — 8 s dan keyin qayta yuborish ikkinchi to'lov yozardi.   A4  «+ Ta'minotchi» — ikki marta bosish ikki ta'minotchi.
  B2 / B3  Xaridni parallel tahrirlash / o'chirish (PostgreSQL) — ombor xarid miqdoridan ajrab ketardi.
  B6  Kirimda «Hozir to'langan» jamidan ko'p — server jimgina qisqartirardi.   B9  8 s oynasi haqiqiy to'lovni yutardi.
  C1 / C2  Yuklovchilar — 401 / 5xx da «0 so'm», oldingi ta'minotchi ma'lumoti (to'lov YANGI ta'minotchiga ketardi), abadiy «Yuklanmoqda...».
  C3  Ruxsatsiz tugmalar ko'rinardi (bosilsa 403).   C4  Qoralama boshqa ta'minotchiga ko'chardi, korxona / foydalanuvchi bo'yicha emas edi.
  C5  POST javobida materialning o'rtacha narxi (narx ruxsati yo'qqa ham).   C6  Kirim qatori «Jami» butun so'mga.
  C7  Tarix: `page_size=0` / noto'g'ri sana — 500.   D1  Xato matnlari: «Xato yuz berdi», «Failed to fetch», `Kirim saqlashda xato: <SQL>`.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (B2 / B3 parallel sinovlari — faqat PG). Asl kodga (zip 179) qarshi
QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_taminot180.py
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
PG_BAZA = "taminot180_test"
_T = tempfile.mkdtemp(prefix="tm180_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tm180.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, Rol, Inventory, InventoryPurchase, InventoryReceipt, Supplier,   # noqa: E402
                    SupplierPayment, ErrorLog)
from models import TransportExpense                # noqa: E402  — kech146 (R180i)
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


def qoldiq(mid):
    return db_ishi(lambda s: round(float(s.get(Inventory, mid).stock_quantity or 0), 6))


def tolovlar(sid):
    return db_ishi(lambda s: [round(float(p.amount), 2) for p in s.query(SupplierPayment).filter_by(supplier_id=sid)
                              .order_by(SupplierPayment.id).all()])


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t180_admin", PAROL, UserRole.ADMIN, "T180 Admin", company_id=1)
    for _u in ("t180_kor", "t180_kir"):
        auth.create_user(s, _u, PAROL, UserRole.MANAGER, _u.upper(), company_id=1)
s.close()
# «Ta'minotchilar» — faqat ko'rish (C3); «Kirim» — faqat kirim yaratish, narx ruxsatisiz (C2, C3, C5)
rol_qoy("t180_kor", {"taminotchi": ["korish"], "kirim": ["korish"], "material": ["korish"]}, "T180 Ta'minotchi ko'ruvchi")
rol_qoy("t180_kir", {"kirim": ["yaratish"], "material": ["korish"]}, "T180 Kirimchi")
UID = db_ishi(lambda d: {u.username: u.id for u in d.query(User).filter(User.username.like("t180_%")).all()})

TG = []
main._send_telegram = lambda msg, *a, **k: (TG.append(str(msg)), True)[1]


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


C = mijoz("t180_admin")
CK = mijoz("t180_kir")


def taminotchi(nom):
    r = C.post("/api/suppliers", json={"name": nom, "phone": "+998901112233"})
    assert r.status_code == 200, r.text
    return js(r)["id"]


def material(nom, qold=0.0, narx=1000.0):
    r = C.post("/api/inventory", json={"item_name": nom, "unit": "kg", "category": "Kimyoviy qo'shimchalar",
                                       "stock_quantity": qold, "price_per_unit": narx, "min_stock": 0})
    assert r.status_code == 200, r.text
    return js(r)["id"]


def kirim(c, sup, qatorlar, paid_now=0.0, kalit=None, sana=None):
    tana = {"items": [{"inventory_id": m, "quantity": q, "price_per_unit": n} for m, q, n in qatorlar],
            "transport_cost": 0, "tushirish_cost": 0, "yuklash_cost": 0, "boshqa_cost": 0, "add_to_cost": False,
            "supplier_id": sup, "document_number": None, "paid_now": paid_now, "notes": "T180"}
    if sana:
        tana["receipt_date"] = sana
    return c.post("/api/inventory/receipt", json=tana, headers={"X-Amal-Kaliti": kalit} if kalit else {})


def xarid(c, mid, sup, q, n, paid_now=0.0, kalit=None):
    return c.post(f"/api/inventory/{mid}/purchase", json={"quantity": q, "price_per_unit": n, "paid_now": paid_now,
                                                          "supplier_id": sup, "notes": "T180"},
                  headers={"X-Amal-Kaliti": kalit} if kalit else {})


def tolov(c, sup, summa, kalit=None, tasdiq=False):
    return c.post(f"/api/suppliers/{sup}/payment", json={"supplier_id": sup, "amount": summa, "confirm_overpay": tasdiq},
                  headers={"X-Amal-Kaliti": kalit} if kalit else {})


SA, SB, SC = taminotchi("T180 Alfa"), taminotchi("T180 Beta"), taminotchi("T180 Gamma")
M1, M2, M3 = material("T180 Akril"), material("T180 Boyoq"), material("T180 Sement", qold=100.0)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Server — takror so'rov, sabab, sahifalash, narx sirini (A1–A4, B9, C5, C7, D1)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_q0, _k0, _t0 = qoldiq(M1), soni(InventoryReceipt, supplier_id=SA), len(tolovlar(SA))
_r1 = kirim(C, SA, [(M1, 10, 1000)], paid_now=4000, kalit="t180kirimkalit0001")
_r2 = kirim(C, SA, [(M1, 10, 1000)], paid_now=4000, kalit="t180kirimkalit0001")
check("S1 (A1) kirim — o'sha kalit bilan ikkinchi so'rov: 200, `takror`, `X-Takror: 1`, o'sha hujjat raqami",
      _r1.status_code == 200 and _r2.status_code == 200 and js(_r2).get("takror") is True and _r2.headers.get("x-takror") == "1"
      and js(_r1).get("receipt_id") == js(_r2).get("receipt_id"), (_r1.status_code, _r2.status_code, js(_r2), dict(_r2.headers)))
check("S1b (A1) kirim BITTA: hujjat +1, ombor +10 (ikki emas), «Kirim to'lovi» bitta",
      soni(InventoryReceipt, supplier_id=SA) == _k0 + 1 and qoldiq(M1) == _q0 + 10 and len(tolovlar(SA)) == _t0 + 1,
      (soni(InventoryReceipt, supplier_id=SA) - _k0, qoldiq(M1) - _q0, tolovlar(SA)))
_k1 = soni(InventoryReceipt, supplier_id=SA)
kirim(C, SA, [(M1, 1, 1000)])
kirim(C, SA, [(M1, 1, 1000)])
check("S2 NAZORAT: kalitsiz ikki kirim — ikkalasi yoziladi (kalitsiz xulq o'zgarmagan)", soni(InventoryReceipt, supplier_id=SA) == _k1 + 2,
      soni(InventoryReceipt, supplier_id=SA) - _k1)

_asl_kirim = crud.create_inventory_receipt
_xl0 = db_ishi(lambda d: d.query(ErrorLog).filter(ErrorLog.endpoint == "api_create_inventory_receipt").count())


def _buzuq(*a, **k):
    raise RuntimeError("UNIQUE constraint failed: t180_maxfiy_jadval.ustun")


crud.create_inventory_receipt = _buzuq
try:
    _r3 = kirim(C, SA, [(M1, 2, 1000)], kalit="t180kirimkalit0002")
finally:
    crud.create_inventory_receipt = _asl_kirim
_d3 = str(js(_r3).get("detail"))
check("S3 (D1) kirim — kutilmagan xato: 500, o'zbekcha «Kirim saqlanmadi — server xatosi», ichki xato matni (SQL) YO'Q",
      _r3.status_code == 500 and "Kirim saqlanmadi" in _d3 and "UNIQUE" not in _d3 and "Kirim saqlashda xato" not in _d3, (_r3.status_code, _d3))
check("S3b (D1) sabab «Xatoliklar» jurnalida (stek bilan)",
      db_ishi(lambda d: d.query(ErrorLog).filter(ErrorLog.endpoint == "api_create_inventory_receipt",
                                                 ErrorLog.error_message.like("%UNIQUE%")).count()) == _xl0 + 1)
_k2 = soni(InventoryReceipt, supplier_id=SA)
_r3c = kirim(C, SA, [(M1, 2, 1000)], kalit="t180kirimkalit0002")
check("S3c xato bergan so'rov kaliti saqlanmagan — o'sha kalit bilan qayta: bajariladi (takror emas)",
      _r3c.status_code == 200 and not js(_r3c).get("takror") and soni(InventoryReceipt, supplier_id=SA) == _k2 + 1, (_r3c.status_code, js(_r3c)))

_p0, _q0, TG[:] = soni(InventoryPurchase, supplier_id=SA, inventory_id=M2), qoldiq(M2), []
_r4 = xarid(C, M2, SA, 5, 1000, kalit="t180xaridkalit00001")
_r4b = xarid(C, M2, SA, 5, 1000, kalit="t180xaridkalit00001")
check("S4 (A2) xarid — o'sha kalit: 200 `takror`, xarid BITTA, ombor +5, Telegram BITTA",
      _r4.status_code == 200 and js(_r4b).get("takror") is True and soni(InventoryPurchase, supplier_id=SA, inventory_id=M2) == _p0 + 1
      and qoldiq(M2) == _q0 + 5 and len(TG) == 1, (_r4.status_code, js(_r4b), qoldiq(M2) - _q0, len(TG)))
check("S4b NAZORAT: admin (narx ruxsati bor) — javobda o'rtacha narx bor",
      isinstance(js(_r4).get("old_price"), (int, float)) and isinstance(js(_r4).get("new_price"), (int, float)), js(_r4))

_n0 = soni(Supplier, name="T180 Ikki marta")
_r5 = C.post("/api/suppliers", json={"name": "T180 Ikki marta"}, headers={"X-Amal-Kaliti": "t180taminotkalit01"})
_r5b = C.post("/api/suppliers", json={"name": "T180 Ikki marta"}, headers={"X-Amal-Kaliti": "t180taminotkalit01"})
check("S5 (A4) yangi ta'minotchi — o'sha kalit: bitta ta'minotchi, ikkinchi javob — o'sha id (`takror`)",
      _r5.status_code == 200 and js(_r5b).get("takror") is True and js(_r5b).get("id") == js(_r5).get("id")
      and soni(Supplier, name="T180 Ikki marta") == _n0 + 1, (js(_r5), js(_r5b)))

_t0 = len(tolovlar(SA))
_r6 = tolov(C, SA, 1000, kalit="t180tolovkalit0001")
_r6b = tolov(C, SA, 1000, kalit="t180tolovkalit0001")
check("S6 (A3) to'lov — o'sha kalit: bitta to'lov, ikkinchi javob `takror`",
      _r6.status_code == 200 and js(_r6b).get("takror") is True and len(tolovlar(SA)) == _t0 + 1, (js(_r6), js(_r6b), tolovlar(SA)))
tolov(C, SA, 700, kalit="t180tolovkalit0002")
tolov(C, SA, 700, kalit="t180tolovkalit0003")
check("S6b (B9) ikki HAR XIL kalit, bir xil summa, 8 s ichida — ikkalasi yoziladi (kalit takrorni aniq ajratadi)",
      len(tolovlar(SA)) == _t0 + 3, tolovlar(SA))
tolov(C, SA, 300)
tolov(C, SA, 300)
check("S6c NAZORAT: kalitsiz ikki bir xil to'lov 8 s ichida — bittasi (eski himoya qoldi)", len(tolovlar(SA)) == _t0 + 4, tolovlar(SA))

_t0 = len(tolovlar(SB))
_r7 = xarid(C, M2, SB, 1, 1000, paid_now=400)
_r7b = tolov(C, SB, 400)
check("S7 (B9) xarid bilan birga to'langan 400 dan keyin 8 s ichida ESKI qarzga 400 — ikkalasi yoziladi (ilgari ikkinchisi «yutilardi»)",
      _r7.status_code == 200 and _r7b.status_code == 200 and len(tolovlar(SB)) == _t0 + 2, (js(_r7b), tolovlar(SB)))
_r8 = tolov(C, SB, 5000000)
_m8 = str((js(_r8).get("detail") or {}).get("message") if isinstance(js(_r8).get("detail"), dict) else js(_r8).get("detail"))
check("S8 (D1) ortiqcha to'lov ogohlantirishi — ming ajratgichi bo'shliq («5 000 000»; ilgari «5,000,000»)",
      _r8.status_code == 409 and "5 000 000" in _m8 and "5,000,000" not in _m8, (_r8.status_code, _m8))

_h = {
    "page_size=0": C.get(f"/api/suppliers/{SA}/history?page=1&page_size=0").status_code,
    "page=0": C.get(f"/api/suppliers/{SA}/history?page=0&page_size=5").status_code,
    "page_size=101": C.get(f"/api/suppliers/{SA}/history?page=1&page_size=101").status_code,
}
check("S9 (C7) tarix: `page_size=0` / `page=0` / `page_size=101` — 422 (ilgari 0 — 500)", set(_h.values()) == {422}, _h)
_r9 = C.get(f"/api/suppliers/{SA}/history?start_date=2026-13-45")
_r9b = C.get(f"/api/suppliers/{SA}/history?end_date=abc")
check("S9b (C7) noto'g'ri sana — 400 va sabab (ilgari 500)",
      _r9.status_code == 400 and "Boshlanish sanasi noto'g'ri" in str(js(_r9).get("detail"))
      and _r9b.status_code == 400 and "Tugash sanasi noto'g'ri" in str(js(_r9b).get("detail")), (_r9.status_code, js(_r9), _r9b.status_code))
check("S9c NAZORAT: to'g'ri so'rov — 200", C.get(f"/api/suppliers/{SA}/history?page=1&page_size=5&start_date=2026-01-01").status_code == 200)

_mats = [material(f"T180 Qator {i}") for i in range(7)]
_r10 = kirim(C, SC, [(m, 1 + i, 100) for i, m in enumerate(_mats)], sana="2026-09-01")
_ids = []
for _sah in (1, 2, 3):
    _ids += [p["id"] for p in js(C.get(f"/api/suppliers/{SC}/history?page={_sah}&page_size=3")).get("purchases", [])]
check("S10 (C7) bir hujjatning 7 qatori (bir xil vaqt) — 3 tadan sahifalarda har biri AYNAN bir marta",
      _r10.status_code == 200 and len(_ids) == 7 and len(set(_ids)) == 7, (_r10.status_code, _ids))

_r11 = kirim(CK, SA, [(M1, 1, 1000)])
_r11b = xarid(CK, M1, SA, 1, 1000)
_res11 = (js(_r11).get("results") or [{}])[0]
check("S11 (C5) narx ruxsati yo'q — kirim javobida `results[].old_price` / `new_price` null",
      _r11.status_code == 200 and "old_price" in _res11 and _res11.get("old_price") is None and _res11.get("new_price") is None,
      (_r11.status_code, js(_r11)))
check("S11b (C5) narx ruxsati yo'q — xarid javobida `old_price` / `new_price` null",
      _r11b.status_code == 200 and "old_price" in js(_r11b) and js(_r11b).get("old_price") is None and js(_r11b).get("new_price") is None,
      (_r11b.status_code, js(_r11b)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Egasi qarorlari 14.10 — ta'minotchini yashirish, to'langan xaridni o'chirish / tahrirlash (B1, B5, B4)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
QA, QB = taminotchi("T180 Yashirin"), taminotchi("T180 Toza")
MQ = material("T180 Gips", qold=0.0)
xarid(C, MQ, QA, 2, 1000, paid_now=500)
_qt0 = tolovlar(QA)
_rq1 = C.delete(f"/api/suppliers/{QA}?force=true")
_sq1 = db_ishi(lambda d: d.get(Supplier, QA).is_active if d.get(Supplier, QA) is not None else "yo'q")
check("Q1 (B1 «Yashirilsin») tarixi bor ta'minotchi — 200 `yashirildi`, bazada qoldi (`is_active` False), to'lovlari O'ZGARMADI",
      _rq1.status_code == 200 and js(_rq1).get("yashirildi") is True and _sq1 is False
      and tolovlar(QA) == _qt0, (_rq1.status_code, js(_rq1), tolovlar(QA), _qt0))
check("Q1b yashirilgan ta'minotchi ro'yxatda YO'Q", all(s.get("id") != QA for s in (js(C.get("/api/suppliers")) or [])))
_rq2 = C.delete(f"/api/suppliers/{QB}")
check("Q2 NAZORAT: tarixsiz ta'minotchi — butunlay o'chadi (`yashirildi` False)",
      _rq2.status_code == 200 and js(_rq2).get("yashirildi") is False and db_ishi(lambda d: d.get(Supplier, QB)) is None, js(_rq2))


def _qxarid(qty, narx, tolov):
    r = xarid(C, MQ, SB, qty, narx, paid_now=tolov)
    assert r.status_code == 200, r.text
    return db_ishi(lambda d: d.query(InventoryPurchase.id).filter_by(inventory_id=MQ, supplier_id=SB).order_by(InventoryPurchase.id.desc()).first()[0])


_PID = getattr(SupplierPayment, "purchase_id", None)     # asl kodda (zip 179) ustun yo'q — sinov qulamasin


def _bogtolov(pid):
    if _PID is None:
        return ["ustun yo'q"]
    return db_ishi(lambda d: [(round(float(p.amount), 2), p.notes, p.purchase_id) for p in d.query(SupplierPayment).filter(
        SupplierPayment.supplier_id == SB, _PID == pid).all()])


def _avans(pid):
    # SQLite o'chirilgan oxirgi id ni qayta beradi — avans izohidagi raqam bilan faqat o'chirishdan DARHOL keyin qidiriladi
    return db_ishi(lambda d: [(round(float(p.amount), 2), p.notes, getattr(p, "purchase_id", None)) for p in d.query(SupplierPayment).filter(
        SupplierPayment.supplier_id == SB, SupplierPayment.notes.like(f"Avans (bekor qilingan xarid #{pid}:%")).all()])


_q3 = _qxarid(10, 100, 400)
_qq0 = qoldiq(MQ)
_r3 = C.delete(f"/api/inventory/purchases/{_q3}")
_d3 = js(_r3).get("detail") or {}
check("Q3 (B5 «Har safar so'rasin») 400 so'm darhol to'langan xarid — tanlovsiz 409 `purchase_has_payment`, HECH NARSA o'zgarmadi",
      _r3.status_code == 409 and isinstance(_d3, dict) and _d3.get("type") == "purchase_has_payment" and float(_d3.get("summa") or 0) == 400
      and "400 so'm" in str(_d3.get("message")) and db_ishi(lambda d: d.get(InventoryPurchase, _q3)) is not None and qoldiq(MQ) == _qq0,
      (_r3.status_code, _d3))
_r3b = C.delete(f"/api/inventory/purchases/{_q3}?tolov=avans")
_b3 = _avans(_q3)
check("Q3b `tolov=avans` — xarid o'chdi, to'lov QOLDI (izoh «Avans (bekor qilingan xarid #…)», bog'lanish uzildi)",
      _r3b.status_code == 200 and db_ishi(lambda d: d.get(InventoryPurchase, _q3)) is None and len(_b3) == 1 and _b3[0][0] == 400
      and _b3[0][1].startswith("Avans (bekor qilingan xarid #") and _b3[0][2] is None and qoldiq(MQ) == _qq0 - 10, (_r3b.status_code, _b3))
_q4 = _qxarid(5, 100, 200)
_r4 = C.delete(f"/api/inventory/purchases/{_q4}?tolov=ochirish")
check("Q4 `tolov=ochirish` — xarid ham, to'lovi ham o'chdi", _r4.status_code == 200 and _bogtolov(_q4) == []
      and db_ishi(lambda d: d.get(InventoryPurchase, _q4)) is None, (_r4.status_code, _bogtolov(_q4)))
_q4b = _qxarid(1, 100, 50)
check("Q4b noto'g'ri tanlov — 400", C.delete(f"/api/inventory/purchases/{_q4b}?tolov=xato").status_code == 400)
C.delete(f"/api/inventory/purchases/{_q4b}?tolov=ochirish")
_q5 = _qxarid(10, 100, 400)
if _PID is not None:
    db_ishi(lambda d: d.query(SupplierPayment).filter(_PID == _q5).update({"purchase_id": None}))
_r5 = C.delete(f"/api/inventory/purchases/{_q5}")
check("Q5 eski to'lov (bog'lanmagan — ustungacha yozilgan) ham topiladi: izoh + vaqt bo'yicha → 409",
      _r5.status_code == 409 and (js(_r5).get("detail") or {}).get("type") == "purchase_has_payment", (_r5.status_code, js(_r5)))
C.delete(f"/api/inventory/purchases/{_q5}?tolov=ochirish")
_q6 = _qxarid(10, 100, 400)
_r6 = C.put(f"/api/inventory/purchases/{_q6}", json={"quantity": 3})
_d6 = js(_r6).get("detail") or {}
check("Q6 (B4) 1 000 lik xarid (400 to'langan) → 300: tanlovsiz 409 `purchase_payment_excess`, ortiqcha 100, HECH NARSA o'zgarmadi",
      _r6.status_code == 409 and isinstance(_d6, dict) and _d6.get("type") == "purchase_payment_excess" and float(_d6.get("summa") or 0) == 100
      and float(db_ishi(lambda d: d.get(InventoryPurchase, _q6).quantity)) == 10, (_r6.status_code, _d6))
_r6b = C.put(f"/api/inventory/purchases/{_q6}?tolov=ochirish", json={"quantity": 3})
check("Q6b `tolov=ochirish` — ortiqcha to'lovdan ayirildi (to'lov 300), miqdor 3",
      _r6b.status_code == 200 and [x[0] for x in _bogtolov(_q6)] == [300.0]
      and float(db_ishi(lambda d: d.get(InventoryPurchase, _q6).quantity)) == 3, (_r6b.status_code, _bogtolov(_q6)))
_q7 = _qxarid(10, 100, 400)
_r7 = C.put(f"/api/inventory/purchases/{_q7}?tolov=avans", json={"quantity": 2})
check("Q7 `tolov=avans` — to'lov o'zgarmadi (400), miqdor 2 (ortiqcha 200 — avans)",
      _r7.status_code == 200 and [x[0] for x in _bogtolov(_q7)] == [400.0], (_r7.status_code, _bogtolov(_q7)))
_r7b = C.put(f"/api/inventory/purchases/{_q7}", json={"quantity": 20})
check("Q7b NAZORAT: summani OSHIRISH — so'ralmaydi (200)", _r7b.status_code == 200, (_r7b.status_code, js(_r7b)))
_q9a, _q9b = _qxarid(3, 100, 100), _qxarid(3, 100, 100)
_r9 = C.delete(f"/api/inventory/purchases/{_q9a}")
check("Q9 bir daqiqada bir xil ikki xarid (ikkalasi qisman to'langan) — to'lov xaridga BOG'LANGAN: o'chirishda so'raladi (409)",
      _r9.status_code == 409 and (js(_r9).get("detail") or {}).get("type") == "purchase_has_payment"
      and [x[0] for x in _bogtolov(_q9a)] == [100.0], (_r9.status_code, js(_r9), _bogtolov(_q9a)))
C.delete(f"/api/inventory/purchases/{_q9a}?tolov=ochirish")
C.delete(f"/api/inventory/purchases/{_q9b}?tolov=ochirish")
_rk = kirim(C, SB, [(MQ, 10, 100), (M2, 5, 100)], paid_now=1500)
_kid = js(_rk).get("receipt_id")
_kq = db_ishi(lambda d: d.query(InventoryPurchase.id).filter_by(receipt_id=_kid, inventory_id=MQ).first()[0])
_r8 = C.put(f"/api/inventory/purchases/{_kq}", json={"quantity": 5})
_d8 = js(_r8).get("detail") or {}
_kt = lambda: db_ishi(lambda d: [round(float(p.amount), 2) for p in d.query(SupplierPayment).filter(
    SupplierPayment.notes.like(f"Kirim to%lovi — #{_kid}%")).all()])
check("Q8 (B4) Kirim hujjati qatori 1 000 → 500 (hujjat 1 500 to'langan): 409, ortiqcha 500, «Kirim #…» deb aytiladi",
      _rk.status_code == 200 and _r8.status_code == 409 and isinstance(_d8, dict) and _d8.get("type") == "purchase_payment_excess"
      and float(_d8.get("summa") or 0) == 500 and f"Kirim #{_kid}" in str(_d8.get("message")), (_rk.status_code, _r8.status_code, _d8))
_r8b = C.put(f"/api/inventory/purchases/{_kq}?tolov=ochirish", json={"quantity": 5})
check("Q8b `tolov=ochirish` — hujjat to'lovi 1 000 ga tushdi", _r8b.status_code == 200 and _kt() == [1000.0], (_r8b.status_code, _kt()))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. «Jami xarid» va boshlang'ich ombor (B7, B8)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
SJ = taminotchi("T180 Iota")
MJ, MJ2 = material("T180 Gips J"), material("T180 Shpaklyovka J")
_rj1 = xarid(C, MJ, SJ, 10, 100000, paid_now=1000000)      # naqd — darhol TO'LIQ to'langan (nasiya emas)
_rj2 = xarid(C, MJ, SJ, 5, 100000)                         # nasiya 500 000
_dj = js(C.get(f"/api/suppliers/{SJ}/history"))
check("J1 (B7) 1 000 000 naqd + 500 000 nasiya — `total_purchases` 1 500 000, `paid_cash` 1 000 000; `total_credit` 500 000, qarz "
      "500 000 (qarz qoidasi o'zgarmagan; ilgari Kirim sahifasi «Jami xarid» = 500 000)",
      _rj1.status_code == 200 and _rj2.status_code == 200 and _dj.get("total_purchases") == 1500000 and _dj.get("paid_cash") == 1000000
      and _dj.get("total_credit") == 500000 and _dj.get("debt") == 500000 and _dj.get("total_paid") == 0,
      (_rj1.status_code, _rj2.status_code, {k: _dj.get(k) for k in ("total_purchases", "paid_cash", "total_credit", "total_paid", "debt")}))
_rj3 = tolov(C, SJ, 200000)
_dj3 = js(_rj3)
check("J2 (B7) to'lov javobi ham — `total_purchases` 1 500 000, qarz 300 000",
      _rj3.status_code == 200 and _dj3.get("total_purchases") == 1500000 and _dj3.get("debt") == 300000, (_rj3.status_code, _dj3))
_rj4 = C.post("/api/inventory/receipt", json={
    "items": [{"inventory_id": MJ2, "quantity": 3, "price_per_unit": 1000, "is_opening_stock": True},
              {"inventory_id": MJ, "quantity": 2, "price_per_unit": 1000}],
    "transport_cost": 0, "tushirish_cost": 0, "yuklash_cost": 0, "boshqa_cost": 0, "add_to_cost": False,
    "supplier_id": SJ, "document_number": None, "paid_now": 2000, "notes": "T180 J"})
_jkid = js(_rj4).get("receipt_id")
_dj4 = js(C.get(f"/api/suppliers/{SJ}/history"))
_jh = {p.get("item_name"): p.get("kirimda_tolangan") for p in (_dj4.get("purchases") or []) if p.get("receipt_id") == _jkid}
check("J3 (B8) kirim: boshlang'ich 3 000 + nasiya 2 000, «hozir to'langan» 2 000 — boshlang'ich qator `boshlangich`, nasiya qatori "
      "`tolangan` (ilgari ikkalasi «Qisman» — hujjat jami boshlang'ichni ham sanardi)",
      _rj4.status_code == 200 and _jh == {"T180 Shpaklyovka J": "boshlangich", "T180 Gips J": "tolangan"}, (_rj4.status_code, _jh))
check("J4 (B7) boshlang'ich ombor «Jami xarid» ga kirmaydi: 1 500 000 + 2 000 = 1 502 000; qarz o'zgarmadi (300 000)",
      _dj4.get("total_purchases") == 1502000 and _dj4.get("debt") == 300000 and _dj4.get("paid_cash") == 1000000,
      {k: _dj4.get(k) for k in ("total_purchases", "paid_cash", "total_credit", "total_paid", "debt")})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R180i. Review 1 tuzatishlari — server (№1 ortiqcha to'lov, №5 eski to'lov, №6, №7, №9)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from datetime import datetime as _dtm180i, timedelta as _td180i        # noqa: E402


def _xid(mid, sid):
    return db_ishi(lambda d: d.query(InventoryPurchase.id).filter_by(inventory_id=mid, supplier_id=sid)
                   .order_by(InventoryPurchase.id.desc()).first()[0])


def _det(r):
    d = js(r).get("detail") if isinstance(js(r), dict) else None
    return d if isinstance(d, dict) else {}


def _eski_tolov(sid, summa, izoh, vaqt):
    db_ishi(lambda d: d.add(SupplierPayment(supplier_id=sid, amount=summa, notes=izoh, paid_at=vaqt, paid_by="eski")))


def _kirim_tolovi(kid):
    return db_ishi(lambda d: [round(float(p.amount), 2) for p in d.query(SupplierPayment).filter(
        SupplierPayment.notes.like(f"Kirim to%lovi — #{kid}")).order_by(SupplierPayment.id).all()])


XS1, XM1 = taminotchi("T180 X Alfa"), material("T180 X Akril")
xarid(C, XM1, XS1, 10, 100000, paid_now=400000)
_x1 = _xid(XM1, XS1)
_rx1 = C.put(f"/api/inventory/purchases/{_x1}?tolov=avans", json={"quantity": 3, "price_per_unit": 100000})
_rx1a = C.put(f"/api/inventory/purchases/{_x1}", json={"notes": "faqat izoh"})
_rx1b = C.put(f"/api/inventory/purchases/{_x1}", json={"quantity": 3.5, "price_per_unit": 100000})
check("X1 (№1) 10 × 100 000 (400 000 to'langan) → 3 «avans qolsin»; keyin faqat izoh va summani OSHIRISH (3 → 3.5) — so'ralmaydi "
      "(200), to'lov 400 000 (ilgari ikkalasi 409)",
      _rx1.status_code == 200 and _rx1a.status_code == 200 and _rx1b.status_code == 200 and tolovlar(XS1) == [400000.0],
      (_rx1.status_code, _rx1a.status_code, js(_rx1a), _rx1b.status_code, tolovlar(XS1)))
_rx1c = C.put(f"/api/inventory/purchases/{_x1}", json={"quantity": 2.5, "price_per_unit": 100000})
_dx1c = _det(_rx1c)
check("X1b (№1) keyin 3.5 → 2.5: 409, summa — faqat SHU tahrir ortiqchasi 100 000 (ilgari 150 000), «avvalgi 50 000 so'm avans "
      "o'zgarmaydi»", _rx1c.status_code == 409 and float(_dx1c.get("summa") or 0) == 100000
      and "avvalgi 50 000 so'm avans o'zgarmaydi" in str(_dx1c.get("message")), (_rx1c.status_code, _dx1c))
_rx1d = C.put(f"/api/inventory/purchases/{_x1}?tolov=ochirish", json={"quantity": 2.5, "price_per_unit": 100000})
check("X1c (№1) `ochirish` — to'lovdan AYNAN 100 000 ayirildi: 300 000 (egasi qoldirgan 50 000 avans saqlandi; ilgari 250 000)",
      _rx1d.status_code == 200 and tolovlar(XS1) == [300000.0], (_rx1d.status_code, tolovlar(XS1)))

XS2, XM2a, XM2b = taminotchi("T180 X Beta"), material("T180 X Kley"), material("T180 X Qum")
_xk2 = js(kirim(C, XS2, [(XM2a, 100, 1000), (XM2b, 100, 1000)], paid_now=200000)).get("receipt_id")
_x2a, _x2b = _xid(XM2a, XS2), _xid(XM2b, XS2)
_rx2 = C.put(f"/api/inventory/purchases/{_x2a}?tolov=avans", json={"quantity": 50})
_rx2a = C.put(f"/api/inventory/purchases/{_x2b}", json={"notes": "faqat izoh"})
_rx2b = C.put(f"/api/inventory/purchases/{_x2b}", json={"quantity": 100, "price_per_unit": 1000})
check("X2 (№1) Kirim (100 000 + 100 000, to'langan 200 000): A → 50 000 «avans»; B ning izohi / o'zgarmagan miqdor-narxi (sahifa shuni "
      "yuboradi) — so'ralmaydi (ilgari 409 «ortiqcha 50 000»)",
      _rx2.status_code == 200 and _rx2a.status_code == 200 and _rx2b.status_code == 200 and _kirim_tolovi(_xk2) == [200000.0],
      (_rx2.status_code, _rx2a.status_code, js(_rx2a), _rx2b.status_code, _kirim_tolovi(_xk2)))
_rx2c = C.put(f"/api/inventory/purchases/{_x2b}", json={"quantity": 90})
check("X2b (№1) B 100 → 90 — 409, ortiqcha 10 000 (ilgari 60 000 — A ning avansi ham qo'shilardi)",
      _rx2c.status_code == 409 and float(_det(_rx2c).get("summa") or 0) == 10000, (_rx2c.status_code, _det(_rx2c)))
_rx2d = C.put(f"/api/inventory/purchases/{_x2b}?tolov=ochirish", json={"quantity": 90})
check("X2c (№1) `ochirish` — hujjat to'lovi 190 000 (A ning 50 000 avansi saqlandi; ilgari 140 000)",
      _rx2d.status_code == 200 and _kirim_tolovi(_xk2) == [190000.0], (_rx2d.status_code, _kirim_tolovi(_xk2)))

_som146 = getattr(crud, "_som", None)      # zip 179 da yo'q — sinov qulamaydi, X3 yiqiladi
_sm = ([_som146(x) for x in (0.5, 2.5, 1234567.5, 1234567.49, None)] if _som146 else ["_som yo'q"])
check("X3 (№1) `_som` — butun so'mga 0.5 YUQORIGA (pul UI `fmt` bilan bir): 0.5 → «1», 2.5 → «3» (ilgari Python `round`: «0», «2»)",
      _sm == ["1", "3", "1 234 568", "1 234 567", "0"], _sm)
XS3, XM3 = taminotchi("T180 X Gamma"), material("T180 X Sement")
xarid(C, XM3, XS3, 3, 1000, paid_now=2000)
_x3 = _xid(XM3, XS3)
db_ishi(lambda d: d.query(SupplierPayment).filter(SupplierPayment.supplier_id == XS3).update({"amount": 3000.5}))
_rx3 = C.put(f"/api/inventory/purchases/{_x3}", json={"notes": "eski yozuv"})
check("X3b (№1) eski yozuv (to'lov jamidan 0.5 so'm ko'p — yaxlitlash qoldig'i): izoh tahriri so'ralmaydi (ilgari 409 «ortiqcha 0 so'm»)",
      _rx3.status_code == 200, (_rx3.status_code, js(_rx3)))
XS3c, XM3c = taminotchi("T180 X Gamma2"), material("T180 X Ohak")
xarid(C, XM3c, XS3c, 10, 100.05, paid_now=900.5)
_rx3c = C.put(f"/api/inventory/purchases/{_xid(XM3c, XS3c)}", json={"quantity": 5, "price_per_unit": 100})
check("X3c (№1) ortiqcha 400.5 — xabarda «ortiqcha 401 so'm» (0.5 yuqoriga; ilgari «400»)",
      _rx3c.status_code == 409 and float(_det(_rx3c).get("summa") or 0) == 400.5 and "ortiqcha 401 so'm" in str(_det(_rx3c).get("message")),
      (_rx3c.status_code, _det(_rx3c)))

XS3d, XM3d = taminotchi("T180 X Gamma3"), material("T180 X Kum")
xarid(C, XM3d, XS3d, 1, 1000, paid_now=999.7)
_rx3d = C.put(f"/api/inventory/purchases/{_xid(XM3d, XS3d)}", json={"quantity": 1, "price_per_unit": 999.4})
check("X3d (№1) tahrir ortiqchasi 0.3 so'm — yarim so'mdan (`QARZ_BARDOSH`) kam: so'ralmaydi (200; ilgari 409 «ortiqcha 0 so'm»)",
      _rx3d.status_code == 200 and tolovlar(XS3d) == [999.7], (_rx3d.status_code, js(_rx3d), tolovlar(XS3d)))

XS4, XM4 = taminotchi("T180 X Delta"), material("T180 X Tosh")
xarid(C, XM4, XS4, 5, 100000)                              # «hoziroq to'lovi» YO'Q
_x4 = _xid(XM4, XS4)
_t4 = db_ishi(lambda d: d.get(InventoryPurchase, _x4).purchased_at)
_eski_tolov(XS4, 200000, "T180 X Tosh xaridi bilan bir vaqtda to'langan", _t4 - _td180i(seconds=90))
_rx4 = C.delete(f"/api/inventory/purchases/{_x4}")
check("X4 (№5) 90 s OLDIN (o'chirilgan boshqa xariddan) qolgan eski to'lov — «hoziroq to'lovi» yo'q xaridni o'chirishda SO'RALMAYDI (200), "
      "to'lov tegilmadi (ilgari 409; «To'lovni ham o'chirish» begona to'lovni o'chirardi)",
      _rx4.status_code == 200 and tolovlar(XS4) == [200000.0], (_rx4.status_code, js(_rx4), tolovlar(XS4)))
XS4b, XM4b = taminotchi("T180 X Delta2"), material("T180 X Tosh2")
xarid(C, XM4b, XS4b, 1, 1000)
_x4b = _xid(XM4b, XS4b)
_eski_tolov(XS4b, 5000, "T180 X Tosh2 xaridi bilan bir vaqtda to'langan",
            db_ishi(lambda d: d.get(InventoryPurchase, _x4b).purchased_at) + _td180i(seconds=1))
_rx4b = C.delete(f"/api/inventory/purchases/{_x4b}")
XS4d, XM4d = taminotchi("T180 X4d Chegara"), material("T180 X4d Sement")
_r4d0 = xarid(C, XM4d, XS4d, 5, 1999999999.99)
_x4d = _xid(XM4d, XS4d)
_r4d = C.put(f"/api/inventory/purchases/{_x4d}", json={"price_per_unit": 1234})
check("X4d (tahrir180_m) xarid jami chegarada (9 999 999 999.95), to'lovsiz: narx 1 234 ga — 200, jami 6 170 (PG da ilgari 500 «numeric "
      "field overflow» — eski to'lov sharti SQL da)",
      _r4d0.status_code == 200 and _r4d.status_code == 200
      and abs(db_ishi(lambda d: float(d.get(InventoryPurchase, _x4d).total_amount)) - 6170) < 0.01,
      (_r4d0.status_code, _r4d.status_code, js(_r4d)))
check("X4b (№5) eski to'lov xarid jamisidan (1 000) KO'P (5 000) — bu xaridniki emas: so'ralmaydi (200; ilgari 409)",
      _rx4b.status_code == 200 and tolovlar(XS4b) == [5000.0], (_rx4b.status_code, js(_rx4b), tolovlar(XS4b)))
XS4c, XM4c = taminotchi("T180 X Delta3"), material("T180 X Tosh3")
xarid(C, XM4c, XS4c, 1, 1000)
_x4c = _xid(XM4c, XS4c)
_eski_tolov(XS4c, 500, "T180 X Tosh3 xaridi bilan bir vaqtda to'langan",
            db_ishi(lambda d: d.get(InventoryPurchase, _x4c).purchased_at) + _td180i(seconds=2))
_rx4c = C.delete(f"/api/inventory/purchases/{_x4c}")
check("X4c NAZORAT: eski to'lov xariddan 2 s KEYIN, summasi jamidan oshmaydi — topiladi, so'raladi (409)",
      _rx4c.status_code == 409 and _det(_rx4c).get("type") == "purchase_has_payment", (_rx4c.status_code, js(_rx4c)))

XS5, XM5 = taminotchi("T180 X Epsilon"), material("T180 X Yog'och")
C.post(f"/api/inventory/{XM5}/purchase", json={"quantity": 1, "price_per_unit": 50000, "paid_now": 0, "supplier_id": XS5, "notes": "T180",
                                               "payment_due_date": (_dtm180i.utcnow() - _td180i(days=3)).strftime("%Y-%m-%d")})
_dd = lambda: [x.get("supplier_id") for x in (js(C.get("/api/suppliers/due-dates")) or []) if isinstance(x, dict)]     # noqa: E731
_dd0 = _dd()
_rx5 = C.delete(f"/api/suppliers/{XS5}?force=true")
_dd1 = _dd()
check("X5 (№7) muddati o'tgan qarzli ta'minotchi yashirildi — `/api/suppliers/due-dates` da YO'Q (yashirishdan oldin bor edi; ro'yxat va "
      "`debt-total` bilan bir)", XS5 in _dd0 and js(_rx5).get("yashirildi") is True and XS5 not in _dd1, (_dd0, js(_rx5), _dd1))

XS6, XM6 = taminotchi("T180 X Zeta"), material("T180 X Bo'r")
xarid(C, XM6, XS6, 10, 100000, paid_now=400000)
_x6 = _xid(XM6, XS6)
_rx6 = C.put(f"/api/inventory/purchases/{_x6}", json={"is_credit": False})
_h6 = js(C.get(f"/api/suppliers/{XS6}/history"))
check("X6 (№9) «hoziroq to'langan» to'lovi bor nasiya xaridni API orqali naqdga o'tkazish — 400 va sabab, hech narsa o'zgarmadi "
      "(ilgari 200: Kassa 400 000 to'lovni ham, 1 000 000 naqd xaridni ham sanardi)",
      _rx6.status_code == 400 and "naqdga o'tkazib bo'lmaydi" in str(js(_rx6).get("detail"))
      and db_ishi(lambda d: d.get(InventoryPurchase, _x6).is_credit) is True and _h6.get("paid_cash") == 0,
      (_rx6.status_code, js(_rx6), {k: _h6.get(k) for k in ("total_paid", "paid_cash", "debt")}))
xarid(C, XM6, XS6, 2, 1000)
_rx6b = C.put(f"/api/inventory/purchases/{_xid(XM6, XS6)}", json={"is_credit": False})
check("X6b NAZORAT: to'lovsiz nasiya xaridni naqdga o'tkazish — avvalgidek 200", _rx6b.status_code == 200, (_rx6b.status_code, js(_rx6b)))

_rx7 = C.post("/api/suppliers", json={"name": "T180 X Nomli"}, headers={"X-Amal-Kaliti": "t180xnomkalit00001"})
_rx7b = C.post("/api/suppliers", json={"name": "T180 X Boshqa nom"}, headers={"X-Amal-Kaliti": "t180xnomkalit00001"})
check("X7 (№6) yangi ta'minotchi javobida `name`; o'sha kalit bilan takror — BIRINCHI so'rov nomi va id (sahifa shu nomni ko'rsatadi)",
      js(_rx7).get("name") == "T180 X Nomli" and js(_rx7b).get("takror") is True and js(_rx7b).get("name") == "T180 X Nomli"
      and js(_rx7b).get("id") == js(_rx7).get("id"), (js(_rx7), js(_rx7b)))

if PG_URL:
    section("P. PostgreSQL — xaridni parallel tahrirlash / o'chirish (B2, B3)")

    def _sekin(asl):
        holat = {"n": 0}
        qulf = threading.Lock()

        def f(*a, **k):
            with qulf:
                holat["n"] += 1
                birinchi = holat["n"] == 1
            if birinchi:
                time.sleep(1.2)
            return asl(*a, **k)
        return f

    def _parallel(so_rovlar):
        natija = [None] * len(so_rovlar)

        def ish(i, fn):
            try:
                natija[i] = fn()
            except Exception as e:         # noqa: BLE001
                natija[i] = e
        iplar = []
        for i, fn in enumerate(so_rovlar):
            t = threading.Thread(target=ish, args=(i, fn))
            t.start()
            iplar.append(t)
            time.sleep(0.35)
        for t in iplar:
            t.join(30)
        return natija

    C1, C2 = mijoz("t180_admin"), mijoz("t180_admin")
    _rp = xarid(C, M3, SA, 10, 500)
    _pid = db_ishi(lambda d: d.query(InventoryPurchase.id).filter_by(inventory_id=M3, supplier_id=SA).order_by(
        InventoryPurchase.id.desc()).first()[0])
    _q0 = qoldiq(M3)
    _asl = crud.get_item_locked
    crud.get_item_locked = _sekin(_asl)
    try:
        _n = _parallel([lambda: C1.put(f"/api/inventory/purchases/{_pid}", json={"quantity": 12}),
                        lambda: C2.put(f"/api/inventory/purchases/{_pid}", json={"quantity": 15})])
    finally:
        crud.get_item_locked = _asl
    _qx = db_ishi(lambda d: float(d.get(InventoryPurchase, _pid).quantity))
    check("P1 (B2) parallel tahrir 10→12 va 10→15: ombor o'zgarishi = yakuniy xarid miqdori − 10 (ilgari +2 va +5 = +7)",
          all(getattr(x, "status_code", 0) == 200 for x in _n) and abs((qoldiq(M3) - _q0) - (_qx - 10)) < 1e-6,
          ([getattr(x, "status_code", x) for x in _n], _qx, qoldiq(M3) - _q0))

    _rp2 = xarid(C, M3, SA, 10, 500)
    _pid2 = db_ishi(lambda d: d.query(InventoryPurchase.id).filter_by(inventory_id=M3, supplier_id=SA).order_by(
        InventoryPurchase.id.desc()).first()[0])
    _q0 = qoldiq(M3)
    _asl = crud.inventory_qulf
    crud.inventory_qulf = _sekin(_asl)
    try:
        _n = _parallel([lambda: C1.delete(f"/api/inventory/purchases/{_pid2}"),
                        lambda: C2.delete(f"/api/inventory/purchases/{_pid2}")])
    finally:
        crud.inventory_qulf = _asl
    _kodlar = sorted(getattr(x, "status_code", 0) for x in _n)
    check("P2 (B3) parallel ikki o'chirish: biri 200, ikkinchisi 404; ombordan AYNAN 10 ayirildi (ilgari 20)",
          _kodlar == [200, 404] and abs((_q0 - qoldiq(M3)) - 10) < 1e-6, (_kodlar, _q0 - qoldiq(M3)))

    # ── kech146 (zip 180, review 1 — №3, №4): qulf tartibi hujjat → xarid → material → to'lovlar
    from sqlalchemy import text as _tx146
    if not hasattr(crud, "_tolovni_kamaytir"):     # asl kod (zip 179) — funksiya yo'q: sinov QULAMASIN (P3 / P7 / P8 yiqiladi)
        crud._tolovni_kamaytir = lambda *a, **k: None

    def _kodi(x):
        return getattr(x, "status_code", f"{type(x).__name__}")

    def _hujjat_qatori(kid, mid):
        return db_ishi(lambda d: d.query(InventoryPurchase.id).filter_by(receipt_id=kid, inventory_id=mid).first()[0])

    def _deadlock_soni():
        def f(d):
            d.execute(_tx146("SELECT pg_stat_clear_snapshot()"))
            return int(d.execute(_tx146("SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()")).scalar() or 0)
        return db_ishi(f)

    def _xato_jurnali():
        return db_ishi(lambda d: d.query(ErrorLog).count())

    _dl0, _ej0 = _deadlock_soni(), _xato_jurnali()
    XP3, XP3a, XP3b = taminotchi("T180 P3"), material("T180 P3 Kley"), material("T180 P3 Qum")
    _kp3 = js(kirim(C, XP3, [(XP3a, 100, 1000), (XP3b, 100, 1000)], paid_now=200000)).get("receipt_id")
    _p3a, _p3b = _hujjat_qatori(_kp3, XP3a), _hujjat_qatori(_kp3, XP3b)
    # oyna kengaytiriladi: (1) to'lov kamaytirishda — asl kodda yo'qolgan yangilanish; (2) o'z qatori qulflangach, hujjatning boshqa
    # qatorlarini qulflashdan OLDIN (`_kirim_xaridlari`, asl kodda yo'q) — hujjat qulfisiz ikki tahrir bir-birining qatorini kutib deadlock
    _asl, _asl_x = crud._tolovni_kamaytir, getattr(crud, "_kirim_xaridlari", None)
    crud._tolovni_kamaytir = _sekin(_asl)
    if _asl_x is not None:
        crud._kirim_xaridlari = _sekin(_asl_x)
    try:
        _n = _parallel([lambda: C1.put(f"/api/inventory/purchases/{_p3a}?tolov=ochirish", json={"quantity": 50}),
                        lambda: C2.put(f"/api/inventory/purchases/{_p3b}?tolov=ochirish", json={"quantity": 50})])
    finally:
        crud._tolovni_kamaytir = _asl
        if _asl_x is not None:
            crud._kirim_xaridlari = _asl_x
    check("P3 (№3) bir Kirimning ikki qatori PARALLEL 100 000 → 50 000 `?tolov=ochirish`: ikkalasi 200, hujjat to'lovi 100 000 (ilgari "
          "150 000 — bitta kamaytirish yo'qolib, 50 000 yashirin avans)",
          [_kodi(x) for x in _n] == [200, 200] and _kirim_tolovi(_kp3) == [100000.0], ([_kodi(x) for x in _n], _kirim_tolovi(_kp3)))

    XP4, XP4a, XP4b = taminotchi("T180 P4"), material("T180 P4 Akril"), material("T180 P4 Boyoq")
    _kp4 = js(kirim(C, XP4, [(XP4a, 10, 1000), (XP4b, 1, 1000)])).get("receipt_id")
    _p4 = _hujjat_qatori(_kp4, XP4a)
    _asl = crud.log_movement
    crud.log_movement = _sekin(_asl)
    try:
        _n = _parallel([lambda: C1.put(f"/api/inventory/purchases/{_p4}", json={"quantity": 15}),
                        lambda: C2.post(f"/api/inventory/receipts/{_kp4}/cancel")])
    finally:
        crud.log_movement = _asl
    check("P4 (№4) Kirim qatori 10 → 15 (sekin) bilan PARALLEL hujjatni bekor qilish: ikkalasi 200, xarid ham hujjat ham yo'q, ombor 0 "
          "(ilgari 5 — bekor qilish eski 10 ni ayirardi)",
          [_kodi(x) for x in _n] == [200, 200] and qoldiq(XP4a) == 0 and qoldiq(XP4b) == 0 and soni(InventoryPurchase, receipt_id=_kp4) == 0,
          ([_kodi(x) for x in _n], qoldiq(XP4a), qoldiq(XP4b)))

    XP5, XP5a, XP5b = taminotchi("T180 P5"), material("T180 P5 Akril"), material("T180 P5 Boyoq")
    _kp5 = js(kirim(C, XP5, [(XP5a, 10, 1000), (XP5b, 1, 1000)])).get("receipt_id")
    _p5 = _hujjat_qatori(_kp5, XP5a)
    _asl = crud.log_movement
    crud.log_movement = _sekin(_asl)
    try:
        _n = _parallel([lambda: C2.post(f"/api/inventory/receipts/{_kp5}/cancel"),
                        lambda: C1.put(f"/api/inventory/purchases/{_p5}", json={"quantity": 15})])
    finally:
        crud.log_movement = _asl
    check("P5 (№4) hujjatni bekor qilish (sekin) bilan PARALLEL qator tahriri: bekor 200, tahrir 404 (xarid yo'q), ombor 0 "
          "(ilgari tahrir 200 va ombor 5)", [_kodi(x) for x in _n] == [200, 404] and qoldiq(XP5a) == 0,
          ([_kodi(x) for x in _n], qoldiq(XP5a)))

    XP6, XP6a, XP6b = taminotchi("T180 P6"), material("T180 P6 Gips"), material("T180 P6 Tosh")
    _kp6 = js(kirim(C, XP6, [(XP6a, 10, 1000), (XP6b, 5, 1000)])).get("receipt_id")
    _p6a, _p6b = _hujjat_qatori(_kp6, XP6a), _hujjat_qatori(_kp6, XP6b)
    _asl = crud.log_movement
    crud.log_movement = _sekin(_asl)
    try:
        _n = _parallel([lambda: C1.put(f"/api/inventory/purchases/{_p6a}", json={"quantity": 12}),
                        lambda: C2.delete(f"/api/inventory/purchases/{_p6b}")])
    finally:
        crud.log_movement = _asl
    _kp6b = js(kirim(C, XP6, [(XP6a, 10, 1000), (XP6b, 5, 1000)])).get("receipt_id")
    _p6c = _hujjat_qatori(_kp6b, XP6a)
    _q6 = qoldiq(XP6a)
    _asl = crud.log_movement
    crud.log_movement = _sekin(_asl)
    try:
        _n2 = _parallel([lambda: C1.put(f"/api/inventory/purchases/{_p6c}", json={"quantity": 12}),
                         lambda: C2.delete(f"/api/inventory/purchases/{_p6c}")])
    finally:
        crud.log_movement = _asl
    check("P6 NAZORAT (№3): qator A tahriri ‖ qator B ni o'chirish va qator tahriri ‖ o'sha qatorni o'chirish — hammasi 200, ombor xaridlar "
          "bilan bir (deadlock / 500 yo'q)",
          [_kodi(x) for x in _n] == [200, 200] and [_kodi(x) for x in _n2] == [200, 200] and qoldiq(XP6b) == 5
          and abs(qoldiq(XP6a) - (_q6 - 10)) < 1e-6 and soni(InventoryPurchase, receipt_id=_kp6) == 1,
          ([_kodi(x) for x in _n], [_kodi(x) for x in _n2], qoldiq(XP6a), _q6, qoldiq(XP6b)))

    XP7, XP7m = taminotchi("T180 P7"), material("T180 P7 Akril")
    xarid(C, XP7m, XP7, 10, 1000, paid_now=4000)
    _p7 = db_ishi(lambda d: d.query(InventoryPurchase.id).filter_by(inventory_id=XP7m, supplier_id=XP7).first()[0])
    _t7 = db_ishi(lambda d: d.query(SupplierPayment.id).filter_by(supplier_id=XP7).first()[0])
    _asl = crud._tolovni_kamaytir
    crud._tolovni_kamaytir = _sekin(_asl)
    try:
        _n = _parallel([lambda: C1.put(f"/api/inventory/purchases/{_p7}?tolov=ochirish", json={"quantity": 3}),
                        lambda: C2.delete(f"/api/suppliers/payments/{_t7}")])
    finally:
        crud._tolovni_kamaytir = _asl
    check("P7 (№3) yakka xarid `?tolov=ochirish` tahriri (sekin) bilan PARALLEL shu to'lovni qo'lda o'chirish — 500 yo'q, ikkalasi 200 "
          "(ilgari to'lov qulfsiz o'qilib 500 «UPDATE … 0 were matched»)",
          [_kodi(x) for x in _n] == [200, 200] and tolovlar(XP7) == [], ([_kodi(x) for x in _n], tolovlar(XP7)))

    XP9, XP9m = taminotchi("T180 P9"), material("T180 P9 Akril")
    _kp9 = js(kirim(C, XP9, [(XP9m, 10, 1000)])).get("receipt_id")
    _p9 = _hujjat_qatori(_kp9, XP9m)
    _asl = crud.log_movement
    crud.log_movement = _sekin(_asl)
    try:
        _n = _parallel([lambda: C1.put(f"/api/inventory/purchases/{_p9}", json={"quantity": 15}),
                        lambda: C2.delete(f"/api/inventory/purchases/{_p9}")])
    finally:
        crud.log_movement = _asl
    check("P9 (№4) bir qatorli Kirim: qator 10 → 15 (sekin) bilan PARALLEL shu qatorni o'chirish (butun hujjat bekor qilinadi): ikkalasi 200, "
          "xarid ham hujjat ham yo'q, ombor 0 (ilgari 5 — bekor qilish oldin o'qilgan eski 10 ni ayirardi)",
          [_kodi(x) for x in _n] == [200, 200] and qoldiq(XP9m) == 0 and soni(InventoryReceipt, id=_kp9) == 0
          and soni(InventoryPurchase, receipt_id=_kp9) == 0, ([_kodi(x) for x in _n], qoldiq(XP9m), soni(InventoryReceipt, id=_kp9)))

    XP10 = taminotchi("T180 P10")
    XP10m = [material("T180 P10 Akril"), material("T180 P10 Boyoq")]
    _kp10a = js(kirim(C, XP10, [(XP10m[0], 5, 1000), (XP10m[1], 5, 1000)])).get("receipt_id")
    _kp10b = js(kirim(C, XP10, [(XP10m[1], 5, 1000), (XP10m[0], 5, 1000)])).get("receipt_id")
    _asl = crud.log_movement

    def _sekin10(*a, **k):
        time.sleep(0.8)
        return _asl(*a, **k)
    crud.log_movement = _sekin10
    try:
        _n = _parallel([lambda: C1.post(f"/api/inventory/receipts/{_kp10a}/cancel"),
                        lambda: C2.post(f"/api/inventory/receipts/{_kp10b}/cancel")])
    finally:
        crud.log_movement = _asl
    check("P10 (№3) bir xil ikki materialli ikki Kirim (qatorlari TESKARI tartibda) PARALLEL bekor qilindi — ikkalasi 200, ombor 0 "
          "(ilgari materiallar qator tartibida qulflanib deadlock 40P01 — biri 500)",
          [_kodi(x) for x in _n] == [200, 200] and [qoldiq(m) for m in XP10m] == [0, 0], ([_kodi(x) for x in _n], [qoldiq(m) for m in XP10m]))

    # ── kech146 (zip 180, tahrir180_j — ESKI xatolar): P11 — «yagona qator → butun hujjat bekor» qarori hujjat qulfi ostida
    XP11 = taminotchi("T180 P11")
    XP11m = [material("T180 P11 Akril"), material("T180 P11 Boyoq")]
    _kp11 = js(kirim(C, XP11, [(XP11m[0], 5, 1000), (XP11m[1], 5, 1000)])).get("receipt_id")
    _p11 = [_hujjat_qatori(_kp11, m) for m in XP11m]
    _asl = crud.inventory_qulf
    crud.inventory_qulf = _sekin(_asl)
    try:
        _n = _parallel([lambda: C1.delete(f"/api/inventory/purchases/{_p11[0]}"),
                        lambda: C2.delete(f"/api/inventory/purchases/{_p11[1]}")])
    finally:
        crud.inventory_qulf = _asl
    check("P11 ikki qatorli to'lovsiz Kirimning ikkala qatori PARALLEL o'chirildi — ikkalasi 200, qatorsiz BO'SH hujjat qolmaydi, ombor 0 "
          "(ilgari ikkalasi ham «yagona qator emas» deb qatorni o'chirib, bo'sh hujjat qoldirardi)",
          [_kodi(x) for x in _n] == [200, 200] and soni(InventoryReceipt, id=_kp11) == 0
          and soni(InventoryPurchase, receipt_id=_kp11) == 0 and [qoldiq(m) for m in XP11m] == [0, 0],
          ([_kodi(x) for x in _n], soni(InventoryReceipt, id=_kp11), soni(InventoryPurchase, receipt_id=_kp11), [qoldiq(m) for m in XP11m]))

    # P12 — ikki Kirim parallel YARATILADI (bir xil ikki material, qatorlari teskari tartibda): materiallar id tartibida qulflanadi
    XP12 = taminotchi("T180 P12")
    XP12m = [material("T180 P12 Akril"), material("T180 P12 Boyoq")]
    _asl = crud.log_movement

    def _sekin12(*a, **k):
        time.sleep(0.8)
        return _asl(*a, **k)
    crud.log_movement = _sekin12
    try:
        _n = _parallel([lambda: kirim(C1, XP12, [(XP12m[0], 5, 1000), (XP12m[1], 5, 1000)]),
                        lambda: kirim(C2, XP12, [(XP12m[1], 7, 1000), (XP12m[0], 7, 1000)])])
    finally:
        crud.log_movement = _asl
    check("P12 bir xil ikki materialli ikki Kirim (qatorlari TESKARI tartibda) PARALLEL yaratildi — ikkalasi 200, ombor 12 / 12 "
          "(ilgari materiallar qator tartibida qulflanib deadlock 40P01 — biri 500 «Kirim saqlanmadi»)",
          [_kodi(x) for x in _n] == [200, 200] and [qoldiq(m) for m in XP12m] == [12, 12],
          ([_kodi(x) for x in _n], [qoldiq(m) for m in XP12m]))

    # P8: aralash yuklama — bitta to'langan Kirim ustida 6 parallel so'rov (tahrir ↑↓ `ochirish`, ba'zan bekor qilish), 4 davra
    import random as _rnd146
    CX = [mijoz("t180_admin") for _ in range(6)]
    _asl_k, _asl_l = crud._tolovni_kamaytir, crud.log_movement

    def _sekin_doim(asl):
        def f(*a, **k):
            time.sleep(0.25)
            return asl(*a, **k)
        return f
    _p8_xato = []
    crud._tolovni_kamaytir, crud.log_movement = _sekin_doim(_asl_k), _sekin_doim(_asl_l)
    try:
        for _d in range(4):
            _s8 = taminotchi(f"T180 P8 {_d}")
            _m8 = [material(f"T180 P8 {_d} M{i}") for i in range(3)]
            _k8 = js(kirim(C, _s8, [(m, 100, 1000) for m in _m8], paid_now=300000)).get("receipt_id")
            _q8 = {m: _hujjat_qatori(_k8, m) for m in _m8}
            _rnd146.seed(_d)
            _ish = []
            for i in range(6):
                _m = _rnd146.choice(_m8)
                if i == 4 and _d % 2 == 1:
                    _ish.append(lambda i=i: CX[i].post(f"/api/inventory/receipts/{_k8}/cancel?tolov=ochirish"))
                else:
                    _ish.append(lambda i=i, _m=_m, _q=_rnd146.choice([40, 60, 80, 120]):
                                CX[i].put(f"/api/inventory/purchases/{_q8[_m]}?tolov=ochirish", json={"quantity": _q}))
            natija = [None] * len(_ish)

            def _bir(i, fn):
                try:
                    natija[i] = fn()
                except Exception as e:     # noqa: BLE001
                    natija[i] = e
            _ip = [threading.Thread(target=_bir, args=(i, fn)) for i, fn in enumerate(_ish)]
            for t in _ip:
                t.start()
                time.sleep(0.05)
            for t in _ip:
                t.join(60)
            _qq = db_ishi(lambda d: {p.inventory_id: (float(p.quantity), float(p.total_amount))
                                      for p in d.query(InventoryPurchase).filter_by(receipt_id=_k8)})
            _tl8 = sum(_kirim_tolovi(_k8))
            _jm8 = sum(v[1] for v in _qq.values())
            _kod8 = [_kodi(x) for x in natija]
            if not (all(k in (200, 404) for k in _kod8) and all(abs(qoldiq(m) - (_qq[m][0] if m in _qq else 0)) < 1e-6 for m in _m8)
                    and _tl8 <= _jm8 + 0.005):
                _p8_xato.append((_d, _kod8, {m: qoldiq(m) for m in _m8}, _qq, _tl8, _jm8))
    finally:
        crud._tolovni_kamaytir, crud.log_movement = _asl_k, _asl_l
    time.sleep(1.5)
    _dl1 = _deadlock_soni()
    _ej1 = db_ishi(lambda d: [str(e.error_message)[:100] for e in d.query(ErrorLog).order_by(ErrorLog.id).all()][_ej0:])
    check("P8 (№3, №4) aralash yuklama (4 davra × 6 parallel so'rov: tahrir ↑↓ `ochirish`, bekor qilish): 500 yo'q, deadlock (40P01) yo'q, "
          "ombor = xaridlar, hujjat to'lovi ≤ hujjat jami (ilgari: deadlock, 500, yashirin avans)",
          not _p8_xato and _dl1 == _dl0 and not [e for e in _ej1 if "40P01" in e or "deadlock" in e.lower()],
          (_p8_xato[:2], _dl1 - _dl0, _ej1[:4]))

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


def kontekst(user="t180_admin", oldin=None):
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


# Xabarlar va tasdiq oynalari: `window.__msg`; tasdiq javobi — `window.__ha` (standart: true)
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
    except Exception as e:                 # noqa: BLE001 — eski kodda funksiya / o'zgaruvchi yo'q
        x = "XATO: " + str(e)[:160]
    pg.wait_for_timeout(kutish)
    return x


def kut(pg, ifoda, ms=6000):
    try:
        pg.wait_for_function(ifoda, timeout=ms)
        return True
    except Exception:                      # noqa: BLE001
        return False


def sorovlar(nima, usul="POST"):
    return [x for x in SOROV if nima in x[1] and x[0] == usul]


def korinadi(pg, sel):
    """Ko'rinadigan elementlar soni — JS «ko'rsatadigan» holatda (inline `display: none` olib tashlanadi; CSS `!important` baribir yashiradi)."""
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


def tarix_yuklandi(pg, sid):
    return kut(pg, f"() => typeof openHistory !== 'undefined' && openHistory.yuklandi === {sid}", 8000)


if br:
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("U. «Ta'minotchilar» sahifasi (C1, A2, A3, A4, D1)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    SD, SE = taminotchi("T180 Delta"), taminotchi("T180 Epsilon")
    xarid(C, M1, SD, 3, 2000)                     # Delta qarzi 6 000
    xarid(C, M2, SE, 1, 1500)                     # Epsilon qarzi 1 500
    ctx, pg = kontekst(oldin=[(re.compile(r".*/api/suppliers$"), lambda r: r.fulfill(**SAHIFA_502))])
    try:
        ochiq(pg, "/suppliers")
        _sl, _kt = matn(pg, "#supList") or "", matn(pg, "#k-total-debt")
        check("U1 (C1) ro'yxat 502 — KPI «—», ro'yxat o'rnida sabab (ilgari abadiy «Yuklanmoqda...»)",
              _kt == "—" and "Ta'minotchilar ro'yxati yuklanmadi" in _sl and SERVER in _sl, (_kt, _sl))
        ctx.unroute(re.compile(r".*/api/suppliers$"))
        ochiq(pg, "/suppliers")
        check("U1b NAZORAT: ro'yxat yuklanadi", "T180 Delta" in (matn(pg, "#supList") or ""), matn(pg, "#supList"))

        baj(pg, "(id) => { openHistory(id); }", SD)
        _ok_a = tarix_yuklandi(pg, SD)
        pg.route(re.compile(rf".*/api/suppliers/{SE}/history.*"), lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, "(id) => { openHistory(id); }", SE, kutish=1200)
        _nm, _qz = matn(pg, "#hist-name"), matn(pg, "#hist-debt")
        _btn = baj(pg, "() => document.getElementById('supplier-pay-save-btn').disabled", kutish=50)
        _hp = matn(pg, "#hist-purchases") or ""
        check("U2 (C1) boshqa ta'minotchi tarixi 502 — nom / qarz «—» (oldingisi QOLMAYDI), sabab, «💰 To'lov qilish» berk",
              _ok_a and _nm == "—" and _qz == "—" and _btn is True and "yuklanmadi" in _hp and SERVER in _hp, (_ok_a, _nm, _qz, _btn, _hp))
        msg_tozala(pg)
        _n0 = len(sorovlar("/payment"))
        baj(pg, "async () => { document.getElementById('pay-amount').value = '1000'; await savePayment(); }")
        check("U2b (C1) tarix yuklanmagan — to'lov YUBORILMAYDI, sabab (ilgari ekranda Delta, to'lov Epsilonga ketardi)",
              len(sorovlar("/payment")) == _n0 and "yuklanmagan" in msg_matn(pg), (sorovlar("/payment")[_n0:], msg_matn(pg)))
        pg.unroute(re.compile(rf".*/api/suppliers/{SE}/history.*"))

        _u = Ushla()
        pg.route(re.compile(rf".*/api/suppliers/{SD}/history.*"), _u)
        baj(pg, "(id) => { openHistory(id); }", SD, kutish=400)
        baj(pg, "(id) => { openHistory(id); }", SE, kutish=1200)
        _u.qoyib_yubor()
        pg.wait_for_timeout(1200)
        _nm = matn(pg, "#hist-name")
        _yk = baj(pg, "() => (typeof openHistory !== 'undefined') ? openHistory.yuklandi : null", kutish=50)
        check("U3 (C1) Delta → Epsilon tez almashtirildi, Delta javobi KECH keldi — ekranda Epsilon qoladi",
              _nm == "T180 Epsilon" and _yk == SE, (_nm, _yk, len(_u.ushlangan)))
        pg.unroute(re.compile(rf".*/api/suppliers/{SD}/history.*"))
    except Exception as _x:               # noqa: BLE001
        check("U1–U3 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    ctx, pg = kontekst()
    try:
        ochiq(pg, "/suppliers")
        _n0 = soni(Supplier, name="T180 Dubl")
        _p0 = len(sorovlar("/api/suppliers"))
        baj(pg, "() => { openSupplierModal(); document.getElementById('s-name').value = 'T180 Dubl'; }", kutish=200)
        pg.dblclick("#sup-save-btn")
        pg.wait_for_timeout(1500)
        _yangi = [x for x in sorovlar("/api/suppliers")[_p0:] if x[1].endswith("/api/suppliers")]
        check("U4 (A4) «Saqlash» ikki marta bosildi — BITTA so'rov (kalit bilan), bitta ta'minotchi",
              len(_yangi) == 1 and bool(_yangi[0][2]) and soni(Supplier, name="T180 Dubl") == _n0 + 1, (_yangi, soni(Supplier, name="T180 Dubl")))

        _b = Bajar502(faqat="POST")
        pg.route(re.compile(r".*/api/suppliers$"), _b)
        baj(pg, "() => { openSupplierModal(); document.getElementById('s-name').value = 'T180 Uzilgan'; }", kutish=200)
        baj(pg, "async () => { await saveSupplier(); }", kutish=900)
        _e1 = matn(pg, "#sup-error") or ""
        pg.unroute(re.compile(r".*/api/suppliers$"))
        baj(pg, "async () => { await saveSupplier(); }", kutish=1200)
        check("U5 (A4 / D1) yangi ta'minotchi 502 — «natijasi noma'lum» (ilgari «❌ Xato yuz berdi»); qayta — o'sha kalit, BITTA ta'minotchi",
              NOMALUM in _e1 and _b.holat == [200] and soni(Supplier, name="T180 Uzilgan") == 1, (_e1, _b.holat, soni(Supplier, name="T180 Uzilgan")))

        baj(pg, "(id) => { openHistory(id); }", SD)
        tarix_yuklandi(pg, SD)
        _t0 = len(tolovlar(SD))
        _b = Bajar502()
        pg.route(re.compile(rf".*/api/suppliers/{SD}/payment$"), _b)
        msg_tozala(pg)
        baj(pg, "async () => { document.getElementById('pay-amount').value = '1 000'; await savePayment(); }", kutish=900)
        _m1 = msg_matn(pg)
        pg.unroute(re.compile(rf".*/api/suppliers/{SD}/payment$"))
        tarix_yuklandi(pg, SD)
        msg_tozala(pg)
        baj(pg, "async () => { document.getElementById('pay-amount').value = '1 000'; await savePayment(); }", kutish=1200)
        _m2 = msg_matn(pg)
        check("U6 (A3) to'lov 502 — «To'lov natijasi noma'lum»; qayta — «ikkinchi marta yozilmadi», to'lov BITTA",
              NOMALUM in _m1 and TAKROR in _m2 and len(tolovlar(SD)) == _t0 + 1 and _b.holat == [200], (_m1, _m2, tolovlar(SD), _b.holat))

        tarix_yuklandi(pg, SD)
        _x0 = (soni(InventoryPurchase, supplier_id=SD, inventory_id=M1), soni(InventoryPurchase, supplier_id=SD, inventory_id=M2))
        _b = Bajar502()
        pg.route(re.compile(rf".*/api/inventory/{M2}/purchase$"), _b)
        msg_tozala(pg)
        baj(pg, """(a) => { apBasket = [{itemId: a.m1, itemName: 'T180 Akril', unit: 'kg', qty: 2, price: 1000, total: 2000},
                                        {itemId: a.m2, itemName: 'T180 Boyoq', unit: 'kg', qty: 3, price: 500, total: 1500}];
                            renderApBasket(); document.getElementById('ap-qty').value = ''; document.getElementById('ap-price').value = '';
                            document.getElementById('ap-paid-now').value = ''; return saveAddPurchase(); }""",
            {"m1": M1, "m2": M2}, kutish=1500)
        _m1 = msg_matn(pg)
        _sav = baj(pg, "() => apBasket.map(l => l.itemId)", kutish=50)
        pg.unroute(re.compile(rf".*/api/inventory/{M2}/purchase$"))
        tarix_yuklandi(pg, SD)
        msg_tozala(pg)
        baj(pg, "() => saveAddPurchase()", kutish=1500)
        _m2 = msg_matn(pg)
        _x1 = (soni(InventoryPurchase, supplier_id=SD, inventory_id=M1), soni(InventoryPurchase, supplier_id=SD, inventory_id=M2))
        check("U7 (A2) savatdagi 2-qator 502 — 1-si saqlandi, 2-si savatda QOLDI («natija noma'lum» bilan; ilgari savat tozalanardi)",
              "1 ta material saqlandi" in _m1 and "natija noma'lum" in _m1 and _sav == [M2], (_m1, _sav))
        check("U7b (A2) qayta saqlash — o'sha kalit: Bo'yoq xaridi BITTA (ikki emas), Akril ham bitta",
              _x1 == (_x0[0] + 1, _x0[1] + 1) and _b.holat == [200] and "xaridi yozildi" in _m2, (_x0, _x1, _b.holat, _m2))

        pg.route(re.compile(r".*/api/inventory$"), lambda r: r.fulfill(**jsn(403, {"detail": "Ruxsat yo'q"})))
        tarix_yuklandi(pg, SD)
        baj(pg, "() => { invItems = []; openAddPurchase(); }", kutish=900)
        _op = matn(pg, "#ap-item option") or ""
        check("U8 (D1) materiallar 403 — «Materiallar ro'yxati yuklanmadi — ko'rish ruxsati yo'q» (ilgari «❌ Xato (status: 403)»)",
              "Materiallar ro'yxati yuklanmadi" in _op and "ruxsati yo'q" in _op and "status" not in _op, _op)
        pg.unroute(re.compile(r".*/api/inventory$"))
    except Exception as _x:               # noqa: BLE001
        check("U4–U8 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("R. Ruxsatsiz tugmalar (C3)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    SEL = {
        "«+ Ta'minotchi»": '[onclick^="openSupplierModal("]',
        "✏️ ta'minotchi": '[onclick*="editSupplier("]',
        "✕ ta'minotchi": '[onclick*="deleteSupplier("]',
        "«💰 To'lov qilish»": "#supplier-pay-save-btn",
        "«+ Xarid qo'shish»": '[onclick^="openAddPurchase("]',
        "xarid ✏️": '[onclick^="editPurchase("]',
        "xarid ✕": '[onclick^="deletePurchase("]',
        "to'lov ✕": '[onclick^="deletePayment("]',
    }

    def sup_korinish(user):
        ctx, pg = kontekst(user)
        try:
            ochiq(pg, "/suppliers")
            baj(pg, "(id) => { openHistory(id); }", SD)
            tarix_yuklandi(pg, SD)
            pg.wait_for_timeout(300)
            n = {k: korinadi(pg, v) for k, v in SEL.items()}
            q = pg.evaluate("() => { const r = document.querySelector('.sup-row'); return r ? r.getAttribute('onclick') : null; }")
            t = korinadi(pg, ".sup-tarix")
            return n, q, t
        finally:
            ctx.close()
    try:
        _a, _aq, _ = sup_korinish("t180_admin")
        check("R1 NAZORAT: admin — hamma tugma ko'rinadi, qator — Kirim sahifasi", all((v or 0) > 0 for v in _a.values())
              and "/suppliers/receive" in (_aq or ""), (_a, _aq))
        _k, _kq, _kt = sup_korinish("t180_kor")
        check("R2 «Ta'minotchilar: Ko'rish» — yozuvchi tugmalar YO'Q (🕓 Tarix — bor)", all((v or 0) == 0 for v in _k.values()) and (_kt or 0) > 0,
              (_k, _kt))
        check("R3 «Ta'minotchilar: Ko'rish» — qator bosilsa tarix oynasi (Kirim sahifasi emas — u «ruxsat yo'q» berardi)",
              "openHistory(" in (_kq or "") and "/suppliers/receive" not in (_kq or ""), _kq)
    except Exception as _x:               # noqa: BLE001
        check("R1–R3 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("K. «Ta'minotchidan kirim» sahifasi (A1, C2, C3, C4, B6, C6, D1)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    SF = taminotchi("T180 Zeta")
    KIRIM_TAYYOR = """(a) => { const sel = document.getElementById('r-supplier'); sel.value = String(a.sid); currentSupplierId = a.sid;
      prodTypeChosen = true; document.getElementById('r-date').value = tkISO();
      apBasket = a.qatorlar.map(q => ({itemId: q[0], itemName: q[1], unit: 'kg', qty: q[2], price: q[3], total: buyurtmaJami(q[2], q[3]).jami,
                                       isPenoplast: false, volumePerUnit: null}));
      renderBasket(); document.getElementById('ap-paid-now').value = a.tolov; document.getElementById('ap-qty').value = '';
      document.getElementById('ap-price').value = ''; }"""
    ctx, pg = kontekst()
    try:
        ochiq(pg, f"/suppliers/receive?supplier_id={SF}")
        _k0, _q0 = soni(InventoryReceipt, supplier_id=SF), qoldiq(M2)
        _b = Bajar502()
        pg.route(re.compile(r".*/api/inventory/receipt$"), _b)
        baj(pg, KIRIM_TAYYOR, {"sid": SF, "qatorlar": [[M2, "T180 Boyoq", 4, 2500]], "tolov": "3000"}, kutish=200)
        msg_tozala(pg)
        baj(pg, "async () => { await submitReceive(); }", kutish=1200)
        _m1, _sv = msg_matn(pg), baj(pg, "() => apBasket.length", kutish=50)
        pg.unroute(re.compile(r".*/api/inventory/receipt$"))
        msg_tozala(pg)
        baj(pg, "async () => { await submitReceive(); }", kutish=1500)
        _m2 = msg_matn(pg)
        check("K1 (A1) kirim 502 — «Kirim natijasi noma'lum» (ilgari «❌ Xato: Kirim saqlanmadi»), savat QOLADI",
              NOMALUM in _m1 and "Kirim" in _m1 and _sv == 1 and _b.holat == [200], (_m1, _sv, _b.holat))
        check("K1b (A1) qayta «Kirimni tasdiqlash» — o'sha kalit: «ikkinchi marta yozilmadi», kirim BITTA, ombor +4 (ikki emas)",
              TAKROR in _m2 and "Kirim saqlandi" in _m2 and soni(InventoryReceipt, supplier_id=SF) == _k0 + 1 and qoldiq(M2) == _q0 + 4,
              (_m2, soni(InventoryReceipt, supplier_id=SF) - _k0, qoldiq(M2) - _q0))

        _p0 = len(sorovlar("/api/inventory/receipt"))
        baj(pg, KIRIM_TAYYOR, {"sid": SF, "qatorlar": [[M2, "T180 Boyoq", 2, 1000]], "tolov": "2500"}, kutish=200)
        msg_tozala(pg)
        baj(pg, "async () => { await submitReceive(); }", kutish=800)
        _m = msg_matn(pg)
        check("K2 (B6) «Hozir to'langan» 2 500 > materiallar 2 000 — saqlanmaydi, sabab (ilgari server jimgina 2 000 yozardi)",
              len(sorovlar("/api/inventory/receipt")) == _p0 and "ko'p bo'lishi mumkin emas" in _m, (_m, sorovlar("/api/inventory/receipt")[_p0:]))

        baj(pg, """() => { document.getElementById('ap-qty').value = '7'; document.getElementById('ap-price').value = '1 000,07'; apCalc(); }""",
            kutish=100)
        _jm = baj(pg, "() => document.getElementById('ap-total').value", kutish=50)
        check("K3 (C6) qator «Jami» 7 × 1 000,07 = 7 000.49 (server qoidasi; ilgari «7 000»)", "7 000.49" in str(_jm), _jm)
        baj(pg, "() => { document.getElementById('ap-qty').value = ''; document.getElementById('ap-price').value = ''; apBasket = []; renderBasket(); }",
            kutish=50)

        _t0 = len(tolovlar(SF))
        pg.route(re.compile(rf".*/api/suppliers/{SF}/payment$"), lambda r: r.abort())
        msg_tozala(pg)
        baj(pg, "async () => { document.getElementById('sup-quickpay-amount').value = '500'; await quickPaySupplier(); }", kutish=900)
        _m = msg_matn(pg)
        pg.unroute(re.compile(rf".*/api/suppliers/{SF}/payment$"))
        check("K4 (A3 / D1) «Eski qarzni to'lash» — internet uzildi: «To'lov natijasi noma'lum: internet aloqasi yo'q» (ilgari jim)",
              NOMALUM in _m and UZILISH in _m and len(tolovlar(SF)) == _t0, (_m, tolovlar(SF)))

        _n0 = soni(Supplier, name="T180 Kirimdan")
        _b = Bajar502(faqat="POST")
        pg.route(re.compile(r".*/api/suppliers$"), _b)
        msg_tozala(pg)
        baj(pg, "async () => { openNewSupplier(); document.getElementById('ns-name').value = 'T180 Kirimdan'; await saveNewSupplier(); }",
            kutish=900)
        _m1 = msg_matn(pg)
        pg.unroute(re.compile(r".*/api/suppliers$"))
        baj(pg, "async () => { await saveNewSupplier(); }", kutish=1200)
        _sel = baj(pg, "() => document.getElementById('r-supplier').selectedOptions[0].textContent", kutish=50)
        check("K5 (A4 / D1) «+ Yangi» ta'minotchi 502 — «natijasi noma'lum» (ilgari «Xato yuz berdi»); qayta — BITTA, tanlangan",
              NOMALUM in _m1 and soni(Supplier, name="T180 Kirimdan") == _n0 + 1 and _sel == "T180 Kirimdan", (_m1, _sel, _b.holat))

        pg.route(re.compile(rf".*/api/suppliers/{SD}/history.*"), lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, "(id) => { document.getElementById('r-supplier').value = String(id); onSupplierChange(); }", SD, kutish=1200)
        _st = [matn(pg, "#sup-credit"), matn(pg, "#sup-paid"), matn(pg, "#sup-debt")]
        _tb = matn(pg, "#rcv-history-body") or ""
        pg.unroute(re.compile(rf".*/api/suppliers/{SD}/history.*"))
        check("K6 (C2) statistika / tarix 502 — «—» va sabab (ilgari oldingi ta'minotchi raqamlari qolardi)",
              _st == ["—", "—", "—"] and "Ta'minotchi tarixi yuklanmadi" in _tb and SERVER in _tb, (_st, _tb))

        _u = Ushla()
        pg.route(re.compile(rf".*/api/suppliers/{SD}/history.*"), _u)
        _uf = Ushla()
        pg.route(re.compile(rf".*/api/suppliers/{SD}/purchased-items.*"), _uf)
        baj(pg, "(id) => { document.getElementById('r-supplier').value = String(id); onSupplierChange(); }", SD, kutish=400)
        baj(pg, "(id) => { document.getElementById('r-supplier').value = String(id); onSupplierChange(); }", SE, kutish=1500)
        _u.qoyib_yubor()
        _uf.qoyib_yubor()
        pg.wait_for_timeout(1200)
        _qz = matn(pg, "#sup-debt")
        _kut = baj(pg, "(d) => fmt(d) + \" so'm\"", js(C.get(f"/api/suppliers/{SE}/history")).get("debt"), kutish=50)
        _fl = baj(pg, "() => supplierFilterIds ? [...supplierFilterIds].sort((a, b) => a - b) : null", kutish=50)
        _fe = sorted({p["id"] for p in js(C.get(f"/api/suppliers/{SE}/purchased-items"))})
        pg.unroute(re.compile(rf".*/api/suppliers/{SD}/history.*"))
        pg.unroute(re.compile(rf".*/api/suppliers/{SD}/purchased-items.*"))
        check("K7 (C2) Delta → Epsilon tez, Delta javoblari KECH — qarz va materiallar filtri Epsilonniki",
              _qz == _kut and _fl == _fe, (_qz, _kut, _fl, _fe))
    except Exception as _x:               # noqa: BLE001
        check("K1–K7 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    ctx, pg = kontekst(oldin=[(re.compile(r".*/api/inventory$"), lambda r: r.fulfill(**SAHIFA_502))])
    try:
        ochiq(pg, f"/suppliers/receive?supplier_id={SF}")
        _op = matn(pg, "#ap-item option") or ""
        check("K8 (D1) materiallar 502 — «Materiallar ro'yxati yuklanmadi — server javob bermadi» (ilgari «❌ Xato (502)»)",
              "Materiallar ro'yxati yuklanmadi" in _op and SERVER in _op, _op)
    except Exception as _x:               # noqa: BLE001
        check("K8 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ── C4: qoralama
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/suppliers/receive", ilgak=False)
        _kalit = baj(pg, "() => (typeof RCV_DRAFT_KEY !== 'undefined') ? RCV_DRAFT_KEY : null", kutish=50)
        check("K9 (C4) qoralama kaliti — korxona va foydalanuvchi bo'yicha", _kalit == f"pdp_receive_draft_v1_1_{UID['t180_admin']}", _kalit)
        _qor = json.dumps({"supplierId": SD, "basket": [{"itemId": M1, "itemName": "T180 Akril", "unit": "kg", "qty": 3, "price": 700,
                                                         "total": 2100, "isPenoplast": False, "volumePerUnit": None}]})
        _kl = _kalit or "pdp_receive_draft_v1"
        pg.evaluate("(a) => { localStorage.clear(); localStorage.setItem(a[0], a[1]); }", [_kl, _qor])
        ochiq(pg, f"/suppliers/receive?supplier_id={SE}", ilgak=False)
        _sv = baj(pg, "() => apBasket.length", kutish=50)
        _bx = matn(pg, "#rcvMsgBox") or ""
        baj(pg, "() => saveDraft()", kutish=50)
        _saq = pg.evaluate("(k) => { const d = JSON.parse(localStorage.getItem(k) || 'null'); return d ? [d.supplierId, d.basket.length] : null; }", _kl)
        check("K10 (C4) Delta qoralamasi, sahifa Epsilon uchun ochildi — savat KO'CHIRILMADI (ilgari Delta materiallari Epsilon qarziga)",
              _sv == 0 and "Boshqa ta'minotchi uchun tugallanmagan kirim saqlangan" in _bx, (_sv, _bx))
        check("K10b (C4) bo'sh savat Delta qoralamasi ustidan YOZILMADI", _saq == [SD, 1], _saq)
        ochiq(pg, "/suppliers/receive", ilgak=False)
        _sv = baj(pg, "() => [apBasket.length, document.getElementById('r-supplier').value]", kutish=50)
        check("K11 (C4) ta'minotchisiz ochildi — Delta qoralamasi tiklandi (Delta tanlangan)", _sv == [1, str(SD)], _sv)
        # kech146 (zip 180, review 1 — №10, MOSLANDI): eski umumiy kalitdagi qoralama SHU korxona ta'minotchisiniki bo'lsa endi yangi kalitga
        # ko'chiriladi (XU8); bu yerda — BOSHQA korxona ta'minotchisi (ro'yxatda yo'q id): tiklanmaydi (asl kodda ham, yangisida ham)
        pg.evaluate("(a) => { localStorage.clear(); localStorage.setItem('pdp_receive_draft_v1', a); }",
                    json.dumps(dict(json.loads(_qor), supplierId=987654321)))
        ochiq(pg, "/suppliers/receive", ilgak=False)
        _sv = baj(pg, "() => apBasket.length", kutish=50)
        check("K12 (C4) umumiy (eski) kalitdagi qoralama — boshqa korxona ta'minotchisiniki — tiklanmaydi", _sv == 0, _sv)
        pg.evaluate("() => localStorage.clear()")
    except Exception as _x:               # noqa: BLE001
        check("K9–K12 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ── C2 / C3: «Kirimchi» (kirim yaratish; ta'minotchi ko'rish, to'lov, material yaratish — yo'q)
    SEL_K = {"«+ Yangi»": '[onclick^="openNewSupplier("]', "«Eski qarzni to'lash»": ".rcv-quickpay",
             "«🆕 yangi material»": '[onclick^="apToggleNewItem("]'}

    def kirim_korinish(user):
        ctx, pg = kontekst(user)
        try:
            SOROV[:] = []
            ochiq(pg, f"/suppliers/receive?supplier_id={SD}")
            pg.wait_for_timeout(500)
            n = {k: korinadi(pg, v) for k, v in SEL_K.items()}
            st = [matn(pg, "#sup-credit"), matn(pg, "#sup-debt")]
            tb = matn(pg, "#rcv-history-body") or ""
            gt = [x[1] for x in SOROV if x[0] == "GET" and f"/api/suppliers/{SD}/" in x[1]]
            return n, st, tb, gt
        finally:
            ctx.close()
    try:
        _a, _ast, _, _ = kirim_korinish("t180_admin")
        check("K13 NAZORAT: admin — «+ Yangi», «Eski qarzni to'lash», «🆕 yangi material» ko'rinadi, statistika bor",
              all((v or 0) > 0 for v in _a.values()) and _ast[0] not in (None, "—", "…"), (_a, _ast))
        _k, _kst, _ktb, _kgt = kirim_korinish("t180_kir")
        check("K14 (C3) «Kirimchi» — «+ Yangi», «Eski qarzni to'lash», «🆕 yangi material» YO'Q", all((v or 0) == 0 for v in _k.values()), _k)
        check("K15 (C2) «Kirimchi» — statistika «—», ruxsat sababi; tarix / filtr so'ralmaydi (ilgari «0 so'm» + 403)",
              _kst == ["—", "—"] and "Ko'rish» ruxsati bilan ko'rinadi" in _ktb and not _kgt, (_kst, _ktb, _kgt))
    except Exception as _x:               # noqa: BLE001
        check("K13–K15 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("V. Egasi qarorlari — sahifada (B1, B5, B4)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/suppliers")
        _qv = _qxarid(4, 100, 150)
        baj(pg, "(id) => { openHistory(id); }", SB)
        tarix_yuklandi(pg, SB)
        msg_tozala(pg)
        _n0 = len(sorovlar(f"/api/inventory/purchases/{_qv}", "DELETE"))
        baj(pg, """(id) => { window.__javob = [true, 'alt']; window.__savol = [];
                             window.customConfirm = async (a, b) => { window.__savol.push(String(typeof b === "string" ? b : a));
                                                                      return window.__javob.length ? window.__javob.shift() : true; };
                             return deletePurchase(id); }""", _qv, kutish=1500)
        _so = [x[1] for x in sorovlar(f"/api/inventory/purchases/{_qv}", "DELETE")[_n0:]]
        _sv = baj(pg, "() => window.__savol", kutish=50)
        check("V1 (B5) to'langan xaridni o'chirish — so'raldi («150 so'm darhol to'langan»), «avans» tanlandi → `?tolov=avans`, xabar",
              _so == [f"/api/inventory/purchases/{_qv}", f"/api/inventory/purchases/{_qv}?tolov=avans"]
              and any("150 so'm darhol to'langan" in (x or "") for x in (_sv or [])) and "avans" in msg_matn(pg)
              and db_ishi(lambda d: d.get(InventoryPurchase, _qv)) is None and len(_avans(_qv)) == 1, (_so, _sv, msg_matn(pg)))

        _qe = _qxarid(10, 100, 400)
        tarix_yuklandi(pg, SB)
        baj(pg, "(id) => { openHistory(id); }", SB)
        tarix_yuklandi(pg, SB)
        msg_tozala(pg)
        _n0 = len(sorovlar(f"/api/inventory/purchases/{_qe}", "PUT"))
        baj(pg, """(id) => { window.__javob = [true]; window.__savol = []; window.__kirit = ['3', '100'];
                             window.kiritishOyna = async () => window.__kirit.shift();
                             window.customConfirm = async (a, b) => { window.__savol.push(String(typeof b === "string" ? b : a));
                                                                      return window.__javob.length ? window.__javob.shift() : true; };
                             return editPurchase(id, 10, 100, true); }""", _qe, kutish=1500)
        _so = [x[1] for x in sorovlar(f"/api/inventory/purchases/{_qe}", "PUT")[_n0:]]
        check("V2 (B4) summa to'langanidan past (400 → 300) — so'raldi, «Ortiqchasini to'lovdan ayirish» → `?tolov=ochirish`, to'lov 300",
              _so == [f"/api/inventory/purchases/{_qe}", f"/api/inventory/purchases/{_qe}?tolov=ochirish"]
              and [x[0] for x in _bogtolov(_qe)] == [300.0] and "to'lovdan ayirildi" in msg_matn(pg), (_so, _bogtolov(_qe), msg_matn(pg)))

        QY = taminotchi("T180 Yashiriladigan")
        xarid(C, MQ, QY, 1, 100, paid_now=50)
        ochiq(pg, "/suppliers")
        msg_tozala(pg)
        baj(pg, """(id) => { window.__savol = []; window.customConfirm = async (a, b) => { window.__savol.push(String(typeof b === "string" ? b : a));
                             return true; }; return deleteSupplier(id, 50); }""", QY, kutish=1500)
        _sv = baj(pg, "() => window.__savol", kutish=50)
        check("V3 (B1) qarzli ta'minotchini o'chirish — tasdiqda «YASHIRILADI … Kassa o'zgarmaydi», xabar «Ro'yxatdan yashirildi»",
              any("YASHIRILADI" in (x or "") and "Kassa o'zgarmaydi" in (x or "") for x in (_sv or []))
              and "Ro'yxatdan yashirildi" in msg_matn(pg) and "T180 Yashiriladigan" not in (matn(pg, "#supList") or ""), (_sv, msg_matn(pg)))
        _qi = _qxarid(2, 100, 80)
        ochiq(pg, "/inventory")
        _n0 = len(sorovlar(f"/api/inventory/purchases/{_qi}", "DELETE"))
        baj(pg, """(id) => { window.__toast = []; window.invToast = (t) => { window.__toast.push(String(t)); };
                             window.__javob = [true, true]; window.__savol = [];
                             window.customConfirm = async (a, b) => { window.__savol.push(String(typeof b === "string" ? b : a));
                                                                      return window.__javob.length ? window.__javob.shift() : true; };
                             window.setTimeout = () => 0; window.openPurchaseHistory = () => null;   // sahifa qayta yuklanmasin
                             return deletePurchase(id, 'T180 Gips', 2); }""", _qi, kutish=1500)
        _so = [x[1] for x in sorovlar(f"/api/inventory/purchases/{_qi}", "DELETE")[_n0:]]
        _tt = baj(pg, "() => window.__toast", kutish=50)
        check("V4 (B5) Omborxona «Xaridlar tarixi» dan o'chirish — so'raldi, «To'lovni ham o'chirish» → `?tolov=ochirish`, to'lov o'chdi",
              _so == [f"/api/inventory/purchases/{_qi}", f"/api/inventory/purchases/{_qi}?tolov=ochirish"] and _bogtolov(_qi) == []
              and any("to'lovi ham o'chirildi" in (x or "") for x in (_tt or [])), (_so, _tt, _bogtolov(_qi)))
    except Exception as _x:               # noqa: BLE001
        check("V1–V4 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("JU. «Ta'minotchidan kirim» — «Jami xarid», «Boshlang'ich» (B7, B8)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, f"/suppliers/receive?supplier_id={SJ}")
        kut(pg, """() => (document.getElementById('sup-credit').textContent || '').includes("so'm")
                         && !!document.querySelector('#rcv-history-body .kirim-holat')""")
        _raq = lambda sel: re.sub(r"\D", "", matn(pg, sel) or "")
        _jst = [_raq("#sup-credit"), _raq("#sup-paid"), _raq("#sup-debt")]
        check("JU1 (B7) «Jami xarid» 1 502 000 (naqd ham), «To'langan» 1 202 000 (to'lovlar + naqd), «Qarz» 300 000 — Jami − To'langan = Qarz "
              "(ilgari «Jami xarid» 502 000, «To'langan» 202 000)", _jst == ["1502000", "1202000", "300000"], _jst)
        _bh = baj(pg, """() => [...document.querySelectorAll('#rcv-history-body .kirim-holat[data-holat="boshlangich"]')]
                               .map(x => [x.textContent.trim(), x.title])""", kutish=50)
        check("JU2 (B8) tarixda boshlang'ich qator — «Boshlang'ich» (ilgari «Qisman» / «Nasiya»), izohi «ta'minotchiga qarz emas»",
              _bh and len(_bh) == 1 and _bh[0][0] == "Boshlang'ich" and "qarz emas" in _bh[0][1], _bh)
    except Exception as _x:               # noqa: BLE001
        check("JU1–JU2 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("R180i-U. Review 1 tuzatishlari — sahifada (№2 savat, №6 yangi ta'minotchi, №8 to'lov kaliti, №10 eski qoralama)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    class Ketma:
        """Mos so'rovlar navbat bilan: '502' — serverga yetadi va bajariladi, brauzerga 502; 'uz' — uzilish (serverga yetmaydi); qolgani —
        o'tadi."""

        def __init__(self, *amallar):
            self.amallar = list(amallar)
            self.holat = []

        def __call__(self, route):
            a = self.amallar.pop(0) if self.amallar else None
            if a == "502":
                try:
                    self.holat.append(route.fetch().status)
                except Exception as e:     # noqa: BLE001
                    self.holat.append(type(e).__name__)
                route.fulfill(**SAHIFA_502)
            elif a == "uz":
                self.holat.append("uz")
                route.abort()
            else:
                route.continue_()

    def _transport(nom):
        return db_ishi(lambda d: d.query(TransportExpense).filter(TransportExpense.materials_note == nom).count())

    XUS = taminotchi("T180 XU Savat")
    XUM1, XUM2, XUM3 = material("T180 XU Akril"), material("T180 XU Boyoq"), material("T180 XU Gips")
    _SAVAT = """(a) => { apBasket = a.qatorlar.map(q => ({itemId: q[0], itemName: q[1], unit: 'kg', qty: q[2], price: q[3], total: q[2] * q[3]}));
      renderApBasket(); ['ap-qty', 'ap-price', 'ap-paid-now', 'ap-transport-cost'].forEach(id => { document.getElementById(id).value = ''; });
      document.getElementById('ap-transport-payer').value = a.tp; apToggleTransport();
      document.getElementById('ap-transport-cost').value = a.tc; return saveAddPurchase(); }"""
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/suppliers")
        baj(pg, "(id) => { openHistory(id); }", XUS)
        tarix_yuklandi(pg, XUS)
        baj(pg, "() => openAddPurchase()", kutish=900)
        _tr1, _tr2 = _transport("T180 XU Akril"), _transport("T180 XU Boyoq")
        pg.route(re.compile(rf".*/api/inventory/{XUM2}/purchase$"), lambda r: r.abort())
        msg_tozala(pg)
        baj(pg, _SAVAT, {"qatorlar": [[XUM1, "T180 XU Akril", 2, 1000], [XUM2, "T180 XU Boyoq", 3, 500]], "tp": "self", "tc": "5 000"},
            kutish=1500)
        pg.unroute(re.compile(rf".*/api/inventory/{XUM2}/purchase$"))
        _hol = baj(pg, """() => ({forma: getComputedStyle(document.getElementById('addPurchaseForm')).display,
                                  savat: getComputedStyle(document.getElementById('ap-basket')).display,
                                  qator: apBasket.map(l => l.itemId), tp: document.getElementById('ap-transport-payer').value,
                                  tc: document.getElementById('ap-transport-cost').value})""", kutish=50)
        check("XU1 (№2) savatdagi 2-qator saqlanmadi — forma OCHIQ, savat ko'rinadi (Bo'yoq), transport maydonlari tozalandi (transport 1-qator "
              "bilan yozildi; ilgari forma yopilardi, transport qolardi)",
              isinstance(_hol, dict) and _hol.get("forma") == "block" and _hol.get("savat") != "none" and _hol.get("qator") == [XUM2]
              and _hol.get("tp") == "none" and _hol.get("tc") == "" and _transport("T180 XU Akril") == _tr1 + 1, (_hol, msg_matn(pg)))
        tarix_yuklandi(pg, XUS)
        baj(pg, "() => { openAddPurchase(); openAddPurchase(); }", kutish=700)
        _q = baj(pg, "() => [getComputedStyle(document.getElementById('addPurchaseForm')).display, apBasket.map(l => l.itemId)]", kutish=50)
        check("XU2 (№2) «+ Xarid qo'shish» bilan yopib-qayta ochish — savatdagi Bo'yoq QOLDI (ilgari savat tozalanardi)",
              _q == ["block", [XUM2]], _q)
        tarix_yuklandi(pg, XUS)
        msg_tozala(pg)
        baj(pg, "() => saveAddPurchase()", kutish=1500)
        _xs = (soni(InventoryPurchase, supplier_id=XUS, inventory_id=XUM1), soni(InventoryPurchase, supplier_id=XUS, inventory_id=XUM2))
        check("XU3 (№2) qayta saqlash — Bo'yoq BITTA yozildi, transport xarajati jami BITTA (ikkinchi transport yo'q)",
              _xs == (1, 1) and _transport("T180 XU Akril") == _tr1 + 1 and _transport("T180 XU Boyoq") == _tr2, (_xs, msg_matn(pg)))

        _k = Ketma("502")
        pg.route(re.compile(rf".*/api/inventory/{XUM3}/purchase$"), _k)
        tarix_yuklandi(pg, XUS)
        baj(pg, "() => { if (getComputedStyle(document.getElementById('addPurchaseForm')).display === 'none') openAddPurchase(); }",
            kutish=700)
        msg_tozala(pg)
        baj(pg, _SAVAT, {"qatorlar": [[XUM3, "T180 XU Gips", 1, 700], [XUM3, "T180 XU Gips", 1, 700]], "tp": "none", "tc": ""}, kutish=1500)
        _n1 = soni(InventoryPurchase, supplier_id=XUS, inventory_id=XUM3)
        _sv = baj(pg, "() => apBasket.length", kutish=50)
        tarix_yuklandi(pg, XUS)
        msg_tozala(pg)
        baj(pg, "() => saveAddPurchase()", kutish=1500)
        _n2 = soni(InventoryPurchase, supplier_id=XUS, inventory_id=XUM3)
        pg.unroute(re.compile(rf".*/api/inventory/{XUM3}/purchase$"))
        check("XU4 (№2) savatda bir xil IKKI qator, 1-sining javobi yo'qoldi (server yozgan): 2-si O'Z kaliti bilan yozildi (2 ta), qayta "
              "saqlash — takror, jami 2 (ilgari 2-si 1-ning javobini olib «saqlandi» derdi-yu, yozilmasdi)",
              _n1 == 2 and _sv == 1 and _n2 == 2 and _k.holat == [200], (_n1, _sv, _n2, _k.holat, msg_matn(pg)))

        baj(pg, "() => closeHistoryModal()", kutish=100)
        _b = Bajar502(faqat="POST")
        pg.route(re.compile(r".*/api/suppliers$"), _b)
        baj(pg, "() => { openSupplierModal(); document.getElementById('s-name').value = 'T180 XU Birinchi'; }", kutish=200)
        baj(pg, "async () => { await saveSupplier(); }", kutish=900)
        pg.unroute(re.compile(r".*/api/suppliers$"))
        baj(pg, "() => { document.getElementById('s-name').value = 'T180 XU Ikkinchi'; }", kutish=50)
        baj(pg, "async () => { await saveSupplier(); }", kutish=1200)
        check("XU5 (№6) «+ Ta'minotchi»: «A» natijasi noma'lum, nom «C» ga o'zgartirildi — «C» YARATILDI (ilgari server «A» javobini qaytarib, "
              "«C» jimgina yaratilmasdi)", soni(Supplier, name="T180 XU Birinchi") == 1 and soni(Supplier, name="T180 XU Ikkinchi") == 1
              and _b.holat == [200], (soni(Supplier, name="T180 XU Birinchi"), soni(Supplier, name="T180 XU Ikkinchi"), _b.holat))
        _b = Bajar502(faqat="POST")
        pg.route(re.compile(r".*/api/suppliers$"), _b)
        baj(pg, "() => { openSupplierModal(); document.getElementById('s-name').value = 'T180 XU Uchinchi'; }", kutish=200)
        baj(pg, "async () => { await saveSupplier(); }", kutish=900)
        pg.unroute(re.compile(r".*/api/suppliers$"))
        msg_tozala(pg)
        baj(pg, "async () => { await saveSupplier(); }", kutish=1200)
        _m = msg_matn(pg)
        check("XU5b (№6) o'sha nom bilan qayta — BITTA ta'minotchi, xabarda nomi va «ikkinchi marta yozilmadi» (ilgari jim)",
              soni(Supplier, name="T180 XU Uchinchi") == 1 and TAKROR in _m and "T180 XU Uchinchi" in _m, (_m, _b.holat))

        ochiq(pg, "/suppliers")
        baj(pg, "(id) => { openHistory(id); }", XUS)
        tarix_yuklandi(pg, XUS)
        _t0 = len(tolovlar(XUS))
        _b = Bajar502()
        pg.route(re.compile(rf".*/api/suppliers/{XUS}/payment$"), _b)
        baj(pg, "async () => { document.getElementById('pay-amount').value = '1 000'; await savePayment(); }", kutish=900)
        pg.unroute(re.compile(rf".*/api/suppliers/{XUS}/payment$"))
        tarix_yuklandi(pg, XUS)
        baj(pg, "async () => { document.getElementById('pay-amount').value = '2 000'; await savePayment(); }", kutish=1200)
        check("XU7 (№8) to'lov 1 000 natijasi noma'lum, keyin BOSHQA summa 2 000 — 2 000 ham yozildi (ilgari «takror» deb yutilardi, "
              "xabar esa «2 000 so'm to'lov qilindi» derdi)", tolovlar(XUS)[_t0:] == [1000.0, 2000.0] and _b.holat == [200],
              (tolovlar(XUS)[_t0:], _b.holat, msg_matn(pg)))
    except Exception as _x:               # noqa: BLE001
        check("XU1–XU7 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    ctx, pg = kontekst()
    try:
        ochiq(pg, "/suppliers/receive")
        _b = Bajar502(faqat="POST")
        pg.route(re.compile(r".*/api/suppliers$"), _b)
        baj(pg, "async () => { openNewSupplier(); document.getElementById('ns-name').value = 'T180 XU Kirim A'; await saveNewSupplier(); }",
            kutish=900)
        pg.unroute(re.compile(r".*/api/suppliers$"))
        baj(pg, "async () => { document.getElementById('ns-name').value = 'T180 XU Kirim C'; await saveNewSupplier(); }", kutish=1200)
        _sel = baj(pg, "() => { const s = document.getElementById('r-supplier'); return [s.value, s.selectedOptions[0].textContent]; }",
                   kutish=50)
        _idc = db_ishi(lambda d: (d.query(Supplier.id).filter(Supplier.name == "T180 XU Kirim C").first() or [None])[0])
        check("XU6 (№6) «+ Yangi»: «A» natijasi noma'lum, «C» kiritildi — «C» yaratildi, tanlangan qiymat «C» niki (ilgari ro'yxatda «C», "
              "qiymati «A» — kirim «A» ga yozilardi)", _idc is not None and _sel == [str(_idc), "T180 XU Kirim C"], (_sel, _idc, _b.holat))
        _b = Bajar502(faqat="POST")
        pg.route(re.compile(r".*/api/suppliers$"), _b)
        baj(pg, "async () => { openNewSupplier(); document.getElementById('ns-name').value = 'T180 XU Kirim G'; await saveNewSupplier(); }",
            kutish=900)
        pg.unroute(re.compile(r".*/api/suppliers$"))
        msg_tozala(pg)
        baj(pg, "async () => { await saveNewSupplier(); }", kutish=1200)
        _sel = baj(pg, "() => { const s = document.getElementById('r-supplier'); return [s.value, s.selectedOptions[0].textContent]; }",
                   kutish=50)
        _idg = db_ishi(lambda d: (d.query(Supplier.id).filter(Supplier.name == "T180 XU Kirim G").first() or [None])[0])
        check("XU6b (№6) o'sha nom bilan qayta — BITTA, tanlangan — o'sha ta'minotchi (server nomi), «ikkinchi marta yozilmadi» izohi",
              soni(Supplier, name="T180 XU Kirim G") == 1 and _sel == [str(_idg), "T180 XU Kirim G"] and TAKROR in msg_matn(pg),
              (_sel, _idg, msg_matn(pg)))

        ochiq(pg, f"/suppliers/receive?supplier_id={XUS}")
        pg.wait_for_timeout(600)
        _t0 = len(tolovlar(XUS))
        _b = Bajar502()
        pg.route(re.compile(rf".*/api/suppliers/{XUS}/payment$"), _b)
        baj(pg, "async () => { document.getElementById('sup-quickpay-amount').value = '300'; await quickPaySupplier(); }", kutish=900)
        pg.unroute(re.compile(rf".*/api/suppliers/{XUS}/payment$"))
        baj(pg, "async () => { document.getElementById('sup-quickpay-amount').value = '400'; await quickPaySupplier(); }", kutish=1200)
        check("XU7b (№8) «Eski qarzni to'lash»: 300 natijasi noma'lum, keyin 400 — 400 ham yozildi (ilgari yutilardi)",
              tolovlar(XUS)[_t0:] == [300.0, 400.0] and _b.holat == [200], (tolovlar(XUS)[_t0:], _b.holat, msg_matn(pg)))
    except Exception as _x:               # noqa: BLE001
        check("XU6–XU7b bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    ctx, pg = kontekst()
    try:
        ochiq(pg, "/suppliers/receive", ilgak=False)
        _kl = baj(pg, "() => (typeof RCV_DRAFT_KEY !== 'undefined') ? RCV_DRAFT_KEY : null", kutish=50)
        _bir = {"itemId": XUM1, "itemName": "T180 XU Akril", "unit": "kg", "qty": 3, "price": 700, "total": 2100, "isPenoplast": False,
                "volumePerUnit": None}
        _qor = json.dumps({"supplierId": XUS, "basket": [_bir]})
        pg.evaluate("(a) => { localStorage.clear(); localStorage.setItem('pdp_receive_draft_v1', a); }", _qor)
        ochiq(pg, "/suppliers/receive", ilgak=False)
        _sv = baj(pg, "() => [apBasket.length, document.getElementById('r-supplier').value]", kutish=50)
        _ls = pg.evaluate("(k) => [localStorage.getItem('pdp_receive_draft_v1') === null, !!localStorage.getItem(k)]", _kl)
        check("XU8 (№10) eski UMUMIY kalitdagi qoralama (shu korxona ta'minotchisi), yangi kalitda qoralama yo'q — tiklandi, yangi kalitga "
              "ko'chdi, eski kalit O'CHIRILDI (ilgari qoralama yo'qolardi, narxli eski yozuv brauzerda qolardi)",
              _sv == [1, str(XUS)] and _ls == [True, True], (_sv, _ls))
        _qor2 = json.dumps({"supplierId": XUS, "basket": [_bir, dict(_bir, qty=5, total=3500)]})
        _qorb = json.dumps({"supplierId": 987654321, "basket": [_bir]})
        pg.evaluate("(a) => { localStorage.clear(); localStorage.setItem('pdp_receive_draft_v1', a[0]); localStorage.setItem(a[1], a[2]); }",
                    [_qorb, _kl or "yoq", _qor2])
        ochiq(pg, "/suppliers/receive", ilgak=False)
        _sv = baj(pg, "() => apBasket.length", kutish=50)
        _ls = pg.evaluate("(k) => [localStorage.getItem('pdp_receive_draft_v1') === null, JSON.parse(localStorage.getItem(k) || 'null')]", _kl)
        check("XU8b (№10) yangi kalitda o'z qoralamasi bor, eskisida boshqa korxona ta'minotchisiniki — o'zinikisi tiklandi (2 ta), eskisi "
              "ko'chirilmadi va O'CHIRILDI", _sv == 2 and _ls and _ls[0] is True and isinstance(_ls[1], dict)
              and len(_ls[1].get("basket") or []) == 2, (_sv, _ls))
        pg.evaluate("() => localStorage.clear()")
    except Exception as _x:               # noqa: BLE001
        check("XU8 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
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
