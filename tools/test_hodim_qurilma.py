#!/usr/bin/env python3
"""
test_hodim_qurilma.py — kech133 (zip 159): hodim paneliga FAQAT o'z telefonidan kirish (admin ruxsati bilan) va PIN ni hodimning
o'zi qo'yishi — SERVER (kirish, holatlar, admin ruxsati / rad / uzish, PIN, telefon raqami, o'chirilgan hodim, zaxira, migratsiya)
va SHABLONLAR (statik).

NIMA UCHUN KERAK (egasi 09.10 14:50: «hodim tel no'meri va pin kodini tersa hamma odam kirsa bo'lar ekan — faqat o'zini telefonidan
kira oladigon qilsak»)
-------------------------------------------------------------------------------------------------------------------
  O'LCHANGAN (zip 158 kodi): kirish — telefon + PIN, xolos; to'g'ri raqam va PIN ni bilgan HAR KIM istalgan telefondan kirib, hodim
  nomidan avans yozardi; PIN ni admin qo'yadi va biladi. Shu bilan birga: telefon harfma-harf solishtirilardi (kirish sahifasi
  namunasi «+998 90 123 45 67», admin oynasiniki «+998901234567» — bo'sh joy farqi bilan to'g'ri PIN ham rad etilardi); o'chirilgan
  («O'chirilganlar» dagi) hodim kirib avans yoza olardi (`is_deleted` tekshirilmasdi); `/api/employees` telefon raqamini bermasdi —
  «🔑 Kirish» oynasi doim bo'sh ochilardi.
  EGASI QARORLARI (09.10, tugmali): har yangi telefonga admin ruxsati (birinchisiga ham); PIN ni hodimning o'zi o'zgartiradi (admin
  bergani vaqtinchalik).

BO'LIMLAR
  A — kirish va telefon so'rovi: yangi telefon «ruxsat kutadi» (panel / API yopiq), brauzer kaliti cookie (httponly, secure, 400 kun),
      admin ro'yxati, qayta kirishda yangi so'rov yo'q, Telegram xabari faqat yangi so'rovda, telefon nomi;
  B — admin: ruxsat (aynan ko'rilgan so'rovga — 409), rad, so'rovni boshqa telefon almashtirishi, yangi telefon — eskisi uziladi,
      uzish, ruxsat («Hodimlar: Tahrirlash»), boshqa korxona hodimi — 404;
  C — PIN: majburiy (vaqtinchalik PIN) — oson / mos emas / bir xil / noto'g'ri tana rad; ixtiyoriy — hozirgi PIN shart, noto'g'risi
      kirish urinishi sifatida hisoblanadi (5 ta → 429); boshqa sessiyalar yopiladi; admin PIN ni qayta bersa — yana vaqtinchalik,
      telefon bog'liq qoladi;
  D — telefon raqami ko'rinishlari (bitta raqam), bir raqam boshqa ko'rinishda band, urinishlar hisobi raqam bo'yicha, o'chirilgan
      hodim, eski (telefonsiz) sessiya, sessiya boshqa brauzerda;
  E — shablonlar (statik), zaxira nusxa (telefon kalitlari kirmaydi), migratsiya (`sync_missing_columns`: PIN — vaqtinchalik).
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 158) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_hodim_qurilma.py
"""
import os
import re
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hodim_qurilma159_test"
_DB = os.path.join(tempfile.gettempdir(), "hodim_qurilma159_test.db")
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
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import database                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Employee, EmployeeSession, ActivityLog, LoginHistory   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

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


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def matn(r):
    """HTML matni — `&#39;` → `'` (Jinja apostrofni shunday yozadi)."""
    return (r.text or "").replace("&#39;", "'").replace("&#x27;", "'").replace("&quot;", '"')


ANDROID = "Mozilla/5.0 (Linux; Android 13; SM-A525F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
ANDROID_K = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
          "Mobile/15E148 Safari/604.1")
SAMSUNG = ("Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.0.0 "
           "Mobile Safari/537.36")
_IP = {"n": 10}


def mijoz(ua=ANDROID):
    """TestClient — har biri o'z ulanish manzili bilan (kirish cheklovi hisoblari aralashmasin) va telefon brauzer satri bilan."""
    _IP["n"] += 1
    try:
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False,
                       client=(f"203.0.113.{_IP['n']}", 50000))
    except TypeError:                      # eski Starlette — `client=` yo'q
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.headers["user-agent"] = ua
    return c


def kirish(c, tel, pin, korxona=None, model=None):
    """Ikki korxona bor — kod SHART (1-korxona kodi `KOD1`)."""
    d = {"phone": tel, "pin": pin, "korxona": KOD1 if korxona is None else korxona}
    if model is not None:
        d["qurilma_model"] = model
    return c.post("/hodim/login", data=d, follow_redirects=False)


def cookie_ol(c, nom):
    """Klient cookie si (server qo'ygan — domeni «testserver.local» bo'lishi mumkin; nomi bo'yicha birinchisi)."""
    return next((ck.value for ck in c.cookies.jar if ck.name == nom), None)


def cookie_qoy(c, nom, qiymat):
    """Boshqa klientga cookie — o'sha domen bilan (serverniki bilan bir xil yuborilsin)."""
    _d = next((ck.domain for ck in A.cookies.jar), "testserver.local")
    c.cookies.set(nom, qiymat or "", domain=_d, path="/")


