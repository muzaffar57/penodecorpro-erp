#!/usr/bin/env python3
"""
test_galereya243.py — kech178 (zip 243): «Bajarilgan ishlar» galereyasi (onlayn do'kon rejasi, 1-bosqich).

NIMA UCHUN KERAK (egasi QARORLARI «Onlayn do'kon rejasi» 30.10 — «Galereya bo'yicha tanlovlar»; O'LCHANGAN: zip 242 kodida galereya YO'Q —
  jadval, marshrut, do'kon API si, admin sahifasi bo'limi yo'q)
  Saytdagi «Bajarilgan ishlar» bo'limi: har ishning rasmlari, joyi, oyi va KATALOGDAN tanlangan mahsulotlari (shu uydagi miqdori bilan);
  narx va chegirma katalogdan (galereyada saqlanmaydi). Ishni egasi admin panelda o'zi qo'shadi.
TALAB (har biri o'lchanadi):
  S  statik: jadvallar / ustunlar, korxona qoidalari (ota — ish; havola — model / detal), o'chirish tartibi (qator / rasm → ish → detal →
     model), marshrutlar, do'kon API yo'li, `_dokon_rasm_jadvallari` (ikki jadval), sahifada kartochka va JS
  A  kirish: katalog o'chiq — 404; Menejer — 403; boshqa korxona (B) ishiga — 404; B dagi detal — 400
  G  saqlash: detal (metr kasr, dona butun) va komplekt (rom / eshik, o'lcham katalogdagi yozilishiga, kapitel / bazasiz model — False);
     noto'g'ri nom / oy / miqdor / takror / ortiqcha maydon / 31 qator / begona detal / komplekt bo'lmagan model / o'lchami yo'q — 400 va
     HECH NARSA yozilmaydi; tahrir — o'zgarishsiz saqlash jurnalga yozilmaydi, o'zgarsa — yoziladi; to'liq almashtirish
  B  bog'liqlik: detal / model o'chirilsa — qatorlari o'chadi (ish qoladi, jurnalda); model / detal yashirilsa yoki komplekt o'lchami
     o'chsa — qator qoladi, sababi ko'rsatiladi, saytga berilmaydi
  R  rasmlar: yuklash (GPS yo'q, fayl diskda, ochiq manzil login siz 200), 10 tadan ortiq — 400, tartib, o'chirish (fayl o'chadi), ish
     o'chirilsa — fayllar o'chadi, katalog o'chirilsa — ochiq manzil 404; yetim fayl tozalash galereya faylini o'chirmaydi
  D  do'kon API (kalit bilan): faqat yoqilgan va rasmi bor ishlar, yangisi birinchi, qat'iy kalitlar, narx YO'Q, ko'rinmaydigan qatorlar yo'q,
     `bolimlar`, ETag 304; kalitsiz — 401
  Z  zaxira: eksportda jadvallar; galereya rasmlari tekshiruvi (shakl, ikki jadval orasida takror, boshqa korxonaniki)
  Q  (PG) parallel: ish saqlanayotganda detal o'chirilsa — 500 yo'q, o'chirilgan detalga qator qolmaydi
  U  HAQIQIY Chromium: kartochka, «+ Yangi ish», katalogdan tanlash, saqlash, rasm yuklash, nomdagi HTML — MATN, telefon (390) — gorizontal
     aylanish yo'q, JS xatosi yo'q
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL` bilan HAQIQIY PostgreSQL 16 (Q faqat PG da).
Asl kodga (zip 242) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_galereya243.py
"""
import os
import io
import re
import sys
import json
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"galereya243_test_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t243_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't243.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
# sinov rasm papkasi — har yurishning o'z vaqtinchalik papkasida (etalon tf0 / tf1 parallel — zip 232 saboqi)
DOKON_DISK = os.path.join(_T, "uploads", "dokon")
if hasattr(crud, "dokon_rasm_papkasi"):
    crud.dokon_rasm_papkasi = lambda: DOKON_DISK
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, ActivityLog     # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from PIL import Image                              # noqa: E402

G = getattr(models, "DokonGalereya", None)
GQ = getattr(models, "DokonGalereyaQator", None)
GR = getattr(models, "DokonGalereyaRasm", None)
YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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


def js(r):
    try:
        x = r.json()
        return x if isinstance(x, (dict, list)) else {}
    except Exception:                      # noqa: BLE001
        return {}


def xavfsiz(fn, std=None):
    s = SessionLocal()
    try:
        return fn(s)
    except Exception:                      # noqa: BLE001
        return std
    finally:
        s.close()


def soni(M, **f):
    if M is None:
        return -1
    return xavfsiz(lambda d: d.query(M).filter_by(**f).count(), -1)


def jurnal(tur):
    return xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == tur).count(), -1)


for _n in ("_send_telegram", "_send_telegram_to", "_send_telegram_document", "_send_telegram_to_qoplamachi"):
    if hasattr(main, _n):
        setattr(main, _n, lambda *a, **k: False)

s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T243 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t243_admin", PAROL, UserRole.ADMIN, "T243 Admin", company_id=1)
    auth.create_user(s, "t243_plat", PAROL, UserRole.ADMIN, "T243 Platforma", company_id=1)
    auth.create_user(s, "t243_men", PAROL, UserRole.MANAGER, "T243 Menejer", company_id=1)
    auth.create_user(s, "t243_b", PAROL, UserRole.ADMIN, "T243 B Admin", company_id=2)
s.query(User).filter(User.username == "t243_plat").first().is_platform_admin = True
s.commit()
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA, CP, CM, CB = (mijoz(x) for x in ("t243_admin", "t243_plat", "t243_men", "t243_b"))
OCHIQ = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
GL = API + "/galereya"


def jpeg_gps(w=900, h=600, rang=(180, 120, 60)):
    im = Image.new("RGB", (w, h), rang)
    ex = Image.Exif()
    ex[0x8825] = {1: "N", 2: (40.0, 47.0, 0.0), 3: "E", 4: (72.0, 20.0, 0.0)}
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90, exif=ex.tobytes())
    return buf.getvalue()


def yukla(gid, bayt=None, nom="uy.jpg", c=None):
    return (c or CA).post(f"{GL}/{gid}/rasmlar", files={"fayl": (nom, bayt or jpeg_gps(), "image/jpeg")})


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("S1 jadvallar: dokon_galereya (gl_nomi, gl_joyi, gl_oy — Date, yoqilgan), dokon_galereya_qatorlari (model_id, detal_id NULL bo'ladi, "
      "glq_kmp_*, glq_miqdor Numeric(12, 3)), dokon_galereya_rasmlari (fayl / kichik — yagona)",
      lambda: G.__tablename__ == "dokon_galereya" and {"gl_nomi", "gl_joyi", "gl_oy", "yoqilgan"} <= set(G.__table__.c.keys())
      and str(G.__table__.c.gl_oy.type) == "DATE" and GQ.__table__.c.detal_id.nullable and not GQ.__table__.c.model_id.nullable
      and {"glq_kmp_turi", "glq_kmp_olcham", "glq_kmp_toliq"} <= set(GQ.__table__.c.keys())
      and (GQ.__table__.c.glq_miqdor.type.precision, GQ.__table__.c.glq_miqdor.type.scale) == (12, 3)
      and GR.__table__.c.fayl.unique and GR.__table__.c.kichik.unique)
