#!/usr/bin/env python3
"""
test_e_tarix.py — kech120, E BOSQICH 3-qism (TARIX VA JURNALLAR): «Tizim jurnallari» (Kirish tarixi, Audit jurnali) —
filtr, sahifalash, hamma amal o'zbekcha, tahrir yozuvida nima o'zgargani; Ombor — «Xaridlar tarixi» va «Ombor harakatlari»
(«Yana yuklash», jami soni, material «Tarix», tanlangan filtr, davr jami serverdan).

NIMA UCHUN KERAK (audit kech114, «Katta Korxona»; kodda va rasmda ko'rilgan):
  G6-23  Kirish tarixi va Audit jurnali faqat oxirgi 100 yozuv — sana / foydalanuvchi filtri, qidiruv yo'q («o'tgan hafta kim
         buyurtmani o'chirdi?» — javob yo'q); nomi berilmagan amallar xom inglizcha («refunded», «release_reservation»,
         «delete», «gift_period_add_master»); «Tahrirlandi» yozuvida eski va yangi qiymat bir xil («partiya 1 m², 4 ta material
         → partiya 1 m², 4 ta material»). Yo'lda topilgan: «Zaxiradan tiklash» yozuvi korxonasiz (NOT NULL) — yozilmasdi.
  G4-14  «Xaridlar tarixi» — oxirgi 60, «Ombor harakatlari» — 100 (sana bilan 500), «yana» yo'q, kesilgani aytilmaydi; bitta
         materialning tarixi yo'q (server qo'llaydi, sahifa ishlatmaydi); tanlangan filtr tugmasi ko'rinmaydi; «Tanlangan davr
         — jami» faqat yuklangan qatorlardan.
BO'LIMLAR: S — statik; L — Audit jurnali (server HTML: sahifalash, barqaror tartib, sana — Toshkent kuni chegarasi, kim,
  amal, matn — `%` / `_` oddiy belgi, birgalikda, noto'g'ri qiymatlar, havolalar ikkinchi bo'lim filtrini saqlaydi, korxona
  chegarasi, o'zbekcha nomlar, escape); K — Kirish tarixi; D — tahrir yozuvida farq (retsept, buyurtma — haqiqiy API);
  Z — zaxiradan tiklash yozuvi; A — ombor API (`X-Jami`, `offset`, «Kirim» hujjati bo'linmaydi, davr jami = baza);
  B — brauzer: ombor oynalari («Tarix», «Yana yuklash», tanlangan filtr, davr jami), jurnal yorlig'i manzilda;
  T — telefon 390 px; X — JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 128) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium (B / T bo'limlari; bo'lmasa — o'sha tekshiruvlar yiqiladi).
ISHLATISH: python3 tools/test_e_tarix.py
"""
import os
import re
import sys
import io
import json
import glob
import time
import html
import socket
import inspect
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "e_tarix_test"
_T = tempfile.mkdtemp(prefix="etarix_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'e_tarix_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import production_routes                       # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, ActivityLog, LoginHistory, Inventory, InventoryMovement, InventoryPurchase,  # noqa: E402
                    InventoryReceipt, Project, Master)
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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def tartibda(src, *qismlar):
    p = 0
    for q in qismlar:
        i = src.find(q, p)
        if i < 0:
            return False
        p = i + len(q)
    return True


def manba(obj, nom):
    f = getattr(obj, nom, None)
    if f is None:
        return ""
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAIN = oqi("main.py")
CRUD = oqi("crud.py")
PR = oqi("production_routes.py")
LOGS = oqi("templates/logs.html")
INV = oqi("templates/inventory.html")

# Koddagi HAMMA amal turlari — o'zbekcha nom ro'yxatida bo'lishi SHART (yangi amal qo'shilsa — shu yerda yiqiladi)
_AMAL_RE = [
    re.compile(r"log_activity\(\s*(?:db|_db|s|session)\s*,\s*(?:action\s*=\s*)?[\"']([^\"']+)[\"']"),
    re.compile(r"log_activity\((?:(?!log_activity\()[\s\S]){0,400}?\baction\s*=\s*[\"']([^\"']+)[\"']"),
    re.compile(r"ActivityLog\((?:(?!ActivityLog\()[\s\S]){0,400}?\baction\s*=\s*[\"']([^\"']+)[\"']"),
    re.compile(r"_po_jurnal\(\s*db\s*,\s*po\s*,\s*[\"']([^\"']+)[\"']"),
    re.compile(r"(?<![\w.])_jurnal\(\s*db\s*,\s*c\s*,\s*[\"']([^\"']+)[\"']"),
]
KOD_AMALLARI = {}
for _f in sorted(glob.glob(os.path.join(ROOT, "*.py"))):
    _src = open(_f, encoding="utf-8").read()
    # `from models import ActivityLog as _X` — taxallus bilan konstruktor ham
    for _takh in set(re.findall(r"ActivityLog as (\w+)", _src)):
        for _m in re.finditer(rf"(?<![\w.]){re.escape(_takh)}\((?:(?!{re.escape(_takh)}\()[\s\S]){{0,400}}?\baction\s*=\s*[\"']([^\"']+)[\"']", _src):
            KOD_AMALLARI.setdefault(_m.group(1), os.path.basename(_f))
    for _r in _AMAL_RE:
        for _m in _r.finditer(_src):
            KOD_AMALLARI.setdefault(_m.group(1), os.path.basename(_f))
_NOMLAR = getattr(crud, "AUDIT_AMALLARI", {}) or {}
check("S1 koddagi HAR amal turi o'zbekcha nom ro'yxatida (`crud.AUDIT_AMALLARI`) — xom inglizcha nom sahifaga chiqmaydi "
      f"(kodda {len(KOD_AMALLARI)} tur)",
      len(KOD_AMALLARI) >= 18 and not [a for a in KOD_AMALLARI if a not in _NOMLAR]
      and all(isinstance(v, tuple) and len(v) == 3 and v[2] for v in _NOMLAR.values()),
      {"yoq": [f"{a} ({f})" for a, f in KOD_AMALLARI.items() if a not in _NOMLAR], "kod": sorted(KOD_AMALLARI)})
check("S2 /logs: kirish tarixi va audit jurnali — filtr / sahifalash funksiyalari bilan (100 ta bilan kesish YO'Q)",
      "crud.kirish_tarixi_sahifasi(db, _cid," in MAIN and "crud.audit_jurnali_sahifasi(db, _cid," in MAIN
      and "crud.get_login_history(db, limit=100" not in MAIN and "crud.get_activity_log(db, limit=100, company_id=_cid)" not in MAIN)
check("S3 logs.html: amal nomi `amal_nomi(...)` dan (xom `{{ a.action }}` matn sifatida YO'Q), filtr formalari, sahifa havolalari",
      "{% set _am = amal_nomi(a.action) %}" in LOGS and "{{ a.action }}</" not in LOGS and "{% else %}{{ a.action }}" not in LOGS
      and 'id="auditFiltr"' in LOGS and 'id="kirishFiltr"' in LOGS and 'name="a_amal"' in LOGS and 'name="k_natija"' in LOGS
      and 'rel="next"' in LOGS and "split(farq_belgi, 1)" in LOGS)
_ul = manba(production_routes, "update_bom")
check("S4 retsept tahriri: holat o'zgarishdan OLDIN olinadi, yozuvda «O'zgardi: …» (farq xatosi saqlashga xalaqit bermaydi)",
      tartibda(_ul, "_holat120 = _retsept_holati(bom)", "bom.variant_name = _vnom", "_farq120 = crud.audit_farq_matni(",
               "new_value=_retsept_xulosa(bom, _unit110) + _farq120"))
_uo = manba(crud, "update_order_full")
check("S5 buyurtma tahriri: holat detallar almashishidan OLDIN olinadi, yozuvda farq (farq xatosi yozuvni yo'qotmaydi)",
      tartibda(_uo, "_audit_eski = _buyurtma_audit_holati(order)", "old_snapshot = [", "_audit_after += audit_farq_matni(",
               "except Exception:", "log_activity(db, \"updated\", \"order\""))
check("S6 zaxiradan tiklash yozuvi — korxona bilan, o'zbekcha nomli amal (`backup_restored`), xatoda sessiya tozalanadi",
      'crud.log_activity(db, action="backup_restored"' in MAIN and "company_id=auth.company_id_of(current_user))\n    except Exception:\n        db.rollback()" in MAIN
      and 'action="Zaxiradan tiklash"' not in MAIN)
