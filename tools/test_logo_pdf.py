#!/usr/bin/env python3
"""
test_logo_pdf.py — kech129 (zip 153): korxona logotipi «Buyurtma hisobi» va «Taklif» PDF larida — o'z NISBATI va YO'NALISHI bilan;
o'qib bo'lmaydigan logotip qabul qilinmaydi va PDF ni yiqitmaydi.

NIMA UCHUN KERAK (O'LCHANGAN — kech129, egasi yangi logotip yuklamoqchi, 08.10)
  1) `pdf_service.generate_nakladnoy` logotipni QAT'IY 32 × 18 mm chizardi (standart logotip nisbati 1,78 uchun yozilgan): kvadrat
     logotip (400 × 400) PDF da 1,78 marta cho'zilgan, tik logotip (300 × 600) — 3,6 marta. Taklif PDF i — o'sha shablon.
  2) EXIF yo'nalishli JPEG (telefonda olingan rasm — 90° burilgan): brauzer (chap panel) to'g'ri ko'rsatadi, ReportLab EXIF ni
     hisobga OLMAYDI — PDF da logotip yonboshlab chiqardi.
  3) Imzosi to'g'ri, ichi buzilgan PNG (yarim yuklangan fayl) — yuklash 200 berardi (zip 152 faqat boshidagi imzoni tekshiradi),
     keyin shu korxonaning HAR «Buyurtma hisobi» va «Taklif» PDF i 500 («PDF xato»).
TALAB (har biri o'lchanadi):
  S  statik: `pdf_service._logo_olcham` bor; RLImage o'lchami undan; logotip yuklashda `_rasm_ochish` (to'liq o'qish) tekshiruvi;
  N  nisbat: kvadrat / tik / keng / WEBP logotip — PDF dagi rasm nisbati = fayl nisbati (±2 %), 32 × 18 mm qutiga sig'adi, bir
     tomoni qutiga teng; standart logotip (`static/logo_transparent.png`) — AYNAN 32 × 18 mm (o'zgarmagan); taklif PDF i ham;
  E  EXIF: 600 × 200, yo'nalish 6 — saqlangan fayl to'g'rilangan (200 × 600), PDF da tik (bo'yi > eni);
  B  buzilgan: imzoli, ichi buzilgan PNG — 400, fayl yozilmadi, korxona logotipi o'zgarmadi; diskdagi logotip buzilsa ham (eski
     yozuv) — «Buyurtma hisobi» va «Taklif» PDF lari 200, logotip o'rniga korxona NOMI.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 152) qarshi QULAMAYDI — yiqiladi (yangi nomlar `getattr`, HTTP istisno — 599).
Test o'zi yozgan logotip fayllarini oxirida o'chiradi.
ISHLATISH: python3 tools/test_logo_pdf.py
"""
import os
import io
import sys
import glob
import tempfile
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "logo_pdf_test"
_DB = os.path.join(tempfile.gettempdir(), "logo_pdf_test.db")
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
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import pdf_service                             # noqa: E402

from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, Project, Inventory    # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from PIL import Image                              # noqa: E402
import pdfplumber                                  # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF] " if os.environ.get("TENANT_FILTER") else "")
OK = FAIL = 0
FAILED = []
MM = 72.0 / 25.4                                   # 1 mm — PDF nuqtalarida


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


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


def rasm(w, h, fmt="PNG", exif_yonalish=None):
    mode = "RGB" if fmt == "JPEG" else "RGBA"
    im = Image.new(mode, (w, h), (20, 110, 190) if mode == "RGB" else (20, 110, 190, 255))
    for x in range(0, w, 7):                         # bir xil rang bo'lmasin (siqilganda ham rasm)
        im.putpixel((x, (x * 3) % h), (240, 200, 20) if mode == "RGB" else (240, 200, 20, 255))
    b = io.BytesIO()
    if exif_yonalish:
        ex = Image.Exif()
        ex[0x0112] = exif_yonalish
        im.save(b, fmt, exif=ex.tobytes())
    else:
        im.save(b, fmt)
    return b.getvalue()


def pdf_rasmlari(baytlar):
    """PDF birinchi sahifasidagi rasmlar: [(eni_mm, boyi_mm)]; o'qib bo'lmasa — None."""
    try:
        with pdfplumber.open(io.BytesIO(baytlar)) as p:
            return [(round(i["width"] / MM, 2), round(i["height"] / MM, 2)) for i in p.pages[0].images]
    except Exception:                      # noqa: BLE001
        return None


def pdf_matni(baytlar):
    try:
        with pdfplumber.open(io.BytesIO(baytlar)) as p:
            return p.pages[0].extract_text() or ""
    except Exception:                      # noqa: BLE001
        return ""


