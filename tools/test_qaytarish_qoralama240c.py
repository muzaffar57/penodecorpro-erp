#!/usr/bin/env python3
"""
test_qaytarish_qoralama240c.py — kech175 (zip 240c; review240 M2 izohi — «oddiy `POST /api/returns` qoralama buyurtmaga ham qaytarish
yozadi», ASL kodda ham bor).

NIMA UCHUN KERAK
  O'LCHANGAN (`work/k240c/probe240c.py`, asl kod = zip 240b): QORALAMA buyurtmadan «Ortiqcha» 5 m — 200, tayyor mahsulotlar omboriga +5 m
  (hech qachon ishlab chiqarilmagan mahsulot), hisob-kitobda kelishilgan summa 250 000 ga kamaydi; «Brak» — penoplast yechildi;
  `to_stock=false` ham yozildi; qoralama keyin jarayonga olinsa ham omborga qo'shilgan mahsulot QOLDI. BEKOR QILINGAN buyurtmada ham
  shunday. «Yangi qaytarish» / «Brak yozish» tanlovlari va komplekt qaytarish (zip 240) bunday buyurtmani bermaydi (404) — yozuvchi yo'l
  bermasligi kerak. O'chirilgan buyurtma qoidasi (topshirilgani qaytadi; topshirilmagani omborga — yo'q) ATAYLAB o'zgarmaydi.
BO'LIMLAR
  S — statik (tekshiruv hech narsa yozilishidan OLDIN). A — qoralama (API). B — bekor qilingan (API). C — crud to'g'ridan-to'g'ri (ikkinchi
  to'siq). D — o'zgarmagan holatlar (jarayonda, «Tayyor», yetkazilgan, o'chirilgan). E — korxona. F — 240c dan OLDIN yozilib qolgan
  (eski) qoralama / bekor qilingan buyurtma qaytarishi: hisob-kitob va brak taqdiri — rad (review240c M1), o'chirish — ochiq, hammasi
  orqaga. X — 5xx yo'q.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`. Asl kodga (zip 240b) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_qaytarish_qoralama240c.py
"""
import os
import io
import sys
import inspect
import tempfile
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qaytarish_qoralama240c_test"
_T = tempfile.mkdtemp(prefix="t240c_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't240c.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas                                 # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, ReturnItem, FinishedProduct, Order, OrderItem, OrderStatus, Project, Payment,   # noqa: E402
                    InventoryMovement, ActivityLog)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import event as _event             # noqa: E402
from sqlalchemy.orm import Session as _Session     # noqa: E402

FLUSH = [0]


@_event.listens_for(_Session, "after_flush")
def _flush_sanagich(session, ctx):
    """review240c L4: rad etilgan crud chaqiruvi bazaga hech narsa yubormaganini (flush ham) sinash uchun."""
    if session.new or session.dirty or session.deleted:
        FLUSH[0] += 1

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
XATO5 = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if callable(detail):
        try:
            detail = detail()
        except Exception as e:             # noqa: BLE001
            detail = f"{type(e).__name__}: {e}"
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
        x = r.json()
        return x if isinstance(x, (dict, list)) else {}
    except Exception:                      # noqa: BLE001
        return {}


def det(r):
    d = js(r)
    d = d.get("detail") if isinstance(d, dict) else d
    if isinstance(d, dict):
        d = d.get("message")
    return str(d)


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def xavfsiz(fn, std=None):
    try:
        return db_ishi(fn)
    except Exception:                      # noqa: BLE001
        return std


class _Xato:
    status_code = 599
    text = ""

    def __init__(self, e):
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    if r.status_code >= 500:
        XATO5.append((metod, url, r.status_code, str(getattr(r, "text", ""))[:200]))
    return r


main._send_telegram = lambda *a, **k: True
crud.PUL_TAKROR_SONIYA = 0
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T240C B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t240c_admin", PAROL, UserRole.ADMIN, "T240C Admin", company_id=1)
    auth.create_user(s, "t240c_b", PAROL, UserRole.ADMIN, "T240C B Admin", company_id=2)
