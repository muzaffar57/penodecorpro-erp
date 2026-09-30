#!/usr/bin/env python3
"""
test_pdf_shrift.py — kech106, K106-1 darvozasi: PDF hujjatlarda shriftda YO'Q belgi (QORA KVADRAT ■) chiqmasin.

NIMA UCHUN (zip 101 kodida O'LCHANGAN — `work/probe106f.py`, HAQIQIY chizish `pdftoppm`, `natija/k106/pdf_asl/`)
---------------------------------------------------------------------------------------------------------------
ReportLab standart shrifti Helvetica (Type1, WinAnsi / cp1252) da Kirill harflari (o'zbek: қ ғ ў ҳ ham), "№" va emoji
yo'q — ReportLab ularni ZapfDingbats "■" (qora kvadrat) bilan almashtirardi. 7 PDF ning HAMMASIDA: yuk xati (mijozga
Telegram'da boradi) sarlavhasi "YUK XATI (NAKLADNOY) ■ ORD-001-1/Y-1", jadval ustuni "■", Kirill yozilgan mijoz /
loyiha / mahsulot nomi — butunlay "■■■■■■ ■■■■■", "■■ QISMAN YETKAZISH", "■ Transport", moliya hisobotida "■ Arenda";
Kirill ma'lumotli sinov fiksturasida jami 233 ta ■.

TUZATISH (`pdf_shrift.py`): Liberation Sans 2.1.5 (`fonts/`, SIL OFL 1.1) — Helvetica metrikasi bilan BIR XIL — standart
'Helvetica' / '-Bold' / '-Oblique' / '-BoldOblique' NOMLARI bilan ro'yxatga olinadi (PDF kodi o'zgarmaydi); shriftda yo'q
belgi (ma'lumotdagi emoji) chizilmaydi; kod matnlaridagi emoji olib tashlangan.

BO'LIMLAR
  A — shrift: fayllar va litsenziya, 4 nom → Liberation TTF, `<b>` / `<i>` oilasi, metrika = Helvetica (AFM),
      Type1 Helvetica AVVAL ishlatilgan jarayonda ham almashadi (alohida jarayon), takroriy ulash zararsiz
  B — 7 PDF (Kirill fikstura: mijoz, loyiha, usta, mahsulot "№" bilan, TM, xaridor, izoh; qisman yetkazish, transport,
      to'lov, chegirma, xarajatlar): Type1 / ZapfDingbats / Symbol shrifti YO'Q, ■ YO'Q, Kirill nomlar va "№" matnda
  C — ma'lumotdagi emoji (TM nomi) — PDF chiqadi, belgi tashlab yuboriladi (bo'sh kvadrat emas), qolgan matn joyida
  D — statik: 3 PDF moduli shriftni ulaydi; kod matnlarida shriftda yo'q belgi yo'q; ReportLab faqat shu modullarda;
      `requirements.txt` — reportlab 4.2.x (ro'yxatga olish shu versiyaga moslangan)
  E — nazorat: PDF o'quvchi Type1 / ZapfDingbats kvadratini TOPADI (tekshiruv bo'sh emas)
PDF matni — kutubxonasiz (ASCII85 + Flate oqimlari; TTF — `ToUnicode` CMap orqali; Type1 — WinAnsi).

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_pdf_shrift.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_pdf_shrift.py
"""
import os
import re
import ast
import sys
import zlib
import base64
import tempfile
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "pdf_shrift_test"
_DB = os.path.join(tempfile.gettempdir(), "pdf_shrift_test.db")

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

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import pdf_service, delivery_pdf, finance_pdf  # noqa: E402 — yuklanishi shriftni ulaydi (D bo'limida nomlari)
try:
    import pdf_shrift                              # noqa: E402
except Exception:                                  # noqa: BLE001 — asl kodda modul yo'q: test yiqiladi, QULAMAYDI
    pdf_shrift = None
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Project, Inventory, Master, FinishedProduct, StockSource, ProductionStatus  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from reportlab.pdfbase import pdfmetrics           # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont       # noqa: E402

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


