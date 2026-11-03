#!/usr/bin/env python3
"""
test_dokon_api236.py — kech170 (zip 236 «Do'kon API»; egasi QARORLARI «Onlayn do'kon rejasi» 30.10: do'kon ↔ ERP faqat server ↔ server, maxfiy
kalit bilan, faqat PenoDecorPro korxonasi doirasida; korxona KALITDAN aniqlanadi; API eng kam huquqli — ulgurji narx, tannarx do'konga berilmaydi;
kalitga so'rovlar soni cheklanadi).

NIMA UCHUN KERAK
  Do'kon sayti (alohida server) ERP dan katalog va sozlamalarni o'qiydi. Xato — ulgurji narx yoki tannarxning begonaga chiqishi, boshqa
  korxona katalogining ko'rinishi, kalitsiz / eski kalit bilan o'qish, saytda yashirilgan model / narxning chiqishi, sahifadagidan farqli
  narx (chegirmali, qoplamali, komplekt), kalitning bazada / jurnalda / zaxirada ochiq qolishi, zaxiradan tiklash bilan o'chirilgan kalitning
  tirilishi.
BO'LIMLAR
  S — statik: marshrutlar (kalit boshqaruvi FAQAT Admin, do'kon yo'llari — faqat GET), jadval, zaxiradan tashqari, sahifa kartochkasi.
  A — kirish: belgi o'chiq — 404, Menejer — 403, kalitsiz / noto'g'ri shakl / yo'q kalit — 401 (WWW-Authenticate), Bearer ham.
  Y — kalit: yaratish (bir marta ko'rsatiladi, bazada faqat xesh), almashtirishsiz takror — 409, almashtirish — eskisi 401, o'chirish — 401,
      holat (boshi, kim, oxirgi murojaat — 5 daqiqada bir yoziladi), so'rov tekshiruvlari, jurnal (faqat boshi).
  K — katalog: faqat saytda ko'rinadigan (yoqilgan bo'lim → model → narx qatori), qoplamali (yozilgan / avto), chegirma (amaldagi, o'lchamga;
      muddati tugagan — yo'q), komplekt (mustaqil hisob bilan AYNAN; ulgurji komplekt yo'q), rasmlar, tartib; ulgurji / tannarx / ichki
      maydonlar YO'Q (hamma kalit va qiymat tekshiriladi).
  Z — sozlamalar: ish vaqtida / tashqarida ko'rinadigan raqamlar, ish vaqti matni, retsept.
  E — ETag / 304.
  L — so'rovlar chegarasi: 429 + Retry-After, boshqa kalit / vaqt o'tgach — ochiq.
  T — korxona ajratish: B kaliti faqat B ni ko'radi; so'rovdagi korxona raqami e'tiborga olinmaydi; belgi o'chirilsa — 404.
  B — zaxira: kalit jadvali zaxirada yo'q; tiklash kalitni o'chirmaydi va eskisini tiriltirmaydi.
  P — PG parallel: ikki oynadan bir vaqtda «Kalit yaratish» — bittasi 200, bittasi 409; almashtirish ∥ do'kon so'rovlari — 500 yo'q.
  U — HAQIQIY brauzer: yaratish, nusxa olish, almashtirish (tasdiq), o'chirish, escape, 375 px, JS xatosi yo'q.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` (U — faqat SQLite / TF1). `T236_TEZ=1` — U o'tkaziladi.
Asl kodga (zip 235) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_dokon_api236.py
"""
import os
import io
import re
import sys
import glob
import json
import time
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
TEZ = os.environ.get("T236_TEZ") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "dokon236_test"
_T = tempfile.mkdtemp(prefix="t236_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't236.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, ActivityLog, DokonModel, DokonBolim, DokonRasm   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

DokonChegirma = getattr(models, "DokonChegirma", None)
DokonApiKalit = getattr(models, "DokonApiKalit", None)

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


def ix(lst, i, std=None):
    try:
        return lst[i]
    except Exception:                      # noqa: BLE001
        return std


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Vaqt: «bugun» — Toshkent 2026-11-03 (seshanba) 12:00 (UTC 07:00) — ish vaqti
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
class _SoxtaVaqt:
    t = datetime(2026, 11, 3, 7, 0)

    @classmethod
    def utcnow(cls):
        return cls.t


if getattr(crud, "_dt233", None) is not None:
    crud._dt233 = _SoxtaVaqt

s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T236 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t236_admin", PAROL, UserRole.ADMIN, "T236 Admin", company_id=1)
    auth.create_user(s, "t236_plat", PAROL, UserRole.ADMIN, "T236 Platforma", company_id=1)
    auth.create_user(s, "t236_men", PAROL, UserRole.MANAGER, "T236 Menejer", company_id=1)
    auth.create_user(s, "t236_b", PAROL, UserRole.ADMIN, "T236 B Admin", company_id=2)
    auth.create_user(s, "t236_ui", PAROL, UserRole.ADMIN, "UI <img src=x onerror=window.__xss236=1>", company_id=1)
s.query(User).filter(User.username == "t236_plat").first().is_platform_admin = True
s.commit()
s.close()
main._send_telegram = lambda msg, *a, **k: True


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t236_admin")
CP = mijoz("t236_plat")
CM = mijoz("t236_men")
CB = mijoz("t236_b")
DOK = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)    # do'kon serveri — cookie siz
API = "/api/sayt-katalogi"
AK = API + "/api-kalit"
KAT = "/api/dokon/v1/katalog"
SOZ = "/api/dokon/v1/sozlamalar"
KALIT_RE = re.compile(r"pdk_[A-Za-z0-9_-]{43}")


def dok(yol, kalit=None, **sarlavha):
    h = dict(sarlavha)
    if kalit is not None:
        h["X-Dokon-Kalit"] = kalit
    return DOK.get(yol, headers=h)


def yarat(c=None, almashtir=None, eski_boshi="auto"):
    """almashtir=True — sahifa ko'rgan kalit boshi (`eski_boshi`) bilan; "auto" — hozirgi holatdan olinadi."""
    c = c or CA
    if almashtir is None:
        return c.post(AK, json={})
    tana = {"almashtir": almashtir}
    if eski_boshi == "auto":
        eski_boshi = js(c.get(AK)).get("boshi")
    if eski_boshi is not None:
        tana["eski_boshi"] = eski_boshi
    return c.post(AK, json=tana)


def kalit_qatori(cid=1):
    def f(d):
        k = d.query(DokonApiKalit).filter(DokonApiKalit.company_id == cid).first()
        return None if k is None else {"xesh": k.api_kalit_xesh, "boshi": k.api_kalit_boshi, "oxirgi": k.oxirgi_murojaat,
                                       "yaratgan": k.api_yaratgan}
    return xavfsiz(f) if DokonApiKalit is not None else None


def jurnal(entity="dokon_api_kalit"):
    return db_ishi(lambda d: [(a.action, a.old_value or "", a.new_value or "", a.performed_by, a.company_id)
                              for a in d.query(ActivityLog).filter(ActivityLog.entity_type == entity).order_by(ActivityLog.id).all()])


D = Decimal


def o_avto(n, koeff=D(2)):
    asl = D(str(n)) * koeff
    x = (asl / D(1000)).quantize(D(1), rounding=ROUND_HALF_UP) * D(1000)
    return x if x > 0 else asl.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def o_ch(n, f):
    n = D(str(n))
    asl = n * (D(100) - D(str(f))) / D(100)
    for q in (D(100), D(10)):
        x = (asl / q).quantize(D(1), rounding=ROUND_HALF_UP) * q
        if 0 < x < n:
            return x
    return max(asl.quantize(D("0.01"), rounding=ROUND_HALF_UP), D("0.01"))


def son(v):
    return None if v is None else D(str(v)).quantize(D("0.01"))


def kalitlar_hammasi(ob, yol=""):
    """JSON obyektidagi hamma kalit yo'llari («modellar[].detallar[].narx» shaklida)."""
    natija = set()
    if isinstance(ob, dict):
        for k, v in ob.items():
            natija.add(f"{yol}.{k}" if yol else k)
            natija |= kalitlar_hammasi(v, f"{yol}.{k}" if yol else k)
    elif isinstance(ob, list):
        for v in ob:
            natija |= kalitlar_hammasi(v, yol + "[]")
    return natija


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_yollar = {(m, r.path): r for r in main.app.routes for m in (getattr(r, "methods", None) or ())}


def _admin_only(m, p):
    r = _yollar.get((m, p))
    return bool(r) and any(getattr(dp.call, "__name__", "") == "admin_only" for dp in r.dependant.dependencies)


check("S1 kalit boshqaruvi — 3 marshrut bor va FAQAT Admin (auth.admin_only): GET / POST / DELETE /api/sayt-katalogi/api-kalit",
      all(_admin_only(m, AK) for m in ("GET", "POST", "DELETE")), [(m, (m, AK) in _yollar) for m in ("GET", "POST", "DELETE")])
