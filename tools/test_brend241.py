#!/usr/bin/env python3
"""
test_brend241.py — kech176 (zip 241): platforma nomi «epserp» + logotipi; korxona hujjatlarida FAQAT o'z logotipi / nomi.

NIMA UCHUN KERAK (egasi so'rovi 02.11 14:52 — demo korxonalar uchun; O'LCHANGAN `work/k241/probe241.py`, asl kod = zip 240c)
  1) Dastur nomi hamma joyda «PenoDecorPro ERP» edi: kirish oynasi («Penodecor<span>Pro</span>», «PD» belgisi), brauzer yorlig'i
     (24 sahifa sarlavhasi «… — PenoDecorPro ERP», base standarti, xato sahifasi), hodim sahifalari («… — PenoDecorPro»), hodim
     kirishi («Penodecor<span>Pro</span>»), /api/health matni — demo mijoz BOSHQA korxonaning nomini ko'rardi.
  2) Logotip yuklagan korxonada logotip faqat 2 hujjatda («Buyurtma hisobi», «Taklif») bor edi; yuk xati, hisob-kitob varaqasi, sotuv
     cheki (yakka / savat), yuk xatlari jamlanmasi, moliya hisobotlari (oylik, yo'nalishlar) — logotipsiz (egasi QARORI 02.11: «7 hujjatga
     ham logo»). O'lchov: yangi korxonaning 9 hujjatida PenoDecorPro nomi / telefoni / manzili / shiori / logotipi YO'Q edi (to'g'ri) —
     shu qoida saqlanishi SHART.
TALAB (har biri o'lchanadi):
  S  statik: logotip fayllari (SVG — egasi ranglari «eps» #1E293B, «erp» #2563EB; belgi; 180 px PNG), shablonlarda «PenoDecorPro» /
     «Penodecor» ko'rinadigan matni yo'q (sarlavha 24 + base + xato + hodim 4), favicon (base, kirish, hodim 4, xato), kirish oynasi —
     1-namuna (oq plitada logotip, telefonda tepada), main.py title / health, crud Excel muallifi, PDF yordamchilari va 7 generator
  L  HTTP: /login, /hodim/login — sarlavha «… — epserp», logotip va belgi havolalari 200 (to'g'ri turi bilan), «penodecor» YO'Q;
     /api/health — «epserp ishlamoqda!»
  T  kirgan foydalanuvchi sahifalari (yangi korxona admini): har HTML sahifa sarlavhasi «… — epserp», sarlavhada «PenoDecorPro» yo'q;
     menyuda korxonaning O'Z logotipi / nomi (begona emas)
  H  hujjatlar (9 PDF × 3 korxona): A (logotip yuklangan) — HAR hujjatda o'z logotipi (ko'rinish imzosi; sarlavhada 300 dpi ga
     kichraytirilgan — H10: hujjat hajmi), PenoDecorPro logotipi /
     nomi / telefoni / manzili / shiori YO'Q, o'z nomi bor, logotip 34 × 12 mm qutida nisbati bilan; B (logotipsiz) — rasm YO'Q, o'z
     nomi bor, taqiqlilar yo'q; 1 (platforma egasi) — 9 hujjatda o'z logotipi va nomi; sarlavha balandligi o'zgarmagan (hujjat nomi
     A da B dagidek joyda); sahifalar soni A = B; sarlavha geometriyasi (oq katak, bo'sh joylar, quti chegaralari — A = B)
  N  nisbat: tik (300 × 600) va juda keng (1000 × 100) logotip — yuk xatida nisbati saqlanadi, qutiga sig'adi; eski katta logotip
     (diskda 3000 × 1500) — PDF ga kichraytirilgan nusxa
  B  buzilgan logotip fayli (diskda) — 7 hujjat 200, rasm yo'q, nom bor (yiqilmaydi)
  U  (review241 H1) UZUN nom (40 belgi) + KENG logotip (4 : 1) + 20 detalli to'liq yuk: logotipli (C) va logotipsiz (D) — sahifalar soni
     AYNAN (yuk xati 1 sahifa), sarlavha qutisi kengligi bir xil, balandligi OSHMAYDI, nom qatorlari soni bir xil; oylik hisobot oltin
     chizig'i — butun eniga (L1)
  G  (review241 M2) 16 bitli kulrang PNG logotip — 8 bitga saqlanadi, PDF da OQ quti emas (yuk xati va «Buyurtma hisobi»); diskdagi eski
     16 bitli fayl ham PDF da 8 bitga
  R  (review241 M1) logotip almashtirilayotganda PDF lar (yuk xati, hisob-kitob, oylik, «Buyurtma hisobi») — hammasi 200, rasm — eski yoki
     yangi logotip
  J  HAQIQIY Chromium: kirish oynasi (kompyuter — oq plitadagi logotip ko'rinadi; telefon 390 — tepada logotip), hodim kirishi
     logotipi, brauzer belgisi (favicon) yuklanadi; past ekranda (844 × 390, 320 × 568 — blok xabari bilan ham) logotip va forma tepasi
     ko'rinadi, tugmagacha aylantiriladi (review241 L3)
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL` bilan HAQIQIY PostgreSQL 16.
Asl kodga (zip 240c) qarshi QULAMAYDI — yiqiladi. Test o'zi yozgan logotip fayllarini oxirida o'chiradi.
ISHLATISH: python3 tools/test_brend241.py
"""
import os
import io
import re
import sys
import time
import socket
import hashlib
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta, timezone

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"brend241_test_{os.getpid()}"     # review241 L5: parallel PG yurishlari bir-birining bazasini o'chirmasin
_DB = os.path.join(tempfile.mkdtemp(prefix="brend241_"), "brend241_test.db")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User, Project, Inventory, FinishedProduct, StockSource, ProductionStatus  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from PIL import Image                              # noqa: E402
import pdfplumber                                  # noqa: E402
from pypdf import PdfReader                        # noqa: E402

for _n in ("_send_telegram", "_send_telegram_to", "_send_telegram_document", "_send_telegram_to_qoplamachi"):
    if hasattr(main, _n):
        setattr(main, _n, lambda *a, **k: False)
crud.PUL_TAKROR_SONIYA = 0

OK = FAIL = 0
FAILED = []
MM = 72 / 25.4


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        good = bool(cond)
    except Exception:                      # noqa: BLE001
        good = False
    if good:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:700]}")


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
        return None


def fayl(nom, binar=False):
    try:
        with open(os.path.join(ROOT, nom), "rb" if binar else "r", **({} if binar else {"encoding": "utf-8"})) as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return b"" if binar else ""


def rgb_md5(im):
    try:
        return hashlib.md5(im.convert("RGB").tobytes()).hexdigest()
    except Exception:                      # noqa: BLE001
        return None


def imzo(im):
    """Rasm «imzosi» — oq fonga qo'yilgan (shaffoflik hisobga olinadi), 32 × 32 kulrang piksellar va eni / bo'yi nisbati. PDF sarlavhasidagi
    logotip 300 dpi ga kichraytiriladi (zip 241) — piksel md5 emas, ko'rinish solishtiriladi."""
    try:
        rgba = im.convert("RGBA")
        oq = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        k = Image.alpha_composite(oq, rgba).convert("L").resize((32, 32), resample=Image.BILINEAR)
        return list(k.getdata()), im.size[0] / float(im.size[1])
    except Exception:                      # noqa: BLE001
        return None


def bir_xil(x, asl):
    """PDF dagi rasm (`pdf_rasmlari` elementi) asl rasmga (`imzo`) ko'rinishda tengmi: o'rtacha farq < 8 (0–255) va nisbat ±3 %."""
    if not x or not asl or not x[2]:
        return False
    a, b = x[2], asl
    return abs(a[1] / b[1] - 1) < 0.03 and sum(abs(p - q) for p, q in zip(a[0], b[0])) / 1024.0 < 8


