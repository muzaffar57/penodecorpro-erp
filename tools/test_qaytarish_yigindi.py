#!/usr/bin/env python3
"""
test_qaytarish_yigindi.py — 5-bo'lim 3-band darvozasi (kech39, 2026-09-23).

NIMA UCHUN KERAK (asl kod `8265a94` da O'LCHANGAN — SQLite va HAQIQIY
PostgreSQL 16, `work/probe39.py`)
--------------------------------------------------------------------
  * 10 metrli detaldan "Ortiqcha" 6 + 6 + 6 metr — uchalasi 200, tayyor
    mahsulotlar omboriga 18 metr qo'shildi (bitta qaytarish buyurtmadan
    oshmasligi tekshirilardi, YIG'INDI — yo'q).
  * "Notog'ri o'lcham" va `to_stock=false` "Mijoz iltimosi" ham xuddi shunday.
  * Bitta buyurtmada bir xil nomli ikki detal bo'lishi mumkin
    (`POST /api/orders` 200). `ReturnItem` da detal raqami YO'Q edi (faqat
    `item_name`) — yig'indini detal bo'yicha hisoblab bo'lmasdi, detal
    raqamisiz so'rov esa `.first()` bilan detalni TAXMIN qilardi.

Tuzatish (kech39):
  * `models.ReturnItem.order_item_id` (FK `order_items.id`, `ON DELETE SET
    NULL`, indeks); `_TENANT_REFS` da korxona tekshiruvi.
  * `crud.create_return_item`: brakdan boshqa sabablar bo'yicha shu detalning
    jami qaytarilgani <= buyurtmadagi miqdor (aniq xabar: avval qancha, yana
    ko'pi bilan qancha); brak cheklanmaydi va yig'indiga kirmaydi; qulf (101,
    buyurtma) va yig'indi qulfdan KEYIN o'qiladi; detal raqamisiz so'rovda nom
    takrorlansa — rad; yozuvga `order_item_id` yoziladi.
  * `main._migrate_return_order_item`: ustun; BIR MARTALIK to'ldirish (faqat
    nomi buyurtmada YAGONA bo'lsa; belgi — indeks yo'qligi); PG da FK.

Qoldi (bu darvozaga KIRMAYDI): K39-1 — qaytarish yozuvini o'chirish omborga
qo'shilgan mahsulotni olib tashlamaydi (O'LCHANGAN, alohida band).

REJIMLAR: odatiy SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_qaytarish_yigindi.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_qaytarish_yigindi.py
"""
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qaytarish_yigindi_test"
_DB = os.path.join(tempfile.gettempdir(), "qaytarish_yigindi_test.db")

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
    import crud, auth, schemas                     # noqa: E402
    import database                                # noqa: E402

from sqlalchemy import text, inspect as sa_inspect  # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from production_models import Company              # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Order, OrderItem, ReturnItem, ReturnReason,
    FinishedProduct, StockSource,
)
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {str(detail)[:400]}")


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


def xabar(r):
    """400 javobidagi sabab matni (`detail.message` yoki `detail` matn)."""
    d = js(r)
    if isinstance(d, dict):
        det = d.get("detail")
        if isinstance(det, dict):
            return str(det.get("message") or "")
        return str(det or "")
    return ""


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — 1-korxona (asosiy), 2-korxona (begona)
# ══════════════════════════════════════════════════════════════
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="QY Korxona B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "QY_admin", "Parol123!", UserRole.ADMIN, "QY Admin", company_id=1)
PRJ = Project(company_id=1, client_name="QY Mijoz", project_name="QY loyiha",
              total_budget=0, total_paid=0)
PRJ_B = Project(company_id=2, client_name="QY Mijoz B", project_name="QY loyiha B",
                total_budget=0, total_paid=0)
_db.add_all([PRJ, PRJ_B])
_db.commit()
PRJ_ID, PRJB_ID = PRJ.id, PRJ_B.id
_db.close()

_n = [0]


