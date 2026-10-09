#!/usr/bin/env python3
"""
test_material_royxat.py — kech135 (zip 161): «Materiallar ro'yxati (retsept va tarkib uchun)» ruxsati — SERVER va SHABLONLAR (statik).

NIMA UCHUN KERAK (egasi 09.10 22:0x, tugmali: «retsept ruxsati + rollarda belgi — admin xohlasa ochadi, xohlasa yopadi»;
ro'yxatda — «Nomi va birligi»)
-------------------------------------------------------------------------------------------------------------------
  O'LCHANGAN (zip 160 kodi, `work/k161/olchov161.py`, SQLite va PG): faqat «Loy retseptlari» / «Mahsulot turlari va tarkibi» ruxsati
  bor (Omborxona → Materiallar: Ko'rish YO'Q) rol — retsept oynasida material tanlab bo'lmaydi (`/api/inventory` 403), tarkib
  oynasida ro'yxat XABARSIZ bo'sh, mavjud tarkib qatorlarida noto'g'ri «(yashirilgan)»; «Ishlab chiqarish buyurtmalari» ruxsati yo'q
  rolga «Ishlab chiqarish» yorlig'i ko'rinib, 403 bilan «Hali ishlab chiqarish yo'q» deb yozardi.
  YECHIM: band `material_royxat` (faqat Ko'rish, «Retsept va ishlab chiqarish» bo'limida; mavjud rollarda O'CHIQ), `GET
  /api/material-royxati` (shu band YOKI «Materiallar: Ko'rish»; nomi, birligi, turkumi; qoldiq — faqat «Materiallar: Ko'rish»
  bor rolga; narx — hech kimga), Rollar sahifasida «retsept yoziladi, lekin ro'yxat yo'q» ogohlantirishi (`AMAL_KERAK`).

BO'LIMLAR
  K — katalog: band, amali, joyi, sahifa bog'liqligi, AMAL_KERAK, tayyor rollar andozasi o'zgarmagan, `/api/rollar` katalogi;
  A — `GET /api/material-royxati`: ruxsatlar (retsept / tarkib / ikkalasi / band yolg'iz / Menejer / Omborchi / Moliyachi / Admin /
      sessiyasiz), maydonlar (AYNAN), qoldiq va narx QIYMAT bo'yicha javobda yo'q, ro'yxat `/api/inventory` bilan AYNAN (tartib,
      o'chirilgan material yo'q), boshqa korxona materiali yo'q;
  R — shu ruxsat bilan ish: retsept yaratish / tahrirlash, tarkib yaratish (material — ro'yxatdan);
  M — rollar API: band bilan rol saqlash, noto'g'ri amal 400, mavjud (bandsiz) rol — ruxsat yo'q (migratsiya yo'q);
  S — shablonlar: retsept / tarkib oynalari yangi ro'yxatni o'qiydi, «(yashirilgan)» yo'q, «Ishlab chiqarish» yorlig'i ruxsatga
      qarab (server chizadi), Rollar sahifasi ogohlantirishi.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 160) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_material_royxat.py
"""
import os
import sys
import json
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "material_royxat161_test"
_DB = os.path.join(tempfile.gettempdir(), "material_royxat161_test.db")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import ruxsatlar as RX                             # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol, Inventory, Recipe, RecipeIngredient, Yonalish   # noqa: E402
from production_models import Company, ProductType, BOM, BOMItem   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
HAMMA = ["korish", "yaratish", "tahrirlash", "ochirish"]
BAND = "material_royxat"
YOL = "/api/material-royxati"
BAND_NOMI = "Materiallar ro'yxati (retsept va tarkib uchun)"


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


def royxat(r):
    """Javob ro'yxat bo'lsa — o'zi, aks holda (asl kodda 404 `{"detail": …}`) — bo'sh ro'yxat (sinov QULAMASIN)."""
    d = js(r)
    return d if isinstance(d, list) else []


