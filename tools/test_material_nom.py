#!/usr/bin/env python3
"""
test_material_nom.py — kech112 darvozasi: K112-4 — materialni (ombor) boshqa material nomiga qayta nomlash 500 berardi.

NIMA UCHUN KERAK (kech112 jonli C zanjiri sizish tekshiruvida topildi; asl kod `5519200` da O'LCHANDI —
`work/k113/probe_nom.py`, SQLite = PG): `PUT /api/inventory/{id}` da `item_name` shu korxonadagi BOSHQA materialning
nomiga teng bo'lsa `uq_inventory_company_item_name` ga urilib 500 ("Serverda kutilmagan xato") va xato jurnaliga
yozuv chiqardi; o'chirilgan (yashirilgan, tarixi bor) material nomi ham shunday (PG). Nom chetidagi bo'shliqlar
saqlanardi ("Akril " — "Akril" dan alohida material): tahrirda ham, API orqali yaratishda ham (UI `trim` qiladi).

YECHIM (texnik — Claude): `crud.update_item` — nom chetidagi bo'shliqlarsiz, 2 belgidan qisqa — rad; shu korxonada
boshqa material (yashirilgani ham) shu nomda bo'lsa — hech narsa yozilmasdan 400 (aniq sabab); marshrutda
`IntegrityError` → 400 (parallel so'rov uchun ikkinchi to'siq). `crud.add_item` — nom chetidagi bo'shliqlarsiz
(" Akril " → mavjud "Akril" qoidasi: ishlatilmagan — qayta ishlatiladi, ishlatilgan — 400). Katta / kichik harf
qoidasi O'ZGARMAGAN ("AKRIL" — alohida material, avvalgidek).

BO'LIMLAR: N — qayta nomlash, Y — yaratish, T — korxona chegarasi, J — xato jurnali, S — statik.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
    python3 tools/test_material_nom.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_material_nom.py
Asl kodga qarshi QULAMAYDI (HTTP istisno → 599, yangi nomlar `getattr`). Chiqish kodi 0 — hammasi o'tdi.
"""
import os
import sys
import inspect
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "material_nom_test"
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
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'material_nom_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, ErrorLog   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        detail = f"{detail} [{type(e).__name__}: {e}]"
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


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════
# Fikstura: A (1) va B (2) korxonalari
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="MN B korxona"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "MN_A", "Parol123!", UserRole.ADMIN, "Nom Admin A", company_id=1)
    auth.create_user(_db, "MN_B", "Parol123!", UserRole.ADMIN, "Nom Admin B", company_id=2)
_db.close()
C = {}
for _h in ("A", "B"):
    _c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    _lr = req(_c, "post", "/login", data={"username": f"MN_{_h}", "password": "Parol123!"}, follow_redirects=False)
    C[_h] = _c
    check(f"F0 {_h} tizimga kirdi", _lr.status_code == 302, _lr.status_code)


def so(h, metod, url, **k):
    return req(C[h], metod, url, **k)


def jurnal_soni():
    s = SessionLocal()
    try:
        return s.query(ErrorLog).count()
    finally:
        s.close()


def nomlar(cid=1):
    s = SessionLocal()
    try:
        return {x.id: (x.item_name, bool(x.is_deleted)) for x in s.query(Inventory).filter(Inventory.company_id == cid)
                .order_by(Inventory.id).all()}
    finally:
        s.close()


ID = {}
# «Akril» — ISHLATILGAN (boshlang'ich qoldiq + xarid tarixi), «Qum» — ishlatilmagan, «Yashirin» — yashirilgan (tarixi bor)
ID["akril"] = (js(so("A", "post", "/api/inventory", json={"item_name": "MN Akril", "unit": "kg", "stock_quantity": 10,
                                                           "price_per_unit": 1000})) or {}).get("id")
ID["qum"] = (js(so("A", "post", "/api/inventory", json={"item_name": "MN Qum", "unit": "kg"})) or {}).get("id")
ID["bosh"] = (js(so("A", "post", "/api/inventory", json={"item_name": "MN Bosh", "unit": "kg"})) or {}).get("id")
ID["yashirin"] = (js(so("A", "post", "/api/inventory", json={"item_name": "MN Yashirin", "unit": "kg", "stock_quantity": 1,
                                                              "price_per_unit": 100})) or {}).get("id")
_s = SessionLocal()
try:
    _y = _s.get(Inventory, ID["yashirin"])
    _y.is_deleted = True               # yashirilgan (tarixi bor) material — SQLite / PG da bir xil holat
    _s.commit()
finally:
    _s.close()
ID["b_mat"] = (js(so("B", "post", "/api/inventory", json={"item_name": "MN B Kley", "unit": "kg"})) or {}).get("id")
check("F1 materiallar yaratildi", all(ID.values()), ID)
J0 = jurnal_soni()

