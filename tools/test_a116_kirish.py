#!/usr/bin/env python3
"""
test_a116_kirish.py — kech116, A bosqich 2-qism: U-01 (mijozning HAQIQIY IP manzili, kirish cheklovi) va G6-06 (parol /
PIN almashtirilganda o'sha odamning boshqa kirishlari yopiladi). Server qismi; `users.html` parol oynasi —
`tools/test_a116_ui.py`.

NIMA UCHUN KERAK (audit kech114 — O'LCHANGAN, asl kod = `staging` 44c40ee)
  U-01   Jonli `/logs`: 100 kirish yozuvida IP lar faqat 100.64.0.x (Railway proksisi) — `request.client.host`. 5 xato →
         15 daqiqa cheklov IP bo'yicha ham hisoblanadi: bitta proksi manzilidan kelayotgan HAMMA foydalanuvchi (boshqa
         korxonalar ham) birga bloklanishi mumkin. `uvicorn --forwarded-allow-ips='*'` (0.30.6) esa XFF ning ENG CHAP
         (soxtalashtiriladigan) manzilini olardi.
  G6-06  Parol almashtirilgach o'sha odamning boshqa kompyuter / telefondagi kirishi yopilmasdi (8 soat), hodim PIN i
         almashtirilsa — eski kirish 14 kun ishlardi.
BO'LIMLAR: I — `auth.mijoz_ip` qoidasi; L — HAQIQIY HTTP (uvicorn, ulanish 127.0.0.1 = ichki proksi): kirish jurnalida
  haqiqiy IP; R — kirish cheklovi (foydalanuvchi nomi 5, IP 20); P — parol: boshqa sessiyalar yopiladi, joriy qoladi;
  H — hodim PIN i; X — xatolar.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI (yangi nomlar — `getattr`).
ISHLATISH: python3 tools/test_a116_kirish.py
"""
import os
import sys
import time
import socket
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "a116_kirish_test"
_T = tempfile.mkdtemp(prefix="a116k_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'a116_kirish_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, LoginHistory, UserSession, EmployeeSession, Employee, User   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from starlette.requests import Request as _SR      # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HOLATLAR = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:600]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.headers = {}
        self.cookies = {}

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    HOLATLAR.append((metod.upper() + " " + url.split("?")[0], r.status_code))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ══════════════════════════════════════════════════════════════
section("I. `auth.mijoz_ip` — haqiqiy mijoz manzili")
# ══════════════════════════════════════════════════════════════
_mip = getattr(auth, "mijoz_ip", None)


def sorov(ulanish, sarlavhalar=None):
    scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"",
             "headers": [(k.lower().encode("latin1"), v.encode("latin1")) for k, v in (sarlavhalar or {}).items()],
             "client": (ulanish, 5555) if ulanish else None}
    return _SR(scope)


def ip(ulanish, sarlavhalar=None):
    if _mip is None:
        return "YO'Q: auth.mijoz_ip (asl kod)"
    try:
        return _mip(sorov(ulanish, sarlavhalar))
    except Exception as e:                 # noqa: BLE001
        return f"ISTISNO {type(e).__name__}: {e}"


HOLLAR = [
    ("I1 Railway proksisi (100.64.0.3) + XFF «203.0.113.7» → 203.0.113.7", "100.64.0.3", {"X-Forwarded-For": "203.0.113.7"},
     "203.0.113.7"),
    ("I2 mijoz soxta XFF yuborgan («1.2.3.4, 203.0.113.7») — ENG O'NG ochiq manzil (proksi qo'shgan) olinadi", "100.64.0.3",
     {"X-Forwarded-For": "1.2.3.4, 203.0.113.7"}, "203.0.113.7"),
    ("I3 ichki qadamlar o'tkaziladi («203.0.113.7, 10.0.0.5, 100.64.0.2»)", "100.64.0.9",
     {"X-Forwarded-For": "203.0.113.7, 10.0.0.5, 100.64.0.2"}, "203.0.113.7"),
    ("I4 IP bo'lmagan qism va port («abc, 203.0.113.7:4444»)", "10.1.2.3", {"X-Forwarded-For": "abc, 203.0.113.7:4444"},
     "203.0.113.7"),
    ("I5 IPv6 qavs va port («[2001:db8::5]:443»)", "127.0.0.1", {"X-Forwarded-For": "[2001:db8::5]:443"}, "2001:db8::5"),
    ("I6 XFF yo'q — X-Real-IP (198.51.100.9)", "100.64.0.3", {"X-Real-IP": "198.51.100.9"}, "198.51.100.9"),
    ("I7 sarlavha yo'q — ulanish manzili", "100.64.0.3", {}, "100.64.0.3"),
    ("I8 XFF da faqat ichki manzillar — ulanish manzili", "100.64.0.3", {"X-Forwarded-For": "10.0.0.1, 192.168.1.5"},
     "100.64.0.3"),
    ("I9 to'g'ridan-to'g'ri ulanish (ochiq 8.8.8.8) — sarlavhalarga ISHONILMAYDI", "8.8.8.8",
     {"X-Forwarded-For": "1.1.1.1", "X-Real-IP": "1.1.1.2"}, "8.8.8.8"),
    ("I10 IPv4 ichidagi IPv6 (::ffff:203.0.113.8)", "100.64.0.3", {"X-Forwarded-For": "::ffff:203.0.113.8"}, "203.0.113.8"),
    ("I11 mijozsiz so'rov — None", None, {"X-Forwarded-For": "203.0.113.7"}, None),
]
for nom, ul, sar, kut in HOLLAR:
    got = ip(ul, sar)
    check(nom, got == kut, got)

# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
s.add(Company(id=2, name="Kirish116 B", code="K116B"))
s.get(Company, 1).code = "K116A"          # ikki korxona — hodim kirishida korxona kodi shart
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    for u, rol, cid in (("k116_admin", UserRole.ADMIN, 1), ("k116_a", UserRole.ADMIN, 1), ("k116_b", UserRole.ADMIN, 1),
                        ("k116_x", UserRole.ADMIN, 1), ("k116_y", UserRole.ADMIN, 1), ("k116_e", UserRole.ADMIN, 1),
                        ("k116_d", UserRole.ADMIN, 1), ("k116_ip", UserRole.ADMIN, 1), ("k116_bk", UserRole.ADMIN, 2)):
        auth.create_user(s, u, "Parol123!", rol, u.upper(), company_id=cid)
EMP = Employee(company_id=1, name="K116 Hodim", position="Kesuvchi")
s.add(EMP)
s.commit()
EMP_ID = EMP.id
s.close()


def mijoz(ip="203.0.113.102"):
    """TestClient — har bo'lim o'z ulanish manzili bilan (cheklov hisoblari aralashmasin). Manzil ochiq — `mijoz_ip` uni
    o'zicha qaytaradi (asl kodda ham `request.client.host` — AYNAN)."""
    try:
        return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False, client=(ip, 50000))
    except TypeError:                      # eski Starlette — `client=` yo'q
        return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)


def kir(c, login, parol="Parol123!", sarlavha=None):
    return req(c, "post", "/login", data={"username": login, "password": parol}, follow_redirects=False,
               headers=sarlavha or {})


def kirdimi(r):
    return r.status_code in (302, 303) and "session_token" in (r.headers.get("set-cookie") or "")


def oxirgi_ip(login):
    d = SessionLocal()
    try:
        x = d.query(LoginHistory).filter(LoginHistory.username == login).order_by(LoginHistory.id.desc()).first()
        return x.ip_address if x else None
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════
section("L. HAQIQIY HTTP (uvicorn; ulanish 127.0.0.1 — ichki proksi o'rnida)")
# ══════════════════════════════════════════════════════════════
import uvicorn                                     # noqa: E402
import httpx                                       # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


PORT = _port()
# `proxy_headers=False` — Railway bilan AYNAN: jonli ilova `uvicorn main:app --host 0.0.0.0 --port $PORT` (Procfile) —
# uvicorn faqat 127.0.0.1 dan kelgan XFF ga ishonadi (FORWARDED_ALLOW_IPS standarti), Railway proksisi esa 100.64.x →
# `request.client.host` = proksi manzili. Bu yerda ulanish 127.0.0.1 — uvicorn XFF ni O'ZI almashtirib yuborardi
# (eng o'ng ishonchsiz manzil) va `request.client.host` ga qaytgan kod ham «to'g'ri» ko'rinardi (kech116 mutatsiya
# M51 / M52 — USHLANMADI). O'chirilganda ilova proksi manzilini ko'radi — jonlidagi kabi.
SERVER = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="critical", lifespan="off",
                                       proxy_headers=False))
TH = threading.Thread(target=SERVER.run, daemon=True)
TH.start()
for _ in range(100):
    if SERVER.started:
        break
    time.sleep(0.1)
check("L0 uvicorn ishga tushdi", SERVER.started)
BASE = f"http://127.0.0.1:{PORT}"


def hkir(login, parol, xff=None):
    try:
        return httpx.post(BASE + "/login", data={"username": login, "password": parol}, follow_redirects=False,
                          headers={"X-Forwarded-For": xff} if xff else {}, timeout=30)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


_r = hkir("k116_ip", "noto'g'ri", "9.9.9.9, 203.0.113.50")
check("L1 noto'g'ri parol (XFF «9.9.9.9, 203.0.113.50») — jurnalda 203.0.113.50 (asl: 127.0.0.1 — proksi manzili)",
      _r.status_code == 200 and oxirgi_ip("k116_ip") == "203.0.113.50", (_r.status_code, oxirgi_ip("k116_ip")))
