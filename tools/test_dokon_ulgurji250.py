#!/usr/bin/env python3
"""
test_dokon_ulgurji250.py — kech184 (zip 250: do'kon — ulgurji bo'lim: katalog va magazin buyurtmasi; ERP tomoni).

NIMA UCHUN KERAK
  Egasi QARORLARI («Onlayn do'kon rejasi» 30.10, «Ulgurji bo'lim»): ulgurji narx FAQAT egasi tasdiqlagan magazinga (boshqa hech kimga
  yuborilmaydi), narx 1 dona uchun (metrli detal — 1 dona = 2 m, ERP ga metr bo'lib tushadi), qo'shimcha chegirma yo'q, rom komplekti
  ulgurjida ham (kapitel / bazasiz ham), magazin buyurtmasida ism / telefon — hisobdan, manzil — bir marta, «takrorlash»; ulgurjiga keshbek
  yo'q. Asl kodda (zip 249) ulgurji yo'llari YO'Q — test yiqiladi (qulamaydi).
BO'LIMLAR
  S — tayyorgarlik. A — kirish (kim ko'radi). K — ulgurji katalog. H — narx hisobi. B — buyurtma yozish. U — ERP «Saytdan» va tasdiq.
  T — kabinet tarixi va PDF. O — oxirgi manzil / takrorlash. Z — zaxira, eski baza, ikkinchi korxona, yo'llar.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
ISHLATISH: python3 tools/test_dokon_ulgurji250.py
"""
import os
import io
import re
import sys
import json
import tempfile
import contextlib
from datetime import datetime

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"ulgurji250_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t250_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't250.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "DOKON_BOT_TOKEN", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Master          # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

KIRISH_MAX = getattr(crud, "DOKON_KIRISH_DAQIQA_MAX", 60)
YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
DokonMijoz = getattr(models, "DokonMijoz", None)
DokonKirish = getattr(models, "DokonKirish", None)
DokonSessiya = getattr(models, "DokonSessiya", None)


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


def xavfsiz(fn, std=None):
    try:
        return fn()
    except Exception:                      # noqa: BLE001
        return std


class _SoxtaVaqt:
    t = datetime(2026, 11, 3, 7, 0)          # Toshkent 12:00

    @classmethod
    def utcnow(cls):
        return cls.t


if getattr(crud, "_dt233", None) is not None:
    crud._dt233 = _SoxtaVaqt
TG = []
main._send_telegram = lambda *a, **k: TG.append(" ".join(str(x) for x in a)) or True

# Telegram — soxta (tarmoq yo'q): getMe / getWebhookInfo / setWebhook va bot xabarlari yoziladi
BOT_TOKEN = "123456789:AAHsinov250_" + "q" * 24
TGAPI = {"getMe": {"username": "penodecor_sinov_bot"}, "getWebhookInfo": {"url": ""}}
TGCHAQ = []
BOT = []


def _soxta_tg_api(token, metod, maydonlar=None, timeout=10):
    TGCHAQ.append((token, metod, maydonlar))
    if metod == "setWebhook":
        TGAPI["getWebhookInfo"] = {"url": (maydonlar or {}).get("url", "")}
        return True
    return TGAPI.get(metod)


main._tg_api = _soxta_tg_api
main._tg_post_message = lambda token, chat_id, text, reply_markup=None: BOT.append((str(chat_id), text, reply_markup, token))

s = SessionLocal()
_c1 = s.get(Company, 1)
_c1.name = "T250 Penodekor"
s.add(Company(id=2, name="T250 Begona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t250_admin", PAROL, UserRole.ADMIN, "T250 Admin", company_id=1)
    auth.create_user(s, "t250_plat", PAROL, UserRole.ADMIN, "T250 Platforma", company_id=1)
    auth.create_user(s, "t250_b", PAROL, UserRole.ADMIN, "T250 B", company_id=2)
    auth.create_user(s, "t250_men", PAROL, UserRole.MANAGER, "T250 Menejer", company_id=1)
s.query(User).filter(User.username == "t250_plat").first().is_platform_admin = True
s.add(Master(company_id=1, name="Bahodir usta", phone="+998 90 111 22 33", kpi_percent=3.0, cashback_percent=0.0, is_active=True))
s.add(Master(company_id=2, name="Begona usta", phone="+998 90 555 66 77", kpi_percent=1.0, cashback_percent=0.0, is_active=True))
s.commit()
MASTER1 = s.query(Master.id).filter(Master.company_id == 1, Master.name == "Bahodir usta").scalar()
MASTER_B = s.query(Master.id).filter(Master.company_id == 2).scalar()
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t250_admin")
CP = mijoz("t250_plat")
CB = mijoz("t250_b")
CM = mijoz("t250_men")
NC = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
KALIT = js(CA.post(API + "/api-kalit", json={})).get("kalit") or ""


def chek_tozala():
    for _n in ("_DOKON_API_CHEKLOV", "_DOKON_KIRISH_CHEKLOV", "_DOKON_HOLAT_CHEKLOV", "_DOKON_MIJOZ_CHEKLOV"):
        _ch = getattr(crud, _n, None)
        if _ch is not None:
            _ch.tozala()


def dok(yol, tana=None, sessiya=None, kalit=None, usul="post"):
    chek_tozala()
    h = {"X-Dokon-Kalit": KALIT if kalit is None else kalit, "Content-Type": "application/json"}
    if sessiya is not None:
        h["X-Mijoz-Sessiya"] = sessiya
    if usul == "get":
        return NC.get(yol, headers=h)
    return NC.post(yol, content=json.dumps(tana if tana is not None else {}).encode("utf-8"), headers=h)


def tg(update, sir=None):
    return NC.post("/telegram/dokon", json=update,
                   headers={"X-Telegram-Bot-Api-Secret-Token": bot_sir(BOT_TOKEN) if sir is None else sir})


def xabar(uid, text=None, contact=None, turi="private", chat_id=None, ism="Azizbek"):
    m = {"message_id": 1, "date": 1, "from": {"id": uid, "is_bot": False, "first_name": ism},
         "chat": {"id": uid if chat_id is None else chat_id, "type": turi}}
    if text is not None:
        m["text"] = text
    if contact is not None:
        m["contact"] = contact
    return {"update_id": uid, "message": m}


def kontakt(uid, tel, egasi=None, ism="Azizbek", fam="Karimov"):
    return {"phone_number": tel, "first_name": ism, "last_name": fam, "user_id": uid if egasi is None else egasi}


def oxirgi_bot(chat):
    for x in reversed(BOT):
        if x[0] == str(chat):
            return x
    return None


def bazadan(fn):
    """Bazadan o'qish; xato (asl kodda jadval / model yo'q) — None (test yiqiladi, qulamaydi)."""
    d = SessionLocal()
    try:
        return fn(d)
    except Exception:                      # noqa: BLE001
        d.rollback()
        return None
    finally:
        d.close()


def xesh(x):
    import hashlib
    return hashlib.sha256(str(x).encode("utf-8")).hexdigest()


def bot_sir(token):
    """Kutilgan webhook siri — tokendan HMAC-SHA256 (spetsifikatsiya: alohida o'zgaruvchi shart emas)."""
    import hmac
    return hmac.new(token.encode("utf-8"), b"penodecor-dokon-bot-webhook", "sha256").hexdigest()


def kirib_ol(uid, tel, ism="Azizbek"):
    """To'liq oqim: kirish → /start → kontakt → holat. Natija (sessiya, holat javobi)."""
    k = js(dok("/api/dokon/v1/kirish", {}))
    tg(xabar(uid, text=f"/start k_{k.get('kod')}", ism=ism))
    tg(xabar(uid, contact=kontakt(uid, tel, ism=ism), ism=ism))
    h = js(dok("/api/dokon/v1/kirish/holat", {"kod": k.get("kod"), "sir": k.get("sir")}))
    return h.get("sessiya"), h


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Tayyorgarlik: bot, hisoblar, katalog")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
os.environ["DOKON_BOT_TOKEN"] = BOT_TOKEN
from decimal import Decimal as D                           # noqa: E402
from models import DokonBuyurtma, DokonBuyurtmaQator, Order, OrderItem      # noqa: E402
HAS = hasattr(crud, "dokon_api_ulgurji")
UL = "/api/dokon/v1/ulgurji"
UB = "/api/dokon/v1/ulgurji/buyurtmalar"
BY = "/api/dokon/v1/buyurtmalar"
SB = "/api/sayt-buyurtmalari"
MB = "/api/dokon/v1/mijoz/buyurtmalar"
_kn = [0]


def yangi_kalit():
    _kn[0] += 1
    return f"ulg-{_kn[0]:06d}-t250"


def katalog_ulg(sessiya, kalit=None):
    chek_tozala()
    h = {"X-Dokon-Kalit": KALIT if kalit is None else kalit}
    if sessiya is not None:
        h["X-Mijoz-Sessiya"] = sessiya
    return NC.get(UL, headers=h)


def ulg_buyurtma(tana, sessiya, kalit=None, amal=None, yol=UB):
    crud._DOKON_BUYURTMA_CHEKLOV.tozala()
    chek_tozala()
    h = {"X-Dokon-Kalit": KALIT if kalit is None else kalit, "X-Amal-Kaliti": amal or yangi_kalit(), "Content-Type": "application/json"}
    if sessiya is not None:
        h["X-Mijoz-Sessiya"] = sessiya
    return NC.post(yol, content=json.dumps(tana).encode("utf-8"), headers=h)


def sb(raqam):
    return bazadan(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == raqam).first())


