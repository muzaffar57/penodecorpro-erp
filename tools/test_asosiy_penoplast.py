#!/usr/bin/env python3
"""
test_asosiy_penoplast.py — 18-band (K37-1) darvozasi (kech37, 2026-09-23).

NIMA UCHUN KERAK (asl kodda O'LCHANGAN — SQLite va HAQIQIY PostgreSQL 16)
-----------------------------------------------------------------------
* `DELETE /api/inventory/{id}` ASOSIY penoplastni ham bemalol o'chirardi (200).
  Keyin korxonada "★ Asosiy" belgili ko'rinadigan penoplast qolmasdi;
  `/api/penoplasts` `default_id` esa qolgan penoplastlardan tartibsiz
  `.first()` bilan tanlanardi.
* PG da (tarixi bor material YASHIRILADI) yashirin qator
  `is_default_penoplast = True` ni saqlab qolardi → keyin yaratilgan penoplast
  ham asosiy bo'lmasdi (`crud.add_item` `has_default` yashirinni ham sanardi).
  SQLite da esa (tashqi kalitlar tekshirilmaydi — butunlay o'chadi) asosiy
  bo'lardi: ikki bazada xulq FARQ qilardi.

Tuzatish (kech37):
  * `crud.delete_item`: asosiy penoplastni boshqa ko'rinadigan penoplast bor
    bo'lsa o'chirish — `ValueError` → marshrut 400 ("avval boshqa penoplastni
    asosiy qiling" — `update_item` qoidasi bilan bir xil). Yagona penoplast
    o'chiriladi / yashiriladi va yashirin qatorning asosiy belgisi olinadi.
  * `crud.add_item`: `has_default` va qayta tiklash yo'lidagi `_bor` —
    yashirin qatorlar hisobga olinmaydi (eski ma'lumot uchun ham).
  * `services.get_default_penoplast`: zaxira tanlovi `order_by(Inventory.id)`.

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_asosiy_penoplast.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_asosiy_penoplast.py
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "asosiy_penoplast_test"
_DB = os.path.join(tempfile.gettempdir(), "asosiy_penoplast_test.db")

if PG_URL:
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
    import auth, services                          # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory             # noqa: E402
from sqlalchemy import text                        # noqa: E402
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
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "AP_admin", "Parol123!", UserRole.ADMIN, "AP", company_id=1)
db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "AP_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print(f"LOGIN BO'LMADI: {_lr.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)


def peno(nom, narx=None):
    b = {"item_name": nom, "unit": "blok", "stock_quantity": 5, "min_stock": 0,
         "is_penoplast": True, "volume_per_unit": 1}
    if narx:
        b["price_per_unit"] = narx       # boshlang'ich xarid → PG da o'chirish YASHIRADI (tarix)
    r = req(C, "post", "/api/inventory", json=b)
    return r.status_code, (js(r) or {}).get("id")


def pp():
    d = js(req(C, "get", "/api/penoplasts")) or {}
    return d.get("default_id"), {i.get("id"): bool(i.get("is_default")) for i in d.get("items", [])}


def qator(i):
    s = SessionLocal()
    try:
        x = s.query(Inventory).filter(Inventory.id == i).first()
        return None if x is None else (bool(x.is_deleted), bool(x.is_default_penoplast))
    finally:
        s.close()


def yoz(i, **maydon):
    s = SessionLocal()
    try:
        s.query(Inventory).filter(Inventory.id == i).update(maydon, synchronize_session=False)
        s.commit()
    finally:
        s.close()


section("1. Fikstura: ikki penoplast (birinchisi avtomatik asosiy)")
_s1, P1 = peno("PENO_A 14P", 1000)
_s2, P2 = peno("PENO_B 10P", 2000)
check("P1, P2 yaratildi (200)", _s1 == 200 and _s2 == 200 and bool(P1) and bool(P2), f"{_s1} {_s2}")
# Oddiy (penoplast EMAS) material — "boshqa penoplast bormi" tekshiruvi uni sanamasligi SHART (4-bo'lim)
_ro = req(C, "post", "/api/inventory", json={"item_name": "AP_ODDIY_MATERIAL", "unit": "kg", "stock_quantity": 3,
                                              "min_stock": 0})
check("oddiy material (penoplast emas) yaratildi", _ro.status_code == 200, f"{_ro.status_code}")
_d, _it = pp()
check("P1 asosiy (default_id == P1, is_default), P2 emas", _d == P1 and _it.get(P1) and not _it.get(P2), f"{_d} {_it}")

section("2. Asosiy penoplastni o'chirish — boshqa penoplast bor → 400, hech narsa o'zgarmaydi")
_r = req(C, "delete", f"/api/inventory/{P1}")
check("DELETE P1 (asosiy) → 400", _r.status_code == 400, f"{_r.status_code} {getattr(_r, 'text', '')[:160]}")
check("xabar: \"avval boshqa penoplastni asosiy qiling\"",
      "avval boshqa penoplastni asosiy qiling" in str((js(_r) or {}).get("detail", "")), getattr(_r, "text", "")[:200])
check("P1 bazada o'zgarmagan: ko'rinadi va asosiy", qator(P1) == (False, True), str(qator(P1)))
_d, _it = pp()
check("/api/penoplasts: default_id == P1, P1 ro'yxatda", _d == P1 and P1 in _it, f"{_d} {_it}")

section("3. Avval P2 asosiy qilinadi — keyin P1 (endi oddiy) o'chiriladi")
_r = req(C, "post", f"/api/inventory/{P2}/set-default-penoplast")
check("set-default P2 → 200", _r.status_code == 200, f"{_r.status_code}")
_r = req(C, "delete", f"/api/inventory/{P1}")
check("DELETE P1 (oddiy penoplast) → 200", _r.status_code == 200, f"{_r.status_code} {getattr(_r, 'text', '')[:160]}")
_d, _it = pp()
check("default_id == P2, P2 is_default, P1 ro'yxatda YO'Q", _d == P2 and _it.get(P2) and P1 not in _it, f"{_d} {_it}")

section("4. YAGONA penoplast (asosiy) o'chiriladi — ruxsat; yashirin qator asosiy bo'lib QOLMAYDI")
_r = req(C, "delete", f"/api/inventory/{P2}")
_rj = js(_r) or {}
check("DELETE P2 (yagona, asosiy) → 200", _r.status_code == 200, f"{_r.status_code} {getattr(_r, 'text', '')[:160]}")
_q2 = qator(P2)
if PG_URL:
    check("PG: tarixi bor → YASHIRILDI (soft), asosiy belgisi OLINDI", _rj.get("soft") is True and _q2 == (True, False),
          f"soft {_rj.get('soft')}, qator {_q2}")
else:
    check("SQLite: butunlay o'chdi yoki yashirin qator asosiy emas", _q2 is None or _q2 == (True, False), str(_q2))
_d, _it = pp()
check("/api/penoplasts: bo'sh, default_id None", _d is None and not _it, f"{_d} {_it}")

section("5. Keyin yaratilgan penoplast ASOSIY bo'ladi (ikki bazada bir xil)")
_s3, P3 = peno("PENO_C 16P")
_d, _it = pp()
check("P3 yaratildi va asosiy (default_id == P3, is_default)", _s3 == 200 and _d == P3 and _it.get(P3), f"{_s3} {_d} {_it}")

section("6. ESKI ma'lumot: yashirin qatorda qolgan asosiy belgi yangi penoplastga to'sqinlik qilmaydi")
_s4, P4 = peno("PENO_D 12P")
yoz(P3, is_deleted=True)                     # tuzatishdan OLDINGI holat: yashirin + asosiy belgi
check("holat: P3 yashirin + asosiy belgili (eski), P4 ko'rinadi, oddiy", qator(P3) == (True, True)
      and qator(P4) == (False, False), f"{qator(P3)} {qator(P4)}")
_s5, P5 = peno("PENO_E 18P")
check("yangi P5 → asosiy (`has_default` yashirinni sanamaydi)", _s5 == 200 and qator(P5) == (False, True), str(qator(P5)))
_d, _it = pp()
check("/api/penoplasts default_id == P5", _d == P5 and _it.get(P5), f"{_d} {_it}")

section("7. Qayta tiklash yo'li (yashirin nom qayta yaratiladi) — yashirin eski asosiy hisobga olinmaydi")
_s6, P6 = peno("PENO_F 20P")
yoz(P5, is_deleted=True)                     # P5: yashirin + asosiy belgi (eski holat)
yoz(P6, is_deleted=True)                     # P6: yashirin, oddiy — shu nom qayta yaratiladi
_s6b, P6b = peno("PENO_F 20P")
check("PENO_F qayta yaratildi — O'SHA qator tiklandi (id == P6)", _s6b == 200 and P6b == P6, f"{_s6b} {P6b} vs {P6}")
check("tiklangan P6 → asosiy (ko'rinadigan asosiy yo'q edi)", qator(P6) == (False, True), str(qator(P6)))

section("8. Zaxira tanlovi (ko'rinadigan asosiy yo'q) — eng kichik id, BARQAROR")
for _i in (P3, P5):
    yoz(_i, is_default_penoplast=False)
yoz(P6, is_default_penoplast=False)          # ko'rinadiganlar: P4 (kichik id), P6 — ikkalasi oddiy
_eng = min(P4, P6)
yoz(_eng, stock_quantity=7)                  # UPDATE — PG da yangi qator nusxasi sahifa oxiriga tushadi
if PG_URL:
    _s = SessionLocal()
    try:
        _s.execute(text("ANALYZE inventory"))
        _s.commit()
        _xom = _s.query(Inventory).filter(Inventory.company_id == 1, Inventory.is_penoplast == True,
                                          Inventory.is_deleted.isnot(True)).first()
    finally:
        _s.close()
    check("PG sezgirlik isboti: tartibsiz `.first()` shu fiksturada eng kichik id ni QAYTARMAYDI",
          _xom is not None and _xom.id != _eng, f"{getattr(_xom, 'id', None)} vs {_eng}")
_s = SessionLocal()
try:
    _t = [getattr(services.get_default_penoplast(_s, company_id=1), "id", None) for _ in range(3)]
finally:
    _s.close()
check("get_default_penoplast → eng kichik id (3 marta bir xil)", _t == [_eng] * 3, f"{_t} vs {_eng}")
_d, _it = pp()
check("/api/penoplasts default_id == eng kichik id", _d == _eng, f"{_d} vs {_eng}")
_src = inspect.getsource(services.get_default_penoplast)
check("statik: zaxira so'rovi `.order_by(Inventory.id).first()` bilan", "isnot(True))).order_by(Inventory.id).first()" in _src,
      _src[-400:])

print("\n" + "=" * 66)
print(f"REJIM: {'PostgreSQL' if PG_URL else 'SQLite'}")
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
sys.exit(1 if FAIL else 0)
