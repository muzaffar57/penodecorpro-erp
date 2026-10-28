#!/usr/bin/env python3
"""
test_reja_loy_foyda221.py — kech159 (zip 221 «Tayyor gacha foydada reja loy» — egasi 28.10; tanlovi «Taxminiy belgisi bilan (Tavsiya)» +
«Ha, farq ko'rinsin (Tavsiya)»).

NIMA UCHUN KERAK (O'LCHANGAN — `work/k221/probe221.py`, zip 220 kodi, SQLite)
  Buyurtmaga yozilgan reja loy (300 kg) buyurtma YARATILGANDA ombordan yechiladi (kley −300), lekin «Tayyor» gacha «Foyda tahlili» qoplamani
  umuman hisoblamasdi: tan narxi 255 000 (qoplamasiz), «Tayyor» 320 kg dan keyin 895 000 — egasi «faqat penoplast hisoblanadi» deb ko'rdi.
QOIDA
  Haqiqiy loy yozilmagan, «Tayyor» / bekor / o'chirilgan EMAS buyurtmada (holat so'ralmaganda) — qoplama REJA bo'yicha, yechilgan paytdagi narxda,
  «Qoplama — reja bo'yicha (…, taxminiy)», `taxminiy: True`. «Tayyor» da — haqiqiy (avvalgidek AYNAN), reja dan farq qilsa izoh
  «Loy: reja A kg → haqiqiy B kg (±C kg, ±D so'm)». Hisobotlar / KPI / loyiha foydasi («Tayyor» buyurtmalar) — O'ZGARMAYDI.
BO'LIMLAR
  S — manba. A — server (jarayondagi reja, narx o'zgarsa ham yechilgan narx, «Tayyor» loysiz = taxmin AYNAN, ±farq izohi, reja 0, tahrirda reja
  o'zgarishi, holat / o'chirilgan / bekor — rejasiz, tayyor loy zaxirasidan, hisobotlarda taxminiy YO'Q). U — HAQIQIY Chromium («Foyda tahlili»
  oynasi: taxminiy bloki, kartada «(taxminiy)», «Tayyor» dan keyin farq izohi, JS xatosi yo'q).
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (S + A).
Asl kodga (zip 220) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_reja_loy_foyda221.py
"""
import os
import io
import re
import sys
import time
import json
import socket
import inspect
import datetime
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "rejaloy221_test"
_T = tempfile.mkdtemp(prefix="k221_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k221.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []


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
        print(f"  ✗ {label}   {str(detail)[:1200]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


ORD = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master, Order, OrderStatus, Recipe, RecipeIngredient    # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_src = inspect.getsource(services.calculate_order_profit)
check("S1 `calculate_order_profit`: haqiqiy loy yo'q, «Tayyor» / bekor / o'chirilgan emas, holat so'ralmagan — reja loy (`_get_planned_loy`)",
      "_loy_reja221 = bool(not _haqiqiy_bor221 and _reja_kg221 > 0 and holat_vaqti is None" in _src
      and "OrderStatus.READY.value, OrderStatus.CANCELLED.value" in _src and "_get_planned_loy(order)" in _src)
check("S2 javobda `taxminiy` va `loy_holati`; «Tayyor» da reja → haqiqiy izohi",
      '"taxminiy": bool(_loy_holati221' in _src and '"loy_holati": _loy_holati221' in _src and '_qator221["izoh"]' in _src)
check("S3 «Foyda tahlili» oynasi: izoh qatori, taxminiy bloki, kartada «(taxminiy)»",
      "${b.izoh ? `<div class=\"foyda-izoh\"" in ORD and 'class="foyda-taxminiy"' in ORD and "const _taxm221 = d.taxminiy === true;" in ORD)

_srcc = inspect.getsource(services.complete_order)
check("S4 `complete_order`: READY dan OLDIN «Foyda tahlili» taxminini `reja_qoplama_tannarxi` ga yozadi; ustun — modelda va migratsiyada",
      "order.reja_qoplama_tannarxi = _taxmin221" in _srcc and _srcc.find("order.reja_qoplama_tannarxi = _taxmin221") < _srcc.find("# === LOY HISOB-KITOBI ===")
      and hasattr(Order, "reja_qoplama_tannarxi") and "ADD COLUMN reja_qoplama_tannarxi FLOAT" in open(os.path.join(ROOT, "main.py"), encoding="utf-8").read())

# ── ma'lumot
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k221_a", PAROL, UserRole.ADMIN, "K221 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K221 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000, volume_per_unit=1.0,
                 is_penoplast=True, is_default_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="K221 Kley", unit="kg", stock_quantity=1_000_000, price_per_unit=2_000, category="Kimyo")
PRJ = Project(company_id=1, client_name="K221 mijoz", project_name="K221 loyiha", client_phone="+998901112221", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K221 Usta", phone="+998900002221", kpi_percent=10)
s.add_all([PENO, KLEY, PRJ, US])
s.flush()
REC = Recipe(company_id=1, name="K221 Oq marmar", batch_size_kg=100.0)
REC2 = Recipe(company_id=1, name="K221 Zaxirali", batch_size_kg=100.0)
s.add_all([REC, REC2])
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
s.add(RecipeIngredient(recipe_id=REC2.id, inventory_id=KLEY.id, quantity_kg=100.0))
s.commit()
ID = {"PENO": PENO.id, "KLEY": KLEY.id, "PRJ": PRJ.id, "US": US.id, "REC": REC.id, "REC2": REC2.id}
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "k221_a", "password": PAROL}, follow_redirects=False)
BUGUN = datetime.date.today()
_SANOQ = [0]


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {"_matn": r.text[:300]}