_dy = sorted((m, p) for (m, p) in _yollar if p.startswith("/api/dokon/"))
# kech171 (zip 237): do'kon yo'llari — 2 GET + BITTA POST (buyurtma yuborish; tools/test_dokon_buyurtma237.py S1)
# kech172 (zip 238, MOSLANDI): + «tayyor» GET (Tayyor mahsulotlar qoldig'i; tools/test_dokon_tayyor238.py S1)
check("S2 do'kon yo'llari — 3 ta GET (katalog, sozlamalar, tayyor) + buyurtma POST (zip 237); o'chiruvchi / tahrirlovchi yo'l YO'Q",
      sorted(_dy) == sorted([("GET", KAT), ("GET", SOZ), ("GET", "/api/dokon/v1/tayyor"), ("POST", "/api/dokon/v1/buyurtmalar")]
                             + ([("GET", "/api/dokon/v1/galereya")] if hasattr(crud, "dokon_api_galereya") else [])
                             + ([("POST", "/api/dokon/v1/buyurtmalar/pdf"), ("POST", "/api/dokon/v1/savat/pdf")] if hasattr(crud, "sayt_pdf_savat") else [])
                             + ([("POST", "/api/dokon/v1/kirish"), ("POST", "/api/dokon/v1/kirish/holat"), ("GET", "/api/dokon/v1/mijoz"), ("POST", "/api/dokon/v1/mijoz/royxat"), ("POST", "/api/dokon/v1/mijoz/chiqish")] if hasattr(crud, "dokon_kirish_boshla") else []) + ([("GET", "/api/dokon/v1/mijoz/buyurtmalar"), ("POST", "/api/dokon/v1/mijoz/buyurtmalar/pdf")] if hasattr(crud, "dokon_mijoz_buyurtmalari") else [])), _dy)   # kech178 (zip 243): galereya; zip 244: PDF; kech181 (zip 248, MOSLANDI): kirish / mijoz
check("S3 jadval `dokon_api_kalitlar`: korxonaga bitta qator (yagona company_id), xesh — 64 belgi, yagona; xom kalit ustuni YO'Q",
      DokonApiKalit is not None and DokonApiKalit.__tablename__ == "dokon_api_kalitlar"
      and any(getattr(c, "name", "") == "uq_dokon_api_kalit_korxona" for c in DokonApiKalit.__table__.constraints)
      and DokonApiKalit.__table__.c.api_kalit_xesh.type.length == 64 and DokonApiKalit.__table__.c.api_kalit_xesh.unique
      and not any(c.name in ("kalit", "api_kalit", "token") for c in DokonApiKalit.__table__.columns),
      DokonApiKalit and [c.name for c in DokonApiKalit.__table__.columns])
check("S4 zaxiraga KIRMAYDI (`_NON_TENANT_TABLES`), «Barcha ma'lumotlarni o'chirish» tartibida YO'Q (`_reset_table_order`)",
      "dokon_api_kalitlar" in getattr(crud, "_NON_TENANT_TABLES", set())
      and "DokonApiKalit" not in [c.__name__ for c in crud._reset_table_order()])
_html = open(os.path.join(ROOT, "templates", "sayt_katalogi.html"), encoding="utf-8").read()
check("S5 sahifa: «🔑 Do'kon sayti uchun kalit (API)» shtorkasi (data-sht=sk-api), holat / tugmalar / yangi kalit bloklari",
      all(x in _html for x in ('data-sht="sk-api"', 'id="skApiHolat"', 'id="skApiTugmalar"', 'id="skApiYangi"', "Do'kon sayti uchun kalit")))
check("S6 crud: dokon_api_korxona / dokon_api_katalog / dokon_api_sozlamalar / dokon_api_kalit_yarat / _ochir / _holati, DokonApiRad",
      all(callable(getattr(crud, n, None)) for n in ("dokon_api_korxona", "dokon_api_katalog", "dokon_api_sozlamalar", "dokon_api_kalit_yarat",
                                                     "dokon_api_kalit_ochir", "dokon_api_kalit_holati"))
      and isinstance(getattr(crud, "DokonApiRad", None), type))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Kirish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_st = [CA.get(AK).status_code, yarat().status_code, CA.delete(AK).status_code]
check("A1 sayt katalogi belgisi o'chiq — kalit marshrutlari 404", _st == [404, 404, 404], _st)
r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
check("A0 platforma: korxona 1 da sayt katalogi yoqildi", r.status_code == 200, r.text[:200])
_st = [CM.get(AK).status_code, yarat(CM).status_code, CM.delete(AK).status_code]
check("A2 Menejer — kalit marshrutlari 403", _st == [403, 403, 403], _st)
_st = [CB.get(AK).status_code, yarat(CB).status_code, CB.delete(AK).status_code]
check("A3 B korxona admini (belgi o'chiq) — 404", _st == [404, 404, 404], _st)
_r = [dok(KAT), dok(SOZ), dok(KAT, "pdk_" + "a" * 43), dok(KAT, "pdk_" + "a" * 42), dok(KAT, "x" * 47), dok(KAT, "pdk_" + "a" * 43 + " x"),
      DOK.get(KAT, headers={"Authorization": "Bearer pdk_" + "b" * 43}), DOK.get(KAT, headers={"Authorization": "Basic abc"})]
check("A4 kalitsiz / shakli noto'g'ri / bazada yo'q kalit (X-Dokon-Kalit ham, Bearer ham) — 401, WWW-Authenticate: Bearer, no-store, "
      "javobda katalog yo'q", all(x.status_code == 401 and x.headers.get("www-authenticate") == "Bearer"
                                  and "no-store" in x.headers.get("cache-control", "") and "modellar" not in x.text for x in _r),
      [(x.status_code, dict(x.headers).get("www-authenticate"), x.text[:80]) for x in _r])
_r = DOK.get(KAT, cookies=CA.cookies)
check("A5 Admin sessiya cookie si bilan, kalitsiz — 401 (do'kon yo'li sessiyani tan olmaydi)", _r.status_code == 401, (_r.status_code, _r.text[:120]))

# ── Sinov katalogi ──
K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}
KOMP, KAR, TERMO, DEK = BOL.get("Rom va eshik dekorlari"), BOL.get("Karnizlar"), BOL.get("Termopanel"), BOL.get("Dekor elementlar")


def model(bolim, kod, c=None, **kw):
    return js((c or CA).post(API + "/modellar", json=dict({"bolim_id": bolim, "kod": kod}, **kw))).get("id")


def detal(mid, turi, olcham, c=None, **kw):
    return js((c or CA).post(API + "/detallar", json=dict({"model_id": mid, "turi": turi, "olcham": olcham}, **kw))).get("id")


ORTA = "O'rta"
# Ulgurji narxlar — HECH qayerda uchramaydigan sonlar (javob matnida qidiriladi)
ULG = {"karniz": 71311, "podokonnik": 71322, "nalichnik": 71333, "kapitel": 71344, "baza": 71355}
M1 = model(KOMP, "R-18", nom="Klassik", kapitel_baza_bor=True, tavsif="Klassik rom dekori")
DID = {}
for _t, _n in (("karniz", 15000), ("podokonnik", 14000), ("nalichnik", 12000), ("kapitel", 30000), ("baza", 30000)):
    DID[_t] = detal(M1, _t, ORTA, narx=_n, ulgurji_narx=ULG[_t], ulgurji_qoplamali=ULG[_t] + 1000,
                    eni_sm=15 if _t == "karniz" else None, qalinligi_sm=10 if _t == "karniz" else None)
for _t, _n in (("karniz", 18000), ("podokonnik", 16000), ("nalichnik", 14000), ("kapitel", 34000), ("baza", 34000)):
    DID["k_" + _t] = detal(M1, _t, "Katta", narx=_n, ulgurji_narx=ULG[_t] + 7, narx_qoplamali=_n * 2 + 500)
M2 = model(KAR, "K-12", nom="Tekis")
DID["k12"] = detal(M2, "asosiy", "12 sm", narx=45000, narx_qoplamali=98000, ulgurji_narx=72111, ulgurji_qoplamali=72122)
DID["k15"] = detal(M2, "asosiy", "15 sm", narx=52000, yoqilgan=False)               # saytda yashirin qator
DID["k18"] = detal(M2, "asosiy", "18 sm")                                             # narxi kiritilmagan
MT = model(TERMO, "T-1", nom="Termopanel 60×120")
DID["t1"] = detal(MT, "asosiy", "60×120", narx=150000.5, ulgurji_narx=72133)
M3 = model(DEK, "D-1", nom="Rozetka", yoqilgan=False)                                 # saytda yashirin model
DID["d1"] = detal(M3, "asosiy", "Standart", narx=9100)
M4 = model(DEK, "D-2", nom="Burchak")
DID["d2"] = detal(M4, "asosiy", "S", narx=9900)
BYOQ = js(CA.post(API + "/bolimlar", json={"nom": "Yashirin bo'lim T236", "qolip": "dona", "yoqilgan": False})).get("id")
M5 = model(BYOQ, "Y-1", nom="Yashirin bo'limdagi model") if BYOQ else None
DID["y1"] = detal(M5, "asosiy", "S", narx=9300) if M5 else None
CA.put(API + f"/modellar/{M4}", json={"tartib": 0})                      # bo'lim ichida tartib: D-2 (keyin yaratilgan) — oldin
r = CA.put(API + f"/modellar/{M1}/chegirma", json={"foiz": 15, "olchamlar": [ORTA]})
check("A6 chegirma (R-18, −15 %, faqat O'rta) qo'yildi", r.status_code == 200, r.text[:200])
if DokonChegirma is not None:                      # muddati o'tgan chegirma — bazaga to'g'ridan-to'g'ri (API o'tgan sanani qabul qilmaydi)
    db_ishi(lambda d: d.add(DokonChegirma(company_id=1, model_id=M2, foiz=10, olchamlar=None, tugash=date(2026, 10, 1),
                                          created_by="t", updated_by="t")))
    db_ishi(lambda d: d.add(DokonChegirma(company_id=1, model_id=MT, foiz=20, olchamlar=None, tugash=date(2026, 11, 3),
                                          created_by="t", updated_by="t")))
