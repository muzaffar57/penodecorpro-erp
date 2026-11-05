#!/usr/bin/env python3
"""
test_dokon_tayyor238.py — kech172 (zip 238 «Tayyor mahsulotlar saytda»; egasi QARORLARI «Onlayn do'kon rejasi» 30.10: «Tayyor
mahsulotlar» — omborda bor, faqat QOPLAMALI, katalog narxida, qoldiq ERP dan; brak / 2-nav ko'rinmaydi; moslik — ERP «Kam qoldiq» kaliti;
saytdan kelgan buyurtma ombordagi mahsulotni darhol BAND qiladi — tasdiqlanmasa 48 soatdan keyin o'zi bo'shaydi, bekor qilinsa — darhol;
komplekt «Tayyor mahsulotlar»da — detallar qoldig'idan, eng kichigi).

NIMA UCHUN KERAK
  Xato — ikki mijozga oxirgi metrni sotish (band yo'q / poyga), brak / qoplamasiz / jarayondagi partiyani saytdagi qoldiqqa qo'shish, band
  muddati o'tgach ham qoldiqni ushlab turish, bekor qilinganda bandni bo'shatmaslik, tasdiqlashda partiyaga emas penoplastga yozish (ombor
  ikki marta), qaytgan partiyani hisobga olmaslik yoki ERP guruh qoidasini buzish, forma tahririda narxni yo'qotish, bitta mahsulotni ikki
  detalga bog'lash (qoldiq ikki marta), boshqa korxona mahsulotini ko'rish / bog'lash, do'konga ERP nomi / partiya / tannarx berish.
BO'LIMLAR
  S — statik. A — kirish (belgi, rollar, kalit). L — bog'lash (ro'yxat, birlik, bittalik, uzish, jurnal). Q — do'kon «tayyor» API.
  O — buyurtma (ombordan qator, qoldiq, 409, qoplamasiz / bog'lanmagan rad, juft metr). B — band (48 soat, bekor). T — tasdiqlash
  (partiyaga, guruhlar, forma narxi, retsept, yetmasa 409). E — «Tayyor mahsulotlar» sahifasi bandlari. Z — zaxira. K — korxona ajratish.
  P — PG parallel. U — HAQIQIY brauzer.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` (U — faqat SQLite / TF1). `T238_TEZ=1` — U o'tkaziladi.
Asl kodga (zip 237b) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_dokon_tayyor238.py
"""
import os
import io
import sys
import json
import tempfile
import threading
import contextlib
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
TEZ = os.environ.get("T238_TEZ") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "dokon238_test"
_T = tempfile.mkdtemp(prefix="t238_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't238.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, ActivityLog, Order, OrderItem, Inventory, FinishedProduct, StockSource,   # noqa: E402
                    ProductionStatus)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

DokonBuyurtma = getattr(models, "DokonBuyurtma", None)
DokonBuyurtmaQator = getattr(models, "DokonBuyurtmaQator", None)
DokonDetal = getattr(models, "DokonDetal", None)

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


D = Decimal


def pul(x):
    try:
        return D(str(x)).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    except Exception:                      # noqa: BLE001
        return D("NaN")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Muhit: «hozir» — UTC 2026-11-03 07:00 (Toshkent 12:00); Telegram — ushlanadi
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
class _SoxtaVaqt:
    t = datetime(2026, 11, 3, 7, 0)

    @classmethod
    def utcnow(cls):
        return cls.t


if getattr(crud, "_dt233", None) is not None:
    crud._dt233 = _SoxtaVaqt
TG = []


def _tg(msg, *a, **k):
    TG.append((msg, k.get("company_id")))
    return True


main._send_telegram = _tg

s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T238 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t238_admin", PAROL, UserRole.ADMIN, "T238 Admin", company_id=1)
    auth.create_user(s, "t238_plat", PAROL, UserRole.ADMIN, "T238 Platforma", company_id=1)
    auth.create_user(s, "t238_men", PAROL, UserRole.MANAGER, "T238 Menejer", company_id=1)
    auth.create_user(s, "t238_b", PAROL, UserRole.ADMIN, "T238 B Admin", company_id=2)
s.query(User).filter(User.username == "t238_plat").first().is_platform_admin = True
RETSEPT = models.Recipe(company_id=1, name="Qoplama T238")
s.add(RETSEPT)
s.add(Inventory(company_id=1, item_name="Penoplast T238", unit="blok", is_penoplast=True, is_default_penoplast=True,
                volume_per_unit=1.0, price_per_unit=1000000, stock_quantity=50))
s.commit()
RID = RETSEPT.id
PENO = s.query(Inventory.id).filter(Inventory.company_id == 1).scalar()
s.close()
MEN_TAYYOR_K = xavfsiz(lambda d: d.query(User).filter(User.username == "t238_men").first().ruxsat("tayyor", "korish"))


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t238_admin")
CP = mijoz("t238_plat")
CM = mijoz("t238_men")
CB = mijoz("t238_b")
DOK = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
BY = "/api/dokon/v1/buyurtmalar"
TY = "/api/dokon/v1/tayyor"
SB = "/api/sayt-buyurtmalari"
BL = "/api/sayt-bandlar"
KALIT = {"A": None, "B": None}
_kn = [0]


def yangi_kalit():
    _kn[0] += 1
    return f"savat-{_kn[0]:06d}-t238"


def yubor(tana, kalit="auto", dkalit="A"):
    for _ch in ("_DOKON_BUYURTMA_CHEKLOV", "_DOKON_API_CHEKLOV"):
        if hasattr(crud, _ch):
            getattr(crud, _ch).tozala()
    h = {"Content-Type": "application/json", "X-Dokon-Kalit": KALIT.get(dkalit) or "pdk_x"}
    h["X-Amal-Kaliti"] = yangi_kalit() if kalit == "auto" else kalit
    return DOK.post(BY, content=json.dumps(tana).encode("ascii"), headers=h)


def tayyor(dkalit="A"):
    for _ch in ("_DOKON_API_CHEKLOV",):
        if hasattr(crud, _ch):
            getattr(crud, _ch).tozala()
    return DOK.get(TY, headers={"X-Dokon-Kalit": KALIT.get(dkalit) or "pdk_x"})


_tn = [0]


def tana(qatorlar, **kw):
    _tn[0] += 1
    t = {"mijoz": "Vali Aliyev", "telefon": "+998 91 222 33 %02d" % (_tn[0] % 100), "viloyat": "andijon", "qatorlar": qatorlar}
    t.update(kw)
    return t


def fp(nom, q, cat="profil", unit="metr", coat=True, src=StockSource.PRODUCED, st=ProductionStatus.READY, band=0.0, w=15.0, t=10.0,
       brak=None, cid=1):
    def f(d):
        x = FinishedProduct(company_id=cid, name=nom, category=cat, is_coated=coat, width=w, thickness=t, quantity=q,
                            produced_quantity=max(q, 0), unit=unit, unit_price=1, cost_price=max(q, 0) * 1000, unit_cost_stable=1000,
                            source=src, unit_volume_m3=0.01, volume_m3=0.01 * max(q, 0), production_status=st, reserved_quantity=band,
                            brak_taqdir=brak, penoplast_id=PENO if cid == 1 else None)
        d.add(x)
        d.flush()
        return x.id
    return db_ishi(f)


def fpq(*ids):
    return xavfsiz(lambda d: [round(float(d.get(FinishedProduct, i).quantity), 3) for i in ids])


def tmlist(c=None):
    return (js((c or CA).get(API + "/tm-mahsulotlar")).get("mahsulotlar") or [])


def tmk(nom_qismi, c=None):
    return next((x for x in tmlist(c) if nom_qismi in (x.get("nom") or "")), {})


def bogla(did, kalit, c=None):
    return (c or CA).put(API + f"/detallar/{did}/tm", json={"tm_kaliti": kalit})


def qoldiq(did, j=None):
    j = j if j is not None else js(tayyor())
    return next((x.get("qoldiq") for x in (j.get("detallar") or []) if x.get("detal_id") == did), None)


def sb_band(raqam):
    """Sayt buyurtmasining band tugash vaqti (yo'q / asl kodda ustun yo'q — «yo'q»)."""
    return xavfsiz(lambda d: getattr(d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == raqam).first(),
                                     "sb_band_tugash", "yo'q"), "yo'q")


def sb_id(raqam):
    return xavfsiz(lambda d: d.query(DokonBuyurtma.id).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == raqam).scalar(),
                   None) if DokonBuyurtma else None


def sb_soni(cid=1):
    return xavfsiz(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == cid).count(), -1) if DokonBuyurtma else -1