def holat(c):
    r = c.get("/api/hodim/qurilma-holati")
    return r.status_code, js(r).get("holat")


def emp_ol(eid):
    s = SessionLocal()
    try:
        e = s.query(Employee).filter(Employee.id == eid).first()
        return {k: getattr(e, k, "YO'Q") for k in ("phone", "qurilma_hash", "qurilma_nomi", "qurilma_sorov_hash", "qurilma_sorov_nomi",
                                                     "qurilma_sorov_vaqti", "pin_vaqtinchalik", "pin_hash", "is_deleted")}
    finally:
        s.close()


def sessiyalar(eid):
    s = SessionLocal()
    try:
        return s.query(EmployeeSession).filter(EmployeeSession.employee_id == eid).count()
    finally:
        s.close()


def faoliyat(eid, amal):
    s = SessionLocal()
    try:
        return s.query(ActivityLog).filter(ActivityLog.entity_type == "employee", ActivityLog.entity_id == eid,
                                           ActivityLog.action == amal).count()
    finally:
        s.close()


# ══════════════════════════════════════════════════════════════
# Fikstura: korxona admini (A), menejer (M — «Hodimlar: Tahrirlash» yo'q), 2-korxona va uning admini (B)
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ikkinchi Korxona", code="IKKINCHI-159"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "hq_admin", "Parol123!", UserRole.ADMIN, "HQ admin", company_id=1)
    auth.create_user(s, "hq_men", "Parol123!", UserRole.MANAGER, "HQ menejer", company_id=1)
    auth.create_user(s, "hq_b", "Parol123!", UserRole.ADMIN, "B admin", company_id=2)
s.commit()
KOD1 = (s.query(Company).filter(Company.id == 1).first().code or "")
s.close()
A = mijoz()
M = mijoz()
B = mijoz()
_la = [c.post("/login", data={"username": u, "password": "Parol123!"}, follow_redirects=False).status_code
       for c, u in ((A, "hq_admin"), (M, "hq_men"), (B, "hq_b"))]


def hodim(nom, tel, pin, klient=None):
    k = klient or A
    r = k.post("/api/employees", json={"name": nom, "position": "Kesuvchi", "pay_type": "fixed", "fixed_amount": 5_000_000})
    eid = js(r).get("id")
    rs = k.post(f"/api/employees/{eid}/set-login", data={"phone": tel, "pin": pin})
    return eid, rs.status_code


def sorovlar(klient=None):
    r = (klient or A).get("/api/admin/qurilma-sorovlari")
    d = js(r)
    return r.status_code, (d if isinstance(d, list) else [])


def sorov_kaliti(eid):
    return next((x.get("kalit") for x in sorovlar()[1] if x.get("employee_id") == eid), None)


def ruxsat(eid, kalit=None, klient=None):
    k = kalit if kalit is not None else sorov_kaliti(eid)
    return (klient or A).post(f"/api/employees/{eid}/qurilma/ruxsat", json={"kalit": k or ""})


def emp_qatori(eid, klient=None):
    d = js((klient or A).get("/api/employees"))
    return next((x for x in (d if isinstance(d, list) else []) if x.get("id") == eid), {})


E1, _s1 = hodim("Ulug'bek", "+998901110001", "4826")
check("0 adminlar kirdi (302), hodimga telefon + PIN berildi (200); 1-korxona kodi bor", _la == [302, 302, 302] and _s1 == 200
      and bool(KOD1), (_la, _s1, KOD1))

# ══════════════════════════════════════════════════════════════
section("A. Kirish va telefon so'rovi")
# ══════════════════════════════════════════════════════════════
_tg = []
_asl_tg = main._send_telegram
main._send_telegram = lambda text, company_id=None: _tg.append((text, company_id))
H = mijoz(ANDROID)
_r = kirish(H, "+998901110001", "4826")
_scl = [v for k, v in _r.headers.multi_items() if k.lower() == "set-cookie"]
_qc = next((v for v in _scl if v.startswith("emp_qurilma=")), "")      # faqat telefon kaliti cookie si (atributlari aralashmasin)
_qk = re.match(r"emp_qurilma=([A-Za-z0-9_-]+);", _qc)
check("A1 to'g'ri telefon + PIN → /hodim; brauzerga telefon kaliti (43 belgi, HttpOnly, Secure, SameSite=lax, 400 kun) va sessiya",
      _r.status_code == 302 and _r.headers.get("location") == "/hodim" and _qk is not None and len(_qk.group(1)) == 43
      and "httponly" in _qc.lower() and "max-age=34560000" in _qc.lower() and "secure" in _qc.lower()
      and "samesite=lax" in _qc.lower() and any(v.startswith("emp_session_token=") for v in _scl),
      (_r.status_code, _r.headers.get("location"), _scl))
_p = H.get("/hodim")
check("A2 yangi telefon — sahifa «Bu telefon hali tasdiqlanmagan» (ruxsatni kutadi, holatni so'raydi), panel YO'Q",
      _p.status_code == 200 and "Bu telefon hali tasdiqlanmagan" in matn(_p) and "/api/hodim/qurilma-holati" in _p.text
      and "Avans oldim deb yozish" not in _p.text, (_p.status_code, matn(_p)[:300]))
