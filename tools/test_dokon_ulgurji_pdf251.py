#!/usr/bin/env python3
"""
test_dokon_ulgurji_pdf251.py — kech184 (zip 251: do'kon — magazin narxlar ro'yxati PDF i va ulgurji tanlov PDF i; ERP tomoni).

NIMA UCHUN KERAK
  Egasi QARORLARI («Onlayn do'kon rejasi» 30.10): «narxlar ro'yxati PDF shu bo'limdan olinadi»; «Magazin butun ulgurji katalogni o'z
  narxlari bilan PDF qilib oladi — vitrina va mijozlari uchun». Ulgurji narx FAQAT tasdiqlangan magazinga (zip 250 qoidasi — PDF da ham).
  Narxlar ro'yxati — ulgurji katalog API sidagi narxlarning O'ZI; tanlov PDF i — buyurtma hisobining O'ZI (metr qatori donada), hech narsa
  yozilmaydi. Asl kodda (zip 250) bu yo'llar YO'Q — test yiqiladi (qulamaydi).
BO'LIMLAR
  S — tayyorgarlik (zip 250 testi bilan bir xil katalog). A — kirish. N — narxlar ro'yxati PDF matni. V — tanlov (savat) PDF i.
  C — chegara. Z — ikkinchi korxona, yo'llar, ko'p sahifa.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
ISHLATISH: python3 tools/test_dokon_ulgurji_pdf251.py
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
PG_BAZA = f"ulgurjipdf251_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t251_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't251.db')}"
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
from models import DokonBuyurtma, DokonBuyurtmaQator      # noqa: E402
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
section("A. Kirish: narxlar ro'yxati va tanlov PDF ini kim oladi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from pypdf import PdfReader                        # noqa: E402
NP = "/api/dokon/v1/ulgurji/narxlar/pdf"
VP = "/api/dokon/v1/ulgurji/savat/pdf"
HAS251 = hasattr(crud, "ulgurji_narxlar_pdf_malumoti")


def pdf_chek_tozala(hisob=True):
    chek_tozala()
    _p = getattr(crud, "_DOKON_PDF_CHEKLOV", None)
    if _p is not None:
        _p.tozala()
    _h = getattr(crud, "_ULGURJI_NARXLAR_HISOB_CHEKLOV", None)
    if hisob and _h is not None:
        _h.tozala()
    _u = getattr(crud, "_ULGURJI_PDF_CHEKLOV", None)
    if _u is not None:
        _u.tozala()


def narxlar(sessiya, kalit=None, hisob=True):
    pdf_chek_tozala(hisob)
    h = {"X-Dokon-Kalit": KALIT if kalit is None else kalit}
    if sessiya is not None:
        h["X-Mijoz-Sessiya"] = sessiya
    return NC.get(NP, headers=h)


def savat_pdf(tana, sessiya, kalit=None):
    pdf_chek_tozala()
    h = {"X-Dokon-Kalit": KALIT if kalit is None else kalit, "Content-Type": "application/json"}
    if sessiya is not None:
        h["X-Mijoz-Sessiya"] = sessiya
    return NC.post(VP, content=json.dumps(tana).encode("utf-8"), headers=h)


def matn(r):
    """PDF matni (sahifalar, bo'shliqlar bitta) yoki "" (PDF emas)."""
    try:
        return re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages))
    except Exception:                      # noqa: BLE001
        return ""


def ixcham(t):
    return re.sub(r"\s+", "", t or "")


def sahifalar(r):
    try:
        return len(PdfReader(io.BytesIO(r.content)).pages)
    except Exception:                      # noqa: BLE001
        return 0


def pul(x):
    """PDF dagi summa ko'rinishi (bo'shliqsiz): butun so'mgacha, yarim — yuqoriga (`pdf_service._pul_matni`)."""
    from decimal import ROUND_HALF_UP
    return str(int(D(str(x)).quantize(D("1"), rounding=ROUND_HALF_UP)))


