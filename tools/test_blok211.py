#!/usr/bin/env python3
"""
test_blok211.py — kech155 (zip 211 «Blok hisoblash» — egasi so'rovi 23.10 21:36, kelishuv 21:3x–21:54).

NIMA UCHUN KERAK
  Boshqa korxona kub (Profil / Panel / Donali) ishlatmaydi — BLOK da hisoblaydi. Blok detali kub kabi butun jarayonda ishlaydi: birlik
  m / ta / m², «1 blokdan chiqadigan» (xodim yozadi), «Necha … kerak», «1 blok narxi» — QOPLAMASIZ (detalda yozilsa — o'ziniki, yozilmasa —
  buyurtmaning «1 blok asosiy narxi»), qoplama — koeffitsient (standart 2), plotnost — ombordan qaysi blok. Sozlamalarda HAMMA tur
  (Profil, Panel, Donali, Blok, Loy sotish, MRP) yashirilsa bo'ladi, kamida bittasi yoqiq.
BO'LIMLAR
  K — turlar sozlamasi: sozlanmagan korxona (eski qoida AYNAN), `v=2` to'liq ro'yxat, eski sahifa (faqat ixtiyoriylar), kamida bitta,
      jurnal, eski kalit (orqaga qaytish uchun), yangi korxona standarti, korxonalar ajralgan.
  B — server: blok detal ustunlari (birlik / chiqishi / o'z narxi / koeffitsient), «1 blok asosiy narxi», ombor (blok soni), birlik
      (`delivery_unit`, PDF, jurnal), tahrir, topshirilgan detal birligi o'zgarmaydi, tayyor mahsulot (ishlab chiqarish birligi, buyurtmada
      birlik — mahsulotniki), tana qat'iy (noma'lum birlik / chegara — 422 / 400), taklif, usta birliklari, tayyor mahsulot hisobi (oy chegarasi).
  U — HAQIQIY brauzer (Playwright): faqat Blok yoqiq korxona — tur tugmalari, asosiy narx maydonlari, blok hisobi (m / ta / m², o'z narxi,
      asosiy, koeffitsient), saqlash → server, tahrirda tiklanish (o'zgarishsiz saqlash — summa o'zgarmaydi), eski (zip 211 dan oldingi) blok
      yozuvi, yashirin turdagi mavjud detal, Sozlamalar sahifasi (6 tur, hammasini o'chirib bo'lmaydi), Tayyor mahsulotlar (blok ishlab
      chiqarish, buyurtmaga olish), qoralama, telefon (390 px), JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (U bo'limi faqat SQLite / TF1 da).
Asl kodga (zip 210) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_blok211.py
"""
import os
import io
import sys
import time
import tempfile
import datetime
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "blok211_test"
_T = tempfile.mkdtemp(prefix="k211_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k211.db')}"
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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def yaqin(a, b, eps=0.005):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


_MIG = io.StringIO()
with contextlib.redirect_stdout(_MIG):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, Project, FinishedProduct, StockSource, ProductionStatus, OrderItem, Order,  # noqa: E402
                    ActivityLog, CompanySetting, User, OrderType, OrderStatus, DeliveryItem, Recipe)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import text                        # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
for _cid, _nom in ((2, "K211 B korxona"), (3, "K211 Blok korxona")):
    if not s.get(Company, _cid):
        s.add(Company(id=_cid, name=_nom))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k211_a", PAROL, UserRole.ADMIN, "K211 Admin", company_id=1)
    auth.create_user(s, "k211_b", PAROL, UserRole.ADMIN, "K211 B Admin", company_id=2)
    auth.create_user(s, "k211_c", PAROL, UserRole.ADMIN, "K211 Blok Admin", company_id=3)
    auth.create_user(s, "k211_plat", PAROL, UserRole.ADMIN, "K211 Platforma", company_id=1)
