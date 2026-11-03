#!/usr/bin/env python3
"""
test_dokon_kirish248.py — kech181 (zip 248: do'kon — usta / magazin Telegram orqali kirish va ro'yxat; do'kon 2-bosqich, ERP tomoni).

NIMA UCHUN KERAK
  Egasi QARORLARI («Onlayn do'kon rejasi» 30.10): kirish parol / SMS siz — Telegram orqali (@penodecorprobot, «Raqamni yuborish» —
  telefon Telegram akkauntidan); birinchi kirishda usta yoki magazin tanlanadi; egasi tasdiqlaydi (usta — KPI % SHART, ERP ustasiga
  bog'lanadi); tasdiq / rad — bot xabari. Asl kodda (zip 247) bu yo'llar umuman YO'Q — test yiqiladi (qulamaydi).
BO'LIMLAR
  K — kirishni boshlash (kod / sir / havola, sayt manzili, kalit). W — do'kon boti webhooki (sir, /start k_…, kontakt, begona / xorijiy
  raqam, eskirgan, guruh chati). H — kirish holati (tayyor — BIR marta sessiya). M — mijoz sessiyasi va ro'yxat. A — admin tasdiq / rad /
  bloklash / blokdan chiqarish (usta — mavjud yoki yangi ERP ustasi, KPI %). B — do'kon boti holati va ulash (boshqa manzil — 409,
  majburiy — faqat production). Z — zaxira / xeshlar.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
ISHLATISH: python3 tools/test_dokon_kirish248.py
"""
import os
import io
import re
import sys
import json
import time
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"kirish248_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t248_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't248.db')}"
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
BOT_TOKEN = "123456789:AAHsinov248_" + "q" * 24
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
_c1.name = "T248 Penodekor"
s.add(Company(id=2, name="T248 Begona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t248_admin", PAROL, UserRole.ADMIN, "T248 Admin", company_id=1)
    auth.create_user(s, "t248_plat", PAROL, UserRole.ADMIN, "T248 Platforma", company_id=1)
    auth.create_user(s, "t248_b", PAROL, UserRole.ADMIN, "T248 B", company_id=2)
    auth.create_user(s, "t248_men", PAROL, UserRole.MANAGER, "T248 Menejer", company_id=1)
s.query(User).filter(User.username == "t248_plat").first().is_platform_admin = True
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


CA = mijoz("t248_admin")
CP = mijoz("t248_plat")
CB = mijoz("t248_b")
CM = mijoz("t248_men")
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
section("K. Kirishni boshlash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("K0 sinov tayyorgarligi: do'kon kaliti bor, jadvallar bor", KALIT.startswith("pdk_") and DokonMijoz is not None
      and DokonKirish is not None and DokonSessiya is not None, (KALIT[:6], DokonMijoz))
r = dok("/api/dokon/v1/kirish", {})
check("K1 do'kon boti tokeni yo'q — 503, «qo'ng'iroq qiling», no-store", r.status_code == 503 and "qo'ng'iroq" in str(js(r).get("detail"))
      and r.headers.get("cache-control") == "no-store", (r.status_code, r.text[:200]))
os.environ["DOKON_BOT_TOKEN"] = "noto'g'ri token"
r = dok("/api/dokon/v1/kirish", {})
check("K1b token ko'rinishi noto'g'ri — sozlanmagan deb olinadi (503), Telegram'ga so'rov ketmaydi",
      r.status_code == 503 and not TGCHAQ, (r.status_code, TGCHAQ[:2]))
os.environ["DOKON_BOT_TOKEN"] = BOT_TOKEN
r = dok("/api/dokon/v1/kirish", {"sayt": "https://Dokon.Example.uz/"})
K = js(r)
K_KOD, K_SIR = (K.get("kod") if isinstance(K.get("kod"), str) else "Q" * 32), (K.get("sir") if isinstance(K.get("sir"), str) else "R" * 43)
check("K2 kirish: 200, kod (32) / sir (43), muddat 600 s, bot nomi, havola t.me/<bot>?start=k_<kod>, no-store",
      r.status_code == 200 and re.fullmatch(r"[A-Za-z0-9_-]{32}", K.get("kod") or "") and re.fullmatch(r"[A-Za-z0-9_-]{43}", K.get("sir") or "")
      and K.get("muddat_soniya") == 600 and K.get("bot") == "penodecor_sinov_bot"
      and K.get("havola") == f"https://t.me/penodecor_sinov_bot?start=k_{K.get('kod')}" and r.headers.get("cache-control") == "no-store",
      (r.status_code, K))
check("K3 bazada xom kod / sir YO'Q — faqat SHA-256 xeshlar; sayt manzili saqlandi (kichik harf, yo'lsiz)",
      bazadan(lambda d: [(x.kr_kod_xesh, x.kr_sir_xesh) for x in d.query(DokonKirish).all()]) ==
      [(xesh(K.get("kod", "")), xesh(K.get("sir", "")))]
      and bazadan(lambda d: crud.get_setting(d, "dokon_sayt_url", None, company_id=1)) == "https://dokon.example.uz", K)
_rs = [dok("/api/dokon/v1/kirish", {"sayt": x}).status_code for x in
       ("http://dokon.uz", "https://dokon.uz/yol", "https://a@dokon.uz", "https://dokon.uz?x=1", "javascript:alert(1)", 5)]
check("K4 noto'g'ri sayt manzili (http, yo'l, foydalanuvchi, so'rov, javascript, son) — 400", _rs == [400] * 6, _rs)
r = dok("/api/dokon/v1/kirish", {"boshqa": 1})
check("K5 ortiqcha maydon — 400", r.status_code == 400, r.status_code)
_rk = [dok("/api/dokon/v1/kirish", {}, kalit="").status_code, dok("/api/dokon/v1/kirish", {}, kalit="pdk_" + "x" * 43).status_code]
check("K6 kalitsiz / noto'g'ri kalit — 401", _rk == [401, 401], _rk)
chek_tozala()
_h = {"X-Dokon-Kalit": KALIT, "Content-Type": "application/json"}
_rl = [NC.post("/api/dokon/v1/kirish", content=b"{}", headers=_h).status_code for _ in range(KIRISH_MAX + 1)]
check(f"K7 kalitga daqiqasiga {KIRISH_MAX} ta kirish — keyingisi 429", _rl[:-1].count(200) == len(_rl) - 1 and _rl[-1] == 429,
      (_rl.count(200), _rl[-1]))
chek_tozala()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Kirish holati (bot ochilmasdan)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = dok("/api/dokon/v1/kirish/holat", {"kod": K.get("kod"), "sir": K.get("sir")})
check("H1 hali bot ochilmagan — «kutilmoqda», telegram_ochildi false, no-store", r.status_code == 200
      and js(r) == {"holat": "kutilmoqda", "telegram_ochildi": False} and r.headers.get("cache-control") == "no-store", (r.status_code, r.text))
_rh = [dok("/api/dokon/v1/kirish/holat", t) for t in (
    {"kod": K.get("kod"), "sir": "A" * 43}, {"kod": "B" * 32, "sir": K.get("sir")}, {"kod": K_KOD[:-1], "sir": K_SIR},
    {"kod": 1, "sir": 2}, {"kod": K.get("kod"), "sir": K.get("sir"), "x": 1})]
check("H2 noto'g'ri sir / kod / shakl — 404 «Kirish topilmadi» (bir xil); ortiqcha maydon — 400",
      [x.status_code for x in _rh] == [404, 404, 404, 404, 400] and len({x.text for x in _rh[:4]}) == 1, [(x.status_code, x.text[:60]) for x in _rh])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("W. Do'kon boti webhooki")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
U1 = 700001
_w = [tg(xabar(U1, text="/start"), sir="").status_code, tg(xabar(U1, text="/start"), sir="x" * 64).status_code,
      tg(xabar(U1, text="/start"), sir=main.TELEGRAM_WEBHOOK_SECRET or "usta-boti-siri").status_code]
check("W1 sirsiz / noto'g'ri sir / usta botining siri — 403, bot javob bermaydi", _w == [403, 403, 403] and not BOT, (_w, BOT[:1]))
os.environ.pop("DOKON_BOT_TOKEN")
r = tg(xabar(U1, text="/start"))
check("W1b token yo'q — 503", r.status_code == 503, r.status_code)
os.environ["DOKON_BOT_TOKEN"] = BOT_TOKEN
r = tg(xabar(U1, text="/start"))
_b = oxirgi_bot(U1)
check("W2 oddiy /start — salom va «🛒 Saytni ochish» tugmasi (sayt manzili), javob do'kon boti tokeni bilan",
      r.status_code == 200 and _b and "T248 Penodekor rasmiy boti" in _b[1] and _b[2] == {"inline_keyboard": [[{"text": "🛒 Saytni ochish",
                                                                                                  "url": "https://dokon.example.uz"}]]}
      and _b[3] == BOT_TOKEN, _b)
BOT.clear()
tg(xabar(U1, text=f"/start k_{K.get('kod')}", turi="group", chat_id=-100))
tg(xabar(U1, text=f"/start k_{K.get('kod')}", chat_id=U1 + 1))
check("W3 guruh chati / chat ≠ yuboruvchi — e'tiborsiz (javob yo'q, holat o'zgarmadi)", not BOT
      and js(dok("/api/dokon/v1/kirish/holat", {"kod": K.get("kod"), "sir": K.get("sir")})).get("telegram_ochildi") is False, BOT)
tg(xabar(U1, text=f"/start k_{K.get('kod')}", turi="supergroup"))
tg(xabar(U1, text=f"/start k_{K.get('kod')}", turi="channel"))
check("W3b guruh / kanal turi (chat raqami yuboruvchiniki bilan bir xil bo'lsa ham) — e'tiborsiz", not BOT
      and js(dok("/api/dokon/v1/kirish/holat", {"kod": K.get("kod"), "sir": K.get("sir")})).get("telegram_ochildi") is False, BOT)
tg(xabar(U1, text=f"/start k_{K.get('kod')}"))
_b = oxirgi_bot(U1)
check("W4 /start k_<kod> — «Raqamni yuborish» tugmasi (request_contact), ogohlantirish matni; holat — telegram_ochildi true",
      _b and "Raqamni yuborish" in _b[1] and "boshlamagan" in _b[1] and _b[2] and _b[2].get("keyboard") == [[{"text": "📱 Raqamni yuborish",
                                                                                                           "request_contact": True}]]
      and js(dok("/api/dokon/v1/kirish/holat", {"kod": K.get("kod"), "sir": K.get("sir")})) == {"holat": "kutilmoqda", "telegram_ochildi": True},
      _b)
tg(xabar(U1, contact=kontakt(U1, "+998 90 111 22 33", egasi=U1 + 5)))
_b = oxirgi_bot(U1)
check("W5 boshqa odamning kontakti (user_id ≠ from.id) — rad, tugma qayta; hisob ochilmadi", _b and "o'zingizning" in _b[1]
      and _b[2] and _b[2].get("keyboard") and bazadan(lambda d: d.query(DokonMijoz).count()) == 0, _b)
tg(xabar(U1, contact=kontakt(U1, "+7 900 123 45 67")))
_b = oxirgi_bot(U1)
check("W6 O'zbekiston raqami emas (+7) — rad («+998»), hisob ochilmadi", _b and "+998" in _b[1] and bazadan(lambda d: d.query(DokonMijoz).count()) == 0,
      _b)
tg(xabar(U1, contact=kontakt(U1, "998901112233")))
_b = ([x for x in BOT if x[0] == str(U1)][-2:] or [None])[0]
_m = bazadan(lambda d: [(x.mj_tg_id, x.mj_telefon, x.mj_tg_ism, x.mj_holat, x.mj_turi) for x in d.query(DokonMijoz).all()])
check("W7 o'z kontakti — «qabul qilindi», tugma yopildi; hisob «yangi», telefon +998901112233, ism Telegramdan",
      _b and "qabul qilindi" in _b[1] and _b[2] == {"remove_keyboard": True}
      and _m == [(str(U1), "+998901112233", "Azizbek Karimov", "yangi", None)], (_b, _m))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Kirish holati — sessiya")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = dok("/api/dokon/v1/kirish/holat", {"kod": K.get("kod"), "sir": K.get("sir")})
H = js(r)
S1 = H.get("sessiya") or ""
check("H3 «tayyor»: sessiya pds_ + 43, mijoz — turi yo'q, holat «yangi», telefon; KPI / ERP ustasi / Telegram raqami YO'Q",
      r.status_code == 200 and H.get("holat") == "tayyor" and re.fullmatch(r"pds_[A-Za-z0-9_-]{43}", S1)
      and set((H.get("mijoz") or {}).keys()) == {"id", "turi", "turi_nomi", "holat", "holat_nomi", "ism", "tg_ism", "telefon",
                                                 "telefon_korinish", "magazin", "shahar", "rad_sababi"}
      and H["mijoz"]["holat"] == "yangi" and H["mijoz"]["turi"] is None and H["mijoz"]["telefon_korinish"] == "+998 90 111 22 33", H)
r = dok("/api/dokon/v1/kirish/holat", {"kod": K.get("kod"), "sir": K.get("sir")})
check("H4 qayta so'rov — «ishlatildi» (ikkinchi sessiya YO'Q); bazada sessiya bitta, faqat xeshi", js(r) == {"holat": "ishlatildi"}
      and bazadan(lambda d: [x.ss_xesh for x in d.query(DokonSessiya).all()]) == [xesh(S1)], (r.text, S1))
# Poyga: ikki so'rov ham «tasdiqlandi» ni o'qiydi — biri sessiyani olgach, ikkinchisi (shartli UPDATE) — «ishlatildi» (ikkinchi sessiya YO'Q)
Kp = js(dok("/api/dokon/v1/kirish", {}))
tg(xabar(U1, text=f"/start k_{Kp.get('kod')}"))
tg(xabar(U1, contact=kontakt(U1, "998901112233")))
_ichki = {}
_asl_cd = crud._hm248.compare_digest if getattr(crud, "_hm248", None) is not None else None


def _poyga_cd(a, b):
    natija = _asl_cd(a, b)
    if not _ichki:
        _ichki["x"] = "boshlandi"
        _d2 = SessionLocal()
        try:
            _ichki["x"] = crud.dokon_kirish_holat(_d2, 1, {"kod": Kp.get("kod"), "sir": Kp.get("sir")}).get("holat")
        finally:
            _d2.close()
    return natija


_sess0 = bazadan(lambda d: d.query(DokonSessiya).count())
if _asl_cd is not None:
    crud._hm248.compare_digest = _poyga_cd
    try:
        _tash = xavfsiz(lambda: bazadan(lambda d: crud.dokon_kirish_holat(d, 1, {"kod": Kp.get("kod"), "sir": Kp.get("sir")}).get("holat")))
    finally:
        crud._hm248.compare_digest = _asl_cd
else:
    _tash = None
check("H4b poyga: parallel ikkinchi so'rov — «ishlatildi», sessiya BITTA qo'shildi", _ichki.get("x") == "tayyor" and _tash == "ishlatildi"
      and bazadan(lambda d: d.query(DokonSessiya).count()) == (_sess0 or 0) + 1, (_ichki, _tash, _sess0))
K2 = js(dok("/api/dokon/v1/kirish", {}))
_SoxtaVaqt.t += timedelta(minutes=11)
tg(xabar(U1, text=f"/start k_{K2.get('kod')}"))
_b = oxirgi_bot(U1)
check("H5 11 daqiqadan keyin: /start — «eskirgan», holat — «muddati_otdi»", _b and "eskirgan" in _b[1]
      and js(dok("/api/dokon/v1/kirish/holat", {"kod": K2.get("kod"), "sir": K2.get("sir")})) == {"holat": "muddati_otdi"}, _b)
_sn6 = bazadan(lambda d: d.query(DokonSessiya).count())
tg(xabar(U1, contact=kontakt(U1, "998901112233")))
_b = oxirgi_bot(U1)
check("H6 ochiq kirishsiz kontakt — «muddati o'tgan», sessiya qo'shilmadi", _b and "muddati o'tgan" in _b[1]
      and bazadan(lambda d: d.query(DokonSessiya).count()) == _sn6, _b)
tg(xabar(U1, text="/start k_" + "Z" * 32))
check("H7 noma'lum kod — «eskirgan»", "eskirgan" in (oxirgi_bot(U1) or ("", ""))[1], oxirgi_bot(U1))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Mijoz sessiyasi va ro'yxat")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = dok("/api/dokon/v1/mijoz", sessiya=S1, usul="get")
check("M1 GET /mijoz (sessiya bilan) — 200, holat «yangi», no-store", r.status_code == 200 and js(r).get("holat") == "yangi"
      and r.headers.get("cache-control") == "no-store", (r.status_code, r.text[:200]))
_rm = [dok("/api/dokon/v1/mijoz", usul="get").status_code, dok("/api/dokon/v1/mijoz", sessiya="pds_" + "x" * 43, usul="get").status_code,
       dok("/api/dokon/v1/mijoz", sessiya=S1[:-1], usul="get").status_code, dok("/api/dokon/v1/mijoz", sessiya=S1, kalit="", usul="get").status_code]
check("M2 sessiyasiz / noto'g'ri / kesilgan sessiya — 401; do'kon kalitisiz — 401", _rm == [401, 401, 401, 401], _rm)
_rr = [dok("/api/dokon/v1/mijoz/royxat", t, sessiya=S1).status_code for t in (
    {"turi": "boshliq", "ism": "Azizbek"}, {"turi": "usta", "ism": "A"}, {"turi": "magazin", "ism": "Azizbek", "shahar": "Asaka"},
    {"turi": "magazin", "ism": "Azizbek", "magazin": "Q", "shahar": "Asaka"}, {"turi": "usta", "ism": "Azizbek", "magazin": "X"},
    {"turi": "usta", "ism": "Azizbek", "x": 1}, {"turi": "usta", "ism": "A\ud800b"}, {"turi": "usta", "ism": "x" * 101})]
check("M3 ro'yxat tekshiruvi: noto'g'ri tur, 1 harfli ism, magazin nomisiz, 1 harfli magazin, ustada magazin, ortiqcha maydon, buzilgan "
      "belgi, 101 belgi — 400", _rr == [400] * 8, _rr)
TG.clear()
r = dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "  Azizbek ​ usta "}, sessiya=S1)
check("M4 usta so'rovi — 200, «kutilmoqda», ism tozalandi; egasiga Telegram (usta, telefon)", r.status_code == 200
      and js(r).get("holat") == "kutilmoqda" and js(r).get("ism") == "Azizbek usta" and len(TG) == 1 and "Usta" in TG[0]
      and "+998 90 111 22 33" in TG[0], (r.status_code, r.text[:200], TG))
r = dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "Azizbek usta"}, sessiya=S1)
check("M5 o'sha so'rov qayta — 200, egasiga qayta xabar YO'Q", r.status_code == 200 and len(TG) == 1, TG)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Admin: tasdiq / rad / bloklash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = CA.get(API + "/mijozlar")
L = js(r)
_x = next((x for x in L.get("mijozlar", []) if x.get("tg_id") == str(U1)), {})
MJ1 = _x.get("id")
check("A1 ro'yxat: 1 kutilmoqda, telefoni mos ERP ustasi taklif qilindi (Bahodir usta, KPI 3); begona korxona ustasi ro'yxatda YO'Q",
      r.status_code == 200 and L.get("kutilmoqda") == 1 and (_x.get("taklif") or {}).get("id") == MASTER1
      and (_x.get("taklif") or {}).get("kpi") == 3.0 and MASTER_B not in [u["id"] for u in L.get("ustalar", [])], L)
check("A1b begona korxona admini — 404 (sayt katalogi yoqilmagan)", CB.get(API + "/mijozlar").status_code == 404, "")
_ra = [CA.post(API + f"/mijozlar/{MJ1}/tasdiqla", json=t).status_code for t in (
    {"master_id": MASTER1}, {"kpi": 0, "master_id": MASTER1}, {"kpi": 101, "master_id": MASTER1}, {"kpi": "abc", "master_id": MASTER1},
    {"kpi": True, "master_id": MASTER1}, {"kpi": 5}, {"kpi": 5, "master_id": MASTER1, "yangi_usta": True},
    {"kpi": 5, "master_id": MASTER_B}, {"kpi": 5, "master_id": 999999}, {"kpi": "nan", "master_id": MASTER1})]
