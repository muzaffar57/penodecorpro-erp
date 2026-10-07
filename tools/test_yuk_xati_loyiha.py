#!/usr/bin/env python3
"""
test_yuk_xati_loyiha.py — kech124 (zip 144): loyiha sahifasida «Yuk xatlari», yuk xati raqami LOYIHA bo'yicha, «Jamlab olish».

NIMA UCHUN KERAK (egasi, 2026-10-06 16:24–16:37 — QARORLAR, QAYTA SO'RALMAYDI)
-----------------------------------------------------------------------------
(1) Loyiha ichidan har yuk xatini olish — O'LCHANGAN: `templates/projects.html` da yuk xati UMUMAN yo'q edi (faqat buyurtma ichida,
    `orders.html` yuk xati tarixi). Endi loyiha sahifasida «Yuk xatlari» bo'limi: loyihaning HAMMA buyurtmalari yuk xatlari bitta
    ro'yxatda — raqam, sana, berilgan detallar (miqdor + birlik), summa, har qatorda 📄 (buyurtmadagi yuk xati PDF i).
(2) Yuk xati raqami LOYIHA bo'yicha davom etadi, ko'rinishi «ORD-001-2/Y-6» (buyurtma raqami qoladi; «PRJ-001/Y-6» — RAD). O'LCHANGAN:
    `crud.create_delivery` raqamni BUYURTMA bo'yicha berardi (shu buyurtma yuklarining eng kattasi + 1, `orders.oxirgi_yuk_seq`) — ikkinchi
    buyurtmaning birinchi yuki yana «/Y-1». ESKI raqamlar O'ZGARMAYDI (mijozga qog'oz berilgan); o'chirilgan raqam qayta berilmaydi
    (QAROR «A»); bir loyihaning ikki buyurtmasiga BIR VAQTDA yuk xati — takror raqam yo'q (loyiha qatori qulfi, PostgreSQL).
(3) «Jamlab olish»: belgilangan (standart — hammasi) yuk xatlaridagi BIR XIL detallar bitta qatorda, jami miqdor bilan (Y-1 100 m karniz +
    Y-2 50 m = 150 m); bir xil = nom, o'lcham, qoplama, birlik, birlik narxi; varaqda «miqdor, birlik narxi, summa va jami summa»
    («Faqat miqdor» — RAD); pastida kirgan yuk xatlari (raqam, sana). Buyurtmadagi «Hisob-kitob varaqasi» har yuk xatini alohida bo'lim
    qiladi, jamlamaydi va faqat bitta buyurtma — o'zgarmadi.

BO'LIMLAR
---------
  S  statik: `projects.oxirgi_yuk_seq`, loyiha qulfi (`FOR NO KEY UPDATE`) va uning TARTIBI `create_delivery` da (tayyor mahsulot
     chiqimidan keyin, to'lov va loyiha «To'langan» summasidan oldin), marshrutlar va ruxsati, sahifa bo'limi, migratsiya;
  R  raqam (API): egasining misoli (5 yuk — Y-1…Y-5, ikkinchi buyurtma — Y-6, Y-7), eski raqamlar o'zgarmaydi, o'rtadagi / oxirgi yuk
     o'chirilsa — qayta berilmaydi, BUTUNLAY o'chirilgan buyurtmaning raqami ham; boshqa loyiha va begona korxona — o'zicha; takroriy
     yuborish; «Tayyor» dagi avtomatik yuk xati; eski (zip 144 dan oldingi) ma'lumotda — buyurtmalar raqamlaridan davom etadi;
  M  yangilanish: `projects.oxirgi_yuk_seq` siz baza → ustun qo'shiladi va mavjud yuk xatlaridan to'ldiriladi
     (`main._migrate_loyiha_yuk_seq`, IDEMPOTENT) — eski buyurtmaning oxirgi yuki o'chirilsa ham raqami qayta berilmaydi;
  P  PostgreSQL parallel (faqat `PG_URL`): bir loyihaning ikki buyurtmasiga bir vaqtda yuk xati (sekin commit bilan poyga, 8 oqim) —
     raqamlar takrorlanmaydi va ketma-ket; aralash yuklama (buyurtma yaratish + «Tayyor» + to'lovli yuk xati + to'lov) — xatosiz
     (deadlock yo'q);
  L  «Yuk xatlari» ro'yxati API: loyihaning hamma buyurtmalari (begona loyiha yo'q), tartib, summalar (tiyin), qaysi buyurtmalar (loyiha
     pul hisobi qoidasi), begona korxona — 404, ruxsatsiz rol — 403, so'rovlar soni buyurtma / yuk xati soniga bog'liq emas;
  J  «Jamlab olish» varag'i: jamlash qoidasi (nom / tur / o'lcham / qoplama / birlik / narx), miqdor, narx, summa va JAMI qo'lda hisob
     bilan, belgilangan qism, kirgan yuk xatlari, PDF matni (kutubxonasiz o'qiladi), begona / noma'lum / noto'g'ri id, «<» va «&»,
     korxona nomi, yarim so'm yaxlitlash (brauzer jami bilan aynan);
  U  sahifa (Chromium, 1440 va 390 px, yorug' / tungi): bo'lim, belgilash, «Tanlangan» jami, «Jamlab olish» havolasi, 📄 belgilashni
     o'zgartirmaydi, U-13 qoidalari (`tools/test_u13.py` o'lchov JS i), yon tomonga surilish yo'q, ruxsatsiz rolda bo'lim yo'q, bo'sh loyiha.

REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16 (+ P bo'limi); `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 143) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_yuk_xati_loyiha.py
"""
import os
import io
import re
import sys
import glob
import time
import zlib
import base64
import socket
import inspect
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = os.environ.get("YXL_PG_BAZA", "yuk_xati_loyiha_test")
_T = tempfile.mkdtemp(prefix="yxl_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'yuk_xati_loyiha.db')}"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402
    import schemas                                 # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import (UserRole, Inventory, Order, OrderItem, OrderStatus, Delivery, DeliveryItem, Project)   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import event, text as T            # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                              # noqa: BLE001
        return None


class _Xato:
    """HTTP chaqiruvi istisno bersa (asl / buzilgan kodda) — test QULAMASIN: 599."""
    status_code = 599
    content = b""
    text = ""
    headers = {}

    def __init__(self, e):
        self.text = f"{type(e).__name__}: {e}"

    def json(self):
        return {"xato": self.text}


def req(c, metod, url, **k):
    try:
        return getattr(c, metod)(url, **k)
    except Exception as e:                         # noqa: BLE001
        return _Xato(e)


def tartibda(src, *qismlar):
    """Qismlar src ichida AYNAN shu tartibda uchraydimi (find — topilmasa False)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def manba(obj):
    try:
        return inspect.getsource(obj) if obj is not None else ""
    except (TypeError, OSError):
        return ""


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except OSError:
        return ""


def tiyin(v):
    """So'm → butun tiyin (HALF_UP, `models.pul_tiyin` bilan bir xil)."""
    return int(Decimal(repr(float(v))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)


def som_hu(t):
    """Butun tiyin → «1 234 567» (butun so'mga HALF_UP — brauzer `Math.round` bilan bir)."""
    v = int((Decimal(int(t)) / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{v:,}".replace(",", " ")


# ── PDF o'quvchi (kutubxonasiz; `tools/test_pdf_matn.py` bilan AYNAN bir usul) ─────────────────────────────────────
def _oqim(tana):
    lugat, _, qolgan = tana.partition(b"stream")
    data = qolgan[2:] if qolgan.startswith(b"\r\n") else qolgan[1:]
    m = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", lugat)
    data = data[:int(m.group(1))] if m else data[:data.rfind(b"endstream")].rstrip(b"\r\n")
    if b"ASCII85Decode" in lugat:
        data = re.sub(rb"\s", b"", data)
        if data.startswith(b"<~"):
            data = data[2:]
        if data.endswith(b"~>"):
            data = data[:-2]
        data = base64.a85decode(data)
    if b"FlateDecode" in lugat:
        data = zlib.decompress(data)
    return lugat, data


def _satr(b):
    chiq, i = bytearray(), 0
    while i < len(b):
        c = b[i]
        if c == 0x5C and i + 1 < len(b):
            n = b[i + 1]
            if 0x30 <= n <= 0x37:
                j = i + 1
                while j < len(b) and j < i + 4 and 0x30 <= b[j] <= 0x37:
                    j += 1
                chiq.append(int(b[i + 1:j], 8) & 0xFF)
                i = j
                continue
            chiq.append({ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}.get(n, n))
            i += 2
            continue
        chiq.append(c)
        i += 1
    return bytes(chiq)


_PDF_TOKEN = re.compile(rb"%[^\r\n]*|\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/\[\]()<>{}%]*|[^\s/\[\]()<>{}%]+", re.S)


def _bt_bloklar(data):
    blok = None
    for m in _PDF_TOKEN.finditer(data):
        tok = m.group(0)
        if tok.startswith(b"%"):
            continue
        if tok == b"BT":
            blok = []
        elif tok == b"ET":
            if blok is not None:
                yield blok
            blok = None
        elif blok is not None:
            blok.append(tok)


def pdf_satrlar(bayt):
    """Har `BT … ET` bloki — bitta satr (jadval katagi — alohida satr)."""
    obyektlar = {int(n): tana for n, tana in re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", bayt or b"", re.S)}
    shriftlar = {}
    for tana in obyektlar.values():
        nom = re.search(rb"/Name\s*/([^\s/>\[]+)", tana)
        if b"/Type /Font" not in tana or not nom:
            continue
        cmap = None
        tu = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", tana)
        if tu and int(tu.group(1)) in obyektlar:
            _, cm = _oqim(obyektlar[int(tu.group(1))])
            cmap = {}
            for blok in re.findall(rb"beginbfchar(.*?)endbfchar", cm, re.S):
                for k, v in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blok):
                    cmap[int(k, 16)] = bytes.fromhex(v.decode()).decode("utf-16-be")
        shriftlar[nom.group(1).decode()] = cmap
    satrlar = []
    for tana in obyektlar.values():
        if b"stream" not in tana or b"/Type /Font" in tana:
            continue
        try:
            _, data = _oqim(tana)
        except Exception:                          # noqa: BLE001
            continue
        if b" Tf" not in data:
            continue
        for blok in _bt_bloklar(data):
            cmap, qism = None, []
            for j, tok in enumerate(blok):
                if tok == b"Tf" and j >= 2 and blok[j - 2].startswith(b"/"):
                    cmap = shriftlar.get(blok[j - 2][1:].decode())
                elif tok == b"Tj" and j >= 1 and blok[j - 1].startswith(b"("):
                    kodlar = _satr(blok[j - 1][1:-1])
                    qism.append("".join(cmap.get(k, "■") for k in kodlar) if cmap is not None else kodlar.decode("cp1252", "replace"))
            if qism:
                satrlar.append("".join(qism).strip())
    return satrlar


def ixcham(s):
    return re.sub(r"\s+", "", str(s)).replace(" ", "")


# ── S. Statik ────────────────────────────────────────────────────────────────────────────────────────────────────
section("S. Statik — loyiha hisoblagichi, loyiha qulfi va uning tartibi, marshrutlar, sahifa bo'limi, migratsiya")
_col = Project.__table__.columns.get("oxirgi_yuk_seq") if "oxirgi_yuk_seq" in Project.__table__.columns else None
check("S1 `projects.oxirgi_yuk_seq` — loyihada berilgan eng katta Y-raqam (Integer, NULL bo'la oladi, standart qiymatsiz — "
      "`sync_missing_columns` eski qatorlarga 0 yozmasin)", _col is not None and _col.nullable and _col.default is None,
      [c.name for c in Project.__table__.columns])
_src_q = manba(getattr(crud, "_loyiha_yuk_eng_katta", None))
check("S2 `crud._loyiha_yuk_eng_katta` — loyiha qatori QULF bilan o'qiladi (`FOR NO KEY UPDATE` — buyurtma qo'shishdagi tashqi kalit "
      "tekshiruvi bilan to'qnashmaydi), korxona bilan; hamma buyurtmalar yuklari va hisoblagichlari",
      "with_for_update(key_share=True)" in _src_q and "Project.company_id == _cid" in _src_q and "Order.project_id ==" in _src_q
      and "oxirgi_yuk_seq" in _src_q and "istisno_delivery_id" in _src_q, _src_q[:200])
_src_cd = manba(crud.create_delivery)
check("S3 `create_delivery` da loyiha qulfi TARTIBI: buyurtma qulfi (101) → tayyor mahsulot chiqimi → LOYIHA qatori → yakuniy raqam → "
      "to'lov → loyiha «To'langan» → hisoblagichlar → commit (`create_order` / `_loyiha_tolangan_yangila` bilan bir tartib — teskarisi "
      "deadlock)",
      tartibda(_src_cd, "_pul_qulfi(db, 101, order.id)", "_mrp_deliver_stock(", "_loyiha_yuk_eng_katta(db, order, istisno_delivery_id=db_delivery.id)",
               "delivery_number = f\"{order.order_number}/Y-{seq}\"", "db_delivery.delivery_number = delivery_number",
               "db.add(Payment(", "_loyiha_tolangan_yangila(db, order.project)", "order.oxirgi_yuk_seq = seq",
               "_prj144.oxirgi_yuk_seq = seq", "db.commit()\n    db.refresh(db_delivery)"), "")
_marsh = {}
for _r in main.app.routes:
    for _m in (getattr(_r, "methods", None) or []):
        _marsh[f"{_m} {getattr(_r, 'path', '')}"] = getattr(_r, "endpoint", None)
_e1 = _marsh.get("GET /api/projects/{project_id}/yuk-xatlari")
_e2 = _marsh.get("GET /api/projects/{project_id}/yuk-xatlari/jamlama-pdf")
check("S4 marshrutlar: «Yuk xatlari» ro'yxati va «Jamlab olish» PDF — ruxsat yuk xati PDF i bilan BIR XIL («Yetkazib berish va transport: "
      "Ko'rish»), loyiha korxonadan tekshiriladi",
      bool(_e1 and _e2) and all('auth.ruxsat("yetkazish", "korish")' in manba(e) and "auth.project_of_company(" in manba(e) for e in (_e1, _e2))
      and 'auth.ruxsat("yetkazish", "korish")' in manba(_marsh.get("GET /api/deliveries/{delivery_id}/pdf")), [bool(_e1), bool(_e2)])
_tpl = fayl("templates/projects.html")
check("S5 loyiha sahifasi: «Yuk xatlari» bo'limi faqat shu ruxsat bilan (`ruxsat('yetkazish', 'korish')`), bo'lim chizuvchisi, «Jamlab "
      "olish» havolasi",
      tartibda(_tpl, "{% if current_user.ruxsat('yetkazish', 'korish') %}", 'data-tab="yuklar"', "Yuk xatlari", "{% endif %}")
      and "if (tab === 'yuklar') return renderYukXatlari(d);" in _tpl and "/yuk-xatlari/jamlama-pdf?ids=" in _tpl
      and "/api/deliveries/${Number(dl.id)}/pdf" in _tpl, "")
_src_main = fayl("main.py")
check("S6 yangilanish migratsiyasi `main._migrate_loyiha_yuk_seq` — ishga tushishda chaqiriladi",
      callable(getattr(main, "_migrate_loyiha_yuk_seq", None)) and "\n_migrate_loyiha_yuk_seq()\n" in _src_main, "")
import delivery_pdf                                # noqa: E402
check("S7 «Jamlab olish» varag'i — `delivery_pdf.generate_yuk_jamlanma_pdf`, jamlash — `crud.yuk_xatlari_jamlanmasi`",
      callable(getattr(delivery_pdf, "generate_yuk_jamlanma_pdf", None)) and callable(getattr(crud, "yuk_xatlari_jamlanmasi", None)), "")

# ── Tayyorgarlik ─────────────────────────────────────────────────────────────────────────────────────────────────
db = SessionLocal()
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="YXL Begona <MChJ> & Co"))
    db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "yxl_admin", "Parol123!", UserRole.ADMIN, "YXL Admin", company_id=1)
    auth.create_user(db, "yxl_begona", "Parol123!", UserRole.ADMIN, "YXL Begona", company_id=2)
    auth.create_user(db, "yxl_moliya", "Parol123!", UserRole.ACCOUNTANT, "YXL Moliyachi", company_id=1)
    auth.create_user(db, "yxl_menejer", "Parol123!", UserRole.MANAGER, "YXL Menejer", company_id=1)
for _cid in (1, 2):
    db.add(Inventory(company_id=_cid, item_name=f"YXL Penoplast {_cid}", category="Penoplast", unit="blok", stock_quantity=100000.0,
                     min_stock=0, price_per_unit=600000, volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True))
    db.add(Inventory(company_id=_cid, item_name=f"YXL Kley {_cid}", category="Kimyoviy qo'shimchalar", unit="kg",
                     stock_quantity=1000000.0, min_stock=0, price_per_unit=3000, volume_per_unit=1.0))
    db.add(Inventory(company_id=_cid, item_name=f"YXL Qum {_cid}", category="Qattiq qotishmalar", unit="kg",
                     stock_quantity=1000000.0, min_stock=0, price_per_unit=800, volume_per_unit=1.0))
db.commit()
PENO = {c: db.query(Inventory).filter(Inventory.company_id == c, Inventory.is_penoplast.is_(True)).first().id for c in (1, 2)}
KLEY = {c: db.query(Inventory).filter(Inventory.company_id == c, Inventory.item_name.like("YXL Kley%")).first().id for c in (1, 2)}
QUM = {c: db.query(Inventory).filter(Inventory.company_id == c, Inventory.item_name.like("YXL Qum%")).first().id for c in (1, 2)}
db.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c


C1, C2, CMOL, CMEN = mijoz("yxl_admin"), mijoz("yxl_begona"), mijoz("yxl_moliya"), mijoz("yxl_menejer")
RETSEPT = {}
for _cid, _c in ((1, C1), (2, C2)):
    _r = req(_c, "post", "/api/recipes", json={"name": f"YXL Qoplama {_cid}", "batch_size_kg": 100, "notes": "",
                                               "ingredients": [{"inventory_id": KLEY[_cid], "quantity_kg": 30},
                                                               {"inventory_id": QUM[_cid], "quantity_kg": 70}]})
    RETSEPT[_cid] = (js(_r) or {}).get("id")


def loyiha(nom, cid=1, mijoz_nomi=None):
    c = C1 if cid == 1 else C2
    r = req(c, "post", "/api/projects", json={"project_name": nom, "client_name": mijoz_nomi or f"{nom} mijoz",
                                              "client_phone": "+998901112233", "client_address": "Andijon", "description": "", "notes": ""})
    j = js(r) or {}
    return j.get("id"), j.get("project_number")


def detal(nom, kat="profil", *, w=20, t=15, l=0, q=1, narx=100000, qop=False, cid=1):
    return {"name": nom, "category": kat, "width": w, "thickness": t, "length": l, "quantity": q, "unit_price": narx,
            "is_coated": qop, "penoplast_id": PENO[cid], "price_per_m3": None, "finished_product_id": None, "sub_details": []}


def buyurtma(prj, detallar, cid=1):
    c = C1 if cid == 1 else C2
    _qop = any(d["is_coated"] for d in detallar)
    tana = {"project_id": prj, "order_type": "product", "recipe_id": RETSEPT.get(cid) if _qop else None, "master_id": None,
            "deadline": None, "is_draft": False, "base_price": 600000, "loy_kg": 10 if _qop else 0, "items": detallar}
    r = req(c, "post", "/api/orders", json=tana)
    if r.status_code == 409:
        r = req(c, "post", "/api/orders?confirm_shortage=true", json=tana)
    j = js(r) or {}
    items = sorted((j.get("items") or []), key=lambda x: x["id"])
    return j.get("id"), [x["id"] for x in items], j.get("order_number")


_yn = [0]


def yuk(oid, qatorlar, cid=1, tolov=None, izoh=None):
    c = C1 if cid == 1 else C2
    _yn[0] += 1
    tana = {"order_id": oid, "items": [{"order_item_id": i, "quantity": q} for i, q in qatorlar],
            "received_by": "YXL Qabul", "notes": izoh or f"YXL yuk {_yn[0]}"}
    if tolov:
        tana["payment_amount"] = tolov
    r = req(c, "post", "/api/deliveries", json=tana)
    j = js(r) or {}
    return j.get("delivery_id"), j.get("delivery_number"), r.status_code


def yuk_ochir(did, cid=1):
    return req(C1 if cid == 1 else C2, "delete", f"/api/deliveries/{did}").status_code


def raqamlar(oid):
    s = SessionLocal()
    try:
        return [x for (x,) in s.query(Delivery.delivery_number).filter(Delivery.order_id == oid).order_by(Delivery.id)]
    finally:
        s.close()


def loyiha_raqamlari(pid):
    s = SessionLocal()
    try:
        return [x for (x,) in s.query(Delivery.delivery_number).join(Order, Order.id == Delivery.order_id)
                .filter(Order.project_id == pid).order_by(Delivery.id)]
    finally:
        s.close()


def ynum(raqam):
    m = re.search(r"/Y-(\d+)$", raqam or "")
    return int(m.group(1)) if m else None


def hisoblagich(jadval, i):
    try:
        with engine.connect() as cn:
            return cn.execute(T(f"SELECT oxirgi_yuk_seq FROM {jadval} WHERE id = :i"), {"i": i}).scalar()
    except Exception as e:                         # noqa: BLE001
        return f"YO'Q ({type(e).__name__})"


# ── R. Raqam ─────────────────────────────────────────────────────────────────────────────────────────────────────
section("R. Yuk xati raqami — LOYIHA bo'yicha davom etadi («ORD-001-2/Y-6»), qayta berilmaydi")
P1, P1N = loyiha("YXL R loyiha")
oA, iA, nA = buyurtma(P1, [detal("YXL Karniz R", l=50, narx=500000)])
oB, iB, nB = buyurtma(P1, [detal("YXL Panel R", "panel", w=60, t=5, q=40, narx=20000)])
check("R0 tayyorgarlik: loyiha, ikki buyurtma (API)", P1 and oA and oB and nA and nB, (P1, oA, oB, nA, nB))
YA = [yuk(oA, [(iA[0], 1)]) for _ in range(5)] if oA else []
check("R1 egasining misoli: 5 ga bo'lib berilsa — 5 ta yuk xati, Y-1 … Y-5 (buyurtma raqami bilan)",
      [y[1] for y in YA] == [f"{nA}/Y-{i}" for i in range(1, 6)], YA)
YB = [yuk(oB, [(iB[0], 2)]) for _ in range(2)] if oB else []
check("R2 shu loyihadagi KEYINGI buyurtmaning yuk xati 6 dan davom etadi: ORD-…-2/Y-6, Y-7 (buyurtma raqami qoladi, «PRJ-…» emas)",
      [y[1] for y in YB] == [f"{nB}/Y-6", f"{nB}/Y-7"], YB)
check("R3 eski raqamlar O'ZGARMADI (birinchi buyurtma: Y-1 … Y-5)", raqamlar(oA) == [f"{nA}/Y-{i}" for i in range(1, 6)], raqamlar(oA))
_s1 = yuk_ochir(YA[2][0]) if len(YA) > 2 else 0
YA8 = yuk(oA, [(iA[0], 1)]) if oA else (None, None, 0)
check("R4 o'rtadagi yuk (Y-3) o'chirilgach birinchi buyurtmaga yangi yuk — Y-8 (Y-3 qayta berilmadi, loyihada keyingisi)",
      _s1 == 200 and YA8[1] == f"{nA}/Y-8", (_s1, YA8))
_s2 = yuk_ochir(YA8[0]) if YA8[0] else 0
YB9 = yuk(oB, [(iB[0], 2)]) if oB else (None, None, 0)
check("R5 loyihadagi OXIRGI yuk (Y-8) o'chirilgach boshqa buyurtmaga — Y-9 (Y-8 qayta berilmadi)",
      _s2 == 200 and YB9[1] == f"{nB}/Y-9", (_s2, YB9))
_lr = loyiha_raqamlari(P1)
check("R6 loyiha hisoblagichi = 9; buyurtmalarniki: birinchisi 8, ikkinchisi 9; loyihada hamma Y-raqam YAGONA",
      hisoblagich("projects", P1) == 9 and hisoblagich("orders", oA) == 8 and hisoblagich("orders", oB) == 9
      and len({ynum(x) for x in _lr}) == len(_lr), (hisoblagich("projects", P1), hisoblagich("orders", oA), hisoblagich("orders", oB), _lr))
P2, _ = loyiha("YXL R ikkinchi loyiha")
o2, i2, n2 = buyurtma(P2, [detal("YXL Karniz R2", l=10, narx=100000)])
Y2 = yuk(o2, [(i2[0], 1)]) if o2 else (None, None, 0)
PB, _ = loyiha("YXL R begona", cid=2)
oX, iX, nX = buyurtma(PB, [detal("YXL Begona karniz", l=10, narx=100000, cid=2)], cid=2)
YX = yuk(oX, [(iX[0], 1)], cid=2) if oX else (None, None, 0)
check("R7 boshqa loyiha (shu korxona) va begona korxona loyihasi — o'z raqamidan (Y-1), birinchi loyihaga ta'sir yo'q",
      Y2[1] == f"{n2}/Y-1" and YX[1] == f"{nX}/Y-1" and hisoblagich("projects", P1) == 9, (Y2, YX, hisoblagich("projects", P1)))
oC, iC, nC = buyurtma(P1, [detal("YXL Karniz C", l=4, narx=40000)])
YC = yuk(oC, [(iC[0], 4)]) if oC else (None, None, 0)
_sd = req(C1, "delete", f"/api/orders/{oC}").status_code if oC else 0
_sp = req(C1, "delete", f"/api/orders/{oC}/permanent").status_code if oC else 0
_s = SessionLocal()
_bor = _s.query(Order.id).filter(Order.id == oC).first() is not None if oC else True
_s.close()
YB11 = yuk(oB, [(iB[0], 2)]) if oB else (None, None, 0)
check("R8 BUTUNLAY o'chirilgan buyurtmaning yuk xati raqami ham qayta berilmaydi: ORD-…/Y-10 → o'chirish → savatdan butunlay → keyingisi "
      "Y-11", YC[1] == f"{nC}/Y-10" and _sd == 200 and _sp == 200 and not _bor and YB11[1] == f"{nB}/Y-11",
      (YC, _sd, _sp, _bor, YB11))
_tana = {"order_id": oB, "items": [{"order_item_id": iB[0], "quantity": 1.5}], "received_by": "YXL Qabul", "notes": "YXL takror"}
_t1, _t2 = req(C1, "post", "/api/deliveries", json=_tana), req(C1, "post", "/api/deliveries", json=_tana)
check("R9 takroriy yuborish (bir xil so'rov 8 s ichida) — ikkinchisi o'sha yuk xatini qaytaradi (Y-12), yangi raqam olinmaydi",
      _t1.status_code == 200 and _t2.status_code == 200 and (js(_t2) or {}).get("duplicate") is True
      and (js(_t1) or {}).get("delivery_number") == (js(_t2) or {}).get("delivery_number") == f"{nB}/Y-12"
      and hisoblagich("projects", P1) == 12, (js(_t1), js(_t2), hisoblagich("projects", P1)))
oD, iD, nD = buyurtma(P1, [detal("YXL Karniz D", l=3, narx=30000)])
_rd = req(C1, "post", f"/api/orders/{oD}/ready") if oD else _Xato(Exception("buyurtma yo'q"))
check("R10 «Tayyor» dagi AVTOMATIK yuk xati ham loyiha bo'yicha: ORD-…/Y-13",
      _rd.status_code == 200 and raqamlar(oD) == [f"{nD}/Y-13"] and hisoblagich("projects", P1) == 13, (_rd.status_code, raqamlar(oD)))

# Eski (zip 144 dan oldingi) ma'lumot: har buyurtma o'z raqamidan boshlagan, hisoblagichlar bo'sh
P3, _ = loyiha("YXL R eski loyiha")
oE, iE, nE = buyurtma(P3, [detal("YXL Karniz E", l=20, narx=200000)])
oF, iF, nF = buyurtma(P3, [detal("YXL Karniz F", l=20, narx=200000)])


def eski_yuklar(oid, iid, n):
    """zip 144 dan oldingi yuk xatlari — bazaga to'g'ridan (buyurtma bo'yicha raqam: /Y-1 … /Y-n), hisoblagichlar NULL."""
    s = SessionLocal()
    o = s.query(Order).filter(Order.id == oid).first()
    for k in range(1, n + 1):
        d = Delivery(order_id=oid, delivery_number=f"{o.order_number}/Y-{k}", delivered_by="eski", received_by="eski",
                     delivered_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30 - k))
        s.add(d)
        s.flush()
        s.add(DeliveryItem(delivery_id=d.id, order_item_id=iid, quantity=1.0, unit="metr"))
    s.commit()
    s.close()
    with engine.connect() as cn:
        cn.execute(T("UPDATE orders SET oxirgi_yuk_seq = NULL WHERE id = :i"), {"i": oid})
        cn.commit()


