#!/usr/bin/env python3
"""
test_buyurtma_narx_jami.py — kech95 darvozasi (2026-09-27, 117-band + K95-1): buyurtma detali NARXI bazadagidek
2 xonaga (HALF_UP), JAMI shu narxdan; buyurtma jami — detallar jamisining o'nlik yig'indisi; sig'im; detal
tahriri / o'chirilishida kelishilgan summa; "Tayyor" qisman; TM sotuvi tannarxi.

O'LCHANGAN (asl kod = zip 88, SQLite va HAQIQIY PostgreSQL 16 — kech94 `work/probe117.py`, kech95
`work/probe117b.py`):
  * narx `Numeric(12,2)` ga yaxlitlanib yozilardi, jami esa YAXLITLANMAGAN narxdan: `333 × 10.335` → narx
    10.34, jami 3441.56 (10.34 × 333 = 3443.22); `7 × 0.125` → SQLite 0.12 / PG 0.13, jami 0.88; 3 detalli
    buyurtma jami detallar jamisidan 1 tiyin farq (7146.13 ↔ 7146.14) — yaratish, to'liq tahrir, detal tahriri;
  * K95-1: jami `Numeric(12,2)` sig'imidan oshsa (9 999 999 999.99 × 2; 6e9 + 6e9) PG da 500 (SQLite 200);
  * `PUT` / `DELETE /api/order-items` kelishilgan summaga UMUMAN tegmasdi (12 000 → jami 6 000, kelishilgan
    12 000 qolardi);
  * "Tayyor" qisman: jami "eski jami × ulush" — narx × topshirilgan bilan mos emas (10.335 × 333, 100 → 1033.50
    ↔ 1034.00); profilda narx butun uzunlikniki qolib, `check_financial_consistency` yolg'on
    "order_total_mismatch" berardi;
  * TM sotuvi: PG da 10.01 li mahsulotning yarmi sotilganda tannarx 5.01 + 5.01 = 10.02 (1 tiyin paydo
    bo'lardi), SQLite da 5.00 + 5.00; javobdagi `profit` 14.995000000000001;
  * Donalik (eski usul, hajm narxdan) o'zgarishsiz qayta saqlansa penoplast qoldig'i tiyin hajm farqiga
    o'zgarardi (yangi holat XOM narxdan, eski holat bazadan — 2 xona).

Bo'limlar: A — yaratish; B — to'liq tahrir; C — detal tahriri; D — detal o'chirish; E — sig'im (K95-1);
F — "Tayyor" qisman; G — TM sotuvi; H — Donalik tahriri ombori; P — brauzer (`orders.html` `buyurtmaJami`) ↔
server paritet (node); X — 5xx yo'q; S — statik.

Ishlatish:
    python3 tools/test_buyurtma_narx_jami.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_buyurtma_narx_jami.py
"""
import os
import sys
import json
import random
import inspect
import tempfile
import subprocess
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "buyurtma_narx_jami_test"
_T = tempfile.mkdtemp(prefix="bnj_")
_DB = os.path.join(_T, "buyurtma_narx_jami_test.db")

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

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, Project, Order, OrderItem, FinishedProduct,   # noqa: E402
                    FinishedProductSale, StockSource, ProductionStatus)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HOLATLAR = []


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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:400]}")


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
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    HOLATLAR.append((metod.upper() + " " + url.split("?")[0], r.status_code))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ── MUSTAQIL etalon (kod emas — qoida): narx 2 xonaga HALF_UP, jami SHU narxdan ──
def d2(x):
    return Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def kutilgan(miqdor, narx):
    n2 = d2(narx)
    return float(n2), float((Decimal(repr(float(miqdor))) * n2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ── fikstura ──
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "bnj_admin", "Parol123!", UserRole.ADMIN, "BNJ", company_id=1)
PRJ = [Project(company_id=1, client_name=f"BNJ mijoz {i}", project_name=f"BNJ loyiha {i}", total_budget=0,
               total_paid=0) for i in range(80)]
PENO = Inventory(company_id=1, item_name="BNJ Penoplast", unit="blok", stock_quantity=1e7, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
s.add_all(PRJ + [PENO])
s.commit()
PRJ_ID = [p.id for p in PRJ]
PENO_ID = PENO.id
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r = C.post("/login", data={"username": "bnj_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _r.status_code in (302, 303), _r.status_code)
_PI = [0]


def yangi_loyiha():
    _PI[0] += 1
    return PRJ_ID[_PI[0]]


def detal(nom, narx, miqdor, kat="panel", **kw):
    d = {"name": nom, "category": kat, "width": 20, "thickness": 10, "quantity": miqdor, "unit_price": narx,
         "is_coated": False, "penoplast_id": PENO_ID}
    if kat == "profil":
        d["length"] = kw.pop("length", 10)
    d.update(kw)
    return d


def yarat(items, **kw):
    pid = yangi_loyiha()
    tana = {"project_id": pid, "order_type": "product", "items": items}
    tana.update(kw)
    r = req(C, "post", "/api/orders", json=tana)
    return r, (js(r) or {}).get("id") if isinstance(js(r), dict) else None, pid


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid) if oid else None
        if o is None:
            return None
        its = s.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()
        return {"total": float(o.total_amount or 0), "agreed": float(o.agreed_amount or 0),
                "disc": float(o.discount_percent or 0),
                "items": [{"id": i.id, "narx": float(i.unit_price or 0), "miqdor": float(i.quantity or 0),
                           "uzunlik": float(i.length or 0), "jami": float(i.total_price or 0)} for i in its]}
    finally:
        s.close()


def sanoq():
    s = SessionLocal()
    try:
        return s.query(Order).count(), s.query(OrderItem).count()
    finally:
        s.close()


def penoplast_qoldiq():
    s = SessionLocal()
    try:
        return float(s.get(Inventory, PENO_ID).stock_quantity)
    finally:
        s.close()


HOLLAR = [("1234.565 x 3", 1234.565, 3), ("10.335 x 333", 10.335, 333), ("0.125 x 7", 0.125, 7),
          ("800.005 x 1", 800.005, 1), ("5000.5 x 2", 5000.5, 2), ("333.333 x 3", 333.333, 3),
          ("1234.56 x 3", 1234.56, 3), ("3997.125 x 34", 3997.125, 34), ("571428.5714 x 7", 1000000 / 1.75, 7)]

# ════════════════════════════════════════════════════════════════════════════
section("A. Yaratish (POST /api/orders): narx 2 xona, jami SHU narxdan, buyurtma jami = detallar jamisi")
for nom, narx, miq in HOLLAR:
    r, oid, _ = yarat([detal("A " + nom, narx, miq)])
    h = holat(oid)
    kn, kj = kutilgan(miq, narx)
    ok = r.status_code == 200 and h is not None
    check(f"A {nom}: narx {kn}, jami {kj}, buyurtma jami va kelishilgan = {kj}",
          ok and h["items"][0]["narx"] == kn and h["items"][0]["jami"] == kj and h["total"] == kj
          and h["agreed"] == kj, (r.status_code, h))
r, oid, _ = yarat([detal("A3a", 1234.565, 3), detal("A3b", 10.335, 333), detal("A3c", 0.125, 7)])
h = holat(oid)
_k = [kutilgan(3, 1234.565)[1], kutilgan(333, 10.335)[1], kutilgan(7, 0.125)[1]]
_ks = float(sum(Decimal(repr(x)) for x in _k))
check(f"A 3 detal: detallar jami {_k}, buyurtma jami = yig'indi {_ks} (asl kodda 7146.12 / 7146.13)",
      r.status_code == 200 and h and [i["jami"] for i in h["items"]] == _k and h["total"] == _ks
      and h["agreed"] == _ks, (r.status_code, h))
r, oid, _ = yarat([detal("A4", 1000, 1)], agreed_amount=800.005)
h = holat(oid)
check("A kelishilgan summa 800.005 → 800.01 (HALF_UP, SQLite = PG), chegirma foizi shundan",
      r.status_code == 200 and h and h["agreed"] == 800.01 and h["disc"] == 20.0, (r.status_code, h))

# ════════════════════════════════════════════════════════════════════════════
section("B. To'liq tahrir (PUT /api/orders/{id})")
r, oid, pid = yarat([detal("B1", 100, 1)])
r = req(C, "put", f"/api/orders/{oid}", json={"project_id": pid, "order_type": "product",
                                               "items": [detal("B1", 10.335, 333)]})
h = holat(oid)
kn, kj = kutilgan(333, 10.335)
check(f"B tahrir 10.335 x 333 → narx {kn}, jami {kj}, buyurtma jami {kj} (asl: 3441.56)",
      r.status_code == 200 and h and h["items"][0]["narx"] == kn and h["items"][0]["jami"] == kj
      and h["total"] == kj, (r.status_code, r.text[:200], h))
r = req(C, "put", f"/api/orders/{oid}", json={"project_id": pid, "order_type": "product",
                                               "items": [detal("B1", 10.335, 333), detal("B2", 0.125, 7)],
                                               "agreed_amount": 3000.005})
h = holat(oid)
_ks = float(Decimal(repr(kj)) + Decimal(repr(kutilgan(7, 0.125)[1])))
check(f"B yangi detal + kelishilgan 3000.005 → jami {_ks}, kelishilgan 3000.01",
      r.status_code == 200 and h and h["total"] == _ks and h["agreed"] == 3000.01, (r.status_code, h))
r, oid, pid = yarat([detal("B3", 6228752.75, 1)])
r = req(C, "put", f"/api/orders/{oid}", json={"project_id": pid, "order_type": "product",
                                               "items": [detal("B3", 6228752.75, 1)], "agreed_amount": 6228752.75})
h = holat(oid)
check("B kelishilgan 6 228 752.75 AYNAN saqlanadi (brauzer endi aniq yuboradi — 124)",
      r.status_code == 200 and h and h["agreed"] == 6228752.75 and h["total"] == 6228752.75, (r.status_code, h))

# ════════════════════════════════════════════════════════════════════════════
section("C. Detal tahriri (PUT /api/order-items/{id}): qoida + kelishilgan summa")
r, oid, _ = yarat([detal("C1", 100, 1)])
h = holat(oid)
r = req(C, "put", f"/api/order-items/{h['items'][0]['id']}", json={"unit_price": 10.335, "quantity": 333})
h = holat(oid)
check(f"C 10.335 x 333 → narx {kn}, jami {kj}, buyurtma jami {kj}; chegirmasiz → kelishilgan = jami",
      r.status_code == 200 and h and h["items"][0]["narx"] == kn and h["items"][0]["jami"] == kj
      and h["total"] == kj and h["agreed"] == kj, (r.status_code, h))
r, oid, _ = yarat([detal("C2a", 1000, 10), detal("C2b", 500, 4)])
h0 = holat(oid)
r = req(C, "put", f"/api/order-items/{h0['items'][0]['id']}", json={"quantity": 6})
h = holat(oid)
check("C chegirmasiz 12 000: detal 10 → 6 → jami 8 000, kelishilgan 8 000 (asl: 12 000 qolardi)",
      r.status_code == 200 and h and h["total"] == 8000 and h["agreed"] == 8000 and h["disc"] == 0, (r.status_code, h))
r, oid, _ = yarat([detal("C3a", 1000, 10), detal("C3b", 500, 4)], agreed_amount=9600)
h0 = holat(oid)
r = req(C, "put", f"/api/order-items/{h0['items'][0]['id']}", json={"quantity": 6})
h = holat(oid)
check("C 20 % chegirmali (12 000 → 9 600): detal 10 → 6 → jami 8 000, kelishilgan 6 400, foiz 20",
      r.status_code == 200 and h and h["total"] == 8000 and h["agreed"] == 6400 and h["disc"] == 20.0,
      (r.status_code, h))
r = req(C, "put", f"/api/order-items/{h0['items'][0]['id']}", json={"notes": "faqat izoh"})
h2 = holat(oid)
check("C jami o'zgarmagan tahrir → kelishilgan summa O'ZGARMAYDI (6 400)",
      r.status_code == 200 and h2 and h2["agreed"] == 6400 and h2["total"] == 8000, (r.status_code, h2))
r, oid, _ = yarat([detal("C4", 1000, 12)], agreed_amount=13000)
h0 = holat(oid)
r = req(C, "put", f"/api/order-items/{h0['items'][0]['id']}", json={"notes": "faqat izoh"})
h2 = holat(oid)
check("C ustamali (jami 12 000, kelishilgan 13 000): jami o'zgarmagan tahrir → 13 000 qoladi",
      r.status_code == 200 and h2 and h2["agreed"] == 13000 and h2["total"] == 12000, (r.status_code, h2))

# ════════════════════════════════════════════════════════════════════════════
section("D. Detal o'chirish (DELETE /api/order-items/{id}): kelishilgan summa")
r, oid, _ = yarat([detal("D1a", 1000, 6), detal("D1b", 500, 4)])
h0 = holat(oid)
r = req(C, "delete", f"/api/order-items/{h0['items'][1]['id']}")
h = holat(oid)
check("D chegirmasiz 8 000: 2 000 li detal o'chirildi → jami 6 000, kelishilgan 6 000 (asl: 8 000 qolardi)",
      r.status_code == 200 and h and h["total"] == 6000 and h["agreed"] == 6000, (r.status_code, h))
r, oid, _ = yarat([detal("D2a", 1000, 6), detal("D2b", 500, 4)], agreed_amount=6400)
h0 = holat(oid)
r = req(C, "delete", f"/api/order-items/{h0['items'][1]['id']}")
h = holat(oid)
check("D 20 % chegirmali (8 000 → 6 400): o'chirishdan keyin jami 6 000, kelishilgan 4 800",
      r.status_code == 200 and h and h["total"] == 6000 and h["agreed"] == 4800 and h["disc"] == 20.0,
      (r.status_code, h))

# ════════════════════════════════════════════════════════════════════════════
section("E. K95-1 — sig'im (Numeric(12,2)): aniq 400, hech narsa yozilmaydi, 5xx yo'q")
MAX = 9_999_999_999.99
for nom, items in [("detal MAX x 2", [detal("E1", MAX, 2)]),
                   ("6e9 + 6e9 (buyurtma jami)", [detal("E2a", 6e9, 1), detal("E2b", 6e9, 1)])]:
    s0 = sanoq()
    r, _, _ = yarat(items)
    check(f"E yaratish {nom} → 400 'juda katta', buyurtma / detal qo'shilmadi",
          r.status_code == 400 and "juda katta" in r.text and sanoq() == s0, (r.status_code, r.text[:200]))
s0 = sanoq()
r, oid, _ = yarat([detal("E3", 5e9, 1.9999999999)])
h = holat(oid)
check("E chegarada: 5e9 x 1.9999999999 → 200, jami 9 999 999 999.50",
      r.status_code == 200 and h and h["total"] == 9999999999.5, (r.status_code, h))
r, oid, pid = yarat([detal("E4", 100, 1)])
h0 = holat(oid)
r = req(C, "put", f"/api/orders/{oid}", json={"project_id": pid, "order_type": "product",
                                               "items": [detal("E4", MAX, 2)]})
check("E to'liq tahrir MAX x 2 → 400 'juda katta', buyurtma o'zgarmadi",
      r.status_code == 400 and "juda katta" in r.text and holat(oid) == h0, (r.status_code, r.text[:200]))
r = req(C, "put", f"/api/order-items/{h0['items'][0]['id']}", json={"quantity": 2, "unit_price": MAX})
check("E detal tahriri MAX x 2 → 400 'juda katta', detal o'zgarmadi",
      r.status_code == 400 and "juda katta" in r.text and holat(oid) == h0, (r.status_code, r.text[:200]))
r, oid, _ = yarat([detal("E5a", 5e9, 1), detal("E5b", 4e9, 1)])
h0 = holat(oid)
r = req(C, "put", f"/api/order-items/{h0['items'][1]['id']}" if h0 else "/api/order-items/0",
        json={"unit_price": 6e9})
check("E detal tahriri buyurtma jamisini sig'imdan oshiradi (5e9 + 6e9) → 400, o'zgarmadi",
      h0 is not None and r.status_code == 400 and "juda katta" in r.text and holat(oid) == h0,
      (r.status_code, r.text[:200]))
s0 = sanoq()
r, _, _ = yarat([detal("E7", 1, 1e30)])
check("E miqdor 1e30 × narx 1 → 400 'juda katta' (o'nlik yaxlitlash qulamaydi), hech narsa yozilmadi",
      r.status_code == 400 and "juda katta" in r.text and sanoq() == s0, (r.status_code, r.text[:200]))
s0 = sanoq()
r = req(C, "post", "/api/orders", content=('{"project_id": %d, "order_type": "product", "items": [{"name": "E6", '
                                            '"category": "panel", "width": 20, "thickness": 10, "quantity": Infinity, '
                                            '"unit_price": 0, "penoplast_id": %d}]}' % (yangi_loyiha(), PENO_ID)),
        headers={"Content-Type": "application/json"})
check("E miqdor Infinity → 4xx, hech narsa yozilmadi (5xx yo'q)",
      400 <= r.status_code < 500 and sanoq() == s0, (r.status_code, r.text[:200]))


# ════════════════════════════════════════════════════════════════════════════
section("F. \"Tayyor\" qisman (finalize_partial_order_quantities)")


def qisman_tayyor(items, bering):
    r, oid, _ = yarat(items)
    req(C, "post", f"/api/orders/{oid}/activate")
    h = holat(oid)
    yuk = [{"order_item_id": h["items"][i]["id"], "quantity": q} for i, q in bering]
    ry = req(C, "post", "/api/deliveries", json={"order_id": oid, "items": yuk, "notes": "bnj",
                                                  "transport_cost": 0, "transport_payer": "none",
                                                  "payment_method": "naqd"})
    rt = req(C, "post", f"/api/orders/{oid}/ready")
    return oid, ry.status_code, rt.status_code, h, holat(oid)


oid, ys, ts, h0, h = qisman_tayyor([detal("F1", 10.335, 333)], [(0, 100)])
check("F panel 10.335 x 333, 100 topshirildi → narx 10.34, jami 1 034.00 (asl: 1 033.50), buyurtma jami 1 034.00",
      ys == 200 and ts == 200 and h and h["items"][0]["jami"] == 1034.0 and h["items"][0]["narx"] == 10.34
      and h["total"] == 1034.0 and h["agreed"] == 1034.0, (ys, ts, h))
oid, ys, ts, h0, h = qisman_tayyor([detal("F2", 3997.125, 34)], [(0, 7)])
_kj7 = kutilgan(7, 3997.125)[1]
check(f"F 3997.125 x 34, 7 topshirildi → jami {_kj7} (narx x topshirilgan; SQLite = PG)",
      ys == 200 and ts == 200 and h and h["items"][0]["jami"] == _kj7 and h["total"] == _kj7, (ys, ts, h))
oid, ys, ts, h0, h = qisman_tayyor([detal("F3", 100000, 1, kat="profil", length=10)], [(0, 4)])
s = SessionLocal()
try:
    _iss = crud.check_financial_consistency(s, company_id=1)
except Exception as e:                     # noqa: BLE001
    _iss = {"issues": [{"type": "order_total_mismatch", "label": f"xato {e}"}]}
finally:
    s.close()
_raqam = None
s = SessionLocal()
try:
    _o = s.get(Order, oid)
    _raqam = _o.order_number if _o else None
finally:
    s.close()
_mis = [x for x in (_iss.get("issues") or []) if x.get("type") == "order_total_mismatch"
        and _raqam and _raqam in str(x.get("label"))]
check("F profil 10 m, 4 m topshirildi → narx 40 000 (butun uzunlik narxi qolmaydi), jami 40 000, "
      "muvofiqlik tekshiruvida 'order_total_mismatch' YO'Q",
      ys == 200 and ts == 200 and h and h["items"][0]["narx"] == 40000 and h["items"][0]["jami"] == 40000
      and h["items"][0]["uzunlik"] == 4 and not _mis, (ys, ts, h, _mis))
oid, ys, ts, h0, h = qisman_tayyor([detal("F4a", 10.335, 10), detal("F4b", 1234.565, 3)], [(0, 10), (1, 1)])
check("F 2 detal: to'liq topshirilgani O'ZGARMAYDI, qismani narx x topshirilgan; buyurtma jami = yig'indi",
      ys == 200 and ts == 200 and h and h["items"][0] == h0["items"][0]
      and h["items"][1]["jami"] == kutilgan(1, 1234.565)[1]
      and h["total"] == float(Decimal(repr(h0["items"][0]["jami"])) + Decimal(repr(kutilgan(1, 1234.565)[1]))),
      (ys, ts, h0, h))
r, oid, _ = yarat([detal("F6a", 10.335, 333), detal("F6b", 1234.565, 3)])
req(C, "post", f"/api/orders/{oid}/activate")
h0 = holat(oid)
s = SessionLocal()
try:   # eski buyurtma: jami eski qoida bilan (xom narxdan) — Core bilan yoziladi
    s.execute(OrderItem.__table__.update().where(OrderItem.id == h0["items"][0]["id"]).values(total_price=3441.56))
    s.execute(Order.__table__.update().where(Order.id == oid).values(total_amount=3441.56 + 3703.71,
                                                                      agreed_amount=3441.56 + 3703.71))
    s.commit()
finally:
    s.close()
ry = req(C, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": h0["items"][0]["id"], "quantity": 333},
                                                                         {"order_item_id": h0["items"][1]["id"], "quantity": 1}],
                                              "notes": "bnj", "transport_cost": 0, "transport_payer": "none",
                                              "payment_method": "naqd"})
rt = req(C, "post", f"/api/orders/{oid}/ready")
h = holat(oid)
check("F eski qoidali (3 441.56) TO'LIQ topshirilgan detal qisman \"Tayyor\" da O'ZGARMAYDI",
      ry.status_code == 200 and rt.status_code == 200 and h and h["items"][0]["jami"] == 3441.56
      and h["items"][1]["jami"] == kutilgan(1, 1234.565)[1], (ry.status_code, rt.status_code, h))
oid, ys, ts, h0, h = qisman_tayyor([detal("F5", 1000.01, 3)], [(0, 1)])
check("F chegirmasiz qisman: kelishilgan = yangi jami (2 xona)", ts == 200 and h and h["agreed"] == h["total"] == 1000.01,
      (ts, h))


# ════════════════════════════════════════════════════════════════════════════
section("G. TM sotuvi: tannarx saqlanadi (sotuv + qolgan = asl), foyda bazadagi summalardan")


def tm(nom, cost, qty, narx):
    s = SessionLocal()
    fp = FinishedProduct(company_id=1, name=nom, category="dona", quantity=qty, produced_quantity=qty, unit="dona",
                         unit_price=narx, cost_price=cost, source=StockSource.PRODUCED, is_coated=False,
                         production_status=ProductionStatus.READY)
    s.add(fp)
    s.commit()
    i = fp.id
    s.close()
    return i


def tm_holat(fid):
    s = SessionLocal()
    try:
        fp = s.get(FinishedProduct, fid)
        sl = s.query(FinishedProductSale).filter(FinishedProductSale.finished_product_id == fid).all()
        return float(fp.cost_price or 0), [(float(x.total_amount), float(x.cost_amount or 0)) for x in sl]
    finally:
        s.close()


for nom, cost, qty, sot, narx in [("10.01 / 2, 1 sotildi", 10.01, 2, 1, 20), ("10000 / 3, 1 sotildi", 10000, 3, 1, 5000),
                                  ("1000.03 / 7, 3 sotildi", 1000.03, 7, 3, 300), ("0.05 / 2, 1 sotildi", 0.05, 2, 1, 1),
                                  ("0.2 / 2, 1 sotildi, 0.3 (float 0.3 - 0.1 = 0.19999999999999998)", 0.2, 2, 1, 0.3)]:
    fid = tm("G " + nom, cost, qty, narx)
    r = req(C, "post", "/api/finished/sell", json={"finished_product_id": fid, "quantity": sot, "unit_price": narx,
                                                   "buyer_name": "bnj", "payment_method": "naqd",
                                                   "confirm_below_cost": True})
    d = js(r) if isinstance(js(r), dict) else {}
    qolgan, sotuvlar = tm_holat(fid)
    _sc = sotuvlar[0][1] if sotuvlar else None
    _st = sotuvlar[0][0] if sotuvlar else None
    check(f"G {nom}: sotuv tannarxi + qolgan = {cost}; profit = jami − tannarx (2 xona)",
          r.status_code == 200 and sotuvlar and float(Decimal(repr(_sc)) + Decimal(repr(qolgan))) == cost
          and d.get("profit") == float(Decimal(repr(_st)) - Decimal(repr(_sc))),
          (r.status_code, d, qolgan, sotuvlar))
f1, f2 = tm("G savatcha 1", 10.01, 2, 20), tm("G savatcha 2", 1000.03, 7, 300)
r = req(C, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": f1, "quantity": 1, "unit_price": 20},
                                                               {"finished_product_id": f2, "quantity": 3, "unit_price": 300}],
                                                     "buyer_name": "bnj", "payment_method": "naqd", "agreed_amount": None,
                                                     "master_id": None, "confirm_below_cost": True})
