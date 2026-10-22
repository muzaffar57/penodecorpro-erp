#!/usr/bin/env python3
"""
test_tm_qulf198.py — kech154 (zip 198 «Qulf tartibi — tayyor mahsulot qatorlari»; pasport 7-bo'lim OCHIQ (2) «QOLDI» va mustaqil tekshiruv
`work/k198/review198/HISOBOT.md`): tayyor mahsulot partiyasini YOZISHDAN / bitta-bitta qulflashdan OLDIN kerakli partiyalar va (guruhida
minus bo'lsa — yoki keyin guruh baribir qulflansa) guruhdoshlari BITTA o'tishda, id tartibida qulflanadi (`crud._tm_oldindan_qulf`,
`crud._buyurtma_tm_oldindan_qulf`): brak bekori (faol taqdiri bilan ham), MRP band ozod qilish, buyurtmani o'chirish, «Tayyor» (qisman),
yuk xati va uni o'chirish.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k198/probe198.py`, `probe198b.py`, zip 197 kodi, HAQIQIY PostgreSQL 16; ikki parallel so'rov,
bir martalik kechikish; sanoq `pg_stat_database.deadlocks`): har yo'lda shu guruhdan bir vaqtdagi buyurtma bilan 3 / 3 urinishda 40P01 —
tekshirilayotgan amal 500 («Serverda kutilmagan xato»; tranzaksiya qaytadi, ma'lumot buzilmaydi).
BO'LIMLAR: K — tartib (manba); Y — yordamchilar qaysi qatorlarni qulflaydi; F — ketma-ket natijalar (asl kod bilan AYNAN — xulq
o'zgarmagan); P — [faqat PG] parallel: 40P01 yo'q, ikkala so'rov 200, natija shu holatni KETMA-KET bajargandagi bilan bir xil (har
tekshiruv uchun ikki bir xil holat yasaladi). P4b / P4c / P4d — asl kodda ham o'tadi (yangi kodning qo'riqchilari).
Mustaqil tekshiruv v2 (`work/k198/review198/HISOBOT_v2.md`) sahnalari: P10 — R12 (taqdir xomashyosi KLEY bilan brak bekori ∥ shu detal
uchun ishlab chiqarishni «Boshlash»: asl kodda 0 — detal qulfi taqdir xomashyosidan oldinga o'tsa 3 / 3 — QO'RIQCHI), P11 — R13 (2-nav
taqdiri 2-nav guruhidagi minusni yopgan — yozuv guruhi; id T0 < T < N0 < N — asl 3 / 3; P11b — T0 < N0 < T < N, asl 0 — qo'riqchi;
P11c — o'sha, kechikish oldindan qulf bilan taqdir bekori orasida: yozuv partiyalari (`toliq`) OLDINDAN qulflanmasa 3 / 3 — mutatsiya
M23; asl kodda B oldin bajariladi va A 400 «shu hodisadan keyin chiqim bo'lgan» — zip 197 qoidasi, deadlock emas), P12 — R14 (yuk xati ∥ o'sha detal partiyasining brak bekori; asl
3 / 3), P13 — R16 (buyurtmani o'chirish ∥ unga bog'langan ishlab chiqarishni «Yakunlash»).
kech155 (`work/k198/probe198c.py` — DETALNI o'chirish yo'li, `DELETE /api/order-items/{id}`; mustaqil tekshiruv v3 —
`work/k198/review198/HISOBOT_v3.md`): P14 — R17 (detalni o'chirish ∥ «Yakunlash»), P15 — R18 (MRP band detalni o'chirish, guruhda minus ∥
guruhdan buyurtma; asl 3 / 3). P13 / P14 asl kodda O'TADI (asl kod M ni ishlab chiqarish buyurtmasidan KEYIN yozadi — `autoflush=False`;
kechikish ilgagi `flush` QILMAYDI — v3 N2) — ular zip 198 oldindan qulfining (P3 / P5) sherigi P8 / P9 ni qo'riqlaydi (P8 / P9 siz 3 / 3).
Ishlab chiqarish buyurtmasi bilan boshqa sheriklar (v3): P16 — R28 («Tayyor» qisman ∥ «Yakunlash»; asl 0, P6 bilan P10 siz 3 / 3), P17 /
P18 — R22 / R22b («Yakunlash» oldin ∥ detal / buyurtma o'chirish — teskari tartib; asl 0, P9 / P8 siz 3 / 3), P19 / P20 — R19 / R20
(detal / buyurtma o'chirish ∥ «Bekor qilish»; asl StaleDataError 500), P21 — R21 (detal o'chirish ∥ 2-ishlab chiqarishni «Boshlash»; asl
tashqi kalit 500), P22 / P22b — R27 / R27b (ishlab chiqarish YARATISH ∥ detal / buyurtma o'chirish; asl tashqi kalit 500), P23 — R27c (to'liq
tahrir detalni olib tashlaydi ∥ o'sha detalga yaratish; asl — detalsiz qoralama qoladi, ketma-ket esa yaratish 400).
MATERIAL ↔ GURUH tartibi (MRP yakuni, buyurtma tahriri ∥ yaratish, penoplast xomashyoli taqdir — R10 / R11) — bu zipda EMAS (pasport
7-bo'lim OCHIQ).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (baza nomi — `TM198_PG_BAZA`, bo'lmasa `tm_qulf198_test`); `TENANT_FILTER=1`.
Asl kodga (zip 197) qarshi K, Y va (PG da) P yiqiladi; F o'tadi.
ISHLATISH: python3 tools/test_tm_qulf198.py
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
PG_BAZA = os.environ.get("TM198_PG_BAZA") or "tm_qulf198_test"
_T = tempfile.mkdtemp(prefix="tm198_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tm198.db')}"
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
                    Recipe, RecipeIngredient, DeliveryItem, BrakTaqdir, Order)
from production_models import ProductionOrder      # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
YANGI = hasattr(crud, "_tm_oldindan_qulf")


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
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


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
    auth.create_user(s, "tm198_admin", PAROL, UserRole.ADMIN, "TM198 Admin", company_id=1)
PRJ = Project(company_id=1, client_name="TM198 Mijoz", project_name="TM198 loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="TM198 PENO", unit="blok", stock_quantity=100000, min_stock=0, is_penoplast=True,
                 volume_per_unit=1, price_per_unit=120000, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="TM198 KLEY", unit="kg", stock_quantity=100000, min_stock=0, price_per_unit=2000,
                 category="Kimyo")
s.add_all([PRJ, PENO, KLEY])
s.flush()
REC = Recipe(company_id=1, name="TM198 retsept", batch_size_kg=100.0)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
s.commit()
PRJ_ID, PENO_ID, KLEY_ID, REC_ID = PRJ.id, PENO.id, KLEY.id, REC.id
s.close()


def mijoz():
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    assert c.post("/login", data={"username": "tm198_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)
    return c


A = mijoz()
_n = {"d": 0, "pt": 0, "id": 950000}


def yangi_tm(miqdor, nom, birlik=1000, holat=ProductionStatus.READY, fid=None):
    def f(s):
        fp = FinishedProduct(company_id=1, name=nom, category="profil", is_coated=False, width=20, thickness=10,
                             quantity=miqdor, produced_quantity=max(miqdor, 0), unit="metr", unit_price=0,
                             cost_price=max(miqdor, 0) * birlik, unit_cost_stable=birlik, source=StockSource.PRODUCED,
                             penoplast_id=PENO_ID, unit_volume_m3=0.01, volume_m3=0.01 * max(miqdor, 0), production_status=holat,
                             reserved_quantity=0)
        if fid is not None:
            fp.id = fid
        s.add(fp)
        s.flush()
        return fp.id
    return db_ishi(f)


def katta_idli_tm(miqdor, nom):
    """Id i keyingi MRP partiyalaridan KATTA partiya (ikki o'tish tartibini aniq yasash uchun; PG — ketma-ketlik undan ancha past).
    SQLite yangi id ni «eng katta + 1» dan beradi — shuning uchun har safar mavjud eng kattasidan yuqori (tartib SQLite da ahamiyatsiz:
    parallel bo'lim faqat PG da)."""
    _eng = db_ishi(lambda s: s.query(FinishedProduct.id).order_by(FinishedProduct.id.desc()).first())
    _n["id"] = max(_n["id"] + 1, (int(_eng[0]) if _eng else 0) + 1000)
    return yangi_tm(miqdor, nom, fid=_n["id"])


def oddiy_detal():
    """Penoplastdan yasaladigan oddiy detal (tayyor mahsulotsiz) — buyurtma detali o'chirilganda bo'sh qolmasin."""
    _n["d"] += 1
    return {"name": f"TM198 oddiy {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": 2, "quantity": 1,
            "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID}


def detal(uz, fid):
    _n["d"] += 1
    return {"name": f"TM198 detal {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": uz, "quantity": 1,
            "unit_price": 20000, "is_coated": False, "penoplast_id": PENO_ID, "finished_product_id": fid}


def tana(*items, loy=0, rec=None):
    t = {"project_id": PRJ_ID, "order_type": "product", "loy_kg": loy, "items": list(items)}
    if rec:
        t["recipe_id"] = rec
    return t


def buyurtma(*items, loy=0, rec=None, c=None):
    r = (c or A).post("/api/orders?confirm_shortage=true", json=tana(*items, loy=loy, rec=rec))
    assert r.status_code == 200, (r.status_code, r.text[:400])
    return js(r).get("id")


def b_buyurtma(*items, loy=0, rec=None):
    """B: shu guruhdan buyurtma (guruh id tartibida qulflanadi) — `fn(c)`."""
    return lambda c: c.post("/api/orders?confirm_shortage=true", json=tana(*items, loy=loy, rec=rec))


def tm(fid):
    """(miqdor, band) — partiya o'chirilgan bo'lsa (masalan bekor qilingan taqdirning bo'sh partiyasi) None."""
    def f(s):
        x = s.get(FinishedProduct, fid)
        return None if x is None else (round(float(x.quantity), 4), round(float(x.reserved_quantity or 0), 4))
    return db_ishi(f)


def qarz(oid):
    return db_ishi(lambda s: round(sum(float(getattr(x, "fp_qarz", None) or 0)
                                       for x in s.query(OrderItem).filter(OrderItem.order_id == oid)), 4))


def kley():
    return db_ishi(lambda s: round(float(s.get(Inventory, KLEY_ID).stock_quantity), 4))


def detal_idlari(oid):
    return db_ishi(lambda s: [x.id for x in s.query(OrderItem).filter(OrderItem.order_id == oid).order_by(OrderItem.id)])


def mrp_turi(mat=None):
    """Har holatga ALOHIDA MRP turi (guruhlar bir-biriga aralashmasin). BOM — penoplast (yoki `mat` — masalan KLEY; xomashyo
    ishlab chiqarishda yechiladi)."""
    _n["pt"] += 1
    pt = js(A.post("/api/production/product-types", json={"name": f"TM198 Karniz {_n['pt']}", "unit": "dona",
                                                          "input_template": "quantity_only", "pricing_formula": "unit_based"})).get("id")
    bom = js(A.post("/api/production/boms", json={"product_type_id": pt, "variant_name": "Asosiy", "batch_quantity": 1,
                                                  "items": [{"inventory_id": mat or PENO_ID, "quantity": 0.01}]})).get("id")
    assert pt and bom, (pt, bom)
    return pt, bom


def mrp_detal(pt, soni, fid=None):
    _n["d"] += 1
    d = {"name": f"TM198 MRP {_n['d']}", "category": "mrp_product", "quantity": soni, "unit_price": 100000, "is_coated": False,
         "penoplast_id": None, "product_type_id": pt}
    if fid:
        d["finished_product_id"] = fid
    return d


def po_yarat(pt, bom, miqdor, oid=None, iid=None, qadamlar=("start", "complete")):
    """Ishlab chiqarish buyurtmasi (`qadamlar` — qaysi bosqichgacha: () — qoralama, ("start",) — jarayonda) — id i."""
    t = {"product_type_id": pt, "bom_id": bom, "quantity": miqdor, "source_type": "customer_order" if oid else "warehouse_stock"}
    if oid:
        t.update({"source_order_id": oid, "source_order_item_id": iid})
    r = A.post("/api/production/orders", json=t)
    pid = ((js(r) or {}).get("production_order") or {}).get("id")
    assert pid, (r.status_code, r.text[:300])
    for q in qadamlar:
        r1 = A.post(f"/api/production/orders/{pid}/{q}")
        assert r1.status_code == 200, (q, r1.status_code, r1.text[:300])
    return pid


def po(pt, bom, miqdor, oid=None, iid=None):
    pid = po_yarat(pt, bom, miqdor, oid, iid)
    return db_ishi(lambda s: s.get(ProductionOrder, pid).finished_product_id)


def po_holat(pid, oid=None, iid=None):
    """(holat, buyurtmaga bog'langanmi, detalga bog'langanmi) — id lar emas (parallel va ketma-ket nusxalarda id lar har xil)."""
    return db_ishi(lambda s: (s.get(ProductionOrder, pid).status,
                              s.get(ProductionOrder, pid).source_order_id is not None and s.get(ProductionOrder, pid).source_order_id == oid,
                              s.get(ProductionOrder, pid).source_order_item_id is not None
                              and s.get(ProductionOrder, pid).source_order_item_id == iid))


def berilgan(iid):
    return db_ishi(lambda s: round(sum(float(x.quantity or 0) for x in s.query(DeliveryItem).filter(DeliveryItem.order_item_id == iid)), 4))


def faol_taqdir_tm(loss_id):
    return db_ishi(lambda s: s.query(BrakTaqdir.tm_id).filter(BrakTaqdir.fp_loss_id == loss_id, BrakTaqdir.bekor_vaqti.is_(None)).scalar())


def buyurtma_holat(oid):
    """(o'chirilganmi, holati) — buyurtma butunlay o'chgan bo'lsa None."""
    return db_ishi(lambda s: None if s.get(Order, oid) is None else (bool(s.get(Order, oid).is_deleted),
                                                                   getattr(s.get(Order, oid).status, "value", s.get(Order, oid).status)))


def po_royxat(pt, oid, iid):
    """Shu MRP turidagi ishlab chiqarish buyurtmalari: (holat, buyurtmaga bog'langanmi, detalga bog'langanmi), id tartibida."""
    return db_ishi(lambda s: [(p.status, p.source_order_id is not None and p.source_order_id == oid,
                               p.source_order_item_id is not None and p.source_order_item_id == iid)
                              for p in s.query(ProductionOrder).filter(ProductionOrder.product_type_id == pt).order_by(ProductionOrder.id)])


def po_tm(pid):
    """Ishlab chiqarish buyurtmasining tayyor mahsuloti (miqdor, band) — hali yo'q bo'lsa None."""
    _f = db_ishi(lambda s: s.get(ProductionOrder, pid).finished_product_id)
    return tm(_f) if _f else None


def tahrir_tashla(oid, tashla):
    """To'liq tahrir tanasi — `tashla` indeksli detallar olib tashlanadi."""
    o = js(A.get(f"/api/orders/{oid}"))
    items = []
    for i, it in enumerate(o.get("items") or []):
        if i in tashla:
            continue
        dd = {k: it.get(k) for k in ("id", "name", "category", "quantity", "length", "width", "thickness", "unit_price", "is_coated",
                                     "penoplast_id", "finished_product_id", "product_type_id", "recipe_id")}
        items.append({k: v for k, v in dd.items() if v is not None})
    return {"project_id": PRJ_ID, "order_type": "product", "loy_kg": o.get("loy_kg") or 0, "items": items, "notes": o.get("notes")}


def brak(fid, soni, taqdir=None):
    t = {"finished_product_id": fid, "quantity": soni, "reason": "x", "brak_sabab": "boshqa"}
    if taqdir:
        t["taqdir"] = taqdir
    r = A.post("/api/finished/loss", json=t)
    assert r.status_code == 200, (r.status_code, r.text[:300])
    return js(r).get("loss_id")


def yuk(oid, *qatorlar):
    r = A.post("/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": i, "quantity": q} for i, q in qatorlar]})
    assert r.status_code == 200, (r.status_code, r.text[:300])
    return js(r).get("delivery_id")


