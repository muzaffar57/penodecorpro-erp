#!/usr/bin/env python3
"""
test_mayda247.py — kech180 (zip 247: mayda tuzatishlar — favicon, do'kon API keshi, sayt detal nomi).

NIMA UCHUN KERAK
  O'LCHOV (`work/k247/probe247.py`, asl = zip 246): /favicon.ico — 404; do'kon API (`/api/dokon/v1/…`) 400 / 409 / 413 / 404 / 405 javobida
  Cache-Control YO'Q; nomsiz model + katta harfli o'lcham — ERP buyurtmasida «D-3 · xl» (saytda «D-3 · XL»); o'lcham eni bilan boshlansa —
  «K-12 Tekis · 12 sm · 12 sm (keng)»; partiyasi qolmagan eski bog'lam — «Katalogdan tanlash» forma nomi kichik harfda («d-2 burchak»).
BO'LIMLAR
  F — /favicon.ico. C — do'kon API Cache-Control. N — detal nomi tartibi (« · » dan keyingi qism AYNAN). S — `_sayt_nom` (eni bir marta),
  sayt buyurtmasi, guruh nomi, PDF, ERP buyurtmasi. B — partiyasiz bog'lam nomi (245 / 246 / hozirgi kalit), yangi partiya o'sha kalitga.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
Asl kodga (zip 246) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_mayda247.py
"""
import os
import io
import re
import sys
import json
import tempfile
import contextlib
from datetime import datetime

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"mayda247_{os.getpid()}"            # kech180: parallel PG yurishlari bir-birini o'chirmasin
_T = tempfile.mkdtemp(prefix="t247_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't247.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User                  # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from pypdf import PdfReader                        # noqa: E402

DokonBuyurtma = getattr(models, "DokonBuyurtma", None)
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
    if callable(detail):
        try:
            detail = detail()
        except Exception as e:             # noqa: BLE001
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
        x = r.json()
        return x if isinstance(x, (dict, list)) else {}
    except Exception:                      # noqa: BLE001
        return {}


def xavfsiz(fn, std=None):
    try:
        return fn()
    except Exception:                      # noqa: BLE001
        return std


def matn(r):
    b = getattr(r, "content", r)
    if not isinstance(b, (bytes, bytearray)) or not bytes(b).startswith(b"%PDF"):
        return ""
    try:
        return re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(bytes(b))).pages))
    except Exception:                      # noqa: BLE001
        return ""


def zich(s):
    return re.sub(r"\s+", "", str(s or "")).replace("\xa0", "")


class _SoxtaVaqt:
    t = datetime(2026, 11, 3, 7, 0)          # Toshkent 12:00 — ish vaqti

    @classmethod
    def utcnow(cls):
        return cls.t


if getattr(crud, "_dt233", None) is not None:
    crud._dt233 = _SoxtaVaqt
TG = []
main._send_telegram = lambda *a, **k: TG.append(" ".join(str(x) for x in a)) or True

s = SessionLocal()
_c1 = s.get(Company, 1)
_c1.name = "T247 Penodekor"
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t247_admin", PAROL, UserRole.ADMIN, "T247 Admin", company_id=1)
    auth.create_user(s, "t247_plat", PAROL, UserRole.ADMIN, "T247 Platforma", company_id=1)
s.query(User).filter(User.username == "t247_plat").first().is_platform_admin = True
s.add(models.Recipe(company_id=1, name="Qoplama T247"))
s.commit()
RID = s.query(models.Recipe.id).filter(models.Recipe.company_id == 1).scalar()
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t247_admin")
CP = mijoz("t247_plat")
DOK = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
BY = "/api/dokon/v1/buyurtmalar"
BPDF = "/api/dokon/v1/buyurtmalar/pdf"
SPDF = "/api/dokon/v1/savat/pdf"
SB = "/api/sayt-buyurtmalari"
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
KALIT = js(CA.post(API + "/api-kalit", json={})).get("kalit") or ""
CA.post(API + "/telefonlar", json={"raqam": "+998 97 999 57 57"})


