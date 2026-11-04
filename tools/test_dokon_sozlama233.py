#!/usr/bin/env python3
"""
test_dokon_sozlama233.py — kech168 (zip 233 «Do'kon sozlamalari: telefonlar, ish vaqti, komplekt retsepti»; egasi QARORLARI
«Onlayn do'kon rejasi» 30.10).

NIMA UCHUN KERAK
  Saytdagi buyurtma tasdig'i sahifasi «shu raqamlardan biriga qo'ng'iroq qiling» deydi: raqamlar admin panelda boshqariladi, oxirgisi
  o'chirilmaydi; ish vaqtida (dushanba–shanba 8:00–18:00) — hammasi, tashqarida va yakshanba — faqat bitta raqam. Komplekt (rom / eshik)
  narxi detallar narxidan RETSEPT bo'yicha yig'iladi (rom: karniz 2 m, podokonnik 2 m, nalichnik 4 m, kapitel 2, baza 2; eshik: karniz
  2 m, nalichnik 5 m, kapitel 2, baza 2); kapitel / baza o'chirilsa — aynan ularning narxi ayiriladi; ulgurjida — faqat rom, 1 dona = 2 m.
  Xato hisob — mijozga noto'g'ri narx; raqamsiz tasdiq sahifasi — yo'qolgan buyurtma.
BO'LIMLAR
  S — statik: jadval, yagona kalit, zaxira tartibi, marshrutlar, standart qiymatlar = egasining jadvali.
  A — API: belgi o'chiq — 404, Menejer — 403; raqam shakli (har xil yozilishi → bitta), takror, 10 ta chegara, birinchi raqam «doim»,
      oxirgi raqam / oxirgi «doim» — o'chirilmaydi, tartib, izoh; korxona raqamlari; ish vaqti tekshiruvlari va matni; retsept
      tekshiruvlari; buzilgan sozlama — standart; jurnal (o'zgarishsiz — yozilmaydi); ikki korxona; zaxira → tiklash.
  K — komplekt narxi: mustaqil hisob (oracle) bilan AYNAN — rom / eshik / ulgurji rom, qoplamasiz / qoplamali (alohida va avto),
      kapitel / bazasiz, yetishmaydigan / yashirin detal, kapitelsiz model, retsept va koeffitsient o'zgarsa, bitta model marshruti.
  V — ish vaqti: aniq UTC vaqtlarda (Toshkent = UTC+5) chegaralar, yakshanba, hozir ko'rinadigan raqamlar.
  P — PG parallel: bir raqam ikki marta, oxirgi ikki «doim» raqamni bir vaqtda o'chirish / belgini olish — qoida buzilmaydi, 500 yo'q.
  U — HAQIQIY brauzer: sozlamalar kartochkasi, raqam qo'shish / doim / tartib / o'chirish, ish vaqti, retsept, komplekt narxlari bloki
      (katak saqlangach yangilanadi, boshqa katakdagi matn yo'qolmaydi), 375 px, JS xatosi yo'q.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` (U — faqat SQLite / TF1).
Asl kodga (zip 232c) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_dokon_sozlama233.py
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
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "dokon233_test"
_T = tempfile.mkdtemp(prefix="t233_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't233.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, ActivityLog, ErrorLog, CompanySetting, DokonDetal   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

DokonTelefon = getattr(models, "DokonTelefon", None)    # asl kodda (zip 232c) yo'q — sinov qulamasin

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
    try:
        return db_ishi(fn)
    except Exception:                      # noqa: BLE001
        return std


def tel_soni(cid=1):
    if DokonTelefon is None:
        return -1
    return db_ishi(lambda d: d.query(DokonTelefon).filter(DokonTelefon.company_id == cid).count())


def tel_bazada(cid=1):
    """[(raqam, doim, izoh)] tartib bo'yicha."""
    if DokonTelefon is None:
        return []
    return db_ishi(lambda d: [(t.raqam, bool(t.doim), t.izoh) for t in d.query(DokonTelefon).filter(DokonTelefon.company_id == cid)
                              .order_by(DokonTelefon.tartib, DokonTelefon.id).all()])


def sozlama(kalit, cid=1):
    return db_ishi(lambda d: d.query(CompanySetting.value).filter(CompanySetting.company_id == cid,
                                                                   CompanySetting.key == kalit).scalar())


def sozlama_yoz(kalit, qiymat, cid=1):
    def _f(d):
        r = d.query(CompanySetting).filter(CompanySetting.company_id == cid, CompanySetting.key == kalit).first()
        if r:
            r.value = qiymat
        else:
            d.add(CompanySetting(company_id=cid, key=kalit, value=qiymat))
    db_ishi(_f)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: korxona 1 — platforma egasi, korxona 2 — boshqa korxona (belgi bazada qo'lda yoqiladi — ajratish sinovi uchun)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T233 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t233_admin", PAROL, UserRole.ADMIN, "T233 Admin", company_id=1)
    auth.create_user(s, "t233_plat", PAROL, UserRole.ADMIN, "T233 Platforma", company_id=1)
    auth.create_user(s, "t233_men", PAROL, UserRole.MANAGER, "T233 Menejer", company_id=1)
    auth.create_user(s, "t233_b", PAROL, UserRole.ADMIN, "T233 B Admin", company_id=2)
s.query(User).filter(User.username == "t233_plat").first().is_platform_admin = True
s.commit()
s.close()
main._send_telegram = lambda msg, *a, **k: True


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t233_admin")
CP = mijoz("t233_plat")
CM = mijoz("t233_men")
CB = mijoz("t233_b")
API = "/api/sayt-katalogi"
T = API + "/telefonlar"


def jurnal(entity, cid=1):
    return db_ishi(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == entity, ActivityLog.company_id == cid).count())


def katalog(c=CA):
    d = js(c.get(API))
    return d if isinstance(d, dict) else {}


def soz(c=CA):
    d = katalog(c).get("sozlamalar") or {}
    return {"telefonlar": [], "korxona_telefonlari": [], "korinadigan_telefonlar": [], "ish_vaqti": {}, "retsept": {},
            "ish_vaqti_kiritilgan": None, "hozir_ish_vaqti": None, "ish_izoh": None, "ish_vaqti_matni": None, "komplekt_olcham": None, **d}


def ix(lst, i):
    """Asl kodda ro'yxat bo'sh — sinov qulamasin (0 — mavjud bo'lmagan id, 422)."""
    return lst[i] if -len(lst) <= i < len(lst) else 0


# egasining jadvali (30.10) — sinovda MUSTAQIL yozilgan (kod konstantasi S4 da solishtiriladi)
STD = {"rom": {"karniz": 2, "podokonnik": 2, "nalichnik": 4, "kapitel": 2, "baza": 2},
       "eshik": {"karniz": 2, "nalichnik": 5, "kapitel": 2, "baza": 2}}
STD_ISH = {"kunlar": [1, 2, 3, 4, 5, 6], "boshi": "08:00", "oxiri": "18:00"}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("S1 jadval `dokon_telefonlar`: company_id, raqam (13), izoh (40), doim, tartib; yagona (company_id, raqam)",
      lambda: DokonTelefon.__tablename__ == "dokon_telefonlar"
      and {c.name for c in DokonTelefon.__table__.columns} >= {"company_id", "raqam", "izoh", "doim", "tartib"}
      and DokonTelefon.__table__.c.raqam.type.length == 13 and DokonTelefon.__table__.c.izoh.type.length == 40
      and any({c.name for c in u.columns} == {"company_id", "raqam"} for u in DokonTelefon.__table__.constraints
              if u.__class__.__name__ == "UniqueConstraint"))
check("S2 zaxira / tiklash tartibida DokonTelefon bor", lambda: "DokonTelefon" in [c.__name__ for c in crud._reset_table_order()])
_yol = {(m, r.path) for r in main.app.routes for m in (getattr(r, "methods", None) or ())}
_kerak = {("POST", T), ("PUT", T), ("PUT", T + "/{telefon_id}"), ("DELETE", T + "/{telefon_id}"), ("PUT", API + "/ish-vaqti"),
          ("PUT", API + "/komplekt"), ("GET", API + "/modellar/{model_id}/komplekt")}
check("S3 7 ta yangi marshrut", _kerak <= _yol, sorted(_kerak - _yol))
check("S4 standart qiymatlar — egasining qarorlari (30.10): retsept, ish vaqti dushanba–shanba 08:00–18:00, o'lcham «O'rta»",
      lambda: crud.DOKON_RETSEPT_STANDART == {"rom": {"karniz": 2, "podokonnik": 2, "nalichnik": 4, "kapitel": 2, "baza": 2},
                                              "eshik": {"karniz": 2, "nalichnik": 5, "kapitel": 2, "baza": 2}}
      and crud.DOKON_ISH_STANDART == {"kunlar": [1, 2, 3, 4, 5, 6], "boshi": "08:00", "oxiri": "18:00"}
      and crud.DOKON_KOMPLEKT_OLCHAM_STANDART == "O'rta")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_st = [CA.post(T, json={"raqam": "+998979995757"}).status_code, CA.put(T, json={"tartib": []}).status_code,
       CA.put(T + "/1", json={"izoh": "x"}).status_code, CA.delete(T + "/1").status_code,
       CA.put(API + "/ish-vaqti", json={}).status_code, CA.put(API + "/komplekt", json={}).status_code,
       CA.get(API + "/modellar/1/komplekt").status_code]
