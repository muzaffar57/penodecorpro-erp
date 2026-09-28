#!/usr/bin/env python3
"""
test_kam_qoldiq_yagona.py — kech108, K108-2 (19-band) darvozasi.

EGASI QARORI (2026-09-28, "Ha, ko'rinsin (Tavsiya)"): minimal qoldig'i belgilanmagan (0) material TUGASA — bosh sahifa
«Kam qolgan xomashyo» blokida ham ko'rinadi; qo'ng'iroqcha «qolmadi» va Omborxona «Kam qolganlar» bilan BIR XIL gapiradi.

O'LCHANGAN (`main` zaxirasi → o'tish simulyatsiyasi, lokal nusxa): Penoplast 10P (qoldiq −0.0619, min 0) —
`/api/inventory/kpi` low_count 1, `/api/notifications` "Penoplast 10P qolmadi", LEKIN `/api/dashboard/stats`
low_stock_items [] va `/api/warnings/low-stock` [] ("Barcha xomashyo yetarli"). Uch xil qoida bor edi.

YAGONA qoida (`crud.kam_qoldiq_sharti` / `crud.kam_qoldiqmi`): yashirilmagan, "Tayyor loy (" bilan boshlanmaydigan,
COALESCE(qoldiq, 0) ≤ COALESCE(min, 0).

FIKSTURA (A–H) va KUTILGAN "kam" to'plami — HAMMA joyda AYNAN {A, B, D, F}:
  A −0.06 / 0 (tugagan, min belgilanmagan)   B 0 / 0   C 5 / 0 (yetarli)   D 5 / 10 (kam)   E 15 / 10 (yetarli)
  F 0 / NULL (min NULL — 0 deb)   G Tayyor loy 0 / 0 (HAQIQIY generator — hech qachon)   H yashirilgan 0 / 0 (hech qachon)

  1 — server: `/api/dashboard/stats` (bosh sahifa, dashboard), `/api/warnings/low-stock` (buyurtmalar sahifasi),
      `/api/dashboard/today-tasks`, `/api/dashboard/charts` low_stock, `/api/reports/alerts`, Telegram «Ombor hisoboti»
      (`/api/inventory/full-stock-report` — yozib olinadi), `crud.get_low_stock_items` (Telegram ogohlantirishlari),
      `/api/inventory/kpi` low_count; matnlar ("tugagan" / "tugadi"), `tugagan` belgisi; NULL min — 500 YO'Q.
  2 — Omborxona sahifasi (server render): A / B / F qatori "Tugagan", chizig'i 0 % (asl: 100 %).
  3 — statik: YAGONA shart ishlatiladi, `min_stock > 0` sharti qolmagan.

REJIMLAR: odatiy (SQLite); `PG_URL` berilsa — har ishga YANGI PostgreSQL bazasi.
    python3 tools/test_kam_qoldiq_yagona.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_kam_qoldiq_yagona.py
"""
import os
import re
import sys
import types
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "kam_qoldiq_yagona_test"
_DB = os.path.join(tempfile.gettempdir(), "kam_qoldiq_yagona_test.db")
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
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

import io                                          # noqa: E402
import html                                        # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, services                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import text as _sql                # noqa: E402

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
        print(f"  ✗ {REJIM}{label}   {str(detail)[:400]}")


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


TG = []


def _yozib_ol(text, company_id=None, *a, **k):
    TG.append((company_id, str(text)))


main._send_telegram = _yozib_ol

db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "KQ_admin", "Parol123!", UserRole.ADMIN, "KQ", company_id=1)
db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "KQ_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print(f"LOGIN BO'LMADI: {_lr.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

NOM = {"A": "KQ_A_tugagan_min0", "B": "KQ_B_nol_min0", "C": "KQ_C_bor_min0", "D": "KQ_D_kam_min10",
       "E": "KQ_E_yetarli_min10", "F": "KQ_F_nol_minNULL", "H": "KQ_H_yashirin_nol"}
QIYMAT = {"A": (-0.06, 0), "B": (0, 0), "C": (5, 0), "D": (5, 10), "E": (15, 10), "F": (0, None), "H": (0, 0)}
KAM = {"A", "B", "D", "F"}
IDS = {}

section("0. Fikstura")
for k in ("A", "B", "C", "D", "E", "F", "H"):
    r = req(C, "post", "/api/inventory", json={"item_name": NOM[k], "unit": "kg", "stock_quantity": 0, "min_stock": 0})
    IDS[k] = (js(r) or {}).get("id")
s = SessionLocal()
try:
    for k, (q, m) in QIYMAT.items():
        if IDS.get(k):
            s.execute(_sql("UPDATE inventory SET stock_quantity = :q, min_stock = :m WHERE id = :i"),
                      {"q": q, "m": m, "i": IDS[k]})
    if IDS.get("H"):
        s.execute(_sql("UPDATE inventory SET is_deleted = :t WHERE id = :i"), {"t": True, "i": IDS["H"]})
    s.commit()
    with contextlib.redirect_stdout(_quiet):
        _loy = services.get_or_create_loy_stock(s, types.SimpleNamespace(name="KQ retsept", company_id=1), company_id=1)
    if _loy is not None:
        s.execute(_sql("UPDATE inventory SET stock_quantity = 0, min_stock = 0 WHERE id = :i"), {"i": _loy.id})
        s.commit()
        IDS["G"] = _loy.id
        NOM["G"] = _loy.item_name