def bor(t, v):
    """PDF matnida summa bormi: «45 001» ko'rinishida (ming ajratgich — bo'shliq), chap / o'ng tomonida raqam yo'q (jadvalda ustunlar
    bo'shliq bilan ajraladi — «60 000 120 000» dan ikkala summa topiladi). `v` — `pul()` natijasi yoki son."""
    s_ = f"{int(str(v)):,}".replace(",", " ")
    return re.search(r"(?<![\d,.])" + re.escape(s_) + r"(?![\d,.])", t or "") is not None


def ispdf(r):
    return r.status_code == 200 and r.headers.get("content-type", "").startswith("application/pdf") and r.content[:5] == b"%PDF-"


a1 = narxlar(S_MAG)
A1M = matn(a1)
check("A1 tasdiqlangan magazin — narxlar ro'yxati PDF (200, application/pdf, no-store, attachment «ulgurji-narxlar-2026-11-03.pdf»)",
      ispdf(a1) and a1.headers.get("cache-control") == "no-store"
      and a1.headers.get("content-disposition") == 'attachment; filename="ulgurji-narxlar-2026-11-03.pdf"',
      (a1.status_code, a1.headers.get("content-type"), a1.headers.get("content-disposition"), a1.text[:200] if a1.status_code != 200 else ""))
_a2 = {n: narxlar(s) for n, s in (("yo'q", None), ("bo'sh", ""), ("soxta", "pds_" + "A" * 43))}
check("A2 sessiyasiz / soxta sessiya — 401 «Kirilmagan» (PDF yo'q)",
      all(r.status_code == 401 and js(r).get("detail") == "Kirilmagan" and not r.content.startswith(b"%PDF") for r in _a2.values()),
      {k: (r.status_code, r.text[:80]) for k, r in _a2.items()})
_a3 = {n: narxlar(s) for n, s in (("usta", S_USTA), ("kutilmoqda", S_KUT), ("rad", S_RAD), ("yangi", S_YANGI))}
check("A3 usta / kutilayotgan / rad etilgan magazin / turi tanlanmagan — 403 BIR XIL «faqat tasdiqlangan magazinlar uchun», PDF yo'q",
      all(r.status_code == 403 and js(r).get("detail") == "Bu bo'lim faqat tasdiqlangan magazinlar uchun" for r in _a3.values())
      and len({r.text for r in _a3.values()}) == 1, {k: (r.status_code, r.text[:80]) for k, r in _a3.items()})
_a4 = narxlar(S_MAG, kalit="pdk_" + "x" * 40)
check("A4 noto'g'ri do'kon kaliti — 401 (`WWW-Authenticate: Bearer`)", _a4.status_code == 401
      and _a4.headers.get("www-authenticate") == "Bearer" and not _a4.content.startswith(b"%PDF"), (_a4.status_code, _a4.text[:120]))