_pu = s.query(User).filter(User.username == "k211_plat").first()
_pu.is_platform_admin = True
PENO = Inventory(company_id=1, item_name="K211 Penoplast 15", unit="blok", stock_quantity=1_000, price_per_unit=500_000,
                 volume_per_unit=2.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
PENO2 = Inventory(company_id=1, item_name="K211 Penoplast 25", unit="blok", stock_quantity=1_000, price_per_unit=800_000,
                  volume_per_unit=2.0, is_penoplast=True, is_default_penoplast=False, category="Penoplast")
PENO_C = Inventory(company_id=3, item_name="C Penoplast 15", unit="blok", stock_quantity=500, price_per_unit=450_000,
                   volume_per_unit=2.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P1 = Project(company_id=1, client_name="Sardor K211", project_name="Andijon K211", client_phone="+998901112211", total_budget=0, total_paid=0)
PC = Project(company_id=3, client_name="Demo mijoz", project_name="Demo loyiha", client_phone="+998901112212", total_budget=0, total_paid=0)
s.add_all([PENO, PENO2, PENO_C, P1, PC])
s.commit()
ID = {"PENO": PENO.id, "PENO2": PENO2.id, "PENO_C": PENO_C.id, "P1": P1.id, "PC": PC.id}
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    return c


A = mijoz("k211_a")
B = mijoz("k211_b")
C = mijoz("k211_c")


def js(r):
    try:
        return r.json()
    except Exception:                   # noqa: BLE001
        return {}


def turlar(c=A):
    return {x["code"]: x["enabled"] for x in (js(c.get("/api/settings/categories")).get("categories") or [])}


def sozlama(cid, kalit):
    _s = SessionLocal()
    try:
        r = _s.query(CompanySetting).filter(CompanySetting.company_id == cid, CompanySetting.key == kalit).first()
        return None if r is None else r.value
    finally:
        _s.close()


def stok(pid):
    _s = SessionLocal()
    try:
        return float(_s.get(Inventory, pid).stock_quantity)
    finally:
        _s.close()


def blok(nom, birlik, chiqishi, kerak, oz=None, asosiy=600_000, koef=2.0, qoplama=False, peno=None, fp=None, eni=None, qalin=None):
    """Forma (`collectItems`) yuboradigan blok detal — 1 birlik narxi formadagi formula bilan."""
    bn = oz if oz else asosiy
    birlik_narxi = (bn / chiqishi) * (koef if qoplama else 1) if chiqishi else 0
    return {"name": nom, "category": "blok", "width": eni, "thickness": qalin, "length": (kerak / chiqishi) if chiqishi else 0,
            "quantity": kerak, "unit_price": birlik_narxi, "is_coated": qoplama, "penoplast_id": peno, "price_per_m3": None,
            "finished_product_id": fp, "blok_birlik": birlik, "blok_chiqishi": chiqishi, "blok_narxi": oz, "blok_koef": koef,
            "notes": f"blok_narxi={bn * (koef if qoplama else 1)},blok_yield={chiqishi}"}


def buyurtma(items, pid=None, **kw):
    b = {"project_id": pid or ID["P1"], "order_type": "product", "items": items,
         "deadline": (datetime.date.today() + datetime.timedelta(days=10)).isoformat() + "T00:00:00"}
    b.update(kw)
    return b


def detallar(c, oid):
    return js(c.get(f"/api/orders/{oid}"))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Mahsulot turlari sozlamasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_k0 = turlar(A)
check("K1 GET — 6 tur (Profil, Panel, Donali, Blok, Loy sotish, MRP); sozlanmagan korxona — eski qoida AYNAN (Blok yashirin, qolgani yoqiq)",
      list(_k0) == ["profil", "panel", "dona", "blok", "loy_sotish", "mrp_product"]
      and _k0 == {"profil": True, "panel": True, "dona": True, "blok": False, "loy_sotish": True, "mrp_product": True}, _k0)
_kl = [x["label"] for x in (js(A.get("/api/settings/categories")).get("categories") or [])]
check("K1b nomlar: «🧊 Blok» (endi «eskirgan» yozuvi yo'q)", "🧊 Blok" in _kl and not any("eskirgan" in x for x in _kl), _kl)
_r = C.put("/api/settings/categories", data={"codes": "blok", "v": "2"})
check("K2 `v=2` faqat Blok — 200, yoqilgani faqat Blok; `cat_on` — Profil / Panel / Donali / MRP yo'q",
      _r.status_code == 200 and turlar(C) == {"profil": False, "panel": False, "dona": False, "blok": True, "loy_sotish": False,
                                              "mrp_product": False}
      and not main.cat_on("profil", 3) and main.cat_on("blok", 3) and not main.cat_on("mrp_product", 3), (_r.status_code, turlar(C)))
check("K2b saqlandi: `mahsulot_turlari` = «blok», eski `enabled_categories` = «blok» (orqaga qaytilsa ham Blok yoqiq qoladi)",
      sozlama(3, "mahsulot_turlari") == "blok" and sozlama(3, "enabled_categories") == "blok",
      (sozlama(3, "mahsulot_turlari"), sozlama(3, "enabled_categories")))
_r = C.put("/api/settings/categories", data={"codes": "", "bosh": "1", "v": "2"})
check("K3 hammasini o'chirish (`bosh=1`, `v=2`) — 400 «Kamida bitta», hech narsa o'zgarmadi",
      _r.status_code == 400 and "Kamida bitta" in _r.text and turlar(C)["blok"] and sozlama(3, "mahsulot_turlari") == "blok",
      (_r.status_code, _r.text[:200]))
_r = C.put("/api/settings/categories", data={"codes": "", "v": "2"})
check("K4 bo'sh ro'yxat `bosh` siz — 400 «yuklanmagan» (ilgarigi C1 qoidasi)", _r.status_code == 400 and "yuklanmagan" in _r.text,
      (_r.status_code, _r.text[:200]))
_r = C.put("/api/settings/categories", data={"codes": "noma_lum,gips", "v": "2"})
check("K4b faqat noma'lum / olib tashlangan kodlar — 400, o'zgarmadi", _r.status_code == 400 and sozlama(3, "mahsulot_turlari") == "blok",
      (_r.status_code, _r.text[:200]))
# eski sahifa (zip 211 dan oldingi, faqat Loy sotish / Blok ni biladi) — asosiy turlar holati saqlanadi
_r = A.put("/api/settings/categories", data={"codes": "loy_sotish,blok"})
check("K5 eski sahifa (`v` yo'q, faqat ixtiyoriy kodlar) — Profil / Panel / Donali / MRP holati SAQLANDI, Blok yoqildi",
      _r.status_code == 200 and turlar(A) == {"profil": True, "panel": True, "dona": True, "blok": True, "loy_sotish": True,
                                              "mrp_product": True}, (_r.status_code, turlar(A)))
_r = A.put("/api/settings/categories", data={"codes": "", "bosh": "1"})
check("K5b eski sahifa «hammasini o'chirish» (`bosh=1`) — faqat Loy sotish / Blok o'chdi, asosiylar yoqiq (natija bo'sh emas — 200)",
      _r.status_code == 200 and turlar(A) == {"profil": True, "panel": True, "dona": True, "blok": False, "loy_sotish": False,
                                              "mrp_product": True}, (_r.status_code, turlar(A)))
_r = A.put("/api/settings/categories", data={"codes": "dona,blok,loy_sotish", "v": "2"})
_s = SessionLocal()
_jur = [(a.new_value or "") for a in _s.query(ActivityLog).filter(ActivityLog.company_id == 1, ActivityLog.entity_type == "company_settings")
        .order_by(ActivityLog.id.desc()).limit(1).all()]
_s.close()
check("K6 jurnal: «yoqildi: 🧊 Blok», «yoqildi: 🪣 Loy sotish», «o'chirildi: 📏 Profil / 🔲 Panel / 🏭 MRP mahsuloti» — bitta yozuvda",
      _r.status_code == 200 and _jur and all(x in _jur[0] for x in ("yoqildi: 🧊 Blok", "yoqildi: 🪣 Loy sotish", "o'chirildi: 📏 Profil",
                                                                     "o'chirildi: 🔲 Panel", "o'chirildi: 🏭 MRP mahsuloti"))
      and "Donali" not in _jur[0], _jur)
check("K6b kodlarda asosiy tur bor (`v` siz ham) — to'liq ro'yxat deb olinadi",
      (A.put("/api/settings/categories", data={"codes": "profil,panel"}).status_code == 200
       and turlar(A) == {"profil": True, "panel": True, "dona": False, "blok": False, "loy_sotish": False, "mrp_product": False}), turlar(A))
A.put("/api/settings/categories", data={"codes": "profil,panel,dona,blok,loy_sotish,mrp_product", "v": "2"})
check("K7 korxonalar ajralgan: B (sozlanmagan) — eski qoida (Blok yashirin), C — faqat Blok",
      turlar(B) == {"profil": True, "panel": True, "dona": True, "blok": False, "loy_sotish": True, "mrp_product": True}
      and turlar(C)["blok"] and not turlar(C)["profil"], (turlar(B), turlar(C)))
s = SessionLocal()
if PG_URL:
    s.execute(text("SELECT setval(pg_get_serial_sequence('companies', 'id'), (SELECT MAX(id) FROM companies))"))
    s.commit()
s.close()
CP = mijoz("k211_plat")
_rk = CP.post("/api/platform/companies", data={"name": "K211 Yangi korxona", "admin_username": "k211_yangi"})
_yk = ((js(_rk) or {}).get("company") or {}).get("id")
check("K8 platformadan yangi korxona — Profil, Panel, Donali, MRP yoqiq; Blok, Loy sotish yashirin (egasi QARORI)",
      _rk.status_code == 200 and _yk and sozlama(_yk, "mahsulot_turlari") == "profil,panel,dona,mrp_product"
      and getattr(main, "yoqilgan_turlar", lambda _c: None)(_yk) == ["profil", "panel", "dona", "mrp_product"],
      (_rk.status_code, _rk.text[:200], _yk and sozlama(_yk, "mahsulot_turlari")))
_ts211 = getattr(main, "turlar_sozlamadan", None)      # asl kodda (zip 210) yo'q — sinov yiqiladi, qulamaydi
check("K9 `turlar_sozlamadan`: buzilgan yangi qiymat (faqat noma'lum so'z) — eski qoidaga (yashirib yuborilmaydi); faqat Blok — o'zi; "
      "ixtiyoriylar — eski kalitdan (zip 210 ga qaytib eski sahifada yoqilgan Blok / Loy sotish saqlanadi — review211 №11)",
      _ts211 is not None
      and _ts211("gips,termopanel", None) == {"profil", "panel", "dona", "mrp_product", "loy_sotish"}
      and _ts211("blok", "blok") == {"blok"} and _ts211(None, "") == {"profil", "panel", "dona", "mrp_product"}
      and _ts211("profil,panel,dona,mrp_product", "loy_sotish,blok") == {"profil", "panel", "dona", "mrp_product", "loy_sotish", "blok"}
      and _ts211("blok", "") == {"profil", "panel", "dona", "mrp_product"}, "turlar_sozlamadan yo'q" if _ts211 is None else "")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Server — blok detal")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_st0 = stok(ID["PENO"])
_items = [blok("B1 rozetka", "dona", 200, 50, peno=ID["PENO"], eni=12, qalin=3),
          blok("B1 plita", "m2", 25, 30, oz=500_000, peno=ID["PENO"]),
          blok("B1 karniz", "metr", 40, 100, peno=ID["PENO"])]
_r = A.post("/api/orders", json=buyurtma(_items, blok_base_price=600_000))
O1 = js(_r).get("id")
_d = detallar(A, O1) if O1 else {}
_it = {x["name"]: x for x in (_d.get("items") or [])}
check("B1 yaratildi — 200; «1 blok asosiy narxi» saqlandi va javobda (600 000)",
      _r.status_code == 200 and O1 and yaqin(_d.get("blok_base_price"), 600_000), (_r.status_code, _r.text[:300]))
check("B2 ta: 1 blokdan 200 ta, 50 ta (asosiy 600 000) → 1 ta 3 000, jami 150 000, blok 0,25; birlik — dona; o'lcham 12×3 saqlandi",
      _it.get("B1 rozetka", {}).get("blok_birlik") == "dona" and yaqin(_it["B1 rozetka"].get("blok_chiqishi"), 200)
      and _it["B1 rozetka"].get("blok_narxi") is None and yaqin(_it["B1 rozetka"]["unit_price"], 3000)
      and yaqin(_it["B1 rozetka"]["total_price"], 150_000) and yaqin(_it["B1 rozetka"]["length"], 0.25, 1e-9)
      and _it["B1 rozetka"]["delivery_unit"] == "dona" and _it["B1 rozetka"]["width"] == 12 and _it["B1 rozetka"]["thickness"] == 3,
      _it.get("B1 rozetka"))
check("B3 m²: o'z blok narxi 500 000, 1 blokdan 25 m², 30 m² → 1 m² 20 000, jami 600 000, birlik «m²», o'z narxi saqlandi",
      _it.get("B1 plita", {}).get("blok_birlik") == "m2" and yaqin(_it["B1 plita"].get("blok_narxi"), 500_000)
      and yaqin(_it["B1 plita"]["unit_price"], 20_000) and yaqin(_it["B1 plita"]["total_price"], 600_000)
      and _it["B1 plita"]["delivery_unit"] == "m²", _it.get("B1 plita"))
check("B4 m: 1 blokdan 40 m, 100 m → 1 m 15 000, jami 1 500 000, birlik metr; koeffitsient 2 saqlandi",
      _it.get("B1 karniz", {}).get("blok_birlik") == "metr" and yaqin(_it["B1 karniz"]["unit_price"], 15_000)
      and yaqin(_it["B1 karniz"]["total_price"], 1_500_000) and _it["B1 karniz"]["delivery_unit"] == "metr"
      and yaqin(_it["B1 karniz"].get("blok_koef"), 2), _it.get("B1 karniz"))
check("B5 ombordan blok soni ayirildi: 0,25 + 1,2 + 2,5 = 3,95 blok", yaqin(_st0 - stok(ID["PENO"]), 3.95, 1e-6), (_st0, stok(ID["PENO"])))
check("B6 buyurtma jami = 150 000 + 600 000 + 1 500 000", yaqin(_d.get("total_amount"), 2_250_000), _d.get("total_amount"))
_s = SessionLocal()
_oi = _s.query(OrderItem).filter(OrderItem.order_id == O1).all()
_pr = services.calculate_order_profit(_s, O1, company_id=1) if O1 else {}
_s.close()
check("B7 tan narxi — ishlatilgan blok × blok narxi: 3,95 × 500 000 = 1 975 000",
      yaqin(_pr.get("tan_narxi"), 3.95 * 500_000, 1), _pr.get("tan_narxi"))
# PDF birligi
try:
    import pdf_service
    _s = SessionLocal()
    _o = _s.get(Order, O1)
    _pdf = pdf_service.generate_nakladnoy(_o, _s)
    _s.close()
    from pypdf import PdfReader
    _txt = "".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(_pdf)).pages)
    check("B8 buyurtma PDF: birliklar «dona», «m²», «m» (ilgari blok doim «m»)",
          "m²" in _txt and "dona" in _txt and "B1 rozetka" in _txt, _txt[:600])
except ImportError:
    check("B8 buyurtma PDF (pypdf yo'q — o'tkazildi)", True)
except Exception as _e:                    # noqa: BLE001
    check("B8 buyurtma PDF", False, f"{type(_e).__name__}: {_e}")