# rasm — yozuv bazaga (fayl ishlovi zip 232 da sinalgan)
db_ishi(lambda d: d.add(DokonRasm(company_id=1, model_id=M1, fayl="/static/uploads/dokon/t236a.jpg", kichik="/static/uploads/dokon/t236a_k.jpg",
                                  eni=1600, boyi=1200, hajm=123456, turi="jpeg", tartib=2, created_by="t")))
db_ishi(lambda d: d.add(DokonRasm(company_id=1, model_id=M1, fayl="/static/uploads/dokon/t236b.jpg", kichik="/static/uploads/dokon/t236b_k.jpg",
                                  eni=800, boyi=600, hajm=65432, turi="jpeg", tartib=1, created_by="t")))
check("A7 sinov katalogi yaratildi (6 model, 17 narx qatori)", all(v for v in DID.values()) and all((M1, M2, MT, M3, M4, M5)), DID)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Y. Kalit")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = CA.get(AK)
H0 = js(r)
check("Y1 holat — kalit yo'q: bor=false, boshi / yaratilgan / oxirgi — null; sarlavha X-Dokon-Kalit, 2 yo'l, daqiqasiga 120",
      r.status_code == 200 and H0.get("bor") is False and H0.get("boshi") is None and H0.get("oxirgi_murojaat") is None
      and H0.get("sarlavha") == "X-Dokon-Kalit" and H0.get("yollar") == [KAT, SOZ, "/api/dokon/v1/buyurtmalar", "/api/dokon/v1/tayyor"] + (["/api/dokon/v1/galereya"] if hasattr(crud, "dokon_api_galereya") else []) + (["/api/dokon/v1/buyurtmalar/pdf", "/api/dokon/v1/savat/pdf"] if hasattr(crud, "sayt_pdf_savat") else []) + (["/api/dokon/v1/kirish", "/api/dokon/v1/kirish/holat", "/api/dokon/v1/mijoz", "/api/dokon/v1/mijoz/royxat", "/api/dokon/v1/mijoz/chiqish"] if hasattr(crud, "dokon_kirish_boshla") else []) + (["/api/dokon/v1/mijoz/buyurtmalar", "/api/dokon/v1/mijoz/buyurtmalar/pdf"] if hasattr(crud, "dokon_mijoz_buyurtmalari") else []) and H0.get("daqiqa_max") == 120, (r.status_code, H0))
_j0 = len(jurnal())
r = yarat()
Y1 = js(r)
K1 = Y1.get("kalit") or ""
_q = kalit_qatori()
check("Y2 yaratish — 200, kalit «pdk_» + 43 belgi, javob keshlanmaydi (no-store), holat bor=true, boshi = kalitning 10 belgisi, yaratgan — Admin",
      r.status_code == 200 and KALIT_RE.fullmatch(K1) and "no-store" in r.headers.get("cache-control", "")
      and Y1.get("bor") is True and Y1.get("boshi") == K1[:10] and Y1.get("yaratgan") == "T236 Admin", (r.status_code, Y1))
check("Y3 bazada FAQAT SHA-256 xesh (xom kalit hech bir ustunda yo'q), boshi 10 belgi",
      _q is not None and _q["xesh"] == __import__("hashlib").sha256(K1.encode()).hexdigest() and _q["boshi"] == K1[:10]
      and K1 not in json.dumps(_q, default=str), _q)
r = CA.get(AK)
check("Y4 holat — xom kalit ham, xeshi ham YO'Q (faqat boshi)", r.status_code == 200 and K1 not in r.text and (_q or {}).get("xesh", "?") not in r.text
      and js(r).get("boshi") == K1[:10] and "kalit" not in js(r), r.text[:300])
r = dok(KAT, K1)
check("Y5 do'kon yo'li yangi kalit bilan — 200 (X-Dokon-Kalit)", r.status_code == 200 and isinstance(js(r).get("modellar"), list), (r.status_code, r.text[:200]))
_r = [DOK.get(KAT, headers={"Authorization": "Bearer " + K1}), DOK.get(KAT, headers={"authorization": "bearer " + K1}),
      DOK.get(KAT, headers={"X-Dokon-Kalit": "  " + K1 + "  "})]
check("Y6 «Authorization: Bearer …» (katta-kichik harfsiz), bo'shliq bilan — 200", [x.status_code for x in _r] == [200, 200, 200],
      [x.status_code for x in _r])
_q = kalit_qatori()
check("Y7 oxirgi murojaat yozildi; holatda Toshkent vaqti «dd.mm.yyyy HH:MM»", _q and _q["oxirgi"] is not None
      and re.fullmatch(r"\d\d\.\d\d\.\d{4} \d\d:\d\d", js(CA.get(AK)).get("oxirgi_murojaat") or ""), (_q, js(CA.get(AK))))
_eski = datetime(2026, 1, 1, 0, 0)
xavfsiz(lambda d: setattr(d.query(DokonApiKalit).filter(DokonApiKalit.company_id == 1).first(), "oxirgi_murojaat", datetime.utcnow() - timedelta(minutes=2)))
_o2 = (kalit_qatori() or {}).get("oxirgi")
dok(KAT, K1)
_o3 = (kalit_qatori() or {}).get("oxirgi")
xavfsiz(lambda d: setattr(d.query(DokonApiKalit).filter(DokonApiKalit.company_id == 1).first(), "oxirgi_murojaat", _eski))
dok(SOZ, K1)
_o4 = (kalit_qatori() or {}).get("oxirgi")
check("Y8 oxirgi murojaat 5 daqiqada bir marta yoziladi: 2 daqiqa oldingisi — o'zgarmaydi, eskisi — yangilanadi",
      _o2 is not None and _o3 == _o2 and _o4 is not None and _o4 > _eski + timedelta(days=30), (_o2, _o3, _o4))
r = yarat()
check("Y9 almashtirishsiz qayta yaratish — 409 «allaqachon bor», kalit o'zgarmaydi (eski ishlaydi)", r.status_code == 409 and "kalit" not in js(r)
      and "allaqachon bor" in det(r)
      and dok(KAT, K1).status_code == 200 and (kalit_qatori() or {}).get("boshi") == K1[:10], (r.status_code, r.text[:200]))
_r = [CA.post(AK, json={"almashtir": "true"}), CA.post(AK, json={"almashtir": 1}), CA.post(AK, json={"company_id": 2}),
      CA.post(AK, json=[1]), CA.post(AK, content=b"{", headers={"Content-Type": "application/json"})]
check("Y10 noto'g'ri so'rov (almashtir matn / son, begona maydon, ro'yxat, buzilgan JSON) — 400 / 422, kalit o'zgarmaydi",
      all(x.status_code in (400, 422) for x in _r) and (kalit_qatori() or {}).get("boshi") == K1[:10], [(x.status_code, x.text[:80]) for x in _r])
_r = [yarat(almashtir=True, eski_boshi=None), yarat(almashtir=True, eski_boshi="pdk_BOSHQA"), yarat(almashtir=True, eski_boshi=K1[:9])]
_r4 = yarat(almashtir=True, eski_boshi=123)
check("Y10b almashtirish sahifa ko'rgan kalit boshisiz / boshqa boshi bilan — 409 «boshqa oynada o'zgargan» (review236 L2); boshi son — 400; "
      "kalit o'zgarmaydi", [x.status_code for x in _r] == [409, 409, 409] and all("boshqa oynada" in det(x) for x in _r)
      and _r4.status_code == 400 and dok(KAT, K1).status_code == 200 and (kalit_qatori() or {}).get("boshi") == K1[:10],
      [(x.status_code, det(x)[:60]) for x in _r + [_r4]])
r = yarat(almashtir=True)
Y2 = js(r)
K2 = Y2.get("kalit") or ""
check("Y11 almashtirish ({\"almashtir\": true}) — 200, yangi kalit boshqa; ESKI kalit darhol 401, yangisi 200",
      r.status_code == 200 and KALIT_RE.fullmatch(K2) and K2 != K1 and dok(KAT, K1).status_code == 401 and dok(KAT, K2).status_code == 200,
      (r.status_code, Y2))
check("Y12 almashtirilgach oxirgi murojaat — yangi kalitniki (birinchi so'rovgacha null emas — Y11 da so'rov bo'ldi)",
      (kalit_qatori() or {}).get("oxirgi") is not None)