if oE and oF:
    eski_yuklar(oE, iE[0], 3)
    eski_yuklar(oF, iF[0], 2)
    with engine.connect() as _cn:                  # kech86 davri: E ning Y-4, Y-5 yuklari yozilib o'chirilgan — hisoblagich 5 da
        _cn.execute(T("UPDATE orders SET oxirgi_yuk_seq = 5 WHERE id = :i"), {"i": oE})
        _cn.commit()
YF = yuk(oF, [(iF[0], 1)]) if oF else (None, None, 0)
check("R11 eski ma'lumot (ORD-…-1/Y-1…Y-3 — buyurtma hisoblagichi 5: Y-4, Y-5 o'chirilgan; ORD-…-2/Y-1…Y-2; loyiha hisoblagichi bo'sh): "
      "keyingi yuk — loyihadagi eng kattasidan (buyurtma hisoblagichi ham) keyin, Y-6; eski raqamlar o'zgarmadi",
      YF[1] == f"{nF}/Y-6" and raqamlar(oE) == [f"{nE}/Y-{k}" for k in (1, 2, 3)]
      and raqamlar(oF)[:2] == [f"{nF}/Y-1", f"{nF}/Y-2"], (YF, raqamlar(oE), raqamlar(oF)))

# ── M. Yangilanish ───────────────────────────────────────────────────────────────────────────────────────────────
section("M. Yangilanish — `projects.oxirgi_yuk_seq` siz baza → ustun qo'shiladi, mavjud yuk xatlaridan to'ldiriladi (IDEMPOTENT)")
P4, _ = loyiha("YXL M eski loyiha")
oG4, iG4, nG4 = buyurtma(P4, [detal("YXL Karniz M", l=20, narx=200000)])
if oG4:
    eski_yuklar(oG4, iG4[0], 3)