# Tahrir: birlik / o'z narxi o'zgaradi; boshqa turga o'tsa blok ustunlari tozalanadi
_items2 = [blok("B1 rozetka", "m2", 20, 10, oz=400_000, peno=ID["PENO"]),
           blok("B1 plita", "m2", 25, 30, oz=500_000, peno=ID["PENO"]),
           {"name": "B1 karniz", "category": "profil", "width": 10, "thickness": 10, "length": 5, "quantity": 1, "unit_price": 12_500,
            "is_coated": False, "penoplast_id": ID["PENO"], "notes": "blok_narxi=600000,blok_yield=40",
            # eskirgan blok qiymatlari (noto'g'ri mijoz yuborgan) — profilda saqlanmasligi kerak
            "blok_birlik": "dona", "blok_chiqishi": 40, "blok_narxi": 600000, "blok_koef": 2}]
_r = A.put(f"/api/orders/{O1}", json=buyurtma(_items2, blok_base_price=650_000))
_d = detallar(A, O1)
_it = {x["name"]: x for x in (_d.get("items") or [])}
check("B9 tahrir: rozetka — m², o'z narxi 400 000, chiqishi 20; asosiy narx 650 000",
      _r.status_code == 200 and _it.get("B1 rozetka", {}).get("blok_birlik") == "m2" and yaqin(_it["B1 rozetka"].get("blok_narxi"), 400_000)
      and yaqin(_it["B1 rozetka"].get("blok_chiqishi"), 20) and yaqin(_d.get("blok_base_price"), 650_000), (_r.status_code, _r.text[:300]))
check("B10 tahrir: blokdan profilga o'tgan detal — blok ustunlari TOZALANDI (tana blok qiymatlarini yuborsa ham)",
      _it.get("B1 karniz", {}).get("category") == "profil" and _it["B1 karniz"].get("blok_birlik") is None
      and _it["B1 karniz"].get("blok_chiqishi") is None and _it["B1 karniz"].get("blok_koef") is None
      and _it["B1 karniz"]["delivery_unit"] == "metr", _it.get("B1 karniz"))
check("B11 ombor farqi: rozetka 0,25 → 0,5 blok, karniz 2,5 blok → profil hajmi (0,0025 m³ = 0,00125 blok)",
      yaqin(_st0 - stok(ID["PENO"]), 0.5 + 1.2 + (0.1 * 0.1 * 5 / 2) / 2.0, 1e-6), (_st0, stok(ID["PENO"])))

# Topshirilgan blok detal birligi o'zgarmaydi
_r = A.post("/api/orders", json=buyurtma([blok("B12 plita", "m2", 25, 40, peno=ID["PENO"])], blok_base_price=600_000))
O2 = js(_r).get("id")
_oi2 = (detallar(A, O2).get("items") or [{}])[0]
_rd = A.post("/api/deliveries", json={"order_id": O2, "items": [{"order_item_id": _oi2.get("id"), "quantity": 10.0}]})
check("B12 yuk xati: 10 m² topshirildi (yuk xati birligi «m²»)", _rd.status_code == 200, (_rd.status_code, _rd.text[:300]))
_s = SessionLocal()
_dun = [d.unit for d in _s.query(DeliveryItem).filter(DeliveryItem.order_item_id == _oi2.get("id")).all()]
_s.close()
check("B12b yuk xati qatori birligi — «m²»", _dun == ["m²"], _dun)
_r = A.put(f"/api/orders/{O2}", json=buyurtma([blok("B12 plita", "dona", 25, 40, peno=ID["PENO"])], blok_base_price=600_000))
check("B13 topshirilgan blok detal birligini o'zgartirish (m² → ta) — rad, sabab «o'lchov birligini o'zgartirib bo'lmaydi»",
      _r.status_code in (400, 409) and "birligini o'zgartirib bo'lmaydi" in _r.text
      and (detallar(A, O2).get("items") or [{}])[0].get("blok_birlik") == "m2", (_r.status_code, _r.text[:300]))
_r = A.put(f"/api/orders/{O2}", json=buyurtma([blok("B12 plita", "m2", 25, 45, peno=ID["PENO"])], blok_base_price=600_000))
check("B14 o'sha birlikda miqdorni oshirish — 200", _r.status_code == 200 and yaqin((detallar(A, O2).get("items") or [{}])[0].get("quantity"), 45),
      (_r.status_code, _r.text[:300]))

# Tana qat'iy
_r1 = A.post("/api/orders", json=buyurtma([dict(blok("B15", "metr", 40, 10, peno=ID["PENO"]), blok_birlik="kg")]))
_r2 = A.post("/api/orders", json=buyurtma([dict(blok("B15", "metr", 40, 10, peno=ID["PENO"]), blok_koef=1000)]))
_r3 = A.post("/api/orders", json=buyurtma([dict(blok("B15", "metr", 40, 10, peno=ID["PENO"]), blok_chiqishi=-1)]))
_r4 = A.post("/api/orders", json=buyurtma([blok("B15", "metr", 40, 10, peno=ID["PENO"])], blok_base_price=-5))
check("B15 noma'lum birlik / koeffitsient 1000 / manfiy chiqishi / manfiy asosiy narx — 422, hech narsa yozilmadi",
      [_r1.status_code, _r2.status_code, _r3.status_code, _r4.status_code] == [422, 422, 422, 422],
      [_r1.status_code, _r2.status_code, _r3.status_code, _r4.status_code])

# Eski (zip 211 dan oldingi) API mijozi — blok maydonlarisiz: metr, avvalgidek
_r = A.post("/api/orders", json=buyurtma([{"name": "B16 eski blok", "category": "blok", "length": 0.5, "quantity": 20, "unit_price": 25_000,
                                           "is_coated": False, "penoplast_id": ID["PENO"], "notes": "blok_narxi=1000000,blok_yield=40"}]))
_e = (detallar(A, js(_r).get("id")).get("items") or [{}])[0] if _r.status_code == 200 else {}
check("B16 blok maydonlarisiz (eski sahifa / API) — birlik bo'sh, yetkazish birligi metr, summa avvalgidek",
      _r.status_code == 200 and _e.get("blok_birlik") is None and _e.get("delivery_unit") == "metr" and yaqin(_e.get("total_price"), 500_000),
      (_r.status_code, _e))

# Tayyor mahsulot: ishlab chiqarish birligi
_st1 = stok(ID["PENO"])
_rp = A.post("/api/finished/produce", json={"name": "B17 TM rozetka", "category": "blok", "width": 12, "thickness": 3, "length": 0.5,
                                            "quantity": 100, "is_coated": False, "penoplast_id": ID["PENO"], "unit_price": 3500, "loy_kg": 0,
                                            "blok_birlik": "dona"})
FPB = js(_rp).get("product_id")
check("B17 TM blok (ta): birlik «dona», 100 dona, ombordan 0,5 blok", _rp.status_code == 200 and js(_rp).get("unit") == "dona"
      and yaqin(_st1 - stok(ID["PENO"]), 0.5, 1e-9), (_rp.status_code, _rp.text[:300]))
_rp2 = A.post("/api/finished/produce", json={"name": "B17 TM plita", "category": "blok", "length": 1, "quantity": 25, "is_coated": False,
                                             "penoplast_id": ID["PENO"], "unit_price": 20000, "loy_kg": 0, "blok_birlik": "m2"})
_rp3 = A.post("/api/finished/produce", json={"name": "B17 TM karniz", "category": "blok", "length": 1, "quantity": 40, "is_coated": False,
                                             "penoplast_id": ID["PENO"], "unit_price": 15000, "loy_kg": 0})
_rp4 = A.post("/api/finished/produce", json={"name": "B17 yomon", "category": "blok", "length": 1, "quantity": 4, "is_coated": False,
                                             "penoplast_id": ID["PENO"], "unit_price": 1, "loy_kg": 0, "blok_birlik": "kg"})
check("B18 TM blok m² — «m²»; birliksiz (eski sahifa) — «metr»; noma'lum birlik — 400",
      js(_rp2).get("unit") == "m²" and js(_rp3).get("unit") == "metr" and _rp4.status_code in (400, 422),
      (js(_rp2).get("unit"), js(_rp3).get("unit"), _rp4.status_code, _rp4.text[:200]))
_s = SessionLocal()
_fp = _s.get(FinishedProduct, FPB) if FPB else None     # asl kodda (zip 210) `blok_birlik` — noma'lum maydon: mahsulot yo'q
if _fp is not None:
    _fp.production_status = ProductionStatus.READY
    _s.commit()
_s.close()
# buyurtmada tayyor mahsulotdan — birlik MAHSULOTNIKI (forma boshqa yuborsa ham)
_tm = blok("B19 TM rozetka", "m2", 0, 20, peno=None, fp=FPB)
_tm.update({"unit_price": 3500, "length": 0, "blok_chiqishi": None, "blok_narxi": None, "blok_koef": None, "notes": None})
_r = A.post("/api/orders", json=buyurtma([_tm]))
_t = (detallar(A, js(_r).get("id")).get("items") or [{}])[0] if _r.status_code == 200 else {}
check("B19 tayyor mahsulotdan blok — birlik mahsulotniki («dona», forma «m2» yuborsa ham), 20 × 3 500 = 70 000",
      _r.status_code == 200 and _t.get("blok_birlik") == "dona" and _t.get("delivery_unit") == "dona" and yaqin(_t.get("total_price"), 70_000),
      (_r.status_code, _r.text[:300], _t))

# Usta birliklari (qoplamachi / birlik stavkasi)
_qb = services._qoplama_birliklari


def _OI211(**k):
    """Sinov detali (bazaga yozilmaydi); asl kodda (zip 210) blok ustunlari yo'q — ular tashlanadi (sinov yiqiladi, qulamaydi)."""
    for _k in [x for x in k if x.startswith("blok_")]:
        if not hasattr(OrderItem, _k):
            k.pop(_k)
    return OrderItem(**k)