def ulg_of(raqam):
    return getattr(sb(raqam), "sb_ulgurji", "YO'Q")


def qatorlar_of(raqam):
    return bazadan(lambda d: [(q.sbq_tur, q.sbq_detal_turi, q.sbq_birlik, float(q.miqdor), D(str(q.narx)), D(str(q.summa)), q.sbq_guruh_nomi,
                               q.komplekt_soni, q.qoplamali)
                              for q in d.query(DokonBuyurtmaQator).join(DokonBuyurtma, DokonBuyurtma.id == DokonBuyurtmaQator.buyurtma_id)
                              .filter(DokonBuyurtma.sb_raqam == raqam, DokonBuyurtma.company_id == 1)
                              .order_by(DokonBuyurtmaQator.tartib).all()])


def sb_soni():
    return bazadan(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == 1).count())


def mijoz_admin(mid, tana, amal="tasdiqla"):
    return CA.post(API + f"/mijozlar/{mid}/{amal}", json=tana)


def model(bolim, kod, **kw):
    return js(CA.post(API + "/modellar", json=dict({"bolim_id": bolim, "kod": kod}, **kw))).get("id")


def detal(mid, turi, olcham, **kw):
    return js(CA.post(API + "/detallar", json=dict({"model_id": mid, "turi": turi, "olcham": olcham}, **kw))).get("id")


K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}
KOMP, KAR, TERMO, DEK, USTUN = (BOL.get("Rom va eshik dekorlari"), BOL.get("Karnizlar"), BOL.get("Termopanel"), BOL.get("Dekor elementlar"),
                                BOL.get("Ustunlar va pilyastrlar"))
ORTA = "O'rta"
# rom R-15 (kapitel / baza bilan): O'rta — hamma ulgurji narx; qoplamali — avto (× 2, 1 000 ga), nalichnik qoplamalisi alohida yozilgan
ULG = {"karniz": 30000, "podokonnik": 28000, "nalichnik": 22000, "kapitel": 16000, "baza": 14000}
M1 = model(KOMP, "R-15", nom="Klassik", kapitel_baza_bor=True)
DID = {}
for _t, _n in ULG.items():
    DID[_t] = detal(M1, _t, ORTA, narx=_n + 9000, ulgurji_narx=_n, eni_sm=15 if _t in ("karniz", "podokonnik") else 12,
                    qalinligi_sm=8 if _t in ("karniz", "podokonnik", "nalichnik") else None,
                    **({"ulgurji_qoplamali": 47500} if _t == "nalichnik" else {}))
# Katta — nalichnikning ulgurji narxi YO'Q (komplekt ulgurjida chiqmaydi; qolgan detallari alohida chiqadi)
for _t, _n in ULG.items():
    DID["k_" + _t] = detal(M1, _t, "Katta", narx=_n + 13000, **({} if _t == "nalichnik" else {"ulgurji_narx": _n + 4000}))
M2 = model(KAR, "K-3", nom="Tom osti")
DID["k3"] = detal(M2, "asosiy", "15 sm", narx=60000, ulgurji_narx=45001, eni_sm=15, qalinligi_sm=10)    # toq tiyin yo'q, toq so'm
DID["k3t"] = detal(M2, "asosiy", "18 sm", narx=70000, ulgurji_narx=56000.01, eni_sm=18, qalinligi_sm=10)  # toq tiyin — 1 m narxi yarim tiyin
DID["k3y"] = detal(M2, "asosiy", "22 sm", narx=80000, ulgurji_narx=69000, yoqilgan=False)               # saytda yashirin qator
DID["k3n"] = detal(M2, "asosiy", "30 sm", narx=98000)                                                  # ulgurji narxi yo'q
MT = model(TERMO, "TP-1", nom="Termopanel")
DID["tp"] = detal(MT, "asosiy", "3 sm", narx=70000, ulgurji_narx=60000, eni_sm=40, qalinligi_sm=3)
MD = model(DEK, "D-4", nom="Kronshteyn")
DID["d4"] = detal(MD, "asosiy", "Standart", narx=35000, ulgurji_narx=28000)
MDQ = model(DEK, "D-6", nom="Konsol")
DID["d6q"] = detal(MDQ, "asosiy", "25 sm", ulgurji_qoplamali=40000)                 # faqat qoplamali ulgurji narxi bor
MY = model(DEK, "D-9", nom="Yashirin", yoqilgan=False)
DID["d9"] = detal(MY, "asosiy", "S", narx=9000, ulgurji_narx=7000)
MP = model(USTUN, "P-3", nom="Pilyastr", kapitel_baza_bor=True)
DID["p3"] = detal(MP, "asosiy", "25×3 sm", narx=80000, ulgurji_narx=60000, eni_sm=25, qalinligi_sm=3)
DID["p3k"] = detal(MP, "kapitel", "25 sm", narx=95000, ulgurji_narx=85000)
_ch = CA.put(API + f"/modellar/{M1}/chegirma", json={"foiz": 20})                    # chakana chegirma — ulgurjiga TEGMAYDI
check("S0 katalog (rom R-15 O'rta / Katta, K-3, TP-1, D-4, D-6, yashirinlar, P-3) va chakana chegirma −20 %",
      all(DID.values()) and _ch.status_code == 200 and KALIT.startswith("pdk_"), (DID, _ch.text[:200]))

