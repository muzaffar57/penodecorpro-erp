#!/usr/bin/env python3
"""
test_nan216.py — kech157 (zip 216 «NaN / cheksiz son — butun dastur bo'ylab»; zip 215b dagi buyurtma o'lchami sinfi).

NIMA UCHUN KERAK
  O'LCHANGAN (HAQIQIY PG 16, `work/k216/NAN_OLCHOV.md`): (1) kassa yozuvi «nan» — 500, lekin `cash_transactions.amount = NaN` yozilardi
  (keyin kassa qoldig'i / pul oqimi — 500), «inf» / «-inf» — 500; (2) ehson foizi «nan» — `'nan'` saqlanardi (keyin ehson foizi, Moliya
  tarixi — 500); (3) buyurtma / taklif `base_price`, `price_per_m3`, `unit_price_for_volume` «-Infinity» — buyurtmada 500, taklifda tanaga
  yozilib taklifni ochish 500, manfiy son qabul qilinardi; (4) `planned_gips_kg` NaN / ∞, `gips_additives[].planned_qty` ∞ — qabul qilinardi.
BO'LIMLAR
  S — manba (isfinite tekshiruvi, sxema chegaralari).
  K — kassa: «nan», «inf», «-inf» (boshlang'ich, usta KPI, ehson) — 400, yozuv yo'q, kassa qoldig'i / pul oqimi ishlaydi; oddiy summa — 200.
  E — ehson foizi: «nan», «inf» — 400, sozlama o'zgarmaydi, o'qish ishlaydi; 5 — 200.
  B — buyurtma (yaratish, tahrir) va taklif (yaratish, tahrir, rasmiylashtirish): narxlar −∞ / NaN / manfiy, gips kg NaN / ∞ / manfiy,
      gips qo'shimchasi ∞ — 422, hech narsa yozilmaydi, taklif ochiladi; oddiy qiymatlar — 200.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (asosiy — NaN faqat PG da saqlanadi).
Asl kodga (zip 215c) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_nan216.py
"""
import os
import io
import sys
import json
import tempfile
import datetime
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "nan216_test"
_T = tempfile.mkdtemp(prefix="k216_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k216.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


section("S — manba")
MAIN_SRC = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
SCH = open(os.path.join(ROOT, "schemas.py"), encoding="utf-8").read()
_k = MAIN_SRC[MAIN_SRC.find("def api_record_cash_transaction("):][:2500]
_e = MAIN_SRC[MAIN_SRC.find("def api_set_ehson_percent("):][:1200]
check("S1 kassa yozuvi va ehson foizi — `isfinite` tekshiruvi yozishdan OLDIN",
      ".isfinite(amount)" in _k and _k.find(".isfinite(amount)") < _k.find("crud.record_cash_transaction")
      and ".isfinite(percent)" in _e and _e.find(".isfinite(percent)") < _e.find("crud.set_setting"), (len(_k), len(_e)))
check("S2 sxema: price_per_m3, unit_price_for_volume, base_price, planned_gips_kg — ge=0 va allow_inf_nan=False; gips qo'shimchasi — "
      "allow_inf_nan=False",
      "price_per_m3: Optional[float] = Field(default=None, ge=0, le=9_999_999_999.99, allow_inf_nan=False)" in SCH
      and "unit_price_for_volume: Optional[float] = Field(default=None, ge=0, le=9_999_999_999.99, allow_inf_nan=False)" in SCH
      and "base_price: Optional[float] = Field(default=None, ge=0, le=9_999_999_999.99, allow_inf_nan=False)" in SCH
      and "planned_gips_kg: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)" in SCH
      and "planned_qty: float = Field(..., gt=0, allow_inf_nan=False)" in SCH)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from sqlalchemy import text as _sql                # noqa: E402
from models import UserRole, Inventory, Project, Order, CashTransaction   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k216_a", PAROL, UserRole.ADMIN, "K216 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K216 Penoplast", unit="blok", stock_quantity=1000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="K216 Kley", unit="kg", stock_quantity=1000, price_per_unit=1000, category="Kimyo")
P1 = Project(company_id=1, client_name="K216 mijoz", project_name="K216 loyiha", client_phone="+998901112216", total_budget=0, total_paid=0)
s.add_all([PENO, KLEY, P1])
s.commit()
ID = {"PENO": PENO.id, "KLEY": KLEY.id, "P1": P1.id}
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "k216_a", "password": PAROL}, follow_redirects=False)
_N = [0]