def detail(r):
    d = js(r)
    return d.get("detail") if isinstance(d, dict) else None


def oqi(f):
    try:
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


_IP = {"n": 60}


def mijoz():
    _IP["n"] += 1
    try:
        return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False,
                          client=(f"203.0.113.{_IP['n']}", 50000))
    except TypeError:
        return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)


def kirish(login):
    c = mijoz()
    c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def rol_qoy(login, ruxsat):
    """Foydalanuvchiga YANGI maxsus rol (bazaga to'g'ridan — ruxsatlar JSON i qanday yozilgan bo'lsa shunday)."""
    def f(s):
        r = Rol(company_id=s.query(User).filter(User.username == login).first().company_id, nom="MR161 " + login,
                kod=None, ruxsatlar=json.dumps(ruxsat), tavsif="")
        s.add(r)
        s.flush()
        s.query(User).filter(User.username == login).first().rol_id = r.id
        return r.id
    return db_ishi(f)


# ══════════════════════════════════════════════════════════════
# Fikstura: 1-korxona — Admin (A), retsept (R), retsept + band (RB), tarkib (M), tarkib + band (MB), band yolg'iz (B), Menejer (MN),
# Omborchi (W), Moliyachi (F); 2-korxona — retsept + band (X). Materiallar: narx / qoldiq — QIDIRUV uchun noyob sonlar.
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ikkinchi Korxona", code="IKKINCHI-161"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "mr_admin", "Parol123!", UserRole.ADMIN, "MR admin", company_id=1)
    for _u, _t in (("mr_r", UserRole.MANAGER), ("mr_rb", UserRole.MANAGER), ("mr_m", UserRole.MANAGER),
                   ("mr_mb", UserRole.MANAGER), ("mr_b", UserRole.MANAGER), ("mr_mn", UserRole.MANAGER),
                   ("mr_w", UserRole.WAREHOUSE), ("mr_f", UserRole.ACCOUNTANT)):
        auth.create_user(s, _u, "Parol123!", _t, _u.upper(), company_id=1)
    auth.create_user(s, "mr_x", "Parol123!", UserRole.MANAGER, "MR X", company_id=2)
s.commit()
s.close()
for _u, _rx in (("mr_r", {"retsept": HAMMA}), ("mr_rb", {"retsept": HAMMA, BAND: ["korish"]}),
                ("mr_m", {"mahsulot_turi": HAMMA}), ("mr_mb", {"mahsulot_turi": HAMMA, BAND: ["korish"]}),
                ("mr_b", {BAND: ["korish"]}), ("mr_x", {"retsept": HAMMA, BAND: ["korish"]})):
    rol_qoy(_u, _rx)


def _fikstura(s):
    ids = {}
    A = Inventory(company_id=1, item_name="MR161 Kley «A»", unit="kg", stock_quantity=12.37, price_per_unit=7319.0, min_stock=3.91,
                  category="Kimyoviy qo'shimchalar", notes="MR161 izoh sir")
    B = Inventory(company_id=1, item_name="MR161 Qum", unit="qop", base_unit="kg", conversion_factor=50, stock_quantity=41.73,
                  price_per_unit=25017.0, min_stock=0, category="Qattiq qotishmalar")
    C = Inventory(company_id=1, item_name="MR161 Bo'yoq", unit="l", stock_quantity=9.61, price_per_unit=41023.0, min_stock=0,
                  category=None)
    D = Inventory(company_id=1, item_name="MR161 O'chirilgan", unit="kg", stock_quantity=5, price_per_unit=100, min_stock=0,
                  category="Gips", is_deleted=True)
    X = Inventory(company_id=2, item_name="MR161 Begona", unit="kg", stock_quantity=77, price_per_unit=999, min_stock=0,
                  category="Gips")
    s.add_all([A, B, C, D, X])
    s.flush()
    ids.update(A=A.id, B=B.id, C=C.id, D=D.id, X=X.id)
    R1 = Recipe(company_id=1, name="MR161 Kvars", batch_size_kg=120, notes="birinchi")
    s.add(R1)
    s.flush()
    s.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=A.id, quantity_kg=2.5),
               RecipeIngredient(recipe_id=R1.id, inventory_id=B.id, quantity_kg=60)])
    _yo = s.query(Yonalish).filter(Yonalish.company_id == 1).first()
    PT = ProductType(company_id=1, name="MR161 Kafel kley", unit="qop", input_template="quantity_only", pricing_formula="unit_based",
                     yonalish_id=_yo.id if _yo else None)
    s.add(PT)
    s.flush()
    BM = BOM(company_id=1, product_type_id=PT.id, variant_name="Standart", batch_quantity=1)
    s.add(BM)
    s.flush()
    s.add(BOMItem(company_id=1, bom_id=BM.id, inventory_id=A.id, quantity=0.5, scrap_factor_percent=0))
    ids.update(R1=R1.id, PT=PT.id, BOM=BM.id)
    return ids