check("S2 korxona qoidalari: qator / rasm — o'z ishidan; qator — o'z korxonasining modeli va detaliga",
      lambda: models._TENANT_RULES.get("DokonGalereyaQator") == [("galereya_id", "DokonGalereya")]
      and models._TENANT_RULES.get("DokonGalereyaRasm") == [("galereya_id", "DokonGalereya")]
      and ("model_id", "DokonModel") in models._TENANT_REFS.get("DokonGalereyaQator", [])
      and ("detal_id", "DokonDetal") in models._TENANT_REFS.get("DokonGalereyaQator", []))
_tart = [m.__name__ for m in (crud._reset_table_order() or [])]
check("S3 o'chirish tartibi: galereya qatori va rasmi → ish → detal → model (tiklashda teskari)",
      lambda: _tart.index("DokonGalereyaQator") < _tart.index("DokonGalereya") < _tart.index("DokonDetal") < _tart.index("DokonModel")
      and _tart.index("DokonGalereyaRasm") < _tart.index("DokonGalereya"), _tart[-12:])
_yollar = {(getattr(r, "path", None), m) for r in main.app.routes for m in (getattr(r, "methods", None) or ())}
check("S4 marshrutlar: GET / POST galereya, PUT / DELETE ish, rasm POST / PUT tartib / DELETE, do'kon API GET /api/dokon/v1/galereya",
      {(GL, "GET"), (GL, "POST"), (GL + "/{galereya_id}", "PUT"), (GL + "/{galereya_id}", "DELETE"),
       (GL + "/{galereya_id}/rasmlar", "POST"), (GL + "/{galereya_id}/rasmlar", "PUT"),
       (API + "/galereya-rasmlari/{rasm_id}", "DELETE"), ("/api/dokon/v1/galereya", "GET")} <= _yollar)
check("S5 rasm jadvallari — ikkalasi (fayl o'chirish / ochiq berish / yetim / zaxira bitta ro'yxatdan)",
      lambda: [x.__name__ for x in crud._dokon_rasm_jadvallari()] == ["DokonRasm", "DokonGalereyaRasm"])
_html = open(os.path.join(ROOT, "templates", "sayt_katalogi.html"), encoding="utf-8").read()
check("S6 sahifa: «🏠 Bajarilgan ishlar (galereya)» shtorkasi (`data-sht=\"sk-gl\"`), «+ Yangi ish», skGlYukla / skGlSaqla / skGlRasmYukla",
      'data-sht="sk-gl"' in _html and "Bajarilgan ishlar (galereya)" in _html and 'id="skGlYangi"' in _html
      and all(f"function {f}(" in _html for f in ("skGlYukla", "skGlSaqla", "skGlRasmYukla", "skGlChiz")))
_fn = re.search(r"function skGlBoshHtml\(g, och\) \{.*?\n\}\n", _html, re.S)
check("S7 ish sarlavhasida server matni — escapeHtml orqali (nomi, joyi, eslatma)",
      _fn is not None and "escapeHtml(g.nomi)" in _fn.group(0) and "escapeHtml(meta)" in _fn.group(0)
      and "escapeHtml(g.eslatma.join(', '))" in _fn.group(0))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Kirish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = [CA.get(GL).status_code, CA.post(GL, json={"nomi": "X"}).status_code]
check("A1 katalog o'chiq: ro'yxat 404, yaratish 404", _r == [404, 404], _r)
r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
check("A0 platforma: korxona 1 da sayt katalogi yoqildi", r.status_code == 200, r.text[:200])
K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}


def model(bolim, kod, **kw):
    return js(CA.post(API + "/modellar", json=dict({"bolim_id": bolim, "kod": kod}, **kw))).get("id")


def detal(mid, turi, olcham, **kw):
    return js(CA.post(API + "/detallar", json=dict({"model_id": mid, "turi": turi, "olcham": olcham}, **kw))).get("id")


M_K = model(BOL.get("Karnizlar"), "K-3", nom="Tekis")
D_K15 = detal(M_K, "asosiy", "15 sm", narx=120000, eni_sm=15, qalinligi_sm=8)
D_K20 = detal(M_K, "asosiy", "20 sm", narx=140000, eni_sm=20, qalinligi_sm=8)
M_D = model(BOL.get("Dekor elementlar"), "D-4", nom="Kronshteyn")
D_D4 = detal(M_D, "asosiy", "Bitta o'lcham", narx=45000)
M_R = model(BOL.get("Rom va eshik dekorlari"), "R-12", nom="Klassik", kapitel_baza_bor=True)
for _t in ("karniz", "podokonnik", "nalichnik", "kapitel", "baza"):
    detal(M_R, _t, "O'rta", narx=50000, eni_sm=15, qalinligi_sm=8)
    detal(M_R, _t, "Katta", narx=60000, eni_sm=18, qalinligi_sm=8)
M_R2 = model(BOL.get("Rom va eshik dekorlari"), "R-15", nom="Oddiy", kapitel_baza_bor=False)
for _t in ("karniz", "podokonnik", "nalichnik"):
    detal(M_R2, _t, "Kichik", narx=40000, eni_sm=12, qalinligi_sm=8)
_D_R_ORTA = xavfsiz(lambda d: d.query(models.DokonDetal).filter_by(model_id=M_R, turi="karniz", olcham="O'rta").first().id)
check("A2 katalog tayyorlandi (karniz, dekor, ikki komplekt modeli)", all([M_K, D_K15, D_K20, M_D, D_D4, M_R, M_R2, _D_R_ORTA]))

_B_DET = None

_r = [CM.get(GL).status_code, CM.post(GL, json={"nomi": "M"}).status_code]
check("A3 Menejer — 403 (faqat Admin)", _r == [403, 403], _r)
check("A4 B korxona — katalog o'chiq (404), A ishi ko'rinmaydi", CB.get(GL).status_code == 404)
# B korxonada ham katalog yoqiladi (bazadan — platforma yo'li faqat platforma korxonasiga): korxona ajratish HAQIQIY sinalsin (mut243 M01)
xavfsiz(lambda d: (d.query(Company).filter(Company.id == 2).update({"dokon_yoqilgan": True}), d.commit()))
check("A5 B korxonada katalog yoqildi — B ro'yxati 200 va BO'SH", CB.get(GL).status_code == 200 and js(CB.get(GL)).get("galereya") == [])
# B korxona detali — B ning o'z API si bilan (mut243 M02: begona detal / model qulf ostida ham korxona bilan tekshirilsin)
_BBID = js(CB.post(API + "/bolimlar", json={"nom": "B karnizlar", "qolip": "juft_metr"})).get("id")
_BBK = js(CB.post(API + "/bolimlar", json={"nom": "B romlar", "qolip": "komplekt"})).get("id")
_BM = js(CB.post(API + "/modellar", json={"bolim_id": _BBID, "kod": "BK-1"})).get("id")
_BMK = js(CB.post(API + "/modellar", json={"bolim_id": _BBK, "kod": "BR-1"})).get("id")
js(CB.post(API + "/detallar", json={"model_id": _BMK, "turi": "karniz", "olcham": "O'rta", "narx": 1000, "eni_sm": 10, "qalinligi_sm": 8}))
_B_DET = js(CB.post(API + "/detallar", json={"model_id": _BM, "turi": "asosiy", "olcham": "10 sm", "narx": 1000, "eni_sm": 10,
                                             "qalinligi_sm": 8})).get("id")