# ── PDF o'quvchi (kutubxonasiz) ─────────────────────────────────────────────────────────────────────────────────
KVADRAT = "■"
_WINANSI = {0x80: "€", 0x82: "‚", 0x83: "ƒ", 0x84: "„", 0x85: "…", 0x86: "†", 0x87: "‡", 0x88: "ˆ", 0x89: "‰", 0x8A: "Š",
            0x8B: "‹", 0x8C: "Œ", 0x8E: "Ž", 0x91: "‘", 0x92: "’", 0x93: "“", 0x94: "”", 0x95: "•", 0x96: "–", 0x97: "—",
            0x98: "˜", 0x99: "™", 0x9A: "š", 0x9B: "›", 0x9C: "œ", 0x9E: "ž", 0x9F: "Ÿ"}


def _oqim(tana):
    """Obyekt oqimi: `/Length` bo'yicha kesiladi (Flate ikkilik ma'lumoti bo'shliq / qator belgisi bilan tugashi mumkin)."""
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
    """PDF satri `( … )` ichidagi qochirishlar."""
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


def pdf_oqi(bayt):
    """→ {"matn": …, "shriftlar": [BaseFont…], "type1": [...]}. TTF — ToUnicode orqali (kod 0 / .notdef → ■),
    Type1 — WinAnsi (ZapfDingbats → ■, Symbol → ?)."""
    obyektlar = {int(n): tana for n, tana in re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", bayt, re.S)}
    shriftlar = {}
    for n, tana in obyektlar.items():
        if b"/Type /Font" not in tana or b"/BaseFont" not in tana:
            continue
        nom = re.search(rb"/Name\s*/([^\s/>\[]+)", tana)
        base = re.search(rb"/BaseFont\s*/([^\s/>\[]+)", tana).group(1).decode()
        cmap = None
        tu = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", tana)
        if tu and int(tu.group(1)) in obyektlar:
            _, cm = _oqim(obyektlar[int(tu.group(1))])
            cmap = {}
            for blok in re.findall(rb"beginbfchar(.*?)endbfchar", cm, re.S):
                for k, v in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blok):
                    cmap[int(k, 16)] = bytes.fromhex(v.decode()).decode("utf-16-be")
            for blok in re.findall(rb"beginbfrange(.*?)endbfrange", cm, re.S):
                for a, b, v in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blok):
                    bosh = int(v, 16)
                    for k in range(int(a, 16), int(b, 16) + 1):
                        cmap[k] = chr(bosh + k - int(a, 16))
        if nom:
            shriftlar[nom.group(1).decode()] = (base, cmap)
    matn = []
    for n, tana in obyektlar.items():
        if b"stream" not in tana or b"/Type /Font" in tana:
            continue
        try:
            _, data = _oqim(tana)
        except Exception:                  # noqa: BLE001 — rasm / shrift fayli oqimlari
            continue
        if b" Tf" not in data:
            continue
        joriy = (None, None)
        for m in re.finditer(rb"/([^\s/]+)\s+[\d.]+\s+Tf|\(((?:\\.|[^\\)])*)\)\s*Tj|\bET\b|\bT\*|\bTd\b", data, re.S):
            if m.group(1) is not None:
                joriy = shriftlar.get(m.group(1).decode(), (m.group(1).decode(), None))
                continue
            if m.group(2) is None:
                matn.append("\n" if m.group(0) == b"ET" else " ")
                continue
            kodlar = _satr(m.group(2))
            base, cmap = joriy
            if cmap is not None:
                matn.append("".join(KVADRAT if not cmap.get(k) or cmap.get(k) == "\x00" else cmap[k] for k in kodlar))
            elif base and "ZapfDingbats" in base:
                matn.append(KVADRAT * len(kodlar))
            elif base and "Symbol" in base:
                matn.append("".join("−" if k == 0x2D else "?" for k in kodlar))
            else:
                matn.append("".join(_WINANSI.get(k, chr(k)) for k in kodlar))
        matn.append("\n")
    bazalar = sorted({b for b, _ in shriftlar.values()})
    return {"matn": re.sub(r"[ \t]+", " ", "".join(matn)), "shriftlar": bazalar,
            "type1": [b for b, c in shriftlar.values() if c is None]}


