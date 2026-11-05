#!/usr/bin/env python3
"""
test_karniz_qoplamali257.py — kech190 (zip 257: formulali karnizda QOPLAMALI narx — qo'lda).

NIMA UCHUN KERAK
  Zip 255 da formulali (karniz) modelning asosiy qatorida qoplamasiz VA qoplamali narx kataklari yopiq edi (qoplamali = qoplamasiz ×
  koeffitsient). Egasi QARORI 05.11: «qoplamali narxni ham qo'lda yozaman — × 2 bunda ishlamaydi» — qoplamali narx qo'lda (yozilsa —
  o'sha, bo'sh — × koeffitsient), formula FAQAT qoplamasiz narxni hisoblaydi va qo'lda yozilgan qoplamaliga tegmaydi (1 m³ narxi, formula,
  balandlik o'zgarsa ham). «Boshqa o'lcham» (katalogda yo'q balandlik) qoplamalisi — egasi tanlovi «Yaqin o'lchamdan»: eng yaqin qo'lda
  yozilgan o'lchamning qoplama ulushi (qoplamali − qoplamasiz) balandlikka mutanosib (30 sm 26 919 / 60 000 → 35 sm 36 640 + 38 595 = 75 235).
  Egasi QARORI 05.11 (keyingi xabar): «Boshqa o'lcham» — eng kichigi 25 sm, eng kattasi 60 sm (undan kattasi — korxona bilan bog'lanish).
  Asl kodda (zip 256) qo'lda qoplamali — 400, «Boshqa o'lcham» — × 2, oraliq 15 … 40: test yiqiladi (qulamaydi).
BO'LIMLAR
  S — tayyorgarlik. Q — qo'lda qoplamali (sahifa API: tahrir, yangi qator, rad, qayta hisoblarda saqlanishi, avto). E — Excel. M — «Boshqa
  o'lcham»: oraliq 25 … 60 va qoplamalisi (do'kon API; mustaqil hisob). B — savat / buyurtma (narx so'rovi bilan AYNAN). K — do'kon katalogi, chegirma.
  U — sahifa (Chromium; PG rejimida o'tkazib yuboriladi). Z — ikkinchi korxona (o'z do'koni bilan), jurnal.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
"""
import os
import io
import sys
import json
import time
import tempfile
import contextlib
from fractions import Fraction

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"karniz257_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t257_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't257.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "DOKON_BOT_TOKEN", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
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

# Mustaqil hisob (crud ga tayanmaydi): formula — h² × blok × kub ÷ (asos × 10 000 × bo'lak), HALF_UP butun so'm
ASOS, BLOK, BOLAK, KUB = Fraction(20), Fraction("9.97"), 2, Fraction(1200000)


def toza(v):
    """Sahifa katagidagi pul matni — bo'shliqlarsiz (oddiy, NBSP, tor NBSP)."""
    return "".join(ch for ch in str(v) if ch not in " \u00a0\u202f")


def yaxlit(x):
    return int((Fraction(x) + Fraction(1, 2)).__floor__())


def f_narx(h, kub=KUB, blok=BLOK):
    h = Fraction(str(h))
    return yaxlit(h * h * blok * kub / (ASOS * 10000 * BOLAK))


def f_qop(h, eni, qop_eni, kub=KUB):
    """Egasi tanlovi «Yaqin o'lchamdan»: formula(h) + (qoplamali(eni) − formula(eni)) × h ÷ eni (ulush manfiy — 0)."""
    ulush = Fraction(str(qop_eni)) - f_narx(eni, kub)
    return f_narx(h, kub) + (yaxlit(ulush * Fraction(str(h)) / Fraction(str(eni))) if ulush > 0 else 0)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Tayyorgarlik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
