#!/usr/bin/env python3
"""
test_dokon_kutish252.py — kech185 (zip 252: do'kon — «Kelganda xabar bering»; ERP tomoni).

NIMA UCHUN KERAK
  Egasi rejasi («Onlayn do'kon rejasi» 30.10): «Tayyor mahsulot tugasa, mijoz tugmani bosadi; omborga kelganda Telegram'da xabar oladi.
  Siz qaysi mahsulot kutilayotganini ko'rasiz»; «… «Kelganda xabar bering» shakllarida urinishlar soni cheklanadi». Faqat kirgan hisob,
  faqat «Tayyor mahsulotlar» dagi TUGAGAN element (saytdagi qoldiq — `/api/dokon/v1/tayyor` bilan AYNAN); xabar — BIR marta (shartli
  UPDATE), yetmasa — qayta urinish, 5 tadan keyin «xato»; bloklangan hisobga — yo'q; bo'lim yashirin — kutadi. Asl kodda (zip 251) bu
  yo'llar / jadval YO'Q — test yiqiladi (qulamaydi).
BO'LIMLAR
  S — tayyorgarlik. A — statik (jadval, yo'llar, rejalashtiruvchi). K — kirish. Q — qo'shish / bekor / chegaralar. T — tekshiruv (xabar).
  D — admin ro'yxati. Z — ikkinchi korxona, zaxira / tiklash / o'chirish. U — haqiqiy brauzer (admin bo'limi; PG da o'tkaziladi).
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
ISHLATISH: python3 tools/test_dokon_kutish252.py
"""
import os
import io
import sys
import json
import time
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta
from collections import Counter

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"kutish252_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t252_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't252.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "DOKON_BOT_TOKEN", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Master, Inventory, FinishedProduct, StockSource, ProductionStatus   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
DokonMijoz = getattr(models, "DokonMijoz", None)
DokonBolim = getattr(models, "DokonBolim", None)
DokonKutish = getattr(models, "DokonKutish", None)


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
    t = datetime(2026, 11, 4, 7, 0)          # Toshkent 12:00

    @classmethod
    def utcnow(cls):
        return cls.t


if getattr(crud, "_dt233", None) is not None:
    crud._dt233 = _SoxtaVaqt
TG = []
main._send_telegram = lambda *a, **k: TG.append(" ".join(str(x) for x in a)) or True

# Telegram — soxta (tarmoq yo'q): getMe / getWebhookInfo va bot xabarlari yoziladi
BOT_TOKEN = "123456789:AAHsinov252_" + "q" * 24
TGAPI = {"getMe": {"username": "penodecor_sinov_bot"}, "getWebhookInfo": {"url": ""}}
BOT = []


def _soxta_tg_api(token, metod, maydonlar=None, timeout=10):
    if metod == "setWebhook":
        TGAPI["getWebhookInfo"] = {"url": (maydonlar or {}).get("url", "")}
        return True
    return TGAPI.get(metod)


main._tg_api = _soxta_tg_api
main._tg_post_message = lambda token, chat_id, text, reply_markup=None: BOT.append((str(chat_id), text, reply_markup, token))

