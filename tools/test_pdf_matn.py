#!/usr/bin/env python3
"""
test_pdf_matn.py — kech106, K106-3 va K106-4 darvozasi: PDF hujjatlardagi foydalanuvchi matni va korxona nomi.

NIMA UCHUN (zip 101 kodida O'LCHANGAN)
--------------------------------------
K106-3 (`work/probe106x.py`, `natija/k106/pdfx_asl/`): foydalanuvchi matni ReportLab `Paragraph` ga to'g'ridan-to'g'ri
berilardi — "<" + harf belgilash deb o'qilardi: mahsulot nomi "Karniz <A> 5<6", mijoz "Ali<Vali", izoh "<b>izoh" bo'lsa
nakladnoy, YUK XATI (mijozga Telegram'da boradi) va hisob-kitob varaqasi PDF lari 500 ("Parse error"); moliya PDF —
xarajat turkumi / izohida "x<y" bo'lsa 500.
K106-4 (`work/probe106b.py`, `natija/k106/probe106b_d108.txt`): yuk xati, TM sotuvi, hisob-kitob varaqasi, oylik moliya,
foyda ulushi PDF larining katta sarlavhasi QATTIQ "PENODECORPRO" edi — boshqa korxona ("Sinov Korxona C") hujjatida ham
bizning nom (2026-09-20 brend tuzatishidan qolgan; nakladnoy to'g'ri edi).

BO'LIMLAR (fikstura — 2-korxona "Ali & Vali <MChJ>": nomi, shiori, manzili, telefoni; mijoz, telefon, manzil, loyiha,
usta, mahsulot, buyurtma / yuk / sotuv izohlari, tashuvchi, xaridorlar, xarajat turkumi va izohi — HAMMASIDA "<" / "&")
  A — 7 PDF: 200 va har matn AYNAN (belgilash sifatida o'qilmagan)
  B — sarlavha: 2-korxonada korxona nomi (katta harf), "PENODECORPRO" YO'Q; 1-korxonada "PENODECORPRO" (o'zgarmagan)
  C — statik (AST): PDF modullarida "PENODECORPRO" matni yo'q; `Paragraph(...)` ning birinchi argumenti — o'zgarmas matn,
      `_x(…)`, yoki qiymatlari `_x(…)` / son formati / `_fmt` / `.strftime` / tizim qiymatlari (ro'yxat) bo'lgan f-satr;
      tashuvchi qismlari (`parts`) `_x` bilan; nazorat — sun'iy buzilishni TOPADI
PDF matni — kutubxonasiz (ASCII85 + Flate; TTF ToUnicode / Type1 WinAnsi).

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_pdf_matn.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_pdf_matn.py
"""
import os
import re
import ast
import sys
import zlib
import base64
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "pdf_matn_test"
_DB = os.path.join(tempfile.gettempdir(), "pdf_matn_test.db")

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
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime, timedelta           # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, Project, Inventory, Master, FinishedProduct, StockSource, ProductionStatus  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