check("B20 usta birliklari: qoplamali blok m — metr, ta — dona, m² — hech biri; eski (birliksiz) — metr; qoplamasiz — yo'q",
      _qb(_OI211(category="blok", quantity=30, is_coated=True, blok_birlik="metr"))["metr"] == 30
      and _qb(_OI211(category="blok", quantity=50, is_coated=True, blok_birlik="dona"))["dona"] == 50
      and _qb(_OI211(category="blok", quantity=50, is_coated=True, blok_birlik="dona"))["metr"] == 0
      and sum(_qb(_OI211(category="blok", quantity=12, is_coated=True, blok_birlik="m2")).values()) == 0
      and _qb(_OI211(category="blok", quantity=7, is_coated=True))["metr"] == 7
      and sum(_qb(_OI211(category="blok", quantity=7, is_coated=False, blok_birlik="dona")).values()) == 0)


def _oylik(y, m):
    _s = SessionLocal()
    try:
        r = services.get_monthly_report(_s, y, m, company_id=1)
        return float(r.get("jami_metr") or 0), float(r.get("jami_dona") or 0)
    finally:
        _s.close()


_kn0 = _oylik(2026, 11)
_ko0 = _oylik(2026, 10)
_s = SessionLocal()
for _nom, _u, _q, _sana in (("B21 nov m", "metr", 40, datetime.datetime(2026, 11, 10, 8)), ("B21 nov ta", "dona", 7, datetime.datetime(2026, 11, 12, 8)),
                            ("B21 nov m2", "m²", 5, datetime.datetime(2026, 11, 13, 8)), ("B21 okt m", "metr", 3, datetime.datetime(2026, 10, 10, 8))):
    _s.add(FinishedProduct(company_id=1, name=_nom, category="blok", quantity=_q, produced_quantity=_q, unit=_u, unit_price=1000, cost_price=0,
                           source=StockSource.PRODUCED, production_status=ProductionStatus.READY, is_coated=True,
                           created_at=_sana, finished_production_at=_sana))
_s.commit()
_s.close()
_kn1 = _oylik(2026, 11)
_ko1 = _oylik(2026, 10)
check("B21 «Tayyor mahsulotlar» blok (qoplamali) usta hisobi — noyabrdan o'z birligida: +40 m, +7 dona, m² — yo'q; oktyabr — avvalgidek "
      "(3 m «dona» ga — o'tgan hisob o'zgarmaydi)",
      yaqin(_kn1[0] - _kn0[0], 40) and yaqin(_kn1[1] - _kn0[1], 7) and yaqin(_ko1[0] - _ko0[0], 0) and yaqin(_ko1[1] - _ko0[1], 3),
      (_kn0, _kn1, _ko0, _ko1))

# Taklif: «1 blok asosiy narxi» va blok maydonlari
_rt = A.post("/api/takliflar", json={"mijoz": "Taklif mijoz", "buyurtma": buyurtma([blok("B22 taklif", "dona", 100, 30, peno=ID["PENO"])],
                                                                                   blok_base_price=700_000)})
_tid = ((js(_rt).get("taklif") or {}).get("id"))
_tg = js(A.get(f"/api/takliflar/{_tid}")) if _tid else {}
check("B22 taklif: «1 blok asosiy narxi» va detal birligi qaytadi (rasmiylashtirishda forma shundan to'ladi)",
      _rt.status_code == 200 and yaqin(_tg.get("blok_base_price"), 700_000) and (_tg.get("items") or [{}])[0].get("blok_birlik") == "dona",
      (_rt.status_code, _rt.text[:300], _tg.get("blok_base_price")))
_rpdf = A.get(f"/api/takliflar/{_tid}/pdf") if _tid else None
try:
    from pypdf import PdfReader
    _tt = "".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(_rpdf.content)).pages) if _rpdf is not None and _rpdf.status_code == 200 else ""
    check("B22b taklif PDF — blok detal birligi «dona»", "dona" in _tt and "B22 taklif" in _tt, _tt[:400])
except ImportError:
    check("B22b taklif PDF (pypdf yo'q — o'tkazildi)", True)

check("B23 blok maydonlari boshqa korxonaga sizmaydi: B korxona A ning buyurtmasini ko'rmaydi (404)",
      B.get(f"/api/orders/{O1}").status_code == 404)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Mustaqil tekshiruv (review211) tuzatishlari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# №1: qisman «Tayyor» — blok soni ham topshirilgan ulushga (tan narxi)
_r = A.post("/api/orders", json=buyurtma([blok("R1 karniz", "metr", 40, 100, peno=ID["PENO"])], blok_base_price=600_000))
OR1 = js(_r).get("id")
_ir1 = (detallar(A, OR1).get("items") or [{}])[0]
_d1 = A.post("/api/deliveries", json={"order_id": OR1, "items": [{"order_item_id": _ir1.get("id"), "quantity": 40.0}]})
_st_r1 = stok(ID["PENO"])
_t1 = A.post(f"/api/orders/{OR1}/ready")
_s = SessionLocal()
_oi_r1 = _s.get(OrderItem, _ir1.get("id")) if _ir1.get("id") else None
_l_r1 = float(_oi_r1.length or 0) if _oi_r1 is not None else None
_pr_r1 = services.calculate_order_profit(_s, OR1, company_id=1) if OR1 else {}
_s.close()
check("R1 qisman «Tayyor» (100 m dan 40 m): omborga 1,5 blok qaytdi, detal blok soni 1,0 (ilgari 2,5 qolardi), tan narxi 1 × 500 000",
      _d1.status_code == 200 and _t1.status_code == 200 and yaqin(stok(ID["PENO"]) - _st_r1, 1.5, 1e-9) and yaqin(_l_r1, 1.0, 1e-9)
      and yaqin(_pr_r1.get("tan_narxi"), 500_000, 1), (_d1.status_code, _t1.status_code, _t1.text[:200], _l_r1, _pr_r1.get("tan_narxi")))
# №2: qaytgan blok mahsuloti boshqa birlikdagi partiyaga birlashmaydi
_ra = A.post("/api/orders", json=buyurtma([blok("R2 plita", "m2", 25, 30, oz=500_000, peno=ID["PENO"])]))
_rb = A.post("/api/orders", json=buyurtma([blok("R2 plita", "dona", 25, 40, oz=500_000, peno=ID["PENO"])]))
_ia = (detallar(A, js(_ra).get("id")).get("items") or [{}])[0]
_ib = (detallar(A, js(_rb).get("id")).get("items") or [{}])[0]
for _o, _i in ((js(_ra).get("id"), _ia), (js(_rb).get("id"), _ib)):
    A.post("/api/deliveries", json={"order_id": _o, "items": [{"order_item_id": _i.get("id"), "quantity": 20.0}]})
_q1 = A.post("/api/returns", json={"order_id": js(_ra).get("id"), "order_item_id": _ia.get("id"), "item_name": "R2 plita", "quantity": 10,
                                   "unit": "m²", "reason": "Mijoz iltimosi", "to_stock": True})
_q2 = A.post("/api/returns", json={"order_id": js(_rb).get("id"), "order_item_id": _ib.get("id"), "item_name": "R2 plita", "quantity": 5,
                                   "unit": "dona", "reason": "Mijoz iltimosi", "to_stock": True})
_s = SessionLocal()
_qf = sorted((f.unit, float(f.quantity)) for f in _s.query(FinishedProduct).filter(FinishedProduct.company_id == 1,
                                                                                    FinishedProduct.name == "R2 plita").all())
_s.close()
check("R2 qaytgan blok mahsuloti: 10 m² va 5 dona — ALOHIDA partiyalar (ilgari «15 m²» bo'lib birlashardi)",
      _q1.status_code == 200 and _q2.status_code == 200 and _qf == [("dona", 5.0), ("m²", 10.0)], (_q1.status_code, _q1.text[:200], _qf))
# №4: bir xil nomli ikki blok detal (biri topshirilgan, birliklari har xil) — o'zgarishsiz tahrir (forma tartibi teskari) — 200
_r = A.post("/api/orders", json=buyurtma([blok("R4 plita", "m2", 25, 30, peno=ID["PENO"]), blok("R4 plita", "dona", 100, 40, peno=ID["PENO"])],
                                         blok_base_price=600_000))
OR4 = js(_r).get("id")
_i4 = {x.get("blok_birlik"): x for x in (detallar(A, OR4).get("items") or [])}
A.post("/api/deliveries", json={"order_id": OR4, "items": [{"order_item_id": _i4.get("m2", {}).get("id"), "quantity": 10.0}]})
_u4 = A.put(f"/api/orders/{OR4}", json=buyurtma([blok("R4 plita", "dona", 100, 40, peno=ID["PENO"]), blok("R4 plita", "m2", 25, 30, peno=ID["PENO"])],
                                                blok_base_price=600_000))
_i4b = {x["id"]: x for x in (detallar(A, OR4).get("items") or [])}
check("R4 bir xil nomli blok detallar (m² — topshirilgan, ta) teskari tartibda o'zgarishsiz — 200, har biri o'z birligida qoldi",
      _u4.status_code == 200 and _i4b.get(_i4.get("m2", {}).get("id"), {}).get("blok_birlik") == "m2"
      and _i4b.get(_i4.get("dona", {}).get("id"), {}).get("blok_birlik") == "dona", (_u4.status_code, _u4.text[:300]))
# №6: tanada blok maydonlari yo'q (eski sahifa / API) — mavjud blok detal birligi saqlanadi
_r = A.post("/api/orders", json=buyurtma([blok("R6 rozetka", "dona", 200, 50, peno=ID["PENO"])], blok_base_price=600_000))
OR6 = js(_r).get("id")
_eski6 = {k: v for k, v in blok("R6 rozetka", "dona", 200, 50, peno=ID["PENO"]).items() if not k.startswith("blok_")}
_u6 = A.put(f"/api/orders/{OR6}", json=buyurtma([_eski6]))
_i6 = (detallar(A, OR6).get("items") or [{}])[0]
check("R6 eski sahifa tanasi (blok maydonlarisiz) — «ta» detal «ta» qoldi (ilgari jimgina «metr» ga aylanardi), chiqishi saqlandi",
      _u6.status_code == 200 and _i6.get("blok_birlik") == "dona" and _i6.get("delivery_unit") == "dona" and yaqin(_i6.get("blok_chiqishi"), 200),
      (_u6.status_code, _i6))
