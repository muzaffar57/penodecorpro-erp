#!/usr/bin/env python3
"""
test_sayt_pdf244.py — kech178 (zip 244: do'kon — buyurtma va savat PDF i; egasi TALABI «Onlayn do'kon rejasi» 30.10, «Buyurtma ro'yxati —
PDF»: savatda va buyurtma berilgandan keyingi sahifada «PDF yuklab olish»; PDF da firma nomi va telefoni, buyurtma raqami va sanasi, mijoz
ismi va telefoni, har qator (model, o'lcham, detal, miqdor, narx, summa) va jami summa; komplekt buyurtmalar uchun ham).

NIMA UCHUN KERAK
  Xato — do'kon kaliti bilan BOSHQA mijozning buyurtmasini raqamini taxmin qilib ochish (amal kaliti so'ralmasa), raqam / kalit xatosini
  ajratib aytish (taxmin qilishga yordam), boshqa korxona buyurtmasini ochish, PDF da narxning bugungi katalogdan olinishi (buyurtmada
  qotgani emas), savat PDF i bilan buyurtma yozib qo'yish, savatda ERP hisobidan boshqa narx, komplekt sarlavhasining yo'qolishi, bekor /
  tasdiqlangan buyurtmada «qo'ng'iroq qilib tasdiqlating» yozuvi, «Taklif» PDF ining o'zgarib qolishi, tasdiqlashda ERP buyurtmasi
  qatorlarining o'zgarishi (halqa ajratilgani uchun), katta / buzilgan tana.
BO'LIMLAR
  S — statik (yo'llar, kalit sahifasi ro'yxati, funksiyalar). A — kirish (kalit, katalog o'chiq, B korxona). P — buyurtma PDF i (matn,
  qatorlar, komplekt, jami, holat, qotgan narx). X — tekshiruv (404 / 400 / 413 / 405). K — savat PDF i. E — ERP buyurtma qatorlari AYNAN
  (tasdiqlash). T — «Taklif» PDF i o'zgarmagan.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
Asl kodga (zip 243) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_sayt_pdf244.py
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
PG_BAZA = "saytpdf244_test"
_T = tempfile.mkdtemp(prefix="t244_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't244.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
    import pdf_service                             # noqa: E402
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


def _y246():
    """kech179 (zip 246): `crud._sayt_nom` katalog o'lchamini nomga qo'shadimi (qobiliyat — eski kodda ham o'tadi)."""
    try:
        from types import SimpleNamespace as _S246
        return crud._sayt_nom(_S246(kod="X-1", nom=None), _S246(turi="asosiy", olcham="S", eni_sm=None)) == "X-1 · S"
    except Exception:                      # noqa: BLE001
        return False


Y246 = _y246()


def _n246(eski, olcham):
    """ERP / katalog nomi: zip 246 dan — «… · o'lcham»."""
    return f"{eski} · {olcham}" if Y246 else eski


def _p246(nom, olcham):
    """PDF qatori: zip 246 dan — o'lcham nomda («… · S»), avval — «… — S» (zip 244)."""
    return f"{nom} · {olcham}" if Y246 else f"{nom} — {olcham}"


def js(r):
    try:
        x = r.json()
        return x if isinstance(x, (dict, list)) else {}
    except Exception:                      # noqa: BLE001
        return {}


def det(r):
    d = js(r)
    return str(d.get("detail") if isinstance(d, dict) else d)


def xavfsiz(fn, std=None):
    try:
        return fn()
    except Exception:                      # noqa: BLE001
        return std


def matn(r_yoki_bayt):
    """PDF matni (bo'shliqlar bitta); PDF emas — ''."""
    b = getattr(r_yoki_bayt, "content", r_yoki_bayt)
    if not isinstance(b, (bytes, bytearray)) or not bytes(b).startswith(b"%PDF"):
        return ""
    try:
        return re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(bytes(b))).pages))
    except Exception:                      # noqa: BLE001
        return ""


def zich(s):
    return re.sub(r"\s+", "", str(s or "")).replace(" ", "").replace("\xa0", "")


def pul(x):
    """PDF dagi pul yozuvi (bo'shliqsiz) — `pdf_service._pul_matni`."""
    return zich(pdf_service._pul_matni(float(x)))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Muhit: «bugun» — Toshkent 2026-11-03 (seshanba) 12:00 (UTC 07:00) — ish vaqti; Telegram — ushlanadi
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
class _SoxtaVaqt:
    t = datetime(2026, 11, 3, 7, 0)

    @classmethod
    def utcnow(cls):
        return cls.t


if getattr(crud, "_dt233", None) is not None:
    crud._dt233 = _SoxtaVaqt
main._send_telegram = lambda *a, **k: True