# ── fikstura ────────────────────────────────────────────────────────────────────────────────────────────────────
MIJOZ = "Раҳимов Ўктам (Қўқон)"
LOYIHA = "Ғиштли уй фасади"
USTA_NOMI = "Усмон уста"
DETAL = "Карниз №1 профил"
TM_NOMI = "Тайёр карниз"
TM_EMOJI = "Karniz 🔥 sariq"
XARIDOR = "Жўрабек"

s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "shrift_admin", "Parol123!", UserRole.ADMIN, "Shrift admin", company_id=1)
PRJ = Project(company_id=1, client_name=MIJOZ, project_name=LOYIHA, total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="Shrift Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
USTA = Master(company_id=1, name=USTA_NOMI, phone="+998900001072", kpi_percent=10)
TM = FinishedProduct(company_id=1, name=TM_NOMI, quantity=50, unit="metr", source=StockSource.PRODUCED,
                     production_status=ProductionStatus.READY, unit_price=10_000, cost_price=5_000)
TM2 = FinishedProduct(company_id=1, name=TM_EMOJI, quantity=50, unit="metr", source=StockSource.PRODUCED,
                      production_status=ProductionStatus.READY, unit_price=10_000, cost_price=5_000)
s.add_all([PRJ, PENO, USTA, TM, TM2])
s.commit()
PRJ_ID, PENO_ID, USTA_ID, TM_ID, TM2_ID = PRJ.id, PENO.id, USTA.id, TM.id, TM2.id
s.execute(text("UPDATE users SET is_platform_admin = :t WHERE username = 'shrift_admin'"), {"t": True})
s.commit()
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "shrift_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

ID = {}
_r = req(C, "post", "/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": PRJ_ID, "order_type": "product", "master_id": USTA_ID, "deadline": "2026-10-05",
    "items": [{"name": DETAL, "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 1,
               "unit_price": 1_000_000, "is_coated": False, "penoplast_id": PENO_ID}]})
ID["O1"] = (js(_r) or {}).get("id") if _r.status_code == 200 else None
s = SessionLocal()
try:
    ID["IT1"] = s.execute(text("SELECT id FROM order_items WHERE order_id = :o"), {"o": ID["O1"] or 0}).scalar()
finally:
    s.close()
_r = req(C, "post", "/api/deliveries", json={"order_id": ID["O1"], "items": [{"order_item_id": ID["IT1"], "quantity": 4}],
                                             "notes": "Изоҳ: эҳтиёт бўлинг", "transport_cost": 50_000,
                                             "transport_payer": "client", "payment_method": "naqd",
                                             "payment_amount": 100_000})
ID["D1"] = (js(_r) or {}).get("delivery_id") if isinstance(js(_r), dict) else None
_r = req(C, "post", "/api/finished/sell", json={"finished_product_id": TM_ID, "quantity": 2, "unit_price": 10_000,
                                                "buyer_name": XARIDOR})
ID["SALE"] = (js(_r) or {}).get("sale_id") if isinstance(js(_r), dict) else None
_r = req(C, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": TM_ID, "quantity": 3,
                                                                  "unit_price": 10_000}],
                                                       "buyer_name": "Ҳамид ака", "agreed_amount": 27_000})
ID["GROUP"] = (js(_r) or {}).get("sale_group_id") if isinstance(js(_r), dict) else None
_r = req(C, "post", "/api/finished/sell", json={"finished_product_id": TM2_ID, "quantity": 1, "unit_price": 10_000,
                                                "buyer_name": "Emoji xaridor"})
ID["SALE2"] = (js(_r) or {}).get("sale_id") if isinstance(js(_r), dict) else None
ID["XARAJAT"] = [req(C, "post", "/api/finance/transactions", json={"category": k, "amount": float(v), "notes": iz}).status_code
                 for k, v, iz in (("arenda", 1_500_000, "Ижара"), ("elektr", 300_000, "Свет"), ("tushlik", 200_000, None),
                                  ("soliqlar", 400_000, "Солиқ"))]
