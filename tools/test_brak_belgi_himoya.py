#!/usr/bin/env python3
"""
test_brak_belgi_himoya.py — K57-1 / 40-band darvozasi (kech57, 2026-09-24).

NIMA UCHUN KERAK (O'LCHANGAN)
-----------------------------
"Ishlab chiqarish braki" yozuvi (`FinishedProductLoss`) matn BELGISI bilan
ajratiladi: `reason` `crud._ISH_BRAK_BELGI` ("Ishlab chiqarish jarayonida brak")
bilan boshlansa — ishlab chiqarish braki. Lekin "Tayyor turgan, keyin yo'qoldi"
(`POST /api/finished/loss`) yozuvining `reason` i — foydalanuvchi ERKIN matni.
`work/probe57.py` (asl kod `5931ff3` = zip 56, SQLite VA PG — AYNAN):
izoh "Ishlab chiqarish jarayonida brak chiqdi, ..." bo'lsa mahsulot 10 → 8,
tan narx −200 000, LEKIN Moliya `brak_xarajat` O'ZGARMADI (200 000 hisobotdan
yo'qoldi, sof foyda oshib ko'rindi), `/api/returns/stats` uni ishlab chiqarish
braki deb sanadi, brak tahlili turi "Ishlab chiqarish braki", bekor qilish
(`DELETE /api/finished/loss/{id}`) 400 bilan RAD etildi — ombor 8 da qoldi.

Qo'shimcha (40-band, kodda): belgi `services.py` da IKKI literal NUSXA edi
(`get_monthly_report`, `calculate_split_profit_report`) — biri o'zgarsa
ishlab chiqarish braki ikki marta ayirilardi.

YECHIM (texnik — Claude): `crud._ish_brak_belgisidan_ajrat` — bunday izoh
"Izoh: " bilan saqlanadi (buxgalteriya REJIMGA bo'ysunadi, matnga emas; harf
kattaligi farqsiz — SQLite `LIKE`); `services` belgini `crud._ISH_BRAK_BELGI`
dan oladi (yagona manba). Ishlab chiqarish braki yozuvchisi O'ZGARMAGAN.

BO'LIMLAR
  A. Yordamchi — holatlar jadvali
  B. HTTP: belgi bilan boshlangan izoh (3 xil yozilish) — saqlanish, Moliya,
     stats, tahlil, bekor qilish, ombor tiklanishi
  C. Oddiy izohlar AYNAN saqlanadi (bo'shliq, o'rtada, None, oddiy)
  E. Yagona manba — `crud._ISH_BRAK_BELGI` vaqtincha almashtirilsa Moliya va
     liniya hisoboti unga ergashadi (sezgirlik; D dan OLDIN yuriladi)
  D. Ishlab chiqarish braki O'ZGARMAGAN (belgi, ikki marta hisoblanmaydi,
     bekor qilish rad, stats sanaydi)
  S. Statik — chaqiruv joyi, yozuvchi, literal nusxa yo'q

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_brak_belgi_himoya.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_brak_belgi_himoya.py
"""
import os
import sys
import io
import inspect
import tempfile
import contextlib
from datetime import datetime

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "brak_belgi_himoya_test"
_DB = os.path.join(tempfile.gettempdir(), "brak_belgi_himoya_test.db")

if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
               isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402,F401
from sqlalchemy import event                       # noqa: E402
from database import SessionLocal, engine          # noqa: E402

if not PG_URL:
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
    # kech40 saboqi: migratsiyalar ochgan ulanishlar hovuzda PRAGMA siz qoladi
    engine.dispose()

import crud                                        # noqa: E402
import auth                                        # noqa: E402
import services                                    # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    FinishedProduct, FinishedProductLoss, StockSource, ProductionStatus,
    Inventory, UserRole,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
db = SessionLocal()
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {YORLIQ}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {YORLIQ}{label}   {detail}")


def bolim(t):
    print(f"\n{'=' * 60}\n{YORLIQ}{t}\n{'=' * 60}")


BELGI = "Ishlab chiqarish jarayonida brak"
_N = datetime.utcnow()
YIL, OY = _N.year, _N.month

for _cid, _nom in ((1, "A"), (2, "B")):
    if not db.query(Company).filter(Company.id == _cid).first():
        db.add(Company(id=_cid, name=_nom))
db.commit()