s = SessionLocal()
_c1 = s.get(Company, 1)
_c1.name = "T252 Penodekor"
s.add(Company(id=2, name="T252 Begona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t252_admin", PAROL, UserRole.ADMIN, "T252 Admin", company_id=1)
    auth.create_user(s, "t252_plat", PAROL, UserRole.ADMIN, "T252 Platforma", company_id=1)
    auth.create_user(s, "t252_b", PAROL, UserRole.ADMIN, "T252 B", company_id=2)
    auth.create_user(s, "t252_men", PAROL, UserRole.MANAGER, "T252 Menejer", company_id=1)
s.query(User).filter(User.username == "t252_plat").first().is_platform_admin = True
s.add(Master(company_id=1, name="Bahodir usta", phone="+998 90 111 22 33", kpi_percent=3.0, cashback_percent=0.0, is_active=True))
s.add(Inventory(company_id=1, item_name="Penoplast T252", unit="blok", is_penoplast=True, is_default_penoplast=True,
                volume_per_unit=1.0, price_per_unit=1000000, stock_quantity=50))
s.commit()
MASTER1 = s.query(Master.id).filter(Master.company_id == 1, Master.name == "Bahodir usta").scalar()
PENO = s.query(Inventory.id).filter(Inventory.company_id == 1).scalar()
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t252_admin")
CP = mijoz("t252_plat")
CB = mijoz("t252_b")
CM = mijoz("t252_men")
NC = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
_s2 = SessionLocal()                     # B korxonasi — platforma egasiniki emas (yoqish yo'li 400): sinov uchun bazada yoqiladi
_s2.get(Company, 2).dokon_yoqilgan = True
_s2.commit()
_s2.close()
KALIT = js(CA.post(API + "/api-kalit", json={})).get("kalit") or ""
KALIT_B = js(CB.post(API + "/api-kalit", json={})).get("kalit") or ""
KT = "/api/dokon/v1/kutish"
KTB = "/api/dokon/v1/kutish/bekor"
TY = "/api/dokon/v1/tayyor"


def chek_tozala(kutish=True):
    for _n in ("_DOKON_API_CHEKLOV", "_DOKON_KIRISH_CHEKLOV", "_DOKON_HOLAT_CHEKLOV", "_DOKON_MIJOZ_CHEKLOV") + \
              (("_DOKON_KUTISH_CHEKLOV",) if kutish else ()):
        _ch = getattr(crud, _n, None)
        if _ch is not None:
            _ch.tozala()


def dok(yol, tana=None, sessiya=None, kalit=None, usul="post", kutish_tozala=True, xom=None):
    chek_tozala(kutish_tozala)
    h = {"X-Dokon-Kalit": KALIT if kalit is None else kalit, "Content-Type": "application/json"}
    if sessiya is not None:
        h["X-Mijoz-Sessiya"] = sessiya
    if usul == "get":
        return NC.get(yol, headers=h)
    return NC.post(yol, content=xom if xom is not None else json.dumps(tana if tana is not None else {}).encode("utf-8"), headers=h)


def tg(update):
    return NC.post("/telegram/dokon", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": bot_sir(BOT_TOKEN)})


def xabar(uid, text=None, contact=None, ism="Azizbek"):
    m = {"message_id": 1, "date": 1, "from": {"id": uid, "is_bot": False, "first_name": ism}, "chat": {"id": uid, "type": "private"}}
    if text is not None:
        m["text"] = text
    if contact is not None:
        m["contact"] = contact
    return {"update_id": uid, "message": m}


def bot_sir(token):
    import hmac
    return hmac.new(token.encode("utf-8"), b"penodecor-dokon-bot-webhook", "sha256").hexdigest()


def bazadan(fn):
    """Bazadan o'qish / yozish (commit); xato (asl kodda jadval / model yo'q) — None (test yiqiladi, qulamaydi)."""
    d = SessionLocal()
    try:
        r = fn(d)
        d.commit()
        return r
    except Exception:                      # noqa: BLE001
        d.rollback()
        return None
    finally:
        d.close()


def kirib_ol(uid, tel, ism="Azizbek", sayt=None):
    """To'liq oqim: kirish → /start → kontakt → holat. Natija — sessiya."""
    k = js(dok("/api/dokon/v1/kirish", {"sayt": sayt} if sayt else {}))
    tg(xabar(uid, text=f"/start k_{k.get('kod')}", ism=ism))
    tg(xabar(uid, contact={"phone_number": tel, "first_name": ism, "last_name": "K", "user_id": uid}, ism=ism))
    return js(dok("/api/dokon/v1/kirish/holat", {"kod": k.get("kod"), "sir": k.get("sir")})).get("sessiya")


def mid_of(tg_id):
    return bazadan(lambda d: d.query(DokonMijoz.id).filter(DokonMijoz.company_id == 1, DokonMijoz.mj_tg_id == str(tg_id)).scalar())


def model(bolim, kod, **kw):
    return js(CA.post(API + "/modellar", json=dict({"bolim_id": bolim, "kod": kod}, **kw))).get("id")


def detal(mid, turi, olcham, **kw):
    return js(CA.post(API + "/detallar", json=dict({"model_id": mid, "turi": turi, "olcham": olcham}, **kw))).get("id")


def fp(nom, q, cat="profil", unit="metr", w=15.0, t=10.0, cid=1):
    def f(d):
        x = FinishedProduct(company_id=cid, name=nom, category=cat, is_coated=True, width=w, thickness=t, quantity=q,
                            produced_quantity=max(q, 0), unit=unit, unit_price=1, cost_price=max(q, 0) * 1000, unit_cost_stable=1000,
                            source=StockSource.PRODUCED, unit_volume_m3=0.01, volume_m3=0.01 * max(q, 0),
                            production_status=ProductionStatus.READY, reserved_quantity=0.0, penoplast_id=PENO if cid == 1 else None)
        d.add(x)
        d.flush()
        return x.id
    return bazadan(f)


def fp_miqdor(fid, q):
    def f(d):
        x = d.get(FinishedProduct, fid)
        x.quantity = q
        x.produced_quantity = max(q, 0)
        return True
    return bazadan(f)


def tmk(nom_qismi, c=None):
    return next((x for x in (js((c or CA).get(API + "/tm-mahsulotlar")).get("mahsulotlar") or []) if nom_qismi in (x.get("nom") or "")), {})


def bogla(did, nom_qismi):
    return CA.put(API + f"/detallar/{did}/tm", json={"tm_kaliti": tmk(nom_qismi).get("kalit")})


def tayyor(kalit=None):
    chek_tozala()
    return js(NC.get(TY, headers={"X-Dokon-Kalit": KALIT if kalit is None else kalit}))


def qoldiq(did):
    return next((x.get("qoldiq") for x in (tayyor().get("detallar") or []) if x.get("detal_id") == did), None)


def komplekt_soni(mid, kom, kb):
    return next((x.get("soni") for x in (tayyor().get("komplektlar") or []) if x.get("model_id") == mid and x.get("komplekt") == kom
                 and x.get("kapitel_baza") is kb), None)


def kutishlar(sessiya):
    return js(dok(KT, sessiya=sessiya, usul="get")).get("kutishlar")


def faol_kalitlar(sessiya):
    return sorted(x.get("kalit") for x in (kutishlar(sessiya) or []) if x.get("holat") == "kutilmoqda")


def qator(kalit, mid):
    return bazadan(lambda d: (lambda r: None if r is None else {"id": r.id, "holat": r.kt_holat, "urinish": r.kt_urinish, "nom": r.kt_nom,
                                                                "xabar": r.kt_xabar_vaqti, "created": r.created_at})(
        d.query(DokonKutish).filter(DokonKutish.company_id == 1, DokonKutish.mijoz_id == mid, DokonKutish.kt_kalit == kalit).first()))


def kutish_soni(**f):
    def _f(d):
        q = d.query(DokonKutish).filter(DokonKutish.company_id == f.pop("cid", 1))
        for k, v in f.items():
            q = q.filter(getattr(DokonKutish, k) == v)
        return q.count()
    return bazadan(_f)


def tekshir(yubor=None, cid=1, hozir=None):
    yub = yubor if yubor is not None else (lambda chat, matn, tugma: BOT.append((str(chat), matn, tugma, "tekshir")) or True)
    d = SessionLocal()
    try:
        return crud.dokon_kutish_tekshir(d, cid, yub, hozir=hozir)
    except Exception as e:                 # noqa: BLE001
        d.rollback()
        return {"xato_turi": f"{type(e).__name__}: {e}"}
    finally:
        d.close()


def botga(chat, n0=0):
    return [x for x in BOT[n0:] if x[0] == str(chat)]


def bolim_yoq(tizim, yoqilgan):
    def f(d):
        b = d.query(DokonBolim).filter(DokonBolim.company_id == 1, DokonBolim.tizim_kaliti == tizim).first()
        b.yoqilgan = yoqilgan
        return True
    return bazadan(f)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Tayyorgarlik: bot, hisoblar, katalog, ombor")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
os.environ["DOKON_BOT_TOKEN"] = BOT_TOKEN
K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}
KOMP, KAR, DEK = BOL.get("Rom va eshik dekorlari"), BOL.get("Karnizlar"), BOL.get("Dekor elementlar")
ORTA = "O'rta"
MR = model(KOMP, "R-20", nom="Klassik", kapitel_baza_bor=True)
DID = {t: detal(MR, t, ORTA, narx=n, eni_sm=15, qalinligi_sm=10)
       for t, n in {"karniz": 15000, "podokonnik": 14000, "nalichnik": 12000, "kapitel": 30000, "baza": 31000}.items()}
MK = model(KAR, "K-20", nom="Tekis")
DID["k20"] = detal(MK, "asosiy", "20 sm", narx=50000, eni_sm=20, qalinligi_sm=8)
DID["k25"] = detal(MK, "asosiy", "25 sm", narx=60000, eni_sm=25, qalinligi_sm=8)          # omborga bog'lanmaydi — «Tayyor»da yo'q
MD = model(DEK, "D-7", nom="Gul *qalin* _yotiq_ [havola]")                                # Telegram Markdown belgilari
DID["d7"] = detal(MD, "asosiy", "S", narx=9000)
FP = {"rk": fp("Karniz R-20 15 sm", 12), "rp": fp("Podokonnik R-20 15 sm", 9), "rn": fp("Nalichnik R-20 15 sm", 20),
      "rkap": fp("Kapitel R-20", 1, cat="dona", unit="dona", w=None, t=None), "rbaz": fp("Baza R-20", 1, cat="dona", unit="dona", w=None, t=None),
      "k20": fp("Karniz K-20 20 sm", 0.5, w=20, t=8), "d7": fp("Rozetka D-7", 3, cat="dona", unit="dona", w=None, t=None)}
_bg = [bogla(DID[t], n).status_code for t, n in (("karniz", "Karniz R-20"), ("podokonnik", "Podokonnik R-20"), ("nalichnik", "Nalichnik R-20"),
                                                ("kapitel", "Kapitel R-20"), ("baza", "Baza R-20"), ("k20", "Karniz K-20"), ("d7", "Rozetka D-7"))]
check("S0 katalog (rom R-20 O'rta 5 detal, K-20 20 sm / 25 sm, D-7) va ombor partiyalari bog'landi; kalitlar bor",
      all(DID.values()) and all(FP.values()) and _bg == [200] * 7 and KALIT.startswith("pdk_") and KALIT_B.startswith("pdk_"), (DID, FP, _bg))
check("S1 «Tayyor»: K-20 20 sm — 0,5 m (tugagan), D-7 — 3 dona (bor), K-20 25 sm — yo'q; rom kapitel-baza bilan — 0 komplekt, ularsiz — ≥ 1",
      qoldiq(DID["k20"]) == 0.5 and qoldiq(DID["d7"]) == 3 and qoldiq(DID["k25"]) is None
      and komplekt_soni(MR, "rom", True) == 0 and (komplekt_soni(MR, "rom", False) or 0) >= 1,
      (qoldiq(DID["k20"]), qoldiq(DID["d7"]), tayyor().get("komplektlar")))
SAYT = "https://dokon.sinov.uz"
S_USTA = kirib_ol(9201, "998901112201", ism="Azizbek", sayt=SAYT)
dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "Azizbek usta"}, sessiya=S_USTA)
MJ_USTA = mid_of(9201)
_ru = CA.post(API + f"/mijozlar/{MJ_USTA}/tasdiqla", json={"kpi": 3, "master_id": MASTER1})
S_MAG = kirib_ol(9202, "998901112202", ism="Botir")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "magazin", "ism": "Botir", "magazin": "Qurilish dunyosi", "shahar": "Asaka"}, sessiya=S_MAG)
MJ_MAG = mid_of(9202)                                                                      # tasdiq kutmoqda — baribir kirgan hisob
S_YANGI = kirib_ol(9203, "998901112203", ism="Yangi")                                       # kirdi, ro'yxat so'rovi yubormagan
MJ_YANGI = mid_of(9203)
S_BLOK = kirib_ol(9204, "998901112204", ism="Bloklanadi")
MJ_BLOK = mid_of(9204)
check("S2 hisoblar: tasdiqlangan usta, tasdiq kutayotgan magazin, yangi, keyin bloklanadigan; sayt manzili ERP da",
      all((S_USTA, S_MAG, S_YANGI, S_BLOK, MJ_USTA, MJ_MAG, MJ_YANGI, MJ_BLOK)) and _ru.status_code == 200
      and crud.get_setting(SessionLocal(), crud.DOKON_SAYT_URL_KALIT, None, company_id=1) == SAYT, (_ru.status_code, _ru.text[:200]))