S_MAG, _ = kirib_ol(9101, "998901112201", ism="Botir")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "magazin", "ism": "Botir", "magazin": "Qurilish dunyosi", "shahar": "Asaka"}, sessiya=S_MAG)
MJ_MAG = bazadan(lambda d: d.query(DokonMijoz.id).filter(DokonMijoz.mj_tg_id == "9101").scalar())
_rm = mijoz_admin(MJ_MAG, {})
S_MAG2, _ = kirib_ol(9102, "998901112202", ism="Dilshod")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "magazin", "ism": "Dilshod", "magazin": "Baraka qurilish", "shahar": "Andijon"}, sessiya=S_MAG2)
MJ_MAG2 = bazadan(lambda d: d.query(DokonMijoz.id).filter(DokonMijoz.mj_tg_id == "9102").scalar())
_rm2 = mijoz_admin(MJ_MAG2, {})
S_KUT, _ = kirib_ol(9103, "998901112203", ism="Kutuvchi")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "magazin", "ism": "Kutuvchi", "magazin": "Kutilayotgan", "shahar": "Xo'jaobod"}, sessiya=S_KUT)
S_USTA, _ = kirib_ol(9104, "998901112204", ism="Azizbek")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "Azizbek usta"}, sessiya=S_USTA)
MJ_USTA = bazadan(lambda d: d.query(DokonMijoz.id).filter(DokonMijoz.mj_tg_id == "9104").scalar())
_ru = mijoz_admin(MJ_USTA, {"kpi": 3, "master_id": MASTER1})
S_RAD, _ = kirib_ol(9105, "998901112205", ism="Rad")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "magazin", "ism": "Rad", "magazin": "Rad etilgan", "shahar": "Shahrixon"}, sessiya=S_RAD)
MJ_RAD = bazadan(lambda d: d.query(DokonMijoz.id).filter(DokonMijoz.mj_tg_id == "9105").scalar())
_rr = mijoz_admin(MJ_RAD, {"sabab": "sinov"}, amal="rad")
_s_rad_eski = S_RAD
S_RAD, _ = kirib_ol(9105, "998901112205", ism="Rad")        # rad etilganda eski sessiya bekor bo'ladi (mj_avlod) — qayta kiradi
S_YANGI, _ = kirib_ol(9106, "998901112206", ism="Yangi")            # kirdi, ro'yxat so'rovi yubormagan
check("S1 hisoblar: 2 ta tasdiqlangan magazin, kutilayotgan magazin, tasdiqlangan usta, rad etilgan magazin, yangi",
      all((S_MAG, S_MAG2, S_KUT, S_USTA, S_RAD, S_YANGI)) and _rm.status_code == 200 and _rm2.status_code == 200 and _ru.status_code == 200
      and _rr.status_code == 200, (_rm.status_code, _rm2.status_code, _ru.status_code, _rr.status_code, _rr.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Kirish: ulgurji narxni kim ko'radi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
a_ok = katalog_ulg(S_MAG)
UK = js(a_ok)
check("A1 tasdiqlangan magazin — 200, no-store, magazin nomi", a_ok.status_code == 200 and a_ok.headers.get("cache-control") == "no-store"
      and (UK.get("magazin") or {}).get("nom") == "Qurilish dunyosi", (a_ok.status_code, a_ok.headers.get("cache-control"), a_ok.text[:300]))
_a = {n: katalog_ulg(s) for n, s in (("yo'q", None), ("bo'sh", ""), ("soxta", "pds_" + "A" * 43), ("noto'g'ri", "x y"))}
check("A2 sessiyasiz / soxta sessiya — 401 «Kirilmagan», no-store, narx yo'q",
      all(r.status_code == 401 and js(r).get("detail") == "Kirilmagan" and r.headers.get("cache-control") == "no-store" and "30000" not in r.text
          for r in _a.values()), {k: (r.status_code, r.text[:80]) for k, r in _a.items()})
_b = {n: katalog_ulg(s) for n, s in (("usta", S_USTA), ("kutilmoqda", S_KUT), ("rad", S_RAD), ("yangi", S_YANGI))}
_b_eski = katalog_ulg(_s_rad_eski)
check("A3 usta / tasdiq kutayotgan / rad etilgan magazin (qayta kirgan) / turi tanlanmagan — 403, BIR XIL matn, narx yo'q; rad etilgandagi "
      "eski sessiya — 401", all(r.status_code == 403 and js(r).get("detail") == "Bu bo'lim faqat tasdiqlangan magazinlar uchun" and "30000" not in r.text
                                and r.headers.get("cache-control") == "no-store" for r in _b.values())
      and len({r.text for r in _b.values()}) == 1 and _b_eski.status_code == 401, ({k: (r.status_code, r.text[:80]) for k, r in _b.items()},
                                                                                 _b_eski.status_code))
_kat = NC.get("/api/dokon/v1/katalog", headers={"X-Dokon-Kalit": KALIT})
_katm = next((m for m in js(_kat).get("modellar") or [] if m.get("id") == M1), {})
_sonlar = set(re.findall(r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])", _kat.text))
check("A4 oddiy katalog API — ulgurji narx / ulgurji komplekt YO'Q (o'zgarmagan)", _kat.status_code == 200 and "ulgurji_" not in _kat.text
      and not ({"45001", "45001.0", "56000.01", "47500.0"} & _sonlar)
      and all("ulgurji_rom" not in x for x in (_katm.get("komplekt") or [])), sorted(_sonlar)[:80])
_s = katalog_ulg(S_MAG, kalit="pdk_" + "x" * 40)
check("A5 noto'g'ri do'kon kaliti — 401 (kalit xatosi, `WWW-Authenticate`), narx yo'q", _s.status_code == 401 and "30000" not in _s.text
      and _s.headers.get("www-authenticate") == "Bearer", (_s.status_code, _s.text[:120]))
_hd = NC.head(UL, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG})
_pt = NC.post(UL, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG})
check("A6 boshqa usullar (POST katalog yo'liga) — 405", _pt.status_code == 405 and "30000" not in _pt.text, (_hd.status_code, _pt.status_code))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Ulgurji katalog")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MODS = {m.get("id"): m for m in UK.get("modellar") or []}
DETS = {d.get("id"): d for m in MODS.values() for d in m.get("detallar") or []}
check("K1 faqat ulgurji narxi bor, saytda ko'rinadigan qatorlar (yashirin qator / model, ulgurji narxsiz qator — yo'q)",
      HAS and DID["k3"] in DETS and DID["k3t"] in DETS and DID["tp"] in DETS and DID["d4"] in DETS and DID["d6q"] in DETS
      and DID["p3"] in DETS and DID["p3k"] in DETS and DID["karniz"] in DETS and DID["k_karniz"] in DETS
      and DID["k3y"] not in DETS and DID["k3n"] not in DETS and DID["d9"] not in DETS and DID["k_nalichnik"] not in DETS and MY not in MODS,
      sorted(DETS))
_d = DETS.get(DID["k3"]) or {}
check("K2 metrli detal: sotish «dona2m», narx — 1 dona (= kiritilgan ulgurji narx), qoplamali — avto (× 2, 1 000 ga yaxlit)",
      _d.get("sotish") == "dona2m" and _d.get("narx") == 45001.0 and _d.get("narx_qoplamali") == 90000.0 and UK.get("dona_metr") == 2, _d)
_t = DETS.get(DID["tp"]) or {}
_k = DETS.get(DID["d4"]) or {}
_q = DETS.get(DID["d6q"]) or {}
check("K3 termopanel — «m2» (1 m² narxi), dekor — «dona»; faqat qoplamali narxi bor detal — qoplamasiz narx null",
      _t.get("sotish") == "m2" and _t.get("narx") == 60000.0 and _k.get("sotish") == "dona" and _k.get("narx") == 28000.0
      and _q.get("narx") is None and _q.get("narx_qoplamali") == 40000.0, (_t, _k, _q))
_ruxsat_d = {"id", "model_id", "turi", "turi_nomi", "olcham", "eni_sm", "qalinligi_sm", "birlik", "sotish", "narx", "narx_qoplamali"}
_ruxsat_m = {"id", "bolim_id", "kod", "nom", "qolip", "kapitel_baza_bor", "tartib", "rasmlar", "detallar", "komplekt"}
check("K4 javob kalitlari qat'iy (tannarx, chakana narx, chegirma, updated_by, tm kaliti — YO'Q)",
      all(set(d) == _ruxsat_d for d in DETS.values()) and all(set(m) == _ruxsat_m for m in MODS.values())
      and set(UK) == {"versiya", "bugun", "magazin", "bolimlar", "modellar", "komplekt_retsepti", "dona_metr", "manzil", "oxirgi"}
      and "39000" not in a_ok.text and "tannarx" not in a_ok.text and "chegirma" not in a_ok.text and "updated_by" not in a_ok.text,
      (sorted(UK), [sorted(d) for d in list(DETS.values())[:1]]))
_kp = {x.get("olcham"): x for x in (MODS.get(M1) or {}).get("komplekt") or []}
_o = _kp.get(ORTA) or {}
_avto = {t: float(crud.dokon_avto_qoplamali(D(v), D("2"))) for t, v in ULG.items()}
_avto["nalichnik"] = 47500.0
_kut_q = 30000 + 28000 + 2 * 22000 + 2 * 16000 + 2 * 14000
_kut_qq = _avto["karniz"] + _avto["podokonnik"] + 2 * 47500 + 2 * _avto["kapitel"] + 2 * _avto["baza"]
check("K5 rom komplekti O'rta: karniz 1 + podokonnik 1 + nalichnik 2 + kapitel 2 + baza 2 dona; qoplamasiz / qoplamali / kapitel-bazasiz",
      _o.get("qoplamasiz") == _kut_q and _o.get("qoplamali") == _kut_qq
      and _o.get("qoplamasiz_kbsiz") == 30000 + 28000 + 2 * 22000
      and [(x.get("turi"), x.get("dona")) for x in _o.get("detallar") or []] == [("karniz", 1), ("podokonnik", 1), ("nalichnik", 2),
                                                                                  ("kapitel", 2), ("baza", 2)]
      and UK.get("komplekt_retsepti") == {"karniz": 1, "podokonnik": 1, "nalichnik": 2, "kapitel": 2, "baza": 2}, (_o, _kut_q, _kut_qq))
