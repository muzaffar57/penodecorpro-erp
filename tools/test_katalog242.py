#!/usr/bin/env python3
"""
test_katalog242.py — kech177 (zip 242): «Tayyor mahsulotlar» → ishlab chiqarish oynasida «📖 Katalogdan tanlash».

NIMA UCHUN KERAK (onlayn do'kon rejasi, Komplekt 6-band — egasi rejasi 30.10; O'LCHANGAN `work/k242/probe242.py`, asl = zip 241b)
  Ishlab chiqarishda nom QO'LDA yozilardi: partiya saytdagi detalga bog'lanmasdi («Sayt katalogi»da «Omborga bog'lash» — qo'lda);
  «K-12 Tekis 12 sm» / «· 12sm» deb yozilsa yoki eni / qalinligi almashsa — BOSHQA mahsulot (`models.tm_kam_kaliti`), saytdagi qoldiqqa
  qo'shilmasdi. Endi katalogdan tanlanadi: nomi (`crud._sayt_nom`), turi, eni / qalinligi, qoplama — o'zi; partiya detalga O'ZI bog'lanadi.
TALAB (har biri o'lchanadi):
  S  statik: sxema / qoida maydoni, crud funksiyalari, marshrut, shablonda tugma faqat `sayt_katalogi_bormi` ostida, JS
  A  kirish: katalog o'chiq — ro'yxat 404, `dokon_detal_id` bilan ishlab chiqarish 400 (partiya YO'Q, penoplast o'zgarmaydi); Usta — 403;
     Menejer / Omborchi (ishlab chiqarish ruxsati) — 200; boshqa korxona detali — 400 (partiya yo'q); B korxona ro'yxatida A detali yo'q
  K  ro'yxat: faqat metr / dona detallar (m² — yo'q), narx maydoni yo'q, nom = `_sayt_nom`, turkum, bog'lam (eng yangi partiya nomi /
     o'lchami; partiyasi qolmagan — kalitdagi o'lcham), tartib
  P  ishlab chiqarish (P16 — crud: boshqa korxona partiyasi rad; P17 — katalog keyin o'chirilsa 400): bog'lanmagan detal → «boglandi» (kalit = partiya kaliti, jurnal); «Sotuvga tayyor» dan keyin saytda qoldiq;
     ikkinchi partiya — «qoshildi» (qoldiq jamlanadi); qoplamasiz / birlik mos emas / detal boshqa mahsulotda / mahsulot boshqa detalda —
     partiya yoziladi, bog'lam O'ZGARMAYDI, sabab xabarda; donali; noto'g'ri id (yo'q / 0 / matn / bool / juda katta) — 400, partiya yo'q;
     takror (`X-Amal-Kaliti`) — bitta partiya, o'sha javob; `dokon_detal_id` siz — avvalgidek (`katalog` yo'q); P18–P20 (review242 H1) —
     bog'lanmagan detal FAQAT katalogning o'z nomi / o'lchami bilan, aks holda «farq»
  Q  (PG) parallel: bitta bog'lanmagan detalga ikki xil partiya bir vaqtda — faqat BITTASI bog'lanadi, ikkinchisi «boshqa», ikkalasi
     yaratiladi, yiqilish yo'q; Q2 — crud ikki sessiyada: bir xil mahsulot ikki detalga — korxona qulfi (238), ikkinchisi «band»
  U  HAQIQIY Chromium: tugma ko'rinadi (katalog yoqilgan), oyna, qidiruv, tanlash → maydonlar to'ladi (nom, tur, eni, kengligi, qoplama),
     belgi; tanlov qoplamani «Bor» qiladi; bog'langan detal — maydonlar o'sha mahsulotdan (U4b); nom / o'lcham o'zgartirilsa — ogohlantirish (U4c); donali «1 metrdan nechta» (U4d); qoplama «Yo'q» — ogohlantirish; saqlash → xabarda «bog'landi»; nomdagi HTML — MATN; telefon (390) — oyna ekranga sig'adi;
     JS xatosi yo'q; katalog o'chiq korxonada tugma YO'Q
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL` bilan HAQIQIY PostgreSQL 16 (Q faqat PG da).
Asl kodga (zip 241c) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_katalog242.py
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
PG_BAZA = f"katalog242_test_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t242_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't242.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
    import schemas                                 # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, ActivityLog, Inventory, FinishedProduct   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

DokonDetal = getattr(models, "DokonDetal", None)
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


for _n in ("_send_telegram", "_send_telegram_to", "_send_telegram_document", "_send_telegram_to_qoplamachi"):
    if hasattr(main, _n):
        setattr(main, _n, lambda *a, **k: False)

s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T242 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t242_admin", PAROL, UserRole.ADMIN, "T242 Admin", company_id=1)
    auth.create_user(s, "t242_plat", PAROL, UserRole.ADMIN, "T242 Platforma", company_id=1)
    auth.create_user(s, "t242_men", PAROL, UserRole.MANAGER, "T242 Menejer", company_id=1)
    auth.create_user(s, "t242_omb", PAROL, UserRole.WAREHOUSE, "T242 Omborchi", company_id=1)
    auth.create_user(s, "t242_usta", PAROL, UserRole.MASTER, "T242 Usta", company_id=1)
    auth.create_user(s, "t242_b", PAROL, UserRole.ADMIN, "T242 B Admin", company_id=2)
s.query(User).filter(User.username == "t242_plat").first().is_platform_admin = True
s.add(Inventory(company_id=1, item_name="Penoplast T242", unit="blok", is_penoplast=True, is_default_penoplast=True,
                volume_per_unit=1.0, price_per_unit=1000000, stock_quantity=500))
s.add(Inventory(company_id=2, item_name="Penoplast T242 B", unit="blok", is_penoplast=True, is_default_penoplast=True,
                volume_per_unit=1.0, price_per_unit=1000000, stock_quantity=500))
s.commit()
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA, CP, CM, CW, CU, CB = (mijoz(x) for x in ("t242_admin", "t242_plat", "t242_men", "t242_omb", "t242_usta", "t242_b"))
DOK = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
KR = "/api/finished/katalog-detallar"
PR = "/api/finished/produce"
_kn = [0]


def amal():
    _kn[0] += 1
    return f"t242-amal-{os.getpid()}-{_kn[0]:06d}"


def fp_soni(cid=1):
    return xavfsiz(lambda d: d.query(FinishedProduct).filter(FinishedProduct.company_id == cid).count(), -1)


def peno(cid=1):
    return xavfsiz(lambda d: float(d.query(Inventory.stock_quantity).filter(Inventory.company_id == cid).scalar()), None)


def bog(did):
    return xavfsiz(lambda d: d.get(DokonDetal, did).tm_bogl_kaliti if DokonDetal is not None else "?", "?")


def kalit(pid):
    return xavfsiz(lambda d: models.tm_kam_kaliti(d.get(FinishedProduct, pid)), None)


def ishlab(nom, cat="profil", h=12, w=8, t=None, l=5, q=None, coat=True, detal="yoq", c=None, kalit_=None, yield_=None):
    tana = {"name": nom, "category": cat, "is_coated": coat, "unit_price": 10000, "loy_kg": 0}
    if cat == "profil":
        tana.update(width=h, thickness=w, length=l, quantity=1)
    else:
        if yield_:
            tana.update(width=h, thickness=t, length=q / yield_, quantity=q, notes=f"dona_yield={yield_}")
        else:
            tana.update(width=None, thickness=None, length=None, quantity=q, unit_price_for_volume=10000)
    if detal != "yoq":
        tana["dokon_detal_id"] = detal
    hd = {"X-Amal-Kaliti": kalit_ or amal()}
    return (c or CA).post(PR, json=tana, headers=hd)


def tayyor_qil(pid, c=None):
    return (c or CA).post(f"/api/finished/{pid}/complete")


def sayt_qoldiq(did):
    if hasattr(crud, "_DOKON_API_CHEKLOV"):
        crud._DOKON_API_CHEKLOV.tozala()
    j = js(DOK.get("/api/dokon/v1/tayyor", headers={"X-Dokon-Kalit": KALIT[0] or "pdk_x"}))
    return next((x.get("qoldiq") for x in (j.get("detallar") or []) if x.get("detal_id") == did), None)


KALIT = [None]

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_html = open(os.path.join(ROOT, "templates", "finished.html"), encoding="utf-8").read()
_crud = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
check("S1 sxema / qoida: ProduceCreate.dokon_detal_id (1 … 2 147 483 647, bo'sh mumkin); `_val_rules` Produce — id",
      "dokon_detal_id" in getattr(schemas.ProduceCreate, "model_fields", {})
      and crud._val_rules()["Produce"].get("dokon_detal_id") == ("id", True))
check("S2 crud: dokon_tm_katalog, dokon_partiya_katalogga; marshrut GET /api/finished/katalog-detallar (ishlab chiqarish ruxsati)",
      callable(getattr(crud, "dokon_tm_katalog", None)) and callable(getattr(crud, "dokon_partiya_katalogga", None))
      and any(getattr(r, "path", None) == KR and "GET" in getattr(r, "methods", ()) for r in main.app.routes))
_tm = re.search(r"\{% if sayt_katalogi_bormi\(current_user\) %\}\s*<div class=\"pk242-qator\">.*?\{% endif %\}", _html, re.S)
check("S3 shablon: «📖 Katalogdan tanlash» tugmasi FAQAT `sayt_katalogi_bormi` ostida; oyna (`data-yopish`), qidiruv; saqlashda "
      "`dokon_detal_id`; xabarda `katalog.matn`",
      _tm is not None and "Katalogdan tanlash" in _tm.group(0) and 'id="katalog242"' in _html
      and re.search(r'id="katalog242".*?data-yopish', _html, re.S) is not None
      and "data.dokon_detal_id = window._pKat242.detal_id" in _html and "r.katalog.matn" in _html)
_fn = re.search(r"function pKatalogChiz\(\) \{.*?\n\}\n", _html, re.S)
check("S4 ro'yxat chizish — server matni faqat textContent (innerHTML ga o'zgaruvchi qo'shilmaydi)",
      _fn is not None and "textContent = x.nom" in _fn.group(0)
      and not re.search(r"innerHTML\s*(\+?=)\s*(?!'')[^;]*\$\{", _fn.group(0)), _fn.group(0)[:300] if _fn else None)
check("S5 bog'lash — o'sha tranzaksiyada: `dokon_partiya_katalogga` ichida commit / rollback YO'Q; qulf tartibi korxona (238) → model → qator",
      (lambda b: b is not None and "db.commit" not in b.group(0) and "db.rollback" not in b.group(0)
       and b.group(0).find("_pul_qulfi(db, SAYT_TM_QULF_NS") < b.group(0).find("_dokon_model_of(db, _d0.model_id, company_id, lock=True)")
       < b.group(0).find("_dokon_detal_of(db, detal_id, company_id, lock=True)"))
      (re.search(r"def dokon_partiya_katalogga\(.*?\n(?=\n\n\S|\Z)", _crud, re.S)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Kirish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_f0, _p0 = fp_soni(), peno()
_r = [CA.get(KR).status_code, ishlab("O'chiq katalog 12 sm", detal=1).status_code]
check("A1 katalog o'chiq: ro'yxat 404; `dokon_detal_id` bilan ishlab chiqarish 400 — partiya YO'Q, penoplast o'zgarmadi",
      _r == [404, 400] and fp_soni() == _f0 and peno() == _p0, (_r, fp_soni(), _f0, peno(), _p0))
r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
check("A0 platforma: korxona 1 da sayt katalogi yoqildi", r.status_code == 200, r.text[:200])
KALIT[0] = js(CA.post(API + "/api-kalit", json={})).get("kalit")
K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}


def model(bolim, kod, c=None, **kw):
    return js((c or CA).post(API + "/modellar", json=dict({"bolim_id": bolim, "kod": kod}, **kw))).get("id")


def detal(mid, turi, olcham, c=None, **kw):
    return js((c or CA).post(API + "/detallar", json=dict({"model_id": mid, "turi": turi, "olcham": olcham}, **kw))).get("id")


M_R = model(BOL.get("Rom va eshik dekorlari"), "R-18", nom="Klassik", kapitel_baza_bor=True)
D = {t: detal(M_R, t, "O'rta", narx=10000, eni_sm=15, qalinligi_sm=10) for t in ("karniz", "podokonnik", "nalichnik", "kapitel", "baza")}
M_K = model(BOL.get("Karnizlar"), "K-12", nom="Tekis")
D["k12"] = detal(M_K, "asosiy", "12 sm", narx=45000, narx_qoplamali=98000, ulgurji_narx=40000, eni_sm=12, qalinligi_sm=8)
D["k14"] = detal(M_K, "asosiy", "14 sm", narx=47000, eni_sm=14, qalinligi_sm=8)
D["k16"] = detal(M_K, "asosiy", "16 sm", narx=49000, eni_sm=16, qalinligi_sm=8)
D["k18"] = detal(M_K, "asosiy", "18 sm", narx=51000, eni_sm=18, qalinligi_sm=8)
D["k20"] = detal(M_K, "asosiy", "20 sm", narx=53000, eni_sm=20, qalinligi_sm=8)
M_T = model(BOL.get("Termopanel"), "TP-2", nom="Termopanel")
D["tp"] = detal(M_T, "asosiy", "4 sm", narx=90000, eni_sm=50, qalinligi_sm=4)
M_D = model(BOL.get("Dekor elementlar"), "D-2", nom="Burchak <b>x</b>")
D["d2"] = detal(M_D, "asosiy", "S", narx=9900)
M_Y = model(BOL.get("Karnizlar"), "K-30", nom="Yashirin", yoqilgan=False)
D["k30"] = detal(M_Y, "asosiy", "30 sm", narx=60000, eni_sm=30, qalinligi_sm=10)
check("A2 sinov katalogi: R-18 (5 detal), K-12 (12 / 14 / 16 / 18 / 20 sm), TP-2 (m²), D-2 (dona), K-30 (yashirin)",
      all(isinstance(v, int) for v in D.values()), D)
_st = {u: c.get(KR).status_code for u, c in (("admin", CA), ("menejer", CM), ("omborchi", CW), ("usta", CU))}
check("A3 ro'yxat: Admin / Menejer / Omborchi (ishlab chiqarish ruxsati) — 200, Usta — 403",
      _st == {"admin": 200, "menejer": 200, "omborchi": 200, "usta": 403}, _st)
_st_b = CB.get(KR).status_code
check("A4 B korxona (katalog o'chiq) — ro'yxat 404", _st_b == 404, _st_b)
_f0b = fp_soni(2)
_rb = ishlab("Begona detal 12 sm", detal=D["k12"], c=CB)
check("A5 B korxona A ning detali bilan ishlab chiqarsa — 400, partiya YO'Q, A detali bog'lanmadi",
      _rb.status_code == 400 and fp_soni(2) == _f0b and bog(D["k12"]) is None, (_rb.status_code, _rb.text[:200], fp_soni(2), _f0b))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Ro'yxat")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
L = js(CA.get(KR)).get("detallar") or []
LD = {x.get("detal_id"): x for x in L}
check("K1 faqat metr / dona detallar: R-18 (5), K-12 (5), D-2, K-30 (yashirin ham) — m² (TP-2) YO'Q",
      set(LD) == {D[k] for k in D if k != "tp"}, sorted(LD))
_narx = [k for x in L for k in x if "narx" in k or "ulgurji" in k or "tannarx" in k]
check("K2 narx / ulgurji / tannarx maydoni YO'Q", not _narx and "45000" not in json.dumps(L) and "98000" not in json.dumps(L), _narx)
_k12 = LD.get(D["k12"], {})
check("K3 K-12 12 sm: nom «K-12 Tekis · 12 sm» (`_sayt_nom`), turkum profil, birlik metr, eni 12 / qalinligi 8, saytda, bog'lam yo'q",
      _k12.get("nom") == "K-12 Tekis · 12 sm" and _k12.get("turkum") == "profil" and _k12.get("birlik") == "metr"
      and _k12.get("eni") == 12 and _k12.get("qalinligi") == 8 and _k12.get("saytda") is True and _k12.get("bog") is None, _k12)
_kap, _d2, _k30 = LD.get(D["kapitel"], {}), LD.get(D["d2"], {}), LD.get(D["k30"], {})
check("K4 Kapitel R-18 — «Kapitel R-18 · 15 sm», turkum dona; D-2 — «D-2 Burchak <b>x</b>» (HTML — o'zgarmagan matn); K-30 — saytda=false",
      _kap.get("nom") == _n246("Kapitel R-18 · 15 sm", "O'rta") and _kap.get("turkum") == "dona" and _d2.get("nom") == _n246("D-2 Burchak <b>x</b>", "S")
      and _d2.get("turkum") == "dona" and _k30.get("saytda") is False, (_kap, _d2, _k30))
_tartib = [x["detal_id"] for x in L]
check("K5 tartib: bo'lim → model → detal (R-18 detallari ketma-ket, K-12 12 → 20 sm)",
      lambda: _tartib.index(D["karniz"]) < _tartib.index(D["baza"]) and _tartib.index(D["k12"]) < _tartib.index(D["k14"]) < _tartib.index(D["k20"])
      and abs(_tartib.index(D["karniz"]) - _tartib.index(D["baza"])) == 4, _tartib)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. Ishlab chiqarish — bog'lash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_jur0 = xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == "dokon_detal").count(), 0)
r1 = ishlab("K-12 Tekis · 12 sm", h=12, w=8, l=10, detal=D["k12"])
j1 = js(r1)
P1 = j1.get("product_id")
check("P1 bog'lanmagan detal → 200, katalog.holat «boglandi», matnda «bog'landi»; detal kaliti = partiya kaliti; «Faoliyat jurnali» +1",
      r1.status_code == 200 and (j1.get("katalog") or {}).get("holat") == "boglandi" and "bog'landi" in (j1.get("katalog") or {}).get("matn", "")
      and P1 and bog(D["k12"]) == kalit(P1)
      and xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == "dokon_detal").count(), 0) == _jur0 + 1,
      (r1.status_code, j1.get("katalog"), bog(D["k12"]), kalit(P1) if P1 else None))
_q0 = sayt_qoldiq(D["k12"])
tayyor_qil(P1)
_q1 = sayt_qoldiq(D["k12"])
check("P2 saytda: «Sotuvga tayyor» dan OLDIN qoldiq 0 / yo'q, keyin 10 m", (_q0 in (None, 0, 0.0)) and _q1 == 10, (_q0, _q1))
r2 = ishlab("k-12  tekis · 12 sm", h=12.0, w=8.0, l=6, detal=D["k12"])
j2 = js(r2)
tayyor_qil(j2.get("product_id"))
check("P3 ikkinchi partiya (harf / bo'shliq farqi — o'sha mahsulot) → «qoshildi», bog'lam o'zgarmadi; saytda 16 m",
      r2.status_code == 200 and (j2.get("katalog") or {}).get("holat") == "qoshildi" and bog(D["k12"]) == kalit(P1)
      and sayt_qoldiq(D["k12"]) == 16, (r2.status_code, j2.get("katalog"), sayt_qoldiq(D["k12"])))
L2 = {x["detal_id"]: x for x in js(CA.get(KR)).get("detallar") or []}
check("P4 ro'yxatda K-12 12 sm — bog'lam: eng yangi partiya nomi «k-12  tekis · 12 sm», eni 12 / qalinligi 8, partiya bor",
      (L2.get(D["k12"]) or {}).get("bog") == {"nom": "k-12  tekis · 12 sm", "eni": 12.0, "qalinligi": 8.0, "partiya_bor": True},
      (L2.get(D["k12"]) or {}).get("bog"))
r3 = ishlab("K-12 Tekis · 14 sm", h=14, w=8, l=3, coat=False, detal=D["k14"])
j3 = js(r3)
check("P5 qoplamasiz → partiya yaratildi, holat «qoplamasiz», detal bog'lanmadi",
      r3.status_code == 200 and j3.get("product_id") and (j3.get("katalog") or {}).get("holat") == "qoplamasiz" and bog(D["k14"]) is None,
      (r3.status_code, j3.get("katalog"), bog(D["k14"])))
r4 = ishlab("K-12 Tekis · 14 sm", cat="dona", q=5, detal=D["k14"])
j4 = js(r4)
check("P6 birlik mos emas (metrli detal, donali partiya) → partiya yaratildi, holat «birlik», bog'lanmadi",
      r4.status_code == 200 and (j4.get("katalog") or {}).get("holat") == "birlik" and bog(D["k14"]) is None, (r4.status_code, j4.get("katalog")))
# K-12 16 sm — avval qo'lda (zip 238) boshqa nomli partiyaga bog'langan
r5a = ishlab("Karniz K12 16sm", h=16, w=8, l=4)
P5a = js(r5a).get("product_id")
tayyor_qil(P5a)
_rb5 = CA.put(API + f"/detallar/{D['k16']}/tm", json={"tm_kaliti": kalit(P5a)})
r5 = ishlab("K-12 Tekis · 16 sm", h=16, w=8, l=2, detal=D["k16"])
j5 = js(r5)
check("P7 detal boshqa mahsulotga bog'langan (qo'lda, «Karniz K12 16sm») → partiya yaratildi, holat «boshqa», bog'lam O'ZGARMADI",
      _rb5.status_code == 200 and r5.status_code == 200 and (j5.get("katalog") or {}).get("holat") == "boshqa"
      and bog(D["k16"]) == kalit(P5a) and "Omborga bog'lash" in (j5.get("katalog") or {}).get("matn", ""),
      (_rb5.status_code, r5.status_code, j5.get("katalog")))
L3 = {x["detal_id"]: x for x in js(CA.get(KR)).get("detallar") or []}
check("P8 ro'yxatda K-12 16 sm — bog'lam nomi «Karniz K12 16sm» (keyingi tanlov o'sha mahsulotni to'ldiradi)",
      ((L3.get(D["k16"]) or {}).get("bog") or {}).get("nom") == "Karniz K12 16sm", (L3.get(D["k16"]) or {}).get("bog"))
# K-12 18 sm partiyasi — kaliti K-12 12 sm ga bog'langan mahsulot bilan bir xil (nom / o'lcham AYNAN)
r6 = ishlab("K-12 Tekis · 12 sm", h=12, w=8, l=1, detal=D["k18"])
j6 = js(r6)
check("P9 mahsulot boshqa detalga bog'langan (12 sm) → partiya yaratildi, holat «band» (o'sha detal nomi bilan), 18 sm bog'lanmadi",
      r6.status_code == 200 and (j6.get("katalog") or {}).get("holat") == "band" and "K-12 Tekis · 12 sm" in (j6.get("katalog") or {}).get("matn", "")
      and bog(D["k18"]) is None and bog(D["k12"]) == kalit(P1), (r6.status_code, j6.get("katalog"), bog(D["k18"])))
r7 = ishlab(_n246("Kapitel R-18 · 15 sm", "O'rta"), cat="dona", h=15, t=10, q=10, yield_=5, detal=D["kapitel"])
j7 = js(r7)
check("P10 donali (Kapitel, «1 metrdan nechta» bilan) → «boglandi», kalit turkumi dona; tayyor bo'lgach saytda 10 dona",
      r7.status_code == 200 and (j7.get("katalog") or {}).get("holat") == "boglandi" and (bog(D["kapitel"]) or "").startswith("dona|")
      and tayyor_qil(j7.get("product_id")).status_code == 200 and sayt_qoldiq(D["kapitel"]) == 10, (r7.status_code, j7.get("katalog")))
_f0, _p0 = fp_soni(), peno()
_xato = {}
for _v in (999_999, 0, -1, "5", True, 2_147_483_648, 1.5):
    _r = ishlab("Noto'g'ri detal 20 sm", h=20, w=8, l=2, detal=_v)
    _xato[repr(_v)] = _r.status_code
check("P11 noto'g'ri `dokon_detal_id` (yo'q / 0 / −1 / matn / bool / 2³¹ / kasr) — 400, partiya YO'Q, penoplast o'zgarmadi",
      all(v == 400 for v in _xato.values()) and fp_soni() == _f0 and peno() == _p0, (_xato, fp_soni(), _f0, peno(), _p0))
_ak = amal()
r8a = ishlab("K-12 Tekis · 20 sm", h=20, w=8, l=3, detal=D["k20"], kalit_=_ak)
_f8 = fp_soni()
r8b = ishlab("K-12 Tekis · 20 sm", h=20, w=8, l=3, detal=D["k20"], kalit_=_ak)
check("P12 takror (`X-Amal-Kaliti` o'sha) — ikkinchi so'rov yangi partiya yaratmaydi, javob (katalog bilan) AYNAN",
      r8a.status_code == 200 and r8b.status_code == 200 and fp_soni() == _f8 and js(r8a).get("product_id") == js(r8b).get("product_id")
      and (js(r8b).get("katalog") or {}).get("holat") == "boglandi", (r8a.status_code, r8b.status_code, js(r8b).get("katalog"), fp_soni(), _f8))
r9 = ishlab("Oddiy karniz 25 sm", h=25, w=8, l=2)
check("P13 `dokon_detal_id` siz — avvalgidek (200, javobda `katalog` yo'q)", r9.status_code == 200 and "katalog" not in js(r9), js(r9))
r10 = ishlab("K-30 Yashirin · 30 sm", h=30, w=10, l=2, detal=D["k30"], c=CM)
check("P14 Menejer, yashirin model detali — «boglandi» (jurnalda Menejer nomi)",
      r10.status_code == 200 and (js(r10).get("katalog") or {}).get("holat") == "boglandi"
      and xavfsiz(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == "dokon_detal", ActivityLog.entity_id == D["k30"])
                  .order_by(ActivityLog.id.desc()).first().performed_by, "") == "T242 Menejer", (r10.status_code, js(r10).get("katalog")))
# partiyasi qolmagan bog'lam — ro'yxatda kalitdagi o'lcham
_k20 = bog(D["k20"])
db_ishi(lambda d: d.query(FinishedProduct).filter(FinishedProduct.id == js(r8a).get("product_id")).delete())
L4 = {x["detal_id"]: x for x in js(CA.get(KR)).get("detallar") or []}
check("P15 bog'langan mahsulotning partiyasi qolmagan — ro'yxatda bog'lam: nom (kalitdan; katalog nomi bilan kichik harfda teng — katalog "
      "nomi), eni 20 / qalinligi 8 (kalitdan), partiya_bor=false (review242 L1)",
      _k20 and (L4.get(D["k20"]) or {}).get("bog") == {"nom": "K-12 Tekis · 20 sm", "eni": 20.0, "qalinligi": 8.0, "partiya_bor": False},
      (L4.get(D["k20"]) or {}).get("bog"))

# review242 H1: bog'lanmagan detal — FAQAT katalogning o'z nomi / o'lchami bilan (tanlovdan keyin qo'lda o'zgartirilsa — «farq»)
_d18 = detal(M_K, "asosiy", "28 sm", narx=58000, eni_sm=28, qalinligi_sm=8)
_r18a = ishlab("Butunlay boshqa mahsulot", h=28, w=8, l=2, detal=_d18)
_r18b = ishlab("K-12 Tekis · 28 sm", h=30, w=3, l=2, detal=_d18)
_r18c = ishlab("K-12 Tekis · 28 sm", h=28, w=9, l=2, detal=_d18)
check("P18 bog'lanmagan detal, nom yoki o'lcham katalogdagidan farq (boshqa nom / 30 × 3 / qalinligi 9) — partiya yaratildi, holat «farq» "
      "(matnda katalog nomi va o'lchami), detal BOG'LANMADI",
      all(x.status_code == 200 and (js(x).get("katalog") or {}).get("holat") == "farq" for x in (_r18a, _r18b, _r18c))
      and "K-12 Tekis · 28 sm" in (js(_r18a).get("katalog") or {}).get("matn", "") and "eni 28 sm" in (js(_r18a).get("katalog") or {}).get("matn", "")
      and bog(_d18) is None, [(x.status_code, js(x).get("katalog")) for x in (_r18a, _r18b, _r18c)])
_r18d = ishlab(" k-12  TEKIS · 28 sm ", h=28.0, w=8.0, l=2, detal=_d18)
check("P19 o'sha detal, nom harf / bo'shliq farqi bilan, o'lcham AYNAN — «boglandi»",
      _r18d.status_code == 200 and (js(_r18d).get("katalog") or {}).get("holat") == "boglandi" and bog(_d18) == kalit(js(_r18d).get("product_id")),
      (_r18d.status_code, js(_r18d).get("katalog")))
_r18e = ishlab(_n246("Baza R-18 · 15 sm", "O'rta"), cat="dona", q=4, detal=D["baza"])
check("P20 donali, «1 metrdan nechta»siz (o'lchamsiz) — katalog nomi bilan «boglandi»",
      _r18e.status_code == 200 and (js(_r18e).get("katalog") or {}).get("holat") == "boglandi", (_r18e.status_code, js(_r18e).get("katalog")))

# crud to'g'ridan-to'g'ri: boshqa korxona partiyasi (marshrut o'z partiyasini beradi — himoya qatlami)
_fpb = js(ishlab("B partiya 12 sm", h=12, w=8, l=2, c=CB)).get("product_id")
_p16 = None
try:
    _s16 = SessionLocal()
    try:
        crud.dokon_partiya_katalogga(_s16, _fpb, D["k14"], 1, "t242")
        _p16 = "xato yo'q"
    finally:
        _s16.rollback()
        _s16.close()
except ValueError as _e16:
    _p16 = str(_e16)
except Exception as _e16:                  # noqa: BLE001
    _p16 = f"{type(_e16).__name__}: {_e16}"
check("P16 crud: boshqa korxonaning partiyasi (B) A detaliga — rad («Partiya topilmadi»), detal bog'lanmadi",
      _fpb and _p16 == "Partiya topilmadi" and bog(D["k14"]) is None, (_fpb, _p16, bog(D["k14"])))
# katalog keyin o'chirilsa — detal bor, lekin bog'lanmaydi, partiya ham yozilmaydi
_f0, _p0 = fp_soni(), peno()
_o17 = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "0"}).status_code
_r17 = ishlab("K-12 Tekis · 14 sm", h=14, w=8, l=2, detal=D["k14"])
_l17 = CA.get(KR).status_code
_y17 = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"}).status_code
check("P17 katalog keyin O'CHIRILSA (detallar bor): ishlab chiqarish 400 («yoqilmagan»), partiya YO'Q, penoplast o'zgarmadi, detal bog'lanmadi; "
      "ro'yxat 404; qayta yoqildi",
      _o17 == 200 and _r17.status_code == 400 and "yoqilmagan" in _r17.text and fp_soni() == _f0 and peno() == _p0
      and bog(D["k14"]) is None and _l17 == 404 and _y17 == 200, (_o17, _r17.status_code, _r17.text[:200], _l17, _y17))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Parallel (faqat PG)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    _qd = detal(M_K, "asosiy", "22 sm", narx=55000, eni_sm=22, qalinligi_sm=8)
    _qn = {}

    def _par(i):
        c = mijoz("t242_admin" if i == 0 else "t242_men")
        _qn[i] = ishlab(f"K-12 Tekis · 22 sm{' v' + str(i) if i else ''}", h=22, w=8, l=2, detal=_qd, c=c)

    _f0 = fp_soni()
    _th = [threading.Thread(target=_par, args=(i,)) for i in range(2)]
    for _t in _th:
        _t.start()
    for _t in _th:
        _t.join(120)
    _hol = sorted((js(v).get("katalog") or {}).get("holat") for v in _qn.values())
    _kq = bog(_qd)
    _pids = [js(v).get("product_id") for v in _qn.values()]
    check("Q1 bitta bog'lanmagan detalga ikki xil partiya BIR VAQTDA — ikkalasi 200 (2 partiya), bittasi «boglandi», ikkinchisi «boshqa»; "
          "detal kaliti — «boglandi» bo'lganining kaliti (ikkinchisi «boshqa» yoki — nomi katalogdan farq qilsa — «farq»)",
          all(v.status_code == 200 for v in _qn.values()) and len(_qn) == 2 and _hol in (["boglandi", "boshqa"], ["boglandi", "farq"]) and fp_soni() == _f0 + 2
          and _kq in [kalit(p) for i, p in zip(_qn, _pids) if (js(_qn[i]).get("katalog") or {}).get("holat") == "boglandi"],
          ({i: (v.status_code, js(v).get("katalog")) for i, v in _qn.items()}, _kq))
    # Q2: marshrutlar xomashyo navbatida ketma-ket — korxona qulfini (238) sinash uchun crud ikki sessiyada (kech174 saboq)
    _qa = detal(M_K, "asosiy", "23 sm", narx=55000, eni_sm=23, qalinligi_sm=8)
    # boshqa MODEL — model qatori qulfi ikkalasini ketma-ket qilmaydi, faqat korxona qulfi (238) himoya qiladi
    _qb = detal(model(BOL.get("Karnizlar"), "K-23", nom="Parallel"), "asosiy", "23 sm", narx=55000, eni_sm=23, qalinligi_sm=8)
    _fa = js(ishlab("K-12 Tekis · 23 sm", h=23, w=8, l=2)).get("product_id")
    _fb = js(ishlab("K-12 Tekis · 23 sm", h=23, w=8, l=2)).get("product_id")
    _q2 = {}

    def _q2_bir():
        s1 = SessionLocal()
        try:
            _q2["a"] = crud.dokon_partiya_katalogga(s1, _fa, _qa, 1, "q2a")
            _q2["a_t"] = time.time()
            time.sleep(1.5)                                   # qulf ushlangan holda
            s1.commit()
            _q2["a_c"] = time.time()
        finally:
            s1.close()

    def _q2_ikki():
        time.sleep(0.4)
        s2 = SessionLocal()
        try:
            _q2["b"] = crud.dokon_partiya_katalogga(s2, _fb, _qb, 1, "q2b")
            _q2["b_t"] = time.time()
            s2.commit()
        finally:
            s2.close()

    _th = [threading.Thread(target=_q2_bir), threading.Thread(target=_q2_ikki)]
    for _t in _th:
        _t.start()
    for _t in _th:
        _t.join(60)
    check("Q2 crud ikki sessiyada: bir xil mahsulot ikki MODEL detaliga BIR VAQTDA — birinchisi «boglandi», ikkinchisi korxona qulfini kutadi "
          "(birinchi commit dan keyin) va «band»; faqat bitta detal bog'langan",
          (_q2.get("a") or {}).get("holat") == "boglandi" and (_q2.get("b") or {}).get("holat") == "band"
          and _q2.get("b_t", 0) >= _q2.get("a_c", 1e18) and bog(_qa) == kalit(_fa) and bog(_qb) is None,
          ({k: v for k, v in _q2.items()}, bog(_qa), bog(_qb)))
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
    _ud = detal(M_K, "asosiy", "24 sm <i>y</i>", narx=57000, eni_sm=24, qalinligi_sm=9)
    _ub = detal(M_K, "asosiy", "26 sm", narx=59000, eni_sm=26, qalinligi_sm=8)
    _fpu = js(ishlab("Karniz K12 26sm", h=26.5, w=8.5, l=4)).get("product_id")
    tayyor_qil(_fpu)
    _bu = CA.put(API + f"/detallar/{_ub}/tm", json={"tm_kaliti": kalit(_fpu)}).status_code
    _kut_soni = len(js(CA.get(KR)).get("detallar") or [])
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
                pg.goto(BU + "/finished", wait_until="networkidle")
                return ctx, pg, jsx

            ctx, pg, JSX = kir("t242_admin")
            pg.evaluate("openProduceModal()")
            pg.wait_for_timeout(200)
            _u1 = pg.evaluate("""() => { const b = document.getElementById('p-katalog-btn'); const r = b ? b.getBoundingClientRect() : null;
                return {bor: !!b, eni: r ? Math.round(r.width) : 0, boyi: r ? Math.round(r.height) : 0, chip: getComputedStyle(document.getElementById('p-katalog-chip')).display}; }""")
            check("U1 ishlab chiqarish oynasida «📖 Katalogdan tanlash» tugmasi ko'rinadi (bo'yi 32 px — .btn-sm), belgi yashirin",
                  _u1["bor"] and _u1["eni"] > 0 and _u1["boyi"] == 32 and _u1["chip"] == "none", _u1)
            pg.click("#p-katalog-btn")
            pg.wait_for_selector("#pk242-royxat .btn-tanlov", timeout=15000)
            _u2 = pg.evaluate("""() => ({oyna: getComputedStyle(document.getElementById('katalog242')).display,
                soni: document.querySelectorAll('#pk242-royxat .btn-tanlov').length, matn: document.getElementById('pk242-royxat').innerText,
                i: document.querySelectorAll('#pk242-royxat i, #pk242-royxat b').length})""")
            check("U2 oyna ochildi: detallar (m² yo'q), guruh sarlavhalari, bog'langanida «🔗 Omborga bog'langan»; nomdagi HTML — MATN",
                  _u2["oyna"] == "flex" and _u2["soni"] == _kut_soni and "TP-2" not in _u2["matn"] and "Omborga bog'langan" in _u2["matn"]
                  and "24 sm <i>y</i>" in _u2["matn"] and "D-2 Burchak <b>x</b>" in _u2["matn"] and _u2["i"] == 0,
                  {k: (v[:300] if isinstance(v, str) else v) for k, v in _u2.items()})
            pg.fill("#pk242-q", "14 sm")
            pg.wait_for_timeout(150)
            _u3 = pg.evaluate("() => Array.from(document.querySelectorAll('#pk242-royxat .btn-tanlov')).map(b => +b.dataset.detal)")
            check("U3 qidiruv «14 sm» — faqat K-12 14 sm", _u3 == [D["k14"]], _u3)
            pg.fill("#pk242-q", "")
            pg.wait_for_timeout(150)
            pg.evaluate("setPCoating(null, false)")             # tanlov qoplamani «Bor» qilishi kerak
            pg.click(f"#pk242-royxat .btn-tanlov[data-detal='{_ud}']")
            pg.wait_for_timeout(200)
            _u4 = pg.evaluate("""() => ({nom: document.getElementById('p-name').value, tur: document.getElementById('p-type').value,
                faol: (document.querySelector('#p-type-toggle .type-opt.active') || {}).dataset?.value, h: document.getElementById('p-h').value,
                w: document.getElementById('p-w').value, qop: document.getElementById('p-coated').value,
                oyna: getComputedStyle(document.getElementById('katalog242')).display,
                chip: getComputedStyle(document.getElementById('p-katalog-chip')).display, chipm: document.getElementById('p-katalog-matn').textContent})""")
            check("U4 tanlandi: nom «K-12 Tekis · 24 sm» (o'lcham matni nomda emas — eni), tur Profil, Eni 24, Kengligi 9, qoplama «Bor»; oyna "
                  "yopildi; belgi «… bog'lanadi»",
                  _u4["nom"] == _n246("K-12 Tekis · 24 sm", "24 sm <i>y</i>") and _u4["tur"] == "profil" and _u4["faol"] == "profil" and _u4["h"] == "24"
                  and _u4["w"] == "9" and _u4["qop"] == "true" and _u4["oyna"] == "none" and _u4["chip"] == "flex"
                  and "bog'lanadi" in _u4["chipm"], _u4)
            pg.click("#p-coat-toggle .coat-no")
            _u5 = pg.evaluate("() => ({m: document.getElementById('p-katalog-matn').textContent, o: document.getElementById('p-katalog-chip').classList.contains('ogoh')})")
            pg.click("#p-coat-toggle .coat-yes")
            _u5b = pg.evaluate("() => document.getElementById('p-katalog-chip').classList.contains('ogoh')")
            check("U5 qoplama «Yo'q» — belgida ogohlantirish (saytga bog'lanmaydi), «Bor» — ogohlantirish yo'qoladi",
                  _u5["o"] and "bog'lanmaydi" in _u5["m"] and not _u5b, (_u5, _u5b))
            pg.click("#p-katalog-btn")
            pg.wait_for_selector(f"#pk242-royxat .btn-tanlov[data-detal='{_ub}']", timeout=15000)
            pg.click(f"#pk242-royxat .btn-tanlov[data-detal='{_ub}']")
            pg.wait_for_timeout(200)
            _u4b = pg.evaluate("""() => ({nom: document.getElementById('p-name').value, h: document.getElementById('p-h').value,
                w: document.getElementById('p-w').value, chipm: document.getElementById('p-katalog-matn').textContent})""")
            check("U4b qo'lda bog'langan detal (K-12 26 sm → «Karniz K12 26sm», 26,5 × 8,5) tanlansa — maydonlar O'SHA mahsulotdan (nom, eni 26.5, "
                  "kengligi 8.5; katalogdagi 26 / 8 emas), belgi «… qo'shiladi»",
                  _bu == 200 and _u4b["nom"] == "Karniz K12 26sm" and _u4b["h"] == "26.5" and _u4b["w"] == "8.5" and "qo'shiladi" in _u4b["chipm"],
                  (_bu, _u4b))
            pg.click("#p-katalog-btn")
            pg.wait_for_selector(f"#pk242-royxat .btn-tanlov[data-detal='{D['kapitel']}']", timeout=15000)
            pg.click(f"#pk242-royxat .btn-tanlov[data-detal='{D['kapitel']}']")
            pg.wait_for_timeout(200)
            _u4d = pg.evaluate("""() => ({tur: document.getElementById('p-type').value, h: document.getElementById('p-h').value,
                t: document.getElementById('p-t').value, m: document.getElementById('p-katalog-matn').textContent,
                o: document.getElementById('p-katalog-chip').classList.contains('ogoh')})""")
            pg.fill("#p-donayield", "5")
            _u4d2 = pg.evaluate("() => ({m: document.getElementById('p-katalog-matn').textContent, o: document.getElementById('p-katalog-chip').classList.contains('ogoh')})")
            check("U4d donali Kapitel (o'lcham bilan bog'langan): Donali, Eni 15 / Qalinlik 10; «1 metrdan nechta» bo'sh — belgida ogohlantirish; "
                  "kiritilsa — «qo'shiladi» (review242 M2)",
                  _u4d["tur"] == "dona" and _u4d["h"] == "15" and _u4d["t"] == "10" and _u4d["o"] and "1 metrdan nechta" in _u4d["m"]
                  and not _u4d2["o"] and "qo'shiladi" in _u4d2["m"], (_u4d, _u4d2))
            pg.fill("#p-donayield", "")
            pg.click("#p-katalog-btn")
            pg.wait_for_selector(f"#pk242-royxat .btn-tanlov[data-detal='{_ud}']", timeout=15000)
            pg.click(f"#pk242-royxat .btn-tanlov[data-detal='{_ud}']")
            pg.wait_for_timeout(200)
            pg.fill("#p-name", "Butunlay boshqa mahsulot")
            _u4c = pg.evaluate("() => ({m: document.getElementById('p-katalog-matn').textContent, o: document.getElementById('p-katalog-chip').classList.contains('ogoh')})")
            pg.fill("#p-name", _n246("K-12 Tekis · 24 sm", "24 sm <i>y</i>"))
            pg.fill("#p-w", "12")
            _u4c2 = pg.evaluate("() => document.getElementById('p-katalog-matn').textContent")
            pg.fill("#p-w", "9")
            _u4c3 = pg.evaluate("() => ({m: document.getElementById('p-katalog-matn').textContent, o: document.getElementById('p-katalog-chip').classList.contains('ogoh')})")
            check("U4c tanlovdan keyin nom o'zgartirilsa — belgida «nomi o'zgartirildi … bog'lanmaydi»; kengligi o'zgartirilsa — «o'lchami "
                  "o'zgartirildi»; qaytarilsa — ogohlantirish yo'qoladi (review242 H1)",
                  _u4c["o"] and "nomi o'zgartirildi" in _u4c["m"] and "bog'lanmaydi" in _u4c["m"] and "o'lchami o'zgartirildi" in _u4c2
                  and not _u4c3["o"] and "bog'lanadi" in _u4c3["m"], (_u4c, _u4c2, _u4c3))
            pg.fill("#p-l", "3")
            pg.fill("#p-price", "50000")
            _f0 = fp_soni()
            _xab = []
            pg.on("console", lambda m: None)
            pg.evaluate("""() => { window.__xab = []; const _o = window.showMsg; window.showMsg = function (t, k) { window.__xab.push(String(t)); return _o.apply(this, arguments); }; }""")
            pg.click("#produce-btn")
            pg.wait_for_function("() => window.__xab.length > 0 || getComputedStyle(document.getElementById('p-error')).display !== 'none'",
                                 timeout=30000)
            _u6 = pg.evaluate("() => window.__xab.join('\\n---\\n') + ' | xato: ' + document.getElementById('p-error').textContent")
            check("U6 saqlash → partiya yaratildi, xabarda «bog'landi»; detal bog'landi",
                  fp_soni() == _f0 + 1 and "bog'landi" in _u6 and bog(_ud) is not None, (_u6[:400], fp_soni(), _f0))
            pg.evaluate("openProduceModal()")
            _u7 = pg.evaluate("() => ({c: getComputedStyle(document.getElementById('p-katalog-chip')).display, k: window._pKat242})")
            check("U7 oyna qayta ochilganda katalog tanlovi tozalangan", _u7["c"] == "none" and _u7["k"] is None, _u7)
            pg.evaluate("closeProduceModal()")
            check("U8 sahifada JS xatosi yo'q (kompyuter)", not JSX, JSX)
            ctx.close()
            ctx, pg, JSX = kir("t242_admin", 390, 844)
            pg.evaluate("openProduceModal()")
            pg.click("#p-katalog-btn")
            pg.wait_for_selector("#pk242-royxat .btn-tanlov", timeout=15000)
            _u9 = pg.evaluate("""() => { const q = document.querySelector('#katalog242 .pk242-quti').getBoundingClientRect();
                const b = document.querySelector('#katalog242 [data-yopish]').getBoundingClientRect();
                return {chap: Math.round(q.left), ong: Math.round(q.right), tepa: Math.round(q.top), past: Math.round(q.bottom), vw: innerWidth,
                        vh: innerHeight, yop: Math.round(b.top), sw: document.documentElement.scrollWidth}; }""")
            check("U9 telefon (390 × 844): oyna ekranga sig'adi (chap / o'ng / tepa / past), yopish tugmasi ko'rinadi, gorizontal aylanish yo'q",
                  _u9["chap"] >= 0 and _u9["ong"] <= _u9["vw"] and _u9["tepa"] >= 0 and _u9["past"] <= _u9["vh"] and _u9["yop"] >= 0
                  and _u9["sw"] <= _u9["vw"], _u9)
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(200)
            _u10 = pg.evaluate("() => ({k: getComputedStyle(document.getElementById('katalog242')).display, p: getComputedStyle(document.getElementById('prodModal')).display})")
            check("U10 Esc — avval katalog oynasi yopiladi, ishlab chiqarish oynasi ochiq qoladi", _u10 == {"k": "none", "p": "flex"}, _u10)
            check("U11 sahifada JS xatosi yo'q (telefon)", not JSX, JSX)
            ctx.close()
            ctx, pg, JSX = kir("t242_b")
            _u12 = pg.evaluate("() => ({b: !!document.getElementById('p-katalog-btn'), o: !!document.getElementById('katalog242')})")
            check("U12 katalog o'chiq korxona (B) — tugma ham, oyna ham YO'Q; JS xatosi yo'q", _u12 == {"b": False, "o": False} and not JSX, (_u12, JSX))
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
    print("\nYiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
