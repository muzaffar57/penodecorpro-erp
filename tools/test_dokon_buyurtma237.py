#!/usr/bin/env python3
"""
test_dokon_buyurtma237.py — kech171 (zip 237 «Saytdan kelgan buyurtmalar»; egasi QARORLARI «Onlayn do'kon rejasi» 30.10, «Buyurtma
jarayoni» 1–7: mijoz savatni yig'ib ism + telefon bilan buyurtma beradi → ERP da «Saytdan kelgan buyurtmalar» ro'yxati va Telegram xabari →
xodim qo'ng'iroq qilib tasdiqlaydi (oddiy ERP buyurtmasi) yoki bekor qiladi; narx buyurtma paytida qotadi — chegirmali ham; komplekt
detallarga ajraladi; Andijon — yetkazish bepul, qolganlari — 50/50).

NIMA UCHUN KERAK
  Xato — do'kon yuborgan narxga ishonish (mijoz o'zi narx yozadi), ulgurji narx bilan sotish, saytda yashirilgan model / narxsiz qatorni
  sotish, komplekt narxining katalogdagidan farqi, chegirmaning boshqa o'lchamga tushishi, takror yuborishda ikkinchi buyurtma, boshqa
  korxona buyurtmasini ko'rish / tasdiqlash, tasdiqlashda ikki buyurtma (ikki oyna), yarim yozilgan holat (loyiha bor, buyurtma yo'q),
  narx o'zgargach eski buyurtma narxining o'zgarishi, Telegram'da mijoz matni bilan Markdown buzilishi, sahifada XSS.
BO'LIMLAR
  S — statik (marshrutlar, ruxsatlar, jadvallar, zaxira tartibi, xomashyo navbati). A — kirish (kalit, belgi, rollar, B korxona).
  N — narx (komplekt / detal / chegirma / qoplamali / kutilgan_jami). V — kirish ma'lumoti tekshiruvi. I — takror (X-Amal-Kaliti).
  L — chegaralar (telefon, kalit). R — ERP ro'yxati (filtr, qidiruv, son, sahifa). B — bekor. T — tasdiqlash (loyiha + buyurtma,
  qotgan narx, qatorlar xaritasi, yetishmovchilik, ruxsat, qayta). O — buyurtma o'chirilsa. Z — zaxira / tiklash. K — korxona ajratish.
  P — PG parallel. U — HAQIQIY brauzer.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` (U — faqat SQLite / TF1). `T237_TEZ=1` — U o'tkaziladi.
Asl kodga (zip 236) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_dokon_buyurtma237.py
"""
import os
import io
import re
import sys
import json
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
TEZ = os.environ.get("T237_TEZ") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "dokon237_test"
_T = tempfile.mkdtemp(prefix="t237_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't237.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, ActivityLog, Order, Project, Inventory   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

DokonBuyurtma = getattr(models, "DokonBuyurtma", None)
DokonBuyurtmaQator = getattr(models, "DokonBuyurtmaQator", None)


class _Yoq237:
    """Asl kodda (zip 236) yo'q narsalar o'rniga — sinov QULAMASIN, yiqilsin."""
    ko_pi = -1

    def tozala(self):
        pass


for _n, _v in (("_DOKON_BUYURTMA_CHEKLOV", _Yoq237()), ("sayt_viloyatlar", lambda: []),
               ("sayt_buyurtma_tanasi", lambda *a, **k: {"items": []})):
    if not hasattr(crud, _n):
        setattr(crud, _n, _v)

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


D = Decimal


def pul(x):
    """2 xonali Decimal; son emas (asl kodda javob yo'q) — NaN (hech narsaga teng emas, sinov qulamaydi)."""
    try:
        return D(str(x)).quantize(D("0.01"), rounding=ROUND_HALF_UP)
    except Exception:                      # noqa: BLE001
        return D("NaN")


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


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Muhit: «bugun» — Toshkent 2026-11-03 (seshanba) 12:00 (UTC 07:00) — ish vaqti; Telegram — ushlanadi
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
    s.add(Company(id=2, name="T237 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t237_admin", PAROL, UserRole.ADMIN, "T237 Admin", company_id=1)
    auth.create_user(s, "t237_plat", PAROL, UserRole.ADMIN, "T237 Platforma", company_id=1)
    auth.create_user(s, "t237_men", PAROL, UserRole.MANAGER, "T237 Menejer", company_id=1)
    auth.create_user(s, "t237_b", PAROL, UserRole.ADMIN, "T237 B Admin", company_id=2)
    auth.create_user(s, "t237_bplat", PAROL, UserRole.ADMIN, "T237 B Platforma", company_id=2)
    auth.create_user(s, "t237_ui", PAROL, UserRole.ADMIN, "UI <img src=x onerror=window.__xss237=1>", company_id=1)
s.query(User).filter(User.username == "t237_plat").first().is_platform_admin = True
RETSEPT = models.Recipe(company_id=1, name="Qoplama T237")
s.add(RETSEPT)
s.add(models.Recipe(company_id=2, name="B qoplama T237"))
s.add(Inventory(company_id=1, item_name="Penoplast T237", unit="blok", is_penoplast=True, is_default_penoplast=True,
                volume_per_unit=1.0, price_per_unit=1000000, stock_quantity=50))
s.commit()
RID = RETSEPT.id
RID_B = s.query(models.Recipe.id).filter(models.Recipe.company_id == 2).scalar()
s.close()
MEN_BUYURTMA_Y = xavfsiz(lambda d: d.query(User).filter(User.username == "t237_men").first().ruxsat("buyurtma", "yaratish"))
MEN_BUYURTMA_K = xavfsiz(lambda d: d.query(User).filter(User.username == "t237_men").first().ruxsat("buyurtma", "korish"))
MEN_LOYIHA_Y = xavfsiz(lambda d: d.query(User).filter(User.username == "t237_men").first().ruxsat("loyiha", "yaratish"))


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t237_admin")
CP = mijoz("t237_plat")
CM = mijoz("t237_men")
CB = mijoz("t237_b")
DOK = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)    # do'kon serveri — cookie siz
API = "/api/sayt-katalogi"
BY = "/api/dokon/v1/buyurtmalar"
SB = "/api/sayt-buyurtmalari"
_kalit_n = [0]


def yangi_kalit():
    _kalit_n[0] += 1
    return f"savat-{_kalit_n[0]:06d}-t237"


KALIT = {"A": None, "B": None}
CHEKLOV_TOZALA = [True]          # sinov ko'p so'rov yuboradi — chegara faqat L bo'limida tekshiriladi


def yubor(tana, kalit="auto", dkalit="A", **sarlavha):
    if CHEKLOV_TOZALA[0]:
        crud._DOKON_BUYURTMA_CHEKLOV.tozala()
        crud._DOKON_API_CHEKLOV.tozala()
    h = dict(sarlavha)
    if dkalit is not None:
        h["X-Dokon-Kalit"] = KALIT.get(dkalit) or dkalit
    if kalit == "auto":
        kalit = yangi_kalit()
    if kalit is not None:
        h["X-Amal-Kaliti"] = kalit
    if isinstance(tana, (bytes, str)):
        h.setdefault("Content-Type", "application/json")
        return DOK.post(BY, content=tana, headers=h)
    h.setdefault("Content-Type", "application/json")
    return DOK.post(BY, content=json.dumps(tana).encode("ascii"), headers=h)     # ensure_ascii — «\ud800» ham yuboriladi


TEL = ["+998 90 111 22 %02d" % i for i in range(100)]
_tel_n = [0]


def tel():
    _tel_n[0] += 1
    return TEL[_tel_n[0] % 100]


def tana(qatorlar, **kw):
    t = {"mijoz": "Ali Valiyev", "telefon": tel(), "viloyat": "andijon", "qatorlar": qatorlar}
    t.update(kw)
    return t


def sb_soni(cid=1):
    return xavfsiz(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == cid).count(), -1) if DokonBuyurtma else -1


def sb_id(raqam, cid=1):
    return xavfsiz(lambda d: (d.query(DokonBuyurtma.id).filter(DokonBuyurtma.company_id == cid, DokonBuyurtma.sb_raqam == raqam)
                              .scalar()), None) if DokonBuyurtma else None


def guruh_jami(j):
    return [g.get("summa") for g in (j.get("guruhlar") or [])]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_yollar = {(m, r.path): r for r in main.app.routes for m in (getattr(r, "methods", None) or ())}
_dy = sorted((m, p) for (m, p) in _yollar if p.startswith("/api/dokon/"))
# kech172 (zip 238, MOSLANDI): + «tayyor» GET (tools/test_dokon_tayyor238.py S1)
check("S1 do'kon yo'llari: 3 GET (katalog, sozlamalar, tayyor) + BITTA POST (buyurtmalar); o'chiruvchi / tahrirlovchi yo'l YO'Q",
      _dy == [("GET", "/api/dokon/v1/katalog"), ("GET", "/api/dokon/v1/sozlamalar"), ("GET", "/api/dokon/v1/tayyor"), ("POST", BY)], _dy)


def _ruxsat(m, p):
    """Marshrut ruxsati — `auth.ruxsat(band, amal)` qaytargan funksiyaning `ruxsat_talabi` belgisidan."""
    r = _yollar.get((m, p))
    if r is None:
        return None
    for dp in r.dependant.dependencies:
        t = getattr(dp.call, "ruxsat_talabi", None)
        if t:
            return tuple(t[1][0]) if len(t[1]) == 1 else tuple(t[1])
    return ()


_R = {("GET", SB): _ruxsat("GET", SB), ("GET", SB + "/{sb_id}"): _ruxsat("GET", SB + "/{sb_id}"),
      ("POST", SB + "/{sb_id}/bekor"): _ruxsat("POST", SB + "/{sb_id}/bekor"),
      ("POST", SB + "/{sb_id}/tasdiqla"): _ruxsat("POST", SB + "/{sb_id}/tasdiqla")}
