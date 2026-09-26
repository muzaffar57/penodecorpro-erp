#!/usr/bin/env python3
"""
test_buyurtma_raqam.py — kech86 darvozasi (100-band, FOYDALANUVCHI QARORI "A": buyurtma raqami HECH QACHON
qayta berilmaydi — raqam faqat o'sadi, o'chirilgan buyurtma raqami bo'shliq bo'lib qoladi) + K86-1 (yuk xati raqami).

O'LCHANGAN (asl kod `9e843c3` (zip 79), `work/probe100.py`, `probe100b.py`, `probe86c.py`; SQLite = PG 16):
`crud.create_order` raqami `seq = loyihadagi buyurtmalar SONI + 1 + urinish` (5 urinish) edi:
  R2 OXIRGI buyurtma qattiq o'chirilsa — yangisi AYNAN shu raqamni olardi (jurnalda bir raqam ikki buyurtmada);
  R3 O'RTADAGISI o'chirilsa — to'qnashuv -> `db.rollback()`: PG advisory qulfi BO'SHARDI (0), endpoint
     tranzaksiyasi bekor bo'lardi; parallel ikki bir xil so'rov (ikki marta bosish) — IKKI buyurtma (6 / 6);
  R5 BIRINCHI 5 tasi o'chirilsa — loyihaga buyurtma umuman yaratilmasdi (500, ikki marta).
K86-1: yuk xati raqami `yuklar SONI + 1` — o'rtadagi yuk o'chirilsa keyingisi MAVJUD raqamni olardi (Y-3 ikki marta);
oxirgi yuk o'chirilsa uning raqami qayta berilardi. Loyiha raqami: `PRJ-003` butunlay o'chirilgach yangi loyiha yana
`PRJ-003` (probe86c). FOYDALANUVCHI QARORI (kech86): "A" qoidasi yuk xati va loyiha raqamlariga HAM.

TUZATISH: `projects.oxirgi_buyurtma_seq` (BERILGAN eng katta raqam) + `crud.buyurtma_raqam_asosi` (hisoblagich,
korxonadagi shu prefiksli buyurtmalar, hisoblagich bo'sh bo'lsa faoliyat jurnali); band raqam oldindan o'tkaziladi;
PG to'qnashuvi — SAVEPOINT (qulf saqlanadi); urinishlar tugasa 409; hisoblagich oxirida (TM / ombordan keyin);
migratsiya `main._migrate_buyurtma_raqam_hisoblagich` (NULL larni to'ldiradi, idempotent); yuk raqami — eng katta + 1
va `orders.oxirgi_yuk_seq`; loyiha raqami — korxona qulfi (186) + `companies.oxirgi_loyiha_seq` (NULL bo'lsa jurnaldan).

Bo'limlar: A ketma-ket / oxirgisi / o'rtadagisi; B yumshoq va butunlay o'chirish; C birinchi 5 tasi; D qoralama;
T takror 8 s; M migratsiya (jurnal, bo'sh loyiha, tegilmaydi, idempotent, dangasa yo'l, ustun yo'q); P bir prefiks
ikki loyihada; S nosozlik in'ektsiyasi (eskirgan asos: PG — SAVEPOINT bilan keyingi raqam, SQLite — 409;
urinishlar tugasa — 409, baza o'zgarmaydi); K yuk xati raqami (o'rtadagi / oxirgi o'chirilsa, eski buyurtma);
L loyiha raqami (butunlay o'chirilgan qayta berilmaydi, hisoblagich bo'sh — jurnaldan); Q (faqat PG) parallel
nazorat va bo'shliq; H statik tartib.

Ishlatish:
    python3 tools/test_buyurtma_raqam.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_buyurtma_raqam.py
"""
import os
import sys
import inspect
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "buyurtma_raqam_test"
_T = tempfile.mkdtemp(prefix="buyurtma_raqam_")
_DB = os.path.join(_T, "buyurtma_raqam_test.db")

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
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402
    import schemas                                 # noqa: E402

from sqlalchemy import text as T                   # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, Order, OrderItem, ActivityLog, InventoryMovement, Delivery,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.headers = {}

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def xabar(r):
    d = js(r)
    if isinstance(d, dict):
        det = d.get("detail", d)
        if isinstance(det, dict):
            return str(det.get("message") or det)
        return str(det)
    return str(getattr(r, "text", ""))[:300]


