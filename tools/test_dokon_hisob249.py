#!/usr/bin/env python3
"""
test_dokon_hisob249.py — kech182 (zip 249: do'kon — buyurtma ↔ hisob, kabinet tarixi va PDF, bloklangan kirish holati; do'kon 2-bosqich,
ERP tomoni 2-qism).

NIMA UCHUN KERAK
  Egasi QARORLARI («Onlayn do'kon rejasi» 30.10): ro'yxatdan o'tgan usta va magazin kabinetida o'z buyurtmalari tarixi, holati va PDF i;
  usta bergan buyurtmasi «Tayyor» bo'lganda keshbek (ERP buyurtmasidagi usta — KPI). Asl kodda (zip 248) buyurtma hisobga bog'lanmaydi,
  tarix / PDF yo'llari YO'Q, bloklangan hisob raqam yuborsa sayt «kutilmoqda» da qoladi — test yiqiladi (qulamaydi).
BO'LIMLAR
  S — tayyorgarlik. B — buyurtma ↔ hisob (mehmon, usta, magazin, kutayotgan usta, yaroqsiz sessiya, takror). T — kabinet tarixi. U — ERP
  buyurtmasiga usta va mijozga holat. P — o'z buyurtmasi PDF i. L — bloklangan hisob kirishi. Z — zaxira / ikkinchi korxona / yo'llar.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
ISHLATISH: python3 tools/test_dokon_hisob249.py
"""
import os
import io
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
PG_BAZA = f"hisob249_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t249_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't249.db')}"
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
BOT_TOKEN = "123456789:AAHsinov249_" + "q" * 24
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
_c1.name = "T249 Penodekor"
s.add(Company(id=2, name="T249 Begona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t249_admin", PAROL, UserRole.ADMIN, "T249 Admin", company_id=1)
    auth.create_user(s, "t249_plat", PAROL, UserRole.ADMIN, "T249 Platforma", company_id=1)
    auth.create_user(s, "t249_b", PAROL, UserRole.ADMIN, "T249 B", company_id=2)
    auth.create_user(s, "t249_men", PAROL, UserRole.MANAGER, "T249 Menejer", company_id=1)
s.query(User).filter(User.username == "t249_plat").first().is_platform_admin = True
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


CA = mijoz("t249_admin")
CP = mijoz("t249_plat")
CB = mijoz("t249_b")
CM = mijoz("t249_men")
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
from models import DokonBuyurtma, Order, OrderStatus      # noqa: E402
HAS = hasattr(crud, "dokon_mijoz_buyurtmalari")
BY = "/api/dokon/v1/buyurtmalar"
SB = "/api/sayt-buyurtmalari"
MB = "/api/dokon/v1/mijoz/buyurtmalar"
_kn = [0]


def yangi_kalit():
    _kn[0] += 1
    return f"savat-{_kn[0]:06d}-t249"


_teln = [0]


def buyurtma(qatorlar, sessiya=None, kalit=None, mijoz="Ali Valiyev", telefon=None):
    if telefon is None:                    # telefonga soatiga 5 ta chegarasi — har buyurtma o'z raqami bilan
        _teln[0] += 1
        telefon = "+998 90 123 %02d %02d" % (_teln[0] // 100, _teln[0] % 100)
    crud._DOKON_BUYURTMA_CHEKLOV.tozala()
    chek_tozala()
    h = {"X-Dokon-Kalit": KALIT, "X-Amal-Kaliti": kalit or yangi_kalit(), "Content-Type": "application/json"}
    if sessiya is not None:
        h["X-Mijoz-Sessiya"] = sessiya
    return NC.post(BY, content=json.dumps({"mijoz": mijoz, "telefon": telefon, "viloyat": "andijon", "qatorlar": qatorlar}).encode("utf-8"),
                   headers=h)


def sb(raqam):
    return bazadan(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == raqam).first())


def mid_of(raqam):
    return bazadan(lambda d: getattr(d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == raqam).first(),
                                     "mijoz_id", "YO'Q"))