def tana(loy, coated=True, rec="REC", uzun=None):
    _SANOQ[0] += 1
    L = uzun or (40 + _SANOQ[0])
    it = [{"name": f"K221 Karniz {_SANOQ[0]}", "category": "profil", "width": 20, "thickness": 10, "length": L, "quantity": 1,
           "unit_price": 60_000 * L, "is_coated": coated, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}]
    return {"project_id": ID["PRJ"], "order_type": "product", "recipe_id": ID[rec], "master_id": ID["US"],
            "deadline": (BUGUN + datetime.timedelta(days=5)).isoformat(), "is_draft": False, "base_price": 0, "loy_kg": loy, "items": it}


def yarat(loy, coated=True, rec="REC"):
    r = A.post("/api/orders?confirm_shortage=true", json=tana(loy, coated, rec))
    return js(r).get("id") if r.status_code == 200 else None


def foyda(oid):
    return js(A.get(f"/api/orders/{oid}/profit"))


def qoplama(f):
    return [b for b in (f.get("breakdown") or []) if str(b.get("nomi", "")).startswith("Qoplama")]


def narx(inv_id, v):
    s2 = SessionLocal()
    try:
        s2.get(Inventory, inv_id).price_per_unit = v
        s2.commit()
    finally:
        s2.close()


def yigindi_mos(f):
    return (abs(sum(float(b["summa"]) for b in f.get("breakdown") or []) - float(f.get("tan_narxi") or 0)) < 0.01
            and abs(sum(float(q["summa"]) for q in f.get("tannarx_qismlari") or []) - float(f.get("tan_narxi") or 0)) < 0.01)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — server")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
O1 = yarat(300)
f1 = foyda(O1)
q1 = qoplama(f1)
check("A1 jarayondagi buyurtma (reja 300 kg): «Qoplama — reja bo'yicha (300 kg loy × 2 000 so'm/kg, taxminiy)» = 600 000, `taxminiy`, "
      "`loy_holati` = reja (asl: qoplama qatori YO'Q)",
      len(q1) == 1 and q1[0]["nomi"] == "Qoplama — reja bo'yicha (300 kg loy × 2 000 so'm/kg, taxminiy)" and abs(q1[0]["summa"] - 600_000) < 0.01
      and q1[0].get("taxminiy") is True and f1.get("taxminiy") is True and (f1.get("loy_holati") or {}).get("tur") == "reja"
      and (f1.get("loy_holati") or {}).get("reja_kg") == 300.0, (q1, f1.get("taxminiy"), f1.get("loy_holati")))
check("A1b tan narxi = xarajatlar yig'indisi = tannarx qismlari yig'indisi (qoplama ichida)", yigindi_mos(f1), f1)
narx(ID["KLEY"], 6_000)
f1b = foyda(O1)
narx(ID["KLEY"], 2_000)
check("A2 kley narxi ×3 dan keyin ham — 600 000 (ombordan YECHILGAN paytdagi narx, «Tayyor» dagi qoida bilan bir)",
      [x["summa"] for x in qoplama(f1b)] == [600_000.0] and f1b.get("tan_narxi") == f1.get("tan_narxi"), (qoplama(f1b), f1b.get("tan_narxi")))

