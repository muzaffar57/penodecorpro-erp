#!/usr/bin/env python3
"""
test_ombor_turkum.py — kech105 darvozasi: K105-2 (ombor turkumi "Boshqa" har deployda "Bazalt" ga aylanardi) va
K105-3 (penoplast belgisi material NOMIDAN har deployda qo'yilardi; Ta'minotchilar sahifasida yaratilgan yangi
"Penoplast" materiali penoplast belgisisiz qolardi). UI qismi — `tools/test_ombor_turkum_ui.js`.

NIMA UCHUN (asl kod staging `77ef78a` = zip 98 da O'LCHANGAN — `work/probe105.py`, SQLite = PG)
------------------------------------------------------------------------------------------------
  * `main._migrate_payment_columns` HAR ishga tushishda (har deploy / Railway qayta yuklash) bajarardi:
      - `UPDATE inventory SET category = 'Bazalt' WHERE category = 'Boshqa'` — nomidan turkum topilmagan
        material (`crud.guess_category` → 'Boshqa'), Ta'minotchilar sahifasida "Boshqa" tanlangan yoki
        Omborxonada qo'lda "Boshqa" qilingan material keyingi deployda jimgina "Bazalt"; kirim yozuvi "Boshqa".
        Jonli sinovda: "Podveska", "Qorishma (travertin)", "Tayyor loy (Oq marmar)" — "Bazalt", "Boshqa" — 0.
      - `UPDATE inventory SET is_penoplast = TRUE WHERE LOWER(item_name) LIKE '%penoplast%'` — ataylab
        penoplast EMAS deb yaratilgan "Penoplast kleyi" (Kimyoviy qo'shimcha) penoplast bo'lib, korxonada
        plotnost bo'lmasa — ASOSIY plotnost ham bo'lib qolardi.
  * `services.get_penoplast_list` nomida "penoplast" bo'lgan HAR materialni plotnost tanlovida ko'rsatardi.
  * suppliers.html yangi materialni `{item_name, category, unit, …}` bilan yaratardi — "Penoplast" turkumi
    bo'lsa ham `is_penoplast` yo'q → oddiy material: plotnost tanlovida yo'q.

TUZATISH: 'Boshqa' → 'Bazalt' olib tashlandi; ism bo'yicha belgi va asosiy plotnost to'ldirish — FAQAT ustun shu
ishga tushishda YANGI qo'shilganda (eski baza, bir marta); plotnost ro'yxati / asosiy plotnost zaxirasi nom
bo'yicha faqat belgisi NOMA'LUM (NULL) qatorlarni oladi; `crud.add_item` — turkum ANIQ "Penoplast" va
`is_penoplast` yuborilmagan bo'lsa — penoplast.

BO'LIMLAR: A — K105-2 qayta ishga tushish (ikki usul: migratsiya funksiyasi va YANGI jarayonda `import main`);
B — K105-3 ataylab "penoplast emas"; C — yaratishdagi belgi qoidasi; D — ESKI baza (ustunlar yo'q): bir martalik
migratsiya hali ishlaydi va bir marta (alohida baza, alohida jarayon); E — belgisi NULL eski qator; F — korxona
izolyatsiyasi (A / B); G — statik.

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazalari.
    python3 tools/test_ombor_turkum.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_ombor_turkum.py
"""
import os
import sys
import json
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "ombor_turkum_test"
PG_BAZA_ESKI = "ombor_turkum_eski_test"
_DB = os.path.join(tempfile.gettempdir(), "ombor_turkum_test.db")
_DB_ESKI = os.path.join(tempfile.gettempdir(), "ombor_turkum_eski_test.db")


def _pg_yangi(nom):
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
               isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {nom} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {nom}"))
    _adm.dispose()


if PG_URL:
    _pg_yangi(PG_BAZA)
    _pg_yangi(PG_BAZA_ESKI)
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
    DB_ESKI_URL = f"{PG_URL}/{PG_BAZA_ESKI}"