check("A2 tasdiq tekshiruvi: KPI yo'q / 0 / 101 / matn / bool / usta tanlanmagan / ikkalasi / begona usta / yo'q usta / NaN — 400",
      _ra == [400] * 10 and bazadan(lambda d: d.get(DokonMijoz, MJ1).mj_holat) == "kutilmoqda", _ra)
r = CA.post(API + f"/mijozlar/{MJ1}/tasdiqla", json={"kpi": 5, "master_id": MASTER_B})
check("A2b begona korxona ustasi — «Usta topilmadi» (o'z korxonasida qidiriladi), begona usta o'zgarmadi",
      r.status_code == 400 and js(r).get("detail") == "Usta topilmadi" and bazadan(lambda d: d.get(Master, MASTER_B).kpi_percent) == 1.0, r.text)
r = CA.post(API + f"/mijozlar/{MJ1}/tasdiqla", json={"kpi": 5, "yangi_usta": True})
check("A3 shu telefonli usta ERP da bor — «yangi usta» 409 (ikki usta ochilmaydi)", r.status_code == 409
      and bazadan(lambda d: d.query(Master).filter(Master.company_id == 1).count()) == 1, (r.status_code, r.text))
BOT.clear()
r = CA.post(API + f"/mijozlar/{MJ1}/tasdiqla", json={"kpi": "7,5", "master_id": MASTER1})
_u = bazadan(lambda d: (d.get(Master, MASTER1).kpi_percent, d.get(Master, MASTER1).telegram_id))
_mm = bazadan(lambda d: (d.get(DokonMijoz, MJ1).mj_holat, d.get(DokonMijoz, MJ1).master_id, d.get(DokonMijoz, MJ1).mj_tasdiqlagan))
_jr = bazadan(lambda d: [x.new_value for x in d.query(models.ActivityLog).filter(models.ActivityLog.entity_type == "dokon_mijoz").all()])
check("A4 mavjud ustaga tasdiq (KPI «7,5») — mijoz «tasdiqlangan», ustaga bog'landi, KPI 3 → 7,5, ustaning Telegram raqami yozildi; jurnal; "
      "mijozga bot xabari", r.status_code == 200 and _u == (7.5, str(U1)) and _mm == ("tasdiqlangan", MASTER1, "T248 Admin")
      and len(_jr) == 1 and "KPI 3 → 7,5" in _jr[0] and any(b[0] == str(U1) and "usta sifatida tasdiqlandingiz" in b[1] for b in BOT),
      (r.status_code, r.text[:200], _u, _mm, _jr, BOT))