def tasdiqla(raqam):
    b = sb(raqam)
    r = CA.post(SB + f"/{b.id}/tasdiqla", json={"deadline": "2026-11-20"})
    oid = bazadan(lambda d: d.query(DokonBuyurtma.order_id).filter(DokonBuyurtma.id == b.id).scalar())
    return r, oid


def order_master(oid):
    return bazadan(lambda d: d.query(Order.master_id).filter(Order.id == oid).scalar())


def mijoz_admin(mid, tana):
    return CA.post(API + f"/mijozlar/{mid}/tasdiqla", json=tana)


def tarix(sessiya):
    chek_tozala()
    return NC.get(MB, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": sessiya})


def pdf(sessiya, tana):
    crud._DOKON_PDF_CHEKLOV.tozala()
    chek_tozala()
    h = {"X-Dokon-Kalit": KALIT, "Content-Type": "application/json"}
    if sessiya is not None:
        h["X-Mijoz-Sessiya"] = sessiya
    return NC.post(MB + "/pdf", content=json.dumps(tana).encode("utf-8"), headers=h)


K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}
MOD = js(CA.post(API + "/modellar", json={"bolim_id": BOL.get("Karnizlar"), "kod": "K-49", "nom": "Sinov"})).get("id")
DET = js(CA.post(API + "/detallar", json={"model_id": MOD, "turi": "asosiy", "olcham": "12 sm", "narx": 45000, "eni_sm": 12,
                                            "qalinligi_sm": 8})).get("id")
Q = [{"detal_id": DET, "qoplamali": False, "miqdor": 4}]

# usta (tasdiqlangan, ERP ustasi MASTER1), magazin (tasdiqlangan), usta2 (kutilmoqda), blok (bloklangan)
S_USTA, _ = kirib_ol(9001, "998901112233", ism="Azizbek")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "Azizbek usta"}, sessiya=S_USTA)
MJ_USTA = bazadan(lambda d: d.query(DokonMijoz.id).filter(DokonMijoz.mj_tg_id == "9001").scalar())
_ru = mijoz_admin(MJ_USTA, {"kpi": 3, "master_id": MASTER1})
S_MAG, _ = kirib_ol(9002, "998901112244", ism="Botir")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "magazin", "ism": "Botir", "magazin": "Qurilish dunyosi", "shahar": "Asaka"}, sessiya=S_MAG)
MJ_MAG = bazadan(lambda d: d.query(DokonMijoz.id).filter(DokonMijoz.mj_tg_id == "9002").scalar())
_rm = mijoz_admin(MJ_MAG, {})
S_U2, _ = kirib_ol(9003, "998901112255", ism="Sardor")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "Sardor"}, sessiya=S_U2)
MJ_U2 = bazadan(lambda d: d.query(DokonMijoz.id).filter(DokonMijoz.mj_tg_id == "9003").scalar())
check("S0 tayyorgarlik: kalit, model / detal, uchta hisob (usta tasdiqlangan, magazin tasdiqlangan, usta kutilmoqda)",
      KALIT.startswith("pdk_") and MOD and DET and S_USTA and S_MAG and S_U2 and _ru.status_code == 200 and _rm.status_code == 200
      and bazadan(lambda d: [x.mj_holat for x in d.query(DokonMijoz).order_by(DokonMijoz.id).all()]) == ["tasdiqlangan", "tasdiqlangan", "kutilmoqda"],
      (_ru.status_code, _ru.text[:200], _rm.status_code, MOD, DET))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Buyurtma ↔ hisob")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TG.clear()
r0 = buyurtma(Q)
R0 = js(r0).get("raqam")
check("B1 mehmon buyurtmasi — 200, hisobga bog'lanmagan (mijoz_id NULL), Telegramda usta / magazin qatori YO'Q",
      r0.status_code == 200 and mid_of(R0) is None and TG and "👷" not in TG[-1] and "🏪" not in TG[-1], (r0.status_code, r0.text[:200], mid_of(R0), TG[-1:]))