def pdf_rasmlari(b):
    """[(rgb_md5, (px_eni, px_boyi), imzo)] — HAMMA sahifadagi rasmlar; o'qib bo'lmasa — None."""
    try:
        out = []
        for p in PdfReader(io.BytesIO(b)).pages:
            for im in p.images:
                out.append((rgb_md5(im.image), im.image.size, imzo(im.image)))
        return out
    except Exception:                      # noqa: BLE001
        return None


def pdf_rasm_mm(b):
    """Birinchi sahifadagi rasmlar: [(eni_mm, bo'yi_mm)]."""
    try:
        with pdfplumber.open(io.BytesIO(b)) as p:
            return [(round(i["width"] / MM, 2), round(i["height"] / MM, 2)) for i in p.pages[0].images]
    except Exception:                      # noqa: BLE001
        return None


def pdf_matni(b):
    try:
        with pdfplumber.open(io.BytesIO(b)) as p:
            return "\n".join((pg.extract_text() or "") for pg in p.pages)
    except Exception:                      # noqa: BLE001
        return ""


def pdf_sahifalar(b):
    try:
        return len(PdfReader(io.BytesIO(b)).pages)
    except Exception:                      # noqa: BLE001
        return None


def soz_top(b, soz):
    """Birinchi sahifada `soz` so'zining (birinchi uchrashuvi) tepadan masofasi (nuqta)."""
    try:
        with pdfplumber.open(io.BytesIO(b)) as p:
            for w in p.pages[0].extract_words():
                if w["text"] == soz:
                    return round(w["top"], 1)
    except Exception:                      # noqa: BLE001
        pass
    return None


DARK_RGB = (0.102, 0.145, 0.184)        # PDF sarlavha foni #1A252F


def _rang(r, c):
    x = r.get("non_stroking_color")
    return isinstance(x, (tuple, list)) and len(x) == 3 and all(abs(a - b) < 0.01 for a, b in zip(x, c))


def sarlavha_quti(b):
    """Birinchi sahifadagi ENG TEPADAGI to'q sarlavha: {'quti': (x0, x1, top, bottom) — to'q + oq katak birga, 'oq': [(x0, x1)],
    'rasm': [(x0, x1, top, bottom)] — sarlavha ichidagi rasmlar}; to'q sarlavha topilmasa — None."""
    try:
        with pdfplumber.open(io.BytesIO(b)) as p:
            pg = p.pages[0]
            tq = [r for r in pg.rects if _rang(r, DARK_RGB)]
            if not tq:
                return None
            t0 = min(tq, key=lambda r: r["top"])
            ust = lambda r: abs(r["top"] - t0["top"]) < 0.6 and abs(r["bottom"] - t0["bottom"]) < 0.6
            bir = [r for r in tq if ust(r)]
            oq = [r for r in pg.rects if _rang(r, (1, 1, 1)) and ust(r)]
            im = [i for i in pg.images if i["top"] >= t0["top"] - 0.6 and i["bottom"] <= t0["bottom"] + 0.6]
            hamma = bir + oq
            return {"quti": (round(min(r["x0"] for r in hamma), 1), round(max(r["x1"] for r in hamma), 1), round(t0["top"], 1),
                             round(t0["bottom"], 1)),
                    "oq": sorted({(round(r["x0"], 1), round(r["x1"], 1)) for r in oq}),
                    "tq_x0": round(min(r["x0"] for r in bir), 1),
                    "rasm": [(round(i["x0"], 1), round(i["x1"], 1), round(i["top"], 1), round(i["bottom"], 1)) for i in im]}
    except Exception:                      # noqa: BLE001
        return None


TAQIQ = [r"penodecor", r"999\s*57\s*57", r"fasad bezaklari", r"andijon"]


def taqiqlar(matn):
    return [t for t in TAQIQ if re.search(t, matn or "", re.I)]


def rasm_bayt(w, h, rang=(20, 120, 90), fmt="PNG"):
    im = Image.new("RGB", (w, h), rang)
    for x in range(0, w, 5):
        im.putpixel((x, (x * 7) % h), (250, 250, 20))
    b = io.BytesIO()
    im.save(b, fmt)
    return b.getvalue(), rgb_md5(im)


UPL = os.path.join(ROOT, "static", "uploads", "logos")
_BOSH = set(os.listdir(UPL)) if os.path.isdir(UPL) else set()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
LG = fayl("templates/login.html")
HL = fayl("templates/hodim_login.html")
BASE = fayl("templates/base.html")
XATO = fayl("templates/xato_sahifa.html")
MAIN = fayl("main.py")
CRUD = fayl("crud.py")
PS = fayl("pdf_service.py")
DP = fayl("delivery_pdf.py")
FP = fayl("finance_pdf.py")
SVG = fayl("static/epserp_logo.svg")
BELGI = fayl("static/epserp_belgi.svg")
PNG180 = fayl("static/epserp_belgi_180.png", binar=True)
check("S1 logotip SVG: «epserp» (harflar — egri chiziq), ikki rang — «eps» #1E293B, «erp» #2563EB; to'q sariq yo'q",
      SVG.startswith("<svg") and 'fill="#1E293B"' in SVG and 'fill="#2563EB"' in SVG and SVG.count("<path") == 2
      and "<text" not in SVG and 'aria-label="epserp"' in SVG and "#F59E0B" not in SVG.upper(), SVG[:200])
_png = None
try:
    _png = Image.open(io.BytesIO(PNG180)).convert("RGB")
except Exception:                          # noqa: BLE001
    pass
check("S2 belgi: SVG (ko'k #2563EB fon, oq harf) va 180 × 180 PNG (telefon «Bosh ekran»; burchak — ko'k, o'rtasi — oq)",
      BELGI.startswith("<svg") and 'fill="#2563EB"' in BELGI and 'fill="#FFFFFF"' in BELGI and _png is not None
      and _png.size == (180, 180) and _png.getpixel((3, 3)) == (37, 99, 235) and _png.getpixel((90, 90)) == (255, 255, 255),
      (BELGI[:120], _png.size if _png else None))
_tdir = os.path.join(ROOT, "templates")
_yomon_t = []
_sar = 0
for _f in sorted(os.listdir(_tdir)):
    if not _f.endswith(".html"):
        continue
    _s = fayl(f"templates/{_f}")
    for _m in re.finditer(r"\{% block title %\}(.*?)\{% endblock %\}", _s, re.S):
        _sar += 1
        if not _m.group(1).endswith(" — epserp") and _f != "base.html":
            _yomon_t.append((_f, _m.group(1)[-40:]))
    _s2 = re.sub(r"\{#.*?#\}", "", _s, flags=re.S)                     # Jinja izohlari
    _s2 = re.sub(r"/\*.*?\*/", "", _s2, flags=re.S)                    # CSS / JS blok izohlari
    _s2 = _s2.replace("penodecor_new_order_draft_v1", "")              # brauzer xotirasi kaliti (ko'rinmaydi; qoralamalar yo'qolmasin)
    if re.search(r"penodecor", _s2, re.I):
        _yomon_t.append((_f, [ln.strip()[:90] for ln in _s2.splitlines() if re.search("penodecor", ln, re.I)][:3]))
check("S3 shablonlar: HAR `{% block title %}` «… — epserp» (24 sahifa), base standarti «epserp»; ko'rinadigan matnda / kodda "
      "«PenoDecorPro» / «Penodecor» YO'Q (izohlardan tashqari)", not _yomon_t and _sar >= 25
      and "<title>{% block title %}epserp{% endblock %}</title>" in BASE and "{{ _kn or 'epserp' }}" in BASE
      and "<title>{{ sarlavha }} — epserp</title>" in XATO, (_sar, _yomon_t[:8]))