# ── holatlar (har biri yangi guruh): {"rol": {nom: partiya id}, "o": buyurtma, "a": A(c), "b": B(c), "kal": kechikish, "kim": A funksiyasi} ──
def h_brak(u):
    """S1: G (kichik id) −4, T 0 (brak 3 — guruhda bo'sh qoldiq yo'q); A — brakni bekor qilish (T +3 → G ning 3 qarzi yopiladi)."""
    nom = f"TM198 S1 Karniz {u}"
    G = yangi_tm(0, nom)
    T = yangi_tm(3, nom)
    L = js(A.post("/api/finished/loss", json={"finished_product_id": T, "quantity": 3, "reason": "x", "brak_sabab": "boshqa"})).get("loss_id")
    O = buyurtma(detal(4, G))
    return {"rol": {"G": G, "T": T}, "o": O, "a": lambda c: c.delete(f"/api/finished/loss/{L}"), "b": b_buyurtma(detal(1, T)),
            "kal": "muv", "kim": "delete_finished_product_loss"}


def h_brak_taqdir(u):
    """R1: brakning faol taqdiri «Tuzatildi — o'sha joyiga» (T 3 → 0 → 3); buyurtma G dan 4 → G −1, T 0; A — brakni bekor qilish (taqdir
    bekori T ni qulflaydi — endi undan OLDIN guruh)."""
    nom = f"TM198 R1 Karniz {u}"
    G = yangi_tm(0, nom)
    T = yangi_tm(3, nom)
    rl = A.post("/api/finished/loss", json={"finished_product_id": T, "quantity": 3, "reason": "x", "brak_sabab": "boshqa",
                                            "taqdir": {"taqdir": "tuzatildi", "joy": "joyiga"}})
    assert rl.status_code == 200, (rl.status_code, rl.text[:300])
    L = js(rl).get("loss_id")
    O = buyurtma(detal(4, G))
    return {"rol": {"G": G, "T": T}, "o": O, "a": lambda c: c.delete(f"/api/finished/loss/{L}"), "b": b_buyurtma(detal(1, T)),
            "kal": "taqdir", "kim": "delete_finished_product_loss"}


def h_ozod(u):
    """S2: MRP — G (bo'sh partiya, kichik id) 2 → buyurtma 5 → G −3; M 4 — Oz detaliga band; A — Oz ni o'chirish (M ozod → G yopiladi)."""
    pt, bom = mrp_turi()
    G = po(pt, bom, 2)
    O = buyurtma(mrp_detal(pt, 5, G))
    Oz = buyurtma(mrp_detal(pt, 4))
    M = po(pt, bom, 4, Oz, detal_idlari(Oz)[0])
    return {"rol": {"G": G, "M": M}, "o": O, "a": lambda c: c.delete(f"/api/orders/{Oz}"), "b": b_buyurtma(mrp_detal(pt, 1, G)),
            "kal": "muv", "kim": "api_delete_order"}


