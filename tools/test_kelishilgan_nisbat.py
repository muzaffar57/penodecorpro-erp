#!/usr/bin/env python3
"""
test_kelishilgan_nisbat.py — kech110 darvozasi: K110-1. Buyurtma jami o'zgarganda KELISHILGAN summaning YAGONA
qoidasi (`crud.kelishilgan_qayta_hisob`) — to'liq tahrir, detal tahriri / o'chirish, qisman «Tayyor», qo'lda summa,
to'lovda kechirilgan qarz (`Order.kechirilgan_qarz`) va uning migratsiyasi; brauzer nusxasi (`orders.html`
`kelishilganQayta`) bilan paritet (hisob butun tiyinlarda — float .5 chegarasida 1 so'mga adashardi).

NIMA UCHUN KERAK (asl kod `ba6935c` da O'LCHANGAN — `work/probe110k2.py`, HAQIQIY brauzer + uvicorn, SQLite = PG)
------------------------------------------------------------------------------------------------------------------
  * Tahrir formasi har doim eski kelishilgan summani yuborardi, server uni "qo'lda kiritilgan" deb olardi: chegirmasiz
    400 000 li buyurtmadan 100 000 lik detal olib tashlansa — kelishilgan 400 000 QOLARDI (mijoz qarzi 100 000 ga
    ortiq); 10 → 15 dona (jami 550 000) — 400 000 (27.27 % "chegirma" o'z-o'zidan); tiyinli 107 000.48 → 99 999.99 —
    107 000.48. Jonli sinovda (kech110): 56 000 → jami 20 000, kelishilgan 56 000.
  * 10 % chegirmali formaga nomsiz (saqlanmaydigan) qator qo'shilsa — u ham hisobga kirib 450 000 saqlanardi (jami
    400 000 — "ustama").
  * Ustamali 450 000 (jami 400 000): forma — 450 000 qolardi, API / detal tahriri / qisman «Tayyor» — ustama
    yo'qolardi (300 000 / 250 000 / 150 000).
  * To'lovda kechirilgan qarz: chegirmasiz buyurtmada forma eski summani qoldirardi (399 000, jami 300 000),
    chegirmalida kechirilgan summa yo'qolib qarz qayta paydo bo'lardi (495 000 − 358 000 = 137 000, to'g'risi 135 000).
  * Foiz `discount_percent` (2 xonaga yaxlitlangan) dan olinardi — `main` dagi ORD-030-1 (0.1043 % → 0.1 %) jami
    6 000 000 ga o'zgarsa 5 994 000 (aniq nisbat — 5 993 743).

EGASI QARORLARI (kech110, AskUserQuestion): ustama — "Foizi saqlansin" (400 000 / 450 000 → 300 000 da 337 500);
kechirilgan qarz — "Kechirilgan so'mda qolsin" (1 000 000, 5 %, 2 000 kechirilgan → 1 200 000 da 1 138 000).
Chegirma foizi saqlanishi va chegirmasiz buyurtma jami bilan birga o'zgarishi — avvalgi qoida (server 28-band).

BO'LIMLAR: R — qoida jadvali (sof funksiya); P — brauzer (`kelishilganQayta`, node) ↔ server paritet, 3 000+ holat;
A — API (to'liq tahrir summasiz, qo'lda summa, detal tahriri / o'chirish, qisman «Tayyor», kechirish yig'indisi,
`/agreed-amount` foizi, `GET /api/orders/{id}`); M — `main._migrate_kechirilgan_qarz` (izoh belgisidan to'ldirish,
aniq qiymat, idempotent, ustun yo'q bo'lsa qo'shish); X — 5xx yo'q; S — statik.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi; `TENANT_FILTER=1` bilan ham.
    python3 tools/test_kelishilgan_nisbat.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_kelishilgan_nisbat.py
Asl kodga qarshi QULAMAYDI (yangi nomlar `getattr`, HTTP istisno → 599). Chiqish kodi 0 — hammasi o'tdi.
"""
import os
import sys
import json
import math
import random
import inspect
import tempfile
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "kelishilgan_nisbat_test"
_T = tempfile.mkdtemp()
_DB = os.path.join(_T, "kelishilgan_nisbat_test.db")

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

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402

from sqlalchemy import text as _sql, inspect as _insp   # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import UserRole, Project, Order, OrderItem, OrderType, Inventory   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond)
    except Exception:                      # noqa: BLE001
        cond = False
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:500]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

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


