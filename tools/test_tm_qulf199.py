#!/usr/bin/env python3
"""
test_tm_qulf199.py — kech155 (zip 199 «Qulf tartibi — xomashyo ↔ tayyor mahsulot guruhi»; zip 198 pasport 7-bo'lim OCHIQ (2) va mustaqil
tekshiruvlar `work/k198/review198/HISOBOT.md` F2 / F5, `HISOBOT_v2.md` V4): xomashyo (Inventory) qulfi `FOR NO KEY UPDATE` (qatorni
o'chiradigan joydan tashqari) va MRP «Yakunlash» da yangi partiya guruhi xomashyodan OLDIN.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k198/review198/s/rv198v3.py` R2 / R5 / R7 / R10 / R11, zip 198 kodi, HAQIQIY PostgreSQL 16; ikki
parallel so'rov, bir martalik kechikish; sanoq `pg_stat_database.deadlocks`; `work/natija/k199/baza_r2_r11_stg198_pg.txt`): har birida
3 / 3 urinishda 40P01 — tekshirilayotgan amal 500 («Serverda kutilmagan xato»; tranzaksiya qaytadi, ma'lumot buzilmaydi):
  R7  buyurtma tahriri (guruh → penoplast `FOR UPDATE`) ∥ buyurtma yaratish (detal yozuvi penoplastga tashqi kalit KEY SHARE → guruh) —
      minussiz ham; R10 / R11 taqdirli («Tuzatildi — o'sha joyiga», penoplast xomashyosi) brak bekori (partiya → penoplast) ∥ shu
      partiyadan + oddiy detalli buyurtma (penoplast KEY SHARE → partiya). ILDIZ — xomashyo qulfi `FOR UPDATE` tashqi kalit KEY SHARE bilan
      to'qnashadi.
  R2  MRP «Yakunlash» (BOM xomashyosi KLEY → yangi partiya M → minusdagi guruh) ∥ loyli buyurtma (guruh → loy KLEY); R5 o'sha, penoplast
      BOM ∥ buyurtma tahriri (guruh → penoplast).
XOMASHYO NAVBATI (statik audit `work/k199/AUDIT_QULF.md`, O'LCHANGAN `work/k199/probe199.py` — zip 198 kodida S1 S2 S5 S5b S6 S8 S9 3 / 3
40P01; faqat `FOR NO KEY UPDATE` bilan yana S3 S3b S4 S4c 3 / 3 — yaratish endi tashqi kalitda kutmay, xomashyoni boshqa tartibda oladi):
xomashyoga tegadigan marshrutlar (`main._XOMASHYO_MARSHRUTLARI`) tranzaksiyasining BIRINCHI qulfi — korxona bo'yicha
`pg_advisory_xact_lock(199, korxona)` (`crud.xomashyo_navbati`; so'rov ichidagi keyingi tranzaksiyalarda — `after_begin`). S-sahnalar:
S1 qoplamali yaratish ∥ qoralamani faollashtirish, S2 ∥ qoplamali brak, S3 / S3b ∥ ishlab chiqarish / «+», S4 / S4c buyurtmani o'chirish ∥
yaratish, S5 ikki zichlikli faollashtirish ∥ teskari tartibli yaratish, S5b ikki loysiz yaratish, S6 «Tayyor» qisman (loy farqi) ∥
ishlab chiqarish, S8 o'chirish ∥ faollashtirish (tayyor mahsulot + penoplast), S9 MRP «Yakunlash» (BOM [KLEY, penoplast]) ∥ faollashtirish.
BO'LIMLAR: K — tartib (manba); Y — [faqat PG] qulf turi (xomashyo `inventory_qulf` ostida turganda boshqa ulanish KEY SHARE ni KUTMASDAN
oladi; `ochirish=True` da — kutadi); F — ketma-ket natijalar (asl kod bilan AYNAN — xulq o'zgarmagan); P — [faqat PG] parallel: 40P01
yo'q, ikkala so'rov 200, natija shu holatni KETMA-KET bajargandagi bilan bir xil (har tekshiruvga ikki bir xil holat yasaladi).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (baza nomi — `TM199_PG_BAZA`, bo'lmasa `tm_qulf199_test`); `TENANT_FILTER=1`.
Asl kodga (zip 198) qarshi K va (PG da) Y, P yiqiladi; F o'tadi.
ISHLATISH: python3 tools/test_tm_qulf199.py
"""
import os
import io
import sys
import time
import inspect
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = os.environ.get("TM199_PG_BAZA") or "tm_qulf199_test"
_T = tempfile.mkdtemp(prefix="tm199_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tm199.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402
    import production_service                      # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import (UserRole, Project, Inventory, FinishedProduct, OrderItem, StockSource, ProductionStatus,   # noqa: E402
                    Recipe, RecipeIngredient)