_FAV = '<link rel="icon" type="image/svg+xml" href="/static/epserp_belgi.svg?v={{ static_version }}">'
_APL = '<link rel="apple-touch-icon" href="/static/epserp_belgi_180.png?v={{ static_version }}">'
_fav_yoq = [f for f in ("base", "login", "hodim_login", "hodim_kutish", "hodim_pin", "hodim_panel", "xato_sahifa", "hodim_qr")
            if fayl(f"templates/{f}.html").count(_FAV) != 1 or fayl(f"templates/{f}.html").count(_APL) != 1]
check("S4 brauzer belgisi (favicon) va telefon belgisi — base, kirish, 4 hodim sahifasi, hodim QR, xato sahifasi (har birida bir marta); "
      "«Zaxiradan tiklash» sahifasi — «… — epserp» va belgi", not _fav_yoq
      and '<title>Zaxiradan tiklash — epserp</title><link rel="icon" type="image/svg+xml" href="/static/epserp_belgi.svg">' in MAIN, _fav_yoq)
check("S5 kirish oynasi — 1-namuna: oq plitada logotip (chap panel), telefonda tepada logotip («mobil-brend»), «PD» belgisi va "
      "«Penodecor<span>Pro</span>» yo'q; parol / blok / forma — o'zgarmagan",
      '<div class="brand-plita"><img src="/static/epserp_logo.svg?v={{ static_version }}" alt="epserp"' in LG
      and '<div class="mobil-brend"><img src="/static/epserp_logo.svg?v={{ static_version }}" alt="epserp"' in LG
      and ".brand-plita{display:inline-flex;align-items:center;background:#fff;" in LG and ">PD<" not in LG
      and "Penodecor" not in LG and "<title>Kirish — epserp</title>" in LG and 'id="parolUnutdim"' in LG
      and 'id="blokXabari"' in LG and 'name="username" maxlength="100"' in LG and 'class="side-stats"' in LG
      and "login-bg.webp" in LG)
check("S6 hodim kirishi: epserp logotipi (rang — SVG faylda; sahifada #2563EB yo'q), «Penodecor» yo'q",
      '<img src="/static/epserp_logo.svg?v={{ static_version }}" alt="epserp"' in HL and "Penodecor" not in HL
      and "#2563EB" not in HL and "<title>Hodim kirishi — epserp</title>" in HL)
check("S7 main.py: FastAPI title «epserp», /api/health «epserp ishlamoqda!»; crud: do'kon Excel muallifi «epserp»",
      'app = FastAPI(title="epserp",' in MAIN and '"message": "epserp ishlamoqda!"' in MAIN
      and 'title="PenoDecorPro ERP"' not in MAIN and "PenoDecorPro ERP ishlamoqda" not in MAIN
      and 'wb.properties.creator = "epserp"' in CRUD and 'creator = "PenoDecorPro ERP"' not in CRUD)
check("S8 pdf_service: `pdf_logo_katagi` (34 × 12 mm, `_logo_tayyorla` — o'qilmasa None), `logoli_sarlavha` (oq katak, katak "
      "yo'q — jadval o'zi)", "SARLAVHA_LOGO_QUTI_MM = (34, 12)" in PS and "def pdf_logo_katagi(brand, quti_mm=SARLAVHA_LOGO_QUTI_MM):" in PS
      and "def logoli_sarlavha(ichki, katak, eni, fon, ost_chiziq=None):" in PS and "_t = _logo_tayyorla(yol)" in PS
      and '("BACKGROUND", (0, 0), (0, 0), colors.white)' in PS and "if not katak:\n        return ichki" in PS
      and "def sarlavha_uslubi(uslub, satrlar, tor, keng):" in PS and "def _logo_baytlari(yol):" in PS
      and "_lb241 = _logo_baytlari(logo_path) if _lo else None" in PS and "    _os.replace(_vaqt241, _os.path.join(papka, nom))" in MAIN)
check("S9 7 generator: delivery_pdf 5, finance_pdf 2 — `_logo_katagi241(_brand)` + `_logoli_sarlavha241` + sarlavha eni katakka "
      "kamaytirilgan", DP.count("_lk241 = _logo_katagi241(_brand)") == 5 and DP.count("header = _logoli_sarlavha241(header, _lk241,") == 5
      and FP.count("_lk241 = _logo_katagi241(_brand)") == 2 and FP.count("header = _logoli_sarlavha241(header, _lk241, W, DARK)") == 1
      and FP.count("header = _logoli_sarlavha241(header, _lk241, W, DARK, ost_chiziq=GOLD)") == 1
      and DP.count("_st241t = _sarlavha_uslubi241(st_title,") == 5 and DP.count("_st241s = _sarlavha_uslubi241(st_sub,") == 5
      and FP.count("_sarlavha_uslubi241(") == 4
      and DP.count("colWidths=[18*cm - _lk241e])") == 3 and DP.count("colWidths=[18.2*cm - _lk241e])") == 2
      and "colWidths=[W - _lk241e])" in FP and "colWidths=[(W - _lk241e) * 0.62, (W - _lk241e) * 0.38])" in FP,
      (DP.count("_lk241 = _logo_katagi241(_brand)"), FP.count("_lk241 = _logo_katagi241(_brand)")))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: korxona 1 (platforma egasi — logotipi platforma logotipi, production dagidek), platforma admini;
# korxona A «Namuna Penoplast» (logotip yuklanadi), B «Sinov Dekor» (logotipsiz) — PLATFORMA PANELI API si bilan
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PLAT_LOGO = getattr(main, "PLATFORMA_LOGOTIPI", "static/logo_transparent.png")
PLAT_MD5 = rgb_md5(Image.open(os.path.join(ROOT, PLAT_LOGO)))
PLAT_IMZO = imzo(Image.open(os.path.join(ROOT, PLAT_LOGO)))
s = SessionLocal()
c1 = s.query(Company).filter(Company.id == 1).first()
if c1 is None:
    c1 = Company(id=1, name="PenodecorPro")
    s.add(c1)
    s.flush()
c1.logo_path = PLAT_LOGO
c1.slogan, c1.address, c1.phone = "Fasad bezaklari", "Andijon", "+998 97 999 57 57"
s.commit()
# Logotip fayli nomi — `company_<id>` (static/uploads/logos — rejimlar uchun UMUMIY papka): bir vaqtda yuradigan nusxalar (SQLite / TF1 /
# PG, etalon zanjirlari) bir-birining logotipini almashtirmasin — A / B id lari jarayonga xos (bo'sh korxona + ketma-ketlik).
_X = 100_000 + os.getpid() * 3
s.add(Company(id=_X, name=f"B241 bo'sh {_X}"))
s.commit()
if PG_URL:
    s.execute(text("SELECT setval(pg_get_serial_sequence('companies', 'id'), :x)"), {"x": _X})
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "b241_plat", "Parol123!", UserRole.ADMIN, "Platforma", company_id=1)
_u = s.query(User).filter(User.username == "b241_plat").first()
_u.is_platform_admin = True
s.commit()
s.close()


def kirish(login, parol):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": parol}, follow_redirects=False)
    return c if getattr(r, "status_code", 599) == 302 else None


PL = kirish("b241_plat", "Parol123!")
KX = {"1": {"nom": "PenodecorPro", "id": 1, "C": PL}}
for _k, _nom, _login in (("A", "Namuna Penoplast", "b241_namuna"), ("B", "Sinov Dekor", "b241_sinov")):
    _r = req(PL, "post", "/api/platform/companies", data={"name": _nom, "admin_username": _login, "admin_full_name": _nom + " admin"}) \
        if PL else _Xato(Exception("platforma admini kirmadi"))
    _j = js(_r) or {}
    KX[_k] = {"nom": _nom, "id": (_j.get("company") or {}).get("id"), "login": _login, "parol": (_j.get("admin") or {}).get("password") or "",
              "C": kirish(_login, (_j.get("admin") or {}).get("password") or "")}
