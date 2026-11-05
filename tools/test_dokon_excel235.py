#!/usr/bin/env python3
"""
test_dokon_excel235.py — kech170 (zip 235 «Excel»; egasi QARORI «Onlayn do'kon rejasi» 30.10 «Narxlar qayerda turadi»).

NIMA UCHUN KERAK
  Admin sayt katalogi narx jadvalini Excel faylga yuklab oladi, narxlarni tahrirlab qaytaradi. Qaytarishda HAMMA qator tekshiriladi va
  saqlashdan OLDIN nima o'zgarishi ko'rsatiladi; ulgurji narx — faqat Admin; chegirma — `dokon_chegirmalar` (foiz) dan. Xato hisob — saytda
  noto'g'ri narx: narx boshqa detalga yozilishi (qatorlar aralashgan), «125.500» ning 125,5 so'm bo'lib qolishi, bo'sh katak narxni jimgina
  o'chirishi, yarim saqlangan fayl, boshqa oynadagi o'zgarishni bosib ketish, ulgurji narxning jurnalga / begonaga chiqishi.
BO'LIMLAR
  S — statik: requirements (openpyxl qotirilgan), marshrutlar FAQAT Admin, sahifa kartochkasi.
  A — kirish: belgi o'chiq — 404, Menejer — 403, B korxona — 404.
  E — eksport: sarlavha, tartib (bo'lim → model → qator), qiymatlar mustaqil hisob bilan AYNAN (avto qoplamali, chegirmali, muddati tugagan),
      saytda / yashirin, tiyin, «=» bilan boshlangan nom formula emas, boshqaruv belgisi — 500 emas, keshlanmaydi.
  K — ko'rish: narx matni shakllari, noaniq «125.500», bo'sh — o'chiriladi, formula (natijasi bor / yo'q), sana / mantiqiy, raqamsiz /
      takror / yo'q raqam, qatorlar aralashgan (kimlik farqi), kimlik variantlari, ma'lumot ustunlari o'qilmaydi, ustunlar tartibi, varaq
      nomi, siyrak qatorlar, chegaralar; bazaga HECH NARSA yozilmaydi; ogohlantirishlar (2 barobar, chegirma bilan tannarxdan past).
  X — fayl xavfsizligi: xlsx emas, bo'sh, 5 MB, zip-bomba, a'zolar soni, DOCTYPE / ENTITY, buzilgan xlsx — 400 (500 emas).
  Z — saqlash: AYNAN yoziladi, jurnal (ulgurji raqami YO'Q), takror — ikki marta yozilmaydi, ziddiyat — 409 va HECH NARSA, bitta yomon
      qator — hech narsa, so'rov tekshiruvlari, chegirmali narx / komplekt qayta hisoblanadi.
  T — korxona ajratish: B korxona A ning qatorlarini ko'rmaydi va o'zgartirmaydi.
  L — HAQIQIY ofis dasturi (LibreOffice) saqlagan fayl: o'zgarishsiz — 0 o'zgarish; tahrir + formula — hisoblangan qiymat.
  P — PG parallel: bir xil saqlash ikki oynadan, saqlash ∥ panel tahriri ∥ modelni o'chirish — 500 / deadlock yo'q, ikki marta yozilmaydi.
  U — HAQIQIY brauzer: yuklab olish, yuklash (xato / to'g'ri), jadval, escape, saqlash, tarmoq uzilishi, 409, 375 px, JS xatosi yo'q.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` (U, L — faqat SQLite / TF1).
Asl kodga (zip 234) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_dokon_excel235.py
"""
import os
import io
import re
import sys
import glob
import json
import time
import shutil
import socket
import zipfile
import tempfile
import threading
import contextlib
import subprocess
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "dokon235_test"
_T = tempfile.mkdtemp(prefix="t235_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't235.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, ActivityLog, ErrorLog, DokonDetal, DokonModel, Inventory   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
import openpyxl                                    # noqa: E402

DokonChegirma = getattr(models, "DokonChegirma", None)

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
    return str(d.get("detail") if isinstance(d, dict) else d)


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


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Vaqt: «bugun» — Toshkent 2026-11-03 12:00 (UTC 07:00)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
class _SoxtaVaqt:
    t = datetime(2026, 11, 3, 7, 0)

    @classmethod
    def utcnow(cls):
        return cls.t


_asl_dt = getattr(crud, "_dt233", None)
if _asl_dt is not None:
    crud._dt233 = _SoxtaVaqt

s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="T235 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t235_admin", PAROL, UserRole.ADMIN, "T235 Admin", company_id=1)
    auth.create_user(s, "t235_plat", PAROL, UserRole.ADMIN, "T235 Platforma", company_id=1)
    auth.create_user(s, "t235_men", PAROL, UserRole.MANAGER, "T235 Menejer", company_id=1)
    auth.create_user(s, "t235_b", PAROL, UserRole.ADMIN, "T235 B Admin", company_id=2)
s.query(User).filter(User.username == "t235_plat").first().is_platform_admin = True
for _p in s.query(Inventory).filter(Inventory.company_id == 1, Inventory.is_penoplast == True).all():   # noqa: E712
    _p.is_default_penoplast = False
s.add(Inventory(company_id=1, item_name="Penoplast T235", unit="blok", is_penoplast=True, is_default_penoplast=True,
                volume_per_unit=0.96, price_per_unit=410000, stock_quantity=5))
s.commit()
s.close()
main._send_telegram = lambda msg, *a, **k: True


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t235_admin")
CP = mijoz("t235_plat")
CM = mijoz("t235_men")
CB = mijoz("t235_b")
API = "/api/sayt-katalogi"
EX = API + "/excel"


def excel_ol(c=None):
    return (c or CA).get(EX)


def wb_of(bayt):
    try:
        return openpyxl.load_workbook(io.BytesIO(bayt))
    except Exception:                      # noqa: BLE001
        return None