s.add(Company(id=2, name="T257 Begona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t257_admin", PAROL, UserRole.ADMIN, "T257 Admin", company_id=1)
    auth.create_user(s, "t257_plat", PAROL, UserRole.ADMIN, "T257 Platforma", company_id=1)
    auth.create_user(s, "t257_b", PAROL, UserRole.ADMIN, "T257 B", company_id=2)
s.query(User).filter(User.username == "t257_plat").first().is_platform_admin = True
s.query(User).filter(User.username == "t257_b").first().is_platform_admin = True     # review257 M2: B korxonaning HAQIQIY do'koni bo'lsin (Z)
s.commit()
s.close()


def kirish(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA, CP, CB = kirish("t257_admin"), kirish("t257_plat"), kirish("t257_b")
NC = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
CP.post("/api/platform/companies/2/dokon", data={"yoqilgan": "1"})
KALIT = js(CA.post(API + "/api-kalit", json={})).get("kalit") or ""
BOL = {b.get("nom"): b.get("id") for b in (js(CA.get(API)).get("bolimlar") or [])}
MK = js(CA.post(API + "/modellar", json={"bolim_id": BOL.get("Karnizlar"), "kod": "K-20", "nom": "Klassik"})).get("id")
MO = js(CA.post(API + "/modellar", json={"bolim_id": BOL.get("Karnizlar"), "kod": "K-30", "nom": "Oddiy"})).get("id")
DK = {}
for e, q in ((25, 8.45), (30, 10.14), (40, 13.52)):
    DK[e] = js(CA.post(API + "/detallar", json={"model_id": MK, "turi": "asosiy", "olcham": f"{e} sm", "narx": 50000, "eni_sm": e,
                                                 "qalinligi_sm": q})).get("id")
DO = js(CA.post(API + "/detallar", json={"model_id": MO, "turi": "asosiy", "olcham": "12 sm", "narx": 45123, "eni_sm": 12,
                                         "qalinligi_sm": 8})).get("id")
r1 = CA.put(API + "/kub-narx", json={"kub_narx": 1200000})
r2 = CA.put(API + f"/modellar/{MK}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
check("S1 do'kon, modellar, qatorlar, 1 m³ narxi va formula", BOL.get("Karnizlar") and len(KALIT) > 20 and MK and MO and all(DK.values())
      and DO and r1.status_code == 200 and r2.status_code == 200, (BOL, MK, MO, DK, DO, r1.text[:200], r2.text[:200]))


def katalog():
    return js(CA.get(API))


def detal(did):
    return next((d for d in (katalog().get("detallar") or []) if d.get("id") == did), {})


def chek_tozala():
    for _n in ("_DOKON_API_CHEKLOV", "_DOKON_MIJOZ_CHEKLOV", "_DOKON_BUYURTMA_CHEKLOV"):
        _ch = getattr(crud, _n, None)
        if _ch is not None:
            _ch.tozala()


def dokon_get(yol, kalit=None):
    chek_tozala()
    return NC.get(yol, headers={"X-Dokon-Kalit": KALIT if kalit is None else kalit})


def maxsus(h, mid=None):
    return dokon_get(f"/api/dokon/v1/maxsus-narx?model_id={mid or MK}&balandlik={h}")


def mq(h):
    return js(maxsus(h)).get("narx_qoplamali")


def mq_m(h, mid):
    return js(maxsus(h, mid)).get("narx_qoplamali")


_kn = [0]


def buyurtma(qatorlar):
    chek_tozala()
    _kn[0] += 1
    h = {"X-Dokon-Kalit": KALIT, "X-Amal-Kaliti": f"savat-{_kn[0]:06d}-t257", "Content-Type": "application/json"}
    tana = {"mijoz": "Ali Valiyev", "telefon": "+998901234567", "viloyat": "andijon", "qatorlar": qatorlar}
    return NC.post("/api/dokon/v1/buyurtmalar", content=json.dumps(tana).encode("utf-8"), headers=h)


check("S2 mustaqil hisob = server (25 / 30 / 40 sm: 18 694 / 26 919 / 47 856)",
      lambda: (detal(DK[25]).get("narx"), detal(DK[30]).get("narx"), detal(DK[40]).get("narx")) == (f_narx(25), f_narx(30), f_narx(40))
      == (18694, 26919, 47856), lambda: (detal(DK[25]), detal(DK[30]), detal(DK[40])))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Qo'lda qoplamali narx — formulali qatorda")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = CA.put(API + f"/detallar/{DK[30]}", json={"narx_qoplamali": 60000})
d = detal(DK[30])
check("Q1 formulali qatorga qoplamali 60 000 — qabul (asl kodda 400)", r.status_code == 200 and d.get("narx_qoplamali") == 60000,
      (r.status_code, r.text[:200]))
check("Q1b qoplamasiz narx formula bo'yicha qoldi (26 919), avto qiymat yo'q (qo'lda yozilgan)",
      d.get("narx") == 26919 and d.get("narx_qoplamali_avto") is None, d)
r = CA.put(API + f"/detallar/{DK[30]}", json={"narx": 10000})
check("Q2 qoplamasiz narx — baribir 400 (formula), matnda qoplamali qo'lda yozilishi aytiladi",
      r.status_code == 400 and "qoplamali narxni qo'lda" in js(r).get("detail", "") and detal(DK[30]).get("narx") == 26919,
      (r.status_code, r.text[:300]))
r = CA.put(API + f"/detallar/{DK[30]}", json={"narx": 10000, "narx_qoplamali": 65000})
check("Q3 ikkalasi birga — 400, qoplamali ham o'zgarmadi (bitta amal)", r.status_code == 400
      and detal(DK[30]).get("narx_qoplamali") == 60000, (r.status_code, detal(DK[30])))
r = CA.post(API + "/detallar", json={"model_id": MK, "turi": "asosiy", "olcham": "35 sm", "eni_sm": 35, "qalinligi_sm": 11.83,
                                     "narx_qoplamali": 80000})
D35 = js(r).get("id")
check("Q4 yangi formulali qator qoplamali bilan — qabul: qoplamasiz 36 640 (formula), qoplamali 80 000",
      r.status_code == 200 and detal(D35).get("narx") == f_narx(35) == 36640 and detal(D35).get("narx_qoplamali") == 80000,
      (r.status_code, r.text[:200]))
r = CA.post(API + "/detallar", json={"model_id": MK, "turi": "asosiy", "olcham": "45 sm", "eni_sm": 45, "narx": 1, "narx_qoplamali": 9})
check("Q5 yangi qator qoplamasiz narx bilan — 400 (qator yaratilmadi)", r.status_code == 400
      and not any(x.get("olcham") == "45 sm" for x in katalog().get("detallar") or []), (r.status_code, r.text[:200]))
r = CA.put(API + f"/detallar/{D35}", json={"eni_sm": 32})
check("Q6 balandlik o'zgardi → qoplamasiz qayta (32 sm → 30 628), qo'lda qoplamali 80 000 O'ZGARMADI",
      r.status_code == 200 and detal(D35).get("narx") == f_narx(32) == 30628 and detal(D35).get("narx_qoplamali") == 80000, detal(D35))
CA.delete(API + f"/detallar/{D35}")
CA.put(API + f"/modellar/{MK}", json={"kapitel_baza_bor": True})
_kp7 = js(CA.post(API + "/detallar", json={"model_id": MK, "turi": "kapitel", "olcham": "30 sm", "eni_sm": 30, "narx": 1000,
                                           "narx_qoplamali": 5000})).get("id")
r = CA.put(API + "/kub-narx", json={"kub_narx": 1300000})
check("Q7 1 m³ narxi o'zgardi → 3 qator qayta, qo'lda qoplamali qatorlar soni 1 (kapitel — qo'lda narx, formulaga kirmaydi — sanalmaydi)",
      _kp7 and r.status_code == 200 and js(r).get("qayta_hisoblandi") == 3 and js(r).get("qolda_qoplamali") == 1, (_kp7, r.status_code, r.text[:300]))
check("Q7d javobda ro'yxat: K-20 · 30 sm — qoplamasiz 29 162, qoplamali 60 000, kam emas, ko'rinadi",
      [{k: x.get(k) for k in ("detal_id", "kod", "olcham", "narx", "narx_qoplamali", "kam", "yashirin")} for x in js(r).get("qoplamali_qatorlar") or []]
      == [{"detal_id": DK[30], "kod": "K-20", "olcham": "30 sm", "narx": 29162, "narx_qoplamali": 60000, "kam": False, "yashirin": False}],
      r.text[:400])
CA.delete(API + f"/detallar/{_kp7}")
CA.put(API + f"/modellar/{MK}", json={"kapitel_baza_bor": False})
check("Q7b 30 sm qoplamasiz 29 162, qoplamali 60 000 O'ZGARMADI; 25 sm avto (37 388 → 40 504)",
      detal(DK[30]).get("narx") == f_narx(30, 1300000) == 29162 and detal(DK[30]).get("narx_qoplamali") == 60000
      and detal(DK[25]).get("narx_qoplamali") is None and detal(DK[25]).get("narx_qoplamali_avto") == 2 * f_narx(25, 1300000) == 40504,
      lambda: (detal(DK[30]), detal(DK[25])))
r = CA.put(API + "/kub-narx", json={"kub_narx": 1300000})
check("Q7c o'sha 1 m³ narxi qayta — 0 qayta hisob, eslatma yo'q", r.status_code == 200 and js(r).get("qayta_hisoblandi") == 0
      and not js(r).get("qolda_qoplamali"), r.text[:200])
r = CA.put(API + "/kub-narx", json={"kub_narx": 3000000})
_q13 = (js(r).get("qoplamali_qatorlar") or [{}])[0]
check("Q7e 1 m³ 3 000 000: 30 sm qoplamasiz 67 298 > qo'lda 60 000 — ro'yxatda «kam», narx avtomatik O'ZGARMAYDI (egasi qarori)",
      r.status_code == 200 and _q13.get("kam") is True and _q13.get("narx") == f_narx(30, 3000000) == 67298
      and detal(DK[30]).get("narx_qoplamali") == 60000, r.text[:300])
_j13 = bazadan(lambda d: [a.new_value or "" for a in d.query(models.ActivityLog).filter(models.ActivityLog.company_id == 1).all()])
check("Q7f jurnalda: «1 ta qatorda qoplamali narx qo'lda yozilgan — o'zgarmadi (1 tasida qoplamasizdan kam yoki teng)»",
      _j13 and any("1 ta qatorda qoplamali narx qo'lda yozilgan — o'zgarmadi (1 tasida qoplamasizdan kam yoki teng)" in x for x in _j13),
      _j13 and _j13[-3:])
CA.put(API + f"/detallar/{DK[30]}", json={"yoqilgan": False})
r = CA.put(API + "/kub-narx", json={"kub_narx": 1200000})
check("Q7g yashirin qator ro'yxatda «yashirin» belgisi bilan", ((js(r).get("qoplamali_qatorlar") or [{}])[0]).get("yashirin") is True, r.text[:300])
CA.put(API + f"/detallar/{DK[30]}", json={"yoqilgan": True})
r = CA.put(API + f"/modellar/{MK}", json={"formula": {"asos_sm": 20, "blok_sm": 10, "bolak": 2}})
check("Q8a formula o'zgarganda ham javobda qo'lda qoplamali qatorlar (1)", r.status_code == 200 and js(r).get("qolda_qoplamali") == 1
      and (js(r).get("qoplamali_qatorlar") or [{}])[0].get("detal_id") == DK[30], r.text[:300])
check("Q8 formula o'zgardi (blok 10) → 30 sm 27 000, qoplamali 60 000 O'ZGARMADI",
      r.status_code == 200 and detal(DK[30]).get("narx") == 27000 and detal(DK[30]).get("narx_qoplamali") == 60000, detal(DK[30]))
CA.put(API + f"/modellar/{MK}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
check("Q8b formula qaytarildi — 26 919 / 60 000", detal(DK[30]).get("narx") == 26919 and detal(DK[30]).get("narx_qoplamali") == 60000,
      detal(DK[30]))
r = CA.put(API + f"/detallar/{DK[30]}", json={"narx_qoplamali": None})
check("Q9 qoplamali bo'shatildi — avto × 2 (53 838)", r.status_code == 200 and detal(DK[30]).get("narx_qoplamali") is None
      and detal(DK[30]).get("narx_qoplamali_avto") == 53838, detal(DK[30]))
for n, v in (("manfiy", -5), ("matn", "60000"), ("bool", True), ("0", 0)):
    r = CA.put(API + f"/detallar/{DK[30]}", json={"narx_qoplamali": v})
    check(f"Q10 qoplamali noto'g'ri ({n}) — 400 (oddiy qator qoidasi)", r.status_code == 400 and detal(DK[30]).get("narx_qoplamali") is None,
          (r.status_code, r.text[:200]))
CA.put(API + f"/detallar/{DK[30]}", json={"narx_qoplamali": 60000})
r = CA.put(API + f"/detallar/{DK[30]}", json={"ulgurji_narx": 40000, "ulgurji_qoplamali": 52000})
check("Q11 ulgurji narxlar — qo'lda (avvalgidek), chakana qoplamali o'zgarmadi", r.status_code == 200
      and detal(DK[30]).get("ulgurji_qoplamali") == 52000 and detal(DK[30]).get("narx_qoplamali") == 60000, detal(DK[30]))
# formula o'chirilib qayta yoqilsa ham qo'lda qoplamali qoladi (bitta qoida: formula faqat qoplamasizga tegadi)
CA.put(API + f"/modellar/{MK}", json={"formula": None})
r = CA.put(API + f"/modellar/{MK}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
check("Q12 formula o'chirib qayta yoqildi — qoplamali 60 000 saqlandi, qoplamasiz formula", r.status_code == 200
      and detal(DK[30]).get("narx") == 26919 and detal(DK[30]).get("narx_qoplamali") == 60000, detal(DK[30]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Excel orqali")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    import openpyxl

    def _excel(ozgar):
        _b = bazadan(lambda d: crud.dokon_excel_yarat(d, 1))
        wb = openpyxl.load_workbook(io.BytesIO(_b))
        ws = wb.worksheets[0]
        ust = {}
        sar = None
        for row in ws.iter_rows():
            for c in row:
                if c.value in ("Narx (qoplamasiz), so'm", "Narx (qoplamali), so'm", "Raqam"):
                    ust.setdefault(c.value, c.column)
                    sar = sar or c.row
        qator = next(r_ for r_ in range(sar + 1, ws.max_row + 1) if ws.cell(r_, ust["Raqam"]).value == DK[30])
        for k, v in ozgar.items():
            ws.cell(qator, ust[k]).value = v
        o = io.BytesIO()
        wb.save(o)
        return bazadan(lambda d: crud.dokon_excel_korish(d, 1, o.getvalue()))

    _kor = _excel({"Narx (qoplamali), so'm": 62000})
    check("E1 Excel'da formulali qatorning QOPLAMALI narxi o'zgartirilsa — xatosiz, o'zgarishda (60 000 → 62 000)",
          _kor and not _kor["xatolar"] and len(_kor["ozgarishlar"]) == 1
          and _kor["ozgarishlar"][0]["yangi"].get("narx_qoplamali") == 62000, _kor and (_kor["xatolar"][:3], _kor["ozgarishlar"]))
    r = CA.post(API + "/excel/saqla", json={"ozgarishlar": [{k: x[k] for k in ("id", "kimlik", "eski", "yangi")} for x in _kor["ozgarishlar"]]})
    check("E2 Excel saqlash — qoplamali 62 000 yozildi, qoplamasiz formula (26 919)", r.status_code == 200
          and detal(DK[30]).get("narx_qoplamali") == 62000 and detal(DK[30]).get("narx") == 26919, (r.status_code, r.text[:200]))
    _kor = _excel({"Narx (qoplamasiz), so'm": 10000})
    check("E3 Excel'da QOPLAMASIZ narx o'zgartirilsa — baribir xato (formula), o'zgarish yo'q",
          _kor and any("formula" in x for x in _kor["xatolar"]) and not _kor["ozgarishlar"], _kor and _kor["xatolar"][:3])
    r = CA.post(API + "/excel/saqla", json={"ozgarishlar": [{"id": DK[30], "kimlik": "K-20 · Asosiy · 30 sm", "eski": {"narx": 26919},
                                                              "yangi": {"narx": 10000}}]})
    check("E4 Excel saqlash yo'li (to'g'ridan-to'g'ri) — qoplamasiz rad", r.status_code in (400, 404, 409)
          and detal(DK[30]).get("narx") == 26919, (r.status_code, r.text[:200]))
except Exception as e:                     # noqa: BLE001
    check("E Excel bo'limi", False, f"{type(e).__name__}: {e}")
CA.put(API + f"/detallar/{DK[30]}", json={"narx_qoplamali": 60000})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. «Boshqa o'lcham» — oraliq 25 … 60 sm va qoplamali (eng yaqin qo'lda yozilgan o'lchamdan; do'kon API)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# katalog: 25 sm (avto), 30 sm (qo'lda 60 000), 40 sm (avto)
r = maxsus(35)
check("M1 misol: 35 sm → 36 640 / 75 235 (ulush 33 081 × 35 / 30 = 38 594,5 → 38 595; asl kodda × 2 = 73 280)",
      r.status_code == 200 and js(r).get("narx") == 36640 and js(r).get("narx_qoplamali") == 75235 == f_qop(35, 30, 60000),
      (r.status_code, r.text[:300]))
check("M2 28 sm → 23 449 + 33 081 × 28 / 30 = 54 325", mq(28) == f_qop(28, 30, 60000) == 54325, maxsus(28).text[:300])
check("M2b 27,5 sm — mustaqil hisob bilan AYNAN", mq("27.5") == f_qop("27.5", 30, 60000), maxsus("27.5").text[:300])
check("M3 katalogdagi o'lchamning o'zi: 30 sm → 60 000 (qo'lda yozilgani AYNAN)", mq(30) == 60000, maxsus(30).text[:300])
check("M3b katalogdagi avto o'lcham: 25 sm → 37 388 (× 2, katalog bilan AYNAN — yaqin qo'lda yozilganidan EMAS)",
      mq(25) == detal(DK[25]).get("narx_qoplamali_avto") == 37388, maxsus(25).text[:300])
check("M3c 40 sm (avto) → 95 712 = 47 856 × 2", mq(40) == 2 * f_narx(40) == 95712, maxsus(40).text[:300])
CA.put(API + f"/detallar/{DK[40]}", json={"narx_qoplamali": 100000})
check("M4 teng masofa (30 va 40 sm qo'lda) — kichigi (30 sm) olinadi: 35 sm → 75 235", mq(35) == 75235, maxsus(35).text[:300])
check("M5 38 sm → eng yaqini 40 sm", mq(38) == f_qop(38, 40, 100000), (maxsus(38).text[:300], f_qop(38, 40, 100000)))
check("M5b 60 sm (yuqori chegara) → 40 sm dan", mq(60) == f_qop(60, 40, 100000), (maxsus(60).text[:300], f_qop(60, 40, 100000)))
check("M5c 26 sm → eng yaqin QO'LDA yozilgani 30 sm (25 sm avto — hisobga olinmaydi): 48 889",
      mq(26) == f_qop(26, 30, 60000) == 48889, maxsus(26).text[:300])
CA.put(API + f"/detallar/{DK[30]}", json={"yoqilgan": False})
check("M6 30 sm qatori saytda yashirin — 28 sm uchun 40 sm dan (faqat ko'rinadigan qatorlar)", mq(28) == f_qop(28, 40, 100000),
      (maxsus(28).text[:300], f_qop(28, 40, 100000)))
check("M6b yashirin 30 sm balandligi «Boshqa o'lcham» sifatida — 40 sm dan (yashirin narx sizib chiqmaydi)",
      lambda: mq(30) == f_qop(30, 40, 100000) and mq(30) != 60000, maxsus(30).text[:300])
CA.put(API + f"/detallar/{DK[30]}", json={"yoqilgan": True})
CA.put(API + f"/detallar/{DK[40]}", json={"narx_qoplamali": 40000})
r = maxsus(45)
check("M7 qo'lda qoplamali qoplamasizdan kichik (40 sm: 40 000 < 47 856) — ulush 0: qoplamali = qoplamasiz (manfiy emas)",
      js(r).get("narx_qoplamali") == js(r).get("narx") == f_narx(45), r.text[:300])
CA.put(API + f"/detallar/{DK[40]}", json={"narx_qoplamali": None})
CA.put(API + f"/detallar/{DK[30]}", json={"narx_qoplamali": None})
check("M8 qo'lda yozilgan qoplamali yo'q — avvalgidek × koeffitsient (35 sm: 73 280)", mq(35) == 2 * f_narx(35) == 73280,
      maxsus(35).text[:300])
CA.put(API + "/koeff", json={"koeff": 1.5})
check("M8b koeffitsient 1,5 — 36 640 × 1,5 = 54 960", mq(35) == 54960, maxsus(35).text[:300])
CA.put(API + "/koeff", json={"koeff": 2})
CA.put(API + f"/detallar/{DK[30]}", json={"narx_qoplamali": 60000})
CA.put(API + "/kub-narx", json={"kub_narx": 1300000})
check("M9 1 m³ narxi 1 300 000: ulush endi 60 000 − 29 162 → 35 sm (mustaqil hisob 75 671)",
      mq(35) == f_qop(35, 30, 60000, kub=1300000) == 75671, (maxsus(35).text[:300], f_qop(35, 30, 60000, kub=1300000)))
CA.put(API + "/kub-narx", json={"kub_narx": 1200000})
# kapitel / baza (donada, qo'lda) — «Boshqa o'lcham» qoplamalisiga ta'sir qilmaydi (faqat asosiy qatorlar)
CA.put(API + f"/modellar/{MK}", json={"kapitel_baza_bor": True})
_kp = js(CA.post(API + "/detallar", json={"model_id": MK, "turi": "kapitel", "olcham": "34 sm", "eni_sm": 34, "narx": 1000,
                                          "narx_qoplamali": 900000})).get("id")
check("M10 kapitel qatori (34 sm, qoplamali 900 000) hisobga olinmaydi — 34 sm 30 sm dan", lambda: _kp and mq(34) == f_qop(34, 30, 60000),
      (_kp, maxsus(34).text[:300]))
CA.delete(API + f"/detallar/{_kp}")
CA.put(API + f"/modellar/{MK}", json={"kapitel_baza_bor": False})
# oraliq — egasi QARORI 05.11: 25 … 60 sm
for n, h in (("24,9", "24.9"), ("15 (eski chegara)", "15"), ("20", "20")):
    r = maxsus(h)
    check(f"M11 {n} sm — 400 «eng kichik o'lcham — 25 sm»", r.status_code == 400 and "eng kichik o'lcham — 25 sm" in js(r).get("detail", ""),
          (r.status_code, r.text[:200]))
for n, h in (("60,1", "60.1"), ("61", "61"), ("100", "100")):
    r = maxsus(h)
    check(f"M12 {n} sm — 400 «60 sm dan katta … korxona bilan bog'laning»", r.status_code == 400
          and "60 sm dan katta o'lcham kerak bo'lsa — korxona bilan bog'laning" in js(r).get("detail", ""), (r.status_code, r.text[:200]))
for h in ("25", "41", "59.9", "60"):
    r = maxsus(h)
    check(f"M13 {h} sm — qabul (asl kodda 41 … 60 rad)", r.status_code == 200 and js(r).get("narx") == f_narx(h), (r.status_code, r.text[:200]))
_mk = next((m for m in (js(dokon_get("/api/dokon/v1/katalog")).get("modellar") or []) if m.get("id") == MK), {})
check("M14 do'kon katalogida oraliq 25 … 60, sahifa katalogida ham", (_mk.get("maxsus") or {}).get("min") == 25
      and (_mk.get("maxsus") or {}).get("max") == 60 and katalog().get("maxsus_min") == 25 and katalog().get("maxsus_max") == 60,
      (_mk.get("maxsus"), katalog().get("maxsus_min"), katalog().get("maxsus_max")))
r = buyurtma([{"maxsus": {"model_id": MK, "balandlik_sm": 24}, "qoplamali": False, "miqdor": 2}])
check("M15 savatda 24 sm — 400 (buyurtma yo'li ham oraliqni tekshiradi)", r.status_code == 400 and "25 sm" in r.text, (r.status_code, r.text[:200]))
r = buyurtma([{"maxsus": {"model_id": MK, "balandlik_sm": 61}, "qoplamali": False, "miqdor": 2}])
check("M15b savatda 61 sm — 400 «korxona bilan bog'laning»", r.status_code == 400 and "korxona bilan bog'laning" in r.text, (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Savat / buyurtma — narx so'rovi bilan AYNAN")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = buyurtma([{"maxsus": {"model_id": MK, "balandlik_sm": 35}, "qoplamali": True, "miqdor": 4}])
check("B1 maxsus 35 sm qoplamali 4 m — qabul", r.status_code in (200, 201) and js(r).get("raqam"), (r.status_code, r.text[:300]))
_q = bazadan(lambda d: d.query(models.DokonBuyurtmaQator).order_by(models.DokonBuyurtmaQator.id.desc()).first())
check("B2 qator narxi 75 235, summa 300 940, hajm narxi (qoplamasiz) 36 640", _q is not None and float(_q.narx) == 75235
      and float(_q.summa) == 300940 and float(_q.hajm_narxi) == 36640 and _q.qoplamali, _q and (_q.narx, _q.summa, _q.hajm_narxi))
_sb = bazadan(lambda d: d.query(models.DokonBuyurtma).order_by(models.DokonBuyurtma.id.desc()).first())
check("B3 buyurtma jami 300 940", _sb is not None and float(_sb.sb_jami) == 300940, _sb and _sb.sb_jami)
r = buyurtma([{"maxsus": {"model_id": MK, "balandlik_sm": 35}, "qoplamali": False, "miqdor": 2}])
_q = bazadan(lambda d: d.query(models.DokonBuyurtmaQator).order_by(models.DokonBuyurtmaQator.id.desc()).first())
check("B4 qoplamasiz — formula (36 640), qo'lda qoplamali ta'sir qilmaydi", r.status_code in (200, 201) and _q is not None
      and float(_q.narx) == 36640, (r.status_code, _q and _q.narx))
r = buyurtma([{"detal_id": DK[30], "qoplamali": True, "miqdor": 2}])
_q = bazadan(lambda d: d.query(models.DokonBuyurtmaQator).order_by(models.DokonBuyurtmaQator.id.desc()).first())
check("B5 katalog o'lchami 30 sm qoplamali — qo'lda yozilgan 60 000", r.status_code in (200, 201) and _q is not None
      and float(_q.narx) == 60000, (r.status_code, _q and _q.narx))
_h = bazadan(lambda d: crud.sayt_buyurtma_hisobla(d, 1, [{"maxsus": {"model_id": MK, "balandlik_sm": 28}, "qoplamali": True, "miqdor": 2}]))
check("B6 savat hisobi (ERP) = narx so'rovi (28 sm qoplamali 54 325 × 2)", lambda: _h is not None and float(_h["jami"]) == 2 * 54325
      == 2 * mq(28), _h and _h["jami"])
# review257 M2: buyurtma yo'liga YASHIRIN qatorlar ham keladi — narx so'rovi bilan bir xil bo'lishi kerak
CA.put(API + f"/detallar/{DK[40]}", json={"narx_qoplamali": 100000})
CA.put(API + f"/detallar/{DK[30]}", json={"yoqilgan": False})


def _hisob(h):
    x = bazadan(lambda d: crud.sayt_buyurtma_hisobla(d, 1, [{"maxsus": {"model_id": MK, "balandlik_sm": h}, "qoplamali": True, "miqdor": 2}]))
    return None if x is None else float(x["jami"]) / 2


check("B7 30 sm yashirin: 28 sm buyurtma = narx so'rovi = 40 sm dan (yashirin 30 sm hisobga olinmaydi)",
      lambda: _hisob(28) == mq(28) == f_qop(28, 40, 100000), lambda: (_hisob(28), mq(28), f_qop(28, 40, 100000)))
check("B7b aynan 30 sm buyurtma = narx so'rovi, yashirin qo'lda 60 000 EMAS", lambda: _hisob(30) == mq(30) == f_qop(30, 40, 100000) != 60000,
      lambda: (_hisob(30), mq(30)))
CA.put(API + f"/detallar/{DK[30]}", json={"yoqilgan": True})
CA.put(API + f"/detallar/{DK[40]}", json={"narx_qoplamali": None})
# review257 M2: teng masofada — KICHIK balandlik (id tartibi teskari bo'lsa ham); bir balandlikda ikki qator — qo'lda yozilgani
MK2 = js(CA.post(API + "/modellar", json={"bolim_id": BOL.get("Karnizlar"), "kod": "K-40", "nom": "Tartib"})).get("id")
_d2 = {}
for nom, e, q in (("30 sm B", 30, None), ("40 sm", 40, 110000), ("30 sm", 30, 65000)):
    _t = {"model_id": MK2, "turi": "asosiy", "olcham": nom, "eni_sm": e, "qalinligi_sm": 10, "narx": 1}
    _d2[nom] = js(CA.post(API + "/detallar", json=_t)).get("id")
CA.put(API + f"/modellar/{MK2}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
CA.put(API + f"/detallar/{_d2['40 sm']}", json={"narx_qoplamali": 110000})
CA.put(API + f"/detallar/{_d2['30 sm']}", json={"narx_qoplamali": 65000})
check("B8 tayyorgarlik: 30 sm B (avto, id kichik), 40 sm (qo'lda, id o'rtada), 30 sm (qo'lda, id katta)",
      _d2["30 sm B"] < _d2["40 sm"] < _d2["30 sm"] and detal(_d2["30 sm"]).get("narx_qoplamali") == 65000, _d2)
check("B8b teng masofa (35 sm: 30 va 40) — kichik balandlik (30 sm, id katta bo'lsa ham)", lambda: mq_m(35, MK2) == f_qop(35, 30, 65000),
      lambda: (mq_m(35, MK2), f_qop(35, 30, 65000), f_qop(35, 40, 110000)))
check("B8c aynan 30 sm — ikki qatordan QO'LDA yozilgani (65 000), avto emas", lambda: mq_m(30, MK2) == 65000, lambda: mq_m(30, MK2))
check("B8d buyurtma yo'li ham shunday", lambda: bazadan(lambda d: float(crud.sayt_buyurtma_hisobla(d, 1, [
      {"maxsus": {"model_id": MK2, "balandlik_sm": 35}, "qoplamali": True, "miqdor": 2}])["jami"])) == 2 * f_qop(35, 30, 65000))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Do'kon katalogi va chegirma")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_km = next((m for m in (js(dokon_get("/api/dokon/v1/katalog")).get("modellar") or []) if m.get("id") == MK), {})
_k30 = next((x for x in (_km.get("detallar") or []) if x.get("id") == DK[30]), {})
_k25 = next((x for x in (_km.get("detallar") or []) if x.get("id") == DK[25]), {})
check("K1 do'kon katalogida 30 sm: 26 919 / 60 000 (qo'lda), 25 sm: 18 694 / 37 388 (avto)",
      (_k30.get("narx"), _k30.get("narx_qoplamali"), _k25.get("narx"), _k25.get("narx_qoplamali")) == (26919, 60000, 18694, 37388),
      (_k30, _k25))
r = CA.put(API + f"/modellar/{MK}/chegirma", json={"foiz": 10})
_km = next((m for m in (js(dokon_get("/api/dokon/v1/katalog")).get("modellar") or []) if m.get("id") == MK), {})
_k30 = next((x for x in (_km.get("detallar") or []) if x.get("id") == DK[30]), {})
check("K2 chegirma 10 %: qo'lda qoplamali 60 000 → 54 000", r.status_code == 200 and (_k30.get("chegirma") or {}).get("narx_qoplamali") == 54000,
      (r.status_code, _k30.get("chegirma")))
check("K2b «Boshqa o'lcham»ga chegirma yo'q (avvalgidek) — 35 sm 75 235", mq(35) == 75235, maxsus(35).text[:200])
CA.delete(API + f"/modellar/{MK}/chegirma")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. Sahifa — «Sayt katalogi» (Chromium)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
    import glob
    import socket
    import threading
    import uvicorn
    from playwright.sync_api import sync_playwright
    _sk = socket.socket()
    _sk.bind(("127.0.0.1", 0))
    PORT = _sk.getsockname()[1]
    _sk.close()
    _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error", lifespan="off"))
    threading.Thread(target=_srv.run, daemon=True).start()
    while not _srv.started:
        time.sleep(0.1)
    BASE = f"http://127.0.0.1:{PORT}"
    _exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    XATOLAR = []
    UI = {}

    def _ui():
        with sync_playwright() as pw:
            br = pw.chromium.launch(executable_path=_exe[-1] if _exe else None)
            ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent")
            ctx.route("**/*", lambda r: r.fulfill(status=204, body="") if not r.request.url.startswith(BASE) else r.continue_())
            pg = ctx.new_page()
            pg.set_default_timeout(10000)
            pg.on("pageerror", lambda e: XATOLAR.append(str(e)[:200]))
            pg.on("dialog", lambda d: (XATOLAR.append("dialog: " + d.message[:100]), d.accept()))
            pg.goto(BASE + "/login")
            pg.fill("input[name=username]", "t257_admin")
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            pg.goto(BASE + "/sayt-katalogi")
            pg.wait_for_load_state("networkidle")
            pg.click(".sk-bolim:has-text('Karnizlar')")
            pg.wait_for_timeout(300)
            pg.click(f"[data-och='{MK}']")
            pg.wait_for_timeout(300)

            def katak(did, k):
                return pg.evaluate(f"""() => {{ const i = document.querySelector('tr[data-detal="{did}"] [data-df="{k}"]');
                    return i ? {{dis: i.disabled, v: i.value}} : null; }}""")
            UI["narx30"], UI["qop30"] = katak(DK[30], "narx"), katak(DK[30], "narx_qoplamali")
            UI["qop_kp_matn"] = pg.evaluate(f"""() => document.querySelector('.sk-model[data-model="{MK}"]').textContent""")
            # qoplamali katagiga yozish → server
            q = pg.locator(f"tr[data-detal='{DK[30]}'] [data-df='narx_qoplamali']")
            q.fill("61 500")
            q.dispatch_event("change")
            pg.wait_for_timeout(800)
            UI["qop30_server"] = detal(DK[30]).get("narx_qoplamali")
            # balandlik o'zgarsa — yopiq qoplamasiz katagi yangilanadi
            e = pg.locator(f"tr[data-detal='{DK[40]}'] [data-df='eni_sm']")
            e.fill("32")
            e.dispatch_event("change")
            pg.wait_for_timeout(800)
            UI["narx40_keyin"] = katak(DK[40], "narx")
            # yangi qator: «Asosiy» — qoplamasiz yopiq, qoplamali ochiq
            tr = f"tr[data-yangi='{MK}']"
            pg.select_option(tr + " [data-yf='turi']", "asosiy")
            UI["yangi"] = pg.evaluate(f"""() => {{ const t = document.querySelector("{tr}");
                const n = t.querySelector('[data-yf="narx"]'), q = t.querySelector('[data-yf="narx_qoplamali"]');
                return {{n: n.disabled, q: q.disabled, qp: q.placeholder}}; }}""")
            pg.fill(tr + " [data-yf='olcham']", "36 sm")
            pg.fill(tr + " [data-yf='eni_sm']", "36")
            pg.fill(tr + " [data-yf='narx_qoplamali']", "87 000")
            pg.click(f"[data-dyarat='{MK}']")
            pg.wait_for_timeout(900)
            UI["yangi_server"] = next(((x.get("narx"), x.get("narx_qoplamali")) for x in katalog().get("detallar") or []
                                       if x.get("model_id") == MK and x.get("olcham") == "36 sm"), None)
            pg.click(f"[data-och='{MK}']") if not pg.is_visible(f"tr[data-detal='{DK[30]}'] [data-df='narx_qoplamali']") else None
            # qoplamasizdan kam qoplamali — katak ostida ⚠ (saqlanadi, rad etilmaydi)
            q = pg.locator(f"tr[data-detal='{DK[30]}'] [data-df='narx_qoplamali']")
            q.fill("20 000")
            q.dispatch_event("change")
            pg.wait_for_timeout(800)
            UI["kam_izoh"] = pg.evaluate(f"""() => document.querySelector('tr[data-detal="{DK[30]}"] [data-avto="narx_qoplamali"]').textContent""")
            UI["kam_server"] = detal(DK[30]).get("narx_qoplamali")
            # 1 m³ narxi saqlansa — YOPILMAYDIGAN oynada ro'yxat
            pg.fill("#skKub", "1 250 000")
            pg.click("#skKubSaqla")
            pg.wait_for_timeout(5000)                       # showMsg 4 s da yo'qoladi — oyna qolishi kerak
            UI["kub_xabar"] = pg.evaluate("() => document.body.innerText")
            # formula saqlansa ham — oyna
            pg.evaluate("() => document.querySelectorAll('button').forEach(b => { if (/^(OK|Yopish|Tushunarli)$/.test(b.textContent.trim())) b.click(); })")
            pg.wait_for_timeout(400)
            UI["oyna_yopildi"] = "Qoplamali narxlarni tekshiring" not in pg.evaluate("() => document.body.innerText")
            UI["qayta_kam"] = pg.evaluate(f"""() => document.querySelector('tr[data-detal="{DK[30]}"] [data-avto="narx_qoplamali"]').textContent""")
            br.close()

    try:
        _ui()
    except Exception as _e:                # noqa: BLE001
        UI["xato"] = f"{type(_e).__name__}: {_e}"[:400]
    check("U1 formulali qatorda qoplamasiz katagi yopiq, QOPLAMALI ochiq va qiymati 60 000 (asl kodda yopiq)",
          lambda: UI["narx30"]["dis"] is True and UI["qop30"]["dis"] is False and toza(UI["qop30"]["v"]) == "60000",
          lambda: (UI.get("narx30"), UI.get("qop30"), UI.get("xato")))
    check("U2 izoh: «qoplamali narx — qo'lda (bo'sh — × koeffitsient)»", lambda: "qoplamali narx — qo'lda" in UI["qop_kp_matn"],
          lambda: UI.get("qop_kp_matn", "")[-400:])
    check("U3 qoplamali katagiga 61 500 yozildi — serverda 61 500", lambda: UI["qop30_server"] == 61500, lambda: UI.get("qop30_server"))
    check("U4 balandlik 32 sm — yopiq qoplamasiz katagi darhol 30 628 (sahifa yangilanmasdan)",
          lambda: toza(UI["narx40_keyin"]["v"]) == "30628", lambda: UI.get("narx40_keyin"))
    check("U5 yangi qator «Asosiy»: qoplamasiz yopiq, qoplamali ochiq («avto»)",
          lambda: UI["yangi"] == {"n": True, "q": False, "qp": "avto"}, lambda: UI.get("yangi"))
    check("U6 yangi qator 36 sm qoplamali 87 000 bilan yaratildi (qoplamasiz — formula)",
          lambda: UI["yangi_server"] == (f_narx(36), 87000), lambda: (UI.get("yangi_server"), f_narx(36)))
    check("U7 1 m³ narxi saqlanganda — 5 s dan keyin ham turgan oyna «Qoplamali narxlarni tekshiring», qatorlar ro'yxati, ⚠ kam",
          lambda: "Qoplamali narxlarni tekshiring" in UI["kub_xabar"] and "K-20 · 30 sm" in UI["kub_xabar"] and "K-20 · 36 sm" in UI["kub_xabar"]
          and "⚠ qoplamasizdan kam" in UI["kub_xabar"] and "O'ZGARMADI" in UI["kub_xabar"], lambda: UI.get("kub_xabar", "")[-900:])
    check("U9 qoplamasizdan kam qoplamali (20 000) — saqlandi va katak ostida «⚠ qoplamasizdan kam»; jadval qayta chizilganda ham",
          lambda: UI["kam_server"] == 20000 and "⚠ qoplamasizdan kam" in UI["kam_izoh"] and "⚠ qoplamasizdan kam" in UI["qayta_kam"],
          lambda: (UI.get("kam_server"), UI.get("kam_izoh"), UI.get("qayta_kam")))
    check("U10 oyna tugma bilan yopiladi", lambda: UI["oyna_yopildi"] is True, lambda: UI.get("oyna_yopildi"))
    check("U8 sahifada JS xatosi / xom oyna yo'q", lambda: not XATOLAR and "xato" not in UI, lambda: (XATOLAR, UI.get("xato")))
    CA.put(API + "/kub-narx", json={"kub_narx": 1200000})
    CA.put(API + f"/detallar/{DK[40]}", json={"eni_sm": 40})
    CA.put(API + f"/detallar/{DK[30]}", json={"narx_qoplamali": 60000})
    for _x in [x for x in katalog().get("detallar") or [] if x.get("model_id") == MK and x.get("olcham") == "36 sm"]:
        CA.delete(API + f"/detallar/{_x['id']}")                 # UI da qo'shilgan qator — keyingi bo'limlar SQ / PG da bir xil holatda

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Ikkinchi korxona, jurnal")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("Z0 B korxonaning o'z do'koni ochiq (sinov haqiqiy bo'lsin)", CB.get(API).status_code == 200, CB.get(API).text[:200])
r = CB.put(API + f"/detallar/{DK[30]}", json={"narx_qoplamali": 1})
check("Z1 B korxona begona qatorga qoplamali — 404 «Narx qatori topilmadi», o'zgarmadi", r.status_code == 404
      and "topilmadi" in js(r).get("detail", "") and detal(DK[30]).get("narx_qoplamali") == 60000, (r.status_code, r.text[:200]))
_bol_b = {b.get("nom"): b.get("id") for b in (js(CB.get(API)).get("bolimlar") or [])}
_mb = js(CB.post(API + "/modellar", json={"bolim_id": _bol_b.get("Karnizlar"), "kod": "K-20", "nom": "B karniz"})).get("id")
_db = js(CB.post(API + "/detallar", json={"model_id": _mb, "turi": "asosiy", "olcham": "33 sm", "eni_sm": 33, "qalinligi_sm": 11,
                                          "narx": 1, "narx_qoplamali": 9000000})).get("id")
CB.put(API + "/kub-narx", json={"kub_narx": 1200000})
_rb = CB.put(API + f"/modellar/{_mb}", json={"formula": {"asos_sm": 20, "blok_sm": 9.97, "bolak": 2}})
check("Z1b B korxonada 33 sm qo'lda qoplamali 9 000 000 — A korxonaning 34 / 33 sm «Boshqa o'lcham»iga ta'sir qilmaydi",
      _mb and _db and _rb.status_code == 200 and mq(34) == f_qop(34, 30, 60000) and mq(33) == f_qop(33, 30, 60000),
      (_mb, _db, _rb.text[:200], mq(34), f_qop(34, 30, 60000)))
_j = bazadan(lambda d: [a.new_value or "" for a in d.query(models.ActivityLog).filter(models.ActivityLog.company_id == 1).all()])
check("Z2 jurnalda: 1 m³ narxi o'zgarganda «qatorda qoplamali narx qo'lda yozilgan — o'zgarmadi»",
      _j and any("qoplamali narx qo'lda yozilgan — o'zgarmadi" in x for x in _j), _j and _j[-5:])
check("Z3 jurnalda qo'lda qoplamali tahriri (Sayt narxi K-20)", _j and any("60 000" in x or "60000" in x for x in _j), _j and _j[-5:])

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
