#!/usr/bin/env python3
"""
test_karniz255.py — kech187 (zip 255: karniz formula narxi, «Boshqa o'lcham», yaxlitlashsiz narx, «kelishuv asosida» yetkazish,
zaxira tiklashdagi aylana bog'lam, o'tish indeksi).

NIMA UCHUN KERAK
  Egasi QARORLARI 04.11 (rasm bilan): karniz 1 m qoplamasiz = balandlik × blok chuqurligi × 1 m³ narxi ÷ 2 (ikki karniz bitta blokdan),
  qoplamali = × koeffitsient; tayyor o'lchamlar ham shu formula bilan; saytda «Boshqa o'lcham» 15 … 40 sm; YAXLITLASH YO'Q («aniq chiqqan
  summa qolsin» — 30.10 dagi «1 000 gacha» qarori o'rnini bosadi); viloyatlarga yetkazib berish — «kelishuv asosida». kech187 o'lchovi:
  band qilingan tayyor mahsulot bor zaxira tiklanmasdi (FK aylana), o'tish yo'lida zip 240 indeksi yaratilmasdi.
  Asl kodda (zip 254) formula / maxsus qator / 1 m³ narxi YO'Q, qoplamali narx 1 000 ga yaxlitlanadi — test yiqiladi (qulamaydi).
BO'LIMLAR
  S — tayyorgarlik. F — formula (1 m³ narxi, model formulasi, qatorlar qayta hisobi, egasining misoli). R — rad (qo'lda narx, Excel,
  qolip, 1 m³ siz, balandliksiz qator). M — «Boshqa o'lcham» narxi (do'kon API). B — savatda maxsus qator (ERP buyurtmasi). Y — yaxlitlash
  yo'q, yetkazish matni. T — zaxira tiklash (band tayyor mahsulot), indeks ro'yxati. Z — ikkinchi korxona, jurnal.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
"""
import os
import io
import sys
import json
import tempfile
import contextlib
from decimal import Decimal

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"karniz255_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t255_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't255.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "DOKON_BOT_TOKEN", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
    import database                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User                  # noqa: E402
from production_models import Company              # noqa: E402
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


def bazadan(fn):
    d = SessionLocal()
    try:
        return fn(d)
    except Exception:                      # noqa: BLE001
        d.rollback()
        return None
    finally:
        d.close()


main._send_telegram = lambda *a, **k: True

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Tayyorgarlik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
s.add(Company(id=2, name="T255 Begona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t255_admin", PAROL, UserRole.ADMIN, "T255 Admin", company_id=1)
    auth.create_user(s, "t255_plat", PAROL, UserRole.ADMIN, "T255 Platforma", company_id=1)
    auth.create_user(s, "t255_b", PAROL, UserRole.ADMIN, "T255 B", company_id=2)
s.query(User).filter(User.username == "t255_plat").first().is_platform_admin = True
s.commit()
s.close()


def kirish(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA, CP, CB = kirish("t255_admin"), kirish("t255_plat"), kirish("t255_b")
NC = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
CP.post("/api/platform/companies/2/dokon", data={"yoqilgan": "1"})
KALIT = js(CA.post(API + "/api-kalit", json={})).get("kalit") or ""
K0 = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K0.get("bolimlar") or [])}
check("S1 Karnizlar bo'limi va do'kon kaliti bor", BOL.get("Karnizlar") and len(KALIT) > 20, BOL)
MK = js(CA.post(API + "/modellar", json={"bolim_id": BOL.get("Karnizlar"), "kod": "K-20", "nom": "Klassik"})).get("id")
MO = js(CA.post(API + "/modellar", json={"bolim_id": BOL.get("Karnizlar"), "kod": "K-30", "nom": "Oddiy"})).get("id")
DK = {}
for e, q in ((15, 5.07), (20, 6.76), (25, 8.45)):
    r = CA.post(API + "/detallar", json={"model_id": MK, "turi": "asosiy", "olcham": f"{e} sm", "narx": 50000, "eni_sm": e,
                                         "qalinligi_sm": q})
    DK[e] = js(r).get("id")
DO = js(CA.post(API + "/detallar", json={"model_id": MO, "turi": "asosiy", "olcham": "12 sm", "narx": 45123, "eni_sm": 12,
                                         "qalinligi_sm": 8})).get("id")
check("S2 modellar va qatorlar yaratildi (formula hali yo'q — narx qo'lda)", MK and MO and all(DK.values()) and DO, (MK, MO, DK, DO))


def katalog():
    return js(CA.get(API))


def detal(did):
    return next((d for d in (katalog().get("detallar") or []) if d.get("id") == did), {})


def model(mid):
    return next((m for m in (katalog().get("modellar") or []) if m.get("id") == mid), {})


def chek_tozala():
    for _n in ("_DOKON_API_CHEKLOV", "_DOKON_MIJOZ_CHEKLOV", "_DOKON_BUYURTMA_CHEKLOV"):
        _ch = getattr(crud, _n, None)
        if _ch is not None:
            _ch.tozala()


def dokon_get(yol, kalit=None):
    chek_tozala()
    return NC.get(yol, headers={"X-Dokon-Kalit": KALIT if kalit is None else kalit})


_kn = [0]