s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T244 B korxona"))
_c1 = s.get(Company, 1)
_c1.name = "T244 Penodekor"
_c1.phone = "+998 90 000 44 01"
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t244_admin", PAROL, UserRole.ADMIN, "T244 Admin", company_id=1)
    auth.create_user(s, "t244_plat", PAROL, UserRole.ADMIN, "T244 Platforma", company_id=1)
    auth.create_user(s, "t244_b", PAROL, UserRole.ADMIN, "T244 B Admin", company_id=2)
s.query(User).filter(User.username == "t244_plat").first().is_platform_admin = True
s.add(models.Recipe(company_id=1, name="Qoplama T244"))
s.commit()
RID = s.query(models.Recipe.id).filter(models.Recipe.company_id == 1).scalar()
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t244_admin")
CP = mijoz("t244_plat")
CB = mijoz("t244_b")
DOK = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)    # do'kon serveri — cookie siz
API = "/api/sayt-katalogi"
BY = "/api/dokon/v1/buyurtmalar"
BPDF = "/api/dokon/v1/buyurtmalar/pdf"
SPDF = "/api/dokon/v1/savat/pdf"
SB = "/api/sayt-buyurtmalari"
KALIT = {"A": None, "B": None}


def chek_tozala():
    for _n in ("_DOKON_BUYURTMA_CHEKLOV", "_DOKON_API_CHEKLOV", "_DOKON_PDF_CHEKLOV"):
        _ch = getattr(crud, _n, None)
        if _ch is not None:
            _ch.tozala()


def yubor(tana, amal, dkalit="A"):
    chek_tozala()
    return DOK.post(BY, content=json.dumps(tana).encode("ascii"),
                    headers={"X-Dokon-Kalit": KALIT.get(dkalit) or "", "X-Amal-Kaliti": amal, "Content-Type": "application/json"})


def pdf_ol(yol, tana, dkalit="A", xom=None, **h):
    chek_tozala()
    hh = {"Content-Type": "application/json", **h}
    if dkalit is not None:
        hh["X-Dokon-Kalit"] = KALIT.get(dkalit) or dkalit
    return DOK.post(yol, content=(xom if xom is not None else json.dumps(tana).encode("ascii")), headers=hh)


def sb_soni(cid=1):
    return xavfsiz(lambda: SessionLocal().query(DokonBuyurtma).filter(DokonBuyurtma.company_id == cid).count(), -1) if DokonBuyurtma else -1


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_yollar = {(m, getattr(r, "path", None)) for r in main.app.routes for m in (getattr(r, "methods", None) or ())}
check("S1 POST /api/dokon/v1/buyurtmalar/pdf va POST /api/dokon/v1/savat/pdf bor; GET — yo'q (kalit URL ga tushmasin)",
      ("POST", BPDF) in _yollar and ("POST", SPDF) in _yollar and ("GET", BPDF) not in _yollar and ("GET", SPDF) not in _yollar)
check("S2 kalit sahifasidagi yo'llar ro'yxatida ikkala PDF yo'li", lambda: BPDF in crud.DOKON_API_YOLLAR and SPDF in crud.DOKON_API_YOLLAR)
import inspect                                     # noqa: E402
check("S3 `sayt_buyurtma_tanasi` qatorlarni `_sayt_erp_qatorlari` dan oladi (PDF bilan bir qoida); PDF — «Taklif» shablonining o'zi",
      lambda: "_sayt_erp_qatorlari(qatorlar, tm)" in inspect.getsource(crud.sayt_buyurtma_tanasi)
      and "generate_nakladnoy(" in inspect.getsource(pdf_service.generate_sayt_pdf))
check("S4 kalit solishtirish — `hmac.compare_digest` (vaqt bo'yicha sizdirmaydi)",
      lambda: "compare_digest" in inspect.getsource(crud.sayt_buyurtma_pdf_ol))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Kirish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = [pdf_ol(BPDF, {"raqam": "S-0001", "kalit": "savat-000001-t244"}, dkalit=None), pdf_ol(SPDF, {"qatorlar": []}, dkalit=None),
      pdf_ol(BPDF, {}, dkalit="pdk_" + "a" * 43)]
check("A1 kalitsiz / noto'g'ri kalit — 401 (WWW-Authenticate)", all(x.status_code == 401 for x in _r)
      and all(x.headers.get("www-authenticate") == "Bearer" for x in _r), [(x.status_code, x.text[:80]) for x in _r])
r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
KALIT["A"] = js(CA.post(API + "/api-kalit", json={})).get("kalit")



def b_katalog(yoq):
    """B korxonada katalog belgisi — bazadan (platforma yo'li faqat platforma egasining korxonasida yoqadi; mut243 M01 saboq'i: B da
    katalog YOQIQ bo'lsin — aks holda 404 haqiqiy ajratishni yashiradi)."""
    d = SessionLocal()
    try:
        d.query(Company).filter(Company.id == 2).update({"dokon_yoqilgan": bool(yoq)})
        d.commit()
    finally:
        d.close()


