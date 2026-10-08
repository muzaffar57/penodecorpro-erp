#!/usr/bin/env python3
"""
test_saas_marshrut.py — kech129 (zip 153): SaaS migratsiya HTTP sahifasi (`/saas-migratsiya`, `/api/saas-migration/*`, 8 marshrut)
OLIB TASHLANDI; migratsiya DVIGATELI (`saas_migration.STEPS`, `run_step`, `verify_tables`, `run_kod_migration`, `status_report`,
terminal buyrug'i) — `saas_otish` uchun QOLDI.

NIMA UCHUN KERAK
  O'LCHANGAN (kech129, `work/k153/probe_saas_router.py`, `probe_saas_router2.py`, HAQIQIY PG 16): 8 marshrut qorovuli `auth.admin_only`
  — ISTALGAN korxonaning admini (platforma egasi shart emas). Mijoz korxona admini (korxona 2): `GET /api/saas-migration/status` — 200,
  javobda BOSHQA korxona nomi, butun bazadagi jadval qatorlari soni va HAMMA tasdiq so'zlari; `POST /saas-migratsiya/haqiqiy/W1`
  (tasdiq so'zi bilan) — «HAQIQIY MIGRATSIYA BAJARILDI»: `users.company_id` ga `DEFAULT 1` QAYTA qo'shildi (to'lqinlar uni olib
  tashlagan edi — korxonasiz yozuv 1-korxonaga tushardi); `POST /saas-migratsiya/kod/haqiqiy` — boshqa korxonalarga kod yozdi.
  Sabab: `tools/test_rollar.py` kech123 da bu marshrutlarni `SAAS_IXTIYORIY` bilan jadvaldan chiqargan (Python 3.11 da modul yuklanmasdi).
  Migratsiya tugagan (staging 2026-09, `main` 2026-10-07): sahifa kerak emas; eski bazani o'tkazish — faqat ishga tushishda, avtomatik.
TALAB (har biri o'lchanadi):
  S  statik: ilovada `saas-migra` marshruti YO'Q; `main.py` routerni ulamaydi; `saas_migration` da `router` / FastAPI / HTML sahifa /
     «Sinov tenanti» YO'Q; dvigatel funksiyalari BOR; W-qadamlar = `saas_otish.OTISH_TARTIBI`; `test_rollar` da istisno YO'Q;
  H  HTTP: 8 marshrut — mijoz korxona admini, uning menejeri, platforma egasi va kirmagan foydalanuvchi uchun — 404;
  D  ma'lumot (faqat PG): mijoz admini tasdiq so'zlari bilan HAQIQIY qadam / kod / sinov tenanti so'rovlarini yuborgandan keyin —
     25 jadval `company_id` ustuni DEFAULT, `companies` (id, kod, nom) va korxonalar soni AYNAN;
  E  dvigatel (faqat PG): `status_report` — 13 qadam, xatosiz; `run_step(W1, dry_run)` va `run_kod_migration(dry_run)` — xatosiz va
     baza o'zgarmaydi; terminal buyrug'i `python3 saas_migration.py --status` — RC 0, JSON.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 152) qarshi QULAMAYDI — yiqiladi (yangi nomlar `getattr`, HTTP istisno — 599).
ISHLATISH: python3 tools/test_saas_marshrut.py
"""
import os
import sys
import io
import json
import tempfile
import importlib
import subprocess
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "saas_marshrut_test"
_DB = os.path.join(tempfile.gettempdir(), "saas_marshrut_test.db")
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
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import saas_otish                              # noqa: E402

from sqlalchemy import text                        # noqa: E402
from database import SessionLocal, engine         # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User                  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

try:
    with contextlib.redirect_stdout(_quiet):
        SM = importlib.import_module("saas_migration")