q1, s1 = tm_holat(f1)
q2, s2 = tm_holat(f2)
check("G savatcha: har mahsulotda sotuv tannarxi + qolgan = asl (10.01, 1000.03)",
      r.status_code == 200 and s1 and s2 and float(Decimal(repr(s1[0][1])) + Decimal(repr(q1))) == 10.01
      and float(Decimal(repr(s2[0][1])) + Decimal(repr(q2))) == 1000.03, (r.status_code, r.text[:200], q1, s1, q2, s2))

# ════════════════════════════════════════════════════════════════════════════
section("H. Donalik (eski usul, hajm narxdan) o'zgarishsiz qayta saqlansa ombor o'zgarmaydi")
_dh = {"name": "H1 Donalik", "category": "dona", "quantity": 34, "unit_price": 3997.125, "is_coated": False,
       "penoplast_id": PENO_ID, "price_per_m3": 1000000.25, "unit_price_for_volume": 3997.125}
r, oid, pid = yarat([dict(_dh)])
q0 = penoplast_qoldiq()
r2 = req(C, "put", f"/api/orders/{oid}", json={"project_id": pid, "order_type": "product", "items": [dict(_dh)]})
q1 = penoplast_qoldiq()
check("H o'zgarishsiz to'liq tahrir → penoplast qoldig'i AYNAN (nazorat: farq ombor chegarasidan kichik)",
      r.status_code == 200 and r2.status_code == 200 and q1 == q0, (r.status_code, r2.status_code, q0, q1, q1 - q0))