r = CA.delete(AK)
check("Y13 o'chirish — 200; kalit 401; holat bor=false; qayta o'chirish — 404", r.status_code == 200 and dok(KAT, K2).status_code == 401
      and js(CA.get(AK)).get("bor") is False and CA.delete(AK).status_code == 404 and (kalit_qatori() or {}).get("xesh", "x") is None,
      (r.status_code, kalit_qatori()))
r = yarat(almashtir=True)
K3 = js(r).get("kalit") or ""
check("Y14 kalit yo'q paytda «almashtir: true» bilan ham yaratiladi (korxonada qator bitta qoladi)", lambda: r.status_code == 200 and KALIT_RE.fullmatch(K3)
      and db_ishi(lambda d: d.query(DokonApiKalit).filter(DokonApiKalit.company_id == 1).count()) == 1, (r.status_code, r.text[:200]))
_j = jurnal()[_j0:]
_kalitlar = [K1, K2, K3]
_xeshlar = [__import__("hashlib").sha256(x.encode()).hexdigest() for x in _kalitlar]
check("Y15 jurnal: yaratildi / almashtirildi / o'chirildi / (qayta) yaratildi — har birida FAQAT boshi («kalit pdk_xxxxxx…»), xom kalit va "
      "xesh YO'Q", [a[0] for a in _j] == ["created", "updated", "deleted", "created"] and _j[0][2] == f"kalit {K1[:10]}…" and _j[1][1] == f"kalit {K1[:10]}…"
      and _j[1][2] == f"kalit {K2[:10]}…; eski kalit o'chirildi" and _j[2][1] == f"kalit {K2[:10]}…" and _j[3][2] == f"kalit {K3[:10]}…"
      and all(a[3] == "T236 Admin" and a[4] == 1 for a in _j)
      and not any(x in json.dumps(_j, ensure_ascii=False) for x in _kalitlar + _xeshlar), _j)
_hamma_jurnal = db_ishi(lambda d: " ".join((a.old_value or "") + " " + (a.new_value or "") + " " + (a.entity_label or "") for a in d.query(ActivityLog).all()))
check("Y16 butun jurnalda (ActivityLog) hech bir kalit yoki uning xeshi YO'Q", not any(x in _hamma_jurnal for x in _kalitlar + _xeshlar))
KALIT = K3

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Katalog")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = dok(KAT, KALIT)
KT = js(r)
check("K1 200, application/json, ETag, Cache-Control private, no-cache; versiya 1, bugun 2026-11-03 (Toshkent)",
      r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json") and re.fullmatch(r'"[0-9a-f]{32}"', r.headers.get("etag", ""))
      and r.headers.get("cache-control") == "private, no-cache" and KT.get("versiya") == 1 and KT.get("bugun") == "2026-11-03",
      (r.status_code, dict(r.headers), r.text[:200]))
RUXSAT = {
    "versiya", "bugun", "bolimlar", "bolimlar[].id", "bolimlar[].nom", "bolimlar[].qolip", "bolimlar[].tizim_kaliti", "bolimlar[].tartib",
    "bolimlar[].qolip_nomi", "modellar", "modellar[].id", "modellar[].bolim_id", "modellar[].kod", "modellar[].nom", "modellar[].tavsif",
    "modellar[].qolip", "modellar[].qolip_nomi", "modellar[].kapitel_baza_bor", "modellar[].tartib", "modellar[].rasmlar",
    "modellar[].rasmlar[].url", "modellar[].rasmlar[].kichik", "modellar[].rasmlar[].eni", "modellar[].rasmlar[].boyi", "modellar[].detallar",
    "modellar[].detallar[].id", "modellar[].detallar[].turi", "modellar[].detallar[].turi_nomi", "modellar[].detallar[].olcham",
    "modellar[].detallar[].eni_sm", "modellar[].detallar[].qalinligi_sm", "modellar[].detallar[].birlik", "modellar[].detallar[].narx",
    "modellar[].detallar[].narx_qoplamali", "modellar[].detallar[].chegirma", "modellar[].detallar[].chegirma.foiz",
    "modellar[].detallar[].chegirma.narx", "modellar[].detallar[].chegirma.narx_qoplamali", "modellar[].komplekt",
    "modellar[].komplekt[].olcham", "modellar[].komplekt[].rom", "modellar[].komplekt[].eshik", "modellar[].komplekt[].chegirma",
    "modellar[].komplekt[].chegirma.foiz", "modellar[].komplekt[].chegirma.rom", "modellar[].komplekt[].chegirma.eshik",
    "modellar[].chegirma", "modellar[].chegirma.foiz", "modellar[].chegirma.olchamlar", "modellar[].chegirma.tugash",
    "modellar[].chegirma.tugash_matni"}
for _k in ("rom", "eshik", "chegirma.rom", "chegirma.eshik"):
    for _n in ("qoplamasiz", "qoplamali", "qoplamasiz_kbsiz", "qoplamali_kbsiz"):
        RUXSAT.add(f"modellar[].komplekt[].{_k}.{_n}")
_bor = kalitlar_hammasi(KT)
check("K2 javobdagi HAMMA kalit ruxsat ro'yxatida (ulgurji, tannarx, yetishmaydi, updated_by, yoqilgan, koeff … — YO'Q)", _bor <= RUXSAT,
      sorted(_bor - RUXSAT))
_matn = r.text
_ulg_sonlar = [str(v) for v in ULG.values()] + [str(v + 1000) for v in ULG.values()] + [str(v + 7) for v in ULG.values()] + ["72111", "72122", "72133"]
check("K3 ulgurji narxlar (oddiy / qoplamali / avto ulgurji, komplekt ulgurji) javob matnida UMUMAN uchramaydi; «tannarx» so'zi yo'q; «ulgurji» "
      "— faqat «Ulgurji» bo'limi nomida", not any(x in _matn for x in _ulg_sonlar) and "tannarx" not in _matn.lower()
      and _matn.lower().count("ulgurji") == sum(json.dumps(b, ensure_ascii=False).lower().count("ulgurji") for b in KT.get("bolimlar") or []),
      [x for x in _ulg_sonlar if x in _matn])
_avto_ulg = [str(int(o_avto(v))) for v in list(ULG.values()) + [72111, 72133]]
check("K4 ulgurji narxning avto qoplamalisi (× koeff) ham matnda yo'q", not any(f":{x}" in _matn or f":{x}." in _matn for x in _avto_ulg),
      [x for x in _avto_ulg if x in _matn])
_bnom = [b.get("nom") for b in KT.get("bolimlar") or []]
check("K5 bo'limlar: faqat yoqilganlar, sahifadagi tartibda (yashirin bo'lim yo'q)",
      "Yashirin bo'lim T236" not in _bnom and _bnom == [b["nom"] for b in K.get("bolimlar", []) if b.get("yoqilgan")], (_bnom, K.get("bolimlar")))
_mk = [m.get("kod") for m in KT.get("modellar") or []]
check("K6 modellar: yashirin model (D-1) va yashirin bo'lim modeli (Y-1) YO'Q; tartib — bo'lim → model tartibi (D-2 tartib 0 — R-18 / K-12 / T-1 dan "
      "keyin, o'z bo'limida birinchi)", _mk == ["R-18", "K-12", "T-1", "D-2"], _mk)
MD = {m.get("kod"): m for m in KT.get("modellar") or []}
_m1 = MD.get("R-18", {})
check("K7 R-18: bo'lim, nom, tavsif, qolip komplekt, kapitel/baza bor; rasmlar tartib bo'yicha (tartib 1 — birinchi), manzil / kichik / o'lcham",
      _m1.get("bolim_id") == KOMP and _m1.get("nom") == "Klassik" and _m1.get("tavsif") == "Klassik rom dekori" and _m1.get("qolip") == "komplekt"
      and _m1.get("kapitel_baza_bor") is True
      and _m1.get("rasmlar") == [{"url": "/static/uploads/dokon/t236b.jpg", "kichik": "/static/uploads/dokon/t236b_k.jpg", "eni": 800, "boyi": 600},
                                 {"url": "/static/uploads/dokon/t236a.jpg", "kichik": "/static/uploads/dokon/t236a_k.jpg", "eni": 1600, "boyi": 1200}],
      _m1)
_d = {x.get("id"): x for x in _m1.get("detallar") or []}
_kr = _d.get(DID["karniz"], {})
check("K8 R-18 O'rta karniz: turi / nomi / o'lcham / eni / qalinlik / birlik; narx 15 000, qoplamali avto 30 000; chegirma −15 %: 12 800 / 25 500 "
      "(mustaqil hisob)",
      _kr.get("turi") == "karniz" and _kr.get("turi_nomi") == "Rom karnizi" and _kr.get("olcham") == ORTA and _kr.get("eni_sm") == 15
      and _kr.get("qalinligi_sm") == 10 and _kr.get("birlik") == "metr" and son(_kr.get("narx")) == D(15000)
      and son(_kr.get("narx_qoplamali")) == o_avto(15000) and _kr.get("chegirma") == {"foiz": 15.0, "narx": float(o_ch(15000, 15)),
                                                                                    "narx_qoplamali": float(o_ch(o_avto(15000), 15))}, _kr)