O2 = yarat(300)
f2a = foyda(O2)
_r2 = A.post(f"/api/orders/{O2}/ready")
f2 = foyda(O2)
check("A3 «Tayyor» (loy kiritilmasdan = reja): oddiy «Qoplama (300 kg loy × 2 000 so'm/kg)», taxminiy EMAS, izoh yo'q; tan narxi taxmindagi bilan AYNAN",
      _r2.status_code == 200 and [x["nomi"] for x in qoplama(f2)] == ["Qoplama (300 kg loy × 2 000 so'm/kg)"]
      and not any("izoh" in x or x.get("taxminiy") for x in qoplama(f2)) and f2.get("taxminiy") is False and f2.get("loy_holati") is None
      and abs(float(f2["tan_narxi"]) - float(f2a["tan_narxi"])) < 0.01 and f2a.get("taxminiy") is True, (_r2.status_code, qoplama(f2), f2a.get("tan_narxi"),
                                                                                                         f2.get("tan_narxi")))

_r1 = A.post(f"/api/orders/{O1}/ready?loy_kg=320")
f1c = foyda(O1)
q1c = qoplama(f1c)
check("A4 «Tayyor» 320 kg: «Qoplama (320 kg loy × 2 000 so'm/kg)» = 640 000 (asl bilan AYNAN), izoh «Loy: reja 300 kg → haqiqiy 320 kg (+20 kg, "
      "+40 000 so'm)», `loy_holati` farq 20 / 40 000",
      _r1.status_code == 200 and len(q1c) == 1 and q1c[0]["nomi"] == "Qoplama (320 kg loy × 2 000 so'm/kg)" and abs(q1c[0]["summa"] - 640_000) < 0.01
      and q1c[0].get("izoh") == "Loy: reja 300 kg → haqiqiy 320 kg (+20 kg, +40 000 so'm)" and f1c.get("taxminiy") is False
      and (f1c.get("loy_holati") or {}).get("tur") == "haqiqiy" and abs((f1c.get("loy_holati") or {}).get("farq_kg", 0) - 20) < 1e-9
      and abs((f1c.get("loy_holati") or {}).get("farq_summa", 0) - 40_000) < 0.01, (_r1.status_code, q1c, f1c.get("loy_holati")))
s4c = SessionLocal()
_snap1 = s4c.get(Order, O1).reja_qoplama_tannarxi if hasattr(Order, "reja_qoplama_tannarxi") else "ustun yo'q"
_snap2 = s4c.get(Order, O2).reja_qoplama_tannarxi if hasattr(Order, "reja_qoplama_tannarxi") else "ustun yo'q"
s4c.close()
check("A4a «Tayyor» oldidagi taxmin saqlandi: 600 000 (320 kg li), 600 000 (loysiz «Tayyor»)", _snap1 == 600_000.0 and _snap2 == 600_000.0, (_snap1, _snap2))
check("A4b tan narxi = taxmin + farq (855 000 → 895 000 kabi: taxmindagi + 40 000)",
      abs(float(f1c["tan_narxi"]) - float(f1["tan_narxi"]) - 40_000) < 0.01 and yigindi_mos(f1c), (f1["tan_narxi"], f1c["tan_narxi"]))

O3 = yarat(300)
f3a = foyda(O3)
_r3 = A.post(f"/api/orders/{O3}/ready?loy_kg=280")
f3 = foyda(O3)
q3 = qoplama(f3)
check("A5 «Tayyor» 280 kg: izoh «Loy: reja 300 kg → haqiqiy 280 kg (−20 kg, −40 000 so'm)», tan narxi taxmindan 40 000 kam",
      _r3.status_code == 200 and len(q3) == 1 and q3[0].get("izoh") == "Loy: reja 300 kg → haqiqiy 280 kg (−20 kg, −40 000 so'm)"
      and abs(float(f3a["tan_narxi"]) - float(f3["tan_narxi"]) - 40_000) < 0.01, (q3, f3a.get("tan_narxi"), f3.get("tan_narxi")))