h = holat(oid)
r3 = req(C, "put", f"/api/order-items/{h['items'][0]['id']}" if h else "/api/order-items/0",
         json={"unit_price": 3997.125, "unit_price_for_volume": 3997.125, "price_per_m3": 1000000.25})
q2 = penoplast_qoldiq()
check("H o'zgarishsiz detal tahriri → penoplast qoldig'i AYNAN", r3.status_code == 200 and q2 == q1,
      (r3.status_code, q1, q2, q2 - q1))
# Yuqoridagi holatda farq (34 × 0.005 / 1 000 000.25 m3) `adjust_inventory_diff` ning 0.0001 m3 chegarasidan
# kichik — asl kodda ham ko'rinmaydi. Mexanizm "1 m3 narxi" kichik bo'lganda ko'rinadi (34 × 0.005 / 10 = 0.017 m3):
_dh2 = dict(_dh, name="H2 Donalik", price_per_m3=10)
r, oid, pid = yarat([dict(_dh2)])
q0 = penoplast_qoldiq()
r2 = req(C, "put", f"/api/orders/{oid}", json={"project_id": pid, "order_type": "product", "items": [dict(_dh2)]})
q1 = penoplast_qoldiq()
check("H \"1 m3 narxi\" 10: o'zgarishsiz to'liq tahrir → penoplast qoldig'i AYNAN (asl: 0.017 m3 farq)",
      r.status_code == 200 and r2.status_code == 200 and q1 == q0, (r.status_code, r2.status_code, q0, q1, q1 - q0))