finally:
    s.close()
check("fikstura: A–H yaratildi (G — HAQIQIY Tayyor loy generatori), F.min_stock = NULL",
      all(IDS.get(k) for k in "ABCDEFGH") and NOM.get("G", "").startswith("Tayyor loy ("), (IDS, NOM.get("G")))
_s = SessionLocal()
try:
    _fm = _s.execute(_sql("SELECT min_stock FROM inventory WHERE id = :i"), {"i": IDS.get("F")}).scalar()
finally:
    _s.close()
check("fikstura: F.min_stock bazada NULL", _fm is None, _fm)


def fiks(nomlar):
    """Berilgan nomlar ro'yxatidan fikstura harflari to'plami."""
    t = set()
    for n in nomlar:
        for k, v in NOM.items():
            if n == v:
                t.add(k)
    return t


section("1. Server — HAMMA joyda AYNAN {A, B, D, F}")
st = js(req(C, "get", "/api/dashboard/stats")) or {}
_li = st.get("low_stock_items") or []
check("1.1 /api/dashboard/stats (bosh sahifa «Kam qolgan xomashyo», dashboard) — low_stock_items AYNAN {A, B, D, F}",
      fiks(i.get("item_name") for i in _li) == KAM, sorted(fiks(i.get("item_name") for i in _li)))
check("1.2 /api/dashboard/stats low_stock_count == len(low_stock_items)", st.get("low_stock_count") == len(_li), st.get("low_stock_count"))
_a = {i.get("item_name"): i for i in _li}
check("1.3 tugagan (qoldiq ≤ 0) — `tugagan: true`, alert «tugagan»; D (5 / 10) — `tugagan: false`",
      all(_a.get(NOM[k], {}).get("tugagan") is True and "tugagan" in _a.get(NOM[k], {}).get("alert", "") for k in "ABF")
      and _a.get(NOM["D"], {}).get("tugagan") is False, {k: _a.get(NOM[k]) for k in "ABDF"})
check("1.4 NULL min (F) — min_stock 0.0, deficit 0.0 (500 / None YO'Q)",
      _a.get(NOM["F"], {}).get("min_stock") == 0.0 and _a.get(NOM["F"], {}).get("deficit") == 0.0, _a.get(NOM["F"]))
w = js(req(C, "get", "/api/warnings/low-stock")) or {}
check("1.5 /api/warnings/low-stock (buyurtmalar sahifasi ogohlantirishi) — AYNAN {A, B, D, F}",
      fiks(i.get("item_name") for i in (w.get("warnings") or [])) == KAM, w)
tt = js(req(C, "get", "/api/dashboard/today-tasks")) or {}
_tt = [x.get("text", "") for x in (tt.get("tasks") if isinstance(tt, dict) else tt) or []] if tt else []
_ttk = {k for k in NOM if any(t.startswith(NOM[k] + " ") for t in _tt)}
check("1.6 /api/dashboard/today-tasks — kam / tugagan AYNAN {A, B, D, F}", _ttk == KAM, _tt)
check("1.7 bugungi vazifalar matni: A «tugagan», D «kam qolgan»",
      any(t.startswith(NOM["A"] + " tugagan") for t in _tt) and any(t.startswith(NOM["D"] + " kam qolgan") for t in _tt), _tt)
ch = js(req(C, "get", "/api/dashboard/charts")) or {}
_chl = ch.get("low_stock") or ch.get("low_stock_items") or []
check("1.8 /api/dashboard/charts low_stock — AYNAN {A, B, D, F}", fiks(i.get("item_name") for i in _chl) == KAM,
      [i.get("item_name") for i in _chl][:12])
al = js(req(C, "get", "/api/reports/alerts")) or []
_alt = [x.get("text", "") for x in (al if isinstance(al, list) else al.get("alerts", []))]
_alk = {k for k in NOM if any(f"Omborda {NOM[k]} " in t for t in _alt)}
check("1.9 /api/reports/alerts (hisobotlar) — AYNAN {A, B, D, F}; A «tugadi», D «kamaymoqda»",
      _alk == KAM and any(f"Omborda {NOM['A']} tugadi" in t for t in _alt)
      and any(f"Omborda {NOM['D']} kamaymoqda" in t for t in _alt), _alt)
