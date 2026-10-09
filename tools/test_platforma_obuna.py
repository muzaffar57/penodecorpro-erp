#!/usr/bin/env python3
"""
test_platforma_obuna.py — kech111 darvozasi: PLATFORMA ADMIN PANELI (egasi QARORLARI kech109 / kech110 / kech111).

NIMA UCHUN KERAK (asl kod `286ca94` da shu test bilan O'LCHANDI): platformada korxonani BLOKLASH / OCHISH, obuna
MUDDATI, eslatma, avtomatik bloklash, SINOV davri, platforma raqamlari va hamma korxonalar xatolari UMUMAN yo'q edi
(faqat ro'yxat, korxona qo'shish, parol tiklash); yuklangan fayllar (`/static/uploads/…`) LOGINSIZ va korxona
tekshiruvisiz ochilardi — havolasi bor har kim (boshqa korxona ham) chizma / rasmni ko'rardi.

QARORLAR: bloklash — kirish, API, hodim paneli, Telegram bot yopiladi, ma'lumot O'CHMAYDI, platforma egasining o'z
korxonasi bloklanmaydi; muddatdan 3 kun keyin avtomatik yopiladi (kirishda ham hisoblanadi); avtomatik bloklanganni
uzaytirmasdan «Ochish» — 3 kunlik imtiyoz; eslatma — egasiga Telegram + mijoz dasturida (7 kun qolganda faqat
adminga, muddat tugagach — hammaga); uzaytirish «Aralash» (tugamagan — eski sanadan, tugagan — bugundan); yangi
korxona — 30 kunlik sinov; aloqa telefoni — platforma sozlamasi.

BO'LIMLAR: H — `obuna.holat` chegaralari; U — uzaytirish sanasi; A — ruxsat (faqat platforma admini); Y — yangi
korxona (sinov); B — qo'lda bloklash (login, API, sessiyalar, hodim paneli, bot, A ta'sirlanmaydi, jurnal); O — ochish
va imtiyoz; D — muddat o'tgani HAR SO'ROVDA (sahifa, API, hodim paneli); K — kunlik tekshiruv (bosqichlar bir marta,
avtomatik blok bazaga, egasi korxonasi o'tkaziladi); N — mijoz ogohlantirishi (banner); T — aloqa telefoni;
R — raqamlar va faollik; X — xatolar ro'yxati; F — fayllar himoyasi va logotip; M — migratsiya / sxema; S — statik.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
    python3 tools/test_platforma_obuna.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_platforma_obuna.py
Asl kodga qarshi QULAMAYDI (HTTP istisno → 599, yangi nomlar `getattr`). Chiqish kodi 0 — hammasi o'tdi.
"""
import os
import sys
import inspect
import tempfile
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "platforma_obuna_test"
_T = tempfile.mkdtemp()
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'platforma_obuna_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import date, datetime, timedelta     # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import database                                # noqa: E402
try:
    with contextlib.redirect_stdout(_quiet):
        import obuna                               # noqa: E402
except Exception:                                  # noqa: BLE001 — asl kodda modul yo'q
    obuna = None

from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, UserSession, Employee, EmployeeSession, PayType, Master,   # noqa: E402
                    ActivityLog, LoginHistory, Inventory, CompanySetting)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)   # lambda — asl kodda javob shakli boshqa bo'lsa QULAMASIN
    except Exception:                      # noqa: BLE001
        cond = False
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:500]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.headers = {}
        self.content = b""

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def matn(r):
    """Sahifa matni — HTML belgilarisiz (Jinja `'` ni `&#39;` qiladi)."""
    import html as _html
    try:
        return _html.unescape(r.text)
    except Exception:                      # noqa: BLE001
        return ""


def roy(r):
    """Javob ro'yxat bo'lsa — ro'yxat, aks holda [] (401 / 404 JSON lug'ati ustida aylanib test QULAMASIN)."""
    d = js(r)
    return [x for x in d if isinstance(x, dict)] if isinstance(d, list) else []


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


def ob(nom, *a, **k):
    """obuna.<nom>(...) — asl kodda modul / funksiya yo'q bo'lsa QULAMAYDI (None + belgi)."""
    f = getattr(obuna, nom, None) if obuna is not None else None
    if f is None:
        return "__YOQ__"
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return e


BUGUN = date(2026, 10, 10)                 # sinov "bugun"i (obuna.bugun almashtiriladi)
if obuna is not None:
    obuna.bugun = lambda: BUGUN


def bugun_qil(d):
    global BUGUN
    BUGUN = d


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    parol = PAROL.get(login, "Parol123!")
    r = req(c, "post", "/login", data={"username": login, "password": parol}, follow_redirects=False)
    return c, r


def korxona(cid):
    s = SessionLocal()
    try:
        return s.query(Company).filter(Company.id == cid).first()
    finally:
        s.close()


def ustun_yoz(cid, **k):
    """Korxona qatoriga to'g'ridan-to'g'ri yozish (fikstura: muddat / holat). Yangi ustun yo'q (asl) — o'tkaziladi."""
    s = SessionLocal()
    try:
        c = s.query(Company).filter(Company.id == cid).first()
        for a, v in k.items():
            if hasattr(Company, a):
                setattr(c, a, v)
        s.commit()
    finally:
        s.close()


def sessiyalar(cid):
    s = SessionLocal()
    try:
        u = s.query(UserSession).join(User, User.id == UserSession.user_id).filter(User.company_id == cid).count()
        e = (s.query(EmployeeSession).join(Employee, Employee.id == EmployeeSession.employee_id)
             .filter(Employee.company_id == cid).count())
        return u, e
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════
# Fikstura: A (1, platforma egasi) — platforma admini PLAT + oddiy admin A_ADM; B, C, D — platformadan yaratiladi
# ══════════════════════════════════════════════════════════════
PAROL = {}
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "PO_PLAT", "Parol123!", UserRole.ADMIN, "Platforma Egasi", company_id=1)
    auth.create_user(_db, "PO_A_ADM", "Parol123!", UserRole.ADMIN, "A korxona admini", company_id=1)
_db.query(User).filter(User.username == "PO_PLAT").first().is_platform_admin = True
_db.query(User).filter(User.username == "PO_A_ADM").first().is_platform_admin = False
_c1 = _db.query(Company).filter(Company.id == 1).first()
_c1.phone = "+998 97 111 22 33"
_db.commit()
_db.close()

CP, _r = mijoz("PO_PLAT")
CA, _ra = mijoz("PO_A_ADM")
C0 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)

section("Y. Yangi korxona — 30 kunlik sinov davri")
ID = {}
for kod, login in (("B", "po_b_admin"), ("C", "po_c_admin"), ("D", "po_d_admin"), ("E", "po_e_admin")):
    r = req(CP, "post", "/api/platform/companies", data={"name": f"PO {kod} korxona", "admin_username": login})
    d = js(r) or {}
    ID[kod] = (d.get("company") or {}).get("id")
    PAROL[login] = (d.get("admin") or {}).get("password") or "x"
check("Y1 platformadan 4 korxona yaratildi (200)", all(ID.values()), ID)
_cb = korxona(ID["B"]) if ID.get("B") else None
check("Y2 yangi korxona — sinov davri 30 kun (obuna_tugash = bugun + 30, turi 'sinov', boshi = bugun)",
      _cb is not None and getattr(_cb, "obuna_tugash", None) == BUGUN + timedelta(days=30)
      and getattr(_cb, "obuna_turi", None) == "sinov" and getattr(_cb, "obuna_boshi", None) == BUGUN,
      (getattr(_cb, "obuna_tugash", None), getattr(_cb, "obuna_turi", None)))
check("Y3 javobda sinov muddati", ((js(r) or {}).get("company") or {}).get("obuna_turi") == "sinov", js(r))
check("Y4 platforma egasi korxonasi (1) — muddatsiz, bloklanmagan (hech narsa to'ldirilmagan)",
      getattr(korxona(1), "obuna_tugash", "x") is None and getattr(korxona(1), "bloklangan_at", "x") is None)

# B korxonasi: menejer, hodim (PIN), usta (Telegram)
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    if ID.get("B"):
        auth.create_user(_db, "po_b_men", "Parol123!", UserRole.MANAGER, "B menejer", company_id=ID["B"])
        _db.add(Employee(company_id=ID["B"], name="B hodim", phone="+998900000001", pin_hash=auth.hash_pin("4321"),
                         is_active=True, pay_type=PayType.FIXED))
        _db.add(Master(company_id=ID["B"], name="B usta", phone="+998900000002", telegram_id="777001", is_active=True))
        _db.add(Master(company_id=1, name="A usta", phone="+998900000003", telegram_id="777002", is_active=True))
_db.commit()
_db.close()
PAROL["po_b_men"] = "Parol123!"
KOD_B = getattr(korxona(ID["B"]), "code", "") if ID.get("B") else ""