_rh = holat(H)
_ro = H.get("/api/hodim/oylik")
_ra = H.post("/api/hodim/advance-request", data={"amount": "100000", "requested_date": "2026-10-01", "notes": "x"})
_rq = H.get("/api/hodim/my-requests")
check("A3 ruxsat kutayotgan telefon: holat «kutilmoqda»; hodim API lari (oylik, avans yozish, so'rovlar) — 401",
      _rh == (200, "kutilmoqda") and (_ro.status_code, _ra.status_code, _rq.status_code) == (401, 401, 401),
      (_rh, _ro.status_code, _ra.status_code, _rq.status_code))
_st, _sr = sorovlar()
_s0 = next((x for x in _sr if x.get("employee_id") == E1), {})
_e = emp_ol(E1)
check("A4 admin ro'yxatida: ism, telefon nomi «Android · SM-A525F · Chrome», 16 belgili so'rov belgisi, vaqt (UTC, Z); bazada — "
      "kalitning SHA-256 i (kalitning o'zi emas)",
      _st == 200 and _s0.get("name") == "Ulug'bek" and _s0.get("nomi") == "Android · SM-A525F · Chrome"
      and re.fullmatch(r"[0-9a-f]{16}", str(_s0.get("kalit"))) is not None and str(_s0.get("vaqti", "")).endswith("Z")
      and _qk is not None and _e.get("qurilma_sorov_hash") == auth.qurilma_hash_ol(_qk.group(1)) if hasattr(auth, "qurilma_hash_ol")
      else False, (_st, _sr, _e))
_q = emp_qatori(E1)
check("A5 /api/employees qatorida: telefon raqami (ilgari yo'q edi — «🔑 Kirish» oynasi bo'sh ochilardi), bog'langan telefon yo'q, "
      "kutayotgan so'rov (shu belgi bilan), PIN vaqtinchalik",
      _q.get("phone") == "+998901110001" and _q.get("qurilma") is None and isinstance(_q.get("qurilma_sorov"), dict)
      and _q["qurilma_sorov"].get("kalit") == _s0.get("kalit") and _q.get("pin_vaqtinchalik") is True
      and "pin_hash" not in _q and "qurilma_hash" not in _q, _q)
_vaqt0 = _e.get("qurilma_sorov_vaqti")
_r2 = kirish(H, "+998901110001", "4826")
_e2 = emp_ol(E1)
check("A6 o'sha telefon qayta kirsa — yangi so'rov YO'Q (vaqt o'zgarmadi, faoliyat yozuvi 1 ta), Telegram xabari faqat birinchisida",
      _r2.status_code == 302 and _e2.get("qurilma_sorov_vaqti") == _vaqt0 and faoliyat(E1, "qurilma_sorov") == 1 and len(_tg) == 1,
      (_r2.status_code, _vaqt0, _e2.get("qurilma_sorov_vaqti"), faoliyat(E1, "qurilma_sorov"), len(_tg)))
check("A7 Telegram xabari — korxonaga, hodim ismi va telefon nomi bilan, qayerda ruxsat berilishi aytiladi",
      len(_tg) == 1 and _tg[0][1] == 1 and "Ulug'bek" in _tg[0][0] and "Android · SM-A525F · Chrome" in _tg[0][0]
      and "Bosh sahifa" in _tg[0][0], _tg)
_nom = getattr(crud, "qurilma_nomi_yasash", None)
check("A8 telefon nomi: sahifa skripti bergan model ustun; yangi Chrome («Android 10; K») — model yo'q; iPhone; Samsung Internet; "
      "xavfli belgilar olib tashlanadi; 120 belgigacha",
      _nom is not None and _nom(ANDROID_K, "") == "Android · Chrome" and _nom(ANDROID_K, "Redmi Note 12") == "Android · Redmi Note 12 · Chrome"
      and _nom(IPHONE, "") == "iPhone · Safari" and _nom(SAMSUNG, "") == "Android · SM-S918B · Samsung Internet"
      and _nom(ANDROID_K, '<img src=x onerror=alert(1)>') == "Android · img srcx onerroralert(1) · Chrome"
      and len(_nom("x" * 500, "y" * 500)) <= 120, [_nom(u, m) for u, m in ((ANDROID_K, ""), (IPHONE, ""), (SAMSUNG, ""))] if _nom else None)

# ══════════════════════════════════════════════════════════════
section("B. Admin: ruxsat, rad, almashtirish, uzish")
# ══════════════════════════════════════════════════════════════
_k1 = sorov_kaliti(E1)
_rb = A.post(f"/api/employees/{E1}/qurilma/ruxsat", json={"kalit": "0000000000000000"})
_rb2 = A.post(f"/api/employees/{E1}/qurilma/ruxsat", json={})
_rb3 = A.post(f"/api/employees/{E1}/qurilma/ruxsat", json={"kalit": _k1, "boshqa": 1})
_rm = M.post(f"/api/employees/{E1}/qurilma/ruxsat", json={"kalit": _k1})
_rml = M.get("/api/admin/qurilma-sorovlari")
_rbb = B.post(f"/api/employees/{E1}/qurilma/ruxsat", json={"kalit": _k1})
check("B1 boshqa so'rov belgisi — 409 (o'zbekcha); belgisiz / ortiqcha kalit — 400; menejer («Hodimlar: Tahrirlash» yo'q) — 403 "
      "(ro'yxat ham); boshqa korxona admini — 404; hech biri telefonga ruxsat bermadi",
      _rb.status_code == 409 and "yangilang" in js(_rb).get("detail", "") and (_rb2.status_code, _rb3.status_code) == (400, 400)
      and (_rm.status_code, _rml.status_code, _rbb.status_code) == (403, 403, 404) and emp_ol(E1).get("qurilma_hash") is None
      and holat(H) == (200, "kutilmoqda"),
      (_rb.status_code, js(_rb), _rb2.status_code, _rb3.status_code, _rm.status_code, _rml.status_code, _rbb.status_code))