from production_models import ProductionOrder      # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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
        if callable(detail):
            try:
                detail = detail()
            except Exception as e:         # noqa: BLE001
                detail = f"{type(e).__name__}: {e}"
        print(f"  ✗ {REJIM}{label}   {str(detail)[:1500]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def tartibda(src, *qismlar):
    """Qismlar `src` ichida AYNAN shu tartibda uchraydimi."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def manba(modul, nom):
    f = getattr(modul, nom, None)
    try:
        return inspect.getsource(f) if f else ""
    except (OSError, TypeError):
        return ""


main._send_telegram = lambda *a, **k: True

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "tm199_admin", PAROL, UserRole.ADMIN, "TM199 Admin", company_id=1)
PRJ = Project(company_id=1, client_name="TM199 Mijoz", project_name="TM199 loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="TM199 PENO", unit="blok", stock_quantity=100000, min_stock=0, is_penoplast=True,
                 volume_per_unit=1, price_per_unit=120000, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TM199 KLEY", unit="kg", stock_quantity=100000, min_stock=0, price_per_unit=2000,
                 category="Kimyo")
s.add_all([PRJ, PENO, KLEY])
s.flush()
REC = Recipe(company_id=1, name="TM199 retsept", batch_size_kg=100.0)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
s.commit()
PRJ_ID, PENO_ID, KLEY_ID, REC_ID = PRJ.id, PENO.id, KLEY.id, REC.id
PRJ2 = Project(company_id=1, client_name="TM199 Mijoz 2", project_name="TM199 loyiha 2", total_budget=0, total_paid=0)
P2 = Inventory(company_id=1, item_name="TM199 PENO 2", unit="blok", stock_quantity=100000, min_stock=0, is_penoplast=True,
               volume_per_unit=1, price_per_unit=150000, category="Penoplast")
M2 = Inventory(company_id=1, item_name="TM199 MARMAR", unit="kg", stock_quantity=100000, min_stock=0, price_per_unit=1000,
               category="Kimyo")
s.add_all([PRJ2, P2, M2])
s.flush()
REC2 = Recipe(company_id=1, name="TM199 R2", batch_size_kg=100.0)
s.add(REC2)
s.flush()
s.add_all([RecipeIngredient(recipe_id=REC2.id, inventory_id=KLEY.id, quantity_kg=50.0),
           RecipeIngredient(recipe_id=REC2.id, inventory_id=M2.id, quantity_kg=50.0)])
s.commit()
PRJ2_ID, P2_ID, M2_ID, REC2_ID = PRJ2.id, P2.id, M2.id, REC2.id
s.close()


def mijoz():
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    assert c.post("/login", data={"username": "tm199_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)
    return c


A = mijoz()
_n = {"d": 0, "pt": 0}
A.get(f"/api/loy-stock?recipe_id={REC2_ID}")                    # «Tayyor loy (TM199 R2)» qatori (qoldiq 0) — yaratish tekshiruvi uni qulflaydi
SR_ID = (lambda s: (s.query(Inventory.id).filter(Inventory.item_name == "Tayyor loy (TM199 R2)").scalar()))(SessionLocal())


def yangi_tm(miqdor, nom, birlik=1000):
    def f(s):
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=False, width=20, thickness=10,
                             quantity=miqdor, produced_quantity=max(miqdor, 0), unit="metr", unit_price=0,
                             cost_price=max(miqdor, 0) * birlik, unit_cost_stable=birlik, source=StockSource.PRODUCED,
                             penoplast_id=PENO_ID, unit_volume_m3=0.01, volume_m3=0.01 * max(miqdor, 0),
                             production_status=ProductionStatus.READY, reserved_quantity=0)
        s.add(fp)
        s.flush()
        return fp.id
    return db_ishi(f)


def detal(uz, fid):
    _n["d"] += 1
    return {"name": f"TM199 detal {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": uz, "quantity": 1,
            "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID, "finished_product_id": fid}


def oddiy_detal():
    """Penoplastdan yasaladigan oddiy detal (tayyor mahsulotsiz) — yaratishda penoplast yechiladi, yozuvi penoplastga tashqi kalit."""
    _n["d"] += 1
    return {"name": f"TM199 oddiy {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": 2, "quantity": 1,
            "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID}


def tana(*items, loy=0, rec=None):
    t = {"project_id": PRJ_ID, "order_type": "product", "loy_kg": loy, "items": list(items)}
    if rec:
        t["recipe_id"] = rec
    return t


def buyurtma(*items, loy=0, rec=None):
    r = A.post("/api/orders?confirm_shortage=true", json=tana(*items, loy=loy, rec=rec))
    assert r.status_code == 200, (r.status_code, r.text[:400])
    return js(r).get("id")


def b_buyurtma(*items, loy=0, rec=None):
    return lambda c: c.post("/api/orders?confirm_shortage=true", json=tana(*items, loy=loy, rec=rec))


def tm(fid):
    """(miqdor, band) — partiya o'chirilgan bo'lsa None."""
    def f(s):
        x = s.get(FinishedProduct, fid)
        return None if x is None else (round(float(x.quantity), 4), round(float(x.reserved_quantity or 0), 4))
    return db_ishi(f)


def zaxira(iid):
    return db_ishi(lambda s: round(float(s.get(Inventory, iid).stock_quantity), 4))


def detal_idlari(oid):
    return db_ishi(lambda s: [x.id for x in s.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id)])


def mrp_turi(mat=None):
    """Har holatga ALOHIDA MRP turi (guruhlar bir-biriga aralashmasin); BOM — `mat` (odatda penoplast) 0,01 / dona."""
    _n["pt"] += 1
    pt = js(A.post("/api/production/product-types", json={"name": f"TM199 Karniz {_n['pt']}", "unit": "dona",
                                                          "input_template": "quantity_only", "pricing_formula": "unit_based"})).get("id")
    bom = js(A.post("/api/production/boms", json={"product_type_id": pt, "variant_name": "Asosiy", "batch_quantity": 1,
                                                  "items": [{"inventory_id": mat or PENO_ID, "quantity": 0.01}]})).get("id")
    assert pt and bom, (pt, bom)
    return pt, bom


def mrp_detal(pt, soni, fid=None):
    _n["d"] += 1
    d = {"name": f"TM199 MRP {_n['d']}", "category": "mrp_product", "quantity": soni, "unit_price": 100000, "is_coated": False,
         "penoplast_id": None, "product_type_id": pt}
    if fid:
        d["finished_product_id"] = fid
    return d


def po_yarat(pt, bom, miqdor, qadamlar=("start", "complete")):
    """Omborga ishlab chiqarish (`qadamlar` — qaysi bosqichgacha) — id i."""
    r = A.post("/api/production/orders", json={"product_type_id": pt, "bom_id": bom, "quantity": miqdor, "source_type": "warehouse_stock"})
    pid = ((js(r) or {}).get("production_order") or {}).get("id")
    assert pid, (r.status_code, r.text[:300])
    for q in qadamlar:
        r1 = A.post(f"/api/production/orders/{pid}/{q}")
        assert r1.status_code == 200, (q, r1.status_code, r1.text[:300])
    return pid


def po_tm(pid):
    return db_ishi(lambda s: s.get(ProductionOrder, pid).finished_product_id)


def tahrir_tana(oid, ozgar):
    """To'liq tahrir tanasi — `ozgar`: {indeks: {maydon: qiymat}}."""
    o = js(A.get(f"/api/orders/{oid}"))
    items = []
    for i, it in enumerate(o.get("items") or []):
        d = {k: it.get(k) for k in ("id", "name", "category", "quantity", "length", "width", "thickness", "unit_price", "is_coated",
                                    "penoplast_id", "finished_product_id", "product_type_id", "recipe_id")}
        d = {k: v for k, v in d.items() if v is not None}
        d.update(ozgar.get(i) or {})
        items.append(d)
    return {"project_id": PRJ_ID, "order_type": "product", "loy_kg": o.get("loy_kg") or 0, "items": items, "notes": o.get("notes")}


# ── holatlar: {"rol": {nom: partiya id}, "a": A(c), "b": B(c), "kal": kechikish, "kim": A funksiyasi, "qosh": qo'shimcha holat} ──
def h_tahrir(u):
    """R7 (mustaqil tekshiruv F5 — ILDIZ; minussiz): MRP partiya G 20 (bo'sh); Oe — G dan 1 + oddiy detal. A — Oe tahriri (oddiy detal
    uzunligi 2 → 3: guruh, so'ng penoplast — kechikish `adjust_inventory_diff` oldidan); B — yangi buyurtma: G dan 1 + oddiy detal
    (detal yozuvi penoplastga KEY SHARE, so'ng guruh)."""
    pt, bom = mrp_turi()
    G = po_tm(po_yarat(pt, bom, 20))
    Oe = buyurtma(mrp_detal(pt, 1, G), oddiy_detal())
    tb = tahrir_tana(Oe, {1: {"length": 3}})
    p0 = zaxira(PENO_ID)
    return {"rol": {"G": G}, "a": lambda c: c.put(f"/api/orders/{Oe}?confirm_shortage=true", json=tb),
            "b": b_buyurtma(mrp_detal(pt, 1, G), oddiy_detal()), "kal": "adj", "kim": "update_order_full",
            "qosh": lambda: {"peno": round(p0 - zaxira(PENO_ID), 4)}}


def h_brak_peno(u, ikkinchi=False):
    """R11 (mustaqil tekshiruv v2 V4): T 3 → brak 3, faol taqdir «Tuzatildi — o'sha joyiga», xomashyo PENOPLAST 0,1 (T 3). `ikkinchi` — R10:
    o'sha taqdir bekor qilinib, «2-nav» (N, 1 000) faol. A — brakni bekor qilish (oldindan qulf partiyani oladi, so'ng taqdir xomashyosi
    penoplast — kechikish `_taqdir_inv` oldidan); B — T dan 1 + oddiy detalli buyurtma (penoplast KEY SHARE, so'ng T guruhi)."""
    T = yangi_tm(3, f"TM199 R11 Karniz {u}")
    rl = A.post("/api/finished/loss", json={"finished_product_id": T, "quantity": 3, "reason": "x", "brak_sabab": "boshqa",
                                            "taqdir": {"taqdir": "tuzatildi", "joy": "joyiga",
                                                       "materiallar": [{"inventory_id": PENO_ID, "miqdor": 0.1}]}})
    assert rl.status_code == 200, (rl.status_code, rl.text[:300])
    L = js(rl).get("loss_id")
    rol = {"T": T}
    if ikkinchi:
        rt = A.post(f"/api/finished/loss/{L}/taqdir", json={"taqdir": "ikkinchi_nav", "narx": 1000})
        assert rt.status_code == 200, (rt.status_code, rt.text[:300])
        rol["N"] = js(rt).get("tm_id")
    p0 = zaxira(PENO_ID)
    return {"rol": rol, "a": lambda c: c.delete(f"/api/finished/loss/{L}"), "b": b_buyurtma(detal(1, T), oddiy_detal()),
            "kal": "tinv", "kim": "delete_finished_product_loss", "qosh": lambda: {"peno": round(p0 - zaxira(PENO_ID), 4)}}


def h_yakun_loy(u):
    """R2 (mustaqil tekshiruv F2): MRP turi (BOM — KLEY); G 2 → buyurtma 5 → G −3; M 4 (jarayonda). A — «Yakunlash» (KLEY → M → guruh —
    kechikish guruh qulfi oldidan); B — G dan 1 + loy 10 kg (KLEY) buyurtma (guruh, so'ng loy KLEY)."""
    pt, bom = mrp_turi(KLEY_ID)
    G = po_tm(po_yarat(pt, bom, 2))
    buyurtma(mrp_detal(pt, 5, G))
    pid = po_yarat(pt, bom, 4, qadamlar=("start",))
    M = po_tm(pid)
    k0 = zaxira(KLEY_ID)
    return {"rol": {"G": G, "M": M}, "a": lambda c: c.post(f"/api/production/orders/{pid}/complete"),
            "b": b_buyurtma(mrp_detal(pt, 1, G), loy=10, rec=REC_ID), "kal": "fpg", "kim": "complete_production_order",
            "qosh": lambda: {"kley": round(k0 - zaxira(KLEY_ID), 4)}}


def h_yakun_tahrir(u):
    """R5 (mustaqil tekshiruv F2): MRP turi (BOM — penoplast); G 2 → buyurtma 5 → G −3; Oe — G dan 1 + oddiy detal (G −4); M 4 (jarayonda).
    A — «Yakunlash» (penoplast → M → guruh — kechikish guruh qulfi oldidan); B — Oe tahriri (oddiy detal 2 → 3: guruh, so'ng penoplast)."""
    pt, bom = mrp_turi()
    G = po_tm(po_yarat(pt, bom, 2))
    buyurtma(mrp_detal(pt, 5, G))
    Oe = buyurtma(mrp_detal(pt, 1, G), oddiy_detal())
    pid = po_yarat(pt, bom, 4, qadamlar=("start",))
    M = po_tm(pid)
    tb = tahrir_tana(Oe, {1: {"length": 3}})
    p0 = zaxira(PENO_ID)
    return {"rol": {"G": G, "M": M}, "a": lambda c: c.post(f"/api/production/orders/{pid}/complete"),
            "b": lambda c: c.put(f"/api/orders/{Oe}?confirm_shortage=true", json=tb), "kal": "fpg", "kim": "complete_production_order",
            "qosh": lambda: {"peno": round(p0 - zaxira(PENO_ID), 4)}}


# ── XOMASHYO NAVBATI sahnalari (`work/k199/probe199.py`) — holat: xomashyolar o'zgarishi (yasalgandan keyin) ──
_XOM = None


def zaxiralar():
    return db_ishi(lambda s: {k: round(float(s.get(Inventory, v).stock_quantity), 4) for k, v in
                              (("P1", PENO_ID), ("P2", P2_ID), ("K", KLEY_ID), ("M2", M2_ID), ("S", SR_ID)) if v})


def ozgarish(z0):
    z = zaxiralar()
    return {k: round(z[k] - z0[k], 4) for k in z}


def qd(p=None, uz=2, qoplama=True):
    """Qoplamali (yoki `qoplama=False`) penoplast detali."""
    _n["d"] += 1
    return {"name": f"TM199 q {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": uz, "quantity": 1,
            "unit_price": 20000, "is_coated": qoplama, "penoplast_id": p or PENO_ID}


def qtana(*items, loy=10, prj=None, qoralama=False):
    t = {"project_id": prj or PRJ_ID, "order_type": "product", "loy_kg": loy, "items": list(items)}
    if loy:
        t["recipe_id"] = REC2_ID
    if qoralama:
        t["is_draft"] = True
    return t


def qyarat(*items, **kw):
    return lambda c: c.post("/api/orders?confirm_shortage=true", json=qtana(*items, **kw))


def qbuyurtma(*items, **kw):
    r = A.post("/api/orders?confirm_shortage=true", json=qtana(*items, **kw))
    assert r.status_code == 200, (r.status_code, r.text[:400])
    return js(r).get("id")


def produce_tana(uz=5):
    _n["d"] += 1
    return {"name": f"TM199 prof {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": uz, "is_coated": True,
            "penoplast_id": PENO_ID, "recipe_id": REC2_ID, "loy_kg": 5, "unit_price": 10000}


def _sh(a, b, kal, kim, rol=None):
    z0 = zaxiralar()
    return {"rol": rol or {}, "a": a, "b": b, "kal": kal, "kim": kim, "qosh": lambda: ozgarish(z0)}


def h_s1(u):
    D = qbuyurtma(qd(), qoralama=True)
    return _sh(lambda c: c.post(f"/api/orders/{D}/activate?confirm_shortage=true"), qyarat(qd()), "loy", "activate_draft_order")


def h_s2(u):
    O = qbuyurtma(qd())
    x = detal_idlari(O)[0]
    t = {"order_id": O, "order_item_id": x, "item_name": "TM199 brak", "quantity": 1, "unit": "metr", "reason": "Brak",
         "brak_sabab": "boshqa", "coating_applied": True}
    return _sh(lambda c: c.post("/api/returns", json=t), qyarat(qd()), "loy", "create_return_item")


def h_s3(u):
    return _sh(qyarat(qd()), lambda c: c.post("/api/finished/produce", json=produce_tana()), "peno", "api_create_order")


def h_s3b(u):
    r = A.post("/api/finished/produce", json=produce_tana())
    F = js(r).get("product_id")
    assert A.post(f"/api/finished/{F}/complete").status_code == 200
    return _sh(qyarat(qd()), lambda c: c.post(f"/api/finished/{F}/add", json={"quantity": 1}), "peno", "api_create_order", rol={"F": F})


def h_s4(u):
    O = qbuyurtma(qd())
    return _sh(lambda c: c.delete(f"/api/orders/{O}"), qyarat(qd()), "otm", "api_delete_order")


def h_s4c(u):
    G = yangi_tm(20, f"TM199 S4c {u}")
    O = qbuyurtma(qd(qoplama=False), detal(1, G), loy=0)
    return _sh(lambda c: c.delete(f"/api/orders/{O}"), qyarat(detal(1, G), qd(qoplama=False), loy=0), "otm", "api_delete_order",
               rol={"G": G})


def h_s5(u):
    D = qbuyurtma(qd(PENO_ID, qoplama=False), qd(P2_ID, qoplama=False), loy=0, qoralama=True)
    return _sh(lambda c: c.post(f"/api/orders/{D}/activate?confirm_shortage=true"),
               qyarat(qd(P2_ID, qoplama=False), qd(PENO_ID, qoplama=False), loy=0), "lm", "activate_draft_order")


def h_s5b(u):
    return _sh(qyarat(qd(qoplama=False), loy=0), qyarat(qd(qoplama=False), loy=0, prj=PRJ2_ID), "peno", "api_create_order")


def h_s6(u):
    O = qbuyurtma(qd(uz=4))
    x = detal_idlari(O)[0]
    ry = A.post("/api/deliveries", json={"order_id": O, "items": [{"order_item_id": x, "quantity": 2}]})
    assert ry.status_code == 200, (ry.status_code, ry.text[:300])
    return _sh(lambda c: c.post(f"/api/orders/{O}/ready?loy_kg=7"), lambda c: c.post("/api/finished/produce", json=produce_tana()),
               "tq", "complete_order")


def h_s8(u):
    G = yangi_tm(20, f"TM199 S8 {u}")
    O = qbuyurtma(detal(1, G), qd(qoplama=False), loy=0)
    D = qbuyurtma(detal(1, G), qd(qoplama=False), loy=0, qoralama=True)
    return _sh(lambda c: c.delete(f"/api/orders/{O}"), lambda c: c.post(f"/api/orders/{D}/activate?confirm_shortage=true"),
               "otm", "api_delete_order", rol={"G": G})


def h_s9(u):
    _n["pt"] += 1
    pt = js(A.post("/api/production/product-types", json={"name": f"TM199 S9 {_n['pt']}", "unit": "dona",
                                                          "input_template": "quantity_only", "pricing_formula": "unit_based"})).get("id")
    bom = js(A.post("/api/production/boms", json={"product_type_id": pt, "variant_name": "Asosiy", "batch_quantity": 1,
                                                  "items": [{"inventory_id": KLEY_ID, "quantity": 1},
                                                            {"inventory_id": PENO_ID, "quantity": 0.01}]})).get("id")
    pid = po_yarat(pt, bom, 1, qadamlar=("start",))
    D = qbuyurtma(qd(), qoralama=True)
    return _sh(lambda c: c.post(f"/api/production/orders/{pid}/complete"),
               lambda c: c.post(f"/api/orders/{D}/activate?confirm_shortage=true"), "lm", "complete_production_order")


def holat(h):
    r = {k: tm(v) for k, v in h["rol"].items()}
    if h.get("qosh"):
        r.update(h["qosh"]())
    return r


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K — qulf tartibi (manba): xomashyo `FOR NO KEY UPDATE`, o'chirishda `FOR UPDATE`; «Yakunlash» — guruh xomashyodan OLDIN")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_m_iqs, _m_iq, _m_del = manba(crud, "inventory_qulf_sorov"), manba(crud, "inventory_qulf"), manba(crud, "delete_item")
check("K1 `inventory_qulf_sorov`: odatda `with_for_update(key_share=True)`; faqat `ochirish=True` da oddiy `with_for_update()`",
      "ochirish: bool = False" in _m_iqs and tartibda(_m_iqs, "if ochirish:", ".with_for_update().first()",
                                                       ".with_for_update(key_share=True).first()"))
check("K2 `inventory_qulf` `ochirish` ni uzatadi; `delete_item` ikkala qulfi — `ochirish=True`",
      "inventory_qulf_sorov(db, q, ochirish=ochirish)" in _m_iq and _m_del.count("inventory_qulf(db, item_id, ochirish=True)") == 2)
check("K3 `delete_return_item`: qaytgan xomashyo qatori — `FOR NO KEY UPDATE`",
      ".populate_existing().with_for_update(key_share=True).first()" in manba(crud, "delete_return_item")
      and ".populate_existing().with_for_update().first()" not in manba(crud, "delete_return_item"))
check("K4 «Yakunlash»: `_tm_oldindan_qulf` (yangi partiya guruhi) → xomashyo qulfi (`inventory_qulf_sorov`) → guruh muvozanati",
      tartibda(manba(production_service, "complete_production_order"), "crud._tm_oldindan_qulf(db, [po.finished_product_id], company_id)",
               "crud.inventory_qulf_sorov(db, db.query(Inventory)", "crud._fp_qulf_guruh(db, [fp.id], company_id)"))
_xm = getattr(main, "_XOMASHYO_MARSHRUTLARI", frozenset())
from sqlalchemy import event as _ev199                # noqa: E402
from sqlalchemy.engine import Engine as _Eng199      # noqa: E402
from sqlalchemy.pool import Pool as _Pool199         # noqa: E402
check("K5 xomashyo navbati — ilova darajasidagi bog'liqlik (`_xomashyo_navbati_marshrut`) ro'yxatdan o'tgan; tinglovchilar: `after_begin`"
      " (yangi tranzaksiya belgisi), `before_cursor_execute` (dangasa navbat), commit / rollback / hovuzga qaytish (belgi tozalanadi)",
      lambda: any(getattr(d, "dependency", None) is getattr(main, "_xomashyo_navbati_marshrut", 0) for d in main.app.router.dependencies)
      and _ev199.contains(SessionLocal, "after_begin", crud._xomashyo_navbati_tranzaksiyada)
      and _ev199.contains(_Eng199, "before_cursor_execute", crud._xomashyo_navbati_bayonotda)
      and _ev199.contains(_Eng199, "commit", crud._xomashyo_navbati_yakun)
      and _ev199.contains(_Eng199, "rollback", crud._xomashyo_navbati_yakun)
      and _ev199.contains(_Pool199, "checkin", crud._xomashyo_navbati_qaytdi))
def _endpointlar(routes):
    """Ilova marshrutlari endpoint lari — ichki routerlar (`include_router` — FastAPI 0.14x da `_IncludedRouter`) bilan."""
    out = set()
    for r in routes:
        if hasattr(r, "endpoint"):
            out.add((getattr(r.endpoint, "__module__", ""), getattr(r.endpoint, "__name__", "")))
        elif getattr(r, "original_router", None) is not None:
            out |= _endpointlar(r.original_router.routes)
        elif getattr(r, "routes", None):
            out |= _endpointlar(r.routes)
    return out


_ep = _endpointlar(main.app.routes)
check("K6 ro'yxatdagi har marshrut ilovada BOR (nomi o'zgarsa — test yiqiladi)", _xm and _xm <= _ep, sorted(_xm - _ep))
check("K7 asosiy yo'llar navbatda: yaratish, tahrir, o'chirish, faollashtirish, «Tayyor», detal, brak / qaytarish, ishlab chiqarish, «+»,"
      " MRP boshlash / yakunlash, kirim",
      {("main", n) for n in ("api_create_order", "api_update_order", "api_delete_order", "api_activate_draft", "api_mark_order_ready",
                             "api_update_order_item", "api_delete_order_item", "api_create_return", "api_delete_return",
                             "api_record_finished_loss", "api_delete_finished_loss", "api_produce", "api_add_production",
                             "api_delete_finished", "api_finished_production_brak", "api_create_inventory_receipt",
                             "api_receipt_cancel", "api_restore_order")}
      | {("production_routes", "start_order"), ("production_routes", "complete_order")} <= _xm)


def _xomashyo_grafi():
    """Xomashyoga tegadigan o'zgartiruvchi marshrutlar (POST / PUT / PATCH / DELETE) — nom bo'yicha chaqiruv grafi (`work/k199/marshrut_xarita.py`
    bilan bir mantiq; ortig'i bilan — xavfsiz tomoni). Urug' — xomashyo qulfi yordamchilari va xomashyoni qulfsiz yangilaydigan joylar."""
    import ast
    import re
    urug = {"inventory_qulf_sorov", "inventory_qulf", "get_item_locked", "delete_return_item", "update_item", "add_item",
            "api_update_price", "api_update_min_stock", "api_set_default_penoplast", "update_stock", "purchase_stock",
            "get_or_create_loy_stock"}
    funk, marshrut = {}, []
    for f in ("crud.py", "services.py", "production_service.py", "main.py", "production_routes.py"):
        src = open(os.path.join(ROOT, f), encoding="utf-8").read()
        satr = src.splitlines()
        for n in ast.parse(src).body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funk.setdefault(n.name, []).append("\n".join(satr[n.lineno - 1:n.end_lineno]))
                for dec in n.decorator_list:
                    if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in ("post", "put", "patch", "delete")
                            and dec.args and isinstance(dec.args[0], ast.Constant)):
                        marshrut.append((f[:-3], n.name))
    nomlar = set(funk)
    chaq = {nom: {m.group(1) for b in tanalar for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", b)
                  if m.group(1) in nomlar and m.group(1) != nom} for nom, tanalar in funk.items()}
    tegadi = urug & nomlar
    yana = True
    while yana:
        yana = False
        for nom, ch in chaq.items():
            if nom not in tegadi and ch & tegadi:
                tegadi.add(nom)
                yana = True
    return {m for m in marshrut if m[1] in tegadi}