def hodim_kir():
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/hodim/login", data={"phone": "+998900000001", "pin": "4321", "korxona": KOD_B},
            follow_redirects=False)
    return c, r


# ══════════════════════════════════════════════════════════════
section("H. obuna.holat — chegaralar (Toshkent kuni; E = oxirgi to'langan kun)")
# ══════════════════════════════════════════════════════════════


class _K:
    def __init__(self, **k):
        self.obuna_tugash = self.imtiyoz_gacha = self.obuna_boshi = self.bloklangan_at = None
        self.blok_sabab = self.blok_avtomatik = self.bloklagan = self.obuna_turi = None
        for a, v in k.items():
            setattr(self, a, v)


E0 = date(2026, 11, 15)
_h = {}
for farq in (-8, -7, -1, 0, 1, 3, 4):
    _h[farq] = ob("holat", _K(obuna_tugash=E0, obuna_boshi=E0 - timedelta(days=30)), E0 + timedelta(days=farq))
_ok = all(isinstance(v, dict) for v in _h.values())
check("H1 E−8 — 'faol', qolgan 8", _ok and _h[-8]["bosqich"] == "faol" and _h[-8]["qolgan_kun"] == 8, _h.get(-8))
check("H2 E−7 — 'yaqin' (7 kun qolganda sariq)", _ok and _h[-7]["bosqich"] == "yaqin", _h.get(-7))
check("H3 E (oxirgi kun) — 'yaqin', qolgan 0, bloklanmagan", _ok and _h[0]["bosqich"] == "yaqin"
      and _h[0]["qolgan_kun"] == 0 and not _h[0]["bloklangan"], _h.get(0))
check("H4 E+1 — 'otgan' (imtiyoz), kirish ochiq, yopilish E+4 (3 kundan keyin)", _ok and _h[1]["bosqich"] == "otgan"
      and not _h[1]["bloklangan"] and _h[1]["yopilish_kuni"] == E0 + timedelta(days=4) and _h[1]["yopilishga"] == 3,
      _h.get(1))
check("H5 E+3 — hali ochiq (imtiyozning oxirgi kuni), yopilishga 1", _ok and not _h[3]["bloklangan"]
      and _h[3]["yopilishga"] == 1, _h.get(3))
check("H6 E+4 — AVTOMATIK bloklangan (bazaga yozilmagan bo'lsa ham)", _ok and _h[4]["bloklangan"]
      and _h[4]["avtomatik"] and _h[4]["bosqich"] == "bloklangan", _h.get(4))
_hi = ob("holat", _K(obuna_tugash=E0, imtiyoz_gacha=E0 + timedelta(days=10)), E0 + timedelta(days=10))
_hj = ob("holat", _K(obuna_tugash=E0, imtiyoz_gacha=E0 + timedelta(days=10)), E0 + timedelta(days=11))
check("H7 imtiyoz_gacha — shu kungacha ochiq, keyingi kun yana avtomatik yopiladi",
      isinstance(_hi, dict) and not _hi["bloklangan"] and isinstance(_hj, dict) and _hj["bloklangan"] and _hj["avtomatik"],
      (_hi, _hj))
_hm = ob("holat", _K(), E0)
check("H8 muddatsiz (NULL) — 'muddatsiz', hech qachon bloklanmaydi", isinstance(_hm, dict)
      and _hm["bosqich"] == "muddatsiz" and not _hm["bloklangan"], _hm)
_hq = ob("holat", _K(obuna_tugash=E0, bloklangan_at=datetime(2026, 11, 1), blok_sabab="To'lov qilinmagan",
                     blok_avtomatik=False), E0 - timedelta(days=20))
check("H9 qo'lda bloklangan (muddat hali bor) — bloklangan, avtomatik EMAS, sabab", isinstance(_hq, dict)
      and _hq["bloklangan"] and not _hq["avtomatik"] and _hq["sabab"] == "To'lov qilinmagan", _hq)
_hs = ob("holat", _K(obuna_tugash=E0, obuna_turi="sinov", obuna_boshi=E0 - timedelta(days=30)), E0 - timedelta(days=10))
check("H10 sinov davri belgisi va davr uzunligi (chiziq uchun)", isinstance(_hs, dict) and _hs["sinov"]
      and _hs["davr_kun"] == 30 and _hs["qolgan_kun"] == 10, _hs)

# ══════════════════════════════════════════════════════════════
section("U. Uzaytirish sanasi — «Aralash» qoida (egasi QARORI kech111)")
# ══════════════════════════════════════════════════════════════
_u1 = ob("uzaytirish_sanasi", _K(obuna_tugash=date(2026, 10, 15)), oylar=1, kun=date(2026, 10, 1))
_u2 = ob("uzaytirish_sanasi", _K(obuna_tugash=date(2026, 9, 20)), oylar=1, kun=date(2026, 9, 29))
_u3 = ob("uzaytirish_sanasi", _K(), oylar=3, kun=date(2026, 9, 29))
_u4 = ob("uzaytirish_sanasi", _K(obuna_tugash=date(2027, 1, 31)), oylar=1, kun=date(2027, 1, 10))
_u5 = ob("oy_qosh", date(2027, 12, 31), 2)
_u6 = ob("uzaytirish_sanasi", _K(obuna_tugash=date(2026, 9, 29)), oylar=12, kun=date(2026, 9, 29))
check("U1 muddat tugamagan (15.10, bugun 01.10) +1 oy → 15.11 (eski sanadan davom)", _u1 == date(2026, 11, 15), _u1)
check("U2 muddat tugagan (20.09, bugun 29.09) +1 oy → 29.10 (bugundan)", _u2 == date(2026, 10, 29), _u2)
check("U3 muddatsiz +3 oy → bugundan (29.12)", _u3 == date(2026, 12, 29), _u3)
check("U4 31.01 + 1 oy → 28.02 (oy oxiri siqiladi)", _u4 == date(2027, 2, 28), _u4)
check("U5 oy_qosh: 31.12.2027 + 2 oy → 29.02.2028 (kabisa, yil o'tishi)", _u5 == date(2028, 2, 29), _u5)
check("U6 oxirgi kunda (E = bugun) +12 oy → E dan (29.09.2027)", _u6 == date(2027, 9, 29), _u6)
_u7 = ob("uzaytirish_sanasi", _K(), sana="2026-12-31", kun=date(2026, 9, 29))
_u8 = ob("uzaytirish_sanasi", _K(), sana="2026-09-28", kun=date(2026, 9, 29))
_u9 = ob("uzaytirish_sanasi", _K(), oylar=2, kun=date(2026, 9, 29))
check("U7 aniq sana → o'sha kun", _u7 == date(2026, 12, 31), _u7)
check("U8 aniq sana bugundan oldin — rad (ObunaXato)", isinstance(_u8, ValueError) and "oldin" in str(_u8), _u8)
check("U9 ro'yxatda yo'q oy (+2) — rad", isinstance(_u9, ValueError), _u9)

# ══════════════════════════════════════════════════════════════
section("A. Ruxsat — platforma amallari FAQAT platforma admini")
# ══════════════════════════════════════════════════════════════
_b = ID.get("B") or 0
_yollar = [("get", "/api/platform/companies", {}), ("get", "/api/platform/summary", {}),
           ("post", f"/api/platform/companies/{_b}/block", {"data": {"sabab": "Boshqa"}}),
           ("post", f"/api/platform/companies/{_b}/unblock", {}),
           ("post", f"/api/platform/companies/{_b}/extend", {"data": {"oy": "1"}}),
           ("post", "/api/platform/contact-phone", {"data": {"telefon": "1"}}),
           ("get", "/api/platform/errors", {})]
_n401 = [(m, y, req(C0, m, y, **k).status_code) for m, y, k in _yollar]
_n403 = [(m, y, req(CA, m, y, **k).status_code) for m, y, k in _yollar]
check("A1 kirmagan — 7 platforma API ning hammasi 401", all(s == 401 for _, _, s in _n401), _n401)
check("A2 KORXONA admini (platforma emas) — hammasi 403", all(s == 403 for _, _, s in _n403), _n403)
check("A3 B korxona hech narsa o'zgarmadi (A2 dagi bloklash / uzaytirish urinishlaridan keyin)",
      getattr(korxona(_b), "bloklangan_at", None) is None
      and getattr(korxona(_b), "obuna_tugash", None) == BUGUN + timedelta(days=30), korxona(_b))
r = req(CA, "get", "/platforma", follow_redirects=False)
check("A4 /platforma — oddiy admin bosh sahifaga (302 /)", r.status_code == 302 and r.headers.get("location") == "/",
      (r.status_code, r.headers.get("location")))