# xom narx «Tayyor» oldidan o'zgarsa (review221 №1): 300 kg × 2 000 taxmin, kley 3 000, «Tayyor» 350 — qo'shimcha 50 kg × 3 000 = +150 000
O3c = yarat(300)
f3ca = foyda(O3c)
narx(ID["KLEY"], 3_000)
_r3c = A.post(f"/api/orders/{O3c}/ready?loy_kg=350")
f3c = foyda(O3c)
narx(ID["KLEY"], 2_000)
q3c = qoplama(f3c)
check("A4c kley 2 000 → 3 000, «Tayyor» 350 kg: qoplama 750 000, izoh «(+50 kg, +150 000 so'm)» = haqiqiy − taxmin (600 000) — oynada ko'rilgan "
      "taxmin → haqiqiy o'zgarishi bilan AYNAN (o'rtacha narxdagi «+107 143» EMAS)",
      _r3c.status_code == 200 and len(q3c) == 1 and abs(q3c[0]["summa"] - 750_000) < 0.01 and [x["summa"] for x in qoplama(f3ca)] == [600_000.0]
      and q3c[0].get("izoh") == "Loy: reja 300 kg → haqiqiy 350 kg (+50 kg, +150\u00a0000 so'm)"
      and abs(float(f3c["tan_narxi"]) - float(f3ca["tan_narxi"]) - 150_000) < 0.01, (q3c, qoplama(f3ca)))

# taxmin saqlanmagan (eski «Tayyor») — izohda faqat kg; 0,01 kg gacha farq — izoh yo'q (`complete_order` «Reja bo'yicha ketdi»)
s3d = SessionLocal()
if hasattr(Order, "reja_qoplama_tannarxi"):
    s3d.get(Order, O3).reja_qoplama_tannarxi = None
s3d.commit()
s3d.close()
f3d = foyda(O3)
O3e = yarat(300)
_r3e = A.post(f"/api/orders/{O3e}/ready?loy_kg=300.004")
f3e = foyda(O3e)
check("A5b taxmin saqlanmagan (eski «Tayyor») — izoh faqat kg: «Loy: reja 300 kg → haqiqiy 280 kg (−20 kg)», summasi avvalgidek",
      [x.get("izoh") for x in qoplama(f3d)] == ["Loy: reja 300 kg → haqiqiy 280 kg (−20 kg)"]
      and (f3d.get("loy_holati") or {}).get("farq_summa", "yo'q") is None and abs(float(f3d["tan_narxi"]) - float(f3["tan_narxi"])) < 0.01,
      (qoplama(f3d), f3d.get("loy_holati")))
check("A5c «Tayyor» 300,004 kg (reja 300) — farq 0,01 kg dan kichik: izoh yo'q, `loy_holati` yo'q",
      _r3e.status_code == 200 and len(qoplama(f3e)) == 1 and "izoh" not in qoplama(f3e)[0] and f3e.get("loy_holati") is None, (qoplama(f3e), f3e.get("loy_holati")))

O4 = yarat(None)
f4 = foyda(O4)
check("A6 reja loy yozilmagan qoplamali buyurtma — qoplama qatori yo'q, taxminiy EMAS (avvalgidek)",
      qoplama(f4) == [] and f4.get("taxminiy") is False and f4.get("loy_holati") is None and f4.get("success") is True, f4)

O5 = yarat(300)
_r5 = A.put(f"/api/orders/{O5}/loy?loy_kg=400")
f5 = foyda(O5)
check("A7 loy rejasi 300 → 400 kg (`PUT /api/orders/{id}/loy`): «Qoplama — reja bo'yicha (400 kg loy …, taxminiy)» = 800 000",
      _r5.status_code == 200 and [x["summa"] for x in qoplama(f5)] == [800_000.0] and "400 kg loy" in qoplama(f5)[0]["nomi"]
      and f5.get("taxminiy") is True, (_r5.status_code, str(js(_r5))[:300], qoplama(f5)))

s8 = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    _h8 = services.calculate_order_profit(s8, O5, company_id=1, holat_vaqti=datetime.datetime.now())
s8.close()
check("A8 holat (`holat_vaqti` — faqat «Tayyor» hisobotlari) so'ralsa — reja qo'shilmaydi", qoplama(_h8) == [] and _h8.get("taxminiy") is False, _h8)

O9 = yarat(300)
O10 = yarat(300)
_r9 = A.delete(f"/api/orders/{O9}")
s9 = SessionLocal()
_o10 = s9.get(Order, O10)
_o10.status = OrderStatus.CANCELLED
s9.commit()
with contextlib.redirect_stdout(io.StringIO()):
    _f9 = services.calculate_order_profit(s9, O9, company_id=1)
    _f10 = services.calculate_order_profit(s9, O10, company_id=1)
