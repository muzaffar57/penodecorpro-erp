#!/usr/bin/env python3
"""
test_havola254.py — kech186 (zip 254: do'kon 3-bosqich «Ustaning shaxsiy havolasi», ERP tomoni).

NIMA UCHUN KERAK
  Egasi QARORLARI («Onlayn do'kon rejasi» 30.10, AskUserQuestion 04.11): usta o'z havolasini mijoziga yuboradi; mijoz shu havola orqali
  buyurtma bersa — keshbek havola egasiga; havola orqali kirgan mijozning keyingi buyurtmalari ham 30 kun shu ustaga; ikki xil havola —
  OXIRGI havola egasiga; usta o'zi buyurtma bersa — o'ziga; ulgurji buyurtmaga keshbek YO'Q. Asl kodda (zip 253) havola YO'Q — buyurtma
  tanasidagi «havola» rad etiladi (400), ERP buyurtmasi ustasiz — test yiqiladi (qulamaydi).
BO'LIMLAR
  S — tayyorgarlik. K — havola kodi (kabinet API). B — buyurtma ↔ havola (kod, telefon bo'yicha 30 kun, oxirgi havola, o'z usta hisobi,
  magazin chakana, noto'g'ri kod, bloklangan, takror). U — ERP buyurtmasiga usta (tasdiq), hisob tasdig'ida bog'lash, ulgurji. Z — ikkinchi
  korxona, Telegram yorlig'i, zaxira.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432`.
"""
import os
import io
import sys
import json
import tempfile
import contextlib
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"havola254_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t254_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't254.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "DOKON_BOT_TOKEN", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Order           # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
DokonMijoz = models.DokonMijoz
DokonBuyurtma = models.DokonBuyurtma


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


def bazadan(fn):
    d = SessionLocal()
    try:
        return fn(d)
    except Exception:                      # noqa: BLE001
        d.rollback()
        return None
    finally:
        d.close()


TG = []
main._send_telegram = lambda *a, **k: TG.append(" ".join(str(x) for x in a)) or True

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Tayyorgarlik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
s.add(Company(id=2, name="T254 Begona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t254_admin", PAROL, UserRole.ADMIN, "T254 Admin", company_id=1)
    auth.create_user(s, "t254_plat", PAROL, UserRole.ADMIN, "T254 Platforma", company_id=1)
    auth.create_user(s, "t254_b", PAROL, UserRole.ADMIN, "T254 B", company_id=2)
s.query(User).filter(User.username.in_(["t254_plat"])).first().is_platform_admin = True
s.commit()
s.close()


def kirish(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA, CP, CB = kirish("t254_admin"), kirish("t254_plat"), kirish("t254_b")
NC = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
CP.post("/api/platform/companies/2/dokon", data={"yoqilgan": "1"})
KALIT = js(CA.post(API + "/api-kalit", json={})).get("kalit") or ""
K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}
MOD = js(CA.post(API + "/modellar", json={"bolim_id": BOL.get("Karnizlar"), "kod": "K-54", "nom": "Havola"})).get("id")
DET = js(CA.post(API + "/detallar", json={"model_id": MOD, "turi": "asosiy", "olcham": "12 sm", "narx": 45000, "eni_sm": 12,
                                            "qalinligi_sm": 8})).get("id")
Q = [{"detal_id": DET, "qoplamali": False, "miqdor": 4}]


def chek_tozala():
    for _n in ("_DOKON_API_CHEKLOV", "_DOKON_MIJOZ_CHEKLOV", "_DOKON_BUYURTMA_CHEKLOV"):
        _ch = getattr(crud, _n, None)
        if _ch is not None:
            _ch.tozala()


_kn = [0]


def buyurtma(telefon, havola=None, sessiya=None, kalit=None, amal=None, qatorlar=None):
    chek_tozala()
    _kn[0] += 1
    h = {"X-Dokon-Kalit": KALIT if kalit is None else kalit, "X-Amal-Kaliti": amal or f"savat-{_kn[0]:06d}-t254",
         "Content-Type": "application/json"}
    if sessiya is not None:
        h["X-Mijoz-Sessiya"] = sessiya
    tana = {"mijoz": "Ali Valiyev", "telefon": telefon, "viloyat": "andijon", "qatorlar": qatorlar or Q}
    if havola is not None:
        tana["havola"] = havola
    return NC.post("/api/dokon/v1/buyurtmalar", content=json.dumps(tana).encode("utf-8"), headers=h)


def sb(raqam):
    return bazadan(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.sb_raqam == raqam).first())