def nanlar():
    """bazadagi HAMMA sonli ustunlarda NaN / ±∞ soni (PG); SQLite — NaN saqlanmaydi (NULL), ∞ — tekshiriladi."""
    s2 = SessionLocal()
    try:
        if PG_URL:
            ust = s2.execute(_sql("""SELECT table_name, column_name, data_type FROM information_schema.columns
                                     WHERE table_schema = 'public' AND data_type IN ('double precision', 'real', 'numeric')""")).fetchall()
            jami = 0
            for t, c, d in ust:
                if d == "numeric":
                    q = f"SELECT count(*) FROM \"{t}\" WHERE \"{c}\" = 'NaN'::numeric"
                else:
                    q = f"SELECT count(*) FROM \"{t}\" WHERE \"{c}\" IN ('NaN'::float8, 'Infinity'::float8, '-Infinity'::float8)"
                jami += int(s2.execute(_sql(q)).scalar() or 0)
            jami += int(s2.execute(_sql("SELECT count(*) FROM company_settings WHERE lower(value) IN ('nan', 'inf', '-inf', 'infinity', "
                                        "'-infinity')")).scalar() or 0)
            jami += int(s2.execute(_sql("SELECT count(*) FROM takliflar WHERE tana LIKE '%NaN%' OR tana LIKE '%Infinity%'")).scalar() or 0)
            return jami
        return int(s2.execute(_sql("SELECT count(*) FROM takliflar WHERE tana LIKE '%NaN%' OR tana LIKE '%Infinity%'")).scalar() or 0)
    finally:
        s2.close()


def kassa_soni():
    s2 = SessionLocal()
    try:
        return s2.query(CashTransaction).count()
    finally:
        s2.close()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K — kassa yozuvi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
n0, k0 = nanlar(), kassa_soni()
_r = []
for kat, vals in (("boshlangich", ("nan", "NaN", "inf", "-inf", "Infinity")), ("usta_kpi", ("-inf", "-Infinity", "nan")),
                  ("ehson", ("-inf", "nan"))):
    for v in vals:
        _N[0] += 1
        r = A.post("/api/finance/cash-transaction", data={"category": kat, "amount": v, "notes": f"K216 {_N[0]}"})
        _r.append((kat, v, r.status_code))