def h_ochir_ikki(u):
    """R4: MRP guruhi (G2 bo'sh — eng kichik id, M — Oz ning MRP detaliga band) va ombor partiyasi S (id M dan KATTA); Oz: MRP detali +
    S dan 2; A — Oz ni o'chirish (ilgari: S guruhi, so'ng M — ikki o'tish); B — G2 va S dan (G2, M, S id tartibida)."""
    pt, bom = mrp_turi()
    G2 = po(pt, bom, 3)
    S = katta_idli_tm(10, f"TM198 R4 Karniz {u}")
    Oz = buyurtma(mrp_detal(pt, 4), detal(2, S))
    M = po(pt, bom, 4, Oz, detal_idlari(Oz)[0])
    return {"rol": {"G2": G2, "S": S, "M": M}, "o": Oz, "a": lambda c: c.delete(f"/api/orders/{Oz}"),
            "b": b_buyurtma(mrp_detal(pt, 1, G2), detal(1, S)), "kal": "ozod", "kim": "api_delete_order"}


def h_ochir_loy(u):
    """R3: G (bo'sh MRP partiya), Oz: MRP detali 4 + qoplama loyi (KLEY); M — Oz ga band; A — Oz ni o'chirish (ilgari: loy KLEY, so'ng
    M); B — G dan + loy (guruh {G, M}, so'ng KLEY)."""
    pt, bom = mrp_turi()
    G = po(pt, bom, 2)
    Oz = buyurtma(mrp_detal(pt, 4), loy=10, rec=REC_ID)
    M = po(pt, bom, 4, Oz, detal_idlari(Oz)[0])
    return {"rol": {"G": G, "M": M}, "o": Oz, "a": lambda c: c.delete(f"/api/orders/{Oz}"),
            "b": b_buyurtma(mrp_detal(pt, 1, G), loy=10, rec=REC_ID), "kal": "ozod", "kim": "api_delete_order"}


def h_tayyor(u):
    """R9: R4 holati, S detalidan 1 topshirilgan (qisman); A — «Tayyor» (qolgan S qaytadi — S guruhi, M band ozod)."""
    h = h_ochir_ikki(f"T{u}")
    Oz = h["o"]
    yuk(Oz, (detal_idlari(Oz)[1], 1))
    h.update({"a": lambda c: c.post(f"/api/orders/{Oz}/ready"), "kim": "complete_order"})
    return h


def h_yuk(u, mrp_avval=False, kal="yuk"):
    """S4: MRP — G bo'sh partiya 6; O1: D1 (MRP, 3 — M ga band), D2 (G dan 2); A — yuk xati D1 3 + D2 2. `mrp_avval` — M ning id si G dan
    kichik (ikkinchi tartib)."""
    pt, bom = mrp_turi()
    if mrp_avval:
        O1 = buyurtma(mrp_detal(pt, 3))
        d1 = detal_idlari(O1)[0]
        M = po(pt, bom, 3, O1, d1)
        G = po(pt, bom, 6)
        r2 = A.put(f"/api/orders/{O1}?confirm_shortage=true", json=dict(tana(
            dict(mrp_detal(pt, 3), id=d1, name=db_ishi(lambda s: s.get(OrderItem, d1).name)), mrp_detal(pt, 2, G)),
            notes=js(A.get(f"/api/orders/{O1}")).get("notes")))
        assert r2.status_code == 200, (r2.status_code, r2.text[:400])
        _ids = detal_idlari(O1)
    else:
        G = po(pt, bom, 6)
        O1 = buyurtma(mrp_detal(pt, 3), mrp_detal(pt, 2, G))
        _ids = detal_idlari(O1)
        M = po(pt, bom, 3, O1, _ids[0])
    tana_yuk = {"order_id": O1, "items": [{"order_item_id": _ids[0], "quantity": 3}, {"order_item_id": _ids[1], "quantity": 2}]}
    return {"rol": {"G": G, "M": M}, "o": O1, "a": lambda c: c.post("/api/deliveries", json=tana_yuk),
            "b": b_buyurtma(mrp_detal(pt, 1, G)), "kal": kal, "kim": "create_delivery"}


def h_yuk_ochir(u):
    """R6: MRP — G 2 → buyurtma 5 → G −3; O1 MRP detali 3 — M ga band; yuk xati 3 (M 0); A — yuk xatini o'chirish (M ga 3 qaytadi —
    ilgari M yozilib, keyin muvozanat guruhi)."""
    pt, bom = mrp_turi()
    G = po(pt, bom, 2)
    O = buyurtma(mrp_detal(pt, 5, G))
    O1 = buyurtma(mrp_detal(pt, 3))
    d1 = detal_idlari(O1)[0]
    M = po(pt, bom, 3, O1, d1)
    D = yuk(O1, (d1, 3))
    return {"rol": {"G": G, "M": M}, "o": O, "a": lambda c: c.delete(f"/api/deliveries/{D}"), "b": b_buyurtma(mrp_detal(pt, 1, G)),
            "kal": "muv", "kim": "delete_delivery"}


def h_boshlash(u):
    """R12 (mustaqil tekshiruv v2 V1 — v2 da detal qulfi taqdir xomashyosidan OLDINGA o'tgan edi; asl kodda 0 — QO'RIQCHI): MRP turi (BOM —
    KLEY); O: MRP detali D 6; T 4 — D ga band (D ga yana 2 kerak); T dan brak 1, taqdiri «Tuzatildi — o'sha joyiga» (xomashyo KLEY 1); D
    uchun 2-ishlab chiqarish buyurtmasi (qoralama, 2). A — brakni bekor qilish (taqdir xomashyosi KLEY, so'ng detal D); B — 2-ishlab
    chiqarishni «Boshlash» (KLEY, so'ng D). Qo'shimcha holat: KLEY o'zgarishi va 2-ishlab chiqarish holati."""
    pt, bom = mrp_turi(KLEY_ID)
    O = buyurtma(mrp_detal(pt, 6))
    D = detal_idlari(O)[0]
    T = po(pt, bom, 4, O, D)
    L = brak(T, 1, {"taqdir": "tuzatildi", "joy": "joyiga", "materiallar": [{"inventory_id": KLEY_ID, "miqdor": 1}]})
    pid2 = po_yarat(pt, bom, 2, O, D, qadamlar=())
    k0 = kley()
    return {"rol": {"T": T}, "o": O, "a": lambda c: c.delete(f"/api/finished/loss/{L}"),
            "b": lambda c: c.post(f"/api/production/orders/{pid2}/start"), "kal": "tinv", "kim": "delete_finished_product_loss",
            "qosh": lambda: {"kley": round(kley() - k0, 4), "po2": po_holat(pid2)[0]}}


def h_brak_2nav(u, t_avval=True):
    """R13 (mustaqil tekshiruv v2 — 2-nav taqdiri minusni yopgan, yozuv guruhi; asl 3 / 3): T0 3 → brak 2 «2-nav» (N0 2) → buyurtma N0 dan
    3 (N0 −1); T 3 → brak 2 «2-nav» (N — 2-nav guruhi; N0 ning 1 qarzini yopdi — `minus_yopdi` yozuvi). A — T brakini bekor qilish (N dan 2
    olinadi, N0 qarzdorga qaytadi; T ga 2 qaytadi); B — T0 guruhidan 1 va 2-nav guruhidan (N0) 1. `t_avval` — T0 va T avval yaratiladi
    (id: T0 < T < N0 < N — mustaqil tekshiruvdagi tartib, asl kodda 3 / 3); aks holda T0 < N0 < T < N (asl kodda ham 0 — qo'riqchi)."""
    nom = f"TM198 R13 Karniz {u}"
    T0 = yangi_tm(3, nom)
    T = yangi_tm(3, nom) if t_avval else None
    L0 = brak(T0, 2, {"taqdir": "ikkinchi_nav", "narx": 1000})
    N0 = faol_taqdir_tm(L0)
    O = buyurtma(detal(3, N0))
    if T is None:
        T = yangi_tm(3, nom)
    L = brak(T, 2, {"taqdir": "ikkinchi_nav", "narx": 1000})
    N = faol_taqdir_tm(L)
    _yoz = db_ishi(lambda s: s.query(BrakTaqdir.minus_yopdi).filter(BrakTaqdir.fp_loss_id == L, BrakTaqdir.bekor_vaqti.is_(None)).scalar())
    assert N0 and N and _yoz, (N0, N, _yoz)
    return {"rol": {"T0": T0, "T": T, "N0": N0, "N": N}, "o": O, "a": lambda c: c.delete(f"/api/finished/loss/{L}"),
            "b": b_buyurtma(detal(1, T0), detal(1, N0)), "kal": "taqdir", "kim": "delete_finished_product_loss",
            "qosh": lambda: {"qarz": qarz(O)}}


def h_yuk_brak(u):
    """R14 (mustaqil tekshiruv v2 V2; asl 3 / 3): MRP: O detali D 4, T 4 — D ga band; T dan brak 1 (T 3). A — D ning 2 sini yuk xatiga
    (partiya T, so'ng yuk xati qatori — detal D ga KEY SHARE); B — o'sha brakni bekor qilish (ilgari detal D FOR UPDATE, so'ng T)."""
    pt, bom = mrp_turi()
    O = buyurtma(mrp_detal(pt, 4))
    D = detal_idlari(O)[0]
    T = po(pt, bom, 4, O, D)
    L = brak(T, 1)
    tana_yuk = {"order_id": O, "items": [{"order_item_id": D, "quantity": 2}]}
    return {"rol": {"T": T}, "o": O, "a": lambda c: c.post("/api/deliveries", json=tana_yuk),
            "b": lambda c: c.delete(f"/api/finished/loss/{L}"), "kal": "mtq", "kim": "create_delivery",
            "qosh": lambda: {"berilgan": berilgan(D)}}


