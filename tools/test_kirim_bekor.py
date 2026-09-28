#!/usr/bin/env python3
"""
test_kirim_bekor.py — kech107 darvozasi (5-bo'lim 10-band, "Kirim hujjatini bekor qilish"): Ombor KIRIM HUJJATINI
butunlay bekor qilish va xarid o'chirilganda O'RTACHA NARXning qaytishi. UI qismi — `tools/test_kirim_bekor_ui.js`.

NIMA UCHUN (asl kod staging `061e082` = zip 101 da O'LCHANGAN — `work/probe107f.py`, SQLite = PG)
-------------------------------------------------------------------------------------------------
  * Butun hujjatni bekor qiladigan yo'l YO'Q edi — faqat xaridlarni bittalab o'chirish. Akril 100 kg × 1 000 bor; xato
    kirim 100 kg × 3 000 + transport 20 000 + tushirish 5 000, «hozir to'langan» 150 000 → hamma xarid o'chirilgach
    ombor qaytdi, LEKIN narx 2 000 da qoldi (1 000 emas), Moliyada 25 000 xarajat (sof foyda −25 000), ta'minotchiga
    150 000 to'lov, kassa −175 000 va hujjat qatori qoldi.
EGASI QARORI (kech107): "Har safar so'rasin" — to'lov: o'chirish yoki ta'minotchida avans; qolgani avtomatik orqaga.

TUZATISH: `InventoryPurchase.narx_oldin` / `narx_keyin`; `crud._xarid_narxini_qaytar` (narx hali `narx_keyin` ga teng
bo'lsa — `narx_oldin`); `crud.kirim_hujjatini_bekor_qilish` (reja = amal); `GET …/cancel-plan`, `POST …/cancel?tolov=`.

BO'LIMLAR: A — yakka xarid o'chirish (narx qoidasi); B — reja hech narsani o'zgartirmaydi; C — to'lovsiz hujjat;
D — to'lovli: 409 / ochirish / avans / noto'g'ri tanlov / takror; E — bir material ikki qatorda + tannarxga qo'shish;
F — oraliq sarf va manfiy qoldiq; G — izolyatsiya ("#1" ↔ "#12", begona korxona); H — audit; I — PG parallel; J — statik.

REJIMLAR: SQLite; `PG_URL` berilsa — YANGI PG bazasi.
    python3 tools/test_kirim_bekor.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_kirim_bekor.py
"""
import os
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "kirim_bekor_test"
_DB = os.path.join(tempfile.gettempdir(), "kirim_bekor_test.db")

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
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402

from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, Inventory, InventoryPurchase, InventoryReceipt, ExpenseTransaction,  # noqa: E402
                    SupplierPayment, InventoryMovement, ActivityLog)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
crud.PUL_TAKROR_SONIYA = 0


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
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


# ── Fikstura ────────────────────────────────────────────────────────────────
s = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    if s.get(Company, 2) is None:
        s.add(Company(id=2, name="KB Korxona B"))
        s.commit()
    auth.create_user(s, "kb_admin", "Parol123!", UserRole.ADMIN, "KB admin", company_id=1)
    auth.create_user(s, "kb_admin_b", "Parol123!", UserRole.ADMIN, "KB admin B", company_id=2)
s.commit()
s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
req(C, "post", "/login", data={"username": "kb_admin", "password": "Parol123!"}, follow_redirects=False)
req(CB, "post", "/login", data={"username": "kb_admin_b", "password": "Parol123!"}, follow_redirects=False)
BUGUN = tashkent_date()
YIL, OY = BUGUN.year, BUGUN.month


def taminotchi(c, nom):
    r = req(c, "post", "/api/suppliers", json={"name": nom, "phone": "+998901112233"})
    return (js(r) or {}).get("id") if r.status_code == 200 else None


def material(c, nom, qoldiq=0.0, narx=0.0):
    r = req(c, "post", "/api/inventory", json={"item_name": nom, "unit": "kg", "category": "Kimyoviy qo'shimchalar",
                                                "stock_quantity": qoldiq, "price_per_unit": narx, "min_stock": 0})
    return (js(r) or {}).get("id") if r.status_code == 200 else None