TG.clear()
r = req(C, "post", "/api/inventory/full-stock-report")
_tg = "\n".join(t for _, t in TG)
_kam_qism = _tg.split("━━━ YETARLI")[0] if "━━━ YETARLI" in _tg else ""
_tgk = {k for k in NOM if f" {NOM[k]}:" in _kam_qism}
check("1.10 Telegram «Ombor hisoboti» → 200, «KAM QOLGANLAR» AYNAN {A, B, D, F}, A «— tugagan»",
      r.status_code == 200 and _tgk == KAM and f"{NOM['A']}:" in _kam_qism and "— tugagan" in _kam_qism,
      (r.status_code, sorted(_tgk), _tg[:500]))
s = SessionLocal()
try:
    _gl = {i.item_name for i in crud.get_low_stock_items(s, company_id=1)}
finally:
    s.close()
check("1.11 crud.get_low_stock_items (Telegram ogohlantirishlari) — AYNAN {A, B, D, F} (NULL min F ham)",
      fiks(_gl) == KAM, sorted(fiks(_gl)))
k = js(req(C, "get", "/api/inventory/kpi")) or {}
check("1.12 /api/inventory/kpi low_count == 4 (A, B, D, F) == len(crud.get_low_stock_items)",
      k.get("low_count") == 4 and len(_gl) == 4, k)
nt = js(req(C, "get", "/api/notifications")) or []
_nt = [x.get("text", "") for x in nt] if isinstance(nt, list) else []
check("1.13 qo'ng'iroqcha «qolmadi» — A, B, F (qoldiq ≤ 0), G / H YO'Q (o'zgarmagan qoida)",
      all(f"{NOM[k]} qolmadi" in _nt for k in "ABF") and not any(f"{NOM[k]} qolmadi" in _nt for k in "GH"), _nt)
check("1.14 funksiyalar: crud.kam_qoldiq_sharti / crud.kam_qoldiqmi mavjud va KPI bilan bir xil",
      callable(getattr(crud, "kam_qoldiq_sharti", None)) and callable(getattr(crud, "kam_qoldiqmi", None)))

section("2. Omborxona sahifasi (server render)")
_inv = req(C, "get", "/inventory")
_h = getattr(_inv, "text", "")


def qator(nom):
    """Omborxona qatori: `<div class="mat-row" … data-name="<nom kichik harf>" … data-status="…">` dan keyingi qatorgacha."""
    i = _h.find(f'data-name="{html.escape(nom.lower(), quote=True)}"')
    if i < 0:
        return ""
    a = _h.rfind('<div class="mat-row"', 0, i)
    b = _h.find('<div class="mat-row"', i)
    return _h[a:(b if b > 0 else len(_h))]


def chiziq(q):
    m = re.search(r'class="stock-fill[^"]*" style="width:\s*(\d+)%', q)
    return int(m.group(1)) if m else None


def yorliq(q):
    m = re.search(r'<span class="stat-badge [^"]*">([^<]*)</span>', q)
    return m.group(1) if m else None


_qa, _qb, _qf, _qc = qator(NOM["A"]), qator(NOM["B"]), qator(NOM["F"]), qator(NOM["C"])
check("2.1 /inventory 200", _inv.status_code == 200, _inv.status_code)
check("2.2 A (−0.06 / 0), B (0 / 0), F (0 / NULL) — «Tugagan», chizig'i 0 % (asl: 100 %)",
      all(yorliq(q) == "Tugagan" and chiziq(q) == 0 for q in (_qa, _qb, _qf)), [(chiziq(q), yorliq(q)) for q in (_qa, _qb, _qf)])
check("2.3 C (5 / 0) — «Yetarli», chizig'i 100 % (o'zgarmagan)", yorliq(_qc) == "Yetarli" and chiziq(_qc) == 100,
      (chiziq(_qc), yorliq(_qc)))

section("3. Statik")
_cs = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
_ss = open(os.path.join(ROOT, "services.py"), encoding="utf-8").read()
_ms = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()


def kodsiz_izoh(t):
    return "\n".join(q for q in t.split("\n") if not q.strip().startswith("#"))


check("3.1 services.py: `Inventory.min_stock > 0` sharti QOLMAGAN (check_low_stock, get_business_alerts)",
      "Inventory.min_stock > 0" not in kodsiz_izoh(_ss), "")
check("3.2 services.check_low_stock va get_business_alerts — `kam_qoldiq_sharti()` orqali",
      kodsiz_izoh(_ss).count("kam_qoldiq_sharti()") >= 2, kodsiz_izoh(_ss).count("kam_qoldiq_sharti()"))
check("3.3 crud.get_low_stock_items — `kam_qoldiq_sharti()` orqali", "filter(*kam_qoldiq_sharti())" in _cs)
check("3.4 main.py: Telegram «Ombor hisoboti» `min_q > 0 and` sharti QOLMAGAN, `crud.kam_qoldiqmi(item)`",
      "if min_q > 0 and qty <= min_q" not in _ms and "if crud.kam_qoldiqmi(item):" in _ms)
check("3.5 main.py: `float(item.min_stock)` (NULL da TypeError) QOLMAGAN",
      "min_q = float(item.min_stock)\n" not in _ms)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