def yangi_buyurtma(nomlar=None, miqdor=10, narx=100_000, cid=1, prj=None):
    """YANGI buyurtma (panel, penoplastsiz; birlik — metr, 10 metr) →
    (order_id, [detal_id]). `nomlar` — detal nomlari (takrorlanishi mumkin)."""
    _n[0] += 1
    nomlar = nomlar or [f"QY_D{_n[0]}"]
    d = SessionLocal()
    try:
        with contextlib.redirect_stdout(_quiet):
            o = crud.create_order(d, schemas.OrderCreate(
                project_id=prj or PRJ_ID, order_type="product",
                items=[schemas.OrderItemCreate(
                    name=nm, category="panel", width=100, thickness=10,
                    length=100, quantity=miqdor, unit_price=narx, is_coated=False)
                    for nm in nomlar]), performed_by="QY")
        oid = o.id
        o2 = d.get(Order, oid)
        if o2.company_id != cid:
            o2.company_id = cid
        items = d.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id).all()
        for it in items:
            if getattr(it, "company_id", cid) != cid:
                it.company_id = cid
        d.commit()
        return oid, [x.id for x in items]
    finally:
        d.close()


def detal_nomi(iid):
    d = SessionLocal()
    try:
        return d.get(OrderItem, iid).name
    finally:
        d.close()


def ombor(nom):
    """Tayyor mahsulotlar omboridagi QAYTGAN mahsulot (shu nom) jami."""
    d = SessionLocal()
    try:
        return round(sum(float(f.quantity or 0) for f in d.query(FinishedProduct).filter(
            FinishedProduct.name == nom, FinishedProduct.source == StockSource.RETURNED).all()), 4)
    finally:
        d.close()


def yozuvlar(oid):
    """Buyurtmaning qaytarish yozuvlari: [(sabab, miqdor, order_item_id)]."""
    d = SessionLocal()
    try:
        return [(r.reason.value, round(float(r.quantity), 4), getattr(r, "order_item_id", "YO'Q"))
                for r in d.query(ReturnItem).filter(ReturnItem.order_id == oid).order_by(ReturnItem.id).all()]
    finally:
        d.close()


def qaytar(oid, iid, miqdor, sabab="Ortiqcha", nom=None, **kw):
    t = {"order_id": oid, "item_name": nom if nom is not None else detal_nomi(iid),
         "quantity": miqdor, "unit": "metr", "reason": sabab}
    if iid is not None:
        t["order_item_id"] = iid
    t.update(kw)
    return req(C, "post", "/api/returns", json=t)


C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "QY_admin", "password": "Parol123!"},
          follow_redirects=False)