def kirim(c, sup, qatorlar, add_to_cost=False, paid_now=0.0, transport=0.0, tushirish=0.0, hujjat="KB"):
    r = req(c, "post", "/api/inventory/receipt", json={
        "items": [{"inventory_id": m, "quantity": q, "price_per_unit": n} for m, q, n in qatorlar],
        "transport_cost": transport, "tushirish_cost": tushirish, "yuklash_cost": 0, "boshqa_cost": 0,
        "add_to_cost": add_to_cost, "supplier_id": sup, "document_number": hujjat, "paid_now": paid_now, "notes": hujjat})
    return r.status_code, (js(r) or {})


def mat(mid):
    s = SessionLocal()
    try:
        it = s.get(Inventory, mid)
        return [round(float(it.stock_quantity or 0), 6), round(float(it.price_per_unit or 0), 2)] if it else None
    finally:
        s.close()


def holat(sup=None):
    s = SessionLocal()
    try:
        out = {
            "mat": {i.id: [round(float(i.stock_quantity or 0), 6), round(float(i.price_per_unit or 0), 2)]
                    for i in s.query(Inventory).filter(Inventory.company_id == 1).order_by(Inventory.id).all()},
            "xaridlar": s.query(InventoryPurchase).count(),
            "hujjatlar": s.query(InventoryReceipt).count(),
            "xarajatlar": sorted((t.category, float(t.amount), t.source, t.company_id) for t in s.query(ExpenseTransaction).all()),
            "tolovlar": sorted((p.supplier_id, float(p.amount), p.notes or "") for p in s.query(SupplierPayment).all()),
        }
        if sup:
            out["qarz"] = crud.get_supplier_debt(s, sup, company_id=1)
    finally:
        s.close()
    rep = js(req(C, "get", f"/api/finance/report?year={YIL}&month={OY}")) or {}
    out["hisobot"] = [rep.get("jami_xarajat"), rep.get("sof_foyda")]
    out["kassa"] = (js(req(C, "get", "/api/finance/cash-balance")) or {}).get("balance")
    return out


def farq(a, b):
    return {k: [a.get(k), b.get(k)] for k in set(a) | set(b) if a.get(k) != b.get(k)}


SUP = taminotchi(C, "KB Ta'minotchi")
M1 = material(C, "KB Akril", 100, 1000)
M2 = material(C, "KB Qum", 0, 0)
check("0 fikstura", SUP and M1 and M2 and mat(M1) == [100.0, 1000.0], (SUP, M1, M2, mat(M1)))

# ══════════════════════════════════════════════════════════════
section("A — yakka xarid o'chirish: o'rtacha narx")
st, rj = kirim(C, SUP, [(M1, 100, 3000)], hujjat="KB-A1")
_pid = (rj.get("purchase_ids") or [None])[0]
check("A0 kirim: Akril 200 kg × 2 000 (o'rtacha)", st == 200 and mat(M1) == [200.0, 2000.0], (st, mat(M1)))
r = req(C, "delete", f"/api/inventory/purchases/{_pid}")
check("A1 xarid o'chirildi — qoldiq 100, narx 1 000 ga QAYTDI (asl: 2 000 da qolardi)",
      r.status_code == 200 and mat(M1) == [100.0, 1000.0], (r.status_code, mat(M1)))
st, rj = kirim(C, SUP, [(M1, 100, 3000)], add_to_cost=True, transport=20000, hujjat="KB-A2")
_pid = (rj.get("purchase_ids") or [None])[0]
check("A2 tannarxga qo'shilgan transport bilan: narx 2 100 (100×1000 + 100×3200) / 200", mat(M1) == [200.0, 2100.0], mat(M1))
req(C, "delete", f"/api/inventory/purchases/{_pid}")
check("A3 o'chirildi — narx 1 000 (transport ulushi ham chiqdi)", mat(M1) == [100.0, 1000.0], mat(M1))
st, rj = kirim(C, SUP, [(M1, 100, 3000)], hujjat="KB-A4")
_pid = (rj.get("purchase_ids") or [None])[0]
req(C, "post", f"/api/inventory/{M1}/purchase", json={"quantity": 10, "price_per_unit": 5000, "notes": "KB keyingi"})
_n = mat(M1)
req(C, "delete", f"/api/inventory/purchases/{_pid}")
check("A4 orada BOSHQA kirim bo'lsa — narx TEGILMAYDI (teskari hisob noaniq), qoldiq −100",
      mat(M1) == [round(_n[0] - 100, 6), _n[1]], (_n, mat(M1)))