def taxminan(a, b, eps=0.006):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def tartibda(src, *qismlar):
    """Qismlar `src` da shu TARTIBDA uchraydimi (`find` — topilmasa False, istisno yo'q)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


QAYTA = getattr(crud, "kelishilgan_qayta_hisob", None)


def qoida(t0, t1, asl0, x=0.0):
    if QAYTA is None:
        return None
    try:
        a, p = QAYTA(t0, t1, asl0, x)
        return (round(float(a), 2), round(float(p), 2))
    except Exception as e:                 # noqa: BLE001
        return f"ISTISNO {type(e).__name__}: {e}"


# ══════════════════════════════════════════════════════════════
# R. Qoida jadvali
# ══════════════════════════════════════════════════════════════
section("R. Qoida jadvali — `crud.kelishilgan_qayta_hisob` (eski jami, yangi jami, eski ASL, kechirilgan)")
check("R0 `crud.kelishilgan_qayta_hisob` bor", QAYTA is not None)
check("R1 jami o'zgarmagan — ASL o'zgarmaydi (360 000)", qoida(400_000, 400_000, 360_000) == (360_000, 360_000),
      qoida(400_000, 400_000, 360_000))
check("R2 chegirmasiz: 400 000 → 300 000 — kelishilgan 300 000", qoida(400_000, 300_000, 400_000) == (300_000, 300_000),
      qoida(400_000, 300_000, 400_000))
check("R3 10 % chegirma: 300 000 da 270 000", qoida(400_000, 300_000, 360_000) == (270_000, 270_000),
      qoida(400_000, 300_000, 360_000))
check("R4 ustama +12.5 % (450 000 / 400 000): 300 000 da 337 500 (egasi QARORI \"Foizi saqlansin\")",
      qoida(400_000, 300_000, 450_000) == (337_500, 337_500), qoida(400_000, 300_000, 450_000))
check("R5 chegirmasiz, 1 000 kechirilgan (399 000): 300 000 da 299 000, narx 300 000",
      qoida(400_000, 300_000, 399_000, 1_000) == (299_000, 300_000), qoida(400_000, 300_000, 399_000, 1_000))
check("R6 10 % chegirma, 2 000 kechirilgan (358 000): 550 000 da 493 000, narx 495 000",
      qoida(400_000, 550_000, 358_000, 2_000) == (493_000, 495_000), qoida(400_000, 550_000, 358_000, 2_000))
check("R7 egasi misoli: 1 000 000, 5 %, 2 000 kechirilgan (948 000) → 1 200 000 da 1 138 000 (so'mda)",
      qoida(1_000_000, 1_200_000, 948_000, 2_000) == (1_138_000, 1_140_000), qoida(1_000_000, 1_200_000, 948_000, 2_000))
check("R8 tiyinli chegirmasiz: 107 000.48 → 99 999.99 — AYNAN 99 999.99",
      qoida(107_000.48, 99_999.99, 107_000.48) == (99_999.99, 99_999.99), qoida(107_000.48, 99_999.99, 107_000.48))
check("R9 HALF_UP (bankir emas): 1 / 2 nisbat, 5 → 2.5 → 3", qoida(2, 5, 1) == (3, 3), qoida(2, 5, 1))
check("R10 eski jami 0 — yangi jamiga teng", qoida(0, 100_000, 0) == (100_000, 100_000), qoida(0, 100_000, 0))
check("R11 kechirilgan narxdan katta — 0 (manfiy emas)", qoida(400_000, 1_000, 395_000, 5_000) == (0, 1_000),
      qoida(400_000, 1_000, 395_000, 5_000))
_r12 = qoida(5_970_225.6, 6_000_000, 5_964_000)
# o'nlik arifmetikada: 6 000 000 × 5 964 000 / 5 970 225.6 = 5 993 743.352… → 5 993 743 (saqlangan 0.1 % bilan — 5 994 000)
check("R12 aniq nisbat (`main` ORD-030-1: 0.1043 %, saqlangan foiz 0.1): 6 000 000 da 5 993 743 (eski — 5 994 000)",
      _r12 == (5_993_743, 5_993_743), _r12)
check("R13 ustama + kechirilgan: 450 000 − 500 = 449 500, 300 000 da 337 500 − 500 = 337 000",
      qoida(400_000, 300_000, 449_500, 500) == (337_000, 337_500), qoida(400_000, 300_000, 449_500, 500))
check("R14 tiyin chegarasi: jami 0.004 ga farq — o'zgarmagan hisoblanadi (ASL AYNAN)",
      qoida(400_000.00, 400_000.004, 360_000.37) == (360_000.37, 360_000.37), qoida(400_000.00, 400_000.004, 360_000.37))
# .5 chegarasi — float `yangi × P / eski` adashadi (736 334.90 / 368 167.45 — 50 %, 1 022 239 → aniq 511 119.5):
_r15 = qoida(736_334.90, 1_022_239, 368_167.45)
check("R15 butun tiyinlarda HALF_UP: 50 % chegirma, yangi jami 1 022 239 — 511 120 (float hisob 511 119 berardi)",
      _r15 == (511_120, 511_120), _r15)
_r16 = qoida(3_764_434.38, 1_919_339, 1_882_217.19)
check("R16 xuddi shunday: 3 764 434.38 / 1 882 217.19, yangi 1 919 339 — 959 670 (float — 959 669)",
      _r16 == (959_670, 959_670), _r16)
check("R17 ustama tiyinli (400 000 / 450 000.37): 300 000 da butun so'm — 337 500", qoida(400_000, 300_000, 450_000.37)
      == (337_500, 337_500), qoida(400_000, 300_000, 450_000.37))

# ══════════════════════════════════════════════════════════════
# P. Brauzer ↔ server paritet (node)
# ══════════════════════════════════════════════════════════════
section("P. Brauzer (orders.html `kelishilganQayta`) ↔ server (`kelishilgan_qayta_hisob`) — node")


def js_funksiya(src, nom):
    i = src.find("function " + nom + "(")
    if i < 0:
        return None
    j = src.find("{", i)
    d = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            d += 1
        elif src[k] == "}":
            d -= 1
            if d == 0:
                return src[i:k + 1]
    return None


try:
    _src = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
except Exception:                          # noqa: BLE001
    _src = ""
_fn = [js_funksiya(_src, n) for n in ("_tiyin110", "_tiyinda110", "kelishilganQayta")]
check("P0 orders.html da `_tiyin110`, `_tiyinda110` va `kelishilganQayta` bor", all(_fn), [bool(x) for x in _fn])
_rnd = random.Random(110110)
HOLAT_P = [(400_000, 400_000, 360_000, 0), (400_000, 300_000, 400_000, 0), (400_000, 300_000, 360_000, 0),
           (400_000, 300_000, 450_000, 0), (400_000, 300_000, 399_000, 1_000), (400_000, 550_000, 358_000, 2_000),
           (107_000.48, 99_999.99, 107_000.48, 0), (2, 5, 1, 0), (0, 100_000, 0, 0), (400_000, 1_000, 395_000, 5_000),
           (5_970_225.6, 6_000_000, 5_964_000, 0), (1_000_000, 1_200_000, 948_000, 2_000),
           # .5 chegarasi — float formulasi aniq o'nlik HALF_UP dan 1 so'mga farq qiladigan holatlar (kech110 qidiruvi)
           (3_823_215.56, 3_157_510, 2_867_411.67, 0), (736_334.9, 1_022_239, 368_167.45, 0),
           (3_214_767.12, 23_250_668, 401_845.89, 0), (3_764_434.38, 1_919_339, 1_882_217.19, 0),
           (4_803_721.48, 2_035_367, 2_401_860.74, 0), (1_342_604.7, 4_051_547, 671_302.35, 0)]


def _tiyin(v):
    return math.floor(v * 100 + 0.5) / 100


for _ in range(3_000):
    t0 = _tiyin(_rnd.uniform(0, 9_000_000)) if _rnd.random() < 0.8 else float(_rnd.randint(1, 5_000_000))
    tur = _rnd.random()
    if tur < 0.25:
        asl = t0
    elif tur < 0.55:
        asl = _tiyin(t0 * _rnd.uniform(0.5, 1.0))
    elif tur < 0.7:
        asl = float(round(t0 * _rnd.uniform(0.7, 1.0)))
    else:
        asl = _tiyin(t0 * _rnd.uniform(1.0, 1.5))
    x = 0.0 if _rnd.random() < 0.6 else _tiyin(_rnd.uniform(0, min(asl, 200_000)))
    asl = max(0.0, _tiyin(asl - x))
    t1 = t0 if _rnd.random() < 0.1 else (_tiyin(_rnd.uniform(0, 9_000_000)) if _rnd.random() < 0.7
                                         else float(_rnd.randint(0, 5_000_000)))
    HOLAT_P.append((t0, t1, asl, x))
_py = []
for h in HOLAT_P:
    try:
        a, p = QAYTA(*h) if QAYTA else (None, None)
        _py.append([a, p])
    except Exception as e:                 # noqa: BLE001
        _py.append([f"ISTISNO {e}", None])
_node = None
if all(_fn):
    _kod = "\n".join(_fn) + """