check("A5 qayta tasdiq — 409; tasdiqlangan hisob qayta so'rov yubora olmaydi — 409",
      CA.post(API + f"/mijozlar/{MJ1}/tasdiqla", json={"kpi": 5, "master_id": MASTER1}).status_code == 409
      and dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "Azizbek"}, sessiya=S1).status_code == 409, "")
check("A5b do'kon ko'radigan hisob — «tasdiqlangan», usta", js(dok("/api/dokon/v1/mijoz", sessiya=S1, usul="get")).get("holat") == "tasdiqlangan", "")

U2 = 700002
S2, _h2 = kirib_ol(U2, "+998 93 444 55 66", ism="Sardor")
r = dok("/api/dokon/v1/mijoz/royxat", {"turi": "magazin", "ism": "Sardor", "magazin": "«Qurilish dunyosi»", "shahar": "Asaka"}, sessiya=S2)
MJ2 = js(r).get("id")
check("A6 ikkinchi foydalanuvchi — magazin so'rovi «kutilmoqda» (magazin, shahar)", r.status_code == 200 and js(r).get("magazin") == "«Qurilish dunyosi»"
      and js(r).get("shahar") == "Asaka" and S2, (r.status_code, r.text[:200], _h2))
_rmg = CA.post(API + f"/mijozlar/{MJ2}/tasdiqla", json={"kpi": 5}).status_code
BOT.clear()
r = CA.post(API + f"/mijozlar/{MJ2}/tasdiqla", json={})
check("A7 magazin: KPI yuborilsa — 400; bo'sh tasdiq — 200, bot xabari «Ulgurji»", _rmg == 400 and r.status_code == 200
      and any(b[0] == str(U2) and "Ulgurji" in b[1] for b in BOT), (_rmg, r.status_code, BOT))

U3 = 700003
S3, _ = kirib_ol(U3, "+998 94 777 88 99", ism="Jasur")
MJ3 = js(dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "Jasur"}, sessiya=S3)).get("id")
BOT.clear()
r = CA.post(API + f"/mijozlar/{MJ3}/rad", json={"sabab": "Tanimadik"})
check("A8 rad (sabab bilan) — «rad», sessiyalar o'chdi (401), bot xabarida sabab", r.status_code == 200
      and bazadan(lambda d: d.get(DokonMijoz, MJ3).mj_holat) == "rad" and dok("/api/dokon/v1/mijoz", sessiya=S3, usul="get").status_code == 401
      and any(b[0] == str(U3) and "Tanimadik" in b[1] for b in BOT), (r.status_code, BOT))