def chek_tozala():
    for _n in ("_DOKON_BUYURTMA_CHEKLOV", "_DOKON_API_CHEKLOV", "_DOKON_PDF_CHEKLOV"):
        _ch = getattr(crud, _n, None)
        if _ch is not None:
            _ch.tozala()


def dok(yol, tana, amal=None):
    chek_tozala()
    h = {"X-Dokon-Kalit": KALIT, "Content-Type": "application/json"}
    if amal:
        h["X-Amal-Kaliti"] = amal
    return DOK.post(yol, content=json.dumps(tana).encode("ascii"), headers=h)




# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. /favicon.ico — platforma belgisi (ilgari 404)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_BELGI = open(os.path.join(ROOT, "static", "epserp_belgi_180.png"), "rb").read()
NC = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)     # loginsiz, cookie siz
r = NC.get("/favicon.ico", follow_redirects=False)
check("F1 GET /favicon.ico (loginsiz) — 200, image/png, tana = static/epserp_belgi_180.png, «public, max-age=604800»",
      r.status_code == 200 and r.headers.get("content-type") == "image/png" and r.content == _BELGI
      and r.headers.get("cache-control") == "public, max-age=604800", (r.status_code, r.headers.get("content-type"), r.headers.get("cache-control")))
r = NC.head("/favicon.ico", follow_redirects=False)
check("F2 HEAD /favicon.ico — 200, tana yo'q, uzunlik sarlavhasi — fayl hajmi", r.status_code == 200 and r.content == b""
      and r.headers.get("content-length") == str(len(_BELGI)), (r.status_code, r.headers.get("content-length")))
r = NC.get("/favicon.ico", headers={"Accept": "text/html,*/*"}, follow_redirects=False)
check("F3 brauzer so'rovi (Accept: text/html) — ham rasm (o'zbekcha 404 sahifasi EMAS), xavfsizlik sarlavhalari bor",
      r.status_code == 200 and r.headers.get("content-type") == "image/png" and r.headers.get("x-content-type-options") == "nosniff", r.status_code)