P5, _ = loyiha("YXL M yuksiz loyiha")
P6, _ = loyiha("YXL M hisoblagichli loyiha")
oH6, iH6, nH6 = buyurtma(P6, [detal("YXL Karniz M6", l=20, narx=200000)])
if oH6:
    eski_yuklar(oH6, iH6[0], 2)
    with engine.connect() as _cn:                  # kech86 davri: Y-3, Y-4 yozilib o'chirilgan — buyurtma hisoblagichi 4 da
        _cn.execute(T("UPDATE orders SET oxirgi_yuk_seq = 4 WHERE id = :i"), {"i": oH6})
        _cn.commit()
_mx, _yoq, _bor, _n1, _n2 = "", False, False, None, None
try:
    from sqlalchemy import inspect as _ins144
    import database as _dbm144
    with engine.connect() as _cn:
        _cn.execute(T("ALTER TABLE projects DROP COLUMN oxirgi_yuk_seq"))
        _cn.commit()
    _yoq = "oxirgi_yuk_seq" not in {c["name"] for c in _ins144(engine).get_columns("projects")}
    with contextlib.redirect_stdout(_quiet):
        _dbm144.sync_missing_columns()
        _n1 = main._migrate_loyiha_yuk_seq()
        _n2 = main._migrate_loyiha_yuk_seq()
    _bor = "oxirgi_yuk_seq" in {c["name"] for c in _ins144(engine).get_columns("projects")}