check("A6 B korxona katalogida model, detal va komplekt modeli (begona sinovi uchun)", bool(_BM and _B_DET and _BMK), (_BM, _B_DET, _BMK))
# 31 xil detal — qatorlar chegarasi takrorsiz sinalsin (mut243 M08)
M_31 = model(BOL.get("Karnizlar"), "K-31", nom="Chegara")
D_31 = [detal(M_31, "asosiy", f"{10 + i} sm", narx=10000, eni_sm=10 + i, qalinligi_sm=8) for i in range(31)]

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. Saqlash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TANA1 = {"nomi": "Ikki qavatli uy fasadi", "joyi": "Andijon sh.", "oy": "2026-09", "yoqilgan": True,
         "qatorlar": [{"detal_id": D_K15, "miqdor": 36},
                      {"detal_id": D_D4, "miqdor": 16},
                      {"model_id": M_R, "komplekt_turi": "rom", "komplekt_olcham": "O’rta", "komplekt_toliq": True, "miqdor": 8},
                      {"model_id": M_R2, "komplekt_turi": "eshik", "komplekt_olcham": "Kichik", "komplekt_toliq": True, "miqdor": 2}]}
_j0 = jurnal("dokon_galereya")
r = CA.post(GL, json=TANA1)
G1 = js(r).get("id")
check("G1 yangi ish (detal juft metr 36, dona 16, rom komplekti, eshik komplekti) — 200", r.status_code == 200 and G1, r.text[:300])
L = js(CA.get(GL))
g1 = next((x for x in (L.get("galereya") or []) if x.get("id") == G1), {})
q = g1.get("qatorlar") or []
check("G2 ro'yxatda: nomi / joyi / oy «2026-09» / «2026, sentyabr» / 4 qator tartibda; nom — katalogdan (o'lcham HAR DOIM — review243 L4)",
      g1.get("nomi") == "Ikki qavatli uy fasadi" and g1.get("joyi") == "Andijon sh." and g1.get("oy") == "2026-09"
      and g1.get("oy_matni") == "2026, sentyabr" and [x.get("nom") for x in q] ==
      ["K-3 Tekis · 15 sm", "D-4 Kronshteyn · Bitta o'lcham", "R-12 Klassik — Rom komplekti, O'rta", "R-15 Oddiy — Eshik komplekti, Kichik"], q)
check("G3 komplekt o'lchami katalogdagi yozilishida («O’rta» → «O'rta»); kapitel / bazasiz model — toliq = False; birliklar",
      [x.get("komplekt_olcham") for x in q[2:]] == ["O'rta", "Kichik"] and [x.get("komplekt_toliq") for x in q[2:]] == [True, False]
      and [x.get("birlik") for x in q] == ["metr", "dona", "komplekt", "komplekt"] and q[0].get("miqdor") == 36, q)
check("G4 rasmsiz ish — «saytda» emas, eslatmada «rasm yo'q»; jurnalda «created»",
      g1.get("saytda") is False and "rasm yo'q" in (g1.get("eslatma") or []) and jurnal("dokon_galereya") == _j0 + 1, g1)

_q0, _g0 = soni(GQ), soni(G)
YOMON = [
    ("bo'sh nom", dict(TANA1, nomi="  ")),
    ("oy 13", dict(TANA1, oy="2026-13")),
    ("oy 1999", dict(TANA1, oy="1999-12")),
    ("oy matn", dict(TANA1, oy="sentyabr")),
    ("oy son", dict(TANA1, oy=202609)),
    ("miqdor 0", dict(TANA1, qatorlar=[{"detal_id": D_K15, "miqdor": 0}])),
    ("miqdor manfiy", dict(TANA1, qatorlar=[{"detal_id": D_K15, "miqdor": -2}])),
    ("miqdor matn", dict(TANA1, qatorlar=[{"detal_id": D_K15, "miqdor": "5"}])),
    ("miqdor bool", dict(TANA1, qatorlar=[{"detal_id": D_K15, "miqdor": True}])),
    ("miqdor juda katta", dict(TANA1, qatorlar=[{"detal_id": D_K15, "miqdor": 10 ** 400}])),
    ("dona kasr", dict(TANA1, qatorlar=[{"detal_id": D_D4, "miqdor": 2.5}])),
    ("juft metrda toq (review243 M1)", dict(TANA1, qatorlar=[{"detal_id": D_K15, "miqdor": 35}])),
    ("juft metrda kasr", dict(TANA1, qatorlar=[{"detal_id": D_K15, "miqdor": 36.5}])),
    ("komplekt 501 (do'kon chegarasi 500)", dict(TANA1, qatorlar=[{"model_id": M_R, "komplekt_turi": "rom", "komplekt_olcham": "Katta", "komplekt_toliq": True, "miqdor": 501}])),
    ("dona 10 001 (do'kon chegarasi 10 000)", dict(TANA1, qatorlar=[{"detal_id": D_D4, "miqdor": 10001}])),
    ("oy arabcha raqam (review243 L7)", dict(TANA1, oy="\u0662\u0660\u0662\u0666-\u0660\u0669")),
    ("komplekt kasr", dict(TANA1, qatorlar=[{"model_id": M_R, "komplekt_turi": "rom", "komplekt_olcham": "Katta", "komplekt_toliq": True, "miqdor": 1.5}])),
    ("takror detal", dict(TANA1, qatorlar=[{"detal_id": D_K15, "miqdor": 2}, {"detal_id": D_K15, "miqdor": 4}])),
    ("takror komplekt", dict(TANA1, qatorlar=[{"model_id": M_R, "komplekt_turi": "rom", "komplekt_olcham": "Katta", "komplekt_toliq": True, "miqdor": 1},
                                             {"model_id": M_R, "komplekt_turi": "rom", "komplekt_olcham": "katta", "komplekt_toliq": True, "miqdor": 2}])),
    ("ortiqcha maydon", dict(TANA1, narx=5)),
    ("qatorda ortiqcha maydon", dict(TANA1, qatorlar=[{"detal_id": D_K15, "miqdor": 2, "narx": 1}])),
    ("31 qator (31 xil detal)", dict(TANA1, qatorlar=[{"detal_id": x, "miqdor": 2} for x in D_31])),
    ("begona (B) detal", dict(TANA1, qatorlar=[{"detal_id": _B_DET or 999999, "miqdor": 2}])),
    ("begona (B) komplekt modeli", dict(TANA1, qatorlar=[{"model_id": _BMK or 999999, "komplekt_turi": "rom", "komplekt_olcham": "O'rta", "komplekt_toliq": False, "miqdor": 1}])),
    ("yo'q detal", dict(TANA1, qatorlar=[{"detal_id": 2_000_000_000, "miqdor": 2}])),
    ("komplekt emas model", dict(TANA1, qatorlar=[{"model_id": M_K, "komplekt_turi": "rom", "komplekt_olcham": "15 sm", "komplekt_toliq": False, "miqdor": 1}])),
    ("komplekt turi", dict(TANA1, qatorlar=[{"model_id": M_R, "komplekt_turi": "arka", "komplekt_olcham": "Katta", "komplekt_toliq": True, "miqdor": 1}])),
    ("komplekt o'lchami yo'q", dict(TANA1, qatorlar=[{"model_id": M_R, "komplekt_turi": "rom", "komplekt_olcham": "Gigant", "komplekt_toliq": True, "miqdor": 1}])),
    ("toliq bool emas", dict(TANA1, qatorlar=[{"model_id": M_R, "komplekt_turi": "rom", "komplekt_olcham": "Katta", "komplekt_toliq": 1, "miqdor": 1}])),
    ("detal + komplekt maydoni", dict(TANA1, qatorlar=[{"detal_id": D_K15, "komplekt_turi": "rom", "miqdor": 1}])),
    ("qatorlar ro'yxat emas", dict(TANA1, qatorlar={"detal_id": D_K15})),
]
_yom = {n: CA.post(GL, json=t).status_code for n, t in YOMON}
check("G5 noto'g'ri qiymatlar (31 holat) — hammasi 400", all(v == 400 for v in _yom.values()), _yom)
check("G6 … va HECH NARSA yozilmadi (ish ham, qator ham)", soni(G) == _g0 and soni(GQ) == _q0, (soni(G), _g0, soni(GQ), _q0))
_rb = [CA.post(GL, json=dict(TANA1, qatorlar=[{"detal_id": _B_DET or 999999, "miqdor": 2}])),
       CA.post(GL, json=dict(TANA1, qatorlar=[{"model_id": _BMK or 999999, "komplekt_turi": "rom", "komplekt_olcham": "O'rta",
                                               "komplekt_toliq": False, "miqdor": 1}]))]