def tasdiqla(sbid, tana_=None, tasdiq=False):
    return CA.post(SB + f"/{sbid}/tasdiqla" + ("?confirm_shortage=true" if tasdiq else ""),
                   json=tana_ if tana_ is not None else {"deadline": "2026-11-20"})


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_yollar = {(m, r.path): r for r in main.app.routes for m in (getattr(r, "methods", None) or ())}
_dy = sorted((m, p) for (m, p) in _yollar if p.startswith("/api/dokon/"))
check("S1 do'kon yo'llari: 3 GET (katalog, sozlamalar, tayyor) + BITTA POST (buyurtmalar); o'chiruvchi / tahrirlovchi yo'l YO'Q",
      _dy == sorted(([("GET", "/api/dokon/v1/galereya")] if hasattr(crud, "dokon_api_galereya") else []) + [("GET", "/api/dokon/v1/katalog"), ("GET", "/api/dokon/v1/sozlamalar"), ("GET", TY), ("POST", BY)] + ([("POST", "/api/dokon/v1/buyurtmalar/pdf"), ("POST", "/api/dokon/v1/savat/pdf")] if hasattr(crud, "sayt_pdf_savat") else [])
             + ([("POST", "/api/dokon/v1/kirish"), ("POST", "/api/dokon/v1/kirish/holat"), ("GET", "/api/dokon/v1/mijoz"), ("POST", "/api/dokon/v1/mijoz/royxat"), ("POST", "/api/dokon/v1/mijoz/chiqish")] if hasattr(crud, "dokon_kirish_boshla") else []) + ([("GET", "/api/dokon/v1/mijoz/buyurtmalar"), ("POST", "/api/dokon/v1/mijoz/buyurtmalar/pdf")] if hasattr(crud, "dokon_mijoz_buyurtmalari") else []) + ([("GET", "/api/dokon/v1/ulgurji"), ("POST", "/api/dokon/v1/ulgurji/buyurtmalar")] if hasattr(crud, "dokon_api_ulgurji") else []) + ([("GET", "/api/dokon/v1/ulgurji/narxlar/pdf"), ("POST", "/api/dokon/v1/ulgurji/savat/pdf")] if hasattr(crud, "ulgurji_narxlar_pdf_malumoti") else []) + ([("GET", "/api/dokon/v1/kutish"), ("POST", "/api/dokon/v1/kutish"), ("POST", "/api/dokon/v1/kutish/bekor")] if hasattr(crud, "dokon_kutish_qosh") else []) + ([("GET", "/api/dokon/v1/mijoz/keshbek")] if hasattr(crud, "dokon_mijoz_keshbek") else []) + ([("GET", "/api/dokon/v1/maxsus-narx")] if hasattr(crud, "dokon_api_maxsus_narx") else [])), _dy)   # kech178 (zip 244): PDF; kech181 (zip 248, MOSLANDI): kirish / mijoz


def _bogliq(m, p):
    r = _yollar.get((m, p))
    if r is None:
        return None
    out = []
    for dp in r.dependant.dependencies:
        t = getattr(dp.call, "ruxsat_talabi", None)
        if t:
            out.append(("ruxsat",) + tuple(t[1][0]))
        elif getattr(dp.call, "__name__", "") == "admin_only":
            out.append(("admin",))
    return out


check("S2 ERP yo'llari: ombor ro'yxati va bog'lash — FAQAT Admin; sahifa bandlari — «Tayyor mahsulotlar: Ko'rish»",
      _bogliq("GET", API + "/tm-mahsulotlar") == [("admin",)] and _bogliq("PUT", API + "/detallar/{detal_id}/tm") == [("admin",)]
      and _bogliq("GET", BL) == [("ruxsat", "tayyor", "korish")],
      (_bogliq("GET", API + "/tm-mahsulotlar"), _bogliq("PUT", API + "/detallar/{detal_id}/tm"), _bogliq("GET", BL)))
check("S3 ustunlar: dokon_detallar.tm_bogl_kaliti, dokon_buyurtmalar.sb_band_tugash, dokon_buyurtma_qatorlari.sbq_tm_kaliti (NULL bo'ladi)",
      DokonDetal is not None and DokonBuyurtma is not None and DokonBuyurtmaQator is not None
      and "tm_bogl_kaliti" in DokonDetal.__table__.c and DokonDetal.__table__.c.tm_bogl_kaliti.nullable
      and "sb_band_tugash" in DokonBuyurtma.__table__.c and DokonBuyurtma.__table__.c.sb_band_tugash.nullable
      and "sbq_tm_kaliti" in DokonBuyurtmaQator.__table__.c and DokonBuyurtmaQator.__table__.c.sbq_tm_kaliti.nullable)
check("S4 kalit sahifasidagi manzillarda «tayyor»; band — 48 soat; tasdiqlash yo'li xomashyo navbatida (partiyadan yechadi)",
      TY in getattr(crud, "DOKON_API_YOLLAR", ()) and getattr(crud, "SAYT_BAND_SOAT", None) == 48
      and ("main", "api_sayt_tasdiqla") in getattr(main, "_XOMASHYO_MARSHRUTLARI", ()))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Kirish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_st = [CA.get(API + "/tm-mahsulotlar").status_code, CA.put(API + "/detallar/1/tm", json={"tm_kaliti": None}).status_code]
_bl = CA.get(BL)
check("A1 belgi o'chiq — ombor ro'yxati / bog'lash 404; sahifa bandlari — bo'sh ro'yxat",
      _st == [404, 404] and _bl.status_code == 200 and js(_bl).get("bandlar") == [], (_st, _bl.status_code, _bl.text[:200]))
r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
check("A0 platforma: korxona 1 da sayt katalogi yoqildi", r.status_code == 200, r.text[:200])
KALIT["A"] = js(CA.post(API + "/api-kalit", json={})).get("kalit")
_r = [DOK.get(TY), DOK.get(TY, headers={"X-Dokon-Kalit": "pdk_" + "a" * 43}), DOK.get(TY, cookies=CA.cookies)]
check("A2 do'kon «tayyor» — kalitsiz / noto'g'ri kalit / faqat cookie — 401", [x.status_code for x in _r] == [401, 401, 401],
      [x.status_code for x in _r])
_st = [CM.get(API + "/tm-mahsulotlar").status_code, CM.put(API + "/detallar/1/tm", json={"tm_kaliti": None}).status_code]
check("A3 menejer (Admin emas) — ombor ro'yxati va bog'lash 403", _st == [403, 403], _st)
check("A4 menejer «Tayyor mahsulotlar» ko'radi — sahifa bandlari 200 (ruxsati bo'lsa)",
      (CM.get(BL).status_code == 200) == bool(MEN_TAYYOR_K), (CM.get(BL).status_code, MEN_TAYYOR_K))

# ── Sinov katalogi ──
K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}
KOMP, KAR, DEK = BOL.get("Rom va eshik dekorlari"), BOL.get("Karnizlar"), BOL.get("Dekor elementlar")


def model(bolim, kod, **kw):
    return js(CA.post(API + "/modellar", json=dict({"bolim_id": bolim, "kod": kod}, **kw))).get("id")


def detal(mid, turi, olcham, **kw):
    return js(CA.post(API + "/detallar", json=dict({"model_id": mid, "turi": turi, "olcham": olcham}, **kw))).get("id")


ORTA = "O'rta"
M1 = model(KOMP, "R-18", nom="Klassik", kapitel_baza_bor=True)
NARX = {"karniz": 15000, "podokonnik": 14000, "nalichnik": 12000, "kapitel": 30000, "baza": 31000}
DID = {t: detal(M1, t, ORTA, narx=n, eni_sm=15, qalinligi_sm=10) for t, n in NARX.items()}
M2 = model(KAR, "K-12", nom="Tekis")
DID["k12"] = detal(M2, "asosiy", "12 sm", narx=45000, narx_qoplamali=98000, eni_sm=12, qalinligi_sm=8)
DID["k14"] = detal(M2, "asosiy", "14 sm", narx=None)                        # narxsiz qator
DID["k10"] = detal(M2, "asosiy", "10 sm", narx=40000, eni_sm=10, qalinligi_sm=8)   # narxli, omborga bog'lanmaydi
M4 = model(DEK, "D-2", nom="Burchak")
DID["d2"] = detal(M4, "asosiy", "S", narx=9900)
M5 = model(DEK, "D-5", nom="Yashirin", yoqilgan=False)
DID["d5"] = detal(M5, "asosiy", "S", narx=9100)
check("A5 katalog: R-18 komplekt (O'rta), K-12 karniz (12 sm, 14 sm narxsiz), D-2 dekor, D-5 yashirin", all(DID.values()), DID)