def buyurtma(qatorlar, viloyat="andijon"):
    chek_tozala()
    _kn[0] += 1
    h = {"X-Dokon-Kalit": KALIT, "X-Amal-Kaliti": f"savat-{_kn[0]:06d}-t255", "Content-Type": "application/json"}
    tana = {"mijoz": "Ali Valiyev", "telefon": "+998901234567", "viloyat": viloyat, "qatorlar": qatorlar}
    return NC.post("/api/dokon/v1/buyurtmalar", content=json.dumps(tana).encode("utf-8"), headers=h)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. Formula — 1 m³ narxi, model formulasi, qatorlar (egasining misoli)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = CA.put(API + f"/modellar/{MK}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
check("F1 1 m³ narxisiz formula — 400, «Do'kon sozlamalari»", r.status_code == 400 and "1 m³" in js(r).get("detail", ""), (r.status_code, r.text[:200]))
check("F1b rad etilgan formula yozilmadi", model(MK).get("formula") is None, model(MK))
r = CA.put(API + "/kub-narx", json={"kub_narx": 1200000})
check("F2 1 m³ narxi saqlandi (formulali model hali yo'q — 0 qayta hisob)",
      r.status_code == 200 and js(r).get("kub_narx") == 1200000 and js(r).get("qayta_hisoblandi") == 0, (r.status_code, r.text[:200]))
check("F2b katalogda kub_narx, oraliq 15 … 40", katalog().get("kub_narx") == 1200000 and katalog().get("maxsus_min") == 15
      and katalog().get("maxsus_max") == 40, katalog().get("kub_narx"))
r = CA.put(API + f"/modellar/{MK}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
check("F3 formula yoqildi", r.status_code == 200, (r.status_code, r.text[:200]))
F = model(MK).get("formula") or {}
check("F3b model formulasi qaytadi", F.get("asos_sm") == 20 and F.get("blok_sm") == 9.97 and F.get("bolak") == 2, F)
check("F4 egasining misoli: 20 sm → 11 964 (0,2 × 0,0997 × 1 200 000 ÷ 2)", detal(DK[20]).get("narx") == 11964, detal(DK[20]))
check("F5 15 sm → 6 730, 25 sm → 18 694 (hajm balandlik kvadrati bilan)",
      detal(DK[15]).get("narx") == 6730 and detal(DK[25]).get("narx") == 18694, (detal(DK[15]).get("narx"), detal(DK[25]).get("narx")))
check("F6 qoplamali — × 2, YAXLITLASHSIZ: 23 928 (asl kodda 24 000)", detal(DK[20]).get("narx_qoplamali_avto") == 23928,
      detal(DK[20]))
check("F7 oddiy (formulasiz) model narxi o'zgarmadi", detal(DO).get("narx") == 45123, detal(DO))
r = CA.put(API + "/kub-narx", json={"kub_narx": 1300000})
check("F8 1 m³ narxi o'zgardi → formulali model qatorlari qayta (3 ta)", r.status_code == 200 and js(r).get("qayta_hisoblandi") == 3,
      (r.status_code, r.text[:200]))
check("F8b 20 sm → 12 961 (0,2 × 0,0997 × 1 300 000 ÷ 2 = 12 961)", detal(DK[20]).get("narx") == 12961, detal(DK[20]))
r = CA.put(API + "/kub-narx", json={"kub_narx": 1200000})
check("F8c qaytarildi — 11 964", r.status_code == 200 and detal(DK[20]).get("narx") == 11964, detal(DK[20]))
r = CA.put(API + f"/modellar/{MK}", json={"formula": {"asos_sm": 20, "blok_sm": 10, "bolak": 2}})
check("F9 formula o'zgardi (blok 10) → 20 sm 12 000", r.status_code == 200 and detal(DK[20]).get("narx") == 12000, detal(DK[20]))
CA.put(API + f"/modellar/{MK}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
r = CA.post(API + "/detallar", json={"model_id": MK, "turi": "asosiy", "olcham": "30 sm", "eni_sm": 30, "qalinligi_sm": 10.14})
D30 = js(r).get("id")
check("F10 formulali modelga yangi qator — narx serverdan (30 sm → 26 919)", r.status_code == 200 and detal(D30).get("narx") == 26919,
      (r.status_code, r.text[:200], detal(D30)))
r = CA.put(API + f"/detallar/{D30}", json={"eni_sm": 22})
check("F11 balandlik o'zgardi → narx qayta (22 sm → 14 476)", r.status_code == 200 and detal(D30).get("narx") == 14476, detal(D30))
CA.delete(API + f"/detallar/{D30}")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Rad etiladigan holatlar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = CA.put(API + f"/detallar/{DK[20]}", json={"narx": 10000})
check("R1 formulali modelda qo'lda narx — 400, narx o'zgarmadi", r.status_code == 400 and detal(DK[20]).get("narx") == 11964,
      (r.status_code, r.text[:200]))
r = CA.put(API + f"/detallar/{DK[20]}", json={"narx_qoplamali": 30000})
check("R2 formulali modelda qo'lda qoplamali narx — 400", r.status_code == 400 and detal(DK[20]).get("narx_qoplamali") is None,
      (r.status_code, r.text[:200]))
r = CA.put(API + f"/detallar/{DK[20]}", json={"ulgurji_narx": 20000})
check("R3 ulgurji narx — qo'lda (formulaga kirmaydi)", r.status_code == 200 and detal(DK[20]).get("ulgurji_narx") == 20000,
      (r.status_code, r.text[:200]))
r = CA.post(API + "/detallar", json={"model_id": MK, "turi": "asosiy", "olcham": "35 sm", "narx": 50000, "eni_sm": 35})
check("R4 formulali modelga narx bilan qator — 400", r.status_code == 400, (r.status_code, r.text[:200]))
r = CA.post(API + "/detallar", json={"model_id": MK, "turi": "asosiy", "olcham": "Katta"})
check("R5 formulali modelga balandliksiz qator — 400", r.status_code == 400 and "balandlik" in js(r).get("detail", ""),
      (r.status_code, r.text[:200]))
r = CA.put(API + f"/detallar/{DK[20]}", json={"eni_sm": None})
check("R6 balandlikni o'chirish — 400", r.status_code == 400 and detal(DK[20]).get("eni_sm") == 20, (r.status_code, r.text[:200]))
r = CA.put(API + "/kub-narx", json={"kub_narx": None})
check("R7 formulali model bor — 1 m³ narxini o'chirish 400", r.status_code == 400 and "K-20" in js(r).get("detail", ""),
      (r.status_code, r.text[:200]))
for n, v in (("0", 0), ("manfiy", -5), ("kasr", 1200000.5), ("matn", "1200000"), ("bool", True), ("katta", 10 ** 13)):
    r = CA.put(API + "/kub-narx", json={"kub_narx": v})
    check(f"R8 1 m³ narxi noto'g'ri ({n}) — 400", r.status_code == 400, (r.status_code, r.text[:200]))
check("R8b 1 m³ narxi o'zgarmadi", katalog().get("kub_narx") == 1200000, katalog().get("kub_narx"))
r = CA.put(API + "/kub-narx", json={"kub_narx": 1, "boshqa": 2})
check("R9 ortiqcha kalit — 400", r.status_code == 400, r.status_code)
for n, f in (("asos 0", {"asos_sm": 0, "blok_sm": 9.97, "bolak": 2}), ("blok 3 xona", {"asos_sm": 20, "blok_sm": 9.975, "bolak": 2}),
             ("bo'lak 0", {"asos_sm": 20, "blok_sm": 9.97, "bolak": 0}), ("bo'lak kasr", {"asos_sm": 20, "blok_sm": 9.97, "bolak": 1.5}),
             ("kalit yo'q", {"asos_sm": 20, "blok_sm": 9.97}), ("ortiqcha", {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2, "x": 1}),
             ("matn", "20/9.97/2")):
    r = CA.put(API + f"/modellar/{MK}", json={"formula": f})
    check(f"R10 formula noto'g'ri ({n}) — 400", r.status_code == 400, (r.status_code, r.text[:200]))
check("R10b formula o'zgarmadi", (model(MK).get("formula") or {}).get("blok_sm") == 9.97, model(MK))
MKOM = js(CA.post(API + "/modellar", json={"bolim_id": BOL.get("Rom va eshik dekorlari"), "kod": "R-55", "nom": "Rom"})).get("id")
r = CA.put(API + f"/modellar/{MKOM}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
check("R11 komplekt modelda formula — 400 (faqat metrli)", MKOM and r.status_code == 400, (MKOM, r.status_code, r.text[:200]))
r = CA.put(API + f"/modellar/{MK}", json={"qolip": "dona"})
check("R12 formulali modelni donaga o'tkazish — 400", r.status_code == 400 and model(MK).get("qolip") == "juft_metr",
      (r.status_code, r.text[:200]))
# Excel: formulali qatorning narxini o'zgartirish — xato (saqlanmaydi)
try:
    import openpyxl
    _b = bazadan(lambda d: crud.dokon_excel_yarat(d, 1))
    wb = openpyxl.load_workbook(io.BytesIO(_b))
    ws = wb.worksheets[0]
    _sar = _raq = _narx = None
    for row in ws.iter_rows():
        for c in row:
            if c.value == "Narx (qoplamasiz), so'm":
                _sar, _narx = c.row, c.column
            if c.value == "Raqam" and _raq is None:
                _raq = c.column
    _qator = next(r_ for r_ in range(_sar + 1, ws.max_row + 1) if ws.cell(r_, _raq).value == DK[20])
    ws.cell(_qator, _narx).value = 10000
    _o = io.BytesIO()
    wb.save(_o)
    _kor = bazadan(lambda d: crud.dokon_excel_korish(d, 1, _o.getvalue()))
    check("R13 Excel'da formulali narx o'zgartirilsa — xato, o'zgarish yo'q",
          _kor and any("formula" in x for x in _kor["xatolar"]) and not _kor["ozgarishlar"], _kor and _kor["xatolar"][:3])
except Exception as e:                     # noqa: BLE001
    check("R13 Excel'da formulali narx o'zgartirilsa — xato, o'zgarish yo'q", False, f"{type(e).__name__}: {e}")
r = CA.post(API + "/excel/saqla", json={"ozgarishlar": [{"id": DK[20], "kimlik": "K-20 · Asosiy · 20 sm", "eski": {"narx": 11964},
                                                          "yangi": {"narx": 10000}}]})
check("R14 Excel saqlash yo'li ham rad (to'g'ridan-to'g'ri so'rov) — narx o'zgarmadi", r.status_code in (400, 404, 409)
      and detal(DK[20]).get("narx") == 11964, (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. «Boshqa o'lcham» narxi — do'kon API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
KAT = js(dokon_get("/api/dokon/v1/katalog"))
_mk = next((m for m in (KAT.get("modellar") or []) if m.get("id") == MK), {})
_mo = next((m for m in (KAT.get("modellar") or []) if m.get("id") == MO), {})
check("M1 do'kon katalogida formulali modelda «maxsus» 15 … 40, oddiyda yo'q",
      (_mk.get("maxsus") or {}).get("min") == 15 and (_mk.get("maxsus") or {}).get("max") == 40 and _mo.get("maxsus") is None, (_mk.get("maxsus"), _mo.get("maxsus")))
check("M1b do'kon katalogida formula ichki sonlari (blok, bo'lak, 1 m³) yo'q", "formula" not in _mk and "kub_narx" not in KAT, list(_mk))
r = dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MK}&balandlik=18")
J = js(r)
check("M2 18 sm → 9 691 / qoplamali 19 382 (0,18 × 0,08973 × 1 200 000 ÷ 2)",
      r.status_code == 200 and J.get("narx") == 9691 and J.get("narx_qoplamali") == 19382 and J.get("olcham") == "18 sm (maxsus o'lcham)",
      (r.status_code, r.text[:300]))
check("M2b chuqurlik — 20 sm qatoridan mutanosib (6,76 × 18 / 20 = 6,08), birlik metr",
      J.get("qalinligi_sm") == 6.08 and J.get("eni_sm") == 18 and J.get("birlik") == "metr", J)
r = dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MK}&balandlik=18,5")
check("M3 18,5 sm (vergul) — qabul, «18,5 sm»", r.status_code == 200 and js(r).get("olcham") == "18,5 sm (maxsus o'lcham)"
      and js(r).get("narx") == 10237 and js(r).get("narx_qoplamali") == 20474, (r.status_code, r.text[:200]))
for n, h in (("14,9", "14.9"), ("40,1", "40.1"), ("2 xona", "18.55"), ("matn", "abc"), ("bo'sh", ""), ("inf", "inf"), ("nan", "nan")):
    r = dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MK}&balandlik={h}")
    check(f"M4 balandlik noto'g'ri ({n}) — 400", r.status_code == 400, (r.status_code, r.text[:200]))
for n, h in (("15", "15"), ("40", "40")):
    r = dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MK}&balandlik={h}")
    check(f"M5 chegara {n} sm — qabul", r.status_code == 200, (r.status_code, r.text[:200]))
check("M5b 15 sm — katalogdagi 15 sm narxi bilan AYNAN (6 730)", js(dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MK}&balandlik=15")).get("narx")
      == detal(DK[15]).get("narx") == 6730)
r = dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MO}&balandlik=18")
check("M6 formulasiz model — 404", r.status_code == 404, (r.status_code, r.text[:200]))
r = dokon_get("/api/dokon/v1/maxsus-narx?model_id=999999&balandlik=18")
check("M7 yo'q model — 404", r.status_code == 404, (r.status_code, r.text[:200]))
r = dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MK}&balandlik=18", kalit="noto'g'ri-kalit-1234567890")
check("M8 kalitsiz / noto'g'ri kalit — 401", r.status_code == 401, (r.status_code, r.text[:200]))
CA.put(API + f"/modellar/{MK}", json={"yoqilgan": False})
r = dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MK}&balandlik=18")
check("M9 o'chirilgan model — 404", r.status_code == 404, (r.status_code, r.text[:200]))
CA.put(API + f"/modellar/{MK}", json={"yoqilgan": True})
check("M10 yo'l DOKON_API_YOLLAR da", "/api/dokon/v1/maxsus-narx" in crud.DOKON_API_YOLLAR)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Savatda maxsus qator → sayt buyurtmasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
CA.put(API + f"/modellar/{MK}/chegirma", json={"foiz": 10})
r = buyurtma([{"maxsus": {"model_id": MK, "balandlik_sm": 18}, "qoplamali": True, "miqdor": 4}])
J = js(r)
check("B1 maxsus qator qabul (18 sm, qoplamali, 4 m)", r.status_code in (200, 201) and J.get("raqam"), (r.status_code, r.text[:300]))
Q = bazadan(lambda d: [(q.sbq_tur, q.sbq_olcham, q.eni_sm, q.qalinligi_sm, float(q.narx), float(q.summa), q.chegirma_foiz, q.qoplamali,
                        q.miqdor, q.detal_id, float(q.hajm_narxi)) for q in d.query(models.DokonBuyurtmaQator).order_by(models.DokonBuyurtmaQator.id).all()]) or []