check("G15 begona detal / komplekt modeli — o'z korxonasi qoidasi bilan rad (aniq xabar: «katalogda bunday o'lcham / model yo'q»)",
      "katalogda bunday o'lcham yo'q" in _rb[0].text and "katalogda bunday model yo'q" in _rb[1].text, [x.text[:120] for x in _rb])
r = CA.post(GL, json=dict(TANA1, qatorlar=[{"detal_id": D_K15, "miqdor": 2}, {"detal_id": D_K15, "miqdor": 4}]))
check("G7 takror xabari — qator raqami va nomi bilan", r.status_code == 400 and "ikki marta" in r.text and "K-3 Tekis · 15 sm" in r.text, r.text[:200])

_j1 = jurnal("dokon_galereya")
r = CA.put(f"{GL}/{G1}", json=TANA1)
check("G8 o'zgarishsiz saqlash — 200, jurnalga YOZILMAYDI", r.status_code == 200 and jurnal("dokon_galereya") == _j1)
r = CA.put(f"{GL}/{G1}", json={"joyi": "Asaka tumani", "qatorlar": [{"detal_id": D_K20, "miqdor": 10}, {"detal_id": D_K15, "miqdor": 36}]})
g1 = next((x for x in js(CA.get(GL)).get("galereya", []) if x.get("id") == G1), {})
check("G9 tahrir: joyi va qatorlar to'liq almashadi (tartib — yuborilgandek), nom / oy — o'zgarmaydi; jurnalda «updated»",
      r.status_code == 200 and g1.get("joyi") == "Asaka tumani" and g1.get("nomi") == TANA1["nomi"] and g1.get("oy") == "2026-09"
      and [x.get("detal_id") for x in g1.get("qatorlar", [])] == [D_K20, D_K15] and jurnal("dokon_galereya") == _j1 + 1, g1)
_jm = xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == "dokon_galereya").order_by(ActivityLog.id.desc()).first().new_value, "")
check("G10 jurnal matnida o'zgargan maydonlar va mahsulotlar (nom — miqdor)",
      "joyi" in _jm and "mahsulotlar" in _jm and "K-3 Tekis · 15 sm — 36" in _jm and "K-3 Tekis · 20 sm — 10" in _jm, _jm)
r = CA.put(f"{GL}/{G1}", json={"oy": None})
check("G11 oyni olib tashlash — oy null, «oy_matni» null",
      r.status_code == 200 and next((x for x in js(CA.get(GL)).get("galereya", []) if x.get("id") == G1), {}).get("oy") is None)
CA.put(f"{GL}/{G1}", json={"oy": "2026-09"})
_r = [CA.put(f"{GL}/2000000000", json={"nomi": "X"}).status_code, CA.delete(f"{GL}/2000000000").status_code,
      CA.put(f"{GL}/0", json={"nomi": "X"}).status_code]
check("G12 yo'q ish — 404, 0 — 422", _r == [404, 404, 422], _r)
check("G13 B korxona (katalogi yoqiq) A ishini o'zgartira / o'chira / rasm qo'sha olmaydi (404), A ishi o'zgarmadi",
      [CB.put(f"{GL}/{G1}", json={"nomi": "B"}).status_code, CB.delete(f"{GL}/{G1}").status_code,
       CB.post(f"{GL}/{G1}/rasmlar", files={"fayl": ("b.jpg", jpeg_gps(), "image/jpeg")}).status_code] == [404, 404, 404]
      and soni(G, id=G1) == 1 and next((x for x in js(CA.get(GL)).get("galereya", []) if x.get("id") == G1), {}).get("nomi") == TANA1["nomi"])
check("G14 30 xil detal — chegara ichida (200)", CA.post(GL, json=dict(TANA1, nomi="30 qator", qatorlar=[{"detal_id": x, "miqdor": 2} for x in D_31[:30]])).status_code == 200)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Rasmlar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = yukla(G1)
R1 = js(r)
_yol = crud.dokon_rasm_yoli(R1.get("url")) if R1.get("url") else None
check("R1 rasm yuklandi: manzil shakli, fayl diskda, kichik nusxa bor", r.status_code == 200 and _yol and os.path.isfile(_yol)
      and os.path.isfile(crud.dokon_rasm_yoli(R1.get("kichik"))), r.text[:200])