_rr = ruxsat(E1, _k1)
_e = emp_ol(E1)
check("B2 ruxsat → hodimning YAGONA telefoni (nomi bilan), so'rov tozalandi; kutib turgan sahifa holati — «pin» (avval o'z PIN i); "
      "faoliyat yozuvi",
      _rr.status_code == 200 and _e.get("qurilma_hash") == (auth.qurilma_hash_ol(_qk.group(1)) if _qk and hasattr(auth, "qurilma_hash_ol") else 1)
      and _e.get("qurilma_nomi") == "Android · SM-A525F · Chrome" and _e.get("qurilma_sorov_hash") is None
      and holat(H) == (200, "pin") and faoliyat(E1, "qurilma_ruxsat") == 1, (_rr.status_code, js(_rr), _e, holat(H)))
_pp = H.get("/hodim")
_po = H.get("/api/hodim/oylik")
_pa = H.post("/api/hodim/advance-request", data={"amount": "100000", "requested_date": "2026-10-01", "notes": "x"})
check("B3 PIN hali admin bergan: /hodim — «O'z PIN kodingizni qo'ying» (hozirgi PIN so'ralmaydi); hodim API lari — 403 o'zbekcha sabab",
      _pp.status_code == 200 and "O'z PIN kodingizni qo'ying" in matn(_pp) and 'id="pinEski"' not in _pp.text
      and "/api/hodim/pin" in _pp.text and (_po.status_code, _pa.status_code) == (403, 403)
      and js(_po).get("detail") == "Avval o'z PIN kodingizni qo'ying", (_pp.status_code, matn(_pp)[:200], _po.status_code, js(_po)))
_rp = H.post("/api/hodim/pin", json={"yangi": "5937", "takror": "5937"})
_pn = H.get("/hodim")
check("B4 o'z PIN i qo'yildi → panel (forma, «🔒 PIN» havolasi); oylik API — 200",
      _rp.status_code == 200 and "Avans oldim deb yozish" in _pn.text and 'href="/hodim/pin"' in _pn.text
      and H.get("/api/hodim/oylik").status_code == 200, (_rp.status_code, js(_rp), _pn.status_code))
# Boshqa telefon (X) to'g'ri PIN bilan; keyin uchinchisi (Y) — X ning so'rovini almashtiradi
X = mijoz(IPHONE)
_rx = kirish(X, "+998901110001", "5937")
_kx = sorov_kaliti(E1)
check("B5 ruxsat berilgan telefon bor — boshqa telefondan to'g'ri PIN bilan ham panel yopiq (kutadi); ro'yxatda hozirgi telefon "
      "ko'rinadi; asl telefon ishlayveradi",
      _rx.status_code == 302 and holat(X) == (200, "kutilmoqda") and X.get("/api/hodim/oylik").status_code == 401
      and next((x.get("hozirgi") for x in sorovlar()[1] if x.get("employee_id") == E1), None) == "Android · SM-A525F · Chrome"
      and H.get("/api/hodim/oylik").status_code == 200, (_rx.status_code, holat(X), sorovlar()))
Y = mijoz(SAMSUNG)
kirish(Y, "+998901110001", "5937")
_ky = sorov_kaliti(E1)
_rxo = ruxsat(E1, _kx)
check("B6 uchinchi telefon (Y) so'rovi X nikini almashtiradi: X holati «rad», Y «kutilmoqda»; X ning eski belgisi bilan ruxsat — 409",
      _ky != _kx and holat(X) == (200, "rad") and holat(Y) == (200, "kutilmoqda") and _rxo.status_code == 409
      and len([x for x in sorovlar()[1] if x.get("employee_id") == E1]) == 1, (_kx, _ky, holat(X), holat(Y), _rxo.status_code))
_xtok = cookie_ol(X, "emp_session_token")
_xp = X.get("/hodim")


def _tok_bormi(tok):
    _s = SessionLocal()
    try:
        return _s.query(EmployeeSession).filter(EmployeeSession.token == (tok or "")).count()
    finally:
        _s.close()


check("B7 «rad» holatdagi telefon /hodim ochganda — «Bu telefonga ruxsat berilmadi» (qayta kirish havolasi), sessiyasi yopiladi "
      "(brauzer cookie si ham, bazadagi sessiya ham — eski token bilan qayta so'ralsa ham 401)",
      _xtok and _xp.status_code == 200 and "Bu telefonga ruxsat berilmadi" in matn(_xp) and 'href="/hodim/login"' in _xp.text
      and holat(X)[0] == 401 and _tok_bormi(_xtok) == 0, (_xp.status_code, matn(_xp)[:200], holat(X), _tok_bormi(_xtok)))