ID = db_ishi(_fikstura)
C = {u: kirish(u) for u in ("mr_admin", "mr_r", "mr_rb", "mr_m", "mr_mb", "mr_b", "mr_mn", "mr_w", "mr_f", "mr_x")}

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Katalog va tayyor rollar")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_b = RX.BANDLAR.get(BAND) or {}
check("K1 band `material_royxat` — «Retsept va ishlab chiqarish» bo'limida, nomi, faqat Ko'rish",
      _b.get("modul") == "ishlab" and _b.get("nom") == BAND_NOMI and tuple(_b.get("amallar") or ()) == ("korish",), _b)
_ish = [b[0] for m in RX.BOLIMLAR if m[0] == "ishlab" for b in m[3]]
check("K2 joyi — «Mahsulot turlari va tarkibi» dan keyin, «Ishlab chiqarish buyurtmalari» dan oldin",
      _ish == ["retsept", "mahsulot_turi", BAND, "ishlab_buyurtma"], _ish)
check("K3 izohda — faqat nomi va birligi, narx va qoldiqsiz; «Materiallar: Ko'rish» bor rol baribir ko'radi",
      "nomi va birligi" in (_b.get("izoh") or "") and "narx va qoldiqsiz" in (_b.get("izoh") or "")
      and "Materiallar: Ko'rish" in (_b.get("izoh") or ""), _b.get("izoh"))
_sk = RX.SAHIFA_KERAK.get(BAND)
check("K4 sahifa bog'liqligi: «Loy retseptlari» yoki «Mahsulot turlari va tarkibi» Ko'rish",
      _sk is not None and set(_sk[0]) == {("retsept", "korish"), ("mahsulot_turi", "korish")}, _sk)
_ak = getattr(RX, "AMAL_KERAK", {})
check("K5 AMAL_KERAK: retsept va mahsulot_turi — Yaratish / Tahrirlash bo'lsa, band YOKI «Materiallar: Ko'rish» kerak",
      all(set(_ak.get(b, ((), (), ""))[0]) == {"yaratish", "tahrirlash"}
          and set(_ak.get(b, ((), (), ""))[1]) == {(BAND, "korish"), ("material", "korish")}
          and BAND_NOMI in _ak.get(b, ((), (), ""))[2] for b in ("retsept", "mahsulot_turi")) and set(_ak) == {"retsept", "mahsulot_turi"},
      _ak)
_ak_yomon = [b for b, (am, k, _m) in _ak.items() if b not in RX.BANDLAR or any(a not in RX.BANDLAR[b]["amallar"] for a in am)
             or any(kb not in RX.BANDLAR or ka not in RX.BANDLAR[kb]["amallar"] for kb, ka in k)]