except Exception as _e:                            # noqa: BLE001 — asl kodda migratsiya yo'q
    _mx = f"{type(_e).__name__}: {str(_e)[:300]}"
_h = {p: hisoblagich("projects", p) for p in (P1, P2, P3, P4, P5, P6, PB)}
check("M1 ustun o'chirildi → ishga tushish (`sync_missing_columns` + `_migrate_loyiha_yuk_seq`): ustun qaytdi; yuk xatli loyihalar "
      "to'ldirildi — eng katta Y-raqam yoki buyurtma hisoblagichi (birinchi loyiha 13, ikkinchisi 1, eski loyiha 6, M loyiha 3, "
      "hisoblagichli 4 — yuklari Y-2 gacha, buyurtma hisoblagichi 4; begona 1), yuksiz — NULL",
      _yoq and _bor and _h == {P1: 13, P2: 1, P3: 6, P4: 3, P5: None, P6: 4, PB: 1} and _n1 == 6, (_mx, _yoq, _bor, _n1, _h))
check("M2 migratsiya qayta ishga tushsa — 0 loyiha (IDEMPOTENT)", _n2 == 0, _n2)
_YM = raqamlar(oG4) if oG4 else []
_s = SessionLocal()
_oxirgi = _s.query(Delivery.id).filter(Delivery.order_id == oG4, Delivery.delivery_number == f"{nG4}/Y-3").scalar() if oG4 else None
_s.close()
_sm = yuk_ochir(_oxirgi) if _oxirgi else 0
YM4 = yuk(oG4, [(iG4[0], 1)]) if oG4 else (None, None, 0)
check("M3 eski buyurtmaning (hisoblagichi bo'sh) OXIRGI yuki (Y-3) yangilanishdan keyin o'chirilsa — keyingisi Y-4 (Y-3 qayta "
      "berilmaydi — migratsiya loyiha hisoblagichiga 3 ni yozgan)", _sm == 200 and YM4[1] == f"{nG4}/Y-4", (_YM, _sm, YM4))

# ── P. PostgreSQL parallel ───────────────────────────────────────────────────────────────────────────────────────
if PG_URL:
    section("P. PostgreSQL parallel — bir loyihaning ikki buyurtmasiga bir vaqtda yuk xati; aralash yuklama xatosiz")
    PP, _ = loyiha("YXL P loyiha")
    oPG, iPG, nPG = buyurtma(PP, [detal("YXL Karniz PG", l=500, narx=5000000)])
    oPH, iPH, nPH = buyurtma(PP, [detal("YXL Karniz PH", l=500, narx=5000000)])
    _pn = [0]

    def _dc(oid, iid, q, tolov=None):
        _pn[0] += 1
        k = {"order_id": oid, "items": [{"order_item_id": iid, "quantity": q}], "notes": f"YXL P {_pn[0]}", "received_by": "YXL P"}
        if tolov:
            k["payment_amount"] = tolov
        return schemas.DeliveryCreate(**k)

    def sekin(s, kut=0.5):
        asl = s.commit

        def f():
            time.sleep(kut)
            asl()
        s.commit = f

    def poyga(ishlar, sekinlar=()):
        nat = [None] * len(ishlar)
        bar = threading.Barrier(len(ishlar))

        def t(k, fn):
            s = SessionLocal()
            if k in sekinlar:
                sekin(s)
            try:
                try:
                    bar.wait(timeout=60)
                except Exception:                  # noqa: BLE001
                    pass
                if k not in sekinlar and sekinlar:
                    time.sleep(0.15)
                try:
                    x = fn(s)
                    # ORM obyekti (buyurtma, to'lov) — sessiya ochiq paytida soddalashtiriladi (keyin «detached» bo'ladi)
                    nat[k] = {"obj": type(x).__name__, "id": getattr(x, "id", None)} if hasattr(x, "__table__") else x
                except Exception as e:             # noqa: BLE001
                    try:
                        s.rollback()
                    except Exception:              # noqa: BLE001
                        pass
                    nat[k] = f"ISTISNO {type(e).__name__}: {str(e)[:300]}"
            finally:
                s.close()
        ts = [threading.Thread(target=t, args=(k, fn)) for k, fn in enumerate(ishlar)]
        for x in ts:
            x.start()
        for x in ts:
            x.join(timeout=180)
        return nat

    _p1 = []
    for _k in range(3):
        _r = poyga([lambda s: crud.create_delivery(s, _dc(oPG, iPG[0], 1.0), delivered_by="P1", company_id=1),
                    lambda s: crud.create_delivery(s, _dc(oPH, iPH[0], 1.0), delivered_by="P1", company_id=1)], sekinlar=(0,))
        _p1.append([(x or {}).get("delivery_number") if isinstance(x, dict) else x for x in _r])
    _lr = loyiha_raqamlari(PP)
    _ys = sorted(ynum(x) for x in _lr)
    check("P1 sekin commit bilan poyga (3 marta): birinchi oqim loyiha qulfini ushlab turadi, ikkinchisi KUTADI — 6 yuk xati, Y-raqamlar "
          "YAGONA va ketma-ket (1…6), har juft ikki buyurtmada", all(isinstance(a, str) and isinstance(b, str) and "/Y-" in a and "/Y-" in b
                                                                   for a, b in _p1) and _ys == list(range(1, 7)),
          (_p1, _lr))
    _r8 = poyga([(lambda s, k=k: crud.create_delivery(s, _dc(oPG if k % 2 else oPH, iPG[0] if k % 2 else iPH[0], 1.0 + k / 10),
                                                      delivered_by="P2", company_id=1)) for k in range(8)])
    _lr = loyiha_raqamlari(PP)
    _ys = sorted(ynum(x) for x in _lr)
    check("P2 8 oqim bir vaqtda (Barrier), ikki buyurtma: hammasi saqlandi, Y-raqamlar yagona va ketma-ket (1…14), hisoblagich 14",
          all(isinstance(x, dict) and x.get("success") for x in _r8) and _ys == list(range(1, 15)) and hisoblagich("projects", PP) == 14,
          ([x if not isinstance(x, dict) else x.get("delivery_number") for x in _r8], _lr, hisoblagich("projects", PP)))
    _p3 = []
    for _k in range(3):
        oK, iK, nK = buyurtma(PP, [detal(f"YXL Karniz K{_k}", l=5, narx=50000)])
        _ot = schemas.OrderCreate(**{"project_id": PP, "order_type": "product", "items": [
            {"name": f"YXL Yangi {_k}", "category": "profil", "width": 20, "thickness": 15, "length": 6, "quantity": 1,
             "unit_price": 60000, "is_coated": False, "penoplast_id": PENO[1]}]})
        _r = poyga([lambda s: crud.create_delivery(s, _dc(oPG, iPG[0], 2.0, tolov=float(10000 + _k)), delivered_by="P3", company_id=1),
                    lambda s, oK=oK: services.complete_order(s, oK),
                    lambda s, _ot=_ot: crud.create_order(s, _ot, performed_by="P3", company_id=1),
                    lambda s: crud.create_payment(s, schemas.PaymentCreate(order_id=oPH, amount=float(5000 + _k)), company_id=1)],
                   sekinlar=(1,))
        _p3.append((_r, raqamlar(oK)))
    _lr = loyiha_raqamlari(PP)
    check("P3 aralash yuklama bir loyihada (3 marta): to'lovli yuk xati ∥ «Tayyor» (avtomatik yuk xati, ombor) ∥ yangi buyurtma (ombor, "
          "loyiha hisoblagichi) ∥ to'lov — HAMMASI xatosiz (deadlock / istisno yo'q), avtomatik yuk xatlari raqamli, loyihada Y-raqamlar "
          "yagona",
          all(isinstance(r[0], dict) and r[0].get("success") and isinstance(r[1], dict) and r[1].get("success")
              and isinstance(r[2], dict) and r[2].get("id") and isinstance(r[3], dict) and r[3].get("id") and len(rq) == 1 for r, rq in _p3)
          and len({ynum(x) for x in _lr}) == len(_lr) == 20,
          ([([str(x)[:120] for x in r], rq) for r, rq in _p3], len(_lr)))