S3b, H3b = kirib_ol(U3, "+998 94 777 88 99", ism="Jasur")
check("A9 rad etilgan qayta kiradi — holat «rad», sababi ko'rinadi; qayta so'rov — «kutilmoqda», sabab tozalandi",
      (H3b.get("mijoz") or {}).get("holat") == "rad" and (H3b.get("mijoz") or {}).get("rad_sababi") == "Tanimadik"
      and js(dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "Jasur"}, sessiya=S3b)).get("holat") == "kutilmoqda"
      and bazadan(lambda d: d.get(DokonMijoz, MJ3).mj_rad_sababi) is None, H3b)
r = CA.post(API + f"/mijozlar/{MJ3}/tasdiqla", json={"kpi": 4, "yangi_usta": True})
_nu = bazadan(lambda d: [(u.name, u.phone, u.kpi_percent, u.telegram_id) for u in d.query(Master).filter(Master.company_id == 1, Master.id != MASTER1).all()])
check("A10 «yangi usta» — ERP da usta ochildi (ism, telefon, KPI 4, Telegram raqami), hisobga bog'landi", r.status_code == 200
      and _nu == [("Jasur", "+998947778899", 4.0, str(U3))] and bazadan(lambda d: d.get(DokonMijoz, MJ3).master_id) is not None, (r.text[:200], _nu))
U4 = 700004
S4, _ = kirib_ol(U4, "+998 95 000 11 22", ism="Olim")
MJ4 = js(dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "Olim"}, sessiya=S4)).get("id")
r = CA.post(API + f"/mijozlar/{MJ4}/tasdiqla", json={"kpi": 4, "master_id": MASTER1})
check("A11 boshqa hisobga bog'langan usta — 409, hisob «kutilmoqda» qoldi", r.status_code == 409
      and bazadan(lambda d: d.get(DokonMijoz, MJ4).mj_holat) == "kutilmoqda", (r.status_code, r.text))
r = CA.post(API + f"/mijozlar/{MJ2}/blokla")
BOT.clear()
K5 = js(dok("/api/dokon/v1/kirish", {}))
tg(xabar(U2, text=f"/start k_{K5.get('kod')}", ism="Sardor"))
tg(xabar(U2, contact=kontakt(U2, "+998 93 444 55 66", ism="Sardor"), ism="Sardor"))
_hb = js(dok("/api/dokon/v1/kirish/holat", {"kod": K5.get("kod"), "sir": K5.get("sir")}))
check("A12 bloklash — sessiya 401; bot orqali kirmoqchi bo'lsa «yopilgan», sessiya berilmaydi", r.status_code == 200
      and dok("/api/dokon/v1/mijoz", sessiya=S2, usul="get").status_code == 401 and "yopilgan" in (oxirgi_bot(U2) or ("", ""))[1]
      and _hb.get("holat") != "tayyor" and "sessiya" not in _hb, (r.status_code, _hb, oxirgi_bot(U2)))
_rb = [CA.post(API + f"/mijozlar/{MJ2}/blokla").status_code, CA.post(API + f"/mijozlar/{MJ2}/ochish").status_code,
       CA.post(API + f"/mijozlar/{MJ2}/ochish").status_code, CA.post(API + "/mijozlar/999999/blokla").status_code]
check("A13 qayta bloklash — 409; blokdan chiqarish — 200 («kutilmoqda», qayta tasdiq), qayta — 409; yo'q hisob — 404",
      _rb == [409, 200, 409, 404] and bazadan(lambda d: d.get(DokonMijoz, MJ2).mj_holat) == "kutilmoqda", _rb)
check("A14 rad / tasdiq faqat «kutilmoqda» dan: tasdiqlangan hisobni rad etish — 409",
      CA.post(API + f"/mijozlar/{MJ1}/rad", json={}).status_code == 409, "")
_rmn = [CM.get(API + "/mijozlar").status_code, CM.post(API + f"/mijozlar/{MJ4}/tasdiqla", json={"kpi": 4, "yangi_usta": True}).status_code,
        CM.get(API + "/dokon-bot").status_code]
check("A15 Menejer — ro'yxat, tasdiq, bot holati 403; hisob o'zgarmadi", _rmn == [403, 403, 403]
      and bazadan(lambda d: d.get(DokonMijoz, MJ4).mj_holat) == "kutilmoqda", _rmn)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Do'kon boti holati va ulash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = CA.get(API + "/dokon-bot")
B = js(r)
check("B1 holat: token bor (qiymati javobda YO'Q), bot nomi, webhook bo'sh, kutilgan …/telegram/dokon, ulanmagan, sayt manzili",
      r.status_code == 200 and B.get("token_bor") is True and B.get("bot") == "penodecor_sinov_bot" and B.get("webhook") == ""
      and B.get("kutilgan") == "https://testserver/telegram/dokon" and B.get("ulangan") is False and BOT_TOKEN not in r.text
      and B.get("sayt") == "https://dokon.example.uz", B)
TGCHAQ.clear()
r = CA.post(API + "/dokon-bot/ulash", json={})
_sw = [x for x in TGCHAQ if x[1] == "setWebhook"]
check("B2 ulash (bot hech qayerga ulanmagan) — setWebhook: o'z manzili, sir = tokendan, message + callback_query; javob — ulangan",
      r.status_code == 200 and js(r).get("ulangan") is True and len(_sw) == 1 and _sw[0][2] == {
          "url": "https://testserver/telegram/dokon", "secret_token": bot_sir(BOT_TOKEN), "allowed_updates": ["message", "callback_query"],
          "max_connections": 10}, (r.status_code, r.text[:200], _sw))
TGAPI["getWebhookInfo"] = {"url": "https://boshqa.example/hook"}
TGCHAQ.clear()
_rw = [CA.post(API + "/dokon-bot/ulash", json={}).status_code, CA.post(API + "/dokon-bot/ulash", json={"majburiy": True}).status_code]
check("B3 bot boshqa manzilga ulangan, sinov muhiti — oddiy ham, majburiy ham 409, setWebhook YO'Q", _rw == [409, 409]
      and not [x for x in TGCHAQ if x[1] == "setWebhook"], (_rw, TGCHAQ))
os.environ["RAILWAY_ENVIRONMENT_NAME"] = "production"
_rw2 = [CA.post(API + "/dokon-bot/ulash", json={}).status_code, CA.post(API + "/dokon-bot/ulash", json={"majburiy": True}).status_code]
os.environ.pop("RAILWAY_ENVIRONMENT_NAME")
check("B4 production: oddiy — 409 (ogohlantirish), majburiy — 200 (ulandi)", _rw2 == [409, 200]
      and TGAPI["getWebhookInfo"]["url"] == "https://testserver/telegram/dokon", _rw2)