_admin_k = bazadan(lambda d: crud.dokon_komplekt_narxlari(d, 1, M1)) or {}
_ar = {x["olcham"]: x["ulgurji_rom"] for x in _admin_k.get(M1) or []}
check("K6 chakana chegirma (−20 %) ulgurjiga TEGMAYDI; komplekt narxi admin ko'rinishidagi «ulgurji rom» bilan AYNAN",
      _ar.get(ORTA, {}).get("qoplamasiz") == _o.get("qoplamasiz") and _ar.get(ORTA, {}).get("qoplamali") == _o.get("qoplamali")
      and _ar.get(ORTA, {}).get("qoplamasiz_kbsiz") == _o.get("qoplamasiz_kbsiz"), (_ar.get(ORTA), _o))
check("K7 Katta o'lchamda nalichnik ulgurji narxi yo'q — komplekt chiqmaydi (alohida detallari chiqadi)", "Katta" not in _kp
      and DID["k_karniz"] in DETS, list(_kp))
_bn = {b.get("nom") for b in UK.get("bolimlar") or []}
check("K8 bo'limlar — faqat ulgurji mahsuloti bor oddiy bo'limlar (tizim bo'limlari — «Tayyor», «O'z o'lchami», «Ulgurji» — yo'q)",
      {"Rom va eshik dekorlari", "Karnizlar", "Termopanel", "Dekor elementlar", "Ustunlar va pilyastrlar"} <= _bn
      and not ({"Tayyor mahsulotlar", "O'z o'lchamingiz bilan", "Ulgurji"} & _bn), _bn)