s9.close()
check("A9 o'chirilgan buyurtma (reja loy omborga qaytgan) — reja qo'shilmaydi",
      _r9.status_code == 200 and qoplama(_f9) == [] and not _f9.get("taxminiy"), (_r9.status_code, _f9))
check("A10 bekor qilingan buyurtma — reja qo'shilmaydi", qoplama(_f10) == [] and _f10.get("taxminiy") is False, _f10)

# o'chirilgan deb belgilangan (savatdagi) jarayondagi buyurtma va «Tayyor» lekin haqiqiy loy yozilmagan (eski) buyurtma — reja qo'shilmaydi
O9b = yarat(300)
O13 = yarat(300)
_r13 = A.post(f"/api/orders/{O13}/ready")
s13 = SessionLocal()
s13.get(Order, O9b).is_deleted = True
_o13 = s13.get(Order, O13)
_o13.actual_loy_kg = None
_o13.notes = re.sub(r",?\s*loy_kg=[\d.]+", "", _o13.notes or "")
s13.commit()
with contextlib.redirect_stdout(io.StringIO()):
    _f9b = services.calculate_order_profit(s13, O9b, company_id=1)
    _f13 = services.calculate_order_profit(s13, O13, company_id=1)
s13.close()
check("A9b o'chirilgan deb belgilangan (`is_deleted`) jarayondagi buyurtma — reja qo'shilmaydi",
      _f9b.get("success") is True and qoplama(_f9b) == [] and _f9b.get("taxminiy") is False, _f9b)
check("A13 «Tayyor», lekin haqiqiy loy yozilmagan (eski yozuv) — reja qo'shilmaydi (hisobotdagi «Tayyor» qiymati avvalgidek)",
      _r13.status_code == 200 and _f13.get("success") is True and qoplama(_f13) == [] and _f13.get("taxminiy") is False, (_r13.status_code, _f13))

# jarayondagi buyurtmada haqiqiy loy ANIQ 0 yozilgan (masalan o'chirish yakunini tiklashdagi surat) — reja emas, haqiqiy (0)
O13b = yarat(300)
s13b = SessionLocal()
s13b.get(Order, O13b).actual_loy_kg = 0.0
s13b.commit()
with contextlib.redirect_stdout(io.StringIO()):
    _f13b = services.calculate_order_profit(s13b, O13b, company_id=1)
s13b.close()
check("A13b jarayondagi buyurtma, haqiqiy loy = 0 (yozilgan) — reja qo'shilmaydi", _f13b.get("success") is True and qoplama(_f13b) == []
      and _f13b.get("taxminiy") is False, _f13b)

# qoralama: ombordan hali yechilmagan — taxmin JORIY narxda (yozilgan reja bo'yicha, «taxminiy»)
s15 = SessionLocal()
_q0 = float(s15.get(Inventory, ID["KLEY"]).stock_quantity)
s15.close()
_t15 = tana(300)
_t15["is_draft"] = True
_r15 = A.post("/api/orders?confirm_shortage=true", json=_t15)
O15 = js(_r15).get("id")
s15 = SessionLocal()
_q1 = float(s15.get(Inventory, ID["KLEY"]).stock_quantity)
_st15 = s15.get(Order, O15).status.value if O15 else None
s15.close()
f15 = foyda(O15) if O15 else {}
check("A15 qoralama (reja 300 kg, ombordan YECHILMAGAN) — «Qoplama — reja bo'yicha (…, taxminiy)» joriy narxda 600 000",
      _r15.status_code == 200 and _st15 == "draft" and abs(_q1 - _q0) < 1e-9 and [x["summa"] for x in qoplama(f15)] == [600_000.0]
      and f15.get("taxminiy") is True, (_r15.status_code, _st15, _q0, _q1, qoplama(f15)))