r = req(C0, "get", "/platforma", follow_redirects=False)
check("A5 /platforma — kirmagan /login ga", r.status_code == 302 and "/login" in (r.headers.get("location") or ""),
      (r.status_code, r.headers.get("location")))
r = req(CP, "get", "/platforma")
check("A6 /platforma — platforma admini 200, kartochkalar va modal", r.status_code == 200 and 'id="plKartalar"' in r.text
      and 'id="plModal"' in r.text, r.status_code)
r = req(CA, "get", "/orders")
check("A7 oddiy adminning chap menyusida «Platforma» havolasi YO'Q", r.status_code == 200 and 'href="/platforma"' not in r.text,
      r.status_code)
r = req(CP, "get", "/orders")
check("A8 platforma admini menyusida «Platforma» havolasi BOR", r.status_code == 200 and 'href="/platforma"' in r.text,
      r.status_code)

# ══════════════════════════════════════════════════════════════
section("B. Qo'lda BLOKLASH — kirish, API, sessiyalar, hodim paneli, bot; A ta'sirlanmaydi")
# ══════════════════════════════════════════════════════════════
CB, _rb = mijoz("po_b_admin")
CBM, _rbm = mijoz("po_b_men")
CH, _rh = hodim_kir()
check("B0 B admin, menejer va hodim kirdi (302)", _rb.status_code == 302 and _rbm.status_code == 302
      and _rh.status_code == 302, (_rb.status_code, _rbm.status_code, _rh.status_code))
check("B0b B da 2 foydalanuvchi + 1 hodim sessiyasi", sessiyalar(_b) == (2, 1), sessiyalar(_b))
r = req(CP, "post", f"/api/platform/companies/{_b}/block", data={"sabab": "Noma'lum sabab"})
check("B1 ro'yxatda yo'q sabab — 400, hech narsa o'zgarmaydi", r.status_code == 400
      and getattr(korxona(_b), "bloklangan_at", None) is None, (r.status_code, r.text[:160]))
r = req(CP, "post", "/api/platform/companies/1/block", data={"sabab": "To'lov qilinmagan"})
check("B2 platforma egasining o'z korxonasi — 400 'bloklanmaydi'", r.status_code == 400 and "bloklanmaydi" in r.text,
      (r.status_code, r.text[:160]))
r = req(CP, "post", "/api/platform/companies/999999/block", data={"sabab": "To'lov qilinmagan"})
check("B3 mavjud bo'lmagan korxona — 404", r.status_code == 404, r.status_code)
r = req(CP, "post", f"/api/platform/companies/{_b}/block",
        data={"sabab": "To'lov qilinmagan", "izoh": "Sentabr obunasi to'lanmagan"})
d = js(r) or {}
check("B4 bloklash 200 — ochiq sessiyalar hisoblandi: 2 foydalanuvchi va 1 hodim (keyingi so'rovda yopiladi)", r.status_code == 200
      and d.get("sessiyalar") == 2 and d.get("hodim_sessiyalari") == 1, (r.status_code, r.text[:200]))
check("B5 bazada: sessiyalar HALI o'chirilmagan (K112-2 — keyingi so'rovda SABAB bilan yopiladi), bloklangan_at, sabab, "
      "izoh, kim, avtomatik=False", sessiyalar(_b) == (2, 1)
      and getattr(korxona(_b), "bloklangan_at", None) is not None
      and getattr(korxona(_b), "blok_sabab", None) == "To'lov qilinmagan"
      and getattr(korxona(_b), "blok_izoh", None) == "Sentabr obunasi to'lanmagan"
      and "PO_PLAT" in (getattr(korxona(_b), "bloklagan", None) or "")
      and getattr(korxona(_b), "blok_avtomatik", None) is False, (sessiyalar(_b), korxona(_b)))
r = req(CP, "post", f"/api/platform/companies/{_b}/block", data={"sabab": "Boshqa"})
check("B6 ikkinchi marta bloklash — 400 'allaqachon'", r.status_code == 400 and "allaqachon" in r.text, r.status_code)
r = req(CB, "get", "/orders", follow_redirects=False)
check("B7 ochiq sahifa sessiyasi — /login?b=1 ga (qo'lda bloklangan), cookie o'chiriladi", r.status_code == 302
      and r.headers.get("location") == "/login?b=1" and "session_token" in (r.headers.get("set-cookie") or ""),
      (r.status_code, r.headers.get("location"), r.headers.get("set-cookie")))
r = req(C0, "get", "/login?b=1")
check("B7b o'sha kirish sahifasida — sabab (to'xtatilgan) va aloqa telefoni (sababsiz chiqarib yuborilmaydi)",
      r.status_code == 200 and 'id="blokXabari"' in r.text and "vaqtincha to'xtatilgan" in matn(r)
      and "+998 97 111 22 33" in r.text and "Obuna muddati tugagan" not in matn(r), r.text[-300:])
check("B7c admin sessiyasi bazadan o'chirildi (menejer va hodimniki — hali ochiq)", sessiyalar(_b) == (1, 1), sessiyalar(_b))
r = req(CBM, "get", "/api/orders")
check("B8 menejerning ochiq sessiyasi — API 403, JSON sababi bilan (ma'lumot yo'q)", r.status_code == 403
      and "vaqtincha to'xtatilgan" in ((js(r) or {}).get("detail") or "") and not isinstance(js(r), list),
      (r.status_code, r.text[:160]))
check("B8b menejer sessiyasi ham o'chirildi", sessiyalar(_b) == (0, 1), sessiyalar(_b))
r = req(CB, "get", "/api/orders")
check("B8c admin (cookie o'chgan) — API 401/403, ma'lumot yo'q", r.status_code in (401, 403) and not isinstance(js(r), list),
      (r.status_code, r.text[:120]))
_s = SessionLocal()
_lh0 = _s.query(LoginHistory).filter(LoginHistory.username == "po_b_admin", LoginHistory.success == False).count()  # noqa: E712
_s.close()
CB, r = mijoz("po_b_admin")
check("B9 to'g'ri parol bilan qayta kirish — sessiya YO'Q, sahifada blok xabari va aloqa telefoni",
      r.status_code == 200 and 'id="blokXabari"' in r.text and "vaqtincha to'xtatilgan" in matn(r)
      and "+998 97 111 22 33" in r.text and "session_token" not in (r.headers.get("set-cookie") or ""),
      (r.status_code, r.text[-300:]))
_s = SessionLocal()
_lh1 = _s.query(LoginHistory).filter(LoginHistory.username == "po_b_admin", LoginHistory.success == False).count()  # noqa: E712
_s.close()
check("B10 blok sababli rad — 'noto'g'ri urinish' deb YOZILMAYDI (rate-limit mijozni qulflamasin)", _lh1 == _lh0,
      (_lh0, _lh1))
_Cx, r = mijoz("po_b_admin") if False else (None, req(TestClient(main.app, base_url="https://testserver",
                                                                raise_server_exceptions=False),
                                                     "post", "/login", data={"username": "po_b_admin", "password": "noto'g'ri"}))
check("B11 NOTO'G'RI parol — oddiy xato (blok holati oshkor qilinmaydi)", r.status_code == 200
      and "vaqtincha to'xtatilgan" not in matn(r) and "noto'g'ri" in matn(r), r.text[-200:])
CH2, r = hodim_kir()
check("B12 hodim paneli: to'g'ri PIN — kirilmaydi, blok xabari", r.status_code == 200 and "vaqtincha to'xtatilgan" in matn(r)
      and 'id="blokXabari"' in r.text, (r.status_code, r.text[-200:]))
r = req(CH, "get", "/hodim", follow_redirects=False)
check("B13 hodimning ochiq sessiyasi — /hodim/login?b=1 ga (sabab bilan)", r.status_code == 302
      and (r.headers.get("location") or "") == "/hodim/login?b=1", (r.status_code, r.headers.get("location")))
check("B13b hodim sessiyasi ham o'chirildi — B da ochiq sessiya qolmadi", sessiyalar(_b) == (0, 0), sessiyalar(_b))
_s = SessionLocal()
_mb = main._master_by_chat_id(_s, "777001")
_ma = main._master_by_chat_id(_s, "777002")
_s.close()
check("B14 Telegram: B ustasi topilmaydi, sabab — blok xabari", _mb[0] is None and "vaqtincha to'xtatilgan" in (_mb[1] or ""),
      _mb)
check("B15 Telegram: A ustasi odatdagidek", _ma[0] is not None and getattr(_ma[0], "company_id", None) == 1 and _ma[1] is None,
      _ma)
r = req(CA, "get", "/api/orders")
check("B16 A korxona (oddiy admin) ishlaydi — 200", r.status_code == 200, r.status_code)
r = req(CP, "get", "/api/platform/companies")
_bq = [x for x in roy(r) if x.get("id") == _b]
check("B17 ro'yxatda B — 'bloklangan', sabab, izoh (faqat platforma ko'radi)", lambda: _bq and _bq[0]["holat"]["bosqich"] == "bloklangan"
      and _bq[0]["holat"]["sabab"] == "To'lov qilinmagan" and _bq[0].get("blok_izoh") == "Sentabr obunasi to'lanmagan", _bq)