for _n in ("_send_telegram", "_send_telegram_to", "_send_telegram_document", "_send_telegram_to_qoplamachi"):
    if hasattr(main, _n):
        setattr(main, _n, lambda *a, **k: False)

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
        print(f"  ✗ {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.content = b""

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


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except OSError:
        return ""


# ── PDF o'quvchi (kutubxonasiz; `tools/test_pdf_shrift.py` bilan bir xil usul) ──────────────────────────────────────
def _oqim(tana):
    lugat, _, qolgan = tana.partition(b"stream")
    data = qolgan[2:] if qolgan.startswith(b"\r\n") else qolgan[1:]
    m = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", lugat)
    data = data[:int(m.group(1))] if m else data[:data.rfind(b"endstream")].rstrip(b"\r\n")
    if b"ASCII85Decode" in lugat:
        # kech106: tugatuvchi "~>" FAQAT bir marta olinadi — ">" ASCII85 ning oddiy belgisi (29); ilgari `rstrip(b"~>")`
        # ma'lumotning oxirgi ">" ini ham o'chirib Flate ni buzardi (~1-2 % oqim — vaqt sayohatida tasodifiy yiqilish)
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


# PDF kontent tokenlari (kech106): satr `( … )` — BUTUN token, shuning uchun uning ichidagi "ET" / "BT" ("YETKAZISH",
# "(BT)") `BT … ET` blokini uzmaydi (ilgari `re.finditer(rb"BT(.*?)ET", …)` blokni satr ichida uzib, qatorni tashlardi).
_PDF_TOKEN = re.compile(rb"%[^\r\n]*|\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/\[\]()<>{}%]*|[^\s/\[\]()<>{}%]+", re.S)


def _bt_bloklar(data):
    """Kontent oqimidagi `BT … ET` bloklari — har biri tokenlar ro'yxati (satr tokeni qavslari bilan: `(…)`)."""
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
    """Har `BT … ET` bloki — bitta satr (Tj bo'laklari ORALIQSIZ qo'shiladi — "a<b" bitta so'z bo'lib qoladi)."""
    obyektlar = {int(n): tana for n, tana in re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", bayt, re.S)}
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


def _ixcham(s):
    return re.sub(r"\s+", "", s)


# ── fikstura ────────────────────────────────────────────────────────────────────────────────────────────────────
KN = "Ali & Vali <MChJ>"
MATN = {"slogan": "Eshik <va> deraza", "manzil": "Namangan & Chust", "tel": "+998 90 <3>",
        "mijoz": "Ali<Vali (Qo<qon)", "mijoz_tel": "+998 <90> 111", "mijoz_manzil": "Chust <markaz>",
        "loyiha": "Uy <2-qavat> & hovli", "usta": "Usmon <usta>", "detal": "Karniz <A> 5<6", "buyurtma_izoh": "Izoh <b>qalin",
        "tashuvchi": "Tashuvchi <T>", "yuk_izoh": "<b>izoh", "tm": "TM <x>", "xaridor": "Xaridor<1>", "sotuv_izoh": "<i>sotuv",
        "savat_xaridor": "Hamid <aka>", "savat_izoh": "savat <izoh>", "turkum": "a<b>c", "xarajat_izoh": "x<y"}

s = SessionLocal()
_c2 = Company(id=2, name=KN, slogan=MATN["slogan"], address=MATN["manzil"], phone=MATN["tel"])   # PG: aniq id (ketma-ketlik 1 da)
s.add(_c2)
s.commit()
CID = _c2.id
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "pm_admin", "Parol123!", UserRole.ADMIN, "PM admin", company_id=CID)
    auth.create_user(s, "pm1_admin", "Parol123!", UserRole.ADMIN, "PM1 admin", company_id=1)
PRJ = Project(company_id=CID, client_name=MATN["mijoz"], client_phone=MATN["mijoz_tel"], client_address=MATN["mijoz_manzil"],
              project_name=MATN["loyiha"], total_budget=0, total_paid=0)
PENO = Inventory(company_id=CID, item_name="PM Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
USTA = Master(company_id=CID, name=MATN["usta"], phone="+998900001074", kpi_percent=0)
TM = FinishedProduct(company_id=CID, name=MATN["tm"], quantity=50, unit="metr", source=StockSource.PRODUCED,
                     production_status=ProductionStatus.READY, unit_price=10_000, cost_price=5_000)
PRJ1 = Project(company_id=1, client_name="PM1 mijoz", project_name="PM1 loyiha", total_budget=0, total_paid=0)
PENO1 = Inventory(company_id=1, item_name="PM1 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                  volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
s.add_all([PRJ, PENO, USTA, TM, PRJ1, PENO1])
s.commit()
ID = {"PRJ": PRJ.id, "PENO": PENO.id, "USTA": USTA.id, "TM": TM.id, "PRJ1": PRJ1.id, "PENO1": PENO1.id}
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    return c if r.status_code == 302 else None


C = mijoz("pm_admin")
C1 = mijoz("pm1_admin")
if C is None or C1 is None:
    print("LOGIN BO'LMADI")
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)


def buyurtma(c, prj, peno, nom, izoh=None, usta=None):
    tana = {"project_id": prj, "order_type": "product", "notes": izoh,
            "items": [{"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 1,
                       "unit_price": 1_000_000, "is_coated": False, "penoplast_id": peno}]}
    if usta:
        tana["master_id"] = usta
    r = req(c, "post", "/api/orders", params={"confirm_shortage": "true"}, json=tana)
    oid = (js(r) or {}).get("id") if r.status_code == 200 else None
    s_ = SessionLocal()
    try:
        it = s_.execute(text("SELECT id FROM order_items WHERE order_id = :o"), {"o": oid or 0}).scalar()
    finally:
        s_.close()
    return oid, it


ID["O"], ID["IT"] = buyurtma(C, ID["PRJ"], ID["PENO"], MATN["detal"], MATN["buyurtma_izoh"], ID["USTA"])
_rd = req(C, "post", "/api/deliveries", json={"order_id": ID["O"], "items": [{"order_item_id": ID["IT"], "quantity": 4}],
                                              "notes": MATN["yuk_izoh"], "transport_carrier": MATN["tashuvchi"],
                                              "transport_cost": 50_000, "transport_payer": "client", "payment_method": "naqd",
                                              "payment_amount": 0})
ID["D"] = (js(_rd) or {}).get("delivery_id") if isinstance(js(_rd), dict) else None
_rs = req(C, "post", "/api/finished/sell", json={"finished_product_id": ID["TM"], "quantity": 1, "unit_price": 10_000,
                                                 "buyer_name": MATN["xaridor"], "notes": MATN["sotuv_izoh"]})
ID["S"] = (js(_rs) or {}).get("sale_id") if isinstance(js(_rs), dict) else None
_rg = req(C, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": ID["TM"], "quantity": 1, "unit_price": 10_000}],
                                                       "buyer_name": MATN["savat_xaridor"], "notes": MATN["savat_izoh"]})
ID["G"] = (js(_rg) or {}).get("sale_group_id") if isinstance(js(_rg), dict) else None
_rx = req(C, "post", "/api/finance/transactions", json={"category": MATN["turkum"], "amount": 15_000.0, "notes": MATN["xarajat_izoh"]})
_rb = req(C, "post", "/api/finance/transactions", json={"category": "boshqa", "amount": 5_000.0, "notes": MATN["xarajat_izoh"]})
ID["O1"], ID["IT1"] = buyurtma(C1, ID["PRJ1"], ID["PENO1"], "PM1 detal")
_rd1 = req(C1, "post", "/api/deliveries", json={"order_id": ID["O1"], "items": [{"order_item_id": ID["IT1"], "quantity": 2}],
                                                "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd",
                                                "payment_amount": 0})
ID["D1"] = (js(_rd1) or {}).get("delivery_id") if isinstance(js(_rd1), dict) else None
_tk = datetime.utcnow() + timedelta(hours=5)

section("0. Tayyorgarlik")
check("0.1 fikstura: 2-korxona, buyurtma (izoh), yuk xati (tashuvchi, izoh), TM sotuvi yakka / guruh, xarajatlar; 1-korxona yuk xati",
      all(ID.get(k) for k in ("O", "IT", "D", "S", "G", "O1", "D1")) and _rx.status_code == 200 and _rb.status_code == 200,
      [ID, _rx.status_code, _rb.status_code, _rd.text[:160] if not ID.get("D") else ""])

PDFLAR = [
    ("nakladnoy", f"/api/orders/{ID['O']}/pdf", {}, ["mijoz", "mijoz_tel", "mijoz_manzil", "loyiha", "usta", "detal",
                                                     "buyurtma_izoh"]),
    ("yuk_xati", f"/api/deliveries/{ID['D']}/pdf", {}, ["mijoz", "loyiha", "detal", "tashuvchi", "yuk_izoh"]),
    ("hisob_kitob", f"/api/orders/{ID['O']}/summary-pdf", {}, ["mijoz", "loyiha", "detal"]),
    ("tm_yakka", f"/api/finished/sales/{ID['S']}/pdf", {}, ["tm", "xaridor", "sotuv_izoh"]),
    ("tm_guruh", f"/api/finished/sales/batch/{ID['G']}/pdf", {}, ["tm", "savat_xaridor", "savat_izoh"]),
    ("moliya_oylik", "/api/finance/report-pdf", {"year": _tk.year, "month": _tk.month}, ["turkum"]),
    ("foyda_ulushi", "/api/finance/split-profit-pdf", {"year": _tk.year, "month": _tk.month}, []),
]
SATR = {}
for _nom, _url, _par, _ in PDFLAR:
    _r = req(C, "get", _url, params=_par)
    try:
        SATR[_nom] = (_r.status_code, pdf_satrlar(_r.content) if _r.status_code == 200 else [])
    except Exception as e:                 # noqa: BLE001
        SATR[_nom] = (_r.status_code, [f"{type(e).__name__}: {e}"])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Foydalanuvchi matni \"<\" / \"&\" bilan — PDF chiqadi, matn AYNAN")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