xavfsiz(lambda: b_katalog(True))
KALIT["B"] = js(CB.post(API + "/api-kalit", json={})).get("kalit")
check("A2 A va B korxonada sayt katalogi yoqildi, do'kon kalitlari bor", r.status_code == 200
      and bool(KALIT["A"]) and bool(KALIT["B"]) and KALIT["A"] != KALIT["B"], (r.text[:120], KALIT))
for _t in ("+998 97 999 57 57", "+998 90 623 22 72"):
    CA.post(API + "/telefonlar", json={"raqam": _t})

# katalog: R-18 komplekt (O'rta, chegirma −15 %), K-12 karniz (metr), T-1 termopanel (m²), D-2 dekor (dona)
K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}


def model(bolim, kod, **kw):
    return js(CA.post(API + "/modellar", json=dict({"bolim_id": bolim, "kod": kod}, **kw))).get("id")


def detal(mid, turi, olcham, **kw):
    return js(CA.post(API + "/detallar", json=dict({"model_id": mid, "turi": turi, "olcham": olcham}, **kw))).get("id")


ORTA = "O'rta"
NARX = {"karniz": 15000, "podokonnik": 14000, "nalichnik": 12000, "kapitel": 30000, "baza": 31000}
M1 = model(BOL.get("Rom va eshik dekorlari"), "R-18", nom="Klassik", kapitel_baza_bor=True)
DID = {}
for _t, _n in NARX.items():
    DID[_t] = detal(M1, _t, ORTA, narx=_n, eni_sm=15 if _t not in ("kapitel", "baza") else 12,
                    qalinligi_sm=10 if _t == "karniz" else (4 if _t in ("podokonnik", "nalichnik") else None))
M2 = model(BOL.get("Karnizlar"), "K-12", nom="Tekis")
DID["k12"] = detal(M2, "asosiy", "12 sm", narx=45000, narx_qoplamali=98000, eni_sm=12, qalinligi_sm=8)
MT = model(BOL.get("Termopanel"), "T-1", nom="Termopanel 60x120")
DID["t1"] = detal(MT, "asosiy", "60x120", narx=150000)
M4 = model(BOL.get("Dekor elementlar"), "D-2", nom="Burchak")
DID["d2"] = detal(M4, "asosiy", "S", narx=9900)
DID["d2m"] = detal(M4, "asosiy", "M", narx=12300)            # review244 H1: bir model — ikki o'lcham
M5 = model(BOL.get("Dekor elementlar"), "AB-12", nom="KESMA")  # review244 L1: katta harfli nom — PDF da AYNAN («Ab-12 kesma» emas)
DID["ab"] = detal(M5, "asosiy", "XL", narx=12345)
_rc = CA.put(API + f"/modellar/{M1}/chegirma", json={"foiz": 15, "olchamlar": [ORTA]})
check("A3 sinov katalogi (komplekt, karniz, termopanel, dekor) va chegirma", all(DID.values()) and _rc.status_code == 200,
      (DID, _rc.text[:200]))

SAVAT = [{"komplekt": "rom", "model_id": M1, "olcham": ORTA, "qoplamali": False, "soni": 3},
         {"detal_id": DID["k12"], "qoplamali": True, "miqdor": 6},
         {"detal_id": DID["t1"], "qoplamali": False, "miqdor": 2.5},
         {"detal_id": DID["d2"], "qoplamali": False, "miqdor": 4},
         {"detal_id": DID["d2m"], "qoplamali": False, "miqdor": 1},
         {"detal_id": DID["ab"], "qoplamali": False, "miqdor": 2}]
AMAL1 = "savat-000001-t244"
r = yubor({"mijoz": "Ali Valiyev <b>", "telefon": "+998 90 111 22 33", "viloyat": "toshkent_sh", "qatorlar": SAVAT}, AMAL1)
if r.status_code != 200:
    r = yubor({"mijoz": "Ali Valiyev <b>", "telefon": "+998 90 111 22 33",
               "viloyat": next((v["kod"] for v in crud.sayt_viloyatlar() if not v["yetkazish_bepul"]), "x"), "qatorlar": SAVAT}, AMAL1)
J1 = js(r)
RAQAM1 = J1.get("raqam")
check("A4 sayt buyurtmasi yaratildi (4 mahsulot, 50/50 viloyat)", r.status_code == 200 and bool(RAQAM1), r.text[:300])
AMAL2 = "savat-000002-t244"
J2 = js(yubor({"mijoz": "Vali Aliyev", "telefon": "+998 90 111 22 44", "viloyat": "andijon",
               "qatorlar": [{"detal_id": DID["d2"], "qoplamali": False, "miqdor": 2}]}, AMAL2))