# №7: topshirilgan detal birligini tayyor mahsulot orqali o'zgartirib bo'lmaydi (samarali birlik)
_r = A.post("/api/orders", json=buyurtma([blok("R7 plita", "m2", 25, 30, peno=ID["PENO"])], blok_base_price=600_000))
OR7 = js(_r).get("id")
_i7 = (detallar(A, OR7).get("items") or [{}])[0]
A.post("/api/deliveries", json={"order_id": OR7, "items": [{"order_item_id": _i7.get("id"), "quantity": 10.0}]})
_tm7 = blok("R7 plita", "m2", 0, 30, fp=FPB)
_tm7.update({"unit_price": 3500, "length": 0, "blok_chiqishi": None, "blok_narxi": None, "blok_koef": None, "notes": None})
_u7 = A.put(f"/api/orders/{OR7}", json=buyurtma([_tm7]))
check("R7 tanada «m2», lekin «dona» tayyor mahsulot — samarali birlik «dona» ≠ topshirilgan «m²» — rad, detal m² qoldi",
      _u7.status_code in (400, 409) and "birligini o'zgartirib bo'lmaydi" in _u7.text
      and (detallar(A, OR7).get("items") or [{}])[0].get("blok_birlik") == "m2", (_u7.status_code, _u7.text[:300]))
# №9: birlik o'zgarishi jurnalda
_r = A.post("/api/orders", json=buyurtma([blok("R9 plita", "m2", 25, 30, peno=ID["PENO"])], blok_base_price=600_000))
OR9 = js(_r).get("id")
A.put(f"/api/orders/{OR9}", json=buyurtma([blok("R9 plita", "dona", 25, 30, peno=ID["PENO"])], blok_base_price=600_000))
_s = SessionLocal()
_j9 = [(a.new_value or "") for a in _s.query(ActivityLog).filter(ActivityLog.company_id == 1, ActivityLog.entity_type == "order",
                                                                 ActivityLog.entity_id == OR9).order_by(ActivityLog.id.desc()).limit(1).all()]
_s.close()
check("R9 birlik m² → ta — «Faoliyat jurnali» da «birlik m² → dona» (ilgari «O'zgardi: hech narsa»)",
      _j9 and "birlik m² → dona" in _j9[0], _j9)
# №12 / №13
_s = SessionLocal()
_ko2 = _oylik(2026, 10)
_s.add(FinishedProduct(company_id=1, name="R12 okt m2", category="blok", quantity=25, produced_quantity=25, unit="m²", unit_price=1000, cost_price=0,
                       source=StockSource.PRODUCED, production_status=ProductionStatus.READY, is_coated=True,
                       created_at=datetime.datetime(2026, 10, 11, 8), finished_production_at=datetime.datetime(2026, 10, 11, 8)))
_s.commit()
_s.close()
_ko3 = _oylik(2026, 10)
check("R12 oktyabrda ishlab chiqarilgan m² blok mahsuloti — metr / dona ga kirmaydi (m² zip 211 dan oldin yo'q edi)",
      yaqin(_ko3[0] - _ko2[0], 0) and yaqin(_ko3[1] - _ko2[1], 0), (_ko2, _ko3))