TG.clear()
r1 = buyurtma(Q, sessiya=S_USTA)
R1 = js(r1).get("raqam")
check("B2 kirgan usta buyurtmasi — hisobga bog'landi, Telegramda «👷 Usta: Azizbek usta»", r1.status_code == 200 and mid_of(R1) == MJ_USTA
      and TG and "👷 Usta: Azizbek usta" in TG[-1], (r1.status_code, mid_of(R1), TG[-1:]))
check("B3 javob shakli mehmon javobi bilan AYNAN (kalitlar ro'yxati), hisob / sessiya ma'lumoti javobda yo'q",
      sorted(js(r0)) == sorted(js(r1)) and S_USTA not in r1.text and "mijoz_id" not in r1.text, (sorted(js(r0)), sorted(js(r1))))
TG.clear()
r2 = buyurtma(Q, sessiya=S_MAG)
R2 = js(r2).get("raqam")
check("B4 magazin buyurtmasi — bog'landi, Telegramda «🏪 Magazin: «Qurilish dunyosi», Asaka»", r2.status_code == 200 and mid_of(R2) == MJ_MAG
      and TG and "🏪 Magazin: «Qurilish dunyosi», Asaka" in TG[-1], (mid_of(R2), TG[-1:]))
TG.clear()
r3 = buyurtma(Q, sessiya=S_U2)
R3 = js(r3).get("raqam")
check("B5 tasdiq kutayotgan usta — bog'landi, Telegramda holati bilan («(tasdiq kutilmoqda)»)", r3.status_code == 200 and mid_of(R3) == MJ_U2
      and TG and "👷 Usta: Sardor (tasdiq kutilmoqda)" in TG[-1], TG[-1:])
_rx = [buyurtma(Q, sessiya=x) for x in ("pds_" + "A" * 43, "noto'g'ri", "pds_" + "B" * 50)]
check("B6 yaroqsiz sessiya bilan buyurtma — RAD ETILMAYDI (200, mehmon kabi), bog'lanmaydi",
      all(x.status_code == 200 and mid_of(js(x).get("raqam")) is None for x in _rx), [(x.status_code, x.text[:100]) for x in _rx])
_k = yangi_kalit()
_a = buyurtma(Q, sessiya=S_USTA, kalit=_k, telefon="+998 90 777 00 01")
_b = buyurtma(Q, sessiya=S_MAG, kalit=_k, telefon="+998 90 777 00 01")
check("B7 takror (o'sha kalit, o'sha savat) — o'sha buyurtma, birinchi hisobda qoladi (ikkinchi sessiya o'zgartirmaydi)",
      js(_a).get("raqam") == js(_b).get("raqam") and js(_b).get("takror") is True and mid_of(js(_a).get("raqam")) == MJ_USTA,
      (js(_a).get("raqam"), js(_b).get("raqam"), mid_of(js(_a).get("raqam"))))
RT = js(_a).get("raqam")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Kabinet: buyurtmalar tarixi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
t = tarix(S_USTA)
T = js(t).get("buyurtmalar") or []
check("T1 usta — FAQAT o'z buyurtmalari (yangisi birinchi), no-store", t.status_code == 200 and [x.get("raqam") for x in T] == [RT, R1]
      and t.headers.get("cache-control") == "no-store", (t.status_code, t.text[:300]))
_x = T[-1] if T else {}
check("T2 yozuv: raqam, sana (Toshkent), jami, mahsulotlar soni, holat «kutilmoqda» — ortiqcha maydon YO'Q",
      set(_x) == ({"raqam", "sana", "jami", "soni", "holat", "holat_nomi"} | ({"ulgurji"} if hasattr(crud, "dokon_api_ulgurji") else set())) and _x.get("sana") == "03.11.2026" and _x.get("jami") == 180000.0
      and _x.get("soni") == 1 and _x.get("holat") == "kutilmoqda" and _x.get("holat_nomi") == "Tasdiqlash kutilmoqda", _x)
check("T3 magazin — o'zinikini ko'radi (usta buyurtmalari YO'Q)", [x.get("raqam") for x in js(tarix(S_MAG)).get("buyurtmalar") or []] == [R2],
      js(tarix(S_MAG)))
