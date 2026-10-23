#!/usr/bin/env python3
"""
test_ochirish_jurnal209.py — kech155 (zip 209 «Qisman topshirilgan donali — 500 va o'chirish jurnali»; texnik tuzatish).

NIMA UCHUN KERAK
  (1) review207 M3 (YUQORI, O'LCHANGAN): o'lchamsiz «Donali» (eni / qalinligi / «1 metrdan nechta» bo'sh — narx-nisbat yo'li) detalli
      buyurtmaning faqat bir qismi topshirilgach «Tayyor» va «O'chirish» — 500 (`services._ProratedItem` da `unit_price` yo'q edi);
      buyurtma «Jarayonda» qolib, yakunlab ham, o'chirib ham bo'lmasdi.
  (2) ORD-068 (production, 23.10): hech narsa topshirilmagan buyurtma BUTUNLAY o'chirilganda to'lovlari jim o'chardi; savatdan
      «Butunlay o'chirish» da ham (cascade); yuk xatini o'chirish jurnalga yozilmasdi; buyurtma o'chirildi yozuvida nima o'chgani yo'q edi.
BO'LIMLAR
  F — ilovaning O'Z API si: qisman topshirilgan o'lchamsiz «Donali» — «Tayyor» 200, qolgan qism penoplasti AYNAN qaytadi (hajm = birlik
      narxi ÷ asosiy narx × qolgan miqdor), qolgan detal 0; o'chirish 200 (savatga), qolgan qism qaytadi, tiklash AYNAN teskari; detalning
      o'zi qisman topshirilgan (10 dan 4) — qolgan 6 tasi; «Blok» qisman topshirilgan — qolgan ulush bloklari (mustaqil tekshiruv T4);
      o'lchamli «Donali» va panel — avvalgidek (nazorat).
  J — jurnal: butunlay o'chirishda har to'lov (summa, tur, usul, qabul qilgan, sana, «buyurtma bilan birga o'chirildi»), buyurtma
      yozuvida jami / detallar (nomi — miqdor birlik) / to'lovlar / «butunlay»; to'lovsiz — «to'lov yo'q»; yumshoq o'chirish —
      «O'chirilganlar» da; savatdan butunlay — to'lovlar va «savatdan butunlay»; yuk xati o'chirilganda — raqami, sanasi, kim topshirdi /
      qabul qildi, detallar (ko'pi bilan 12), transport, to'lov taqdiri (o'chirildi / saqlab qolindi); rad etilgan o'chirish («Tayyor»
      buyurtma yuk xati) — yozuv YO'Q; qisman topshirilgan buyurtma o'chirilsa — yakunlashdan OLDINGI jami; savatdagi buyurtmani qayta
      o'chirish — 409, yozuvsiz; yozuvlar korxonaga tegishli; «Faoliyat jurnali» sahifasida ko'rinadi.
  K — Ustalar KPI (egasi savoli 23.10): «Tayyor mahsulotlar» dan buyurtmasiz sotuvlar soni alohida — API (`sales_count`), shablon,
      HAQIQIY brauzerda qator matni «0 ta buyurtma · 2 ta sotuv»; hisob (sotuv summasi) o'zgarmagan.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL. Asl kodga (zip 208) qarshi
QULAMAYDI — yiqiladi (F — 500, J — yozuvlar yo'q).
ISHLATISH: python3 tools/test_ochirish_jurnal209.py
"""
import os
import io
import sys
import tempfile
import datetime
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "ochirish_jurnal209_test"
_T = tempfile.mkdtemp(prefix="k209_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k209.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
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


with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master, ActivityLog, Payment, Order, OrderItem   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k209_a", PAROL, UserRole.ADMIN, "K209 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K209 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P1 = Project(company_id=1, client_name="Sardor K209", project_name="Andijon K209", client_phone="+998901112209", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K209 Usta", phone="+998900002090")
s.add_all([PENO, P1, US])
s.commit()
ID = {"PENO": PENO.id, "P1": P1.id, "US": US.id}
s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lg = C.post("/login", data={"username": "k209_a", "password": PAROL}, follow_redirects=False)
TK = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).date()


def detal(nom, cat, miqdor, narx, en=0, qal=0, uz=0):
    return {"name": nom, "category": cat, "width": en, "thickness": qal, "length": uz, "quantity": miqdor, "unit_price": narx,
            "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}


def buyurtma(detallar):
    tana = {"project_id": ID["P1"], "order_type": "product", "recipe_id": None, "master_id": ID["US"],
            "deadline": (TK + datetime.timedelta(days=5)).isoformat(), "is_draft": False, "base_price": 600000, "loy_kg": None,
            "items": detallar}
    r = C.post("/api/orders?confirm_shortage=true", json=tana)
    return (r.json() or {}) if r.status_code == 200 else {"_xato": (r.status_code, r.text[:300])}


def qoldiq():
    _s = SessionLocal()
    try:
        return float(_s.query(Inventory).filter(Inventory.id == ID["PENO"]).first().stock_quantity)
    finally:
        _s.close()


def topshir(oid, nomlar, ulush=1.0, tolov=None, **qosh):
    h = (C.get(f"/api/orders/{oid}/delivery-status").json() or {}).get("items") or []
    tana = {"order_id": oid, "items": [{"order_item_id": x["id"], "quantity": round(float(x["remaining"]) * ulush, 3)} for x in h
                                       if x["name"] in nomlar],
            "received_by": qosh.get("qabul", "K209 Mijoz"), "notes": "", "transport_carrier": qosh.get("tashuvchi", ""),
            "transport_cost": qosh.get("transport", 0), "transport_payer": "client" if qosh.get("transport") else "none"}
    if tolov:
        tana["payment_amount"] = tolov
    r = C.post("/api/deliveries", json=tana)
    return r.status_code, (r.json() if r.status_code == 200 else r.text[:300])


def jurnal(**f):
    _s = SessionLocal()
    try:
        q = _s.query(ActivityLog)
        for k, v in f.items():
            q = q.filter(getattr(ActivityLog, k) == v)
        return [(a.action, a.entity_type, a.entity_id, a.entity_label, a.new_value, a.old_value, a.company_id, a.performed_by)
                for a in q.order_by(ActivityLog.id).all()]
    finally:
        _s.close()


def songi_id():
    _s = SessionLocal()
    try:
        return max([a.id for a in _s.query(ActivityLog).all()] or [0])
    finally:
        _s.close()


def yangi_yozuvlar(dan):
    _s = SessionLocal()
    try:
        return [(a.action, a.entity_type, a.entity_id, a.entity_label, a.new_value or "", a.company_id, a.performed_by)
                for a in _s.query(ActivityLog).filter(ActivityLog.id > dan).order_by(ActivityLog.id).all()]
    finally:
        _s.close()


def tolov(oid, summa, tur="zaklat"):
    return C.post("/api/payments", json={"order_id": oid, "amount": summa, "payment_type": tur, "payment_method": "naqd",
                                         "received_by": "K209 Kassir"}).status_code


EPS = 1e-6
check("T0 kirish", _lg.status_code in (302, 303), _lg.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F — qisman topshirilgan o'lchamsiz «Donali» (review207 M3)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# A: 4 dona × 6 000 → 0,04 m³; B: 10 dona × 12 000 → 0,20 m³ (asosiy narx 600 000 so'm / m³; blok — 1 m³)
_q0 = qoldiq()
F1 = buyurtma([detal("K209 Dona A", "dona", 4, 6000), detal("K209 Dona B", "dona", 10, 12000)])
_q1 = qoldiq()
_t1 = topshir(F1.get("id"), ["K209 Dona A"])
_r1 = C.post(f"/api/orders/{F1.get('id')}/ready")
_q2 = qoldiq()
check("F1 yaratish — ikkala detal hajmi yechildi (0,04 + 0,20 = 0,24 blok); A to'liq topshirildi",
      F1.get("id") and abs((_q0 - _q1) - 0.24) < EPS and _t1[0] == 200, (F1.get("_xato"), _q0 - _q1, _t1))
check("F2 «Tayyor» — 200 (ilgari 500 `'_ProratedItem' … 'unit_price'`); topshirilmagan B penoplasti AYNAN qaytdi (+0,20 blok — "
      "12 000 ÷ 600 000 × 10); A sarfi (0,04) qoldi",
      _r1.status_code == 200 and abs((_q2 - _q1) - 0.20) < EPS and abs((_q0 - _q2) - 0.04) < EPS,
      (_r1.status_code, _r1.text[:300], _q2 - _q1))
_s = SessionLocal()
_b = {it.name: (float(it.quantity or 0), float(it.total_price or 0)) for it in _s.query(OrderItem).filter(OrderItem.order_id == F1.get("id")).all()}
_ho = _s.query(Order).filter(Order.id == F1.get("id")).first()
_ho = (_ho.status.value if _ho is not None and _ho.status is not None else None)
_s.close()
check("F3 «Tayyor» dan keyin: B miqdori 0, jami 0; A o'sha (4 dona, 24 000); holat «Tayyor»",
      _b.get("K209 Dona B") == (0.0, 0.0) and _b.get("K209 Dona A") == (4.0, 24000.0) and _ho == "ready", (_b, _ho))

F2 = buyurtma([detal("K209 Dona C", "dona", 4, 6000), detal("K209 Dona D", "dona", 10, 12000)])
_q3 = qoldiq()
_t2 = topshir(F2.get("id"), ["K209 Dona C"])
_d2 = C.delete(f"/api/orders/{F2.get('id')}")
_q4 = qoldiq()
check("F4 o'chirish — 200 (ilgari 500), savatga (topshirilgani bor); qolgan D penoplasti AYNAN qaytdi (+0,20 blok)",
      _t2[0] == 200 and _d2.status_code == 200 and (_d2.json() or {}).get("soft_deleted") is True and abs((_q4 - _q3) - 0.20) < EPS,
      (_t2, _d2.status_code, _d2.text[:300], _q4 - _q3))
_tk = C.post(f"/api/orders/{F2.get('id')}/restore")
_q5 = qoldiq()
check("F5 tiklash — 200, AYNAN teskari (qolgan qism qayta yechildi: qoldiq o'chirishdan oldingidek)",
      _tk.status_code == 200 and abs(_q5 - _q3) < EPS, (_tk.status_code, _tk.text[:200], _q5 - _q3))
# qisman topshirilgan detalning O'ZI (ulush): G 10 dona × 12 000 → 0,20 m³, 4 tasi topshirildi — qolgan 6 ta (0,12 blok) qaytadi
F4 = buyurtma([detal("K209 Dona G", "dona", 10, 12000), detal("K209 Dona H", "dona", 2, 6000)])
_q8 = qoldiq()
_t4 = topshir(F4.get("id"), ["K209 Dona G"], ulush=0.4)
_t5 = topshir(F4.get("id"), ["K209 Dona H"])
_r4 = C.post(f"/api/orders/{F4.get('id')}/ready")
_q9 = qoldiq()
check("F7 detalning O'ZI qisman topshirilgan (10 dan 4 ta): «Tayyor» 200, qolgan 6 ta penoplasti AYNAN (+0,12 blok — narx ulushga "
      "ko'paytirilmaydi, miqdor ulushda)",
      _t4[0] == 200 and _t5[0] == 200 and _r4.status_code == 200 and abs((_q9 - _q8) - 0.12) < EPS, (_t4, _t5, _r4.status_code, _q9 - _q8))
# nazorat: o'lchamli «Donali» (eni 10 sm, qalinligi 5 sm, «metr ekvivalenti» 2 m → 10 × 5 / 2 × 2 / 10 000 = 0,005 m³) va panel
F3 = buyurtma([detal("K209 Dona E", "dona", 2, 9000, en=10, qal=5, uz=2), detal("K209 Panel F", "panel", 10, 15000, en=60, qal=5)])
_q6 = qoldiq()
_t3 = topshir(F3.get("id"), ["K209 Dona E"])
_r3 = C.post(f"/api/orders/{F3.get('id')}/ready")
_q7 = qoldiq()
check("F6 nazorat — o'lchamli «Donali» topshirilib, panel topshirilmay «Tayyor»: 200, panel hajmi (0,60 × 0,05 × 10 = 0,30 blok) qaytdi",
      _t3[0] == 200 and _r3.status_code == 200 and abs((_q7 - _q6) - 0.30) < EPS, (_t3, _r3.status_code, _q7 - _q6))

# «Blok» detali (review209 T4): 10 m chiqadi, 2 blok ishlatiladi (blok hajmi 1 m³ → 2 blok yechiladi); yarmi (5 m) topshirilsa — qolgan 1 blok
F5 = buyurtma([detal("K209 Blok P", "blok", 10, 20000, uz=2)])
_qa = qoldiq()
_tb = topshir(F5.get("id"), ["K209 Blok P"], ulush=0.5)
_rb = C.post(f"/api/orders/{F5.get('id')}/ready")
_qb = qoldiq()
check("F8 qisman topshirilgan «Blok» (10 m dan 5 m, 2 blok): «Tayyor» — qolgan ulush 1 blok qaytadi (ilgari HAMMA 2 blok qaytardi)",
      F5.get("id") and _tb[0] == 200 and _rb.status_code == 200 and abs((_qb - _qa) - 1.0) < EPS, (F5.get("_xato"), _tb, _rb.status_code, _qb - _qa))
F6 = buyurtma([detal("K209 Blok Q", "blok", 10, 20000, uz=2)])
_qc = qoldiq()
_tq = topshir(F6.get("id"), ["K209 Blok Q"], ulush=0.5)
_dq = C.delete(f"/api/orders/{F6.get('id')}")
_qd = qoldiq()
_rq = C.post(f"/api/orders/{F6.get('id')}/restore")
_qe = qoldiq()
check("F9 qisman topshirilgan «Blok» o'chirilsa — 1 blok qaytadi, tiklash AYNAN teskari",
      _tq[0] == 200 and _dq.status_code == 200 and abs((_qd - _qc) - 1.0) < EPS and _rq.status_code == 200 and abs(_qe - _qc) < EPS,
      (_tq, _dq.status_code, _qd - _qc, _rq.status_code, _qe - _qc))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J — o'chirish «Faoliyat jurnali» ga")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# J1: hech narsa topshirilmagan, 2 ta to'lov — BUTUNLAY o'chadi
J1 = buyurtma([detal("K209 Karniz J", "profil", 1, 25000, en=20, qal=10, uz=40), detal("K209 Panel J", "panel", 10, 15000, en=60, qal=5)])
_tp1 = [tolov(J1.get("id"), 100000, "zaklat"), tolov(J1.get("id"), 50000, "partial")]      # jami 175 000 — qarzdan oshmaydi
_s = SessionLocal()
_pids = [p.id for p in _s.query(Payment).filter(Payment.order_id == J1.get("id")).order_by(Payment.id).all()]
_s.close()
_dan = songi_id()
_dj1 = C.delete(f"/api/orders/{J1.get('id')}")
_y1 = yangi_yozuvlar(_dan)
_tol = [y for y in _y1 if y[0] == "deleted" and y[1] == "payment"]
_buy = [y for y in _y1 if y[0] == "deleted" and y[1] == "order"]
_s = SessionLocal()
_qoldi = _s.query(Payment).filter(Payment.id.in_(_pids)).count() if _pids else -1
_s.close()
check("J1 butunlay o'chirish (hech narsa topshirilmagan): 200, savatga TUSHMAYDI, to'lovlar bazadan o'chdi",
      _tp1 == [200, 200] and len(_pids) == 2 and _dj1.status_code == 200 and (_dj1.json() or {}).get("soft_deleted") is False
      and _qoldi == 0, (_tp1, _pids, _dj1.status_code, _dj1.text[:200], _qoldi))
check("J2 HAR o'chgan to'lov jurnalda (ilgari jim o'chardi): «Buyurtma <raqam>», summa, tur, usul, qabul qilgan, sana, "
      "«buyurtma bilan birga o'chirildi»",
      sorted(t[2] for t in _tol) == sorted(_pids)
      and all(t[3] == f"Buyurtma {J1.get('order_number')}" and "buyurtma bilan birga o'chirildi" in t[4] and "naqd" in t[4]
              and "qabul qilgan: K209 Kassir" in t[4] and "sana: " in t[4] for t in _tol)
      and any(t[4].startswith("100 000 so'm · zaklat") for t in _tol) and any(t[4].startswith("50 000 so'm · partial") for t in _tol),
      _tol)
_bm = _buy[0][4] if len(_buy) == 1 else ""
check("J3 buyurtma yozuvida NIMA o'chgani: jami, 2 ta detal (nomi — miqdor birlik), to'lovlar soni va summasi, «butunlay»",
      len(_buy) == 1 and _buy[0][2] == J1.get("id") and f"Jami: {J1.get('total_amount', 0):,.0f}".replace(",", " ") + " so'm, 2 ta detal" in _bm
      and "K209 Karniz J — 40 m" in _bm and "K209 Panel J — 10 m" in _bm
      and "to'lovlar: 2 ta, 150 000 so'm — buyurtma bilan birga o'chirildi" in _bm and "butunlay (savatga tushmaydi" in _bm, _buy)
check("J4 yozuvlar korxonaniki (company_id = 1) va kim o'chirgani yozilgan",
      _y1 and all(y[5] == 1 for y in _y1) and all(y[6] == "K209 Admin" for y in _tol + _buy), [(y[1], y[5], y[6]) for y in _y1])

J2 = buyurtma([detal("K209 Panel K", "panel", 5, 15000, en=60, qal=5)])
_dan = songi_id()
_dj2 = C.delete(f"/api/orders/{J2.get('id')}")
_y2 = yangi_yozuvlar(_dan)
check("J5 to'lovsiz butunlay o'chirish: buyurtma yozuvida «to'lov yo'q», to'lov yozuvi yo'q",
      _dj2.status_code == 200 and [y[1] for y in _y2] == ["order"] and "to'lov yo'q" in _y2[0][4] and "K209 Panel K — 5 m" in _y2[0][4], _y2)

# J3: topshirilgani bor — yumshoq (savatga), keyin savatdan butunlay
J3 = buyurtma([detal("K209 Panel L", "panel", 10, 15000, en=60, qal=5), detal("K209 Panel M", "panel", 4, 15000, en=60, qal=5)])
_tp3 = tolov(J3.get("id"), 50000)
_t33 = topshir(J3.get("id"), ["K209 Panel L"], ulush=0.5)
_dan = songi_id()
_dj3 = C.delete(f"/api/orders/{J3.get('id')}")
_y3 = yangi_yozuvlar(_dan)
_b3 = [y for y in _y3 if y[1] == "order" and y[0] == "deleted"]
check("J6 yumshoq o'chirish (yarmi topshirilgan — topshirilgan qismi bilan yakunlanadi): yozuvda YAKUNLASHDAN OLDINGI jami va detallar "
      "(210 000; L — 10 m, M — 4 m — mustaqil tekshiruv T1: ilgari «75 000», «M — 0 m»), «topshirilgan qismi bilan yakunlandi: 75 000», "
      "«O'chirilganlar» da — tiklash mumkin; to'lov o'chmaydi",
      _tp3 == 200 and _t33[0] == 200 and _dj3.status_code == 200 and (_dj3.json() or {}).get("soft_deleted") is True and len(_b3) == 1
      and _b3[0][4].startswith("Jami: 210 000 so'm, 2 ta detal (K209 Panel L — 10 m; K209 Panel M — 4 m)")
      and "· topshirilgan qismi bilan yakunlandi: 75 000 so'm · «O'chirilganlar» da — tiklash mumkin" in _b3[0][4]
      and not [y for y in _y3 if y[1] == "payment"], (_tp3, _t33, _dj3.status_code, _y3))
_dan = songi_id()
_dj3b = C.delete(f"/api/orders/{J3.get('id')}")
check("J6b savatdagi buyurtmani QAYTA o'chirish — 409 (mustaqil tekshiruv T5: ilgari 200 va jurnalga ikkinchi «o'chirildi»), yangi yozuv YO'Q",
      _dj3b.status_code == 409 and yangi_yozuvlar(_dan) == [], (_dj3b.status_code, _dj3b.text[:200], yangi_yozuvlar(_dan)))
_s = SessionLocal()
_p3 = [p.id for p in _s.query(Payment).filter(Payment.order_id == J3.get("id")).all()]
_s.close()
_dan = songi_id()
_pd = C.delete(f"/api/orders/{J3.get('id')}/permanent")
_y4 = yangi_yozuvlar(_dan)
_t4 = [y for y in _y4 if y[1] == "payment"]
_b4 = [y for y in _y4 if y[1] == "order"]
check("J7 savatdan BUTUNLAY o'chirish: buyurtma bilan birga o'chgan to'lov(lar) jurnalda («savatdan butunlay o'chirilgani bilan birga»), "
      "buyurtma yozuvida to'lovlar va «O'chirilganlar» dan butunlay",
      _pd.status_code == 200 and len(_p3) >= 1 and sorted(t[2] for t in _t4) == sorted(_p3)
      and all("savatdan butunlay o'chirilgani bilan birga" in t[4] and t[0] == "deleted" for t in _t4)
      and len(_b4) == 1 and _b4[0][0] == "permanently_deleted" and "«O'chirilganlar» dan butunlay o'chirildi" in _b4[0][4]
      and f"to'lovlar: {len(_p3)} ta" in _b4[0][4], (_pd.status_code, _p3, _y4))

# J4: yuk xatini o'chirish
J4 = buyurtma([detal("K209 Karniz N", "profil", 1, 25000, en=20, qal=10, uz=30), detal("K209 Panel O", "panel", 6, 15000, en=60, qal=5)])
_ty = topshir(J4.get("id"), ["K209 Karniz N"], ulush=0.5, qabul="Aziz K209", tashuvchi="K209 Tashuvchi", transport=80000)
_s = SessionLocal()
from models import Delivery as _Del    # noqa: E402
_dl = [(d.id, d.delivery_number) for d in _s.query(_Del).filter(_Del.order_id == J4.get("id")).all()]
_s.close()
_dan = songi_id()
_dd = C.delete(f"/api/deliveries/{_dl[0][0]}") if _dl else None
_y5 = yangi_yozuvlar(_dan)
check("J8 yuk xati o'chirildi — jurnalda (ilgari yozilmasdi): «Buyurtma <raqam> — yuk xati <raqam>», sana, kim topshirdi / qabul qildi, "
      "detal (nomi — miqdor birlik), transport",
      _ty[0] == 200 and _dd is not None and _dd.status_code == 200 and len(_y5) == 1 and _y5[0][0] == "deleted"
      and _y5[0][1] == "delivery" and _y5[0][2] == _dl[0][0]
      and _y5[0][3] == f"Buyurtma {J4.get('order_number')} — yuk xati {_dl[0][1]}" and "topshirilgan: " in _y5[0][4]
      and "qabul qildi: Aziz K209" in _y5[0][4] and "K209 Karniz N — 15 m" in _y5[0][4]
      and "transport: K209 Tashuvchi, 80 000 so'm" in _y5[0][4] and "to'lov:" not in _y5[0][4] and _y5[0][5] == 1,
      (_ty, _dl, _dd and _dd.status_code, _y5))
_ty2 = topshir(J4.get("id"), ["K209 Panel O"], tolov=30000)
_s = SessionLocal()
_dl2 = [d.id for d in _s.query(_Del).filter(_Del.order_id == J4.get("id")).all()]
_s.close()
_dan = songi_id()
_dd2 = C.delete(f"/api/deliveries/{_dl2[-1]}?tolov=ochir") if _dl2 else None
_y6 = yangi_yozuvlar(_dan)
check("J9 to'lovli yuk xati «to'lov ham o'chsin» bilan: to'lov yozuvi (avvalgidek) + yuk xati yozuvida «to'lov: 1 ta o'chirildi»",
      _ty2[0] == 200 and _dd2 is not None and _dd2.status_code == 200
      and [y[1] for y in _y6] == ["payment", "delivery"] and "to'lov: 1 ta o'chirildi" in _y6[1][4] and "K209 Panel O — 6 m" in _y6[1][4],
      (_ty2, _dd2 and _dd2.status_code, _y6))
_ty3 = topshir(J4.get("id"), ["K209 Panel O"], tolov=20000)
_s = SessionLocal()
_dl3 = [d.id for d in _s.query(_Del).filter(_Del.order_id == J4.get("id")).all()]
_s.close()
_dan = songi_id()
_dd3 = C.delete(f"/api/deliveries/{_dl3[-1]}?tolov=qoldir") if _dl3 else None
_y7 = yangi_yozuvlar(_dan)
check("J10 «to'lov qolsin» bilan: to'lov yangilangani (avvalgidek) + yuk xati yozuvida «to'lov: 1 ta buyurtmada saqlab qolindi»",
      _ty3[0] == 200 and _dd3 is not None and _dd3.status_code == 200
      and [(y[0], y[1]) for y in _y7] == [("updated", "payment"), ("deleted", "delivery")]
      and "to'lov: 1 ta buyurtmada saqlab qolindi" in _y7[1][4], (_ty3, _dd3 and _dd3.status_code, _y7))
_s = SessionLocal()                         # «Tayyor» F1 — yuk xati bor (A topshirilgan)
_dl4 = [d.id for d in _s.query(_Del).filter(_Del.order_id == F1.get("id")).all()]
_s.close()
_dan = songi_id()
_dd4 = C.delete(f"/api/deliveries/{_dl4[0]}") if _dl4 else None
_y8 = yangi_yozuvlar(_dan)
check("J11 rad etilgan o'chirish («Tayyor» buyurtmaning yuk xati — 400): jurnalda yuk xati yozuvi YO'Q, yuk xati joyida",
      _dd4 is not None and _dd4.status_code == 400 and not [y for y in _y8 if y[1] == "delivery"],
      (_dd4 and _dd4.status_code, _y8))

J5 = buyurtma([detal(f"K209 Bo'lak {i:02d}", "panel", 1, 15000, en=60, qal=5) for i in range(1, 15)])
_tk14 = topshir(J5.get("id"), [f"K209 Bo'lak {i:02d}" for i in range(1, 15)])
_s = SessionLocal()
_dl14 = [d.id for d in _s.query(_Del).filter(_Del.order_id == J5.get("id")).all()]
_s.close()
_dan = songi_id()
_dd14 = C.delete(f"/api/deliveries/{_dl14[0]}") if _dl14 else None
_y14 = yangi_yozuvlar(_dan)
_ym14 = _y14[0][4] if len(_y14) == 1 else ""
check("J13 14 detalli yuk xati o'chirilsa — yozuvda 12 tasi nomi bilan, «… yana 2 ta» (buyurtma yozuvi bilan bir chegara; mustaqil tekshiruv T2)",
      _tk14[0] == 200 and _dd14 is not None and _dd14.status_code == 200 and "K209 Bo'lak 12 — 1 m" in _ym14 and "K209 Bo'lak 13" not in _ym14
      and "… yana 2 ta" in _ym14, (_tk14, _dd14 and _dd14.status_code, _ym14[:400]))

# «Faoliyat jurnali» sahifasi
_lp = C.get("/logs")
_h = _lp.text if _lp.status_code == 200 else ""
check("J12 «Faoliyat jurnali» sahifasida: yuk xati yozuvi, buyurtma bilan birga o'chgan to'lov, buyurtma tafsiloti ko'rinadi",
      _lp.status_code == 200 and f"yuk xati {_dl[0][1] if _dl else '?'}" in _h
      and ("buyurtma bilan birga o&#39;chirildi" in _h or "buyurtma bilan birga o'chirildi" in _h)
      and "K209 Karniz J — 40 m" in _h, (_lp.status_code, len(_h)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K — Ustalar KPI: buyurtma va to'g'ridan-to'g'ri sotuv soni (egasi savoli 23.10)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from models import FinishedProduct, StockSource, ProductionStatus, OrderStatus    # noqa: E402
_s = SessionLocal()
US2 = Master(company_id=1, name="K209 Sotuvchi", phone="+998900002091", kpi_percent=3)
TM = FinishedProduct(company_id=1, name="K209 Karniz tayyor", category="profil", quantity=50.0, produced_quantity=50.0, unit="metr",
                     unit_price=12000, cost_price=5000, source=StockSource.PRODUCED, production_status=ProductionStatus.READY, is_coated=False)
_s.add_all([US2, TM])
_s.commit()
ID["US2"], ID["TM"] = US2.id, TM.id
_s.close()


def tm_sotish(usta, miqdor, narx):
    r = C.post("/api/finished/sell", json={"finished_product_id": ID["TM"], "quantity": miqdor, "unit_price": narx, "buyer_name": None,
                                          "payment_method": "naqd", "master_id": usta, "confirm_below_cost": True})
    return r.status_code


_ks = [tm_sotish(ID["US2"], 3, 12000), tm_sotish(ID["US2"], 2, 12500)]
_kr = C.get(f"/api/masters/kpi-report?year={TK.year}")
_rows = {r["name"]: r for r in ((_kr.json() or {}).get("masters") or [])} if _kr.status_code == 200 else {}
_k2, _k1 = _rows.get("K209 Sotuvchi") or {}, _rows.get("K209 Usta") or {}
_s = SessionLocal()
_tayyor_us = _s.query(Order).filter(Order.master_id == ID["US"], Order.status == OrderStatus.READY).count()
_s.close()
check("K1 KPI hisoboti: faqat to'g'ridan-to'g'ri sotuvli usta — «buyurtma» 0, «sotuv» 2, Sotuv = 3 × 12 000 + 2 × 12 500 = 61 000 (hisob "
      "o'zgarmagan); buyurtmali usta — «sotuv» 0, «buyurtma» = «Tayyor» buyurtmalar soni",
      _ks == [200, 200] and _k2.get("orders_count") == 0 and _k2.get("sales_count") == 2 and _k2.get("yearly_sales") == 61000
      and _k1.get("sales_count") == 0 and _k1.get("orders_count") == _tayyor_us and _tayyor_us >= 1,
      (_ks, _kr.status_code, _k2, _k1, _tayyor_us))
check("K2 shablon: «N ta buyurtma» va sotuv bo'lsa «· M ta sotuv» (ilgari faqat «N ta»)",
      "${m.orders_count} ta buyurtma${(m.sales_count || 0) > 0 ? ` · ${m.sales_count} ta sotuv` : ''}" in open(
          os.path.join(ROOT, "templates", "kpi.html"), encoding="utf-8").read())
_kpi_qator = {}
try:
    import re as _re
    import glob as _glob
    import socket as _socket
    import threading as _threading
    import time as _time
    import uvicorn as _uv
    from playwright.sync_api import sync_playwright as _spw
    _so = _socket.socket()
    _so.bind(("127.0.0.1", 0))
    _port = _so.getsockname()[1]
    _so.close()
    _srv = _uv.Server(_uv.Config(main.app, host="127.0.0.1", port=_port, log_level="critical", lifespan="off"))
    _threading.Thread(target=_srv.run, daemon=True).start()
    for _ in range(150):
        if _srv.started:
            break
        _time.sleep(0.1)
    with _spw() as _pw:
        _exe = None
        for _y in sorted(_glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*", "chrome-linux", "chrome"))):
            _exe = _y
        _br = _pw.chromium.launch(executable_path=_exe) if _exe else _pw.chromium.launch()
        _ctx = _br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
        _ctx.route(_re.compile(r"^https://.*"), lambda r: r.fulfill(status=204, body=""))
        _pg = _ctx.new_page()
        _pg.goto(f"http://127.0.0.1:{_port}/login")
        _pg.fill("input[name=username]", "k209_a")
        _pg.fill("input[name=password]", PAROL)
        _pg.press("input[name=password]", "Enter")
        _pg.wait_for_load_state("networkidle")
        _pg.goto(f"http://127.0.0.1:{_port}/kpi")
        _pg.wait_for_load_state("networkidle")
        _pg.wait_for_function("() => document.querySelectorAll('.mk-card').length >= 2", timeout=15000)
        _kpi_qator = _pg.evaluate("""() => Object.fromEntries([...document.querySelectorAll('.mk-card')].map(c => [
            (c.querySelector('.mk-name') || {}).innerText.trim().split('\\n')[0].trim(), (c.querySelector('.mk-meta') || {}).innerText.trim()]))""")
        _br.close()
    _srv.should_exit = True
except Exception as _e:                    # noqa: BLE001
    _kpi_qator = {"_xato": f"{type(_e).__name__}: {_e}"}
_m2 = next((v for k, v in _kpi_qator.items() if k.startswith("K209 Sotuvchi")), "")
_m1 = next((v for k, v in _kpi_qator.items() if k.startswith("K209 Usta")), "")
check("K3 HAQIQIY brauzer — «Ustalar KPI» qatori: sotuvchi usta «0 ta buyurtma · 2 ta sotuv», buyurtmali usta «N ta buyurtma» (sotuvsiz — "
      "«sotuv» so'zi yo'q)",
      "0 ta buyurtma · 2 ta sotuv" in _m2 and f"{_tayyor_us} ta buyurtma" in _m1 and "sotuv" not in _m1.split("Foyda")[-1],
      _kpi_qator)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
if PG_URL:
    try:
        from database import engine as _eng
        _eng.dispose()
        _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass
sys.exit(1 if FAIL else 0)