_rad = A.post(f"/api/employees/{E1}/qurilma/rad", json={"kalit": _ky})
check("B8 admin Y ni rad etdi: Y holati «rad», so'rov yo'q; bog'langan telefon (H) o'zgarmadi va ishlaydi; faoliyat yozuvi",
      _rad.status_code == 200 and holat(Y) == (200, "rad") and emp_ol(E1).get("qurilma_sorov_hash") is None
      and H.get("/api/hodim/oylik").status_code == 200 and faoliyat(E1, "qurilma_rad") == 1, (_rad.status_code, holat(Y)))
# Yangi telefon Z ga ruxsat — eski (H) uziladi
Z = mijoz(ANDROID_K)
kirish(Z, "+998901110001", "5937", model="Redmi Note 12")
_rz = ruxsat(E1)
check("B9 yangi telefon (Z) ga ruxsat: endi u yagona telefon (nomida sahifa bergan model), eski telefon (H) sessiyasi yopildi (401), Z — "
      "panel (PIN o'zi qo'ygan — so'ralmaydi)",
      _rz.status_code == 200 and js(_rz).get("eski") == "Android · SM-A525F · Chrome" and holat(H)[0] == 401
      and holat(Z) == (200, "tayyor") and Z.get("/api/hodim/oylik").status_code == 200
      and emp_ol(E1).get("qurilma_nomi") == "Android · Redmi Note 12 · Chrome", (_rz.status_code, js(_rz), holat(H), holat(Z)))
_ru = A.post(f"/api/employees/{E1}/qurilma/uzish")
_ru2 = A.post(f"/api/employees/{E1}/qurilma/uzish")
check("B10 uzish: hamma sessiya yopildi, telefon yo'q; qayta uzish — 409; keyingi kirish — yangi so'rov",
      _ru.status_code == 200 and sessiyalar(E1) == 0 and emp_ol(E1).get("qurilma_hash") is None and _ru2.status_code == 409
      and kirish(Z, "+998901110001", "5937").status_code == 302 and holat(Z) == (200, "kutilmoqda"),
      (_ru.status_code, _ru2.status_code, sessiyalar(E1), holat(Z)))
ruxsat(E1)
check("B11 qayta ruxsat — o'sha telefon panelga qaytdi", holat(Z) == (200, "tayyor"), holat(Z))

# ══════════════════════════════════════════════════════════════
section("C. PIN ni hodimning o'zi qo'yishi")
# ══════════════════════════════════════════════════════════════
E2, _ = hodim("Jurabek", "+998901110002", "2580")
J = mijoz(ANDROID)
kirish(J, "+998901110002", "2580")
ruxsat(E2)
_rad_pin = {}
for _p in ("1111", "1234", "9876", "0123", "6789"):
    _rad_pin[_p] = js(J.post("/api/hodim/pin", json={"yangi": _p, "takror": _p})).get("detail")
_mos = J.post("/api/hodim/pin", json={"yangi": "4071", "takror": "4072"})
_bir = J.post("/api/hodim/pin", json={"yangi": "2580", "takror": "2580"})
_uch = J.post("/api/hodim/pin", json={"yangi": "407", "takror": "407"})
_hrf = J.post("/api/hodim/pin", json={"yangi": "40a1", "takror": "40a1"})
_ort = J.post("/api/hodim/pin", json={"yangi": "4071", "takror": "4071", "admin": True})
_son = J.post("/api/hodim/pin", json={"yangi": 4071, "takror": 4071})
_bos = J.post("/api/hodim/pin", content="x", headers={"Content-Type": "application/json"})
check("C1 oson PIN (bir xil raqamlar, ketma-ket) — rad, o'zbekcha sabab; ikki marta mos emas / hozirgisi bilan bir xil / 3 xonali / "
      "harfli — 400 sababi bilan; ortiqcha kalit, son — 400; JSON emas — 400/422 (FastAPI); PIN o'zgarmadi (hali vaqtinchalik)",
      all(v and "juda oson" in v for v in _rad_pin.values())
      and js(_mos).get("detail") == "Yangi PIN ikki marta bir xil yozilmadi"
      and js(_bir).get("detail") == "Yangi PIN hozirgisidan farq qilishi kerak"
      and js(_uch).get("detail") == js(_hrf).get("detail") == "Yangi PIN aynan 4 xonali raqam bo'lishi kerak"
      and (_ort.status_code, _son.status_code) == (400, 400) and _bos.status_code in (400, 422)
      and emp_ol(E2).get("pin_vaqtinchalik") is True,
      (_rad_pin, js(_mos), js(_bir), js(_uch), _ort.status_code, _son.status_code, _bos.status_code, emp_ol(E2).get("pin_vaqtinchalik")))
_ok = J.post("/api/hodim/pin", json={"yangi": "4071", "takror": "4071"})
_e = emp_ol(E2)
check("C2 majburiy PIN (hozirgisi so'ralmaydi) qo'yildi: vaqtinchalik emas, bcrypt xesh, faoliyat yozuvi; /api/employees — "
      "«o'zi qo'ygan»",
      _ok.status_code == 200 and _e.get("pin_vaqtinchalik") is False and str(_e.get("pin_hash", "")).startswith("$2")
      and faoliyat(E2, "pin_ozgartirildi") == 1 and emp_qatori(E2).get("pin_vaqtinchalik") is False,
      (_ok.status_code, js(_ok), _e.get("pin_vaqtinchalik")))