_s = SessionLocal()
_jb = [a for a in _s.query(ActivityLog).filter(ActivityLog.action == "blocked").all()]
_s.close()
check("B18 B ning audit jurnalida 'blocked' (korxona B, kim — platforma admini); A da yo'q",
      len(_jb) == 1 and _jb[0].company_id == _b and "PO_PLAT" in (_jb[0].performed_by or ""), [(a.company_id, a.performed_by) for a in _jb])
r = req(CP, "get", "/api/orders")
check("B19 platforma admini o'zi ishlaydi (200)", r.status_code == 200, r.status_code)
ustun_yoz(1, bloklangan_at=datetime(2026, 10, 1), blok_sabab="Boshqa", blok_avtomatik=False)
_rp, _ra2 = req(CP, "get", "/api/orders"), req(CA, "get", "/api/orders")
ustun_yoz(1, bloklangan_at=None, blok_sabab=None, blok_avtomatik=None)
check("B19b platforma admini HECH QACHON bloklanmaydi (korxonasi bazada bloklangan bo'lsa ham 200); shu korxonaning oddiy "
      "admini — 403", _rp.status_code == 200 and _ra2.status_code == 403, (_rp.status_code, _ra2.status_code))
CA, _ra = mijoz("PO_A_ADM")

# ══════════════════════════════════════════════════════════════
section("O. OCHISH va 3 kunlik imtiyoz")
# ══════════════════════════════════════════════════════════════
r = req(CP, "post", f"/api/platform/companies/{_b}/unblock")
check("O1 ochish 200 — muddat hali bor, imtiyoz yo'q", r.status_code == 200 and (js(r) or {}).get("imtiyoz_gacha") is None
      and getattr(korxona(_b), "bloklangan_at", "x") is None and getattr(korxona(_b), "blok_sabab", "x") is None,
      (r.status_code, r.text[:200]))
CB, r = mijoz("po_b_admin")
check("O2 B yana kiradi (302) va sahifa ochiladi", r.status_code == 302 and req(CB, "get", "/api/orders").status_code == 200,
      r.status_code)
r = req(CP, "post", f"/api/platform/companies/{_b}/unblock")
check("O3 bloklanmagan korxonani ochish — 400", r.status_code == 400 and "bloklanmagan" in r.text, r.status_code)
_s = SessionLocal()
_jo = _s.query(ActivityLog).filter(ActivityLog.action == "unblocked", ActivityLog.company_id == _b).count()
_s.close()
check("O4 audit: 'unblocked' B jurnalida (1)", _jo == 1, _jo)
# C: muddat 20.09, bugun 10.10 → avtomatik bloklangan (hisobda) → ochish → imtiyoz 13.10
_c = ID.get("C") or 0
ustun_yoz(_c, obuna_tugash=date(2026, 9, 20), obuna_turi="obuna")
_hc = ob("korxona_holati", SessionLocal(), _c)
check("O5 C (muddat 20.09, bugun 10.10) — hisobda avtomatik bloklangan",
      isinstance(_hc, tuple) and _hc[1] and _hc[1]["bloklangan"] and _hc[1]["avtomatik"], _hc)
r = req(CP, "post", f"/api/platform/companies/{_c}/unblock")
check("O6 ochish — 3 kunlik imtiyoz 13.10 gacha", r.status_code == 200 and (js(r) or {}).get("imtiyoz_gacha") == "2026-10-13",
      (r.status_code, r.text[:200]))
CC, r = mijoz("po_c_admin")
check("O7 imtiyozda C kiradi (302)", r.status_code == 302, r.status_code)
bugun_qil(date(2026, 10, 13))
check("O8 13.10 (imtiyozning oxirgi kuni) — hali ishlaydi", req(CC, "get", "/api/orders").status_code == 200)
bugun_qil(date(2026, 10, 14))
r = req(CC, "get", "/api/orders")
check("O9 14.10 — yana AVTOMATIK yopildi: API 403, sabab 'Obuna muddati tugagan'", r.status_code == 403
      and "Obuna muddati tugagan" in r.text, (r.status_code, r.text[:200]))
bugun_qil(date(2026, 10, 10))

# ══════════════════════════════════════════════════════════════
section("D. Muddat o'tgani HAR SO'ROVDA (kunlik ish yurmagan bo'lsa ham) — sahifa, API, hodim paneli")
# ══════════════════════════════════════════════════════════════
_d = ID.get("D") or 0
CD, _rd = mijoz("po_d_admin")
check("D0 D kirdi", _rd.status_code == 302, _rd.status_code)
ustun_yoz(_d, obuna_tugash=date(2026, 10, 6), obuna_turi="obuna")      # E+4 = 10.10 = bugun → yopiq
r = req(CD, "get", "/orders", follow_redirects=False)
check("D1 sahifa — /login?b=2 (muddat sababli) ga, cookie o'chiriladi", r.status_code == 302
      and r.headers.get("location") == "/login?b=2" and "session_token" in (r.headers.get("set-cookie") or ""),
      (r.status_code, r.headers.get("location"), r.headers.get("set-cookie")))
check("D2 shu sessiya bazadan o'chirildi", sessiyalar(_d)[0] == 0, sessiyalar(_d))
r = req(C0, "get", "/login?b=2")
check("D3 /login?b=2 — xabar: to'xtatilgan + 'Obuna muddati tugagan' + telefon", r.status_code == 200
      and "vaqtincha to'xtatilgan" in matn(r) and "Obuna muddati tugagan" in matn(r) and "+998 97 111 22 33" in r.text,
      r.text[-300:])
r = req(C0, "get", "/login?b=zz")
check("D4 /login?b=<boshqa> — xabar yo'q", r.status_code == 200 and "vaqtincha to'xtatilgan" not in matn(r))
ustun_yoz(_d, obuna_tugash=date(2026, 10, 7))                           # E+3 = bugun → ochiq
CD, _rd = mijoz("po_d_admin")
check("D5 imtiyozning oxirgi kuni (E+3) — kirish 302", _rd.status_code == 302, _rd.status_code)
ustun_yoz(_d, obuna_tugash=date(2026, 10, 6))
r = req(CD, "get", "/api/projects")
check("D6 API — 403, JSON sababi bilan (belgi sarlavhasi javobda yo'q)", r.status_code == 403
      and "vaqtincha to'xtatilgan" in ((js(r) or {}).get("detail") or "")
      and "x-korxona-bloklangan" not in {k.lower() for k in r.headers.keys()}, (r.status_code, r.text[:200], dict(r.headers)))
r = req(CD, "get", "/login")
check("D7 /login ga to'g'ridan-to'g'ri (sessiya o'chgan) — oddiy sahifa (halqa yo'q)", r.status_code == 200, r.status_code)
# hodim paneli: B hodimi, B ga muddat qo'yamiz
ustun_yoz(_b, obuna_tugash=date(2026, 12, 31))
CH, _rh = hodim_kir()
check("D8 B hodimi kirdi", _rh.status_code == 302, _rh.status_code)
ustun_yoz(_b, obuna_tugash=date(2026, 10, 1))
r = req(CH, "get", "/hodim", follow_redirects=False)
check("D9 hodim paneli — /hodim/login?b=2 ga, emp cookie o'chiriladi", r.status_code == 302
      and r.headers.get("location") == "/hodim/login?b=2" and "emp_session_token" in (r.headers.get("set-cookie") or ""),
      (r.status_code, r.headers.get("location")))
r = req(C0, "get", "/hodim/login?b=2")
check("D10 /hodim/login?b=2 — blok xabari", r.status_code == 200 and "vaqtincha to'xtatilgan" in matn(r), r.text[-200:])
CH, _rh = hodim_kir()
r = req(CH, "get", "/api/hodim/my-requests")
check("D11 hodim API (muddat o'tgan) — kirish ham yo'q (200 sahifa xabari yoki 401/403)",
      _rh.status_code == 200 and "vaqtincha to'xtatilgan" in matn(_rh) and r.status_code in (401, 403),
      (_rh.status_code, r.status_code))
ustun_yoz(_b, obuna_tugash=BUGUN + timedelta(days=30))

# ══════════════════════════════════════════════════════════════
section("K. Kunlik tekshiruv — avtomatik bloklash bazaga, egasiga eslatma (har bosqich BIR marta)")
# ══════════════════════════════════════════════════════════════
_e = ID.get("E") or 0
YUB = []
ustun_yoz(_e, obuna_tugash=date(2026, 10, 20), obuna_turi="obuna", eslatma_holati=None)
ustun_yoz(_b, obuna_tugash=None)
ustun_yoz(_c, obuna_tugash=None, imtiyoz_gacha=None)
ustun_yoz(_d, obuna_tugash=None)