_kk = _d.get(DID["k_karniz"], {})
check("K9 R-18 Katta karniz: qoplamali — yozilgani (36 500), chegirma YO'Q (chegirma faqat O'rta o'lchamga)",
      son(_kk.get("narx")) == D(18000) and son(_kk.get("narx_qoplamali")) == D(36500) and _kk.get("chegirma") is None, _kk)
check("K10 R-18 da 10 narx qatori (sahifadagi tartibda: O'rta 5, Katta 5)", list(_d) == [DID[k] for k in ("karniz", "podokonnik", "nalichnik",
      "kapitel", "baza", "k_karniz", "k_podokonnik", "k_nalichnik", "k_kapitel", "k_baza")], list(_d))
check("K11 R-18 chegirmasi: foiz 15, faqat O'rta, muddatsiz", _m1.get("chegirma") == {"foiz": 15.0, "olchamlar": [ORTA], "tugash": None,
                                                                                       "tugash_matni": None} or (
      (_m1.get("chegirma") or {}).get("foiz") == 15.0 and (_m1.get("chegirma") or {}).get("olchamlar") == [ORTA]
      and (_m1.get("chegirma") or {}).get("tugash") is None), _m1.get("chegirma"))
R = crud.DOKON_RETSEPT_STANDART


def o_komplekt(narxlar, kom, kb=True):
    return sum(D(str(narxlar[t])) * R[kom][t] for t in R[kom] if kb or t not in ("kapitel", "baza"))


_orta = {"karniz": 15000, "podokonnik": 14000, "nalichnik": 12000, "kapitel": 30000, "baza": 30000}
_orta_q = {k: o_avto(v) for k, v in _orta.items()}
_orta_ch = {k: o_ch(v, 15) for k, v in _orta.items()}
_orta_chq = {k: o_ch(o_avto(v), 15) for k, v in _orta.items()}
_katta = {"karniz": 18000, "podokonnik": 16000, "nalichnik": 14000, "kapitel": 34000, "baza": 34000}
_katta_q = {k: v * 2 + 500 for k, v in _katta.items()}
_ko = {x.get("olcham"): x for x in _m1.get("komplekt") or []}
_o = _ko.get(ORTA, {})
check("K12 komplekt O'rta (mustaqil hisob): rom — to'liq / kapitel-bazasiz, qoplamasiz / qoplamali; eshik — xuddi shunday",
      _o.get("rom") == {"qoplamasiz": float(o_komplekt(_orta, "rom")), "qoplamali": float(o_komplekt(_orta_q, "rom")),
                        "qoplamasiz_kbsiz": float(o_komplekt(_orta, "rom", False)), "qoplamali_kbsiz": float(o_komplekt(_orta_q, "rom", False))}
      and _o.get("eshik") == {"qoplamasiz": float(o_komplekt(_orta, "eshik")), "qoplamali": float(o_komplekt(_orta_q, "eshik")),
                              "qoplamasiz_kbsiz": float(o_komplekt(_orta, "eshik", False)),
                              "qoplamali_kbsiz": float(o_komplekt(_orta_q, "eshik", False))}, (_o, o_komplekt(_orta, "rom")))
check("K13 komplekt O'rta chegirmasi — chegirmali detallar yig'indisi (−15 %): rom / eshik, to'liq / kbsiz",
      (_o.get("chegirma") or {}).get("foiz") == 15.0
      and (_o.get("chegirma") or {}).get("rom") == {"qoplamasiz": float(o_komplekt(_orta_ch, "rom")), "qoplamali": float(o_komplekt(_orta_chq, "rom")),
                                                    "qoplamasiz_kbsiz": float(o_komplekt(_orta_ch, "rom", False)),
                                                    "qoplamali_kbsiz": float(o_komplekt(_orta_chq, "rom", False))}
      and (_o.get("chegirma") or {}).get("eshik", {}).get("qoplamasiz") == float(o_komplekt(_orta_ch, "eshik")), _o.get("chegirma"))
_kt = _ko.get("Katta", {})
check("K14 komplekt Katta: yozilgan qoplamali narxlardan; chegirma YO'Q; ulgurji komplekt va «yetishmaydi» YO'Q",
      (_kt.get("rom") or {}).get("qoplamali") == float(o_komplekt(_katta_q, "rom")) and (_kt.get("rom") or {}).get("qoplamasiz") == float(o_komplekt(_katta, "rom"))
      and _kt.get("chegirma") is None and set(_kt) == {"olcham", "rom", "eshik", "chegirma"}, _kt)
_mm = db_ishi(lambda d: d.query(DokonModel).filter(DokonModel.id == M1).first())
_crud_k = db_ishi(lambda d: crud.dokon_komplekt_narxlari(d, 1, M1)).get(M1) or []
check("K15 komplekt — `crud.dokon_model_komplekti` (sahifa) bilan AYNAN (rom / eshik / chegirma)",
      [{"olcham": x["olcham"], "rom": {k: v for k, v in x["rom"].items() if k != "yetishmaydi"},
        "eshik": {k: v for k, v in x["eshik"].items() if k != "yetishmaydi"},
        "chegirma": x["chegirma"]} for x in _crud_k] == _m1.get("komplekt"), (_crud_k, _m1.get("komplekt")))
_m2 = MD.get("K-12", {})
_d2 = {x.get("id"): x for x in _m2.get("detallar") or []}
check("K16 K-12: yashirin qator (15 sm) YO'Q; narxi kiritilmagan (18 sm) — narx null; qoplamali yozilgani 98 000; muddati o'tgan chegirma — "
      "YO'Q (model va qatorda); komplekt null (oddiy model)",
      list(_d2) == [DID["k12"], DID["k18"]] and son(_d2[DID["k12"]].get("narx_qoplamali")) == D(98000) and _d2[DID["k18"]].get("narx") is None
      and _d2[DID["k18"]].get("narx_qoplamali") is None and _d2[DID["k12"]].get("chegirma") is None and _m2.get("chegirma") is None
      and _m2.get("komplekt") is None, _m2)
_mt = MD.get("T-1", {})
_dt = (_mt.get("detallar") or [{}])[0]
check("K17 T-1: tiyinli narx 150 000,50; qoplamali avto 300 000 (1 000 ga); chegirma bugun tugaydi — AMALDA (−20 %), «tugash» 2026-11-03",
      son(_dt.get("narx")) == D("150000.50") and son(_dt.get("narx_qoplamali")) == o_avto(D("150000.5"))
      and (_dt.get("chegirma") or {}).get("narx") == float(o_ch(D("150000.5"), 20)) and (_mt.get("chegirma") or {}).get("tugash") == "2026-11-03"
      and (_mt.get("chegirma") or {}).get("tugash_matni"), _mt)
_kat_a = js(CA.get(API))
_sahifa = {d["id"]: d for d in _kat_a.get("detallar") or []}
_api_d = {x["id"]: x for m in KT.get("modellar") or [] for x in m.get("detallar") or []}
_farq = [i for i, x in _api_d.items() if not (son(x["narx"]) == son(_sahifa[i]["narx"])
                                              and son(x["narx_qoplamali"]) == son(_sahifa[i]["narx_qoplamali"] if _sahifa[i]["narx_qoplamali"] is not None
                                                                                  else _sahifa[i]["narx_qoplamali_avto"])
                                              and x["chegirma"] == _sahifa[i]["chegirma"])]
check("K18 har narx qatori sahifadagi (Admin katalogi) narx / qoplamali (yozilgan yoki avto) / chegirma bilan AYNAN", not _farq and len(_api_d) == 14,
      (_farq, len(_api_d)))
_SoxtaVaqt.t = datetime(2026, 11, 3, 19, 30)                  # Toshkent 4-noyabr 00:30 — T-1 chegirmasi tugadi
_kt2 = js(dok(KAT, KALIT))
_SoxtaVaqt.t = datetime(2026, 11, 3, 7, 0)
_mt2 = {m["kod"]: m for m in _kt2.get("modellar") or []}.get("T-1", {})
check("K19 Toshkent kuni o'tgach (4-noyabr 00:30) T-1 chegirmasi o'zi yo'qoladi; bugun 2026-11-04",
      _kt2.get("bugun") == "2026-11-04" and _mt2.get("chegirma") is None and ((_mt2.get("detallar") or [{}])[0]).get("chegirma") is None, _mt2)
xavfsiz(lambda d: setattr(d.query(DokonBolim).filter(DokonBolim.id == KAR).first(), "yoqilgan", False))
_mk2 = [m["kod"] for m in js(dok(KAT, KALIT)).get("modellar") or []]
xavfsiz(lambda d: setattr(d.query(DokonBolim).filter(DokonBolim.id == KAR).first(), "yoqilgan", True))
check("K20 bo'lim yashirilsa — uning modellari ham yo'qoladi (K-12)", _mk2 == ["R-18", "T-1", "D-2"], _mk2)
# review236 M1: komplekt modelning butunlay yashirin o'lchami; chegirma faqat yashirin o'lchamga / qisman yashirin o'lchamlarga
M6 = model(KOMP, "R-20", nom="Yashirin o'lchamli")
for _t, _n in (("karniz", 15000), ("podokonnik", 14000), ("nalichnik", 12000), ("kapitel", 30000), ("baza", 30000)):
    detal(M6, _t, ORTA, narx=_n)
    detal(M6, _t, "Maxfiy-Olcham-T236", narx=_n + 1, yoqilgan=False)