h = holat(oid)
r3 = req(C, "put", f"/api/order-items/{h['items'][0]['id']}" if h else "/api/order-items/0",
         json={"unit_price": 3997.125, "unit_price_for_volume": 3997.125, "price_per_m3": 10})
q2 = penoplast_qoldiq()
check("H \"1 m3 narxi\" 10: o'zgarishsiz detal tahriri → penoplast qoldig'i AYNAN", r3.status_code == 200 and q2 == q1,
      (r3.status_code, q1, q2, q2 - q1))
_dh3 = {k: v for k, v in _dh2.items() if k != "unit_price_for_volume"}
_dh3["name"] = "H3 Donalik"
r, oid, pid = yarat([dict(_dh3)])
q0 = penoplast_qoldiq()
r2 = req(C, "put", f"/api/orders/{oid}", json={"project_id": pid, "order_type": "product", "items": [dict(_dh3)]})
q1 = penoplast_qoldiq()
check("H hajm narxi (unit_price_for_volume) siz, \"1 m3 narxi\" 10: o'zgarishsiz tahrir → qoldiq AYNAN",
      r.status_code == 200 and r2.status_code == 200 and q1 == q0, (r.status_code, r2.status_code, q0, q1, q1 - q0))
# API "1 m3 narxi" ni 3 xona bilan berishi mumkin (UI — 2 xona): 10.125 → PG 10.13, SQLite bankir 10.12 (yozishda _pul2 bo'lmasa). Yangi holat bazaga yoziladigan
# qiymat bilan (2 xona) hisoblanmasa, o'zgarishsiz tahrir hajmni 3997.13 / 10.125 ↔ / 10.13 farqiga o'zgartiradi.
_dh4 = {k: v for k, v in _dh.items() if k != "unit_price_for_volume"}
_dh4.update(name="H4 Donalik", price_per_m3=10.125)
r, oid, pid = yarat([dict(_dh4)])
q0 = penoplast_qoldiq()
r2 = req(C, "put", f"/api/orders/{oid}", json={"project_id": pid, "order_type": "product", "items": [dict(_dh4)]})
q1 = penoplast_qoldiq()
check("H \"1 m3 narxi\" 10.125 (API, aniq teng yarim — SQLite bankir o'qiydi): o'zgarishsiz tahrir → penoplast qoldig'i AYNAN",
      r.status_code == 200 and r2.status_code == 200 and q1 == q0, (r.status_code, r2.status_code, q0, q1, q1 - q0))