_pg = J.get("/hodim/pin")
check("C3 paneldan PIN o'zgartirish sahifasi — hozirgi PIN maydoni bilan (ixtiyoriy rejim, panelga qaytish havolasi)",
      _pg.status_code == 200 and 'id="pinEski"' in _pg.text and "PIN kodni o'zgartirish" in matn(_pg) and 'href="/hodim"' in _pg.text,
      (_pg.status_code, matn(_pg)[:200]))
# Ikkinchi sessiya o'sha telefondan (o'sha brauzer — boshqa sessiya)
J2 = mijoz(ANDROID)
cookie_qoy(J2, "emp_qurilma", cookie_ol(J, "emp_qurilma"))
kirish(J2, "+998901110002", "4071")
_ikki = (holat(J), holat(J2))
_yoq = J.post("/api/hodim/pin", json={"yangi": "3829", "takror": "3829"})
_nt = J.post("/api/hodim/pin", json={"eski": "0000", "yangi": "3829", "takror": "3829"})
_s = SessionLocal()
_tk = crud.telefon_kaliti("+998901110002") if hasattr(crud, "telefon_kaliti") else "998901110002"
_xato_urin = _s.query(LoginHistory).filter(LoginHistory.username == _tk, LoginHistory.success == False).count()   # noqa: E712
_s.close()
_ok2 = J.post("/api/hodim/pin", json={"eski": "4071", "yangi": "3829", "takror": "3829"})
check("C4 ixtiyoriy almashtirish: hozirgi PIN siz / noto'g'ri — 400 («Hozirgi PIN noto'g'ri»), noto'g'risi kirish urinishi sifatida "
      "yozildi (raqam kaliti bilan); to'g'ri — o'zgardi, shu sessiya qoldi, o'sha hodimning BOSHQA sessiyasi yopildi",
      _ikki == ((200, "tayyor"), (200, "tayyor")) and js(_yoq).get("detail") == "Hozirgi PIN noto'g'ri"
      and js(_nt).get("detail") == "Hozirgi PIN noto'g'ri" and _xato_urin == 2 and _ok2.status_code == 200
      and holat(J) == (200, "tayyor") and holat(J2)[0] == 401,
      (_ikki, js(_yoq), js(_nt), _xato_urin, _ok2.status_code, holat(J), holat(J2)))
J3 = mijoz(ANDROID)
cookie_qoy(J3, "emp_qurilma", cookie_ol(J, "emp_qurilma"))
_ek = kirish(J3, "+998901110002", "4071")
check("C6 eski PIN bilan kirish — rad (sahifada xato)", _ek.status_code == 200 and "PIN noto'g'ri" in matn(_ek), (_ek.status_code,))
# Admin PIN ni qayta beradi (unutdi) — vaqtinchalik, telefon bog'liq qoladi
_sl = A.post(f"/api/employees/{E2}/set-login", data={"phone": "+998901110002", "pin": "7777"})
_e = emp_ol(E2)
J4 = mijoz(ANDROID)
cookie_qoy(J4, "emp_qurilma", cookie_ol(J, "emp_qurilma"))
_kr = kirish(J4, "+998901110002", "7777")
check("C7 admin PIN ni qayta berdi: hodim sessiyalari yopildi, PIN — vaqtinchalik, telefon bog'liq qoldi; o'sha telefondan yangi "
      "vaqtinchalik PIN bilan — so'rovsiz, to'g'ri «o'z PIN i» bosqichiga",
      _sl.status_code == 200 and _e.get("pin_vaqtinchalik") is True and _e.get("qurilma_hash") is not None
      and holat(J)[0] == 401 and _kr.status_code == 302 and holat(J4) == (200, "pin") and emp_ol(E2).get("qurilma_sorov_hash") is None,
      (_sl.status_code, _e.get("pin_vaqtinchalik"), holat(J), holat(J4)))

_mj = J4.post("/api/hodim/pin", json={"yangi": "5824", "takror": "5824"})
for _i in range(2):
    J4.post("/api/hodim/pin", json={"eski": "1357", "yangi": "6201", "takror": "6201"})
_blok = J4.post("/api/hodim/pin", json={"eski": "5824", "yangi": "6201", "takror": "6201"})
_s = SessionLocal()
_qoldi = crud.authenticate_employee(_s, "+998901110002", "5824", company_id=1) is not None
_s.close()
check("C8 noto'g'ri «hozirgi PIN» lar kirish xatolari bilan BITTA hisobda (raqam bo'yicha): jami 5 ta (C4 — 2, C6 — 1, bu yerda 2) → "
      "keyingi urinish to'g'ri PIN bilan ham 429, sabab o'zbekcha; PIN o'zgarmadi",
      _mj.status_code == 200 and _blok.status_code == 429 and "Juda ko'p noto'g'ri urinish" in js(_blok).get("detail", "") and _qoldi,
      (_mj.status_code, _blok.status_code, js(_blok), _qoldi))

# ══════════════════════════════════════════════════════════════
section("D. Telefon raqami, o'chirilgan hodim, eski sessiyalar")
# ══════════════════════════════════════════════════════════════
E3, _ = hodim("Mirjalol", "+998 90 111 00 03", "3141")
_kor = []
for _t in ("+998 90 111 00 03", "+998901110003", "998901110003", "90 111 00 03", "901110003", "+998(90)111-00-03"):
    _c = mijoz(ANDROID)
    _r = kirish(_c, _t, "3141")
    _kor.append((_t, _r.status_code, _r.headers.get("location")))