check("K6 AMAL_KERAK — faqat katalogdagi band / amal", not _ak_yomon and _ak, _ak_yomon)
check("K7 tayyor rollar andozasi: Admin — hammasi (band bilan); Menejer, Omborchi, Moliyachi — bandsiz (o'zgarmagan)",
      BAND in RX.TAYYOR_ROLLAR["admin"]["ruxsatlar"] and all(BAND not in RX.TAYYOR_ROLLAR[k]["ruxsatlar"]
                                                            for k in ("menejer", "omborchi", "moliyachi", "usta")))
_rl = js(C["mr_admin"].get("/api/rollar"))
_kb = {b["kod"]: b for m in (_rl.get("katalog") or []) for b in m.get("bandlar", [])}
check("K8 `/api/rollar` katalogi: band bor; retsept / mahsulot_turi da `amal_kerak` (amallar, kerak, matn), boshqalarida null",
      BAND in _kb and (_kb.get("retsept") or {}).get("amal_kerak", {}) and
      set((_kb["retsept"]["amal_kerak"] or {}).get("amallar", [])) == {"yaratish", "tahrirlash"}
      and {(k["band"], k["amal"]) for k in (_kb.get("mahsulot_turi", {}).get("amal_kerak") or {}).get("kerak", [])}
      == {(BAND, "korish"), ("material", "korish")}
      and _kb.get("kirim", {}).get("amal_kerak", "yo'q") is None and _kb.get(BAND, {}).get("kerak_matn"),
      {k: _kb.get(k) for k in ("retsept", BAND)})
_adm_rol = [r for r in (_rl.get("rollar") or []) if r.get("admin")]
check("K9 Admin roli (sahifada) — yangi band ham belgilangan", _adm_rol and BAND in (_adm_rol[0].get("ruxsatlar") or {}),
      _adm_rol[:1])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. GET /api/material-royxati — ruxsat, maydonlar, qiymatlar")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
J = {u: C[u].get(YOL) for u in C}
_rad = detail(J["mr_r"]) or ""
check("A1 faqat retsept ruxsati (bandsiz) — 403, sababida yangi band nomi («Retsept va ishlab chiqarish → …»)",
      J["mr_r"].status_code == 403 and f"«Retsept va ishlab chiqarish → {BAND_NOMI}»" in _rad and "Ko'rish" in _rad,
      (J["mr_r"].status_code, _rad))
check("A2 faqat tarkib ruxsati (bandsiz) — 403", J["mr_m"].status_code == 403, J["mr_m"].status_code)
check("A3 Moliyachi (bandsiz, «Materiallar» yo'q) — 403", J["mr_f"].status_code == 403, J["mr_f"].status_code)
check("A4 sessiyasiz — 401", mijoz().get(YOL).status_code == 401)
for _u, _n in (("mr_rb", "retsept + band"), ("mr_mb", "tarkib + band"), ("mr_b", "band yolg'iz"), ("mr_mn", "Menejer"),
               ("mr_w", "Omborchi"), ("mr_admin", "Admin")):
    check(f"A5 {_n} — 200, ro'yxat", J[_u].status_code == 200 and isinstance(js(J[_u]), list), (J[_u].status_code, J[_u].text[:200]))
_mayd = set(getattr(RX, "MATERIAL_ROYXAT_MAYDONLAR", ("id", "item_name", "unit", "base_unit", "category")))
check("A6 band bilan (Omborxonasiz) — maydonlar AYNAN: id, item_name, unit, base_unit, category (qoldiq, narx, min, izoh YO'Q)",
      royxat(J["mr_rb"]) and all(set(x) == {"id", "item_name", "unit", "base_unit", "category"} for x in royxat(J["mr_rb"]))
      and _mayd == {"id", "item_name", "unit", "base_unit", "category"}, royxat(J["mr_rb"])[:2])
check("A7 «Materiallar: Ko'rish» bor (Menejer, Omborchi, Admin) — + `stock_quantity`, narx YO'Q",
      all(royxat(J[u]) and all(set(x) == {"id", "item_name", "unit", "base_unit", "category", "stock_quantity"} for x in royxat(J[u]))
          for u in ("mr_mn", "mr_w", "mr_admin")), royxat(J["mr_mn"])[:1])