UPL_LOGO = os.path.join(ROOT, "static", "uploads", "logos")
_BOSH_LOGO = set(os.listdir(UPL_LOGO)) if os.path.isdir(UPL_LOGO) else set()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: korxona 2 «LG Logo Dekor» — admin, loyiha, penoplast, buyurtma, taklif
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
KN = "LG Logo Dekor"
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name=KN, slogan="Fasad", address="Namangan", phone="+998 90 000 00 02"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "lg_admin", "Parol123!", UserRole.ADMIN, "LG admin", company_id=2)
PRJ = Project(company_id=2, client_name="LG Mijoz", project_name="LG loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=2, item_name="LG Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
s.add_all([PRJ, PENO])
s.commit()
ID = {"PRJ": PRJ.id, "PENO": PENO.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_rl = req(C, "post", "/login", data={"username": "lg_admin", "password": "Parol123!"}, follow_redirects=False)
if getattr(_rl, "status_code", 599) != 302:
    print("LOGIN BO'LMADI", getattr(_rl, "status_code", 599))
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_tana = {"order_type": "product", "items": [{"name": "LG karniz", "category": "profil", "width": 20, "thickness": 10, "length": 10,
                                             "quantity": 1, "unit_price": 1_000_000, "is_coated": False, "penoplast_id": ID["PENO"]}]}
_ro = req(C, "post", "/api/orders", params={"confirm_shortage": "true"}, json={**_tana, "project_id": ID["PRJ"]})
OID = (js(_ro) or {}).get("id") if _ro.status_code == 200 else None
_rt = req(C, "post", "/api/takliflar", json={"mijoz": "LG Taklif mijozi", "telefon": "+998 90 111 22 33", "buyurtma": _tana})
TID = ((js(_rt) or {}).get("taklif") or {}).get("id") if _rt.status_code == 200 else None
check("T0 fikstura: buyurtma va taklif yaratildi", OID and TID, (_ro.status_code, _ro.text[:200], _rt.status_code, _rt.text[:200]))


def logo_yukla(baytlar, nom, tur):
    return req(C, "post", "/api/settings/company/logo", files={"file": (nom, baytlar, tur)})


def logo_yoli():
    s_ = SessionLocal()
    try:
        return s_.execute(text("SELECT logo_path FROM companies WHERE id = 2")).scalar()
    finally:
        s_.close()


def pdf(tur="buyurtma"):
    url = f"/api/orders/{OID}/pdf" if tur == "buyurtma" else f"/api/takliflar/{TID}/pdf"
    r = req(C, "get", url)
    return r.status_code, (r.content if r.status_code == 200 else b"")


def nisbat_mos(olcham, w, h):
    """PDF dagi rasm (mm) nisbati fayl nisbatiga ±2 %, 32 × 18 qutiga sig'adi va bir tomoni qutiga teng."""
    if not olcham:
        return False
    e, b = olcham
    if not e or not b:
        return False
    return (abs((e / b) / (w / h) - 1) < 0.02 and e <= 32.05 and b <= 18.05
            and (abs(e - 32) < 0.06 or abs(b - 18) < 0.06))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ps = fayl("pdf_service.py")
check("S1 `pdf_service._logo_olcham` bor; RLImage o'lchami undan (qat'iy `width=32*mm, height=18*mm` YO'Q)",
      callable(getattr(pdf_service, "_logo_olcham", None)) and "RLImage(logo_path, width=32*mm, height=18*mm)" not in _ps
      and "RLImage(logo_path, width=_lo[0], height=_lo[1])" in _ps)
_mn = fayl("main.py")
_lg = _mn[_mn.find("async def api_upload_company_logo"):][:4000]
check("S2 logotip yuklashda to'liq o'qish (`_rasm_ochish`) — diskka yozishdan OLDIN; burilgan bo'lsa to'g'rilab saqlanadi",
      "_rasm_ochish(data" in _lg and _lg.find("_rasm_ochish(data") < _lg.find("with open(_os.path.join(papka, nom), \"wb\")")
      and "_burildi" in _lg)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("N. Nisbat — PDF dagi logotip")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_st, _pb = pdf()
_std = pdf_rasmlari(_pb)
check("N0 logotipsiz korxona — PDF 200, rasm yo'q, korxona nomi bor (o'zgarmagan)",
      _st == 200 and _std == [] and KN.upper() in pdf_matni(_pb).upper(), (_st, _std))
for _kod, (_w, _h, _fmt, _tur, _nom) in (("N1", (400, 400, "PNG", "image/png", "kvadrat")),
                                         ("N2", (300, 600, "PNG", "image/png", "tik")),
                                         ("N3", (1000, 200, "JPEG", "image/jpeg", "keng")),
                                         ("N4", (500, 500, "WEBP", "image/webp", "kvadrat WEBP"))):
    _r = logo_yukla(rasm(_w, _h, _fmt), f"logo.{_fmt.lower()}", _tur)
    _st, _pb = pdf()
    _ol = pdf_rasmlari(_pb)
    check(f"{_kod} {_nom} logotip ({_w} × {_h}) — yuklash 200, PDF 200, nisbat {_w / _h:.2f} saqlangan, 32 × 18 mm qutiga sig'adi",
          _r.status_code == 200 and _st == 200 and _ol and nisbat_mos(_ol[0], _w, _h), (_r.status_code, _st, _ol))
_r = logo_yukla(rasm(400, 400, "PNG"), "logo.png", "image/png")
_st, _pb = pdf("taklif")
_ol = pdf_rasmlari(_pb)
check("N5 taklif PDF i — kvadrat logotip nisbati saqlangan", _r.status_code == 200 and _st == 200 and _ol and nisbat_mos(_ol[0], 1, 1),
      (_r.status_code, _st, _ol))
# standart logotip (platforma egasi korxonasi o'rnatilgan logotipi) — AYNAN 32 × 18 mm
s = SessionLocal()
s.execute(text("UPDATE companies SET logo_path = 'static/logo_transparent.png' WHERE id = 2"))
s.commit()
s.close()
_st, _pb = pdf()
_ol = pdf_rasmlari(_pb)
check("N6 standart logotip (`static/logo_transparent.png`, 998 × 561) — AYNAN 32 × 18 mm (o'zgarmagan)",
      _st == 200 and _ol and abs(_ol[0][0] - 32) < 0.06 and abs(_ol[0][1] - 18) < 0.06, (_st, _ol))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. EXIF yo'nalishi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = logo_yukla(rasm(600, 200, "JPEG", exif_yonalish=6), "telefon.jpg", "image/jpeg")
_y = logo_yoli() or ""
try:
    with Image.open(os.path.join(ROOT, _y)) as _im:
        _sak = _im.size
        _sak_exif = int(_im.getexif().get(0x0112, 1) or 1)
except Exception as e:                     # noqa: BLE001
    _sak, _sak_exif = None, f"{type(e).__name__}"
check("E1 EXIF 6 (90° burilgan) JPEG — 200, saqlangan fayl to'g'rilangan: 200 × 600, EXIF yo'nalishi yo'q / 1",
      _r.status_code == 200 and _sak == (200, 600) and _sak_exif == 1, (_r.status_code, _y, _sak, _sak_exif))
_st, _pb = pdf()
_ol = pdf_rasmlari(_pb)
check("E2 PDF da logotip TIK (bo'yi > eni) va nisbati 1 : 3", _st == 200 and _ol and _ol[0][1] > _ol[0][0] and nisbat_mos(_ol[0], 200, 600),
      (_st, _ol))
_r = logo_yukla(rasm(400, 400, "JPEG"), "oddiy.jpg", "image/jpeg")
_y = logo_yoli() or ""
_bayt = open(os.path.join(ROOT, _y), "rb").read() if _y and os.path.exists(os.path.join(ROOT, _y)) else b""
check("E3 EXIF siz JPEG — ASLICHA saqlanadi (baytlar o'zgarmagan)", _r.status_code == 200 and _bayt == rasm(400, 400, "JPEG"),
      (_r.status_code, len(_bayt)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Buzilgan logotip")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_logo_oldin = logo_yoli()
_disk_oldin = set(os.listdir(UPL_LOGO)) if os.path.isdir(UPL_LOGO) else set()
_buzuq = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + os.urandom(64)
_r = logo_yukla(_buzuq, "buzuq.png", "image/png")
_fayl_bayt = open(os.path.join(ROOT, _logo_oldin), "rb").read() if _logo_oldin and os.path.exists(os.path.join(ROOT, _logo_oldin)) else b""
check("B1 imzoli, ichi buzilgan PNG — 400, korxona logotipi o'zgarmadi, diskdagi logotip fayli o'zgarmadi",
      _r.status_code == 400 and logo_yoli() == _logo_oldin and _fayl_bayt == rasm(400, 400, "JPEG")
      and (set(os.listdir(UPL_LOGO)) if os.path.isdir(UPL_LOGO) else set()) == _disk_oldin,
      (_r.status_code, _r.text[:150], logo_yoli(), _logo_oldin, len(_fayl_bayt)))
# eski yozuv: diskdagi logotip buzilgan (masalan zip 152 gacha yuklangan) — PDF yiqilmasin
_buzuq_yol = os.path.join(UPL_LOGO, "company_2.png")
os.makedirs(UPL_LOGO, exist_ok=True)
with open(_buzuq_yol, "wb") as _f:
    _f.write(_buzuq)
s = SessionLocal()
s.execute(text("UPDATE companies SET logo_path = 'static/uploads/logos/company_2.png' WHERE id = 2"))
s.commit()
s.close()
_st1, _pb1 = pdf()
_st2, _pb2 = pdf("taklif")
check("B2 diskdagi logotip buzilgan — «Buyurtma hisobi» PDF 200, rasm yo'q, korxona NOMI bor",
      _st1 == 200 and pdf_rasmlari(_pb1) == [] and KN.upper() in pdf_matni(_pb1).upper(), (_st1, pdf_rasmlari(_pb1)))
check("B3 diskdagi logotip buzilgan — «Taklif» PDF 200, korxona NOMI bor", _st2 == 200 and KN.upper() in pdf_matni(_pb2).upper(), _st2)

# tozalash: test yozgan logotip fayllari
for _p in glob.glob(os.path.join(UPL_LOGO, "company_2.*")):
    if os.path.basename(_p) not in _BOSH_LOGO:
        try:
            os.remove(_p)
        except OSError:
            pass

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
