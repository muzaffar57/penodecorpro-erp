#!/usr/bin/env python3
"""
test_transport230.py — kech165 (zip 230 «Xarid o'chirilsa transport — so'raladi»; egasi QARORI 31.10 «Har safar so'rasin (Tavsiya)»).

NIMA UCHUN KERAK
  Ta'minotchilar sahifasidan xarid «O'z hisobimdan» transport bilan kiritilsa, transport Moliyaga alohida xarajat bo'lib yoziladi
  (izoh «<material> xaridi bilan birga»), lekin xaridga BOG'LANMAGAN edi. Xarid o'chirilsa — xarid va ombor qaytardi, transport esa
  Moliyada jimgina QOLARDI (Kassa transport summasicha kam, xarid yo'q); Kirim hujjati bekor qilinsa esa uning transporti o'chadi.
  O'LCHANGAN (`work/k230/probe230.py`, asl = zip 229): 50 000 / 40 000 transport o'chirishdan keyin ham Moliyada.
  Endi: `transport_expenses.purchase_id`; o'chirishda 409 `purchase_has_transport` — egasi tanlaydi: «Transportni ham o'chirish»
  (`?transport=ochirish`) yoki «Transport Moliyada qolsin» (`?transport=qoldirish`). To'lov savoli (zip 180) — birinchi.
BO'LIMLAR
  S — statik: ustun, marshrut parametri, crud funksiyalari, sahifalarda tugma matnlari.
  A — API: bog'lanish; tanlovsiz 409 — HECH NARSA o'zgarmaydi (xarid, ombor, transport, Kassa); `ochirish` — Kassa xariddan oldingi holatga;
      `qoldirish` — transport qoladi, bog'lanish uziladi, izohga belgi; noto'g'ri tanlov — 400; to'lov + transport — ikki savol ketma-ket;
      transportsiz / «Ta'minotchi hisobidan» — savolsiz (avvalgidek); savat (transport 1-qatorda) — xabarda boshqa qatorlar soni;
      eski yozuv (ustunsiz) — izoh / vaqt / yaratgan bo'yicha topiladi, bir ma'nosiz — so'ralmaydi (avvalgidek); begona korxona transporti
      tegilmaydi; Kirim hujjati qatori — avvalgidek; zaxira → tiklash — bog'lanish saqlanadi.
  P — PG parallel: ikki o'chirish (`ochirish`) — biri 200, biri 404, 500 yo'q; o'chirish ↔ Moliyadan transportni o'chirish — 500 yo'q.
  U — HAQIQIY brauzer: Ta'minotchilar (transport; to'lov + transport → `?tolov=avans&transport=qoldirish`), Omborxona «Xaridlar tarixi».
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (U bo'limi faqat SQLite / TF1 da).
Asl kodga (zip 229) qarshi QULAMAYDI — yiqiladi (savol yo'q, transport qoladi).
ISHLATISH: python3 tools/test_transport230.py
"""
import os
import io
import re
import sys
import glob
import json
import time
import socket
import tempfile
import threading
import contextlib
from datetime import timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "transport230_test"
_T = tempfile.mkdtemp(prefix="t230_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't230.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, InventoryPurchase, SupplierPayment, TransportExpense,   # noqa: E402
                    ErrorLog)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
_PID = getattr(TransportExpense, "purchase_id", None)       # asl kodda (zip 229) ustun yo'q — sinov qulamasin


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


def det(r):
    d = js(r).get("detail") if isinstance(js(r), dict) else None
    return d if isinstance(d, dict) else {}


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T230 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t230_admin", PAROL, UserRole.ADMIN, "T230 Admin", company_id=1)
    auth.create_user(s, "t230_b", PAROL, UserRole.ADMIN, "T230 B Admin", company_id=2)
s.close()
main._send_telegram = lambda msg, *a, **k: True
crud.PUL_TAKROR_SONIYA = 0


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


C = mijoz("t230_admin")
CB = mijoz("t230_b")


def taminotchi(nom, c=None):
    r = (c or C).post("/api/suppliers", json={"name": nom, "phone": "+998901112233"})
    assert r.status_code == 200, r.text
    return js(r)["id"]


def material(nom, c=None):
    r = (c or C).post("/api/inventory", json={"item_name": nom, "unit": "kg", "category": "Kimyoviy qo'shimchalar",
                                              "stock_quantity": 0, "price_per_unit": 0, "min_stock": 0})
    assert r.status_code == 200, r.text
    return js(r)["id"]


def xarid(mid, sup, q, n, transport=0, payer="self", paid_now=0.0, izoh="Ta'minotchilar sahifasidan qo'shildi", c=None):
    return (c or C).post(f"/api/inventory/{mid}/purchase", json={
        "quantity": q, "price_per_unit": n, "paid_now": paid_now, "supplier_id": sup, "notes": izoh,
        "transport_payer": payer if transport else "none", "transport_cost": transport})


def oxirgi_xarid(mid):
    return db_ishi(lambda d: d.query(InventoryPurchase.id).filter(InventoryPurchase.inventory_id == mid)
                   .order_by(InventoryPurchase.id.desc()).first()[0])


def xarid_bormi(pid):
    return db_ishi(lambda d: d.get(InventoryPurchase, pid) is not None)


def qoldiq(mid):
    return db_ishi(lambda d: round(float(d.get(Inventory, mid).stock_quantity or 0), 6))