check("K9 manzil / oxirgi buyurtma — hali yo'q (null)", UK.get("manzil") is None and UK.get("oxirgi") is None, (UK.get("manzil"), UK.get("oxirgi")))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Narx hisobi (ERP qayta hisoblaydi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def hisob(q):
    return bazadan(lambda d: crud.ulgurji_buyurtma_hisobla(d, 1, q))


def hisob_xato(q):
    d = SessionLocal()
    try:
        crud.ulgurji_buyurtma_hisobla(d, 1, q)
        return None
    except ValueError as e:
        return str(e)
    except Exception as e:                 # noqa: BLE001
        return f"{type(e).__name__}: {e}"
    finally:
        d.close()


_h1 = hisob([{"detal_id": DID["k3"], "qoplamali": False, "miqdor": 50}]) or {}
_x = (_h1.get("qatorlar") or [{}])[0]
check("H1 metrli detal 50 dona → ERP 100 m, 1 m narxi = dona ÷ 2, summa = 50 × 45 001 (AYNAN)",
      _x.get("birlik") == "metr" and _x.get("miqdor") == D("100") and _x.get("narx") == D("22500.50") and _x.get("summa") == D("2250050.00")
      and _h1.get("jami") == D("2250050.00") and _h1.get("chegirmasiz") == _h1.get("jami") and _x.get("chegirma_foiz") is None,
      _x)
check("H1b guruh nomida dona va metr: «… — 50 dona (100 m)»", str(_x.get("guruh_nomi", "")).endswith(" — 50 dona (100 m)"), _x.get("guruh_nomi"))
_h2 = hisob([{"detal_id": DID["k3t"], "qoplamali": False, "miqdor": 3}]) or {}
_x2 = (_h2.get("qatorlar") or [{}])[0]
check("H2 toq tiyinli dona narxi (56 000,01): summa = 3 × 56 000,01 = 168 000,03 (dona bo'yicha, AYNAN); 1 m narxi — 2 xona",
      _x2.get("summa") == D("168000.03") and _x2.get("narx") == D("28000.01") and _h2.get("jami") == D("168000.03"), _x2)
_h3 = hisob([{"detal_id": DID["tp"], "qoplamali": True, "miqdor": 8}, {"detal_id": DID["d4"], "qoplamali": False, "miqdor": 7},
             {"detal_id": DID["d6q"], "qoplamali": True, "miqdor": 3}, {"detal_id": DID["p3k"], "qoplamali": False, "miqdor": 3}]) or {}
_q3 = _h3.get("qatorlar") or [{}, {}, {}, {}]
check("H3 termopanel 8 m² qoplamali (avto 120 000), dekor 7 dona, faqat qoplamali D-6 3 dona, kapitel 3 dona (toq son)",
      [(x.get("birlik"), x.get("miqdor"), x.get("narx"), x.get("summa")) for x in _q3] ==
      [("m2", D("8.00"), D("120000"), D("960000.00")), ("dona", D("7"), D("28000"), D("196000.00")), ("dona", D("3"), D("40000"), D("120000.00")),
       ("dona", D("3"), D("85000"), D("255000.00"))] and _h3.get("jami") == D("1531000.00"),
      [(x.get("birlik"), x.get("miqdor"), x.get("narx"), x.get("summa")) for x in _q3])
_h4 = hisob([{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "kapitel_baza": True, "soni": 10}]) or {}
_q4 = _h4.get("qatorlar") or []
check("H4 rom komplekti O'rta × 10: karniz 20 m, podokonnik 20 m, nalichnik 40 m, kapitel 20, baza 20 dona; jami = 10 × komplekt narxi",
      [(x.get("detal_turi"), x.get("miqdor")) for x in _q4] == [("karniz", D("20")), ("podokonnik", D("20")), ("nalichnik", D("40")),
                                                                ("kapitel", D("20")), ("baza", D("20"))]
      and _h4.get("jami") == D(str(_kut_q * 10)) and all(x.get("tur") == "komplekt_rom" and x.get("komplekt_soni") == 10 for x in _q4)
      and "ulgurji rom komplekti, O'rta, qoplamasiz × 10" in str((_q4 or [{}])[0].get("guruh_nomi")), [(x.get("detal_turi"), x.get("miqdor")) for x in _q4])
_h5 = hisob([{"komplekt": "rom", "model_id": M1, "olcham": "o'rta", "qoplamali": True, "kapitel_baza": False, "soni": 2}]) or {}
check("H5 kapitel va bazasiz, qoplamali × 2 (o'lcham katta-kichik harfsiz): 3 detal, jami = 2 × qoplamali kbsiz",
      len(_h5.get("qatorlar") or []) == 3 and _h5.get("jami") == D(str(2 * (_avto["karniz"] + _avto["podokonnik"] + 2 * 47500)))
      and "kapitel va bazasiz" in str(((_h5.get("qatorlar") or [{}])[0]).get("guruh_nomi")), _h5.get("jami"))
_xatolar = {
    "eshik": hisob_xato([{"komplekt": "eshik", "model_id": M1, "olcham": ORTA, "qoplamali": False, "kapitel_baza": True, "soni": 1}]),
    "katta_kom": hisob_xato([{"komplekt": "rom", "model_id": M1, "olcham": "Katta", "qoplamali": False, "kapitel_baza": True, "soni": 1}]),
    "narxsiz": hisob_xato([{"detal_id": DID["k3n"], "qoplamali": False, "miqdor": 1}]),
    "yashirin": hisob_xato([{"detal_id": DID["k3y"], "qoplamali": False, "miqdor": 1}]),
    "yashirin_m": hisob_xato([{"detal_id": DID["d9"], "qoplamali": False, "miqdor": 1}]),
    "qopsiz_yoq": hisob_xato([{"detal_id": DID["d6q"], "qoplamali": False, "miqdor": 1}]),
    "kasr": hisob_xato([{"detal_id": DID["k3"], "qoplamali": False, "miqdor": 2.5}]),
    "float": hisob_xato([{"detal_id": DID["k3"], "qoplamali": False, "miqdor": 2.0}]),
    "nol": hisob_xato([{"detal_id": DID["d4"], "qoplamali": False, "miqdor": 0}]),
    "katta": hisob_xato([{"detal_id": DID["k3"], "qoplamali": False, "miqdor": 5001}]),
    "bool": hisob_xato([{"detal_id": DID["d4"], "qoplamali": False, "miqdor": True}]),
    "m2_kasr": hisob_xato([{"detal_id": DID["tp"], "qoplamali": False, "miqdor": 0.805}]),
    "bosh": hisob_xato([]),
    "begona_kalit": hisob_xato([{"detal_id": DID["d4"], "qoplamali": False, "miqdor": 1, "narx": 1}]),
    "ombordan": hisob_xato([{"detal_id": DID["d4"], "qoplamali": True, "miqdor": 1, "ombordan": True}]),
    "oz_olcham": hisob_xato([{"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 2}], "qoplamali": False}]),
    "kop": hisob_xato([{"detal_id": DID["d4"], "qoplamali": False, "miqdor": 1}] * 151),
    "nan": hisob_xato([{"detal_id": DID["d4"], "qoplamali": False, "miqdor": float("inf")}]),
}
check("H6 xatolar — 400 matni bilan (qulamaydi): eshik, narxsiz / yashirin, qoplamasiz narxi yo'q, kasr / 0 / katta dona, ombordan, "
      "o'z o'lchami, begona kalit, 151 qator", all(isinstance(v, str) and v and "Error" not in v.split(":")[0] for v in _xatolar.values()),
      _xatolar)
check("H6b xato matnlari: ulgurjida faqat rom; ulgurji narxi kiritilmagan; dona — butun son",
      "faqat rom komplekti" in str(_xatolar["eshik"]) and "ulgurji narxi kiritilmagan" in str(_xatolar["narxsiz"])
      and "butun son" in str(_xatolar["kasr"]) and "5000" in str(_xatolar["katta"]), _xatolar)
check("H7 2 dona = 4 m da 1 000 000 dona emas — eng ko'pi 5 000 dona (10 000 m)", hisob([{"detal_id": DID["k3"], "qoplamali": False,
                                                                                     "miqdor": 5000}]) is not None, "")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Magazin buyurtmasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
Q1 = [{"detal_id": DID["k3"], "qoplamali": False, "miqdor": 50},
      {"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": True, "kapitel_baza": True, "soni": 4},
      {"detal_id": DID["tp"], "qoplamali": True, "miqdor": 4.8}]
T1 = {"viloyat": "andijon", "manzil": "Asaka, Navoiy ko'chasi 12", "izoh": "Ertalab olib keling", "qatorlar": Q1}
_jami1 = D("2250050") + D(str(_kut_qq)) * 4 + D("120000") * D("4.8")
TG.clear()
_n0 = sb_soni()
b1 = ulg_buyurtma(dict(T1, kutilgan_jami=float(_jami1)), S_MAG, amal="ulg-birinchi-t250")
R1 = js(b1).get("raqam")
B1 = sb(R1)
check("B1 tasdiqlangan magazin — 200, raqam, jami (ERP hisobi), «ulgurji»: true, no-store", b1.status_code == 200 and R1
      and js(b1).get("jami") == float(_jami1) and js(b1).get("ulgurji") is True and b1.headers.get("cache-control") == "no-store",
      (b1.status_code, b1.text[:300], float(_jami1)))
check("B2 bazada: ulgurji belgisi, hisobga bog'langan, ism — magazin nomi, telefon — hisobdan, manzil / izoh",
      B1 is not None and B1.sb_ulgurji is True and B1.mijoz_id == MJ_MAG and B1.sb_mijoz == "Qurilish dunyosi" and B1.sb_telefon == "+998901112201"
      and B1.sb_manzil == "Asaka, Navoiy ko'chasi 12" and B1.sb_izoh == "Ertalab olib keling" and B1.sb_holat == "yangi" and B1.sb_band_tugash is None,
      vars(B1) if B1 is not None else None)
_qq = qatorlar_of(R1) or []
check("B3 qatorlar: metr 100 m (narx 1 m), komplekt 4 × 5 detal (4 / 4 / 8 dona = 8 / 8 / 16 m, kapitel / baza — 8 / 8), termopanel 4,8 m²",
      [(x[0], x[1], x[2], x[3]) for x in _qq] == [("detal", "asosiy", "metr", 100.0), ("komplekt_rom", "karniz", "metr", 8.0),
                                                  ("komplekt_rom", "podokonnik", "metr", 8.0), ("komplekt_rom", "nalichnik", "metr", 16.0),
                                                  ("komplekt_rom", "kapitel", "dona", 8.0), ("komplekt_rom", "baza", "dona", 8.0),
                                                  ("detal", "asosiy", "m2", 4.8)]
      and sum(x[5] for x in _qq) == _jami1, _qq)
check("B4 Telegram: «🏪 Magazin (ulgurji)», magazin qatori, 50 % oldindan, dona / metr; ulgurji narx faqat korxona botida",
      TG and "🏪 *Magazin (ulgurji)*" in TG[-1] and "🏪 Magazin: «Qurilish dunyosi», Asaka" in TG[-1] and "50 % oldindan" in TG[-1]
      and "50 dona (100 m)" in TG[-1], TG[-1:])
_b2 = ulg_buyurtma(dict(T1, kutilgan_jami=float(_jami1)), S_MAG, amal="ulg-birinchi-t250")
check("B5 takror (o'sha kalit, o'sha tanlov) — o'sha buyurtma, `X-Takror: 1`, yangi yozuv yo'q",
      _b2.status_code == 200 and js(_b2).get("raqam") == R1 and js(_b2).get("takror") is True and _b2.headers.get("x-takror") == "1"
      and sb_soni() == _n0 + 1, (_b2.status_code, _b2.text[:200]))
_b3 = ulg_buyurtma(dict(T1, kutilgan_jami=float(_jami1)), S_MAG2, amal="ulg-birinchi-t250")
_b4 = ulg_buyurtma(dict(T1, kutilgan_jami=float(_jami1), mijoz="Ali"), None, amal="ulg-birinchi-t250", yol=BY)
_b4b = ulg_buyurtma({"mijoz": "Ali Valiyev", "telefon": "+998901112201", "viloyat": "andijon", "qatorlar": [{"detal_id": DID["d4"],
                    "qoplamali": False, "miqdor": 1}]}, None, amal="ulg-birinchi-t250", yol=BY)
check("B6 o'sha kalit — boshqa magazin yoki oddiy yo'l bilan — 409 (avvalgi ulgurji buyurtma va narxlari BERILMAYDI)",
      _b3.status_code == 409 and _b4.status_code in (400, 409) and _b4b.status_code == 409 and R1 not in _b3.text + _b4.text + _b4b.text
      and "2250050" not in _b3.text + _b4b.text and sb_soni() == _n0 + 1, (_b3.status_code, _b3.text[:150], _b4.status_code, _b4b.status_code))
_c = {
    "usta": ulg_buyurtma(T1, S_USTA), "kutilmoqda": ulg_buyurtma(T1, S_KUT), "rad": ulg_buyurtma(T1, S_RAD), "yangi": ulg_buyurtma(T1, S_YANGI),
}
_c401 = {"yo'q": ulg_buyurtma(T1, None), "soxta": ulg_buyurtma(T1, "pds_" + "Z" * 43)}
check("B7 usta / kutilayotgan / rad / yangi — 403; sessiyasiz / soxta — 401; HECH NARSA yozilmaydi, Telegram yo'q",
      all(r.status_code == 403 and js(r).get("detail") == "Bu bo'lim faqat tasdiqlangan magazinlar uchun" for r in _c.values())
      and all(r.status_code == 401 for r in _c401.values()) and sb_soni() == _n0 + 1 and len(TG) == 1,
      ({k: r.status_code for k, r in _c.items()}, {k: r.status_code for k, r in _c401.items()}, sb_soni() - _n0, len(TG)))
_e = {
    "manzilsiz": ulg_buyurtma({"viloyat": "andijon", "qatorlar": Q1}, S_MAG),
    "manzil_bosh": ulg_buyurtma({"viloyat": "andijon", "manzil": "  ", "qatorlar": Q1}, S_MAG),
    "mijoz_maydoni": ulg_buyurtma(dict(T1, mijoz="Boshqa ism"), S_MAG),
    "viloyatsiz": ulg_buyurtma({"manzil": "Asaka", "qatorlar": Q1}, S_MAG),
    "telefon_xato": ulg_buyurtma(dict(T1, telefon="12345"), S_MAG),
    "kalitsiz": ulg_buyurtma(T1, S_MAG, amal="x"),
}
check("B8 manzil yo'q / bo'sh, «mijoz» maydoni (ism hisobdan), viloyat yo'q, noto'g'ri telefon, amal kaliti noto'g'ri — 400, yozilmaydi",
      all(r.status_code == 400 for r in _e.values()) and sb_soni() == _n0 + 1 and "ko'cha va uyni" in _e["manzilsiz"].text,
      {k: (r.status_code, r.text[:100]) for k, r in _e.items()})
_f = ulg_buyurtma(dict(T1, kutilgan_jami=float(_jami1) - 1), S_MAG)
check("B9 narx o'zgargan (kutilgan_jami farq) — 409 + yangi jami, yozilmaydi", _f.status_code == 409
      and (js(_f).get("detail") or {}).get("narx_ozgardi") is True and (js(_f).get("detail") or {}).get("jami") == float(_jami1)
      and sb_soni() == _n0 + 1, (_f.status_code, _f.text[:200]))
TG.clear()
_g = ulg_buyurtma({"telefon": "+998 93 444 55 66", "viloyat": "fargona", "manzil": "Farg'ona, bozor yonida",
                   "qatorlar": [{"detal_id": DID["d4"], "qoplamali": False, "miqdor": 10}]}, S_MAG)
R2 = js(_g).get("raqam")
B2 = sb(R2)
check("B10 boshqa telefon raqam — buyurtmaga shu raqam yoziladi (hisob telefoni o'zgarmaydi); Farg'ona — yetkazish yarmi",
      _g.status_code == 200 and B2 is not None and B2.sb_telefon == "+998934445566" and js(_g).get("yetkazish_bepul") is False
      and bazadan(lambda d: d.query(DokonMijoz.mj_telefon).filter(DokonMijoz.id == MJ_MAG).scalar()) == "+998901112201", (_g.status_code, _g.text[:200]))
# magazin bloklansa — keyingi buyurtma 401
_rb = mijoz_admin(MJ_MAG2, {}, amal="blokla")
_h = ulg_buyurtma(T1, S_MAG2)
check("B11 magazin bloklandi — sessiya ishlamaydi (401), buyurtma yozilmaydi; katalog ham 401", _rb.status_code == 200 and _h.status_code == 401
      and katalog_ulg(S_MAG2).status_code == 401 and sb_soni() == _n0 + 2, (_rb.status_code, _h.status_code))
# oddiy (chakana) buyurtma — magazin sessiyasi bilan: ulgurji emas
_ch1 = ulg_buyurtma({"mijoz": "Botir", "telefon": "+998 90 999 00 11", "viloyat": "andijon",
                     "qatorlar": [{"detal_id": DID["d4"], "qoplamali": False, "miqdor": 1}]}, S_MAG, yol=BY)
R3 = js(_ch1).get("raqam")
check("B12 magazin oddiy yo'ldan buyurtma bersa — chakana narx (35 000), ulgurji belgisi YO'Q (NULL)", _ch1.status_code == 200
      and js(_ch1).get("jami") == 35000.0 and js(_ch1).get("ulgurji") is False and ulg_of(R3) is None, (_ch1.status_code, _ch1.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. ERP: «🛒 Saytdan» ro'yxati va tasdiq")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ls = js(CA.get(SB))
_ul = {x.get("raqam"): x.get("ulgurji") for x in _ls.get("royxat") or []}
check("U1 ro'yxatda «ulgurji» belgisi: ulgurji — true, oddiy — false", _ul.get(R1) is True and _ul.get(R2) is True and _ul.get(R3) is False, _ul)
_html = CA.get("/orders").text
check("U2 «🛒 Saytdan» sahifasida «🏪 Ulgurji (magazin)» belgisi chiziladi (b.ulgurji)", "b.ulgurji ?" in _html and "🏪 Ulgurji (magazin)" in _html, "")
_sr = SessionLocal()
_ret = models.Recipe(company_id=1, name="Qoplama T250")
_sr.add(_ret)
_sr.commit()
RID = _ret.id
_sr.close()
_rt = CA.post(SB + f"/{getattr(B1, 'id', 0)}/tasdiqla", json={"deadline": "2026-11-20", "recipe_id": RID})
OID = bazadan(lambda d: d.query(DokonBuyurtma.order_id).filter(DokonBuyurtma.id == B1.id).scalar())
_it = bazadan(lambda d: [(i.category, i.length, i.quantity, float(i.total_price or 0), i.kmp_turi) for i in
                         d.query(OrderItem).filter(OrderItem.order_id == OID).order_by(OrderItem.id).all()]) or []
_od = bazadan(lambda d: (d.query(Order.master_id).filter(Order.id == OID).scalar(), d.query(Order.notes).filter(Order.id == OID).scalar(),
                         float(d.query(Order.agreed_amount).filter(Order.id == OID).scalar() or 0))) or (None, "", 0)
check("U3 tasdiq — ERP buyurtmasi: metr qatorlari profil (uzunlik = metr), komplekt belgisi, kelishilgan summa = jami, izohda «Ulgurji narx»",
      _rt.status_code == 200 and OID and _it and _it[0][0] == "profil" and _it[0][1] == 100.0 and abs(_it[0][3] - 2250050.0) < 0.01
      and [x[4] for x in _it[1:6]] == ["komplekt_rom"] * 5 and abs(_od[2] - float(_jami1)) < 0.01 and "Ulgurji narx (magazin)" in str(_od[1]),
      (_rt.status_code, _rt.text[:300], _it, _od))
check("U4 ulgurji buyurtmaga usta (KPI / keshbek) YO'Q", _od[0] is None, _od)


class _B:
    def __init__(self, **kw):
        self.__dict__.update(kw)


_us1 = bazadan(lambda d: crud.sayt_mijoz_ustasi(d, 1, _B(mijoz_id=MJ_USTA, sb_ulgurji=None)))
_us2 = bazadan(lambda d: crud.sayt_mijoz_ustasi(d, 1, _B(mijoz_id=MJ_USTA, sb_ulgurji=True)))
check("U5 qoida: tasdiqlangan usta hisobiga bog'langan buyurtma ulgurji bo'lsa — usta yozilmaydi (oddiy bo'lsa — yoziladi)",
      _us1 == MASTER1 and _us2 is None, (_us1, _us2))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Kabinet: tarix va PDF")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
chek_tozala()
_tr = js(NC.get(MB, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG}))
_tu = {x.get("raqam"): x.get("ulgurji") for x in _tr.get("buyurtmalar") or []}
check("T1 kabinet tarixida «ulgurji» belgisi (ulgurji — true, oddiy — false)", _tu.get(R1) is True and _tu.get(R2) is True and _tu.get(R3) is False, _tu)


def pdf_matn(r):
    try:
        import pypdf
        return "".join((pg.extract_text() or "") for pg in pypdf.PdfReader(io.BytesIO(r.content)).pages).replace(" ", "").replace("\n", "")
    except Exception as e:                 # noqa: BLE001
        return f"XATO {e}"


crud._DOKON_PDF_CHEKLOV.tozala()
chek_tozala()
_p = NC.post(MB + "/pdf", content=json.dumps({"raqam": R2}).encode("utf-8"),
             headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG, "Content-Type": "application/json"})
_pm = pdf_matn(_p)
crud._DOKON_PDF_CHEKLOV.tozala()
chek_tozala()
_p1 = NC.post(MB + "/pdf", content=json.dumps({"raqam": R1}).encode("utf-8"),
              headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG, "Content-Type": "application/json"})
_pm1 = pdf_matn(_p1)
check("T2 ulgurji buyurtma PDF i: sarlavha «ULGURJI BUYURTMA», metrli qatorda «(1 dona = 2 m)», 1 dona narxi va summa (review250 L2)",
      _p.status_code == 200 and "ULGURJIBUYURTMA" in _pm and _p1.status_code == 200 and "(1dona=2m)" in _pm1 and "45001" in _pm1
      and "2250050" in _pm1 and "22500,5" not in _pm1, (_pm[:300], _pm1[:600]))
crud._DOKON_PDF_CHEKLOV.tozala()
chek_tozala()
_p3 = NC.post(MB + "/pdf", content=json.dumps({"raqam": R3}).encode("utf-8"),
              headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG, "Content-Type": "application/json"})
_pm3 = pdf_matn(_p3)
check("T3 oddiy buyurtma PDF i — «BUYURTMA» (ulgurji emas), dona yozuvi yo'q", _p3.status_code == 200 and "ULGURJI" not in _pm3
      and "BUYURTMA" in _pm3 and "1dona=2m" not in _pm3, _pm3[:200])
_jv = bazadan(lambda d: crud.sayt_dokon_javobi(d, crud.sayt_ol(d, 1, B1.id))) or {}
_g0 = ((_jv.get("guruhlar") or [{}])[0].get("detallar") or [{}])[0]
_gk = [x for g in (_jv.get("guruhlar") or [])[1:2] for x in g.get("detallar") or []]
check("T4 do'kon javobida ulgurji metr qatori DONADA: 50 dona × 45 001 = summa; komplekt metr qatorlari ham (review250 L2)",
      _g0.get("birlik") == "dona" and _g0.get("miqdor") == 50.0 and _g0.get("narx") == 45001.0 and _g0.get("summa") == 2250050.0
      and [(x.get("birlik"), x.get("miqdor")) for x in _gk][:3] == [("dona", 4.0), ("dona", 4.0), ("dona", 8.0)]
      and all(abs(x["narx"] * x["miqdor"] - x["summa"]) < 0.005 for x in _gk), (_g0, _gk[:3]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("O. Oxirgi manzil va takrorlash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
UK2 = js(katalog_ulg(S_MAG))
_ox = UK2.get("oxirgi") or {}
check("O1 manzil — shu magazinning oxirgi manzilli buyurtmasidan (keyingisida o'zi chiqadi)",
      UK2.get("manzil") == {"viloyat": "fargona", "manzil": "Farg'ona, bozor yonida"}, UK2.get("manzil"))
check("O2 oxirgi ULGURJI buyurtma (oddiy buyurtma emas) — raqami va so'rov shaklidagi qatorlari", _ox.get("raqam") == R2
      and _ox.get("qatorlar") == [{"detal_id": DID["d4"], "qoplamali": False, "miqdor": 10}], _ox)
_tk = bazadan(lambda d: crud._ulgurji_takror_qatorlari(crud._sayt_qatorlari(d, 1, B1.id))) or []
check("O3 takrorlash qatorlari (B1): dona 50, komplekt (o'lcham, qoplamali, kapitel-baza bilan, soni 4), m² 4,8 — so'rov shaklida",
      _tk == [{"detal_id": DID["k3"], "qoplamali": False, "miqdor": 50},
              {"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": True, "kapitel_baza": True, "soni": 4},
              {"detal_id": DID["tp"], "qoplamali": True, "miqdor": 4.8}], _tk)
_hk = hisob(_tk) or {}
check("O4 takrorlash qatorlari bugungi narx bilan qayta hisoblanadi — o'sha jami", _hk.get("jami") == _jami1, (_hk.get("jami"), _jami1))
_r4 = ulg_buyurtma({"viloyat": "andijon", "manzil": "Asaka", "qatorlar": [{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False,
                                                                          "kapitel_baza": False, "soni": 1}]}, S_MAG)
_tk3 = bazadan(lambda d: crud._ulgurji_takror_qatorlari(crud._sayt_qatorlari(d, 1, sb(js(_r4).get("raqam")).id)))
check("O5 kapitel va bazasiz komplekt — takrorlashda «kapitel_baza»: false", _r4.status_code == 200 and _tk3 ==
      [{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "kapitel_baza": False, "soni": 1}], (_r4.status_code, _tk3))
_ox2 = bazadan(lambda d: crud.dokon_api_ulgurji(d, 1, d.query(DokonMijoz).filter(DokonMijoz.id == MJ_MAG2).first())) or {"oxirgi": R1}
check("O6 boshqa magazin (buyurtmasi yo'q) — oxirgi buyurtma / manzil YO'Q (birinchi magazinniki ko'rinmaydi)",
      HAS and _ox2.get("oxirgi") is None and _ox2.get("manzil") is None and R1 not in json.dumps(_ox2, ensure_ascii=False), str(_ox2)[:200])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Mustaqil tekshiruv (review250) tuzatishlari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
S_M3, _ = kirib_ol(9107, "998901112207", ism="Murod")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "magazin", "ism": "Murod", "magazin": "Murod savdo", "shahar": "Marhamat"}, sessiya=S_M3)
MJ_M3 = bazadan(lambda d: d.query(DokonMijoz.id).filter(DokonMijoz.mj_tg_id == "9107").scalar())
mijoz_admin(MJ_M3, {})
_rw = ulg_buyurtma({"viloyat": "andijon", "manzil": "Marhamat", "qatorlar": [{"detal_id": DID["k3"], "qoplamali": False, "miqdor": 2}]}, S_M3)
RW = js(_rw).get("raqam")
_rc = ulg_buyurtma({"mijoz": "Murod", "telefon": "+998 90 111 22 07", "viloyat": "andijon",
                    "qatorlar": [{"detal_id": DID["d4"], "qoplamali": False, "miqdor": 1}]}, S_M3, yol=BY)
RC = js(_rc).get("raqam")


def turi_ber(mid, turi):
    return bazadan(lambda d: (d.query(DokonMijoz).filter(DokonMijoz.id == mid).update({DokonMijoz.mj_turi: turi}), d.commit(), True)[2])


def tarix_jami(sessiya):
    chek_tozala()
    return {x.get("raqam"): x.get("jami") for x in js(NC.get(MB, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": sessiya})).get("buyurtmalar") or []}


def pdf_kod(sessiya, raqam):
    crud._DOKON_PDF_CHEKLOV.tozala()
    chek_tozala()
    return NC.post(MB + "/pdf", content=json.dumps({"raqam": raqam}).encode("utf-8"),
                   headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": sessiya, "Content-Type": "application/json"})


_j0 = tarix_jami(S_M3)
turi_ber(MJ_M3, "usta")
_j1, _p1x, _pc = tarix_jami(S_M3), pdf_kod(S_M3, RW), pdf_kod(S_M3, RC)
turi_ber(MJ_M3, "magazin")
_j2, _p2x = tarix_jami(S_M3), pdf_kod(S_M3, RW)
check("R1 hisob endi tasdiqlangan magazin emas (usta bo'lib qayta tasdiqlangan) — eski ULGURJI buyurtma narxsiz, PDF i 404; oddiy buyurtmasi "
      "— o'zgarmaydi; magazinga qaytsa — yana ko'rinadi (review250 M1)",
      _rw.status_code == 200 and _rc.status_code == 200 and _j0.get(RW) == 90002.0 and _j1.get(RW) is None and RW in _j1
      and _j1.get(RC) == 35000.0 and _p1x.status_code == 404 and _pc.status_code == 200 and _j2.get(RW) == 90002.0 and _p2x.status_code == 200
      and "90002" not in _p1x.text, (_j0, _j1, _j2, _p1x.status_code, _pc.status_code, _p2x.status_code))
_hq = (hisob([{"detal_id": DID["d6q"], "qoplamali": True, "miqdor": 2}]) or {}).get("qatorlar") or [{}]
check("R2 faqat qoplamali ulgurji narxi bor donali detal — hajm narxi qoplamasiz (40 000 ÷ 2 = 20 000; review250 M2)",
      _hq[0].get("hajm_narxi") == D("20000.00"), _hq[0].get("hajm_narxi"))
M5 = model(KOMP, "R-21", nom="Oddiy", kapitel_baza_bor=True)
for _t, _n in (("karniz", 20000), ("podokonnik", 18000), ("nalichnik", 15000)):
    detal(M5, _t, "Kichik", narx=_n + 5000, ulgurji_narx=_n)
_kp5 = {x.get("olcham"): x for x in (next((m for m in js(katalog_ulg(S_MAG)).get("modellar") or [] if m.get("id") == M5), {}).get("komplekt") or [])}
_k5 = _kp5.get("Kichik") or {}
_r5a = hisob([{"komplekt": "rom", "model_id": M5, "olcham": "Kichik", "qoplamali": False, "kapitel_baza": False, "soni": 2}]) or {}
_r5b = hisob_xato([{"komplekt": "rom", "model_id": M5, "olcham": "Kichik", "qoplamali": False, "kapitel_baza": True, "soni": 2}])
check("R3 kapitel / baza qatori yo'q o'lcham — katalogda kapitel-bazasiz komplekt chiqadi (to'liq narx null), buyurtma — faqat kapitel-bazasiz "
      "(review250 L1)", _k5.get("qoplamasiz") is None and _k5.get("qoplamasiz_kbsiz") == 20000 + 18000 + 2 * 15000
      and [x.get("turi") for x in _k5.get("detallar") or []] == ["karniz", "podokonnik", "nalichnik"]
      and _r5a.get("jami") == D(str(2 * (20000 + 18000 + 2 * 15000))) and "kapitel yo'q" in str(_r5b), (_k5, _r5a.get("jami"), _r5b))
_ub = next((b.get("id") for b in js(CA.get(API)).get("bolimlar") or [] if b.get("tizim_kaliti") == "ulgurji"), None)
_ry = CA.put(API + f"/bolimlar/{_ub}", json={"yoqilgan": False})
_y1, _y2 = katalog_ulg(S_MAG), ulg_buyurtma(T1, S_MAG)
CA.put(API + f"/bolimlar/{_ub}", json={"yoqilgan": True})
_y3 = katalog_ulg(S_MAG)
check("R4 admin «Ulgurji» bo'limini saytda yashirsa — katalog ham, buyurtma ham 404 (narx yo'q); qayta yoqilsa — 200 (review250 L3)",
      _ry.status_code == 200 and _y1.status_code == 404 and _y2.status_code == 404 and "45001" not in _y1.text + _y2.text and _y3.status_code == 200,
      (_ry.status_code, _y1.status_code, _y2.status_code, _y3.status_code))
_sg = '{"viloyat": "andijon", "manzil": "Asaka \\ud800", "qatorlar": [{"detal_id": %d, "qoplamali": false, "miqdor": 1}]}' % DID["d4"]
crud._DOKON_BUYURTMA_CHEKLOV.tozala()
chek_tozala()
_e1 = NC.post(UB, content=_sg.encode("utf-8"), headers={"X-Dokon-Kalit": KALIT, "X-Amal-Kaliti": yangi_kalit(), "X-Mijoz-Sessiya": S_MAG,
                                                        "Content-Type": "application/json"})
_e2 = NC.post(BY, content=_sg.replace('{"viloyat"', '{"mijoz": "Ali", "telefon": "+998901234599", "viloyat"').encode("utf-8"),
              headers={"X-Dokon-Kalit": KALIT, "X-Amal-Kaliti": yangi_kalit(), "Content-Type": "application/json"})
check("R5 juft bo'lmagan surrogat — 400 «buzilgan belgi» (xom Python xatosi emas), ulgurji va oddiy yo'lda (review250 E1)",
      _e1.status_code == 400 and "buzilgan belgi" in _e1.text and "codec" not in _e1.text
      and _e2.status_code == 400 and "buzilgan belgi" in _e2.text and "codec" not in _e2.text, (_e1.text[:150], _e2.text[:150]))

_bk1 = bazadan(lambda d: d.query(DokonBuyurtma.sb_kalit).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == R1).scalar())
_bk3 = bazadan(lambda d: d.query(DokonBuyurtma.sb_kalit).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == R3).scalar())
crud._DOKON_PDF_CHEKLOV.tozala()
chek_tozala()
_k1 = NC.post(BY + "/pdf", content=json.dumps({"raqam": R1, "kalit": _bk1 or "x" * 8}).encode("utf-8"),
              headers={"X-Dokon-Kalit": KALIT, "Content-Type": "application/json"})
_k3 = NC.post(BY + "/pdf", content=json.dumps({"raqam": R3, "kalit": _bk3 or "x" * 8}).encode("utf-8"),
              headers={"X-Dokon-Kalit": KALIT, "Content-Type": "application/json"})
check("R6 kalit bilan (sessiyasiz) PDF — ulgurji buyurtmaga 404 (FAQAT kabinetdan), oddiy buyurtmaga — 200 (review250-dokon U1)",
      _k1.status_code == 404 and _k3.status_code == 200 and _k3.content[:4] == b"%PDF", (_k1.status_code, _k3.status_code))
M6 = model(KOMP, "R-24", nom="Yarim", kapitel_baza_bor=True)
for _t, _n in (("karniz", 21000), ("podokonnik", 19000), ("nalichnik", 16000), ("kapitel", 9000)):
    detal(M6, _t, ORTA, narx=_n + 5000, ulgurji_narx=_n)
_k6 = ({x.get("olcham"): x for x in (next((m for m in js(katalog_ulg(S_MAG)).get("modellar") or [] if m.get("id") == M6), {}).get("komplekt") or [])}
       .get(ORTA) or {})
check("R7 o'lchamda faqat kapitel bor (baza yo'q) — komplekt faqat kapitel-bazasiz: to'liq narx null, detallarda kapitel yo'q (review250-dokon U2)",
      _k6.get("qoplamasiz") is None and _k6.get("qoplamasiz_kbsiz") == 21000 + 19000 + 2 * 16000
      and [x.get("turi") for x in _k6.get("detallar") or []] == ["karniz", "podokonnik", "nalichnik"], _k6)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira, eski baza, ikkinchi korxona, yo'llar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bk = bazadan(lambda d: crud.export_full_backup(d, company_id=1)) or {}
_rows = ((_bk.get("tables") or {}).get("dokon_buyurtmalar")) or []
_mm = {x.get("sb_raqam"): x.get("sb_ulgurji") for x in _rows if isinstance(x, dict)}
check("Z1 zaxirada ulgurji belgisi bor (ulgurji — true, oddiy — null)", _mm.get(R1) is True and _mm.get(R2) is True and R3 in _mm
      and _mm[R3] is None, dict(list(_mm.items())[:6]))
_res = bazadan(lambda d: crud.import_full_backup(d, _bk, company_id=1, replace=True)) or {}
check("Z2 tiklashdan keyin belgi AYNAN", _res.get("success") is True and ulg_of(R1) is True and ulg_of(R3) is None,
      (_res.get("success"), str(_res)[:200]))
CBK = mijoz("t250_b")
CP.post("/api/platform/companies/2/dokon", data={"yoqilgan": "1"})
_bkalit = js(CBK.post(API + "/api-kalit", json={})).get("kalit") or ""
_z3 = katalog_ulg(S_MAG, kalit=_bkalit or "pdk_x")
_z3b = ulg_buyurtma(T1, S_MAG, kalit=_bkalit or "pdk_x")
check("Z3 boshqa korxona kaliti + bu korxona magazin sessiyasi — katalog ham, buyurtma ham YO'Q (401)", _z3.status_code == 401
      and _z3b.status_code == 401 and "45001" not in _z3.text, (_bkalit[:6], _z3.status_code, _z3b.status_code))
check("Z4 do'kon API yo'llari ro'yxatida ulgurji yo'llari bor", HAS and UL in crud.DOKON_API_YOLLAR and UB in crud.DOKON_API_YOLLAR,
      getattr(crud, "DOKON_API_YOLLAR", None))
if not PG_URL:
    import sqlite3
    import database as _dbm250
    _yol = os.environ["DATABASE_URL"].replace("sqlite:///", "")
    _c = sqlite3.connect(_yol)
    try:
        _c.execute("ALTER TABLE dokon_buyurtmalar DROP COLUMN sb_ulgurji")
        _c.commit()
        _yoq = "sb_ulgurji" not in [r[1] for r in _c.execute("PRAGMA table_info(dokon_buyurtmalar)")]
    except Exception as _e:                # noqa: BLE001
        _yoq = f"XATO {_e}"
    _c.close()
    _dbm250.engine.dispose()
    with contextlib.redirect_stdout(io.StringIO()):
        xavfsiz(_dbm250.sync_missing_columns)
    S_MAG, _ = kirib_ol(9101, "998901112201", ism="Botir")      # tiklash (Z2) sessiyalarni o'chiradi — qayta kiradi
    _c = sqlite3.connect(_yol)
    _bor = "sb_ulgurji" in [r[1] for r in _c.execute("PRAGMA table_info(dokon_buyurtmalar)")]
    _c.close()
    _dbm250.engine.dispose()
    check("Z5 eski baza (ustunsiz) — ishga tushishda ustun qo'shiladi (sync_missing_columns), eski qatorlar — NULL",
          _yoq is True and _bor and ulg_of(R1) is None and katalog_ulg(S_MAG).status_code == 200,
          lambda: (_yoq, _bor, ulg_of(R1), katalog_ulg(S_MAG).status_code, katalog_ulg(S_MAG).text[:200]))

if PG_URL:
    try:
        import database as _dbm249
        _dbm249.engine.dispose()
        _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception as _e:                        # noqa: BLE001
        print("PG bazasi o'chirilmadi:", _e)
print(f"\n{'=' * 70}\n{YORLIQ}NATIJA: {OK} ok, {FAIL} fail")
for f in FAILED:
    print("  -", f)
sys.exit(1 if FAIL else 0)