# ── L. «Yuk xatlari» ro'yxati ────────────────────────────────────────────────────────────────────────────────────
section("L. «Yuk xatlari» ro'yxati — loyihaning hamma buyurtmalari, summalar, ruxsat, begona korxona, so'rovlar soni")
_rl = req(C1, "get", f"/api/projects/{P1}/yuk-xatlari")
_jl = js(_rl) or {}
_dl = _jl.get("deliveries") or []
_s = SessionLocal()
_db_yuk = (_s.query(Delivery).join(Order, Order.id == Delivery.order_id).filter(Order.project_id == P1)
           .order_by(Delivery.delivered_at.desc(), Delivery.id.desc()).all())
_kut = [d.delivery_number for d in _db_yuk]
_kut_t = {}
for _d in _db_yuk:
    _t = 0
    for _di in _d.items:
        _oi = _di.order_item
        _n = float(_oi.order_qty_normalized or 0)
        _t += tiyin((float(_oi.total_price or 0) / _n if _n > 0 else 0) * float(_di.quantity))
    _kut_t[_d.delivery_number] = _t
_s.close()
check("L1 ro'yxat (200): loyihaning HAMMA buyurtmalari yuk xatlari (ikkinchi buyurtma, «Tayyor» avtomatigi ham), yangidan eskiga — "
      "bazadagi tartib bilan AYNAN; boshqa loyiha yuki yo'q",
      _rl.status_code == 200 and [d.get("delivery_number") for d in _dl] == _kut and len(_kut) == 10
      and not any(str(d.get("delivery_number") or "").startswith(str(n2)) for d in _dl), (_rl.status_code, [d.get("delivery_number") for d in _dl], _kut))
_q0 = _dl[0] if _dl else {}
check("L2 har qator: raqam, buyurtma raqami, sana, berilgan detallar (nomi, miqdori, birligi), summa; `jami_tiyin` — qo'lda hisob "
      "(narx = detal jami ÷ miqdori, × berilgan, tiyinga) bilan AYNAN, ro'yxat jami — yig'indisi",
      all(d.get("order_number") and d.get("delivered_at") and d.get("items") and d.get("jami_tiyin") == _kut_t.get(d.get("delivery_number"))
          and all("item_name" in i and "quantity" in i and "unit" in i for i in d.get("items") or []) for d in _dl)
      and _jl.get("jami_tiyin") == sum(_kut_t.values()) and _jl.get("soni") == len(_dl),
      (_q0, _kut_t, _jl.get("jami_tiyin")))
_r2 = req(C2, "get", f"/api/projects/{P1}/yuk-xatlari")
_r2p = req(C2, "get", f"/api/projects/{P1}/yuk-xatlari/jamlama-pdf")
_r2o = req(C2, "get", f"/api/projects/{PB}/yuk-xatlari")
check("L3 begona korxona: boshqa korxona loyihasi — 404 (ro'yxat ham, PDF ham; mavjudligi bildirilmaydi), o'z loyihasi — faqat o'ziniki",
      _r2.status_code == 404 and _r2p.status_code == 404 and b"%PDF" not in (_r2p.content or b"")[:8]
      and _r2o.status_code == 200 and [d.get("delivery_number") for d in (js(_r2o) or {}).get("deliveries") or []] == [f"{nX}/Y-1"],
      (_r2.status_code, _r2p.status_code, _r2o.status_code, (js(_r2o) or {}).get("deliveries")))
_rm1, _rm2 = req(CMOL, "get", f"/api/projects/{P1}/yuk-xatlari"), req(CMOL, "get", f"/api/projects/{P1}/yuk-xatlari/jamlama-pdf")
_rn1, _rn2 = req(CMEN, "get", f"/api/projects/{P1}/yuk-xatlari"), req(CMEN, "get", f"/api/projects/{P1}/yuk-xatlari/jamlama-pdf")
check("L4 ruxsat: Moliyachi («Yetkazib berish: Ko'rish» yo'q) — 403 ikkalasida; Menejer — 200 (yuk xati PDF i bilan bir qoida)",
      _rm1.status_code == 403 and _rm2.status_code == 403 and _rn1.status_code == 200 and _rn2.status_code == 200,
      (_rm1.status_code, _rm2.status_code, _rn1.status_code, _rn2.status_code))
# qaysi buyurtmalar — loyiha pul hisobi qoidasi
PL, _ = loyiha("YXL L qoida loyiha")
oLx, iLx, nLx = buyurtma(PL, [detal("YXL Karniz Lx", l=10, narx=100000)])
oLy, iLy, nLy = buyurtma(PL, [detal("YXL Karniz Ly", l=10, narx=100000)])
YLx = yuk(oLx, [(iLx[0], 4)]) if oLx else (None, None, 0)
YLy = yuk(oLy, [(iLy[0], 3)]) if oLy else (None, None, 0)
_slx = req(C1, "delete", f"/api/orders/{oLx}").status_code if oLx else 0
with engine.connect() as _cn:                      # kech100 dan oldin o'chirilgan qisman topshirilgan (IN_PROGRESS) buyurtma
    _cn.execute(T("UPDATE orders SET is_deleted = :t, status = 'IN_PROGRESS' WHERE id = :i"), {"t": True, "i": oLy})
    _cn.commit()
_s = SessionLocal()
_stx = _s.query(Order.status, Order.is_deleted).filter(Order.id == oLx).first()
_s.close()
_jq = js(req(C1, "get", f"/api/projects/{PL}/yuk-xatlari")) or {}
_pq = req(C1, "get", f"/api/projects/{PL}/yuk-xatlari/jamlama-pdf?ids={YLy[0]}")
check("L5 qaysi buyurtmalar — «Loyiha qiymati» qoidasi: o'chirilgan, topshirilgani bilan yakunlangan («Tayyor») buyurtma yuki — BOR; "
      "eski o'chirilgan yakunlanmagan (IN_PROGRESS) buyurtma yuki — YO'Q (ro'yxatda ham, varaqda ham — 404)",
      _slx == 200 and _stx is not None and _stx[1] and _stx[0] in (OrderStatus.READY, OrderStatus.DELIVERED)
      and [d.get("delivery_number") for d in _jq.get("deliveries") or []] == [YLx[1]] and _pq.status_code == 404,
      (_slx, _stx, _jq.get("deliveries"), _pq.status_code))

_SANOQ = [0]


@event.listens_for(engine, "before_cursor_execute")
def _sanoq(conn, cursor, statement, parameters, context, executemany):   # noqa: ARG001
    _SANOQ[0] += 1


def sorovlar(url):
    req(C1, "get", url)                            # isinish (sessiya, ruxsatlar keshi)
    _SANOQ[0] = 0
    r = req(C1, "get", url)
    return _SANOQ[0], r.status_code


PN1, _ = loyiha("YXL N bitta")
_o, _i, _ = buyurtma(PN1, [detal("YXL N1 karniz", l=10, narx=100000), detal("YXL N1 panel", "panel", w=60, t=5, q=10, narx=20000)])
if _o:
    yuk(_o, [(_i[0], 1), (_i[1], 1)])
PN5, _ = loyiha("YXL N ko'p")
for _k in range(4):
    _o, _i, _ = buyurtma(PN5, [detal(f"YXL N5 karniz {_k}", l=10, narx=100000), detal(f"YXL N5 panel {_k}", "panel", w=60, t=5, q=10, narx=20000)])
    for _j in range(2):
        if _o:
            yuk(_o, [(_i[0], 1), (_i[1], 1)])
_n_1, _st1 = sorovlar(f"/api/projects/{PN1}/yuk-xatlari")
_n_5, _st5 = sorovlar(f"/api/projects/{PN5}/yuk-xatlari")
_p_1, _pt1 = sorovlar(f"/api/projects/{PN1}/yuk-xatlari/jamlama-pdf")
_p_5, _pt5 = sorovlar(f"/api/projects/{PN5}/yuk-xatlari/jamlama-pdf")
check("L6 so'rovlar soni buyurtma / yuk xati soniga bog'liq EMAS: 1 buyurtma × 1 yuk ↔ 4 buyurtma × 2 yuk (har yuk 2 qator) — ro'yxat "
      "va «Jamlab olish» varag'i", _st1 == _st5 == _pt1 == _pt5 == 200 and _n_1 == _n_5 and _p_1 == _p_5,
      (_n_1, _n_5, _p_1, _p_5, _st1, _st5, _pt1, _pt5))

