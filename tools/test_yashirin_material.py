#!/usr/bin/env python3
"""
test_yashirin_material.py — K34-1 darvozasi (kech34, 2026-09-22).

NIMA UCHUN KERAK (jonli `web-sinov` da O'LCHANGAN)
--------------------------------------------------
Tarixi bor materialni o'chirganda (`crud.delete_item`) u bazadan butunlay
o'chmaydi — `is_deleted = True` bo'lib Omborxona ro'yxatidan YASHIRILADI.
Jonli o'lchov: narx va qoldiq bilan yaratilgan material (boshlang'ich
qoldiq xaridi → FK) o'chirildi, `soft: true` qaytdi, `/api/inventory` da
yo'q — lekin BOSH SAHIFA "Kam qolgan xomashyo" blokida ko'rinishda davom
etdi. Kod o'qilganda xuddi shu nuqson quyidagilarda topildi:

  * `services.check_low_stock` — `/api/dashboard/stats` (bosh sahifa,
    dashboard), `/api/warnings/low-stock` (buyurtmalar sahifasi),
    `/api/dashboard/today-tasks`, `/api/dashboard/charts`;
  * `services.get_dashboard_stats` — `total_inventory_items` yashirinlarni
    ham sanardi;
  * `crud.get_low_stock_items` — Telegram: qo'lda ogohlantirish
    (`/api/inventory/low-stock-alert`), kunlik cron, buyurtma va ishlab
    chiqarishdan keyingi ogohlantirish;
  * `main.api_full_stock_report` — Telegram "Ombor hisoboti" va uning
    "(N ta xomashyo)" soni.

`get_business_alerts`, `get_notifications`, `get_inventory_kpi` allaqachon
`is_deleted.isnot(True)` bilan to'g'ri edi — endi hammasi bir xil.
`isnot(True)`: eski (NULL) qatorlar ko'rinadigan bo'lib qoladi — sinaladi.

Qo'shimcha (statik): `services.py` va `main.py` da `return` dan keyin
qolib ketgan (erishib bo'lmaydigan) yetim kod bloklari bor edi — AST
tekshiruvi yangilari paydo bo'lishini ushlaydi.

REJIMLAR
--------
* Odatiy (SQLite, `hammasi.sh`): SQLite tashqi kalitlarni tekshirmaydi,
  shuning uchun "xarid → o'chirish → soft" yo'li u yerda yuz bermaydi —
  yashirin qatorlar `is_deleted` ni to'g'ridan yozib yaratiladi.
* `PG_URL` berilsa (masalan `PG_URL=postgresql://postgres@127.0.0.1:5432`):
  har ishga YANGI PostgreSQL bazasi, va birinchi yashirin material HAQIQIY
  yo'l bilan yaratiladi (narx + qoldiq → boshlang'ich xarid → DELETE →
  `soft: true`), qo'shimcha tekshiruv bilan.

ISHGA TUSHIRISH
---------------
    python3 tools/test_yashirin_material.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_yashirin_material.py
"""
import os
import sys
import ast
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "yashirin_material_test"
_DB = os.path.join(tempfile.gettempdir(), "yashirin_material_test.db")

if PG_URL:
    # Har ishga YANGI PostgreSQL bazasi (izolyatsiya qoidasi).
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
               isolation_level="AUTOCOMMIT")
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
    import crud, auth, services                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory             # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {detail}")


def section(t):
    print(f"\n--- {t} ---")


def safe(fn, *a, **k):
    """Chaqiruv xato bersa — ("XATO", matn): tekshiruv yiqiladi, skript to'xtamaydi."""
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {e}")


class _Xato:
    """HTTP chaqiruvi istisno bersa — 599 (skript qulamaydi)."""
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


# ------------------------------------------------------------------ Telegram
# Xabar tarmoqqa chiqmaydi — `main._send_telegram` yozib oluvchi bilan almashtiriladi
# (marshrutlar uni modul global nomi orqali chaqiradi).
TG = []


def _yozib_ol(text, company_id=None, *a, **k):
    TG.append((company_id, str(text)))


main._send_telegram = _yozib_ol