def hav(r):
    return getattr(sb(js(r).get("raqam")), "havola_mijoz_id", "YO'Q")


def tasdiqla(raqam):
    b = sb(raqam)
    r = CA.post(f"/api/sayt-buyurtmalari/{b.id}/tasdiqla", json={"deadline": "2026-11-30"})
    oid = bazadan(lambda d: d.query(DokonBuyurtma.order_id).filter(DokonBuyurtma.id == b.id).scalar())
    return r, oid


def order_master(oid):
    return bazadan(lambda d: d.query(Order.master_id).filter(Order.id == oid).scalar())


def hisob(tg, tel, turi, holat, ism, cid=1, **kw):
    d = SessionLocal()
    try:
        m = DokonMijoz(company_id=cid, mj_tg_id=tg, mj_telefon=tel, mj_ism=ism, mj_turi=turi, mj_holat=holat, **kw)
        d.add(m)
        d.commit()
        return m.id
    finally:
        d.close()


def sessiya(mid):
    d = SessionLocal()
    try:
        t = crud._dk_sessiya_yarat(d, d.get(DokonMijoz, mid), datetime.utcnow())
        d.commit()
        return t
    finally:
        d.close()


def keshbek(ses, kalit=None):
    chek_tozala()
    return NC.get("/api/dokon/v1/mijoz/keshbek", headers={"X-Dokon-Kalit": KALIT if kalit is None else kalit, "X-Mijoz-Sessiya": ses})


U1 = hisob("5401", "+998901110001", "usta", "kutilmoqda", "Birinchi usta")
U2 = hisob("5402", "+998901110002", "usta", "kutilmoqda", "Ikkinchi usta")
U3 = hisob("5403", "+998901110003", "usta", "kutilmoqda", "Uchinchi usta")
MG = hisob("5404", "+998901110004", "magazin", "tasdiqlangan", "Magazinchi", mj_magazin="Qurilish", mj_shahar="Asaka")
_rt = [CA.post(f"{API}/mijozlar/{x}/tasdiqla", json={"kpi": 5, "yangi_usta": True}).status_code for x in (U1, U2, U3)]
M1, M2, M3 = (bazadan(lambda d, x=x: d.get(DokonMijoz, x).master_id) for x in (U1, U2, U3))
S1, S2, S3, SM = sessiya(U1), sessiya(U2), sessiya(U3), sessiya(MG)
check("S0 tayyorgarlik: kalit, model / detal, 3 usta tasdiqlangan (ERP ustalari), magazin", KALIT and MOD and DET and _rt == [200] * 3
      and all((M1, M2, M3)), (_rt, M1, M2, M3, MOD, DET))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Havola kodi — kabinet API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
k1 = js(keshbek(S1))
k1b = js(keshbek(S1))
H1, H2, H3 = k1.get("havola"), js(keshbek(S2)).get("havola"), js(keshbek(S3)).get("havola")
import re                                         # noqa: E402
check("K1 tasdiqlangan usta — havola kodi (8 belgi, a–z 0–9), qayta so'rovda AYNAN, bazada saqlandi; har ustaniki — boshqa",
      isinstance(H1, str) and re.fullmatch(r"[a-z0-9]{8}", H1) and k1b.get("havola") == H1 and len({H1, H2, H3}) == 3
      and bazadan(lambda d: d.get(DokonMijoz, U1).mj_havola) == H1 and k1.get("havola_buyurtmalar") == 0, (k1, k1b))