check("D1 bitta raqam turli ko'rinishda (bo'sh joy, +, 998 siz, qavs, chiziqcha) — hammasi o'sha hodim (302 → /hodim)",
      all(x[1] == 302 and x[2] == "/hodim" for x in _kor), _kor)
_band = A.post(f"/api/employees/{E1}/set-login", data={"phone": "90 111 00 03", "pin": "1593"})
check("D2 boshqa hodimga o'sha raqam boshqa ko'rinishda — 400 «Bu telefon raqami boshqa xodimda band»; Ulug'bek raqami o'zgarmadi",
      _band.status_code == 400 and "band" in js(_band).get("detail", "") and emp_ol(E1).get("phone") == "+998901110001",
      (_band.status_code, js(_band), emp_ol(E1).get("phone")))
E4, _ = hodim("Sardor", "+998901110004", "2468")
_q = mijoz(ANDROID)
for _t in ("+998901110004", "+998 90 111 00 04", "901110004", "998901110004", "90 111 00 04"):
    kirish(_q, _t, "0000")
_r6 = kirish(_q, "+998901110004", "2468")
check("D3 urinishlar hisobi — RAQAM bo'yicha: 5 ta noto'g'ri PIN turli ko'rinishda → 6-si to'g'ri PIN bilan ham «Juda ko'p noto'g'ri "
      "urinish» (ko'rinishni o'zgartirib cheklovdan qochib bo'lmaydi)",
      _r6.status_code == 200 and "Juda ko'p noto'g'ri urinish" in matn(_r6), (_r6.status_code, matn(_r6)[-400:]))
E5, _ = hodim("Bekzod", "+998901110005", "1470")
K = mijoz(ANDROID)
kirish(K, "+998901110005", "1470")
ruxsat(E5)
K.post("/api/hodim/pin", json={"yangi": "8642", "takror": "8642"})
_ok5 = holat(K)
_del = A.delete(f"/api/employees/{E5}")
_kd = holat(K)
_kd2 = kirish(mijoz(ANDROID), "+998901110005", "8642")
check("D4 o'chirilgan hodim («O'chirilganlar» ga): ochiq sessiyasi yopildi, qayta kira olmaydi (ilgari kirib avans yozardi)",
      _ok5 == (200, "tayyor") and _del.status_code == 200 and _kd[0] == 401 and sessiyalar(E5) == 0
      and _kd2.status_code == 200 and "PIN noto'g'ri" in matn(_kd2), (_ok5, _del.status_code, _kd, _kd2.status_code))
# Eski (zip 159 dan oldingi) sessiya — telefonsiz; sessiya boshqa brauzerda
_s = SessionLocal()
_tok = "eski-sessiya-159-" + "x" * 20
from datetime import datetime as _dt, timedelta as _td   # noqa: E402
_s.add(EmployeeSession(token=_tok, employee_id=E1, expires_at=_dt.utcnow() + _td(days=3)))
_s.commit()
_s.close()
O = mijoz(ANDROID)
cookie_qoy(O, "emp_session_token", _tok)
cookie_qoy(O, "emp_qurilma", cookie_ol(Z, "emp_qurilma"))
_oh = O.get("/hodim", follow_redirects=False)
check("D5 eski sessiya (telefon belgisi yo'q) — yaroqsiz: /hodim → kirish sahifasi, API — 401 (yangilanish kuni hamma qayta kiradi)",
      _oh.status_code == 302 and str(_oh.headers.get("location", "")).startswith("/hodim/login")
      and O.get("/api/hodim/oylik").status_code == 401, (_oh.status_code, _oh.headers.get("location")))
P1 = mijoz(ANDROID)
cookie_qoy(P1, "emp_session_token", cookie_ol(Z, "emp_session_token"))
P2 = mijoz(ANDROID)
cookie_qoy(P2, "emp_session_token", cookie_ol(Z, "emp_session_token"))
cookie_qoy(P2, "emp_qurilma", "A" * 43)
P3 = mijoz(ANDROID)
cookie_qoy(P3, "emp_session_token", cookie_ol(Z, "emp_session_token"))
cookie_qoy(P3, "emp_qurilma", cookie_ol(Z, "emp_qurilma"))
check("D6 sessiya cookie si boshqa brauzerga ko'chirilsa: telefon kalitisiz yoki boshqa kalit bilan — 401; asl telefon ishlayveradi "
      "(nazorat: IKKALA cookie ko'chirilsa — o'sha telefon brauzeri deb olinadi, 200 — ko'chirish usuli ishlaydi)",
      P1.get("/api/hodim/oylik").status_code == 401 and P2.get("/api/hodim/oylik").status_code == 401
      and P3.get("/api/hodim/oylik").status_code == 200 and holat(Z) == (200, "tayyor"),
      (P1.get("/api/hodim/oylik").status_code, P2.get("/api/hodim/oylik").status_code, P3.get("/api/hodim/oylik").status_code, holat(Z)))
_lp = Z.get("/hodim/login", follow_redirects=False)
_lx = mijoz(ANDROID).get("/hodim/login")
check("D7 kirish sahifasi: kirgan hodim — /hodim ga; yangi brauzer — forma (telefon modeli maydoni, «admin ruxsat» izohi)",
      _lp.status_code == 302 and _lp.headers.get("location") == "/hodim" and _lx.status_code == 200
      and 'name="qurilma_model"' in _lx.text and "admin ruxsat berishi kerak" in matn(_lx), (_lp.status_code, _lx.status_code))

