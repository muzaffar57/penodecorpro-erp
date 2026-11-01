#!/usr/bin/env python3
"""
test_komplekt239.py — kech173 (zip 239 «ERP buyurtma qatorlarida komplekt belgisi»; reja «Onlayn do'kon rejasi» 30.10, «Komplekt ERP'da qanday
bilinadi» 4-band: saytdan kelgan komplekt detallarga ajralib oddiy qatorlar bo'lib tushadi, lekin shu qatorlar bitta komplektdan ekanini ERP
biladi — buyurtma sahifasida, yuk xatida va PDF da «R-18 rom komplekti, O'rta — 3 komplekt» sarlavhasi, tagida detallari; bekor qilishda
butun komplekt yoki alohida detal; «O'z o'lchamingiz bilan» 4-band: bir modelning detallari — «o'z o'lchami» guruhi).

NIMA UCHUN KERAK
  Xato — komplekt detallari ERP da sarlavhasiz aralashib ketishi (bir nomli uchta «Rom karnizi R-18» — qaysi komplektdan, omborchi bilmaydi),
  tahrirda belgining yo'qolishi / boshqa qatorga o'tishi, eski ochiq sahifa saqlaganda belgining o'chishi, yarim belgi yoki bir guruhda ikki
  xil sarlavha, sarlavhadagi matn bilan HTML / PDF buzilishi, «o'z o'lchami» narxining alohida detal narxidan farq qilishi, boshqa model /
  boshqa o'lcham / toq metr / ombordan bilan «o'z o'lchami» qabul qilinishi, hisob-kitobning (narx, jami) belgi sababli o'zgarishi.
BO'LIMLAR
  S — statik. O — do'kon «o'z o'lchami» qatori. T — tasdiq → ERP qatorlari belgi bilan. E — tahrir (saqlanadi / uziladi / eski sahifa) va
  sxema tekshiruvi. C — qo'lda buyurtma va taklif. P — PDF (buyurtma hisobi, yuk xati, kutilayotganlar, hisob-kitob varaqasi, taklif).
  R — qaytarish tanlovi, yetkazish holati. Z — zaxira. U — HAQIQIY brauzer.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` (U — faqat SQLite / TF1). `T239_TEZ=1` — U o'tkaziladi.
Asl kodga (zip 238) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_komplekt239.py
"""
import os
import io
import sys
import json
import tempfile
import threading
import contextlib
import subprocess

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
TEZ = os.environ.get("T239_TEZ") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "komplekt239_test"
_T = tempfile.mkdtemp(prefix="t239_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't239.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, OrderItem, Inventory      # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if callable(detail):
        try:
            detail = detail()
        except Exception as e:             # noqa: BLE001
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
        x = r.json()
        return x if isinstance(x, (dict, list)) else {}
    except Exception:                      # noqa: BLE001
        return {}


def det(r):
    d = js(r)
    return str(d.get("detail") if isinstance(d, dict) else d)


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def xavfsiz(fn, std=None):
    try:
        return db_ishi(fn)
    except Exception:                      # noqa: BLE001
        return std


def pdf_matn(r):
    p = os.path.join(_T, "x.pdf")
    with open(p, "wb") as f:
        f.write(r.content)
    return subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True).stdout


def kmp(it):
    return (it.get("kmp_guruh"), it.get("kmp_turi"), it.get("kmp_nomi"), it.get("kmp_soni"))


main._send_telegram = lambda *a, **k: True
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t239_admin", PAROL, UserRole.ADMIN, "T239 Admin", company_id=1)
    auth.create_user(s, "t239_plat", PAROL, UserRole.ADMIN, "T239 Platforma", company_id=1)
s.query(User).filter(User.username == "t239_plat").first().is_platform_admin = True
RETSEPT = models.Recipe(company_id=1, name="Qoplama T239")
s.add(RETSEPT)
s.add(Inventory(company_id=1, item_name="Penoplast T239", unit="blok", is_penoplast=True, is_default_penoplast=True,
                volume_per_unit=1.0, price_per_unit=1000000, stock_quantity=50))
s.commit()
RID = RETSEPT.id
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t239_admin")
CP = mijoz("t239_plat")
DOK = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
BY = "/api/dokon/v1/buyurtmalar"
SB = "/api/sayt-buyurtmalari"
KALIT = {"A": None}
_kn = [0]


def yubor(tana_):
    for _ch in ("_DOKON_BUYURTMA_CHEKLOV", "_DOKON_API_CHEKLOV"):
        if hasattr(crud, _ch):
            getattr(crud, _ch).tozala()
    _kn[0] += 1
    h = {"Content-Type": "application/json", "X-Dokon-Kalit": KALIT["A"] or "pdk_x", "X-Amal-Kaliti": f"savat-{_kn[0]:06d}-t239"}
    return DOK.post(BY, content=json.dumps(tana_).encode("ascii"), headers=h)


def tana(qatorlar):
    return {"mijoz": "Vali Aliyev", "telefon": "+998 91 222 33 %02d" % (_kn[0] % 100), "viloyat": "andijon", "qatorlar": qatorlar}


def sb_id(raqam):
    return xavfsiz(lambda d: d.query(models.DokonBuyurtma.id).filter(models.DokonBuyurtma.company_id == 1,
                                                                     models.DokonBuyurtma.sb_raqam == raqam).scalar())


def tasdiqla(raqam):
    r = CA.post(SB + f"/{sb_id(raqam)}/tasdiqla", json={"deadline": "2026-11-20", "recipe_id": RID})
    return r, (js(r).get("order_id") or (js(r).get("order") or {}).get("id"))


def buyurtma(oid):
    return js(CA.get(f"/api/orders/{oid}"))


def forma_tanasi(o, kmp_bilan=True):
    """Tahrir formasi yuboradigan tana (forma `collectItems` kabi: id, qiymatlar; `kmp_bilan` — yangi forma belgini qaytaradi)."""
    items = []
    for it in o["items"]:
        x = {k: it.get(k) for k in ("id", "name", "category", "width", "thickness", "length", "quantity", "is_coated", "price_per_m3",
                                     "finished_product_id", "penoplast_id")}
        x["unit_price"] = float(it["unit_price"])
        if it.get("category") == "dona":
            x["unit_price_for_volume"] = it.get("unit_price") / 2 if it.get("is_coated") else it.get("unit_price")
        if kmp_bilan:
            x.update({"kmp_guruh": it.get("kmp_guruh"), "kmp_turi": it.get("kmp_turi"), "kmp_nomi": it.get("kmp_nomi"),
                      "kmp_soni": it.get("kmp_soni")})
        items.append(x)
    return {"project_id": o["project_id"], "order_type": "product", "items": items, "recipe_id": RID,
            "agreed_amount": float(o.get("kelishilgan_asl") or o.get("agreed_amount") or 0)}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_c = OrderItem.__table__.c