_n0 = mat(M1)
st, rj = kirim(C, SUP, [(M1, 50, 4000)], hujjat="KB-A5")
_pid = (rj.get("purchase_ids") or [None])[0]
r = req(C, "post", f"/api/inventory/{M1}/price", json={"price_per_unit": 1234})
req(C, "delete", f"/api/inventory/purchases/{_pid}")
check("A5 orada narx QO'LDA o'zgartirilsa — o'chirish uni BOSIB KETMAYDI (1 234 qoladi)",
      r.status_code == 200 and mat(M1) == [_n0[0], 1234.0], (r.status_code, r.text[:120], mat(M1)))
s = SessionLocal()
_it = s.get(Inventory, M1)
_it.stock_quantity, _it.price_per_unit = 100, 1000
s.commit()
s.close()
st, rj = kirim(C, SUP, [(M1, 100, 3000)], hujjat="KB-A6")
_pid = (rj.get("purchase_ids") or [None])[0]
s = SessionLocal()
_p = s.get(InventoryPurchase, _pid)
_p.narx_oldin, _p.narx_keyin = None, None       # eski (kech107 dan oldingi) xarid kabi
s.commit()
s.close()
req(C, "delete", f"/api/inventory/purchases/{_pid}")
check("A6 eski xarid (narx_oldin / narx_keyin NULL) — narx TEGILMAYDI (avvalgi xulq)", mat(M1) == [100.0, 2000.0], mat(M1))
s = SessionLocal()
_it = s.get(Inventory, M1)
_it.stock_quantity, _it.price_per_unit = 100, 1000
s.commit()
s.close()
st, rj = kirim(C, SUP, [(M1, 100, 3000)], hujjat="KB-A7")
_pid = (rj.get("purchase_ids") or [None])[0]
r = req(C, "post", f"/api/inventory/{M1}/stock", json={"quantity_change": -30, "reason": "KB sarf"})
req(C, "delete", f"/api/inventory/purchases/{_pid}")
check("A7 orada SARF (chiqim −30) — narx baribir 1 000 ga qaytadi (sarf narxni o'zgartirmaydi), qoldiq 70",
      r.status_code == 200 and mat(M1) == [70.0, 1000.0], (r.status_code, mat(M1)))
s = SessionLocal()
_it = s.get(Inventory, M1)
_it.stock_quantity, _it.price_per_unit = 100, 1000
s.commit()
s.close()

# ══════════════════════════════════════════════════════════════
section("B — reja (cancel-plan) hech narsani o'zgartirmaydi")
H0 = holat(SUP)
st, rj = kirim(C, SUP, [(M1, 100, 3000), (M2, 50, 2000)], paid_now=150000, transport=20000, tushirish=5000, hujjat="KB-B")
RB = rj.get("receipt_id")
HA = holat(SUP)
r = req(C, "get", f"/api/inventory/receipts/{RB}/cancel-plan")
reja = js(r) or {}
check("B1 reja 200 va hech narsa o'zgarmadi", r.status_code == 200 and holat(SUP) == HA, (r.status_code, r.text[:200]))
_m1 = [m for m in (reja.get("materiallar") or []) if m.get("inventory_id") == M1]
check("B2 rejada Akril: qoldiq 200 → 100, narx 2 000 → 1 000, narx_qaytdi",
      _m1 and (_m1[0].get("joriy_qoldiq"), _m1[0].get("yangi_qoldiq"), _m1[0].get("joriy_narx"), _m1[0].get("yangi_narx"),
               _m1[0].get("narx_qaytdi")) == (200.0, 100.0, 2000.0, 1000.0, True), _m1)