from datetime import datetime, timedelta           # noqa: E402
_tk = datetime.utcnow() + timedelta(hours=5)

section("0. Tayyorgarlik")
check("0.1 fikstura: buyurtma, yuk xati (qisman, transport, to'lov), TM sotuvi yakka / guruh (chegirma), emoji nomli TM, "
      "4 xarajat", all(ID.get(k) for k in ("O1", "IT1", "D1", "SALE", "GROUP", "SALE2")) and ID["XARAJAT"] == [200] * 4, ID)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Shrift — Liberation Sans standart Helvetica nomlari bilan")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
TTF_FAYLLAR = ["fonts/LiberationSans-Regular.ttf", "fonts/LiberationSans-Bold.ttf", "fonts/LiberationSans-Italic.ttf",
               "fonts/LiberationSans-BoldItalic.ttf"]
check("A1 fonts/ da 4 ta Liberation Sans TTF va litsenziya (SIL Open Font License 1.1)",
      all(os.path.getsize(os.path.join(ROOT, f)) > 100_000 for f in TTF_FAYLLAR if os.path.exists(os.path.join(ROOT, f)))
      and all(os.path.exists(os.path.join(ROOT, f)) for f in TTF_FAYLLAR)
      and "SIL OPEN FONT LICENSE Version 1.1" in fayl("fonts/OFL.txt"),
      [f for f in TTF_FAYLLAR if not os.path.exists(os.path.join(ROOT, f))])
_NOMLAR = {"Helvetica": b"LiberationSans", "Helvetica-Bold": b"LiberationSans-Bold",
           "Helvetica-Oblique": b"LiberationSans-Italic", "Helvetica-BoldOblique": b"LiberationSans-BoldItalic"}


def _yuz(nom):
    try:
        f = pdfmetrics.getFont(nom)
        return (type(f).__name__, getattr(getattr(f, "face", None), "name", None), isinstance(f, TTFont))
    except Exception as e:                 # noqa: BLE001
        return (type(e).__name__, None, False)


check("A2 PDF modullari yuklangach 4 nom ('Helvetica', '-Bold', '-Oblique', '-BoldOblique') → Liberation Sans TTF",
      all(_yuz(n)[2] and _yuz(n)[1] == y for n, y in _NOMLAR.items()), {n: _yuz(n) for n in _NOMLAR})
try:
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    _fr1 = [f.fontName for f in Paragraph("<b>a</b> b <i>c</i> <b><i>d</i></b>",
                                          ParagraphStyle("t1", fontName="Helvetica", fontSize=10)).frags]
    _fr2 = [f.fontName for f in Paragraph("<i>a</i> b", ParagraphStyle("t2", fontName="Helvetica-Bold", fontSize=10)).frags]
except Exception as e:                     # noqa: BLE001
    _fr1 = _fr2 = [f"{type(e).__name__}: {e}"]
check("A3 `<b>` / `<i>` oilasi: Helvetica + <b> → -Bold, <i> → -Oblique, <b><i> → -BoldOblique; -Bold + <i> → -BoldOblique",
      _fr1 == ["Helvetica-Bold", "Helvetica", "Helvetica-Oblique", "Helvetica", "Helvetica-BoldOblique"]
      and _fr2 == ["Helvetica-BoldOblique", "Helvetica-Bold"], [_fr1, _fr2])
_NAMUNA = "YUK XATI (NAKLADNOY) Mahsulot nomi Birlik narxi 1 000 000 so'm — QARZ QOLDI: 900 000 so'm ORD-001-1/Y-1"
_farq = {}
for _n in _NOMLAR:
    try:
        _afm = pdfmetrics.Font("afm_" + _n, _n, "WinAnsiEncoding").stringWidth(_NAMUNA, 10)
        _ttf = pdfmetrics.stringWidth(_NAMUNA, _n, 10)
        _farq[_n] = round(100 * (_ttf - _afm) / _afm, 4)
    except Exception as e:                 # noqa: BLE001
        _farq[_n] = f"{type(e).__name__}: {e}"
