#!/usr/bin/env python3
"""
test_sxema_n4.py — kech144 (zip 172): N4 — PRODUCTION BAZASI SXEMASI KODDAN FARQ QILADI (va jurnal xatosi yutilishi).

NIMA UCHUN KERAK (har biri O'LCHANGAN — asl kod zip 171b, `work/k172/`):
  N4  12.10 11:47 production: `PUT /api/orders/196` — tahrir SAQLANGAN, so'ng jurnal yozuvi «value too long for type
      character varying(255)» → `except Exception: pass` (rollback siz) → PendingRollbackError → 500. Sabab:
      `database._sql_type_for_column` da `isinstance(t, String)` BIRINCHI — `Text` esa `String` ning bolasi: keyinroq
      qo'shilgan HAR matn ustuni production da VARCHAR(255) (`main` tarixidan qayta qurilgan baza — 9 ta ustun: jurnal
      old / new_value, «yopish» nusxasi, loy manbasi, avans rad sababi, bonus izohi, MRP yozuvlari, gips qo'shimchalari).
      Sinovlar va zaxira nusxalari sxemani KODDAN yaratadi — xato hech qachon ko'rinmagan.
BO'LIMLAR:
  A — `_sql_type_for_column` — har model ustuni = dialekt kompilyatori (`create_all`) turi (asl: Text → VARCHAR(255)).
  C — (PG) ishga tushishda kengaytirish: production kabi toraytirilgan bazada `import main` → TEXT / VARCHAR(200) /
      NUMERIC(12,2), ustun izohi, qiymatlar o'zgarmaydi, takror — o'zgarishsiz, «qo'lda» farq — tegilmaydi, yangi baza — 0 farq.
  B — `sync_missing_columns`: ustunlarsiz eski bazada qo'shilgan ustun turi = yangi bazadagi (Text, String, Numeric, Enum +
      standart).
  D — buyurtma tahriri / yuk xati bor buyurtmani o'chirish — uzun jurnal / «yopish» nusxasi saqlanadi (asl PG: 500).
  E — jurnal yozuvi yiqilsa (sun'iy xato): amal saqlanadi, 200, sessiya toza, sabab «Xatoliklar» da; buyurtma yaratish —
      bitta buyurtma (takror / yarim yo'q).
  F — «Tizim salomatligi» (`/api/system/health-check`): platforma admini — `sxema`; oddiy admin — yo'q.
  G — «kim»: buyurtma yaratish / tahrir / faollashtirish jurnalida foydalanuvchi (asl: bo'sh).
  X — kutilmagan 5xx yo'q.
REJIMLAR: SQLite (odatiy) va `PG_URL` bilan HAQIQIY PostgreSQL 16 (C va D ning sxema qismi faqat PG da — SQLite ustun
  uzunligini tekshirmaydi). Asl kodga qarshi QULAMAYDI (yangi nomlar — `getattr`).
ISHLATISH: python3 tools/test_sxema_n4.py   |   PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_sxema_n4.py
"""
import os
import sys
import io
import contextlib
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "sxema_n4_test"
PG_YANGI = "sxema_n4_yangi"
_T = tempfile.mkdtemp(prefix="sxema_n4_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        for _b in (PG_BAZA, PG_YANGI):
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {_b} WITH (FORCE)"))
            _c.execute(_tx(f"CREATE DATABASE {_b}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'sxema_n4_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "RESET_ADMIN_PASSWORD", "TELEGRAM_WEBHOOK_SECRET"):
    os.environ.pop(_k, None)

from sqlalchemy import text, event                 # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HOLATLAR = []
KUTILGAN_IDX = set()                       # ataylab 5xx bo'lishi mumkin bo'lgan so'rovlar (HOLATLAR indeksi)


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
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


def xav(fn, standart=None):
    """Bitta qadam yiqilsa butun test qulamasin."""
    try:
        return fn()
    except Exception as e:                 # noqa: BLE001
        print(f"    (qadam yiqildi: {type(e).__name__}: {str(e)[:300]})")
        return standart


# ══════════════════════════════════════════════════════════════
# 0. «PRODUCTION HOLATI» (faqat PG): jadvallar KODDAN yaratiladi va production dagi kabi TORAYTIRILADI — `import main` dan OLDIN.
#    Ro'yxat — `main` tarixidan qayta qurilgan baza (`work/k172/replay_main.py`, `sxema_oqi.py`): 9 ta Text ustun VARCHAR(255).
#    Qo'shimcha kengaytirish turlari: String uzunligi (VARCHAR(60) → 200), NUMERIC aniqligi (10,2 → 12,2).
#    «Qo'lda» farq (ENUM o'rnida VARCHAR — qayta yaratilgan bazadagi kabi) — avtomatik o'zgartirilmasligi kerak.
# ══════════════════════════════════════════════════════════════
TORAYTIRISH = [
    ("activity_logs", "old_value", "VARCHAR(255)", "TEXT"), ("activity_logs", "new_value", "VARCHAR(255)", "TEXT"),
    ("advance_requests", "rad_sababi", "VARCHAR(255)", "TEXT"), ("delivery_items", "mrp_olingan", "VARCHAR(255)", "TEXT"),
    ("employee_monthly_adjustments", "bonus_reason", "VARCHAR(255)", "TEXT"),
    ("finished_products", "gips_additives_json", "VARCHAR(255)", "TEXT"),
    ("orders", "loy_manba_json", "VARCHAR(255)", "TEXT"), ("orders", "ochirish_yopish_json", "VARCHAR(255)", "TEXT"),
    ("return_items", "mrp_ozod", "VARCHAR(255)", "TEXT"),
    # kech154 (zip 202, V5): jurnal sarlavhasi — Text (production da VARCHAR(200)); VARCHAR → VARCHAR namunasi — murojaat sahifasi
    ("activity_logs", "entity_label", "VARCHAR(200)", "TEXT"), ("murojaatlar", "kelgan_sahifa", "VARCHAR(60)", "VARCHAR(200)"),
    ("orders", "agreed_amount", "NUMERIC(10,2)", "NUMERIC(12,2)"),
]
QOLDA = ("finished_products", "production_status")
# «Qo'lda» xabarlari (avtomatik tuzatilmaydi): kodda ixtiyoriy — bazada NOT NULL; kodda yo'q — bazada majburiy, standartsiz
QOLDA_NN = ("takliflar", "telefon")
QOLDA_ORTIQ = ("takliflar", "eski_ustun")
_bosh_chiqish = io.StringIO()
if PG_URL:
    import database as _database0                  # noqa: E402
    __import__("models")                           # jadvallar metadata ga (create_all uchun)
    __import__("production_models")
    _database0.Base.metadata.create_all(bind=_database0.engine)
    with _database0.engine.begin() as _c:
        for _t, _u, _tur, _ in TORAYTIRISH:
            _c.execute(text(f"ALTER TABLE {_t} ALTER COLUMN {_u} TYPE {_tur}"))
        _c.execute(text(f"ALTER TABLE {QOLDA[0]} ALTER COLUMN {QOLDA[1]} TYPE VARCHAR(20) USING {QOLDA[1]}::text"))
        _c.execute(text(f"ALTER TABLE {QOLDA_NN[0]} ALTER COLUMN {QOLDA_NN[1]} SET NOT NULL"))
        _c.execute(text(f"ALTER TABLE {QOLDA_ORTIQ[0]} ADD COLUMN {QOLDA_ORTIQ[1]} INTEGER NOT NULL"))

with contextlib.redirect_stdout(_bosh_chiqish):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import database                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, ActivityLog, ErrorLog, Order, Murojaat    # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

BOSH = _bosh_chiqish.getvalue()
PAROL = "Parol123!"
with TestClient(main.app, base_url="https://testserver") as _c0:      # startup
    _c0.get("/login")

db = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    for _u, _rol in (("sx_egasi", UserRole.ADMIN), ("sx_admin", UserRole.ADMIN)):
        auth.create_user(db, _u, PAROL, _rol, _u.upper(), company_id=1)
db.query(User).filter(User.is_platform_admin == True).update({User.is_platform_admin: False})   # noqa: E712
db.query(User).filter(User.username == "sx_egasi").update({User.is_platform_admin: True})
db.commit()
db.close()


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"

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


def mijoz():
    return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)


EGASI = mijoz()
_r = req(EGASI, "post", "/login", data={"username": "sx_egasi", "password": PAROL}, follow_redirects=False)
check("S0 platforma egasi kirdi", _r.status_code in (302, 303), _r.status_code)
ADM = mijoz()
_r = req(ADM, "post", "/login", data={"username": "sx_admin", "password": PAROL}, follow_redirects=False)
check("S0b oddiy admin kirdi", _r.status_code in (302, 303), _r.status_code)
main._send_telegram = lambda *a, **k: None


def ustun_turi(jadval, ustun):
    """PG: (data_type, max_len, precision, scale, udt_name, default); SQLite: (PRAGMA turi, standart)."""
    with database.engine.connect() as c:
        if PG_URL:
            r = c.execute(text("SELECT data_type, character_maximum_length, numeric_precision, numeric_scale, udt_name, "
                               "column_default FROM information_schema.columns WHERE table_schema = current_schema() "
                               "AND table_name = :t AND column_name = :u"), {"t": jadval, "u": ustun}).fetchone()
            return tuple(r) if r else None
        for r in c.execute(text(f"PRAGMA table_info({jadval})")).fetchall():
            if r[1] == ustun:
                return (str(r[2]).upper(), r[4])
    return None


def pg_tur_matn(t):
    """information_schema qatori → «TEXT» / «VARCHAR(200)» / «NUMERIC(12,2)»."""
    if not t:
        return None
    if t[0] == "text":
        return "TEXT"
    if t[0] == "character varying":
        return f"VARCHAR({t[1]})" if t[1] else "VARCHAR"
    if t[0] == "numeric":
        return f"NUMERIC({t[2]},{t[3]})" if t[2] is not None else "NUMERIC"
    return t[0].upper()


def ustun_izohi(jadval, ustun):
    with database.engine.connect() as c:
        return c.execute(text("SELECT col_description(CAST(:t AS regclass), a.attnum) FROM pg_attribute a "
                              "WHERE a.attrelid = CAST(:t AS regclass) AND a.attname = :u"), {"t": jadval, "u": ustun}).scalar()


# ══════════════════════════════════════════════════════════════
section("A. `_sql_type_for_column` — yangi bazadagi (`create_all`) tur")
# ══════════════════════════════════════════════════════════════
_farq_a = []
_jami_a = 0
for _tn, _tab in sorted(database.Base.metadata.tables.items()):
    for _col in _tab.columns:
        try:
            _kut = _col.type.compile(dialect=database.engine.dialect)
        except Exception:                  # noqa: BLE001 — kompilyator bilmagan tur: solishtirilmaydi
            continue
        _jami_a += 1
        _bor = xav(lambda: database._sql_type_for_column(_col), "ISTISNO")
        if _bor != _kut:
            _farq_a.append(f"{_tn}.{_col.name}: {_bor} ≠ {_kut}")
check(f"A1 HAR model ustuni ({_jami_a} ta): `_sql_type_for_column` = dialekt kompilyatori turi (asl: Text → VARCHAR(255), "
      "Numeric → NUMERIC(12,2) …)", _jami_a > 600 and not _farq_a, f"{len(_farq_a)} ta: {_farq_a[:8]}")
_nv = ActivityLog.__table__.c.new_value
check("A2 `activity_logs.new_value` (Text) → «TEXT» (asl: «VARCHAR(255)» — production 12.10 11:47 xatosining ildizi)",
      xav(lambda: database._sql_type_for_column(_nv)) == "TEXT", xav(lambda: database._sql_type_for_column(_nv)))
_el = Murojaat.__table__.c.kelgan_sahifa
check("A3 `murojaatlar.kelgan_sahifa` String(200) → «VARCHAR(200)»", xav(lambda: database._sql_type_for_column(_el)) == "VARCHAR(200)",
      xav(lambda: database._sql_type_for_column(_el)))
_el4 = ActivityLog.__table__.c.entity_label
check("A4 `activity_logs.entity_label` (kech154, zip 202 — Text) → «TEXT»", xav(lambda: database._sql_type_for_column(_el4)) == "TEXT",
      xav(lambda: database._sql_type_for_column(_el4)))

# ══════════════════════════════════════════════════════════════
section("C. Ishga tushishda sxema kengaytirish (PG: production kabi toraytirilgan baza)")
# ══════════════════════════════════════════════════════════════
_holat = getattr(database, "SXEMA_ISHGA_TUSHISH", None) or {}
if PG_URL:
    _turlar = {(_t, _u): pg_tur_matn(ustun_turi(_t, _u)) for _t, _u, _, _ in TORAYTIRISH}
    _yomon = {k: v for k, v in _turlar.items() if v != dict(((t, u), kk) for t, u, _, kk in TORAYTIRISH)[k]}
    check("C1 12 ta toraytirilgan ustun ishga tushishda kengaytirildi (9 × VARCHAR(255) → TEXT, jurnal sarlavhasi VARCHAR(200) → "
          "TEXT, VARCHAR(60) → VARCHAR(200), NUMERIC(10,2) → NUMERIC(12,2)) — asl kod tegmaydi", not _yomon, _yomon)
    _q = ustun_turi(*QOLDA)
    with database.engine.connect() as _c:
        _nn = _c.execute(text("SELECT column_name, is_nullable FROM information_schema.columns WHERE table_schema = current_schema() "
                              "AND table_name = 'takliflar' AND column_name IN ('telefon', 'eski_ustun') ORDER BY 1")).fetchall()
    check("C2 «qo'lda» farqlar avtomatik o'zgartirilmadi (ENUM o'rnida VARCHAR(20); NOT NULL; kodda yo'q majburiy ustun)",
          _q and _q[0] == "character varying" and _q[1] == 20 and [tuple(x) for x in _nn] == [("eski_ustun", "NO"), ("telefon", "NO")],
          (_q, _nn))
    _izohlar = {(_t, _u): xav(lambda: ustun_izohi(_t, _u)) for _t, _u, _, _ in TORAYTIRISH}
    check("C3 har kengaytirilgan ustunga izoh: «sxema_kengaytirildi <vaqt>: VARCHAR(255) -> TEXT» (qayta ishga tushishdan keyin ham "
          "«Tizim salomatligi» da ko'rinadi)",
          all(isinstance(v, str) and v.startswith("sxema_kengaytirildi ") and "VARCHAR(255) -> TEXT" in v
              for (t, u), v in _izohlar.items()
              if (t, u) not in (("activity_logs", "entity_label"), ("murojaatlar", "kelgan_sahifa"), ("orders", "agreed_amount")))
          and "VARCHAR(200) -> TEXT" in (_izohlar.get(("activity_logs", "entity_label")) or "")
          and "VARCHAR(60) -> VARCHAR(200)" in (_izohlar.get(("murojaatlar", "kelgan_sahifa")) or "")
          and "NUMERIC(10,2) -> NUMERIC(12,2)" in (_izohlar.get(("orders", "agreed_amount")) or ""), _izohlar)
    check("C4 `SXEMA_ISHGA_TUSHISH`: 12 ta kengaytirildi, xato 0, qo'lda ≥ 1; server logida «Baza tuzilishi kengaytirildi»",
          len(_holat.get("kengaytirildi") or []) == 12 and not _holat.get("xatolar") and (_holat.get("qolda") or 0) >= 1
          and BOSH.count("Baza tuzilishi kengaytirildi") == 12, (_holat, BOSH.count("Baza tuzilishi kengaytirildi")))
    _f = xav(lambda: database.sxema_farqlari(), {}) or {}
    _ff = _f.get("farqlar") or []
    _ffm = {(x["jadval"], x["ustun"]): x for x in _ff}
    check("C5 `sxema_farqlari`: qolgan farqlar — faqat 3 ta «qo'lda» (ENUM ← VARCHAR(20); NOT NULL — kodda ixtiyoriy; kodda yo'q "
          "majburiy ustun), kengaytiriladigan 0; kengaytirilgan — 12 ta (oldin / keyin / vaqt)",
          sorted((x["jadval"], x["ustun"], x["tur"]) for x in _ff) == sorted([(*QOLDA, "qolda"), (*QOLDA_NN, "qolda"), (*QOLDA_ORTIQ, "qolda")])
          and _ffm.get(QOLDA, {}).get("bazada") == "VARCHAR(20)" and _ffm.get(QOLDA, {}).get("kodda") == "ENUM productionstatus"
          and _ffm.get(QOLDA_NN, {}).get("bazada") == "NOT NULL" and _ffm.get(QOLDA_ORTIQ, {}).get("kodda") == "yo'q"
          and len(_f.get("kengaytirilgan") or []) == 12
          and all(x.get("oldin") and x.get("keyin") and x.get("vaqt") for x in _f.get("kengaytirilgan") or []), _f)
    _n2 = xav(lambda: database.sxema_kengaytir(), {}) or {}
    check("C6 takror ishga tushish — hech narsa o'zgarmaydi (IDEMPOTENT)", _n2.get("kengaytirildi") == [] and not _n2.get("xatolar")
          and {(_t, _u): pg_tur_matn(ustun_turi(_t, _u)) for _t, _u, _, _ in TORAYTIRISH} == _turlar, _n2)
    # C7 — mavjud qiymatlar o'zgarmaydi: ustun qayta toraytiriladi, unga qiymat yoziladi, kengaytiriladi
    _qiymat = "C7 " + "x" * 220 + " — o'zbekcha ʻ belgilar"          # 255 dan qisqa (toraytirilgan ustunga sig'adi)
    _c7 = None
    try:
        with database.engine.begin() as _c:
            _c.execute(text("ALTER TABLE activity_logs ALTER COLUMN old_value TYPE VARCHAR(255)"))
            _c.execute(text("INSERT INTO activity_logs (company_id, action, entity_type, entity_id, old_value, created_at) "
                            "VALUES (1, 'c7', 'sinov', 7, :v, now())"), {"v": _qiymat})
        _n3 = database.sxema_kengaytir()
        with database.engine.connect() as _c:
            _c7 = (_c.execute(text("SELECT old_value FROM activity_logs WHERE action = 'c7'")).scalar(), _n3.get("kengaytirildi"))
    except Exception as _e:                # noqa: BLE001
        _c7 = f"{type(_e).__name__}: {_e}"
    check("C7 kengaytirishda mavjud qiymat AYNAN saqlanadi (VARCHAR(255) → TEXT)", isinstance(_c7, tuple) and _c7[0] == _qiymat
          and [(x["jadval"], x["ustun"]) for x in (_c7[1] or [])] == [("activity_logs", "old_value")]
          and pg_tur_matn(ustun_turi("activity_logs", "old_value")) == "TEXT", _c7)
    # C8 — yangi (koddan yaratilgan) bazada farq yo'q: solishtiruvchining o'zi ham to'g'ri
    _c8 = None
    try:
        from sqlalchemy import create_engine as _ce8
        _e8 = _ce8(f"{PG_URL}/{PG_YANGI}".replace("postgresql://", "postgresql+pg8000://", 1))
        database.Base.metadata.create_all(bind=_e8)
        with _e8.connect() as _c:
            _c8 = database.sxema_farqlari(_c)
        _e8.dispose()
    except Exception as _e:                # noqa: BLE001
        _c8 = f"{type(_e).__name__}: {_e}"
    check("C8 yangi bazada (`create_all`): 59 jadval, 700+ ustun — 0 farq, 0 kengaytirilgan", isinstance(_c8, dict)
          and _c8.get("farqlar") == [] and _c8.get("kengaytirilgan") == [] and (_c8.get("ustunlar") or 0) > 700
          and (_c8.get("jadvallar") or 0) >= 59, _c8 if not isinstance(_c8, dict) else
          {k: _c8.get(k) for k in ("jadvallar", "ustunlar")} | {"farqlar": (_c8.get("farqlar") or [])[:5]})
    # C9 — kengaytirish xatosi ilovani to'xtatmaydi (ustunga qaram VIEW — ALTER TYPE rad etiladi), sabab natijada
    _c9 = None
    try:
        with database.engine.begin() as _c:
            _c.execute(text("ALTER TABLE return_items ALTER COLUMN mrp_ozod TYPE VARCHAR(255)"))
            _c.execute(text("CREATE VIEW sxema_n4_korinish AS SELECT mrp_ozod FROM return_items"))
        _c9 = database.sxema_kengaytir()
        with database.engine.begin() as _c:
            _c.execute(text("DROP VIEW sxema_n4_korinish"))
        _c9b = database.sxema_kengaytir()
    except Exception as _e:                # noqa: BLE001
        _c9, _c9b = f"{type(_e).__name__}: {_e}", None
    check("C9 kengaytirib bo'lmasa (ustunga qaram ko'rinish) — xato natijada, istisno yo'q; to'siq olingach — kengayadi",
          isinstance(_c9, dict) and [(x["jadval"], x["ustun"]) for x in _c9.get("xatolar") or []] == [("return_items", "mrp_ozod")]
          and isinstance(_c9b, dict) and [(x["jadval"], x["ustun"]) for x in _c9b.get("kengaytirildi") or []]
          == [("return_items", "mrp_ozod")] and pg_tur_matn(ustun_turi("return_items", "mrp_ozod")) == "TEXT", (_c9, _c9b))
else:
    _f = xav(lambda: database.sxema_farqlari(), {}) or {}
    check("C0 SQLite: sxema tekshiruvi o'tkazilmaydi (uzunlik / tur cheklanmaydi) — `tekshirildi` False, sababi bilan; "
          "ishga tushish natijasi bo'sh", _f.get("tekshirildi") is False and "SQLite" in (_f.get("izoh") or "")
          and _holat.get("kengaytirildi") == [] and _holat.get("xatolar") == [], (_f, _holat))

# ══════════════════════════════════════════════════════════════
section("B. `sync_missing_columns` — eski bazada (ustunsiz) qo'shilgan ustun turi = yangi bazadagi")
# ══════════════════════════════════════════════════════════════
B_USTUNLAR = [("activity_logs", "old_value"), ("orders", "ochirish_yopish_json"), ("activity_logs", "entity_label"),
              ("orders", "agreed_amount"), ("finished_products", "production_status")]
_b = None
try:
    with database.engine.begin() as _c:
        for _t, _u in B_USTUNLAR:
            _c.execute(text(f"ALTER TABLE {_t} DROP COLUMN {_u}"))
        if PG_URL:      # ENUM turi ham yo'q (yangi Enum ustuni) — sync uni yaratishi kerak
            _c.execute(text("DROP TYPE IF EXISTS productionstatus"))
    with contextlib.redirect_stdout(io.StringIO()):
        database.sync_missing_columns()
    _b = {(_t, _u): ustun_turi(_t, _u) for _t, _u in B_USTUNLAR}
except Exception as _e:                    # noqa: BLE001
    _b = f"{type(_e).__name__}: {_e}"
if PG_URL:
    _kut_b = {("activity_logs", "old_value"): "TEXT", ("orders", "ochirish_yopish_json"): "TEXT",
              ("activity_logs", "entity_label"): "TEXT", ("orders", "agreed_amount"): "NUMERIC(12,2)"}
    check("B1 qo'shilgan Text → TEXT (jurnal sarlavhasi ham — kech154, zip 202), Numeric(12,2) → NUMERIC(12,2) (asl: Text → "
          "VARCHAR(255))",
          isinstance(_b, dict) and all(pg_tur_matn(_b.get(k)) == v for k, v in _kut_b.items()), _b)
    _ps = _b.get(("finished_products", "production_status")) if isinstance(_b, dict) else None
    check("B2 qo'shilgan ENUM — `productionstatus` turi (bazada yo'q edi — yaratildi), standarti «IN_PROGRESS» (asl: VARCHAR(11), "
          "standartsiz)",
          _ps and _ps[0] == "USER-DEFINED" and _ps[4] == "productionstatus" and "IN_PROGRESS" in str(_ps[5] or ""), _ps)
else:
    _kut_b = {}
    for _t, _u in B_USTUNLAR:
        _kut_b[(_t, _u)] = database.Base.metadata.tables[_t].c[_u].type.compile(dialect=database.engine.dialect).upper()
    check("B1 qo'shilgan ustunlar turi = `create_all` turi (TEXT, NUMERIC(12, 2), VARCHAR(11)) (asl: Text → VARCHAR(255))",
          isinstance(_b, dict) and all((_b.get(k) or ("?",))[0] == v for k, v in _kut_b.items()), (_b, _kut_b))
    _ps = _b.get(("finished_products", "production_status")) if isinstance(_b, dict) else None
    check("B2 qo'shilgan ENUM standarti — «'IN_PROGRESS'» (saqlanadigan qiymat; asl: standartsiz)", _ps and _ps[1] == "'IN_PROGRESS'", _ps)

# ══════════════════════════════════════════════════════════════
section("D. Buyurtma tahriri va o'chirish — uzun jurnal / «yopish» nusxasi saqlanadi")
# ══════════════════════════════════════════════════════════════
_pr = js(req(EGASI, "post", "/api/projects", json={"project_name": "SX Loyiha N4", "client_name": "Aziz Karimov"}))
PID = _pr.get("id") if isinstance(_pr, dict) else None
check("D0 loyiha yaratildi", bool(PID), _pr)
_n = [0]


def detal(nom, **k):
    d = {"name": nom, "category": "panel", "width": 50, "thickness": 10, "quantity": 2, "unit_price": 1000, "is_coated": False}
    d.update(k)
    return d


def buyurtma_tana(*detallar, **k):
    t = {"project_id": PID, "order_type": "product", "items": list(detallar)}
    t.update(k)
    return t


def buyurtmalar_soni():
    s = SessionLocal()
    try:
        return s.query(Order).filter(Order.project_id == PID).count()
    finally:
        s.close()


def jurnal(action, oid):
    s = SessionLocal()
    try:
        return [(x.performed_by, x.new_value) for x in s.query(ActivityLog).filter(
            ActivityLog.action == action, ActivityLog.entity_type == "order", ActivityLog.entity_id == oid).order_by(ActivityLog.id)]
    finally:
        s.close()


def xatolar_soni(qism):
    s = SessionLocal()
    try:
        return s.query(ErrorLog).filter(ErrorLog.error_message.like(f"%{qism}%")).count()
    finally:
        s.close()


_r = req(EGASI, "post", "/api/orders?confirm_shortage=true", json=buyurtma_tana(detal("SX D1 detal")))
OID = js(_r).get("id")
check("D1 buyurtma yaratildi", _r.status_code == 200 and OID, (_r.status_code, _r.text[:300]))
UZUN = [detal(f"SX D2 uzun nomli fasad paneli №{i} — karniz va ustun bezagi bilan, oq rangda, qoplamasiz", quantity=i + 1)
        for i in range(5)]
_r = req(EGASI, "put", f"/api/orders/{OID}?confirm_shortage=true", json=buyurtma_tana(*UZUN))
_jt = jurnal("updated", OID)
check("D2 tahrir: «O'zgardi: …» 255 belgidan uzun — 200, jurnalda TO'LIQ matn (asl PG production holatida: 500 — "
      "«value too long for type character varying(255)», tahrir saqlangan)",
      _r.status_code == 200 and len(_jt) == 1 and len(_jt[0][1] or "") > 255 and "O'zgardi" in (_jt[0][1] or ""),
      (_r.status_code, _r.text[:300], [(a, len(b or "")) for a, b in _jt]))
s = SessionLocal()
try:
    _d2 = sorted(i.name for i in s.get(Order, OID).items) if OID else []
finally:
    s.close()
check("D2b tahrir saqlangan (5 ta yangi detal)", len(_d2) == 5 and all(x.startswith("SX D2") for x in _d2), _d2)
# D3 — yuk xati bor buyurtmani o'chirish («yopish» nusxasi — barcha detallar JSON da, 255 dan uzun)
_r = req(EGASI, "post", "/api/orders?confirm_shortage=true", json=buyurtma_tana(*[detal(f"SX D3 detal {i} " + "y" * 40) for i in range(4)]))
OID3 = js(_r).get("id")
s = SessionLocal()
try:
    _iid = [i.id for i in s.get(Order, OID3).items] if OID3 else []
finally:
    s.close()
_ry = req(EGASI, "post", "/api/deliveries", json={"order_id": OID3, "items": [{"order_item_id": _iid[0], "quantity": 1}] if _iid else [],
                                                  "notes": "SX D3 yuk", "transport_cost": 0, "transport_payer": "none",
                                                  "payment_method": "naqd"})
_rd = req(EGASI, "delete", f"/api/orders/{OID3}")
s = SessionLocal()
try:
    _o3 = s.get(Order, OID3) if OID3 else None
    _d3 = (bool(_o3.is_deleted), len(_o3.ochirish_yopish_json or "")) if _o3 else None
finally:
    s.close()
check("D3 yuk xati bor buyurtmani o'chirish — 200, «yopish» nusxasi saqlandi (> 255 belgi; asl PG production holatida — 500, "
      "o'chmaydi)", _ry.status_code == 200 and _rd.status_code == 200 and _d3 and _d3[0] and _d3[1] > 255,
      (_ry.status_code, _rd.status_code, _rd.text[:300], _d3))
if PG_URL:
    # D4 — production holati AYNAN: kengaytirishdan KEYIN ustun qayta toraytiriladi (ishlayotgan serverda) — jurnal yozuvi bazaga
    # sig'maydi (22001); tahrir saqlanadi, javob 200, sabab «Xatoliklar» da (asl: 500, PendingRollbackError)
    try:
        with database.engine.begin() as _c:
            _c.execute(text("ALTER TABLE activity_logs ALTER COLUMN new_value TYPE VARCHAR(40) USING left(new_value, 40)"))
        _x0 = xatolar_soni("Faoliyat jurnaliga yozilmadi")
        _r = req(EGASI, "put", f"/api/orders/{OID}?confirm_shortage=true", json=buyurtma_tana(detal("SX D4 bitta detal")))
        s = SessionLocal()
        try:
            _d4 = sorted(i.name for i in s.get(Order, OID).items)
            _x = s.query(ErrorLog).filter(ErrorLog.error_message.like("%Faoliyat jurnaliga yozilmadi%")).order_by(ErrorLog.id.desc()).first()
            _x = (_x.error_message, _x.company_id, _x.endpoint) if _x else None
        finally:
            s.close()
        check("D4 production holati (new_value VARCHAR(40), 22001): tahrir — 200, saqlangan; sabab «Xatoliklar» da (korxona 1, "
              "«value too long»); asl: 500", _r.status_code == 200 and _d4 == ["SX D4 bitta detal"]
              and xatolar_soni("Faoliyat jurnaliga yozilmadi") == _x0 + 1 and _x and _x[1] == 1 and "too long" in _x[0]
              and len(jurnal("updated", OID)) == 1, (_r.status_code, _r.text[:300], _d4, _x))
    except Exception as _e:                # noqa: BLE001
        check("D4 production holati (new_value VARCHAR(40)) — sinov qadami", False, f"{type(_e).__name__}: {_e}")
    finally:
        with database.engine.begin() as _c:
            _c.execute(text("ALTER TABLE activity_logs ALTER COLUMN new_value TYPE TEXT"))

# ══════════════════════════════════════════════════════════════
section("E. Jurnal yozuvi yiqilsa (sun'iy xato) — amal saqlanadi, sessiya toza, sabab «Xatoliklar» da")
# ══════════════════════════════════════════════════════════════
BUZ = {"on": False}


@event.listens_for(ActivityLog, "before_insert")
def _jurnal_buz(mapper, connection, target):
    if BUZ["on"]:
        raise RuntimeError("N4 sinov: jurnal yozuvi yiqildi")


try:
    BUZ["on"] = True
    _x0 = xatolar_soni("N4 sinov: jurnal yozuvi yiqildi")
    _r = req(EGASI, "put", f"/api/orders/{OID}?confirm_shortage=true", json=buyurtma_tana(detal("SX E1 detal A"), detal("SX E1 detal B")))
    BUZ["on"] = False
    s = SessionLocal()
    try:
        _e1 = sorted(i.name for i in s.get(Order, OID).items)
    finally:
        s.close()
    check("E1 tahrir (amal o'zi saqlaydi, keyin jurnal): 200, tahrir saqlangan, «Xatoliklar» da sabab (asl: 500 — "
          "PendingRollbackError, tahrir saqlangan)", _r.status_code == 200 and _e1 == ["SX E1 detal A", "SX E1 detal B"]
          and xatolar_soni("N4 sinov: jurnal yozuvi yiqildi") == _x0 + 1, (_r.status_code, _r.text[:300], _e1))
    _r2 = req(EGASI, "get", f"/api/orders/{OID}")
    check("E1b keyingi so'rov — oddiy (sessiya / ulanish buzilmagan)", _r2.status_code == 200, _r2.status_code)
    BUZ["on"] = True
    _n0 = buyurtmalar_soni()
    _x0 = xatolar_soni("N4 sinov: jurnal yozuvi yiqildi")
    _tana = buyurtma_tana(detal("SX E2 detal"))
    _e2_idx = len(HOLATLAR)
    _r = req(EGASI, "post", "/api/orders?confirm_shortage=true", json=_tana)
    BUZ["on"] = False
    _n1 = buyurtmalar_soni()
    if PG_URL:
        check("E2 yaratish (bitta tranzaksiya ichida, SAVEPOINT): 200, BITTA buyurtma, «Xatoliklar» da sabab (asl: 500, saqlanmaydi)",
              _r.status_code == 200 and _n1 == _n0 + 1 and xatolar_soni("N4 sinov: jurnal yozuvi yiqildi") == _x0 + 1,
              (_r.status_code, _r.text[:300], _n0, _n1))
    else:
        check("E2 yaratish (SQLite — savepoint yo'q): butun amal bekor (500 / 4xx, buyurtma 0) yoki saqlangan (200, 1) — YARIM yo'q",
              (_r.status_code == 200 and _n1 == _n0 + 1) or (_r.status_code >= 400 and _n1 == _n0), (_r.status_code, _n0, _n1))
        KUTILGAN_IDX.add(_e2_idx)          # SQLite: savepoint siz — butun amal bekor, 500 kutilgan bo'lishi mumkin
    _r3 = req(EGASI, "post", "/api/orders?confirm_shortage=true", json=_tana)
    check("E3 foydalanuvchi qayta bosdi — jami BITTA buyurtma (takror yo'q)", _r3.status_code == 200 and buyurtmalar_soni() == _n0 + 1,
          (_r3.status_code, buyurtmalar_soni(), _n0))
    # E4 — to'g'ridan-to'g'ri: `log_activity(commit=True)` — chaqiruvchining o'zgarishi saqlanadi, sessiya ishlaydi
    s = SessionLocal()
    _e4 = None
    try:
        _o = s.get(Order, OID)
        _o.notes = "SX E4 izoh"
        BUZ["on"] = True
        crud.log_activity(s, "updated", "order", OID, "E4", "sinov", new_value="E4", company_id=1)
        BUZ["on"] = False
        _e4 = (s.get(Order, OID).notes, s.query(Order).filter(Order.id == OID).count())
    except Exception as _e:                # noqa: BLE001
        _e4 = f"{type(_e).__name__}: {_e}"
    finally:
        BUZ["on"] = False
        s.close()
    s = SessionLocal()
    try:
        _e4b = s.get(Order, OID).notes
    finally:
        s.close()
    check("E4 `log_activity(commit=True)` jurnali yiqilsa: istisno yo'q, chaqiruvchining o'zgarishi SAQLANGAN, sessiya ishlaydi "
          "(asl: istisno — sessiya buzuq)", _e4 == ("SX E4 izoh", 1) and _e4b == "SX E4 izoh", (_e4, _e4b))
    # E5 — `commit=False` (retsept / MRP): jurnal amal bilan BITTA tranzaksiyada — yiqilsa ikkalasi ham saqlanmaydi (o'zgarmagan)
    s = SessionLocal()
    try:
        _e5_oldin = s.get(Order, OID).notes
    finally:
        s.close()
    s = SessionLocal()
    _e5 = None
    try:
        s.get(Order, OID).notes = "SX E5 izoh"
        crud.log_activity(s, "updated", "order", OID, "E5", "sinov", new_value="E5", company_id=1, commit=False)
        BUZ["on"] = True
        try:
            s.commit()
            _e5 = "commit o'tdi"
        except Exception:                  # noqa: BLE001
            s.rollback()
            _e5 = "rad"
    finally:
        BUZ["on"] = False
        s.close()
    s = SessionLocal()
    try:
        _e5b = s.get(Order, OID).notes
    finally:
        s.close()
    check("E5 `commit=False` — avvalgidek: jurnal yiqilsa amal ham saqlanmaydi (bitta tranzaksiya)", _e5 == "rad" and _e5b == _e5_oldin
          and _e5b != "SX E5 izoh", (_e5, _e5b, _e5_oldin))
finally:
    BUZ["on"] = False
    event.remove(ActivityLog, "before_insert", _jurnal_buz)

# ══════════════════════════════════════════════════════════════
section("F. «Tizim salomatligi» — baza tuzilishi bloki")
# ══════════════════════════════════════════════════════════════
_h = js(req(EGASI, "get", "/api/system/health-check"))
_sx = _h.get("sxema") if isinstance(_h, dict) else None
if PG_URL:
    # B bo'limi 5 ta ustunni o'chirib qayta qo'shdi: ularning izohi yo'q (yangi ustun), ENUM esa endi to'g'ri — farq 0
    _kut_f = sorted((t, u) for t, u, _, _ in TORAYTIRISH if (t, u) not in B_USTUNLAR)
    check("F1 platforma egasi: `sxema` — tekshirildi, 59+ jadval; farq — 2 ta «qo'lda» (B ENUM ni to'g'riladi); kengaytirilgan — "
          f"izohli ustunlar ({len(_kut_f)} ta, oldin / keyin / vaqt bilan); ishga tushish xatolari 0",
          isinstance(_sx, dict) and _sx.get("tekshirildi") is True and (_sx.get("jadvallar") or 0) >= 59
          and sorted((x["jadval"], x["ustun"], x["tur"]) for x in _sx.get("farqlar") or [])
          == sorted([(*QOLDA_NN, "qolda"), (*QOLDA_ORTIQ, "qolda")]) and sorted((x["jadval"], x["ustun"]) for x in _sx.get("kengaytirilgan") or []) == _kut_f
          and all(x.get("oldin") and x.get("keyin") and x.get("vaqt") for x in _sx.get("kengaytirilgan") or [])
          and (_sx.get("ishga_tushish") or {}).get("xatolar") == [], _sx)
else:
    check("F1 platforma egasi (SQLite): `sxema` — tekshirilmadi, sababi bilan", isinstance(_sx, dict) and _sx.get("tekshirildi") is False
          and "SQLite" in (_sx.get("izoh") or ""), _sx)
check("F2 moliyaviy va texnik qismlar avvalgidek (financial, issues_found)", isinstance(_h, dict) and "financial" in _h
      and "issues_found" in _h, list(_h)[:12] if isinstance(_h, dict) else _h)
_ha = js(req(ADM, "get", "/api/system/health-check"))
check("F3 oddiy korxona admini — `sxema` YO'Q (jadval / ustun nomlari — faqat platforma egasiga)", isinstance(_ha, dict)
      and "sxema" not in _ha and _ha.get("technical_hidden") is True, list(_ha)[:12] if isinstance(_ha, dict) else _ha)

# ══════════════════════════════════════════════════════════════
section("G. «Kim» — buyurtma jurnalida foydalanuvchi")
# ══════════════════════════════════════════════════════════════
_r = req(EGASI, "post", "/api/orders?confirm_shortage=true", json=buyurtma_tana(detal("SX G1 detal")))
OIDG = js(_r).get("id")
check("G1 yaratish jurnali — «SX_EGASI» (asl: bo'sh)", [a for a, _ in jurnal("created", OIDG)] == ["SX_EGASI"], jurnal("created", OIDG))
_r = req(EGASI, "put", f"/api/orders/{OIDG}?confirm_shortage=true", json=buyurtma_tana(detal("SX G2 detal")))
check("G2 tahrir jurnali — «SX_EGASI» (asl: bo'sh — production 153 … 198)", _r.status_code == 200
      and [a for a, _ in jurnal("updated", OIDG)] == ["SX_EGASI"], (_r.status_code, jurnal("updated", OIDG)))
_r = req(EGASI, "post", "/api/orders?confirm_shortage=true", json=buyurtma_tana(detal("SX G3 qoralama"), is_draft=True))
OIDQ = js(_r).get("id")
_r = req(EGASI, "post", f"/api/orders/{OIDQ}/activate")
check("G3 qoralamani faollashtirish jurnali — «SX_EGASI» (asl: bo'sh)", _r.status_code == 200
      and [a for a, _ in jurnal("activated", OIDQ)] == ["SX_EGASI"], (_r.status_code, jurnal("activated", OIDQ)))

# ══════════════════════════════════════════════════════════════
section("X. 5xx yo'q")
# ══════════════════════════════════════════════════════════════
_xato5 = [h for i, h in enumerate(HOLATLAR) if h[1] >= 500 and i not in KUTILGAN_IDX]
check("X1 kutilmagan 5xx yo'q", not _xato5, _xato5[:8])

print(f"\nNATIJA: o'tdi = {OK}, yiqildi = {FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