check("B3 rejada qo'shimcha xarajatlar 25 000 (2 qator) va to'lov 150 000",
      reja.get("xarajatlar_jami") == 25000 and len(reja.get("xarajatlar") or []) == 2
      and (reja.get("tolov") or {}).get("summa") == 150000, {k: reja.get(k) for k in ("xarajatlar", "xarajatlar_jami", "tolov")})

# ══════════════════════════════════════════════════════════════
section("D — to'lovli hujjat: 409 → tanlov")
r = req(C, "post", f"/api/inventory/receipts/{RB}/cancel")
_d = (js(r) or {}).get("detail")
check("D1 tanlovsiz — 409 `receipt_has_payment` (summa 150 000) va HECH NARSA o'zgarmadi",
      r.status_code == 409 and isinstance(_d, dict) and _d.get("type") == "receipt_has_payment" and _d.get("summa") == 150000
      and holat(SUP) == HA, (r.status_code, r.text[:200]))
r = req(C, "post", f"/api/inventory/receipts/{RB}/cancel?tolov=xato")
check("D2 noto'g'ri tanlov — 400, o'zgarmadi", r.status_code == 400 and holat(SUP) == HA, (r.status_code, r.text[:160]))
r = req(C, "post", f"/api/inventory/receipts/{RB}/cancel?tolov=ochirish")
HB = holat(SUP)
check("D3 `tolov=ochirish` — 200 va holat hujjatdan OLDINGI bilan AYNAN (ombor, narx, xarajat, to'lov, qarz, hisobot, kassa)",
      r.status_code == 200 and HB == H0, (r.status_code, r.text[:200], farq(H0, HB)))
r = req(C, "post", f"/api/inventory/receipts/{RB}/cancel?tolov=ochirish")
check("D4 takror bekor qilish — 404, o'zgarmadi", r.status_code == 404 and holat(SUP) == H0, (r.status_code, r.text[:120]))
H0 = holat(SUP)
st, rj = kirim(C, SUP, [(M1, 100, 3000)], paid_now=150000, transport=20000, hujjat="KB-D5")
RD = rj.get("receipt_id")
r = req(C, "post", f"/api/inventory/receipts/{RD}/cancel?tolov=avans")
HB = holat(SUP)
_f = farq(H0, HB)
check("D5 `tolov=avans` — faqat to'lov qoldi (ta'minotchida ortiqcha 150 000, kassa −150 000); ombor, narx, xarajat — AYNAN",
      r.status_code == 200 and set(_f) <= {"tolovlar", "kassa", "qarz"} and HB["mat"] == H0["mat"]
      and HB["xarajatlar"] == H0["xarajatlar"] and HB["hisobot"] == H0["hisobot"]
      and (HB["kassa"] or 0) == (H0["kassa"] or 0) - 150000, (r.status_code, _f))
_av = [t for t in HB["tolovlar"] if t[1] == 150000.0 and t[2] not in [x[2] for x in H0["tolovlar"]]]
check("D6 avans izohi \"Kirim to'lovi — #N\" bilan BOSHLANMAYDI (keyingi hujjat uni o'z to'lovi deb olmasin)",
      len(_av) == 1 and not _av[0][2].startswith("Kirim to'lovi — #") and _av[0][2].startswith("Avans"), _av)
st, rj = kirim(C, SUP, [(M2, 10, 100)], hujjat="KB-D7")
RD7 = rj.get("receipt_id")
r = req(C, "get", f"/api/inventory/receipts/{RD7}/cancel-plan")
check("D7 keyingi (to'lovsiz) hujjat rejasida to'lov YO'Q (eski avans — begona)", r.status_code == 200 and (js(r) or {}).get("tolov") is None,
      (js(r) or {}).get("tolov"))

