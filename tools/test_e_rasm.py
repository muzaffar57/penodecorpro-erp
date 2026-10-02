#!/usr/bin/env python3
"""
test_e_rasm.py — kech120, E BOSQICH 6-qism (RASMLAR: kichraytirish va kichik nusxa, audit G5-16 ikkinchi qismi; uzun ro'yxat animatsiyasi).

NIMA UCHUN KERAK (audit kech114; kodda ko'rilgan — main.py `_save_upload`, ro'yxat shablonlari):
  G5-16  Rasm kichraytirilmay 25 MB gacha saqlanardi (telefon kamerasi — 4000 × 3000, 3–6 MB) va ro'yxatdagi 40–70 px katakda ham
         TO'LIQ yuklanardi — mahsulot / material ko'paysa sahifa telefonda sekinlashadi. Telefon rasmidagi joylashuv (GPS) ham
         saqlanib qolardi.
BO'LIMLAR: S — statik (shablonlar: ro'yxat katagi — kichik nusxa, ko'ruvchi oyna — ASL manzil); F — `rasmni_kichraytir`
  (katta → 1920, burilish belgisi qo'llanadi, GPS yo'qoladi, kichigi — ASLICHA, shaffoflik saqlanadi, animatsiya / buzuq fayl /
  Pillowsiz — ASLICHA); Y — yuklash (material, tayyor mahsulot, loyiha, retsept, qaytarish, detal: diskda 1920 va kichik nusxa;
  buyurtma ILOVASI — ASLICHA); K — `?o=k` (kichik nusxa, ruxsat — asl fayl bilan bir xil: kirmagan 401, boshqa korxona 404;
  eski rasmga birinchi so'rovda yasaladi; logotip va PDF — asl; `_kichik` papkasi to'g'ridan-to'g'ri — 404); R — sahifalar
  (server shablonlari: `src` — kichik, `data-src` — asl); J — `kichikRasm` (JS) va `kichik_rasm` (Jinja) BIR XIL qoida;
  A — uzun ro'yxat animatsiyasi (Omborxona, Loyihalar, Qaytarishlar: faqat birinchi 20 qator «paydo bo'ladi», qolganlari darhol —
  O'LCHANGAN: 120 qatorli Omborxona telefonda (CPU 4× sekin) har qator animatsiyasi bilan asosiy oqimni 1,6–2,3 s band qilardi, animatsiyasiz
  0,8–1,2 s); B — HAQIQIY Chromium (Omborxona: katakdagi rasm 360 px, bosilganda — 1920 px asl; Tayyor mahsulotlar — kichik nusxa;
  21-qatordan animatsiya yo'q; «harakatni kamaytirish» — hech biri).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 129) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `PIL` (Pillow — reportlab bog'liqligi), `playwright` + Chromium (B bo'limi), `node` (J bo'limi).
Test o'zi yaratgan fayllarni (asl va kichik nusxa) oxirida o'chiradi.
ISHLATISH: python3 tools/test_e_rasm.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import uuid
import socket
import shutil
import tempfile
import threading
import contextlib
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "e_rasm_test"
_T = tempfile.mkdtemp(prefix="erasm_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'e_rasm_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, Project, Recipe, FinishedProduct, ReturnItem, ReturnReason,   # noqa: E402
                    Order, OrderItem, OrderType)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from PIL import Image                              # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
YARATILGAN = []                                    # test yaratgan fayllar — oxirida o'chiriladi


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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def rasm(w, h, fmt="JPEG", rang=(180, 120, 60), alfa=False, exif=None, **k):
    """Sinov rasmi: chap yarmi qizil, o'ng yarmi ko'k (burilishni aniqlash uchun), qolgan — `rang`."""
    im = Image.new("RGBA" if alfa else "RGB", (w, h), rang + ((128,) if alfa else ()))
    im.paste((220, 20, 20) + ((255,) if alfa else ()), (0, 0, w // 2, h))
    buf = io.BytesIO()
    if exif is not None:
        k["exif"] = exif
    im.save(buf, fmt, **k)
    return buf.getvalue()


def olcham(b):
    try:
        im = Image.open(io.BytesIO(b))
        return im.size, im.format, im.mode
    except Exception as e:                 # noqa: BLE001
        return None, f"{type(e).__name__}: {e}", None


def disk_yoli(url):
    return os.path.join(ROOT, url.split("?", 1)[0].lstrip("/"))


def kichik_yollari(url):
    papka = url.split("?", 1)[0].split("/")[3]
    return main._kichik_nusxa_yollari(disk_yoli(url), papka) if hasattr(main, "_kichik_nusxa_yollari") else ("", "")


KATTA = getattr(main, "RASM_KATTA_TOMON", None)
KICHIK = getattr(main, "RASM_KICHIK_TOMON", None)
KR = getattr(main, "rasmni_kichraytir", None)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAIN = oqi("main.py")
BASE = oqi("templates/base.html")
SH = {n: oqi(f"templates/{n}.html") for n in ("inventory", "projects", "recipes", "returns", "finished", "orders")}
check("S1 o'lchamlar: katta tomoni 1920, kichik nusxa 360 (ro'yxat katagi 40–70 px × telefon zichligi 3)", KATTA == 1920 and KICHIK == 360,
      (KATTA, KICHIK))
check("S2 server shablonlari: katak `src` — `|kichik_rasm`, ko'ruvchi oyna `data-src` — ASL (material, loyiha, retsept, qaytarish)",
      '<img src="{{ item.image_url|kichik_rasm }}" alt="" data-src="{{ item.image_url }}"' in SH["inventory"]
      and '<img src="{{ p.image_url|kichik_rasm }}" alt="" data-src="{{ p.image_url }}"' in SH["projects"]
      and '<img src="{{ recipe.image_url|kichik_rasm }}" alt="" data-src="{{ recipe.image_url }}"' in SH["recipes"]
      and '<img src="{{ r.image_url|kichik_rasm }}" alt="" data-src="{{ r.image_url }}"' in SH["returns"])
check("S3 JS shablonlari: katak — `kichikRasm(...)`, ko'ruvchi oyna — ASL (tayyor mahsulot 2 joy, detal, ilova katagi)",
      SH["finished"].count("escapeHtml(kichikRasm(i0.image_url))") == 1
      and "<img src=\"${escapeHtml(kichikRasm(i.image_url))}\" alt=\"\" onclick=\"event.preventDefault();event.stopPropagation();openLightbox('${jsAttrEscape(i.image_url)}')\">" in SH["finished"]
      and "<img src=\"${escapeHtml(kichikRasm(item.image_url))}\" alt=\"\" onclick=\"event.stopPropagation();openItemImgLightbox('${jsAttrEscape(item.image_url)}')\">" in SH["orders"]
      and '<img src="${escapeHtml(kichikRasm(a.file_url))}" alt="">' in SH["orders"] and '<a class="dl" href="${a.file_url}"' in SH["orders"])
check("S4 `kichikRasm` — base.html (har sahifada), `kichik_rasm` filtri — main.py; yuklashda faqat-rasm (`ALLOWED_IMAGE_EXT`) kichraytiriladi",
      "function kichikRasm(url)" in BASE and 'templates.env.filters["kichik_rasm"] = kichik_rasm_manzili' in MAIN
      and "faqat_rasm = allowed_ext == ALLOWED_IMAGE_EXT" in MAIN and "contents = rasmni_kichraytir(contents, ext)" in MAIN)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. rasmni_kichraytir")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_katta = rasm(4000, 3000, quality=95)
_r = KR(_katta, ".jpg") if KR else _katta
check("F1 4000 × 3000 JPEG → 1920 × 1440 JPEG, hajm kichraydi", olcham(_r)[:2] == ((1920, 1440), "JPEG") and len(_r) < len(_katta),
      (olcham(_r), len(_katta), len(_r)))
_ex = Image.Exif()
_ex[0x0112] = 6                                    # 90° burilgan (telefon tik ushlangan)
_ex[0x010F] = "Telefon"
_ex[0x8825] = {2: (41.0, 18.0, 0.0), 1: "N"}       # GPS
_bur = rasm(1000, 500, exif=_ex, quality=92)
_r = KR(_bur, ".jpeg") if KR else _bur
_o = olcham(_r)
_chap = None
try:
    _im = Image.open(io.BytesIO(_r)).convert("RGB")
    _chap = (_im.getpixel((_im.size[0] // 2, 2)), _im.getpixel((_im.size[0] // 2, _im.size[1] - 3)))
except Exception:                          # noqa: BLE001
    pass
check("F2 burilish belgisi (EXIF 6) — kichik rasm ham QAYTA yoziladi: 500 × 1000 (tik), belgi va GPS yo'q",
      _o[:2] == ((500, 1000), "JPEG") and Image.open(io.BytesIO(_r)).getexif().get(0x0112) in (None, 1)
      and 0x8825 not in Image.open(io.BytesIO(_r)).getexif(), (_o, dict(Image.open(io.BytesIO(_r)).getexif()) if _o[0] else None))
check("F3 burilish to'g'ri tomonga (soat mili bo'yicha 90°: chap yarmi — qizil — endi TEPADA, pastda — jigarrang)", _chap is not None
      and _chap[0][0] > 170 and _chap[0][1] < 70 and _chap[1][1] > 90, _chap)
_ex2 = Image.Exif()
_ex2[0x8825] = {2: (41.0, 18.0, 0.0), 1: "N"}
_gps = rasm(3000, 2000, exif=_ex2, quality=90)
_r = KR(_gps, ".jpg") if KR else _gps
check("F4 katta rasmdagi GPS (joylashuv) — kichraytirilganda saqlanmaydi", 0x8825 in Image.open(io.BytesIO(_gps)).getexif()
      and 0x8825 not in Image.open(io.BytesIO(_r)).getexif() and olcham(_r)[0] == (1920, 1280), olcham(_r))
_kichik = rasm(800, 600, quality=90)
check("F5 kichik (≤ 1920), burilishsiz rasm — bayt-ba-bayt ASLICHA", (KR(_kichik, ".jpg") if KR else None) == _kichik)
_png = rasm(3000, 2000, "PNG", alfa=True)
_r = KR(_png, ".png") if KR else _png
check("F6 shaffof PNG 3000 × 2000 → PNG 1920 × 1280, shaffoflik (RGBA) saqlanadi", olcham(_r) == ((1920, 1280), "PNG", "RGBA"), olcham(_r))
_webp = rasm(2500, 2500, "WEBP", quality=90)
_r = KR(_webp, ".webp") if KR else _webp
check("F7 WebP 2500 × 2500 → WebP 1920 × 1920", olcham(_r)[:2] == ((1920, 1920), "WEBP"), olcham(_r))
_kadr = [Image.new("RGB", (2400, 1200), (i * 80, 10, 10)) for i in range(3)]
_buf = io.BytesIO()
_kadr[0].save(_buf, "WEBP", save_all=True, append_images=_kadr[1:], duration=100, loop=0)
_anim = _buf.getvalue()
check("F8 animatsiyali WebP — ASLICHA (harakat yo'qolmaydi)", (KR(_anim, ".webp") if KR else None) == _anim)
_buzuq = b"\xff\xd8\xff\xe0" + os.urandom(3000)
check("F9 buzuq / rasm emas (.jpg) — ASLICHA, xato chiqmaydi", (KR(_buzuq, ".jpg") if KR else None) == _buzuq)
_asl_pil = getattr(main, "_pillow", None)
if _asl_pil:
    main._pillow = lambda: (None, None)
try:
    _r9 = KR(_katta, ".jpg") if KR else None
    _k9 = main.kichik_nusxa_yarat(os.path.join(_T, "yoq.jpg"), "inventory") if hasattr(main, "kichik_nusxa_yarat") else "x"
finally:
    if _asl_pil:
        main._pillow = _asl_pil
check("F10 Pillow bo'lmasa — ASLICHA saqlanadi, kichik nusxa yasalmaydi (asl beriladi)", _asl_pil is not None and _r9 == _katta and _k9 is None,
      (_asl_pil, _k9))
_eski_ch = getattr(main, "RASM_PIKSEL_CHEGARA", None)
if _eski_ch:
    main.RASM_PIKSEL_CHEGARA = 1_000_000
try:
    _r11 = KR(_katta, ".jpg") if KR else None
finally:
    if _eski_ch:
        main.RASM_PIKSEL_CHEGARA = _eski_ch
check("F11 piksel chegarasidan katta rasm — ishlov berilmaydi (xotira himoyasi), ASLICHA", _eski_ch == 60_000_000 and _r11 == _katta, _eski_ch)
check("F12 ruxsat etilmagan kengaytma (.pdf) — ASLICHA", (KR(_katta, ".pdf") if KR else None) == _katta)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Y. Yuklash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "erasm_admin", "Parol123!"
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="Rasm B korxona", code="RASM-B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, ADMIN, PAROL, UserRole.ADMIN, "Rasm Admin", company_id=1)
    auth.create_user(_db, "erasm_b", PAROL, UserRole.ADMIN, "B Admin", company_id=2)
_n = uuid.uuid4().hex[:6]
_inv = Inventory(company_id=1, item_name=f"Rasm material {_n}", unit="kg")
_prj = Project(company_id=1, project_number=f"RSM-{_n}", project_name=f"Rasm loyiha {_n}", client_name="Rasm Mijoz")
_rec = Recipe(company_id=1, name=f"Rasm retsept {_n}")
_fp = FinishedProduct(company_id=1, name=f"Rasm mahsulot {_n}", quantity=5, unit="dona", category="dona")
_db.add_all([_inv, _prj, _rec, _fp])
_db.commit()
_ord = Order(company_id=1, project_id=_prj.id, order_number=f"RSM-{_n}-1", order_type=OrderType.PRODUCT)
_db.add(_ord)
_db.commit()
_oi = OrderItem(company_id=1, order_id=_ord.id, name="Rasm detal")
_ret = ReturnItem(company_id=1, finished_product_id=_fp.id, item_name="Rasm qaytarish", quantity=1, reason=ReturnReason.DEFECT)
_db.add_all([_oi, _ret])
_db.commit()
ID = {"inv": _inv.id, "prj": _prj.id, "rec": _rec.id, "fp": _fp.id, "ord": _ord.id, "oi": _oi.id, "ret": _ret.id}
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
C0 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_l1 = C.post("/login", data={"username": ADMIN, "password": PAROL}, follow_redirects=False).status_code
_l2 = CB.post("/login", data={"username": "erasm_b", "password": PAROL}, follow_redirects=False).status_code
check("Y0 ikki korxona adminlari kirdi", (_l1, _l2) == (302, 302), (_l1, _l2))


def yukla(yol, nom, baytlar, turi="image/jpeg", c=None):
    r = (c or C).post(yol, files={"file": (nom, baytlar, turi)})
    try:
        j = r.json()
    except Exception:                      # noqa: BLE001
        j = {}
    url = j.get("image_url") or j.get("file_url") or ""
    if url:
        YARATILGAN.append(disk_yoli(url))
        YARATILGAN.extend(kichik_yollari(url))
    return r.status_code, url


def diskda(url):
    try:
        with open(disk_yoli(url), "rb") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return b""


URL = {}
for _k, _yol in (("inv", f"/api/inventory/{ID['inv']}/image"), ("fp", f"/api/finished/{ID['fp']}/image"),
                 ("prj", f"/api/projects/{ID['prj']}/image"), ("rec", f"/api/recipes/{ID['rec']}/image"),
                 ("ret", f"/api/returns/{ID['ret']}/image"), ("oi", f"/api/order-items/{ID['oi']}/image")):
    URL[_k] = yukla(_yol, f"telefon_{_k}.jpg", _katta)
_hamma = {k: (v[0], olcham(diskda(v[1]))[0]) for k, v in URL.items()}
check("Y1 6 ta faqat-rasm yuklamasi (material, tayyor mahsulot, loyiha, retsept, qaytarish, detal): 200, diskda 1920 × 1440",
      all(v == (200, (1920, 1440)) for v in _hamma.values()), _hamma)
_kn = {k: [y for y in kichik_yollari(v[1]) if os.path.isfile(y)] for k, v in URL.items() if v[1]}
_kno = {k: (Image.open(v[0]).size if v else None) for k, v in _kn.items()}
check("Y2 yuklashda kichik nusxa ham yasaldi (`uploads/_kichik/<papka>/<nom>_360.jpg`, 360 × 270)",
      len(_kno) == 6 and all(v == (360, 270) for v in _kno.values())
      and all(y[0].endswith("_360.jpg") and f"{os.sep}_kichik{os.sep}" in y[0] for y in _kn.values()), _kno)
_s, _ilova = yukla(f"/api/orders/{ID['ord']}/attachments", "chizma_rasm.jpg", _katta)
check("Y3 buyurtma ILOVASI (rasm-hujjat) — ASLICHA saqlanadi (bayt-ba-bayt, 4000 × 3000), kichik nusxa yuklashda yasalmaydi",
      _s == 200 and diskda(_ilova) == _katta and not any(os.path.isfile(y) for y in kichik_yollari(_ilova)), (_s, _ilova))
_s, _kich = yukla(f"/api/inventory/{ID['inv']}/image", "kichik.jpg", _kichik)
check("Y4 kichik rasm (800 × 600) — ASLICHA saqlanadi", _s == 200 and diskda(_kich) == _kichik, _s)
_s, _bz = yukla(f"/api/inventory/{ID['inv']}/image", "buzuq.jpg", _buzuq)
check("Y5 buzuq «rasm» — avvalgidek qabul qilinadi (ASLICHA), xato 500 emas", _s == 200 and diskda(_bz) == _buzuq, _s)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Kichik nusxa (`?o=k`)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_u = URL["inv"][1]
# Y4 / Y5 materialning rasmini almashtirdi — katta rasmni qayta biriktiramiz (tekshiruv shu yozuvga bog'liq)
_s, _u = yukla(f"/api/inventory/{ID['inv']}/image", "telefon_inv2.jpg", _katta)
_a = C.get(_u)
_k = C.get(_u + "?o=k")
check("K1 asl manzil — 1920 × 1440; `?o=k` — 360 × 270 JPEG, `private, max-age=86400`",
      _a.status_code == 200 and olcham(_a.content)[0] == (1920, 1440) and _k.status_code == 200 and olcham(_k.content)[:2] == ((360, 270), "JPEG")
      and _k.headers.get("content-type", "").startswith("image/jpeg") and _k.headers.get("cache-control") == "private, max-age=86400",
      (_a.status_code, _k.status_code, olcham(_k.content), _k.headers.get("content-type"), _k.headers.get("cache-control")))
check("K2 kichik nusxa — ancha yengil (< 40 KB va asldan 5 baravar kichik)", len(_k.content) < 40_000 and len(_k.content) * 5 < len(_a.content),
      (len(_k.content), len(_a.content)))
_k0 = C0.get(_u + "?o=k", follow_redirects=False)
_kb = CB.get(_u + "?o=k", follow_redirects=False)
check("K3 ruxsat — asl fayl bilan bir xil: kirmagan — 401 / kirishga, BOSHQA korxona — 404", _k0.status_code in (401, 302, 303)
      and _kb.status_code == 404 and not olcham(_k0.content)[0] and not olcham(_kb.content)[0], (_k0.status_code, _kb.status_code))
_jpg, _pngy = kichik_yollari(_u)
_kpap = os.path.relpath(_jpg, os.path.join(ROOT, "static", "uploads")).replace(os.sep, "/") if _jpg else ""
_tog = C.get("/static/uploads/" + _kpap) if _kpap else None
_tog2 = C.get("/static/uploads/_kichik/" + os.path.basename(_jpg)) if _jpg else None
check("K4 `_kichik` papkasi to'g'ridan-to'g'ri ochilmaydi — 404 (faqat `?o=k` orqali, ruxsat bilan)", _tog is not None
      and _tog.status_code == 404 and _tog2.status_code == 404, (_kpap, _tog and _tog.status_code, _tog2 and _tog2.status_code))
# eski rasm: ilgari (kichraytirishsiz) yuklangan — diskka to'g'ridan-to'g'ri yozamiz va yozuvga bog'laymiz
_eski_url = f"/static/uploads/inventory/{uuid.uuid4().hex}.jpg"
with open(disk_yoli(_eski_url), "wb") as _f:
    _f.write(_katta)
YARATILGAN.append(disk_yoli(_eski_url))
YARATILGAN.extend(kichik_yollari(_eski_url))
_db = SessionLocal()
_db.query(Inventory).filter(Inventory.id == ID["inv"]).update({"image_url": _eski_url})
_db.commit()
_db.close()
_yoq_oldin = not any(os.path.isfile(y) for y in kichik_yollari(_eski_url))
_e1 = C.get(_eski_url + "?o=k")
_bor_keyin = any(os.path.isfile(y) for y in kichik_yollari(_eski_url))
_e2 = C.get(_eski_url)
check("K5 ESKI rasm (4000 × 3000, nusxasiz): birinchi `?o=k` — nusxa yasaladi (360 × 270) va diskka yoziladi; asl — o'zgarmaydi",
      _yoq_oldin and _e1.status_code == 200 and olcham(_e1.content)[0] == (360, 270) and _bor_keyin and _e2.content == _katta,
      (_yoq_oldin, _e1.status_code, olcham(_e1.content), _bor_keyin))
for _y in kichik_yollari(_eski_url):
    if os.path.isfile(_y):
        with open(_y, "wb") as _f:
            _f.write(b"TAYYOR-NUSXA")
_e3 = C.get(_eski_url + "?o=k")
check("K6 nusxa bor bo'lsa — qayta yasalmaydi (diskdagisi beriladi)", _e3.content == b"TAYYOR-NUSXA", _e3.content[:40])
for _y in kichik_yollari(_eski_url):
    if os.path.isfile(_y):
        os.remove(_y)
_s, _pu = yukla(f"/api/inventory/{ID['inv']}/image", "shaffof.png", _png, "image/png")
_pk = C.get(_pu + "?o=k")
check("K7 shaffof PNG — nusxa PNG (shaffoflik saqlanadi), `image/png`", _pk.status_code == 200 and olcham(_pk.content) == ((360, 240), "PNG", "RGBA")
      and _pk.headers.get("content-type", "").startswith("image/png"), (_pk.status_code, olcham(_pk.content), _pk.headers.get("content-type")))
_ik = C.get(_ilova + "?o=k")
check("K8 ilova (rasm) — `?o=k` bilan nusxa (ilova katagi uchun), asli ASLICHA qoladi", _ik.status_code == 200
      and olcham(_ik.content)[0] == (360, 270) and diskda(_ilova) == _katta, (_ik.status_code, olcham(_ik.content)))
_pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
_s, _pdfu = yukla(f"/api/orders/{ID['ord']}/attachments", "hujjat.pdf", _pdf, "application/pdf")
_pk2 = C.get(_pdfu + "?o=k")
check("K9 PDF ilova — `?o=k` bilan ham ASL PDF", _s == 200 and _pk2.status_code == 200 and _pk2.content == _pdf, (_s, _pk2.status_code))
_logo = rasm(900, 900, "PNG")
_lr = C.post("/api/settings/company/logo", files={"file": ("logo.png", _logo, "image/png")})
_lp = "/" + ((_lr.json() if _lr.status_code == 200 else {}).get("logo_path") or "x")
_lk = C.get(_lp + "?o=k")
check("K10 logotip (nomi doimiy) — `?o=k` bilan ham ASL fayl, `no-cache`", _lr.status_code == 200 and _lk.status_code == 200
      and _lk.content == _logo and "no-cache" in (_lk.headers.get("cache-control") or ""), (_lr.status_code, _lk.status_code))
_db = SessionLocal()
_db.query(Company).filter(Company.id == 1).update({"logo_path": None})
_db.commit()
_db.close()
if os.path.isfile(disk_yoli(_lp)):
    YARATILGAN.append(disk_yoli(_lp))
_db = SessionLocal()
_db.query(Inventory).filter(Inventory.id == ID["inv"]).update({"image_url": _u})
_db.commit()
_db.close()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Sahifalar (server shablonlari)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_db = SessionLocal()
_db.query(Project).filter(Project.id == ID["prj"]).update({"image_url": URL["prj"][1]})
_db.query(Recipe).filter(Recipe.id == ID["rec"]).update({"image_url": URL["rec"][1]})
_db.query(ReturnItem).filter(ReturnItem.id == ID["ret"]).update({"image_url": URL["ret"][1]})
_db.commit()
_db.close()
_sah = {}
for _p, _k in (("/inventory", "inv"), ("/projects", "prj"), ("/recipes", "rec"), ("/returns", "ret")):
    _h = C.get(_p).text
    _url = _u if _k == "inv" else URL[_k][1]
    _sah[_p] = (f'<img src="{_url}?o=k" alt="" data-src="{_url}"' in _h, not re.search(r'(?<!data-)src="' + re.escape(_url) + '"', _h))
check("R1 Omborxona, Loyihalar, Retseptlar, Qaytarishlar: katak `src` — `?o=k`, `data-src` (ko'ruvchi oyna) — asl",
      all(a and b for a, b in _sah.values()), _sah)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Uzun ro'yxat animatsiyasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ANIM = {"inventory": ("mat-row", "matFadeIn"), "projects": ("proj-card", "pIn"), "returns": ("ret-row", "rIn")}
check("A1 uslub: 20-qatordan keyingilari (`anim-yoq`) — animatsiyasiz, darhol ko'rinadi; «harakatni kamaytirish» — hech biri",
      all(f".{k}.anim-yoq{{animation:none;opacity:1}}" in SH[n] and f"@media (prefers-reduced-motion:reduce){{.{k}{{animation:none;opacity:1}}}}" in SH[n]
          for n, (k, _a) in ANIM.items()))
_db = SessionLocal()
for _i in range(25):
    _db.add(Inventory(company_id=1, item_name=f"Anim material {_n} {_i:02d}", unit="kg"))
    _db.add(Project(company_id=1, project_number=f"ANM-{_n}-{_i:02d}", project_name=f"Anim loyiha {_i:02d}", client_name="Anim Mijoz"))
    _db.add(ReturnItem(company_id=1, finished_product_id=ID["fp"], item_name=f"Anim qaytarish {_i:02d}", quantity=1, reason=ReturnReason.EXCESS))
_db.commit()
_db.close()
_anim = {}
for _n2, (_k, _a) in ANIM.items():
    _h = C.get("/" + _n2).text
    _q = re.findall(r'<div class="' + _k + r'((?: [^"]*)?)"([^>]*)>', _h)
    _bosh = _q[:20]
    _qol = _q[20:]
    _anim[_n2] = (len(_q), all("anim-yoq" not in c and re.search(r'style="animation-delay:[0-9.]+s"', a) for c, a in _bosh),
                  len(_qol) >= 5 and all("anim-yoq" in c and "animation-delay" not in a for c, a in _qol),
                  [(re.search(r'animation-delay:([0-9.]+)s', a) or re.search("(.*)", c[:0] + a[:120])).group(1)
                   for c, a in _bosh[:3] + _bosh[-1:]] if len(_bosh) == 20 else None)
check("A2 sahifalar (25+ qator): birinchi 20 — animatsiya kechikishi bilan (0, 0.02, … 0.38 s), qolganlari `anim-yoq`, kechikishsiz "
      "(Omborxona, Loyihalar, Qaytarishlar)", all(v[1] and v[2] and v[3] == ["0.0", "0.02", "0.04", "0.38"] for v in _anim.values()), _anim)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. kichikRasm (JS) = kichik_rasm (Jinja)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
NAMUNA = ["/static/uploads/inventory/ab12.jpg", "/static/uploads/finished/AB.JPEG", "/static/uploads/x/y.png", "/static/uploads/x/y.webp",
          "/static/uploads/x/y.pdf", "/static/uploads/x/y.dwg", "/static/uploads/x/y.jpg?o=k", "/static/logo_round.jpg",
          "https://misol.uz/static/uploads/a.jpg", "", None, "static/uploads/x/y.jpg", "/static/uploads/x/y.jpg?v=2.png"]
_fn = re.search(r"function kichikRasm\(url\) \{.*?\n\}", BASE, re.S)
_js_n = None
if _fn and shutil.which("node"):
    _kod = _fn.group(0) + "\nconsole.log(JSON.stringify(" + json.dumps(NAMUNA) + ".map(kichikRasm)));"
    try:
        _js_n = json.loads(subprocess.run(["node", "-e", _kod], capture_output=True, text=True, timeout=30).stdout.strip())
    except Exception as _e:                # noqa: BLE001
        _js_n = str(_e)
_py_n = [main.kichik_rasm_manzili(x) for x in NAMUNA] if hasattr(main, "kichik_rasm_manzili") else None
_kut = ["/static/uploads/inventory/ab12.jpg?o=k", "/static/uploads/finished/AB.JPEG?o=k", "/static/uploads/x/y.png?o=k",
        "/static/uploads/x/y.webp?o=k", "/static/uploads/x/y.pdf", "/static/uploads/x/y.dwg", "/static/uploads/x/y.jpg?o=k",
        "/static/logo_round.jpg", "https://misol.uz/static/uploads/a.jpg", "", "", "static/uploads/x/y.jpg", "/static/uploads/x/y.jpg?v=2.png"]
check("J1 Jinja `kichik_rasm`: faqat yuklangan rasm (`/static/uploads/…` + .jpg/.jpeg/.png/.webp) → `?o=k`; PDF, chizma, statik, tashqi, "
      "bo'sh, so'rov qatori bor manzil — o'zgarmaydi", _py_n == _kut, _py_n)
check("J2 JS `kichikRasm` — AYNAN shu natija (node)", _js_n == _kut, _js_n)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Brauzer (HAQIQIY Chromium)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
import uvicorn                                     # noqa: E402


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
pw_ctx = br = None
if PW_BOR and server.started:
    pw_ctx = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*", "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        br = None
        _pw_x = f"{type(_e).__name__}: {_e}"
check("B0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO = []
SOROV = []
if br:
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True,
                         timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("requestfinished", lambda q: SOROV.append(q.url.replace(B, "")) if "/static/uploads/" in q.url else None)
    try:
        pg.goto(B + "/login")
        pg.fill("input[name=username]", ADMIN)
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
        pg.goto(B + "/inventory", wait_until="networkidle")
        _ib = pg.evaluate("""(u) => { const im = [...document.querySelectorAll('.mat-thumb img')].find(x => x.dataset.src === u);
            if (!im) return null; return {src: im.getAttribute('src'), w: im.naturalWidth, h: im.naturalHeight, tugal: im.complete,
            kw: im.getBoundingClientRect().width}; }""", _u)
        check("B1 Omborxona (telefon, 3×): katakdagi rasm — `?o=k`, yuklandi, 360 × 270 (katak ~70 px)", _ib and _ib["src"] == _u + "?o=k"
              and _ib["tugal"] and (_ib["w"], _ib["h"]) == (360, 270) and 0 < _ib["kw"] <= 80, _ib)
        check("B2 sahifa ochilganda ASL (1920) rasm so'ralmaydi — faqat kichik nusxa", _u + "?o=k" in SOROV and _u not in SOROV, SOROV)
        pg.evaluate("""(u) => { const im = [...document.querySelectorAll('.mat-thumb img')].find(x => x.dataset.src === u); im.click(); }""", _u)
        pg.wait_for_function("""() => { const i = document.getElementById('invLightboxImg'); return i && i.complete && i.naturalWidth > 0; }""")
        _lb = pg.evaluate("""() => { const i = document.getElementById('invLightboxImg'); return {src: i.getAttribute('src'), w: i.naturalWidth}; }""")
        check("B3 rasm bosilganda ko'ruvchi oyna — ASL manzil, 1920 px", _lb.get("src") == _u and _lb.get("w") == 1920, _lb)
        del SOROV[:]
        pg.goto(B + "/finished", wait_until="networkidle")
        pg.wait_for_timeout(400)
        _fi = pg.evaluate("""(u) => [...document.querySelectorAll('img')].filter(x => (x.getAttribute('src') || '').indexOf(u) === 0)
            .map(x => ({src: x.getAttribute('src'), w: x.naturalWidth}))""", URL["fp"][1])
        check("B4 Tayyor mahsulotlar: mahsulot rasmi — `?o=k` (360 px), asl so'ralmaydi", _fi and all(x["src"] == URL["fp"][1] + "?o=k"
              and x["w"] == 360 for x in _fi) and URL["fp"][1] not in SOROV, (_fi, SOROV))
        _ao = {}
        for _n2, (_k, _a) in ANIM.items():
            pg.goto(B + "/" + _n2, wait_until="domcontentloaded")
            _ao[_n2] = pg.evaluate("""([k, a]) => { const q = [...document.querySelectorAll('.' + k)]; const cs = e => getComputedStyle(e);
                return {soni: q.length, birinchi: cs(q[0]).animationName, yigirmanchi: cs(q[19]).animationName,
                        keyingi: q.slice(20).map(e => cs(e).animationName + '/' + cs(e).opacity).filter((v, i, m) => m.indexOf(v) === i)}; }""",
                                    [_k, _a])
        check("B6 HAQIQIY Chromium: 1–20-qator animatsiyali (`matFadeIn` / `pIn` / `rIn`), 21-dan — `none`, darhol ko'rinadi (opacity 1)",
              all(v["soni"] >= 25 and v["birinchi"] == ANIM[n][1] and v["yigirmanchi"] == ANIM[n][1] and v["keyingi"] == ["none/1"]
                  for n, v in _ao.items()), _ao)
        _ctx_rm = br.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="reduce", timezone_id="Asia/Tashkent", locale="uz-UZ",
                                 storage_state=ctx.storage_state())
        _ctx_rm.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
        _prm = _ctx_rm.new_page()
        _rm = {}
        for _n2, (_k, _a) in ANIM.items():
            _prm.goto(B + "/" + _n2, wait_until="domcontentloaded")
            _rm[_n2] = _prm.evaluate("""k => [...document.querySelectorAll('.' + k)].map(e => getComputedStyle(e).animationName + '/' + getComputedStyle(e).opacity)
                .filter((v, i, m) => m.indexOf(v) === i)""", _k)
        _ctx_rm.close()
        check("B7 «harakatni kamaytirish» yoqilgan tizimda — birorta qator animatsiyasiz (hammasi `none`, ko'rinadi)",
              all(v == ["none/1"] for v in _rm.values()), _rm)
        check("B5 JS xatosi yo'q", not JS_XATO, JS_XATO)
    except Exception as _e:                # noqa: BLE001
        check("B! brauzer ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
if br:
    br.close()
if pw_ctx:
    pw_ctx.stop()
server.should_exit = True

# ── tozalash: test yaratgan fayllar ──
for _y in set(YARATILGAN):
    try:
        if _y and os.path.isfile(_y):
            os.remove(_y)
    except OSError:
        pass
shutil.rmtree(_T, ignore_errors=True)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