EK20 = {"tur": "d", "detal_id": DID["k20"]}
ED7 = {"tur": "d", "detal_id": DID["d7"]}
ER1 = {"tur": "k", "model_id": MR, "komplekt": "rom", "olcham": ORTA, "kapitel_baza": True}
ER0 = {"tur": "k", "model_id": MR, "komplekt": "rom", "olcham": ORTA, "kapitel_baza": False}
K_K20 = f"d|{DID['k20']}"
K_R1 = f"k|{MR}|rom|1|o'rta"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Statik: jadval, yo'llar, rejalashtiruvchi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_t = getattr(DokonKutish, "__table__", None)
check("A1 jadval dokon_kutishlar: hisob × kalit YAGONA (uq_dokon_kutish_kalit), mijoz_id → dokon_mijozlar (CASCADE), holat indeksli",
      _t is not None and _t.name == "dokon_kutishlar" and any(getattr(c, "name", "") == "uq_dokon_kutish_kalit" for c in _t.constraints)
      and any(fk.column.table.name == "dokon_mijozlar" and fk.ondelete == "CASCADE" for fk in _t.c.mijoz_id.foreign_keys)
      and _t.c.kt_holat.index, getattr(_t, "name", None))
_yollar = {(m, getattr(r, "path", "")) for r in main.app.routes for m in (getattr(r, "methods", None) or ())}
check("A2 yo'llar: GET / POST /api/dokon/v1/kutish, POST /kutish/bekor, admin GET /api/sayt-katalogi/kutishlar; do'kon yo'llari ro'yxatida",
      {("GET", KT), ("POST", KT), ("POST", KTB), ("GET", API + "/kutishlar")} <= _yollar
      and KT in getattr(crud, "DOKON_API_YOLLAR", ()) and KTB in getattr(crud, "DOKON_API_YOLLAR", ()), sorted(p for _m, p in _yollar if "kutish" in p))
_tr = xavfsiz(lambda: [m.__name__ for m in crud._reset_table_order()], [])
check("A3 o'chirish tartibi: kutish hisobdan OLDIN (tiklashda — keyin); korxona bog'lami qoidasi (_TENANT_REFS)",
      "DokonKutish" in _tr and _tr.index("DokonKutish") < _tr.index("DokonMijoz")
      and models._TENANT_REFS.get("DokonKutish") == [("mijoz_id", "DokonMijoz")], _tr[-30:])
_job = xavfsiz(lambda: main._scheduler.get_job("dokon_kutish"))
check("A4 rejalashtiruvchi: «dokon_kutish» — har 5 daqiqa, bir vaqtda bitta nusxa",
      _job is not None and _job.trigger.interval == timedelta(minutes=5) and _job.max_instances == 1, _job)
xavfsiz(lambda: main._scheduler.remove_job("dokon_kutish"))           # sinov davomida fon ishi aralashmasin

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Kirish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = [dok(KT, usul="get").status_code, dok(KT, EK20).status_code, dok(KTB, {"kalit": K_K20}).status_code,
      dok(KT, sessiya="pds_" + "x" * 43, usul="get").status_code, dok(KT, EK20, sessiya="pds_" + "x" * 43).status_code]
check("K1 sessiyasiz / soxta sessiya — 401 (o'qish ham, yozish ham); hech narsa yozilmadi",
      _r == [401] * 5 and kutish_soni() == 0, _r)