# ── ERP partiyalari ──
FP = {}
FP["k1"] = fp("Karniz K-12 12 sm", 5, w=12, t=8)                             # ishlab chiqarilgan, qoplamali
FP["k2"] = fp("Karniz  k-12 12 sm", 4, w=12, t=8, band=1.0)                  # o'sha mahsulot (nom bo'shliq / harf), 1 m MRP band
FP["kr"] = fp("Karniz K-12 12 sm", 3, w=12, t=8, src=StockSource.RETURNED)    # qaytgan — o'sha mahsulot, boshqa ERP guruhi
FP["ki"] = fp("Karniz K-12 12 sm", 10, w=12, t=8, st=ProductionStatus.IN_PROGRESS)   # jarayonda — qoldiqqa kirmaydi
FP["kb"] = fp("Karniz K-12 12 sm", 6, w=12, t=8, brak="2_nav")               # 2-nav — kirmaydi
FP["kq"] = fp("Karniz K-12 12 sm", 7, w=12, t=8, coat=False)                 # qoplamasiz — kirmaydi
FP["dn"] = fp("Burchak D-2", 20, cat="dona", unit="dona", w=None, t=None)
FP["pn"] = fp("Panel P-1", 30, cat="panel", unit="metr", w=30, t=4)           # panel — bog'lanmaydi
FP["rk"] = fp("Karniz R-18 15 sm", 12, w=15, t=10)
FP["rp"] = fp("Podokonnik R-18 15 sm", 9, w=15, t=10)
FP["rn"] = fp("Nalichnik R-18 15 sm", 20, w=15, t=10)
FP["rkap"] = fp("Kapitel R-18", 7, cat="dona", unit="dona", w=None, t=None)
FP["rbaz"] = fp("Baza R-18", 9, cat="dona", unit="dona", w=None, t=None)
FP["bk"] = fp("Karniz K-12 12 sm", 50, w=12, t=8, cid=2)                     # B korxonasi
FP["k14"] = fp("Karniz K-12 14 sm", 9, w=14, t=8)
FP["ub"] = fp("Karniz Birlik 12 sm", 8, w=12, t=8, unit="dona")              # profil, lekin birligi dona — mos emas
FP["q1"] = fp("Karniz Qarz 30 sm", 5, w=30, t=8)                              # guruhda qarz: 5 va −2 → bo'sh 3
FP["q2"] = fp("Karniz Qarz 30 sm", -2, w=30, t=8)                            # narxsiz detalga bog'lanadi
FP["kas"] = fp("Karniz KAS 20 sm", 2.5, w=20, t=8)                           # kasr qoldiq (ishlab chiqarilgan)
FP["kasr"] = fp("Karniz KAS 20 sm", 3, w=20, t=8, src=StockSource.RETURNED)  # o'sha mahsulot — qaytgan

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L. Omborga bog'lash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TL = tmlist()
KK = tmk("Karniz K-12")
check("L1 ro'yxat: K-12 karniz — BITTA mahsulot (nom bo'shliq / harfi farqi — bir xil), ERP qoldig'i = 5 + (4 − 1 band) + 3 qaytgan = 11 "
      "(jarayondagi, 2-nav, qoplamasiz — YO'Q), partiyalar 4, birlik metr",
      KK.get("erp_qoldiq") == 11 and KK.get("qoldiq") == 11 and KK.get("sayt_band") == 0 and KK.get("partiyalar") == 4
      and KK.get("birlik") == "metr" and len([x for x in TL if "k-12 12" in " ".join((x.get("nom") or "").lower().split())]) == 1, KK)
check("L2 ro'yxatda panel, qoplamasiz, brak, B korxonasi mahsuloti, birligi turkumiga mos emas (profil — dona) YO'Q; dona mahsulot "
      "(Burchak D-2) — birligi dona; qarzli guruh (5 va −2) — 3",
      not any("Panel" in (x.get("nom") or "") for x in TL) and not tmk("Karniz Birlik") and tmk("Karniz Qarz").get("erp_qoldiq") == 3 and tmk("Burchak").get("birlik") == "dona"
      and tmk("Burchak").get("qoldiq") == 20 and not any((x.get("erp_qoldiq") or 0) >= 50 for x in TL), [x.get("nom") for x in TL])
r = bogla(DID["k12"], KK.get("kalit"))
check("L3 K-12 12 sm detali → «Karniz K-12 12 sm» — 200, detalda kalit, ro'yxatda detal raqami",
      r.status_code == 200 and js(r).get("detal", {}).get("tm_kaliti") == KK.get("kalit")
      and tmk("Karniz K-12").get("detal_id") == DID["k12"], r.text[:300])
_r = [bogla(DID["d2"], KK.get("kalit")), bogla(DID["k14"], KK.get("kalit")), bogla(DID["d2"], "profil||yo'q|metr|1|12|8|"),
      bogla(DID["k14"], 123), bogla(DID["k14"], "x" * 301), CA.put(API + f"/detallar/{DID['k14']}/tm", json={"tm_kaliti": None, "boshqa": 1}),
      bogla(999999, KK.get("kalit"))]
check("L4 rad: dona detal ↔ metr mahsulot (birlik), shu mahsulot ikkinchi detalga (bittalik), yo'q kalit, son, 301 belgi, noma'lum maydon "
      "— 400; yo'q detal — 404",
      [x.status_code for x in _r] == [400, 400, 400, 400, 400, 400, 404]
      and "Birlik" in det(_r[0]) and "boshqa detalga" in det(_r[1]), [(x.status_code, det(x)[:70]) for x in _r])
_l0 = xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == "dokon_detal", ActivityLog.entity_id == DID["k12"]).count(), -1)
r = bogla(DID["k12"], KK.get("kalit"))
_l1 = xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == "dokon_detal", ActivityLog.entity_id == DID["k12"]).count(), -1)
check("L5 o'sha bog'lam qayta — 200, jurnalga yangi yozuv YO'Q", r.status_code == 200 and _l1 == _l0, (_l0, _l1))
r = bogla(DID["k12"], None)
_l2 = xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == "dokon_detal", ActivityLog.entity_id == DID["k12"])
              .order_by(ActivityLog.id.desc()).first().new_value, "")
check("L6 uzish — tm_kaliti null, jurnalda «uzildi»; qayta bog'lash — jurnalda mahsulot nomi",
      r.status_code == 200 and js(r).get("detal", {}).get("tm_kaliti") is None and "uzildi" in (_l2 or ""), (r.text[:200], _l2))
bogla(DID["k12"], KK.get("kalit"))
_l3 = xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == "dokon_detal", ActivityLog.entity_id == DID["k12"])
              .order_by(ActivityLog.id.desc()).first().new_value, "")
check("L7 jurnal: «omborga bog'landi: Karniz …»", "omborga bog'landi" in (_l3 or "") and "Karniz" in (_l3 or ""), _l3)
_kd = next((d for d in (js(CA.get(API)).get("detallar") or []) if d.get("id") == DID["k12"]), {})
check("L8 sahifa katalogida detal bog'lami va ERP mahsulotlari ro'yxati (sayt qoldig'i bilan)",
      _kd.get("tm_kaliti") == KK.get("kalit") and any(x.get("kalit") == KK.get("kalit") for x in js(CA.get(API)).get("tm_mahsulotlar") or [])
      and js(CA.get(API)).get("band_soat") == 48, _kd)
for _t, _nm in (("karniz", "Karniz R-18"), ("podokonnik", "Podokonnik R-18"), ("nalichnik", "Nalichnik R-18"), ("kapitel", "Kapitel R-18"),
                ("baza", "Baza R-18")):
    bogla(DID[_t], tmk(_nm).get("kalit"))
bogla(DID["d2"], tmk("Burchak").get("kalit"))
bogla(DID["d5"], None)
bogla(DID["k14"], tmk("Karniz K-12 14 sm").get("kalit"))         # narxsiz detal — bog'lash mumkin, saytda «tayyor»da chiqmaydi
DID["kas"] = detal(M2, "asosiy", "20 sm", narx=30000, narx_qoplamali=70000, eni_sm=20, qalinligi_sm=8)
bogla(DID["kas"], tmk("Karniz KAS 20 sm").get("kalit"))
check("L9 R-18 komplekt detallari (5 ta), D-2, K-12 14 sm (narxsiz), KAS 20 sm — bog'landi",
      sum(1 for d in (js(CA.get(API)).get("detallar") or []) if d.get("tm_kaliti")) == 9)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Do'kon «tayyor» API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = tayyor()