_qn = services._qoplama_narxi
check("R13 loy taqsimoti — blok qoplama ulushi o'z koeffitsientidan: koef 3 — 300 000 × 2/3 = 200 000; koef yo'q — 2 (150 000); "
      "profil — avvalgidek 2", yaqin(_qn(_OI211(category="blok", is_coated=True, total_price=300_000, blok_koef=3)), 200_000, 0.01)
      and yaqin(_qn(_OI211(category="blok", is_coated=True, total_price=300_000)), 150_000, 0.01)
      and yaqin(_qn(_OI211(category="profil", is_coated=True, total_price=100_000, blok_koef=3)), 50_000, 0.01))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
    import glob
    import socket
    import threading
    import uvicorn
    from playwright.sync_api import sync_playwright
    _sk = socket.socket()
    _sk.bind(("127.0.0.1", 0))
    PORT = _sk.getsockname()[1]
    _sk.close()
    _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error", lifespan="off"))
    threading.Thread(target=_srv.run, daemon=True).start()
    while not _srv.started:
        time.sleep(0.1)
    BASE = f"http://127.0.0.1:{PORT}"
    _exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    XATOLAR = []
    # eski (zip 211 dan oldingi) qoplamali blok yozuvi — C korxonada (ustunlar bo'sh, narx `notes` da: yakuniy 1 500 001 / 40 m)
    _s = SessionLocal()
    _rc = Recipe(company_id=3, name="C qoplama retsepti")       # qoplamali buyurtma tahriri retseptsiz saqlanmaydi (54-band)
    _s.add(_rc)
    _s.flush()
    _eo = Order(company_id=3, order_number="ORD-ESKI-1", project_id=ID["PC"], order_type=OrderType.PRODUCT, total_amount=750_000.6,
                agreed_amount=750_000.6, status=OrderStatus.IN_PROGRESS, deadline=datetime.datetime(2026, 12, 1),
                qoplama_retsept_id=_rc.id)
    _s.add(_eo)
    _s.flush()
    _s.add(OrderItem(company_id=3, order_id=_eo.id, name="Eski qoplamali blok", category="blok", length=0.5, quantity=20,
                     unit_price=37500.03, total_price=750_000.6, is_coated=True, penoplast_id=ID["PENO_C"], recipe_id=_rc.id,
                     notes="blok_narxi=1500001.25,blok_yield=40"))
    _s.commit()
    ID["ESKI"] = _eo.id
    _po = Order(company_id=3, order_number="ORD-PROFIL-1", project_id=ID["PC"], order_type=OrderType.PRODUCT, total_amount=50_000,
                agreed_amount=50_000, status=OrderStatus.IN_PROGRESS, deadline=datetime.datetime(2026, 12, 1), base_price=1_000_000)
    _s.add(_po)
    _s.flush()
    _s.add(OrderItem(company_id=3, order_id=_po.id, name="Eski profil", category="profil", width=10, thickness=10, length=10, quantity=1,
                     unit_price=50_000, total_price=50_000, is_coated=False, penoplast_id=ID["PENO_C"]))
    _s.commit()
    ID["PROFIL_C"] = _po.id
    _eo2 = Order(company_id=3, order_number="ORD-ESKI-2", project_id=ID["PC"], order_type=OrderType.PRODUCT, total_amount=50_001,
                 agreed_amount=50_001, status=OrderStatus.IN_PROGRESS, deadline=datetime.datetime(2026, 12, 1), qoplama_retsept_id=_rc.id)
    _s.add(_eo2)
    _s.flush()
    _s.add(OrderItem(company_id=3, order_id=_eo2.id, name="Eski yarim tiyin blok", category="blok", length=50, quantity=100,
                     unit_price=500.01, total_price=50_001, is_coated=True, penoplast_id=ID["PENO_C"], recipe_id=_rc.id,
                     notes="blok_narxi=1000.01,blok_yield=2"))
    _s.commit()
    ID["ESKI2"] = _eo2.id
    _s.close()

    def _ui():
      with sync_playwright() as pw:
          br = pw.chromium.launch(executable_path=_exe[-1] if _exe else None)

          def kontekst(login, w=1440, h=900):
              ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent")
              ctx.route("**/*", lambda r: r.fulfill(status=204, body="") if not r.request.url.startswith(BASE) else r.continue_())
              pg = ctx.new_page()
              pg.set_default_timeout(10000)
              pg.on("pageerror", lambda e: XATOLAR.append(str(e)[:200]))
              pg.on("dialog", lambda d: d.accept())
              pg.goto(BASE + "/login")
              pg.fill("input[name=username]", login)
              pg.fill("input[name=password]", PAROL)
              pg.press("input[name=password]", "Enter")
              pg.wait_for_load_state("networkidle")
              return ctx, pg

          def qator_holati(pg):
              return pg.evaluate("""() => { const r = document.querySelector('#items .detal'); const v = s => r.querySelector(s);
                  const korinadi = s => { const e = s.startsWith('#') ? document.querySelector(s) : v(s); return !!e && e.offsetParent !== null; };
                  return {tur: v('.i-type').value, turlar: [...r.querySelectorAll('.type-opt')].map(o => o.textContent.trim()),
                    variantlar: [...v('.i-type').options].map(o => o.value), birlik: v('.i-blokunit').value,
                    faol: [...r.querySelectorAll('.blokunit-opt.active')].map(o => o.textContent.trim()),
                    lYorliq: v('.i-l-label').textContent, qYorliq: v('.i-q-label').textContent, permYorliq: v('.i-perm-label').textContent,
                    perm: v('.i-perm').value, jami: v('.i-price').value, hajm: v('.i-vol').value,
                    blokNarx: korinadi('.i-blokprice'), m3: korinadi('.i-m3price'), koef: korinadi('.i-blokmult'), birlikTanlov: korinadi('.blokunit-toggle'),
                    eni: korinadi('.i-h'), qalin: korinadi('.i-t'), chiqishi: korinadi('.i-l'), upNarx: korinadi('.i-unitprice'),
                    kubAsosiy: korinadi('#base_price'), blokAsosiy: korinadi('#blok_base_price')}; }""")

          def tasdiqla(pg, marta=3):
              # `updateOrder` va boshqalar tasdiq oynasini (`showConfirmModal` — #genericConfirmOk) kutadi: so'rov ketishi uchun bosiladi
              for _ in range(marta):
                  pg.wait_for_timeout(500)
                  if not pg.evaluate("() => { const b = document.getElementById('genericConfirmOk'); if (b && b.offsetParent !== null) { b.click(); return true; } return false; }"):
                      break

          def yoz(pg, sel, qiymat):
              pg.evaluate("""([sel, q]) => { const r = document.querySelector('#items .detal'); const e = sel.startsWith('#') ? document.querySelector(sel)
                  : r.querySelector(sel); e.value = q; e.dispatchEvent(new Event('input', {bubbles: true})); }""", [sel, qiymat])
              pg.wait_for_timeout(60)

          ctx, pg = kontekst("k211_c")
          pg.goto(BASE + "/orders", wait_until="networkidle")
          pg.evaluate("() => { showNewForm(); }")
          pg.wait_for_timeout(400)
          h0 = qator_holati(pg)
          check("U1 faqat Blok yoqiq korxona: tur tugmasi faqat «🧊 Blok», tanlovda faqat blok; yangi detal — Blok; «1 m³ asosiy narxi» yo'q, "
                "«1 blok asosiy narxi» bor",
                h0["turlar"] == ["🧊 Blok"] and h0["variantlar"] == ["blok"] and h0["tur"] == "blok" and not h0["kubAsosiy"] and h0["blokAsosiy"], h0)
          check("U2 blok detal maydonlari: birlik tanlovi (m tanlangan), Eni / Qalinligi (ixtiyoriy), chiqishi, «1 blok narxi», koeffitsient; "
                "«1 m³ narxi» yo'q", h0["birlikTanlov"] and h0["faol"] == ["m"] and h0["eni"] and h0["qalin"] and h0["chiqishi"]
                and h0["blokNarx"] and h0["koef"] and not h0["m3"] and h0["lYorliq"] == "1 blokdan chiqadigan m", h0)
          yoz(pg, ".i-name", "Rozetka R-1")
          pg.evaluate("() => document.querySelector('#items .detal .blokunit-opt[data-value=\"dona\"]').click()")
          yoz(pg, "#blok_base_price", "600 000")
          yoz(pg, ".i-l", "200")
          yoz(pg, ".i-q", "50")
          h1 = qator_holati(pg)
          bosh = lambda x: str(x).replace(" ", " ").replace(" ", " ")   # noqa: E731
          check("U3 ta: yorliqlar «1 blokdan chiqadigan ta» / «Necha ta kerak» / «1 ta narxi»; 600 000 ÷ 200 = 3 000, × 50 = 150 000; "
                "hajm 0,25 blok", h1["birlik"] == "dona" and h1["faol"] == ["ta"] and h1["lYorliq"] == "1 blokdan chiqadigan ta"
                and h1["qYorliq"] == "Necha ta kerak" and h1["permYorliq"] == "1 ta narxi" and bosh(h1["perm"]) == "3 000"
                and bosh(h1["jami"]) == "150 000" and "0,25 blok" in bosh(h1["hajm"]), h1)
          pg.evaluate("() => document.querySelector('#items .detal .coat-yes').click()")
          pg.wait_for_timeout(80)
          h2 = qator_holati(pg)
          yoz(pg, ".i-blokmult", "1.5")
          h3 = qator_holati(pg)
          yoz(pg, ".i-blokprice", "500 000")
          h4 = qator_holati(pg)
          check("U4 qoplama «Bor» — ×2 (300 000); koeffitsient 1,5 — 225 000; o'z blok narxi 500 000 (asosiydan ustun) — 2 500 × 1,5 = 3 750, "
                "jami 187 500", bosh(h2["jami"]) == "300 000" and bosh(h3["jami"]) == "225 000" and bosh(h4["perm"]) == "3 750"
                and bosh(h4["jami"]) == "187 500", [h2["jami"], h3["jami"], h4["perm"], h4["jami"]])
          pg.evaluate("() => document.querySelector('#items .detal .coat-no').click()")
          yoz(pg, ".i-blokprice", "")
          pg.evaluate("() => document.querySelector('#items .detal .blokunit-opt[data-value=\"m2\"]').click()")
          yoz(pg, ".i-l", "25")
          yoz(pg, ".i-q", "30")
          h5 = qator_holati(pg)
          check("U5 m²: «1 blokdan chiqadigan m²», «Necha m² kerak», «1 m² narxi»; asosiy 600 000 ÷ 25 = 24 000, × 30 = 720 000",
                h5["lYorliq"] == "1 blokdan chiqadigan m²" and h5["qYorliq"] == "Necha m² kerak" and h5["permYorliq"] == "1 m² narxi"
                and bosh(h5["perm"]) == "24 000" and bosh(h5["jami"]) == "720 000", h5)
          pg.evaluate("() => document.querySelector('#items .detal .blokunit-opt[data-value=\"dona\"]').click()")
          yoz(pg, ".i-l", "200")
          yoz(pg, ".i-q", "50")
          yoz(pg, ".i-blokprice", "500 000")
          yoz(pg, ".i-h", "12")
          yoz(pg, ".i-t", "3")
          pg.evaluate(f"() => {{ document.getElementById('project_id').value = '{ID['PC']}'; document.getElementById('deadline_input').value = '2026-12-01'; }}")
          # «1 blokdan chiqadigan» bo'sh — saqlanmaydi
          yoz(pg, ".i-l", "")
          pg.evaluate("() => { saveOrder(); }")
          pg.wait_for_timeout(700)
          _val = pg.evaluate("() => { const m = document.getElementById('validationModal'); return m && m.style.display === 'flex' ? m.textContent : ''; }")
          check("U6 «1 blokdan chiqadigan ta» bo'sh — saqlanmaydi (kamchiliklar oynasi shu sabab bilan)", "1 blokdan chiqadigan ta" in _val, _val[:300])
          pg.evaluate("() => closeValidationModal()")
          yoz(pg, ".i-l", "200")
          _oldin = {o["id"] for o in (js(C.get("/api/orders")) or [])}
          pg.evaluate("() => { saveOrder(); }")
          tasdiqla(pg)
          pg.wait_for_timeout(1500)
          _yangi = [o for o in (js(C.get("/api/orders")) or []) if o["id"] not in _oldin]
          OU = _yangi[0]["id"] if _yangi else None
          _du = detallar(C, OU) if OU else {}
          _iu = (_du.get("items") or [{}])[0]
          check("U7 saqlandi: birlik dona, chiqishi 200, o'z blok narxi 500 000, koeffitsient 1,5 (qoplamasiz), o'lcham 12×3, 1 ta 2 500, "
                "jami 125 000; asosiy narx 600 000",
                _iu.get("blok_birlik") == "dona" and yaqin(_iu.get("blok_chiqishi"), 200) and yaqin(_iu.get("blok_narxi"), 500_000)
                and yaqin(_iu.get("blok_koef"), 1.5) and _iu.get("width") == 12 and _iu.get("thickness") == 3
                and yaqin(_iu.get("unit_price"), 2500) and yaqin(_iu.get("total_price"), 125_000) and yaqin(_du.get("blok_base_price"), 600_000)
                and yaqin(_iu.get("length"), 0.25, 1e-9), (_du.get("blok_base_price"), _iu))
          if OU:
              pg.goto(f"{BASE}/orders?order={OU}", wait_until="networkidle")
              pg.wait_for_timeout(700)
              pg.evaluate("() => { editSelected(); }")
              pg.wait_for_timeout(1300)
              h6 = qator_holati(pg)
              _maydon = pg.evaluate("""() => { const r = document.querySelector('#items .detal');
                  return {l: r.querySelector('.i-l').value, q: r.querySelector('.i-q').value, bp: r.querySelector('.i-blokprice').value,
                          k: r.querySelector('.i-blokmult').value, h: r.querySelector('.i-h').value, t: r.querySelector('.i-t').value,
                          asosiy: document.getElementById('blok_base_price').value}; }""")
              check("U8 tahrirda tiklandi: «ta» tanlangan, chiqishi 200, kerak 50, o'z narxi 500 000, koeffitsient 1,5, o'lcham 12 / 3, "
                    "asosiy 600 000; jami 125 000",
                    h6["faol"] == ["ta"] and _maydon["l"] == "200" and _maydon["q"] == "50" and bosh(_maydon["bp"]) == "500 000"
                    and _maydon["k"] == "1.5" and _maydon["h"] == "12" and _maydon["t"] == "3" and bosh(_maydon["asosiy"]) == "600 000"
                    and bosh(h6["jami"]) == "125 000", (h6, _maydon))
              pg.evaluate(f"() => {{ updateOrder({OU}); }}")
              tasdiqla(pg)
              pg.wait_for_timeout(1500)
              _du2 = detallar(C, OU)
              check("U9 o'zgarishsiz saqlash — summa va blok maydonlari o'zgarmadi", yaqin(_du2.get("total_amount"), 125_000)
                    and (_du2.get("items") or [{}])[0].get("blok_birlik") == "dona", (_du2.get("total_amount"), (_du2.get("items") or [{}])[0]))
          # eski qoplamali yozuv
          pg.goto(f"{BASE}/orders?order={ID['ESKI']}", wait_until="networkidle")
          pg.wait_for_timeout(700)
          pg.evaluate("() => { editSelected(); }")
          pg.wait_for_timeout(1300)
          h7 = qator_holati(pg)
          _m7 = pg.evaluate("""() => { const r = document.querySelector('#items .detal');
              return {l: r.querySelector('.i-l').value, bp: r.querySelector('.i-blokprice').value, k: r.querySelector('.i-blokmult').value}; }""")
          check("U10 eski (zip 211 dan oldingi) qoplamali blok: metr, chiqishi 40, o'z narxi = 1 500 001,25 ÷ 2 = 750 000,63 (maydonda), "
                "koeffitsient 2; 1 m narxi o'zgarmadi (37 500,03)",
                h7["faol"] == ["m"] and _m7["l"] == "40" and bosh(_m7["bp"]) == "750 000.63" and _m7["k"] == "2"
                and bosh(h7["perm"]) in ("37 500", "37 500,03"), (h7, _m7))
          pg.evaluate(f"() => {{ updateOrder({ID['ESKI']}); }}")
          tasdiqla(pg)
          pg.wait_for_timeout(1500)
          _de = detallar(C, ID["ESKI"])
          _ie = (_de.get("items") or [{}])[0]
          check("U11 eski yozuvni o'zgarishsiz saqlash — 1 m narxi (37 500,03) va jami O'ZGARMADI, endi ustunlar to'ldirildi (metr, 40, koef 2)",
                yaqin(_ie.get("unit_price"), 37500.03, 0.0001) and yaqin(_ie.get("total_price"), 750_000.6, 0.0001)
                and _ie.get("blok_birlik") == "metr" and yaqin(_ie.get("blok_chiqishi"), 40) and yaqin(_ie.get("blok_koef"), 2), _ie)
          # review211 №8: eski qoplamali yozuv — yarim tiyinli blok narxi (1 000,01 ÷ 2 = 500,005)
          pg.goto(f"{BASE}/orders?order={ID['ESKI2']}", wait_until="networkidle")
          pg.wait_for_timeout(700)
          pg.evaluate("() => { editSelected(); }")
          pg.wait_for_timeout(1300)
          pg.evaluate(f"() => {{ updateOrder({ID['ESKI2']}); }}")
          tasdiqla(pg)
          pg.wait_for_timeout(1500)
          _ie2 = (detallar(C, ID["ESKI2"]).get("items") or [{}])[0]
          check("U11c eski qoplamali yozuv (1 000,01 / 2 m, 100 m) o'zgarishsiz saqlandi — 1 m 500,01, jami 50 001 (ilgari 500,00 / 50 000)",
                yaqin(_ie2.get("unit_price"), 500.01, 0.0001) and yaqin(_ie2.get("total_price"), 50_001, 0.0001) and _ie2.get("blok_birlik") == "metr",
                _ie2)
          _yb = pg.evaluate("() => [yetkazishBirligi('metr'), yetkazishBirligi('dona'), yetkazishBirligi('m²'), yetkazishBirligi('kg'), "
                            "yetkazishBirligi('m²', false), yetkazishBirligi('')]")
          check("U11d yetkazish oynalari / tavsiya birligi (review211 №3 / №5): metr «m», dona « ta», m² « m²», kg « kg»",
                _yb == ["m", " ta", " m²", " kg", "m²", " ta"], _yb)
          # yashirin (Profil) turdagi mavjud detal — shu qatorga tugma; «1 m³ asosiy narxi» ko'rinadi, narx o'zgarmaydi
          pg.goto(f"{BASE}/orders?order={ID['PROFIL_C']}", wait_until="networkidle")
          pg.wait_for_timeout(700)
          pg.evaluate("() => { editSelected(); }")
          pg.wait_for_timeout(1300)
          hp = qator_holati(pg)
          check("U11b faqat Blok korxonada mavjud PROFIL detal: shu qatorga «📏 Profil» tugmasi va varianti, «1 m³ asosiy narxi» ko'rinadi, "
                "jami 50 000 (o'zgarmadi)", "📏 Profil" in hp["turlar"] and "profil" in hp["variantlar"] and hp["tur"] == "profil"
                and hp["kubAsosiy"] and bosh(hp["jami"]) == "50 000", hp)
          # telefon
          ctxt, pgt = kontekst("k211_c", 390, 844)
          pgt.goto(BASE + "/orders", wait_until="networkidle")
          pgt.evaluate("() => { showNewForm(); }")
          pgt.wait_for_timeout(400)
          _sur = pgt.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
          _tl = pgt.evaluate("""() => { const t = document.querySelector('#items .detal .blokunit-toggle').getBoundingClientRect();
              return {w: t.width, right: t.right, vw: window.innerWidth}; }""")
          check("U12 telefon 390 px: gorizontal surilish yo'q, birlik tanlovi ekranda", _sur <= 0 and _tl["right"] <= _tl["vw"] and _tl["w"] > 100,
                (_sur, _tl))
          ctxt.close()
          # qoralama: blok asosiy narxi va birlik tiklanadi
          pg.goto(BASE + "/orders", wait_until="networkidle")
          pg.evaluate("() => { localStorage.clear(); showNewForm(); }")
          pg.wait_for_timeout(300)
          yoz(pg, ".i-name", "Qoralama plita")
          pg.evaluate("() => document.querySelector('#items .detal .blokunit-opt[data-value=\"m2\"]').click()")
          yoz(pg, "#blok_base_price", "550 000")
          yoz(pg, ".i-l", "22")
          yoz(pg, ".i-q", "11")
          pg.evaluate(f"() => {{ document.getElementById('project_id').value = '{ID['PC']}'; saveDraftLS(); }}")
          pg.wait_for_timeout(200)
          _dr = pg.evaluate("() => localStorage.getItem(ORDER_DRAFT_LS_KEY)")
          # sahifa yangidan ochilgandek: forma yopiladi va «1 blok asosiy narxi» maydoni bo'shatiladi — qiymat FAQAT qoralamadan tiklanishi kerak
          pg.evaluate("() => { hideNewForm(); const b = document.getElementById('blok_base_price'); if (b) b.value = ''; }")
          pg.evaluate("(d) => { restoreDraftLS(JSON.parse(d)); }", _dr)
          pg.wait_for_timeout(500)
          h8 = qator_holati(pg)
          _ab = pg.evaluate("() => document.getElementById('blok_base_price').value")
          check("U13 qoralama: «1 blok asosiy narxi» 550 000, birlik m², yorliqlar m², 550 000 ÷ 22 × 11 = 275 000",
                bosh(_ab) == "550 000" and h8["faol"] == ["m²"] and h8["qYorliq"] == "Necha m² kerak" and bosh(h8["jami"]) == "275 000", (_ab, h8))
          # Sozlamalar sahifasi
          pg.goto(BASE + "/sozlamalar", wait_until="networkidle")
          pg.wait_for_timeout(600)
          _cb = pg.evaluate("() => [...document.querySelectorAll('.cat-cb')].map(c => [c.value, c.checked])")
          PUTLAR = []
          pg.on("request", lambda q: PUTLAR.append(q.post_data or "") if (q.method == "PUT" and "/api/settings/categories" in q.url) else None)
          pg.evaluate("() => { document.querySelectorAll('.cat-cb').forEach(c => c.checked = false); saveCategories(); }")
          pg.wait_for_timeout(500)
          _xab = pg.evaluate("() => document.getElementById('cat-status').textContent")
          check("U14 Sozlamalar: 6 tur (faqat Blok belgilangan); hammasini o'chirib «Saqlash» — so'rov YUBORILMAYDI, «Kamida bitta …» xabari",
                [x[0] for x in _cb] == ["profil", "panel", "dona", "blok", "loy_sotish", "mrp_product"] and [x[0] for x in _cb if x[1]] == ["blok"]
                and not PUTLAR and "Kamida bitta" in _xab, (_cb, PUTLAR, _xab))
          pg.evaluate("() => { document.querySelectorAll('.cat-cb').forEach(c => c.checked = ['blok', 'loy_sotish'].includes(c.value)); saveCategories(); }")
          pg.wait_for_timeout(1500)
          check("U15 «Blok, Loy sotish» saqlandi (`v=2` bilan) — server holati shu", PUTLAR and "v" in PUTLAR[-1]
                and turlar(C) == {"profil": False, "panel": False, "dona": False, "blok": True, "loy_sotish": True, "mrp_product": False},
                (PUTLAR[-1:], turlar(C)))
          C.put("/api/settings/categories", data={"codes": "blok", "v": "2"})
          # Tayyor mahsulotlar — blok ishlab chiqarish
          pg.goto(BASE + "/finished", wait_until="networkidle")
          pg.wait_for_timeout(500)
          pg.evaluate("() => openProduceModal()")
          pg.wait_for_timeout(300)
          _tm = pg.evaluate("""() => ({turlar: [...document.querySelectorAll('#p-type-toggle .type-opt')].map(o => o.textContent.trim()),
              tur: document.getElementById('p-type').value, birlik: document.getElementById('p-blokunit-wrap').offsetParent !== null,
              m3: document.getElementById('p-m3').offsetParent !== null})""")
          check("U16 Tayyor mahsulotlar oynasi: tur faqat «🧊 Blok», birlik tanlovi bor, «1 m³ narxi» yo'q", _tm["turlar"] == ["🧊 Blok"]
                and _tm["tur"] == "blok" and _tm["birlik"] and not _tm["m3"], _tm)
          pg.evaluate("""() => { const f = (id, v) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); };
              f('p-name', 'TM Rozetka C'); setPBlokUnit('dona'); f('p-l', '200'); f('p-q', '100'); f('p-blokprice', '450 000');
              setPCoating(document.querySelector('#p-coat-toggle .coat-no'), false); }""")
          pg.wait_for_timeout(200)
          _pc = pg.evaluate("() => ({c: window._pCalc, lbl: document.getElementById('p-l-label').textContent, q: document.getElementById('p-q-label').textContent, u: document.getElementById('p-unit-label').textContent})")
          _stc0 = stok(ID["PENO_C"])
          pg.evaluate("() => { saveProduce(); }")
          pg.wait_for_timeout(1500)
          _s = SessionLocal()
          _tmc = _s.query(FinishedProduct).filter(FinishedProduct.company_id == 3, FinishedProduct.name == "TM Rozetka C").first()
          _tmc_d = None if _tmc is None else (_tmc.unit, float(_tmc.quantity), float(_tmc.unit_price), _tmc.id)
          if _tmc is not None:
              _tmc.production_status = ProductionStatus.READY
              _s.commit()
          _s.close()
          check("U17 TM blok (ta): yorliqlar ta, 450 000 ÷ 200 = 2 250 so'm/ta; saqlandi — birlik «dona», 100, narx 2 250, ombordan 0,5 blok",
                _pc["lbl"] == "1 blokdan chiqadigan ta" and _pc["q"] == "Necha ta kerak" and _pc["u"] == "dona"
                and yaqin((_pc["c"] or {}).get("perUnitPrice"), 2250) and _tmc_d and _tmc_d[:3] == ("dona", 100.0, 2250.0)
                and yaqin(_stc0 - stok(ID["PENO_C"]), 0.5, 1e-9), (_pc, _tmc_d, _stc0, stok(ID["PENO_C"])))
          # buyurtmaga tayyor mahsulotdan
          if _tmc_d:
              pg.goto(BASE + "/orders", wait_until="networkidle")
              pg.evaluate("() => { localStorage.clear(); showNewForm(); }")
              pg.wait_for_timeout(300)
              _fpj = js(C.get("/api/finished"))
              _fpo = [f for f in (_fpj if isinstance(_fpj, list) else []) if f.get("id") == _tmc_d[3]]
              if _fpo:
                  pg.evaluate("""(fp) => { const r = document.querySelector('#items .detal'); const el = document.createElement('div');
                      el.dataset.fp = JSON.stringify(fp); r.appendChild(el); pickFinished(el); }""", _fpo[0])
                  pg.wait_for_timeout(300)
                  yoz(pg, ".i-q", "30")
                  h9 = qator_holati(pg)
                  _lock = pg.evaluate("() => { const r = document.querySelector('#items .detal'); const before = r.querySelector('.i-blokunit').value; "
                                      "r.querySelector('.blokunit-opt[data-value=\"m2\"]').click(); return [before, r.querySelector('.i-blokunit').value]; }")
                  check("U18 buyurtmaga TM blok: birlik «ta» (mahsulotniki, o'zgarmaydi), «1 ta narxi» = 2 250 ko'rinadi, chiqishi / blok narxi "
                        "yashirin; 30 × 2 250 = 67 500",
                        h9["faol"] == ["ta"] and h9["upNarx"] and not h9["chiqishi"] and not h9["blokNarx"] and bosh(h9["jami"]) == "67 500"
                        and _lock == ["dona", "dona"], (h9, _lock))
              else:
                  check("U18 buyurtmaga TM blok (mahsulot ro'yxatda)", False, _fpj)
          # review211 №10: faqat MRP yoqiq korxona — mahsulot turi tanlanmagan MRP qatori saqlanmaydi
          # oldingi (U18 — TM blok) forma qoralamasi sahifadan chiqishda saqlanib, keyingi ochilishda JIM tiklanadi (77-band — mo'ljallangan)
          # — toza forma uchun shu sahifaning qoralama saqlovchisi o'chiriladi
          pg.evaluate("() => { if (typeof saveDraftLS === 'function') { window.removeEventListener('pagehide', saveDraftLS); "
                      "window.removeEventListener('beforeunload', saveDraftLS); } localStorage.clear(); }")
          _rm = C.put("/api/settings/categories", data={"codes": "mrp_product", "v": "2"})
          pg.goto(BASE + "/orders", wait_until="networkidle")
          pg.evaluate("() => { localStorage.clear(); showNewForm(); }")
          pg.wait_for_timeout(300)
          yoz(pg, ".i-name", "MRP tanlanmagan")
          yoz(pg, ".i-unitprice", "120 000")
          pg.evaluate(f"() => {{ document.getElementById('project_id').value = '{ID['PC']}'; document.getElementById('deadline_input').value = '2026-12-01'; saveOrder(); }}")
          pg.wait_for_timeout(700)
          _vm = pg.evaluate("() => { const m = document.getElementById('validationModal'); return m && m.style.display === 'flex' ? m.textContent : ''; }")
          _vd = pg.evaluate("""() => { const r = document.querySelector('#items .detal'); let k = null;
              try { k = buyurtmaUmumiyKamchiliklar(collectItems()).map(x => x.text); } catch (e) { k = 'XATO ' + e.message; }
              return {tur: r && r.querySelector('.i-type').value, nom: r && r.querySelector('.i-name').value, pt: r && r.dataset.mrpProductTypeId,
                      kamchilik: k, edit: typeof editMode !== 'undefined' ? editMode : null, msg: (document.getElementById('msg') || {}).textContent,
                      variant: r ? [...r.querySelectorAll('.i-type option')].map(o => o.value) : null,
                      tugma: r ? [...r.querySelectorAll('.type-opt')].map(o => o.dataset.value) : null,
                      qatorlar: document.querySelectorAll('#items .detal').length}; }""")
          _vd["put"] = (_rm.status_code, _rm.text[:200], turlar(C))
          check("U18b faqat MRP yoqiq korxona: qatorda faqat MRP turi; mahsulot turi tanlanmagan MRP qatori — saqlanmaydi («MRP mahsuloti "
                "tanlanmagan»)",
                "MRP mahsuloti tanlanmagan" in _vm and _vd.get("variant") == ["mrp_product"] and _vd.get("tugma") == ["mrp_product"],
                (_vm[:300], _vd))
          pg.evaluate("() => closeValidationModal()")
          C.put("/api/settings/categories", data={"codes": "blok", "v": "2"})
          ctx.close()
          # A korxona (Blok yashirin) — mavjud blok detalli buyurtma
          A.put("/api/settings/categories", data={"codes": "profil,panel,dona,loy_sotish,mrp_product", "v": "2"})
          ctxa, pga = kontekst("k211_a")
          pga.goto(f"{BASE}/orders?order={O2}", wait_until="networkidle")
          pga.wait_for_timeout(700)
          pga.evaluate("() => { editSelected(); }")
          pga.wait_for_timeout(1300)
          ha = qator_holati(pga)
          check("U19 Blok yashirin korxonada mavjud blok detal: shu qatorga «🧊 Blok» tugmasi va varianti qo'shildi, birlik m² (topshirilgan — "
                "o'zgarmaydi), «1 blok asosiy narxi» maydoni ko'rinadi",
                "🧊 Blok" in ha["turlar"] and "blok" in ha["variantlar"] and ha["tur"] == "blok" and ha["faol"] == ["m²"] and ha["blokAsosiy"], ha)
          _ch = pga.evaluate("() => { const r = document.querySelector('#items .detal'); r.querySelector('.blokunit-opt[data-value=\"metr\"]').click(); "
                             "return r.querySelector('.i-blokunit').value; }")
          check("U20 topshirilgan blok detal birligini UI da o'zgartirib bo'lmaydi (m² qoldi)", _ch == "m2", _ch)
          pga.evaluate("() => { hideNewForm(); showNewForm(); }")
          pga.wait_for_timeout(300)
          hb = qator_holati(pga)
          check("U21 o'sha korxonada YANGI detal — Blok yo'q (Profil, Panel, Donali, Loy sotish, MRP); «1 blok asosiy narxi» yashirin",
                "🧊 Blok" not in hb["turlar"] and hb["variantlar"] == ["profil", "panel", "dona", "loy_sotish", "mrp_product"] and hb["kubAsosiy"]
                and not hb["blokAsosiy"], hb)
          ctxa.close()
          # sinov saytida jonli sinov (24.10) topgani: 1440 px ekranda blok detal maydonlari 24 px ga tushardi (yozilgan son ko'rinmasdi);
          # qoplama tugmasi doim «Bor (×2)» edi (koeffitsient 2,5 bo'lsa ham)
          ctxw, pgw = kontekst("k211_c", 1440, 900)
          pgw.goto(BASE + "/orders", wait_until="networkidle")
          pgw.evaluate("() => { localStorage.clear(); showNewForm(); }")
          pgw.wait_for_timeout(300)
          _lw = pgw.evaluate("""() => { const r = document.querySelector('#items .detal'); const w = s => Math.round(r.querySelector(s).getBoundingClientRect().width);
              const rw = r.getBoundingClientRect(); const qutilar = [...r.querySelectorAll('.dgrp-flex-row > .dgrp')].filter(b => b.offsetParent)
                .map(b => b.getBoundingClientRect());
              return {q: w('.i-q'), l: w('.i-l'), h: w('.i-h'), t: w('.i-t'), sigadi: qutilar.length === 2 && qutilar.every(b => b.right <= rw.right + 1),
                      oyna: Math.round(rw.width)}; }""")
          check("U23 1440 px ekran: blok detal maydonlari o'qiladigan kenglikda (≥ 60 px), «O'lcham» / «Miqdor va narx» qatordan chiqmaydi",
                min(_lw["q"], _lw["l"], _lw["h"], _lw["t"]) >= 60 and _lw["sigadi"], _lw)
          _ky = pgw.evaluate("""() => { const r = document.querySelector('#items .detal'); r.querySelector('.coat-yes').click();
              const k = r.querySelector('.i-blokmult'); k.value = '2.5'; k.dispatchEvent(new Event('input', {bubbles: true}));
              return r.querySelector('.coat-yes').textContent; }""")
          pgw.goto(BASE + "/finished", wait_until="networkidle")
          _kf = pgw.evaluate("""() => { openProduceModal(); const k = document.getElementById('p-blokmult'); k.value = '3';
              k.dispatchEvent(new Event('input', {bubbles: true})); return document.querySelector('#p-coat-toggle .coat-yes').textContent; }""")
          check("U24 qoplama tugmasi koeffitsient bilan: buyurtma «Bor (×2,5)», tayyor mahsulot «Bor (×3)» (ilgari doim «×2»)",
                _ky == "Bor (×2,5)" and _kf == "Bor (×3)", (_ky, _kf))
          ctxw.close()
          br.close()
    try:
        _ui()
    except Exception as _e:                 # noqa: BLE001
        check("U0 brauzer bo'limi xatosiz yakunlandi", False, f"{type(_e).__name__}: {str(_e)[:400]}")
    check("U22 sahifa JS xatosi yo'q", not XATOLAR, XATOLAR[:5])
    _srv.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