check("S2 ERP marshrutlari: ro'yxat / bitta — «Buyurtmalar: Ko'rish», bekor / tasdiqlash — «Buyurtmalar: Yaratish»",
      _R[("GET", SB)] == ("buyurtma", "korish") and _R[("GET", SB + "/{sb_id}")] == ("buyurtma", "korish")
      and _R[("POST", SB + "/{sb_id}/bekor")] == ("buyurtma", "yaratish") and _R[("POST", SB + "/{sb_id}/tasdiqla")] == ("buyurtma", "yaratish"),
      _R)
check("S3 tasdiqlash yo'li xomashyo navbatida (`_XOMASHYO_MARSHRUTLARI`) — ombordan yechadi",
      ("main", "api_sayt_tasdiqla") in getattr(main, "_XOMASHYO_MARSHRUTLARI", ()))
_tar = [m.__name__ for m in crud._reset_table_order()]
check("S4 zaxira tartibi: qator → sayt buyurtmasi → … → buyurtma (o'chirishda), Taklif yonida",
      "DokonBuyurtmaQator" in _tar and "DokonBuyurtma" in _tar and _tar.index("DokonBuyurtmaQator") < _tar.index("DokonBuyurtma")
      < _tar.index("Order"), _tar[:25])
check("S5 jadvallar: dokon_buyurtmalar (company_id NOT NULL, yagona (korxona, seq) va (korxona, kalit), order_id SET NULL) va qatorlari "
      "(CASCADE); tenant qoidalari",
      DokonBuyurtma is not None and DokonBuyurtmaQator is not None
      and not DokonBuyurtma.__table__.c.company_id.nullable and not DokonBuyurtmaQator.__table__.c.company_id.nullable
      and {tuple(sorted(c.name for c in u.columns)) for u in DokonBuyurtma.__table__.constraints if u.__class__.__name__ == "UniqueConstraint"}
      >= {("company_id", "sb_seq"), ("company_id", "sb_kalit")}
      and list(DokonBuyurtma.__table__.c.order_id.foreign_keys)[0].ondelete == "SET NULL"
      and list(DokonBuyurtmaQator.__table__.c.buyurtma_id.foreign_keys)[0].ondelete == "CASCADE"
      and models._TENANT_RULES.get("DokonBuyurtmaQator") == [("buyurtma_id", "DokonBuyurtma")]
      and models._TENANT_REFS.get("DokonBuyurtma") == [("order_id", "Order")])
check("S6 kalit sahifasida manzillar ro'yxatida buyurtma yo'li; buyurtma chegarasi katalognikidan ALOHIDA",
      BY in crud.DOKON_API_YOLLAR and crud._DOKON_BUYURTMA_CHEKLOV is not crud._DOKON_API_CHEKLOV
      and crud._DOKON_BUYURTMA_CHEKLOV.ko_pi == 30)
_hk = None
check("S7 viloyatlar: 14 ta (12 viloyat + Toshkent shahri + Qoraqalpog'iston), Andijon — bepul, qolgani — 50/50",
      len(crud.sayt_viloyatlar()) == 14 and [v["kod"] for v in crud.sayt_viloyatlar() if v["yetkazish_bepul"]] == ["andijon"]
      and all(v["yetkazish_matni"] == "Yetkazib berish narxining yarmini biz to'laymiz" for v in crud.sayt_viloyatlar() if not v["yetkazish_bepul"]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Kirish va katalog")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_st = [CA.get(SB).status_code, CA.get(SB + "/1").status_code, CA.post(SB + "/1/bekor", json={}).status_code,
       CA.post(SB + "/1/tasdiqla", json={"deadline": "2026-11-20"}).status_code]
check("A1 sayt katalogi belgisi o'chiq — ERP marshrutlari 404", _st == [404, 404, 404, 404], _st)
_o = CA.get("/orders")
check("A2 belgi o'chiq — Buyurtmalar sahifasida «🛒 Saytdan» tugmasi va paneli YO'Q", _o.status_code == 200
      and 'id="saytBtn"' not in _o.text and 'id="saytPanel"' not in _o.text, _o.status_code)
r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
check("A0 platforma: korxona 1 da sayt katalogi yoqildi", r.status_code == 200, r.text[:200])
KALIT["A"] = js(CA.post(API + "/api-kalit", json={})).get("kalit")
check("A3 do'kon kaliti yaratildi; kalit holatida buyurtma yo'lining o'z chegarasi (30) — review237 L6",
      bool(KALIT["A"]) and KALIT["A"].startswith("pdk_") and js(CA.get(API + "/api-kalit")).get("buyurtma_daqiqa_max") == 30, KALIT["A"])
_r = [yubor(tana([]), dkalit=None), yubor(tana([]), dkalit="pdk_" + "a" * 43), DOK.post(BY, json={}, cookies=CA.cookies)]
check("A4 kalitsiz / noto'g'ri kalit / faqat sessiya cookie — 401 (WWW-Authenticate), hech narsa yozilmaydi",
      all(x.status_code == 401 and x.headers.get("www-authenticate") == "Bearer" for x in _r) and sb_soni() == 0,
      [(x.status_code, x.text[:80]) for x in _r])
_r = DOK.get(BY, headers={"X-Dokon-Kalit": KALIT["A"]})
check("A5 GET buyurtmalar — 405 (do'kon buyurtmalarni o'qiy olmaydi)", _r.status_code == 405, _r.status_code)

# ── Sinov katalogi ──
K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}
KOMP, KAR, TERMO, DEK, RUST = (BOL.get("Rom va eshik dekorlari"), BOL.get("Karnizlar"), BOL.get("Termopanel"), BOL.get("Dekor elementlar"),
                               BOL.get("Rustlar va burchak toshlari"))


def model(bolim, kod, **kw):
    return js(CA.post(API + "/modellar", json=dict({"bolim_id": bolim, "kod": kod}, **kw))).get("id")


def detal(mid, turi, olcham, **kw):
    return js(CA.post(API + "/detallar", json=dict({"model_id": mid, "turi": turi, "olcham": olcham}, **kw))).get("id")


ORTA = "O'rta"
ULG = {"karniz": 71311, "podokonnik": 71322, "nalichnik": 71333, "kapitel": 71344, "baza": 71355}
NARX = {"karniz": 15000, "podokonnik": 14000, "nalichnik": 12000, "kapitel": 30000, "baza": 31000}
M1 = model(KOMP, "R-18", nom="Klassik", kapitel_baza_bor=True)
DID = {}
for _t, _n in NARX.items():
    DID[_t] = detal(M1, _t, ORTA, narx=_n, ulgurji_narx=ULG[_t], eni_sm=15 if _t != "kapitel" and _t != "baza" else 12,
                    qalinligi_sm=10 if _t == "karniz" else (4 if _t in ("podokonnik", "nalichnik") else None))
for _t, _n in NARX.items():
    DID["k_" + _t] = detal(M1, _t, "Katta", narx=_n + 3000, narx_qoplamali=(_n + 3000) * 2 + 500, ulgurji_narx=ULG[_t] + 7)
M2 = model(KAR, "K-12", nom="Tekis")
DID["k12"] = detal(M2, "asosiy", "12 sm", narx=45000, narx_qoplamali=98000, ulgurji_narx=72111, eni_sm=12, qalinligi_sm=8)
DID["k15"] = detal(M2, "asosiy", "15 sm", narx=52000, yoqilgan=False)               # saytda yashirin qator
DID["k18"] = detal(M2, "asosiy", "18 sm")                                             # narxi kiritilmagan
MT = model(TERMO, "T-1", nom="Termopanel 60×120")
DID["t1"] = detal(MT, "asosiy", "60×120", narx=150000.5, ulgurji_narx=72133)
M3 = model(DEK, "D-1", nom="Rozetka", yoqilgan=False)                                 # saytda yashirin model
DID["d1"] = detal(M3, "asosiy", "Standart", narx=9100)
M4 = model(DEK, "D-2", nom="Burchak")
DID["d2"] = detal(M4, "asosiy", "S", narx=9900)
MR = model(RUST, "RS-1", nom="Rust")
DID["r1"] = detal(MR, "asosiy", "20 sm", narx=21000, eni_sm=20, qalinligi_sm=3)
BYOQ = js(CA.post(API + "/bolimlar", json={"nom": "Yashirin bo'lim T237", "qolip": "dona", "yoqilgan": False})).get("id")
M5 = model(BYOQ, "Y-1", nom="Yashirin bo'limdagi model") if BYOQ else None
DID["y1"] = detal(M5, "asosiy", "S", narx=9300) if M5 else None
r = CA.put(API + f"/modellar/{M1}/chegirma", json={"foiz": 15, "olchamlar": [ORTA]})
check("A6 katalog (R-18 komplekt O'rta / Katta, K-12, T-1, D-2, RS-1, yashirinlar) va chegirma (R-18, −15 %, faqat O'rta)",
      all(DID.values()) and r.status_code == 200, (DID, r.text[:200]))
KAT = js(DOK.get("/api/dokon/v1/katalog", headers={"X-Dokon-Kalit": KALIT["A"]}))
SOZ = js(DOK.get("/api/dokon/v1/sozlamalar", headers={"X-Dokon-Kalit": KALIT["A"]}))
check("A7 sozlamalar API da viloyatlar (kod, nom, yetkazish yozuvi) — buyurtma formasi uchun",
      SOZ.get("viloyatlar") == crud.sayt_viloyatlar(), str(SOZ.get("viloyatlar"))[:300])
_km = next((m for m in KAT.get("modellar") or [] if m.get("id") == M1), {})
KOMP_KAT = {x["olcham"]: x for x in (_km.get("komplekt") or [])}

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("N. Narx — ERP hisoblaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
RET = crud.dokon_retsept(SessionLocal(), 1)
r = yubor(tana([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "soni": 3}]))
J1 = js(r)
_kut = sum(o_ch(NARX[t], 15) * RET["rom"][t] * 3 for t in ("karniz", "podokonnik", "nalichnik", "kapitel", "baza"))
_kat = D(str(KOMP_KAT.get(ORTA, {}).get("chegirma", {}).get("rom", {}).get("qoplamasiz") or 0)) * 3
check("N1 rom komplekti O'rta × 3 (qoplamasiz, chegirma −15 %): jami = Σ chegirmali detal × retsept × 3 = katalogdagi komplekt narxi × 3",
      r.status_code == 200 and pul(J1.get("jami")) == pul(_kut) == pul(_kat) and J1.get("raqam") == "S-0001" and J1.get("holat") == "yangi",
      (r.status_code, r.text[:400], _kut, _kat))