check("B2 qator: «18 sm (maxsus o'lcham)», eni 18, chuqurlik 6,08, narx 19 382, summa 77 528, chegirma YO'Q",
      Q and Q[-1][:9] == ("maxsus", "18 sm (maxsus o'lcham)", 18.0, 6.08, 19382.0, 77528.0, None, True, 4.0), Q[-1:] if Q else Q)
check("B2b detal_id bo'sh, hajm narxi — qoplamasiz 9 691", Q and Q[-1][9] is None and Q[-1][10] == 9691.0, Q[-1:] if Q else Q)
_sb = bazadan(lambda d: d.query(models.DokonBuyurtma).order_by(models.DokonBuyurtma.id.desc()).first())
check("B3 buyurtma jami 77 528", _sb is not None and float(_sb.sb_jami) == 77528.0, _sb and _sb.sb_jami)
r = buyurtma([{"maxsus": {"model_id": MK, "balandlik_sm": 18}, "qoplamali": False, "miqdor": 3}])
check("B4 juft metr qoidasi — 3 m rad (400)", r.status_code == 400, (r.status_code, r.text[:200]))
for n, q in (("41 sm", {"maxsus": {"model_id": MK, "balandlik_sm": 41}, "qoplamali": False, "miqdor": 2}),
             ("formulasiz model", {"maxsus": {"model_id": MO, "balandlik_sm": 18}, "qoplamali": False, "miqdor": 2}),
             ("ortiqcha kalit", {"maxsus": {"model_id": MK, "balandlik_sm": 18, "narx": 1}, "qoplamali": False, "miqdor": 2}),
             ("narx yuborilgan", {"maxsus": {"model_id": MK, "balandlik_sm": 18}, "qoplamali": False, "miqdor": 2, "narx": 1}),
             ("maxsus ro'yxat", {"maxsus": [MK, 18], "qoplamali": False, "miqdor": 2})):
    r = buyurtma([q])
    check(f"B5 maxsus qator noto'g'ri ({n}) — 400", r.status_code == 400, (r.status_code, r.text[:200]))