# tayyor loy zaxirasi: 500 kg (yechilgan paytdagi retsept narxi 2 000) — buyurtma rejasi zaxiradan
s11 = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    _z = services.get_or_create_loy_stock(s11, s11.get(Recipe, ID["REC2"]))
_z.stock_quantity = 500.0
s11.commit()
s11.close()
O11 = yarat(300, rec="REC2")
narx(ID["KLEY"], 6_000)
f11 = foyda(O11)
_r11 = A.post(f"/api/orders/{O11}/ready")
f11b = foyda(O11)
narx(ID["KLEY"], 2_000)
q11 = qoplama(f11)
check("A11 tayyor loy zaxirasidan olingan reja: «… 300 kg tayyor loy zaxirasidan × 2 000 …, taxminiy» = 600 000 (kley ×3 dan keyin ham); «Tayyor» "
      "(loysiz) — AYNAN shu summa, taxminiysiz",
      len(q11) == 1 and "tayyor loy zaxirasidan" in q11[0]["nomi"] and q11[0]["nomi"].endswith(", taxminiy)") and abs(q11[0]["summa"] - 600_000) < 0.01
      and _r11.status_code == 200 and [x["summa"] for x in qoplama(f11b)] == [600_000.0] and f11b.get("taxminiy") is False
      and abs(float(f11b["tan_narxi"]) - float(f11["tan_narxi"])) < 0.01, (q11, qoplama(f11b), _r11.status_code))

# zaxiradan olingan reja, narx o'zgargach «Tayyor» boshqa kg bilan — izohdagi pul farqi = haqiqiy − «Tayyor» oldidagi taxmin
O14 = yarat(100, rec="REC2")
f14a = foyda(O14)
narx(ID["KLEY"], 6_000)
_r14 = A.post(f"/api/orders/{O14}/ready?loy_kg=150")
f14 = foyda(O14)
narx(ID["KLEY"], 2_000)
_q14a, _q14 = qoplama(f14a), qoplama(f14)
check("A11b zaxiradan olingan reja 100 kg (× 2 000 = taxmin 200 000) → kley ×3 → «Tayyor» 150 kg (qoplama 500 000): izoh «(+50 kg, "
      "+300 000 so'm)» = haqiqiy − taxmin",
      _r14.status_code == 200 and len(_q14a) == 1 and len(_q14) == 1 and "tayyor loy zaxirasidan" in _q14a[0]["nomi"]
      and abs(float(_q14a[0]["summa"]) - 200_000) < 0.01 and abs(float(_q14[0]["summa"]) - 500_000) < 0.01
      and _q14[0].get("izoh") == "Loy: reja 100 kg → haqiqiy 150 kg (+50 kg, +300\u00a0000 so'm)"
      and abs(float((f14.get("loy_holati") or {}).get("farq_summa") or 0) - 300_000) < 0.01,
      (_r14.status_code, _q14a, _q14, f14.get("loy_holati")))

# hisobotlar: «Tayyor» buyurtmalar — taxminiy foyda hech qachon kirmaydi (jarayondagi O_J reja bilan bor)
O_J = yarat(300)
_asl = services.calculate_order_profit
CHAQ = []


def _kuzat(*a, **k):
    r = _asl(*a, **k)
    CHAQ.append((a[1] if len(a) > 1 else k.get("order_id"), bool(isinstance(r, dict) and r.get("taxminiy"))))
    return r


def _hisobotlar():
    """oylik hisobot, loyihalar paneli, usta KPI, grafik, loyiha tafsiloti — istisno YUTILMAYDI (review221 2-bosqich)"""
    _s = SessionLocal()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _n = (services.get_monthly_report(_s, BUGUN.year, BUGUN.month, company_id=1), crud.get_projects_dashboard_stats(_s, company_id=1),
                  crud.get_masters_kpi_report(_s, BUGUN.year, company_id=1), services.get_chart_data(_s, company_id=1))
    finally:
        _s.close()
    _r = A.get(f"/api/projects/{ID['PRJ']}/detail-stats")
    return json.dumps([_n, _r.status_code, js(_r)], sort_keys=True, default=str)


services.HISOBOT_XOTIRASI_YOQIQ = False
services.calculate_order_profit = _kuzat
try:
    _h12a = xav(_hisobotlar, standart="XATO")
finally:
    services.calculate_order_profit = _asl
_s12 = SessionLocal()
_oj = _s12.get(Order, O_J)
_reja12 = _oj.planned_loy_kg
_oj.planned_loy_kg = 0.0
_s12.commit()
_s12.close()
_h12b = xav(_hisobotlar, standart="XATO")
_s12 = SessionLocal()
_s12.get(Order, O_J).planned_loy_kg = _reja12
_s12.commit()
_s12.close()
check("A12 oylik hisobot, loyihalar paneli, usta KPI, grafik, loyiha tafsiloti — xatosiz, foyda hisoblangan (≥ 1 chaqiruv), birortasi TAXMINIY emas, "
      "jarayondagi buyurtma kirmaydi",
      _h12a != "XATO" and len(CHAQ) >= 1 and not any(t for _i, t in CHAQ) and O_J not in [i for i, _t in CHAQ], (CHAQ[:20], str(_h12a)[:200]))