r = NC.post("/favicon.ico")
check("F4 POST /favicon.ico — 405 (faqat GET / HEAD)", r.status_code == 405, r.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Do'kon API — har javobda Cache-Control (xatolar — no-store)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
BOL = {b.get("nom"): b.get("id") for b in (js(CA.get(API)).get("bolimlar") or [])}


def model(bolim, kod, **kw):
    return js(CA.post(API + "/modellar", json=dict({"bolim_id": BOL.get(bolim), "kod": kod}, **kw))).get("id")


def detal(mid, olcham, eni=None, turi="asosiy", narx=10000, **kw):
    t = dict({"model_id": mid, "turi": turi, "olcham": olcham, "narx": narx}, **kw)
    if eni is not None:
        t.update(eni_sm=eni, qalinligi_sm=8)
    return js(CA.post(API + "/detallar", json=t)).get("id")


MD = model("Dekor elementlar", "D-2", nom="Burchak")
M3 = model("Dekor elementlar", "D-3", nom="")
MK = model("Karnizlar", "K-12", nom="Tekis")
MB = model("Karnizlar", "BK-1", nom="")
DID = {"S": detal(MD, "S", narx=9900), "XL": detal(M3, "XL", narx=11000), "keng": detal(MK, "12 sm (keng)", 12, narx=45000),
       "k12": detal(MK, "12 sm", 12, narx=40000), "bk": detal(MB, "S", 15, narx=30000)}
check("C0 sinov katalogi (D-2 S, D-3 XL / BK-1 S eni 15 — nomsiz model, K-12 «12 sm (keng)» / «12 sm» eni 12)", all(DID.values()), DID)
_q1 = [{"detal_id": DID["S"], "qoplamali": False, "miqdor": 2}]
_cc = {}
_cc["400 tana"] = dok(BY, {}, "t247-0000000001")
_cc["400 JSON emas"] = (chek_tozala(), DOK.post(SPDF, content=b"x", headers={"X-Dokon-Kalit": KALIT, "Content-Type": "application/json"}))[1]
_cc["400 savat"] = dok(SPDF, {"qatorlar": 5})
_cc["413"] = dok(SPDF, {"a": "x" * 210000})
_cc["409 narx"] = dok(BY, {"mijoz": "Ali", "telefon": "+998 90 111 22 33", "viloyat": "andijon", "kutilgan_jami": 1, "qatorlar": _q1},
                      "t247-0000000002")
_cc["404 yo'l"] = (chek_tozala(), DOK.get("/api/dokon/v1/bunday-yol-yoq", headers={"X-Dokon-Kalit": KALIT}))[1]
_cc["405"] = (chek_tozala(), DOK.put("/api/dokon/v1/katalog", headers={"X-Dokon-Kalit": KALIT}))[1]
_hol = {k: (v.status_code, v.headers.get("cache-control")) for k, v in _cc.items()}
check("C1 400 (tana / JSON emas / savat), 413, 409 narx_ozgardi, 404 noma'lum yo'l, 405 — HAMMASI «no-store» (ilgari Cache-Control yo'q)",
      _hol == {"400 tana": (400, "no-store"), "400 JSON emas": (400, "no-store"), "400 savat": (400, "no-store"), "413": (413, "no-store"),
               "409 narx": (409, "no-store"), "404 yo'l": (404, "no-store"), "405": (405, "no-store")}, _hol)
chek_tozala()
r1 = DOK.get("/api/dokon/v1/katalog", headers={"X-Dokon-Kalit": KALIT})
r2 = DOK.get("/api/dokon/v1/katalog", headers={"X-Dokon-Kalit": KALIT, "If-None-Match": r1.headers.get("etag") or "-"})
r3 = DOK.get("/api/dokon/v1/katalog")
r4 = dok(BY, {"mijoz": "Ali", "telefon": "+998 90 111 22 33", "viloyat": "andijon", "qatorlar": _q1}, "t247-0000000003")
check("C2 o'zi bergan sarlavha O'ZGARMAYDI: katalog 200 / 304 — «private, no-cache» (ETag bilan), kalitsiz 401 — «no-store», buyurtma 200 — "
      "«no-store» (ikki marta emas)",
      (r1.status_code, r1.headers.get("cache-control"), r2.status_code, r2.headers.get("cache-control"), r3.status_code,
       r3.headers.get("cache-control"), r4.status_code, r4.headers.get("cache-control")) ==
      (200, "private, no-cache", 304, "private, no-cache", 401, "no-store", 200, "no-store")
      and r4.headers.get_list("cache-control") == ["no-store"],
      (r1.status_code, r1.headers.get("cache-control"), r2.status_code, r2.headers.get("cache-control"), r3.status_code, r4.status_code,
       r4.headers.get_list("cache-control")))
r = CA.get("/api/orders")
r5 = NC.get("/api/health")
r6 = NC.get("/api/dokonlar")
check("C3 boshqa API (/api/orders, /api/health, «/api/dokonlar» — «/api/dokon/» EMAS) — tegilmaydi",
      r.status_code == 200 and r.headers.get("cache-control") is None and r5.headers.get("cache-control") is None
      and r6.status_code == 404 and r6.headers.get("cache-control") is None,
      (r.status_code, r.headers.get("cache-control"), r5.headers.get("cache-control"), r6.status_code, r6.headers.get("cache-control")))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("N. Detal nomi tartibi — « · » dan keyingi o'lcham AYNAN (review246 L3)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from schemas import detal_nomi_tartib as _dnt      # noqa: E402
NT = [("D-3 · XL", "D-3 · XL"), ("D-2 · XXL", "D-2 · XXL"), ("AB-12 KESMA · XL", "Ab-12 kesma · XL"), ("D-2 Burchak · S", "D-2 Burchak · S"),
      ("D-3 · S", "D-3 · S"), ("PADAKOLNIK · 12 sm", "PADAKOLNIK · 12 sm"), ("K-1 · 12 sm · XL", "K-1 · 12 sm · XL"),
      # review247 M1: oddiy so'z bor (« · » dan keyin ham) — butun nom o'zgarmaydi; bo'lmasa — faqat boshi
      ("BK-1 · 15 sm · S", "BK-1 · 15 sm · S"), ("MDF · panel", "MDF · panel"), ("TP-9 · XL", "Tp-9 · XL"), ("AB-12  KESMA · XL", "Ab-12 kesma · XL"),
      # « · » siz — zip 222 qoidasi O'ZGARMAGAN
      ("PADAKOLNIK", "Padakolnik"), ("AB-12 KESMA", "Ab-12 kesma"), ("15 LI NALIChNIK", "15 li nalichnik"), ("MDF panel", "MDF panel"),
      ("Karniz 15 sm", "Karniz 15 sm"), ("karniz  q8", "karniz  q8"), ("BN_D1", "BN_D1"), ("BN_D1 · XL", "BN_D1 · XL"), (None, None)]
_nt = [(a, xavfsiz(lambda a=a: _dnt(a), "XATO")) for a, _k in NT]
check(f"N1 jadval ({len(NT)}): «D-3 · XL» → «D-3 · XL» (ilgari «D-3 · xl»), «AB-12 KESMA · XL» → «Ab-12 kesma · XL»; «BK-1 · 15 sm · S» — "
      "o'zgarmaydi (review247 M1); « · » siz nomlar — zip 222 dagidek", [b for _a, b in _nt] == [k for _a, k in NT], [(a, b, k) for (a, b), (_x, k) in zip(_nt, NT) if b != k])
AM = "t247-0000000004"
r = dok(BY, {"mijoz": "Vali", "telefon": "+998 90 111 22 34", "viloyat": "andijon",
             "qatorlar": [{"detal_id": DID["XL"], "qoplamali": False, "miqdor": 2}, {"detal_id": DID["bk"], "qoplamali": False, "miqdor": 2}]}, AM)
_rq = js(r).get("raqam")
_sid = xavfsiz(lambda: SessionLocal().query(DokonBuyurtma.id).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == _rq).scalar())
r = CA.post(SB + f"/{_sid}/tasdiqla", json={"deadline": "2026-11-20", "recipe_id": RID})
_oid = js(r).get("order_id")
_its = xavfsiz(lambda: sorted(i.name for i in SessionLocal().get(models.Order, _oid).items), [])
check("N2 nomsiz modellar — tasdiqlangan ERP buyurtmasi qatorlari «D-3 · XL», «BK-1 · 15 sm · S» (saytdagidek; review247 M1: «Bk-1» EMAS)",
      r.status_code == 200 and _its == ["BK-1 · 15 sm · S", "D-3 · XL"],
      (r.status_code, r.text[:200], _its))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Sayt detal nomi — o'lcham eni bilan boshlansa, eni bir marta (review246 L5)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from types import SimpleNamespace as _NS     # noqa: E402
SJ = [  # (kod, model nomi, turi, o'lcham, eni, kutilgan)
    ("K-12", "Tekis", "asosiy", "12 sm (keng)", 12, "K-12 Tekis · 12 sm (keng)"),
    ("K-12", "Tekis", "asosiy", "12sm keng", 12, "K-12 Tekis · 12sm keng"),
    ("K-12", "Tekis", "asosiy", "12 (keng)", 12, "K-12 Tekis · 12 (keng)"),
    ("K-12", "Tekis", "asosiy", "12 см keng", 12, "K-12 Tekis · 12 см keng"),
    ("K-12", "Tekis", "asosiy", "12.0 sm uzun", 12, "K-12 Tekis · 12.0 sm uzun"),
    ("K-12", "Tekis", "asosiy", "12 x 3", 12, "K-12 Tekis · 12 x 3"),
    ("A-1", "Kasr", "asosiy", "12,5 sm keng", 12.5, "A-1 Kasr · 12,5 sm keng"),
    ("R-18", "Klassik", "karniz", "15 sm (keng)", 15, "Rom karnizi R-18 · 15 sm (keng)"),
    ("K-12", "Tekis 12 sm keng", "asosiy", "12 sm keng", 12, "K-12 Tekis 12 sm keng"),          # o'lcham enisiz nomda bor — qo'shilmaydi
    # o'zgarmagan (zip 246)
    ("K-12", "Tekis", "asosiy", "12 sm", 12, "K-12 Tekis · 12 sm"), ("K-12", "Tekis", "asosiy", "12", 12, "K-12 Tekis · 12 sm"),
    ("K-12", "Tekis", "asosiy", "12sm", 12, "K-12 Tekis · 12 sm"), ("K-12", "Tekis", "asosiy", "12 см", 12, "K-12 Tekis · 12 sm"),
    ("K-12", "Tekis", "asosiy", "12,5 sm", 12, "K-12 Tekis · 12 sm · 12,5 sm"), ("K-12", "Tekis", "asosiy", "120 sm", 12, "K-12 Tekis · 12 sm · 120 sm"),
    ("K-12", "Tekis", "asosiy", "12.004 keng", 12, "K-12 Tekis · 12 sm · 12.004 keng"), ("K-1", "Tekis", "asosiy", "S", 12, "K-1 Tekis · 12 sm · S"),
    ("D-2", "Burchak", "asosiy", "S", None, "D-2 Burchak · S"), ("T-1", "Panel", "asosiy", "60x120", None, "T-1 Panel · 60x120"),
    ("R-18", "Klassik", "karniz", "O'rta", 15, "Rom karnizi R-18 · 15 sm · O'rta"), ("A", None, "asosiy", "S", None, "Mahsulot A · S"),
    ("A", None, "asosiy", "12 sm", 12, "A · 12 sm"), ("A", None, "asosiy", "12 sm (keng)", 12, "A · 12 sm (keng)"),            # review247 L1: «A · 12 sm» bilan bir xil (old qo'shimchasiz)
]
_sn = [(k, xavfsiz(lambda k=k: crud._sayt_nom(_NS(kod=k[0], nom=k[1]), _NS(turi=k[2], olcham=k[3], eni_sm=k[4])), "XATO")) for k in SJ]
check(f"S1 jadval ({len(SJ)}): «K-12 Tekis · 12 sm (keng)» (ilgari «· 12 sm · 12 sm (keng)»), «12sm keng», «12 (keng)», «12 см keng», kasr eni "
      "«12,5 sm keng»; «12 sm», «12,5 sm», «120 sm», «12.004 keng», «S» — zip 246 dagidek", all(b == k[5] for k, b in _sn),
      [(k[5], b) for k, b in _sn if b != k[5]])
_uz = xavfsiz(lambda: crud._sayt_nom(_NS(kod="Z" * 30, nom="N" * 120), _NS(turi="asosiy", olcham="12 sm (keng)", eni_sm=12)), "")
check("S2 juda uzun nom — 150 belgi, o'lcham BUTUN oxirida («… · 12 sm (keng)»), eni takrori yo'q", len(_uz) == 150
      and _uz.endswith("N · 12 sm (keng)") and _uz.count("12 sm") == 1, (len(_uz), _uz[-30:]))
AM2 = "t247-0000000005"
_q2 = [{"detal_id": DID["keng"], "qoplamali": True, "miqdor": 2}, {"detal_id": DID["k12"], "qoplamali": True, "miqdor": 2}]
r = dok(BY, {"mijoz": "Soli", "telefon": "+998 90 111 22 35", "viloyat": "andijon", "qatorlar": _q2}, AM2)
J = js(r)
_rq2 = J.get("raqam")
_gn = [g.get("guruh_nomi") for g in (J.get("guruhlar") or [])]
_dn = [d.get("nom") for g in (J.get("guruhlar") or []) for d in (g.get("detallar") or [])]
check("S3 sayt buyurtmasi: «K-12 Tekis · 12 sm (keng)» / «K-12 Tekis · 12 sm» — HAR XIL nom; guruh nomi — o'lcham bir marta",
      r.status_code == 200 and _dn == ["K-12 Tekis · 12 sm (keng)", "K-12 Tekis · 12 sm"]
      and _gn == ["K-12 Tekis · 12 sm (keng), qoplamali", "K-12 Tekis · 12 sm, qoplamali"], (r.status_code, _dn, _gn, r.text[:300]))
r = dok(BPDF, {"raqam": _rq2, "kalit": AM2})
P1 = matn(r)
check("S4 buyurtma PDF i — «K-12 Tekis · 12 sm (keng)», «· 12 sm · 12 sm» takrori YO'Q", lambda: r.status_code == 200
      and zich("K-12 Tekis · 12 sm (keng)") in zich(P1) and zich("12 sm · 12 sm") not in zich(P1) and zich("(keng) — 12 sm (keng)") not in zich(P1),
      (r.status_code, P1[:900]))
_sid2 = xavfsiz(lambda: SessionLocal().query(DokonBuyurtma.id).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == _rq2).scalar())
r = CA.post(SB + f"/{_sid2}/tasdiqla", json={"deadline": "2026-11-20", "recipe_id": RID})
_oid2 = js(r).get("order_id")
_its2 = xavfsiz(lambda: sorted(i.name for i in SessionLocal().get(models.Order, _oid2).items), [])
check("S5 tasdiqlangan ERP buyurtmasi — ikki alohida qator «K-12 Tekis · 12 sm», «K-12 Tekis · 12 sm (keng)»", r.status_code == 200
      and _its2 == ["K-12 Tekis · 12 sm", "K-12 Tekis · 12 sm (keng)"], (r.status_code, r.text[:200], _its2))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Partiyasi qolmagan bog'lam — «Katalogdan tanlash» nomi katta-kichik harfi bilan (review246 L4)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_sh = {k: xavfsiz(lambda k=k: crud._sayt_nom_shakllari(*(lambda s: (s.get(models.DokonModel, s.get(models.DokonDetal, DID[k]).model_id),
                                                                   s.get(models.DokonDetal, DID[k])))(SessionLocal())), [])
       for k in ("S", "keng", "k12")}
