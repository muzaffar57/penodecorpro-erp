#!/usr/bin/env python3
"""
test_ozim264.py — kech201 (zip 264): xavfsizlik REJA 16-band (Fable F11) — «Xarajat qo'shish» dagi «o'z bugungi xarajatim» foydalanuvchi
ID si bo'yicha (`expense_transactions.created_by_user_id`).

NIMA UCHUN KERAK (zip 263 gacha — O'LCHANDI shu testning A3 / A4 / B2 bandlarida, asl kodda yiqiladi):
  «Bugun siz kiritganlar» (`GET /api/finance/transactions/bugungi-ozim`) va o'z xarajatini o'chirish (`DELETE …/{id}/ozim`) faqat
  `created_by` (to'liq ism yoki login) bo'yicha edi — bir korxonada to'liq ismi bir xil ikki foydalanuvchi (masalan ikkita «Menejer»)
  bir-birining bugungi xarajatini ko'rib O'CHIRA OLARDI; ismi almashgan foydalanuvchi esa o'zi kiritganini ko'rmay qolardi.
  Endi: yozishda `created_by_user_id` = joriy foydalanuvchi (tanadagi qiymat hisobga olinmaydi); «o'ziniki» — shu id; id si yo'q eski
  yozuv (zip 264 dan oldin — faqat o'tish kuni) — avvalgidek ism bo'yicha.
BO'LIMLAR: A — yozish va id bo'yicha ajratish; B — chegaralar (eski yozuv, ism almashishi, boshqa korxona, boshqa manba, kecha);
           C — sxema va zaxira (ustun bor; zaxirada bor; eski zaxira — ustunsiz — tiklanadi, qiymat NULL).
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (7956576 — zip 263) qarshi YIQILADI, QULAMAYDI.
ISHLATISH: python3 tools/test_ozim264.py
"""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "ozim264_test"
_T = tempfile.mkdtemp(prefix="ozim264_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'ozim264_test.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "ADMIN_PASSWORD", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
import tenant_context                              # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User, ExpenseTransaction   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import inspect as _sa_inspect      # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


YANGI_KOD = hasattr(ExpenseTransaction, "created_by_user_id")
PAROL = "Kuchli-Sinov-Parol-264"
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ozim B korxona", code="OZIM-B264"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "oz_menejer1", PAROL, UserRole.MANAGER, "Menejer", company_id=1)
    auth.create_user(s, "oz_menejer2", PAROL, UserRole.MANAGER, "Menejer", company_id=1)
    auth.create_user(s, "oz_b_menejer", PAROL, UserRole.MANAGER, "Menejer", company_id=2)
s.close()


def uid(login):
    d = SessionLocal()
    try:
        return d.query(User.id).execution_options(skip_tenant_filter=True).filter(User.username == login).scalar()
    finally:
        d.close()


U1, U2, UB = uid("oz_menejer1"), uid("oz_menejer2"), uid("oz_b_menejer")


def kirgan(login, parol=PAROL):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": parol}, follow_redirects=False)
    assert r.status_code == 302, f"{login} kirmadi: {r.status_code} {r.text[-200:]}"
    return c


C1, C2, CB = kirgan("oz_menejer1"), kirgan("oz_menejer2"), kirgan("oz_b_menejer")


def tx_ol(tx_id):
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            return d.query(ExpenseTransaction).filter(ExpenseTransaction.id == tx_id).first()
    finally:
        d.close()


def tx_qosh(company_id, created_by, source="manual", user_id=None, kun_oldin=0, category="boshqa", amount=1000):
    """To'g'ridan-to'g'ri yozuv (eski / boshqa manba / kechagi holatlar uchun)."""
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            _hozir = datetime.now(timezone.utc).replace(tzinfo=None)
            kw = dict(company_id=company_id, date=_hozir, category=category, amount=amount, notes="ozim264",
                      created_by=created_by, source=source, created_at=_hozir - timedelta(days=kun_oldin))
            if YANGI_KOD:
                kw["created_by_user_id"] = user_id
            t = ExpenseTransaction(**kw)
            d.add(t)
            d.commit()
            return t.id
    finally:
        d.close()


def royxat(c):
    return [x.get("id") for x in (js(c.get("/api/finance/transactions/bugungi-ozim")) or []) if isinstance(x, dict)]


# ══════════════════════════════════════════════════════════════
section("A — yozish: created_by_user_id = joriy foydalanuvchi; «o'ziniki» id bo'yicha")
# ══════════════════════════════════════════════════════════════
r = C1.post("/api/finance/transactions", json={"category": "boshqa", "amount": 12500, "notes": "A1 menejer1"})
X1 = js(r).get("id")
_t = tx_ol(X1) if X1 else None
check("A1 menejer1 xarajat yozdi — 200; bazada created_by «Menejer», created_by_user_id = menejer1 id",
      r.status_code == 200 and _t is not None and _t.created_by == "Menejer" and getattr(_t, "created_by_user_id", "yo'q") == U1,
      (r.status_code, r.text[:200], getattr(_t, "created_by_user_id", "yo'q") if _t else None, U1))
r = C1.post("/api/finance/transactions", json={"category": "boshqa", "amount": 700, "notes": "A2 soxta id", "created_by_user_id": U2})
_t2 = tx_ol(js(r).get("id")) if r.status_code == 200 and js(r).get("id") else None
check("A2 tanada boshqa foydalanuvchi id si (created_by_user_id) — 400 «Noma'lum maydon», yozuv YO'Q (id ni faqat server qo'yadi; "
      "mut264 M06 — `crud` ichida tanadan o'qish shu sababli EKVIVALENT: `_clean_val` uni o'tkazmaydi)",
      r.status_code == 400 and "Noma'lum maydon" in str(js(r).get("detail")) and _t2 is None,
      (r.status_code, r.text[:200]))
X2 = _t2.id if _t2 is not None else None
_l2 = royxat(C2)
check("A3 menejer2 (to'liq ismi ham «Menejer») «Bugun siz kiritganlar» da menejer1 ning xarajati YO'Q",
      X1 is not None and X1 not in _l2 and (X2 is None or X2 not in _l2), (_l2, X1, X2))
r = C2.delete(f"/api/finance/transactions/{X1}/ozim")
check("A4 menejer2 menejer1 ning bugungi xarajatini O'CHIRA OLMAYDI — 404 (mavjudligi aytilmaydi), yozuv joyida",
      r.status_code == 404 and tx_ol(X1) is not None, (r.status_code, r.text[:200]))
_l1 = royxat(C1)
check("A5 menejer1 o'zinikini ko'radi (ikkalasi)", X1 in _l1 and (X2 is None or X2 in _l1), (_l1, X1, X2))
r = C2.post("/api/finance/transactions", json={"category": "boshqa", "amount": 3300, "notes": "A6 menejer2"})
X3 = js(r).get("id")
check("A6 menejer2 o'z xarajati — o'zida bor, menejer1 da yo'q",
      r.status_code == 200 and X3 in royxat(C2) and X3 not in royxat(C1), (r.status_code, X3))
r = C1.delete(f"/api/finance/transactions/{X1}/ozim")
check("A7 menejer1 o'z bugungi xarajatini o'chiradi — 200, yozuv yo'q", r.status_code == 200 and tx_ol(X1) is None,
      (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════
section("B — chegaralar")
# ══════════════════════════════════════════════════════════════
XE = tx_qosh(1, "Menejer", user_id=None)
check("B1 id si yo'q ESKI yozuv (zip 264 dan oldin, bugun) — ism bo'yicha: ikkala «Menejer» ko'radi (o'tish kuni, avvalgidek)",
      XE in royxat(C1) and XE in royxat(C2), (XE, royxat(C1), royxat(C2)))
XB4 = tx_qosh(1, "Menejer", source="inventory_receipt", user_id=U1)
XK = tx_qosh(1, "Menejer", user_id=U1, kun_oldin=1)
check("B2 boshqa manba (kirim) va KECHAGI qo'lda xarajat — ro'yxatda yo'q, o'chirib bo'lmaydi (404)",
      XB4 not in royxat(C1) and XK not in royxat(C1)
      and C1.delete(f"/api/finance/transactions/{XB4}/ozim").status_code == 404
      and C1.delete(f"/api/finance/transactions/{XK}/ozim").status_code == 404
      and tx_ol(XB4) is not None and tx_ol(XK) is not None)
r = CB.post("/api/finance/transactions", json={"category": "boshqa", "amount": 900, "notes": "B3 boshqa korxona"})
XBK = js(r).get("id")
check("B3 boshqa korxonadagi «Menejer» — 1-korxona xarajatlarini ko'rmaydi / o'chirmaydi; o'zinikini ko'radi",
      r.status_code == 200 and X3 not in royxat(CB) and XE not in royxat(CB) and XBK in royxat(CB)
      and CB.delete(f"/api/finance/transactions/{X3}/ozim").status_code == 404 and tx_ol(X3) is not None,
      (r.status_code, royxat(CB)))
d = SessionLocal()
d.query(User).execution_options(skip_tenant_filter=True).filter(User.id == U2).update({"full_name": "Menejer Ikkinchi"},
                                                                                      synchronize_session=False)
d.commit()
d.close()
C2b = kirgan("oz_menejer2")
_l2b = royxat(C2b)
check("B4 menejer2 to'liq ismini almashtirdi — o'zi bugun kiritgani (id li) ro'yxatda QOLADI va o'chira oladi; eski id siz «Menejer» "
      "yozuvi endi unga tegishli emas", X3 in _l2b and XE not in _l2b
      and C2b.delete(f"/api/finance/transactions/{X3}/ozim").status_code == 200 and tx_ol(X3) is None, (_l2b, X3, XE))
r = C2b.post("/api/finance/transactions", json={"category": "boshqa", "amount": 450, "notes": "B5 yangi ism"})
_t5 = tx_ol(js(r).get("id")) if js(r).get("id") else None
check("B5 yangi ism bilan yozuv — created_by «Menejer Ikkinchi», id — menejer2", _t5 is not None
      and _t5.created_by == "Menejer Ikkinchi" and getattr(_t5, "created_by_user_id", None) == U2)
_m = js(C1.get("/api/finance/transactions/bugungi-ozim"))
check("B6 ro'yxat maydonlari o'zgarmadi (id, date, category, amount, notes, created_at) — id raqami foydalanuvchiga chiqmaydi",
      isinstance(_m, list) and _m and all(set(x) == {"id", "date", "category", "amount", "notes", "created_at"} for x in _m), _m)

# ══════════════════════════════════════════════════════════════
section("C — sxema va zaxira")
# ══════════════════════════════════════════════════════════════
_ust = [c["name"] for c in _sa_inspect(engine).get_columns("expense_transactions")]
check("C1 bazada expense_transactions.created_by_user_id ustuni bor (NULL ruxsat)", "created_by_user_id" in _ust, _ust)
d = SessionLocal()
with tenant_context.system_context(d):
    _zx = crud.export_full_backup(d, company_id=1)
d.close()
_rows = _zx["tables"].get("expense_transactions", [])
check("C2 zaxirada xarajat qatorlarida created_by_user_id bor (id li yozuvda — qiymat)",
      _rows and all("created_by_user_id" in x for x in _rows) and any(x.get("created_by_user_id") == U1 for x in _rows),
      [(x.get("id"), x.get("created_by_user_id")) for x in _rows][:8])
for x in _rows:
    x.pop("created_by_user_id", None)
_n = len(_rows)
d = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    _rz = crud.import_full_backup(d, _zx, company_id=1, replace=True)
d.close()
d = SessionLocal()
with tenant_context.system_context(d):
    _q = d.query(ExpenseTransaction).filter(ExpenseTransaction.company_id == 1).all()
    _nul = [getattr(t, "created_by_user_id", "yo'q") for t in _q]
d.close()
check("C3 ESKI zaxira (ustunsiz) tiklanadi — muvaffaqiyat, qatorlar soni teng, created_by_user_id hammasida NULL",
      _rz.get("success") and len(_q) == _n and all(v is None for v in _nul), (_rz.get("message"), len(_q), _n, _nul[:8]))

print(f"\nNATIJA: o'tdi = {OK}, yiqildi = {FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
