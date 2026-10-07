#!/usr/bin/env python3
"""
test_finished_tartib.py — 15-band darvozasi (kech35, 2026-09-23).

NIMA UCHUN KERAK (jonli `web-sinov` da O'LCHANGAN, kech28)
-----------------------------------------------------------
Tayyor mahsulotlar ro'yxati `order_by(FinishedProduct.source,
FinishedProduct.name)` bilan saralanardi. Nomi (va manbasi) bir xil
mahsulotlar orasida tartib ANIQLANMAGAN edi: PostgreSQL da qator UPDATE
qilinganda (masalan qoldiq o'zgarganda) u jadvalning oxiriga o'tadi va
ro'yxatda o'rin almashadi (jonli: 56|55 → 55|56). Zararsiz, lekin
foydalanuvchi uchun ro'yxat "sakraydi", qidiruvdagi `LIMIT 10` esa bir
xil nomli ko'p mahsulot bo'lsa HAR SAFAR boshqa 10 tasini qaytarishi mumkin.

Tuzatish: `crud.get_finished_products`, `get_finished_products_for_main_page`
(ikki tarmoq) va `search_finished_products` da `FinishedProduct.id` —
oxirgi saralash kaliti.

REJIMLAR
--------
* Odatiy (SQLite, `hammasi.sh`): SQLite teng kalitli qatorlarni odatda
  rowid tartibida beradi — asl kod bu rejimda TASODIFAN to'g'ri chiqishi
  mumkin. Shuning uchun 6-bo'lim STATIK: har `order_by` oxirida
  `FinishedProduct.id` bor-yo'qligini AST bilan tekshiradi.
* `PG_URL` berilsa: har ishga YANGI PostgreSQL bazasi; fikstura qatorlari
  UPDATE qilinadi va (1b) jismoniy tartib id tartibidan FARQ qilishi
  O'LCHANADI — ya'ni dinamik tekshiruvlar asl kodni HAQIQATAN yiqita oladi.

ISHGA TUSHIRISH
---------------
    python3 tools/test_finished_tartib.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_finished_tartib.py
"""
import os
import sys
import ast
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "finished_tartib_test"
_DB = os.path.join(tempfile.gettempdir(), "finished_tartib_test.db")

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
    import crud, auth                              # noqa: E402

from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, FinishedProduct, StockSource,   # noqa: E402
                    ProductionStatus)
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


# ------------------------------------------------------------------ foydalanuvchi
db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "FT_admin", "Parol123!", UserRole.ADMIN, "FT", company_id=1)

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "FT_admin", "password": "Parol123!"},
          follow_redirects=False)