check("A1 belgi o'chiq — 7 ta yangi marshrut ham 404 (noto'g'ri tana bilan ham)", _st == [404] * 7, _st)
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
_s0 = soz()
check("A2 yoqilgach katalogda `sozlamalar`: raqam yo'q, ish vaqti va retsept — standart, matn «Dushanba–shanba, 8:00–18:00»",
      lambda: _s0["telefonlar"] == [] and _s0["ish_vaqti"] == {"kunlar": [1, 2, 3, 4, 5, 6], "boshi": "08:00", "oxiri": "18:00"}
      and _s0["ish_vaqti_matni"] == "Dushanba–shanba, 8:00–18:00" and _s0["retsept"] == crud.DOKON_RETSEPT_STANDART
      and _s0["komplekt_olcham"] == "O'rta" and _s0["ish_vaqti_kiritilgan"] is False, str(_s0)[:400])
_st = [CM.post(T, json={"raqam": "+998979995757"}).status_code, CM.put(T, json={"tartib": []}).status_code,
       CM.put(T + "/1", json={"izoh": "x"}).status_code, CM.delete(T + "/1").status_code,
       CM.put(API + "/ish-vaqti", json={"kunlar": [1], "boshi": "08:00", "oxiri": "09:00"}).status_code,
       CM.put(API + "/komplekt", json={"olcham": "Katta"}).status_code, CM.get(API + "/modellar/1/komplekt").status_code]
check("A3 Menejer — hammasi 403, hech narsa yozilmadi", _st == [403] * 7 and tel_soni() == 0, (_st, tel_soni()))

# Telefon shakli
_norm = getattr(crud, "dokon_telefon_norm", None)


def _n(x):
    try:
        return _norm(x)
    except ValueError:
        return "RAD"


_shakl = {"+998 97 999 57 57": "+998979995757", "998979995757": "+998979995757", "97 999 57 57": "+998979995757",
          "(97) 999-57-57": "+998979995757", "+998-97-999.57.57": "+998979995757", " 979995757 ": "+998979995757",
          "​+998 97 999 57 57": "+998979995757", "+7 912 345 67 89": "RAD", "97 999 57 5": "RAD", "+998 97 999 57 577": "RAD",
          "97x9995757": "RAD", "+99897+9995757": "RAD", "+979995757": "RAD", "٩٧٩٩٩٥٧٥٧": "RAD", "": "RAD", "   ": "RAD",
          "1" * 41: "RAD"}
check("A4 raqam bitta shaklga (+998XXXXXXXXX): 7 xil yozilishi — bitta; noto'g'ri (9 xonali emas, harf, ikkinchi «+», boshqa "
      "davlat, arabcha raqam, bo'sh) — rad", lambda: {k: _n(k) for k in _shakl} == _shakl,
      lambda: {k: _n(k) for k in _shakl if _n(k) != _shakl[k]})
check("A4b raqam matn bo'lmasa / buzilgan belgi — 400",
      [CA.post(T, json={"raqam": x}).status_code for x in (979995757, None, True, ["+998979995757"])]
      + [CA.post(T, content=b'{"raqam": "+998 97 999 57 57\\ud800"}', headers={"Content-Type": "application/json"}).status_code]
      == [400] * 5)
_j0 = jurnal("dokon_telefon")
_r = CA.post(T, json={"raqam": "97 999 57 57", "izoh": "  Bosh   raqam ", "doim": False})
check("A5 birinchi raqam — «doim» o'zi qo'yildi (yuborilgan false bo'lsa ham), izoh tozalandi, ko'rinishi «+998 97 999 57 57», jurnal",
      _r.status_code == 200 and js(_r).get("doim") is True and js(_r).get("korinish") == "+998 97 999 57 57"
      and tel_bazada() == [("+998979995757", True, "Bosh raqam")] and jurnal("dokon_telefon") == _j0 + 1, (_r.status_code, _r.text[:300]))
T1 = js(_r).get("id")
_r = CA.post(T, json={"raqam": "+998-97-999-57-57"})
check("A6 takror (boshqacha yozilgan) — 400, bazada 1 ta", _r.status_code == 400 and "allaqachon" in det(_r) and tel_soni() == 1,
      (_r.status_code, det(_r)))
_r = CA.post(T, json={"raqam": "+998 90 623 22 72", "izoh": "Menejer"})
T2 = js(_r).get("id")
_r3 = CA.post(T, json={"raqam": "+998 97 699 19 19"})
T3 = js(_r3).get("id")
check("A7 ikkinchi va uchinchi raqam — «doim» emas (birinchisi bor), tartib 1, 2, 3",
      _r.status_code == 200 and _r3.status_code == 200 and tel_bazada() == [("+998979995757", True, "Bosh raqam"),
                                                                           ("+998906232272", False, "Menejer"),
                                                                           ("+998976991919", False, None)], tel_bazada())
_st = [CA.post(T, json={"raqam": "+998901234500", "x": 1}).status_code, CA.post(T, json={"raqam": "+998901111111", "izoh": "x" * 41}).status_code,
       CA.post(T, json={"raqam": "+998901111111", "doim": "ha"}).status_code, CA.post(T, json=["+998901111111"]).status_code,
       CA.post(T, json={"raqam": "+998901111111", "izoh": "a\x00b"}).status_code]
check("A8 noma'lum kalit / izoh 41 belgi / doim satr — 400, ro'yxat tana — 422; NUL izohdan olib tashlanadi (200)",
      _st == [400, 400, 400, 422, 200] and ("+998901111111", False, "ab") in tel_bazada()
      and "+998901234500" not in [x[0] for x in tel_bazada()], (_st, tel_bazada()))
T4 = xavfsiz(lambda d: d.query(DokonTelefon.id).filter(DokonTelefon.raqam == "+998901111111").scalar())
for _i in range(6):
    CA.post(T, json={"raqam": f"+99890200000{_i}"})
_r = CA.post(T, json={"raqam": "+998902000009"})
check("A9 ko'pi bilan 10 ta raqam — 11-si 400", tel_soni() == 10 and _r.status_code == 400 and "10" in det(_r), (tel_soni(), det(_r)))
for _i in range(6):
    _id = xavfsiz(lambda d: d.query(DokonTelefon.id).filter(DokonTelefon.raqam == f"+99890200000{_i}").scalar())
    CA.delete(T + f"/{_id}")
check("A9b oddiy raqamlar o'chirildi (4 ta qoldi)", tel_soni() == 4, tel_soni())

_j0 = jurnal("dokon_telefon")
_r = CA.put(T + f"/{T1}", json={"doim": False})
check("A10 yagona «doim» raqamdan belgini olish — 400, o'zgarmadi, jurnal yo'q",
      lambda: _r.status_code == 400 and "boshqa raqam" in det(_r) and tel_bazada()[0][1] is True and jurnal("dokon_telefon") == _j0,
      (_r.status_code, det(_r)))
_r = CA.delete(T + f"/{T1}")
check("A11 yagona «doim» raqamni o'chirish — 400", _r.status_code == 400 and tel_soni() == 4, (_r.status_code, det(_r)))
_r = CA.put(T + f"/{T2}", json={"doim": True, "izoh": "Menejer Ali"})
_r2 = CA.put(T + f"/{T1}", json={"doim": False})
check("A12 boshqasiga «doim» qo'yilgach — birinchisidan olindi; izoh yangilandi; jurnal 2 ta",
      _r.status_code == 200 and _r2.status_code == 200 and js(_r).get("izoh") == "Menejer Ali"
      and [x[1] for x in tel_bazada()] == [False, True, False, False] and jurnal("dokon_telefon") == _j0 + 2,
      (_r.text[:200], _r2.text[:200], tel_bazada()))
_j0 = jurnal("dokon_telefon")
_r = CA.put(T + f"/{T2}", json={"izoh": "Menejer  Ali"})
check("A13 o'zgarishsiz saqlash (bo'shliqlar tozalangach bir xil) — 200, jurnalga yozilmadi",
      _r.status_code == 200 and jurnal("dokon_telefon") == _j0, (_r.status_code, jurnal("dokon_telefon") - _j0))
_st = [CA.put(T + f"/{T2}", json={}).status_code, CA.put(T + f"/{T2}", json={"raqam": "+998900000000"}).status_code,
       CA.put(T + f"/{T2}", json={"doim": 1}).status_code, CA.put(T + "/999999", json={"izoh": "x"}).status_code,
       CA.put(T + "/0", json={"izoh": "x"}).status_code, CA.put(T + "/2147483648", json={"izoh": "x"}).status_code]
check("A14 bo'sh tana / raqamni o'zgartirish / doim son — 400; yo'q id — 404; 0 va 2^31 — 422",
      _st == [400, 400, 400, 404, 422, 422], _st)
_r = CA.put(T + f"/{T2}", json={"izoh": None})
check("A14b izoh null — o'chiriladi", _r.status_code == 200 and js(_r).get("izoh") is None, _r.text[:200])