q_oldin = penoplast_qoldiq()
_dh5 = dict(_dh4, name="H5 Donalik")
r, oid, pid = yarat([dict(_dh5)])
q_keyin = penoplast_qoldiq()
r2 = req(C, "delete", f"/api/orders/{oid}")
q_qaytdi = penoplast_qoldiq()
check("H yaratish (1 m3 narxi 10.125) → o'chirish: penoplast AYNAN qaytadi (yechilgani bazadagi 2 xonali qiymatdan)",
      r.status_code == 200 and r2.status_code == 200 and q_keyin < q_oldin and abs(q_qaytdi - q_oldin) < 1e-6,
      (r.status_code, r2.status_code, q_oldin, q_keyin, q_qaytdi, q_qaytdi - q_oldin))

# ════════════════════════════════════════════════════════════════════════════
section("P. Brauzer (orders.html buyurtmaJami) ↔ server (_buyurtma_narx_jami) — node, 4 000 holat")


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


_src = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_fn = [js_funksiya(_src, n) for n in ("_onlikQism", "_tiyinHalfUp", "buyurtmaJami")]
check("P orders.html da _onlikQism / _tiyinHalfUp / buyurtmaJami bor", all(_fn), [bool(x) for x in _fn])
_rnd = random.Random(95117)
HOLAT_P = [(q, n) for _, n, q in HOLLAR]
for _ in range(4000):
    tur = _rnd.random()
    if tur < 0.3:
        n = round(_rnd.uniform(0, 5_000_000), _rnd.choice([0, 1, 2, 3, 4]))
    elif tur < 0.5:
        n = int(_rnd.uniform(0, 1_000_000)) + _rnd.choice([0.005, 0.015, 0.125, 0.335, 0.565, 0.995, 0.4999])
    elif tur < 0.7:
        n = _rnd.uniform(0, 100_000) / _rnd.choice([1, 1.75, 3, 7, 13])
    else:
        n = _rnd.uniform(0, 2_000_000) * _rnd.random() / _rnd.choice([2, 3, 6])
    q = _rnd.choice([1, 2, 3, 7, 34, 333, 0.5, 1.75, 12.345, 0.001, 1e-7, 1e-5, 250.25,
                     round(_rnd.uniform(0.01, 5000), _rnd.choice([0, 1, 2, 3]))])
    HOLAT_P.append((q, n))