# ══════════════════════════════════════════════════════════════
section("C — to'lovsiz hujjat")
H0 = holat(SUP)
st, rj = kirim(C, SUP, [(M2, 40, 2500)], transport=10000, hujjat="KB-C")
RC = rj.get("receipt_id")
r = req(C, "post", f"/api/inventory/receipts/{RC}/cancel")
check("C1 to'lovsiz hujjat tanlovsiz bekor qilinadi — 200 va holat AYNAN", r.status_code == 200 and holat(SUP) == H0,
      (r.status_code, r.text[:200], farq(H0, holat(SUP))))

# ══════════════════════════════════════════════════════════════
section("E — bir material ikki qatorda + tannarxga qo'shish")
H0 = holat(SUP)
st, rj = kirim(C, SUP, [(M1, 40, 3000), (M2, 50, 2000), (M1, 60, 3500)], add_to_cost=True, transport=30000,
               tushirish=5000, paid_now=100000, hujjat="KB-E")
RE = rj.get("receipt_id")
check("E0 kirim: Akril narxi ikki marta o'zgardi", st == 200 and mat(M1)[1] != H0["mat"][M1][1], (st, mat(M1)))
_s = mat(M1)[0]
r = req(C, "get", f"/api/inventory/receipts/{RE}/cancel-plan")
_m1 = [m for m in ((js(r) or {}).get("materiallar") or []) if m.get("inventory_id") == M1]
check("E2 REJA ham ketma-ket: Akril 2 qator — oxirgisi joriy qoldiqdan (−60), birinchisi undan keyingidan (−40); "
      "yakuniy narx boshlang'ich",
      r.status_code == 200 and len(_m1) == 2 and _m1[1].get("joriy_qoldiq") == _s and _m1[1].get("yangi_qoldiq") == _s - 60
      and _m1[0].get("joriy_qoldiq") == _s - 60 and _m1[0].get("yangi_qoldiq") == _s - 100
      and _m1[0].get("yangi_narx") == H0["mat"][M1][1], (r.status_code, _s, _m1))
r = req(C, "post", f"/api/inventory/receipts/{RE}/cancel?tolov=ochirish")
check("E1 bekor — narx ketma-ket (oxirgi qatordan) AYNAN boshlang'ichga, holat AYNAN",
      r.status_code == 200 and holat(SUP) == H0, (r.status_code, farq(H0, holat(SUP))))

# ══════════════════════════════════════════════════════════════
section("F — oraliq sarf va manfiy qoldiq")
H0 = holat(SUP)
st, rj = kirim(C, SUP, [(M1, 100, 3000)], hujjat="KB-F")
RF = rj.get("receipt_id")
req(C, "post", f"/api/inventory/{M1}/stock", json={"quantity_change": -150, "reason": "KB katta sarf"})
s = SessionLocal()
try:
    _hmax = max([h.id for h in s.query(InventoryMovement).all()] or [0])
finally:
    s.close()
r = req(C, "get", f"/api/inventory/receipts/{RF}/cancel-plan")
check("F1 reja: qoldiq manfiyga tushadi — `manfiy` ro'yxatida Akril", r.status_code == 200 and "KB Akril" in ((js(r) or {}).get("manfiy") or []),
      (js(r) or {}).get("manfiy"))
r = req(C, "post", f"/api/inventory/receipts/{RF}/cancel")
check("F2 bekor — qoldiq −50 (arifmetik, 20-band), narx boshlang'ich 1 000",
      r.status_code == 200 and mat(M1) == [H0["mat"][M1][0] - 150, H0["mat"][M1][1]], (r.status_code, mat(M1)))
s = SessionLocal()
try:
    _h = s.query(InventoryMovement).filter(InventoryMovement.inventory_id == M1, InventoryMovement.id > _hmax,
                                           InventoryMovement.reason.like(f"Kirim #{RF} bekor qilindi%")).all()
    _hr = [(h.movement_type, float(h.quantity), h.reason) for h in _h]
finally:
    s.close()
check("F3 jurnalda chiqim yozuvi (100 kg) va manfiy ogohlantirishi", len(_hr) == 1 and _hr[0][0] == "out" and _hr[0][1] == 100.0
      and "manfiy" in _hr[0][2], _hr)
req(C, "post", f"/api/inventory/{M1}/stock", json={"quantity_change": 150, "reason": "KB tiklash"})