else:
    for _f in (_DB, _DB_ESKI):
        if os.path.exists(_f):
            os.remove(_f)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
    DB_ESKI_URL = f"sqlite:///{_DB_ESKI}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth, services                          # noqa: E402

from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory             # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
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
        print(f"  ✗ {label}   {str(detail)[:400]}")


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


def tartibda(src, *qismlar):
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


def xavfsiz(fn, *a, **k):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {str(e)[:200]}")


def qayta_ishga_tushirish_funksiya():
    """1-usul: server ishga tushishida yuradigan `_migrate_payment_columns` ni qayta chaqirish."""
    return xavfsiz(main._migrate_payment_columns)


_BOLA = r'''
import io, os, sys, json, contextlib
sys.path.insert(0, os.getcwd())
with contextlib.redirect_stdout(io.StringIO()):
    import main
print("IMPORT OK")
'''


def qayta_ishga_tushirish_jarayon():
    """2-usul: YANGI Python jarayonida to'liq `import main` (Railway deployi kabi) — o'sha bazaga."""
    try:
        pr = subprocess.run([sys.executable, "-c", _BOLA], cwd=ROOT, env=dict(os.environ),
                            capture_output=True, text=True, timeout=300)
        return pr.returncode, pr.stdout.strip()[-60:], pr.stderr.strip()[-300:]
    except Exception as e:                 # noqa: BLE001
        return 599, "", f"{type(e).__name__}: {e}"


def material(iid):
    s = SessionLocal()
    try:
        it = s.get(Inventory, iid) if iid else None
        if it is None:
            return None
        return {"category": it.category, "is_penoplast": it.is_penoplast,
                "is_default_penoplast": it.is_default_penoplast}
    finally:
        s.close()


def api_penoplast_nomlari(c):
    r = req(c, "get", "/api/penoplasts")
    j = js(r) or {}
    items = j.get("items") if isinstance(j, dict) else None
    return r.status_code, sorted(str(x.get("name")) for x in (items or []))


def orders_tanlov(c, nom):
    r = req(c, "get", "/orders")
    return r.status_code == 200 and (nom in (getattr(r, "text", "") or ""))


# ── fikstura ────────────────────────────────────────────────────────────────────────────────────────────────
_db = SessionLocal()
_db.add(Company(id=2, name="OT Korxona B"))
_db.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(_db, "ot_a", "Parol123!", UserRole.ADMIN, "OT A", company_id=1)
    auth.create_user(_db, "ot_b", "Parol123!", UserRole.ADMIN, "OT B", company_id=2)
_db.close()