def kt(d):
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            return ob("kunlik_tekshiruv", s, kun=d, yubor=YUB.append)
    finally:
        s.close()


_k0 = kt(date(2026, 10, 12))                                            # 8 kun qoldi — hech narsa
check("K1 8 kun qolganda — xabar yo'q", _k0 == [] and YUB == [], (_k0, YUB))
_k1 = kt(date(2026, 10, 13))                                            # 7 kun
check("K2 7 kun qolganda — '7' bosqich xabari (korxona nomi, sana)", len(YUB) == 1 and "PO E korxona" in YUB[0]
      and "7 kundan keyin" in YUB[0] and "20.10.2026" in YUB[0], YUB)
kt(date(2026, 10, 13))
kt(date(2026, 10, 15))
check("K3 shu kun qayta va 5 kun qolganda — TAKRORLANMAYDI", len(YUB) == 1, YUB)
kt(date(2026, 10, 19))
check("K4 1 kun qolganda — 'ERTAGA' xabari", len(YUB) == 2 and "ERTAGA" in YUB[1], YUB)
kt(date(2026, 10, 20))
check("K5 oxirgi kun — takror yo'q ('1' bosqich allaqachon)", len(YUB) == 2, YUB)
kt(date(2026, 10, 21))
check("K6 muddat o'tgan kun — 'tugadi' xabari (3 kundan keyin yopiladi, 24.10)", len(YUB) == 3 and "24.10.2026" in YUB[2]
      and "3 kundan keyin" in YUB[2], YUB)
CE, _re = mijoz("po_e_admin")
check("K7 imtiyozda E kira oladi", _re.status_code == 302, _re.status_code)
_k = kt(date(2026, 10, 24))
_ce = korxona(_e)
check("K8 E+4 — BAZADA avtomatik bloklandi (bloklangan_at, avtomatik, sabab, 'Tizim'), egasiga xabar",
      getattr(_ce, "bloklangan_at", None) is not None and getattr(_ce, "blok_avtomatik", None) is True
      and getattr(_ce, "blok_sabab", None) == getattr(obuna, "AVTO_SABAB", "?")
      and "Tizim" in (getattr(_ce, "bloklagan", None) or "") and len(YUB) == 4 and "AVTOMATIK yopildi" in YUB[3],
      (_ce, YUB[3:]))
_se9 = sessiyalar(_e)[0]
check("K9 avtomatik bloklashda sessiyalar O'CHIRILMAYDI (K112-2 — keyingi so'rovda sabab bilan)", _se9 >= 1, _se9)
r = req(CE, "get", "/orders", follow_redirects=False)
check("K9b E ning ochiq sessiyasi — /login?b=2 ga (muddat sababli xabar)", r.status_code == 302
      and r.headers.get("location") == "/login?b=2", (r.status_code, r.headers.get("location")))
check("K9c o'sha sessiya o'chirildi", sessiyalar(_e)[0] == _se9 - 1, (_se9, sessiyalar(_e)))
kt(date(2026, 10, 25))
check("K10 ertasi kuni — takror xabar yo'q", len(YUB) == 4, YUB)
check("K11 platforma egasi korxonasi (1) va muddatsizlar — tegilmadi", getattr(korxona(1), "bloklangan_at", "x") is None
      and getattr(korxona(_b), "bloklangan_at", "x") is None, (korxona(1), korxona(_b)))
ustun_yoz(1, obuna_tugash=date(2026, 9, 1))
ustun_yoz(_d, obuna_tugash=date(2026, 10, 30), obuna_turi="obuna", eslatma_holati=None)     # shu kuni '7' bosqichi
_n_y = len(YUB)
_k11 = kt(date(2026, 10, 25))
check("K11b egasi korxonasiga bazada o'tgan muddat yozilgan bo'lsa ham — kunlik ish uni BLOKLAMAYDI, xabar yo'q, xato yo'q; "
      "keyingi korxona (D) ham shu ishda ko'rib chiqiladi", getattr(korxona(1), "bloklangan_at", "x") is None
      and len(YUB) == _n_y + 1 and "PO D korxona" in YUB[-1] and isinstance(_k11, list)
      and not any(x.get("amal") == "xato" for x in _k11 if isinstance(x, dict)), (korxona(1), YUB[_n_y:], _k11))
ustun_yoz(1, obuna_tugash=None)
ustun_yoz(_d, obuna_tugash=None, eslatma_holati=None)
bugun_qil(date(2026, 10, 25))
r = req(CP, "post", f"/api/platform/companies/{_e}/extend", data={"oy": "1", "korish": "1"})
check("K12 oldindan ko'rish (korish=1) — tugagan muddat → bugundan +1 oy (25.11), BAZAGA yozilmaydi",
      r.status_code == 200 and (js(r) or {}).get("obuna_tugash") == "2026-11-25"
      and getattr(korxona(_e), "obuna_tugash", None) == date(2026, 10, 20), (r.status_code, r.text[:160]))
r = req(CP, "post", f"/api/platform/companies/{_e}/extend", data={"oy": "1"})
_ce = korxona(_e)
check("K13 uzaytirish — avtomatik blok OCHILDI, muddat 25.11, turi 'obuna', eslatma belgisi tozalandi",
      r.status_code == 200 and (js(r) or {}).get("ochildi") is True and getattr(_ce, "bloklangan_at", "x") is None
      and getattr(_ce, "obuna_tugash", None) == date(2026, 11, 25) and getattr(_ce, "obuna_turi", None) == "obuna"
      and getattr(_ce, "eslatma_holati", "x") is None and getattr(_ce, "obuna_boshi", None) == date(2026, 10, 25),
      (r.status_code, r.text[:200], _ce))
CE, _re = mijoz("po_e_admin")
check("K14 E yana kiradi", _re.status_code == 302, _re.status_code)
_n15 = len(YUB)
kt(date(2026, 11, 18))
check("K15 yangi muddat uchun '7' bosqich yana yuboriladi (eski muddat belgisi tegishli emas)", len(YUB) == _n15 + 1
      and "25.11.2026" in YUB[-1], YUB[_n15:])
ustun_yoz(_e, obuna_tugash=date(2026, 12, 20), eslatma_holati="2026-11-25:bloklandi")
kt(date(2026, 12, 13))
check("K15b belgi BOSHQA muddatniki ('2026-11-25:bloklandi') — yangi muddat (20.12) '7' bosqichi yuboriladi",
      len(YUB) == _n15 + 2 and "20.12.2026" in YUB[-1] and getattr(korxona(_e), "eslatma_holati", None) == "2026-12-20:7",
      YUB[_n15:])
ustun_yoz(_e, obuna_tugash=date(2026, 11, 25), eslatma_holati="2026-11-25:7")
# qo'lda bloklangan korxona uzaytirilsa — blok QOLADI
req(CP, "post", f"/api/platform/companies/{_e}/block", data={"sabab": "Mijoz o'zi so'radi"})
r = req(CP, "post", f"/api/platform/companies/{_e}/extend", data={"sana": "2027-01-31"})
check("K16 qo'lda bloklanganni uzaytirish — muddat 31.01.2027, blok QOLADI (ochilmadi)", r.status_code == 200
      and (js(r) or {}).get("ochildi") is False and getattr(korxona(_e), "bloklangan_at", None) is not None
      and getattr(korxona(_e), "obuna_tugash", None) == date(2027, 1, 31), (r.status_code, r.text[:200]))
r = req(CP, "post", f"/api/platform/companies/{_e}/extend", data={"sana": "2020-01-01"})
check("K17 o'tmishdagi aniq sana — 400", r.status_code == 400 and "oldin" in r.text, (r.status_code, r.text[:160]))
r = req(CP, "post", f"/api/platform/companies/{_e}/extend", data={"oy": "7"})
check("K18 ro'yxatda yo'q oy — 400", r.status_code == 400, r.status_code)
r = req(CP, "post", "/api/platform/companies/1/extend", data={"oy": "1"})
check("K19 platforma egasi korxonasi — uzaytirilmaydi (400), muddatsiz qoladi", r.status_code == 400
      and getattr(korxona(1), "obuna_tugash", "x") is None, (r.status_code, r.text[:160]))
r = req(CP, "post", "/api/platform/companies/1/extend", data={"oy": "1", "korish": "1"})
check("K20 platforma egasi — oldindan ko'rish ham 400", r.status_code == 400, r.status_code)
req(CP, "post", f"/api/platform/companies/{_e}/unblock")
bugun_qil(date(2026, 10, 10))
_s = SessionLocal()
_je = sorted(a.action for a in _s.query(ActivityLog).filter(ActivityLog.company_id == _e,
                                                            ActivityLog.entity_type == "company").all())