check("R2 GPS (EXIF) yo'q — rasm qayta yozilgan", lambda: 0x8825 not in Image.open(_yol).getexif())
_o = OCHIQ.get(R1["url"]) if R1.get("url") else None
check("R3 ochiq manzil login siz — 200 (galereya rasmi ham ochiq beriladi)", lambda: _o.status_code == 200 and len(_o.content) > 100)
_rids = [R1.get("id")] + [js(yukla(G1, jpeg_gps(rang=(i * 20, 90, 90)), f"u{i}.jpg")).get("id") for i in range(9)]
r = yukla(G1, nom="ortiqcha.jpg")
check("R4 10 ta rasm bor — 11-si 400 (xabarda ish nomi), papkada ortiqcha fayl qolmadi",
      all(_rids) and r.status_code == 400 and "Ikki qavatli uy fasadi" in r.text
      and len([f for f in os.listdir(DOKON_DISK) if f.endswith(".jpg")]) == 20, (r.status_code, r.text[:150]))
_yangi = [_rids[3]] + [x for x in _rids if x != _rids[3]]
r = CA.put(f"{GL}/{G1}/rasmlar", json={"tartib": _yangi})
check("R5 tartib: 4-rasm asosiy bo'ldi", r.status_code == 200 and [x.get("id") for x in js(r).get("rasmlar", [])] == _yangi, r.text[:200])
check("R6 tartib — ro'yxat mos emas / takror / ortiqcha maydon — 400",
      [CA.put(f"{GL}/{G1}/rasmlar", json={"tartib": _yangi[:-1]}).status_code,
       CA.put(f"{GL}/{G1}/rasmlar", json={"tartib": _yangi[:-1] + [_yangi[0]]}).status_code,
       CA.put(f"{GL}/{G1}/rasmlar", json={"tartib": _yangi, "x": 1}).status_code] == [400, 400, 400])
_r9 = xavfsiz(lambda d: next(x for x in next(g for g in js(CA.get(GL))["galereya"] if g["id"] == G1)["rasmlar"] if x["id"] == _rids[9]), {})
r = CA.delete(f"{API}/galereya-rasmlari/{_rids[9]}")
check("R7 rasm o'chirildi — fayllari ham (commit dan keyin)", lambda: r.status_code == 200 and not os.path.exists(crud.dokon_rasm_yoli(_r9["url"]))
      and not os.path.exists(crud.dokon_rasm_yoli(_r9["kichik"])))
check("R8 B korxona A rasmini o'chira olmaydi (404)", CB.delete(f"{API}/galereya-rasmlari/{_rids[8]}").status_code == 404)
# yetim fayl tozalash — galereya fayliga tegmaydi, yozuvsiz eskisi o'chadi
os.makedirs(DOKON_DISK, exist_ok=True)
_yetim = os.path.join(DOKON_DISK, "a" * 32 + ".jpg")
open(_yetim, "wb").write(b"x")
_eski = time.time() - 7200
for _f in os.listdir(DOKON_DISK):
    os.utime(os.path.join(DOKON_DISK, _f), (_eski, _eski))
_n = xavfsiz(lambda d: crud.dokon_yetim_fayllar_tozala(d), -1)
check("R9 yetim fayllar: yozuvsiz eski fayl o'chdi, galereya rasmlari (18 fayl) QOLDI",
      _n == 1 and not os.path.exists(_yetim) and len([f for f in os.listdir(DOKON_DISK) if f.endswith(".jpg")]) == 18, _n)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Do'kon API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
KALIT = js(CA.post(API + "/api-kalit", json={})).get("kalit")
DH = {"X-Dokon-Kalit": KALIT or "pdk_x"}


def dapi(**h):
    if hasattr(crud, "_DOKON_API_CHEKLOV"):
        crud._DOKON_API_CHEKLOV.tozala()
    return OCHIQ.get("/api/dokon/v1/galereya", headers=dict(DH, **h))


G2 = js(CA.post(GL, json={"nomi": "Ustunli kirish qismi", "joyi": "Asaka tumani", "oy": "2026-10",
                          "qatorlar": [{"detal_id": D_D4, "miqdor": 4}]})).get("id")
G3 = js(CA.post(GL, json={"nomi": "Rasmsiz ish", "oy": "2026-11", "qatorlar": [{"detal_id": D_D4, "miqdor": 4}]})).get("id")
G4 = js(CA.post(GL, json={"nomi": "Yashirin ish", "oy": "2026-12", "yoqilgan": False, "qatorlar": []})).get("id")
G5 = js(CA.post(GL, json={"nomi": "Sanasiz ish", "qatorlar": []})).get("id")
for _g in (G2, G4, G5):
    yukla(_g)
r = dapi()
A = js(r)
check("D1 kalit bilan 200; kalitsiz — 401", r.status_code == 200 and OCHIQ.get("/api/dokon/v1/galereya").status_code == 401, r.text[:200])
check("D2 faqat yoqilgan va rasmi bor ishlar, yangisi birinchi (oy kamayib, sanasizi oxirida): G2, G1, G5",
      [x.get("id") for x in A.get("galereya", [])] == [G2, G1, G5], [x.get("id") for x in A.get("galereya", [])])
_a1 = next((x for x in A.get("galereya", []) if x.get("id") == G1), {})
check("D3 qat'iy kalitlar: javob {versiya, galereya}; ish {id, nomi, joyi, oy, oy_matni, rasmlar, bolimlar, qatorlar}; qator — narxsiz",
      set(A) == {"versiya", "galereya"} and set(_a1) == {"id", "nomi", "joyi", "oy", "oy_matni", "rasmlar", "bolimlar", "qatorlar"}
      and all(set(x) == {"model_id", "model_kod", "model_nom", "bolim_id", "detal_id", "turi", "olcham", "birlik", "komplekt", "nom", "miqdor"}
              for x in _a1.get("qatorlar", []))
      and "narx" not in json.dumps(A) and "ulgurji" not in json.dumps(A), _a1)
check("D4 rasmlar — asosiysi birinchi, {url, kichik, eni, boyi} (hajm / id yo'q); bolimlar — ishlatilgan bo'limlar",
      [set(x) for x in _a1.get("rasmlar", [])][:1] == [{"url", "kichik", "eni", "boyi"}] and len(_a1.get("rasmlar", [])) == 9
      and _a1.get("bolimlar") == [BOL.get("Karnizlar")], _a1.get("bolimlar"))
_et = r.headers.get("etag")
check("D5 ETag — o'zgarmasa 304", _et and dapi(**{"If-None-Match": _et}).status_code == 304)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Bog'liqlik (katalog o'zgarsa)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
G6 = js(CA.post(GL, json={"nomi": "Bog'liqlik sinovi", "oy": "2025-05", "qatorlar": [
    {"detal_id": D_K15, "miqdor": 6}, {"detal_id": D_K20, "miqdor": 8}, {"detal_id": D_D4, "miqdor": 3},
    {"model_id": M_R, "komplekt_turi": "rom", "komplekt_olcham": "Katta", "komplekt_toliq": False, "miqdor": 2}]})).get("id")
yukla(G6)


def g6():
    return next((x for x in js(CA.get(GL)).get("galereya", []) if x.get("id") == G6), {})


def a6():
    return next((x for x in js(dapi()).get("galereya", []) if x.get("id") == G6), {})