except Exception as _e:                            # noqa: BLE001
    SM = None
    print(f"  (saas_migration yuklanmadi: {type(_e).__name__}: {_e})")

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF] " if os.environ.get("TENANT_FILTER") else "")
OK = FAIL = 0
FAILED = []


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
        print(f"  ✗ {label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.content = b""
        self.headers = {}

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def xavfsiz(fn, standart=None):
    try:
        return fn()
    except Exception:                      # noqa: BLE001
        return standart


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: korxona 1 — platforma egasi; 2 — «SM Alfa» (mijoz); 3 — «SM Beta Raqib» (boshqa mijoz, kodsiz)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_db = SessionLocal()
for _cid, _nom in ((2, "SM Alfa Dekor"), (3, "SM Beta Raqib")):
    if not _db.query(Company).filter(Company.id == _cid).first():
        _db.add(Company(id=_cid, name=_nom))
_db.commit()
if "code" in Company.__table__.c:
    _db.execute(text("UPDATE companies SET code = NULL WHERE id IN (2, 3)"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "sm_ega", "Parol123!", UserRole.ADMIN, "Platforma Egasi", company_id=1)
    auth.create_user(_db, "sm_a_admin", "Parol123!", UserRole.ADMIN, "Alfa Admin", company_id=2)
    auth.create_user(_db, "sm_a_menejer", "Parol123!", UserRole.MANAGER, "Alfa Menejer", company_id=2)
_db.query(User).filter(User.username == "sm_ega").update({"is_platform_admin": True})
_db.query(User).filter(User.username.in_(["sm_a_admin", "sm_a_menejer"])).update(
    {"is_platform_admin": False}, synchronize_session=False)
_db.commit()
_db.close()


def mijoz(u):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    if u is None:
        return c, 302
    r = req(c, "post", "/login", data={"username": u, "password": "Parol123!"}, follow_redirects=False)
    return c, getattr(r, "status_code", 599)


CE, _s1 = mijoz("sm_ega")
CA, _s2 = mijoz("sm_a_admin")
CM, _s3 = mijoz("sm_a_menejer")
CK, _s4 = mijoz(None)
if {_s1, _s2, _s3, _s4} != {302}:
    print("LOGIN BO'LMADI", _s1, _s2, _s3, _s4)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

# Olib tashlangan 8 marshrut — (usul, yo'l, forma / so'rov) — tasdiq so'zlari bilan (asl kodda HAQIQIY bajarilardi)
MARSHRUTLAR = [
    ("get", "/saas-migratsiya", None),
    ("get", "/api/saas-migration/status", None),
    ("post", "/api/saas-migration/step/W1?dry_run=false&confirm=PENODECORPRO-STEP1", None),
    ("post", "/saas-migratsiya/sinov/W1", None),
    ("post", "/saas-migratsiya/haqiqiy/W1", {"confirm": "PENODECORPRO-STEP1"}),
    ("post", "/saas-migratsiya/kod/sinov", None),
    ("post", "/saas-migratsiya/kod/haqiqiy", {"confirm": "PENODECORPRO-M1KOD"}),
    ("post", "/saas-migratsiya/sinov-tenant", {"confirm": "PENODECORPRO-TENANT-B", "parol": "Parol123!"}),
]


def surat():
    """Faqat PG: 25 to'lqin jadvali `company_id` DEFAULT, `companies` (id, kod, nom)."""
    if not PG_URL:
        return None
    with engine.connect() as c:
        d = c.execute(text(
            "SELECT table_name, coalesce(column_default, '') FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'company_id' ORDER BY table_name")).all()
        k = c.execute(text("SELECT id, coalesce(code, ''), name FROM companies ORDER BY id")).all()
    return {"default": [tuple(r) for r in d], "korxonalar": [tuple(r) for r in k]}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_yollar = set()


def _yigish(routes):
    """FastAPI 0.141: `include_router` marshrutlarni `_IncludedRouter` ichida saqlaydi (`original_router.routes`) — ichiga kiriladi
    (aks holda ulangan router marshrutlari ko'rinmaydi va tekshiruv asl kodda ham o'tib ketardi — O'LCHANDI)."""
    for _r in routes:
        _ichki = getattr(_r, "original_router", None)
        if _ichki is not None:
            _yigish(getattr(_ichki, "routes", []) or [])
            continue
        _yollar.add(getattr(_r, "path", ""))


_yigish(main.app.routes)
_saas_yol = sorted(y for y in _yollar if "saas-migra" in y or "saas_migra" in y)
check("S1 ilovada SaaS migratsiya marshruti YO'Q (`/saas-migratsiya`, `/api/saas-migration/*`; ulangan routerlar ichi ham)",
      not _saas_yol and any(y.startswith("/api/production/") for y in _yollar),
      (_saas_yol, len(_yollar), "ulangan production_router ko'rindimi:", any(y.startswith("/api/production/") for y in _yollar)))
_main = fayl("main.py")
check("S2 `main.py` SaaS migratsiya routerini ulamaydi (`from saas_migration import router` / `include_router(saas_` yo'q)",
      "from saas_migration import router" not in _main and "include_router(saas_" not in _main
      and "import saas_otish as _saas_otish" in _main)
_sm = fayl("saas_migration.py")
check("S3 `saas_migration`: `router` atributi, FastAPI / `HTMLResponse`, `@router.` YO'Q",
      SM is not None and not hasattr(SM, "router") and "APIRouter" not in _sm and "HTMLResponse" not in _sm
      and "@router." not in _sm and "from fastapi" not in _sm,
      [n for n in ("APIRouter", "HTMLResponse", "@router.", "from fastapi") if n in _sm])
check("S4 HTML sahifa va «Sinov tenanti» vositasi YO'Q (`_render_page`, `create_test_tenant`, `tenant_status`, `SINOV-TENANT`)",
      SM is not None and not [n for n in ("_render_page", "create_test_tenant", "tenant_status", "_CSS", "run_step1")
                              if hasattr(SM, n)]
      and "SINOV-TENANT" not in _sm and "ZZZ_SINOV_KORXONA_B" not in _sm,
      [n for n in ("_render_page", "create_test_tenant", "tenant_status", "_CSS", "run_step1") if SM is not None and hasattr(SM, n)])
_dvigatel = ("STEPS", "run_step", "verify_tables", "run_kod_migration", "status_report", "kod_status", "_step", "environment_info")
check("S5 dvigatel QOLDI: " + ", ".join(_dvigatel),
      SM is not None and all(hasattr(SM, n) for n in _dvigatel),
      [n for n in _dvigatel if SM is None or not hasattr(SM, n)])
_kalitlar = [s.get("kalit") for s in (getattr(SM, "STEPS", None) or [])]
check("S6 `STEPS` = W1 … W6 (W2B, W3B bilan) + TEKSHIRUV + M1KOD (13); W-qadamlar = `saas_otish.OTISH_TARTIBI` (tartibi bilan)",
      _kalitlar == list(saas_otish.OTISH_TARTIBI) + ["TEKSHIRUV", "M1KOD"], _kalitlar)
check("S7 `saas_otish.otish` dvigatelni FAQAT eski bazada yuklaydi (modul darajasida `import saas_migration` yo'q)",
      "\nimport saas_migration" not in fayl("saas_otish.py") and "import saas_migration as sm" in fayl("saas_otish.py"))
_tr = fayl("tools/test_rollar.py")
check("S8 `tools/test_rollar.py` — `SAAS_IXTIYORIY` istisnosi YO'Q (har marshrut ruxsat jadvalida)",
      "SAAS_IXTIYORIY = {" not in _tr and "not in SAAS_IXTIYORIY" not in _tr
      and "_jadvalsiz = sorted(k for k in MARSHRUT if k not in ESKI and k not in YANGI_MARSHRUTLAR)\n" in _tr)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. HTTP — 8 marshrut hamma uchun 404")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_oldin = surat()
for _kod, (_c, _nom) in (("H1", (CA, "mijoz korxona admini")), ("H2", (CM, "mijoz menejeri")),
                         ("H3", (CE, "platforma egasi")), ("H4", (CK, "kirmagan"))):
    _nat = []
    for _m, _y, _forma in MARSHRUTLAR:
        _k = {"follow_redirects": False}
        if _forma is not None:
            _k["data"] = _forma
        _r = req(_c, _m, _y, **_k)
        _nat.append((_m.upper(), _y.split("?")[0], _r.status_code))
    check(f"{_kod} {_nom}: 8 marshrut — hammasi 404", all(s == 404 for _, _, s in _nat), [x for x in _nat if x[2] != 404])
_r = req(CA, "get", "/api/saas-migration/status")
check("H5 mijoz admini holat javobida boshqa korxona nomi («SM Beta Raqib») va tasdiq so'zi YO'Q",
      "SM Beta Raqib" not in _r.text and "PENODECORPRO-" not in _r.text, _r.text[:300])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Ma'lumot o'zgarmadi (faqat PG)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    _keyin = surat()
    _d_farq = sorted(set(_oldin["default"]) ^ set(_keyin["default"]))
    check("D1 25+ jadval `company_id` DEFAULT — 8 marshrut so'rovlaridan keyin AYNAN (asl kodda `users` ga DEFAULT 1 qaytardi)",
          _oldin["default"] == _keyin["default"] and len(_keyin["default"]) >= 25, _d_farq[:6])
    check("D2 `users.company_id` — DEFAULT YO'Q (korxonasiz yozuv 1-korxonaga tushmaydi)",
          dict(_keyin["default"]).get("users", "x") == "", dict(_keyin["default"]).get("users"))
    check("D3 `companies` (id, kod, nom) va korxonalar soni AYNAN (asl kodda M1KOD 2 va 3 ga kod yozdi; sinov tenanti yaratilmadi)",
          _oldin["korxonalar"] == _keyin["korxonalar"], (_oldin["korxonalar"], _keyin["korxonalar"]))
else:
    print("  (SQLite — D bo'limi faqat PG da)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Dvigatel ishlaydi (faqat PG)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL and SM is not None:
    _e0 = surat()
    _st = xavfsiz(lambda: SM.status_report(engine), {})
    _q = _st.get("qadamlar") or []
    check("E1 `status_report` — 13 qadam (W1 … M1KOD), xato yo'q, `tenant` turi yo'q",
          len(_q) == 13 and "xato" not in _st and not [x for x in _q if x.get("tur") == "tenant"],
          (len(_q), _st.get("xato"), [x.get("kalit") for x in _q]))
    _w1 = xavfsiz(lambda: SM.run_step(engine, "W1", dry_run=True), {"xato": "istisno"})
    check("E2 `run_step(W1, dry_run=True)` — xatosiz", not _w1.get("xato") and "DRY-RUN" in str(_w1.get("rejim", "")),
          (_w1.get("natija"), _w1.get("xato")))
    _k1 = xavfsiz(lambda: SM.run_kod_migration(engine, dry_run=True), {"xato": "istisno"})
    check("E3 `run_kod_migration(dry_run=True)` — xatosiz", not _k1.get("xato"), (_k1.get("natija"), _k1.get("xato")))
    check("E4 dry-run dan keyin baza AYNAN (DEFAULT, korxonalar, kodlar)", surat() == _e0)
    _env = dict(os.environ, DATABASE_URL=f"{PG_URL}/{PG_BAZA}")
    _env.pop("TENANT_FILTER", None)
    try:
        _p = subprocess.run([sys.executable, "saas_migration.py", "--status"], cwd=ROOT, env=_env, capture_output=True,
                            text=True, timeout=300)
        _js = _p.stdout[_p.stdout.find("{"):] if "{" in _p.stdout else ""
        _pj = json.loads(_js) if _js else {}
        _rc = _p.returncode
    except Exception as e:                 # noqa: BLE001
        _pj, _rc = {}, f"{type(e).__name__}: {e}"
    check("E5 terminal: `python3 saas_migration.py --status` — RC 0, JSON 13 qadam", _rc == 0 and len(_pj.get("qadamlar") or []) == 13,
          (_rc, list(_pj)[:4]))
else:
    print("  (SQLite — E bo'limi faqat PG da)")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