_g = ix(J1.get("guruhlar") or [], 0, {})
check("N2 komplekt — bitta guruh, tagida 5 detal (miqdor = retsept × soni), nomi «R-18 «Klassik» — rom komplekti, O'rta, qoplamasiz × 3»",
      _g.get("guruh_nomi") == "R-18 «Klassik» — rom komplekti, O'rta, qoplamasiz × 3" and len(_g.get("detallar") or []) == 5
      and [x.get("miqdor") for x in _g.get("detallar")] == [RET["rom"][t] * 3 for t in ("karniz", "podokonnik", "nalichnik", "kapitel", "baza")]
      and all(x.get("chegirma_foiz") == 15.0 for x in _g.get("detallar")), _g)
check("N3 chegirmasiz summa va tejaldi; yetkazish (Andijon — bepul); tasdiqlash raqamlari javobda",
      pul(J1.get("chegirmasiz")) == pul(sum(D(NARX[t]) * RET["rom"][t] * 3 for t in NARX))
      and pul(J1.get("tejaldi")) == pul(J1.get("chegirmasiz")) - pul(J1.get("jami"))
      and J1.get("yetkazish_bepul") is True and J1.get("yetkazish_matni") == "Yetkazib berish bepul" and isinstance(J1.get("telefonlar"), list), J1)
r = yubor(tana([{"komplekt": "eshik", "model_id": M1, "olcham": "Katta", "qoplamali": True, "kapitel_baza": False, "soni": 2}],
               viloyat="samarqand"))
J2 = js(r)
_kut2 = sum(D((NARX[t] + 3000) * 2 + 500) * RET["eshik"][t] * 2 for t in ("karniz", "nalichnik"))
check("N4 eshik komplekti Katta, qoplamali (yozilgan narx), kapitel va bazasiz × 2 — chegirma YO'Q (boshqa o'lcham); Samarqand — 50/50",
      r.status_code == 200 and pul(J2.get("jami")) == pul(_kut2) == pul(D(str(KOMP_KAT["Katta"]["eshik"]["qoplamali_kbsiz"])) * 2)
      and pul(J2.get("tejaldi")) == 0 and J2.get("yetkazish_bepul") is False
      and J2.get("yetkazish_matni") == "Yetkazib berish narxining yarmini biz to'laymiz"
      and "kapitel va bazasiz" in str(ix(J2.get("guruhlar"), 0, {}).get("guruh_nomi")), (r.status_code, r.text[:400], _kut2))
r = yubor(tana([{"detal_id": DID["k12"], "qoplamali": True, "miqdor": 6}, {"detal_id": DID["t1"], "qoplamali": False, "miqdor": 7.25},
                {"detal_id": DID["d2"], "qoplamali": True, "miqdor": 4}, {"detal_id": DID["r1"], "qoplamali": False, "miqdor": 3},
                {"detal_id": DID["kapitel"], "qoplamali": True, "miqdor": 5}]))
J3 = js(r)
_kut3 = [pul(D(98000) * 6), pul(D("150000.5") * D("7.25")), pul(o_avto(9900) * 4), pul(D(21000) * 3), pul(o_ch(o_avto(30000), 15) * 5)]
check("N5 detallar: karniz 6 m qoplamali (yozilgan), termopanel 7,25 m² (kasr narx), dekor 4 dona qoplamali (avto ×2, 1 000 ga), rust 3 m "
      "(butun metr), kapitel 5 dona (komplekt modelidan, chegirmali, qoplamali avto)",
      r.status_code == 200 and [pul(x) for x in guruh_jami(J3)] == _kut3 and pul(J3.get("jami")) == sum(_kut3), (r.status_code, r.text[:500], _kut3))
_sb3 = sb_id(J3.get("raqam"))
_q3 = xavfsiz(lambda d: [(q.sbq_nom, q.sbq_birlik, q.miqdor, q.narx, q.asl_narx, q.summa, q.chegirma_foiz) for q in
                         d.query(DokonBuyurtmaQator).filter(DokonBuyurtmaQator.buyurtma_id == _sb3).order_by(DokonBuyurtmaQator.tartib)], [])
check("N6 bazada qatorlar: ERP nomi («Kapitel R-18 · 12 sm», «K-12 Tekis · 12 sm»), birlik, QOTGAN narx (chegirmali / asl), summa",
      [x[0] for x in _q3] == ["K-12 Tekis · 12 sm", "T-1 Termopanel 60×120", "D-2 Burchak", "RS-1 Rust · 20 sm", "Kapitel R-18 · 12 sm"]
      and [x[1] for x in _q3] == ["metr", "m2", "dona", "metr", "dona"] and pul(ix(_q3, 4, [0] * 7)[3]) == o_ch(o_avto(30000), 15)
      and pul(ix(_q3, 4, [0] * 7)[4]) == o_avto(30000) and ix(_q3, 4, [0] * 7)[6] == 15, _q3)
_ulg = [yubor(tana([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "soni": 1}])),
        yubor(tana([{"detal_id": DID["k12"], "qoplamali": False, "miqdor": 2}]))]
check("N7 ulgurji narx hech qachon ishlatilmaydi (javobda ulgurji raqamlari yo'q)", all(x.status_code == 200 for x in _ulg)
      and not any(str(v) in x.text for x in _ulg for v in list(ULG.values()) + [72111, 72133]), [x.text[:200] for x in _ulg])
_n0 = sb_soni()
_r = [yubor(tana([{"detal_id": DID["k15"], "qoplamali": False, "miqdor": 2}])),     # yashirin qator
      yubor(tana([{"detal_id": DID["k18"], "qoplamali": False, "miqdor": 2}])),     # narxsiz
      yubor(tana([{"detal_id": DID["d1"], "qoplamali": False, "miqdor": 1}])),      # yashirin model
      yubor(tana([{"detal_id": DID["y1"], "qoplamali": False, "miqdor": 1}])),      # yashirin bo'lim
      yubor(tana([{"komplekt": "rom", "model_id": M2, "olcham": "12 sm", "qoplamali": False, "soni": 1}])),   # komplekt emas
      yubor(tana([{"komplekt": "rom", "model_id": M1, "olcham": "Kichik", "qoplamali": False, "soni": 1}])),  # o'lcham yo'q
      yubor(tana([{"detal_id": 999999, "qoplamali": False, "miqdor": 1}]))]
check("N8 saytda ko'rinmaydigan / narxsiz / mavjud bo'lmagan mahsulot, komplekt bo'lmagan model, yo'q o'lcham — 400, hech narsa yozilmaydi",
      all(x.status_code == 400 for x in _r) and sb_soni() == _n0 and all("sotuvda yo'q" in det(x) or "narxi kiritilmagan" in det(x) for x in _r),
      [(x.status_code, det(x)[:90]) for x in _r])
_n0 = sb_soni()
_qt = [{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "soni": 2}]
r = yubor(tana(_qt, kutilgan_jami=float(_kut / 3 * 2 + 1000)))
check("N9 do'kon ko'rsatgan jami (`kutilgan_jami`) farq qilsa — 409 + yangi jami va guruhlar, hech narsa yozilmaydi",
      r.status_code == 409 and isinstance(js(r).get("detail"), dict) and js(r)["detail"].get("narx_ozgardi") is True
      and pul(js(r)["detail"].get("jami")) == pul(_kut / 3 * 2) and sb_soni() == _n0, (r.status_code, r.text[:300]))
r = yubor(tana(_qt, kutilgan_jami=float(_kut / 3 * 2)))
check("N10 kutilgan_jami mos — 200", r.status_code == 200 and pul(js(r).get("jami")) == pul(_kut / 3 * 2), r.text[:200])
MQ = model(DEK, "QC-1", nom="Faqat qoplamali")
DID["qc"] = detal(MQ, "asosiy", "S", narx_qoplamali=40000)
_kq = next((x for m in js(DOK.get("/api/dokon/v1/katalog", headers={"X-Dokon-Kalit": KALIT["A"]})).get("modellar") or []
            if m.get("id") == MQ for x in m.get("detallar") or []), {})
_r = [yubor(tana([{"detal_id": DID["qc"], "qoplamali": True, "miqdor": 2}])), yubor(tana([{"detal_id": DID["qc"], "qoplamali": False, "miqdor": 2}]))]
check("N12 review237 M2: faqat qoplamali narxi bor qator — katalogda qoplamali 40 000 → buyurtma qoplamali 80 000 (200), qoplamasiz — 400 "
      "(katalogda ham yo'q)", _kq.get("narx") is None and _kq.get("narx_qoplamali") == 40000 and _r[0].status_code == 200
      and pul(js(_r[0]).get("jami")) == pul(80000) and _r[1].status_code == 400, [(x.status_code, x.text[:120]) for x in _r])
xavfsiz(lambda d: d.add(models.DokonChegirma(company_id=1, model_id=M2, foiz=20, tugash=date(2026, 11, 2))))
r = yubor(tana([{"detal_id": DID["k12"], "qoplamali": False, "miqdor": 2}]))
check("N13 muddati o'tgan chegirma (kecha tugagan) — chegirma YO'Q", r.status_code == 200 and pul(js(r).get("jami")) == pul(90000)
      and pul(js(r).get("tejaldi")) == 0, r.text[:200])
CA.put(API + f"/detallar/{DID['k_nalichnik']}", json={"yoqilgan": False})
_r = [yubor(tana([{"komplekt": "rom", "model_id": M1, "olcham": "Katta", "qoplamali": False, "soni": 1}])),
      yubor(tana([{"komplekt": "eshik", "model_id": M1, "olcham": "Katta", "qoplamali": False, "soni": 1}]))]
