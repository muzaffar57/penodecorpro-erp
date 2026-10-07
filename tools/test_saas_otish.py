#!/usr/bin/env python3
"""
test_saas_otish.py — kech109 darvozasi: `main` ko'chirishi (K108-1) — `saas_otish.py` va korxona id ketma-ketligi (K109-3).

NIMA UCHUN KERAK (O'LCHANGAN)
-----------------------------
K108-1 (kech108, `main` zaxirasining lokal nusxasi, HAQIQIY PG 16): SaaS to'lqinlarisiz `main` bazasida `staging` kodi
  IMPORTDA yiqilardi (`auth.create_default_admin` — `users.company_id` yo'q) va undan oldin 5 migratsiya QISMAN
  bajarilardi. Ikki bosqichli (to'lqinlar sahifasi, keyin kod) o'rniga — BITTA yuklash: `saas_otish.startup_otish`
  `init_database()` dan OLDIN eski bazani aniqlab, to'lqinlarni SINOV (bitta tranzaksiya, har qadam savepoint,
  oxirida hammasi qaytariladi) → HAQIQIY (har qadam o'z tranzaksiyasi) tartibida bajaradi. Haqiqiy `main` ma'lumoti
  ustidagi to'liq sinov — `work/otish109.sh` (python3.12, `saas_migration` 3.12 sintaksisi); bu test MEXANIZMNI
  tekshiradi (soxta `saas_migration` bilan — 3.11 da ham).
K109-3 (`work/probe109k.py`, HAQIQIY PG 16, asl kod `bd0b48c`): toza bazada platformadan BIRINCHI "korxona qo'shish"
  400 — "duplicate key … companies_pkey (id)=(1)" (korxona id=1 ANIQ yozilgan, ketma-ketlik surilmagan), ikkinchisi
  o'tardi. Endi har ishga tushishda ketma-ketlik MAX(id) ga tenglashtiriladi.

BO'LIMLAR
  A — `otish_kerakmi`: SQLite / bo'sh PG / eski `users` / qisman to'lqin / to'liq to'lqin / staging sxemasi.
  B — `otish` mexanizmi (soxta `sm`, haqiqiy PG): hammasi OK; SINOVDA to'xtash (baza O'ZGARMAYDI, korxonalar jadvali
      ham yo'q); HAQIQIY da to'xtash (oldingi qadamlar saqlangan, keyingisi yo'q); TEKSHIRUV to'xtatadi; SINOVda
      keyingi qadam oldingisining natijasini KO'RADI (savepoint); `startup_otish` — xatoda RuntimeError.
  K — K109-3: ilova ishga tushgach platformadan birinchi "korxona qo'shish" — 200 (SQLite va PG).
  S — statik: `main.py` da `startup_otish` `init_database()` dan OLDIN; tartib va jadval ro'yxati `saas_migration.STEPS`
      bilan AYNAN (matndan — 3.12 modul 3.11 da yuklanmaydi).
REJIMLAR: SQLite (A1, K, S); `PG_URL` — hammasi (har ishga YANGI PG bazalari).
"""
import os
import re
import sys
import types
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "saas_otish_test"
_DB = os.path.join(tempfile.gettempdir(), "saas_otish_test.db")

from sqlalchemy import create_engine, text  # noqa: E402


def _pg(url_baza):
    return create_engine(url_baza.replace("postgresql://", "postgresql+pg8000://", 1))


def _yangi_baza(nom):
    adm = create_engine(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
                        isolation_level="AUTOCOMMIT")
    with adm.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {nom} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {nom}"))
    adm.dispose()
    return _pg(f"{PG_URL}/{nom}")


if PG_URL:
    _yangi_baza(PG_BAZA).dispose()
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
try:
    import saas_otish as SO                        # noqa: E402
except Exception:                                  # noqa: BLE001
    SO = None
from database import SessionLocal                  # noqa: E402
from models import User, UserRole                  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


def f(nom):
    """saas_otish dagi nom (asl kodda modul yo'q — None, QULAMAYDI)."""
    return getattr(SO, nom, None) if SO is not None else None


def chaqir(fn, *a, **k):
    if fn is None:
        return ("XATO", "funksiya yo'q")
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {str(e)[:200]}")


# ══════════════════════════════════════════════════════════════
# A. otish_kerakmi
# ══════════════════════════════════════════════════════════════
section("A. Eski bazani aniqlash")
_sq = create_engine(f"sqlite:///{os.path.join(tempfile.gettempdir(), 'saas_otish_a1.db')}")
with _sq.begin() as c:
    c.execute(text("DROP TABLE IF EXISTS users"))
    c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50))"))