M7 = model(KAR, "K-30", nom="Chegirma yashirinda")
detal(M7, "asosiy", "12 sm", narx=40000)
detal(M7, "asosiy", "Sirli-15-T236", narx=41000, yoqilgan=False)
_r = [CA.put(API + f"/modellar/{M7}/chegirma", json={"foiz": 10, "olchamlar": ["Sirli-15-T236"]}),
      CA.put(API + f"/modellar/{M6}/chegirma", json={"foiz": 5, "olchamlar": [ORTA, "Maxfiy-Olcham-T236"]})]
_rk = dok(KAT, KALIT)
_mm = {m["kod"]: m for m in js(_rk).get("modellar") or []}
_m6, _m7 = _mm.get("R-20", {}), _mm.get("K-30", {})
check("K21 komplekt modelning hamma qatori yashirin o'lchami — komplektda YO'Q, nomi javobda uchramaydi (review236 M1)",
      [x.get("olcham") for x in _m6.get("komplekt") or []] == [ORTA] and "Maxfiy-Olcham-T236" not in _rk.text and [x.status_code for x in _r] == [200, 200],
      ([x.get("olcham") for x in _m6.get("komplekt") or []], [x.status_code for x in _r]))
check("K22 chegirma faqat yashirin o'lchamga — model chegirmasi null (chegirmali narxsiz «−10 %» belgisi yo'q), yashirin o'lcham nomi yo'q",
      _m7.get("chegirma") is None and all(x.get("chegirma") is None for x in _m7.get("detallar") or []) and "Sirli-15-T236" not in _rk.text, _m7)
check("K23 chegirma ko'rinadigan va yashirin o'lchamlarga — o'lchamlar ro'yxatida faqat ko'rinadigani (O'rta), komplekt O'rta chegirmali",
      (_m6.get("chegirma") or {}).get("olchamlar") == [ORTA] and ((_m6.get("komplekt") or [{}])[0].get("chegirma") or {}).get("foiz") == 5.0,
      _m6.get("chegirma"))
xavfsiz(lambda d: setattr(d.query(DokonChegirma).filter(DokonChegirma.model_id == M6).first(), "olchamlar", "buzilgan json"))
_m6b = {m["kod"]: m for m in js(dok(KAT, KALIT)).get("modellar") or []}.get("R-20", {})
check("K24 chegirma o'lchamlari bazada buzilgan — hech bir qatorga tegmaydi, model chegirmasi ham null (500 yo'q)",
      _m6b.get("chegirma") is None and all(x.get("chegirma") is None for x in _m6b.get("komplekt") or []), _m6b.get("chegirma"))
for _mid in (M6, M7):
    CA.delete(API + f"/modellar/{_mid}")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Sozlamalar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
for _raq, _izoh in (("+998979995757", "Egasi"), ("+998901112233", "Menejer"), ("+998935554433", None)):
    CA.post(API + "/telefonlar", json={"raqam": _raq, "izoh": _izoh} if _izoh else {"raqam": _raq})
r = dok(SOZ, KALIT)
SZ = js(r)
check("Z1 200, ETag; ish vaqtida (seshanba 12:00) — 3 raqam ko'rinadi, hozir_ish_vaqti=true; ish vaqti «Dushanba–shanba, 8:00–18:00»",
      r.status_code == 200 and r.headers.get("etag") and SZ.get("hozir_ish_vaqti") is True
      and [t.get("raqam") for t in SZ.get("korinadigan_telefonlar") or []] == ["+998979995757", "+998901112233", "+998935554433"]
      and SZ.get("ish_vaqti_matni") == "Dushanba–shanba, 8:00–18:00", SZ)
check("Z2 raqam shakli: raqam, ko'rinishi «+998 97 999 57 57», izoh, doim (birinchisi — doim); id / tartib YO'Q",
      (SZ.get("telefonlar") or [{}])[0] == {"raqam": "+998979995757", "korinish": "+998 97 999 57 57", "izoh": "Egasi", "doim": True}
      and all(set(t) == {"raqam", "korinish", "izoh", "doim"} for t in (SZ.get("telefonlar") or []) + (SZ.get("korinadigan_telefonlar") or [])), SZ)
_SoxtaVaqt.t = datetime(2026, 11, 3, 14, 0)                   # Toshkent 19:00 — ish vaqtidan tashqari
SZ2 = js(dok(SOZ, KALIT))
_SoxtaVaqt.t = datetime(2026, 11, 3, 7, 0)
check("Z3 ish vaqtidan tashqari (19:00) — faqat «doim» raqami ko'rinadi; hamma raqamlar ro'yxati — o'zgarmaydi",
      SZ2.get("hozir_ish_vaqti") is False and [t.get("raqam") for t in SZ2.get("korinadigan_telefonlar") or []] == ["+998979995757"]
      and len(SZ2.get("telefonlar") or []) == 3, SZ2)
check("Z4 retsept — standart (rom 2/2/4/2/2, eshik 2/5/2/2), komplekt o'lchami O'rta, ish vaqti tuzilmasi",
      SZ.get("retsept") == crud.DOKON_RETSEPT_STANDART and SZ.get("komplekt_olcham") == ORTA
      and SZ.get("ish_vaqti") == {"kunlar": [1, 2, 3, 4, 5, 6], "boshi": "08:00", "oxiri": "18:00"}, SZ)
check("Z5 sozlamalar kalitlari — FAQAT ruxsat etilganlar (korxona telefonlari, metrli turlar va boshqa ichki ma'lumot YO'Q)",
      set(SZ) == {"versiya", "hozir_ish_vaqti", "korinadigan_telefonlar", "telefonlar", "ish_vaqti", "ish_vaqti_matni", "ish_izoh", "retsept",
                  "komplekt_olcham", "viloyatlar"}, sorted(SZ))           # kech171 (zip 237): viloyatlar — buyurtma formasi uchun

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. ETag")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r1 = dok(KAT, KALIT)
_et = r1.headers.get("etag", "")
r2 = dok(KAT, KALIT, **{"If-None-Match": _et})
r3 = dok(KAT, KALIT, **{"If-None-Match": '"abc", ' + _et})
r4 = dok(KAT, KALIT, **{"If-None-Match": '"abc"'})
check("E1 If-None-Match = ETag (yoki ro'yxatda) — 304, tana bo'sh, ETag qaytadi; boshqa ETag — 200 va to'liq javob",
      _et and r2.status_code == 304 and r2.content == b"" and r2.headers.get("etag") == _et and r3.status_code == 304
      and r4.status_code == 200 and r4.content == r1.content, (_et, r2.status_code, r3.status_code, r4.status_code))
CA.put(API + f"/detallar/{DID['k12']}", json={"narx": 46000})
r5 = dok(KAT, KALIT, **{"If-None-Match": _et})
check("E2 narx o'zgarsa — eski ETag bilan 200 va yangi narx (yangi ETag)", r5.status_code == 200 and r5.headers.get("etag") != _et
      and any(x.get("narx") == 46000 for m in js(r5).get("modellar") or [] for x in m.get("detallar") or []), (r5.status_code, r5.text[:200]))
r6 = dok(KAT, "pdk_" + "z" * 43, **{"If-None-Match": _et})
check("E3 noto'g'ri kalit + to'g'ri ETag — baribir 401 (304 emas)", r6.status_code == 401, r6.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L. So'rovlar chegarasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("L0 standart chegara — daqiqasiga 120 ta, 60 soniyalik oyna", getattr(crud, "DOKON_API_DAQIQA_MAX", None) == 120
      and getattr(crud, "DOKON_API_OYNA_SEKUND", None) == 60)
_asl_ch = getattr(crud, "_DOKON_API_CHEKLOV", None)
if _asl_ch is not None:
    crud._DOKON_API_CHEKLOV = crud._DokonApiCheklov(3, 60)
_r = [dok(KAT, KALIT).status_code for _ in range(3)]
r = dok(SOZ, KALIT)
check("L1 chegara (sinovda 3 ta) to'lgach — 429, Retry-After (1 … 60 soniya), no-store, sababi o'zbekcha; javobda katalog yo'q",
      _r == [200, 200, 200] and r.status_code == 429 and 1 <= int(r.headers.get("retry-after", "0")) <= 60
      and "no-store" in r.headers.get("cache-control", "") and "So'rovlar juda ko'p" in det(r) and "telefon" not in r.text,
      (_r, r.status_code, dict(r.headers), r.text[:200]))
check("L2 noto'g'ri kalit chegaraga sanalmaydi va 401 (429 emas)", dok(KAT, "pdk_" + "q" * 43).status_code == 401)


def _l3():
    _ch = crud._DokonApiCheklov(2, 60)
    return (_ch.ol(1, 100.0) is None and _ch.ol(1, 110.0) is None and _ch.ol(1, 120.0) == 40 and _ch.ol(2, 120.0) is None
            and _ch.ol(1, 160.5) is None and _ch.ol(1, 165.0) == 5)