RAQAM2 = J2.get("raqam")
# B korxona — o'z buyurtmasi (B ning kaliti bilan)
KB = js(CB.get(API))
_bb = {b.get("nom"): b.get("id") for b in (KB.get("bolimlar") or [])}
_bbid = _bb.get("Dekor elementlar") or js(CB.post(API + "/bolimlar", json={"nom": "B dekor bo'limi", "qolip": "dona",
                                                                             "yoqilgan": True})).get("id")
_mb = js(CB.post(API + "/modellar", json={"bolim_id": _bbid, "kod": "BD-1", "nom": "B dekor"})).get("id")
_db = js(CB.post(API + "/detallar", json={"model_id": _mb, "turi": "asosiy", "olcham": "S", "narx": 7000})).get("id")
AMALB = "savat-0000b1-t244"
JB = js(yubor({"mijoz": "B mijoz", "telefon": "+998 90 111 22 55", "viloyat": "andijon",
               "qatorlar": [{"detal_id": _db, "qoplamali": False, "miqdor": 1}]}, AMALB, dkalit="B"))
check("A5 B korxona buyurtmasi (B kaliti bilan) — raqami A nikiga teng bo'lishi mumkin (har korxonada o'z sanog'i)",
      JB.get("raqam") == "S-0001", JB)
_r = [pdf_ol(BPDF, {"raqam": RAQAM1, "kalit": AMAL1}, dkalit="B"), pdf_ol(BPDF, {"raqam": "S-0001", "kalit": AMALB}, dkalit="A")]
check("A6 B kaliti + A buyurtmasining raqami va amal kaliti — 404; A kaliti + B buyurtmasi — 404 (korxona kalitdan)",
      [x.status_code for x in _r] == [404, 404] and all(det(x) == "Buyurtma topilmadi" for x in _r),
      [(x.status_code, x.text[:120]) for x in _r])
_rb = pdf_ol(BPDF, {"raqam": "S-0001", "kalit": AMALB}, dkalit="B")
check("A7 B o'z buyurtmasi PDF ini oladi — B korxona nomi, A niki YO'Q", _rb.status_code == 200 and "T244 B korxona" in matn(_rb)
      and "T244 Penodekor" not in matn(_rb), (_rb.status_code, _rb.text[:200]))
xavfsiz(lambda: b_katalog(False))
_r = [pdf_ol(BPDF, {"raqam": "S-0001", "kalit": AMALB}, dkalit="B"), pdf_ol(SPDF, {"qatorlar": [{"detal_id": _db, "miqdor": 1}]},
                                                                             dkalit="B")]
check("A8 B da katalog o'chirilsa — B kaliti bilan ikkala PDF ham 404", [x.status_code for x in _r] == [404, 404],
      [(x.status_code, x.text[:120]) for x in _r])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. Buyurtma PDF i")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = pdf_ol(BPDF, {"raqam": RAQAM1, "kalit": AMAL1})
P1 = matn(r)
check("P1 200, application/pdf, «attachment; filename=\"buyurtma-S-0001.pdf\"», no-store, nosniff",
      r.status_code == 200 and r.headers.get("content-type", "").startswith("application/pdf")
      and r.headers.get("content-disposition") == f'attachment; filename="buyurtma-{RAQAM1}.pdf"'
      and r.headers.get("cache-control") == "no-store" and r.headers.get("x-content-type-options") == "nosniff",
      (r.status_code, dict(r.headers), r.text[:200]))
_vn = crud.SAYT_VILOYAT_NOMI.get(J1.get("viloyat"), "?") if hasattr(crud, "SAYT_VILOYAT_NOMI") else "?"
check("P2a sarlavha — «BUYURTMA # S-0001» (TAKLIF / «BUYURTMA HISOBI» emas)",
      lambda: re.search(r"BUYURTMA\s*#\s*" + re.escape(RAQAM1), P1) is not None and "TAKLIF" not in P1 and "BUYURTMA HISOBI" not in P1,
      P1[:300])
check("P2 sarlavha «BUYURTMA», firma nomi va telefoni, raqam, sana (Toshkent) 03.11.2026 12:00, mijoz (HTML — matn), telefon, viloyat, «Yangi»",
      lambda: all(x in P1 for x in ("BUYURTMA", "T244 Penodekor", "44 01", RAQAM1, "03.11.2026 12:00", "Ali Valiyev <b>",
                                    crud.dokon_telefon_korinish("+998901112233"), _vn, "Yangi")), P1[:900])
_g = J1.get("guruhlar") or []
check("P3 komplekt sarlavhasi («R-18 «Klassik» — rom komplekti, O'rta, qoplamasiz» … 3 komplekt) va har detal nomi",
      lambda: "rom komplekti" in P1 and "3 komplekt" in P1
      and all(zich(d.get("nom")) in zich(P1) for gg in _g for d in gg.get("detallar") or []), P1[:1500])