check("S7 ombor API: `offset`, `X-Jami`, chegaralangan `limit` (1–500), davr jami endpointi, «Kirim» hujjati bo'linmaydi",
      'def api_inventory_movements(response: Response,' in MAIN and 'response.headers["X-Jami"] = str(q.order_by(None).count())' in MAIN
      and '@app.get("/api/inventory/movements/jami")' in MAIN and "crud.kirim_qolgan_qatorlari(" in MAIN
      and 'response.headers["X-Keyingi"]' in MAIN and MAIN.count("limit: int = Query(100, ge=1, le=500)") >= 2)
check("S8 inventory.html: 60 ta bilan kesish YO'Q; «Yana yuklash», jami soni, material «Tarix», tanlangan filtr, davr jami serverdan",
      "purchases?limit=60" not in INV and "params.set('limit', '500')" not in INV and "X-Jami" in INV
      and 'onclick="openMovements({{ item.id }}, this.dataset.name)"' in INV and 'aria-pressed="true"' in INV
      and "/api/inventory/movements/jami?" in INV and "function mvYanaHtml()" in INV and "function phYanaHtml()" in INV)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Fikstura")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "etr_admin", "Parol123!"
_db = SessionLocal()
for _cid, _nom in ((2, "ETR B korxona"), (3, "ETR Bo'sh korxona")):
    if not _db.query(Company).filter(Company.id == _cid).first():
        _db.add(Company(id=_cid, name=_nom))
        _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, ADMIN, PAROL, UserRole.ADMIN, "Tarix Admin", company_id=1)
    auth.create_user(_db, "etr_b", PAROL, UserRole.ADMIN, "Begona Admin", company_id=2)
    auth.create_user(_db, "etr_plat", PAROL, UserRole.ADMIN, "Platforma Egasi", company_id=3)
_pu = _db.query(User).filter(User.username == "etr_plat").first()
_pu.is_platform_admin = True
_db.commit()

# Audit jurnali: 140 yozuv (1-korxona) — hamma amal turi + noma'lum tur, 3 xil «kim», 30 tasi BIR XIL vaqtda (barqaror
# tartib); sana chegarasi (UTC 19:30 = Toshkent 00:30 ertasi kuni); `%` / `_` li nomlar; HTML li nom; eski bir xil tahrir
_AMALLAR = list(_NOMLAR.keys()) + ["foo_noma"]
_KIMLAR = ["Ali Usta", "Vali Hisobchi", "Tarix Admin"]
_BAZA_VAQT = datetime(2026, 9, 25, 12, 0, 0)
_yoz = []
for _i in range(140):
    _vaqt = _BAZA_VAQT - timedelta(minutes=_i) if not (40 <= _i < 70) else _BAZA_VAQT - timedelta(minutes=40)
    _yoz.append(ActivityLog(company_id=1, action=_AMALLAR[_i % len(_AMALLAR)], entity_type="order", entity_id=_i,
                            entity_label=f"ETR-{_i:03d}", performed_by=_KIMLAR[(_i % 5) % 3], new_value=f"qiymat {_i}",
                            created_at=_vaqt))
_yoz += [
    ActivityLog(company_id=1, action="updated", entity_type="order", entity_id=900, entity_label="CHEGARA-1",
                performed_by="Ali Usta", created_at=datetime(2026, 9, 30, 19, 30)),      # Toshkent 01.10 00:30
    ActivityLog(company_id=1, action="updated", entity_type="order", entity_id=901, entity_label="CHEGARA-2",
                performed_by="Ali Usta", created_at=datetime(2026, 9, 30, 18, 59)),      # Toshkent 30.09 23:59
    ActivityLog(company_id=1, action="created", entity_type="order", entity_id=902, entity_label="Chegirma 100% MAXSUS",
                performed_by="Vali Hisobchi", created_at=datetime(2026, 9, 1, 9, 0)),
    ActivityLog(company_id=1, action="created", entity_type="order", entity_id=903, entity_label="kod a_b MAXSUS",
                performed_by="Vali Hisobchi", created_at=datetime(2026, 9, 1, 9, 1)),
    ActivityLog(company_id=1, action="created", entity_type="order", entity_id=904, entity_label="kod aXb MAXSUS",
                performed_by="Vali Hisobchi", created_at=datetime(2026, 9, 1, 9, 2)),
    ActivityLog(company_id=1, action="created", entity_type="order", entity_id=905, entity_label="<b>QALIN</b> nom",
                performed_by="Vali Hisobchi", created_at=datetime(2026, 9, 1, 9, 3)),
    ActivityLog(company_id=1, action="updated", entity_type="bom", entity_id=906, entity_label="ESKI-TAHRIR",
                old_value="«Standart»: partiya 1 m², 4 ta material", new_value="«Standart»: partiya 1 m², 4 ta material",
                performed_by="Ali Usta", created_at=datetime(2026, 9, 1, 9, 4)),
]
for _i in range(6):
    _yoz.append(ActivityLog(company_id=2, action="deleted", entity_type="order", entity_id=_i, entity_label=f"BEGONA-{_i}",
                            performed_by="Begona Kim", created_at=_BAZA_VAQT - timedelta(minutes=_i)))
# Kirish tarixi: 70 (1-korxona) — muvaffaqiyatli / xato aralash, 3 nom; 4 ta (2-korxona)
for _i in range(70):
    _yoz.append(LoginHistory(company_id=1, username=["etr_admin", "ali", "vali"][_i % 3], success=(_i % 4 != 0),
                             ip_address=f"10.0.0.{_i}", created_at=_BAZA_VAQT - timedelta(minutes=_i)))
for _i in range(4):
    _yoz.append(LoginHistory(company_id=2, username="begona_user", success=True, ip_address="10.9.9.9",
                             created_at=_BAZA_VAQT - timedelta(minutes=_i)))
_db.add_all(_yoz)
_db.commit()

# Ombor: «ETR Kley» (kirim / chiqim harakatlari, xaridlar va bitta «Kirim» hujjati sahifa chegarasida), «ETR Tosh»
_kley = Inventory(company_id=1, item_name="ETR Kley", unit="kg", stock_quantity=500, min_stock=1, price_per_unit=1000,
                  category="Kimyoviy qo'shimchalar")
_tosh = Inventory(company_id=1, item_name="ETR Tosh", unit="kg", stock_quantity=500, min_stock=1, price_per_unit=2000,
                  category="Qattiq qotishmalar")