# ── J. «Jamlab olish» ────────────────────────────────────────────────────────────────────────────────────────────
section("J. «Jamlab olish» — bir xil detal bitta qatorda: miqdor, birlik narxi, summa, JAMI; kirgan yuk xatlari; PDF")
PJ, PJN = loyiha("YXL Jamlama <uy> & hovli", mijoz_nomi="Ali <Vali> & Co")
oJ1, iJ1, nJ1 = buyurtma(PJ, [detal("YXL Karniz <A> & B", l=150, narx=300000), detal("YXL Panel J", "panel", w=60, t=5, q=40, narx=20000)])
oJ2, iJ2, nJ2 = buyurtma(PJ, [detal("yxl  karniz <a> & b ", l=100, narx=200000), detal("YXL Karniz <A> & B", l=50, narx=150000),
                              detal("YXL Karniz <A> & B", w=25, t=15, l=20, narx=40000)])
# qoplamali karniz — birlik narxi qoplamasiz karniz bilan BIR XIL (2 000 so'm / m: 20 000 ÷ 10 m; O'LCHANGAN — server narxni
# qoplama uchun o'zgartirmaydi, «×2» brauzerda) — faqat qoplama farq qiladi
oJ3, iJ3, nJ3 = buyurtma(PJ, [detal("YXL Karniz <A> & B", l=10, narx=20000, qop=True)])
JY = []
if oJ1 and oJ2 and oJ3:
    JY.append(yuk(oJ1, [(iJ1[0], 100), (iJ1[1], 10)]))
    JY.append(yuk(oJ1, [(iJ1[0], 50)]))
    JY.append(yuk(oJ2, [(iJ2[0], 30), (iJ2[1], 50)]))
    JY.append(yuk(oJ2, [(iJ2[2], 20)]))
    JY.append(yuk(oJ3, [(iJ3[0], 10)]))
    JY.append(yuk(oJ1, [(iJ1[1], 12.5)]))
check("J0 tayyorgarlik: uch buyurtma, 6 yuk xati (Y-1 … Y-6 — loyiha bo'yicha)",
      [y[2] for y in JY] == [200] * 6 and [ynum(y[1]) for y in JY] == [1, 2, 3, 4, 5, 6], JY)
_s = SessionLocal()
_tp = {oi_id: float(tp) for oi_id, tp in _s.query(OrderItem.id, OrderItem.total_price)
       .filter(OrderItem.id.in_((iJ1 or []) + (iJ2 or []) + (iJ3 or []))).all()} if JY else {}
_s.close()
_qop_narx = (_tp.get(iJ3[0], 0) / 10) if iJ3 else 0
check("J0b qoplamali karnizning birlik narxi qoplamasiz bilan bir xil (2 000) — jamlashda faqat QOPLAMA ajratadi", _qop_narx == 2000.0,
      _qop_narx)
KUT_Q = [  # (nom boshi, qoplama, eni, miqdor, birlik narxi, summa)
    ("YXL Karniz <A> & B", False, 20.0, 180.0, 2000.0, 360000.0),
    ("YXL Panel J", False, 60.0, 22.5, 20000.0, 450000.0),
    ("YXL Karniz <A> & B", False, 20.0, 50.0, 3000.0, 150000.0),
    ("YXL Karniz <A> & B", False, 25.0, 20.0, 2000.0, 40000.0),
    ("YXL Karniz <A> & B", True, 20.0, 10.0, _qop_narx, _qop_narx * 10),
]
_s = SessionLocal()
_jm, _jx = {}, ""
try:
    _jm = crud.yuk_xatlari_jamlanmasi(crud.loyiha_yuk_xatlari(_s, PJ, company_id=1))
except Exception as _e:                            # noqa: BLE001 — asl kodda yo'q
    _jx = f"{type(_e).__name__}: {_e}"
_s.close()
_jq = [(q.get("nom"), q.get("qoplama"), q.get("eni"), q.get("miqdor"), q.get("birlik_narxi"), q.get("summa")) for q in (_jm.get("qatorlar") or [])]
check("J1 jamlash qoidasi: «Karniz» Y-1 100 m + Y-2 50 m + ikkinchi buyurtmada 30 m (nomi kichik harf / ortiqcha bo'shliq bilan — bir xil, "
      "narx 2 000) = 180 m bitta qatorda; panel 10 + 12,5 = 22,5 m; boshqa NARX (3 000), boshqa O'LCHAM (25×15), QOPLAMALI — alohida "
      "qatorlar; tartib — birinchi uchragan joy", _jq == KUT_Q and _qop_narx > 0, (_jx, _jq, KUT_Q))
_jami_kut = sum(q[5] for q in KUT_Q)
check("J2 JAMI = qatorlar summalari = tanlangan yuk xatlari summalari (tiyin aniqligida); kirgan yuk xatlari — eskidan yangiga, 6 ta, "
      "buyurtmalar ro'yxati", abs(float(_jm.get("jami") or -1) - _jami_kut) < 0.005
      and [y.get("raqam") for y in _jm.get("yuk_xatlari") or []] == [y[1] for y in JY]
      and sum(tiyin(y.get("summa")) for y in _jm.get("yuk_xatlari") or []) == tiyin(_jami_kut)
      and _jm.get("buyurtmalar") == [nJ1, nJ2, nJ3], (_jm.get("jami"), _jami_kut, _jm.get("yuk_xatlari"), _jm.get("buyurtmalar")))
_jl = js(req(C1, "get", f"/api/projects/{PJ}/yuk-xatlari")) or {}
_rp = req(C1, "get", f"/api/projects/{PJ}/yuk-xatlari/jamlama-pdf?ids=" + ",".join(str(d.get("id")) for d in _jl.get("deliveries") or []))
_sat = pdf_satrlar(_rp.content if _rp.status_code == 200 else b"")
_ix = [ixcham(x) for x in _sat]
_pdf_katak = (["Mijoz:", "180m", "2000so'm", "360000", "22.5m", "20000so'm", "450000", "50m", "3000so'm", "150000", "20m", "40000",
               "JAMI:", ixcham(som_hu(tiyin(_jami_kut))), "Kirganyukxatlari"] + [ixcham(y[1]) for y in JY])
_pdf_qism = ["YUKXATLARIJAMLANMASI", ixcham(PJN or "?"), ixcham("Ali <Vali> & Co"), ixcham("YXL Jamlama <uy> & hovli"),
             ixcham(f"{nJ1}, {nJ2}, {nJ3}"), ixcham("YXL Karniz <A> & B (qoplamali) · 20×15 sm"),
             ixcham("YXL Karniz <A> & B · 20×15 sm"), ixcham("YXL Karniz <A> & B · 25×15 sm"), ixcham("YXL Panel J · 60×5 sm")]
_pdf_kut = [k for k in _pdf_katak if k not in _ix] + [k for k in _pdf_qism if not any(k in x for x in _ix)]
check("J3 «Jamlab olish» PDF (200, `application/pdf`, ochiladigan nom): sarlavha, loyiha raqami, mijoz / loyiha («<», «&» — AYNAN), "
      "buyurtmalar; har qatorda miqdor, birlik narxi, summa (qo'lda hisob), o'lcham va qoplama; JAMI; kirgan 6 yuk xati",
      _rp.status_code == 200 and "application/pdf" in str(_rp.headers.get("content-type")) and "inline" in str(_rp.headers.get("content-disposition"))
      and not _pdf_kut and any("Ushbuhujjat6tayukxatibo'yichajamlanma" in x for x in _ix),
      (_rp.status_code, _pdf_kut, _sat[:60]))
check("J4 brauzerdagi «Tanlangan» jami (ro'yxat `jami_tiyin` yig'indisi) = varaqdagi JAMI (bir xil yaxlitlash)",
      _jl.get("jami_tiyin") == tiyin(_jami_kut) and ixcham(som_hu(_jl.get("jami_tiyin") or 0)) in _ix, (_jl.get("jami_tiyin"), tiyin(_jami_kut)))
_id = {ynum(d.get("delivery_number")): d.get("id") for d in _jl.get("deliveries") or []}
_rs = req(C1, "get", f"/api/projects/{PJ}/yuk-xatlari/jamlama-pdf?ids={_id.get(3)},{_id.get(1)}")
_ss = [ixcham(x) for x in pdf_satrlar(_rs.content if _rs.status_code == 200 else b"")]
_sub_jami = 130 * 2000 + 10 * 20000 + 50 * 3000
check("J5 belgilangan qism (Y-1, Y-3): faqat ular — karniz 100 + 30 = 130 m (260 000), panel 10 m, karniz 3 000 lik 50 m; JAMI 610 000; "
      "kirgan yuk xatlari — faqat shu ikkitasi; boshqalari yo'q",
      _rs.status_code == 200 and "130m" in _ss and "260000" in _ss and "10m" in _ss and "50m" in _ss and ixcham(som_hu(_sub_jami * 100)) in _ss
      and ixcham(JY[0][1]) in _ss and ixcham(JY[2][1]) in _ss and all(ixcham(JY[k][1]) not in _ss for k in (1, 3, 4, 5))
      and "Ushbuhujjat2tayukxatibo'yichajamlanma" in "".join(_ss), (_rs.status_code, _ss[:50]))
_rb1 = req(C1, "get", f"/api/projects/{PJ}/yuk-xatlari/jamlama-pdf?ids={_id.get(1)},{Y2[0]}")
_rb2 = req(C1, "get", f"/api/projects/{PJ}/yuk-xatlari/jamlama-pdf?ids={_id.get(1)},{YX[0]}")
_rb3 = req(C1, "get", f"/api/projects/{PJ}/yuk-xatlari/jamlama-pdf?ids={_id.get(1)},99999999")
_dt = [(js(r) or {}).get("detail") for r in (_rb1, _rb2, _rb3)]
check("J6 belgilanganlardan biri shu loyihada YO'Q (boshqa loyiha / begona korxona / mavjud emas) — 404, hujjat CHIQMAYDI; javob uchala "
      "holatda AYNAN bir xil (begona yozuv borligi bildirilmaydi)",
      [r.status_code for r in (_rb1, _rb2, _rb3)] == [404, 404, 404] and _dt[0] and _dt[0] == _dt[1] == _dt[2]
      and not any(b"%PDF" in (r.content or b"")[:8] for r in (_rb1, _rb2, _rb3)), ([r.status_code for r in (_rb1, _rb2, _rb3)], _dt))