# ------------------------------------------------------------------ foydalanuvchi
db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "HM_admin", "Parol123!", UserRole.ADMIN, "HM", company_id=1)

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "HM_admin", "password": "Parol123!"},
          follow_redirects=False)
if _lr.status_code != 302:
    print(f"LOGIN BO'LMADI: {_lr.status_code} {getattr(_lr, 'text', '')[:200]}")
    print(f"NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

V1 = "HM_KORINADI_KAM"        # ko'rinadigan, kam qolgan — HAMMA joyda chiqishi SHART
N1 = "HM_NULL_ESKI_KAM"       # is_deleted = NULL (eski qator) — ko'rinadigan
OKQ = "HM_YETARLI"            # ko'rinadigan, qoldiq yetarli
H1 = "HM_YASHIRIN_SOFT"       # o'chirilgan (PG: haqiqiy soft yo'l)
H2 = "HM_YASHIRIN_BAYROQ"     # is_deleted = True (to'g'ridan)
YASHIRINLAR = (H1, H2)


def _stats():
    return js(req(C, "get", "/api/dashboard/stats")) or {}


section("0. Boshlang'ich holat (fikstura oldidan)")
_s0 = _stats()
B_TOTAL = _s0.get("total_inventory_items")
B_LOW = _s0.get("low_stock_count")
check("boshlang'ich /api/dashboard/stats o'qildi", isinstance(B_TOTAL, int) and isinstance(B_LOW, int),
      str(_s0)[:200])
B_TOTAL = B_TOTAL if isinstance(B_TOTAL, int) else 0
B_LOW = B_LOW if isinstance(B_LOW, int) else 0


def yarat(nom, qoldiq, minimal, narx=None):
    tana = {"item_name": nom, "unit": "kg", "stock_quantity": qoldiq, "min_stock": minimal}
    if narx is not None:
        tana["price_per_unit"] = narx
    r = req(C, "post", "/api/inventory", json=tana)
    d = js(r) or {}
    return r.status_code, d.get("id")


def bayroq(inv_id, qiymat):
    s = SessionLocal()
    try:
        s.query(Inventory).filter(Inventory.id == inv_id).update(
            {"is_deleted": qiymat}, synchronize_session=False)
        s.commit()
    finally:
        s.close()


section("1. Fikstura")
IDS = {}
for _nom, _q, _m in ((V1, 1, 5), (N1, 1, 4), (OKQ, 50, 5), (H2, 0, 3)):
    _st, IDS[_nom] = yarat(_nom, _q, _m)
    check(f"material yaratildi: {_nom}", _st == 200 and IDS[_nom], f"status {_st}")

# H1: narx + qoldiq → boshlang'ich qoldiq xaridi (FK) → DELETE → soft (PG da)
_st, IDS[H1] = yarat(H1, 2, 10, narx=1000)
check(f"material yaratildi: {H1} (narx bilan — boshlang'ich xarid)", _st == 200 and IDS[H1], f"status {_st}")
_dr = req(C, "delete", f"/api/inventory/{IDS[H1]}")
_dd = js(_dr) or {}
if PG_URL:
    check("[PG] H1 o'chirildi → 200, soft: true (xarid FK tufayli yashirildi — jonli holat)",
          _dr.status_code == 200 and _dd.get("soft") is True, f"{_dr.status_code} {str(_dd)[:160]}")
else:
    # SQLite FK ni tekshirmaydi — butunlay o'chgan bo'lishi mumkin: qatorni qayta
    # tiklab bo'lmaydi, shuning uchun yangisini yaratib bayroq qo'yamiz.
    if _dd.get("soft") is not True:
        _st, IDS[H1] = yarat(H1, 2, 10)
        check(f"[SQLite] {H1} qayta yaratildi (FK yo'q — soft yo'li yuz bermaydi)",
              _st == 200 and IDS[H1], f"status {_st}")
        bayroq(IDS[H1], True)
    else:
        check("[SQLite] H1 soft bo'ldi", True)

bayroq(IDS[H2], True)
bayroq(IDS[N1], None)

_s = SessionLocal()
try:
    _hol = {n: _s.query(Inventory.is_deleted).filter(Inventory.id == IDS[n]).scalar()
            for n in (V1, N1, OKQ, H1, H2) if IDS.get(n)}
finally:
    _s.close()
check("bayroqlar: H1, H2 = True; N1 = NULL; V1, OKQ = False",
      _hol.get(H1) is True and _hol.get(H2) is True and _hol.get(N1) is None
      and _hol.get(V1) is False and _hol.get(OKQ) is False, str(_hol))

_inv = js(req(C, "get", "/api/inventory")) or []
_inv_n = {x.get("item_name") for x in _inv if isinstance(x, dict)}
check("/api/inventory: V1, N1, OKQ BOR; H1, H2 YO'Q (mavjud qoida — Omborxona ro'yxati)",
      {V1, N1, OKQ} <= _inv_n and not (set(YASHIRINLAR) & _inv_n), str(sorted(_inv_n))[:200])


def yashirin_yoq(matnlar):
    m = " | ".join(str(x) for x in matnlar)
    return not any(h in m for h in YASHIRINLAR), m[:220]


section("2. /api/dashboard/stats (bosh sahifa `/` va dashboard)")
_s1 = _stats()
_items = _s1.get("low_stock_items") or []
_nomlar = [x.get("item_name") for x in _items if isinstance(x, dict)]
_ok, _m = yashirin_yoq(_nomlar)
check("low_stock_items da yashirin material YO'Q", _ok, _m)
check("low_stock_items da V1 va N1 (NULL — eski qator) BOR", V1 in _nomlar and N1 in _nomlar, _m)
check("low_stock_items da qoldig'i yetarli OKQ YO'Q", OKQ not in _nomlar, _m)
check("low_stock_count == boshlang'ich + 2 (V1, N1) va == len(low_stock_items)",
      _s1.get("low_stock_count") == B_LOW + 2 and _s1.get("low_stock_count") == len(_items),
      f"{_s1.get('low_stock_count')} (boshlang'ich {B_LOW}), len {len(_items)}")
check("total_inventory_items == boshlang'ich + 3 (V1, N1, OKQ) — yashirinlar sanalmaydi",
      _s1.get("total_inventory_items") == B_TOTAL + 3,
      f"{_s1.get('total_inventory_items')} (boshlang'ich {B_TOTAL})")

section("3. /api/warnings/low-stock (buyurtmalar sahifasi)")
_w = (js(req(C, "get", "/api/warnings/low-stock")) or {}).get("warnings") or []
_wn = [x.get("item_name") for x in _w if isinstance(x, dict)]
_ok, _m = yashirin_yoq(_wn)
check("warnings da yashirin material YO'Q", _ok, _m)
check("warnings da V1 BOR", V1 in _wn, _m)

section("4. /api/dashboard/today-tasks (Bugungi vazifalar)")
_t = js(req(C, "get", "/api/dashboard/today-tasks")) or []
_tt = [x.get("text", "") for x in _t if isinstance(x, dict)]
_ok, _m = yashirin_yoq(_tt)
check("today-tasks da yashirin material YO'Q", _ok, _m)
check("today-tasks da V1 BOR", any(V1 in x for x in _tt), _m)

section("5. /api/dashboard/charts (omborxona holati)")
_c = (js(req(C, "get", "/api/dashboard/charts")) or {}).get("low_stock") or []
_cn = [x.get("item_name") for x in _c if isinstance(x, dict)]
_ok, _m = yashirin_yoq(_cn)
check("charts.low_stock da yashirin material YO'Q", _ok, _m)
check("charts.low_stock da V1 BOR", V1 in _cn, _m)

section("6. crud.get_low_stock_items (Telegram ogohlantirishlari manbai)")
_d = SessionLocal()
_gl = safe(crud.get_low_stock_items, _d, company_id=1)
_gn = [getattr(x, "item_name", None) for x in _gl] if isinstance(_gl, list) else []
_d.close()
_ok, _m = yashirin_yoq(_gn if _gn else [_gl])
check("get_low_stock_items da yashirin material YO'Q", isinstance(_gl, list) and _ok, _m)
check("get_low_stock_items da V1 va N1 BOR", V1 in _gn and N1 in _gn, _m)

section("7. services.get_business_alerts (allaqachon to'g'ri — himoya)")
_d = SessionLocal()
_ba = safe(services.get_business_alerts, _d, company_id=1)
_d.close()
_ok, _m = yashirin_yoq(_ba if isinstance(_ba, list) else [_ba])
check("business_alerts da yashirin material YO'Q", isinstance(_ba, list) and _ok, _m)

section("8. Telegram xabarlari")
TG.clear()
_r = req(C, "post", "/api/inventory/low-stock-alert")
_rj = js(_r) or {}
_msg = " ".join(t for _, t in TG)
check("low-stock-alert → 200, sent: true", _r.status_code == 200 and _rj.get("sent") is True,
      f"{_r.status_code} {str(_rj)[:120]}")
check("low-stock-alert xabarida yashirin material YO'Q", bool(TG) and yashirin_yoq([_msg])[0], _msg[:220])
check("low-stock-alert xabarida V1 BOR", V1 in _msg, _msg[:220])

TG.clear()
_r = req(C, "post", "/api/inventory/full-stock-report")
_rj = js(_r) or {}
_msg = " ".join(t for _, t in TG)
_s = SessionLocal()
try:
    _kutilgan = _s.query(Inventory).filter(Inventory.company_id == 1,
                                           Inventory.is_deleted.isnot(True)).count()
finally:
    _s.close()
check("full-stock-report → 200", _r.status_code == 200, f"{_r.status_code} {str(_rj)[:120]}")
check("full-stock-report xabarida yashirin material YO'Q", bool(TG) and yashirin_yoq([_msg])[0], _msg[:220])
check("full-stock-report xabarida V1 va OKQ BOR", V1 in _msg and OKQ in _msg, _msg[:220])
check(f"full-stock-report javobi '({_kutilgan} ta xomashyo)' — yashirinlar sanalmaydi",
      f"({_kutilgan} ta xomashyo)" in str(_rj.get("message", "")), str(_rj)[:160])

TG.clear()
main.CRON_SECRET = "K34_SIR"
_cr = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r = req(_cr, "get", "/api/cron/low-stock-check", params={"secret": "K34_SIR"})
_rj = js(_r) or {}
_msg = " ".join(t for cid, t in TG if cid == 1)
check("cron low-stock-check → 200, sent: true", _r.status_code == 200 and _rj.get("sent") is True,
      f"{_r.status_code} {str(_rj)[:120]}")
check("cron xabarida yashirin material YO'Q", bool(_msg) and yashirin_yoq([_msg])[0], _msg[:220])
check("cron xabarida V1 BOR", V1 in _msg, _msg[:220])

section("9. Statik: erishib bo'lmaydigan (return / raise dan keyingi) kod yo'q")


def erishilmas(yol):
    """Har blokda `return` / `raise` / `continue` / `break` dan KEYIN kelgan
    bayonotlar — (qator, tur) ro'yxati. Tahlil qila olmasa — ("XATO", ...)."""
    try:
        daraxt = ast.parse(open(os.path.join(ROOT, yol), encoding="utf-8").read())
    except Exception as e:                 # noqa: BLE001
        return [("XATO", f"{type(e).__name__}: {e}")]
    topildi = []
    for node in ast.walk(daraxt):
        for attr in ("body", "orelse", "finalbody"):
            blok = getattr(node, attr, None)
            if not isinstance(blok, list):
                continue
            for i, st in enumerate(blok[:-1]):
                if isinstance(st, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                    topildi.append((blok[i + 1].lineno, type(st).__name__))
                    break
    return topildi


for _f in ("main.py", "crud.py", "services.py", "production_service.py", "production_routes.py"):
    if not os.path.exists(os.path.join(ROOT, _f)):
        check(f"{_f} mavjud", False, "fayl yo'q")
        continue
    _e = erishilmas(_f)
    check(f"{_f}: erishib bo'lmaydigan kod bloki yo'q", _e == [], str(_e)[:200])

print("\n" + "=" * 66)
print(f"REJIM: {'PostgreSQL' if PG_URL else 'SQLite'}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
db.close()
sys.exit(1 if FAIL else 0)