check("B1 nom shakllari: D-2 S — [«D-2 Burchak · S», «D-2 Burchak»]; «12 sm (keng)» — [hozirgi, zip 246 «· 12 sm · 12 sm (keng)», zip 245 "
      "«· 12 sm»]; «12 sm» — bitta", _sh == {"S": ["D-2 Burchak · S", "D-2 Burchak"],
                                             "keng": ["K-12 Tekis · 12 sm (keng)", "K-12 Tekis · 12 sm · 12 sm (keng)", "K-12 Tekis · 12 sm"],
                                             "k12": ["K-12 Tekis · 12 sm"]}, _sh)
from models import FinishedProduct, tm_kam_kaliti     # noqa: E402


def _kalit(nom, cat="dona", unit="dona", eni=None, qal=None):
    return tm_kam_kaliti(FinishedProduct(company_id=1, name=nom, category=cat, unit=unit, is_coated=True, quantity=1, width=eni,
                                         thickness=qal))


def _bog(did, kalit):
    s = SessionLocal()
    s.get(models.DokonDetal, did).tm_bogl_kaliti = kalit
    s.commit()
    x = {y["detal_id"]: y for y in crud.dokon_tm_katalog(s, 1)}.get(did) or {}
    s.close()
    return x.get("bog") or {}


