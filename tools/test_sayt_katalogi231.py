#!/usr/bin/env python3
"""
test_sayt_katalogi231.py — kech166 (zip 231 «Sayt katalogi» poydevori; egasi QARORLARI «Onlayn do'kon rejasi» 30.10, 31.10 «Onlayn do'kon»).

NIMA UCHUN KERAK
  Onlayn do'kon katalogi va narxlari ERP ichida turadi (Google Sheets emas): bo'lim → model → narx qatori (detal turi × o'lcham;
  oddiy / qoplamali / ulgurji narx). Do'kon FAQAT platforma egasining korxonasida (PenoDecorPro) — SaaS mijoz korxonalarga hech
  narsa ko'rinmasin va ularning ishi o'zgarmasin. Ulgurji narx — maxfiy: faqat Admin.
BO'LIMLAR
  S — statik: ustun, jadvallar, `_TENANT_REFS`, zaxira tartibi (bola otadan OLDIN), marshrutlar.
  A — API: belgi o'chiq — 404 (sahifa, API), menyuda yo'q; Platforma: faqat platforma admini, faqat o'z korxonasi (mijoz — 400),
      birinchi yoqishda 9 standart bo'lim (tartib, tizim kalitlari), qayta yoqish — takrorsiz; Menejer — 403; bo'lim / model / narx
      qatori CRUD va tekshiruvlar (noma'lum kalit, uzun / bo'sh matn, qolip, tizim bo'limi qoidalari, takror nom / kod / qator, narx 0 /
      manfiy / NaN / mantiqiy / satr / juda katta, yaxlitlash, birlik serverda, avto qoplamali narx 1 000 ga, koeffitsient);
      o'zgarishsiz saqlash — jurnalga yozilmaydi; ikki korxona — begona yozuvga tegilmaydi (404 / 400), qo'riqchi (TenantMismatchError);
      zaxira → tiklash; o'chirish — ma'lumot qoladi.
  P — PG parallel: bir xil kodli ikki model, bir xil ikki narx qatori, bir xil nomli ikki bo'lim — bittasi saqlanadi, 500 yo'q.
  U — HAQIQIY brauzer: sahifa, bo'limlar, model qo'shish, narx qatori, katakni o'zgartirish (server qiymati), Platforma tugmasi, JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (U bo'limi faqat SQLite / TF1 da).
Asl kodga (zip 230) qarshi QULAMAYDI — yiqiladi (marshrut / jadval yo'q).
ISHLATISH: python3 tools/test_sayt_katalogi231.py
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

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "sayt231_test"
_T = tempfile.mkdtemp(prefix="t231_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't231.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, ActivityLog, ErrorLog   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

DokonBolim = getattr(models, "DokonBolim", None)    # asl kodda (zip 230) yo'q — sinov qulamasin
DokonModel = getattr(models, "DokonModel", None)
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
    """Asl kodda (jadval / ustun yo'q) sinov qulamasin — xato bo'lsa `std`."""
    try:
        return db_ishi(fn)
    except Exception:                      # noqa: BLE001
        return std


def soni(cls, cid=None):
    if cls is None:
        return -1

    def _f(d):
        q = d.query(cls)
        if cid is not None:
            q = q.filter(cls.company_id == cid)
        return q.count()
    return db_ishi(_f)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: korxona 1 — platforma egasi (platforma admini shu korxonada), korxona 2 — mijoz
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T231 B mijoz korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t231_admin", PAROL, UserRole.ADMIN, "T231 Admin", company_id=1)
    auth.create_user(s, "t231_plat", PAROL, UserRole.ADMIN, "T231 Platforma", company_id=1)
    auth.create_user(s, "t231_men", PAROL, UserRole.MANAGER, "T231 Menejer", company_id=1)
    auth.create_user(s, "t231_b", PAROL, UserRole.ADMIN, "T231 B Admin", company_id=2)
_pu = s.query(User).filter(User.username == "t231_plat").first()
_pu.is_platform_admin = True
s.commit()
s.close()
main._send_telegram = lambda msg, *a, **k: True


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t231_admin")
CP = mijoz("t231_plat")
CM = mijoz("t231_men")
CB = mijoz("t231_b")
API = "/api/sayt-katalogi"


def jurnal(entity, cid=1):
    return db_ishi(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == entity,
                                                       ActivityLog.company_id == cid).count())


def katalog(c=CA):
    d = js(c.get(API))
    d = d if isinstance(d, dict) else {}
    return {"bolimlar": [], "modellar": [], "detallar": [], "koeff": None, **d}


def detal(i, c=CA):
    return next((d for d in katalog(c)["detallar"] if d.get("id") == i), {})


def model(i, c=CA):
    return next((m for m in katalog(c)["modellar"] if m.get("id") == i), {})


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("S1 `companies.dokon_yoqilgan` ustuni va uch jadval", hasattr(Company, "dokon_yoqilgan") and DokonBolim is not None
      and DokonModel is not None and DokonDetal is not None
      and {DokonBolim.__tablename__, DokonModel.__tablename__, DokonDetal.__tablename__} ==
      {"dokon_bolimlar", "dokon_modellar", "dokon_detallar"})
_refs = getattr(models, "_TENANT_REFS", {})
check("S2 `_TENANT_REFS`: model → bo'lim, narx qatori → model",
      ("bolim_id", "DokonBolim") in _refs.get("DokonModel", []) and ("model_id", "DokonModel") in _refs.get("DokonDetal", []))
_tart = [c.__name__ for c in crud._reset_table_order()]
check("S3 zaxira / tiklash tartibi: DokonDetal → DokonModel → DokonBolim (bola otadan OLDIN)",
      all(n in _tart for n in ("DokonDetal", "DokonModel", "DokonBolim"))
      and _tart.index("DokonDetal") < _tart.index("DokonModel") < _tart.index("DokonBolim"), _tart[-8:])
_yol = {(m, r.path) for r in main.app.routes for m in (getattr(r, "methods", None) or ())}
_kerak = {("GET", "/sayt-katalogi"), ("GET", API), ("POST", API + "/bolimlar"), ("PUT", API + "/bolimlar/{bolim_id}"),
          ("DELETE", API + "/bolimlar/{bolim_id}"), ("POST", API + "/modellar"), ("PUT", API + "/modellar/{model_id}"),
          ("DELETE", API + "/modellar/{model_id}"), ("POST", API + "/detallar"), ("PUT", API + "/detallar/{detal_id}"),
          ("DELETE", API + "/detallar/{detal_id}"), ("PUT", API + "/koeff"), ("POST", "/api/platform/companies/{company_id}/dokon")}
check("S4 13 ta yangi marshrut", _kerak <= _yol, sorted(_kerak - _yol))
_base = open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8").read()
check("S5 menyu havolasi — FAQAT Admin va belgi yoqilgan (`sayt_katalogi_bormi`)",
      "{% if m_admin and sayt_katalogi_bormi(current_user) %}" in _base and 'href="/sayt-katalogi"' in _base)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = CA.get("/sayt-katalogi")
_r2 = CA.get(API)
_r3 = CA.post(API + "/bolimlar", json={"nom": "X", "qolip": "dona"})
check("A1 belgi o'chiq — sahifa, katalog, yozish — 404", _r.status_code == 404 and _r2.status_code == 404 and _r3.status_code == 404,
      (_r.status_code, _r2.status_code, _r3.status_code))
check("A1b belgi o'chiq — menyuda havola yo'q", 'href="/sayt-katalogi"' not in CA.get("/dashboard").text)
check("A1c belgi o'chiq — koeffitsient (noto'g'ri tana bilan ham) — 404", CA.put(API + "/koeff", json={}).status_code == 404
      and CA.put(API + "/koeff", json={"koeff": 2}).status_code == 404)

_r = CA.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
check("A2 oddiy Admin Platforma belgisini o'zgartira olmaydi (403)", _r.status_code == 403, _r.status_code)
_r = CP.post("/api/platform/companies/2/dokon", data={"yoqilgan": "1"})
check("A3 mijoz korxonaga yoqilmaydi — 400, belgi NULL, bo'lim yaratilmadi",
      _r.status_code == 400 and not xavfsiz(lambda d: d.get(Company, 2).dokon_yoqilgan) and soni(DokonBolim, 2) == 0,
      (_r.status_code, _r.text[:200]))
_r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "2"})
check("A3b noto'g'ri qiymat — 400", _r.status_code == 400, _r.status_code)
_j0 = jurnal("company")
_r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
_k = katalog()
_nomlar = [b["nom"] for b in _k.get("bolimlar", [])]
check("A4 o'z korxonasida yoqildi — 9 standart bo'lim (tartib bilan), tizim kalitlari",
      _r.status_code == 200 and js(_r).get("yaratilgan_bolimlar") == 9 and _nomlar == [
          "Tayyor mahsulotlar", "Rom va eshik dekorlari", "Karnizlar", "Ustunlar va pilyastrlar", "Termopanel",
          "Rustlar va burchak toshlari", "Dekor elementlar", "O'z o'lchamingiz bilan", "Ulgurji"]
      and [b["tizim_kaliti"] for b in _k["bolimlar"] if b["tizim_kaliti"]] == ["tayyor", "oz_olcham", "ulgurji"],
      (_r.status_code, _r.text[:200], _nomlar))
check("A4b yoqish korxona jurnaliga yozildi", jurnal("company") == _j0 + 1, (_j0, jurnal("company")))
_r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
check("A4c qayta yoqish — takror bo'lim yo'q, jurnal o'zgarmadi",
      _r.status_code == 200 and js(_r).get("ozgardi") is False and soni(DokonBolim, 1) == 9 and jurnal("company") == _j0 + 1,
      (_r.status_code, soni(DokonBolim, 1)))
_pl = js(CP.get("/api/platform/companies"))
_pl = _pl if isinstance(_pl, list) else (_pl.get("korxonalar") or _pl.get("royxat") or [])
check("A4d Platforma ro'yxatida `dokon_yoqilgan`", any(r.get("id") == 1 and r.get("dokon_yoqilgan") is True for r in _pl)
      and any(r.get("id") == 2 and r.get("dokon_yoqilgan") is False for r in _pl), str(_pl)[:300])
check("A5 yoqilgach: sahifa 200, menyuda havola (Admin)", CA.get("/sayt-katalogi").status_code == 200
      and 'href="/sayt-katalogi"' in CA.get("/dashboard").text)
_rm = CM.get(API)
check("A6 Menejer — 403 (sahifa, API, yozish), menyuda havola yo'q",
      _rm.status_code == 403 and CM.get("/sayt-katalogi").status_code in (302, 303, 403)
      and CM.post(API + "/bolimlar", json={"nom": "M", "qolip": "dona"}).status_code == 403
      and 'href="/sayt-katalogi"' not in CM.get("/orders").text, _rm.status_code)
check("A7 mijoz korxona Admini — 404 (uning korxonasida yoqilmagan)", CB.get(API).status_code == 404
      and CB.get("/sayt-katalogi").status_code == 404)

_B = {b["tizim_kaliti"] or b["nom"]: b for b in _k.get("bolimlar", [])}
ROM = _B.get("Rom va eshik dekorlari", {}).get("id")
KARNIZ = _B.get("Karnizlar", {}).get("id")
USTUN = _B.get("Ustunlar va pilyastrlar", {}).get("id")
TERMO = _B.get("Termopanel", {}).get("id")
TAYYOR = _B.get("tayyor", {}).get("id")
DEKOR = _B.get("Dekor elementlar", {}).get("id")

# Bo'limlar
_j0 = jurnal("dokon_bolim")
_r = CA.post(API + "/bolimlar", json={"nom": "  Arkalar   va  gumbazlar ", "qolip": "juft_metr"})
ARKA = js(_r).get("id")
check("A8 yangi bo'lim — nom tozalandi, oxirgi tartib, jurnal",
      _r.status_code == 200 and js(_r).get("nom") == "Arkalar va gumbazlar" and js(_r).get("tartib") == 10
      and jurnal("dokon_bolim") == _j0 + 1, _r.text[:200])
for _n, _tana, _kut in (
        ("A9a takror nom (katta / kichik harf)", {"nom": "arkalar VA gumbazlar", "qolip": "dona"}, 400),
        ("A9b qolip noto'g'ri", {"nom": "Y1", "qolip": "litr"}, 400),
        ("A9c qolipsiz", {"nom": "Y2"}, 400),
        ("A9d noma'lum kalit (company_id)", {"nom": "Y3", "qolip": "dona", "company_id": 2}, 400),
        ("A9e juda uzun nom", {"nom": "Q" * 81, "qolip": "dona"}, 400),
        ("A9f bo'sh nom", {"nom": "   ", "qolip": "dona"}, 400),
        ("A9g nom matn emas", {"nom": 5, "qolip": "dona"}, 400),
        ("A9h tizim kaliti yuborib bo'lmaydi", {"nom": "Y4", "qolip": "dona", "tizim_kaliti": "tayyor"}, 400)):
    _r = CA.post(API + "/bolimlar", json=_tana)
    check(_n + f" — {_kut}", _r.status_code == _kut, (_r.status_code, _r.text[:160]))
check("A9i rad etilganlar bazaga yozilmadi", soni(DokonBolim, 1) == 10, soni(DokonBolim, 1))
_r = CA.put(API + f"/bolimlar/{TAYYOR}", json={"nom": "Ombordagi tovarlar", "tartib": 1, "yoqilgan": True})
check("A10 tizim bo'limi — nomi o'zgaradi", _r.status_code == 200 and js(_r).get("nom") == "Ombordagi tovarlar", _r.text[:200])
_r = CA.put(API + f"/bolimlar/{TAYYOR}", json={"qolip": "dona"})
check("A10b tizim bo'limi qolipi o'zgarmaydi — 400", _r.status_code == 400, _r.status_code)
check("A10c tizim bo'limi o'chirilmaydi — 400", CA.delete(API + f"/bolimlar/{TAYYOR}").status_code == 400)
_r = CA.post(API + "/modellar", json={"bolim_id": TAYYOR, "kod": "T-1"})
check("A10d tizim bo'limiga model qo'shilmaydi — 400", _r.status_code == 400, _r.text[:200])
_j1 = jurnal("dokon_bolim")
_r = CA.put(API + f"/bolimlar/{ARKA}", json={"nom": "Arkalar va gumbazlar", "tartib": 10, "yoqilgan": True})
check("A11 o'zgarishsiz saqlash — 200, jurnalga yozilmadi", _r.status_code == 200 and jurnal("dokon_bolim") == _j1,
      (_r.status_code, _j1, jurnal("dokon_bolim")))
_r = CA.put(API + f"/bolimlar/{ARKA}", json={"tartib": -1})
_r2 = CA.put(API + f"/bolimlar/{ARKA}", json={"tartib": 1.5})
_r3 = CA.put(API + f"/bolimlar/{ARKA}", json={"yoqilgan": "ha"})
check("A11b tartib manfiy / kasr, yoqilgan satr — 400", (_r.status_code, _r2.status_code, _r3.status_code) == (400, 400, 400))
check("A11c mavjud bo'lmagan / juda katta raqam — 404 / 422",
      CA.put(API + "/bolimlar/999999", json={"nom": "Z"}).status_code == 404
      and CA.put(API + "/bolimlar/99999999999", json={"nom": "Z"}).status_code == 422
      and CA.delete(API + "/bolimlar/0").status_code == 422)

# Modellar
_r = CA.post(API + "/modellar", json={"bolim_id": ROM, "kod": " r-18 ", "nom": "Klassik", "kapitel_baza_bor": True,
                                      "tavsif": "Uch o'lchamda.\r\n  Kapitel bilan "})
R18 = js(_r).get("id")
check("A12 rom modeli — kod katta harfda, qolip bo'limdan (komplekt), tavsif qatorlari saqlandi",
      _r.status_code == 200 and js(_r).get("kod") == "R-18" and js(_r).get("qolip") == "komplekt"
      and js(_r).get("tavsif") == "Uch o'lchamda.\nKapitel bilan", _r.text[:300])
check("A12b takror kod (kichik harf bilan) — 400", CA.post(API + "/modellar", json={"bolim_id": KARNIZ, "kod": "r-18"}).status_code == 400)
check("A12c mavjud bo'lmagan bo'lim — 400", CA.post(API + "/modellar", json={"bolim_id": 999999, "kod": "Q-1"}).status_code == 400)
check("A12d bo'lim raqami satr — 400", CA.post(API + "/modellar", json={"bolim_id": str(ROM), "kod": "Q-2"}).status_code == 400)
_r = CA.post(API + "/modellar", json={"bolim_id": USTUN, "kod": "DU-1", "nom": "Dumaloq ustun", "qolip": "butun_metr",
                                      "kapitel_baza_bor": True})
DU1 = js(_r).get("id")
check("A13 «Ustunlar» bo'limida dumaloq ustun — o'z qolipi (butun metr)", _r.status_code == 200 and js(_r).get("qolip") == "butun_metr",
      _r.text[:200])
_r = CA.post(API + "/modellar", json={"bolim_id": TERMO, "kod": "TP-2", "nom": "Termopanel"})
TP2 = js(_r).get("id")
_r = CA.post(API + "/modellar", json={"bolim_id": KARNIZ, "kod": "K-3"})
K3 = js(_r).get("id")
_r = CA.post(API + "/modellar", json={"bolim_id": DEKOR, "kod": "D-1"})
D1 = js(_r).get("id")

# Narx qatorlari
_j0 = jurnal("dokon_detal")
_r = CA.post(API + "/detallar", json={"model_id": R18, "turi": "karniz", "olcham": "O'rta", "eni_sm": 15,
                                      "narx": 12345, "ulgurji_narx": 20000})
D_KAR = js(_r).get("id")
check("A14 rom karnizi — birlik metr, avto qoplamali 24 690 → 25 000 (1 000 ga), ulgurji avto 40 000, jurnal",
      _r.status_code == 200 and js(_r).get("birlik") == "metr" and js(_r).get("narx_qoplamali_avto") == 25000
      and js(_r).get("ulgurji_qoplamali_avto") == 40000 and js(_r).get("narx_qoplamali") is None
      and jurnal("dokon_detal") == _j0 + 1, _r.text[:300])
_r = CA.post(API + "/detallar", json={"model_id": R18, "turi": "kapitel", "olcham": "O'rta", "narx": 30000,
                                      "narx_qoplamali": 45000})
D_KAP = js(_r).get("id")
check("A15 kapitel — birlik dona, alohida qoplamali narx (avto yo'q)",
      _r.status_code == 200 and js(_r).get("birlik") == "dona" and js(_r).get("narx_qoplamali") == 45000
      and js(_r).get("narx_qoplamali_avto") is None, _r.text[:300])
check("A15b komplekt modelida «asosiy» turi — 400",
      CA.post(API + "/detallar", json={"model_id": R18, "turi": "asosiy", "olcham": "O'rta"}).status_code == 400)
check("A15c takror qator (o'lcham katta / kichik harf) — 400",
      CA.post(API + "/detallar", json={"model_id": R18, "turi": "karniz", "olcham": "o'rta"}).status_code == 400)
check("A15d kapitel / bazasiz modelda kapitel — 400",
      CA.post(API + "/detallar", json={"model_id": K3, "turi": "kapitel", "olcham": "15 sm"}).status_code == 400)
check("A15e karniz modelida «podokonnik» turi — 400",
      CA.post(API + "/detallar", json={"model_id": K3, "turi": "podokonnik", "olcham": "15 sm"}).status_code == 400)
_r = CA.post(API + "/detallar", json={"model_id": TP2, "turi": "asosiy", "olcham": "4 sm", "qalinligi_sm": 4, "narx": 95000.004})
check("A16 termopanel — birlik m2, narx 2 xonaga (95 000,00)", _r.status_code == 200 and js(_r).get("birlik") == "m2"
      and js(_r).get("narx") == 95000.0, _r.text[:200])
_r = CA.post(API + "/detallar", json={"model_id": DU1, "turi": "asosiy", "olcham": "25 sm", "eni_sm": 25, "qalinligi_sm": 25,
                                      "narx": 100000.005})
check("A16b dumaloq ustun — metr, 100 000,005 → 100 000,01 (HALF_UP)", _r.status_code == 200 and js(_r).get("birlik") == "metr"
      and js(_r).get("narx") == 100000.01, _r.text[:200])
_r = CA.post(API + "/detallar", json={"model_id": DU1, "turi": "baza", "olcham": "25 sm", "narx": 40000})
check("A16c dumaloq ustun bazasi — dona", _r.status_code == 200 and js(_r).get("birlik") == "dona", _r.text[:200])
_r = CA.post(API + "/detallar", json={"model_id": D1, "turi": "asosiy", "olcham": "Standart", "narx": 70000})
D_DEK = js(_r).get("id")
check("A16d dekor — dona", _r.status_code == 200 and js(_r).get("birlik") == "dona", _r.text[:200])
_n0 = soni(DokonDetal, 1)
for _n, _tana in (("narx 0", {"narx": 0}), ("narx manfiy", {"narx": -5}), ("narx NaN", {"narx": float("nan")}),
                  ("narx cheksiz", {"narx": float("inf")}), ("narx true", {"narx": True}), ("narx satr", {"narx": "1000"}),
                  ("narx juda katta", {"narx": 1e13}), ("eni 0", {"eni_sm": 0}), ("eni 1 001", {"eni_sm": 1001}),
                  ("o'lcham bo'sh", {"olcham": " "}), ("o'lcham 41 belgi", {"olcham": "x" * 41}),
                  ("turi noma'lum", {"turi": "arka"}), ("noma'lum kalit", {"birlik": "m2"})):
    _tn = {"model_id": K3, "turi": "asosiy", "olcham": "Yangi " + _n}
    _tn.update(_tana)
    try:
        _r = CA.post(API + "/detallar", content=json.dumps(_tn, allow_nan=True), headers={"Content-Type": "application/json"})
        _st = _r.status_code
    except Exception as e:                 # noqa: BLE001
        _st = f"{type(e).__name__}"
    check(f"A17 {_n} — 400/422", _st in (400, 422), _st)
check("A17b rad etilganlar bazaga yozilmadi, server xatosi yo'q", soni(DokonDetal, 1) == _n0
      and db_ishi(lambda d: d.query(ErrorLog).count()) == 0, (soni(DokonDetal, 1), _n0))
_r = CA.post(API + "/detallar", json={"model_id": K3, "turi": "asosiy", "olcham": "13 sm", "narx": None, "ulgurji_narx": None})
D_K13 = js(_r).get("id")
check("A17c narx bo'sh (null) — ruxsat (hali kiritilmagan), avto ham null", _r.status_code == 200 and js(_r).get("narx") is None
      and js(_r).get("narx_qoplamali_avto") is None, _r.text[:200])

# Tahrir
_j0 = jurnal("dokon_detal")
_r = CA.put(API + f"/detallar/{D_KAR}", json={"narx": 15000})
check("A18 faqat bitta maydon — narx 15 000, avto 30 000, qolganlari joyida, jurnal +1",
      _r.status_code == 200 and js(_r).get("narx") == 15000 and js(_r).get("narx_qoplamali_avto") == 30000
      and js(_r).get("ulgurji_narx") == 20000 and js(_r).get("eni_sm") == 15 and jurnal("dokon_detal") == _j0 + 1, _r.text[:300])
_r = CA.put(API + f"/detallar/{D_KAR}", json={"narx": 15000.0, "eni_sm": 15})
check("A18b o'zgarishsiz (15000 == 15000.00) — jurnalga yozilmadi", _r.status_code == 200 and jurnal("dokon_detal") == _j0 + 1,
      (_r.status_code, jurnal("dokon_detal")))
_r = CA.put(API + f"/detallar/{D_KAR}", json={"narx_qoplamali": 33000})
check("A18c qoplamali narx yozildi — avto yo'q", _r.status_code == 200 and js(_r).get("narx_qoplamali") == 33000
      and js(_r).get("narx_qoplamali_avto") is None, _r.text[:200])
_r = CA.put(API + f"/detallar/{D_KAR}", json={"narx_qoplamali": None})
check("A18d qoplamali narx bo'shatildi — yana avto", _r.status_code == 200 and js(_r).get("narx_qoplamali_avto") == 30000)
check("A18e turi tahrirlanmaydi — 400", CA.put(API + f"/detallar/{D_KAR}", json={"turi": "nalichnik"}).status_code == 400)
check("A18f narx 0 bilan tahrir — 400, eski qiymat joyida",
      CA.put(API + f"/detallar/{D_KAR}", json={"narx": 0}).status_code == 400
      and detal(D_KAR).get("narx") == 15000)

# Koeffitsient
_r = CA.put(API + "/koeff", json={"koeff": 2.5})
_kd = [detal(D_KAR)] if detal(D_KAR) else []
check("A19 koeffitsient 2,5 — avto 15 000 × 2,5 = 37 500 → 38 000; alohida yozilgan qoplamali (kapitel 45 000) o'zgarmadi",
      _r.status_code == 200 and katalog()["koeff"] == 2.5 and _kd and _kd[0]["narx_qoplamali_avto"] == 38000
      and detal(D_KAP).get("narx_qoplamali") == 45000, (_r.text[:200], _kd))
for _n, _tana in (("0,5", {"koeff": 0.5}), ("11", {"koeff": 11}), ("satr", {"koeff": "2"}), ("true", {"koeff": True}),
                  ("ortiqcha kalit", {"koeff": 2, "x": 1}), ("bo'sh", {})):
    check(f"A19b koeffitsient {_n} — 400", CA.put(API + "/koeff", json=_tana).status_code == 400)
check("A19c rad etilgandan keyin 2,5 joyida", katalog()["koeff"] == 2.5)

# Model qolipi va kapitel / baza
_r = CA.put(API + f"/modellar/{R18}", json={"qolip": "juft_metr"})
check("A20 komplekt detallari (karniz, kapitel) bor modelni juft metrga o'tkazib bo'lmaydi — 400", _r.status_code == 400, _r.text[:200])
_r = CA.put(API + f"/modellar/{D1}", json={"qolip": "m2"})
check("A20b dekor (asosiy) → m² — birlik ham m2", _r.status_code == 200
      and detal(D_DEK).get("birlik") == "m2", _r.text[:200])
_r = CA.put(API + f"/modellar/{R18}", json={"kapitel_baza_bor": False})
check("A20c kapitel narxi bor modelda «kapitel va baza yo'q» — 400", _r.status_code == 400)
_r = CA.put(API + f"/modellar/{K3}", json={"bolim_id": ARKA, "nom": "Arka karnizi", "tartib": 3})
check("A21 model boshqa bo'limga o'tkazildi", _r.status_code == 200 and js(_r).get("bolim_id") == ARKA, _r.text[:200])
check("A21b tizim bo'limiga o'tkazib bo'lmaydi — 400", CA.put(API + f"/modellar/{K3}", json={"bolim_id": TAYYOR}).status_code == 400)
check("A21c boshqa modelning kodiga o'zgartirib bo'lmaydi — 400", CA.put(API + f"/modellar/{K3}", json={"kod": "du-1"}).status_code == 400)
check("A22 modellari bor bo'lim o'chirilmaydi — 400", CA.delete(API + f"/bolimlar/{ARKA}").status_code == 400)

# Ikki korxona
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", True))     # sinov uchun bevosita (API — faqat egasiga)
_rb = CB.post(API + "/bolimlar", json={"nom": "B bo'limi", "qolip": "dona"})
BB = js(_rb).get("id")
_kb = katalog(CB)
check("A23 B korxona faqat o'z katalogini ko'radi", _rb.status_code == 200 and [b["nom"] for b in _kb.get("bolimlar", [])] == ["B bo'limi"]
      and not _kb.get("modellar") and not _kb.get("detallar"), str(_kb)[:300])
_b_sorov = (CB.put(API + f"/bolimlar/{ROM}", json={"nom": "Buzildi"}).status_code,
            CB.delete(API + f"/bolimlar/{ARKA}").status_code,
            CB.put(API + f"/modellar/{R18}", json={"nom": "Buzildi"}).status_code,
            CB.delete(API + f"/modellar/{K3}").status_code,
            CB.put(API + f"/detallar/{D_KAR}", json={"narx": 1}).status_code,
            CB.delete(API + f"/detallar/{D_KAR}").status_code)
check("A24 B — A ning bo'lim / model / narx qatoriga tegolmaydi (404)", _b_sorov == (404,) * 6, _b_sorov)
check("A24b B — A ning bo'limiga model, A ning modeliga qator qo'sholmaydi (400)",
      CB.post(API + "/modellar", json={"bolim_id": ROM, "kod": "B-1"}).status_code == 400
      and CB.post(API + "/detallar", json={"model_id": R18, "turi": "karniz", "olcham": "Katta"}).status_code == 400)
check("A24c B kodi A dagi bilan bir xil bo'lishi mumkin (korxona ichida yagona)",
      CB.post(API + "/modellar", json={"bolim_id": BB, "kod": "R-18"}).status_code == 200)
check("A24d A ning qiymatlari o'zgarmagan", katalog()["modellar"] and model(R18).get("nom") == "Klassik"
      and detal(D_KAR).get("narx") == 15000)
check("A24e B ning koeffitsienti alohida (standart 2)", katalog(CB).get("koeff") == 2.0 and katalog().get("koeff") == 2.5)


def _qoriqchi(d):
    if DokonModel is None:
        return "jadval yo'q"
    d.add(DokonModel(company_id=2, bolim_id=ROM, kod="QOR-1", qolip="dona", kapitel_baza_bor=False, tartib=1, yoqilgan=True))
    try:
        d.flush()
        return "o'tdi"
    except Exception as e:                 # noqa: BLE001
        d.rollback()
        return type(e).__name__


check("A25 qo'riqchi: B korxona modeli A bo'limiga — TenantMismatchError", db_ishi(_qoriqchi) == "TenantMismatchError")

# Jurnal
check("A26 jurnal: yaratish / tahrir yozuvlari A korxonasiga",
      jurnal("dokon_model") >= 5 and jurnal("dokon_detal") >= 6 and jurnal("company_setting") >= 1 and jurnal("dokon_model", 2) >= 1)

# Model o'chirish
_nd = xavfsiz(lambda d: d.query(DokonDetal).filter(DokonDetal.model_id == DU1).count())
_r = CA.delete(API + f"/modellar/{DU1}")
check("A27 model o'chirildi — uning narx qatorlari ham", _r.status_code == 200 and _nd == 2
      and xavfsiz(lambda d: d.query(DokonDetal).filter(DokonDetal.model_id == DU1).count()) == 0, (_r.status_code, _nd))
_r = CA.delete(API + f"/detallar/{D_K13}")
check("A27b narx qatori o'chirildi; qayta o'chirish — 404", _r.status_code == 200 and CA.delete(API + f"/detallar/{D_K13}").status_code == 404)

# Zaxira → tiklash
_oldin = (soni(DokonBolim, 1), soni(DokonModel, 1), soni(DokonDetal, 1))
_s = SessionLocal()
_zax = json.loads(json.dumps(crud.export_full_backup(_s, company_id=1), default=str))
_s.close()
_tz = _zax.get("tables") or {}
_s = SessionLocal()
try:
    _nat = crud.import_full_backup(_s, _zax, company_id=1, replace=True)
except Exception as e:                  # noqa: BLE001
    _nat = {"success": False, "message": f"{type(e).__name__}: {e}"}
_s.close()
_keyin = (soni(DokonBolim, 1), soni(DokonModel, 1), soni(DokonDetal, 1))
check("A28 zaxirada uch jadval; tiklashdan keyin sonlar AYNAN, narx va koeffitsient joyida",
      all(len(_tz.get(t) or []) == n for t, n in zip(("dokon_bolimlar", "dokon_modellar", "dokon_detallar"), _oldin))
      and _nat.get("success") is True and _keyin == _oldin
      and detal(D_KAR).get("narx") == 15000 and katalog()["koeff"] == 2.5,
      (_oldin, _keyin, str(_nat)[:300]))
check("A28b tiklash B korxona katalogiga tegmadi", soni(DokonBolim, 2) == 1 and soni(DokonModel, 2) == 1)

# O'chirish (Platforma)
_r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "0"})
check("A29 o'chirildi — API 404, menyuda yo'q, ma'lumot QOLDI",
      _r.status_code == 200 and CA.get(API).status_code == 404 and 'href="/sayt-katalogi"' not in CA.get("/dashboard").text
      and (soni(DokonBolim, 1), soni(DokonModel, 1), soni(DokonDetal, 1)) == _oldin, (_r.status_code, _r.text[:200]))
_r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
check("A29b qayta yoqildi — yangi bo'lim yaratilmadi, eski katalog joyida",
      _r.status_code == 200 and js(_r).get("yaratilgan_bolimlar") == 0 and soni(DokonBolim, 1) == _oldin[0]
      and detal(D_KAR).get("narx") == 15000)
# review231 tuzatishlari
_r = CA.post(API + "/detallar", json={"model_id": K3, "turi": "asosiy", "olcham": "Ulgurji sinov", "narx": 50000,
                                      "ulgurji_narx": 777777})
_du = js(_r).get("id")
CA.put(API + f"/detallar/{_du}", json={"ulgurji_narx": 888888, "ulgurji_qoplamali": 999999})
CA.delete(API + f"/detallar/{_du}")
_jm = db_ishi(lambda d: [(a.entity_label or "") + " " + (a.old_value or "") + " " + (a.new_value or "")
                         for a in d.query(ActivityLog).filter(ActivityLog.entity_type == "dokon_detal")])
check("A31 jurnal matnida ULGURJI narx raqami yo'q (yaratish / tahrir / o'chirish), oddiy narx bor",
      _r.status_code == 200 and _jm and not [t for t in _jm if re.search(r"7[\s\u00a0]?77|8[\s\u00a0]?88|9[\s\u00a0]?99", t)]
      and any("50" in t for t in _jm) and any("ulgurji narx o'zgardi" in t for t in _jm), [t for t in _jm if "Ulgurji" in t][:3])
for _n, _url, _tana in (("narx 1e26", "/detallar", {"model_id": K3, "turi": "asosiy", "olcham": "Katta1", "narx": 1e26}),
                        ("narx 10**40 (butun)", "/detallar", {"model_id": K3, "turi": "asosiy", "olcham": "Katta2", "narx": 10 ** 40}),
                        ("eni 10**400", "/detallar", {"model_id": K3, "turi": "asosiy", "olcham": "Katta3", "eni_sm": 10 ** 400})):
    _r = CA.post(API + _url, content=json.dumps(_tana), headers={"Content-Type": "application/json"})
    check(f"A32 {_n} — 400 (500 emas)", _r.status_code == 400, (_r.status_code, _r.text[:120]))
_r = CA.put(API + "/koeff", content='{"koeff": 1e30}', headers={"Content-Type": "application/json"})
check("A32b koeffitsient 1e30 — 400", _r.status_code == 400, _r.status_code)
_r = CA.post(API + "/bolimlar", json={"nom": "Nul\x00bo'lim", "qolip": "dona"})
check("A33 nomdagi NUL olib tashlanadi (PG da 500 emas)", _r.status_code == 200 and js(_r).get("nom") == "Nulbo'lim", (_r.status_code, _r.text[:120]))
_r = CA.post(API + "/bolimlar", json={"nom": "\u200b\u200e\u2060 \ufeff", "qolip": "dona"})
check("A33b faqat ko'rinmas belgilardan iborat nom — 400", _r.status_code == 400, _r.status_code)
_r = CA.post(API + "/modellar", json={"bolim_id": KARNIZ, "kod": "ß" * 16})
check("A34 katta harfda 30 dan uzun bo'ladigan kod («ß» × 16) — 400", _r.status_code == 400, (_r.status_code, _r.text[:120]))
_r1 = CA.post(API + "/bolimlar", json={"nom": "Ärka", "qolip": "dona"})
_r2 = CA.post(API + "/bolimlar", json={"nom": "ärka", "qolip": "dona"})
_r3 = CA.post(API + "/modellar", json={"bolim_id": js(_r1).get("id"), "kod": "Ö-1"})
_r4 = CA.post(API + "/modellar", json={"bolim_id": js(_r1).get("id"), "kod": "ö-1"})
check("A35 lotin bo'lmagan harflar — katta / kichik harfsiz takror (SQLite da ham): bo'lim va kod — 400",
      (_r1.status_code, _r2.status_code, _r3.status_code, _r4.status_code) == (200, 400, 200, 400),
      (_r1.status_code, _r2.status_code, _r3.status_code, _r4.status_code))
_r = CA.post(API + "/detallar", json={"model_id": K3, "turi": "asosiy", "olcham": "Arzon", "narx": 100})
check("A36 avto qoplamali 0 ga tushmaydi (100 × 2,5 = 250)", _r.status_code == 200 and js(_r).get("narx_qoplamali_avto") == 250,
      _r.text[:200])
check("A37 termopanel (m²) va dekor (dona) da kapitel / baza yo'q — 400",
      CA.post(API + "/detallar", json={"model_id": TP2, "turi": "kapitel", "olcham": "4 sm"}).status_code == 400
      and CA.post(API + "/modellar", json={"bolim_id": TERMO, "kod": "TP-9", "kapitel_baza_bor": True}).status_code == 400
      and CA.put(API + f"/modellar/{TP2}", json={"kapitel_baza_bor": True}).status_code == 400)
_r = CP.post("/api/platform/companies/2/dokon", data={"yoqilgan": "0"})
check("A38 mijoz korxonada (bevosita yoqilgan) o'chirish — ruxsat, ma'lumot qoladi",
      _r.status_code == 200 and not xavfsiz(lambda d: d.get(Company, 2).dokon_yoqilgan, True) and soni(DokonBolim, 2) == 1,
      (_r.status_code, _r.text[:200]))
check("A30 server xatosi (ErrorLog) yo'q", db_ishi(lambda d: d.query(ErrorLog).count()) == 0,
      db_ishi(lambda d: [e.message[:120] for e in d.query(ErrorLog).limit(3)]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PG parallel")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    from concurrent.futures import ThreadPoolExecutor

    def parallel(fn, n=2):
        with ThreadPoolExecutor(max_workers=n) as ex:
            return sorted(f.result() for f in [ex.submit(fn) for _ in range(n)])

    _c1, _c2 = mijoz("t231_admin"), mijoz("t231_admin")
    _ck = iter([_c1, _c2, _c1, _c2, _c1, _c2])
    _st = parallel(lambda: next(_ck).post(API + "/modellar", json={"bolim_id": ROM, "kod": "PAR-1"}).status_code)
    check("P1 bir xil kodli ikki model — bittasi 200, ikkinchisi 400 / 409, 500 yo'q",
          _st[0] == 200 and _st[1] in (400, 409) and xavfsiz(lambda d: d.query(DokonModel).filter(DokonModel.kod == "PAR-1").count()) == 1,
          _st)
    _pm = xavfsiz(lambda d: d.query(DokonModel.id).filter(DokonModel.kod == "PAR-1").scalar())
    _st = parallel(lambda: next(_ck).post(API + "/detallar", json={"model_id": _pm, "turi": "nalichnik", "olcham": "Katta",
                                                                  "narx": 9000}).status_code)
    check("P2 bir xil ikki narx qatori — bittasi 200, ikkinchisi 400, 500 yo'q",
          _st == [200, 400] and xavfsiz(lambda d: d.query(DokonDetal).filter(DokonDetal.model_id == _pm).count()) == 1, _st)
    _ck = iter([_c1, _c2])
    _asl_band = getattr(crud, "_dokon_bolim_nomi_bandmi", None)

    def _sekin_band(*a, **k):
        r = _asl_band(*a, **k)
        time.sleep(0.4)                    # tekshiruvdan KEYIN kechikish — qulfsiz kodda ikkalasi ham «bo'sh» ko'radi (kech143 saboq)
        return r
    if _asl_band:
        crud._dokon_bolim_nomi_bandmi = _sekin_band
    _st = parallel(lambda: next(_ck).post(API + "/bolimlar", json={"nom": "Parallel bo'lim", "qolip": "dona"}).status_code)
    if _asl_band:
        crud._dokon_bolim_nomi_bandmi = _asl_band
    check("P3 bir xil nomli ikki bo'lim — bittasi 200, ikkinchisi 400, 500 yo'q",
          _st == [200, 400] and xavfsiz(lambda d: d.query(DokonBolim).filter(DokonBolim.nom == "Parallel bo'lim").count()) == 1, _st)
    _pa = js(_c1.post(API + "/detallar", json={"model_id": _pm, "turi": "nalichnik", "olcham": "Kichik"})).get("id")
    _pb = js(_c1.post(API + "/detallar", json={"model_id": _pm, "turi": "nalichnik", "olcham": "O'rta"})).get("id")
    _ck = iter([(_c1, _pa), (_c2, _pb)])

    def _qayta_nom():
        c, i = next(_ck)
        return c.put(API + f"/detallar/{i}", json={"olcham": "Bir xil"}).status_code
    _st = parallel(_qayta_nom)
    check("P5 ikki qatorni bir vaqtda bir xil o'lchamga — bittasi 200, ikkinchisi 400 (model qulfi)",
          _st == [200, 400] and xavfsiz(lambda d: d.query(DokonDetal).filter(DokonDetal.model_id == _pm,
                                                                          DokonDetal.olcham == "Bir xil").count()) == 1, _st)
    db_ishi(lambda d: d.add(Company(id=3, name="T231 C ega")))
    with contextlib.redirect_stdout(io.StringIO()):
        _s3 = SessionLocal()
        auth.create_user(_s3, "t231_c", PAROL, UserRole.ADMIN, "T231 C", company_id=3)
        _s3.query(User).filter(User.username == "t231_c").first().is_platform_admin = True
        _s3.commit()
        _s3.close()
    _p1, _p2 = mijoz("t231_plat"), mijoz("t231_plat")
    _ck = iter([_p1, _p2])
    _st = parallel(lambda: next(_ck).post("/api/platform/companies/3/dokon", data={"yoqilgan": "1"}).status_code)
    check("P6 ikki oynadan bir vaqtda yoqish — 500 yo'q, bo'limlar 9 ta (takrorsiz)", 500 not in _st and soni(DokonBolim, 3) == 9,
          (_st, soni(DokonBolim, 3)))
    check("P4 server xatosi yo'q", db_ishi(lambda d: d.query(ErrorLog).count()) == 0)
else:
    print("  (faqat PG rejimida)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
br = pw_ctx = server = None
if PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
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
    JS_XATO, SOROV, KONSOL = [], [], []

    def kontekst(login, kenglik=1440):
        ctx = br.new_context(viewport={"width": kenglik, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
        ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
        pg.on("console", lambda m: KONSOL.append(m.text[:200]) if m.type == "error" else None)
        pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""))) if "/api/" in q.url else None)
        pg.goto(B + "/login")
        pg.fill("input[name=username]", login)
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
        return ctx, pg

    def kut(pg, ifoda, ms=8000):
        try:
            pg.wait_for_function(ifoda, timeout=ms)
            return True
        except Exception:                  # noqa: BLE001
            return False

    if br:
        try:
            ctx, pg = kontekst("t231_admin")
            pg.goto(B + "/sayt-katalogi")
            _y = kut(pg, "document.querySelectorAll('#skBolimlar .sk-bolim').length >= 10")
            check("U1 sahifa — bo'limlar ro'yxati (10 ta), koeffitsient 2,5 yuklandi",
                  _y and pg.evaluate("document.getElementById('skKoeff').value") == "2.5", pg.evaluate("document.body.innerText.slice(0,300)"))
            CA.post(API + "/modellar", json={"bolim_id": KARNIZ, "kod": "X<b>1</b>", "nom": '<img src=x onerror="window.__xss=1">'})
            pg.reload()
            kut(pg, "document.querySelectorAll('#skBolimlar .sk-bolim').length >= 10")
            pg.evaluate("""() => { const b = [...document.querySelectorAll('#skBolimlar .sk-bolim')]
                                 .find(x => x.innerText.includes('Karnizlar')); b.click(); }""")
            pg.wait_for_timeout(600)
            check("U1b server matni escape qilinadi (model nomi / kodidagi HTML — matn bo'lib ko'rinadi, bajarilmaydi)",
                  pg.evaluate("window.__xss === undefined && document.getElementById('skOng').innerText.includes('<img src=x')"
                              " && document.getElementById('skOng').innerText.includes('X<B>1</B>')"),
                  pg.evaluate("document.getElementById('skOng').innerText.slice(0,300)"))
            pg.evaluate("skYangiModelOch()")
            pg.fill("#skYmKod", "k-7")
            pg.fill("#skYmNom", "Brauzer karnizi")
            _bas = len(SOROV)
            pg.click("#skYmSaqla")
            _y = kut(pg, "document.querySelector('.sk-model.ochiq') && document.querySelector('.sk-model.ochiq').innerText.includes('K-7')")
            check("U2 model qo'shildi (kod katta harfda, ochiq holda chizildi) — 1 ta POST",
                  _y and [x for x in SOROV[_bas:] if x == ("POST", API + "/modellar")] == [("POST", API + "/modellar")],
                  SOROV[_bas:])
            _mid = xavfsiz(lambda d: d.query(DokonModel.id).filter(DokonModel.kod == "K-7").scalar())
            tr = f"tr[data-yangi='{_mid}']"
            pg.fill(tr + " [data-yf=olcham]", "15 sm")
            pg.fill(tr + " [data-yf=narx]", "120000")
            pg.fill(tr + " [data-yf=ulgurji_narx]", "200000")
            pg.click(tr + " [data-dyarat]")
            _y = kut(pg, "document.querySelectorAll(\"tr[data-detal]\").length > 0 && [...document.querySelectorAll('tr[data-detal]')].some(r => r.querySelector('[data-df=olcham]').value === '15 sm')")
            _did = xavfsiz(lambda d: d.query(DokonDetal.id).filter(DokonDetal.model_id == _mid).scalar())
            check("U3 narx qatori qo'shildi — bazada 120 000 / 200 000, birlik metr, avto qoplamali 300 000 ko'rsatildi",
                  _y and _did and xavfsiz(lambda d: (float(d.get(DokonDetal, _did).narx), float(d.get(DokonDetal, _did).ulgurji_narx),
                                                    d.get(DokonDetal, _did).birlik)) == (120000.0, 200000.0, "metr")
                  and "300" in (pg.get_attribute(f"tr[data-detal='{_did}'] [data-df=narx_qoplamali]", "placeholder") or ""),
                  pg.evaluate("document.querySelector('.sk-model.ochiq') && document.querySelector('.sk-model.ochiq').innerText.slice(0,400)"))
            _bas = len(SOROV)
            pg.fill(f"tr[data-detal='{_did}'] [data-df=narx]", "125 500")
            pg.press(f"tr[data-detal='{_did}'] [data-df=narx]", "Tab")
            _y = kut(pg, f"(document.querySelector(\"tr[data-detal='{_did}'] [data-df=narx_qoplamali]\").placeholder || '').indexOf('314') >= 0")
            check("U4 katakni o'zgartirish — PUT, bazada 125 500, avto 313 750 → 314 000 ko'rsatildi",
                  _y and xavfsiz(lambda d: float(d.get(DokonDetal, _did).narx)) == 125500.0
                  and [x for x in SOROV[_bas:] if x[0] == "PUT"] == [("PUT", API + f"/detallar/{_did}")], SOROV[_bas:])
            _bas = len(SOROV)
            pg.fill(f"tr[data-detal='{_did}'] [data-df=narx]", "0")
            pg.press(f"tr[data-detal='{_did}'] [data-df=narx]", "Tab")
            _y = kut(pg, f"document.querySelector(\"tr[data-detal='{_did}'] [data-df=narx]\").classList.contains('xato')")
            check("U5 narx 0 — server rad etdi, katak qizil, bazada eski qiymat", _y
                  and xavfsiz(lambda d: float(d.get(DokonDetal, _did).narx)) == 125500.0)
            # U10 / U11 (review231 №4): sekin saqlash — keyingi katakka yozilgan matn yo'qolmaydi; bir katak ketma-ket ikki marta
            pg.evaluate("""() => { const f = window.fetch; window.__asl_fetch = f;
                window.fetch = (u, o) => (o && o.method === 'PUT' && /detallar\\/\\d+$/.test(String(u)))
                  ? new Promise(r => setTimeout(r, 1500)).then(() => f(u, o)) : f(u, o); }""")
            _n = f"tr[data-detal='{_did}'] [data-df=narx]"
            _u = f"tr[data-detal='{_did}'] [data-df=ulgurji_narx]"
            pg.fill(_n, "130000")
            pg.press(_n, "Tab")
            pg.click(_u)
            pg.keyboard.press("Control+A")
            pg.keyboard.type("21")
            pg.wait_for_timeout(2500)
            check("U10 saqlash davomida keyingi katakka yozilgan matn va kursor joyida",
                  pg.evaluate(f"document.querySelector(\"{_u}\").value") == "21"
                  and pg.evaluate(f"document.activeElement === document.querySelector(\"{_u}\")")
                  and xavfsiz(lambda d: float(d.get(DokonDetal, _did).narx)) == 130000.0,
                  pg.evaluate(f"[document.querySelector(\"{_u}\").value, document.activeElement && document.activeElement.dataset.df]"))
            pg.keyboard.press("Escape")
            pg.fill(_n, "1000")
            pg.press(_n, "Tab")
            pg.wait_for_timeout(200)
            pg.fill(_n, "2000")
            pg.press(_n, "Tab")
            pg.wait_for_timeout(4500)
            check("U11 bir katak ketma-ket ikki marta (birinchisi saqlanayotganda) — bazada ham, ekranda ham OXIRGI qiymat 2000",
                  xavfsiz(lambda d: float(d.get(DokonDetal, _did).narx)) == 2000.0
                  and pg.evaluate(f"document.querySelector(\"{_n}\").value") == "2000",
                  (xavfsiz(lambda d: float(d.get(DokonDetal, _did).narx)), pg.evaluate(f"document.querySelector(\"{_n}\").value")))
            pg.evaluate("() => { window.fetch = window.__asl_fetch; }")
            pg.set_viewport_size({"width": 390, "height": 844})
            pg.wait_for_timeout(300)
            _toshdi = pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            check("U6 telefon (390 px) — sahifa gorizontal toshmaydi (jadval o'z qutisida aylanadi)", not _toshdi,
                  pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]"))
            ctx.close()
            ctx, pg = kontekst("t231_plat")
            pg.goto(B + "/platforma")
            _y = kut(pg, "document.querySelector('#plDokon [data-dokon]') !== null")
            check("U7 Platforma — o'z korxonasi uchun «Sayt katalogi» tugmasi (yoqilgan — «O'chirish»)",
                  _y and pg.evaluate("document.querySelector('#plDokon [data-dokon]').dataset.yoq") == "0"
                  and "yoqilgan" in pg.evaluate("document.getElementById('plDokon').innerText"),
                  pg.evaluate("document.getElementById('plDokon') && document.getElementById('plDokon').innerText"))
            ctx.close()
            check("U8 JS xatosi yo'q", not JS_XATO, JS_XATO[:3])
            check("U9 konsolda xato yo'q (rad etilgan 400 dan tashqari)",
                  not [k for k in KONSOL if "400" not in k], KONSOL[:3])
        except Exception as e:             # noqa: BLE001
            check("U* brauzer sinovi qulamadi", False, f"{type(e).__name__}: {e}")
    if br:
        br.close()
    if pw_ctx:
        pw_ctx.stop()
    if server:
        server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