with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(db, "bbh_admin", "Parol123!", UserRole.ADMIN, "BBH", company_id=1)
client = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = client.post("/login", data={"username": "bbh_admin", "password": "Parol123!"},
                  follow_redirects=False)
check("login (admin, A korxona)", _lr.status_code == 302, str(_lr.status_code))

_FP_N = [0]


def yangi_fp(qty=10.0, cost=1_000_000.0, cid=1):
    _FP_N[0] += 1
    fp = FinishedProduct(company_id=cid, name=f"BBH Mahsulot {_FP_N[0]}", category="profil",
                         quantity=qty, produced_quantity=qty, unit="metr",
                         unit_price=200_000, cost_price=cost,
                         source=StockSource.PRODUCED,
                         production_status=ProductionStatus.READY)
    db.add(fp)
    db.commit()
    db.refresh(fp)
    return fp.id


def yangi_peno(cid=1, stock=100.0):
    inv = Inventory(company_id=cid, item_name=f"BBH Penoplast {cid}", unit="blok",
                    stock_quantity=stock, price_per_unit=500_000,
                    volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv.id


def yangi_peno_fp(peno_id, cid=1, qty=10.0, cost=100_000.0):
    fp = FinishedProduct(company_id=cid, name="BBH Profil peno", category="profil",
                         quantity=qty, produced_quantity=qty, unit="metr",
                         unit_price=50_000, cost_price=cost,
                         source=StockSource.PRODUCED,
                         production_status=ProductionStatus.READY,
                         penoplast_id=peno_id, unit_volume_m3=0.01,
                         unit_loy_kg=0.0, is_coated=False)
    db.add(fp)
    db.commit()
    db.refresh(fp)
    return fp.id


def moliya_brak():
    db.expire_all()
    try:
        return round(float(services.get_monthly_report(db, YIL, OY, company_id=1)
                           .get("brak_xarajat", 0) or 0), 2)
    except Exception as e:           # hisobot yiqilsa ham skript QULAMASIN
        return f"xato: {type(e).__name__}"


def liniya_peno_brak():
    db.expire_all()
    try:
        r = services.calculate_split_profit_report(db, YIL, OY, company_id=1)
        return round(float(((r or {}).get("penoplast") or {}).get("brak_xarajati", 0) or 0), 2)
    except Exception as e:
        return f"xato: {type(e).__name__}"


def stats():
    r = client.get("/api/returns/stats")
    if r.status_code != 200:
        return ("status", r.status_code)
    j = r.json()
    return (round(float(j.get("brak_total_value") or 0), 2), int(j.get("brak_total_count") or 0))


def tahlil_turi(nomi):
    db.expire_all()
    try:
        t = services.get_brak_tahlil(db, YIL, OY, company_id=1, oylar=1)
        return [y.get("turi") for y in (t.get("yoqotishlar") or []) if y.get("nomi") == nomi]
    except Exception as e:
        return f"xato: {type(e).__name__}"


def fp_holat(fp_id):
    db.expire_all()
    fp = db.get(FinishedProduct, fp_id)
    return (round(float(fp.quantity), 6), round(float(fp.cost_price or 0), 2))


def loss_yozuvi(loss_id):
    db.expire_all()
    return db.get(FinishedProductLoss, loss_id)


def son(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ════════════════════════════════════════════════════════════════
bolim("A. Yordamchi — holatlar jadvali")
# ════════════════════════════════════════════════════════════════
_aj = getattr(crud, "_ish_brak_belgisidan_ajrat", None)
check("crud._ish_brak_belgisidan_ajrat mavjud", callable(_aj))
check("crud._ISH_BRAK_BELGI o'zgarmagan", getattr(crud, "_ISH_BRAK_BELGI", None) == BELGI,
      str(getattr(crud, "_ISH_BRAK_BELGI", None)))
_jadval = [
    ("None -> None", None, None),
    ("oddiy izoh -> AYNAN", "Omborda sindi", "Omborda sindi"),
    ("belgi bilan boshlansa -> 'Izoh: '", f"{BELGI} chiqdi", f"Izoh: {BELGI} chiqdi"),
    ("faqat belgi -> 'Izoh: '", BELGI, f"Izoh: {BELGI}"),
    ("kichik harf -> 'Izoh: '", BELGI.lower() + " x", "Izoh: " + BELGI.lower() + " x"),
    ("katta harf -> 'Izoh: '", BELGI.upper(), "Izoh: " + BELGI.upper()),
    ("boshida bo'shliq -> AYNAN", "  " + BELGI, "  " + BELGI),
    ("o'rtada -> AYNAN", f"izoh: {BELGI}", f"izoh: {BELGI}"),
    ("allaqachon 'Izoh: ' -> AYNAN", f"Izoh: {BELGI}", f"Izoh: {BELGI}"),
    ("bo'sh matn -> AYNAN", "", ""),
]
for _nom, _kir, _kut in _jadval:
    try:
        _chiq = _aj(_kir) if callable(_aj) else "funksiya yo'q"
    except Exception as e:
        _chiq = f"xato: {type(e).__name__}"
    check(f"yordamchi: {_nom}", _chiq == _kut, repr(_chiq))
if callable(_aj):
    check("yordamchi natijasi ishlab chiqarish braki EMAS (_ish_brakimi)",
          not crud._ish_brakimi(type("L", (), {"reason": _aj(f"{BELGI} x")})()))
else:
    check("yordamchi natijasi ishlab chiqarish braki EMAS (_ish_brakimi)", False, "funksiya yo'q")


# ════════════════════════════════════════════════════════════════
bolim("B. HTTP: belgi bilan boshlangan 'tayyor turgan' izoh")
# ════════════════════════════════════════════════════════════════
_b_holatlar = [
    ("aniq belgi", f"{BELGI} chiqdi, omborda yotgan edi"),
    ("kichik harf", BELGI.lower() + " — omborda"),
    ("katta harf", BELGI.upper()),
]
for _nom, _izoh in _b_holatlar:
    fid = yangi_fp()
    _m0, _l0, _s0 = moliya_brak(), liniya_peno_brak(), stats()
    r = client.post("/api/finished/loss",
                    json={"finished_product_id": fid, "quantity": 2, "reason": _izoh})
    check(f"B[{_nom}] POST 200", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
    j = r.json() if r.status_code == 200 else {}
    lid, xarajat = j.get("loss_id"), son(j.get("cost_amount"))
    check(f"B[{_nom}] tan narx 200 000", xarajat is not None and abs(xarajat - 200_000) < 0.01,
          str(xarajat))
    l = loss_yozuvi(lid) if lid else None
    _saq = getattr(l, "reason", "yozuv yo'q")
    check(f"B[{_nom}] izoh 'Izoh: ' bilan, matn o'zgarmagan", _saq == "Izoh: " + _izoh, repr(_saq))
    check(f"B[{_nom}] yozuv ishlab chiqarish braki EMAS",
          l is not None and not crud._ish_brakimi(l))
    check(f"B[{_nom}] mahsulot 8 / 800 000", fp_holat(fid) == (8.0, 800_000.0), str(fp_holat(fid)))
    _m1, _l1, _s1 = moliya_brak(), liniya_peno_brak(), stats()
    check(f"B[{_nom}] Moliya brak_xarajat +200 000",
          son(_m1) is not None and son(_m0) is not None and abs(_m1 - _m0 - 200_000) < 0.5,
          f"{_m0} -> {_m1}")
    check(f"B[{_nom}] liniya hisoboti penoplast brak +200 000",
          son(_l1) is not None and son(_l0) is not None and abs(_l1 - _l0 - 200_000) < 0.5,
          f"{_l0} -> {_l1}")
    check(f"B[{_nom}] /returns/stats o'zgarmadi (ishlab chiqarish braki emas)", _s1 == _s0,
          f"{_s0} -> {_s1}")
    _tur = tahlil_turi(f"BBH Mahsulot {_FP_N[0]}")
    check(f"B[{_nom}] tahlil turi \"Yo'qotish (tayyor turgan)\"",
          _tur == ["Yo'qotish (tayyor turgan)"], str(_tur))
    d = client.delete(f"/api/finished/loss/{lid}") if lid else None
    check(f"B[{_nom}] bekor qilish 200", d is not None and d.status_code == 200,
          f"{getattr(d, 'status_code', None)} {getattr(d, 'text', '')[:150]}")
    check(f"B[{_nom}] bekor qilingach mahsulot 10 / 1 000 000",
          fp_holat(fid) == (10.0, 1_000_000.0), str(fp_holat(fid)))
    _m2 = moliya_brak()
    check(f"B[{_nom}] bekor qilingach Moliya asl holatda",
          son(_m2) is not None and son(_m0) is not None and abs(_m2 - _m0) < 0.5, f"{_m0} -> {_m2}")


# ════════════════════════════════════════════════════════════════
bolim("C. Oddiy izohlar AYNAN saqlanadi")
# ════════════════════════════════════════════════════════════════
_c_holatlar = [
    ("oddiy", "Omborda sindi"),
    ("boshida bo'shliq", "  " + BELGI),
    ("o'rtada", "izoh: " + BELGI + " emas"),
    ("izohsiz (None)", None),
]
for _nom, _izoh in _c_holatlar:
    fid = yangi_fp()
    _m0, _s0 = moliya_brak(), stats()
    tana = {"finished_product_id": fid, "quantity": 1}
    if _izoh is not None:
        tana["reason"] = _izoh
    r = client.post("/api/finished/loss", json=tana)
    check(f"C[{_nom}] POST 200", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
    lid = (r.json() if r.status_code == 200 else {}).get("loss_id")
    l = loss_yozuvi(lid) if lid else None
    check(f"C[{_nom}] izoh AYNAN", l is not None and l.reason == _izoh,
          repr(getattr(l, "reason", "yozuv yo'q")))
    _m1, _s1 = moliya_brak(), stats()
    check(f"C[{_nom}] Moliya +100 000, stats o'zgarmadi",
          son(_m1) is not None and son(_m0) is not None and abs(_m1 - _m0 - 100_000) < 0.5
          and _s1 == _s0, f"{_m0} -> {_m1}; {_s0} -> {_s1}")
    d = client.delete(f"/api/finished/loss/{lid}") if lid else None
    check(f"C[{_nom}] bekor qilish 200, mahsulot tiklandi",
          d is not None and d.status_code == 200 and fp_holat(fid) == (10.0, 1_000_000.0),
          f"{getattr(d, 'status_code', None)} {fp_holat(fid)}")


# ════════════════════════════════════════════════════════════════
bolim("E. Yagona manba — crud._ISH_BRAK_BELGI ga ergashadi (sezgirlik; D dan OLDIN —\n      bazada belgili yozuv yo'q, aks holda almashtirishda u ham siljiydi)")
# ════════════════════════════════════════════════════════════════
_asl_belgi = getattr(crud, "_ISH_BRAK_BELGI", BELGI)
_E_BELGI = "XBELGI57 sinov"
_e_fid = yangi_fp()
_e_loss = FinishedProductLoss(company_id=1, finished_product_id=_e_fid, product_name="BBH E",
                              category="profil", quantity=1, unit="metr", cost_amount=12_345,
                              reason=_E_BELGI + " — yozuv", created_by="t",
                              lost_at=datetime.utcnow())
db.add(_e_loss)
db.commit()
_e_id = _e_loss.id
try:
    _me0, _le0 = moliya_brak(), liniya_peno_brak()
    crud._ISH_BRAK_BELGI = _E_BELGI
    _me1, _le1 = moliya_brak(), liniya_peno_brak()
finally:
    crud._ISH_BRAK_BELGI = _asl_belgi
check("E asl belgi bilan yozuv Moliyada hisoblanadi (fikstura)",
      son(_me0) is not None and son(_me1) is not None and _me0 >= 12_345 - 0.5, f"{_me0}")
check("E belgi almashtirilsa Moliya yozuvni ishlab chiqarish braki deb chiqaradi (−12 345)",
      son(_me0) is not None and son(_me1) is not None and abs((_me0 - _me1) - 12_345) < 0.5,
      f"{_me0} -> {_me1}")
check("E belgi almashtirilsa liniya hisoboti ham ergashadi (−12 345)",
      son(_le0) is not None and son(_le1) is not None and abs((_le0 - _le1) - 12_345) < 0.5,
      f"{_le0} -> {_le1}")
check("E belgi qaytarildi", getattr(crud, "_ISH_BRAK_BELGI", None) == _asl_belgi)
db.expire_all()
_e_obj = db.get(FinishedProductLoss, _e_id)
if _e_obj is not None:
    db.delete(_e_obj)
    db.commit()


# ════════════════════════════════════════════════════════════════
bolim("D. Ishlab chiqarish braki O'ZGARMAGAN")
# ════════════════════════════════════════════════════════════════
pid = yangi_peno()
pfid = yangi_peno_fp(pid)
_m0, _l0, _s0 = moliya_brak(), liniya_peno_brak(), stats()
try:
    rd = crud.record_finished_product_production_brak(
        db, pfid, 2.0, BELGI + " (izohda ham belgi)", created_by="t", company_id=1)
except Exception as e:
    rd = {"success": False, "message": f"xato: {type(e).__name__}: {e}"}
check("D ishlab chiqarish braki yozildi", bool(rd.get("success")), str(rd)[:200])
_dlid = rd.get("loss_id")
if not _dlid:
    db.expire_all()
    _q = (db.query(FinishedProductLoss)
          .filter(FinishedProductLoss.finished_product_id == pfid)
          .order_by(FinishedProductLoss.id.desc()).first())
    _dlid = _q.id if _q else None
dl = loss_yozuvi(_dlid) if _dlid else None
check("D izoh belgi bilan boshlanadi (yozuvchi o'zgarmagan)",
      dl is not None and (dl.reason or "").startswith(BELGI), repr(getattr(dl, "reason", None)))
check("D yozuv ishlab chiqarish braki (_ish_brakimi)", dl is not None and crud._ish_brakimi(dl))
_dxar = son(getattr(dl, "cost_amount", None))
_m1, _l1, _s1 = moliya_brak(), liniya_peno_brak(), stats()
check("D Moliya brak_xarajat BIR marta (harakat orqali, yo'qotish yozuvi qo'shilmaydi)",
      _dxar is not None and son(_m1) is not None and son(_m0) is not None
      and _dxar > 0 and abs((_m1 - _m0) - _dxar) < 1.0,
      f"{_m0} -> {_m1}, yozuv {_dxar}")
check("D liniya hisoboti ham BIR marta",
      _dxar is not None and son(_l1) is not None and son(_l0) is not None
      and abs((_l1 - _l0) - _dxar) < 1.0, f"{_l0} -> {_l1}, yozuv {_dxar}")
check("D /returns/stats ishlab chiqarish brakini sanaydi (+1)",
      isinstance(_s1[0], float) and _s1[1] == _s0[1] + 1, f"{_s0} -> {_s1}")
_fp_d0 = fp_holat(pfid)
dd = client.delete(f"/api/finished/loss/{_dlid}") if _dlid else None
check("D bekor qilish 400 (rad)", dd is not None and dd.status_code == 400,
      f"{getattr(dd, 'status_code', None)} {getattr(dd, 'text', '')[:120]}")
check("D rad etilgach mahsulot o'zgarmadi", fp_holat(pfid) == _fp_d0, f"{_fp_d0} -> {fp_holat(pfid)}")
check("D tahlil turi \"Ishlab chiqarish braki\"",
      tahlil_turi("BBH Profil peno") == ["Ishlab chiqarish braki"], str(tahlil_turi("BBH Profil peno")))


# ════════════════════════════════════════════════════════════════
bolim("S. Statik")
# ════════════════════════════════════════════════════════════════
try:
    _src_loss = inspect.getsource(crud.record_finished_product_loss)
except Exception:
    _src_loss = ""
try:
    _src_prod = inspect.getsource(crud.record_finished_product_production_brak)
except Exception:
    _src_prod = ""
_src_services = open(os.path.join(ROOT, "services.py"), encoding="utf-8").read()
_src_crud = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
check("S1 record_finished_product_loss izohni yordamchidan o'tkazadi",
      "reason=_ish_brak_belgisidan_ajrat(data.reason)" in _src_loss)
check("S2 record_finished_product_loss da xom `reason=data.reason,` YO'Q",
      "reason=data.reason," not in _src_loss)
check("S3 ishlab chiqarish braki yozuvchisi yordamchini CHAQIRMAYDI",
      bool(_src_prod) and "_ish_brak_belgisidan_ajrat" not in _src_prod)
check("S4 services.py da belgi literal nusxasi YO'Q",
      _src_services.count('"' + BELGI + '"') == 0,
      str(_src_services.count('"' + BELGI + '"')))
check("S5 services.py Moliya / liniya / tahlil crud._ISH_BRAK_BELGI ni oladi (>= 3)",
      _src_services.count("._ISH_BRAK_BELGI") >= 3, str(_src_services.count("._ISH_BRAK_BELGI")))
check("S6 crud.py da belgi matni FAQAT bir marta (konstanta)",
      _src_crud.count('"' + BELGI + '"') == 1, str(_src_crud.count('"' + BELGI + '"')))


db.close()
print(f"\n{'=' * 60}")
print(f"{YORLIQ}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