check("P4 «JAMI:» = buyurtma jami (chegirmali); to'lov / qarz / imzo qatori YO'Q",
      lambda: "JAMI:" in P1 and pul(J1["jami"]) + "so'm" in zich(P1) and "QARZ" not in P1 and "Imzo" not in P1
      and "TO'LOV SUMMASI" not in P1, (J1.get("jami"), P1[-900:]))
_det = [d for gg in _g for d in gg.get("detallar") or []]
check("P5 har qator summasi (qotgan narx × miqdor) PDF da; termopanel 2,5 m², karniz 6 m (qoplamali)",
      lambda: all(pul(d["summa"]) in zich(P1) for d in _det) and "2,5" in P1 and "(qoplamali)" in P1, (_det, P1[:1500]))
check("P6 pastida: «Shu raqamlardan biriga qo'ng'iroq qilib buyurtmani tasdiqlating: +998 97 999 57 57 · …», yetkazish 50/50, tejaldi",
      lambda: "qo'ng'iroq qilib buyurtmani tasdiqlating" in P1 and "+998 97 999 57 57" in P1 and "+998 90 623 22 72" in P1
      and "yarmini biz to'laymiz" in P1 and "Chegirma hisobiga tejaldi" in P1
      and zich(crud.xabar_son(J1.get("tejaldi") or 0, 2)) in zich(P1), P1[-900:])
check("P10 alohida detal qatorida katalog O'LCHAMI (review244 H1): «D-2 Burchak — S» va «D-2 Burchak — M» — ikki xil qator",
      lambda: _p246("D-2 Burchak", "S") in P1 and _p246("D-2 Burchak", "M") in P1, P1[:1800])
check("P11 katta harfli model kodi va nomi PDF da AYNAN («AB-12 KESMA — XL», «Ab-12 kesma — xl» emas — review244 L1)",
      lambda: _p246("AB-12 KESMA", "XL") in P1 and "Ab-12" not in P1, P1[:1800])
check("P16 metrli qator: miqdor 6, 1 m narxi, qator summasi — ketma-ket («K-12 … m 6 98 000 588 000»; kit karnizi «6 12 800 76 800»)",
      lambda: zich("m 6 98 000 588 000") in zich(P1) and zich("m 6 12 800 76 800") in zich(P1), P1[:1800])
_tart = [zich(d.get("nom")) for gg in _g for d in gg.get("detallar") or []]
_joy = [zich(P1).find(x) for x in _tart]
check("P12 qatorlar tartibi — buyurtmadagidek (guruhlar va detallar ketma-ketligi)", lambda: all(j >= 0 for j in _joy) and _joy == sorted(_joy),
      (_tart, _joy))
check("P13 pul yozuvi — yarim so'm YUQORIGA (review244 M2): 6 172,5 → «6 173», 6 173,5 → «6 174», 1 234 567,4 → «1 234 567»",
      lambda: [pdf_service._pul_matni(x) for x in (6172.5, 6173.5, 1234567.4, 0, None)] == ["6 173", "6 174", "1 234 567", "0", "0"])
_sid = xavfsiz(lambda: SessionLocal().query(DokonBuyurtma.id).filter(DokonBuyurtma.company_id == 1,
                                                                      DokonBuyurtma.sb_raqam == RAQAM1).scalar())


def _band(qiymat):
    d = SessionLocal()
    try:
        d.query(DokonBuyurtma).filter(DokonBuyurtma.id == _sid).update({"sb_band_tugash": qiymat})
        d.commit()
    finally:
        d.close()


xavfsiz(lambda: _band(datetime(2026, 11, 5, 7, 0)))
r = pdf_ol(BPDF, {"raqam": RAQAM1, "kalit": AMAL1})
check("P14 ombordan qator band qilingan buyurtma — pastida «Ombordagi mahsulot 48 soat band qilindi — 05.11.2026 12:00 gacha …»",
      lambda: r.status_code == 200 and "48 soat band qilindi" in matn(r) and "05.11.2026 12:00 gacha" in matn(r), matn(r)[-700:])
xavfsiz(lambda: _band(None))
_SoxtaVaqt.t = datetime(2026, 11, 3, 17, 0)                  # Toshkent 22:00 — ish vaqtidan tashqari
r = pdf_ol(BPDF, {"raqam": RAQAM1, "kalit": AMAL1})
_SoxtaVaqt.t = datetime(2026, 11, 3, 7, 0)
check("P15 ish vaqtidan tashqari — faqat «doim» raqami (birinchisi) ko'rinadi, ikkinchisi YO'Q (sayt qoidasi bilan bir xil)",
      lambda: r.status_code == 200 and "+998 97 999 57 57" in matn(r) and "623 22 72" not in matn(r), matn(r)[-700:])
