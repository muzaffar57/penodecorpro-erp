#!/usr/bin/env python3
"""
test_tayyor_reja_loy.py — kech112 darvozasi: K112-3 — «Tayyor» da haqiqiy loy kiritilmasa, qoplama xarajati foydadan
tushib qolardi.

NIMA UCHUN KERAK (kech112 jonli C zanjirida topildi; asl kod `5519200` da O'LCHANDI — `work/k113/probe_qoplama.py`,
SQLite = PG): qoplamali buyurtma (20 kg loy, retsept) «Tayyor» qilinganda loy maydoni BO'SH qoldirilsa (yoki API
`loy_kg` siz chaqirilsa) `services.complete_order` "Reja bo'yicha hisoblandi" derdi, ombor ham rejadagi loyni
ishlatilgan deb qoldirardi, lekin `orders.actual_loy_kg` va izohdagi `loy_kg=` YOZILMASDI. Buyurtma foydasi
(`services.calculate_order_profit` — oylik hisobot, usta KPI, foyda oynasi) loyni faqat shu ikkisidan o'qiydi —
qoplama xarajati 0 bo'lib, foyda ~30 000 so'mga ortiq chiqardi (20 kg × ~1 500 so'm/kg). Loy KIRITILGANDA
(UI oynasi rejani oldindan to'ldiradi) hammasi to'g'ri edi — shuning uchun `main` da bunday buyurtma yo'q (5 / 5).

YECHIM (texnik — Claude): «kiritilmadi» tarmog'ida reja haqiqiy loy sifatida yoziladi (`actual_loy_kg`, izohda
`loy_kg=`) — kiritilgan miqdor bilan AYNAN bir xil natija.

BO'LIMLAR: R — «Tayyor» (bo'sh / kiritilgan / ko'p / qisman / qoplamasiz), P — paritet (bo'sh = kiritilgan reja),
H — oylik hisobot, S — statik.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
    python3 tools/test_tayyor_reja_loy.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tayyor_reja_loy.py
Asl kodga qarshi QULAMAYDI (HTTP istisno → 599, yangi nomlar `getattr`). Chiqish kodi 0 — hammasi o'tdi.
"""
import os
import sys
import inspect
import tempfile
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tayyor_reja_loy_test"
_T = tempfile.mkdtemp()
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tayyor_reja_loy_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import UserRole, Order, Inventory      # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        detail = f"{detail} [{type(e).__name__}: {e}]"
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


def tartibda(src, *qismlar):
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


# ══════════════════════════════════════════════════════════════
# Fikstura: korxona 1 admini, materiallar (kirim — qo'shimcha xarajat tannarxga), qoplama retsepti, loyiha
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "TRL_A", "Parol123!", UserRole.ADMIN, "Reja Loy Admin", company_id=1)
_db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "TRL_A", "password": "Parol123!"}, follow_redirects=False)
check("F0 admin tizimga kirdi", _lr.status_code == 302, _lr.status_code)
XATO5 = []


def so(metod, url, **k):
    r = req(C, metod, url, **k)
    if r.status_code >= 500:
        XATO5.append((metod, url, r.status_code, getattr(r, "text", "")[:200]))
    return r


ID = {}
for _k, _tana in (("peno", {"item_name": "TRL Penoplast", "category": "Penoplast", "unit": "blok", "is_penoplast": True,
                             "is_default_penoplast": True, "volume_per_unit": 1.0}),
                  ("kley", {"item_name": "TRL Kley", "category": "Kimyoviy qo'shimchalar", "unit": "kg"}),
                  ("qum", {"item_name": "TRL Qum", "category": "Qattiq qotishmalar", "unit": "kg"})):
    ID[_k] = (js(so("post", "/api/inventory", json=_tana)) or {}).get("id")
_kr = so("post", "/api/inventory/receipt", json={
    "items": [{"inventory_id": ID["peno"], "quantity": 20, "price_per_unit": 600000, "volume_per_unit": 1.0},
              {"inventory_id": ID["kley"], "quantity": 400, "price_per_unit": 3000},
              {"inventory_id": ID["qum"], "quantity": 1000, "price_per_unit": 800}],
    "paid_now": 0, "transport_cost": 150000, "tushirish_cost": 50000, "add_to_cost": True, "production_type": "umumiy"})