check("B0 G6 — 4 qator saytda", len(a6().get("qatorlar", [])) == 4 and g6().get("eslatma") == [], a6())
CA.put(f"{API}/detallar/{D_K20}", json={"yoqilgan": False})
_s = [x.get("sabab") for x in g6().get("qatorlar", [])]
check("B1 detal yashirildi — qator qoladi, sababi «20 sm o'lchami yashirilgan», saytga BERILMAYDI",
      lambda: _s[1] == "20 sm o'lchami yashirilgan" and [x.get("detal_id") for x in a6().get("qatorlar", [])] == [D_K15, D_D4, None], (_s, a6()))
CA.put(f"{API}/detallar/{D_K20}", json={"yoqilgan": True})
CA.put(f"{API}/modellar/{M_D}", json={"yoqilgan": False})
check("B2 model yashirildi — sabab «D-4 modeli yashirilgan», saytda yo'q",
      lambda: g6().get("qatorlar", [{}] * 3)[2].get("sabab") == "D-4 modeli yashirilgan"
      and D_D4 not in [x.get("detal_id") for x in a6().get("qatorlar", [])])
CA.put(f"{API}/modellar/{M_D}", json={"yoqilgan": True})
for _d in xavfsiz(lambda d: [x.id for x in d.query(models.DokonDetal).filter_by(model_id=M_R, olcham="Katta").all()], []):
    CA.put(f"{API}/detallar/{_d}", json={"yoqilgan": False})
check("B3 komplekt o'lchami yashirildi — sabab, saytda yo'q",
      lambda: "o'lchami modelda yo'q yoki yashirilgan" in str(g6().get("qatorlar", [{}] * 4)[3].get("sabab"))
      and None not in [x.get("detal_id") for x in a6().get("qatorlar", [])], g6().get("qatorlar"))
# review243 M3: komplekt o'lchami qayta nomlansa — galereya qatori yangi nomga (oxirgi qatori nomlangach)
G8 = js(CA.post(GL, json={"nomi": "Nom sinovi", "qatorlar": [
    {"model_id": M_R2, "komplekt_turi": "eshik", "komplekt_olcham": "Kichik", "komplekt_toliq": False, "miqdor": 2}]})).get("id")
_k_ids = xavfsiz(lambda d: [x.id for x in d.query(models.DokonDetal).filter_by(model_id=M_R2, olcham="Kichik").order_by(models.DokonDetal.id).all()], [])
_r2 = lambda: next((x for x in next((g for g in js(CA.get(GL)).get("galereya", []) if g.get("id") == G8), {}).get("qatorlar", [])   # noqa: E731
                    if x.get("model_id") == M_R2), {})
CA.put(f"{API}/detallar/{_k_ids[0]}", json={"olcham": "Mitti"}) if _k_ids else None
_ol1 = _r2().get("komplekt_olcham")
for _x in _k_ids[1:]:
    CA.put(f"{API}/detallar/{_x}", json={"olcham": "Mitti"})
check("B6 komplekt o'lchami qayta nomlandi (3 qator bittalab): birinchisidan keyin — eski nom, oxirgisidan keyin — «Mitti», saytda ko'rinadi",
      lambda: len(_k_ids) == 3 and _ol1 == "Kichik" and _r2().get("komplekt_olcham") == "Mitti" and _r2().get("sabab") is None, (_ol1, _r2()))
# review243 M4: kapitel / baza o'chirilsa — «to'liq» va «bazasiz» komplekt bitta bo'ladi, ish saqlanadi
G7 = js(CA.post(GL, json={"nomi": "Kapitel sinovi", "qatorlar": [
    {"model_id": M_R, "komplekt_turi": "rom", "komplekt_olcham": "O'rta", "komplekt_toliq": True, "miqdor": 2},
    {"model_id": M_R, "komplekt_turi": "rom", "komplekt_olcham": "O'rta", "komplekt_toliq": False, "miqdor": 3}]})).get("id")
for _x in xavfsiz(lambda d: [x.id for x in d.query(models.DokonDetal).filter(models.DokonDetal.model_id == M_R,
                                                                            models.DokonDetal.turi.in_(("kapitel", "baza"))).all()], []):
    CA.delete(f"{API}/detallar/{_x}")
r = CA.put(f"{API}/modellar/{M_R}", json={"kapitel_baza_bor": False})
_g7 = next((g for g in js(CA.get(GL)).get("galereya", []) if g.get("id") == G7), {})
check("B7 kapitel / baza o'chirildi — ikki komplekt qatori bittaga birlashdi (toliq = False), ish o'zgarishsiz saqlanadi",
      lambda: r.status_code == 200 and [(x.get("komplekt_toliq"), x.get("miqdor")) for x in _g7.get("qatorlar", [])] == [(False, 2)]
      and CA.put(f"{GL}/{G7}", json={"nomi": "Kapitel sinovi 2"}).status_code == 200, (r.status_code, _g7.get("qatorlar")))
# review243 M4: qolip o'zgarsa (dona → juft metr) — 3 dona endi «3 m» (toq): sabab, saytda yo'q; qaytarilsa — yana ko'rinadi
CA.put(f"{API}/modellar/{M_D}", json={"qolip": "juft_metr"})
_s8 = next((x.get("sabab") for x in g6().get("qatorlar", []) if x.get("detal_id") == D_D4), "?")
_a8 = [x.get("detal_id") for x in a6().get("qatorlar", [])]
CA.put(f"{API}/modellar/{M_D}", json={"qolip": "dona"})
check("B8 qolip o'zgardi (dona → juft metr): 3 — endi yaroqsiz, sabab «birligiga mos emas», saytda yo'q; qaytarilgach — yana bor",
      lambda: "birligiga mos emas" in str(_s8) and D_D4 not in _a8 and D_D4 in [x.get("detal_id") for x in a6().get("qatorlar", [])], (_s8, _a8))
_jd = jurnal("dokon_detal")
r = CA.delete(f"{API}/detallar/{D_K20}")
_old = xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == "dokon_detal").order_by(ActivityLog.id.desc()).first().old_value, "")
check("B4 detal O'CHIRILDI — galereya qatori ham o'chdi (ish qoldi), jurnalda «galereyadan 2 ta qator» (G1 va G6)",
      r.status_code == 200 and D_K20 not in [x.get("detal_id") for x in g6().get("qatorlar", [])] and g6().get("id") == G6
      and "galereyadan 2 ta qator" in _old and soni(GQ, detal_id=D_K20) == 0, (r.status_code, _old))
# review243 L5: zaxiradan kelgan nomuvofiq qator (model_id — boshqa model, detali — R-12 niki) ham o'chadi (PG da FK 500 bo'lmasin)
_nomuvofiq = xavfsiz(lambda d: (lambda x: (d.add(x), d.commit(), x.id)[-1])(GQ(company_id=1, galereya_id=G6, model_id=M_K, tartib=99,
                     detal_id=d.query(models.DokonDetal).filter_by(model_id=M_R).first().id, glq_miqdor=2)))
