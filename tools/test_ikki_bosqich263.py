#!/usr/bin/env python3
"""
test_ikki_bosqich263.py — kech199 (zip 263, xavfsizlik REJA 2-band + 12-band + 17-band): platforma egasi kirishiga TELEGRAM KODI
(EGASI QARORI 06.11 17:33 «Ha qo'shilsin»), tarqoq blokdan egasining o'tishi, IP chegarasi 60.

NIMA UCHUN KERAK
----------------
  Platforma egasi hisobi — hamma korxonalar ustidan hokim; ilgari faqat parol. Endi to'g'ri paroldan keyin 6 xonali kod egasining
  Telegramiga ketadi; sessiya — faqat kod to'g'ri bo'lsa. 12-band (Fable F4, O'LCHANGAN): 30 tarqoq xato egasini yangi qurilmadan
  kiritmasdi — endi to'g'ri parol + kod bilan o'tadi, egasiga ogohlantirish. 17-band (Fable F12): CGNAT — IP chegarasi 20 → 60.

BO'LIMLAR
  A — oddiy foydalanuvchi: avvalgidek (kod yo'q);
  B — platforma egasi: kod yuboriladi (chat, matn), sessiya yo'q, cookie xossalari, sahifa, noto'g'ri kod (qolgan urinish), to'g'ri kod
      → sessiya + «bu qurilma», qayta ishlatish yo'q, ishonchli qurilma (o'zi / parol almashsa / muddati / begona foydalanuvchi /
      «eslab qolish» yo'q), 5 urinish, muddati, Telegram yuborilmadi, 15 daqiqada 5 kod, PLATFORMA_2FA=0, Telegram sozlanmagan,
      noto'g'ri parol, xeshlar, bo'shliqli kod, cookie siz sahifa, jurnal, nofaol foydalanuvchi, atomar urinish;
  C — 12 / 17-band: tarqoq blok — egasi FAQAT ishonchli qurilmadan o'tadi (kech200, review263 R1: yangi qurilmadan to'g'ri / noto'g'ri
      parol — AYNAN bir xil blok matni), oddiy foydalanuvchi — blok
      (korxona chatiga ogohlantirish), ogohlantirish 15 daqiqada bir marta, (login, IP) bloki — o'tilmaydi, 2FA o'chiq — o'tilmaydi,
      `sabab`, IP chegarasi 60;
  D — sxema: jadvallar, zaxiradan tashqari, foydalanuvchi o'chirilganda yozuvlar;
  E — shablon: oddiy kirish sahifasi o'zgarmagan, kod sahifasi.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 263 1-qism, 894aa9b) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_ikki_bosqich263.py
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "ikki_bosqich263_test"
_DB = os.path.join(tempfile.gettempdir(), "ikki_bosqich263_test.db")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["TELEGRAM_BOT_TOKEN"] = "111:SINOV263"
os.environ["BACKUP_TELEGRAM_CHAT_ID"] = "555263"
os.environ.pop("PLATFORMA_2FA", None)

import re                                          # noqa: E402
import html as _html                               # noqa: E402
import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime, timedelta           # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, LoginHistory, ErrorLog   # noqa: E402
from production_models import Company             # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

try:
    import ikki_bosqich                            # noqa: E402
    from models import IkkiBosqichKod, IshonchliQurilma   # noqa: E402
    YANGI = True
except Exception:                                  # noqa: BLE001
    ikki_bosqich = IkkiBosqichKod = IshonchliQurilma = None
    YANGI = False

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


TG = []                    # (token, chat, matn)
XABAR = []                 # _send_telegram (matn, company_id)
TG_BUZ = {"v": False}


def _tg(token, chat_id, text, reply_markup=None):
    if TG_BUZ["v"]:
        raise RuntimeError("sinov: Telegram javob bermadi")
    TG.append((token, chat_id, text))
    return None


main._tg_post_message = _tg
main._send_telegram = lambda text, company_id=None: XABAR.append((text, company_id))

PAROL = "Egasi-Parol-263!"
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ikkinchi Korxona", code="IKKINCHI-I263"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    pe = auth.create_user(s, "i263_egasi", PAROL, UserRole.ADMIN, "Platforma egasi", company_id=1)
    od = auth.create_user(s, "i263_oddiy", PAROL, UserRole.ADMIN, "Oddiy admin", company_id=2)
    ik = auth.create_user(s, "i263_ikkinchi", PAROL, UserRole.ADMIN, "Ikkinchi egasi", company_id=1)
s.commit()
s.query(User).filter(User.id.in_([pe.id, ik.id])).update({"is_platform_admin": True}, synchronize_session=False)
s.commit()
PE_ID, OD_ID, IK_ID = pe.id, od.id, ik.id
s.close()
_IP = {"n": 10}


def mijoz(ip=None):
    _IP["n"] += 1
    ip = ip or f"198.51.{_IP['n'] // 250}.{_IP['n'] % 250 + 1}"
    try:
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False, follow_redirects=False,
                       client=(ip, 50000))
    except TypeError:
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False, follow_redirects=False)
    c.headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    return c


def kir(c, login="i263_egasi", parol=None):
    return c.post("/login", data={"username": login, "password": parol if parol is not None else PAROL})


def oxirgi_kod():
    for _t, _c, matn in reversed(TG):
        m = re.search(r"kirish kodi: (\d{6})", matn)
        if m:
            return m.group(1)
    return "999999"                # kod yuborilmagan (asl kod) — sinov qulamasin


def set_cookie_sarlavhalari(r):
    return [v for k, v in r.headers.multi_items() if k.lower() == "set-cookie"]


def javob_cookie(r, nom):
    """Javob o'rnatgan cookie qiymati (Set-Cookie sarlavhasidan; mijoz idishidagi eski nusxalardan qat'i nazar)."""
    for v in set_cookie_sarlavhalari(r):
        m = re.match(rf"\s*{re.escape(nom)}=([^;]*)", v)
        if m and m.group(1) not in ("", '""'):
            return m.group(1)
    return None


def db_q(fn):
    db = SessionLocal()
    try:
        return fn(db)
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — oddiy foydalanuvchi")
TG.clear()
c = mijoz()
r = kir(c, "i263_oddiy")
check("A1 oddiy admin — darhol sessiya (302 /), kod yuborilmadi",
      lambda: r.status_code == 302 and r.headers.get("location") == "/" and c.cookies.get("session_token") and TG == [],
      (r.status_code, r.headers.get("location"), TG))

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B — platforma egasi: Telegram kodi")
TG.clear()
c = mijoz("203.0.113.77")
r = kir(c)
check("B1 to'g'ri parol — /login/kod ga (302), sessiya YO'Q",
      lambda: r.status_code == 302 and r.headers.get("location") == "/login/kod" and not c.cookies.get("session_token"),
      (r.status_code, r.headers.get("location"), dict(c.cookies)))
sc = " | ".join(set_cookie_sarlavhalari(r)).lower()
check("B2 kirish_kod cookie: httponly, secure, samesite=strict, path=/login, 300 s",
      lambda: "kirish_kod=" in sc and "httponly" in sc and "secure" in sc and "samesite=strict" in sc and "path=/login" in sc
      and "max-age=300" in sc, sc)
check("B3 Telegram: tizim tokeni, egasining chati, 6 xonali kod, login, IP",
      lambda: len(TG) == 1 and TG[0][0] == "111:SINOV263" and TG[0][1] == "555263" and re.search(r"kirish kodi: \d{6}", TG[0][2])
      and "i263_egasi" in TG[0][2] and "203.0.113.77" in TG[0][2], TG)
KOD1 = oxirgi_kod()
r = c.get("/login/kod")
check("B4 /login/kod sahifasi — kod maydoni, «eslab qolish» (belgilangan), 200",
      lambda: r.status_code == 200 and 'name="kod"' in _html.unescape(r.text) and 'autocomplete="one-time-code"' in _html.unescape(r.text)
      and 'name="eslab_qol"' in _html.unescape(r.text) and "checked" in _html.unescape(r.text) and 'action="/login/kod"' in _html.unescape(r.text), r.status_code)
notogri = "000000" if KOD1 != "000000" else "111111"
r = c.post("/login/kod", data={"kod": notogri, "eslab_qol": "1"})
check("B5 noto'g'ri kod — 400, «Yana 4 ta urinish», sessiya yo'q",
      lambda: r.status_code == 400 and "Yana 4 ta urinish" in _html.unescape(r.text) and not c.cookies.get("session_token"), (r.status_code, r.text[-600:]))
check("B6 noto'g'ri kod — kirish tarixida muvaffaqiyatsiz urinish",
      lambda: db_q(lambda d: d.query(LoginHistory).filter(LoginHistory.username == "i263_egasi", LoginHistory.success == False,   # noqa: E712
                                                          LoginHistory.ip_address == "203.0.113.77").count()) == 1)
r = c.post("/login/kod", data={"kod": KOD1[:3] + " " + KOD1[3:], "eslab_qol": "1"})
check("B7 to'g'ri kod (bo'shliq bilan) — 302 /, sessiya bor",
      lambda: r.status_code == 302 and r.headers.get("location") == "/" and c.cookies.get("session_token"), (r.status_code, r.text[-300:]))
sc = " | ".join(set_cookie_sarlavhalari(r)).lower()
check("B8 ishonchli_qurilma cookie: httponly, secure, path=/login, 30 kun; kirish_kod o'chirildi",
      lambda: "ishonchli_qurilma=" in sc and "path=/login" in sc and f"max-age={30 * 24 * 3600}" in sc
      and re.search(r'kirish_kod=("")?;', sc) is not None, sc)
r2 = c.get("/api/health")
check("B9 sessiya ishlaydi", lambda: r2.status_code == 200)
QUR_COOKIE = javob_cookie(r, "ishonchli_qurilma")
check("B10 muvaffaqiyatli kirish jurnalda", lambda: db_q(lambda d: d.query(LoginHistory).filter(
    LoginHistory.username == "i263_egasi", LoginHistory.success == True).count()) >= 1)   # noqa: E712
c2 = mijoz()
c2.cookies.set("kirish_kod", "eski", path="/login")
r = c2.get("/login/kod")
check("B11 yaroqsiz kirish_kod — /login?kod=tugadi", lambda: r.status_code == 302 and r.headers.get("location") == "/login?kod=tugadi",
      (r.status_code, r.headers.get("location")))
r = mijoz().get("/login?kod=tugadi")
check("B12 /login?kod=tugadi — «muddati yoki urinishlari tugadi»", lambda: r.status_code == 200 and "tugadi" in _html.unescape(r.text), r.status_code)
r = mijoz().get("/login/kod")
check("B13 cookie siz /login/kod — /login ga", lambda: r.status_code == 302 and r.headers.get("location", "").startswith("/login"))
# qayta ishlatish: o'sha kirish_kod qiymati bilan
TG.clear()
c3 = mijoz()
r = kir(c3)
KOD2, XOM2 = oxirgi_kod(), javob_cookie(r, "kirish_kod")
r3 = c3.post("/login/kod", data={"kod": KOD2})
c4 = mijoz()
c4.cookies.set("kirish_kod", XOM2 or "x", path="/login")
r = c4.post("/login/kod", data={"kod": KOD2})
check("B14 ishlatilgan kod qayta ishlamaydi (o'sha cookie + kod) — /login?kod=tugadi, sessiya yo'q",
      lambda: r.status_code == 302 and r.headers.get("location") == "/login?kod=tugadi" and not c4.cookies.get("session_token"),
      (r.status_code, r.headers.get("location")))
check("B15 «eslab qolish» belgisiz — sessiya bor, ishonchli qurilma cookie si YO'Q",
      lambda: r3.status_code == 302 and javob_cookie(r3, "session_token") and not javob_cookie(r3, "ishonchli_qurilma"))
# ishonchli qurilma
TG.clear()
c5 = mijoz()
if QUR_COOKIE:
    c5.cookies.set("ishonchli_qurilma", QUR_COOKIE, path="/login")
r = kir(c5)
check("B16 ishonchli qurilma — kodsiz sessiya, Telegram yo'q",
      lambda: r.status_code == 302 and r.headers.get("location") == "/" and c5.cookies.get("session_token") and TG == [],
      (r.status_code, r.headers.get("location"), TG))
c6 = mijoz()
if QUR_COOKIE:
    c6.cookies.set("ishonchli_qurilma", QUR_COOKIE, path="/login")
r = kir(c6, "i263_ikkinchi")
check("B17 boshqa platforma egasi o'sha qurilma cookie si bilan — kod so'raladi",
      lambda: r.status_code == 302 and r.headers.get("location") == "/login/kod", (r.status_code, r.headers.get("location")))
if YANGI:
    db = SessionLocal()
    q = db.query(IshonchliQurilma).filter(IshonchliQurilma.user_id == PE_ID).first()
    check("B18 bazada token XESHI (xom cookie emas), parol belgisi, qurilma nomi",
          lambda: q is not None and q.token_xesh != QUR_COOKIE and len(q.token_xesh) == 64 and q.parol_belgisi and q.qurilma)
    db.close()
s = SessionLocal()
auth.change_password(s, PE_ID, "Yangi-Parol-263!x", company_id=1, bajaruvchi=s.query(User).filter(User.id == PE_ID).first())
s.close()
TG.clear()
c7 = mijoz()
if QUR_COOKIE:
    c7.cookies.set("ishonchli_qurilma", QUR_COOKIE, path="/login")
r = kir(c7, parol="Yangi-Parol-263!x")
check("B19 parol almashtirilgach — ishonchli qurilma BEKOR (kod so'raladi)",
      lambda: r.status_code == 302 and r.headers.get("location") == "/login/kod" and len(TG) == 1, (r.status_code, r.headers.get("location")))
PAROL = "Yangi-Parol-263!x"
r = c7.post("/login/kod", data={"kod": oxirgi_kod(), "eslab_qol": "1"})
QUR2 = javob_cookie(r, "ishonchli_qurilma")
if YANGI:
    db = SessionLocal()
    db.query(IshonchliQurilma).filter(IshonchliQurilma.user_id == PE_ID).update(
        {"expires_at": datetime.utcnow() - timedelta(minutes=1)}, synchronize_session=False)
    db.commit()
    db.close()
TG.clear()
c8 = mijoz()
if QUR2:
    c8.cookies.set("ishonchli_qurilma", QUR2, path="/login")
r = kir(c8)
check("B20 ishonchli qurilma muddati o'tgan — kod so'raladi", lambda: r.status_code == 302 and r.headers.get("location") == "/login/kod",
      (r.status_code, r.headers.get("location")))
# 5 urinish
TG.clear()
c9 = mijoz()
r = kir(c9)
K9 = oxirgi_kod()
xato9 = "123123" if K9 != "123123" else "321321"
javoblar = [c9.post("/login/kod", data={"kod": xato9}) for _ in range(5)]
check("B21 5 ta noto'g'ri — 4,3,2,1 qoldi, 5-chisi /login?kod=tugadi",
      lambda: [j.status_code for j in javoblar] == [400, 400, 400, 400, 302] and "Yana 1 ta" in _html.unescape(javoblar[3].text)
      and javoblar[4].headers.get("location") == "/login?kod=tugadi", [j.status_code for j in javoblar])
c9b = mijoz()
c9b.cookies.set("kirish_kod", javob_cookie(r, "kirish_kod") or "x", path="/login")
r = c9b.post("/login/kod", data={"kod": K9})
check("B22 urinishlar tugagach to'g'ri kod ham ishlamaydi (sessiya yo'q)", lambda: not c9b.cookies.get("session_token"))
# muddati
TG.clear()
c10 = mijoz()
r = kir(c10)
K10 = oxirgi_kod()
if YANGI:
    db = SessionLocal()
    db.query(IkkiBosqichKod).filter(IkkiBosqichKod.user_id == PE_ID, IkkiBosqichKod.ishlatilgan == False).update(   # noqa: E712
        {"expires_at": datetime.utcnow() - timedelta(seconds=1)}, synchronize_session=False)
    db.commit()
    db.close()
r = c10.post("/login/kod", data={"kod": K10})
check("B23 muddati o'tgan kod — /login?kod=tugadi, sessiya yo'q",
      lambda: r.status_code == 302 and r.headers.get("location") == "/login?kod=tugadi" and not c10.cookies.get("session_token"))
# Telegram yuborilmadi
if YANGI:
    db = SessionLocal()
    db.query(IkkiBosqichKod).delete(synchronize_session=False)
    db.commit()
    db.close()
TG.clear()
TG_BUZ["v"] = True
c11 = mijoz()
r = kir(c11)
TG_BUZ["v"] = False
check("B24 Telegram yuborilmadi — kirish YO'Q, «yuborilmadi», kod sahifasiga emas",
      lambda: r.status_code == 200 and "yuborilmadi" in _html.unescape(r.text) and not javob_cookie(r, "session_token")
      and not javob_cookie(r, "kirish_kod"), (r.status_code, r.text[-300:]))
check("B25 … kod yozuvi qolmadi, xato jurnalda",
      lambda: (not YANGI or db_q(lambda d: d.query(IkkiBosqichKod).count()) == 0)
      and db_q(lambda d: d.query(ErrorLog).filter(ErrorLog.error_message.like("%kirish kodi Telegramga yuborilmadi%")).count()) >= 1)
# 15 daqiqada 5 kod
TG.clear()
javob = [kir(mijoz()) for _ in range(6)]
check("B26 15 daqiqada 5 ta kod — 6-chisi «Juda ko'p kod so'raldi», Telegram 5 ta",
      lambda: [j.headers.get("location") for j in javob[:5]] == ["/login/kod"] * 5 and javob[5].status_code == 200
      and "Juda ko'p kod" in _html.unescape(javob[5].text) and len(TG) == 5, ([j.status_code for j in javob], len(TG)))
if YANGI:
    db = SessionLocal()
    db.query(IkkiBosqichKod).delete(synchronize_session=False)
    db.commit()
    db.close()
# PLATFORMA_2FA=0
os.environ["PLATFORMA_2FA"] = "0"
TG.clear()
c12 = mijoz()
r = kir(c12)
os.environ.pop("PLATFORMA_2FA", None)
check("B27 PLATFORMA_2FA=0 — kodsiz sessiya", lambda: r.status_code == 302 and r.headers.get("location") == "/" and TG == [],
      (r.status_code, r.headers.get("location")))
_tok = os.environ.pop("TELEGRAM_BOT_TOKEN")
c13 = mijoz()
r = kir(c13)
os.environ["TELEGRAM_BOT_TOKEN"] = _tok
check("B28 tizim Telegrami sozlanmagan (token yo'q) — kodsiz (yuboradigan joy yo'q)",
      lambda: r.status_code == 302 and r.headers.get("location") == "/", (r.status_code, r.headers.get("location")))
TG.clear()
r = kir(mijoz(), parol="notogri-parol-xx")
check("B29 noto'g'ri parol — oddiy xato, kod yuborilmadi", lambda: r.status_code == 200 and "noto" in _html.unescape(r.text) and TG == [])
if YANGI:
    TG.clear()
    c14 = mijoz()
    xom14 = javob_cookie(kir(c14), "kirish_kod")
    db = SessionLocal()
    q14 = db.query(IkkiBosqichKod).filter(IkkiBosqichKod.user_id == PE_ID).order_by(IkkiBosqichKod.id.desc()).first()
    check("B30 bazada kod va cookie XOM saqlanmaydi (HMAC / sha256)",
          lambda: q14 is not None and oxirgi_kod() not in (q14.kod_xesh or "") and q14.token_xesh != xom14
          and len(q14.kod_xesh) == 64 and len(q14.token_xesh) == 64)
    q14.urinish = ikki_bosqich.KOD_URINISH
    db.commit()
    db.close()
    natija = ikki_bosqich.kod_tekshir(SessionLocal(), xom14, oxirgi_kod())
    check("B31 urinishi tugagan yozuv — to'g'ri kod ham yaroqsiz (atomar shart)", lambda: not natija["ok"] and natija["yaroqsiz"], natija)
    TG.clear()
    c15 = mijoz()
    kir(c15)
    s = SessionLocal()
    s.query(User).filter(User.id == PE_ID).update({"is_active": False})
    s.commit()
    s.close()
    r = c15.post("/login/kod", data={"kod": oxirgi_kod()})
    s = SessionLocal()
    s.query(User).filter(User.id == PE_ID).update({"is_active": True})
    s.commit()
    s.close()
    check("B32 kod kutilayotganda hisob o'chirildi — sessiya yo'q", lambda: r.status_code == 302 and not c15.cookies.get("session_token"),
          (r.status_code, r.headers.get("location")))
    check("B33 kod xabari: «hech kimga bermang», 5 daqiqa", lambda: "hech kimga bermang" in ikki_bosqich.kod_xabari("123456", "a", "1.2.3.4", "PC")
          and "5 daqiqa" in ikki_bosqich.kod_xabari("123456", "a", None, None))
    check("B34 kod_tozala: «12-34 56» → «123456»", lambda: ikki_bosqich.kod_tozala("12-34 56") == "123456")
    check("B35 yoqilganmi: '0' / 'off' / 'yoq' — o'chiq, bo'sh — yoqiq",
          lambda: [ikki_bosqich.yoqilganmi() for v in ("0", "off", "yoq", "") if os.environ.update({"PLATFORMA_2FA": v}) is None]
          == [False, False, False, True])
    os.environ.pop("PLATFORMA_2FA", None)
    db = SessionLocal()
    db.query(IkkiBosqichKod).delete(synchronize_session=False)
    db.commit()
    db.close()

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C — 12-band: tarqoq blok; 17-band: IP chegarasi 60")


def tarqoq_xato(login, n=30):
    db = SessionLocal()
    cid = db.query(User.company_id).filter(User.username == login).scalar()
    for i in range(n):
        db.add(LoginHistory(company_id=cid, username=login, success=False, ip_address=f"192.0.2.{i + 1}", user_agent="hujum"))
    db.commit()
    db.close()


def tarix_tozala():
    db = SessionLocal()
    db.query(LoginHistory).delete(synchronize_session=False)
    db.commit()
    db.close()
    if hasattr(main, "_BLOK_OGOH_OXIRGI"):
        main._BLOK_OGOH_OXIRGI.clear()


tarix_tozala()
tarqoq_xato("i263_egasi")
s = SessionLocal()
rl = crud.check_login_rate_limit(s, "i263_egasi", "198.18.0.1")
s.close()
check("C1 30 tarqoq xato — blok, sabab «login_jami»", lambda: rl["blocked"] and rl.get("sabab") == "login_jami", rl)
TG.clear()
XABAR.clear()
c = mijoz("198.18.0.1")
r = kir(c)
_t_togri = _html.unescape(r.text)
# kech200 (zip 263, review263 R1): blokdan FAQAT ishonchli qurilma o'tadi — yangi qurilmadan to'g'ri parol ham blok matni (oracle yo'q)
check("C2 platforma egasi to'g'ri parol, yangi IP, ishonchli qurilmasiz — BLOK matni (kodga O'TMAYDI), kod yuborilmadi, sessiya yo'q",
      lambda: r.status_code == 200 and "Juda ko'p noto'g'ri urinish" in _t_togri and TG == [] and not c.cookies.get("session_token")
      and not c.cookies.get("kirish_kod"), (r.status_code, r.headers.get("location"), r.text[-200:]))
check("C3 egasiga ogohlantirish (tizim chati, company_id yo'q) + qayerdan kira olishi (ishonchli qurilma / odatdagi joy)",
      lambda: len(XABAR) == 1 and "30 dan ortiq" in XABAR[0][0] and "i263_egasi" in XABAR[0][0] and XABAR[0][1] is None
      and "ishonchli qurilmangizdan" in XABAR[0][0], XABAR)
TG.clear()
XABAR.clear()
r = kir(mijoz("198.18.0.2"), parol="notogri-parol-zz")
check("C5 blokda noto'g'ri parol — BLOK matni, to'g'ri paroldagi javob bilan AYNAN bir xil (parol oshkor emas), ogohlantirish takrorlanmadi",
      lambda: r.status_code == 200 and "Juda ko'p noto'g'ri urinish" in _html.unescape(r.text) and TG == [] and XABAR == []
      and _html.unescape(r.text) == _t_togri, (r.text[-300:], XABAR))
s = SessionLocal()
_pe = s.query(User).filter(User.username == "i263_egasi").first()
_qur_blok = (ikki_bosqich.qurilma_yarat(s, _pe, "203.0.113.5", "Sinov qurilma") if ikki_bosqich is not None
             else "asl-kodda-yoq")          # asl kodda modul yo'q — sinov qulamasin
s.close()
TG.clear()
c = mijoz("198.18.0.5")
c.cookies.set("ishonchli_qurilma", _qur_blok, path="/login")
r = kir(c)
check("C4 egasining ISHONCHLI qurilmasi + to'g'ri parol — blokdan o'tadi, kodsiz sessiya",
      lambda: r.status_code == 302 and r.headers.get("location") == "/" and javob_cookie(r, "session_token") and TG == [],
      (r.status_code, r.headers.get("location"), r.text[-200:]))
c = mijoz("198.18.0.6")
c.cookies.set("ishonchli_qurilma", _qur_blok, path="/login")
r = kir(c, parol="notogri-parol-zz")
check("C4b ishonchli qurilma + noto'g'ri parol — BLOK matni, sessiya yo'q",
      lambda: r.status_code == 200 and "Juda ko'p noto'g'ri urinish" in _html.unescape(r.text) and not javob_cookie(r, "session_token"),
      r.status_code)
c = mijoz("198.18.0.7")
c.cookies.set("ishonchli_qurilma", "soxta-qurilma-kaliti-123", path="/login")
r = kir(c)
check("C4c soxta ishonchli qurilma cookie si + to'g'ri parol — BLOK matni (kod ham yo'q)",
      lambda: r.status_code == 200 and "Juda ko'p noto'g'ri urinish" in _html.unescape(r.text) and TG == [], (r.status_code, TG))
tarix_tozala()
tarqoq_xato("i263_oddiy")
XABAR.clear()
r = kir(mijoz("198.18.0.3"), "i263_oddiy")
check("C6 oddiy foydalanuvchi tarqoq blokda — to'g'ri parol bilan ham BLOK; korxona chatiga ogohlantirish",
      lambda: r.status_code == 200 and "Juda ko'p noto'g'ri urinish" in _html.unescape(r.text) and len(XABAR) == 1 and XABAR[0][1] == 2,
      (r.status_code, XABAR))
r = kir(mijoz("198.18.0.4"), "i263_oddiy")
check("C7 ogohlantirish 15 daqiqada bir marta", lambda: len(XABAR) == 1, XABAR)
tarix_tozala()
db = SessionLocal()
for i in range(5):
    db.add(LoginHistory(company_id=1, username="i263_egasi", success=False, ip_address="198.18.0.9", user_agent="x"))
db.commit()
db.close()
TG.clear()
r = kir(mijoz("198.18.0.9"))
check("C8 (login, IP) bloki — platforma egasi ham O'TOLMAYDI (kod yo'q)",
      lambda: r.status_code == 200 and "Juda ko'p" in _html.unescape(r.text) and TG == [], (r.status_code, TG))
tarix_tozala()
tarqoq_xato("i263_egasi")
os.environ["PLATFORMA_2FA"] = "0"
r = kir(mijoz("198.18.0.10"))
os.environ.pop("PLATFORMA_2FA", None)
check("C9 2FA o'chiq — tarqoq blokdan o'tilmaydi", lambda: r.status_code == 200 and "Juda ko'p" in _html.unescape(r.text), r.status_code)
tarix_tozala()
db = SessionLocal()
for i in range(59):
    db.add(LoginHistory(company_id=None, username=f"yoq{i}", success=False, ip_address="198.18.1.1", user_agent="x"))
db.commit()
rl59 = crud.check_login_rate_limit(db, "i263_oddiy", "198.18.1.1")
db.add(LoginHistory(company_id=None, username="yoq60", success=False, ip_address="198.18.1.1", user_agent="x"))
db.commit()
rl60 = crud.check_login_rate_limit(db, "i263_oddiy", "198.18.1.1")
db.close()
check("C10 IP chegarasi 60: 59 xato — ochiq, 60 — blok (sabab «ip»)",
      lambda: not rl59["blocked"] and rl60["blocked"] and rl60.get("sabab") == "ip", (rl59, rl60))
tarix_tozala()
db = SessionLocal()
for i in range(5):
    db.add(LoginHistory(company_id=2, username="i263_oddiy", success=False, ip_address="198.18.2.1", user_agent="x"))
db.commit()
rl5 = crud.check_login_rate_limit(db, "i263_oddiy", "198.18.2.1")
db.close()
check("C11 (login, IP) 5 — sabab «login_ip»", lambda: rl5["blocked"] and rl5.get("sabab") == "login_ip", rl5)
tarix_tozala()

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — sxema, zaxira, foydalanuvchi o'chirilishi")
from sqlalchemy import inspect as _insp          # noqa: E402
import database as _dbm                         # noqa: E402
jadvallar = set(_insp(_dbm.engine).get_table_names())
check("D1 jadvallar bor: ikki_bosqich_kodlar, ishonchli_qurilmalar", lambda: {"ikki_bosqich_kodlar", "ishonchli_qurilmalar"} <= jadvallar)
check("D2 zaxiradan tashqari (`_NON_TENANT_TABLES`)",
      lambda: {"ikki_bosqich_kodlar", "ishonchli_qurilmalar"} <= set(crud._NON_TENANT_TABLES))
s = SessionLocal()
ex = crud.export_full_backup(s, company_id=1)
s.close()
check("D3 korxona zaxirasida yo'q", lambda: "ikki_bosqich_kodlar" not in ex["tables"] and "ishonchli_qurilmalar" not in ex["tables"])
if YANGI:
    s = SessionLocal()
    u2 = s.query(User).filter(User.id == OD_ID).first()
    ikki_bosqich.kod_yarat(s, u2, "1.1.1.1")
    ikki_bosqich.qurilma_yarat(s, u2, "1.1.1.1", "PC")
    with contextlib.redirect_stdout(_quiet):
        auth.create_user(s, "i263_qoladi", PAROL, UserRole.ADMIN, "Qoladi", company_id=2)
    s.commit()
    qoladi = s.query(User).filter(User.username == "i263_qoladi").first().id
    try:
        crud.factory_reset_all_data(s, keep_only_user_id=qoladi, company_id=2)
        xato = None
    except Exception as e:                 # noqa: BLE001
        xato = e
        s.rollback()
    check("D4 «faqat men qolay» tozalash — boshqa foydalanuvchining kod / qurilma yozuvlari bilan XATOSIZ, yozuvlar o'chdi",
          lambda: xato is None and s.query(IkkiBosqichKod).filter(IkkiBosqichKod.user_id == OD_ID).count() == 0
          and s.query(IshonchliQurilma).filter(IshonchliQurilma.user_id == OD_ID).count() == 0, xato)
    s.close()

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E — shablon")
r = mijoz().get("/login")
check("E1 oddiy kirish sahifasi — login / parol formasi, kod maydoni YO'Q",
      lambda: r.status_code == 200 and 'name="username"' in _html.unescape(r.text) and 'name="password"' in _html.unescape(r.text) and 'name="kod"' not in _html.unescape(r.text)
      and "Xush kelibsiz" in _html.unescape(r.text))
TG.clear()
c = mijoz()
kir(c)
r = c.get("/login/kod")
check("E2 kod sahifasi — login / parol maydoni YO'Q, «Qaytadan kirish» havolasi",
      lambda: r.status_code == 200 and 'name="password"' not in _html.unescape(r.text) and 'href="/login"' in _html.unescape(r.text) and "Telegram kodi" in _html.unescape(r.text))

print("\n" + "=" * 70)
print(f"{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