check("F1 kirim hujjati (qo'shimcha xarajat tannarxga)", _kr.status_code == 200, _kr.text[:200])
ID["retsept"] = (js(so("post", "/api/recipes", json={
    "name": "TRL Qoplama", "batch_size_kg": 100,
    "ingredients": [{"inventory_id": ID["kley"], "quantity_kg": 30}, {"inventory_id": ID["qum"], "quantity_kg": 70}]})) or {}).get("id")
ID["loyiha"] = (js(so("post", "/api/projects", json={"project_name": "TRL Loyiha", "client_name": "TRL Mijoz"})) or {}).get("id")
check("F2 materiallar, retsept, loyiha yaratildi", all(ID.get(k) for k in ("peno", "kley", "qum", "retsept", "loyiha")), ID)


def buyurtma(nom, qoplamali=True, loy=20):
    """Profil (qoplamali) + panel; reja loyi `loy` kg (qoplamasiz buyurtmada — yo'q)."""
    tana = {"project_id": ID["loyiha"], "order_type": "product", "recipe_id": ID["retsept"] if qoplamali else None,
            "deadline": "2026-10-10", "is_draft": False, "base_price": 600000, "loy_kg": loy if qoplamali else None,
            "items": [{"name": f"{nom} Karniz", "category": "profil", "width": 20, "thickness": 15, "length": 30,
                       "quantity": 1, "unit_price": 540000 if qoplamali else 270000, "is_coated": qoplamali,
                       "penoplast_id": ID["peno"], "sub_details": []},
                      {"name": f"{nom} Panel", "category": "panel", "width": 60, "thickness": 5, "length": 0,
                       "quantity": 20, "unit_price": 18000, "is_coated": False, "penoplast_id": ID["peno"]}]}
    r = so("post", "/api/orders", json=tana)
    o = js(r) or {}
    oid = o.get("id")
    if oid and qoplamali:
        so("post", f"/api/orders/{oid}/coating-notify", params={"loy_kg": loy})
    items = sorted(o.get("items") or [], key=lambda x: x.get("id", 0))
    return oid, [x.get("id") for x in items]


def yetkaz(oid, faqat=None):
    ds = js(so("get", f"/api/orders/{oid}/delivery-status")) or {}
    its = [{"order_item_id": x["id"], "quantity": x["remaining"]} for x in (ds.get("items") or [])
           if x.get("remaining", 0) > 0 and (faqat is None or x["id"] in faqat)]
    return so("post", "/api/deliveries", json={"order_id": oid, "items": its})


def holat(oid):
    s = SessionLocal()
    try:
        o = s.get(Order, oid)
        return {"actual": (float(o.actual_loy_kg) if o.actual_loy_kg is not None else None), "notes": o.notes or "",
                "status": str(getattr(o.status, "value", o.status))}
    finally:
        s.close()


def foyda(oid):
    s = SessionLocal()
    try:
        return services.calculate_order_profit(s, oid, company_id=1)
    finally:
        s.close()


def qoplama_qatori(f):
    return next((b for b in (f.get("breakdown") or []) if str(b.get("nomi", "")).startswith("Qoplama (")), None)


def narx(iid):
    s = SessionLocal()
    try:
        return float(s.get(Inventory, iid).price_per_unit or 0)
    finally:
        s.close()


def qoldiq(iid):
    s = SessionLocal()
    try:
        return float(s.get(Inventory, iid).stock_quantity or 0)
    finally:
        s.close()


KG_NARX = 0.3 * narx(ID["kley"]) + 0.7 * narx(ID["qum"])   # 1 kg loy (retsept 30 / 70, kirim narxida)