check("A12b hisobotlar natijasi jarayondagi buyurtma rejasi bor (300 kg) / yo'q (0) — AYNAN bir xil (taxmin hisobotga kirmaydi)",
      _h12a != "XATO" and _h12a == _h12b, (len(str(_h12a)), len(str(_h12b))))

# «Tayyor» buyurtmaning loy rejasi o'zgarmaydi (review221 2-2): PUT /loy — 400, coating-notify — 409; reja, ombor, izoh o'zgarmaydi
_s17 = SessionLocal()
_k17 = float(_s17.get(Inventory, ID["KLEY"]).stock_quantity)
_s17.close()
_r17a = A.put(f"/api/orders/{O1}/loy?loy_kg=400")
_r17b = A.post(f"/api/orders/{O1}/coating-notify?loy_kg=250")
_s17 = SessionLocal()
_o17 = _s17.get(Order, O1)
_reja17, _k17b = _o17.planned_loy_kg, float(_s17.get(Inventory, ID["KLEY"]).stock_quantity)
_s17.close()
f17 = foyda(O1)
check("A17 «Tayyor» buyurtma (reja 300, haqiqiy 320): loy rejasini o'zgartirish — `PUT /loy` 400, `coating-notify` 409; reja 300, kley o'zgarmadi, "
      "izoh avvalgidek",
      _r17a.status_code == 400 and _r17b.status_code == 409 and _reja17 == 300.0 and abs(_k17b - _k17) < 1e-9
      and [x.get("izoh") for x in qoplama(f17)] == ["Loy: reja 300 kg → haqiqiy 320 kg (+20 kg, +40\u00a0000 so'm)"],
      (_r17a.status_code, _r17b.status_code, _reja17, _k17, _k17b, qoplama(f17)))
O17 = yarat(300)
_r17c = A.post(f"/api/orders/{O17}/coating-notify?loy_kg=300")
check("A17b jarayondagi buyurtmada `coating-notify` — avvalgidek 200", _r17c.status_code == 200, (_r17c.status_code, _r17c.text[:200]))

# taxmin o'qishida SQL xatosi (review221 2-1): «Tayyor» to'xtamaydi (PG — savepoint), taxmin NULL, izohda faqat kg
O16 = yarat(300)
_asl16 = services.calculate_order_profit
_chaq16 = []


def _buzuq16(db, oid, *a, **k):
    from sqlalchemy import text as _t16
    _o = db.get(Order, oid)
    if _o is not None and _o.status != OrderStatus.READY:      # faqat «Tayyor» OLDIDAGI taxmin o'qishi (keyingi KPI hisobi — tegilmaydi)
        _chaq16.append(oid)
        db.execute(_t16("SELECT * FROM yoq_jadval_k221"))
    return _asl16(db, oid, *a, **k)


services.calculate_order_profit = _buzuq16
try:
    _r16 = A.post(f"/api/orders/{O16}/ready?loy_kg=310")
finally:
    services.calculate_order_profit = _asl16
_s16 = SessionLocal()
_o16 = _s16.get(Order, O16)
_st16, _sn16, _hq16 = _o16.status.value, getattr(_o16, "reja_qoplama_tannarxi", "?"), _o16.actual_loy_kg
_s16.close()
f16 = foyda(O16)
check("A16 taxmin o'qishida SQL xatosi — «Tayyor» 200, buyurtma READY, haqiqiy 310 kg, taxmin NULL, izoh faqat kg «(+10 kg)»",
      _chaq16 == [O16] and _r16.status_code == 200 and _st16 == "ready" and _hq16 == 310.0 and _sn16 is None
      and [x.get("izoh") for x in qoplama(f16)] == ["Loy: reja 300 kg → haqiqiy 310 kg (+10 kg)"],
      (_chaq16, _r16.status_code, _r16.text[:300], _st16, _sn16, _hq16, qoplama(f16)))

# qisman «Tayyor»: yarmi topshirilgan, haqiqiy loy 150 — izoh: haqiqiy − taxmin (−150 kg, −300 000)
O18 = yarat(300)
_h18 = js(A.get(f"/api/orders/{O18}/delivery-status")).get("items") or []
_r18d = A.post("/api/deliveries", json={"order_id": O18, "items": [{"order_item_id": x["id"], "quantity": round(float(x["remaining"]) / 2, 2)}
                                                                    for x in _h18 if (x.get("remaining") or 0) > 1e-6],
                                        "received_by": "K221", "notes": "K221 qisman", "transport_carrier": "", "transport_cost": 0,
                                        "transport_payer": "client"})