_r = hkir("k116_ip", "Parol123!", "198.51.100.23")
check("L2 muvaffaqiyatli kirish — jurnalda 198.51.100.23", _r.status_code in (302, 303)
      and oxirgi_ip("k116_ip") == "198.51.100.23", (_r.status_code, oxirgi_ip("k116_ip")))
_r = hkir("k116_ip", "noto'g'ri")
check("L3 sarlavhasiz — ulanish manzili (127.0.0.1)", oxirgi_ip("k116_ip") == "127.0.0.1", oxirgi_ip("k116_ip"))
try:
    _h = httpx.post(BASE + "/hodim/login", data={"phone": "+998900000116", "pin": "0000", "korxona": ""},
                    headers={"X-Forwarded-For": "203.0.113.61"}, follow_redirects=False, timeout=30)
except Exception as e:                     # noqa: BLE001
    _h = _Xato(e)
check("L4 hodim kirishi ham haqiqiy IP bilan (203.0.113.61)", oxirgi_ip("+998900000116") == "203.0.113.61",
      (_h.status_code, oxirgi_ip("+998900000116")))

# ══════════════════════════════════════════════════════════════
section("R. Kirish cheklovi — foydalanuvchi nomi 5, IP 20")
# ══════════════════════════════════════════════════════════════
RIP = "203.0.113.101"
CA = mijoz(RIP)
for _ in range(5):
    kir(CA, "k116_a", "xato-parol")
_r = kir(CA, "k116_a")
check("R1 bitta hisobga 5 xato — shu hisob TO'G'RI parol bilan ham 15 daqiqa kira olmaydi (avvalgidek)",
      not kirdimi(_r) and "Juda ko" in (_r.text or ""), (_r.status_code, (_r.text or "")[:120]))
_r = kir(mijoz(RIP), "k116_b")
check("R2 o'sha IP dagi BOSHQA xodim (to'g'ri parol) kiradi — bitta xodimning xatosi ofisni yopmaydi (asl: IP 5 da bloklardi)",
      kirdimi(_r), (_r.status_code, (_r.text or "")[:120]))
for i in range(14):
    kir(mijoz(RIP), f"yoq_login_{i}", "xato")
_r = kir(mijoz(RIP), "k116_d")
check("R3 19 xato (IP bo'yicha) — hali kiradi", kirdimi(_r), (_r.status_code, (_r.text or "")[:120]))
kir(mijoz(RIP), "yoq_login_x", "xato")
_r = kir(mijoz(RIP), "k116_e")
check("R4 20 xato bir IP dan (turli hisoblarga) — shu IP dagi keyingi kirish bloklanadi", not kirdimi(_r)
      and "Juda ko" in (_r.text or ""), (_r.status_code, (_r.text or "")[:120]))
_r = hkir("k116_e", "Parol123!", "198.51.100.200")
check("R5 boshqa IP dan (haqiqiy IP 198.51.100.200) shu foydalanuvchi kiradi", _r.status_code in (302, 303),
      _r.status_code)
_rl = getattr(crud, "check_login_rate_limit")
_d = SessionLocal()
try:
    _t = _rl(_d, "hech_kim", "203.0.113.250")
finally:
    _d.close()
check("R6 `check_login_rate_limit` — toza IP va nom: bloklanmagan", _t.get("blocked") is False, _t)

# ══════════════════════════════════════════════════════════════
section("P. Parol almashtirilganda boshqa kirishlar yopiladi")
# ══════════════════════════════════════════════════════════════
ADM = mijoz()
check("P0 admin kirdi", kirdimi(kir(ADM, "k116_admin")))
X1, X2 = mijoz(), mijoz()
check("P0 X ikki qurilmada kirdi", kirdimi(kir(X1, "k116_x")) and kirdimi(kir(X2, "k116_x")))


def ishlaydimi(c):
    return req(c, "get", "/api/finance/cash-balance").status_code


def uid(login):
    d = SessionLocal()
    try:
        return d.query(User.id).filter(User.username == login).scalar()
    finally:
        d.close()


def sessiyalar(login):
    d = SessionLocal()
    try:
        return d.query(UserSession).filter(UserSession.user_id == uid(login)).count()
    finally:
        d.close()


_oldin = [ishlaydimi(X1), ishlaydimi(X2), sessiyalar("k116_x")]
_r = req(ADM, "post", f"/api/users/{uid('k116_x')}/password", json={"new_password": "Yangi456!"})
_keyin = [ishlaydimi(X1), ishlaydimi(X2), sessiyalar("k116_x")]
check("P1 admin X ning parolini almashtirdi — X ning IKKALA qurilmasi chiqarildi (401), sessiya 0 (asl: ishlayverardi)",
      _r.status_code == 200 and _oldin == [200, 200, 2] and _keyin == [401, 401, 0], (_r.status_code, _oldin, _keyin))