if _lr.status_code != 302:
    print(f"LOGIN BO'LMADI: {_lr.status_code} {getattr(_lr, 'text', '')[:200]}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

BIR = "FT_TARTIB_BIR"       # 3 ta, manba PRODUCED, nomi bir xil
IKKI = "FT_TARTIB_IKKI"     # 3 ta, manba RETURNED, nomi bir xil
GURUHLAR = {BIR: StockSource.PRODUCED, IKKI: StockSource.RETURNED}

section("1. Fikstura: har guruhda nomi bir xil 3 ta mahsulot, keyin 1- va 2-si UPDATE")
IDS = {BIR: [], IKKI: []}
_s = SessionLocal()
try:
    for _nom, _manba in GURUHLAR.items():
        for _k in range(3):
            _fp = FinishedProduct(
                company_id=1, name=_nom, category="profil", unit="metr",
                quantity=5.0 + _k, produced_quantity=5.0 + _k, is_coated=True,
                source=_manba, production_status=ProductionStatus.READY,
                unit_price=1000, cost_price=0, volume_m3=0.0,
            )
            _s.add(_fp)
            _s.commit()
            IDS[_nom].append(_fp.id)
    # UPDATE: PostgreSQL da yangilangan qator versiyasi jadvalning oxiriga
    # yoziladi — jismoniy tartib 3, 1, 2 bo'ladi (jonli holatdagi "sakrash").
    for _nom in GURUHLAR:
        for _id in IDS[_nom][:2]:
            _s.execute(text("UPDATE finished_products SET quantity = quantity + 1 WHERE id = :i"),
                       {"i": _id})
        _s.commit()
    if PG_URL:
        # Yangi jadvalda statistika yo'q — rejalashtiruvchi `company_id` indeksi
        # orqali (bitmap) skan tanlaydi va HOT zanjiri asl tartibni saqlab,
        # nuqsonni YASHIRADI. ANALYZE dan keyin kichik jadval ketma-ket (seq)
        # skan qilinadi — jonli bazadagi holat (O'LCHANDI, kech35).
        _s.execute(text("ANALYZE finished_products"))
        _s.commit()
finally:
    _s.close()
check("fikstura: har guruhda 3 ta id, o'sish tartibida",
      all(len(IDS[n]) == 3 and IDS[n] == sorted(IDS[n]) for n in GURUHLAR), str(IDS))

if PG_URL:
    _s = SessionLocal()
    try:
        # Asl (id kalitisiz) saralash shu fiksturada tartibni BUZISHI SHART —
        # aks holda 2–5-bo'limlar asl kodni yiqita olmaydi (sezgirlik isboti).
        _asl = [x.id for x in _s.query(FinishedProduct).filter(
            FinishedProduct.company_id == 1).order_by(
            FinishedProduct.source, FinishedProduct.name).all() if x.name == BIR]
    finally:
        _s.close()
    check("[PG] 1b. id kalitisiz saralash (asl so'rov) bu fiksturada tartibni buzadi",
          len(_asl) == 3 and _asl != sorted(_asl), f"asl so'rov {_asl}")


def tartib(ro, nom):
    """Ro'yxatda `nom` li yozuvlarning id lari (kelish tartibida)."""
    chiqish = []
    for x in ro or []:
        if isinstance(x, dict):
            n, i = x.get("name"), x.get("id")
        else:
            n, i = getattr(x, "name", None), getattr(x, "id", None)
        if n == nom:
            chiqish.append(i)
    return chiqish


def guruh_tekshir(yorliq, ro, nomlar=(BIR, IKKI)):
    if isinstance(ro, tuple) and ro and ro[0] == "XATO":
        check(f"{yorliq}: chaqiruv", False, ro[1][:200])
        return
    for nom in nomlar:
        t = tartib(ro, nom)
        check(f"{yorliq}: '{nom}' — 3 ta, id o'sish tartibida",
              t == IDS[nom], f"kelgan {t}, kutilgan {IDS[nom]}")


section("2. crud.get_finished_products (`/finished` sahifasi, `?source=` / `?only_available=`)")
_d = SessionLocal()
guruh_tekshir("get_finished_products()", safe(crud.get_finished_products, _d, company_id=1))
guruh_tekshir("get_finished_products(source=produced)",
              safe(crud.get_finished_products, _d, source="produced", company_id=1), (BIR,))
guruh_tekshir("get_finished_products(only_available=True)",
              safe(crud.get_finished_products, _d, only_available=True, company_id=1))
_d.close()

section("3. crud.get_finished_products_for_main_page (standart va show_all)")
_d = SessionLocal()
guruh_tekshir("for_main_page()", safe(crud.get_finished_products_for_main_page, _d, company_id=1))
guruh_tekshir("for_main_page(show_all=True)",
              safe(crud.get_finished_products_for_main_page, _d, show_all=True, company_id=1))
_d.close()

section("4. /api/finished (Tayyor mahsulotlar sahifasi, hisobotlar, buyurtma formasi)")
for _url, _nomlar in (("/api/finished", (BIR, IKKI)),
                      ("/api/finished?show_all=true", (BIR, IKKI)),
                      ("/api/finished?source=produced", (BIR,)),
                      ("/api/finished?source=returned", (IKKI,)),
                      ("/api/finished?only_available=true", (BIR, IKKI))):
    _r = req(C, "get", _url)
    _j = js(_r)
    if _r.status_code != 200 or not isinstance(_j, list):
        check(f"{_url} → 200 va massiv", False, f"{_r.status_code} {str(_j)[:160]}")
        continue
    guruh_tekshir(_url, _j, _nomlar)

section("5. /api/finished/search (buyurtmada taklif, LIMIT 10)")
for _nom in (BIR, IKKI):
    _r = req(C, "get", "/api/finished/search", params={"q": _nom})
    _j = js(_r) or {}
    _it = _j.get("items") if isinstance(_j, dict) else None
    if _r.status_code != 200 or not isinstance(_it, list):
        check(f"search q={_nom} → 200 va items", False, f"{_r.status_code} {str(_j)[:160]}")
        continue
    guruh_tekshir(f"search q={_nom}", _it, (_nom,))

section("6. Statik: har `order_by` oxirida `FinishedProduct.id` (SQLite tasodifini yopadi)")


def order_by_kalitlari(fayl, funksiya):
    """`funksiya` ichidagi har `.order_by(...)` chaqiruvi argumentlari
    (matn ko'rinishida) ro'yxati. Tahlil qila olmasa — ("XATO", ...)."""
    try:
        daraxt = ast.parse(open(os.path.join(ROOT, fayl), encoding="utf-8").read())
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {e}")
    for node in ast.walk(daraxt):
        if isinstance(node, ast.FunctionDef) and node.name == funksiya:
            chiqish = []
            for n in ast.walk(node):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and n.func.attr == "order_by"):
                    chiqish.append([ast.unparse(a) for a in n.args])
            return chiqish
    return ("XATO", f"{funksiya} topilmadi")


for _fn, _soni in (("get_finished_products", 1),
                   ("get_finished_products_for_main_page", 2),
                   ("search_finished_products", 1)):
    _k = order_by_kalitlari("crud.py", _fn)
    if isinstance(_k, tuple):
        check(f"crud.{_fn}: AST", False, _k[1])
        continue
    check(f"crud.{_fn}: order_by soni = {_soni}", len(_k) == _soni, str(_k)[:200])
    check(f"crud.{_fn}: har order_by oxirgi kaliti FinishedProduct.id",
          bool(_k) and all(a and a[-1] == "FinishedProduct.id" for a in _k), str(_k)[:200])

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
