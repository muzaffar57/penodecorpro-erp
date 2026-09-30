#!/usr/bin/env python3
"""
test_tannarx.py — kech118 ROLLAR 2-qism: «TANNARX VA FOYDA» RUXSATI (egasi QARORLARI 2026-09-30 18:4x, tugmali, QAYTA
SO'RALMAYDI: «Tannarx va foyda» ruxsati YO'Q rol — tannarx HAMMA joyda «—» (Menejer / Omborchi hozir ko'radigan «tan: …»,
tayyor mahsulot «Ombor qiymati», MRP «Taxminiy tannarx» ham); xomashyo XARID narxi (material narxi, kirim summasi, ta'minotchi
qarzi) tannarxga KIRMAYDI — «Xomashyo kirimi» ruxsati borlar ko'radi).

NIMA UCHUN KERAK
  Rollar 1-qismida «Tannarx va foyda» — faqat ba'zi sahifa bloklarining sharti edi: tayyor rol Menejer / Omborchi sahifada
  «tan: …», «Ombor qiymati», «Taxminiy tannarx» ni ko'rardi, API esa tannarx / foydani HAR KIMGA berardi (brauzer
  konsolida ko'rinardi). Endi: server javobni foydalanuvchiga ketishidan OLDIN tozalaydi (`ruxsatlar.tannarx_tozala`,
  `main._TannarxHimoyasi`), sahifalar null ni «—» qilib ko'rsatadi, PDF lar ham.
TALAB (har biri o'lchanadi):
  S  `tannarx_tozala`: umumiy kalitlar (har chuqurlikda; lug'at — hamma bargi), marshrut yo'llari (ro'yxat, filtrli ro'yxat
     `a[k=v1|v2].x`, regex), shartli qoida (narxsiz TM ombor qiymati), bool / boshqa maydonlar tegilmaydi;
  K  jadvaldagi har marshrut — haqiqiy API marshruti (yozuv xatosi jim o'tmaydi); himoya qatlami ulangan;
  A  HAQIQIY HTTP, har GET /api/... (fikstura id lari bilan): «Hammasi» (hamma ruxsat) va «Tannarxsiz» (xuddi shu, faqat
     «Tannarx va foyda»siz) — holat kodi bir xil (tannarx talab qiladiganlaridan tashqari); farq FAQAT null ga aylanish va
     faqat jadvaldagi joylarda; «Tannarxsiz» javobida birorta tannarx kaliti null emas qiymatga ega emas; Admin va Moliyachi
     (tayyor rol, tannarx bor) — tozalanmaydi (Hammasi bilan AYNAN); fikstura bo'yicha MAJBURIY yashirinlar ro'yxati —
     Hammasida son, Tannarxsizda null; xomashyo narxi va ta'minotchi qarzi — ko'rinadi (qaror 2);
  P  POST javoblari (sotish, brak, retsept oynasi, ishlab chiqarish rejasi) — tannarx / foyda null;
  F  PDF (oylik hisobot, yo'nalishlar): Tannarxsizda sof foyda / tannarx soni yo'q, «—» bor; Admin da — bor;
  H  sahifalar: `TANNARX_KORADI` bayrog'i to'g'ri, retsept sahifasida 1 kg tannarxi — «—», hamma sahifa 200;
     shablonlarda null → «—» belgilari joyida;
  M  himoya qatlami: JSON bo'lmagan javob / xato javobi / HTML tegilmaydi, o'zbekcha matn buzilmaydi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16.
ISHLATISH: python3 tools/test_tannarx.py
"""
import os
import re
import sys
import json
import zlib
import base64
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tannarx_test"
_T = tempfile.mkdtemp(prefix="tannarx_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'tannarx_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import copy                                        # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import ruxsatlar as RX                             # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, User, Rol, Inventory, FinishedProduct, StockSource, ProductionStatus,   # noqa: E402
                    Supplier)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from fastapi.routing import APIRoute               # noqa: E402

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


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def xavfsiz(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return e


# ── PDF matni (ReportLab: FlateDecode / ASCII85, ToUnicode) — test_yonalish_natija bilan bir usul ──
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


def som_matn(v):
    """finance_pdf._fmt_ishora bilan bir ko'rinish: −2 618 028 (U+2212). Son emas (masalan xato bilan yashirilgan) — «∅»."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return "∅"
    n = int(round(float(v)))
    return ("−" if n < 0 else "") + f"{abs(n):,}".replace(",", " ")


# ── Barglar: JSON → {yo'l: qiymat}; yo'l — "a.b[3].c" ──
def barglar(x, yol="", acc=None):
    acc = acc if acc is not None else {}
    if isinstance(x, dict):
        for k, v in x.items():
            barglar(v, f"{yol}.{k}" if yol else str(k), acc)
        if not x and yol:
            acc[yol] = {}
    elif isinstance(x, list):
        for i, v in enumerate(x):
            barglar(v, f"{yol}[{i}]", acc)
        if not x and yol:
            acc[yol] = []
    else:
        acc[yol] = x
    return acc


def umumiy(yol):
    return re.sub(r"\[\d+\]", "[]", yol)


def marshrutlar(routes):
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif type(r).__name__ == "_IncludedRouter":
            yield from marshrutlar(r.original_router.routes)


API = [r for r in marshrutlar(main.app.routes) if r.path.startswith("/api/")]
API_YOLLAR = {r.path for r in API}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. tannarx_tozala — qoidalar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
d = {"cost_price": 5, "name": "X", "ichki": {"profit": 1.5, "unit_price": 7, "tannarx": {"doim": 1, "qoplamali": 2}},
     "royxat": [{"sof_foyda": -3, "daromad": 9}, {"margin": 12.5}], "is_active": True, "foyda": True}
RX.tannarx_tozala(d, "/api/yoq/marshrut")
check("S1 umumiy kalit (yuqori daraja) — null", d["cost_price"] is None)
check("S2 umumiy kalit ichma-ich — null, qo'shni maydon tegilmaydi", d["ichki"]["profit"] is None and d["ichki"]["unit_price"] == 7)
check("S3 lug'at qiymatli umumiy kalit — hamma bargi null, kalitlar saqlanadi",
      d["ichki"]["tannarx"] == {"doim": None, "qoplamali": None}, d["ichki"]["tannarx"])
check("S4 ro'yxat ichidagi yozuvlar — null, boshqa maydon joyida",
      d["royxat"][0] == {"sof_foyda": None, "daromad": 9} and d["royxat"][1]["margin"] is None, d["royxat"])
check("S5 bool qiymat va oddiy matn tegilmaydi", d["is_active"] is True and d["foyda"] is True and d["name"] == "X")
y = {"yonalishlar": [{"som": {"jami_xarajat": 5, "xarajat_qismlari": {"brak": 1, "doimiy": 2}, "daromad": 3}}],
     "tarkib": [{"kalit": "brak", "summa": 5, "foiz": 1.0}, {"kalit": "hodimlar", "summa": 7, "foiz": 2.0},
                {"kalit": "tm_yoqotish", "summa": 1, "foiz": 0.5}],
     "oldingi": {"xarajat": 4, "daromad": 8}, "umumiy_xarajatlar": {"brak": 3, "transport": 5}}
RX.tannarx_tozala(y, "/api/finance/yonalishlar")
check("S6 marshrut yo'li (ro'yxat ichida) — null",
      y["yonalishlar"][0]["som"]["jami_xarajat"] is None and y["yonalishlar"][0]["som"]["daromad"] == 3)
check("S7 marshrut yo'li — xarajat qismlarida brak null, doimiy joyida",
      y["yonalishlar"][0]["som"]["xarajat_qismlari"] == {"brak": None, "doimiy": 2})
check("S8 filtrli ro'yxat `tarkib[kalit=brak|tm_yoqotish]` — faqat shu qatorlar null",
      [(t["kalit"], t["summa"], t["foiz"]) for t in y["tarkib"]] ==
      [("brak", None, None), ("hodimlar", 7, 2.0), ("tm_yoqotish", None, None)], y["tarkib"])
check("S9 oldingi davr xarajati (tannarx ichida) null, daromad joyida",
      y["oldingi"] == {"xarajat": None, "daromad": 8} and y["umumiy_xarajatlar"] == {"brak": None, "transport": 5})
tm = [{"unit_price": 0, "ombor_qiymati": 500, "cost_price": 500}, {"unit_price": 20, "ombor_qiymati": 200, "cost_price": 90}]
RX.tannarx_tozala(tm, "/api/finished")
check("S10 TM: narxsiz partiya ombor qiymati (tannarx) null, narxlisi (sotuv narxi) — ko'rinadi",
      tm[0]["ombor_qiymati"] is None and tm[1]["ombor_qiymati"] == 200 and tm[0]["cost_price"] is None, tm)
bt = {"brak_foizi": 1.5, "bosqichlar": [{"qiymat": 5, "ulush": 50}], "yozuvlar_qiymati": 7, "meyor_foiz": 5}
RX.tannarx_tozala(bt, "/api/reports/brak-tahlil")
check("S11 regex yo'l `*~qiymat` — har chuqurlikda, foizlar joyida",
      bt == {"brak_foizi": 1.5, "bosqichlar": [{"qiymat": None, "ulush": 50}], "yozuvlar_qiymati": None, "meyor_foiz": 5}, bt)
bp = {"doim": {"xomashyo": 1, "jami": 2}, "qatorlar": [{"narx": 5, "summa": 10}], "birlik": "dona"}
RX.tannarx_tozala(bp, "/api/production/boms/preview")
check("S12 retsept oynasi: 1 birlik tannarxi (lug'at) va qator summasi null, xomashyo narxi (qaror 2) ko'rinadi",
      bp == {"doim": {"xomashyo": None, "jami": None}, "qatorlar": [{"narx": 5, "summa": None}], "birlik": "dona"}, bp)
kp = {"success": True, "master_kpi": {"master": "U", "kpi_percent": 3.0, "foyda": 1000, "total_kpi": 30}}
RX.tannarx_tozala(kp, "/api/orders/{order_id}/ready")
check("S13 buyurtma «Tayyor»: usta KPI summasi (foyda × foiz) va foyda null, foiz / ism joyida",
      kp["master_kpi"] == {"master": "U", "kpi_percent": 3.0, "foyda": None, "total_kpi": None}, kp)
q = [1, "a", None, {"x": [2, {"profit": 3}]}]
check("S14 ro'yxat / aralash tur — xatosiz, faqat kalit tozalanadi",
      RX.tannarx_tozala(q, None) == [1, "a", None, {"x": [2, {"profit": None}]}])
_dt = {"detail": "Foyda 673 774 × 5% + qo'shimcha oylik 100 000", "ichki": [{"detail": "Sotuv 1 674 000 × 2%"}]}
RX.tannarx_tozala(_dt, "/api/finance/report")
check("S16 hodim oyligi izohi «Foyda N × p%» — summa «—» (qolgani joyida); boshqa izoh (sotuvdan foiz) tegilmaydi; Jinja filtri",
      _dt == {"detail": "Foyda — × 5% + qo'shimcha oylik 100 000", "ichki": [{"detail": "Sotuv 1 674 000 × 2%"}]}
      and main.templates.env.filters["foyda_yashir"]("Foyda -2 618 028 × 3.0%") == "Foyda — × 3.0%", _dt)
check("S15 xomashyo xarid narxi va ta'minotchi qarzi kalitlari — tannarx ro'yxatida EMAS (egasi qarori 2)",
      not ({"price_per_unit", "total_amount", "debt", "total_debt", "xomashyo_xaridi", "unit_price_at_time", "avg_price",
            "joriy_narx", "xarid_narxi", "narx"} & set(RX.TANNARX_KALITLAR)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Katalog va ulanish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_yoq = sorted(set(RX.TANNARX_YOLLAR) - API_YOLLAR) + sorted(set(RX.TANNARX_SHARTLI) - API_YOLLAR)
check("K1 TANNARX_YOLLAR / TANNARX_SHARTLI dagi har marshrut — haqiqiy API marshruti", not _yoq, _yoq)
check("K2 har yo'l yozuvi o'qiladi (bo'sh qism yo'q)",
      all(y and all(RX._yol_qismlari(y)) for ys in RX.TANNARX_YOLLAR.values() for y in ys))
_mw = [m.cls.__name__ for m in main.app.user_middleware]
check("K3 himoya qatlami (`_TannarxHimoyasi`) ilovaga ulangan", "_TannarxHimoyasi" in _mw, _mw)
check("K4 «Tannarx va foyda» katalogda (moliya bo'limida) va tayyor rollar: Admin / Moliyachi — bor, Menejer / Omborchi — yo'q",
      "tannarx" in RX.BANDLAR and "korish" in RX.TAYYOR_ROLLAR["admin"]["ruxsatlar"].get("tannarx", [])
      and "tannarx" in RX.TAYYOR_ROLLAR["moliyachi"]["ruxsatlar"]
      and "tannarx" not in RX.TAYYOR_ROLLAR["menejer"]["ruxsatlar"]
      and "tannarx" not in RX.TAYYOR_ROLLAR["omborchi"]["ruxsatlar"])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Fikstura: korxona 1 — foydalanuvchilar (Admin, «Hammasi», «Tannarxsiz», Moliyachi, Menejer, Omborchi), xomashyo,
# ta'minotchi, loy retsepti, MRP turi + retsept + ishlab chiqarish (yakunlangan va qoralama), tayyor mahsulotlar (narxli va
# narxsiz), sotuv, brak.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="TN B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "tn_admin", "Parol123!", UserRole.ADMIN, "TN Admin", company_id=1)
    auth.create_user(s, "tn_hammasi", "Parol123!", UserRole.MANAGER, "TN Hammasi", company_id=1)
    auth.create_user(s, "tn_tannarxsiz", "Parol123!", UserRole.MANAGER, "TN Tannarxsiz", company_id=1)
    auth.create_user(s, "tn_moliyachi", "Parol123!", UserRole.ACCOUNTANT, "TN Moliyachi", company_id=1)
    auth.create_user(s, "tn_menejer", "Parol123!", UserRole.MANAGER, "TN Menejer", company_id=1)
    auth.create_user(s, "tn_omborchi", "Parol123!", UserRole.WAREHOUSE, "TN Omborchi", company_id=1)
HAMMASI = {b: list(v["amallar"]) for b, v in RX.BANDLAR.items()}
TANNARXSIZ = {b: v for b, v in HAMMASI.items() if b != "tannarx"}
r_h = Rol(company_id=1, nom="TN Hammasi", kod=None, ruxsatlar=json.dumps(HAMMASI), tavsif="")
r_t = Rol(company_id=1, nom="TN Tannarxsiz", kod=None, ruxsatlar=json.dumps(TANNARXSIZ), tavsif="")
s.add_all([r_h, r_t])
s.flush()
s.query(User).filter(User.username == "tn_hammasi").first().rol_id = r_h.id
s.query(User).filter(User.username == "tn_tannarxsiz").first().rol_id = r_t.id
MAT = Inventory(company_id=1, item_name="TN Kley", unit="kg", stock_quantity=500, price_per_unit=1200, min_stock=0)
MAT2 = Inventory(company_id=1, item_name="TN Qum", unit="kg", stock_quantity=800, price_per_unit=300, min_stock=0)
SUP = Supplier(company_id=1, name="TN Ta'minotchi")
s.add_all([MAT, MAT2, SUP])
s.flush()
FP_NARXSIZ = FinishedProduct(company_id=1, name="TN Travertin partiya", category="dynamic_bom", quantity=10,
                             produced_quantity=10, unit="dona", unit_price=0, cost_price=51_000,
                             source=StockSource.PRODUCED, production_status=ProductionStatus.READY)
FP_NARXLI = FinishedProduct(company_id=1, name="TN Profil ʻOqʼ", category="profil", quantity=20, produced_quantity=20,
                            unit="metr", unit_price=30_000, cost_price=220_000, source=StockSource.PRODUCED,
                            production_status=ProductionStatus.READY)
s.add_all([FP_NARXSIZ, FP_NARXLI])
s.commit()
IDS = {"mat": MAT.id, "mat2": MAT2.id, "sup": SUP.id, "fp_narxsiz": FP_NARXSIZ.id, "fp_narxli": FP_NARXLI.id}
s.close()


def mijoz(u):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": u, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


CA, _sa = mijoz("tn_admin")
CH, _sh = mijoz("tn_hammasi")
CT, _st = mijoz("tn_tannarxsiz")
CF, _sf = mijoz("tn_moliyachi")
CM, _sm = mijoz("tn_menejer")
CW, _sw = mijoz("tn_omborchi")
if {_sa, _sh, _st, _sf, _sm, _sw} != {302}:
    print("LOGIN BO'LMADI", _sa, _sh, _st, _sf, _sm, _sw)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

# MRP: tur, retsept, qoralama va yakunlangan ishlab chiqarish (admin — API)
_pt = js(CA.post("/api/production/product-types", json={"name": "TN Travertin", "unit": "dona",
                                                         "input_template": "quantity_only",
                                                         "pricing_formula": "unit_based"})) or {}
PT_ID = _pt.get("id")
_bom = js(CA.post("/api/production/boms", json={
    "product_type_id": PT_ID, "variant_name": "Standart", "batch_quantity": 1,
    "items": [{"inventory_id": IDS["mat"], "quantity": 2.5, "fixed_cost_per_unit": 400},
              {"inventory_id": IDS["mat2"], "quantity": 4}]})) or {}
BOM_ID = _bom.get("id")
_po1 = js(CA.post("/api/production/orders", json={"product_type_id": PT_ID, "bom_id": BOM_ID, "quantity": 5,
                                                  "source_type": "warehouse_stock"})) or {}
PO_YAKUN = (_po1.get("production_order") or _po1).get("id") if isinstance(_po1, dict) else None
_st1 = CA.post(f"/api/production/orders/{PO_YAKUN}/start")
_co1 = CA.post(f"/api/production/orders/{PO_YAKUN}/complete")
_po2 = js(CA.post("/api/production/orders", json={"product_type_id": PT_ID, "bom_id": BOM_ID, "quantity": 3,
                                                  "source_type": "warehouse_stock"})) or {}
PO_QORALAMA = (_po2.get("production_order") or _po2).get("id") if isinstance(_po2, dict) else None
# Loy retsepti
_rec = js(CA.post("/api/recipes", json={"name": "TN Kvars", "batch_size_kg": 100,
                                        "ingredients": [{"inventory_id": IDS["mat"], "quantity_kg": 30},
                                                        {"inventory_id": IDS["mat2"], "quantity_kg": 70}]})) or {}
REC_ID = _rec.get("id")
# Sotuv (Hammasi) — javobda foyda / tannarx bor; Tannarxsiz — null (P bo'limi)
_sell_h = CH.post("/api/finished/sell", json={"finished_product_id": IDS["fp_narxli"], "quantity": 2, "unit_price": 30_000})
_sell_t = CT.post("/api/finished/sell", json={"finished_product_id": IDS["fp_narxli"], "quantity": 1, "unit_price": 30_000})
_loss_h = CH.post("/api/finished/loss", json={"finished_product_id": IDS["fp_narxli"], "quantity": 1, "reason": "TN sinov"})
_loss_t = CT.post("/api/finished/loss", json={"finished_product_id": IDS["fp_narxli"], "quantity": 1, "reason": "TN sinov"})
# «Foydadan foiz» hodim — oylik izohida foyda summasi (Moliya, Qarzdorlar)
_emp = CA.post("/api/employees", json={"name": "TN Foizchi", "pay_type": "percent_profit", "percent_value": 5})
check("F0b fikstura: «Foydadan foiz» hodim yaratildi", _emp.status_code in (200, 201), (_emp.status_code, _emp.text[:200]))
check("F0 fikstura: MRP turi, retsept, ishlab chiqarish (yakunlandi + qoralama), loy retsepti, sotuv, brak — yaratildi",
      all([PT_ID, BOM_ID, PO_YAKUN, PO_QORALAMA, REC_ID]) and _st1.status_code == 200 and _co1.status_code == 200
      and _sell_h.status_code == 200 and _sell_t.status_code == 200 and _loss_h.status_code == 200
      and _loss_t.status_code == 200,
      [PT_ID, BOM_ID, PO_YAKUN, PO_QORALAMA, REC_ID, _st1.status_code, _st1.text[:200], _co1.status_code, _co1.text[:200],
       _sell_h.status_code, _sell_h.text[:200], _loss_h.status_code, _loss_h.text[:200]])

BUGUN = tashkent_date()
ID = {"order_id": 999999, "project_id": 999999, "fp_id": IDS["fp_narxsiz"], "item_id": IDS["mat"],
      "supplier_id": IDS["sup"], "po_id": PO_QORALAMA, "pt_id": PT_ID, "master_id": 999999, "employee_id": 999999,
      "emp_id": 999999, "delivery_id": 999999, "sale_id": 999999, "group_id": "yoq", "receipt_id": 999999,
      "bom_id": BOM_ID, "recipe_id": REC_ID, "loss_id": 999999, "return_id": 999999, "payment_id": 999999}
SORAV = {"year": BUGUN.year, "month": BUGUN.month, "category": "arenda", "product_type_id": PT_ID, "bom_id": BOM_ID,
         "quantity": 4}
TASHQARI = ("/cron", "/system", "/platform", "/hodim/", "telegram", "pdf", "/export", "backup")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Har GET /api — «Hammasi» va «Tannarxsiz»")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def tannarx_talabi(r):
    """Marshrut qorovuli «Tannarx va foyda» ni talab qiladimi (ruxsat / ruxsat_hammasi — shu juft; ruxsat_biri — birortasi
    tannarxsiz bo'lmasa)."""
    for dep in r.dependant.dependencies:
        t = getattr(dep.call, "ruxsat_talabi", None)
        if t:
            tur, juftlar = t
            bor = [j for j in juftlar if j[0] == "tannarx"]
            if tur == "biri":
                return bool(bor) and len(bor) == len(juftlar)
            return bool(bor)
    return False


JAVOB = {}          # marshrut → (holat_hammasi, holat_tannarxsiz, json_h, json_t)
for r in API:
    if "GET" not in r.methods or any(x in r.path for x in TASHQARI):
        continue
    url = r.path
    for k, v in ID.items():
        url = url.replace("{" + k + "}", str(v))
    if "{" in url:
        continue
    q = {p.name: SORAV[p.name] for p in r.dependant.query_params if p.field_info.is_required() and p.name in SORAV}
    xh, xt = CH.get(url, params=q), CT.get(url, params=q)
    JAVOB[r.path] = (xh.status_code, xt.status_code,
                     js(xh) if "json" in xh.headers.get("content-type", "") else None,
                     js(xt) if "json" in xt.headers.get("content-type", "") else None, url, q)
_GET = [r.path for r in API if "GET" in r.methods and not any(x in r.path for x in TASHQARI)]
check("A0 HAMMA GET /api marshruti (cron / platforma / PDF dan tashqari) so'raldi va hech biri 500 emas",
      len(_GET) >= 90 and set(JAVOB) == set(_GET) and not [p for p, v in JAVOB.items() if v[0] >= 500 or v[1] >= 500],
      (len(JAVOB), len(_GET), sorted(set(_GET) - set(JAVOB)),
       [(p, v[0], v[1]) for p, v in JAVOB.items() if v[0] >= 500 or v[1] >= 500][:10]))

_holat_farq = []
for r in API:
    if r.path not in JAVOB:
        continue
    hh, ht = JAVOB[r.path][0], JAVOB[r.path][1]
    if tannarx_talabi(r):
        if not (ht == 403 and hh != 403):
            _holat_farq.append((r.path, hh, ht, "tannarx talab qilinadi — Tannarxsizga 403 kutilgan"))
    elif hh != ht:
        _holat_farq.append((r.path, hh, ht))
check("A1 holat kodi — «Tannarxsiz» da faqat «Tannarx va foyda» talab qiladigan marshrutlar 403, qolgani Hammasi bilan bir",
      not _holat_farq, _holat_farq)
check("A2 tannarx talab qiladigan marshrutlar bor (buyurtma / TM foyda hisobi) — so'raldi",
      any(tannarx_talabi(r) and r.path in JAVOB for r in API),
      [r.path for r in API if tannarx_talabi(r)])

_ruxsatsiz_farq, _qolgan_sir, _yashirildi = [], [], {}
for p, (hh, ht, jh, jt, _u, _q) in JAVOB.items():
    if hh != 200 or ht != 200 or jh is None or jt is None:
        continue
    bh, bt = barglar(jh), barglar(jt)
    kutilgan = barglar(RX.tannarx_tozala(copy.deepcopy(jh), p))
    if bt != kutilgan:
        _f = sorted(set(k for k in set(bt) | set(kutilgan) if bt.get(k, "∅") != kutilgan.get(k, "∅")))[:6]
        _ruxsatsiz_farq.append((p, [(k, bh.get(k), bt.get(k, "∅"), kutilgan.get(k, "∅")) for k in _f]))
    for k, v in bt.items():
        oxirgi = re.split(r"[.\[]", k)[-1] if k else k
        if oxirgi in RX.TANNARX_KALITLAR and v not in (None, {}, []) and not isinstance(v, bool):
            _qolgan_sir.append((p, k, v))
    for k, v in bh.items():
        if bt.get(k, "∅") is None and v is not None:
            _yashirildi.setdefault(p, set()).add(umumiy(k))
check("A3 «Tannarxsiz» javobi = «Hammasi» javobi + `tannarx_tozala` (boshqa hech qanday farq yo'q — ortiqcha ham, kam ham "
      "yashirilmagan)", not _ruxsatsiz_farq, _ruxsatsiz_farq[:5])
check("A4 «Tannarxsiz» javobida birorta tannarx / foyda kaliti null emas qiymat bilan qolmagan (har chuqurlikda)",
      not _qolgan_sir, _qolgan_sir[:10])

MAJBURIY = {
    "/api/finished": ["[].cost_price", "[].ombor_qiymati"],
    "/api/finished/stats": ["total_value", "produced_value", "narxsiz_tannarx_qiymati"],
    "/api/finished/sales": ["[].cost_amount"],
    "/api/production/orders": ["[].total_cost", "[].taxminiy_tannarx", "[].total_material_cost"],
    "/api/production/orders/{po_id}/preview": ["tannarx", "bir_birlik", "xomashyo", "qatorlar[].summa"],
    "/api/production/orders/preview": ["tannarx", "bir_birlik", "xomashyo", "qatorlar[].summa"],
    "/api/production/product-types/xulosa": ["[].retseptlar[].tannarx.doim"],
    "/api/loy-cost": ["cost_per_kg"],
    "/api/finance/report": ["tannarx_jami", "sof_foyda", "fp_sales_tannarx", "fp_loss_xarajat", "foyda_foiz",
                            "sof_foyda_tarkibi.tm_yoqotish", "xarajat_tarkibi[].summa", "fp_sales_foyda"],
    "/api/finance/history": ["[].sof_foyda", "[].tannarx_jami"],
    "/api/finance/yonalishlar": ["jami.tannarx", "jami.natija", "moliya_sof_foyda", "tarkib[].summa",
                                 "jami.xarajat_qismlari.tm_yoqotish"],
    "/api/dashboard/today": ["today_profit"],
    "/api/reports/forecast": ["current_foyda"],
}
_majburiy_xato = []
for p, yollar in MAJBURIY.items():
    for yol in yollar:
        if yol not in _yashirildi.get(p, set()):
            _majburiy_xato.append((p, yol, JAVOB.get(p, ("so'ralmadi",))[:2]))
check("A5 MAJBURIY yashirinlar (fikstura bo'yicha): Hammasida SON, Tannarxsizda null — tayyor mahsulot tannarxi / ombor "
      "qiymati, TM statistikasi, sotuv tannarxi, MRP taxminiy va yakuniy tannarx, reja, retseptlar tannarxi, loy 1 kg narxi, "
      "moliya (tannarx, sof foyda, TM yo'qotishi), yo'nalishlar natijasi, bugungi foyda, prognoz foydasi",
      not _majburiy_xato, _majburiy_xato)
_tm = next((t for t in (JAVOB.get("/api/finished") or (0, 0, None, None))[3] or [] if t.get("id") == IDS["fp_narxli"]), {})
check("A6 narxli tayyor mahsulot ombor qiymati (qoldiq × SOTUV narxi) va sotuv narxi — Tannarxsizga KO'RINADI",
      _tm.get("ombor_qiymati") not in (None, 0) and _tm.get("unit_price") == 30_000, _tm)
_inv = next((i for i in (JAVOB.get("/api/inventory") or (0, 0, None, None))[3] or [] if i.get("id") == IDS["mat"]), {})
check("A7 xomashyo narxi — Tannarxsizga KO'RINADI (egasi qarori 2: xarid narxi tannarxga kirmaydi)",
      float(_inv.get("price_per_unit") or 0) == 1200, _inv)
_rj = (JAVOB.get("/api/production/orders/{po_id}/preview") or (0, 0, None, {}))[3] or {}
check("A8 ishlab chiqarish rejasi: material narxi va miqdori ko'rinadi (qaror 2), faqat summa / tannarx yashirin",
      any(float(q.get("narx") or 0) > 0 and q.get("summa") is None for q in _rj.get("qatorlar") or []), _rj)

_teng, _teng_xato = 0, []
CA_J = {}
for p, (hh, ht, jh, jt, url, q) in JAVOB.items():
    if hh != 200 or jh is None:
        continue
    xa = CA.get(url, params=q)
    ja = js(xa) if "json" in xa.headers.get("content-type", "") else None
    CA_J[p] = ja
    if p in ("/api/me", "/api/auth/me", "/api/notifications", "/api/rollar", "/api/users", "/api/activity-logs",
             "/api/logs", "/api/dashboard/today-tasks"):
        continue
    if xa.status_code == 200 and ja is not None:
        if barglar(ja) == barglar(jh):
            _teng += 1
        else:
            _f = [k for k in set(barglar(ja)) | set(barglar(jh)) if barglar(ja).get(k, "∅") != barglar(jh).get(k, "∅")][:4]
            if any(re.split(r"[.\[]", k)[-1] in RX.TANNARX_KALITLAR or barglar(jh).get(k, "∅") is None for k in _f):
                _teng_xato.append((p, _f))
check("A9 Admin — tozalanmaydi (tannarx maydonlari «Hammasi» bilan AYNAN)", _teng > 50 and not _teng_xato,
      (_teng, _teng_xato[:5]))
_mol_xato = []
for p in ("/api/finance/report", "/api/finance/yonalishlar", "/api/finance/history", "/api/dashboard/today",
          "/api/reports/forecast"):
    hh, ht, jh, jt, url, q = JAVOB[p]
    xf = CF.get(url, params=q)
    if xf.status_code != 200 or barglar(js(xf)) != barglar(jh):
        _mol_xato.append((p, xf.status_code))
check("A10 Moliyachi (tayyor rol, «Tannarx va foyda» bor) — moliya javoblari tozalanmaydi (Hammasi bilan AYNAN)",
      not _mol_xato, _mol_xato)
_mx = []
for c, nom in ((CM, "Menejer"), (CW, "Omborchi")):
    for url in ("/api/finished", "/api/finished/stats", "/api/finished/sales"):
        j = js(c.get(url))
        if j is None:
            continue
        for k, v in barglar(j).items():
            if re.split(r"[.\[]", k)[-1] in RX.TANNARX_KALITLAR and v is not None:
                _mx.append((nom, url, k, v))
check("A11 tayyor rollar Menejer / Omborchi (tannarxsiz) — tayyor mahsulot javoblarida tannarx yo'q", not _mx, _mx[:6])
_om = js(CW.get(f"/api/production/orders/{PO_QORALAMA}/preview")) or {}
check("A12 Omborchi — ishlab chiqarish rejasida taxminiy tannarx / 1 birlik tannarxi yo'q (egasi: MRP «Taxminiy tannarx» ham)",
      _om.get("tannarx", 0) is None and _om.get("bir_birlik", 0) is None, _om)

_hb = lambda j: [b.get("detail") for b in ((j or {}).get("hodimlar_moslashuvchan_breakdown") or []) if b.get("name") == "TN Foizchi"]
_dh, _dtt = _hb(JAVOB["/api/finance/report"][2]), _hb(JAVOB["/api/finance/report"][3])
_ob = [e.get("detail") for e in ((JAVOB["/api/obligations/status"][3] or {}).get("employees") or [])]
_dtt = _dtt + [d for d in _ob if d != (_dtt[0] if _dtt else None)] if _ob else _dtt
check("A13 «Foydadan foiz» hodim izohi: Hammasida «Foyda <son> × 5%», Tannarxsizda «Foyda — × 5%»; qarzdorlik "
      "(`/api/obligations/status`) ham",
      _dh and re.match(r"^Foyda [-−]?\d[\d ]* × 5(\.0)?%$", _dh[0]) and len(_dtt) == 1
      and re.fullmatch(r"Foyda — × 5(\.0)?%", _dtt[0] or ""), (_dh, _dtt))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. POST javoblari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
jh, jt = js(_sell_h) or {}, js(_sell_t) or {}
_sot_h = [k for k in barglar(jh) if re.split(r"[.\[]", k)[-1] in ("profit", "cost_amount", "cost_price")]
check("P1 sotish — Hammasi javobida foyda / tannarx SON, Tannarxsizda o'sha maydonlar null",
      _sot_h and all(isinstance(barglar(jh)[k], (int, float)) for k in _sot_h)
      and all(barglar(jt).get(k, 0) is None for k in _sot_h), (_sot_h, jh, jt))
check("P2 sotish — sotuv summasi (sir emas) ikkalasida ham son",
      isinstance(jh.get("total_amount"), (int, float)) and isinstance(jt.get("total_amount"), (int, float)), (jh, jt))
lh, lt = js(_loss_h) or {}, js(_loss_t) or {}
check("P3 brak (TM yo'qotishi) — «Tan narxi» summasi Hammasida son, Tannarxsizda null",
      isinstance(lh.get("cost_amount"), (int, float)) and lh.get("cost_amount") > 0 and lt.get("cost_amount", 0) is None,
      (lh, lt))
_bp = {"product_type_id": PT_ID, "variant_name": "Sinov", "batch_quantity": 1,
       "items": [{"inventory_id": IDS["mat"], "quantity": 2}]}
bh, bt = js(CH.post("/api/production/boms/preview", json=_bp)) or {}, js(CT.post("/api/production/boms/preview", json=_bp)) or {}
check("P4 retsept oynasi (saqlanmagan retsept) — Hammasida 1 birlik tannarxi son, Tannarxsizda null; material narxi ikkalasida",
      isinstance((bh.get("doim") or {}).get("jami"), (int, float)) and (bt.get("doim") or {}).get("jami", 0) is None
      and (bt.get("hammasi") or {}).get("jami", 0) is None
      and float((bt.get("qatorlar") or [{}])[0].get("narx") or 0) == 1200 and (bt.get("qatorlar") or [{}])[0].get("summa", 0) is None,
      (bh, bt))
_xt = CT.get("/api/orders/999999/profit")
check("P5 buyurtma foyda hisobi (`/profit`) — Tannarxsizga 403", _xt.status_code == 403, _xt.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. PDF — oylik hisobot va yo'nalishlar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_rep = JAVOB["/api/finance/report"][2] or {}
_q = f"year={BUGUN.year}&month={BUGUN.month}"
pa = CA.get(f"/api/finance/report-pdf?{_q}")
pt_ = CT.get(f"/api/finance/report-pdf?{_q}")
sa, st = pdf_satrlar(pa.content), pdf_satrlar(pt_.content)
_sof, _tmt = som_matn(_rep["sof_foyda"]), som_matn(_rep["fp_sales_tannarx"])
check("F1 oylik hisobot PDF — ikkalasida 200 va matn o'qiladi", pa.status_code == 200 and pt_.status_code == 200
      and len(sa) > 20 and len(st) > 20, (pa.status_code, pt_.status_code, len(sa), len(st)))
check("F2 Admin PDF: sof foyda va TM sotuvi tannarxi summasi BOR",
      any(_sof in x for x in sa) and any(_tmt in x for x in sa), (_sof, _tmt, sa[:40]))
check("F3 Tannarxsiz PDF: sof foyda / TM sotuvi tannarxi summasi YO'Q, «—» bor, «so'm» siz",
      not any(_sof + " so'm" == x or x.startswith(_sof + " so'm") for x in st) and not any(_tmt + " so'm" == x for x in st)
      and "—" in st and "— so'm" not in st, (st[:60]))


def _keyingi(satrlar, yorliq):
    """`yorliq` qatoridan KEYINGI qator (kartadagi / jadvaldagi qiymat); yo'q bo'lsa None."""
    return next((satrlar[i + 1] for i, x in enumerate(satrlar[:-1]) if x == yorliq), None)


_KARTA = ("JAMI XARAJAT", "SOF FOYDA", "RENTABELLIK")
_QATOR = ("Ishlab chiqarish xarajati (xomashyo tan narxi)", "Tayyor mahsulot sotuvi tannarxi",
          "Tayyor mahsulot yo'qotishi (omborda)", "SOF FOYDA (barcha xarajat va brak ayirilgandan keyin)")
check("F7 Tannarxsiz PDF: kartalar (JAMI XARAJAT, SOF FOYDA, RENTABELLIK), tannarx / yo'qotish qatorlari va yakuniy SOF FOYDA — "
      "aynan «—» (0 ham, son ham emas); yakuniy rentabellik «— rentabellik»; Admin kartalarida — son",
      all(_keyingi(st, y) == "\u2014" for y in _KARTA + _QATOR) and "\u2014 rentabellik" in st
      and all(_keyingi(sa, y) not in (None, "\u2014") for y in _KARTA),
      ({y: _keyingi(st, y) for y in _KARTA + _QATOR}, {y: _keyingi(sa, y) for y in _KARTA}))
check("F4 Tannarxsiz PDF: daromad va boshqa xarajatlar summasi ko'rinadi",
      any(som_matn(_rep["daromad"]) in x for x in st), st[:30])
ya = CA.get(f"/api/finance/split-profit-pdf?{_q}")
yt = CT.get(f"/api/finance/split-profit-pdf?{_q}")
ysa, yst = pdf_satrlar(ya.content), pdf_satrlar(yt.content)
_nat = (JAVOB["/api/finance/yonalishlar"][2] or {}).get("jami", {}).get("natija")
_natm = ("+" if _nat and _nat > 0 else "") + som_matn(_nat or 0)
check("F5 yo'nalishlar PDF — ikkalasida 200; Admin da JAMI natija bor, Tannarxsizda — yo'q, «—» bor",
      ya.status_code == 200 and yt.status_code == 200 and any(_natm == x for x in ysa)
      and not any(_natm == x for x in yst) and "—" in yst, (_natm, ysa[:50], yst[:50]))
check("F6 yo'nalishlar PDF (Tannarxsiz) — «NATIJA» va «TANNARX» qatorlari bor (tuzilma saqlanadi), «— so'm» yo'q",
      any("NATIJA" in x for x in yst) and any("TANNARX" in x for x in yst) and not any("— so'm" in x for x in yst),
      yst[:60])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Sahifalar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
SAHIFALAR = ("/finished", "/production", "/recipes", "/finance", "/reports", "/dashboard", "/returns", "/kpi",
             "/projects", "/orders", "/inventory")
_sx = []
for sah in SAHIFALAR:
    a, t = CA.get(sah), CT.get(sah)
    if a.status_code != 200 or t.status_code != 200:
        _sx.append((sah, a.status_code, t.status_code))
    elif "const TANNARX_KORADI = true;" not in a.text or "const TANNARX_KORADI = false;" not in t.text:
        _sx.append((sah, "bayroq"))
check("H1 sahifalar 200; `TANNARX_KORADI` — Admin true, Tannarxsiz false", not _sx, _sx)
_rm = CM.get("/finished")
check("H2 Menejer (tayyor rol) — /finished da `TANNARX_KORADI = false`",
      _rm.status_code == 200 and "const TANNARX_KORADI = false;" in _rm.text, _rm.status_code)
_rp_a, _rp_t = CA.get("/recipes").text, CT.get("/recipes").text
_kg = js(CA.get(f"/api/loy-cost?recipe_id={REC_ID}")) or {}
_kgm = f"{float(_kg.get('cost_per_kg') or 0):,.0f}".replace(",", " ") + " so'm"
check("H3 Retseptlar: 1 kg tannarxi — Admin da son, Tannarxsizda «—» (son yo'q)",
      _kgm in _rp_a and _kgm not in _rp_t and 'class="rec-stat-val">—<' in _rp_t, (_kgm, _kg))
_da, _dt2 = CA.get("/debts"), CT.get("/debts")
_fa = re.findall(r"Foyda [^<]*?× 5(?:\.0)?%", _da.text)
_ft = re.findall(r"Foyda [^<]*?× 5(?:\.0)?%", _dt2.text)
check("H5 Qarzdorlar sahifasi (server chizadi): hodim izohi — Admin da foyda summasi bilan, Tannarxsizda «Foyda — × 5%»",
      _da.status_code == 200 and _dt2.status_code == 200 and _fa and all(re.match(r"Foyda [-−]?\d", x) for x in _fa)
      and _ft and all(re.fullmatch(r"Foyda — × 5(\.0)?%", x) for x in _ft), (_da.status_code, _dt2.status_code, _fa, _ft))
BELGILAR = {
    "templates/base.html": ["function somYoq(n, f)", "const TANNARX_KORADI ="],
    "templates/finished.html": ["tannarxKoradi ? `<div", "cpu === null ?", "s.total_value === null ? '—'",
                                "r.cost_amount === null ?"],
    "templates/production.html": ["po.total_cost === null ? null", "natija.qoplamali.jami === null"],
    "templates/dashboard.html": ["somYoq(t.today_profit, fmt)", "d.sof_foyda === null ? null"],
    "templates/finance.html": ["if (v === null) return '—';", "d.sof_foyda === null ? '—'", "u.s.natija === null"],
    "templates/reports.html": ["const qisqaSom =", "toliqSom(h.sof_foyda)", "toliqSom(i.cost_price)"],
    "templates/returns.html": ["somYoq(d.brak_xarajat, fmt)", "somYoq(x.qiymat, fmt)", "somYoq(it.value, fmt)"],
    "templates/kpi.html": ["m.yearly_profit === null ? '—'", "r.profit === null ? '—'"],
    "templates/projects.html": ["stats.total_profit === null ? '—'"],
    "templates/orders.html": ["result.master_kpi.total_kpi !== null"],
    "templates/recipes.html": ["current_user.ruxsat('tannarx', 'korish')"],
    "templates/debts.html": ["e.detail|foyda_yashir"],
}
_bx = []
for f, bb in BELGILAR.items():
    matn = open(os.path.join(ROOT, f), encoding="utf-8").read()
    _bx += [(f, b) for b in bb if b not in matn]
check("H4 shablonlarda null → «—» belgilari joyida (tayyor mahsulot, MRP, dashboard, moliya, hisobotlar, qaytarish, KPI, "
      "loyiha, buyurtma, retsept)", not _bx, _bx)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Himoya qatlami — tegilmaydigan javoblar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
x404 = CT.get("/api/production/orders/99999999/preview")
check("M1 xato javobi (4xx) tegilmaydi — `detail` joyida", x404.status_code in (404, 409) and "detail" in (js(x404) or {}),
      (x404.status_code, x404.text[:200]))
xh = CT.get("/finished")
check("M2 HTML sahifa tegilmaydi (JSON emas)", xh.status_code == 200 and xh.headers.get("content-type", "").startswith("text/html"))
_tmj = js(CT.get("/api/finished")) or []
_nom = next((t.get("name") for t in _tmj if t.get("id") == IDS["fp_narxli"]), "")
check("M3 o'zbekcha matn (ʻ ʼ) va Content-Length to'g'ri — javob qayta yozilganda buzilmaydi",
      _nom == "TN Profil ʻOqʼ", _nom)
_r = CT.get("/api/finished")
check("M4 Content-Length = haqiqiy tana uzunligi",
      int(_r.headers.get("content-length", -1)) == len(_r.content), (_r.headers.get("content-length"), len(_r.content)))
_pdf = CT.get(f"/api/finance/report-pdf?{_q}")
check("M5 PDF javobi (JSON emas) — himoya qatlami tegmaydi (content-type application/pdf)",
      _pdf.headers.get("content-type", "").startswith("application/pdf"))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f_ in FAILED:
        print("  -", f_)
sys.exit(1 if FAIL else 0)