# ══════════════════════════════════════════════════════════════
section("G — izolyatsiya")
s = SessionLocal()
try:
    _rid_max = max([r.id for r in s.query(InventoryReceipt).all()] or [0])
finally:
    s.close()
st, rj = kirim(C, SUP, [(M2, 5, 100)], transport=7000, hujjat="KB-G")
RG = rj.get("receipt_id")
s = SessionLocal()
s.add(ExpenseTransaction(company_id=1, category="transport_kirim", amount=1111, source="inventory_receipt",
                         notes=f"Transport (kirim) — Kirim #{RG}0 (boshqa hujjat)", created_by="KB"))
s.add(ExpenseTransaction(company_id=2, category="transport_kirim", amount=2222, source="inventory_receipt",
                         notes=f"Transport (kirim) — Kirim #{RG}", created_by="KB B"))
s.add(ExpenseTransaction(company_id=1, category="arenda", amount=3333, source="manual",
                         notes=f"Kirim #{RG} haqida qo'lda yozilgan izoh", created_by="KB"))
# Har filtr ALOHIDA tekshirilsin (mutatsiya): tur mos, manba qo'lda — va manba mos, tur boshqa.
s.add(ExpenseTransaction(company_id=1, category="transport_kirim", amount=4444, source="manual",
                         notes=f"Transport — Kirim #{RG} (qo'lda yozilgan)", created_by="KB"))
s.add(ExpenseTransaction(company_id=1, category="arenda", amount=5555, source="inventory_receipt",
                         notes=f"Kirim #{RG} — boshqa turdagi yozuv", created_by="KB"))
# Shu ta'minotchiga BOSHQA hujjat ("#N0") to'lovi — bu hujjatniki emas (tanlovsiz bekor qilinadi, to'lov tegilmaydi).
s.add(SupplierPayment(supplier_id=SUP, amount=6666, notes=f"Kirim to'lovi — #{RG}0 (boshqa hujjat)", paid_by="KB"))
s.commit()
s.close()
r = req(CB, "get", f"/api/inventory/receipts/{RG}/cancel-plan")
r2 = req(CB, "post", f"/api/inventory/receipts/{RG}/cancel?tolov=ochirish")
check("G1 B korxona admini A hujjatini ko'ra / bekor qila olmaydi (404)", r.status_code == 404 and r2.status_code == 404,
      (r.status_code, r2.status_code))
r = req(C, "post", f"/api/inventory/receipts/{RG}/cancel")
s = SessionLocal()
try:
    _q = sorted((t.company_id, float(t.amount), t.notes) for t in s.query(ExpenseTransaction).filter(
        ExpenseTransaction.amount.in_([1111, 2222, 3333, 4444, 5555, 7000])).all())
    _tp = [(float(t.amount), t.notes) for t in s.query(SupplierPayment).filter(SupplierPayment.amount == 6666).all()]
finally:
    s.close()
check("G2 faqat O'Z xarajati (7 000) o'chdi: \"#N0\" (boshqa hujjat), B korxonaniki, qo'lda yozilgan (tur mos ham) va "
      "boshqa tur — TEGILMADI",
      r.status_code == 200 and sorted(x[1] for x in _q) == [1111.0, 2222.0, 3333.0, 4444.0, 5555.0], (r.status_code, r.text[:160], _q))
check("G3 boshqa hujjat to'lovi (\"Kirim to'lovi — #N0\") — bu hujjatniki emas: tanlovsiz bekor qilindi, to'lov izohi AYNAN",
      r.status_code == 200 and _tp == [(6666.0, f"Kirim to'lovi — #{RG}0 (boshqa hujjat)")], (r.status_code, _tp))

# ══════════════════════════════════════════════════════════════
section("H — audit")
s = SessionLocal()
try:
    _a = [(a.action, a.entity_type, a.entity_label, a.new_value) for a in s.query(ActivityLog).filter(
        ActivityLog.entity_type == "inventory_receipt").all()]
finally:
    s.close()