r = buyurtma([{"detal_id": DK[20], "qoplamali": False, "miqdor": 2}])
_q2 = bazadan(lambda d: d.query(models.DokonBuyurtmaQator).order_by(models.DokonBuyurtmaQator.id.desc()).first())
check("B6 katalog o'lchami (20 sm) — chegirma amalda (10 %): 11 964 → 10 768 (formula modelida ham chegirma ishlaydi)",
      r.status_code in (200, 201) and _q2 is not None and float(_q2.asl_narx) == 11964.0 and _q2.chegirma_foiz is not None,
      (r.status_code, _q2 and (_q2.narx, _q2.asl_narx, _q2.chegirma_foiz)))
CA.delete(API + f"/modellar/{MK}/chegirma")
_tanasi = bazadan(lambda d: crud.sayt_buyurtma_tanasi(_sb, crud._sayt_qatorlari(d, 1, _sb.id), 1, __import__("datetime").date(2026, 11, 5),
                                                      recipe_id=1))
check("B7 ERP buyurtma tanasi — maxsus qator alohida detal (komplekt belgisi yo'q), nomida «18 sm»",
      _tanasi and len(_tanasi["items"]) == 1 and "18 sm" in (_tanasi["items"][0].get("name") or "")
      and not _tanasi["items"][0].get("kmp_turi"), _tanasi and _tanasi["items"])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Y. Yaxlitlash yo'q, yetkazish — «kelishuv asosida»")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("Y1 oddiy model: 45 123 × 2 = 90 246 (asl kodda 90 000)", detal(DO).get("narx_qoplamali_avto") == 90246, detal(DO))