check("0.1 fikstura: platforma admini; A va B korxonalari platforma paneli API si bilan yaratildi (id — jarayonga xos), adminlari kirdi",
      PL is not None and all(KX[k]["id"] and KX[k]["C"] is not None for k in ("A", "B")) and KX["A"]["id"] == _X + 1,
      {k: (v["id"], v["C"] is not None) for k, v in KX.items()})
if not all(KX[k]["C"] is not None for k in ("1", "A", "B")):
    print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL + 1}   jami = {OK + FAIL + 1}")
    sys.exit(1)
CA = KX["A"]["C"]
LOGO_A, LOGO_A_MD5 = rasm_bayt(600, 300)
LOGO_A_IMZO = imzo(Image.open(io.BytesIO(LOGO_A)))
_rl = req(CA, "post", "/api/settings/company/logo", files={"file": ("namuna.png", LOGO_A, "image/png")})
LOGO_A_YOL = os.path.join(ROOT, (js(_rl) or {}).get("logo_path") or "x")
check("0.2 A korxonasi logotipi yuklandi (600 × 300 PNG; diskdagi piksellar AYNAN)", _rl.status_code == 200 and os.path.exists(LOGO_A_YOL)
      and rgb_md5(Image.open(LOGO_A_YOL)) == LOGO_A_MD5, (_rl.status_code, _rl.text[:200]))

s = SessionLocal()
for _k in ("1", "A", "B"):
    _cid = KX[_k]["id"]
    _p = Project(company_id=_cid, client_name=f"{_k} mijoz", client_phone="+998 91 000 00 00", project_name=f"{_k} loyiha",
                 total_budget=0, total_paid=0)
    _pe = Inventory(company_id=_cid, item_name=f"{_k} Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                    volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
    _tm = FinishedProduct(company_id=_cid, name=f"{_k} TM", quantity=50, unit="metr", source=StockSource.PRODUCED,
                          production_status=ProductionStatus.READY, unit_price=10_000, cost_price=5_000)
    s.add_all([_p, _pe, _tm])
    s.commit()
    KX[_k].update({"PRJ": _p.id, "PENO": _pe.id, "TM": _tm.id})
s.close()
_tk = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=5)


def hujjatlar(k, n=1, toliq=False):
    """Korxona k da: n detalli buyurtma, yuk xati (toliq — hamma detal butunicha, aks holda 1-detaldan 4 m), TM sotuvi, xarajat, taklif."""
    d = KX[k]
    c = d["C"]
    tana = {"project_id": d["PRJ"], "order_type": "product",
            "items": [{"name": f"{k} karniz" + (f" detal nomi {i}" if n > 1 else ""), "category": "profil", "width": 20, "thickness": 10,
                       "length": 10, "quantity": 1, "unit_price": 1_000_000, "is_coated": False, "penoplast_id": d["PENO"]}
                      for i in range(n)]}
    oid = (js(req(c, "post", "/api/orders", params={"confirm_shortage": "true"}, json=tana)) or {}).get("id")
    s_ = SessionLocal()
    try:
        its = [x[0] for x in s_.execute(text("SELECT id FROM order_items WHERE order_id = :o ORDER BY id"), {"o": oid or 0}).fetchall()]
    finally:
        s_.close()
    it = its[0] if its else None
    _yuk = [{"order_item_id": x, "quantity": 10} for x in its] if toliq else [{"order_item_id": it, "quantity": 4}]
    did = (js(req(c, "post", "/api/deliveries", json={"order_id": oid, "items": _yuk,
                                                      "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd",
                                                      "payment_amount": 0})) or {}).get("delivery_id")
    sid = (js(req(c, "post", "/api/finished/sell", json={"finished_product_id": d["TM"], "quantity": 1, "unit_price": 10_000,
                                                         "buyer_name": "X"})) or {}).get("sale_id")
    gid = (js(req(c, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": d["TM"], "quantity": 1,
                                                                          "unit_price": 10_000}], "buyer_name": "Y"})) or {}).get("sale_group_id")
    req(c, "post", "/api/finance/transactions", json={"category": "boshqa", "amount": 5_000.0, "notes": "x"})
    tid = ((js(req(c, "post", "/api/takliflar", json={"mijoz": "T mijoz", "telefon": "+998 90 111 22 33",
                                                      "buyurtma": {"order_type": "product", "items": tana["items"][:1]}})) or {})
           .get("taklif") or {}).get("id")
    d["URL"] = {"buyurtma_hisobi": (f"/api/orders/{oid}/pdf", {}),
                "taklif": (f"/api/takliflar/{tid}/pdf", {}),
                "yuk_xati": (f"/api/deliveries/{did}/pdf", {}),
                "hisob_kitob": (f"/api/orders/{oid}/summary-pdf", {}),
                "sotuv_cheki": (f"/api/finished/sales/{sid}/pdf", {}),
                "sotuv_savat": (f"/api/finished/sales/batch/{gid}/pdf", {}),
                "yuk_jamlanma": (f"/api/projects/{d['PRJ']}/yuk-xatlari/jamlama-pdf", {}),
                "moliya_oylik": ("/api/finance/report-pdf", {"year": _tk.year, "month": _tk.month}),
                "foyda_ulushi": ("/api/finance/split-profit-pdf", {"year": _tk.year, "month": _tk.month})}
    return all((oid, it, did, sid, gid, tid)) and len(its) == n


YETTI = ("yuk_xati", "hisob_kitob", "sotuv_cheki", "sotuv_savat", "yuk_jamlanma", "moliya_oylik", "foyda_ulushi")


def pdflar(k):
    out = {}
    for nom, (url, par) in KX[k]["URL"].items():
        r = req(KX[k]["C"], "get", url, params=par)
        out[nom] = r.content if (r.status_code == 200 and r.content[:4] == b"%PDF") else None
    return out


check("0.3 fikstura: 3 korxonada buyurtma, yuk xati, TM sotuvi (yakka / savat), xarajat, taklif",
      all(hujjatlar(k) for k in ("1", "A", "B")))
P = {k: pdflar(k) for k in ("1", "A", "B")}

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L. Kirish sahifalari (HTTP)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
AN = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_rlg = req(AN, "get", "/login")
_rhl = req(AN, "get", "/hodim/login")
_t = lambda h: (re.search(r"<title>(.*?)</title>", h or "", re.S).group(1).strip() if re.search(r"<title>(.*?)</title>", h or "", re.S) else None)
check("L1 /login: 200, sarlavha «Kirish — epserp», logotip (plita + telefon) va belgi havolalari, «penodecor» YO'Q",
      _rlg.status_code == 200 and _t(_rlg.text) == "Kirish — epserp" and _rlg.text.count('src="/static/epserp_logo.svg?v=') == 2
      and 'rel="icon" type="image/svg+xml" href="/static/epserp_belgi.svg?v=' in _rlg.text and not re.search("penodecor", _rlg.text, re.I),
      (_rlg.status_code, _t(getattr(_rlg, "text", ""))))
check("L2 /hodim/login: 200, «Hodim kirishi — epserp», epserp logotipi, «penodecor» YO'Q",
      _rhl.status_code == 200 and _t(_rhl.text) == "Hodim kirishi — epserp" and 'src="/static/epserp_logo.svg?v=' in _rhl.text
      and not re.search("penodecor", _rhl.text, re.I), (_rhl.status_code, _t(getattr(_rhl, "text", ""))))
_fs = {u: req(AN, "get", u) for u in ("/static/epserp_logo.svg", "/static/epserp_belgi.svg", "/static/epserp_belgi_180.png")}
check("L3 logotip / belgi fayllari kirishsiz ochiladi (200, to'g'ri turi: image/svg+xml, image/png)",
      all(r.status_code == 200 for r in _fs.values())
      and "image/svg+xml" in _fs["/static/epserp_logo.svg"].headers.get("content-type", "")
      and "image/svg+xml" in _fs["/static/epserp_belgi.svg"].headers.get("content-type", "")
      and _fs["/static/epserp_belgi_180.png"].headers.get("content-type", "") == "image/png"
      and _fs["/static/epserp_logo.svg"].content == SVG.encode(), {u: (r.status_code, r.headers.get("content-type")) for u, r in _fs.items()})