_py = []
for q, n in HOLAT_P:
    try:
        _py.append(list(crud._buyurtma_narx_jami(q, n)))
    except Exception:                      # noqa: BLE001
        _py.append(list(kutilgan(q, n)))
_node_natija = None
if all(_fn):
    _kod = "\n".join(_fn) + """
const kirish = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(kirish.map(([q, n]) => { const r = buyurtmaJami(q, n); return [r.narx, r.jami]; })));
"""
    _jf = os.path.join(_T, "paritet.js")
    open(_jf, "w", encoding="utf-8").write(_kod)
    try:
        _p = subprocess.run(["node", _jf], input=json.dumps(HOLAT_P), capture_output=True, text=True, timeout=120)
        _node_natija = json.loads(_p.stdout) if _p.returncode == 0 else None
        if _node_natija is None:
            print("   node:", _p.stderr[:400])
    except Exception as e:                 # noqa: BLE001
        print("   node ishlamadi:", e)
check("P node ishladi", _node_natija is not None and len(_node_natija) == len(HOLAT_P))
if _node_natija is not None and len(_node_natija) == len(HOLAT_P):
    _farq = [(HOLAT_P[i], _py[i], _node_natija[i]) for i in range(len(HOLAT_P)) if _py[i] != _node_natija[i]]
    _etalon_farq = [(HOLAT_P[i], _py[i]) for i in range(len(HOLAT_P)) if _py[i] != list(kutilgan(*HOLAT_P[i]))]
    check(f"P {len(HOLAT_P)} holatda brauzer narx / jami = server AYNAN", not _farq, _farq[:5])
    check("P server = mustaqil etalon (HALF_UP, jami narx2 dan)", not _etalon_farq, _etalon_farq[:5])
    check("P chegara holatlari: 10.335 x 333 → [10.34, 3443.22]; 0.125 x 7 → [0.13, 0.91]; 1e6/1.75 x 7 → 3 999 999.99",
          _node_natija[1] == [10.34, 3443.22] and _node_natija[2] == [0.13, 0.91] and _node_natija[8][1] == 3999999.99,
          (_node_natija[1], _node_natija[2], _node_natija[8]))