for _i, (_nom, _url, _par, _kalit) in enumerate(PDFLAR, 1):
    _st, _sl = SATR[_nom]
    _ix = _ixcham("\n".join(_sl))
    _yoq = [MATN[k] for k in _kalit if _ixcham(MATN[k]) not in _ix]
    check(f"A{_i} {_nom}: 200" + (f", matnda AYNAN: {', '.join(MATN[k] for k in _kalit[:4])}{'…' if len(_kalit) > 4 else ''}"
                                   if _kalit else ""),
          _st == 200 and not _yoq, [_st, "yo'q: " + repr(_yoq), _sl[:3]])
_mo = _ixcham("\n".join(SATR["moliya_oylik"][1]))
check("A8 moliya: xarajat izohi \"x<y\" (Boshqa — x<y) AYNAN", _ixcham("Boshqa — x<y") in _mo, [q for q in SATR["moliya_oylik"][1] if "x" in q][:4])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Katta sarlavha — korxona nomi (K106-4)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_kutilgan = KN.upper()
_bosh = {n: (SATR[n][1][:1] or ["?"])[0] for n in ("yuk_xati", "hisob_kitob", "tm_yakka", "tm_guruh", "moliya_oylik", "foyda_ulushi")}
check(f"B1 2-korxona: 6 PDF sarlavhasi \"{_kutilgan}\" (ilgari \"PENODECORPRO\")",
      all(_ixcham(v) == _ixcham(_kutilgan) for v in _bosh.values()), _bosh)