_s.close()
check("K21 E jurnali: blocked ×2 (avtomatik + qo'lda), extended ×2, unblocked ×1", _je == ["blocked", "blocked", "extended",
                                                                                           "extended", "unblocked"], _je)

# ══════════════════════════════════════════════════════════════
section("N. Mijoz dasturidagi ogohlantirish — 'Admin, keyin hamma' (egasi QARORI kech111)")
# ══════════════════════════════════════════════════════════════
ustun_yoz(_b, obuna_tugash=date(2026, 10, 15), obuna_turi="obuna", obuna_boshi=date(2026, 9, 15))
CB, _rb = mijoz("po_b_admin")
CBM, _rbm = mijoz("po_b_men")
r1 = req(CB, "get", "/orders")
r2 = req(CBM, "get", "/orders")
check("N1 5 kun qolganda — B ADMINI sariq ogohlantirish (5 kundan keyin, sana, telefon)", r1.status_code == 200
      and 'id="obunaBanner"' in r1.text and "5 kundan keyin tugaydi" in r1.text and "15.10.2026" in r1.text
      # kech118 (zip 122 — tungi rejim, MOSLANDI): fon umumiy ranglar ro'yxatidan (var(--f-fef3c7) = #FEF3C7 yorug' rejimda)
      and "+998 97 111 22 33" in r1.text and ("#FEF3C7" in r1.text or "var(--f-fef3c7)" in r1.text), r1.status_code)
check("N2 5 kun qolganda — B MENEJERI ko'rmaydi", r2.status_code == 200 and 'id="obunaBanner"' not in r2.text, r2.status_code)
ustun_yoz(_b, obuna_tugash=date(2026, 10, 8))
r1 = req(CB, "get", "/orders")
r2 = req(CBM, "get", "/orders")
check("N3 muddat o'tgan (imtiyoz) — admin qizil: 'tugadi — kirish 2 kundan keyin (12.10.2026) yopiladi'", r1.status_code == 200
      and 'id="obunaBanner"' in r1.text and "08.10.2026 da tugadi" in r1.text and "2 kundan keyin (12.10.2026)" in r1.text
      and ("#FEE2E2" in r1.text or "var(--f-fee2e2)" in r1.text), r1.text[r1.text.find('obunaBanner'):][:400])
check("N4 muddat o'tgan — MENEJER ham ko'radi", 'id="obunaBanner"' in r2.text and "08.10.2026 da tugadi" in r2.text,
      r2.status_code)
ustun_yoz(_b, obuna_tugash=date(2026, 10, 10), obuna_turi="sinov")
r1 = req(CB, "get", "/orders")
check("N5 sinov davri oxirgi kuni — 'Sinov davri bugun tugaydi'", "Sinov davri bugun tugaydi" in r1.text, r1.status_code)
ustun_yoz(_b, obuna_tugash=date(2026, 12, 31), obuna_turi="obuna")
r1 = req(CB, "get", "/orders")
check("N6 muddat uzoq — ogohlantirish yo'q", r1.status_code == 200 and 'id="obunaBanner"' not in r1.text)
r1 = req(CP, "get", "/orders")
check("N7 platforma admini — ogohlantirish yo'q", 'id="obunaBanner"' not in r1.text)
_bn = ob("banner", SessionLocal(), None)
check("N8 foydalanuvchi yo'q — None", _bn is None, _bn)

# ══════════════════════════════════════════════════════════════
section("T. Aloqa telefoni (platforma sozlamasi)")
# ══════════════════════════════════════════════════════════════
r = req(CP, "post", "/api/platform/contact-phone", data={"telefon": " +998 90 555 44 33 "})
check("T1 saqlash 200 (bo'shliqlar olinadi)", r.status_code == 200 and (js(r) or {}).get("aloqa_telefoni") == "+998 90 555 44 33",
      (r.status_code, r.text[:160]))
check("T2 blok xabarida yangi telefon", "+998 90 555 44 33" in req(C0, "get", "/login?b=1").text)
r = req(CP, "post", "/api/platform/contact-phone", data={"telefon": "9" * 61})
check("T3 61 belgi — 400, eski qiymat qoladi", r.status_code == 400
      and (js(req(CP, "get", "/api/platform/summary")) or {}).get("aloqa_telefoni") == "+998 90 555 44 33", r.status_code)
r = req(CP, "post", "/api/platform/contact-phone", data={"telefon": ""})
check("T4 bo'sh — tozalanadi, zaxira: platforma egasi korxonasining telefoni", r.status_code == 200
      and (js(r) or {}).get("aloqa_telefoni") == "+998 97 111 22 33", (r.status_code, r.text[:160]))
_s = SessionLocal()
_ts = _s.query(CompanySetting).filter(CompanySetting.key == getattr(obuna, "TELEFON_KALIT", "?")).all()
_s.close()
check("T5 sozlama platforma egasi korxonasida (1) saqlanadi", len(_ts) == 1 and _ts[0].company_id == 1,
      [(x.company_id, x.value) for x in _ts])

# ══════════════════════════════════════════════════════════════
section("R. Platforma raqamlari va korxona faolligi")
# ══════════════════════════════════════════════════════════════
ustun_yoz(_b, obuna_tugash=date(2026, 10, 14), obuna_turi="obuna")     # yaqin
ustun_yoz(_c, obuna_tugash=date(2026, 11, 30), obuna_turi="sinov", imtiyoz_gacha=None)   # sinov, faol
ustun_yoz(_d, obuna_tugash=date(2026, 10, 8), obuna_turi="obuna")      # otgan (imtiyoz)
req(CP, "post", f"/api/platform/companies/{_e}/block", data={"sabab": "Boshqa"})   # bloklangan
r = req(CP, "get", "/api/platform/summary")
rq = (js(r) or {}).get("raqamlar") or {}
check("R1 raqamlar: mijoz 4 (egasisiz), faol 1, muddati yaqin 2 (yaqin + imtiyoz), bloklangan 1, sinov 1",
      rq.get("jami") == 4 and rq.get("faol") == 1 and rq.get("muddati_yaqin") == 2 and rq.get("bloklangan") == 1
      and rq.get("sinov") == 1, rq)
check("R2 bugungi kirishlar > 0 (haqiqiy Toshkent kuni)", isinstance(rq.get("bugun_kirish"), int), rq)
r = req(CP, "get", "/api/platform/companies")
_l = {x.get("id"): x for x in roy(r)}
check("R3 ro'yxat: 5 korxona, 1-korxona platforma_egasi, qolganlari emas", lambda: len(_l) == 5 and _l.get(1, {}).get("platforma_egasi")
      and not any(_l[k]["platforma_egasi"] for k in _l if k != 1), list(_l))
check("R4 B foydalanuvchilar 2 (admin + menejer), A 3 (admin, PO_PLAT, PO_A_ADM)", _l.get(_b, {}).get("users") == 2
      and _l.get(1, {}).get("users") == 3, (_l.get(_b, {}).get("users"), _l.get(1, {}).get("users")))
check("R5 B oxirgi kirish bor, C (hali kirmagan admin — imtiyozda kirgan) ham", _l.get(_b, {}).get("oxirgi_kirish")
      and _l.get(_c, {}).get("oxirgi_kirish"), (_l.get(_b), _l.get(_c)))
# buyurtma: B da loyiha + buyurtma (shu oy)
_pr = req(CB, "post", "/api/projects", json={"project_name": "R loyiha", "client_name": "R mijoz",
                                             "client_phone": "+998901112233"})
_pid = (js(_pr) or {}).get("id")
_or = req(CB, "post", "/api/orders", params={"confirm_shortage": "true"},
          json={"project_id": _pid, "order_type": "product", "master_id": None,
                "items": [{"name": "R detal", "category": "dona", "quantity": 2, "unit_price": 1000,
                           "is_coated": False, "penoplast_id": None}]})
bugun_qil(database.tashkent_date())                   # buyurtma HAQIQIY vaqtda yaratildi
_l = {x.get("id"): x for x in roy(req(CP, "get", "/api/platform/companies"))}
bugun_qil(date(2031, 1, 15))                          # boshqa oy
_l2 = {x.get("id"): x for x in roy(req(CP, "get", "/api/platform/companies"))}
bugun_qil(date(2026, 10, 10))
check("R6 B buyurtma: jami 1; shu oy — joriy Toshkent oyida 1, boshqa oyda 0", _or.status_code == 200
      and _l.get(_b, {}).get("buyurtma_jami") == 1 and _l.get(_b, {}).get("buyurtma_shu_oy") == 1
      and _l2.get(_b, {}).get("buyurtma_shu_oy") == 0 and _l2.get(_b, {}).get("buyurtma_jami") == 1,
      (_pr.status_code, _or.status_code, _or.text[:200], _l.get(_b), _l2.get(_b)))