# Grafda bor, lekin ataylab navbatsiz (mustaqil tekshiruv 199 F5 — xomashyoga YETMAYDI: nom to'qnashuvi; navbat ostida uzoq ishlardi)
_ISTISNO = {
    ("main", "api_coating_notify"): "qoplamachiga 2 Telegram xabari — xomashyoga tegmaydi",
    ("main", "api_create_employee_advance"): "hodim avansi — oylik foyda hisoboti, xomashyoga tegmaydi",
    ("main", "api_confirm_advance_request"): "avans so'rovini tasdiqlash — oylik hisobot, xomashyoga tegmaydi",
    ("main", "api_close_employee_debt"): "hodim qarzini yopish — hisobot, xomashyoga tegmaydi",
    ("main", "api_close_gift_period"): "sovg'a davrini yopish — davr hisoboti, xomashyoga tegmaydi",
}
check("K8 TO'LIQLIK: xomashyoga tegadigan har o'zgartiruvchi marshrut (chaqiruv grafi) ro'yxatda yoki asosli istisnoda; istisnolar ro'yxatda "
      "emas (yangi marshrut ro'yxatga qo'shilmasa — test yiqiladi)",
      lambda: _xm and (_xomashyo_grafi() <= set(_xm) | set(_ISTISNO)) and not (set(_ISTISNO) & set(_xm)),
      lambda: (sorted(_xomashyo_grafi() - set(_xm) - set(_ISTISNO)), sorted(set(_ISTISNO) & set(_xm))))