_kat_o = next((m for m in (js(dokon_get("/api/dokon/v1/katalog")).get("modellar") or []) if m.get("id") == MO), {})
check("Y2 do'kon katalogida ham 90 246", (_kat_o.get("detallar") or [{}])[0].get("narx_qoplamali") == 90246, _kat_o.get("detallar"))
check("Y3 koeffitsient 1,5 × 45 123 = 67 684,5 → 67 685 (butun so'm)", crud.dokon_avto_qoplamali(45123, Decimal("1.5")) == Decimal("67685"))
check("Y4 kichik narx «bepul» bo'lmaydi: 0,2 × 1 → 0,20", crud.dokon_avto_qoplamali(Decimal("0.2"), 1) == Decimal("0.20"))
check("Y5 viloyat: «Yetkazib berish — kelishuv asosida», Andijon — bepul",
      all(v["yetkazish_matni"] == "Yetkazib berish — kelishuv asosida" for v in crud.sayt_viloyatlar() if not v["yetkazish_bepul"])
      and any(v["yetkazish_bepul"] for v in crud.sayt_viloyatlar()))
r = buyurtma([{"detal_id": DO, "qoplamali": True, "miqdor": 2}], viloyat="fargona")
check("Y6 Farg'ona buyurtmasi javobida «kelishuv asosida»", r.status_code in (200, 201)
      and js(r).get("yetkazish_matni") == "Yetkazib berish — kelishuv asosida", (r.status_code, r.text[:300]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Zaxira tiklash — band tayyor mahsulot (aylana bog'lam); indeks")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def _band_yarat(d):
    p = models.Project(company_id=1, client_name="T255 Mijoz", project_name="T255 Loyiha")
    d.add(p)
    d.flush()
    o = models.Order(company_id=1, project_id=p.id, order_type=models.OrderType.PRODUCT, order_number="T255-1")
    d.add(o)
    d.flush()
    oi = models.OrderItem(order_id=o.id, name="T255 karniz", quantity=4)
    d.add(oi)
    d.flush()
    fp = models.FinishedProduct(company_id=1, name="T255 karniz TM", quantity=10, reserved_for_order_item_id=oi.id, reserved_quantity=4)
    d.add(fp)
    d.flush()
    oi.finished_product_id = fp.id
    d.commit()
    return fp.id, oi.id


_fp, _oi = bazadan(_band_yarat) or (None, None)
check("T1 band tayyor mahsulot yaratildi (TM ↔ detal — ikki tomonlama)", _fp and _oi, (_fp, _oi))
_zx = bazadan(lambda d: crud.export_full_backup(d, company_id=1))
_nat = bazadan(lambda d: crud.import_full_backup(d, json.loads(json.dumps(_zx, default=str)), 1, replace=True))
check("T2 shu zaxira tiklanadi (asl kodda FK xatosi — rad)", _nat and _nat.get("success"), _nat and _nat.get("message"))
check("T3 tiklangach band va bog'lam AYNAN", bazadan(lambda d: (d.get(models.FinishedProduct, _fp).reserved_for_order_item_id,
                                                                  d.get(models.OrderItem, _oi).finished_product_id)) == (_oi, _fp))
check("T4 tiklangach 1 m³ narxi va model formulasi saqlandi", katalog().get("kub_narx") == 1200000
      and (model(MK).get("formula") or {}).get("blok_sm") == 9.97 and detal(DK[20]).get("narx") == 11964, (katalog().get("kub_narx"), model(MK)))
import inspect as _ins                     # noqa: E402
check("T5 o'tish indekslari ro'yxatida return_items.kqt_kalit", '("return_items", "kqt_kalit")' in _ins.getsource(database.add_missing_indexes))
if PG_URL:
    _ix = bazadan(lambda d: d.execute(__import__("sqlalchemy").text(
        "select count(*) from pg_indexes where indexname='ix_return_items_kqt_kalit'")).scalar())
    check("T6 [PG] ix_return_items_kqt_kalit bor", _ix == 1, _ix)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("V. Mustaqil tekshiruv (review255) tuzatishlari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from types import SimpleNamespace as _NS                                                         # noqa: E402
from fractions import Fraction as _Fr                                                            # noqa: E402


def _aniq(h, asos, blok, kub, bolak):
    x = _Fr(Decimal(str(h))) ** 2 * _Fr(Decimal(str(blok))) * _Fr(Decimal(str(kub))) / (_Fr(Decimal(str(asos))) * 10000 * bolak)
    return Decimal((x + _Fr(1, 2)).__floor__())


_l1 = [(15, 14, 10.0, 2730000, 2), (20, 12, 7.55, 2298000, 2), (20, 20, 9.97, 1200000, 2), (18.5, 20, 9.97, 1200000, 2),
       (33.3, 7, 3.33, 999999, 3), (40, 17, 13.13, 1234567, 7)]
_l1x = [(t, crud.dokon_formula_narx(_NS(formula_asos_sm=t[1], formula_blok_sm=t[2], formula_bolak=t[4]), t[0], t[3]), _aniq(*t)) for t in _l1]
check("V1 (L1) formula — aniq kasrning HALF_UP i: 14 / 10 / 15 sm / 2 730 000 → 21 938 (ilgari 21 937), egasining misoli 11 964",
      all(a == b for _t, a, b in _l1x) and _l1x[0][1] == 21938 and _l1x[2][1] == 11964, _l1x)
# M2: kapitel / baza (donada) — formulaga kirmaydi
MP = js(CA.post(API + "/modellar", json={"bolim_id": BOL.get("Karnizlar"), "kod": "P-1", "nom": "Pilyastr", "kapitel_baza_bor": True})).get("id")
DPA = js(CA.post(API + "/detallar", json={"model_id": MP, "turi": "asosiy", "olcham": "20 sm", "narx": 15000, "eni_sm": 20,
                                          "qalinligi_sm": 6.76})).get("id")
DPK = js(CA.post(API + "/detallar", json={"model_id": MP, "turi": "kapitel", "olcham": "30 sm", "narx": 85000, "eni_sm": 30})).get("id")
DPKB = js(CA.post(API + "/detallar", json={"model_id": MP, "turi": "kapitel", "olcham": "Katta", "narx": 95000})).get("id")
r = CA.put(API + f"/modellar/{MP}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
check("V2 (M2) kapitelli metr modeliga formula — qabul (enisiz kapitel qatori to'sqinlik qilmaydi)", r.status_code == 200 and MP and DPK and DPKB,
      (r.status_code, r.text[:200]))
check("V2b asosiy qator — formula (11 964), kapitel qatorlari — o'z narxi (85 000 / 95 000)",
      detal(DPA).get("narx") == 11964 and detal(DPK).get("narx") == 85000 and detal(DPKB).get("narx") == 95000,
      (detal(DPA).get("narx"), detal(DPK).get("narx"), detal(DPKB).get("narx")))
r = CA.put(API + f"/detallar/{DPK}", json={"narx": 87000})
check("V2c kapitel narxini qo'lda o'zgartirish — mumkin", r.status_code == 200 and detal(DPK).get("narx") == 87000, (r.status_code, r.text[:200]))
r = CA.post(API + "/detallar", json={"model_id": MP, "turi": "baza", "olcham": "30 sm", "narx": 70000, "eni_sm": 30})
DPB = js(r).get("id")
check("V2d baza qatori o'z narxi bilan — qo'shiladi", r.status_code == 200 and detal(DPB).get("narx") == 70000, (r.status_code, r.text[:200]))
r = CA.put(API + f"/detallar/{DPA}", json={"narx": 1})
check("V2e asosiy qatorda qo'lda narx — baribir rad", r.status_code == 400 and detal(DPA).get("narx") == 11964, (r.status_code, r.text[:200]))
r = CA.put(API + "/kub-narx", json={"kub_narx": 1300000})
check("V2f 1 m³ o'zgardi — faqat asosiy qatorlar qayta (K-20: 3, P-1: 1), kapitel / baza o'zgarmadi",
      r.status_code == 200 and js(r).get("qayta_hisoblandi") == 4 and detal(DPK).get("narx") == 87000 and detal(DPB).get("narx") == 70000,
      (r.status_code, r.text[:200]))
CA.put(API + "/kub-narx", json={"kub_narx": 1200000})
check("V2g katalog javobida kapitel narxi — qo'lda yozilgani (do'kon katalogi)",
      any(d.get("id") == DPK and d.get("narx") == 87000 for m in (js(dokon_get("/api/dokon/v1/katalog")).get("modellar") or [])
          for d in (m.get("detallar") or [])))
# L2: balandlik 5 sm dan kam / 0 so'm
for n, e in (("0,1 sm", 0.1), ("4,9 sm (metrda yozilgan)", 4.9)):
    r = CA.post(API + "/detallar", json={"model_id": MK, "turi": "asosiy", "olcham": f"x{e}", "eni_sm": e})
    check(f"V3 (L2) formulali qator balandligi {n} — 400 (0 / 1 so'm narx yozilmaydi)", r.status_code == 400 and "5 sm" in js(r).get("detail", ""),
          (r.status_code, r.text[:200]))
r = CA.put(API + f"/detallar/{DK[20]}", json={"eni_sm": 0.2})
check("V3b mavjud qator balandligini 0,2 qilish — 400, o'zgarmadi", r.status_code == 400 and detal(DK[20]).get("eni_sm") == 20,
      (r.status_code, r.text[:200]))
# L3: juda katta 1 m³ narxi — 400 (500 emas), hech narsa o'zgarmadi
r = CA.put(API + "/kub-narx", json={"kub_narx": 1000000000})
check("V4 (L3) 1 m³ 1 000 000 000 — formula narxi chegaradan oshmaydi (20 sm ≈ 9,97 mln): qabul", r.status_code == 200, (r.status_code, r.text[:200]))
r = CA.post(API + "/detallar", json={"model_id": MK, "turi": "asosiy", "olcham": "1000 sm", "eni_sm": 1000})
check("V4b 1000 sm qator (narx 24,9 mlrd > chegara) — 400, 500 emas", r.status_code == 400 and "juda katta" in js(r).get("detail", ""),
      (r.status_code, r.text[:200]))
CA.put(API + f"/modellar/{MK}", json={"formula": {"asos_sm": 5, "blok_sm": 100, "bolak": 1}})
r = dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MK}&balandlik=40")
check("V4c eng katta formula (1 m³ 1 mlrd, 40 sm, blok 100 / asos 5) — narx chegara ichida (3,2 mlrd), 200",
      r.status_code == 200 and js(r).get("narx") == 3200000000, (r.status_code, r.text[:200]))
r = buyurtma([{"maxsus": {"model_id": MK, "balandlik_sm": 40}, "qoplamali": True, "miqdor": 2}])
check("V4c2 shunday qatorli buyurtma (summa ustun sig'imidan katta) — 400, 500 emas", r.status_code == 400, (r.status_code, r.text[:200]))
CA.put(API + f"/modellar/{MK}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
r = CA.put(API + "/kub-narx", json={"kub_narx": 1200000})
check("V4d 1 m³ qaytarildi — K-20 20 sm 11 964", r.status_code == 200 and detal(DK[20]).get("narx") == 11964, (r.status_code, r.text[:200]))
# L5: guruh nomida o'lcham bir marta; L6: chuqurlik — faqat ko'rinadigan qatordan (narx so'rovi = buyurtma)
CA.put(API + f"/detallar/{DK[20]}", json={"yoqilgan": False})
_jm = js(dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MK}&balandlik=18.5"))
r = buyurtma([{"maxsus": {"model_id": MK, "balandlik_sm": 18.5}, "qoplamali": False, "miqdor": 2}])
_qv = bazadan(lambda d: d.query(models.DokonBuyurtmaQator).order_by(models.DokonBuyurtmaQator.id.desc()).first())
check("V5 (L6) 20 sm qatori yashirin — chuqurlik narx so'rovida va buyurtma qatorida BIR XIL (eng yaqin ko'rinadigan qatordan)",
      r.status_code in (200, 201) and _qv is not None and _jm.get("qalinligi_sm") is not None and _qv.qalinligi_sm == _jm.get("qalinligi_sm"),
      (r.status_code, _jm.get("qalinligi_sm"), _qv and _qv.qalinligi_sm))
_gn = _qv and _qv.sbq_guruh_nomi
check("V6 (L5) guruh nomida «18,5 sm (maxsus o'lcham)» — BIR marta", _gn and _gn.count("18,5 sm (maxsus o'lcham)") == 1, _gn)
_sb5 = bazadan(lambda d: d.query(models.DokonBuyurtma).order_by(models.DokonBuyurtma.id.desc()).first())
_tg = bazadan(lambda d: crud.sayt_telegram_matni(_sb5, crud._sayt_qatorlari(d, 1, _sb5.id))) if _sb5 is not None else None
check("V6b Telegram xabarida ham bir marta", _tg and _tg.count("18,5 sm (maxsus o'lcham)") == 1, _tg)
CA.put(API + f"/detallar/{DK[20]}", json={"yoqilgan": True})
# M4: yetkazish sharti buyurtmada saqlanadi; eski (NULL) buyurtma — eski shart
r = buyurtma([{"detal_id": DO, "qoplamali": False, "miqdor": 2}], viloyat="fargona")
_sbf = bazadan(lambda d: d.query(models.DokonBuyurtma).order_by(models.DokonBuyurtma.id.desc()).first())
check("V7 (M4) yangi buyurtmada shart saqlandi: «Yetkazib berish — kelishuv asosida»",
      r.status_code in (200, 201) and _sbf is not None and _sbf.sb_yetkazish == "Yetkazib berish — kelishuv asosida", _sbf and _sbf.sb_yetkazish)
_asl_y = crud.SAYT_YETKAZISH_YARIM
try:
    crud.SAYT_YETKAZISH_YARIM = "Yetkazib berish — keyingi yangi shart"
    _v = bazadan(lambda d: crud.sayt_korinish(d.get(models.DokonBuyurtma, _sbf.id), qatorlar=crud._sayt_qatorlari(d, 1, _sbf.id)))
    _t = bazadan(lambda d: crud.sayt_telegram_matni(d.get(models.DokonBuyurtma, _sbf.id), crud._sayt_qatorlari(d, 1, _sbf.id)))
finally:
    crud.SAYT_YETKAZISH_YARIM = _asl_y
check("V7b shart keyin o'zgarsa ham shu buyurtmada — o'zi (ko'rinish, Telegram)",
      _v and _v.get("yetkazish_matni") == "Yetkazib berish — kelishuv asosida" and _t and "kelishuv asosida" in _t and "keyingi" not in _t,
      (_v and _v.get("yetkazish_matni"), _t))
bazadan(lambda d: (d.query(models.DokonBuyurtma).filter(models.DokonBuyurtma.id == _sbf.id).update({"sb_yetkazish": None}), d.commit()))
_t0 = bazadan(lambda d: crud.sayt_telegram_matni(d.get(models.DokonBuyurtma, _sbf.id), crud._sayt_qatorlari(d, 1, _sbf.id)))
check("V7c zip 255 dan oldingi buyurtma (shart saqlanmagan) — o'sha paytdagi shart «narxining yarmini biz to'laymiz»",
      _t0 and "yarmini biz to'laymiz" in _t0, _t0)
check("V7d Andijon (shart saqlanmagan) — «bepul»", crud.sayt_buyurtma_yetkazish(_NS(sb_yetkazish=None, sb_viloyat="andijon")) == "Yetkazib berish bepul")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Ikkinchi korxona, jurnal")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("Z1 B korxona 1 m³ narxi — o'ziniki (bo'sh)", js(CB.get(API)).get("kub_narx") is None, js(CB.get(API)).get("kub_narx"))
r = CB.put(API + f"/modellar/{MK}", json={"formula": None})
check("Z2 B korxona begona modelga formula — 404", r.status_code == 404, (r.status_code, r.text[:200]))
r = CB.put(API + "/kub-narx", json={"kub_narx": 999})
check("Z3 B korxonada do'kon yoqilmaydi (faqat platforma egasining korxonasi) — 404, A ning 1 m³ narxi o'zgarmadi",
      r.status_code == 404 and katalog().get("kub_narx") == 1200000, (r.status_code, r.text[:200]))
_j = bazadan(lambda d: [a.new_value for a in d.query(models.ActivityLog).filter(models.ActivityLog.company_id == 1).all()
                        if "1 m³" in (a.entity_label or "") or "formula" in (a.new_value or "")])
check("Z4 jurnalda 1 m³ narxi va formula o'zgarishlari", _j and any("qayta hisoblandi" in (x or "") for x in _j), _j)
r = CA.put(API + f"/modellar/{MK}", json={"formula": None})
check("Z5 formula o'chirildi — narxlar oxirgi qiymatda qoladi, qo'lda tahrir mumkin",
      r.status_code == 200 and detal(DK[20]).get("narx") == 11964 and CA.put(API + f"/detallar/{DK[20]}", json={"narx": 12000}).status_code == 200,
      (r.status_code, r.text[:200]))
r = dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={MK}&balandlik=18")
check("Z6 formulasi o'chgan modelda «Boshqa o'lcham» — 404", r.status_code == 404, r.status_code)
CA.put(API + f"/modellar/{MP}", json={"formula": None})
r = CA.put(API + "/kub-narx", json={"kub_narx": None})
check("Z7 formulali model qolmadi — 1 m³ narxini o'chirish mumkin", r.status_code == 200 and katalog().get("kub_narx") is None, r.text[:200])

print(f"\nNATIJA: {OK} / {OK + FAIL}{'  ' + YORLIQ if YORLIQ else ''}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
if PG_URL:
    try:
        from database import engine as _eng
        _eng.dispose()
        _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass
sys.exit(1 if FAIL else 0)