_sirlar = ("7319", "25017", "41023", "12.37", "41.73", "9.61", "3.91", "MR161 izoh sir")
check("A8 band bilan — javob MATNIDA narx, qoldiq, minimal qoldiq, izoh qiymatlari YO'Q (QIYMAT bo'yicha qidiruv)",
      J["mr_rb"].status_code == 200 and not [v for v in _sirlar if v in J["mr_rb"].text]
      and not [v for v in _sirlar if v in J["mr_b"].text], [v for v in _sirlar if v in J["mr_rb"].text])
check("A9 Admin / Omborchi — narx qiymatlari javobda YO'Q (tanlovga kerak emas), qoldiq bor",
      not [v for v in ("7319", "25017", "41023") if v in J["mr_admin"].text + J["mr_w"].text]
      and "12.37" in J["mr_admin"].text, "")
_inv = js(C["mr_admin"].get("/api/inventory"))
_inv = _inv if isinstance(_inv, list) else []
check("A10 ro'yxat `/api/inventory` bilan AYNAN: id, nomi, birligi, turkumi, qoldig'i va TARTIBI (Admin)",
      [(x["id"], x["item_name"], x["unit"], x.get("base_unit"), x.get("category"), x["stock_quantity"]) for x in _inv]
      == [(x.get("id"), x.get("item_name"), x.get("unit"), x.get("base_unit"), x.get("category"), x.get("stock_quantity"))
          for x in royxat(J["mr_admin"])] and len(_inv) >= 3, (len(_inv), len(royxat(J["mr_admin"]))))
check("A11 band bilan ham AYNAN o'sha materiallar va tartib (qoldiqsiz)",
      [x["id"] for x in _inv] == [x.get("id") for x in royxat(J["mr_rb"])] == [x.get("id") for x in royxat(J["mr_mb"])], "")
_ids_rb = {x.get("id") for x in royxat(J["mr_rb"])}
check("A12 o'chirilgan material va boshqa korxona materiali — ro'yxatda YO'Q", ID["D"] not in _ids_rb and ID["X"] not in _ids_rb
      and ID["A"] in _ids_rb, _ids_rb)
_x = royxat(J["mr_x"])
check("A13 2-korxona hodimi — faqat o'z korxonasi materiallari", [m.get("id") for m in _x] == [ID["X"]], _x)
_a = [x for x in royxat(J["mr_rb"]) if x.get("id") == ID["A"]]
_q = [x for x in royxat(J["mr_rb"]) if x.get("id") == ID["B"]]
check("A14 qiymatlar: nom (« » belgilari bilan) AYNAN, birlik, retsept birligi (qop → kg), turkum; turkumsiz — null",
      _a and _a[0] == {"id": ID["A"], "item_name": "MR161 Kley «A»", "unit": "kg", "base_unit": None,
                       "category": "Kimyoviy qo'shimchalar"}
      and _q and _q[0]["unit"] == "qop" and _q[0]["base_unit"] == "kg"
      and [x.get("category") for x in royxat(J["mr_rb"]) if x.get("id") == ID["C"]] == [None], (_a, _q))
check("A15 `/api/inventory` o'zgarmagan: band bilan (Omborxonasiz) — 403, «Materiallar: Ko'rish» — 200",
      C["mr_rb"].get("/api/inventory").status_code == 403 and C["mr_mn"].get("/api/inventory").status_code == 200)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Shu ruxsat bilan ish — retsept va tarkib")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_tanlov = {x.get("item_name"): x.get("id") for x in royxat(J["mr_rb"])}
_r = C["mr_rb"].post("/api/recipes", json={"name": "MR161 Yangi", "batch_size_kg": 100, "notes": None,
                                           "ingredients": [{"inventory_id": _tanlov.get("MR161 Bo'yoq"), "quantity_kg": 1.5}]})