check("A1 SQLite (users company_id siz) — False (faqat PostgreSQL)", chaqir(f("otish_kerakmi"), _sq) is False,
      chaqir(f("otish_kerakmi"), _sq))
_sq.dispose()

JADVALLAR = list(f("TOLQIN_JADVALLARI") or ())

if PG_URL:
    e = _yangi_baza("saas_otish_a")
    check("A2 bo'sh PG baza (jadval yo'q) — False", chaqir(f("otish_kerakmi"), e) is False, chaqir(f("otish_kerakmi"), e))
    with e.begin() as c:
        c.execute(text("CREATE TABLE users (id SERIAL PRIMARY KEY, username VARCHAR(50))"))
        c.execute(text("CREATE TABLE orders (id SERIAL PRIMARY KEY)"))
    check("A3 eski baza (users company_id siz) — True", chaqir(f("otish_kerakmi"), e) is True, chaqir(f("otish_kerakmi"), e))
    with e.begin() as c:
        c.execute(text("ALTER TABLE users ADD COLUMN company_id INTEGER"))
    check("A4 qisman o'tgan (users bor, orders da company_id yo'q) — True", chaqir(f("otish_kerakmi"), e) is True,
          chaqir(f("otish_kerakmi"), e))
    with e.begin() as c:
        c.execute(text("ALTER TABLE orders ADD COLUMN company_id INTEGER"))
    check("A5 mavjud to'lqin jadvallarining hammasida company_id — False", chaqir(f("otish_kerakmi"), e) is False,
          chaqir(f("otish_kerakmi"), e))
    e.dispose()
    from database import engine as _ilova_motori
    check("A6 staging sxemasi (ilovaning o'z toza bazasi) — False", chaqir(f("otish_kerakmi"), _ilova_motori) is False,
          chaqir(f("otish_kerakmi"), _ilova_motori))

