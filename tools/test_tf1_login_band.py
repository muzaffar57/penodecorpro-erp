#!/usr/bin/env python3
"""
test_tf1_login_band.py — kech108, K107-2 darvozasi: TENANT_FILTER=1 da boshqa korxonada BAND login.

NIMA UCHUN KERAK (O'LCHANGAN — shu test ASL `auth.py` ga qarshi): `main` ko'chirishida TENANT_FILTER=1 yoqiladi.
`auth.create_user` bandlik tekshiruvi (`db.query(User).filter(User.username == …)`) global korxona filtri bilan JORIY
korxonaga cheklanardi — boshqa korxonadagi login ko'rinmas, INSERT `ix_users_username` (butun tizim bo'yicha YAGONA)
xatosi → 500 (400 "Bu username band" o'rniga).

Test o'zi TENANT_FILTER=1 ni yoqadi (hammasi.sh tf0 / tf1 da ham bir xil ishlaydi).
  1 — API: A korxona admini B korxonadagi login bilan foydalanuvchi yaratadi → 400 "Bu username band" (asl: 500), INSERT
      urinishi YO'Q (oldindan tekshiruv; IntegrityError yo'li — faqat parallel holat, 3-bo'lim);
      yangi login → 200 (A korxonasida); o'sha login yana → 400; B korxonasi foydalanuvchilari o'zgarmadi.
  2 — funksiya: kontekst = A, `auth.create_user(…, "B_BAND", …)` → HTTPException 400.
  3 — parallel (tekshiruvdan keyin boshqa so'rov yozib ulgurgan — soxta sessiya birinchi tekshiruvni "bo'sh" qaytaradi):
      commit IntegrityError → 400, sessiya ishlashda davom etadi.
  4 — login almashtirish: A sessiyasi cookie da turganda B foydalanuvchisi bilan kirish → 302, /users — faqat B.

REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ["TENANT_FILTER"] = "1"

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tf1_login_band_test"
_DB = os.path.join(tempfile.gettempdir(), "tf1_login_band_test.db")
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

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import tenant_context                              # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User                  # noqa: E402
from production_models import Company              # noqa: E402
from fastapi import HTTPException                  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond)
    except Exception:                      # noqa: BLE001
        cond = False
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:300]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


db = SessionLocal()
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="TF1 B korxona"))
    db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "A_ADMIN", "Parol123!", UserRole.ADMIN, "A", company_id=1)
    auth.create_user(db, "B_ADMIN", "Parol123!", UserRole.ADMIN, "B", company_id=2)
    auth.create_user(db, "B_BAND", "Parol123!", UserRole.MANAGER, "B band", company_id=2)
db.close()


def b_sanoq():
    s = SessionLocal()
    try:
        with tenant_context.system_context(s):
            return sorted(u.username for u in s.query(User).execution_options(skip_tenant_filter=True)
                          .filter(User.company_id == 2).all())
    finally:
        s.close()


section("0. Muhit")
check("TENANT_FILTER yoqilgan (tenant_context.ENABLED)", getattr(tenant_context, "ENABLED", False) is True)
B0 = b_sanoq()
check("B korxonada B_ADMIN, B_BAND", B0 == ["B_ADMIN", "B_BAND"], B0)

from sqlalchemy import event as _event                # noqa: E402
from database import engine as _engine               # noqa: E402
USERS_INSERT = []


@_event.listens_for(_engine, "before_cursor_execute")
def _yoz_insert(conn, cursor, statement, parameters, context, executemany):
    if " ".join(str(statement).split()).upper().startswith("INSERT INTO USERS"):
        USERS_INSERT.append(1)


section("1. API — A admini")
CA = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_l = req(CA, "post", "/login", data={"username": "A_ADMIN", "password": "Parol123!"}, follow_redirects=False)
check("A_ADMIN kirdi (302)", _l.status_code == 302, _l.status_code)
USERS_INSERT.clear()
r = req(CA, "post", "/api/users", json={"username": "B_BAND", "password": "Parol123!", "role": "manager", "full_name": "x"})
check("1.1 B korxonadagi band login → 400 'Bu username band' (asl: 500)",
      r.status_code == 400 and "band" in str((js(r) or {}).get("detail", "")), (r.status_code, getattr(r, "text", "")[:200]))
check("1.1b band login — INSERT urinishi YO'Q (oldindan tekshiruv butun tizim bo'yicha to'xtatdi; IntegrityError zaxira yo'li emas)",
      len(USERS_INSERT) == 0, len(USERS_INSERT))
r = req(CA, "post", "/api/users", json={"username": "A_YANGI", "password": "Parol123!", "role": "manager", "full_name": "y"})
check("1.2 yangi login → 200", r.status_code == 200 and (js(r) or {}).get("username") == "A_YANGI", (r.status_code, getattr(r, "text", "")[:200]))
r = req(CA, "post", "/api/users", json={"username": "A_YANGI", "password": "Parol123!", "role": "manager", "full_name": "y"})
check("1.3 o'sha login yana (o'z korxonasida band) → 400", r.status_code == 400, (r.status_code, getattr(r, "text", "")[:200]))
check("1.4 B korxona foydalanuvchilari o'zgarmadi", b_sanoq() == B0, b_sanoq())
s = SessionLocal()
try:
    _ay = s.query(User).execution_options(skip_tenant_filter=True).filter(User.username == "A_YANGI").first()
    _ayc = getattr(_ay, "company_id", None)
finally:
    s.close()
check("1.5 A_YANGI — A korxonasida (company_id 1)", _ayc == 1, _ayc)

section("2. Funksiya — kontekst A")
s = SessionLocal()
tenant_context.set_current_company(s, 1)
try:
    kod = None
    try:
        auth.create_user(s, "B_BAND", "Parol123!", UserRole.MANAGER, "z", company_id=1)
    except HTTPException as e:
        kod = e.status_code
    except Exception as e:                 # noqa: BLE001
        kod = type(e).__name__
    check("2.1 auth.create_user(kontekst A, 'B_BAND') → HTTPException 400 (asl: IntegrityError)", kod == 400, kod)
finally:
    s.rollback()
    s.close()

section("3. Parallel yaratish — tekshiruvdan keyin yozilgan login")


class _Soxta:
    """Haqiqiy sessiya; BIRINCHI `query` — tekshiruvni "bo'sh" deb qaytaradi (boshqa so'rov hali yozmagan payt)."""
    def __init__(self, s):
        self._s = s
        self._n = 0

    def query(self, *a, **k):
        self._n += 1
        if self._n == 1:
            class _Q:
                def execution_options(self, **kw):
                    return self

                def filter(self, *a, **kw):
                    return self

                def first(self):
                    return None
            return _Q()
        return self._s.query(*a, **k)

    def __getattr__(self, n):
        return getattr(self._s, n)


s = SessionLocal()
tenant_context.set_current_company(s, 1)
try:
    kod = None
    try:
        auth.create_user(_Soxta(s), "B_BAND", "Parol123!", UserRole.MANAGER, "p", company_id=1)
    except HTTPException as e:
        kod = e.status_code
    except Exception as e:                 # noqa: BLE001
        kod = type(e).__name__
    check("3.1 IntegrityError → 400 'Bu username band' (500 / xom IntegrityError EMAS)", kod == 400, kod)
    ishlaydi = None
    try:
        ishlaydi = s.query(User).execution_options(skip_tenant_filter=True).count()
    except Exception as e:                 # noqa: BLE001
        ishlaydi = type(e).__name__
    check("3.2 sessiya keyin ishlaydi (rollback qilingan)", isinstance(ishlaydi, int) and ishlaydi >= 4, ishlaydi)
finally:
    s.rollback()
    s.close()

section("4. Login almashtirish (A sessiyasi turganda B bilan kirish)")
_l = req(CA, "post", "/login", data={"username": "B_ADMIN", "password": "Parol123!"}, follow_redirects=False)
check("4.1 B_ADMIN bilan kirish → 302", _l.status_code == 302, _l.status_code)
r = req(CA, "get", "/users")
_t = getattr(r, "text", "") or ""
check("4.2 /users sahifasi — B korxonasi (B_ADMIN, B_BAND) bor, A korxonasi (A_ADMIN, A_YANGI) YO'Q",
      r.status_code == 200 and "B_ADMIN" in _t and "B_BAND" in _t and "A_ADMIN" not in _t and "A_YANGI" not in _t,
      (r.status_code, [n for n in ("B_ADMIN", "B_BAND", "A_ADMIN", "A_YANGI") if n in _t]))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