check("B2 2-korxona: 7 PDF ning HECH birida \"PENODECORPRO\" yo'q",
      not [n for n, (_, sl) in SATR.items() if "PENODECORPRO" in _ixcham("\n".join(sl)).upper()],
      [n for n, (_, sl) in SATR.items() if "PENODECORPRO" in _ixcham("\n".join(sl)).upper()])
check("B3 2-korxona: shior / manzil / telefon (\"<\", \"&\" bilan) AYNAN — yuk xati sarlavha ostida",
      all(_ixcham(MATN[k]) in _ixcham("\n".join(SATR["yuk_xati"][1][:3])) for k in ("slogan", "manzil", "tel")), SATR["yuk_xati"][1][:3])
_r1 = req(C1, "get", f"/api/deliveries/{ID['D1']}/pdf")
try:
    _s1 = pdf_satrlar(_r1.content) if _r1.status_code == 200 else []
except Exception as e:                     # noqa: BLE001
    _s1 = [f"{type(e).__name__}: {e}"]
_ism1 = None
s = SessionLocal()
try:
    _ism1 = s.execute(text("SELECT name FROM companies WHERE id = 1")).scalar()
finally:
    s.close()
check("B4 1-korxona yuk xati: sarlavha = o'z nomi katta harf bilan (\"PENODECORPRO\" — o'zgarmagan)",
      _r1.status_code == 200 and _s1 and _ixcham(_s1[0]) == _ixcham((_ism1 or "").upper()), [_r1.status_code, _s1[:1], _ism1])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Statik (AST)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