# ══════════════════════════════════════════════════════════════
# B. otish mexanizmi (soxta saas_migration, haqiqiy PG)
# ══════════════════════════════════════════════════════════════
if PG_URL:
    section("B. SINOV → HAQIQIY mexanizmi (soxta saas_migration)")
    TARTIB = list(f("OTISH_TARTIBI") or ())

    def soxta_sm(sinov_xato=None, haqiqiy_xato=None, verify_xato=None, korish=None):
        """run_step: jurnal jadvaliga qadam nomi yoziladi (saas_migration naqshi: connect → begin → commit/rollback)."""
        kuzatuv = {"korgan": {}}
        SinovMotori = f("_SinovMotori")

        def run_step(motor, k, dry_run=True):
            sinovmi = SinovMotori is not None and isinstance(motor, SinovMotori)
            conn = motor.connect()
            trans = conn.begin()
            try:
                if korish and k == korish[1]:
                    kuzatuv["korgan"][("sinov" if sinovmi else "haqiqiy")] = conn.execute(
                        text("SELECT COUNT(*) FROM jurnal WHERE qadam = :q"), {"q": korish[0]}).scalar()
                conn.execute(text("INSERT INTO jurnal (qadam) VALUES (:q)"), {"q": k})
                xato = (sinov_xato if sinovmi else haqiqiy_xato)
                if xato == k:
                    trans.rollback()
                    return {"natija": "⛔ TO'XTATILDI", "xato": f"{k}: soxta to'xtash"}
                trans.commit()
                return {"natija": "✅", "xato": None}
            finally:
                conn.close()

        def verify_tables(motor):
            with motor.connect() as c:
                n = c.execute(text("SELECT COUNT(*) FROM jurnal")).scalar()
            return [{"jadval": "jurnal", "mavjud": True, "NULL_company_id": (1 if verify_xato else 0),
                     "yetim_company_id": 0, "nomuvofiq": [], "qatorlar": n}]

        def run_kod_migration(motor, dry_run=True):
            conn = motor.connect()
            trans = conn.begin()
            try:
                conn.execute(text("INSERT INTO jurnal (qadam) VALUES ('M1KOD')"))
                trans.commit()
                return {"natija": "✅", "xato": None}
            finally:
                conn.close()

        return types.SimpleNamespace(run_step=run_step, verify_tables=verify_tables,
                                     run_kod_migration=run_kod_migration), kuzatuv

    def tayyor(nom):
        e = _yangi_baza(nom)
        with e.begin() as c:
            c.execute(text("CREATE TABLE users (id SERIAL PRIMARY KEY, username VARCHAR(50))"))
            c.execute(text("CREATE TABLE jurnal (id SERIAL PRIMARY KEY, qadam VARCHAR(20))"))
        return e

    def jurnal(e):
        with e.connect() as c:
            return [r[0] for r in c.execute(text("SELECT qadam FROM jurnal ORDER BY id")).fetchall()]

    def korxonalar(e):
        with e.connect() as c:
            if not c.execute(text("SELECT to_regclass('public.companies')")).scalar():
                return None
            return [tuple(r) for r in c.execute(text("SELECT id, name FROM companies ORDER BY id")).fetchall()]

    CH = []

    def chiqar(s):
        CH.append(str(s))

    check("B0 tartib: W1 … W6 (11 qadam, W2B / W3B ichida)", TARTIB == ["W1", "W2G1", "W2G2", "W2G3", "W2G4", "W2B",
                                                                       "W3", "W3B", "W4", "W5", "W6"], TARTIB)
    # B1 — hammasi OK
    e = tayyor("saas_otish_b1")
    sm, _ = soxta_sm()
    r = chaqir(f("otish"), e, sm=sm, chiqar=chiqar)
    check("B1 hammasi OK — ok True, bosqich 'haqiqiy'", isinstance(r, dict) and r.get("ok") is True
          and r.get("bosqich") == "haqiqiy", r)
    check("B2 jurnalda FAQAT haqiqiy bosqich: 11 qadam + M1KOD, har biri BIR marta (SINOV qaytarilgan)",
          jurnal(e) == TARTIB + ["M1KOD"], jurnal(e))
    check("B3 asosiy korxona yaratildi (id=1, PenodecorPro)", korxonalar(e) == [(1, "PenodecorPro")], korxonalar(e))
    try:
        with e.begin() as c:
            _n = c.execute(text("SELECT nextval(pg_get_serial_sequence('companies', 'id'))")).scalar()
    except Exception as _xe:               # noqa: BLE001 — B1 muvaffaqiyatsiz bo'lsa jadval yo'q (QULAMASIN)
        _n = ("XATO", f"{type(_xe).__name__}: {str(_xe)[:120]}")
    check("B4 korxona id ketma-ketligi surilgan (keyingi id = 2)", _n == 2, _n)
    e.dispose()

    # B5 — SINOVDA to'xtash
    e = tayyor("saas_otish_b5")
    sm, _ = soxta_sm(sinov_xato="W3")
    CH.clear()
    r = chaqir(f("otish"), e, sm=sm, chiqar=chiqar)
    check("B5 SINOVDA W3 to'xtadi — ok False, bosqich 'sinov', qadam W3", isinstance(r, dict) and r.get("ok") is False
          and r.get("bosqich") == "sinov" and r.get("qadam") == "W3", r)
    check("B6 baza O'ZGARMADI: jurnal bo'sh, companies jadvali YO'Q (SINOV to'liq qaytarildi)",
          jurnal(e) == [] and korxonalar(e) is None, (jurnal(e), korxonalar(e)))
    e.dispose()

    # B7 — HAQIQIY da to'xtash
    e = tayyor("saas_otish_b7")
    sm, _ = soxta_sm(haqiqiy_xato="W4")
    r = chaqir(f("otish"), e, sm=sm, chiqar=chiqar)
    check("B7 SINOV o'tdi, HAQIQIY W4 da to'xtadi — ok False, bosqich 'haqiqiy', qadam W4",
          isinstance(r, dict) and r.get("ok") is False and r.get("bosqich") == "haqiqiy" and r.get("qadam") == "W4", r)
    check("B8 oldingi qadamlar (W1 … W3B) saqlangan, W4 va keyingilar YO'Q",
          jurnal(e) == TARTIB[:TARTIB.index("W4")] if "W4" in TARTIB else False, jurnal(e))
    e.dispose()

    # B9 — TEKSHIRUV to'xtatadi
    e = tayyor("saas_otish_b9")
    sm, _ = soxta_sm(verify_xato=True)
    r = chaqir(f("otish"), e, sm=sm, chiqar=chiqar)
    check("B9 TEKSHIRUV (bo'sh company_id) — SINOVDA to'xtaydi, baza o'zgarmadi",
          isinstance(r, dict) and r.get("ok") is False and r.get("bosqich") == "sinov" and r.get("qadam") == "TEKSHIRUV"
          and jurnal(e) == [] and korxonalar(e) is None, (r, jurnal(e), korxonalar(e)))
    e.dispose()

    # B10 — SINOVDA keyingi qadam oldingisini ko'radi
    e = tayyor("saas_otish_b10")
    sm, kz = soxta_sm(korish=("W2G1", "W3"))
    r = chaqir(f("otish"), e, sm=sm, chiqar=chiqar)
    check("B10 SINOVDA W3 o'z ichida W2G1 natijasini ko'radi (bitta tranzaksiya, savepoint) — 1; HAQIQIY da ham 1",
          kz["korgan"].get("sinov") == 1 and kz["korgan"].get("haqiqiy") == 1, kz)
    e.dispose()

    # B11 — startup_otish: xatoda RuntimeError, kerak bo'lmasa False
    e = tayyor("saas_otish_b11")
    _asl_otish = f("otish")
    if SO is not None and _asl_otish is not None:
        SO.otish = lambda motor, sm=None, chiqar=print: _asl_otish(motor, sm=soxta_sm(sinov_xato="W1")[0], chiqar=chiqar)
    _rt = chaqir(f("startup_otish"), e, chiqar=chiqar)
    if SO is not None and _asl_otish is not None:
        SO.otish = _asl_otish
    check("B11 startup_otish — SINOV to'xtasa RuntimeError (ilova ishga tushmaydi)",
          isinstance(_rt, tuple) and "RuntimeError" in str(_rt[1]), _rt)
    with e.begin() as c:
        c.execute(text("ALTER TABLE users ADD COLUMN company_id INTEGER"))
    check("B12 startup_otish — kerak bo'lmasa False (hech narsa qilinmaydi)",
          chaqir(f("startup_otish"), e, chiqar=chiqar) is False and korxonalar(e) is None, korxonalar(e))
    e.dispose()

