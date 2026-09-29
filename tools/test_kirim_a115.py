#!/usr/bin/env python3
"""
test_kirim_a115.py — kech115, A bosqich (pul va ma'lumot xatolari), «Kirim qilish» guruhi: G4-01, G4-02, G4-03 va K115-1.

NIMA UCHUN KERAK (audit kech114 — O'LCHANGAN, asl kod = `staging` d1ba2b0)
  G4-01  «Kirimni tasdiqlash» yozib qo'yilgan (savatga qo'shilmagan) oxirgi qatorni TEKSHIRUVLARDAN OLDIN savatga qo'shardi
         va maydonlarni tozalamasdi: yo'nalish tanlanmagani uchun to'xtagach qayta bosilsa o'sha qator IKKI marta
         yuborilardi (ombor 200 kg, ta'minotchi qarzi 600 000 — 100 kg × 3 000 ikki marta). Server AYNAN bir xil ikki
         qatorni ham qabul qilardi. Tarmoq uzilib qayta bosilganda ham xuddi shunday. Chala qator (miqdor bor, narx yo'q)
         esa savatdagi boshqa qatorlar bilan JIM tashlab yuborilardi.
  G4-02  «Boshlang'ich ombor» belgisi va hujjat raqami saqlangandan keyin tozalanmasdi — keyingi oddiy xarid ham jimgina
         boshlang'ich (qarzsiz, to'lov 0) bo'lib o'sha raqam bilan yozilardi; belgi yoqilganda xulosa baribir
         «Qarzga qoladi …» derdi.
  G4-03  «Sana» va «To'lov muddati» serverga yuborilmasdi — kirim doim bugun, qarz muddati hech qayerda saqlanmasdi
         (dashboard «muddati yaqinlashgan qarzlar» ogohlantirishi shu muddatga tayanadi).
  K115-1 (shu testda topildi) saqlangach material ro'yxati qayta yuklanmasdi — keyingi kirimda savat qatori «?» nomi
         bilan, penoplast hajm maydoni ochilmasdi.

BO'LIMLAR
  S — server (`POST /api/inventory/receipt`): takror qator rad (hech narsa yozilmaydi), ikki partiya ruxsat; sana (o'tgan
      kun — xarid / hujjat / xarajat / to'lov shu kunga, ombor jurnali — kiritilgan vaqtda; oylik xarid statistikasi),
      bugun, kelajak / bir yildan eski / noto'g'ri shakl — rad, chegara 366 kun; to'lov muddati (nasiyaga, ogohlantirishda;
      kirim sanasidan oldin — rad; boshlang'ich omborda yozilmaydi).
  U — sahifa (HAQIQIY server + jsdom, sahifaning o'z skripti): G4-01 ssenariylari (yo'nalishsiz bosish, tarmoq uzilishi,
      takror qator, chala qator), G4-02 (belgi xulosada, saqlangach tozalanadi), G4-03 (sana / muddat yuboriladi,
      tasdiq, kelajak rad), K115-1.
  X — 5xx yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI (yiqiladi).
ISHLATISH: NODE_PATH=$(npm root -g) python3 tools/test_kirim_a115.py
           PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_kirim_a115.py
"""
import os
import sys
import json
import time
import socket
import shutil
import tempfile
import threading
import subprocess
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "kirim_a115_test"
_T = tempfile.mkdtemp(prefix="ka115_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'kirim_a115_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
import services                                    # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, Inventory, Supplier, InventoryPurchase, SupplierPayment,   # noqa: E402
                    ExpenseTransaction, InventoryReceipt, InventoryMovement)
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


def detail(r):
    d = js(r).get("detail") if isinstance(js(r), dict) else None
    return str(d if d is not None else getattr(r, "text", ""))


BUGUN = tashkent_date()
KECHA = BUGUN - timedelta(days=1)
OTGAN = BUGUN - timedelta(days=40)          # 40 kun — har doim boshqa oy
ERTAGA = BUGUN + timedelta(days=1)
MUDDAT = BUGUN + timedelta(days=10)
ISO = lambda d: d.strftime("%Y-%m-%d")      # noqa: E731

s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "ka_admin", "Parol123!", UserRole.ADMIN, "KA Admin", company_id=1)
MAT = {}
for kalit, nom, birlik, peno in [("m1", "KA Kley", "kg", False), ("m2", "KA Setka", "m2", False),
                                 ("m3", "KA Qum", "kg", False), ("m4", "KA Bo'yoq", "kg", False),
                                 ("m5", "KA Gruntovka", "kg", False), ("m6", "KA Penoplast 15", "m3", True),
                                 ("s1", "KA Server 1", "kg", False), ("s2", "KA Server 2", "kg", False),
                                 ("s3", "KA Server 3", "kg", False), ("s4", "KA Server 4", "kg", False),
                                 ("s5", "KA Server 5", "kg", False), ("s6", "KA Server 6", "kg", False)]:
    m = Inventory(company_id=1, item_name=nom, unit=birlik, stock_quantity=0, price_per_unit=0, is_penoplast=peno,
                  category=("Penoplast" if peno else "Kimyoviy qo'shimchalar"), volume_per_unit=(1.0 if peno else None))
    s.add(m)
    MAT[kalit] = m