check("A4 metrika = Helvetica (AFM): satr kengligi farqi < 0.05 % (jadval / satr ko'chishi o'zgarmaydi)",
      all(isinstance(v, float) and abs(v) < 0.05 for v in _farq.values()), _farq)
_KOD = ("import os, sys; sys.path.insert(0, os.getcwd())\n"
        "from reportlab.pdfbase import pdfmetrics\n"
        "pdfmetrics.stringWidth('Salom', 'Helvetica', 10); pdfmetrics.stringWidth('Salom', 'Helvetica-Bold', 10)\n"
        "import pdf_shrift; pdf_shrift.shriftlarni_ulash()\n"
        "print(sorted(type(pdfmetrics.getFont(n)).__name__ for n in ('Helvetica', 'Helvetica-Bold')))\n")
try:
    _p = subprocess.run([sys.executable, "-c", _KOD], capture_output=True, text=True, timeout=120, cwd=ROOT)
    _a5 = _p.stdout.strip() + _p.stderr.strip()[-200:]
except Exception as e:                     # noqa: BLE001
    _a5 = f"{type(e).__name__}: {e}"
check("A5 standart Type1 Helvetica jarayonda AVVAL ishlatilgan bo'lsa ham ulashdan keyin TTF (ReportLab jim o'tkazmaydi)",
      _a5 == "['_XavfsizShrift', '_XavfsizShrift']", _a5)
try:
    _oldin = [pdfmetrics.getFont(n) for n in _NOMLAR]
    pdf_shrift.shriftlarni_ulash()
    _a6 = all(a is pdfmetrics.getFont(n) for a, n in zip(_oldin, _NOMLAR))
except Exception as e:                     # noqa: BLE001
    _a6 = False
    _oldin = f"{type(e).__name__}: {e}"
check("A6 takroriy `shriftlarni_ulash()` — o'sha shrift obyektlari (qayta yuklanmaydi)", _a6, _oldin)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. 7 PDF — Kirill ma'lumot, \"№\", qora kvadrat YO'Q")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
PDFLAR = [
    ("B1 nakladnoy", f"/api/orders/{ID['O1']}/pdf", {}, [MIJOZ, LOYIHA, DETAL]),
    ("B2 yuk xati (mijozga boradi)", f"/api/deliveries/{ID['D1']}/pdf", {},
     [MIJOZ, LOYIHA, DETAL, "№ ORD-", "QISMAN YETKAZISH", "Transport:", "Shu yuk uchun to'lov qilindi:", "Изоҳ: эҳтиёт бўлинг"]),
    ("B3 hisob-kitob varaqasi", f"/api/orders/{ID['O1']}/summary-pdf", {}, [MIJOZ, LOYIHA, DETAL, "№1 ·"]),
    ("B4 TM sotuvi (yakka)", f"/api/finished/sales/{ID['SALE']}/pdf", {}, [TM_NOMI, XARIDOR, "№ S-"]),
    ("B5 TM sotuvi (guruh, chegirma)", f"/api/finished/sales/batch/{ID['GROUP']}/pdf", {}, [TM_NOMI, "Ҳамид ака", "− "]),
    ("B6 oylik moliya", "/api/finance/report-pdf", {"year": _tk.year, "month": _tk.month}, ["Arenda", "Elektr", "Tushlik", "Soliqlar"]),
    # kech117 (A2): «Gips vs Penoplast» o'rniga — yo'nalishlar bo'yicha sof foyda hisoboti
    ("B7 yo'nalishlar bo'yicha sof foyda", "/api/finance/split-profit-pdf", {"year": _tk.year, "month": _tk.month},
     ["Yo'nalishlar bo'yicha sof foyda hisoboti", "Moliya hisobotidagi sof foyda", "Penoplast", "SOF FOYDA"]),
]
_JAMI_KV = 0
for _nom, _url, _par, _kutilgan in PDFLAR:
    _r = req(C, "get", _url, params=_par)
    _ok = _r.status_code == 200 and _r.content[:4] == b"%PDF"
    try:
        _o = pdf_oqi(_r.content) if _ok else {"matn": "", "shriftlar": [], "type1": ["?"]}
    except Exception as e:                 # noqa: BLE001
        _o = {"matn": "", "shriftlar": [f"{type(e).__name__}: {e}"], "type1": ["?"]}
    _kv = _o["matn"].count(KVADRAT)
    _JAMI_KV += _kv
    _yoq = [k for k in _kutilgan if k not in _o["matn"]]
    check(f"{_nom}: 200, faqat Liberation TTF (Type1 / ZapfDingbats / Symbol yo'q), ■ yo'q, matnda: {', '.join(_kutilgan[:4])}…",
          _ok and not _o["type1"] and _o["shriftlar"] and all("LiberationSans" in b for b in _o["shriftlar"])
          and _kv == 0 and not _yoq,
          [_r.status_code, _o["shriftlar"], f"■ {_kv}", "yo'q: " + repr(_yoq),
           [q.strip()[:90] for q in _o["matn"].splitlines() if KVADRAT in q][:4]])