r = CA.delete(f"{API}/modellar/{M_R}")
check("B5 model O'CHIRILDI — uning hamma galereya qatorlari (komplekt ham) o'chdi, boshqa qatorlar qoldi",
      r.status_code == 200 and soni(GQ, model_id=M_R) == 0 and _nomuvofiq and soni(GQ, id=_nomuvofiq) == 0
      and [x.get("detal_id") for x in g6().get("qatorlar", [])] == [D_K15, D_D4]
      and len(next((x for x in js(CA.get(GL)).get("galereya", []) if x.get("id") == G1), {}).get("qatorlar", [])) == 1, r.text[:200])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_z = xavfsiz(lambda d: crud.export_full_backup(d, company_id=1), {}) or {}
_tb = _z.get("tables", {})
check("Z1 eksportda dokon_galereya, dokon_galereya_qatorlari, dokon_galereya_rasmlari",
      len(_tb.get("dokon_galereya", [])) >= 5 and len(_tb.get("dokon_galereya_qatorlari", [])) >= 3
      and len(_tb.get("dokon_galereya_rasmlari", [])) >= 10, {k: len(v) for k, v in _tb.items() if "galereya" in k})
_gr = _tb.get("dokon_galereya_rasmlari", [])
_zx = lambda rows, gal: xavfsiz(lambda d: crud.dokon_rasm_zaxira_xatosi(d, rows, 1, galereya_rows=gal), "QULADI")   # noqa: E731
check("Z2 to'g'ri qatorlar — xato yo'q", _zx(_tb.get("dokon_rasmlar", []), _gr) is None, _zx(_tb.get("dokon_rasmlar", []), _gr))
_b1 = ([dict(_gr[0], kichik=_gr[0]["fayl"])] + _gr[1:]) if _gr else [{"fayl": "x"}]
check("Z3 galereya rasmi manzili buzilgan — rad (jadval nomi bilan)", "dokon_galereya_rasmlari" in str(_zx([], _b1)), _zx([], _b1))
_b2 = [{"fayl": _gr[0]["fayl"], "kichik": _gr[0]["kichik"]}] if _gr else []
check("Z4 bir fayl ikki jadvalda (model rasmi va galereya rasmi) — rad", bool(_gr) and "ikki marta" in str(_zx(_b2, _gr)), _zx(_b2, _gr))


_h = None
if not TF and GR is not None:      # TF rejimida korxona qo'riqchisi begona ota bilan yozuvni rad etadi — tekshiruv SQ / PG da
    _h = xavfsiz(lambda d: (lambda b: (d.add(G(company_id=2, gl_nomi="B ish")), d.flush(),
                                       d.add(GR(company_id=2, galereya_id=d.query(G).filter_by(company_id=2).first().id,
                                                fayl=f"/static/uploads/dokon/{b}.jpg", kichik=f"/static/uploads/dokon/{b}_k.jpg",
                                                eni=1, boyi=1, hajm=1, turi="jpeg")), d.commit(), b)[-1])("b" * 32))
    check("Z5 boshqa korxonaning galereya rasmi fayli zaxirada — rad (xabarda dokon_galereya_rasmlari — review243 L7)",
          "dokon_galereya_rasmlari dagi rasm boshqa korxonaga tegishli" in str(_zx([], [{"fayl": f"/static/uploads/dokon/{'b' * 32}.jpg",
                                                       "kichik": f"/static/uploads/dokon/{'b' * 32}_k.jpg"}])), _h)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R2. Ish o'chirish va katalog o'chirish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_u = xavfsiz(lambda d: [x["url"] for x in next(g for g in js(CA.get(GL))["galereya"] if g["id"] == G2)["rasmlar"]], [])
r = CA.delete(f"{GL}/{G2}")
check("R10 ish o'chirildi — qatorlari, rasm yozuvlari va fayllari ham",
      lambda: bool(_u) and r.status_code == 200 and soni(G, id=G2) == 0 and soni(GQ, galereya_id=G2) == 0 and soni(GR, galereya_id=G2) == 0
      and not any(os.path.exists(crud.dokon_rasm_yoli(u)) for u in _u), r.text[:200])
_url1 = xavfsiz(lambda d: next(g for g in js(CA.get(GL))["galereya"] if g["id"] == G1)["rasmlar"][0]["url"], "/static/uploads/dokon/yoq.jpg")
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "0"})
check("R11 katalog o'chirildi — galereya rasmi ochiq manzili 404, API 404",
      _url1 != "/static/uploads/dokon/yoq.jpg" and OCHIQ.get(_url1).status_code == 404 and CA.get(GL).status_code == 404)
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
check("R12 qayta yoqildi — yana 200", OCHIQ.get(_url1).status_code == 200)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Parallel (PG)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    _hol = []
    for i in range(8):
        _d = detal(M_K, "asosiy", f"{30 + i} sm", narx=150000, eni_sm=30 + i, qalinligi_sm=8)
        _gid = js(CA.post(GL, json={"nomi": f"Poyga {i}", "qatorlar": []})).get("id")
        _nat = {}
        _bar = threading.Barrier(2)

        def _saqla():
            _bar.wait()
            _nat["s"] = CA.put(f"{GL}/{_gid}", json={"qatorlar": [{"detal_id": _d, "miqdor": 6}, {"detal_id": D_K15, "miqdor": 2}]}).status_code

        def _ochir():
            _bar.wait()
            _nat["o"] = CA.delete(f"{API}/detallar/{_d}").status_code

        _t = [threading.Thread(target=_saqla), threading.Thread(target=_ochir)]
        [x.start() for x in _t]
        [x.join(30) for x in _t]
        _hol.append((_nat.get("s"), _nat.get("o"), soni(GQ, detal_id=_d)))
    check("Q1 saqlash ↔ detal o'chirish bir vaqtda (8 marta): 500 yo'q, detal o'chdi, o'chirilgan detalga qator qolmadi",
          all(s in (200, 400) and o == 200 and n == 0 for s, o, n in _hol), _hol)