SUP = {k: Supplier(company_id=1, name=f"KA Taminotchi {k}") for k in ("u", "s1", "s2", "s3", "s4", "s5")}
s.add_all(SUP.values())
s.commit()
M = {k: v.id for k, v in MAT.items()}
SID = {k: v.id for k, v in SUP.items()}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = C.post("/login", data={"username": "ka_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _lr.status_code in (200, 302, 303), _lr.status_code)


def kirim(qatorlar, **kw):
    tana = {"items": [{"inventory_id": m, "quantity": q, "price_per_unit": n, "volume_per_unit": None,
                       "is_opening_stock": bool(o)} for m, q, n, o in qatorlar],
            "notes": "KA", "production_type": None}
    tana.update(kw)
    return req(C, "post", "/api/inventory/receipt", json=tana)


def holat(inv_id=None, sid=None):
    """Bazadagi xom holat: xaridlar, qoldiq, hujjatlar, to'lovlar, xarajatlar soni."""
    s = SessionLocal()
    try:
        d = {"receipts": s.query(InventoryReceipt).count(), "xarajat": s.query(ExpenseTransaction).count(),
             "tolov": s.query(SupplierPayment).count(), "xarid": s.query(InventoryPurchase).count()}
        if inv_id is not None:
            it = s.query(Inventory).filter(Inventory.id == inv_id).first()
            d["qoldiq"] = float(it.stock_quantity or 0)
            d["xaridlar"] = [(float(p.quantity), float(p.price_per_unit), p.purchased_at, p.payment_due_date,
                              bool(p.is_credit), bool(p.is_opening_stock), p.receipt_id)
                             for p in s.query(InventoryPurchase).filter(InventoryPurchase.inventory_id == inv_id)
                             .order_by(InventoryPurchase.id).all()]
            d["harakat"] = [h.created_at for h in s.query(InventoryMovement).filter(
                InventoryMovement.inventory_id == inv_id).order_by(InventoryMovement.id).all()]
        if sid is not None:
            d["tolovlar"] = [(float(p.amount), p.paid_at) for p in s.query(SupplierPayment).filter(
                SupplierPayment.supplier_id == sid).order_by(SupplierPayment.id).all()]
            _q = crud.get_supplier_debt(s, sid, company_id=1)
            d["qarz"] = _q.get("debt")
        return d
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════
section("S1. Takror qator (G4-01) — AYNAN bir xil qator rad, hech narsa yozilmaydi; ikki partiya — ruxsat")
# ══════════════════════════════════════════════════════════════
h0 = holat(M["s1"], SID["s1"])
r = kirim([(M["s1"], 100, 3000, False), (M["s1"], 100, 3000, False)], supplier_id=SID["s1"], paid_now=0,
          transport_cost=5000)
h1 = holat(M["s1"], SID["s1"])
check("S1.1 bir material 100 × 3 000 ikki qatorda → 400 (asl: 200, ombor 200, qarz 600 000)", r.status_code == 400,
      (r.status_code, detail(r)[:200]))
check("S1.2 xabar — qator raqami va «AYNAN bir xil», material nomi", "2-qator 1-qator bilan AYNAN bir xil" in detail(r)
      and "KA Server 1" in detail(r), detail(r))
check("S1.3 hech narsa yozilmadi (hujjat, xarid, xarajat, to'lov, qoldiq 0)",
      (h1["receipts"], h1["xarid"], h1["xarajat"], h1["tolov"], h1["qoldiq"])
      == (h0["receipts"], h0["xarid"], h0["xarajat"], h0["tolov"], 0.0), (h0, h1))
r = kirim([(M["s1"], 50, 3000, False), (M["s2"], 1, 10, False), (M["s1"], 50, 3000.004, False)],
          supplier_id=SID["s1"], paid_now=0)
check("S1.4 narx tiyinga yaxlitlanganda bir xil (3 000 va 3 000.004) → 400, 3-qator 1-qator bilan",
      r.status_code == 400 and "3-qator 1-qator bilan" in detail(r), (r.status_code, detail(r)[:200]))
r = kirim([(M["s1"], 100, 3000, False), (M["s1"], 100, 3100, False)], supplier_id=SID["s1"], paid_now=0)
h2 = holat(M["s1"], SID["s1"])
check("S1.5 bir material ikki xil narxda (ikki partiya) → 200, ikki xarid, qoldiq 200",
      r.status_code == 200 and len(h2["xaridlar"]) == 2 and h2["qoldiq"] == 200, (r.status_code, detail(r)[:200], h2))
r = kirim([(M["s2"], 10, 500, False), (M["s2"], 20, 500, False)], supplier_id=SID["s1"], paid_now=0)
check("S1.6 bir material bir narx, har xil miqdor → 200", r.status_code == 200, (r.status_code, detail(r)[:200]))
r = kirim([(M["m6"], 2, 900000, False), (M["m6"], 2, 900000, False)], supplier_id=SID["s1"], paid_now=0)
check("S1.7 penoplast — hajm bir xil (null) → 400", r.status_code == 400, (r.status_code, detail(r)[:200]))
r = req(C, "post", "/api/inventory/receipt", json={
    "items": [{"inventory_id": M["m6"], "quantity": 2, "price_per_unit": 900000, "volume_per_unit": 1.2},
              {"inventory_id": M["m6"], "quantity": 2, "price_per_unit": 900000, "volume_per_unit": 1.4}],
    "supplier_id": SID["s1"], "paid_now": 0})
check("S1.8 penoplast — hajmi har xil (1.2 va 1.4 m³) → 200 (ikki partiya)", r.status_code == 200,
      (r.status_code, detail(r)[:200]))

# ══════════════════════════════════════════════════════════════
section("S2. Kirim sanasi (G4-03) — o'tgan kun: hamma pul yozuvlari shu kunga")
# ══════════════════════════════════════════════════════════════
_oy_oldin = services.get_purchase_stats_for_period(SessionLocal(), OTGAN.year, OTGAN.month, company_id=1)["total_amount"]
_oy_hozir = services.get_purchase_stats_for_period(SessionLocal(), BUGUN.year, BUGUN.month, company_id=1)["total_amount"]
_t0 = datetime.utcnow()
r = kirim([(M["s3"], 4, 2500, False)], supplier_id=SID["s2"], paid_now=4000, transport_cost=7000,
          receipt_date=ISO(OTGAN), payment_due_date=ISO(MUDDAT))
h = holat(M["s3"], SID["s2"])
check("S2.1 kirim sanasi 40 kun oldin → 200 (asl: 400 — maydon noma'lum)", r.status_code == 200,
      (r.status_code, detail(r)[:200]))
_x = (h.get("xaridlar") or [(None,) * 7])[0]
check("S2.2 xarid sanasi — tanlangan kun 00:00 (Toshkent kalendarida ham shu kun)",
      _x[2] is not None and _x[2] == datetime(OTGAN.year, OTGAN.month, OTGAN.day)
      and tashkent_date(_x[2]) == OTGAN, _x)
s = SessionLocal()
_rc = s.query(InventoryReceipt).filter(InventoryReceipt.id == (_x[6] or -1)).first()
_ex = s.query(ExpenseTransaction).filter(ExpenseTransaction.notes.like(f"%Kirim #{_x[6]}%")).all()
s.close()
check("S2.3 hujjat sanasi — o'sha kun", _rc is not None and _rc.receipt_date == datetime(OTGAN.year, OTGAN.month,
                                                                                           OTGAN.day), _rc and _rc.receipt_date)
check("S2.4 transport xarajati (Moliya) — o'sha kun", len(_ex) == 1 and tashkent_date(_ex[0].date) == OTGAN,
      [(e.date, e.amount) for e in _ex])
check("S2.5 «hozir to'langan» 4 000 — o'sha kun", [(a, tashkent_date(t)) for a, t in h["tolovlar"]] == [(4000.0, OTGAN)],
      h["tolovlar"])
check("S2.6 ombor harakati jurnali — kiritilgan vaqtda (bugun)", len(h["harakat"]) == 1
      and h["harakat"][0] >= _t0 - timedelta(seconds=5), h["harakat"])
_oy_oldin2 = services.get_purchase_stats_for_period(SessionLocal(), OTGAN.year, OTGAN.month, company_id=1)["total_amount"]
_oy_hozir2 = services.get_purchase_stats_for_period(SessionLocal(), BUGUN.year, BUGUN.month, company_id=1)["total_amount"]
check("S2.7 oylik xomashyo xaridi: o'sha oyga +10 000, joriy oyga 0",
      _oy_oldin2 - _oy_oldin == 10000 and _oy_hozir2 == _oy_hozir, (_oy_oldin, _oy_oldin2, _oy_hozir, _oy_hozir2))
check("S2.8 to'lov muddati nasiya xaridida saqlandi", _x[3] is not None and _x[3].date() == MUDDAT and _x[4] is True, _x)
s = SessionLocal()
_due = [d for d in crud.get_supplier_payment_due_dates(s, company_id=1) if d["supplier_id"] == SID["s2"]]
s.close()
check("S2.9 dashboard «to'lov muddati» ogohlantirishida ta'minotchi (qarz 6 000, 10 kun)",
      len(_due) == 1 and _due[0]["debt"] == 6000 and _due[0]["days_left"] == 10, _due)

# ══════════════════════════════════════════════════════════════
section("S3. Sana chegaralari — bugun, kelajak, bir yildan eski, noto'g'ri shakl, muddat")
# ══════════════════════════════════════════════════════════════
_t1 = datetime.utcnow()
r = kirim([(M["s4"], 1, 100, False)], supplier_id=SID["s3"], paid_now=0, receipt_date=ISO(BUGUN))
h = holat(M["s4"])
check("S3.1 bugungi sana → 200, xarid vaqti — HOZIR (00:00 emas)", r.status_code == 200 and h["xaridlar"]
      and abs((h["xaridlar"][-1][2] - _t1).total_seconds()) < 120, (r.status_code, detail(r)[:200], h.get("xaridlar")))
r = kirim([(M["s4"], 1, 101, False)], supplier_id=SID["s3"], paid_now=0, receipt_date="")
h = holat(M["s4"])
check("S3.2 bo'sh sana → 200, hozir", r.status_code == 200 and abs((h["xaridlar"][-1][2] - _t1).total_seconds()) < 120,
      (r.status_code, detail(r)[:200]))
h0 = holat(M["s5"], SID["s4"])
r = kirim([(M["s5"], 1, 100, False)], supplier_id=SID["s4"], paid_now=100, transport_cost=50, receipt_date=ISO(ERTAGA))
h1 = holat(M["s5"], SID["s4"])
check("S3.3 ertangi sana → 400 «kelajakda», hech narsa yozilmadi",
      r.status_code == 400 and "kelajakda" in detail(r)
      and (h1["receipts"], h1["xarid"], h1["xarajat"], h1["tolov"]) == (h0["receipts"], h0["xarid"], h0["xarajat"], h0["tolov"]),
      (r.status_code, detail(r)[:200]))
r = kirim([(M["s5"], 1, 100, False)], supplier_id=SID["s4"], paid_now=0,
          receipt_date=ISO(BUGUN - timedelta(days=366)))
check("S3.4 roppa-rosa 366 kun oldin → 200 (chegara ichida)", r.status_code == 200, (r.status_code, detail(r)[:200]))
r = kirim([(M["s5"], 1, 102, False)], supplier_id=SID["s4"], paid_now=0, receipt_date=ISO(BUGUN - timedelta(days=367)))
check("S3.5 367 kun oldin → 400 «juda eski»", r.status_code == 400 and "juda eski" in detail(r),
      (r.status_code, detail(r)[:200]))
r = kirim([(M["s5"], 1, 103, False)], supplier_id=SID["s4"], paid_now=0, receipt_date="2026-13-45")
check("S3.6 noto'g'ri sana «2026-13-45» → 400", r.status_code == 400, (r.status_code, detail(r)[:200]))
r = kirim([(M["s5"], 1, 104, False)], supplier_id=SID["s4"], paid_now=0, receipt_date=ISO(KECHA),
          payment_due_date=ISO(KECHA - timedelta(days=1)))
check("S3.7 to'lov muddati kirim sanasidan oldin → 400", r.status_code == 400 and "oldin bo'lishi mumkin emas" in detail(r),
      (r.status_code, detail(r)[:200]))
r = kirim([(M["s5"], 1, 105, False)], supplier_id=SID["s4"], paid_now=0, receipt_date=ISO(KECHA),
          payment_due_date=ISO(KECHA))
check("S3.8 to'lov muddati = kirim sanasi → 200", r.status_code == 200, (r.status_code, detail(r)[:200]))
r = kirim([(M["s6"], 3, 100, True)], supplier_id=SID["s5"], paid_now=0, payment_due_date=ISO(MUDDAT))
h = holat(M["s6"])
check("S3.9 boshlang'ich ombor + muddat → 200, muddat YOZILMAYDI (qarz yo'q)",
      r.status_code == 200 and h["xaridlar"] and h["xaridlar"][-1][3] is None and h["xaridlar"][-1][5] is True,
      (r.status_code, detail(r)[:200], h.get("xaridlar")))
r = kirim([(M["s6"], 3, 101, False)], supplier_id=None, paid_now=0, payment_due_date=ISO(MUDDAT))
h = holat(M["s6"])
check("S3.10 ta'minotchisiz kirim + muddat → 200, muddat yozilmaydi", r.status_code == 200
      and h["xaridlar"][-1][3] is None, (r.status_code, detail(r)[:200], h.get("xaridlar")))
_kv = getattr(crud, "kirim_sanalari", None)
if _kv:
    try:
        _a = _kv(ISO(KECHA), None)
        _b = _kv(None, None)
        _c = _kv(ISO(BUGUN), ISO(MUDDAT))
    except Exception as e:                 # noqa: BLE001
        _a = _b = _c = repr(e)
    check("S3.11 `kirim_sanalari`: kecha → 00:00; bo'sh / bugun → None; muddat matn",
          _a == (datetime(KECHA.year, KECHA.month, KECHA.day), None) and _b == (None, None)
          and _c == (None, ISO(MUDDAT)), (_a, _b, _c))
else:
    check("S3.11 `crud.kirim_sanalari` bor", False, "yo'q")

# ══════════════════════════════════════════════════════════════
# U — sahifa: HAQIQIY server + jsdom
# ══════════════════════════════════════════════════════════════
NODE_JS = r"""
let JSDOM, VirtualConsole, ResourceLoader;
try { ({ JSDOM, VirtualConsole, ResourceLoader } = require("jsdom")); }
catch (e) { console.log(JSON.stringify({ fatal: "jsdom topilmadi: " + String(e.message).slice(0, 200) })); process.exit(3); }
const base = process.argv[2], cookie = process.argv[3];
const sahifalar = JSON.parse(require("fs").readFileSync(process.argv[4], "utf8"));
class FaqatOzimiz extends ResourceLoader {
  fetch(url, options) { return url.startsWith(base) ? super.fetch(url, options) : null; }
}
const kut = ms => new Promise(r => setTimeout(r, ms));
const res = { sahifa: {}, xato: [], api_xato: [], natija: {} };
process.on("unhandledRejection", e => res.xato.push("va'da: " + String((e && (e.message || e)) || "").slice(0, 200)));
process.on("uncaughtException", e => res.xato.push("xato: " + String((e && (e.message || e)) || "").slice(0, 200)));
async function ochish(yol, qadamlar) {
  const r = await fetch(base + yol, { headers: { cookie }, redirect: "manual" });
  res.sahifa[yol] = r.status;
  const html = await r.text();
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => { const m = String((e && (e.message || e)) || "").slice(0, 300); if (!/Not implemented/.test(m)) res.xato.push(yol + ": " + m); });
  let pending = 0, lastActive = Date.now();
  const sahifaUrl = base + yol;
  const dom = new JSDOM(html, { url: sahifaUrl, runScripts: "dangerously", pretendToBeVisual: true,
    resources: new FaqatOzimiz(), virtualConsole: vc,
    beforeParse(w) {
      w.__sorovlar = [];
      try { w.localStorage.clear(); } catch (e) {}
      w.fetch = async (u, o) => {
        pending++; lastActive = Date.now();
        try {
          o = o || {};
          const h = Object.assign({}, o.headers || {}); h.cookie = cookie;
          const url = new URL(String(u), sahifaUrl).href;
          if (!url.startsWith(base)) throw new Error("tashqi so'rov: " + url);
          const resp = await fetch(url, Object.assign({}, o, { headers: h, redirect: "manual" }));
          if (resp.status >= 500) res.api_xato.push(resp.status + " " + url.slice(base.length, base.length + 120));
          w.__sorovlar.push({ url: url.slice(base.length), method: o.method || "GET", status: resp.status,
                              body: (o.method && o.method !== "GET") ? String(o.body || "").slice(0, 6000) : null });
          return resp;
        } finally { pending--; lastActive = Date.now(); }
      };
      w.alert = () => {}; w.confirm = () => false; w.prompt = () => null; w.print = () => {};
      w.scrollTo = () => {}; w.open = () => null;
      w.matchMedia = () => ({ matches: false, media: "", addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
      class K { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } }
      w.IntersectionObserver = K; w.ResizeObserver = K;
      w.HTMLCanvasElement.prototype.getContext = () => null;
      w.HTMLElement.prototype.scrollIntoView = () => {};
    } });
  const w = dom.window;
  await new Promise(r => { if (w.document.readyState === "complete") return r(); w.addEventListener("load", () => r()); setTimeout(r, 8000); });
  async function tinch() {
    await kut(300);
    const t0 = Date.now();
    while (Date.now() - t0 < 15000) { await kut(60); if (pending === 0 && Date.now() - lastActive > 300) return; }
    res.xato.push(yol + ": tarmoq 15 s ichida tinchimadi");
  }
  await tinch();
  for (const q of qadamlar) {
    try {
      if (q.amal) { await w.eval("(async () => { " + q.amal + "\n})()"); await tinch(); }
      if (q.natija) res.natija[q.nom] = await w.eval("(async () => { " + q.natija + "\n})()");
    } catch (e) {
      res.natija[q.nom] = { XATO: String((e && (e.stack || e.message)) || e).slice(0, 400) };
    }
  }
  w.close();
}
(async () => {
  for (const s of sahifalar) await ochish(s.yol, s.qadamlar);
  console.log(JSON.stringify(res));
  process.exit(0);
})().catch(e => { res.xato.push("yakuniy: " + String(e && e.message)); console.log(JSON.stringify(res)); process.exit(0); });
"""

YORDAM = r"""
window.__msg = [];
window.__tasdiq = [];
window.showMsg = (t, k) => { window.__msg.push([String(t), String(k || '')]); };
window.customConfirm = async (t) => { window.__tasdiq.push(String(t)); return true; };
window.__m = el => el ? el.textContent.replace(/\s+/g, ' ').trim() : null;
window.__oxirgi = () => (window.__msg[window.__msg.length - 1] || ['', ''])[0];
window.__postlar = () => window.__sorovlar.filter(s => s.method === 'POST' && s.url.startsWith('/api/inventory/receipt'));
window.__qator = (id, miq, narx) => {
  if (typeof showAllMaterials === 'function') showAllMaterials();
  document.getElementById('ap-item').value = String(id);
  if (typeof apOnItemChange === 'function') apOnItemChange();
  document.getElementById('ap-qty').value = miq == null ? '' : String(miq);
  document.getElementById('ap-price').value = narx == null ? '' : String(narx);
};
window.__yonalish = () => selectProdType(document.querySelector('#ap-prod-type-toggle .rcv-cat-opt'), '');
window.__holat = () => ({ savat: apBasket.length, savat_nomlar: apBasket.map(b => b.itemName),
  qty: document.getElementById('ap-qty').value, price: document.getElementById('ap-price').value,
  postlar: __postlar().length, oxirgi: __oxirgi(),
  oxirgi_body: (__postlar().slice(-1)[0] || {}).body ? JSON.parse(__postlar().slice(-1)[0].body) : null });
return true;
"""


def q(nom, amal=None, natija=None):
    return {"nom": nom, "amal": amal, "natija": natija}


U = [
    q("yordam", natija=YORDAM),
    # ta'minotchi tanlanadi — `amal` ichida: sahifaning fon so'rovlari (tarix, material filtri — ro'yxatni qayta chizadi)
    # tugashini kutish uchun
    q("tanla", amal=f"document.getElementById('r-supplier').value = '{SID['u']}'; await onSupplierChange();",
      natija="return currentSupplierId;"),
    # U1 — G4-01: yo'nalish tanlanmagan, oxirgi qator yozilgan → to'xtaydi; yo'nalish tanlab qayta → BITTA qator
    q("u1_a", amal=f"__qator({M['m1']}, 100, '3 000'); await submitReceive();", natija="return __holat();"),
    q("u1_b", amal="__yonalish(); await submitReceive();", natija="return __holat();"),
    # K115-1: saqlangach material nomi (invItems qayta yuklangan)
    q("u8", amal=f"__qator({M['m1']}, 5, 1000); await apAddToBasket();",
      natija="const n = apBasket.map(b => b.itemName); apRemoveFromBasket(0); return {nomlar: n, savat: apBasket.length};"),
    q("u8_peno", amal=f"__qator({M['m6']}, 1, 1000);",
      natija="return document.getElementById('ap-volume-wrap').style.display;"),
    # U3 — takror qator: savatda M2 10 × 500, yana shu qator yozilgan → rad, POST yo'q
    q("u3_a", amal=f"__qator({M['m2']}, 10, 500); await apAddToBasket(); __qator({M['m2']}, 10, 500); __yonalish(); await submitReceive();",
      natija="return __holat();"),
    q("u3_b", amal="document.getElementById('ap-qty').value=''; document.getElementById('ap-price').value=''; __yonalish(); await submitReceive();",
      natija="return __holat();"),
    q("u3_c", amal=f"__qator({M['m2']}, 10, 500); await apAddToBasket(); __qator({M['m2']}, 10, 500); await apAddToBasket();",
      natija="const h = __holat(); apBasket.length = 0; renderBasket(); return h;"),
    # U2 — tarmoq uzilishi: birinchi yuborish yiqiladi, qayta — BITTA qator
    q("u2_a", amal=f"""__qator({M['m3']}, 7, 2000); __yonalish();
      window.__asilFetch = window.fetch; window.__uzildi = false;
      window.fetch = async (u, o) => {{ if (String(u).includes('/api/inventory/receipt') && !window.__uzildi) {{ window.__uzildi = true; throw new TypeError('Failed to fetch'); }} return window.__asilFetch(u, o); }};
      await submitReceive();""", natija="return __holat();"),
    q("u2_b", amal="window.fetch = window.__asilFetch; __yonalish(); await submitReceive();", natija="return __holat();"),
    # U7 — chala qator (miqdor bor, narx yo'q) savatda qator bo'lganda → to'xtaydi (JIM tashlab yuborilmaydi)
    q("u7_a", amal=f"__qator({M['m4']}, 1, 100); await apAddToBasket(); __qator({M['m4']}, 5, ''); __yonalish(); await submitReceive();",
      natija="return __holat();"),
    q("u7_b", amal="apBasket.length = 0; renderBasket(); document.getElementById('ap-qty').value='';", natija="return __holat();"),
    # U4 — G4-02: boshlang'ich ombor — xulosa, saqlash, keyin tozalanadi; keyingi xarid oddiy
    q("u4_a", amal=f"""const cb = document.getElementById('ap-opening-stock'); cb.checked = true; cb.dispatchEvent(new Event('change'));
      __qator({M['m4']}, 2, 1000); await apAddToBasket(); document.getElementById('ap-paid-now').value = '500';
      document.getElementById('ap-paid-now').dispatchEvent(new Event('input'));
      document.getElementById('r-docnum').value = 'HUJ-1';""",
      natija=r"""const w = document.getElementById('sum-opening-warn');
      return {qarz: __m(document.getElementById('sum-debt')), tolangan: __m(document.getElementById('sum-paid')),
        ogoh: w ? w.style.display : null, ogoh_matn: w ? __m(w) : null};"""),
    q("u4_b", amal="__yonalish(); await submitReceive();",
      natija=r"""const w = document.getElementById('sum-opening-warn');
      return Object.assign(__holat(), {belgi: document.getElementById('ap-opening-stock').checked,
        hujjat: document.getElementById('r-docnum').value, ogoh: w ? w.style.display : null});"""),
    q("u4_c", amal=f"__qator({M['m4']}, 3, 1000); await apAddToBasket(); document.getElementById('ap-paid-now').value = '1 000'; __yonalish(); await submitReceive();",
      natija="return __holat();"),
    # U5 — G4-03: o'tgan sana va to'lov muddati yuboriladi, tasdiq so'raladi, keyin sana — bugun
    q("u5_a", amal=f"""const d = document.getElementById('r-date'); d.value = '{ISO(OTGAN)}'; d.dispatchEvent(new Event('change'));""",
      natija=r"""const w = document.getElementById('sum-date-warn'); return {ko: w ? w.style.display : null, matn: w ? __m(w) : null};"""),
    q("u5_b", amal=f"""__qator({M['m5']}, 4, 2500); document.getElementById('ap-due-date').value = '{ISO(MUDDAT)}'; __yonalish();
      window.__tasdiq = []; await submitReceive();""",
      natija="return Object.assign(__holat(), {tasdiq: window.__tasdiq.slice(), sana: document.getElementById('r-date').value, bugun: tkISO()});"),
    # U6 — kelajak sanasi — to'xtaydi
    q("u6", amal=f"""document.getElementById('r-date').value = '{ISO(ERTAGA)}'; __qator({M['m5']}, 1, 100); __yonalish(); await submitReceive();""",
      natija="const h = __holat(); document.getElementById('r-date').value = tkISO(); return h;"),
    # U9 — muddat kirim sanasidan oldin — to'xtaydi
    q("u9", amal=f"""document.getElementById('r-date').value = '{ISO(KECHA)}'; document.getElementById('ap-due-date').value = '{ISO(KECHA - timedelta(days=2))}'; __yonalish(); await submitReceive();""",
      natija="return __holat();"),
]
SAHIFALAR = [{"yol": "/suppliers/receive", "qadamlar": U}]

section("U. Sahifa — HAQIQIY server + jsdom (sahifaning o'z skripti)")
node = shutil.which("node")
check("U0 node topildi", node is not None)
NAT = {}
if node:
    try:
        npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:                      # noqa: BLE001
        npm_root = ""
    env = dict(os.environ)
    env["NODE_PATH"] = os.pathsep.join(x for x in (os.environ.get("NODE_PATH", ""), npm_root,
                                                    os.path.join(ROOT, "node_modules")) if x)
    import uvicorn

    def _port():
        so = socket.socket()
        so.bind(("127.0.0.1", 0))
        p = so.getsockname()[1]
        so.close()
        return p

    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    check("U0 uvicorn ishga tushdi", server.started)
    base = f"http://127.0.0.1:{port}"
    try:
        import httpx
        lr = httpx.post(base + "/login", data={"username": "ka_admin", "password": "Parol123!"}, follow_redirects=False,
                        timeout=30)
        cookie = "; ".join(hh.split(";")[0] for hh in lr.headers.get_list("set-cookie"))
        pj = os.path.join(_T, "sahifalar.json")
        with open(pj, "w", encoding="utf-8") as f:
            json.dump(SAHIFALAR, f, ensure_ascii=False)
        sj = os.path.join(_T, "kirim_a115.js")
        with open(sj, "w", encoding="utf-8") as f:
            f.write(NODE_JS)
        k = subprocess.run([node, sj, base, cookie, pj], capture_output=True, text=True, timeout=900, env=env)
        try:
            NAT = json.loads((k.stdout or "").strip().splitlines()[-1])
        except Exception as e:             # noqa: BLE001
            NAT = {"fatal": f"{type(e).__name__}: {e}; stdout={(k.stdout or '')[-400:]} stderr={(k.stderr or '')[-400:]}"}
    finally:
        server.should_exit = True
        th.join(timeout=10)
N = NAT.get("natija") or {}
check("U0 sahifa 200, ssenariy tugadi", "fatal" not in NAT and N.get("yordam") is True
      and (NAT.get("sahifa") or {}).get("/suppliers/receive") == 200, {k: NAT.get(k) for k in ("sahifa", "fatal", "xato")})


def g(nom, kalit=None, std=None):
    v = N.get(nom)
    if kalit is None:
        return v
    return v.get(kalit, std) if isinstance(v, dict) else std


def body_items(nom):
    b = g(nom, "oxirgi_body") or {}
    return [(it.get("inventory_id"), it.get("quantity"), it.get("price_per_unit")) for it in (b.get("items") or [])]


# G4-01
check("U1.1 yo'nalishsiz bosish → «Yo'nalishni tanlang», savat 0, so'rov yo'q (asl: savat 1)",
      "Yo'nalishni tanlang" in (g("u1_a", "oxirgi") or "") and g("u1_a", "savat") == 0 and g("u1_a", "postlar") == 0,
      N.get("u1_a"))
check("U1.2 yozilgan qator o'z joyida qoldi (100 / 3 000)", g("u1_a", "qty") == "100" and g("u1_a", "price") == "3 000",
      N.get("u1_a"))
check("U1.3 yo'nalish tanlab qayta → BITTA POST, BITTA qator (asl: 2 qator)",
      g("u1_b", "postlar") == 1 and body_items("u1_b") == [(M["m1"], 100, 3000)], N.get("u1_b"))
h = holat(M["m1"], SID["u"])
check("U1.4 serverda: qoldiq 100, BITTA nasiya xarid 100 × 3 000 (asl: qoldiq 200, ikki xarid — qarz 600 000)",
      h["qoldiq"] == 100 and [(x[0], x[1], x[4]) for x in h["xaridlar"]] == [(100.0, 3000.0, True)], h)
check("U1.5 saqlangach maydonlar bo'sh, muvaffaqiyat xabari", g("u1_b", "qty") == "" and g("u1_b", "price") == ""
      and "Kirim saqlandi" in (g("u1_b", "oxirgi") or ""), N.get("u1_b"))
# K115-1
check("U8.1 saqlangandan keyin qo'shilgan qator — material nomi bilan (asl: «?»)", g("u8", "nomlar") == ["KA Kley"],
      N.get("u8"))
check("U8.2 saqlangandan keyin penoplast tanlansa hajm maydoni ochiladi (asl: yopiq)", N.get("u8_peno") == "block",
      N.get("u8_peno"))
# takror
check("U3.1 savatdagi qator yana yozilib bosildi → rad («allaqachon bor»), POST yo'q, savat 1",
      "allaqachon bor" in (g("u3_a", "oxirgi") or "") and g("u3_a", "savat") == 1 and g("u3_a", "postlar") == 1,
      N.get("u3_a"))
check("U3.2 maydonlar tozalangach yuborildi — bitta qator, serverda qoldiq 10",
      g("u3_b", "postlar") == 2 and body_items("u3_b") == [(M["m2"], 10, 500)] and holat(M["m2"])["qoldiq"] == 10,
      (N.get("u3_b"), holat(M["m2"])["qoldiq"]))
check("U3.3 «+ ro'yxatga qo'shish» ham takror qatorni rad etadi (savat 1)",
      g("u3_c", "savat") == 1 and "allaqachon bor" in (g("u3_c", "oxirgi") or ""), N.get("u3_c"))
# tarmoq
check("U2.1 tarmoq uzildi → «aloqa yo'q», qator savatda (1), maydonlar bo'sh",
      "aloqa" in (g("u2_a", "oxirgi") or "") and g("u2_a", "savat") == 1 and g("u2_a", "qty") == "", N.get("u2_a"))
check("U2.2 qayta bosish → BITTA qator (asl: 2), serverda qoldiq 7",
      body_items("u2_b") == [(M["m3"], 7, 2000)] and holat(M["m3"])["qoldiq"] == 7, (N.get("u2_b"), holat(M["m3"])))
# chala qator
check("U7.1 chala oxirgi qator (narxsiz) → to'xtaydi «to'liq emas», POST yo'q (asl: savatdagi qator JIM yuborilardi)",
      "to'liq emas" in (g("u7_a", "oxirgi") or "") and g("u7_a", "postlar") == g("u2_b", "postlar"), N.get("u7_a"))
# G4-02
check("U4.1 belgi yoqilganda xulosa: to'langan 0, qarz 0 va sariq ogohlantirish (asl: «Qarzga qoladi 2 000»)",
      g("u4_a", "qarz") == "0 so'm" and g("u4_a", "tolangan") == "0 so'm" and g("u4_a", "ogoh") == "block"
      and "Boshlang'ich ombor" in (g("u4_a", "ogoh_matn") or ""), N.get("u4_a"))
_b4 = g("u4_b", "oxirgi_body") or {}
check("U4.2 boshlang'ich kirim yuborildi (is_opening_stock, paid_now 0, HUJ-1)",
      _b4.get("paid_now") == 0 and _b4.get("document_number") == "HUJ-1"
      and all(it.get("is_opening_stock") is True for it in _b4.get("items") or [{}]), _b4)
check("U4.3 saqlangach belgi olib tashlandi, hujjat raqami bo'sh, ogohlantirish yashirin (asl: belgi qolardi)",
      g("u4_b", "belgi") is False and g("u4_b", "hujjat") == "" and g("u4_b", "ogoh") == "none", N.get("u4_b"))
_b4c = g("u4_c", "oxirgi_body") or {}
check("U4.4 keyingi oddiy xarid — nasiya, to'lov 1 000, hujjat raqamisiz (asl: boshlang'ich, 0, HUJ-1)",
      _b4c.get("paid_now") == 1000 and _b4c.get("document_number") is None
      and all(it.get("is_opening_stock") is False for it in _b4c.get("items") or [{}]), _b4c)
h = holat(M["m4"], SID["u"])
check("U4.5 serverda: m4 — bitta boshlang'ich (2), bitta nasiya (3)",
      [(x[0], x[4], x[5]) for x in h["xaridlar"]] == [(2.0, False, True), (3.0, True, False)], h["xaridlar"])
# G4-03
check("U5.1 sana bugun emas — xulosada ko'k eslatma (sana bilan)",
      g("u5_a", "ko") == "block" and OTGAN.strftime("%d.%m.%Y") in (g("u5_a", "matn") or ""), N.get("u5_a"))
_b5 = g("u5_b", "oxirgi_body") or {}
check("U5.2 yuborilgan tanada receipt_date va payment_due_date (asl: yo'q)",
      _b5.get("receipt_date") == ISO(OTGAN) and _b5.get("payment_due_date") == ISO(MUDDAT), _b5)
check("U5.3 tasdiq so'raldi (sana bilan)", len(g("u5_b", "tasdiq") or []) == 1
      and OTGAN.strftime("%d.%m.%Y") in (g("u5_b", "tasdiq") or [""])[0], N.get("u5_b"))
check("U5.4 saqlangach sana — yana bugun", g("u5_b", "sana") == g("u5_b", "bugun") and g("u5_b", "sana"), N.get("u5_b"))
h = holat(M["m5"])
check("U5.5 serverda: xarid o'sha kunda, muddat saqlangan",
      len(h["xaridlar"]) == 1 and h["xaridlar"][0][2] == datetime(OTGAN.year, OTGAN.month, OTGAN.day)
      and h["xaridlar"][0][3] is not None and h["xaridlar"][0][3].date() == MUDDAT, h["xaridlar"])
check("U6.1 kelajak sanasi → to'xtaydi «kelajakda», POST yo'q",
      "kelajakda" in (g("u6", "oxirgi") or "") and g("u6", "postlar") == g("u5_b", "postlar"), N.get("u6"))
check("U9.1 muddat kirim sanasidan oldin → to'xtaydi, POST yo'q",
      "oldin bo'lishi mumkin emas" in (g("u9", "oxirgi") or "") and g("u9", "postlar") == g("u5_b", "postlar"), N.get("u9"))
check("U10 sahifa JS xatosi yo'q, 5xx yo'q", not NAT.get("xato") and not NAT.get("api_xato"),
      (NAT.get("xato"), NAT.get("api_xato")))

section("X. Server xatosi yo'q")
_5xx = [h for h in HOLATLAR if h[1] >= 500]
check("X1 hech bir so'rov 5xx emas", not _5xx, _5xx[:5])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