# ══════════════════════════════════════════════════════════════
section("X. Hamma korxonalar xatolari (platforma admini)")
# ══════════════════════════════════════════════════════════════
_s = SessionLocal()
crud.log_error(_s, "X1 xato A [parameters: ('maxfiy_token', 1)]", endpoint="/api/x1", method="GET", company_id=1)
crud.log_error(_s, "X2 xato B", endpoint="/api/x2", method="POST", performed_by="B admin", company_id=_b)
crud.log_error(_s, "X3 platforma xatosi", endpoint="/cron", method="GET")
_s.close()
r = req(CP, "get", "/api/platform/errors")
_x = roy(r)
check("X1 hammasi: 3 xato, korxona nomlari bilan", lambda: r.status_code == 200 and {x["xabar"][:2] for x in _x} >= {"X1", "X2", "X3"}
      and any(x["korxona"] == "PO B korxona" for x in _x), str(_x)[:300])
check("X2 maxfiy SQL parametrlari yashirilgan", lambda: isinstance(_x, list) and _x and all("maxfiy_token" not in x["xabar"] for x in _x),
      str(_x)[:300])
r = req(CP, "get", f"/api/platform/errors?korxona={_b}")
check("X3 korxona filtri — faqat B", lambda: [x["xabar"][:2] for x in (js(r) or [])] == ["X2"], js(r))
r = req(CP, "get", "/api/platform/errors?korxona=platforma")
check("X4 'platforma' — faqat korxonasiz", lambda: [x["xabar"][:2] for x in (js(r) or [])] == ["X3"], js(r))
r = req(CP, "get", "/api/platform/errors?q=B%20admin")
check("X5 qidiruv (kim)", lambda: [x["xabar"][:2] for x in (js(r) or [])] == ["X2"], js(r))
r = req(CP, "get", "/api/platform/errors?korxona=abc")
check("X6 noto'g'ri korxona — 400", r.status_code == 400, r.status_code)
bugun_qil(database.tashkent_date())                   # xato va kirish yozuvlari HAQIQIY vaqtda
rq = (js(req(CP, "get", "/api/platform/summary")) or {}).get("raqamlar") or {}
check("X7 bugungi xatolar soni ≥ 3 va kirishlar ≥ 1 (haqiqiy Toshkent kuni; ErrorLog vaqti — Toshkent)",
      (rq.get("bugun_xato") or 0) >= 3 and (rq.get("bugun_kirish") or 0) >= 1, rq)
bugun_qil(date(2026, 10, 10))

# ══════════════════════════════════════════════════════════════
section("F. Yuklangan fayllar himoyasi (login + fayl egasi korxonasi) va logotip")
# ══════════════════════════════════════════════════════════════
YARATILGAN = []
_png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
_s = SessionLocal()
_ia = Inventory(company_id=1, item_name=f"F A material {uuid.uuid4().hex[:6]}", unit="kg")
_ib = Inventory(company_id=_b, item_name=f"F B material {uuid.uuid4().hex[:6]}", unit="kg")
_s.add_all([_ia, _ib])
_s.commit()
IA, IB = _ia.id, _ib.id
_s.close()
ustun_yoz(_b, obuna_tugash=date(2026, 12, 31))
CB, _rb = mijoz("po_b_admin")
r = req(CA, "post", f"/api/inventory/{IA}/image", files={"file": ("a.png", _png, "image/png")})
UA = (js(r) or {}).get("image_url") or ""
r = req(CB, "post", f"/api/inventory/{IB}/image", files={"file": ("b.png", _png, "image/png")})
UB = (js(r) or {}).get("image_url") or ""
for _u in (UA, UB):
    if _u:
        YARATILGAN.append(os.path.join(ROOT, _u.lstrip("/")))
check("F0 ikkala rasm yuklandi (eski URL shakli /static/uploads/inventory/<uuid>.png)", UA.startswith("/static/uploads/inventory/")
      and UB.startswith("/static/uploads/inventory/"), (UA, UB))
r = req(C0, "get", UA, follow_redirects=False)
check("F1 kirmagan — fayl berilmaydi (/login ga)", r.status_code in (302, 401) and r.content != _png, r.status_code)
r = req(CA, "get", UA)
check("F2 egasi korxona (A) — 200, fayl mazmuni, private kesh", r.status_code == 200 and r.content == _png
      and "private" in (r.headers.get("cache-control") or ""), (r.status_code, r.headers.get("cache-control")))
r = req(CB, "get", UA)
check("F3 BOSHQA korxona (B) A faylini ololmaydi — 404", r.status_code == 404, r.status_code)
r = req(CB, "get", UB)
check("F4 B o'z faylini oladi — 200", r.status_code == 200 and r.content == _png, r.status_code)
_yetim = f"/static/uploads/inventory/{uuid.uuid4().hex}.png"
_yp = os.path.join(ROOT, _yetim.lstrip("/"))
with open(_yp, "wb") as _f:
    _f.write(_png)
YARATILGAN.append(_yp)
r = req(CA, "get", _yetim)
check("F5 hech bir yozuvga bog'lanmagan (yetim) fayl — 404", r.status_code == 404, r.status_code)
_ua_nom = UA.rsplit("/", 1)[-1]
_aylan = ["/static/uploads/inventory/%2E/" + _ua_nom, "/static/uploads//inventory/" + _ua_nom,
          "/static/uploads/inventory/x/../" + _ua_nom, "/static/uploads/inventory/%2E%2E/inventory/" + _ua_nom,
          "/static/uploads/./inventory/" + _ua_nom]
_ay = [(y, req(C0, "get", y, follow_redirects=False)) for y in _aylan]
check("F6 aylanib o'tish yo'llari (%2E, //, .., .) — LOGINSIZ fayl berilmaydi", _ua_nom and all(
      x.content != _png for _, x in _ay), [(y, x.status_code) for y, x in _ay])
_ay2 = [(y, req(CB, "get", y, follow_redirects=False)) for y in _aylan]
check("F6b xuddi shu yo'llar — BOSHQA korxona ham ololmaydi", _ua_nom and all(x.content != _png for _, x in _ay2),
      [(y, x.status_code) for y, x in _ay2])
check("F7 umumiy statik fayllar (CSS) — loginsiz ochiq qoladi", req(C0, "get", "/static/style.css").status_code == 200)
r = req(CA, "get", "/static/uploads/inventory/yoq_fayl.png")
check("F8 mavjud bo'lmagan fayl — 404", r.status_code == 404, r.status_code)
# kech129 (zip 153, MOSLANDI): logotip endi TO'LIQ o'qiladi (PDF ga chiziladi) — yuqoridagi qo'lda yozilgan `_png` ning IDAT qismi
# buzilgan (Pillow: «broken data stream»), u 400 bilan rad etiladi. Logotip uchun — Pillow yasagan haqiqiy 1 × 1 PNG.
from PIL import Image as _PilImage                 # noqa: E402
_png_logo_b = io.BytesIO()
_PilImage.new("RGBA", (1, 1), (200, 30, 30, 255)).save(_png_logo_b, "PNG")
_png_logo = _png_logo_b.getvalue()
r = req(CB, "post", "/api/settings/company/logo", files={"file": ("l.png", _png_logo, "image/png")})
_lp = (js(r) or {}).get("logo_path") or ""
if _lp:
    YARATILGAN.append(os.path.join(ROOT, _lp))
check("F9 logotip static/uploads/logos/ ga yoziladi", r.status_code == 200 and _lp == f"static/uploads/logos/company_{_b}.png",
      (r.status_code, _lp))
r = req(CB, "get", "/" + _lp)
check("F10 logotip — egasi korxona 200, kesh 'no-cache'", r.status_code == 200 and "no-cache" in (r.headers.get("cache-control") or ""),
      (r.status_code, r.headers.get("cache-control")))
check("F11 logotip — boshqa korxona 404", req(CA, "get", "/" + _lp).status_code == 404)
r = req(CB, "get", "/orders")
check("F12 chap paneldagi logotip yangi yo'l bilan", f'src="/{_lp}"' in r.text, r.status_code)
req(CP, "post", f"/api/platform/companies/{_b}/block", data={"sabab": "Boshqa"})
r = req(CB, "get", UB, follow_redirects=False)
check("F13 bloklangan korxona o'z faylini ham ololmaydi", r.status_code in (302, 401, 403) and r.content != _png, r.status_code)
req(CP, "post", f"/api/platform/companies/{_b}/unblock")
for _p in YARATILGAN:
    try:
        os.remove(_p)
    except OSError:
        pass