const kirish = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(kirish.map(([a, b, c, d]) => { const r = kelishilganQayta(a, b, c, d); return [r.asl, r.narx]; })));
"""
    _jf = os.path.join(_T, "paritet110.js")
    open(_jf, "w", encoding="utf-8").write(_kod)
    try:
        _p = subprocess.run(["node", _jf], input=json.dumps(HOLAT_P), capture_output=True, text=True, timeout=120)
        _node = json.loads(_p.stdout) if _p.returncode == 0 else None
        if _node is None:
            print("   node:", _p.stderr[:400])
    except Exception as e:                 # noqa: BLE001
        print("   node ishlamadi:", e)
check("P1 node ishladi (3 018 holat)", _node is not None and len(_node) == len(HOLAT_P))
if _node is not None and len(_node) == len(HOLAT_P) and QAYTA is not None:
    _farq = [(HOLAT_P[i], _py[i], _node[i]) for i in range(len(HOLAT_P)) if _py[i] != _node[i]]
    check("P2 brauzer va server natijasi HAR holatda AYNAN (float tengligi)", not _farq, _farq[:5])
    _turlar = {"o'zgarmagan": 0, "chegirmasiz": 0, "chegirma": 0, "ustama": 0, "kechirilgan": 0}
    for (t0, t1, asl, x) in HOLAT_P:
        p0 = _tiyin(asl + x)
        if abs(t1 - t0) <= 0.005:
            _turlar["o'zgarmagan"] += 1
        elif abs(p0 - t0) <= 0.005:
            _turlar["chegirmasiz"] += 1
        elif p0 < t0:
            _turlar["chegirma"] += 1
        else:
            _turlar["ustama"] += 1
        if x > 0:
            _turlar["kechirilgan"] += 1
    check("P3 holatlar hamma turni qamraydi (har biri ≥ 100)", min(_turlar.values()) >= 100, _turlar)
else:
    check("P2 paritet — o'lchab bo'lmadi", False, "node yoki server funksiyasi yo'q")

# ══════════════════════════════════════════════════════════════
# Tayyorgarlik (API)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "KN_admin", "Parol123!", UserRole.ADMIN, "KN Admin", company_id=1)
PRJ = [Project(company_id=1, client_name=f"KN Mijoz {i}", project_name=f"KN loyiha {i}", total_budget=0, total_paid=0)
       for i in range(40)]
PENO = Inventory(company_id=1, item_name="KN Penoplast", unit="blok", stock_quantity=100_000,
                 price_per_unit=500_000, volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
_db.add_all(PRJ + [PENO])
_db.commit()
PRJ_ID = [p.id for p in PRJ]
PENO_ID = PENO.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "KN_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code)
    print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL + 1}   jami = {OK + FAIL + 1}")
    sys.exit(1)

_n = [0]
XATO5 = []


def _qayd(r, nima):
    if getattr(r, "status_code", 0) >= 500:
        XATO5.append((nima, r.status_code, getattr(r, "text", "")[:200]))
    return r


def detal(nom, miqdor, narx):
    return {"name": nom, "category": "panel", "width": 50, "thickness": 5, "quantity": miqdor, "unit_price": narx,
            "is_coated": False, "penoplast_id": PENO_ID}


def buyurtma(agreed=None, a=(10, 30_000), b=(5, 20_000)):
    """Yangi buyurtma (alohida loyiha): A (10 × 30 000) + B (5 × 20 000) = 400 000."""
    _n[0] += 1
    k = f"KN{_n[0]}"
    tana = {"project_id": PRJ_ID[_n[0] % len(PRJ_ID)], "order_type": "product",
            "items": [detal(f"{k} A", *a), detal(f"{k} B", *b)]}
    if agreed is not None:
        tana["agreed_amount"] = agreed
    r = _qayd(req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"}), "yaratish")
    d = js(r) or {}
    return (d.get("id") if isinstance(d, dict) else None), k


def kechir(oid, tolanadi):
    """`tolanadi` so'm to'lanadi, qolgan qarz KECHIRILADI (`write_off_remainder=true`)."""
    r = _qayd(req(C, "post", "/api/payments", params={"write_off_remainder": "true"},
                  json={"order_id": oid, "amount": tolanadi, "payment_type": "partial", "payment_method": "naqd"}),
              "kechirish")
    return r.status_code


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        if o is None:
            return {}
        kq = getattr(o, "kechirilgan_qarz", None)
        return {"total": round(float(o.total_amount or 0), 2),
                "agreed": round(float(o.agreed_amount), 2) if o.agreed_amount is not None else None,
                "dp": float(o.discount_percent or 0), "kech": (round(float(kq), 2) if kq is not None else None),
                "debt": round(float(o.debt_amount or 0), 2), "paid": round(float(o.paid_amount or 0), 2)}
    finally:
        s.close()


def detallar(oid):
    s = SessionLocal()
    try:
        return {i.name[-1]: (i.id, float(i.quantity or 0), float(i.unit_price or 0))
                for i in s.query(OrderItem).filter(OrderItem.order_id == oid).all()}
    finally:
        s.close()


def tahrir(oid, k, a=(10, 30_000), b=(5, 20_000), agreed=None):
    """UI `updateOrder` tanasi — `b=None` bo'lsa B olib tashlanadi; `agreed` — faqat QO'LDA yozilganda."""
    s = SessionLocal()
    try:
        prj = s.get(Order, oid).project_id
    finally:
        s.close()
    its = [detal(f"{k} A", *a)] + ([detal(f"{k} B", *b)] if b else [])
    tana = {"project_id": prj, "order_type": "product", "recipe_id": None, "master_id": None, "deadline": None,
            "base_price": None, "loy_kg": None, "items": its}
    if agreed is not None:
        tana["agreed_amount"] = agreed
    return _qayd(req(C, "put", f"/api/orders/{oid}", json=tana, params={"confirm_shortage": "true"}), "tahrir")


def yuk(oid, iid, miqdor):
    return _qayd(req(C, "post", "/api/deliveries", json={
        "order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}], "notes": "KN yuk",
        "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"}), "yuk").status_code


# ══════════════════════════════════════════════════════════════
# A. API
# ══════════════════════════════════════════════════════════════
section("A. API — to'liq tahrir (summasiz — brauzer summani faqat qo'lda yozilganda yuboradi)")
o1, k1 = buyurtma()
r = tahrir(o1, k1, b=None)
h = holat(o1)
check("A1 chegirmasiz, B olib tashlandi: jami 300 000, kelishilgan 300 000, foiz 0",
      r.status_code == 200 and h.get("total") == 300_000 and h.get("agreed") == 300_000 and h.get("dp") == 0, (r.status_code, h))

o2, k2 = buyurtma(agreed=450_000)
r = tahrir(o2, k2, b=None)
h = holat(o2)
check("A2 ustama 450 000: B olib tashlandi — 337 500 (+12.5 % saqlandi), foiz 0",
      r.status_code == 200 and h.get("agreed") == 337_500 and h.get("dp") == 0, (r.status_code, h))

o3, k3 = buyurtma(agreed=360_000)
r = tahrir(o3, k3, a=(15, 30_000))
h = holat(o3)
check("A3 10 % chegirma: A 10 → 15 (jami 550 000) — 495 000, foiz 10",
      r.status_code == 200 and h.get("agreed") == 495_000 and h.get("dp") == 10, (r.status_code, h))

o4, k4 = buyurtma()
kr = kechir(o4, 399_000)
h0 = holat(o4)
check("A4a chegirmasiz, 399 000 to'lab 1 000 kechirildi: kelishilgan 399 000, kechirilgan 1 000, foiz 0",
      kr == 200 and h0.get("agreed") == 399_000 and h0.get("kech") == 1_000 and h0.get("dp") == 0, (kr, h0))
r = tahrir(o4, k4, b=None)
h = holat(o4)
check("A4b B olib tashlandi: 300 000 − 1 000 = 299 000 (kechirilgan so'mda), kechirilgan 1 000",
      r.status_code == 200 and h.get("agreed") == 299_000 and h.get("kech") == 1_000 and h.get("dp") == 0, (r.status_code, h))

o5, k5 = buyurtma(agreed=360_000)
kr = kechir(o5, 358_000)
r = tahrir(o5, k5, a=(15, 30_000))
h = holat(o5)
check("A5 10 % chegirma, 2 000 kechirilgan: A → 15 — 495 000 − 2 000 = 493 000, foiz 10 (narx chegirmasi), qarz 135 000",
      kr == 200 and r.status_code == 200 and h.get("agreed") == 493_000 and h.get("dp") == 10
      and h.get("debt") == 135_000, (kr, r.status_code, h))

r = tahrir(o5, k5, a=(15, 30_000), agreed=420_000)
h = holat(o5)
check("A6 qo'lda 420 000 (kechirilgan 2 000): kelishilgan AYNAN 420 000, foiz — narx (422 000) bo'yicha 23.27",
      r.status_code == 200 and h.get("agreed") == 420_000 and h.get("dp") == round((550_000 - 422_000) / 550_000 * 100, 2),
      (r.status_code, h))

o7, k7 = buyurtma(agreed=360_000)
kechir(o7, 358_000)
r = tahrir(o7, k7)
h = holat(o7)
check("A7 o'zgarishsiz tahrir (chegirma + kechirilgan): kelishilgan 358 000, foiz 10 qoladi (asl: 10.5 — kechirilgan "
      "\"chegirma\"ga qo'shilardi)", r.status_code == 200 and h.get("agreed") == 358_000 and h.get("dp") == 10, (r.status_code, h))

section("A'. Detal tahriri / o'chirish (`PUT` / `DELETE /api/order-items`), qisman «Tayyor»")
o8, k8 = buyurtma(agreed=450_000)
d8 = detallar(o8)
r = _qayd(req(C, "put", f"/api/order-items/{d8['A'][0]}", json={"quantity": 5}), "detal tahriri")
h = holat(o8)
check("A8 ustama 450 000: A 10 → 5 (jami 250 000) — 281 250", r.status_code == 200 and h.get("total") == 250_000
      and h.get("agreed") == 281_250, (r.status_code, h))

o9, k9 = buyurtma()
kechir(o9, 399_000)
d9 = detallar(o9)
r = _qayd(req(C, "delete", f"/api/order-items/{d9['B'][0]}"), "detal o'chirish")
h = holat(o9)
check("A9 chegirmasiz, 1 000 kechirilgan: B o'chirildi — 299 000", r.status_code == 200 and h.get("agreed") == 299_000
      and h.get("kech") == 1_000, (r.status_code, h))

o10, k10 = buyurtma(agreed=450_000)
d10 = detallar(o10)
yk = yuk(o10, d10["A"][0], 5)
r = _qayd(req(C, "post", f"/api/orders/{o10}/ready"), "tayyor")
h = holat(o10)
check("A10 ustama 450 000, qisman «Tayyor» (A 5 / 10, B 0): jami 150 000 — 168 750",
      yk == 200 and r.status_code == 200 and h.get("total") == 150_000 and h.get("agreed") == 168_750, (yk, r.status_code, h))

o11, k11 = buyurtma(agreed=360_000)
kechir(o11, 300_000)
d11 = detallar(o11)
yk = yuk(o11, d11["A"][0], 5)
r = _qayd(req(C, "post", f"/api/orders/{o11}/ready"), "tayyor")
h = holat(o11)
check("A11 10 % chegirma, 60 000 kechirilgan, qisman «Tayyor» (jami 150 000): 135 000 − 60 000 = 75 000",
      yk == 200 and r.status_code == 200 and h.get("agreed") == 75_000 and h.get("kech") == 60_000, (yk, r.status_code, h))

o12, k12 = buyurtma()
kechir(o12, 399_000)
tahrir(o12, k12, a=(15, 30_000))
h1 = holat(o12)
kr = kechir(o12, 149_500)
h2 = holat(o12)
check("A12 kechirish YIG'INDISI: 1 000, tahrir (549 000), yana 500 — kechirilgan 1 500, kelishilgan 548 500, qarz 0",
      h1.get("agreed") == 549_000 and kr == 200 and h2.get("kech") == 1_500 and h2.get("agreed") == 548_500
      and h2.get("debt") == 0, (h1, kr, h2))

o13 = js(req(C, "get", f"/api/orders/{o4}")) or {}
check("A13 GET /api/orders/{id}: `kechirilgan_qarz` = 1 000 (tahrir formasi shundan hisoblaydi)",
      taxminan(o13.get("kechirilgan_qarz"), 1_000), {k: o13.get(k) for k in ("kechirilgan_qarz", "kelishilgan_asl")})

o14, k14 = buyurtma()
kechir(o14, 399_000)
r = _qayd(req(C, "put", f"/api/orders/{o14}/agreed-amount", json={"agreed_amount": 350_000}), "agreed-amount")
h = holat(o14)
check("A14 `/agreed-amount` 350 000 (kechirilgan 1 000): foiz — narx 351 000 bo'yicha 12.25 (asl: 12.5)",
      r.status_code == 200 and h.get("agreed") == 350_000 and h.get("dp") == 12.25, (r.status_code, h))

o15, k15 = buyurtma()
_qayd(req(C, "put", f"/api/orders/{o15}/agreed-amount", json={"agreed_amount": 400_000}), "agreed-amount")
r = tahrir(o15, k15, b=None)
h = holat(o15)
check("A15 yangi buyurtma: kechirilgan 0 (NULL emas), chegirmasiz tahrir — 300 000",
      h.get("kech") == 0 and h.get("agreed") == 300_000, h)

# ══════════════════════════════════════════════════════════════
# M. Migratsiya
# ══════════════════════════════════════════════════════════════
section("M. `main._migrate_kechirilgan_qarz` — eski buyurtmalar (izoh belgisi `[WRITEOFF:N]`)")
MIG = getattr(main, "_migrate_kechirilgan_qarz", None)
check("M0 `main._migrate_kechirilgan_qarz` bor", MIG is not None)


def eski(total, agreed, dp, notes):
    s = SessionLocal()
    try:
        o = Order(company_id=1, order_number=f"KN-ESKI-{_n[0]}-{total}", project_id=PRJ_ID[0],
                  order_type=OrderType.PRODUCT, total_amount=total, agreed_amount=agreed,
                  discount_percent=dp, notes=notes)
        _n[0] += 1
        s.add(o)
        s.commit()
        oid = o.id
    finally:
        s.close()
    with engine.connect() as c:
        c.execute(_sql("UPDATE orders SET kechirilgan_qarz = NULL WHERE id = :i"), {"i": oid})
        c.commit()
    return oid


def kq(oid):
    try:
        with engine.connect() as c:
            v = c.execute(_sql("SELECT kechirilgan_qarz FROM orders WHERE id = :i"), {"i": oid}).scalar()
    except Exception as e:                 # noqa: BLE001 — ustun yo'q (mutatsiya) — test QULAMASIN
        return f"ISTISNO {type(e).__name__}"
    return None if v is None else round(float(v), 2)


_ustun_bor = "kechirilgan_qarz" in {c["name"] for c in _insp(engine).get_columns("orders")}
check("M1 `orders.kechirilgan_qarz` ustuni bor", _ustun_bor)
if _ustun_bor and MIG is not None:
    ma = eski(400_000, 400_000, 0.0, "oddiy izoh")
    mb = eski(1_112_697.6, 1_112_000, 0.0, "planned_loy=0.0 [WRITEOFF:698]")
    mc = eski(2_642_907.5, 2_600_000, 1.18, "planned_loy=0.0 [WRITEOFF:11813]")
    md = eski(400_000, 449_500, 0.0, "ustama [WRITEOFF:500]")
    me = eski(562_320, 550_000, 0.0, None)
    # chegirmali (0.01 %) + kechirilgan: jami − kelishilgan = 100.9 (0.90 chegirma + 100 kechirilgan) — belgidan 1 dan
    # kam farq, lekin narx chegirmasi BOR: aniq qiymat EMAS, belgi olinadi (chegirma kechirilganga aralashmasin)
    mf = eski(10_000, 9_899.10, 0.01, "kichik [WRITEOFF:100]")
    with contextlib.redirect_stdout(_quiet):
        MIG()
    check("M2 belgisiz — 0; izohsiz (NULL) — 0", kq(ma) == 0 and kq(me) == 0, (kq(ma), kq(me)))
    check("M3 chegirmasiz, belgi 698 — ANIQ 697.60 (jami − kelishilgan, belgi yaxlitlangan) — `main` ORD-060-1",
          kq(mb) == 697.6, kq(mb))
    check("M4 chegirmali (1.18 %), belgi 11 813 — 11 813 (`main` ORD-032-1)", kq(mc) == 11_813, kq(mc))
    check("M5 ustamali (jami < kelishilgan), belgi 500 — 500 (aniq qiymat manfiy)", kq(md) == 500, kq(md))
    check("M5b chegirmali (0.01 %), jami − kelishilgan 100.90, belgi 100 — 100 (chegirma kechirilganga aralashmaydi)",
          kq(mf) == 100, kq(mf))
    with engine.connect() as c:
        _oldin = c.execute(_sql("SELECT id, kechirilgan_qarz FROM orders ORDER BY id")).fetchall()
    with contextlib.redirect_stdout(_quiet):
        MIG()
    with engine.connect() as c:
        _keyin = c.execute(_sql("SELECT id, kechirilgan_qarz FROM orders ORDER BY id")).fetchall()
        _null = c.execute(_sql("SELECT COUNT(*) FROM orders WHERE kechirilgan_qarz IS NULL")).scalar()
    check("M6 idempotent: ikkinchi ishga tushish hech narsa o'zgartirmaydi, NULL qolmadi",
          [tuple(x) for x in _oldin] == [tuple(x) for x in _keyin] and _null == 0, (_null, len(_oldin)))
    check("M7 yangi buyurtmalar (API) tegilmagan: A4 — 1 000, A12 — 1 500, A1 — 0",
          kq(o4) == 1_000 and kq(o12) == 1_500 and kq(o1) == 0, (kq(o4), kq(o12), kq(o1)))
    # ustun yo'q baza (eski `main`) — migratsiya o'zi qo'shadi va to'ldiradi
    _tushdi = None
    try:
        with engine.connect() as c:
            c.execute(_sql("ALTER TABLE orders DROP COLUMN kechirilgan_qarz"))
            c.commit()
        _tushdi = "kechirilgan_qarz" not in {x["name"] for x in _insp(engine).get_columns("orders")}
    except Exception as e:                 # noqa: BLE001
        _tushdi = f"ISTISNO {e}"
    with contextlib.redirect_stdout(_quiet):
        MIG()
    _bor = "kechirilgan_qarz" in {x["name"] for x in _insp(engine).get_columns("orders")}
    check("M8 ustun yo'q (eski baza): migratsiya qo'shadi va to'ldiradi (698 → 697.60, 11 813, 0)",
          _tushdi is True and _bor and kq(mb) == 697.6 and kq(mc) == 11_813 and kq(ma) == 0,
          (_tushdi, _bor, kq(mb), kq(mc), kq(ma)))
    try:
        h = holat(o4)
    except Exception as e:                 # noqa: BLE001 — ustun yo'q (mutatsiya) — test QULAMASIN
        h = f"ISTISNO {type(e).__name__}"
    check("M9 qayta to'ldirilgan bazada API buyurtmasi (A4) — izohdagi belgidan 1 000 (jami 300 000, kelishilgan 299 000)",
          kq(o4) == 1_000 and isinstance(h, dict) and h.get("agreed") == 299_000, (kq(o4), h))
else:
    check("M2–M9 o'lchab bo'lmadi", False, (_ustun_bor, MIG is not None))

# ══════════════════════════════════════════════════════════════
# X / S
# ══════════════════════════════════════════════════════════════
section("X. 5xx yo'q")
check("X1 hech bir so'rov 5xx bermadi", not XATO5, XATO5[:5])

section("S. Statik")
_uof = manba(crud, "update_order_full")
_dob = manba(crud, "_detal_ozgargach_buyurtma")
_fin = manba(crud, "finalize_partial_order_quantities")
check("S1 to'liq tahrir, detal tahriri / o'chirish, qisman «Tayyor» — `kelishilgan_qayta_hisob` chaqiradi",
      all("kelishilgan_qayta_hisob(" in x for x in (_uof, _dob, _fin)), [("kelishilgan_qayta_hisob(" in x) for x in (_uof, _dob, _fin)])
check("S2 ularda eski `(1 - … / 100)` foiz formulasi qolmagan",
      not any(("discount_pct / 100" in x) or ("old_discount_pct / 100" in x) or ("eski_chegirma) / 100" in x)
              for x in (_uof, _dob, _fin)))
_upd = js_funksiya(_src, "updateOrder") or ""
_rea = js_funksiya(_src, "reapplyDiscount") or ""
check("S3 orders.html `updateOrder`: summa FAQAT qo'lda yozilgan bo'lsa (`editUserTouched`) yuboriladi",
      "agreed_amount: (editUserTouched && finalPrice) ? finalPrice : undefined" in _upd)
check("S4 `reapplyDiscount`: `kelishilganQayta` + `getNamedTotal` (nomsiz qator kirmaydi), `editDiscountPct` yo'q",
      "kelishilganQayta(" in _rea and "getNamedTotal()" in _rea and "editDiscountPct" not in _src)
_wo = manba(main, "_tolov_qoldigini_chegirmaga")
check("S5 `main._tolov_qoldigini_chegirmaga` kechirilgan summani ustunga QO'SHADI",
      tartibda(_wo, "order.agreed_amount = order.kelishilgan_summa - remaining", "order.kechirilgan_qarz =",
               "order.kechirilgan + remaining"))
check("S6 `crud.create_order` — yangi buyurtma `kechirilgan_qarz=0`", "kechirilgan_qarz=0" in manba(crud, "create_order"))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