check("H1 har bekor qilish audit jurnalida (\"Kirim hujjati #N\", material soni, xarajat, to'lov amali)",
      len(_a) >= 5 and all(x[0] == "deleted" and (x[2] or "").startswith("Kirim hujjati #") for x in _a)
      and any("avans" in (x[3] or "") for x in _a) and any("o'chirildi" in (x[3] or "") for x in _a), _a[:3])

# ══════════════════════════════════════════════════════════════
section("I — PG: parallel ikki bekor qilish")
if PG_URL:
    H0 = holat(SUP)
    st, rj = kirim(C, SUP, [(M1, 100, 3000)], paid_now=50000, hujjat="KB-I")
    RI = rj.get("receipt_id")
    _bar = threading.Barrier(2)
    _nat = []

    def _ish():
        _s = SessionLocal()
        try:
            _bar.wait(timeout=10)
            with crud.bitta_tranzaksiya(_s):
                _r = crud.kirim_hujjatini_bekor_qilish(_s, RI, company_id=1, tolov="ochirish", performed_by="KB")
            _nat.append("OK" if _r else "YOQ")
        except Exception as e:             # noqa: BLE001
            _nat.append(f"{type(e).__name__}")
        finally:
            _s.close()
    _t = [threading.Thread(target=_ish) for _ in range(2)]
    for t in _t:
        t.start()
    for t in _t:
        t.join(30)
    check("I1 bittasi bekor qildi, ikkinchisi topmadi — ombor / narx / to'lov BIR marta qaytdi (holat AYNAN)",
          sorted(_nat) == ["OK", "YOQ"] and holat(SUP) == H0, (_nat, farq(H0, holat(SUP))))
else:
    print("  (SQLite — o'tkazildi: haqiqiy parallellik yo'q)")

# ══════════════════════════════════════════════════════════════
section("J — statik")
_c = fayl("crud.py")
check("J1 xarid yozuvida `narx_oldin` / `narx_keyin` (yaratishda)",
      tartibda(_c, "def _purchase_stock_no_commit(", "narx_oldin=round(old_price, 2)", "narx_keyin=round(float(db_item.price_per_unit or 0), 2)"), "")
_i = _c.find("def delete_purchase(")
check("J2 `delete_purchase` narxni `_xarid_narxini_qaytar` bilan", "_xarid_narxini_qaytar(inv.price_per_unit, p)" in _c[_i:_i + 4000], "")
_i = _c.find("def kirim_hujjatini_bekor_qilish(")
_fn = _c[_i:_c.find("\ndef ", _i + 10)] if _i >= 0 else ""
check("J3 bekor qilish: tanlov tekshiruvi HECH NARSA o'zgartirilishidan OLDIN, oxirgi qatordan boshlab",
      tartibda(_fn, "raise KirimTolovTanloviKerak(", "for p in reversed(qism[\"xaridlar\"]):", "db.delete(p)", "db.delete(receipt)"), "")
_m = fayl("main.py")
check("J4 marshrutlar: reja (GET, faqat_hisob) va amal (POST, bitta_tranzaksiya, 409 receipt_has_payment)",
      tartibda(_m, '@app.get("/api/inventory/receipts/{receipt_id}/cancel-plan")', "faqat_hisob=True",
               '@app.post("/api/inventory/receipts/{receipt_id}/cancel")', "with crud.bitta_tranzaksiya(db):",
               '"type": "receipt_has_payment"'), "")
_mo = fayl("models.py")
check("J5 model: `narx_oldin` / `narx_keyin` NULL bo'la oladi, `default=` YO'Q (eski xaridlar — NULL)",
      "narx_oldin = Column(Numeric(12, 2), nullable=True)" in _mo and "narx_keyin = Column(Numeric(12, 2), nullable=True)" in _mo, "")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   -", f)

try:
    from database import engine as _eng
    _eng.dispose()
except Exception:                          # noqa: BLE001
    pass
if PG_URL:
    try:
        from sqlalchemy import create_engine as _ce2, text as _tx2
        _adm = _ce2(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
                    isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c2:
            _c2.execute(_tx2(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass
else:
    try:
        os.remove(_DB)
    except OSError:
        pass
sys.exit(1 if FAIL else 0)
