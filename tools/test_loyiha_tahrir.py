#!/usr/bin/env python3
"""
test_loyiha_tahrir.py — kech107 darvozasi (5-bo'lim 10-band, "1a loyiha tahririda muddat"): LOYIHA TAHRIRI —
muddat (deadline) va ixtiyoriy maydonlarni tozalash. UI qismi — `tools/test_loyiha_tahrir_ui.js`.

NIMA UCHUN (asl kod staging `061e082` = zip 101 da O'LCHANGAN — `work/probe107a.py`, SQLite = PG)
-------------------------------------------------------------------------------------------------
  * Tahrir oynasida "Muddati" maydoni YO'Q edi, server esa `PUT /api/projects/{id}` dagi `deadline` ni 400 bilan rad
    etardi ("Bu maydonni o'zgartirib bo'lmaydi: deadline") — loyiha muddatini qo'shish, o'zgartirish yoki olib
    tashlashning birorta yo'li yo'q edi (yaratishda kiritilmagan bo'lsa — hech qachon).
  * Tahrir oynasining AYNAN tanasi — telefon, manzil, Telegram ID va izoh TOZALANGAN (`null`) — 200 qaytarardi,
    lekin `crud.update_project` `None` qiymatlarni JIMGINA tashlab yuborardi: eski telefon / manzil / tg_id joyida
    qolardi (mijozga Telegram xabarlari davom etardi, sahifa esa "saqlandi" deb qayta yuklanardi). `description: null`
    va `total_budget: null` ham 200 bilan o'zgarishsiz.

TUZATISH: `crud._upd_rules()["Project"]["deadline"] = ("sana", True)`, `schemas.ProjectUpdate.deadline`;
`update_project` — YUBORILGAN ixtiyoriy maydon `null` bo'lsa tozalanadi (`crud.LOYIHA_TOZALANADIGAN`),
`total_budget: null` — 0 (yaratish qoidasi), majburiy maydonlar `null` — 400 (avvalgidek); `projects.html` tahrir
oynasiga "Muddati" (`e-deadline`).

BO'LIMLAR: A — muddat (qo'shish / o'zgartirish / olib tashlash / noto'g'ri sana); B — tozalash (UI tanasi); C — qisman
tahrir va majburiy maydonlar; D — korxona izolyatsiyasi; E — sahifa (render); F — statik.

REJIMLAR: SQLite; `PG_URL` berilsa — YANGI PG bazasi.
    python3 tools/test_loyiha_tahrir.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_loyiha_tahrir.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "loyiha_tahrir_test"
_DB = os.path.join(tempfile.gettempdir(), "loyiha_tahrir_test.db")

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
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas                                 # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import UserRole, Project               # noqa: E402
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


def baza(pid):
    s = SessionLocal()
    try:
        p = s.get(Project, pid) if pid else None
        if p is None:
            return None
        return {"client_phone": p.client_phone, "client_address": p.client_address, "description": p.description,
                "notes": p.notes, "deadline": p.deadline.strftime("%Y-%m-%d %H:%M") if p.deadline else None,
                "status": p.status.name if p.status else None, "total_budget": float(p.total_budget or 0),
                "project_name": p.project_name, "client_name": p.client_name}
    finally:
        s.close()


# ── Fikstura: A (1-korxona) va B (2-korxona) adminlari ──────────────────────
s = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    if s.get(Company, 2) is None:
        s.add(Company(id=2, name="LT Korxona B"))
        s.commit()
    auth.create_user(s, "lt_admin", "Parol123!", UserRole.ADMIN, "LT admin", company_id=1)
    auth.create_user(s, "lt_admin_b", "Parol123!", UserRole.ADMIN, "LT admin B", company_id=2)
s.commit()
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
req(C, "post", "/login", data={"username": "lt_admin", "password": "Parol123!"}, follow_redirects=False)
req(CB, "post", "/login", data={"username": "lt_admin_b", "password": "Parol123!"}, follow_redirects=False)


def yarat(**k):
    tana = {"client_name": "Karimov Botir", "client_phone": "+998901234567", "client_address": "Andijon, Bog'ishamol 5",
            "project_name": "LT Hovli fasadi", "total_budget": 5_000_000, "deadline": "2026-10-05",
            "notes": "tg_id=123456789, eshik oldi"}
    tana.update(k)
    r = req(C, "post", "/api/projects", json=tana)
    return (js(r) or {}).get("id") if r.status_code == 200 else None


# ══════════════════════════════════════════════════════════════
section("A — muddat (tahrirda qo'shish / o'zgartirish / olib tashlash)")
P1 = yarat()
check("A0 yaratishda muddat saqlanadi (15-band — nazorat)", baza(P1) and baza(P1)["deadline"] == "2026-10-05 00:00", baza(P1))
r = req(C, "put", f"/api/projects/{P1}", json={"deadline": "2026-10-20"})
check("A1 tahrirda muddatni o'zgartirish — 200 va bazada 2026-10-20 (asl: 400 'Bu maydonni o'zgartirib bo'lmaydi')",
      r.status_code == 200 and baza(P1)["deadline"] == "2026-10-20 00:00", (r.status_code, r.text[:200], baza(P1)))
P2 = yarat(project_name="LT Muddatsiz", deadline=None)
r = req(C, "put", f"/api/projects/{P2}", json={"deadline": "2026-11-01"})
check("A2 muddatsiz yaratilgan loyihaga keyin muddat qo'shish", r.status_code == 200 and baza(P2)["deadline"] == "2026-11-01 00:00",
      (r.status_code, r.text[:200], baza(P2)))
r = req(C, "put", f"/api/projects/{P1}", json={"deadline": None})
check("A3 muddatni olib tashlash (`null`) — bazada NULL", r.status_code == 200 and baza(P1)["deadline"] is None,
      (r.status_code, r.text[:200], baza(P1)))
r = req(C, "put", f"/api/projects/{P1}", json={"deadline": ""})
check("A3b bo'sh matn ham olib tashlaydi (UI — `value || null`, API — '')", r.status_code == 200 and baza(P1)["deadline"] is None,
      (r.status_code, r.text[:200], baza(P1)))
req(C, "put", f"/api/projects/{P1}", json={"deadline": "2026-10-20"})
_oldin = baza(P1)
_yomon = {}
for _qiymat in ("2026-13-45", "abc", "1999-12-31", "2101-01-01", 20261020, True):
    r = req(C, "put", f"/api/projects/{P1}", json={"deadline": _qiymat, "client_address": "BUZILMASIN"})
    _yomon[str(_qiymat)] = r.status_code
check("A4 noto'g'ri muddat (13-oy, matn, 1999 / 2101 yil, son, bool) — 400 va HECH NARSA o'zgarmaydi",
      all(v == 400 for v in _yomon.values()) and baza(P1) == _oldin, (_yomon, baza(P1), _oldin))
r = req(C, "get", "/projects")
check("A5 sahifa kartasi yangi muddatni ko'rsatadi (Toshkent: 20.10.2026; xom qiymat 2026-10-20T00:00:00)",
      r.status_code == 200 and "20.10.2026" in r.text and 'data-deadline-raw="2026-10-20T00:00:00"' in r.text, r.status_code)

# ══════════════════════════════════════════════════════════════
section("B — tozalash: tahrir oynasining AYNAN tanasi (saveEditProject)")
P3 = yarat(project_name="LT Tozalash")
UI_TANA = {"client_name": "Karimov Botir", "client_phone": None, "project_name": "LT Tozalash", "client_address": None,
           "total_budget": 5_000_000, "status": "ACTIVE", "deadline": None, "notes": None}
r = req(C, "put", f"/api/projects/{P3}", json=UI_TANA)
_b = baza(P3)
check("B1 telefon tozalandi (asl: eski +998901234567 qolardi)", r.status_code == 200 and _b["client_phone"] is None, _b)
check("B2 manzil tozalandi", _b and _b["client_address"] is None, _b)
check("B3 Telegram ID + izoh tozalandi (`notes` NULL — mijozga xabar ketmaydi)", _b and _b["notes"] is None, _b)
check("B4 muddat ham (UI — maydon bo'sh)", _b and _b["deadline"] is None, _b)
check("B5 qolganlari o'zgarmadi (nom, mijoz, byudjet, holat)",
      _b and (_b["project_name"], _b["client_name"], _b["total_budget"], _b["status"]) ==
      ("LT Tozalash", "Karimov Botir", 5_000_000.0, "ACTIVE"), _b)
P4 = yarat(project_name="LT Tg", notes="tg_id=555, izoh qoladi")
r = req(C, "put", f"/api/projects/{P4}", json={"notes": "izoh qoladi"})
check("B6 faqat Telegram ID olib tashlandi, izoh qoldi (loyihaIzohYasa)", r.status_code == 200 and baza(P4)["notes"] == "izoh qoladi",
      baza(P4))
s = SessionLocal()
_p = s.get(Project, P4)
_p.description = "Eski tavsif"
s.commit()
s.close()
r = req(C, "put", f"/api/projects/{P4}", json={"description": None})
check("B7 `description: null` — tozalanadi (asl: o'zgarmasdi)", r.status_code == 200 and baza(P4)["description"] is None, baza(P4))
r = req(C, "put", f"/api/projects/{P4}", json={"total_budget": None})
check("B8 `total_budget: null` — 0 (yaratish qoidasi: None → 0; asl: jimgina o'zgarmasdi)",
      r.status_code == 200 and baza(P4)["total_budget"] == 0.0, (r.status_code, baza(P4)))

# ══════════════════════════════════════════════════════════════
section("C — qisman tahrir va majburiy maydonlar")
P5 = yarat(project_name="LT Qisman")
_oldin = baza(P5)
r = req(C, "put", f"/api/projects/{P5}", json={"status": "COMPLETED"})
_b = baza(P5)
check("C1 faqat holat (markProjectComplete) — boshqa maydonlar (telefon, manzil, izoh, muddat) TEGILMAYDI",
      r.status_code == 200 and _b["status"] == "COMPLETED" and all(_b[k] == _oldin[k] for k in
                                                                    ("client_phone", "client_address", "notes", "deadline", "total_budget")),
      (_oldin, _b))
_natija = {}
for _k in ("project_name", "client_name", "status"):
    r = req(C, "put", f"/api/projects/{P5}", json={_k: None, "client_address": "BUZILMASIN"})
    _natija[_k] = (r.status_code, (js(r) or {}).get("detail"))
check("C2 majburiy maydon `null` (nom, mijoz, holat) — 400 va hech narsa o'zgarmaydi",
      all(v[0] == 400 for v in _natija.values()) and baza(P5)["client_address"] == _oldin["client_address"], _natija)
r = req(C, "put", f"/api/projects/{P5}", json={"total_paid": 1})
check("C3 `total_paid` — avvalgidek 400 (to'lovlardan hisoblanadi)", r.status_code == 400, (r.status_code, r.text[:160]))
r = req(C, "put", f"/api/projects/{P5}", json={"company_id": 2})
check("C4 noma'lum maydon (`company_id`) — 400", r.status_code == 400, (r.status_code, r.text[:160]))
with contextlib.redirect_stdout(_quiet):
    _s = SessionLocal()
    try:
        _nat = crud.update_project(_s, P5, schemas.ProjectUpdate(client_phone=None))
    finally:
        _s.close()
check("C5 crud ildizi (`ProjectUpdate(client_phone=None)` — aniq berilgan) ham tozalaydi",
      _nat is not None and baza(P5)["client_phone"] is None, baza(P5))

# ══════════════════════════════════════════════════════════════
section("D — korxona izolyatsiyasi")
_oldin = baza(P5)
r = req(CB, "put", f"/api/projects/{P5}", json={"deadline": "2030-01-01", "client_address": None})
check("D1 B korxona admini A loyihasini tahrirlay olmaydi (404) va hech narsa o'zgarmaydi",
      r.status_code == 404 and baza(P5) == _oldin, (r.status_code, baza(P5)))

# ══════════════════════════════════════════════════════════════
section("E — sahifa (render)")
P6 = yarat(project_name="LT Sahifa", deadline="2026-12-31")
r = req(C, "get", "/projects")
h = r.text if r.status_code == 200 else ""
check("E1 /projects 200", r.status_code == 200, r.status_code)
check("E2 tahrir oynasida 'Muddati' maydoni (`id=\"e-deadline\"`, type=date)",
      'id="e-deadline"' in h and tartibda(h, 'id="editModal"', "Muddati", 'type="date" id="e-deadline"'), "")
check("E3 kartada muddatning xom qiymati (`data-deadline-raw`) — tahrir oynasi shundan to'ldiradi",
      'data-deadline-raw="2026-12-31T00:00:00"' in h, "")

# ══════════════════════════════════════════════════════════════
section("F — statik")
_c = fayl("crud.py")
_q = getattr(crud, "_upd_rules", lambda: {})() if callable(getattr(crud, "_upd_rules", None)) else {}
check("F1 tahrir qoidasida `deadline` — ('sana', True)", (_q.get("Project") or {}).get("deadline") == ("sana", True), (_q.get("Project") or {}).get("deadline"))
check("F2 `crud.LOYIHA_TOZALANADIGAN` — telefon, manzil, tavsif, izoh, muddat",
      set(getattr(crud, "LOYIHA_TOZALANADIGAN", ()) or ()) ==
      {"client_phone", "client_address", "description", "notes", "deadline"}, getattr(crud, "LOYIHA_TOZALANADIGAN", None))
_i = _c.find("def update_project(")
_j = _c.find("\ndef ", _i + 10)
_fn = _c[_i:_j] if _i >= 0 else ""
check("F3 `update_project` da `value is not None` bilan tashlab yuborish YO'Q",
      _fn and "and value is not None:" not in _fn and "LOYIHA_TOZALANADIGAN" in _fn, "")
check("F4 `schemas.ProjectUpdate` da `deadline`", "deadline" in getattr(schemas.ProjectUpdate, "model_fields", {}), "")
_h = fayl("templates/projects.html")
check("F5 saveEditProject tanasida `deadline:` (bo'sh — null)",
      tartibda(_h, "async function saveEditProject", "const payload = {", "deadline: document.getElementById('e-deadline').value || null"), "")
check("F6 openEditModal muddatni Toshkent sanasi bilan to'ldiradi (`tkISO(d.deadlineRaw)`)",
      tartibda(_h, "function openEditModal", "document.getElementById('e-deadline').value = d.deadlineRaw ? tkISO(d.deadlineRaw) : ''"), "")

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
        with _adm.connect() as _c2:
            _c2.execute(_tx2(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass
else:
    try:
        os.remove(_DB)
    except OSError:
        pass
sys.exit(1 if FAIL else 0)
