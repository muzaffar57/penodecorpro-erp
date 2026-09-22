#!/usr/bin/env python3
"""
test_ombor_kpi_loy.py — K35-1 darvozasi (kech36, 2026-09-23).

NIMA UCHUN KERAK (jonli `web-sinov` da O'LCHANGAN, kech35 va kech36)
---------------------------------------------------------------------
Omborxona sahifasi (`/inventory`) KPI kartochkasi "Kam qolganlar 1 ta" deb
ko'rsatardi (`/api/inventory/kpi` → `low_count` 1), qator holati esa qizil
"Tugagan" edi — sababi yagona: `Tayyor loy (Oq marmar)` (qoldiq 0, min 0).
Bir vaqtning o'zida bosh sahifa "Barcha xomashyo yetarli", qo'ng'iroqcha
bo'sh, Telegram "kam qoldi" ro'yxati (`crud.get_low_stock_items`) ham uni
chiqarmasdi. Kodda uch joyda izoh bilan yozilgan qoida: "Tayyor loy (...)"
— buyurtmalardan ORTGAN, avtomatik yaratiladigan zaxira
(`services.get_or_create_loy_stock`), sotib olinadigan xomashyo EMAS; u
odatda 0 / 0 turadi va bu me'yor.

Tuzatish (kech36):
  * `services.get_inventory_kpi` — "Tayyor loy (" bilan boshlanadigan
    pozitsiya `low_count` ga sanalmaydi; `low_count` ==
    `len(crud.get_low_stock_items(...))`.
  * `templates/inventory.html` — Tayyor loy qatori: qoldiq ≤ 0 → neytral
    "Bo'sh" (`data-status="neutral"`), aks holda "Yetarli"; hech qachon
    "Tugagan" / "Kam!" emas. Guruhlash ham o'sha qoida bilan.
  * `services.get_notifications` (qo'ng'iroqcha) — `'Tayyor loy%'` (qavssiz)
    o'rniga o'sha yagona qoida: foydalanuvchi o'zi yaratgan "Tayyor loy"
    nomli ODDIY material tugasa, endi Telegram kabi u ham ogohlantiradi.

Tayyor loy fiksturasi HAQIQIY generator (`get_or_create_loy_stock`) bilan
yaratiladi — nom shakli ishlab chiqarishdagi bilan aynan bir xil bo'lishi uchun.

REJIMLAR
--------
* Odatiy (SQLite, `hammasi.sh`).
* `PG_URL` berilsa — har ishga YANGI PostgreSQL bazasi.

ISHGA TUSHIRISH
---------------
    python3 tools/test_ombor_kpi_loy.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_ombor_kpi_loy.py
"""
import os
import re
import sys
import html
import types
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "ombor_kpi_loy_test"
_DB = os.path.join(tempfile.gettempdir(), "ombor_kpi_loy_test.db")

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
# Xabar tarmoqqa chiqmaydi — `main._send_telegram` yozib oluvchi bilan almashtiriladi.
TG = []


def _yozib_ol(text, company_id=None, *a, **k):
    TG.append((company_id, str(text)))


main._send_telegram = _yozib_ol


# ------------------------------------------------------------------ foydalanuvchi
db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "OK_admin", "Parol123!", UserRole.ADMIN, "OK", company_id=1)

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "OK_admin", "password": "Parol123!"},
          follow_redirects=False)