PDF_MODULLAR = ["pdf_service.py", "delivery_pdf.py", "finance_pdf.py"]


def _qattiq_nom(m):
    """Kod satrlarida (izohlar emas) "PENODECORPRO"."""
    try:
        return [t.lineno for t in ast.walk(ast.parse(fayl(m)))
                if isinstance(t, ast.Constant) and isinstance(t.value, str) and "PENODECORPRO" in t.value]
    except SyntaxError as e:
        return [f"SyntaxError: {e}"]


check("C1 PDF modullari kodida \"PENODECORPRO\" satri yo'q (sarlavha — korxona nomi; izohlar hisobga olinmaydi)",
      not any(_qattiq_nom(m) for m in PDF_MODULLAR), {m: _qattiq_nom(m) for m in PDF_MODULLAR if _qattiq_nom(m)})
# Tizim qiymatlari (foydalanuvchi matni EMAS): raqamlar, holat / tur yorliqlari, oy nomi, hujjat raqami.
TIZIM = {
    "pdf_service.py": {'_tashkent_vaqt(order.created_at).strftime("%d.%m.%Y") if order.created_at else "—"', "order.order_number",
                       "order_type", "status_txt", "str(i+1)"},
    "delivery_pdf.py": {'"<b>Transport:</b> " + "  ·  ".join(parts)', "{delivery.delivery_number}", "{group_id}",
                        "{order.order_number}", "{pct}", "{sale.id}", "{status_txt}"},
    # kech117 (A2): `_uu` — yo'nalishlar PDF ida umumiy xarajat bo'linish usuli: o'zgarmas matn yoki `_x(nom)` + foiz
    # (eski «Gips vs Penoplast» PDF i va uning `gips_foiz` / `penoplast_foiz` qiymatlari olib tashlandi)
    "finance_pdf.py": {"count_label", "label", "r[0]", "r[1]", "title", "{MONTH_NAMES[month]}", "{data['foyda_foiz']}",
                       "{foyda_foiz}", "{net_sign}", "{year}", "{_uu}",
                       # kech117 (G6-09): son ko'rinishlari — ayiriladigan / ishorali summa, rentabellik foizi, «+» belgisi
                       "_ayir(v) if ishora else _fmt_ishora(v)", "{f}", "{'+' if _yaxlit_butun(net) > 0 else ''}",
                       # kech118 (yo'nalishlar natijasi — egasi QARORI 15:23): «—» (faqat Jami qatori) / ayiriladigan
                       # summa, natija «+N» / «−N» — faqat son
                       '"\\u2014" if v is None else (_ayir(v) if ayir else _fmt_ishora(v))', "_fmt_natija(v)"},
}


def buzilishlar(src, tizim):
    """`Paragraph(birinchi, …)` — o'zgarmas matn, `_x(…)` yoki xavfsiz f-satr bo'lmagan joylar."""
    out = []
    try:
        daraxt = ast.parse(src)
    except SyntaxError as e:
        return [f"SyntaxError: {e}"]
    for t in ast.walk(daraxt):
        if not (isinstance(t, ast.Call) and getattr(t.func, "id", None) == "Paragraph" and t.args):
            continue
        a0 = t.args[0]
        if isinstance(a0, ast.Constant) or (isinstance(a0, ast.Call) and getattr(a0.func, "id", None) == "_x"):
            continue
        if isinstance(a0, ast.JoinedStr):
            for v in a0.values:
                if not isinstance(v, ast.FormattedValue) or v.format_spec is not None:
                    continue
                e = v.value
                # kech117: `_fmt_ishora` — faqat son (ishora + raqamlar), `_fmt` kabi
                # kech118: `_fmt_natija` / `_foiz_uz` / `_ozgarish_matni` — faqat son (ishora, raqam, vergul, «%»)
                # kech118 (ROLLAR 2-qism): `_som` — son ko'rinishi (`_fmt` / `_fmt_ishora` / `_fmt_natija`) + « so'm» yoki «—»
                # kech120 (zip 136 — G6-12, MOSLANDI): `_pul_matni` (pdf_service) — faqat son (raqam va bo'shliq)
                if isinstance(e, ast.Call) and (getattr(e.func, "id", None) in ("_x", "_fmt", "_num", "len", "_fmt_ishora",
                                                                                "_fmt_natija", "_foiz_uz", "_ozgarish_matni",
                                                                                "_som", "_pul_matni")
                                                or getattr(e.func, "attr", None) == "strftime"):
                    continue
                q = "{" + ast.get_source_segment(src, e) + "}"
                if q not in tizim:
                    out.append(f"{t.lineno}: {q}")
            continue
        q = ast.get_source_segment(src, a0)
        if q not in tizim:
            out.append(f"{t.lineno}: {q[:80]}")
    return out