T_V = [{"detal_id": DID["k3"], "qoplamali": False, "miqdor": 3}, {"detal_id": DID["tp"], "qoplamali": True, "miqdor": 1.6},
       {"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "kapitel_baza": True, "soni": 2},
       {"detal_id": DID["d6q"], "qoplamali": True, "miqdor": 4}]
_a5 = {n: savat_pdf({"qatorlar": T_V}, s) for n, s in (("yo'q", None), ("soxta", "pds_" + "B" * 43), ("usta", S_USTA), ("kut", S_KUT))}
check("A5 tanlov PDF — sessiyasiz / soxta — 401, usta / kutilayotgan — 403 (narx yo'q)",
      _a5["yo'q"].status_code == 401 and _a5["soxta"].status_code == 401 and _a5["usta"].status_code == 403 and _a5["kut"].status_code == 403
      and not any(r.content.startswith(b"%PDF") for r in _a5.values()), {k: (r.status_code, r.text[:80]) for k, r in _a5.items()})
_ub = next((b.get("id") for b in js(CA.get(API)).get("bolimlar") or [] if b.get("tizim_kaliti") == "ulgurji"), None)
_ry = CA.put(API + f"/bolimlar/{_ub}", json={"yoqilgan": False})
_y1, _y2 = narxlar(S_MAG), savat_pdf({"qatorlar": T_V}, S_MAG)
CA.put(API + f"/bolimlar/{_ub}", json={"yoqilgan": True})
_y3 = narxlar(S_MAG)
check("A6 admin «Ulgurji» bo'limini yashirsa — ikkala PDF 404 «Ulgurji bo'lim hozir yopiq»; qayta yoqilsa — 200",
      _ry.status_code == 200 and _y1.status_code == 404 and _y2.status_code == 404 and js(_y1).get("detail") == "Ulgurji bo'lim hozir yopiq"
      and ispdf(_y3), (_ry.status_code, _y1.status_code, _y2.status_code, _y3.status_code))
_y4 = NC.post(NP, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG})
_y5 = NC.get(VP, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG})
check("A7 boshqa usul — 405 (narxlar — faqat GET, tanlov — faqat POST)", _y4.status_code == 405 and _y5.status_code == 405,
      (_y4.status_code, _y5.status_code))


def xom_savat(tana_bayt, sessiya):
    pdf_chek_tozala()
    h = {"X-Dokon-Kalit": KALIT, "Content-Type": "application/json"}
    if sessiya is not None:
        h["X-Mijoz-Sessiya"] = sessiya
    return NC.post(VP, content=tana_bayt, headers=h)


_a8 = {"usta xx": xom_savat(b"xx", S_USTA), "usta []": xom_savat(b"[]", S_USTA), "sessiyasiz xx": xom_savat(b"xx", None),
       "magazin xx": xom_savat(b"xx", S_MAG)}