def transport(tid):
    return db_ishi(lambda d: (lambda t: None if t is None else {"amount": float(t.amount), "notes": t.notes,
                                                                 "pid": getattr(t, "purchase_id", None)})(d.get(TransportExpense, tid)))


def transportlar(nom):
    """«<nom> xaridi bilan birga» transportlari id lari (shu korxona)."""
    return db_ishi(lambda d: [t.id for t in d.query(TransportExpense).filter(TransportExpense.company_id == 1,
                                                                             TransportExpense.notes.like(f"{nom} xaridi bilan birga%"))
                              .order_by(TransportExpense.id).all()])


def kassa(c=None):
    return round(float(js((c or C).get("/api/finance/cash-balance")).get("balance") or 0), 2)


def bogtolov(pid):
    return db_ishi(lambda d: [round(float(t.amount), 2) for t in d.query(SupplierPayment).filter(SupplierPayment.purchase_id == pid).all()]
                   if hasattr(SupplierPayment, "purchase_id") else [])


def bekor(pid, **q):
    return C.delete(f"/api/inventory/purchases/{pid}", params=q)


SA = taminotchi("T230 Alfa")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik — ustun, marshrut, crud, sahifalar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_crud_src = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
_main_src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
_inv_src = open(os.path.join(ROOT, "templates", "inventory.html"), encoding="utf-8").read()
_sup_src = open(os.path.join(ROOT, "templates", "suppliers.html"), encoding="utf-8").read()
check("S1 `transport_expenses.purchase_id` (Integer, NULL, FK siz — `SupplierPayment.purchase_id` naqshi)",
      _PID is not None and not list(TransportExpense.__table__.c.purchase_id.foreign_keys)
      and TransportExpense.__table__.c.purchase_id.nullable, str(_PID))
check("S2 crud: `XARID_TRANSPORT_TANLOV` = (ochirish, qoldirish), `XaridTransportTanloviKerak` (409 `purchase_has_transport`, to'lov "
      "istisnosining vorisi), `xarid_transportlari`, `delete_purchase(…, transport=…)`",
      getattr(crud, "XARID_TRANSPORT_TANLOV", None) == ("ochirish", "qoldirish")
      and issubclass(getattr(crud, "XaridTransportTanloviKerak", type(None)), getattr(crud, "XaridTolovTanloviKerak", Exception))
      and callable(getattr(crud, "xarid_transportlari", None))
      and "transport" in __import__("inspect").signature(crud.delete_purchase).parameters)
check("S3 marshrut `DELETE /api/inventory/purchases/{id}` — `transport` parametri; xarid marshruti transportni xarid raqami bilan yozadi",
      "tolov: Optional[str] = None, transport: Optional[str] = None" in _main_src
      and 'purchase_id=result["purchase"].id      # kech165 (zip 230)' in _main_src)
check("S4 sahifalar: «Transportni ham o'chirish» / «Transport Moliyada qolsin» — Omborxona va Ta'minotchilar; `purchase_has_transport`",
      all("Transportni ham o'chirish" in x and "Transport Moliyada qolsin" in x and "purchase_has_transport" in x
          for x in (_inv_src, _sup_src)))