def kirish(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c


CA = kirish("ot_a")
CB = kirish("ot_b")


def yarat(c, tana):
    r = req(c, "post", "/api/inventory", json=tana)
    j = js(r) or {}
    return r.status_code, j.get("id")


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("0. NAZORAT — A korxonada haqiqiy plotnost (asosiy) bor")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
st0, P25 = yarat(CA, {"item_name": "OT Penoplast 25", "category": "Penoplast", "unit": "dona", "stock_quantity": 0,
                      "min_stock": 0, "is_penoplast": True, "is_default_penoplast": True, "volume_per_unit": 1.2})
check("0.1 A: plotnost yaratildi (200)", st0 == 200 and P25, st0)
check("0.2 A: u penoplast va ASOSIY", material(P25) == {"category": "Penoplast", "is_penoplast": True,
                                                        "is_default_penoplast": True}, material(P25))

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. K105-2 — 'Boshqa' turkumi qayta ishga tushishda O'ZGARMAYDI")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
ID = {}
ID["a"] = yarat(CA, {"item_name": "OT Podveska", "unit": "dona", "stock_quantity": 0, "min_stock": 0})[1]
ID["b"] = yarat(CA, {"item_name": "OT Setka", "category": "Boshqa", "unit": "m", "stock_quantity": 0,
                     "min_stock": 0})[1]
ID["c"] = yarat(CA, {"item_name": "OT Ftalat", "category": "Kimyoviy qo'shimchalar", "unit": "kg",
                     "stock_quantity": 0, "min_stock": 0})[1]
_rc = req(CA, "put", f"/api/inventory/{ID['c']}", json={"category": "Boshqa"})
ID["d"] = yarat(CA, {"item_name": "OT Bazalt plita", "category": "Bazalt", "unit": "m2", "stock_quantity": 0,
                     "min_stock": 0})[1]
_rk = req(CA, "post", f"/api/inventory/{ID['b']}/purchase", json={"quantity": 10, "price_per_unit": 1000,
                                                                  "notes": "OT kirim"})
check("A0 materiallar yaratildi, qo'lda 'Boshqa' (PUT) va kirim — 200",
      all(ID[k] for k in "abcd") and _rc.status_code == 200 and _rk.status_code == 200,
      [ID, _rc.status_code, _rk.status_code])
oldin = {k: material(ID[k]) for k in "abcd"}
check("A1 yaratilgandan keyin: a (nomidan taxmin) / b (tanlangan) / c (qo'lda) — 'Boshqa', d — 'Bazalt'",
      [oldin[k]["category"] if oldin[k] else None for k in "abcd"] == ["Boshqa", "Boshqa", "Boshqa", "Bazalt"],
      oldin)
qayta_ishga_tushirish_funksiya()
keyin1 = {k: material(ID[k]) for k in "abcd"}
check("A2 1-usul (_migrate_payment_columns qayta) — a 'Boshqa' qoladi (asl: 'Bazalt')",
      keyin1["a"] and keyin1["a"]["category"] == "Boshqa", keyin1["a"])
check("A3 1-usul — b ('Boshqa' tanlangan) 'Boshqa' qoladi (asl: 'Bazalt')",
      keyin1["b"] and keyin1["b"]["category"] == "Boshqa", keyin1["b"])
check("A4 1-usul — c (qo'lda 'Boshqa' qilingan) 'Boshqa' qoladi (asl: 'Bazalt')",
      keyin1["c"] and keyin1["c"]["category"] == "Boshqa", keyin1["c"])
check("A5 NAZORAT — d (ataylab 'Bazalt') 'Bazalt' qoladi", keyin1["d"] and keyin1["d"]["category"] == "Bazalt",
      keyin1["d"])
rc, out, err = qayta_ishga_tushirish_jarayon()
check("A6 2-usul — YANGI jarayonda `import main` muvaffaqiyatli", rc == 0 and "IMPORT OK" in out, [rc, out, err])
keyin2 = {k: material(ID[k]) for k in "abcd"}
check("A7 2-usul (to'liq ishga tushish) — a / b / c 'Boshqa', d 'Bazalt' (asl: hammasi 'Bazalt')",
      [keyin2[k]["category"] if keyin2[k] else None for k in "abcd"] == ["Boshqa", "Boshqa", "Boshqa", "Bazalt"],
      keyin2)
_s = SessionLocal()
try:
    _kirim = _s.execute(text("SELECT category FROM inventory_purchases WHERE inventory_id = :i"),
                        {"i": ID["b"]}).scalars().all()
finally:
    _s.close()
check("A8 kirim yozuvi turkumi = material turkumi ('Boshqa') — ikkalasi bir xil (asl: kirim 'Boshqa', material 'Bazalt')",
      _kirim == ["Boshqa"] and keyin2["b"] and keyin2["b"]["category"] == "Boshqa", [_kirim, keyin2["b"]])
_r = req(CA, "get", "/api/inventory")
_kat = {x.get("item_name"): x.get("category") for x in (js(_r) or []) if isinstance(x, dict)}
check("A9 /api/inventory (foydalanuvchi ko'radigani) — 'OT Podveska' / 'OT Setka' / 'OT Ftalat' — 'Boshqa'",
      [_kat.get(n) for n in ("OT Podveska", "OT Setka", "OT Ftalat")] == ["Boshqa"] * 3, _kat)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. K105-3 — ataylab 'penoplast EMAS' material (nomida 'penoplast' bor)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
stb, KLEY = yarat(CA, {"item_name": "OT Penoplast kleyi", "category": "Kimyoviy qo'shimchalar", "unit": "kg",
                       "stock_quantity": 0, "min_stock": 0, "is_penoplast": False, "is_default_penoplast": False,
                       "volume_per_unit": 1.0})
check("B0 yaratildi — is_penoplast=false", stb == 200 and material(KLEY) and material(KLEY)["is_penoplast"] is False,
      [stb, material(KLEY)])
_st, _nomlar = api_penoplast_nomlari(CA)
check("B1 /api/penoplasts da YO'Q (asl: nomdagi 'penoplast' tufayli BOR)",
      _st == 200 and "OT Penoplast kleyi" not in _nomlar and "OT Penoplast 25" in _nomlar, [_st, _nomlar])
check("B2 /orders plotnost tanlovida YO'Q (asl: BOR)", not orders_tanlov(CA, "OT Penoplast kleyi")
      and orders_tanlov(CA, "OT Penoplast 25"), "")
qayta_ishga_tushirish_funksiya()
check("B3 1-usul qayta ishga tushish — is_penoplast=false QOLADI (asl: true)",
      material(KLEY) and material(KLEY)["is_penoplast"] is False, material(KLEY))
qayta_ishga_tushirish_jarayon()
check("B4 2-usul (to'liq ishga tushish) — is_penoplast=false, asosiy EMAS (asl: true)",
      material(KLEY) and material(KLEY)["is_penoplast"] is False
      and not material(KLEY)["is_default_penoplast"], material(KLEY))
_s = SessionLocal()
try:
    _dp = xavfsiz(services.get_default_penoplast, _s, company_id=1)
    _dp_id = getattr(_dp, "id", None)
finally:
    _s.close()
check("B5 A ning asosiy plotnosti — 'OT Penoplast 25' (kley emas)", _dp_id == P25, [_dp_id, P25, KLEY])
_st, _nomlar = api_penoplast_nomlari(CA)
check("B6 qayta ishga tushishlardan keyin ham /api/penoplasts da kley YO'Q", _st == 200
      and "OT Penoplast kleyi" not in _nomlar, _nomlar)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. K105-3 — yaratishda penoplast belgisi (crud.add_item)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
# C1: suppliers.html (asl) AYNAN shu tanani yuborardi — turkum "Penoplast", is_penoplast YO'Q
stc1, P30 = yarat(CA, {"item_name": "OT Plotnost 30", "category": "Penoplast", "unit": "dona", "stock_quantity": 0,
                       "min_stock": 0})
check("C1 turkum 'Penoplast', is_penoplast YUBORILMAGAN → penoplast (asl: oddiy material)",
      stc1 == 200 and material(P30) and material(P30)["is_penoplast"] is True, [stc1, material(P30)])
_st, _nomlar = api_penoplast_nomlari(CA)
check("C2 u /api/penoplasts va /orders plotnost tanlovida BOR (asl: YO'Q)",
      "OT Plotnost 30" in _nomlar and orders_tanlov(CA, "OT Plotnost 30"), _nomlar)
check("C3 A da asosiy plotnost O'ZGARMADI (yangi penoplast asosiy EMAS — 25 bor edi)",
      material(P30) and not material(P30)["is_default_penoplast"] and material(P25)["is_default_penoplast"] is True,
      [material(P30), material(P25)])
stc4, P35 = yarat(CA, {"item_name": "OT Plotnost 35", "category": "Penoplast", "unit": "dona", "stock_quantity": 0,
                       "min_stock": 0, "is_penoplast": False})
check("C4 turkum 'Penoplast', lekin is_penoplast=false ANIQ yuborilgan → penoplast EMAS (aniq qiymat hurmat qilinadi)",
      stc4 == 200 and material(P35) and material(P35)["is_penoplast"] is False, [stc4, material(P35)])
stc5, P40 = yarat(CA, {"item_name": "OT Plotnost 40", "category": "Kimyoviy qo'shimchalar", "unit": "dona",
                       "stock_quantity": 0, "min_stock": 0, "is_penoplast": True, "volume_per_unit": 1.0})
check("C5 turkum boshqa, is_penoplast=true ANIQ → penoplast", stc5 == 200 and material(P40)
      and material(P40)["is_penoplast"] is True, [stc5, material(P40)])
stc6, OXRA = yarat(CA, {"item_name": "OT Oxra", "category": " penoplast ", "unit": "kg", "stock_quantity": 0,
                        "min_stock": 0})
check("C6 turkum AYNAN 'Penoplast' emas (' penoplast ' — kichik harf) → belgi qo'yilmaydi",
      stc6 == 200 and material(OXRA) and material(OXRA)["is_penoplast"] is False, [stc6, material(OXRA)])
stc7, AKRIL = yarat(CA, {"item_name": "OT Akril", "category": "Kimyoviy qo'shimchalar", "unit": "kg",
                         "stock_quantity": 0, "min_stock": 0})
check("C7 oddiy material (turkum Kimyoviy, belgi yo'q) → penoplast EMAS", stc7 == 200 and material(AKRIL)
      and material(AKRIL)["is_penoplast"] is False, [stc7, material(AKRIL)])
# qayta ishlatish yo'li (`add_item`: shu nomli, hali ishlatilmagan — qoldiq 0, kirimsiz — qator qayta ishlatiladi)
stc8, P35b = yarat(CA, {"item_name": "OT Plotnost 35", "category": "Penoplast", "unit": "dona", "stock_quantity": 0,
                        "min_stock": 0})
check("C8 qayta ishlatish yo'lida ham (o'sha qator) — turkum 'Penoplast', belgi yuborilmagan → penoplast",
      stc8 == 200 and P35b == P35 and material(P35) and material(P35)["is_penoplast"] is True,
      [stc8, P35b, P35, material(P35)])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. ESKI baza (penoplast ustunlari YO'Q) — bir martalik migratsiya hali ishlaydi, faqat BIR marta")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ESKI = r'''
import io, os, sys, json, contextlib
sys.path.insert(0, os.getcwd())
with contextlib.redirect_stdout(io.StringIO()):
    import main
from sqlalchemy import text
from database import engine
out = {}
def holat():
    with engine.connect() as c:
        rows = c.execute(text("SELECT item_name, is_penoplast, is_default_penoplast, category FROM inventory "
                              "WHERE item_name LIKE 'OE %' ORDER BY id")).fetchall()
    return [[r[0], None if r[1] is None else bool(r[1]), None if r[2] is None else bool(r[2]), r[3]] for r in rows]
with engine.connect() as c:
    c.execute(text("ALTER TABLE inventory DROP COLUMN is_default_penoplast"))
    c.execute(text("ALTER TABLE inventory DROP COLUMN is_penoplast"))
    for nom, kat in (("OE Penoplast 25", "Penoplast"), ("OE Akril", "Kimyoviy qo'shimchalar"),
                     ("OE Setka", "Boshqa")):
        c.execute(text("INSERT INTO inventory (company_id, item_name, stock_quantity, unit, category, is_deleted) "
                       "VALUES (1, :n, 5, 'dona', :k, FALSE)"), {"n": nom, "k": kat})
    c.commit()
with contextlib.redirect_stdout(io.StringIO()):
    main._migrate_payment_columns()
out["1_eski_baza_migratsiya"] = holat()
with engine.connect() as c:
    c.execute(text("UPDATE inventory SET is_default_penoplast = FALSE"))
    c.execute(text("INSERT INTO inventory (company_id, item_name, stock_quantity, unit, category, is_deleted, "
                   "is_penoplast, is_default_penoplast) VALUES (1, 'OE Penoplast kleyi', 5, 'kg', "
                   "'Kimyoviy qo''shimchalar', FALSE, FALSE, FALSE)"))
    c.commit()
with contextlib.redirect_stdout(io.StringIO()):
    main._migrate_payment_columns()
out["2_ikkinchi_ishga_tushish"] = holat()
print("NATIJA_JSON " + json.dumps(out, ensure_ascii=False))
'''
try:
    _env = dict(os.environ)
    _env["DATABASE_URL"] = DB_ESKI_URL
    _pr = subprocess.run([sys.executable, "-c", _ESKI], cwd=ROOT, env=_env, capture_output=True, text=True,
                         timeout=300)
    _qator = [q for q in _pr.stdout.splitlines() if q.startswith("NATIJA_JSON ")]
    ESKI = json.loads(_qator[-1][len("NATIJA_JSON "):]) if _qator else {}
    ESKI_XATO = "" if _qator else (_pr.stderr[-500:] or _pr.stdout[-300:])
except Exception as e:                     # noqa: BLE001
    ESKI, ESKI_XATO = {}, f"{type(e).__name__}: {e}"
check("D0 eski baza jarayoni ishladi", bool(ESKI), ESKI_XATO)
_e1 = {r[0]: r for r in ESKI.get("1_eski_baza_migratsiya", [])}
check("D1 ustun YANGI qo'shilganda — 'OE Penoplast 25' nomidan penoplast (bir martalik migratsiya ishlaydi)",
      _e1.get("OE Penoplast 25", [None, None])[1] is True, _e1)
check("D2 'OE Akril' / 'OE Setka' — penoplast EMAS", _e1.get("OE Akril", [None, None])[1] is False
      and _e1.get("OE Setka", [None, None])[1] is False, _e1)
check("D3 asosiy plotnost bir marta qo'yildi — 'OE Penoplast 25' (yagona)",
      _e1.get("OE Penoplast 25", [None, None, None])[2] is True
      and sum(1 for r in _e1.values() if r[2]) == 1, _e1)
check("D4 eski bazada 'Boshqa' turkumi 'Bazalt' ga AYLANMADI (asl: 'Bazalt')",
      _e1.get("OE Setka", [None, None, None, None])[3] == "Boshqa", _e1)
_e2 = {r[0]: r for r in ESKI.get("2_ikkinchi_ishga_tushish", [])}
check("D5 ikkinchi ishga tushish (ustunlar ENDI bor) — keyin yaratilgan 'OE Penoplast kleyi' (false) false qoladi "
      "(asl: true)", _e2.get("OE Penoplast kleyi", [None, None])[1] is False, _e2)
check("D6 ikkinchi ishga tushish — asosiy plotnost QAYTA qo'yilmaydi (hammasi false edi; asl: bittasini qo'yardi)",
      bool(_e2) and sum(1 for r in _e2.values() if r[2]) == 0, _e2)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Belgisi NOMA'LUM (NULL) eski qator — nom bo'yicha zaxira FAQAT shular uchun")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_db = SessionLocal()
try:
    _db.execute(text("INSERT INTO inventory (company_id, item_name, stock_quantity, unit, category, is_deleted, "
                     "is_penoplast, is_default_penoplast) VALUES (1, 'OT Penoplast eski', 5, 'dona', NULL, FALSE, "
                     "NULL, FALSE)"))
    _db.commit()
finally:
    _db.close()
_st, _nomlar = api_penoplast_nomlari(CA)
check("E1 belgisi NULL, nomida 'penoplast' — plotnost ro'yxatida BOR (eski xulq saqlandi)",
      "OT Penoplast eski" in _nomlar, _nomlar)
check("E2 belgisi ANIQ false — ro'yxatda YO'Q (kley, 'OT Plotnost 35' emas — u endi true)",
      "OT Penoplast kleyi" not in _nomlar, _nomlar)
# B korxona: faqat NULL va false "penoplast" nomli materiallar — asosiy plotnost zaxirasi
_db = SessionLocal()
try:
    _db.add(Company(id=3, name="OT Korxona C"))
    _db.commit()
    for cid, nom, flag in ((2, "OTB Penoplast kleyi", False), (2, "OTB Penoplast eski", None),
                           (3, "OTC Penoplast kleyi", False)):
        _db.execute(text("INSERT INTO inventory (company_id, item_name, stock_quantity, unit, is_deleted, "
                         "is_penoplast, is_default_penoplast) VALUES (:c, :n, 5, 'kg', FALSE, :f, FALSE)"),
                    {"c": cid, "n": nom, "f": flag})
    _db.commit()
    _b = xavfsiz(services.get_default_penoplast, _db, company_id=2)
    _c3 = xavfsiz(services.get_default_penoplast, _db, company_id=3)
finally:
    _db.close()
check("E3 B: plotnost belgisi yo'q — asosiy zaxira NULL belgili eski qator ('OTB Penoplast eski'), kley EMAS "
      "(asl: nom bo'yicha birinchisi — kley)", getattr(_b, "item_name", None) == "OTB Penoplast eski",
      getattr(_b, "item_name", _b))
check("E4 C: faqat ANIQ false kley — asosiy plotnost YO'Q (None) (asl: kley)", _c3 is None,
      getattr(_c3, "item_name", _c3))
# E5: nom bo'yicha zaxira tartibi BARQAROR (eng kichik id) — PG da `ORDER BY` siz birinchi qator JISMONIY tartibda
# keladi (K103-6 saboqi). Kattaroq id li qator jismonan OLDIN yoziladi (aniq id bilan, ketma-ketlikdan ancha yuqori),
# kichik id lisi — keyin: `ORDER BY id` bo'lmasa PG kattasini qaytaradi (SQLite rowid tartibida — farq sezilmaydi).
_db = SessionLocal()
try:
    _db.add(Company(id=4, name="OT Korxona D"))
    _db.commit()
    _max = int(_db.execute(text("SELECT COALESCE(MAX(id), 0) FROM inventory")).scalar() or 0)
    for iid, nom in ((_max + 200, "OTD Penoplast ikkinchi"), (_max + 100, "OTD Penoplast birinchi")):
        _db.execute(text("INSERT INTO inventory (id, company_id, item_name, stock_quantity, unit, is_deleted, "
                         "is_penoplast, is_default_penoplast) VALUES (:i, 4, :n, 5, 'dona', FALSE, NULL, FALSE)"),
                    {"i": iid, "n": nom})
    _db.commit()
    _d4 = xavfsiz(services.get_default_penoplast, _db, company_id=4)
    _d4_kichik = _db.execute(text("SELECT MIN(id) FROM inventory WHERE company_id = 4")).scalar()
finally:
    _db.close()
check("E5 D: ikki NULL belgili eski qator — asosiy zaxira ENG KICHIK id li ('OTD Penoplast birinchi'), jismoniy "
      "tartibdan qat'iy nazar", getattr(_d4, "id", None) == _d4_kichik
      and getattr(_d4, "item_name", None) == "OTD Penoplast birinchi", [getattr(_d4, "item_name", _d4), _d4_kichik])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. Korxona izolyatsiyasi (A / B)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
stf1, B20 = yarat(CB, {"item_name": "OTB Plotnost 20", "category": "Penoplast", "unit": "dona", "stock_quantity": 0,
                       "min_stock": 0})
check("F1 B: Ta'minotchilar tanasi bilan yangi plotnost — B niki, penoplast", stf1 == 200 and material(B20)
      and material(B20)["is_penoplast"] is True, [stf1, material(B20)])
_stb, _nb = api_penoplast_nomlari(CB)
check("F2 B ning /api/penoplasts — faqat B niki (A ning 'OT …' YO'Q)", _stb == 200 and "OTB Plotnost 20" in _nb
      and not any(n.startswith("OT ") for n in _nb), _nb)
_sta, _na = api_penoplast_nomlari(CA)
check("F3 A ning /api/penoplasts — B niki YO'Q", _sta == 200 and not any(n.startswith("OTB") for n in _na), _na)
qayta_ishga_tushirish_funksiya()
qayta_ishga_tushirish_jarayon()
check("F4 qayta ishga tushishlardan keyin: A ning asosiy plotnosti o'zgarmadi, B ning materiallari o'zgarmadi",
      material(P25)["is_default_penoplast"] is True and material(B20)["is_penoplast"] is True, [material(P25),
                                                                                                 material(B20)])
_db = SessionLocal()
try:
    _bd = xavfsiz(services.get_default_penoplast, _db, company_id=2)
finally:
    _db.close()
check("F5 B ning asosiy plotnosti — B niki ('OTB Plotnost 20'), A niki EMAS", getattr(_bd, "company_id", None) == 2
      and getattr(_bd, "item_name", None) == "OTB Plotnost 20", getattr(_bd, "item_name", _bd))

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. Statik")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAIN = fayl("main.py")
# izoh qatorlari (tuzatish tarixini aytadi) — statik tekshiruvda hisobga olinmaydi
MAIN_KOD = "\n".join(q for q in MAIN.split("\n") if not q.strip().startswith("#"))
check("G1 main.py KODIDA (izohlardan tashqari) 'Boshqa' → 'Bazalt' UPDATE YO'Q",
      "SET category = 'Bazalt' WHERE category = 'Boshqa'" not in MAIN_KOD and len(MAIN_KOD) > 1000)
check("G2 ism bo'yicha penoplast UPDATE — ustun yangi qo'shilgandagina (bayroq, keyin shart, keyin UPDATE)",
      tartibda(MAIN, "_penoplast_ustuni_yangi = 'is_penoplast' not in inv_cols", "if _penoplast_ustuni_yangi:",
               "UPDATE inventory SET is_penoplast = TRUE"))
check("G3 asosiy plotnost to'ldirish — ustun yangi qo'shilgandagina",
      tartibda(MAIN, "_asosiy_ustuni_yangi = 'is_default_penoplast' not in inv_cols",
               "WHERE is_default_penoplast = TRUE\"", ")).scalar() if _asosiy_ustuni_yangi else 1"))
SUPR = fayl("templates/supplier_receive.html")
check("G4 supplier_receive.html: yangi material turkumlarida '🧱 Bazalt' YO'Q, 'Boshqa' BOR",
      'value="Bazalt"' not in SUPR and '<option value="Boshqa">Boshqa</option>' in SUPR)
check("G5 supplier_receive.html: turkumsiz material 'Boshqa' guruhida; o'lik updateBazaltWrapVisibility YO'Q",
      "const cat = i.category || 'Boshqa';" in SUPR and "updateBazaltWrapVisibility" not in SUPR)
SUP = fayl("templates/suppliers.html")
check("G6 suppliers.html: yangi material turkumi o'zgarsa apNewItemCategoryChange; tanada is_penoplast",
      'id="ap-newitem-category" onchange="apNewItemCategoryChange()"' in SUP
      and "is_penoplast: isPeno" in SUP)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   -", f)

try:
    from database import engine as _eng
    _eng.dispose()
except Exception:                          # noqa: BLE001
    pass
if PG_URL:
    try:
        from sqlalchemy import create_engine as _ce2, text as _tx2
        _adm = _ce2(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
                    isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx2(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
            _c.execute(_tx2(f"DROP DATABASE IF EXISTS {PG_BAZA_ESKI} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass
else:
    for _f in (_DB, _DB_ESKI):
        try:
            os.remove(_f)
        except OSError:
            pass
sys.exit(1 if FAIL else 0)