check("A8 tanlov PDF — kirish TANADAN OLDIN: buzuq tana bilan usta — 403, sessiyasiz — 401; magazin — 400 (review251 L1)",
      _a8["usta xx"].status_code == 403 and _a8["usta []"].status_code == 403 and _a8["sessiyasiz xx"].status_code == 401
      and _a8["magazin xx"].status_code == 400, {k: (r.status_code, r.text[:60]) for k, r in _a8.items()})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("N. Narxlar ro'yxati PDF matni = ulgurji katalog API narxlari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
UK = js(katalog_ulg(S_MAG))
MODS = {m.get("id"): m for m in UK.get("modellar") or []}
DETS = {d.get("id"): d for m in MODS.values() for d in m.get("detallar") or []}
AX = ixcham(A1M)
check("N1 sarlavha «ULGURJI NARXLAR RO'YXATI», korxona, sana, magazin «Qurilish dunyosi (Asaka)», «1 sotish birligi uchun»",
      "ULGURJINARXLARRO'YXATI" in AX and "T250Penodekor" in AX and "03.11.2026" in AX and "Qurilishdunyosi(Asaka)" in AX
      and "1sotishbirligiuchun" in AX, A1M[:600])
_yoq = []
for _d in DETS.values():
    for _k in ("narx", "narx_qoplamali"):
        if _d.get(_k) is not None and not bor(A1M, pul(_d[_k])):
            _yoq.append((_d.get("id"), _k, _d[_k]))
check("N2 API dagi HAR detal narxi (qoplamasiz / qoplamali) PDF da bor (butun so'mgacha: 56 000,01 → «56 000»)",
      HAS251 and len(DETS) >= 15 and not _yoq, (_yoq, len(DETS)))
_komp = [k for m in MODS.values() for k in (m.get("komplekt") or [])]
_kyoq = [(k.get("olcham"), n, k.get(n)) for k in _komp for n in ("qoplamasiz", "qoplamali", "qoplamasiz_kbsiz", "qoplamali_kbsiz")
         if k.get(n) is not None and not bor(A1M, pul(k[n]))]
check("N3 rom komplektlari: har o'lcham narxi (qoplamasiz / qoplamali / kapitel-bazasiz) PDF da, «ROM KOMPLEKTLARI», tarkib — qatorda",
      _komp and not _kyoq and "ROMKOMPLEKTLARI" in AX and "R-15«Klassik»·O'rta" in AX and "kapitelvabazasiz" in AX
      and "romkarnizi1dona,podokonnik1dona,nalichnik2dona,kapitel2dona,baza2dona" in AX and "1komplekt:" not in AX,
      (_kyoq, len(_komp), A1M[-900:]))
_api_son = {pul(v) for d in DETS.values() for v in (d.get("narx"), d.get("narx_qoplamali")) if v is not None} | \
    {pul(k[n]) for k in _komp for n in ("qoplamasiz", "qoplamali", "qoplamasiz_kbsiz", "qoplamali_kbsiz") if k.get(n) is not None}
_chakana = {"39000", "37000", "31000", "25000", "23000", "43000", "41000", "98000", "35000", "95000", "69000", "7000", "9000"}
check("N4 chakana narx, yashirin qator (K-3 22 sm — 69 000), ulgurji narxsiz qator (K-3 30 sm), yashirin model (D-9) — PDF da YO'Q",
      not [x for x in _chakana - _api_son if bor(A1M, x)] and "D-9" not in A1M and "Yashirin" not in A1M and "30sm" not in AX and "22sm" not in AX,
      [x for x in _chakana - _api_son if bor(A1M, x)])
check("N5 birliklar: metrli — «1 dona (2 m)», donali — «1 dona», m² — «1 m²»; detal nomi — ERP nomi («K-3 Tom osti · 15 sm»)",
      "1dona(2m)" in AX and "1m²" in AX and "1dona" in AX and "K-3TomostiR" not in AX and "K-3Tomosti·15sm" in AX
      and "Pilyastr" in AX, A1M[:1500])
check("N6 bo'limlar sarlavhasi (Karnizlar, Termopanel, Dekor elementlar, Ustunlar va pilyastrlar) — tartibda",
      all(x in AX for x in ("Karnizlar", "Termopanel", "Dekorelementlar", "Ustunlarvapilyastrlar")), A1M[:1200])
check("N7 faqat qoplamali narxi bor detal (D-6) — qoplamasiz ustunida «—», qoplamali — 40 000",
      re.search(r"D-6 Konsol · 25 sm 1 dona — 40 000", A1M) is not None, re.findall(r"D-6.{0,60}", A1M))
check("N8 pastki: sana holatiga, «50 % oldindan», «Qo'shimcha chegirma yo'q»; har sahifa pastida «1-sahifa»",
      "03.11.2026holatiga" in AX and "50%oldindan" in AX and "Qo'shimchachegirmayo'q" in AX and "1-sahifa" in AX, A1M[-700:])
check("N9 ichki maydon / tannarx so'zlari yo'q (ulgurji_narx, tannarx, model_id)",
      not any(x in A1M for x in ("ulgurji_narx", "tannarx", "model_id", "detal_id")), A1M[:300])
_ikki = narxlar(S_MAG2)
check("N10 ikkinchi magazin — o'z nomi («Baraka qurilish (Andijon)»), narxlar AYNAN", ispdf(_ikki)
      and "Barakaqurilish(Andijon)" in ixcham(matn(_ikki)) and bor(matn(_ikki), pul(DETS[DID["k3"]]["narx"]))
      and "Qurilishdunyosi" not in ixcham(matn(_ikki)), matn(_ikki)[:300])
import pdf_service                                 # noqa: E402
_bo = xavfsiz(lambda: pdf_service.generate_ulgurji_narxlar_pdf({"company_id": 1, "sana": datetime(2026, 11, 3, 7, 0), "magazin": "Bo'sh",
                                                                 "shahar": None, "bolimlar": [], "komplektlar": [], "pastki": []}, None), b"")


class _R:
    def __init__(self, b):
        self.content = b


check("N11 bo'sh katalog — PDF baribir: «Hozircha ulgurji narxli mahsulot yo'q»", (_bo or b"")[:5] == b"%PDF-"
      and "Hozirchaulgurjinarxlimahsulotyo'q" in ixcham(matn(_R(_bo))), matn(_R(_bo or b""))[:300])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("V. Tanlov (savat) PDF i — buyurtma hisobining O'ZI, hech narsa yozilmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_sb0 = sb_soni()
_q0 = bazadan(lambda d: d.query(DokonBuyurtmaQator).count())
v1 = savat_pdf({"qatorlar": T_V}, S_MAG)
V1M = matn(v1)
VX = ixcham(V1M)
_h = bazadan(lambda d: crud.ulgurji_buyurtma_hisobla(d, 1, T_V)) or {}
check("V1 200 PDF «ulgurji-savat.pdf», sarlavha «ULGURJI SAVAT (HISOB-KITOB)», magazin nomi, «buyurtma hali berilmagan»",
      ispdf(v1) and v1.headers.get("content-disposition") == 'attachment; filename="ulgurji-savat.pdf"'
      and "ULGURJISAVAT(HISOB-KITOB)" in VX and "Qurilishdunyosi" in VX and "buyurtmahaliberilmagan" in VX,
      (v1.status_code, v1.text[:200] if v1.status_code != 200 else V1M[:500]))
check("V2 JAMI = ERP ulgurji hisobi (buyurtma yuborilgandagi summa) AYNAN", _h.get("jami") is not None and bor(V1M, pul(_h["jami"]))
      and "JAMI" in VX, (_h.get("jami"), V1M[-500:]))
_k3 = DETS[DID["k3"]]
check("V3 metrli detal (K-3) — DONADA: «(1 dona = 2 m)», miqdor 3, 1 dona narxi 45 001, summa 135 003",
      "(1dona=2m)" in VX and bor(V1M, 135003) and bor(V1M, pul(_k3["narx"])) and re.search(r"K-3 .{0,40}dona 3 45 001 135 003", V1M), re.findall(r"K-3.{0,90}", V1M))
check("V4 komplekt sarlavhasi (R-15 rom komplekti — 2 komplekt) va «50 % oldindan»", "R-15" in V1M and "komplekt" in V1M.lower()
      and "50%oldindan" in VX, V1M[:1200])
check("V5 hech narsa yozilmaydi (sayt buyurtmasi / qator soni o'zgarmadi)", sb_soni() == _sb0
      and bazadan(lambda d: d.query(DokonBuyurtmaQator).count()) == _q0, (_sb0, sb_soni()))
_v6 = {n: savat_pdf(t, S_MAG) for n, t in (("bo'sh", {"qatorlar": []}), ("kalit", {"qatorlar": T_V, "x": 1}),
                                             ("narxsiz", {"qatorlar": [{"detal_id": DID["k3n"], "qoplamali": False, "miqdor": 1}]}),
                                             ("yashirin", {"qatorlar": [{"detal_id": DID["d9"], "qoplamali": False, "miqdor": 1}]}),
                                             ("manfiy", {"qatorlar": [{"detal_id": DID["k3"], "qoplamali": False, "miqdor": -1}]}))}
check("V6 noto'g'ri tanlov (bo'sh, noma'lum kalit, ulgurji narxsiz / yashirin detal, manfiy) — 400, PDF yo'q",
      all(r.status_code == 400 and not r.content.startswith(b"%PDF") for r in _v6.values()), {k: (r.status_code, r.text[:90]) for k, r in _v6.items()})
_ret = NC.post("/api/dokon/v1/savat/pdf", content=json.dumps({"qatorlar": [{"detal_id": DID["d4"], "qoplamali": False, "miqdor": 1}]}).encode(),
               headers={"X-Dokon-Kalit": KALIT, "Content-Type": "application/json"})
_rx = ixcham(matn(_ret))
check("V7 oddiy (chakana) savat PDF i o'zgarmagan: «SAVAT (HISOB-KITOB)», MAGAZIN maydoni yo'q, ulgurji narx yo'q",
      ispdf(_ret) and "SAVAT(HISOB-KITOB)" in _rx and "ULGURJI" not in _rx and "MAGAZIN" not in _rx and bor(matn(_ret), 35000)
      and not bor(matn(_ret), 28000), (_ret.status_code, matn(_ret)[:300]))
_v8 = savat_pdf({"qatorlar": T_V}, S_MAG2)
check("V8 ikkinchi magazin — o'z nomi bilan, jami AYNAN", ispdf(_v8) and "Barakaqurilish" in ixcham(matn(_v8))
      and bor(matn(_v8), pul(_h.get("jami") or 0)), matn(_v8)[:200])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Chegaralar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
pdf_chek_tozala()
_c = [narxlar(S_MAG, hisob=False) for _ in range(7)]
_c2 = narxlar(S_MAG2, hisob=False)
check("C1 narxlar ro'yxati — hisobga daqiqasiga 6: 7-so'rov 429 (`Retry-After`, o'zbekcha matn); boshqa magazin — o'tadi",
      all(ispdf(r) for r in _c[:6]) and _c[6].status_code == 429 and int(_c[6].headers.get("retry-after") or 0) >= 1
      and "Narxlar ro" in js(_c[6]).get("detail", "") and ispdf(_c2), [r.status_code for r in _c] + [_c2.status_code])
pdf_chek_tozala()
_c3 = []
for _ in range(31):
    chek_tozala()
    _c3.append(NC.post(VP, content=json.dumps({"qatorlar": T_V}).encode(), headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG,
                                                                                     "Content-Type": "application/json"}).status_code)
check("C2 tanlov PDF — kalitga PDF chegarasi (daqiqasiga 30): 31-so'rov 429", _c3[:30] == [200] * 30 and _c3[30] == 429, _c3)
pdf_chek_tozala()
_ret_c = NC.post("/api/dokon/v1/savat/pdf", content=json.dumps({"qatorlar": [{"detal_id": DID["d4"], "qoplamali": False, "miqdor": 1}]}).encode(),
                 headers={"X-Dokon-Kalit": KALIT, "Content-Type": "application/json"})
for _ in range(30):
    chek_tozala()
    NC.post(VP, content=json.dumps({"qatorlar": T_V}).encode(), headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG,
                                                                         "Content-Type": "application/json"})