# Tartib
_ids = [x["id"] for x in soz()["telefonlar"]]
_yangi = [ix(_ids, 2), ix(_ids, 0), ix(_ids, 3), ix(_ids, 1)]
_r = CA.put(T, json={"tartib": _yangi})
check("A15 tartib — yangi ro'yxat bazada va javobda", _r.status_code == 200 and [x["id"] for x in js(_r).get("telefonlar", [])] == _yangi
      and [x["id"] for x in soz()["telefonlar"]] == _yangi, _r.text[:300])
_st = [CA.put(T, json={"tartib": _yangi[:3]}).status_code, CA.put(T, json={"tartib": _yangi + [_yangi[0]]}).status_code,
       CA.put(T, json={"tartib": [True] + _yangi[1:]}).status_code, CA.put(T, json={"tartib": "1,2"}).status_code,
       CA.put(T, json={"tartib": _yangi, "x": 1}).status_code, CA.put(T, json={"tartib": _yangi[:3] + [999999]}).status_code]
check("A16 tartib: yetishmaydi / takror / mantiqiy / satr / ortiqcha kalit / begona id — 400",
      _st == [400] * 6 and [x["id"] for x in soz()["telefonlar"]] == _yangi, _st)
_j0 = jurnal("dokon_telefon")
check("A16b o'sha tartib qayta — jurnalga yozilmadi", CA.put(T, json={"tartib": _yangi}).status_code == 200 and jurnal("dokon_telefon") == _j0)

# Oxirgi raqam
_r = CA.delete(T + f"/{T4}")
_r2 = CA.delete(T + f"/{T3}")
_r3 = CA.delete(T + f"/{T1}")
check("A17 oddiy raqamlar o'chdi; qolgan bitta («doim») — o'chirilmaydi (400 «Oxirgi raqam»)",
      _r.status_code == 200 and _r2.status_code == 200 and _r3.status_code == 200 and tel_soni() == 1
      and CA.delete(T + f"/{T2}").status_code == 400 and "Oxirgi raqam" in det(CA.delete(T + f"/{T2}")) and tel_soni() == 1,
      (_r.status_code, _r2.status_code, _r3.status_code, tel_bazada()))
check("A17b o'chirilgan raqam qayta — 404", CA.delete(T + f"/{T4}").status_code == 404)
# qayta: 3 ta raqam (egasining ro'yxati) — keyingi sinovlar uchun
CA.post(T, json={"raqam": "+998979995757"})
CA.post(T, json={"raqam": "+998976991919"})
_ids = [x["id"] for x in soz()["telefonlar"]]
CA.put(T, json={"tartib": [ix(_ids, 1), ix(_ids, 0), ix(_ids, 2)]})
CA.put(T + f"/{ix(_ids, 1)}", json={"doim": True})
CA.put(T + f"/{ix(_ids, 0)}", json={"doim": False, "izoh": "Menejer"})
check("A18 tayyorlandi: +998 97 999 57 57 (doim), +998 90 623 22 72 (Menejer), +998 97 699 19 19",
      tel_bazada() == [("+998979995757", True, None), ("+998906232272", False, "Menejer"), ("+998976991919", False, None)], tel_bazada())

# Korxona telefonlari
def _kx(d):
    co = d.get(Company, 1)
    co.phone, co.phone2, co.phone3 = "+998 97 999 57 57", "(71) 200-00-01", "Ofis: qo'ng'iroq qiling"


db_ishi(_kx)
check("A19 korxona sozlamalaridagi raqamlar: do'konda borlari va shakli noto'g'rilari chiqmaydi, qolgani bitta shaklda",
      lambda: soz()["korxona_telefonlari"] == [{"raqam": "+998712000001", "korinish": "+998 71 200 00 01"}], lambda: soz()["korxona_telefonlari"])

# Ish vaqti
I = API + "/ish-vaqti"
_j0 = jurnal("company_setting")
_r = CA.put(I, json={"kunlar": [6, 1, 2, 3, 4, 5], "boshi": "08:00", "oxiri": "18:00"})
check("A20 standart bilan bir xil ish vaqti — saqlandi (kiritilgan), lekin jurnalga o'zgarish yozilmadi",
      _r.status_code == 200 and soz()["ish_vaqti_kiritilgan"] is True and jurnal("company_setting") == _j0
      and json.loads(sozlama("dokon_ish_vaqti") or "{}").get("kunlar") == [1, 2, 3, 4, 5, 6], (_r.text[:200], jurnal("company_setting") - _j0))
_r = CA.put(I, json={"kunlar": [1, 2, 3, 4, 5], "boshi": "09:30", "oxiri": "17:45", "izoh": "Telefon orqali ma'lumot — 22:00 gacha"})
_s = soz()
check("A21 yangi ish vaqti va izoh — saqlandi, matn «Dushanba–juma, 9:30–17:45», jurnal",
      _r.status_code == 200 and _s["ish_vaqti"] == {"kunlar": [1, 2, 3, 4, 5], "boshi": "09:30", "oxiri": "17:45"}
      and _s["ish_vaqti_matni"] == "Dushanba–juma, 9:30–17:45" and _s["ish_izoh"] == "Telefon orqali ma'lumot — 22:00 gacha"
      and jurnal("company_setting") == _j0 + 1, (_r.text[:200], _s.get("ish_vaqti_matni")))
_r = CA.put(I, json={"kunlar": [1, 2, 3, 4, 5], "boshi": "09:30", "oxiri": "17:45"})
check("A22 izoh yuborilmasa — eskisi qoladi; o'zgarishsiz — jurnal yo'q",
      _r.status_code == 200 and soz()["ish_izoh"] == "Telefon orqali ma'lumot — 22:00 gacha" and jurnal("company_setting") == _j0 + 1)
_bad = [{"kunlar": [], "boshi": "08:00", "oxiri": "18:00"}, {"kunlar": [1, 1], "boshi": "08:00", "oxiri": "18:00"},
        {"kunlar": [8], "boshi": "08:00", "oxiri": "18:00"}, {"kunlar": [0], "boshi": "08:00", "oxiri": "18:00"},
        {"kunlar": [True], "boshi": "08:00", "oxiri": "18:00"}, {"kunlar": "1-6", "boshi": "08:00", "oxiri": "18:00"},
        {"kunlar": [1], "boshi": "8:00", "oxiri": "18:00"}, {"kunlar": [1], "boshi": "08:00", "oxiri": "24:00"},
        {"kunlar": [1], "boshi": "18:00", "oxiri": "08:00"}, {"kunlar": [1], "boshi": "08:00", "oxiri": "08:00"},
        {"kunlar": [1], "boshi": 8, "oxiri": "18:00"}, {"kunlar": [1], "boshi": "08:00", "oxiri": "18:00", "izoh": "x" * 201},
        {"kunlar": [1], "boshi": "08:00"}, {"kunlar": [1], "boshi": "08:00", "oxiri": "18:00", "x": 1},
        {"kunlar": [1, 2, 3, 4, 5, 6, 7, 1], "boshi": "08:00", "oxiri": "18:00"}, {"kunlar": [1.0], "boshi": "08:00", "oxiri": "18:00"},
        {"kunlar": [1], "boshi": "08:00\n", "oxiri": "18:00x"}]
_st = [CA.put(I, json=b).status_code for b in _bad]
check(f"A23 noto'g'ri ish vaqti ({len(_bad)} xil) — hammasi 400, sozlama o'zgarmadi",
      lambda: _st == [400] * len(_bad) and soz()["ish_vaqti"]["boshi"] == "09:30", list(zip(_st, [str(b)[:60] for b in _bad])))
_r = CA.put(I, json={"kunlar": [1, 2, 3, 4, 5, 6], "boshi": "08:00", "oxiri": "18:00", "izoh": None})
check("A23b izoh null — o'chirildi (sozlama qatori yo'q)", _r.status_code == 200 and soz()["ish_izoh"] is None
      and sozlama("dokon_ish_izoh") is None)
_mat = getattr(crud, "dokon_ish_vaqti_matni", None)
_kut = {(1, 2, 3, 4, 5, 6, "08:00", "18:00"): "Dushanba–shanba, 8:00–18:00",
        (1, 3, 5, "08:00", "18:00"): "Dushanba, chorshanba, juma, 8:00–18:00",
        (1, 2, 4, 5, 6, "10:05", "20:00"): "Dushanba, seshanba, payshanba–shanba, 10:05–20:00",
        (1, 2, 3, 4, 5, 6, 7, "00:00", "23:59"): "Har kuni, 0:00–23:59", (7, "08:00", "18:00"): "Yakshanba, 8:00–18:00",
        (6, 7, "08:00", "18:00"): "Shanba, yakshanba, 8:00–18:00", (1, 2, 3, 5, 6, 7, "08:00", "18:00"): "Dushanba–chorshanba, juma–yakshanba, 8:00–18:00"}


def _mk(k):
    return _mat({"kunlar": list(k[:-2]), "boshi": k[-2], "oxiri": k[-1]})


check("A24 ish vaqti matni — oraliq (3+ ketma-ket kun), alohida kunlar, «Har kuni», bosh harf, soat boshidagi 0 siz",
      lambda: {k: _mk(k) for k in _kut} == _kut, lambda: {k: _mk(k) for k in _kut if _mk(k) != _kut[k]})