J = js(r)
_qd = {x.get("detal_id"): x for x in (J.get("detallar") or [])}
check("Q1 «tayyor»: band 48 soat; K-12 12 sm — 11 m; D-2 — 20 dona; R-18 detallari — partiyalar qoldig'i",
      r.status_code == 200 and J.get("band_soat") == 48 and _qd.get(DID["k12"], {}).get("qoldiq") == 11
      and _qd.get(DID["d2"], {}).get("qoldiq") == 20 and _qd.get(DID["karniz"], {}).get("qoldiq") == 12
      and _qd.get(DID["kapitel"], {}).get("qoldiq") == 7, J)
check("Q2 javob tarkibi QAT'IY: detal — {detal_id, model_id, birlik, qoldiq}; ERP nomi / partiya / tannarx / ulgurji YO'Q",
      set(J) == {"versiya", "band_soat", "detallar", "komplektlar"}
      and all(set(x) == {"detal_id", "model_id", "birlik", "qoldiq"} for x in J.get("detallar") or [])
      and "Karniz K-12 12 sm" not in r.text and "partiya" not in r.text and "tannarx" not in r.text and "ulgurji" not in r.text, r.text[:400])
check("Q3 bog'lanmagan (K-12 10 sm), bog'langan lekin narxsiz (K-12 14 sm), yashirin model (D-5) — ro'yxatda YO'Q; KAS — 5,5 m",
      DID["k14"] not in _qd and DID["d5"] not in _qd and DID["k10"] not in _qd and _qd.get(DID["kas"], {}).get("qoldiq") == 5.5,
      (list(_qd), _qd.get(DID["kas"])))
_kmp = {(x.get("komplekt"), x.get("kapitel_baza")): x.get("soni") for x in J.get("komplektlar") or [] if x.get("model_id") == M1}
_ret = crud.dokon_retsept(SessionLocal(), 1)