def fayl(wb):
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def korish(bayt, c=None, nom="narxlar.xlsx"):
    return (c or CA).post(EX + "/korish", files={"fayl": (nom, bayt, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})


def saqla(oz, c=None):
    return (c or CA).post(EX + "/saqla", json={"ozgarishlar": oz})


def oz_of(d):
    return [{"id": x["id"], "kimlik": x.get("kimlik"), "eski": x["eski"], "yangi": x["yangi"]} for x in (d.get("ozgarishlar") or [])]


TURI_NOMI = {"asosiy": "Asosiy", "karniz": "Rom karnizi", "podokonnik": "Podokonnik", "nalichnik": "Nalichnik", "kapitel": "Kapitel",
             "baza": "Baza"}


def kim(did):
    """Narx qatorining ko'rishdagi nomi «R-18 · Rom karnizi · O'rta» (bazadan, mustaqil); yo'q / noto'g'ri raqam — «x»."""
    if isinstance(did, bool) or not isinstance(did, int):
        return "x"

    def f(d):
        x = d.query(DokonDetal).filter(DokonDetal.id == did).first()
        if x is None:
            return "x"
        m = d.query(DokonModel).filter(DokonModel.id == x.model_id).first()
        return f"{m.kod if m else '?'} · {TURI_NOMI.get(x.turi, x.turi)} · {x.olcham}"
    return xavfsiz(f, "x")


def narxlar(cid=1):
    """{detal_id: (narx, narx_qoplamali, ulgurji_narx, ulgurji_qoplamali)} — Decimal (2 xona) / None."""
    def q(x):
        return None if x is None else Decimal(str(x)).quantize(Decimal("0.01"))
    return db_ishi(lambda d: {r.id: (q(r.narx), q(r.narx_qoplamali), q(r.ulgurji_narx), q(r.ulgurji_qoplamali))
                              for r in d.query(DokonDetal).filter(DokonDetal.company_id == cid).all()})


def jurnal_soni(entity="dokon_detal"):
    return db_ishi(lambda d: d.query(ActivityLog).filter(ActivityLog.entity_type == entity).count())


def jurnal_oxirgi(n, entity="dokon_detal"):
    return db_ishi(lambda d: [(a.entity_id, a.old_value or "", a.new_value or "", a.performed_by)
                              for a in d.query(ActivityLog).filter(ActivityLog.entity_type == entity)
                              .order_by(ActivityLog.id.desc()).limit(n).all()][::-1])


def ustun(ws, sarlavha):
    for c in ws[1]:
        if c.value == sarlavha:
            return c.column
    return None


def qator_of(ws, did):
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value == did:
            return r
    return None


def ix(lst, i, std=None):
    try:
        return lst[i]
    except Exception:                      # noqa: BLE001
        return std


D = Decimal
SARLAVHA = ["Raqam", "Bo'lim", "Model kodi", "Model nomi", "Detal", "O'lcham", "Birlik", "Narx (qoplamasiz), so'm",
            "Narx (qoplamali), so'm", "Qoplamali — avto (bo'sh bo'lsa)", "Ulgurji (qoplamasiz), so'm", "Ulgurji (qoplamali), so'm",
            "Ulgurji qoplamali — avto", "Chegirma", "Chegirmali narx (qoplamasiz)", "Chegirmali narx (qoplamali)", "Saytda",
            "⚙ Asl narx (qoplamasiz) — o'zgartirmang", "⚙ Asl narx (qoplamali) — o'zgartirmang", "⚙ Asl ulgurji (qoplamasiz) — o'zgartirmang",
            "⚙ Asl ulgurji (qoplamali) — o'zgartirmang", "⚙ Raqam (tekshiruv) — o'zgartirmang"]
NX, NQ, AV, UX, UQ, UA, CHG, CHN, CHQ, SAYT = 8, 9, 10, 11, 12, 13, 14, 15, 16, 17
ASX, ASQ, ASU, ASUQ, R2 = 18, 19, 20, 21, 22


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_req = open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read()
check("S1 requirements.txt — openpyxl QOTIRILGAN va sinov o'sha versiyada (production'da ilgari yo'q edi); et-xmlfile ham qotirilgan",
      re.search(r"^openpyxl==" + re.escape(openpyxl.__version__) + r"\s*$", _req, re.M)
      and re.search(r"^et-xmlfile==\d+\.\d+\.\d+\s*$", _req, re.M), re.findall(r"^(?:openpyxl|et-xmlfile).*$", _req, re.M))
_yollar = {(m, r.path): r for r in main.app.routes for m in (getattr(r, "methods", None) or ())}


def _admin_only(m, p):
    r = _yollar.get((m, p))
    return bool(r) and any(getattr(dp.call, "__name__", "") == "admin_only" for dp in r.dependant.dependencies)


check("S2 3 marshrut bor va FAQAT Admin (auth.admin_only): GET /excel, POST /excel/korish, POST /excel/saqla",
      all(_admin_only(m, p) for m, p in (("GET", EX), ("POST", EX + "/korish"), ("POST", EX + "/saqla"))),
      [(m, p, (m, p) in _yollar) for m, p in (("GET", EX), ("POST", EX + "/korish"), ("POST", EX + "/saqla"))])
check("S3 crud: dokon_excel_yarat / dokon_excel_korish / dokon_excel_saqla / dokon_excel_oqi, DokonExcelZiddiyat",
      all(callable(getattr(crud, n, None)) for n in ("dokon_excel_yarat", "dokon_excel_korish", "dokon_excel_saqla", "dokon_excel_oqi"))
      and isinstance(getattr(crud, "DokonExcelZiddiyat", None), type))
_html = open(os.path.join(ROOT, "templates", "sayt_katalogi.html"), encoding="utf-8").read()
check("S4 sahifa: «📊 Narxlarni Excel orqali o'zgartirish» shtorkasi (data-sht=sk-excel), yuklab olish / yuklash tugmalari, natija bloki",
      all(x in _html for x in ('data-sht="sk-excel"', 'id="skExOl"', 'id="skExFayl"', 'id="skExNatija"', "Narxlarni Excel orqali")))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Kirish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bo = fayl(openpyxl.Workbook())
_st = [CA.get(EX).status_code, korish(_bo).status_code, saqla([{"id": 1, "kimlik": kim(1), "eski": {"narx": 1}, "yangi": {"narx": 2}}]).status_code]
check("A1 sayt katalogi belgisi o'chiq — 3 marshrut 404", _st == [404, 404, 404], _st)
r = CP.post("/api/platform/companies/1/dokon", data={"yoqilgan": "1"})
check("A0 platforma: korxona 1 da sayt katalogi yoqildi", r.status_code == 200, r.text[:200])
_st = [CM.get(EX).status_code, korish(_bo, CM).status_code, saqla([{"id": 1, "kimlik": kim(1), "eski": {"narx": 1}, "yangi": {"narx": 2}}], CM).status_code]
check("A2 Menejer — 3 marshrut 403 (ulgurji narx faqat Admin)", _st == [403, 403, 403], _st)
_st = [CB.get(EX).status_code, korish(_bo, CB).status_code, saqla([{"id": 1, "kimlik": kim(1), "eski": {"narx": 1}, "yangi": {"narx": 2}}], CB).status_code]
check("A3 B korxona admini (belgi o'chiq) — 404", _st == [404, 404, 404], _st)

# ── Sinov katalogi ──
K = js(CA.get(API))
BOL = {b.get("nom"): b.get("id") for b in (K.get("bolimlar") or [])}
KOMP, KAR, TERMO, DEK = BOL.get("Rom va eshik dekorlari"), BOL.get("Karnizlar"), BOL.get("Termopanel"), BOL.get("Dekor elementlar")


def model(bolim, kod, **kw):
    return js(CA.post(API + "/modellar", json=dict({"bolim_id": bolim, "kod": kod}, **kw))).get("id")


def detal(mid, turi, olcham, **kw):
    return js(CA.post(API + "/detallar", json=dict({"model_id": mid, "turi": turi, "olcham": olcham}, **kw))).get("id")


M1 = model(KOMP, "R-18", nom="Klassik", kapitel_baza_bor=True)
ORTA = "O'rta"
DID = {}
for _t, _n, _u in (("karniz", 15000, 13000), ("podokonnik", 14000, 12000), ("nalichnik", 12000, None), ("kapitel", 30000, 28000),
                   ("baza", 30000, 28000)):
    DID[_t] = detal(M1, _t, ORTA, narx=_n, ulgurji_narx=_u, eni_sm=15 if _t == "karniz" else None, qalinligi_sm=10 if _t == "karniz" else None)
M2 = model(KAR, "K-12", nom="Tekis")
DID["k12"] = detal(M2, "asosiy", "12 sm", narx=45000, narx_qoplamali=98000, ulgurji_narx=80000, ulgurji_qoplamali=170000)
DID["k15"] = detal(M2, "asosiy", "15 sm", narx=52000)
MT = model(TERMO, "T-1", nom="Termopanel 60×120")
DID["t1"] = detal(MT, "asosiy", "60×120", narx=150000.5)
M3 = model(DEK, "D-1", nom="Rozetka", yoqilgan=False)
DID["d1"] = detal(M3, "asosiy", "Standart")
M4 = model(DEK, "=HYPERLINK(\"X\",\"Y\")", nom="=1+2")
DID["d4"] = detal(M4, "asosiy", "S", narx=9000, yoqilgan=False)
DID["d5"] = detal(M4, "asosiy", "Q\x01W\x07", narx=9500)            # API boshqaruv belgisini (\x01, \x07) o'tkazadi — eksportda olib tashlanadi
CA.put(API + f"/modellar/{M4}", json={"tartib": 0})                     # bo'lim ichida model tartibi: M4 (keyin yaratilgan) — D-1 dan oldin
CA.put(API + f"/modellar/{M1}/chegirma", json={"foiz": 15})
if DokonChegirma is not None:                      # muddati o'tgan chegirma (API o'tgan sanani qabul qilmaydi) — bazaga to'g'ridan-to'g'ri
    db_ishi(lambda d: d.add(DokonChegirma(company_id=1, model_id=M2, foiz=10, olchamlar=None, tugash=date(2026, 10, 1),
                                          created_by="t", updated_by="t")))
# boshqaruv belgisi (eski / tiklangan yozuvda bo'lishi mumkin) — eksport 500 bermasin
xavfsiz(lambda d: setattr(d.query(DokonModel).filter(DokonModel.id == M4).first(), "tavsif", "a\x01b"))
xavfsiz(lambda d: setattr(d.query(DokonModel).filter(DokonModel.id == M3).first(), "nom", "Rozetka\x02\x1f"))
check("A4 sinov katalogi yaratildi (5 model, 11 narx qatori)", all(DID.values()) and all((M1, M2, MT, M3, M4)) and len(DID) == 11, DID)


def o_avto(n, koeff=D(2)):
    asl = D(str(n)) * koeff
    # kech187 (zip 255, MOSLANDI — QOBILIYAT bo'yicha): avto qoplamali narx endi 1 000 ga yaxlitlanmaydi, butun so'm (egasi QARORI 04.11);
    # eski kodda — 1 000 ga. Test eski va yangi kodda ham o'tadi.
    x = ((asl / D(1000)).quantize(D(1), rounding=ROUND_HALF_UP) * D(1000) if crud.dokon_avto_qoplamali(Decimal("1234"), Decimal("2")) == Decimal("2000")
         else asl.quantize(D(1), rounding=ROUND_HALF_UP))
    return x if x > 0 else asl.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def o_ch(n, f):
    n = D(str(n))
    asl = n * (D(100) - D(str(f))) / D(100)
    # kech188 (zip 255, MOSLANDI — QOBILIYAT bo'yicha): chegirmali narx endi BUTUN so'm (egasi QARORI 04.11 «chegirmada ham yaxlitlash
    # bo'lmasin»); eski kodda 100 / 10 so'mgacha. Test eski va yangi kodda ham o'tadi.
    for q in ((D(100), D(10)) if crud.dokon_chegirma_narx(D("41800"), D("10")) == D("37600") else (D(1),)):
        x = (asl / q).quantize(D(1), rounding=ROUND_HALF_UP) * q
        if 0 < x < n:
            return x
    return max(asl.quantize(D("0.01"), rounding=ROUND_HALF_UP), D("0.01"))


def son(v):
    return None if v is None else D(str(v)).quantize(D("0.01"))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Eksport")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = excel_ol()
check("E1 GET /excel — 200, .xlsx turi, fayl nomi sayt_narxlari_2026-11-03.xlsx (Toshkent kuni), keshlanmaydi (no-store), nosniff",
      r.status_code == 200 and r.headers.get("content-type", "").startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
      and 'filename="sayt_narxlari_2026-11-03.xlsx"' in r.headers.get("content-disposition", "")
      and "no-store" in r.headers.get("cache-control", "") and r.headers.get("x-content-type-options") == "nosniff",
      (r.status_code, dict(r.headers), r.text[:200]))
ASL = r.content if r.status_code == 200 else b""
WB = wb_of(ASL)
WS = WB["Narxlar"] if WB is not None and "Narxlar" in WB.sheetnames else None
check("E2 varaqlar: «Narxlar» va «Yo'riqnoma»; sarlavha AYNAN 22 ustun (17 ko'rinadigan + 5 yashirin «⚙»)", WS is not None and WB.sheetnames == ["Narxlar", "Yo'riqnoma"]
      and [c.value for c in WS[1]] == SARLAVHA, (WB.sheetnames if WB else None, [c.value for c in WS[1]] if WS else None))
_qatorlar = [[c.value for c in row] for row in WS.iter_rows(min_row=2)] if WS is not None else []
_kut_tartib = [DID[k] for k in ("karniz", "podokonnik", "nalichnik", "kapitel", "baza", "k12", "k15", "t1", "d4", "d5", "d1")]
check("E3 qatorlar sahifadagi tartibda — bo'lim (Rom va eshik → Karnizlar → Termopanel → Dekor) → model TARTIBI (keyin yaratilgan, tartibi 0 "
      "— oldin) → narx qatori; har narx qatori bitta",
      [q[0] for q in _qatorlar] == _kut_tartib, [q[0] for q in _qatorlar])
_q = {q[0]: q for q in _qatorlar}
_k = _q.get(DID["karniz"], [None] * 17)
check("E4 karniz qatori: bo'lim, kod, nom, detal nomi, o'lcham, birlik; narx 15 000, qoplamali bo'sh, avto 30 000 (15 000 × 2, 1 000 ga), "
      "ulgurji 13 000, ulgurji avto 26 000",
      _k[1:7] == ["Rom va eshik dekorlari", "R-18", "Klassik", "Rom karnizi", ORTA, "1 m (ulgurji: 1 dona = 2 m)"]
      and son(_k[NX - 1]) == D("15000.00") and _k[NQ - 1] is None and son(_k[AV - 1]) == o_avto(15000)
      and son(_k[UX - 1]) == D("13000.00") and _k[UQ - 1] is None and son(_k[UA - 1]) == o_avto(13000), _k)
check("E5 amaldagi chegirma (R-18, −15 %): «−15 %», chegirmali 15 000 → 12 800, qoplamali avto 30 000 → 25 500 (mustaqil hisob); "
      "ulgurji — chegirmasiz", _k[CHG - 1] == "−15 %" and son(_k[CHN - 1]) == o_ch(15000, 15) and son(_k[CHQ - 1]) == o_ch(o_avto(15000), 15)
      and son(_k[UX - 1]) == D("13000.00"), (_k[CHG - 1:CHQ], o_ch(15000, 15), o_ch(30000, 15)))
_k12 = _q.get(DID["k12"], [None] * 17)
check("E6 K-12: alohida qoplamali 98 000 (avto bo'sh), ulgurji 80 000 / 170 000; chegirmasi muddati o'tgan — «−10 % (muddati tugagan)», "
      "chegirmali narx YO'Q", son(_k12[NQ - 1]) == D("98000.00") and _k12[AV - 1] is None and son(_k12[UX - 1]) == D("80000.00")
      and son(_k12[UQ - 1]) == D("170000.00") and _k12[UA - 1] is None and _k12[CHG - 1] == "−10 % (muddati tugagan)"
      and _k12[CHN - 1] is None and _k12[CHQ - 1] is None, _k12)
_t1 = _q.get(DID["t1"], [None] * 17)
_t1c = WS.cell(_kut_tartib.index(DID["t1"]) + 2, NX) if WS is not None else None
check("E7 tiyinli narx 150 000,50 — son (float), format «#,##0.00»; butun narx — «#,##0»; birlik «1 m²»",
      _t1[NX - 1] == 150000.5 and _t1c is not None and _t1c.number_format == "#,##0.00" and _t1[6] == "1 m²"
      and WS.cell(2, NX).number_format == "#,##0", (_t1, _t1c.number_format if _t1c is not None else None))
_d1, _d4 = _q.get(DID["d1"], [None] * 17), _q.get(DID["d4"], [None] * 17)
check("E8 «Saytda»: ko'rinadigan — «Ha»; yashirin model (D-1) va yashirin narx qatori (=… modeli) — «Yashirin»; narxsiz qator — bo'sh kataklar",
      _k[SAYT - 1] == "Ha" and _d1[SAYT - 1] == "Yashirin" and _d4[SAYT - 1] == "Yashirin" and _d1[NX - 1] is None and _d1[AV - 1] is None,
      (_k[SAYT - 1], _d1, _d4))
_c4 = [WS.cell(_kut_tartib.index(DID["d4"]) + 2, j) for j in (3, 4)] if WS is not None else []
_wf = openpyxl.load_workbook(io.BytesIO(ASL), data_only=False) if ASL else None
_f4 = [_wf["Narxlar"].cell(_kut_tartib.index(DID["d4"]) + 2, j) for j in (3, 4)] if _wf is not None else []
check("E9 «=» bilan boshlangan kod / nom — MATN katak (formula emas: Excel ochganda hisoblamaydi, havola ochmaydi)",
      [c.value for c in _c4] == ['=HYPERLINK("X","Y")', "=1+2"] and [c.data_type for c in _f4] == ["s", "s"],
      ([(c.value, c.data_type) for c in _f4]))
check("E10 nom / o'lchamdagi boshqaruv belgisi (\\x01, \\x02, \\x07, \\x1f) — olib tashlandi, eksport 500 bermadi",
      _d1[3] == "Rozetka" and _q.get(DID["d5"], [None] * 17)[5] == "QW", (_d1[3:4], _q.get(DID["d5"], [None] * 17)[5:6]))
check("E11 narx ustunlari sariq, o'zgarmaydiganlari kulrang; birinchi qator + 3 ustun qotirilgan; filtr; narx ustunlarida Excel tekshiruvi (> 0)",
      WS is not None and WS.cell(2, NX).fill.start_color.rgb.endswith("FFF4D6") and WS.cell(2, 2).fill.start_color.rgb.endswith("EFEFEF")
      and WS.freeze_panes == "D2" and (WS.auto_filter.ref or "").startswith("A1:V")
      and any("H2:" in str(v.sqref) for v in WS.data_validations.dataValidation), WS.freeze_panes if WS is not None else None)
_hid = {L: WS.column_dimensions[L].hidden for L in "QRSTUV"} if WS is not None else {}
_ka = _q.get(DID["k12"], [None] * 22)
check("E11b oxirgi 5 ustun (R:V) YASHIRIN, «Saytda» (Q) ko'rinadi; ularda yuklab olingan paytdagi 4 narx va tekshiruv raqami (K-12: 45 000, "
      "98 000, 80 000, 170 000, raqam)", _hid == {"Q": False, "R": True, "S": True, "T": True, "U": True, "V": True}
      and [son(x) for x in _ka[ASX - 1:ASUQ]] == [D("45000.00"), D("98000.00"), D("80000.00"), D("170000.00")] and _ka[R2 - 1] == DID["k12"],
      (_hid, _ka[17:22]))
_yo = [c.value for c in WB["Yo'riqnoma"]["A"]] if WB is not None and "Yo'riqnoma" in WB.sheetnames else []
check("E12 «Yo'riqnoma»: sariq ustunlar, «125.500» rad, bo'sh katak — o'chiriladi, kimlik ustunlari, qator o'chirilsa — o'chmaydi, ulgurji maxfiy",
      all(any(x in (v or "") for v in _yo) for x in ("SARIQ", "125.500", "bo'shatsangiz", "Raqam, Model kodi, Detal va O'lcham",
                                                     "narx o'chmaydi", "maxfiy", "yashirin «⚙» ustunlar", "BUTUN jadvalni")), _yo[:4])
check("E13 eksport bazaga hech narsa yozmadi (jurnal yo'q)", jurnal_soni("dokon_excel") == 0)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Ko'rish (saqlamasdan)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
N0, J0 = narxlar(), jurnal_soni()


def _oracle_wb():
    """Asl kodda (eksport yo'q) sinov qulamasin: kutilgan jadval (sarlavha + bazadagi qatorlar) — mustaqil quriladi."""
    w = openpyxl.Workbook()
    ws = w.active
    ws.title = "Narxlar"
    ws.append(SARLAVHA)
    turi_nomi = {"asosiy": "Asosiy", "karniz": "Rom karnizi", "podokonnik": "Podokonnik", "nalichnik": "Nalichnik", "kapitel": "Kapitel",
                 "baza": "Baza"}
    def f(v):
        return None if v is None else float(v)

    def qatorlar(d):
        mod = {m.id: m.kod for m in d.query(DokonModel).filter(DokonModel.company_id == 1).all()}
        bor = {x.id: x for x in d.query(DokonDetal).filter(DokonDetal.company_id == 1).all()}
        return [[x.id, None, mod.get(x.model_id), None, turi_nomi.get(x.turi, x.turi), re.sub("[\x00-\x08\x0b\x0c\x0e-\x1f]", "", x.olcham),
                 None, f(x.narx), f(x.narx_qoplamali), None, f(x.ulgurji_narx), f(x.ulgurji_qoplamali), None, None, None, None, None,
                 f(x.narx), f(x.narx_qoplamali), f(x.ulgurji_narx), f(x.ulgurji_qoplamali), x.id]
                for x in (bor.get(i) for i in _kut_tartib) if x is not None]
    for q in db_ishi(qatorlar):
        ws.append(q)
    return w


def yangi_wb():
    return wb_of(ASL) or _oracle_wb()


def tahrir(*juftlar, wb=None):
    """juftlar: (detal_id, ustun, qiymat) → bayt"""
    w = wb or yangi_wb()
    ws = w["Narxlar"]
    for did, j, v in juftlar:
        q = qator_of(ws, did)
        if q is not None:                  # asl kodda (eksport yo'q) yangi qator jadvalda bo'lmasligi mumkin — sinov qulamasin
            ws.cell(q, j).value = v
    return fayl(w)


def kor(bayt):
    r = korish(bayt)
    return r, js(r)


def maydonlar(d):
    return {(x.get("id"), f.get("maydon")): (f.get("eski"), f.get("yangi")) for x in (d.get("ozgarishlar") or [])
            for f in (x.get("maydonlar") or [])}


r, d = kor(ASL)
check("K1 o'zgarishsiz fayl — 200: 11 qator, 0 o'zgarish, 11 o'zgarmagan, xato yo'q (bazada boshqaruv belgili o'lcham ham mos)",
      r.status_code == 200 and d.get("qatorlar") == 11 and d.get("ozgarishlar") == [] and d.get("ozgarmagan") == 11 and d.get("xatolar") == []
      and d.get("faylda_yoq") == 0, (r.status_code, r.text[:400]))
r, d = kor(tahrir((DID["karniz"], NX, 16000), (DID["podokonnik"], NX, "14 500"), (DID["nalichnik"], NX, "12 500"),
                  (DID["kapitel"], NX, "31000,5"), (DID["baza"], NX, "29000.50"), (DID["k12"], UX, None), (DID["d1"], NX, 7000)))
_m = maydonlar(d)
check("K2 shakllar: son 16 000, «14 500», «12 500» (bo'linmas bo'shliq), «31000,5», «29000.50», bo'sh katak — o'chiriladi (yangi null), "
      "narxsiz qatorga narx", r.status_code == 200 and d.get("xatolar") == []
      and _m.get((DID["karniz"], "narx")) == (15000.0, 16000.0) and _m.get((DID["podokonnik"], "narx")) == (14000.0, 14500.0)
      and _m.get((DID["nalichnik"], "narx")) == (12000.0, 12500.0) and _m.get((DID["kapitel"], "narx")) == (30000.0, 31000.5)
      and _m.get((DID["baza"], "narx")) == (30000.0, 29000.5) and _m.get((DID["k12"], "ulgurji_narx")) == (80000.0, None)
      and _m.get((DID["d1"], "narx")) == (None, 7000.0) and len(d.get("ozgarishlar") or []) == 7 and d.get("ozgarmagan") == 4,
      (r.status_code, d.get("xatolar"), _m))
_x = next((x for x in (d.get("ozgarishlar") or []) if x.get("id") == DID["karniz"]), {})
check("K3 o'zgarish yozuvi: id, Excel qator raqami (2), kod, detal nomi, o'lcham, eski / yangi — faqat o'zgargan maydonlar",
      _x.get("qator") == 2 and _x.get("kod") == "R-18" and _x.get("turi_nomi") == "Rom karnizi" and _x.get("olcham") == ORTA
      and _x.get("eski") == {"narx": 15000.0} and _x.get("yangi") == {"narx": 16000.0}, _x)
check("K4 ko'rish bazaga HECH NARSA yozmadi (narxlar va jurnal o'zgarmadi)", narxlar() == N0 and jurnal_soni() == J0)
for _no, (_v, _bor) in enumerate((("125.500", "aniq emas"), ("125,500", "aniq emas"), ("1.250.000", "aniq emas"), ("12 abc", "son emas"),
                                  ("-5000", "0 dan katta"), (-5000, "0 dan katta"), (0, "0 dan katta"), ("0", "0 dan katta"),
                                  (10 ** 13, "juda katta"), ("99999999999999", "juda katta"), (True, "son yozing"),
                                  (datetime(2026, 1, 5), "sana"), ("1e5", "son emas"), ("12,345,678", "aniq emas"),
                                  ("#DIV/0!", "formulada xato (#DIV/0!)")), start=1):
    r, d = kor(tahrir((DID["k15"], NX, _v)))
    _xt = " | ".join(d.get("xatolar") or [])
    check(f"K5.{_no} «{_v!r}» — xato ({_bor}), qator raqami va detal bilan; o'zgarish saqlanmaydi (ozgarishlar bo'sh yoki xato bor)",
          r.status_code == 200 and _bor in _xt and "8-qator" in _xt and "K-12 · Asosiy · 15 sm" in _xt and d.get("xatolar_soni") == 1
          and d.get("xatoli_qatorlar") == 1, (r.status_code, _xt[:300], r.text[:200]))
r, d = kor(tahrir((DID["k15"], NX, "52000"), (DID["k12"], NX, "  45 000  ")))
check("K6 o'sha qiymat matn ko'rinishida («52000», «  45 000  ») — o'zgarish emas", r.status_code == 200 and d.get("ozgarishlar") == []
      and d.get("xatolar") == [], r.text[:300])
r, d = kor(tahrir((DID["k15"], NX, "=H7*2")))
check("K7 formula, natijasi saqlanmagan (openpyxl yozgan) — xato «formula natijasi bo'sh yoki saqlanmagan» (narx jimgina o'chirilmaydi)",
      "formula natijasi bo'sh yoki saqlanmagan" in " ".join(d.get("xatolar") or []) and not maydonlar(d), r.text[:300])
# qatorlar aralashgan: «Model kodi» ustuni alohida saralangan (R-18 va K-12 joy almashgan)
_w = yangi_wb()
_ws = _w["Narxlar"]
_r1, _r2 = qator_of(_ws, DID["karniz"]), qator_of(_ws, DID["k12"])
_ws.cell(_r1, 3).value, _ws.cell(_r2, 3).value = "K-12", "R-18"
_ws.cell(_r1, NX).value = 99000
r, d = kor(fayl(_w))
_xt = " | ".join(d.get("xatolar") or [])
check("K8 «Model kodi» ustuni boshqa qatorlarga aralashgan — ikkala qator xato («ERP'da «R-18 · Rom karnizi · O'rta», faylda «K-12 …»»), "
      "narx boshqa detalga YOZILMAYDI", d.get("xatolar_soni") == 2 and "ERP'da «R-18 · Rom karnizi · O'rta», faylda «K-12" in _xt
      and "aralashgan" in _xt and not maydonlar(d), _xt[:400])
for _no, (_j, _v, _bor) in enumerate(((6, "Katta", "faylda «R-18 · Rom karnizi · Katta»"), (5, "Podokonnik", "faylda «R-18 · Podokonnik · O'rta»"),
                                      (3, "R-19", "faylda «R-19 · Rom karnizi · O'rta»")), start=2):
    _w = yangi_wb()
    _ws = _w["Narxlar"]
    _r = qator_of(_ws, DID["karniz"])
    _ws.cell(_r, _j).value = _v
    _ws.cell(_r, NX).value = 16000
    r, d = kor(fayl(_w))
    check(f"K8.{_no} faqat bitta kimlik ustuni farq qiladi ({_bor}) — xato, narx yozilmaydi", _bor in " ".join(d.get("xatolar") or [])
          and d.get("xatolar_soni") == 1 and not maydonlar(d), d.get("xatolar"))
_w = yangi_wb()
_ws = _w["Narxlar"]
_r = qator_of(_ws, DID["karniz"])
_ws.cell(_r, 3).value, _ws.cell(_r, 5).value, _ws.cell(_r, 6).value = "r-18", "karniz", "O’rta"
_ws.cell(_r, NX).value = 16000
r, d = kor(fayl(_w))
check("K9 kimlik variantlari mos: kod kichik harf («r-18»), detal kodi («karniz»), o'lcham boshqa tutuq belgisi bilan («O’rta»)",
      d.get("xatolar") == [] and maydonlar(d).get((DID["karniz"], "narx")) == (15000.0, 16000.0), r.text[:300])
_w = yangi_wb()
_ws = _w["Narxlar"]
_r = qator_of(_ws, DID["karniz"])
for _j, _v in ((2, "Boshqa bo'lim"), (4, "Boshqa nom"), (7, "dona"), (AV, 1), (UA, 2), (CHG, "−99 %"), (CHN, 5), (CHQ, 6), (SAYT, "Yo'q")):
    _ws.cell(_r, _j).value = _v
r, d = kor(fayl(_w))
check("K10 ma'lumot ustunlari (bo'lim, nom, birlik, avto, chegirma, chegirmali, saytda) o'zgartirilsa — o'qilmaydi, o'zgarish yo'q",
      d.get("xatolar") == [] and d.get("ozgarishlar") == [], r.text[:300])
_w = yangi_wb()
_ws = _w["Narxlar"]
_ws.delete_rows(qator_of(_ws, DID["k15"]))
_ws.cell(qator_of(_ws, DID["karniz"]), NX).value = 16000
r, d = kor(fayl(_w))
check("K11 qator o'chirilgan — «faylda yo'q» 1 ta (o'zgarmaydi), qolgani o'qildi", d.get("faylda_yoq") == 1 and d.get("xatolar") == []
      and len(d.get("ozgarishlar") or []) == 1 and narxlar()[DID["k15"]] == N0[DID["k15"]], r.text[:300])
_w = yangi_wb()
_ws = _w["Narxlar"]
_ws.append([None, None, "R-99", None, "Asosiy", "S", None, 5000])
_ws.append([None] * 17)
_ws.append(["", "  ", None, None, None, None, None, None])
_ASLQ = [None] * 9 + [15000, None, 13000, None]                      # J:Q (9 ta) bo'sh, R:U — yuklab olingandagi narxlar
_ws.append([DID["karniz"], None, "R-18", None, "Rom karnizi", ORTA, None, 15000] + _ASLQ + [DID["karniz"]])
_ws.append([987654, None, "R-18", None, "Rom karnizi", ORTA, None, 15000] + _ASLQ + [987654])
_ws.append(["abc", None, "R-18", None, "Rom karnizi", ORTA, None, 15000] + _ASLQ + ["abc"])
r, d = kor(fayl(_w))
_xt = " | ".join(d.get("xatolar") or [])
check("K12 raqamsiz qator (yangi detal) — xato «Excel orqali qo'shilmaydi»; bo'sh qatorlar — o'tkazildi; takror raqam — xato (2-qatorda ham); "
      "yo'q raqam — xato; noto'g'ri raqam — xato; jami 4 xato",
      "13-qator (R-99 · Asosiy · S): «Raqam» bo'sh" in _xt and "qo'shilmaydi" in _xt and f"16-qator: «Raqam» {DID['karniz']} faylda ikki marta (2-qatorda ham)" in _xt
      and "17-qator: «Raqam» 987654 li narx qatori ERP'da yo'q" in _xt and "18-qator (R-18 · Rom karnizi · O'rta): «Raqam» noto'g'ri" in _xt
      and d.get("xatolar_soni") == 4, _xt[:700])
# ustunlar tartibi boshqa, qo'shimcha ustun, varaq nomi boshqa, oldida boshqa varaq
_VAR = {"Raqam": "raqam", "Model kodi": "MODEL KODI", "O'lcham": "O’lcham", "Detal": "detal"}
_src = [[c.value for c in row] for row in yangi_wb()["Narxlar"].iter_rows()]
_w = openpyxl.Workbook()
_w.active.title = "Boshqa"
_w.active["A1"] = "izoh"
_ws = _w.create_sheet("narxlar")
_ws.append(["Izohim"] + [_VAR.get(h, h) for h in reversed(_src[0])])
for _row in _src[1:]:
    _row = list(_row) + [None] * (22 - len(_row))
    if _row[0] == DID["karniz"]:
        _row[NX - 1] = 17000
    _ws.append(["x"] + list(reversed(_row)))
    for _c in _ws[_ws.max_row]:
        if isinstance(_c.value, str) and _c.value.startswith("="):
            _c.data_type = "s"                                       # «=HYPERLINK…» kodi — matn (openpyxl formula qilmasin)
r, d = kor(fayl(_w))
check("K13 ustunlar teskari tartibda (yashirinlari bilan), qo'shimcha ustun, sarlavha variantlari, varaq «narxlar» (oldida boshqa varaq) — "
      "o'qildi, faqat tahrirlangan katak", d.get("xatolar") == [] and maydonlar(d) == {(DID["karniz"], "narx"): (15000.0, 17000.0)}
      and d.get("varaq") == "narxlar" and d.get("faylda_yoq") == 0, r.text[:300])
_w = openpyxl.Workbook()
_w.active.title = "Sheet1"
_w.active.append(["Raqam", "Model kodi", "Detal", "O'lcham", "Narx (qoplamasiz), so'm", "Narx (qoplamali), so'm", "Ulgurji (qoplamasiz), so'm",
                  "Ulgurji (qoplamali), so'm"])
_w.active.append([DID["k12"], "K-12", "Asosiy", "12 sm", 45000, 98000, 81000, 170000])
r = korish(fayl(_w))
check("K14 qo'lda tuzilgan / boshqa faylga ko'chirilgan jadval (yashirin «⚙» ustunlarsiz) — 400 «ERP'dan yuklab olingan nusxa emas» "
      "(eski / begona fayl yangi narxni bosib ketmasin)", r.status_code == 400 and "nusxa emas" in det(r), (r.status_code, det(r)))
for _no, (_bosh, _bor) in enumerate(((["Model kodi", "Detal", "O'lcham", "Narx (qoplamasiz), so'm"], "Raqam"),
                                      (["Raqam", "Model kodi", "Detal", "O'lcham", "Bo'lim"], "Narx ustuni topilmadi"),
                                      (["Raqam", "Model kodi", "Model kodi", "Detal", "O'lcham", "Narx (qoplamasiz), so'm"], "ikki marta")), start=1):
    _w = openpyxl.Workbook()
    _w.active.append(_bosh)
    r = korish(fayl(_w))
    check(f"K15.{_no} sarlavha noto'g'ri ({_bor}) — 400 tushunarli sabab bilan", r.status_code == 400 and _bor in det(r), (r.status_code, det(r)))
_w = yangi_wb()
_w["Narxlar"].cell(1, UX).value = "Ulgurji"
_w["Narxlar"].cell(qator_of(_w["Narxlar"], DID["k12"]), UX).value = 99000
r = korish(fayl(_w))
check("K15.4 bitta narx ustunining sarlavhasi o'zgartirilgan («Ulgurji») — 400 «Narx ustuni topilmadi: «Ulgurji (qoplamasiz), so'm»» "
      "(tahrir jimgina tashlab ketilmaydi)", r.status_code == 400 and "«Ulgurji (qoplamasiz), so'm»" in det(r), (r.status_code, det(r)))
r = korish(fayl(openpyxl.Workbook()))
check("K16 bo'sh varaq — 400 «bo'sh»", r.status_code == 400 and "bo'sh" in det(r), (r.status_code, det(r)))
# siyrak qatorlar: orada bo'sh qatorlar — xato xabaridagi qator raqami Excel'dagi bilan bir xil
_w = yangi_wb()
_ws = _w["Narxlar"]
_ws.insert_rows(5, 3)
_rk = qator_of(_ws, DID["k15"])
_ws.cell(_rk, NX).value = "1.500.000"
r, d = kor(fayl(_w))
check("K17 orada 3 bo'sh qator — xatodagi qator raqami Excel'dagi bilan AYNAN (siljimagan)", f"{_rk}-qator (K-12 · Asosiy · 15 sm)" in " ".join(d.get("xatolar") or [])
      and _rk == 11, (_rk, d.get("xatolar")))
# chegaralar
_asl_mq, _asl_mo = getattr(crud, "DOKON_EXCEL_MAX_QATOR", None), getattr(crud, "DOKON_EXCEL_MAX_OZGARISH", None)
if _asl_mq is not None:
    crud.DOKON_EXCEL_MAX_QATOR = 5
r = korish(ASL)
if _asl_mq is not None:
    crud.DOKON_EXCEL_MAX_QATOR = _asl_mq
check("K18 qatorlar soni chegaradan ko'p (sinovda 5) — 400 «juda ko'p qator»", r.status_code == 400 and "juda ko'p qator" in det(r), (r.status_code, det(r)))
if _asl_mo is not None:
    crud.DOKON_EXCEL_MAX_OZGARISH = 2
r, d = kor(tahrir((DID["karniz"], NX, 16000), (DID["podokonnik"], NX, 15000), (DID["nalichnik"], NX, 13000)))
_r2 = saqla([{"id": DID["karniz"], "kimlik": kim(DID["karniz"]), "eski": {"narx": 15000.0}, "yangi": {"narx": 16000}},
             {"id": DID["podokonnik"], "kimlik": kim(DID["podokonnik"]), "eski": {"narx": 14000.0}, "yangi": {"narx": 15000}},
             {"id": DID["nalichnik"], "kimlik": kim(DID["nalichnik"]), "eski": {"narx": 12000.0}, "yangi": {"narx": 13000}}])
if _asl_mo is not None:
    crud.DOKON_EXCEL_MAX_OZGARISH = _asl_mo
check("K19 o'zgarishlar chegaradan ko'p (sinovda 2) — ko'rishda xato «ko'pi bilan», saqlash (3 ta) — 400; hech narsa yozilmadi",
      "ko'pi bilan" in " ".join(d.get("xatolar") or []) and _r2.status_code == 400 and "ko'pi bilan" in det(_r2) and narxlar() == N0,
      (d.get("xatolar"), _r2.status_code, det(_r2)))
# ogohlantirishlar
r, d = kor(tahrir((DID["k12"], NX, 450000), (DID["karniz"], NX, 3500)))
_og = " | ".join(d.get("ogohlantirishlar") or [])
check("K20 ogohlantirish (saqlashni to'smaydi): 45 000 → 450 000 — «2 barobardan ko'p»; R-18 (−15 %) karniz 3 500 → chegirmali 3 000 < "
      "tannarx 3 203 — «tannarxdan past»; xato yo'q", d.get("xatolar") == [] and "2 barobardan" in _og and "450" in _og
      and "tannarxdan" in _og and "3 203" in _og.replace(" ", " ") and len(d.get("ozgarishlar") or []) == 2, _og[:500])
# review235 Y2: faqat A:G ustunlari saralangan (Raqam va kimlik narxlardan ajraldi) — xato, narx boshqa detalga yozilmaydi
_w = yangi_wb()
_ws = _w["Narxlar"]
_n = _ws.max_row
_blok = [[_ws.cell(i, j).value for j in range(1, 8)] for i in range(2, _n + 1)][::-1]
for _i, _row in enumerate(_blok, start=2):
    for _j, _v in enumerate(_row, start=1):
        _ws.cell(_i, _j).value = _v
_ws.cell(2, NX).value = 99999
r, d = kor(fayl(_w))
_xt = " | ".join(d.get("xatolar") or [])
check("K23 faqat A:G ustunlari teskari saralangan — joyi o'zgargan 10 qatorning hammasi xato «qatorning qolgan qismidan ajralib ketgan», "
      "o'zgarish YO'Q (narx boshqa detalga yozilmaydi)", d.get("xatolar_soni") == 10 and _xt.count("ajralib ketgan") == 10 and not maydonlar(d),
      (d.get("xatolar_soni"), _xt[:300], maydonlar(d)))
r, d = kor(tahrir((DID["karniz"], NX, 14000), (DID["podokonnik"], NX, 12000), (DID["nalichnik"], NX, 15000)))
check("K24 «Narx (qoplamasiz)» ustuni alohida saralangan (3 ta narx faqat joy almashgan: 15 000 / 14 000 / 12 000) — xato «joy almashgan»",
      "joy almashgan" in " ".join(d.get("xatolar") or []), d.get("xatolar"))
r, d = kor(tahrir((DID["karniz"], NX, 14000), (DID["podokonnik"], NX, 15000)))
check("K24b ikki qator narxi almashgan (chegaradan kam) — xato emas, 2 o'zgarish", d.get("xatolar") == [] and len(maydonlar(d)) == 2, d.get("xatolar"))
from openpyxl.styles import PatternFill as _PF                     # noqa: E402
_w = yangi_wb()
_ws = _w["Narxlar"]
for _i in range(_ws.max_row + 1, 25001):
    _ws.cell(_i, NX).fill = _PF("solid", start_color="FFF4D6", end_color="FFF4D6")
_ws.cell(qator_of(_ws, DID["karniz"]), NX).value = 16000
r, d = kor(fayl(_w))
check("K25 bo'sh, lekin formatlangan 25 000 gacha qator — «juda ko'p qator» emas: 11 qator, 1 o'zgarish (review235 O3)",
      r.status_code == 200 and d.get("qatorlar") == 11 and len(maydonlar(d)) == 1 and d.get("xatolar") == [], (r.status_code, r.text[:200]))
r, d = kor(tahrir((DID["d1"], NX, 125.5), (DID["d1"], NQ, "3")))
_og = " | ".join(d.get("ogohlantirishlar") or [])
check("K26 eski narxi yo'q qatorga juda kichik narx (125,5 va 3 so'm) — ogohlantirish «juda kichik narx» (saqlashni to'smaydi)",
      d.get("xatolar") == [] and _og.count("juda kichik narx") == 2, _og)
check("K21 jami — K bo'limida bazaga hech narsa yozilmadi", narxlar() == N0 and jurnal_soni() == J0)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("X. Fayl xavfsizligi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def zipla(azolar):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for n, t in azolar:
            z.writestr(n, t)
    return b.getvalue()


_bomba = zipla([("[Content_Types].xml", "<Types/>"), ("xl/workbook.xml", "<workbook/>"), ("xl/worksheets/sheet1.xml", b"\0" * (45 * 1024 * 1024))])
_kop = zipla([("xl/workbook.xml", "<workbook/>")] + [(f"xl/x{i}.xml", "<a/>") for i in range(400)])
_z = zipfile.ZipFile(io.BytesIO(ASL or fayl(yangi_wb())))
_doctype = zipla([(i.filename, (b'<?xml version="1.0"?><!DOCTYPE lol [<!ENTITY a "aaaaaaaa">]>' + _z.read(i).split(b"?>", 1)[-1])
                   if i.filename == "xl/worksheets/sheet1.xml" else _z.read(i)) for i in _z.infolist()])
_buzuq = zipla([(i.filename, b"<buzilgan" if i.filename == "xl/workbook.xml" else _z.read(i)) for i in _z.infolist()])
_docx = zipla([("word/document.xml", "<w/>")])
for _no, (_b, _bor, _nom) in enumerate(((b"", "bo'sh", "bo'sh fayl"), (b"Raqam;Model kodi\n1;R-18\n", "xlsx", "CSV matn"),
                                         (b"\xd0\xcf\x11\xe0" + b"\0" * 600, "xlsx", "eski .xls"),
                                         (b"PK\x03\x04" + b"\0" * (5 * 1024 * 1024), "juda katta", "5 MB dan katta"),
                                         (_bomba, "juda ko'p ma'lumot", "zip-bomba (45 MB ochiladi)"), (_kop, "juda ko'p ma'lumot", "400 a'zoli zip"),
                                         (_doctype, "tuzilmasi", "DOCTYPE / ENTITY"), (_buzuq, "xlsx", "buzilgan workbook.xml"),
                                         (_docx, "xlsx", "Word (.docx)"), (b"PK\x03\x04garbage", "xlsx", "buzilgan zip")), start=1):
    _t0 = time.time()
    r = korish(_b)
    check(f"X{_no} {_nom} — 400 «{_bor}» (500 emas), tez ({time.time() - _t0:.1f} s)", r.status_code == 400 and _bor in det(r)
          and time.time() - _t0 < 20, (r.status_code, det(r)[:200]))
_z = zipfile.ZipFile(io.BytesIO(ASL or fayl(yangi_wb())))
_az = []
for _i in _z.infolist():
    _b = _z.read(_i)
    if _i.filename == "xl/worksheets/sheet1.xml":
        _az.append(("xl/worksheets/sheet1.dat", b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]>' + _b.split(b"?>", 1)[-1]))
        continue
    if _i.filename in ("xl/_rels/workbook.xml.rels", "[Content_Types].xml"):
        _b = _b.replace(b"worksheets/sheet1.xml", b"worksheets/sheet1.dat")
    _az.append((_i.filename, _b))
r = korish(zipla(_az))
check("X12 DOCTYPE / ENTITY .xml bo'lmagan nomdagi varaqda (sheet1.dat) — baribir 400 «tuzilmasi» (review235 P6)",
      r.status_code == 400 and "tuzilmasi" in det(r), (r.status_code, det(r)))
check("X13 requirements.txt — defusedxml qotirilgan (openpyxl XML ni xavfsiz o'qiydi)",
      re.search(r"^defusedxml==\d+\.\d+\.\d+\s*$", _req, re.M))
check("X11 fayl tekshiruvlari — server xatosi (ErrorLog) yo'q", lambda: db_ishi(lambda d: d.query(ErrorLog).count()) == 0,
      lambda: db_ishi(lambda d: [e.message[:200] for e in d.query(ErrorLog).limit(3).all()]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Saqlash")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r, d = kor(tahrir((DID["karniz"], NX, 16000), (DID["k12"], UX, 85000), (DID["k12"], UQ, None), (DID["t1"], NQ, "310 000"),
                  (DID["d1"], NX, 7000)))
OZ1 = oz_of(d)
xavfsiz(lambda s_: s_.query(DokonDetal).filter(DokonDetal.id == DID["karniz"]).update(
    {"updated_by": "eski kishi", "updated_at": datetime(2020, 1, 1)}, synchronize_session=False))
J1 = jurnal_soni()
KOM0 = (js(CA.get(API)).get("komplekt") or {}).get(str(M1))
r = saqla(OZ1)
N1 = narxlar()
check("Z1 saqlash — 200 {saqlandi: 4, avval_saqlangan: 0}; bazada AYNAN: karniz 16 000, K-12 ulgurji 85 000 / qoplamali o'chdi, "
      "T-1 qoplamali 310 000, D-1 narx 7 000; boshqalari o'zgarmadi",
      r.status_code == 200 and js(r) == {"saqlandi": 4, "avval_saqlangan": 0} and N1[DID["karniz"]][0] == D("16000.00")
      and N1[DID["k12"]][2:] == (D("85000.00"), None) and N1[DID["t1"]][1] == D("310000.00") and N1[DID["d1"]][0] == D("7000.00")
      and all(N1[k] == N0[k] for k in N0 if k not in (DID["karniz"], DID["k12"], DID["t1"], DID["d1"])), (r.status_code, r.text[:300]))
_jr = jurnal_oxirgi(4)
_jm = " ".join(o + " " + n for _, o, n, _ in _jr)
check("Z2 jurnal — har qator uchun 1 ta «updated» (4), «Excel'dan yuklandi», kim — admin; ULGURJI raqami YO'Q (85 000 / 80 000 / 170 000), "
      "«ulgurji narx o'zgardi»", jurnal_soni() == J1 + 4 and all("Excel'dan yuklandi" in n for _, _, n, _ in _jr)
      and all(p and "T235 Admin" in p for *_, p in _jr) and not re.search(r"85[  ]?000|80[  ]?000|170[  ]?000", _jm)
      and "ulgurji narx o'zgardi" in _jm and "16 000" in _jm, _jr)
check("Z3 updated_by (admin) va updated_at yangilandi (ilgari «eski kishi», 2020-01-01)",
      xavfsiz(lambda s_: (lambda x: "T235" in (x.updated_by or "") and x.updated_at > datetime(2025, 1, 1))(
          s_.query(DokonDetal).filter(DokonDetal.id == DID["karniz"]).first())),
      lambda: xavfsiz(lambda s_: (lambda x: (x.updated_by, x.updated_at))(s_.query(DokonDetal).filter(DokonDetal.id == DID["karniz"]).first())))
r = saqla(OZ1)
check("Z4 o'sha so'rov qayta (ikki marta bosish / tarmoq qayta yubordi) — 200 {saqlandi: 0, avval_saqlangan: 4}, jurnal qo'shilmadi",
      r.status_code == 200 and js(r) == {"saqlandi": 0, "avval_saqlangan": 4} and jurnal_soni() == J1 + 4 and narxlar() == N1, r.text[:300])
_k1 = js(CA.get(API))
_kd = next((x for x in (_k1.get("detallar") or []) if x.get("id") == DID["karniz"]), {})
check("Z5 katalogda karniz 16 000, chegirmali (−15 %) 13 600 — mustaqil hisob; R-18 komplekt narxlari ham o'zgardi (server hisobi)",
      _kd.get("narx") == 16000.0 and ((_kd.get("chegirma") or {}).get("narx")) == float(o_ch(16000, 15))
      and KOM0 and (_k1.get("komplekt") or {}).get(str(M1)) and (_k1.get("komplekt") or {}).get(str(M1)) != KOM0, (_kd, KOM0))
# ziddiyat: ko'rishdan keyin boshqa oynada o'zgardi
r, d = kor(tahrir((DID["karniz"], NX, 17000), (DID["podokonnik"], NX, 15000), wb=wb_of(excel_ol().content)))
OZ2 = oz_of(d)
CA.put(API + f"/detallar/{DID['podokonnik']}", json={"narx": 14800})
N2, J2 = narxlar(), jurnal_soni()
r = saqla(OZ2)
check("Z6 ko'rishdan keyin podokonnik boshqa oynada 14 800 qilindi — 409 (qaysi detal — matnda), HECH NARSA yozilmadi (karniz ham 16 000 qoldi)",
      r.status_code == 409 and "R-18 · Podokonnik · O'rta" in det(r) and "Hech narsa saqlanmadi" in det(r) and narxlar() == N2
      and jurnal_soni() == J2, (r.status_code, det(r)))
# aralash: bir qator allaqachon yangi, ikkinchisi hali eski
r, d = kor(tahrir((DID["karniz"], NX, 17000), (DID["nalichnik"], NX, 12500), wb=wb_of(excel_ol().content)))
OZ3 = oz_of(d)
CA.put(API + f"/detallar/{DID['karniz']}", json={"narx": 17000})
J3 = jurnal_soni()
r = saqla(OZ3)
check("Z7 bir qator boshqa oynada allaqachon yangi qiymatda (17 000) — o'tkazildi, ikkinchisi yozildi: {saqlandi: 1, avval_saqlangan: 1}",
      r.status_code == 200 and js(r) == {"saqlandi": 1, "avval_saqlangan": 1} and narxlar()[DID["nalichnik"]][0] == D("12500.00")
      and jurnal_soni() == J3 + 1, r.text[:300])
N4, J4 = narxlar(), jurnal_soni()
_yaxshi = {"id": DID["k15"], "kimlik": kim(DID["k15"]), "eski": {"narx": 52000.0}, "yangi": {"narx": 53000.0}}
for _no, (_tana, _bor) in enumerate((
        ({"ozgarishlar": []}, "o'zgarish yo'q"), ({"ozgarishlar": "x"}, "o'zgarish yo'q"), ({}, "o'zgarish yo'q"),
        ({"ozgarishlar": [_yaxshi], "boshqa": 1}, "yuborib bo'lmaydi"),
        ({"ozgarishlar": [_yaxshi, dict(_yaxshi, qoshimcha=1)]}, "yuborib bo'lmaydi"),
        ({"ozgarishlar": [_yaxshi, {"id": DID["k12"], "kimlik": kim(DID["k12"]), "eski": {"narx": 45000.0}, "yangi": {"narx_qoplamali": 1}}]}, "qayta yuklang"),
        ({"ozgarishlar": [_yaxshi, {"id": DID["k12"], "kimlik": kim(DID["k12"]), "eski": {"tartib": 1}, "yangi": {"tartib": 2}}]}, "qayta yuklang"),
        ({"ozgarishlar": [_yaxshi, {"id": DID["k12"], "kimlik": kim(DID["k12"]), "eski": {}, "yangi": {}}]}, "qayta yuklang"),
        ({"ozgarishlar": [_yaxshi, {"id": True, "kimlik": kim(True), "eski": {"narx": 1}, "yangi": {"narx": 2}}]}, "raqami noto'g'ri"),
        ({"ozgarishlar": [_yaxshi, {"id": "5", "kimlik": kim("5"), "eski": {"narx": 1}, "yangi": {"narx": 2}}]}, "raqami noto'g'ri"),
        ({"ozgarishlar": [_yaxshi, {"id": 0, "kimlik": kim(0), "eski": {"narx": 1}, "yangi": {"narx": 2}}]}, "raqami noto'g'ri"),
        ({"ozgarishlar": [_yaxshi, {"id": 2 ** 31, "kimlik": kim(2 ** 31), "eski": {"narx": 1}, "yangi": {"narx": 2}}]}, "raqami noto'g'ri"),
        ({"ozgarishlar": [_yaxshi, _yaxshi]}, "ikki marta"),
        ({"ozgarishlar": [_yaxshi, {"id": DID["k12"], "kimlik": kim(DID["k12"]), "eski": {"narx": 45000.0}, "yangi": {"narx": -1}}]}, "0 dan katta"),
        ({"ozgarishlar": [_yaxshi, {"id": DID["k12"], "kimlik": kim(DID["k12"]), "eski": {"narx": 45000.0}, "yangi": {"narx": "46000"}}]}, "son bo'lishi kerak"),
        ({"ozgarishlar": [_yaxshi, {"id": DID["k12"], "kimlik": kim(DID["k12"]), "eski": {"narx": 45000.0}, "yangi": {"narx": 1e30}}]}, "juda katta"),
        ({"ozgarishlar": [_yaxshi, {"id": DID["k12"], "kimlik": kim(DID["k12"]), "eski": {"narx": "x"}, "yangi": {"narx": 46000}}]}, "qayta yuklang"),
        ({"ozgarishlar": [_yaxshi, {"id": 987654, "kimlik": kim(987654), "eski": {"narx": 1}, "yangi": {"narx": 2}}]}, "topilmadi"),
        ({"ozgarishlar": [{"id": DID["k15"], "kimlik": kim(DID["k15"]), "eski": {"narx": 52000.0}, "yangi": {"narx": 52000.0}}]}, "o'zgarish yo'q"),
        ({"ozgarishlar": [_yaxshi, "x"]}, "Noto'g'ri so'rov"),
), start=1):
    r = CA.post(EX + "/saqla", json=_tana)
    check(f"Z8.{_no} noto'g'ri so'rov ({_bor}) — 400, yaxshi qator ham YOZILMADI", r.status_code == 400 and _bor in det(r)
          and narxlar() == N4 and jurnal_soni() == J4, (r.status_code, det(r)[:200]))
r = CA.post(EX + "/saqla", content=b"not json", headers={"Content-Type": "application/json"})
check("Z9 JSON emas — 4xx (500 emas)", 400 <= r.status_code < 500, r.status_code)
if _asl_mo is not None:
    crud.DOKON_EXCEL_MAX_OZGARISH = 1
r = saqla([_yaxshi, {"id": DID["k12"], "kimlik": kim(DID["k12"]), "eski": {"narx": 45000.0}, "yangi": {"narx": 46000}}])
if _asl_mo is not None:
    crud.DOKON_EXCEL_MAX_OZGARISH = _asl_mo
check("Z10 saqlashda ham o'zgarishlar soni chegarasi (sinovda 1) — 400, hech narsa", r.status_code == 400 and narxlar() == N4, (r.status_code, det(r)))
r = saqla([{"id": DID["karniz"], "kimlik": kim(DID["karniz"]), "eski": {"narx": 17000}, "yangi": {"narx": 18000}}], CM)
check("Z11 Menejer saqlay olmaydi — 403", r.status_code == 403 and narxlar() == N4, r.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Y. Eski fayl, qayta nomlash, qisman chegirma")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
F0 = excel_ol().content                                             # «dushanba» fayli
NY = narxlar()
CA.put(API + f"/detallar/{DID['k15']}", json={"narx": float(NY[DID["k15"]][0]) + 4000})          # «seshanba» panelda
CA.put(API + f"/detallar/{DID['t1']}", json={"narx_qoplamali": 320000})
r, d = kor(tahrir((DID["podokonnik"], NX, float(NY[DID["podokonnik"]][0]) + 100), wb=wb_of(F0)))
check("Y1 eski fayl (yuklab olingandan keyin panelda K-12 15 sm narxi va T-1 qoplamali o'zgargan): faqat egasi o'zgartirgan katak (podokonnik) — "
      "o'zgarish; panelda o'zgargan narxlar QAYTARILMAYDI / O'CHIRILMAYDI (review235 Y1)", d.get("xatolar") == []
      and set(maydonlar(d)) == {(DID["podokonnik"], "narx")}, (d.get("xatolar"), maydonlar(d)))
r, d = kor(tahrir((DID["k15"], NX, float(NY[DID["k15"]][0]) + 1000), wb=wb_of(F0)))
_xt = " | ".join(d.get("xatolar") or [])
check("Y2 eski faylda panelda o'zgargan narxning o'zi tahrirlangan — xato «yuklab olgandan keyin ERP'da o'zgargan» (faylda / ERP'da hozir) "
      "— bosib ketilmaydi", "yuklab olgandan keyin ERP'da o'zgargan" in _xt and "K-12 · Asosiy · 15 sm" in _xt and not maydonlar(d), _xt[:300])
r, d = kor(tahrir((DID["k15"], NX, float(NY[DID["k15"]][0]) + 4000), wb=wb_of(F0)))
check("Y3 eski faylda ERP'dagi hozirgi narxning o'zi yozilgan — o'zgarish ham, xato ham emas", d.get("xatolar") == [] and not maydonlar(d),
      d.get("xatolar"))
CA.put(API + f"/detallar/{DID['k15']}", json={"narx": float(NY[DID["k15"]][0])})
CA.put(API + f"/detallar/{DID['t1']}", json={"narx_qoplamali": None if NY[DID["t1"]][1] is None else float(NY[DID["t1"]][1])})
# review235 O1: ko'rishdan keyin o'lcham qayta nomlandi — saqlanmaydi
r, d = kor(tahrir((DID["k15"], NX, float(NY[DID["k15"]][0]) + 500), wb=wb_of(excel_ol().content)))
_oz = oz_of(d)
CA.put(API + f"/detallar/{DID['k15']}", json={"olcham": "16 sm"})
_n0, _j0 = narxlar(), jurnal_soni()
r = saqla(_oz)
check("Y4 ko'rishdan keyin o'lcham «15 sm» → «16 sm» qayta nomlandi — saqlash 409 («endi «K-12 · Asosiy · 16 sm»»), narx yozilmadi",
      r.status_code == 409 and "endi «K-12 · Asosiy · 16 sm»" in det(r) and narxlar() == _n0 and jurnal_soni() == _j0, (r.status_code, det(r)))
CA.put(API + f"/detallar/{DID['k15']}", json={"olcham": "15 sm"})
_m20 = model(KAR, "K-20")
_d20 = detal(_m20, "asosiy", "20 sm", narx=60000)
_d25 = detal(_m20, "asosiy", "25 sm", narx=70000)
CA.put(API + f"/modellar/{_m20}/chegirma", json={"foiz": 20, "olchamlar": ["20 sm"]})
_w20 = wb_of(excel_ol().content)
_q20 = {row[0].value: [c.value for c in row] for row in _w20["Narxlar"].iter_rows(min_row=2)} if _w20 is not None else {}
check("Y5 chegirma faqat «20 sm» ga (−20 %): 20 sm qatorida «−20 %» va 48 000; 25 sm qatorida chegirma ham, chegirmali narx ham YO'Q "
      "(sayt ham chegirmasiz ko'rsatadi — review235 O4)", (_q20.get(_d20) or [None] * 22)[CHG - 1] == "−20 %"
      and son((_q20.get(_d20) or [None] * 22)[CHN - 1]) == D("48000.00") and (_q20.get(_d25) or [None] * 22)[CHG - 1] is None
      and (_q20.get(_d25) or [None] * 22)[CHN - 1] is None, (_q20.get(_d20), _q20.get(_d25)))
CA.delete(API + f"/modellar/{_m20}")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Korxona ajratish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
xavfsiz(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", True))     # sinov uchun: B da ham belgi (platforma qoidasi — faqat egasida)
_kb = js(CB.get(API))
_bb = next((b.get("id") for b in (_kb.get("bolimlar") or []) if b.get("nom") == "Karnizlar"), None)
if _bb is None:
    _bb = js(CB.post(API + "/bolimlar", json={"nom": "Karnizlar B", "qolip": "juft_metr"})).get("id")
_mb = js(CB.post(API + "/modellar", json={"bolim_id": _bb, "kod": "BK-1"})).get("id")
_db = js(CB.post(API + "/detallar", json={"model_id": _mb, "turi": "asosiy", "olcham": "S", "narx": 1000})).get("id")
_eb = CB.get(EX)
_wbb = wb_of(_eb.content) if _eb.status_code == 200 else None
check("T1 B korxona eksporti — faqat o'z qatori (BK-1), A ning narxlari YO'Q", _wbb is not None
      and [[c.value for c in row][:3] for row in _wbb["Narxlar"].iter_rows(min_row=2)] == [[_db, "Karnizlar" if _kb.get("bolimlar") else "Karnizlar B", "BK-1"]]
      and b"R-18" not in _eb.content, (_eb.status_code, [[c.value for c in row][:3] for row in _wbb["Narxlar"].iter_rows(min_row=2)] if _wbb else None))
NA, JA = narxlar(), jurnal_soni()
r = korish(tahrir((DID["k15"], NX, 1)), CB)
check("T2 B A ning faylini yuklasa — hamma qator «ERP'da yo'q» (A ning narxlari ko'rinmaydi), o'zgarish yo'q", r.status_code == 200
      and js(r).get("ozgarishlar") == [] and js(r).get("xatolar_soni") == 11 and "ERP'da yo'q" in json.dumps(js(r).get("xatolar"), ensure_ascii=False),
      r.text[:300])
r = saqla([{"id": DID["k15"], "kimlik": kim(DID["k15"]), "eski": {"narx": 52000.0}, "yangi": {"narx": 1}}], CB)
check("T3 B A ning qatorini saqlay olmaydi — 400 «topilmadi», A ning narxi o'zgarmadi", r.status_code == 400 and "topilmadi" in det(r)
      and narxlar() == NA and jurnal_soni() == JA, (r.status_code, det(r)))
xavfsiz(lambda d: setattr(d.get(Company, 2), "dokon_yoqilgan", False))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L. LibreOffice (haqiqiy ofis dasturi) saqlagan fayl")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
LO = shutil.which("soffice")


def lo_qayta(bayt, nom="lo"):
    """Faylni LibreOffice da ochib, .xlsx qilib qayta saqlaydi (formulalar hisoblanadi) — bayt yoki None."""
    if not LO:
        return None
    papka = tempfile.mkdtemp(prefix=nom + "_", dir=_T)
    kir = os.path.join(papka, "kirish.xlsx")
    open(kir, "wb").write(bayt)
    chiq = os.path.join(papka, "chiq")
    try:
        subprocess.run([LO, "-env:UserInstallation=file://" + os.path.join(papka, "profil"), "--headless", "--calc", "--convert-to",
                        "xlsx:Calc MS Excel 2007 XML", "--outdir", chiq, kir], capture_output=True, timeout=240)
    except Exception:                      # noqa: BLE001
        return None
    p = os.path.join(chiq, "kirish.xlsx")
    return open(p, "rb").read() if os.path.exists(p) else None


TEZ = os.environ.get("T235_TEZ") == "1"          # mutatsiya: faqat server mutatsiyalarida L / U bo'limlari o'tkaziladi (mut235.py)
if TEZ:
    print("  (T235_TEZ=1 — o'tkazildi)")
elif PG_URL or not LO:
    print("  (LibreOffice sinovlari — faqat SQLite / TF1 da va soffice bo'lsa)" + ("" if LO else " — soffice YO'Q"))
    if not PG_URL:
        check("L0 LibreOffice (soffice) o'rnatilgan", False, "soffice topilmadi")
else:
    _e0 = excel_ol().content
    _lo = lo_qayta(_e0)
    r, d = kor(_lo or b"")
    check("L1 eksport → LibreOffice ochib saqladi (o'zgarishsiz) → yuklash: 0 o'zgarish, 0 xato (ulashilgan matnlar, siyrak qatorlar)",
          _lo is not None and r.status_code == 200 and d.get("ozgarishlar") == [] and d.get("xatolar") == [] and d.get("qatorlar") == 11,
          (r.status_code, r.text[:300]))
    _w = wb_of(_e0) or yangi_wb()
    _ws = _w["Narxlar"]
    _ws.insert_rows(4, 2)                                          # avval qator qo'shiladi (openpyxl formula havolalarini siljitmaydi)
    _rk, _rp = qator_of(_ws, DID["k15"]), qator_of(_ws, DID["podokonnik"])
    _ws.cell(_rk, NX).value = "=52000*1.1"                          # 57 200 — LibreOffice hisoblaydi (o'z katagiga havola — aylana xato)
    _ws.cell(_rp, NX).value = "14 900"
    _lo2 = lo_qayta(fayl(_w), "lo2")
    r, d = kor(_lo2 or b"")
    _m = maydonlar(d)
    check("L2 formula «=52000*1,1» (LibreOffice hisoblagan natija 57 200) va matn «14 900» — o'qildi; orada bo'sh qatorlar bo'lsa ham",
          _lo2 is not None and d.get("xatolar") == [] and _m.get((DID["k15"], "narx")) == (52000.0, 57200.0)
          and _m.get((DID["podokonnik"], "narx")) == (14800.0, 14900.0) and len(_m) == 2, (r.status_code, r.text[:400]))
    _w = wb_of(_e0) or yangi_wb()
    _ws = _w["Narxlar"]
    _ws.cell(qator_of(_ws, DID["k15"]), NX).value = "125.500"
    _ws.insert_rows(6, 4)
    _rk = qator_of(_ws, DID["k15"])
    _lo3 = lo_qayta(fayl(_w), "lo3")
    r, d = kor(_lo3 or b"")
    check("L3 LibreOffice saqlagan faylda xato qatori raqami — Excel'dagi bilan AYNAN (bo'sh qatorlar yozilmagan siyrak XML)",
          _lo3 is not None and f"{_rk}-qator (K-12 · Asosiy · 15 sm)" in " ".join(d.get("xatolar") or []), (_rk, d.get("xatolar")))
    _w = wb_of(_e0) or yangi_wb()
    _ws = _w["Narxlar"]
    _ws.cell(qator_of(_ws, DID["k15"]), NX).value = "=1/0"
    _lo4 = lo_qayta(fayl(_w), "lo4")
    r, d = kor(_lo4 or b"")
    check("L4 formula xato beradi (=1/0 → #DIV/0!) — xato «formulada xato (#DIV/0!)», narx o'zgarmaydi",
          _lo4 is not None and "formulada xato (#DIV/0!)" in " ".join(d.get("xatolar") or []) and not maydonlar(d), d.get("xatolar"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. PG parallel")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    from concurrent.futures import ThreadPoolExecutor

    def parallel(fns):
        with ThreadPoolExecutor(max_workers=len(fns)) as ex:
            return [f.result() for f in [ex.submit(fn) for fn in fns]]

    _c1, _c2 = mijoz("t235_admin"), mijoz("t235_admin")
    r, d = kor(tahrir((DID["kapitel"], NX, 33000), (DID["baza"], NX, 34000), wb=wb_of(excel_ol().content)))
    _oz = oz_of(d)
    _asl_dm = crud._dokon_detal_matni

    def _sekin_dm(x):
        time.sleep(0.25)                   # qulfdan KEYIN (yozish paytida) kechikish — qulfsiz kodda ikkalasi ham «eski» ni ko'rib yozardi
        return _asl_dm(x)
    crud._dokon_detal_matni = _sekin_dm
    _j = jurnal_soni()
    _rs = parallel([lambda: saqla(_oz, _c1), lambda: saqla(_oz, _c2)])
    crud._dokon_detal_matni = _asl_dm
    _jb = sorted([js(x) for x in _rs], key=lambda x: x.get("saqlandi", 0))
    check("P1 bir xil saqlash ikki oynadan bir vaqtda — ikkalasi 200: biri {saqlandi: 2}, ikkinchisi {avval_saqlangan: 2}; jurnal AYNAN 2 ta",
          [x.status_code for x in _rs] == [200, 200] and _jb == [{"saqlandi": 0, "avval_saqlangan": 2}, {"saqlandi": 2, "avval_saqlangan": 0}]
          and jurnal_soni() == _j + 2 and narxlar()[DID["kapitel"]][0] == D("33000.00"), ([x.text[:120] for x in _rs], jurnal_soni() - _j))
    r, d = kor(tahrir((DID["kapitel"], NX, 35000), (DID["karniz"], NX, 18000), wb=wb_of(excel_ol().content)))
    _oz = oz_of(d)
    _asl_mo2 = crud._dokon_model_of
    _asl_q1, _asl_q2 = getattr(crud, "_dokon_excel_modellarni_qulfla", None), getattr(crud, "_dokon_excel_qatorlarni_qulfla", None)

    def _sekin_mo(*a, **k):
        r_ = _asl_mo2(*a, **k)
        if k.get("lock"):
            time.sleep(0.5)
        return r_

    def _sekin(fn):
        def w(*a, **k):
            r_ = fn(*a, **k)
            time.sleep(0.6)                # qulfdan KEYIN kechikish: teskari tartibda (qator → model) panel bilan o'zaro kutish bo'lardi
            return r_
        return w
    crud._dokon_model_of = _sekin_mo
    if _asl_q1 and _asl_q2:
        crud._dokon_excel_modellarni_qulfla, crud._dokon_excel_qatorlarni_qulfla = _sekin(_asl_q1), _sekin(_asl_q2)

    def _panel():
        time.sleep(0.1)
        return _c2.put(API + f"/detallar/{DID['kapitel']}", json={"ulgurji_narx": 29000}).status_code
    _st = parallel([lambda: saqla(_oz, _c1).status_code, _panel])
    crud._dokon_model_of = _asl_mo2
    if _asl_q1 and _asl_q2:
        crud._dokon_excel_modellarni_qulfla, crud._dokon_excel_qatorlarni_qulfla = _asl_q1, _asl_q2
    check("P2 Excel saqlash va panelda o'sha modelning qatorini tahrirlash bir vaqtda — deadlock / 500 yo'q (qulf tartibi model → qator)",
          _st[0] in (200, 409) and _st[1] == 200, _st)
    _m9 = js(CA.post(API + "/modellar", json={"bolim_id": KAR, "kod": "K-P9"})).get("id")
    _d9 = js(CA.post(API + "/detallar", json={"model_id": _m9, "turi": "asosiy", "olcham": "S", "narx": 50000})).get("id")
    r, d = kor(tahrir((_d9, NX, 51000), wb=wb_of(excel_ol().content)))
    _oz = oz_of(d)
    _st = parallel([lambda: saqla(_oz, _c1).status_code, lambda: (time.sleep(0.05), _c2.delete(API + f"/modellar/{_m9}").status_code)[1]])
    check("P3 Excel saqlash va modelni o'chirish bir vaqtda — 500 yo'q: o'chirish 200, saqlash 200 yoki 400 (qator o'chgan)",
          _st[1] == 200 and _st[0] in (200, 400) and xavfsiz(lambda s_: s_.query(DokonModel).filter(DokonModel.id == _m9).count()) == 0, _st)
    check("P4 server xatosi yo'q", lambda: db_ishi(lambda d: d.query(ErrorLog).count()) == 0,
          lambda: db_ishi(lambda d: [e.message[:200] for e in d.query(ErrorLog).limit(3).all()]))
else:
    print("  (faqat PG rejimida)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
br = pw_ctx = server = None
if TEZ:
    print("  (T235_TEZ=1 — o'tkazildi)")
elif PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
    try:
        from playwright.sync_api import sync_playwright
        PW_BOR, _pw_x = True, ""
    except Exception as _e:                # noqa: BLE001
        PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
    import uvicorn                                 # noqa: E402

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
    if PW_BOR and server.started:
        pw_ctx = sync_playwright().start()
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                  "chrome-linux", "chrome"))):
            _exe = _yol
        try:
            br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
        except Exception as _e:            # noqa: BLE001
            br = None
            _pw_x = f"{type(_e).__name__}: {_e}"
    check("U0 lokal server va Chromium", bool(server.started and br), _pw_x)
    JS_XATO, SOROV, KONSOL = [], [], []

    def kontekst(login, kenglik=1440):
        ctx = br.new_context(viewport={"width": kenglik, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ", accept_downloads=True)
        ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
        pg = ctx.new_page()
        pg.set_default_timeout(15000)
        pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
        pg.on("console", lambda m: KONSOL.append(m.text[:200]) if m.type == "error" else None)
        pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""))) if "/api/" in q.url else None)
        pg.goto(B + "/login")
        pg.fill("input[name=username]", login)
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
        return ctx, pg

    def kut(pg, ifoda, ms=10000):
        try:
            pg.wait_for_function(ifoda, timeout=ms)
            return True
        except Exception:                  # noqa: BLE001
            return False

    def matn(pg, sel):
        return pg.evaluate(f"(document.querySelector(\"{sel}\") || {{}}).innerText || ''")

    def yukla(pg, bayt, nom="narxlar.xlsx"):
        p = os.path.join(_T, nom)
        open(p, "wb").write(bayt)
        pg.set_input_files("#skExFayl", p)

    if br:
        try:
            _xm = js(CA.post(API + "/modellar", json={"bolim_id": DEK, "kod": '"><B>XSS</B>'})).get("id")
            _xd = js(CA.post(API + "/detallar", json={"model_id": _xm, "turi": "asosiy", "olcham": "<i>o</i>", "narx": 4000})).get("id")
            ctx, pg = kontekst("t235_admin")
            pg.goto(B + "/sayt-katalogi")
            kut(pg, "document.querySelectorAll('#skBolimlar .sk-bolim').length > 3")
            _y = kut(pg, "!!document.querySelector('details.sht[data-sht=\"sk-excel\"]')")
            check("U1 «📊 Narxlarni Excel orqali o'zgartirish» shtorkasi bor, birinchi marta yopiq", _y
                  and "Narxlarni Excel orqali" in matn(pg, "#skExcel summary") and not pg.evaluate("document.querySelector('#skExcel details').open"))
            pg.click("#skExcel summary")
            with pg.expect_download(timeout=15000) as _dl:
                pg.click("#skExOl")
            _dlf = _dl.value
            _dlb = open(_dlf.path(), "rb").read()
            _dw = wb_of(_dlb)
            check("U2 «⬇ Excel'ga yuklab olish» — fayl yuklab olindi (sayt_narxlari_2026-11-03.xlsx), ichida hamma narx qatori",
                  _dlf.suggested_filename == "sayt_narxlari_2026-11-03.xlsx" and _dw is not None
                  and {c[0].value for c in _dw["Narxlar"].iter_rows(min_row=2)} >= set(DID.values()) | {_xd}, _dlf.suggested_filename)
            NU0, JU0 = narxlar(), jurnal_soni()
            _w = wb_of(_dlb)
            _ws = _w["Narxlar"]
            _ws.cell(qator_of(_ws, DID["k15"]), NX).value = 54000
            _ws.cell(qator_of(_ws, DID["podokonnik"]), NX).value = "125.500"
            _ws.cell(qator_of(_ws, _xd), NX).value = "x<b>y</b>"
            _bas = len(SOROV)
            yukla(pg, fayl(_w), "xatoli.xlsx")
            _y = kut(pg, "!!document.querySelector('#skExNatija .sk-ex-blok.xato')")
            _nt = matn(pg, "#skExNatija")
            check("U3 xatoli fayl yuklandi — qizil «❌ Xatolar: 2 ta — hech narsa saqlanmaydi», qator raqamlari bilan; «Saqlash» tugmasi YO'Q; "
                  "shtorka holati qizil; bazaga yozilmadi", _y and "Xatolar: 2 ta" in _nt and "aniq emas" in _nt and "son emas" in _nt
                  and not pg.evaluate("!!document.getElementById('skExSaqla')") and pg.evaluate("!!document.querySelector('#skExcel .sht-holat.yomon')")
                  and narxlar() == NU0 and ("POST", EX + "/korish") in SOROV[_bas:], _nt[:400])
            check("U4 xato matnidagi HTML (kod «\"><B>XSS</B>», qiymat «x<b>y</b>») — matn bo'lib ko'rindi, <b>/<B> teg yaratilmadi",
                  '"><B>XSS</B>' in _nt and "x<b>y</b>" in _nt
                  and pg.evaluate("![...document.querySelectorAll('#skExNatija b')].some(b => b.textContent === 'XSS' || b.textContent === 'y')"), _nt[:300])
            _ws.cell(qator_of(_ws, DID["podokonnik"]), NX).value = 14900
            _ws.cell(qator_of(_ws, _xd), NX).value = 4500
            _ws.cell(qator_of(_ws, DID["k12"]), UX).value = None
            yukla(pg, fayl(_w), "togri.xlsx")
            _y = kut(pg, "!!document.getElementById('skExSaqla')")
            _nt = matn(pg, "#skExNatija")
            check("U5 to'g'ri fayl — jadvalda 4 o'zgarish (eski → yangi), «o'chiriladi» (ulgurji bo'sh), «✓ Saqlash (4 ta qator)», xato bloki yo'q, "
                  "HTML li kod / o'lcham — matn", _y and pg.evaluate("document.querySelectorAll('#skExNatija tbody tr').length") == 4
                  and "o'chiriladi" in _nt and "Saqlash (4 ta qator)" in _nt and not pg.evaluate("!!document.querySelector('#skExNatija .sk-ex-blok.xato')")
                  and '"><B>XSS</B> · Asosiy · <i>o</i>' in _nt and not pg.evaluate("!!document.querySelector('#skExNatija i')")
                  and narxlar() == NU0, _nt[:500])
            pg.focus("#skExFayl")
            check("U5b klaviatura fokusi «⬆ Excel'dan yuklash» da ko'rinadi (yorliqda ramka — review235 P4)",
                  pg.evaluate("getComputedStyle(document.getElementById('skExYuklaTugma')).outlineStyle") not in ("none", ""),
                  pg.evaluate("getComputedStyle(document.getElementById('skExYuklaTugma')).outlineStyle"))
            # tarmoq uzildi — natija noma'lum, tugma qoladi; qayta bosish — bir marta yoziladi
            pg.route("**/api/sayt-katalogi/excel/saqla", lambda route: route.abort())
            pg.click("#skExSaqla")
            pg.wait_for_timeout(700)
            pg.unroute("**/api/sayt-katalogi/excel/saqla")
            check("U6 tarmoq uzildi — «natija noma'lum … ikki marta yozilmaydi» xabari, «Saqlash» tugmasi joyida va faol; bazaga yozilmadi",
                  pg.evaluate("!!document.getElementById('skExSaqla') && !document.getElementById('skExSaqla').disabled") and narxlar() == NU0
                  and pg.evaluate("[...document.querySelectorAll('div')].some(x => (x.textContent || '').indexOf('ikki marta yozilmaydi') >= 0)"), "")
            _bas = len(SOROV)
            pg.evaluate("""() => { const f = window.fetch; window.__asl_fetch = f;
                window.fetch = (u, o) => /excel\\/saqla/.test(String(u)) ? new Promise(r => setTimeout(r, 1500)).then(() => f(u, o)) : f(u, o); }""")
            pg.click("#skExSaqla")
            pg.wait_for_timeout(300)
            _hol = pg.evaluate("""() => { const b = document.getElementById('skExBekor'); b.click();
                return {bekor: b.disabled, fayl: document.getElementById('skExFayl').disabled,
                        band: document.getElementById('skExYuklaTugma').classList.contains('band'),
                        jadval: document.querySelectorAll('#skExNatija tbody tr').length}; }""")
            check("U7b saqlash davomida (sekin tarmoq) «Bekor qilish» va «Excel'dan yuklash» yopiq, bosilsa ham natija o'chmaydi (review235 O2)",
                  _hol == {"bekor": True, "fayl": True, "band": True, "jadval": 4}, _hol)
            _y = kut(pg, "document.getElementById('skExNatija').innerText.trim() === ''")
            pg.evaluate("() => { window.fetch = window.__asl_fetch; }")
            check("U7c saqlash tugagach — tugmalar yana ochiq", pg.evaluate("!document.getElementById('skExFayl').disabled && "
                  "!document.getElementById('skExYuklaTugma').classList.contains('band')"))
            _nu = narxlar()
            check("U7 «Saqlash» — 4 qator yozildi (K-12 15 sm 54 000, podokonnik 14 900, XSS 4 500, K-12 ulgurji o'chdi), jurnal +4, bitta POST "
                  "/excel/saqla, natija bloki tozalandi, katalog qayta yuklandi",
                  _y and _nu[DID["k15"]][0] == D("54000.00") and _nu[DID["podokonnik"]][0] == D("14900.00") and _nu[_xd][0] == D("4500.00")
                  and _nu[DID["k12"]][2] is None and jurnal_soni() == JU0 + 4
                  and [x for x in SOROV[_bas:] if x[0] == "POST"] == [("POST", EX + "/saqla")] and ("GET", API) in SOROV[_bas:],
                  (SOROV[_bas:], _nu.get(DID["k15"])))
            pg.evaluate("() => { const b = [...document.querySelectorAll('#skBolimlar .sk-bolim')].find(x => x.innerText.includes('Karnizlar')); b && b.click(); }")
            kut(pg, f"!!document.querySelector('[data-och=\"{M2}\"]')")
            pg.evaluate(f"() => {{ const m = document.querySelector('.sk-model[data-model=\"{M2}\"]'); if (m && !m.classList.contains('ochiq')) m.querySelector('[data-och]').click(); }}")
            _y = kut(pg, f"(document.querySelector(\"tr[data-detal='{DID['k15']}'] [data-df=narx]\") || {{}}).value === '54000'")
            check("U8 sahifadagi narx katagida yangi narx (K-12 15 sm — 54000)", _y,
                  pg.evaluate(f"(document.querySelector(\"tr[data-detal='{DID['k15']}'] [data-df=narx]\") || {{}}).value"))
            # 409: ko'rishdan keyin boshqa oynada o'zgardi
            _w = wb_of(excel_ol().content)
            _ws = _w["Narxlar"]
            _ws.cell(qator_of(_ws, DID["k15"]), NX).value = 55000
            yukla(pg, fayl(_w), "ziddiyat.xlsx")
            kut(pg, "!!document.getElementById('skExSaqla')")
            CA.put(API + f"/detallar/{DID['k15']}", json={"narx": 54500})
            pg.click("#skExSaqla")
            _y = kut(pg, "!!document.querySelector('#skExNatija .sk-ex-blok.xato')")
            check("U9 ko'rishdan keyin boshqa oynada o'zgardi — «❌ Saqlanmadi: … boshqa oynada o'zgardi», «Saqlash» tugmasi olib tashlandi, bazada 54 500",
                  _y and "boshqa oynada" in matn(pg, "#skExNatija .sk-ex-blok.xato") and not pg.evaluate("!!document.getElementById('skExSaqla')")
                  and narxlar()[DID["k15"]][0] == D("54500.00"), matn(pg, "#skExNatija")[:300])
            pg.click("#skExBekor")
            check("U10 «Bekor qilish» — natija bloki tozalandi", kut(pg, "document.getElementById('skExNatija').innerText.trim() === ''"))
            # o'zgarishsiz fayl
            yukla(pg, excel_ol().content, "bir_xil.xlsx")
            _y = kut(pg, "!!document.getElementById('skExBekor')")
            check("U11 o'zgarishsiz fayl — «Faylda o'zgargan narx yo'q», «Saqlash» yo'q, «Yopish» tugmasi", _y
                  and "o'zgargan narx yo'q" in matn(pg, "#skExNatija") and not pg.evaluate("!!document.getElementById('skExSaqla')")
                  and matn(pg, "#skExBekor").strip() == "Yopish", matn(pg, "#skExNatija")[:200])
            yukla(pg, b"bu excel emas", "notogri.xlsx")
            _y = kut(pg, "(document.getElementById('skExNatija').innerText || '').indexOf('qabul qilinmadi') >= 0")
            check("U12 Excel bo'lmagan fayl — «❌ Fayl qabul qilinmadi: Bu Excel (.xlsx) fayl emas …»", _y and "xlsx" in matn(pg, "#skExNatija"),
                  matn(pg, "#skExNatija")[:200])
            # telefon
            _w = wb_of(excel_ol().content)
            _ws = _w["Narxlar"]
            _ws.cell(qator_of(_ws, DID["k15"]), NX).value = 56000
            _ws.cell(qator_of(_ws, DID["karniz"]), UX).value = 14000
            yukla(pg, fayl(_w), "telefon.xlsx")
            kut(pg, "!!document.getElementById('skExSaqla')")
            for _kn in (375, 320):
                pg.set_viewport_size({"width": _kn, "height": 800})
                pg.wait_for_timeout(300)
                check(f"U13 telefon ({_kn} px): sahifa gorizontal toshmaydi, o'zgarishlar jadvali kartochka (sarlavha yashirin), tugmalar ekran kengligida",
                      lambda: not pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
                      and pg.evaluate("getComputedStyle(document.querySelector('#skExNatija thead')).display") == "none"
                      and pg.evaluate("[...document.querySelectorAll('#skExNatija td, #skExNatija .btn, #skExcel .sk-ex-yukla')].every(t => t.getBoundingClientRect().right <= window.innerWidth + 1)"),
                      pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]"))
            pg.set_viewport_size({"width": 1440, "height": 900})
            pg.click("#skExBekor")
            ctx.close()
            CA.delete(API + f"/modellar/{_xm}")
            check("U14 JS xatosi yo'q", not JS_XATO, JS_XATO[:3])
            check("U15 konsolda kutilmagan xato yo'q (ataylab: tarmoq uzilishi, 409, 400)",
                  not [k for k in KONSOL if not re.search(r"409|400|ERR_FAILED|Failed to fetch|net::", k)], KONSOL[:4])
        except Exception as e:             # noqa: BLE001
            import traceback
            print("".join(traceback.format_exc().splitlines(True)[-12:])[:3000])
            check("U* brauzer sinovi qulamadi", False, f"{type(e).__name__}: {e}")
    if br:
        br.close()
    if pw_ctx:
        pw_ctx.stop()
    if server:
        server.should_exit = True

check("Y1 butun sinov davomida server xatosi (ErrorLog) yo'q", lambda: db_ishi(lambda d: d.query(ErrorLog).count()) == 0,
      lambda: db_ishi(lambda d: [e.message[:200] for e in d.query(ErrorLog).limit(3).all()]))
if _asl_dt is not None:
    crud._dt233 = _asl_dt
shutil.rmtree(_T, ignore_errors=True)
print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
