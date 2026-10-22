#!/usr/bin/env python3
"""
test_mayda202.py — kech154 (zip 202 «Qolgan 3 mayda qoldiq»; egasi TANLOVI 22.10 02:0x): «Faoliyat jurnali» yozuvi yo'qolmaydi (V5),
ruxsatsiz rolda loyiha tugmalari yo'q, katta logotip kichraytiriladi (N5).

NIMA UCHUN KERAK (O'LCHANGAN — zip 201 kodi; `work/k202/probe202_v5.py`, `work/k202/probe202_n5.py`):
  V5  HAQIQIY PG: 150 belgili nomli mahsulot brakining bekori — «Faoliyat jurnali» yozuvi 0 ta («Brak bekor qilindi: <nom> — 1 metr
      (… so'm) · ombor tiklandi» — 211 belgi, `activity_logs.entity_label` VARCHAR(200)); «Xatoliklar» da «Faoliyat jurnaliga
      yozilmadi». Amalning o'zi saqlanardi.
  T   «Loyihalar: Ko'rish» li maxsus rolda «Yangi loyiha», «Tahrirlash», «Yakunlash», «O'chirish», loyiha rasmi (kamera) ko'rinardi —
      bosilsa 403 (pasport 7-bo'lim, kech138).
  N5  sodda grafikali logotip 2 MB ichida juda katta (10300 × 5793 — 262 KB) va ASLICHA saqlanardi: har «Buyurtma hisobi» PDF i 4,7 s,
      +521…863 MB xotira (60 MP); 20 MP — 1,3–1,9 s, +173…299 MB.
BO'LIMLAR:
  S — manba: jurnal sarlavhasi Text; `main.LOGO_TOMON` = `pdf_service.LOGO_TOMON` = 1000, PNG / WEBP chegarasi 16 MP.
  J — jurnal: 150 belgili nomli brak bekori — yozuv bor (to'liq sarlavha, 200 dan uzun), «Xatoliklar» da yo'q; «Faoliyat jurnali»
      sahifasida to'liq ko'rinadi; (PG) production kabi VARCHAR(200) ustunli baza ishga tushishda TEXT ga kengaytiriladi (izoh bilan).
  L — logotip (xotira — /proc VmHWM, `clear_refs` bilan): katta PNG kichraytiriladi (shaffoflik saqlanadi), 16 MP dan katta PNG — 400
      (o'zbekcha sabab; avvalgi logotip o'zgarmaydi), katta JPEG — «draft» bilan (kam xotira), kichik logotip ASLICHA, WEBP; avval
      yuklangan katta logotip (diskda) — PDF ga kichraytirilgan nusxa (1000 px), ikkinchi PDF keshdan (kam xotira), fayl o'zgarmaydi.
  T — HAQIQIY Chromium (Playwright) + lokal server: «Ko'rish» — hech bir amal tugmasi yo'q; «Tahrirlash» — Tahrirlash / Yakunlash;
      «O'chirish» — faqat O'chirish; «Loyiha ko'rsatkichlari: Tahrirlash» — rasm (kamera); admin — hammasi (o'zgarmagan); server
      avvalgidek rad etadi (403); JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL` bilan HAQIQIY PostgreSQL 16 (J ning uzunlik qismi faqat PG da — SQLite ustun
  uzunligini tekshirmaydi). Asl kodga (zip 201) qarshi QULAMAYDI — yiqiladi.
Test o'zi yozgan logotip fayllarini oxirida o'chiradi (korxona 7 / 8 / 9 — rejimga qarab, parallel yurishlar to'qnashmasin).
ISHLATISH: python3 tools/test_mayda202.py
"""
import os
import io
import re
import sys
import glob
import json
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = os.environ.get("M202_PG_BAZA") or "mayda202_test"
TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="m202_")
from sqlalchemy import text                        # noqa: E402
if PG_URL:
    from sqlalchemy import create_engine as _ce
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(text(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(text(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'm202.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        if callable(detail):
            try:
                detail = detail()
            except Exception as e:         # noqa: BLE001
                detail = f"{type(e).__name__}: {e}"
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


# ── PG: production kabi — jurnal sarlavhasi VARCHAR(200) bo'lgan baza (ishga tushishdan OLDIN)
if PG_URL:
    import database as _d0                         # noqa: E402
    __import__("models")
    __import__("production_models")
    _d0.Base.metadata.create_all(bind=_d0.engine)
    with _d0.engine.begin() as _c:
        _c.execute(text("ALTER TABLE activity_logs ALTER COLUMN entity_label TYPE VARCHAR(200)"))

_bosh = io.StringIO()
with contextlib.redirect_stdout(_bosh):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import database                                # noqa: E402
    import pdf_service                             # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, Rol, Project, Inventory, FinishedProduct, StockSource, ProductionStatus,   # noqa: E402
                    ActivityLog, ErrorLog)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from PIL import Image, ImageDraw                   # noqa: E402
import pdfplumber                                  # noqa: E402

PAROL = "Parol123!"
KID = 9 if PG_URL else (8 if TF else 7)            # logotip sinovi korxonasi — rejimga qarab (fayllar to'qnashmasin)
MM = 72 / 25.4


def hwm_nol():
    try:
        with open("/proc/self/clear_refs", "w") as f:
            f.write("5")
        return True
    except OSError:
        return False


def hwm():
    try:
        for q in open("/proc/self/status"):
            if q.startswith("VmHWM"):
                return int(q.split()[1]) // 1024
    except OSError:
        pass
    return -1


def ortish(f, *a, **k):
    """(natija, eng yuqori xotira o'sishi MB)."""
    hwm_nol()
    b = hwm()
    r = f(*a, **k)
    return r, hwm() - b


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from sqlalchemy import Text as _Text               # noqa: E402
check("S1 `activity_logs.entity_label` — Text (uzun jurnal sarlavhasi sig'adi)",
      isinstance(ActivityLog.__table__.c.entity_label.type, _Text), ActivityLog.__table__.c.entity_label.type)
check("S2 `main.LOGO_TOMON` = `pdf_service.LOGO_TOMON` = 1000 px; PNG / WEBP logotip chegarasi 16 MP",
      getattr(main, "LOGO_TOMON", None) == 1000 and getattr(pdf_service, "LOGO_TOMON", None) == 1000
      and getattr(main, "LOGO_PIKSEL_CHEGARA", None) == 16_000_000,
      (getattr(main, "LOGO_TOMON", None), getattr(pdf_service, "LOGO_TOMON", None), getattr(main, "LOGO_PIKSEL_CHEGARA", None)))

# ── tayyorgarlik
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "m202_a", PAROL, UserRole.ADMIN, "M202 Admin", company_id=1)
    for _u in ("m202_kor", "m202_tah", "m202_och", "m202_ras"):
        auth.create_user(s, _u, PAROL, UserRole.MANAGER, _u.upper(), company_id=1)
ROLLAR = {"m202_kor": {"loyiha": ["korish"]}, "m202_tah": {"loyiha": ["korish", "tahrirlash"]},
          "m202_och": {"loyiha": ["korish", "ochirish"]},
          "m202_ras": {"loyiha": ["korish"], "loyiha_korsatkich": ["korish", "tahrirlash"]}}
for _u, _rx in ROLLAR.items():
    _r = Rol(company_id=1, nom="M202 " + _u, kod=None, ruxsatlar=json.dumps(_rx), tavsif="")
    s.add(_r)
    s.flush()
    s.query(User).filter(User.username == _u).first().rol_id = _r.id
NOM = ("Karniz " + "uzun nomli fasad profili " * 10)[:150]
FP = FinishedProduct(company_id=1, name=NOM, category="profil", quantity=10, produced_quantity=10, unit="metr", unit_price=0,
                     cost_price=1_000_000, unit_cost_stable=100_000, source=StockSource.PRODUCED,
                     production_status=ProductionStatus.READY, reserved_quantity=0)
PRJ1 = Project(company_id=1, client_name="M202 Mijoz", project_name="M202 loyiha", total_budget=0, total_paid=0)
s.add_all([FP, PRJ1])
if not s.query(Company).filter(Company.id == KID).first():
    s.add(Company(id=KID, name=f"M202 Logo {KID}", slogan="Fasad", address="Andijon", phone="+998 90 000 02 02"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, f"m202_l{KID}", PAROL, UserRole.ADMIN, "M202 logo admin", company_id=KID)
PRJ = Project(company_id=KID, client_name="M202 L Mijoz", project_name="M202 L loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=KID, item_name="M202 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
s.add_all([PRJ, PENO])
s.commit()
ID = {"FP": FP.id, "PRJ1": PRJ1.id, "PRJ": PRJ.id, "PENO": PENO.id}
s.close()


def mijoz(user):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": PAROL}, follow_redirects=False)
    return c if r.status_code in (302, 303) else None


A = mijoz("m202_a")
L = mijoz(f"m202_l{KID}")
check("T0 fikstura: kirish (admin, logotip korxonasi admini)", A is not None and L is not None)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J — «Faoliyat jurnali»: uzun sarlavha")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_rb = xav(A.post, "/api/finished/loss", json={"finished_product_id": ID["FP"], "quantity": 1, "brak_sabab": "boshqa", "reason": "M202"})
_lid = (_rb.json() or {}).get("loss_id") if _rb is not None and _rb.status_code == 200 else None
_rd = xav(A.delete, f"/api/finished/loss/{_lid}") if _lid else None
s = SessionLocal()
_j = s.query(ActivityLog).filter(ActivityLog.entity_type == "finished_product_loss", ActivityLog.action == "delete",
                                 ActivityLog.entity_id == (_lid or -1)).all()
_x = [e.error_message for e in s.query(ErrorLog).all() if "Faoliyat jurnaliga yozilmadi" in (e.error_message or "")]
s.close()
check("J1 150 belgili nomli mahsulot brakining bekori — 200, jurnal yozuvi BOR (to'liq sarlavha: nom va «ombor tiklandi», 200 dan uzun), "
      "«Xatoliklar» da «Faoliyat jurnaliga yozilmadi» yo'q",
      _rd is not None and _rd.status_code == 200 and len(_j) == 1 and NOM in (_j[0].entity_label or "")
      and (_j[0].entity_label or "").endswith("· ombor tiklandi") and len(_j[0].entity_label) > 200 and not _x,
      (getattr(_rb, "status_code", None), getattr(_rd, "status_code", None), [len(x.entity_label or "") for x in _j], _x[:1]))
_rl = xav(A.get, "/logs")
_h = _rl.text if _rl is not None and _rl.status_code == 200 else ""
check("J2 «Faoliyat jurnali» sahifasida yozuv to'liq ko'rinadi (nomning oxiri va «ombor tiklandi»)",
      "Brak bekor qilindi: " + NOM[:40] in _h and NOM[-40:].strip() in _h and "· ombor tiklandi" in _h,
      (getattr(_rl, "status_code", None), len(_h)))
if PG_URL:
    with database.engine.connect() as _c:
        _tur = _c.execute(text("SELECT data_type FROM information_schema.columns WHERE table_schema = current_schema() "
                               "AND table_name = 'activity_logs' AND column_name = 'entity_label'")).scalar()
        _izoh = _c.execute(text("SELECT col_description('activity_logs'::regclass, a.attnum) FROM pg_attribute a "
                                "WHERE a.attrelid = 'activity_logs'::regclass AND a.attname = 'entity_label'")).scalar()
    _kh = [x for x in (database.SXEMA_ISHGA_TUSHISH.get("kengaytirildi") or []) if x.get("ustun") == "entity_label"]
    check("J3 production kabi baza (jurnal sarlavhasi VARCHAR(200)) — ishga tushishda TEXT ga kengaytirildi, ustun izohi «VARCHAR(200) -> "
          "TEXT», server logida «Baza tuzilishi kengaytirildi: activity_logs.entity_label»",
          _tur == "text" and "VARCHAR(200) -> TEXT" in (_izoh or "") and len(_kh) == 1
          and "activity_logs.entity_label" in _bosh.getvalue(), (_tur, _izoh, _kh))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L — logotip (N5)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
UPL = os.path.join(ROOT, "static", "uploads", "logos")
_BOSH_LOGO = set(os.listdir(UPL)) if os.path.isdir(UPL) else set()


def rasm(w, h, fmt="PNG", shaffof=True):
    mode = "RGBA" if (shaffof and fmt != "JPEG") else "RGB"
    im = Image.new(mode, (w, h), (0, 0, 0, 0) if mode == "RGBA" else (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([w // 10, h // 10, w * 9 // 10, h * 9 // 10], fill=(180, 140, 40, 255) if mode == "RGBA" else (180, 140, 40))
    d.ellipse([w // 4, h // 4, w * 3 // 4, h * 3 // 4], fill=(30, 30, 30, 255) if mode == "RGBA" else (30, 30, 30))
    b = io.BytesIO()
    if fmt == "PNG":
        im.save(b, "PNG", optimize=True)
    elif fmt == "JPEG":
        im.save(b, "JPEG", quality=70)
    else:
        im.save(b, "WEBP", quality=80)
    del im, d
    return b.getvalue()


def yukla(baytlar, nom, tur):
    return xav(L.post, "/api/settings/company/logo", files={"file": (nom, baytlar, tur)})


def logo_yoli():
    s_ = SessionLocal()
    try:
        return s_.execute(text("SELECT logo_path FROM companies WHERE id = :k"), {"k": KID}).scalar()
    finally:
        s_.close()


def saqlangan():
    """(yo'l, baytlar, (eni, bo'yi), rejim, burchak pikseli) yoki None."""
    y = logo_yoli()
    p = os.path.join(ROOT, y) if y else None
    if not p or not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        bb = f.read()
    with Image.open(io.BytesIO(bb)) as im:
        im.load()
        return y, bb, im.size, im.mode, im.convert("RGBA").getpixel((2, 2))


def nisbat(a, b, w, h, tol=0.006):
    return a and b and abs((a / b) / (w / h) - 1) < tol


_b1 = rasm(5300, 2981)
_r1, _m1 = ortish(yukla, _b1, "katta.png", "image/png")
_s1 = saqlangan()
check("L1 katta PNG logotip (5300 × 2981, 15,8 MP, shaffof) — 200, saqlangani PNG, katta tomoni 1000 px, nisbati o'sha, shaffoflik "
      "saqlangan (burchak alfa 0); yuklash xotirasi < 200 MB",
      _r1 is not None and _r1.status_code == 200 and _s1 and _s1[0].endswith(".png") and max(_s1[2]) == 1000
      and nisbat(_s1[2][0], _s1[2][1], 5300, 2981) and _s1[3] == "RGBA" and _s1[4][3] == 0 and 0 <= _m1 < 200,
      (getattr(_r1, "status_code", None), getattr(_r1, "text", "")[:150], _s1 and (_s1[0], _s1[2], _s1[3], _s1[4]), _m1))
_b2 = rasm(10300, 5793)
_r2, _m2 = ortish(yukla, _b2, "juda_katta.png", "image/png")
_s2 = saqlangan()
_d2 = ""
try:
    _d2 = (_r2.json() or {}).get("detail") or ""
except Exception:                          # noqa: BLE001
    pass
check("L2 juda katta PNG (10300 × 5793 — 60 MP, 262 KB) — 400, o'zbekcha sabab (o'lchami bilan), avvalgi logotip va fayli o'zgarmadi; "
      "xotira < 60 MB (fayl boshidan o'lchami; asl kod 60 MP ni to'liq o'qiydi — +228 MB)",
      _r2 is not None and _r2.status_code == 400 and "Logotip juda katta (10300 × 5793 piksel)" in _d2 and "4000 × 4000" in _d2
      and _s2 and _s1 and _s2[0] == _s1[0] and _s2[1] == _s1[1] and 0 <= _m2 < 60,
      (f"xotira +{_m2} MB", "logotip o'zgarmadi" if (_s2 and _s1 and _s2[1] == _s1[1]) else "LOGOTIP O'ZGARDI",
       getattr(_r2, "status_code", None), _d2[:120]))
_b3 = rasm(8000, 6000, "JPEG")
_r3, _m3 = ortish(yukla, _b3, "foto.jpg", "image/jpeg")
_s3 = saqlangan()
check("L3 katta JPEG (8000 × 6000 — 48 MP) — 200 («draft» — kichik masshtabda o'qiladi), saqlangani .jpg, katta tomoni 1000 px, nisbati "
      "o'sha; xotira < 100 MB",
      _r3 is not None and _r3.status_code == 200 and _s3 and _s3[0].endswith(".jpg") and max(_s3[2]) == 1000
      and nisbat(_s3[2][0], _s3[2][1], 8000, 6000) and 0 <= _m3 < 100,
      (getattr(_r3, "status_code", None), getattr(_r3, "text", "")[:150], _s3 and (_s3[0], _s3[2]), _m3, len(_b3)))
_b4 = rasm(1000, 562)
_r4 = yukla(_b4, "kichik.png", "image/png")
_s4 = saqlangan()
check("L4 kichik logotip (1000 × 562) — ASLICHA saqlanadi (baytlar o'zgarmagan — avvalgidek)",
      _r4 is not None and _r4.status_code == 200 and _s4 and _s4[1] == _b4, (getattr(_r4, "status_code", None), _s4 and _s4[2]))
_b5 = rasm(4000, 2000, "WEBP")
_r5 = yukla(_b5, "logo.webp", "image/webp")
_s5 = saqlangan()
check("L5 katta WEBP (4000 × 2000, shaffof) — 200, saqlangani .webp, katta tomoni 1000 px, shaffoflik saqlangan",
      _r5 is not None and _r5.status_code == 200 and _s5 and _s5[0].endswith(".webp") and max(_s5[2]) == 1000
      and nisbat(_s5[2][0], _s5[2][1], 4000, 2000) and _s5[4][3] == 0,
      (getattr(_r5, "status_code", None), getattr(_r5, "text", "")[:150], _s5 and (_s5[0], _s5[2], _s5[3], _s5[4])))

# ── avval yuklangan (zip 202 dan oldin) katta logotip — diskda katta fayl
_tana = {"order_type": "product", "items": [{"name": "M202 karniz", "category": "profil", "width": 20, "thickness": 10, "length": 10,
                                             "quantity": 1, "unit_price": 1_000_000, "is_coated": False, "penoplast_id": ID["PENO"]}]}
_ro = xav(L.post, "/api/orders", params={"confirm_shortage": "true"}, json={**_tana, "project_id": ID["PRJ"]})
OID = (_ro.json() or {}).get("id") if _ro is not None and _ro.status_code == 200 else None
_eski = rasm(6000, 3375)
os.makedirs(UPL, exist_ok=True)
_eski_yol = os.path.join(UPL, f"company_{KID}.png")
with open(_eski_yol, "wb") as f:
    f.write(_eski)
s = SessionLocal()
s.execute(text("UPDATE companies SET logo_path = :y WHERE id = :k"), {"y": f"static/uploads/logos/company_{KID}.png", "k": KID})
s.commit()
s.close()


def pdf_rasmlari(bb):
    try:
        with pdfplumber.open(io.BytesIO(bb)) as p:
            return [(round(i["width"] / MM, 2), round(i["height"] / MM, 2), tuple(i.get("srcsize") or ())) for i in p.pages[0].images]
    except Exception:                      # noqa: BLE001
        return None


def pdf_ol():
    r = xav(L.get, f"/api/orders/{OID}/pdf")
    return (r.status_code, r.content) if r is not None else (None, b"")


(_p6, _m6) = ortish(pdf_ol)
_i6 = pdf_rasmlari(_p6[1]) if _p6[0] == 200 else None
check("L6 avval yuklangan katta logotip (diskda 6000 × 3375) — «Buyurtma hisobi» PDF 200, PDF ga KICHRAYTIRILGAN nusxa (≤ 1000 px), "
      "qutida nisbati o'sha (32 × 18 mm)",
      OID and _p6[0] == 200 and _i6 and len(_i6) == 1 and _i6[0][2] and max(_i6[0][2]) <= 1000
      and abs((_i6[0][0] / _i6[0][1]) / (6000 / 3375) - 1) < 0.02 and _i6[0][0] <= 32.05 and _i6[0][1] <= 18.05,
      (OID, _p6[0], _i6, _m6))
# katta faylni Pillow bilan ochishlar sanaladi (xotira o'lchovi qayta o'qishni ko'rsatmaydi: Pillow bo'shagan bloklarni qayta ishlatadi —
# keshsiz mutatsiya ham +0 MB berdi)
import PIL.Image as _PILImage                      # noqa: E402
_ochish7 = []
_asl_open7 = _PILImage.open


def _kuzat_open(fp, *a, **k):
    _nom = fp if isinstance(fp, (str, os.PathLike)) else getattr(fp, "name", None)
    if isinstance(_nom, (str, os.PathLike)) and os.path.abspath(str(_nom)) == os.path.abspath(_eski_yol):
        _ochish7.append(1)
    return _asl_open7(fp, *a, **k)


_PILImage.open = _kuzat_open
try:
    _t7 = time.time()
    (_p7, _m7) = ortish(pdf_ol)
    _t7 = round(time.time() - _t7, 2)
finally:
    _PILImage.open = _asl_open7
_i7 = pdf_rasmlari(_p7[1]) if _p7[0] == 200 else None
with open(_eski_yol, "rb") as f:
    _eski_endi = f.read()
check("L7 ikkinchi PDF — kichik nusxa keshdan: katta logotip fayli Pillow bilan qayta OCHILMAYDI (0 marta), xotira < 40 MB, rasm o'sha; "
      "diskdagi logotip fayli O'ZGARMADI",
      _p7[0] == 200 and _i7 == _i6 and not _ochish7 and 0 <= _m7 < 40 and _eski_endi == _eski,
      (f"ochildi {len(_ochish7)} marta", f"xotira +{_m7} MB", _p7[0], _i7, _t7, _eski_endi == _eski))
_kichik_png = rasm(998, 561)
with open(_eski_yol, "wb") as f:
    f.write(_kichik_png)
_p8 = pdf_ol()
_i8 = pdf_rasmlari(_p8[1]) if _p8[0] == 200 else None
check("L8 logotip fayli almashsa (yangi o'zgarish vaqti / hajm) — PDF yangisini oladi (998 × 561 — o'z holicha, kesh eskisini bermaydi)",
      _p8[0] == 200 and _i8 and len(_i8) == 1 and _i8[0][2] == (998, 561), (_p8[0], _i8))


# ── mustaqil tekshiruv F3: diskdagi kichraytirilgan nusxa (qayta ishga tushgandan keyin ham katta fayl o'qilmaydi) va bitta qulf
KICHIK_PDF = os.path.join(ROOT, "static", "uploads", "_kichik", "logo_pdf")


def _kichik_nusxalar():
    return sorted(f for f in (os.listdir(KICHIK_PDF) if os.path.isdir(KICHIK_PDF) else []) if f.startswith(f"company_{KID}_"))


with open(_eski_yol, "wb") as f:
    f.write(_eski)
xav(getattr(pdf_service, "_LOGO_KESH", {}).clear)
for _f in _kichik_nusxalar():
    xav(os.remove, os.path.join(KICHIK_PDF, _f))
_p12a = pdf_ol()                                   # birinchi PDF — katta fayl o'qiladi, nusxa diskka yoziladi
_n12 = _kichik_nusxalar()
xav(getattr(pdf_service, "_LOGO_KESH", {}).clear)                  # «qayta ishga tushish» — jarayon keshi bo'sh
_ochish12 = []
_PILImage.open = _kuzat_open
_ochish7 = _ochish12
try:
    _p12 = pdf_ol()
finally:
    _PILImage.open = _asl_open7
_i12 = pdf_rasmlari(_p12[1]) if _p12[0] == 200 else None
check("L12 avval yuklangan katta logotip — birinchi PDF dan keyin kichraytirilgan nusxa DISKDA (`uploads/_kichik/logo_pdf/`, nomida asl o'lcham); "
      "jarayon keshi bo'shagach (qayta ishga tushish) keyingi PDF katta faylni OCHMAYDI (0 marta), rasm ≤ 1000 px",
      _p12a[0] == 200 and len(_n12) == 1 and "_6000x3375_1000.png" in _n12[0] and _p12[0] == 200 and not _ochish12
      and _i12 and len(_i12) == 1 and max(_i12[0][2]) <= 1000, (_p12a[0], _n12, _p12[0], len(_ochish12), _i12))
xav(getattr(pdf_service, "_LOGO_KESH", {}).clear)
for _f in _kichik_nusxalar():
    xav(os.remove, os.path.join(KICHIK_PDF, _f))
_ochish13 = []
_ochish7 = _ochish13
_natija13 = []
_PILImage.open = _kuzat_open
try:
    _ipl = [threading.Thread(target=lambda: _natija13.append(xav(getattr(pdf_service, "_logo_tayyorla", None) or (lambda y: None), _eski_yol))) for _ in range(3)]
    [t.start() for t in _ipl]
    [t.join(120) for t in _ipl]
finally:
    _PILImage.open = _asl_open7
check("L13 bir vaqtda 3 ta PDF (kesh va disk nusxasi bo'sh) — katta fayl FAQAT BIR MARTA o'qiladi (bitta faylga bitta qulf), hammasiga bir xil "
      "kichik nusxa",
      len(_ochish13) == 1 and len(_natija13) == 3 and all(x and x[2] for x in _natija13) and len({x[2] for x in _natija13}) == 1,
      (f"ochildi {len(_ochish13)} marta", [bool(x and x[2]) for x in _natija13]))
for _f in _kichik_nusxalar():
    xav(os.remove, os.path.join(KICHIK_PDF, _f))
xav(getattr(pdf_service, "_LOGO_KESH", {}).clear)

# ── mustaqil tekshiruv F2: format va kengaytma — HAQIQIY rasmdan (brauzer aytgan turdan emas)
_b9 = rasm(3000, 1500)                             # shaffof PNG
_r9 = yukla(_b9, "logo.jpg", "image/jpeg")
_s9 = saqlangan()
check("L9 «.jpg» nomli (image/jpeg) shaffof PNG 3000 × 1500 — 200, saqlangani .png (PNG), RGBA, fon shaffof (qora EMAS), 1000 px",
      _r9 is not None and _r9.status_code == 200 and _s9 and _s9[0].endswith(".png") and _s9[3] == "RGBA" and _s9[4][3] == 0
      and max(_s9[2]) == 1000, (getattr(_r9, "status_code", None), getattr(_r9, "text", "")[:150], _s9 and (_s9[0], _s9[2], _s9[3], _s9[4])))
_cm = Image.new("CMYK", (3000, 1500), (200, 200, 0, 0))
_bb = io.BytesIO()
_cm.save(_bb, "JPEG", quality=70)
_b10 = _bb.getvalue()
_r10 = yukla(_b10, "logo.png", "image/png")
_s10 = saqlangan()
check("L10 «.png» nomli (image/png) CMYK JPEG 3000 × 1500 — 200 (500 EMAS), saqlangani .jpg (JPEG), 1000 px",
      _r10 is not None and _r10.status_code == 200 and _s10 and _s10[0].endswith(".jpg") and max(_s10[2]) == 1000
      and _s10[1][:3] == b"\xff\xd8\xff", (getattr(_r10, "status_code", None), getattr(_r10, "text", "")[:150], _s10 and (_s10[0], _s10[2])))
_g = Image.new("I;16", (2000, 1000), 40000)
_bb = io.BytesIO()
_g.save(_bb, "PNG")
_r11 = yukla(_bb.getvalue(), "kulrang.png", "image/png")
_y11 = logo_yoli()
_px11 = None
try:
    with Image.open(os.path.join(ROOT, _y11)) as _im11:
        _px11 = (_im11.mode, _im11.getpixel((5, 5)), _im11.size)
except Exception as _e:                    # noqa: BLE001
    _px11 = str(_e)
check("L11 16 bitli kulrang PNG 2000 × 1000 (qiymat 40000) — 200, 8 bitli kulrang (L) saqlandi, piksel ≈ 156 (oq 255 EMAS), 1000 px",
      _r11 is not None and _r11.status_code == 200 and isinstance(_px11, tuple) and _px11[0] == "L" and abs(_px11[1] - 156) <= 2
      and max(_px11[2]) == 1000, (getattr(_r11, "status_code", None), _px11))
_b15 = rasm(800, 400)
_r15 = yukla(_b15, "kichik.jpg", "image/jpeg")
_s15 = saqlangan()
check("L15 kichik PNG «.jpg» nomi bilan — baytlari ASLICHA, lekin kengaytma haqiqiy formatdan: .png",
      _r15 is not None and _r15.status_code == 200 and _s15 and _s15[0].endswith(".png") and _s15[1] == _b15,
      (getattr(_r15, "status_code", None), _s15 and _s15[0]))

for _f in os.listdir(UPL) if os.path.isdir(UPL) else []:
    if _f not in _BOSH_LOGO and _f.startswith(f"company_{KID}."):
        xav(os.remove, os.path.join(UPL, _f))

# ── mustaqil tekshiruv F5: logotip ishlovi ip hovuzida — katta logotip yuklanayotganda server boshqa so'rovlarga javob beradi
import uvicorn                                     # noqa: E402
import httpx                                       # noqa: E402
so = socket.socket()
so.bind(("127.0.0.1", 0))
port = so.getsockname()[1]
so.close()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
_srv_ip = threading.Thread(target=server.run, daemon=True)
_srv_ip.start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
BU = f"http://127.0.0.1:{port}"
# rasm ishlovi qaysi ipda bajarilganini yozib olish (hodisalar sikli — server ipi; ip hovuzi — boshqa ip). Vaqt o'lchovi yuklamaga
# bog'liq (asl kodda 0,16–0,3 s) — asosiy mezon ip.
_ip14 = []
_asl_saqlash14 = getattr(main, "_logo_saqlashga", None)
if _asl_saqlash14 is not None:
    def _kuzat_saqlash14(*a, **k):
        _ip14.append(threading.get_ident())
        return _asl_saqlash14(*a, **k)
    main._logo_saqlashga = _kuzat_saqlash14
_lg14 = xav(httpx.post, BU + "/login", data={"username": f"m202_l{KID}", "password": PAROL}, follow_redirects=False)
_tok14 = _lg14.cookies.get("session_token") if _lg14 is not None else None
_b14 = rasm(3999, 3999)
_yuk14 = {}


def _yukla14():
    _t = time.time()
    try:
        _r = httpx.post(BU + "/api/settings/company/logo", files={"file": ("katta.png", _b14, "image/png")},
                        headers={"Cookie": f"session_token={_tok14}"}, timeout=120)
        _yuk14["st"] = _r.status_code
    except Exception as _e:                # noqa: BLE001
        _yuk14["st"] = str(_e)
    _yuk14["dt"] = time.time() - _t


_th14 = threading.Thread(target=_yukla14)
_kech14 = []
with httpx.Client(base_url=BU, timeout=30) as _c14:
    _c14.get("/api/health")
    _th14.start()
    while _th14.is_alive():
        _t = time.time()
        _rh = xav(_c14.get, "/api/health")
        _kech14.append((time.time() - _t, getattr(_rh, "status_code", None)))
        time.sleep(0.02)
_th14.join(120)
if _asl_saqlash14 is not None:
    main._logo_saqlashga = _asl_saqlash14
_eng14 = round(max((x[0] for x in _kech14), default=9), 3)
check(f"L14 katta PNG logotip (3999 × 3999, shaffof) yuklanganda rasm ishlovi (`_logo_saqlashga`) IP HOVUZIDA — hodisalar sikli (server ipi) "
      f"bo'sh; boshqa so'rov kutmaydi: eng sekin javob < 0,3 s (o'lchandi: {_eng14} s; ilgari hodisalar siklida — 0,47 s)",
      _tok14 and _yuk14.get("st") == 200 and len(_ip14) == 1 and _ip14[0] != _srv_ip.ident and len(_kech14) >= 3 and _eng14 < 0.3
      and all(x[1] == 200 for x in _kech14),
      (_yuk14, f"ishlov ipi: {_ip14} server ipi: {_srv_ip.ident}", len(_kech14), _eng14))
for _f in os.listdir(UPL) if os.path.isdir(UPL) else []:
    if _f not in _BOSH_LOGO and _f.startswith(f"company_{KID}."):
        xav(os.remove, os.path.join(UPL, _f))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T — loyiha tugmalari (HAQIQIY brauzer)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_kor = mijoz("m202_kor")
_srv = {
    "yaratish": xav(_kor.post, "/api/projects", json={"client_name": "X", "project_name": "X"}),
    "tahrir": xav(_kor.put, f"/api/projects/{ID['PRJ1']}", json={"status": "COMPLETED"}),
    "ochirish": xav(_kor.delete, f"/api/projects/{ID['PRJ1']}"),
}
check("T1 server avvalgidek: «Ko'rish» li rol — yaratish / tahrir (Yakunlash) / o'chirish 403",
      all(r is not None and r.status_code == 403 for r in _srv.values()),
      {k: getattr(r, "status_code", None) for k, r in _srv.items()})

PW_BOR = True
try:
    from playwright.sync_api import sync_playwright
except Exception:                          # noqa: BLE001
    PW_BOR = False
check("T2 Python `playwright` bor", PW_BOR)

HOLAT = r"""() => {
  const ko = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
  const tug = [...document.querySelectorAll('#tabContent .qa-row button')].filter(ko).map(b => (b.innerText || '').trim());
  const top = [...document.querySelectorAll('button')].filter(b => ko(b) && /Yangi loyiha/.test(b.innerText || '')).length;
  const kart = document.querySelectorAll('.proj-card').length;
  const kamera = document.querySelectorAll('.proj-thumb-cam').length;
  const fayl = document.querySelectorAll('.proj-thumb input[type=file]').length;
  return {tug, top, kart, kamera, fayl};
}"""

if PW_BOR:
    NATIJA = {}
    XATOLAR = {}
    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()
        for _u in ("m202_kor", "m202_tah", "m202_och", "m202_ras", "m202_a"):
            ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https://.*"), lambda r: r.fulfill(status=204, body=""))
            pg = ctx.new_page()
            _xt = []
            pg.on("pageerror", lambda e, _xt=_xt: _xt.append(str(e)[:300]))
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", _u)
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.goto, BU + "/projects")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.wait_for_function, "() => document.querySelector('#tabContent .qa-row') !== null", timeout=15000)
            NATIJA[_u] = xav(pg.evaluate, HOLAT)
            if _u in ("m202_kor", "m202_a"):
                xav(pg.goto, BU + "/projects?yangi=1")
                xav(pg.wait_for_load_state, "networkidle")
                _yangi = xav(pg.evaluate, "() => { const m = document.getElementById('addModal'); "
                                          "return m ? getComputedStyle(m).display : 'yoq'; }")
                if NATIJA.get(_u) is not None:
                    NATIJA[_u]["yangi1"] = _yangi
            XATOLAR[_u] = list(_xt)
            ctx.close()
        br.close()

    def tug(u):
        return (NATIJA.get(u) or {}).get("tug") or []

    def bor(u, nom):
        return any(nom in t for t in tug(u))

    _amallar = ("Tahrirlash", "Yakunlash", "O'chirish")
    check("T3 «Loyihalar: Ko'rish» — «Yangi loyiha», «Tahrirlash», «Yakunlash», «O'chirish», kamera / fayl tanlash YO'Q; ko'rish "
          "tugmalari (Buyurtmalari va h.k. — ruxsatiga qarab) avvalgidek",
          NATIJA.get("m202_kor") and not any(bor("m202_kor", n) for n in _amallar) and NATIJA["m202_kor"]["top"] == 0
          and NATIJA["m202_kor"]["kamera"] == 0 and NATIJA["m202_kor"]["fayl"] == 0 and NATIJA["m202_kor"]["kart"] >= 1,
          NATIJA.get("m202_kor"))
    check("T4 «Ko'rish + Tahrirlash» — «Tahrirlash» va «Yakunlash» BOR, «O'chirish» va «Yangi loyiha» yo'q",
          bor("m202_tah", "Tahrirlash") and bor("m202_tah", "Yakunlash") and not bor("m202_tah", "O'chirish")
          and (NATIJA.get("m202_tah") or {}).get("top") == 0, NATIJA.get("m202_tah"))
    check("T5 «Ko'rish + O'chirish» — faqat «O'chirish»",
          bor("m202_och", "O'chirish") and not bor("m202_och", "Tahrirlash") and not bor("m202_och", "Yakunlash"),
          NATIJA.get("m202_och"))
    check("T6 «Loyiha ko'rsatkichlari: Tahrirlash» — loyiha rasmi (kamera va fayl tanlash) BOR, amal tugmalari yo'q",
          (NATIJA.get("m202_ras") or {}).get("kamera", 0) >= 1 and (NATIJA.get("m202_ras") or {}).get("fayl", 0) >= 1
          and not any(bor("m202_ras", n) for n in _amallar), NATIJA.get("m202_ras"))
    check("T7 admin — hammasi avvalgidek («Yangi loyiha», Tahrirlash, Yakunlash, O'chirish, kamera)",
          all(bor("m202_a", n) for n in _amallar) and (NATIJA.get("m202_a") or {}).get("top") == 1
          and (NATIJA.get("m202_a") or {}).get("kamera", 0) >= 1, NATIJA.get("m202_a"))
    check("T8 sahifada JS xatosi yo'q (5 foydalanuvchi)", all(not v for v in XATOLAR.values()) and len(XATOLAR) == 5, XATOLAR)
    check("T9 «/projects?yangi=1» (eski xatcho'p / tarix) — «Ko'rish» li rolda yangi loyiha oynasi OCHILMAYDI, admin da ochiladi",
          (NATIJA.get("m202_kor") or {}).get("yangi1") == "none" and (NATIJA.get("m202_a") or {}).get("yangi1") == "flex",
          ((NATIJA.get("m202_kor") or {}).get("yangi1"), (NATIJA.get("m202_a") or {}).get("yangi1")))
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