def _kom(kom, kb):
    q = {"karniz": 12, "podokonnik": 9, "nalichnik": 20, "kapitel": 7, "baza": 9}
    out = []
    for t in crud.DOKON_RETSEPT_TURLARI[kom]:
        if not _ret[kom][t] or (t in ("kapitel", "baza") and not kb):
            continue
        out.append(int(D(q[t]) // D(_ret[kom][t])))
    return min(out)


check("Q4 komplektlar (R-18 O'rta): rom / eshik × kapitel-baza bilan / ularsiz — har detal qoldig'i ÷ retsept, eng kichigi",
      _kmp.get(("rom", True)) == _kom("rom", True) and _kmp.get(("rom", False)) == _kom("rom", False)
      and _kmp.get(("eshik", True)) == _kom("eshik", True) and _kmp.get(("eshik", False)) == _kom("eshik", False),
      (_kmp, _ret))
r2 = DOK.get(TY, headers={"X-Dokon-Kalit": KALIT["A"], "If-None-Match": r.headers.get("etag", "")})
check("Q5 ETag: o'zgarmagan — 304", r2.status_code == 304, r2.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("O. Buyurtma — ombordan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_q0 = xavfsiz(lambda d: [round(float(x.quantity), 3) for x in d.query(FinishedProduct).order_by(FinishedProduct.id).all()])
r = yubor(tana([{"detal_id": DID["k12"], "qoplamali": True, "miqdor": 7, "ombordan": True}]))
J1 = js(r)
check("O1 K-12 12 sm × 7 m ombordan (toq metr — juft talabi yo'q) — 200, narx — qoplamali katalog narxi (98 000), jami 686 000",
      r.status_code == 200 and pul(J1.get("jami")) == pul(98000 * 7)
      and (J1.get("guruhlar") or [{}])[0].get("detallar", [{}])[0].get("ombordan") is True, r.text[:400])
check("O2 band: tugash = yaratilgan + 48 soat (UTC, «Z»); javobda band matni (Toshkent vaqti 05.11.2026 12:00)",
      lambda: sb_band(J1.get("raqam")) == datetime(2026, 11, 5, 7, 0) and J1.get("band_tugash") == "2026-11-05T07:00:00Z"
      and "05.11.2026 12:00" in (J1.get("band_matni") or ""), (J1.get("band_tugash"), J1.get("band_matni")))
_q1 = xavfsiz(lambda d: [round(float(x.quantity), 3) for x in d.query(FinishedProduct).order_by(FinishedProduct.id).all()])
check("O3 ERP partiyalari O'ZGARMADI (band faqat saytdagi qoldiqdan); saytda K-12 — 11 − 7 = 4 m", _q1 == _q0 and qoldiq(DID["k12"]) == 4,
      (_q0, _q1, qoldiq(DID["k12"])))
_n0 = sb_soni()
r = yubor(tana([{"detal_id": DID["k12"], "qoplamali": True, "miqdor": 5, "ombordan": True}]))
_y = (js(r).get("detail") or {}) if isinstance(js(r).get("detail"), dict) else {}
check("O4 ikkinchi mijoz 5 m (bor — 4) — 409 «omborda yetmaydi» (bor 4, so'ralgan 5, detal raqami), hech narsa yozilmaydi",
      r.status_code == 409 and _y.get("ombor_yetmaydi") is True and (_y.get("yetmaydi") or [{}])[0].get("bor") == 4
      and (_y.get("yetmaydi") or [{}])[0].get("kerak") == 5 and (_y.get("yetmaydi") or [{}])[0].get("detal_idlar") == [DID["k12"]]
      and sb_soni() == _n0, r.text[:400])
r = yubor(tana([{"detal_id": DID["k12"], "qoplamali": True, "miqdor": 4, "ombordan": True}]))
J2 = js(r)
check("O5 4 m — 200; saytda K-12 — 0", r.status_code == 200 and qoldiq(DID["k12"]) == 0, (r.status_code, r.text[:200], qoldiq(DID["k12"])))
_r = [yubor(tana([{"detal_id": DID["k12"], "qoplamali": False, "miqdor": 1, "ombordan": True}])),
      yubor(tana([{"detal_id": DID["k10"], "qoplamali": True, "miqdor": 2, "ombordan": True}])),
      yubor(tana([{"detal_id": DID["d2"], "qoplamali": True, "miqdor": 1.5, "ombordan": True}])),
      yubor(tana([{"detal_id": DID["d2"], "qoplamali": True, "miqdor": 1, "ombordan": "ha"}])),
      yubor(tana([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "soni": 1, "ombordan": True}])),
      yubor(tana([{"detal_id": DID["d2"], "qoplamali": True, "miqdor": 1, "ombordan": True, "x": 1}]))]
check("O6 rad (400): ombordan qoplamasiz, bog'lanmagan detal, 1,5 dona, «ombordan» matn, qoplamasiz komplekt ombordan, noma'lum maydon",
      [x.status_code for x in _r] == [400] * 6 and "qoplamali" in det(_r[0]) and "omborda yo'q" in det(_r[1]),
      [(x.status_code, det(x)[:70]) for x in _r])
r = yubor(tana([{"detal_id": DID["k12"], "qoplamali": True, "miqdor": 3}]))
check("O7 o'sha detal ombordan EMAS (buyurtmaga tayyorlanadi) — omborga qaramaydi, juft metr talabi o'z kuchida (3 m — 400)",
      r.status_code == 400 and "juft" in det(r), (r.status_code, det(r)[:120]))
r = yubor(tana([{"detal_id": DID["k12"], "qoplamali": True, "miqdor": 30}]))
check("O8 buyurtmaga tayyorlanadigani (ombordan emas) 30 m — 200, band YO'Q (sb_band_tugash NULL)",
      r.status_code == 200 and sb_band(js(r).get("raqam")) is None, r.text[:200])
_kal = yangi_kalit()
_t = tana([{"detal_id": DID["d2"], "qoplamali": True, "miqdor": 3, "ombordan": True}])
r1, r2 = yubor(_t, kalit=_kal), yubor(_t, kalit=_kal)
check("O9 takror (o'sha kalit, o'sha savat) — o'sha raqam, X-Takror; band IKKI marta ayirilmaydi (D-2 — 20 − 3 = 17)",
      r1.status_code == 200 and r2.status_code == 200 and js(r1).get("raqam") == js(r2).get("raqam") and r2.headers.get("x-takror") == "1"
      and qoldiq(DID["d2"]) == 17, (r1.text[:100], r2.text[:100], qoldiq(DID["d2"])))
r = yubor(dict(_t, qatorlar=[{"detal_id": DID["d2"], "qoplamali": True, "miqdor": 3}]), kalit=_kal)
check("O10 o'sha kalit + «ombordan»siz savat — 409 (boshqa savat)", r.status_code == 409, r.status_code)
J0 = js(tayyor())
_kmp0 = {(x.get("komplekt"), x.get("kapitel_baza")): x.get("soni") for x in J0.get("komplektlar") or [] if x.get("model_id") == M1}
r = yubor(tana([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": True, "soni": 2, "ombordan": True}]))
JK = js(r)
_g = (JK.get("guruhlar") or [{}])[0]
check("O11 R-18 rom komplekti × 2 ombordan — 200, bitta guruh («…, ombordan × 2»), hamma detal «ombordan», qoldiq retsept × 2 ga kamaydi",
      r.status_code == 200 and ", ombordan × 2" in (_g.get("guruh_nomi") or "") and all(x.get("ombordan") for x in _g.get("detallar") or [])
      and qoldiq(DID["karniz"]) == 12 - 2 * int(_ret["rom"]["karniz"]), (r.text[:300], qoldiq(DID["karniz"])))
J0b = js(tayyor())
_kmp1 = {(x.get("komplekt"), x.get("kapitel_baza")): x.get("soni") for x in J0b.get("komplektlar") or [] if x.get("model_id") == M1}
check("O12 komplektlar soni yangi qoldiqdan qayta hisoblandi (rom bilan: avvalgidan kam)",
      (_kmp1.get(("rom", True)) or 0) < (_kmp0.get(("rom", True)) or 0), (_kmp0, _kmp1))
r = yubor(tana([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": True, "soni": (_kmp1.get(("rom", True)) or 0) + 1,
                 "ombordan": True}]))
check("O13 komplekt soni qoldiqdan 1 ta ko'p — 409 «omborda yetmaydi»", r.status_code == 409 and "Omborda yetmaydi" in r.text, r.text[:300])
_tg = [m for m, c in TG if "Ombordan" in m]
check("O14 Telegram: ombordan buyurtmada «🏭 Ombordan — 48 soat band: 05.11.2026 12:00 gacha»",
      any("🏭 Ombordan — 48 soat band: 05.11.2026 12:00 gacha" in m for m in _tg), TG[-1:])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Band — 48 soat, bekor")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_v = js(CA.get(SB + f"/{sb_id(J1.get('raqam'))}"))
check("B1 ERP sahifasi: band faol, tugash vaqti, «ombordan» ogohlantirishi, qoplama retsepti SHART EMAS (faqat ombordan)",
      _v.get("band_faol") is True and _v.get("band_tugash") == "2026-11-05T07:00:00" and _v.get("ombordan_bor") is True
      and _v.get("qoplamali_bor") is False and any("Ombordan" in x for x in _v.get("ogohlantirishlar") or []), _v)
r = CA.post(SB + f"/{sb_id(J2.get('raqam'))}/bekor", json={"sabab": "mijoz rad etdi"})
check("B2 bekor qilindi — band DARHOL bo'shadi (K-12: 0 → 4)", r.status_code == 200 and qoldiq(DID["k12"]) == 4, (r.status_code, qoldiq(DID["k12"])))
_SoxtaVaqt.t = datetime(2026, 11, 5, 6, 59)
_q59 = qoldiq(DID["k12"])
_SoxtaVaqt.t = datetime(2026, 11, 5, 7, 0)
_q60 = qoldiq(DID["k12"])
check("B3 48 soat: 06:59 da hali band (4), 07:00 da bo'shadi (11) — fon vazifasisiz", _q59 == 4 and _q60 == 11, (_q59, _q60))
_v = js(CA.get(SB + f"/{sb_id(J1.get('raqam'))}"))
check("B4 muddati o'tgan band: band_faol false, ogohlantirish «Band muddati o'tgan», holat hali «yangi»",
      _v.get("band_faol") is False and _v.get("holat") == "yangi" and any("Band muddati o'tgan" in x for x in _v.get("ogohlantirishlar") or []),
      _v)
_SoxtaVaqt.t = datetime(2026, 11, 3, 8, 0)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. «Tayyor mahsulotlar» sahifasi bandlari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bl = js(CA.get(BL)).get("bandlar") or []
_bk = next((x for x in _bl if FP["k1"] in (x.get("fp_idlar") or [])), {})
check("E1 K-12 bandi: partiyalar (ishlab chiqarilgan, MRP bandli, qaytgan, jarayondagi — saytga mos HAMMASI; 2-nav / qoplamasiz — yo'q), "
      "miqdor 7, sayt raqami",
      sorted(_bk.get("fp_idlar") or []) == sorted([FP["k1"], FP["k2"], FP["kr"], FP["ki"]]) and _bk.get("miqdor") == 7
      and _bk.get("raqamlar") == [J1.get("raqam")], _bl)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Tasdiqlash — partiyadan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_q0 = fpq(FP["k1"], FP["k2"], FP["kr"], FP["ki"], FP["kb"], FP["kq"])
_inv0 = xavfsiz(lambda d: float(d.get(Inventory, PENO).stock_quantity))
r = tasdiqla(sb_id(J1.get("raqam")))
_o = js(r)
_oi = xavfsiz(lambda d: [(i.name, i.category, float(i.length or 0), float(i.quantity), float(i.unit_price), float(i.total_price),
                          i.finished_product_id, bool(i.is_coated))
                         for i in d.query(OrderItem).filter(OrderItem.order_id == _o.get("order_id")).order_by(OrderItem.id).all()], [])
_q1 = fpq(FP["k1"], FP["k2"], FP["kr"], FP["ki"], FP["kb"], FP["kq"])
check("T1 retseptsiz tasdiq (faqat ombordan) — 200; 7 m: ishlab chiqarilgan guruh (bo'sh 8) — 7 m (bitta qator, profil, soni 1, narx = jami "
      "686 000), partiya qaytgani tegilmaydi",
      r.status_code == 200 and len(_oi) == 1 and _oi[0][1] == "profil" and _oi[0][2] == 7 and _oi[0][3] == 1
      and pul(_oi[0][4]) == pul(686000) and _oi[0][6] in (FP["k1"], FP["k2"]) and _oi[0][7], (r.text[:300], _oi))
check("T2 ERP partiyalari: ishlab chiqarilgan guruhdan 7 m (5 + 4 → jami 2, band 1 o'z joyida), qaytgan / jarayondagi / 2-nav / qoplamasiz "
      "o'zgarmadi; penoplast yechilmadi",
      round(_q1[0] + _q1[1], 3) == round(_q0[0] + _q0[1] - 7, 3) and _q1[2:] == _q0[2:] and _q1[1] >= 1
      and xavfsiz(lambda d: float(d.get(Inventory, PENO).stock_quantity)) == _inv0, (_q0, _q1))
_eo = js(CA.get(f"/api/orders/{_o.get('order_id')}"))
_ei = (_eo.get("items") or [{}])[0]
check("T3 forma tahriri: saqlangan 1 m narxi (`tmSaqlanganBirlikNarxi` = narx × soni ÷ uzunlik) = 98 000 AYNAN; agreed = jami",
      pul(float(_ei.get("unit_price") or 0) * float(_ei.get("quantity") or 0) / float(_ei.get("length") or 1)) == pul(98000)
      and pul(_eo.get("agreed_amount")) == pul(686000) and pul(_eo.get("total_amount")) == pul(686000), _ei)
# 9 m: ishlab chiqarilgan guruhda 2 − 1 band = 1 bo'sh, qaytgan — 3 → 3 + 1 … yetmaydi (4) → 409; tasdiq bilan — minus
r = yubor(tana([{"detal_id": DID["k12"], "qoplamali": True, "miqdor": 4, "ombordan": True}]))
J3 = js(r)
_q0 = fpq(FP["k1"], FP["k2"], FP["kr"])
r = tasdiqla(sb_id(J3.get("raqam")))
_oi = xavfsiz(lambda d: [(float(i.length or 0), i.finished_product_id, float(i.unit_price))
                         for i in d.query(OrderItem).filter(OrderItem.order_id == js(r).get("order_id")).order_by(OrderItem.id).all()], [])
_q1 = fpq(FP["k1"], FP["k2"], FP["kr"])
check("T4 4 m (ishlab chiqarilgan bo'sh 1, qaytgan 3): ikki qator — qaytgan guruhdan 3 m, ishlab chiqarilgandan 1 m; summa 392 000 AYNAN "
      "taqsimlandi",
      r.status_code == 200 and sorted((x[0], x[1] == FP["kr"]) for x in _oi) == [(1.0, False), (3.0, True)]
      and pul(sum(x[2] for x in _oi)) == pul(98000 * 4) and _q1[2] == 0 and round(_q1[0] + _q1[1], 3) == round(_q0[0] + _q0[1] - 1, 3),
      (r.status_code, r.text[:300], _oi, _q0, _q1))
r = yubor(tana([{"detal_id": DID["d2"], "qoplamali": True, "miqdor": 2, "ombordan": True},
                {"detal_id": DID["k12"], "qoplamali": True, "miqdor": 2}]))
J4 = js(r)
r1 = tasdiqla(sb_id(J4.get("raqam")))
r2 = tasdiqla(sb_id(J4.get("raqam")), {"deadline": "2026-11-20", "recipe_id": RID})
_oi = xavfsiz(lambda d: [(i.category, i.finished_product_id, float(i.quantity), float(i.unit_price))
                         for i in d.query(OrderItem).filter(OrderItem.order_id == js(r2).get("order_id")).order_by(OrderItem.id).all()], [])
check("T5 aralash (D-2 ombordan + K-12 buyurtmaga): retseptsiz — 400 (qoplamali tayyorlanadigan qator bor), retsept bilan — 200; D-2 — dona "
      "qatori partiyadan (2 × qoplamali narx), K-12 — oddiy profil (partiyasiz)",
      r1.status_code == 400 and r2.status_code == 200 and _oi
      and _oi[0] == ("dona", FP["dn"], 2.0, float((J4.get("guruhlar") or [{}])[0].get("detallar", [{}])[0].get("narx") or -1))
      and _oi[1][0] == "profil" and _oi[1][1] is None, (r1.status_code, det(r1)[:80], r2.status_code, _oi))
r = yubor(tana([{"detal_id": DID["d2"], "qoplamali": True, "miqdor": 1, "ombordan": True}]))
J5 = js(r)
db_ishi(lambda d: setattr(d.get(FinishedProduct, FP["dn"]), "name", "Burchak D-2 (yangi nom)"))
_n0 = xavfsiz(lambda d: d.query(Order).count())
r = tasdiqla(sb_id(J5.get("raqam")))
check("T6 ERP mahsuloti nomi o'zgargan (kalit mos emas) — 400 «topilmadi … qayta bog'lang», buyurtma / loyiha OCHILMADI, holat «yangi»",
      r.status_code == 400 and "topilmadi" in det(r) and xavfsiz(lambda d: d.query(Order).count()) == _n0
      and js(CA.get(SB + f"/{sb_id(J5.get('raqam'))}")).get("holat") == "yangi", (r.status_code, det(r)[:200]))
db_ishi(lambda d: setattr(d.get(FinishedProduct, FP["dn"]), "name", "Burchak D-2"))
# ERP o'zi sotib qo'ygan (band — faqat sayt ichida) → tasdiqda 409 «davom etasizmi?», tasdiq bilan — minus
r = yubor(tana([{"detal_id": DID["karniz"], "qoplamali": True, "miqdor": 2, "ombordan": True}]))
J6 = js(r)
db_ishi(lambda d: setattr(d.get(FinishedProduct, FP["rk"]), "quantity", 1.0))
r1 = tasdiqla(sb_id(J6.get("raqam")))
r2 = tasdiqla(sb_id(J6.get("raqam")), tasdiq=True)
check("T7 partiya ERP da sotilgan (qoldiq 1, kerak 2): 409 stock_shortage_warning (hech narsa yozilmaydi), «davom etish» bilan — 200, minus −1",
      r1.status_code == 409 and (js(r1).get("detail") or {}).get("type") == "stock_shortage_warning" and r2.status_code == 200
      and fpq(FP["rk"]) == [-1.0], (r1.status_code, r1.text[:200], r2.status_code, fpq(FP["rk"])))
r = tasdiqla(sb_id(J6.get("raqam")), tasdiq=True)
check("T8 qayta tasdiq — 409 (ikkinchi buyurtma ochilmaydi)", r.status_code == 409, r.status_code)

r = yubor(tana([{"detal_id": DID["kas"], "qoplamali": True, "miqdor": 5, "ombordan": True}]))
r = tasdiqla(sb_id(js(r).get("raqam")))
_oi = xavfsiz(lambda d: sorted((float(i.length or 0), i.finished_product_id) for i in d.query(OrderItem)
                               .filter(OrderItem.order_id == js(r).get("order_id")).all()), [])
check("T9 kasr qoldiq (ishlab chiqarilgan 2,5 m + qaytgan 3 m), kerak 5 m — qismlar BUTUN metr: qaytgan 3 + ishlab chiqarilgan 2; partiyalar "
      "0,5 va 0", r.status_code == 200 and _oi == [(2.0, FP["kas"]), (3.0, FP["kasr"])] and fpq(FP["kas"], FP["kasr"]) == [0.5, 0.0],
      (r.status_code, r.text[:200], _oi, fpq(FP["kas"], FP["kasr"])))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. review238 — topilmalar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# H1: kasr qoldiq — 2,5 (ishlab chiqarilgan) + 2,5 (qaytgan); saytda 5 m; tasdiqda «yetmaydi» (409) va minus bo'lmasin
_ha = fp("Karniz H1 22 sm", 2.5, w=22, t=8)
_hb = fp("Karniz H1 22 sm", 2.5, w=22, t=8, src=StockSource.RETURNED)
_dh1 = detal(M2, "asosiy", "22 sm", narx=30000, narx_qoplamali=70000, eni_sm=22, qalinligi_sm=8)
bogla(_dh1, tmk("Karniz H1 22").get("kalit"))
r = yubor(tana([{"detal_id": _dh1, "qoplamali": True, "miqdor": 5, "ombordan": True}]))
_hr = js(r).get("raqam")
r = tasdiqla(sb_id(_hr))
_oi = xavfsiz(lambda d: sorted((float(i.length or 0), i.finished_product_id, float(i.unit_price)) for i in d.query(OrderItem)
                               .filter(OrderItem.order_id == js(r).get("order_id")).all()), [])
check("R1 (H1) 2,5 + 2,5 m, kerak 5 m — tasdiq 200 (soxta «yetmaydi» YO'Q), qismlar 2,5 + 2,5 (summa AYNAN 350 000), partiyalar 0 / 0 (minus yo'q)",
      r.status_code == 200 and [(x[0], x[1]) for x in _oi] == sorted([(2.5, _ha), (2.5, _hb)]) and pul(sum(x[2] for x in _oi)) == pul(350000)
      and fpq(_ha, _hb) == [0.0, 0.0], (r.status_code, r.text[:200], _oi, fpq(_ha, _hb)))
# M2: model qolipi «dona» ga o'zgarsa — metrli mahsulot bog'lami ishlamaydi (do'konda yo'q, ombordan buyurtma — 400, sahifada ogohlantirish)
_mq = model(KAR, "Q-1", nom="Qolip")
_dq = detal(_mq, "asosiy", "18 sm", narx=20000, narx_qoplamali=45000, eni_sm=18, qalinligi_sm=8)
fp("Karniz Q-1 18 sm", 10, w=18, t=8)
bogla(_dq, tmk("Karniz Q-1").get("kalit"))
_v0 = qoldiq(_dq)
r0 = CA.put(API + f"/modellar/{_mq}", json={"qolip": "dona"})
_dd = next((d for d in (js(CA.get(API)).get("detallar") or []) if d.get("id") == _dq), {})
r = yubor(tana([{"detal_id": _dq, "qoplamali": True, "miqdor": 3, "ombordan": True}]))
check("R2 (M2) qolip «dona» ga o'zgardi — «tayyor»da detal YO'Q, ombordan buyurtma 400, katalogda tm_mos=false (kalit saqlangan — uzish mumkin)",
      _v0 == 10 and r0.status_code == 200 and qoldiq(_dq) is None and r.status_code == 400 and _dd.get("birlik") == "dona"
      and _dd.get("tm_mos") is False and bool(_dd.get("tm_kaliti")), (_v0, r0.status_code, r0.text[:150], qoldiq(_dq), r.status_code, _dd))
CA.put(API + f"/modellar/{_mq}", json={"qolip": "butun_metr"})
check("R3 (M2) qolip qaytdi — bog'lam yana ishlaydi (10 m)", qoldiq(_dq) == 10, qoldiq(_dq))
# M3: A buyurtma bandi muddati o'tgan, B shu mahsulotni band qilgan — A tasdig'i avval so'raladi
_SoxtaVaqt.t = datetime(2026, 11, 3, 8, 0)
_dm3 = detal(M2, "asosiy", "24 sm", narx=30000, narx_qoplamali=70000, eni_sm=24, qalinligi_sm=8)
_fm3 = fp("Karniz M3 24 sm", 5, w=24, t=8)
bogla(_dm3, tmk("Karniz M3 24").get("kalit"))
_ra = js(yubor(tana([{"detal_id": _dm3, "qoplamali": True, "miqdor": 5, "ombordan": True}]))).get("raqam")
_SoxtaVaqt.t = datetime(2026, 11, 5, 9, 0)                    # A bandi tugadi
_rb = js(yubor(tana([{"detal_id": _dm3, "qoplamali": True, "miqdor": 5, "ombordan": True}]))).get("raqam")
_n0 = xavfsiz(lambda d: d.query(Order).count())
r1 = tasdiqla(sb_id(_ra))
_d1 = js(r1).get("detail") if isinstance(js(r1).get("detail"), dict) else {}
check("R4 (M3) bandi o'tgan A — boshqa mijoz (B) bandiga tegadi: 409 «davom etasizmi?» (band muddati o'tgan), hech narsa yozilmaydi",
      bool(_ra) and bool(_rb) and r1.status_code == 409 and _d1.get("type") == "stock_shortage_warning"
      and "band muddati o'tgan" in " ".join(_d1.get("shortages") or []) and xavfsiz(lambda d: d.query(Order).count()) == _n0,
      (_ra, _rb, r1.status_code, r1.text[:300]))
r2 = tasdiqla(sb_id(_ra), tasdiq=True)
check("R5 (M3) «davom etish» bilan — 200 (xodim qarori)", r2.status_code == 200 and fpq(_fm3) == [0.0], (r2.status_code, r2.text[:200], fpq(_fm3)))
r3 = tasdiqla(sb_id(_rb))
check("R6 bandi FAOL B ni tasdiqlash — band tekshiruvi yo'q, ERP o'zi: 409 (omborda 0)",
      r3.status_code == 409 and "Band muddati" not in r3.text, (r3.status_code, r3.text[:200]))
# bir mahsulot bir buyurtmada IKKI qatorda (3 + 3): ishlab chiqarilgan 3 va qaytgan 3 — har qator boshqa guruhdan (ishlatilgani ayiriladi)
_SoxtaVaqt.t = datetime(2026, 11, 5, 9, 10)
_dr8 = detal(M2, "asosiy", "26 sm", narx=30000, narx_qoplamali=70000, eni_sm=26, qalinligi_sm=8)
_fr8a = fp("Karniz R8 26 sm", 3, w=26, t=8)
_fr8b = fp("Karniz R8 26 sm", 3, w=26, t=8, src=StockSource.RETURNED)
bogla(_dr8, tmk("Karniz R8 26").get("kalit"))
r = yubor(tana([{"detal_id": _dr8, "qoplamali": True, "miqdor": 3, "ombordan": True},
                {"detal_id": _dr8, "qoplamali": True, "miqdor": 3, "ombordan": True}]))
r = tasdiqla(sb_id(js(r).get("raqam")))
check("R8 bir mahsulot ikki qatorda (3 + 3; ishlab chiqarilgan 3, qaytgan 3) — tasdiq 200 «yetmaydi»siz, har guruhdan 3, partiyalar 0 / 0",
      r.status_code == 200 and fpq(_fr8a, _fr8b) == [0.0, 0.0], (r.status_code, r.text[:200], fpq(_fr8a, _fr8b)))
# L1: takror javob — bekor qilingan buyurtmada «band qilindi» matni yo'q
_SoxtaVaqt.t = datetime(2026, 11, 5, 9, 30)
_kl = yangi_kalit()
_tl = tana([{"detal_id": DID["d2"], "qoplamali": True, "miqdor": 1, "ombordan": True}])
_j1 = js(yubor(_tl, kalit=_kl))
CA.post(SB + f"/{sb_id(_j1.get('raqam'))}/bekor", json={})
_j2 = js(yubor(_tl, kalit=_kl))
check("R7 (L1) takror: birinchi javobda band matni bor, bekor qilingandan keyingi takrorda — YO'Q (holat «bekor»)",
      bool(_j1.get("band_matni")) and _j2.get("raqam") == _j1.get("raqam") and _j2.get("band_matni") is None and _j2.get("holat") == "bekor",
      (_j1.get("band_matni"), _j2))
_SoxtaVaqt.t = datetime(2026, 11, 3, 8, 0)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_d0 = xavfsiz(lambda d: sorted((x.id, x.tm_bogl_kaliti) for x in d.query(DokonDetal).filter(DokonDetal.company_id == 1).all()))
_b0 = xavfsiz(lambda d: sorted((x.id, x.sb_band_tugash) for x in d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == 1).all()))
_zx = db_ishi(lambda d: crud.export_full_backup(d, 1))
try:
    db_ishi(lambda d: crud.import_full_backup(d, _zx, 1, replace=True))
    _tx = None
except Exception as e:                      # noqa: BLE001
    _tx = f"{type(e).__name__}: {e}"
_d1 = xavfsiz(lambda d: sorted((x.id, x.tm_bogl_kaliti) for x in d.query(DokonDetal).filter(DokonDetal.company_id == 1).all()))
_b1 = xavfsiz(lambda d: sorted((x.id, x.sb_band_tugash) for x in d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == 1).all()))
check("Z1 zaxira → tiklash: detal bog'lamlari va band muddatlari AYNAN", _tx is None and _d1 == _d0 and _b1 == _b0 and bool(_d0),
      lambda: (_tx, (_d0 or [])[:3], (_d1 or [])[:3]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Korxona ajratish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", True))
KALIT["B"] = js(CB.post(API + "/api-kalit", json={})).get("kalit")
_bbol = js(CB.post(API + "/bolimlar", json={"nom": "B karniz", "qolip": "butun_metr"})).get("id")
_bm = js(CB.post(API + "/modellar", json={"bolim_id": _bbol, "kod": "BK-1"})).get("id")
_bd = js(CB.post(API + "/detallar", json={"model_id": _bm, "turi": "asosiy", "olcham": "12", "narx": 5000})).get("id")
_btl = tmlist(CB)
check("K1 B korxonasi ro'yxatida faqat B partiyasi (50 m); A ro'yxatida u yo'q",
      len(_btl) == 1 and _btl[0].get("erp_qoldiq") == 50 and not any(x.get("erp_qoldiq") == 50 for x in tmlist()), _btl)
_r = [bogla(_bd, KK.get("kalit"), CB).status_code, bogla(DID["k12"], None, CB).status_code, CA.put(API + f"/detallar/{_bd}/tm",
                                                                                                   json={"tm_kaliti": None}).status_code]
check("K2 B admin A detaliga / A admin B detaliga — 404; B o'z detalini A mahsuloti kaliti bilan (B da u yo'q, kalit matni bir xil) — "
      "B ning o'z partiyasiga bog'lanadi", _r[1:] == [404, 404], _r)
r = bogla(_bd, _btl[0].get("kalit") if _btl else None, CB)
_ty = js(tayyor("B"))
check("K3 B «tayyor» — faqat B detali (50 m); A «tayyor» B detalini ko'rmaydi",
      r.status_code == 200 and [x.get("qoldiq") for x in _ty.get("detallar") or []] == [50]
      and not any(x.get("detal_id") == _bd for x in js(tayyor()).get("detallar") or []), (r.text[:200], _ty))
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", False))
check("K4 B da do'kon o'chirildi — «tayyor» 404", tayyor("B").status_code == 404, tayyor("B").status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PG parallel")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    _nom = "Karniz PG238"
    _fid = fp(_nom, 5, w=20, t=10)
    _md = model(KAR, "PG-1", nom="Parallel")
    _dd = detal(_md, "asosiy", "20 sm", narx=10000, eni_sm=20, qalinligi_sm=10)
    bogla(_dd, tmk(_nom).get("kalit"))
    _nat = []
    _bar = threading.Barrier(4)

    def _ish():
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
        t = json.dumps(tana([{"detal_id": _dd, "qoplamali": True, "miqdor": 3, "ombordan": True}])).encode("ascii")
        h = {"Content-Type": "application/json", "X-Dokon-Kalit": KALIT["A"], "X-Amal-Kaliti": yangi_kalit()}
        _bar.wait()
        _r = c.post(BY, content=t, headers=h)
        _nat.append(_r.status_code if _r.status_code != 409 or "ombor_yetmaydi" in _r.text else -409)
    crud._DOKON_BUYURTMA_CHEKLOV.tozala()
    _th = [threading.Thread(target=_ish) for _ in range(4)]
    [x.start() for x in _th]
    [x.join(60) for x in _th]
    check("P1 4 mijoz bir vaqtda 3 m dan (omborda 5): FAQAT bittasi 200, qolganlari 409; saytda 2 m",
          sorted(_nat) == [200, 409, 409, 409] and qoldiq(_dd) == 2, (_nat, qoldiq(_dd)))
else:
    print("  (PG emas — P o'tkazildi)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL or TEZ:
    print("  (U — PG / T238_TEZ da o'tkaziladi)")
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
    from datetime import timezone as _tz238
    # kech191 (zip 258): VAQT BOMBASI tuzatildi — oldingi bo'limlar soxta soatda (2026-11-03 08:00) band yaratgan (48 soat → 2026-11-05
    # 08:00 UTC gacha); haqiqiy soat undan o'tgach (05.11 13:00 Toshkent dan) U7 dagi «Kapitel R-18» bandi tugagan bo'lib yiqilardi. Endi
    # haqiqiy soatga o'tishda hamma band muddatlari xuddi shu farqqa suriladi — bandlar holati soxta soatdagidek qoladi, sana qanday bo'lmasin.
    _hozir238 = datetime.now(_tz238.utc).replace(tzinfo=None)
    _siljish238 = _hozir238 - _SoxtaVaqt.t

    def _bandlarni_surish238(d):
        for _x in d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_band_tugash.isnot(None)).all():
            _x.sb_band_tugash = _x.sb_band_tugash + _siljish238
    db_ishi(_bandlarni_surish238)
    _SoxtaVaqt.t = _hozir238   # brauzer — haqiqiy soat (band «gacha» vaqti sahifada ko'rinadi)
    _f16 = fp("Karniz K-12 16 sm <i>x</i>", 8, w=16, t=8)     # nomida HTML — sahifada MATN bo'lib chiqishi kerak
    _d16 = detal(M2, "asosiy", "16 sm", narx=60000, eni_sm=16, qalinligi_sm=8)
    fp("Burchak D-2", 5, cat="dona", unit="dona", w=None, t=None)       # D-2 — endi 2 partiyali guruh («Tayyor mahsulotlar» guruh qatori)
    _ru = yubor(tana([{"detal_id": DID["d2"], "qoplamali": True, "miqdor": 2, "ombordan": True}]))
    _uraqam = js(_ru).get("raqam")
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1366, "height": 900})
            pg = ctx.new_page()
            JSX = []
            pg.on("pageerror", lambda e: JSX.append(str(e)))
            pg.on("dialog", lambda d: d.dismiss())
            pg.goto(BASE + "/login")
            pg.fill("input[name=username]", "t238_admin")
            pg.fill("input[name=password]", PAROL)
            pg.click("button[type=submit]")
            pg.wait_for_load_state("networkidle")
            pg.goto(BASE + "/sayt-katalogi")
            pg.wait_for_selector(".sk-bolim", timeout=30000)
            pg.click(f".sk-bolim[data-id='{KAR}']")
            pg.wait_for_selector(f"[data-och='{M2}']", timeout=10000)
            pg.click(f"[data-och='{M2}']")
            _tm12 = pg.locator(f"[data-tm='{DID['k12']}']")
            check("U1 K-12 12 sm qatorida «🏭 Karniz K-12 12 sm · saytda … m», «O'zgartirish» / «Uzish»",
                  "Karniz K-12 12 sm" in (_tm12.inner_text() or "") and "saytda" in (_tm12.inner_text() or "")
                  and _tm12.locator("[data-tmuz]").count() == 1, _tm12.inner_text())
            pg.click(f"[data-tm='{_d16}'] [data-tmbog]")
            pg.wait_for_selector("#skTmOyna.ko", timeout=10000)
            pg.wait_for_timeout(300)
            _txt = pg.inner_text("#skTmRoyxat")
            check("U2 oyna: faqat metrli mahsulotlar (dona — yo'q), K-12 12 sm — «boshqa detalga bog'langan» (tanlab bo'lmaydi), nomdagi HTML — "
                  "MATN", "Karniz K-12 16 sm <i>x</i>" in _txt and "Burchak" not in _txt and "boshqa detalga" in _txt
                  and pg.locator("#skTmRoyxat i").count() == 0
                  and pg.locator("#skTmRoyxat .sk-tm-tanlov[disabled]").count() >= 1, _txt[:400])
            pg.fill("#skTmQidir", "16 sm")
            _n = pg.locator("#skTmRoyxat .sk-tm-tanlov").count()
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(300)
            check("U3 qidiruv — 1 ta; Esc — oyna yopiladi (data-yopish)", _n == 1 and pg.locator("#skTmOyna.ko").count() == 0, _n)
            pg.fill(f"tr[data-detal='{DID['k12']}'] input[data-df='olcham']", "12 sm")   # yozilgan narx katagi saqlanib qolishini tekshirish
            pg.fill(f"tr[data-detal='{_d16}'] input[data-df='narx_qoplamali']", "123456")
            pg.click(f"[data-tm='{_d16}'] [data-tmbog]")
            pg.wait_for_selector("#skTmOyna.ko", timeout=10000)
            pg.wait_for_timeout(300)
            pg.click("#skTmRoyxat .sk-tm-tanlov:not([disabled]):has-text('16 sm')")
            pg.wait_for_function("!document.querySelector('#skTmOyna.ko')", timeout=10000)
            pg.wait_for_timeout(300)
            _k16 = xavfsiz(lambda d: d.get(DokonDetal, _d16).tm_bogl_kaliti)
            check("U4 tanlandi — oyna yopildi, serverda bog'landi, qatorda «🏭 Karniz K-12 16 sm», yozilayotgan narx katagi O'CHMADI",
                  bool(_k16) and "16 sm <i>x</i>" in (pg.inner_text(f"[data-tm='{_d16}']") or "")
                  and pg.locator(f"[data-tm='{_d16}'] i").count() == 0
                  and pg.input_value(f"tr[data-detal='{_d16}'] input[data-df='narx_qoplamali']") == "123456", (_k16, JSX))
            pg.evaluate("window.customConfirm = async () => true")
            pg.click(f"[data-tm='{_d16}'] [data-tmuz]")
            pg.wait_for_function(f"!document.querySelector(\"[data-tm='{_d16}'] [data-tmuz]\")", timeout=10000)
            check("U5 «Uzish» — serverda NULL, qatorda «🏭 Omborga bog'lash»",
                  xavfsiz(lambda d: d.get(DokonDetal, _d16).tm_bogl_kaliti, "x") is None
                  and "Omborga bog" in (pg.inner_text(f"[data-tm='{_d16}']") or ""))
            pg.goto(BASE + "/orders")
            pg.wait_for_load_state("networkidle")
            pg.click("#saytBtn")
            pg.wait_for_function("document.querySelector('#saytRoyxat .tk-qator') !== null", timeout=30000)
            _q = pg.locator(f"#saytRoyxat .tk-qator:has(.tk-raqam:text-is('{_uraqam}'))")
            _qt = _q.inner_text() if _q.count() else ""
            check("U6 «🛒 Saytdan» panelida: «🏭 ombordan» belgisi va «🔒 ombor bandi: … gacha»",
                  "🏭 ombordan" in _qt and "ombor bandi" in _qt and "gacha" in _qt, _qt[:400])
            pg.goto(BASE + "/finished")
            pg.wait_for_load_state("networkidle")
            pg.wait_for_selector(".fp-sayt-band", timeout=15000)
            _bt = pg.locator(".fp-sayt-band").all_inner_texts()
            _bd2 = next((x for x in (js(CA.get(BL)).get("bandlar") or []) if FP["dn"] in (x.get("fp_idlar") or [])), {})
            _bkp = next((x for x in (js(CA.get(BL)).get("bandlar") or []) if FP["rkap"] in (x.get("fp_idlar") or [])), {})
            _gd2 = pg.locator(".fp-guruh:has(.fp-guruh-bosh[data-name='burchak d-2']) .fp-guruh-bosh .fp-sayt-band").all_inner_texts()
            check("U7 «Tayyor mahsulotlar»: D-2 GURUH qatorida «🛒 Saytda band: <server miqdori> dona · …, S-…» (yangi buyurtma raqami bilan); "
                  "yakka partiya (Kapitel R-18) qatorida ham",
                  bool(_uraqam) and any(f"Saytda band (jami): {crud.xabar_son(_bd2.get('miqdor', -1))} dona" in x and _uraqam in x for x in _gd2)
                  and any(f"Saytda band (jami): {crud.xabar_son(_bkp.get('miqdor', -1))} dona" in x for x in _bt) and bool(_bkp), (_bt, _gd2, _bd2, _bkp))
            pg.set_viewport_size({"width": 375, "height": 800})
            pg.goto(BASE + "/sayt-katalogi")
            pg.wait_for_selector(".sk-bolim", timeout=30000)
            pg.click(f".sk-bolim[data-id='{KAR}']")
            pg.click(f"[data-och='{M2}']")
            pg.click(f"[data-tm='{_d16}'] [data-tmbog]")
            pg.wait_for_selector("#skTmOyna.ko", timeout=10000)
            _w = pg.evaluate("[document.documentElement.scrollWidth, document.querySelector('#skTmOyna .sk-tm-quti').getBoundingClientRect().right]")
            check("U8 375 px: oyna ekranga sig'adi, sahifa gorizontal surilmaydi", _w[0] <= 375 and _w[1] <= 375, _w)
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