check("K1 «nan» / «inf» / «-inf» summa (boshlang'ich, usta KPI, ehson) — hammasi 400 (500 emas)", all(x[2] == 400 for x in _r), _r)
check("K2 kassaga yozuv YO'Q, bazada NaN / ∞ yo'q", kassa_soni() == k0 and nanlar() == n0, (kassa_soni() - k0, nanlar() - n0))
_b = [A.get(u).status_code for u in ("/api/finance/cash-balance", "/api/finance/cash-transactions")]
check("K3 kassa qoldig'i va kassa ro'yxati — 200 (ilgari «nan» dan keyin 500)", _b == [200, 200], _b)
r = A.post("/api/finance/cash-transaction", data={"category": "boshlangich", "amount": "1000", "notes": "K216 oddiy"})
r2 = A.post("/api/finance/cash-transaction", data={"category": "usta_kpi", "amount": "-500", "notes": "K216 oddiy kpi"})
check("K4 oddiy summa — avvalgidek 200 (boshlang'ich 1000, usta KPI −500), 2 yozuv", r.status_code == 200 and r2.status_code == 200
      and kassa_soni() == k0 + 2, (r.status_code, r.text[:200], r2.status_code, r2.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E — ehson foizi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
A.put("/api/settings/ehson-percent", data={"percent": "7"})
_r = [(v, A.put("/api/settings/ehson-percent", data={"percent": v}).status_code) for v in ("nan", "NaN", "inf", "-inf", "Infinity")]
_g = A.get("/api/settings/ehson-percent")
check("E1 «nan» / «inf» — 400; sozlama o'zgarmadi (7), o'qish 200", all(x[1] == 400 for x in _r) and _g.status_code == 200
      and _g.json().get("ehson_percent") == 7, (_r, _g.status_code, _g.text[:200]))
check("E2 Moliya tarixi — 200 (ilgari «nan» dan keyin 500)", A.get("/api/finance/history").status_code == 200)
check("E3 oddiy foiz 5 — 200; 101 — 400 (avvalgidek)", A.put("/api/settings/ehson-percent", data={"percent": "5"}).status_code == 200
      and A.put("/api/settings/ehson-percent", data={"percent": "101"}).status_code == 400)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B — buyurtma va taklif")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
BUGUN = datetime.date.today()


def buyurtma_tana(pid=None, **ust):
    _N[0] += 1
    it = {"name": f"K216 Panel {_N[0]}", "category": "panel", "width": 100, "thickness": 5, "length": 2, "quantity": 1, "unit_price": 10000,
          "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": 500000, "unit_price_for_volume": None, "finished_product_id": None}
    for k in ("price_per_m3", "unit_price_for_volume"):
        if k in ust:
            it[k] = ust.pop(k)
    b = {"project_id": pid or ID["P1"], "order_type": "product", "recipe_id": None, "master_id": None,
         "deadline": (BUGUN + datetime.timedelta(days=3)).isoformat(), "is_draft": False, "base_price": 600000, "loy_kg": None, "items": [it]}
    b.update(ust)
    return b


def yubor(m, u, b):
    return getattr(A, m)(u, content=json.dumps(b, allow_nan=True), headers={"Content-Type": "application/json"})


def buyurtmalar_soni():
    s2 = SessionLocal()
    try:
        return s2.query(Order).count()
    finally:
        s2.close()


YOMON = [("base_price", float("-inf")), ("base_price", float("nan")), ("base_price", -5), ("price_per_m3", float("-inf")),
         ("price_per_m3", -1), ("unit_price_for_volume", float("-inf")), ("unit_price_for_volume", float("nan")),
         ("planned_gips_kg", float("nan")), ("planned_gips_kg", float("inf")), ("planned_gips_kg", -2)]
o0, n0 = buyurtmalar_soni(), nanlar()
_r = [(f, v, yubor("post", "/api/orders?confirm_shortage=true", buyurtma_tana(**{f: v})).status_code) for f, v in YOMON]
_gb = buyurtma_tana()
_gb["gips_additives"] = [{"inventory_id": ID["KLEY"], "planned_qty": float("inf")}]
_r.append(("gips_additives.planned_qty", "inf", yubor("post", "/api/orders?confirm_shortage=true", _gb).status_code))
check("B1 buyurtma yaratish: narxlar −∞ / NaN / manfiy, gips kg NaN / ∞ / manfiy, gips qo'shimchasi ∞ — hammasi 422 (500 / 200 emas)",
      all(x[2] == 422 for x in _r), _r)
check("B2 buyurtma yozilmadi, bazada NaN / ∞ yo'q", buyurtmalar_soni() == o0 and nanlar() == n0, (buyurtmalar_soni() - o0, nanlar() - n0))
_ok = yubor("post", "/api/orders?confirm_shortage=true", buyurtma_tana(planned_gips_kg=5, unit_price_for_volume=4000))
_oid = _ok.json().get("id") if _ok.status_code == 200 else None
check("B3 oddiy qiymatlar (gips 5 kg, hajm narxi 4000, 1 m³ 500 000, asosiy narx 600 000) — 200", _oid, (_ok.status_code, _ok.text[:300]))
_rp = [(f, v, yubor("put", f"/api/orders/{_oid}", buyurtma_tana(**{f: v})).status_code) for f, v in YOMON] if _oid else []
check("B4 buyurtma tahriri (PUT) — o'sha qiymatlar 422", _rp and all(x[2] == 422 for x in _rp) and nanlar() == n0, _rp)


def taklif_tana(**ust):
    b = buyurtma_tana(**ust)
    b.pop("project_id")
    _N[0] += 1
    return {"mijoz": f"K216 taklif mijoz {_N[0]}", "buyurtma": b}


_rt = [(f, v, yubor("post", "/api/takliflar", taklif_tana(**{f: v})).status_code) for f, v in YOMON]
check("B5 taklif yaratish — o'sha qiymatlar 422 (ilgari −∞ / NaN 200 bo'lib tanaga yozilardi, keyin taklif ochilmasdi)",
      all(x[2] == 422 for x in _rt) and nanlar() == n0, (_rt, nanlar() - n0))
_tk = yubor("post", "/api/takliflar", taklif_tana())
_tid = (_tk.json().get("taklif") or {}).get("id") if _tk.status_code == 200 else None
_ru = [(f, v, yubor("put", f"/api/takliflar/{_tid}", taklif_tana(**{f: v})).status_code) for f, v in YOMON] if _tid else []
_ochil = A.get(f"/api/takliflar/{_tid}").status_code if _tid else None
check("B6 taklif tahriri — 422; taklif ochiladi (200)", _tid and _ru and all(x[2] == 422 for x in _ru) and _ochil == 200 and nanlar() == n0,
      (_tk.status_code, _ru, _ochil))
_rr = [(f, v, yubor("post", f"/api/takliflar/{_tid}/rasmiylashtir?confirm_shortage=true",
                    {"loyiha_id": ID["P1"], "buyurtma": taklif_tana(**{f: v})["buyurtma"]}).status_code) for f, v in YOMON[:4]] if _tid else []
check("B7 taklifni rasmiylashtirish — o'sha qiymatlar 422 (500 emas), buyurtma yaratilmaydi",
      _rr and all(x[2] == 422 for x in _rr) and buyurtmalar_soni() == o0 + 1, (_rr, buyurtmalar_soni() - o0))

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