def h_ochir_yakun(u):
    """R16 (mustaqil tekshiruv v2 V3, v3 N2): MRP: Oz detali 4, ishlab chiqarish (jarayonda) — M 4 Oz ga band. A — Oz ni o'chirish
    (kechikish band ozod qilingach; zip 198 oldindan qulfi M ni ishlab chiqarish buyurtmasi yangilanishidan OLDIN oladi — P8 siz 3 / 3; asl
    kod M ni keyin yozadi — 0); B — o'sha ishlab chiqarishni «Yakunlash» (ishlab chiqarish buyurtmasi, so'ng M)."""
    pt, bom = mrp_turi()
    Oz = buyurtma(mrp_detal(pt, 4))
    d = detal_idlari(Oz)[0]
    pid = po_yarat(pt, bom, 4, Oz, d, qadamlar=("start",))
    M = db_ishi(lambda s: s.get(ProductionOrder, pid).finished_product_id)
    return {"rol": {"M": M}, "o": Oz, "d": d, "a": lambda c: c.delete(f"/api/orders/{Oz}"),
            "b": lambda c: c.post(f"/api/production/orders/{pid}/complete"), "kal": "ozodk", "kim": "api_delete_order",
            "qosh": lambda: {"po": po_holat(pid, Oz, d)}}


def h_detal_yakun(u):
    """R17 (kech155, `probe198c.py`, v3 N2): MRP: Oz — MRP detali d 4 + oddiy detal; ishlab chiqarish (jarayonda) — M 4 d ga band.
    A — d ni o'chirish (`DELETE /api/order-items/{id}`; zip 198 oldindan qulfi M ni ishlab chiqarish buyurtmasi yangilanishidan OLDIN
    oladi — P9 siz 3 / 3; asl kod — 0, guruhda minus bo'lsa 3 / 3); B — o'sha ishlab chiqarishni «Yakunlash»."""
    pt, bom = mrp_turi()
    Oz = buyurtma(mrp_detal(pt, 4), oddiy_detal())
    d = detal_idlari(Oz)[0]
    pid = po_yarat(pt, bom, 4, Oz, d, qadamlar=("start",))
    M = db_ishi(lambda s: s.get(ProductionOrder, pid).finished_product_id)
    return {"rol": {"M": M}, "o": Oz, "d": d, "a": lambda c: c.delete(f"/api/order-items/{d}"),
            "b": lambda c: c.post(f"/api/production/orders/{pid}/complete"), "kal": "ozodk", "kim": "delete_order_item",
            "qosh": lambda: {"po": po_holat(pid, Oz, d), "detallar": len(detal_idlari(Oz))}}


def h_detal_ochir(u):
    """R18 (kech155, `probe198c.py`; asl 3 / 3): MRP — G (bo'sh partiya, kichik id) 2 → buyurtma O 5 → G −3; Oz — MRP detali d 4 (M 4 d ga
    band) + oddiy detal. A — d ni o'chirish (M ozod → G yopiladi; ilgari M yozilib, keyin muvozanat guruhni qulflardi); B — G dan 1."""
    pt, bom = mrp_turi()
    G = po(pt, bom, 2)
    O = buyurtma(mrp_detal(pt, 5, G))
    Oz = buyurtma(mrp_detal(pt, 4), oddiy_detal())
    d = detal_idlari(Oz)[0]
    M = po(pt, bom, 4, Oz, d)
    return {"rol": {"G": G, "M": M}, "o": O, "a": lambda c: c.delete(f"/api/order-items/{d}"), "b": b_buyurtma(mrp_detal(pt, 1, G)),
            "kal": "muv", "kim": "delete_order_item", "qosh": lambda: {"qarz": qarz(O)}}


def _mrp_bilan(pt, bom, soni=4, qadamlar=("start",), oddiy=True, qosh_detal=None):
    """Oz — MRP detali d (`soni`) [+ oddiy detal] [+ `qosh_detal`]; d ga ishlab chiqarish (`qadamlar`) — (Oz, d, pid, M)."""
    _d = [mrp_detal(pt, soni)] + ([oddiy_detal()] if oddiy else []) + ([qosh_detal] if qosh_detal else [])
    Oz = buyurtma(*_d)
    d = detal_idlari(Oz)[0]
    pid = po_yarat(pt, bom, 4, Oz, d, qadamlar=qadamlar)
    M = db_ishi(lambda s: s.get(ProductionOrder, pid).finished_product_id)
    return Oz, d, pid, M


def h_tayyor_yakun(u):
    """R28 (mustaqil tekshiruv v3 N1 — P6 keltirib chiqargan; asl 0): MRP turi (BOM — KLEY); Oz — MRP detali d 4 (ishlab chiqarish
    jarayonda — M 4 d ga band), oddiy detal e (1 topshirilgan — qisman), «Loy sotish» 20 kg (retsept — KLEY). A — «Tayyor» (kechikish
    «Loy sotish» xomashyosi qaytishidan oldin; oldindan qulf M ni allaqachon olgan); B — o'sha ishlab chiqarishni «Yakunlash» (ishlab
    chiqarish buyurtmasi → KLEY → M)."""
    pt, bom = mrp_turi(KLEY_ID)
    _n["d"] += 1
    _ls = {"name": f"TM198 loy sotish {_n['d']}", "category": "loy_sotish", "quantity": 20, "unit_price": 5000, "is_coated": False,
           "penoplast_id": None, "recipe_id": REC_ID}
    Oz, d, pid, M = _mrp_bilan(pt, bom, qosh_detal=_ls)
    e = detal_idlari(Oz)[1]
    yuk(Oz, (e, 1))
    k0 = kley()
    return {"rol": {"M": M}, "o": Oz, "d": d, "a": lambda c: c.post(f"/api/orders/{Oz}/ready"),
            "b": lambda c: c.post(f"/api/production/orders/{pid}/complete"), "kal": "rli", "kim": "complete_order",
            "qosh": lambda: {"kley": round(kley() - k0, 4), "po": po_holat(pid, Oz, d), "buyurtma": buyurtma_holat(Oz)}}


def h_yakun_ochir(u, butun=False):
    """R22 / R22b (v3 — teskari tartib; asl 0, P9 / P8 siz 3 / 3): MRP turi (BOM — KLEY); Oz — MRP detali d 4 (ishlab chiqarish jarayonda,
    M 4 band). A — «Yakunlash» (kechikish ishlab chiqarish buyurtmasi va KLEY qulflangach, M yozilishidan oldin — `_qoshimcha_xarajat`);
    B — d ni (`butun` — buyurtmani) o'chirish."""
    pt, bom = mrp_turi(KLEY_ID)
    Oz, d, pid, M = _mrp_bilan(pt, bom)
    return {"rol": {"M": M}, "o": Oz, "d": d, "a": lambda c: c.post(f"/api/production/orders/{pid}/complete"),
            "b": (lambda c: c.delete(f"/api/orders/{Oz}")) if butun else (lambda c: c.delete(f"/api/order-items/{d}")),
            "kal": "qx", "kim": "complete_production_order",
            "qosh": lambda: {"po": po_holat(pid, Oz, d), "detallar": len(detal_idlari(Oz)), "buyurtma": buyurtma_holat(Oz)}}


def h_ochir_bekor(u, butun=False):
    """R19 / R20 (v3; asl StaleDataError 500): MRP — Oz detali d 4 (ishlab chiqarish jarayonda, M 4 band). A — d ni (`butun` — buyurtmani)
    o'chirish (kechikish band ozod qilingach); B — o'sha ishlab chiqarishni «Bekor qilish» (ishlab chiqarish buyurtmasi → M o'chadi)."""
    pt, bom = mrp_turi()
    Oz, d, pid, M = _mrp_bilan(pt, bom)
    return {"rol": {"M": M}, "o": Oz, "d": d,
            "a": (lambda c: c.delete(f"/api/orders/{Oz}")) if butun else (lambda c: c.delete(f"/api/order-items/{d}")),
            "b": lambda c: c.post(f"/api/production/orders/{pid}/cancel"), "kal": "ozodk",
            "kim": "api_delete_order" if butun else "delete_order_item",
            "qosh": lambda: {"po": po_holat(pid, Oz, d), "detallar": len(detal_idlari(Oz)), "buyurtma": buyurtma_holat(Oz)}}


def h_detal_boshlash(u):
    """R21 (v3; asl tashqi kalit 500): MRP — Oz detali d 6; 1-ishlab chiqarish (jarayonda) M 4 d ga band; 2-ishlab chiqarish (qoralama) 2.
    A — d ni o'chirish (kechikish band ozod qilingach); B — 2-ishlab chiqarishni «Boshlash» (yangi M2 d ga band bo'lardi)."""
    pt, bom = mrp_turi()
    Oz = buyurtma(mrp_detal(pt, 6), oddiy_detal())
    d = detal_idlari(Oz)[0]
    pid1 = po_yarat(pt, bom, 4, Oz, d, qadamlar=("start",))
    M = db_ishi(lambda s: s.get(ProductionOrder, pid1).finished_product_id)
    pid2 = po_yarat(pt, bom, 2, Oz, d, qadamlar=())
    return {"rol": {"M": M}, "o": Oz, "d": d, "a": lambda c: c.delete(f"/api/order-items/{d}"),
            "b": lambda c: c.post(f"/api/production/orders/{pid2}/start"), "kal": "ozodk", "kim": "delete_order_item",
            "qosh": lambda: {"po1": po_holat(pid1, Oz, d), "po2": po_holat(pid2, Oz, d), "m2": po_tm(pid2), "detallar": len(detal_idlari(Oz))}}