check("B8 7 PDF da jami ■ = 0 (asl zip 101 kodida shu fiksturada — 233)", _JAMI_KV == 0, _JAMI_KV)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Ma'lumotdagi emoji — tashlab yuboriladi (bo'sh kvadrat emas)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = req(C, "get", f"/api/finished/sales/{ID['SALE2']}/pdf")
try:
    _o = pdf_oqi(_r.content) if _r.status_code == 200 else {"matn": "", "shriftlar": [], "type1": ["?"]}
except Exception as e:                     # noqa: BLE001
    _o = {"matn": "", "shriftlar": [f"{type(e).__name__}: {e}"], "type1": ["?"]}
_satrlar = [q.strip() for q in _o["matn"].splitlines() if "Karniz" in q]
check("C1 TM nomi \"Karniz 🔥 sariq\": PDF 200, nom \"Karniz  sariq\" (emoji chizilmagan), ■ / .notdef yo'q",
      _r.status_code == 200 and any("Karniz" in q and "sariq" in q and "🔥" not in q for q in _satrlar)
      and KVADRAT not in _o["matn"] and not _o["type1"], [_r.status_code, _satrlar[:3], _o["shriftlar"]])
check("C2 tashlab yuborilgan belgi qayd etilgan (`pdf_shrift.TASHLANGAN` da 🔥)",
      pdf_shrift is not None and "🔥" in getattr(pdf_shrift, "TASHLANGAN", set()),
      sorted(getattr(pdf_shrift, "TASHLANGAN", set())) if pdf_shrift else "pdf_shrift yo'q")
try:
    _w1 = pdfmetrics.stringWidth("Karniz 🔥 sariq", "Helvetica", 10)
    _w2 = pdfmetrics.stringWidth("Karniz  sariq", "Helvetica", 10)
except Exception as e:                     # noqa: BLE001
    _w1, _w2 = f"{type(e).__name__}: {e}", None
check("C3 tashlangan belgi satr kengligiga qo'shilmaydi (jadval katagi siljimaydi)", _w1 == _w2, [_w1, _w2])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Statik")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
PDF_MODULLAR = [m.__name__ + ".py" for m in (pdf_service, delivery_pdf, finance_pdf)]


def _modul_chaqiruv(nom):
    """Modul darajasida `shriftlarni_ulash()` (yoki taxallusi) chaqiriladimi."""
    try:
        daraxt = ast.parse(fayl(nom))
    except SyntaxError:
        return False
    taxallus = {"shriftlarni_ulash"}
    for t in daraxt.body:
        if isinstance(t, ast.ImportFrom) and t.module == "pdf_shrift":
            taxallus |= {a.asname or a.name for a in t.names if a.name == "shriftlarni_ulash"}
    return any(isinstance(t, ast.Expr) and isinstance(t.value, ast.Call) and getattr(t.value.func, "id", None) in taxallus
               for t in daraxt.body)


