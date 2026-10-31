#!/usr/bin/env python3
"""
test_dokon_rasm232.py — kech167 (zip 232 «Sayt katalogi rasmlari»; egasi QARORLARI «Onlayn do'kon rejasi» 30.10).

NIMA UCHUN KERAK
  Sayt katalogi modeliga rasm: telefondan / kompyuterdan, bir nechtasi birdan; birinchisi — asosiy, tartibi suriladi; rasm HECH
  QACHON qirqilmaydi; faqat JPG / PNG / WEBP — ichidan tekshiriladi va QAYTA saqlanadi; joylashuv (GPS) va boshqa yashirin
  ma'lumot o'chiriladi; telefon rasmi burilgan bo'lsa — to'g'rilanadi; katta rasm 1920 pikselgacha, ro'yxat uchun kichik nusxa;
  rasmlar hammaga ochiq ALOHIDA papkada (`/static/uploads/dokon/`), boshqa ERP fayllari — avvalgidek faqat kirgan xodimga.
  O'LCHANGAN (work/k232/probe232.py, asl kod 2a00a12): ERP'ning umumiy yuklash yo'li kichik, burilmagan rasmni ASLICHA saqlaydi —
  GPS, kamera, dastur, izoh, XMP, ICC faylda QOLADI; qayta yozilganda ham JPEG izohi o'tib ketadi; telefonning MPO fayli rad.
BO'LIMLAR
  S — statik: jadval, `_TENANT_REFS`, zaxira tartibi, marshrutlar, Pillow versiyasi qotirilgan.
  I — ishlov (`main.dokon_rasm_tayyorla`): metama'lumot TUZILMA bo'yicha yo'q (JPEG / PNG / WEBP / MPO), burilish, sRGB (P3
      profil), qirqilmaydi (nisbat), shaffof PNG, CMYK, 16 bit, palitra, harakatli / HEIC / rasm emas / buzilgan / juda katta /
      juda kichik / cho'zinchoq — rad, Pillow yo'q / tekshiruv o'tmasa — SAQLANMAYDI (yopiq holatda xato).
  A — API: belgi o'chiq — 404; Menejer — 403; boshqa korxona — 404; yuklash → fayllar, katalog, jurnal; OCHIQ manzil (login siz),
      sarlavhalar, yozuvsiz fayl / noto'g'ri nom — 404, boshqa papkalar himoyada; belgi o'chsa — 404; 10 ta chegara; tartib
      (to'g'ri / noto'g'ri ro'yxat); o'chirish (fayllar ham); model o'chirilsa — rasmlari ham; yozuv saqlanmasa — fayl qolmaydi;
      zaxira → tiklash.
  P — PG parallel: 9 ta rasmli modelga bir vaqtda ikki rasm — bittasi o'tadi (10 ta), fayl qolmaydi; tartib ↔ o'chirish — 500 yo'q.
  U — HAQIQIY brauzer: yuklash (2 ta), xato fayl sababi bilan, namuna (qirqilmaydi), ◀ ▶, surish, ko'rish oynasi, o'chirish,
      yuklash davomida narx katagiga yozilgan matn yo'qolmaydi, telefon (375 px), JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (U bo'limi faqat SQLite / TF1 da).
Asl kodga (zip 231d) qarshi QULAMAYDI — yiqiladi (marshrut / jadval / funksiya yo'q).
ISHLATISH: python3 tools/test_dokon_rasm232.py
"""
import os
import io
import re
import sys
import glob
import json
import time
import uuid
import struct
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "rasm232_test"
_T = tempfile.mkdtemp(prefix="t232_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't232.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
# kech167 (d240 dan keyin): sinov rasm papkasi — HAR yurishning o'z vaqtinchalik papkasida. Etalonda tf0 va tf1 BIR repoda PARALLEL
# yuradi: A23 dagi yetim fayl tozalash ikkinchi yurishning «eski, lekin yozuvi bor» faylini o'chirardi (O'LCHANGAN: parallel SQ + TF1 —
# U12 da 404), A11 dagi sobit nom va A16 dagi «papkadagi hamma fayl» ham bir-birini ko'rardi. Haqiqiy joy (Railway Volume ichida) — S6.
_ASL_PAPKA = crud.dokon_rasm_papkasi() if hasattr(crud, "dokon_rasm_papkasi") else None
DOKON_DISK = os.path.join(_T, "uploads", "dokon")
if _ASL_PAPKA is not None:
    crud.dokon_rasm_papkasi = lambda: DOKON_DISK
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, ActivityLog, ErrorLog   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
import PIL                                         # noqa: E402
from PIL import Image, ImageCms, PngImagePlugin    # noqa: E402

DokonModel = getattr(models, "DokonModel", None)
DokonRasm = getattr(models, "DokonRasm", None)     # asl kodda (zip 231d) yo'q — sinov qulamasin
TAYYORLA = getattr(main, "dokon_rasm_tayyorla", None)
XATO = getattr(main, "DokonRasmXato", ValueError)

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
YARATILGAN = []                                    # sinov yaratgan fayllar — oxirida o'chiriladi (tf0 / tf1 bir papkada)


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | " + (str(detail) if not callable(detail) else "")
    if callable(detail):
        try:
            detail = detail() if not cond else ""
        except Exception as e:             # noqa: BLE001
            detail = f"(tafsilot: {type(e).__name__}: {e})"
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
        return {}


def det(r):
    d = js(r)
    return str(d.get("detail") if isinstance(d, dict) else d)


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def xavfsiz(fn, std=None):
    try:
        return db_ishi(fn)
    except Exception:                      # noqa: BLE001
        return std


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Rasm yasovchilar
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAXFIY = (b"GPSMAXFIY232", b"SOFTMAXFIY232", b"KAMERAMAXFIY232", b"XMPMAXFIY232", b"IZOHMAXFIY232", b"MATNMAXFIY232")


def exif_gps(orient=1):
    ex = Image.Exif()
    ex[0x0112] = orient
    ex[0x010F] = "KAMERAMAXFIY232"
    ex[0x0131] = "SOFTMAXFIY232"
    ex.get_ifd(0x8825).update({1: "N", 2: (40.0, 47.0, 1.5), 3: "E", 4: (72.0, 20.0, 30.0), 0x1B: b"GPSMAXFIY232"})
    return ex


XMP = (b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
       b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/" '
       b'exif:GPSLatitude="40,47.0N" exif:UserComment="XMPMAXFIY232"/></rdf:RDF></x:xmpmeta><?xpacket end="w"?>')


def _s15(x):
    return struct.pack(">i", int(round(x * 65536)))


def p3_profil():
    """Kichik ICC v2 profili — Display P3 asosiy ranglari (D50), gamma 2,2. sRGB ga o'tkazish HAQIQATAN bajarilganini sinash uchun
    (sRGB profili bilan o'tkazish sezilmaydi)."""
    def teg_xyz(x, y, z):
        return b"XYZ " + b"\0" * 4 + _s15(x) + _s15(y) + _s15(z)
    curv = b"curv" + b"\0" * 4 + struct.pack(">I", 1) + struct.pack(">H", int(2.2 * 256)) + b"\0\0"
    matn = b"Sinov P3\0"
    desc = (b"desc" + b"\0" * 4 + struct.pack(">I", len(matn)) + matn + struct.pack(">II", 0, 0) + struct.pack(">HB", 0, 0)
            + b"\0" * 67)
    desc += b"\0" * ((4 - len(desc) % 4) % 4)
    teglar = [(b"desc", desc), (b"wtpt", teg_xyz(0.9642, 1.0, 0.8249)), (b"rXYZ", teg_xyz(0.5151, 0.2412, -0.0011)),
              (b"gXYZ", teg_xyz(0.2920, 0.6922, 0.0419)), (b"bXYZ", teg_xyz(0.1571, 0.0666, 0.7841)),
              (b"rTRC", curv), (b"gTRC", curv), (b"bTRC", curv)]
    jadval = struct.pack(">I", len(teglar))
    tana = b""
    joy = 128 + 4 + 12 * len(teglar)
    for nom, t in teglar:
        jadval += nom + struct.pack(">II", joy + len(tana), len(t))
        tana += t
    hajm = 128 + len(jadval) + len(tana)
    bosh = (struct.pack(">I", hajm) + b"\0" * 4 + struct.pack(">I", 0x02100000) + b"mntrRGB XYZ " + b"\0" * 12 + b"acsp"
            + b"\0" * 24 + struct.pack(">I", 0) + _s15(0.9642) + _s15(1.0) + _s15(0.8249) + b"\0" * 48)
    assert len(bosh) == 128
    return bosh + jadval + tana


SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
P3 = p3_profil()


def jpeg(w=1200, h=900, rang=(200, 120, 40), orient=1, icc=SRGB, meta=True, rejim="RGB", sifat=90):
    im = Image.new(rejim, (w, h), rang)
    buf = io.BytesIO()
    kw = {"quality": sifat}
    if meta:
        kw.update(exif=exif_gps(orient), comment=b"IZOHMAXFIY232", xmp=XMP)
    if icc:
        kw["icc_profile"] = icc
    im.save(buf, "JPEG", **kw)
    return buf.getvalue()


def ikki_rang(w, h, chap, ong, rejim="RGB"):
    im = Image.new(rejim, (w, h), chap)
    im.paste(Image.new(rejim, (w // 2, h), ong), (w // 2, 0))
    return im


def png(im, meta=True, icc=SRGB):
    buf = io.BytesIO()
    kw = {}
    if meta:
        pi = PngImagePlugin.PngInfo()
        pi.add_text("Comment", "MATNMAXFIY232")
        pi.add_itxt("XML:com.adobe.xmp", XMP.decode())
        kw.update(pnginfo=pi, exif=exif_gps())
    if icc:
        kw["icc_profile"] = icc
    im.save(buf, "PNG", **kw)
    return buf.getvalue()


def webp(im, meta=True):
    buf = io.BytesIO()
    kw = {"quality": 90}
    if meta:
        kw.update(exif=exif_gps(), xmp=XMP, icc_profile=SRGB)
    im.save(buf, "WEBP", **kw)
    return buf.getvalue()


def maxfiy_qoldi(b):
    return [m.decode() for m in MAXFIY if m in b] + (["Exif"] if b"Exif\x00\x00" in b else []) + \
        (["xmp"] if b"ns.adobe.com/xap" in b or b"x:xmpmeta" in b else []) + (["ICC"] if b"acsp" in b else [])


def jpeg_segmentlar(b):
    i, s = 2, []
    while i + 4 <= len(b) and b[i] == 0xFF:
        mk = b[i + 1]
        if mk == 0xDA:
            break
        ln = int.from_bytes(b[i + 2:i + 4], "big")
        s.append(mk)
        i += 2 + ln
    return s


def png_bolaklar(b):
    i, s = 8, []
    while i + 12 <= len(b):
        ln = int.from_bytes(b[i:i + 4], "big")
        s.append(b[i + 4:i + 8].decode("latin-1"))
        i += 12 + ln
    return s


def ochil(b):
    o = Image.open(io.BytesIO(b))
    o.load()
    return o


def xv(fn, std=None):
    """Mutatsiya / asl kodda kutilmagan natija sinovni qulatmasin."""
    try:
        return fn()
    except Exception:                      # noqa: BLE001
        return std


def tayyorla(data, nom="rasm.jpg"):
    """(natija, xato matni)."""
    if TAYYORLA is None:
        return None, "KUTILMAGAN: funksiya yo'q"
    try:
        return TAYYORLA(data, nom), None
    except XATO as e:
        return None, str(e)
    except Exception as e:                 # noqa: BLE001
        return None, f"KUTILMAGAN {type(e).__name__}: {e}"


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: korxona 1 — platforma egasi (sayt katalogi yoqiladi), korxona 2 — mijoz
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T232 B mijoz korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t232_admin", PAROL, UserRole.ADMIN, "T232 Admin", company_id=1)
    auth.create_user(s, "t232_plat", PAROL, UserRole.ADMIN, "T232 Platforma", company_id=1)
    auth.create_user(s, "t232_men", PAROL, UserRole.MANAGER, "T232 Menejer", company_id=1)
    auth.create_user(s, "t232_b", PAROL, UserRole.ADMIN, "T232 B Admin", company_id=2)
_pu = s.query(User).filter(User.username == "t232_plat").first()
_pu.is_platform_admin = True
s.commit()
s.close()
main._send_telegram = lambda msg, *a, **k: True


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t232_admin")
CP = mijoz("t232_plat")
CM = mijoz("t232_men")
CB = mijoz("t232_b")
CX = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)     # login SIZ (sayt mehmoni)
API = "/api/sayt-katalogi"


def jurnal(entity, cid=1):
    return db_ishi(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == entity,
                                                       ActivityLog.company_id == cid).count())


def katalog(c=CA):
    d = js(c.get(API))
    d = d if isinstance(d, dict) else {}
    return {"bolimlar": [], "modellar": [], "detallar": [], "rasmlar": [], **d}


def rasmlar(model_id, c=CA):
    return [r for r in katalog(c)["rasmlar"] if r.get("model_id") == model_id]


def yukla(model_id, data, nom="rasm.jpg", c=CA):
    r = c.post(API + f"/modellar/{model_id}/rasmlar", files={"fayl": (nom, data, "image/jpeg")})
    d = js(r)
    if isinstance(d, dict):
        YARATILGAN.extend(u for u in (d.get("url"), d.get("kichik")) if u)
    return r


def disk(url):
    if not url or "static/" not in url:
        return os.path.join(_T, "yoq", "fayl")
    _rel = url.lstrip("/").split("static/", 1)[1]
    if _ASL_PAPKA is not None and _rel.startswith("uploads/dokon/"):
        return os.path.join(DOKON_DISK, _rel[len("uploads/dokon/"):])
    return os.path.join(ROOT, "static", _rel)


def dokon_glob(naqsh):
    return glob.glob(os.path.join(os.path.dirname(disk("/static/uploads/dokon/x")), naqsh))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("S1 `dokon_rasmlar` jadvali — fayl / kichik yagona, model va korxona majburiy",
      DokonRasm is not None and DokonRasm.__tablename__ == "dokon_rasmlar"
      and DokonRasm.__table__.c.fayl.unique and DokonRasm.__table__.c.kichik.unique
      and not DokonRasm.__table__.c.model_id.nullable and not DokonRasm.__table__.c.company_id.nullable)
check("S2 `_TENANT_REFS`: rasm → model", ("model_id", "DokonModel") in getattr(models, "_TENANT_REFS", {}).get("DokonRasm", []))
_tart = [c.__name__ for c in crud._reset_table_order()]
check("S3 zaxira / tiklash tartibi: rasm modeldan OLDIN", "DokonRasm" in _tart and _tart.index("DokonRasm") < _tart.index("DokonModel"),
      _tart[-6:])
_yol = {(m, r.path) for r in main.app.routes for m in (getattr(r, "methods", None) or ())}
_kerak = {("POST", API + "/modellar/{model_id}/rasmlar"), ("PUT", API + "/modellar/{model_id}/rasmlar"),
          ("DELETE", API + "/rasmlar/{rasm_id}")}
check("S4 3 ta yangi marshrut", _kerak <= _yol, sorted(_kerak - _yol))
_req = open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read().lower()
_pin = re.search(r"^pillow==([0-9.]+)$", _req, re.M)
check("S5 Pillow requirements da QOTIRILGAN va sinov o'sha versiyada", bool(_pin) and _pin.group(1) == PIL.__version__,
      (_pin.group(1) if _pin else None, PIL.__version__))
check("S6 sayt rasmlari papkasi — umumiy `static` ichida `uploads/dokon` (Railway Volume `/app/static/uploads` ichida — qayta yuklashda "
      "yo'qolmaydi)", _ASL_PAPKA is not None
      and os.path.realpath(_ASL_PAPKA) == os.path.realpath(os.path.join(main.static_dir, "uploads", "dokon")),
      (_ASL_PAPKA, getattr(main, "static_dir", None)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("I. Ishlov (dokon_rasm_tayyorla)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_m = jpeg(2400, 1800)
_n, _x = tayyorla(_m)
check("I1 JPEG 2400×1800 + GPS / kamera / dastur / XMP / izoh / ICC → katta 1920×1440, kichik 640×480, metama'lumot YO'Q",
      lambda: (_n and (_n["eni"], _n["boyi"]) == (1920, 1440) and _n["ext"] == ".jpg" and ochil(_n["kichik"]).size == (640, 480)
      and not maxfiy_qoldi(_n["katta"]) and not maxfiy_qoldi(_n["kichik"])
      and not [m for m in jpeg_segmentlar(_n["katta"]) if 0xE1 <= m <= 0xEF or m == 0xFE]
      and not [m for m in jpeg_segmentlar(_n["kichik"]) if 0xE1 <= m <= 0xEF or m == 0xFE]
      and len(ochil(_n["katta"]).getexif()) == 0), lambda: ((_x, _n and maxfiy_qoldi(_n["katta"]), _n and jpeg_segmentlar(_n["katta"]))))
_m = jpeg(1000, 750)
_n, _x = tayyorla(_m)
check("I2 KICHIK burilmagan JPEG (1000×750) ham QAYTA yoziladi (asl kod ASLICHA saqlar edi) — GPS va hammasi o'chdi, o'lcham o'sha",
      lambda: (_n and _n["katta"] != _m and (_n["eni"], _n["boyi"]) == (1000, 750) and not maxfiy_qoldi(_n["katta"])),
      lambda: ((_x, _n and maxfiy_qoldi(_n["katta"]))))
_im = ikki_rang(1200, 800, (220, 20, 20), (20, 20, 220))
_buf = io.BytesIO()
_im.save(_buf, "JPEG", quality=95, exif=exif_gps(6))
_n, _x = tayyorla(_buf.getvalue())
_o = xv(lambda: ochil(_n["katta"]))
check("I3 telefon burilishi (EXIF 6) — to'g'rilandi: 800×1200, chap yarmi (qizil) — tepada, o'ng (ko'k) — pastda",
      lambda: (_o and _o.size == (800, 1200) and _o.getpixel((400, 250))[0] > 180 and _o.getpixel((400, 950))[2] > 180),
      lambda: ((_x, _o and _o.size, _o and (_o.getpixel((400, 250)), _o.getpixel((400, 950))))))
_n, _x = tayyorla(jpeg(1600, 1200, rang=(180, 100, 60), icc=P3))
_kut = ImageCms.profileToProfile(Image.new("RGB", (4, 4), (180, 100, 60)), ImageCms.ImageCmsProfile(io.BytesIO(P3)),
                                 ImageCms.createProfile("sRGB"), outputMode="RGB").getpixel((1, 1))
_px = xv(lambda: ochil(_n["katta"]).getpixel((800, 600)))
check("I4 rangli profil (P3) — sRGB ga O'TKAZILDI (profil o'zi yozilmadi): piksel sRGB qiymatiga mos, asl qiymatdan farqli",
      lambda: (_px and all(abs(a - b) <= 3 for a, b in zip(_px, _kut)) and max(abs(a - b) for a, b in zip(_px, (180, 100, 60))) >= 6
      and "ICC" not in maxfiy_qoldi(_n["katta"])), lambda: ((_x, _px, _kut)))
_im = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
_im.paste(Image.new("RGBA", (500, 500), (30, 160, 60, 255)), (250, 250))
_n, _x = tayyorla(png(_im), "logo.png")
_o = xv(lambda: ochil(_n["katta"]))
check("I5 shaffof PNG → PNG (shaffoflik saqlandi), bo'laklar faqat IHDR / IDAT / IEND, matn / EXIF / XMP / ICC yo'q",
      lambda: (_o and _n["ext"] == ".png" and _o.mode == "RGBA" and _o.getpixel((10, 10))[3] == 0 and _o.getpixel((500, 500))[3] == 255
      and set(png_bolaklar(_n["katta"])) <= {"IHDR", "PLTE", "tRNS", "IDAT", "IEND"} and not maxfiy_qoldi(_n["katta"])
      and set(png_bolaklar(_n["kichik"])) <= {"IHDR", "PLTE", "tRNS", "IDAT", "IEND"}),
      lambda: ((_x, _n and png_bolaklar(_n["katta"]), _n and maxfiy_qoldi(_n["katta"]))))
_n, _x = tayyorla(png(Image.new("RGBA", (900, 600), (40, 50, 60, 255))), "toliq.png")
check("I6 shaffof joyi yo'q PNG (RGBA, alfa hammasi 255) → JPEG", lambda: (_n and _n["ext"] == ".jpg" and not maxfiy_qoldi(_n["katta"])), lambda: (_x))
_n, _x = tayyorla(webp(Image.new("RGB", (1300, 900), (120, 130, 140))), "telefon.webp")
check("I7 WEBP (EXIF / XMP / ICC bilan) → JPEG, metama'lumot yo'q", lambda: (_n and _n["ext"] == ".jpg" and not maxfiy_qoldi(_n["katta"])
      and (_n["eni"], _n["boyi"]) == (1300, 900)), lambda: ((_x, _n and maxfiy_qoldi(_n["katta"]))))
_im = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
_im.paste(Image.new("RGBA", (400, 400), (200, 0, 0, 200)), (200, 200))
_n, _x = tayyorla(webp(_im, meta=False), "shaffof.webp")
check("I7b shaffof WEBP → PNG (shaffoflik saqlandi)", lambda: (_n and _n["ext"] == ".png" and ochil(_n["katta"]).getpixel((5, 5))[3] == 0), lambda: (_x))
_a = ikki_rang(2000, 1500, (10, 200, 10), (200, 10, 10))
_buf = io.BytesIO()
_a.save(_buf, "MPO", save_all=True, append_images=[Image.new("RGB", (500, 375), (0, 0, 0))], exif=exif_gps())
_n, _x = tayyorla(_buf.getvalue(), "IMG_PORTRET.jpg")
_o = xv(lambda: ochil(_n["katta"]))
check("I8 MPO (telefonning ko'p rasmli JPEG i) — qabul: ASOSIY rasm (1920×1440, chap yashil), GPS yo'q (asl kod rad etardi)",
      lambda: (_o and _o.size == (1920, 1440) and _o.getpixel((100, 700))[1] > 150 and not maxfiy_qoldi(_n["katta"])), lambda: ((_x, _o and _o.size)))
_fr = [Image.new("RGB", (600, 600), c) for c in ((255, 0, 0), (0, 255, 0))]
_buf = io.BytesIO()
_fr[0].save(_buf, "WEBP", save_all=True, append_images=_fr[1:], duration=100)
_n1, _x1 = tayyorla(_buf.getvalue(), "harakat.webp")
_buf = io.BytesIO()
_fr[0].save(_buf, "PNG", save_all=True, append_images=_fr[1:], duration=100)
_n2, _x2 = tayyorla(_buf.getvalue(), "harakat.png")
check("I9 harakatli WEBP va APNG — rad («Harakatli»)", lambda: (_n1 is None and _n2 is None and "Harakatli" in (_x1 or "")
      and "Harakatli" in (_x2 or "")), lambda: ((_x1, _x2)))
_n1, _x1 = tayyorla(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 200, "IMG_1.HEIC")
_n2, _x2 = tayyorla(jpeg(), "IMG_2.heic")
check("I10 HEIC (iPhone) — tushunarli xabar bilan rad (imzo bo'yicha ham, kengaytma bo'yicha ham)",
      lambda: (_n1 is None and _n2 is None and "HEIC" in (_x1 or "") and "HEIC" in (_x2 or "")), lambda: ((_x1, _x2)))
for _nm, _d, _f, _kutil in (("matn .jpg nomli", b"bu rasm emas, matn", "soxta.jpg", "rasm emas"),
                            ("bo'sh fayl", b"", "bosh.jpg", "bo'sh"),
                            ("buzilgan (yarmi kesilgan) JPEG", jpeg(1600, 1200, meta=False)[:4000], "kesik.jpg", "o'qib bo'lmadi"),
                            ("JPEG imzoli, ichi PNG emas — aralash", b"\xff\xd8\xff" + b"\x00" * 3000, "aralash.jpg", None),
                            ("25 MB dan katta", b"\xff\xd8\xff" + b"\x00" * (25 * 1024 * 1024), "katta.jpg", "25 MB")):
    _n, _x = tayyorla(_d, _f)
    check(f"I11 {_nm} — rad, tushunarli matn", lambda: (_n is None and _x and "KUTILMAGAN" not in _x and (_kutil is None or _kutil in _x)), lambda: (_x))
_buf = io.BytesIO()
Image.new("RGB", (5000, 5000), (1, 2, 3)).save(_buf, "PNG")
_n, _x = tayyorla(_buf.getvalue(), "katta.png")
_n1, _x1 = tayyorla(jpeg(1000, 800, meta=False), "rasm.jfif")
_n2, _x2 = tayyorla(png(Image.new("RGB", (900, 600), (9, 9, 9)), meta=False, icc=None), "rasm.gif")
_n3, _x3 = tayyorla(jpeg(1000, 800, meta=False), "rasm")
check("I11b tur ICHIDAN aniqlanadi (review232 №10): haqiqiy JPEG «.jfif» va kengaytmasiz — qabul, «.gif» nomli PNG — qabul (PNG)",
      lambda: (_n1 and _n3 and _n2 and _n2["ext"] == ".jpg" and _n1["ext"] == ".jpg"), lambda: ((_x1, _x2, _x3)))
check("I12 PNG 25 MP (fayli kichik — «bomba») — rad (xotira), o'lchami xabarda", lambda: (_n is None and "5000 × 5000" in (_x or "")), lambda: (_x))
_buf = io.BytesIO()
Image.new("RGB", (10000, 10000), (90, 80, 70)).save(_buf, "JPEG", quality=70)
_n, _x = tayyorla(_buf.getvalue(), "108mp.jpg")
_buf2 = io.BytesIO()
Image.new("RGB", (4500, 4000), (5, 5, 5)).save(_buf2, "PNG")
_n18, _x18 = tayyorla(_buf2.getvalue(), "18mp.png")
check("I12b JPEG 100 MP (telefonning eng katta rejimi) — qabul, 1920×1920 («draft» bilan)", lambda: (_n and (_n["eni"], _n["boyi"]) == (1920, 1920)), lambda: (_x))
_n1, _x1 = tayyorla(jpeg(450, 300, meta=False), "kichik.jpg")
_n2, _x2 = tayyorla(jpeg(1800, 200, meta=False), "chiziq.jpg")
_n3, _x3 = tayyorla(jpeg(1600, 200, meta=False), "8ga1.jpg")
check("I12c PNG 18 MP — rad (PNG / WEBP chegarasi 16 MP, review232 №1)", lambda: (_n18 is None and "16 megapiksel" in (_x18 or "")),
      lambda: (_x18))


def _sof2_soxta(w, h):
    """Kichik progressive JPEG, sarlavhada (SOF2) o'lchami soxta — review232 №1 «bomba» (701 bayt → +938 MB)."""
    b = io.BytesIO()
    Image.new("RGB", (16, 16), (1, 2, 3)).save(b, "JPEG", progressive=True, quality=50)
    b = bytearray(b.getvalue())
    i = b.find(b"\xff\xc2")
    b[i + 5:i + 7] = h.to_bytes(2, "big")
    b[i + 7:i + 9] = w.to_bytes(2, "big")
    return bytes(b)


_b1 = _sof2_soxta(10900, 10900)
_b2 = _sof2_soxta(10900, 10900)[:-2]
_buf = io.BytesIO()
Image.new("RGB", (6000, 6000), (90, 80, 70)).save(_buf, "JPEG", quality=60, progressive=True)
_b3 = _buf.getvalue()
_buf = io.BytesIO()
Image.new("CMYK", (6000, 5000), (10, 20, 30, 40)).save(_buf, "JPEG", quality=60)
_b4 = _buf.getvalue()
_buf = io.BytesIO()
Image.new("RGB", (5000, 5000), (90, 80, 70)).save(_buf, "JPEG", quality=60, progressive=True)
_b5 = _buf.getvalue()
_t0 = time.time()
_r1 = tayyorla(_b1, "soxta.jpg")
_r2 = tayyorla(_b2, "kesik.jpg")
_r3 = tayyorla(_b3, "prog36.jpg")
_r4 = tayyorla(_b4, "cmyk30.jpg")
_t1 = time.time() - _t0
_r5 = tayyorla(_b5, "prog25.jpg")
check("I21 progressive / CMYK JPEG xotira byudjeti (review232 №1): soxta sarlavhali 10900² (EOI bilan) — rad, EOI siz — «buzilgan», "
      "progressive 36 MP va CMYK 30 MP — rad (tez, dekodlanmaydi); progressive 25 MP — qabul",
      lambda: (_r1[0] is None and "progressive" in (_r1[1] or "") and _r2[0] is None and "buzilgan" in (_r2[1] or "")
               and _r3[0] is None and "progressive" in (_r3[1] or "") and _r4[0] is None and "CMYK" in (_r4[1] or "")
               and _t1 < 5 and _r5[0] is not None and (_r5[0]["eni"], _r5[0]["boyi"]) == (1920, 1920)),
      lambda: ((_r1[1], _r2[1], _r3[1], _r4[1], round(_t1, 2), _r5[1])))
_im3 = Image.new("RGB", (800, 600), (255, 0, 255))
_im3.paste(Image.new("RGB", (400, 300), (20, 120, 220)), (200, 150))
_im3.info["transparency"] = (255, 0, 255)
_buf = io.BytesIO()
_im3.save(_buf, "PNG", transparency=(255, 0, 255))
_n, _x = tayyorla(_buf.getvalue(), "kalit.png")
_o = xv(lambda: ochil(_n["katta"]))
check("I22 RGB PNG rang-kalit shaffofligi (tRNS) saqlanadi — PNG RGBA, kalit rangli joy shaffof (review232 №6)",
      lambda: (_n["ext"] == ".png" and _o.mode == "RGBA" and _o.getpixel((5, 5))[3] == 0 and _o.getpixel((400, 300))[3] == 255),
      lambda: ((_x, _o and _o.mode, _o and _o.getpixel((5, 5)))))
check("I13 juda kichik (450×300) va cho'zinchoq (9 : 1) — rad; 8 : 1 — qabul",
      lambda: (_n1 is None and "kichik" in (_x1 or "") and _n2 is None and "cho'zinchoq" in (_x2 or "") and _n3 is not None), lambda: ((_x1, _x2, _x3)))
_n, _x = tayyorla(jpeg(1200, 900, rang=(10, 80, 160, 30), rejim="CMYK", icc=None, meta=False), "cmyk.jpg")
check("I14 CMYK JPEG → RGB JPEG", lambda: (_n and ochil(_n["katta"]).mode == "RGB"), lambda: (_x))
_g = Image.new("I", (800, 600), 40000).convert("I;16")
_n, _x = tayyorla(png(_g, meta=False, icc=None), "16bit.png")
_o = xv(lambda: ochil(_n["katta"]))
check("I15 16 bitli kulrang PNG → 8 bit (oq bo'lib qolmadi: 40000/65535 ≈ 156)", lambda: (_o and abs(_o.convert("L").getpixel((5, 5)) - 156) <= 3),
      lambda: ((_x, _o and _o.mode, _o and _o.convert("L").getpixel((5, 5)))))
_p = Image.new("P", (700, 700), 0)
_p.putpalette([255, 255, 255, 200, 30, 30] + [0] * 762)
_p.paste(1, (100, 100, 600, 600))
_p.info["transparency"] = 0
_n, _x = tayyorla(png(_p, meta=False, icc=None), "palitra.png")
check("I16 palitrali PNG (shaffof rangi bilan) → PNG RGBA, shaffoflik saqlandi",
      lambda: (_n and _n["ext"] == ".png" and ochil(_n["katta"]).getpixel((10, 10))[3] == 0), lambda: (_x))
_n, _x = tayyorla(jpeg(3000, 1000, meta=False), "keng.jpg")
_n2, _x2 = tayyorla(jpeg(1000, 3000, meta=False), "tik.jpg")
check("I17 QIRQILMAYDI — nisbat saqlanadi: 3000×1000 → 1920×640 (kichik 640×213), 1000×3000 → 640×1920",
      lambda: (_n and (_n["eni"], _n["boyi"]) == (1920, 640) and ochil(_n["kichik"]).size == (640, 213)
      and _n2 and (_n2["eni"], _n2["boyi"]) == (640, 1920)), lambda: ((_x, _x2, _n and ochil(_n["kichik"]).size)))
_asl_pillow = main._pillow
main._pillow = lambda: (None, None)
_n, _x = tayyorla(jpeg())
main._pillow = _asl_pillow
check("I18 Pillow yo'q — rasm SAQLANMAYDI (asl kod ASLICHA saqlar edi)", lambda: (_n is None and "moduli" in (_x or "")), lambda: (_x))
_asl_yoz = getattr(main, "_dokon_yoz", None)
if _asl_yoz:
    main._dokon_yoz = lambda im, turi, sifat: (lambda b: b[:2] + b"\xff\xe1\x00\x0aExif\x00\x00MM" + b[2:])(_asl_yoz(im, turi, sifat))
_n, _x = tayyorla(jpeg())
if _asl_yoz:
    main._dokon_yoz = _asl_yoz
check("I19 yozilgan faylda metama'lumot qolsa (tekshiruv) — SAQLANMAYDI", lambda: (_n is None and "xavfsiz" in (_x or "")), lambda: (_x))
check("I20 tuzilma tekshiruvchisi: EXIF / izoh / ICC li JPEG va tEXt li PNG — rad, toza — qabul",
      lambda: (hasattr(main, "_dokon_rasm_metasiz") and not main._dokon_rasm_metasiz(jpeg(), "jpg")
      and main._dokon_rasm_metasiz(tayyorla(jpeg())[0]["katta"], "jpg")
      and not main._dokon_rasm_metasiz(png(Image.new("RGB", (600, 600)), icc=None), "png")
      and not main._dokon_rasm_metasiz(tayyorla(png(_im))[0]["katta"] + b"ortiqcha", "png")))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("A1 belgi o'chiq — yuklash / tartib / o'chirish — 404",
      lambda: (CA.post(API + "/modellar/1/rasmlar", files={"fayl": ("a.jpg", jpeg(), "image/jpeg")}).status_code == 404
      and CA.put(API + "/modellar/1/rasmlar", json={"tartib": []}).status_code == 404
      and CA.delete(API + "/rasmlar/1").status_code == 404))
_r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
_k = katalog()
_B = {b["nom"]: b["id"] for b in _k["bolimlar"]}
_r1 = CA.post(API + "/modellar", json={"bolim_id": _B.get("Karnizlar"), "kod": "K-232"})
_r2 = CA.post(API + "/modellar", json={"bolim_id": _B.get("Karnizlar"), "kod": "K-233"})
M1, M2 = js(_r1).get("id"), js(_r2).get("id")
check("A2 belgi yoqildi, ikki model; katalogda `rasmlar` (bo'sh) va `rasm_max` = 10",
      lambda: (_r.status_code == 200 and M1 and M2 and _k.get("rasmlar") == [] and _k.get("rasm_max") == 10), lambda: ((_r.text[:120], _k.get("rasm_max"))))
check("A3 Menejer — 403; mijoz korxona Admini — 404 (uning korxonasida o'chiq)",
      lambda: (CM.post(API + f"/modellar/{M1}/rasmlar", files={"fayl": ("a.jpg", jpeg(), "image/jpeg")}).status_code == 403
      and CB.post(API + f"/modellar/{M1}/rasmlar", files={"fayl": ("a.jpg", jpeg(), "image/jpeg")}).status_code == 404))
_j0 = jurnal("dokon_rasm")
_ra = yukla(M1, jpeg(2400, 1800, rang=(250, 0, 0)), "IMG_0001.JPG")
_rb = yukla(M1, png(_im), "shaffof.png")
_rc = yukla(M1, webp(Image.new("RGB", (1300, 900), (0, 0, 250))), "c.webp")
RA, RB, RC = js(_ra), js(_rb), js(_rc)
check("A4 uchta rasm yuklandi (JPEG / PNG / WEBP) — javobda url / kichik / o'lcham / tartib 1, 2, 3",
      lambda: ([x.status_code for x in (_ra, _rb, _rc)] == [200, 200, 200]
      and [RA.get("tartib"), RB.get("tartib"), RC.get("tartib")] == [1, 2, 3]
      and (RA.get("eni"), RA.get("boyi")) == (1920, 1440) and RB.get("turi") == "png" and RC.get("turi") == "jpeg"
      and re.fullmatch(r"/static/uploads/dokon/[0-9a-f]{32}\.jpg", RA.get("url") or "")
      and RA.get("kichik") == RA.get("url", "")[:-4] + "_k.jpg"), lambda: ((_ra.text[:200], _rb.text[:120], _rc.text[:120])))
check("A4b fayllar diskda (katta va kichik), diskdagi bayt — metama'lumotsiz, katalogda shu tartibda, jurnal +3",
      lambda: (all(os.path.isfile(disk(x.get(k))) for x in (RA, RB, RC) for k in ("url", "kichik"))
      and not maxfiy_qoldi(open(disk(RA["url"]), "rb").read())
      and [r["id"] for r in rasmlar(M1)] == [RA.get("id"), RB.get("id"), RC.get("id")] and jurnal("dokon_rasm") == _j0 + 3),
      lambda: ((jurnal("dokon_rasm"), _j0)))
_r = CX.get(RA.get("url", "/x"))
_rk = CX.get(RA.get("kichik", "/x"))
check("A5 OCHIQ manzil — login siz 200, image/jpeg, kesh «public, max-age=3600», nosniff, bayt diskdagi bilan AYNAN (katta va kichik)",
      lambda: (_r.status_code == 200 and _r.headers.get("content-type") == "image/jpeg"
      and _r.headers.get("cache-control", "") == "public, max-age=3600" and _r.headers.get("x-content-type-options") == "nosniff"
      and _r.content == open(disk(RA["url"]), "rb").read() and _rk.status_code == 200
      and ochil(_rk.content).size == (640, 480)), lambda: ((_r.status_code, dict(_r.headers))))
check("A5b PNG — image/png", lambda: (CX.get(RB.get("url", "/x")).headers.get("content-type") == "image/png"))
_yetim = f"/static/uploads/dokon/{uuid.uuid4().hex}.jpg"
os.makedirs(os.path.dirname(disk(_yetim)), exist_ok=True)
open(disk(_yetim), "wb").write(jpeg(meta=False))
YARATILGAN.append(_yetim)
_yomon = [_yetim, "/static/uploads/dokon/" + RA.get("url", "/x/y").rsplit("/", 1)[1].upper(),
          "/static/uploads/dokon/..%2Fdokon%2F" + RA.get("url", "/x/y").rsplit("/", 1)[1],
          "/static/uploads/dokon/" + RA.get("url", "/x/y.jpg").rsplit("/", 1)[1][:-4] + ".png",
          "/static/uploads/dokon/%2E/" + RA.get("url", "/x/y").rsplit("/", 1)[1], "/static/uploads/dokon/abc.jpg"]
_st = [CX.get(u, follow_redirects=False).status_code for u in _yomon]
check("A6 diskda bor, lekin yozuvi yo'q fayl, katta harfli / boshqa kengaytmali nom, «..», «%2E» — 404 (login siz)",
      lambda: (all(x == 404 for x in _st)), lambda: (_st))
_inv = "/static/uploads/inventory/" + uuid.uuid4().hex + ".jpg"
os.makedirs(os.path.dirname(disk(_inv)), exist_ok=True)
open(disk(_inv), "wb").write(jpeg(meta=False))
YARATILGAN.append(_inv)
_r = CX.get(_inv, follow_redirects=False)
check("A7 boshqa papka (ombor rasmi) avvalgidek HIMOYADA — login siz kirish sahifasiga, kirgan admin — 404 (yozuvi yo'q)",
      lambda: (_r.status_code in (302, 303, 401) and (_r.status_code == 401 or _r.headers.get("location", "").startswith("/login"))
      and CA.get(_inv).status_code == 404), lambda: ((_r.status_code, _r.headers.get("location"))))
_r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "0"})
_o1 = CX.get(RA.get("url", "/x")).status_code
_r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
_o2 = CX.get(RA.get("url", "/x")).status_code
check("A8 sayt katalogi o'chirilsa — ochiq rasm 404, qayta yoqilsa — 200 (fayl va yozuv joyida)", lambda: ((_o1, _o2) == (404, 200)), lambda: ((_o1, _o2)))
check("A9 mijoz korxona Admini A ning rasmini o'chira / tartiblay olmaydi — 404",
      lambda: (CB.delete(API + f"/rasmlar/{RA.get('id')}").status_code == 404
      and CB.put(API + f"/modellar/{M1}/rasmlar", json={"tartib": [RA.get("id")]}).status_code == 404
      and len(rasmlar(M1)) == 3))
# A9b: IKKINCHI do'kon egasi (platforma admini bor korxona — sayt katalogi unda ham yoqiladi) — A ning rasmlariga tegolmaydi
db_ishi(lambda d: d.add(Company(id=3, name="T232 C ega")) if not d.get(Company, 3) else None)
with contextlib.redirect_stdout(io.StringIO()):
    _s3 = SessionLocal()
    auth.create_user(_s3, "t232_c", PAROL, UserRole.ADMIN, "T232 C", company_id=3)
    _s3.query(User).filter(User.username == "t232_c").first().is_platform_admin = True
    _s3.commit()
    _s3.close()
_r3y = CP.post("/api/platform/companies/3/dokon", data={"yoqilgan": "1"})
CC = mijoz("t232_c")
_kc = katalog(CC)
_cm = js(CC.post(API + "/modellar", json={"bolim_id": next((b["id"] for b in _kc["bolimlar"] if b["nom"] == "Karnizlar"), 0),
                                         "kod": "C-1"})).get("id")
_rc1 = CC.delete(API + f"/rasmlar/{RA.get('id')}")
_rc2 = CC.put(API + f"/modellar/{M1}/rasmlar", json={"tartib": [x["id"] for x in rasmlar(M1)]})
_rc3 = CC.post(API + f"/modellar/{M1}/rasmlar", files={"fayl": ("a.jpg", jpeg(), "image/jpeg")})
_rc4 = CC.put(API + f"/modellar/{_cm}/rasmlar", json={"tartib": [RA.get("id")]})
check("A9b boshqa do'kon egasi (korxona 3, sayt katalogi YOQILGAN) A ning rasmini o'chira / tartiblay / modeliga yuklay olmaydi, "
      "o'z modeliga A ning rasmini qo'sha olmaydi, katalogida A ning rasmi yo'q",
      lambda: (_r3y.status_code == 200 and (_rc1.status_code, _rc2.status_code, _rc3.status_code) == (404, 404, 404)
      and _rc4.status_code == 400 and _kc.get("rasmlar") == [] and len(rasmlar(M1)) == 3
      and CX.get(RA.get("url", "/x")).status_code == 200),
      lambda: ((_r3y.status_code, _rc1.status_code, _rc2.status_code, _rc3.status_code, _rc4.status_code, _kc.get("rasmlar"))))
_r = CA.post(API + f"/modellar/{M1}/rasmlar", files={"fayl": ("soxta.jpg", b"matn", "image/jpeg")})
_r2 = CA.post(API + f"/modellar/{M1}/rasmlar", files={"fayl": ("IMG.HEIC", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 100, "image/heic")})
_r3 = CA.post(API + "/modellar/999999/rasmlar", files={"fayl": ("a.jpg", jpeg(), "image/jpeg")})
_r4 = CA.post(API + "/modellar/99999999999/rasmlar", files={"fayl": ("a.jpg", jpeg(), "image/jpeg")})
_r5 = CA.post(API + f"/modellar/{M1}/rasmlar")
check("A10 rasm emas / HEIC — 400 matn bilan; mavjud bo'lmagan model — 404; juda katta raqam — 422; faylsiz — 422; bazaga yozilmadi",
      lambda: ((_r.status_code, _r2.status_code, _r3.status_code, _r4.status_code, _r5.status_code) == (400, 400, 404, 422, 422)
      and "rasm emas" in det(_r) and "HEIC" in det(_r2) and len(rasmlar(M1)) == 3),
      lambda: ((_r.status_code, _r2.status_code, _r3.status_code, _r4.status_code, _r5.status_code, det(_r)[:80])))

# Chegara: 10 ta
for _i in range(7):
    yukla(M1, jpeg(800, 600, rang=(_i * 30, 100, 100), meta=False), f"q{_i}.jpg")
_sabit = uuid.UUID("12345678123456781234567812345678")
_asl_uuid = uuid.uuid4
uuid.uuid4 = lambda: _sabit
try:
    _r = yukla(M1, jpeg(800, 600, meta=False), "11.jpg")
finally:
    uuid.uuid4 = _asl_uuid
_qoldi = [p for p in dokon_glob(_sabit.hex + "*")]
check("A11 modelda 10 ta rasm — 11-si 400 (tushunarli matn), uning fayllari diskda QOLMADI",
      lambda: (len(rasmlar(M1)) == 10 and _r.status_code == 400 and "10 ta rasm" in det(_r) and not _qoldi), lambda: ((_r.status_code, det(_r)[:120], _qoldi)))

_chaqirildi = []
_asl_t = getattr(main, "dokon_rasm_tayyorla", None)
main.dokon_rasm_tayyorla = lambda *a, **k: (_chaqirildi.append(1), _asl_t(*a, **k))[1]
_r = CA.post(API + f"/modellar/{M1}/rasmlar", files={"fayl": ("x.jpg", _sof2_soxta(10900, 10900), "image/jpeg")})
if _asl_t:
    main.dokon_rasm_tayyorla = _asl_t
else:
    del main.dokon_rasm_tayyorla
check("A11b modelda 10 ta rasm — 11-si rasm ISHLANMASDAN rad (400; review232 №1)", lambda: (_r.status_code == 400 and not _chaqirildi
      and "10 ta rasm" in det(_r)), lambda: ((_r.status_code, det(_r)[:100], _chaqirildi)))

_qx = None
try:
    db_ishi(lambda d: crud.dokon_rasm_qosh(d, 1, M1, "/static/uploads/dokon/" + "e" * 32 + ".jpg",
                                           "/static/uploads/dokon/" + "e" * 32 + "_k.jpg", 10, 10, 10, "T"))
    _qx = "o'tib ketdi"
except Exception as _e:                    # noqa: BLE001
    _qx = f"{type(_e).__name__}: {_e}"
check("A11c yakuniy chegara — yozuvda (model qulfi ostida): 11-rasm yozuvi rad (ValueError «10 ta rasm»)",
      lambda: (_qx.startswith("ValueError") and "10 ta rasm" in _qx and len(rasmlar(M1)) == 10), lambda: (_qx))

# Tartib
_ids = [r["id"] for r in rasmlar(M1)]
_j0 = jurnal("dokon_model")
_r = CA.put(API + f"/modellar/{M1}/rasmlar", json={"tartib": list(reversed(_ids))})
check("A12 tartib teskari — 200, katalogda yangi tartib (birinchisi — asosiy), jurnal +1",
      lambda: (_r.status_code == 200 and [x["id"] for x in js(_r).get("rasmlar", [])] == list(reversed(_ids))
      and [r["id"] for r in rasmlar(M1)] == list(reversed(_ids)) and jurnal("dokon_model") == _j0 + 1), lambda: (_r.text[:200]))
_r = CA.put(API + f"/modellar/{M1}/rasmlar", json={"tartib": list(reversed(_ids))})
check("A12b o'zgarishsiz tartib — 200, jurnalga yozilmadi", lambda: (_r.status_code == 200 and jurnal("dokon_model") == _j0 + 1))
_rb2 = yukla(M2, jpeg(900, 700, meta=False), "m2.jpg")
_rv = list(reversed(_ids))
for _nm, _tana in (("bitta yetishmaydi", {"tartib": _rv[:-1]}), ("begona (boshqa model) rasmi", {"tartib": _rv[:-1] + [js(_rb2).get("id")]}),
                   ("takror", {"tartib": _rv[:-1] + _rv[:1]}), ("satr", {"tartib": [str(x) for x in _rv]}),
                   ("mantiqiy", {"tartib": [True] + _rv[1:]}), ("ro'yxat emas", {"tartib": "1,2"}),
                   ("ortiqcha kalit", {"tartib": _rv, "model_id": M2}), ("bo'sh tana", {})):
    _r = CA.put(API + f"/modellar/{M1}/rasmlar", json=_tana)
    check(f"A13 tartib: {_nm} — 400", lambda: (_r.status_code == 400), lambda: ((_r.status_code, _r.text[:120])))
check("A13b rad etilganlardan keyin tartib o'zgarmadi", lambda: ([r["id"] for r in rasmlar(M1)] == _rv))

# O'chirish
_bir = (rasmlar(M1) or [{"id": 0, "url": "/x", "kichik": "/x"}])[0]
_j0 = jurnal("dokon_rasm")
_r = CA.delete(API + f"/rasmlar/{_bir['id']}")
check("A14 rasm o'chirildi — 200, fayllari diskdan o'chdi, ochiq manzil 404, keyingisi asosiy bo'ldi, jurnal +1",
      lambda: (_r.status_code == 200 and not os.path.exists(disk(_bir["url"])) and not os.path.exists(disk(_bir["kichik"]))
      and CX.get(_bir["url"]).status_code == 404 and rasmlar(M1)[0]["id"] == _rv[1] and len(rasmlar(M1)) == 9
      and jurnal("dokon_rasm") == _j0 + 1), lambda: (_r.status_code))
check("A14b qayta o'chirish — 404", lambda: (CA.delete(API + f"/rasmlar/{_bir['id']}").status_code == 404))

# Diskka yozishda xato (joy yetmadi) — 507, fayl va vaqtinchalik fayl qolmaydi (review232 №4)
_asl_replace = os.replace
_sanoq = []


def _replace_xato(a, b):
    _sanoq.append(1)
    if len(_sanoq) == 2:
        raise OSError(28, "No space left on device")
    return _asl_replace(a, b)


os.replace = _replace_xato
uuid.uuid4 = lambda: _sabit
try:
    _r = yukla(M1, jpeg(800, 600, meta=False), "disk.jpg")
finally:
    uuid.uuid4 = _asl_uuid
    os.replace = _asl_replace
_qoldi = dokon_glob(_sabit.hex + "*")
check("A20 diskka yozishda xato (2-fayl) — 507 tushunarli matn, 1-fayl va vaqtinchalik fayllar QOLMADI, yozuv yo'q",
      lambda: (_r.status_code == 507 and "saqlanmadi" in det(_r) and not _qoldi and len(rasmlar(M1)) == 9),
      lambda: ((_r.status_code, det(_r)[:100], _qoldi)))
# Navbat band — 503 (review232 №1)
_asl_kut = getattr(main, "DOKON_RASM_KUTISH", None)
_nav = getattr(main, "_DOKON_RASM_NAVBAT", None)
_r = None
if _nav is not None:
    main.DOKON_RASM_KUTISH = 0.3
    _nav.acquire()
    try:
        _tb = time.time()
        _r = yukla(M1, jpeg(800, 600, meta=False), "band.jpg")
        _tb = time.time() - _tb
    finally:
        _nav.release()
        main.DOKON_RASM_KUTISH = _asl_kut
check("A21 rasm ishlash navbati band — 503 «server band», kutish chegarasi bilan (ish oqimi bloklanmaydi)",
      lambda: (_r.status_code == 503 and "band" in det(_r) and len(rasmlar(M1)) == 9 and _tb < 3),
      lambda: ((getattr(_r, "status_code", None), det(_r)[:100], round(_tb, 2))))

# Yozuv saqlanmasa — fayl qolmaydi (model rasm ishlanayotganda o'chirildi)
_asl_qosh = getattr(crud, "dokon_rasm_qosh", None)
crud.dokon_rasm_qosh = lambda *a, **k: None
uuid.uuid4 = lambda: _sabit
try:
    _r = yukla(M1, jpeg(800, 600, meta=False), "x.jpg")
finally:
    uuid.uuid4 = _asl_uuid
    if _asl_qosh:
        crud.dokon_rasm_qosh = _asl_qosh
    else:
        del crud.dokon_rasm_qosh
_qoldi = dokon_glob(_sabit.hex + "*")
check("A15 model rasm ishlanayotganda o'chirilgan (yozuv — None) — 404, fayllar QOLMADI", lambda: (_r.status_code == 404 and not _qoldi),
      lambda: ((_r.status_code, _qoldi)))

# Zaxira → tiklash
_zx = db_ishi(lambda d: json.loads(json.dumps(crud.export_full_backup(d, company_id=1), default=str)))
_zrows = (_zx.get("tables") or {}).get("dokon_rasmlar") or []
check("A16 zaxira nusxada `dokon_rasmlar` (10 ta: 9 + 1, URL bilan)", lambda: (len(_zrows) == 10 and all(r.get("fayl") for r in _zrows)), lambda: (len(_zrows)))
_rcy = yukla(_cm, jpeg(900, 700, meta=False), "c.jpg", c=CC)
_cr = js(_rcy)
_tanlov = []
for _nm, _qator in (("noto'g'ri manzil", {"fayl": "/static/uploads/inventory/x.jpg", "kichik": "/static/uploads/dokon/" + "b" * 32 + "_k.jpg"}),
                    ("juftsiz (boshqa nom)", {"fayl": "/static/uploads/dokon/" + "c" * 32 + ".jpg", "kichik": "/static/uploads/dokon/" + "d" * 32 + "_k.jpg"}),
                    ("BOSHQA korxonaning (3) fayli", {"fayl": _cr.get("url"), "kichik": _cr.get("kichik")})):
    _z2 = json.loads(json.dumps(_zx))
    _q = dict((_z2.get("tables", {}).get("dokon_rasmlar") or [{}])[0])
    _q.update(_qator, id=999999)
    _z2.setdefault("tables", {}).setdefault("dokon_rasmlar", []).append(_q)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _t2 = db_ishi(lambda d: crud.import_full_backup(d, _z2, company_id=1, replace=True))
    except Exception as _e:                # noqa: BLE001
        _t2 = {"success": None, "message": f"{type(_e).__name__}: {_e}"}
    _tanlov.append((_nm, _t2.get("success"), str(_t2.get("message"))[:90]))
check("A22 zaxirada rasm manzili noto'g'ri / juftsiz / boshqa korxonaniki — tiklash RAD (hech narsa o'zgarmadi), korxona 3 rasmi joyida "
      "(review232 №3)", lambda: (_rcy.status_code == 200 and all(x[1] is False for x in _tanlov) and len(rasmlar(M1)) == 9
                                 and CX.get(_cr.get("url", "/x")).status_code == 200), lambda: ((_rcy.status_code, _tanlov)))
# A22b: himoya qatlami — yozuv (qanday yo'l bilan bo'lmasin) boshqa korxona fayllariga ishora qilsa, o'chirilganda u fayllar QOLADI
_soxta_id = None
if DokonRasm is not None and _cr.get("url"):
    def _soxta(d):
        x = DokonRasm(company_id=1, model_id=M1, fayl=_cr["kichik"], kichik=_cr["url"], eni=1, boyi=1, hajm=1, turi="jpeg", tartib=99)
        d.add(x)
        d.flush()
        return x.id
    _soxta_id = xavfsiz(_soxta)
_r = CA.delete(API + f"/rasmlar/{_soxta_id or 0}")
check("A22b boshqa korxona fayliga ishora qiluvchi yozuv o'chirilsa — o'sha fayllar diskda QOLADI, korxona 3 rasmi ochiq",
      lambda: (_soxta_id and _r.status_code == 200 and os.path.exists(disk(_cr["url"])) and os.path.exists(disk(_cr["kichik"]))
               and CX.get(_cr["url"]).status_code == 200), lambda: ((_soxta_id, _r.status_code)))
_eski = f"/static/uploads/dokon/{uuid.uuid4().hex}.jpg"
_yangi = f"/static/uploads/dokon/{uuid.uuid4().hex}_k.png"
for _u in (_eski, _yangi):
    open(disk(_u), "wb").write(b"x")
    YARATILGAN.append(_u)
_kech = time.time() - 7200
os.utime(disk(_eski), (_kech, _kech))
_eski_ish = rasmlar(M1)[0]["url"] if rasmlar(M1) else None
if _eski_ish:
    os.utime(disk(_eski_ish), (_kech, _kech))
_t = None
try:
    with contextlib.redirect_stdout(io.StringIO()):
        _t = db_ishi(lambda d: crud.import_full_backup(d, _zx, company_id=1, replace=True))
except Exception as _e:                    # noqa: BLE001
    _t = f"{type(_e).__name__}: {_e}"
check("A16b tiklash (replace) — rasmlar qaytdi (9 ta), tartibi o'sha, ochiq manzil ishlaydi",
      lambda: (len(rasmlar(M1)) == 9 and [r["id"] for r in rasmlar(M1)] == _rv[1:] and CX.get(rasmlar(M1)[0]["url"]).status_code == 200),
      lambda: ((str(_t)[:200], len(rasmlar(M1)))))
check("A23 tiklashdan keyin YOZUVSIZ va 1 soatdan eski fayl o'chdi; yangi yetim fayl va eski, lekin yozuvi bor fayl — joyida (review232 №5)",
      lambda: (not os.path.exists(disk(_eski)) and os.path.exists(disk(_yangi)) and _eski_ish and os.path.exists(disk(_eski_ish))
               and os.path.exists(disk(_cr.get("url")))), lambda: ((os.path.exists(disk(_eski)), os.path.exists(disk(_yangi)))))

# Model o'chirilsa — rasmlari ham
_m2r = rasmlar(M2)
_r = CA.delete(API + f"/modellar/{M2}")
check("A17 model o'chirildi — rasm yozuvlari ham, fayllari diskdan o'chdi, ochiq manzil 404",
      lambda: (_r.status_code == 200 and _m2r and not xavfsiz(lambda d: d.query(DokonRasm).filter(DokonRasm.model_id == M2).count(), 1)
      and not os.path.exists(disk(_m2r[0]["url"])) and CX.get(_m2r[0]["url"]).status_code == 404), lambda: ((_r.status_code, _r.text[:200])))
if DokonRasm is not None:
    _q = None
    try:
        def _beg(d):
            _bb = Company(id=5, name="T232 D") if not d.get(Company, 5) else None
            if _bb:
                d.add(_bb)
                d.flush()
            d.add(DokonRasm(company_id=5, model_id=M1, fayl="/static/uploads/dokon/" + "a" * 32 + ".jpg",
                            kichik="/static/uploads/dokon/" + "a" * 32 + "_k.jpg", eni=1, boyi=1, hajm=1, turi="jpeg", tartib=1))
            d.flush()
        db_ishi(_beg)
        _q = "o'tib ketdi"
    except Exception as _e:                # noqa: BLE001
        _q = type(_e).__name__
    check("A18 qo'riqchi: boshqa korxonaning modeliga rasm yozuvi — rad (TenantMismatchError)", lambda: (_q == "TenantMismatchError"), lambda: (_q))
check("A19 server xatosi (ErrorLog) yo'q", lambda: (db_ishi(lambda d: d.query(ErrorLog).count()) == 0),
      lambda: (db_ishi(lambda d: [e.message[:160] for e in d.query(ErrorLog).limit(3)])))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PG parallel")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    from concurrent.futures import ThreadPoolExecutor
    _m3 = js(CA.post(API + "/modellar", json={"bolim_id": _B.get("Karnizlar"), "kod": "PAR-232"})).get("id")
    for _i in range(9):
        yukla(_m3, jpeg(700, 600, meta=False), f"p{_i}.jpg")
    _c1, _c2 = mijoz("t232_admin"), mijoz("t232_admin")
    _asl_rl = getattr(crud, "_dokon_model_rasmlari", lambda *a, **k: [])

    def _sekin(*a, **k):
        r = _asl_rl(*a, **k)
        time.sleep(0.4)                    # sanoqdan KEYIN kechikish — qulfsiz kodda ikkalasi ham «9 ta» ko'radi
        return r
    crud._dokon_model_rasmlari = _sekin
    with ThreadPoolExecutor(max_workers=2) as ex:
        _f = [ex.submit(yukla, _m3, jpeg(700, 600, meta=False), f"par{i}.jpg", c) for i, c in enumerate((_c1, _c2))]
        _st = sorted(x.result().status_code for x in _f)
    crud._dokon_model_rasmlari = _asl_rl
    _yoz = xavfsiz(lambda d: [r.fayl for r in d.query(DokonRasm).filter(DokonRasm.model_id == _m3)], [])
    _disk = {os.path.basename(p) for p in dokon_glob("*")}
    _yaratilgan = [u for u in YARATILGAN if u.rsplit("/", 1)[1] in _disk]
    check("P1 9 ta rasmli modelga bir vaqtda ikki rasm — bittasi 200, ikkinchisi 400, jami 10, rad etilganning fayli diskda yo'q",
          _st == [200, 400] and len(_yoz) == 10 and all(os.path.isfile(disk(u)) for u in _yoz), (_st, len(_yoz)))
    _ids3 = [r["id"] for r in rasmlar(_m3)]

    def _tartib():
        return _c1.put(API + f"/modellar/{_m3}/rasmlar", json={"tartib": list(reversed(_ids3))}).status_code

    def _ochir():
        return _c2.delete(API + f"/rasmlar/{(_ids3 or [0])[0]}").status_code
    crud._dokon_model_rasmlari = _sekin     # tartib ro'yxatni o'qib 0,4 s kutadi — shu payt o'chirish keladi (review232 №2)
    with ThreadPoolExecutor(max_workers=2) as ex:
        _f1 = ex.submit(_tartib)
        time.sleep(0.15)
        _f2 = ex.submit(_ochir)
        _st = (_f1.result(), _f2.result())
    crud._dokon_model_rasmlari = _asl_rl
    check("P2 bir vaqtda tartib va o'chirish — 500 / 409 yo'q (o'chirish 200, tartib 200 yoki 400 — qulf tartibi model → rasm)",
      _st[0] in (200, 400) and _st[1] == 200, _st)
    check("P3 server xatosi yo'q", db_ishi(lambda d: d.query(ErrorLog).count()) == 0)
else:
    print("  (faqat PG rejimida)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
br = pw_ctx = server = None
if PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
    try:
        from playwright.sync_api import sync_playwright
        PW_BOR, _pw_x = True, ""
    except Exception as _e:                # noqa: BLE001
        PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
    import uvicorn                                 # noqa: E402

    def _port():
        so = socket.socket()
        so.bind(("127.0.0.1", 0))
        p = so.getsockname()[1]
        so.close()
        return p

    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    B = f"http://127.0.0.1:{port}"
    if PW_BOR and server.started:
        pw_ctx = sync_playwright().start()
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                  "chrome-linux", "chrome"))):
            _exe = _yol
        try:
            br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
        except Exception as _e:            # noqa: BLE001
            br = None
            _pw_x = f"{type(_e).__name__}: {_e}"
    check("U0 lokal server va Chromium", bool(server.started and br), _pw_x)
    JS_XATO, SOROV, KONSOL = [], [], []

    def kontekst(login, kenglik=1440):
        ctx = br.new_context(viewport={"width": kenglik, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
        ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
        pg.on("console", lambda m: KONSOL.append(m.text[:200]) if m.type == "error" else None)
        pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""))) if "/api/" in q.url else None)
        pg.goto(B + "/login")
        pg.fill("input[name=username]", login)
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
        return ctx, pg

    def kut(pg, ifoda, ms=10000):
        try:
            pg.wait_for_function(ifoda, timeout=ms)
            return True
        except Exception:                  # noqa: BLE001
            return False

    def fayl(nom, b):
        p = os.path.join(_T, nom)
        with open(p, "wb") as f:
            f.write(b)
        return p

    if br:
        try:
            _mu = js(CA.post(API + "/modellar", json={"bolim_id": _B.get("Karnizlar"), "kod": "UI-232", "nom": "Brauzer"})).get("id")
            _du = js(CA.post(API + "/detallar", json={"model_id": _mu, "turi": "asosiy", "olcham": "15 sm", "narx": 100000})).get("id")
            ctx, pg = kontekst("t232_admin")
            pg.goto(B + "/sayt-katalogi")
            kut(pg, "document.querySelectorAll('#skBolimlar .sk-bolim').length >= 9")
            pg.evaluate("""() => { const b = [...document.querySelectorAll('#skBolimlar .sk-bolim')]
                                 .find(x => x.innerText.includes('Karnizlar')); b.click(); }""")
            kut(pg, f"document.querySelector('[data-och=\"{_mu}\"]') !== null")
            pg.click(f"[data-och='{_mu}']")
            _blok = f"[data-rasmlar='{_mu}']"
            check("U1 model ochildi — «Rasmlar» bloki, «Rasm qo'shish» (accept: JPG / PNG / WEBP, multiple), «rasm yo'q» sarlavhada",
                  pg.evaluate(f"!!document.querySelector(\"{_blok} input[type=file][multiple]\")")
                  and pg.evaluate(f"document.querySelector(\"{_blok} input[type=file]\").accept") == "image/jpeg,image/png,image/webp"
                  and "rasm yo'q" in pg.text_content(f".sk-model[data-model='{_mu}'] .sk-son"),
                  pg.evaluate(f"document.querySelector(\"{_blok}\") && document.querySelector(\"{_blok}\").innerText.slice(0,200)"))
            # U7 oldidan: narx katagiga yozamiz (change yo'q) — yuklash tugagach matn joyida qolishi kerak
            _nk = f"tr[data-detal='{_du}'] [data-df=narx]"
            pg.click(_nk)
            pg.keyboard.press("Control+A")
            pg.keyboard.type("777")
            pg.evaluate("""() => { const f = window.fetch; window.__asl_fetch = f;
                window.fetch = (u, o) => (o && o.method === 'POST' && /rasmlar$/.test(String(u)))
                  ? new Promise(r => setTimeout(r, 600)).then(() => f(u, o)) : f(u, o); }""")
            _bas = len(SOROV)
            pg.set_input_files(f"{_blok} input[type=file]", [fayl("keng.jpg", jpeg(3000, 1000, rang=(240, 120, 0))),
                                                              fayl("tik.png", png(Image.new("RGB", (700, 2100), (0, 90, 200))))])
            _y = kut(pg, f"document.querySelectorAll(\"{_blok} .sk-rasm\").length === 2 && !document.querySelector(\"{_blok} .sk-rasm-qosh.band\")", 20000)
            check("U2 ikki fayl tanlandi — KETMA-KET 2 ta POST, 2 ta rasm, birinchisida «Asosiy», sarlavhada «2 ta rasm»",
                  _y and [x for x in SOROV[_bas:] if x[0] == "POST"] == [("POST", API + f"/modellar/{_mu}/rasmlar")] * 2
                  and pg.evaluate(f"document.querySelector(\"{_blok} .sk-rasm\").classList.contains('asosiy')")
                  and "2 ta rasm" in pg.text_content(f".sk-model[data-model='{_mu}'] .sk-son"), SOROV[_bas:])
            check("U7 yuklash davomida narx katagiga yozilgan matn («777», saqlanmagan) joyida — qator qayta chizilmadi",
                  pg.evaluate(f"document.querySelector(\"{_nk}\").value") == "777", pg.evaluate(f"document.querySelector(\"{_nk}\").value"))
            pg.evaluate("() => { window.fetch = window.__asl_fetch; }")
            kut(pg, f"[...document.querySelectorAll(\"{_blok} img\")].every(i => i.complete && i.naturalWidth > 0)")
            check("U3 rasmlar OCHIQ manzildan yuklandi (naturalWidth > 0), kartochka va namunada object-fit: contain (QIRQILMAYDI)",
                  pg.evaluate(f"[...document.querySelectorAll(\"{_blok} img\")].every(i => i.complete && i.naturalWidth > 0)")
                  and pg.evaluate(f"[...document.querySelectorAll(\"{_blok} .sk-rasm-kor img, {_blok} .sk-nm-karta img, {_blok} .sk-nm-sahifa img.asl\")]"
                                  ".every(i => getComputedStyle(i).objectFit === 'contain')")
                  and pg.evaluate(f"!!document.querySelector(\"{_blok} .sk-nm-sahifa img.xira\")"),
                  pg.evaluate(f"[...document.querySelectorAll(\"{_blok} img\")].map(i => [i.naturalWidth, getComputedStyle(i).objectFit])"))
            _bas = len(SOROV)
            pg.set_input_files(f"{_blok} input[type=file]", [fayl("buzuq.jpg", b"bu rasm emas")])
            _y = kut(pg, f"!document.querySelector(\"{_blok} .sk-rasm-qosh.band\") && (document.querySelector(\"{_blok} .sk-rasm-holat\") || {{}}).innerText && document.querySelector(\"{_blok} .sk-rasm-holat\").innerText.includes('buzuq.jpg:')")
            check("U4 rasm bo'lmagan fayl — blok ostida fayl nomi va sababi, rasmlar soni o'zgarmadi",
                  _y and "rasm emas" in pg.text_content(f"{_blok} .sk-rasm-holat")
                  and pg.evaluate(f"document.querySelectorAll(\"{_blok} .sk-rasm\").length") == 2,
                  pg.evaluate(f"(document.querySelector(\"{_blok} .sk-rasm-holat\") || {{}}).innerText"))
            pg.set_input_files(f"{_blok} input[type=file]", [{"name": '<img src=x onerror="window.__x232=1">.jpg',
                                                              "mimeType": "image/jpeg", "buffer": b"rasm emas"}])
            _y = kut(pg, f"!document.querySelector(\"{_blok} .sk-rasm-qosh.band\") && (document.querySelector(\"{_blok} .sk-rasm-holat\") || {{}}).innerText && document.querySelector(\"{_blok} .sk-rasm-holat\").innerText.includes('<img src=x')")
            pg.wait_for_timeout(300)
            check("U4b fayl nomidagi HTML — matn bo'lib ko'rinadi, bajarilmaydi", _y and pg.evaluate("window.__x232 === undefined"),
                  pg.evaluate(f"(document.querySelector(\"{_blok} .sk-rasm-holat\") || {{}}).innerText"))
            _ids = [r["id"] for r in rasmlar(_mu)]
            pg.click(f"{_blok} [data-rsur='{_ids[1]}'][data-yon='-1']")
            _y = kut(pg, f"document.querySelector(\"{_blok} .sk-rasm\").dataset.rasm === '{_ids[1]}' && !document.querySelector(\"{_blok} .sk-rasm-ush[disabled]\")")
            check("U5 ◀ — ikkinchi rasm asosiy bo'ldi (ekranda va bazada)", _y and [r["id"] for r in rasmlar(_mu)] == [_ids[1], _ids[0]],
                  [r["id"] for r in rasmlar(_mu)])
            _u0 = pg.locator(f"{_blok} .sk-rasm").nth(0).locator(".sk-rasm-ush").bounding_box()
            _u1 = pg.locator(f"{_blok} .sk-rasm").nth(1).bounding_box()
            pg.mouse.move(_u0["x"] + _u0["width"] / 2, _u0["y"] + _u0["height"] / 2)
            pg.mouse.down()
            pg.mouse.move(_u1["x"] + _u1["width"] * 0.8, _u1["y"] + 30, steps=8)
            pg.mouse.up()
            _y = kut(pg, f"document.querySelector(\"{_blok} .sk-rasm\").dataset.rasm === '{_ids[0]}' && !document.querySelector(\"{_blok} .sk-rasm-ush[disabled]\")")
            check("U6 «⠿» ushlab surish — tartib almashdi va saqlandi (PUT)", _y and [r["id"] for r in rasmlar(_mu)] == _ids,
                  [r["id"] for r in rasmlar(_mu)])
            pg.click(f"{_blok} [data-rkor='{_ids[1]}']")
            _y = kut(pg, "!document.getElementById('skKorish').hidden && document.getElementById('skKorRasm').naturalWidth > 0")
            _ok1 = _y and pg.evaluate("getComputedStyle(document.getElementById('skKorRasm')).objectFit") == "contain" \
                and "2 / 2" in pg.text_content("#skKorSoni")
            pg.keyboard.press("ArrowLeft")
            _ok2 = "1 / 2" in pg.text_content("#skKorSoni")
            _tab = []
            for _ in range(5):
                pg.keyboard.press("Tab")
                _tab.append(pg.evaluate("!!document.activeElement.closest('#skKorish')"))
            pg.keyboard.press("Escape")
            _ok3 = pg.evaluate(f"document.activeElement && document.activeElement.dataset.rkor === '{_ids[1]}'")
            check("U8 ko'rish oynasi — butun rasm (contain), ‹ › va Esc; Tab oynadan chiqmaydi, yopilganda fokus ochgan rasmga qaytadi",
                  _ok1 and _ok2 and all(_tab) and _ok3 and pg.evaluate("document.getElementById('skKorish').hidden"), (_ok1, _ok2, _tab, _ok3))
            _bas = len(SOROV)
            pg.focus(f"{_blok} [data-rsur='{_ids[0]}'][data-yon='1']")
            pg.keyboard.press("Enter")
            _y = kut(pg, f"document.querySelector(\"{_blok} .sk-rasm\").dataset.rasm === '{_ids[1]}' && !document.querySelector(\"{_blok} .sk-rasm-ush[disabled]\")")
            _fok = pg.evaluate("[document.activeElement.dataset.rsur || document.activeElement.dataset.rkor || document.activeElement.tagName, document.activeElement.dataset.yon]")
            check("U8b klaviatura bilan ▶ (Enter) — tartib saqlandi, fokus o'sha rasmning tugmasida qoldi (review232 №11)",
                  _y and _fok[0] == str(_ids[0]), _fok)
            _u0 = pg.locator(f"{_blok} .sk-rasm").nth(0).locator(".sk-rasm-ush").bounding_box()
            _u1 = pg.locator(f"{_blok} .sk-rasm").nth(1).bounding_box()
            _bas = len(SOROV)
            pg.mouse.move(_u0["x"] + _u0["width"] / 2, _u0["y"] + _u0["height"] / 2)
            pg.mouse.down(button="right")
            pg.mouse.move(_u1["x"] + _u1["width"] * 0.8, _u1["y"] + 30, steps=8)
            pg.mouse.up(button="right")
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(600)
            check("U8c o'ng tugma bilan surish — tartib o'zgarmaydi, so'rov yo'q (review232 №12)",
                  not [x for x in SOROV[_bas:] if x[0] == "PUT"] and [r["id"] for r in rasmlar(_mu)] == [_ids[1], _ids[0]], SOROV[_bas:])
            pg.set_viewport_size({"width": 375, "height": 800})
            pg.wait_for_timeout(300)
            check("U9 telefon (375 px) — sahifa gorizontal toshmaydi, rasm kartochkalari bir qatorda 2 ta",
                  not pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
                  and pg.evaluate(f"(() => {{ const r = [...document.querySelectorAll(\"{_blok} .sk-rasm\")].map(x => x.getBoundingClientRect().top); return r.length === 2 && Math.abs(r[0] - r[1]) < 2; }})()"),
                  pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]"))
            pg.set_viewport_size({"width": 1440, "height": 900})
            pg.evaluate("window.customConfirm = async () => true")
            _o = rasmlar(_mu)[0]
            pg.click(f"{_blok} [data-rochir='{_o['id']}']")
            _y = kut(pg, f"document.querySelectorAll(\"{_blok} .sk-rasm\").length === 1")
            check("U10 rasm o'chirildi — ekranda 1 ta qoldi, fayli diskdan o'chdi", _y and not os.path.exists(disk(_o["url"])))
            ctx.close()
            check("U11 JS xatosi yo'q", not JS_XATO, JS_XATO[:3])
            check("U12 konsolda xato yo'q (rad etilgan 400 dan tashqari)", not [k for k in KONSOL if "400" not in k], KONSOL[:3])
        except Exception as e:             # noqa: BLE001
            check("U* brauzer sinovi qulamadi", False, f"{type(e).__name__}: {e}")
    if br:
        br.close()
    if pw_ctx:
        pw_ctx.stop()
    if server:
        server.should_exit = True

# Sinov fayllarini tozalash (tf0 / tf1 bir papkada — faqat O'ZI yaratganlari)
for _u in set(YARATILGAN):
    try:
        if os.path.isfile(disk(_u)):
            os.remove(disk(_u))
    except OSError:
        pass
if DokonRasm is not None:
    for _u in xavfsiz(lambda d: [u for r in d.query(DokonRasm) for u in (r.fayl, r.kichik)], []) or []:
        try:
            if os.path.isfile(disk(_u)):
                os.remove(disk(_u))
        except OSError:
            pass

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