# ══════════════════════════════════════════════════════════════
section("M. Sxema va migratsiya")
# ══════════════════════════════════════════════════════════════
from sqlalchemy import Column as _Col, Date as _Date, inspect as _insp   # noqa: E402
check("M1 database._sql_type_for_column(Date) = DATE (ilgari TEXT ga tushardi)",
      database._sql_type_for_column(_Col("x", _Date)) == "DATE", database._sql_type_for_column(_Col("x", _Date)))
_ust = {c["name"]: c for c in _insp(database.engine).get_columns("companies")}
_kerak = ("bloklangan_at", "blok_sabab", "blok_izoh", "bloklagan", "blok_avtomatik", "obuna_boshi", "obuna_tugash",
          "obuna_turi", "imtiyoz_gacha", "eslatma_holati")
check("M2 companies da 10 ta yangi ustun, hammasi NULL ga ruxsat", all(k in _ust and _ust[k]["nullable"] for k in _kerak),
      [k for k in _kerak if k not in _ust])
if PG_URL:
    check("M3 [PG] obuna_tugash turi DATE", "DATE" in str(_ust.get("obuna_tugash", {}).get("type", "")).upper(),
          _ust.get("obuna_tugash"))
_mig = getattr(main, "_migrate_platforma_obuna", None)
_mxato = None if _mig else "funksiya yo'q"
try:
    with contextlib.redirect_stdout(_quiet):
        _mig() if _mig else None
    _mok = _mig is not None
except Exception as e:                     # noqa: BLE001
    _mok, _mxato = False, repr(e)[:300]
check("M4 _migrate_platforma_obuna — qayta chaqirish xatosiz (idempotent)", _mok, _mxato)
_s = SessionLocal()
_kz = crud.export_full_backup(_s, company_id=_b)
_s.close()
check("M5 mijoz zaxirasiga companies (obuna ustunlari) KIRMAYDI", "companies" not in (_kz.get("tables") or {}),
      list((_kz.get("tables") or {}).keys())[:5])

# ══════════════════════════════════════════════════════════════
section("C. Kunlik 'kam qoldi' cron — bloklangan korxonaga Telegram yuborilmaydi")
_s = SessionLocal()
_s.add_all([Inventory(company_id=1, item_name=f"C A kam {uuid.uuid4().hex[:5]}", unit="kg", stock_quantity=1, min_stock=10),
            Inventory(company_id=_b, item_name=f"C B kam {uuid.uuid4().hex[:5]}", unit="kg", stock_quantity=1, min_stock=10)])
_s.commit()
_s.close()
TG = []
_asl_tg, _asl_cs = main._send_telegram, getattr(main, "CRON_SECRET", "")
main._send_telegram = lambda matn, company_id=None: TG.append((company_id, matn))
main.CRON_SECRET = "po_cron"
req(CP, "post", f"/api/platform/companies/{_b}/block", data={"sabab": "Boshqa"})
r = req(C0, "get", "/api/cron/low-stock-check?secret=po_cron")
_tg_b = [c for c, _ in TG if c == _b]
_tg_a = [c for c, _ in TG if c == 1]
req(CP, "post", f"/api/platform/companies/{_b}/unblock")
TG.clear()
r2 = req(C0, "get", "/api/cron/low-stock-check?secret=po_cron")
_tg_b2 = [c for c, _ in TG if c == _b]
main._send_telegram, main.CRON_SECRET = _asl_tg, _asl_cs
check("C1 B bloklangan — A ga xabar bor, B ga YO'Q", r.status_code == 200 and _tg_a and not _tg_b, (r.status_code, r.text[:200], TG))
check("C2 B ochilgach — B ga ham xabar boradi (nazorat)", r2.status_code == 200 and _tg_b2, (r2.status_code, TG))

_mig2 = getattr(main, "_migrate_platforma_obuna", None)
try:
    from sqlalchemy import text as _tx2
    with database.engine.connect() as _cn:
        _cn.execute(_tx2("ALTER TABLE companies DROP COLUMN eslatma_holati"))
        _cn.execute(_tx2("ALTER TABLE companies DROP COLUMN imtiyoz_gacha"))
        _cn.commit()
    with contextlib.redirect_stdout(_quiet):
        _mig2() if _mig2 else None
    _ust2 = {c["name"]: c for c in _insp(database.engine).get_columns("companies")}
    _m4b = "eslatma_holati" in _ust2 and "imtiyoz_gacha" in _ust2 and (
        not PG_URL or "DATE" in str(_ust2["imtiyoz_gacha"]["type"]).upper())
except Exception as e:                     # noqa: BLE001
    _m4b, _ust2 = False, str(e)
check("M4b eski baza (ustunlar yo'q) — _migrate_platforma_obuna ularni qo'shadi (PG da DATE turi)", _m4b,
      str(_ust2)[:300])

section("S. Statik — kod tuzilishi")
# ══════════════════════════════════════════════════════════════
_gcu = manba(auth, "get_current_user")
# kech133 (zip 159, MOSLANDI): hodim sessiyasi tekshiruvi `auth.hodim_holati` ga ko'chdi (telefon va PIN holati bilan) —
# `get_current_employee` uni chaqiradi; blok tekshiruvi o'sha yerda (B13 / D9 — xatti-harakat o'zgarmagan). Asl kodda — eskisidek.
_gce = manba(auth, "hodim_holati") if hasattr(auth, "hodim_holati") else manba(auth, "get_current_employee")
check("S1 auth.get_current_user — korxona bloki tekshiruvi (sessiya o'chiriladi)", "_korxona_bloklanganmi" in _gcu
      and "delete_session" in _gcu, _gcu[-300:])
check("S2 auth.get_current_employee — xuddi shu tekshiruv", "_korxona_bloklanganmi" in _gce
      and "delete_employee_session" in _gce, _gce[-300:])
_kb = manba(auth, "_korxona_bloklanganmi")
check("S3 platforma admini hech qachon bloklanmaydi (tekshiruv boshida)", tartibda(_kb, "if platforma", "return",
                                                                                   "kirish_rad_sababi"), _kb[:400])
_rs = [getattr(r, "path", None) or getattr(r, "name", None) for r in main.app.router.routes]
try:
    _i1 = _rs.index("/static/uploads/{papka}/{fayl}")
    _i2 = next(i for i, r in enumerate(main.app.router.routes) if getattr(r, "name", None) == "static")
    _tart = _i1 < _i2
except (ValueError, StopIteration):
    _tart = False
check("S4 himoyalangan fayl marshruti umumiy /static mount dan OLDIN", _tart)
_sch = getattr(main, "_scheduler", None)
_job = _sch.get_job("obuna_tekshiruvi") if _sch is not None else None
check("S5 rejalashtiruvchida 'obuna_tekshiruvi' (Toshkent 09:05)", _job is not None and "hour='9'" in str(_job.trigger)
      and "minute='5'" in str(_job.trigger), str(getattr(_job, "trigger", None)))
_base = open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8").read()
check("S6 base.html: ogohlantirish YUQORI PANELDA (kontent oqimida emas — `calc(100vh - 58px)` sahifalar kesilmasin), "
      "platforma havolasi faqat platforma admini",
      tartibda(_base, 'class="erp-topbar"', "obuna_banneri(current_user)", 'id="obunaBanner"', 'id="obunaPanel"',
               'id="notifWrap"', "</header>", "{% block content %}")
      and tartibda(_base, "{% if current_user.is_platform_admin %}", 'href="/platforma"'), "")
_pl = open(os.path.join(ROOT, "templates", "platforma.html"), encoding="utf-8").read() \
    if os.path.exists(os.path.join(ROOT, "templates", "platforma.html")) else ""
check("S7 platforma.html: inline onclick yo'q (data-* + delegatsiya), foydalanuvchi matni escapeHtml",
      _pl and "onclick=" not in _pl and _pl.count("escapeHtml(") >= 15, _pl.count("escapeHtml("))
check("S8 platforma.html: sana — Toshkent yordamchilari (new Date( / toISOString YO'Q)", _pl and "new Date(" not in _pl
      and "toISOString" not in _pl)
check("S9 uzaytirish sanasi brauzerda HISOBLANMAYDI — server `korish=1` (formula nusxasi yo'q)",
      _pl and "korish" in _pl and "setMonth" not in _pl and "getMonth" not in _pl)
_logs = open(os.path.join(ROOT, "templates", "logs.html"), encoding="utf-8").read()
check("S10 logs.html «Korxonalar» — /platforma havolasi, eski jadval funksiyalari yo'q", 'href="/platforma"' in _logs
      and "loadPlatformCompanies" not in _logs and "createCompany" not in _logs)
_ls = manba(main, "login_submit")
check("S11 login_submit: blok tekshiruvi parol TO'G'RI bo'lgandan KEYIN, sessiya yaratishdan OLDIN",
      tartibda(_ls, "verify_and_upgrade_password", "kirish_rad_sababi", "create_session"), _ls[-600:])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