check("L3 sirpanuvchi oyna: 2 ta → 3-si kutadi; 60 soniya o'tgach — yana ruxsat; boshqa kalit — alohida hisob", _l3)
if _asl_ch is not None:
    crud._DOKON_API_CHEKLOV = _asl_ch
    _asl_ch.tozala()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Korxona ajratish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
xavfsiz(lambda d: setattr(d.query(Company).filter(Company.id == 2).first(), "dokon_yoqilgan", True))    # sinov: B da ham belgi (platforma faqat egasida yoqadi)
with contextlib.redirect_stdout(io.StringIO()):
    db_ishi(lambda d: crud._dokon_bolimlarni_yarat(d, 2, "t"))
_kb = js(CB.get(API))
_bb = {b.get("nom"): b.get("id") for b in (_kb.get("bolimlar") or [])}
MB = model(_bb.get("Karnizlar"), "B-SIRLI", c=CB, nom="B korxona modeli")
detal(MB, "asosiy", "10 sm", c=CB, narx=61111)
rb = yarat(CB)
KB = js(rb).get("kalit") or ""
check("T1 B korxona admini o'z kalitini yaratdi (A ning kaliti o'zgarmadi)", rb.status_code == 200 and KALIT_RE.fullmatch(KB) and KB != KALIT
      and dok(KAT, KALIT).status_code == 200, (rb.status_code, rb.text[:200]))
_ka, _kbj = dok(KAT, KALIT), dok(KAT, KB)
check("T2 A kaliti — faqat A modellari (B-SIRLI yo'q); B kaliti — faqat B modeli (R-18 va A narxlari yo'q)",
      "B-SIRLI" not in _ka.text and "61111" not in _ka.text and [m["kod"] for m in js(_kbj).get("modellar") or []] == ["B-SIRLI"]
      and "R-18" not in _kbj.text and "15000" not in _kbj.text, (_ka.text[:100], _kbj.text[:300]))
_r = [DOK.get(KAT + "?company_id=2", headers={"X-Dokon-Kalit": KALIT}), DOK.get(KAT, headers={"X-Dokon-Kalit": KALIT, "X-Company-Id": "2"}),
      DOK.get(KAT, headers={"X-Dokon-Kalit": KALIT}, cookies=CB.cookies)]
check("T3 so'rovdagi korxona raqami (?company_id=2, X-Company-Id, B sessiya cookie si) e'tiborga olinmaydi — A kaliti baribir faqat A",
      all(x.status_code == 200 and "B-SIRLI" not in x.text and "R-18" in x.text for x in _r), [(x.status_code, x.text[:80]) for x in _r])
_szb = js(dok(SOZ, KB))
check("T4 B sozlamalari — A ning telefonlari YO'Q", _szb.get("telefonlar") == [] and "979995757" not in json.dumps(_szb), _szb)
xavfsiz(lambda d: setattr(d.query(Company).filter(Company.id == 2).first(), "dokon_yoqilgan", False))
_r = [dok(KAT, KB), dok(SOZ, KB)]
check("T5 B da sayt katalogi o'chirildi — B kaliti 404 (katalog yo'q); A kaliti ishlaydi",
      [x.status_code for x in _r] == [404, 404] and "B-SIRLI" not in _r[0].text and dok(KAT, KALIT).status_code == 200,
      [(x.status_code, x.text[:80]) for x in _r])