# ══════════════════════════════════════════════════════════════
section("R. «Tayyor» — loy maydoni BO'SH (reja bo'yicha)")
O1, I1 = buyurtma("TRL1")
check("R0 buyurtma 1 yaratildi (2 detal)", O1 and len(I1) == 2, (O1, I1))
yetkaz(O1)
_k0, _q0 = qoldiq(ID["kley"]), qoldiq(ID["qum"])
r = so("post", f"/api/orders/{O1}/ready")
d = js(r) or {}
check("R1 «Tayyor» (loy_kg siz) → 200", r.status_code == 200, r.text[:300])
check("R2 javob: «Reja bo'yicha hisoblandi», actual = reja 20", (d.get("loy_info") or {}).get("actual") == 20
      and (d.get("loy_info") or {}).get("action") == "teng", d.get("loy_info"))
h1 = holat(O1)
check("R3 buyurtma READY", h1["status"] == "ready", h1)
check("R4 `actual_loy_kg` = 20 (reja haqiqiy loy sifatida yozildi)", h1["actual"] == 20.0, h1)
check("R5 izohda `loy_kg=20.0` (kiritilgandagi kabi)", "loy_kg=20.0" in h1["notes"], h1["notes"])
check("R6 ombor o'zgarmadi (reja allaqachon yechilgan — qo'shimcha yechish / qaytarish yo'q)",
      abs(qoldiq(ID["kley"]) - _k0) < 1e-9 and abs(qoldiq(ID["qum"]) - _q0) < 1e-9,
      (_k0, qoldiq(ID["kley"]), _q0, qoldiq(ID["qum"])))
f1 = foyda(O1)
q1 = qoplama_qatori(f1)
check("R7 foyda breakdownida «Qoplama (20 kg loy …)» qatori BOR", q1 is not None and "20 kg loy" in str(q1.get("nomi")),   # kech119 (G2-15): son_korinish
      f1.get("breakdown"))
check("R8 qoplama summasi = 20 kg × (0.3 × Kley + 0.7 × Qum) narxi (tiyingacha)",
      q1 is not None and abs(float(q1.get("summa", 0)) - 20 * KG_NARX) < 0.02, (q1, 20 * KG_NARX))
check("R9 tan narxi = breakdown yig'indisi (qoplama ichida)",
      abs(float(f1.get("tan_narxi", 0)) - sum(float(b.get("summa", 0)) for b in (f1.get("breakdown") or []))) < 0.01, f1)

section("P. Paritet: bo'sh maydon = rejani kiritgandek")
O2, I2 = buyurtma("TRL2")
yetkaz(O2)
r = so("post", f"/api/orders/{O2}/ready", params={"loy_kg": 20})
check("P1 «Tayyor» (loy_kg=20 kiritilgan) → 200", r.status_code == 200, r.text[:200])
h2, f2 = holat(O2), foyda(O2)
check("P2 `actual_loy_kg` AYNAN (bo'sh ↔ kiritilgan)", h2["actual"] == h1["actual"], (h1, h2))
check("P3 izoh AYNAN (buyurtma raqamidan tashqari)", h2["notes"] == h1["notes"], (h1["notes"], h2["notes"]))
check("P4 tan narxi va foyda AYNAN", abs(float(f2.get("tan_narxi", 0)) - float(f1.get("tan_narxi", 0))) < 0.01
      and abs(float(f2.get("foyda", 0)) - float(f1.get("foyda", 0))) < 0.01, (f1.get("tan_narxi"), f2.get("tan_narxi")))

section("R. Kiritilgan KO'P loy (avvalgi qoida o'zgarmagan)")
O3, I3 = buyurtma("TRL3")
yetkaz(O3)
_k0, _q0 = qoldiq(ID["kley"]), qoldiq(ID["qum"])
r = so("post", f"/api/orders/{O3}/ready", params={"loy_kg": 25})
d = js(r) or {}
check("R10 «Tayyor» (25 kg) → 200, «qoshimcha» 5 kg", r.status_code == 200 and (d.get("loy_info") or {}).get("diff") == 5.0, d)
check("R11 5 kg loy ingredientlari yechildi (Kley −1.5, Qum −3.5)",
      abs((_k0 - qoldiq(ID["kley"])) - 1.5) < 1e-6 and abs((_q0 - qoldiq(ID["qum"])) - 3.5) < 1e-6,
      (_k0 - qoldiq(ID["kley"]), _q0 - qoldiq(ID["qum"])))