def h_yarat_ochir(u, butun=False):
    """R27 / R27b (v3 N4; asl tashqi kalit 500): MRP — Oz detali d 4 (ishlab chiqarishsiz). A — d ga ishlab chiqarish YARATISH (kechikish
    qator yozilgach, tranzaksiya yakunlanishidan oldin — `_po_jurnal`); B — d ni (`butun` — buyurtmani) o'chirish."""
    pt, bom = mrp_turi()
    Oz = buyurtma(mrp_detal(pt, 4), oddiy_detal())
    d = detal_idlari(Oz)[0]
    _t = {"product_type_id": pt, "bom_id": bom, "quantity": 4, "source_type": "customer_order", "source_order_id": Oz,
          "source_order_item_id": d}
    return {"rol": {}, "o": Oz, "d": d, "a": lambda c: c.post("/api/production/orders", json=_t),
            "b": (lambda c: c.delete(f"/api/orders/{Oz}")) if butun else (lambda c: c.delete(f"/api/order-items/{d}")),
            "kal": "pj", "kim": "create_production_order",
            "qosh": lambda: {"po": po_royxat(pt, Oz, d), "detallar": len(detal_idlari(Oz)), "buyurtma": buyurtma_holat(Oz)}}


def h_tahrir_yarat(u):
    """R27c (v3 N4; asl — detalsiz qoralama): MRP — Oz detali d 4 (ishlab chiqarishsiz) + oddiy detal. A — to'liq tahrir d ni olib tashlaydi
    (kechikish faol bog'lam tekshiruvidan KEYIN — `_mrp_faol_boglamlar`); B — d ga ishlab chiqarish yaratish. Ketma-ket: tahrir 200,
    yaratish 400 («detali topilmadi»)."""
    pt, bom = mrp_turi()
    Oz = buyurtma(mrp_detal(pt, 4), oddiy_detal())
    d = detal_idlari(Oz)[0]
    tb = tahrir_tashla(Oz, {0})
    _t = {"product_type_id": pt, "bom_id": bom, "quantity": 4, "source_type": "customer_order", "source_order_id": Oz,
          "source_order_item_id": d}
    return {"rol": {}, "o": Oz, "d": d, "a": lambda c: c.put(f"/api/orders/{Oz}?confirm_shortage=true", json=tb),
            "b": lambda c: c.post("/api/production/orders", json=_t), "kal": "mfbk", "kim": "update_order_full", "kod": (200, 400),
            "qosh": lambda: {"po": po_royxat(pt, Oz, d), "detallar": len(detal_idlari(Oz))}}


def holat(h):
    r = {k: tm(v) for k, v in h["rol"].items()}
    if h.get("qosh"):
        r.update(h["qosh"]())
    return r


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K — qulf tartibi (manba): kerakli qatorlar (guruhi bilan) partiyani yozishdan / bitta-bitta qulflashdan OLDIN")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_m_brak, _m_ozod, _m_yuk = (manba(crud, "delete_finished_product_loss"), manba(crud, "_auto_release_mrp_reservations"),
                            manba(crud, "create_delivery"))
_m_ochir, _m_tayyor, _m_yukochir = manba(main, "api_delete_order"), manba(services, "complete_order"), manba(crud, "delete_delivery")
check("K1 brak bekori: `_tm_oldindan_qulf` (partiya, faol taqdir partiyasi, yozuv guruhlari) → taqdir bekori → detal qulfi (asl joyida — "
      "taqdir xomashyosidan keyin) → partiya qulfi → muvozanat",
      tartibda(_m_brak, "_tm_oldindan_qulf(db, [loss.finished_product_id", "brak_taqdir_ochir(db, \"yoqotish\", loss",
               "_detal142 = _dq142.populate_existing().with_for_update().first()",
               "fp = fpq.populate_existing().with_for_update(key_share=True).first()", "_tm_muvozanat_kerak_bolsa("))
check("K2 MRP band ozod: `_tm_oldindan_qulf` band partiyalar yozilishidan va muvozanatdan OLDIN",
      tartibda(_m_ozod, "_tm_oldindan_qulf(db, _kq198[_c198], _c198)", "fp.reserved_quantity = 0.0", "_tm_muvozanat_kerak_bolsa("))
check("K3 yuk xati: MRP partiyalari (qulfsiz o'qish) va ombor detallari — bitta `_fp_qulf`, so'ng 1-o'tish (MRP) va 2-o'tish "
      "(tekshiruv qatorlari)",
      tartibda(_m_yuk, "_mrp_band_tmlar(db, _oi198, order.company_id, lock=False)", "_fp_qulf(db, _oldin198",
               "_mrp_tayyor_qoldiq(db, oi, order.company_id)", "_tm_yetkazish_kami(db, valid_items"))
check("K4 buyurtmani o'chirish: penoplast qaytishi → `_buyurtma_tm_oldindan_qulf` → tayyor mahsulot qaytishi → loy",
      tartibda(_m_ochir, "services.return_inventory_for_order(db, order)", "crud._buyurtma_tm_oldindan_qulf(db, order)",
               "crud._return_finished_for_order(db, order)", "services.return_loy_ingredients("))
check("K5 «Tayyor» (qisman): penoplast qaytishi → `_buyurtma_tm_oldindan_qulf` → tayyor mahsulot qaytishi → MRP band ozod",
      tartibda(_m_tayyor, "return_inventory_for_order_partial(", "_crud._buyurtma_tm_oldindan_qulf(db, order)",
               "_crud._return_finished_for_order(db, order)", "_crud._auto_release_mrp_reservations("))
check("K6 yuk xatini o'chirish: `_tm_oldindan_qulf` MRP partiyalari qaytishidan OLDIN",
      tartibda(_m_yukochir, "_mrp_olingan_oqi(di)", "_tm_oldindan_qulf(db, _oldin198, _cid)", "_mrp_deliver_stock(db, _oi"))
check("K7 buyurtmani o'chirish: bog'langan ishlab chiqarish buyurtmalari (id tartibida) — tayyor mahsulot va xomashyodan OLDIN",
      tartibda(_m_ochir, "with crud.bitta_tranzaksiya(db):", "_poq198.order_by(_PO198.id).with_for_update().all()",
               "services.return_inventory_for_order(db, order)", "crud._buyurtma_tm_oldindan_qulf(db, order)"))
check("K8 detalni o'chirish: buyurtma qulfi → bog'langan ishlab chiqarish buyurtmalari (id tartibida) → xomashyo → MRP band ozod",
      tartibda(manba(crud, "delete_order_item"), "_pul_qulfi(db, 101, db_item.order_id)",
               "_poq198d.order_by(_PO198d.id).with_for_update().all()", "services.adjust_inventory_diff(",
               "_auto_release_mrp_reservations(db, [db_item.id])"))
check("K9 «Tayyor» (qisman): bog'langan ishlab chiqarish buyurtmalari → penoplast → oldindan qulf → «Loy sotish» xomashyosi",
      tartibda(_m_tayyor, "if is_partial_completion:", "_poq198t.order_by(_PO198t.id).with_for_update().all()",
               "return_inventory_for_order_partial(", "_crud._buyurtma_tm_oldindan_qulf(db, order)",
               "partial_log.extend(return_loy_ingredients("))