else:
    print("  (PG_URL yo'q — Q o'tkazib yuborildi)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. Brauzer (HAQIQIY Chromium)")
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
    _rasm = os.path.join(_T, "fasad.jpg")
    open(_rasm, "wb").write(jpeg_gps(1200, 800, (90, 120, 160)))
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        try:
            def kir(login, w=1366, h=900):
                ctx = br.new_context(viewport={"width": w, "height": h})
                pg = ctx.new_page()
                jsx = []
                pg.on("pageerror", lambda e: jsx.append(str(e)))
                pg.on("dialog", lambda d: d.dismiss())
                pg.goto(BU + "/login")
                pg.fill("input[name=username]", login)
                pg.fill("input[name=password]", PAROL)
                pg.click("button[type=submit]")
                pg.wait_for_load_state("networkidle")
                pg.goto(BU + "/sayt-katalogi", wait_until="networkidle")
                return ctx, pg, jsx

            ctx, pg, JSX = kir("t243_admin")
            pg.evaluate("document.querySelector('[data-sht=\"sk-gl\"]').open = true")
            pg.wait_for_function("document.querySelectorAll('#skGlRoyxat .sk-gl-ish').length > 0", timeout=10000)
            _u1 = pg.evaluate("""() => ({n: document.querySelectorAll('#skGlRoyxat .sk-gl-ish').length,
                holat: document.getElementById('skGlHolat').textContent,
                birinchi: document.querySelector('#skGlRoyxat .sk-gl-bosh b').textContent})""")
            check("U1 kartochka: ishlar ro'yxati (yangisi birinchi), sarlavhada soni", _u1["n"] >= 4 and "ta ish" in _u1["holat"]
                  and _u1["birinchi"] == "Yashirin ish", _u1)
            pg.click("#skGlYangi")
            pg.fill('[data-glish="yangi"] [data-glm="nomi"]', "Yangi <b>uy</b> fasadi")
            pg.fill('[data-glish="yangi"] [data-glm="joyi"]', "Xo'jaobod tumani")
            pg.fill('[data-glish="yangi"] [data-glm="oy"]', "2026-07")
            pg.select_option('[data-glish="yangi"] [data-gltm]', str(M_K))
            _v = pg.evaluate("Array.from(document.querySelectorAll('[data-glish=\"yangi\"] [data-gltv] option')).map(o => o.textContent)")
            check("U2 model tanlanganda — o'lchamlari ro'yxati (birligi bilan qo'shiladi)", any("15 sm" in x for x in _v), _v)
            pg.select_option('[data-glish="yangi"] [data-gltv]', index=0)
            pg.fill('[data-glish="yangi"] [data-gltq]', "24")
            pg.click('[data-glish="yangi"] [data-gltqosh]')
            _u3 = pg.evaluate("Array.from(document.querySelectorAll('[data-glish=\"yangi\"] .sk-gl-qnom')).map(x => x.textContent)")
            check("U3 «+ Qo'shish» — qator ro'yxatda (katalog nomi)", _u3 == ["K-3 Tekis · 15 sm"], _u3)
            pg.click('[data-glish="yangi"] [data-glsaqla]')
            pg.wait_for_function("!document.querySelector('[data-glish=\"yangi\"]') && document.querySelector('.sk-gl-ish.ochiq [data-glrasm]')", timeout=10000)
            _gid = pg.evaluate("parseInt(document.querySelector('.sk-gl-ish.ochiq').dataset.glish, 10)")
            _bz = next((x for x in js(CA.get(GL)).get("galereya", []) if x.get("id") == _gid), {})
            check("U4 saqlandi: serverda o'sha ish (nom, joy, oy, 24 m), ochiq qoldi — rasm bloki ko'rinadi",
                  _bz.get("nomi") == "Yangi <b>uy</b> fasadi" and _bz.get("joyi") == "Xo'jaobod tumani" and _bz.get("oy") == "2026-07"
                  and [x.get("miqdor") for x in _bz.get("qatorlar", [])] == [24], _bz)
            _u5 = pg.evaluate("""() => { const b = document.querySelector('.sk-gl-ish.ochiq .sk-gl-bosh b');
                return {matn: b.textContent, html: b.innerHTML.indexOf('<b>') >= 0}; }""")
            check("U5 nomdagi HTML — MATN sifatida (teg emas)", _u5["matn"] == "Yangi <b>uy</b> fasadi" and not _u5["html"], _u5)
            pg.set_input_files('.sk-gl-ish.ochiq [data-glrfayl]', _rasm)
            pg.wait_for_function("document.querySelectorAll('.sk-gl-ish.ochiq [data-glrasm] .sk-rasm').length === 1", timeout=20000)
            _u6 = pg.evaluate("""() => { const i = document.querySelector('.sk-gl-ish.ochiq [data-glrasm] .sk-rasm img');
                return {src: i.getAttribute('src'), fit: getComputedStyle(i).objectFit, tugadi: i.complete && i.naturalWidth > 0}; }""")
            check("U6 rasm yuklandi — kichik nusxa, qirqilmagan (object-fit: contain)", _u6["src"].startswith("/static/uploads/dokon/")
                  and _u6["fit"] == "contain", _u6)
            _u6b = pg.evaluate("document.querySelector('.sk-gl-ish.ochiq .sk-gl-bosh').textContent")
            check("U6b sarlavha rasm qo'shilgach yangilandi: «1 ta rasm», «Saytda», rasmi bor (review243 L2)",
                  "1 ta rasm" in _u6b and "Saytda" in _u6b and "ko'rinmaydi" not in _u6b
                  and pg.query_selector(".sk-gl-ish.ochiq .sk-gl-bosh img") is not None, _u6b)
            # yozilayotgan matn rasm amalida yo'qolmaydi
            pg.fill('.sk-gl-ish.ochiq [data-glm="joyi"]', "Saqlanmagan joy")
            pg.click('.sk-gl-ish.ochiq [data-glrsur][data-yon="1"]') if pg.query_selector('.sk-gl-ish.ochiq [data-glrsur][data-yon="1"]:not([disabled])') else None
            check("U7 rasm amali forma maydonidagi saqlanmagan matnni o'chirmaydi; saqlanmagan o'zgarish sezildi (sahifadan chiqishda so'raladi — L6)",
                  pg.input_value('.sk-gl-ish.ochiq [data-glm="joyi"]') == "Saqlanmagan joy" and pg.evaluate("skGlOzgargan()") is True)
            _og = pg.evaluate(f"skGlOgoh({M_K}, null)")
            check("U7b model o'chirish tasdig'ida galereya ogohlantirishi (review243 M2)", "ta ishdan ham olib tashlanadi" in _og, _og)
            pg.select_option('.sk-gl-ish.ochiq [data-gltm]', str(M_K))
            _qd = pg.text_content('.sk-gl-ish.ochiq [data-gltb]')
            check("U7c miqdor qoidasi ko'rsatiladi: juft metr (review243 M1)", "juft" in _qd, _qd)
            check("U8 JS xatosi yo'q", not JSX, JSX)
            ctx.close()
            ctx, pg, JSX = kir("t243_admin", 390, 844)
            pg.evaluate("document.querySelector('[data-sht=\"sk-gl\"]').open = true")
            pg.wait_for_function("document.querySelectorAll('#skGlRoyxat .sk-gl-ish').length > 0", timeout=10000)
            pg.click('#skGlRoyxat .sk-gl-bosh')
            pg.wait_for_timeout(300)
            _u9 = pg.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
                keng: Array.from(document.querySelectorAll('.sk-gl-ish.ochiq *')).filter(e => e.getBoundingClientRect().right > window.innerWidth + 1).length})""")
            check("U9 telefon (390): gorizontal aylanish yo'q, ochiq ish elementlari ekrandan chiqmaydi", _u9["sw"] <= _u9["cw"] and _u9["keng"] == 0, _u9)
            check("U10 telefon — JS xatosi yo'q", not JSX, JSX)
            ctx.close()
        finally:
            br.close()
    server.should_exit = True
except Exception as _e:                    # noqa: BLE001
    check("U! brauzer bo'limi", False, f"{type(_e).__name__}: {_e}")

if PG_URL:
    try:
        from database import engine as _eng
        _eng.dispose()
        _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