_r = [dok(KT, sessiya=S_USTA, kalit="pdk_" + "y" * 40, usul="get").status_code, dok(KT, EK20, sessiya=S_USTA, kalit="").status_code]
check("K2 noto'g'ri do'kon kaliti — 401 / 403 (kalitsiz yo'l yo'q)", all(x in (401, 403) for x in _r) and kutish_soni() == 0, _r)
r = dok(KT, sessiya=S_USTA, usul="get")
check("K3 kirgan hisob — 200, bo'sh ro'yxat, max 30; javob no-store", r.status_code == 200 and js(r).get("kutishlar") == []
      and js(r).get("max") == 30 and "no-store" in r.headers.get("cache-control", ""), (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Qo'shish, bekor qilish, chegaralar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = dok(KT, EK20, sessiya=S_USTA)
J = js(r)
_x = (J.get("kutishlar") or [{}])[0]
check("Q1 K-20 20 sm (0,5 m — «Tugagan») — 200: ro'yxatda kalit, nom «K-20 Tekis · 20 sm», holat «kutilmoqda», sana (Toshkent)",
      r.status_code == 200 and J.get("faol") == 1 and _x.get("kalit") == K_K20 and _x.get("nom") == "K-20 Tekis · 20 sm"
      and _x.get("holat") == "kutilmoqda" and _x.get("sana") == "04.11.2026" and _x.get("detal_id") == DID["k20"]
      and "no-store" in r.headers.get("cache-control", ""), (r.status_code, r.text[:400]))
_q1 = qator(K_K20, MJ_USTA)
r2 = dok(KT, EK20, sessiya=S_USTA)
check("Q2 takror bosish — 200, BITTA yozuv (o'sha raqam), o'zgarmadi",
      r2.status_code == 200 and kutish_soni(mijoz_id=MJ_USTA) == 1 and qator(K_K20, MJ_USTA) == _q1, (r2.status_code, _q1, qator(K_K20, MJ_USTA)))
r = dok(KT, ED7, sessiya=S_USTA)
check("Q3 omborda BOR (D-7 — 3 dona) — 409 «savatga qo'shing», yozilmadi",
      r.status_code == 409 and "omborda bor" in js(r).get("detail", "") and kutish_soni(mijoz_id=MJ_USTA) == 1, (r.status_code, r.text[:200]))
_r = [dok(KT, {"tur": "d", "detal_id": DID["k25"]}, sessiya=S_USTA).status_code,
      dok(KT, {"tur": "d", "detal_id": 2_000_000}, sessiya=S_USTA).status_code,
      dok(KT, dict(ER1, olcham="Katta"), sessiya=S_USTA).status_code, dok(KT, dict(ER1, komplekt="eshik", model_id=MK), sessiya=S_USTA).status_code]
check("Q4 «Tayyor»da yo'q element (bog'lanmagan detal, yo'q raqam, yo'q o'lcham, komplekt bo'lmagan model) — 404, yozilmadi",
      _r == [404] * 4 and kutish_soni(mijoz_id=MJ_USTA) == 1, _r)
r = dok(KT, ER1, sessiya=S_USTA)
r0 = dok(KT, ER0, sessiya=S_USTA)
_x = next((x for x in js(r).get("kutishlar") or [] if x.get("tur") == "k"), {})
check("Q5 komplekt: rom kapitel-baza bilan (0 ta yig'iladi) — 200, kalit / nom «R-20 Klassik — Rom komplekti, O'rta»; ularsiz (bor) — 409",
      r.status_code == 200 and _x.get("kalit") == K_R1 and _x.get("nom") == "R-20 Klassik — Rom komplekti, O'rta"
      and _x.get("kapitel_baza") is True and _x.get("olcham") == ORTA and _x.get("model_id") == MR and r0.status_code == 409,
      (r.status_code, r.text[:300], r0.status_code))
r = dok(KT, dict(ER1, olcham="O‘RTA"), sessiya=S_USTA)
check("Q6 o'lcham tutuq belgisi / harfi boshqacha («O‘RTA») — o'sha element (yangi yozuv YO'Q)",
      r.status_code == 200 and kutish_soni(mijoz_id=MJ_USTA) == 2, (r.status_code, kutish_soni(mijoz_id=MJ_USTA)))
_yomon = [dict(EK20, boshqa=1), {"tur": "x", "detal_id": 1}, {"tur": "d", "detal_id": True}, {"tur": "d", "detal_id": "5"},
          {"tur": "d", "detal_id": 0}, {"tur": "d", "detal_id": 2 ** 31}, dict(EK20, model_id=MR), dict(ER1, komplekt="stol"),
          dict(ER1, kapitel_baza="ha"), dict(ER1, olcham=""), dict(ER1, olcham="x" * 61), dict(ER1, detal_id=1), dict(ER1, model_id=None),
          dict(ER1, olcham="\ud800")]
_r = [dok(KT, t, sessiya=S_USTA).status_code for t in _yomon] + [dok(KT, sessiya=S_USTA, xom=b"[1, 2]").status_code,
                                                                   dok(KT, sessiya=S_USTA, xom=b"{yomon").status_code]
check("Q7 noto'g'ri so'rovlar (ortiqcha maydon, tur, raqam turi / chegarasi, komplekt, kapitel_baza, o'lcham, surrogat, JSON emas) — 400",
      _r == [400] * len(_r) and kutish_soni(mijoz_id=MJ_USTA) == 2, _r)
r = dok(KT, EK20, sessiya=S_MAG)
r2 = dok(KT, EK20, sessiya=S_YANGI)
check("Q8 tasdiq kutayotgan magazin va ro'yxat so'rovi yubormagan hisob ham — 200 (kirgan hisob yetarli); har biri o'z ro'yxatini ko'radi",
      r.status_code == 200 and r2.status_code == 200 and faol_kalitlar(S_MAG) == [K_K20] and faol_kalitlar(S_YANGI) == [K_K20]
      and faol_kalitlar(S_USTA) == sorted([K_K20, K_R1]), (r.status_code, r2.status_code, faol_kalitlar(S_USTA)))
bolim_yoq("tayyor", False)
r = dok(KT, ER1, sessiya=S_BLOK)
bolim_yoq("tayyor", True)
check("Q9 «Tayyor mahsulotlar» bo'limi yashirin — 404 «bo'limi hozir yopiq», yozilmadi", r.status_code == 404 and "yopiq" in js(r).get("detail", "")
      and kutish_soni(mijoz_id=MJ_BLOK) == 0, (r.status_code, r.text[:200]))
r = dok(KTB, {"kalit": K_K20}, sessiya=S_YANGI)
check("Q10 bekor qilish — 200, ro'yxatda yo'q, bazada «bekor»; boshqalarniki o'zgarmadi",
      r.status_code == 200 and js(r).get("kutishlar") == [] and (qator(K_K20, MJ_YANGI) or {}).get("holat") == "bekor"
      and faol_kalitlar(S_MAG) == [K_K20] and faol_kalitlar(S_USTA) == sorted([K_K20, K_R1]), (r.status_code, r.text[:200]))
_r = [dok(KTB, {"kalit": K_K20}, sessiya=S_YANGI).status_code, dok(KTB, {"kalit": K_R1}, sessiya=S_MAG).status_code,
      dok(KTB, {"kalit": "d|999999"}, sessiya=S_MAG).status_code]
check("Q11 qayta bekor / boshqa hisobniki / yo'q — 404; boshqa hisobning kutishi o'zgarmadi",
      _r == [404, 404, 404] and (qator(K_R1, MJ_USTA) or {}).get("holat") == "kutilmoqda", _r)
_r = [dok(KTB, {}, sessiya=S_MAG).status_code, dok(KTB, {"kalit": 5}, sessiya=S_MAG).status_code,
      dok(KTB, {"kalit": "x" * 121}, sessiya=S_MAG).status_code, dok(KTB, {"kalit": K_K20, "b": 1}, sessiya=S_MAG).status_code,
      dok(KTB, {"kalit": K_K20}).status_code]
check("Q12 bekor — noto'g'ri tana 400, sessiyasiz 401", _r == [400, 400, 400, 400, 401], _r)
_id0 = (qator(K_K20, MJ_YANGI) or {}).get("id")
r = dok(KT, EK20, sessiya=S_YANGI)
_q = qator(K_K20, MJ_YANGI) or {}
check("Q13 bekor qilingandan keyin qayta bosish — o'sha yozuv yana «kutilmoqda» (yangi qator YO'Q)",
      r.status_code == 200 and _q.get("id") == _id0 and _q.get("holat") == "kutilmoqda" and kutish_soni(mijoz_id=MJ_YANGI) == 1, (_id0, _q))
_eski_max = getattr(crud, "DOKON_KUTISH_MAX", 30)
crud.DOKON_KUTISH_MAX = 2
r = dok(KT, EK20, sessiya=S_BLOK)
r2 = dok(KT, ER1, sessiya=S_BLOK)
_kb = js(dok(KTB, {"kalit": K_K20}, sessiya=S_BLOK))
r3 = dok(KT, EK20, sessiya=S_USTA)
crud.DOKON_KUTISH_MAX = 1
r4 = dok(KT, ER1, sessiya=S_YANGI)
crud.DOKON_KUTISH_MAX = _eski_max
check("Q14 faol kutishlar chegarasi (sinovda 1 / 2): to'lgan — 409 «Ko'pi bilan»; bekor qilinsa — qayta qo'shiladi; mavjud faolini takror "
      "bosish chegaraga urilmaydi",
      r.status_code == 200 and r2.status_code == 200 and _kb.get("faol") == 1 and r3.status_code == 200 and r4.status_code == 409
      and "Ko'pi bilan 1" in js(r4).get("detail", "") and faol_kalitlar(S_YANGI) == [K_K20],
      (r.status_code, r2.status_code, _kb, r3.status_code, r4.status_code, r4.text[:200]))
chek_tozala()
_r = [dok(KT, EK20, sessiya="pds_" + "z" * 43, kutish_tozala=False).status_code for _ in range(25)]
_r += [dok(KTB, {"kalit": K_R1}, sessiya=S_BLOK, kutish_tozala=False).status_code]
_r += [dok(KT, EK20, sessiya=S_MAG, kutish_tozala=False).status_code for _ in range(20)]
r = dok(KT, EK20, sessiya=S_MAG, kutish_tozala=False)
r2 = dok(KT, EK20, sessiya=S_USTA, kutish_tozala=False)
check("Q15 hisob chegarasi: daqiqasiga 20 yozuvchi so'rov — 21-si 429 (Retry-After); sessiyasizlari sanalmaydi; boshqa hisobga ta'sir yo'q",
      _r[:25] == [401] * 25 and _r[25:] == [200] * 21 and r.status_code == 429 and int(r.headers.get("retry-after", "0")) >= 1
      and r2.status_code == 200, (_r, r.status_code, r.headers.get("retry-after"), r2.status_code))
chek_tozala()
r = dok(KT, sessiya=S_MAG, usul="get")
check("Q16 GET chegaraga kirmaydi (o'qish) — 200", r.status_code == 200, r.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Tekshiruv va Telegram xabari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_holat0 = bazadan(lambda d: sorted((r.mijoz_id, r.kt_kalit, r.kt_holat) for r in d.query(DokonKutish).filter(DokonKutish.company_id == 1).all()))
n0 = len(BOT)
st = tekshir()
check("T1 hech narsa kelmagan — xabar YO'Q, holatlar o'zgarmadi",
      len(BOT) == n0 and st.get("yuborildi") == 0 and bazadan(lambda d: sorted((r.mijoz_id, r.kt_kalit, r.kt_holat) for r in d.query(DokonKutish)
                                                                                .filter(DokonKutish.company_id == 1).all())) == _holat0, (st, _holat0))
FP["k20b"] = fp("Karniz K-20 20 sm", 5, w=20, t=8)
n0 = len(BOT)
st = tekshir()
_u = botga(9201, n0)
_m = botga(9202, n0)
_y = botga(9203, n0)
check("T2 K-20 keldi (0,5 + 5 = 5,5 m): uchala kutuvchiga BIR xabar — nom, «Hozir omborda: 5 metr», 48 soat band; tugma — sayt/tayyor",
      qoldiq(DID["k20"]) == 5.5 and st.get("yuborildi") == 3 and len(_u) == 1 and len(_m) == 1 and len(_y) == 1
      and "K-20 Tekis · 20 sm" in _u[0][1] and "Hozir omborda: 5 metr" in _u[0][1] and "48 soat" in _u[0][1]
      and _u[0][2] == {"inline_keyboard": [[{"text": "🛒 Tayyor mahsulotlar", "url": SAYT + "/tayyor"}]]}, (st, BOT[n0:]))
_q = qator(K_K20, MJ_USTA) or {}
check("T3 bazada «yuborildi», xabar vaqti; rom komplekti (hali yo'q) — «kutilmoqda»",
      _q.get("holat") == "yuborildi" and _q.get("xabar") == _SoxtaVaqt.t and (qator(K_R1, MJ_USTA) or {}).get("holat") == "kutilmoqda", _q)
n0 = len(BOT)
st = tekshir()
check("T4 qayta tekshiruv — takror xabar YO'Q", len(BOT) == n0 and st.get("yuborildi") == 0, st)
_ls = {x.get("kalit"): x for x in kutishlar(S_USTA) or []}
check("T5 kabinet ro'yxati: faoli birinchi (rom), keyin kelgan — «yuborildi», «Keldi — Telegramga xabar yuborildi», xabar sanasi",
      list(_ls) == [K_R1, K_K20] and _ls[K_K20].get("holat") == "yuborildi" and _ls[K_K20].get("xabar_sana") == "04.11.2026 12:00"
      and "yuborildi" in _ls[K_K20].get("holat_nomi", ""), _ls)
r = dok(KT, EK20, sessiya=S_USTA)
_tm = getattr(crud, "DOKON_KUTISH_TARIX_MAX", None)
crud.DOKON_KUTISH_TARIX_MAX = 0
_ls0 = [x.get("kalit") for x in kutishlar(S_USTA) or []]
crud.DOKON_KUTISH_TARIX_MAX = 50 if _tm is None else _tm
check("T5b kelganlar ro'yxati cheklangan (sinovda 0 — faqat faollari; do'kon 100 tadan ko'pini rad etadi)", _ls0 == [K_R1] and _tm == 50, _ls0)
check("T6 kelgandan keyin qayta bosish — omborda bor: 409 (yozuv «yuborildi» qoladi)",
      r.status_code == 409 and (qator(K_K20, MJ_USTA) or {}).get("holat") == "yuborildi", (r.status_code, r.text[:200]))
fp_miqdor(FP["k20b"], 0)
r = dok(KT, EK20, sessiya=S_USTA)
_q2 = qator(K_K20, MJ_USTA) or {}
check("T7 yana tugadi — qayta bosish: o'sha yozuv «kutilmoqda», urinish 0, xabar vaqti tozalandi",
      r.status_code == 200 and _q2.get("id") == _q.get("id") and _q2.get("holat") == "kutilmoqda" and _q2.get("urinish") == 0
      and _q2.get("xabar") is None, _q2)
fp_miqdor(FP["k20b"], 5)
_urin = []
st = tekshir(yubor=lambda chat, matn, tugma: _urin.append(chat) and False)
_q3 = qator(K_K20, MJ_USTA) or {}
check("T8 Telegram yetmadi (False) — «kutilmoqda», urinish 1, xabar vaqti yo'q (keyingi tekshiruvda yana)",
      _urin == ["9201"] and st.get("qayta") == 1 and _q3.get("holat") == "kutilmoqda" and _q3.get("urinish") == 1 and _q3.get("xabar") is None,
      (st, _q3, _urin))


def _xato(chat, matn, tugma):
    raise RuntimeError("tarmoq")


for _i in range(3):
    tekshir(yubor=_xato)
_q4 = qator(K_K20, MJ_USTA) or {}
st = tekshir(yubor=_xato)
_q5 = qator(K_K20, MJ_USTA) or {}
n0 = len(BOT)
st2 = tekshir()
check("T9 istisno ham — yetmadi; 5-urinishdan keyin «xato», boshqa urinilmaydi; ro'yxatda «Telegram xabari yetmadi»",
      _q4.get("urinish") == 4 and _q4.get("holat") == "kutilmoqda" and st.get("xato") == 1 and _q5.get("holat") == "xato"
      and _q5.get("urinish") == 5 and len(botga(9201, n0)) == 0 and st2.get("yuborildi") == 0
      and any(x.get("holat") == "xato" and "yetmadi" in x.get("holat_nomi", "") for x in kutishlar(S_USTA) or []), (_q4, _q5, st, st2))
# bir vaqtda ikki tekshiruv: birinchisi xabar yuborayotganda ikkinchisi ishlaydi — har kutishga BITTA xabar (shartli UPDATE)
fp_miqdor(FP["k20b"], 0)
for _ss in (S_MAG, S_YANGI):
    dok(KT, EK20, sessiya=_ss)
fp_miqdor(FP["k20b"], 5)
_ichki = []


def _ichma_ich(chat, matn, tugma):
    BOT.append((str(chat), matn, tugma, "tashqi"))
    if not _ichki:
        _ichki.append(tekshir())
    return True


n0 = len(BOT)
st = tekshir(yubor=_ichma_ich)
_sanoq = Counter(x[0] for x in BOT[n0:])
check("T10 bir vaqtda ikki tekshiruv — har hisobga BITTA xabar (ichki tekshiruv band qilinganini o'tkazib yubordi)",
      _sanoq == Counter({"9202": 1, "9203": 1}) and (_ichki[0].get("yuborildi") if _ichki else None) == 1 and st.get("yuborildi") == 1,
      (_sanoq, _ichki, st))
# «yuborilmoqda» da qolib ketgan (jarayon to'xtagan) — 30 daqiqadan keyin qayta navbatga
fp_miqdor(FP["k20b"], 0)
dok(KT, EK20, sessiya=S_MAG)
fp_miqdor(FP["k20b"], 5)


def _qotir(daqiqa):
    def f(d):
        r = d.query(DokonKutish).filter(DokonKutish.company_id == 1, DokonKutish.mijoz_id == MJ_MAG, DokonKutish.kt_kalit == K_K20).first()
        r.kt_holat = "yuborilmoqda"
        r.kt_xabar_vaqti = _SoxtaVaqt.t - timedelta(minutes=daqiqa)
        return True
    return bazadan(f)


_qotir(29)
n0 = len(BOT)
st = tekshir()
_a = (qator(K_K20, MJ_MAG) or {}).get("holat")
_qotir(31)
st2 = tekshir()
check("T11 «yuborilmoqda» da qolgan: 29 daqiqa — tegilmaydi (xabarsiz); 31 daqiqa — qayta navbat va xabar",
      _a == "yuborilmoqda" and st.get("tiklandi") == 0 and st2.get("tiklandi") == 1 and st2.get("yuborildi") == 1
      and len(botga(9202, n0)) == 1 and (qator(K_K20, MJ_MAG) or {}).get("holat") == "yuborildi", (_a, st, st2))
# bloklangan hisob — xabarsiz «bekor»
dok(KT, ER1, sessiya=S_BLOK)
dok(KT, ER1, sessiya=S_MAG)
_rb = CA.post(API + f"/mijozlar/{MJ_BLOK}/blokla")
FP["rkap2"] = fp("Kapitel R-20", 3, cat="dona", unit="dona", w=None, t=None)
FP["rbaz2"] = fp("Baza R-20", 3, cat="dona", unit="dona", w=None, t=None)
n0 = len(BOT)
st = tekshir()
_k = [x for x in BOT[n0:] if "Rom komplekti" in x[1]]
check("T12 komplekt keldi (kapitel / baza qo'shildi): usta va magazinga xabar «R-20 Klassik — Rom komplekti, O'rta», «… komplekt»; "
      "bloklangan hisob — xabarsiz «bekor»",
      _rb.status_code == 200 and (komplekt_soni(MR, "rom", True) or 0) >= 1 and sorted(x[0] for x in _k) == ["9201", "9202"]
      and all("R-20 Klassik — Rom komplekti, O'rta" in x[1] and " komplekt\n" in x[1] for x in _k)
      and not botga(9204, n0) and (qator(K_R1, MJ_BLOK) or {}).get("holat") == "bekor" and st.get("bekor") == 1, (st, BOT[n0:], _rb.status_code))
# Markdown belgilari va bo'lim yashirin
fp_miqdor(FP["d7"], 0.4)
dok(KT, ED7, sessiya=S_USTA)
bolim_yoq("tayyor", False)
fp_miqdor(FP["d7"], 4)
n0 = len(BOT)
st = tekshir()
_yq = (qator(f"d|{DID['d7']}", MJ_USTA) or {}).get("holat")
bolim_yoq("tayyor", True)
st2 = tekshir()
_d = botga(9201, n0)
check("T13 «Tayyor mahsulotlar» yashirin — xabar yo'q (kutadi); ochilgach — xabar; nom qalinsiz (review252 L2), * _ [ — Markdown uchun ekranlangan",
      st.get("yuborildi") == 0 and _yq == "kutilmoqda" and st2.get("yuborildi") == 1 and len(_d) == 1
      and r"«D-7 Gul \*qalin\* \_yotiq\_ \[havola] · S»" in _d[0][1] and "*D-7" not in _d[0][1] and "Hozir omborda: 4 dona" in _d[0][1],
      (st, st2, _d))
# do'kon o'chiq — hech narsa
fp_miqdor(FP["d7"], 0.2)
dok(KT, ED7, sessiya=S_USTA)
fp_miqdor(FP["d7"], 4)


def _dokon(yoq):
    def f(d):
        d.get(Company, 1).dokon_yoqilgan = yoq
        return True
    return bazadan(f)


_dokon(False)
n0 = len(BOT)
st = tekshir()
_dokon(True)
check("T14 sayt katalogi o'chirilgan korxona — tekshiruv hech narsa qilmaydi", st == {"yuborildi": 0, "qayta": 0, "xato": 0, "bekor": 0, "tiklandi": 0,
                                                                                    "toxtadi": 0}
      and len(BOT) == n0 and (qator(f"d|{DID['d7']}", MJ_USTA) or {}).get("holat") == "kutilmoqda", st)
# rejalashtiruvchi ishi: token yo'q — hech narsa; token bor — do'kon boti orqali (haqiqiy _tg_post_message yo'li)
os.environ.pop("DOKON_BOT_TOKEN", None)
n0 = len(BOT)
xavfsiz(lambda: main.dokon_kutish_ish())
_a = len(BOT) == n0 and (qator(f"d|{DID['d7']}", MJ_USTA) or {}).get("holat") == "kutilmoqda"
os.environ["DOKON_BOT_TOKEN"] = BOT_TOKEN
xavfsiz(lambda: main.dokon_kutish_ish())
_d = botga(9201, n0)
check("T15 main.dokon_kutish_ish: bot tokeni yo'q — hech narsa; bor — do'kon boti (token bilan) orqali xabar, holat «yuborildi»",
      _a and len(_d) == 1 and _d[0][3] == BOT_TOKEN and "Gul" in _d[0][1] and _d[0][2] is not None
      and (qator(f"d|{DID['d7']}", MJ_USTA) or {}).get("holat") == "yuborildi", (_a, _d))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Admin ro'yxati")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
J0 = js(CA.get(API + "/kutishlar"))
check("D0 hamma kutish kelgan — ro'yxat bo'sh; yig'indi: so'nggi 30 kunda yuborilgan 5, yetmagan 1, bo'lim ochiq, tekshiruv 5 daqiqa",
      J0.get("mahsulotlar") == [] and J0.get("kutayotgan") == 0 and J0.get("yuborilgan") == 5 and J0.get("xato") == 1
      and J0.get("tarix_kun") == 30 and J0.get("tayyor_ochiq") is True and J0.get("tekshiruv_daqiqa") == 5, J0)
fp_miqdor(FP["k20b"], 0)
for _ss in (S_USTA, S_MAG, S_YANGI):
    dok(KT, EK20, sessiya=_ss)
r = CA.get(API + "/kutishlar")
J = js(r)
_mh = {g.get("kalit"): g for g in J.get("mahsulotlar") or []}
_g = _mh.get(K_K20) or {}
check("D1 admin: K-20 — 3 kishi (birinchi — ko'p kutilgani), holat «tugagan», qoldiq 0; kim — ism / magazin nomi, telefon, turi, shahar",
      r.status_code == 200 and (J.get("mahsulotlar") or [{}])[0].get("kalit") == K_K20 and _g.get("n") == 3 and _g.get("holat") == "tugagan"
      and _g.get("soni") == 0 and _g.get("nom") == "K-20 Tekis · 20 sm"
      and sorted(k.get("ism") or "" for k in _g.get("kutayotganlar") or [])[:2] == ["Azizbek usta", "Qurilish dunyosi"]
      and sorted(k.get("ism") or "" for k in _g.get("kutayotganlar") or [])[2].startswith("Yangi")
      and any(k.get("telefon") and k.get("turi_nomi") == "Qurilish magazini" and k.get("shahar") == "Asaka" for k in _g.get("kutayotganlar") or []),
      (r.status_code, J))
check("D2 yig'indi: 3 kutish; qayta bosilganlari endi «yuborilgan» / «yetmagan» da sanalmaydi (2 / 0 qoldi)",
      J.get("kutayotgan") == 3 and J.get("yuborilgan") == 3 and J.get("xato") == 0, J)
fp_miqdor(FP["k20b"], 5)
_g = {g.get("kalit"): g for g in js(CA.get(API + "/kutishlar")).get("mahsulotlar") or []}.get(K_K20) or {}
CA.put(API + f"/detallar/{DID['k20']}/tm", json={"tm_kaliti": None})
_g2 = {g.get("kalit"): g for g in js(CA.get(API + "/kutishlar")).get("mahsulotlar") or []}.get(K_K20) or {}
n0 = len(BOT)
st = tekshir()
bogla(DID["k20"], "Karniz K-20")
check("D3 holat: kelgan — «omborda» (soni 5); ombor bog'lami uzilsa — «saytda_yoq», nom NUSXADAN, tekshiruv xabar YUBORMAYDI",
      _g.get("holat") == "omborda" and _g.get("soni") == 5 and _g2.get("holat") == "saytda_yoq" and _g2.get("soni") is None
      and _g2.get("nom") == "K-20 Tekis · 20 sm" and st.get("yuborildi") == 0 and len(BOT) == n0, (_g, _g2, st))
fp_miqdor(FP["d7"], 0.3)
dok(KT, ED7, sessiya=S_USTA)                               # «D-7 …» alifboda K-20 dan OLDIN, lekin 1 kishi kutadi
_tr = [g.get("kalit") for g in js(CA.get(API + "/kutishlar")).get("mahsulotlar") or []]
dok(KTB, {"kalit": f"d|{DID['d7']}"}, sessiya=S_USTA)
fp_miqdor(FP["d7"], 4)
check("D3b tartib — ko'p kutilgani birinchi (alifbo emas): K-20 (3) → D-7 (1)", _tr == [K_K20, f"d|{DID['d7']}"], _tr)
_r = [CM.get(API + "/kutishlar").status_code, NC.get(API + "/kutishlar", follow_redirects=False).status_code]
_jb = js(CB.get(API + "/kutishlar"))
check("D4 menejer — 403, kirmagan — 401 / 303; B korxonasi admini — A ning kutishlari YO'Q",
      _r[0] == 403 and _r[1] in (401, 303) and _jb.get("mahsulotlar") == [] and _jb.get("kutayotgan") == 0, (_r, _jb))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. Brauzer (HAQIQIY Chromium) — «🔔 Kelganda xabar bering» bo'limi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    print("  (PG rejimida brauzer bo'limi o'tkaziladi — SQLite / TF1 da)")
else:
    # yangi model (nomida HTML) — ikki yangi hisob kutadi; K-20 (3 kishi, omborda) ham ro'yxatda
    _m = model(KAR, "K-30", nom="<b>Qalin</b>")
    _d = detal(_m, "asosiy", "30 sm", narx=70000, eni_sm=30, qalinligi_sm=8)
    fp("Karniz K-30 30 sm", 0.3, w=30, t=8)
    bogla(_d, "Karniz K-30")
    _su = kirib_ol(9301, "998901113301", ism="Ulug'bek")
    dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "<i>Ulug'bek</i> usta"}, sessiya=_su)
    _sm = kirib_ol(9302, "998901113302", ism="Sardor")
    _ru = [dok(KT, {"tur": "d", "detal_id": _d}, sessiya=_su).status_code, dok(KT, {"tur": "d", "detal_id": _d}, sessiya=_sm).status_code]
    try:
        from playwright.sync_api import sync_playwright
        import uvicorn
        so = socket.socket()
        so.bind(("127.0.0.1", 0))
        port = so.getsockname()[1]
        so.close()
        server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
        threading.Thread(target=server.run, daemon=True).start()
        for _ in range(150):
            if server.started:
                break
            time.sleep(0.1)
        BU = f"http://127.0.0.1:{port}"
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            try:
                for _w in (1366, 390):
                    ctx = br.new_context(viewport={"width": _w, "height": 900})
                    pg = ctx.new_page()
                    JSX = []
                    pg.on("pageerror", lambda e: JSX.append(str(e)))
                    pg.goto(BU + "/login")
                    pg.fill("input[name=username]", "t252_admin")
                    pg.fill("input[name=password]", PAROL)
                    pg.click("button[type=submit]")
                    pg.wait_for_load_state("networkidle")
                    pg.goto(BU + "/sayt-katalogi", wait_until="networkidle")
                    pg.wait_for_function("document.querySelectorAll('#skKtRoyxat .sk-kt-mahsulot').length > 0", timeout=10000)
                    pg.evaluate("document.querySelector('[data-sht=\"sk-kt\"]').open = true")
                    _u = pg.evaluate("""() => { const b = Array.from(document.querySelectorAll('#skKtRoyxat .sk-kt-mahsulot'));
                        const q = b.filter(x => x.textContent.indexOf('K-30') >= 0)[0], k = document.getElementById('skKt');
                        return {holat: document.getElementById('skKtHolatQisqa').textContent, nom: q.querySelector('.sk-kt-bosh b').textContent,
                                teg: q.querySelector('.sk-kt-bosh b b, li i') !== null, matn: q.textContent, dh: q.dataset.holat,
                                birinchi: b[0].textContent, bh: b[0].dataset.holat, jami: document.querySelector('#skKtRoyxat .sk-kt-jami').textContent,
                                kenglik: k.scrollWidth, oyna: k.clientWidth}; }""")
                    check(f"U1 ({_w} px) bo'lim: sarlavhada «5 ta kutish»; birinchi — K-20 (3 kishi, «Omborda: 5 metr»); K-30 — nomi va ismdagi HTML "
                          "MATN, «2 kishi kutmoqda», «Tugagan», telefon; kartochkada gorizontal toshish yo'q; JS xatosi yo'q",
                          _ru == [200, 200] and _u["holat"] == "5 ta kutish" and "K-20 Tekis · 20 sm" in _u["birinchi"]
                          and "3 kishi kutmoqda" in _u["birinchi"] and "Omborda: 5 metr" in _u["birinchi"] and _u["bh"] == "omborda"
                          and _u["nom"] == "K-30 <b>Qalin</b> · 30 sm" and not _u["teg"] and "2 kishi kutmoqda" in _u["matn"]
                          and "Tugagan" in _u["matn"] and "<i>Ulug'bek</i> usta" in _u["matn"] and "+998 90 111 33 01" in _u["matn"]
                          and _u["dh"] == "tugagan" and "xabar yuborildi: 2" in _u["jami"] and _u["kenglik"] <= _u["oyna"] and not JSX,
                          (_ru, _u, JSX))
                    ctx.close()
            finally:
                br.close()
        server.should_exit = True
    except Exception as _e:                        # noqa: BLE001
        check("U0 brauzer sinovi ishga tushdi", False, f"{type(_e).__name__}: {_e}")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Mustaqil tekshiruv (review252) tuzatishlari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
K_D7 = f"d|{DID['d7']}"
fp_miqdor(FP["k20b"], 0)                                   # K-20 yana tugadi — 3 ta ESKI kutish (omborda yo'q)
fp_miqdor(FP["d7"], 0.3)
dok(KT, ED7, sessiya=S_MAG)                                # ENG YANGI kutish
fp_miqdor(FP["d7"], 4)
_eski_p = getattr(crud, "DOKON_KUTISH_PARTIYA", 300)
crud.DOKON_KUTISH_PARTIYA = 1
n0 = len(BOT)
st = tekshir()
crud.DOKON_KUTISH_PARTIYA = _eski_p
check("R1 (H1) partiya — FAQAT kelgan elementlar kutishlaridan: eski (tugagan) kutishlar ko'p bo'lsa ham yangi kelgani yuboriladi",
      st.get("yuborildi") == 1 and [x[0] for x in BOT[n0:]] == ["9202"] and (qator(K_D7, MJ_MAG) or {}).get("holat") == "yuborildi"
      and (qator(K_K20, MJ_USTA) or {}).get("holat") == "kutilmoqda", (st, BOT[n0:]))
fp_miqdor(FP["d7"], 0.3)
dok(KT, ED7, sessiya=S_USTA)
fp_miqdor(FP["d7"], 4)
_bk = []


def _bekor_paytida(chat, matn, tugma):
    _bk.append(dok(KTB, {"kalit": K_D7}, sessiya=S_USTA).status_code)
    return False


st = tekshir(yubor=_bekor_paytida)
check("R2 (M1) xabar yuborilayotganda bekor qilindi (200) — xabar yetmasa ham qayta navbatga TUSHMAYDI («bekor» qoladi)",
      _bk == [200] and (qator(K_D7, MJ_USTA) or {}).get("holat") == "bekor" and st.get("qayta") == 0, (_bk, st, qator(K_D7, MJ_USTA)))
fp_miqdor(FP["d7"], 0.3)
for _ss in (S_MAG, S_YANGI):
    dok(KT, ED7, sessiya=_ss)
fp_miqdor(FP["d7"], 4)
_tx = []


def _toxta(chat, matn, tugma):
    _tx.append(chat)
    raise crud.DokonKutishToxta("Telegram ishlamayapti")


st = tekshir(yubor=_toxta) if hasattr(crud, "DokonKutishToxta") else {}
_qm, _qy = qator(K_D7, MJ_MAG) or {}, qator(K_D7, MJ_YANGI) or {}
check("R3 (M2) Telegram umuman ishlamayapti — tekshiruv birinchi xabardayoq TO'XTADI, urinish SANALMADI, ikkala kutish «kutilmoqda»",
      st.get("toxtadi") == 1 and len(_tx) == 1 and _qm.get("holat") == "kutilmoqda" and _qy.get("holat") == "kutilmoqda"
      and _qm.get("urinish") == 0 and _qy.get("urinish") == 0 and _qm.get("xabar") is None, (st, _tx, _qm, _qy))
_eski_x = getattr(crud, "dokon_kutish_xabari", lambda x, sayt=None: ("", None))
_xs = []


def _xabar_xato(x, sayt=None):
    _xs.append(1)
    if len(_xs) == 1:
        raise RuntimeError("bitta yomon kutish")
    return _eski_x(x, sayt)


crud.dokon_kutish_xabari = _xabar_xato
n0 = len(BOT)
st = tekshir()
crud.dokon_kutish_xabari = _eski_x
_birinchi = sorted([(qator(K_D7, MJ_MAG) or {}).get("holat") or "", (qator(K_D7, MJ_YANGI) or {}).get("holat") or ""])
n1 = len(BOT)
st2 = tekshir(hozir=_SoxtaVaqt.t + timedelta(minutes=31))
check("R4 (L4) bitta kutishda kutilmagan xato — qolgani yuborildi; xatolisi «yuborilmoqda» da qoladi va 30 daqiqadan keyin qayta yuboriladi",
      st.get("yuborildi") == 1 and n1 - n0 == 1 and _birinchi == ["yuborildi", "yuborilmoqda"] and st2.get("tiklandi") == 1
      and st2.get("yuborildi") == 1 and len(BOT) - n1 == 1, (st, st2, _birinchi))


def _null_qotgan(d):
    r = d.query(DokonKutish).filter(DokonKutish.company_id == 1, DokonKutish.mijoz_id == MJ_YANGI, DokonKutish.kt_kalit == K_D7).first()
    r.kt_holat, r.kt_xabar_vaqti = "yuborilmoqda", None
    return True


bazadan(_null_qotgan)
st = tekshir()
check("R5 (L5) «yuborilmoqda» + xabar vaqti yo'q — qayta navbatga (darhol)", st.get("tiklandi") == 1, st)
_k1 = xavfsiz(lambda: crud._dokon_kutish_k_kalit(1, "rom", True, "ß" * 40), "")
_k2 = xavfsiz(lambda: crud._dokon_kutish_k_kalit(1, "rom", True, "ß" * 39 + "s"), "")
check("R6 (L5) juda uzun o'lcham kaliti (casefold «ß» → «ss») — 120 belgidan oshmaydi, barqaror, boshqasidan farqli",
      0 < len(_k1) <= 120 and _k1 == xavfsiz(lambda: crud._dokon_kutish_k_kalit(1, "rom", True, "ß" * 40)) and _k1 != _k2 and len(_k2) <= 120,
      (_k1, _k2))
# M3: detal / model o'chirilsa — kutishlari bekor; detal kutishi boshqa modelga o'tib qolgan bo'lsa — xabar YO'Q
M40 = model(KAR, "K-40", nom="O'chiriladi")
D40 = detal(M40, "asosiy", "40 sm", narx=80000, eni_sm=40, qalinligi_sm=8)
M41 = model(KAR, "K-41", nom="Model o'chadi")
D41 = detal(M41, "asosiy", "41 sm", narx=81000, eni_sm=41, qalinligi_sm=8)
fp("Karniz K-40 40 sm", 0.2, w=40, t=8)
fp("Karniz K-41 41 sm", 0.2, w=41, t=8)
bogla(D40, "Karniz K-40")
bogla(D41, "Karniz K-41")
_r = [dok(KT, {"tur": "d", "detal_id": D40}, sessiya=S_USTA).status_code, dok(KT, {"tur": "d", "detal_id": D41}, sessiya=S_USTA).status_code]
_o = [CA.delete(API + f"/detallar/{D40}").status_code, CA.delete(API + f"/modellar/{M41}").status_code]
check("R7 (M3) detal / model o'chirildi — ularning kutishlari «bekor» (kabinet ro'yxatida yo'q, 30 talik chegarani band qilmaydi)",
      _r == [200, 200] and _o == [200, 200] and (qator(f"d|{D40}", MJ_USTA) or {}).get("holat") == "bekor"
      and (qator(f"d|{D41}", MJ_USTA) or {}).get("holat") == "bekor"
      and not any(x.get("kalit") in (f"d|{D40}", f"d|{D41}") for x in kutishlar(S_USTA) or []), (_r, _o))
fp_miqdor(FP["d7"], 0.3)
dok(KT, ED7, sessiya=S_YANGI)
fp_miqdor(FP["d7"], 4)


def _model_ozgar(mid_):
    def f(d):
        r = d.query(DokonKutish).filter(DokonKutish.company_id == 1, DokonKutish.mijoz_id == MJ_YANGI, DokonKutish.kt_kalit == K_D7).first()
        r.model_id = mid_
        return True
    return bazadan(f)


_model_ozgar(MK)
n0 = len(BOT)
st = tekshir()
_a = (qator(K_D7, MJ_YANGI) or {}).get("holat")
_model_ozgar(MD)
st2 = tekshir()
check("R8 (M3) detal kutishi — boshqa model detali bo'lib qolgan (raqam qayta berilgan) — xabar YO'Q; o'z modeli — xabar",
      st.get("yuborildi") == 0 and _a == "kutilmoqda" and st2.get("yuborildi") == 1 and len(botga(9203, n0)) == 1, (st, st2, _a))
import urllib.error as _ue                                                                     # noqa: E402
_eski_post = main._tg_post_message
_nat = []
for _kod in (400, 403, 401, 404, 429, 500, 502):
    def _p(token, chat_id, text, reply_markup=None, _k=_kod):
        raise _ue.HTTPError("https://api.telegram.org/x", _k, "sinov", {}, None)
    main._tg_post_message = _p
    try:
        _nat.append((_kod, main._dokon_kutish_yubor("9201", "x", None)))
    except Exception as _e:                                                                    # noqa: BLE001
        _nat.append((_kod, type(_e).__name__))


def _tarmoq(token, chat_id, text, reply_markup=None):
    raise _ue.URLError("ulanish yo'q")


main._tg_post_message = _tarmoq
try:
    _nat.append(("tarmoq", main._dokon_kutish_yubor("9201", "x", None)))
except Exception as _e:                                                                        # noqa: BLE001
    _nat.append(("tarmoq", type(_e).__name__))
main._tg_post_message = _eski_post
os.environ.pop("DOKON_BOT_TOKEN", None)
try:
    _nat.append(("token", main._dokon_kutish_yubor("9201", "x", None)))
except Exception as _e:                                                                        # noqa: BLE001
    _nat.append(("token", type(_e).__name__))
os.environ["DOKON_BOT_TOKEN"] = BOT_TOKEN
_ok = xavfsiz(lambda: main._dokon_kutish_yubor("9201", "x", None))
check("R9 (M2) yuborish: chatga bog'liq rad (400, 403) — False (urinish sanaladi); token / chegara / Telegram / tarmoq / token yo'q — "
      "DokonKutishToxta (to'xtaydi); muvaffaqiyat — True",
      _nat == [(400, False), (403, False), (401, "DokonKutishToxta"), (404, "DokonKutishToxta"), (429, "DokonKutishToxta"),
               (500, "DokonKutishToxta"), (502, "DokonKutishToxta"), ("tarmoq", "DokonKutishToxta"), ("token", "DokonKutishToxta")]
      and _ok is True, (_nat, _ok))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Ikkinchi korxona, zaxira, tiklash, o'chirish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = [dok(KT, sessiya=S_USTA, kalit=KALIT_B, usul="get").status_code, dok(KT, EK20, sessiya=S_USTA, kalit=KALIT_B).status_code,
      dok(KTB, {"kalit": K_K20}, sessiya=S_USTA, kalit=KALIT_B).status_code]
