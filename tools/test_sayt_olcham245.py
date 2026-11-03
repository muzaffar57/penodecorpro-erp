#!/usr/bin/env python3
"""
test_sayt_olcham245.py — kech179 (zip 245: sayt buyurtmasi — alohida detal guruh nomida o'lcham takrori va PDF qatorida o'lcham yo'qolishi).

NIMA UCHUN KERAK
  ERP detal nomi (`crud._sayt_nom`) enini « · 12 sm» qilib yozadi; alohida detal guruh nomi esa ustiga katalog o'lchamini yana qo'shardi —
  «S244 Jonli sinov · 12 sm, 12 sm, qoplamali» («🛒 Saytdan» paneli, Telegram xabari; kech178 jonli sinovida topildi). PDF (zip 244) esa
  o'lchamni nomning MATN qismi deb tekshirardi: «S-1 Burchak» (o'lcham «S»), «MS-1» («M»), «K-12 Raqam» («12») qatorlarida o'lcham YO'Q
  edi — bir modelning ikki o'lchami PDF da bir xil qator bo'lib qolishi mumkin edi (review244 H1 ning o'zi, boshqa kodlar bilan).
  Qoida BITTA — `crud._sayt_olcham_nomdami(nom, olcham, eni_sm)`: o'lcham nomda butun so'z(lar) bo'lib turibdi YOKI ERP nomidagi eni.
BO'LIMLAR
  Q — qoida (jadval). G — guruh nomi (hisob, panel, Telegram). P — PDF qatorlari (savat va buyurtma). E — ERP buyurtmasi qatorlari
  O'ZGARMAGAN (nom = `_sayt_nom`). K — komplekt / «o'z o'lchami» guruh nomi O'ZGARMAGAN.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
Asl kodga (zip 244) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_sayt_olcham245.py
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
PG_BAZA = f"saytolcham245_{os.getpid()}"            # review245 L4: parallel PG yurishlari bir-birini o'chirmasin
_T = tempfile.mkdtemp(prefix="t245_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't245.db')}"
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
_c1.name = "T245 Penodekor"
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t245_admin", PAROL, UserRole.ADMIN, "T245 Admin", company_id=1)
    auth.create_user(s, "t245_plat", PAROL, UserRole.ADMIN, "T245 Platforma", company_id=1)
s.query(User).filter(User.username == "t245_plat").first().is_platform_admin = True
s.add(models.Recipe(company_id=1, name="Qoplama T245"))
s.commit()
RID = s.query(models.Recipe.id).filter(models.Recipe.company_id == 1).scalar()
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t245_admin")
CP = mijoz("t245_plat")
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
section("Q. Qoida — `_sayt_olcham_nomdami(nom, olcham, eni_sm)`")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_f = getattr(crud, "_sayt_olcham_nomdami", None)
JADVAL = [  # (nom, olcham, eni, kutilgan)
    ("S244 Jonli sinov · 12 sm", "12 sm", 12, True),
    ("S244 Jonli sinov · 12 sm", "12", 12, True),
    ("S244 Jonli sinov · 12 sm", "12sm", 12, True),
    ("S244 Jonli sinov · 12 sm", "12 см", 12, True),
    ("S244 Jonli sinov · 12 sm", "12 SM", 12, True),
    ("S244 Jonli sinov · 12 sm", "12.0 sm", 12, True),
    ("S244 Jonli sinov · 12 sm", "12.0", 12, True),
    ("K-5 Kasr · 12,5 sm", "12,5 sm", 12.5, True),
    ("K-5 Kasr · 12,5 sm", "12.5 sm", 12.5, True),
    ("K-5 Kasr · 12,5 sm", "12.5", 12.5, True),
    ("K-5 Kasr · 12,5 sm", "12,5sm", 12.5, True),
    ("K-5 Kasr · 12,5 sm", "12,50sm", 12.5, True),
    ("K-5 Kasr · 12,5 sm", "12,5см", 12.5, True),
    ("K-9 Boshqa · 12 sm", "15 sm", 12, False),
    ("K-9 Boshqa · 12 sm", "12,5 sm", 12, False),
    ("K-11 Mm · 12 sm", "120 mm", 12, False),
    ("K-10 Enisiz", "12 sm", None, False),
    ("K-12 Raqam", "12", None, False),
    ("D-12 Kesma", "12", None, False),
    ("S-1 Burchak", "S", None, False),
    ("MS-1 Burchak", "M", None, False),
    ("SM-1 Burchak", "S", None, False),
    ("D-2 Burchak", "S", None, False),
    ("D-2 Burchak S", "S", None, True),
    ("D-2 Burchak s", "S", None, True),
    ("D-2 Burchak (XL)", "XL", None, True),
    ("Rom karnizi R-18 · O'rta", "O‘rta", None, True),
    ("K-13 · 12 sm", "12 sm, 12 sm", 12, False),
    ("K-14 · 12 sm", "· 12 sm", 12, True),
    ("Nimadir", "", None, True),
    ("Nimadir", None, None, True),
    ("Nimadir", "·", None, False),
    ("K-15 · 12 sm", "12 sm uzun", 12, False),
    ("K-16 · 0,5 sm", "0.5 sm", 0.5, True),
    ("K-17", "12 sm", 0, False),
    # review245 M1: eni yozuvidagi vergul / ming ajratgich — so'zlarga bo'linmaydi
    ("A-1 Kasr · 12,5 sm", "12", 12.5, False),
    ("A-1 Kasr · 12,5 sm", "5", 12.5, False),
    ("A-1 Kasr · 12,5 sm", "5 sm", 12.5, False),
    ("A-1 · 0,5 sm", "5 sm", 0.5, False),
    ("A-1 · 0,5 sm", "0", 0.5, False),
    ("A-1 · 1 000 sm", "1", 1000, False),
    ("A-1 · 1 000 sm", "000 sm", 1000, False),
    ("A-1 · 1 000 sm", "1000 sm", 1000, True),
    ("A-1 · 12 sm", "sm", 12, False),
    ("A-1 2.5", "5", None, False),
    ("A-1 2,5", "5", None, False),
    ("A-1 · 12,25 sm", "12.25 sm", 12.25, True),
    ("A-1 · 12,25 sm", "12,25", 12.25, True),
    ("Burchak·S", "S", None, True),
    # review245 L1: nom 150 belgida kesilgan — eni qismi nomda yo'q
    ("X" * 150, "12 sm", 12, False),
    ("A-1 · 12 sm", "12 sm", 15, True),           # eni boshqa, lekin «12 sm» nomda so'z bo'lib turibdi
    ("A-1 · 15 sm", "12 sm", 12, False),
    # review245 L3: yaxlitlashsiz — son AYNAN teng
    ("A-1 · 12 sm", "12.004", 12, False),
    ("A-1 · 12,35 sm", "12.345", 12.35, False),
    ("A-1 · 12 sm", "12.00", 12, True),
]
_xato = [(n, o, e, k, xavfsiz(lambda n=n, o=o, e=e: _f(n, o, e), "XATO")) for n, o, e, k in JADVAL]
check(f"Q1 jadval ({len(JADVAL)} holat): butun so'z / eni (12, 12 sm, 12sm, 12 см, 12 SM, 12.0 sm, 12,5 = 12.5) — bor; «S» — «S-1» da, "
      "«12» — «K-12» da, «15 sm» / «120 mm» — eni 12 da YO'Q",
      lambda: _f is not None and all(x[4] == x[3] for x in _xato), [x for x in _xato if x[4] != x[3]])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. Guruh nomi (hisob, «Saytdan» paneli, Telegram)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
BOL = {b.get("nom"): b.get("id") for b in (js(CA.get(API)).get("bolimlar") or [])}


def model(bolim, kod, **kw):
    return js(CA.post(API + "/modellar", json=dict({"bolim_id": BOL.get(bolim), "kod": kod}, **kw))).get("id")


def detal(mid, olcham, eni=None, turi="asosiy", **kw):
    t = dict({"model_id": mid, "turi": turi, "olcham": olcham, "narx": 10000}, **kw)
    if eni is not None:
        t.update(eni_sm=eni, qalinligi_sm=8)
    return js(CA.post(API + "/detallar", json=t)).get("id")


KAT = [  # (kalit, bo'lim, kod, nom, o'lcham, eni, kutilgan guruh nomi, kutilgan PDF nomi)
    ("a", "Karnizlar", "S244", "Jonli sinov", "12 sm", 12, "S244 Jonli sinov · 12 sm, qoplamali", "S244 Jonli sinov · 12 sm"),
    ("b", "Karnizlar", "K-2", "Ikki", "12", 12, "K-2 Ikki · 12 sm, qoplamali", "K-2 Ikki · 12 sm"),
    ("c", "Karnizlar", "K-3", "Kirill", "12 см", 12, "K-3 Kirill · 12 sm, qoplamali", "K-3 Kirill · 12 sm"),
    ("d", "Karnizlar", "K-5", "Kasr", "12.5 sm", 12.5, "K-5 Kasr · 12,5 sm, qoplamali", "K-5 Kasr · 12,5 sm"),
    ("e", "Karnizlar", "K-9", "Boshqa", "15 sm", 12, "K-9 Boshqa · 12 sm, 15 sm, qoplamali", "K-9 Boshqa · 12 sm — 15 sm"),
    ("f", "Karnizlar", "K-10", "Enisiz", "12 sm", None, "K-10 Enisiz, 12 sm, qoplamali", "K-10 Enisiz — 12 sm"),
    ("g", "Karnizlar", "K-12", "Raqam", "12", None, "K-12 Raqam, 12, qoplamali", "K-12 Raqam — 12"),
    ("h", "Dekor elementlar", "S-1", "Burchak", "S", None, "S-1 Burchak, S, qoplamali", "S-1 Burchak — S"),
    ("i", "Dekor elementlar", "S-1", None, "M", None, "S-1 Burchak, M, qoplamali", "S-1 Burchak — M"),
    ("j", "Dekor elementlar", "MS-1", "Burchak", "M", None, "MS-1 Burchak, M, qoplamali", "MS-1 Burchak — M"),
    ("k", "Dekor elementlar", "D-2", "Burchak S", "S", None, "D-2 Burchak S, qoplamali", "D-2 Burchak S"),
    ("l", "Karnizlar", "A-1", "Kasr", "12", 12.5, "A-1 Kasr · 12,5 sm, 12, qoplamali", "A-1 Kasr · 12,5 sm — 12"),     # review245 M1
    ("m", "Karnizlar", "A-1", None, "5 sm", 12.5, "A-1 Kasr · 12,5 sm, 5 sm, qoplamali", "A-1 Kasr · 12,5 sm — 5 sm"),
]
MID, DID = {}, {}
for kk, bol, kod, nom, ol, eni, _g, _p in KAT:
    if kod not in MID:
        MID[kod] = model(bol, kod, **({"nom": nom} if nom else {}))
    DID[kk] = detal(MID[kod], ol, eni)
check("G0 sinov katalogi (13 detal, 11 model; «S-1» va «A-1» — ikki o'lcham)", all(DID.values()) and all(MID.values()), (MID, DID))
SAVAT = [{"detal_id": DID[k[0]], "qoplamali": True, "miqdor": 2} for k in KAT]
_d = SessionLocal()
H = xavfsiz(lambda: crud.sayt_buyurtma_hisobla(_d, 1, SAVAT), {"qatorlar": []})
_d.close()
_gn = [x.get("guruh_nomi") for x in H["qatorlar"]]
_kut = [k[6] for k in KAT]
check("G1 `sayt_buyurtma_hisobla` guruh nomlari — o'lcham ikki marta EMAS («S244 Jonli sinov · 12 sm, qoplamali»); eni yo'q / boshqa "
      "o'lcham — AYNAN (asl qoida)", _gn == _kut, [(a, b) for a, b in zip(_gn, _kut) if a != b] or _gn)
check("G2 hech bir guruh nomida «12 sm, 12 sm» / «12 sm, 12,» / «, 12 см» yo'q",
      lambda: bool(_gn) and not any(re.search(r"12 sm, 12( |,)|, 12 см|, 12\.5 sm", g) for g in _gn), _gn)
AMAL = "t245-0000000001"
r = dok(BY, {"mijoz": "Ali", "telefon": "+998 90 111 22 33", "viloyat": "andijon", "qatorlar": SAVAT}, AMAL)
J = js(r)
RAQAM = J.get("raqam")
check("G3 sayt buyurtmasi yaratildi; javobdagi guruh nomlari — hisob bilan AYNAN",
      r.status_code == 200 and [g.get("guruh_nomi") for g in (J.get("guruhlar") or [])] == _kut, r.text[:400])
_tg = "\n".join(TG)
check("G4 Telegram xabarida — «• S244 Jonli sinov · 12 sm, qoplamali — …», «12 sm, 12 sm» YO'Q; «S-1 Burchak, S» va «S-1 Burchak, M» bor",
      lambda: "S244 Jonli sinov · 12 sm, qoplamali — " in _tg and "12 sm, 12 sm" not in _tg
      and "S-1 Burchak, S, qoplamali" in _tg and "S-1 Burchak, M, qoplamali" in _tg, _tg[:900])
SID = xavfsiz(lambda: SessionLocal().query(DokonBuyurtma.id).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == RAQAM).scalar())
_pn = js(CA.get(SB + f"/{SID}")) if SID else {}
check("G5 «🛒 Saytdan» paneli (GET /api/sayt-buyurtmalari/{id}) guruh nomlari — AYNAN (bazada saqlangani)",
      [g.get("guruh_nomi") for g in (_pn.get("guruhlar") or [])] == _kut, _pn)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PDF qatorlari (savat va buyurtma)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_pdf = xavfsiz(lambda: [x["name"] for x in crud._sayt_pdf_qatorlari([crud._sayt_hisob_qatori(q) for q in H["qatorlar"]])], [])
_kp = [k[7] for k in KAT]
check("P1 `_sayt_pdf_qatorlari` nomlari: «S-1 Burchak — S» / «— M», «MS-1 Burchak — M», «K-12 Raqam — 12» (o'lcham kod ichida emas); eni bilan "
      "teng o'lcham — qo'shilmaydi; nomdagi butun so'z («D-2 Burchak S») — qo'shilmaydi", _pdf == _kp,
      [(a, b) for a, b in zip(_pdf, _kp) if a != b] or _pdf)
r = dok(SPDF, {"qatorlar": SAVAT})
K1 = matn(r)
check("P2 savat PDF i — har qator nomi PDF da (bo'shliqsiz solishtirish); «S-1 Burchak — S» va «S-1 Burchak — M» ikkalasi",
      lambda: r.status_code == 200 and all(zich(x) in zich(K1) for x in _kp)
      and zich("S-1 Burchak — S") in zich(K1) and zich("S-1 Burchak — M") in zich(K1), (r.status_code, K1[:1500]))
check("P3 savat PDF ida «12 sm — 12 sm» / «12 sm — 12» / «12,5 sm — 12.5 sm» YO'Q",
      lambda: bool(K1) and not any(zich(x) in zich(K1) for x in ("12 sm — 12 sm", "· 12 sm — 12", "12,5 sm — 12.5 sm", "12 sm — 12 см")),
      K1[:1500])
r = dok(BPDF, {"raqam": RAQAM, "kalit": AMAL})
P1 = matn(r)
check("P4 buyurtma PDF i (bazadagi qatorlar, `eni_sm` — qatordan) — savat PDF i bilan bir xil nomlar",
      lambda: r.status_code == 200 and all(zich(x) in zich(P1) for x in _kp) and zich("S-1 Burchak — S") in zich(P1)
      and zich("K-12 Raqam — 12") in zich(P1) and zich("12 sm — 12 sm") not in zich(P1), (r.status_code, P1[:1500]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. ERP buyurtmasi qatorlari O'ZGARMAGAN")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def _erp():
    d = SessionLocal()
    try:
        b = d.get(DokonBuyurtma, SID)
        q = crud._sayt_qatorlari(d, 1, b.id)
        return crud.sayt_buyurtma_tanasi(b, q, 1, datetime(2026, 11, 20), recipe_id=RID)["items"], [x.sbq_nom for x in q]
    finally:
        d.close()


_ei = xavfsiz(_erp, ([], []))
_mnom = {k[2]: k[3] for k in KAT if k[3]}
_nomlar = [k[2] + (f" {_mnom[k[2]]}" if k[2] in _mnom else "") + (f" · {crud.audit_son(k[5], 2)} sm" if k[5] else "") for k in KAT]
check("E1 ERP qatori nomi — `_sayt_nom` (« · 12 sm» bilan; o'lcham qo'shilmaydi — ERP / «Tayyor mahsulotlar» bog'lami shu nomda)",
      lambda: [i["name"] for i in _ei[0]] == _ei[1] == _nomlar and not any(i.get("kmp_guruh") for i in _ei[0]), (_ei, _nomlar))
r = CA.post(SB + f"/{SID}/tasdiqla", json={"deadline": "2026-11-20", "recipe_id": RID})
_oid = js(r).get("order_id")
from schemas import detal_nomi_tartib as _dnt        # noqa: E402
_its = xavfsiz(lambda: sorted(i.name for i in SessionLocal().get(models.Order, _oid).items), [])
check("E2 tasdiqlash — ERP buyurtmasi qatorlari nomi `_sayt_nom` (tartiblangan) bilan AYNAN", lambda: r.status_code == 200 and bool(_oid)
      and _its == sorted(_dnt(x) for x in _nomlar), (r.text[:300], _its))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Komplekt / «o'z o'lchami» guruh nomi O'ZGARMAGAN")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MK = model("Rom va eshik dekorlari", "R-18", nom="Klassik", kapitel_baza_bor=False)
KD = {t: detal(MK, "15 sm", 15, turi=t, **({} if t == "karniz" else {})) for t in ("karniz", "podokonnik", "nalichnik")}
_d = SessionLocal()
H2 = xavfsiz(lambda: crud.sayt_buyurtma_hisobla(_d, 1, [{"komplekt": "rom", "model_id": MK, "olcham": "15 sm", "qoplamali": False, "soni": 2},
                                                         {"oz_olcham": [{"detal_id": KD["karniz"], "miqdor": 2}], "qoplamali": True}]),
             {"qatorlar": []})
_d.close()
# review245 L2 (M24): komplekt o'lchami eni bilan teng EMAS («O'rta», eni 15) — PDF komplekt qatoriga baribir qo'shilmaydi (sarlavhada)
MK2 = model("Rom va eshik dekorlari", "R-19", nom="Zamonaviy", kapitel_baza_bor=False)
KD2 = {t: detal(MK2, "O'rta", 15, turi=t) for t in ("karniz", "podokonnik", "nalichnik")}
_d = SessionLocal()
H3 = xavfsiz(lambda: crud.sayt_buyurtma_hisobla(_d, 1, [{"komplekt": "rom", "model_id": MK2, "olcham": "O'rta", "qoplamali": True, "soni": 1},
                                                         {"oz_olcham": [{"detal_id": KD2["podokonnik"], "miqdor": 4}], "qoplamali": False}]),
             {"qatorlar": []})
_d.close()
_g2 = [(x.get("tur"), x.get("guruh_nomi")) for x in H2["qatorlar"]]
check("K1 komplekt — «R-18 «Klassik» — rom komplekti, 15 sm, qoplamasiz × 2» (3 detal); «o'z o'lchami» — «R-18 «Klassik», 15 sm, o'z "
      "o'lchami, qoplamali» (o'lcham — komplekt tanlovining o'zi, ERP komplekt sarlavhasi shundan)",
      _g2 == [("komplekt_rom", "R-18 «Klassik» — rom komplekti, 15 sm, qoplamasiz × 2")] * 3
      + [("oz_olcham", "R-18 «Klassik», 15 sm, o'z o'lchami, qoplamali")], _g2)
_pk = xavfsiz(lambda: [x["name"] for x in crud._sayt_pdf_qatorlari([crud._sayt_hisob_qatori(q) for q in H2["qatorlar"]])], [])
check("K2 komplekt / «o'z o'lchami» PDF qatori — «— o'lcham» qo'shilmaydi (sarlavhada)",
      _pk == ["Rom karnizi R-18 · 15 sm", "Podokonnik R-18 · 15 sm", "Nalichnik R-18 · 15 sm", "Rom karnizi R-18 · 15 sm"], _pk)
_pk3 = xavfsiz(lambda: [x["name"] for x in crud._sayt_pdf_qatorlari([crud._sayt_hisob_qatori(q) for q in H3["qatorlar"]])], [])
check("K3 komplekt o'lchami «O'rta» (eni 15) — guruh nomida «O'rta», PDF qatorlarida «— O'rta» YO'Q (komplekt / «o'z o'lchami» qatori)",
      lambda: [x.get("guruh_nomi") for x in H3["qatorlar"]] == ["R-19 «Zamonaviy» — rom komplekti, O'rta, qoplamali × 1"] * 3
      + ["R-19 «Zamonaviy», O'rta, o'z o'lchami, qoplamasiz"]
      and _pk3 == ["Rom karnizi R-19 · 15 sm", "Podokonnik R-19 · 15 sm", "Nalichnik R-19 · 15 sm", "Podokonnik R-19 · 15 sm"],
      (H3["qatorlar"][:1], _pk3))

if PG_URL:                                         # review245 L4: jarayon nomli baza — oxirida o'chiriladi
    try:
        import database as _dbm245
        _dbm245.engine.dispose()
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