_t401 = [tarix(x) for x in ("", "pds_" + "C" * 43)]
check("T4 sessiyasiz / soxta sessiya — 401 «Kirilmagan», no-store", all(x.status_code == 401 and x.headers.get("cache-control") == "no-store"
                                                                        for x in _t401), [(x.status_code, x.text[:80]) for x in _t401])
_rk = NC.get(MB, headers={"X-Mijoz-Sessiya": S_USTA})
check("T5 do'kon kalitisiz — 401 (sessiya yetmaydi)", _rk.status_code == 401, (_rk.status_code, _rk.text[:100]))
_rp = NC.post(MB, headers={"X-Dokon-Kalit": KALIT, "X-Mijoz-Sessiya": S_USTA})
check("T6 POST tarix — 405", _rp.status_code == 405, _rp.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. ERP buyurtmasi: usta (KPI / keshbek) va holat")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r1, O1 = tasdiqla(R1)
check("U1 tasdiqlangan usta buyurtmasi tasdiqlandi — ERP buyurtmasiga uning ERP ustasi yozildi", _r1.status_code == 200 and O1
      and order_master(O1) == MASTER1, (_r1.status_code, _r1.text[:300], O1, order_master(O1)))
_r0, O0 = tasdiqla(R0)
_r2, O2 = tasdiqla(R2)
_r3, O3 = tasdiqla(R3)
check("U2 mehmon / magazin / tasdiq kutayotgan usta — ERP buyurtmasida usta YO'Q", all(x.status_code == 200 for x in (_r0, _r2, _r3))
      and (order_master(O0), order_master(O2), order_master(O3)) == (None, None, None),
      ([x.status_code for x in (_r0, _r2, _r3)], order_master(O0), order_master(O2), order_master(O3)))


def holat(raqam, sessiya):
    return next((x.get("holat") for x in js(tarix(sessiya)).get("buyurtmalar") or [] if x.get("raqam") == raqam), None)


def order_holat(oid, st, ochir=None):
    def _f(d):
        o = d.query(Order).filter(Order.id == oid).first()
        o.status = st
        if ochir is not None:
            o.is_deleted = ochir
        d.commit()
        return True
    return bazadan(_f)


_h0 = holat(R1, S_USTA)                     # tasdiqdan keyingi haqiqiy holat (ERP buyurtmasi qanday ochilsa)
_st0 = bazadan(lambda d: getattr(d.query(Order.status).filter(Order.id == O1).scalar(), "value", None))
order_holat(O1, OrderStatus.NEW)
_h = [holat(R1, S_USTA)]
for _st in (OrderStatus.IN_PROGRESS, OrderStatus.COATING, OrderStatus.READY, OrderStatus.DELIVERED, OrderStatus.CANCELLED):
    order_holat(O1, _st)
    _h.append(holat(R1, S_USTA))
order_holat(O1, OrderStatus.READY, ochir=True)
_h.append(holat(R1, S_USTA))
check("U3 mijozga holat — ERP buyurtmasi bo'yicha: tasdiqlandi → tayyorlanmoqda ×2 → tayyor → yetkazildi → bekor; o'chirilgan — «tasdiqlandi»",
      _h == ["tasdiqlandi", "tayyorlanmoqda", "tayyorlanmoqda", "tayyor", "yetkazildi", "bekor", "tasdiqlandi"]
      and _h0 == {"new": "tasdiqlandi", "draft": "tasdiqlandi", "in_progress": "tayyorlanmoqda"}.get(_st0), (_h, _h0, _st0))
_bk = js(CA.post(SB + f"/{sb(RT).id}/bekor", json={"sabab": "sinov"}))
check("U4 sayt buyurtmasi bekor qilindi — mijozga «Bekor qilindi»", holat(RT, S_USTA) == "bekor"
      and next((x.get("holat_nomi") for x in js(tarix(S_USTA)).get("buyurtmalar") or [] if x.get("raqam") == RT), None) == "Bekor qilindi",
      (_bk, holat(RT, S_USTA)))
# usta faol emas — ERP buyurtmasiga yozilmaydi
bazadan(lambda d: (d.query(Master).filter(Master.id == MASTER1).update({Master.is_active: False}), d.commit()))
r5 = buyurtma(Q, sessiya=S_USTA)
_r5, O5 = tasdiqla(js(r5).get("raqam"))
bazadan(lambda d: (d.query(Master).filter(Master.id == MASTER1).update({Master.is_active: True}), d.commit()))
check("U5 ERP ustasi faol emas — buyurtma tasdiqlanadi, usta yozilmaydi", _r5.status_code == 200 and order_master(O5) is None,
      (_r5.status_code, order_master(O5)))
# hisob keyin bloklangan — bergan buyurtmasi tasdiqlanadi, lekin usta yozilmaydi
r6 = buyurtma(Q, sessiya=S_USTA)
CA.post(API + f"/mijozlar/{MJ_USTA}/blokla", json={})
_r6, O6 = tasdiqla(js(r6).get("raqam"))
check("U6 hisob bloklangan — buyurtma tasdiqlanadi, usta yozilmaydi; bloklangan sessiya tarixni ko'rmaydi (401)",
      _r6.status_code == 200 and order_master(O6) is None and tarix(S_USTA).status_code == 401, (_r6.status_code, order_master(O6)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. Kabinet: o'z buyurtmasining PDF i")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
p1 = pdf(S_MAG, {"raqam": R2})
check("P1 o'z buyurtmasi — PDF (application/pdf, fayl nomi), no-store", p1.status_code == 200 and p1.content[:4] == b"%PDF"
      and "buyurtma-" + str(R2) in (p1.headers.get("content-disposition") or "") and p1.headers.get("cache-control") == "no-store",
      (p1.status_code, p1.text[:200]))
_p = [pdf(S_MAG, {"raqam": R0}), pdf(S_MAG, {"raqam": R3}), pdf(S_MAG, {"raqam": "S-9999"})]
check("P2 boshqaning / mehmonning / yo'q buyurtma — 404, javob BIR XIL (borligi bilinmaydi)",
      all(x.status_code == 404 for x in _p) and len({x.text for x in _p}) == 1, [(x.status_code, x.text[:80]) for x in _p])
_pb = [pdf(S_MAG, {"raqam": "S 0001; --"}), pdf(S_MAG, {"raqam": R2, "kalit": "x" * 22}), pdf(S_MAG, {})]
check("P3 noto'g'ri tana — 400", all(x.status_code == 400 for x in _pb), [(x.status_code, x.text[:80]) for x in _pb])
_pn = [pdf(None, {"raqam": R2}), pdf(S_USTA, {"raqam": R2})]
check("P4 sessiyasiz / bloklangan sessiya — 401", all(x.status_code == 401 for x in _pn), [(x.status_code, x.text[:80]) for x in _pn])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L. Bloklangan hisob kirmoqchi bo'lsa")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_k = js(dok("/api/dokon/v1/kirish", {}))
tg(xabar(9001, text=f"/start k_{_k.get('kod')}"))
tg(xabar(9001, contact=kontakt(9001, "998901112233")))
_h1 = js(dok("/api/dokon/v1/kirish/holat", {"kod": _k.get("kod"), "sir": _k.get("sir")}))
_h2 = js(dok("/api/dokon/v1/kirish/holat", {"kod": _k.get("kod"), "sir": _k.get("sir")}))
check("L1 bloklangan hisob raqam yubordi — sayt «bloklangan» oladi (ilgari «kutilmoqda» da qolardi), sessiya BERILMAYDI",
      _h1 == {"holat": "bloklangan"} and _h2 == {"holat": "bloklangan"}
      and "yopilgan" in (oxirgi_bot(9001) or ("", ""))[1], (_h1, _h2, oxirgi_bot(9001)))
# review249 H249-3: raqam yuborilgandan KEYIN, sayt so'rashidan OLDIN blokdan chiqarilsa ham — o'sha kirish sessiya bermaydi
_k3 = js(dok("/api/dokon/v1/kirish", {}))
tg(xabar(9001, text=f"/start k_{_k3.get('kod')}"))
tg(xabar(9001, contact=kontakt(9001, "998901112233")))
CA.post(API + f"/mijozlar/{MJ_USTA}/ochish", json={})
_h3 = js(dok("/api/dokon/v1/kirish/holat", {"kod": _k3.get("kod"), "sir": _k3.get("sir")}))
check("L3 (H249-3) bloklangan paytda yuborilgan raqam — keyin blokdan chiqarilsa ham o'sha kirish «bloklangan» (sessiya yo'q)",
      _h3 == {"holat": "bloklangan"}, _h3)
S_USTA2, _hh = kirib_ol(9001, "998901112233", ism="Azizbek")
check("L2 blokdan chiqarilgan hisob qayta kira oladi (eski buyurtmalari tarixda qoladi)", bool(S_USTA2) and R1 in
      [x.get("raqam") for x in js(tarix(S_USTA2)).get("buyurtmalar") or []], (_hh, js(tarix(S_USTA2))))

_hol = bazadan(lambda d: d.query(DokonMijoz.mj_holat, DokonMijoz.master_id).filter(DokonMijoz.id == MJ_USTA).first())
r7 = buyurtma(Q, sessiya=S_USTA2)
_r7, O7 = tasdiqla(js(r7).get("raqam"))
check("L4 (H249-1) blokdan chiqarilgan usta («kutilmoqda», ERP ustasi bog'lami saqlangan) — buyurtmasiga usta YOZILMAYDI",
      tuple(_hol or ()) == ("kutilmoqda", MASTER1) and _r7.status_code == 200 and order_master(O7) is None, (_hol, _r7.status_code, order_master(O7)))
mijoz_admin(MJ_USTA, {"kpi": 3, "master_id": MASTER1})
# hisob bazada BOSHQA korxona ustasiga bog'langan bo'lsa (buzilgan / qo'lda tiklangan ma'lumot) — usta yozilmaydi, tasdiq ishlaydi
bazadan(lambda d: (d.query(DokonMijoz).filter(DokonMijoz.id == MJ_USTA).update({DokonMijoz.master_id: MASTER_B}), d.commit()))
r9 = buyurtma(Q, sessiya=S_USTA2)
_r9, O9 = tasdiqla(js(r9).get("raqam"))
bazadan(lambda d: (d.query(DokonMijoz).filter(DokonMijoz.id == MJ_USTA).update({DokonMijoz.master_id: MASTER1}), d.commit()))
check("L4b hisob boshqa korxona ustasiga bog'langan — tasdiq ishlaydi, usta YOZILMAYDI (korxona tekshiruvi)",
      _r9.status_code == 200 and order_master(O9) is None, (_r9.status_code, _r9.text[:200], order_master(O9)))
r8 = buyurtma(Q, sessiya=S_USTA2)
_r8, O8 = tasdiqla(js(r8).get("raqam"))
check("L5 qayta tasdiqlangach — keyingi buyurtmasiga usta yoziladi", _r8.status_code == 200 and order_master(O8) == MASTER1,
      (_r8.status_code, order_master(O8)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Kabinet PDF i holati (H249-4) va eski baza indeksi (H249-2)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
order_holat(O2, OrderStatus.CANCELLED)
_pd = bazadan(lambda d: crud.dokon_mijoz_pdf_malumoti(d, d.query(DokonBuyurtma).filter(DokonBuyurtma.sb_raqam == R2).first(),
                                                      crud._sayt_qatorlari(d, 1, sb(R2).id))) or {}
def _pdf_matn(r):
    import pypdf
    return "".join((pg.extract_text() or "") for pg in pypdf.PdfReader(io.BytesIO(r.content)).pages).replace(" ", "").replace("\n", "")


_pr = pdf(S_MAG, {"raqam": R2})
_pm = xavfsiz(lambda: _pdf_matn(_pr), "")
check("Q0 kabinet PDF ining O'ZIDA — «Buyurtmaholati:bekorqilindi», «Buyurtmatasdiqlangan.» yo'q", _pr.status_code == 200
      and "Buyurtmaholati:bekorqilindi" in _pm and "Buyurtmatasdiqlangan." not in _pm, (_pr.status_code, _pm[-300:]))
check("Q1 tasdiqlangan, keyin bekor qilingan buyurtma — kabinet PDF ida ham «bekor qilindi» (ro'yxat bilan bir xil), «tasdiqlangan» YO'Q",
      _pd.get("holat_nomi") == "Bekor qilindi" and "Buyurtma holati: bekor qilindi." in (_pd.get("pastki") or [])
      and "Buyurtma tasdiqlangan." not in (_pd.get("pastki") or []) and holat(R2, S_MAG) == "bekor" and pdf(S_MAG, {"raqam": R2}).status_code == 200,
      (_pd.get("holat_nomi"), _pd.get("pastki")))


def _indeks_bormi():
    import database as _dbx
    from sqlalchemy import inspect as _ins
    return any(i.get("name") == "ix_dokon_buyurtmalar_mijoz_id" for i in _ins(_dbx.engine).get_indexes("dokon_buyurtmalar"))


def _indeks_tikla():
    import database as _dbx
    from sqlalchemy import text as _t
    with _dbx.engine.connect() as _c:
        _c.execute(_t("DROP INDEX IF EXISTS ix_dokon_buyurtmalar_mijoz_id"))
        _c.commit()
    _yoq = not _indeks_bormi()
    with contextlib.redirect_stdout(io.StringIO()):
        _dbx.add_missing_indexes()
    return _yoq, _indeks_bormi()


check("Q2 (H249-2) eski bazada (indeks yo'q) — ishga tushishdagi indeks qadami uni yaratadi", xavfsiz(_indeks_tikla) == (True, True),
      xavfsiz(_indeks_tikla))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira va ikkinchi korxona")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bk = bazadan(lambda d: crud.export_full_backup(d, company_id=1)) or {}
_rows = ((_bk.get("tables") or {}).get("dokon_buyurtmalar")) or []
_mm = {x.get("sb_raqam"): x.get("mijoz_id") for x in _rows if isinstance(x, dict)}
check("Z1 zaxirada sayt buyurtmasining hisob bog'lami bor", _mm.get(R1) == MJ_USTA and _mm.get(R2) == MJ_MAG and R0 in _mm and _mm[R0] is None,
      dict(list(_mm.items())[:6]))
_res = bazadan(lambda d: crud.import_full_backup(d, _bk, company_id=1, replace=True)) or {}
check("Z2 tiklashdan keyin bog'lam AYNAN (kabinet tarixi qaytadi)", _res.get("success") is True and mid_of(R1) == MJ_USTA and mid_of(R2) == MJ_MAG,
      (_res.get("success"), mid_of(R1), mid_of(R2)))
# B korxona kaliti + A korxona sessiyasi — tarix yo'q
CBK = mijoz("t249_b")
CP.post("/api/platform/companies/2/dokon", data={"yoqilgan": "1"})
_bkalit = ""
with SessionLocal() as _d:
    _co = _d.get(Company, 2)
    for _n in [x for x in dir(models) if x.startswith("_")][:0]:
        pass
_bkalit = js(CBK.post(API + "/api-kalit", json={})).get("kalit") or ""
_tb = NC.get(MB, headers={"X-Dokon-Kalit": _bkalit or "pdk_x", "X-Mijoz-Sessiya": S_MAG})
check("Z3 boshqa korxona kaliti + bu korxona sessiyasi — tarix YO'Q (401 yoki 404)", _tb.status_code in (401, 404) and R2 not in _tb.text,
      (_bkalit[:6], _tb.status_code, _tb.text[:120]))
check("Z4 do'kon API yo'llari ro'yxatida yangi yo'llar bor", HAS and "/api/dokon/v1/mijoz/buyurtmalar" in crud.DOKON_API_YOLLAR
      and "/api/dokon/v1/mijoz/buyurtmalar/pdf" in crud.DOKON_API_YOLLAR, getattr(crud, "DOKON_API_YOLLAR", None))

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