check("K9 navbat bog'liqligi korxonani YON TA'SIRSIZ aniqlaydi (`_navbat_korxonasi` — faqat o'qish; `auth.get_current_user` emas: u bloklangan "
      "korxonada sessiyani yopib 403 beradi — bog'liqlik yutsa qorovul 401 «tizimga kiring» berardi)",
      lambda: "_navbat_korxonasi(request, db)" in manba(main, "_xomashyo_navbati_marshrut")
      and "get_current_user(" not in manba(main, "_xomashyo_navbati_marshrut")
      and not any(x in manba(main, "_navbat_korxonasi") for x in ("delete(", "commit(", "get_current_user(", "HTTPException")))
_BAYONOT = [("SELECT inventory.id FROM inventory WHERE inventory.id = %s", False),
            ("SELECT inventory.id FROM inventory WHERE inventory.id = %s FOR NO KEY UPDATE", True),
            ("SELECT finished_products.id FROM finished_products WHERE finished_products.id IN (%s) FOR UPDATE", True),
            ("SELECT id FROM inventory WHERE id = %s FOR KEY SHARE", True),
            ("SELECT pg_advisory_xact_lock(%s, %s)", True), ("SELECT pg_advisory_xact_lock(%s)", True),
            ("INSERT INTO activity_logs (action) VALUES (%s) RETURNING activity_logs.id", True),
            ("UPDATE inventory SET stock_quantity=%s WHERE inventory.id = %s", True), ("DELETE FROM order_items WHERE id = %s", True),
            ("WITH t AS (SELECT 1) UPDATE inventory SET min_stock = 0", True),
            ("SAVEPOINT sa_savepoint_1", True), ("/* izoh */ SAVEPOINT sa_savepoint_2", True),
            ("RELEASE SAVEPOINT sa_savepoint_1", False), ("ROLLBACK TO SAVEPOINT sa_savepoint_1", False),
            ("SELECT count(*) FROM pg_locks", False), ("SELECT nextval('orders_id_seq')", False), ("  select 1", False),
            ("WITH x AS (SELECT 1 AS a) SELECT a FROM x", False), ("(SELECT 1) UNION ALL (SELECT 2)", False), ("VALUES (1)", False),
            ("TABLE inventory", False), ("/* izoh */\nSET LOCAL lock_timeout = '1s'", False), ("SELECT pg_try_advisory_xact_lock(5)", True),
            ("-- izoh\nINSERT INTO activity_logs (action) VALUES (%s)", True), ("WITH y AS (DELETE FROM t RETURNING id) SELECT id FROM y", True)]