for _buzuq in ("{buzuq", '{"kunlar": [], "boshi": "08:00", "oxiri": "18:00"}', '{"kunlar": [1], "boshi": "19:00", "oxiri": "08:00"}',
               '{"kunlar": [9], "boshi": "08:00", "oxiri": "18:00"}', "[]"):
    sozlama_yoz("dokon_ish_vaqti", _buzuq)
    _r = CA.get(API)
    check(f"A25 buzilgan ish vaqti sozlamasi ({_buzuq[:24]}) — katalog 200, standart qiymat",
          _r.status_code == 200 and js(_r).get("sozlamalar", {}).get("ish_vaqti") == STD_ISH, _r.text[:200])
sozlama_yoz("dokon_ish_vaqti", '{"kunlar":[1,2,3,4,5,6],"boshi":"08:00","oxiri":"18:00"}')

# Retsept
KP = API + "/komplekt"
_j0 = jurnal("company_setting")
_r = CA.put(KP, json={"retsept": STD})
check("A26 retsept = standart — 200, sozlama yozildi, jurnalga o'zgarish yo'q",
      _r.status_code == 200 and json.loads(sozlama("dokon_komplekt_retsept") or "null") == STD and jurnal("company_setting") == _j0,
      (_r.text[:200], jurnal("company_setting") - _j0))


def _rt(**o):
    r = json.loads(json.dumps(STD))
    for k, v in o.items():
        kom, t = k.split("__")
        if v == "YOQ":
            r[kom].pop(t)
        else:
            r[kom][t] = v
    return r


_bad = [_rt(rom__nalichnik=5), _rt(rom__karniz=-2), _rt(rom__karniz=42), _rt(eshik__nalichnik=41), _rt(rom__kapitel=21),
        _rt(rom__baza="2"), _rt(rom__baza=True), _rt(rom__karniz=2.5), _rt(eshik__nalichnik=None), _rt(rom__podokonnik="YOQ"),
        _rt(eshik__podokonnik=2), _rt(rom__karniz=0, rom__podokonnik=0, rom__nalichnik=0), _rt(eshik__karniz=0, eshik__nalichnik=0),
        _rt(rom__karniz=10 ** 400)]
_st = [CA.put(KP, json={"retsept": b}).status_code for b in _bad]
_st += [CA.put(KP, json={"retsept": {"rom": STD["rom"]}}).status_code, CA.put(KP, json={"retsept": [1]}).status_code,
        CA.put(KP, json={"retsept": dict(STD, ulgurji={})}).status_code, CA.put(KP, json={}).status_code,
        CA.put(KP, json={"x": 1}).status_code, CA.put(KP, json={"olcham": ""}).status_code,
        CA.put(KP, json={"olcham": "x" * 41}).status_code, CA.put(KP, json={"olcham": 5}).status_code]
check(f"A27 noto'g'ri retsept / o'lcham ({len(_st)} xil: rom toq metr, manfiy, > 40, kapitel > 20, satr, mantiqiy, kasr, null, "
      "yetishmaydi, eshikda podokonnik, metrsiz komplekt, 10^400, ortiqcha / yetishmagan komplekt, bo'sh o'lcham …) — hammasi 400",
      _st == [400] * len(_st) and json.loads(sozlama("dokon_komplekt_retsept") or "null") == STD, _st)
_r = CA.put(KP, json={"retsept": _rt(eshik__nalichnik=6.0, rom__baza=0), "olcham": "  Katta "})
check("A28 retsept saqlandi (6.0 → 6, baza 0), standart o'lcham «Katta»; jurnal 2 ta (retsept, o'lcham)",
      lambda: _r.status_code == 200 and js(_r).get("retsept", {}).get("eshik", {}).get("nalichnik") == 6
      and soz()["retsept"]["rom"]["baza"] == 0 and soz()["komplekt_olcham"] == "Katta" and jurnal("company_setting") == _j0 + 2,
      (_r.text[:300], jurnal("company_setting") - _j0))
for _buzuq in ("{", '{"rom": {}, "eshik": {}}', json.dumps(_rt(rom__nalichnik=3))):
    sozlama_yoz("dokon_komplekt_retsept", _buzuq)
    check(f"A29 buzilgan retsept sozlamasi ({_buzuq[:20]}) — standart retsept", lambda: soz()["retsept"] == STD)
CA.put(KP, json={"retsept": STD, "olcham": "O'rta"})

# Ikki korxona
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", True))
_a = tel_bazada()
_ida = [x["id"] for x in soz()["telefonlar"]]
_st = [CB.put(T + f"/{ix(_ida, 0)}", json={"izoh": "B"}).status_code, CB.delete(T + f"/{ix(_ida, 1)}").status_code,
       CB.put(T, json={"tartib": _ida}).status_code]
_rb = CB.post(T, json={"raqam": "+998 97 999 57 57"})
check("A30 B korxona: A ning raqamiga — 404, A ning id lari bilan tartib — 400; xuddi shu raqamni o'ziga qo'sha oladi; A o'zgarmadi",
      _st == [404, 404, 400] and _rb.status_code == 200 and tel_bazada() == _a and tel_bazada(2) == [("+998979995757", True, None)],
      (_st, _rb.status_code, tel_bazada(2)))
CB.put(API + "/ish-vaqti", json={"kunlar": [7], "boshi": "10:00", "oxiri": "11:00"})
check("A30b B ning ish vaqti / retsepti A ga ta'sir qilmaydi",
      lambda: soz()["ish_vaqti"] == STD_ISH and soz(CB)["ish_vaqti"] == {"kunlar": [7], "boshi": "10:00", "oxiri": "11:00"})


def _qoriqchi(d):
    t = DokonTelefon(company_id=2, raqam="+998900000001", doim=True, tartib=9)
    d.add(t)
    d.flush()
    return d.query(DokonTelefon).filter(DokonTelefon.raqam == "+998900000001").count()


check("A31 B korxona raqami bazaga to'g'ridan-to'g'ri — faqat company_id=2 bilan (A ro'yxatida yo'q)",
      lambda: xavfsiz(_qoriqchi) == 1 and "+998900000001" not in [x[0] for x in tel_bazada()])
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", None))
check("A31b B belgisi o'chirilgach — B uchun 404", CB.get(API).status_code == 404 and CB.post(T, json={"raqam": "+998900000002"}).status_code == 404)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Komplekt narxi — mustaqil hisob bilan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_k = katalog()
ROM = next((b["id"] for b in _k.get("bolimlar", []) if b.get("qolip") == "komplekt"), None)
KARNIZ = next((b["id"] for b in _k.get("bolimlar", []) if b.get("nom") == "Karnizlar"), None)
M1 = js(CA.post(API + "/modellar", json={"bolim_id": ROM, "kod": "R-18", "nom": "Klassik", "kapitel_baza_bor": True})).get("id")
M2 = js(CA.post(API + "/modellar", json={"bolim_id": ROM, "kod": "R-20", "kapitel_baza_bor": False})).get("id")
M3 = js(CA.post(API + "/modellar", json={"bolim_id": KARNIZ, "kod": "K-3"})).get("id")
# (turi, o'lcham) → (narx, narx_qoplamali, ulgurji, ulgurji_qoplamali, yoqilgan)
NARX = {
    ("karniz", "O'rta"): (15000, 32000, 26000, None, True), ("podokonnik", "O'RTA"): (14000, None, 24000, None, True),
    ("nalichnik", "o'rta"): (12000, None, 22000, 50000, True), ("kapitel", "O'rta"): (25000, None, 40000, None, True),
    ("baza", "O'rta"): (21000, None, 35000, None, True),
    ("karniz", "Katta"): (17000, None, None, None, True), ("podokonnik", "Katta"): (None, None, None, None, True),
    ("nalichnik", "Katta"): (14000, None, None, None, True), ("kapitel", "Katta"): (27000, None, None, None, False),
    ("baza", "Katta"): (23000, None, None, None, True),
    ("karniz", "Kichik"): (13333.33, None, 20001, None, True), ("podokonnik", "Kichik"): (12000, None, 18000, None, True),
    ("nalichnik", "Kichik"): (10050, None, 15000, None, True), ("kapitel", "Kichik"): (19999.99, None, 30000, None, True),
    ("baza", "Kichik"): (100, None, 150, None, True),
}
for (turi, ol), (n, nq, u, uq, yoq) in NARX.items():
    for _m in (M1, M2):
        if _m == M2 and turi in ("kapitel", "baza"):
            continue
        CA.post(API + "/detallar", json={"model_id": _m, "turi": turi, "olcham": ol, "narx": n, "narx_qoplamali": nq, "ulgurji_narx": u,
                                         "ulgurji_qoplamali": uq, "yoqilgan": yoq})
CA.post(API + "/detallar", json={"model_id": M3, "turi": "asosiy", "olcham": "15 sm", "narx": 50000})


def soni_d(mid):
    return db_ishi(lambda d: d.query(DokonDetal).filter(DokonDetal.model_id == mid).count())


check("K0 modellar va narx qatorlari yaratildi", lambda: soni_d(M1) == 15 and soni_d(M2) == 9,
      lambda: (soni_d(M1), soni_d(M2)))