PENO = {}
PRJ = {}
for _cid in (1, 2):
    _p = Inventory(company_id=_cid, item_name=f"T240C Peno {_cid}", unit="blok", stock_quantity=1000, price_per_unit=500_000,
                   volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
    s.add(_p)
    s.flush()
    PENO[_cid] = _p.id
    _pr = Project(company_id=_cid, client_name=f"T240C Mijoz {_cid}", project_name=f"T240C {_cid}", total_budget=0, total_paid=0)
    s.add(_pr)
    s.flush()
    PRJ[_cid] = _pr.id
s.commit()
s.close()
BRAK_SABAB = list(crud.BRAK_SABABLARI)[0]
if isinstance(BRAK_SABAB, (list, tuple)):
    BRAK_SABAB = BRAK_SABAB[0]


def kir(u):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": u, "password": PAROL}, follow_redirects=False)
    return c if r.status_code == 302 else None


CA, CB = kir("t240c_admin"), kir("t240c_b")
if CA is None or CB is None:
    print("LOGIN BO'LMADI")
    print("\nNATIJA: o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)
_n = [0]


def yarat(c=None, cid=1, draft=False, uzun=10):
    """Profil buyurtma (10 m × 50 000); (order_id, order_item_id)."""
    _n[0] += 1
    r = req(c or CA, "post", "/api/orders", params={"confirm_shortage": "true"}, json={
        "project_id": PRJ[cid], "order_type": "product", "loy_kg": 0, "is_draft": draft,
        "items": [{"name": f"T240C_{_n[0]}", "category": "profil", "width": 20, "thickness": 10, "length": uzun, "quantity": uzun,
                   "unit_price": 50_000, "is_coated": False, "penoplast_id": PENO[cid]}]})
    oid = js(r).get("id") if isinstance(js(r), dict) else None
    iid = xavfsiz(lambda s: (s.query(OrderItem.id).filter(OrderItem.order_id == oid).first() or [None])[0])
    return oid, iid


def tana(oid, iid, q, reason="Ortiqcha", **kw):
    t = {"order_id": oid, "order_item_id": iid, "item_name": "x", "quantity": q, "unit": "metr", "reason": reason, "to_stock": True}
    if reason == "Brak":
        t.update({"to_stock": False, "brak_sabab": BRAK_SABAB})
    t.update(kw)
    return t


def qayt(oid, iid, q, reason="Ortiqcha", c=None, headers=None, **kw):
    return req(c or CA, "post", "/api/returns", json=tana(oid, iid, q, reason, **kw), headers=headers or {})


def surat(oid=None, cid=1):
    """Hech narsa yozilmaganini solishtirish uchun: qaytarishlar, TM jami, penoplast, to'lovlar, ombor harakatlari, faoliyat jurnali."""
    def _f(s):
        qq = s.query(ReturnItem)
        if oid is not None:
            qq = qq.filter(ReturnItem.order_id == oid)
        o = s.get(Order, oid) if oid is not None else None
        return (qq.count(),
                round(sum(float(x.quantity or 0) for x in s.query(FinishedProduct).filter(FinishedProduct.company_id == cid).all()), 6),
                round(float(s.get(Inventory, PENO[cid]).stock_quantity or 0), 6),
                s.query(Payment).count(),
                s.query(InventoryMovement).count(),
                s.query(ActivityLog).count(),
                getattr(getattr(o, "status", None), "value", None))
    try:
        return db_ishi(_f)
    except Exception as e:                 # noqa: BLE001
        print("   surat xatosi:", type(e).__name__, str(e)[:200])
        return (None,) * 7


def holat_qoy(oid, st):
    db_ishi(lambda s: s.execute(Order.__table__.update().where(Order.__table__.c.id == oid).values(status=st.name)))


# ══════════════════════════════════════════════════════════════
section("S — statik: tekshiruv hech narsa yozilishidan OLDIN, marshrut — tanlov qoidasi")
_src = inspect.getsource(crud.create_return_item) if hasattr(crud, "create_return_item") else ""
_i_chk = _src.find("OrderStatus.DRAFT, OrderStatus.CANCELLED")
check("S1 crud.create_return_item: qoralama / bekor qilingan tekshiruvi bor",
      _i_chk > 0, _src[:200])
check("S2 tekshiruv buyurtma topilgandan KEYIN, sabab / detal / qulf / omborga yozishdan OLDIN",
      _i_chk > _src.find('raise ValueError("Buyurtma topilmadi")') > 0
      and all(_src.find(x) > _i_chk for x in ("ReturnReason(data.reason)", "_pul_qulfi(db, 101", "brak_taqdir_tana(", "ReturnItem(")),
      _i_chk)
_rsrc = inspect.getsource(main.api_create_return) if hasattr(main, "api_create_return") else ""
check("S3 POST /api/returns: qoralama / bekor qilingan — 404 (tanlov va komplekt marshrutlari bilan bir qoida), `_amal_bajar` dan OLDIN",
      0 < _rsrc.find("OrderStatus.DRAFT, OrderStatus.CANCELLED") < _rsrc.find("_amal_bajar("), _rsrc[:120])
_tsrc = inspect.getsource(main.api_tanlov_buyurtma_detallari) if hasattr(main, "api_tanlov_buyurtma_detallari") else ""
check("S4 tanlov detallari marshruti qoidasi o'zgarmagan (qoralama / bekor — yo'q, o'chirilgan — yo'q)",
      "_OS.DRAFT, _OS.CANCELLED" in _tsrc and "is_deleted.isnot(True)" in _tsrc)

# ══════════════════════════════════════════════════════════════
section("A — QORALAMA buyurtma (API)")
OD, ID_ = yarat(draft=True)
check("A0 qoralama yaratildi (holat draft, ombordan hech narsa yechilmadi)",
      OD and surat(OD)[6] == "draft" and surat(OD)[2] == 1000.0, surat(OD))
check("A0b tanlov detallari — 404 (oyna bunday buyurtmani bermaydi; o'zgarmagan)",
      req(CA, "get", f"/api/tanlov/buyurtmalar/{OD}/detallar").status_code == 404)
_s0 = surat(OD)
r = qayt(OD, ID_, 5)
check("A1 «Ortiqcha» 5 m (omborga) — 404 «Buyurtma topilmadi» (asl: 200, TM +5 m)", r.status_code == 404 and "topilmadi" in det(r),
      (r.status_code, r.text[:200]))
check("A1b hech narsa yozilmadi: qaytarish, TM, penoplast, to'lov, ombor harakati, jurnal — AYNAN", surat(OD) == _s0, (_s0, surat(OD)))
r = qayt(OD, ID_, 1, to_stock=False)
check("A2 «Ortiqcha» `to_stock=false` — 404, hech narsa yozilmadi", r.status_code == 404 and surat(OD) == _s0,
      (r.status_code, r.text[:200], surat(OD)))
r = qayt(OD, ID_, 2, "Brak")
check("A3 «Brak» 2 m — 404, penoplast yechilmadi (asl: −0,02 blok)", r.status_code == 404 and surat(OD) == _s0,
      (r.status_code, r.text[:200], surat(OD)))
_sabablar = [v.value for v in __import__("models").ReturnReason if v.value != "Brak"]
_bad = []
for _sb in _sabablar:
    r = qayt(OD, ID_, 1, _sb)
    if r.status_code != 404:
        _bad.append((_sb, r.status_code, r.text[:120]))
check("A4 brakdan boshqa HAMMA sabab (" + ", ".join(_sabablar) + ") — 404, hech narsa yozilmadi", not _bad and surat(OD) == _s0,
      (_bad, surat(OD)))
r = qayt(OD, ID_, 3, headers={"X-Amal-Kaliti": "t240c-qoralama-0001"})
r2 = qayt(OD, ID_, 3, headers={"X-Amal-Kaliti": "t240c-qoralama-0001"})
check("A5 `X-Amal-Kaliti` bilan (takror ham) — 404, hech narsa yozilmadi", r.status_code == 404 and r2.status_code == 404
      and surat(OD) == _s0, (r.status_code, r2.status_code, surat(OD)))
r = qayt(OD, ID_ + 100000 if ID_ else 1, 1)
check("A6 qoralama + begona / yo'q detal — baribir 404 (buyurtma qoidasi birinchi)", r.status_code == 404, (r.status_code, r.text[:160]))
r = req(CA, "post", f"/api/orders/{OD}/activate", params={"confirm_shortage": "true"})
check("A7 qoralama jarayonga olindi (200; xomashyo endi yechildi)", r.status_code == 200 and surat(OD)[6] == "in_progress"
      and surat(OD)[2] < 1000.0, (r.status_code, r.text[:160], surat(OD)))
_s7 = surat(OD)
r = qayt(OD, ID_, 4)
check("A8 jarayonga olingandan keyin «Ortiqcha» 4 m — 200 (oddiy qoida), TM +4 m", r.status_code == 200
      and surat(OD)[0] == _s7[0] + 1 and abs(surat(OD)[1] - _s7[1] - 4) < 1e-6, (r.status_code, r.text[:200], _s7, surat(OD)))
r = qayt(OD, ID_, 1, "Brak")
check("A9 jarayondagi buyurtmada «Brak» — 200 (oddiy qoida)", r.status_code == 200, (r.status_code, r.text[:200]))
# o'chirilgan QORALAMA — qoralama qoidasi (o'chirilgan qoidasi emas). review240c L2: oddiy qoralama butunlay o'chadi (404 — «yo'q»
# sababidan); eski qaytarish yozuvi bor qoralama esa YUMSHOQ o'chadi (qator qoladi, `is_deleted`) — shunisi sinaladi.
OD2, ID2 = yarat(draft=True)


def _eski_yozuv(oid, iid, q=1.0, sabab="Ortiqcha"):
    def _f(s):
        oi = s.get(OrderItem, iid)
        x = ReturnItem(company_id=s.get(Order, oid).company_id, order_id=oid, order_item_id=iid, item_name=oi.name, quantity=q,
                       unit="metr", reason=__import__("models").ReturnReason(sabab), refund_amount=0)
        s.add(x)
        s.flush()
        return x.id
    return xavfsiz(_f)


_eski_yozuv(OD2, ID2)
r = req(CA, "delete", f"/api/orders/{OD2}")
_od2 = xavfsiz(lambda s: (bool(s.get(Order, OD2).is_deleted), getattr(s.get(Order, OD2).status, "value", None)), (None, None))
_s2 = surat(OD2)
r = qayt(OD2, ID2, 2)
r2 = qayt(OD2, ID2, 1, "Brak")
check("A10 YUMSHOQ o'chirilgan QORALAMA (qator bor, is_deleted) — «Ortiqcha» va «Brak» 404, hech narsa yozilmadi",
      _od2 == (True, "draft") and r.status_code == 404 and r2.status_code == 404 and surat(OD2) == _s2,
      (_od2, r.status_code, r2.status_code, _s2, surat(OD2)))

# ══════════════════════════════════════════════════════════════
section("B — BEKOR QILINGAN buyurtma (API; holatni bazada qo'yamiz — eski ma'lumotda bo'lishi mumkin)")
OC, IC = yarat()
holat_qoy(OC, OrderStatus.CANCELLED)
_sc = surat(OC)
check("B0 holat «cancelled», tanlov detallari 404", _sc and _sc[6] == "cancelled"
      and req(CA, "get", f"/api/tanlov/buyurtmalar/{OC}/detallar").status_code == 404, _sc)
r = qayt(OC, IC, 3)
check("B1 «Ortiqcha» 3 m — 404, TM o'zgarmadi (asl: 200, TM +3 m)", r.status_code == 404 and surat(OC) == _sc,
      (r.status_code, r.text[:200], surat(OC)))
r = qayt(OC, IC, 1, "Brak")
check("B2 «Brak» 1 m — 404, penoplast yechilmadi", r.status_code == 404 and surat(OC) == _sc, (r.status_code, r.text[:200], surat(OC)))

# ══════════════════════════════════════════════════════════════
section("C — crud to'g'ridan-to'g'ri (ikkinchi to'siq: boshqa chaqiruvchi ham yoza olmasin)")


def crud_urin(oid, iid, q, reason="Ortiqcha", **kw):
    """(xato matni yoki None, sessiyada yozilishga tayyor narsa bormi). Sessiya commit qilinmaydi."""
    ss = SessionLocal()
    try:
        d = schemas.ReturnItemCreate(**{k: v for k, v in tana(oid, iid, q, reason, **kw).items() if v is not None})
        _f0 = FLUSH[0]
        try:
            crud.create_return_item(ss, d, company_id=1, performed_by="t240c")
            xato = None
        except ValueError as e:
            xato = str(e)
        nopok = bool(ss.new) or bool(ss.dirty) or bool(ss.deleted) or (xato is not None and FLUSH[0] != _f0)
        ss.rollback()
        return xato, nopok
    finally:
        ss.close()


OD3, ID3 = yarat(draft=True)
_s3 = surat(OD3)
_x, _np = crud_urin(OD3, ID3, 2)
check("C1 crud: qoralama «Ortiqcha» — ValueError «Qoralama yoki bekor qilingan buyurtmaga qaytarish / brak yozilmaydi …»",
      _x is not None and _x.startswith("Qoralama yoki bekor qilingan buyurtmaga qaytarish / brak yozilmaydi"), _x)
check("C2 crud: rad etilganda sessiyada hech narsa yo'q (yangi / o'zgargan obyekt yo'q, flush ham bo'lmadi), bazada ham", not _np and surat(OD3) == _s3,
      (_np, _s3, surat(OD3)))
_x, _np = crud_urin(OD3, ID3, 1, "Brak")
check("C3 crud: qoralama «Brak» — o'sha ValueError, sessiya toza", _x is not None and _x.startswith("Qoralama yoki bekor") and not _np,
      (_x, _np))
holat_qoy(OD3, OrderStatus.CANCELLED)
_x, _np = crud_urin(OD3, ID3, 1)
check("C4 crud: bekor qilingan — o'sha ValueError, sessiya toza", _x is not None and _x.startswith("Qoralama yoki bekor") and not _np,
      (_x, _np))
holat_qoy(OD3, OrderStatus.IN_PROGRESS)
_x, _np = crud_urin(OD3, ID3, 1)
check("C5 crud: o'sha buyurtma jarayonda — yoziladi (xato yo'q)", _x is None, _x)
if hasattr(crud, "create_komplekt_return"):
    holat_qoy(OD3, OrderStatus.DRAFT)

    def _k(s):
        try:
            crud.create_komplekt_return(s, OD3, 1, 1, company_id=1)
            return None
        except ValueError as e:
            return str(e)
    _kx = xavfsiz(_k)
    check("C6 komplekt qaytarish (zip 240) qoidasi o'zgarmagan — qoralama ValueError", _kx and "Qoralama" in _kx, _kx)

# ══════════════════════════════════════════════════════════════
section("D — o'zgarmagan holatlar")
ON, IN = yarat()
_sn = surat(ON)
r = qayt(ON, IN, 2)
r2 = qayt(ON, IN, 1, "Brak")
check("D1 jarayondagi buyurtma: «Ortiqcha» 2 m (TM +2) va «Brak» 1 m (penoplast −) — 200",
      r.status_code == 200 and r2.status_code == 200 and abs(surat(ON)[1] - _sn[1] - 2) < 1e-6 and surat(ON)[2] < _sn[2],
      (r.status_code, r2.status_code, _sn, surat(ON)))
OR_, IR = yarat()
r = req(CA, "post", f"/api/orders/{OR_}/ready", json={})
r2 = qayt(OR_, IR, 3)
check("D2 «Tayyor» buyurtma: «Ortiqcha» 3 m — 200", r.status_code == 200 and r2.status_code == 200, (r.status_code, r2.status_code,
                                                                                                       r2.text[:160]))
OY, IY = yarat()
r = req(CA, "post", "/api/deliveries", json={"order_id": OY, "items": [{"order_item_id": IY, "quantity": 10}], "notes": "t240c-d3",
                                             "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
_sy = surat(OY)
r2 = qayt(OY, IY, 4)
check("D3 to'liq yetkazilgan buyurtma: «Ortiqcha» 4 m — 200, TM +4", r.status_code == 200 and r2.status_code == 200
      and surat(OY)[6] == "delivered" and abs(surat(OY)[1] - _sy[1] - 4) < 1e-6, (r.status_code, r2.status_code, _sy, surat(OY)))
OO, IO = yarat()
req(CA, "post", "/api/deliveries", json={"order_id": OO, "items": [{"order_item_id": IO, "quantity": 4}], "notes": "t240c-d4",
                                         "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
r = req(CA, "delete", f"/api/orders/{OO}")
_so = surat(OO)
r2 = qayt(OO, IO, 3)
r3 = qayt(OO, IO, 1, "Brak")
check("D4 O'CHIRILGAN (jarayondan) buyurtma — o'z qoidasi ATAYLAB o'zgarmagan: topshirilgan qismdan «Ortiqcha» 3 m va «Brak» — 200",
      r.status_code == 200 and r2.status_code == 200 and r3.status_code == 200 and surat(OO)[0] == _so[0] + 2,
      (r.status_code, r2.status_code, r2.text[:160], r3.status_code, r3.text[:160]))
r4 = qayt(OO, IO, 3)
check("D4b o'chirilgan: topshirilganidan ortig'i — 400 (o'z sababi bilan, 404 EMAS)", r4.status_code == 400, (r4.status_code, r4.text[:200]))
# ══════════════════════════════════════════════════════════════
section("E — korxona")
OBD, IBD = yarat(c=CB, cid=2, draft=True)
_sb2 = surat(OBD, cid=2)
r = qayt(OBD, IBD, 1, c=CB)
check("E1 B korxona o'z qoralamasiga — 404, hech narsa yozilmadi", r.status_code == 404 and surat(OBD, cid=2) == _sb2,
      (r.status_code, r.text[:160]))
OBN, IBN = yarat(c=CB, cid=2)
r = qayt(OBN, IBN, 1, c=CA)
check("E2 A korxona B ning jarayondagi buyurtmasiga — 404 (o'zgarmagan)", r.status_code == 404, (r.status_code, r.text[:160]))
r = qayt(OBN, IBN, 1, c=CB)
check("E3 B korxona o'z jarayondagi buyurtmasiga — 200", r.status_code == 200, (r.status_code, r.text[:160]))

# ══════════════════════════════════════════════════════════════
section("F — 240c dan OLDIN yozilib qolgan (eski) qaytarishlar: hisob-kitob / taqdir — rad, o'chirish — ochiq (review240c M1, L3)")
# Haqiqiy eski yozuv: jarayondagi buyurtmaga oddiy yo'l bilan «Ortiqcha» 3 m (TM +3, summa) va «Brak» 1 m (penoplast −) yoziladi, keyin
# holat bazada QORALAMA / BEKOR qilinadi — eski kod qoralamaga yozgan yozuv bilan bir xil bog'lamlar (TM, xomashyo, summa).


def kelishilgan(oid):
    return xavfsiz(lambda s: round(float(s.get(Order, oid).kelishilgan_summa or 0), 2))


def eski_qatorlar(st):
    o, i = yarat()
    r1 = qayt(o, i, 3)
    r2 = qayt(o, i, 1, "Brak")
    holat_qoy(o, st)
    return o, i, js(r1).get("id"), js(r2).get("id"), r1.status_code, r2.status_code


_sp0 = surat()
OF, IF_, RO, RB, c1, c2 = eski_qatorlar(OrderStatus.DRAFT)
check("F0 eski yozuvlar tayyor (jarayonda yozildi: «Ortiqcha» 3 m TM +3, «Brak» 1 m; keyin holat — draft)",
      c1 == 200 and c2 == 200 and RO and RB and surat(OF)[6] == "draft" and abs(surat()[1] - _sp0[1] - 3) < 1e-6,
      (c1, c2, RO, RB, surat(OF)))
_sf, _kf = surat(OF), kelishilgan(OF)
r = req(CA, "post", f"/api/returns/{RO}/refund", params={"payment_method": "naqd"})
check("F1 eski qoralama qaytarishi «💰 Hisob-kitob» — 400 «… hisob-kitob qilinmaydi — bu yozuvni o'chiring», kelishilgan summa, to'lov, "
      "hammasi AYNAN (asl: 200, kelishilgan −150 000)",
      r.status_code == 400 and "hisob-kitob qilinmaydi" in det(r) and "o'chiring" in det(r) and kelishilgan(OF) == _kf
      and surat(OF) == _sf and not xavfsiz(lambda s: s.get(ReturnItem, RO).is_refunded, True),
      (r.status_code, r.text[:200], _kf, kelishilgan(OF), _sf, surat(OF)))
r = req(CA, "post", f"/api/returns/{RO}/refund", params={"payment_method": "naqd", "komplekt": "1"})
check("F1b `?komplekt=1` yo'li ham — 400, hech narsa o'zgarmadi", r.status_code == 400 and kelishilgan(OF) == _kf and surat(OF) == _sf,
      (r.status_code, r.text[:200]))
r = req(CA, "post", f"/api/returns/{RB}/taqdir", json={"taqdir": "tuzatildi", "joy": "omborga", "materiallar": []})
check("F2 eski qoralama brakiga taqdir «Tuzatildi → Omborga» — 400 «… taqdir belgilanmaydi», TM qo'shilmadi (asl: 200, TM +1 m)",
      r.status_code == 400 and "taqdir belgilanmaydi" in det(r) and surat(OF) == _sf, (r.status_code, r.text[:200], _sf, surat(OF)))
r = req(CA, "delete", f"/api/returns/{RO}")
_sd = surat(OF)
check("F3 eski «Ortiqcha» yozuvini o'chirish — 200, omborga qo'shilgan 3 m qaytib ketdi (tozalash yo'li ochiq)",
      r.status_code == 200 and _sd[0] == _sf[0] - 1 and abs(_sf[1] - _sd[1] - 3) < 1e-6, (r.status_code, r.text[:200], _sf, _sd))
r = req(CA, "delete", f"/api/returns/{RB}")
check("F4 eski «Brak» yozuvini o'chirish — 200, penoplast qaytdi", r.status_code == 200 and surat(OF)[0] == _sd[0] - 1
      and surat(OF)[2] > _sd[2], (r.status_code, r.text[:200], _sd, surat(OF)))
OFC, IFC, ROC, RBC, c1, c2 = eski_qatorlar(OrderStatus.CANCELLED)
_sc2, _kc2 = surat(OFC), kelishilgan(OFC)
r = req(CA, "post", f"/api/returns/{ROC}/refund", params={"payment_method": "naqd"})
r2 = req(CA, "post", f"/api/returns/{RBC}/taqdir", json={"taqdir": "tuzatildi", "joy": "omborga", "materiallar": []})
check("F5 bekor qilingan buyurtmadagi eski yozuvlar: hisob-kitob va taqdir — 400, hech narsa o'zgarmadi",
      r.status_code == 400 and r2.status_code == 400 and kelishilgan(OFC) == _kc2 and surat(OFC) == _sc2,
      (r.status_code, r2.status_code, r2.text[:160]))
holat_qoy(OFC, OrderStatus.IN_PROGRESS)
r = req(CA, "post", f"/api/returns/{ROC}/refund", params={"payment_method": "naqd"})
r2 = req(CA, "post", f"/api/returns/{RBC}/taqdir", json={"taqdir": "tuzatildi", "joy": "omborga", "materiallar": []})
check("F6 o'sha yozuvlar buyurtma jarayonda bo'lsa — hisob-kitob 200 (kelishilgan kamaydi), taqdir 200 (oddiy qoida o'zgarmagan)",
      r.status_code == 200 and r2.status_code == 200 and kelishilgan(OFC) < _kc2, (r.status_code, r.text[:160], r2.status_code,
                                                                                   r2.text[:160]))

section("X — 5xx")
check("X1 hech bir so'rov 5xx bermadi", not XATO5, XATO5[:5])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:\n  " + "\n  ".join(FAILED))
sys.exit(1 if FAIL else 0)
