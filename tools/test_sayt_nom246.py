#!/usr/bin/env python3
"""
test_sayt_nom246.py — kech179 (zip 246: sayt detal nomida katalog O'LCHAMI — nomda bo'lmasa).

NIMA UCHUN KERAK
  ERP detal nomi (`crud._sayt_nom`) faqat model kodi / nomi va enidan iborat edi: enisiz detalning (dona, m²) ikki o'lchami — «D-2 Burchak»
  S va M, «T-1 Panel» 60x120 va 60x60 — tasdiqlangan ERP buyurtmasida BIR XIL nomli qator (ishlab chiqarishda qaysi o'lcham — ko'rinmaydi);
  «Katalogdan tanlash» (zip 242) partiyalari bir xil nom → bitta «Tayyor mahsulotlar» kaliti (`tm_kam_kaliti`): S bog'lanadi, M — «band»
  (saytga qo'yib bo'lmaydi, qoldiq aralashadi). Endi o'lcham nomga qo'shiladi (`_sayt_olcham_nomdami` «yo'q» desa — eni bilan teng
  «12 sm» qo'shilmaydi).
BO'LIMLAR
  N — `_sayt_nom` jadvali. E — sayt buyurtmasi, guruh nomi, tasdiqlangan ERP buyurtmasi, Telegram. P — PDF (takror yo'q). T — katalog
  tanlovi nomlari, S / M partiyalari — alohida kalit, ikkalasi bog'lanadi. K — komplekt sarlavhasi o'zgarmagan, detal nomida o'lcham.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
Asl kodga (zip 245) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_sayt_nom246.py
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
PG_BAZA = f"saytnom246_{os.getpid()}"            # kech179: parallel PG yurishlari bir-birini o'chirmasin
_T = tempfile.mkdtemp(prefix="t246_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't246.db')}"
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
_c1.name = "T246 Penodekor"
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t246_admin", PAROL, UserRole.ADMIN, "T246 Admin", company_id=1)
    auth.create_user(s, "t246_plat", PAROL, UserRole.ADMIN, "T246 Platforma", company_id=1)
s.query(User).filter(User.username == "t246_plat").first().is_platform_admin = True
s.add(models.Recipe(company_id=1, name="Qoplama T246"))
s.commit()
RID = s.query(models.Recipe.id).filter(models.Recipe.company_id == 1).scalar()
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t246_admin")
CP = mijoz("t246_plat")
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


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("N. `_sayt_nom` — o'lcham nomda bo'lmasa qo'shiladi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from types import SimpleNamespace as _NS     # noqa: E402
NJ = [  # (kod, model nomi, turi, o'lcham, eni, kutilgan)
    ("D-2", "Burchak", "asosiy", "S", None, "D-2 Burchak · S"),
    ("D-2", "Burchak", "asosiy", "M", None, "D-2 Burchak · M"),
    ("T-1", "Panel", "asosiy", "60x120", None, "T-1 Panel · 60x120"),
    ("K-12", "Tekis", "asosiy", "12 sm", 12, "K-12 Tekis · 12 sm"),
    ("K-12", "Tekis", "asosiy", "12", 12, "K-12 Tekis · 12 sm"),
    ("K-12", "Tekis", "asosiy", "12sm", 12, "K-12 Tekis · 12 sm"),          # eni yozuvi bilan teng (so'z sifatida emas — mut246 M03)
    ("K-12", "Tekis", "asosiy", "12 см", 12, "K-12 Tekis · 12 sm"),
    ("K-12", "Tekis", "asosiy", "12.0", 12, "K-12 Tekis · 12 sm"),
    ("K-1", "Tekis", "asosiy", "S", 12, "K-1 Tekis · 12 sm · S"),
    ("A-1", "Kasr", "asosiy", "5 sm", 12.5, "A-1 Kasr · 12,5 sm · 5 sm"),
    ("D-3", "Burchak S", "asosiy", "S", None, "D-3 Burchak S"),
    ("R-18", "Klassik", "karniz", "O'rta", 15, "Rom karnizi R-18 · 15 sm · O'rta"),
    ("R-18", "Klassik", "kapitel", "O'rta", None, "Kapitel R-18 · O'rta"),
    ("R-18", "Klassik", "karniz", "15 sm", 15, "Rom karnizi R-18 · 15 sm"),
    ("A", None, "asosiy", "S", None, "Mahsulot A · S"),
    ("A", None, "asosiy", "12 sm", 12, "A · 12 sm"),
]
_nn = [(k, xavfsiz(lambda k=k: crud._sayt_nom(_NS(kod=k[0], nom=k[1]), _NS(turi=k[2], olcham=k[3], eni_sm=k[4])), "XATO")) for k in NJ]
check(f"N1 jadval ({len(NJ)} holat): «D-2 Burchak · S» / «· M», «T-1 Panel · 60x120», eni bilan teng o'lcham («12 sm», «12») — "
      "qo'shilmaydi, nomdagi so'z («Burchak S») — qo'shilmaydi, komplekt detali — «· O'rta»", all(b == k[5] for k, b in _nn),
      [(k[5], b) for k, b in _nn if b != k[5]])
_uz = xavfsiz(lambda: crud._sayt_nom(_NS(kod="Z" * 30, nom="N" * 120), _NS(turi="asosiy", olcham="XL", eni_sm=None)), "")
_uz2 = xavfsiz(lambda: crud._sayt_nom(_NS(kod="Z" * 30, nom="N" * 120), _NS(turi="asosiy", olcham="60x120", eni_sm=None)), "")
_uz3 = xavfsiz(lambda: crud._sayt_nom(_NS(kod="Z" * 30, nom="N" * 120), _NS(turi="asosiy", olcham="60x60", eni_sm=None)), "")
check("N2 juda uzun nom — 150 belgi, o'lcham BUTUN oxirida («… · XL», «… · 60x120» ≠ «… · 60x60»), asos qisqaradi (review246 L1)",
      len(_uz) == 150 and _uz.startswith("Z" * 30) and _uz.endswith(" · XL") and _uz2.endswith(" · 60x120") and _uz3.endswith(" · 60x60")
      and len(_uz2) == len(_uz3) == 150 and _uz2 != _uz3
      and len(xavfsiz(lambda: crud._sayt_nom(_NS(kod="Z" * 30, nom="N" * 120), _NS(turi="asosiy", olcham="12 sm", eni_sm=12)), "")) == 150,
      (len(_uz), _uz[-20:], _uz2[-12:], _uz3[-12:]))
_sz = [xavfsiz(lambda o=o: crud._sayt_olcham_nomdami(crud._sayt_nom(_NS(kod="D-2", nom="Burchak"), _NS(turi="asosiy", olcham=o, eni_sm=None)),
                                                     o, None), None) for o in ("()", "«»", "·")]
check("N3 faqat ajratuvchidan iborat o'lcham («()», ««»», «·») — nomga bir marta qo'shiladi, keyin «nomda bor» (guruh nomi / PDF da "
      "takrorlanmaydi — review246 L2)", _sz == [True, True, True], _sz)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. ERP buyurtmasi — bir modelning ikki o'lchami AJRALADI")
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
MT = model("Termopanel", "T-1", nom="Panel")
MK = model("Karnizlar", "K-12", nom="Tekis")
DID = {"S": detal(MD, "S", narx=9900), "M": detal(MD, "M", narx=12300), "t1": detal(MT, "60x120", narx=150000),
       "t2": detal(MT, "60x60", narx=80000), "k": detal(MK, "12 sm", 12, narx=45000)}
check("E0 sinov katalogi (D-2 S / M, T-1 60x120 / 60x60, K-12 12 sm)", all(DID.values()), DID)
SAVAT = [{"detal_id": DID["S"], "qoplamali": False, "miqdor": 2}, {"detal_id": DID["M"], "qoplamali": False, "miqdor": 3},
         {"detal_id": DID["t1"], "qoplamali": False, "miqdor": 1}, {"detal_id": DID["t2"], "qoplamali": False, "miqdor": 1},
         {"detal_id": DID["k"], "qoplamali": True, "miqdor": 2}]
KUT_NOM = ["D-2 Burchak · S", "D-2 Burchak · M", "T-1 Panel · 60x120", "T-1 Panel · 60x60", "K-12 Tekis · 12 sm"]
KUT_GURUH = ["D-2 Burchak · S, qoplamasiz", "D-2 Burchak · M, qoplamasiz", "T-1 Panel · 60x120, qoplamasiz", "T-1 Panel · 60x60, qoplamasiz",
             "K-12 Tekis · 12 sm, qoplamali"]
AMAL = "t246-0000000001"
r = dok(BY, {"mijoz": "Ali", "telefon": "+998 90 111 22 33", "viloyat": "andijon", "qatorlar": SAVAT}, AMAL)
J = js(r)
RAQAM = J.get("raqam")
_gn = [g.get("guruh_nomi") for g in (J.get("guruhlar") or [])]
_dn = [d.get("nom") for g in (J.get("guruhlar") or []) for d in (g.get("detallar") or [])]
check("E1 sayt buyurtmasi: detal nomlari — «D-2 Burchak · S» / «· M», «T-1 Panel · 60x120» / «· 60x60», «K-12 Tekis · 12 sm» (eni — bir marta)",
      r.status_code == 200 and _dn == KUT_NOM, (r.status_code, _dn, r.text[:300]))
check("E2 guruh nomlari — o'lcham BIR marta («D-2 Burchak · S, qoplamasiz»; «…, S, …» takrori yo'q)", _gn == KUT_GURUH, _gn)
SID = xavfsiz(lambda: SessionLocal().query(DokonBuyurtma.id).filter(DokonBuyurtma.company_id == 1, DokonBuyurtma.sb_raqam == RAQAM).scalar())
r = CA.post(SB + f"/{SID}/tasdiqla", json={"deadline": "2026-11-20", "recipe_id": RID})
_oid = js(r).get("order_id")
from schemas import detal_nomi_tartib as _dnt      # noqa: E402
_its = xavfsiz(lambda: [i.name for i in sorted(SessionLocal().get(models.Order, _oid).items, key=lambda i: i.id)], [])
check("E3 tasdiqlangan ERP buyurtmasi qatorlari — har o'lcham O'Z nomi bilan (ikki bir xil «D-2 Burchak» / «T-1 Panel» qatori YO'Q)",
      lambda: r.status_code == 200 and _its == [_dnt(x) for x in KUT_NOM] and len(set(_its)) == len(_its), (r.text[:300], _its))
_tg = "\n".join(TG)
check("E4 Telegram — «• D-2 Burchak · S, qoplamasiz — …» va «• D-2 Burchak · M, qoplamasiz — …»",
      "D-2 Burchak · S, qoplamasiz — " in _tg and "D-2 Burchak · M, qoplamasiz — " in _tg, _tg[:700])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PDF — o'lcham bir marta")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = dok(BPDF, {"raqam": RAQAM, "kalit": AMAL})
P1 = matn(r)
check("P1 buyurtma PDF i — «D-2 Burchak · S», «D-2 Burchak · M», «T-1 Panel · 60x120»; «· S — S» / «— 60x120» takrori YO'Q",
      lambda: r.status_code == 200 and all(zich(x) in zich(P1) for x in KUT_NOM)
      and not any(zich(x) in zich(P1) for x in ("· S — S", "· M — M", "60x120 — 60x120", "60x60 — 60x60")), (r.status_code, P1[:1200]))
r = dok(SPDF, {"qatorlar": SAVAT})
K1 = matn(r)
check("P2 savat PDF i — o'sha nomlar, takror yo'q", lambda: r.status_code == 200 and all(zich(x) in zich(K1) for x in KUT_NOM)
      and zich("· S — S") not in zich(K1), K1[:1200])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. «Katalogdan tanlash» va «Tayyor mahsulotlar» — S va M alohida mahsulot")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_kd = js(CA.get("/api/finished/katalog-detallar"))
_kl = _kd if isinstance(_kd, list) else (_kd.get("detallar") or _kd.get("items") or [])
_kn = {x.get("detal_id"): x.get("nom") for x in _kl if isinstance(x, dict)}
check("T1 GET /api/finished/katalog-detallar — S va M nomlari HAR XIL («D-2 Burchak · S» / «· M»)",
      _kn.get(DID["S"]) == "D-2 Burchak · S" and _kn.get(DID["M"]) == "D-2 Burchak · M", _kd)
from models import FinishedProduct, tm_kam_kaliti     # noqa: E402
_d = SessionLocal()
_fp = {}
for _k, _q in (("S", 5), ("M", 7)):
    _x = FinishedProduct(company_id=1, name=_kn.get(DID[_k]) or "?", category="dona", unit="dona", is_coated=True, quantity=_q)
    _d.add(_x)
    _d.flush()
    _fp[_k] = _x.id
_d.commit()
_kal = [tm_kam_kaliti(_d.get(FinishedProduct, _fp[k])) for k in ("S", "M")]
_r = [xavfsiz(lambda k=k: crud.dokon_partiya_katalogga(_d, _fp[k], DID[k], 1, "t246"), {}) for k in ("S", "M")]
_d.commit()
_d.close()
check("T2 S va M partiyalari (katalog nomi bilan) — TM kalitlari HAR XIL; ikkalasi o'z detaliga «boglandi» (M — «band» EMAS)",
      _kal[0] != _kal[1] and [x.get("holat") for x in _r] == ["boglandi", "boglandi"], (_kal, _r))
_d = SessionLocal()
_bk = {d.id: d.tm_bogl_kaliti for d in _d.query(models.DokonDetal).filter(models.DokonDetal.id.in_([DID["S"], DID["M"]])).all()}
_d.close()
check("T3 bazada: S detali — S partiyasi kaliti, M detali — M niki", _bk.get(DID["S"]) == _kal[0] and _bk.get(DID["M"]) == _kal[1], (_bk, _kal))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Komplekt — sarlavha o'zgarmagan, detal nomida o'lcham")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MR = model("Rom va eshik dekorlari", "R-18", nom="Klassik", kapitel_baza_bor=False)
for _t in ("karniz", "podokonnik", "nalichnik"):
    detal(MR, "O'rta", 15, turi=_t)
_d = SessionLocal()
H = xavfsiz(lambda: crud.sayt_buyurtma_hisobla(_d, 1, [{"komplekt": "rom", "model_id": MR, "olcham": "O'rta", "qoplamali": False, "soni": 2}]),
            {"qatorlar": []})
_d.close()
check("K1 komplekt guruh nomi — «R-18 «Klassik» — rom komplekti, O'rta, qoplamasiz × 2» (o'zgarmagan); detallar — «Rom karnizi R-18 · 15 sm "
      "· O'rta» …", [x.get("guruh_nomi") for x in H["qatorlar"]] == ["R-18 «Klassik» — rom komplekti, O'rta, qoplamasiz × 2"] * 3
      and [x.get("nom") for x in H["qatorlar"]] == ["Rom karnizi R-18 · 15 sm · O'rta", "Podokonnik R-18 · 15 sm · O'rta",
                                                    "Nalichnik R-18 · 15 sm · O'rta"], H["qatorlar"][:1])
_pk = xavfsiz(lambda: [x["name"] for x in crud._sayt_pdf_qatorlari([crud._sayt_hisob_qatori(q) for q in H["qatorlar"]])], [])
check("K2 komplekt PDF qatori — o'sha nom, «— O'rta» qo'shilmaydi", _pk == [x.get("nom") for x in H["qatorlar"]] and bool(_pk), _pk)

if PG_URL:                                         # kech179: jarayon nomli baza — oxirida o'chiriladi
    try:
        import database as _dbm246
        _dbm246.engine.dispose()
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