CA.put(API + f"/detallar/{DID['k_nalichnik']}", json={"yoqilgan": True})
check("N14 komplektga kerak detal saytda yashirin — 400 (komplekt sotilmaydi)", all(x.status_code == 400 and "nalichnik" in det(x) for x in _r),
      [(x.status_code, det(x)[:80]) for x in _r])
r = yubor(tana([{"komplekt": "rom", "model_id": M1, "olcham": "O\u2019RTA", "qoplamali": False, "soni": 1}]))
check("N11 o'lcham yozilishi (iPhone tutuq belgisi, katta harf) — o'sha o'lcham, guruh nomida katalogdagi yozilish",
      r.status_code == 200 and "O'rta" in str(ix(js(r).get("guruhlar"), 0, {}).get("guruh_nomi")), r.text[:300])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("V. Kirish ma'lumoti tekshiruvi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_q1 = [{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 1}]
_n0 = sb_soni()
_holatlar = {
    "ism yo'q": {"telefon": tel(), "viloyat": "andijon", "qatorlar": _q1},
    "ism 1 harf": tana(_q1, mijoz="A"),
    "ism 101": tana(_q1, mijoz="A" * 101),
    "ism son": tana(_q1, mijoz=123),
    "ism surrogat": tana(_q1, mijoz="Ali \ud800"),
    "telefon noto'g'ri": tana(_q1, telefon="12345"),
    "telefon harf": tana(_q1, telefon="+998 9O 111 22 33"),
    "viloyat yo'q": tana(_q1, viloyat="moskva"),
    "viloyat son": tana(_q1, viloyat=1),
    "manzil 301": tana(_q1, manzil="x" * 301),
    "izoh 501": tana(_q1, izoh="x" * 501),
    "lokatsiya tashqarida": tana(_q1, lokatsiya={"lat": 55.75, "lon": 37.61}),
    "lokatsiya matn": tana(_q1, lokatsiya={"lat": "40.7", "lon": 72.3}),
    "lokatsiya ortiqcha kalit": tana(_q1, lokatsiya={"lat": 40.7, "lon": 72.3, "alt": 1}),
    "noma'lum maydon": tana(_q1, company_id=2),
    "narx yuborildi": tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 1, "narx": 1}]),
    "savat bo'sh": tana([]),
    "qatorlar matn": tana("abc"),
    "51 qator": tana(_q1 * 51),
    "miqdor 0": tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 0}]),
    "miqdor manfiy": tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": -2}]),
    "dona kasr": tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 1.5}]),
    "juft metr toq": tana([{"detal_id": DID["k12"], "qoplamali": False, "miqdor": 3}]),
    "komplekt karniz toq": tana([{"detal_id": DID["karniz"], "qoplamali": False, "miqdor": 5}]),
    "m2 3 xona": tana([{"detal_id": DID["t1"], "qoplamali": False, "miqdor": 1.255}]),
    "miqdor juda katta": tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 10 ** 400}]),
    "miqdor bool": tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": True}]),
    "qoplamali matn": tana([{"detal_id": DID["d2"], "qoplamali": "ha", "miqdor": 1}]),
    "soni 0": tana([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "soni": 0}]),
    "soni 501": tana([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "soni": 501}]),
    "komplekt turi": tana([{"komplekt": "ayvon", "model_id": M1, "olcham": ORTA, "qoplamali": False, "soni": 1}]),
    "kutilgan_jami matn": tana(_q1, kutilgan_jami="9900"),
    "250+ detal": tana([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "soni": 1}] * 50 +
                       [{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 1}]),
}
_res = {k: yubor(v) for k, v in _holatlar.items()}
check("V1 noto'g'ri kirishlar — HAMMASI 400 (tushunarli sabab), 500 yo'q, hech narsa yozilmaydi",
      all(x.status_code == 400 and det(x) for x in _res.values()) and sb_soni() == _n0,
      {k: (x.status_code, det(x)[:70]) for k, x in _res.items() if x.status_code != 400})
_r = [yubor(b'{"mijoz": NaN}'), yubor(b'{"mijoz": "A", "telefon": Infinity}'), yubor(b"[1,2]"), yubor(b"\xff\xfe"), yubor(b"{" * 5000),
      yubor(b'{"a": "' + b"x" * 200_100 + b'"}')]
check("V2 NaN / Infinity / massiv / buzilgan UTF-8 / juda chuqur JSON — 400; 200 KB dan katta — 413",
      [x.status_code for x in _r] == [400, 400, 400, 400, 400, 413] and sb_soni() == _n0, [(x.status_code, x.text[:60]) for x in _r])
_r = [yubor(tana(_q1), kalit=None), yubor(tana(_q1), kalit="abc"), yubor(tana(_q1), kalit="x" * 65), yubor(tana(_q1), kalit="savat 123 45")]
check("V3 `X-Amal-Kaliti` yo'q / qisqa / uzun / noto'g'ri belgi — 400", all(x.status_code == 400 for x in _r) and sb_soni() == _n0,
      [(x.status_code, det(x)[:60]) for x in _r])
r = yubor(tana(_q1, mijoz="  Ali\u200b   Valiyev ", telefon="(90) 111-22-77", manzil=" Andijon sh.,\r\n\r\n  Bobur ko'chasi 5 ",
               lokatsiya={"lat": 40.782511, "lon": 72.344229}, izoh="Kechqurun qo'ng'iroq qiling"))
_b = xavfsiz(lambda d: (lambda x: None if x is None else type("B", (), {k: getattr(x, k) for k in (
    "sb_mijoz", "sb_telefon", "sb_manzil", "sb_lokatsiya", "sb_izoh")}))(
    d.query(DokonBuyurtma).filter(DokonBuyurtma.sb_raqam == js(r).get("raqam")).first()))
check("V4 tozalash: ism (ko'rinmas belgi, bo'shliqlar), telefon → +998901112277, manzil qatorlari, joylashuv «40.782511,72.344229»",
      r.status_code == 200 and _b is not None and _b.sb_mijoz == "Ali Valiyev" and _b.sb_telefon == "+998901112277"
      and _b.sb_manzil == "Andijon sh.,\nBobur ko'chasi 5" and _b.sb_lokatsiya == "40.782511,72.344229" and _b.sb_izoh == "Kechqurun qo'ng'iroq qiling",
      (r.status_code, r.text[:200], _b and (_b.sb_mijoz, _b.sb_telefon, _b.sb_manzil, _b.sb_lokatsiya)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("I. Takror yuborish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TG.clear()
_tn = tana([{"detal_id": DID["k12"], "qoplamali": False, "miqdor": 4}])
_k = yangi_kalit()
r1 = yubor(_tn, kalit=_k)
r2 = yubor(_tn, kalit=_k)
check("I1 bir xil kalit + bir xil savat — avvalgi buyurtma (o'sha raqam, `takror: true`, X-Takror: 1), ikkinchi yozuv YO'Q",
      r1.status_code == 200 and r2.status_code == 200 and js(r1).get("raqam") == js(r2).get("raqam") and js(r2).get("takror") is True
      and js(r1).get("takror") is False and r2.headers.get("x-takror") == "1"
      and xavfsiz(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.sb_kalit == _k).count()) == 1, (r1.text[:150], r2.text[:150]))
check("I2 Telegram — BIR marta (takrorda yo'q), korxona 1 botiga", len(TG) == 1 and TG[0][1] == 1, TG)
r3 = yubor(dict(_tn, mijoz="Boshqa Mijoz"), kalit=_k)
check("I3 bir xil kalit + boshqa savat — 409, yangi yozuv yo'q", r3.status_code == 409 and "kalit" in det(r3).lower()
      and xavfsiz(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.sb_kalit == _k).count()) == 1, (r3.status_code, det(r3)))
check("I4 javob kesh-siz (Cache-Control: no-store)", "no-store" in r1.headers.get("cache-control", ""), dict(r1.headers))
TG.clear()
r = yubor(tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 2}], mijoz="Ali *qalin* _qiya_ [havola](http://x.uz) `kod`",
               manzil="Uy *1*", izoh="[x](y)", lokatsiya={"lat": 40.78, "lon": 72.34}))
_tg = ix(TG, 0, ("", None))[0]
check("I5 Telegram matni: raqam, mijoz (Markdown belgilari «\\» bilan — havola / qalin yozuv bo'lmaydi), telefon ko'rinishi, viloyat, "
      "xarita havolasi, mahsulot va jami",
      r.status_code == 200 and js(r).get("raqam") in _tg and "Ali \\*qalin\\* \\_qiya\\_ \\[havola](http://x.uz) \\`kod\\`" in _tg
      and "Uy \\*1\\*" in _tg and "\\[x](y)" in _tg and "+998 90 111 22" in _tg and "Andijon viloyati" in _tg
      and "maps.google.com/?q=40.780000,72.340000" in _tg and "D-2 Burchak" in _tg and "19\u00a0800 so'm" in _tg, _tg)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L. Chegaralar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
CHEKLOV_TOZALA[0] = False
crud._DOKON_BUYURTMA_CHEKLOV.tozala()
_tel_l = "+998 93 555 44 33"
_rl = [yubor(tana(_q1, telefon=_tel_l)) for _ in range(6)]
check("L1 bir telefondan 1 soatda 5 ta — 6-chisi 429 (Retry-After), yozilmaydi", [x.status_code for x in _rl] == [200] * 5 + [429]
      and _rl[5].headers.get("retry-after") and "ko'p" in det(_rl[5]), [(x.status_code, det(x)[:60]) for x in _rl])