check("S5 transport savoli HECH NARSA o'zgartirilmasdan OLDIN (delete_purchase: savollar → keyin `db.delete`)",
      (lambda f: f.find("raise XaridTransportTanloviKerak(") != -1
       and f.find("raise XaridTransportTanloviKerak(") < f.find("db.delete(t)")
       and f.find("raise XaridTransportTanloviKerak(") < f.find("inv.stock_quantity = new_qty"))(
          _crud_src[_crud_src.find("def delete_purchase("):_crud_src.find("KIRIM_XARAJAT_TURLARI = (")]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API — xarid o'chirilsa transport")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
M1 = material("T230 Akril")
_k0 = kassa()
_r = xarid(M1, SA, 10, 1000, transport=50_000)
_p1 = oxirgi_xarid(M1)
_t1 = (transportlar("T230 Akril") or [None])[-1]
check("A1 xarid «O'z hisobimdan» transport 50 000 bilan — transport xarid raqamiga bog'langan",
      _r.status_code == 200 and _t1 and (transport(_t1) or {}).get("pid") == _p1, (_r.status_code, _r.text[:200], transport(_t1), _p1))
_k1 = kassa()
_r2 = bekor(_p1)
check("A2 tanlovsiz o'chirish — 409 `purchase_has_transport`, summa 50 000, xabar «50 000 so'm transport xarajati»; HECH NARSA o'zgarmadi",
      _r2.status_code == 409 and det(_r2).get("type") == "purchase_has_transport" and float(det(_r2).get("summa") or 0) == 50_000
      and "50 000 so'm transport xarajati" in str(det(_r2).get("message")) and xarid_bormi(_p1) and qoldiq(M1) == 10
      and (transport(_t1) or {}).get("pid") == _p1 and kassa() == _k1,
      (_r2.status_code, _r2.text[:300], xarid_bormi(_p1), qoldiq(M1), transport(_t1), kassa(), _k1))
_r3 = bekor(_p1, transport="xato")
check("A3 noto'g'ri tanlov — 400, hech narsa o'zgarmadi", _r3.status_code == 400 and xarid_bormi(_p1) and transport(_t1) is not None,
      (_r3.status_code, _r3.text[:200]))
_r4 = bekor(_p1, transport="ochirish")
check("A4 `transport=ochirish` — xarid ham, transport ham o'chdi; ombor 0; Kassa xariddan OLDINGI holatda",
      _r4.status_code == 200 and not xarid_bormi(_p1) and transport(_t1) is None and qoldiq(M1) == 0 and kassa() == _k0,
      (_r4.status_code, _r4.text[:200], xarid_bormi(_p1), transport(_t1), qoldiq(M1), kassa(), _k0))

_r = xarid(M1, SA, 4, 1000, transport=30_000)
_p2 = oxirgi_xarid(M1)
_t2 = transportlar("T230 Akril")[-1]
_k2 = kassa()
_r5 = bekor(_p2, transport="qoldirish")
check("A5 `transport=qoldirish` — xarid o'chdi, transport 30 000 Moliyada QOLDI (bog'lanish uzildi, izohda «(xarid #N bekor qilingan)»), "
      "Kassa o'zgarmadi (ta'minotchidan nasiya — Kassa ta'sirsiz)",
      _r5.status_code == 200 and not xarid_bormi(_p2) and (transport(_t2) or {}).get("amount") == 30_000
      and (transport(_t2) or {}).get("pid") is None and f"(xarid #{_p2} bekor qilingan)" in ((transport(_t2) or {}).get("notes") or "")
      and kassa() == _k2, (_r5.status_code, _r5.text[:200], transport(_t2), kassa(), _k2))
_r5b = C.get("/api/transport-expenses")
check("A5b qolgan transport Moliya ro'yxatida («Transport» — izohi bilan)",
      _r5b.status_code == 200 and any(isinstance(x, dict) and x.get("id") == _t2 for x in (js(_r5b) if isinstance(js(_r5b), list)
                                                                                           else js(_r5b).get("items", []))),
      (_r5b.status_code, str(js(_r5b))[:300]))

# to'lov + transport — ikki savol ketma-ket
_r = xarid(M1, SA, 5, 1000, transport=20_000, paid_now=2_000)
_p3 = oxirgi_xarid(M1)
_t3 = transportlar("T230 Akril")[-1]
_r6a = bekor(_p3)
_r6b = bekor(_p3, tolov="ochirish")
_r6c = bekor(_p3, tolov="ochirish", transport="ochirish")
check("A6 to'lov + transport: 1) 409 `purchase_has_payment`; 2) `tolov=ochirish` — 409 `purchase_has_transport` (to'lov HALI joyida);"
      " 3) ikkalasi bilan — 200, to'lov ham, transport ham o'chdi",
      _r6a.status_code == 409 and det(_r6a).get("type") == "purchase_has_payment"
      and _r6b.status_code == 409 and det(_r6b).get("type") == "purchase_has_transport"
      and _r6c.status_code == 200 and not xarid_bormi(_p3) and transport(_t3) is None and bogtolov(_p3) == [],
      (_r6a.status_code, det(_r6a).get("type"), _r6b.status_code, det(_r6b).get("type"), _r6c.status_code, transport(_t3), bogtolov(_p3)))
check("A6b 2-qadamda (transport savoli) to'lov o'chmagan edi — 409 dan keyin to'lov 2 000 bog'langan holda turardi",
      _r6b.status_code == 409, _r6b.status_code)
_r = xarid(M1, SA, 5, 1000, transport=15_000, paid_now=2_000)
_p4 = oxirgi_xarid(M1)
_t4 = transportlar("T230 Akril")[-1]
_r7 = bekor(_p4, tolov="avans", transport="qoldirish")
_av = db_ishi(lambda d: [float(t.amount) for t in d.query(SupplierPayment).filter(SupplierPayment.notes.like(f"Avans (bekor qilingan xarid #{_p4}:%"))])
check("A7 `tolov=avans&transport=qoldirish` — to'lov avans bo'lib qoldi, transport Moliyada qoldi",
      _r7.status_code == 200 and _av == [2000.0] and (transport(_t4) or {}).get("pid") is None and transport(_t4) is not None,
      (_r7.status_code, _r7.text[:200], _av, transport(_t4)))

# transportsiz / «Ta'minotchi hisobidan» — savolsiz
_n0 = len(transportlar("T230 Akril"))
_r = xarid(M1, SA, 2, 1000)
_p5 = oxirgi_xarid(M1)
_r8 = bekor(_p5)
_r = xarid(M1, SA, 2, 1000, transport=9_000, payer="supplier")
_p6 = oxirgi_xarid(M1)
_r9 = bekor(_p6)
check("A8 transportsiz va «Ta'minotchi hisobidan» transportli xarid — savolsiz 200 (avvalgidek), transport yozuvi yo'q",
      _r8.status_code == 200 and _r9.status_code == 200 and len(transportlar("T230 Akril")) == _n0,
      (_r8.status_code, _r8.text[:200], _r9.status_code, _r9.text[:200], transportlar("T230 Akril")))

# savat: transport 1-qatorda, 2 qator (izoh «Bir vaqtda ko'p material xaridi»)
M2, M3 = material("T230 Mel"), material("T230 Kley")
SAVAT = "Bir vaqtda ko'p material xaridi"
xarid(M2, SA, 3, 1000, transport=40_000, izoh=SAVAT)
xarid(M3, SA, 7, 2000, izoh=SAVAT)
_ps1, _ps2 = oxirgi_xarid(M2), oxirgi_xarid(M3)
_r10 = bekor(_ps2)
_r11 = bekor(_ps1)
check("A9 savat: transportsiz 2-qator — savolsiz 200; transportli 1-qator — 409 (2-qator o'chgach — xabarda «yana N ta» YO'Q)",
      _r10.status_code == 200 and _r11.status_code == 409 and "yana" not in str(det(_r11).get("message")),
      (_r10.status_code, _r11.status_code, det(_r11)))
bekor(_ps1, transport="ochirish")
xarid(M2, SA, 3, 1000, transport=40_000, izoh=SAVAT)
xarid(M3, SA, 7, 2000, izoh=SAVAT)
xarid(M1, SA, 1, 1000, izoh=SAVAT)
_ps1 = oxirgi_xarid(M2)
xarid(M3, SA, 1, 2000, izoh=SAVAT)              # OLDINGI (alohida) savatning qatori — 1 daqiqa oldin
_oldingi = oxirgi_xarid(M3)
db_ishi(lambda d: setattr(d.get(InventoryPurchase, _oldingi), "purchased_at",
                          d.get(InventoryPurchase, _ps1).purchased_at - timedelta(seconds=60)))
_r12 = bekor(_ps1)
check("A10 savat (3 qator): transportli 1-qator o'chirilsa — xabarda «shu mashinada yana 2 ta material xaridi kiritilgan» (1 daqiqa "
      "OLDINGI boshqa savat qatori sanalmaydi — review230 №3)",
      _r12.status_code == 409 and "yana 2 ta material xaridi" in str(det(_r12).get("message")), (_r12.status_code, det(_r12)))
bekor(_oldingi)
_r12b = bekor(_ps1, transport="qoldirish")
check("A10b savat 1-qatori `qoldirish` — transport 40 000 Moliyada (boshqa qatorlar uchun), qolgan qatorlar joyida",
      _r12b.status_code == 200 and xarid_bormi(oxirgi_xarid(M3)) and oxirgi_xarid(M3) != _oldingi and 40_000 in [transport(t)["amount"] for t in transportlar("T230 Mel")],
      (_r12b.status_code, [transport(t) for t in transportlar("T230 Mel")]))

# eski yozuv (ustungacha): bog'lanish yo'q — izoh / vaqt / yaratgan bo'yicha
M4 = material("T230 Gips")


def _eski_qil(tid):
    def f(d):
        t = d.get(TransportExpense, tid)
        if _PID is not None:
            t.purchase_id = None
    db_ishi(f)


xarid(M4, SA, 6, 1000, transport=25_000)
_pe = oxirgi_xarid(M4)
_te = transportlar("T230 Gips")[-1]
_eski_qil(_te)
_r13 = bekor(_pe)
check("A11 eski yozuv (bog'lanishsiz, izoh «T230 Gips xaridi bilan birga», bir vaqtda) — topildi: 409, summa 25 000",
      _r13.status_code == 409 and det(_r13).get("type") == "purchase_has_transport" and float(det(_r13).get("summa") or 0) == 25_000,
      (_r13.status_code, _r13.text[:300]))
_r13b = bekor(_pe, transport="ochirish")
check("A11b eski yozuv `ochirish` — transport o'chdi", _r13b.status_code == 200 and transport(_te) is None, (_r13b.status_code, transport(_te)))
# eski — vaqt oynasidan tashqari (transport xariddan 60 s keyin) — so'ralmaydi, tegilmaydi
xarid(M4, SA, 6, 1000, transport=26_000)
_pe2 = oxirgi_xarid(M4)
_te2 = transportlar("T230 Gips")[-1]
_eski_qil(_te2)
db_ishi(lambda d: setattr(d.get(TransportExpense, _te2), "expense_date", d.get(InventoryPurchase, _pe2).purchased_at + timedelta(seconds=60)))
_r14 = bekor(_pe2)
check("A12 eski yozuv, vaqt oynasidan tashqari (60 s) — savolsiz 200, transport tegilmadi (avvalgidek)",
      _r14.status_code == 200 and (transport(_te2) or {}).get("amount") == 26_000, (_r14.status_code, transport(_te2)))
# eski — bir ma'nosiz: shu materialning ikkinchi xaridi bir vaqtda (transport qaysiniki — noma'lum)
xarid(M4, SA, 1, 1000, transport=27_000)
_pa = oxirgi_xarid(M4)
_ta = transportlar("T230 Gips")[-1]
xarid(M4, SA, 2, 1000)
_pb = oxirgi_xarid(M4)
_eski_qil(_ta)
db_ishi(lambda d: setattr(d.get(InventoryPurchase, _pb), "purchased_at", d.get(TransportExpense, _ta).expense_date))
_x13 = db_ishi(lambda d: [len(crud.xarid_transportlari(d, d.get(InventoryPurchase, x), company_id=1)) for x in (_pa, _pb)]
               if hasattr(crud, "xarid_transportlari") else None)
_r15a = bekor(_pb)
check("A13 eski yozuv bir ma'nosiz (shu materialning ikki xaridi bir vaqtda) — ikkalasiga ham topilmaydi; biri savolsiz 200, transport "
      "tegilmadi (avvalgidek)",
      _x13 == [0, 0] and _r15a.status_code == 200 and (transport(_ta) or {}).get("amount") == 27_000, (_x13, _r15a.status_code, transport(_ta)))
_r15b = bekor(_pa, transport="qoldirish")
check("A13b ikkinchisi qolganda — endi bir ma'noli (so'raladi; `qoldirish` — transport joyida)",
      _r15b.status_code == 200 and (transport(_ta) or {}).get("amount") == 27_000, (_r15b.status_code, transport(_ta)))
# review230 №2: B (transportsiz), 5 s dan keyin A (shu material, transport T); A eski kodda o'chirilgan — T bog'lanishsiz qolgan.
# B o'chirilganda T «B niki» deb topilmasin (transport xariddan keyingi 2 s ichida yoziladi)
xarid(M4, SA, 1, 1000)
_pB = oxirgi_xarid(M4)
xarid(M4, SA, 1, 1000, transport=31_000)
_pA = oxirgi_xarid(M4)
_tA = transportlar("T230 Gips")[-1]
_eski_qil(_tA)


def _eski_ochir(d):
    a, b = d.get(InventoryPurchase, _pA), d.get(InventoryPurchase, _pB)
    d.get(TransportExpense, _tA).expense_date = b.purchased_at + timedelta(seconds=5)
    d.delete(a)
db_ishi(_eski_ochir)
_r15c = bekor(_pB)
check("A13c eski: B dan 5 s keyingi (o'chirilgan) A xaridining transporti — B o'chirilganda so'ralmaydi (200), transport tegilmadi",
      _r15c.status_code == 200 and (transport(_tA) or {}).get("amount") == 31_000, (_r15c.status_code, _r15c.text[:200], transport(_tA)))
xarid(M4, SA, 1, 1000)
_pC = oxirgi_xarid(M4)
db_ishi(lambda d: setattr(d.get(TransportExpense, _tA), "expense_date", d.get(InventoryPurchase, _pC).purchased_at - timedelta(seconds=1)))
_r15d = bekor(_pC)
check("A13d eski: transport xariddan 1 s OLDIN yozilgan — shu xaridniki emas (transport xariddan keyin yoziladi), so'ralmaydi",
      _r15d.status_code == 200 and (transport(_tA) or {}).get("amount") == 31_000, (_r15d.status_code, transport(_tA)))
# eski — boshqa foydalanuvchi yozgan (yaratgan farqli) — so'ralmaydi
xarid(M4, SA, 1, 1000, transport=28_000)
_pc = oxirgi_xarid(M4)
_tc = transportlar("T230 Gips")[-1]
_eski_qil(_tc)
db_ishi(lambda d: setattr(d.get(TransportExpense, _tc), "created_by", "Boshqa xodim"))
_r16 = bekor(_pc)
check("A14 eski yozuv, transportni BOSHQA xodim yozgan — so'ralmaydi (200), transport tegilmadi",
      _r16.status_code == 200 and (transport(_tc) or {}).get("amount") == 28_000, (_r16.status_code, transport(_tc)))

# begona korxona: B dagi xuddi shu izoh / vaqt / yaratgan transporti A ning eski xaridiga «topilmaydi»
xarid(M4, SA, 1, 1000, transport=29_000)
_pd = oxirgi_xarid(M4)
_td = transportlar("T230 Gips")[-1]
_eski_qil(_td)


def _begona(d):
    t = d.get(TransportExpense, _td)
    d.add(TransportExpense(company_id=2, amount=11_111, notes=t.notes, created_by=t.created_by, expense_date=t.expense_date))
    d.delete(t)
db_ishi(_begona)
_r17 = bekor(_pd)
_bt = db_ishi(lambda d: [float(t.amount) for t in d.query(TransportExpense).filter(TransportExpense.company_id == 2).all()])
check("A15 B korxonaning bir xil izoh / vaqt / yaratganli transporti — A ning xaridi o'chirilganda so'ralmaydi, B niki tegilmadi",
      _r17.status_code == 200 and _bt == [11_111.0], (_r17.status_code, _r17.text[:200], _bt))
_r17b = CB.delete(f"/api/inventory/purchases/{oxirgi_xarid(M1)}", params={"transport": "ochirish"})
check("A15b B korxona A ning xaridini o'chira olmaydi (404)", _r17b.status_code == 404, _r17b.status_code)

# Kirim hujjati qatori — avvalgidek (hujjat xarajati — hujjat bekorida)
_rk = C.post("/api/inventory/receipt", json={
    "items": [{"inventory_id": M1, "quantity": 3, "price_per_unit": 1000}], "transport_cost": 50_000, "tushirish_cost": 0,
    "yuklash_cost": 0, "boshqa_cost": 0, "add_to_cost": False, "supplier_id": SA, "document_number": "", "paid_now": 0, "notes": ""})
_kp = oxirgi_xarid(M1)
_r18 = bekor(_kp)
check("A16 Kirim hujjati qatori (qo'shimcha xarajatli) — 409 `receipt_line_locked` (avvalgidek, transport savoli emas)",
      _rk.status_code == 200 and _r18.status_code == 409 and det(_r18).get("type") == "receipt_line_locked",
      (_rk.status_code, _r18.status_code, det(_r18)))

# zaxira → tiklash: bog'lanish saqlanadi
M5 = material("T230 Sement")
xarid(M5, SA, 2, 1000, transport=12_000)
_pz = oxirgi_xarid(M5)
_tz = transportlar("T230 Sement")[-1]
_s = SessionLocal()
_zax = json.loads(json.dumps(crud.export_full_backup(_s, company_id=1), default=str))
_s.close()
_zt = [r for r in ((_zax.get("tables") or {}).get("transport_expenses") or []) if r.get("id") == _tz]
_s = SessionLocal()
try:
    _nat = crud.import_full_backup(_s, _zax, company_id=1, replace=True)
except Exception as e:                  # noqa: BLE001
    _nat = {"success": False, "message": f"{type(e).__name__}: {e}"}
_s.close()
_r19 = bekor(_pz)
check("A17 zaxirada `transport_expenses.purchase_id`; tiklashdan keyin bog'lanish saqlangan — o'chirishda so'raladi",
      _zt and _zt[0].get("purchase_id") == _pz and _nat.get("success") is True and _r19.status_code == 409
      and det(_r19).get("type") == "purchase_has_transport", (_zt, str(_nat)[:200], _r19.status_code, _r19.text[:200]))
bekor(_pz, transport="ochirish")
check("A18 server xatosi (ErrorLog) yo'q", db_ishi(lambda d: d.query(ErrorLog).count()) == 0,
      db_ishi(lambda d: [(e.path, (e.message or "")[:120]) for e in d.query(ErrorLog).limit(5).all()]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PG — parallel")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    from concurrent.futures import ThreadPoolExecutor
    C2 = mijoz("t230_admin")
    _asl_qulf = crud.xarid_transportlari

    def _sekin(*a, **k):
        r = _asl_qulf(*a, **k)
        time.sleep(0.6)
        return r
    crud.xarid_transportlari = _sekin
    try:
        xarid(M1, SA, 3, 1000, transport=18_000)
        _pp = oxirgi_xarid(M1)
        _tp = transportlar("T230 Akril")[-1]
        with ThreadPoolExecutor(2) as ex:
            _f = [ex.submit(lambda c: c.delete(f"/api/inventory/purchases/{_pp}", params={"transport": "ochirish"}), c) for c in (C, C2)]
            _kod = sorted(f.result().status_code for f in _f)
        check("P1 bir xaridni PARALLEL ikki marta `transport=ochirish` — 200 + 404, 500 yo'q; transport o'chdi, ombor bir marta qaytdi",
              _kod == [200, 404] and transport(_tp) is None and not xarid_bormi(_pp), (_kod, transport(_tp)))
        xarid(M1, SA, 3, 1000, transport=19_000)
        _pq = oxirgi_xarid(M1)
        _tq = transportlar("T230 Akril")[-1]
        with ThreadPoolExecutor(2) as ex:
            _f1 = ex.submit(lambda: C.delete(f"/api/inventory/purchases/{_pq}", params={"transport": "ochirish"}))
            time.sleep(0.2)
            _f2 = ex.submit(lambda: C2.delete(f"/api/transport-expenses/{_tq}"))
            _k1, _k2 = _f1.result().status_code, _f2.result().status_code
        check("P2 xaridni o'chirish (`ochirish`, qulf ostida) ↔ shu transportni Moliyadan o'chirish PARALLEL — 200 + 404 (ilgari Moliya "
              "tomoni yolg'on 200 — 0 qator o'chirib), transport yo'q, xarid yo'q",
              (_k1, _k2) == (200, 404) and transport(_tq) is None and not xarid_bormi(_pq), (_k1, _k2, transport(_tq), xarid_bormi(_pq)))
        xarid(M1, SA, 3, 1000, transport=21_000)
        _pr = oxirgi_xarid(M1)
        _tr = transportlar("T230 Akril")[-1]
        with ThreadPoolExecutor(2) as ex:
            _f2 = ex.submit(lambda: C2.delete(f"/api/transport-expenses/{_tr}"))
            _f1 = ex.submit(lambda: C.delete(f"/api/inventory/purchases/{_pr}", params={"transport": "qoldirish"}))
            _k1, _k2 = _f1.result().status_code, _f2.result().status_code
        check("P2b Moliyadan transportni o'chirish ↔ xaridni o'chirish (`qoldirish`) PARALLEL — 500 yo'q; transport yo'q, xarid yo'q",
              500 not in (_k1, _k2) and _k2 == 200 and transport(_tr) is None and not xarid_bormi(_pr),
              (_k1, _k2, transport(_tr), xarid_bormi(_pr)))
    finally:
        crud.xarid_transportlari = _asl_qulf
    check("P3 server xatosi (ErrorLog) yo'q", db_ishi(lambda d: d.query(ErrorLog).count()) == 0,
          db_ishi(lambda d: [(e.path, (e.message or "")[:160]) for e in d.query(ErrorLog).limit(5).all()]))
else:
    print("  (faqat PG rejimida)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
br = pw_ctx = server = None
if PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
    try:
        from playwright.sync_api import sync_playwright
        PW_BOR, _pw_x = True, ""
    except Exception as _e:                # noqa: BLE001
        PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
    import uvicorn                                 # noqa: E402

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
    if PW_BOR and server.started:
        pw_ctx = sync_playwright().start()
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                  "chrome-linux", "chrome"))):
            _exe = _yol
        try:
            br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
        except Exception as _e:            # noqa: BLE001
            br = None
            _pw_x = f"{type(_e).__name__}: {_e}"
    check("U0 lokal server va Chromium", bool(server.started and br), _pw_x)
    JS_XATO, SOROV = [], []

    def kontekst():
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
        ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
        pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""))) if "/api/" in q.url else None)
        pg.goto(B + "/login")
        pg.fill("input[name=username]", "t230_admin")
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
        return ctx, pg

    def baj(pg, ifoda, arg=None, kutish=700):
        x = None
        try:
            x = pg.evaluate(ifoda, arg) if arg is not None else pg.evaluate(ifoda)
        except Exception as e:             # noqa: BLE001 — eski kodda funksiya yo'q
            x = "XATO: " + str(e)[:160]
        pg.wait_for_timeout(kutish)
        return x

    def kut(pg, ifoda, ms=8000):
        try:
            pg.wait_for_function(ifoda, timeout=ms)
            return True
        except Exception:                  # noqa: BLE001
            return False

    def sorovlar(nima, usul="DELETE", bas=0):
        """`bas` — shu qadamdan oldingi so'rovlar soni (SQLite o'chirilgan xarid raqamini qayta beradi — eski qadam so'rovlari sanalmasin)."""
        return [x[1] for x in SOROV[bas:] if (x[1] == nima or x[1].startswith(nima + "?")) and x[0] == usul]

    SAVOL = """(javoblar) => { window.__javob = javoblar; window.__savol = []; window.__msg = []; window.__toast = [];
      window.customConfirm = async (a, b, o) => { window.__savol.push([String(typeof b === "string" ? b : a), (o || b || {}).okText || '',
                                                                       (o || b || {}).altText || '']);
                                                  return window.__javob.length ? window.__javob.shift() : false; };
      window.showMsg = (t, ty) => { window.__msg.push(String(t)); };
      window.invToast = (t) => { window.__toast.push(String(t)); };
      window.setTimeout = () => 0; window.openPurchaseHistory = () => null; }"""

    if br:
        ctx, pg = kontekst()
        try:
            MU = material("T230 UI Akril")
            # Ta'minotchilar: transport — «Transportni ham o'chirish»
            xarid(MU, SA, 4, 1000, transport=33_000)
            _pu1 = oxirgi_xarid(MU)
            _tu1 = transportlar("T230 UI Akril")[-1]
            pg.goto(B + "/suppliers", wait_until="networkidle")
            baj(pg, "(id) => { openHistory(id); }", SA, kutish=300)
            kut(pg, f"() => typeof openHistory !== 'undefined' && openHistory.yuklandi === {SA}")
            baj(pg, SAVOL, [True, True], kutish=100)
            _b1 = len(SOROV)
            baj(pg, "(id) => deletePurchase(id)", _pu1, kutish=1500)
            _sv = baj(pg, "() => window.__savol", kutish=50) or []
            _ms = baj(pg, "() => window.__msg", kutish=50) or []
            check("U1 Ta'minotchilar: transportli xarid — so'raldi («33 000 so'm transport», tugmalar «Transportni ham o'chirish» / "
                  "«Transport Moliyada qolsin»), → `?transport=ochirish`, xabar «transport xarajati ham o'chirildi», transport yo'q",
                  sorovlar(f"/api/inventory/purchases/{_pu1}", bas=_b1) == [f"/api/inventory/purchases/{_pu1}",
                                                                    f"/api/inventory/purchases/{_pu1}?transport=ochirish"]
                  and any("33 000 so'm transport" in x[0] and x[1] == "Transportni ham o'chirish"
                          and x[2] == "Transport Moliyada qolsin" for x in _sv if isinstance(x, list))
                  and any("transport xarajati ham o'chirildi" in x for x in _ms) and transport(_tu1) is None,
                  (sorovlar(f"/api/inventory/purchases/{_pu1}", bas=_b1), _sv, _ms, transport(_tu1)))
            # Ta'minotchilar: to'lov + transport — «avans», keyin «qolsin»
            xarid(MU, SA, 4, 1000, transport=34_000, paid_now=1_500)
            _pu2 = oxirgi_xarid(MU)
            _tu2 = transportlar("T230 UI Akril")[-1]
            baj(pg, "(id) => { openHistory(id, true); }", SA, kutish=300)
            kut(pg, f"() => typeof openHistory !== 'undefined' && openHistory.yuklandi === {SA}")
            baj(pg, SAVOL, [True, "alt", "alt"], kutish=100)
            _b2 = len(SOROV)
            baj(pg, "(id) => deletePurchase(id)", _pu2, kutish=2000)
            _sv = baj(pg, "() => window.__savol", kutish=50) or []
            _ms = baj(pg, "() => window.__msg", kutish=50) or []
            check("U2 Ta'minotchilar: to'lov + transport — avval to'lov, keyin transport so'raldi; → `?tolov=avans` → "
                  "`?tolov=avans&transport=qoldirish`; xabar «… avans bo'lib qoldi; transport xarajati Moliyada qoldi»",
                  sorovlar(f"/api/inventory/purchases/{_pu2}", bas=_b2) == [f"/api/inventory/purchases/{_pu2}",
                                                                    f"/api/inventory/purchases/{_pu2}?tolov=avans",
                                                                    f"/api/inventory/purchases/{_pu2}?tolov=avans&transport=qoldirish"]
                  and len(_sv) == 3 and "1 500 so'm darhol to'langan" in _sv[1][0] and "34 000 so'm transport" in _sv[2][0]
                  and any("avans bo'lib qoldi; transport xarajati Moliyada qoldi" in x for x in _ms)
                  and not xarid_bormi(_pu2) and (transport(_tu2) or {}).get("pid") is None and transport(_tu2) is not None,
                  (sorovlar(f"/api/inventory/purchases/{_pu2}", bas=_b2), _sv, _ms, transport(_tu2)))
            # Ta'minotchilar: transport savolida «Bekor» — hech narsa o'zgarmaydi
            xarid(MU, SA, 4, 1000, transport=35_000)
            _pu3 = oxirgi_xarid(MU)
            _tu3 = transportlar("T230 UI Akril")[-1]
            baj(pg, SAVOL, [True, False], kutish=100)
            _b3 = len(SOROV)
            baj(pg, "(id) => deletePurchase(id)", _pu3, kutish=1500)
            check("U3 Ta'minotchilar: transport savolida «Bekor» — ikkinchi so'rov yo'q, xarid va transport joyida",
                  sorovlar(f"/api/inventory/purchases/{_pu3}", bas=_b3) == [f"/api/inventory/purchases/{_pu3}"] and xarid_bormi(_pu3)
                  and (transport(_tu3) or {}).get("pid") == _pu3, (sorovlar(f"/api/inventory/purchases/{_pu3}", bas=_b3), transport(_tu3)))
            # Omborxona «Xaridlar tarixi»: transport — «qolsin»
            pg.goto(B + "/inventory", wait_until="networkidle")
            baj(pg, SAVOL, [True, "alt"], kutish=100)
            _b4 = len(SOROV)
            baj(pg, "(id) => deletePurchase(id, 'T230 UI Akril', 4)", _pu3, kutish=1500)
            _sv = baj(pg, "() => window.__savol", kutish=50) or []
            _tt = baj(pg, "() => window.__toast", kutish=50) or []
            check("U4 Omborxona: transportli xarid — so'raldi, «Transport Moliyada qolsin» → `?transport=qoldirish`, xabar, transport qoldi",
                  sorovlar(f"/api/inventory/purchases/{_pu3}", bas=_b4) == [f"/api/inventory/purchases/{_pu3}",
                                                                         f"/api/inventory/purchases/{_pu3}?transport=qoldirish"]
                  and any("35 000 so'm transport" in x[0] for x in _sv if isinstance(x, list))
                  and any("transport xarajati Moliyada qoldi" in x for x in _tt) and not xarid_bormi(_pu3)
                  and (transport(_tu3) or {}).get("pid") is None and transport(_tu3) is not None,
                  (sorovlar(f"/api/inventory/purchases/{_pu3}", bas=_b4), _sv, _tt, transport(_tu3)))
            # Omborxona: to'lov + transport — «To'lovni ham o'chirish», «Transportni ham o'chirish»
            xarid(MU, SA, 4, 1000, transport=36_000, paid_now=1_000)
            _pu4 = oxirgi_xarid(MU)
            _tu4 = transportlar("T230 UI Akril")[-1]
            baj(pg, SAVOL, [True, True, True], kutish=100)
            _b5 = len(SOROV)
            baj(pg, "(id) => deletePurchase(id, 'T230 UI Akril', 4)", _pu4, kutish=2000)
            _tt = baj(pg, "() => window.__toast", kutish=50) or []
            check("U5 Omborxona: to'lov + transport — `?tolov=ochirish` → `?tolov=ochirish&transport=ochirish`; xabar «to'lovi ham "
                  "o'chirildi; transport xarajati ham o'chirildi»; to'lov ham, transport ham yo'q",
                  sorovlar(f"/api/inventory/purchases/{_pu4}", bas=_b5) == [f"/api/inventory/purchases/{_pu4}",
                                                                    f"/api/inventory/purchases/{_pu4}?tolov=ochirish",
                                                                    f"/api/inventory/purchases/{_pu4}?tolov=ochirish&transport=ochirish"]
                  and "✓ Xarid bekor qilindi — to'lovi ham o'chirildi; transport xarajati ham o'chirildi." in _tt
                  and transport(_tu4) is None and bogtolov(_pu4) == [] and not xarid_bormi(_pu4),
                  (sorovlar(f"/api/inventory/purchases/{_pu4}", bas=_b5), _tt, transport(_tu4), bogtolov(_pu4)))
            # Omborxona: transportsiz, to'lovli — avvalgidek (zip 180 xabari o'zgarmagan)
            xarid(MU, SA, 2, 1000, paid_now=500)
            _pu5 = oxirgi_xarid(MU)
            baj(pg, SAVOL, [True, True], kutish=100)
            _b6 = len(SOROV)
            baj(pg, "(id) => deletePurchase(id, 'T230 UI Akril', 2)", _pu5, kutish=1500)
            _tt = baj(pg, "() => window.__toast", kutish=50) or []
            check("U6 Omborxona: faqat to'lov (transportsiz) — avvalgidek: `?tolov=ochirish`, xabar «✓ Xarid bekor qilindi — to'lovi ham "
                  "o'chirildi.»",
                  sorovlar(f"/api/inventory/purchases/{_pu5}", bas=_b6) == [f"/api/inventory/purchases/{_pu5}",
                                                                    f"/api/inventory/purchases/{_pu5}?tolov=ochirish"]
                  and "✓ Xarid bekor qilindi — to'lovi ham o'chirildi." in _tt, (sorovlar(f"/api/inventory/purchases/{_pu5}", bas=_b6), _tt))
        except Exception as _x:            # noqa: BLE001
            check("U1–U6 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
        finally:
            ctx.close()
        check("U7 sahifalarda JS xatosi yo'q", not JS_XATO, JS_XATO[:5])
    if br:
        try:
            br.close()
        except Exception:                  # noqa: BLE001
            pass
    if pw_ctx:
        try:
            pw_ctx.stop()
        except Exception:                  # noqa: BLE001
            pass
    if server:
        server.should_exit = True

print(f"\n{'=' * 66}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
print("=" * 66)
if FAILED:
    print("Yiqilganlar:")
    for x in FAILED:
        print("  - " + x)
sys.exit(0 if FAIL == 0 else 1)