check("P2 X yangi parol bilan kiradi, eskisi bilan — yo'q", kirdimi(kir(mijoz(), "k116_x", "Yangi456!"))
      and not kirdimi(kir(mijoz(), "k116_x", "Parol123!")))
check("P3 admin sessiyasi o'zgarmadi", ishlaydimi(ADM) == 200)
Y1, Y2 = mijoz(), mijoz()
check("P4 Y ikki qurilmada kirdi", kirdimi(kir(Y1, "k116_y")) and kirdimi(kir(Y2, "k116_y")))
_r = req(Y1, "post", f"/api/users/{uid('k116_y')}/password", json={"new_password": "Yangi789!", "current_password": "xato"})
check("P5 o'z parolida joriy parol noto'g'ri — 400 «Joriy parol noto'g'ri», hech kim chiqarilmadi",
      _r.status_code == 400 and "noto'g'ri" in str(js(_r).get("detail")) and [ishlaydimi(Y1), ishlaydimi(Y2)] == [200, 200],
      (_r.status_code, js(_r)))
_r = req(Y1, "post", f"/api/users/{uid('k116_y')}/password", json={"new_password": "Yangi789!", "current_password": "Parol123!"})
check("P6 Y o'z parolini almashtirdi — JORIY qurilma ishlaydi, boshqasi chiqarildi (asl: ikkalasi ham ishlardi)",
      _r.status_code == 200 and [ishlaydimi(Y1), ishlaydimi(Y2)] == [200, 401] and sessiyalar("k116_y") == 1,
      (_r.status_code, ishlaydimi(Y1), ishlaydimi(Y2), sessiyalar("k116_y")))
BK = mijoz()
kir(BK, "k116_bk")
_s0 = sessiyalar("k116_admin")
_r = req(BK, "post", f"/api/users/{uid('k116_admin')}/password", json={"new_password": "Buzgunchi1"})
check("P7 B korxona admini A ning parolini almashtira olmaydi (404) — A ning sessiyalari joyida",
      _r.status_code == 404 and sessiyalar("k116_admin") == _s0 and ishlaydimi(ADM) == 200, (_r.status_code, _s0))
_r = req(ADM, "post", f"/api/users/{uid('k116_x')}/password", json={"new_password": "123"})
check("P8 qisqa parol — 400, hech narsa o'zgarmadi", _r.status_code == 400 and kirdimi(kir(mijoz(), "k116_x", "Yangi456!")),
      (_r.status_code, js(_r)))

# ══════════════════════════════════════════════════════════════
section("H. Hodim PIN i almashtirilganda panel kirishi yopiladi")
# ══════════════════════════════════════════════════════════════
_r = req(ADM, "post", f"/api/employees/{EMP_ID}/set-login", data={"phone": "+998901160116", "pin": "1234"})
check("H0 hodimga telefon + PIN berildi", _r.status_code == 200, (_r.status_code, js(_r)))
HD = mijoz("203.0.113.103")
_r = req(HD, "post", "/hodim/login", data={"phone": "+998901160116", "pin": "1234", "korxona": "K116A"}, follow_redirects=False)
_hk = req(HD, "get", "/api/hodim/my-requests").status_code
check("H1 hodim panelga kirdi", _r.status_code in (302, 303) and _hk == 200, (_r.status_code, _hk))
_r = req(ADM, "post", f"/api/employees/{EMP_ID}/set-login", data={"phone": "+998901160116", "pin": "5678"})
_d = SessionLocal()
try:
    _es = _d.query(EmployeeSession).filter(EmployeeSession.employee_id == EMP_ID).count()
finally:
    _d.close()
_hk2 = req(HD, "get", "/api/hodim/my-requests").status_code
check("H2 PIN almashtirildi — hodimning eski kirishi yopildi (401, sessiya 0) (asl: 14 kun ishlardi)",
      _r.status_code == 200 and _hk2 == 401 and _es == 0, (_r.status_code, _hk2, _es))
_r = req(mijoz("203.0.113.103"), "post", "/hodim/login", data={"phone": "+998901160116", "pin": "5678", "korxona": "K116A"},
         follow_redirects=False)
check("H3 yangi PIN bilan kiradi", _r.status_code in (302, 303), _r.status_code)

# ══════════════════════════════════════════════════════════════
section("X. Xatolar")
# ══════════════════════════════════════════════════════════════
SERVER.should_exit = True
TH.join(timeout=10)
_5xx = [x for x in HOLATLAR if x[1] >= 500]
check("X1 API 5xx yo'q", not _5xx, _5xx[:5])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