check("S1 order_items: kmp_guruh / kmp_turi / kmp_nomi / kmp_soni — NULL bo'ladi, standart qiymatsiz (eski qatorlar — guruhsiz)",
      all(k in _c and _c[k].nullable and _c[k].default is None for k in ("kmp_guruh", "kmp_turi", "kmp_nomi", "kmp_soni"))
      and str(_c.kmp_turi.type) == "VARCHAR(20)" and str(_c.kmp_nomi.type) == "VARCHAR(200)")
check("S2 sarlavha qoidasi: komplekt — «<nomi> — 3 komplekt», o'z o'lchami — nomi, to'liq bo'lmagan — None",
      lambda: models.kmp_sarlavha(OrderItem(kmp_guruh=1, kmp_turi="komplekt_rom", kmp_nomi="R-18", kmp_soni=3)) == "R-18 — 3 komplekt"
      and models.kmp_sarlavha(OrderItem(kmp_guruh=2, kmp_turi="oz_olcham", kmp_nomi="R-12, O'rta, o'z o'lchami")) == "R-12, O'rta, o'z o'lchami"
      and models.kmp_sarlavha(OrderItem(kmp_guruh=None, kmp_turi="oz_olcham", kmp_nomi="x")) is None
      and models.kmp_sarlavha(OrderItem(kmp_guruh=1, kmp_turi="boshqa", kmp_nomi="x")) is None)


def _s3():
    _a, _b, _d = (OrderItem(id=1, kmp_guruh=1, kmp_turi="komplekt_rom", kmp_nomi="A", kmp_soni=2), OrderItem(id=2),
                  OrderItem(id=3, kmp_guruh=1, kmp_turi="komplekt_rom", kmp_nomi="A", kmp_soni=2))
    return [(s_, [x.id for x in q]) for s_, _t, q in models.kmp_bloklari([_a, _b, _d])]


check("S3 guruhlash: guruh qatorlari birinchi uchragan joyida yig'iladi (keyin qo'shilgani ham), guruhsiz — o'z blokida, tartib saqlanadi",
      lambda: _s3() == [("A — 2 komplekt", [1, 3]), (None, [2])], lambda: _s3())
_bh = open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8").read()
_oh = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_rh = open(os.path.join(ROOT, "templates", "returns.html"), encoding="utf-8").read()
check("S4 sahifa: base.html da kmpSarlavha / kmpBloklari (server qoidasi bilan bir xil), orders.html — buyurtma oynasi, yetkazish oynasi, "
      "nusxa tanlovi, tahrir formasi; returns.html — tanlovda guruh",
      "function kmpSarlavha(" in _bh and "function kmpBloklari(" in _bh and _oh.count("kmpBloklari(") == 3
      and "kmpQatorgaYoz239(row, kmpTolikmi239(item, itemsToUse, order.items) ? item : null)" in _oh and "kmpTanaga239(x, _q220)" in _oh and "kmpBloklari(currentOrderItems)" in _rh)

# ── Sinov katalogi ──
r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
KALIT["A"] = js(CA.post(API + "/api-kalit", json={})).get("kalit")
K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}
KOMP, KAR = BOL.get("Rom va eshik dekorlari"), BOL.get("Karnizlar")


def model(bolim, kod, **kw):
    return js(CA.post(API + "/modellar", json=dict({"bolim_id": bolim, "kod": kod}, **kw))).get("id")


def detal(mid, turi, olcham, **kw):
    return js(CA.post(API + "/detallar", json=dict({"model_id": mid, "turi": turi, "olcham": olcham}, **kw))).get("id")