_b = {nom: _bog(DID["S"], _kalit(nom)) for nom in ("D-2 Burchak", "D-2 Burchak · S", "D-2 Eski nom")}
check("B2 D-2 S: eski (245) kalit «d-2 burchak» → forma nomi «D-2 Burchak» (ilgari «d-2 burchak»); hozirgi kalit → «D-2 Burchak · S»; "
      "boshqa nom (model qayta nomlangan) — kalitdagidek kichik harf; hammasida partiya_bor = False",
      [(_b[k].get("nom"), _b[k].get("partiya_bor")) for k in ("D-2 Burchak", "D-2 Burchak · S", "D-2 Eski nom")]
      == [("D-2 Burchak", False), ("D-2 Burchak · S", False), ("d-2 eski nom", False)], _b)
_bk = {nom: _bog(DID["keng"], _kalit(nom, "profil", "metr", 12.0, 8.0)) for nom in ("K-12 Tekis · 12 sm · 12 sm (keng)", "K-12 Tekis · 12 sm")}
check("B3 K-12 «12 sm (keng)»: zip 246 kaliti → «K-12 Tekis · 12 sm · 12 sm (keng)», zip 245 kaliti → «K-12 Tekis · 12 sm»; eni / qalinlik — "
      "kalitdan", [(_bk[k].get("nom"), _bk[k].get("eni"), _bk[k].get("qalinligi")) for k in _bk]
      == [("K-12 Tekis · 12 sm · 12 sm (keng)", 12.0, 8.0), ("K-12 Tekis · 12 sm", 12.0, 8.0)], _bk)
