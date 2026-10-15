#!/usr/bin/env python3
"""
test_tm_minus182.py — kech145 (zip 182, N5): MINUSDAGI TAYYOR MAHSULOT — EGASI QARORLARI 14.10 05:3x (QAYTA SO'RALMAYDI):
«Avtomatik yopilsin» (shu mahsulotning bo'sh qoldig'i paydo bo'lishi bilan minus yopiladi), «ushlansin» (minus bor guruhda bo'sh qoldiq
sotilmaydi), «Darhol xabar» (minusga tushganda Telegram), «Faqat bor» (yuk xatida jismonan bor miqdordan ko'p emas).

NIMA UCHUN KERAK (O'LCHANGAN — staging 14.10 05:0x, FP 83 −5 m; agent hisoboti `work/k182_tayyorgarlik/agent_minus/HISOBOT.md`):
  minus partiya o'chirilsa buyurtma qarzi JIM yo'qolardi; 90 kundan eski minus partiya ro'yxatdan tushardi; boshqa partiyada bo'sh qoldiq
  bo'lsa ham minus turaverardi (ogohlantirish «yetmaydi» derdi); «Yana ishlab chiqarish» minusdan keyin tannarxni oshirardi (−5 + 5 = 0 m
  qatorda tannarx qolardi); brak bekor qilinganda minusdagi qatorga tannarx qo'shilardi; qiymat «-100 000», foyda oynasi «FOYDA -100 000»;
  yuk xati minusdagi (hali ishlab chiqarilmagan) miqdorni ham topshirardi; Telegram xabari yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (P — parallel, faqat PG); `TENANT_FILTER=1`.
Asl kodga (zip 181) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_tm_minus182.py
"""
import os
import io
import sys
import json
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta, timezone

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tm_minus182_test"
_T = tempfile.mkdtemp(prefix="tm182_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tm182.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Inventory, FinishedProduct, Order, StockSource, ProductionStatus,   # noqa: E402
                    ActivityLog)
from production_models import ProductionOrder      # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
XABARLAR = []


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


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def det(r):
    d = js(r)
    return d.get("detail") if isinstance(d, dict) else None


def det_matn(r):
    d = det(r)
    if isinstance(d, dict):
        return str(d.get("message") or "") + " | " + " | ".join(str(x) for x in (d.get("shortages") or []))
    return str(d or "")


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


# Telegram — yozib olinadi (haqiqiy so'rov yo'q)
def _tg_yozuvchi(text, company_id=None):
    XABARLAR.append(str(text))
    return True


main._send_telegram = _tg_yozuvchi

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "tm182_admin", PAROL, UserRole.ADMIN, "TM182 Admin", company_id=1)
PRJ = Project(company_id=1, client_name="TM182 Mijoz", project_name="TM182 loyiha", total_budget=0, total_paid=0)
# P bo'limi: ikkinchi loyiha — bir loyihaning buyurtmalari `pg_advisory_xact_lock(loyiha)` bilan ketma-ket (parallellik bo'lmasdi)
PRJ2 = Project(company_id=1, client_name="TM182 Mijoz 2", project_name="TM182 loyiha 2", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="TM182 PENO", unit="blok", stock_quantity=100000, min_stock=0, is_penoplast=True,
                 volume_per_unit=1, price_per_unit=500000, category="Penoplast")
s.add_all([PRJ, PRJ2, PENO])
s.commit()
PRJ_ID, PENO_ID, PRJ2_ID = PRJ.id, PENO.id, PRJ2.id
s.close()


def mijoz():
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    assert c.post("/login", data={"username": "tm182_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)
    return c


A = mijoz()
_n = {"d": 0}


def yangi_tm(miqdor, nom, band=0.0, holat=ProductionStatus.READY, narx=0.0, kun_oldin=0, manba=StockSource.PRODUCED,
             qoplama=False, eni=20, birlik=1000):
    def f(s):
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=qoplama, width=eni, thickness=10,
                             quantity=miqdor, produced_quantity=max(miqdor, 0), unit="metr", unit_price=narx,
                             cost_price=max(miqdor, 0) * birlik, unit_cost_stable=birlik, source=manba, penoplast_id=PENO_ID,
                             unit_volume_m3=0.01, volume_m3=0.01 * max(miqdor, 0), production_status=holat, reserved_quantity=band)
        if kun_oldin:
            fp.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=kun_oldin)
        s.add(fp)
        s.flush()
        return fp.id
    return db_ishi(f)