check("K10 navbat kerak bo'lgan bayonot (`crud.xomashyo_navbati_bayonotimi`): qator / advisory qulf, yozuv va SAVEPOINT — HA; o'qish (WITH-SELECT, "
      "UNION, VALUES, TABLE ham) va tranzaksiya boshqaruvi — YO'Q",
      lambda: all(crud.xomashyo_navbati_bayonotimi(b) is k for b, k in _BAYONOT),
      lambda: [(b, crud.xomashyo_navbati_bayonotimi(b)) for b, k in _BAYONOT if crud.xomashyo_navbati_bayonotimi(b) is not k])

check("K11 taklifni rasmiylashtirish buyurtma xabarlarini fon vazifasiga beradi (`bitta_tranzaksiya` ichida Telegram YO'Q); `update_order_loy` "
      "buyurtmani qulflab qayta o'qiydi (eski loy rejasi navbat ostida)",
      lambda: "background_tasks=background_tasks" in manba(main, "api_taklif_rasmiylashtir")
      and "_fonda(background_tasks, _send_telegram, msg" in manba(main, "api_create_order")
      and "_fonda(background_tasks, _tm_minus_xabari, db" in manba(main, "api_create_order")
      and tartibda(manba(crud, "update_order_loy"), "qoplama_retsepti_tekshir(", ".populate_existing()",
                   ".with_for_update(key_share=True).first()", "old_loy = services._get_planned_loy(order)"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    section("Y — [PG] qulf turi: xomashyo `inventory_qulf` ostida — boshqa ulanish KEY SHARE ni kutmaydi; `ochirish=True` da kutadi")

    def key_share_kutmaydimi(ochirish):
        """1-sessiya xomashyoni qulflaydi; 2-ulanish (lock_timeout 700 ms) `FOR KEY SHARE` oladimi."""
        s1 = SessionLocal()
        try:
            crud.inventory_qulf(s1, PENO_ID, 1, ochirish=ochirish) if ochirish else crud.inventory_qulf(s1, PENO_ID, 1)
            with engine.connect() as c2:
                c2.execute(text("SET lock_timeout = '700ms'"))
                try:
                    c2.execute(text("SELECT id FROM inventory WHERE id = :i FOR KEY SHARE"), {"i": PENO_ID}).all()
                    natija = True
                except Exception:          # noqa: BLE001
                    natija = False
                c2.rollback()
            return natija
        finally:
            s1.rollback()
            s1.close()
    check("Y1 `inventory_qulf` (odatiy) — boshqa ulanish tashqi kalit KEY SHARE ni darhol oladi (FOR NO KEY UPDATE)",
          lambda: key_share_kutmaydimi(False) is True)
    check("Y2 `inventory_qulf(ochirish=True)` — KEY SHARE kutadi (FOR UPDATE — o'chirish uchun)",
          lambda: key_share_kutmaydimi(True) is False)

    def navbat_bandmi():
        """Boshqa ulanishdan: korxona 1 ning xomashyo navbati (199, 1) BAND mi. XOM DBAPI ulanish — ilovaning SQLAlchemy hodisalari
        (dangasa navbat) bu tekshiruvga ta'sir qilmaydi (mutatsiyada eskirgan belgi kuzatuvchini osib qo'ymasin)."""
        rc = engine.raw_connection()
        try:
            cur = rc.cursor()
            cur.execute("SELECT pg_try_advisory_xact_lock(199, 1)")
            ol = bool(cur.fetchone()[0])
            cur.close()
            rc.rollback()
        finally:
            rc.close()
        return not ol
    _ichida = {}
    _asl_dio = services.deduct_inventory_for_order

    def _dio_tekshir(*a, **k):
        _ichida.setdefault("yaratish", navbat_bandmi())
        return _asl_dio(*a, **k)
    services.deduct_inventory_for_order = _dio_tekshir
    try:
        _ry = A.post("/api/orders?confirm_shortage=true", json=tana(oddiy_detal()))
    finally:
        services.deduct_inventory_for_order = _asl_dio
    check("Y3 buyurtma yaratish (ro'yxatdagi marshrut) ichida korxona xomashyo navbati BAND; so'rov tugagach — bo'sh",
          lambda: _ry.status_code == 200 and _ichida.get("yaratish") is True and navbat_bandmi() is False, (_ry.status_code, _ichida))

    def keyingi_tranzaksiyada():
        """(1-tranzaksiyada darhol, commit dan keyin bo'sh, keyingi tranzaksiya faqat o'qisa — navbatsiz, qulflovchi bayonotda — band,
        SAVEPOINT qaytarilgach ham — band, so'ng commit — bo'sh)."""
        s1 = SessionLocal()
        try:
            crud.xomashyo_navbati(s1, 1)
            bir = navbat_bandmi()
            s1.commit()
            bosh = navbat_bandmi()                         # commit — navbat bo'shadi
            s1.execute(text("SELECT stock_quantity FROM inventory WHERE id = :i"), {"i": PENO_ID})
            oqish = navbat_bandmi()                        # yangi tranzaksiya, faqat o'qish — navbatsiz (dangasa)
            s1.execute(text("SELECT id FROM inventory WHERE id = :i FOR NO KEY UPDATE"), {"i": PENO_ID})
            qulf = navbat_bandmi()                         # qulflovchi bayonotdan OLDIN navbat olindi
            _sp = s1.begin_nested()
            s1.execute(text("SELECT 1"))
            _sp.rollback()
            sp = navbat_bandmi()                           # SAVEPOINT qaytdi — tashqi tranzaksiya navbatni ushlab turibdi
            s1.commit()
            bosh2 = navbat_bandmi()
            # mustaqil tekshiruv v3 G3: keyingi tranzaksiyaning BIRINCHI qulfi SAVEPOINT ichida, so'ng savepoint qaytariladi — navbat
            # SAVEPOINT dan oldin tashqi darajada olingan bo'lishi kerak (aks holda PG uni savepoint bilan bo'shatadi)
            s1.execute(text("SELECT stock_quantity FROM inventory WHERE id = :i"), {"i": PENO_ID})
            _sp2 = s1.begin_nested()
            s1.execute(text("SELECT id FROM inventory WHERE id = :i FOR NO KEY UPDATE"), {"i": PENO_ID})
            _sp2.rollback()
            sp2 = navbat_bandmi()
            s1.commit()
            return bir, bosh, oqish, qulf, sp, bosh2, sp2, navbat_bandmi()
        finally:
            s1.rollback()
            s1.close()

    def belgisiz_sessiya():
        """Navbatli sessiya (2-tranzaksiyasi faqat o'qigan — belgi «olinmagan») yopilgach: hovuzdagi hech bir ulanishda belgi QOLMAGAN
        (commit / rollback / hovuzga qaytishda tozalanadi) va BELGISIZ sessiya qulflasa / yozsa navbat OLINMAYDI."""
        s1 = SessionLocal()
        try:
            crud.xomashyo_navbati(s1, 1)
            s1.commit()
            s1.execute(text("SELECT 1"))
            s1.commit()
        finally:
            s1.close()
        qolgan = [r.info.get(crud._XN_ULANISH) for r in list(engine.pool._pool.queue)]
        s2 = SessionLocal()
        try:
            s2.execute(text("SELECT id FROM inventory WHERE id = :i FOR NO KEY UPDATE"), {"i": PENO_ID})
            s2.execute(text("INSERT INTO error_logs (error_message) VALUES ('tm199 Y4c')"))
            return [x for x in qolgan if x is not None], navbat_bandmi()
        finally:
            s2.rollback()
            s2.close()

    _asl_poq = production_service._po_qulfli

    def _poq_tekshir(*a, **k):
        _ichida.setdefault("mrp", navbat_bandmi())
        return _asl_poq(*a, **k)
    _ptm, _pbm = mrp_turi()
    _pid_y = js(A.post("/api/production/orders", json={"product_type_id": _ptm, "bom_id": _pbm, "quantity": 1,
                                                       "source_type": "warehouse_stock"})).get("production_order", {}).get("id")
    production_service._po_qulfli = _poq_tekshir
    try:
        _rs = A.post(f"/api/production/orders/{_pid_y}/start")
    finally:
        production_service._po_qulfli = _asl_poq
    check("Y5 MRP «Boshlash» (ichki router marshruti) ichida ham navbat BAND (ilova bog'liqligi ichki routerga ham qo'llanadi)",
          lambda: _rs.status_code == 200 and _ichida.get("mrp") is True, (_rs.status_code, _rs.text[:200], _ichida))
    check("Y4 navbat 1-tranzaksiyada darhol; commit dan keyingi tranzaksiya faqat O'QISA — navbatsiz (javob o'qishi / Telegram navbatni "
          "ushlamaydi), birinchi qulflovchi bayonotdan OLDIN — olinadi; SAVEPOINT qaytishi navbatni bo'shatmaydi — keyingi tranzaksiyaning "
          "birinchi qulfi SAVEPOINT ichida bo'lsa ham (navbat SAVEPOINT dan oldin, tashqi darajada)",
          lambda: keyingi_tranzaksiyada() == (True, False, False, True, True, False, True, False), keyingi_tranzaksiyada)
    check("Y4c navbatli sessiya yopilgach hovuz ulanishlarida navbat belgisi QOLMAYDI; BELGISIZ sessiya qulflasa / yozsa ham navbat OLINMAYDI",
          lambda: belgisiz_sessiya() == ([], False), belgisiz_sessiya)

    # ── Y6 / Y7 / Y8: haqiqiy marshrutlar — har bayonot kuzatiladi (o'sha ulanishda `pg_locks`)
    _KUZ = {"qulf": [], "oqish": []}

    def _navbat_shu_ulanishda(conn):
        _c = conn.connection.dbapi_connection.cursor()
        try:
            _c.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND classid = 199 AND objid = 1 AND objsubid = 2 "
                       "AND granted AND pid = pg_backend_pid()")
            return int(_c.fetchone()[0]) > 0
        finally:
            _c.close()

    def _kuz_oldin(conn, cursor, statement, parameters, context, executemany):
        _h = conn.info.get(getattr(crud, "_XN_ULANISH", "-"))
        conn.info["_t199_oldin"] = None if _h is None else bool(_h[1])

    def _t_qulflovchi(statement):
        """Testning O'Z tasniflagichi (ilovanikidan mustaqil): qator / advisory qulf, yozuv yoki SAVEPOINT."""
        u = " ".join((statement or "").split()).upper()
        while u.startswith("(") or u.startswith("/*"):
            u = (u[1:] if u.startswith("(") else u[u.find("*/") + 2:] if "*/" in u else "").lstrip()
        if any(k in u for k in ("FOR UPDATE", "FOR NO KEY UPDATE", "FOR SHARE", "FOR KEY SHARE", "PG_ADVISORY", "PG_TRY_ADVISORY")):
            return True
        _b = u.split(" ", 1)[0] if u else ""
        if _b == "WITH":
            return any(f" {k} " in f" {u} " for k in ("INSERT", "UPDATE", "DELETE"))
        return _b in ("INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "SAVEPOINT")

    def _kuz_keyin(conn, cursor, statement, parameters, context, executemany):
        _old = conn.info.pop("_t199_oldin", None)
        if _old is None:
            return
        _bosh = " ".join((statement or "").split())[:70]
        if "pg_advisory_xact_lock" in (statement or "") and list(parameters or [])[:1] == [199]:
            return                                 # navbatning o'zi (1-tranzaksiya, bog'liqlik) — bayonot hali bajarilmagan
        if _t_qulflovchi(statement):
            _KUZ["qulf"].append((_bosh, _old, _navbat_shu_ulanishda(conn)))
        elif _old is False:
            _KUZ["oqish"].append((_bosh, _navbat_shu_ulanishda(conn)))

    _TG = []
    _asl_tg, _asl_tmx = main._send_telegram, main._tm_minus_xabari

    def _tg_kuzat(*a, **k):
        _TG.append(navbat_bandmi())
        return True

    def _tmx_kuzat(*a, **k):
        _TG.append(navbat_bandmi())
        return _asl_tmx(*a, **k)

    def y6_kuzat():
        """Marshrutlar: tahrir, yaratish, qoralamani faollashtirish, ishlab chiqarish, «+», o'chirish, «Tayyor» qisman, MRP «Yakunlash»,
        kirim → qator tahriri → hujjatni bekor qilish; «kam qoldiq» xabari (Telegram — commit dan keyin)."""
        def _kam(s):
            s.add(Inventory(company_id=1, item_name="TM199 KAM", unit="kg", stock_quantity=1, min_stock=10, price_per_unit=1000,
                            category="Kimyo"))
        db_ishi(_kam)
        kodlar = []
        main._send_telegram, main._tm_minus_xabari = _tg_kuzat, _tmx_kuzat
        # tartib: kuzatuvchi (oldin) → ilova (dangasa navbat) → kuzatuvchi (keyin); sinf darajasidagi `insert=True` tartibni
        # o'zgartirmaydi (SQLAlchemy 2.0.35 — O'LCHANGAN), shuning uchun ilova tinglovchisi qayta ulanadi
        _ev199.remove(_Eng199, "before_cursor_execute", crud._xomashyo_navbati_bayonotda)
        _ev199.listen(_Eng199, "before_cursor_execute", _kuz_oldin)
        _ev199.listen(_Eng199, "before_cursor_execute", crud._xomashyo_navbati_bayonotda)
        _ev199.listen(_Eng199, "before_cursor_execute", _kuz_keyin)
        try:
            for yasa in (h_tahrir, h_s1, h_s3, h_s3b, h_s4, h_s6, h_s9):
                h = yasa(f"Y6{yasa.__name__}")
                kodlar += [h["a"](A).status_code, h["b"](A).status_code]
            _sup = js(A.post("/api/suppliers", json={"name": "TM199 Y6 ta'minotchi", "phone": "+998901112233"})).get("id")
            _rk = A.post("/api/inventory/receipt", json={
                "items": [{"inventory_id": KLEY_ID, "quantity": 10, "price_per_unit": 1000}], "transport_cost": 0, "tushirish_cost": 0,
                "yuklash_cost": 0, "boshqa_cost": 0, "add_to_cost": False, "supplier_id": _sup, "document_number": None, "paid_now": 0,
                "notes": "TM199 Y6"})
            _kid = js(_rk).get("receipt_id")
            _xid = db_ishi(lambda d: d.execute(text("SELECT id FROM inventory_purchases WHERE receipt_id = :k"), {"k": _kid}).scalar())
            kodlar += [_rk.status_code, A.put(f"/api/inventory/purchases/{_xid}", json={"quantity": 15}).status_code,
                       A.post(f"/api/inventory/receipts/{_kid}/cancel").status_code]
            # taklif → rasmiylashtirish (buyurtma `bitta_tranzaksiya` ichida yaratiladi — mustaqil tekshiruv v3 G1)
            _rt = A.post("/api/takliflar", json={"mijoz": "TM199 Y6 mijoz", "telefon": None,
                                                 "buyurtma": {"order_type": "product", "items": [oddiy_detal()]}})
            _tid = (js(_rt).get("taklif") or {}).get("id")
            kodlar += [_rt.status_code, A.post(f"/api/takliflar/{_tid}/rasmiylashtir?confirm_shortage=true",
                                               json={"loyiha_id": PRJ_ID, "buyurtma": {"order_type": "product",
                                                                                       "items": [oddiy_detal()]}}).status_code]
            # loyli buyurtma tahriri (loy qadami — commit dan keyingi tranzaksiya)
            _ol = buyurtma(qd(), loy=10, rec=REC_ID)
            kodlar.append(A.put(f"/api/orders/{_ol}?confirm_shortage=true&loy_kg=12", json=tahrir_tana(_ol, {})).status_code)
        finally:
            _ev199.remove(_Eng199, "before_cursor_execute", _kuz_keyin)
            _ev199.remove(_Eng199, "before_cursor_execute", _kuz_oldin)
            main._send_telegram, main._tm_minus_xabari = _asl_tg, _asl_tmx
        return kodlar
    _Y6K = {}

    def _y6():
        if "k" not in _Y6K:
            _Y6K["k"] = y6_kuzat()
        return _Y6K["k"]
    check("Y6 haqiqiy marshrutlar (tahrir, yaratish, faollashtirish, ishlab chiqarish, «+», o'chirish, «Tayyor», MRP «Yakunlash», kirim / "
          "qator tahriri / bekor) — 200; HAR qulflovchi / yozuvchi bayonotda korxona navbati USHLANGAN (o'sha ulanishda `pg_locks`); "
          "commit dan keyingi tranzaksiyada dangasa olish ishlagan",
          lambda: all(k == 200 for k in _y6()) and len(_KUZ["qulf"]) > 0 and all(x[2] for x in _KUZ["qulf"])
          and any(x[1] is False for x in _KUZ["qulf"]),
          lambda: (_y6(), len(_KUZ["qulf"]), [x for x in _KUZ["qulf"] if not x[2]][:5], sum(1 for x in _KUZ["qulf"] if x[1] is False)))
    check("Y7 o'sha marshrutlarda commit dan keyingi (qulflovchi bayonotgacha) O'QISH bayonotlari navbatsiz",
          lambda: _y6() is not None and len(_KUZ["oqish"]) > 0 and not any(x[1] for x in _KUZ["oqish"]),
          lambda: (len(_KUZ["oqish"]), [x for x in _KUZ["oqish"] if x[1]][:5]))
    check("Y8 Telegram xabari («kam qoldiq», tayyor mahsulot minusi; buyurtma yaratish, tahrir, taklifni rasmiylashtirish) yuborilayotganda "
          "korxona navbati BO'SH (mustaqil tekshiruv 199 F1 / v3 G1: ilgari navbat xabar davomida ushlanib, boshqa amallar 2,6–5,6 s kutardi)",
          lambda: _y6() is not None and len(_TG) > 0 and not any(_TG), lambda: _TG)

    def xato_turi():
        """Dangasa navbat olinmasa (lock_timeout): xato SQLAlchemy `DBAPIError` turida, belgi «olinmagan» qoladi (mustaqil tekshiruv v3 G4).
        `lock_timeout` — BAZA darajasida (yangi ulanishlar; hovuz qayta ochiladi): bitta ipda ikkinchi sessiya navbatni ushlaganda hech
        bir kutish (mutatsiyada ham) cheksiz osilib qolmasin."""
        import sqlalchemy.exc as _sae
        _adm2 = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")

        def _lt(q):
            with _adm2.connect() as _c:
                _c.execute(_tx(f"ALTER DATABASE {PG_BAZA} {q}"))
            engine.dispose()
        _lt("SET lock_timeout = '1500ms'")
        s1, s2 = SessionLocal(), SessionLocal()
        try:
            crud.xomashyo_navbati(s1, 1)
            s1.commit()
            crud.xomashyo_navbati(s2, 1)                       # navbatni boshqa sessiya ushlaydi
            s1.execute(text("SELECT 1"))
            _ul = s1.connection()
            try:
                s1.execute(text("SELECT id FROM inventory WHERE id = :i FOR NO KEY UPDATE"), {"i": PENO_ID})
                tur = "xato yo'q"
            except Exception as e:     # noqa: BLE001
                tur = isinstance(e, _sae.DBAPIError)
            return tur, (_ul.info.get(crud._XN_ULANISH) or [None, None])[1]
        finally:
            for _s in (s1, s2):
                try:
                    _s.rollback()
                    _s.close()
                except Exception:      # noqa: BLE001
                    pass
            _lt("RESET lock_timeout")
            _adm2.dispose()
    check("Y9 dangasa navbat olinmasa (lock_timeout) — xato SQLAlchemy DBAPIError turida (ilovaning `except` lari ushlaydi), belgi «olinmagan»",
          lambda: xato_turi() == (True, False), xato_turi)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F — ketma-ket: natija (asl kod bilan bir xil — faqat qulf turi / tartibi o'zgardi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
F7 = h_tahrir("F")
_r = F7["a"](A)
check("F7 tahrir 200: oddiy detal 2 → 3 m — penoplast yana 0,01 blok yechildi; G 20 − 1 = 19",
      _r.status_code == 200 and holat(F7) == {"G": (19.0, 0.0), "peno": 0.01}, (_r.status_code, _r.text[:300], holat(F7)))
_r = F7["b"](A)
check("F7 keyin yangi buyurtma (G dan 1 + oddiy 2 m) 200: G 18, penoplast yana 0,02", _r.status_code == 200
      and holat(F7) == {"G": (18.0, 0.0), "peno": 0.03}, (_r.status_code, _r.text[:300], holat(F7)))

F11 = h_brak_peno("F")
_r = F11["a"](A)
check("F11 taqdirli (penoplast xomashyoli) brak bekori 200: T 3; taqdir xomashyosi 0,1 blok omborga qaytdi",
      _r.status_code == 200 and holat(F11) == {"T": (3.0, 0.0), "peno": -0.1}, (_r.status_code, _r.text[:300], holat(F11)))
_r = F11["b"](A)
check("F11 keyin buyurtma (T dan 1 + oddiy 2 m) 200: T 2, penoplast 0,02 yechildi", _r.status_code == 200
      and holat(F11) == {"T": (2.0, 0.0), "peno": -0.08}, (_r.status_code, _r.text[:300], holat(F11)))

F10 = h_brak_peno("F10", ikkinchi=True)
_n10 = holat(F10)
_r = F10["a"](A)
check("F10 2-nav faol (avval penoplastli «Tuzatildi» bekor qilingan) brak bekori 200: T 3, bo'sh 2-nav partiyasi o'chdi",
      _r.status_code == 200 and holat(F10)["T"] == (3.0, 0.0) and holat(F10)["N"] is None, (_r.status_code, _r.text[:300], _n10,
                                                                                         holat(F10)))

F2 = h_yakun_loy("F")
_r = F2["a"](A)
check("F2 «Yakunlash» 200: M 4 bo'sh partiya G ning 3 qarzini yopdi — G 0, M 1; KLEY 0,04 yechildi",
      _r.status_code == 200 and holat(F2) == {"G": (0.0, 0.0), "M": (1.0, 0.0), "kley": 0.04}, (_r.status_code, _r.text[:300], holat(F2)))
_r = F2["b"](A)
check("F2 keyin loyli buyurtma (G dan 1 + loy 10 kg) 200: M ning 1 i yopdi — M 0; KLEY yana 10", _r.status_code == 200
      and holat(F2) == {"G": (0.0, 0.0), "M": (0.0, 0.0), "kley": 10.04}, (_r.status_code, _r.text[:300], holat(F2)))

F5 = h_yakun_tahrir("F")
_r = F5["a"](A)
check("F5 «Yakunlash» 200: G −4 (5 + Oe dagi 1) ning hammasini M 4 yopdi — G 0, M 0; penoplast 0,04 yechildi",
      _r.status_code == 200 and holat(F5) == {"G": (0.0, 0.0), "M": (0.0, 0.0), "peno": 0.04}, (_r.status_code, _r.text[:300], holat(F5)))
_r = F5["b"](A)
check("F5 keyin tahrir (oddiy detal 2 → 3 m) 200: penoplast yana 0,01", _r.status_code == 200
      and holat(F5) == {"G": (0.0, 0.0), "M": (0.0, 0.0), "peno": 0.05}, (_r.status_code, _r.text[:300], holat(F5)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    section("P — [PG] parallel: A (kechikish bilan) ∥ B — 40P01 yo'q, ikkalasi 200, natija KETMA-KET bilan bir xil")
    CA, CB = mijoz(), mijoz()
    _KECH = {}

    def kechiktir(modul, nom, kalit, flush=False, keyin=False):
        """Bir martalik kechikish — faqat chaqiruv zanjirida `_KECH[kalit]` nomli funksiya (A ning yo'li) bo'lsa. `flush` QILINMAYDI
        (ilova sessiyasi `autoflush=False` — flush asl kodda yo'q tartibni yasardi)."""
        asl = getattr(modul, nom)

        def _uxla(a):
            v = _KECH.get(kalit)
            if not v:
                return
            f = sys._getframe(2)
            while f is not None and f.f_code.co_name != v:
                f = f.f_back
            if f is None:
                return
            _KECH[kalit] = False
            if flush and a and hasattr(a[0], "flush"):
                a[0].flush()
            time.sleep(2.0)

        def w(*a, **k):
            if not keyin:
                _uxla(a)
            r = asl(*a, **k)
            if keyin:
                _uxla(a)
            return r
        setattr(modul, nom, w)
        return asl
    _asl = {
        "adj": (services, "adjust_inventory_diff", kechiktir(services, "adjust_inventory_diff", "adj")),     # R7: guruhdan keyin, penoplast oldidan
        "tinv": (crud, "_taqdir_inv", kechiktir(crud, "_taqdir_inv", "tinv")),                              # R10 / R11: taqdir xomashyosi oldidan
        "fpg": (crud, "_fp_qulf_guruh", kechiktir(crud, "_fp_qulf_guruh", "fpg")),                          # R2 / R5: xomashyodan keyin, guruh oldidan
        "loy": (services, "deduct_loy_ingredients", kechiktir(services, "deduct_loy_ingredients", "loy")),    # S1 / S2
        "peno": (services, "deduct_inventory_for_order", kechiktir(services, "deduct_inventory_for_order", "peno")),   # S3 / S5b
        "otm": (crud, "_buyurtma_tm_oldindan_qulf", kechiktir(crud, "_buyurtma_tm_oldindan_qulf", "otm")),   # S4 / S4c / S8
        "lm": (crud, "log_movement", kechiktir(crud, "log_movement", "lm")),                                # S5 / S9
        "tq": (services, "return_inventory_for_order_partial", kechiktir(services, "return_inventory_for_order_partial", "tq")),  # S6
        "loyd": (services, "adjust_loy_diff", kechiktir(services, "adjust_loy_diff", "loyd")),              # P12 (v3 G2)
    }

    def deadlocks():
        with engine.connect() as c:
            c.execute(text("SELECT pg_stat_clear_snapshot()"))
            return int(c.execute(text("SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()")).scalar() or 0)

    def parallel(h):
        nat = {}

        def ish(nom, fn, c, kut):
            time.sleep(kut)
            try:
                r = fn(c)
                nat[nom] = (r.status_code, (r.text or "")[:160] if r.status_code != 200 else "")
            except Exception as e:         # noqa: BLE001
                nat[nom] = (599, f"{type(e).__name__}: {str(e)[:160]}")
        d0 = deadlocks()
        _KECH[h["kal"]] = h["kim"]
        ta = threading.Thread(target=ish, args=("A", h["a"], CA, 0.0))
        tb = threading.Thread(target=ish, args=("B", h["b"], CB, 0.5))
        ta.start()
        tb.start()
        ta.join(90)
        tb.join(90)
        _KECH[h["kal"]] = False
        time.sleep(1.0)
        return nat.get("A"), nat.get("B"), deadlocks() - d0

    def ketma_ket(h):
        ra, rb = h["a"](A), h["b"](A)
        return (ra.status_code, rb.status_code), holat(h)

    def p_tekshir(nom, izoh, yasa, b_izoh, n=2):
        _p = []
        for u in range(n):
            hk = yasa(f"{nom}k{u}")
            _st, _kut = ketma_ket(hk)
            hp = yasa(f"{nom}p{u}")
            _tr = " < ".join(k for k, _ in sorted(hp["rol"].items(), key=lambda kv: kv[1]))
            a, b, dl = parallel(hp)
            _p.append((_tr, a, b, dl, holat(hp), _st, _kut))
        check(f"{nom} {izoh} ({_p[0][0]}) ∥ {b_izoh}: 40P01 yo'q, ikkalasi 200; natija ketma-ket bilan bir xil",
              all(a is not None and b is not None and (a[0], b[0]) == (200, 200) and dl == 0 and st == (200, 200) and hol == kut
                  for _t, a, b, dl, hol, st, kut in _p), _p)

    p_tekshir("P7", "buyurtma tahriri (guruh → penoplast) — R7", h_tahrir, "o'sha guruhdan + oddiy detalli buyurtma (penoplast KEY SHARE)")
    p_tekshir("P11", "taqdirli (penoplast xomashyoli) brak bekori — R11", h_brak_peno, "shu partiyadan + oddiy detalli buyurtma")
    p_tekshir("P10", "2-nav faol, avval penoplastli taqdir bekor qilingan brak bekori — R10", lambda u: h_brak_peno(u, ikkinchi=True),
              "shu partiyadan + oddiy detalli buyurtma")
    p_tekshir("P2", "MRP «Yakunlash» (KLEY BOM; guruhda minus) — R2", h_yakun_loy, "o'sha guruhdan loyli (KLEY) buyurtma")
    p_tekshir("P5", "MRP «Yakunlash» (penoplast BOM; guruhda minus) — R5", h_yakun_tahrir, "o'sha guruhdan detalli buyurtma tahriri")
    p_tekshir("S1", "qoralamani faollashtirish (penoplast olingach kechikish)", h_s1, "qoplamali buyurtma yaratish")
    p_tekshir("S2", "qoplamali brak (penoplast olingach kechikish)", h_s2, "qoplamali buyurtma yaratish")
    p_tekshir("S3", "qoplamali yaratish (loy xomashyosi olingach kechikish)", h_s3, "ishlab chiqarish (penoplast → xomashyo)")
    p_tekshir("S3b", "qoplamali yaratish (loy xomashyosi olingach kechikish)", h_s3b, "tayyor mahsulotga «+»")
    p_tekshir("S4", "buyurtmani o'chirish (penoplast qaytgach kechikish)", h_s4, "qoplamali buyurtma yaratish")
    p_tekshir("S4c", "buyurtmani o'chirish [penoplast, tayyor mahsulot]", h_s4c, "yaratish [tayyor mahsulot, penoplast]")
    p_tekshir("S5", "ikki zichlikli [P1, P2] qoralamani faollashtirish", h_s5, "[P2, P1] buyurtma yaratish")
    p_tekshir("S5b", "loysiz buyurtma yaratish", h_s5b, "boshqa loyihada loysiz buyurtma yaratish (o'sha penoplast)")
    p_tekshir("S6", "«Tayyor» qisman (loy farqi — xomashyo qaytgach kechikish)", h_s6, "ishlab chiqarish (penoplast → xomashyo)")
    p_tekshir("S8", "buyurtmani o'chirish [tayyor mahsulot, penoplast]", h_s8, "[tayyor mahsulot, penoplast] qoralamani faollashtirish")
    p_tekshir("S9", "MRP «Yakunlash» (BOM [KLEY, penoplast])", h_s9, "qoplamali qoralamani faollashtirish")

    def h_loy(u):
        """Mustaqil tekshiruv v3 G2: loyli (100 % KLEY retsept) buyurtma, reja 10 kg. A — tahrir, loy 20 (kechikish `adjust_loy_diff` boshida);
        B — tahrir, loy 15. Holat: (yakuniy reja, yechilgan KLEY)."""
        O = buyurtma(qd(), loy=10, rec=REC_ID)

        def _tana(loy):
            t = tahrir_tana(O, {})
            t.update({"loy_kg": loy, "recipe_id": REC_ID})
            return t
        ta, tb = _tana(20), _tana(15)
        k0 = zaxira(KLEY_ID)

        def _reja():
            from models import Order as _O199
            return db_ishi(lambda d: round(float(services._get_planned_loy(d.get(_O199, O)) or 0), 4))
        return {"a": lambda c: c.put(f"/api/orders/{O}?confirm_shortage=true&loy_kg=20", json=ta),
                "b": lambda c: c.put(f"/api/orders/{O}?confirm_shortage=true&loy_kg=15", json=tb), "kal": "loyd", "kim": "update_order_loy",
                "holat": lambda: (_reja(), round(k0 - zaxira(KLEY_ID), 4))}

    def loy_tekshir(n=2):
        _r = []
        for u in range(n):
            ab = h_loy(f"ab{u}")
            _s_ab = (ab["a"](A).status_code, ab["b"](A).status_code)
            _k_ab = ab["holat"]()                      # darhol — keyingi buyurtmalar KLEY ni o'zgartirmasidan oldin
            ba = h_loy(f"ba{u}")
            _s_ba = (ba["b"](A).status_code, ba["a"](A).status_code)
            _k_ba = ba["holat"]()
            hp = h_loy(f"p{u}")
            a, b, dl = parallel(hp)
            _r.append((a, b, dl, hp["holat"](), _k_ab, _k_ba, _s_ab, _s_ba))
        return _r
    _lr = loy_tekshir()
    check("P12 bir buyurtmaning ikki PARALLEL loy tahriri (10 → 20 kechikish bilan ∥ 10 → 15): 40P01 yo'q, ikkalasi 200; yakuniy reja va yechilgan "
          "KLEY ketma-ket A → B yoki B → A bilan bir xil (ilgari eski reja navbatsiz o'qilib 15 kg yechilardi — mustaqil tekshiruv v3 G2)",
          all(a is not None and b is not None and (a[0], b[0]) == (200, 200) and dl == 0 and hol in (kab, kba)
              and sab == (200, 200) and sba == (200, 200) for a, b, dl, hol, kab, kba, sab, sba in _lr), _lr)
    for _m, _f, _a in reversed(list(_asl.values())):
        setattr(_m, _f, _a)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B — bloklangan korxona: ro'yxatdagi marshrut ham 403 va blok belgisi (mustaqil tekshiruv 199 F2) — OXIRIDA (korxona 1 bloklanadi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
import obuna as _obuna199                           # noqa: E402
from production_models import Company as _Co199     # noqa: E402
from datetime import datetime                      # noqa: E402
_CB1, _CB2 = mijoz(), mijoz()


def _blok(bormi):
    def f(s):
        _c = s.get(_Co199, 1)
        if _c is None:
            _c = _Co199(id=1, name="TM199 korxona")
            s.add(_c)
            s.flush()
        _c.bloklangan_at = datetime.utcnow() if bormi else None
    db_ishi(f)


_blok(True)
try:
    _rb1 = _CB1.post("/api/orders?confirm_shortage=true", json=tana(oddiy_detal()))
    _rb2 = _CB2.get("/api/orders")
finally:
    _blok(False)
_SABAB199 = _obuna199.blok_xabari(SessionLocal())[:40]
check("B1 bloklangan korxona — ro'yxatdagi marshrut (buyurtma yaratish): 403 va sababi («Korxonangiz hisobi vaqtincha to'xtatilgan…»; zip 199 "
      "1-variantida 401 «Iltimos, tizimga kiring» edi — sabab ko'rinmasdi)",
      _rb1.status_code == 403 and _SABAB199 in str(js(_rb1).get("detail")), (_rb1.status_code, _rb1.text[:200]))
check("B2 nazorat: ro'yxatdan tashqari marshrut (buyurtmalar ro'yxati) — 403 va sababi",
      _rb2.status_code == 403 and _SABAB199 in str(js(_rb2).get("detail")), (_rb2.status_code, _rb2.text[:200]))

print(f"\n{'=' * 70}\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