_rv = [req(C1, "get", f"/api/projects/{PJ}/yuk-xatlari/jamlama-pdf?ids={x}").status_code
       for x in ("abc", "0", "-5", "1.5", ",".join(str(k) for k in range(1, 1003)))]
_re = req(C1, "get", f"/api/projects/{PJ}/yuk-xatlari/jamlama-pdf?ids=")
_re_s = [ixcham(x) for x in pdf_satrlar(_re.content if _re.status_code == 200 else b"")]
_r0 = req(C1, "get", f"/api/projects/{P5}/yuk-xatlari/jamlama-pdf")
check("J7 noto'g'ri `ids` (matn, 0, manfiy, kasr, 1 000 tadan ko'p) — 400; bo'sh — loyihaning HAMMA yuk xatlari (6); yuk xatisiz loyiha — "
      "404", _rv == [400, 400, 400, 400, 400] and _re.status_code == 200 and "Ushbuhujjat6tayukxatibo'yichajamlanma" in "".join(_re_s)
      and _r0.status_code == 404, (_rv, _re.status_code, _r0.status_code))
_rk1 = req(C1, "get", f"/api/projects/{PJ}/yuk-xatlari/jamlama-pdf")
_rk2 = req(C2, "get", f"/api/projects/{PB}/yuk-xatlari/jamlama-pdf")
_k1 = [ixcham(x) for x in pdf_satrlar(_rk1.content if _rk1.status_code == 200 else b"")]
_k2 = [ixcham(x) for x in pdf_satrlar(_rk2.content if _rk2.status_code == 200 else b"")]
check("J8 sarlavha — korxona nomi: 1-korxona varag'ida o'z nomi, begona korxona varag'ida «YXL BEGONA <MCHJ> & CO» (boshqa korxona nomi YO'Q)",
      _rk2.status_code == 200 and ixcham("YXL BEGONA <MCHJ> & CO") in _k2 and ixcham("YXL BEGONA <MCHJ> & CO") not in _k1
      and _rk1.status_code == 200, (_rk1.status_code, _rk2.status_code, _k2[:4]))
# yarim so'm: brauzer `Math.round` (yarimda yuqoriga) = varaq; Python `round` yarimda juftga — 500,5 → 500 bo'lardi
PY, _ = loyiha("YXL Yarim so'm")
oYa, iYa, _ = buyurtma(PY, [detal("YXL Yarim karniz", l=2, narx=1001)])
YYa = yuk(oYa, [(iYa[0], 1)]) if oYa else (None, None, 0)
_jy = js(req(C1, "get", f"/api/projects/{PY}/yuk-xatlari")) or {}
_ry = req(C1, "get", f"/api/projects/{PY}/yuk-xatlari/jamlama-pdf")
_ys = [ixcham(x) for x in pdf_satrlar(_ry.content if _ry.status_code == 200 else b"")]
check("J9 yarim so'm (narx 500,5, 1 m): ro'yxat `jami_tiyin` = 50 050, varaqdagi summa va JAMI — 501 (brauzer ham 501 ko'rsatadi; "
      "`_fmt` 500 qilardi)", _jy.get("jami_tiyin") == 50050 and _ry.status_code == 200 and _ys.count("501") >= 3, (_jy.get("jami_tiyin"), _ys[-30:]))

# ── U. Sahifa (brauzer) ──────────────────────────────────────────────────────────────────────────────────────────
section("U. Loyiha sahifasi — «Yuk xatlari» bo'limi (Chromium, 1440 / 390 px, yorug' / tungi)")
try:
    from playwright.sync_api import sync_playwright
    _pw_bor, _pw_x = True, ""
except Exception as _e:                            # noqa: BLE001
    _pw_bor, _pw_x = False, f"{type(_e).__name__}: {_e}"
import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


_u13 = fayl("tools/test_u13.py")
_i0 = _u13.find('U13_JS = r"""')
U13_JS = _u13[_i0 + len('U13_JS = r"""'):_u13.find('"""', _i0 + len('U13_JS = r"""'))] if _i0 >= 0 else ""
_m = re.search(r"ISTISNO_SEL = \(([^)]*)\)", _u13)
ISTISNO_SEL = "".join(re.findall(r'"([^"]*)"', _m.group(1))) if _m else ""
SHKALA = {12.0, 13.0, 14.0, 16.0, 18.0, 24.0, 32.0}
TUGMA_H = {1440: {32.0, 36.0, 40.0}, 390: {36.0, 40.0, 44.0}}
TUGMA_FS = {13.0, 14.0, 16.0}


def bormi(qiymat, toplam, tol=0.6):
    return any(abs(qiymat - x) <= tol for x in toplam)


def tugma_yomon(o, w):
    """`tools/test_u13.py` dagi hakam bilan AYNAN: balandlik / burchak / yozuv o'lchami / kvadrat belgi-tugma / yozuv sig'ishi."""
    yomon = []
    for t in (o or {}).get("tugmalar") or []:
        if t["tur"] == "karta":
            continue
        xato = []
        if t["tur"] == "tanlov":
            if t["h"] < max(TUGMA_H[w]) - 0.6:
                xato.append(f"h={t['h']}")
        elif not bormi(t["h"], TUGMA_H[w]):
            xato.append(f"h={t['h']}")
        if t["chip"]:
            if t["rad"] < t["h"] / 2 - 1:
                xato.append(f"rad={t['rad']}")
        elif abs(t["rad"] - 8) > 0.5:
            xato.append(f"rad={t['rad']}")
        belgi = not re.search(r"[A-Za-z0-9Ѐ-ӿ’ʻ]", t.get("yozuv", t["matn"]) or "")
        if t["fs"] not in TUGMA_FS and not (belgi and t["fs"] == 18.0):
            xato.append(f"fs={t['fs']}")
        if t.get("ikon") and abs(t["w"] - t["h"]) > 1:
            xato.append(f"kvadrat emas {t['w']}×{t['h']}")
        if t.get("toshdi"):
            xato.append("yozuv sig'madi")
        if xato:
            yomon.append(f"{t['sel'][:60]} «{t['matn'][:20]}» " + " ".join(xato))
    return yomon


def belgi_yomon(o):
    return [f"{b['sel'][:60]} {b['w']}×{b['h']}" for b in (o or {}).get("belgilar") or [] if b["h"] > 22 or b["w"] > 22]


def shrift_yomon(o):
    return {k: v["misol"][:3] for k, v in ((o or {}).get("shrift") or {}).items() if float(k) not in SHKALA}


_srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=_port(), log_level="critical", lifespan="off"))
threading.Thread(target=_srv.run, daemon=True).start()
for _ in range(150):
    if _srv.started:
        break
    time.sleep(0.1)
_pw = _br = None
if _pw_bor and _srv.started:
    _pw = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                              "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        _br = _pw.chromium.launch(executable_path=_exe) if _exe else _pw.chromium.launch()
    except Exception as _e:                        # noqa: BLE001
        _br, _pw_x = None, f"{type(_e).__name__}: {_e}"
check("U0 lokal server va Chromium; o'lchov JS i `tools/test_u13.py` dan", bool(_srv.started and _br and U13_JS), _pw_x)
_B = f"http://127.0.0.1:{_srv.config.port}"
_JS_XATO = []
_UI = {}
_HOLAT_JS = """() => {
  const a = document.getElementById('yx-jamlab');
  const chk = [...document.querySelectorAll('.yx-chk')];
  return {qator: document.querySelectorAll('.yx-qator').length, belgilangan: chk.filter(c => c.checked).length,
          idlar: chk.map(c => Number(c.value)), tiyin: chk.filter(c => c.checked).map(c => Number(c.dataset.tiyin)),
          soni: (document.getElementById('yx-tanlangan-soni') || {}).textContent || null,
          jami: (document.getElementById('yx-tanlangan-jami') || {}).textContent || null,
          href: a ? a.getAttribute('href') : 'tugma yo\\'q', yozuv: a ? a.textContent.trim() : null,
          ochiq: a ? (a.getAttribute('aria-disabled') !== 'true' && !a.classList.contains('yx-ochiq-emas')) : null,
          yon: document.documentElement.scrollWidth <= innerWidth + 1,
          tab: !!document.querySelector('.tab-btn[data-tab="yuklar"]')};
}"""
_JOY_JS = """() => {
  const q = document.querySelector('.yx-qator'); if (!q) return null;
  const r = e => { const b = q.querySelector(e).getBoundingClientRect(); return {x: Math.round(b.left), y: Math.round(b.top), r: Math.round(b.right), b: Math.round(b.bottom)}; };
  const qr = q.getBoundingClientRect();
  return {raqam: r('.yx-raqam'), summa: r('.yx-summa'), pdf: r('.yx-pdf'), qator: {x: Math.round(qr.left), r: Math.round(qr.right)}};
}"""


def _kirish(ctx, login):
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: _JS_XATO.append((login, str(e)[:200])))
    pg.goto(_B + "/login")
    pg.fill("input[name=username]", login)
    pg.fill("input[name=password]", "Parol123!")
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return pg


def _kontekst(w, h, tel):
    ctx = _br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=tel, has_touch=tel,
                          timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                         r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), lambda route: route.fulfill(status=204, body=""))
    return ctx