# ════════════════════════════════════════════════════════════════════════════
section("X. 5xx yo'q")
_5xx = [h for h in HOLATLAR if h[1] >= 500]
check("X hech bir so'rov 5xx / istisno bermadi", not _5xx, _5xx[:8])

# ════════════════════════════════════════════════════════════════════════════
section("S. Statik")


def manba(mod, nom):
    try:
        return inspect.getsource(getattr(mod, nom))
    except Exception:                      # noqa: BLE001
        return ""


_co, _uo = manba(crud, "create_order"), manba(crud, "update_order_full")
_ui, _di, _fi = manba(crud, "update_order_item"), manba(crud, "delete_order_item"), \
    manba(crud, "finalize_partial_order_quantities")
check("S1 create / to'liq tahrir: jami _buyurtma_narx_jami + _pul_yigindi; xom ko'paytma yo'q",
      "_buyurtma_narx_jami(item_data.quantity, item_data.unit_price)" in _co and "_pul_yigindi(_jamilar)" in _co
      and "item_data.unit_price * item_data.quantity" not in _co
      and _uo.count("_buyurtma_narx_jami(nd.quantity or 1, nd.unit_price or 0)") == 2
      and "* float(nd.quantity or 1)" not in _uo, "")
# kech110 (K110-1): `_detal_ozgargach_buyurtma` endi eski chegirma FOIZINI (2 xonaga yaxlitlangan) olmaydi — eski
# kelishilgan summani o'zi o'qiydi (`crud.kelishilgan_qayta_hisob`, nisbat); tekshiruv ma'nosi AYNAN.
check("S2 detal tahriri / o'chirish: _detal_ozgargach_buyurtma; sig'im tekshiruvi yozishdan OLDIN",
      "_detal_ozgargach_buyurtma(db, order, _eski_jami117)" in _ui
      and "_detal_ozgargach_buyurtma(db, order, _eski_jami117)" in _di
      and 0 <= _ui.find("_buyurtma_sigim_tekshir(") < _ui.find("setattr(db_item, field, value)"), "")
check("S3 finalize: narx x topshirilgan (_buyurtma_narx_jami), 'old_total * fraction, 2)' yo'q",
      "_buyurtma_narx_jami(delivered, item.unit_price or 0)" in _fi and "round(old_total * fraction, 2)" not in _fi, "")
_mr = manba(main, "api_create_order")
check("S4 yaratish marshruti sig'imni 400 bilan (yetishmovchilik tekshiruvidan OLDIN) tekshiradi",
      0 <= _mr.find("crud._buyurtma_sigim_tekshir(order.items)") < _mr.find("check_inventory_for_order"), "")

print("\n" + "=" * 66)
print(f"REJIM: {'PostgreSQL' if PG_URL else 'SQLite'}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
sys.exit(1 if FAIL else 0)