_ret_c2 = NC.post("/api/dokon/v1/savat/pdf", content=json.dumps({"qatorlar": [{"detal_id": DID["d4"], "qoplamali": False, "miqdor": 1}]}).encode(),
                  headers={"X-Dokon-Kalit": KALIT, "Content-Type": "application/json"})
check("C3 ulgurji PDF chegarasi chakana PDF lardan ALOHIDA: 30 ta tanlov PDF idan keyin oddiy savat PDF i — 200",
      ispdf(_ret_c) and ispdf(_ret_c2), (_ret_c.status_code, _ret_c2.status_code))
pdf_chek_tozala()
_c4 = []
for _ in range(40):
    chek_tozala()
    _c4.append(NC.get(NP, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_USTA}).status_code)
for _ in range(40):
    chek_tozala()
    _c4.append(NC.get(NP, headers={"X-Dokon-Kalit": KALIT}).status_code)
chek_tozala()
_c4b = NC.get(NP, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG})
_c4c = NC.post(VP, content=json.dumps({"qatorlar": T_V}).encode(), headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG,
                                                                           "Content-Type": "application/json"})
check("C4 usta (40) va sessiyasiz (40) so'rovlar PDF chegarasini band QILMAYDI — keyin magazin narxlar / tanlov PDF i — 200 (review251 M1)",
      _c4 == [403] * 40 + [401] * 40 and ispdf(_c4b) and ispdf(_c4c), (sorted(set(_c4)), _c4b.status_code, _c4c.status_code))