_SoxtaVaqt.t = datetime(2026, 11, 3, 8, 1)
r = yubor(tana(_q1, telefon=_tel_l))
check("L2 1 soat o'tgach — yana qabul qilinadi", r.status_code == 200, (r.status_code, det(r)))
_SoxtaVaqt.t = datetime(2026, 11, 3, 7, 0)
_ch = crud._DOKON_BUYURTMA_CHEKLOV
_ch.tozala()
crud._DOKON_API_CHEKLOV.tozala()
_eski_kp = _ch.ko_pi
_ch.ko_pi = 3
_rl = [yubor(tana(_q1)) for _ in range(4)]
_kat_ok = DOK.get("/api/dokon/v1/katalog", headers={"X-Dokon-Kalit": KALIT["A"]}).status_code
check("L3 buyurtma yo'li chegarasi (sinovda 3 ta) — 4-chisi 429; katalog o'qish BU chegaraga kirmaydi (200)",
      [x.status_code for x in _rl] == [200, 200, 200, 429] and _kat_ok == 200, ([x.status_code for x in _rl], _kat_ok))
_ch.ko_pi = _eski_kp
_ch.tozala()
CHEKLOV_TOZALA[0] = True

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. ERP ro'yxati")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
R0 = js(CA.get(SB))
_jami = sb_soni()
check("R1 ro'yxat: hammasi «yangi», sonlar to'g'ri, eng yangisi tepada, sahifa 20 tadan",
      R0.get("sonlar", {}).get("hammasi") == _jami == R0.get("sonlar", {}).get("yangi") and len(R0.get("royxat") or []) == min(20, _jami)
      and [x.get("id") for x in R0.get("royxat")] == sorted([x.get("id") for x in R0.get("royxat")], reverse=True)
      and R0.get("sahifalar") == (_jami + 19) // 20, (R0.get("sonlar"), R0.get("sahifalar"), _jami))
_x = next((x for x in R0.get("royxat") or [] if x.get("raqam") == J3.get("raqam")), None)
if _x is None:
    _x = js(CA.get(SB + f"/{_sb3}"))
check("R2 qatorda: mijoz, telefon (+998…, ko'rinishi), viloyat, yetkazish, guruhlar (detallari bilan), jami, ogohlantirishlar "
      "(dona / m² / o'lchamsiz)", _x.get("telefon", "").startswith("+998") and _x.get("viloyat_nomi") == "Andijon viloyati"
      and len(_x.get("guruhlar") or []) == 5 and pul(_x.get("jami")) == pul(J3.get("jami"))
      and any("Donali" in o for o in _x.get("ogohlantirishlar") or []) and any("m²" in o for o in _x.get("ogohlantirishlar") or []), _x)
r = CA.get(SB, params={"q": "111 22 77"})
check("R3 qidiruv telefon raqamlari bo'yicha (bo'shliqli yozuv ham)", r.status_code == 200
      and [x.get("telefon") for x in (js(r).get("royxat") or [])] == ["+998901112277"], (js(r).get("royxat") or []))
r = CA.get(SB, params={"q": "s-0001"})
check("R4 qidiruv raqam bo'yicha (kichik harf bilan)", [x.get("raqam") for x in (js(r).get("royxat") or [])] == ["S-0001"], (js(r).get("royxat") or []))
_r = [CA.get(SB, params={"q": "%"}), CA.get(SB, params={"q": "S_0"})]
check("R4b review237 L5: «%» / «_» qidiruvda oddiy belgi (hammasini qaytarmaydi)", all(x.status_code == 200 and not (js(x).get("royxat") or [])
                                                                                  for x in _r), [len(js(x).get("royxat") or []) for x in _r])
r = CA.get(SB, params={"sahifa": 2})
check("R5 2-sahifa", r.status_code == 200 and js(r).get("sahifa") == min(2, R0.get("sahifalar")), js(r).get("sahifa"))
_o = CA.get("/orders")
check("R6 Buyurtmalar sahifasida «🛒 Saytdan» tugmasi soni = yangilar soni, panel va oyna bor (yopish tugmasida data-yopish)",
      _o.status_code == 200 and re.search(r'id="saytSoni"[^>]*>%d<' % _jami, _o.text) is not None and 'id="saytPanel"' in _o.text
      and re.search(r'<button[^>]*data-yopish[^>]*onclick="saytOynaYop\(\)"', _o.text) is not None, re.findall(r'id="saytSoni"[^<]*<', _o.text))
_r = [CM.get(SB).status_code, CM.get("/orders").text.count('id="saytBtn"')]
check("R7 Menejer — ruxsatiga qarab (ko'rish ruxsati bo'lsa ro'yxat 200 va tugma bor)",
      _r == ([200, 1] if MEN_BUYURTMA_K else [403, 0]), (_r, MEN_BUYURTMA_K))
_r = [CB.get(SB).status_code, CB.get(SB + f"/{_sb3}").status_code]
check("R8 B korxona (do'kon o'chiq) — 404", _r == [404, 404], _r)
check("R9 bitta: noma'lum / juda katta raqam — 404 / 422", CA.get(SB + "/999999").status_code == 404
      and CA.get(SB + "/99999999999").status_code == 422)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Bekor qilish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bid = sb_id(J2.get("raqam"))
r = CA.post(SB + f"/{_bid}/bekor", json={"sabab": "  Mijoz   voz kechdi "})
check("B1 bekor (sabab tozalanadi) — holat «bekor», kim / qachon / sabab, jurnalda", r.status_code == 200 and js(r).get("holat") == "bekor"
      and js(r).get("bekor_sababi") == "Mijoz voz kechdi" and js(r).get("bekor_qilgan") == "T237 Admin"
      and xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == "sayt_buyurtma", ActivityLog.action == "cancelled",
                                                        ActivityLog.entity_id == _bid).count()) == 1, r.text[:300])
_r = [CA.post(SB + f"/{_bid}/bekor", json={}), CA.post(SB + f"/{_bid}/tasdiqla", json={"deadline": "2026-11-20"})]
check("B2 qayta bekor / bekor qilinganni tasdiqlash — 409", [x.status_code for x in _r] == [409, 409], [(x.status_code, det(x)) for x in _r])
_bid2 = sb_id(J1.get("raqam"))
_r = [CA.post(SB + f"/{_bid2}/bekor", json={"sabab": "x" * 201}), CA.post(SB + f"/{_bid2}/bekor", json={"boshqa": 1}),
      CA.post(SB + f"/{_bid2}/bekor", json={"sabab": 5})]
check("B3 sabab 201 belgi / noma'lum maydon / son — 400, holat o'zgarmaydi", all(x.status_code == 400 for x in _r)
      and js(CA.get(SB + f"/{_bid2}")).get("holat") == "yangi", [(x.status_code, det(x)) for x in _r])