check("R1 retsept + band: ro'yxatdan tanlangan material bilan yangi retsept — 200",
      _r.status_code == 200 and [i.get("inventory_id") for i in (js(_r).get("ingredients") or [])] == [ID["C"]], _r.text[:300])
_r = C["mr_rb"].put(f"/api/recipes/{ID['R1']}", json={"name": "MR161 Kvars", "batch_size_kg": 120, "notes": "birinchi",
                                                      "ingredients": [{"inventory_id": ID["A"], "quantity_kg": 2.5},
                                                                      {"inventory_id": ID["B"], "quantity_kg": 60},
                                                                      {"inventory_id": _tanlov.get("MR161 Bo'yoq"), "quantity_kg": 3}]})
check("R2 retsept tahriri: yangi material qo'shildi — 200, 3 ta tarkib", _r.status_code == 200
      and len(js(_r).get("ingredients") or []) == 3, _r.text[:300])
_r = C["mr_mb"].post("/api/production/boms", json={"product_type_id": ID["PT"], "variant_name": "MR161 Yozgi", "batch_quantity": 1,
                                                   "notes": None, "items": [{"inventory_id": _tanlov.get("MR161 Qum"),
                                                                             "component_type": "raw_material", "quantity": 20,
                                                                             "scrap_factor_percent": 0}]})
check("R3 tarkib + band: ro'yxatdan tanlangan material bilan yangi tarkib — 200", _r.status_code == 200, _r.text[:300])
check("R4 band yolg'iz (sahifasiz) — retsept yoza olmaydi (403)",
      C["mr_b"].post("/api/recipes", json={"name": "MR161 Y", "batch_size_kg": 1, "notes": None,
                                           "ingredients": [{"inventory_id": ID["A"], "quantity_kg": 1}]}).status_code == 403)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Rollar API — band bilan saqlash, mavjud rollar")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = C["mr_admin"].post("/api/rollar", json={"nom": "MR161 Texnolog", "ruxsatlar": {"retsept": HAMMA, BAND: ["korish"]}})
_rid = js(_r).get("id")
check("M1 Admin: band bilan yangi rol — 200, ruxsatlarda saqlandi", _r.status_code == 200 and (js(_r).get("ruxsatlar") or {}).get(BAND)
      == ["korish"], _r.text[:300])
_r2 = C["mr_admin"].put(f"/api/rollar/{_rid}", json={"ruxsatlar": {"retsept": HAMMA}})
check("M2 band olib tashlandi (tahrir) — 200, ruxsatlarda yo'q", _r2.status_code == 200 and BAND not in (js(_r2).get("ruxsatlar") or {}),
      _r2.text[:300])
_r3 = C["mr_admin"].post("/api/rollar", json={"nom": "MR161 Yomon", "ruxsatlar": {BAND: ["yaratish"]}})
check("M3 bandda bo'lmagan amal (Yaratish) — 400, sababi o'zbekcha", _r3.status_code == 400 and "amali yo'q" in (detail(_r3) or ""),
      _r3.text[:200])
check("M4 menejer (Admin emas) rol saqlay olmaydi — 403",
      C["mr_mn"].post("/api/rollar", json={"nom": "MR161 M", "ruxsatlar": {BAND: ["korish"]}}).status_code == 403)
# eski (zip 160 dan oldingi) rol — bandsiz JSON: ruxsat YO'Q (migratsiya qo'shmaydi — admin o'zi yoqadi)
_eski = db_ishi(lambda s: [r.ruxsatlar for r in s.query(Rol).filter(Rol.company_id == 1, Rol.kod.isnot(None)).all()])
check("M5 tayyor rollar bazada — band qo'shilmagan (Admin yozuvidan tashqari hech birida yo'q; ishga tushishda o'zgarmadi)",
      _eski and not any(BAND in (r or "") for r in db_ishi(lambda s: [x.ruxsatlar for x in s.query(Rol).filter(
          Rol.company_id == 1, Rol.kod.in_(("menejer", "omborchi", "moliyachi"))).all()])), _eski[:2])