def detal(uz, fid, nom="TM182 detal"):
    _n["d"] += 1                           # 8 s «takroriy yuborish» imzosi (nom, tur, soni) — har detal nomi noyob
    return {"name": f"{nom} {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": uz, "quantity": 1,
            "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID, "finished_product_id": fid}


def tana(*d, qoralama=False, prj=None):
    t = {"project_id": prj or PRJ_ID, "order_type": "product", "loy_kg": 0, "items": list(d)}
    if qoralama:
        t["is_draft"] = True
    return t


def buyurtma(*d, tasdiq=False, qoralama=False, c=None):
    return (c or A).post("/api/orders" + ("?confirm_shortage=true" if tasdiq else ""), json=tana(*d, qoralama=qoralama))


def tm(fid):
    def f(s):
        x = s.get(FinishedProduct, fid)
        if x is None:
            return None
        return (round(float(x.quantity), 3), round(float(x.cost_price or 0), 2), round(float(x.reserved_quantity or 0), 3))
    return db_ishi(f)


def tahrir(oid, fid, uz, tasdiq=False):
    o = js(A.get(f"/api/orders/{oid}"))
    it = (o.get("items") or [{}])[0]
    t = tana(dict(detal(uz, fid), id=it.get("id"), name=it.get("name")))
    t["notes"] = o.get("notes")
    return A.put(f"/api/orders/{oid}" + ("?confirm_shortage=true" if tasdiq else ""), json=t)


def detal_id(oid):
    return ((js(A.get(f"/api/orders/{oid}")).get("items") or [{}])[0]).get("id")


def holat(oid):
    def f(s):
        o = s.get(Order, oid)
        return getattr(o.status, "value", o.status) if o else None
    return db_ishi(f)


def jurnal(amal, fid):
    return db_ishi(lambda s: s.query(ActivityLog).filter(ActivityLog.action == amal, ActivityLog.entity_id == fid).count())


def ruyxat():
    return {x["id"]: x for x in (js(A.get("/api/finished")) or [])}


def yangi_xabarlar(n0):
    return XABARLAR[n0:]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Guruh kaliti — finished.html guruhi bilan bir mahsulot")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_k1, _k2 = yangi_tm(1, "TM182 Kalit  Karniz"), yangi_tm(1, "tm182 kalit karniz")
_k3, _k4 = yangi_tm(1, "TM182 Kalit Karniz", qoplama=True), yangi_tm(1, "TM182 Kalit Karniz", manba=StockSource.RETURNED)
_k5 = yangi_tm(1, "TM182 Kalit Karniz", eni=25)
_kf = getattr(crud, "tm_guruh_kaliti", None)          # asl kodda yo'q — tekshiruv yiqiladi, sinov qulamaydi
_kal = db_ishi(lambda s: {i: _kf(s.get(FinishedProduct, i)) for i in (_k1, _k2, _k3, _k4, _k5)}) if _kf else {}
check("K1 nom harfi / bo'shliqlari farq qilsa ham — bir guruh", _kf and _kal[_k1] == _kal[_k2], _kal)
check("K2 qoplama, manba (qaytgan), eni boshqa — boshqa guruh",
      _kf and len({_kal[_k1], _kal[_k3], _kal[_k4], _kal[_k5]}) == 4, _kal)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. «Avtomatik yopilsin» — yangi partiya tayyor bo'lganda minus yopiladi (egasi qarori)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FA = yangi_tm(10, "TM182 A Karniz")
_x0 = len(XABARLAR)
ra = buyurtma(detal(15, FA), tasdiq=True)
OA = js(ra).get("id")
check("A1 10 m dan 15 m (tasdiq) — 200, qoldiq −5, tannarx 0", ra.status_code == 200 and tm(FA) == (-5.0, 0.0, 0.0), (ra.status_code, tm(FA)))
_xa = yangi_xabarlar(_x0)
check("A2 Telegram — BITTA xabar: «minusda», mahsulot nomi, «-5», buyurtma raqami (egasi qarori «Darhol xabar»)",
      len(_xa) == 1 and "minusda" in _xa[0] and "TM182 A Karniz" in _xa[0] and "-5" in _xa[0]
      and (js(ra).get("order_number") or "?") in _xa[0], _xa)
rp = A.post("/api/finished/produce", json={"name": "TM182 A Karniz", "category": "profil", "width": 20, "thickness": 10, "length": 20,
                                           "is_coated": False, "penoplast_id": PENO_ID, "unit_price": 0})
FB = js(rp).get("product_id")
check("A3 «+ Penoplast detal» (shu mahsulot, 20 m) — jarayonda: minus HALI yopilmaydi (tayyor emas)",
      rp.status_code == 200 and FB and tm(FA) == (-5.0, 0.0, 0.0) and tm(FB)[0] == 20.0, (rp.status_code, js(rp), tm(FA), tm(FB)))
_b_tannarx = tm(FB)[1]
rc = A.post(f"/api/finished/{FB}/complete")
check("A4 «Sotuvga tayyor» — minus yopildi: A 0, B 15 (5 m minusga ko'chdi), javobda `minus_yopildi`",
      rc.status_code == 200 and tm(FA)[0] == 0.0 and tm(FB)[0] == 15.0 and js(rc).get("minus_yopildi"), (rc.status_code, js(rc), tm(FA), tm(FB)))
check("A5 tannarx: B dan 5 m ulushi chiqdi (B = 20 m tannarxining 15/20), A da 0 (minusni yopgan qism buyurtmaga ketgan)",
      abs(tm(FB)[1] - round(_b_tannarx * 15 / 20, 2)) <= 0.02 and tm(FA)[1] == 0.0, (_b_tannarx, tm(FA), tm(FB)))
check("A6 «Faoliyat jurnali» — `tm_minus_yopildi` (A partiyasi)", jurnal("tm_minus_yopildi", FA) == 1, jurnal("tm_minus_yopildi", FA))
A.delete(f"/api/orders/{OA}")
check("A7 buyurtma o'chirildi — 15 m A ga qaytdi (A 15, B 15 — jami 30 = 10 + 20), A tannarxi 15 × 1 000",
      tm(FA) == (15.0, 15000.0, 0.0) and tm(FB)[0] == 15.0, (tm(FA), tm(FB)))
check("A8 «Tayyor mahsulot minusi yopildi» amali jurnal nomlarida (`crud.AUDIT_AMALLARI`)",
      "tm_minus_yopildi" in crud.AUDIT_AMALLARI)


def _detal_birlik(oid):
    from models import OrderItem as _OI
    return db_ishi(lambda s: [round(float(x.fp_unit_cost or 0), 4) for x in s.query(_OI).filter(_OI.order_id == oid).order_by(_OI.id)])


def _guruh_qiymat(*ids):
    return round(sum(tm(i)[1] for i in ids), 2)


# tekshiruv 2-bosqich P1-2: guruhdoshdan ko'chgan qism — donor tannarxida (detal birligi), o'chirilganda tannarx saqlanadi
FG1, FG2 = yangi_tm(10, "TM182 G Karniz", birlik=1000), yangi_tm(20, "TM182 G Karniz", birlik=1500)
rg = buyurtma(detal(15, FG1))
OG = js(rg).get("id")
_bg = _detal_birlik(OG)
check("A9 G1 10 × 1 000 + G2 20 × 1 500: G1 dan 15 m — 5 m G2 dan ko'chdi; detal birligi (10 × 1 000 + 5 × 1 500) / 15 = 1 166,67",
      rg.status_code == 200 and (tm(FG1)[0], tm(FG2)[0]) == (0.0, 15.0) and _bg and abs(_bg[0] - 17500 / 15) < 0.01,
      (rg.status_code, tm(FG1), tm(FG2), _bg))
A.delete(f"/api/orders/{OG}")
check("A10 buyurtma o'chirildi — guruh tannarxi 40 000 AYNAN (ilgari 37 500 — 2 500 yo'qolardi), G1 15 m / 17 500",
      _guruh_qiymat(FG1, FG2) == 40000.0 and tm(FG1)[:2] == (15.0, 17500.0), (tm(FG1), tm(FG2)))
FJ1, FJ2 = yangi_tm(10, "TM182 J Karniz", birlik=1000), yangi_tm(20, "TM182 J Karniz", birlik=1500)
OJ = js(buyurtma(detal(5, FJ1))).get("id")
rj = tahrir(OJ, FJ1, 15)
_bj = _detal_birlik(OJ)
check("A11 tahrir 5 → 15 m (J1 10 × 1 000): 5 m J2 (1 500) dan ko'chdi — detal birligi 1 166,67; o'chirilganda guruh 40 000",
      rj.status_code == 200 and _bj and abs(_bj[0] - 17500 / 15) < 0.01, (rj.status_code, det_matn(rj), tm(FJ1), tm(FJ2), _bj))
A.delete(f"/api/orders/{OJ}")
check("A12 tahrirlangan buyurtma o'chirildi — guruh tannarxi 40 000 AYNAN", _guruh_qiymat(FJ1, FJ2) == 40000.0, (tm(FJ1), tm(FJ2)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Buyurtma — shu mahsulotning boshqa partiyasidagi bo'sh qoldiq ham hisobga olinadi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FS1, FS2 = yangi_tm(10, "TM182 S Karniz"), yangi_tm(20, "TM182 S Karniz")
_x0 = len(XABARLAR)
rs = buyurtma(detal(15, FS1))
check("S1 S1 10 m + S2 20 m, S1 dan 15 m TASDIQSIZ — 200 (ilgari 409 «yetmaydi»), S1 0, S2 15 (5 m ko'chdi), minus yo'q",
      rs.status_code == 200 and tm(FS1)[0] == 0.0 and tm(FS2)[0] == 15.0, (rs.status_code, det_matn(rs), tm(FS1), tm(FS2)))
check("S2 tannarx: S2 20 000 − 5 × 1 000 = 15 000, S1 0; Telegram xabari yo'q (minus yo'q)",
      tm(FS2)[1] == 15000.0 and tm(FS1)[1] == 0.0 and not yangi_xabarlar(_x0), (tm(FS1), tm(FS2), yangi_xabarlar(_x0)))
rs2 = buyurtma(detal(40, FS1))
check("S3 guruhda 15 m, 40 m tasdiqsiz — 409, izoh «boshqa partiyalaridan yana 15 metr olinadi — yetmagani 25 metr»",
      rs2.status_code == 409 and "omborda 0 metr, kerak 40 metr" in det_matn(rs2)
      and "boshqa partiyalaridan yana 15 metr olinadi — yetmagani 25 metr" in det_matn(rs2), (rs2.status_code, det_matn(rs2)))
rs3 = buyurtma(detal(40, FS1), tasdiq=True)
OS3 = js(rs3).get("id")
check("S4 tasdiq bilan — S1 −25 (15 m S2 dan yopildi), S2 0", rs3.status_code == 200 and tm(FS1)[0] == -25.0 and tm(FS2)[0] == 0.0,
      (rs3.status_code, tm(FS1), tm(FS2)))
FB1, FB2 = yangi_tm(10, "TM182 B Karniz", band=8), yangi_tm(20, "TM182 B Karniz")
rb = buyurtma(detal(5, FB1))
check("S5 band: B1 10 (band 8, bo'sh 2) + B2 20, B1 dan 5 m — 200 (guruhda bo'sh 22); B1 8 = band, B2 17 (band to'ldirildi)",
      rb.status_code == 200 and tm(FB1) == (8.0, tm(FB1)[1], 8.0) and tm(FB2)[0] == 17.0, (rb.status_code, det_matn(rb), tm(FB1), tm(FB2)))
FX1, FX2 = yangi_tm(10, "TM182 X Karniz", band=10), yangi_tm(10, "TM182 X Karniz")
rx = buyurtma(detal(15, FX2), tasdiq=True)
check("S7 guruhdoshning BAND qismi minusni yopmaydi: X1 10 (hammasi band) + X2 10, X2 dan 15 m — X2 −5, X1 10 / band 10 o'zgarmadi",
      rx.status_code == 200 and tm(FX2)[0] == -5.0 and tm(FX1) == (10.0, 10000.0, 10.0), (rx.status_code, tm(FX1), tm(FX2)))
FZ1, FZ2 = yangi_tm(10, "TM182 Z Karniz"), yangi_tm(0, "TM182 Z Karniz")
OZ1 = js(buyurtma(detal(10, FZ1))).get("id")
buyurtma(detal(5, FZ2), tasdiq=True)
_z0 = (tm(FZ1)[0], tm(FZ2)[0])
rz = tahrir(OZ1, FZ1, 4)
check("S8 tahrirda qaytgan qoldiq guruhdagi minusni yopadi: Z1 0 / Z2 −5 → Z1 dan buyurtma 10 → 4 m: Z1 1, Z2 0",
      _z0 == (0.0, -5.0) and rz.status_code == 200 and tm(FZ1)[0] == 1.0 and tm(FZ2)[0] == 0.0, (_z0, rz.status_code, det_matn(rz), tm(FZ1), tm(FZ2)))
FW1, FW2, FW3 = yangi_tm(-5, "TM182 W Karniz"), yangi_tm(5, "TM182 W Karniz"), yangi_tm(0, "TM182 W Karniz")   # majburan (eski holat)
rw = buyurtma(detal(5, FW3))
check("S9 eski minus (W1 −5) + bo'sh (W2 5): W3 dan 5 m TASDIQSIZ — 409 (bo'sh qoldiq avval eski qarzni yopadi), hech narsa o'zgarmadi",
      rw.status_code == 409 and tm(FW1)[0] == -5.0 and tm(FW2)[0] == 5.0 and tm(FW3)[0] == 0.0, (rw.status_code, det_matn(rw), tm(FW1), tm(FW2), tm(FW3)))
import schemas                                     # noqa: E402
_tw = schemas.OrderCreate(**tana(detal(5, FW3)))
_ogw = db_ishi(lambda s: crud.taklif_ogohlantirishlari(s, 1, _tw))
check("S13 taklif (omborga tegmaydi): W3 dan 5 m — «yetmaydi» ogohlantirishi (guruhdagi bo'sh 5 m avval W1 qarzini yopadi), "
      "hech narsa o'zgarmadi", any("TM182 W Karniz" in str(x) for x in (_ogw or []))
      and (tm(FW1)[0], tm(FW2)[0], tm(FW3)[0]) == (-5.0, 5.0, 0.0), (_ogw, tm(FW1), tm(FW2), tm(FW3)))
_x0 = len(XABARLAR)
rw2 = buyurtma(detal(5, FW3), tasdiq=True)
check("S10 tasdiq bilan — avval W1 qarzi yopildi (W1 0, W2 0), W3 −5; Telegram xabari BITTA (W3 −5)",
      rw2.status_code == 200 and (tm(FW1)[0], tm(FW2)[0], tm(FW3)[0]) == (0.0, 0.0, -5.0) and len(yangi_xabarlar(_x0)) == 1,
      (rw2.status_code, tm(FW1), tm(FW2), tm(FW3), yangi_xabarlar(_x0)))
FV1, FV2 = yangi_tm(-5, "TM182 VV Karniz"), yangi_tm(5, "TM182 VV Karniz")      # majburan (eski holat)
_x0 = len(XABARLAR)
rv = buyurtma(detal(3, FV1), tasdiq=True)
check("S11 eski minus V1 −5 + bo'sh V2 5: V1 dan 3 m (tasdiq) — avval qarz yopiladi (V2 0), so'ng V1 −3; Telegram xabari BITTA «-3»",
      rv.status_code == 200 and (tm(FV1)[0], tm(FV2)[0]) == (-3.0, 0.0) and len(yangi_xabarlar(_x0)) == 1 and "-3" in yangi_xabarlar(_x0)[0],
      (rv.status_code, tm(FV1), tm(FV2), yangi_xabarlar(_x0)))
FB4, FB5 = yangi_tm(10, "TM182 B4 Karniz", band=8), yangi_tm(20, "TM182 B4 Karniz")
OB4 = js(buyurtma(detal(2, FB4))).get("id")
_b4 = (tm(FB4)[0], tm(FB5)[0])
rb4 = tahrir(OB4, FB4, 5)
check("S12 tahrirda band: B4 10 (band 8) dan 2 m (B4 8), so'ng 2 → 5 m — 200; band to'ldirildi: B4 8, B5 17",
      _b4 == (8.0, 20.0) and rb4.status_code == 200 and tm(FB4)[0] == 8.0 and tm(FB5)[0] == 17.0, (_b4, rb4.status_code, det_matn(rb4), tm(FB4), tm(FB5)))
# tekshiruv 2-bosqich P1-1: avval BAND partiya kamomadi, so'ng minus — band boshqa buyurtmaniki
FE1, FE2, FE3 = yangi_tm(10, "TM182 E Karniz", band=8), yangi_tm(0, "TM182 E Karniz"), yangi_tm(5, "TM182 E Karniz")
_x0 = len(XABARLAR)
re1 = buyurtma(detal(7, FE1), detal(3, FE2), tasdiq=True)
check("S14 E1 10 (band 8) + E2 0 + E3 5: E1 dan 7, E2 dan 3 (tasdiq) — E3 ning 5 m i E1 bandiga (E1 8 = band), E2 −3 qoladi, Telegram",
      re1.status_code == 200 and (tm(FE1)[0], tm(FE2)[0], tm(FE3)[0]) == (8.0, -3.0, 0.0) and len(yangi_xabarlar(_x0)) == 1,
      (re1.status_code, det_matn(re1), tm(FE1), tm(FE2), tm(FE3), yangi_xabarlar(_x0)))
FH2 = yangi_tm(0, "TM182 H Karniz")                      # id tartibi: H2 < H1 < H3
FH1, FH3 = yangi_tm(10, "TM182 H Karniz", band=8), yangi_tm(5, "TM182 H Karniz")
rh1 = buyurtma(detal(7, FH1), detal(3, FH2), tasdiq=True)
check("S15 id tartibi boshqa (H2 0 < H1 10 / band 8 < H3 5) — rad EMAS (ilgari 400 «band»): H1 8, H2 −3, H3 0",
      rh1.status_code == 200 and (tm(FH1)[0], tm(FH2)[0], tm(FH3)[0]) == (8.0, -3.0, 0.0),
      (rh1.status_code, det_matn(rh1), tm(FH1), tm(FH2), tm(FH3)))
FB3 = yangi_tm(10, "TM182 B3 Karniz", band=8)
rb3 = buyurtma(detal(5, FB3), tasdiq=True)
check("S6 guruhdoshsiz band (zip 176 qoidasi AYNAN) — tasdiq bilan ham 400 «band», o'zgarmadi",
      rb3.status_code == 400 and "band" in det_matn(rb3) and tm(FB3) == (10.0, 10000.0, 8.0), (rb3.status_code, det_matn(rb3), tm(FB3)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Y. Yuk xati — «Faqat bor» (egasi qarori): minusdagi qism topshirilmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FY = yangi_tm(10, "TM182 Y Karniz")
OY = js(buyurtma(detal(15, FY), tasdiq=True)).get("id")
DY = detal_id(OY)
_qy = buyurtma(detal(5, FY), qoralama=True, tasdiq=True)      # qoralama omborga tegmaydi — jismoniy hisobga KIRMAYDI
check("Y0 shu partiyadan qoralama (5 m) — 200, qoldiq o'zgarmadi (−5)", _qy.status_code == 200 and tm(FY)[0] == -5.0, (_qy.status_code, tm(FY)))
ry1 = A.post("/api/deliveries", json={"order_id": OY, "items": [{"order_item_id": DY, "quantity": 15}]})
check("Y1 minus −5: 15 m yuk xati — 400 «jismonan 10 metr bor — 5 metr hali ishlab chiqarilmagan»",
      ry1.status_code == 400 and "jismonan 10 metr bor" in det_matn(ry1) and "5 metr hali ishlab chiqarilmagan" in det_matn(ry1),
      (ry1.status_code, det_matn(ry1)))
ry2 = A.post("/api/deliveries", json={"order_id": OY, "items": [{"order_item_id": DY, "quantity": 10}]})
check("Y2 10 m — 200 (bor miqdor)", ry2.status_code == 200, (ry2.status_code, det_matn(ry2)))
ry3 = A.post("/api/deliveries", json={"order_id": OY, "items": [{"order_item_id": DY, "quantity": 5}]})
check("Y3 qolgan 5 m — 400 «jismonan 0 metr»", ry3.status_code == 400 and "jismonan 0 metr bor" in det_matn(ry3), (ry3.status_code, det_matn(ry3)))
_ad = js(A.post(f"/api/finished/{FY}/add", json={"quantity": 5}))
check("Y4 «Yana ishlab chiqarish» +5 — minus yopildi (0), tannarx 0 (ilgari 5 m tannarxi 0 m li qatorda qolardi)",
      _ad.get("success") and tm(FY) == (0.0, 0.0, 0.0), (_ad, tm(FY)))
ry4 = A.post("/api/deliveries", json={"order_id": OY, "items": [{"order_item_id": DY, "quantity": 5}]})
check("Y5 endi 5 m — 200", ry4.status_code == 200, (ry4.status_code, det_matn(ry4)))
FT = yangi_tm(10, "TM182 T Karniz")
OT = js(buyurtma(detal(15, FT), tasdiq=True)).get("id")
rt = A.post(f"/api/orders/{OT}/ready")
check("Y6 «Tayyor» (avtomatik yuk xati) minusda — 400, sabab «minusda», buyurtma jarayonda qoldi",
      rt.status_code == 400 and "minusda" in det_matn(rt) and holat(OT) == "in_progress", (rt.status_code, det_matn(rt), holat(OT)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. Sotuv — minusda sotilmaydi, guruhda minus bo'lsa bo'sh qoldiq «ushlanadi» (egasi qarori)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FU1, FU2 = yangi_tm(-5, "TM182 U Karniz"), yangi_tm(20, "TM182 U Karniz")      # bazada majburan (muvozanatsiz) — himoya qatlami sinovi
ru1 = A.post("/api/finished/sell", json={"finished_product_id": FU2, "quantity": 20, "unit_price": 5000})
check("U1 U1 −5, U2 20: U2 dan 20 sotish — 400 «boshqa partiyasi minusda (5 metr buyurtmaga qarz) … faqat 15»",
      ru1.status_code == 400 and "boshqa partiyasi minusda" in str(det(ru1)) and "faqat 15" in str(det(ru1)) and tm(FU2)[0] == 20.0,
      (ru1.status_code, det(ru1), tm(FU2)))
ru2 = A.post("/api/finished/sell", json={"finished_product_id": FU2, "quantity": 15, "unit_price": 5000})
check("U2 15 m — 200, U2 5", ru2.status_code == 200 and tm(FU2)[0] == 5.0, (ru2.status_code, det(ru2), tm(FU2)))
ru3 = A.post("/api/finished/sell-batch", json={"items": [{"finished_product_id": FU2, "quantity": 1, "unit_price": 5000}]})
check("U3 savatcha: U2 dan 1 m — 400 «ushlanadi» (qarz 5 > bo'sh 5 − 5 = 0)",
      ru3.status_code == 400 and "boshqa partiyasi minusda" in json.dumps(js(ru3), ensure_ascii=False) and tm(FU2)[0] == 5.0,
      (ru3.status_code, js(ru3), tm(FU2)))
ru4 = A.post("/api/finished/sell", json={"finished_product_id": FU1, "quantity": 1, "unit_price": 5000})
check("U4 minusdagi U1 ni sotish — 400 «qoldiq minusda … sotib bo'lmaydi» (ilgari «Omborda faqat -5 m bor»)",
      ru4.status_code == 400 and "qoldiq minusda" in str(det(ru4)) and "-5 m" not in str(det(ru4)).replace("(-5 metr", ""),
      (ru4.status_code, det(ru4)))
rl = A.post("/api/finished/loss", json={"finished_product_id": FU1, "quantity": 1, "reason": "x", "brak_sabab": "boshqa"})
check("U5 minusdagi U1 — omborda brak — 400 «qoldiq minusda»", rl.status_code == 400 and "qoldiq minusda" in json.dumps(js(rl), ensure_ascii=False),
      (rl.status_code, js(rl)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. O'chirish — minusdagi mahsulot o'chirilmaydi (qarz jim yo'qolardi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
rd = A.delete(f"/api/finished/{FU1}")
check("D1 −5 dagi mahsulotni o'chirish — 400 «minusda … o'chirib bo'lmaydi», mahsulot joyida",
      rd.status_code == 400 and "minusda" in str(det(rd)) and "o'chirib bo'lmaydi" in str(det(rd)) and tm(FU1) is not None,
      (rd.status_code, det(rd), tm(FU1)))
check("D2 `crud.delete_finished_product` ham rad etadi (ichki chaqiruv)",
      db_ishi(lambda s: crud.delete_finished_product(s, FU1, company_id=1)) is False and tm(FU1) is not None)

FDI = yangi_tm(10, "TM182 DI Karniz")
_rdi = buyurtma(detal(4, FDI), {"name": "TM182 oddiy detal", "category": "profil", "width": 20, "thickness": 10, "length": 2,
                                "quantity": 1, "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID})
_odi = js(_rdi).get("id")
_idi = [it.get("id") for it in (js(A.get(f"/api/orders/{_odi}")).get("items") or []) if it.get("finished_product_id") == FDI]
check("D3 tayyor mahsulotdan 4 m olingan (6 m qoldi)", _rdi.status_code == 200 and tm(FDI) == (6.0, 6000.0, 0.0), (_rdi.status_code, tm(FDI)))
_rdd = A.delete(f"/api/order-items/{_idi[0]}") if _idi else None
check("D4 shu detal `DELETE /api/order-items/{id}` bilan o'chirildi — 4 m omborga QAYTDI, 10 m / 10 000 (ilgari 6 m da qolardi)",
      _rdd is not None and _rdd.status_code == 200 and tm(FDI) == (10.0, 10000.0, 0.0), (_rdd.status_code if _rdd is not None else None, tm(FDI)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L / V. Ro'yxat, qiymat, statistika, foyda oynasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FL, FL0 = yangi_tm(-3, "TM182 L Karniz", kun_oldin=100), yangi_tm(0, "TM182 L0 Karniz", kun_oldin=100)
_r = ruyxat()
check("L1 100 kun oldingi −3 partiya `/api/finished` da BOR (ilgari tushib qolardi), 0 li eskisi — yo'q (avvalgidek)",
      FL in _r and FL0 not in _r, (FL in _r, FL0 in _r))
FV = yangi_tm(-4, "TM182 V Karniz", narx=20000)
_r = ruyxat()
check("V1 narxli minus partiya: `total_value` 0, `ombor_qiymati` 0 (ilgari −80 000)",
      _r[FV]["total_value"] == 0 and _r[FV]["ombor_qiymati"] == 0, (_r[FV]["total_value"], _r[FV]["ombor_qiymati"]))
_st = js(A.get("/api/finished/stats"))
_mm = {x["birlik"]: x["miqdor"] for x in (_st.get("minus_miqdorlar") or [])}
_kut = round(-sum(min(0.0, (tm(f) or (0,))[0]) for f in ruyxat() if (tm(f) or (0,))[0] < 0), 4)
check("V2 statistika: `minus_soni` va `minus_miqdorlar` (metr — hamma minus yig'indisi, musbat son); eski kalitlar joyida",
      _st.get("minus_soni") == sum(1 for f in ruyxat() if (tm(f) or (0,))[0] < 0) and abs(_mm.get("metr", 0) - _kut) < 1e-6
      and "miqdorlar" in _st and "total_value" in _st, (_st.get("minus_soni"), _mm, _kut))
_pf = js(A.get(f"/api/finished/{FV}/profit"))
check("V3 foyda oynasi: `minusda` true, `qarz` 4, sotuv 0, foyda 0 (ilgari «-80 000»), `quantity` −4",
      _pf.get("minusda") is True and _pf.get("qarz") == 4 and _pf.get("revenue") == 0 and _pf.get("profit") == 0
      and _pf.get("quantity") == -4, _pf)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. «Yana ishlab chiqarish» — minusdan keyin tannarx faqat musbat qismga")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FQ = yangi_tm(10, "TM182 Q Karniz")
buyurtma(detal(15, FQ), tasdiq=True)
_aq = js(A.post(f"/api/finished/{FQ}/add", json={"quantity": 8}))
check("Q1 −5 + 8 = 3, tannarx = qo'shilgan tannarxning 3/8 qismi (ilgari to'liq 8 m tannarxi 3 m ga)",
      _aq.get("success") and tm(FQ)[0] == 3.0 and abs(tm(FQ)[1] - round(_aq.get("add_cost", 0) * 3 / 8, 2)) <= 1.0,
      (_aq, tm(FQ)))
FQ2 = yangi_tm(10, "TM182 Q2 Karniz")
_aq2 = js(A.post(f"/api/finished/{FQ2}/add", json={"quantity": 5}))
check("Q2 musbat qoldiqda (10 + 5) — avvalgidek AYNAN: tannarx 10 000 + qo'shilgan",
      _aq2.get("success") and tm(FQ2)[0] == 15.0 and abs(tm(FQ2)[1] - (10000 + _aq2.get("add_cost", 0))) <= 1.0, (_aq2, tm(FQ2)))
FQ3, FQ4 = yangi_tm(-6, "TM182 Q3 Karniz"), yangi_tm(4, "TM182 Q3 Karniz")
_aq3 = js(A.post(f"/api/finished/{FQ4}/add", json={"quantity": 4}))
check("Q3 musbat guruhdoshga +4 (Q4 8) — guruhdagi Q3 −6 yopildi: Q3 0, Q4 2", _aq3.get("success") and tm(FQ3)[0] == 0.0
      and tm(FQ4)[0] == 2.0 and _aq3.get("minus_yopildi"), (_aq3, tm(FQ3), tm(FQ4)))
FQ5, FQ6 = yangi_tm(0, "TM182 Q5 Karniz", band=6), yangi_tm(2, "TM182 Q5 Karniz")   # eski holat: band qoldiqdan katta (minus EMAS)
_aq5 = js(A.post(f"/api/finished/{FQ6}/add", json={"quantity": 8}))
check("Q4 eski «band > qoldiq» (Q5 0 / band 6, minus emas) — guruhdoshga +8: Q6 10, Q5 0 / band 6 o'zgarmadi (faqat minus yopiladi)",
      _aq5.get("success") and tm(FQ6)[0] == 10.0 and tm(FQ5) == (0.0, 0.0, 6.0) and not _aq5.get("minus_yopildi"), (_aq5, tm(FQ5), tm(FQ6)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R / C. Band bekor qilinganda va brak bekor qilinganda")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FR1, FR2 = yangi_tm(-5, "TM182 R Karniz"), yangi_tm(10, "TM182 R Karniz", band=10)
rr = A.post(f"/api/finished/{FR2}/release-reservation")
check("R1 «Bandni bekor qilish» — ozod bo'lgan 10 m guruhdagi minusni yopdi: R1 0, R2 5",
      rr.status_code == 200 and tm(FR1)[0] == 0.0 and tm(FR2) == (5.0, tm(FR2)[1], 0.0), (rr.status_code, js(rr), tm(FR1), tm(FR2)))
FC = yangi_tm(10, "TM182 C Karniz")
_lc = js(A.post("/api/finished/loss", json={"finished_product_id": FC, "quantity": 4, "reason": "sinov", "brak_sabab": "boshqa"}))
buyurtma(detal(16, FC), tasdiq=True)
check("C1 brak 4 → 6 m, buyurtma 16 m (tasdiq) → −10, tannarx 0", tm(FC) == (-10.0, 0.0, 0.0), (_lc, tm(FC)))
rcb = A.delete(f"/api/finished/loss/{_lc.get('loss_id')}")
check("C2 brak bekor — −6, tannarx 0 (ilgari 4 000 — minusdagi qatorda tannarx)", rcb.status_code == 200 and tm(FC) == (-6.0, 0.0, 0.0),
      (rcb.status_code, js(rcb), tm(FC)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Telegram «Darhol xabar» — tahrir va jarayonga olish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FT2 = yangi_tm(10, "TM182 T2 Karniz")
_x0 = len(XABARLAR)
OT2 = js(buyurtma(detal(12, FT2), tasdiq=True)).get("id")
check("T1 yaratish (−2) — bitta xabar", len(yangi_xabarlar(_x0)) == 1 and "-2" in yangi_xabarlar(_x0)[0], yangi_xabarlar(_x0))
_x0 = len(XABARLAR)
r_t = tahrir(OT2, FT2, 15, tasdiq=True)
check("T2 tahrir 12 → 15 (−5, minus chuqurlashdi) — xabar «-5»", r_t.status_code == 200 and len(yangi_xabarlar(_x0)) == 1
      and "-5" in yangi_xabarlar(_x0)[0], (r_t.status_code, det_matn(r_t), yangi_xabarlar(_x0)))
_x0 = len(XABARLAR)
r_t2 = tahrir(OT2, FT2, 14)
check("T3 tahrir 15 → 14 (minus kamaydi) — xabar YO'Q", r_t2.status_code == 200 and not yangi_xabarlar(_x0) and tm(FT2)[0] == -4.0,
      (r_t2.status_code, det_matn(r_t2), yangi_xabarlar(_x0), tm(FT2)))
FT3 = yangi_tm(5, "TM182 T3 Karniz")
OQ = js(buyurtma(detal(8, FT3), qoralama=True, tasdiq=True)).get("id")
_x0 = len(XABARLAR)
ra1 = A.post(f"/api/orders/{OQ}/activate")
check("T4 qoralama 8 m (qoldiq 5) — jarayonga olish tasdiqsiz 409, xabar yo'q", ra1.status_code == 409 and not yangi_xabarlar(_x0),
      (ra1.status_code, yangi_xabarlar(_x0)))
ra2 = A.post(f"/api/orders/{OQ}/activate?confirm_shortage=true")
check("T5 tasdiq bilan — 200, −3, BITTA xabar", ra2.status_code == 200 and tm(FT3)[0] == -3.0 and len(yangi_xabarlar(_x0)) == 1,
      (ra2.status_code, tm(FT3), yangi_xabarlar(_x0)))
FT4 = yangi_tm(10, "TM182 T4 Karniz")
_x0 = len(XABARLAR)
buyurtma(detal(4, FT4))
check("T6 minussiz buyurtma — xabar yo'q", not yangi_xabarlar(_x0), yangi_xabarlar(_x0))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Retsept bo'yicha (MRP) ishlab chiqarish yakunlanganda minus yopiladi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_mat = js(A.post("/api/inventory", json={"item_name": "TM182 Qum", "unit": "kg", "category": "Kimyoviy qo'shimchalar",
                                         "stock_quantity": 1000, "price_per_unit": 100, "min_stock": 0}))
_pt = js(A.post("/api/production/product-types", json={"name": "TM182 Travertin", "unit": "m2", "input_template": "quantity_only",
                                                       "pricing_formula": "unit_based"}))
_bom = js(A.post("/api/production/boms", json={"product_type_id": _pt.get("id"), "variant_name": "Standart", "batch_quantity": 1,
                                               "items": [{"inventory_id": _mat.get("id"), "quantity": 2}]}))


def ishlab(miqdor):
    p = js(A.post("/api/production/orders", json={"product_type_id": _pt.get("id"), "bom_id": _bom.get("id"), "quantity": miqdor,
                                                  "source_type": "warehouse_stock"}))
    pid = (p.get("production_order") or p).get("id")
    A.post(f"/api/production/orders/{pid}/start")
    r = A.post(f"/api/production/orders/{pid}/complete")
    return pid, r


def mrp_tm(pid):
    return db_ishi(lambda s: s.get(ProductionOrder, pid).finished_product_id if pid else None)


_p1, _rm1 = ishlab(10)
FM1 = mrp_tm(_p1)
db_ishi(lambda s: setattr(s.get(FinishedProduct, FM1), "quantity", -5.0) or setattr(s.get(FinishedProduct, FM1), "cost_price", 0.0))
_p2, _rm2 = ishlab(10)
FM2 = mrp_tm(_p2)
check("M1 MRP partiya −5 (majburan), yangi ishlab chiqarish 10 m² yakunlandi — M1 0, M2 5 (minus yopildi), jurnalda",
      _rm2.status_code == 200 and FM1 and FM2 and FM1 != FM2 and tm(FM1)[0] == 0.0 and tm(FM2)[0] == 5.0
      and jurnal("tm_minus_yopildi", FM1) == 1, (_rm1.status_code, _rm2.status_code, js(_rm2), FM1, FM2, tm(FM1), tm(FM2)))
_tx = {t["id"]: t for t in (js(A.get("/api/production/product-types/xulosa")) or [])}
db_ishi(lambda s: setattr(s.get(FinishedProduct, FM1), "quantity", -2.0))
_tx2 = {t["id"]: t for t in (js(A.get("/api/production/product-types/xulosa")) or [])}
check("M2 «Ishlab chiqarish» jadvali — `minusda` kaliti (0 → 2), «Omborda» o'zgarmaydi (musbat qoldiq)",
      _tx.get(_pt.get("id"), {}).get("minusda") == 0 and _tx2.get(_pt.get("id"), {}).get("minusda") == 2
      and _tx2.get(_pt.get("id"), {}).get("omborda") == 5, (_tx.get(_pt.get("id")), _tx2.get(_pt.get("id"))))
db_ishi(lambda s: setattr(s.get(FinishedProduct, FM1), "quantity", 0.0) or setattr(s.get(FinishedProduct, FM1), "reserved_quantity", 6.0))
_p3, _rm3 = ishlab(10)
FM3 = mrp_tm(_p3)
check("M3 eski «band > qoldiq» (M1 0 / band 6, minus emas) — yangi MRP 10 m² yakunlandi: M3 10, M1 0 / band 6 o'zgarmadi",
      _rm3.status_code == 200 and FM3 and tm(FM3)[0] == 10.0 and tm(FM1)[0] == 0.0 and tm(FM1)[2] == 6.0,
      (_rm3.status_code, js(_rm3), FM3, tm(FM1), tm(FM3)))
# M4 (tekshiruv 2-bosqich P2-6): MRP detalidan «Ortiqcha» qaytarish band qoldiqni bo'shatadi — shu guruhdagi minus yopiladi
_om = js(A.post("/api/orders?confirm_shortage=true", json={"project_id": PRJ_ID, "order_type": "product", "loy_kg": 0, "items": [
    {"name": "TM182 MRP detal", "category": "mrp_product", "quantity": 10, "unit_price": 100000, "is_coated": False,
     "penoplast_id": None, "product_type_id": _pt.get("id")}]}))
_om_id = _om.get("id")
_om_iid = detal_id(_om_id) if _om_id else None
_po4 = js(A.post("/api/production/orders", json={"product_type_id": _pt.get("id"), "bom_id": _bom.get("id"), "quantity": 10,
                                               "source_type": "customer_order", "source_order_id": _om_id,
                                               "source_order_item_id": _om_iid}))
_po4_id = (_po4.get("production_order") or _po4).get("id") if isinstance(_po4, dict) else None
A.post(f"/api/production/orders/{_po4_id}/start")
_rc4 = A.post(f"/api/production/orders/{_po4_id}/complete")
FR4 = mrp_tm(_po4_id)
db_ishi(lambda s: setattr(s.get(FinishedProduct, FM2), "quantity", -3.0) or setattr(s.get(FinishedProduct, FM2), "cost_price", 0.0)
        or (FM3 and setattr(s.get(FinishedProduct, FM3), "quantity", 0.0)) or (FM3 and setattr(s.get(FinishedProduct, FM3), "cost_price", 0.0)))
# guruhdagi boshqa bo'sh qoldiq yo'q (M1 0 / band 6, M3 0) — minusni faqat qaytarishda bo'shagan qism yopa oladi
_rq4 = A.post("/api/returns", json={"order_id": _om_id, "order_item_id": _om_iid, "item_name": "x", "quantity": 4, "unit": "m²",
                                    "reason": "Ortiqcha", "refund_amount": 0, "to_stock": True})
check("M4 MRP detali 10 m² (band 10) dan «Ortiqcha» 4 m² qaytdi — bo'shagan 4 m² guruhdagi M2 −3 ni yopdi: M2 0, partiya 7 / band 6",
      _rc4.status_code == 200 and FR4 and _rq4.status_code == 200 and tm(FM2)[0] == 0.0 and tm(FR4)[0] == 7.0 and tm(FR4)[2] == 6.0,
      (_rc4.status_code, _rq4.status_code, det_matn(_rq4), FR4, tm(FM2), tm(FR4) if FR4 else None))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. Parallel — guruhning ikki partiyasidan bir vaqtda (qulf tartibi, faqat PG)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL and hasattr(crud, "_tm_guruh_muvozanat"):
    FP1, FP2 = yangi_tm(10, "TM182 P Karniz"), yangi_tm(20, "TM182 P Karniz")
    C1, C2 = mijoz(), mijoz()
    _natija = [None, None]
    _orig = crud._tm_guruh_muvozanat

    def _sekin(db, fp, performed_by=None):
        import time as _t
        _t.sleep(0.4)
        return _orig(db, fp, performed_by=performed_by)
    crud._tm_guruh_muvozanat = _sekin
    # ikkala so'rov detalini YOZIB (PG tashqi kalit — tayyor mahsulot qatoriga KEY SHARE), so'ng BIRGA guruh qulfiga keladi —
    # qulf `FOR UPDATE` bo'lsa ikkalasi bir-birining KEY SHARE ini kutib qoladi (40P01); `FOR NO KEY UPDATE` — navbat bilan
    _orig_qg = crud._fp_qulf_guruh
    _bar_q = threading.Barrier(2, timeout=5)

    def _qulf_birga(db, fp_ids, company_id=None):
        try:
            _bar_q.wait()
        except threading.BrokenBarrierError:
            pass
        return _orig_qg(db, fp_ids, company_id)
    crud._fp_qulf_guruh = _qulf_birga
    _bar = threading.Barrier(2)

    def _ish(i, c, fid, prj):
        _bar.wait()
        _natija[i] = c.post("/api/orders?confirm_shortage=true", json=tana(detal(20, fid), prj=prj))
    # ikki BOSHQA loyiha — loyiha qulfi ularni ketma-ket qilmaydi; guruh qulfi (`_fp_qulf_guruh`) bo'lmasa P1 muvozanati P2 ning eski
    # qiymatiga yozib, P2 dagi olishni yo'qotadi (yoki ikkalasi bir-birini kutib qoladi)
    _th = [threading.Thread(target=_ish, args=(0, C1, FP1, PRJ_ID)), threading.Thread(target=_ish, args=(1, C2, FP2, PRJ2_ID))]
    [t.start() for t in _th]
    [t.join() for t in _th]
    crud._tm_guruh_muvozanat = _orig
    crud._fp_qulf_guruh = _orig_qg
    _sum = tm(FP1)[0] + tm(FP2)[0]
    check("P1 P1 dan 20 va P2 dan 20 bir vaqtda (tasdiq) — ikkalasi 200 (qotib qolish / 500 yo'q), jami 30 − 40 = −10",
          [r.status_code for r in _natija] == [200, 200] and abs(_sum - (-10.0)) < 1e-6,
          ([(r.status_code, det_matn(r)) for r in _natija], tm(FP1), tm(FP2)))
    check("P2 muvozanat: bo'sh qoldiq va minus bir vaqtda qolmaydi (bittasi 0, ikkinchisi −10)",
          sorted([tm(FP1)[0], tm(FP2)[0]]) == [-10.0, 0.0], (tm(FP1), tm(FP2)))
    # P3 (tekshiruv 2-bosqich P2-4): qoralamani jarayonga olish (xomashyo → guruh) va guruhdoshga «Yana ishlab chiqarish» (guruh →
    # xomashyo) bir vaqtda — qoralama endi guruhni XOMASHYODAN OLDIN qulflaydi; ilgari ikkalasi bir-birini kutib qolardi (40P01)
    import services as _sv_p3                      # noqa: E402
    FK1, FK2 = yangi_tm(10, "TM182 K3 Karniz"), yangi_tm(10, "TM182 K3 Karniz")
    _qd = buyurtma(detal(2, FK1), dict(detal(1, None), finished_product_id=None), qoralama=True)
    OK3 = js(_qd).get("id")
    _bar3 = threading.Barrier(2, timeout=5)
    _orig_ded, _orig_qg3 = _sv_p3.deduct_inventory_for_order, crud._fp_qulf_guruh

    # to'siqlar argument bo'yicha (marshrut TestClient da boshqa ipda — ip nomi emas): xomashyo yechilgach (faqat jarayonga olish) va
    # «Yana ishlab chiqarish» guruh qulfidan keyin (`[K2]` — faqat qo'shish yo'li)
    def _ded3(*a, **k):
        r = _orig_ded(*a, **k)
        try:
            _bar3.wait()
        except threading.BrokenBarrierError:
            pass
        return r

    def _qg3(db, fp_ids, company_id=None):
        r = _orig_qg3(db, fp_ids, company_id)
        if [x for x in (fp_ids or []) if x] == [FK2]:
            try:
                _bar3.wait()
            except threading.BrokenBarrierError:
                pass
        return r
    _sv_p3.deduct_inventory_for_order, crud._fp_qulf_guruh = _ded3, _qg3
    C3, C4 = mijoz(), mijoz()
    _n3 = {}

    def _akt():
        _n3["akt"] = C3.post(f"/api/orders/{OK3}/activate?confirm_shortage=true")

    def _qosh():
        _n3["qosh"] = C4.post(f"/api/finished/{FK2}/add", json={"quantity": 5})
    _t3 = [threading.Thread(target=_akt, name="akt"), threading.Thread(target=_qosh, name="qosh")]
    [t.start() for t in _t3]
    [t.join() for t in _t3]
    _sv_p3.deduct_inventory_for_order, crud._fp_qulf_guruh = _orig_ded, _orig_qg3
    _s3 = {k: (v.status_code, det_matn(v)) for k, v in _n3.items()}
    check("P3 qoralamani jarayonga olish (K1 dan 2 m + penoplast detal) va K2 ga «Yana ishlab chiqarish» 5 m bir vaqtda — ikkalasi 200 "
          "(qotib qolish / 500 yo'q): K1 8, K2 15",
          _qd.status_code == 200 and _s3.get("akt", (0,))[0] == 200 and _s3.get("qosh", (0,))[0] == 200
          and (tm(FK1)[0], tm(FK2)[0]) == (8.0, 15.0), (_qd.status_code, _s3, tm(FK1), tm(FK2)))
elif PG_URL:
    check("P0 muvozanat yo'q (asl kod)", False)
else:
    print("  (P — faqat PG_URL bilan)")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:\n  - " + "\n  - ".join(FAILED))
sys.exit(0 if FAIL == 0 else 1)