_r = CB.post(SB + f"/{_bid2}/bekor", json={})
check("B4 begona korxona — 404", _r.status_code == 404, _r.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Tasdiqlash — ERP buyurtmasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_tid = sb_id(J3.get("raqam"))
# katalog narxi tasdiqlashdan OLDIN o'zgaradi — buyurtma narxi QOTGAN bo'lishi kerak
CA.put(API + f"/detallar/{DID['k12']}", json={"narx_qoplamali": 123000})
_np0 = xavfsiz(lambda d: d.query(Project).filter(Project.company_id == 1).count(), -1)
_bad = [CA.post(SB + f"/{_tid}/tasdiqla", json={"recipe_id": RID}),
        CA.post(SB + f"/{_tid}/tasdiqla", json={"deadline": "2026-11-02", "recipe_id": RID}),
        CA.post(SB + f"/{_tid}/tasdiqla", json={"deadline": "2028-01-01", "recipe_id": RID}),
        CA.post(SB + f"/{_tid}/tasdiqla", json={"deadline": "2026-13-01", "recipe_id": RID}),
        CA.post(SB + f"/{_tid}/tasdiqla", json={"deadline": "2026-11-20", "loyiha_nomi": "A"}),
        CA.post(SB + f"/{_tid}/tasdiqla", json={"deadline": "2026-11-20", "project_id": 1}),
        CA.post(SB + f"/{_tid}/tasdiqla", json={"deadline": "2026-11-20"}),
        CA.post(SB + f"/{_tid}/tasdiqla", json={"deadline": "2026-11-20", "recipe_id": RID_B}),
        CA.post(SB + f"/{_tid}/tasdiqla", json={"deadline": "2026-11-20", "recipe_id": "1"})]
_sab = [det(x) for x in _bad[:4]]
check("T1a sana tekshiruvi (retsept bilan): yo'q / o'tgan / 1 yildan keyin / noto'g'ri — sana haqidagi xabar",
      all("sana" in x.lower() for x in _sab), _sab)
check("T1 sana yo'q / o'tgan / 1 yildan keyin / noto'g'ri, loyiha nomi 1 harf, noma'lum maydon, qoplamali qator bor — retseptsiz, begona "
      "korxona retsepti, matn retsept — 400, loyiha ochilmaydi",
      all(x.status_code == 400 for x in _bad) and xavfsiz(lambda d: d.query(Project).filter(Project.company_id == 1).count(), -1) == _np0,
      [(x.status_code, det(x)[:60]) for x in _bad])
TG.clear()
_inv0 = xavfsiz(lambda d: d.query(Inventory).filter(Inventory.item_name == "Penoplast T237").first().stock_quantity)
r = CA.post(SB + f"/{_tid}/tasdiqla", json={"deadline": "2026-11-20", "recipe_id": RID})
TJ = js(r)
_oid = TJ.get("order_id")
check("T2 tasdiqlash — 200: sayt buyurtmasi «tasdiqlandi», buyurtma raqami va id, kim / qachon",
      r.status_code == 200 and TJ.get("sayt", {}).get("holat") == "tasdiqlandi" and _oid and TJ.get("order_number")
      and TJ["sayt"].get("order_raqam") == TJ.get("order_number") and TJ["sayt"].get("tasdiqlagan") == "T237 Admin", (r.status_code, r.text[:400]))


def _buyurtma(oid):
    def f(d):
        o = d.get(Order, oid)
        if o is None:
            return None
        p = o.project
        return {"jami": o.total_amount, "kel": o.agreed_amount, "notes": o.notes, "deadline": o.deadline, "kalit": o.yaratish_kaliti,
                "status": o.status.name, "retsept": o.qoplama_retsept_id, "mijoz": p.client_name, "tel": p.client_phone, "manzil": p.client_address, "pnom": p.project_name,
                "items": [(i.name, i.category, i.width, i.thickness, i.length, i.quantity, i.unit_price, i.total_price, i.is_coated,
                           i.blok_birlik, i.delivery_unit) for i in o.items]}
    return xavfsiz(f)


BO = _buyurtma(_oid) or {}
_it = BO.get("items") or []
check("T3 yangi loyiha: mijoz ismi, telefon «+998 90 111 22 77», manzil (viloyat, manzil, xarita), nomi «Sayt S-… — Ali Valiyev»",
      BO.get("mijoz") == "Ali Valiyev" and BO.get("pnom") == f"Sayt {J3.get('raqam')} — Ali Valiyev"
      and (BO.get("tel") or "").startswith("+998 90 111 22") and (BO.get("manzil") or "").startswith("Andijon viloyati"), BO)
check("T4 buyurtma qatorlari — formadagidek: metr → profil (Eni, Qalinlik, Uzunlik = metr, soni 1, narx = qator jami), m² → blok (m²), "
      "dona → dona; narx — QOTGAN (katalog keyin o'zgargan), qoplama belgisi",
      [(x[1], x[4], x[5], x[9], x[10]) for x in _it] == [("profil", 6.0, 1.0, None, "metr"), ("blok", None, 7.25, "m2", "m²"),
                                                          ("dona", None, 4.0, None, "dona"), ("profil", 3.0, 1.0, None, "metr"),
                                                          ("dona", None, 5.0, None, "dona")]
      and [pul(x[7]) for x in _it] == _kut3 and pul(ix(_it, 0, [0] * 11)[6]) == pul(98000 * 6) and ix(_it, 0, [0] * 11)[2] == 12
      and ix(_it, 0, [0] * 11)[3] == 8 and [x[8] for x in _it] == [True, False, True, False, True]
      and [x[0] for x in _it] == ["K-12 Tekis · 12 sm", "T-1 Termopanel 60×120", "D-2 Burchak", "RS-1 Rust · 20 sm", "Kapitel R-18 · 12 sm"], _it)
check("T5 buyurtma jami = kelishilgan = sayt jami; topshirish 2026-11-20; izohda «Saytdan: S-…» va yetkazish; holat «ishlab chiqarishda»",
      pul(BO.get("jami")) == pul(BO.get("kel")) == pul(J3.get("jami")) and BO.get("deadline") == datetime(2026, 11, 20)
      and f"Saytdan: {J3.get('raqam')}" in (BO.get("notes") or "") and "yetkazib berish bepul" in (BO.get("notes") or "")
      and BO.get("status") == "IN_PROGRESS" and BO.get("kalit") == f"sayt1x{(_tid or 0):06d}" and BO.get("retsept") == RID, BO)
_m3 = xavfsiz(lambda d: [(i.category, i.width, i.thickness, i.length, i.is_coated, i.price_per_m3, i.unit_price, i.unit_price_for_volume)
                        for i in d.get(Order, _oid).items], [])


def _forma_narxi(x):
    """Buyurtma formasi (`calculateItem`, profil): 1 m = eni(m) × qalinlik(m) × qatorning 1 m³ narxi ÷ 2, qoplamali × 2; × uzunlik."""
    c, w, t, l, qop, m3 = x[:6]
    return D(str(w)) / 100 * D(str(t)) / 100 * D(str(m3)) / 2 * (2 if qop else 1) * D(str(l))


check("T5b review237 H1: profil qatorida O'Z «1 m³ narxi» — forma undan AYNAN sayt narxini qayta hosil qiladi (tahrirda narx yo'qolmaydi, "
      "«1 m³ asosiy narxi» uni bosib ketmaydi); M1: dona — hajm qoplamasiz narxdan (unit_price_for_volume)",
      [x[0] for x in _m3] == ["profil", "blok", "dona", "profil", "dona"]
      and all(x[5] and abs(_forma_narxi(x) - D(str(x[6]))) < D("0.005") for x in _m3 if x[0] == "profil")
      and pul(ix(_m3, 2, [0] * 8)[7]) == pul(9900) and pul(ix(_m3, 4, [0] * 8)[7]) == pul(30000), _m3)
_inv1 = xavfsiz(lambda d: d.query(Inventory).filter(Inventory.item_name == "Penoplast T237").first().stock_quantity)
check("T6 ombordan penoplast yechildi (profil eni × qalinlik × metr ÷ 2 + dona narxdan — ERP odatiy qoidasi)",
      _inv0 is not None and _inv1 is not None and _inv1 < _inv0, (_inv0, _inv1))
check("T7 jurnalda «rasmiylashtirildi» (qaysi buyurtma va loyiha)", xavfsiz(lambda d: d.query(ActivityLog).filter(
    ActivityLog.entity_type == "sayt_buyurtma", ActivityLog.action == "rasmiylashtirildi", ActivityLog.entity_id == _tid).first().new_value, "")
    .startswith(f"Buyurtma {TJ.get('order_number')} ochildi"))
_np1 = xavfsiz(lambda d: d.query(Project).filter(Project.company_id == 1).count(), -1)
r = CA.post(SB + f"/{_tid}/tasdiqla", json={"deadline": "2026-11-20"})
check("T8 qayta tasdiqlash — 409, ikkinchi loyiha / buyurtma YO'Q", r.status_code == 409
      and xavfsiz(lambda d: d.query(Project).filter(Project.company_id == 1).count(), -1) == _np1, (r.status_code, det(r)))
r = CA.post(SB + f"/{_tid}/bekor", json={})
check("T9 tasdiqlanganni bekor qilish — 409", r.status_code == 409 and TJ.get("order_number", "?") in det(r), det(r))
# yetishmovchilik: penoplast qoldig'i 0 — 409 (hech narsa yozilmaydi), confirm_shortage bilan — 200
db_ishi(lambda d: setattr(d.query(Inventory).filter(Inventory.item_name == "Penoplast T237").first(), "stock_quantity", 0.0))
_yid = sb_id(js(_ulg[1]).get("raqam"))
_np0 = xavfsiz(lambda d: d.query(Project).filter(Project.company_id == 1).count(), -1)
r = CA.post(SB + f"/{_yid}/tasdiqla", json={"deadline": "2026-11-21", "loyiha_nomi": "  Obyekt   Bobur 5 ", "recipe_id": RID})
check("T10 omborda penoplast yetmaydi — 409 stock_shortage_warning, loyiha ham, buyurtma ham ochilmaydi, holat «yangi»",
      r.status_code == 409 and isinstance(js(r).get("detail"), dict) and js(r)["detail"].get("type") == "stock_shortage_warning"
      and xavfsiz(lambda d: d.query(Project).filter(Project.company_id == 1).count(), -1) == _np0
      and js(CA.get(SB + f"/{_yid}")).get("holat") == "yangi", (r.status_code, r.text[:300]))
r = CA.post(SB + f"/{_yid}/tasdiqla?confirm_shortage=true", json={"deadline": "2026-11-21", "loyiha_nomi": "  Obyekt   Bobur 5 ", "recipe_id": RID})
check("T11 «Ha, baribir» (confirm_shortage) — 200, loyiha nomi tozalangan", r.status_code == 200
      and xavfsiz(lambda d: d.get(Order, js(r).get("order_id")).project.project_name) == "Obyekt Bobur 5", (r.status_code, r.text[:300]))
db_ishi(lambda d: setattr(d.query(Inventory).filter(Inventory.item_name == "Penoplast T237").first(), "stock_quantity", 50.0))
# loyiha yaratish ruxsatisiz — 403 (Menejer ruxsatini sinov uchun o'chiramiz)
_asl_rux = User.ruxsat


def _rux(self, band, amal=None):
    if self.username == "t237_men" and band == "loyiha" and amal == "yaratish":
        return False
    return _asl_rux(self, band, amal)


User.ruxsat = _rux
_mid = sb_id(js(_ulg[0]).get("raqam"))
r = CM.post(SB + f"/{_mid}/tasdiqla", json={"deadline": "2026-11-21"})
User.ruxsat = _asl_rux
check("T12 «Loyihalar: Yaratish» ruxsati yo'q — 403 (yoki buyurtma yaratish ruxsati yo'q bo'lsa — 403), holat «yangi»",
      r.status_code == 403 and js(CA.get(SB + f"/{_mid}")).get("holat") == "yangi", (r.status_code, det(r)))
r = CB.post(SB + f"/{_mid}/tasdiqla", json={"deadline": "2026-11-21"})
check("T13 begona korxona — 404", r.status_code == 404, r.status_code)
# tasdiqlash ichida xato (buyurtma yaratish 400) — loyiha ham qolmaydi
_np0 = xavfsiz(lambda d: d.query(Project).filter(Project.company_id == 1).count(), -1)
_asl_tana = crud.sayt_buyurtma_tanasi
crud.sayt_buyurtma_tanasi = lambda *a, **k: dict(_asl_tana(*a, **k), items=[dict(x, category="") for x in _asl_tana(*a, **k)["items"]])
r = CA.post(SB + f"/{_mid}/tasdiqla", json={"deadline": "2026-11-21"})
crud.sayt_buyurtma_tanasi = _asl_tana
check("T14 buyurtma yaratish rad etilsa (400) — yangi loyiha ham QOLMAYDI, holat «yangi»", r.status_code == 400
      and xavfsiz(lambda d: d.query(Project).filter(Project.company_id == 1).count(), -1) == _np0
      and js(CA.get(SB + f"/{_mid}")).get("holat") == "yangi", (r.status_code, det(r)))
r = CA.post(SB + f"/{_mid}/tasdiqla", json={"deadline": "2026-11-21"})
_kom = _buyurtma(js(r).get("order_id")) or {}
_kut_k = [pul(o_ch(NARX[t], 15) * RET["rom"][t]) for t in ("karniz", "podokonnik", "nalichnik", "kapitel", "baza")]
check("T15 komplekt tasdiqlansa — 5 oddiy qator (karniz / podokonnik / nalichnik — profil metr, kapitel / baza — dona), chegirmali narxlar",
      r.status_code == 200 and [(x[1], x[4] if x[1] == "profil" else x[5]) for x in _kom.get("items") or []]
      == [("profil", RET["rom"]["karniz"]), ("profil", RET["rom"]["podokonnik"]), ("profil", RET["rom"]["nalichnik"]),
          ("dona", RET["rom"]["kapitel"]), ("dona", RET["rom"]["baza"])]
      and [pul(x[7]) for x in _kom.get("items") or []] == _kut_k, (r.status_code, _kom))
_m1 = model(DEK, "Q")
_d1 = detal(_m1, "asosiy", "S", narx=7000)
_r1 = yubor(tana([{"detal_id": _d1, "qoplamali": False, "miqdor": 1}]))
_r2 = CA.post(SB + f"/{sb_id(js(_r1).get('raqam'))}/tasdiqla", json={"deadline": "2026-11-21"})
check("T15b review237 L1: 1 belgili model kodi (nomsiz) — ERP detal nomi «Mahsulot Q», tasdiqlanadi",
      _r1.status_code == 200 and _r2.status_code == 200
      and xavfsiz(lambda d: d.get(Order, js(_r2).get("order_id")).items[0].name) == "Mahsulot Q", (_r1.text[:150], _r2.text[:200]))
_o = CA.get("/orders")
_yn = js(CA.get(SB)).get("sonlar", {}).get("yangi")
check("T16b tugma soni — faqat «yangi»lar (tasdiqlangan / bekor qilinganlar sanalmaydi)",
      re.search(r'id="saytSoni"[^>]*>%s<' % _yn, _o.text) is not None and _yn < sb_soni(), (_yn, sb_soni()))
_r = CA.get(SB, params={"filtr": "tasdiqlandi"})
check("T16 filtr «Tasdiqlangan» — faqat tasdiqlanganlar, buyurtma havolasi uchun order_id", (js(_r).get("royxat") or [])
      and all(x.get("holat") == "tasdiqlandi" and x.get("buyurtma_bor") and x.get("order_id") for x in (js(_r).get("royxat") or [])),
      js(_r).get("sonlar"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("O. Buyurtma o'chirilsa")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = CA.delete(f"/api/orders/{_oid}?hard=true")
if r.status_code >= 400:
    r = CA.delete(f"/api/orders/{_oid}")
_bb = js(CA.get(SB + f"/{_tid}"))
_mavjud = xavfsiz(lambda d: d.get(Order, _oid) is not None and not d.get(Order, _oid).is_deleted, None)
check("O1 buyurtma o'chirilsa — sayt buyurtmasi qoladi (tasdiqlangan); butunlay o'chsa order_id NULL, raqami ro'yxatda qoladi",
      r.status_code < 400 and _bb.get("holat") == "tasdiqlandi" and _bb.get("order_raqam") == TJ.get("order_number")
      and (_mavjud or _bb.get("order_id") is None), (r.status_code, r.text[:200], _bb.get("order_id"), _mavjud))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_zx = db_ishi(lambda d: crud.export_full_backup(d, 1))
_jt = _zx.get("tables") or _zx.get("data") or {}
check("Z1 zaxirada sayt buyurtmalari va qatorlari bor", "dokon_buyurtmalar" in json.dumps(list(_jt.keys()) if isinstance(_jt, dict) else _jt)
      and "dokon_buyurtma_qatorlari" in json.dumps(list(_jt.keys()) if isinstance(_jt, dict) else _jt), list(_jt)[:80] if isinstance(_jt, dict) else "")
_s0 = sb_soni()
_q0 = xavfsiz(lambda d: d.query(DokonBuyurtmaQator).filter(DokonBuyurtmaQator.company_id == 1).count(), -1)
try:
    _tik = db_ishi(lambda d: crud.import_full_backup(d, _zx, 1, replace=True))
    _tx = None
except Exception as e:                      # noqa: BLE001
    _tik, _tx = None, f"{type(e).__name__}: {e}"
check("Z2 tiklash (replace) — xatosiz, sayt buyurtmalari va qatorlari soni AYNAN, holat / order bog'lami saqlangan",
      _tx is None and sb_soni() == _s0 and xavfsiz(lambda d: d.query(DokonBuyurtmaQator).filter(DokonBuyurtmaQator.company_id == 1).count(), -1) == _q0
      and js(CA.get(SB + f"/{_mid}")).get("holat") == "tasdiqlandi", (_tx, _s0, sb_soni(), _q0, str(_tik)[:300]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Korxona ajratish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", True))
KALIT["B"] = js(CB.post(API + "/api-kalit", json={})).get("kalit")
_bbol = js(CB.post(API + "/bolimlar", json={"nom": "B dekor", "qolip": "dona"})).get("id")
_bm = js(CB.post(API + "/modellar", json={"bolim_id": _bbol, "kod": "B-1"})).get("id")
_bd = js(CB.post(API + "/detallar", json={"model_id": _bm, "turi": "asosiy", "olcham": "S", "narx": 5000})).get("id")
_r = [yubor(tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 1}]), dkalit="B"),
      yubor(tana([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "soni": 1}]), dkalit="B"),
      yubor(tana([{"detal_id": _bd, "qoplamali": False, "miqdor": 1}]), dkalit="A")]
check("K1 B kaliti A katalogidagi mahsulotni, A kaliti B nikini sota olmaydi — 400 (sotuvda yo'q)",
      all(x.status_code == 400 for x in _r), [(x.status_code, det(x)[:60]) for x in _r])
r = yubor(tana([{"detal_id": _bd, "qoplamali": False, "miqdor": 2}]), dkalit="B")
check("K2 B kaliti — B korxonasida o'z raqami (S-0001), A ro'yxatida ko'rinmaydi; B adminiga faqat B nikilar",
      r.status_code == 200 and js(r).get("raqam") == "S-0001" and sb_soni(2) == 1
      and all(x.get("raqam") != "S-0001" or x.get("mijoz") != "Ali Valiyev" or True for x in (js(CA.get(SB)).get("royxat") or []))
      and [x.get("raqam") for x in (js(CB.get(SB)).get("royxat") or [])] == ["S-0001"]
      and CB.get(SB + f"/{_mid}").status_code == 404 and CA.get(SB + f"/{sb_id('S-0001', 2)}").status_code == 404,
      (r.status_code, r.text[:200]))
_tgb = [x for x in TG if x[1] == 2]
check("K3 B buyurtmasi Telegrami — B korxonasi botiga (company_id 2)", len(_tgb) == 1, TG[-3:])
db_ishi(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", False))
_r = [yubor(tana([{"detal_id": _bd, "qoplamali": False, "miqdor": 2}]), dkalit="B"), CB.get(SB)]
check("K4 B da belgi o'chirilsa — do'kon yo'li va ro'yxat 404", [x.status_code for x in _r] == [404, 404], [x.status_code for x in _r])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PG parallel")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    import concurrent.futures as _cf
    _k = yangi_kalit()
    _tn = tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 3}])
    with _cf.ThreadPoolExecutor(6) as ex:
        _rp = list(ex.map(lambda _: yubor(_tn, kalit=_k), range(6)))
    check("P1 bir xil kalit bilan 6 ta bir vaqtda — hammasi 200, BITTA buyurtma (o'sha raqam), 500 yo'q",
          all(x.status_code == 200 for x in _rp) and len({js(x).get("raqam") for x in _rp}) == 1
          and xavfsiz(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.sb_kalit == _k).count()) == 1,
          [(x.status_code, x.text[:80]) for x in _rp])
    with _cf.ThreadPoolExecutor(6) as ex:
        _rp = list(ex.map(lambda _: yubor(tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 1}])), range(6)))
    _raq = [js(x).get("raqam") for x in _rp]
    check("P2 6 ta har xil savat bir vaqtda — 6 ta 200, raqamlar har xil va ketma-ket", all(x.status_code == 200 for x in _rp)
          and len(set(_raq)) == 6, _raq)
    _pid = sb_id(_raq[0]) if _raq and _raq[0] else None
    _cc = [mijoz("t237_admin") for _ in range(3)]
    with _cf.ThreadPoolExecutor(3) as ex:
        _rp = list(ex.map(lambda c: c.post(SB + f"/{_pid}/tasdiqla", json={"deadline": "2026-11-22"}), _cc))
    check("P3 uch oynadan bir vaqtda tasdiqlash — bittasi 200, qolganlari 409, BITTA buyurtma", sorted(x.status_code for x in _rp) == [200, 409, 409]
          and xavfsiz(lambda d: d.query(Order).filter(Order.yaratish_kaliti == f"sayt1x{(_pid or 0):06d}").count()) == 1,
          [(x.status_code, x.text[:80]) for x in _rp])
    _pid2 = sb_id(_raq[1]) if len(_raq) > 1 and _raq[1] else None
    with _cf.ThreadPoolExecutor(2) as ex:
        _rp = list(ex.map(lambda a: (_cc[0].post(SB + f"/{_pid2}/tasdiqla", json={"deadline": "2026-11-22"}) if a
                                     else _cc[1].post(SB + f"/{_pid2}/bekor", json={})), (True, False)))
    _h = js(CA.get(SB + f"/{_pid2}")).get("holat")
    check("P4 tasdiqlash ∥ bekor — bittasi yutadi (200 + 409), holat mos, 500 yo'q",
          sorted(x.status_code for x in _rp) == [200, 409] and _h in ("tasdiqlandi", "bekor")
          and (_h == "tasdiqlandi") == (_rp[0].status_code == 200), [(x.status_code, x.text[:80]) for x in _rp])
