#!/usr/bin/env python3
"""
test_a117_yonalish.py — kech117, A2: YO'NALISHLAR BO'YICHA MOLIYA (egasi QARORLARI kech114 00:08 — QAYTA SO'RALMAYDI;
audit G3-11 / G6-09 shu ichida). Server qismi: `models.Yonalish`, `crud.yonalish_*` / `yonalish_tanlovi`,
`/api/yonalishlar`, `PATCH /api/production/product-types/{id}`, `main._migrate_yonalishlar`,
`services.calculate_split_profit_report` (+ `/api/finance/yonalishlar`, `/api/finance/split-profit-pdf`),
`get_monthly_report` → `yonalishlar_daromadi` / `sof_foyda_tarkibi`, bugungi ko'rsatkich, dashboard grafigi, Moliya PDF.

NIMA UCHUN KERAK (audit kech114 — O'LCHANGAN, asl kod = `staging` 0014a66)
  G3-11  Ikki PDF da ikki xil «Sof foyda»: Moliya −2 618 028, «Gips vs Penoplast» −2 314 731 (Usta KPI, transport,
         «umumiy» belgili «Boshqa», tayyor mahsulot sotuvi tannarxi bo'lingan hisobotda yo'q edi — 303 297 farq).
  G6-09  Moliya PDF: 1 674 000 − 4 288 944 ≠ −2 618 028 (tayyor mahsulot sotuvi tannarxi 3 084 hech qaysi qatorda yo'q).
  QAROR  Gips moliyadan butunlay olib tashlanadi; yo'nalishlarni korxona o'zi nomlaydi / guruhlaydi (har MRP turi bittasiga,
         penoplast detallari — «Penoplast»); umumiy xarajatlar — daromad ulushida; kassa — BITTA.
TALAB: yo'nalishlar sof foydasi yig'indisi = Moliya sof foydasi (tiyinigacha va butun so'mda); har ustunda daromad −
  tannarx − jami xarajat = sof foyda; daromad / tannarx — sotilgan mahsulot yo'nalishiga aniq; yo'nalishli hodim / xarajat /
  transport / kirim / brak / tayyor mahsulot yo'qotishi — 100 % o'shanga; qolgani — daromad ulushida (daromad yo'q —
  teng); korxona chegarasi (begona yo'nalish — «topilmadi»); eski `production_type` 'penoplast' — asosiy yo'nalish.
BO'LIMLAR: A — yo'nalishlar API; B — yozish yo'llari; C — migratsiya; D — yo'nalishlar hisoboti; E — boshqa ko'rinishlar
  (oylik hisobot, bugun, grafik, PDF); F — zaxira / tozalash / tiklash; Z — xatolar va huquq.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI (yangi nomlar — `getattr`,
  HTTP istisno — 599).
ISHLATISH: python3 tools/test_a117_yonalish.py
"""
import os
import re
import sys
import zlib
import base64
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "a117_yonalish_test"
_T = tempfile.mkdtemp(prefix="a117yon_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'a117_yonalish_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
import models                                      # noqa: E402
import services                                    # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal, tashkent_date, tashkent_oy_oraligi   # noqa: E402
from models import (UserRole, Inventory, Project, ProjectStatus, Order, OrderItem, OrderType, OrderStatus,   # noqa: E402
                    Master, ReturnItem, ReturnReason, FinishedProduct, FinishedProductSale, FinishedProductLoss,
                    InventoryMovement, InventoryReceipt, ExpenseTransaction, TransportExpense, Employee, StockSource,
                    ProductionStatus, KIRIM_TANNARX_MANBA)
from production_models import Company, ProductType   # noqa: E402
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


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.content = b""
        self.headers = {}

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
        return {}


def xavfsiz(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return {"XATO": f"{type(e).__name__}: {e}"}


def teng(a, b, eps=0.005):
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:                      # noqa: BLE001
        return False


def yaxlit(x, birlik=1):
    return int((Decimal(repr(float(x))) * birlik).quantize(Decimal(1), rounding=ROUND_HALF_UP))


# ── PDF matni (kutubxonasiz; test_a116_pdf bilan bir usul) ─────────────────────────────────────────────────────
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
    try:
        obyektlar = {int(n): tana for n, tana in re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", bayt, re.S)}
    except Exception:                      # noqa: BLE001
        return []
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
    for n in sorted(obyektlar):
        tana = obyektlar[n]
        if b"stream" not in tana or b"/Type /Font" in tana:
            continue
        try:
            _, data = _oqim(tana)
        except Exception:                  # noqa: BLE001
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


def son(matn):
    """«−36 000 so'm» / «+100 000» / «864 000 so'm» → ishorali butun son (None — son yo'q)."""
    t = (matn or "").replace("−", "-").replace("\xa0", " ")
    m = re.fullmatch(r"\s*([-+])?\s*(\d[\d ]*)(?:\s*so'm)?\s*", t)
    if not m:
        return None
    v = int(m.group(2).replace(" ", ""))
    return -v if m.group(1) == "-" else v


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
BUGUN = tashkent_date()
YIL, OY = BUGUN.year, BUGUN.month
O_YIL, O_OY = (YIL, OY - 1) if OY > 1 else (YIL - 1, 12)
OY_BOSHI, OY_OXIRI = tashkent_oy_oraligi(YIL, OY)
T = OY_BOSHI + timedelta(days=1, hours=3)          # oyning 2-kuni (Toshkent) — hisobot oyi
T2 = T + timedelta(hours=2)                         # yakunlanishdan keyin (qaytarish hodisasi)
O_BOSHI, _o_oxiri = tashkent_oy_oraligi(O_YIL, O_OY)
T_OTGAN = O_BOSHI + timedelta(days=3)               # o'tgan oy

s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="A117 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "a117_admin", "Parol123!", UserRole.ADMIN, "A117 Admin", company_id=1)
    auth.create_user(s, "a117_ombor", "Parol123!", UserRole.WAREHOUSE, "A117 Omborchi", company_id=1)
    auth.create_user(s, "b117_admin", "Parol123!", UserRole.ADMIN, "B117 Admin", company_id=2)
PRJ = Project(company_id=1, project_number="PRJ-A117", client_name="A117 mijoz", project_name="A117 loyiha",
              status=ProjectStatus.DRAFT)
PENO = Inventory(company_id=1, item_name="A117 Penoplast", unit="dona", stock_quantity=1000, price_per_unit=800_000,
                 volume_per_unit=0.9, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
MAT = Inventory(company_id=1, item_name="A117 Akril", unit="kg", stock_quantity=1000, price_per_unit=10_000,
                category="Kimyoviy qo'shimchalar")
USTA = Master(company_id=1, name="A117 Usta", phone="+998900117001", cashback_percent=10)
s.add_all([PRJ, PENO, MAT, USTA])
s.commit()
ID = {"PRJ": PRJ.id, "PENO": PENO.id, "MAT": MAT.id, "USTA": USTA.id}
with contextlib.redirect_stdout(io.StringIO()):
    crud.set_setting(s, "ehson_percent", "5", company_id=1)
s.close()

CA = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CW = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CN = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_la = req(CA, "post", "/login", data={"username": "a117_admin", "password": "Parol123!"}, follow_redirects=False)
_lw = req(CW, "post", "/login", data={"username": "a117_ombor", "password": "Parol123!"}, follow_redirects=False)
_lb = req(CB, "post", "/login", data={"username": "b117_admin", "password": "Parol123!"}, follow_redirects=False)
if _la.status_code != 302 or _lb.status_code != 302:
    print("LOGIN BO'LMADI", _la.status_code, _lb.status_code)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

Yonalish = getattr(models, "Yonalish", None)


def yon_ro(c, hammasi=False):
    r = req(c, "get", "/api/yonalishlar" + ("?hammasi=true" if hammasi else ""))
    d = js(r)
    return r.status_code, (d if isinstance(d, list) else [])


def yon_yarat(c, nom):
    r = req(c, "post", "/api/yonalishlar", json={"nom": nom})
    return r.status_code, (js(r) if isinstance(js(r), dict) else {})


def db_ol(model, pk):
    d = SessionLocal()
    try:
        o = d.get(model, pk) if pk else None
        if o is None:
            return None
        return {c.key: getattr(o, c.key) for c in model.__table__.columns}
    finally:
        d.close()


def sanoq(model, **f):
    d = SessionLocal()
    try:
        q = d.query(model)
        for k, v in f.items():
            q = q.filter(getattr(model, k) == v)
        return q.count()
    finally:
        d.close()


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Yo'nalishlar API")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_st, _ra = yon_ro(CA, True)
ASOSIY = next((y for y in _ra if y.get("asosiy")), {})
check("A1 A korxona: GET 200, asosiy yo'nalish «Penoplast» (ishga tushish migratsiyasi yaratgan), yashirin emas",
      _st == 200 and ASOSIY.get("nom") == "Penoplast" and ASOSIY.get("yashirin") is False and len(_ra) == 1, [_st, _ra])
_st, _rb = yon_ro(CB, True)
B_ASOSIY = next((y for y in _rb if y.get("asosiy")), {})
check("A2 B korxona (ishga tushishdan KEYIN yaratilgan): asosiy yo'nalish ro'yxatda o'zi yaratiladi, A nikidan boshqa id",
      _st == 200 and B_ASOSIY.get("nom") == "Penoplast" and B_ASOSIY.get("id") and B_ASOSIY.get("id") != ASOSIY.get("id"),
      [_st, _rb, ASOSIY])
_st, M = yon_yarat(CA, "  Metall   konstruksiya ")
check("A3 yangi yo'nalish: bo'shliqlar tozalanadi («Metall konstruksiya»), asosiy emas", _st == 200 and
      M.get("nom") == "Metall konstruksiya" and M.get("asosiy") is False, [_st, M])
_st2, _d2 = yon_yarat(CA, "METALL konstruksiya")
check("A4 takror nom (katta / kichik harf farqsiz) — 400, sababi bilan", _st2 == 400 and "allaqachon" in str(_d2), [_st2, _d2])
_bad = [req(CA, "post", "/api/yonalishlar", json=b).status_code for b in
        ({"nom": ""}, {"nom": "   "}, {"nom": "x" * 61}, {"nom": 5}, {"nom": "Ok", "kod": "penoplast"}, {})]
check("A5 noto'g'ri tana — 400 (bo'sh, faqat bo'shliq, 61 belgi, son, ortiqcha kalit, kalitsiz)", _bad == [400] * 6, _bad)
_st, Y = yon_yarat(CA, "Yog'och")
_st, BM = yon_yarat(CB, "B Metall")
check("A6 yana ikki yo'nalish (A: «Yog'och», B: «B Metall»)", Y.get("id") and BM.get("id"), [Y, BM])
_r = req(CA, "put", f"/api/yonalishlar/{M.get('id')}", json={"nom": "Metall"})
M = js(_r) if _r.status_code == 200 else M
check("A7 nomini o'zgartirish — 200 («Metall»)", _r.status_code == 200 and M.get("nom") == "Metall", [_r.status_code, _r.text[:200]])
_r1 = req(CA, "put", f"/api/yonalishlar/{ASOSIY.get('id')}", json={"yashirin": True})
_r2 = req(CA, "put", f"/api/yonalishlar/{ASOSIY.get('id')}", json={"nom": "Penoplast fasad"})
_r3 = req(CA, "put", f"/api/yonalishlar/{M.get('id')}", json={"kod": "penoplast"})
_r4 = req(CA, "put", f"/api/yonalishlar/{M.get('id')}", json={"yashirin": "ha"})
check("A8 asosiy yashirilmaydi (400); nomi o'zgaradi (200); `kod` / noto'g'ri tur — 400",
      _r1.status_code == 400 and "yashirilmaydi" in _r1.text and _r2.status_code == 200 and _r3.status_code == 400
      and _r4.status_code == 400, [_r1.status_code, _r1.text[:120], _r2.status_code, _r3.status_code, _r4.status_code])
req(CA, "put", f"/api/yonalishlar/{ASOSIY.get('id')}", json={"nom": "Penoplast"})
_rb1 = req(CB, "put", f"/api/yonalishlar/{M.get('id')}", json={"nom": "O'g'irlik"})
_rb2 = req(CB, "delete", f"/api/yonalishlar/{M.get('id')}")
_, _rb_l = yon_ro(CB, True)
check("A9 B korxona A ning yo'nalishini o'zgartira / o'chira olmaydi (404), ro'yxatida A niki yo'q",
      _rb1.status_code == 404 and _rb2.status_code == 404 and M.get("id") not in [y.get("id") for y in _rb_l]
      and db_ol(Yonalish, M.get("id")) and db_ol(Yonalish, M.get("id")).get("nom") == "Metall" if Yonalish else False,
      [_rb1.status_code, _rb2.status_code, _rb_l])
_rw_l = req(CW, "get", "/api/yonalishlar")
_rw_p = req(CW, "post", "/api/yonalishlar", json={"nom": "Omborchi yo'nalishi"})
check("A10 omborchi: ro'yxat 200 (tanlovlar uchun), qo'shish 403", _rw_l.status_code == 200 and _rw_p.status_code == 403,
      [_rw_l.status_code, _rw_p.status_code])
_st, BOSH = yon_yarat(CA, "Bo'sh yo'nalish")
_rd = req(CA, "delete", f"/api/yonalishlar/{BOSH.get('id')}")
_rd2 = req(CA, "delete", f"/api/yonalishlar/{ASOSIY.get('id')}")
check("A11 ishlatilmagan yo'nalish o'chadi (200); asosiy o'chmaydi (400)",
      _rd.status_code == 200 and (db_ol(Yonalish, BOSH.get("id")) is None if Yonalish else False) and _rd2.status_code == 400,
      [_rd.status_code, _rd2.status_code, _rd2.text[:150]])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Yozish yo'llari — hodim, xarajat, transport, kirim, MRP turi")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
MID, YID, AID = M.get("id"), Y.get("id"), ASOSIY.get("id")


def tx(c, **k):
    t = {"category": "boshqa", "amount": 1000.0, "date": T.strftime("%Y-%m-%dT%H:%M:%S")}
    t.update(k)
    r = req(c, "post", "/api/finance/transactions", json=t)
    return r.status_code, (js(r) if isinstance(js(r), dict) else {})


_b1 = [tx(CA, amount=1001.0, yonalish_id=MID), tx(CA, amount=1002.0, production_type="penoplast"),
       tx(CA, amount=1003.0, production_type="gips"), tx(CA, amount=1004.0, production_type="umumiy"), tx(CA, amount=1005.0)]
_b1x = [db_ol(ExpenseTransaction, d.get("id")) or {} for _s, d in _b1]
check("B1 xarajat: yo'nalish id → o'sha; eski 'penoplast' → asosiy (matn saqlanadi); 'gips' / 'umumiy' / yo'q → «Umumiy»",
      [x.get("yonalish_id") for x in _b1x] == [MID, AID, None, None, None]
      and [x.get("production_type") for x in _b1x] == [None, "penoplast", "gips", "umumiy", None]
      and [st for st, _d in _b1] == [200] * 5, [(st, d.get("yonalish_id")) for st, d in _b1] + [_b1x])
_n0 = sanoq(ExpenseTransaction, company_id=1)
_bb = tx(CA, amount=1006.0, yonalish_id=BM.get("id"))
_bn = tx(CA, amount=1007.0, yonalish_id=999_999)
check("B2 B korxonaning / yo'q yo'nalishi — 400 «topilmadi» (farqsiz), hech narsa yozilmadi",
      _bb[0] == 400 and _bn[0] == 400 and "topilmadi" in str(_bb[1]) and str(_bb[1]) == str(_bn[1])
      and sanoq(ExpenseTransaction, company_id=1) == _n0, [_bb, _bn])
_t1 = _b1[1][1].get("id")
_pu = req(CA, "put", f"/api/finance/transactions/{_t1}", json={"category": "boshqa", "amount": 1002.0, "yonalish_id": None})
_x = db_ol(ExpenseTransaction, _t1) or {}
_pu2 = req(CA, "put", f"/api/finance/transactions/{_t1}", json={"category": "boshqa", "amount": 1002.0, "notes": "izoh"})
_x2 = db_ol(ExpenseTransaction, _t1) or {}
check("B3 tahrirda «Umumiy» — yonalish NULL VA eski matn NULL (migratsiya qayta «Penoplast» qilmaydi); kalit yo'q — o'zgarmaydi",
      _pu.status_code == 200 and _x.get("yonalish_id") is None and _x.get("production_type") is None
      and _pu2.status_code == 200 and _x2.get("yonalish_id") is None and _x2.get("notes") == "izoh", [_pu.text[:200], _x, _x2])
_tr = req(CA, "post", "/api/transport-expenses", json={"amount": 70_000, "yonalish_id": MID, "materials_note": "A117 M"})
_trb = req(CA, "post", "/api/transport-expenses", json={"amount": 5, "yonalish_id": BM.get("id")})
_trx = db_ol(TransportExpense, (js(_tr) or {}).get("id")) or {}
check("B4 transport: yo'nalish yoziladi; B niki — 400", _tr.status_code == 200 and _trx.get("yonalish_id") == MID
      and _trb.status_code == 400, [_tr.text[:200], _trb.status_code, _trx])
_n_k = sanoq(InventoryReceipt, company_id=1)
_rc = req(CA, "post", "/api/inventory/receipt", json={
    "items": [{"inventory_id": ID["MAT"], "quantity": 1, "price_per_unit": 10_000}], "transport_cost": 7_000,
    "add_to_cost": False, "yonalish_id": YID, "notes": "A117 kirim", "receipt_date": T.strftime("%Y-%m-%d")})
_rcid = (js(_rc) or {}).get("receipt_id")
_rcx = db_ol(InventoryReceipt, _rcid) or {}
d = SessionLocal()
try:
    _rc_et = [(e.yonalish_id, float(e.amount), e.category) for e in d.query(ExpenseTransaction).filter(
        ExpenseTransaction.notes.like(f"%Kirim #{_rcid}%"))] if _rcid else []
finally:
    d.close()
_rcb = req(CA, "post", "/api/inventory/receipt", json={
    "items": [{"inventory_id": ID["MAT"], "quantity": 1, "price_per_unit": 10_000}], "transport_cost": 1_000,
    "yonalish_id": BM.get("id")})
check("B5 kirim: hujjat va uning qo'shimcha xarajati (transport 7 000) — o'sha yo'nalishda; B niki — 400, hujjat yozilmadi",
      _rc.status_code == 200 and _rcx.get("yonalish_id") == YID and _rc_et == [(YID, 7000.0, "transport_kirim")]
      and _rcb.status_code == 400 and sanoq(InventoryReceipt, company_id=1) == _n_k + 1,
      [_rc.text[:200], _rcx.get("yonalish_id"), _rc_et, _rcb.status_code, _rcb.text[:150]])
_e1 = req(CA, "post", "/api/employees", json={"name": "A117 Metall hodimi", "pay_type": "fixed", "fixed_amount": 2_000_000,
                                              "yonalish_id": MID})
_e2 = req(CA, "post", "/api/employees", json={"name": "A117 Umumiy hodim", "pay_type": "fixed", "fixed_amount": 1_000_000,
                                              "yonalish_id": None})
_e3 = req(CA, "post", "/api/employees", json={"name": "A117 Eski hodim", "pay_type": "fixed", "fixed_amount": 0,
                                              "production_type": "penoplast"})
E1, E2, E3 = (js(_e1) or {}).get("id"), (js(_e2) or {}).get("id"), (js(_e3) or {}).get("id")
_eb = req(CA, "post", "/api/employees", json={"name": "A117 Begona", "pay_type": "fixed", "fixed_amount": 1,
                                              "yonalish_id": BM.get("id")})
_el = {e.get("id"): e for e in (js(req(CA, "get", "/api/employees")) or [])}
check("B6 hodim: yo'nalishi / «Umumiy» / eski 'penoplast' → asosiy; ro'yxatda id va nomi; B niki — 400",
      _el.get(E1, {}).get("yonalish_id") == MID and _el.get(E1, {}).get("yonalish_nom") == "Metall"
      and _el.get(E2, {}).get("yonalish_id") is None and _el.get(E3, {}).get("yonalish_id") == AID
      and _eb.status_code == 400, [_e1.status_code, _e2.status_code, _e3.status_code, _eb.status_code,
                                   {k: (v.get("yonalish_id"), v.get("yonalish_nom")) for k, v in _el.items()}])
_ep = req(CA, "put", f"/api/employees/{E3}", json={"notes": "faqat izoh"})
_ep2 = req(CA, "put", f"/api/employees/{E3}", json={"yonalish_id": YID})
_ep3 = req(CA, "put", f"/api/employees/{E3}", json={"yonalish_id": BM.get("id")})
check("B7 hodim tahriri: kalit yo'q — o'zgarmaydi; yangi yo'nalish — yoziladi; B niki — 400 (o'zgarmadi)",
      _ep.status_code == 200 and _ep2.status_code == 200 and _ep3.status_code == 400
      and (db_ol(Employee, E3) or {}).get("yonalish_id") == YID, [_ep.status_code, _ep2.status_code, _ep3.status_code,
                                                                     (db_ol(Employee, E3) or {}).get("yonalish_id")])
req(CA, "put", f"/api/employees/{E3}", json={"yonalish_id": AID})


def tur(c, nom, **k):
    t = {"name": nom, "unit": "m²", "input_template": "quantity_only", "pricing_formula": "unit_based"}
    t.update(k)
    r = req(c, "post", "/api/production/product-types", json=t)
    return r.status_code, (js(r) if isinstance(js(r), dict) else {})


_s1, PT_M = tur(CA, "A117 Travertin", yonalish_id=MID)
_s2, PT_N = tur(CA, "A117 Belgisiz tur")
_s3, _pb = tur(CA, "A117 Begona tur", yonalish_id=BM.get("id"))
_s4, PT_B = tur(CB, "B117 tur", yonalish_id=BM.get("id"))
check("B8 MRP turi: yo'nalish bilan (A: Metall) / yo'nalishsiz (NULL — «Belgilanmagan»); B niki — 400",
      _s1 == 200 and PT_M.get("yonalish_id") == MID and _s2 == 200 and PT_N.get("yonalish_id") is None and _s3 == 400
      and _s4 == 200, [_s1, PT_M, _s2, PT_N, _s3, _pb, _s4])
_x1 = js(req(CA, "get", "/api/production/product-types/xulosa"))
_x1 = {t.get("id"): t for t in (_x1 if isinstance(_x1, list) else [])}
check("B9 turlar jadvali: yo'nalish nomi / NULL", _x1.get(PT_M.get("id"), {}).get("yonalish_nom") == "Metall"
      and _x1.get(PT_N.get("id"), {}).get("yonalish_nom") is None and "yonalish_id" in _x1.get(PT_N.get("id"), {}), _x1)
_pp = [req(CA, "patch", f"/api/production/product-types/{PT_N.get('id')}", json=b).status_code for b in
       ({"yonalish_id": BM.get("id")}, {"yonalish_id": None}, {"yonalish_id": "3"}, {"yonalish_id": YID, "name": "x"})]
_ppb = req(CB, "patch", f"/api/production/product-types/{PT_N.get('id')}", json={"yonalish_id": BM.get("id")}).status_code
_ppw = req(CW, "patch", f"/api/production/product-types/{PT_M.get('id')}", json={"yonalish_id": MID}).status_code
check("B10 turga biriktirish: B niki / null / matn / ortiqcha kalit — 400; B korxona A turiga — 404; omborchi — 200 (turlar "
      "huquqi bilan bir)", _pp == [400, 400, 400, 400] and _ppb == 404 and _ppw == 200 and
      (db_ol(ProductType, PT_N.get("id")) or {}).get("yonalish_id") is None, [_pp, _ppb, _ppw])
d = SessionLocal()
try:
    _g = xavfsiz(lambda: (d.add(ExpenseTransaction(company_id=2, date=T, category="boshqa", amount=1, yonalish_id=MID)),
                          d.flush()))
    d.rollback()
finally:
    d.close()
check("B11 ORM qo'riqchisi: B xarajatini A yo'nalishiga bog'lab bo'lmaydi (TenantMismatchError)",
      isinstance(_g, dict) and "TenantMismatch" in _g.get("XATO", ""), _g)
_ish = {y.get("id"): y.get("ishlatilishi") for y in yon_ro(CA, hammasi=True)[1]}
_rdm = req(CA, "delete", f"/api/yonalishlar/{MID}")
# B13. Yashirilgan yo'nalishga turni YANGIDAN biriktirib bo'lmaydi (400); turning JORIY yo'nalishi yashirilgan bo'lsa —
# o'sha qiymat qayta yuborilsa qabul qilinadi (tahrir yo'nalishni yo'qotmasin)
_st13, YH = yon_yarat(CA, "A117 Yashirin")
_s13, PT_H = tur(CA, "A117 H turi", yonalish_id=YH.get("id"))
_s13b, PT_H2 = tur(CA, "A117 H2 turi", yonalish_id=MID)
req(CA, "put", f"/api/yonalishlar/{YH.get('id')}", json={"yashirin": True})
_p13a = req(CA, "patch", f"/api/production/product-types/{PT_H.get('id')}", json={"yonalish_id": YH.get("id")})
_p13b = req(CA, "patch", f"/api/production/product-types/{PT_H2.get('id')}", json={"yonalish_id": YH.get("id")})
check("B13 turga yashirin yo'nalish: joriy qiymat — 200; boshqa turga YANGIDAN — 400 (sababi), tur o'zgarmadi",
      _s13 == 200 and _s13b == 200 and _p13a.status_code == 200 and _p13b.status_code == 400
      and "yashirilgan" in _p13b.text and (db_ol(ProductType, PT_H2.get("id")) or {}).get("yonalish_id") == MID,
      [_st13, _s13, _s13b, _p13a.status_code, _p13b.status_code, _p13b.text[:150]])
check("B12 ISHLATILGAN yo'nalish o'chirilmaydi — 400, sababi (qaysi yozuvlar), faqat yashirish; ishlatilishi ro'yxatda",
      _rdm.status_code == 400 and "ishlatilgan" in _rdm.text and "yashirish" in _rdm.text
      and (db_ol(Yonalish, MID) is not None if Yonalish else False)
      and isinstance(_ish.get(MID), dict) and _ish[MID].get("hodim", 0) >= 1 and _ish[MID].get("transport", 0) >= 1,
      [_rdm.status_code, _rdm.text[:200], _ish.get(MID)])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Ishga tushish migratsiyasi (`main._migrate_yonalishlar`)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
d = SessionLocal()
try:
    _ids = {}
    for tbl, cols, qiy in (
            ("expense_transactions", "company_id, date, category, amount, production_type, source",
             "1, :t, 'boshqa', 11, :p, 'manual'"),
            ("transport_expenses", "company_id, amount, expense_date, production_type", "1, 12, :t, :p"),
            ("employees", "company_id, name, pay_type, production_type, is_active, is_deleted",
             "1, :n, 'FIXED', :p, false, true"),
            ("inventory_receipts", "company_id, receipt_date, production_type, add_to_cost", "1, :t, :p, false")):
        _ids[tbl] = []
        for i, pt in enumerate(("penoplast", "gips", "umumiy", None)):
            d.execute(text(f"INSERT INTO {tbl} ({cols}) VALUES ({qiy})"), {"t": T_OTGAN, "p": pt, "n": f"C117_{tbl}_{i}"})
            _ids[tbl].append(d.execute(text(f"SELECT MAX(id) FROM {tbl}")).scalar())
    d.add(Company(id=3, name="C117 korxona"))
    d.flush()
    d.execute(text("INSERT INTO expense_transactions (company_id, date, category, amount, production_type, source) "
                   "VALUES (3, :t, 'boshqa', 13, 'penoplast', 'manual')"), {"t": T_OTGAN})
    _c3 = d.execute(text("SELECT MAX(id) FROM expense_transactions")).scalar()
    d.commit()
finally:
    d.close()
with contextlib.redirect_stdout(io.StringIO()) as _out1:
    xavfsiz(getattr(main, "_migrate_yonalishlar", lambda: None))
d = SessionLocal()
try:
    _c3std = d.execute(text("SELECT id FROM yonalishlar WHERE company_id = 3 AND kod = 'penoplast'")).scalar() \
        if Yonalish else None
    _natija = {tbl: [d.execute(text(f"SELECT yonalish_id, production_type FROM {tbl} WHERE id = :i"), {"i": i}).first()
                     for i in _ids[tbl]] for tbl in _ids} if Yonalish else {}
    _c3r = d.execute(text("SELECT yonalish_id FROM expense_transactions WHERE id = :i"), {"i": _c3}).scalar() \
        if Yonalish else None
finally:
    d.close()
check("C1 eski 'penoplast' → korxonaning asosiy yo'nalishi (4 jadval); 'gips' / 'umumiy' / NULL — NULL («Umumiy»); matn saqlanadi",
      all([tuple(r) for r in _natija.get(t, [])] == [(AID, "penoplast"), (None, "gips"), (None, "umumiy"), (None, None)]
          for t in _ids), [_natija, _out1.getvalue()[-400:]])
check("C2 yangi korxona (3): asosiy yo'nalish yaratildi va uning 'penoplast' xarajati SHU korxonaning yo'nalishiga",
      _c3std and _c3r == _c3std and _c3std not in (AID, B_ASOSIY.get("id")), [_c3std, _c3r])
with contextlib.redirect_stdout(io.StringIO()) as _out2:
    xavfsiz(getattr(main, "_migrate_yonalishlar", lambda: None))
check("C3 qayta ishga tushish — hech narsa o'zgarmaydi (yaratish / o'tkazish xabari yo'q)",
      Yonalish is not None and "yaratildi" not in _out2.getvalue() and "o'tkazildi" not in _out2.getvalue(),
      _out2.getvalue()[-300:])
check("C4 B3 dagi «Umumiy» ga o'tkazilgan xarajat qayta «Penoplast» bo'lmadi",
      (db_ol(ExpenseTransaction, _t1) or {}).get("yonalish_id") is None, db_ol(ExpenseTransaction, _t1))
if PG_URL:
    d = SessionLocal()
    try:
        _fk = d.execute(text("SELECT COUNT(*) FROM pg_constraint WHERE contype = 'f' AND conname LIKE '%yonalish_id%'")).scalar()
    finally:
        d.close()
    check("C5 [PG] 5 jadvalda yonalish_id chet el kaliti bor", _fk == 5, _fk)
d = SessionLocal()
try:
    for tbl in _ids:
        d.execute(text(f"DELETE FROM {tbl} WHERE id IN ({','.join(str(i) for i in _ids[tbl])})"))
    d.execute(text("DELETE FROM expense_transactions WHERE company_id = 3"))
    d.commit()
finally:
    d.close()

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Yo'nalishlar hisoboti — yig'indi = Moliya sof foydasi, qoidalar")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
# B yo'llaridagi 1 000 so'mlik sinov xarajatlarini olib tashlaymiz (hisobot raqamlari aniq bo'lsin)
d = SessionLocal()
try:
    d.query(ExpenseTransaction).filter(ExpenseTransaction.company_id == 1,
                                       ExpenseTransaction.amount < 1100).delete(synchronize_session=False)
    d.commit()
    # Buyurtma O1: profil 800 000 (penoplast) + MRP (Metall) 200 000 tayyor mahsulotdan (6 000 × 10); jami 1 000 000,
    # yakunlanganda kelishilgan 900 000; keyin 50 000 «Pul qaytdi» (MRP detali) — kelishilgan 850 000.
    fp_m = FinishedProduct(company_id=1, name="A117 Travertin partiya", category="dynamic_bom", quantity=0,
                           produced_quantity=10, unit="m²", cost_price=60_000, source=StockSource.PRODUCED,
                           production_status=ProductionStatus.READY, product_type_id=PT_M.get("id"))
    d.add(fp_m)
    d.flush()
    o1 = Order(company_id=1, order_number="A117-1", project_id=ID["PRJ"], order_type=OrderType.PRODUCT,
               total_amount=1_000_000, agreed_amount=850_000, status=OrderStatus.READY, completed_at=T,
               master_id=ID["USTA"])
    d.add(o1)
    d.flush()
    it_p = OrderItem(company_id=1, order_id=o1.id, name="A117 profil", category="profil", width=20, thickness=10,
                     length=4, quantity=1, unit_price=800_000, total_price=800_000, is_coated=False,
                     penoplast_id=ID["PENO"])
    it_m = OrderItem(company_id=1, order_id=o1.id, name="A117 travertin", category="mrp_product", quantity=10,
                     unit_price=20_000, total_price=200_000, product_type_id=PT_M.get("id"), finished_product_id=fp_m.id,
                     fp_unit_cost=6_000)
    d.add_all([it_p, it_m])
    d.flush()
    d.add(ReturnItem(company_id=1, order_id=o1.id, order_item_id=it_m.id, item_name="A117 travertin", quantity=2.5,
                     unit="m²", reason=ReturnReason.CUSTOMER_REQUEST, refund_amount=50_000, is_refunded=True,
                     refunded_at=T2, refund_agreed_delta=50_000, returned_at=T2))
    # Buyurtma O2: yo'nalishsiz MRP turi — «Belgilanmagan» (100 000)
    o2 = Order(company_id=1, order_number="A117-2", project_id=ID["PRJ"], order_type=OrderType.PRODUCT,
               total_amount=100_000, agreed_amount=100_000, status=OrderStatus.READY, completed_at=T)
    d.add(o2)
    d.flush()
    it_n = OrderItem(company_id=1, order_id=o2.id, name="A117 belgisiz", category="mrp_product", quantity=1,
                     unit_price=100_000, total_price=100_000, product_type_id=PT_N.get("id"))
    d.add(it_n)
    # Brak: detal braki (O1 profil) harakati 15 000 — penoplast; qo'lda «Brak» chiqimi 10 000 — umumiy
    rb = ReturnItem(company_id=1, order_id=o1.id, order_item_id=it_p.id, item_name="A117 profil", quantity=0.1,
                    unit="metr", reason=ReturnReason.DEFECT, refund_amount=0, is_refunded=False, returned_at=T)
    d.add(rb)
    d.flush()
    d.add(InventoryMovement(company_id=1, inventory_id=ID["MAT"], item_name="A117 Akril", movement_type="out",
                            quantity=1.5, unit="kg", reason="Brak — detal", order_id=o1.id, return_item_id=rb.id,
                            unit_cost=10_000, is_brak=True, created_at=T))
    d.add(InventoryMovement(company_id=1, inventory_id=ID["MAT"], item_name="A117 Akril", movement_type="out",
                            quantity=1, unit="kg", reason="Brak — qo'lda", unit_cost=10_000, is_brak=True, created_at=T))
    # Tayyor mahsulot: penoplast (profil) sotuvi 300 000 / tannarx 100 000; Metall sotuvi 200 000 / 50 000;
    # ishlab chiqarish braki (profil TM) 25 000 — harakati bog'lanmagan, yozuvi bo'yicha penoplast;
    # Metall TM yo'qotishi (omborda) 40 000.
    fp_p = FinishedProduct(company_id=1, name="A117 profil TM", category="profil", quantity=5, produced_quantity=10,
                           unit="metr", cost_price=200_000, source=StockSource.PRODUCED,
                           production_status=ProductionStatus.READY)
    d.add(fp_p)
    d.flush()
    d.add(FinishedProductSale(company_id=1, finished_product_id=fp_p.id, product_name=fp_p.name, quantity=5, unit="metr",
                              unit_price=60_000, total_amount=300_000, cost_amount=100_000, sold_at=T))
    d.add(FinishedProductSale(company_id=1, finished_product_id=fp_m.id, product_name=fp_m.name, quantity=2, unit="m²",
                              unit_price=100_000, total_amount=200_000, cost_amount=50_000, sold_at=T))
    d.add(FinishedProductLoss(company_id=1, finished_product_id=fp_p.id, product_name=fp_p.name, category="profil",
                              quantity=1, unit="metr", cost_amount=25_000, lost_at=T,
                              reason=crud._ISH_BRAK_BELGI + " — qo'shimcha xomashyo sarflandi (mahsulot soniga tegmaydi)"))
    d.add(InventoryMovement(company_id=1, inventory_id=ID["MAT"], item_name="A117 Akril", movement_type="out",
                            quantity=2.5, unit="kg", reason=crud._ISH_BRAK_BELGI, unit_cost=10_000, is_brak=True,
                            created_at=T))
    d.add(FinishedProductLoss(company_id=1, finished_product_id=fp_m.id, product_name=fp_m.name, category="dynamic_bom",
                              quantity=1, unit="m²", cost_amount=40_000, lost_at=T, reason="Omborda singan"))
    d.commit()
    O1, O2, IT_P, IT_M = o1.id, o2.id, it_p.id, it_m.id
finally:
    d.close()
_xs = [tx(CA, category="arenda", amount=1_000_000.0), tx(CA, category="arenda", amount=200_000.0, yonalish_id=MID),
       tx(CA, category="boshqa", amount=300_000.0, yonalish_id=YID), tx(CA, category="reklama", amount=123_456.78)]
_tq = req(CA, "post", "/api/transport-expenses", json={"amount": 30_000})
d = SessionLocal()
try:   # tannarxga qo'shilgan kirim xarajati (Metall) — sof foydaga ham, yo'nalishga ham KIRMAYDI
    d.add(ExpenseTransaction(company_id=1, date=T, category="transport_kirim", amount=9_999, source=KIRIM_TANNARX_MANBA,
                             **({"yonalish_id": MID} if hasattr(ExpenseTransaction, "yonalish_id") else {})))
    d.commit()
finally:
    d.close()
check("D0 fikstura: 4 xarajat, transport, buyurtmalar, TM, brak", [st for st, _d in _xs] == [200] * 4
      and _tq.status_code == 200, [[st for st, _d in _xs], _tq.status_code])

d = SessionLocal()
try:
    REP = xavfsiz(services.get_monthly_report, d, YIL, OY, company_id=1)
    SP = xavfsiz(services.calculate_split_profit_report, d, YIL, OY, company_id=1)
finally:
    d.close()
_api = req(CA, "get", "/api/finance/yonalishlar", params={"year": YIL, "month": OY})
SPA = js(_api) if _api.status_code == 200 else {}
YL = {y.get("nom"): y for y in (SP.get("yonalishlar") or [])} if isinstance(SP, dict) else {}
TK = REP.get("sof_foyda_tarkibi") or {} if isinstance(REP, dict) else {}
SOF = float(REP.get("sof_foyda", 0) or 0) if isinstance(REP, dict) else 0.0
check("D1 API 200 va natija xizmat bilan AYNAN; ustunlar: Penoplast, Metall, Yog'och, Belgilanmagan (tartib)",
      _api.status_code == 200 and SPA.get("yonalishlar") == SP.get("yonalishlar")
      and [y.get("nom") for y in SP.get("yonalishlar", [])] == ["Penoplast", "Metall", "Yog'och", "Belgilanmagan"],
      [_api.status_code, [y.get("nom") for y in (SP.get("yonalishlar") or [])] if isinstance(SP, dict) else SP])
_som = [y["som"] for y in SP.get("yonalishlar", [])] if isinstance(SP, dict) else []
_aniq = [y["aniq"] for y in SP.get("yonalishlar", [])] if isinstance(SP, dict) else []
check("D2 butun so'mda: sof foydalar yig'indisi = Moliya sof foydasi (HALF_UP) = `moliya_sof_foyda`",
      _som and sum(x["sof_foyda"] for x in _som) == yaxlit(SOF) == SP.get("moliya_sof_foyda"),
      [sum(x["sof_foyda"] for x in _som) if _som else None, yaxlit(SOF), SP.get("moliya_sof_foyda") if isinstance(SP, dict) else SP])
check("D3 tiyinda: sof foydalar yig'indisi = Moliya sof foydasi (tiyin, butun sonlar)",
      _aniq and sum(yaxlit(x["sof_foyda"], 100) for x in _aniq) == yaxlit(SOF, 100),
      [sum(yaxlit(x["sof_foyda"], 100) for x in _aniq) if _aniq else None, yaxlit(SOF, 100)])
_ust_ok = all(x["daromad"] - x["tannarx"] - x["jami_xarajat"] == x["sof_foyda"]
              and x["jami_xarajat"] == x["bevosita"] + x["ulush"]
              and sum(x["bevosita_qismlari"].values()) == x["bevosita"] and sum(x["ulush_qismlari"].values()) == x["ulush"]
              for x in _som)
_ust_ok_t = all(yaxlit(x["daromad"], 100) - yaxlit(x["tannarx"], 100) - yaxlit(x["jami_xarajat"], 100) == yaxlit(x["sof_foyda"], 100)
                for x in _aniq)
check("D4 har ustunda: daromad − tannarx − jami xarajat = sof foyda; jami = bevosita + ulush; qismlar yig'indisi (so'm va tiyin)",
      _som and _ust_ok and _ust_ok_t, _som)
_jam = SP.get("jami", {}) if isinstance(SP, dict) else {}
check("D5 JAMI ustuni = qatorlar yig'indisi; JAMI daromad = Moliya daromadi, JAMI tannarx = tannarx_jami (butun so'm)",
      _som and all(_jam.get(k) == sum(x[k] for x in _som) for k in ("daromad", "tannarx", "bevosita", "ulush",
                                                                 "jami_xarajat", "sof_foyda"))
      and _jam.get("daromad") == yaxlit(float(TK.get("daromad_buyurtmalar", 0)) + float(TK.get("daromad_tm", 0)))
      and abs(_jam.get("tannarx", 0) - float(REP.get("tannarx_jami", 0))) <= 1, [_jam, TK, REP.get("tannarx_jami") if isinstance(REP, dict) else None])
_d = {n: YL.get(n, {}).get("aniq", {}).get("daromad") for n in ("Penoplast", "Metall", "Yog'och", "Belgilanmagan")}
check("D6 daromad yo'nalishga ANIQ: Penoplast 720 000 + TM 300 000; Metall 180 000 − qaytarish 50 000 + TM 200 000; "
      "Yog'och 0; Belgilanmagan 100 000 (yo'nalishsiz MRP turi)",
      _d == {"Penoplast": 1_020_000.0, "Metall": 330_000.0, "Yog'och": 0.0, "Belgilanmagan": 100_000.0}, _d)
# tannarx: penoplast hajmi (0.2×0.1/2×4 = 0.04 m³ × 800 000/0.9) + usta haqi ulushi (80%) + TM 100 000;
# Metall: TM detal 60 000 + usta haqi 20% + qaytarish hodisasi (usta haqi −5 000) + TM 50 000
_peno = 0.04 * 800_000 / 0.9
_usta = (900_000 - (_peno + 60_000)) * 0.10
_t = {n: YL.get(n, {}).get("aniq", {}).get("tannarx") for n in ("Penoplast", "Metall", "Belgilanmagan")}
check("D7 tannarx yo'nalishga: Penoplast = hajm + 80% usta haqi + TM 100 000; Metall = TM detal 60 000 + 20% usta haqi "
      "+ qaytarish hodisasi (−5 000) + TM 50 000; Belgilanmagan 0 (tiyinda)",
      teng(_t["Penoplast"], round(_peno + _usta * 0.8 + 100_000, 2), 0.011)
      and teng(_t["Metall"], round(60_000 + _usta * 0.2 - 5_000 + 50_000, 2), 0.011) and teng(_t["Belgilanmagan"], 0),
      [_t, round(_peno + _usta * 0.8 + 100_000, 2), round(60_000 + _usta * 0.2 - 5_000 + 50_000, 2)])
_bq = {n: YL.get(n, {}).get("som", {}).get("bevosita_qismlari", {}) for n in ("Penoplast", "Metall", "Yog'och")}
check("D8 bevosita: Metall — hodim 2 000 000, arenda 200 000, transport 70 000, TM yo'qotishi 40 000; Yog'och — kirim "
      "transporti 7 000 + «Boshqa» 300 000; Penoplast — brak 15 000 (detal) + 25 000 (ishlab chiqarish braki)",
      _bq["Metall"].get("hodimlar") == 2_000_000 and _bq["Metall"].get("doimiy") == 200_000
      and _bq["Metall"].get("transport") == 70_000 and _bq["Metall"].get("tm_yoqotish") == 40_000
      and _bq["Yog'och"].get("qoshimcha") == 307_000 and _bq["Penoplast"].get("brak") == 40_000
      and sum(v for k, v in _bq["Penoplast"].items() if k != "brak") == 0, _bq)
_um = SP.get("umumiy_xarajatlar", {}) if isinstance(SP, dict) else {}
check("D9 umumiy qism: arenda 1 000 000, reklama 123 456.78, transport 30 000, qo'lda brak 10 000, umumiy hodim 1 000 000, "
      "Ehson (5 %) — hisobotdagi bilan; tannarxga qo'shilgan kirim xarajati (9 999) hech qayerda yo'q",
      teng(_um.get("doimiy"), 1_000_000) and teng(_um.get("qoshimcha"), 123_456.78) and teng(_um.get("transport"), 30_000)
      and teng(_um.get("brak"), 10_000) and teng(_um.get("hodimlar"), 1_000_000)
      and teng(_um.get("ehson"), float(REP.get("ehson_xarajat", -1)), 0.011)
      and float(REP.get("ehson_xarajat", 0)) > 0 and not teng(float(TK.get("qoshimcha", 0)) - 123_456.78 - 307_000, 9_999, 1),
      [_um, REP.get("ehson_xarajat") if isinstance(REP, dict) else None, TK.get("qoshimcha")])
_umumiy_jami = sum(float(v) for v in _um.values())
_ul = {n: YL.get(n, {}).get("aniq", {}).get("ulush") for n in ("Penoplast", "Metall", "Yog'och", "Belgilanmagan")}
_vazn = {"Penoplast": 1_020_000, "Metall": 330_000, "Yog'och": 0, "Belgilanmagan": 100_000}
check("D10 umumiy qism DAROMAD ULUSHIDA (Yog'och — daromadsiz, ulushsiz); ulush foizlari",
      all(teng(_ul[n], _umumiy_jami * _vazn[n] / 1_450_000, 0.02) for n in _ul) and SP.get("ulush_usuli") == "daromad"
      and YL.get("Penoplast", {}).get("ulush_foiz") == round(1_020_000 / 1_450_000 * 100, 1),
      [_ul, _umumiy_jami, SP.get("ulush_usuli") if isinstance(SP, dict) else None])
check("D11 «Belgilanmagan» — qaysi MRP turi (nomi bilan); izoh / hisob farqi yo'q",
      SP.get("belgilanmagan_turlar") == ["A117 Belgisiz tur"] and SP.get("izohlar") == []
      and abs(float(SP.get("tekshiruv_farq", 1))) < 1e-6, [SP.get("belgilanmagan_turlar"), SP.get("izohlar"),
                                                             SP.get("tekshiruv_farq")] if isinstance(SP, dict) else SP)
_rpt = {y.get("nom"): y.get("daromad") for y in (REP.get("yonalishlar_daromadi") or [])} if isinstance(REP, dict) else {}
check("D12 oylik hisobot `yonalishlar_daromadi` — yo'nalishlar hisoboti bilan bir qoida, yig'indisi = daromad",
      _rpt == {"Penoplast": 1_020_000.0, "Metall": 330_000.0, "Yog'och": 0.0, "Belgilanmagan": 100_000.0}
      and "turlar_boyicha" not in REP and teng(sum(_rpt.values()), float(REP.get("daromad", 0)), 0.5), [_rpt, REP.get("daromad")])
_tar = sum(float(TK.get(k, 0)) for k in ("doimiy", "qoshimcha", "transport", "brak", "tm_yoqotish", "usta_kpi", "ehson",
                                          "hodimlar"))
check("D13 `sof_foyda_tarkibi` — sof foydaning AYNAN qismlari (daromad − tannarx − 8 xarajat = sof foyda, tiyin ichida)",
      TK and teng(float(TK["daromad_buyurtmalar"]) + float(TK["daromad_tm"]) - float(TK["tannarx_buyurtmalar"])
                  - float(TK["tannarx_tm"]) - _tar, SOF, 0.001) and teng(_tar, float(REP.get("jami_xarajat", 0)), 0.001),
      [TK, SOF])
# Turga yo'nalish biriktirilsa — o'tgan hisobot ham yangi yo'nalishda (tur — yagona manba), jami o'zgarmaydi
_pa = req(CA, "patch", f"/api/production/product-types/{PT_N.get('id')}", json={"yonalish_id": YID})
d = SessionLocal()
try:
    SP2 = xavfsiz(services.calculate_split_profit_report, d, YIL, OY, company_id=1)
finally:
    d.close()
YL2 = {y.get("nom"): y for y in (SP2.get("yonalishlar") or [])} if isinstance(SP2, dict) else {}
check("D14 turga yo'nalish biriktirildi (PATCH 200): «Belgilanmagan» ustuni yo'qoldi, Yog'och daromadi 100 000, jami sof "
      "foyda o'zgarmadi", _pa.status_code == 200 and "Belgilanmagan" not in YL2
      and YL2.get("Yog'och", {}).get("som", {}).get("daromad") == 100_000
      and SP2.get("jami", {}).get("sof_foyda") == SP.get("jami", {}).get("sof_foyda") and SP2.get("belgilanmagan_turlar") == [],
      [_pa.status_code, {k: v.get("som", {}).get("daromad") for k, v in YL2.items()}])
# Daromadsiz o'tgan oy: faqat xarajat — umumiy qism ko'rinadigan yo'nalishlarga TENG, izoh bilan
d = SessionLocal()
try:
    d.add(ExpenseTransaction(company_id=1, date=T_OTGAN, category="arenda", amount=300_000))
    d.add(ExpenseTransaction(company_id=1, date=T_OTGAN, category="boshqa", amount=90_000,
                             **({"yonalish_id": MID} if hasattr(ExpenseTransaction, "yonalish_id") else {})))
    d.commit()
    SP3 = xavfsiz(services.calculate_split_profit_report, d, O_YIL, O_OY, company_id=1)
    REP3 = xavfsiz(services.get_monthly_report, d, O_YIL, O_OY, company_id=1)
finally:
    d.close()
YL3 = {y.get("nom"): y.get("som", {}) for y in (SP3.get("yonalishlar") or [])} if isinstance(SP3, dict) else {}
check("D15 daromadsiz oy: `teng` usuli + izoh; arenda 300 000 → 100 000 × 3; Metall + 90 000 bevosita; yig'indi = −390 000",
      isinstance(SP3, dict) and SP3.get("ulush_usuli") == "teng" and any("daromad yo'q" in i for i in SP3.get("izohlar", []))
      and YL3.get("Penoplast", {}).get("ulush") == 100_000 and YL3.get("Yog'och", {}).get("ulush") == 100_000
      and YL3.get("Metall", {}).get("jami_xarajat") == 190_000
      and sum(v.get("sof_foyda", 0) for v in YL3.values()) == yaxlit(float(REP3.get("sof_foyda", 0))) == -390_000,
      [SP3 if not isinstance(SP3, dict) else (SP3.get("ulush_usuli"), SP3.get("izohlar"), YL3)])
# Yashirilgan yo'nalish: shu oyda summasi bo'lsa — ustun qoladi («yashirin» belgisi), aks holda — yo'q; tanlovda yo'q
_h = req(CA, "put", f"/api/yonalishlar/{YID}", json={"yashirin": True})
d = SessionLocal()
try:
    SP4 = xavfsiz(services.calculate_split_profit_report, d, YIL, OY, company_id=1)
finally:
    d.close()
_st, _vis = yon_ro(CA)
YL4 = {y.get("nom"): y for y in (SP4.get("yonalishlar") or [])} if isinstance(SP4, dict) else {}
check("D16 yashirilgan (ishlatilgan) Yog'och: ro'yxatda yo'q, hisobotda summasi bilan (yashirin: true), korinadigan_soni 2",
      _h.status_code == 200 and "Yog'och" not in [y.get("nom") for y in _vis] and YL4.get("Yog'och", {}).get("yashirin") is True
      and SP4.get("korinadigan_soni") == 2, [_h.status_code, _vis, {k: v.get("yashirin") for k, v in YL4.items()}])
_hx = tx(CA, amount=555.0, yonalish_id=YID)
check("D17 yashirin yo'nalishga YANGI xarajat — 400 (sababi bilan)", _hx[0] == 400 and "yashirilgan" in str(_hx[1]), _hx)
req(CA, "put", f"/api/yonalishlar/{YID}", json={"yashirin": False})
d = SessionLocal()
try:
    SPB = xavfsiz(services.calculate_split_profit_report, d, YIL, OY, company_id=2)
finally:
    d.close()
check("D18 B korxona hisobotida A ning yo'nalishlari va summalari yo'q (faqat «Penoplast», «B Metall» — 0)",
      isinstance(SPB, dict) and [y.get("nom") for y in SPB.get("yonalishlar", [])] == ["Penoplast", "B Metall"]
      and SPB.get("jami", {}).get("daromad") == 0, SPB if not isinstance(SPB, dict) else [y.get("nom") for y in (SPB.get("yonalishlar") or [])] or SPB)

# D19. Butun so'mga yaxlitlash — ustunlarni ALOHIDA yaxlitlash yig'indini buzadigan holat (uchta teng daromadli yo'nalish,
# umumiy xarajat 3 ga bo'linmaydi) O'TGAN oyda quriladi; shart bajarilguncha 1 so'mlik umumiy xarajat qo'shiladi (oddiy
# yaxlitlash yig'indisi ≠ Moliya sof foydasi bo'lishi SHART — aks holda sinov o'z maqsadiga yetmaydi).
d = SessionLocal()
try:
    _pty = ProductType(company_id=1, name="A117 D19 turi", unit="dona", input_template="quantity_only",
                       pricing_formula="unit_based", **({"yonalish_id": YID} if hasattr(ProductType, "yonalish_id") else {}))
    d.add(_pty)
    d.flush()
    o19 = Order(company_id=1, order_number="A117-19", project_id=ID["PRJ"], order_type=OrderType.PRODUCT,
                total_amount=300_000, agreed_amount=300_000, status=OrderStatus.READY, completed_at=T_OTGAN)
    d.add(o19)
    d.flush()
    d.add_all([
        OrderItem(company_id=1, order_id=o19.id, name="A117 D19 loy", category="loy_sotish", quantity=1,
                  unit_price=100_000, total_price=100_000),
        OrderItem(company_id=1, order_id=o19.id, name="A117 D19 metall", category="mrp_product", quantity=1,
                  unit_price=100_000, total_price=100_000, product_type_id=PT_M.get("id")),
        OrderItem(company_id=1, order_id=o19.id, name="A117 D19 uchinchi", category="mrp_product", quantity=1,
                  unit_price=100_000, total_price=100_000, product_type_id=_pty.id)])
    d.commit()
finally:
    d.close()
_d19 = None
for _i19 in range(7):
    d = SessionLocal()
    try:
        _sp19 = xavfsiz(services.calculate_split_profit_report, d, O_YIL, O_OY, company_id=1)
    finally:
        d.close()
    _y19 = (_sp19.get("yonalishlar") or []) if isinstance(_sp19, dict) else []
    _oddiy = sum(yaxlit((y.get("aniq") or {}).get("sof_foyda", 0)) for y in _y19)
    if _y19 and _oddiy != _sp19.get("moliya_sof_foyda"):
        _d19 = _sp19
        break
    d = SessionLocal()
    try:
        d.add(ExpenseTransaction(company_id=1, date=T_OTGAN, category="boshqa", amount=1))
        d.commit()
    finally:
        d.close()
_s19 = [(y.get("som") or {}) for y in ((_d19 or {}).get("yonalishlar") or [])]
check("D19 ustunlarni alohida yaxlitlash yig'indini buzadigan oyda ham: sof foydalar yig'indisi (so'm) = Moliya sof foydasi, "
      "har ustunda D − T − J = S (eng katta qoldiq usuli)",
      _d19 is not None and len(_s19) >= 3 and sum(x.get("sof_foyda", 0) for x in _s19) == _d19.get("moliya_sof_foyda")
      and all(x["daromad"] - x["tannarx"] - x["jami_xarajat"] == x["sof_foyda"] for x in _s19),
      [(_d19 or {}).get("moliya_sof_foyda"), _s19[:4], _oddiy if _y19 else None])

# D20. «Belgilanmagan» daromadning MRP turidan boshqa MANBALARI (zip 115 jonli sinovi: sinovda 140 000 so'm «Belgilanmagan»
# edi, sababi ko'rinmasdi) — eski turkumli detal, turi tanlanmagan MRP detali, turi / asosiy turkumi yo'q TM sotuvi,
# mahsuloti o'chirilgan TM sotuvi: nomi va AYNAN summasi bilan (o'tgan oyda)
d = SessionLocal()
try:
    # yangi, yo'nalishi BIRIKTIRILMAGAN tur (PT_N D14 da biriktirilgan)
    _pt20 = ProductType(company_id=1, name="A117 D20 belgisiz tur", unit="dona", input_template="quantity_only",
                        pricing_formula="unit_based")
    d.add(_pt20)
    d.flush()
    o20 = Order(company_id=1, order_number="A117-20", project_id=ID["PRJ"], order_type=OrderType.PRODUCT,
                total_amount=45_000, agreed_amount=45_000, status=OrderStatus.READY, completed_at=T_OTGAN)
    d.add(o20)
    d.flush()
    d.add_all([OrderItem(company_id=1, order_id=o20.id, name="A117 D20 termopanel", category="termopanel", quantity=1,
                         unit_price=20_000, total_price=20_000),
               OrderItem(company_id=1, order_id=o20.id, name="A117 D20 turisiz", category="mrp_product", quantity=1,
                         unit_price=10_000, total_price=10_000),
               # turi BOR, lekin yo'nalishi biriktirilmagan — manbalarda EMAS (u `belgilanmagan_turlar` da)
               OrderItem(company_id=1, order_id=o20.id, name="A117 D20 belgisiz tur", category="mrp_product", quantity=1,
                         unit_price=15_000, total_price=15_000, product_type_id=_pt20.id)])
    fp20 = FinishedProduct(company_id=1, name="A117 gips TM", category="gips", quantity=3, produced_quantity=5,
                           unit="dona", cost_price=1_000, source=StockSource.PRODUCED,
                           production_status=ProductionStatus.READY)
    d.add(fp20)
    d.flush()
    d.add_all([FinishedProductSale(company_id=1, finished_product_id=fp20.id, product_name=fp20.name, quantity=1,
                                   unit="dona", unit_price=12_345, total_amount=12_345, cost_amount=1_000, sold_at=T_OTGAN),
               FinishedProductSale(company_id=1, finished_product_id=None, product_name="A117 o'chirilgan TM", quantity=1,
                                   unit="dona", unit_price=7_000, total_amount=7_000, cost_amount=0, sold_at=T_OTGAN)])
    d.commit()
finally:
    d.close()
d = SessionLocal()
try:
    _sp20 = xavfsiz(services.calculate_split_profit_report, d, O_YIL, O_OY, company_id=1)
finally:
    d.close()
_bm20 = {b.get("nom"): b.get("summa") for b in ((_sp20 or {}).get("belgilanmagan_manbalar") or [])} \
    if isinstance(_sp20, dict) else {}
_kut20 = {"Eski «termopanel» turkumli detal": 20_000.0, "MRP detali — mahsulot turi tanlanmagan": 10_000.0,
          "Tayyor mahsulot sotuvi «A117 gips TM» (turkumi: gips)": 12_345.0,
          "Tayyor mahsulot sotuvi «A117 o'chirilgan TM» — mahsulot o'chirilgan": 7_000.0}
_b20 = [y for y in ((_sp20 or {}).get("yonalishlar") or []) if y.get("belgilanmagan")] if isinstance(_sp20, dict) else []
check("D20 «Belgilanmagan» manbalari: eski turkum, turisiz MRP detali, gips TM, o'chirilgan mahsulot sotuvi — nomi va AYNAN "
      "summasi; biriktirilmagan MRP turi (A117 D20 belgisiz tur) bu ro'yxatda EMAS (u — belgilanmagan_turlar)",
      all(teng(_bm20.get(k), v) for k, v in _kut20.items()) and not any("belgisiz tur" in (k or "") for k in _bm20)
      and "A117 D20 belgisiz tur" in ((_sp20 or {}).get("belgilanmagan_turlar") or [])
      and len(_b20) == 1 and (_b20[0].get("aniq") or {}).get("daromad", 0) + 0.005 >= sum(_bm20.values()),
      [_bm20, (_sp20 or {}).get("belgilanmagan_turlar") if isinstance(_sp20, dict) else _sp20,
       [(y.get("nom"), (y.get("aniq") or {}).get("daromad")) for y in _b20]])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Boshqa ko'rinishlar — bugun, grafik, PDF")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
d = SessionLocal()
try:
    o3 = Order(company_id=1, order_number="A117-3", project_id=ID["PRJ"], order_type=OrderType.PRODUCT,
               total_amount=500_000, agreed_amount=400_000, status=OrderStatus.READY, completed_at=datetime.utcnow())
    d.add(o3)
    d.flush()
    d.add(OrderItem(company_id=1, order_id=o3.id, name="A117 bugun profil", category="panel", width=50, thickness=2,
                    quantity=1, unit_price=250_000, total_price=250_000, penoplast_id=ID["PENO"]))
    d.add(OrderItem(company_id=1, order_id=o3.id, name="A117 bugun MRP", category="mrp_product", quantity=1,
                    unit_price=250_000, total_price=250_000, product_type_id=PT_M.get("id")))
    d.commit()
    TS = xavfsiz(services.get_today_stats, d, company_id=1)
    CH = xavfsiz(services.get_chart_data, d, company_id=1)
    REP_E = xavfsiz(services.get_monthly_report, d, YIL, OY, company_id=1)
finally:
    d.close()
_ty = {y.get("nom"): y.get("daromad") for y in (TS.get("today_yonalishlar") or [])} if isinstance(TS, dict) else {}
check("E1 bugungi daromad yo'nalishlar bo'yicha (kelishilgan 400 000 → 200 000 / 200 000); eski gips / penoplast kalitlari yo'q",
      _ty.get("Penoplast", 0) >= 200_000 and _ty.get("Metall", 0) >= 200_000 and "today_gips_revenue" not in TS
      and "today_penoplast_revenue" not in TS, [_ty, sorted(TS)[:20] if isinstance(TS, dict) else TS])
_oy = (CH.get("months") or [{}])[-1] if isinstance(CH, dict) else {}
_ynom = {y.get("kalit"): y.get("nom") for y in (CH.get("yonalishlar") or [])} if isinstance(CH, dict) else {}
check("E2 dashboard grafigi: yo'nalishlar ro'yxati (nomi bilan), oylik summalar kalit bo'yicha, ko'rinadiganlar soni; "
      "eski gips_revenue yo'q", _oy and "gips_revenue" not in _oy and isinstance(_oy.get("yonalishlar"), dict)
      and {_ynom.get(k) for k in _oy["yonalishlar"]} <= set(_ynom.values()) and "Metall" in _ynom.values()
      and CH.get("yonalishlar_soni") == 3, [_oy, _ynom, CH.get("yonalishlar_soni") if isinstance(CH, dict) else CH])
_rp = req(CA, "get", "/api/finance/split-profit-pdf", params={"year": YIL, "month": OY})
SAT = pdf_satrlar(_rp.content) if _rp.status_code == 200 and (_rp.content or b"").startswith(b"%PDF") else []
_mat = "\n".join(SAT)
check("E3 yo'nalishlar PDF: 200, sarlavha, yo'nalish nomlari, «Moliya hisobotidagi sof foyda», «Gips» so'zi yo'q, fayl nomi",
      _rp.status_code == 200 and "Yo'nalishlar bo'yicha sof foyda hisoboti" in _mat and "Metall" in _mat and "Penoplast" in _mat
      and "Moliya hisobotidagi sof foyda" in _mat and "Gips" not in _mat and "■" not in _mat
      and "yonalishlar_hisobot" in (_rp.headers.get("content-disposition") or ""), [_rp.status_code, SAT[:30]])
d = SessionLocal()
try:
    SPN = xavfsiz(services.calculate_split_profit_report, d, YIL, OY, company_id=1)
finally:
    d.close()
_sof_pdf = []
for i, q in enumerate(SAT):
    if q == "SOF FOYDA":
        _sof_pdf = [son(x) for x in SAT[i + 1:i + 1 + len(SPN.get("yonalishlar", [])) + 1]]
check("E4 PDF dagi SOF FOYDA qatori = hisobot (har ustun va JAMI)",
      isinstance(SPN, dict) and isinstance(SPN.get("yonalishlar"), list) and "jami" in SPN
      and _sof_pdf == [y["som"]["sof_foyda"] for y in SPN["yonalishlar"]] + [SPN["jami"]["sof_foyda"]],
      [_sof_pdf, [y["som"]["sof_foyda"] for y in SPN.get("yonalishlar", [])] if isinstance(SPN, dict) else SPN])
_rf = req(CA, "get", "/api/finance/report-pdf", params={"year": YIL, "month": OY})
FS = pdf_satrlar(_rf.content) if _rf.status_code == 200 and (_rf.content or b"").startswith(b"%PDF") else []


def _karta(yorliq):
    for i, q in enumerate(FS):
        if q == yorliq and i + 1 < len(FS):
            return son(FS[i + 1])
    return None


_D, _X, _S = _karta("JAMI DAROMAD"), _karta("JAMI XARAJAT"), _karta("SOF FOYDA")
_SOF_E = float(REP_E.get("sof_foyda", 0) or 0) if isinstance(REP_E, dict) else None
check("E5 Moliya PDF (G6-09): JAMI DAROMAD − JAMI XARAJAT = SOF FOYDA (butun so'm), SOF FOYDA = hisobot",
      None not in (_D, _X, _S, _SOF_E) and _D - _X == _S and _S == yaxlit(_SOF_E), [_D, _X, _S, _SOF_E])


def _jadval_qatorlari(bosh, oxir):
    try:
        i = FS.index(bosh)
        j = next(k for k in range(i, len(FS)) if FS[k] == oxir)
    except (ValueError, StopIteration):
        return [], None
    q, natija, k = FS[i + 1:j], [], 0
    while k < len(q):
        v = son(q[k + 1]) if k + 1 < len(q) else None
        if v is not None and q[k] not in ("Xarajat nomi", "Summa", "Daromad manbai"):
            natija.append((q[k], v))
            k += 2
        else:
            k += 1
    return natija, son(FS[j + 1]) if j + 1 < len(FS) else None


_xq, _xj = _jadval_qatorlari("Xarajatlar tafsiloti (nomma-nom)", "JAMI XARAJAT")
_dq, _dj = _jadval_qatorlari("Daromad tarkibi", "JAMI DAROMAD")
check("E6 Moliya PDF: xarajat qatorlari yig'indisi = JAMI XARAJAT; «Tayyor mahsulot sotuvi tannarxi» 150 000 qatori bor; "
      "daromad tarkibi (buyurtmalar + TM sotuvi 500 000) yig'indisi = JAMI DAROMAD",
      _xq and sum(v for _n, v in _xq) == _xj == _X and dict(_xq).get("Tayyor mahsulot sotuvi tannarxi") == 150_000
      and _dq and sum(v for _n, v in _dq) == _dj == _D and dict(_dq).get("Tayyor mahsulot sotuvi (buyurtmasiz)") == 500_000
      and "Hisob farqi (qatorlarda ko'rinmagan)" not in dict(_xq), [_xq, _xj, _dq, _dj])
check("E7 Moliya PDF: manfiy summa bir xil «−» bilan (oddiy «-» yo'q), sof foyda zarar bo'lsa ham to'g'ri o'qiladi",
      FS and not any(re.fullmatch(r"-\s?\d[\d ]* so'm", q) for q in FS) and (_S is not None), [q for q in FS if "so'm" in q][:12])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. Zaxira, tozalash, tiklash")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bt = tx(CB, amount=77_777.0, yonalish_id=BM.get("id"))
d = SessionLocal()
try:
    ZB = xavfsiz(crud.export_full_backup, d, company_id=2)
finally:
    d.close()
_zy = (ZB.get("tables", {}) or {}).get("yonalishlar") if isinstance(ZB, dict) else None
check("F1 B zaxirasida `yonalishlar` (faqat B niki: 2 ta) va xarajatning yonalish_id si",
      _bt[0] == 200 and isinstance(_zy, list) and sorted(y.get("nom") for y in _zy) == ["B Metall", "Penoplast"]
      and all(y.get("company_id") == 2 for y in _zy)
      and any(e.get("yonalish_id") == BM.get("id") for e in (ZB.get("tables", {}).get("expense_transactions") or [])),
      [_bt, _zy])
_tartib = [m.__name__ for m in xavfsiz(crud._reset_table_order)] if callable(getattr(crud, "_reset_table_order", None)) else []
check("F2 tozalash tartibida Yonalish — unga ishora qiluvchilardan (hodim, xarajat, transport, kirim, MRP turi) KEYIN",
      "Yonalish" in _tartib and all(_tartib.index(x) < _tartib.index("Yonalish") for x in
                                    ("Employee", "ExpenseTransaction", "TransportExpense", "InventoryReceipt", "ProductType")),
      _tartib)
d = SessionLocal()
try:
    _fr = xavfsiz(crud.factory_reset_all_data, d, company_id=2)
    _qoldi = d.query(Yonalish).filter(Yonalish.company_id == 2).count() if Yonalish else -1
    _a_qoldi = d.query(Yonalish).filter(Yonalish.company_id == 1).count() if Yonalish else -1
finally:
    d.close()
check("F3 B tozalash: B yo'nalishlari o'chdi (FK xatosiz), A niki joyida (4 ta: 3 ko'rinadigan + B13 dagi yashirin)",
      not (isinstance(_fr, dict) and "XATO" in _fr) and _qoldi == 0 and _a_qoldi == 4, [_fr, _qoldi, _a_qoldi])
d = SessionLocal()
try:
    _ti = xavfsiz(crud.import_full_backup, d, ZB, company_id=2)
    _yb = d.query(Yonalish).filter(Yonalish.company_id == 2).all() if Yonalish else []
    _eb = d.query(ExpenseTransaction).filter(ExpenseTransaction.company_id == 2, ExpenseTransaction.amount == 77_777).first()
    _yb_d = sorted((y.id, y.nom, y.kod) for y in _yb)
    _eb_y = getattr(_eb, "yonalish_id", None)
finally:
    d.close()
check("F4 B tiklash: yo'nalishlar AYNAN id bilan qaytdi, xarajat o'z yo'nalishiga bog'langan",
      not (isinstance(_ti, dict) and "XATO" in _ti) and _yb_d == sorted([(B_ASOSIY.get("id"), "Penoplast", "penoplast"),
                                                                       (BM.get("id"), "B Metall", None)])
      and _eb_y == BM.get("id"), [_ti if isinstance(_ti, dict) and "XATO" in _ti else "", _yb_d, _eb_y])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Xatolar va huquq")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_z = [req(CA, "get", "/api/finance/yonalishlar", params=p).status_code for p in
      ({"year": YIL, "month": 13}, {"year": YIL, "month": 0}, {"year": 1999, "month": 1}, {"year": YIL})]
_zp = req(CA, "get", "/api/finance/split-profit-pdf", params={"year": YIL, "month": 13}).status_code
_zn = req(CN, "get", "/api/finance/yonalishlar", params={"year": YIL, "month": OY}).status_code
_zw = req(CW, "get", "/api/finance/yonalishlar", params={"year": YIL, "month": OY}).status_code
_zn2 = req(CN, "get", "/api/yonalishlar").status_code
check("Z1 noto'g'ri oy / yil — 400 (oysiz — 422), PDF 13-oy — 400; kirmagan — 401; omborchi (moliya huquqisiz) — 403",
      _z == [400, 400, 400, 422] and _zp == 400 and _zn == 401 and _zw == 403 and _zn2 == 401, [_z, _zp, _zn, _zw, _zn2])

# Platformadan yaratilgan YANGI korxona — asosiy yo'nalish («Penoplast») korxona bilan birga (migratsiya kutilmaydi).
# Oxirida: yangi korxona id si C bo'limidagi qo'lda yaratilgan korxonalar bilan to'qnashmasin.
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "a117_plat", "Parol123!", UserRole.ADMIN, "A117 Platforma", company_id=1)
_pu = s.query(models.User).filter(models.User.username == "a117_plat").first()
if _pu is not None:
    _pu.is_platform_admin = True
    s.commit()
if PG_URL:
    # Korxonalar qo'lda id bilan yaratilgan (2, 3) — PG ketma-ketligi 1 da qolgan; platforma yaratishi uchun suriladi
    s.execute(text("SELECT setval(pg_get_serial_sequence('companies', 'id'), (SELECT MAX(id) FROM companies))"))
    s.commit()
s.close()
CP = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
req(CP, "post", "/login", data={"username": "a117_plat", "password": "Parol123!"}, follow_redirects=False)
_rk = req(CP, "post", "/api/platform/companies", data={"name": "A117 Yangi korxona", "admin_username": "a117_yangi"})
_yk = ((js(_rk) or {}).get("company") or {}).get("id")
s = SessionLocal()
try:
    _yk_yon = [(y.nom, y.kod, bool(y.yashirin)) for y in s.query(Yonalish).filter(Yonalish.company_id == _yk).all()] \
        if (Yonalish is not None and _yk) else None
finally:
    s.close()
check("Z2 platformadan yaratilgan yangi korxonada darhol BITTA yo'nalish — «Penoplast» (asosiy, ko'rinadigan)",
      _rk.status_code == 200 and _yk_yon == [("Penoplast", "penoplast", False)], [_rk.status_code, _rk.text[:200], _yk_yon])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