_r = C["mr_admin"].put(f"/api/rollar/{_rid}", json={"ruxsatlar": {"retsept": HAMMA, BAND: ["korish"]}})
db_ishi(lambda s: s.query(User).filter(User.username == "mr_r").update({"rol_id": _rid}))
check("M6 rolga band yoqilgach — o'sha foydalanuvchi qayta kirmasdan ro'yxatni oladi (200)",
      _r.status_code == 200 and C["mr_r"].get(YOL).status_code == 200, _r.text[:200])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Shablonlar (statik) va sahifalar (server chizgan)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
REC = oqi("templates/recipes.html")
PRD = oqi("templates/production.html")
ROL = oqi("templates/rollar.html")
check("S1 retsept oynasi ro'yxatni `/api/material-royxati` dan oladi (`/api/inventory` emas)",
      "fetch('/api/material-royxati')" in REC and "fetch('/api/inventory')" not in REC)
check("S2 tarkib oynasi ro'yxatni `/api/material-royxati` dan oladi; xato sababi saqlanadi (`invItemsXato`), oynada ko'rsatiladi",
      "fetch('/api/material-royxati')" in PRD and "fetch('/api/inventory')" not in PRD and "let invItemsXato = '';" in PRD
      and 'id="bom-material-xato"' in PRD and "function bomMaterialXatoKorsat()" in PRD)
check("S3 tarkib oynasi: «(yashirilgan)» yo'q — ro'yxat yuklangan bo'lsa «(o'chirilgan)», yuklanmasa belgisiz",
      "(yashirilgan)" not in PRD and "${royxatBor ? \" (o'chirilgan)\" : ''}" in PRD
      and "— Material tanlab bo'lmaydi —" in PRD)
check("S4 qoldiq faqat kelganda («— omborda …»), aks holda tarkib birligi (`bomMaterialMatni`)",
      "function bomMaterialMatni(i)" in PRD and "typeof i.stock_quantity === 'number'" in PRD)
check("S5 buyurtmalar: ruxsatsiz — so'rov yo'q (`PO_KORISH`), xato sababi jadvalda (`poXato`)",
      "var PO_KORISH = {{ 'true' if current_user.ruxsat('ishlab_buyurtma', 'korish') else 'false' }};" in PRD
      and "if (!PO_KORISH) return;" in PRD and "let poXato = '';" in PRD and "${poXato ? escapeHtml(poXato)" in PRD)
check("S6 Rollar sahifasi: `amal_kerak` ogohlantirishi (faqat shu amallar berilganda)",
      "const ak = b.amal_kerak;" in ROL and "ak.amallar.some(a => bor.has(a))" in ROL and "escapeHtml(ak.matn)" in ROL)
_pm = C["mr_m"].get("/production").text
_prm = C["mr_admin"].get("/production").text
check("S7 /production — «Ishlab chiqarish buyurtmalari» ruxsati yo'q rolga «Ishlab chiqarish» yorlig'i chizilmaydi, PO_KORISH = false",
      'data-tab="orders"' not in _pm and "var PO_KORISH = false;" in _pm and 'data-tab="types"' in _pm, _pm[:200])
check("S8 /production — Admin: yorliq bor, PO_KORISH = true", 'data-tab="orders"' in _prm and "var PO_KORISH = true;" in _prm)
_rec = C["mr_rb"].get("/recipes")
check("S9 /recipes — retsept + band roli: 200", _rec.status_code == 200, _rec.status_code)
_rp = C["mr_admin"].get("/rollar").text
check("S10 /rollar (Admin) — yordam oynasida yangi ruxsat izohi", BAND_NOMI in _rp and "nomi va birligi" in _rp)

print("\n" + "=" * 70)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