def _avto(n, k):
    x = Decimal(str(n)) * Decimal(str(k))
    r = (x / 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 1000
    return r if r > 0 else x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def oracle(retsept, koeff, kb, model_turlari=None):
    """Mustaqil hisob: {o'lcham: {kom: {nom: summa | None}}} — NARX jadvalidan (kod funksiyalarisiz)."""
    nat = {}
    for ol in ("O'rta", "Katta", "Kichik"):
        det_ = {t: v for (t, o), v in NARX.items() if o.casefold() == ol.casefold() and (model_turlari is None or t in model_turlari)}
        nat[ol] = {}
        for kom, tur, q in (("rom", "o", retsept["rom"]), ("eshik", "o", retsept["eshik"]), ("ulgurji_rom", "u", retsept["rom"])):
            turlar = [t for t in q if q[t] and (kb or t not in ("kapitel", "baza"))]
            y = {}
            for qop in (False, True):
                for kbsiz in ((False, True) if kb else (False,)):
                    jami = Decimal("0")
                    for t in turlar:
                        if kbsiz and t in ("kapitel", "baza"):
                            continue
                        v = det_.get(t)
                        if v is None or not v[4]:
                            jami = None
                            break
                        n, nq, u, uq, _ = v
                        asos, alohida = (n, nq) if tur == "o" else (u, uq)
                        if asos is None:
                            jami = None
                            break
                        narx = Decimal(str(asos)) if not qop else (Decimal(str(alohida)) if alohida is not None else _avto(asos, koeff))
                        miq = q[t] // 2 if (tur == "u" and t in ("karniz", "podokonnik", "nalichnik")) else q[t]
                        jami += narx * miq
                    nom = ("qoplamali" if qop else "qoplamasiz") + ("_kbsiz" if kbsiz else "")
                    y[nom] = None if jami is None else float(jami.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            nat[ol][kom] = y
    return nat


def koddan(mid):
    r = (katalog().get("komplekt") or {}).get(str(mid)) or []
    return {x["olcham"]: {k: {n: v for n, v in x[k].items() if n != "yetishmaydi"} for k in ("rom", "eshik", "ulgurji_rom")} for x in r}


def solishtir(mid, kb, koeff=2, retsept=None, turlar=None):
    kod_ = koddan(mid)
    kut = oracle(retsept or STD, koeff, kb, turlar)
    kod_n = {o.casefold(): v for o, v in kod_.items()}
    return all(kod_n.get(o.casefold()) == v for o, v in kut.items()) and len(kod_n) == 3, (kod_, kut)


_ok, _d = solishtir(M1, True)
check("K1 R-18 (kapitel / baza bor): 3 o'lcham × rom / eshik / ulgurji rom × qoplamasiz / qoplamali × to'liq / kapitelsiz — "
      "mustaqil hisob bilan AYNAN (alohida qoplamali, avto × 2 1 000 ga, ulgurji 1 dona = 2 m, kasr narx)", _ok, _d)
_r = koddan(M1).get("O'rta", {}).get("rom", {})
check("K1b qo'lda tekshiruv: O'rta rom qoplamasiz = 2×15 000 + 2×14 000 + 4×12 000 + 2×25 000 + 2×21 000 = 198 000; "
      "kapitelsiz 106 000; qoplamali = 2×32 000 + 2×28 000 + 4×24 000 + 2×50 000 + 2×42 000 = 400 000",
      _r.get("qoplamasiz") == 198000.0 and _r.get("qoplamasiz_kbsiz") == 106000.0 and _r.get("qoplamali") == 400000.0, _r)
_u = koddan(M1).get("O'rta", {}).get("ulgurji_rom", {})
check("K1c ulgurji O'rta rom = karniz 1 × 26 000 + podokonnik 1 × 24 000 + nalichnik 2 × 22 000 + kapitel 2 × 40 000 + baza 2 × 35 000 = 244 000; "
      "qoplamali nalichnik — alohida 50 000", _u.get("qoplamasiz") == 244000.0
      and _u.get("qoplamali") == float(52000 + 48000 + 2 * 50000 + 2 * 80000 + 2 * 70000), _u)
_k1 = next((x for x in (katalog().get("komplekt") or {}).get(str(M1), []) if x["olcham"] == "Katta"), {})
check("K2 Katta: podokonnik narxi yo'q, kapitel — saytda yashirin → rom narxsiz va sabablari yozilgan; eshik (podokonniksiz) — "
      "to'liq narxsiz (kapitel), kapitelsiz — bor; ulgurji — narxsiz",
      _k1.get("rom", {}).get("qoplamasiz") is None and _k1.get("eshik", {}).get("qoplamasiz") is None
      and _k1.get("eshik", {}).get("qoplamasiz_kbsiz") == 2 * 17000 + 5 * 14000.0
      and any("Podokonnik" in y for y in _k1.get("rom", {}).get("yetishmaydi", []))
      and any("Kapitel" in y and "yashirin" in y for y in _k1.get("rom", {}).get("yetishmaydi", []))
      and _k1.get("ulgurji_rom", {}).get("qoplamasiz") is None, _k1)
_ok, _d = solishtir(M2, False, turlar=("karniz", "podokonnik", "nalichnik"))
check("K3 kapitelsiz model (R-20): kapitel / baza retseptda bo'lsa ham hisobga kirmaydi, `_kbsiz` kalitlari yo'q",
      _ok and all(not any(n.endswith("_kbsiz") for n in v["rom"]) for v in koddan(M2).values()), _d)
check("K3b o'lcham — detal qatorlari tartibidagi birinchi yozilishi («O'rta», «O'RTA», «o'rta» — bitta guruh)",
      lambda: [x["olcham"] for x in katalog()["komplekt"][str(M1)]] == ["O'rta", "Katta", "Kichik"])
check("K4 komplekt bo'lmagan model (karniz) — `komplekt` da yo'q; marshrut — bo'sh ro'yxat",
      str(M3) not in (katalog().get("komplekt") or {}) and js(CA.get(API + f"/modellar/{M3}/komplekt")).get("komplekt") == [])
_r = CA.get(API + f"/modellar/{M1}/komplekt")
check("K5 bitta model marshruti = katalogdagi bilan AYNAN; yo'q model — 404",
      lambda: _r.status_code == 200 and js(_r).get("komplekt") == katalog()["komplekt"][str(M1)]
      and CA.get(API + "/modellar/999999/komplekt").status_code == 404, _r.text[:200])
CA.put(API + "/koeff", json={"koeff": 2.5})
_ok, _d = solishtir(M1, True, koeff=Decimal("2.5"))
check("K6 koeffitsient 2,5 — avto qoplamali narxlar qayta hisoblandi (alohida yozilganlari o'zgarmadi)", _ok, _d)
_r2 = _rt(eshik__nalichnik=6, rom__kapitel=4, rom__nalichnik=6)
CA.put(KP, json={"retsept": _r2})
_ok, _d = solishtir(M1, True, koeff=Decimal("2.5"), retsept=_r2)
check("K7 retsept o'zgardi (eshik nalichnik 6 m, rom nalichnik 6 m, kapitel 4) — hamma narx yangi retsept bo'yicha", _ok, _d)
CA.put(KP, json={"retsept": STD})
CA.put(API + "/koeff", json={"koeff": 2})
_did = xavfsiz(lambda d: d.query(DokonDetal.id).filter(DokonDetal.model_id == M1, DokonDetal.turi == "karniz",
                                                       DokonDetal.olcham == "O'rta").scalar())
CA.put(API + f"/detallar/{_did}", json={"narx": 16000})
check("K8 detal narxi o'zgardi (karniz 15 000 → 16 000) — komplekt narxi darhol: rom 198 000 → 200 000, eshik 2 m ham",
      lambda: koddan(M1)["O'rta"]["rom"]["qoplamasiz"] == 200000.0 and koddan(M1)["O'rta"]["eshik"]["qoplamasiz"] ==
      2 * 16000 + 5 * 12000 + 2 * 25000 + 2 * 21000.0, lambda: koddan(M1)["O'rta"])
CA.put(API + f"/detallar/{_did}", json={"narx": 15000})
check("K9 B korxonasi A modelining komplektini ololmaydi (belgi yoqilgan B ham — 404)",
      lambda: (db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", True)), CB.get(API + f"/modellar/{M1}/komplekt").status_code)[1] == 404)
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", None))
M4 = js(CA.post(API + "/modellar", json={"bolim_id": ROM, "kod": "R-30", "kapitel_baza_bor": False})).get("id")
_st = [CA.post(API + "/detallar", json={"model_id": M4, "turi": tr, "olcham": ol, "narx": n}).status_code
       for tr, ol, n in (("karniz", "O'rta", 10000), ("podokonnik", "O\u2019rta", 9000), ("nalichnik", "O\u02bbRTA", 8000))]
_dup = CA.post(API + "/detallar", json={"model_id": M4, "turi": "karniz", "olcham": "o\u2018rta", "narx": 1})
check("K10 tutuq belgisi variantlari («O'rta», «O’rta», «OʻRTA») — bitta o'lcham: komplekt bitta guruh, rom = 2×10 000 + 2×9 000 + "
      "4×8 000 = 70 000; o'sha detal «o‘rta» bilan takror — 400 (review233 №3)",
      lambda: _st == [200, 200, 200] and _dup.status_code == 400 and len(katalog()["komplekt"][str(M4)]) == 1
      and katalog()["komplekt"][str(M4)][0]["rom"]["qoplamasiz"] == 70000.0, lambda: (_st, _dup.status_code, katalog()["komplekt"].get(str(M4))))
CA.delete(API + f"/modellar/{M4}")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("V. Ish vaqti — aniq vaqtlarda (Toshkent = UTC+5)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_iv = getattr(crud, "dokon_ish_vaqtimi", None)
# 2026-11-02 — dushanba, 2026-11-07 — shanba, 2026-11-08 — yakshanba
_holatlar = [(datetime(2026, 11, 2, 3, 0), True, "dushanba 08:00"), (datetime(2026, 11, 2, 2, 59), False, "dushanba 07:59"),
             (datetime(2026, 11, 2, 12, 59), True, "dushanba 17:59"), (datetime(2026, 11, 2, 13, 0), False, "dushanba 18:00"),
             (datetime(2026, 11, 7, 12, 30), True, "shanba 17:30"), (datetime(2026, 11, 8, 6, 0), False, "yakshanba 11:00"),
             (datetime(2026, 11, 1, 22, 30), False, "UTC yakshanba 22:30 = dushanba 03:30"),
             (datetime(2026, 11, 8, 2, 0), False, "UTC yakshanba 02:00 = yakshanba 07:00"),
             (datetime(2026, 11, 7, 20, 0), False, "UTC shanba 20:00 = yakshanba 01:00"),
             (datetime(2026, 12, 31, 18, 59), False, "31.12 23:59"), (datetime(2027, 1, 1, 3, 0), True, "01.01.2027 juma 08:00")]
check(f"V1 {len(_holatlar)} ta aniq vaqt: chegaralar (08:00 — ish, 18:00 — emas), yakshanba, UTC / Toshkent kun almashuvi",
      lambda: [_iv(STD_ISH, t) for t, _, _ in _holatlar] == [k for _, k, _ in _holatlar],
      lambda: [(n, _iv(STD_ISH, t)) for t, k, n in _holatlar if _iv(STD_ISH, t) != k])
_kt = getattr(crud, "dokon_korinadigan_telefonlar", None)
check("V2 ish vaqtida — 3 ta raqam (tartib bo'yicha), tashqarida va yakshanba — faqat «doim» (+998 97 999 57 57)",
      lambda: db_ishi(lambda d: ([t.raqam for t in _kt(d, 1, datetime(2026, 11, 2, 5, 0))],
                                 [t.raqam for t in _kt(d, 1, datetime(2026, 11, 2, 14, 0))],
                                 [t.raqam for t in _kt(d, 1, datetime(2026, 11, 8, 5, 0))]))
      == (["+998979995757", "+998906232272", "+998976991919"], ["+998979995757"], ["+998979995757"]))
_asl_utc = getattr(crud, "_dt233", None)


class _SoxtaVaqt:
    t = datetime(2026, 11, 8, 5, 0)

    @classmethod
    def utcnow(cls):
        return cls.t


if _asl_utc is not None:
    crud._dt233 = _SoxtaVaqt
    _a = soz()
    _SoxtaVaqt.t = datetime(2026, 11, 2, 5, 0)
    _b = soz()
    crud._dt233 = _asl_utc
    check("V3 katalogdagi `hozir_ish_vaqti` / `korinadigan_telefonlar` — server vaqtiga qarab (yakshanba — 1 ta, dushanba 10:00 — 3 ta)",
          _a["hozir_ish_vaqti"] is False and [x["raqam"] for x in _a["korinadigan_telefonlar"]] == ["+998979995757"]
          and _b["hozir_ish_vaqti"] is True and len(_b["korinadigan_telefonlar"]) == 3, (_a.get("korinadigan_telefonlar"), _b.get("hozir_ish_vaqti")))
else:
    check("V3 katalogdagi hozirgi raqamlar — server vaqtiga qarab", False, "crud._dt233 yo'q")

# Zaxira → tiklash
_oldin = (tel_bazada(), sozlama("dokon_ish_vaqti"), sozlama("dokon_komplekt_retsept"), sozlama("dokon_komplekt_olcham"))
_s = SessionLocal()
try:
    _zax = json.loads(json.dumps(crud.export_full_backup(_s, company_id=1), default=str))
finally:
    _s.close()
_s = SessionLocal()
try:
    _nat = crud.import_full_backup(_s, _zax, company_id=1, replace=True)
except Exception as e:                     # noqa: BLE001
    _nat = {"success": False, "message": f"{type(e).__name__}: {e}"}
_s.close()
check("A32 zaxirada `dokon_telefonlar` (3 ta); tiklashdan keyin raqamlar (tartib, doim, izoh) va sozlamalar AYNAN",
      len((_zax.get("tables") or {}).get("dokon_telefonlar") or []) == 3 and _nat.get("success") is True
      and (tel_bazada(), sozlama("dokon_ish_vaqti"), sozlama("dokon_komplekt_retsept"), sozlama("dokon_komplekt_olcham")) == _oldin,
      (str(_nat)[:300], tel_bazada()))
_oldin2 = tel_bazada()


def _tikla(o):
    z = json.loads(json.dumps(_zax))
    z.setdefault("tables", {})["dokon_telefonlar"] = o(json.loads(json.dumps((_zax.get("tables") or {}).get("dokon_telefonlar") or [])))
    s2 = SessionLocal()
    try:
        return crud.import_full_backup(s2, z, company_id=1, replace=True)
    except Exception as e:                 # noqa: BLE001
        return {"success": False, "message": f"QULADI {type(e).__name__}: {e}"}
    finally:
        s2.close()


def _hech_doim(r):
    for x in r:
        x["doim"] = False
    return r


def _ortiq(r):
    return r + [dict((r or [{}])[0], id=900 + i, raqam=f"+99890700000{i}", doim=False) for i in range(11)]


def _yomon_raqam(r):
    return [dict(x, raqam="12345") if i == 0 else x for i, x in enumerate(r)] or [{"id": 901, "raqam": "12345", "doim": True}]


def _takror(r):
    r = r or [{"id": 901, "raqam": "+998979995757", "doim": True}]
    return r + [dict(r[0], id=999)]


_nat2 = [_tikla(f) for f in (_hech_doim, _ortiq, _yomon_raqam, _takror)]
check("A34 qo'lda buzilgan zaxira (birorta «doim» yo'q / 11 ta raqam / «12345» / takror) — tiklash rad etildi, raqamlar o'zgarmadi "
      "(review233 №5)", lambda: all(n.get("success") is False and "dokon_telefonlar" in n.get("message", "") for n in _nat2)
      and tel_bazada() == _oldin2, lambda: ([str(n)[:120] for n in _nat2], tel_bazada()))
check("A33 server xatosi yo'q (ErrorLog)", db_ishi(lambda d: d.query(ErrorLog).count()) == 0,
      lambda: db_ishi(lambda d: [e.message[:200] for e in d.query(ErrorLog).limit(3).all()]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PG parallel")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    from concurrent.futures import ThreadPoolExecutor

    def parallel(fns):
        with ThreadPoolExecutor(max_workers=len(fns)) as ex:
            return [f.result() for f in [ex.submit(fn) for fn in fns]]

    _c1, _c2 = mijoz("t233_admin"), mijoz("t233_admin")
    _asl_tel = getattr(crud, "_dokon_telefonlar", None)

    def _sekin(*a, **k):
        r = _asl_tel(*a, **k)
        time.sleep(0.4)                    # tekshiruvdan KEYIN kechikish — qulfsiz kodda ikkalasi ham «joy bor» ko'rardi
        return r
    if _asl_tel:
        crud._dokon_telefonlar = _sekin
    _st = sorted(parallel([lambda: _c1.post(T, json={"raqam": "+998 93 000 00 01"}).status_code,
                           lambda: _c2.post(T, json={"raqam": "930000001"}).status_code]))
    check("P1 bir raqam ikki oynadan (har xil yozilishi) — bittasi 200, ikkinchisi 400 / 409, bazada 1 ta",
          _st[0] == 200 and _st[1] in (400, 409) and [x[0] for x in tel_bazada()].count("+998930000001") == 1, (_st, tel_bazada()))
    # faqat ikkita «doim» raqam qoldiramiz: X (doim), Y (doim)
    for _id in [x["id"] for x in soz()["telefonlar"]]:
        CA.put(T + f"/{_id}", json={"doim": True})
    for _id in [x["id"] for x in soz()["telefonlar"]][2:]:
        CA.delete(T + f"/{_id}")
    _ids = [x["id"] for x in soz()["telefonlar"]] + [0, 0]
    _st = sorted(parallel([lambda: _c1.put(T + f"/{_ids[0]}", json={"doim": False}).status_code,
                           lambda: _c2.put(T + f"/{_ids[1]}", json={"doim": False}).status_code]))
    check("P2 ikki «doim» raqamdan belgini bir vaqtda olish — bittasi 200, ikkinchisi 400; kamida bitta «doim» qoldi",
          _st == [200, 400] and sum(1 for x in tel_bazada() if x[1]) == 1 and len(tel_bazada()) == 2, (_st, tel_bazada()))
    CA.put(T + f"/{_ids[0]}", json={"doim": True})
    CA.put(T + f"/{_ids[1]}", json={"doim": True})
    _st = sorted(parallel([lambda: _c1.delete(T + f"/{_ids[0]}").status_code, lambda: _c2.delete(T + f"/{_ids[1]}").status_code]))
    check("P3 oxirgi ikki raqamni bir vaqtda o'chirish — bittasi 200, ikkinchisi 400; bitta («doim») raqam qoldi",
          _st == [200, 400] and len(tel_bazada()) == 1 and tel_bazada()[0][1] is True, (_st, tel_bazada()))
    for _i in range(10 - len(tel_bazada()) - 1):
        CA.post(T, json={"raqam": f"+99891500000{_i}"})
    _st = sorted(parallel([lambda: _c1.post(T, json={"raqam": "+998915000088"}).status_code,
                           lambda: _c2.post(T, json={"raqam": "+998915000099"}).status_code]))
    check("P5 9 ta raqamga ikki oynadan bir vaqtda yangi raqam — bittasi 200, ikkinchisi 400 (10 ta chegarasi), bazada 10 ta",
          _st == [200, 400] and len(tel_bazada()) == 10, (_st, len(tel_bazada())))
    if _asl_tel:
        crud._dokon_telefonlar = _asl_tel
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

    def och(pg, kalit):
        pg.evaluate(f"() => {{ const d = document.querySelector('details.sht[data-sht=\"{kalit}\"]'); if (d && !d.open) d.querySelector('summary').click(); }}")

    if br:
        try:
            # tayyorgarlik: 2 ta raqam (birinchisi doim)
            for _id in [x["id"] for x in soz()["telefonlar"]]:
                CA.put(T + f"/{_id}", json={"doim": True})
            _bor = soz()["telefonlar"]
            for x in _bor[1:]:
                CA.delete(T + f"/{x['id']}")
            CA.post(T, json={"raqam": "+998 97 699 19 19", "izoh": '"><b>Ofis</b>'})
            ctx, pg = kontekst("t233_admin")
            pg.goto(B + "/sayt-katalogi")
            _y = kut(pg, "document.querySelectorAll('#skSozIch details.sht').length === 3")
            check("U1 «Do'kon sozlamalari» — 3 shtorka (telefonlar, ish vaqti, retsept); sarlavhada «2 ta raqam», «Dushanba–shanba, 8:00–18:00»",
                  _y and "2 ta raqam" in pg.text_content("#skSozIch") and "Dushanba–shanba, 8:00–18:00" in pg.text_content("#skSozIch"),
                  pg.evaluate("document.getElementById('skSozIch').innerText.slice(0,300)"))
            pg.evaluate("() => { const b = [...document.querySelectorAll('#skBolimlar .sk-bolim')].find(x => x.innerText.includes('Rom va eshik')); b && b.click(); }")
            pg.wait_for_timeout(400)
            pg.evaluate(f"() => {{ const x = document.querySelector('[data-och=\"{M1}\"]'); x && x.click(); }}")
            pg.wait_for_timeout(600)
            _ol = pg.evaluate("""() => { const w = document.querySelector('.erp-content'), k = document.getElementById('skKoeff').closest('.card');
                const s = document.getElementById('skSoz'); return {w: !!w && w.contains(document.getElementById('skOng')),
                aylanadi: !!w && w.scrollHeight > w.clientHeight + 10, koeff: k.getBoundingClientRect().height,
                soz: s ? s.getBoundingClientRect().height : 0}; }""")
            check("U1c kompyuter (1440 × 900), model ochiq: sahifa `erp-content` ichida aylanadi; koeffitsient va sozlamalar kartochkalari "
                  "siqilmagan (asl kodda 2 px edi)", _ol["w"] and _ol["aylanadi"] and _ol["koeff"] > 60 and _ol["soz"] > 60, _ol)
            pg.evaluate("window.scrollTo(0, 0); document.querySelector('.erp-content') && document.querySelector('.erp-content').scrollTo(0, 0)")
            och(pg, "sk-soz-tel")
            check("U1b izohdagi HTML — matn bo'lib ko'rinadi (escape)",
                  pg.evaluate("[...document.querySelectorAll('.sk-tel [data-tf=izoh]')].some(i => i.value === '\\\"><b>Ofis</b>')")
                  and pg.evaluate("document.querySelectorAll('#skSozIch b').length") == 0)
            pg.fill("#skTelRaqam", "90 623 22 72")
            pg.fill("#skTelIzoh", "Menejer")
            _bas = len(SOROV)
            pg.click("#skTelQosh")
            _y = kut(pg, "document.querySelectorAll('.sk-tel[data-tel]').length === 3")
            check("U2 raqam qo'shildi (UI) — bazada +998906232272 «Menejer», ro'yxatda «+998 90 623 22 72», 1 ta POST",
                  _y and ("+998906232272", False, "Menejer") in tel_bazada()
                  and "+998 90 623 22 72" in pg.text_content("#skSozIch")
                  and [x for x in SOROV[_bas:] if x[0] == "POST"] == [("POST", T)], (tel_bazada(), SOROV[_bas:]))
            _t3 = xavfsiz(lambda d: d.query(DokonTelefon.id).filter(DokonTelefon.raqam == "+998906232272").scalar())
            pg.click(f".sk-tel[data-tel='{_t3}'] [data-tf=doim]")
            _y = kut(pg, f"document.querySelector(\".sk-tel[data-tel='{_t3}'] [data-tf=doim]\").checked")
            pg.wait_for_timeout(500)
            check("U3 «Ish vaqtidan tashqarida ham» belgisi — bazada doim", _y and ("+998906232272", True, "Menejer") in tel_bazada(), tel_bazada())
            pg.click(f".sk-tel[data-tel='{_t3}'] [data-tsur='-1']")
            _y = kut(pg, f"document.querySelectorAll('.sk-tel[data-tel]')[1].dataset.tel === '{_t3}'")
            check("U4 ▲ — raqam bir pog'ona yuqoriga (server tartibi = ekran), fokus o'sha raqam tugmasida",
                  _y and [x[0] for x in tel_bazada()][1] == "+998906232272"
                  and pg.evaluate(f"document.activeElement && document.activeElement.closest('.sk-tel') && document.activeElement.closest('.sk-tel').dataset.tel === '{_t3}'"),
                  tel_bazada())
            _bir = soz()["telefonlar"][0]["id"]
            pg.click(f".sk-tel[data-tel='{_bir}'] [data-tf=doim]")
            pg.wait_for_timeout(800)
            pg.fill(f".sk-tel[data-tel='{_t3}'] [data-tf=izoh]", "Menejer Ali")
            pg.press(f".sk-tel[data-tel='{_t3}'] [data-tf=izoh]", "Tab")
            pg.wait_for_timeout(800)
            check("U5 birinchi raqamdan «doim» olindi (boshqasi doim), izoh katakda saqlandi",
                  tel_bazada()[0][1] is False and ("+998906232272", True, "Menejer Ali") in tel_bazada(), tel_bazada())
            pg.click(f".sk-tel[data-tel='{_t3}'] [data-tf=doim]")
            pg.wait_for_timeout(800)
            check("U6 yagona «doim» dan belgini olish — server rad etdi, belgi ekranda qaytdi, bazada o'zgarmadi",
                  pg.evaluate(f"document.querySelector(\".sk-tel[data-tel='{_t3}'] [data-tf=doim]\").checked")
                  and ("+998906232272", True, "Menejer Ali") in tel_bazada(), tel_bazada())
            _oxirgi = soz()["telefonlar"][-1]["id"]
            pg.click(f".sk-tel[data-tel='{_oxirgi}'] [data-tochir]")
            pg.click("#ccModalOk")
            _y = kut(pg, "document.querySelectorAll('.sk-tel[data-tel]').length === 2")
            check("U7 o'chirish (tasdiq oynasi) — ro'yxatda 2 ta, bazada 2 ta", _y and len(tel_bazada()) == 2, tel_bazada())
            och(pg, "sk-soz-ish")
            pg.uncheck("#skSozIch [data-kun='6']")
            pg.fill("#skIshBoshi", "09:00")
            pg.fill("#skIshIzoh", "Telefon orqali ma'lumot — 22:00 gacha")
            pg.click("#skIshSaqla")
            _y = kut(pg, "document.getElementById('skSozIch').innerText.indexOf('Dushanba–juma, 9:00–18:00') >= 0")
            check("U8 ish vaqti (UI): shanba olindi, 09:00 — bazada va sarlavhada «Dushanba–juma, 9:00–18:00»",
                  _y and json.loads(sozlama("dokon_ish_vaqti"))["kunlar"] == [1, 2, 3, 4, 5]
                  and sozlama("dokon_ish_izoh") == "Telefon orqali ma'lumot — 22:00 gacha",
                  pg.evaluate("document.getElementById('skSozIch').innerText.slice(0,400)"))
            # komplekt bloki
            pg.evaluate("() => { const b = [...document.querySelectorAll('#skBolimlar .sk-bolim')].find(x => x.innerText.includes('Rom va eshik')); b.click(); }")
            pg.wait_for_timeout(500)
            pg.evaluate(f"() => {{ const m = document.querySelector('.sk-model[data-model=\"{M1}\"]'); if (m && !m.classList.contains('ochiq')) m.querySelector('[data-och]').click(); }}")
            _y = kut(pg, f"document.querySelector('[data-komplekt=\"{M1}\"]') && document.querySelector('[data-komplekt=\"{M1}\"]').innerText.indexOf('198') >= 0")
            check("U9 R-18 ichida «Komplekt narxlari»: O'rta rom 198 000 (standart belgisi), Katta — «Yetishmaydi: Podokonnik …»",
                  _y and "standart" in pg.text_content(f"[data-komplekt='{M1}']") and "Podokonnik" in pg.text_content(f"[data-komplekt='{M1}']"),
                  pg.evaluate(f"document.querySelector('[data-komplekt=\"{M1}\"]') && document.querySelector('[data-komplekt=\"{M1}\"]').innerText.slice(0,500)"))
            _nk = f"tr[data-detal='{_did}'] [data-df=narx]"
            _u = f"tr[data-detal='{_did}'] [data-df=ulgurji_narx]"
            pg.fill(_nk, "16000")
            pg.press(_nk, "Tab")
            pg.click(_u)
            pg.keyboard.press("Control+A")
            pg.keyboard.type("27")
            _y = kut(pg, f"document.querySelector('[data-komplekt=\"{M1}\"]').innerText.replace(/\\s/g, '').indexOf('qoplamasiz200000') >= 0")
            check("U10 karniz katagi 16 000 — komplekt bloki o'zi yangilandi (200 000), keyingi katakdagi yozilayotgan matn va fokus joyida",
                  _y and pg.evaluate(f"document.querySelector(\"{_u}\").value") == "27"
                  and pg.evaluate(f"document.activeElement === document.querySelector(\"{_u}\")"),
                  pg.evaluate(f"[document.querySelector(\"{_u}\").value, document.querySelector('[data-komplekt=\"{M1}\"]').innerText.slice(0,200)]"))
            pg.keyboard.press("Escape")
            pg.fill(_u, "26000")
            pg.press(_u, "Tab")
            pg.wait_for_timeout(600)
            pg.evaluate("window.scrollTo(0, 0); document.querySelector('.erp-content') && document.querySelector('.erp-content').scrollTo(0, 0)")
            och(pg, "sk-soz-retsept")
            pg.fill("#skSozIch [data-rk='eshik'][data-rt='nalichnik']", "6")
            pg.fill("#skKOlcham", "Katta")
            pg.click("#skRetseptSaqla")
            _y = kut(pg, "document.getElementById('skSozIch').innerText.indexOf('standart o\\'lcham: Katta') >= 0")
            pg.wait_for_timeout(800)
            check("U11 retsept (UI): eshik nalichnik 6, standart o'lcham «Katta» — bazada; komplekt bloki qayta hisoblandi (O'rta eshik, karniz 16 000: 184 000 → 196 000)",
                  _y and json.loads(sozlama("dokon_komplekt_retsept"))["eshik"]["nalichnik"] == 6 and sozlama("dokon_komplekt_olcham") == "Katta"
                  and kut(pg, f"(document.querySelector('[data-komplekt=\"{M1}\"]') || {{}}).innerText && document.querySelector('[data-komplekt=\"{M1}\"]').innerText.replace(/\\s/g, '').indexOf('196000') >= 0"),
                  pg.evaluate("document.getElementById('skSozIch').innerText.slice(0,300)"))
            pg.fill("#skSozIch [data-rk='rom'][data-rt='nalichnik']", "5")
            pg.click("#skRetseptSaqla")
            pg.wait_for_timeout(800)
            check("U12 rom nalichnik 5 (toq) — server rad etdi, bazada 4", json.loads(sozlama("dokon_komplekt_retsept"))["rom"]["nalichnik"] == 4)
            pg.click("#skRetseptStandart")
            pg.wait_for_timeout(1000)
            check("U13 «Egasi jadvali» — standart retsept tiklandi", json.loads(sozlama("dokon_komplekt_retsept")) == STD)
            # U17 (review233 №1): telefon amali boshqa formalardagi saqlanmagan matnni va fokusni o'chirmaydi
            pg.evaluate("window.scrollTo(0, 0); document.querySelector('.erp-content').scrollTo(0, 0)")
            for _k in ("sk-soz-tel", "sk-soz-ish", "sk-soz-retsept"):
                och(pg, _k)
            pg.fill("#skSozIch [data-rk='rom'][data-rt='nalichnik']", "8")
            pg.fill("#skIshBoshi", "10:00")
            pg.fill("#skTelRaqam", "93 1")
            _ids = [x["id"] for x in soz()["telefonlar"]]
            CA.put(T + f"/{_ids[0]}", json={"doim": True})
            CA.put(T + f"/{_ids[-1]}", json={"doim": False})
            pg.reload()
            kut(pg, "document.querySelectorAll('#skSozIch details.sht').length === 3")
            for _k in ("sk-soz-tel", "sk-soz-ish", "sk-soz-retsept"):
                och(pg, _k)
            pg.fill("#skSozIch [data-rk='rom'][data-rt='nalichnik']", "8")
            pg.fill("#skIshBoshi", "10:00")
            pg.fill("#skTelRaqam", "93 1")
            _ch = f".sk-tel[data-tel='{_ids[-1]}'] [data-tf=doim]"
            pg.focus(_ch)
            pg.keyboard.press("Space")
            pg.wait_for_timeout(1500)
            pg.wait_for_timeout(200)
            check("U17 «doim» (klaviatura, bo'shliq) — bazada saqlandi; retsept (8), ish boshi (10:00), yangi raqam («93 1») matnlari joyida, fokus o'sha belgida",
                  tel_bazada()[-1][1] is True
                  and pg.evaluate("document.querySelector(\"#skSozIch [data-rk='rom'][data-rt='nalichnik']\").value") == "8"
                  and pg.evaluate("document.getElementById('skIshBoshi').value") == "10:00"
                  and pg.evaluate("document.getElementById('skTelRaqam').value") == "93 1"
                  and pg.evaluate(f"document.activeElement === document.querySelector(\"{_ch}\")"),
                  pg.evaluate("[document.querySelector(\"#skSozIch [data-rk='rom'][data-rt='nalichnik']\").value, document.getElementById('skIshBoshi').value, document.getElementById('skTelRaqam').value, document.activeElement && document.activeElement.outerHTML.slice(0, 80)]"))
            # U18 (review233 №2): sekin tarmoq — izoh yozilib, ▼ bosildi: ro'yxat qayta chizilgach ekran = baza
            pg.reload()
            kut(pg, "document.querySelectorAll('#skSozIch details.sht').length === 3")
            och(pg, "sk-soz-tel")
            pg.evaluate("""() => { const f = window.fetch; window.__asl_fetch = f;
                window.fetch = (u, o) => (o && o.method === 'PUT' && /telefonlar\\/\\d+$/.test(String(u)))
                  ? new Promise(r => setTimeout(r, 1500)).then(() => f(u, o)) : f(u, o); }""")
            _iz = f".sk-tel[data-tel='{_ids[0]}'] [data-tf=izoh]"
            pg.click(_iz)
            pg.keyboard.press("End")
            pg.keyboard.type(" kech")
            pg.click(f".sk-tel[data-tel='{_ids[0]}'] [data-tsur='1']")
            _y = kut(pg, f"document.querySelectorAll('.sk-tel[data-tel]')[1] && document.querySelectorAll('.sk-tel[data-tel]')[1].dataset.tel === '{_ids[0]}'", 10000)
            pg.wait_for_timeout(500)
            _db = next((x["izoh"] for x in soz()["telefonlar"] if x["id"] == _ids[0]), "?")
            check("U18 sekin tarmoqda izoh yozilib ▼ bosildi — izoh saqlandi, ro'yxat qayta chizilgach ekranda ham o'sha (baza = ekran)",
                  _y and (_db or "").endswith("kech") and pg.evaluate(f"document.querySelector(\"{_iz}\").value") == _db,
                  (_db, pg.evaluate(f"document.querySelector(\"{_iz}\") && document.querySelector(\"{_iz}\").value")))
            pg.evaluate("() => { window.fetch = window.__asl_fetch; }")
            for _w in (375, 320):
                pg.set_viewport_size({"width": _w, "height": 800})
                pg.wait_for_timeout(300)
                och(pg, "sk-soz-tel")
                check(f"U14 telefon ({_w} px) — sahifa gorizontal toshmaydi, raqam qatori va komplekt jadvali sig'adi",
                      not pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
                      and pg.evaluate("[...document.querySelectorAll('.sk-tel')].every(q => q.getBoundingClientRect().right <= window.innerWidth + 1)")
                      and pg.evaluate("[...document.querySelectorAll('.sk-kjadval')].every(t => t.getBoundingClientRect().right <= window.innerWidth + 1)")
                      and pg.evaluate("[...document.querySelectorAll('.sk-retsept, .sk-kunlar, .sk-tel')].every(t => t.getBoundingClientRect().right <= document.getElementById('skSozIch').getBoundingClientRect().right + 1)"),
                      pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]"))
            ctx.close()
            check("U15 JS xatosi yo'q", not JS_XATO, JS_XATO[:3])
            check("U16 konsolda xato yo'q (ataylab rad etilgan 400 dan tashqari)", not [k for k in KONSOL if "400" not in k], KONSOL[:3])
        except Exception as e:             # noqa: BLE001
            import traceback
            print("".join(traceback.format_exc().splitlines(True)[-12:])[:3000])
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