check("K10 ishlab chiqarish yaratish: tekshiruv → buyurtma qulfi (101) → QAYTA tekshiruv → yozish",
      tartibda(manba(production_service, "create_production_order"), "_t = _yaratish_tekshiruvi(db, company_id, data)",
               "crud._pul_qulfi(db, 101, _oi198r.order_id)", "_t = _yaratish_tekshiruvi(db, company_id, data)", "db.add(po)"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Y — yordamchilar: qaysi qatorlar qulflanadi (`_fp_qulf` ga uzatilgani)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ush = []
_asl_fq = crud._fp_qulf


def _ush_fq(db, ids, company_id=None):
    _ush.append((sorted(int(i) for i in (ids or [])), company_id))
    return _asl_fq(db, ids, company_id)


def ushla(fn):
    _ush.clear()
    crud._fp_qulf = _ush_fq
    try:
        db_ishi(fn)
    finally:
        crud._fp_qulf = _asl_fq
    return list(_ush)


def oldindan(ids, cid=1, toliq=()):
    return ushla(lambda s: crud._tm_oldindan_qulf(s, ids, cid, toliq=toliq))


if YANGI:
    YG = yangi_tm(0, "TM198 Y Karniz")
    YT = yangi_tm(5, "TM198 Y Karniz")
    YX = yangi_tm(2, "TM198 Y Karniz")
    YJ = yangi_tm(4, "TM198 Y Karniz", holat=ProductionStatus.IN_PROGRESS)     # jarayonda — guruhdosh emas
    YB = yangi_tm(-3, "TM198 Y Boshqa")                                           # boshqa guruh (minusda)
    YC = yangi_tm(1, "TM198 Y Uchinchi")                                          # uchinchi guruh (minussiz)
    YC2 = yangi_tm(2, "TM198 Y Uchinchi")
    check("Y1 guruhda minus yo'q — faqat so'ralgan partiya", oldindan([YT]) == [([YT], 1)], oldindan([YT]))
    db_ishi(lambda s: setattr(s.get(FinishedProduct, YG), "quantity", -4.0))
    check("Y2 guruhda minus bor — tayyor guruhdoshlar bilan (jarayondagi va boshqa guruh — yo'q), bitta chaqiruv, id tartibida",
          oldindan([YT]) == [(sorted([YG, YT, YX]), 1)], (oldindan([YT]), YG, YT, YX, YJ, YB))
    check("Y3 bir nechta guruh — bitta o'tish (ikkala guruh, id tartibida); yo'q id — tashlanadi",
          oldindan([YB, YT, 9_999_999]) == [(sorted([YG, YT, YX, YB]), 1)], oldindan([YB, YT, 9_999_999]))
    check("Y4 korxona noma'lum — qulflanmaydi (eski chaqiruv)", oldindan([YT], None) == [], oldindan([YT], None))
    check("Y5 begona korxona — partiya topilmaydi, qulflanmaydi", oldindan([YT], 2) == [([], 2)], oldindan([YT], 2))
    check("Y6 `toliq` — minussiz guruh ham to'liq (shu o'tishda), qolganlari — odatdagidek",
          oldindan([YT], toliq=[YC]) == [(sorted([YG, YT, YX, YC, YC2]), 1)], (oldindan([YT], toliq=[YC]), YC, YC2))
    db_ishi(lambda s: setattr(s.get(FinishedProduct, YG), "quantity", 0.0))
    check("Y7 minus yo'qolgach — `toliq` dagi guruh to'liq, `fp_ids` dagisi faqat o'zi",
          oldindan([YT], toliq=[YC2]) == [(sorted([YT, YC, YC2]), 1)], oldindan([YT], toliq=[YC2]))
    db_ishi(lambda s: setattr(s.get(FinishedProduct, YB), "quantity", 0.0))
    _hy = h_ochir_ikki("Y")
    _yq = ushla(lambda s: crud._buyurtma_tm_oldindan_qulf(s, crud.get_order(s, _hy["o"], company_id=1), 1))
    check("Y8 `_buyurtma_tm_oldindan_qulf`: ombor detali partiyasi GURUHI bilan va MRP band partiya — bitta chaqiruv, id tartibida",
          _yq == [(sorted([_hy["rol"]["S"], _hy["rol"]["M"]]), 1)], (_yq, _hy["rol"]))
else:
    check("Y0 `crud._tm_oldindan_qulf` bor", False, "yo'q (asl kod)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F — ketma-ket: natija (asl kod bilan bir xil — faqat qulf tartibi o'zgardi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
F1 = h_brak("F")
check("F1 holat: G −4, T 0, buyurtma qarzi 4", (holat(F1), qarz(F1["o"])) == ({"G": (-4.0, 0.0), "T": (0.0, 0.0)}, 4.0),
      (holat(F1), qarz(F1["o"])))
_r = F1["a"](A)
check("F1 brak bekori 200: T +3 → G ning 3 qarzi yopildi — G −1, T 0, qarz 1",
      _r.status_code == 200 and (holat(F1), qarz(F1["o"])) == ({"G": (-1.0, 0.0), "T": (0.0, 0.0)}, 1.0),
      (_r.status_code, _r.text[:300], holat(F1), qarz(F1["o"])))
_r = F1["b"](A)
check("F1 keyin buyurtma T dan 1: T −1 (guruhda bo'sh qoldiq yo'q)", _r.status_code == 200 and tm(F1["rol"]["T"]) == (-1.0, 0.0),
      (_r.status_code, tm(F1["rol"]["T"])))

F5 = h_brak_taqdir("F")
check("F5 holat (taqdir «joyiga»): G −1, T 0 (T ning 3 i G ga ko'chdi), qarz 1",
      (holat(F5), qarz(F5["o"])) == ({"G": (-1.0, 0.0), "T": (0.0, 0.0)}, 1.0), (holat(F5), qarz(F5["o"])))
_r = F5["a"](A)
check("F5 taqdirli brakni bekor qilish 200: G −1, T 0 (o'sha miqdor o'sha partiyaga — sof o'zgarish 0), qarz 1",
      _r.status_code == 200 and (holat(F5), qarz(F5["o"])) == ({"G": (-1.0, 0.0), "T": (0.0, 0.0)}, 1.0),
      (_r.status_code, _r.text[:300], holat(F5), qarz(F5["o"])))
_r = F5["b"](A)
check("F5 keyin buyurtma T dan 1: T −1", _r.status_code == 200 and tm(F5["rol"]["T"]) == (-1.0, 0.0), (_r.status_code, tm(F5["rol"]["T"])))

F2 = h_ozod("F")
check("F2 holat: G −3, M 4 (band 4), buyurtma qarzi 3", (holat(F2), qarz(F2["o"])) == ({"G": (-3.0, 0.0), "M": (4.0, 4.0)}, 3.0),
      (holat(F2), qarz(F2["o"])))
_r = F2["a"](A)
check("F2 band buyurtma o'chirildi 200: M ozod → G yopildi — G 0, M 1 (bandsiz), qarz 0",
      _r.status_code == 200 and (holat(F2), qarz(F2["o"])) == ({"G": (0.0, 0.0), "M": (1.0, 0.0)}, 0.0),
      (_r.status_code, _r.text[:300], holat(F2), qarz(F2["o"])))
_r = F2["b"](A)
check("F2 keyin buyurtma G dan 1: M ning bo'sh 1 i yopdi — G 0, M 0", _r.status_code == 200 and holat(F2) == {"G": (0.0, 0.0),
                                                                                                        "M": (0.0, 0.0)},
      (_r.status_code, holat(F2)))

F6 = h_ochir_ikki("F")
check("F6 holat: G2 3, S 8 (2 Oz da), M 4 (band 4)", holat(F6) == {"G2": (3.0, 0.0), "S": (8.0, 0.0), "M": (4.0, 4.0)}, holat(F6))
_r = F6["a"](A)
check("F6 MRP + ombor detalli buyurtma o'chirildi 200: S 10 (qaytdi), M 4 (bandsiz), G2 3",
      _r.status_code == 200 and holat(F6) == {"G2": (3.0, 0.0), "S": (10.0, 0.0), "M": (4.0, 0.0)},
      (_r.status_code, _r.text[:300], holat(F6)))
_r = F6["b"](A)
check("F6 keyin buyurtma G2 1 + S 1: G2 2, S 9", _r.status_code == 200 and holat(F6) == {"G2": (2.0, 0.0), "S": (9.0, 0.0),
                                                                                        "M": (4.0, 0.0)}, (_r.status_code, holat(F6)))

F7 = h_ochir_loy("F")
_k0 = kley()
_r = F7["a"](A)
check("F7 loyli MRP buyurtma o'chirildi 200: M 4 (bandsiz), G 2; loy (KLEY) +10 qaytdi",
      _r.status_code == 200 and holat(F7) == {"G": (2.0, 0.0), "M": (4.0, 0.0)} and abs(kley() - _k0 - 10) < 1e-6,
      (_r.status_code, _r.text[:300], holat(F7), _k0, kley()))
_k0 = kley()
_r = F7["b"](A)
check("F7 keyin buyurtma G dan 1 + loy 10: G 1, KLEY −10", _r.status_code == 200 and holat(F7)["G"] == (1.0, 0.0)
      and abs(_k0 - kley() - 10) < 1e-6, (_r.status_code, holat(F7), _k0, kley()))

F8 = h_tayyor("F")
check("F8 holat: G2 3, S 8, M 4 (band 4); S detalidan 1 topshirilgan", holat(F8) == {"G2": (3.0, 0.0), "S": (8.0, 0.0), "M": (4.0, 4.0)},
      holat(F8))
_r = F8["a"](A)
check("F8 «Tayyor» (qisman) 200: S ning topshirilmagan 1 i qaytdi — S 9; M band ozod — M 4 (bandsiz)",
      _r.status_code == 200 and holat(F8) == {"G2": (3.0, 0.0), "S": (9.0, 0.0), "M": (4.0, 0.0)},
      (_r.status_code, _r.text[:300], holat(F8)))

F9 = h_yuk_ochir("F")
check("F9 holat: G −3, M 0 (3 yuk xatida)", holat(F9) == {"G": (-3.0, 0.0), "M": (0.0, 0.0)}, holat(F9))
_r = F9["a"](A)
check("F9 yuk xati o'chirildi 200: M ga 3 qaytdi (band 3) — G −3, M 3", _r.status_code == 200 and holat(F9) == {"G": (-3.0, 0.0),
                                                                                                            "M": (3.0, 3.0)},
      (_r.status_code, _r.text[:300], holat(F9)))

F10 = h_boshlash("F")
check("F10 holat (R12): T 4 (band 4 — brak 1 taqdir «joyiga» bilan qaytgan)", holat(F10) == {"T": (4.0, 4.0), "kley": 0.0, "po2": "draft"},
      holat(F10))
_r = F10["a"](A)
check("F10 taqdirli brak bekori 200: T 4 (band 4); KLEY +1 (taqdir xomashyosi qaytdi)",
      _r.status_code == 200 and holat(F10) == {"T": (4.0, 4.0), "kley": 1.0, "po2": "draft"}, (_r.status_code, _r.text[:300], holat(F10)))
_r = F10["b"](A)
check("F10 keyin 2-ishlab chiqarish «Boshlash» 200: holati «jarayonda»; KLEY o'zgarmaydi (xomashyo «Yakunlash» da yechiladi)",
      _r.status_code == 200 and holat(F10) == {"T": (4.0, 4.0), "kley": 1.0, "po2": "in_progress"},
      (_r.status_code, _r.text[:300], holat(F10)))

F11 = h_brak_2nav("F")
check("F11 holat (R13): T0 1, T 1, N0 0 (N ning 1 i N0 qarzini yopdi), N 1; buyurtma qarzi 0",
      holat(F11) == {"T0": (1.0, 0.0), "T": (1.0, 0.0), "N0": (0.0, 0.0), "N": (1.0, 0.0), "qarz": 0.0}, holat(F11))
_r = F11["a"](A)
check("F11 2-nav brak bekori 200: T 3 (2 qaytdi), N olindi (bo'sh 2-nav partiyasi o'chdi), N0 −1 (yopilgan qarz qaytdi), buyurtma qarzi 1",
      _r.status_code == 200 and holat(F11) == {"T0": (1.0, 0.0), "T": (3.0, 0.0), "N0": (-1.0, 0.0), "N": None, "qarz": 1.0},
      (_r.status_code, _r.text[:300], holat(F11)))
_r = F11["b"](A)
check("F11 keyin buyurtma T0 guruhidan 1 + N0 dan 1 200: T0 0, N0 −2",
      _r.status_code == 200 and {k: holat(F11)[k] for k in ("T0", "N0")} == {"T0": (0.0, 0.0), "N0": (-2.0, 0.0)},
      (_r.status_code, _r.text[:300], holat(F11)))

F12 = h_yuk_brak("F")
check("F12 holat (R14): T 3 (band 3 — brak 1), berilgan 0", holat(F12) == {"T": (3.0, 3.0), "berilgan": 0.0}, holat(F12))
_r = F12["a"](A)
check("F12 yuk xati D 2 200: T 1 (band 1), berilgan 2", _r.status_code == 200 and holat(F12) == {"T": (1.0, 1.0), "berilgan": 2.0},
      (_r.status_code, _r.text[:300], holat(F12)))
_r = F12["b"](A)
check("F12 keyin brak bekori 200: T 2 (band 2 — 1 qaytdi), berilgan 2",
      _r.status_code == 200 and holat(F12) == {"T": (2.0, 2.0), "berilgan": 2.0}, (_r.status_code, _r.text[:300], holat(F12)))

F13 = h_ochir_yakun("F")
check("F13 holat (R16): M 4 (jarayonda, band 4), ishlab chiqarish «jarayonda», buyurtmaga bog'langan",
      holat(F13) == {"M": (4.0, 4.0), "po": ("in_progress", True, True)}, holat(F13))
_r = F13["a"](A)
check("F13 buyurtma o'chirildi 200: M band ozod (4, bandsiz), ishlab chiqarish bog'lami uzildi",
      _r.status_code == 200 and holat(F13) == {"M": (4.0, 0.0), "po": ("in_progress", False, False)},
      (_r.status_code, _r.text[:300], holat(F13)))
_r = F13["b"](A)
check("F13 keyin «Yakunlash» 200: M 4 (bandsiz), ishlab chiqarish «tugallangan»",
      _r.status_code == 200 and holat(F13) == {"M": (4.0, 0.0), "po": ("completed", False, False)},
      (_r.status_code, _r.text[:300], holat(F13)))

F14 = h_detal_yakun("F")
check("F14 holat (R17): M 4 (jarayonda, band 4), ishlab chiqarish «jarayonda», detalga bog'langan; detallar 2",
      holat(F14) == {"M": (4.0, 4.0), "po": ("in_progress", True, True), "detallar": 2}, holat(F14))
_r = F14["a"](A)
check("F14 MRP detali o'chirildi 200: M band ozod (4, bandsiz), ishlab chiqarishning detal bog'lami uzildi; detallar 1",
      _r.status_code == 200 and holat(F14) == {"M": (4.0, 0.0), "po": ("in_progress", True, False), "detallar": 1},
      (_r.status_code, _r.text[:300], holat(F14)))
_r = F14["b"](A)
check("F14 keyin «Yakunlash» 200: M 4 (bandsiz), ishlab chiqarish «tugallangan»",
      _r.status_code == 200 and holat(F14) == {"M": (4.0, 0.0), "po": ("completed", True, False), "detallar": 1},
      (_r.status_code, _r.text[:300], holat(F14)))

F15 = h_detal_ochir("F")
check("F15 holat (R18): G −3, M 4 (band 4), buyurtma qarzi 3", holat(F15) == {"G": (-3.0, 0.0), "M": (4.0, 4.0), "qarz": 3.0}, holat(F15))
_r = F15["a"](A)
check("F15 MRP band detal o'chirildi 200: M ozod → G yopildi — G 0, M 1 (bandsiz), qarz 0",
      _r.status_code == 200 and holat(F15) == {"G": (0.0, 0.0), "M": (1.0, 0.0), "qarz": 0.0}, (_r.status_code, _r.text[:300], holat(F15)))
_r = F15["b"](A)
check("F15 keyin buyurtma G dan 1: M ning bo'sh 1 i yopdi — G 0, M 0",
      _r.status_code == 200 and holat(F15) == {"G": (0.0, 0.0), "M": (0.0, 0.0), "qarz": 0.0}, (_r.status_code, holat(F15)))

F16 = h_tayyor_yakun("F")
check("F16 holat (R28): M 4 (band 4), ishlab chiqarish jarayonda (buyurtma va detalga bog'langan); buyurtma faol",
      holat(F16) == {"M": (4.0, 4.0), "kley": 0.0, "po": ("in_progress", True, True), "buyurtma": (False, "in_progress")}, holat(F16))
_r = F16["a"](A)
check("F16 «Tayyor» (qisman) 200: M band ozod (4, bandsiz); «Loy sotish» qolgan 20 kg — KLEY +20; buyurtma «Tayyor»",
      _r.status_code == 200 and holat(F16) == {"M": (4.0, 0.0), "kley": 20.0, "po": ("in_progress", True, True),
                                               "buyurtma": (False, "ready")}, (_r.status_code, _r.text[:300], holat(F16)))
_r = F16["b"](A)
check("F16 keyin «Yakunlash» 200: KLEY −0,04 (4 × 0,01), ishlab chiqarish «tugallangan», M 4 (bandsiz)",
      _r.status_code == 200 and holat(F16) == {"M": (4.0, 0.0), "kley": 19.96, "po": ("completed", True, True),
                                               "buyurtma": (False, "ready")}, (_r.status_code, _r.text[:300], holat(F16)))

F17 = h_ochir_bekor("F")
_r = F17["a"](A)
check("F17 MRP detali o'chirildi 200 (R19): M band ozod (4, bandsiz), ishlab chiqarishning detal bog'lami uzildi; detallar 1",
      _r.status_code == 200 and holat(F17) == {"M": (4.0, 0.0), "po": ("in_progress", True, False), "detallar": 1,
                                               "buyurtma": (False, "in_progress")}, (_r.status_code, _r.text[:300], holat(F17)))
_r = F17["b"](A)
check("F17 keyin «Bekor qilish» 200: jarayondagi M o'chdi, ishlab chiqarish «bekor qilingan»",
      _r.status_code == 200 and holat(F17) == {"M": None, "po": ("cancelled", True, False), "detallar": 1,
                                               "buyurtma": (False, "in_progress")}, (_r.status_code, _r.text[:300], holat(F17)))

F18 = h_yarat_ochir("F")
_r = F18["a"](A)
check("F18 MRP detaliga ishlab chiqarish yaratildi 200 (R27): qoralama, buyurtma va detalga bog'langan",
      _r.status_code == 200 and holat(F18) == {"po": [("draft", True, True)], "detallar": 2, "buyurtma": (False, "in_progress")},
      (_r.status_code, _r.text[:300], holat(F18)))
_r = F18["b"](A)
check("F18 keyin detal o'chirildi 200: qoralamaning detal bog'lami uzildi; detallar 1",
      _r.status_code == 200 and holat(F18) == {"po": [("draft", True, False)], "detallar": 1, "buyurtma": (False, "in_progress")},
      (_r.status_code, _r.text[:300], holat(F18)))

F19 = h_tahrir_yarat("F")
_r = F19["a"](A)
check("F19 to'liq tahrir MRP detalini olib tashladi 200 (R27c): detallar 1, ishlab chiqarish yo'q",
      _r.status_code == 200 and holat(F19) == {"po": [], "detallar": 1}, (_r.status_code, _r.text[:300], holat(F19)))
_r = F19["b"](A)
check("F19 keyin o'sha detalga ishlab chiqarish yaratish 400 («detali topilmadi»), hech narsa yozilmadi",
      _r.status_code == 400 and "topilmadi" in _r.text and holat(F19) == {"po": [], "detallar": 1},
      (_r.status_code, _r.text[:300], holat(F19)))

for _nom, _mav in (("F4", False), ("F4b", True)):
    F4 = h_yuk(_nom, mrp_avval=_mav)
    _tartib = "G < M" if F4["rol"]["G"] < F4["rol"]["M"] else "M < G"
    check(f"{_nom} holat ({_tartib}): G 4, M 3 (band 3)", holat(F4) == {"G": (4.0, 0.0), "M": (3.0, 3.0)}, holat(F4))
    _r = F4["a"](A)
    check(f"{_nom} yuk xati 200: MRP detali 3 (M dan) + ombor detali 2 — M 0, G 4 (o'zgarmaydi — olingan buyurtma yaratishda)",
          _r.status_code == 200 and holat(F4) == {"G": (4.0, 0.0), "M": (0.0, 0.0)}, (_r.status_code, _r.text[:300], holat(F4)))
    _r = F4["b"](A)
    check(f"{_nom} keyin buyurtma G dan 1: G 3", _r.status_code == 200 and tm(F4["rol"]["G"]) == (3.0, 0.0),
          (_r.status_code, tm(F4["rol"]["G"])))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    section("P — [PG] parallel: A (kechikish bilan) ∥ B (shu guruhdan buyurtma) — 40P01 yo'q, ikkalasi 200, natija KETMA-KET bilan bir xil")
    CA, CB = mijoz(), mijoz()
    _KECH = {}

    def kechiktir(modul, nom, kalit, flush=True, keyin=False):
        """Bir martalik kechikish — faqat chaqiruv zanjirida `_KECH[kalit]` nomli funksiya (A ning yo'li) bo'lsa."""
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
        "muv": (crud, "_tm_muvozanat_kerak_bolsa", kechiktir(crud, "_tm_muvozanat_kerak_bolsa", "muv")),
        "yuk": (crud, "_tm_yetkazish_kami", kechiktir(crud, "_tm_yetkazish_kami", "yuk", flush=False)),
        "yuk1": (crud, "_mrp_tayyor_qoldiq", kechiktir(crud, "_mrp_tayyor_qoldiq", "yuk1", flush=False)),   # 1-o'tish boshida
        "taqdir": (crud, "brak_taqdir_ochir", kechiktir(crud, "brak_taqdir_ochir", "taqdir", keyin=True)),  # taqdir bekoridan KEYIN
        "taqdir0": (crud, "brak_taqdir_ochir", kechiktir(crud, "brak_taqdir_ochir", "taqdir0", flush=False)),   # oldindan qulf → taqdir bekori
        "ozod": (crud, "_auto_release_mrp_reservations", kechiktir(crud, "_auto_release_mrp_reservations", "ozod")),
        # mustaqil tekshiruv v2 sahnalari (`review198/s/rv198.py` dagi joylar):
        "tinv": (crud, "_taqdir_inv", kechiktir(crud, "_taqdir_inv", "tinv")),            # R12: brak bekori — taqdir xomashyosidan OLDIN
        "mtq": (crud, "_mrp_tayyor_qoldiq", kechiktir(crud, "_mrp_tayyor_qoldiq", "mtq", flush=False, keyin=True)),  # R14: partiya qulflangach
        # R16 / R17: band ozod qilingach (ilgak `flush` QILMAYDI — ilova sessiyasi `autoflush=False`; flush asl kodda yo'q tartibni
        # yasardi — mustaqil tekshiruv v3 N2)
        "ozodk": (crud, "_auto_release_mrp_reservations",
                  kechiktir(crud, "_auto_release_mrp_reservations", "ozodk", flush=False, keyin=True)),
        "rli": (services, "return_loy_ingredients", kechiktir(services, "return_loy_ingredients", "rli", flush=False)),   # R28
        "qx": (production_service, "_qoshimcha_xarajat", kechiktir(production_service, "_qoshimcha_xarajat", "qx")),    # R22 / R22b
        "pj": (production_service, "_po_jurnal", kechiktir(production_service, "_po_jurnal", "pj")),                   # R27 / R27b
        "mfbk": (crud, "_mrp_faol_boglamlar", kechiktir(crud, "_mrp_faol_boglamlar", "mfbk", keyin=True)),            # R27c
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

    def p_tekshir(nom, izoh, yasa, n=2, b_izoh="guruhdan buyurtma"):
        """Parallel ∥ ketma-ket: 40P01 yo'q; javob kodlari — ketma-ketdagi bilan (odatda 200 / 200; holat `kod` bergan bo'lsa — o'sha);
        natija — ketma-ket bilan bir xil."""
        _p = []
        for u in range(n):
            hk = yasa(f"{nom}k{u}")
            _st, _kut = ketma_ket(hk)
            hp = yasa(f"{nom}p{u}")
            _tr = " < ".join(k for k, _ in sorted(hp["rol"].items(), key=lambda kv: kv[1]))
            a, b, dl = parallel(hp)
            _p.append((_tr, a, b, dl, holat(hp), _st, _kut))
        _kod = hk.get("kod") or (200, 200)
        _kmatn = "ikkalasi 200" if _kod == (200, 200) else f"javoblar {_kod[0]} / {_kod[1]} (ketma-ketdagi kabi)"
        check(f"{nom} {izoh} ({_p[0][0]}) ∥ {b_izoh}: 40P01 yo'q, {_kmatn}; natija ketma-ket bilan bir xil",
              all(a is not None and b is not None and (a[0], b[0]) == _kod and dl == 0 and st == _kod and hol == kut
                  for _t, a, b, dl, hol, st, kut in _p), _p)

    p_tekshir("P1", "brak bekori (asl kodda 3 / 3 deadlock)", h_brak)
    p_tekshir("P2", "MRP band buyurtmani o'chirish", h_ozod)
    p_tekshir("P4", "yuk xati (MRP + ombor detali; kechikish 2-o'tish boshida)", lambda u: h_yuk(u))
    p_tekshir("P4b", "yuk xati (M < G; kechikish 2-o'tish boshida)", lambda u: h_yuk(u, mrp_avval=True))
    p_tekshir("P4c", "yuk xati (kechikish 1-o'tish boshida)", lambda u: h_yuk(u, kal="yuk1"))
    p_tekshir("P4d", "yuk xati (M < G; kechikish 1-o'tish boshida)", lambda u: h_yuk(u, mrp_avval=True, kal="yuk1"))
    p_tekshir("P5", "taqdirli («joyiga») brak bekori", h_brak_taqdir)
    p_tekshir("P6", "MRP + ombor detalli buyurtmani o'chirish (ikki o'tish)", h_ochir_ikki)
    p_tekshir("P7", "loyli MRP buyurtmani o'chirish (loy → M)", h_ochir_loy)
    p_tekshir("P8", "«Tayyor» (qisman; ikki o'tish)", h_tayyor)
    p_tekshir("P9", "yuk xatini o'chirish (M → guruh)", h_yuk_ochir)
    p_tekshir("P10", "taqdir xomashyosi (KLEY) bilan brak bekori — R12 (asl kodda ham 0; detal qulfi xomashyodan keyin)", h_boshlash,
              b_izoh="shu detal uchun ishlab chiqarishni «Boshlash» (KLEY → detal)")
    p_tekshir("P11", "2-nav taqdiri minusni yopgan brak bekori — R13 (yozuv guruhi)", h_brak_2nav,
              b_izoh="T guruhi + 2-nav guruhidan buyurtma")
    p_tekshir("P11b", "2-nav taqdiri minusni yopgan brak bekori (boshqa id tartibi)", lambda u: h_brak_2nav(u, t_avval=False),
              b_izoh="T guruhi + 2-nav guruhidan buyurtma")
    # P11c — yozuv guruhi (`toliq`) OLDINDAN qulflanadimi: kechikish oldindan qulf bilan taqdir bekori ORASIDA, id: T0 < N0 < T < N (B — T0,
    # N0, T, N). `toliq` siz A T va N ni ushlab, keyin N0 ni (bekor rejasi) so'rardi — B N0 ni ushlab T ni kutadi. Asl kodda o'tadi
    # (oldindan qulf yo'q — kechikishda A partiyalarni ushlamaydi).
    p_tekshir("P11c", "2-nav taqdiri minusni yopgan brak bekori (kechikish taqdir bekoridan OLDIN; yozuv guruhi oldindan)",
              lambda u: dict(h_brak_2nav(u, t_avval=False), kal="taqdir0"), b_izoh="T guruhi + 2-nav guruhidan buyurtma")
    p_tekshir("P12", "yuk xati (partiya → detal) — R14", h_yuk_brak, b_izoh="o'sha partiyaning brak bekori")
    p_tekshir("P13", "buyurtmani o'chirish (ishlab chiqarish buyurtmasi oldindan) — R16", h_ochir_yakun,
              b_izoh="unga bog'langan ishlab chiqarishni «Yakunlash»")
    p_tekshir("P14", "detalni o'chirish (ishlab chiqarish buyurtmasi oldindan) — R17", h_detal_yakun,
              b_izoh="unga bog'langan ishlab chiqarishni «Yakunlash»")
    p_tekshir("P15", "MRP band detalni o'chirish (guruhda minus; M → guruh) — R18", h_detal_ochir)
    p_tekshir("P16", "«Tayyor» (qisman; «Loy sotish» KLEY) — R28 (asl kodda ham 0)", h_tayyor_yakun,
              b_izoh="unga bog'langan ishlab chiqarishni «Yakunlash» (KLEY → M)")
    p_tekshir("P17", "«Yakunlash» (KLEY qulflangach kechikish) — R22 (asl kodda ham 0)", h_yakun_ochir, b_izoh="o'sha MRP detalini o'chirish")
    p_tekshir("P18", "«Yakunlash» (KLEY qulflangach kechikish) — R22b (asl kodda ham 0)", lambda u: h_yakun_ochir(u, butun=True),
              b_izoh="o'sha buyurtmani o'chirish")
    p_tekshir("P19", "MRP detalini o'chirish — R19", h_ochir_bekor, b_izoh="unga bog'langan ishlab chiqarishni «Bekor qilish»")
    p_tekshir("P20", "buyurtmani o'chirish — R20", lambda u: h_ochir_bekor(u, butun=True),
              b_izoh="unga bog'langan ishlab chiqarishni «Bekor qilish»")
    p_tekshir("P21", "MRP detalini o'chirish — R21", h_detal_boshlash, b_izoh="shu detal uchun 2-ishlab chiqarishni «Boshlash»")
    p_tekshir("P22", "MRP detaliga ishlab chiqarish yaratish — R27", h_yarat_ochir, b_izoh="o'sha detalni o'chirish")
    p_tekshir("P22b", "MRP detaliga ishlab chiqarish yaratish — R27b", lambda u: h_yarat_ochir(u, butun=True),
              b_izoh="o'sha buyurtmani o'chirish")
    p_tekshir("P23", "to'liq tahrir MRP detalini olib tashlaydi — R27c", h_tahrir_yarat, b_izoh="o'sha detalga ishlab chiqarish yaratish")
    # teskari tartibda tiklanadi (bir funksiya ikki marta o'ralgan — «ozod» / «ozodk», «yuk1» / «mtq»)
    for _m, _f, _a in reversed(list(_asl.values())):
        setattr(_m, _f, _a)

print(f"\n{'=' * 70}\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