check("D1 uch PDF moduli ham modul darajasida shriftni ulaydi (`from pdf_shrift import shriftlarni_ulash` + chaqiruv)",
      all(_modul_chaqiruv(m) for m in PDF_MODULLAR), {m: _modul_chaqiruv(m) for m in PDF_MODULLAR})
_cmaplar = []
for _f in TTF_FAYLLAR[:2]:
    try:
        _cmaplar.append(TTFont("tekshir_" + _f, os.path.join(ROOT, _f)).face.charToGlyph)
    except Exception:                      # noqa: BLE001
        pass


def _yoq_belgilar(nom):
    topildi = {}
    try:
        daraxt = ast.parse(fayl(nom))
    except SyntaxError as e:
        return {"SyntaxError": str(e)}
    for t in ast.walk(daraxt):
        if isinstance(t, ast.Constant) and isinstance(t.value, str):
            for b in set(t.value):
                if b != "\n" and any(ord(b) not in cm for cm in _cmaplar):
                    topildi.setdefault(b, []).append(t.lineno)
    return topildi


_d2 = {m: _yoq_belgilar(m) for m in PDF_MODULLAR} if len(_cmaplar) == 2 else "fonts/ dagi TTF o'qilmadi"
check("D2 PDF modullari matnlarida shriftda (Regular / Bold) YO'Q belgi yo'q (emoji olib tashlangan)",
      isinstance(_d2, dict) and not any(_d2.values()),
      {m: {k: v[:3] for k, v in d.items()} for m, d in _d2.items() if d} if isinstance(_d2, dict) else _d2)
_rl = sorted(f for f in os.listdir(ROOT) if f.endswith(".py") and re.search(r"^\s*(from|import)\s+reportlab", fayl(f), re.M))
check("D3 ReportLab faqat PDF modullari va `pdf_shrift.py` da (boshqa PDF yo'li shriftsiz qolmasin)",
      _rl == sorted(PDF_MODULLAR + ["pdf_shrift.py"]), _rl)
check("D4 `requirements.txt` — reportlab 4.2.x (ro'yxatga olish shu versiya xulqiga moslangan; yangilansa — shu test)",
      re.search(r"^reportlab==4\.2\.\d+\s*$", fayl("requirements.txt"), re.M), re.findall(r"^reportlab.*$", fayl("requirements.txt"), re.M))

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Nazorat — PDF o'quvchi qora kvadratni TOPADI")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    from reportlab.pdfgen import canvas as _canvas
    _t1 = pdfmetrics.Font("NazoratType1", "Helvetica", "WinAnsiEncoding")
    pdfmetrics.registerFont(_t1)
    _buf = io.BytesIO()
    _cv = _canvas.Canvas(_buf)
    _cv.setFont("NazoratType1", 12)
    _cv.drawString(50, 700, "№ 5 Карниз ok")
    _cv.save()
    _e = pdf_oqi(_buf.getvalue())
except Exception as e:                     # noqa: BLE001
    _e = {"matn": f"{type(e).__name__}: {e}", "shriftlar": [], "type1": []}
check("E1 Type1 shrift bilan \"№ 5 Карниз ok\" → o'quvchi: \"■ 5 ■■■■■■ ok\", Type1 va ZapfDingbats qayd etiladi",
      "■ 5 ■■■■■■ ok" in _e["matn"] and "ZapfDingbats" in " ".join(_e["type1"]), [_e["matn"].strip()[:80], _e["type1"]])


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
    _n = pdf_oqi(_npdf)["matn"]
except Exception as e:                     # noqa: BLE001
    _ni, _n = -1, f"{type(e).__name__}: {e}"
check("E2 nazorat: PDF o'quvchi — ASCII85 oqimi \">\" bilan tugasa ham o'qiladi (tugatuvchi \"~>\" faqat bir marta olinadi), satr ichidagi \"ET\" / \"BT\" (\"YETKAZISH\") BT … ET blokini uzmaydi",
      "QISMAN YETKAZISH (BT) ET" in _n and f"nazorat {_ni}" in _n, [_ni, _n.strip()[:80]])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