ORTA = "O'rta"
M1 = model(KOMP, "R-18", nom="Klassik", kapitel_baza_bor=True)
NARX = {"karniz": 15000, "podokonnik": 14000, "nalichnik": 12000, "kapitel": 30000, "baza": 31000}
DID = {t: detal(M1, t, ORTA, narx=n, eni_sm=15, qalinligi_sm=10) for t, n in NARX.items()}
DID["katta"] = detal(M1, "karniz", "Katta", narx=19000, eni_sm=18, qalinligi_sm=10)
DID["narxsiz"] = detal(M1, "podokonnik", "Katta", narx=None)
DID["kq"] = detal(M1, "karniz", "Kichik", narx=None, narx_qoplamali=40000, eni_sm=12, qalinligi_sm=10)   # faqat qoplamali narxi bor
DID["kk"] = detal(M1, "kapitel", "Kichik", narx=25000)
M3 = model(KOMP, "R-20", nom="Zamonaviy", kapitel_baza_bor=False)
DID["r20"] = detal(M3, "karniz", ORTA, narx=16000, eni_sm=15, qalinligi_sm=10)
M2 = model(KAR, "K-12", nom="Tekis")
DID["k12"] = detal(M2, "asosiy", "12 sm", narx=45000, eni_sm=12, qalinligi_sm=8)
check("S5 katalog: R-18 (O'rta + Katta), R-20, K-12", all(DID.values()) and M1 and M2 and M3, DID)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("O. Do'kon: «o'z o'lchami» qatori")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
OZ = [{"detal_id": DID["karniz"], "miqdor": 4}, {"detal_id": DID["podokonnik"], "miqdor": 2}, {"detal_id": DID["kapitel"], "miqdor": 3}]
Q = [{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": True, "kapitel_baza": True, "soni": 3},
     {"komplekt": "eshik", "model_id": M1, "olcham": ORTA, "qoplamali": False, "kapitel_baza": False, "soni": 1},
     {"oz_olcham": OZ, "qoplamali": True},
     {"detal_id": DID["k12"], "qoplamali": False, "miqdor": 6}]
r = yubor(tana(Q))
J = js(r)
G = J.get("guruhlar") or []
check("O1 savat (rom × 3, eshik × 1, o'z o'lchami, K-12) — 200; jami 1 368 000 + 90 000 + 356 000 + 270 000 = 2 084 000",
      r.status_code == 200 and J.get("jami") == 2084000.0, (r.status_code, r.text[:300]))
_oz = next((g for g in G if g.get("tur") == "oz_olcham"), {})
check("O2 «o'z o'lchami» — BITTA guruh (3 detal: karniz 4 m, podokonnik 2 m, kapitel 3 dona), nomi «R-18 «Klassik», O'rta, o'z o'lchami, "
      "qoplamali», komplektlar soni yo'q, summa 120 000 + 56 000 + 180 000",
      _oz.get("guruh_nomi") == "R-18 «Klassik», O'rta, o'z o'lchami, qoplamali" and _oz.get("komplekt_soni") is None
      and [(x.get("miqdor"), x.get("narx")) for x in _oz.get("detallar", [])] == [(4.0, 30000.0), (2.0, 28000.0), (3.0, 60000.0)]
      and _oz.get("summa") == 356000.0, _oz)


def _hisob(q):
    return xavfsiz(lambda d: crud.sayt_buyurtma_hisobla(d, 1, q), {"qatorlar": [], "jami": None})


db_ishi(lambda d: d.add(models.DokonChegirma(company_id=1, model_id=M1, foiz=10)))
_h1 = _hisob([{"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 4}, {"detal_id": DID["kapitel"], "miqdor": 1}], "qoplamali": False}])
_h2 = _hisob([{"detal_id": DID["karniz"], "qoplamali": False, "miqdor": 4}, {"detal_id": DID["kapitel"], "qoplamali": False, "miqdor": 1}])
check("O3 narx qoidasi — alohida detal qatori bilan AYNAN (chegirma 10 % ham): karniz 13 500 × 4, kapitel 27 000 × 1",
      [(x["narx"], x["asl_narx"], x["chegirma_foiz"], x["summa"]) for x in _h1["qatorlar"]]
      == [(x["narx"], x["asl_narx"], x["chegirma_foiz"], x["summa"]) for x in _h2["qatorlar"]]
      and _h1["jami"] == _h2["jami"] == 81000 and len(_h1["qatorlar"]) == 2, (_h1, _h2))
_h3 = _hisob([{"oz_olcham": [{"detal_id": DID["kq"], "miqdor": 2}, {"detal_id": DID["kk"], "miqdor": 1}], "qoplamali": True}])
_h4 = _hisob([{"detal_id": DID["kq"], "qoplamali": True, "miqdor": 2}, {"detal_id": DID["kk"], "qoplamali": True, "miqdor": 1}])
check("O3b qoplamasiz narxi yo'q detal (faqat qoplamali 40 000) — chegirma qoidasi ham alohida detal qatoridek (chegirmasiz 40 000; "
      "kapitel 50 000 → 45 000)",
      [(x["narx"], x["chegirma_foiz"]) for x in _h3["qatorlar"]] == [(x["narx"], x["chegirma_foiz"]) for x in _h4["qatorlar"]]
      == [(40000, None), (45000, 10)], (_h3, _h4))
db_ishi(lambda d: d.query(models.DokonChegirma).filter(models.DokonChegirma.model_id == M1).delete())
_rad = [({"oz_olcham": [], "qoplamali": True}, "kamida bitta"),
        ({"oz_olcham": {"detal_id": DID["karniz"]}, "qoplamali": True}, "kamida bitta"),
        ({"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 2}] * 11, "qoplamali": True}, "ko'pi bilan"),
        ({"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 2}, {"detal_id": DID["r20"], "miqdor": 2}], "qoplamali": True}, "bitta model"),
        ({"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 2}, {"detal_id": DID["katta"], "miqdor": 2}], "qoplamali": True}, "bitta o'lcham"),
        ({"oz_olcham": [{"detal_id": DID["k12"], "miqdor": 2}], "qoplamali": True}, "rom va eshik"),
        ({"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 2}, {"detal_id": DID["karniz"], "miqdor": 4}], "qoplamali": True}, "ikki marta"),
        ({"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 3}], "qoplamali": True}, "juft metr"),
        ({"oz_olcham": [{"detal_id": DID["kapitel"], "miqdor": 1.5}], "qoplamali": True}, "butun son"),
        ({"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 2}], "qoplamali": True, "ombordan": True}, "ombordan"),
        ({"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 2, "narx": 1}], "qoplamali": True}, "narx"),
        ({"oz_olcham": [{"detal_id": DID["narxsiz"], "miqdor": 2}], "qoplamali": True}, "narxi kiritilmagan"),
        ({"oz_olcham": [{"detal_id": 999999, "miqdor": 2}], "qoplamali": True}, "sotuvda yo'q"),
        ({"oz_olcham": ["x"], "qoplamali": True}, "noto'g'ri qator"),
        ({"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 2}], "qoplamali": "ha"}, "qoplamali")]
_n0 = xavfsiz(lambda d: d.query(models.DokonBuyurtma).count(), -1)
_rr = [yubor(tana([q])) for q, _ in _rad]
check("O4 rad (400, hech narsa yozilmaydi): bo'sh / ro'yxat emas, 11 detal, boshqa model, boshqa o'lcham, komplekt bo'lmagan model, bir detal "
      "ikki marta, toq metr, kasr dona, «ombordan», noma'lum maydon, narxsiz, yo'q detal, noto'g'ri qator, qoplamali — matn emas",
      all(x.status_code == 400 and m in det(x) for x, (_, m) in zip(_rr, _rad))
      and xavfsiz(lambda d: d.query(models.DokonBuyurtma).count(), -2) == _n0,
      [(x.status_code, det(x)[:80]) for x in _rr])

M9 = model(KOMP, "R-99", nom="Juda uzun nom " + "X" * 100, kapitel_baza_bor=True)
DID["r99k"] = detal(M9, "karniz", "Juda katta o'lcham 30 belgi", narx=15000, eni_sm=15, qalinligi_sm=10)
DID["r99n"] = detal(M9, "nalichnik", "Juda katta o'lcham 30 belgi", narx=12000, eni_sm=15, qalinligi_sm=10)
_hu = _hisob([{"komplekt": "eshik", "model_id": M9, "olcham": "Juda katta o'lcham 30 belgi", "qoplamali": True, "kapitel_baza": False,
               "soni": 12}, {"oz_olcham": [{"detal_id": DID["r99k"], "miqdor": 2}], "qoplamali": False}])
_gn = [x["guruh_nomi"] for x in _hu["qatorlar"]]
check("O5 (review239 L4) uzun model nomi — guruh nomi ≤ 200, MODEL NOMI qisqaradi («…»), oxiri (o'lcham, qoplama, kapitelsiz, × 12) "
      "butun",
      len(_gn) == 3 and all(len(x) <= 200 for x in _gn) and "…" in _gn[0] and len(_gn[0]) == 200
      and _gn[0].endswith(", Juda katta o'lcham 30 belgi, qoplamali, kapitel va bazasiz × 12")
      and _gn[2].endswith(", Juda katta o'lcham 30 belgi, o'z o'lchami, qoplamasiz") and _gn[0].startswith("R-99 «Juda uzun nom XXX"), _gn)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Tasdiq → ERP qatorlari belgi bilan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r, OID = tasdiqla(J.get("raqam")) if J.get("raqam") else (None, None)
if not OID:
    # asl kod (zip 238) «o'z o'lchami» qatorini rad etadi — qolgan bo'limlar shu buyurtmaga tayanadi (QULAMAYDI, yiqiladi)
    check("T0 tasdiqlangan ERP buyurtmasi bor (qolgan bo'limlar uchun)", False, (getattr(r, "status_code", None), J))
    print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
    print("YIQILGANLAR:\n  " + "\n  ".join(FAILED))
    sys.exit(1)
O = buyurtma(OID)
IT = O.get("items") or []
_k = [kmp(x) for x in IT]
ROM = (1, "komplekt_rom", "R-18 «Klassik» — rom komplekti, O'rta, qoplamali", 3)
ESH = (2, "komplekt_eshik", "R-18 «Klassik» — eshik komplekti, O'rta, qoplamasiz, kapitel va bazasiz", 1)
OZB = (3, "oz_olcham", "R-18 «Klassik», O'rta, o'z o'lchami, qoplamali", None)
check("T1 tasdiq 200; 11 qator: rom komplekti — 5 (guruh 1, «… qoplamali», 3 komplekt; « × 3» sarlavhada YO'Q), eshik — 2 (guruh 2), "
      "o'z o'lchami — 3 (guruh 3, soni yo'q), K-12 — guruhsiz",
      r.status_code == 200 and _k == [ROM] * 5 + [ESH] * 2 + [OZB] * 3 + [(None, None, None, None)], (r.status_code, r.text[:200], _k))
check("T2 hisob-kitob o'zgarmagan: jami / kelishilgan = sayt summasi 2 084 000; qatorlar narxi sayt qotirgani",
      float(O.get("total_amount") or 0) == 2084000 and float(O.get("kelishilgan_asl") or O.get("agreed_amount") or 0) == 2084000
      and [x["total_price"] for x in IT] == [180000, 168000, 288000, 360000, 372000, 30000, 60000, 120000, 56000, 180000, 270000],
      [x["total_price"] for x in IT])
_db = xavfsiz(lambda d: [(x.kmp_guruh, x.kmp_turi, x.kmp_nomi, x.kmp_soni) for x in
                         d.query(OrderItem).filter(OrderItem.order_id == OID).order_by(OrderItem.id).all()], [])
check("T3 bazada ham AYNAN (javob = ustunlar)", _db == _k, _db)
# ombordan komplekt — partiyalarga bo'linsa ham har qism belgili
_tm = {}
for _t, (cat, unit) in {"karniz": ("profil", "metr"), "podokonnik": ("profil", "metr"), "nalichnik": ("profil", "metr"),
                        "kapitel": ("dona", "dona"), "baza": ("dona", "dona")}.items():
    for _q in ((1.0, 3.0) if _t == "karniz" else (9.0,)):          # karniz 4 m — ikki partiyadan (1 + 3)
        db_ishi(lambda d, cat=cat, unit=unit, _t=_t, _q=_q: d.add(models.FinishedProduct(
            company_id=1, name=f"{_t.capitalize()} R-18 15 sm", category=cat, is_coated=True, width=15.0 if cat == "profil" else None,
            thickness=10.0 if cat == "profil" else None, quantity=_q, produced_quantity=_q, unit=unit, unit_price=1, cost_price=_q * 1000,
            unit_cost_stable=1000, source=models.StockSource.PRODUCED, unit_volume_m3=0.01, volume_m3=0.01 * _q,
            production_status=models.ProductionStatus.READY)))
_ml = js(CA.get(API + "/tm-mahsulotlar")).get("mahsulotlar") or []
for _t in ("karniz", "podokonnik", "nalichnik", "kapitel", "baza"):
    _kk = next((x.get("kalit") for x in _ml if (x.get("nom") or "").lower().startswith(_t)), None)
    CA.put(API + f"/detallar/{DID[_t]}/tm", json={"tm_kaliti": _kk})
r = yubor(tana([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": True, "kapitel_baza": True, "soni": 2, "ombordan": True}]))
r2, OID2 = tasdiqla(js(r).get("raqam"))
IT2 = buyurtma(OID2).get("items") or [] if OID2 else []
check("T4 ombordan komplekt × 2 — partiyadan olingan 5 qator (ERP guruh qoidasi: karniz 4 m — bitta partiya qatori, guruhdoshdan "
      "muvozanat) HAMMASI bitta guruhda, «…, ombordan», 2 komplekt",
      r.status_code == 200 and r2.status_code == 200 and len(IT2) == 5 and all(x.get("finished_product_id") for x in IT2)
      and {kmp(x) for x in IT2} == {(1, "komplekt_rom", "R-18 «Klassik» — rom komplekti, O'rta, qoplamali, ombordan", 2)},
      (r.text[:200], r2.text[:200], [kmp(x) for x in IT2]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Tahrir va sxema tekshiruvi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def tahrir(tana_):
    return CA.put(f"/api/orders/{OID}", json=tana_)


r = tahrir(forma_tanasi(O))
O_ = buyurtma(OID)
check("E1 o'zgarishsiz saqlash (yangi forma — belgini qaytaradi) — 200, belgilar va jami o'zgarmadi",
      r.status_code == 200 and [kmp(x) for x in O_["items"]] == _k and float(O_["total_amount"]) == 2084000, (r.status_code, r.text[:300]))
_ft = forma_tanasi(O_, kmp_bilan=False)
r = tahrir(_ft)
check("E2 eski ochiq sahifa (kmp kalitlari YO'Q) saqlasa — belgilar saqlanadi", r.status_code == 200
      and [kmp(x) for x in buyurtma(OID)["items"]] == _k, (r.status_code, r.text[:300]))
_ft = forma_tanasi(buyurtma(OID))
_ft["items"][2]["quantity"], _ft["items"][2]["length"] = 1.0, 10.0          # nalichnik 12 → 10 m
_ft["items"][2]["unit_price"] = 240000.0
_ft["items"][5] = dict(_ft["items"][5], kmp_guruh=None, kmp_turi=None, kmp_nomi=None, kmp_soni=None)   # eshik karnizi — guruhdan chiqarildi
del _ft["items"][6]                                                        # eshik nalichnigi — olib tashlandi (alohida detal bekor)
_yangi = dict(_ft["items"][0])
_yangi.pop("id")
_yangi["length"], _yangi["unit_price"] = 2.0, 60000.0                       # rom komplektiga yana 2 m karniz (yangi qator)
_ft["items"].append(_yangi)
_ft["agreed_amount"] = None
r = tahrir(_ft)
O3 = buyurtma(OID)
_k3 = [kmp(x) for x in O3.get("items") or []]
check("E3 tahrir: o'zgargan qator belgisi qoladi, null yuborilgani guruhsiz, olib tashlangani yo'q, yangi qo'shilgani (belgi bilan) — o'z "
      "komplektida",
      r.status_code == 200 and _k3[:5] == [ROM] * 5 and _k3[5] == (None, None, None, None) and _k3[6:9] == [OZB] * 3
      and _k3[9] == (None, None, None, None) and _k3[10] == ROM and len(_k3) == 11, (r.status_code, r.text[:300], _k3))
_blk = xavfsiz(lambda d: [(s_, [x.id for x in q]) for s_, _t, q in models.kmp_bloklari(
    d.query(OrderItem).filter(OrderItem.order_id == OID).order_by(OrderItem.id).all())], [])
check("E4 guruhlash: yangi qo'shilgan karniz — rom komplekti sarlavhasi TAGIDA (6 detal), eshik komplekti sarlavhasi yo'qoldi",
      [s_ for s_, _q in _blk] == [ROM[2] + " — 3 komplekt", None, OZB[2], None] and len(_blk[0][1]) == 6, _blk)
_b = forma_tanasi(O3)
_x0 = _b["items"][0]


def _bilan(**kw):
    """Tanaga ALOHIDA guruhli (99) yangi qator qo'shiladi va uning belgisi `kw` bilan buziladi (boshqa guruh bilan solishtirish emas —
    faqat qatorning o'z qoidasi tekshiriladi); «bir guruhda ikki xil nom» — mavjud guruhning bitta qatori o'zgartiriladi."""
    t = json.loads(json.dumps(_b))
    if kw.pop("_mavjud", False):
        t["items"][0].update(kw)
        return t
    y = {k: v for k, v in t["items"][0].items() if k != "id"}
    y.update({"name": "Sinov detal E5", "kmp_guruh": 99, "kmp_turi": "komplekt_rom", "kmp_nomi": "Sinov komplekti", "kmp_soni": 1})
    y.update(kw)
    t["items"].append(y)
    return t


_sxema = [("yarim belgi (faqat guruh)", _bilan(kmp_turi=None, kmp_nomi=None, kmp_soni=None)),
          ("o'z o'lchamida soni", _bilan(kmp_turi="oz_olcham", kmp_soni=2)),
          ("komplektda soni yo'q", _bilan(kmp_soni=None)),
          ("noma'lum tur", _bilan(kmp_turi="komplekt_boshqa")),
          ("guruh 0", _bilan(kmp_guruh=0)), ("guruh 1001", _bilan(kmp_guruh=1001)), ("guruh «99» (matn)", _bilan(kmp_guruh="99")), ("guruh 99.0 (kasr ko'rinishi)", _bilan(kmp_guruh=99.0)),
          ("soni «1» (matn)", _bilan(kmp_soni="1")),
          ("guruh true", _bilan(kmp_guruh=True)), ("guruh 1.5", _bilan(kmp_guruh=1.5)),
          ("soni 501", _bilan(kmp_soni=501)), ("nomi 201 belgi", _bilan(kmp_nomi="R" * 201)),
          ("nomi faqat bo'shliq / ko'rinmas belgi", _bilan(kmp_nomi=" ​\t ")),
          ("bir guruhda ikki xil nom", _bilan(_mavjud=True, kmp_nomi="Boshqa sarlavha"))]
_ok5 = tahrir(_bilan())
_k5 = [kmp(x) for x in buyurtma(OID)["items"]]
r = tahrir(_b)                      # qo'shilgan sinov qatori olib tashlanadi
check("E5a nazorat: o'sha yangi qator TO'G'RI belgi bilan — 200 (guruh 99, «Sinov komplekti», 1); olib tashlansa — avvalgidek",
      _ok5.status_code == 200 and (99, "komplekt_rom", "Sinov komplekti", 1) in _k5 and r.status_code == 200
      and [kmp(x) for x in buyurtma(OID)["items"]] == _k3, (_ok5.status_code, _ok5.text[:200], r.status_code))
_rs = [(n, tahrir(t)) for n, t in _sxema]
check("E5 sxema rad (422, hech narsa o'zgarmaydi): yarim belgi, o'z o'lchamida soni, komplektda sonisiz, noma'lum tur, guruh 0 / 1001 / "
      "matn / true / kasr, soni 501, nomi 201, bo'sh nom, bir guruhda ikki xil nom",
      all(x.status_code == 422 for _n, x in _rs) and [kmp(x) for x in buyurtma(OID)["items"]] == _k3,
      [(n, x.status_code, x.text[:120]) for n, x in _rs])
_t = json.loads(json.dumps(_b))
for _it in _t["items"]:
    if _it.get("kmp_guruh") == 1:
        _it["kmp_nomi"] = "  R-18\x00 «Klassik»​ —\trom   komplekti  "
r = tahrir(_t)
check("E6 nomdagi NUL / nol kenglikdagi belgi / tab olib tashlanadi, bo'shliqlar bittaga (bir guruhning hamma qatori bir xil yozilgan)",
      r.status_code == 200 and {x.get("kmp_nomi") for x in buyurtma(OID)["items"] if x.get("kmp_guruh") == 1} == {"R-18 «Klassik» — rom komplekti"},
      (r.status_code, r.text[:200]))
r = tahrir(_b)                      # asl sarlavhaga qaytarish
check("E7 qaytarildi — 200", r.status_code == 200, r.text[:200])
_t = json.loads(json.dumps(_b))
_t["items"][0]["kmp_nomi"] = "Faqat bitta qatorda yangi nom"
for _it in _t["items"][1:]:
    for _kk in ("kmp_guruh", "kmp_turi", "kmp_nomi", "kmp_soni"):
        _it.pop(_kk, None)                  # qolganlari — kalitsiz (eski API: saqlangani qoladi)
r = tahrir(_t)
check("E8 (review239 L1) API bitta qatorning sarlavhasini o'zgartirib, qolganlarini kalitsiz yuborsa — 400 «… har xil bo'lib qoladi», hech narsa "
      "o'zgarmaydi (aks holda buyurtma sahifadan saqlanmay qolardi)",
      r.status_code == 400 and "har xil" in det(r) and [kmp(x) for x in buyurtma(OID)["items"]] == _k3, (r.status_code, r.text[:300]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Qo'lda buyurtma (API) va taklif")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PRJ = O["project_id"]
_ITM = [{"name": "Rom karnizi X-1", "category": "profil", "width": 15, "thickness": 10, "length": 2, "quantity": 1, "unit_price": 30000,
         "is_coated": False, "kmp_guruh": 7, "kmp_turi": "komplekt_rom", "kmp_nomi": "X-1 <b>rom</b> & «komplekt»", "kmp_soni": 1},
        {"name": "Kapitel X-1", "category": "dona", "quantity": 2, "unit_price": 20000, "is_coated": False,
         "kmp_guruh": 7, "kmp_turi": "komplekt_rom", "kmp_nomi": "X-1 <b>rom</b> & «komplekt»", "kmp_soni": 1},
        {"name": "Oddiy karniz", "category": "profil", "width": 10, "thickness": 8, "length": 3, "quantity": 1, "unit_price": 30000,
         "is_coated": False}]
r = CA.post("/api/orders", json={"project_id": PRJ, "order_type": "product", "items": _ITM, "recipe_id": RID})
OIDC = js(r).get("id")
check("C1 qo'lda (API) buyurtma belgi bilan — 200, qatorlarda (guruh 7, HTML belgilar — oddiy matn), uchinchisi guruhsiz",
      r.status_code == 200 and [kmp(x) for x in buyurtma(OIDC).get("items", [])]
      == [(7, "komplekt_rom", "X-1 <b>rom</b> & «komplekt»", 1)] * 2 + [(None, None, None, None)], (r.status_code, r.text[:300]))
r = CA.post("/api/orders", json={"project_id": PRJ, "order_type": "product", "recipe_id": RID,
                                  "items": [dict(_ITM[0]), dict(_ITM[1], kmp_soni=2)]})
check("C2 qo'lda: bir guruhda soni har xil — 422", r.status_code == 422, (r.status_code, r.text[:200]))
_ITM2 = [dict(x, kmp_guruh=8) if x.get("kmp_guruh") else x for x in _ITM]
r = CA.post("/api/orders", json={"project_id": PRJ, "order_type": "product", "items": _ITM2, "recipe_id": RID})
check("C5 (review239 L2) 8 s ichida o'sha detallar, lekin BOSHQA guruh bilan — takror emas: yangi buyurtma (boshqa raqam, guruh 8)",
      r.status_code == 200 and js(r).get("id") not in (None, OIDC)
      and [kmp(x)[0] for x in buyurtma(js(r).get("id")).get("items", [])] == [8, 8, None], (r.status_code, r.text[:200]))
r = CA.post("/api/takliflar", json={"mijoz": "Taklif Mijoz", "telefon": "+998901112233",
                                    "buyurtma": {"order_type": "product", "items": _ITM, "recipe_id": RID}})
TK = (js(r).get("taklif") or {}).get("id")
_tp = pdf_matn(CA.get(f"/api/takliflar/{TK}/pdf")) if TK else ""
check("C3 taklif belgili detallar bilan — 200; taklif PDF da sarlavha «X-1 <b>rom</b> & «komplekt» — 1 komplekt» (matn), tagida 2 detal",
      r.status_code == 200 and "X-1 <b>rom</b> & «komplekt» — 1 komplekt" in _tp
      and _tp.find("— 1 komplekt") < _tp.find("Rom karnizi X-1") < _tp.find("Kapitel X-1") < _tp.find("Oddiy karniz"), (r.text[:200], _tp[:1500]))
_tt = js(CA.get(f"/api/takliflar/{TK}")) if TK else {}
_tt = (_tt.get("taklif") or _tt) if isinstance(_tt, dict) else {}
_tb = (_tt.get("buyurtma") or _tt.get("tana") or {}) if isinstance(_tt, dict) else {}
r = CA.post(f"/api/takliflar/{TK}/rasmiylashtir", json={"loyiha_id": PRJ, "buyurtma": dict(
    {"order_type": "product", "recipe_id": RID}, items=[{k: v for k, v in x.items() if k != "total_price"} for x in (_tb.get("items") or _ITM)])})
_oidt = js(r).get("id")
check("C4 taklif → buyurtma (forma taklif detallarini qaytaradi) — belgi buyurtmaga o'tdi",
      r.status_code == 200 and [kmp(x) for x in buyurtma(_oidt).get("items", [])][:2] == [(7, "komplekt_rom", "X-1 <b>rom</b> & «komplekt»", 1)] * 2,
      (r.status_code, r.text[:300]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PDF hujjatlar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
O = buyurtma(OID)
_p = pdf_matn(CA.get(f"/api/orders/{OID}/pdf"))
_i1, _i2 = _p.find(ROM[2] + " — 3 komplekt"), _p.find(OZB[2])
check("P1 buyurtma hisobi: rom komplekti sarlavhasi, tagida 6 detali (tahrirda qo'shilgani ham), keyin «Alohida detallar» (guruhsiz qator — "
      "komplektdan ajraladi, review239 H1), o'z o'lchami sarlavhasi va 3 detali, yana «Alohida detallar» (K-12); raqamlar 1 … 11 uzluksiz; jami o'zgarmagan",
      _i1 >= 0 and _i2 > _i1 and _p.count("— 3 komplekt") == 1 and "eshik komplekti" not in _p
      and _p.count("Alohida detallar") == 2 and _p.find("Alohida detallar") < _i2 < _p.rfind("Alohida detallar") < _p.find("K-12 Tekis")
      and all(f"\n {n} " in "\n" + "\n".join(" " + ln.strip() for ln in _p.splitlines()) for n in range(1, 12))
      and _p.find("Podokonnik R-18", _i1) < _i2, _p[:2600])
_p = pdf_matn(CA.get(f"/api/orders/{OIDC}/pdf"))
check("P2 sarlavhadagi «<b>» / «&» — PDF da MATN (shablon buzilmaydi)", "X-1 <b>rom</b> & «komplekt» — 1 komplekt" in _p, _p[:1200])
_st = js(CA.get(f"/api/orders/{OID}/delivery-status"))
_dv = {x["id"]: x for x in _st.get("items", [])}
check("R1 yetkazish holati qatorlarida belgi (yetkazish oynasi guruhlaydi)",
      [kmp(_dv[x["id"]]) for x in O["items"]] == [kmp(x) for x in O["items"]], _st)
_ids = [x["id"] for x in O["items"]]
_qty = {x["id"]: float(x["length"] if x["category"] == "profil" else x["quantity"]) for x in O["items"]}
_yuk = [_ids[0], _ids[3], _ids[7], _ids[9]]  # rom karnizi, rom kapiteli, o'z o'lchami detali, K-12 (guruhsiz)
r = CA.post("/api/deliveries", json={"order_id": OID, "items": [{"order_item_id": i, "quantity": _qty[i]} for i in _yuk]})
DLV = js(r).get("delivery_id")
_p = pdf_matn(CA.get(f"/api/deliveries/{DLV}/pdf")) if DLV else ""
_a1, _a2 = _p.find(ROM[2] + " — 3 komplekt"), _p.find(OZB[2])
_kut = _p.find("Keyingi yetkazishda")
check("P3 yuk xati: shu yukdagi rom detallari (karniz, kapitel) o'z sarlavhasi TAGIDA, o'z o'lchami detali — o'z sarlavhasi tagida, K-12 — "
      "«Alohida detallar» tagida (review239 H1)",
      r.status_code == 200 and 0 <= _a1 < _p.find("Rom karnizi R-18", _a1) < _p.find("Kapitel R-18", _a1) < _a2
      < _p.find("Alohida detallar") < _p.find("K-12 Tekis") < _kut, (r.text[:200], _p[:2500]))
_kq = _p[_kut:]
check("P4 yuk xati «Keyingi yetkazishda kutilayotgan mahsulotlar»: qolgan rom detallari va o'z o'lchami detallari ham sarlavha bilan",
      ROM[2] + " — 3 komplekt" in _kq and OZB[2] in _kq and _kq.find(ROM[2]) < _kq.find("Podokonnik R-18"), _kq[:1500])
_p = pdf_matn(CA.get(f"/api/orders/{OID}/summary-pdf"))
check("P5 hisob-kitob varaqasi: yuk xati bo'limida komplekt sarlavhalari, tagida detallar",
      ROM[2] + " — 3 komplekt" in _p and _p.find("Yuk xati") < _p.find(ROM[2]) < _p.find("Rom karnizi R-18") and OZB[2] in _p, _p[:2000])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Qaytarish tanlovi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_tq = js(CA.get(f"/api/tanlov/buyurtmalar/{OID}/detallar"))
check("R2 qaytarish tanlovi detallarida belgi (sahifa komplekt guruhi ostida ko'rsatadi)",
      [kmp(x) for x in _tq.get("items", [])] == [kmp(x) for x in O["items"]], _tq)
r = CA.post("/api/returns", json={"order_id": OID, "order_item_id": _ids[0], "item_name": O["items"][0]["name"], "quantity": 1,
                                  "unit": "metr", "reason": "Mijoz iltimosi", "refund_amount": 0, "to_stock": True})
check("R3 komplekt detalini ALOHIDA qaytarish — avvalgidek ishlaydi (200), belgi o'zgarmaydi",
      r.status_code == 200 and kmp(buyurtma(OID)["items"][0]) == ROM, (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_k0 = xavfsiz(lambda d: sorted((x.id, x.kmp_guruh, x.kmp_turi, x.kmp_nomi, x.kmp_soni) for x in d.query(OrderItem)
                                .filter(OrderItem.company_id == 1, OrderItem.kmp_guruh.isnot(None)).all()))
_zx = db_ishi(lambda d: crud.export_full_backup(d, 1))
try:
    db_ishi(lambda d: crud.import_full_backup(d, _zx, 1, replace=True))
    _tx = None
except Exception as e:                      # noqa: BLE001
    _tx = f"{type(e).__name__}: {e}"
_k1 = xavfsiz(lambda d: sorted((x.id, x.kmp_guruh, x.kmp_turi, x.kmp_nomi, x.kmp_soni) for x in d.query(OrderItem)
                                .filter(OrderItem.company_id == 1, OrderItem.kmp_guruh.isnot(None)).all()))
check("Z1 zaxira → tiklash: buyurtma qatorlarining komplekt belgilari AYNAN", _tx is None and _k1 == _k0 and len(_k0 or []) >= 10,
      lambda: (_tx, len(_k0 or []), (_k0 or [])[:2], (_k1 or [])[:2]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL or TEZ:
    print("  (U — PG / T239_TEZ da o'tkaziladi)")
else:
    import time as _tm
    import socket
    import uvicorn
    from playwright.sync_api import sync_playwright
    _s = socket.socket()
    _s.bind(("127.0.0.1", 0))
    PORT = _s.getsockname()[1]
    _s.close()
    _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error"))
    threading.Thread(target=_srv.run, daemon=True).start()
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=0.2).close()
            break
        except OSError:
            _tm.sleep(0.1)
    BASE = f"http://127.0.0.1:{PORT}"
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1366, "height": 900})
            pg = ctx.new_page()
            JSX = []
            pg.on("pageerror", lambda e: JSX.append(str(e)))
            pg.on("dialog", lambda d: d.dismiss())
            pg.goto(BASE + "/login")
            pg.fill("input[name=username]", "t239_admin")
            pg.fill("input[name=password]", PAROL)
            pg.click("button[type=submit]")
            pg.wait_for_load_state("networkidle")
            pg.goto(BASE + "/orders")
            pg.wait_for_load_state("networkidle")
            pg.wait_for_selector(f".ord-item[data-order-id='{OIDC}']", state="attached", timeout=20000)
            pg.evaluate(f"selectOrder({OIDC}, document.querySelector('.ord-item[data-order-id=\"{OIDC}\"]'))")
            pg.wait_for_function("document.querySelector('#od-items-container .kmp-sarlavha') !== null", timeout=20000)
            _sh = pg.locator("#od-items-container .kmp-sarlavha").all_inner_texts()
            _ch = pg.evaluate("Array.from(document.querySelector('#od-items-container').children).map(e => [e.className.split(' ')[0], "
                              "Array.from(e.children).map(c => c.className.split(' ')[0]).filter(c => c.indexOf('kmp') === 0 || c === 'prod-row')])")
            check("U1 buyurtma oynasi: «🧩 X-1 <b>rom</b> & «komplekt» — 1 komplekt» (MATN, teg yo'q) bloki — ichida 2 detal; guruhsiz qator — "
                  "blokdan TASHQARIDA",
                  _sh == ["🧩 X-1 <b>rom</b> & «komplekt» — 1 komplekt"] and pg.locator("#od-items-container .kmp-sarlavha b").count() == 0
                  and _ch == [["kmp-blok", ["kmp-sarlavha", "prod-row", "prod-row"]], ["prod-row", []]], (_sh, _ch, JSX))
            pg.evaluate(f"selectOrder({OID}, document.querySelector('.ord-item[data-order-id=\"{OID}\"]'))")
            pg.wait_for_function("document.querySelectorAll('#od-items-container .kmp-sarlavha').length === 2", timeout=20000)
            _sh = pg.locator("#od-items-container .kmp-sarlavha").all_inner_texts()
            EKRAN = os.environ.get("T239_EKRAN")          # ixtiyoriy: skrinshotlar papkasi (ko'zda tekshirish uchun)
            if EKRAN:
                pg.screenshot(path=os.path.join(EKRAN, "u2_oyna.png"), full_page=True)
            check("U2 sayt buyurtmasi oynasida: «🧩 R-18 … — 3 komplekt» va «✂️ R-18 …, o'z o'lchami, qoplamali»",
                  _sh == ["🧩 " + ROM[2] + " — 3 komplekt", "✂️ " + OZB[2]], _sh)
            pg.evaluate("editSelected('edit')")
            pg.wait_for_function("document.querySelectorAll('.detal .kmp-belgi').length >= 9", timeout=20000)
            _bl = pg.locator(".detal .kmp-belgi").all_inner_texts()
            _ob = pg.locator(".detal .kmp-olib").count()
            if EKRAN:
                pg.screenshot(path=os.path.join(EKRAN, "u3_tahrir.png"), full_page=True)
            check("U3 tahrir formasi: 6 rom qatorida «🧩 … — 3 komplekt» + «✕ butun komplekt», 3 o'z o'lchami qatorida «✂️ …» (tugmasiz)",
                  sorted(_bl) == sorted(["🧩 " + ROM[2] + " — 3 komplekt"] * 6 + ["✂️ " + OZB[2]] * 3) and _ob == 6, (_bl, _ob))
            _tn = pg.evaluate("collectItems().map(x => [x.kmp_guruh, x.kmp_turi, x.kmp_nomi, x.kmp_soni])")
            check("U4 forma tanasi (collectItems): har qator o'z belgisi, guruhsiz — null", sorted(map(json.dumps, _tn))
                  == sorted(map(json.dumps, [list(kmp(x)) for x in buyurtma(OID)["items"]])), _tn)
            pg.evaluate("window.showConfirmModal = async () => true")
            pg.locator(".detal .kmp-olib").first.click()
            pg.wait_for_timeout(300)
            _qol = pg.evaluate("Array.from(document.querySelectorAll('.detal')).map(r => r.dataset.kmpGuruh || '')")
            check("U5 «✕ butun komplekt» — rom komplektining 6 qatori formadan olindi, qolganlari joyida (saqlanmadi)",
                  _qol.count("1") == 0 and _qol.count("3") == 3 and len(_qol) == 5, _qol)
            pg.evaluate("hideNewForm && hideNewForm()")
            pg.evaluate(f"selectOrder({OID}, document.querySelector('.ord-item[data-order-id=\"{OID}\"]'))")
            pg.wait_for_timeout(500)
            pg.evaluate(f"(async () => {{ await loadDeliveries({OID}); openDeliveryModal(); }})()")
            pg.wait_for_selector("#dlvModal .kmp-sarlavha", timeout=20000)
            _dh = pg.locator("#dlvForm .kmp-sarlavha").all_inner_texts()
            if EKRAN:
                pg.screenshot(path=os.path.join(EKRAN, "u6_yetkazish.png"))
            check("U6 yetkazish oynasi: komplekt va o'z o'lchami sarlavhalari", _dh == ["🧩 " + ROM[2] + " — 3 komplekt", "✂️ " + OZB[2]], _dh)
            pg.evaluate(f"(async () => {{ const o = await (await fetch('/api/orders/{OID}')).json(); openDuplicatePickModal(o); }})()")
            pg.wait_for_selector("#dupPickList .kmp-sarlavha", timeout=20000)
            _dp = pg.locator("#dupPickList .kmp-sarlavha").all_inner_texts()
            pg.evaluate("closeDuplicatePickModal()")
            pg.evaluate(f"(async () => {{ const o = await (await fetch('/api/orders/{OID}')).json(); editSelected('duplicate', o, [0, 6, 7, 8]); }})()")
            pg.wait_for_function("document.querySelectorAll('.detal').length === 4", timeout=20000)
            pg.wait_for_timeout(300)
            _db = pg.locator(".detal .kmp-belgi").all_inner_texts()
            check("U10 (review239 L5) nusxa: tanlovda komplekt sarlavhalari; qisman nusxa (rom komplektidan 1 detal + o'z o'lchami to'liq) — rom "
                  "belgisi TUSHADI, o'z o'lchami — qoladi",
                  _dp == ["🧩 " + ROM[2] + " — 3 komplekt", "✂️ " + OZB[2]] and sorted(_db) == ["✂️ " + OZB[2]] * 3, (_dp, _db))
            pg.evaluate("hideNewForm && hideNewForm()")
            pg.goto(BASE + "/returns")
            pg.wait_for_load_state("networkidle")
            pg.evaluate(f"(() => {{ const s = document.getElementById('f-order'); s.innerHTML = '<option value=\"{OIDC}\">x</option>'; "
                        f"s.value = '{OIDC}'; onOrderChange(); }})()")
            pg.wait_for_function("document.querySelector('#f-item optgroup') !== null", timeout=20000)
            _og = pg.evaluate("Array.from(document.querySelectorAll('#f-item optgroup')).map(g => [g.label, g.children.length])")
            check("U7 qaytarish: detal tanlovida «🧩 X-1 <b>rom</b> & «komplekt» — 1 komplekt» guruhi (2 detal), guruhsiz — tashqarida",
                  _og == [["🧩 X-1 <b>rom</b> & «komplekt» — 1 komplekt", 2]]
                  and pg.evaluate("document.querySelectorAll('#f-item > option').length") == 2, _og)
            pg.set_viewport_size({"width": 375, "height": 800})
            pg.goto(BASE + "/orders")
            pg.wait_for_load_state("networkidle")
            pg.wait_for_selector(f".ord-item[data-order-id='{OID}']", state="attached", timeout=20000)
            pg.evaluate(f"selectOrder({OID}, document.querySelector('.ord-item[data-order-id=\"{OID}\"]'))")
            pg.wait_for_function("document.querySelector('#od-items-container .kmp-sarlavha') !== null", timeout=20000)
            pg.evaluate("editSelected('edit')")
            pg.wait_for_function("document.querySelectorAll('.detal .kmp-belgi').length >= 9", timeout=20000)
            _w = pg.evaluate("[document.documentElement.scrollWidth, Math.max(...Array.from(document.querySelectorAll('.detal .kmp-olib'))"
                             ".map(e => e.getBoundingClientRect().right))]")
            if EKRAN:
                pg.screenshot(path=os.path.join(EKRAN, "u8_375.png"), full_page=True)
            check("U8 375 px: tahrir formasi sig'adi (sahifa gorizontal surilmaydi, «✕ butun komplekt» ekranda)", _w[0] <= 375 and _w[1] <= 375, _w)
            check("U9 sahifalarda JS xatosi yo'q", not JSX, JSX)
            br.close()
    except Exception as e:                  # noqa: BLE001
        check("U0 brauzer sinovi oxirigacha yurdi", False, f"{type(e).__name__}: {e}")
    finally:
        _srv.should_exit = True

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:\n  " + "\n  ".join(FAILED))
sys.exit(1 if FAIL else 0)