pdf_chek_tozala()
for _ in range(30):
    chek_tozala()
    NC.post(VP, content=json.dumps({"qatorlar": T_V}).encode(), headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG,
                                                                         "Content-Type": "application/json"})
chek_tozala()
_c5 = NC.get(NP, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_MAG2})
check("C5 narxlar ro'yxati va tanlov PDF i — korxonaga BITTA ulgurji PDF chegarasi: 30 ta tanlov PDF idan keyin narxlar — 429",
      _c5.status_code == 429 and int(_c5.headers.get("retry-after") or 0) >= 1, (_c5.status_code, _c5.text[:120]))
pdf_chek_tozala()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Ikkinchi korxona, yo'llar, ko'p sahifa")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
CBK = mijoz("t250_b")
CP.post("/api/platform/companies/2/dokon", data={"yoqilgan": "1"})
_bkalit = js(CBK.post(API + "/api-kalit", json={})).get("kalit") or ""
_z1, _z2 = narxlar(S_MAG, kalit=_bkalit or "pdk_x"), savat_pdf({"qatorlar": T_V}, S_MAG, kalit=_bkalit or "pdk_x")
check("Z1 boshqa korxona kaliti + bu korxona magazin sessiyasi — ikkala PDF YO'Q (401)", _z1.status_code == 401 and _z2.status_code == 401
      and not _z1.content.startswith(b"%PDF"), (_bkalit[:6], _z1.status_code, _z2.status_code))