# ══════════════════════════════════════════════════════════════
section("E. Shablonlar, zaxira nusxa, migratsiya")
# ══════════════════════════════════════════════════════════════


def oqi(yol):
    try:
        return open(os.path.join(ROOT, yol), encoding="utf-8").read()
    except OSError:
        return ""


LOGIN, KUT, PIN, DASH, KPI = (oqi("templates/hodim_login.html"), oqi("templates/hodim_kutish.html"), oqi("templates/hodim_pin.html"),
                              oqi("templates/dashboard.html"), oqi("templates/kpi.html"))
check("E1 kirish sahifasi: telefon modeli — `navigator.userAgentData.getHighEntropyValues(['model'])` (yashirin maydon)",
      "getHighEntropyValues(['model'])" in LOGIN and 'id="qurilmaModel"' in LOGIN, "")
check("E2 kutish sahifasi: har 4 soniyada holat, ruxsatda /hodim, 401 da kirish; style.css dan keyin surilish ochiq",
      "/api/hodim/qurilma-holati" in KUT and "4000" in KUT and "location.href = '/hodim'" in KUT
      and "location.href = '/hodim/login'" in KUT and "height:auto;overflow:visible" in KUT
      and KUT.find("style.css") < KUT.find("height:auto;overflow:visible"), "")
check("E3 PIN sahifasi: POST /api/hodim/pin, yangi + takror (+ hozirgi — ixtiyoriy rejimda), mijozda ham 4 xona tekshiruvi",
      "fetch('/api/hodim/pin'" in PIN and 'id="pinYangi"' in PIN and 'id="pinTakror"' in PIN and "{% if not majburiy %}" in PIN
      and "/^\\d{4}$/" in PIN, "")
check("E4 Bosh sahifa: telefon so'rovlari oynasi (Esc / «Keyinroq» — `data-yopish`), avans so'rovlaridan OLDIN; yopilgach avans oynasi",
      'id="qurilmaModal"' in DASH and "qurilmaOynaYop()" in DASH and "data-yopish" in DASH.split('id="qurilmaModal"')[-1][:2500]
      and "checkQurilmaSorovlari();\nloadAll();" in DASH and "if (ochiq) checkPendingAdvanceRequests();" in DASH, "")
check("E5 KPI «🔑 Kirish» oynasi: telefon bo'limi (ruxsat / rad / uzish), qatorda holat, PIN vaqtinchalik izohi",
      'id="pa-qurilma"' in KPI and "function qurilmaQatori" in KPI and "function paQurilmaChiz" in KPI
      and "/api/employees/${id}/qurilma/uzish" in KPI and "/api/employees/${id}/qurilma/rad" in KPI and "Bu PIN — vaqtinchalik" in KPI, "")
_s = SessionLocal()
try:
    _bk = crud.export_full_backup(_s, company_id=1)
finally:
    _s.close()
_er = (_bk.get("tables") or {}).get("employees") or [{}]
check("E6 zaxira nusxa: telefon kalitlari xeshi (ruxsat berilgan va kutayotgan) va PIN xeshi KIRMAYDI; telefon nomi, PIN holati — bor",
      all("qurilma_hash" not in r and "qurilma_sorov_hash" not in r and "pin_hash" not in r for r in _er)
      and all("qurilma_nomi" in r and "pin_vaqtinchalik" in r for r in _er), sorted(_er[0].keys()))
# Migratsiya: ustunlar yo'q eski baza → `sync_missing_columns` qo'shadi, mavjud hodimlarning PIN i — vaqtinchalik
from sqlalchemy import text as _txt                    # noqa: E402
_mig = None
try:
    with database.engine.begin() as _cn:
        _cn.execute(_txt("ALTER TABLE employees DROP COLUMN pin_vaqtinchalik"))
        _cn.execute(_txt("ALTER TABLE employees DROP COLUMN qurilma_sorov_nomi"))
        _cn.execute(_txt("ALTER TABLE employee_sessions DROP COLUMN qurilma_hash"))
    with contextlib.redirect_stdout(_quiet):
        database.sync_missing_columns()
    with database.engine.connect() as _cn:
        _mig = [tuple(r) for r in _cn.execute(_txt("SELECT pin_vaqtinchalik, qurilma_sorov_nomi FROM employees ORDER BY id")).fetchall()]
        _mig_s = _cn.execute(_txt("SELECT COUNT(qurilma_hash) FROM employee_sessions")).scalar()
except Exception as _e:                   # noqa: BLE001 — asl kodda ustunlar yo'q (yiqiladi, qulamaydi)
    _mig = f"{type(_e).__name__}: {_e}"
    _mig_s = None
check("E7 migratsiya (eski baza — ustunlarsiz): `sync_missing_columns` qo'shadi; HAMMA mavjud hodimning PIN i — vaqtinchalik (admin "
      "bergan), boshqa ustunlar — NULL; eski sessiyalar telefonsiz (yaroqsiz)",
      isinstance(_mig, list) and len(_mig) >= 5 and all(bool(r[0]) is True and r[1] is None for r in _mig) and _mig_s == 0,
      (_mig, _mig_s))
main._send_telegram = _asl_tg

print("\n" + "=" * 70)
print(f"{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