# eski (245) kalitli bog'lam: forma nomi bilan yangi partiya — AYNAN o'sha kalitga, bog'lam o'zgarmaydi
_k245 = _kalit("D-2 Burchak")
_bog(DID["S"], _k245)
_kd = js(CA.get("/api/finished/katalog-detallar"))
_kl = _kd if isinstance(_kd, list) else (_kd.get("detallar") or _kd.get("items") or [])
_x = {x.get("detal_id"): x for x in _kl if isinstance(x, dict)}.get(DID["S"]) or {}
_fnom = (_x.get("bog") or {}).get("nom")
_d = SessionLocal()
_fp = FinishedProduct(company_id=1, name=_fnom or "?", category="dona", unit="dona", is_coated=True, quantity=3)
_d.add(_fp)
_d.flush()
_yk = tm_kam_kaliti(_fp)
_rb = xavfsiz(lambda: crud.dokon_partiya_katalogga(_d, _fp.id, DID["S"], 1, "t247"), {})
_d.commit()
_bk2 = _d.get(models.DokonDetal, DID["S"]).tm_bogl_kaliti
_fpn = _d.get(FinishedProduct, _fp.id).name
_d.close()
check("B4 GET /api/finished/katalog-detallar — forma nomi «D-2 Burchak»; shu nom bilan yangi partiya — kalit o'sha (245) bog'lamniki, nomi katta "
      "harf bilan saqlandi, bog'lam o'zgarmadi", _fnom == "D-2 Burchak" and _yk == _k245 and _bk2 == _k245 and _fpn == "D-2 Burchak",
      (_fnom, _yk, _k245, _bk2, _fpn, _rb))

if PG_URL:                                         # kech180: jarayon nomli baza — oxirida o'chiriladi
    try:
        import database as _dbm247
        _dbm247.engine.dispose()
        _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception as _e:                        # noqa: BLE001
        print("PG bazasi o'chirilmadi:", _e)
print(f"\n{'=' * 70}\n{YORLIQ}NATIJA: {OK} ok, {FAIL} fail")
for f in FAILED:
    print("  -", f)
sys.exit(1 if FAIL else 0)