check("Z2 do'kon API yo'llari ro'yxatida ikkala yo'l; yo'llar: GET narxlar, POST tanlov",
      NP in getattr(crud, "DOKON_API_YOLLAR", ()) and VP in getattr(crud, "DOKON_API_YOLLAR", ())
      and any(getattr(r, "path", None) == NP and "GET" in getattr(r, "methods", set()) for r in main.app.routes)
      and any(getattr(r, "path", None) == VP and "POST" in getattr(r, "methods", set()) for r in main.app.routes))
MK = model(KAR, "K-90", nom="Ko'p o'lchamli")
_ko = [detal(MK, "asosiy", f"{10 + i} sm", narx=50000 + i * 100, ulgurji_narx=40000 + i * 100, eni_sm=10 + i) for i in range(70)]
_z3 = narxlar(S_MAG)
_z3m = matn(_z3)
_z3s2 = xavfsiz(lambda: PdfReader(io.BytesIO(_z3.content)).pages[1].extract_text() or "", "")
check("Z3 70 qatorli model — ko'p sahifa (≥ 2), 2-sahifada ham jadval sarlavhasi («Mahsulot», «Qoplamasiz»), «2-sahifa», oxirgi narx 46 900",
      all(_ko) and ispdf(_z3) and sahifalar(_z3) >= 2 and "Mahsulot" in _z3s2 and "Qoplamasiz" in _z3s2 and "2-sahifa" in ixcham(_z3m)
      and bor(_z3m, 46900), (sahifalar(_z3), _z3m.count("Qoplamasiz")))
check("Z4 hech qanday PDF so'rovi bazaga sayt buyurtmasi yozmadi", sb_soni() == _sb0, (_sb0, sb_soni()))
if os.environ.get("PDF_YOZ"):                     # ko'zdan kechirish uchun (jonli sinovdan oldin): PDF fayllar shu papkaga
    for _n, _r in (("narxlar", a1), ("savat", v1), ("kop_sahifa", _z3)):
        with open(os.path.join(os.environ["PDF_YOZ"], f"{_n}251.pdf"), "wb") as _f:
            _f.write(_r.content)

if PG_URL:
    try:
        import database as _dbm251
        _dbm251.engine.dispose()
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