check("K2 magazin — havola yo'q", js(keshbek(SM)).get("havola") is None and bazadan(lambda d: d.get(DokonMijoz, MG).mj_havola) is None,
      js(keshbek(SM)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Buyurtma ↔ havola")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TG.clear()
r = buyurtma("+998 93 100 00 01", havola=H1)
R1 = js(r).get("raqam")
check("B1 mehmon havola (U1 kodi) bilan — 200, buyurtma havola egasiga bog'landi; Telegramda «🔗 Usta havolasi: Birinchi usta»",
      r.status_code == 200 and hav(r) == U1 and TG and "🔗 Usta havolasi: Birinchi usta" in TG[-1], (r.status_code, r.text[:200], hav(r), TG[-1:]))
r = buyurtma("+998 93 100 00 01")
check("B2 o'sha telefon, havolasiz (cookie yo'qolgan) — 30 kun ichida — o'sha usta", r.status_code == 200 and hav(r) == U1, (r.text[:200], hav(r)))
r = buyurtma("+998 93 100 00 01", havola=H2)
r2 = buyurtma("+998 93 100 00 01")
check("B3 ikkinchi havola (U2) — OXIRGI havola egasiga; keyingi havolasiz buyurtma ham U2 ga", hav(r) == U2 and hav(r2) == U2, (hav(r), hav(r2)))
r = buyurtma("+998 93 100 00 02")
check("B4 boshqa telefon, havolasiz — havola yo'q", r.status_code == 200 and hav(r) is None, hav(r))
d0 = SessionLocal()
for x in d0.query(DokonBuyurtma).filter(DokonBuyurtma.sb_telefon.like("%931000001%")).all():
    x.created_at = datetime.utcnow() - timedelta(days=31)
    if getattr(x, "havola_vaqti", None) is not None:
        x.havola_vaqti = datetime.utcnow() - timedelta(days=31)
d0.commit()
d0.close()
r = buyurtma("+998 93 100 00 01")
check("B5 havola bilan oxirgi buyurtma 30 kundan eski — havolasiz buyurtma bog'lanmaydi", r.status_code == 200 and hav(r) is None, hav(r))
r = buyurtma("+998 93 100 00 03", havola=H1, sessiya=S2)
check("B6 kirgan USTA (U2) U1 havolasi bilan — havola e'tiborsiz (o'zi usta), buyurtma o'ziga", r.status_code == 200 and hav(r) is None
      and getattr(sb(js(r).get("raqam")), "mijoz_id", None) == U2, (r.text[:200], hav(r)))
r = buyurtma("+998 93 100 00 04", havola=H1, sessiya=SM)
R_MG = js(r).get("raqam")
check("B7 kirgan magazin chakana buyurtmasi havola bilan — havola egasiga (U1)", r.status_code == 200 and hav(r) == U1, (r.text[:200], hav(r)))
_bad = [buyurtma(f"+998 93 100 05 {i:02d}", havola=x) for i, x in enumerate(("ABCDEFGH", "abc", "a" * 9, 12345678, None, "zzzzzzzz", ["x"]))]
check("B8 noto'g'ri / noma'lum kod (katta harf, qisqa, uzun, son, ro'yxat, topilmagan) — buyurtma QABUL (200), havola yo'q",
      [x.status_code for x in _bad] == [200] * 7 and all(hav(x) is None for x in _bad), [(x.status_code, x.text[:60], hav(x)) for x in _bad])
_b9 = bazadan(lambda d: crud._sayt_havola_hisobi(d, 2, H1, "+998931000006", None, datetime.utcnow()))
check("B9 boshqa korxona (2) uchun A ustasi kodi — havola yo'q", _b9 == (None, None), _b9)
CA.post(f"{API}/mijozlar/{U3}/blokla")
r = buyurtma("+998 93 100 00 07", havola=H3)
check("B10 bloklangan usta kodi — havola yo'q", r.status_code == 200 and hav(r) is None, hav(r))
r1 = buyurtma("+998 93 100 00 08", havola=H1, amal="savat-takror-0254")
r2 = buyurtma("+998 93 100 00 08", havola=H1, amal="savat-takror-0254")
r3 = buyurtma("+998 93 100 00 08", havola=H2, amal="savat-takror-0254")
check("B11 takror (o'sha kalit + o'sha tana) — o'sha buyurtma; havolasi boshqa tana — 409 (kalit band)", r1.status_code == 200
      and js(r2).get("raqam") == js(r1).get("raqam") and r3.status_code == 409, (r1.text[:100], r2.text[:100], r3.status_code))
r = buyurtma("+998 93 100 00 09", havola=H1)
_ex = NC.post("/api/dokon/v1/buyurtmalar", headers={"X-Dokon-Kalit": KALIT, "X-Amal-Kaliti": "savat-ortiq-000254", "Content-Type": "application/json"},
              content=json.dumps({"mijoz": "Ali", "telefon": "+998 93 100 00 10", "viloyat": "andijon", "qatorlar": Q, "boshqa": 1}).encode())
check("B12 noma'lum maydon baribir 400 (faqat «havola» qo'shildi)", _ex.status_code == 400, (_ex.status_code, _ex.text[:120]))

r = buyurtma("+998 93 200 00 01", havola=H1)
_rr = js(r).get("raqam")
d0 = SessionLocal()
_b = d0.query(DokonBuyurtma).filter(DokonBuyurtma.sb_raqam == _rr).first()
_b.sb_holat = "bekor"
d0.commit()
d0.close()
r = buyurtma("+998 93 200 00 01")
check("R1 (review254 M1) havola bilan kelgan buyurtma BEKOR qilingan — telefon bo'yicha keyingisi bog'lanmaydi", hav(r) is None, hav(r))
r0 = buyurtma("+998 93 200 00 02", havola=H1)
d0 = SessionLocal()
_b0 = d0.query(DokonBuyurtma).filter(DokonBuyurtma.sb_raqam == js(r0).get("raqam")).first()
_b0.created_at = datetime.utcnow() - timedelta(days=25)
if hasattr(_b0, "havola_vaqti"):
    _b0.havola_vaqti = _b0.created_at
_v0 = getattr(_b0, "havola_vaqti", None)
d0.commit()
d0.close()
r1 = buyurtma("+998 93 200 00 02")
_v1 = getattr(sb(js(r1).get("raqam")), "havola_vaqti", None)
check("R2 (review254 M2) telefon bo'yicha bog'langan buyurtma — muddat KOD paytidan (nusxa), yangilanmaydi",
      hav(r1) == U1 and _v1 is not None and _v0 is not None and abs((_v1 - _v0).total_seconds()) < 1, (hav(r1), _v0, _v1))
d0 = SessionLocal()
for x in d0.query(DokonBuyurtma).filter(DokonBuyurtma.sb_telefon == "+998932000002").all():
    if hasattr(x, "havola_vaqti"):
        x.havola_vaqti = datetime.utcnow() - timedelta(days=31)
d0.commit()
d0.close()
r2 = buyurtma("+998 93 200 00 02")
check("R3 (review254 M2) kod bilan buyurtmaga 30 kun to'ldi — keyingi buyurtmalar (oraliqdagilar bo'lsa ham) bog'lanmaydi", hav(r2) is None, hav(r2))
r = buyurtma("+998 93 200 00 03", havola=H1)
r2 = buyurtma("+998 93 200 00 03", havola=H3)               # U3 — bloklangan
check("R4 (review254 L5) bloklangan usta kodi — telefon bo'yicha oldingi (amaldagi) havola egasi", hav(r2) == U1, hav(r2))
_k_soni = js(keshbek(S1)).get("havola_buyurtmalar")
_bekor = bazadan(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.havola_mijoz_id == U1, DokonBuyurtma.sb_holat == "bekor").count())
_hammasi = bazadan(lambda d: d.query(DokonBuyurtma).filter(DokonBuyurtma.havola_mijoz_id == U1).count())
check("R5 (review254 L3) kabinetdagi son — bekor qilinganlarsiz", lambda: _bekor >= 1 and _k_soni == _hammasi - _bekor, (_k_soni, _hammasi, _bekor))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. ERP buyurtmasiga usta")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r, oid = tasdiqla(R1)
check("U1 havola bilan kelgan mehmon buyurtmasi tasdiqlandi — ERP buyurtmasida havola egasining ustasi (keshbek)",
      r.status_code == 200 and oid and order_master(oid) == M1, (r.status_code, r.text[:200], oid, order_master(oid), M1))
r, oid = tasdiqla(R_MG)
check("U2 magazin chakana buyurtmasi (havola) — usta U1", r.status_code == 200 and order_master(oid) == M1, (r.text[:150], order_master(oid)))
b = SessionLocal()
_x = b.query(DokonBuyurtma).filter(DokonBuyurtma.sb_raqam == R1).first()
_x.sb_ulgurji = True
_u = crud.sayt_mijoz_ustasi(b, 1, _x)
b.rollback()
b.close()
check("U3 ulgurji buyurtma havola bilan bo'lsa ham — usta YO'Q (ulgurjiga keshbek yo'q)", _u is None, _u)
CA.post(f"{API}/mijozlar/{U3}/ochish")                       # blokdan chiqdi — «kutilmoqda», kod saqlangan
r = buyurtma("+998 93 100 00 11", havola=H3)
R_U3 = js(r).get("raqam")
r2, oid3 = tasdiqla(R_U3)
_m_oldin = order_master(oid3)
_rt3 = CA.post(f"{API}/mijozlar/{U3}/tasdiqla", json={"kpi": 4, "master_id": M3})
check("U4 qayta tasdiq kutayotgan usta havolasi — buyurtma bog'landi, ERP da ustasiz; hisob tasdiqlangach — ERP buyurtmasiga usta (bog'lash)",
      hav(r) == U3 and r2.status_code == 200 and _m_oldin is None and _rt3.status_code == 200 and order_master(oid3) == M3,
      (hav(r), r2.status_code, _m_oldin, _rt3.status_code, _rt3.text[:150], order_master(oid3)))
check("U5 kabinet: havola orqali kelgan buyurtmalar soni (mijoz ma'lumotisiz)", js(keshbek(S1)).get("havola_buyurtmalar", 0) >= 4
      and "Ali" not in keshbek(S1).text and "+998 93" not in keshbek(S1).text, js(keshbek(S1)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira, ikkinchi korxona")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bk = bazadan(lambda d: crud.export_full_backup(d, company_id=1)) or {}
_old = bazadan(lambda d: sorted((x.sb_raqam, x.havola_mijoz_id) for x in d.query(DokonBuyurtma).filter(DokonBuyurtma.company_id == 1).all()))
_oldm = bazadan(lambda d: sorted((x.id, x.mj_havola) for x in d.query(DokonMijoz).filter(DokonMijoz.company_id == 1).all()))
_res = bazadan(lambda d: crud.import_full_backup(d, _bk, company_id=1, replace=True)) or {}
check("Z1 zaxiradan tiklash — havola bog'lamlari va kodlar AYNAN qaytdi",
      _res.get("success") is True and _old == bazadan(lambda d: sorted((x.sb_raqam, x.havola_mijoz_id) for x in d.query(DokonBuyurtma)
                                                                      .filter(DokonBuyurtma.company_id == 1).all()))
      and _oldm == bazadan(lambda d: sorted((x.id, x.mj_havola) for x in d.query(DokonMijoz).filter(DokonMijoz.company_id == 1).all())),
      _res)
check("Z2 indekslar ro'yxatida yangi ustunlar (database.add_missing_indexes)",
      '("dokon_buyurtmalar", "havola_mijoz_id")' in open(os.path.join(ROOT, "database.py"), encoding="utf-8").read()
      and '("dokon_mijozlar", "mj_havola")' in open(os.path.join(ROOT, "database.py"), encoding="utf-8").read(), "")

if PG_URL:
    try:
        import database as _dbm254
        _dbm254.engine.dispose()
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