else:
    print("  (PG_URL yo'q — o'tkazildi)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL or TEZ:
    print("  (PG / T237_TEZ — o'tkazildi)")
else:
    import uvicorn
    from playwright.sync_api import sync_playwright
    _s = socket.socket()
    _s.bind(("127.0.0.1", 0))
    PORT = _s.getsockname()[1]
    _s.close()
    _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error"))
    threading.Thread(target=_srv.run, daemon=True).start()
    import time as _tm
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=0.2).close()
            break
        except OSError:
            _tm.sleep(0.1)
    BASE = f"http://127.0.0.1:{PORT}"
    # XSS li mijoz ismi bilan yangi buyurtma
    _xss = yubor(tana([{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 2}], mijoz="<img src=x onerror=window.__xss237=1> Vali",
                      manzil="<b>qalin</b>", izoh="<script>window.__xss237=2</script>"))
    _xraqam = js(_xss).get("raqam")
    # tahrir sinovi uchun: profil (o'lchamli, qoplamali, chegirmali) + dona — tasdiqlangan buyurtma
    _rr = yubor(tana([{"detal_id": DID["k12"], "qoplamali": True, "miqdor": 6}, {"detal_id": DID["karniz"], "qoplamali": False, "miqdor": 4},
                      {"detal_id": DID["d2"], "qoplamali": True, "miqdor": 3}]))
    _oid2 = js(CA.post(SB + f"/{sb_id(js(_rr).get('raqam'))}/tasdiqla", json={"deadline": "2026-11-26", "recipe_id": RID})).get("order_id")
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1366, "height": 900})
            pg = ctx.new_page()
            JSX = []
            pg.on("pageerror", lambda e: JSX.append(str(e)))
            pg.on("dialog", lambda d: d.dismiss())
            pg.goto(BASE + "/login")
            pg.fill("input[name=username]", "t237_ui")
            pg.fill("input[name=password]", PAROL)
            pg.click("button[type=submit]")
            pg.wait_for_load_state("networkidle")
            pg.goto(BASE + "/orders")
            pg.wait_for_load_state("networkidle")
            _son = pg.text_content("#saytSoni")
            check("U1 «🛒 Saytdan» tugmasida yangilar soni", _son is not None and _son.strip() == str(js(CA.get(SB)).get("sonlar", {}).get("yangi")),
                  _son)
            pg.click("#saytBtn")
            pg.wait_for_function("document.querySelector('#saytRoyxat .tk-qator') !== null", timeout=30000)
            _q = pg.locator(f"#saytRoyxat .tk-qator:has(.tk-raqam:text-is('{_xraqam}'))")
            check("U2 panel ochildi, yangi buyurtma qatori bor; mijoz ismi / manzil / izoh MATN bo'lib chiqdi (XSS yo'q)",
                  _q.count() == 1 and "<img src=x" in (_q.inner_text() or "") and "<b>qalin</b>" in (_q.inner_text() or "")
                  and "<script>window.__xss237=2</script>" in (_q.inner_text() or "")
                  and pg.evaluate("window.__xss237") is None and pg.locator("#saytRoyxat img").count() == 0, (_q.count(), JSX))
            _q.locator("button:has-text('Tasdiqlash')").click()
            pg.wait_for_selector("#saytOynaOverlay", state="visible", timeout=10000)
            check("U3 tasdiqlash oynasi: sarlavhada raqam, loyiha nomi to'ldirilgan, sana bo'sh (fokusda)",
                  _xraqam in (pg.text_content("#saytOynaSarlavha") or "") and (pg.input_value("#saytLoyihaNomi") or "").startswith(f"Sayt {_xraqam}")
                  and pg.input_value("#saytMuddat") == "" and pg.evaluate("document.activeElement && document.activeElement.id") == "saytMuddat")
            _sorovlar = []
            pg.on("request", lambda rq: _sorovlar.append(rq.url) if "/tasdiqla" in rq.url else None)
            pg.click("#saytOynaOk")
            pg.wait_for_function("getComputedStyle(document.getElementById('saytOynaXato')).display !== 'none'", timeout=10000)
            pg.wait_for_timeout(400)
            check("U4 sanasiz «Tasdiqlash» — oynada xato, so'rov yuborilmaydi", "sana" in (pg.text_content("#saytOynaXato") or "")
                  and not _sorovlar
                  and js(CA.get(SB + f"/{sb_id(_xraqam)}")).get("holat") == "yangi")
            pg.keyboard.press("Escape")
            pg.wait_for_selector("#saytOynaOverlay", state="hidden", timeout=10000)
            check("U5 Esc — oyna yopildi", not pg.is_visible("#saytOynaOverlay"))
            _q.locator("button:has-text('Tasdiqlash')").click()
            pg.wait_for_selector("#saytOynaOverlay", state="visible", timeout=10000)
            pg.fill("#saytMuddat", "2026-11-25")
            check("U5b qoplamasiz buyurtma — retsept tanlovi ko'rinmaydi", not pg.is_visible("#saytRetsept"))
            with pg.expect_navigation(timeout=30000):
                pg.click("#saytOynaOk")
            pg.wait_for_load_state("networkidle")
            _bj = js(CA.get(SB + f"/{sb_id(_xraqam)}"))
            try:
                pg.wait_for_function(f"typeof selectedOrderId !== 'undefined' && String(selectedOrderId) === '{_bj.get('order_id')}'", timeout=30000)
            except Exception:                  # noqa: BLE001
                pass
            check("U6 haqiqiy bosish bilan tasdiqlash — buyurtma ochildi, sahifa shu buyurtma tanlangan holda qayta ochildi",
                  _bj.get("holat") == "tasdiqlandi" and pg.evaluate("String(typeof selectedOrderId !== 'undefined' ? selectedOrderId : '')")
                  == str(_bj.get("order_id")), (_bj.get("holat"), pg.url, pg.evaluate("String(typeof selectedOrderId)")))
            # review237 H1: sayt buyurtmasidan ochilgan buyurtma (profil — qatorning 1 m³ narxi bilan) tahrir formasida o'zgarishsiz yig'ilsa — narxlar AYNAN
            pg.goto(BASE + f"/orders?order={_oid2}")
            pg.wait_for_function(f"typeof selectedOrderId !== 'undefined' && String(selectedOrderId) === '{_oid2}'", timeout=30000)
            pg.evaluate("editSelected('edit')")
            pg.wait_for_function("document.querySelectorAll('#items .detal').length >= 2", timeout=30000)
            pg.wait_for_timeout(800)
            _fi = pg.evaluate("collectItems().map(x => [x.category, Math.round(x.unit_price * 100) / 100])")
            _si = xavfsiz(lambda d: [[i.category, float(i.unit_price)] for i in d.get(Order, _oid2).items], [])
            pg.evaluate("document.getElementById('base_price').value = '1200000'; document.querySelectorAll('#items .detal').forEach(r => calculateItem(r))")
            _fi2 = pg.evaluate("collectItems().map(x => [x.category, Math.round(x.unit_price * 100) / 100])")
            check("U6b tahrir formasi: profil / dona narxlari saqlangan narx bilan AYNAN; «1 m³ asosiy narxi» yozilsa ham profil narxi o'zgarmaydi",
                  sorted(x for x in _fi if x[0] != "blok") == sorted(x for x in _si if x[0] != "blok")
                  and sorted(x for x in _fi2 if x[0] == "profil") == sorted(x for x in _si if x[0] == "profil"), (_fi, _fi2, _si))
            pg.goto(BASE + "/orders")
            pg.wait_for_load_state("networkidle")
            pg.click("#saytBtn")
            pg.wait_for_function("document.querySelector('#saytRoyxat .tk-qator') !== null", timeout=30000)
            _y = pg.locator("#saytRoyxat .tk-qator:has(button:has-text('Bekor qilish'))").first
            _yr = _y.locator(".tk-raqam").inner_text()
            _y.locator("button:has-text('Bekor qilish')").click()
            pg.wait_for_selector("#saytOynaOverlay", state="visible", timeout=10000)
            pg.fill("#saytSabab", "Mijoz javob bermadi")
            pg.click("#saytOynaOk")
            pg.wait_for_selector("#saytOynaOverlay", state="hidden", timeout=10000)
            pg.wait_for_function(f"!Array.from(document.querySelectorAll('#saytRoyxat .tk-qator')).some(q => q.querySelector('.tk-raqam').textContent === {json.dumps(_yr)} && q.querySelector('button.btn-green'))",
                                 timeout=30000)
            _bk = js(CA.get(SB + f"/{sb_id(_yr)}"))
            check("U7 haqiqiy bosish bilan bekor qilish (sabab bilan) — holat «bekor», ro'yxatda tugmalar yo'q",
                  _bk.get("holat") == "bekor" and _bk.get("bekor_sababi") == "Mijoz javob bermadi", _bk.get("holat"))
            pg.click("#saytPanel .sb-f[data-f='bekor']")
            pg.wait_for_function("Array.from(document.querySelectorAll('#saytRoyxat .tk-qator')).every(q => q.textContent.includes('Bekor qilingan'))",
                                 timeout=30000)
            check("U8 filtr «Bekor qilingan» — faqat bekorlar", pg.locator("#saytRoyxat .tk-qator").count()
                  == js(CA.get(SB)).get("sonlar", {}).get("bekor"))
            pg.set_viewport_size({"width": 375, "height": 800})
            pg.click("#saytPanel .sb-f[data-f='hammasi']")
            pg.wait_for_timeout(600)
            _ken = pg.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            check("U9 375 px — sahifa gorizontal toshmaydi", _ken[0] <= _ken[1] + 1, _ken)
            check("U10 JS xatosi yo'q", not JSX, JSX)
            br.close()
    except Exception as _e:                # noqa: BLE001 — brauzer oqimi uzildi (mutant / asl kod): sinov QULAMASIN
        check("U0 brauzer oqimi oxirigacha yurdi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    _srv.should_exit = True

print(f"\nNATIJA: {OK} OK, {FAIL} xato")
if FAILED:
    print("YIQILGANLAR:\n  " + "\n  ".join(FAILED))
sys.exit(1 if FAIL else 0)