if _lr.status_code != 302:
    print(f"LOGIN BO'LMADI: {_lr.status_code}")
    print("NATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)


def _indekslar():
    return {ix["name"] for ix in sa_inspect(engine).get_indexes("return_items")}


def _ustunlar():
    return {c["name"] for c in sa_inspect(engine).get_columns("return_items")}


def _fk_turi():
    """PG: `return_items.order_item_id` chet el kalitining ON DELETE turi
    ('n' = SET NULL, 'a' = NO ACTION, ...) yoki None (kalit yo'q)."""
    with engine.connect() as c:
        r = c.execute(text(
            "SELECT c.confdeltype FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey) "
            "WHERE t.relname = 'return_items' AND c.contype = 'f' "
            "AND a.attname = 'order_item_id'")).first()
    if not r:
        return None
    v = r[0]
    return v.decode() if isinstance(v, (bytes, bytearray)) else str(v)


# ══════════════════════════════════════════════════════════════
# F. MIGRATSIYA (BIRINCHI — PG da ustun butunlay olib tashlanadi, bazada
#    boshqa qaytarish yozuvi bo'lmasligi uchun)
# ══════════════════════════════════════════════════════════════
def bolim_migratsiya():
    section("F. Migratsiya: ustun, bir martalik to'ldirish (faqat yagona nom), indeks, FK")
    check("F0 yangi baza: ustun bor", "order_item_id" in _ustunlar(), sorted(_ustunlar()))
    check("F0 yangi baza: indeks ix_return_items_order_item_id bor",
          "ix_return_items_order_item_id" in _indekslar(), sorted(_indekslar()))
    if PG_URL:
        check("F0 yangi baza: FK ON DELETE SET NULL", _fk_turi() == "n", _fk_turi())

    O, (i_u, i_k1, i_k2) = yangi_buyurtma(["F_U", "F_K", "F_K"])
    d = SessionLocal()
    try:
        for nom, m in (("F_U", 4), ("F_K", 3), ("F_YOQ", 2)):
            d.add(ReturnItem(company_id=1, order_id=O, item_name=nom, quantity=m, unit="metr",
                             reason=ReturnReason.EXCESS, refund_amount=0, is_refunded=False))
        d.commit()
    finally:
        d.close()

    # Eski holatga keltirish
    with engine.connect() as c:
        if PG_URL:
            if "order_item_id" in _ustunlar():
                c.execute(text("ALTER TABLE return_items DROP COLUMN order_item_id"))
        else:
            c.execute(text("DROP INDEX IF EXISTS ix_return_items_order_item_id"))
            if "order_item_id" in _ustunlar():
                c.execute(text("UPDATE return_items SET order_item_id = NULL"))
        c.commit()
    engine.dispose()

    mig = getattr(main, "_migrate_return_order_item", None)
    chiq = io.StringIO()
    with contextlib.redirect_stdout(chiq):
        try:
            database.sync_missing_columns()     # ishga tushish tartibi — avval u
        except Exception as e:                  # noqa: BLE001
            print(f"SYNC ISTISNO {e}")
        if mig:
            try:
                mig()
            except Exception as e:              # noqa: BLE001
                print(f"MIG ISTISNO {e}")
    matn = chiq.getvalue()
    engine.dispose()
    check("F1 migratsiya funksiyasi bor", mig is not None)
    check("F1 log: 'bog'lanadi 1 ta, NULL qoladi 2 ta'",
          "bog'lanadi 1 ta, NULL qoladi 2 ta" in matn, matn[-300:])
    check("F1 migratsiya istisnosiz", "ISTISNO" not in matn and "o'tkazib yuborildi" not in matn, matn[-300:])

    def bog():
        with engine.connect() as c:
            if "order_item_id" not in _ustunlar():
                return None
            rows = c.execute(text("SELECT item_name, order_item_id FROM return_items "
                                  "WHERE order_id = :o"), {"o": O}).fetchall()
        return {r[0]: r[1] for r in rows}

    b = bog()
    check("F2 yagona nom F_U → o'z detaliga bog'landi", b is not None and b.get("F_U") == i_u, b)
    check("F2 takrorlangan nom F_K → NULL (taxmin YO'Q)", b is not None and "F_K" in b and b["F_K"] is None, b)
    check("F2 topilmagan nom F_YOQ → NULL", b is not None and "F_YOQ" in b and b["F_YOQ"] is None, b)
    check("F3 indeks yaratildi", "ix_return_items_order_item_id" in _indekslar(), sorted(_indekslar()))
    if PG_URL:
        check("F3 FK ON DELETE SET NULL qo'yildi", _fk_turi() == "n", _fk_turi())

    # Bir martalik: F_K takrorini qayta nomlaymiz → endi F_K yagona; qayta
    # ishga tushishda eski noaniq yozuv tasodifiy detalga BOG'LANMASLIGI SHART.
    d = SessionLocal()
    try:
        d.get(OrderItem, i_k2).name = "F_K2"
        d.commit()
    finally:
        d.close()
    chiq2 = io.StringIO()
    with contextlib.redirect_stdout(chiq2):
        try:
            database.sync_missing_columns()
            if mig:
                mig()
        except Exception as e:                  # noqa: BLE001
            print(f"ISTISNO {e}")
    engine.dispose()
    b2 = bog()
    check("F4 qayta ishga tushish: F_K hali NULL (to'ldirish takrorlanmadi)",
          b2 is not None and "F_K" in b2 and b2["F_K"] is None, b2)
    check("F4 qayta ishga tushish: log jim (to'ldirish qatori yo'q)",
          "bog'lanadi" not in chiq2.getvalue() and "ISTISNO" not in chiq2.getvalue(), chiq2.getvalue()[-200:])

    # Bog'langan eski yozuv yig'indiga kiradi: F_U da avval 4 metr
    r = qaytar(O, i_u, 7)
    check("F5 eski bog'langan 4 m + yangi 7 m (10 m detal) → 400", r.status_code == 400,
          (r.status_code, xabar(r)))
    r = qaytar(O, i_u, 6)
    check("F5 eski 4 m + yangi 6 m → 200", r.status_code == 200, (r.status_code, xabar(r)))

    # Ishga tushishda chaqirilishi (statik): funksiya bor-u, chaqirilmasa
    # jonli bazada ustun `sync_missing_columns` bilan indeks / to'ldirish /
    # FK siz qolardi — F0 (yangi baza, `create_all`) buni ko'rmaydi.
    try:
        _src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read().split("\n")
    except Exception:                           # noqa: BLE001
        _src = []
    _def = [k for k, q in enumerate(_src) if q.startswith("def _migrate_return_order_item(")]
    _chaq = [k for k, q in enumerate(_src) if q.strip() == "_migrate_return_order_item()"
             and not q.startswith((" ", "\t"))]
    check("F6 main.py: _migrate_return_order_item() modul darajasida, e'londan KEYIN chaqiriladi",
          len(_def) == 1 and len(_chaq) == 1 and _chaq[0] > _def[0], (_def, _chaq))


# ══════════════════════════════════════════════════════════════
# A. Yig'indi — omborga qaytadigan sabablar
# ══════════════════════════════════════════════════════════════
def bolim_yigindi():
    section("A. Brakdan boshqa sabablar: detal bo'yicha jami <= buyurtmadagi")
    O, (i1,) = yangi_buyurtma()
    nom = detal_nomi(i1)
    r = qaytar(O, i1, 6)
    check("A1 Ortiqcha 6 / 10 → 200", r.status_code == 200, (r.status_code, xabar(r)))
    check("A1 yozuvda order_item_id = detal", yozuvlar(O) == [("Ortiqcha", 6.0, i1)], yozuvlar(O))
    g = req(C, "get", f"/api/returns?order_id={O}")
    gj = js(g) or []
    check("A1 GET /api/returns da order_item_id", g.status_code == 200 and gj and gj[0].get("order_item_id") == i1,
          str(gj)[:200])
    check("A1 ombor +6", ombor(nom) == 6.0, ombor(nom))

    r = qaytar(O, i1, 6)
    m = xabar(r)
    check("A2 yana Ortiqcha 6 (jami 12 > 10) → 400", r.status_code == 400, (r.status_code, m))
    check("A2 xabar: 'avval 6 metr qaytarilgan (buyurtmada 10 metr) — yana ko'pi bilan 4 metr'",
          "avval 6 metr qaytarilgan (buyurtmada 10 metr)" in m and "ko'pi bilan 4 metr" in m, m)
    check("A2 hech narsa yozilmadi, ombor 6", len(yozuvlar(O)) == 1 and ombor(nom) == 6.0,
          (yozuvlar(O), ombor(nom)))

    r = qaytar(O, i1, 5, "Notog'ri o'lcham")
    check("A3 boshqa sabab (Notog'ri o'lcham) 5 → 400 (sabablar bitta yig'indida)",
          r.status_code == 400, (r.status_code, xabar(r)))
    r = qaytar(O, i1, 5, "Mijoz iltimosi", to_stock=False)
    check("A4 Mijoz iltimosi to_stock=false 5 → 400 (omborga tushmasa ham sanaladi)",
          r.status_code == 400, (r.status_code, xabar(r)))
    check("A3/A4 yozuv va ombor o'zgarmadi", len(yozuvlar(O)) == 1 and ombor(nom) == 6.0,
          (yozuvlar(O), ombor(nom)))

    r = qaytar(O, i1, 4, "Mijoz iltimosi", to_stock=False)
    check("A5 aniq qolgani 4 (to_stock=false) → 200", r.status_code == 200, (r.status_code, xabar(r)))
    r = qaytar(O, i1, 0.01)
    m = xabar(r)
    check("A6 hammasi qaytgach 0.01 → 400", r.status_code == 400, (r.status_code, m))
    check("A6 xabar: 'hammasi (10 metr) allaqachon qaytarilgan'",
          "hammasi (10 metr) allaqachon qaytarilgan" in m, m)
    check("A6 ombor 6 (to_stock=false omborga qo'shmadi)", ombor(nom) == 6.0, ombor(nom))

    O2, (j1,) = yangi_buyurtma()
    natijalar = [qaytar(O2, j1, q).status_code for q in (3.333, 3.333, 3.334)]
    check("A7 3.333 + 3.333 + 3.334 = 10 → uchalasi 200 (kasr chegarasi)",
          natijalar == [200, 200, 200], natijalar)
    r = qaytar(O2, j1, 0.002)
    check("A7 so'ng 0.002 → 400", r.status_code == 400, (r.status_code, xabar(r)))


# ══════════════════════════════════════════════════════════════
# B. Brak — cheklanmaydi va yig'indiga kirmaydi
# ══════════════════════════════════════════════════════════════
def bolim_brak():
    section("B. Brak: yig'indi cheklovi YO'Q, yig'indiga KIRMAYDI")
    O, (i1,) = yangi_buyurtma()
    nom = detal_nomi(i1)
    r1 = qaytar(O, i1, 6, "Brak")
    r2 = qaytar(O, i1, 6, "Brak")
    check("B1 Brak 6 + 6 (12 > 10) → ikkalasi 200", (r1.status_code, r2.status_code) == (200, 200),
          (r1.status_code, xabar(r1), r2.status_code, xabar(r2)))
    r = qaytar(O, i1, 10)
    check("B2 ikki brakdan keyin Ortiqcha 10 → 200 (brak sanalmaydi)", r.status_code == 200,
          (r.status_code, xabar(r)))
    check("B2 ombor +10", ombor(nom) == 10.0, ombor(nom))
    r = qaytar(O, i1, 5, "Brak")
    check("B3 hammasi qaytgach Brak 5 → 200", r.status_code == 200, (r.status_code, xabar(r)))
    r = qaytar(O, i1, 11, "Brak")
    check("B4 bitta brak buyurtmadan ko'p (11 > 10) → 400 (eski qoida o'z kuchida)",
          r.status_code == 400, (r.status_code, xabar(r)))


# ══════════════════════════════════════════════════════════════
# C. Bir xil nomli detallar
# ══════════════════════════════════════════════════════════════
def bolim_nomdosh():
    section("C. Bir xil nomli ikki detal — detal RAQAMI bo'yicha")
    O, (i1, i2) = yangi_buyurtma(["QY_NOMDOSH", "QY_NOMDOSH"])
    r1 = qaytar(O, i1, 10)
    r2 = qaytar(O, i2, 10)
    check("C1 1-detal 10 va 2-detal 10 → ikkalasi 200 (nom bo'yicha aralashmaydi)",
          (r1.status_code, r2.status_code) == (200, 200),
          (r1.status_code, xabar(r1), r2.status_code, xabar(r2)))
    check("C1 yozuvlar o'z detaliga bog'langan",
          sorted(x[2] for x in yozuvlar(O)) == sorted([i1, i2]), yozuvlar(O))
    r = qaytar(O, i1, 1)
    check("C1 1-detal yana 1 → 400", r.status_code == 400, (r.status_code, xabar(r)))

    O2, (k1, k2) = yangi_buyurtma(["QY_NOMDOSH2", "QY_NOMDOSH2"])
    r = qaytar(O2, None, 1, nom="QY_NOMDOSH2")
    m = xabar(r)
    check("C2 detal raqamisiz, nom takrorlangan → 400", r.status_code == 400, (r.status_code, m))
    check("C2 xabar: 'nomli 2 ta detal bor'", "nomli 2 ta detal bor" in m, m)
    check("C2 hech narsa yozilmadi", yozuvlar(O2) == [], yozuvlar(O2))
    O3, (u1,) = yangi_buyurtma()
    r = qaytar(O3, None, 2, nom=detal_nomi(u1))
    check("C3 detal raqamisiz, nom yagona → 200 va o'sha detalga bog'landi",
          r.status_code == 200 and yozuvlar(O3) == [("Ortiqcha", 2.0, u1)], (r.status_code, yozuvlar(O3)))


# ══════════════════════════════════════════════════════════════
# D. Korxona (tenant) — begona detalga bog'lab bo'lmaydi
# ══════════════════════════════════════════════════════════════
def bolim_tenant():
    section("D. Begona korxona detaliga bog'lanish")
    O, (i1,) = yangi_buyurtma()
    OB, (b1,) = yangi_buyurtma(cid=2, prj=PRJB_ID)
    r = qaytar(O, b1, 1)
    check("D1 API: o'z buyurtmasi + begona detal → 404", r.status_code == 404, (r.status_code, xabar(r)))
    d = SessionLocal()
    xato = None
    try:
        d.add(ReturnItem(company_id=1, order_id=O, order_item_id=b1, item_name="x", quantity=1,
                         unit="metr", reason=ReturnReason.EXCESS, refund_amount=0, is_refunded=False))
        d.commit()
    except Exception as e:                      # noqa: BLE001
        xato = type(e).__name__
        d.rollback()
    finally:
        d.close()
    check("D2 ORM: 1-korxona yozuvi 2-korxona detaliga → TenantMismatchError",
          xato == "TenantMismatchError", xato)


# ══════════════════════════════════════════════════════════════
# E. Detal / buyurtma o'chirilishi (PG da FK)
# ══════════════════════════════════════════════════════════════
def bolim_ochirish():
    section("E. Qaytarishi bor detal va buyurtmani o'chirish")
    O, (i1, i2) = yangi_buyurtma(["QY_E1", "QY_E2"])
    qaytar(O, i1, 2)
    r = req(C, "delete", f"/api/order-items/{i1}")
    check("E1 qaytarishi bor detalni o'chirish → 200 (500 EMAS)", r.status_code == 200, (r.status_code, r.text[:200]))
    if PG_URL:
        check("E1 PG: qaytarish yozuvi qoldi, order_item_id NULL (SET NULL)",
              [x[2] for x in yozuvlar(O)] == [None], yozuvlar(O))
    O2, (j1,) = yangi_buyurtma()
    qaytar(O2, j1, 3)
    r = req(C, "delete", f"/api/orders/{O2}")
    check("E2 qaytarishi bor (yetkazishsiz) buyurtmani o'chirish → 200", r.status_code == 200,
          (r.status_code, r.text[:200]))


# ══════════════════════════════════════════════════════════════
# G. Parallel (faqat HAQIQIY PG)
# ══════════════════════════════════════════════════════════════
def bolim_parallel():
    if not PG_URL:
        return
    section("G. Parallel ikki qaytarish (6 va 5 metr, 10 metrli detal) — faqat bittasi")
    asl = crud.add_returned_to_stock

    def sekin(*a, **k):
        # yig'indi o'qilgandan keyin commit gacha oraliqni kengaytiradi
        time.sleep(0.4)
        return asl(*a, **k)

    crud.add_returned_to_stock = sekin
    yomon = []
    try:
        for _ in range(3):
            O, (i1,) = yangi_buyurtma()
            nom = detal_nomi(i1)
            bar = threading.Barrier(2)
            natija = {}

            def ish(k, miqdor):
                s = SessionLocal()
                try:
                    bar.wait(timeout=30)
                    crud.create_return_item(s, schemas.ReturnItemCreate(
                        order_id=O, order_item_id=i1, item_name=nom, quantity=miqdor,
                        unit="metr", reason="Ortiqcha"), company_id=1)
                    natija[k] = "ok"
                except Exception as e:          # noqa: BLE001
                    s.rollback()
                    natija[k] = f"{type(e).__name__}"
                finally:
                    s.close()
            ts = [threading.Thread(target=ish, args=(0, 6.0)), threading.Thread(target=ish, args=(1, 5.0))]
            for t in ts:
                t.start()
            for t in ts:
                t.join(timeout=120)
            jami = sum(x[1] for x in yozuvlar(O) if x[0] != "Brak")
            okn = sum(1 for v in natija.values() if v == "ok")
            if not (okn == 1 and jami <= 10.001 and ombor(nom) <= 10.001):
                yomon.append((natija, jami, ombor(nom)))
    finally:
        crud.add_returned_to_stock = asl
    check("G parallel 6 + 5 (3 urinish): har safar faqat BITTASI o'tdi, jami <= 10",
          not yomon, str(yomon[:1]))


def kumulyativ():
    section("K. 5xx yo'q")
    for u in ("/api/returns", "/api/returns/stats", "/returns"):
        r = req(C, "get", u)
        check(f"K {u} 200", r.status_code == 200, r.status_code)


for _fn in (bolim_migratsiya, bolim_yigindi, bolim_brak, bolim_nomdosh, bolim_tenant,
            bolim_ochirish, bolim_parallel, kumulyativ):
    try:
        _fn()
    except Exception as _e:                    # noqa: BLE001
        check(f"{_fn.__name__}: kutilmagan istisno", False, f"{type(_e).__name__}: {_e}")

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