# ══════════════════════════════════════════════════════════════
# K. K109-3 — birinchi "korxona qo'shish"
# ══════════════════════════════════════════════════════════════
section("K. K109-3 — korxona id ketma-ketligi")
_s = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_s, "SO_PA", "Parol123!", UserRole.ADMIN, "SO PA", company_id=1)
_u = _s.query(User).filter(User.username == "SO_PA").first()
_u.is_platform_admin = True
_s.commit()
_s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = C.post("/login", data={"username": "SO_PA", "password": "Parol123!"}, follow_redirects=False)
_r = C.post("/api/platform/companies", data={"name": "SO Yangi korxona", "admin_username": "so_yangi_admin"})
_d = {}
try:
    _d = _r.json()
except Exception:                          # noqa: BLE001
    _d = {"raw": _r.text[:300]}
check("K1 platformadan BIRINCHI 'korxona qo'shish' — 200, yangi id 2 (asl PG: 400 duplicate key companies_pkey)",
      _lr.status_code == 302 and _r.status_code == 200 and (_d.get("company") or {}).get("id") == 2, (_r.status_code, _d))

# ══════════════════════════════════════════════════════════════
# S. Statik
# ══════════════════════════════════════════════════════════════
section("S. Statik")
_main = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


check("S1 main.py: `_saas_otish.startup_otish(` modul darajasida `init_database()` dan OLDIN",
      tartibda(_main, "import saas_otish as _saas_otish", "\n_saas_otish.startup_otish(_otish_motori)\n",
               "\ninit_database()\n"))
_sm_txt = open(os.path.join(ROOT, "saas_migration.py"), encoding="utf-8").read()
_kalitlar = re.findall(r'"kalit":\s*"([A-Z0-9-]+)"', _sm_txt)
_ustun_qadam = [k for k in _kalitlar if re.fullmatch(r"W\d+(G\d+|B)?", k)]
check("S2 OTISH_TARTIBI = saas_migration.STEPS dagi W-qadamlar (tartibi bilan)",
      list(f("OTISH_TARTIBI") or ()) == _ustun_qadam, (_ustun_qadam, f("OTISH_TARTIBI")))
_jad = []
for _blok in re.findall(r'"jadvallar":\s*\[(.*?)\]', _sm_txt, re.S):
    _jad += re.findall(r'"([a-z_]+)"', _blok)
check("S3 TOLQIN_JADVALLARI = saas_migration.STEPS 'jadvallar' (25 jadval, tartibi bilan)",
      list(JADVALLAR) == _jad and len(_jad) == 25, (len(_jad), _jad[:5], JADVALLAR[:5]))
_seed = inspect.getsource(main._seed_default_company) if hasattr(main, "_seed_default_company") else ""
check("S4 `_seed_default_company` — PG da companies id ketma-ketligi MAX(id) ga (setval)",
      "setval(pg_get_serial_sequence('companies', 'id')" in _seed, _seed[-400:])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