check("B5 ortiqcha maydon — 400", CA.post(API + "/dokon-bot/ulash", json={"x": 1}).status_code == 400, "")
os.environ.pop("DOKON_BOT_TOKEN")
check("B6 token yo'q — holat token_bor false; ulash — 409", js(CA.get(API + "/dokon-bot")).get("token_bor") is False
      and CA.post(API + "/dokon-bot/ulash", json={}).status_code == 409, "")
os.environ["DOKON_BOT_TOKEN"] = BOT_TOKEN

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. Brauzer (HAQIQIY Chromium) — «Usta va magazinlar (saytdan)»")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
U5 = 700005
S5, _ = kirib_ol(U5, "+998 99 123 00 01", ism="Ali")
MJ5 = js(dok("/api/dokon/v1/mijoz/royxat", {"turi": "usta", "ism": "<b>Ali</b> usta"}, sessiya=S5)).get("id")
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
            def kir(w=1366, h=900):
                ctx = br.new_context(viewport={"width": w, "height": h})
                pg = ctx.new_page()
                jsx = []
                pg.on("pageerror", lambda e: jsx.append(str(e)))
                pg.on("dialog", lambda d: d.dismiss())
                pg.goto(BU + "/login")
                pg.fill("input[name=username]", "t248_admin")
                pg.fill("input[name=password]", PAROL)
                pg.click("button[type=submit]")
                pg.wait_for_load_state("networkidle")
                pg.goto(BU + "/sayt-katalogi", wait_until="networkidle")
                return ctx, pg, jsx

            def tasdiq_ok(pg):
                pg.wait_for_selector("#ccModalOk", state="visible", timeout=5000)
                pg.click("#ccModalOk")

            ctx, pg, JSX = kir()
            pg.wait_for_function("document.querySelectorAll('#skMjRoyxat .sk-mj-qator').length > 0", timeout=10000)
            _u1 = pg.evaluate("""() => ({ochiq: document.querySelector('[data-sht="sk-mj"]').open,
                holat: document.getElementById('skMjHolatQisqa').textContent,
                guruh: Array.from(document.querySelectorAll('#skMjRoyxat .sk-mj-guruh')).map(x => x.textContent),
                kut: Array.from(document.querySelectorAll('#skMjRoyxat .sk-mj-qator[data-holat="kutilmoqda"]')).map(x => +x.dataset.mjId)})""")
            check("U1 kartochka: so'rov kutayotgan bo'lsa — o'zi ochiq, sarlavhada soni; guruhlar (kutayotganlar birinchi)",
                  _u1["ochiq"] and _u1["holat"] == "3 ta so'rov kutmoqda" and _u1["guruh"][0] == "Tasdiq kutayotganlar (3)"
                  and sorted(_u1["kut"]) == sorted([MJ2, MJ4, MJ5]) and not JSX, (_u1, JSX))
            _u2 = pg.evaluate(f"""() => {{ const b = document.querySelector('.sk-mj-qator[data-mj-id="{MJ5}"] .sk-mj-bosh b');
                return {{matn: b.textContent, teg: b.querySelector('b') !== null}}; }}""")
            check("U2 ismdagi HTML — MATN sifatida (teg emas)", _u2["matn"] == "<b>Ali</b> usta" and not _u2["teg"], _u2)
            _u3 = pg.evaluate("document.getElementById('skMjBot').textContent")
            check("U3 bot qatori: @bot nomi, boshqa manzilga ulangan, «Botni shu saytga ulash» (sinov muhiti — «Baribir ulash» YO'Q); token "
                  "sahifada YO'Q", "@penodecor_sinov_bot" in _u3 and "boshqa manzilga ulangan" in _u3 and pg.locator("#skMjBotUla").count() == 1
                  and pg.locator("#skMjBotMajburiy").count() == 0 and BOT_TOKEN not in pg.content(), _u3)
            q5 = f'.sk-mj-qator[data-mj-id="{MJ5}"]'
            _tanlov = pg.evaluate(f"document.querySelector('{q5} [data-mj-usta]').value")
            pg.click(f'{q5} [data-mj-amal="tasdiqla"]')
            time.sleep(0.4)
            check("U4 KPI kiritilmagan — tasdiq yuborilmadi (hisob «kutilmoqda»); taklif yo'q — «Yangi usta» tanlangan",
                  _tanlov == "yangi" and bazadan(lambda d: d.get(DokonMijoz, MJ5).mj_holat) == "kutilmoqda", _tanlov)
            pg.fill(f'{q5} [data-mj-kpi]', "6,5")
            pg.click(f'{q5} [data-mj-amal="tasdiqla"]')
            pg.wait_for_function(f"document.querySelector('.sk-mj-qator[data-mj-id=\"{MJ5}\"]').dataset.holat === 'tasdiqlangan'", timeout=10000)
            _u5 = bazadan(lambda d: (d.get(DokonMijoz, MJ5).mj_holat, d.get(Master, d.get(DokonMijoz, MJ5).master_id).kpi_percent,
                                     d.get(Master, d.get(DokonMijoz, MJ5).master_id).name))
            check("U5 «Yangi usta» + KPI «6,5» — tasdiqlandi, ERP ustasi ochildi (KPI 6,5, ism saytdagidek); qator «Tasdiqlanganlar» da",
                  _u5 == ("tasdiqlangan", 6.5, "<b>Ali</b> usta"), _u5)
            q2 = f'.sk-mj-qator[data-mj-id="{MJ2}"]'
            pg.click(f'{q2} [data-mj-amal="tasdiqla"]')
            pg.wait_for_function(f"document.querySelector('.sk-mj-qator[data-mj-id=\"{MJ2}\"]').dataset.holat === 'tasdiqlangan'", timeout=10000)
            check("U6 magazin — bir bosishda tasdiqlandi", bazadan(lambda d: d.get(DokonMijoz, MJ2).mj_holat) == "tasdiqlangan", "")
            q4 = f'.sk-mj-qator[data-mj-id="{MJ4}"]'
            pg.fill(f'{q4} [data-mj-sabab]', "Hujjat yo'q")
            pg.click(f'{q4} [data-mj-amal="rad"]')
            tasdiq_ok(pg)
            pg.wait_for_function(f"document.querySelector('.sk-mj-qator[data-mj-id=\"{MJ4}\"]').dataset.holat === 'rad'", timeout=10000)
            _u7 = pg.evaluate(f"document.querySelector('.sk-mj-qator[data-mj-id=\"{MJ4}\"]').textContent")
            check("U7 rad (sabab bilan, tasdiq oynasi) — «Rad etilganlar», sabab ko'rinadi; serverda sabab saqlangan",
                  "Hujjat yo'q" in _u7 and bazadan(lambda d: d.get(DokonMijoz, MJ4).mj_rad_sababi) == "Hujjat yo'q" and not JSX, (_u7, JSX))
            ctx.close()
            ctx, pg, JSX = kir(390, 844)
            pg.wait_for_function("document.querySelectorAll('#skMjRoyxat .sk-mj-qator').length > 0", timeout=10000)
            pg.evaluate("document.querySelector('[data-sht=\"sk-mj\"]').open = true")
            _u8 = pg.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
                keng: Math.max(...Array.from(document.querySelectorAll('#skMj .sk-mj-qator')).map(x => x.getBoundingClientRect().right))})""")
            check("U8 telefon (390 px): gorizontal toshish yo'q, qatorlar ekran ichida", _u8["sw"] <= _u8["cw"] and _u8["keng"] <= _u8["cw"] + 0.5
                  and not JSX, (_u8, JSX))
            ctx.close()
        finally:
            br.close()
    server.should_exit = True
except Exception as _e:                            # noqa: BLE001
    check("U0 brauzer sinovi oxirigacha yurdi", False, f"{type(_e).__name__}: {_e}")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira, chiqish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_z = bazadan(lambda d: crud.export_full_backup(d, company_id=1)) or {}
_zt = _z.get("tables") or _z
check("Z1 zaxira: dokon_mijozlar BOR; dokon_kirishlar / dokon_sessiyalar YO'Q",
      "dokon_mijozlar" in _zt and "dokon_kirishlar" not in _zt and "dokon_sessiyalar" not in _zt, list(_zt)[:5] if isinstance(_zt, dict) else _zt)
r = dok("/api/dokon/v1/mijoz/chiqish", {}, sessiya=S1)
check("Z2 chiqish — {ok}, sessiya o'chdi (401); qayta chiqish ham {ok}", js(r) == {"ok": True}
      and dok("/api/dokon/v1/mijoz", sessiya=S1, usul="get").status_code == 401
      and js(dok("/api/dokon/v1/mijoz/chiqish", {}, sessiya=S1)) == {"ok": True}, r.text)
_S1z, _ = kirib_ol(U1, "998901112233")
_av = bazadan(lambda d: d.get(DokonMijoz, MJ1).mj_avlod)
_tok_eski = "pds_" + "E" * 43


def _eski_avlod(d):
    d.add(DokonSessiya(company_id=1, mijoz_id=MJ1, ss_xesh=xesh(_tok_eski), ss_avlod=(_av or 0) - 1, created_at=_SoxtaVaqt.t,
                       ss_oxirgi=_SoxtaVaqt.t, ss_muddat=_SoxtaVaqt.t + timedelta(days=30)))
    d.commit()
    return True


check("Z3a avlodi eski sessiya (bloklash / rad dan oldin yaratilgan) — 401; yangi sessiya — 200",
      bazadan(_eski_avlod) is True and dok("/api/dokon/v1/mijoz", sessiya=_tok_eski, usul="get").status_code == 401
      and dok("/api/dokon/v1/mijoz", sessiya=_S1z, usul="get").status_code == 200, _av)
_SoxtaVaqt.t += timedelta(days=31)
check("Z3 31 kundan keyin sessiya yaroqsiz (401)", dok("/api/dokon/v1/mijoz", sessiya=_S1z, usul="get").status_code == 401, "")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Mustaqil tekshiruv (review248) topilmalari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
BOT.clear()
U6, U7 = 700006, 700007
K6 = js(dok("/api/dokon/v1/kirish", {}))
tg(xabar(U6, text=f"/start k_{K6.get('kod')}", ism="Egasi"))
tg(xabar(U7, text=f"/start k_{K6.get('kod')}", ism="Begona"))
_r1 = (oxirgi_bot(U7) or ("", ""))[1]
tg(xabar(U7, contact=kontakt(U7, "+998 90 707 07 07", ism="Begona"), ism="Begona"))
tg(xabar(U6, contact=kontakt(U6, "+998 90 606 06 06", ism="Egasi"), ism="Egasi"))
H6 = js(dok("/api/dokon/v1/kirish/holat", {"kod": K6.get("kod"), "sir": K6.get("sir")}))
check("R1 (M2) havolani ikkinchi odam ochsa — «eskirgan», uning kontakti kirishni egallamaydi; birinchi odam o'z hisobi bilan kiradi",
      "eskirgan" in _r1 and (H6.get("mijoz") or {}).get("telefon") == "+998906060606"
      and bazadan(lambda d: d.query(DokonMijoz).filter(DokonMijoz.mj_tg_id == str(U7)).count()) == 0, (_r1, H6))
S6 = H6.get("sessiya") or ""
_xb = [x for x in BOT if x[0] == str(U6)]
check("R2 (M1) kirishdan keyin — «🚫 Bu men emas» tugmali ogohlantirish (callback dk_chiq)", len(_xb) >= 3
      and _xb[-1][2] == {"inline_keyboard": [[{"text": "🚫 Bu men emas — chiqarish", "callback_data": "dk_chiq"}]]}, _xb[-2:])
K6b = js(dok("/api/dokon/v1/kirish", {}))
tg(xabar(U6, text=f"/start k_{K6b.get('kod')}", ism="Egasi"))
tg(xabar(U6, contact=kontakt(U6, "+998 90 606 06 06", ism="Egasi"), ism="Egasi"))
TGCHAQ.clear()
_cq = {"update_id": 9, "callback_query": {"id": "cq248", "from": {"id": U6, "first_name": "Egasi"}, "data": "dk_chiq",
                                          "message": {"message_id": 5, "chat": {"id": U6, "type": "private"}}}}
r = tg(_cq)
_hb = js(dok("/api/dokon/v1/kirish/holat", {"kod": K6b.get("kod"), "sir": K6b.get("sir")}))
check("R3 (M1) «Bu men emas» — hamma sessiya 401, hali olinmagan tasdiqlangan kirish ham sessiya bermaydi, answerCallbackQuery, jurnal",
      r.status_code == 200 and dok("/api/dokon/v1/mijoz", sessiya=S6, usul="get").status_code == 401 and "sessiya" not in _hb
      and any(x[1] == "answerCallbackQuery" for x in TGCHAQ) and "chiqarildi" in (oxirgi_bot(U6) or ("", ""))[1]
      and bazadan(lambda d: d.query(models.ActivityLog).filter(models.ActivityLog.action == "dokon_chiqarildi").count()) == 1, (_hb, TGCHAQ))
_cq2 = {"update_id": 10, "callback_query": {"id": "cq2", "from": {"id": U6}, "data": "dk_chiq",
                                           "message": {"message_id": 5, "chat": {"id": -100, "type": "group"}}}}
_n = len(BOT)
tg(_cq2)
check("R4 guruhdagi «Bu men emas» — e'tiborsiz", len(BOT) == _n, BOT[_n:])
S6, _ = kirib_ol(U6, "+998 90 606 06 06", ism="Egasi")
K6c = js(dok("/api/dokon/v1/kirish", {}))
tg(xabar(U6, text=f"/start k_{K6c.get('kod')}", ism="Egasi"))
tg(xabar(U6, contact=kontakt(U6, "+998 90 606 06 06", ism="Egasi"), ism="Egasi"))
_t0 = _SoxtaVaqt.t
_SoxtaVaqt.t = _t0 + timedelta(minutes=16)
_h3 = js(dok("/api/dokon/v1/kirish/holat", {"kod": K6c.get("kod"), "sir": K6c.get("sir")}))
_SoxtaVaqt.t = _t0
check("R5 (L3) tasdiqlangan, lekin 15 daqiqadan ortiq olinmagan kirish — «muddati_otdi» (sessiya yo'q)", _h3 == {"holat": "muddati_otdi"}, _h3)
TG.clear()
for _t in ("usta", "magazin", "usta", "magazin", "usta"):
    dok("/api/dokon/v1/mijoz/royxat", {"turi": _t, "ism": "Egasi", **({"magazin": "Dokon", "shahar": "Andijon"} if _t == "magazin" else {})},
        sessiya=S6)
check("R6 (L7) kutilayotgan so'rov turini 5 marta almashtirish — egasiga BITTA xabar", len(TG) == 1, TG)
MJ6 = bazadan(lambda d: d.query(DokonMijoz.id).filter(DokonMijoz.mj_tg_id == str(U6)).scalar())
check("R7 (L1) KPI 0,004 (yaxlitlansa 0) — 400", CA.post(API + f"/mijozlar/{MJ6}/tasdiqla", json={"kpi": 0.004, "yangi_usta": True}).status_code == 400
      and bazadan(lambda d: d.get(DokonMijoz, MJ6).mj_holat) == "kutilmoqda", "")
# M3: tasdiqlangan usta (MJ1, MASTER1) — bloklanadi, blokdan chiqariladi, magazin bo'lib so'rov yuboradi → ERP ustasidan uziladi
CA.post(API + f"/mijozlar/{MJ1}/blokla")
CA.post(API + f"/mijozlar/{MJ1}/ochish")
S1b, _ = kirib_ol(U1, "998901112233")
dok("/api/dokon/v1/mijoz/royxat", {"turi": "magazin", "ism": "Azizbek", "magazin": "Aziz qurilish", "shahar": "Asaka"}, sessiya=S1b)
_m3a = bazadan(lambda d: d.get(DokonMijoz, MJ1).master_id)
r = CA.post(API + f"/mijozlar/{MJ1}/tasdiqla", json={})
r2 = CA.post(API + f"/mijozlar/{MJ6}/tasdiqla", json={"kpi": 5, "master_id": MASTER1})
check("R8 (M3) blokdan chiqqan usta magazin bo'lib qayta so'rov yuborsa — ERP ustasidan uziladi; magazin tasdig'i; o'sha ERP ustasi endi "
      "boshqa ustaga bog'lanadi", _m3a is None and r.status_code == 200 and bazadan(lambda d: d.get(DokonMijoz, MJ1).master_id) is None
      and r2.status_code == 200 and bazadan(lambda d: d.get(DokonMijoz, MJ6).master_id) == MASTER1, (_m3a, r.text[:200], r2.text[:200]))
_cons = [c.name for c in DokonMijoz.__table__.constraints] if DokonMijoz is not None else []
def _ikki_bog(d):
    x = d.get(DokonMijoz, MJ2)
    x.master_id = MASTER1
    try:
        d.commit()
        return "yozildi"
    except Exception as e:                         # noqa: BLE001
        d.rollback()
        return type(e).__name__
check("R9 (L4) baza: bitta ERP ustasi — bitta hisob (uq_dokon_mijoz_master); ikkinchi bog'lam — IntegrityError",
      "uq_dokon_mijoz_master" in _cons and bazadan(_ikki_bog) == "IntegrityError", (_cons, bazadan(_ikki_bog)))
# H1: zaxira → tiklash (hisob va uning ERP ustasi bog'lami qaytadi; sessiyalar — yo'q), «Barcha ma'lumotlarni o'chirish» hisobni ham o'chiradi
S6b = S6
_bk = bazadan(lambda d: crud.export_full_backup(d, company_id=1)) or {}
_nb = len(((_bk.get("tables") or {}).get("dokon_mijozlar")) or [])
_res = bazadan(lambda d: crud.import_full_backup(d, _bk, company_id=1, replace=True)) or {}
_rw = bazadan(lambda d: [(x.id, x.mj_holat, x.master_id) for x in d.query(DokonMijoz).filter(DokonMijoz.company_id == 1).order_by(DokonMijoz.id).all()])
check("R10 (H1) zaxiradan tiklash — hisoblar qaytdi (soni, holati, ERP ustasi bog'lami AYNAN), o'tkazib yuborilmadi; eski sessiya ishlamaydi",
      _res.get("success") is True and "dokon_mijozlar" not in (_res.get("skipped_tables") or []) and _rw is not None and len(_rw) == _nb
      and (MJ6, "tasdiqlangan", MASTER1) in _rw and dok("/api/dokon/v1/mijoz", sessiya=S6b, usul="get").status_code == 401
      and bazadan(lambda d: d.query(DokonSessiya).count()) == 0, (_res, _rw, _nb))
bazadan(lambda d: crud.factory_reset_all_data(d, company_id=1))
check("R11 (H1) korxona ma'lumotlarini o'chirish — saytdagi hisoblar, kirishlar, sessiyalar ham o'chdi",
      bazadan(lambda d: (d.query(DokonMijoz).filter(DokonMijoz.company_id == 1).count(), d.query(DokonKirish).filter(DokonKirish.company_id == 1).count(),
                         d.query(DokonSessiya).filter(DokonSessiya.company_id == 1).count())) == (0, 0, 0), "")

if PG_URL:
    try:
        import database as _dbm248
        _dbm248.engine.dispose()
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