_rh = req(AN, "get", "/api/health")
check("L4 /api/health — «epserp ishlamoqda!»", _rh.status_code == 200 and js(_rh) == {"status": "ok", "message": "epserp ishlamoqda!"},
      getattr(_rh, "text", "")[:120])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Sahifa sarlavhalari va menyu (kirgan foydalanuvchi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
SAHIFALAR = ["/", "/dashboard", "/projects", "/orders", "/production", "/recipes", "/finished", "/returns", "/inventory", "/suppliers",
             "/debts", "/finance", "/kunlik-xarajat", "/reports", "/kpi", "/ustalar", "/users", "/rollar", "/trash", "/logs",
             "/sozlamalar", "/murojaat", "/sayt-katalogi"]
_yomon, _ok_soni = [], 0
for _u in SAHIFALAR:
    _r = req(CA, "get", _u)
    if _r.status_code != 200:
        continue
    _ok_soni += 1
    _ti = _t(_r.text) or ""
    if not _ti.endswith(" — epserp") or re.search("penodecor", _ti, re.I):
        _yomon.append((_u, _ti))
check("T1 yangi korxona (A) admini: HAR HTML sahifa sarlavhasi «… — epserp» (≥ 18 sahifa 200)", _ok_soni >= 18 and not _yomon,
      (_ok_soni, _yomon[:6]))
_rp = req(PL, "get", "/platforma")
check("T2 platforma paneli sarlavhasi «Platforma paneli — epserp»", _rp.status_code == 200 and _t(_rp.text) == "Platforma paneli — epserp",
      (_rp.status_code, _t(getattr(_rp, "text", ""))))


def menyu(c):
    h = getattr(req(c, "get", "/orders"), "text", "")
    img = re.findall(r'class="s-logo-(?:rasm|oddiy)" src="([^"]+)"', h)
    nm = re.search(r'<div class="logo-name">(.*?)</div>', h)
    return img, (nm.group(1) if nm else None), h


_ma, _mb, _m1 = menyu(CA), menyu(KX["B"]["C"]), menyu(PL)
check("T3 menyu: A — o'z logotipi (`uploads/logos/company_<A>`), B — o'z nomi (logotipsiz), 1 — o'z (platforma) logotipi; "
      "favicon — epserp belgisi", _ma[0] and all(f"company_{KX['A']['id']}." in x for x in _ma[0]) and _mb[0] == []
      and _mb[1] == "Sinov Dekor" and _m1[0] == ["/static/logo_menyu.webp"]
      and 'rel="icon" type="image/svg+xml" href="/static/epserp_belgi.svg?v=' in _ma[2], (_ma[:2], _mb[:2], _m1[:2]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Hujjatlar (9 PDF × 3 korxona)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
for _k in ("1", "A", "B"):
    _yoq = [n for n, b in P[_k].items() if b is None]
    check(f"H0.{_k} korxona {_k}: 9 PDF — 200 (PDF)", not _yoq, _yoq)
_hA = {}
for _n, _b in P["A"].items():
    _r = pdf_rasmlari(_b) if _b else None
    _m = pdf_matni(_b) if _b else ""
    _hA[_n] = (bool(_r) and all(bir_xil(x, LOGO_A_IMZO) for x in _r), _r and any(bir_xil(x, PLAT_IMZO) for x in _r), taqiqlar(_m),
               "NAMUNA PENOPLAST" in _m.upper())
check("H1 A (logotip yuklangan): HAR 9 hujjatda o'z logotipi (ko'rinish imzosi — oq fonda 32 × 32, nisbat) — boshqa rasm yo'q",
      all(v[0] for v in _hA.values()), {n: v[0] for n, v in _hA.items()})
check("H2 A: PenoDecorPro logotipi / nomi / telefoni / manzili / shiori — hech bir hujjatda YO'Q; o'z nomi — hammasida",
      all(not v[1] and not v[2] and v[3] for v in _hA.values()), {n: v[1:] for n, v in _hA.items()})
_hB = {n: (pdf_rasmlari(b) if b else None, taqiqlar(pdf_matni(b)) if b else ["?"], "SINOV DEKOR" in pdf_matni(b).upper() if b else False)
       for n, b in P["B"].items()}
check("H3 B (logotipsiz): 9 hujjatda rasm YO'Q (begona logotip ham), taqiqlilar yo'q, o'z nomi bor",
      all(v[0] == [] and not v[1] and v[2] for v in _hB.values()), _hB)
_h1 = {n: (pdf_rasmlari(b) if b else None, "PENODECORPRO" in pdf_matni(b).upper() if b else False) for n, b in P["1"].items()}
check("H4 korxona 1 (platforma egasi): 9 hujjatda o'z logotipi (platforma logotipi) va nomi",
      all(v[0] and all(bir_xil(x, PLAT_IMZO) for x in v[0]) and v[1] for v in _h1.values()),
      {n: ([x[:2] for x in (v[0] or [])], v[1]) for n, v in _h1.items()})
_mmA = {n: pdf_rasm_mm(P["A"][n]) for n in YETTI if P["A"][n]}
check("H5 A: 7 hujjat sarlavhasidagi logotip — 34 × 12 mm qutida, nisbati (2 : 1) saqlangan: 24 × 12 mm (±0,1)",
      len(_mmA) == 7 and all(v and len(v) == 1 and abs(v[0][0] - 24) <= 0.1 and abs(v[0][1] - 12) <= 0.1 for v in _mmA.values()), _mmA)
_SOZ = {"yuk_xati": "YUK", "hisob_kitob": "HISOB-KITOB", "sotuv_cheki": "SOTUV", "sotuv_savat": "SOTUV", "yuk_jamlanma": "YUK"}
_tp = {n: (soz_top(P["A"][n], w), soz_top(P["B"][n], w)) for n, w in _SOZ.items() if P["A"][n] and P["B"][n]}
check("H6 sarlavha balandligi o'zgarmagan: hujjat nomi (YUK XATI / HISOB-KITOB / SOTUV CHEKI / jamlanma) A da B dagidek joyda (±1,5 nuqta)",
      len(_tp) == 5 and all(a is not None and b is not None and abs(a - b) <= 1.5 for a, b in _tp.values()), _tp)
_sp = {n: (pdf_sahifalar(P["A"][n]), pdf_sahifalar(P["B"][n])) for n in YETTI if P["A"][n] and P["B"][n]}
check("H7 sahifalar soni A = B (logotip hujjatni cho'zmaydi); yuk xati — 1 sahifa", len(_sp) == 7
      and all(a == b for a, b in _sp.values()) and _sp.get("yuk_xati") == (1, 1), _sp)
_mm1 = pdf_rasm_mm(P["1"]["yuk_xati"]) if P["1"]["yuk_xati"] else None
_w1, _h1px = Image.open(os.path.join(ROOT, PLAT_LOGO)).size
check("H8 korxona 1 yuk xati: platforma logotipi qutiga bo'yi bo'yicha (12 mm), nisbati saqlangan",
      _mm1 and len(_mm1) == 1 and abs(_mm1[0][1] - 12) <= 0.1 and abs(_mm1[0][0] / _mm1[0][1] - _w1 / _h1px) < 0.02, _mm1)

_geo = {n: (sarlavha_quti(P["A"][n]), sarlavha_quti(P["B"][n])) for n in YETTI if P["A"][n] and P["B"][n]}


def _geo_ok(a, b):
    if not a or not b or b["oq"] or b["rasm"] or len(a["oq"]) != 1 or len(a["rasm"]) != 1:
        return False
    (ox0, ox1), (ix0, ix1, it, ib) = a["oq"][0], a["rasm"][0]
    return (all(abs(x - y) <= 0.6 for x, y in zip(a["quti"], b["quti"])) and abs(ox0 - a["quti"][0]) <= 0.6
            and abs(a["tq_x0"] - ox1) <= 0.6 and ix0 - ox0 >= 4.9 and ox1 - ix1 >= 4.9 and it - a["quti"][2] >= 2.9
            and a["quti"][3] - ib >= 2.9)


check("H9 7 hujjat sarlavhasi: logotip OQ katakda (chap / o'ng ≥ 5 nuqta, tepa / past ≥ 3 nuqta bo'sh), to'q qism katakdan keyin "
      "boshlanadi; sarlavha qutisi (chegaralari) — logotipsiz korxonadagi bilan AYNAN (±0,6 nuqta; sahifadan chiqmaydi)",
      len(_geo) == 7 and all(_geo_ok(a, b) for a, b in _geo.values()), {n: v for n, v in _geo.items() if not _geo_ok(*v)})

_px = {n: [x[1] for x in (pdf_rasmlari(P["A"][n]) or [])] for n in YETTI if P["A"][n]}
_kb1 = {n: round(len(P["1"][n]) / 1024) for n in YETTI if P["1"][n]}
_px1 = [x[1] for x in (pdf_rasmlari(P["1"]["yuk_xati"]) or [])] if P["1"]["yuk_xati"] else None
check("H10 sarlavha logotipi 300 dpi ga kichraytirilgan: A (24 mm) — 284 × 142 px; platforma logotipi (1000 × 798, 15 × 12 mm) — 178 × 142 px; "
      "korxona 1 ning 7 hujjati < 150 KB (jonli sinov: asl o'lchamda ~900 KB edi)",
      len(_px) == 7 and all(v == [(284, 142)] for v in _px.values()) and _px1 == [(178, 142)] and len(_kb1) == 7
      and all(v < 150 for v in _kb1.values()), (_px, _px1, _kb1))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("N. Logotip nisbati (tik / juda keng)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
for _w, _h, _kut in ((300, 600, (6.0, 12.0)), (1000, 100, (34.0, 3.4))):
    _b, _md = rasm_bayt(_w, _h, (120, 30, 60))
    _iz = imzo(Image.open(io.BytesIO(_b)))
    _ru = req(CA, "post", "/api/settings/company/logo", files={"file": ("n.png", _b, "image/png")})
    _rp = req(CA, "get", KX["A"]["URL"]["yuk_xati"][0])
    _mm = pdf_rasm_mm(_rp.content) if _rp.status_code == 200 else None
    _rr = pdf_rasmlari(_rp.content) if _rp.status_code == 200 else None
    check(f"N {_w} × {_h}: yuk xatida {_kut[0]} × {_kut[1]} mm (±0,1), rasm — yangi logotip",
          _ru.status_code == 200 and _mm and len(_mm) == 1 and abs(_mm[0][0] - _kut[0]) <= 0.1 and abs(_mm[0][1] - _kut[1]) <= 0.1
          and _rr and bir_xil(_rr[0], _iz), (_ru.status_code, _mm, [x[:2] for x in (_rr or [])]))

# eski (zip 202 dan oldin yuklangan) katta logotip — diskda 3000 × 1500; PDF ga kichraytirilgan nusxa (`_logo_tayyorla`) chiziladi
s = SessionLocal()
try:
    _ly3 = s.execute(text("SELECT logo_path FROM companies WHERE id = :i"), {"i": KX["A"]["id"]}).scalar()
finally:
    s.close()
_kat, _ = rasm_bayt(3000, 1500, (40, 60, 160))
_kat_iz = imzo(Image.open(io.BytesIO(_kat)))
try:
    with open(os.path.join(ROOT, _ly3 or "x"), "wb") as f:
        f.write(_kat)
except Exception:                          # noqa: BLE001
    pass
_rk = req(CA, "get", KX["A"]["URL"]["yuk_xati"][0])
_rkr = pdf_rasmlari(_rk.content) if _rk.status_code == 200 else None
_rkm = pdf_rasm_mm(_rk.content) if _rk.status_code == 200 else None
check("N3 eski katta logotip (diskda 3000 × 1500): yuk xati 200, PDF dagi rasm kichraytirilgan (300 dpi — 284 × 142 px), o'sha rasm, 24 × 12 mm",
      _rk.status_code == 200 and _rkr and len(_rkr) == 1 and _rkr[0][1] == (284, 142) and bir_xil(_rkr[0], _kat_iz) and _rkm
      and abs(_rkm[0][0] - 24) <= 0.1 and abs(_rkm[0][1] - 12) <= 0.1, (_rk.status_code, [x[:2] for x in (_rkr or [])], _rkm))
_rkn = req(CA, "get", KX["A"]["URL"]["buyurtma_hisobi"][0])
_rknr = pdf_rasmlari(_rkn.content) if _rkn.status_code == 200 else None
check("N3b o'sha eski katta logotip «Buyurtma hisobi» da: 200, rasm — keshdagi kichraytirilgan nusxa (1000 × 500 px; asl 3000 × 1500 emas)",
      _rkn.status_code == 200 and _rknr and len(_rknr) == 1 and _rknr[0][1] == (1000, 500) and bir_xil(_rknr[0], _kat_iz),
      (_rkn.status_code, [x[:2] for x in (_rknr or [])]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Buzilgan logotip fayli (diskda)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
try:
    _ly = s.execute(text("SELECT logo_path FROM companies WHERE id = :i"), {"i": KX["A"]["id"]}).scalar()
finally:
    s.close()
_bz_yol = os.path.join(ROOT, _ly or "x")
try:
    _ok_b = open(_bz_yol, "rb").read()
    with open(_bz_yol, "wb") as f:
        f.write(_ok_b[:60])                                   # imzo bor, ichi kesilgan
except Exception:                          # noqa: BLE001
    pass
_bz = {}
for _n in YETTI:
    url, par = KX["A"]["URL"][_n]
    _r = req(CA, "get", url, params=par)
    _bz[_n] = (_r.status_code, pdf_rasmlari(_r.content) if _r.status_code == 200 else None,
               "NAMUNA PENOPLAST" in pdf_matni(_r.content).upper() if _r.status_code == 200 else False)
check("B1 diskdagi logotip buzilgan: 7 hujjat 200, rasm yo'q, korxona nomi bor (PDF yiqilmaydi)",
      all(v[0] == 200 and v[1] == [] and v[2] for v in _bz.values()), _bz)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. Uzun nom + keng logotip + 20 detalli to'liq yuk (review241 H1)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
UZUN = "«TOSHKENT FASAD DEKOR SERVIS PLYUS» MCHJ"
for _k, _login in (("C", "b241_uzun_c"), ("D", "b241_uzun_d")):
    _r = req(PL, "post", "/api/platform/companies", data={"name": UZUN, "admin_username": _login, "admin_full_name": "Uzun admin"})
    _j = js(_r) or {}
    KX[_k] = {"nom": UZUN, "id": (_j.get("company") or {}).get("id"), "C": kirish(_login, (_j.get("admin") or {}).get("password") or "")}
LOGO_C, LOGO_C_MD5 = rasm_bayt(1000, 250, (30, 90, 170))
_rlc = req(KX["C"]["C"], "post", "/api/settings/company/logo", files={"file": ("keng.png", LOGO_C, "image/png")}) if KX["C"]["C"] else _Xato(Exception("C"))
s = SessionLocal()
for _k in ("C", "D"):
    if KX[_k]["id"] is None:
        continue
    _p = Project(company_id=KX[_k]["id"], client_name=f"{_k} mijoz", client_phone="+998 91 000 00 00", project_name=f"{_k} loyiha",
                 total_budget=0, total_paid=0)
    _pe = Inventory(company_id=KX[_k]["id"], item_name=f"{_k} Penoplast", unit="blok", stock_quantity=1_000_000, price_per_unit=500_000,
                    volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
    _tm = FinishedProduct(company_id=KX[_k]["id"], name=f"{_k} TM", quantity=50, unit="metr", source=StockSource.PRODUCED,
                          production_status=ProductionStatus.READY, unit_price=10_000, cost_price=5_000)
    s.add_all([_p, _pe, _tm])
    s.commit()
    KX[_k].update({"PRJ": _p.id, "PENO": _pe.id, "TM": _tm.id})
s.close()
_uok = all(KX[k]["C"] is not None and KX[k].get("PRJ") for k in ("C", "D")) and _rlc.status_code == 200
_uok = _uok and hujjatlar("C", 20, True) and hujjatlar("D", 20, True)
check("U0 fikstura: C va D — bir xil uzun nom (40 belgi, platforma paneli API si), C ga 1000 × 250 logotip; 20 detalli buyurtma, to'liq yuk",
      _uok, (KX["C"].get("id"), KX["D"].get("id"), getattr(_rlc, "status_code", None)))
PU = {k: pdflar(k) for k in ("C", "D")} if _uok else {"C": {}, "D": {}}
_su = {n: (pdf_sahifalar(PU["C"].get(n)) if PU["C"].get(n) else None, pdf_sahifalar(PU["D"].get(n)) if PU["D"].get(n) else None)
       for n in YETTI}
check("U1 sahifalar soni C (logotipli) = D (logotipsiz) — 7 hujjat; 20 detalli to'liq yuk xati — 1 sahifa (ilgari logotip bilan 2 sahifa)",
      all(a is not None and a == b for a, b in _su.values()) and _su.get("yuk_xati") == (1, 1), _su)
_gu = {n: (sarlavha_quti(PU["C"][n]) if PU["C"].get(n) else None, sarlavha_quti(PU["D"][n]) if PU["D"].get(n) else None) for n in YETTI}


def _gu_ok(a, b):
    if not a or not b or len(a["rasm"]) != 1 or b["rasm"]:
        return False
    return (abs(a["quti"][0] - b["quti"][0]) <= 0.6 and abs(a["quti"][1] - b["quti"][1]) <= 0.6 and abs(a["quti"][2] - b["quti"][2]) <= 0.6
            and (a["quti"][3] - a["quti"][2]) <= (b["quti"][3] - b["quti"][2]) + 0.6)


check("U2 sarlavha: C da logotip bor, quti chap / o'ng / tepa chegaralari D dagidek, balandligi D dagidan OSHMAYDI (7 hujjat)",
      all(_gu_ok(a, b) for a, b in _gu.values()), {n: ((a or {}).get("quti"), (b or {}).get("quti")) for n, (a, b) in _gu.items()})


def nom_qatorlari(b):
    """Birinchi sahifadagi «MCHJ» va «PLYUS»» so'zlari tepadan masofasi bir xilmi (nom bir qatordami) — (bir_qator, qatorlar_soni)."""
    try:
        with pdfplumber.open(io.BytesIO(b)) as p:
            ws = [w for w in p.pages[0].extract_words() if w["top"] < 140]
            tops = sorted({round(w["top"]) for w in ws if any(x in w["text"] for x in ("TOSHKENT", "FASAD", "DEKOR", "SERVIS", "PLYUS", "MCHJ"))})
            return len(tops)
    except Exception:                      # noqa: BLE001
        return None


_nq = {n: (nom_qatorlari(PU["C"][n]) if PU["C"].get(n) else None, nom_qatorlari(PU["D"][n]) if PU["D"].get(n) else None) for n in YETTI}
check("U3 korxona nomi qatorlari soni C = D (logotipsiz bir qatorda bo'lsa — logotip yonida ham bir qatorda)",
      all(a is not None and a == b and a >= 1 for a, b in _nq.values()) and _nq.get("yuk_xati") == (1, 1), _nq)
GOLD_RGB = (0.788, 0.647, 0.353)


def oltin_chiziq(b, quti):
    try:
        with pdfplumber.open(io.BytesIO(b)) as p:
            pg = p.pages[0]
            ch = [x for x in pg.lines + pg.rects if isinstance(x.get("stroking_color"), (tuple, list)) and len(x["stroking_color"]) == 3
                  and all(abs(a - c) < 0.01 for a, c in zip(x["stroking_color"], GOLD_RGB)) and abs(x["top"] - quti[3]) < 3]
            return (round(min(x["x0"] for x in ch), 1), round(max(x["x1"] for x in ch), 1)) if ch else None
    except Exception:                      # noqa: BLE001
        return None


_qc = (_gu.get("moliya_oylik") or (None, None))[0]
_oc = oltin_chiziq(PU["C"]["moliya_oylik"], _qc["quti"]) if _qc and PU["C"].get("moliya_oylik") else None
check("U4 oylik hisobot (logotipli): sarlavha ostidagi oltin chiziq butun eniga — logotip katagi ostidan ham (review241 L1)",
      _oc and _qc and abs(_oc[0] - _qc["quti"][0]) <= 0.6 and abs(_oc[1] - _qc["quti"][1]) <= 0.6, (_oc, (_qc or {}).get("quti")))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. 16 bitli kulrang logotip (review241 M2)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_g16 = Image.new("I;16", (400, 200))
# qiymatlar 20 000 … 59 999 (hammasi > 255): 8 bitga to'g'ri o'tkazilmasa (kesilsa) — butunlay OQ; to'g'ri (÷ 256) — 78 … 234
_g16.putdata([20_000 + ((x * 100) + (y * 50)) % 40_000 for y in range(200) for x in range(400)])
_bg = io.BytesIO()
_g16.save(_bg, "PNG")
_rg = req(CA, "post", "/api/settings/company/logo", files={"file": ("kulrang16.png", _bg.getvalue(), "image/png")})
s = SessionLocal()
try:
    _lyg = s.execute(text("SELECT logo_path FROM companies WHERE id = :i"), {"i": KX["A"]["id"]}).scalar()
finally:
    s.close()
try:
    _mg = Image.open(os.path.join(ROOT, _lyg or "x")).mode
except Exception:                          # noqa: BLE001
    _mg = None


def _ekstrema(b):
    try:
        for pg_ in PdfReader(io.BytesIO(b)).pages:
            for im in pg_.images:
                return im.image.convert("L").getextrema()
    except Exception:                      # noqa: BLE001
        return None
    return None


_eg = {n: _ekstrema(req(CA, "get", KX["A"]["URL"][n][0]).content) for n in ("yuk_xati", "buyurtma_hisobi")}
check("G1 16 bitli kulrang PNG (400 × 200): yuklash 200, diskda 8 bitli («L»); yuk xati va «Buyurtma hisobi» da rasm OQ quti emas "
      "(eng qora piksel < 100)", _rg.status_code == 200 and _mg == "L" and all(e and e[0] < 100 for e in _eg.values()), (_rg.status_code, _mg, _eg))

# eski (zip 241 dan oldin yuklangan) 16 bitli kulrang fayl — diskda o'zgarmagan holda: PDF ga 8 bitli nusxa chiziladi
try:
    with open(os.path.join(ROOT, _lyg or "x"), "wb") as f:
        f.write(_bg.getvalue())
    _mg2 = Image.open(os.path.join(ROOT, _lyg or "x")).mode
except Exception:                          # noqa: BLE001
    _mg2 = None
_eg2 = {n: _ekstrema(req(CA, "get", KX["A"]["URL"][n][0]).content) for n in ("yuk_xati", "buyurtma_hisobi")}
check("G2 diskdagi ESKI 16 bitli kulrang logotip («I;16»): yuk xati va «Buyurtma hisobi» da rasm OQ quti emas (eng qora piksel < 100)",
      _mg2 == "I;16" and all(e and e[0] < 100 for e in _eg2.values()), (_mg2, _eg2))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Logotip almashtirilayotganda PDF lar (review241 M1)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_R1, _R1M = rasm_bayt(800, 400, (200, 40, 40))
_R2, _R2M = rasm_bayt(900, 300, (40, 160, 60))
_tugadi = threading.Event()


_CY = kirish(KX["A"]["login"], KX["A"]["parol"])          # almashtiruvchi ip — o'z mijozi (sessiyasi) bilan
_yuklashlar = [0]


def _almashtir():
    i = 0
    while _CY is not None and not _tugadi.is_set() and i < 400:
        _r = req(_CY, "post", "/api/settings/company/logo", files={"file": ("r.png", _R1 if i % 2 == 0 else _R2, "image/png")})
        _yuklashlar[0] += 1 if _r.status_code == 200 else 0
        i += 1


_rq = [imzo(Image.open(io.BytesIO(_R1))), imzo(Image.open(io.BytesIO(_R2)))]
req(CA, "post", "/api/settings/company/logo", files={"file": ("r.png", _R1, "image/png")})
_th = threading.Thread(target=_almashtir, daemon=True)
_th.start()
_rx = []
for _i in range(12):
    for _n in ("yuk_xati", "hisob_kitob", "moliya_oylik", "buyurtma_hisobi"):
        url, par = KX["A"]["URL"][_n]
        _r = req(CA, "get", url, params=par)
        _im = pdf_rasmlari(_r.content) if _r.status_code == 200 else None
        if _r.status_code != 200 or not _im or not all(bir_xil(x, _rq[0]) or bir_xil(x, _rq[1]) for x in _im):
            _rx.append((_n, _r.status_code, [x[:2] for x in (_im or [])]))
_tugadi.set()
_th.join(timeout=60)
check("R1 logotip ketma-ket almashtirilayotganda 48 PDF (yuk xati, hisob-kitob, oylik, «Buyurtma hisobi») — hammasi 200, rasm — eski yoki "
      "yangi logotip (yarim yozilgan fayl o'qilmaydi); shu orada ≥ 10 marta almashtirildi", _CY is not None and not _rx
      and _yuklashlar[0] >= 10, (_yuklashlar[0], _rx[:6]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. Brauzer (HAQIQIY Chromium)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
    import uvicorn
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    port = so.getsockname()[1]
    so.close()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    BU = f"http://127.0.0.1:{port}"
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        try:
            pg = br.new_page(viewport={"width": 1440, "height": 900})
            pg.goto(BU + "/login", wait_until="networkidle")
            _j1 = pg.evaluate("""() => { const p = document.querySelector('.brand-plita'); const i = p ? p.querySelector('img') : null;
                const r = i ? i.getBoundingClientRect() : null; const f = document.querySelector('link[rel=icon]');
                const m = document.querySelector('.mobil-brend');
                return {sarlavha: document.title, tabiiy: i ? i.naturalWidth : 0, eni: r ? Math.round(r.width) : 0, boyi: r ? Math.round(r.height) : 0,
                        fon: p ? getComputedStyle(p).backgroundColor : null, favicon: f ? f.href : null,
                        mobil: m ? getComputedStyle(m).display : null, matn: document.body.innerText}; }""")
            _fv = req(AN, "get", re.sub(r"^https?://[^/]+", "", _j1.get("favicon") or "/x"))
            check("J1 kirish oynasi (1440): «Kirish — epserp»; oq plitada logotip ko'rinadi (yuklangan, bo'yi 40 px, eni ≈ 158); telefon "
                  "logotipi yashirin; belgi (favicon) — 200 SVG; sahifa matnida «Penodecor» yo'q",
                  _j1["sarlavha"] == "Kirish — epserp" and _j1["tabiiy"] > 0 and _j1["boyi"] == 40 and 150 <= _j1["eni"] <= 166
                  and _j1["fon"] == "rgb(255, 255, 255)" and _j1["mobil"] == "none" and _fv.status_code == 200
                  and "image/svg+xml" in _fv.headers.get("content-type", "") and "penodecor" not in _j1["matn"].lower(),
                  {k: v for k, v in _j1.items() if k != "matn"})
            pg.set_viewport_size({"width": 390, "height": 844})
            pg.wait_for_timeout(200)
            _j2 = pg.evaluate("""() => { const m = document.querySelector('.mobil-brend'); const i = m ? m.querySelector('img') : null;
                const r = i ? i.getBoundingClientRect() : null;
                return {mobil: m ? getComputedStyle(m).display : null, tabiiy: i ? i.naturalWidth : 0, boyi: r ? Math.round(r.height) : 0,
                        top: r ? Math.round(r.top) : -1, panel: getComputedStyle(document.querySelector('.side')).display}; }""")
            check("J2 telefonda (390): chap panel yashirin, tepada epserp logotipi ko'rinadi (yuklangan, bo'yi 34 px, ekran ichida)",
                  _j2["mobil"] == "flex" and _j2["tabiiy"] > 0 and _j2["boyi"] == 34 and 0 <= _j2["top"] < 844 and _j2["panel"] == "none", _j2)
            pg.goto(BU + "/hodim/login", wait_until="networkidle")
            _j3 = pg.evaluate("""() => { const i = document.querySelector('.h-logo img'); const r = i ? i.getBoundingClientRect() : null;
                return {sarlavha: document.title, tabiiy: i ? i.naturalWidth : 0, boyi: r ? Math.round(r.height) : 0,
                        matn: document.body.innerText}; }""")
            check("J3 hodim kirishi (390): «Hodim kirishi — epserp», logotip ko'rinadi (bo'yi 36 px), matnda «Penodecor» yo'q",
                  _j3["sarlavha"] == "Hodim kirishi — epserp" and _j3["tabiiy"] > 0 and _j3["boyi"] == 36
                  and "penodecor" not in _j3["matn"].lower(), {k: v for k, v in _j3.items() if k != "matn"})
            _past = {}
            for (_w, _h, _q) in ((844, 390, "/login"), (844, 390, "/login?b=1"), (320, 568, "/login?b=1"), (667, 375, "/login")):
                pg.set_viewport_size({"width": _w, "height": _h})
                pg.goto(BU + _q, wait_until="networkidle")
                _past[f"{_w}x{_h}{_q[6:]}"] = pg.evaluate("""() => { const m = document.querySelector('.main'); m.scrollTop = 0;
                    const i = document.querySelector('.mobil-brend img') || document.querySelector('.mobil-brend');
                    const r = i ? i.getBoundingClientRect() : {top: -9999};
                    const b = document.querySelector('.btn-submit'); m.scrollTop = m.scrollHeight; const rb = b.getBoundingClientRect();
                    m.scrollTop = 0;
                    return {logo_top: Math.round(r.top), tugma_past: Math.round(rb.bottom), vh: innerHeight,
                            blok: !!document.getElementById('blokXabari')}; }""")
            check("J4 past ekranda (telefon yotiq 844 × 390, 667 × 375; 320 × 568 — blok xabari bilan ham): logotip tepasi ko'rinadi (≥ 0), "
                  "pastga aylantirilsa «Kirish» tugmasi ekranda (review241 L3; ilgari tepasi kesilib qolardi)",
                  len(_past) == 4 and all(v["logo_top"] >= 0 and v["tugma_past"] <= v["vh"] for v in _past.values()), _past)
        finally:
            br.close()
    server.should_exit = True
except Exception as _e:                    # noqa: BLE001
    check("J! brauzer bo'limi", False, f"{type(_e).__name__}: {_e}")

# tozalash: test yozgan logotip fayllari (FAQAT shu jarayon korxonalariniki — parallel nusxalarniki qoladi)
for _f in (set(os.listdir(UPL)) if os.path.isdir(UPL) else set()) - _BOSH:
    if re.fullmatch(rf"company_({KX['A']['id']}|{KX['B']['id']})\.(png|jpg|webp)", _f):
        try:
            os.remove(os.path.join(UPL, _f))
        except OSError:
            pass

if PG_URL:                                          # review241 L5: jarayonga xos PG bazasi — oxirida o'chiriladi
    try:
        from database import engine as _eng241
        _eng241.dispose()
        _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