if _lr.status_code != 302:
    print(f"LOGIN BO'LMADI: {_lr.status_code} {getattr(_lr, 'text', '')[:200]}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)


def _kpi():
    return js(req(C, "get", "/api/inventory/kpi")) or {}


section("0. Boshlang'ich holat (fikstura oldidan)")
_k0 = _kpi()
B_LOW = _k0.get("low_count")
B_TOTAL = _k0.get("total_items")
check("boshlang'ich /api/inventory/kpi o'qildi", isinstance(B_LOW, int) and isinstance(B_TOTAL, int),
      str(_k0)[:200])
B_LOW = B_LOW if isinstance(B_LOW, int) else 0
B_TOTAL = B_TOTAL if isinstance(B_TOTAL, int) else 0

# Tayyor loy zaxiralari (HAQIQIY generator — nom shakli ishlab chiqarishdagidek)
L0 = "KPI_OQ"          # 0 / 0 — me'yor: sanalmaydi, "Bo'sh"
L1 = "KPI_KUL"         # 5 / 0 — "Yetarli"
L2 = "KPI_CHEGARA"     # 3 / 10 — foydalanuvchi chegara qo'ygan: baribir sanalmaydi (Telegram kabi)
# Oddiy materiallar (API orqali)
M0 = "KPI_ODDIY_BOSH"          # 0 / 0 — sanaladi, "Tugagan", qo'ng'iroqcha "qolmadi"
M1 = "KPI_ODDIY_KAM"           # 1 / 5 — sanaladi, "Kam!"
M2 = "KPI_ODDIY_YETARLI"       # 50 / 5 — sanalmaydi
T1 = "Tayyor loy"              # qavssiz, 0 / 5 — generator yasamaydi: ODDIY material, sanaladi
T3 = "AAA Tayyor loy (nusxa)"  # "Tayyor loy (" nomning BOSHIDA emas — oddiy, sanaladi.
                               # "AAA" — har qanday collation da (C / en_US) oddiy guruhning BOSHIDA turadi
YH = "KPI_YASHIRIN_BOSH"       # 0 / 0, yashirilgan (is_deleted) — sanalmaydi (mavjud qoida)
T4 = "Tayyor loyqa KPI"        # "Tayyor loy" bilan boshlanadi, qavssiz — ODDIY; 10 / 0, tez sarflanadi →
                               # qo'ng'iroqcha "N kundan keyin tugaydi" bashorati (ikkinchi so'rov)

ODDIY_SANALADI = (M0, M1, T1, T3)
ODDIY_HAMMASI = (M0, M1, M2, T1, T3, T4)


def loy_nomi(r):
    return f"Tayyor loy ({r})"


def loy_yarat(retsept_nomi, qoldiq, minimal):
    """`services.get_or_create_loy_stock` — soxta retsept (faqat `name`, `company_id`)."""
    s = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            st = services.get_or_create_loy_stock(
                s, types.SimpleNamespace(name=retsept_nomi, company_id=1), company_id=1)
        if st is None:
            return None
        s.query(Inventory).filter(Inventory.id == st.id).update(
            {"stock_quantity": qoldiq, "min_stock": minimal}, synchronize_session=False)
        s.commit()
        return st.id
    except Exception as e:                 # noqa: BLE001
        print(f"    loy_yarat xato: {type(e).__name__}: {e}")
        s.rollback()
        return None
    finally:
        s.close()


def yarat(nom, qoldiq, minimal):
    r = req(C, "post", "/api/inventory",
            json={"item_name": nom, "unit": "kg", "stock_quantity": qoldiq, "min_stock": minimal})
    d = js(r) or {}
    return r.status_code, d.get("id")


section("1. Fikstura")
IDS = {}
for _r, _q, _m in ((L0, 0, 0), (L1, 5, 0), (L2, 3, 10)):
    IDS[_r] = loy_yarat(_r, _q, _m)
    check(f"Tayyor loy zaxirasi yaratildi (generator): {loy_nomi(_r)} {_q} / {_m}", bool(IDS[_r]))
for _n, _q, _m in ((M0, 0, 0), (M1, 1, 5), (M2, 50, 5), (T1, 0, 5), (T3, 0, 0), (YH, 0, 0), (T4, 10, 0)):
    _st, IDS[_n] = yarat(_n, _q, _m)
    check(f"oddiy material yaratildi: {_n} {_q} / {_m}", _st == 200 and bool(IDS[_n]), f"status {_st}")

_s = SessionLocal()
try:
    if IDS.get(YH):
        _s.query(Inventory).filter(Inventory.id == IDS[YH]).update(
            {"is_deleted": True}, synchronize_session=False)
        _s.commit()
    # Sarf tarixi (so'nggi 14 kun) — qo'ng'iroqcha bashorati uchun: T4 (oddiy) 100 chiqim →
    # ~1 kun qoldi (chiqishi SHART); L1 (Tayyor loy 5 kg) 70 chiqim → ~1 kun (chiqmasligi SHART).
    if IDS.get(T4):
        crud.log_movement(_s, IDS[T4], T4, movement_type="out", quantity=100, unit="kg", reason="KPI sinov")
    if IDS.get(L1):
        crud.log_movement(_s, IDS[L1], loy_nomi(L1), movement_type="out", quantity=70, unit="kg",
                          reason="KPI sinov")
    _s.commit()
    _nomlar = {i.id: i.item_name for i in _s.query(Inventory).filter(
        Inventory.id.in_([v for v in IDS.values() if v])).all()}
finally:
    _s.close()
check("generator nomi aynan 'Tayyor loy (KPI_OQ)' shaklida (ishlab chiqarishdagidek)",
      _nomlar.get(IDS.get(L0)) == loy_nomi(L0), str(_nomlar.get(IDS.get(L0))))

section("2. /api/inventory/kpi — Omborxona KPI")
_k1 = _kpi()
_low = _k1.get("low_count")
check("low_count == boshlang'ich + 4 (M0, M1, T1, T3) — Tayyor loy (L0, L1, L2), yetarli M2, yashirin YH sanalmaydi",
      _low == B_LOW + 4, f"{_low} (boshlang'ich {B_LOW})")
check("total_items == boshlang'ich + 9 (yashirin YH sanalmaydi — mavjud qoida)",
      _k1.get("total_items") == B_TOTAL + 9, f"{_k1.get('total_items')} (boshlang'ich {B_TOTAL})")

section("3. KPI == Telegram 'kam qoldi' ro'yxati (crud.get_low_stock_items)")
_d = SessionLocal()
_gl = safe(crud.get_low_stock_items, _d, company_id=1)
_gn = [getattr(x, "item_name", None) for x in _gl] if isinstance(_gl, list) else []
_d.close()
check("get_low_stock_items ro'yxat qaytardi", isinstance(_gl, list), str(_gl)[:160])
check("low_count == len(get_low_stock_items) — KPI va Telegram bir xil sanaydi",
      isinstance(_gl, list) and _low == len(_gl), f"KPI {_low}, Telegram {len(_gn)}: {_gn}")
check("Telegram ro'yxatida M0, M1, T1, T3 BOR; Tayyor loy zaxiralari YO'Q",
      all(n in _gn for n in ODDIY_SANALADI) and not any(n.startswith("Tayyor loy (") for n in _gn if n),
      str(_gn)[:220])

section("4. /inventory sahifasi — KPI kartochkasi va qator holati")
_pr = req(C, "get", "/inventory")
_ph = getattr(_pr, "text", "") or ""
check("/inventory → 200", _pr.status_code == 200, f"{_pr.status_code} {_ph[:160]}")
_km = re.search(r"Kam qolganlar</div>\s*<div class=\"stat-val\">\s*(\d+) ta", _ph)
check("KPI kartochkasi 'Kam qolganlar N ta' — N == /api/inventory/kpi low_count",
      bool(_km) and int(_km.group(1)) == _low, f"{_km.group(1) if _km else 'topilmadi'} vs {_low}")

QATOR = {}
_bloklar = _ph.split('<div class="mat-row"')[1:]
for _b in _bloklar:
    _nm = re.search(r'data-name="([^"]*)"', _b)
    _stt = re.search(r'data-status="([^"]*)"', _b)
    _bd = re.search(r'<span class="stat-badge ([^"]*)">([^<]*)</span>', _b)
    _cat = re.search(r'<span class="cat-badge [^"]*"[^>]*>([^<]*)</span>', _b)
    _fill = re.search(r'class="stock-fill[^"]*" style="width:([^%"]*)%', _b)
    if _nm:
        QATOR[html.unescape(_nm.group(1))] = {
            "status": _stt.group(1) if _stt else None,
            "badge": _bd.group(1) if _bd else None,
            "label": html.unescape(_bd.group(2)).strip() if _bd else None,
            "cat": html.unescape(_cat.group(1)).strip() if _cat else None,
            "fill": _fill.group(1).strip() if _fill else None,
        }
check("sahifadagi qatorlar o'qildi (fikstura qatorlari bor)",
      all(n.lower() in QATOR for n in (loy_nomi(L0), loy_nomi(L1), loy_nomi(L2)) + ODDIY_HAMMASI),
      str(sorted(QATOR))[:220])


def qator(nom):
    return QATOR.get(nom.lower()) or {}


_q = qator(loy_nomi(L0))
check("L0 Tayyor loy 0 / 0 — neytral 'Bo'sh' (data-status neutral, stat-badge neutral), 'Tugagan' EMAS",
      _q.get("status") == "neutral" and _q.get("badge") == "neutral" and _q.get("label") == "Bo'sh", str(_q))
check("L0 zaxira chizig'i bo'sh (width 0%) — to'liq qizil emas", _q.get("fill") == "0", str(_q))
check("L0 kategoriya belgisi 'Tayyor loy'", _q.get("cat") == "Tayyor loy", str(_q))
_q = qator(loy_nomi(L1))
check("L1 Tayyor loy 5 / 0 — 'Yetarli' (ok)",
      _q.get("status") == "ok" and _q.get("badge") == "ok" and _q.get("label") == "Yetarli", str(_q))
_q = qator(loy_nomi(L2))
check("L2 Tayyor loy 3 / 10 — 'Yetarli' (ok): KPI va Telegram uni sanamaydi, qator ham qizil emas",
      _q.get("status") == "ok" and _q.get("badge") == "ok", str(_q))
_q = qator(M0)
check("M0 oddiy 0 / 0 — 'Tugagan' (danger) — avvalgidek",
      _q.get("status") == "danger" and _q.get("badge") == "danger" and _q.get("label") == "Tugagan", str(_q))
_q = qator(M1)
check("M1 oddiy 1 / 5 — 'Kam!' (danger)",
      _q.get("status") == "danger" and _q.get("label") == "Kam!", str(_q))
_q = qator(M2)
check("M2 oddiy 50 / 5 — 'Yetarli' (ok)", _q.get("status") == "ok" and _q.get("label") == "Yetarli", str(_q))
_q = qator(T1)
check("T1 'Tayyor loy' (qavssiz, oddiy) 0 / 5 — 'Tugagan' (danger), kategoriya 'Tayyor loy' EMAS",
      _q.get("status") == "danger" and _q.get("label") == "Tugagan" and _q.get("cat") != "Tayyor loy", str(_q))
_q = qator(T3)
check("T3 'AAA Tayyor loy (nusxa)' 0 / 0 — 'Tugagan' (danger), kategoriya 'Tayyor loy' EMAS",
      _q.get("status") == "danger" and _q.get("label") == "Tugagan" and _q.get("cat") != "Tayyor loy", str(_q))
_q = qator(T4)
check("T4 'Tayyor loyqa KPI' (oddiy) 10 / 0 — 'Yetarli' (ok), kategoriya 'Tayyor loy' EMAS",
      _q.get("status") == "ok" and _q.get("cat") != "Tayyor loy", str(_q))
check("yashirin YH sahifada YO'Q (mavjud qoida)", YH.lower() not in QATOR, str(sorted(QATOR))[:160])

_danger = _ph.count('<span class="stat-badge danger">')
check("sahifadagi qizil (danger) holatlar soni == KPI 'Kam qolganlar' (sahifa ichidagi o'z hisoblagichi)",
      _danger == _low, f"danger {_danger}, KPI {_low}")

_tartib = [html.unescape(re.search(r'data-name="([^"]*)"', b).group(1))
           for b in _bloklar if re.search(r'data-name="([^"]*)"', b)]
_loy_joy = [i for i, n in enumerate(_tartib) if n.startswith("tayyor loy (")]
check("Tayyor loy zaxiralari ro'yxat OXIRIDA (guruhlash)",
      len(_loy_joy) == 3 and _loy_joy == list(range(len(_tartib) - 3, len(_tartib))), str(_tartib)[:220])
# Oddiy guruh ichida nom tartibi (`crud.get_inventory` — `order_by(item_name)`): T3 ("AAA Tayyor…")
# M0 ("KPI_ODDIY…") dan OLDIN turadi. T3 xato ravishda Tayyor loy guruhiga tushsa — M0 dan KEYIN.
_ix = {n: i for i, n in enumerate(_tartib)}
check("T3 oddiy guruhda (M0 dan oldin — nom tartibi), T1 / T4 Tayyor loy zaxiralaridan oldin",
      T3.lower() in _ix and M0.lower() in _ix and _ix[T3.lower()] < _ix[M0.lower()]
      and bool(_loy_joy) and _ix.get(T1.lower(), 10 ** 6) < _loy_joy[0]
      and _ix.get(T4.lower(), 10 ** 6) < _loy_joy[0], str(_tartib)[:220])

section("5. /api/notifications (qo'ng'iroqcha) — KPI bilan bir xil qoida")
_nt = js(req(C, "get", "/api/notifications")) or []
_tx = [x.get("text", "") for x in _nt if isinstance(x, dict)]
_qolmadi = [t for t in _tx if t.endswith(" qolmadi")]
check("M0 oddiy 0 / 0 — 'qolmadi' BOR", f"{M0} qolmadi" in _tx, str(_qolmadi)[:220])
check("T1 'Tayyor loy' (qavssiz, oddiy) — 'qolmadi' BOR (Telegram bilan bir xil)",
      f"{T1} qolmadi" in _tx, str(_qolmadi)[:220])
check("T3 — 'qolmadi' BOR", f"{T3} qolmadi" in _tx, str(_qolmadi)[:220])
check("Tayyor loy zaxiralari (L0) — qo'ng'iroqchada YO'Q",
      not any(t.startswith("Tayyor loy (") for t in _tx), str(_tx)[:220])
check("yashirin YH — qo'ng'iroqchada YO'Q", not any(YH in t for t in _tx), str(_tx)[:220])
_bash = [t for t in _tx if "kundan keyin tugaydi" in t]
check("T4 'Tayyor loyqa KPI' (oddiy, tez sarflanmoqda) — 'kundan keyin tugaydi' bashorati BOR",
      any(t.startswith(f"{T4} ") for t in _bash), str(_bash)[:220])
check("L1 Tayyor loy zaxirasi (sarf tarixi bor) — bashoratda YO'Q", not any(loy_nomi(L1) in t for t in _bash),
      str(_bash)[:220])

section("6. Telegram qo'lda ogohlantirish (/api/inventory/low-stock-alert)")
TG.clear()
_r = req(C, "post", "/api/inventory/low-stock-alert")
_msg = " ".join(t for _, t in TG)
check("low-stock-alert → 200", _r.status_code == 200, f"{_r.status_code} {getattr(_r, 'text', '')[:120]}")
# T3 nomining O'ZIDA "Tayyor loy (" bor — shuning uchun zaxiralar aniq nomi bilan tekshiriladi.
check("xabarda M0, M1, T1, T3 BOR; Tayyor loy zaxiralari (L0, L1, L2) YO'Q",
      all(n in _msg for n in ODDIY_SANALADI)
      and not any(loy_nomi(r) in _msg for r in (L0, L1, L2)), _msg[:220])

section("7. Qiymat o'zgarsa — KPI qayta hisoblanadi (L0 ga qoldiq qo'shiladi, M0 to'ldiriladi)")
_s = SessionLocal()
try:
    _s.query(Inventory).filter(Inventory.id == IDS.get(M0)).update(
        {"stock_quantity": 7}, synchronize_session=False)
    _s.query(Inventory).filter(Inventory.id == IDS.get(L0)).update(
        {"stock_quantity": 4}, synchronize_session=False)
    _s.commit()
finally:
    _s.close()
_k2 = _kpi()
check("M0 to'ldirildi → low_count == boshlang'ich + 3", _k2.get("low_count") == B_LOW + 3,
      f"{_k2.get('low_count')} (boshlang'ich {B_LOW})")
_ph2 = getattr(req(C, "get", "/inventory"), "text", "") or ""
_b2 = [b for b in _ph2.split('<div class="mat-row"')[1:]
       if f'data-name="{html.escape(loy_nomi(L0).lower())}"' in b]
_st2 = re.search(r'data-status="([^"]*)"', _b2[0]).group(1) if _b2 else None
check("L0 qoldiq 4 → 'ok' (Yetarli)", _st2 == "ok", str(_st2))

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