def _loyihani_och(pg, pid, tema):
    pg.goto(_B + "/projects", wait_until="networkidle")
    if tema == "dark":
        pg.evaluate("() => document.documentElement.setAttribute('data-theme', 'dark')")
    pg.evaluate(f"() => {{ const c = document.querySelector('.proj-card[data-id=\"{pid}\"]'); c && selectProj(c); }}")
    pg.wait_for_timeout(400)
    pg.evaluate("() => switchTab('yuklar')")
    try:
        pg.wait_for_function("() => document.querySelector('.yx-chk') || /yuk xati yo/i.test((document.getElementById('tabContent') || {}).innerText || '')",
                             timeout=8000)
    except Exception:                              # noqa: BLE001 — shart bajarilmasa jim davom (tekshiruv o'zi yiqiladi)
        pass
    pg.wait_for_timeout(200)


if _br:
    for _w, _h, _tel in ((1440, 900, False), (390, 844, True)):
        for _tema in ("light", "dark"):
            _ctx = _kontekst(_w, _h, _tel)
            try:
                _pg = _kirish(_ctx, "yxl_admin")
                _loyihani_och(_pg, PJ, _tema)
                _r = {"boshi": _pg.evaluate(_HOLAT_JS), "joy": _pg.evaluate(_JOY_JS),
                      "o": _pg.evaluate(U13_JS, {"istisno": ISTISNO_SEL, "root": "#tabContent"}) if U13_JS else {}}
                if _tema == "light":
                    _pg.evaluate("() => { const c = document.querySelector('.yx-chk'); c.click(); }")
                    _r["bittasiz"] = _pg.evaluate(_HOLAT_JS)
                    _pg.evaluate("() => yxBelgila(false)")
                    _r["hech"] = _pg.evaluate(_HOLAT_JS)
                    _pg.evaluate("() => yxBelgila(true)")
                    _r["hammasi"] = _pg.evaluate(_HOLAT_JS)
                    _oldin = _pg.evaluate("() => document.querySelector('.yx-chk').checked")
                    # yangi oynadagi PDF o'rniga oddiy sahifa (brauzer PDF ni yuklab olishga o'tib, manzil «about:blank» qolmasin)
                    _ctx.route(re.compile(r".*/api/deliveries/\d+/pdf$"),
                               lambda route: route.fulfill(status=200, content_type="text/html", body="<html><body>PDF</body></html>"))
                    try:
                        with _ctx.expect_page(timeout=8000) as _yangi:
                            _pg.click(".yx-qator .yx-pdf")
                        _np = _yangi.value
                        _np.wait_for_load_state("domcontentloaded")
                        _r["pdf_url"] = _np.url
                        _np.close()
                    except Exception as _e:        # noqa: BLE001
                        _r["pdf_url"] = f"{type(_e).__name__}: {str(_e)[:120]}"
                    _r["pdf_belgi"] = (_oldin, _pg.evaluate("() => document.querySelector('.yx-chk').checked"))
                _UI[(_w, _tema)] = _r
            except Exception as _e:                # noqa: BLE001
                _UI[(_w, _tema)] = {"xato": f"{type(_e).__name__}: {str(_e)[:300]}"}
            _ctx.close()
    for _login, _pid, _kalit in (("yxl_moliya", PJ, "moliya"), ("yxl_menejer", PJ, "menejer"), ("yxl_admin", P5, "bosh")):
        _ctx = _kontekst(1440, 900, False)
        try:
            _pg = _kirish(_ctx, _login)
            _pg.goto(_B + "/projects", wait_until="networkidle")
            _pg.evaluate(f"() => {{ const c = document.querySelector('.proj-card[data-id=\"{_pid}\"]'); c && selectProj(c); }}")
            _pg.wait_for_timeout(400)
            _t = _pg.evaluate("() => !!document.querySelector('.tab-btn[data-tab=\"yuklar\"]')")
            _m = None
            if _t:
                _loyihani_och(_pg, _pid, "light")
                _m = _pg.evaluate("() => ({chk: document.querySelectorAll('.yx-chk').length, matn: (document.getElementById('tabContent') || {}).innerText || ''})")
            _UI[_kalit] = {"tab": _t, "m": _m}
        except Exception as _e:                    # noqa: BLE001
            _UI[_kalit] = {"xato": f"{type(_e).__name__}: {str(_e)[:300]}"}
        _ctx.close()

_jlu = js(req(C1, "get", f"/api/projects/{PJ}/yuk-xatlari")) or {}
_ids_kut = [d.get("id") for d in _jlu.get("deliveries") or []]
_tiyin_kut = [d.get("jami_tiyin") for d in _jlu.get("deliveries") or []]
_href_kut = f"/api/projects/{PJ}/yuk-xatlari/jamlama-pdf?ids=" + ",".join(str(x) for x in _ids_kut)
for _w in (1440, 390):
    _l = _UI.get((_w, "light")) or {}
    _b = _l.get("boshi") or {}
    check(f"U1 [{_w}] «Yuk xatlari» bo'limi: 6 qator (ro'yxat API tartibida), HAMMASI belgilangan, «Tanlangan: 6 / 6», jami = yuk xatlari "
          f"summalari (tiyindan), «📄 Jamlab olish (6 ta)» — hamma id lar bilan; yon tomonga surilish yo'q",
          _b.get("qator") == 6 and _b.get("belgilangan") == 6 and _b.get("idlar") == _ids_kut and _b.get("soni") == "6 / 6"
          and ixcham(_b.get("jami")) == ixcham(som_hu(sum(_tiyin_kut))) + "so'm" and _b.get("href") == _href_kut
          and _b.get("yozuv") == "📄 Jamlab olish (6 ta)" and _b.get("ochiq") and _b.get("yon"), (_l.get("xato"), _b, _href_kut))
    _bb, _hh, _ha = _l.get("bittasiz") or {}, _l.get("hech") or {}, _l.get("hammasi") or {}
    check(f"U2 [{_w}] birinchisi olib tashlansa — «5 / 6», jami kamayadi, havolada u yo'q; «Hech biri» — havola o'chiq («📄 Yuk xati "
          f"belgilang»); «Hammasi» — yana 6",
          _bb.get("soni") == "5 / 6" and ixcham(_bb.get("jami")) == ixcham(som_hu(sum(_tiyin_kut[1:]))) + "so'm"
          and _bb.get("href") == f"/api/projects/{PJ}/yuk-xatlari/jamlama-pdf?ids=" + ",".join(str(x) for x in _ids_kut[1:])
          and _hh.get("soni") == "0 / 6" and _hh.get("href") is None and _hh.get("ochiq") is False and _hh.get("yozuv") == "📄 Yuk xati belgilang"
          and _ha.get("soni") == "6 / 6" and _ha.get("href") == _href_kut, (_bb, _hh, _ha))
    check(f"U3 [{_w}] qatordagi 📄 — o'sha yuk xati PDF i (yangi oynada), belgilashni O'ZGARTIRMAYDI",
          str(_l.get("pdf_url") or "").endswith(f"/api/deliveries/{_ids_kut[0] if _ids_kut else 0}/pdf") and _l.get("pdf_belgi") == (True, True),
          (_l.get("pdf_url"), _l.get("pdf_belgi")))
    _j = _l.get("joy") or {}
    _tel_ok = (_j.get("summa", {}).get("y", 0) > _j.get("raqam", {}).get("y", 0)) if _w == 390 else \
        (abs(_j.get("summa", {}).get("y", -99) - _j.get("raqam", {}).get("y", 99)) <= 4)
    check(f"U4 [{_w}] qator joylashuvi: summa va 📄 qator ichida ({'telefonda summa matn ostida' if _w == 390 else 'summa raqam bilan bir qatorda'})",
          bool(_j) and _j["pdf"]["r"] <= _j["qator"]["r"] + 1 and _j["summa"]["r"] <= _j["qator"]["r"] + 1 and _tel_ok, _j)
    for _tema in ("light", "dark"):
        _o = (_UI.get((_w, _tema)) or {}).get("o") or {}
        _tb = [t for t in _o.get("tugmalar") or [] if t["tur"] != "karta"]
        _past = [f"{t['sel'][:50]} «{t['matn']}» {t['k']}" for t in _tb if _tema == "dark" and t.get("k") is not None and t["k"] < 3]
        check(f"U5 [{_w} {'yorug' if _tema == 'light' else 'tungi'}] U-13 qoidasi: tugmalar ({len(_tb)}) ruxsat etilgan balandlikda, "
              f"burchak 8 px, yozuvi 13 / 14 / 16 px; belgilash katagi ≤ 22 px; matn shkalada; tungida yozuv o'qiladi (≥ 3:1)",
              len(_tb) >= 9 and not tugma_yomon(_o, _w) and not belgi_yomon(_o) and not shrift_yomon(_o) and not _past
              and len((_o.get("belgilar") or [])) >= 6, [tugma_yomon(_o, _w)[:6], belgi_yomon(_o)[:4], shrift_yomon(_o), _past, len(_tb),
                                                          (_UI.get((_w, _tema)) or {}).get("xato")])
_um, _un, _ub = _UI.get("moliya") or {}, _UI.get("menejer") or {}, _UI.get("bosh") or {}
check("U6 ruxsat: Moliyachida «Yuk xatlari» bo'limi YO'Q; Menejerda bor (6 qator)",
      _um.get("tab") is False and _un.get("tab") is True and ((_un.get("m") or {}).get("chk") == 6), (_um, _un))
check("U7 yuk xatisiz loyiha: bo'lim ochiladi, «Hali yuk xati yo'q» va qayerda yozilishi (belgilash kataklarisiz)",
      _ub.get("tab") is True and (_ub.get("m") or {}).get("chk") == 0 and "Hali yuk xati yo'q" in ((_ub.get("m") or {}).get("matn") or ""),
      _ub)
check("U8 sahifada JS xatosi yo'q", bool(_UI) and not _JS_XATO, _JS_XATO[:5])
try:
    if _br:
        _br.close()
    if _pw:
        _pw.stop()
except Exception:                                  # noqa: BLE001
    pass
_srv.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