# narx o'zgaradi — buyurtma PDF i eski (qotgan) narxda, savat PDF i yangi narxda
CA.put(API + f"/detallar/{DID['d2']}", json={"narx": 19900})
r = pdf_ol(BPDF, {"raqam": RAQAM1, "kalit": AMAL1})
check("P7 katalogda narx o'zgargach — buyurtma PDF i QOTGAN narx bilan (jami o'zgarmagan, 9 900 qatori bor)",
      lambda: r.status_code == 200 and pul(J1["jami"]) + "so'm" in zich(matn(r)) and pul(9900 * 4) in zich(matn(r))
      and pul(19900 * 4) not in zich(matn(r)), matn(r)[-600:])
r = pdf_ol(BPDF, {"raqam": RAQAM2, "kalit": AMAL2})
P8 = matn(r)
check("P8 Andijon — «yetkazib berish bepul»; chegirmasiz — «tejaldi» yozuvi YO'Q", r.status_code == 200
      and "bepul" in P8 and "tejaldi" not in P8, P8[-600:])
_rb = CA.post(SB + f"/{xavfsiz(lambda: SessionLocal().query(DokonBuyurtma.id).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == RAQAM2).scalar())}/bekor",
              json={})
r = pdf_ol(BPDF, {"raqam": RAQAM2, "kalit": AMAL2})
P9 = matn(r)
check("P9 bekor qilingan buyurtma — «Bekor qilingan», «Buyurtma bekor qilingan.», «qo'ng'iroq qilib … tasdiqlating» YO'Q",
      _rb.status_code == 200 and r.status_code == 200 and "Bekor qilingan" in P9 and "Buyurtma bekor qilingan." in P9
      and "tasdiqlating" not in P9, (_rb.text[:200], P9[-600:]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("X. Tekshiruv")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = [pdf_ol(BPDF, {"raqam": RAQAM1, "kalit": "savat-999999-t244"}), pdf_ol(BPDF, {"raqam": "S-9999", "kalit": AMAL1}),
      pdf_ol(BPDF, {"raqam": RAQAM1, "kalit": AMAL2}), pdf_ol(BPDF, {"raqam": RAQAM1.lower(), "kalit": AMAL1})]
check("X1 noto'g'ri kalit / yo'q raqam / BOSHQA buyurtmaning kaliti / kichik harfli raqam — 404, javob BIR XIL («Buyurtma topilmadi»)",
      [x.status_code for x in _r] == [404] * 4 and len({x.text for x in _r}) == 1 and det(_r[0]) == "Buyurtma topilmadi"
      and all(x.headers.get("cache-control") == "no-store" for x in _r), [(x.status_code, x.text[:100]) for x in _r])
_yomon = [{"raqam": RAQAM1}, {"kalit": AMAL1}, {"raqam": RAQAM1, "kalit": AMAL1, "telefon": "x"}, {"raqam": "S 0001", "kalit": AMAL1},
          {"raqam": "S-" + "1" * 30, "kalit": AMAL1}, {"raqam": 1, "kalit": AMAL1}, {"raqam": RAQAM1, "kalit": "qisqa"},
          {"raqam": RAQAM1, "kalit": "a" * 65}, {"raqam": RAQAM1, "kalit": "kalit bo'shliq bilan"}, {"raqam": RAQAM1, "kalit": None},
          {"raqam": RAQAM1, "kalit": ["savat-000001-t244"]}]
_r = [pdf_ol(BPDF, t) for t in _yomon]
check(f"X2 {len(_yomon)} xil noto'g'ri tana (maydon yo'q / ortiqcha / raqam / kalit shakli) — 400, aniq xabar",
      all(x.status_code == 400 for x in _r) and all(det(x) for x in _r), [(x.status_code, x.text[:90]) for x in _r])
_r = [pdf_ol(BPDF, None, xom=b"[1]"), pdf_ol(BPDF, None, xom=b"{bad"), pdf_ol(BPDF, None, xom=b'{"raqam": NaN, "kalit": "x"}'),
      pdf_ol(SPDF, None, xom=b"\xff\xfe")]
check("X3 JSON emas / massiv / NaN / buzilgan UTF-8 — 400", [x.status_code for x in _r] == [400] * 4, [(x.status_code, x.text[:80]) for x in _r])
_r = [pdf_ol(BPDF, None, xom=b'{"raqam": "' + b"a" * 210000 + b'"}'), pdf_ol(SPDF, None, xom=b" " * 200001)]
check("X4 juda katta tana — 413", [x.status_code for x in _r] == [413, 413], [x.status_code for x in _r])
chek_tozala()
_r = [DOK.get(BPDF, headers={"X-Dokon-Kalit": KALIT["A"]}), DOK.get(SPDF, headers={"X-Dokon-Kalit": KALIT["A"]})]
check("X5 GET — 405", [x.status_code for x in _r] == [405, 405], [x.status_code for x in _r])
chek_tozala()
_n = getattr(crud, "SAYT_PDF_DAQIQA_MAX", 0)
_kodlar = []
for _i in range(_n + 1):
    _kodlar.append(DOK.post(BPDF, json={"raqam": "S-9999", "kalit": AMAL1}, headers={"X-Dokon-Kalit": KALIT["A"]}).status_code)
_kat = DOK.get("/api/dokon/v1/katalog", headers={"X-Dokon-Kalit": KALIT["A"]}).status_code
_sav = DOK.post(SPDF, json={"qatorlar": SAVAT}, headers={"X-Dokon-Kalit": KALIT["A"]}).status_code
check(f"X6 PDF yo'llarining O'Z chegarasi ({_n}/daqiqa — review244 M1): keyingisi 429, savat PDF i ham 429; katalog esa 200 (do'kon yiqilmaydi)",
      _n == 30 and _kodlar[:_n] == [404] * _n and _kodlar[-1] == 429 and _sav == 429 and _kat == 200, (_kodlar[-5:], _sav, _kat))
chek_tozala()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Savat PDF i")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_oldin = sb_soni()
r = pdf_ol(SPDF, {"qatorlar": SAVAT})
K1 = matn(r)
_h = xavfsiz(lambda: crud.sayt_buyurtma_hisobla(SessionLocal(), 1, SAVAT), {})
check("K1 200, «savat.pdf», sarlavha «SAVAT (HISOB-KITOB)», «buyurtma hali berilmagan», sana; raqam / mijoz YO'Q",
      r.status_code == 200 and r.headers.get("content-disposition") == 'attachment; filename="savat.pdf"'
      and "SAVAT (HISOB-KITOB)" in K1 and "buyurtma hali berilmagan" in K1 and "03.11.2026 12:00" in K1 and "S-000" not in K1
      and "MIJOZ" not in K1 and "T244 Penodekor" in K1, (r.status_code, r.text[:200], K1[:600]))
check("K2 jami — ERP hisobi (`sayt_buyurtma_hisobla`, YANGI narx 19 900); komplekt sarlavhasi; «Savollar bo'lsa» raqamlar",
      lambda: pul(_h["jami"]) + "so'm" in zich(K1) and pul(19900 * 4) in zich(K1) and "rom komplekti" in K1
      and "Savollar bo'lsa" in K1 and "+998 97 999 57 57" in K1 and "tasdiqlating" not in K1, (_h.get("jami"), K1[-700:]))
check("K2b savat: komplekt soni («3 komplekt»), o'lchamli qatorlar («D-2 Burchak — M»), qatorlar tartibi — savatdagidek",
      lambda: "3 komplekt" in K1 and _p246("D-2 Burchak", "M") in K1
      and [zich(K1).find(zich(x)) for x in ("Rom karnizi", "K-12 Tekis", "T-1 Termopanel", _p246("D-2 Burchak", "S"), _p246("D-2 Burchak", "M"), "AB-12")]
      == sorted(zich(K1).find(zich(x)) for x in ("Rom karnizi", "K-12 Tekis", "T-1 Termopanel", _p246("D-2 Burchak", "S"), _p246("D-2 Burchak", "M"), "AB-12"))
      and zich(K1).find(zich("Rom karnizi")) >= 0, K1[:1500])
_oz = [{"oz_olcham": [{"detal_id": DID["karniz"], "miqdor": 4}, {"detal_id": DID["kapitel"], "miqdor": 1}], "qoplamali": False}]
r = pdf_ol(SPDF, {"qatorlar": _oz})
_hoz = xavfsiz(lambda: crud.sayt_buyurtma_hisobla(SessionLocal(), 1, _oz), {})
check("K2c «o'z o'lchami» savati — sarlavha «… o'z o'lchami», detallari, jami = ERP hisobi",
      lambda: r.status_code == 200 and "o'z o'lchami" in matn(r) and "Rom karnizi" in matn(r) and "Kapitel" in matn(r)
      and pul(_hoz["jami"]) + "so'm" in zich(matn(r)), (r.status_code, r.text[:200], matn(r)[:900]))
check("K3 savat PDF i hech narsa yozmaydi (sayt buyurtmalari soni o'zgarmadi)", sb_soni() == _oldin, (sb_soni(), _oldin))
_yomon = [{"qatorlar": []}, {"qatorlar": [{"detal_id": DID["k12"], "qoplamali": True, "miqdor": 5}]},
          {"qatorlar": [{"detal_id": 999999, "miqdor": 1}]}, {"qatorlar": SAVAT, "mijoz": "x"}, {},
          {"qatorlar": [{"detal_id": _db, "qoplamali": False, "miqdor": 1}]}]
_r = [pdf_ol(SPDF, t) for t in _yomon]
check("K4 bo'sh savat / toq metr / yo'q detal / ortiqcha maydon / qatorlarsiz / BOSHQA korxona detali — 400 (buyurtma yo'lining xabari)",
      [x.status_code for x in _r] == [400] * len(_yomon) and "Savat bo'sh" in det(_r[0]), [(x.status_code, x.text[:100]) for x in _r])
_r2 = yubor({"mijoz": "Ali", "telefon": "+998 90 111 22 66", "viloyat": "andijon",
             "qatorlar": [{"detal_id": DID["k12"], "qoplamali": True, "miqdor": 5}]}, "savat-000003-t244")
check("K5 savat PDF i xabari buyurtma yo'linikiga AYNAN (toq metr)", _r2.status_code == 400 and det(_r2) == det(_r[1]),
      (det(_r2), det(_r[1])))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. ERP buyurtma qatorlari — halqa ajratilgandan keyin AYNAN")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def _tana_items():
    d = SessionLocal()
    b = d.get(DokonBuyurtma, _sid)
    q = crud._sayt_qatorlari(d, 1, b.id)
    return crud.sayt_buyurtma_tanasi(b, q, 1, datetime(2026, 11, 20))["items"], crud._sayt_erp_qatorlari(q), q


_ti = xavfsiz(_tana_items, ([], None, []))
check("E1 `sayt_buyurtma_tanasi` items == `_sayt_erp_qatorlari` (PDF qatorlari — ERP buyurtmasiniki)",
      bool(_ti[0]) and _ti[0] == _ti[1], _ti[:2])
_esk = [{"name": x.sbq_nom, "birlik": x.sbq_birlik} for x in _ti[2]]
check("E2 profil — Uzunlik = metr, soni 1, narx = qator jami; m² — blok (m2); dona — soni; komplekt belgisi (kmp_guruh) bor",
      lambda: any(i["category"] == "profil" and i["quantity"] == 1.0 and i["length"] == 6.0 for i in _ti[0])
      and any(i["category"] == "blok" and i.get("blok_birlik") == "m2" for i in _ti[0])
      and any(i["category"] == "dona" and i["quantity"] == 4.0 for i in _ti[0])
      and sum(1 for i in _ti[0] if i.get("kmp_guruh")) == 5, (_ti[0], _esk))
from schemas import detal_nomi_tartib as _dnt        # noqa: E402  ERP buyurtmasi nomni saqlashda tartiblaydi (zip 222) — PDF da esa AYNAN
r = CA.post(SB + f"/{_sid}/tasdiqla", json={"deadline": "2026-11-20", "recipe_id": RID})
_oid = js(r).get("order_id")
_items = xavfsiz(lambda: [(i.name, i.category, float(i.unit_price or 0)) for i in SessionLocal().get(models.Order, _oid).items], [])
check("E3 tasdiqlash ishlaydi — ERP buyurtmasi qatorlari PDF qatorlari bilan bir xil (nom, tur, narx)",
      lambda: r.status_code == 200 and bool(_oid)
      and sorted(_items) == sorted((_dnt(i["name"]), i["category"], float(i["unit_price"])) for i in _ti[1]), (r.text[:300], _items))
r = pdf_ol(BPDF, {"raqam": RAQAM1, "kalit": AMAL1})
check("E4 tasdiqlangan buyurtma PDF i — «Tasdiqlangan», «Buyurtma tasdiqlangan.», «qo'ng'iroq qilib … tasdiqlating» YO'Q",
      r.status_code == 200 and "Tasdiqlangan" in matn(r) and "Buyurtma tasdiqlangan." in matn(r) and "tasdiqlating" not in matn(r),
      matn(r)[-500:])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. «Taklif» PDF i o'zgarmagan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_tk = js(CA.post("/api/takliflar", json={"mijoz": "Taklif mijoz", "telefon": "+998 90 123 45 67", "buyurtma": {
    "order_type": "product", "items": [{"name": "Karniz T244", "category": "dona", "quantity": 2, "unit_price": 10000,
                                        "is_coated": False}]}}))
_tid = (_tk.get("taklif") or {}).get("id")
r = CA.get(f"/api/takliflar/{_tid}/pdf") if _tid else None
T1 = matn(r) if r is not None else ""
check("T1 taklif PDF i: «TAKLIF (HISOB-KITOB)», «# T-…», «Narxlar 3 kun amal qiladi», «TO'LOV SUMMASI:», pastida «Taklif: T-…»",
      lambda: r is not None and r.status_code == 200 and "TAKLIF (HISOB-KITOB)" in T1 and "Narxlar 3 kun amal qiladi" in T1
      and "TO'LOV SUMMASI:" in T1 and re.search(r"# T-\d+", T1) and re.search(r"Taklif: T-\d+", T1) and "MIJOZ" in T1
      and "TAKLIF RAQAMI" in T1, (getattr(r, "status_code", None), _tk, T1[:800]))

print(f"\n{'=' * 70}\n{YORLIQ}NATIJA: {OK} ok, {FAIL} fail")
for f in FAILED:
    print("  -", f)
sys.exit(1 if FAIL else 0)