_peno = Inventory(company_id=1, item_name="ETR Penoplast", unit="blok", stock_quantity=1e6, price_per_unit=500000,
                  volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
_kley_b = Inventory(company_id=2, item_name="ETR B Kley", unit="kg", stock_quantity=5, price_per_unit=1000, category="Boshqa")
_db.add_all([_kley, _tosh, _peno, _kley_b])
_db.commit()
KLEY, TOSH, PENO, KLEY_B = _kley.id, _tosh.id, _peno.id, _kley_b.id
_MV_VAQT = datetime(2026, 9, 20, 6, 0, 0)        # Toshkent 20.09 11:00
_mv = []
for _i in range(130):          # Kley: 130 harakat (90 kirim, 40 chiqim), 20.09 dan orqaga — har biri 1 soat
    _mv.append(InventoryMovement(company_id=1, inventory_id=KLEY, item_name="ETR Kley", movement_type="in" if _i % 13 < 9 else "out",
                                 quantity=1.5 if _i % 13 < 9 else 0.25, unit="kg", reason=f"Sinov harakati {_i}",
                                 created_at=_MV_VAQT - timedelta(hours=_i)))
for _i in range(25):           # Tosh: 25 chiqim, bir xil vaqtda (barqaror tartib)
    _mv.append(InventoryMovement(company_id=1, inventory_id=TOSH, item_name="ETR Tosh", movement_type="out", quantity=2,
                                 unit="kg", reason="Tosh chiqimi", created_at=_MV_VAQT - timedelta(hours=3)))
_mv.append(InventoryMovement(company_id=2, inventory_id=KLEY_B, item_name="ETR B Kley", movement_type="in", quantity=999,
                             unit="kg", reason="Begona", created_at=_MV_VAQT))
_db.add_all(_mv)
_rc = InventoryReceipt(company_id=1, document_number="ETR-HUJJAT", receipt_date=datetime(2026, 9, 19))
_db.add(_rc)
_db.commit()
_ph = []
_PH_VAQT = datetime(2026, 9, 19, 10, 0, 0)
for _i in range(95):           # 95 ta yakka xarid (eng yangilari)
    _ph.append(InventoryPurchase(inventory_id=KLEY, item_name="ETR Kley", quantity=1, unit="kg", price_per_unit=1000,
                                 total_amount=1000, purchased_at=_PH_VAQT - timedelta(minutes=_i)))
for _i in range(10):           # «Kirim» hujjati — 10 qator, 96–105-o'rinlar (100-chegarani kesib o'tadi)
    _ph.append(InventoryPurchase(inventory_id=TOSH if _i % 2 else KLEY, item_name="ETR Tosh" if _i % 2 else "ETR Kley",
                                 quantity=2, unit="kg", price_per_unit=2000, total_amount=4000, receipt_id=_rc.id,
                                 purchased_at=_PH_VAQT - timedelta(hours=5)))
for _i in range(20):           # eskiroq 20 ta yakka xarid
    _ph.append(InventoryPurchase(inventory_id=KLEY, item_name="ETR Kley", quantity=3, unit="kg", price_per_unit=1000,
                                 total_amount=3000, purchased_at=_PH_VAQT - timedelta(days=2, minutes=_i)))
_ph.append(InventoryPurchase(inventory_id=KLEY_B, item_name="ETR B Kley", quantity=1, unit="kg", price_per_unit=1,
                             total_amount=1, purchased_at=_PH_VAQT))
_db.add_all(_ph)
_db.commit()
_db.close()


def klient(user):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": PAROL}, follow_redirects=False)
    return c, r.status_code


C, _st1 = klient(ADMIN)
CB, _st2 = klient("etr_b")
CP, _st3 = klient("etr_plat")
check("F0 uchala foydalanuvchi kirdi (302)", (_st1, _st2, _st3) == (302, 302, 302), (_st1, _st2, _st3))
XATO5 = []


def ol(c, url, **k):
    try:
        r = c.get(url, **k)
    except Exception as e:                 # noqa: BLE001
        XATO5.append((url, f"{type(e).__name__}: {e}"))
        return 599, "", {}
    if r.status_code >= 500:
        XATO5.append((url, r.status_code, r.text[:200]))
    return r.status_code, r.text, r.headers




def bolim(h, idsi):
    """Sahifadan bitta bo'lim (`tab-login` / `tab-activity`) HTML qismi."""
    i = h.find(f'<div id="{idsi}"')
    if i < 0:
        return ""
    j = h.find('<div id="tab-', i + 10)
    return h[i:j if j > 0 else len(h)]


def qatorlar(h, idsi):
    """[(id, amal, ko'rinadigan matn)] — bo'lim ichidagi yozuvlar tartibi bilan."""
    b = bolim(h, idsi)
    natija = []
    for m in re.finditer(r'<div class="jr-qator[^"]*" data-id="(\d+)"(?: data-amal="([^"]*)")?', b):
        k = b.find('<div class="jr-qator', m.end())
        qism = b[m.end():k if k > 0 else len(b)]
        matn = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", qism))).strip()
        natija.append((int(m.group(1)), m.group(2), matn))
    return natija


def soni(h, idsi):
    m = re.search(rf'id="{idsi}">\(([\d\s ]+) ta', h)
    return int(re.sub(r"\D", "", m.group(1))) if m else None


def havolalar(h, idsi):
    b = bolim(h, idsi)
    return {k: html.unescape(v) for v, k in re.findall(r'<a href="([^"]+)" rel="(prev|next)"', b)}


def kutilgan_audit(cid=1, f=None):
    """Bazadan MUSTAQIL hisob: korxona yozuvlari, filtr (Python), tartib — vaqt kamayishi, id kamayishi."""
    s = SessionLocal()
    try:
        rows = s.query(ActivityLog).filter(ActivityLog.company_id == cid).all()
        out = [(r.id, r.created_at, r.action, r.performed_by or "", r.entity_label or "", r.old_value or "", r.new_value or "")
               for r in rows]
    finally:
        s.close()
    if f:
        out = [r for r in out if f(r)]
    out.sort(key=lambda r: (r[1], r[0]), reverse=True)
    return [r[0] for r in out]


def tk_kuni(dt):
    return (dt + timedelta(hours=5)).strftime("%Y-%m-%d")


def sahifalar_boyicha(url_asos, idsi, prefiks, max_sahifa=20):
    """1-sahifadan «Eskiroqlar →» havolasi bo'yicha oxirigacha yuradi — [id] (tartib bilan) va sahifalar soni."""
    ids, url, n = [], url_asos, 0
    while url and n < max_sahifa:
        st, h, _ = ol(C, url)
        if st != 200:
            return ids, -st
        ids += [q[0] for q in qatorlar(h, idsi)]
        url = havolalar(h, idsi).get("next")
        n += 1
    return ids, n


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L. Audit jurnali — filtr va sahifalash (server HTML)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_kut = kutilgan_audit()
st, H, _ = ol(C, "/logs?tab=activity")
_q1 = qatorlar(H, "tab-activity")
check(f"L1 filtrsiz: jami = korxona yozuvlari ({len(_kut)}), 1-sahifa — 50 ta, eng yangilari tartib bilan; «1–50 / N»",
      st == 200 and soni(H, "auditSoni") == len(_kut) and [q[0] for q in _q1] == _kut[:50]
      and re.search(r'id="auditSahifa">\s*<span>1–50 / ' + crud.audit_son(len(_kut)).replace(" ", "[\\s ]") + " ta", H),
      (st, soni(H, "auditSoni"), len(_kut), [q[0] for q in _q1][:5], _kut[:5]))
_hamma, _ns = sahifalar_boyicha("/logs?tab=activity", "tab-activity", "a_")
check("L2 «Eskiroqlar →» bo'ylab hamma sahifa: har yozuv AYNAN bir marta, tartib = baza (30 ta bir xil vaqtli yozuv ham), "
      "sahifalar soni = ⌈N/50⌉",
      _hamma == _kut and _ns == (len(_kut) + 49) // 50, (len(_hamma), len(set(_hamma)), len(_kut), _ns))
_oxirgi = (len(_kut) + 49) // 50
st, H, _ = ol(C, f"/logs?tab=activity&a_sahifa={_oxirgi}")
check("L3 oxirgi sahifa: «Eskiroqlar →» yo'q, «← Yangiroqlar» bor (oldingi sahifaga)",
      st == 200 and "next" not in havolalar(H, "tab-activity") and f"a_sahifa={_oxirgi - 1}" in havolalar(H, "tab-activity").get("prev", "")
      and [q[0] for q in qatorlar(H, "tab-activity")] == _kut[(_oxirgi - 1) * 50:], havolalar(H, "tab-activity"))
_xato_sahifa = []
for _v, _kutil in (("abc", 1), ("0", 1), ("-3", 1), ("999", _oxirgi), ("2.5", 1)):
    st, H, _ = ol(C, f"/logs?tab=activity&a_sahifa={_v}")
    _ids = [q[0] for q in qatorlar(H, "tab-activity")]
    if st != 200 or _ids != _kut[(_kutil - 1) * 50:_kutil * 50]:
        _xato_sahifa.append((_v, st, _ids[:3]))
check("L4 noto'g'ri sahifa raqami (abc, 0, −3, 999, 2.5) — 1-sahifa / oxirgi sahifa, 500 yo'q", not _xato_sahifa, _xato_sahifa)

_kut_ali = kutilgan_audit(f=lambda r: r[3] == "Ali Usta")
st, H, _ = ol(C, "/logs?tab=activity&a_kim=Ali+Usta")
_ali_hamma, _ = sahifalar_boyicha("/logs?tab=activity&a_kim=Ali+Usta", "tab-activity", "a_")
_opt = re.findall(r'<option value="([^"]*)"', re.search(r'<select name="a_kim">(.*?)</select>', H, re.S).group(1)) if 'name="a_kim"' in H else []
check("L5 «Kim» filtri — faqat shu foydalanuvchi (hamma sahifalar), ro'yxatda korxona foydalanuvchilari, BEGONA yo'q",
      st == 200 and _ali_hamma == _kut_ali and soni(H, "auditSoni") == len(_kut_ali) and "Ali Usta" in _opt and "Vali Hisobchi" in _opt
      and "Begona Kim" not in _opt and 'value="Ali Usta" selected' in H, (len(_ali_hamma), len(_kut_ali), _opt))
_kut_och = kutilgan_audit(f=lambda r: r[2] in ("deleted", "delete"))
_och, _ = sahifalar_boyicha("/logs?tab=activity&a_amal=deleted", "tab-activity", "a_")
_guruh_nomlari = [g[1] for g in crud.audit_amal_guruhlari()] if hasattr(crud, "audit_amal_guruhlari") else []
check("L6 «Amal» filtri «O'chirildi» — `deleted` VA `delete` (brak bekor qilish), boshqa tur yo'q; filtr ro'yxatida takror nom yo'q",
      _och == _kut_och and len(_kut_och) >= 10 and len(_guruh_nomlari) == len(set(_guruh_nomlari)) and "O'chirildi" in _guruh_nomlari,
      (len(_och), len(_kut_och), _guruh_nomlari))
_matn_x = []
for _q, _f in (("ETR-01", lambda r: "etr-01" in r[4].lower()), ("etr-01", lambda r: "etr-01" in r[4].lower()),
               ("100%", lambda r: "100%" in r[4]), ("a_b", lambda r: "a_b" in r[4]), ("qiymat 13", lambda r: "qiymat 13" in r[6]),
               ("Vali", lambda r: "vali" in r[3].lower() or "vali" in r[4].lower())):
    _k = kutilgan_audit(f=_f)
    _b, _ = sahifalar_boyicha(f"/logs?tab=activity&a_q={_q.replace('%', '%25')}", "tab-activity", "a_")
    if _b != _k:
        _matn_x.append((_q, len(_b), len(_k)))
check("L7 «Qidiruv»: nom / qiymat / kim ichida, katta-kichik harf farqsiz; `%` va `_` — ODDIY belgi («100%» — 1 ta, «a_b» — "
      "«aXb» emas)", not _matn_x, _matn_x)
_kut_c1 = kutilgan_audit(f=lambda r: tk_kuni(r[1]) == "2026-10-01")
_kut_c2 = kutilgan_audit(f=lambda r: tk_kuni(r[1]) == "2026-09-30")
st, H1, _ = ol(C, "/logs?tab=activity&a_dan=2026-10-01&a_gacha=2026-10-01")
st2, H2, _ = ol(C, "/logs?tab=activity&a_dan=2026-09-30&a_gacha=2026-09-30")
_l1 = [q[2] for q in qatorlar(H1, "tab-activity")]
_l2 = [q[2] for q in qatorlar(H2, "tab-activity")]
check("L8 sana — TOSHKENT kuni: UTC 30.09 19:30 (= 01.10 00:30) — 01.10 da, UTC 30.09 18:59 (= 30.09 23:59) — 30.09 da",
      [q[0] for q in qatorlar(H1, "tab-activity")] == _kut_c1 and [q[0] for q in qatorlar(H2, "tab-activity")] == _kut_c2
      and any("CHEGARA-1" in x for x in _l1) and not any("CHEGARA-2" in x for x in _l1)
      and any("CHEGARA-2" in x for x in _l2) and not any("CHEGARA-1" in x for x in _l2), (_l1, _l2))
st, H, _ = ol(C, "/logs?tab=activity&a_dan=2026-10-01&a_gacha=2026-09-30")
_ids_t = [q[0] for q in qatorlar(H, "tab-activity")]
st3, H3, _ = ol(C, "/logs?tab=activity&a_dan=2026-13-45&a_gacha=yoq")
check("L9 teskari sana oralig'i — almashtiriladi (ikkala kun); noto'g'ri sana — e'tiborsiz (filtrsiz natija, maydon bo'sh)",
      sorted(_ids_t) == sorted(_kut_c1 + _kut_c2) and 'name="a_dan" value="2026-09-30"' in H and 'name="a_gacha" value="2026-10-01"' in H
      and st3 == 200 and soni(H3, "auditSoni") == len(_kut) and 'name="a_dan" value=""' in H3, (len(_ids_t), soni(H3, "auditSoni")))
_kut_birga = kutilgan_audit(f=lambda r: r[3] == "Ali Usta" and r[2] == "updated" and tk_kuni(r[1]) >= "2026-09-30")
st, H, _ = ol(C, "/logs?tab=activity&a_kim=Ali+Usta&a_amal=updated&a_dan=2026-09-30")
check("L10 filtrlar BIRGA (kim + amal + sanadan) — AYNAN mos yozuvlar", st == 200 and [q[0] for q in qatorlar(H, "tab-activity")] == _kut_birga
      and len(_kut_birga) == 2, (len(_kut_birga), [q[2][:40] for q in qatorlar(H, "tab-activity")]))
st, H, _ = ol(C, "/logs?tab=activity&a_q=ETR-&k_natija=xato&k_sahifa=2")
_hv = havolalar(H, "tab-activity")
_toz = re.search(r'<form class="jr-filtr" method="get" action="/logs" id="auditFiltr">(.*?)</form>', H, re.S)
_toz_h = re.search(r'id="auditFiltr">.*?<a class="btn btn-outline btn-sm" href="([^"]+)">Tozalash</a>', H, re.S)
_kir_f = re.search(r'id="kirishFiltr">(.*?)</form>', H, re.S)
check("L11 havolalar: «Eskiroqlar →» audit filtrini va KIRISH bo'limi filtrini saqlaydi; «Tozalash» — faqat audit filtri; "
      "har forma ikkinchi bo'lim parametrlarini yashirin maydonda saqlaydi",
      "a_q=ETR-" in _hv.get("next", "") and "k_natija=xato" in _hv.get("next", "") and "k_sahifa=2" in _hv.get("next", "")
      and "a_sahifa=2" in _hv.get("next", "") and "tab=activity" in _hv.get("next", "")
      and _toz_h and "a_q" not in html.unescape(_toz_h.group(1)) and "k_natija=xato" in html.unescape(_toz_h.group(1))
      and _toz and '<input type="hidden" name="k_natija" value="xato">' in _toz.group(1)
      and '<input type="hidden" name="k_sahifa" value="2">' in _toz.group(1)
      and _kir_f and '<input type="hidden" name="a_q" value="ETR-">' in _kir_f.group(1), (_hv, _toz_h and _toz_h.group(1)))
st, H, _ = ol(C, "/logs?tab=activity")
st2, H2, _ = ol(C, "/logs?tab=boshqa")
check("L12 `?tab=activity` — shu yorliq ochiladi (skript), noma'lum yorliq — Kirish tarixi (skriptsiz)",
      "switchLogTab('activity')" in H and "switchLogTab('boshqa')" not in H2 and "if (document.getElementById('tab-" not in H2, "")
_raw = ("refunded", "release_reservation", "auto_release_reservation", "gift_period_add_master", "password_reset",
        "permanently_deleted", "backup_restored", "Zaxiradan tiklash")
_matnlar = {}
_url = "/logs?tab=activity"
while _url:
    st, H, _ = ol(C, _url)
    for _id, _amal, _m in qatorlar(H, "tab-activity"):
        _matnlar.setdefault(_amal, _m)
    _url = havolalar(H, "tab-activity").get("next")
_xom = {a: m for a, m in _matnlar.items() if any(re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", m) for w in _raw if w != "Zaxiradan tiklash")}
_uzb_x = {a: m for a, m in _matnlar.items() if a in _NOMLAR and _NOMLAR[a][1] and _NOMLAR[a][1] not in m}
check("L13 sahifada HAR amal o'zbekcha («pul qaytarildi», «band…», «sovg'a davriga», «paroli tiklandi»…) — ko'rinadigan matnda xom "
      "inglizcha nom YO'Q; noma'lum tur — «amal: foo_noma»",
      len(_matnlar) == len(_AMALLAR) and not _xom and not _uzb_x and "amal: foo_noma" in _matnlar.get("foo_noma", "")
      and "ortiqcha to'lov mijozga qaytarildi" in _matnlar.get("refunded", "") and "sovg'a davriga qo'shildi" in _matnlar.get("gift_period_add_master", ""),
      {"xom": _xom, "uzb_yoq": _uzb_x, "turlar": len(_matnlar)})
st, H, _ = ol(C, "/logs?tab=activity&a_q=BEGONA")
st2, H2, _ = ol(CB, "/logs?tab=activity")
check("L14 korxona chegarasi: A da B yozuvi yo'q (qidiruv bilan ham), B da faqat o'zi (6), B «kim» ro'yxatida A foydalanuvchilari yo'q",
      st == 200 and soni(H, "auditSoni") == 0 and "BEGONA" not in bolim(H, "tab-activity").split("</form>", 1)[-1]
      and soni(H2, "auditSoni") == len(kutilgan_audit(2)) and "ETR-0" not in H2 and "Ali Usta" not in H2,
      (soni(H, "auditSoni"), soni(H2, "auditSoni")))
st, H, _ = ol(C, "/logs?tab=activity&a_q=QALIN")
check("L15 escape: yozuv nomidagi HTML matn bo'lib chiqadi", "&lt;b&gt;QALIN&lt;/b&gt;" in H and "<b><b>QALIN</b>" not in H, "")
st, H, _ = ol(C, "/logs?tab=activity&a_q=ESKI-TAHRIR")
check("L16 eski tahrir yozuvi (eski = yangi, tafsilotsiz) — bir xil «→» juftligi EMAS, izoh: «qisqa tavsif o'zgarmagan»",
      "qisqa tavsif o'zgarmagan" in H and "4 ta material <span" not in bolim(H, "tab-activity"), "")
st, H, _ = ol(C, "/logs?tab=activity&a_dan=2030-01-01")
check("L17 topilmasa — «Bu filtr bo'yicha yozuv yo'q», sahifa chizig'i yo'q", "Bu filtr bo'yicha yozuv yo'q" in bolim(H, "tab-activity")
      and 'id="auditSahifa"' not in H and soni(H, "auditSoni") == 0, "")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Kirish tarixi — filtr va sahifalash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def kutilgan_kirish(cid=1, f=None):
    s = SessionLocal()
    try:
        rows = [(r.id, r.created_at, r.username, bool(r.success)) for r in
                s.query(LoginHistory).filter(LoginHistory.company_id == cid).all()]
    finally:
        s.close()
    if f:
        rows = [r for r in rows if f(r)]
    rows.sort(key=lambda r: (r[1], r[0]), reverse=True)
    return [r[0] for r in rows]


_kk = kutilgan_kirish()
_kh, _kn = sahifalar_boyicha("/logs", "tab-login", "k_")
st, H, _ = ol(C, "/logs")
check(f"K1 filtrsiz: jami = korxona urinishlari ({len(_kk)}), sahifalar bo'ylab har biri bir marta, tartib = baza",
      _kh == _kk and soni(H, "kirishSoni") == len(_kk) and _kn == (len(_kk) + 49) // 50, (len(_kh), len(_kk), _kn))
_kx = kutilgan_kirish(f=lambda r: not r[3])
_kxh, _ = sahifalar_boyicha("/logs?k_natija=xato", "tab-login", "k_")
_kv = kutilgan_kirish(f=lambda r: r[2] == "vali" and r[3])
_kvh, _ = sahifalar_boyicha("/logs?k_kim=vali&k_natija=ok", "tab-login", "k_")
check("K2 «Natija: noto'g'ri urinish» — faqat xatolar; «vali» + muvaffaqiyatli — AYNAN mos",
      _kxh == _kx and len(_kx) >= 17 and _kvh == _kv and len(_kv) >= 10, (len(_kxh), len(_kx), len(_kvh), len(_kv)))
_kd = kutilgan_kirish(f=lambda r: tk_kuni(r[1]) == tk_kuni(_BAZA_VAQT))
_kdh, _ = sahifalar_boyicha(f"/logs?k_dan={tk_kuni(_BAZA_VAQT)}&k_gacha={tk_kuni(_BAZA_VAQT)}", "tab-login", "k_")
st, H, _ = ol(C, "/logs?k_kim=etr_admin")
_kopt = re.findall(r'<option value="([^"]*)"', re.search(r'<select name="k_kim">(.*?)</select>', H, re.S).group(1)) if 'name="k_kim"' in H else []
check("K3 sana (Toshkent kuni) va «Foydalanuvchi» ro'yxati — korxona nomlari, begona yo'q",
      _kdh == _kd and len(_kd) == 70 and "ali" in _kopt and "begona_user" not in _kopt and 'value="etr_admin" selected' in H,
      (len(_kdh), len(_kd), _kopt))
st, H, _ = ol(CB, "/logs")
check("K4 B korxonasi — faqat o'z urinishlari", soni(H, "kirishSoni") == len(kutilgan_kirish(2)) and "10.0.0." not in H, soni(H, "kirishSoni"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Tahrir yozuvida — NIMA O'ZGARGANI (haqiqiy API)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def oxirgi_yozuv(entity, eid):
    s = SessionLocal()
    try:
        r = s.query(ActivityLog).filter(ActivityLog.company_id == 1, ActivityLog.entity_type == entity,
                                        ActivityLog.entity_id == eid).order_by(ActivityLog.id.desc()).first()
        return {"action": r.action, "old": r.old_value, "new": r.new_value, "label": r.entity_label, "id": r.id} if r else {}
    finally:
        s.close()


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


r = C.post("/api/production/product-types", json={"name": "ETR Dekor", "unit": "m²", "input_template": "quantity_only",
                                                  "pricing_formula": "unit_based"})
PT = (js(r) or {}).get("id")
r = C.post("/api/production/boms", json={"product_type_id": PT, "variant_name": "Standart", "batch_quantity": 1,
                                         "items": [{"inventory_id": KLEY, "quantity": 3}, {"inventory_id": TOSH, "quantity": 2}]})
BOM = (js(r) or {}).get("id")
r = C.put(f"/api/production/boms/{BOM}", json={"product_type_id": PT, "variant_name": "Standart", "batch_quantity": 1,
                                               "items": [{"inventory_id": KLEY, "quantity": 4}, {"inventory_id": TOSH, "quantity": 2}]})
j = oxirgi_yozuv("bom", BOM)
_y1 = (j.get("new") or "").split("\nO'zgardi: ")
check("D1 retsept: faqat material miqdori o'zgardi — qisqa tavsif bir xil, lekin «O'zgardi: ETR Kley: 3 → 4 kg» (boshqa narsa yo'q)",
      r.status_code == 200 and j.get("action") == "updated" and len(_y1) == 2 and _y1[0] == j.get("old")
      and _y1[1] == "ETR Kley: 3 → 4 kg", (r.status_code, j))
st, H, _ = ol(C, "/logs?tab=activity&a_q=Retsept&a_amal=updated")
_bq = [q for q in qatorlar(H, "tab-activity") if q[0] == j.get("id")]
check("D2 sahifada: «O'zgardi: ETR Kley: 3 → 4 kg» qatori, bir xil «eski → yangi» juftligi YO'Q",
      _bq and "O'zgardi: ETR Kley: 3 → 4 kg" in _bq[0][2] and "material → «Standart»" not in _bq[0][2], _bq)
r = C.put(f"/api/production/boms/{BOM}", json={"product_type_id": PT, "variant_name": "Kuchli", "batch_quantity": 2.5,
                                               "notes": "yangi izoh",
                                               "items": [{"inventory_id": KLEY, "quantity": 4, "scrap_factor_percent": 5},
                                                         {"inventory_id": PENO, "quantity": 0.5}]})
j = oxirgi_yozuv("bom", BOM)
_f2 = (j.get("new") or "").split("\nO'zgardi: ")[-1]
check("D3 retsept: nom, partiya (2,5), izoh, chiqindi %, material olib tashlandi / qo'shildi — HAMMASI ro'yxatda",
      r.status_code == 200 and all(x in _f2 for x in ("nomi: «Standart» → «Kuchli»", "partiya: 1 → 2,5 m²", "izoh o'zgardi",
                                                     "ETR Kley: chiqindi 0 → 5 %", "− ETR Tosh", "+ ETR Penoplast 0,5 blok"))
      and "«Kuchli»" in (j.get("new") or "") and "partiya 2.5" in (j.get("new") or ""), (r.status_code, _f2))
r = C.put(f"/api/production/boms/{BOM}", json={"product_type_id": PT, "variant_name": "Kuchli", "batch_quantity": 2.5,
                                               "notes": "yangi izoh",
                                               "items": [{"inventory_id": KLEY, "quantity": 4, "scrap_factor_percent": 5},
                                                         {"inventory_id": PENO, "quantity": 0.5}]})
j = oxirgi_yozuv("bom", BOM)
check("D4 retsept o'zgarishsiz saqlandi — «O'zgardi: hech narsa (o'sha holat qayta saqlandi)»",
      r.status_code == 200 and (j.get("new") or "").endswith("\nO'zgardi: hech narsa (o'sha holat qayta saqlandi)"), j)

_s = SessionLocal()
_prj = Project(company_id=1, client_name="ETR mijoz", project_name="ETR loyiha", total_budget=0, total_paid=0)
_u1 = Master(company_id=1, name="Usta Birinchi", phone="+998901110001")
_u2 = Master(company_id=1, name="Usta Ikkinchi", phone="+998901110002")
_s.add_all([_prj, _u1, _u2])
_s.commit()
PRJ, U1, U2 = _prj.id, _u1.id, _u2.id
_s.close()


def detal(nom, narx, miqdor, **kw):
    d = {"name": nom, "category": "panel", "width": 20, "thickness": 10, "quantity": miqdor, "unit_price": narx,
         "is_coated": False, "penoplast_id": PENO}
    d.update(kw)
    return d


r = C.post("/api/orders", json={"project_id": PRJ, "order_type": "product", "master_id": U1, "deadline": "2026-10-05T00:00:00",
                                "items": [detal("Karniz A", 10000, 3), detal("Panel B", 20000, 1)]}, params={"confirm_shortage": "true"})
OID = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
r = C.put(f"/api/orders/{OID}", json={"project_id": PRJ, "order_type": "product", "master_id": U2, "deadline": "2026-10-07T00:00:00",
                                      "items": [detal("Karniz A", 10000, 4), detal("Ustun C", 5000, 2)]},
          params={"confirm_shortage": "true"})
j = oxirgi_yozuv("order", OID)
_fo = (j.get("new") or "").split("\nO'zgardi: ")[-1]
check("D5 buyurtma: miqdor 3 → 4, detal olib tashlandi / qo'shildi, muddat, usta — «O'zgardi» da (jami o'zgarmagan — yo'q); "
      "eski qisqa tavsif saqlangan",
      r.status_code == 200 and j.get("action") == "updated" and (j.get("old") or "").startswith("Jami: 50 000 so'm")
      and all(x in _fo for x in ("Karniz A 20×10 (qoplamasiz): 3 → 4 ta", "− Panel B 20×10 (qoplamasiz) (1 ta)",
                                 "+ Ustun C 20×10 (qoplamasiz) (2 ta, 10 000 so'm)", "topshirish muddati: 05.10.2026 → 07.10.2026",
                                 "usta: Usta Birinchi → Usta Ikkinchi"))
      and "jami:" not in _fo, (r.status_code, j))
r = C.put(f"/api/orders/{OID}", json={"project_id": PRJ, "order_type": "product", "master_id": U2, "deadline": "2026-10-07T00:00:00",
                                      "items": [detal("Karniz A", 12500, 4), detal("Ustun C", 5000, 2)]},
          params={"confirm_shortage": "true"})
j = oxirgi_yozuv("order", OID)
_fo2 = (j.get("new") or "").split("\nO'zgardi: ")[-1]
check("D6 buyurtma: faqat narx o'zgardi — «Karniz A …: 40 000 → 50 000 so'm», «jami: 50 000 → 60 000 so'm»",
      r.status_code == 200 and "Karniz A 20×10 (qoplamasiz): 40 000 → 50 000 so'm" in _fo2 and "jami: 50 000 → 60 000 so'm" in _fo2
      and "usta:" not in _fo2 and "muddati" not in _fo2, (r.status_code, _fo2))
r = C.put(f"/api/orders/{OID}", json={"project_id": PRJ, "order_type": "product", "master_id": U2,
                                      "items": [detal("Karniz A", 12500, 4), detal("Ustun C", 5000, 2)]},
          params={"confirm_shortage": "true"})
j = oxirgi_yozuv("order", OID)
check("D7 buyurtma o'zgarishsiz saqlandi — «hech narsa»", r.status_code == 200
      and (j.get("new") or "").endswith("\nO'zgardi: hech narsa (o'sha holat qayta saqlandi)"), j)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxiradan tiklash — yozuv korxona bilan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = CP.post("/tiklash", files={"file": ("etr_zaxira.json", json.dumps({"tables": {}, "company_id": 3}).encode(), "application/json")},
            data={"replace": "", "confirm": ""})
_s = SessionLocal()
try:
    _z = [(a.action, a.company_id, a.entity_label, a.new_value) for a in
          _s.query(ActivityLog).filter(ActivityLog.entity_type == "system").all()]
finally:
    _s.close()
st, H, _ = ol(CP, "/logs?tab=activity")
check("Z1 bo'sh korxonaga tiklash — jurnalga yozildi (korxona 3, `backup_restored`, «Zaxira fayli «etr_zaxira.json»»), sahifada "
      "«— zaxiradan tiklandi»", r.status_code == 200 and _z == [("backup_restored", 3, "Zaxira fayli «etr_zaxira.json»", "qo'shib tiklandi")]
      and "Zaxira fayli «etr_zaxira.json» — zaxiradan tiklandi" in re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", bolim(H, "tab-activity")))),
      (r.status_code, r.text[:200], _z))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Ombor API — «Yana yuklash» uchun")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def baza_harakat(f=None, cid=1):
    s = SessionLocal()
    try:
        rows = [(r.id, r.created_at, r.inventory_id, r.movement_type, float(r.quantity), r.item_name, r.unit or "")
                for r in s.query(InventoryMovement).filter(InventoryMovement.company_id == cid).all()]
    finally:
        s.close()
    if f:
        rows = [r for r in rows if f(r)]
    rows.sort(key=lambda r: (r[1], r[0]), reverse=True)
    return rows


_bh = baza_harakat()
_api_ids, _off, _jamilar = [], 0, set()
for _ in range(10):
    st, t, hd = ol(C, f"/api/inventory/movements?limit=100&offset={_off}")
    _r = json.loads(t) if st == 200 else []
    _jamilar.add(hd.get("x-jami"))
    _api_ids += [x["id"] for x in _r]
    _off += len(_r)
    if len(_r) < 100:
        break
check(f"A1 harakatlar: `X-Jami` = baza ({len(_bh)}), `offset` bilan hamma sahifa — har biri bir marta, tartib = baza "
      "(bir xil vaqtli 25 ta ham)", _api_ids == [r[0] for r in _bh] and _jamilar == {str(len(_bh))}, (len(_api_ids), len(_bh), _jamilar))
st, t, hd = ol(C, f"/api/inventory/movements?item_id={TOSH}&movement_type=out&limit=10&offset=20")
_kt = [r[0] for r in baza_harakat(lambda r: r[2] == TOSH and r[3] == "out")]
check("A2 material + tur filtri bilan: `X-Jami` = 25, offset 20 → oxirgi 5 ta", st == 200 and hd.get("x-jami") == "25"
      and [x["id"] for x in json.loads(t)] == _kt[20:25], (st, hd.get("x-jami")))
_xl = []
for _u in ("/api/inventory/movements?limit=0", "/api/inventory/movements?limit=501", "/api/inventory/movements?offset=-1",
           "/api/inventory/purchases?limit=0", "/api/inventory/purchases?offset=-5"):
    st, t, _ = ol(C, _u)
    if st != 422:
        _xl.append((_u, st))
check("A3 noto'g'ri `limit` / `offset` — 422 (ilgari cheklovsiz)", not _xl, _xl)
_d1, _d2 = "2026-09-18", "2026-09-19"
st, t, _ = ol(C, f"/api/inventory/movements/jami?date_from={_d1}&date_to={_d2}")
_jb = json.loads(t) if st == 200 else {}
_kb = {}
for r_ in baza_harakat(lambda r: _d1 <= tk_kuni(r[1]) <= _d2):
    _k = _kb.setdefault(r_[5], {"in": 0.0, "out": 0.0, "soni": 0})
    _k[r_[3]] += r_[4]
    _k["soni"] += 1
check("A4 davr jami (`/api/inventory/movements/jami`) — HAMMA mos harakatlardan (Toshkent kunlari), material bo'yicha = baza",
      st == 200 and {m["name"]: {"in": m["in"], "out": m["out"], "soni": m["soni"]} for m in _jb.get("materiallar", [])} ==
      {k: {"in": round(v["in"], 6), "out": round(v["out"], 6), "soni": v["soni"]} for k, v in _kb.items()}
      and _jb.get("jami") == sum(v["soni"] for v in _kb.values()) and "ETR B Kley" not in t, (_jb, _kb))
st, t, hd = ol(C, "/api/inventory/purchases?limit=100&offset=0")
_p1 = json.loads(t) if st == 200 else []
st2, t2, hd2 = ol(C, f"/api/inventory/purchases?limit=100&offset={hd.get('x-keyingi')}")
_p2 = json.loads(t2) if st2 == 200 else []
_s = SessionLocal()
try:
    _kp = [p.id for p in sorted(_s.query(InventoryPurchase).join(Inventory, Inventory.id == InventoryPurchase.inventory_id)
                                .filter(Inventory.company_id == 1).all(), key=lambda p: (p.purchased_at, p.id), reverse=True)]
finally:
    _s.close()
_rc_ids = [x["id"] for x in _p1 if x["receipt_id"]]
check("A5 xaridlar: 1-sahifa 100 + «Kirim» hujjatining qolgan 5 qatori (hujjat bo'linmaydi), `X-Keyingi` = 105, `X-Jami` = 125; "
      "2-sahifa — qolgan 20, takror / tushib qolish yo'q",
      st == 200 and len(_p1) == 105 and len(_rc_ids) == 10 and hd.get("x-keyingi") == "105" and hd.get("x-jami") == str(len(_kp))
      and [x["id"] for x in _p1 + _p2] == _kp and hd2.get("x-keyingi") == str(len(_kp)), (len(_p1), len(_rc_ids), hd.get("x-keyingi"),
                                                                                            hd.get("x-jami"), len(_p2)))
st, t, hd = ol(CB, "/api/inventory/purchases")
check("A6 korxona chegarasi: B — faqat o'z xaridi (1), `X-Jami` 1", st == 200 and len(json.loads(t)) == 1 and hd.get("x-jami") == "1", t[:200])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Brauzer — ombor oynalari, jurnal yorlig'i")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
check("B0 Python `playwright` bor", PW_BOR, _pw_x)

import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


port = _port()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
th = threading.Thread(target=server.run, daemon=True)
th.start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
B = f"http://127.0.0.1:{port}"
pw_ctx = br = None
if PW_BOR and server.started:
    pw_ctx = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*", "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        br = None
        _pw_x = f"{type(_e).__name__}: {_e}"
check("B1 lokal server va Chromium", bool(server.started and br), _pw_x)


def kontekst(w=1280, h=900, tel=False):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=tel, has_touch=tel,
                         timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|cdn\.jsdelivr\.net|unpkg\.com)/.*"),
              lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    try:
        pg.goto(B + "/login")
        pg.fill("input[name=username]", ADMIN)
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
    except Exception as ex:                # noqa: BLE001
        JS_XATO_AMAL.append(("login", f"{type(ex).__name__}: {str(ex)[:160]}"))
    return ctx, pg


def jsq(pg, kod, arg=None):
    try:
        return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
    except Exception as ex:                # noqa: BLE001
        return {"js_xato": f"{type(ex).__name__}: {str(ex)[:300]}"}


def bos(pg, sel, ms=6000):
    """Brauzer amali — xato testni QULATMAYDI (keyingi tekshiruv yiqiladi)."""
    try:
        pg.click(sel, timeout=ms)
        return True
    except Exception as ex:                # noqa: BLE001
        JS_XATO_AMAL.append((sel, f"{type(ex).__name__}: {str(ex)[:160]}"))
        return False


def bor(pg, url):
    try:
        pg.goto(B + url, wait_until="networkidle")
        return True
    except Exception as ex:                # noqa: BLE001
        JS_XATO_AMAL.append((url, f"{type(ex).__name__}: {str(ex)[:160]}"))
        return False


def kut(pg, kod, ms=6000):
    try:
        pg.wait_for_function(kod, timeout=ms)
        return True
    except Exception:                      # noqa: BLE001
        return False


JS_XATO = []
JS_XATO_AMAL = []
MV_HOLAT = r"""() => ({
  ochiq: getComputedStyle(document.getElementById('movementsModal')).display !== 'none',
  sarlavha: document.getElementById('mvSarlavha')?.textContent.trim(),
  material: getComputedStyle(document.getElementById('mvMaterial')).display !== 'none' ? document.getElementById('mvMaterialNomi').textContent : null,
  bosilgan: [...document.querySelectorAll('#mvFiltr .mv-f')].filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.tur),
  yana: document.querySelector('#mvYana')?.textContent.replace(/\s+/g, ' ').trim() || null,
  tugma: !!document.querySelector('#mvYana button'),
  idlar: (typeof mvRows !== 'undefined' ? mvRows : []).map(r => r.id),
  guruhlar: document.querySelectorAll('#mv-list .mv-order-row').length,
  davr: document.getElementById('mvDavrJami')?.textContent.replace(/\s+/g, ' ').trim() || null
})"""
if br:
    CTX, PG = kontekst()
    PG.on("pageerror", lambda e: JS_XATO.append(("1280", str(e)[:200])))
    bor(PG, "/inventory")
    _tb = jsq(PG, """() => [...document.querySelectorAll('.mat-row .act-btn.hist')].map(b => b.dataset.name)""")
    check("B2 har material qatorida «Tarix» tugmasi", isinstance(_tb, list) and {"ETR Kley", "ETR Tosh", "ETR Penoplast"} <= set(_tb), _tb)
    jsq(PG, """() => { const b = [...document.querySelectorAll('.mat-row .act-btn.hist')].find(x => x.dataset.name === 'ETR Tosh'); b.click(); }""")
    kut(PG, "() => document.querySelector('#mvYana')")
    _h1 = jsq(PG, MV_HOLAT)
    _kt = [r[0] for r in baza_harakat(lambda r: r[2] == TOSH)]
    check("B3 «Tarix» (ETR Tosh): oyna — «Tarix — ETR Tosh», «Faqat shu material», faqat shu materialning 25 harakati, "
          "«Ko'rsatilgan: 25 / 25», «Yana» tugmasi yo'q",
          isinstance(_h1, dict) and _h1.get("ochiq") and _h1.get("sarlavha") == "Tarix — ETR Tosh" and _h1.get("material") == "ETR Tosh"
          and _h1.get("idlar") == _kt and _h1.get("yana") == "Ko'rsatilgan: 25 / 25 ta harakat" and not _h1.get("tugma"), _h1)
    bos(PG, "#mvFiltr .mv-f[data-tur=in]")
    kut(PG, "() => document.querySelector('#mvFiltr .mv-f[data-tur=in]').getAttribute('aria-pressed') === 'true' && (document.querySelector('#mv-list').textContent.includes('yo\\'q') || document.querySelector('#mvYana'))")
    PG.wait_for_timeout(300)
    _h2 = jsq(PG, MV_HOLAT)
    check("B4 «Faqat kirim» bosildi — tugma tanlangan (`aria-pressed`), material filtri SAQLANDI (Tosh kirimi yo'q → «Harakatlar yo'q»)",
          isinstance(_h2, dict) and _h2.get("bosilgan") == ["in"] and _h2.get("material") == "ETR Tosh" and _h2.get("idlar") == []
          and "Harakatlar yo'q" in (jsq(PG, "() => document.getElementById('mv-list').textContent") or ""), _h2)
    bos(PG, "#mvMaterial button")
    kut(PG, "() => document.querySelector('#mvYana')")
    PG.wait_for_timeout(300)
    _h3 = jsq(PG, MV_HOLAT)
    _kh_all = [r[0] for r in baza_harakat()]
    _yana_n = min(len(_kh_all) - 100, 100)
    check(f"B5 material filtri olib tashlandi (✕) — «Ombor harakatlari», «Barchasi» tanlangan, 100 ta + «Ko'rsatilgan: 100 / N», "
          f"«Yana {_yana_n} ta yuklash»",
          isinstance(_h3, dict) and _h3.get("sarlavha") == "Ombor harakatlari" and _h3.get("material") is None and _h3.get("bosilgan") == [""]
          and _h3.get("idlar") == _kh_all[:100] and _h3.get("yana", "").startswith(f"Ko'rsatilgan: 100 / {len(_kh_all)} ta harakat")
          and f"Yana {_yana_n} ta yuklash" in (_h3.get("yana") or "") and _h3.get("tugma"),
          (_h3 if not isinstance(_h3, dict) else {k: v for k, v in _h3.items() if k != "idlar"}, len(_kh_all)))
    bos(PG, "#mvYana button")
    kut(PG, f"() => (typeof mvRows !== 'undefined') && mvRows.length === {len(_kh_all)}")
    PG.wait_for_timeout(300)
    _h4 = jsq(PG, MV_HOLAT)
    check(f"B6 «Yana yuklash» — qolgan {len(_kh_all) - 100} ta QO'SHILDI (takrorsiz, tartib = baza), «Ko'rsatilgan: N / N», tugma yo'qoldi",
          isinstance(_h4, dict) and _h4.get("idlar") == _kh_all and _h4.get("yana") == f"Ko'rsatilgan: {len(_kh_all)} / {len(_kh_all)} ta harakat"
          and not _h4.get("tugma"), {k: v for k, v in (_h4 or {}).items() if k != "idlar"} if isinstance(_h4, dict) else _h4)
    jsq(PG, "() => { document.getElementById('mv-date-from').value = '2026-09-18'; document.getElementById('mv-date-to').value = '2026-09-19'; }")
    jsq(PG, "() => loadMovements(mvCurType)")
    kut(PG, "() => document.getElementById('mvDavrJami')")
    PG.wait_for_timeout(300)
    _h5 = jsq(PG, MV_HOLAT)
    _kd = baza_harakat(lambda r: "2026-09-18" <= tk_kuni(r[1]) <= "2026-09-19")
    _kin = sum(r[4] for r in _kd if r[3] == "in" and r[5] == "ETR Kley")
    _kout = sum(r[4] for r in _kd if r[3] == "out" and r[5] == "ETR Kley")
    check("B7 sana oralig'i: «Tanlangan davr — jami (N ta harakat)» SERVERDAN (hamma mos harakat), ETR Kley +kirim / −chiqim = baza",
          isinstance(_h5, dict) and f"Tanlangan davr — jami ({len(_kd)} ta harakat)" in (_h5.get("davr") or "")
          and ("+" + crud.audit_son(_kin)) in (_h5.get("davr") or "") and ("−" + crud.audit_son(_kout)) in (_h5.get("davr") or "")
          and _h5.get("idlar") == [r[0] for r in _kd][:100], (_h5.get("davr") if isinstance(_h5, dict) else _h5, len(_kd), _kin, _kout))
    jsq(PG, "() => closeMovements()")
    # Xaridlar tarixi
    jsq(PG, "() => openPurchaseHistory()")
    kut(PG, "() => document.querySelector('#phYana')")
    PG.wait_for_timeout(300)
    _p = jsq(PG, """() => ({yana: document.querySelector('#phYana')?.textContent.replace(/\\s+/g, ' ').trim(),
        tugma: !!document.querySelector('#phYana button'), soni: phAllPurchases.length,
        hujjat: [...document.querySelectorAll('#hist-list .mv-order-row .mv-order-count')].map(e => e.textContent.trim())})""")
    check("B8 «Xaridlar tarixi»: 105 ta (100 + hujjat qolgani), «Kirim» hujjati to'liq — «10 ta material», «Ko'rsatilgan: 105 / 125»",
          isinstance(_p, dict) and _p.get("soni") == 105 and _p.get("hujjat") == ["10 ta material →"]
          and (_p.get("yana") or "").startswith("Ko'rsatilgan: 105 / 125 ta xarid") and _p.get("tugma"), _p)
    bos(PG, "#phYana button")
    kut(PG, "() => phAllPurchases.length === 125")
    PG.wait_for_timeout(300)
    _p2 = jsq(PG, """() => ({yana: document.querySelector('#phYana')?.textContent.replace(/\\s+/g, ' ').trim(),
        tugma: !!document.querySelector('#phYana button'), ids: phAllPurchases.map(p => p.id)})""")
    check("B9 «Yana yuklash» — 125 / 125, tartib = baza, takror yo'q, tugma yo'qoldi",
          isinstance(_p2, dict) and _p2.get("ids") == _kp and _p2.get("yana") == "Ko'rsatilgan: 125 / 125 ta xarid" and not _p2.get("tugma"),
          {k: v for k, v in (_p2 or {}).items() if k != "ids"} if isinstance(_p2, dict) else _p2)
    jsq(PG, "() => closePurchaseHistory()")
    # Jurnal: yorliq manzilda, forma yuborilganda shu yorliq qoladi
    bor(PG, "/logs")
    bos(PG, ".log-tab[data-tab=activity]")
    _url1 = PG.url
    try:
        PG.select_option("select[name=a_kim]", "Ali Usta", timeout=6000)
    except Exception as _ex:               # noqa: BLE001
        JS_XATO_AMAL.append(("a_kim", str(_ex)[:160]))
    bos(PG, "#auditFiltr button[type=submit]")
    try:
        PG.wait_for_load_state("networkidle")
    except Exception:                      # noqa: BLE001
        pass
    _l = jsq(PG, """() => ({url: location.href, ochiq: getComputedStyle(document.getElementById('tab-activity')).display,
        kirish: getComputedStyle(document.getElementById('tab-login')).display,
        kimlar: [...document.querySelectorAll('#auditRoyxati .jr-qator')].map(q => q.textContent.includes('Ali Usta')),
        soni: document.getElementById('auditSoni').textContent})""")
    check("B10 jurnal: yorliq bosilganda manzilda `tab=activity`; «Kim» tanlab «Ko'rsatish» — sahifa shu yorliqda qoldi, faqat Ali Usta",
          "tab=activity" in _url1 and isinstance(_l, dict) and "a_kim=Ali+Usta" in _l.get("url", "") and _l.get("ochiq") == "block"
          and _l.get("kirish") == "none" and _l.get("kimlar") and all(_l.get("kimlar")) and "filtr bo'yicha" in _l.get("soni", ""),
          (_url1, _l))
    bos(PG, "#auditSahifa a[rel=next]")
    try:
        PG.wait_for_load_state("networkidle")
    except Exception:                      # noqa: BLE001
        pass
    _l2 = jsq(PG, """() => ({url: location.href, ochiq: getComputedStyle(document.getElementById('tab-activity')).display,
        sahifa: document.querySelector('#auditSahifa span')?.textContent.replace(/\\s+/g, ' ')})""")
    check("B11 «Eskiroqlar →» — 2-sahifa, yorliq va filtr saqlandi",
          isinstance(_l2, dict) and "a_sahifa=2" in _l2.get("url", "") and "a_kim=Ali+Usta" in _l2.get("url", "")
          and _l2.get("ochiq") == "block" and (_l2.get("sahifa") or "").startswith("51–"), _l2)
    CTX.close()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Telefon 390 px")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TASHQARI_JS = r"""(sel) => {
  const vw = document.documentElement.clientWidth;
  const t = [...document.querySelectorAll(sel)].filter(e => e.offsetParent !== null).map(e => { const r = e.getBoundingClientRect();
    return {cls: (e.className || e.tagName).toString().slice(0, 40), l: Math.round(r.left), r: Math.round(r.right)}; })
    .filter(x => x.l < -1 || x.r > vw + 1);
  return {vw, sahifa: document.documentElement.scrollWidth, tashqari: t.slice(0, 6)};
}"""
if br:
    CTX, PG = kontekst(390, 844, True)
    PG.on("pageerror", lambda e: JS_XATO.append(("390", str(e)[:200])))
    bor(PG, "/logs?tab=activity&a_kim=Ali+Usta")
    PG.wait_for_timeout(400)
    _t1 = jsq(PG, TASHQARI_JS, "#tab-activity .jr-filtr *, #tab-activity .jr-sahifa *, #tab-activity .jr-qator")
    _t1b = jsq(PG, """() => [...document.querySelectorAll('#auditSahifa a, #auditFiltr button, #auditFiltr select, #auditFiltr input:not([type=hidden])')]
        .map(e => Math.round(e.getBoundingClientRect().height))""")
    check("T1 390 px jurnal: filtr va sahifa chizig'i ekranda, sahifa kengaymaydi, tugma / maydon balandligi ≥ 34 px",
          isinstance(_t1, dict) and not _t1.get("tashqari") and _t1.get("sahifa") <= _t1.get("vw") and isinstance(_t1b, list) and _t1b
          and min(_t1b) >= 34, (_t1, _t1b))
    bor(PG, "/inventory")
    jsq(PG, """() => { const b = [...document.querySelectorAll('.mat-row .act-btn.hist')].find(x => x.dataset.name === 'ETR Kley'); b.click(); }""")
    kut(PG, "() => document.querySelector('#mvYana')")
    PG.wait_for_timeout(400)
    _t2 = jsq(PG, TASHQARI_JS, "#movementsModal .mv-material *, #mvFiltr *, #mvYana *, #mv-list .mv-order-row")
    _t3 = jsq(PG, TASHQARI_JS, ".mat-row .mat-actions .act-btn")
    check("T2 390 px ombor: «Tarix» oynasi (material belgisi, filtr, «Yana yuklash») va qatordagi tugmalar ekranda",
          isinstance(_t2, dict) and not _t2.get("tashqari") and isinstance(_t3, dict) and not _t3.get("tashqari")
          and _t3.get("sahifa") <= _t3.get("vw"), (_t2, _t3))
    CTX.close()
if br:
    br.close()
if pw_ctx:
    pw_ctx.stop()
server.should_exit = True

section("X. Xatolar")
check("X1 brauzerda JS xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])
check("X2 serverda 5xx yo'q", not XATO5, XATO5[:5])
check("X3 brauzer amallari (bosish / ochish) bajarildi — element topilmadi / vaqt tugadi YO'Q", not JS_XATO_AMAL, JS_XATO_AMAL[:5])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