f18a = foyda(O18)
_r18 = A.post(f"/api/orders/{O18}/ready?loy_kg=150")
f18 = foyda(O18)
q18 = qoplama(f18)
check("A18 qisman «Tayyor» (yarmi topshirilgan, reja 300, haqiqiy 150): taxmin 600 000 → qoplama 300 000, izoh «(−150 kg, −300 000 so'm)»",
      _r18d.status_code == 200 and _r18.status_code == 200 and [x["summa"] for x in qoplama(f18a)] == [600_000.0] and len(q18) == 1
      and abs(q18[0]["summa"] - 300_000) < 0.01 and q18[0].get("izoh") == "Loy: reja 300 kg → haqiqiy 150 kg (−150 kg, −300\u00a0000 so'm)",
      (_r18d.status_code, _r18.status_code, qoplama(f18a), q18))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U — HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    print("  (PG rejimida brauzer bo'limi o'tkazilmaydi — SQLite / TF1 da)")
else:
    PW_BOR = True
    try:
        from playwright.sync_api import sync_playwright
    except Exception:                      # noqa: BLE001
        PW_BOR = False
    check("U0 Python `playwright` bor", PW_BOR)
    NAT = {}
    XATO = []
    if PW_BOR:
        import uvicorn                             # noqa: E402
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
        OYNA = """() => { const m = document.getElementById('profitModal'); if (!m) return null;
            return {matn: m.innerText, taxm: (m.querySelector('.foyda-taxminiy') || {}).innerText || '',
                    izoh: [...m.querySelectorAll('.foyda-izoh')].map(x => x.innerText),
                    cost: (document.getElementById('s-cost') || {}).textContent || '',
                    prof: (document.getElementById('s-profit') || {}).textContent || ''}; }"""
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "k221_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.goto, BU + "/orders")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.evaluate, f"() => {{ selectedOrderId = {O_J}; return loadProfit(); }}")
            xav(pg.wait_for_timeout, 1200)
            NAT["jarayon"] = xav(pg.evaluate, OYNA)
            xav(pg.evaluate, "() => { const m = document.getElementById('profitModal'); if (m) m.remove(); }")
            xav(pg.evaluate, f"() => {{ selectedOrderId = {O1}; return loadProfit(); }}")
            xav(pg.wait_for_timeout, 1200)
            NAT["tayyor"] = xav(pg.evaluate, OYNA)
            br.close()
        server.should_exit = True
        j = NAT.get("jarayon") or {}
        t = NAT.get("tayyor") or {}
        check("U1 jarayondagi buyurtma «Foyda tahlili»: «Qoplama — reja bo'yicha», tushuntirish bloki «300 kg … taxminiy … «Tayyor» qilinganda»",
              "Qoplama — reja bo'yicha" in (j.get("matn") or "") and "300 kg" in (j.get("taxm") or "") and "taxminiy" in (j.get("taxm") or "")
              and "Tayyor" in (j.get("taxm") or "") and "Jami tan narxi (taxminiy):" in (j.get("matn") or ""), j)
        check("U2 kartada tan narxi «(taxminiy)», foyda «· taxminiy»; oynada «⊖ Tan narxi (taxminiy)», «📈 Foyda (taxminiy)», «Foyda (Sotuv − Tan narxi) — "
      "taxminiy»", "(taxminiy)" in (j.get("cost") or "") and "taxminiy" in (j.get("prof") or "")
      and "Tan narxi (taxminiy)" in (j.get("matn") or "") and "Foyda (taxminiy)" in (j.get("matn") or "")
      and "tan narxi) — taxminiy" in (j.get("matn") or "").lower(), j)
        check("U3 «Tayyor» (320 kg) buyurtma: izoh «Loy: reja 300 kg → haqiqiy 320 kg (+20 kg, +40 000 so'm)», taxminiy bloki / belgisi YO'Q",
              t.get("izoh") and "Loy: reja 300 kg → haqiqiy 320 kg (+20 kg, +40" in t["izoh"][0] and not t.get("taxm")
              and "taxminiy" not in (t.get("cost") or "") and "taxminiy" not in (t.get("matn") or ""), t)
        check("U4 JS xatosi yo'q", not XATO, XATO[:3])

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
