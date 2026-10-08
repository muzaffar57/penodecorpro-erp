#!/usr/bin/env python3
"""
test_material_narx.py — kech127 (zip 150): «XOMASHYO NARXLARI VA OMBOR QIYMATI» RUXSATI (egasi QARORI 07.10 20:1x, tugmali,
QAYTA SO'RALMAYDI: «Ulugbek va Mirjalol (Menejer) xomashyo xarid narxlari va «Ombor qiymati» ni ham ko'rmasin»).

NIMA UCHUN KERAK
  Menejer sahifada narxni ko'rmasdi (Omborxona narx ustuni, «Ombor qiymati», «Xaridlar tarixi» — boshqa ruxsat sharti bilan
  yashirin), lekin server narxni uning brauzeriga baribir yuborardi: `…/api/inventory` manzili — «Akril 19000», `…/api/inventory/kpi`
  — ombor qiymati 41 942 630 (O'LCHANGAN — `main` nusxasi, Ulugbek nomidan: `work/narx127.py`); Buyurtmalar / Tayyor mahsulotlar
  sahifasi manbasida penoplast narxi. Endi: alohida band `material_narx` (faqat Ko'rish); yo'q bo'lsa (va «Tannarx va foyda» ham
  yo'q bo'lsa) server shu narxlarni null qiladi (`ruxsatlar.narx_tozala`, `main._TannarxHimoyasi`), sahifalar ko'rsatmaydi.
TALAB (har biri o'lchanadi):
  S  `narx_tozala` (faqat marshrut yo'llari, boshqa maydon / marshrut tegilmaydi), `narx_koradi` (band YOKI tannarx; Admin — doim),
     `material_narx_kerakmi` (migratsiya qoidasi);
  K  band katalogda (Omborxona, faqat Ko'rish), tayyor rollar: Admin / Omborchi / Moliyachi — bor, Menejer — yo'q; NARX_YOLLAR —
     haqiqiy GET marshrutlar; himoya ulangan;
  A  HAQIQIY HTTP, har GET /api: «Narxsiz» (band ham, tannarx ham yo'q) javobi = «Tannarxsiz» (band bor) javobi + `narx_tozala`
     (boshqa hech qanday farq yo'q), holat kodlari bir xil; «Faqat tannarx» (band yo'q, tannarx bor) = «Hammasi» AYNAN;
     majburiy yashirinlar — «Tannarxsiz» da son, «Narxsiz» da null;
  V  QIYMAT bo'yicha qidiruv (kalit nomiga tayanmaydi): tayyor Menejer va «Ombor narxsiz» rol (Omborxona to'liq, narxsiz) — HECH
     BIR GET /api javobida xomashyo narxi, xarid narxi / summasi, ombor qiymati yo'q; Omborchi va Admin — ko'radi;
  H  sahifalar: Omborxona — «Ombor qiymati» / narx ustuni faqat narx ko'radiganga, narx tahriri — qo'shimcha «Materiallar:
     Tahrirlash» bilan (H8 — tannarx bor, tahrir yo'q); Buyurtmalar (`PENOPLASTS`) va
     Tayyor mahsulotlar (`PENOS`) manbasida penoplast narxi — ko'rmaydiganga 0;
  J  Omborxona xarid tarixi: null narx / summa — «—», «× narx» yozilmaydi (JS funksiyalari node da), eski `fmt(narx)` yo'q;
  M  migratsiya: mavjud rollar qoidaga ko'ra (Omborchi, Moliyachi, kirim / material yozuvchi, ta'minotchi / Moliya ko'ruvchi — ha;
     Menejer, faqat ko'ruvchi, faqat tannarx — yo'q), korxona belgisi, ikkinchi ishga tushish — hech narsa, admin o'chirgani qayta
     qo'shilmaydi, rollari hozirgi andozadan yaratilgan korxona — belgi darhol (o'zi yaratgan rolga tegilmaydi).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16.
ISHLATISH: python3 tools/test_material_narx.py
"""
import os
import re
import sys
import json
import shutil
import tempfile
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "material_narx_test"
_T = tempfile.mkdtemp(prefix="mnarx_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'material_narx_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import copy                                        # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import ruxsatlar as RX                             # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol, Inventory, CompanySetting   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from fastapi.routing import APIRoute               # noqa: E402

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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def xavfsiz(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return e


def barglar(x, yol="", acc=None):
    acc = acc if acc is not None else {}
    if isinstance(x, dict):
        for k, v in x.items():
            barglar(v, f"{yol}.{k}" if yol else str(k), acc)
        if not x and yol:
            acc[yol] = {}
    elif isinstance(x, list):
        for i, v in enumerate(x):
            barglar(v, f"{yol}[{i}]", acc)
        if not x and yol:
            acc[yol] = []
    else:
        acc[yol] = x
    return acc


def umumiy(yol):
    return re.sub(r"\[\d+\]", "[]", yol)


def marshrutlar(routes):
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif type(r).__name__ == "_IncludedRouter":
            yield from marshrutlar(r.original_router.routes)


API = [r for r in marshrutlar(main.app.routes) if r.path.startswith("/api/")]
API_YOLLAR = {r.path for r in API}
NARX_YOLLAR = getattr(RX, "NARX_YOLLAR", {})
narx_tozala = getattr(RX, "narx_tozala", None)
narx_koradi = getattr(RX, "narx_koradi", None)
kerakmi = getattr(RX, "material_narx_kerakmi", None)
KALIT = getattr(RX, "NARX_MIGRATSIYA_KALITI", "rx_material_narx")
MIG = getattr(main, "_migrate_material_narx_ruxsati", None)


def tozala(d, p):
    return narx_tozala(d, p) if narx_tozala else d


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. narx_tozala / narx_koradi / material_narx_kerakmi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
d = [{"id": 1, "item_name": "K", "price_per_unit": 13579.0, "stock_quantity": 5, "unit": "kg"}]
tozala(d, "/api/inventory")
check("S1 /api/inventory — price_per_unit null, qoldiq / nom joyida",
      d == [{"id": 1, "item_name": "K", "price_per_unit": None, "stock_quantity": 5, "unit": "kg"}], d)
k = {"total_items": 3, "low_count": 1, "total_value": 6233985.0, "today_in_count": 2}
tozala(k, "/api/inventory/kpi")
check("S2 /api/inventory/kpi — total_value null, sonlar joyida",
      k == {"total_items": 3, "low_count": 1, "total_value": None, "today_in_count": 2}, k)
ps = {"year": 2026, "month": 10, "total_amount": 5, "purchase_count": 2,
      "by_material": [{"name": "K", "quantity": 1.0, "total": 5, "unit": "kg", "avg_price": 5}]}
tozala(ps, "/api/inventory/purchase-stats")
check("S3 purchase-stats — jami, material bo'yicha jami va o'rtacha narx null; miqdor / son joyida",
      ps == {"year": 2026, "month": 10, "total_amount": None, "purchase_count": 2,
             "by_material": [{"name": "K", "quantity": 1.0, "total": None, "unit": "kg", "avg_price": None}]}, ps)
pu = [{"id": 3, "quantity": 2, "price_per_unit": 7, "total_amount": 14, "receipt_id": 9}]
tozala(pu, "/api/inventory/purchases")
check("S4 purchases — narx va summa null, miqdor / hujjat joyida",
      pu == [{"id": 3, "quantity": 2, "price_per_unit": None, "total_amount": None, "receipt_id": 9}], pu)
pt = {"months": [{"year": 2026, "month": 9, "total": 4}]}
tozala(pt, "/api/inventory/purchase-trend")
check("S5 purchase-trend — oy jami null", pt == {"months": [{"year": 2026, "month": 9, "total": None}]}, pt)
pp = {"items": [{"id": 1, "name": "P", "stock": 2, "price_per_unit": 735197.0}], "default_id": 1}
tozala(pp, "/api/penoplasts")
check("S6 penoplasts — narx null, qoldiq joyida",
      pp == {"items": [{"id": 1, "name": "P", "stock": 2, "price_per_unit": None}], "default_id": 1}, pp)
lc = {"cost_per_kg": 3.0, "recipe": "R", "breakdown": [{"name": "K", "kg_per_batch": 30, "price": 13579.0}]}
tozala(lc, "/api/loy-cost")
check("S7 loy-cost — tarkib narxi null (1 kg tannarxi — o'z qatlami, `tannarx_tozala`)",
      lc == {"cost_per_kg": 3.0, "recipe": "R", "breakdown": [{"name": "K", "kg_per_batch": 30, "price": None}]}, lc)
o = [{"id": 1, "items": [{"unit_price": 20000, "price_per_unit": 5}]}]
tozala(o, "/api/orders")
check("S8 boshqa marshrut (buyurtmalar — sotuv narxi) — TEGILMAYDI", o == [{"id": 1, "items": [{"unit_price": 20000,
                                                                                                "price_per_unit": 5}]}], o)


class _U:
    def __init__(self, admin=False, r=None):
        self.role = type("R", (), {"value": "admin" if admin else "manager"})()
        self.rol_id = None
        self.company_id = 1
        self.__dict__["_ruxsat_kesh"] = None if admin else r


check("S9 narx_koradi: Admin — ha; band — ha; faqat tannarx — ha; ikkalasi yo'q — yo'q",
      narx_koradi is not None and narx_koradi(_U(True)) and narx_koradi(_U(r={"material_narx": {"korish"}}))
      and narx_koradi(_U(r={"tannarx": {"korish"}})) and not narx_koradi(_U(r={"material": {"korish"}, "kirim": {"korish"}})))
_kq = [("omborchi", {}), ("moliyachi", {}), (None, {"kirim": {"yaratish"}}), (None, {"material": {"tahrirlash"}}),
       (None, {"kirim": {"ochirish"}}), (None, {"taminotchi": {"korish"}}), (None, {"moliya": {"korish"}})]
_kyoq = [("menejer", {"material": {"korish"}, "kirim": {"korish"}}), ("admin", {}), ("usta", {}),
         (None, {"material": {"korish"}, "kirim": {"korish"}, "buyurtma": {"korish"}}), (None, {"tannarx": {"korish"}}),
         (None, {})]
check("S10 material_narx_kerakmi: narx bilan ishlaydigan rol — ha (7 holat), faqat ko'ruvchi / Menejer / faqat tannarx — yo'q",
      kerakmi is not None and all(kerakmi(a, b) for a, b in _kq) and not any(kerakmi(a, b) for a, b in _kyoq),
      [(a, b, kerakmi(a, b) if kerakmi else None) for a, b in _kq + _kyoq])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Katalog va ulanish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
b = RX.BANDLAR.get("material_narx") or {}
check("K1 band `material_narx` — Omborxona bo'limida, faqat Ko'rish, nomi «Xomashyo narxlari va ombor qiymati»",
      b.get("modul") == "ombor" and tuple(b.get("amallar") or ()) == ("korish",)
      and b.get("nom") == "Xomashyo narxlari va ombor qiymati", b)
_tr = RX.TAYYOR_ROLLAR
check("K2 tayyor rollar: Admin / Omborchi / Moliyachi — bor; Menejer — yo'q (egasi qarori)",
      "material_narx" in _tr["admin"]["ruxsatlar"] and "material_narx" in _tr["omborchi"]["ruxsatlar"]
      and "material_narx" in _tr["moliyachi"]["ruxsatlar"] and "material_narx" not in _tr["menejer"]["ruxsatlar"]
      and "xomashyo narxlari" in _tr["menejer"]["tavsif"], {k: v["ruxsatlar"].get("material_narx") for k, v in _tr.items()})
_yoq = sorted(set(NARX_YOLLAR) - API_YOLLAR)
check("K3 NARX_YOLLAR dagi har marshrut — haqiqiy GET API marshruti, kamida 7 ta",
      len(NARX_YOLLAR) >= 7 and not _yoq
      and all(any(r.path == p and "GET" in r.methods for r in API) for p in NARX_YOLLAR), (_yoq, len(NARX_YOLLAR)))
check("K4 har yo'l yozuvi o'qiladi", all(y and all(RX._yol_qismlari(y)) for ys in NARX_YOLLAR.values() for y in ys))
_mw = [m.cls.__name__ for m in main.app.user_middleware]
_msrc = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
check("K5 himoya qatlami ulangan va `narx_yoq` da `narx_tozala` qo'llanadi; auth `narx_yoq` ni belgilaydi",
      "_TannarxHimoyasi" in _mw and "_rx118t.narx_tozala(_ob, _marshrut)" in _msrc
      and 'request.state.narx_yoq = not _rx.narx_koradi(user)' in open(os.path.join(ROOT, "auth.py"), encoding="utf-8").read(), _mw)
_sk = RX.SAHIFA_KERAK.get("material_narx")
check("K6 rollar sahifasi ogohlantirishi (SAHIFA_KERAK) — Omborxona / Kirim / Buyurtmalar / Tayyor mahsulotlar",
      _sk and ("material", "korish") in _sk[0] and ("tayyor", "korish") in _sk[0], _sk)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Fikstura (korxona 1): xomashyo A / B (kirim API orqali — o'ziga xos narxlar), penoplast, loy retsepti; foydalanuvchilar.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="MN B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "mn_admin", "Parol123!", UserRole.ADMIN, "MN Admin", company_id=1)
    for _u in ("mn_hammasi", "mn_tannarxsiz", "mn_narxsiz", "mn_faqat_tannarx", "mn_ombor_narxsiz", "mn_tannarx_korish"):
        auth.create_user(s, _u, "Parol123!", UserRole.MANAGER, _u, company_id=1)
    auth.create_user(s, "mn_menejer", "Parol123!", UserRole.MANAGER, "MN Menejer", company_id=1)
    auth.create_user(s, "mn_omborchi", "Parol123!", UserRole.WAREHOUSE, "MN Omborchi", company_id=1)
HAMMASI = {bb: list(v["amallar"]) for bb, v in RX.BANDLAR.items()}
ROLLAR = {
    "mn_hammasi": HAMMASI,
    "mn_tannarxsiz": {bb: v for bb, v in HAMMASI.items() if bb != "tannarx"},
    "mn_narxsiz": {bb: v for bb, v in HAMMASI.items() if bb not in ("tannarx", "material_narx")},
    "mn_faqat_tannarx": {bb: v for bb, v in HAMMASI.items() if bb != "material_narx"},
    "mn_ombor_narxsiz": {"material": ["korish", "yaratish", "tahrirlash", "ochirish"], "qoldiq": ["tahrirlash"],
                         "kirim": ["korish"], "buyurtma": ["korish"], "tayyor": ["korish"], "sotuv": ["korish"],
                         "loyiha": ["korish"]},
    # «Tannarx va foyda» + Omborxona faqat ko'rish (bandsiz, «Materiallar: Tahrirlash» siz) — narx va «Ombor qiymati» ko'rinadi,
    # «Narxni tuzatish» — yo'q (ikki shart alohida)
    "mn_tannarx_korish": {"tannarx": ["korish"], "material": ["korish"], "kirim": ["korish"]},
}
for _u, _rx in ROLLAR.items():
    _r = Rol(company_id=1, nom=f"MN {_u}", kod=None, ruxsatlar=json.dumps(_rx), tavsif="")
    s.add(_r)
    s.flush()
    s.query(User).filter(User.username == _u).first().rol_id = _r.id
PENO = Inventory(company_id=1, item_name="MN Penoplast 14P", unit="dona", stock_quantity=5, price_per_unit=735197,
                 min_stock=0, category="Penoplast", is_penoplast=True, volume_per_unit=1.4)
A = Inventory(company_id=1, item_name="MN Kley", unit="kg", stock_quantity=0, price_per_unit=None, min_stock=0,
              category="Kimyoviy qo'shimchalar")
B = Inventory(company_id=1, item_name="MN Qum", unit="kg", stock_quantity=0, price_per_unit=None, min_stock=0,
              category="Qattiq qotishmalar")
s.add_all([PENO, A, B])
s.commit()
IDS = {"peno": PENO.id, "a": A.id, "b": B.id}
s.close()


def mijoz(u):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": u, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


C = {}
_kirish = {}
for _u in ("mn_admin", "mn_hammasi", "mn_tannarxsiz", "mn_narxsiz", "mn_faqat_tannarx", "mn_ombor_narxsiz", "mn_menejer",
           "mn_omborchi", "mn_tannarx_korish"):
    C[_u], _kirish[_u] = mijoz(_u)
if set(_kirish.values()) != {302}:
    print("LOGIN BO'LMADI", _kirish)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)
CA = C["mn_admin"]
_p1 = CA.post(f"/api/inventory/{IDS['a']}/purchase", json={"quantity": 100, "price_per_unit": 13579})
_p2 = CA.post(f"/api/inventory/{IDS['b']}/purchase", json={"quantity": 40, "price_per_unit": 24680})
_rec = js(CA.post("/api/recipes", json={"name": "MN Retsept", "batch_size_kg": 100,
                                        "ingredients": [{"inventory_id": IDS["a"], "quantity_kg": 30},
                                                        {"inventory_id": IDS["b"], "quantity_kg": 70}]})) or {}
REC_ID = _rec.get("id")
check("F0 fikstura: 2 kirim (13 579 va 24 680 so'm/kg), loy retsepti, penoplast — yaratildi",
      _p1.status_code == 200 and _p2.status_code == 200 and REC_ID,
      (_p1.status_code, _p1.text[:200], _p2.status_code, _p2.text[:200], _rec))


def sirlar():
    """Bazadan «sir» sonlar (≥ 100): xomashyo narxi, xarid narxi / summasi, ombor qiymati, material bo'yicha oy jami."""
    from sqlalchemy import text
    ss = SessionLocal()
    try:
        out = {}
        for (v,) in ss.execute(text("select price_per_unit from inventory where company_id = 1 and price_per_unit is not null")):
            out.setdefault(round(float(v), 2), "inventory.price_per_unit")
        for p, t in ss.execute(text("select p.price_per_unit, p.total_amount from inventory_purchases p "
                                    "join inventory i on i.id = p.inventory_id where i.company_id = 1")):
            out.setdefault(round(float(p), 2), "purchase.price_per_unit")
            out.setdefault(round(float(t), 2), "purchase.total_amount")
        q = ss.execute(text("select sum(coalesce(stock_quantity,0) * coalesce(price_per_unit,0)) from inventory "
                            "where company_id = 1 and coalesce(is_deleted, false) = false")).scalar()
        out.setdefault(round(float(q or 0), 2), "ombor_qiymati")
        pj = ss.execute(text("select sum(p.total_amount) from inventory_purchases p join inventory i on i.id = p.inventory_id "
                             "where i.company_id = 1")).scalar()
        out.setdefault(round(float(pj or 0), 2), "xarid_jami")
        return {k: v for k, v in out.items() if abs(k) >= 100}
    finally:
        ss.close()


SIR = sirlar()
check("F1 sir sonlar to'plami: 13 579, 24 680, 777 777, 1 357 900, 987 200, ombor qiymati",
      {13579.0, 24680.0, 735197.0, 1357900.0, 987200.0} <= set(SIR) and len(SIR) >= 6, SIR)
ID = {"item_id": IDS["a"], "recipe_id": REC_ID, "receipt_id": 999999, "supplier_id": 999999, "order_id": 999999,
      "project_id": 999999, "fp_id": 999999, "po_id": 999999, "pt_id": 999999, "master_id": 999999,
      "employee_id": 999999, "emp_id": 999999, "delivery_id": 999999, "sale_id": 999999, "group_id": "yoq",
      "bom_id": 999999, "loss_id": 999999, "return_id": 999999, "payment_id": 999999, "taklif_id": 999999,
      "purchase_id": 999999, "murojaat_id": 999999}
TASHQARI = ("/cron", "/system", "/platform", "/hodim/", "telegram", "pdf", "/export", "backup")


def url_of(r):
    u = r.path
    for kk, vv in ID.items():
        u = u.replace("{" + kk + "}", str(vv))
    return None if "{" in u else u


GETLAR = [r for r in API if "GET" in r.methods and not any(x in r.path for x in TASHQARI) and url_of(r)]

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Har GET /api — «Tannarxsiz» (band bor) ↔ «Narxsiz»; «Hammasi» ↔ «Faqat tannarx»")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
JAV = {}
for r in GETLAR:
    u = url_of(r)
    out = {}
    for kk in ("mn_tannarxsiz", "mn_narxsiz", "mn_hammasi", "mn_faqat_tannarx"):
        x = C[kk].get(u)
        out[kk] = (x.status_code, js(x) if "json" in x.headers.get("content-type", "") else None)
    JAV[r.path] = out
check("A0 hamma GET /api so'raldi (≥ 90), hech biri 500 emas",
      len(JAV) >= 90 and not [p for p, v in JAV.items() if any(st >= 500 for st, _ in v.values())],
      (len(JAV), [(p, {k: v[0] for k, v in vv.items()}) for p, vv in JAV.items() if any(st >= 500 for st, _ in vv.values())][:8]))
_hf = [(p, v["mn_tannarxsiz"][0], v["mn_narxsiz"][0]) for p, v in JAV.items() if v["mn_tannarxsiz"][0] != v["mn_narxsiz"][0]]
check("A1 holat kodlari: «Narxsiz» = «Tannarxsiz» (band hech qaysi marshrutni yopmaydi)", not _hf, _hf[:10])
_farq = []
for p, v in JAV.items():
    (st_t, jt), (st_n, jn) = v["mn_tannarxsiz"], v["mn_narxsiz"]
    if st_t != 200 or st_n != 200 or jt is None or jn is None:
        continue
    kut = barglar(tozala(copy.deepcopy(jt), p))
    bn = barglar(jn)
    if bn != kut:
        _ff = sorted(kk for kk in set(bn) | set(kut) if bn.get(kk, "∅") != kut.get(kk, "∅"))[:6]
        _farq.append((p, [(kk, kut.get(kk, "∅"), bn.get(kk, "∅")) for kk in _ff]))
check("A2 «Narxsiz» javobi = «Tannarxsiz» javobi + `narx_tozala` (ortiqcha ham, kam ham yashirilmagan)", not _farq, _farq[:5])
_ft = [p for p, v in JAV.items() if v["mn_hammasi"] != v["mn_faqat_tannarx"]]
check("A3 «Faqat tannarx» (band yo'q, «Tannarx va foyda» bor) = «Hammasi» — narx ko'rinadi (tannarx shundan hisoblanadi)",
      not _ft, _ft[:8])
MAJBURIY = {
    "/api/inventory": ["[].price_per_unit"],
    "/api/inventory/kpi": ["total_value"],
    "/api/inventory/purchases": ["[].price_per_unit", "[].total_amount"],
    "/api/inventory/purchase-stats": ["total_amount", "by_material[].total", "by_material[].avg_price"],
    "/api/inventory/purchase-trend": ["months[].total"],
    "/api/penoplasts": ["items[].price_per_unit"],
    "/api/loy-cost": ["breakdown[].price"],
}
_mj = []
for p, yollar in MAJBURIY.items():
    v = JAV.get(p)
    if not v:
        _mj.append((p, "so'ralmadi"))
        continue
    bt, bn = barglar(v["mn_tannarxsiz"][1]), barglar(v["mn_narxsiz"][1])
    for y in yollar:
        tv = [x for kk, x in bt.items() if umumiy(kk) == y]
        nv = [x for kk, x in bn.items() if umumiy(kk) == y]
        if not tv or not any(isinstance(x, (int, float)) and not isinstance(x, bool) and x for x in tv) \
                or any(x is not None for x in nv):
            _mj.append((p, y, tv[:3], nv[:3]))
check("A4 majburiy yashirinlar (7 marshrut) — «Tannarxsiz» da son bor, «Narxsiz» da hammasi null", not _mj, _mj)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("V. QIYMAT bo'yicha qidiruv — Menejer va «Ombor narxsiz» javoblarida xomashyo narxi / ombor qiymati yo'q")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def qidir(o, yol="", top=None):
    top = top if top is not None else []
    if isinstance(o, dict):
        for kk, vv in o.items():
            qidir(vv, f"{yol}.{kk}", top)
    elif isinstance(o, list):
        for vv in o:
            qidir(vv, yol + "[]", top)
    elif isinstance(o, (int, float)) and not isinstance(o, bool) and round(float(o), 2) in SIR:
        top.append((yol, o, SIR[round(float(o), 2)]))
    return top


def skan(u_kim):
    topildi, ochiq = {}, 0
    for r in GETLAR:
        x = C[u_kim].get(url_of(r))
        if x.status_code != 200 or "json" not in x.headers.get("content-type", ""):
            continue
        ochiq += 1
        t = qidir(js(x))
        if t:
            topildi[r.path] = t[:4]
    return topildi, ochiq


for _kim, _nom in (("mn_menejer", "V1 tayyor Menejer"), ("mn_ombor_narxsiz", "V2 «Ombor narxsiz» (Omborxona to'liq, narxsiz)")):
    _t, _o = skan(_kim)
    check(f"{_nom}: {_o} ta ochiq GET javobida sir son YO'Q", _o >= 15 and not _t, (_o, _t))
_t, _o = skan("mn_omborchi")
check("V3 Omborchi (tayyor, band bor) — xomashyo narxi va ombor qiymati KO'RINADI",
      "/api/inventory" in _t and "/api/inventory/kpi" in _t, (_o, sorted(_t)))
_t, _o = skan("mn_admin")
check("V4 Admin — ko'rinadi (inventory, kpi, purchases, penoplasts, loy-cost)",
      {"/api/inventory", "/api/inventory/kpi", "/api/inventory/purchases", "/api/penoplasts", "/api/loy-cost"} <= set(_t),
      sorted(_t))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Sahifalar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def sahifa(kim, url):
    x = C[kim].get(url)
    return x.status_code, x.text


_sm, _tm = sahifa("mn_menejer", "/inventory")
check("H1 Omborxona (Menejer): sahifa 200; «Ombor qiymati», «1 birlik narxi», narx katagi, «13 579» — YO'Q",
      _sm == 200 and "Ombor qiymati" not in _tm and "<span>1 birlik narxi</span>" not in _tm and 'id="price-' not in _tm
      and "13 579" not in _tm and "13579" not in _tm, (_sm, [w for w in ("Ombor qiymati", "<span>1 birlik narxi</span>", 'id="price-',
                                                                         "13 579", "13579") if w in _tm]))
_so, _to = sahifa("mn_omborchi", "/inventory")
check("H2 Omborxona (Omborchi — band + «Materiallar: Tahrirlash»): «Ombor qiymati», narx «13 579», «Narxni tuzatish» — BOR",
      _so == 200 and "Ombor qiymati" in _to and "13 579" in _to and "Narxni tuzatish" in _to, _so)
_sn, _tn = sahifa("mn_ombor_narxsiz", "/inventory")
check("H3 Omborxona («Materiallar: Tahrirlash» bor, band yo'q): narx ham, «Narxni tuzatish» ham, «Ombor qiymati» ham — YO'Q",
      _sn == 200 and "Ombor qiymati" not in _tn and 'id="price-' not in _tn and "Narxni tuzatish" not in _tn, _sn)
_sf, _tf = sahifa("mn_faqat_tannarx", "/inventory")
check("H4 Omborxona («Faqat tannarx»): narx va «Ombor qiymati» — BOR", _sf == 200 and "Ombor qiymati" in _tf
      and "13 579" in _tf, _sf)
_sk, _tk = sahifa("mn_tannarx_korish", "/inventory")
check("H8 Omborxona («Tannarx va foyda» + «Materiallar: Ko'rish», tahrirsiz): «Ombor qiymati», narx «13 579» — BOR; «Narxni "
      "tuzatish» — YO'Q", _sk == 200 and "Ombor qiymati" in _tk and "13 579" in _tk and "Narxni tuzatish" not in _tk,
      (_sk, [w for w in ("Ombor qiymati", "13 579", "Narxni tuzatish") if w in _tk]))


def penos(txt, nom):
    m = re.search(r"const " + nom + r" = \[(.*?)\];", txt, re.S)
    return m.group(1) if m else ""


_smf, _tmf = sahifa("mn_menejer", "/finished")
_saf, _taf = sahifa("mn_admin", "/finished")
check("H5 Tayyor mahsulotlar `PENOS`: Menejer — penoplast narxi 0 (735197 yo'q), Admin — 735197",
      _smf == 200 and _saf == 200 and "price: 0" in penos(_tmf, "PENOS") and "735197" not in _tmf
      and "735197" in penos(_taf, "PENOS"), (penos(_tmf, "PENOS")[:200], penos(_taf, "PENOS")[:200]))
_smo, _tmo = sahifa("mn_menejer", "/orders")
_sao, _tao = sahifa("mn_admin", "/orders")
check("H6 Buyurtmalar `PENOPLASTS`: Menejer — pricePerUnit 0 (735197 yo'q), Admin — 735197",
      _smo == 200 and _sao == 200 and "pricePerUnit: 0" in penos(_tmo, "PENOPLASTS") and "735197" not in _tmo
      and "735197" in penos(_tao, "PENOPLASTS"), (penos(_tmo, "PENOPLASTS")[:200], penos(_tao, "PENOPLASTS")[:200]))
_sof, _tof = sahifa("mn_omborchi", "/finished")
check("H7 Tayyor mahsulotlar (Omborchi — band bor): `PENOS` da 735197", _sof == 200 and "735197" in penos(_tof, "PENOS"),
      penos(_tof, "PENOS")[:200])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. Omborxona xarid tarixi — null narx / summa")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
INV = open(os.path.join(ROOT, "templates", "inventory.html"), encoding="utf-8").read()
_eski = [w for w in ("fmt(p.total_amount)", "fmt(stats.total_amount)", "fmt(m.total)", "${fmt(total)} so'm") if w in INV]
if INV.count("fmt(p.price_per_unit)") != 1:          # faqat `phNarxQismi` ichida
    _eski.append(f"fmt(p.price_per_unit) × {INV.count('fmt(p.price_per_unit)')}")
check("J1 xarid tarixida eski `fmt(narx / summa)` yo'q — hammasi `phSom` / `phNarxQismi` / `phSummaJami` orqali",
      # phNarxQismi(p): ta'rif + 2 chaqiruv; phSummaJami(: ta'rif + 2 chaqiruv
      not _eski and INV.count("phSom(") >= 6 and INV.count("phNarxQismi(p)") == 3 and INV.count("phSummaJami(") >= 3,
      (_eski, INV.count("phSom("), INV.count("phNarxQismi(p)"), INV.count("phSummaJami(")))


def js_funksiya(src, nom):
    m = re.search(r"function " + nom + r"\b.*?\n}", src, re.S) or re.search(r"function " + nom + r"\b[^\n]*\n", src)
    return m.group(0) if m else ""


_node = shutil.which("node")
_kod = "\n".join(js_funksiya(INV, n) for n in ("fmt", "phNarxQismi", "phSom", "phSummaJami"))
_jsn = """
const r = {
  a: phSom(null), b: phSom(undefined), c: phSom(1357900), d: phNarxQismi({price_per_unit: null}),
  e: phNarxQismi({price_per_unit: 13579}), f: phSummaJami([{total_amount: null}, {total_amount: 5}]),
  g: phSummaJami([{total_amount: 2}, {total_amount: 5}]), h: phSom(phSummaJami([{total_amount: null}]))
};
console.log(JSON.stringify(r));
"""
_nat = None
if _node and "function phSom" in _kod:
    _p = subprocess.run([_node, "-e", _kod + _jsn], capture_output=True, text=True, timeout=60)
    # `toLocaleString('ru-RU')` — ming ajratgich U+00A0 (brauzerda ham shunday) — taqqoslashda oddiy bo'shliq
    _nat = (js(type("R", (), {"json": lambda self: json.loads((_p.stdout.strip() or "null").replace("\\u00a0", " ")
                                                              .replace("\u00a0", " "))})())
            if _p.returncode == 0 else _p.stderr[:300])
check("J2 node: null → «—», «× narx» yozilmaydi; son → «1 357 900 so'm», « × 13 579»; null qatorli jami → null → «—»",
      isinstance(_nat, dict) and _nat == {"a": "—", "b": "—", "c": "1 357 900 so'm", "d": "", "e": " × 13 579", "f": None,
                                          "g": 7, "h": "—"}, _nat)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Migratsiya — mavjud rollar (yangi band qo'shilganda bir marta)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def eski_json(kod):
    """Tayyor rolning ESKI (band qo'shilishidan oldingi) ruxsatlari."""
    return json.dumps({bb: v for bb, v in RX.TAYYOR_ROLLAR[kod]["ruxsatlar"].items() if bb != "material_narx"})


s = SessionLocal()
for _cid, _nom in ((3, "MN eski korxona"), (4, "MN yangi korxona"), (5, "MN aralash korxona")):
    if not s.get(Company, _cid):
        s.add(Company(id=_cid, name=_nom))
s.commit()
ESKI = {"admin": eski_json("admin"), "menejer": eski_json("menejer"), "omborchi": eski_json("omborchi"),
        "moliyachi": eski_json("moliyachi")}
for _kod, _rx in ESKI.items():
    s.add(Rol(company_id=3, nom=RX.TAYYOR_ROLLAR[_kod]["nom"], kod=_kod, ruxsatlar=_rx, tavsif=""))
OZI = {"Kirimchi": {"kirim": ["korish", "yaratish"], "material": ["korish"]},
       "Ko'ruvchi": {"material": ["korish"], "kirim": ["korish"], "buyurtma": ["korish"]},
       "Moliya ko'ruvchi": {"moliya": ["korish"]},
       "Ta'minot": {"taminotchi": ["korish"]},
       "Tannarxchi": {"tannarx": ["korish"]},
       "Material tahrir": {"material": ["korish", "tahrirlash"]}}
for _nom, _rx in OZI.items():
    s.add(Rol(company_id=3, nom=_nom, kod=None, ruxsatlar=json.dumps(_rx), tavsif=""))
s.commit()
s.close()


def rollar_holati(cid):
    ss = SessionLocal()
    try:
        return {(r.kod or r.nom): ("material_narx" in RX.ruxsatlar_oqi(r.ruxsatlar))
                for r in ss.query(Rol).filter(Rol.company_id == cid).all()}, \
            [r.ruxsatlar for r in ss.query(Rol).filter(Rol.company_id == cid).order_by(Rol.id).all()], \
            bool(ss.query(CompanySetting).filter(CompanySetting.company_id == cid, CompanySetting.key == KALIT).first())
    finally:
        ss.close()


def mig():
    if MIG is None:
        return None
    with contextlib.redirect_stdout(io.StringIO()):
        return xavfsiz(MIG)


_h0, _, _b0 = rollar_holati(3)
_n1 = mig()
_h1, _j1, _b1 = rollar_holati(3)
_kut = {"admin": False, "menejer": False, "omborchi": True, "moliyachi": True, "Kirimchi": True, "Ko'ruvchi": False,
        "Moliya ko'ruvchi": True, "Ta'minot": True, "Tannarxchi": False, "Material tahrir": True}
check("M1 eski korxona (belgisiz): qoidaga ko'ra — Omborchi, Moliyachi, Kirimchi, Moliya ko'ruvchi, Ta'minot, Material tahrir "
      "— band qo'shildi; Admin, Menejer, Ko'ruvchi, Tannarxchi — yo'q", not _b0 and _h1 == _kut, (_b0, _h1))
check("M2 korxona belgisi `rx_material_narx` qo'yildi; boshqa ruxsatlar o'zgarmadi (faqat band qo'shildi)",
      _b1 and all({kk: vv for kk, vv in json.loads(j).items() if kk != "material_narx"} ==
                  {kk: vv for kk, vv in (json.loads(ESKI[kod]) if kod in ESKI else OZI[kod]).items()}
                  for kod, j in zip([*ESKI, *OZI], _j1)), _j1[:3])
_n2 = mig()
_h2, _j2, _ = rollar_holati(3)
check("M3 ikkinchi ishga tushish — hech narsa o'zgarmaydi", _j2 == _j1 and _n2 == 0, _n2)
s = SessionLocal()
_kr = s.query(Rol).filter(Rol.company_id == 3, Rol.nom == "Kirimchi").first()
_kr.ruxsatlar = json.dumps({"kirim": ["korish", "yaratish"], "material": ["korish"]})
s.commit()
s.close()
mig()
_h3, _, _ = rollar_holati(3)
check("M4 admin o'chirgan band (Kirimchi) qayta qo'shilmaydi", _h3.get("Kirimchi") is False, _h3)
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    _t4 = auth.tayyor_rollar(s, 4)
s.add(Rol(company_id=4, nom="Yangi kirimchi", kod=None, ruxsatlar=json.dumps({"kirim": ["yaratish"]}), tavsif=""))
s.commit()
s.close()
_h4a, _, _b4 = rollar_holati(4)
mig()
_h4, _, _ = rollar_holati(4)
check("M5 yangi korxona (`auth.tayyor_rollar` — rollar hozirgi andozadan): belgi darhol; Omborchi / Moliyachi — bor, Menejer — "
      "yo'q; admin o'zi yaratgan rol (bandsiz) migratsiyadan keyin ham bandsiz",
      _b4 and _h4.get("omborchi") and _h4.get("moliyachi") and _h4.get("menejer") is False
      and _h4.get("Yangi kirimchi") is False, (_b4, _h4))
s = SessionLocal()
s.add(Rol(company_id=5, nom="Oldin bor rol", kod=None, ruxsatlar=json.dumps({"kirim": ["yaratish"]}), tavsif=""))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.tayyor_rollar(s, 5)
s.close()
_, _, _b5 = rollar_holati(5)
mig()
_h5, _, _b5b = rollar_holati(5)
check("M6 roli bor korxonada `tayyor_rollar` belgi QO'YMAYDI; migratsiya qoidaga ko'ra ko'rib chiqadi va belgilaydi",
      _b5 is False and _b5b and _h5.get("Oldin bor rol") is True, (_b5, _b5b, _h5))
_h1c, _, _b1c = rollar_holati(1)
check("M7 korxona 1 (bo'sh bazada ishga tushish — rollar andozadan): belgi bor, test rollari (o'zi yaratilgan) tegilmagan",
      _b1c and _h1c.get("MN mn_narxsiz") is False and _h1c.get("MN mn_ombor_narxsiz") is False, (_b1c, _h1c))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  - " + f)
sys.exit(1 if FAIL else 0)