def tartibda(src, *qismlar):
    """Qismlar src ichida AYNAN shu tartibda uchraydimi (find — topilmasa False)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


# ---------------- fikstura ----------------
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "BR86_admin", "Parol123!", UserRole.ADMIN, "BR86 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="BR86 Penoplast", unit="blok", stock_quantity=10_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_db.add(PENO)
_db.commit()
PENO_ID = PENO.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = C.post("/login", data={"username": "BR86_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _lr.status_code in (200, 302, 303), _lr.status_code)

_n = [0]


def loyiha(nom, raqam=None):
    s = SessionLocal()
    p = Project(company_id=1, client_name=nom + " mijoz", project_name=nom, total_budget=0, total_paid=0,
                project_number=raqam)
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    return pid


def tana(pid, qoralama=False):
    _n[0] += 1
    return {"project_id": pid, "order_type": "product", "is_draft": bool(qoralama),
            "items": [{"name": f"BR86_D{_n[0]}", "category": "profil", "width": 20, "thickness": 10,
                       "length": 2 + _n[0] % 5, "quantity": 1, "unit_price": 50_000 + _n[0],
                       "is_coated": False, "penoplast_id": PENO_ID}]}


def yarat(pid, qoralama=False, body=None):
    r = req(C, "post", "/api/orders?confirm_shortage=true", json=body or tana(pid, qoralama))
    d = js(r) or {}
    return {"kod": r.status_code, "id": d.get("id") if isinstance(d, dict) else None,
            "raqam": d.get("order_number") if isinstance(d, dict) else None, "det": xabar(r)[:200]}


def ochir(oid):
    return req(C, "delete", f"/api/orders/{oid}").status_code


def raqamlar(pid):
    s = SessionLocal()
    try:
        return [[a, b, bool(c)] for a, b, c in s.query(Order.id, Order.order_number, Order.is_deleted)
                .filter(Order.project_id == pid).order_by(Order.id).all()]
    finally:
        s.close()


def hisob(pid):
    try:
        with engine.connect() as cn:
            return cn.execute(T("SELECT oxirgi_buyurtma_seq FROM projects WHERE id = :i"), {"i": pid}).scalar()
    except Exception as e:                 # noqa: BLE001
        return f"YO'Q ({type(e).__name__})"


def hisob_qoy(pid, qiymat):
    try:
        with engine.connect() as cn:
            cn.execute(T("UPDATE projects SET oxirgi_buyurtma_seq = :v WHERE id = :i"), {"v": qiymat, "i": pid})
            cn.commit()
        return True
    except Exception:                      # noqa: BLE001
        return False


def xato_soni():
    try:
        with engine.connect() as cn:
            return cn.execute(T("SELECT count(*) FROM error_logs")).scalar()
    except Exception:                      # noqa: BLE001
        return -1


def barmoq():
    s = SessionLocal()
    try:
        return {"orders": s.query(Order).count(), "items": s.query(OrderItem).count(),
                "harakat": s.query(InventoryMovement).count(), "jurnal": s.query(ActivityLog).count(),
                "peno": round(float(s.get(Inventory, PENO_ID).stock_quantity), 9),
                "yuk": s.query(Delivery).count()}
    finally:
        s.close()


def pref(pid):
    return f"ORD-{pid:03d}-"


# --- qulf kuzatuvchisi: buyurtma yaratilgach (endpoint bloki ichida, commitdan oldin) ---
QULF = []
_asl_deduct = services.deduct_inventory_for_order


def _kuzat(*a, **k):
    db = a[0] if a else k.get("db")
    try:
        if db.bind.dialect.name == "postgresql":
            QULF.append(int(db.execute(T("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                                         "AND pid = pg_backend_pid()")).scalar()))
    except Exception:                      # noqa: BLE001
        QULF.append(-1)
    return _asl_deduct(*a, **k)


services.deduct_inventory_for_order = _kuzat

# ============ A — ketma-ket, oxirgisi, o'rtadagisi ============
section("A — ketma-ket 7 ta; OXIRGISI va O'RTADAGISI qattiq o'chirilsa raqam qayta berilmaydi")
PA = loyiha("BR86 A")
A = [yarat(PA) for _ in range(7)]
check("A1 7 ta buyurtma — hammasi 200, raqamlar 1..7", [x["kod"] for x in A] == [200] * 7
      and [x["raqam"] for x in A] == [f"{pref(PA)}{i}" for i in range(1, 8)], A)
check("A2 loyiha hisoblagichi = 7", hisob(PA) == 7, hisob(PA))
_k = ochir(A[6]["id"])
_g = req(C, "get", f"/api/orders/{A[6]['id']}").status_code
check("A3a oxirgi buyurtma QATTIQ o'chdi (200, keyin 404)", _k == 200 and _g == 404, [_k, _g])
A8 = yarat(PA)
check("A3 oxirgisi o'chirilgach yangi buyurtma — ORD-…-8 (7 QAYTA BERILMADI)",
      A8["kod"] == 200 and A8["raqam"] == f"{pref(PA)}8", A8)
s = SessionLocal()
_jr = {}
for _lab, _eid in s.query(ActivityLog.entity_label, ActivityLog.entity_id).filter(
        ActivityLog.entity_type == "order", ActivityLog.action == "created",
        ActivityLog.entity_label.like(f"{pref(PA)}%")).all():
    _jr.setdefault(_lab, set()).add(_eid)
s.close()
check("A4 faoliyat jurnalida har raqam BITTA buyurtmaga tegishli", _jr and all(len(v) == 1 for v in _jr.values()),
      {k: sorted(v) for k, v in _jr.items()})
_k = ochir(A[2]["id"])
QULF.clear()
A9 = yarat(PA)
check("A5 o'rtadagisi (3) o'chirilgach — ORD-…-9, 200", _k == 200 and A9["kod"] == 200
      and A9["raqam"] == f"{pref(PA)}9", [_k, A9])
if PG_URL:
    check("A6 PG: yangi buyurtma yaratilgach advisory qulf hali USHLANGAN (1)", QULF == [1], QULF)
check("A7 hisoblagich = 9", hisob(PA) == 9, hisob(PA))

# ============ B — yumshoq va butunlay o'chirish ============
section("B — yumshoq (yuk xatli) va chiqindidan butunlay o'chirish")
PB = loyiha("BR86 B")
B = [yarat(PB) for _ in range(3)]
s = SessionLocal()
_iid = s.query(OrderItem.id).filter(OrderItem.order_id == B[0]["id"]).first()[0]
s.close()
_ry = req(C, "post", "/api/deliveries", json={"order_id": B[0]["id"], "items": [{"order_item_id": _iid, "quantity": 0.3}],
                                                "notes": "BR86 B yuk"})
_k = ochir(B[0]["id"])
_rs = raqamlar(PB)
check("B1 yukli buyurtma YUMSHOQ o'chdi (yozuv qoldi, is_deleted)", _ry.status_code == 200 and _k == 200
      and _rs and _rs[0][2] is True, [_ry.status_code, _k, _rs])
B4 = yarat(PB)
check("B2 yumshoqdan keyin — ORD-…-4", B4["kod"] == 200 and B4["raqam"] == f"{pref(PB)}4", B4)
_kp = req(C, "delete", f"/api/orders/{B[0]['id']}/permanent").status_code
B5 = yarat(PB)
check("B3 chiqindidan BUTUNLAY o'chirilgach — ORD-…-5 (1 qayta berilmadi, 4 bilan to'qnashmadi)",
      _kp == 200 and B5["kod"] == 200 and B5["raqam"] == f"{pref(PB)}5", [_kp, B5])

# ============ C — birinchi 5 tasi o'chirilsa ============
section("C — 10 ta buyurtma, BIRINCHI 5 tasi qattiq o'chirilsa loyiha bloklanmaydi")
PC = loyiha("BR86 C")
CC = [yarat(PC) for _ in range(10)]
_ok = [ochir(x["id"]) for x in CC[:5]]
_e0 = xato_soni()
C11 = yarat(PC)
C12 = yarat(PC)
check("C1 5 ta o'chirish 200", _ok == [200] * 5, _ok)
check("C2 yangi buyurtma 200 — ORD-…-11 (ilgari 500, 5 urinish band)", C11["kod"] == 200
      and C11["raqam"] == f"{pref(PC)}11", C11)
check("C3 yana biri — ORD-…-12", C12["kod"] == 200 and C12["raqam"] == f"{pref(PC)}12", C12)
check("C4 xato jurnaliga hech narsa yozilmadi (IntegrityError yo'q)", xato_soni() == _e0, [_e0, xato_soni()])

# ============ D — qoralama ============
section("D — qoralama ham raqam oladi; faollashtirish raqamni o'zgartirmaydi; o'chirilgan qoralama raqami band")
PD = loyiha("BR86 D")
D1 = yarat(PD, qoralama=True)
check("D1 qoralama — ORD-…-1, hisoblagich 1", D1["kod"] == 200 and D1["raqam"] == f"{pref(PD)}1"
      and hisob(PD) == 1, [D1, hisob(PD)])
D2 = yarat(PD)
_ra = req(C, "post", f"/api/orders/{D1['id']}/activate")
_rs = raqamlar(PD)
check("D2 faollashtirish 200, raqam o'zgarmadi", _ra.status_code == 200 and _rs[0][1] == f"{pref(PD)}1"
      and D2["raqam"] == f"{pref(PD)}2", [_ra.status_code, xabar(_ra), _rs, D2])
_q = yarat(PD, qoralama=True)
_kq = ochir(_q["id"])
D4 = yarat(PD)
check("D3 qoralama (3) qattiq o'chirilgach — ORD-…-4", _q["raqam"] == f"{pref(PD)}3" and _kq == 200
      and D4["raqam"] == f"{pref(PD)}4", [_q, _kq, D4])

# ============ T — takror 8 s ============
section("T — bir xil tana 8 s ichida ikki marta: bitta buyurtma, hisoblagich o'zgarmaydi")
PT = loyiha("BR86 T")
_b = tana(PT)
_f0 = barmoq()
T1 = yarat(PT, body=_b)
_h1 = hisob(PT)
T2 = yarat(PT, body=_b)
_f1 = barmoq()
check("T1 ikkalasi 200, bir xil id va raqam", T1["kod"] == 200 and T2["kod"] == 200 and T1["id"] == T2["id"]
      and T1["raqam"] == f"{pref(PT)}1", [T1, T2])
check("T2 bazada +1 buyurtma, hisoblagich 1 (takror oshirmadi)", _f1["orders"] - _f0["orders"] == 1
      and _h1 == 1 and hisob(PT) == 1, [_f0, _f1, _h1, hisob(PT)])
T3 = yarat(PT)
check("T3 keyingi (boshqa tarkibli) — ORD-…-2", T3["raqam"] == f"{pref(PT)}2", T3)

# ============ M — migratsiya ============
section("M — migratsiya: bo'sh (NULL) hisoblagich to'ldiriladi (jurnal ham), idempotent")
_mig = getattr(main, "_migrate_buyurtma_raqam_hisoblagich", None)


def migratsiya():
    if _mig is None:
        return False
    with contextlib.redirect_stdout(_quiet):
        _mig()
    return True


PM1 = loyiha("BR86 M1")
M1 = [yarat(PM1) for _ in range(5)]
ochir(M1[4]["id"])
ochir(M1[3]["id"])
PM2 = loyiha("BR86 M2")
PM3 = loyiha("BR86 M3")
hisob_qoy(PM1, None)
hisob_qoy(PM2, None)
hisob_qoy(PM3, 100)
_mr = migratsiya()
check("M1 NULL loyiha — jurnaldagi o'chirilgan ORD-…-5 hisobga olindi (5)", _mr and hisob(PM1) == 5, [_mr, hisob(PM1)])
check("M2 buyurtmasiz loyiha — 0", hisob(PM2) == 0, hisob(PM2))
check("M3 to'ldirilgan hisoblagichga TEGILMAYDI (100)", hisob(PM3) == 100, hisob(PM3))
_oldin = [hisob(x) for x in (PA, PB, PC, PD, PT, PM1, PM2, PM3)]
migratsiya()
check("M4 qayta ishga tushirish hech narsani o'zgartirmaydi", [hisob(x) for x in (PA, PB, PC, PD, PT, PM1, PM2, PM3)]
      == _oldin and _mr, _oldin)
M6 = yarat(PM1)
check("M5 migratsiyadan keyin — ORD-…-6", M6["raqam"] == f"{pref(PM1)}6", M6)
PM4 = loyiha("BR86 M4")
M4 = [yarat(PM4) for _ in range(3)]
ochir(M4[2]["id"])
hisob_qoy(PM4, None)
M4n = yarat(PM4)
check("M6 dangasa yo'l: hisoblagich NULL bo'lsa create_order jurnaldan oladi — ORD-…-4, hisoblagich 4",
      M4n["raqam"] == f"{pref(PM4)}4" and hisob(PM4) == 4, [M4n, hisob(PM4)])
M3n = yarat(PM3)
check("M7 hisoblagich 100 — yangi buyurtma ORD-…-101", M3n["raqam"] == f"{pref(PM3)}101", M3n)
_drop = False
try:
    with engine.connect() as cn:
        cn.execute(T("ALTER TABLE projects DROP COLUMN oxirgi_buyurtma_seq"))
        cn.execute(T("ALTER TABLE orders DROP COLUMN oxirgi_yuk_seq"))
        cn.execute(T("ALTER TABLE companies DROP COLUMN oxirgi_loyiha_seq"))
        cn.commit()
    _drop = True
except Exception as e:                     # noqa: BLE001
    _drop = f"{type(e).__name__}: {str(e)[:120]}"
_mr2 = migratsiya()
check("M8 ustun YO'Q bazada migratsiya uni qo'shadi va HAMMA loyihani to'ldiradi",
      _drop is True and _mr2 and [hisob(x) for x in (PA, PB, PC, PD, PT, PM1, PM2, PM4)] == [9, 5, 12, 4, 2, 6, 0, 4],
      [_drop, [hisob(x) for x in (PA, PB, PC, PD, PT, PM1, PM2, PM4)]])
A10 = yarat(PA)
check("M9 ustun qayta qo'shilgach — ORD-…-10", A10["raqam"] == f"{pref(PA)}10", A10)
_ust2 = []
try:
    from sqlalchemy import inspect as _insp
    _ii = _insp(engine)
    _ust2 = ["oxirgi_yuk_seq" in {c["name"] for c in _ii.get_columns("orders")},
             "oxirgi_loyiha_seq" in {c["name"] for c in _ii.get_columns("companies")}]
except Exception as e:                     # noqa: BLE001
    _ust2 = [f"{type(e).__name__}"]
check("M10 migratsiya orders.oxirgi_yuk_seq va companies.oxirgi_loyiha_seq ni ham qo'shdi", _ust2 == [True, True], _ust2)

# ============ P — bir prefiks ikki loyihada ============
section("P — bir korxonada ikki loyiha bir xil prefiksda (PRJ-050 va L-50)")
PP1 = loyiha("BR86 P1", "PRJ-050")
PP2 = loyiha("BR86 P2", "L-50")
P1 = [yarat(PP1) for _ in range(3)]
_e0 = xato_soni()
P2 = yarat(PP2)
check("P1 birinchi loyiha ORD-050-1..3", [x["raqam"] for x in P1] == ["ORD-050-1", "ORD-050-2", "ORD-050-3"], P1)
check("P2 ikkinchi loyihaning birinchi buyurtmasi — ORD-050-4 (to'qnashuvsiz), xato jurnali o'zgarmadi",
      P2["kod"] == 200 and P2["raqam"] == "ORD-050-4" and xato_soni() == _e0, [P2, _e0, xato_soni()])
P1b = yarat(PP1)
check("P3 birinchi loyiha davomi — ORD-050-5", P1b["raqam"] == "ORD-050-5", P1b)

# ============ S — nosozlik in'ektsiyasi (eskirgan asos) ============
section("S — asos eskirgan (to'qnashuv): PG — SAVEPOINT bilan keyingi raqam; SQLite — 409; urinish tugasa 409")
_asl_asos = getattr(crud, "buyurtma_raqam_asosi", None)
_asl_band = getattr(crud, "_buyurtma_raqami_bandmi", None)
PS = loyiha("BR86 S")
S0 = [yarat(PS) for _ in range(3)]
crud.buyurtma_raqam_asosi = lambda *a, **k: 0
crud._buyurtma_raqami_bandmi = lambda *a, **k: False
try:
    _f0 = barmoq()
    _e0 = xato_soni()
    QULF.clear()
    S1 = yarat(PS)
    _f1 = barmoq()
    if PG_URL:
        check("S1 PG: eskirgan asos — 1..3 to'qnashdi, SAVEPOINT bilan ORD-…-4, 200",
              S1["kod"] == 200 and S1["raqam"] == f"{pref(PS)}4", S1)
        check("S2 PG: to'qnashuvlardan keyin ham advisory qulf USHLANGAN (1)", QULF == [1], QULF)
        check("S3 PG: bazada AYNAN +1 buyurtma, +1 detal", _f1["orders"] - _f0["orders"] == 1
              and _f1["items"] - _f0["items"] == 1, [_f0, _f1])
    else:
        check("S1 SQLite: to'qnashuv — 409 'band', hech narsa saqlanmadi", S1["kod"] == 409 and "band" in S1["det"]
              and "saqlanmadi" in S1["det"], S1)
        check("S2 SQLite: baza barmoq izi O'ZGARMADI", _f0 == _f1, [_f0, _f1])
        check("S3 SQLite: hisoblagich o'zgarmadi (3)", hisob(PS) == 3, hisob(PS))
    check("S4 xato jurnaliga 500 yozilmadi", xato_soni() == _e0, [_e0, xato_soni()])
    PS2 = loyiha("BR86 S2")
    crud.buyurtma_raqam_asosi = _asl_asos if _asl_asos else crud.buyurtma_raqam_asosi
    crud._buyurtma_raqami_bandmi = _asl_band if _asl_band else crud._buyurtma_raqami_bandmi
    S2x = [yarat(PS2) for _ in range(6)]
    crud.buyurtma_raqam_asosi = lambda *a, **k: 0
    crud._buyurtma_raqami_bandmi = lambda *a, **k: False
    _f0 = barmoq()
    S2n = yarat(PS2)
    _f1 = barmoq()
    check("S5 urinishlar tugadi (1..5 hammasi band) — 409, 500 EMAS", S2n["kod"] == 409, S2n)
    check("S6 baza barmoq izi O'ZGARMADI, hisoblagich 6", _f0 == _f1 and hisob(PS2) == 6, [_f0, _f1, hisob(PS2)])
finally:
    if _asl_asos is not None:
        crud.buyurtma_raqam_asosi = _asl_asos
    else:
        try:
            del crud.buyurtma_raqam_asosi
        except AttributeError:
            pass
    if _asl_band is not None:
        crud._buyurtma_raqami_bandmi = _asl_band
    else:
        try:
            del crud._buyurtma_raqami_bandmi
        except AttributeError:
            pass
S7 = yarat(PS2)
check("S7 in'ektsiyadan keyin normal — ORD-…-7", S7["kod"] == 200 and S7["raqam"] == f"{pref(PS2)}7", S7)

# ============ K — yuk xati raqami (K86-1) ============
section("K — yuk xati raqami: o'rtadagisi o'chirilsa takrorlanmaydi")
PK = loyiha("BR86 K")
KO = yarat(PK)
s = SessionLocal()
_iid = s.query(OrderItem.id).filter(OrderItem.order_id == KO["id"]).first()[0]
s.close()


def yuk():
    _n[0] += 1
    r = req(C, "post", "/api/deliveries", json={"order_id": KO["id"], "items": [{"order_item_id": _iid, "quantity": 0.3}],
                                                  "notes": f"BR86 K yuk {_n[0]}"})
    d = js(r) or {}
    return r.status_code, d.get("delivery_id"), d.get("delivery_number")


def yuk_raqamlari():
    s = SessionLocal()
    try:
        return [x for (x,) in s.query(Delivery.delivery_number).filter(Delivery.order_id == KO["id"]).order_by(Delivery.id)]
    finally:
        s.close()


Y = [yuk() for _ in range(3)]
check("K1 3 yuk — Y-1, Y-2, Y-3", [y[2] for y in Y] == [f"{KO['raqam']}/Y-{i}" for i in (1, 2, 3)], Y)
_kd = req(C, "delete", f"/api/deliveries/{Y[1][1]}").status_code
Y4 = yuk()
_yr = yuk_raqamlari()
check("K2 o'rtadagi (Y-2) o'chirilgach yangisi — Y-4 (Y-3 takrorlanmadi)", _kd == 200 and Y4[2] == f"{KO['raqam']}/Y-4",
      [_kd, Y4])
check("K3 hamma yuk raqamlari YAGONA", len(_yr) == len(set(_yr)) == 3, _yr)
_kd2 = req(C, "delete", f"/api/deliveries/{Y[0][1]}").status_code
Y5 = yuk()
_yr = yuk_raqamlari()
check("K4 birinchi (Y-1) o'chirilgach ham — Y-5, takror yo'q", _kd2 == 200 and Y5[2] == f"{KO['raqam']}/Y-5"
      and len(_yr) == len(set(_yr)), [_kd2, Y5, _yr])
_kd3 = req(C, "delete", f"/api/deliveries/{Y5[1]}").status_code
Y6 = yuk()
check("K5 OXIRGI (Y-5) o'chirilgach — Y-6 (Y-5 QAYTA BERILMADI)", _kd3 == 200 and Y6[2] == f"{KO['raqam']}/Y-6",
      [_kd3, Y6])


def yuk_hisob(oid):
    try:
        with engine.connect() as cn:
            return cn.execute(T("SELECT oxirgi_yuk_seq FROM orders WHERE id = :i"), {"i": oid}).scalar()
    except Exception as e:                 # noqa: BLE001
        return f"YO'Q ({type(e).__name__})"


check("K6 buyurtma yuk hisoblagichi = 6", yuk_hisob(KO["id"]) == 6, yuk_hisob(KO["id"]))
try:
    with engine.connect() as cn:
        cn.execute(T("UPDATE orders SET oxirgi_yuk_seq = NULL WHERE id = :i"), {"i": KO["id"]})
        cn.commit()
except Exception:                          # noqa: BLE001
    pass
Y7 = yuk()
check("K7 eski buyurtma (hisoblagich NULL) — mavjud yuklardan: Y-7", Y7[2] == f"{KO['raqam']}/Y-7"
      and yuk_hisob(KO["id"]) == 7, [Y7, yuk_hisob(KO["id"])])

# ============ L — loyiha raqami ============
section("L — loyiha raqami: butunlay o'chirilgan loyiha raqami qayta berilmaydi")


def api_loyiha(i):
    r = req(C, "post", "/api/projects", json={"project_name": f"BR86 L{i}", "client_name": f"BR86 M{i}"})
    d = js(r) or {}
    return r.status_code, d.get("id"), d.get("project_number")


def prj(x):
    try:
        return int(str(x).split("-")[1])
    except Exception:                      # noqa: BLE001
        return -1


def komp_hisob():
    try:
        with engine.connect() as cn:
            return cn.execute(T("SELECT oxirgi_loyiha_seq FROM companies WHERE id = 1")).scalar()
    except Exception as e:                 # noqa: BLE001
        return f"YO'Q ({type(e).__name__})"


L0 = [api_loyiha(i) for i in range(3)]
_n0 = prj(L0[0][2])
check("L1 3 loyiha — ketma-ket PRJ raqamlari, hisoblagich = oxirgisi", [x[0] for x in L0] == [200] * 3
      and [prj(x[2]) for x in L0] == [_n0, _n0 + 1, _n0 + 2] and komp_hisob() == _n0 + 2, [L0, komp_hisob()])
_s1 = req(C, "delete", f"/api/projects/{L0[2][1]}").status_code
_s2 = req(C, "delete", f"/api/projects/{L0[2][1]}/permanent").status_code
L3 = api_loyiha(3)
check("L2 oxirgi loyiha BUTUNLAY o'chirilgach — yangisi keyingi raqam (qayta berilmadi)", _s1 == 200 and _s2 == 200
      and prj(L3[2]) == _n0 + 3, [_s1, _s2, L3])
_s3 = req(C, "delete", f"/api/projects/{L3[1]}").status_code
_s4 = req(C, "delete", f"/api/projects/{L3[1]}/permanent").status_code
try:
    with engine.connect() as cn:
        cn.execute(T("UPDATE companies SET oxirgi_loyiha_seq = NULL WHERE id = 1"))
        cn.commit()
except Exception:                          # noqa: BLE001
    pass
L4 = api_loyiha(4)
check("L3 hisoblagich NULL (eski baza) — butunlay o'chirilgan raqam faoliyat jurnalidan olinadi",
      _s3 == 200 and _s4 == 200 and prj(L4[2]) == _n0 + 4 and komp_hisob() == _n0 + 4, [_s3, _s4, L4, komp_hisob()])

# ============ Q — parallel (faqat PG) ============
if PG_URL:
    section("Q — PG parallel: ikki bir xil so'rov bir vaqtda (Barrier) — nazorat va bo'shliq, har biri BITTA buyurtma")

    def _ctana(pid, nom):
        return schemas.OrderCreate(**{"project_id": pid, "order_type": "product",
                                      "items": [{"name": nom, "category": "profil", "width": 20, "thickness": 10,
                                                 "length": 2, "quantity": 1, "unit_price": 50_000,
                                                 "is_coated": False, "penoplast_id": PENO_ID}]})

    def tajriba(bo_shliq):
        s = SessionLocal()
        p = Project(company_id=1, client_name="BR86 Q", project_name="BR86 Q", total_budget=0, total_paid=0)
        s.add(p)
        s.commit()
        pid = p.id
        ids = []
        for _ in range(3):
            _n[0] += 1
            ids.append(crud.create_order(s, _ctana(pid, f"BR86_Q{_n[0]}"), performed_by="test").id)
        if bo_shliq:
            crud.delete_order(s, ids[1], soft=False, performed_by="test")
        s.close()
        _n[0] += 1
        nom = f"BR86_Qyangi{_n[0]}"
        bar = threading.Barrier(2)
        nat = [None, None]

        def ish(i):
            s2 = SessionLocal()
            try:
                t = _ctana(pid, nom)
                bar.wait()
                o = crud.create_order(s2, t, performed_by="test")
                s2.commit()
                nat[i] = o.order_number
            except Exception as e:         # noqa: BLE001
                try:
                    s2.rollback()
                except Exception:          # noqa: BLE001
                    pass
                nat[i] = f"{type(e).__name__}"
            finally:
                s2.close()

        th = [threading.Thread(target=ish, args=(i,)) for i in range(2)]
        for t in th:
            t.start()
        for t in th:
            t.join(60)
        s = SessionLocal()
        soni = sum(1 for o in s.query(Order).filter(Order.project_id == pid, Order.is_deleted.isnot(True)).all()
                   if any(it.name == nom for it in o.items))
        s.close()
        return soni, nat, hisob(pid)

    _naz = [tajriba(False) for _ in range(3)]
    _bos = [tajriba(True) for _ in range(3)]
    check("Q1 nazorat (bo'shliqsiz) — 3 / 3 da BITTA yangi buyurtma, raqam 4, hisoblagich 4",
          all(x[0] == 1 and x[2] == 4 and set(x[1]) == {"ORD-" + x[1][0].split("-")[1] + "-4"} for x in _naz), _naz)
    check("Q2 bo'shliq (2-buyurtma o'chirilgan) — 3 / 3 da BITTA yangi buyurtma (ilgari 2 ta), raqam 4",
          all(x[0] == 1 and x[2] == 4 and set(x[1]) == {"ORD-" + x[1][0].split("-")[1] + "-4"} for x in _bos), _bos)

services.deduct_inventory_for_order = _asl_deduct

# ============ H — statik ============
section("H — statik: create_order / create_delivery tuzilishi")
try:
    _src = inspect.getsource(crud.create_order)
except Exception as e:                     # noqa: BLE001
    _src = ""
    print("  manba o'qilmadi:", e)
try:
    _srcd = inspect.getsource(crud.create_delivery)
except Exception:                          # noqa: BLE001
    _srcd = ""
_kod = "\n".join(q for q in _src.split("\n") if not q.strip().startswith("#"))
check("H1 create_order: `db.rollback()` YO'Q (qulf va endpoint tranzaksiyasi saqlanadi)", _kod and "db.rollback()" not in _kod)
check("H2 create_order: SAVEPOINT (`db.begin_nested()`) BOR", "db.begin_nested()" in _kod)
check("H3 create_order: eski `SONI + 1 + urinish` formulasi YO'Q", _kod and ".count() + 1 + attempt" not in _kod)
check("H4 takror-yuborish qaytishi raqam asosidan OLDIN (takrorda hisoblagich tegilmaydi)",
      tartibda(_kod, "_is_duplicate_submit = True", "return _recent_order", "buyurtma_raqam_asosi(db, _project, _prefiks)"))
check("H5 hisoblagich OXIRIDA: TM olinishidan KEYIN, yakuniy commitdan OLDIN",
      tartibda(_kod, "_take_finished_for_order(db, db_order)", "_project.oxirgi_buyurtma_seq = seq", "db.commit()\n"))
check("H6 band raqam oldindan tekshiriladi (`_buyurtma_raqami_bandmi`)", "_buyurtma_raqami_bandmi(db, _company_id" in _kod)
check("H7 urinishlar tugasa 409 (500 EMAS)", "status_code=409" in _kod and "ajratib bo'lmadi" in _kod)
check("H8 create_delivery: yuk raqami mavjudlarning eng kattasidan keyin (`/Y-(\\d+)$`)",
      tartibda(_srcd, "count() + 1", "/Y-(\\d+)$", "delivery_number = f\"{order.order_number}/Y-{seq}\""))
_mig_src = ""
try:
    _mig_src = inspect.getsource(main._migrate_buyurtma_raqam_hisoblagich)
except Exception:                          # noqa: BLE001
    pass
check("H9 migratsiya faqat NULL larni ishlaydi va jurnalni ham o'qiydi",
      "oxirgi_buyurtma_seq.is_(None)" in _mig_src and "jurnal=True" in _mig_src)
_ust = getattr(Project, "oxirgi_buyurtma_seq", None)
check("H10 model ustuni NULL bo'la oladi, standart qiymatsiz (eski qatorlar sync bilan 0 bo'lmasin)",
      _ust is not None and _ust.property.columns[0].nullable and _ust.property.columns[0].default is None)
try:
    from production_models import Company as _Co
    _u2 = [getattr(Order, "oxirgi_yuk_seq", None), getattr(_Co, "oxirgi_loyiha_seq", None)]
    _u2ok = all(u is not None and u.property.columns[0].nullable and u.property.columns[0].default is None for u in _u2)
except Exception:                          # noqa: BLE001
    _u2ok = False
check("H11 yuk / loyiha hisoblagich ustunlari ham NULL, standart qiymatsiz", _u2ok)
check("H12 create_delivery: hisoblagich yakuniy commitdan OLDIN yoziladi",
      tartibda(_srcd, "oxirgi_yuk_seq).filter(Order.id == order.id)", "order.oxirgi_yuk_seq = seq",
               "db.commit()\n    db.refresh(db_delivery)"))
try:
    _srcp = inspect.getsource(crud.create_project)
except Exception:                          # noqa: BLE001
    _srcp = ""
check("H13 create_project: korxona qulfi (186) va asos loyiha qo'shilishidan OLDIN, hisoblagich commitdan OLDIN",
      tartibda(_srcp, "_pul_qulfi(db, 186, company_id)", "loyiha_raqam_asosi(db, company_id)", "db_project = Project(",
               "oxirgi_loyiha_seq = next_num", "db.commit()"))

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
sys.exit(1 if FAIL else 0)