check("Z1 B korxonasi kaliti + A sessiyasi — 401 (hisob boshqa korxonada); A ning yozuvlari o'zgarmadi",
      _r == [401, 401, 401] and kutish_soni(cid=2) == 0 and (qator(K_K20, MJ_USTA) or {}).get("holat") == "kutilmoqda", _r)
_n = bazadan(lambda d: crud.dokon_kutish_holati(d, 2)) or {}
check("Z2 B korxonasi «Tayyor»ida A ning detallari YO'Q (kalit bo'yicha ham)", K_K20 not in _n and K_R1 not in _n, list(_n)[:5])
_bk = bazadan(lambda d: crud.export_full_backup(d, company_id=1)) or {}
_zt = (_bk.get("tables") or {}).get("dokon_kutishlar") or []
_oldin = bazadan(lambda d: sorted((r.mijoz_id, r.kt_kalit, r.kt_holat, r.kt_nom, r.kt_urinish) for r in d.query(DokonKutish)
                                  .filter(DokonKutish.company_id == 1).all()))
check("Z3 zaxirada dokon_kutishlar BOR (hamma qatorlar)", len(_zt) == len(_oldin or []) and len(_zt) >= 8, (len(_zt), len(_oldin or [])))
_res = bazadan(lambda d: crud.import_full_backup(d, _bk, company_id=1, replace=True)) or {}
_keyin = bazadan(lambda d: sorted((r.mijoz_id, r.kt_kalit, r.kt_holat, r.kt_nom, r.kt_urinish) for r in d.query(DokonKutish)
                                  .filter(DokonKutish.company_id == 1).all()))
check("Z4 zaxiradan tiklash — kutishlar AYNAN qaytdi (hisobga bog'lami bilan), o'tkazib yuborilmadi",
      _res.get("success") is True and "dokon_kutishlar" not in (_res.get("skipped_tables") or []) and _keyin == _oldin, (_res, _keyin))
bazadan(lambda d: crud.factory_reset_all_data(d, company_id=1))
check("Z5 korxona ma'lumotlarini o'chirish — kutishlar ham o'chdi (hisoblar bilan)",
      bazadan(lambda d: (d.query(DokonKutish).filter(DokonKutish.company_id == 1).count(),
                         d.query(DokonMijoz).filter(DokonMijoz.company_id == 1).count())) == (0, 0), "")

if PG_URL:
    try:
        import database as _dbm252
        _dbm252.engine.dispose()
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