xavfsiz(lambda d: setattr(d.query(Company).filter(Company.id == 1).first(), "dokon_yoqilgan", False))
_r = dok(KAT, KALIT)
xavfsiz(lambda d: setattr(d.query(Company).filter(Company.id == 1).first(), "dokon_yoqilgan", True))
check("T6 A da belgi o'chiq — A kaliti ham 404; qayta yoqilsa — 200", _r.status_code == 404 and dok(KAT, KALIT).status_code == 200, _r.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Zaxira")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_zx = db_ishi(lambda d: crud.export_full_backup(d, 1))
_zx_matn = json.dumps(_zx, ensure_ascii=False, default=str)
_xesh_a = __import__("hashlib").sha256(KALIT.encode()).hexdigest()
check("B1 korxona zaxirasida `dokon_api_kalitlar` YO'Q; zaxira matnida xom kalit va xeshi yo'q (boshi — faqat jurnal yozuvida)",
      "dokon_api_kalitlar" not in (_zx.get("tables") or {}) and KALIT not in _zx_matn and _xesh_a not in _zx_matn
      and "dokon_detallar" in (_zx.get("tables") or {})
      and all(KALIT[:10] not in json.dumps(v, ensure_ascii=False, default=str) for k, v in (_zx.get("tables") or {}).items() if k != "activity_logs"),
      [k for k, v in (_zx.get("tables") or {}).items() if KALIT[:10] in json.dumps(v, ensure_ascii=False, default=str)])
r = yarat(almashtir=True)
KALIT_YANGI = js(r).get("kalit") or ""
try:
    with contextlib.redirect_stdout(io.StringIO()):
        _tik = db_ishi(lambda d: crud.import_full_backup(d, _zx, 1, replace=True))
    _tik_x = ""
except Exception as _e:                    # noqa: BLE001
    _tik, _tik_x = None, f"{type(_e).__name__}: {_e}"
check("B2 zaxiradan tiklash (almashtirish o'rniga): tiklash muvaffaqiyatli; YANGI kalit ishlaydi, zaxira paytidagi eski kalit — 401 (tirilmaydi)",
      _tik is not None and dok(KAT, KALIT_YANGI).status_code == 200 and dok(KAT, KALIT).status_code == 401, (_tik_x, str(_tik)[:300]))
KALIT = KALIT_YANGI
check("B3 tiklangan katalog do'kon yo'lidan ham ko'rinadi (R-18 bor)", "R-18" in dok(KAT, KALIT).text)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PG parallel")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if not PG_URL:
    print("  (faqat PG rejimida)")
else:
    CA.delete(AK)
    _c2 = mijoz("t236_admin")
    _nat, _b = [], threading.Barrier(2)

    def _yarat_ip(c):
        _b.wait()
        _nat.append(yarat(c))
    _t = [threading.Thread(target=_yarat_ip, args=(c,)) for c in (CA, _c2)]
    [t.start() for t in _t]
    [t.join() for t in _t]
    _sts = sorted(x.status_code for x in _nat)
    _ok = [x for x in _nat if x.status_code == 200]
    check("P1 ikki oynadan bir vaqtda «Kalit yaratish» — bittasi 200, ikkinchisi 409 (500 / deadlock yo'q); ishlaydigani — 200 olganniki",
          _sts == [200, 409] and len(_ok) == 1 and dok(KAT, js(_ok[0]).get("kalit")).status_code == 200,
          [(x.status_code, x.text[:100]) for x in _nat])
    KALIT = js(_ok[0]).get("kalit") if _ok else KALIT
    _hato, _st_d, _toxta = [], [], threading.Event()

    def _dokon_ip():
        cl = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
        while not _toxta.is_set():
            _st_d.append(cl.get(KAT, headers={"X-Dokon-Kalit": KALIT}).status_code)
    _td = [threading.Thread(target=_dokon_ip) for _ in range(3)]
    [t.start() for t in _td]
    _alm = []
    for _ in range(4):
        _alm.append(yarat(almashtir=True).status_code)
    _toxta.set()
    [t.join() for t in _td]
    check("P2 almashtirish (4 marta) ∥ do'kon so'rovlari (3 oqim) — faqat 200 / 401, 500 yo'q; almashtirishlar 200",
          _alm == [200, 200, 200, 200] and _st_d and set(_st_d) <= {200, 401}, (_alm, sorted(set(_st_d)), len(_st_d)))
    KALIT = None

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
br = pw_ctx = server = None
if TEZ:
    print("  (T236_TEZ=1 — o'tkazildi)")
elif PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
    CA.delete(AK)
    try:
        from playwright.sync_api import sync_playwright
        PW_BOR, _pw_x = True, ""
    except Exception as _e:                # noqa: BLE001
        PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
    import uvicorn                                 # noqa: E402

    def _port():
        so = socket.socket()
        so.bind(("127.0.0.1", 0))
        p = so.getsockname()[1]
        so.close()
        return p

    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    B = f"http://127.0.0.1:{port}"
    if PW_BOR and server.started:
        pw_ctx = sync_playwright().start()
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                  "chrome-linux", "chrome"))):
            _exe = _yol
        try:
            br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
        except Exception as _e:            # noqa: BLE001
            br = None
            _pw_x = f"{type(_e).__name__}: {_e}"
    check("U0 lokal server va Chromium", bool(server.started and br), _pw_x)
    JS_XATO, KONSOL = [], []

    def kontekst(login, kenglik=1440):
        ctx = br.new_context(viewport={"width": kenglik, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
        try:
            ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=B)
        except Exception:                  # noqa: BLE001
            pass
        ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
        pg.on("console", lambda m: KONSOL.append(m.text[:200]) if m.type == "error" else None)
        pg.goto(B + "/login")
        pg.fill("input[name=username]", login)
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
        return ctx, pg

    def kut(pg, ifoda, ms=10000):
        try:
            pg.wait_for_function(ifoda, timeout=ms)
            return True
        except Exception:                  # noqa: BLE001
            return False

    def matn(pg, sel):
        return pg.evaluate(f"(document.querySelector(\"{sel}\") || {{}}).innerText || ''")

    def tasdiqla(pg):
        pg.wait_for_selector("#ccModalOk", state="visible")
        pg.click("#ccModalOk")

    if br:
        try:
            ctx, pg = kontekst("t236_ui")
            pg.goto(B + "/sayt-katalogi")
            pg.wait_for_load_state("networkidle")
            pg.click("details[data-sht=sk-api] > summary")
            check("U1 kartochka: «Kalit yo'q», faqat «🔑 Kalit yaratish» tugmasi, shtorka holati «kalit yo'q»",
                  kut(pg, "document.getElementById('skApiYarat') !== null") and "Kalit yo'q" in matn(pg, "#skApiHolat")
                  and pg.locator("#skApiTugmalar .btn").count() == 1 and "kalit yo'q" in matn(pg, "#skApiHolatQisqa"),
                  (matn(pg, "#skApiHolat"), matn(pg, "#skApiHolatQisqa")))
            pg.click("#skApiYarat")
            _ok = kut(pg, "document.getElementById('skApiKalit') !== null")
            U1 = pg.input_value("#skApiKalit") if _ok else ""
            check("U2 «Kalit yaratish» — yangi kalit maydonda (faqat o'qish), fokusda va belgilangan; holat «Kalit bor: pdk_…»; ogohlantirish matni",
                  _ok and KALIT_RE.fullmatch(U1) and pg.evaluate("document.getElementById('skApiKalit').readOnly")
                  and pg.evaluate("document.activeElement && document.activeElement.id") == "skApiKalit"
                  and U1[:10] in matn(pg, "#skApiHolat") and "faqat hozir ko'rsatiladi" in matn(pg, "#skApiYangi"),
                  (U1, matn(pg, "#skApiHolat")))
            check("U3 sahifadagi kalit — ishlaydi (do'kon yo'li 200)", dok(KAT, U1).status_code == 200)
            check("U4 «yaratgan» ismi (HTML belgilar bilan) — matn sifatida (img chizilmadi, skript ishlamadi)",
                  "<img src=x" in matn(pg, "#skApiHolat") and pg.evaluate("window.__xss236 === undefined")
                  and pg.locator("#skApiHolat img").count() == 0, matn(pg, "#skApiHolat"))
            pg.click("#skApiHolat")                                    # maydondan chiqish (blur) — umumiy «birinchi harf katta» qoidasi
            time.sleep(0.2)
            check("U4b maydondan chiqqanda kalit O'ZGARMAYDI (birinchi harf katta qilinmaydi)", pg.input_value("#skApiKalit") == U1,
                  pg.input_value("#skApiKalit")[:12])
            pg.click("#skApiNusxa")
            _clip = ""
            try:
                _clip = pg.evaluate("navigator.clipboard.readText()")
            except Exception:              # noqa: BLE001
                _clip = ""
            check("U5 «📋 Nusxa olish» — kalit buferda", _clip == U1, (_clip[:12], U1[:12]))
            pg.set_viewport_size({"width": 375, "height": 812})
            time.sleep(0.3)
            check("U6 375 px: gorizontal toshish yo'q (kalit maydoni sig'adi), tugmalar ko'rinadi",
                  pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                  and pg.locator("#skApiNusxa").is_visible(), pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]"))
            pg.set_viewport_size({"width": 1440, "height": 900})
            pg.click("#skApiYop")
            check("U7 «Yopish» — kalit sahifadan olib tashlandi (DOM da yo'q), tugmalar: «Yangi kalit», «O'chirish»",
                  kut(pg, "document.getElementById('skApiKalit') === null") and U1 not in pg.content()
                  and pg.locator("#skApiAlmashtir").count() == 1 and pg.locator("#skApiOchir").count() == 1)
            pg.click("#skApiAlmashtir")
            pg.wait_for_selector("#ccModalOk", state="visible")
            pg.click("#ccModalCancel")
            time.sleep(0.4)
            check("U8 «Yangi kalit» → tasdiqda «Bekor» — kalit o'zgarmadi", dok(KAT, U1).status_code == 200 and pg.locator("#skApiKalit").count() == 0)
            pg.click("#skApiAlmashtir")
            tasdiqla(pg)
            _ok = kut(pg, "document.getElementById('skApiKalit') !== null")
            U2 = pg.input_value("#skApiKalit") if _ok else ""
            check("U9 «Yangi kalit» → tasdiq — yangi kalit ko'rsatildi, eskisi 401, yangisi 200",
                  _ok and KALIT_RE.fullmatch(U2) and U2 != U1 and dok(KAT, U1).status_code == 401 and dok(KAT, U2).status_code == 200, (U1[:10], U2[:10]))
            pg.reload()
            pg.wait_for_load_state("networkidle")
            pg.click("details[data-sht=sk-api] > summary")
            kut(pg, "document.getElementById('skApiAlmashtir') !== null")
            check("U10 sahifa yangilansa — kalit qayta ko'rsatilmaydi (faqat boshi)", U2 not in pg.content() and U2[:10] in matn(pg, "#skApiHolat"))
            pg.click("#skApiOchir")
            tasdiqla(pg)
            check("U11 «O'chirish» → tasdiq — «Kalit yo'q», kalit 401", kut(pg, "document.getElementById('skApiYarat') !== null")
                  and dok(KAT, U2).status_code == 401 and "Kalit yo'q" in matn(pg, "#skApiHolat"))
            _qolgan = [0]

            def _uzil(route):
                _qolgan[0] += 1
                route.abort()
            pg.route("**/api/sayt-katalogi/api-kalit", lambda route: _uzil(route) if route.request.method == "POST" else route.continue_())
            pg.click("#skApiYarat")
            _faol = kut(pg, "document.getElementById('skApiYarat') && !document.getElementById('skApiYarat').disabled", 30000)
            check("U12 tarmoq uzildi — xato xabari, kalit ko'rsatilmadi, holat qayta o'qildi (tugma qayta faol)",
                  _faol and _qolgan[0] == 1 and pg.locator("#skApiKalit").count() == 0, (_faol, _qolgan[0]))
            pg.unroute("**/api/sayt-katalogi/api-kalit")
            pg.evaluate("localStorage.setItem('erp_script', 'kirill')")
            pg.reload()
            pg.wait_for_load_state("networkidle")
            pg.click("details[data-sht=sk-api] > summary")
            kut(pg, "document.getElementById('skApiYarat') !== null")
            pg.click("#skApiYarat")
            _ok = kut(pg, "document.getElementById('skApiKalit') !== null")
            time.sleep(1.0)                                             # Kirill o'giruvchisi har 400 ms da maydonlarni ko'radi
            pg.click("#skApiHolat")
            time.sleep(1.0)
            U3 = pg.input_value("#skApiKalit") if _ok else ""
            _b = pg.evaluate("(document.querySelector('#skApiHolat b') || {}).textContent || ''")
            check("U14 Kirill ko'rinishida: kalit maydoni va boshi — lotin harflarida (o'girilmaydi), kalit ishlaydi; sahifa matni — kirill",
                  lambda: KALIT_RE.fullmatch(U3) and _b == U3[:10] + "…" and dok(KAT, U3).status_code == 200
                  and re.search("[А-Яа-яЎўҚқҒғҲҳ]", matn(pg, "#skApiYangi")) and "X-Dokon-Kalit" in matn(pg, "#skApiYangi")
                  and "/api/dokon/v1/katalog" in matn(pg, "#skApiHolat"), (U3[:12], _b, matn(pg, "#skApiYangi")[:200]))
            pg.evaluate("localStorage.setItem('erp_script', 'lotin')")
            _rb = yarat(almashtir=True)                                 # boshqa oyna kalitni almashtirdi
            U4k = js(_rb).get("kalit") or ""
            pg.click("#skApiAlmashtir")
            tasdiqla(pg)
            time.sleep(1.2)
            check("U15 boshqa oynada almashtirilgan kalitni bu oynada «Yangi kalit» — 409, o'lik kalit «yangi» deb ko'rsatilmaydi (sariq blok yo'q), "
                  "holat — boshqa oynaning kaliti boshi; o'sha kalit ishlayveradi (review236 L2 / M2)",
                  lambda: _rb.status_code == 200 and pg.locator("#skApiKalit").count() == 0 and U4k[:10] in matn(pg, "#skApiHolat")
                  and dok(KAT, U4k).status_code == 200 and dok(KAT, U3).status_code == 401, (_rb.status_code, matn(pg, "#skApiHolat")))
            check("U13 JS xatosi / konsol xatosi yo'q", not JS_XATO and not [k for k in KONSOL if "Failed to load resource" not in k], (JS_XATO, KONSOL))
            ctx.close()
        except Exception as _e:            # noqa: BLE001
            check("U* brauzer bo'limi xatosiz", False, f"{type(_e).__name__}: {_e}")
    if br:
        br.close()
    if pw_ctx:
        pw_ctx.stop()
    if server:
        server.should_exit = True

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