_c2b = {m: buzilishlar(fayl(m), TIZIM[m]) for m in PDF_MODULLAR}
check("C2 PDF modullari: `Paragraph` ga foydalanuvchi matni faqat `_x(…)` orqali (qolgani — o'zgarmas / son / sana / tizim ro'yxati)",
      not any(_c2b.values()), {m: v[:6] for m, v in _c2b.items() if v})
_parts = re.findall(r"parts\.append\((f?\"[^\n]*)\)", fayl("delivery_pdf.py"))
check("C3 delivery_pdf: tashuvchi qismlari (`parts`) — foydalanuvchi qiymati `_x(…)` bilan",
      _parts and all("{" not in p or re.fullmatch(r"f\"(?:[^{]|\{(?:_x|_fmt)\([^}]*\)\})*\"", p) for p in _parts), _parts)
_naz = buzilishlar('Paragraph("A", s)\nParagraph(_x(o.name), s)\nParagraph(f"{o.name}", s)\nParagraph(client, s)\n'
                   'Paragraph(f"{x:,.0f} {_fmt(y)} {d.strftime(\'%d\')}", s)\n', set())
check("C4 nazorat: AST tekshiruvi `f\"{o.name}\"` va `Paragraph(client)` ni TOPADI, o'zgarmas / `_x` / son formatini topmaydi",
      _naz == ["3: {o.name}", "4: client"], _naz)


def _nazorat_pdf():
    """Sun'iy PDF (Type1 shrift, ASCII85 + Flate kontent oqimi): ASCII85 matni tugatuvchi "~>" dan OLDIN ">" bilan tugaydi
    (">" — ASCII85 ning oddiy belgisi; `rstrip(b"~>")` uni ham o'chirib Flate ni buzardi — ~1-2 % oqim, vaqt sayohatida
    tasodifiy yiqilish, kech106); birinchi satr ichida "ET" / "BT" bor ("QISMAN YETKAZISH (BT) ET")."""
    for i in range(5000):
        kontent = ("BT /F1 12 Tf 72 700 Td (QISMAN YETKAZISH \\(BT\\) ET) Tj ET\n"
                   f"BT /F1 12 Tf 72 680 Td (nazorat {i}) Tj ET\n").encode("latin-1")
        kod = base64.a85encode(zlib.compress(kontent))
        if kod.endswith(b">"):
            break
    oqim = kod + b"~>"
    return (b"%PDF-1.4\n1 0 obj\n<< /BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font >>\n"
            b"endobj\n2 0 obj\n<< /Filter [ /ASCII85Decode /FlateDecode ] /Length " + str(len(oqim)).encode() + b" >>\nstream\n"
            + oqim + b"\nendstream\nendobj\n%%EOF\n"), i


try:
    _npdf, _ni = _nazorat_pdf()
    _n = pdf_satrlar(_npdf)
except Exception as e:                     # noqa: BLE001
    _ni, _n = -1, [f"{type(e).__name__}: {e}"]
check("C5 nazorat: PDF o'quvchi — ASCII85 oqimi \">\" bilan tugasa ham o'qiladi (tugatuvchi \"~>\" faqat bir marta olinadi), satr ichidagi \"ET\" / \"BT\" (\"YETKAZISH\") BT … ET blokini uzmaydi",
      _n == ["QISMAN YETKAZISH (BT) ET", f"nazorat {_ni}"], [_ni, _n])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
