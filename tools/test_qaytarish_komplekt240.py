#!/usr/bin/env python3
"""
test_qaytarish_komplekt240.py — kech174 (zip 240 «Komplekt bo'yicha qaytarish»; reja «Onlayn do'kon rejasi» 30.10, «Komplekt ERP'da qanday
bilinadi» 4-band: «Qaytarish yoki bekor qilishda butun komplekt yoki alohida detal tanlanadi»).

NIMA UCHUN KERAK
  O'LCHANGAN (`work/k240/probe240.py`, asl kod = zip 239): sayt komplekti (rom × 3 — 5 detal) qaytarilsa har detal ALOHIDA so'rov (5 ta +
  hisob-kitob yana 5 ta); bittasi rad etilsa qolganlari saqlanib qoladi — omborda «yarim komplekt»; komplekt kaliti — 400. Xato bo'lishi
  mumkin joylar: detalga noto'g'ri ulush (N / K), bir mahsulot ikki qatorga bo'linganda (ombordan partiyalar) yaxlitlash — jami buziladi,
  kasr dona, «o'z o'lchami» komplekt deb qaytishi, avval qaytarilgani hisobga olinmasligi, yarim yozilish (tranzaksiya), pul (kelishilgan
  summa, naqd) noto'g'ri, takror so'rov ikkinchi to'plam, to'plamning bir detalini o'chirib «yarim komplekt» qoldirish, begona korxona,
  ruxsatlar, parallel ikki so'rov ortiqcha qaytarishi, zaxirada belgi yo'qolishi, oynada noto'g'ri tanlov / matn.
BO'LIMLAR
  S — statik / tana tekshiruvi. A — reja (taqsimlash). B — yaratish. C — bitta tranzaksiya. D — «Hozir hisob-kitob». E — o'chirish.
  F — keyin hisob-kitob (`?komplekt=1`). G — takror kalit. H — tanlov / reja marshrutlari. I — korxona va ruxsat. K — parallel (PG).
  Z — zaxira. U — HAQIQIY brauzer.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` (U — faqat SQLite / TF1). `T240_TEZ=1` — U o'tkaziladi.
Asl kodga (zip 239) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_qaytarish_komplekt240.py
"""
import os
import io
import sys
import json
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
TEZ = os.environ.get("T240_TEZ") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qaytarish_komplekt240_test"
_T = tempfile.mkdtemp(prefix="t240_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't240.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Inventory, ReturnItem, FinishedProduct, Order, Payment, Rol      # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

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


def det(r):
    d = js(r)
    d = d.get("detail") if isinstance(d, dict) else d
    if isinstance(d, dict):
        d = d.get("message")
    return str(d)


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


def yaxlit(x, n=3):
    return round(float(x or 0), n)


main._send_telegram = lambda *a, **k: True
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T240 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t240_admin", PAROL, UserRole.ADMIN, "T240 Admin", company_id=1)
    auth.create_user(s, "t240_plat", PAROL, UserRole.ADMIN, "T240 Platforma", company_id=1)
    auth.create_user(s, "t240_omb", PAROL, UserRole.MANAGER, "T240 Omborchi", company_id=1)
    auth.create_user(s, "t240_b", PAROL, UserRole.ADMIN, "T240 B Admin", company_id=2)
    auth.create_user(s, "t240_omb2", PAROL, UserRole.MANAGER, "T240 Omborchi 2", company_id=1)
s.query(User).filter(User.username == "t240_plat").first().is_platform_admin = True
RETSEPT = models.Recipe(company_id=1, name="Qoplama T240")
s.add(RETSEPT)
s.add(Inventory(company_id=1, item_name="Penoplast T240", unit="blok", is_penoplast=True, is_default_penoplast=True,
                volume_per_unit=1.0, price_per_unit=1000000, stock_quantity=500))
s.flush()
# «Omborchi»: qaytarish — yaratish / ko'rish / o'chirish, hisob-kitob (tahrirlash) va tannarx — YO'Q
_rol = Rol(company_id=1, nom="T240 omborchi", kod=None, tavsif="",
           ruxsatlar=json.dumps({"qaytarish": ["korish", "yaratish", "ochirish"]}))
s.add(_rol)
s.flush()
s.query(User).filter(User.username == "t240_omb").first().rol_id = _rol.id
# «Omborchi 2»: qaytarish — hamma amal (hisob-kitob ham), tannarx — YO'Q (review240 L2)
_rol2 = Rol(company_id=1, nom="T240 omborchi 2", kod=None, tavsif="",
            ruxsatlar=json.dumps({"qaytarish": ["korish", "yaratish", "tahrirlash", "ochirish"]}))
s.add(_rol2)
s.flush()
s.query(User).filter(User.username == "t240_omb2").first().rol_id = _rol2.id
s.commit()
RID = RETSEPT.id
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t240_admin")
CP = mijoz("t240_plat")
CO = mijoz("t240_omb")
CO2 = mijoz("t240_omb2")
CB = mijoz("t240_b")
DOK = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
API = "/api/sayt-katalogi"
KQ = "/api/returns/komplekt"
_kn = [0]


def kalit():
    _kn[0] += 1
    return f"t240-kalit-{_kn[0]:06d}"


def qaytar_k(oid, g, soni, c=None, kal=None, **kw):
    tana = dict({"order_id": oid, "kmp_guruh": g, "soni": soni}, **kw)
    return (c or CA).post(KQ, json=tana, headers={"X-Amal-Kaliti": kal or kalit()})


def buyurtma(oid):
    return js(CA.get(f"/api/orders/{oid}"))


def qaytishlar(oid):
    return xavfsiz(lambda d: [(x.id, x.order_item_id, yaxlit(x.quantity), getattr(x, "kqt_kalit", None), getattr(x, "kqt_soni", None),
                               getattr(x, "kqt_nomi", None), bool(x.is_refunded),
                               yaxlit(x.refund_amount, 2)) for x in d.query(ReturnItem).filter(ReturnItem.order_id == oid)
                              .order_by(ReturnItem.id).all()], [])


def yid(lst, i, j=0):
    """Ro'yxat elementi (asl kodda ro'yxat bo'sh — QULAMASIN): yo'q bo'lsa 0."""
    try:
        return lst[i][j]
    except (IndexError, TypeError, KeyError):
        return 0


def tm_holat():
    def f(d):
        j = {}
        for x in d.query(FinishedProduct).filter(FinishedProduct.company_id == 1).all():
            j[x.name] = yaxlit(j.get(x.name, 0) + float(x.quantity or 0))
        return sorted(j.items())
    return xavfsiz(f, [])


def pul_holat(oid):
    def f(d):
        o = d.query(Order).filter(Order.id == oid).first()
        return (yaxlit(o.kelishilgan_summa, 2), yaxlit(sum(float(p.amount or 0) for p in d.query(Payment).filter(Payment.order_id == oid)), 2),
                sorted((yaxlit(p.amount, 2), getattr(p.payment_method, "value", p.payment_method))
                       for p in d.query(Payment).filter(Payment.order_id == oid)))
    return xavfsiz(f)


def tayyor_topshir(oid, topshir=True):
    CA.post(f"/api/orders/{oid}/ready", json={})
    if topshir:
        o = buyurtma(oid)
        r = CA.post("/api/deliveries", json={"order_id": oid, "items": [
            {"order_item_id": it["id"], "quantity": float(it["length"] * (it["quantity"] or 1) if it["category"] == "profil" else it["quantity"])}
            for it in o["items"]]})
        return r.status_code
    return None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik va tana tekshiruvi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ust = {c.name: c for c in ReturnItem.__table__.columns}
check("S1 return_items: kqt_kalit (String 40, indeks), kqt_soni (Integer), kqt_nomi (String 200) — NULL, standartsiz",
      all(k in _ust for k in ("kqt_kalit", "kqt_soni", "kqt_nomi")) and _ust["kqt_kalit"].type.length == 40
      and _ust["kqt_nomi"].type.length == 200 and all(_ust[k].nullable and _ust[k].default is None for k in ("kqt_kalit", "kqt_soni", "kqt_nomi"))
      and bool(_ust["kqt_kalit"].index), sorted(_ust))
_yollar = {(getattr(r, "path", ""), m) for r in main.app.routes for m in (getattr(r, "methods", None) or [])}
check("S2 marshrutlar: POST /api/returns/komplekt, GET /api/returns/komplekt/reja",
      ("/api/returns/komplekt", "POST") in _yollar and ("/api/returns/komplekt/reja", "GET") in _yollar)
_YOMON = [
    ("noma'lum kalit", {"order_id": 1, "kmp_guruh": 1, "soni": 1, "quantity": 2}),
    ("order_id yo'q", {"kmp_guruh": 1, "soni": 1}), ("soni yo'q", {"order_id": 1, "kmp_guruh": 1}),
    ("soni bool", {"order_id": 1, "kmp_guruh": 1, "soni": True}), ("soni kasr", {"order_id": 1, "kmp_guruh": 1, "soni": 1.5}),
    ("soni matn", {"order_id": 1, "kmp_guruh": 1, "soni": "1"}), ("soni 0", {"order_id": 1, "kmp_guruh": 1, "soni": 0}),
    ("soni 501", {"order_id": 1, "kmp_guruh": 1, "soni": 501}), ("guruh 0", {"order_id": 1, "kmp_guruh": 0, "soni": 1}),
    ("guruh 1001", {"order_id": 1, "kmp_guruh": 1001, "soni": 1}), ("order_id 2^31", {"order_id": 2 ** 31, "kmp_guruh": 1, "soni": 1}),
    ("sabab Brak", {"order_id": 1, "kmp_guruh": 1, "soni": 1, "reason": "Brak"}),
    ("sabab noma'lum", {"order_id": 1, "kmp_guruh": 1, "soni": 1, "reason": "Boshqa"}),
    ("izoh son", {"order_id": 1, "kmp_guruh": 1, "soni": 1, "notes": 5}),
    ("hisob noma'lum", {"order_id": 1, "kmp_guruh": 1, "soni": 1, "hisob": "ertaga"}),
    ("usul noma'lum", {"order_id": 1, "kmp_guruh": 1, "soni": 1, "hisob": "hozir", "payment_method": "kripto"}),
    ("usul hisobsiz", {"order_id": 1, "kmp_guruh": 1, "soni": 1, "payment_method": "naqd"}),
]
_rad = []
for _nom, _tana in _YOMON:
    _r = CA.post(KQ, json=_tana, headers={"X-Amal-Kaliti": kalit()})
    if _r.status_code != 400:
        _rad.append((_nom, _r.status_code, _r.text[:120]))
check(f"S3 {len(_YOMON)} xil noto'g'ri tana — har biri 400 (hech narsa yozilmaydi)", not _rad, _rad)
check("S6 komplekt qaytarish marshruti — xomashyo navbatida (`_XOMASHYO_MARSHRUTLARI`; oddiy qaytarish kabi)",
      ("main", "api_create_komplekt_return") in getattr(main, "_XOMASHYO_MARSHRUTLARI", set()))
check("S3b ro'yxat (obyekt emas) — 422 (FastAPI sxemasi, oddiy qaytarish kabi)",
      CA.post(KQ, json=[], headers={"X-Amal-Kaliti": kalit()}).status_code == 422)
check("S4 tana: sabab / hisob berilmasa — «Ortiqcha» / «keyin»; izoh bo'shliq — None",
      lambda: crud.kqt_tana({"order_id": 3, "kmp_guruh": 2, "soni": 1, "notes": "  "}) ==
      {"order_id": 3, "guruh": 2, "soni": 1, "reason": "Ortiqcha", "notes": None, "hisob": "keyin", "usul": None})
check("S5 «Brak» rad sababi — «Brak yozish» oynasiga yo'naltiradi",
      lambda: "Brak yozish" in det(CA.post(KQ, json={"order_id": 1, "kmp_guruh": 1, "soni": 1, "reason": "Brak"},
                                           headers={"X-Amal-Kaliti": kalit()})))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: sayt komplekti (rom × 3, kapitel / baza bilan) + alohida detal → tasdiq → ERP buyurtmasi
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
DKAL = js(CA.post(API + "/api-kalit", json={})).get("kalit")
BOL = {b["nom"]: b["id"] for b in js(CA.get(API)).get("bolimlar", [])}
M1 = js(CA.post(API + "/modellar", json={"bolim_id": BOL.get("Rom va eshik dekorlari"), "kod": "R-18", "nom": "Klassik",
                                         "kapitel_baza_bor": True})).get("id")
NARX = {"karniz": 15000, "podokonnik": 14000, "nalichnik": 12000, "kapitel": 30000, "baza": 31000}
D = {t: js(CA.post(API + "/detallar", json={"model_id": M1, "turi": t, "olcham": "O'rta", "narx": n, "eni_sm": 15,
                                            "qalinligi_sm": 10})).get("id") for t, n in NARX.items()}
_rs = DOK.post("/api/dokon/v1/buyurtmalar", content=json.dumps({
    "mijoz": "Vali", "telefon": "+998912223344", "viloyat": "andijon",
    "qatorlar": [{"komplekt": "rom", "model_id": M1, "olcham": "O'rta", "qoplamali": False, "kapitel_baza": True, "soni": 3},
                 {"detal_id": D["karniz"], "qoplamali": False, "miqdor": 4}]}).encode(),
    headers={"Content-Type": "application/json", "X-Dokon-Kalit": DKAL or "pdk_x", "X-Amal-Kaliti": "t240-sayt-000001"})
_sb = xavfsiz(lambda d: d.query(models.DokonBuyurtma.id).filter(models.DokonBuyurtma.company_id == 1).scalar())
_rt = CA.post(f"/api/sayt-buyurtmalari/{_sb}/tasdiqla", json={"deadline": "2026-11-20"})
OID = js(_rt).get("order_id") or (js(_rt).get("order") or {}).get("id")
if not OID:
    check("T0 sayt komplekti tasdiqlandi (qolgan bo'limlar uchun)", False, (_rs.status_code, _rs.text[:200], _rt.status_code, _rt.text[:200]))
    print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
    sys.exit(1)
O = buyurtma(OID)
PRJ = O["project_id"]
IT = O["items"]
ROMN = "R-18 «Klassik» — rom komplekti, O'rta, qoplamasiz"
check("T1 sayt komplekti → ERP: 5 rom qatori (guruh 1, 3 komplekt) + 1 guruhsiz; jami 744 000",
      [(x["kmp_guruh"], x["kmp_soni"]) for x in IT] == [(1, 3)] * 5 + [(None, None)] and float(O.get("total_amount") or 0) == 744000
      and IT[0]["kmp_nomi"] == ROMN, [(x["name"], x["kmp_guruh"], x["kmp_nomi"]) for x in IT])
_tp = tayyor_topshir(OID)
check("T2 «Tayyor» va hammasi topshirildi (yuk xati 200)", _tp == 200, _tp)


def qo_lda(items, topshir=True, tayyor=True):
    r = CA.post("/api/orders", json={"project_id": PRJ, "order_type": "product", "items": items, "recipe_id": RID})
    oid = js(r).get("id")
    if oid and tayyor:
        tayyor_topshir(oid, topshir)
    return oid, r


def kq(nom, cat, miqdor, narx, g, soni=3, turi="komplekt_rom", knom="X-2 rom komplekti", uz=None):
    x = {"name": nom, "category": cat, "unit_price": narx, "is_coated": False, "kmp_guruh": g, "kmp_turi": turi, "kmp_nomi": knom,
         "kmp_soni": soni}
    if cat == "profil":
        # profil: `unit_price` — bitta bo'lak (uzunlik) narxi; `narx` — 1 metrniki
        _uz = miqdor if uz is None else uz
        x.update({"width": 15, "thickness": 10, "length": _uz, "quantity": 1 if uz is None else miqdor / uz, "unit_price": narx * _uz})
    else:
        x["quantity"] = miqdor
    if turi == "oz_olcham":
        x["kmp_soni"] = None
    return x


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Reja — detallarga taqsimlash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
def reja(oid, g, n):
    def f(d):
        o = d.query(Order).filter(Order.id == oid).first()
        r = crud.kmp_qaytarish_reja(d, o, g, n)
        return [(i.name, round(m, 3)) for i, m in r["qatorlar"]]
    return db_ishi(f)


def reja_xato(oid, g, n):
    try:
        reja(oid, g, n)
        return None
    except ValueError as e:
        return str(e)
    except Exception as e:                  # noqa: BLE001
        return f"{type(e).__name__}: {e}"


_nom = [x["name"] for x in IT[:5]]
check("A1 sayt rom × 3: 1 komplekt — karniz 2 m, podokonnik 2 m, nalichnik 4 m, kapitel 2, baza 2; 3 komplekt — hammasi",
      lambda: reja(OID, 1, 1) == list(zip(_nom, [2.0, 2.0, 4.0, 2.0, 2.0])) and reja(OID, 1, 3) == list(zip(_nom, [6.0, 6.0, 12.0, 6.0, 6.0])),
      lambda: reja(OID, 1, 1))
check("A2 0 / 4 komplekt (3 dan) — ValueError «buyurtmada 3 komplekt»", lambda: "3 komplekt" in (reja_xato(OID, 1, 4) or "")
      and reja_xato(OID, 1, 0) is not None, lambda: (reja_xato(OID, 1, 4), reja_xato(OID, 1, 0)))
check("A3 guruhsiz / yo'q guruh — ValueError «topilmadi»", lambda: "topilmadi" in (reja_xato(OID, 2, 1) or ""), lambda: reja_xato(OID, 2, 1))
# bir mahsulot ikki qatorga bo'lingan (ombordan partiyalar): karniz 10 + 2,6 m; kapitel 2 + 1 dona (K = 3)
OSP, _r = qo_lda([kq("Karniz S", "profil", 10, 10000, 5), kq("Karniz S", "profil", 2.6, 10000, 5), kq("Kapitel S", "dona", 2, 20000, 5),
                  kq("kapitel  s", "dona", 1, 20000, 5)])
check("A4 bo'lingan qatorlar: 1 komplekt — karniz 3,333 + 0,867 = 4,2 m (jami AYNAN), kapitel 1 + 0 (butun dona)",
      lambda: reja(OSP, 5, 1) == [("Karniz S", 3.333), ("Karniz S", 0.867), ("Kapitel S", 1.0)], lambda: (_r.status_code, reja(OSP, 5, 1)))
check("A5 2 komplekt — karniz 6,667 + 1,733 = 8,4; kapitel 1 + 1 (jami 2); 3 komplekt — hammasi AYNAN",
      lambda: reja(OSP, 5, 2) == [("Karniz S", 6.667), ("Karniz S", 1.733), ("Kapitel S", 1.0), ("kapitel  s", 1.0)]
      and reja(OSP, 5, 3) == [("Karniz S", 10.0), ("Karniz S", 2.6), ("Kapitel S", 2.0), ("kapitel  s", 1.0)], lambda: reja(OSP, 5, 2))
OKS, _r = qo_lda([kq("Karniz K", "profil", 6, 10000, 1), kq("Kapitel K", "dona", 4, 20000, 1)])
check("A6 tahrirlangan komplekt (4 dona / 3 komplekt) — 1 komplektga butun dona chiqmaydi — ValueError «detal bo'yicha»; 3 — mumkin",
      lambda: "detal bo'yicha" in (reja_xato(OKS, 1, 1) or "") and reja_xato(OKS, 1, 3) is None, lambda: reja_xato(OKS, 1, 1))
OOZ, _r = qo_lda([kq("Karniz O", "profil", 4, 10000, 1, turi="oz_olcham", knom="R-12, o'z o'lchami"),
                  kq("Kapitel O", "dona", 2, 20000, 1, turi="oz_olcham", knom="R-12, o'z o'lchami")])
check("A7 «o'z o'lchami» guruhi — komplekt emas: ValueError ««O'z o'lchami» guruhi komplekt emas — detal bo'yicha»",
      lambda: "«O'z o'lchami» guruhi komplekt emas — detal bo'yicha" in (reja_xato(OOZ, 1, 1) or ""),
      lambda: (_r.status_code, _r.text[:200], reja_xato(OOZ, 1, 1)))

OHX, _r = qo_lda([kq("Karniz H", "profil", 6, 10000, 1), kq("Kapitel H", "dona", 3, 20000, 1)])
xavfsiz(lambda d: setattr(d.query(models.OrderItem).filter(models.OrderItem.order_id == OHX, models.OrderItem.name == "Kapitel H").first(),
                          "kmp_soni", 4))
check("A8 bir guruhda belgi har xil (bazada buzilgan) — reja ValueError «har xil», qaytarish 400, tanlovda ko'pi bilan 0",
      lambda: "har xil" in (reja_xato(OHX, 1, 1) or "") and qaytar_k(OHX, 1, 1).status_code == 400 and not qaytishlar(OHX)
      and js(CA.get(f"/api/tanlov/buyurtmalar/{OHX}/detallar")).get("komplektlar") == [{"kmp_guruh": 1, "qaytar_max": 0}],
      lambda: reja_xato(OHX, 1, 1))

OBT, _r = qo_lda([kq("Karniz L1", "profil", 1, 10000, 1), kq("Karniz L2", "profil", 2, 10000, 1), kq("Karniz L5", "profil", 5, 10000, 1),
                  kq("Karniz L10", "profil", 10, 10000, 1), kq("Kapitel L", "dona", 3, 20000, 1)])
def _l1():
    return round(sum(q[2] for q in qaytishlar(OBT) if q[1] == buyurtma(OBT)["items"][0]["id"]), 6)


_bt, _l1x = [], []
for _ in range(3):
    _bt.append(qaytar_k(OBT, 1, 1).status_code)
    _l1x.append(_l1())
_btq = xavfsiz(lambda d: sorted((x.item_name, yaxlit(x.quantity)) for x in d.query(ReturnItem).filter(ReturnItem.order_id == OBT)), [])
_btj = {}
for _n, _m in _btq:
    _btj[_n] = round(_btj.get(_n, 0) + _m, 6)
check("A9 (review240 H1) 1 + 1 + 1 komplekt bittalab (1 / 2 / 5 / 10 m, 3 dona; K = 3): uchalasi 200, jami AYNAN 1 / 2 / 5 / 10 m, 3 dona "
      "(oxirgisi qolganini oladi — 0,334 m), 4-chisi — 400; ombor AYNAN",
      _bt == [200, 200, 200] and _btj == {"Karniz L1": 1.0, "Karniz L2": 2.0, "Karniz L5": 5.0, "Karniz L10": 10.0, "Kapitel L": 3.0}
      and qaytar_k(OBT, 1, 1).status_code == 400 and dict(tm_holat()).get("Karniz L1") == 1.0 and dict(tm_holat()).get("Karniz L10") == 10.0,
      (_bt, _btj))
check("A9b ulush JAMLANIB yaxlitlanadi: 1 m dan 1 / 2 / 3 komplektgacha jami 0,333 / 0,667 / 1 (har safar alohida yaxlitlansa 0,666 bo'lardi); "
      "to'rtinchisida sabab «3 tasi avval qaytarilgan»",
      _l1x == [0.333, 0.667, 1.0] and "3 tasi avval qaytarilgan" in det(qaytar_k(OBT, 1, 1)), lambda: (_l1x, det(qaytar_k(OBT, 1, 1))))
OKZ, _r = qo_lda([kq("Karniz Z", "profil", 1.0005, 10000, 1, soni=1)])
r = qaytar_k(OKZ, 1, 1)
check("A10 (review240 L3) 4 xonali miqdor (1,0005 m, 1 komplekt) — oxirgi komplekt AYNAN 1,0005 (1,001 emas — buyurtmadan ko'p emas)",
      _r.status_code == 200 and r.status_code == 200 and xavfsiz(lambda d: [float(x.quantity) for x in
                                                                          d.query(ReturnItem).filter(ReturnItem.order_id == OKZ)]) == [1.0005],
      (_r.status_code, _r.text[:200], r.status_code, det(r)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Yaratish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_tm0 = dict(tm_holat())
_pul0 = pul_holat(OID)
r = qaytar_k(OID, 1, 1, notes="mijoz qaytardi")
J = js(r)
Q = qaytishlar(OID)
check("B1 1 komplekt — 200; 5 qaytarish yozuvi: ulushlar 2 / 2 / 4 / 2 / 2, bitta kalit (32), soni 1, nomi — komplekt nomi",
      r.status_code == 200 and [(q[2], q[4], q[5]) for q in Q] == [(m, 1, ROMN) for m in (2.0, 2.0, 4.0, 2.0, 2.0)]
      and len({q[3] for q in Q}) == 1 and len(yid(Q, 0, 3) or "") == 32 and [q[1] for q in Q] == [x["id"] for x in IT[:5]],
      (r.status_code, r.text[:300], Q))
check("B2 summalar — har detal o'z kelishilgan narxidan: 30 000 + 28 000 + 48 000 + 60 000 + 62 000 = 228 000; javob jami AYNAN",
      [q[7] for q in Q] == [30000.0, 28000.0, 48000.0, 60000.0, 62000.0] and J.get("jami") == 228000.0
      and [x["refund_amount"] for x in J.get("qaytarishlar", [])] == [q[7] for q in Q], (J.get("jami"), Q))
_tm1 = dict(tm_holat())
check("B3 ombor: har detal o'z tayyor mahsulotiga +ulush (karniz 2, podokonnik 2, nalichnik 4, kapitel 2, baza 2)",
      sorted((k, round(v - _tm0.get(k, 0), 3)) for k, v in _tm1.items() if round(v - _tm0.get(k, 0), 3))
      == sorted(zip(_nom, [2.0, 2.0, 4.0, 2.0, 2.0])), (_tm0, _tm1))
check("B4 «keyin»: pul o'zgarmadi, hech biri hisob-kitob qilinmagan; javobda xabar «… — 1 komplekt qaytarildi (5 ta detal …)»",
      pul_holat(OID) == _pul0 and not any(q[6] for q in Q) and "1 komplekt qaytarildi (5 ta detal" in (J.get("xabar") or ""),
      (pul_holat(OID), _pul0, J.get("xabar")))
check("B5 izoh har yozuvda; sabab «Ortiqcha»; omborga (ortiqcha qism yo'q — topshirilgan edi)",
      xavfsiz(lambda d: {(x.notes, x.reason.value, yaxlit(x.ortiqcha_miqdor), bool(x.finished_product_id)) for x in
                         d.query(ReturnItem).filter(ReturnItem.order_id == OID)}) == {("mijoz qaytardi", "Ortiqcha", 0.0, True)})
_t = js(CA.get(f"/api/tanlov/buyurtmalar/{OID}/detallar"))
check("B6 tanlov: komplektlar [{guruh 1, ko'pi bilan 2}] (3 dan 1 qaytdi)", _t.get("komplektlar") == [{"kmp_guruh": 1, "qaytar_max": 2}],
      _t.get("komplektlar"))
# topshirilmagan (jarayondagi — «Tayyor» avto yuk xati yozadi) buyurtma: qaytgan hammasi — ortiqcha qism (omborga qo'yilgan)
OTS, _r = qo_lda([kq("Karniz T", "profil", 6, 10000, 1), kq("Kapitel T", "dona", 3, 20000, 1)], tayyor=False)
r = qaytar_k(OTS, 1, 2)
check("B7 topshirilmagan (jarayondagi) buyurtma: 2 komplekt — 4 m + 2 dona, ikkalasi «ortiqcha» (mijozga topshirilmagan qism) — oddiy qaytarish qoidasi",
      r.status_code == 200 and xavfsiz(lambda d: [(yaxlit(x.quantity), yaxlit(x.ortiqcha_miqdor)) for x in
                                                  d.query(ReturnItem).filter(ReturnItem.order_id == OTS).order_by(ReturnItem.id)])
      == [(4.0, 4.0), (2.0, 2.0)], lambda: (r.status_code, xavfsiz(lambda d: [(yaxlit(x.quantity), x.ortiqcha_miqdor) for x in
                                                                             d.query(ReturnItem).filter(ReturnItem.order_id == OTS)]),
                                            buyurtma(OTS).get("status")))
r = qaytar_k(OSP, 5, 1)
check("B8 bo'lingan qatorlar (A4) — 1 komplekt: 3 yozuv 3,333 / 0,867 / 1 (jami 4,2 m + 1 dona)",
      r.status_code == 200 and [q[2] for q in qaytishlar(OSP)] == [3.333, 0.867, 1.0], (r.status_code, r.text[:200], qaytishlar(OSP)))
_b9 = [qaytar_k(OSP, 5, 1).status_code for _ in range(2)]
_b9d = {}
for _x in qaytishlar(OSP):
    _b9d[_x[1]] = round(_b9d.get(_x[1], 0) + _x[2], 6)
_b9j = sorted(_b9d.items())
check("B9 (review240 H1) bo'lingan qatorlar — yana 1 + 1 komplekt: ikkalasi 200; jami har qatorda AYNAN buyurtmadagicha (10 / 2,6 m, 2 / 1 dona)",
      _b9 == [200, 200] and [x[1] for x in _b9j] == [10.0, 2.6, 2.0, 1.0], (_b9, _b9j))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Bitta tranzaksiya")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
OC, _r = qo_lda([kq("Karniz C", "profil", 6, 10000, 1), kq("Nalichnik C", "profil", 12, 10000, 1), kq("Kapitel C", "dona", 6, 20000, 1)])
_oc = buyurtma(OC)["items"]
r = CA.post("/api/returns", json={"order_id": OC, "order_item_id": _oc[1]["id"], "item_name": _oc[1]["name"], "quantity": 5,
                                  "unit": "metr", "reason": "Ortiqcha", "to_stock": True})
check("C0 nalichnikdan 5 m alohida qaytdi (12 dan) — tanlovda ko'pi bilan 1 komplekt (2 komplektga 8 m kerak, 7 qolgan)",
      r.status_code == 200 and js(CA.get(f"/api/tanlov/buyurtmalar/{OC}/detallar")).get("komplektlar") == [{"kmp_guruh": 1, "qaytar_max": 1}],
      (r.status_code, js(CA.get(f"/api/tanlov/buyurtmalar/{OC}/detallar")).get("komplektlar")))
_q0, _tm0 = qaytishlar(OC), tm_holat()
r = qaytar_k(OC, 1, 2)
check("C1 2 komplekt — 400 «ko'pi bilan 1 komplekt»; hech narsa yozilmadi (karniz / kapitel ham)",
      r.status_code == 400 and "ko'pi bilan 1 komplekt" in det(r) and "avval alohida qaytarilgan" in det(r) and qaytishlar(OC) == _q0
      and tm_holat() == _tm0, (r.status_code, det(r)))
_asl_cri = crud.create_return_item
_chaq = [0]


def _yiqil(*a, **k):
    _chaq[0] += 1
    if _chaq[0] == 3:
        raise ValueError("SINOV: 3-detal rad etildi")
    return _asl_cri(*a, **k)


crud.create_return_item = _yiqil
try:
    r = qaytar_k(OC, 1, 1)
finally:
    crud.create_return_item = _asl_cri
check("C2 3-detal rad etilsa (ichki to'siq) — 400, oldingi 2 detal ham YOZILMADI, ombor o'zgarmadi",
      r.status_code == 400 and "3-detal" in det(r) and qaytishlar(OC) == _q0 and tm_holat() == _tm0, (r.status_code, det(r), qaytishlar(OC)))
_chaq[0] = 0
crud.create_return_item = _yiqil
try:
    r = CA.post(KQ, json={"order_id": OC, "kmp_guruh": 1, "soni": 1})          # `X-Amal-Kaliti` SIZ (kalit o'z tranzaksiyasini ochmaydi)
finally:
    crud.create_return_item = _asl_cri
check("C2b kalitsiz so'rov ham: 3-detal rad etilsa — hech narsa yozilmadi (marshrutning o'z tranzaksiyasi)",
      r.status_code == 400 and qaytishlar(OC) == _q0 and tm_holat() == _tm0, (r.status_code, det(r), qaytishlar(OC)))
_chaq[0] = 0


def _qulat(*a, **k):
    _chaq[0] += 1
    if _chaq[0] == 2:
        raise RuntimeError("SINOV: kutilmagan xato")
    return _asl_cri(*a, **k)


crud.create_return_item = _qulat
try:
    r = qaytar_k(OC, 1, 1)
finally:
    crud.create_return_item = _asl_cri
check("C3 kutilmagan xato (500) — hech narsa yozilmadi", r.status_code == 500 and qaytishlar(OC) == _q0 and tm_holat() == _tm0,
      (r.status_code, qaytishlar(OC)))
r = qaytar_k(OC, 1, 1)
check("C4 keyin 1 komplekt — 200 (3 yozuv), endi ko'pi bilan 0 → yana 1 — 400 «qaytariladigan butun komplekt qolmagan»",
      r.status_code == 200 and len(qaytishlar(OC)) == 4 and "qolmagan" in det(qaytar_k(OC, 1, 1))
      and js(CA.get(f"/api/tanlov/buyurtmalar/{OC}/detallar")).get("komplektlar") == [{"kmp_guruh": 1, "qaytar_max": 0}],
      (r.status_code, r.text[:200]))
r = qaytar_k(OOZ, 1, 1)
check("C5 «o'z o'lchami» guruhi — 400 (detal bo'yicha), yozuv yo'q", r.status_code == 400 and not qaytishlar(OOZ), (r.status_code, det(r)))
r = qaytar_k(999999, 1, 1)
check("C6 yo'q buyurtma — 404", r.status_code == 404, r.status_code)
OC7, _r = qo_lda([kq("Karniz B", "profil", 6, 10000, 1), kq("Kapitel B", "dona", 6, 20000, 1)])
_c7 = buyurtma(OC7)["items"][0]
_rb = CA.post("/api/returns", json={"order_id": OC7, "order_item_id": _c7["id"], "item_name": _c7["name"], "quantity": 1, "unit": "metr",
                                    "reason": "Brak", "brak_sabab": "ishchi", "to_stock": False, "coating_applied": False})
r = qaytar_k(OC7, 1, 3)
check("C7 brak (1 m) — butun qaytarish yig'indisiga KIRMAYDI (oddiy qaytarish qoidasi): tanlovda 3 edi, 3 komplekt — 200",
      _rb.status_code == 200 and r.status_code == 200 and sorted(q[2] for q in qaytishlar(OC7) if q[3]) == [6.0, 6.0],
      (_rb.status_code, _rb.text[:200], r.status_code, det(r)))
OC8, _r = qo_lda([kq("Kapitel M", "dona", 7, 20000, 1), kq("Kapitel M", "dona", 1, 20000, 1), kq("Kapitel M", "dona", 7, 20000, 1)])
_c8 = buyurtma(OC8)["items"][1]
CA.post("/api/returns", json={"order_id": OC8, "order_item_id": _c8["id"], "item_name": _c8["name"], "quantity": 1, "unit": "dona",
                              "reason": "Ortiqcha", "to_stock": True})
_c8m = js(CA.get(f"/api/tanlov/buyurtmalar/{OC8}/detallar")).get("komplektlar")
_c8r = CA.get(f"{KQ}/reja?order_id={OC8}&kmp_guruh=1&soni=1")
_c8s = qaytar_k(OC8, 1, 1)
check("C8 (review240 M1) 7 / 1 / 7 dona (K = 3), 1 donalik qator alohida qaytgan: ko'pi bilan 2; reja 1 komplekt — 200, ishlatilgan qatordan "
      "olmaydi; saqlash ham 200 (ko'rish = saqlash); keyin reja 2 — 400, saqlash 2 — 400",
      _c8m == [{"kmp_guruh": 1, "qaytar_max": 2}] and _c8r.status_code == 200 and _c8s.status_code == 200
      and all(q["order_item_id"] != _c8["id"] for q in js(_c8r).get("qatorlar", [])) and sum(q["quantity"] for q in js(_c8r).get("qatorlar", [])) == 5
      and CA.get(f"{KQ}/reja?order_id={OC8}&kmp_guruh=1&soni=2").status_code == 400 and qaytar_k(OC8, 1, 2).status_code == 400,
      (_c8m, _c8r.status_code, _c8r.text[:300], _c8s.status_code, det(_c8s)))
_rq = CA.post("/api/orders", json={"project_id": PRJ, "order_type": "product", "is_draft": True, "recipe_id": RID,
                                   "items": [kq("Karniz Q", "profil", 6, 10000, 1), kq("Kapitel Q", "dona", 3, 20000, 1)]})
OQR = js(_rq).get("id")
_tmq = tm_holat()
r = qaytar_k(OQR, 1, 3) if OQR else None
check("C9 (review240 M2) qoralama buyurtma — 404, hech narsa yozilmadi (ishlab chiqarilmagan mahsulot omborga qo'shilmaydi)",
      OQR and buyurtma(OQR).get("status") == "draft" and r.status_code == 404 and not qaytishlar(OQR) and tm_holat() == _tmq,
      (_rq.status_code, _rq.text[:150], getattr(r, "status_code", None)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. «Hozir hisob-kitob»")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
OD, _r = qo_lda([kq("Karniz D", "profil", 6, 10000, 1), kq("Kapitel D", "dona", 6, 20000, 1)])
CA.post("/api/payments", json={"order_id": OD, "amount": 180000, "payment_type": "final", "payment_method": "naqd"})
_p0 = pul_holat(OD)
r = qaytar_k(OD, 1, 1, hisob="hozir", payment_method="plastik")
J = js(r)
_p1 = pul_holat(OD)
check("D1 to'liq to'langan (180 000): 1 komplekt «hozir», plastik — kelishilgan 180 000 → 120 000, mijozga 60 000 karta orqali (2 manfiy to'lov)",
      r.status_code == 200 and _p0[0] == 180000.0 and _p1[0] == 120000.0 and _p1[1] == 120000.0
      and sorted(x for x in _p1[2] if x[0] < 0) == [(-40000.0, "plastik"), (-20000.0, "plastik")]
      and all(q[6] for q in qaytishlar(OD)), (r.status_code, r.text[:300], _p0, _p1))
check("D2 javob: jami 60 000, naqd 60 000, kelishilgan kamaydi 60 000, xabar «… 60 000 so'm naqd …»",
      J.get("jami") == 60000.0 and J.get("naqd_qaytarildi") == 60000.0 and J.get("kelishilgan_kamaydi") == 60000.0
      and "naqd" in (J.get("xabar") or "") and "60" in (J.get("xabar") or ""), J)
OD2, _r = qo_lda([kq("Karniz E", "profil", 6, 10000, 1), kq("Kapitel E", "dona", 6, 20000, 1)])
r = qaytar_k(OD2, 1, 1, hisob="hozir")
check("D3 to'lanmagan buyurtma «hozir»: qarzdan chegirildi (kelishilgan 180 000 → 120 000), naqd to'lov YO'Q",
      r.status_code == 200 and pul_holat(OD2)[0] == 120000.0 and pul_holat(OD2)[2] == [] and "qarzdan chegirildi" in (js(r).get("xabar") or ""),
      (r.status_code, r.text[:300], pul_holat(OD2)))
OD3, _r = qo_lda([kq("Karniz F", "profil", 6, 10000, 1), kq("Kapitel F", "dona", 6, 20000, 1)])
r = qaytar_k(OD3, 1, 1, c=CO, hisob="hozir")
check("D4 hisob-kitob ruxsatisiz («Omborchi») «hozir» — 403, hech narsa yozilmadi", r.status_code == 403 and not qaytishlar(OD3),
      (r.status_code, r.text[:200]))
r = qaytar_k(OD3, 1, 1, c=CO)
check("D5 «Omborchi» «keyin» — 200; javobda pul raqamlari YO'Q (jami, summa) — tannarx ruxsati yo'q",
      r.status_code == 200 and "jami" not in js(r) and all("refund_amount" not in x for x in js(r).get("qaytarishlar", []))
      and len(js(r).get("qaytarishlar", [])) == 2, (r.status_code, r.text[:300]))

OD6, _r = qo_lda([kq("Karniz W", "profil", 6, 10000, 1), kq("Kapitel W", "dona", 6, 20000, 1)])
r = qaytar_k(OD6, 1, 1, c=CO2, hisob="hozir")
check("D6 (review240 L2) hisob-kitob ruxsati bor, tannarx YO'Q: «hozir» — 200, hisob-kitob qilindi, javobda va xabarda summa YO'Q",
      r.status_code == 200 and all(q[6] for q in qaytishlar(OD6)) and "jami" not in js(r) and "so'm" not in (js(r).get("xabar") or "x so'm")
      and "Hisob-kitob qilindi" in (js(r).get("xabar") or ""), (r.status_code, r.text[:300]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. O'chirish — faqat butunligicha")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_qd, _pd, _tmd = qaytishlar(OD), pul_holat(OD), tm_holat()
r = CA.delete(f"/api/returns/{yid(_qd, 0, 0)}")
check("E1 to'plamning bitta yozuvi kalitsiz — 409 (ichida «komplekt»: 2), hech narsa o'zgarmadi",
      r.status_code == 409 and (js(r).get("detail") or {}).get("komplekt") == 2 and "butunligicha" in det(r)
      and qaytishlar(OD) == _qd and pul_holat(OD) == _pd and tm_holat() == _tmd, (r.status_code, r.text[:200]))
_e2 = [CA.delete(f"/api/returns/{yid(_qd, 0, 0)}?komplekt={_v}").status_code for _v in ("2", "1.0", "01", "inf", "abc", "")]
check("E2 `komplekt` — faqat «1» (matn): 2 / 1.0 / 01 / inf / abc / bo'sh — 400 (zip 240b, test_loy_query K)", _e2 == [400] * 6
      and qaytishlar(OD) == _qd, _e2)
# birinchi detal (karniz) sotilgan — o'chirish oxirgisidan boshlanadi: kapitel o'chib bo'lgach karnizda rad etiladi → hammasi orqaga
_tmp = xavfsiz(lambda d: d.query(FinishedProduct.id).filter(FinishedProduct.company_id == 1, FinishedProduct.name == "Karniz D").scalar())
xavfsiz(lambda d: setattr(d.get(FinishedProduct, _tmp), "quantity", 0.0))
r = CA.delete(f"/api/returns/{yid(_qd, 0, 0)}?komplekt=1")
xavfsiz(lambda d: setattr(d.get(FinishedProduct, _tmp), "quantity", 2.0))
check("E3 bitta detalni orqaga qaytarib bo'lmasa (karniz sotilgan — qoldiq 0) — 400, HECH BIRI o'chmadi (kapitel ham), pul / ombor o'zgarmadi",
      r.status_code == 400 and qaytishlar(OD) == _qd and pul_holat(OD) == _pd and dict(tm_holat()).get("Kapitel D") == 2.0,
      (r.status_code, det(r), qaytishlar(OD)))
r = CA.delete(f"/api/returns/{yid(_qd, 1, 0)}?komplekt=1")
check("E4 `komplekt=1` (ikkinchi yozuvdan) — 200, 2 yozuv o'chdi; pul tiklandi (kelishilgan 180 000, manfiy to'lovlar yo'q), ombor −2 m −2 dona",
      r.status_code == 200 and js(r).get("komplekt") == 2 and qaytishlar(OD) == [] and pul_holat(OD) == _p0
      and dict(tm_holat()).get("Karniz D", 0) == 0 and dict(tm_holat()).get("Kapitel D", 0) == 0, (r.status_code, r.text[:200], pul_holat(OD)))
_qa = qaytishlar(OC)
r = CA.delete(f"/api/returns/{yid(_qa, 0, 0)}")
check("E5 alohida (to'plamsiz) qaytarish — avvalgidek kalitsiz o'chadi (200)", r.status_code == 200 and len(qaytishlar(OC)) == 3,
      (r.status_code, r.text[:200]))
r = CB.delete(f"/api/returns/{yid(qaytishlar(OC), 0)}?komplekt=1")
check("E6 begona korxona — 404, o'zgarmadi", r.status_code == 404 and len(qaytishlar(OC)) == 3, r.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. Keyin hisob-kitob — komplekt bo'yicha")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_qf = qaytishlar(OD3)
_pf = pul_holat(OD3)
r = CA.post(f"/api/returns/{yid(_qf, 1, 0)}/refund?komplekt=1&payment_method=naqd")
check("F1 `komplekt=1` — to'plamning 2 yozuvi birga hisob-kitob (kelishilgan 180 000 → 120 000), javob komplekt 2, xabar",
      r.status_code == 200 and js(r).get("komplekt") == 2 and all(q[6] for q in qaytishlar(OD3)) and pul_holat(OD3)[0] == _pf[0] - 60000
      and "Kelishilgan summa" in (js(r).get("xabar") or ""), (r.status_code, r.text[:200], pul_holat(OD3)))
r = CA.post(f"/api/returns/{yid(_qf, 0, 0)}/refund?komplekt=1")
check("F2 qayta — 0 ta (ikki marta chegirilmaydi), xabar «avval hisob-kitob qilingan — hech narsa o'zgarmadi» (review240 L1)",
      r.status_code == 200 and js(r).get("komplekt") == 0 and pul_holat(OD3)[0] == _pf[0] - 60000
      and "avval hisob-kitob qilingan" in (js(r).get("xabar") or ""),
      (r.status_code, r.text[:200]))
check("F3 `komplekt=3` / `1.0` — 400; ruxsatsiz («Omborchi») — 403",
      CA.post(f"/api/returns/{yid(_qf, 0, 0)}/refund?komplekt=3").status_code == 400
      and CA.post(f"/api/returns/{yid(_qf, 0, 0)}/refund?komplekt=1.0").status_code == 400
      and CO.post(f"/api/returns/{yid(_qf, 0, 0)}/refund?komplekt=1").status_code == 403)
_oc1 = buyurtma(OC)["items"][1]
_rs1 = CA.post("/api/returns", json={"order_id": OC, "order_item_id": _oc1["id"], "item_name": _oc1["name"], "quantity": 1,
                                     "unit": "metr", "reason": "Ortiqcha", "to_stock": True})
r = CA.post(f"/api/returns/{js(_rs1).get('id')}/refund?komplekt=1") if js(_rs1).get("id") else None
check("F4 to'plamsiz yozuvga `komplekt=1` — faqat o'zi", r is not None and r.status_code == 200 and js(r).get("komplekt") == 1,
      getattr(r, "text", "")[:200])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G. Takror kalit")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
OG, _r = qo_lda([kq("Karniz G", "profil", 6, 10000, 1), kq("Kapitel G", "dona", 6, 20000, 1)])
_kl = kalit()
r1 = qaytar_k(OG, 1, 1, kal=_kl)
r2 = qaytar_k(OG, 1, 1, kal=_kl)
check("G1 o'sha `X-Amal-Kaliti` bilan ikkinchi so'rov — birinchi javob (`takror`, `X-Takror: 1`), to'plam BITTA (2 yozuv)",
      r1.status_code == 200 and r2.status_code == 200 and js(r2).get("takror") is True and r2.headers.get("X-Takror") == "1"
      and js(r2).get("kalit") == js(r1).get("kalit") and len(qaytishlar(OG)) == 2, (r1.text[:150], r2.text[:150], qaytishlar(OG)))
r = CA.post(KQ, json={"order_id": OG, "kmp_guruh": 1, "soni": 1})
check("G2 kalitsiz — ham ishlaydi (kalit ixtiyoriy, oddiy qaytarish kabi)", r.status_code == 200 and len(qaytishlar(OG)) == 4,
      (r.status_code, r.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Tanlov va reja marshrutlari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = CA.get(f"{KQ}/reja?order_id={OID}&kmp_guruh=1&soni=2")
J = js(r)
check("H1 reja (2 komplekt): 5 qator 4 / 4 / 8 / 4 / 4, summalar va jami 456 000; ko'pi bilan 2",
      r.status_code == 200 and [q["quantity"] for q in J.get("qatorlar", [])] == [4.0, 4.0, 8.0, 4.0, 4.0] and J.get("jami") == 456000.0
      and J.get("qaytar_max") == 2 and J.get("sarlavha") == ROMN + " — 3 komplekt", (r.status_code, r.text[:300]))
check("H2 reja 3 komplekt (2 qolgan) — 400 «ko'pi bilan 2» (komplekt nomi matnda BIR marta — zip 240b); «o'z o'lchami» — 400; soni kasr — 422",
      "ko'pi bilan 2" in det(CA.get(f"{KQ}/reja?order_id={OID}&kmp_guruh=1&soni=3"))
      and det(CA.get(f"{KQ}/reja?order_id={OID}&kmp_guruh=1&soni=3")).count("«" + ROMN + "»") == 1
      and CA.get(f"{KQ}/reja?order_id={OOZ}&kmp_guruh=1&soni=1").status_code == 400
      and CA.get(f"{KQ}/reja?order_id={OID}&kmp_guruh=1&soni=1.5").status_code == 422)
r = CO.get(f"{KQ}/reja?order_id={OID}&kmp_guruh=1&soni=1")
check("H3 tannarx ruxsatisiz — reja narxsiz (summa / jami yo'q)", r.status_code == 200 and "jami" not in js(r)
      and all("summa" not in q for q in js(r).get("qatorlar", [])), (r.status_code, r.text[:200]))
check("H4 begona korxona — reja / tanlov 404", CB.get(f"{KQ}/reja?order_id={OID}&kmp_guruh=1&soni=1").status_code == 404
      and CB.get(f"/api/tanlov/buyurtmalar/{OID}/detallar").status_code == 404)
_t = js(CA.get(f"/api/tanlov/buyurtmalar/{OOZ}/detallar"))
check("H5 tanlov: «o'z o'lchami» guruhi komplektlar ro'yxatida YO'Q", _t.get("komplektlar") == [] and len(_t.get("items", [])) == 2, _t)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("I. Korxona va ruxsat")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_q = qaytishlar(OID)
r = qaytar_k(OID, 1, 1, c=CB)
check("I1 begona korxona komplekt qaytarishi — 404, hech narsa yozilmadi", r.status_code == 404 and qaytishlar(OID) == _q, r.status_code)
r = CB.post(f"/api/returns/{yid(_q, 0, 0)}/refund?komplekt=1")
check("I2 begona korxona hisob-kitobi — 404", r.status_code == 404 and qaytishlar(OID) == _q, r.status_code)
_h = CA.get("/returns").text
check("I3 ro'yxat: komplekt qatorlarida «🧩 <nomi> — 1 komplekt qaytdi» va `data-kqt` (5 ta bir xil)",
      _h.count("— 1 komplekt qaytdi") >= 5 and _h.count(f'data-kqt="{yid(_q, 0, 3)}"') == 5 and ROMN.replace("'", "&#39;") in _h,
      _h.count("komplekt qaytdi"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Parallel (PG)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if not PG_URL:
    print("  (K — faqat PG)")
else:
    OK2, _r = qo_lda([kq("Karniz P", "profil", 6, 10000, 1), kq("Kapitel P", "dona", 6, 20000, 1)])
    _cl = [mijoz("t240_admin"), mijoz("t240_admin")]
    _nat = [None, None]
    _bar = threading.Barrier(2)

    def _ish(n):
        _bar.wait()
        _nat[n] = qaytar_k(OK2, 1, 2, c=_cl[n])
    _th = [threading.Thread(target=_ish, args=(n,)) for n in range(2)]
    [t.start() for t in _th]
    [t.join() for t in _th]
    _kod = sorted(x.status_code for x in _nat)
    check("K1 ikki parallel «2 komplekt» (3 dan): biri 200, ikkinchisi 400 «ko'pi bilan 1» — jami 4 m + 4 dona (6 dan oshmadi)",
          _kod == [200, 400] and sorted(q[2] for q in qaytishlar(OK2)) == [4.0, 4.0]
          and any("ko'pi bilan 1 komplekt" in det(x) for x in _nat if x.status_code == 400), (_kod, [det(x) for x in _nat], qaytishlar(OK2)))

    # K2: marshrut navbatisiz (crud to'g'ridan-to'g'ri, ikki sessiya) — crud o'z qulfi bilan himoyalanadimi
    OK3, _r = qo_lda([kq("Karniz P3", "profil", 6, 10000, 1), kq("Kapitel P3", "dona", 6, 20000, 1)])
    _nat2 = [None, None]
    _bar2 = threading.Barrier(2)

    def _ish2(n):
        s2 = SessionLocal()
        try:
            _bar2.wait()
            with crud.bitta_tranzaksiya(s2):
                crud.create_komplekt_return(s2, OK3, 1, 2, company_id=1, performed_by="K2")
            _nat2[n] = "OK"
        except ValueError as e:
            _nat2[n] = str(e)
        except Exception as e:              # noqa: BLE001
            _nat2[n] = f"{type(e).__name__}: {e}"
        finally:
            s2.close()
    _th = [threading.Thread(target=_ish2, args=(n,)) for n in range(2)]
    [t.start() for t in _th]
    [t.join() for t in _th]
    check("K2 crud to'g'ridan-to'g'ri ikki parallel «2 komplekt»: biri OK, ikkinchisi «ko'pi bilan 1 komplekt» (qulf — qoldiq qulfdan KEYIN "
          "o'qiladi); jami 4 m + 4 dona",
          sorted(x == "OK" for x in _nat2) == [False, True] and any("ko'pi bilan 1 komplekt" in str(x) for x in _nat2)
          and sorted(q[2] for q in qaytishlar(OK3)) == [4.0, 4.0], (_nat2, qaytishlar(OK3)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_k0 = xavfsiz(lambda d: sorted((x.id, x.kqt_kalit, x.kqt_soni, x.kqt_nomi) for x in d.query(ReturnItem)
                                .filter(ReturnItem.company_id == 1, ReturnItem.kqt_kalit.isnot(None)).all()))
_zx = db_ishi(lambda d: crud.export_full_backup(d, 1))
try:
    db_ishi(lambda d: crud.import_full_backup(d, _zx, 1, replace=True))
    _tx = None
except Exception as e:                      # noqa: BLE001
    _tx = f"{type(e).__name__}: {e}"
_k1 = xavfsiz(lambda d: sorted((x.id, x.kqt_kalit, x.kqt_soni, x.kqt_nomi) for x in d.query(ReturnItem)
                                .filter(ReturnItem.company_id == 1, ReturnItem.kqt_kalit.isnot(None)).all()))
check("Z1 zaxira → tiklash: komplekt qaytarishi belgilari AYNAN", _tx is None and _k1 == _k0 and len(_k0 or []) >= 10,
      lambda: (_tx, len(_k0 or []), (_k0 or [])[:2], (_k1 or [])[:2]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL or TEZ:
    print("  (U — PG / T240_TEZ da o'tkaziladi)")
else:
    import time as _tm
    import socket
    import uvicorn
    from playwright.sync_api import sync_playwright
    OU, _r = qo_lda([kq("Karniz U", "profil", 6, 10000, 1, knom="U-1 <b>rom</b> & «komplekt»"),
                     kq("Kapitel U", "dona", 6, 20000, 1, knom="U-1 <b>rom</b> & «komplekt»"),
                     {"name": "Oddiy U", "category": "dona", "quantity": 2, "unit_price": 5000, "is_coated": False}])
    _s = socket.socket()
    _s.bind(("127.0.0.1", 0))
    PORT = _s.getsockname()[1]
    _s.close()
    _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error"))
    threading.Thread(target=_srv.run, daemon=True).start()
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=0.2).close()
            break
        except OSError:
            _tm.sleep(0.1)
    BASE = f"http://127.0.0.1:{PORT}"
    EKRAN = os.environ.get("T240_EKRAN")          # ixtiyoriy: skrinshotlar papkasi (ko'zda tekshirish uchun)
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1366, "height": 900})
            pg = ctx.new_page()
            JSX = []
            pg.on("pageerror", lambda e: JSX.append(str(e)))
            pg.on("dialog", lambda d: d.dismiss())
            pg.goto(BASE + "/login")
            pg.fill("input[name=username]", "t240_admin")
            pg.fill("input[name=password]", PAROL)
            pg.click("button[type=submit]")
            pg.wait_for_load_state("networkidle")

            def oyna(oid):
                pg.goto(BASE + "/returns")
                pg.wait_for_load_state("networkidle")
                pg.evaluate("showAddModal()")
                pg.evaluate(f"(() => {{ const s = document.getElementById('f-order'); s.innerHTML = '<option value=\"{oid}\">x</option>'; "
                            f"s.value = '{oid}'; onOrderChange(); }})()")
                pg.wait_for_function("document.querySelector('#f-item optgroup') !== null", timeout=20000)
            oyna(OU)
            _og = pg.evaluate("Array.from(document.querySelectorAll('#f-item optgroup')).map(g => [g.label, Array.from(g.children).map(o => o.value.indexOf('k:') === 0 ? o.textContent : 'detal')])")
            check("U1 detal tanlovida komplekt guruhi: birinchi — «🧩 Butun komplekt (ko'pi bilan 3 ta)», keyin 2 detal; guruhsiz — tashqarida",
                  _og == [["🧩 U-1 <b>rom</b> & «komplekt» — 3 komplekt", ["🧩 Butun komplekt (ko'pi bilan 3 ta)", "detal", "detal"]]], _og)
            pg.select_option("#f-item", "k:1")
            pg.wait_for_function("document.getElementById('f-kmp-reja').textContent.indexOf('Karniz U') >= 0", timeout=20000)
            _rj = pg.evaluate("[document.getElementById('f-unit-label').textContent, document.getElementById('f-qty').value, "
                              "document.getElementById('f-qty').step, document.getElementById('f-kmp-reja').innerText, "
                              "document.getElementById('f-value').value, document.getElementById('f-value').readOnly, "
                              "getComputedStyle(document.getElementById('f-rasm').closest('.form-group')).display]")
            check("U2 «Butun komplekt»: birlik «komplekt», miqdor 1 (qadam 1), reja «Karniz U — 2 m · 20 000 so'm», «Kapitel U — 2 …», "
                  "qiymat 60 000 (o'zgartirib bo'lmaydi), rasm maydoni yashirin",
                  _rj[0] == "komplekt" and _rj[1] == "1" and _rj[2] == "1" and "Karniz U — 2 m" in _rj[3] and "Kapitel U — 2" in _rj[3]
                  and "20 000" in _rj[3].replace(" ", " ") and _rj[4].replace(" ", " ").replace(" ", "") == "60000" and _rj[5] is True
                  and _rj[6] == "none", _rj)
            pg.fill("#f-qty", "2")
            pg.wait_for_function("document.getElementById('f-kmp-reja').textContent.indexOf('4 m') >= 0", timeout=20000)
            pg.fill("#f-qty", "4")
            pg.wait_for_function("document.getElementById('f-kmp-reja').textContent.indexOf('❌') >= 0", timeout=20000)
            _x4 = pg.evaluate("document.getElementById('f-kmp-reja').textContent")
            check("U3 4 komplekt (3 dan) — reja o'rnida server sababi «… 3 komplekt …»", "3 komplekt" in _x4, _x4)
            pg.check("input[name=f-pul][value=keyin]")
            pg.click("#return-save-btn")
            pg.wait_for_timeout(300)
            _e4 = pg.evaluate("document.getElementById('add-error').textContent")
            check("U3b saqlashda ham (sahifa): «❌ Ko'pi bilan 3 komplekt qaytarish mumkin», hech narsa yozilmadi",
                  "Ko'pi bilan 3 komplekt" in _e4 and not qaytishlar(OU), _e4)
            pg.fill("#f-qty", "2")
            pg.wait_for_function("document.getElementById('f-kmp-reja').textContent.indexOf('4 m') >= 0", timeout=20000)
            pg.check("input[name=f-pul][value=keyin]")
            if EKRAN:
                pg.screenshot(path=os.path.join(EKRAN, "u4_oyna.png"), full_page=True)
            pg.evaluate("window.xabarOyna = async (m) => { sessionStorage.setItem('u240x', m); }")
            pg.click("#return-save-btn")
            pg.wait_for_load_state("networkidle")
            pg.wait_for_timeout(500)
            _x = pg.evaluate("sessionStorage.getItem('u240x')")
            _qu = qaytishlar(OU)
            check("U4 saqlash — bitta so'rov: 2 yozuv (4 m, 4 dona) bitta to'plam, xabar «… 2 komplekt qaytarildi (2 ta detal …)»",
                  [q[2] for q in _qu] == [4.0, 4.0] and len({q[3] for q in _qu}) == 1 and "2 komplekt qaytarildi (2 ta detal" in (_x or ""),
                  (_qu, _x))
            pg.wait_for_selector(".ret-kqt", state="attached", timeout=20000)
            _bd = pg.locator(".ret-kqt").all_text_contents()
            check("U5 ro'yxat: to'plam qatorlarida «🧩 U-1 <b>rom</b> & «komplekt» — 2 komplekt qaytdi» (MATN, teg yo'q)",
                  _bd.count("🧩 U-1 <b>rom</b> & «komplekt» — 2 komplekt qaytdi") == 2 and pg.locator(".ret-kqt b").count() == 0,
                  _bd)
            oyna(OU)
            _og = pg.evaluate("Array.from(document.querySelectorAll('#f-item optgroup option')).map(o => [o.value, o.textContent, o.disabled])[0]")
            check("U6 qayta ochilganda: «🧩 Butun komplekt (ko'pi bilan 1 ta)»", _og == ["k:1", "🧩 Butun komplekt (ko'pi bilan 1 ta)", False], _og)
            pg.evaluate("closeModal()")
            pg.evaluate("window.hisobSora = async (m) => { sessionStorage.setItem('u240h', m); return 'karta'; }; "
                        "window.xabarOyna = async (m) => { sessionStorage.setItem('u240x2', m); }")
            pg.evaluate(f"toggleRefund({yid(_qu, 1, 0)}, false)")
            pg.wait_for_load_state("networkidle")
            pg.wait_for_timeout(800)
            _hm = pg.evaluate("sessionStorage.getItem('u240h')")
            check("U6b ro'yxatdagi «💰 Hisob-kitob qilish» (to'plam qatori): tasdiqda «komplekt qaytarishi (2 ta detal), 120 000 so'm», ikkala "
                  "yozuv hisob-kitob qilindi",
                  "komplekt qaytarishi (2 ta detal)" in (_hm or "") and "120" in (_hm or "") and all(q[6] for q in qaytishlar(OU))
                  and len(qaytishlar(OU)) == 2, (_hm, qaytishlar(OU)))
            pg.evaluate("window.customConfirm = async (m) => { sessionStorage.setItem('u240c', m); return true; }")
            pg.evaluate(f"deleteReturn({yid(_qu, 0, 0)})")
            pg.wait_for_load_state("networkidle")
            pg.wait_for_timeout(800)
            _c = pg.evaluate("sessionStorage.getItem('u240c')")
            check("U7 o'chirish: tasdiqda «komplekt qaytarishi (2 ta detal). Hammasi birga o'chiriladi» — ikkala yozuv o'chdi",
                  "komplekt qaytarishi (2 ta detal)" in (_c or "") and qaytishlar(OU) == [], (_c, qaytishlar(OU)))
            pg.set_viewport_size({"width": 375, "height": 800})
            oyna(OU)
            pg.select_option("#f-item", "k:1")
            pg.wait_for_function("document.getElementById('f-kmp-reja').textContent.indexOf('Karniz U') >= 0", timeout=20000)
            _w = pg.evaluate("[document.documentElement.scrollWidth, document.getElementById('f-kmp-reja').getBoundingClientRect().right]")
            if EKRAN:
                pg.screenshot(path=os.path.join(EKRAN, "u8_375.png"), full_page=True)
            check("U8 375 px: oyna va reja sig'adi (gorizontal surilmaydi)", _w[0] <= 375 and _w[1] <= 375, _w)
            pg.select_option("#f-item", index=2)
            _bx = pg.evaluate("[document.getElementById('f-kmp-reja').style.display, document.getElementById('f-qty').step, "
                              "document.getElementById('f-unit-label').textContent, document.getElementById('f-qty').value]")
            check("U9 oddiy detalga qaytilganda — reja yashirin, qadam 0.1, birlik detalniki, komplektlar soni miqdorda QOLMADI (review240 L4)",
                  _bx[0] == "none" and _bx[1] == "0.1" and _bx[2] != "komplekt" and _bx[3] == "", _bx)
            check("U10 sahifada JS xatosi yo'q", not JSX, JSX)
            br.close()
    except Exception as e:                  # noqa: BLE001
        check("U0 brauzer sinovi oxirigacha yurdi", False, f"{type(e).__name__}: {e}")
    finally:
        _srv.should_exit = True

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:\n  " + "\n  ".join(FAILED))
sys.exit(1 if FAIL else 0)