q3 = qoplama_qatori(foyda(O3))
check("R12 foyda: «Qoplama (25 kg loy …)»", q3 is not None and "25 kg loy" in str(q3.get("nomi")), q3)

section("R. Qisman topshirilgan buyurtma, loy BO'SH")
O4, I4 = buyurtma("TRL4")
yetkaz(O4, faqat=[I4[1]])          # faqat panel — profil (qoplamali) topshirilmagan
_p0 = qoldiq(ID["peno"])
r = so("post", f"/api/orders/{O4}/ready")
h4 = holat(O4)
check("R13 qisman «Tayyor» (loy_kg siz) → 200", r.status_code == 200, r.text[:200])
check("R14 qisman: `actual_loy_kg` = reja 20 (loy ingredientlari qaytmadi — reja ishlatilgan deb)", h4["actual"] == 20.0, h4)
check("R15 qisman: topshirilmagan profil penoplasti qaytdi (+0.45 blok)", abs((qoldiq(ID["peno"]) - _p0) - 0.45) < 1e-6,
      qoldiq(ID["peno"]) - _p0)
q4 = qoplama_qatori(foyda(O4))
check("R16 qisman: foydada «Qoplama (20 kg loy …)»", q4 is not None and "20 kg loy" in str(q4.get("nomi")), q4)

section("R. Qoplamasiz buyurtma (reja loyi yo'q) — o'zgarmagan")
O5, I5 = buyurtma("TRL5", qoplamali=False)
yetkaz(O5)
r = so("post", f"/api/orders/{O5}/ready")
h5 = holat(O5)
check("R17 qoplamasiz «Tayyor» → 200", r.status_code == 200, r.text[:200])
check("R18 qoplamasiz: `actual_loy_kg` bo'sh, izohda `loy_kg=` YO'Q", h5["actual"] is None and "loy_kg=" not in h5["notes"], h5)
check("R19 qoplamasiz: foydada qoplama qatori YO'Q", qoplama_qatori(foyda(O5)) is None, foyda(O5).get("breakdown"))

section("H. Oylik hisobot — buyurtmalar foydasi qoplamani o'z ichiga oladi")
_tk = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
_s = SessionLocal()
try:
    rep = services.get_monthly_report(_s, _tk.year, _tk.month, company_id=1)
finally:
    _s.close()
_kutilgan = sum(float(foyda(o).get("foyda", 0)) for o in (O1, O2, O3, O4, O5))
check("H1 `buyurtmalar_foydasi` = 5 buyurtma foydasi yig'indisi (qoplama bilan)",
      abs(float(rep.get("buyurtmalar_foydasi", 0)) - _kutilgan) <= 3, (rep.get("buyurtmalar_foydasi"), _kutilgan))
check("H2 R1 buyurtmasi foydasi ≠ qoplamasiz holatdagi (qoplama ~30 000 ayrilgan)",
      abs((float(f1.get("sotuv_narxi", 0)) - float(f1.get("tan_narxi", 0))) - float(f1.get("foyda", 0))) < 0.01
      and q1 is not None and float(q1.get("summa", 0)) > 29000, f1)
check("H3 hech bir so'rov 500 bermadi", not XATO5, XATO5)

section("S. Statik")
_co = manba(services, "complete_order")
check("S1 `complete_order` — «kiritilmadi» tarmog'i rejani `actual_loy_kg` ga yozadi",
      tartibda(_co, "elif planned_loy > 0:", "Reja bo'yicha hisoblandi", "order.actual_loy_kg = planned_loy"))
check("S2 `complete_order` — «kiritilmadi» tarmog'i izohga `loy_kg=` yozadi (kiritilgandagi format)",
      tartibda(_co, "elif planned_loy > 0:", 'f", loy_kg={float(planned_loy)}"'))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