section("N. Qayta nomlash")
_old = nomlar()
r = so("A", "put", f"/api/inventory/{ID['qum']}", json={"item_name": "MN Akril"})
check("N1 boshqa material nomiga → 400 (500 emas)", r.status_code == 400, (r.status_code, r.text[:200]))
check("N2 sabab — «allaqachon omborda mavjud»", "allaqachon omborda mavjud" in str((js(r) or {}).get("detail")), r.text[:200])
check("N3 hech narsa o'zgarmadi", nomlar() == _old, (nomlar(), _old))
r = so("A", "put", f"/api/inventory/{ID['qum']}", json={"item_name": "  MN Akril  "})
check("N4 bo'shliqli boshqa nom («  MN Akril  ») → 400", r.status_code == 400, (r.status_code, r.text[:200]))
r = so("A", "put", f"/api/inventory/{ID['qum']}", json={"item_name": "MN Yashirin"})
check("N5 yashirilgan material nomiga → 400 (sabab: yashirilgan)", r.status_code == 400
      and "yashirilgan" in str((js(r) or {}).get("detail")), (r.status_code, r.text[:200]))
r = so("A", "put", f"/api/inventory/{ID['qum']}", json={"item_name": "  a "})
check("N6 bo'shliqsiz 1 belgili nom → 400", r.status_code == 400, (r.status_code, r.text[:200]))
check("N7 N1–N6 dan keyin ham hech narsa o'zgarmadi", nomlar() == _old, nomlar())
r = so("A", "put", f"/api/inventory/{ID['qum']}", json={"item_name": "  MN Qum Sariq  "})
check("N8 yangi nom bo'shliqlar bilan → 200", r.status_code == 200, (r.status_code, r.text[:200]))
check("N9 nom chetidagi bo'shliqlarsiz saqlandi («MN Qum Sariq»)", nomlar().get(ID["qum"], ("",))[0] == "MN Qum Sariq",
      nomlar().get(ID["qum"]))
r = so("A", "put", f"/api/inventory/{ID['akril']}", json={"item_name": "MN Akril", "min_stock": 3})
check("N10 o'z nomi bilan (o'zgarmagan) + boshqa maydon → 200", r.status_code == 200, (r.status_code, r.text[:200]))
r = so("A", "put", f"/api/inventory/{ID['akril']}", json={"min_stock": 4})
check("N11 nomsiz tahrir → 200", r.status_code == 200, (r.status_code, r.text[:200]))
r = so("A", "put", f"/api/inventory/{ID['bosh']}", json={"item_name": "mn akril"})
check("N12 katta / kichik harf farqi — alohida nom (qoida o'zgarmagan) → 200", r.status_code == 200, (r.status_code, r.text[:200]))

section("Y. Yaratish — nom chetidagi bo'shliqlar")
r = so("A", "post", "/api/inventory", json={"item_name": "  MN Akril ", "unit": "kg"})
check("Y1 ishlatilgan nom bo'shliqlar bilan → 400 (alohida material YARATILMAYDI)", r.status_code == 400, (r.status_code, r.text[:200]))
_n = len(nomlar())
r = so("A", "post", "/api/inventory", json={"item_name": " MN Qum Sariq ", "unit": "kg"})
check("Y2 ishlatilmagan nom bo'shliqlar bilan → o'sha material qayta ishlatiladi (yangi qator yo'q)",
      r.status_code == 200 and (js(r) or {}).get("id") == ID["qum"] and len(nomlar()) == _n, (r.status_code, r.text[:160]))
r = so("A", "post", "/api/inventory", json={"item_name": "  MN Yangi  ", "unit": "kg"})
check("Y3 yangi nom bo'shliqlar bilan → «MN Yangi» saqlandi", r.status_code == 200 and (js(r) or {}).get("item_name") == "MN Yangi",
      (r.status_code, r.text[:160]))
r = so("A", "post", "/api/inventory", json={"item_name": "  x  ", "unit": "kg"})
check("Y4 bo'shliqsiz 1 belgili nom → 400", r.status_code == 400, (r.status_code, r.text[:200]))

section("T. Korxona chegarasi")
r = so("B", "put", f"/api/inventory/{ID['b_mat']}", json={"item_name": "MN Akril"})
check("T1 B o'z materialini A dagi nom bilan atashi mumkin → 200", r.status_code == 200, (r.status_code, r.text[:200]))
r = so("B", "put", f"/api/inventory/{ID['qum']}", json={"item_name": "MN Buzildi"})
check("T2 B A ning materialini qayta nomlay olmaydi → 404", r.status_code == 404, (r.status_code, r.text[:200]))

section("J. Xato jurnali")
check("J1 butun test davomida xato jurnaliga yangi yozuv YO'Q (500 yo'q)", jurnal_soni() == J0, (J0, jurnal_soni()))

section("S. Statik")
_ui = manba(crud, "update_item")
check("S1 `crud.update_item` — nom bandligi yozishdan OLDIN tekshiriladi (yashirilgani ham)",
      tartibda(_ui, 'if "item_name" in update_data', "Inventory.company_id == db_item.company_id", "Inventory.id != db_item.id",
               "raise ValueError", "setattr(db_item, field, value)"))
_ai = manba(crud, "add_item")
check("S2 `crud.add_item` — nom `strip` qilinadi, mavjud nom qidiruvidan OLDIN",
      tartibda(_ai, '_toza_nom = str(item_data.item_name or "").strip()', "existing_deleted ="))
_mu = manba(main, "api_update_inventory_item")
check("S3 marshrut — `IntegrityError` → 400 (ikkinchi to'siq)", tartibda(_mu, "except IntegrityError:", "db.rollback()",
                                                                        "status_code=400"))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
